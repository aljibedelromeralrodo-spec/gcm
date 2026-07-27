"""Servicio de correo (IMAP lectura + SMTP envio) para Central Mutuos.

Soporta multiples casillas:
  - Principal:  MAIL_USER  (ethangerardobarr@gmail.com)
  - Secundaria: MAIL2_USER (gerardo.ext@centralmutuos.cl)  <- clientes de mesa / PDFs

Funciones sincronas; llamar via asyncio.to_thread desde FastAPI.
Incluye cache simple con TTL para no reconectar en cada request.
"""
import imaplib
import smtplib
import ssl
import os
import re
import time
import base64
import email
from email.header import decode_header, make_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import parsedate_to_datetime, formataddr

IMAP_HOST = os.environ.get("MAIL_IMAP_HOST", "imap.gmail.com")
SMTP_HOST = os.environ.get("MAIL_SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("MAIL_SMTP_PORT", "465"))
FROM_NAME = os.environ.get("MAIL_FROM_NAME", "Central Mutuos")


def _clean_pwd(p):
    return (p or "").replace(" ", "")


ACCOUNTS = []
_u1 = os.environ.get("MAIL_USER", "")
_p1 = _clean_pwd(os.environ.get("MAIL_APP_PASSWORD", ""))
_u2 = os.environ.get("MAIL2_USER", "")
_p2 = _clean_pwd(os.environ.get("MAIL2_APP_PASSWORD", ""))
if _u1 and _p1:
    ACCOUNTS.append({"user": _u1, "pwd": _p1, "rol": "principal"})
if _u2 and _p2:
    ACCOUNTS.append({"user": _u2, "pwd": _p2, "rol": "secundaria"})

_cache = {}
TTL = 60  # seconds


def _cached(key):
    item = _cache.get(key)
    if item and time.time() - item[0] < TTL:
        return item[1]
    return None


def _store(key, value):
    _cache[key] = (time.time(), value)
    return value


def configured():
    return len(ACCOUNTS) > 0


def _connect(acc):
    m = imaplib.IMAP4_SSL(IMAP_HOST, 993, timeout=25)
    m.login(acc["user"], acc["pwd"])
    return m


def _dec(value):
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return str(value)


def _clasificar(texto):
    t = (texto or "").lower()
    if re.search(r"aprobad|aprobaci[oó]n|pre[- ]?aprobad", t):
        return "aprobacion"
    if re.search(r"rechaz|denegad|no viable", t):
        return "rechazo"
    if re.search(r"observa|pendiente|falta|reparo|documentaci[oó]n", t):
        return "observacion"
    return "general"


def get_status():
    cached = _cached("status")
    if cached:
        return cached
    if not configured():
        return {"connected": False, "account": "", "total_emails": 0, "accounts": []}
    accounts = []
    total_global = 0
    any_ok = False
    for acc in ACCOUNTS:
        try:
            m = _connect(acc)
            typ, data = m.select("INBOX", readonly=True)
            total = int(data[0]) if data and data[0] else 0
            m.logout()
            accounts.append({"account": acc["user"], "rol": acc["rol"],
                             "connected": True, "total_emails": total})
            total_global += total
            any_ok = True
        except Exception as e:
            accounts.append({"account": acc["user"], "rol": acc["rol"],
                             "connected": False, "total_emails": 0, "error": str(e)})
    principal = accounts[0]["account"] if accounts else ""
    return _store("status", {
        "connected": any_ok,
        "account": " + ".join(a["account"] for a in accounts if a["connected"]) or principal,
        "total_emails": total_global,
        "accounts": accounts,
    })


def _fetch_account(acc, limit):
    emails = []
    m = _connect(acc)
    typ, data = m.select("INBOX", readonly=True)
    total = int(data[0]) if data and data[0] else 0
    if total == 0:
        m.logout()
        return emails
    start = max(1, total - limit + 1)
    ids = ",".join(str(i) for i in range(total, start - 1, -1))
    typ, msgs = m.fetch(ids, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
    m.logout()
    for part in msgs:
        if not isinstance(part, tuple):
            continue
        msg = email.message_from_bytes(part[1])
        subject = _dec(msg.get("Subject"))
        remitente = _dec(msg.get("From"))
        fecha_raw = msg.get("Date")
        try:
            dt = parsedate_to_datetime(fecha_raw) if fecha_raw else None
            fecha = dt.isoformat() if dt else ""
        except Exception:
            dt, fecha = None, fecha_raw or ""
        emails.append({
            "from": remitente,
            "subject": subject,
            "date": fecha,
            "snippet": subject,
            "tipo": _clasificar(subject),
            "cuenta": acc["user"],
            "_ts": dt.timestamp() if dt else 0,
        })
    return emails


def fetch_recent(limit=15):
    cache_key = f"recent_{limit}"
    cached = _cached(cache_key)
    if cached:
        return cached
    if not configured():
        return []
    todos = []
    for acc in ACCOUNTS:
        try:
            todos.extend(_fetch_account(acc, limit))
        except Exception:
            continue
    todos.sort(key=lambda e: e.get("_ts", 0), reverse=True)
    for e in todos:
        e.pop("_ts", None)
    return _store(cache_key, todos[:max(limit, 15)])


def email_stats(sample=40):
    cached = _cached("stats")
    if cached:
        return cached
    emails = fetch_recent(sample)
    stats = {"aprobaciones": 0, "rechazos": 0, "observaciones": 0}
    for e in emails:
        if e["tipo"] == "aprobacion":
            stats["aprobaciones"] += 1
        elif e["tipo"] == "rechazo":
            stats["rechazos"] += 1
        elif e["tipo"] == "observacion":
            stats["observaciones"] += 1
    st = get_status()
    result = {
        "imap_status": "conectado" if st.get("connected") else "desconectado",
        "imap_backoff_restante_seg": 0,
        "cuenta": st.get("account", ""),
        "analizados": len(emails),
        **stats,
    }
    return _store("stats", result)


def _extraer_nombre(subject, remitente):
    """Heuristica: nombre del cliente desde el asunto o el remitente."""
    s = subject or ""
    mm = re.search(r"(?:cliente|sr\.?|sra\.?|don|dona)\s*[:\-]?\s*([A-Za-zÁÉÍÓÚÑáéíóúñ ]{4,40})", s, re.I)
    if mm:
        return mm.group(1).strip().title()
    mm = re.search(r'"?([A-Za-zÁÉÍÓÚÑáéíóúñ ]{4,40})"?\s*<', remitente or "")
    if mm:
        return mm.group(1).strip().title()
    return (remitente or "Desconocido").split("<")[0].strip() or "Desconocido"


def procesar_seguimiento(max_emails=30):
    """Lee los ultimos correos de todas las casillas y detecta operaciones de mesa."""
    emails = fetch_recent(max_emails)
    ops = []
    for e in emails:
        tipo = e["tipo"]
        if tipo == "general":
            continue
        ops.append({
            "cliente": _extraer_nombre(e["subject"], e["from"]),
            "estado": tipo,
            "asunto": e["subject"],
            "remitente": e["from"],
            "fecha": e["date"],
            "cuenta": e.get("cuenta", ""),
        })
    return ops


def fetch_pdf_attachments(sender_filter=None, limit=20, incluir_sin_adjuntos=False):
    """Trae correos recientes (de todas las casillas) que tengan PDFs adjuntos.

    sender_filter: substring para filtrar por remitente (ej: 'aprobaciones@centralmutuos.cl').
    incluir_sin_adjuntos: si True, incluye tambien correos SIN adjuntos (ej: rechazos solo texto).
    Devuelve: [{from, subject, date, tipo, cuenta, body, pdfs:[{filename, content_bytes}]}]
    """
    if not configured():
        return []
    out = []
    for acc in ACCOUNTS:
        try:
            m = _connect(acc)
            m.select("INBOX", readonly=True)
            crit = ["ALL"]
            if sender_filter:
                crit = ["FROM", f'"{sender_filter}"']
            typ, data = m.search(None, *crit)
            ids = data[0].split() if data and data[0] else []
            ids = ids[-limit:]
            for num in reversed(ids):
                typ, msgdata = m.fetch(num, "(RFC822)")
                if not msgdata or not isinstance(msgdata[0], tuple):
                    continue
                msg = email.message_from_bytes(msgdata[0][1])
                subject = _dec(msg.get("Subject"))
                remitente = _dec(msg.get("From"))
                fecha_raw = msg.get("Date")
                try:
                    fecha = parsedate_to_datetime(fecha_raw).isoformat() if fecha_raw else ""
                except Exception:
                    fecha = fecha_raw or ""
                pdfs = []
                body_text = ""
                CAPTURA_EXT = (".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp")
                for part in msg.walk():
                    ctype = part.get_content_type()
                    disp = str(part.get("Content-Disposition") or "")
                    fname = part.get_filename()
                    if fname:
                        fname = _dec(fname)
                    es_adjunto = (ctype == "application/pdf"
                                  or ctype.startswith("image/") and "attachment" in disp
                                  or (fname or "").lower().endswith(CAPTURA_EXT))
                    if es_adjunto and fname:
                        try:
                            payload = part.get_payload(decode=True)
                            if payload:
                                pdfs.append({"filename": fname or "documento.pdf",
                                             "content_bytes": payload})
                        except Exception:
                            continue
                    elif ctype == "text/plain" and "attachment" not in disp and not body_text:
                        try:
                            body_text = (part.get_payload(decode=True) or b"").decode(
                                part.get_content_charset() or "utf-8", errors="ignore")
                        except Exception:
                            pass
                if pdfs or incluir_sin_adjuntos:
                    out.append({
                        "from": remitente, "subject": subject, "date": fecha,
                        "tipo": _clasificar(subject + " " + body_text),
                        "cuenta": acc["user"], "body": body_text, "pdfs": pdfs,
                    })
            m.logout()
        except Exception:
            continue
    return out


def send_mail(to, subject, body_html, attachments=None, desde="secundaria"):
    """Envia un correo. attachments: [{filename, content_b64}]
    desde: 'secundaria' (gerardo.ext@, para PDFs a clientes) o 'principal'."""
    if not configured():
        return {"success": False, "error": "Correo no configurado"}
    acc = None
    for a in ACCOUNTS:
        if a["rol"] == desde:
            acc = a
            break
    if acc is None:
        acc = ACCOUNTS[0]
    msg = MIMEMultipart()
    msg["From"] = formataddr((FROM_NAME, acc["user"]))
    msg["To"] = to if isinstance(to, str) else ", ".join(to)
    msg["Subject"] = subject
    msg.attach(MIMEText(body_html or "", "html", "utf-8"))
    for att in attachments or []:
        try:
            content = base64.b64decode(att.get("content_b64", ""))
            part = MIMEApplication(content)
            part.add_header("Content-Disposition", "attachment",
                            filename=att.get("filename", "adjunto.pdf"))
            msg.attach(part)
        except Exception:
            continue
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=25, context=ctx) as s:
            s.login(acc["user"], acc["pwd"])
            s.send_message(msg)
        return {"success": True, "desde": acc["user"]}
    except Exception as e:
        return {"success": False, "error": str(e)}
