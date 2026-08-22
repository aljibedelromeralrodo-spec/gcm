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

# ASIGNACIONES PERMANENTES DE MÓDULO (tareas distintas por ejecutivo, editables por Admin/Gerencia)
EJECUTIVOS_MODULO = [
    {"codigo": "victoria", "nombre": "Victoria Vílchez", "modulo": "administrativo",
     "tareas": ["Validación documental y control de carpetas", "Gestión de documentos faltantes"]},
    {"codigo": "daniela", "nombre": "Daniela Galindo", "modulo": "administrativo",
     "tareas": ["Tramitación administrativa y envío a mesa", "Coordinación de instrucciones de escrituración"]},
    {"codigo": "postventa", "nombre": "Javier Urrutia", "modulo": "postventa",
     "tareas": ["Seguimiento paso a paso de escritura y postventa"]},
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
    # Perfil Gerencia Comercial (Daniela/Victoria/Javier): acceso al módulo aunque su rol sea administracion
    if c.get("perfil") == "gerencia_comercial" and "gerencia" in roles:
        return c
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
    for e in EJECUTIVOS_MODULO:
        await db.ejecutivos_modulo.update_one({"codigo": e["codigo"]}, {"$setOnInsert": {
            "id": str(uuid.uuid4()), **e, "permanente": True, "creado": _now()}}, upsert=True)
    logging.info("👑 Gerencia Comercial: brokers internos, plantillas de tracker y ejecutivos por módulo sembrados")


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


@gcom.get("/vision-operaciones")
async def vision_operaciones(request: Request):
    """VISIÓN COMERCIAL — operaciones con categorías filtrables (subsidio, SERVIU,
    vivienda nueva/usada) + subdivisión inmobiliaria/proyecto y comparativos."""
    _exigir(request, ("gerencia", "admin", "maestro", "contralor"))
    ahora = datetime.now(timezone.utc)
    mes = ahora.strftime("%Y-%m")
    mes_anterior = (ahora.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    folders = await db.folders.find({}, {"_id": 0, "id": 1, "nombre": 1, "broker_codigo": 1,
                                         "broker_nombre": 1, "is_escrituracion": 1, "credit_request": 1,
                                         "datos_financieros": 1, "created_at": 1, "updated_at": 1}).to_list(2000)
    proy_mes = {}
    for p in await db.broker_proyecciones.find({"mes": mes}, {"_id": 0, "broker_codigo": 1}).to_list(1000):
        proy_mes[p["broker_codigo"]] = proy_mes.get(p["broker_codigo"], 0) + 1

    def _monto_op(df, cr):
        for src, k in ((df, "monto_credito"), (cr, "monto_credito_uf"), (cr, "monto_uf"),
                       (cr, "monto_credito"), (cr, "monto")):
            v = src.get(k)
            if v in (None, "", 0):
                continue
            try:
                if isinstance(v, str):
                    v = float(v.replace(".", "").replace(",", "."))
                v = float(v)
                if v > 0:
                    return round(v, 1)
            except Exception:
                continue
        return 0.0

    ops = []
    for f in folders:
        df = f.get("datos_financieros") or {}
        cr = f.get("credit_request") or {}
        con_sub = df.get("con_subsidio")
        if con_sub is None:
            con_sub = (cr.get("subsidy") or {}).get("tipo") == "con_subsidio"
        tv = str(df.get("tipo_vivienda") or "").strip().lower()
        if tv not in ("nueva", "usada"):
            tv = "nueva"  # DEFAULT INSTITUCIONAL: vivienda nueva
        try:
            dt = datetime.fromisoformat(str(f.get("updated_at") or f.get("created_at") or "").replace("Z", "+00:00"))
            dias = (ahora - (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))).days
        except Exception:
            dias = 0
        activa = not f.get("is_escrituracion")
        ops.append({"fid": f.get("id"), "cliente": f.get("nombre"),
                    "broker_codigo": f.get("broker_codigo") or "", "broker_nombre": f.get("broker_nombre") or "",
                    "inmobiliaria": (df.get("inmobiliaria") or "").strip() or "Sin inmobiliaria",
                    "proyecto": (df.get("proyecto") or "").strip() or "Sin proyecto",
                    "activa": activa, "monto_uf": _monto_op(df, cr),
                    "mes_creacion": str(f.get("created_at") or "")[:7],
                    "con_subsidio": bool(con_sub),
                    "resolucion_serviu": bool(df.get("resolucion_serviu")),  # DEFAULT: sin resolución
                    "tipo_vivienda": tv, "dias_sin_mov": dias,
                    "semaforo": ("verde" if not activa or dias < 7 else "amarillo" if dias < 14 else "rojo")})
    return {"mes": mes, "mes_anterior": mes_anterior, "actualizado": _now(),
            "proyecciones_mes": proy_mes, "operaciones": ops}


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


# ═══ GESTIÓN DE EJECUTIVOS POR MÓDULO — desempeño en tiempo real ═══
@gcom.put("/ejecutivos-modulo/{codigo}")
async def ejecutivos_modulo_editar(codigo: str, payload: dict, request: Request):
    c = _exigir(request, ("admin", "maestro", "gerencia"))
    doc = await db.ejecutivos_modulo.find_one({"codigo": codigo})
    if not doc:
        raise HTTPException(status_code=404, detail="Ejecutivo no encontrado")
    tareas = [str(t).strip()[:200] for t in (payload or {}).get("tareas") or [] if str(t).strip()]
    await db.ejecutivos_modulo.update_one({"codigo": codigo}, {"$set": {
        "tareas": tareas, "modificado": _now(), "por": c.get("nombre") or c.get("sub")}})
    return {"ok": True, "codigo": codigo, "tareas": tareas}


@gcom.get("/ejecutivos-desempeno")
async def ejecutivos_desempeno(request: Request):
    """Indicadores por ejecutivo: cumplimiento de plazos, pendientes, vencidas,
    historial mensual y alertas. Solo Admin y Gerencia Comercial."""
    _exigir(request, ("admin", "maestro", "gerencia"))
    ahora = datetime.now(timezone.utc)
    asigs = await db.ejecutivos_modulo.find({}, {"_id": 0}).to_list(10)
    plantillas = {"escritura": await _plantilla("escritura"), "administrativo": await _plantilla("administrativo")}
    tipo_por_modulo = {"administrativo": "administrativo", "postventa": "escritura"}
    trackers = {t: await db.trackers.find({"tipo": t}, {"_id": 0}).to_list(1000)
                for t in ("escritura", "administrativo")}

    def _eval(tipo, st):
        pasos_st = st.get("pasos") or {}
        previo, en_curso_visto = None, False
        res = {"pendientes": 0, "vencidas": 0, "completadas": []}
        for p in plantillas[tipo]:
            e = pasos_st.get(p["id"]) or {}
            plazo = p.get("plazo_habiles")
            if e.get("completado"):
                item = {"fecha": e.get("fecha") or "", "responsable": e.get("responsable") or "", "a_tiempo": None}
                if plazo and previo and item["fecha"]:
                    try:
                        ini = datetime.fromisoformat(str(previo).replace("Z", "+00:00"))
                        fin = datetime.fromisoformat(str(item["fecha"]).replace("Z", "+00:00"))
                        item["a_tiempo"] = _dias_habiles_desde(ini, fin) <= plazo
                    except Exception:
                        pass
                res["completadas"].append(item)
                previo = e.get("fecha") or previo
            else:
                res["pendientes"] += 1
                if not en_curso_visto:
                    en_curso_visto = True
                    if plazo and previo:
                        try:
                            ini = datetime.fromisoformat(str(previo).replace("Z", "+00:00"))
                            if _dias_habiles_desde(ini, ahora) > plazo:
                                res["vencidas"] += 1
                        except Exception:
                            pass
        return res

    activas_admin = await db.folders.count_documents({"is_escrituracion": {"$ne": True}})
    pv_activos = await db.postventa_casos.count_documents({})
    hoy = ahora.strftime("%Y-%m-%d")
    salida = []
    for a in asigs:
        tipo = tipo_por_modulo.get(a["modulo"], "administrativo")
        evs = [_eval(tipo, st) for st in trackers[tipo]]
        pend = sum(e["pendientes"] for e in evs)
        venc = sum(e["vencidas"] for e in evs)
        mismo_modulo = [x for x in asigs if x["modulo"] == a["modulo"]]
        nom = a["nombre"].lower().split()[0]
        if len(mismo_modulo) == 1:
            comp = [c for e in evs for c in e["completadas"]]
        else:
            comp = [c for e in evs for c in e["completadas"] if nom in (c["responsable"] or "").lower()]
        con_plazo = [c for c in comp if c["a_tiempo"] is not None]
        a_tiempo = sum(1 for c in con_plazo if c["a_tiempo"])
        ratio = round(a_tiempo / len(con_plazo) * 100) if con_plazo else None
        hist = {}
        for c in comp:
            m = (c["fecha"] or "")[:7]
            if not m:
                continue
            h = hist.setdefault(m, {"completadas": 0, "a_tiempo": 0, "atrasadas": 0})
            h["completadas"] += 1
            if c["a_tiempo"] is True:
                h["a_tiempo"] += 1
            elif c["a_tiempo"] is False:
                h["atrasadas"] += 1
        historial = [{"mes": m, **v} for m, v in sorted(hist.items(), reverse=True)[:6]]
        # ALERTA AUTOMÁTICA: tareas vencidas sin resolver (1 por día por ejecutivo)
        if venc > 0:
            existe = await db.alertas.find_one({"tipo": "ejecutivo_vencidas", "ejecutivo": a["codigo"],
                                                "creado": {"$gte": hoy}})
            if not existe:
                await db.alertas.insert_one({
                    "id": str(uuid.uuid4()), "tipo": "ejecutivo_vencidas", "ejecutivo": a["codigo"],
                    "leida": False, "creado": _now(), "destinatarios": ["admin", "gerencia"],
                    "titulo": f"🚨 {a['nombre']}: {venc} tarea(s) vencida(s) sin resolver",
                    "mensaje": f"El módulo {a['modulo']} registra {venc} tarea(s) fuera de plazo sin completar."})
        alertas_abiertas = await db.alertas.count_documents({
            "leida": False,
            "$or": [{"tipo": "ejecutivo_vencidas", "ejecutivo": a["codigo"]},
                    {"tipo": "tracker_vencido", "mensaje": {"$regex": f"Tracker {tipo}"}}]})
        salida.append({"codigo": a["codigo"], "nombre": a["nombre"], "modulo": a["modulo"],
                       "tareas": a.get("tareas") or [],
                       "ops_activas": pv_activos if a["modulo"] == "postventa" else activas_admin,
                       "tareas_pendientes": pend, "tareas_vencidas": venc,
                       "completadas_total": len(comp), "a_tiempo": a_tiempo,
                       "atrasadas": len(con_plazo) - a_tiempo,
                       "con_plazo_evaluadas": len(con_plazo), "ratio_cumplimiento": ratio,
                       "historial_mensual": historial, "alertas_sin_resolver": alertas_abiertas,
                       "plazos_definidos": any(p.get("plazo_habiles") for p in plantillas[tipo])})
    return {"actualizado": _now(), "ejecutivos": salida,
            "consolidado": {"tareas_pendientes": sum(x["tareas_pendientes"] for x in salida),
                            "tareas_vencidas": sum(x["tareas_vencidas"] for x in salida),
                            "alertas_sin_resolver": sum(x["alertas_sin_resolver"] for x in salida),
                            "completadas_total": sum(x["completadas_total"] for x in salida)}}


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



# ═══ CENTRO DE MANDO UNIFICADO — fusión Gestión de Ejecutivos + KPIs + Alertas ═══
def _monto_folder(fd):
    df = fd.get("datos_financieros") or {}
    try:
        v = float(df.get("monto_credito") or 0)
        if v:
            return v
    except (TypeError, ValueError):
        pass
    cr = fd.get("credit_request") or {}
    for k in ("monto_credito_uf", "monto_uf", "monto_credito", "monto"):
        try:
            x = float(str(cr.get(k) or 0).replace(",", "."))
            if x:
                return x
        except (TypeError, ValueError):
            continue
    return 0.0


def _dias_folder(fd, ahora):
    ts = fd.get("updated_at") or fd.get("created_at") or ""
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (ahora - dt).days
    except (TypeError, ValueError):
        return 0


@gcom.get("/centro-mando")
async def centro_mando(request: Request):
    """Panel único de Rodrigo: KPIs, ranking, tabla de ejecutivos con IMAP y alertas inteligentes.
    Mora = cliente con morosidad vigente en DICOM (datos_financieros.morosidad_dicom)."""
    _exigir(request, ("gerencia", "admin", "maestro", "contralor"))
    ahora = datetime.now(timezone.utc)
    mes = ahora.strftime("%Y-%m")
    folders = await db.folders.find({}, {
        "_id": 0, "id": 1, "nombre": 1, "rut": 1, "is_escrituracion": 1, "fecha_firma": 1,
        "datos_financieros": 1, "credit_request": 1, "created_at": 1, "updated_at": 1}).to_list(3000)
    total_uf = round(sum(_monto_folder(f) for f in folders), 1)
    escrituradas = sum(1 for f in folders if f.get("is_escrituracion"))
    activas = len(folders) - escrituradas
    nuevas_mes = sum(1 for f in folders if str(f.get("created_at") or "").startswith(mes))
    mora = [f for f in folders if (f.get("datos_financieros") or {}).get("morosidad_dicom")]
    mora_uf = round(sum(_monto_folder(f) for f in mora), 1)

    try:
        desem = await ejecutivos_desempeno(request)
    except HTTPException:
        desem = {"ejecutivos": [], "consolidado": {"tareas_vencidas": 0, "tareas_pendientes": 0}}
    des_por_cod = {e["codigo"]: e for e in desem["ejecutivos"]}

    from espejo_hibrido import FUENTES, _estado_fuente
    imap_por_cod = {}
    for fu in FUENTES:
        st = await _estado_fuente(fu)
        imap_por_cod[fu["usuario_codigo"]] = {
            "estado": st["estado"], "email": st["email"],
            "ultimo_barrido": (st.get("ultimo_barrido") or {}).get("fecha", ""),
            "correos_totales": st.get("correos_totales", 0)}

    no_esc = [f for f in folders if not f.get("is_escrituracion")]
    esc = [f for f in folders if f.get("is_escrituracion")]
    pv_act = await db.postventa_casos.count_documents({})
    pv_res = await db.postventa_aprendizaje.count_documents({})
    ejecutivos = []
    for a in await db.ejecutivos_modulo.find({}, {"_id": 0}).to_list(10):
        scope = esc if a["modulo"] == "postventa" else no_esc
        d = des_por_cod.get(a["codigo"], {})
        if a["modulo"] == "postventa":
            tasa = round(pv_res / (pv_act + pv_res) * 100) if (pv_act + pv_res) else 0
        else:
            tasa = round(escrituradas / len(folders) * 100) if folders else 0
        mora_gen = sum(1 for f in scope if (f.get("datos_financieros") or {}).get("morosidad_dicom"))
        ejecutivos.append({
            "codigo": a["codigo"], "nombre": a["nombre"], "modulo": a["modulo"],
            "cartera_ops": len(scope), "cartera_uf": round(sum(_monto_folder(f) for f in scope), 1),
            "ops_activas": d.get("ops_activas", len(scope)), "tasa_cierre": tasa,
            "mora_generada": mora_gen,
            "tareas_pendientes": d.get("tareas_pendientes", 0),
            "tareas_vencidas": d.get("tareas_vencidas", 0),
            "ratio_cumplimiento": d.get("ratio_cumplimiento"),
            "completadas_total": d.get("completadas_total", 0),
            "imap": imap_por_cod.get(a["codigo"], {"estado": "en_espera", "email": ""})})
    ranking = sorted(ejecutivos, key=lambda e: (
        -(e["ratio_cumplimiento"] or 0), e["tareas_vencidas"], -e["tasa_cierre"], -e["completadas_total"]))

    sin_act = sorted([{"cliente": f.get("nombre"), "rut": f.get("rut") or "", "dias": _dias_folder(f, ahora)}
                      for f in no_esc if _dias_folder(f, ahora) >= 7], key=lambda x: -x["dias"])[:12]
    prox = []
    for f in folders:
        ff = str(f.get("fecha_firma") or "")[:10]
        if not ff:
            continue
        try:
            delta = (datetime.fromisoformat(ff).replace(tzinfo=timezone.utc) - ahora).days
            if 0 <= delta <= 7 and not f.get("is_escrituracion"):
                prox.append({"cliente": f.get("nombre"), "fecha_firma": ff, "dias_restantes": delta})
        except ValueError:
            continue

    return {"mes": mes, "actualizado": _now(),
            "kpis": {"cartera_total_uf": total_uf, "cartera_total_ops": len(folders),
                     "operaciones_activas": activas, "escrituradas": escrituradas,
                     "nuevas_mes": nuevas_mes,
                     "mora_vigente": {"n": len(mora), "uf": mora_uf,
                                      "clientes": [{"cliente": f.get("nombre"), "rut": f.get("rut") or ""}
                                                   for f in mora[:10]]}},
            "ranking": ranking, "ejecutivos": ejecutivos,
            "alertas": {
                "ejecutivos_mora_alta": [{"nombre": e["nombre"], "mora": e["mora_generada"]}
                                         for e in ejecutivos if e["mora_generada"] >= 1],
                "operaciones_vencidas": {"tareas_vencidas": desem["consolidado"].get("tareas_vencidas", 0),
                                         "firmas_proximas": sorted(prox, key=lambda x: x["dias_restantes"])[:10]},
                "clientes_sin_actividad": sin_act}}


@gcom.get("/ejecutivo/{codigo}/ficha")
async def ejecutivo_ficha(codigo: str, request: Request):
    """Ficha completa del ejecutivo: historial de operaciones, métricas y comunicaciones."""
    _exigir(request, ("gerencia", "admin", "maestro", "contralor"))
    a = await db.ejecutivos_modulo.find_one({"codigo": codigo}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Ejecutivo no encontrado")
    try:
        desem = await ejecutivos_desempeno(request)
        d = next((e for e in desem["ejecutivos"] if e["codigo"] == codigo), {})
    except HTTPException:
        d = {}
    ahora = datetime.now(timezone.utc)
    q = {"is_escrituracion": True} if a["modulo"] == "postventa" else {"is_escrituracion": {"$ne": True}}
    ops = []
    async for f in db.folders.find(q, {"_id": 0, "nombre": 1, "rut": 1, "datos_financieros": 1,
                                       "credit_request": 1, "updated_at": 1, "created_at": 1,
                                       "is_escrituracion": 1}).sort("updated_at", -1).limit(30):
        ops.append({"cliente": f.get("nombre"), "rut": f.get("rut") or "",
                    "monto_uf": _monto_folder(f),
                    "dicom": bool((f.get("datos_financieros") or {}).get("morosidad_dicom")),
                    "etapa": "Escrituración" if f.get("is_escrituracion") else "Administrativa",
                    "dias_sin_movimiento": _dias_folder(f, ahora),
                    "actualizado": str(f.get("updated_at") or "")[:10]})
    from espejo_hibrido import FUENTES
    fu = next((x for x in FUENTES if x["usuario_codigo"] == codigo), None)
    email_e = fu["email"] if fu else ""
    enviadas = []
    if email_e:
        async for c in db.correos_smtp_log.find(
                {"$or": [{"to": {"$regex": email_e, "$options": "i"}},
                         {"cc": {"$regex": email_e, "$options": "i"}}]},
                {"_id": 0, "fecha": 1, "subject": 1, "success": 1, "desde": 1}).sort("fecha", -1).limit(15):
            enviadas.append(c)
    espejo = []
    if fu:
        async for c in db.espejo_hibrido_correos.find(
                {"fuente": fu["fid"]},
                {"_id": 0, "fecha": 1, "asunto": 1, "resumen": 1, "tipo_comunicacion": 1}).sort("fecha", -1).limit(10):
            espejo.append(c)
    return {"ejecutivo": {**a, "email": email_e}, "metricas": d, "historial_operaciones": ops,
            "comunicaciones": {"enviadas": enviadas, "espejo": espejo}}


@gcom.get("/export-pdf")
async def gerencia_export_pdf(request: Request, pin: str = ""):
    """Reporte PDF ejecutivo (KPIs + ranking + ejecutivos). Protegido por PIN maestro."""
    import os
    import io
    _exigir(request, ("gerencia", "admin", "maestro"))
    if not pin or pin != os.environ.get("MASTER_PIN", ""):
        raise HTTPException(status_code=403, detail="PIN maestro incorrecto — la exportación PDF está protegida")
    cm = await centro_mando(request)
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    ORO = colors.HexColor("#C9A227")
    NEGRO = colors.HexColor("#0a0a0a")
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=36, bottomMargin=36)
    ss = getSampleStyleSheet()
    titulo = ParagraphStyle("t", parent=ss["Title"], textColor=ORO, fontSize=18, spaceAfter=2)
    sub = ParagraphStyle("s", parent=ss["Normal"], textColor=colors.HexColor("#555555"), fontSize=9)
    h2 = ParagraphStyle("h", parent=ss["Heading2"], textColor=NEGRO, fontSize=12, spaceBefore=14)
    k = cm["kpis"]
    est_tabla = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NEGRO), ("TEXTCOLOR", (0, 0), (-1, 0), ORO),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f2e8")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)])
    kpi_tbl = Table([
        ["Cartera Total (UF)", "Operaciones Activas", "Mora Vigente (DICOM)", "Nuevas del Mes", "Escrituradas"],
        [f'{k["cartera_total_uf"]:,.0f} UF · {k["cartera_total_ops"]} ops', str(k["operaciones_activas"]),
         f'{k["mora_vigente"]["n"]} cliente(s) · {k["mora_vigente"]["uf"]:,.0f} UF',
         str(k["nuevas_mes"]), str(k["escrituradas"])]], colWidths=[110, 100, 130, 90, 90])
    kpi_tbl.setStyle(est_tabla)
    rk_filas = [["#", "Ejecutivo", "Módulo", "Cartera", "Ops Activas", "Tasa Cierre", "Mora", "Cumplimiento"]]
    for i, e in enumerate(cm["ranking"], 1):
        rk_filas.append([str(i), e["nombre"], e["modulo"], f'{e["cartera_uf"]:,.0f} UF ({e["cartera_ops"]})',
                         str(e["ops_activas"]), f'{e["tasa_cierre"]}%', str(e["mora_generada"]),
                         f'{e["ratio_cumplimiento"]}%' if e["ratio_cumplimiento"] is not None else "s/d"])
    rk_tbl = Table(rk_filas, colWidths=[18, 110, 75, 95, 60, 60, 40, 75])
    rk_tbl.setStyle(est_tabla)
    al = cm["alertas"]
    alertas_txt = (f'Ejecutivos con mora alta: {len(al["ejecutivos_mora_alta"])} · '
                   f'Tareas vencidas: {al["operaciones_vencidas"]["tareas_vencidas"]} · '
                   f'Firmas próximas (7 días): {len(al["operaciones_vencidas"]["firmas_proximas"])} · '
                   f'Clientes sin actividad reciente: {len(al["clientes_sin_actividad"])}')
    hoy = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    doc.build([
        Paragraph("CENTRAL MUTUOS — GERENCIA COMERCIAL", titulo),
        Paragraph(f"Centro de Mando · Reporte Ejecutivo · Mes {cm['mes']} · Generado el {hoy}", sub),
        Paragraph("Indicadores Principales", h2), kpi_tbl,
        Paragraph("Ranking de Ejecutivos", h2), rk_tbl,
        Paragraph("Alertas Inteligentes", h2), Paragraph(alertas_txt, ss["Normal"]),
        Spacer(1, 18),
        Paragraph("Documento confidencial de uso exclusivo de Gerencia Comercial. "
                  "Exportación protegida por PIN maestro y registrada en bitácora.", sub)])
    await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "export_pdf", "leida": True,
                                 "mensaje": f"📄 Exportación PDF Gerencia por {_claims(request).get('sub')}",
                                 "fecha": _now()})
    from fastapi.responses import Response
    return Response(content=buf.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="Reporte_Gerencia_{cm["mes"]}.pdf"'})