"""⚖️ REGLA CONSTITUCIONAL — FUENTE DE VERDAD DE MESA (aprobaciones@centralmutuos.cl)
Monitoreo permanente y autónomo del canal oficial de mesa. Clasificación 100% LOCAL
(regex, sin consumo de IA): aprobación, rechazo, cambio de tasa, plazo o criterio.
- Aprobación/Rechazo → actualiza la carpeta y activa los botones de envío al ejecutivo.
- Cambio de tasa/plazo/criterio → registro + alerta dashboard + correo al administrador
  + todas las carpetas activas quedan marcadas 'Simulación desactualizada'.
- Todo correo procesado queda en db.mesa_verdad_log (fecha, hora, tipo, parámetros antes/después).
"""
import os
import re
import uuid
import asyncio
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from database import db

mesav = APIRouter(prefix="/mesa-verdad")

MESA_EMAIL = os.environ.get("MESA_EMAIL", "aprobaciones@centralmutuos.cl")
ROLES = ("admin", "maestro", "administracion", "gerencia", "contralor")
INTERVALO_SEG = 120

RX_CAMBIO = re.compile(r"cambio|nueva?s?\b|actualiza|ajust|modific|sube|baja|pasa a|queda en|rige|vigente", re.I)
RX_TASA = re.compile(r"\btasas?\b", re.I)
RX_PLAZO = re.compile(r"\bplazos?\b", re.I)
RX_CRITERIO = re.compile(r"criterios?|renta\s+m[ií]nima|carga\s+financiera|\bltv\b|financiamiento\s+m[aá]x|"
                         r"dividendo\s+m[aá]x|pol[ií]tica\s+de\s+evaluaci[oó]n|score", re.I)
RX_APROB = re.compile(r"\baprobad[oa]s?\b|pre-?aprobad|\bviable\b|curse|cursad", re.I)
RX_RECH = re.compile(r"\brechazad[oa]s?\b|no\s+califica|reprobad[oa]|no\s+aprobad|desistid", re.I)
RX_PCT = re.compile(r"\d{1,2}[.,]?\d{0,2}\s*%")
RX_ANIOS = re.compile(r"\d{1,2}\s*a[ñn]os", re.I)
RX_UF = re.compile(r"\d[\d.,]*\s*uf", re.I)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _hora_cl():
    return datetime.now(ZoneInfo("America/Santiago")).strftime("%d/%m/%Y %H:%M")


def _clasificar(texto):
    """Clasificación LOCAL (sin IA). Prioridad: cambios estructurales > resultado de caso."""
    if RX_TASA.search(texto) and RX_CAMBIO.search(texto) and RX_PCT.search(texto):
        return "cambio_tasa"
    if RX_PLAZO.search(texto) and RX_CAMBIO.search(texto) and RX_ANIOS.search(texto):
        return "cambio_plazo"
    if RX_CRITERIO.search(texto) and RX_CAMBIO.search(texto):
        return "cambio_criterio"
    if RX_RECH.search(texto):
        return "rechazo"
    if RX_APROB.search(texto):
        return "aprobacion"
    return "otro"


def _parametros(texto):
    return {"tasas": RX_PCT.findall(texto)[:4], "plazos": RX_ANIOS.findall(texto)[:4],
            "montos_uf": RX_UF.findall(texto)[:4]}


def _norm_toks(s):
    import unicodedata
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return [t for t in re.split(r"[^a-z]+", s) if len(t) >= 3]


async def _buscar_carpeta(texto):
    """Match de carpeta por RUT o por 2+ tokens del nombre presentes en el correo."""
    ruts = set(re.sub(r"[^0-9kK]", "", r).lower()[:8]
               for r in re.findall(r"\d{1,2}\.?\d{3}\.?\d{3}-?[\dkK]", texto))
    toks_txt = set(_norm_toks(texto))
    async for f in db.folders.find({}, {"_id": 0, "id": 1, "nombre": 1, "rut": 1}):
        fr = re.sub(r"[^0-9kK]", "", f.get("rut") or "").lower()[:8]
        if fr and fr in ruts:
            return f
        ft = _norm_toks(f.get("nombre"))
        if len(ft) >= 2 and sum(1 for t in ft if t in toks_txt) >= 2:
            return f
    return None


async def _param_anteriores(tipo):
    prev = await db.mesa_verdad_log.find_one({"tipo": tipo}, {"_id": 0, "parametros_nuevos": 1},
                                             sort=[("procesado_en", -1)])
    return (prev or {}).get("parametros_nuevos") or {}


async def _procesar_correo(msg):
    mid = msg.get("id") or ""
    if not mid or await db.mesa_verdad_log.find_one({"correo_id": mid}):
        return None
    subject = msg.get("subject") or ""
    body = (msg.get("body") or msg.get("body_full") or msg.get("preview") or "")[:6000]
    texto = f"{subject}\n{body}"
    tipo = _clasificar(texto)
    # REGLA ANTI-FALSO-POSITIVO: si el correo corresponde a un CASO de cliente
    # (carpeta coincidente), NUNCA es un cambio estructural global.
    f_caso = await _buscar_carpeta(texto)
    if tipo.startswith("cambio_") and f_caso:
        tipo = "aprobacion" if RX_APROB.search(texto) else ("rechazo" if RX_RECH.search(texto) else "otro")
    registro = {"id": str(uuid.uuid4()), "correo_id": mid, "tipo": tipo,
                "subject": subject[:200], "sender": msg.get("from") or MESA_EMAIL,
                "fecha_correo": str(msg.get("date") or "")[:25],
                "procesado_en": _now(), "hora_cl": _hora_cl(),
                "parametros_nuevos": _parametros(texto), "parametros_anteriores": {},
                "folder_id": "", "accion": ""}
    if tipo in ("aprobacion", "rechazo"):
        f = f_caso
        if f:
            resultado = "aprobado" if tipo == "aprobacion" else "reprobado"
            await db.folders.update_one({"id": f["id"]}, {"$set": {
                "resultado_mesa": resultado, "resultado_mesa_at": _now(),
                "resultado_mesa_fuente": MESA_EMAIL, "resultado_mesa_asunto": subject[:200]}})
            registro["folder_id"] = f["id"]
            registro["accion"] = f"Carpeta {f.get('nombre')} → {resultado.upper()} (botones de envío al ejecutivo activados)"
            await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "mesa_verdad", "leida": False,
                                         "cliente": f.get("nombre"),
                                         "mensaje": f"⚖️ MESA ({MESA_EMAIL}): {f.get('nombre')} → {resultado.upper()} — botón de envío al ejecutivo ACTIVADO",
                                         "fecha": _now()})
        else:
            registro["accion"] = "Sin carpeta coincidente — requiere revisión manual"
    elif tipo in ("cambio_tasa", "cambio_plazo", "cambio_criterio"):
        registro["parametros_anteriores"] = await _param_anteriores(tipo)
        etiqueta = {"cambio_tasa": "CAMBIO DE TASA", "cambio_plazo": "CAMBIO DE PLAZO",
                    "cambio_criterio": "CAMBIO DE CRITERIO DE EVALUACIÓN"}[tipo]
        r = await db.folders.update_many(
            {"descartada": {"$ne": True}},
            {"$set": {"simulacion_desactualizada": True,
                      "simulacion_desactualizada_motivo": f"{etiqueta} informado por mesa — {subject[:120]}",
                      "simulacion_desactualizada_at": _now()}})
        registro["accion"] = f"{etiqueta}: {r.modified_count} carpeta(s) activas marcadas 'Simulación desactualizada'"
        await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "mesa_verdad_cambio", "nivel": "critica",
                                     "leida": False,
                                     "mensaje": (f"🚨 {etiqueta} desde {MESA_EMAIL} — '{subject[:110]}' · "
                                                 f"nuevos: {registro['parametros_nuevos']} · "
                                                 f"{r.modified_count} carpeta(s) → Simulación desactualizada"),
                                     "fecha": _now()})
        # Correo de notificación al administrador — sujeto a NORMATIVA CORREOS:
        # durante el día solo se registra; el cambio viaja en el Resumen Diario 8AM.
        try:
            from resumen_diario import notificaciones_permitidas, registrar_omitido
            from server import _email_institucional
            import email_service as mail
            admin_to = os.environ.get("MAIL2_USER") or os.environ.get("MAIL_NOTIF_TEST") or ""
            if admin_to and not await notificaciones_permitidas():
                await registrar_omitido("mesa_verdad", f"{etiqueta} — {subject[:140]}")
            elif admin_to:
                nuevos = registro["parametros_nuevos"]
                antes = registro["parametros_anteriores"]
                cuerpo = (
                    f"<p style='margin:0 0 12px'>La mesa ({MESA_EMAIL}) inform&oacute; un <b>{etiqueta}</b>.</p>"
                    f"<p style='margin:0 0 12px'>Asunto: <b>{subject[:150]}</b><br>"
                    f"Fecha y hora: <b>{registro['hora_cl']}</b> (hora de Chile)</p>"
                    f"<p style='margin:0 0 12px'>Par&aacute;metros anteriores: <b>{antes or '—'}</b><br>"
                    f"Par&aacute;metros nuevos: <b>{nuevos or '—'}</b></p>"
                    f"<p style='margin:0 0 12px'>Las carpetas activas quedaron marcadas como "
                    f"<b>'Simulaci&oacute;n desactualizada'</b> hasta regenerar sus simulaciones.</p>")
                html = _email_institucional("Administrador", cuerpo)
                await asyncio.to_thread(mail.send_mail, admin_to, f"🚨 {etiqueta} — Fuente de Verdad de Mesa", html)
        except Exception as e:
            logging.warning(f"mesa_verdad notificación admin: {e}")
    await db.mesa_verdad_log.insert_one(dict(registro))
    return registro


async def barrido_mesa(dias=2):
    import email_service as mail
    if not mail.configured():
        return {"ok": False, "error": "Correo no configurado"}
    msgs = await asyncio.to_thread(mail.fetch_since_by_senders, dias, [MESA_EMAIL], 60)
    procesados = []
    for m in msgs:
        try:
            r = await _procesar_correo(m)
            if r:
                procesados.append({"tipo": r["tipo"], "subject": r["subject"][:80], "accion": r["accion"]})
        except Exception as e:
            logging.warning(f"mesa_verdad procesar: {e}")
    await db.config.update_one({"_key": "mesa_verdad"},
                               {"$set": {"ultimo_barrido": _now(), "revisados": len(msgs),
                                         "nuevos_procesados": len(procesados)}}, upsert=True)
    return {"ok": True, "revisados": len(msgs), "nuevos": len(procesados), "detalle": procesados}


async def mesa_verdad_loop():
    """Monitoreo permanente y autónomo (REGLA CONSTITUCIONAL — inamovible)."""
    await asyncio.sleep(25)
    while True:
        try:
            await barrido_mesa(dias=2)
        except Exception as e:
            logging.warning(f"mesa_verdad loop: {e}")
        await asyncio.sleep(INTERVALO_SEG)


def _exigir(request):
    c = getattr(request.state, "user", {}) or {}
    if c.get("rol") not in ROLES:
        raise HTTPException(status_code=403, detail="Su rol no tiene acceso a esta función")
    return c


@mesav.get("/estado")
async def mesa_verdad_estado(request: Request):
    _exigir(request)
    cfg = await db.config.find_one({"_key": "mesa_verdad"}, {"_id": 0}) or {}
    total = await db.mesa_verdad_log.count_documents({})
    por_tipo = {}
    async for g in db.mesa_verdad_log.aggregate([{"$group": {"_id": "$tipo", "n": {"$sum": 1}}}]):
        por_tipo[g["_id"]] = g["n"]
    return {"canal_oficial": MESA_EMAIL, "monitoreo": "activo", "intervalo_seg": INTERVALO_SEG,
            "ultimo_barrido": cfg.get("ultimo_barrido"), "total_procesados": total, "por_tipo": por_tipo}


@mesav.get("/log")
async def mesa_verdad_log(request: Request, limit: int = 50):
    _exigir(request)
    docs = await db.mesa_verdad_log.find({}, {"_id": 0}).sort("procesado_en", -1).limit(min(limit, 200)).to_list(200)
    return {"registros": docs, "total": len(docs)}


@mesav.post("/procesar-ahora")
async def mesa_verdad_ahora(request: Request):
    """Dispara un barrido inmediato en segundo plano (el IMAP puede tardar minutos)."""
    _exigir(request)
    asyncio.create_task(barrido_mesa(dias=3))
    return {"ok": True, "estado": "barrido_iniciado",
            "mensaje": "Barrido de la casilla de mesa iniciado en segundo plano — revise /api/mesa-verdad/log en unos minutos"}
