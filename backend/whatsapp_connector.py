"""📱 Conector Twilio WhatsApp — se activa solo cuando las claves estén en .env.
Sin claves: estado 'sin_credenciales' y el vigía duerme (no spamea reintentos)."""
import os
import asyncio
import logging
from datetime import datetime, timezone

_cli = None


def _creds():
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
    tok = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    num = os.environ.get("TWILIO_PHONE_NUMBER", "").strip()
    return (sid, tok, num) if sid and tok and num else None


def _client():
    global _cli
    c = _creds()
    if not c:
        return None
    if _cli is None:
        from twilio.rest import Client
        _cli = Client(c[0], c[1])
    return _cli


def estado_sync():
    """Estado real del número: consulta la cuenta Twilio (llamada bloqueante, usar en to_thread)."""
    c = _creds()
    if not c:
        return {"estado": "sin_credenciales",
                "detalle": "Faltan TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_PHONE_NUMBER en .env — pégalas en el chat para activar"}
    try:
        cli = _client()
        acc = cli.api.accounts(c[0]).fetch()
        return {"estado": "conectado" if acc.status == "active" else acc.status,
                "cuenta": acc.friendly_name, "numero": c[2],
                "detalle": f"Cuenta Twilio {acc.status}, número {c[2]} listo para WhatsApp"}
    except Exception as e:
        return {"estado": "error", "detalle": str(e)[:200]}


def enviar_whatsapp_sync(to, body):
    """Envía WhatsApp con 3 reintentos y backoff. Loguea en Mongo. Bloqueante: usar en to_thread."""
    import time as _t
    from bunker import _db
    c = _creds()
    log = {"to": to, "body": body[:500], "fecha": datetime.now(timezone.utc).isoformat()}
    if not c:
        log.update({"ok": False, "error": "sin_credenciales"})
        _db().whatsapp_log.insert_one(log)
        return {"ok": False, "error": "sin_credenciales"}
    dest = to if to.startswith("whatsapp:") else f"whatsapp:{to}"
    origen = c[2] if c[2].startswith("whatsapp:") else f"whatsapp:{c[2]}"
    err = ""
    for intento in range(3):
        try:
            m = _client().messages.create(from_=origen, to=dest, body=body)
            log.update({"ok": True, "sid": m.sid, "intentos": intento + 1})
            _db().whatsapp_log.insert_one(log)
            return {"ok": True, "sid": m.sid}
        except Exception as e:
            err = str(e)[:200]
            _t.sleep(5 * (intento + 1))
    log.update({"ok": False, "error": err, "intentos": 3})
    _db().whatsapp_log.insert_one(log)
    return {"ok": False, "error": err}


async def vigia_conexion(db):
    """Vigía cada 5 min: guarda el estado en Mongo; backoff 15 min tras 3 fallas seguidas."""
    fallas = 0
    while True:
        try:
            if not _creds():
                await asyncio.sleep(600)  # sin claves: duerme 10 min, no hay nada que vigilar
                continue
            st = await asyncio.to_thread(estado_sync)
            await db.whatsapp_status_log.update_one({"_id": "actual"}, {"$set": {
                **st, "checked_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
            fallas = fallas + 1 if st["estado"] == "error" else 0
        except Exception as e:
            logging.warning(f"vigía whatsapp: {e}")
            fallas += 1
        await asyncio.sleep(900 if fallas >= 3 else 300)
