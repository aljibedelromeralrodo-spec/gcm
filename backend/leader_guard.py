"""🔐 LEADER GUARD — elección de líder coordinada por base de datos.
Claim atómico con find_one_and_update sobre db.config (_key=leader_lock), identidad
de pod vía HOSTNAME y heartbeat/TTL: renovación cada 15s, expiración a los 45s.
Con múltiples réplicas, SOLO el pod líder ejecuta los loops periódicos 24/7
(ingesta, mesa, espejo, resúmenes, etc. — gateados en server._task_blindada).
Si el pod líder muere, otra réplica toma el mando en <45s.
"""
import os
import socket
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from pymongo import ReturnDocument

from database import db

POD_ID = os.environ.get("HOSTNAME") or socket.gethostname()
LEASE_TTL_SEG = 45
RENOVAR_CADA_SEG = 15
_es_lider = False


def es_lider():
    return _es_lider


def _now():
    return datetime.now(timezone.utc)


async def _intentar_liderazgo():
    """Claim ATÓMICO (find_one_and_update): toma el lock si está libre, expirado
    o ya pertenece a este pod (heartbeat). Devuelve True si este pod es el líder."""
    global _es_lider
    ahora = _now()
    try:
        await db.config.update_one(
            {"_key": "leader_lock"},
            {"$setOnInsert": {"holder": "", "hasta": "1970-01-01T00:00:00+00:00"}},
            upsert=True)
        doc = await db.config.find_one_and_update(
            {"_key": "leader_lock",
             "$or": [{"holder": POD_ID},
                     {"holder": ""},
                     {"holder": {"$exists": False}},
                     {"hasta": {"$lt": ahora.isoformat()}}]},
            {"$set": {"holder": POD_ID,
                      "hasta": (ahora + timedelta(seconds=LEASE_TTL_SEG)).isoformat(),
                      "renovado": ahora.isoformat(),
                      "pid": os.getpid()}},
            return_document=ReturnDocument.AFTER)
        ganado = doc is not None and doc.get("holder") == POD_ID
        if ganado and not _es_lider:
            logging.info(f"🔐 LEADER GUARD: pod {POD_ID} es ahora el LÍDER — loops periódicos activos")
        elif not ganado and _es_lider:
            logging.warning(f"🔐 LEADER GUARD: pod {POD_ID} PERDIÓ el liderazgo — otra réplica ejecuta los loops")
        _es_lider = ganado
    except Exception as e:
        if "after close" in str(e):
            raise
        logging.warning(f"leader guard claim: {e}")
    return _es_lider


async def lider_loop():
    """Heartbeat permanente del lease (corre en TODAS las réplicas)."""
    while True:
        await _intentar_liderazgo()
        await asyncio.sleep(RENOVAR_CADA_SEG)


async def esperar_liderazgo(nombre=""):
    """Bloquea hasta que este pod sea el líder (los loops periódicos esperan aquí)."""
    while not _es_lider:
        await asyncio.sleep(5)


async def liberar():
    """Suelta el lock al apagar para traspaso inmediato a otra réplica."""
    global _es_lider
    if not _es_lider:
        return
    _es_lider = False
    try:
        await db.config.update_one(
            {"_key": "leader_lock", "holder": POD_ID},
            {"$set": {"holder": "", "hasta": "1970-01-01T00:00:00+00:00"}})
        logging.info(f"🔐 LEADER GUARD: lock liberado por {POD_ID} (shutdown)")
    except Exception:
        pass
