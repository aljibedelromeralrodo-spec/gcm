"""Panel de control y trazabilidad gerencial: hitos automáticos y consultas in-platform.

No envía correos. Gerencia pregunta, el broker responde en la misma ficha.
Las gestiones por mail (Regla #49) siguen en gerencia/reclamo.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from hitos_pipeline import (
    PREGUNTAS, estados_hitos, cuello_botella, filtro_carpetas_broker,
    estado_tras_mensaje, folder_es_de_broker,
)

traza = APIRouter(prefix="/trazabilidad")


def _db():
    from database import db
    return db


def _now():
    return datetime.now(timezone.utc).isoformat()


def _claims(request):
    return getattr(request.state, "user", {}) or {}


def _es_gerencia(user):
    rol = (user or {}).get("rol") or ""
    perfil = (user or {}).get("perfil") or ""
    return rol in ("admin", "maestro", "gerencia", "contralor") or perfil in ("B", "gerencia_comercial")


def _es_broker(user):
    return (user or {}).get("rol") in ("broker", "ejecutivo") or (user or {}).get("perfil") == "D"


def _dueño_broker(fd, user):
    return folder_es_de_broker(fd, user)


async def _folder_visible(fid, user):
    fd = await _db().folders.find_one({"id": fid})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    if _es_gerencia(user) or _dueño_broker(fd, user):
        return fd
    raise HTTPException(status_code=403, detail="Esta operación no pertenece a su cartera")


@traza.get("/hitos/{fid}")
async def traza_hitos(fid: str, request: Request):
    user = _claims(request)
    fd = await _folder_visible(fid, user)
    est = estados_hitos(fd)
    mes = datetime.now(timezone.utc).strftime("%Y-%m")
    return {
        "folder_id": fid,
        "cliente": fd.get("nombre") or "",
        "hitos": est,
        "cuello": cuello_botella(fd, est),
        "proyectado_mes": (fd.get("proyeccion_mes") or fd.get("mes_proyeccion") or "")[:7] == mes,
        "preguntas": PREGUNTAS,
    }


@traza.get("/comunicaciones/{fid}")
async def traza_comunicaciones(fid: str, request: Request):
    user = _claims(request)
    fd = await _folder_visible(fid, user)
    docs = await _db().comunicaciones_operacion.find(
        {"folder_id": fid}, {"_id": 0}).sort("actualizado", -1).to_list(50)
    return {"folder_id": fid, "cliente": fd.get("nombre") or "", "hilos": docs, "total": len(docs)}


@traza.post("/consulta/{fid}")
async def traza_consultar(fid: str, payload: dict, request: Request):
    """Gerencia pregunta en la ficha. No sale correo: el broker responde acá."""
    user = _claims(request)
    if not _es_gerencia(user):
        raise HTTPException(status_code=403, detail="Solo Gerencia Comercial puede abrir una consulta de hito")
    fd = await _db().folders.find_one({"id": fid})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    hito = str((payload or {}).get("hito") or "").strip().lower()
    if hito not in PREGUNTAS:
        raise HTTPException(status_code=400, detail="Hito inválido (tasacion, estudio o serie)")
    pregunta = PREGUNTAS[hito]
    extra = str((payload or {}).get("mensaje") or "").strip()[:800]
    texto = pregunta if not extra else f"{pregunta} {extra}"
    ahora = _now()
    autor = user.get("nombre") or user.get("sub") or "gerencia"
    existente = await _db().comunicaciones_operacion.find_one(
        {"folder_id": fid, "hito": hito, "estado": "abierta"})
    if not existente:
        existente = await _db().comunicaciones_operacion.find_one(
            {"folder_id": fid, "hito": hito}, sort=[("actualizado", -1)])
    msg = {"id": str(uuid.uuid4()), "tipo": "consulta", "autor": autor,
           "rol": user.get("rol") or "", "texto": texto, "fecha": ahora}
    if existente:
        await _db().comunicaciones_operacion.update_one(
            {"id": existente["id"]},
            {"$push": {"mensajes": msg}, "$set": {"actualizado": ahora, "estado": "abierta"}})
        hid = existente["id"]
    else:
        hid = str(uuid.uuid4())
        await _db().comunicaciones_operacion.insert_one({
            "id": hid, "folder_id": fid, "cliente": fd.get("nombre") or "",
            "hito": hito, "pregunta": pregunta, "estado": "abierta",
            "mensajes": [msg], "creado": ahora, "actualizado": ahora,
            "por": autor})
    await _db().gestion_gerencial_log.insert_one({
        "id": str(uuid.uuid4()), "usuario": autor, "accion": f"consulta_{hito}",
        "cliente": fd.get("nombre") or "", "rut": fd.get("rut") or "",
        "fecha": ahora, "canal": "plataforma"})
    return {"ok": True, "hilo_id": hid, "hito": hito, "pregunta": pregunta,
            "envio": "plataforma", "nota": "Quedó en el hilo de la operación. No se envió correo."}


@traza.post("/responder/{fid}")
async def traza_responder(fid: str, payload: dict, request: Request):
    user = _claims(request)
    fd = await _folder_visible(fid, user)
    hid = str((payload or {}).get("hilo_id") or "").strip()
    texto = str((payload or {}).get("mensaje") or "").strip()[:1200]
    if not texto:
        raise HTTPException(status_code=400, detail="Escriba la respuesta")
    q = {"folder_id": fid}
    if hid:
        q["id"] = hid
    else:
        q["estado"] = "abierta"
    hilo = await _db().comunicaciones_operacion.find_one(q, sort=[("actualizado", -1)])
    if not hilo:
        raise HTTPException(status_code=404, detail="No hay hilo en esta operación")
    ahora = _now()
    autor = user.get("nombre") or user.get("sub") or ""
    msg = {"id": str(uuid.uuid4()), "tipo": "respuesta", "autor": autor,
           "rol": user.get("rol") or "", "texto": texto, "fecha": ahora}
    nuevo_estado = estado_tras_mensaje(
        hilo.get("estado"), _es_broker(user), bool((payload or {}).get("cerrar")))
    upd = {"$push": {"mensajes": msg},
           "$set": {"actualizado": ahora, "estado": nuevo_estado}}
    if nuevo_estado == "respondida":
        upd["$set"]["respondida_por"] = autor
        upd["$set"]["respondida_en"] = ahora
    await _db().comunicaciones_operacion.update_one({"id": hilo["id"]}, upd)
    if _es_broker(user):
        try:
            await _db().alertas.insert_one({
                "id": str(uuid.uuid4()), "tipo": "respuesta_broker",
                "destino": "Gerencia Comercial", "folder_id": fid,
                "cliente": fd.get("nombre") or hilo.get("cliente") or "",
                "mensaje": (f"Broker {autor} respondió «{hilo.get('pregunta') or hilo.get('hito')}» "
                            f"de {fd.get('nombre') or ''}: {texto[:180]}"),
                "fecha": ahora, "leida": False})
        except Exception:
            pass
    return {"ok": True, "hilo_id": hilo["id"], "estado": nuevo_estado,
            "envio": "plataforma"}


@traza.get("/pendientes")
async def traza_pendientes(request: Request):
    user = _claims(request)
    q = {"estado": "abierta"}
    if not _es_gerencia(user):
        fids = []
        async for fd in _db().folders.find(filtro_carpetas_broker(user), {"id": 1}):
            fids.append(fd["id"])
        if not fids:
            return {"pendientes": [], "total": 0}
        q["folder_id"] = {"$in": fids}
    docs = await _db().comunicaciones_operacion.find(q, {"_id": 0}).sort("actualizado", -1).to_list(80)
    return {"pendientes": docs, "total": len(docs), "preguntas": PREGUNTAS}


@traza.get("/respuestas")
async def traza_respuestas(request: Request):
    """Últimas respuestas de brokers, para la bandeja de Gerencia."""
    user = _claims(request)
    if not _es_gerencia(user):
        raise HTTPException(status_code=403, detail="Solo Gerencia Comercial ve esta bandeja")
    docs = await _db().comunicaciones_operacion.find(
        {"estado": "respondida"}, {"_id": 0}).sort("respondida_en", -1).to_list(20)
    return {"respuestas": docs, "total": len(docs)}
