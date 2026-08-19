"""FILE & MEDIA STORAGE (Emergent Object Storage) — almacenamiento dual de documentos.
El disco local sigue operando el motor OCR/PDF; el storage integrado es la fuente
persistente y visualizable, organizada por operación/RUT y bandeja sin clasificar.
"""
import os
import uuid
import asyncio
import logging
import mimetypes
from datetime import datetime, timezone

import requests
from fastapi import APIRouter, HTTPException, Request, Response
from database import db

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "central-mutuos-docs"

_storage_key = None
storage_router = APIRouter(prefix="/storage")

_mcli = None


def _metric(**inc):
    """Contadores de eficiencia (auditoría semanal): toda lectura al storage queda medida."""
    global _mcli
    try:
        from pymongo import MongoClient
        if _mcli is None:
            _mcli = MongoClient(os.environ["MONGO_URL"])
        _mcli[os.environ["DB_NAME"]].config.update_one(
            {"_key": "storage_metrics"}, {"$inc": inc}, upsert=True)
    except Exception:
        pass


def _init(force=False):
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key


def _put(path, data, content_type):
    key = _init()
    r = requests.put(f"{STORAGE_URL}/objects/{path}",
                     headers={"X-Storage-Key": key, "Content-Type": content_type},
                     data=data, timeout=120)
    if r.status_code == 404:
        key = _init(force=True)
        r = requests.put(f"{STORAGE_URL}/objects/{path}",
                         headers={"X-Storage-Key": key, "Content-Type": content_type},
                         data=data, timeout=120)
    r.raise_for_status()
    return r.json()


def _get(path):
    key = _init()
    _metric(gets=1)
    r = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    if r.status_code == 404:
        key = _init(force=True)
        r = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "application/octet-stream")


def _mime(nombre):
    return mimetypes.guess_type(nombre or "")[0] or "application/octet-stream"


def _now():
    return datetime.now(timezone.utc).isoformat()


async def registrar_documento(data, filename, folder_doc, origen, subido_por="", rol="", rel=""):
    """Sube el documento al storage organizado por operación/RUT y registra en DB (dual write)."""
    try:
        rut = (folder_doc.get("rut") or "").replace(".", "").replace(" ", "") or "sin-rut"
        oper = str(folder_doc.get("nro_operacion") or "") or f"fid-{folder_doc.get('id')}"
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
        path = f"{APP_NAME}/operacion_{oper}/{rut}/{uuid.uuid4()}.{ext}"
        ct = _mime(filename)
        res = await asyncio.to_thread(_put, path, data, ct)
        reg = {"id": str(uuid.uuid4()), "storage_path": res["path"], "nombre_archivo": filename,
               "content_type": ct, "size": res.get("size") or len(data), "origen": origen,
               "folder_id": folder_doc.get("id"), "cliente": folder_doc.get("nombre") or "",
               "rut": folder_doc.get("rut") or "", "nro_operacion": str(folder_doc.get("nro_operacion") or ""),
               "broker_codigo": folder_doc.get("broker_codigo") or "", "ruta_local": rel,
               "subido_por": subido_por, "rol_subida": rol, "subido_en": _now(), "is_deleted": False}
        await db.storage_docs.insert_one(dict(reg))
        return reg
    except Exception as e:
        logging.warning(f"storage documento {filename}: {e}")
        return None


async def registrar_sin_clasificar(data, filename, bandeja_id, subido_por=""):
    """Documentos sin operación asignada → carpeta separada 'sin_clasificar' del storage."""
    try:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
        path = f"{APP_NAME}/sin_clasificar/{uuid.uuid4()}.{ext}"
        ct = _mime(filename)
        res = await asyncio.to_thread(_put, path, data, ct)
        reg = {"id": str(uuid.uuid4()), "storage_path": res["path"], "nombre_archivo": filename,
               "content_type": ct, "size": res.get("size") or len(data), "origen": "sin_clasificar",
               "bandeja_id": bandeja_id, "folder_id": "", "rut": "", "nro_operacion": "",
               "broker_codigo": "", "subido_por": subido_por, "subido_en": _now(), "is_deleted": False}
        await db.storage_docs.insert_one(dict(reg))
        return reg
    except Exception as e:
        logging.warning(f"storage sin clasificar {filename}: {e}")
        return None


# ═══ CONTROL DE ACCESO POR ROL ═══
def _claims(request):
    return getattr(request.state, "user", {}) or {}


def _puede_ver(claims, d):
    rol, sub = claims.get("rol") or "", claims.get("sub") or ""
    if rol in ("admin", "maestro", "contralor"):
        return True
    if d.get("origen") == "sin_clasificar":
        return rol == "administracion"
    if rol in ("gerencia", "administracion", "postventa"):
        return True
    if rol in ("broker", "ejecutivo"):
        return bool(d.get("broker_codigo")) and d.get("broker_codigo") == sub
    return False


@storage_router.get("/docs")
async def storage_docs_list(request: Request, fid: str = "", bandeja: str = ""):
    c = _claims(request)
    rol, sub = c.get("rol") or "", c.get("sub") or ""
    q = {"is_deleted": False}
    if bandeja:
        if rol not in ("admin", "maestro", "administracion", "contralor"):
            raise HTTPException(status_code=403, detail="La bandeja sin clasificar es visible solo para Administración, Admin y Contralor")
        q["origen"] = "sin_clasificar"
    else:
        q["origen"] = {"$ne": "sin_clasificar"}
        if fid:
            q["folder_id"] = fid
        if rol in ("broker", "ejecutivo"):
            q["broker_codigo"] = sub
        elif rol not in ("admin", "maestro", "contralor", "gerencia", "administracion", "postventa"):
            raise HTTPException(status_code=403, detail="Su rol no tiene acceso a los documentos almacenados")
    docs = await db.storage_docs.find(q, {"_id": 0, "storage_path": 0}).sort("subido_en", -1).to_list(300)
    return {"documentos": docs, "total": len(docs)}


@storage_router.get("/ver/{doc_id}")
async def storage_ver(doc_id: str, request: Request):
    """Visualización INLINE del documento (sin descarga) con control de acceso por rol."""
    d = await db.storage_docs.find_one({"$or": [{"id": doc_id}, {"bandeja_id": doc_id}],
                                        "is_deleted": False})
    if not d:
        raise HTTPException(status_code=404, detail="Documento no encontrado en el almacenamiento")
    if not _puede_ver(_claims(request), d):
        raise HTTPException(status_code=403, detail="Su rol no tiene permisos para ver este documento")
    _metric(gets_demanda=1)
    try:
        data, ct = await asyncio.to_thread(_get, d["storage_path"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No fue posible recuperar el documento del storage: {str(e)[:120]}")
    fn = (d.get("nombre_archivo") or "documento").replace('"', "")
    return Response(content=data, media_type=d.get("content_type") or ct,
                    headers={"Content-Disposition": f'inline; filename="{fn}"',
                             "Cache-Control": "private, max-age=300"})
