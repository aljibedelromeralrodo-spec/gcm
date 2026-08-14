"""BASE_DE_DATOS_HISTORICA — Minado resumible del buzón gerardo.ext@centralmutuos.cl.

Reglas: #64 (Bodega primero, IMAP solo si falta), #65 (certeza 100%, RUT validado o Revisión Manual).
REGLA DE HIERRO: sin Email el registro NO entra a la base de datos.
"""
import io
import re
import email
import uuid
import asyncio
import logging
from email.header import decode_header, make_header
from email.utils import parseaddr, getaddresses, parsedate_to_datetime
from datetime import datetime, timezone
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from database import db
import email_service as _mail

historia = APIRouter(prefix="/historia")
_now = lambda: datetime.now(timezone.utc).isoformat()

BLOQUE = 100
DOMINIOS_PROPIOS = ("centralmutuos.cl", "migrup.cl", "valueproperty.cl", "concreces.cl",
                    "sii.cl", "google.com", "googlemail.com", "amazonses.com", "mailchimp",
                    "sendgrid", "no-reply", "noreply", "notificaciones", "notifications")

CIUDADES = ["santiago", "la serena", "coquimbo", "ovalle", "valparaíso", "valparaiso",
            "viña del mar", "vina del mar", "concepción", "concepcion", "antofagasta",
            "iquique", "arica", "copiapó", "copiapo", "vallenar", "rancagua", "talca",
            "temuco", "puerto montt", "chillán", "chillan", "los ángeles", "los angeles",
            "calama", "quilpué", "quilpue", "puente alto", "maipú", "maipu", "peñuelas"]

RUT_RE = re.compile(r"\b(\d{1,2}\.?\d{3}\.?\d{3})\s*-\s*([\dkK])\b")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
INMO_RE = re.compile(r"inmobiliaria\s+([A-ZÁÉÍÓÚÑa-záéíóúñ][\w&.\- ]{2,35})", re.I)
PROY_RE = re.compile(r"proyecto\s+([A-ZÁÉÍÓÚÑ0-9][\w&.\- ]{2,35})", re.I)
FONO_RE = re.compile(r"(?:\+?56\s?)?(?:9\s?)\d{4}\s?\d{4}\b")


def validar_rut_chileno(rut):
    """Dígito verificador módulo 11 — solo RUTs 100% válidos se guardan (Regla #65)."""
    r = re.sub(r"[^0-9kK]", "", str(rut or "")).lower()
    if len(r) < 8 or not r[:-1].isdigit():
        return False
    cuerpo, dv = r[:-1], r[-1]
    s, m = 0, 2
    for c in reversed(cuerpo):
        s += int(c) * m
        m = 2 if m == 7 else m + 1
    res = 11 - (s % 11)
    dv_calc = "0" if res == 11 else ("k" if res == 10 else str(res))
    return dv == dv_calc


def _fmt_rut(rut):
    r = re.sub(r"[^0-9kK]", "", str(rut or "")).lower()
    if len(r) < 8:
        return rut or ""
    cuerpo, dv = r[:-1], r[-1].upper()
    partes = []
    while cuerpo:
        partes.insert(0, cuerpo[-3:])
        cuerpo = cuerpo[:-3]
    return ".".join(partes) + "-" + dv


def _dec(s):
    try:
        return str(make_header(decode_header(s or "")))
    except Exception:
        return s or ""


def _email_externo(addr):
    a = (addr or "").strip().lower()
    if not a or "@" not in a:
        return False
    propios = {acc["user"].lower() for acc in _mail.ACCOUNTS}
    if a in propios:
        return False
    return not any(d in a for d in DOMINIOS_PROPIOS)


def _texto_msg(msg, limite=12000):
    out = ""
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            try:
                out += part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "ignore")
            except Exception:
                pass
        elif part.get_content_type() == "text/html" and not out:
            try:
                html = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "ignore")
                out = re.sub(r"<[^>]+>", " ", html)
            except Exception:
                pass
        if len(out) > limite:
            break
    return out[:limite]


async def _desde_bodega(email_c, rut, nombre):
    """Regla #64: si el cliente ya existe en la Bodega, la verdad DashAI manda."""
    q = []
    if rut:
        q.append({"rut": {"$regex": re.escape(rut[-9:]), "$options": "i"}})
    if nombre and len(nombre) > 5:
        q.append({"nombre": {"$regex": re.escape(nombre[:20]), "$options": "i"}})
    if not q:
        return {}
    fd = await db.folders.find_one({"$or": q})
    if not fd:
        return {}
    p = fd.get("perfil_consolidado") or {}
    return {"nombre": fd.get("nombre") or nombre, "rut": fd.get("rut") or rut,
            "inmobiliaria": p.get("inmobiliaria") or fd.get("inmobiliaria") or "",
            "proyecto": p.get("proyecto") or fd.get("proyecto") or "", "fuente": "bodega_dashai"}


def _extraer(msg):
    """Extracción con certeza 100% (Regla #65): lo dudoso queda en Revisión Manual."""
    asunto = _dec(msg.get("Subject"))
    cuerpo = _texto_msg(msg)
    texto = f"{asunto}\n{cuerpo}"
    candidatos = []
    for h in ("From", "To", "Cc", "Reply-To"):
        candidatos += getaddresses([_dec(msg.get(h)) or ""])
    email_c, nombre = "", ""
    for nom, addr in candidatos:
        if _email_externo(addr):
            email_c = addr.strip().lower()
            nombre = (nom or "").strip()
            break
    if not email_c:
        for e in EMAIL_RE.findall(cuerpo):
            if _email_externo(e):
                email_c = e.strip().lower()
                break
    if not email_c:
        return None  # REGLA DE HIERRO: sin email no entra
    revision = []
    rut = ""
    for m in RUT_RE.finditer(texto):
        cand = f"{m.group(1)}-{m.group(2)}"
        if validar_rut_chileno(cand):
            rut = _fmt_rut(cand)
            break
        revision.append(f"RUT inválido detectado: {cand}")
    if not nombre:
        mm = re.search(r"Estimad[oa]s?\s+(?:Sr\.?a?\.?\s+)?([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})", cuerpo)
        if mm:
            nombre = mm.group(1).strip()
        else:
            revision.append("Nombre no identificable con certeza")
    inmo = (INMO_RE.search(texto) or [None, ""])[1] if INMO_RE.search(texto) else ""
    proy = (PROY_RE.search(texto) or [None, ""])[1] if PROY_RE.search(texto) else ""
    ciudad = next((c.title() for c in CIUDADES if c in texto.lower()), "")
    fono_m = FONO_RE.search(texto)
    try:
        fecha = parsedate_to_datetime(msg.get("Date")).isoformat() if msg.get("Date") else ""
    except Exception:
        fecha = ""
    return {"email": email_c, "nombre": (nombre or "").upper()[:80], "rut": rut,
            "inmobiliaria": (inmo or "").strip().upper()[:40], "proyecto": (proy or "").strip().upper()[:40],
            "ciudad": ciudad, "telefono": fono_m.group(0).strip() if fono_m else "",
            "revision_manual": bool(revision), "motivos_revision": revision,
            "fecha_correo": fecha, "asunto": asunto[:120]}


def _leer_bloque(desde_idx, cantidad=BLOQUE):
    """Lee un bloque de correos del buzón gerardo.ext (sincrónico, para to_thread)."""
    acc = next((a for a in _mail.ACCOUNTS if "gerardo.ext" in a["user"]), None)
    if not acc:
        acc = next((a for a in _mail.ACCOUNTS if a["rol"] == "secundaria"), None)
    if not acc:
        return None, 0, []
    m = _mail._connect(acc)
    m.select("INBOX", readonly=True)
    typ, data = m.search(None, "ALL")
    ids = data[0].split() if data and data[0] else []
    total = len(ids)
    bloque = ids[desde_idx:desde_idx + cantidad]
    mensajes = []
    for num in bloque:
        try:
            typ, d = m.fetch(num, "(BODY.PEEK[])")
            if d and isinstance(d[0], tuple):
                mensajes.append(email.message_from_bytes(d[0][1]))
        except Exception:
            continue
    m.logout()
    return acc["user"], total, mensajes


async def historia_loop():
    """MOTOR DE RASTREO RESUMIBLE: bloques de 100 con punto de control persistente."""
    await asyncio.sleep(90)
    while True:
        try:
            cfg = await db.config.find_one({"_key": "historia_checkpoint"}) or {}
            if not cfg.get("activo"):
                await asyncio.sleep(60)
                continue
            idx = int(cfg.get("indice") or 0)
            cuenta, total, mensajes = await asyncio.to_thread(_leer_bloque, idx)
            if cuenta is None:
                await asyncio.sleep(300)
                continue
            if idx >= total:
                await db.config.update_one({"_key": "historia_checkpoint"},
                                           {"$set": {"completado": True, "activo": False,
                                                     "total_correos": total, "ultima": _now()}}, upsert=True)
                logging.info(f"📚 Historia: minado COMPLETO ({total} correos)")
                await asyncio.sleep(3600)
                continue
            nuevos = 0
            for msg in mensajes:
                reg = _extraer(msg)
                if not reg:
                    continue
                mejor = await _desde_bodega(reg["email"], reg["rut"], reg["nombre"])
                if mejor:  # Regla #64: la Bodega es la verdad — no se pisa con lo minado
                    for k in ("nombre", "rut", "inmobiliaria", "proyecto"):
                        if mejor.get(k):
                            reg[k] = mejor[k]
                    reg["fuente"] = "bodega_dashai"
                else:
                    reg["fuente"] = "minado_imap"
                existe = await db.clientes_historicos.find_one({"email": reg["email"]})
                if existe:
                    upd = {k: v for k, v in reg.items()
                           if v not in ("", None, []) and not existe.get(k)}
                    if upd:
                        await db.clientes_historicos.update_one({"email": reg["email"]}, {"$set": upd})
                else:
                    reg["id"] = str(uuid.uuid4())
                    reg["creado"] = _now()
                    await db.clientes_historicos.insert_one(reg)
                    nuevos += 1
            await db.config.update_one({"_key": "historia_checkpoint"}, {"$set": {
                "indice": idx + BLOQUE, "total_correos": total, "cuenta": cuenta,
                "ultima": _now(), "completado": False},
                "$inc": {"procesados": len(mensajes), "rescatados_sesion": nuevos}}, upsert=True)
            logging.info(f"📚 Historia: bloque {idx}-{idx + BLOQUE} de {total} · {nuevos} cliente(s) nuevos")
            await asyncio.sleep(20)
        except Exception as e:
            logging.warning(f"historia loop: {e}")
            await asyncio.sleep(120)


@historia.get("/estado")
async def historia_estado():
    cfg = await db.config.find_one({"_key": "historia_checkpoint"}, {"_id": 0}) or {}
    total = await db.clientes_historicos.count_documents({})
    revision = await db.clientes_historicos.count_documents({"revision_manual": True})
    return {"rescatados": total, "revision_manual": revision, "checkpoint": cfg,
            "regla_hierro": "Sin Email el registro NO entra a la base de datos"}


@historia.post("/iniciar")
async def historia_iniciar():
    await db.config.update_one({"_key": "historia_checkpoint"},
                               {"$set": {"activo": True, "completado": False}}, upsert=True)
    return {"ok": True, "detalle": "Motor de rastreo activado — bloques de 100 con punto de control"}


@historia.post("/pausar")
async def historia_pausar():
    await db.config.update_one({"_key": "historia_checkpoint"}, {"$set": {"activo": False}}, upsert=True)
    return {"ok": True, "detalle": "Motor pausado — retomará exactamente donde quedó"}


@historia.get("/clientes")
async def historia_clientes(q: str = "", limite: int = 100):
    filtro = {}
    if q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        filtro = {"$or": [{k: rx} for k in ("nombre", "rut", "email", "inmobiliaria",
                                            "proyecto", "ciudad", "telefono")]}
    docs = await db.clientes_historicos.find(filtro, {"_id": 0}).sort("creado", -1).to_list(min(limite, 300))
    return {"clientes": docs, "total": len(docs)}


@historia.get("/export-xlsx")
async def historia_export():
    """EXPORTACIÓN SEGURA: Excel generado en memoria (streaming) — jamás toca el disco."""
    from openpyxl import Workbook
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Clientes Rescatados")
    ws.append(["Nombre", "RUT", "Email", "Teléfono", "Inmobiliaria", "Proyecto", "Ciudad",
               "Fuente", "Revisión Manual", "Fecha Correo"])
    async for c in db.clientes_historicos.find({}, {"_id": 0}).sort("nombre", 1):
        ws.append([c.get("nombre", ""), c.get("rut", ""), c.get("email", ""), c.get("telefono", ""),
                   c.get("inmobiliaria", ""), c.get("proyecto", ""), c.get("ciudad", ""),
                   c.get("fuente", ""), "SÍ" if c.get("revision_manual") else "NO",
                   (c.get("fecha_correo") or "")[:16]])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": 'attachment; filename="Base_Datos_Historica_CentralMutuos.xlsx"'})
