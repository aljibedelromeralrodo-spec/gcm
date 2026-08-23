"""🔐 LEADER GUARD — mutex distribuido en MongoDB para los loops periódicos.
Con múltiples réplicas en producción, SOLO la instancia líder ejecuta los loops
24/7 (ingesta, mesa, espejo, resúmenes, etc.). El liderazgo es un lease atómico
en la colección `config` (_key=leader_lock) que se renueva cada 15s y expira a
los 45s: si el pod líder muere, otra réplica toma el mando en <45s.
"""
import os
import socket
import uuid
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from database import db

INSTANCE_ID = f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
LEASE_TTL_SEG = 45
RENOVAR_CADA_SEG = 15
_es_lider = False


def es_lider():
    return _es_lider


def _now():
    return datetime.now(timezone.utc)


async def _intentar_liderazgo():
    """Claim atómico: toma el lock si está libre, expirado o ya es nuestro."""
    global _es_lider
    ahora = _now()
    try:
        await db.config.update_one(
            {"_key": "leader_lock"},
            {"$setOnInsert": {"holder": "", "hasta": "1970-01-01T00:00:00+00:00"}},
            upsert=True)
        r = await db.config.update_one(
            {"_key": "leader_lock",
             "$or": [{"holder": INSTANCE_ID},
                     {"holder": ""},
                     {"hasta": {"$lt": ahora.isoformat()}}]},
            {"$set": {"holder": INSTANCE_ID,
                      "hasta": (ahora + timedelta(seconds=LEASE_TTL_SEG)).isoformat(),
                      "renovado": ahora.isoformat(),
                      "pid": os.getpid()}})
        ganado = r.matched_count > 0
        if ganado and not _es_lider:
            logging.info(f"🔐 LEADER GUARD: esta instancia ({INSTANCE_ID}) es ahora la LÍDER — loops periódicos activos")
        elif not ganado and _es_lider:
            logging.warning(f"🔐 LEADER GUARD: liderazgo PERDIDO ({INSTANCE_ID}) — otra réplica ejecuta los loops")
        _es_lider = ganado
    except Exception as e:
        if "after close" in str(e):
            raise
        logging.warning(f"leader guard claim: {e}")
    return _es_lider


async def lider_loop():
    """Renueva el lease permanentemente (corre en TODAS las réplicas)."""
    while True:
        await _intentar_liderazgo()
        await asyncio.sleep(RENOVAR_CADA_SEG)


async def esperar_liderazgo(nombre=""):
    """Bloquea hasta que esta instancia sea la líder (los loops esperan aquí)."""
    while not _es_lider:
        await asyncio.sleep(5)


async def liberar():
    """Suelta el lock al apagar para que otra réplica tome el mando de inmediato."""
    global _es_lider
    if not _es_lider:
        return
    _es_lider = False
    try:
        await db.config.update_one(
            {"_key": "leader_lock", "holder": INSTANCE_ID},
            {"$set": {"holder": "", "hasta": "1970-01-01T00:00:00+00:00"}})
        logging.info(f"🔐 LEADER GUARD: lock liberado por {INSTANCE_ID} (shutdown)")
    except Exception:
        pass
