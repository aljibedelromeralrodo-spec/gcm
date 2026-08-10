"""BÚNKER DE RESPALDO CLOUD (Emergent Object Store) — espejo pasivo y silencioso.
La operación diaria sigue 100% en disco local; la nube es solo un seguro.
"""
import os
import json
import hashlib
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

import requests
from pymongo import MongoClient

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "central-mutuos"
MANIFIESTO_PATH = f"{APP_NAME}/manifiesto.json"

ROOT = Path(__file__).parent / "storage"
SUBDIRS = ("clientes", "autocorreo", "sets_de_credito", "boveda_dashai", "archivo_general")
# Colecciones DashAI cuyo registro se respalda como snapshot JSON
DASHAI_COLECCIONES = ("criterios", "patrones_aprendidos", "dashai_eventos", "aprendizaje_notas")

_storage_key = None
_cli = None
_lock = threading.Lock()


def _db():
    global _cli
    if _cli is None:
        _cli = MongoClient(os.environ["MONGO_URL"])
    return _cli[os.environ["DB_NAME"]]


def init_storage(force=False):
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key


def put_object(path, data, content_type="application/octet-stream"):
    key = init_storage()
    resp = requests.put(f"{STORAGE_URL}/objects/{path}",
                        headers={"X-Storage-Key": key, "Content-Type": content_type},
                        data=data, timeout=120)
    if resp.status_code == 404:
        key = init_storage(force=True)
        resp = requests.put(f"{STORAGE_URL}/objects/{path}",
                            headers={"X-Storage-Key": key, "Content-Type": content_type},
                            data=data, timeout=120)
    resp.raise_for_status()
    return resp.json()


def get_object(path):
    key = init_storage()
    resp = requests.get(f"{STORAGE_URL}/objects/{path}",
                        headers={"X-Storage-Key": key}, timeout=120)
    if resp.status_code == 404:
        key = init_storage(force=True)
        resp = requests.get(f"{STORAGE_URL}/objects/{path}",
                            headers={"X-Storage-Key": key}, timeout=120)
    resp.raise_for_status()
    return resp.content


def _mime(nombre):
    low = nombre.lower()
    if low.endswith(".pdf"):
        return "application/pdf"
    if low.endswith(".csv"):
        return "text/csv"
    if low.endswith(".json"):
        return "application/json"
    return "application/octet-stream"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _walk():
    for sub in SUBDIRS:
        base = ROOT / sub
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file():
                yield f"{sub}/{p.relative_to(base).as_posix()}", p


def _snapshot_dashai(db):
    """Registro DashAI como JSON (config + colecciones de aprendizaje)."""
    data = {"generado_en": _now()}
    for c in DASHAI_COLECCIONES:
        try:
            data[c] = [{k: v for k, v in d.items() if k != "_id"}
                       for d in db[c].find().limit(2000)]
        except Exception:
            data[c] = []
    try:
        data["config"] = [{k: v for k, v in d.items() if k != "_id"}
                          for d in db.config.find({"_key": {"$exists": True}})]
    except Exception:
        data["config"] = []
    return json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")


def escanear_y_respaldar():
    """REGLA DE ESPEJO: sube a la nube todo archivo nuevo o modificado + snapshot DashAI.
    Corre en segundo plano (thread) — nunca bloquea la operación local."""
    if not _lock.acquire(blocking=False):
        return {"skip": "respaldo ya en curso"}
    try:
        db = _db()
        manifest = {m["rel"]: m for m in db.cloud_backups.find({}, {"_id": 0})}
        subidos, errores = 0, 0
        for rel, p in _walk():
            try:
                st = p.stat()
            except OSError:
                continue
            prev = manifest.get(rel)
            if prev and prev.get("size") == st.st_size and prev.get("mtime") == int(st.st_mtime):
                continue
            try:
                cloud_path = f"{APP_NAME}/storage/{rel}"
                res = put_object(cloud_path, p.read_bytes(), _mime(p.name))
                entry = {"rel": rel, "cloud_path": res.get("path", cloud_path),
                         "size": st.st_size, "mtime": int(st.st_mtime),
                         "respaldado_en": _now()}
                db.cloud_backups.replace_one({"rel": rel}, entry, upsert=True)
                manifest[rel] = entry
                subidos += 1
            except Exception as e:
                errores += 1
                logging.warning(f"cloud_bunker {rel}: {e}")
                if errores >= 5:
                    break
        # Registro DashAI (snapshot JSON, solo si cambió)
        try:
            snap = _snapshot_dashai(db)
            h = hashlib.sha256(snap).hexdigest()
            st_doc = db.config.find_one({"_key": "cloud_bunker"}) or {}
            if st_doc.get("dashai_hash") != h:
                put_object(f"{APP_NAME}/dashai/registros_dashai.json", snap, "application/json")
                db.config.update_one({"_key": "cloud_bunker"},
                                     {"$set": {"dashai_hash": h}}, upsert=True)
                subidos += 1
        except Exception as e:
            errores += 1
            logging.warning(f"cloud_bunker dashai: {e}")
        # Manifiesto en la nube (permite recuperación total sin Mongo local)
        try:
            if subidos:
                mani = json.dumps({"generado_en": _now(),
                                   "archivos": list(manifest.values())},
                                  ensure_ascii=False, default=str).encode("utf-8")
                put_object(MANIFIESTO_PATH, mani, "application/json")
        except Exception as e:
            errores += 1
            logging.warning(f"cloud_bunker manifiesto: {e}")
        estado = "SINCRONIZADO" if errores == 0 else ("PARCIAL" if subidos else "ERROR")
        upd = {"estado": estado, "objetos": len(manifest),
               "subidos_ultimo": subidos, "errores_ultimo": errores,
               "revisado_en": _now()}
        if subidos or not (db.config.find_one({"_key": "cloud_bunker"}) or {}).get("ultima_copia"):
            upd["ultima_copia"] = _now()
        db.config.update_one({"_key": "cloud_bunker"}, {"$set": upd}, upsert=True)
        return {"estado": estado, "subidos": subidos, "errores": errores,
                "objetos": len(manifest)}
    finally:
        _lock.release()
