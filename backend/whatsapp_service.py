"""Motor WhatsApp Cloud API (Meta) — número certificado Central Mutuos."""
import os
import logging
import requests

GRAPH_VERSION = "v25.0"
NUMERO_CERTIFICADO = "+56928995453"
NOMBRE_VISIBLE = "Central Mutuos - Gestión Hipotecaria"


def _cfg():
    return {
        "token": (os.environ.get("META_ACCESS_TOKEN") or "").strip(),
        "phone_id": (os.environ.get("META_PHONE_NUMBER_ID") or "").strip(),
        "waba_id": (os.environ.get("META_WABA_ID") or "").strip(),
        "version": (os.environ.get("META_GRAPH_VERSION") or GRAPH_VERSION).strip(),
    }


def configurado():
    c = _cfg()
    return bool(c["token"] and c["phone_id"])


def enviar_texto(to: str, body: str, preview_url: bool = True):
    """Envía texto libre (ventana 24h). Devuelve dict con success/message_id/error."""
    c = _cfg()
    if not configurado():
        return {"success": False, "error": "Credenciales Meta no configuradas (META_ACCESS_TOKEN / META_PHONE_NUMBER_ID)",
                "codigo": "sin_credenciales"}
    to_e164 = "+" + "".join(ch for ch in to if ch.isdigit()) if not to.startswith("+") else to
    url = f"https://graph.facebook.com/{c['version']}/{c['phone_id']}/messages"
    payload = {"messaging_product": "whatsapp", "recipient_type": "individual",
               "to": to_e164, "type": "text",
               "text": {"preview_url": preview_url, "body": body[:4096]}}
    try:
        r = requests.post(url, json=payload, timeout=30,
                          headers={"Authorization": f"Bearer {c['token']}",
                                   "Content-Type": "application/json"})
        data = r.json() if r.content else {}
        if r.ok:
            mid = (data.get("messages") or [{}])[0].get("id")
            logging.info(f"📱 WhatsApp aceptado por Meta: {mid} → {to_e164[-4:]}")
            return {"success": True, "message_id": mid, "to": to_e164}
        err = (data.get("error") or {})
        code = err.get("code")
        detalle = {190: "Token expirado o inválido — genera un System User token nuevo",
                   133010: "El número no está registrado en la plataforma Cloud API",
                   131047: "Ventana de 24h cerrada — se requiere plantilla aprobada",
                   132001: "Plantilla inexistente o no aprobada",
                   131045: "Número emisor con error de registro (revisar estado CONNECTED)"}.get(
            code, err.get("message", "Error Meta desconocido"))
        return {"success": False, "error": f"Meta código {code}: {detalle}", "codigo": code}
    except requests.RequestException as e:
        return {"success": False, "error": f"Conexión con Meta falló: {e}", "codigo": "red"}


def enviar_plantilla(to: str, nombre: str, idioma: str = "es", parametros: list = None):
    """Envía plantilla aprobada (fuera de ventana 24h)."""
    c = _cfg()
    if not configurado():
        return {"success": False, "error": "Credenciales Meta no configuradas", "codigo": "sin_credenciales"}
    to_e164 = "+" + "".join(ch for ch in to if ch.isdigit()) if not to.startswith("+") else to
    url = f"https://graph.facebook.com/{c['version']}/{c['phone_id']}/messages"
    tpl = {"name": nombre, "language": {"code": idioma}}
    if parametros:
        tpl["components"] = [{"type": "body",
                              "parameters": [{"type": "text", "text": str(p)} for p in parametros]}]
    payload = {"messaging_product": "whatsapp", "to": to_e164, "type": "template", "template": tpl}
    try:
        r = requests.post(url, json=payload, timeout=30,
                          headers={"Authorization": f"Bearer {c['token']}",
                                   "Content-Type": "application/json"})
        data = r.json() if r.content else {}
        if r.ok:
            return {"success": True, "message_id": (data.get("messages") or [{}])[0].get("id"), "to": to_e164}
        err = (data.get("error") or {})
        return {"success": False, "error": f"Meta código {err.get('code')}: {err.get('message')}", "codigo": err.get("code")}
    except requests.RequestException as e:
        return {"success": False, "error": f"Conexión con Meta falló: {e}", "codigo": "red"}
