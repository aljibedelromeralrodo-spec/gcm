"""Regla de Oro #62 — Monitor de Fallos de Envío SMTP y Checklist de Trabajo Diario.

Ningún hito se considera enviado hasta que el servidor confirme la salida exitosa.
"""
import re
import asyncio
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException
from database import db
import email_service as _mail

correos_r = APIRouter(prefix="/correos")
_now = lambda: datetime.now(timezone.utc).isoformat()
_PROJ_LISTA = {"_id": 0, "body_html": 0, "attachments": 0}


@correos_r.get("/fallidos")
async def correos_fallidos(horas: int = 24):
    q = {"estado": "fallido"}
    if horas > 0:
        q["fecha"] = {"$gte": (datetime.now(timezone.utc) - timedelta(hours=horas)).isoformat()}
    docs = await db.correos_fallidos.find(q, _PROJ_LISTA).sort("fecha", -1).to_list(100)
    return {"fallidos": docs, "total": len(docs),
            "regla": "#62 — Ningún hito se considera enviado sin confirmación SMTP exitosa"}


@correos_r.post("/fallidos/{cid}/reintentar")
async def correos_reintentar(cid: str):
    """BOTÓN DE RE-INTENTO ATÓMICO (♻️): dispara el mensaje original con un solo clic."""
    doc = await db.correos_fallidos.find_one({"id": cid})
    if not doc:
        raise HTTPException(status_code=404, detail="Correo fallido no encontrado")
    if doc.get("estado") != "fallido":
        raise HTTPException(status_code=409, detail="Este correo ya fue re-enviado con éxito")
    res = await asyncio.to_thread(
        _mail.send_mail, doc.get("to"), doc.get("subject") or "", doc.get("body_html") or "",
        attachments=doc.get("attachments") or None, desde=doc.get("desde_rol") or "secundaria",
        cc=doc.get("cc") or None, bcc=doc.get("bcc") or None, registro_fallo=False)
    if res.get("success"):
        await db.correos_fallidos.update_one({"id": cid}, {
            "$set": {"estado": "reenviado_ok", "reenviado_en": _now(), "smtp_code": res.get("smtp_code")},
            "$inc": {"reintentos": 1}})
        return {"ok": True, "estado": "reenviado_ok", "smtp_code": res.get("smtp_code"),
                "detalle": "El servidor SMTP confirmó la salida exitosa (Regla #62)"}
    await db.correos_fallidos.update_one({"id": cid}, {
        "$set": {"ultimo_error": res.get("error", ""), "ultimo_reintento": _now()},
        "$inc": {"reintentos": 1}})
    raise HTTPException(status_code=502, detail=f"El servidor volvió a rechazar el envío: {res.get('error', '')}")


@correos_r.get("/briefing")
async def correos_briefing():
    """PANTALLA DE BRIEFING MAÑANERO: envíos exitosos y fallidos del día anterior."""
    hoy = datetime.now(timezone.utc).date()
    ini, fin = (hoy - timedelta(days=1)).isoformat(), hoy.isoformat()
    exitosos = await db.correos_smtp_log.find(
        {"success": True, "fecha": {"$gte": ini, "$lt": fin}},
        {"_id": 0, "to": 1, "subject": 1, "fecha": 1, "smtp_code": 1, "desde": 1}
    ).sort("fecha", -1).to_list(200)
    fallidos_dia = await db.correos_fallidos.find(
        {"fecha": {"$gte": ini, "$lt": fin}}, _PROJ_LISTA).sort("fecha", -1).to_list(100)
    pendientes = await db.correos_fallidos.find(
        {"estado": "fallido"}, _PROJ_LISTA).sort("fecha", -1).to_list(100)
    return {"dia": ini, "exitosos": exitosos, "fallidos_dia": fallidos_dia,
            "fallidos_pendientes": pendientes,
            "regla": "#62 — Es obligación de cada ejecutivo limpiar su lista de envíos fallidos al inicio de su jornada"}


async def exigir_correo_ok(cliente: str):
    """REGLA DE HIERRO #62: un hito NO se marca 'Completado' si su correo asociado está Fallido."""
    cliente = (cliente or "").strip()
    if not cliente:
        return
    pend = await db.correos_fallidos.find_one(
        {"estado": "fallido", "subject": {"$regex": re.escape(cliente[:25]), "$options": "i"}})
    if pend:
        raise HTTPException(status_code=409, detail=(
            f"⛔ Regla de Oro #62: existe un correo FALLIDO asociado a {cliente} "
            f"(«{(pend.get('subject') or '')[:80]}»). Re-envíelo desde el Estado de Salida antes de completar el hito."))


# ── CORRECCIÓN URGENTE (regla permanente): todo correo fallido con más de 24 horas
#    se cierra automáticamente ('cerrado'): sin reintentos, alertas ni notificaciones.
#    Solo se monitorean envíos posteriores a su fecha de cierre. ──
async def cierre_automatico_fallidos():
    limite = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    r = await db.correos_fallidos.update_many(
        {"estado": "fallido", "fecha": {"$lt": limite}},
        {"$set": {"estado": "cerrado", "cerrado_en": _now(),
                  "cerrado_motivo": "Cierre automático: más de 24 horas sin entrega (regla permanente)"}})
    if r.modified_count:
        import logging
        logging.info(f"📪 Cierre automático de correos fallidos >24h: {r.modified_count} cerrado(s)")
    return r.modified_count


async def cierre_fallidos_loop():
    await asyncio.sleep(40)
    while True:
        try:
            await cierre_automatico_fallidos()
        except Exception:
            pass
        await asyncio.sleep(3600)
