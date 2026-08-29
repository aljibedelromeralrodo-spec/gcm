"""Minería histórica completa de gerardo.ext@centralmutuos.cl.
Reintenta cada 30 min hasta que Google libere el OVERQUOTA; luego mina todo."""
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
import sys
sys.path.insert(0, "/app/backend")
import email_service as es
import email, json, time, re

OUT = "/app/backend/scripts_lacruz/gerardo_headers.json"
LOG = lambda *a: print(time.strftime("%H:%M:%S"), *a, flush=True)


def headers_bulk(m, criterio, carpeta):
    typ, data = m.search(None, *criterio)
    ids = [i.decode() for i in (data[0].split() if data and data[0] else [])]
    out = []
    for i in range(0, len(ids), 150):
        rango = ",".join(ids[i:i + 150])
        typ, md = m.fetch(rango, "(BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE)])")
        for b in md:
            if not isinstance(b, tuple):
                continue
            h = email.message_from_bytes(b[1])
            out.append({"carpeta": carpeta, "from": es._dec(h.get("From", "")),
                        "to": es._dec(h.get("To", ""))[:120],
                        "subject": es._dec(h.get("Subject", "")), "date": h.get("Date", "")})
        time.sleep(1)
    LOG(carpeta, len(out))
    return out


def minar():
    acc = next(a for a in es.ACCOUNTS if "gerardo.ext" in (a.get("user") or ""))
    m = es._connect(acc)
    res = []
    m.select("INBOX", readonly=True)
    res += headers_bulk(m, ["FROM", "ecomac.cl"], "inbox_ecomac")
    res += headers_bulk(m, ["FROM", "aprobaciones@centralmutuos.cl"], "inbox_mesa")
    res += headers_bulk(m, ["SUBJECT", "borrador"], "esc_borrador")
    res += headers_bulk(m, ["SUBJECT", "escritura"], "esc_escritura")
    res += headers_bulk(m, ["SUBJECT", "firma"], "esc_firma")
    res += headers_bulk(m, ["SUBJECT", "TITULOS"], "esc_titulos")
    try:
        typ, folders = m.list()
        sent = next((f.decode().split(' "/" ')[-1].strip('"') for f in folders if b"\\Sent" in f), None)
        if sent:
            m.select(f'"{sent}"', readonly=True)
            res += headers_bulk(m, ["TO", "ecomac.cl"], "sent_ecomac")
            res += headers_bulk(m, ["TO", "aprobaciones@centralmutuos.cl"], "sent_mesa")
    except Exception as e:
        LOG("sent err", e)
    m.logout()
    json.dump(res, open(OUT, "w"), ensure_ascii=False)
    LOG("GUARDADO", len(res))


for intento in range(48):
    try:
        minar()
        LOG("ÉXITO — minería completa")
        break
    except Exception as e:
        LOG(f"intento {intento+1} falló: {e}")
        if "OVERQUOTA" not in str(e) and intento > 2:
            break
        time.sleep(1800)
