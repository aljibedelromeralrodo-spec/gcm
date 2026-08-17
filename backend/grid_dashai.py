"""GRID-DASHAI — SINCRONIZACIÓN FORZADA E INTEGRAL (Regla de Oro #41).

- ESPEJO CONCRECES CLOUD: la Bodega de Datos del Maserati se replica al búnker GridFS
  (nube de Concreces) con firmas MD5 por archivo.
- PROTOCOLO DE EMPUJE: cada cambio en un cliente genera un evento con secuencia y se
  empuja al instante a todas las instancias (SSE /grid/stream + webhooks registrados).
- RESINCRONIZACIÓN AUTOMÁTICA: al iniciar, se comparan las firmas MD5 nube↔disco y se
  repara cualquier diferencia. El disco en línea es un espejo EXACTO del servidor.
- BLOQUEO DE DESACTIVACIÓN: no existen interruptores. La transmisión es obligatoria y
  permanente (Regla de Hierro).
"""
import os
import json
import uuid
import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from database import db
import bunker

# ── BÓVEDA EXTERNA (Object Storage) — Regla #53: espejo fuera de la BD ──────
import requests as _rq
from urllib.parse import quote as _q
STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
_storage_key = None


def _init_storage(force=False):
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    r = _rq.post(f"{STORAGE_URL}/init", json={"emergent_key": os.environ.get("EMERGENT_LLM_KEY")}, timeout=30)
    r.raise_for_status()
    _storage_key = r.json()["storage_key"]
    return _storage_key


def _subir_nube(ruta, data):
    key = _init_storage()
    url = f"{STORAGE_URL}/objects/centralmutuos/espejo/{_q(ruta)}"
    r = _rq.put(url, headers={"X-Storage-Key": key, "Content-Type": "application/octet-stream"}, data=data, timeout=120)
    if r.status_code == 404:
        key = _init_storage(force=True)
        r = _rq.put(url, headers={"X-Storage-Key": key, "Content-Type": "application/octet-stream"}, data=data, timeout=120)
    r.raise_for_status()
    return r.json()["path"]


def _bajar_nube(cloud_path):
    key = _init_storage()
    r = _rq.get(f"{STORAGE_URL}/objects/{_q(cloud_path)}", headers={"X-Storage-Key": key}, timeout=60)
    r.raise_for_status()
    return r.content

grid = APIRouter(prefix="/grid")
_now = lambda: datetime.now(timezone.utc).isoformat()

# Campos volátiles que no constituyen un "cambio de cliente"
_VOLATILES = {"_id", "updated_at", "ac_status", "prob_aprobacion"}


def _hash_file(p: Path, algo="sha256"):
    h = hashlib.sha256() if algo == "sha256" else hashlib.md5(usedforsecurity=False)
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


async def _next_seq():
    d = await db.counters.find_one_and_update(
        {"_id": "grid_eventos"}, {"$inc": {"seq": 1}}, upsert=True, return_document=True)
    return int(d["seq"])


async def _emitir(tipo, detalle):
    ev = {"seq": await _next_seq(), "id": str(uuid.uuid4()), "tipo": tipo,
          "detalle": detalle, "fecha": _now()}
    await db.grid_eventos.insert_one(dict(ev))
    # PROTOCOLO DE EMPUJE: webhooks registrados (fire-and-forget, jamás bloquea)
    async def _push():
        try:
            import httpx
            hooks = await db.grid_webhooks.find({}).to_list(20)
            if not hooks:
                return
            async with httpx.AsyncClient(timeout=5) as cli:
                for h in hooks:
                    try:
                        await cli.post(h["url"], json=ev if "_id" not in ev else {k: v for k, v in ev.items() if k != "_id"})
                    except Exception:
                        pass
        except Exception:
            pass
    asyncio.create_task(_push())
    return ev


def _firmas_disco():
    """Firmas MD5 de la carpeta de clientes en disco (con caché por size+mtime)."""
    base = bunker.ROOT / "clientes"
    out = {}
    if not base.exists():
        return out
    for p in base.rglob("*"):
        if p.is_file():
            st = p.stat()
            out[f"clientes/{p.relative_to(base).as_posix()}"] = (st.st_size, int(st.st_mtime), p)
    return out


async def resync():
    """RESINCRONIZACIÓN AUTOMÁTICA: compara firmas MD5 nube↔disco y repara diferencias."""
    restaurados = await asyncio.to_thread(bunker.restaurar_faltantes)   # nube → disco
    sync = await asyncio.to_thread(bunker.sync_diff)                    # disco → nube
    disco = await asyncio.to_thread(_firmas_disco)
    idx = {d["ruta"]: d async for d in db.espejo_concreces_cloud.find({})}
    cambiados = 0
    alerta_2h = []
    limite_2h = datetime.now(timezone.utc).timestamp() - 7200
    for ruta, (size, mtime, p) in disco.items():
        prev = idx.get(ruta)
        if prev and prev.get("size") == size and prev.get("mtime") == mtime:
            continue
        # REGLA DE HIERRO #53: archivo con >2h de vida sin respaldo previo → alerta a Gerardo
        if not prev and mtime < limite_2h:
            alerta_2h.append(ruta)
        try:
            firma = await asyncio.to_thread(_hash_file, p)
        except Exception:
            continue
        prev_f = (prev or {}).get("md5") or ""
        # compatibilidad hacia atrás: firmas históricas MD5 (32 hex) se comparan con MD5
        mismo = prev_f == firma or (len(prev_f) == 32
                                    and prev_f == await asyncio.to_thread(_hash_file, p, "md5"))
        if not prev or not mismo:
            cambiados += 1
        cloud_path = (prev or {}).get("cloud_path", "")
        if not cloud_path or not prev or not mismo:
            try:  # BÓVEDA EXTERNA: delta a Object Storage (la BD se mantiene liviana)
                cloud_path = await asyncio.to_thread(_subir_nube, ruta, p.read_bytes())
            except Exception as e:
                logging.warning(f"bóveda externa {ruta}: {e}")
        await db.espejo_concreces_cloud.update_one({"ruta": ruta}, {"$set": {
            "ruta": ruta, "md5": firma, "size": size, "mtime": mtime,
            "cloud_path": cloud_path, "verificado": _now()}}, upsert=True)
    borrados = 0
    for ruta in list(idx):
        if ruta not in disco:
            await db.espejo_concreces_cloud.delete_one({"ruta": ruta})
            borrados += 1
    if alerta_2h:
        ya = await db.alertas.find_one({"tipo": "boveda_2h", "fecha": {"$gte": _now()[:10]}})
        if not ya:
            await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "boveda_2h",
                "mensaje": f"⚠️ REGLA #53: {len(alerta_2h)} archivo(s) llevaban más de 2 horas sin respaldo en la Doble Bóveda. Ya fueron respaldados por GRID-DASHAI. Ej: {alerta_2h[0][:80]}",
                "fecha": _now(), "leida": False})
    estado = {"ultima_resync": _now(), "archivos_espejo": len(disco),
              "restaurados_desde_nube": restaurados,
              "subidos_a_nube": (sync or {}).get("subidos", 0),
              "archivos_en_boveda_externa": await db.espejo_concreces_cloud.count_documents({"cloud_path": {"$ne": ""}}),
              "firmas_actualizadas": cambiados, "firmas_eliminadas": borrados,
              "bloqueo_desactivacion": True, "permanente": True}
    await db.config.update_one({"_key": "grid_dashai"}, {"$set": estado}, upsert=True)
    if restaurados or cambiados or borrados:
        await _emitir("resync_espejo", {"restaurados": restaurados, "firmas": cambiados,
                                        "eliminadas": borrados})
    return estado


def _hash_folder_doc(fd, algo="sha256"):
    limpio = {k: v for k, v in fd.items() if k not in _VOLATILES}
    data = json.dumps(limpio, default=str, sort_keys=True).encode()
    return (hashlib.sha256(data).hexdigest() if algo == "sha256"
            else hashlib.md5(data, usedforsecurity=False).hexdigest())


async def _detectar_cambios_clientes():
    """PROTOCOLO DE EMPUJE: detecta cambios en los documentos de clientes y los empuja."""
    async for fd in db.folders.find({}):
        h = _hash_folder_doc(fd)
        prev = await db.grid_dochash.find_one({"folder_id": fd["id"]})
        prev_h = (prev or {}).get("hash") or ""
        if prev and prev_h == h:
            continue
        if prev and len(prev_h) == 32 and prev_h == _hash_folder_doc(fd, "md5"):
            # migración silenciosa MD5→SHA-256: sin emitir evento (no hubo cambio real)
            await db.grid_dochash.update_one({"folder_id": fd["id"]},
                                             {"$set": {"hash": h, "fecha": _now()}})
            continue
        await db.grid_dochash.update_one({"folder_id": fd["id"]},
                                         {"$set": {"hash": h, "fecha": _now()}}, upsert=True)
        if prev:  # solo se empuja el CAMBIO (el alta inicial no genera ruido)
            await _emitir("cliente_actualizado", {"folder_id": fd["id"],
                                                  "cliente": fd.get("nombre", ""),
                                                  "rut": fd.get("rut", "")})


async def grid_loop():
    """Motor permanente: resync al iniciar + detección de cambios cada 60s.
    PROHIBIDO detenerlo: no existe interruptor (Regla de Oro #41)."""
    await asyncio.sleep(45)
    try:
        await resync()
        logging.info("🛰 GRID-DASHAI: resincronización inicial MD5 nube↔disco completada")
    except Exception as e:
        logging.warning(f"grid resync inicial: {e}")
    ciclo = 0
    while True:
        try:
            await _detectar_cambios_clientes()
            pend = await db.espejo_concreces_cloud.count_documents({"$or": [{"cloud_path": ""}, {"cloud_path": {"$exists": False}}]})
            if pend:
                await _backfill_externo(30)
            ciclo += 1
            if ciclo % 10 == 0:  # espejo completo cada ~10 minutos
                await resync()
        except Exception as e:
            logging.warning(f"grid loop: {e}")
        await asyncio.sleep(60)


@grid.get("/estado")
async def grid_estado():
    cfg = await db.config.find_one({"_key": "grid_dashai"}, {"_id": 0}) or {}
    total_ev = await db.grid_eventos.count_documents({})
    hooks = await db.grid_webhooks.count_documents({})
    return {**cfg, "eventos_emitidos": total_ev, "webhooks_registrados": hooks,
            "bloqueo_desactivacion": True, "permanente": True,
            "regla": "#41 — La información en Central Mutuos es única y universal"}


@grid.get("/eventos")
async def grid_eventos(desde_seq: int = 0):
    regs = await db.grid_eventos.find({"seq": {"$gt": desde_seq}}, {"_id": 0}).sort("seq", 1).to_list(100)
    return {"eventos": regs, "total": len(regs)}


@grid.get("/stream")
async def grid_stream():
    """SSE: empuje instantáneo de eventos a las instancias locales de DashAI."""
    async def gen():
        ultimo = 0
        d = await db.grid_eventos.find_one({}, sort=[("seq", -1)])
        if d:
            ultimo = int(d["seq"])
        yield f"event: conectado\ndata: {json.dumps({'desde_seq': ultimo})}\n\n"
        while True:
            regs = await db.grid_eventos.find({"seq": {"$gt": ultimo}}, {"_id": 0}).sort("seq", 1).to_list(50)
            for r in regs:
                ultimo = int(r["seq"])
                yield f"event: cambio\ndata: {json.dumps(r, default=str)}\n\n"
            await asyncio.sleep(1)
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@grid.post("/resync")
async def grid_resync_manual():
    return {"ok": True, "estado": await resync()}


@grid.post("/webhooks")
async def grid_webhook_registrar(payload: dict):
    url = (payload.get("url") or "").strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL de webhook inválida")
    await db.grid_webhooks.update_one({"url": url}, {"$set": {"url": url, "registrado": _now()}}, upsert=True)
    return {"ok": True, "url": url}


@grid.get("/webhooks")
async def grid_webhooks_listar():
    regs = await db.grid_webhooks.find({}, {"_id": 0}).to_list(50)
    return {"webhooks": regs, "total": len(regs)}


async def _backfill_externo(maxn):
    base = bunker.ROOT / "clientes"
    subidos = fallidos = 0
    async for doc in db.espejo_concreces_cloud.find({"$or": [{"cloud_path": ""}, {"cloud_path": {"$exists": False}}]}).limit(maxn):
        p = base / doc["ruta"].replace("clientes/", "", 1)
        if not p.exists():
            continue
        try:
            cp = await asyncio.to_thread(_subir_nube, doc["ruta"], p.read_bytes())
            await db.espejo_concreces_cloud.update_one({"ruta": doc["ruta"]}, {"$set": {"cloud_path": cp}})
            subidos += 1
        except Exception:
            fallidos += 1
        await asyncio.sleep(0.2)
    logging.info(f"🛰 Bóveda externa: backfill {subidos} subidos, {fallidos} fallidos")
    return subidos, fallidos


@grid.post("/respaldo-externo")
async def grid_respaldo_externo(payload: dict = None):
    """Backfill hacia la Bóveda Externa — corre en segundo plano (no bloquea)."""
    maxn = int((payload or {}).get("max", 200))
    asyncio.create_task(_backfill_externo(maxn))
    pendientes = await db.espejo_concreces_cloud.count_documents({"$or": [{"cloud_path": ""}, {"cloud_path": {"$exists": False}}]})
    return {"ok": True, "en_curso": True, "lote": maxn, "pendientes_antes": pendientes}


@grid.post("/disaster-recovery")
async def grid_disaster_recovery():
    """PROTOCOLO DE RECUPERACIÓN (Regla #53): reconstruye la base documental desde
    las bóvedas (Espejo GridFS + Bóveda Externa + discos locales de los ejecutivos)."""
    restaurados = await asyncio.to_thread(bunker.restaurar_faltantes)
    base = bunker.ROOT / "clientes"
    desde_nube = 0
    async for doc in db.espejo_concreces_cloud.find({"cloud_path": {"$nin": ["", None]}}):
        p = base / doc["ruta"].replace("clientes/", "", 1)
        if p.exists():
            continue
        try:
            data = await asyncio.to_thread(_bajar_nube, doc["cloud_path"])
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            desde_nube += 1
        except Exception as e:
            logging.warning(f"DR bóveda externa {doc['ruta']}: {e}")
    reconstruidas = 0
    if base.exists():
        for d in base.iterdir():
            if not d.is_dir():
                continue
            if await db.folders.find_one({"nombre": {"$regex": f"^{d.name}$", "$options": "i"}}):
                continue
            archivos = [f"{p.parent.name}/{p.name}" for p in d.rglob("*") if p.is_file()]
            await db.folders.insert_one({"id": str(uuid.uuid4()), "nombre": d.name.upper(),
                "rut": "", "archivos": archivos, "origen": "disaster_recovery",
                "created_at": _now()})
            reconstruidas += 1
    estado = await resync()
    await _emitir("disaster_recovery", {"restaurados": restaurados, "desde_boveda_externa": desde_nube,
                                        "carpetas_reconstruidas": reconstruidas})
    return {"ok": True, "archivos_restaurados": restaurados, "desde_boveda_externa": desde_nube,
            "carpetas_reconstruidas": reconstruidas, "espejo": estado,
            "regla": "#53 — Doble Bóveda: local + Espejo Cloud + Bóveda Externa"}
