"""BÚNKER DE ARCHIVOS — Emergent Object Storage como almacenamiento durable principal.

- Fuente de verdad: Emergent Object Store (manifiesto en Mongo `objstore_files`).
- GridFS queda SOLO como respaldo de lectura durante la migración (no se escribe más).
- El disco local es únicamente caché de trabajo efímera (OCR/preview); todo lo que se
  escribe se espeja de inmediato al Object Store y se restaura desde ahí tras un redespliegue.
"""
import os
import re
import logging
import threading
from pathlib import Path

import requests
from pymongo import MongoClient
import gridfs

ROOT = Path(__file__).parent / "storage"
SUBDIRS = ("clientes", "autocorreo", "sets_de_credito", "archivo_general", "brokers")
# ⚠ 'proc' EXCLUIDO (27-08): las copias de trabajo de la cola NO van al búnker —
# llenaban el disco en cada arranque al restaurarse; los documentos finales viven en 'clientes'.
APP_PREFIX = "central-mutuos"

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"

_cli = None
_lock = threading.Lock()
_mig_lock = threading.Lock()
_storage_key = None


def _db():
    global _cli
    if _cli is None:
        _cli = MongoClient(os.environ["MONGO_URL"])
    return _cli[os.environ["DB_NAME"]]


def _manifest():
    return _db()["objstore_files"]


def _gridfs_legacy():
    return gridfs.GridFS(_db(), collection="bunker")


def _skey(force=False):
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    r = requests.post(f"{STORAGE_URL}/init",
                      json={"emergent_key": os.environ.get("EMERGENT_LLM_KEY")}, timeout=30)
    r.raise_for_status()
    _storage_key = r.json()["storage_key"]
    return _storage_key


def _put(rel, data):
    path = f"{APP_PREFIX}/{rel}"
    r = requests.put(f"{STORAGE_URL}/objects/{path}",
                     headers={"X-Storage-Key": _skey(),
                              "Content-Type": "application/octet-stream"},
                     data=data, timeout=180)
    if r.status_code == 404:
        r = requests.put(f"{STORAGE_URL}/objects/{path}",
                         headers={"X-Storage-Key": _skey(force=True),
                                  "Content-Type": "application/octet-stream"},
                         data=data, timeout=180)
    r.raise_for_status()
    return r.json()


def _get(rel):
    path = f"{APP_PREFIX}/{rel}"
    r = requests.get(f"{STORAGE_URL}/objects/{path}",
                     headers={"X-Storage-Key": _skey()}, timeout=120)
    if r.status_code == 404:
        r = requests.get(f"{STORAGE_URL}/objects/{path}",
                         headers={"X-Storage-Key": _skey(force=True)}, timeout=120)
        if r.status_code == 404:
            return None
    r.raise_for_status()
    return r.content


def _walk():
    for sub in SUBDIRS:
        base = ROOT / sub
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file():
                yield f"{sub}/{p.relative_to(base).as_posix()}", p


def _escribir(data, dest, mtime=None):
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    if mtime:
        os.utime(dest, (mtime, mtime))


def _bajar_entry(rel, mtime=None):
    """Baja un archivo al disco: primero Object Store; si no está, GridFS legado."""
    data = None
    try:
        data = _get(rel)
    except Exception as e:
        logging.warning(f"objstore get {rel}: {e}")
    if data is None:
        try:
            g = _gridfs_legacy().find_one({"filename": rel})
            if g is not None:
                data = g.read()
                mtime = mtime or (g.metadata or {}).get("mtime")
        except Exception as e:
            logging.warning(f"gridfs get {rel}: {e}")
    if data is None:
        return False
    _escribir(data, ROOT / rel, mtime)
    return True


def _entradas(prefijo=""):
    """Entradas conocidas del almacén durable: manifiesto objstore + GridFS legado."""
    vistos = {}
    q = {"is_deleted": {"$ne": True}}
    if prefijo:
        q["filename"] = {"$regex": "^" + re.escape(prefijo) + "(/|$)"}
    for d in _manifest().find(q, {"filename": 1, "length": 1, "mtime": 1}):
        vistos[d["filename"]] = {"length": d.get("length"), "mtime": d.get("mtime")}
    try:
        qg = {"filename": {"$regex": "^" + re.escape(prefijo) + "(/|$)"}} if prefijo else {}
        for d in _db()["bunker.files"].find(qg, {"filename": 1, "length": 1, "metadata": 1}):
            vistos.setdefault(d["filename"], {"length": d.get("length"),
                                              "mtime": (d.get("metadata") or {}).get("mtime")})
    except Exception:
        pass
    return vistos


def _archivados():
    """Prefijos archivados: existen solo en el almacén durable, sin copia local."""
    try:
        doc = _db()["config"].find_one({"_key": "bunker_archivados"}) or {}
        return set(doc.get("prefijos") or [])
    except Exception:
        return set()


def _desarchivar(rel):
    try:
        _db()["config"].update_one({"_key": "bunker_archivados"}, {"$pull": {"prefijos": rel}})
    except Exception:
        pass


def archivar_prefijo(rel_prefijo):
    """LIMPIEZA PROFUNDA: verifica que TODO el prefijo esté respaldado en el Object Store
    (sube lo que falte), borra la copia local y lo excluye del cloud-sync.
    Se restaura solo al abrir la carpeta (restaurar_prefijo)."""
    import shutil
    rel = str(rel_prefijo).replace("\\", "/").strip("/")
    base = ROOT / rel
    if not base.exists():
        return {"ok": False, "motivo": "no existe local"}
    conocidos = _entradas(rel)
    subidos = 0
    for p in base.rglob("*"):
        if not p.is_file():
            continue
        r = f"{rel}/{p.relative_to(base).as_posix()}"
        meta = conocidos.get(r)
        if not meta or meta.get("length") != p.stat().st_size:
            subir_archivo(p)
            subidos += 1
    # re-verificación
    conocidos = _entradas(rel)
    for p in base.rglob("*"):
        if p.is_file():
            r = f"{rel}/{p.relative_to(base).as_posix()}"
            if r not in conocidos:
                return {"ok": False, "motivo": f"sin respaldo: {r}"}
    liberado = sum(p.stat().st_size for p in base.rglob("*") if p.is_file())
    shutil.rmtree(base)
    _db()["config"].update_one({"_key": "bunker_archivados"},
                               {"$addToSet": {"prefijos": rel}}, upsert=True)
    return {"ok": True, "subidos": subidos, "liberado": liberado}


MAX_FALLOS_SEGUIDOS = 15


def restaurar_si_vacio():
    """Al arrancar: si el disco está vacío (pod nuevo/redespliegue), restaura TODO.
    Cortacircuito: si el almacén durable falla repetidamente, se pospone (Regla #13 on-demand)."""
    clientes = ROOT / "clientes"
    if clientes.exists() and any(clientes.iterdir()):
        return 0
    n, fallos = 0, 0
    arch = _archivados()
    for rel, meta in _entradas().items():
        if rel.startswith("proc/") or any(rel.startswith(a + "/") or rel == a for a in arch):
            continue
        if _bajar_entry(rel, meta.get("mtime")):
            n += 1
            fallos = 0
        else:
            fallos += 1
            if fallos >= MAX_FALLOS_SEGUIDOS:
                logging.warning(f"🏦 BÚNKER: almacén durable no disponible ({fallos} fallos seguidos) — "
                                "restauración masiva pospuesta, se sirve on-demand (Regla #13)")
                break
    logging.warning(f"🏦 BÚNKER: {n} archivo(s) restaurados del almacén durable al disco")
    return n


def restaurar_faltantes():
    """Cloud Sync: baja los archivos que NO están en el disco local."""
    n, fallos = 0, 0
    arch = _archivados()
    for rel, meta in _entradas().items():
        if rel.startswith("proc/") or any(rel.startswith(a + "/") or rel == a for a in arch):
            continue
        dest = ROOT / rel
        if dest.exists():
            continue
        if _bajar_entry(rel, meta.get("mtime")):
            n += 1
            fallos = 0
        else:
            fallos += 1
            if fallos >= MAX_FALLOS_SEGUIDOS:
                logging.warning(f"🏦 BÚNKER faltantes: almacén durable no disponible ({fallos} fallos seguidos) — "
                                "sync pospuesto al próximo ciclo")
                break
    return n


def restaurar_prefijo(rel_prefijo):
    """Restauración DIRIGIDA: solo lo que cuelga de un prefijo (ej: 'proc/<qid>')."""
    rel = str(rel_prefijo).replace("\\", "/").strip("/")
    if not rel:
        return 0
    _desarchivar(rel)
    n = 0
    for r, meta in _entradas(rel).items():
        dest = ROOT / r
        if dest.exists() and dest.stat().st_size == meta.get("length"):
            continue
        if _bajar_entry(r, meta.get("mtime")):
            n += 1
    if n:
        logging.info(f"🏦 BÚNKER: {n} archivo(s) restaurados para «{rel}»")
    return n


def subir_archivo(p):
    """Persiste UN archivo del disco en el Object Store durable (manifiesto incluido)."""
    p = Path(p)
    rel = p.relative_to(ROOT).as_posix()
    st = p.stat()
    _put(rel, p.read_bytes())
    _manifest().update_one({"filename": rel},
                           {"$set": {"length": st.st_size, "mtime": int(st.st_mtime),
                                     "is_deleted": False}}, upsert=True)
    return rel


def subir_archivo_bg(p):
    threading.Thread(target=lambda: subir_archivo(p), daemon=True).start()


def guardar_bytes(rel, data):
    """Guarda bytes directo en el Object Store durable y deja espejo local de trabajo."""
    _put(rel, data)
    dest = ROOT / rel
    _escribir(data, dest)
    st = dest.stat()
    _manifest().update_one({"filename": rel},
                           {"$set": {"length": st.st_size, "mtime": int(st.st_mtime),
                                     "is_deleted": False}}, upsert=True)
    return dest


def sync_en_background():
    threading.Thread(target=sync_diff, daemon=True).start()


def sync_diff():
    """Espejo disco → Object Store: sube nuevos/cambiados y actualiza el manifiesto.
    NUNCA borra según el disco local: el almacén durable es la fuente de verdad."""
    if not _lock.acquire(blocking=False):
        return {"skipped": True}
    try:
        man = _manifest()
        existentes = {d["filename"]: d for d in
                      man.find({}, {"filename": 1, "length": 1, "mtime": 1})}
        subidos, errores = 0, 0
        for rel, p in _walk():
            try:
                st = p.stat()
                prev = existentes.get(rel)
                if (prev and prev.get("length") == st.st_size
                        and prev.get("mtime") == int(st.st_mtime)):
                    continue
                _put(rel, p.read_bytes())
                man.update_one({"filename": rel},
                               {"$set": {"length": st.st_size, "mtime": int(st.st_mtime),
                                         "is_deleted": False}}, upsert=True)
                subidos += 1
            except Exception as e:
                errores += 1
                logging.warning(f"bunker sync {rel}: {e}")
        return {"subidos": subidos, "errores": errores}
    finally:
        _lock.release()


def migrar_legado():
    """MIGRACIÓN única: disco + GridFS legado → Object Store (manifiesto en Mongo).
    Idempotente y reanudable; corre en hilo daemon."""
    if not _mig_lock.acquire(blocking=False):
        return {"skipped": True}
    try:
        cfg = _db()["config"]
        man = _manifest()
        ya = {d["filename"] for d in man.find({}, {"filename": 1})}
        movidos, errores = 0, 0
        # 1) disco local (prioridad clientes/)
        pendientes = sorted(_walk(), key=lambda x: (not x[0].startswith("clientes/"), x[0]))
        for rel, p in pendientes:
            if rel in ya:
                continue
            try:
                st = p.stat()
                _put(rel, p.read_bytes())
                man.update_one({"filename": rel},
                               {"$set": {"length": st.st_size, "mtime": int(st.st_mtime),
                                         "is_deleted": False}}, upsert=True)
                ya.add(rel)
                movidos += 1
                if movidos % 200 == 0:
                    logging.warning(f"🚚 MIGRACIÓN objstore: {movidos} archivos subidos…")
                    cfg.update_one({"_key": "objstore_migracion"},
                                   {"$set": {"movidos": movidos, "estado": "en_curso"}}, upsert=True)
            except Exception as e:
                errores += 1
                logging.warning(f"migración {rel}: {e}")
        # 2) GridFS legado que no esté ni en disco ni en objstore
        try:
            fs = _gridfs_legacy()
            for d in _db()["bunker.files"].find({}, {"filename": 1, "length": 1, "metadata": 1}):
                rel = d["filename"]
                if rel in ya:
                    continue
                try:
                    _put(rel, fs.get(d["_id"]).read())
                    man.update_one({"filename": rel},
                                   {"$set": {"length": d.get("length"),
                                             "mtime": (d.get("metadata") or {}).get("mtime"),
                                             "is_deleted": False}}, upsert=True)
                    ya.add(rel)
                    movidos += 1
                except Exception as e:
                    errores += 1
                    logging.warning(f"migración gridfs {rel}: {e}")
        except Exception:
            pass
        cfg.update_one({"_key": "objstore_migracion"},
                       {"$set": {"movidos": movidos, "errores": errores,
                                 "estado": "completada", "total_manifiesto": len(ya)}}, upsert=True)
        logging.warning(f"🚚 MIGRACIÓN objstore COMPLETADA: {movidos} subidos, {errores} errores, "
                        f"{len(ya)} archivos en el almacén durable")
        return {"movidos": movidos, "errores": errores, "total": len(ya)}
    finally:
        _mig_lock.release()


def migrar_legado_bg():
    threading.Thread(target=migrar_legado, daemon=True).start()


def eliminar(path):
    """Borrado EXPLÍCITO: soft-delete en el manifiesto (el Object Store no borra objetos),
    borrado en GridFS legado y limpieza del disco local."""
    import shutil as _sh
    try:
        p = Path(path)
        rel = p.relative_to(ROOT).as_posix() if p.is_absolute() else str(path).replace("\\", "/").strip("/")
    except ValueError:
        return 0
    if not rel:
        return 0
    rx = {"$regex": "^" + re.escape(rel) + "(/|$)"}
    n = _manifest().update_many({"filename": rx}, {"$set": {"is_deleted": True}}).modified_count
    try:
        fs = _gridfs_legacy()
        for d in _db()["bunker.files"].find({"filename": rx}, {"_id": 1}):
            try:
                fs.delete(d["_id"])
                n += 1
            except Exception:
                pass
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
        logging.info(f"🏦 BÚNKER: borrado explícito «{rel}» — {n} entrada(s)")
    return n


def eliminar_bg(path):
    threading.Thread(target=eliminar, args=(str(path),), daemon=True).start()
