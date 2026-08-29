"""Verificación profunda: aprobaciones reales del trimestre (texto completo + nombres de adjuntos)."""
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
import sys
sys.path.insert(0, "/app/backend")
import email_service as es
import email, json, time, re

LOG = lambda *a: print(time.strftime("%H:%M:%S"), *a, flush=True)
OUT = "/app/backend/scripts_lacruz/aprob_trimestre.json"


def fetch_full(m, criterio, carpeta):
    typ, data = m.search(None, *criterio)
    ids = [i.decode() for i in (data[0].split() if data and data[0] else [])]
    LOG(carpeta, "mensajes:", len(ids))
    out = []
    for i in range(0, len(ids), 40):
        rango = ",".join(ids[i:i + 40])
        typ, md = m.fetch(rango, "(BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE)] BODYSTRUCTURE)")
        cur = None
        for b in md:
            if isinstance(b, tuple) and b"HEADER.FIELDS" in b[0]:
                h = email.message_from_bytes(b[1])
                cur = {"carpeta": carpeta, "from": es._dec(h.get("From", ""))[:80],
                       "subject": es._dec(h.get("Subject", "")), "date": h.get("Date", ""),
                       "estructura": b[0].decode("utf-8", "ignore")}
                out.append(cur)
            elif isinstance(b, bytes) and cur is not None and b"BODYSTRUCTURE" in b:
                cur["estructura"] += b.decode("utf-8", "ignore")
        time.sleep(1)
    return out


acc = next(a for a in es.ACCOUNTS if "gerardo.ext" in (a.get("user") or ""))
m = es._connect(acc)
res = []
m.select("INBOX", readonly=True)
res += fetch_full(m, ["SINCE", "01-Jun-2026", "FROM", "aprobaciones@centralmutuos.cl"], "inbox_mesa")
typ, folders = m.list()
sent = next((f.decode().split(' "/" ')[-1].strip('"') for f in folders if b"\\Sent" in f), None)
if sent:
    m.select(f'"{sent}"', readonly=True)
    res += fetch_full(m, ["SINCE", "01-Jun-2026", "TO", "ecomac.cl"], "sent_ecomac")
m.logout()
json.dump(res, open(OUT, "w"), ensure_ascii=False)
LOG("GUARDADO", len(res))
