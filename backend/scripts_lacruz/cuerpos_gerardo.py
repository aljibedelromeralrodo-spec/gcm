"""Descarga ligera de cuerpos (primeros 1500B de texto) de la casilla gerardo.ext."""
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
import sys
sys.path.insert(0, "/app/backend")
import email_service as es
import email, json, time, re, quopri, base64

OUT = "/app/backend/scripts_lacruz/gerardo_bodies.json"
LOG = lambda *a: print(time.strftime("%H:%M:%S"), *a, flush=True)


def _decode_snippet(raw, hdr_bytes):
    try:
        h = email.message_from_bytes(hdr_bytes)
        enc = (h.get("Content-Transfer-Encoding") or "").lower()
    except Exception:
        enc = ""
    try:
        if "quoted" in enc:
            raw = quopri.decodestring(raw)
        elif "base64" in enc:
            raw = base64.b64decode(raw + b"=" * (-len(raw) % 4))
    except Exception:
        pass
    txt = raw.decode("utf-8", "ignore")
    txt = re.sub(r"<[^>]+>", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()[:1200]


def fetch_bodies(m, criterio, carpeta):
    typ, data = m.search(None, *criterio)
    ids = [i.decode() for i in (data[0].split() if data and data[0] else [])]
    out = []
    for i in range(0, len(ids), 100):
        rango = ",".join(ids[i:i + 100])
        typ, md = m.fetch(rango, "(BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE CONTENT-TRANSFER-ENCODING)] BODY.PEEK[1]<0.1500>)")
        cur = None
        for b in md:
            if isinstance(b, tuple):
                if b"HEADER.FIELDS" in b[0]:
                    h = email.message_from_bytes(b[1])
                    cur = {"carpeta": carpeta,
                           "from": es._dec(h.get("From", "")),
                           "to": es._dec(h.get("To", ""))[:120],
                           "subject": es._dec(h.get("Subject", "")),
                           "date": h.get("Date", ""), "_hdr": b[1], "body": ""}
                    out.append(cur)
                elif cur is not None:
                    cur["body"] = _decode_snippet(b[1], cur.get("_hdr", b""))
        time.sleep(1.5)
    for o in out:
        o.pop("_hdr", None)
    LOG(carpeta, len(out))
    return out


def minar():
    acc = next(a for a in es.ACCOUNTS if "gerardo.ext" in (a.get("user") or ""))
    m = es._connect(acc)
    res = []
    m.select("INBOX", readonly=True)
    res += fetch_bodies(m, ["FROM", "ecomac.cl"], "inbox_ecomac")
    typ, folders = m.list()
    sent = next((f.decode().split(' "/" ')[-1].strip('"') for f in folders if b"\\Sent" in f), None)
    if sent:
        m.select(f'"{sent}"', readonly=True)
        res += fetch_bodies(m, ["TO", "ecomac.cl"], "sent_ecomac")
    m.logout()
    json.dump(res, open(OUT, "w"), ensure_ascii=False)
    LOG("GUARDADO", len(res))


for intento in range(6):
    try:
        minar()
        LOG("ÉXITO cuerpos")
        break
    except Exception as e:
        LOG(f"intento {intento+1} falló: {e}")
        if "OVERQUOTA" not in str(e).upper():
            break
        time.sleep(1800)
