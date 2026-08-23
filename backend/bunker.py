"""BÚNKER DE ARCHIVOS: espejo GridFS de storage/ para persistencia entre reinicios y réplicas."""
import os
import logging
import threading
from pathlib import Path

from pymongo import MongoClient
import gridfs

ROOT = Path(__file__).parent / "storage"
SUBDIRS = ("clientes", "autocorreo", "proc", "sets_de_credito", "archivo_general")

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


def _escribir_con_mtime(g, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(g.read())
    mt = (g.metadata or {}).get("mtime")
    if mt:
        os.utime(dest, (mt, mt))


def restaurar_si_vacio():
    """Al arrancar: si el disco está vacío (pod nuevo/reinicio), restaura TODO desde GridFS."""
    fs, _db = _fs()
    clientes = ROOT / "clientes"
    if clientes.exists() and any(clientes.iterdir()):
        return 0
    n = 0
    for g in fs.find():
        try:
            _escribir_con_mtime(g, ROOT / g.filename)
            n += 1
        except Exception as e:
            logging.warning(f"bunker restore {g.filename}: {e}")
    logging.warning(f"🏦 BÚNKER: {n} archivo(s) restaurados desde GridFS al disco")
    return n


def restaurar_faltantes():
    """Cloud Sync: baja del GridFS los archivos que NO están en el disco local
    (sin exigir disco vacío). Devuelve la cantidad restaurada."""
    fs, _db = _fs()
    n = 0
    for g in fs.find():
        try:
            dest = ROOT / g.filename
            if dest.exists():
                continue
            _escribir_con_mtime(g, dest)
            n += 1
        except Exception as e:
            logging.warning(f"bunker faltante {g.filename}: {e}")
    return n


def sync_en_background():
    """Dispara sync_diff en un hilo daemon: nunca bloquea reloads ni el event loop."""
    threading.Thread(target=sync_diff, daemon=True).start()


def sync_diff():
    """Espejo disco -> GridFS: sube nuevos/cambiados. NUNCA borra entradas del
    almacenamiento en base de datos basándose en el disco local de un pod:
    GridFS es la FUENTE DE VERDAD. El borrado es solo explícito vía eliminar()."""
    if not _lock.acquire(blocking=False):
        return {"skipped": True}
    try:
        fs, db = _fs()
        files_col = db["bunker.files"]
        existentes = {d["filename"]: d for d in
                      files_col.find({}, {"filename": 1, "length": 1, "metadata": 1})}
        en_disco = set()
        subidos = 0
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
        return {"subidos": subidos, "eliminados": 0, "total_disco": len(en_disco)}
    finally:
        _lock.release()


def eliminar(path):
    """Borrado EXPLÍCITO e intencional: única vía para eliminar archivos del búnker
    (GridFS = fuente de verdad). Acepta ruta absoluta de archivo o carpeta bajo
    storage/; las rutas fuera del búnker son no-op. También limpia el disco local."""
    import re as _re
    import shutil as _sh
    try:
        p = Path(path)
        rel = p.relative_to(ROOT).as_posix() if p.is_absolute() else str(path).replace("\\", "/").strip("/")
    except ValueError:
        return 0
    if not rel or rel in SUBDIRS:
        pass
    fs, db = _fs()
    files_col = db["bunker.files"]
    n = 0
    for d in files_col.find({"filename": {"$regex": "^" + _re.escape(rel) + "(/|$)"}}, {"_id": 1}):
        try:
            fs.delete(d["_id"])
            n += 1
        except Exception:
            pass
    try:
        local = ROOT / rel
        if local.is_dir():
            _sh.rmtree(local, ignore_errors=True)
        elif local.exists():
            local.unlink()
    except Exception:
        pass
    if n:
        logging.info(f"🏦 BÚNKER: borrado explícito «{rel}» — {n} entrada(s) eliminadas de GridFS")
    return n


def eliminar_bg(path):
    """eliminar() en hilo daemon: no bloquea el event loop."""
    threading.Thread(target=eliminar, args=(str(path),), daemon=True).start()

