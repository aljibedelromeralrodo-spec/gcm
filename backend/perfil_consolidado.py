"""Regla de Oro #64 — La verdad del dato reside en DashAI.

Jerarquía estricta de fuentes: 1° DashAI DB (perfil_consolidado) → 2° Archivos Bóveda → 3° Correo IMAP.
"""
import re
import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from database import db

perfil_r = APIRouter(prefix="/perfil")
_now = lambda: datetime.now(timezone.utc).isoformat()


async def cosechar(folder_id, campos, fuente):
    """MOTOR DE COSECHA: guarda los datos clave en el perfil_consolidado del cliente."""
    fd = await db.folders.find_one({"id": folder_id}, {"perfil_consolidado": 1, "perfil_consolidado_meta": 1})
    if not fd:
        return {}
    perfil = fd.get("perfil_consolidado") or {}
    meta = fd.get("perfil_consolidado_meta") or {}
    cambios = {}
    for k, v in (campos or {}).items():
        if v in (None, "", [], {}):
            continue
        m = meta.get(k) or {}
        # REGLA DE HIERRO #64: dato validado por el administrador → DashAI lo defiende
        if m.get("validado_admin") and perfil.get(k) not in (None, ""):
            continue
        # REGLA DE ORO #65: discrepancia en dato crítico → campo BLOQUEADO en ROJO (revisión manual)
        if k in ("rut", "monto_credito", "rol_propiedad") and perfil.get(k) not in (None, "") and perfil.get(k) != v:
            await db.folders.update_one({"id": folder_id}, {"$set": {f"campos_bloqueados.{k}": {
                "valor_existente": perfil.get(k), "valor_nuevo": v, "fuente_nueva": fuente,
                "estado": "rojo", "fecha": _now(), "regla": "#65"}}})
            continue
        if perfil.get(k) != v:
            perfil[k] = v
            meta[k] = {"fuente": fuente, "fecha": _now()}
            cambios[k] = v
    if cambios:
        await db.folders.update_one({"id": folder_id}, {"$set": {
            "perfil_consolidado": perfil, "perfil_consolidado_meta": meta,
            "perfil_consolidado_actualizado": _now()}})
    return cambios


async def cosechar_carpeta(fd, fuente="cosecha_interna"):
    """Extrae los datos clave desde la Bóveda interna (sin tocar IMAP) y los consolida."""
    df = fd.get("datos_financieros") or {}
    comp = await db.compromisos.find_one({"folder_id": fd.get("id")}) or {}
    prop = (comp.get("datos") or {}).get("propiedad") or {}
    campos = {
        "rut": fd.get("rut"), "inmobiliaria": fd.get("inmobiliaria"), "proyecto": fd.get("proyecto"),
        "direccion": prop.get("direccion") or df.get("direccion"),
        "comuna": prop.get("comuna") or df.get("comuna"),
        "rol_propiedad": prop.get("rol") or df.get("rol_propiedad"),
        "monto_credito": df.get("monto_credito"), "valor_propiedad": df.get("valor_propiedad"),
        "plazo_anos": df.get("plazo_anos"), "tasa": df.get("tasa"),
        "con_subsidio": df.get("con_subsidio"),
        "fecha_tasacion": fd.get("tasacion_fecha"),
        "fecha_informe_tasacion": fd.get("tasacion_informe_recibido_at"),
        "fecha_firma": fd.get("fecha_firma") or fd.get("fecha_firma_detectada"),
    }
    return await cosechar(fd.get("id"), campos, fuente)


async def set_completo_en_bodega(nombre):
    """Set de crédito completo en la Bodega: RUT + montos con respaldo OCR."""
    n = (nombre or "").strip()
    if not n:
        return False
    fd = await db.folders.find_one({"nombre": {"$regex": f"^{re.escape(n)}$", "$options": "i"}})
    if not fd:
        return False
    df = fd.get("datos_financieros") or {}
    return bool(fd.get("rut") and df.get("monto_credito") and fd.get("datos_financieros_ocr_fecha"))


async def imap_permitido(nombre, motivo=""):
    """BLOQUEO DE CONSULTAS REDUNDANTES (Regla #64): prohibido consultar el correo
    si el dato ya existe internamente (anti-bloqueo Gmail)."""
    if await set_completo_en_bodega(nombre):
        logging.info(f"🔒 Regla #64: consulta IMAP bloqueada para {nombre} ({motivo}) — set completo en Bodega")
        return False
    return True


@perfil_r.get("/{fid}")
async def perfil_ver(fid: str):
    fd = await db.folders.find_one({"id": fid}, {"_id": 0, "nombre": 1, "perfil_consolidado": 1,
                                                 "perfil_consolidado_meta": 1,
                                                 "perfil_consolidado_actualizado": 1})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    return fd


@perfil_r.post("/{fid}/validar")
async def perfil_validar(fid: str, payload: dict):
    """El administrador valida un dato → DashAI lo defiende como fuente de verdad única."""
    campo = (payload.get("campo") or "").strip()
    if not campo:
        raise HTTPException(status_code=400, detail="Indique el campo a validar")
    valor = payload.get("valor")
    upd = {f"perfil_consolidado_meta.{campo}.validado_admin": True,
           f"perfil_consolidado_meta.{campo}.fecha": _now(),
           f"perfil_consolidado_meta.{campo}.fuente": "validacion_admin"}
    if valor not in (None, ""):
        upd[f"perfil_consolidado.{campo}"] = valor
    r = await db.folders.update_one({"id": fid}, {"$set": upd})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    return {"ok": True, "campo": campo, "regla": "#64 — dato defendido por DashAI como verdad única"}


async def cosecha_loop():
    """ACTUALIZACIÓN SILENCIOSA: consolida perfiles desde datos internos cada 30 min (sin IMAP)."""
    await asyncio.sleep(120)
    while True:
        try:
            marca = await db.config.find_one({"_key": "cosecha_perfil"}) or {}
            desde = marca.get("ultima") or ""
            q = {"updated_at": {"$gt": desde}} if desde else {}
            n = 0
            async for fd in db.folders.find(q).limit(300):
                try:
                    if await cosechar_carpeta(fd, "actualizacion_silenciosa"):
                        n += 1
                except Exception:
                    continue
            await db.config.update_one({"_key": "cosecha_perfil"},
                                       {"$set": {"ultima": _now(), "consolidados": n}}, upsert=True)
            if n:
                logging.info(f"🌾 Cosecha #64: {n} perfil(es) consolidado(s) sin tocar IMAP")
        except Exception as e:
            logging.warning(f"cosecha perfil: {e}")
        await asyncio.sleep(1800)
