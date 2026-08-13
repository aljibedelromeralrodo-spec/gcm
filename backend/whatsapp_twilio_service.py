"""MOTOR WHATSAPP OFICIAL — Twilio (Número Exclusivo de automatización).

Regla de Oro #21: motor WhatsApp oficial Twilio; prohibidos los métodos manuales,
links wa.me o sesiones de navegador/QR. Envío automático uno a uno vía API REST.
Secretos: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER (backend/.env).
"""
import os
import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from database import db

wa_twilio = APIRouter(prefix="/whatsapp-twilio")

MENSAJE_BIENVENIDA = ("🚀 Este es el canal oficial de notificaciones de Central Mutuos. "
                      "Su solicitud está en proceso.")
ADMIN_WHATSAPP = os.environ.get("WHATSAPP_ADMIN_NUMBER", "+56928995453")


def _credenciales():
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
    token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    numero = os.environ.get("TWILIO_PHONE_NUMBER", "").strip()
    return sid, token, numero


def configurado():
    return all(_credenciales())


def _enviar_sync(to, cuerpo):
    """Envío directo vía API Twilio (bloqueante — usar con asyncio.to_thread)."""
    sid, token, numero = _credenciales()
    if not all([sid, token, numero]):
        return {"ok": False, "error": "Twilio no configurado: complete TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_PHONE_NUMBER en backend/.env"}
    from twilio.rest import Client
    cliente = Client(sid, token)
    to_e164 = to if to.startswith("+") else f"+{to}"
    msg = cliente.messages.create(
        from_=f"whatsapp:{numero}",
        to=f"whatsapp:{to_e164}",
        body=cuerpo)
    return {"ok": True, "sid": msg.sid, "estado": msg.status, "to": to_e164}


async def enviar_whatsapp(to, cuerpo, tipo="alerta"):
    """Motor de envío automático: un mensaje por llamada, con registro en db.whatsapp_log."""
    try:
        r = await asyncio.to_thread(_enviar_sync, to, cuerpo)
    except Exception as e:
        r = {"ok": False, "error": str(e)[:250]}
    await db.whatsapp_log.insert_one({
        "to": to, "tipo": tipo, "cuerpo": cuerpo[:400], "resultado": r,
        "fecha": datetime.now(timezone.utc).isoformat()})
    if not r.get("ok"):
        logging.warning(f"whatsapp twilio fallo → {to}: {r.get('error')}")
    return r


async def alerta_admin(cuerpo, tipo="alerta"):
    """Alerta directa al número del dueño (Gerardo)."""
    return await enviar_whatsapp(ADMIN_WHATSAPP, cuerpo, tipo)


@wa_twilio.get("/status")
async def wa_status():
    sid, token, numero = _credenciales()
    enviados = await db.whatsapp_log.count_documents({"resultado.ok": True})
    return {"motor": "Twilio (Número Exclusivo — Regla de Oro #21)",
            "configurado": configurado(),
            "faltan": [k for k, v in (("TWILIO_ACCOUNT_SID", sid), ("TWILIO_AUTH_TOKEN", token),
                                      ("TWILIO_PHONE_NUMBER", numero)) if not v],
            "numero_exclusivo": numero or "(pendiente de compra)",
            "admin": ADMIN_WHATSAPP, "mensajes_enviados": enviados,
            "sin_qr_ni_navegador": True}


@wa_twilio.post("/test-bienvenida")
async def wa_test_bienvenida(payload: dict = None):
    """ALERTA DE BIENVENIDA: envía el mensaje oficial de prueba al admin (o al número indicado)."""
    if not configurado():
        raise HTTPException(status_code=503,
                            detail="Twilio no configurado aún — complete los 3 secretos en backend/.env y reinicie")
    to = ((payload or {}).get("to") or ADMIN_WHATSAPP).strip()
    r = await enviar_whatsapp(to, MENSAJE_BIENVENIDA, tipo="bienvenida")
    if not r.get("ok"):
        raise HTTPException(status_code=502, detail=r.get("error"))
    return {"ok": True, "mensaje": MENSAJE_BIENVENIDA, **r}
