"""GERENCIA COMERCIAL — Brokers Internos, ranking, proyección vs real y Trackers de pasos.
Módulo con identidad propia (no se fusiona). Trackers configurables por el Admin.
"""
import uuid
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Request
from database import db

gcom = APIRouter(prefix="/gerencia-comercial")

BROKERS_INTERNOS = [
    {"codigo": "mutuaria", "nombre": "Mutuaria y Leasing Ilimitada"},
    {"codigo": "demanet", "nombre": "De Manet Servicios Financieros"},
    {"codigo": "josemaria", "nombre": "José María"},
]

TRACKER_ESCRITURA = [
    {"id": "firma_escritura", "label": "Firma de escritura", "plazo_habiles": None},
    {"id": "firma_banco_alzante", "label": "Firma banco alzante", "plazo_habiles": 2},
    {"id": "firma_concreces", "label": "Firma Concreces", "plazo_habiles": 2},
    {"id": "firma_cliente_mandatario", "label": "Firma cliente y mandatario", "plazo_habiles": 2},
    {"id": "firma_codeudor", "label": "Firma codeudor", "condicional": True, "plazo_habiles": 2},
    {"id": "cierre_copia", "label": "Cierre de copia", "plazo_habiles": 3},
    {"id": "ingreso_notaria", "label": "Ingreso a notaría", "plazo_habiles": 2},
    {"id": "salida_notaria", "label": "Salida de notaría", "plazo_habiles": 5},
    {"id": "ingreso_cbr", "label": "Ingreso a Conservador de Bienes Raíces", "plazo_habiles": 3},
    {"id": "cierre_definitivo", "label": "Cierre definitivo", "plazo_habiles": 5},
]

TRACKER_ADMINISTRATIVO = [
    {"id": "recepcion_carpeta", "label": "Recepción de carpeta"},
    {"id": "validacion_documental", "label": "Validación documental"},
    {"id": "estudio_titulo", "label": "Solicitud estudio de título"},
    {"id": "envio_mesa", "label": "Envío a mesa"},
    {"id": "aprobacion", "label": "Aprobación"},
    {"id": "instrucciones_escrituracion", "label": "Instrucciones de escrituración"},
    {"id": "archivo_final", "label": "Archivo y cierre administrativo"},
]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _claims(request):
    return getattr(request.state, "user", {}) or {}


def _exigir(request, roles):
    c = _claims(request)
    if c.get("rol") not in roles:
        raise HTTPException(status_code=403, detail="Su rol no tiene acceso a esta función de Gerencia Comercial")
    return c


async def seed_gerencia_comercial():
    """Siembra idempotente: brokers internos + plantillas de trackers."""
    for b in BROKERS_INTERNOS:
        await db.brokers_internos.update_one({"codigo": b["codigo"]}, {"$setOnInsert": {
            "id": str(uuid.uuid4()), "codigo": b["codigo"], "nombre": b["nombre"],
            "tipo": "interno", "creado": _now()}}, upsert=True)
    for tipo, pasos in (("escritura", TRACKER_ESCRITURA), ("administrativo", TRACKER_ADMINISTRATIVO)):
        cfg = await db.config.find_one({"_key": f"tracker_plantilla_{tipo}"})
        if not cfg:
            await db.config.insert_one({"_key": f"tracker_plantilla_{tipo}", "pasos": pasos,
                                        "modificado": _now(), "por": "sistema"})
        elif tipo == "escritura" and cfg.get("por") == "sistema" and \
                not any("plazo_habiles" in p for p in cfg.get("pasos", [])):
            await db.config.update_one({"_key": f"tracker_plantilla_{tipo}"},
                                       {"$set": {"pasos": pasos, "modificado": _now()}})
    logging.info("👑 Gerencia Comercial: brokers internos y plantillas de tracker sembrados")


# ═══ PANEL PRINCIPAL ═══
@gcom.get("/panel")
async def gcom_panel(request: Request):
    _exigir(request, ("gerencia", "admin", "maestro", "contralor"))
    ahora = datetime.now(timezone.utc)
    mes = ahora.strftime("%Y-%m")
    internos = await db.brokers_internos.find({}, {"_id": 0}).to_list(20)
    cod_internos = {b["codigo"] for b in internos}
    ext_users = await db.users.find({"rol": {"$in": ["broker", "ejecutivo"]},
                                     "codigo": {"$nin": list(cod_internos)}},
                                    {"_id": 0, "codigo": 1, "nombre": 1}).to_list(50)
    folders = await db.folders.find({}, {"_id": 0, "id": 1, "nombre": 1, "broker_codigo": 1,
                                         "broker_nombre": 1, "is_escrituracion": 1,
                                         "credit_request": 1, "updated_at": 1, "created_at": 1}).to_list(2000)
    proys = await db.broker_proyecciones.find({}, {"_id": 0, "broker_codigo": 1, "mes": 1}).to_list(1000)

    def _etapa(f):
        if f.get("is_escrituracion"):
            return "escrituracion"
        if f.get("credit_request"):
            return "evaluacion"
        return "ingreso"

    def _dias_sin_mov(f):
        ts = f.get("updated_at") or f.get("created_at") or ""
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (ahora - dt).days
        except Exception:
            return 0

    def _monto(f):
        cr = f.get("credit_request") or {}
        for k in ("monto_credito_uf", "monto_uf", "monto_credito", "monto"):
            try:
                v = float(str(cr.get(k) or 0).replace(".", "").replace(",", "."))
                if v:
                    return v
            except Exception:
                continue
        return 0.0

    def _stats(codigo, nombre):
        ops = [f for f in folders if f.get("broker_codigo") == codigo
               or (f.get("broker_nombre") or "").strip().lower() == nombre.strip().lower()]
        etapas = {"ingreso": 0, "evaluacion": 0, "escrituracion": 0}
        riesgo = atrasadas = 0
        for f in ops:
            etapas[_etapa(f)] += 1
            d = _dias_sin_mov(f)
            if not f.get("is_escrituracion"):
                if 7 <= d < 14:
                    riesgo += 1
                elif d >= 14:
                    atrasadas += 1
        cerradas = etapas["escrituracion"]
        activas = len(ops) - cerradas
        p_mes = [p for p in proys if p.get("broker_codigo") == codigo and p.get("mes") == mes]
        p_total = [p for p in proys if p.get("broker_codigo") == codigo]
        nuevas_mes = sum(1 for f in ops if str(f.get("created_at") or "").startswith(mes))
        meta = len(p_mes)
        ratio = round(nuevas_mes / meta * 100) if meta else None
        return {"codigo": codigo, "nombre": nombre, "operaciones": len(ops), "activas": activas,
                "cerradas": cerradas, "en_riesgo": riesgo, "atrasadas": atrasadas,
                "etapas": etapas, "monto_uf": round(sum(_monto(f) for f in ops), 1),
                "proyecciones_mes": meta, "proyecciones_total": len(p_total),
                "operaciones_nuevas_mes": nuevas_mes, "ratio_cumplimiento": ratio}

    panel_int = [_stats(b["codigo"], b["nombre"]) for b in internos]
    panel_ext = [_stats(u["codigo"], u.get("nombre") or u["codigo"]) for u in ext_users]
    todos = panel_int + panel_ext
    ranking = sorted(todos, key=lambda x: (x["operaciones"], x["monto_uf"]), reverse=True)

    # Panel ejecutivo (visión gerencial fusionada)
    ejecutivos = []
    total_ops = len(folders) or 1
    escrituradas = sum(1 for f in folders if f.get("is_escrituracion"))
    docs_pend = await db.docs_sin_clasificar.count_documents({})
    pv_activos = await db.postventa_casos.count_documents({"etapa_actual": {"$exists": True}})
    pv_completos = await db.postventa_aprendizaje.count_documents({})
    for u in await db.users.find({"rol": {"$in": ["administracion", "postventa"]}, "activo": {"$ne": False}},
                                 {"_id": 0, "codigo": 1, "nombre": 1, "rol": 1}).to_list(20):
        if u["rol"] == "postventa":
            act, cerr = pv_activos, pv_completos
        else:
            act, cerr = docs_pend, escrituradas
        ratio_av = round(cerr / (act + cerr) * 100) if (act + cerr) else 0
        ejecutivos.append({"nombre": u.get("nombre") or u["codigo"], "rol": u["rol"],
                           "ops_activas": act, "completadas": cerr, "ratio_avance": ratio_av,
                           "aporte_pct": round(cerr / total_ops * 100)})

    return {"mes": mes, "actualizado": _now(),
            "kpis": {"operaciones_totales": len(folders),
                     "activas": len(folders) - escrituradas,
                     "cerradas_exitosas": escrituradas,
                     "en_riesgo": sum(x["en_riesgo"] for x in todos),
                     "atrasadas": sum(x["atrasadas"] for x in todos),
                     "monto_total_uf": round(sum(x["monto_uf"] for x in todos), 1)},
            "brokers_internos": panel_int, "brokers_externos": panel_ext,
            "ranking": ranking[:10], "ejecutivos": ejecutivos}


@gcom.get("/dashboard-principal")
async def dashboard_principal(request: Request):
    """BLOQUE 1 — Frente principal en vivo: SOLO Admin y Gerencia Comercial."""
    _exigir(request, ("admin", "maestro", "gerencia"))
    ahora = datetime.now(timezone.utc)
    mes = ahora.strftime("%Y-%m")
    folders = await db.folders.find({}, {"_id": 0, "id": 1, "nombre": 1, "is_escrituracion": 1,
                                         "credit_request": 1, "updated_at": 1, "created_at": 1,
                                         "faltantes_auto_lista": 1, "broker_codigo": 1}).to_list(2000)
    def _dias(f):
        try:
            dt = datetime.fromisoformat(str(f.get("updated_at") or f.get("created_at") or "").replace("Z", "+00:00"))
            return (ahora - (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))).days
        except Exception:
            return 0
    escrituradas = [f for f in folders if f.get("is_escrituracion")]
    activas = [f for f in folders if not f.get("is_escrituracion")]
    sin_mov5 = [f for f in activas if _dias(f) > 5]
    faltantes = [f for f in folders if f.get("faltantes_auto_lista")]
    proys_mes = await db.broker_proyecciones.count_documents({"mes": mes})
    cerradas_mes = sum(1 for f in escrituradas if str(f.get("updated_at") or "").startswith(mes))
    # Espejo / Concreces
    esp = await db.config.find_one({"_key": "espejo_contralor"}) or {}
    hace24 = (ahora - timedelta(hours=24)).isoformat()
    ia_urgentes_24h = await db.alertas.count_documents({"tipo": "espejo_urgente", "creado": {"$gte": hace24}})
    esp_pendientes = await db.espejo_no_clasificados.count_documents({})
    # Postventa: paso actual del tracker por caso
    pv = []
    plantilla = await _plantilla("escritura")
    async for c in db.postventa_casos.find({}, {"_id": 0, "id": 1, "cliente": 1}).limit(30):
        st = await db.trackers.find_one({"tipo": "escritura", "ref": c["id"]}) or {"pasos": {}}
        hechos = {k for k, v in (st.get("pasos") or {}).items() if v.get("completado")}
        actual = next((p["label"] for p in plantilla if p["id"] not in hechos), "✅ Completado")
        pv.append({"id": c["id"], "cliente": c.get("cliente"), "paso_actual": actual,
                   "vencidos": len(st.get("alertas_enviadas") or [])})
    docs_pend = await db.docs_sin_clasificar.count_documents({})
    return {"actualizado": _now(), "mes": mes,
            "operaciones": {"activas": len(activas), "cerradas_mes": cerradas_mes,
                            "meta_mes": proys_mes, "atrasadas": sum(1 for f in activas if _dias(f) >= 14),
                            "sin_movimiento_5d": len(sin_mov5), "con_docs_faltantes": len(faltantes)},
            "financiero": {"cartera_activa": len(activas), "cerradas_mes": cerradas_mes,
                           "ratio_mes": round(cerradas_mes / proys_mes * 100) if proys_mes else None},
            "espejo": {"ultima_sync": esp.get("ultima_sync") or "", "pendientes": esp_pendientes,
                       "alertas_ia_24h": ia_urgentes_24h},
            "postventa": {"casos": pv, "vencidos_total": sum(x["vencidos"] for x in pv)},
            "documentos": {"carpetas_incompletas": len(faltantes), "sin_clasificar": docs_pend}}


@gcom.get("/indices-admin")
async def indices_admin(request: Request):
    """BLOQUE 4 — Algoritmo Híbrido: índices exclusivos del Admin."""
    _exigir(request, ("admin", "maestro"))
    auds = await db.auditorias_eficiencia.find({}, {"_id": 0, "semana": 1, "fecha": 1,
                                                    "resultado": 1, "fallas": 1}).sort("fecha", -1).to_list(5)
    hace30 = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    brechas = await db.alertas.count_documents({"leida": False, "creado": {"$gte": hace30}})
    normativas = await db.dashai_eventos.count_documents({"inviolable": True})
    exp = await db.config.find_one({"_key": "export_pendiente"}) or {}
    tr_admin = await db.trackers.count_documents({"tipo": "administrativo"})
    usuarios = await db.users.find({}, {"_id": 0, "codigo": 1, "nombre": 1, "rol": 1,
                                        "first_login": 1, "activo": 1, "imap_email": 1,
                                        "imap_configurado": 1, "created": 1}).to_list(100)
    pend_activacion = [{"nombre": u.get("nombre"), "rol": u.get("rol"),
                        "pendiente": "primer ingreso" if u.get("first_login") else "IMAP"}
                       for u in usuarios if u.get("first_login")
                       or (u.get("activo", True) and not (u.get("imap_email") or u.get("imap_configurado"))
                           and u.get("rol") not in ("contralor",))]
    return {"administrativo": {"auditorias_recientes": auds, "brechas_abiertas": brechas,
                               "normativas_vigentes": normativas,
                               "exportacion_pendiente": bool(exp.get("pendiente")),
                               "trackers_administrativos": tr_admin},
            "formaciones": {"usuarios_total": len(usuarios),
                            "pendientes_activacion": pend_activacion,
                            "activos": sum(1 for u in usuarios if u.get("activo", True) and not u.get("first_login"))}}


# ═══ TRACKERS DE PASOS (escritura / administrativo) ═══
_LECTURA = ("gerencia", "admin", "maestro", "contralor", "postventa", "administracion")
_ESCRIBE = {"escritura": ("admin", "maestro", "gerencia", "postventa"),
            "administrativo": ("admin", "maestro", "administracion")}


async def _plantilla(tipo):
    if tipo not in ("escritura", "administrativo"):
        raise HTTPException(status_code=400, detail="Tipo de tracker inválido (escritura|administrativo)")
    cfg = await db.config.find_one({"_key": f"tracker_plantilla_{tipo}"}) or {}
    return cfg.get("pasos") or []


@gcom.get("/trackers/plantillas")
async def trackers_plantillas(request: Request):
    _exigir(request, _LECTURA)
    return {"escritura": await _plantilla("escritura"),
            "administrativo": await _plantilla("administrativo")}


@gcom.post("/trackers/plantillas/{tipo}")
async def trackers_plantilla_editar(tipo: str, payload: dict, request: Request):
    c = _exigir(request, ("admin", "maestro"))
    pasos = (payload or {}).get("pasos") or []
    if not pasos or not all(p.get("id") and p.get("label") for p in pasos):
        raise HTTPException(status_code=400, detail="Cada paso requiere id y label")
    await _plantilla(tipo)
    await db.config.update_one({"_key": f"tracker_plantilla_{tipo}"}, {"$set": {
        "pasos": pasos, "modificado": _now(), "por": c.get("nombre") or c.get("sub")}}, upsert=True)
    return {"ok": True, "tipo": tipo, "total_pasos": len(pasos)}


def _dias_habiles_desde(inicio, ahora):
    d, n = inicio.date(), 0
    while d < ahora.date():
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


@gcom.get("/tracker/{tipo}/{ref}")
async def tracker_get(tipo: str, ref: str, request: Request):
    _exigir(request, _LECTURA)
    plantilla = await _plantilla(tipo)
    st = await db.trackers.find_one({"tipo": tipo, "ref": ref}, {"_id": 0}) or {"pasos": {}}
    ahora = datetime.now(timezone.utc)
    pasos, previo_fecha, en_curso_visto = [], None, False
    alertadas = set(st.get("alertas_enviadas") or [])
    for p in plantilla:
        e = (st.get("pasos") or {}).get(p["id"]) or {}
        completado = bool(e.get("completado"))
        estado, dias_rest, dias_venc = "pendiente", None, None
        if completado:
            estado, previo_fecha = "completado", e.get("fecha") or previo_fecha
        elif not en_curso_visto:
            estado, en_curso_visto = "en_curso", True
            plazo = p.get("plazo_habiles")
            if plazo and previo_fecha:
                try:
                    ini = datetime.fromisoformat(str(previo_fecha).replace("Z", "+00:00"))
                    trans = _dias_habiles_desde(ini, ahora)
                    if trans > plazo:
                        estado, dias_venc = "vencido", trans - plazo
                    else:
                        dias_rest = plazo - trans
                except Exception:
                    pass
        pasos.append({**p, "completado": completado, "estado": estado,
                      "fecha_inicio": previo_fecha if estado in ("en_curso", "vencido") else "",
                      "dias_restantes": dias_rest, "dias_vencidos": dias_venc,
                      "fecha": e.get("fecha") or "", "responsable": e.get("responsable") or ""})
        if estado == "vencido" and p["id"] not in alertadas:
            await db.alertas.insert_one({
                "id": str(uuid.uuid4()), "tipo": "tracker_vencido", "leida": False, "creado": _now(),
                "destinatarios": ["admin", "gerencia"],
                "titulo": f"🚨 Paso vencido: {p['label']}",
                "mensaje": f"Tracker {tipo} ({ref}): '{p['label']}' lleva {dias_venc} día(s) hábil(es) "
                           f"sobre el plazo de {p.get('plazo_habiles')} días."})
            await db.trackers.update_one({"tipo": tipo, "ref": ref},
                                         {"$addToSet": {"alertas_enviadas": p["id"]},
                                          "$setOnInsert": {"id": str(uuid.uuid4()), "creado": _now()}}, upsert=True)
    completados = sum(1 for p in pasos if p["completado"])
    return {"tipo": tipo, "ref": ref, "pasos": pasos, "completados": completados,
            "total": len(pasos), "avance_pct": round(completados / len(pasos) * 100) if pasos else 0,
            "vencidos": sum(1 for p in pasos if p["estado"] == "vencido")}


@gcom.post("/tracker/{tipo}/{ref}/toggle")
async def tracker_toggle(tipo: str, ref: str, payload: dict, request: Request):
    c = _exigir(request, _ESCRIBE.get(tipo) or ("admin",))
    paso_id = ((payload or {}).get("paso_id") or "").strip()
    plantilla = await _plantilla(tipo)
    if paso_id not in {p["id"] for p in plantilla}:
        raise HTTPException(status_code=404, detail="Paso no existe en la plantilla vigente")
    completado = bool((payload or {}).get("completado", True))
    entrada = {"completado": completado,
               "fecha": _now() if completado else "",
               "responsable": (c.get("nombre") or c.get("sub") or "") if completado else ""}
    await db.trackers.update_one({"tipo": tipo, "ref": ref}, {
        "$set": {f"pasos.{paso_id}": entrada, "actualizado": _now()},
        "$setOnInsert": {"id": str(uuid.uuid4()), "creado": _now()}}, upsert=True)
    return {"ok": True, "paso": paso_id, **entrada}
