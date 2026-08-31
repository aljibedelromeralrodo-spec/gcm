"""BUZÓN DE RESCATE AUTOMÁTICO — Martín revisa cada noche los adjuntos en cuarentena
(LEY DEL RUT sin match) y enruta SOLO los que tengan un RUT válido (módulo 11) que
coincida con exactamente una carpeta de cliente (titular o codeudor). Lo ambiguo o
sin RUT legible queda en el buzón para revisión humana."""
import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from database import db
import folders_service as fsvc

TZ_CL = ZoneInfo("America/Santiago")
PROC_DIR = Path(__file__).parent / "storage" / "proc"
RUT_TXT_RX = re.compile(r"\b\d{1,2}[.,]?\d{3}[.,]?\d{3}\s?-\s?[\dkK]\b")
HORA_NOCTURNA = 3


def _now():
    return datetime.now(timezone.utc).isoformat()


def _norm(r):
    return re.sub(r"[^0-9kK]", "", (r or "")).lower()


def _ruts_validos(texto):
    out = set()
    for m in RUT_TXT_RX.findall(texto or ""):
        n = _norm(m)
        if len(n) >= 8 and fsvc._rut_dv_ok(n[:-1], n[-1]):
            try:
                if int(n[:-1]) < 50000000:
                    out.add(n)
            except ValueError:
                pass
    return out


async def _mapa_ruts():
    """{rut_normalizado: (nombre_carpeta, es_codeudor, codeudor_nombre)}"""
    mapa = {}
    async for f in db.folders.find({}, {"nombre": 1, "rut": 1, "codeudor_rut": 1,
                                        "codeudor_nombre": 1}):
        rt = _norm(f.get("rut"))
        if len(rt) >= 8:
            mapa.setdefault(rt, set()).add((f["nombre"], False, ""))
        rc = _norm(f.get("codeudor_rut"))
        if len(rc) >= 8:
            mapa.setdefault(rc, set()).add((f["nombre"], True, f.get("codeudor_nombre") or ""))
    return mapa


async def procesar_buzon(limite=60):
    """Recorre las cuarentenas 'revisar' del buzón y enruta las que tengan match único."""
    import permisos_martin as pm
    import ocr_service
    import bunker
    mapa = await _mapa_ruts()
    items = await db.proc_queue.find(
        {"id": {"$regex": "^rescate-ley-rut-"}, "status": "revisar"}).to_list(limite)
    rep = {"revisados": len(items), "enrutados": [], "ambiguos": [],
           "sin_rut": [], "sin_archivo": 0}
    for it in items:
        qid, fn = it["id"], (it.get("attachments") or [""])[0]
        p = PROC_DIR / qid / fn
        if not fn or not p.exists():
            rep["sin_archivo"] += 1
            continue
        raw = p.read_bytes()
        try:
            texto, _m = await asyncio.to_thread(ocr_service.extraer_texto, raw, fn)
        except Exception:
            texto = ""
        ruts = _ruts_validos(texto)
        destinos = set()
        for r in ruts:
            destinos |= mapa.get(r, set())
        if not destinos:
            rep["sin_rut"].append(fn)
            continue
        if len(destinos) > 1:
            rep["ambiguos"].append({"archivo": fn, "carpetas": sorted(d[0] for d in destinos)})
            continue
        nombre, es_cod, cod_nombre = destinos.pop()
        if es_cod:
            sub = "05_codeudor" + (f"/{fsvc.safe_name(cod_nombre)}" if cod_nombre else "")
            fn_dest = fn if fn.upper().startswith("CODEUDOR_") else f"CODEUDOR_{fn}"
            rel = fsvc.guardar_archivo(nombre, fn_dest, raw, subfolder=sub)
        else:
            rel = fsvc.guardar_archivo(nombre, fn, raw)
        bunker.subir_archivo_bg(fsvc.folder_dir(nombre) / rel)
        await pm.log_accion(db, "bunker.clasificar", f"buzon_rescate/{qid}/{fn}",
                            f"clientes/{nombre}/{rel}")
        ahora = _now()
        await db.proc_queue.update_one({"id": qid}, {"$set": {
            "status": "procesado_martin", "resuelto_en": ahora,
            "resuelto_a": f"{nombre}/{rel}",
            "nota": "Buzón de Rescate automático: RUT con match único"}})
        await db.correos_pendientes.update_many({"qid": qid}, {"$set": {
            "estado": "resuelto", "resuelto_en": ahora}})
        rep["enrutados"].append({"archivo": fn, "carpeta": nombre, "rel": rel,
                                 "codeudor": es_cod})
    if rep["enrutados"]:
        bunker.sync_en_background()
    await db.martin_rescate_log.insert_one({"id": str(uuid.uuid4()), "fecha": _now(), **rep})
    if rep["enrutados"] or rep["ambiguos"]:
        await db.alertas.insert_one({
            "id": str(uuid.uuid4()), "tipo": "rescate_buzon_nocturno",
            "cliente": "",
            "mensaje": (f"🌙 Buzón de Rescate nocturno: {len(rep['enrutados'])} adjunto(s) "
                        f"enrutado(s) por RUT, {len(rep['ambiguos'])} ambiguo(s) esperan "
                        f"revisión, {len(rep['sin_rut'])} sin RUT legible."),
            "fecha": _now(), "leida": False})
    return rep


async def rescate_buzon_loop():
    """Cada noche a las 03:00 (Chile) — reserva atómica del día en db.config."""
    await asyncio.sleep(45)
    while True:
        try:
            await asyncio.sleep(300)
            ahora = datetime.now(TZ_CL)
            if ahora.hour != HORA_NOCTURNA:
                continue
            hoy = ahora.strftime("%Y-%m-%d")
            claim = await db.config.update_one(
                {"_key": "rescate_buzon_nocturno", "last_run": {"$ne": hoy}},
                {"$set": {"last_run": hoy}}, upsert=False)
            if not claim.modified_count:
                seed = await db.config.find_one({"_key": "rescate_buzon_nocturno"})
                if seed:
                    continue
                await db.config.insert_one({"_key": "rescate_buzon_nocturno", "last_run": hoy})
            rep = await procesar_buzon()
            logging.info(f"🌙 Buzón de Rescate nocturno: {len(rep['enrutados'])} enrutados, "
                         f"{len(rep['ambiguos'])} ambiguos, {len(rep['sin_rut'])} sin RUT, "
                         f"{rep['sin_archivo']} sin archivo en disco")
        except Exception as e:
            logging.warning(f"rescate_buzon_loop: {e}")
