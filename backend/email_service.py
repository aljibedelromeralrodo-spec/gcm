"""Servicio de correo (IMAP lectura + SMTP envio) para Central Mutuos.

Soporta multiples casillas:
  - Principal:  MAIL_USER  (ethangerardobarr@gmail.com)
  - Secundaria: MAIL2_USER (gerardo.ext@centralmutuos.cl)  <- clientes de mesa / PDFs

Funciones sincronas; llamar via asyncio.to_thread desde FastAPI.
Incluye cache simple con TTL para no reconectar en cada request.
"""
import imaplib
import socket
socket.setdefaulttimeout(90)  # blindaje: ningún socket IMAP/SMTP puede colgarse indefinidamente
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
    # Formato mesa: "Re: Kevin Macaya (DS19 - INMEDIATA - XIMENA)" -> Kevin Macaya
    limpio = re.sub(r"^\s*((re|fwd?|rv|fw)\s*:\s*)+", "", s, flags=re.I)
    # Quitar palabras de estado al inicio: "EVALUACION MELISA RIVERA", "APROBADO · Kevin ..."
    limpio = re.sub(r"^\s*(?:(?:pre[- ]?)?aprobado[a]?|aprobaci[oó]n|rechazado[a]?|rechazo|evaluaci[oó]n|"
                    r"solicitud(?:\s+de\s+\w+)?|documentos?|antecedentes|carpeta|cr[eé]dito)"
                    r"[\s:·|\-—]*", "", limpio, flags=re.I)
    mm = re.search(r"^([A-Za-zÁÉÍÓÚÑáéíóúñ ]{4,45}?)\s*(?:\(|//|-\s|RUT|·)", limpio)
    if mm and len(mm.group(1).split()) >= 2:
        return mm.group(1).strip().title()
    mm = re.search(r"^([A-Za-zÁÉÍÓÚÑáéíóúñ]+(?:\s+[A-Za-zÁÉÍÓÚÑáéíóúñ]+){1,3})\s*$", limpio.strip())
    if mm and len(mm.group(1).split()) >= 2:
        _stop = {"para", "credito", "crédito", "hipotecario", "subsidio", "vivienda", "usada",
                 "documentos", "evaluacion", "evaluación", "solicitud", "financiamiento",
                 "cliente", "carpeta", "antecedentes", "urgente", "nueva", "nuevo"}
        palabras = mm.group(1).split()
        if not any(p.lower() in _stop for p in palabras):
            return mm.group(1).strip().title()
    mm = re.search(r'"?([A-Za-zÁÉÍÓÚÑáéíóúñ ]{4,40})"?\s*<', remitente or "")
    if mm:
        return mm.group(1).strip().title()
    return (remitente or "Desconocido").split("<")[0].strip() or "Desconocido"


def fetch_headers_since(dias=31):
    """Trae encabezados (FROM/SUBJECT/DATE) de todos los correos de los ultimos N dias."""
    if not configured():
        return []
    from datetime import datetime, timedelta
    fecha = (datetime.now() - timedelta(days=dias)).strftime("%d-%b-%Y")
    todos = []
    for acc in ACCOUNTS:
        try:
            m = _connect(acc)
            m.select("INBOX", readonly=True)
            typ, data = m.search(None, "SINCE", fecha)
            ids = data[0].split() if data and data[0] else []
            ids = ids[-500:]
            if not ids:
                m.logout()
                continue
            idlist = [i.decode() for i in ids]
            partes = []
            for k in range(0, len(idlist), 100):
                idset = ",".join(idlist[k:k + 100])
                typ, msgs = m.fetch(idset, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
                partes.extend(msgs or [])
            m.logout()
            for part in partes:
                if not isinstance(part, tuple):
                    continue
                msg = email.message_from_bytes(part[1])
                subject = _dec(msg.get("Subject"))
                remitente = _dec(msg.get("From"))
                fecha_raw = msg.get("Date")
                try:
                    dt = parsedate_to_datetime(fecha_raw) if fecha_raw else None
                    fecha_iso = dt.isoformat() if dt else ""
                except Exception:
                    dt, fecha_iso = None, fecha_raw or ""
                todos.append({"from": remitente, "subject": subject, "date": fecha_iso,
                              "snippet": subject, "tipo": _clasificar(subject),
                              "cuenta": acc["user"], "_ts": dt.timestamp() if dt else 0})
        except Exception:
            continue
    todos.sort(key=lambda e: e.get("_ts", 0), reverse=True)
    for e in todos:
        e.pop("_ts", None)
    return todos


def procesar_seguimiento(max_emails=30, dias=None):
    """Lee los correos (ultimos N o ultimos `dias` dias) y detecta operaciones de mesa."""
    emails = fetch_headers_since(dias) if dias else fetch_recent(max_emails)
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


def _parse_full_message(msg, with_bytes=False):
    subject = _dec(msg.get("Subject"))
    remitente = _dec(msg.get("From"))
    fecha_raw = msg.get("Date")
    try:
        fecha = parsedate_to_datetime(fecha_raw).isoformat() if fecha_raw else ""
    except Exception:
        fecha = fecha_raw or ""
    body_text = ""
    attachments = []
    for part in msg.walk():
        ctype = part.get_content_type()
        disp = str(part.get("Content-Disposition") or "")
        fname = part.get_filename()
        if fname:
            fname = _dec(fname)
        if fname and ("attachment" in disp or not ctype.startswith("text/")):
            try:
                payload = part.get_payload(decode=True) or b""
            except Exception:
                payload = b""
            att = {"filename": fname, "size": len(payload)}
            if with_bytes:
                att["content_bytes"] = payload
            attachments.append(att)
        elif ctype == "text/plain" and "attachment" not in disp and not body_text:
            try:
                body_text = (part.get_payload(decode=True) or b"").decode(
                    part.get_content_charset() or "utf-8", errors="ignore")
            except Exception:
                pass
    return {"from": remitente, "subject": subject, "date": fecha,
            "tipo": _clasificar(subject + " " + body_text),
            "body": body_text[:1500], "attachments": attachments}


def fetch_recent_full(limit=20):
    """Correos recientes con id ('rol|uid') y metadatos de adjuntos (sin bytes)."""
    cache_key = f"recent_full_{limit}"
    cached = _cached(cache_key)
    if cached:
        return cached
    if not configured():
        return []
    out = []
    per_acc = max(5, limit // max(len(ACCOUNTS), 1))
    for acc in ACCOUNTS:
        try:
            m = _connect(acc)
            typ, data = m.select("INBOX", readonly=True)
            total = int(data[0]) if data and data[0] else 0
            start = max(1, total - per_acc + 1)
            for num in range(total, start - 1, -1):
                try:
                    typ, msgdata = m.fetch(str(num), "(UID BODY.PEEK[])")
                    if not msgdata or not isinstance(msgdata[0], tuple):
                        continue
                    head = msgdata[0][0]
                    head = head.decode(errors="ignore") if isinstance(head, bytes) else str(head)
                    mu = re.search(r"UID (\d+)", head)
                    uid = mu.group(1) if mu else str(num)
                    info = _parse_full_message(email.message_from_bytes(msgdata[0][1]))
                    info["id"] = f"{acc['rol']}|{uid}"
                    info["cuenta"] = acc["user"]
                    out.append(info)
                except Exception:
                    continue
            m.logout()
        except Exception:
            continue
    out.sort(key=lambda e: e.get("date", ""), reverse=True)
    return _store(cache_key, out)


def fetch_attachments_by_id(email_id, filename=None):
    """Descarga los adjuntos (bytes) de un correo identificado como 'rol|uid'."""
    rol, _, uid = (email_id or "").partition("|")
    acc = next((a for a in ACCOUNTS if a["rol"] == rol), None)
    if not acc or not uid:
        return []
    m = _connect(acc)
    m.select("INBOX", readonly=True)
    typ, msgdata = m.uid("fetch", uid, "(BODY.PEEK[])")
    m.logout()
    if not msgdata or not isinstance(msgdata[0], tuple):
        return []
    info = _parse_full_message(email.message_from_bytes(msgdata[0][1]), with_bytes=True)
    atts = info["attachments"]
    if filename:
        atts = [a for a in atts if a["filename"] == filename]
    return atts


def _sin_acentos(s):
    import unicodedata
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _buscar_ids_persona(m, tokens, original):
    """Une varias estrategias de SEARCH para tolerar acentos del servidor."""
    ids = set()
    for t in tokens[:3]:
        try:
            typ, data = m.search(None, "X-GM-RAW", f'"{t}"')
            if typ == "OK" and data and data[0]:
                ids |= set(data[0].split())
        except Exception:
            pass
    # Variante con acentos originales (literal UTF-8)
    orig_toks = [t for t in (original or "").lower().split() if len(t) > 2]
    for t in orig_toks[:3]:
        if t.encode("ascii", "ignore").decode() != t:
            try:
                m.literal = f'"{t}"'.encode("utf-8")
                typ, data = m.search("UTF-8", "X-GM-RAW")
                if typ == "OK" and data and data[0]:
                    ids |= set(data[0].split())
            except Exception:
                pass
    if not ids:
        try:
            typ, data = m.search(None, "TEXT", f'"{max(tokens, key=len)}"')
            if typ == "OK" and data and data[0]:
                ids |= set(data[0].split())
        except Exception:
            pass
    # Siempre revisar además los correos más recientes (caso: correo recién enviado)
    try:
        typ, data = m.search(None, "ALL")
        if typ == "OK" and data and data[0]:
            ids |= set(data[0].split()[-30:])
    except Exception:
        pass
    return sorted(ids, key=lambda x: int(x))


def search_email_headers_by_person(person_name, limit=10):
    """Búsqueda RÁPIDA (solo cabeceras) de correos que mencionen a la persona.
    Para sugerencias en vivo antes de forzar una carpeta."""
    name = _sin_acentos(person_name).strip()
    if not name:
        return []
    tokens = [t for t in name.split() if len(t) > 2] or [name]
    out = []
    for acc in ACCOUNTS:
        try:
            m = _connect(acc)
            m.select("INBOX", readonly=True)
            ids = _buscar_ids_persona(m, tokens, person_name)[-40:]
            for num in reversed(ids):
                typ, hd = m.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)])")
                if not hd or not isinstance(hd[0], tuple):
                    continue
                hmsg = email.message_from_bytes(hd[0][1])
                blob = _sin_acentos(f"{_dec(hmsg.get('Subject'))} {_dec(hmsg.get('From'))}")
                if not any(t in blob for t in tokens):
                    continue
                out.append({"subject": _dec(hmsg.get("Subject")),
                            "from": _dec(hmsg.get("From")),
                            "date": hmsg.get("Date", ""), "cuenta": acc["user"],
                            "message_id": (hmsg.get("Message-ID") or "").strip()})
                if len(out) >= limit:
                    break
            m.logout()
        except Exception:
            continue
        if len(out) >= limit:
            break
    return out


def search_attachments_by_person(person_name, limit=40):
    """Busca correos que mencionen a la persona (SEARCH en servidor) y trae sus adjuntos.
    Tolerante a acentos: 'González' y 'Gonzalez' se tratan igual."""
    name = _sin_acentos(person_name).strip()
    if not name:
        return []
    tokens = [t for t in name.split() if len(t) > 2] or [name]
    CAPTURA_EXT = (".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp")
    exactos, parciales = [], []
    for acc in ACCOUNTS:
        try:
            m = _connect(acc)
            m.select("INBOX", readonly=True)
            ids = _buscar_ids_persona(m, tokens, person_name)
            ids = ids[-60:]
            # Pre-filtrar por cabeceras (rapido) antes de bajar el correo completo
            candidatos = []
            for num in reversed(ids):
                typ, hd = m.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
                if not hd or not isinstance(hd[0], tuple):
                    continue
                hmsg = email.message_from_bytes(hd[0][1])
                blob_h = _sin_acentos(f"{_dec(hmsg.get('Subject'))} {_dec(hmsg.get('From'))}")
                if any(t in blob_h for t in tokens):
                    candidatos.append(num)
                if len(candidatos) >= 8:
                    break
            # El SEARCH del servidor ya buscó en el cuerpo: incluir también los que
            # mencionan a la persona solo en el cuerpo (correos reenviados, etc.)
            if len(candidatos) < 8:
                for num in reversed(ids):
                    if num not in candidatos:
                        candidatos.append(num)
                    if len(candidatos) >= 8:
                        break
            for num in candidatos:
                typ, msgdata = m.fetch(num, "(BODY.PEEK[])")
                if not msgdata or not isinstance(msgdata[0], tuple):
                    continue
                info = _parse_full_message(email.message_from_bytes(msgdata[0][1]), with_bytes=True)
                blob = _sin_acentos(f"{info['subject']} {info['from']} {info['body']}")
                hits = sum(1 for t in tokens if t in blob)
                if hits == 0:
                    continue
                pdfs = [{"filename": a["filename"], "content_bytes": a["content_bytes"]}
                        for a in info["attachments"]
                        if (a["filename"] or "").lower().endswith(CAPTURA_EXT) and a.get("content_bytes")]
                registro = {"from": info["from"], "subject": info["subject"],
                            "date": info["date"], "body": info["body"], "pdfs": pdfs}
                (exactos if hits == len(tokens) else parciales).append(registro)
            m.logout()
        except Exception:
            continue
    return exactos if exactos else parciales


def fetch_attachments_by_message_ids(message_ids):
    """Baja los correos exactos (por Message-ID) con sus adjuntos."""
    CAPTURA_EXT = (".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp")
    pendientes = {m.strip() for m in (message_ids or []) if m and m.strip()}
    out = []
    for acc in ACCOUNTS:
        if not pendientes:
            break
        try:
            m = _connect(acc)
            m.select("INBOX", readonly=True)
            encontrados = set()
            for mid in list(pendientes):
                try:
                    typ, data = m.search(None, "HEADER", "Message-ID", mid)
                except Exception:
                    continue
                nums = data[0].split() if typ == "OK" and data and data[0] else []
                if not nums:
                    continue
                typ, msgdata = m.fetch(nums[-1], "(BODY.PEEK[])")
                if not msgdata or not isinstance(msgdata[0], tuple):
                    continue
                info = _parse_full_message(email.message_from_bytes(msgdata[0][1]), with_bytes=True)
                pdfs = [{"filename": a["filename"], "content_bytes": a["content_bytes"]}
                        for a in info["attachments"]
                        if (a["filename"] or "").lower().endswith(CAPTURA_EXT) and a.get("content_bytes")]
                out.append({"from": info["from"], "subject": info["subject"],
                            "date": info["date"], "body": info["body"], "pdfs": pdfs})
                encontrados.add(mid)
            pendientes -= encontrados
            m.logout()
        except Exception:
            continue
    return out


def _sent_folder(m):
    """Detecta la carpeta de Enviados (flag \\Sent) de la cuenta."""
    try:
        typ, boxes = m.list()
        for b in boxes or []:
            s = b.decode(errors="ignore") if isinstance(b, bytes) else str(b)
            if "\\Sent" in s:
                mm = re.findall(r'"([^"]+)"', s)
                if mm:
                    return mm[-1]
    except Exception:
        pass
    return "[Gmail]/Sent Mail"


def fetch_sent_headers(limit=60):
    """Cabeceras (TO, SUBJECT, DATE) de los últimos correos ENVIADOS de todas las cuentas."""
    global SENT_LAST
    cached = _cached("sent_headers")
    if cached is not None:
        return cached
    out = []
    for acc in ACCOUNTS:
        try:
            m = _connect(acc)
            folder = _sent_folder(m)
            typ, data = m.select(f'"{folder}"', readonly=True)
            total = int(data[0]) if data and data[0] else 0
            if total:
                start = max(1, total - limit + 1)
                ids = ",".join(str(i) for i in range(total, start - 1, -1))
                typ, msgs = m.fetch(ids, "(BODY.PEEK[HEADER.FIELDS (TO SUBJECT DATE)])")
                for part in msgs or []:
                    if not isinstance(part, tuple):
                        continue
                    h = email.message_from_bytes(part[1])
                    fecha_raw = h.get("Date")
                    try:
                        fecha = parsedate_to_datetime(fecha_raw).isoformat() if fecha_raw else ""
                    except Exception:
                        fecha = fecha_raw or ""
                    out.append({"subject": _dec(h.get("Subject")), "to": _dec(h.get("To")),
                                "date": fecha, "cuenta": acc["user"]})
            m.logout()
        except Exception:
            continue
    SENT_LAST = out
    return _store("sent_headers", out)


SENT_LAST = []


def _attachments_from_bodystructure(raw):
    """Extrae nombres de adjuntos desde el BODYSTRUCTURE (sin descargar el mensaje)."""
    s = raw.decode(errors="ignore") if isinstance(raw, bytes) else str(raw)
    nombres = []
    for m in re.finditer(r'"(?:FILENAME|NAME)"\s+"([^"]+)"', s, re.I):
        val = m.group(1)
        try:
            val = str(email.header.make_header(email.header.decode_header(val)))
        except Exception:
            pass
        if val not in nombres:
            nombres.append(val)
    return nombres


def fetch_emails_from_sender(sender_kw, limit=15):
    """Correos recientes de un remitente (ej. 'evaluaciones') con sus adjuntos (metadata).

    Rápido: usa cabeceras + BODYSTRUCTURE, no descarga los adjuntos.
    """
    kw = (sender_kw or "").strip()
    if not kw:
        return []
    out = []
    vistos = set()
    for acc in ACCOUNTS:
        try:
            m = _connect(acc)
            m.select("INBOX", readonly=True)
            try:
                typ, data = m.search(None, "X-GM-RAW", f'from:{kw}')
                if typ != "OK":
                    raise Exception("gm-raw")
            except Exception:
                typ, data = m.search(None, "FROM", f'"{kw}"')
            ids = data[0].split() if data and data[0] else []
            for num in reversed(ids[-limit:]):
                typ, msgdata = m.fetch(num, "(UID BODYSTRUCTURE BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
                if not msgdata or not isinstance(msgdata[0], tuple):
                    continue
                descriptor = msgdata[0][0]
                descriptor = descriptor.decode(errors="ignore") if isinstance(descriptor, bytes) else str(descriptor)
                header_bytes = msgdata[0][1] or b""
                mu = re.search(r"UID (\d+)", descriptor)
                uid = mu.group(1) if mu else str(num)
                hmsg = email.message_from_bytes(header_bytes)
                subject = _dec(hmsg.get("Subject"))
                remitente = _dec(hmsg.get("From"))
                fecha_raw = hmsg.get("Date")
                try:
                    fecha = parsedate_to_datetime(fecha_raw).isoformat() if fecha_raw else ""
                except Exception:
                    fecha = fecha_raw or ""
                nombres = _attachments_from_bodystructure(descriptor)
                clave = f"{subject}|{len(nombres)}"
                if clave in vistos:
                    continue
                vistos.add(clave)
                out.append({"id": f"{acc['rol']}|{uid}", "cuenta": acc["user"],
                            "from": remitente, "subject": subject, "date": fecha, "body": "",
                            "attachments": [{"filename": n, "size": 0} for n in nombres]})
            m.logout()
        except Exception:
            continue
    out.sort(key=lambda e: e.get("date", ""), reverse=True)
    return out


def _texto_de_msg(msg, cap=6000):
    """Texto plano del mensaje (fallback: HTML sin tags)."""
    plano, html = "", ""
    for part in msg.walk():
        ctype = part.get_content_type()
        disp = str(part.get("Content-Disposition") or "")
        if "attachment" in disp:
            continue
        try:
            raw = (part.get_payload(decode=True) or b"").decode(
                part.get_content_charset() or "utf-8", errors="ignore")
        except Exception:
            continue
        if ctype == "text/plain" and not plano:
            plano = raw
        elif ctype == "text/html" and not html:
            html = raw
    texto = plano or re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"[ \t]+", " ", texto).strip()[:cap]


def buscar_hilo_por_asunto(subject_kw, limit=8):
    """Mensajes recibidos cuyo asunto contiene subject_kw, excluyendo los enviados
    por nuestras propias cuentas. Devuelve [{msgid, from, from_email, subject, date, body}]."""
    kw = (subject_kw or "").strip()
    if not kw:
        return []
    propios = {a["user"].lower() for a in ACCOUNTS}
    out, vistos = [], set()
    for acc in ACCOUNTS:
        try:
            m = _connect(acc)
            m.select("INBOX", readonly=True)
            try:
                typ, data = m.search(None, "X-GM-RAW", f'subject:"{kw}"')
                if typ != "OK":
                    raise Exception("gm-raw")
            except Exception:
                typ, data = m.search(None, "SUBJECT", kw[:60].encode("ascii", "ignore").decode())
            ids = data[0].split() if data and data[0] else []
            for num in reversed(ids[-limit:]):
                typ, msgdata = m.fetch(num, "(RFC822)")
                if not msgdata or not isinstance(msgdata[0], tuple):
                    continue
                msg = email.message_from_bytes(msgdata[0][1])
                msgid = (msg.get("Message-ID") or "").strip()
                remitente = _dec(msg.get("From"))
                em = re.search(r"[\w.+-]+@[\w.-]+", remitente or "")
                from_email = em.group(0).lower() if em else ""
                if not msgid or msgid in vistos or from_email in propios:
                    continue
                vistos.add(msgid)
                fecha_raw = msg.get("Date")
                try:
                    fecha = parsedate_to_datetime(fecha_raw).isoformat() if fecha_raw else ""
                except Exception:
                    fecha = fecha_raw or ""
                out.append({"msgid": msgid, "from": remitente, "from_email": from_email,
                            "subject": _dec(msg.get("Subject")), "date": fecha,
                            "body": _texto_de_msg(msg),
                            "attachments": [_dec(p.get_filename()) for p in msg.walk() if p.get_filename()]})
            m.logout()
        except Exception:
            continue
    out.sort(key=lambda e: e.get("date", ""))
    return out


def _log_smtp(entry):
    """Guarda el resultado SMTP completo de cada envío en la base de datos."""
    try:
        from pymongo import MongoClient
        global _smtp_log_col
        if "_smtp_log_col" not in globals() or _smtp_log_col is None:
            _smtp_log_col = MongoClient(os.environ["MONGO_URL"],
                                        serverSelectionTimeoutMS=3000)[os.environ["DB_NAME"]]["correos_smtp_log"]
        from datetime import datetime, timezone
        entry["fecha"] = datetime.now(timezone.utc).isoformat()
        _smtp_log_col.insert_one(entry)
    except Exception:
        pass


def _fmt_refused(refused):
    partes = []
    for rcpt, (code, resp) in refused.items():
        r = resp.decode(errors="ignore") if isinstance(resp, bytes) else str(resp)
        partes.append(f"{rcpt}: {code} {r}")
    return "; ".join(partes)


CLAVE_MAESTRA = "0586"


def _blindaje_simulaciones(attachments, clave=""):
    """REGLA INVIOLABLE (blindaje final): NINGUNA simulación sale del sistema con más
    de 1 página (sin otros plazos ni gastos operacionales). Se aplica a TODO envío
    (aprobación cliente, autocorreo, etc.). Solo la clave maestra 0586 permite omitirlo.
    Devuelve (attachments_seguros, nombres_ajustados)."""
    if clave == CLAVE_MAESTRA:
        return attachments or [], []
    out, ajustados = [], []
    for att in attachments or []:
        fn = att.get("filename") or ""
        if re.search(r"simulad|simulaci[oó]n", fn, re.I) and not re.search(r"carta|aprobaci[oó]n", fn, re.I):
            try:
                import io
                from pypdf import PdfReader, PdfWriter
                raw = base64.b64decode(att.get("content_b64", ""))
                reader = PdfReader(io.BytesIO(raw))
                if len(reader.pages) > 1:
                    w = PdfWriter()
                    w.add_page(reader.pages[0])
                    buf = io.BytesIO()
                    w.write(buf)
                    att = {**att, "content_b64": base64.b64encode(buf.getvalue()).decode()}
                    ajustados.append(fn)
            except Exception:
                pass
        out.append(att)
    return out, ajustados


def send_mail(to, subject, body_html, attachments=None, desde="secundaria", cc=None, headers=None, clave_sin_ajuste=""):
    """Envia un correo. attachments: [{filename, content_b64}]
    desde: 'secundaria' (gerardo.ext@, para PDFs a clientes) o 'principal'.
    cc: str o lista. headers: dict extra (ej In-Reply-To, References)."""
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
    if cc:
        msg["Cc"] = cc if isinstance(cc, str) else ", ".join(cc)
    for hk, hv in (headers or {}).items():
        if hv:
            msg[hk] = hv
    msg["Subject"] = subject
    msg.attach(MIMEText(body_html or "", "html", "utf-8"))
    attachments, _blindados = _blindaje_simulaciones(attachments, clave_sin_ajuste)
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
            refused = s.send_message(msg)
        if refused:
            det = _fmt_refused(refused)
            code = list(refused.values())[0][0]
            res = {"success": False, "error": f"Destinatario rechazado por SMTP: {det}",
                   "smtp_code": code, "smtp_response": det, "desde": acc["user"]}
        else:
            res = {"success": True, "desde": acc["user"], "smtp_code": 250,
                   "smtp_response": "250 OK — aceptado por el servidor SMTP de Gmail"}
    except smtplib.SMTPRecipientsRefused as e:
        det = _fmt_refused(e.recipients)
        code = list(e.recipients.values())[0][0] if e.recipients else None
        res = {"success": False, "error": f"Todos los destinatarios rechazados: {det}",
               "smtp_code": code, "smtp_response": det, "desde": acc["user"]}
    except smtplib.SMTPResponseException as e:
        resp = e.smtp_error.decode(errors="ignore") if isinstance(e.smtp_error, bytes) else str(e.smtp_error)
        res = {"success": False, "error": f"{e.smtp_code} {resp}",
               "smtp_code": e.smtp_code, "smtp_response": resp, "desde": acc["user"]}
    except Exception as e:
        res = {"success": False, "error": str(e), "smtp_code": None,
               "smtp_response": str(e), "desde": acc["user"]}
    _log_smtp({"to": msg["To"], "cc": msg.get("Cc", ""), "subject": subject,
               "desde": acc["user"], "success": res["success"],
               "smtp_code": res.get("smtp_code"), "smtp_response": res.get("smtp_response", ""),
               "simulaciones_blindadas": _blindados,
               "error": res.get("error", "")})
    return res
