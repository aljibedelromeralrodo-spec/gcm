"""📅 CALENDARIO DE CARPETAS + EVALUACIÓN NO CALIFICÓ (módulo Carpetas)
- Calendario mensual: carpetas recibidas por día + pendientes de días anteriores
  (sin avance de estado dentro de su día hábil de recepción).
- Evaluaciones negativas: última simulación del Motor por RUT con
  precalificacion_aprobada=False → etiqueta 'No Calificó' + notificación al ejecutivo.
"""
import re
import os
import uuid
import asyncio
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Request
from database import db

calcarp = APIRouter(prefix="/clientes")

ROLES = ("admin", "maestro", "administracion", "gerencia", "contralor")


def _exigir(request):
    c = getattr(request.state, "user", {}) or {}
    if c.get("rol") not in ROLES:
        raise HTTPException(status_code=403, detail="Su rol no tiene acceso a esta función")
    return c


def _now():
    return datetime.now(timezone.utc).isoformat()


def _dt(ts):
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _avanzo(f):
    """La carpeta 'avanzó' si registra cualquier hito posterior a la recepción."""
    return bool(f.get("mesa_enviado_at") or f.get("estudio_titulo_solicitado_at")
                or f.get("escrituracion_movida_at") or f.get("is_escrituracion")
                or f.get("faltantes_pedidos_at") or f.get("tasacion_solicitada_at")
                or f.get("emails_sent_count"))


def _deadline_habil(created):
    """Fin del día hábil siguiente disponible: vie→lun, sáb→lun, dom→lun, resto→día siguiente."""
    wd = created.weekday()
    extra = 3 if wd == 4 else (2 if wd == 5 else 1)
    limite = (created + timedelta(days=extra)).replace(hour=23, minute=59, second=59)
    return limite


def _item(f):
    df = f.get("datos_financieros") or {}
    return {"folder_id": f.get("id"), "nombre": f.get("nombre"), "rut": f.get("rut") or "",
            "monto_uf": df.get("monto_credito") or None,
            "fecha_recepcion": str(f.get("created_at") or "")[:16].replace("T", " "),
            "avanzo": _avanzo(f)}


_PROJ = {"_id": 0, "id": 1, "nombre": 1, "rut": 1, "created_at": 1, "updated_at": 1,
         "datos_financieros.monto_credito": 1, "mesa_enviado_at": 1, "estudio_titulo_solicitado_at": 1,
         "escrituracion_movida_at": 1, "is_escrituracion": 1, "faltantes_pedidos_at": 1,
         "tasacion_solicitada_at": 1, "emails_sent_count": 1}


@calcarp.get("/calendario")
async def calendario_mes(request: Request, mes: str = ""):
    _exigir(request)
    if not re.match(r"^\d{4}-\d{2}$", mes or ""):
        mes = datetime.now(timezone.utc).strftime("%Y-%m")
    dias = {}
    async for f in db.folders.find({"created_at": {"$regex": f"^{mes}"}}, {"_id": 0, "created_at": 1}):
        d = str(f["created_at"])[:10]
        dias[d] = dias.get(d, 0) + 1
    return {"mes": mes, "dias": dias, "total_mes": sum(dias.values())}


@calcarp.get("/calendario/dia")
async def calendario_dia(request: Request, fecha: str = ""):
    _exigir(request)
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", fecha or ""):
        raise HTTPException(status_code=400, detail="Fecha inválida (YYYY-MM-DD)")
    ahora = datetime.now(timezone.utc)
    # Envíos a mesa por correo directo (espejo de la casilla de mesa) también cuentan como avance
    from auditoria_mesa import _norm_tokens, _match_nombre, _rut_limpio
    mesa_idx = [(_norm_tokens(m.get("cliente") or m.get("nombre")), _rut_limpio(m.get("rut")))
                async for m in db.mesa_enviados.find({}, {"_id": 0, "cliente": 1, "nombre": 1, "rut": 1})]

    def _enviado_directo(f):
        ftoks = _norm_tokens(f.get("nombre"))
        frut = _rut_limpio(f.get("rut"))
        return any((frut and mrut and frut == mrut) or _match_nombre(ftoks, mtoks)
                   for mtoks, mrut in mesa_idx)

    del_dia = [_item(f) async for f in
               db.folders.find({"created_at": {"$regex": f"^{fecha}"}}, _PROJ).sort("created_at", 1)]
    # Pendientes de días anteriores: recibidas antes de la fecha, sin avance y con día hábil vencido
    desde = (datetime.fromisoformat(fecha) - timedelta(days=45)).strftime("%Y-%m-%d")
    pendientes = []
    async for f in db.folders.find({"created_at": {"$gte": desde, "$lt": fecha}}, _PROJ).sort("created_at", -1):
        if _avanzo(f) or _enviado_directo(f):
            continue
        created = _dt(f.get("created_at"))
        if not created or ahora <= _deadline_habil(created):
            continue
        it = _item(f)
        it["dias_sin_avance"] = (ahora - created).days
        pendientes.append(it)
    return {"fecha": fecha, "del_dia": del_dia, "pendientes_anteriores": pendientes,
            "resumen": {"del_dia": len(del_dia), "pendientes": len(pendientes)}}


def _rut_norm(r):
    return re.sub(r"[^0-9kK]", "", r or "").lower()


@calcarp.get("/evaluaciones-negativas")
async def evaluaciones_negativas(request: Request):
    """Mapa folder_id → última simulación negativa del Motor (por RUT)."""
    _exigir(request)
    ultima_por_rut = {}
    async for s in db.simulaciones.find({}, {"_id": 0, "rut": 1, "precalificacion_aprobada": 1,
                                             "timestamp": 1, "monto_aprobado_uf": 1}).sort("timestamp", 1):
        rn = _rut_norm(s.get("rut"))
        if rn:
            ultima_por_rut[rn[:8]] = s
    salida = {}
    async for f in db.folders.find({}, {"_id": 0, "id": 1, "rut": 1}):
        rn = _rut_norm(f.get("rut"))
        if not rn:
            continue
        s = ultima_por_rut.get(rn[:8])
        if s and s.get("precalificacion_aprobada") is False:
            salida[f["id"]] = {"fecha": str(s.get("timestamp") or "")[:10],
                               "monto_aprobado_uf": s.get("monto_aprobado_uf")}
    return {"negativas": salida, "total": len(salida)}


@calcarp.post("/folders/{fid}/notificar-no-califico")
async def notificar_no_califico(fid: str, request: Request):
    """Correo conciso al ejecutivo/solicitante asociado informando el resultado negativo."""
    claims = _exigir(request)
    f = await db.folders.find_one({"id": fid})
    if not f:
        raise HTTPException(status_code=404, detail="Carpeta no encontrada")
    destinos = []
    m = re.search(r"[\w.+-]+@[\w.-]+\.\w+", str(f.get("source_email") or ""))
    if m:
        destinos.append(m.group(0).lower())
    rn = _rut_norm(f.get("rut"))
    if rn:
        q = await db.proc_queue.find_one({"classification.rut": {"$regex": rn[:8], "$options": "i"},
                                          "campos.email_ejecutivo": {"$nin": [None, ""]}},
                                         {"_id": 0, "campos.email_ejecutivo": 1})
        eje = ((q or {}).get("campos") or {}).get("email_ejecutivo") or ""
        if eje and eje.lower() not in destinos:
            destinos.append(eje.lower())
    destinos = [d for d in destinos if not d.endswith("@centralmutuos.cl")] or destinos
    if not destinos:
        raise HTTPException(status_code=400, detail="La carpeta no tiene ejecutivo/solicitante con correo asociado")
    nombre = f.get("nombre") or "el cliente"
    rut = f.get("rut") or ""
    cuerpo = (
        f"<p style='margin:0 0 12px'>Junto con saludar, le informamos que la solicitud de crédito hipotecario de "
        f"<b>{nombre}</b>{f' (RUT {rut})' if rut else ''} fue evaluada por nuestro motor de precalificación y, "
        f"en esta instancia, <b>no cumple con los criterios para continuar el proceso</b>.</p>"
        f"<p style='margin:0 0 12px'>Quedamos atentos a nuevos antecedentes que permitan reevaluar el caso.</p>")
    from server import _email_institucional
    import email_service as mail
    html = _email_institucional("Estimado/a", cuerpo)
    r = await asyncio.to_thread(mail.send_mail, ", ".join(destinos),
                                f"Resultado de evaluación — {nombre}", html)
    if not r.get("success"):
        raise HTTPException(status_code=502, detail=f"No fue posible enviar el correo: {r.get('error')}")
    await db.folders.update_one({"id": fid}, {"$set": {"no_califico_notificado_at": _now(),
                                                       "no_califico_notificado_a": destinos}})
    await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "no_califico_notificado", "leida": True,
                                 "mensaje": f"📧 'No Calificó' notificado a {', '.join(destinos)} — {nombre} (por {claims.get('sub')})",
                                 "fecha": _now()})
    return {"ok": True, "destinatarios": destinos}
