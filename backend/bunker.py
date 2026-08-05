"""BÚNKER DE ARCHIVOS: espejo GridFS de storage/ para persistencia entre reinicios y réplicas."""
import os
import logging
import threading
from pathlib import Path

from pymongo import MongoClient
import gridfs

ROOT = Path(__file__).parent / "storage"
SUBDIRS = ("clientes", "autocorreo", "proc", "set_credito")

_cli = None
_lock = threading.Lock()


def _fs():
    global _cli
    if _cli is None:
        _cli = MongoClient(os.environ["MONGO_URL"])
    db = _cli[os.environ["DB_NAME"]]
    return gridfs.GridFS(db, collection="bunker"), db


def _walk():
    for sub in SUBDIRS:
        base = ROOT / sub
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file():
                yield f"{sub}/{p.relative_to(base).as_posix()}", p


def restaurar_si_vacio():
    """Al arrancar: si el disco está vacío (pod nuevo/reinicio), restaura TODO desde GridFS."""
    fs, _db = _fs()
    clientes = ROOT / "clientes"
    if clientes.exists() and any(clientes.iterdir()):
        return 0
    n = 0
    for g in fs.find():
        try:
            dest = ROOT / g.filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(g.read())
            n += 1
        except Exception as e:
            logging.warning(f"bunker restore {g.filename}: {e}")
    logging.warning(f"🏦 BÚNKER: {n} archivo(s) restaurados desde GridFS al disco")
    return n


def sync_diff():
    """Espejo disco -> GridFS: sube nuevos/cambiados y elimina los borrados (el disco manda)."""
    if not _lock.acquire(blocking=False):
        return {"skipped": True}
    try:
        fs, db = _fs()
        files_col = db["bunker.files"]
        existentes = {d["filename"]: d for d in
                      files_col.find({}, {"filename": 1, "length": 1, "metadata": 1})}
        en_disco = set()
        subidos = eliminados = 0
        for rel, p in _walk():
            en_disco.add(rel)
            try:
                st = p.stat()
                prev = existentes.get(rel)
                if (prev and prev.get("length") == st.st_size
                        and (prev.get("metadata") or {}).get("mtime") == int(st.st_mtime)):
                    continue
                if prev:
                    fs.delete(prev["_id"])
                with open(p, "rb") as fh:
                    fs.put(fh, filename=rel, metadata={"mtime": int(st.st_mtime)})
                subidos += 1
            except Exception as e:
                logging.warning(f"bunker sync {rel}: {e}")
        for rel, d in existentes.items():
            if rel not in en_disco:
                try:
                    fs.delete(d["_id"])
                    eliminados += 1
                except Exception:
                    pass
        return {"subidos": subidos, "eliminados": eliminados, "total_disco": len(en_disco)}
    finally:
        _lock.release()
