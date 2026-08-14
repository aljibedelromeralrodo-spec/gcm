"""PANEL DE GESTIÓN POR EJECUTIVO (Regla de Hierro: medidor de actividad, no espía de
contenido). Contabiliza y clasifica gestiones desde cabeceras de correo — JAMÁS el cuerpo."""
import re
import uuid
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request

from database import db
import email_service as mail

gestion = APIRouter(prefix="/gestion-ejecutivos")

CL_TZ = timezone(timedelta(hours=-4))
# CERO CONFIGURACIÓN: DashAI escucha SOLO las casillas del administrador (Regla #36)
# y atribuye la gestión por nombre/dirección del ejecutivo detectado en las cabeceras.
EJECUTIVOS = {
    "daniela": {"nombre": "Daniela Galindo", "protegida": True,
                "alias": ["daniela galindo", "dgalindo", "daniela.galindo"]},
    "victoria": {"nombre": "Victoria Vilche", "protegida": True,
                 "alias": ["victoria vilche", "vvilche", "victoria.vilche"]},
    "postventa": {"nombre": "Postventa — Javier Urrutia", "protegida": False,
                  "alias": ["javier urrutia", "jurrutia", "javier.urrutia", "postventa"]},
}
TIPOS = [
    ("coordinacion_notaria", "Coordinación con notaría", re.compile(r"notar[ií]a|escritur", re.I)),
    ("coordinacion_tasadores", "Coordinación con tasadores", re.compile(r"tasaci[óo]n|tasador", re.I)),
    ("coordinacion_titulos", "Coordinación con estudio de títulos", re.compile(r"estudio de t[ií]tulo|t[ií]tulos|reparo", re.I)),
    ("envio_documentos", "Envío de documentos", re.compile(r"adjunt|documento|set de cr|carta oferta|simulaci|expediente|antecedente", re.I)),
    ("seguimiento", "Seguimiento a clientes", re.compile(r"seguimiento|estado de|avance|recordatorio", re.I)),
    ("respuesta_consultas", "Respuesta a consultas", re.compile(r"^\s*(re|rv|fwd?)\s*:|consulta|duda", re.I)),
]
RESUELTO_RE = re.compile(r"resuelto|solucionad|cerrad[oa]|finalizad", re.I)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _clasificar(asunto):
    for clave, label, rx in TIPOS:
        if rx.search(asunto or ""):
            return clave, label
    return "otras", "Otras gestiones"


def _exigir_gerencia(request):
    from malla_inteligencia import _exigir_gerencia as _eg
    return _eg(request)


async def _fuentes_cfg():
    cfg = await db.config.find_one({"_key": "gestion_fuentes"}) or {}
    return {e: cfg.get(e) or [] for e in EJECUTIVOS}


@gestion.get("/fuentes")
async def gestion_fuentes_get():
    f = await _fuentes_cfg()
    return {"fuentes": f,
            "ejecutivos": {k: v["nombre"] for k, v in EJECUTIVOS.items()},
            "nota": "Configuración persistida en la bóveda; agregar/quitar es inmediato y queda en bitácora"}


@gestion.post("/fuentes")
async def gestion_fuentes_post(payload: dict, request: Request):
    user = _exigir_gerencia(request)
    ej = (payload.get("ejecutivo") or "").strip().lower()
    accion = (payload.get("accion") or "").strip().lower()
    correo = (payload.get("correo") or "").strip().lower()
    if ej not in EJECUTIVOS or accion not in ("agregar", "quitar") or "@" not in correo:
        raise HTTPException(status_code=400, detail="Ejecutivo, acción o correo inválido")
    fuentes = await _fuentes_cfg()
    lista = fuentes[ej]
    if accion == "agregar" and correo not in lista:
        lista.append(correo)
    if accion == "quitar":
        lista = [c for c in lista if c != correo]
    await db.config.update_one({"_key": "gestion_fuentes"}, {"$set": {ej: lista}}, upsert=True)
    await db.gestion_fuentes_log.insert_one({
        "id": str(uuid.uuid4()), "ejecutivo": ej, "accion": accion, "correo": correo,
        "por": user.get("sub") or "gerencia", "fecha": _now(), "inmutable": True})
    return {"ok": True, "ejecutivo": ej, "fuentes": lista,
            "efecto": "monitoreo inmediato" if accion == "agregar" else "monitoreo detenido de inmediato"}


def _dia_local(dt_utc):
    return dt_utc.astimezone(CL_TZ)


async def _cosechar_gestiones():
    """Barrido de cabeceras (5 min) desde las casillas del ADMINISTRADOR (Regla #36).
    Atribuye por dirección configurada O por nombre del ejecutivo — cero configuración.
    Si detecta una dirección nueva del ejecutivo, la aprende sola (captura automática)."""
    fuentes = await _fuentes_cfg()
    activos = {e: set(l) for e, l in fuentes.items()}
    nombres = [f.get("nombre") or "" async for f in db.folders.find(
        {"oculto_supercarpeta": {"$exists": False}}, {"nombre": 1})]
    nuevos = 0
    for rol in ("principal", "secundaria"):
        headers = await asyncio.to_thread(mail.fetch_recent_headers, rol, 2, 150)
        for h in headers or []:
            texto_dir = f"{h.get('from', '')} {h.get('to', '')} {h.get('cc', '')}".lower()
            asunto = h.get("subject") or ""
            for ej, correos in activos.items():
                por_correo = any(c in texto_dir for c in correos)
                por_nombre = any(a in texto_dir for a in EJECUTIVOS[ej]["alias"])
                if not (por_correo or por_nombre):
                    continue
                if por_nombre and not por_correo:
                    m_dir = re.search(r"[\w.+-]+@[\w.-]+", h.get("from") or "")
                    if m_dir and any(a in (h.get("from") or "").lower() for a in EJECUTIVOS[ej]["alias"]):
                        addr = m_dir.group(0).lower()
                        if addr not in correos:
                            correos.add(addr)
                            await db.config.update_one({"_key": "gestion_fuentes"},
                                                       {"$addToSet": {ej: addr}}, upsert=True)
                            await db.gestion_fuentes_log.insert_one({
                                "id": str(uuid.uuid4()), "ejecutivo": ej, "accion": "agregar",
                                "correo": addr, "por": "sistema (captura automática por nombre)",
                                "fecha": _now(), "inmutable": True})
                msg_key = f"{ej}:{h['id']}"
                if await db.gestion_eventos.find_one({"msg_key": msg_key}):
                    continue
                try:
                    from email.utils import parsedate_to_datetime
                    dt = parsedate_to_datetime(h.get("date") or "")
                    if not dt.tzinfo:
                        dt = dt.replace(tzinfo=timezone.utc)
                except Exception:
                    dt = datetime.now(timezone.utc)
                loc = _dia_local(dt)
                tipo, label = _clasificar(asunto)
                enviado = any(c in (h.get("from") or "").lower() for c in correos)
                cliente = ""
                asunto_l = asunto.lower()
                for n in nombres:
                    toks = [t for t in n.lower().split() if len(t) > 2]
                    if len(toks) >= 2 and sum(1 for t in toks if t in asunto_l) >= 2:
                        cliente = n
                        break
                await db.gestion_eventos.insert_one({
                    "id": str(uuid.uuid4()), "msg_key": msg_key, "ejecutivo": ej,
                    "fecha": dt.astimezone(timezone.utc).isoformat(),
                    "dia": loc.strftime("%Y-%m-%d"), "hora": loc.hour,
                    "tipo": tipo, "tipo_label": label, "cliente": cliente,
                    "direccion": "enviado" if enviado else "recibido",
                    "resuelto": bool(RESUELTO_RE.search(asunto))})
                if cliente:
                    fd = await db.folders.find_one({"nombre": cliente}, {"rut": 1})
                    if fd and fd.get("rut"):
                        import adn_clientes as _adn
                        await db.adn_clientes_360.update_one(
                            {"rut_norm": _adn._norm_rut(fd["rut"])},
                            {"$push": {"gestiones_ejecutivos": {
                                "fecha": _now(), "ejecutivo": ej, "tipo": label}}})
                nuevos += 1
    await db.config.update_one({"_key": "gestion_harvest"}, {"$set": {
        "ultima": _now(), "nuevos": nuevos}}, upsert=True)
    return nuevos


async def gestion_harvest_loop():
    """ACTUALIZACIÓN EN TIEMPO REAL: cada 5 minutos, solo cabeceras (privacidad absoluta)."""
    await asyncio.sleep(240)
    while True:
        try:
            await _cosechar_gestiones()
        except Exception as e:
            logging.warning(f"gestion harvest: {e}")
        await asyncio.sleep(300)


@gestion.post("/cosechar")
async def gestion_cosechar(request: Request):
    _exigir_gerencia(request)
    asyncio.create_task(_cosechar_gestiones())
    return {"ok": True, "lanzado": True, "seguimiento": "GET /api/gestion-ejecutivos (ultima_actualizacion)"}


@gestion.get("")
async def gestion_panel():
    ahora_cl = datetime.now(CL_TZ)
    hoy = ahora_cl.strftime("%Y-%m-%d")
    lunes = (ahora_cl - timedelta(days=ahora_cl.weekday())).strftime("%Y-%m-%d")
    mes_ini = ahora_cl.strftime("%Y-%m-01")
    fuentes = await _fuentes_cfg()
    harvest = await db.config.find_one({"_key": "gestion_harvest"}) or {}
    dias_semana = [(ahora_cl - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
    modulos, total_hoy, comparativa = {}, 0, {d: {} for d in dias_semana}
    for ej, meta in EJECUTIVOS.items():
        evs = [e async for e in db.gestion_eventos.find({"ejecutivo": ej, "dia": {"$gte": mes_ini}})]
        ev_hoy = [e for e in evs if e["dia"] == hoy]
        ev_sem = [e for e in evs if e["dia"] >= lunes]
        por_hora = [0] * 24
        tipos = {}
        for e in ev_hoy:
            por_hora[e.get("hora", 0)] += 1
            tipos[e.get("tipo_label") or "Otras gestiones"] = tipos.get(e.get("tipo_label"), 0) + 1
        dias_con = {e["dia"] for e in evs}
        promedio = round(len(evs) / max(len(dias_con), 1), 1)
        cumplimiento = round(len(ev_hoy) * 100 / promedio) if promedio else (100 if ev_hoy else 0)
        sin_fuentes = False
        protegida = meta["protegida"]
        alerta_incompleto = sin_fuentes or (protegida and promedio > 0 and len(ev_hoy) < promedio * 0.8)
        ult = max((e["fecha"] for e in evs), default="")
        for d in dias_semana:
            comparativa[d][ej] = sum(1 for e in evs if e["dia"] == d)
        mod = {
            "nombre": meta["nombre"], "protegida": protegida,
            "hoy": len(ev_hoy), "semana": len(ev_sem), "mes": len(evs),
            "por_hora": por_hora,
            "tipos": [{"tipo": k, "total": v} for k, v in sorted(tipos.items(), key=lambda x: -x[1])],
            "clientes_hoy": sorted({e["cliente"] for e in ev_hoy if e.get("cliente")}),
            "promedio_diario": promedio, "cumplimiento_pct": cumplimiento,
            "fuentes": fuentes.get(ej) or [],
            "alerta_incompleto": alerta_incompleto,
            "mensaje_incompleto": ("⚠️ El reporte puede estar incompleto: el sistema podría no tener "
                                   "acceso a todos los correos fuente. La gestión real es mayor a la contabilizada.")
                                  if alerta_incompleto else "",
            "ultima_gestion": ult,
        }
        if ej == "postventa":
            ev30 = [e async for e in db.gestion_eventos.find({"ejecutivo": ej})]
            act = {e["cliente"] for e in ev30 if e.get("cliente") and not e.get("resuelto")}
            res_clientes = {e["cliente"] for e in ev30 if e.get("cliente") and e.get("resuelto")}
            tiempos = []
            for c in res_clientes:
                dias_c = sorted(e["dia"] for e in ev30 if e.get("cliente") == c)
                if len(dias_c) >= 2:
                    d0 = datetime.strptime(dias_c[0], "%Y-%m-%d")
                    d1 = datetime.strptime(dias_c[-1], "%Y-%m-%d")
                    tiempos.append((d1 - d0).days)
            mod["postventa"] = {
                "casos_activos": len(act - res_clientes),
                "resueltos_hoy": len({e["cliente"] for e in ev_hoy if e.get("resuelto")}),
                "tiempo_promedio_dias": round(sum(tiempos) / len(tiempos), 1) if tiempos else 0}
        modulos[ej] = mod
        total_hoy += len(ev_hoy)
    mas_activo = max(modulos, key=lambda e: modulos[e]["hoy"]) if total_hoy else ""
    alertas_baja = []
    if 9 <= ahora_cl.hour < 18:
        for ej, m in modulos.items():
            ult = m.get("ultima_gestion")
            if not ult:
                continue
            try:
                delta = datetime.now(timezone.utc) - datetime.fromisoformat(ult)
                if delta > timedelta(hours=2):
                    alertas_baja.append(f"{m['nombre']}: {int(delta.total_seconds() // 3600)}h sin gestiones registradas")
            except Exception:
                pass
    return {"modulos": modulos,
            "consolidado": {"total_hoy": total_hoy,
                            "mas_activo": modulos.get(mas_activo, {}).get("nombre", "") if mas_activo else "",
                            "comparativa_semanal": [{"dia": d, **comparativa[d]} for d in dias_semana],
                            "alertas_baja_actividad": alertas_baja},
            "ultima_actualizacion": harvest.get("ultima", ""),
            "privacidad": "Este módulo jamás muestra el contenido de un correo: solo cuenta, clasifica y presenta métricas"}
