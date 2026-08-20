"""📦 IMPORTADOR .MBOX DE GRAN TAMAÑO (hasta 100 GB) — streaming por fragmentos.
El navegador sube el archivo en trozos (~4 MB). El servidor NUNCA almacena el archivo
completo: mantiene solo el remanente del último mensaje incompleto, parsea cada correo
terminado y lo guarda en db.mbox_correos. Progreso en db.mbox_sesiones.
"""
import re
import uuid
import email
import email.utils
import email.header
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from database import db

mbox = APIRouter(prefix="/mbox")

ROLES = ("admin", "maestro", "administracion", "gerencia")
TMP_DIR = Path(__file__).parent / "storage" / "mbox_tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)
MAX_REMANENTE = 64 * 1024 * 1024  # mensaje individual > 64 MB se omite (protección de disco)
MAX_TOTAL = 100 * 1024 * 1024 * 1024  # 100 GB


def _exigir(request):
    c = getattr(request.state, "user", {}) or {}
    if c.get("rol") not in ROLES:
        raise HTTPException(status_code=403, detail="Su rol no tiene acceso al importador .mbox")
    return c


def _now():
    return datetime.now(timezone.utc).isoformat()


def _dec(v):
    try:
        partes = email.header.decode_header(v or "")
        return "".join(p.decode(enc or "utf-8", "replace") if isinstance(p, bytes) else p
                       for p, enc in partes).strip()
    except Exception:
        return str(v or "").strip()


def _cuerpo_texto(msg):
    try:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain" and not part.get_filename():
                    raw = part.get_payload(decode=True) or b""
                    return raw.decode(part.get_content_charset() or "utf-8", "replace")[:20000]
            for part in msg.walk():
                if part.get_content_type() == "text/html" and not part.get_filename():
                    raw = part.get_payload(decode=True) or b""
                    txt = re.sub(r"<[^>]+>", " ", raw.decode(part.get_content_charset() or "utf-8", "replace"))
                    return re.sub(r"\s+", " ", txt)[:20000]
            return ""
        raw = msg.get_payload(decode=True) or b""
        return raw.decode(msg.get_content_charset() or "utf-8", "replace")[:20000]
    except Exception:
        return ""


def _parse_mensaje(raw, sid):
    """raw incluye la línea de sobre 'From ...' al inicio."""
    i = raw.find(b"\n")
    cuerpo_raw = raw[i + 1:] if i >= 0 else raw
    try:
        msg = email.message_from_bytes(cuerpo_raw)
    except Exception:
        return None
    adjuntos = []
    try:
        for part in msg.walk():
            fn = part.get_filename()
            if fn:
                payload = part.get_payload(decode=False) or ""
                adjuntos.append({"nombre": _dec(fn), "tamano_aprox": len(payload)})
    except Exception:
        pass
    fecha = ""
    try:
        dt = email.utils.parsedate_to_datetime(msg.get("Date") or "")
        if dt:
            fecha = dt.isoformat()
    except Exception:
        pass
    mid = (msg.get("Message-ID") or "").strip() or f"sin-id-{uuid.uuid4()}"
    return {"id": str(uuid.uuid4()), "sesion": sid, "message_id": mid,
            "de": _dec(msg.get("From")), "para": _dec(msg.get("To")),
            "cc": _dec(msg.get("Cc")), "asunto": _dec(msg.get("Subject")),
            "fecha": fecha, "cuerpo": _cuerpo_texto(msg),
            "adjuntos": adjuntos, "n_adjuntos": len(adjuntos), "importado": _now()}


async def _guardar_lote(docs):
    if not docs:
        return 0
    try:
        r = await db.mbox_correos.insert_many(docs, ordered=False)
        return len(r.inserted_ids)
    except Exception as e:
        # duplicados por índice único de message_id: contar los que sí entraron
        detalles = getattr(e, "details", {}) or {}
        return len(docs) - len(detalles.get("writeErrors") or [])


@mbox.post("/iniciar")
async def mbox_iniciar(payload: dict, request: Request):
    c = _exigir(request)
    total = int(payload.get("total_bytes") or 0)
    if total <= 0 or total > MAX_TOTAL:
        raise HTTPException(status_code=400, detail="Tamaño inválido (máximo 100 GB)")
    await db.mbox_correos.create_index("message_id", unique=True, sparse=True)
    sid = str(uuid.uuid4())
    await db.mbox_sesiones.insert_one({
        "sid": sid, "archivo": (payload.get("filename") or "archivo.mbox")[:200],
        "total_bytes": total, "bytes_recibidos": 0, "correos_importados": 0,
        "duplicados": 0, "omitidos": 0, "estado": "subiendo",
        "iniciado": _now(), "actualizado": _now(), "por": c.get("sub")})
    (TMP_DIR / f"{sid}.rem").write_bytes(b"")
    return {"sid": sid, "chunk_bytes": 4 * 1024 * 1024}


async def _procesar_buffer(sid, data, final=False):
    """Corta el buffer en mensajes completos por el separador mbox '\\nFrom '."""
    importados, omitidos, restante = 0, 0, data
    docs = []
    partes = data.split(b"\nFrom ")
    if final:
        cuerpo_partes, restante = partes, b""
    else:
        cuerpo_partes, restante = partes[:-1], (b"\nFrom " + partes[-1] if len(partes) > 1 else data)
    for k, p in enumerate(cuerpo_partes):
        raw = p if (k == 0 and p.startswith(b"From ")) else (b"From " + p)
        if k == 0 and not p.startswith(b"From "):
            continue  # fragmento inicial sin sobre (continuación corrupta)
        d = _parse_mensaje(raw, sid)
        if d:
            docs.append(d)
        else:
            omitidos += 1
        if len(docs) >= 200:
            importados += await _guardar_lote(docs)
            docs = []
    importados += await _guardar_lote(docs)
    if len(restante) > MAX_REMANENTE:
        omitidos += 1
        restante = b""
    return importados, omitidos, restante


@mbox.post("/chunk/{sid}")
async def mbox_chunk(sid: str, request: Request):
    _exigir(request)
    ses = await db.mbox_sesiones.find_one({"sid": sid})
    if not ses or ses.get("estado") not in ("subiendo",):
        raise HTTPException(status_code=404, detail="Sesión no encontrada o ya finalizada")
    chunk = await request.body()
    if not chunk:
        raise HTTPException(status_code=400, detail="Fragmento vacío")
    rem_path = TMP_DIR / f"{sid}.rem"
    data = (rem_path.read_bytes() if rem_path.exists() else b"") + chunk
    if ses["bytes_recibidos"] == 0 and data.startswith(b"From "):
        data = b"\n" + data  # normalizar primer sobre
    importados, omitidos, restante = await _procesar_buffer(sid, data)
    rem_path.write_bytes(restante)
    ses2 = await db.mbox_sesiones.find_one_and_update(
        {"sid": sid},
        {"$inc": {"bytes_recibidos": len(chunk), "correos_importados": importados, "omitidos": omitidos},
         "$set": {"actualizado": _now()}}, return_document=True)
    pct = round(min(100, ses2["bytes_recibidos"] / max(1, ses2["total_bytes"]) * 100), 2)
    return {"ok": True, "pct": pct, "bytes_recibidos": ses2["bytes_recibidos"],
            "correos_importados": ses2["correos_importados"], "omitidos": ses2["omitidos"]}


@mbox.post("/finalizar/{sid}")
async def mbox_finalizar(sid: str, request: Request):
    _exigir(request)
    ses = await db.mbox_sesiones.find_one({"sid": sid})
    if not ses:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    rem_path = TMP_DIR / f"{sid}.rem"
    data = rem_path.read_bytes() if rem_path.exists() else b""
    importados, omitidos, _ = await _procesar_buffer(sid, data, final=True)
    if rem_path.exists():
        rem_path.unlink()
    ses2 = await db.mbox_sesiones.find_one_and_update(
        {"sid": sid},
        {"$inc": {"correos_importados": importados, "omitidos": omitidos},
         "$set": {"estado": "completado", "actualizado": _now()}}, return_document=True)
    await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "mbox_importado", "leida": False,
                                 "mensaje": f"📦 Archivo .mbox '{ses2['archivo']}' procesado: {ses2['correos_importados']} correos importados",
                                 "fecha": _now()})
    return {"ok": True, "correos_importados": ses2["correos_importados"],
            "omitidos": ses2["omitidos"], "estado": "completado"}


@mbox.post("/cancelar/{sid}")
async def mbox_cancelar(sid: str, request: Request):
    _exigir(request)
    rem = TMP_DIR / f"{sid}.rem"
    if rem.exists():
        rem.unlink()
    await db.mbox_sesiones.update_one({"sid": sid}, {"$set": {"estado": "cancelado", "actualizado": _now()}})
    return {"ok": True}


@mbox.get("/estado/{sid}")
async def mbox_estado(sid: str, request: Request):
    _exigir(request)
    ses = await db.mbox_sesiones.find_one({"sid": sid}, {"_id": 0})
    if not ses:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    ses["pct"] = round(min(100, ses["bytes_recibidos"] / max(1, ses["total_bytes"]) * 100), 2)
    return ses


@mbox.get("/sesiones")
async def mbox_sesiones(request: Request):
    _exigir(request)
    out = [s async for s in db.mbox_sesiones.find({}, {"_id": 0}).sort("iniciado", -1).limit(20)]
    total = await db.mbox_correos.estimated_document_count()
    return {"sesiones": out, "correos_en_base": total}
