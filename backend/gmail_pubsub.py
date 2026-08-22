"""📡 GMAIL API + PUB/SUB — Recepción de correos en TIEMPO REAL (Central Mutuos).
Reemplaza el polling IMAP de la cuenta principal por notificaciones push de Google:
Gmail → Pub/Sub (topic) → POST /api/gmail/push → history.list (exactamente una vez,
cerrojo atómico por gmail_msg_id — Regla de Oro #68) → mismo flujo actual de
clasificación, carpetas y asignación a ejecutivos (_run_proc_auto).
"""
import os
import re
import json
import uuid
import base64
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from database import db

gmailr = APIRouter(prefix="/gmail")

CLIENT_ID = os.environ.get("GMAIL_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GMAIL_CLIENT_SECRET", "")
TOPIC = os.environ.get("GMAIL_PUBSUB_TOPIC", "")
CUENTA = os.environ.get("GMAIL_WATCH_ACCOUNT", "ethangerardobarr@gmail.com")
APP_URL = (os.environ.get("APP_URL") or "").rstrip("/")
REDIRECT_URI = f"{APP_URL}/api/gmail/oauth/callback"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly",
          "openid", "https://www.googleapis.com/auth/userinfo.email"]
KEY_TOK, KEY_WATCH = "gmail_api_tokens", "gmail_watch"
CAPTURA_EXT = (".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp")

_now = lambda: datetime.now(timezone.utc).isoformat()


def _exigir_admin(request):
    c = getattr(request.state, "user", {}) or {}
    if c.get("rol") not in ("admin", "maestro", "administracion"):
        raise HTTPException(status_code=403, detail="Solo el administrador")
    return c


def _client_config():
    return {"web": {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"}}


# ══ OAUTH (consentimiento único → refresh token permanente) ═════════════════
@gmailr.get("/oauth/iniciar")
async def oauth_iniciar(request: Request):
    _exigir_admin(request)
    if not CLIENT_ID or not CLIENT_SECRET:
        raise HTTPException(status_code=400, detail="Faltan GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET en .env")
    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, redirect_uri=REDIRECT_URI)
    url, state = flow.authorization_url(access_type="offline", prompt="consent",
                                        login_hint=CUENTA, include_granted_scopes="true")
    await db.config.update_one({"_key": "gmail_oauth_state"},
                               {"$set": {"state": state, "creado": _now()}}, upsert=True)
    return {"url": url, "instruccion": f"Abra esta URL con la cuenta {CUENTA} y acepte el acceso de solo lectura."}


@gmailr.get("/oauth/callback")
async def oauth_callback(code: str = "", state: str = "", error: str = ""):
    if error or not code:
        return HTMLResponse(f"<h3>❌ Autorización cancelada: {error or 'sin código'}</h3>", status_code=400)
    import warnings
    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, redirect_uri=REDIRECT_URI)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            await asyncio.to_thread(flow.fetch_token, code=code)
    except Exception as e:
        return HTMLResponse(f"<h3>❌ Error al canjear el código: {str(e)[:200]}</h3>", status_code=400)
    creds = flow.credentials
    prev = await db.config.find_one({"_key": KEY_TOK}) or {}
    await db.config.update_one({"_key": KEY_TOK}, {"$set": {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token or prev.get("refresh_token"),
        "expira": creds.expiry.replace(tzinfo=timezone.utc).isoformat() if creds.expiry else "",
        "cuenta": CUENTA, "actualizado": _now()}}, upsert=True)
    try:
        w = await iniciar_watch()
        detalle = f"Watch activo hasta {w.get('expira_cl', '?')} · historyId inicial {w.get('historyId', '?')}"
    except Exception as e:
        detalle = f"⚠️ Watch pendiente: {str(e)[:180]}"
    return HTMLResponse(
        "<div style='font-family:Georgia,serif;background:#0b0b0d;color:#e8e2cf;min-height:100vh;"
        "display:flex;align-items:center;justify-content:center;text-align:center'><div>"
        "<h2 style='color:#d4af37'>✅ Gmail API conectada a Central Mutuos</h2>"
        f"<p>Cuenta: <b>{CUENTA}</b></p><p>{detalle}</p>"
        "<p style='color:#8a7a5a'>Ya puede cerrar esta pestaña.</p></div></div>")


# ══ CREDENCIALES (auto-refresh) ══════════════════════════════════════════════
async def _creds():
    tok = await db.config.find_one({"_key": KEY_TOK}) or {}
    if not tok.get("refresh_token"):
        return None
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request as GReq
    creds = Credentials(token=tok.get("access_token"), refresh_token=tok["refresh_token"],
                        token_uri="https://oauth2.googleapis.com/token",
                        client_id=CLIENT_ID, client_secret=CLIENT_SECRET, scopes=SCOPES)
    exp = tok.get("expira") or ""
    vencido = True
    try:
        d = datetime.fromisoformat(exp)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        vencido = datetime.now(timezone.utc) >= d - timedelta(minutes=3)
    except Exception:
        pass
    if vencido:
        await asyncio.to_thread(creds.refresh, GReq())
        await db.config.update_one({"_key": KEY_TOK}, {"$set": {
            "access_token": creds.token,
            "expira": creds.expiry.replace(tzinfo=timezone.utc).isoformat() if creds.expiry else "",
            "actualizado": _now()}})
    return creds


def _svc(creds):
    from googleapiclient.discovery import build
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


# ══ WATCH (renovación obligatoria < 7 días) ══════════════════════════════════
async def iniciar_watch():
    creds = await _creds()
    if not creds:
        raise HTTPException(status_code=412, detail="Gmail sin autorizar: ejecute primero /api/gmail/oauth/iniciar")
    if not TOPIC:
        raise HTTPException(status_code=400, detail="Falta GMAIL_PUBSUB_TOPIC en .env")
    r = await asyncio.to_thread(lambda: _svc(creds).users().watch(
        userId="me", body={"topicName": TOPIC, "labelIds": ["INBOX"],
                           "labelFilterBehavior": "INCLUDE"}).execute())
    exp_ms = int(r.get("expiration") or 0)
    exp_iso = datetime.fromtimestamp(exp_ms / 1000, tz=timezone.utc).isoformat() if exp_ms else ""
    prev = await db.config.find_one({"_key": KEY_WATCH}) or {}
    await db.config.update_one({"_key": KEY_WATCH}, {"$set": {
        "history_id": prev.get("history_id") or str(r.get("historyId") or ""),
        "watch_history_id": str(r.get("historyId") or ""),
        "expira": exp_iso, "renovado_en": _now(), "topic": TOPIC, "cuenta": CUENTA}}, upsert=True)
    logging.info(f"📡 Gmail watch renovado hasta {exp_iso} (historyId {r.get('historyId')})")
    return {"historyId": str(r.get("historyId") or ""), "expira_cl": exp_iso}


# ══ LECTURA DE MENSAJES (formato idéntico al flujo IMAP actual) ══════════════
def _walk_parts(payload):
    yield payload
    for p in payload.get("parts") or []:
        yield from _walk_parts(p)


def _b64url(data):
    return base64.urlsafe_b64decode((data or "") + "===")


def _msg_a_correo(svc, mid):
    m = svc.users().messages().get(userId="me", id=mid, format="full").execute()
    payload = m.get("payload") or {}
    headers = {h["name"].lower(): h.get("value", "") for h in payload.get("headers", [])}
    try:
        fecha = parsedate_to_datetime(headers.get("date", "")).isoformat()
    except Exception:
        fecha = datetime.fromtimestamp(int(m.get("internalDate", "0")) / 1000, tz=timezone.utc).isoformat()
    body, pdfs = "", []
    for part in _walk_parts(payload):
        mime = part.get("mimeType") or ""
        fname = part.get("filename") or ""
        pbody = part.get("body") or {}
        if fname and fname.lower().endswith(CAPTURA_EXT):
            raw = b""
            if pbody.get("data"):
                raw = _b64url(pbody["data"])
            elif pbody.get("attachmentId"):
                att = svc.users().messages().attachments().get(
                    userId="me", messageId=mid, id=pbody["attachmentId"]).execute()
                raw = _b64url(att.get("data"))
            if raw:
                pdfs.append({"filename": fname, "content_bytes": raw})
        elif mime == "text/plain" and not body and pbody.get("data"):
            body = _b64url(pbody["data"]).decode("utf-8", errors="ignore")
    return {"from": headers.get("from", ""), "subject": headers.get("subject", ""),
            "date": fecha, "body": body, "pdfs": pdfs, "gmail_id": mid,
            "cuenta": CUENTA}


async def _encolar(c):
    """Mismo flujo actual de ingesta: reglas de gestión → proc_queue (dedup) → archivos PDF."""
    from server import _reglas_auto_state, _es_gestion, _safe_name, PROC_DIR
    import pdf_service as pdfs_svc
    reglas = await _reglas_auto_state()
    if not _es_gestion(c["from"], c["subject"], bool(c["pdfs"]), reglas):
        return False
    if await db.proc_queue.find_one({"$or": [{"gmail_msg_id": c["gmail_id"]},
                                             {"subject": c["subject"], "date_iso": c["date"]}]}):
        return False
    qid = str(uuid.uuid4())
    folder = PROC_DIR / qid
    folder.mkdir(parents=True, exist_ok=True)
    attachments = []
    for pdf in c["pdfs"]:
        try:
            raw, nombre, _conv = await asyncio.to_thread(
                pdfs_svc.convertir_a_pdf, pdf["content_bytes"], pdf["filename"])
        except Exception:
            continue
        fn = _safe_name(nombre)
        (folder / fn).write_bytes(raw)
        attachments.append(fn)
    await db.proc_queue.insert_one({
        "id": qid, "subject": c["subject"], "sender": c["from"],
        "date_iso": c["date"], "status": "pendiente",
        "body_preview": (c.get("body") or "")[:500], "body_full": (c.get("body") or "")[:8000],
        "attachments": attachments, "attachments_bytes_dir": str(folder),
        "classification": {}, "campos": {}, "drive_folder_id": None,
        "fuente": "gmail_push", "gmail_msg_id": c["gmail_id"]})
    return True


# ══ PROCESAMIENTO EXACTAMENTE-UNA-VEZ (historyId + cerrojo atómico) ══════════
async def _procesar_history(history_id_notif):
    creds = await _creds()
    if not creds:
        logging.warning("📡 Gmail push recibido pero sin autorización OAuth")
        return 0
    st = await db.config.find_one({"_key": KEY_WATCH}) or {}
    start = st.get("history_id") or history_id_notif
    svc = _svc(creds)

    def _listar():
        out, page = [], None
        while True:
            resp = svc.users().history().list(
                userId="me", startHistoryId=start,
                historyTypes=["messageAdded"], pageToken=page).execute()
            for h in resp.get("history", []):
                for ma in h.get("messagesAdded", []):
                    msg = ma.get("message", {})
                    labels = msg.get("labelIds") or []
                    if "INBOX" in labels and "DRAFT" not in labels:
                        out.append(msg["id"])
            page = resp.get("nextPageToken")
            if not page:
                return out

    try:
        mids = await asyncio.to_thread(_listar)
    except Exception as e:
        # historyId expirado (404): se reancla el cursor al de la notificación
        logging.warning(f"📡 Gmail history.list: {str(e)[:150]} — cursor reanclado")
        mids = []
    nuevos = 0
    for mid in dict.fromkeys(mids):
        try:  # ⛡ Regla de Oro #68: reserva atómica (índice único gmail_msg_id)
            await db.gmail_procesados.insert_one({
                "gmail_msg_id": mid, "history_id": str(history_id_notif),
                "estado": "procesando", "fecha": _now()})
        except Exception:
            continue
        try:
            c = await asyncio.to_thread(_msg_a_correo, svc, mid)
            ok = await _encolar(c)
            await db.gmail_procesados.update_one({"gmail_msg_id": mid}, {"$set": {
                "estado": "encolado" if ok else "descartado_no_gestion",
                "subject": (c["subject"] or "")[:200], "sender": (c["from"] or "")[:120]}})
            nuevos += 1 if ok else 0
        except Exception as e:
            await db.gmail_procesados.update_one({"gmail_msg_id": mid},
                                                 {"$set": {"estado": "error", "error": str(e)[:200]}})
    await db.config.update_one({"_key": KEY_WATCH}, {"$set": {
        "history_id": str(history_id_notif), "ultimo_push": _now(),
        "ultimo_push_nuevos": nuevos}}, upsert=True)
    if nuevos:
        from server import _run_proc_auto, _proc_auto_state
        st2 = await _proc_auto_state()
        if not st2.get("running"):
            asyncio.create_task(_run_proc_auto())
        logging.info(f"📡 Gmail push: {nuevos} correo(s) nuevo(s) encolados en tiempo real")
    return nuevos


# ══ WEBHOOK PUB/SUB (público — responde 200 de inmediato) ════════════════════
@gmailr.post("/push")
async def gmail_push(request: Request):
    try:
        body = await request.json()
    except Exception:
        return {"ok": True, "ignorado": "cuerpo inválido"}
    msg = (body or {}).get("message") or {}
    try:
        data = json.loads(_b64url(msg.get("data")).decode() or "{}")
    except Exception:
        return {"ok": True, "ignorado": "data inválida"}
    if (data.get("emailAddress") or "").strip().lower() != CUENTA.lower():
        return {"ok": True, "ignorado": "cuenta no monitoreada"}
    hid = str(data.get("historyId") or "")
    if hid:
        asyncio.create_task(_procesar_history(hid))
    return {"ok": True, "recibido": hid}


# ══ ADMIN: estado, renovación y resincronización manual ══════════════════════
@gmailr.get("/estado")
async def gmail_estado(request: Request):
    _exigir_admin(request)
    tok = await db.config.find_one({"_key": KEY_TOK}, {"_id": 0, "refresh_token": 0, "access_token": 0}) or {}
    watch = await db.config.find_one({"_key": KEY_WATCH}, {"_id": 0}) or {}
    por_estado = {}
    async for g in db.gmail_procesados.aggregate([{"$group": {"_id": "$estado", "n": {"$sum": 1}}}]):
        por_estado[g["_id"]] = g["n"]
    return {"cuenta": CUENTA, "autorizado": bool(tok.get("actualizado")), "token": tok,
            "watch": watch, "procesados": por_estado, "topic": TOPIC,
            "webhook": f"{APP_URL}/api/gmail/push", "redirect_uri": REDIRECT_URI,
            "configuracion_gcp": [
                f"1) En el topic {TOPIC or '(falta GMAIL_PUBSUB_TOPIC)'} agregue como publicador a gmail-api-push@system.gserviceaccount.com",
                f"2) Cree una suscripción PUSH apuntando a {APP_URL}/api/gmail/push",
                f"3) En el cliente OAuth agregue la Redirect URI {REDIRECT_URI}",
                "4) Autorice con GET /api/gmail/oauth/iniciar (cuenta monitoreada)"]}


@gmailr.post("/watch/renovar")
async def gmail_watch_renovar(request: Request):
    _exigir_admin(request)
    return await iniciar_watch()


@gmailr.post("/sincronizar")
async def gmail_sincronizar(request: Request, dias: int = 1):
    """Resincronización manual: barre los mensajes recientes de INBOX vía Gmail API
    (mismo cerrojo exactamente-una-vez) por si algún push se perdió."""
    _exigir_admin(request)
    creds = await _creds()
    if not creds:
        raise HTTPException(status_code=412, detail="Gmail sin autorizar")
    svc = _svc(creds)

    def _listar():
        resp = svc.users().messages().list(userId="me", labelIds=["INBOX"],
                                           q=f"newer_than:{max(1, min(dias, 7))}d",
                                           maxResults=100).execute()
        return [m["id"] for m in resp.get("messages", [])]

    mids = await asyncio.to_thread(_listar)
    nuevos = 0
    for mid in mids:
        try:
            await db.gmail_procesados.insert_one({"gmail_msg_id": mid, "estado": "procesando",
                                                  "fecha": _now(), "origen": "sincronizacion_manual"})
        except Exception:
            continue
        try:
            c = await asyncio.to_thread(_msg_a_correo, svc, mid)
            ok = await _encolar(c)
            await db.gmail_procesados.update_one({"gmail_msg_id": mid}, {"$set": {
                "estado": "encolado" if ok else "descartado_no_gestion",
                "subject": (c["subject"] or "")[:200]}})
            nuevos += 1 if ok else 0
        except Exception as e:
            await db.gmail_procesados.update_one({"gmail_msg_id": mid},
                                                 {"$set": {"estado": "error", "error": str(e)[:200]}})
    return {"ok": True, "revisados": len(mids), "encolados": nuevos}


async def gmail_watch_loop():
    """Renueva el watch antes de su expiración (Google lo corta a los 7 días)."""
    await asyncio.sleep(35)
    try:
        await db.gmail_procesados.create_index("gmail_msg_id", unique=True)
    except Exception as e:
        logging.warning(f"gmail índice: {e}")
    while True:
        try:
            tok = await db.config.find_one({"_key": KEY_TOK}) or {}
            if tok.get("refresh_token"):
                watch = await db.config.find_one({"_key": KEY_WATCH}) or {}
                exp = watch.get("expira") or ""
                renovar = True
                try:
                    d = datetime.fromisoformat(exp)
                    if d.tzinfo is None:
                        d = d.replace(tzinfo=timezone.utc)
                    renovar = (d - datetime.now(timezone.utc)) < timedelta(hours=24)
                except Exception:
                    pass
                if renovar:
                    await iniciar_watch()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.warning(f"gmail watch loop: {e}")
        await asyncio.sleep(6 * 3600)
