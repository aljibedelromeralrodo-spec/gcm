"""🧪 MODO PRUEBA DE CLASIFICACIÓN Y OCR — Central Mutuos.
Durante la ventana activa (ej: lunes 25 de agosto), cada correo con documentos que
llega a la cuenta monitoreada se procesa COMPLETO (carpeta, clasificación, faltantes),
pero NADA se envía al cliente: el resultado íntegro viaja a gerardo.ext@centralmutuos.cl
(cliente detectado, documentos recibidos, faltantes y clasificación de cada archivo).
"""
import uuid
import asyncio
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from database import db

modop = APIRouter(prefix="/modo-prueba")
KEY = "modo_prueba_clasificacion"
DESTINO_DEFAULT = "gerardo.ext@centralmutuos.cl"
TZ_CL = ZoneInfo("America/Santiago")
_now = lambda: datetime.now(timezone.utc).isoformat()


def _exigir_admin(request):
    c = getattr(request.state, "user", {}) or {}
    if c.get("rol") not in ("admin", "maestro", "administracion"):
        raise HTTPException(status_code=403, detail="Solo el administrador")
    return c


async def _estado():
    return await db.config.find_one({"_key": KEY}, {"_id": 0}) or \
        {"_key": KEY, "enabled": False, "fecha_inicio": "", "fecha_fin": "", "destino": DESTINO_DEFAULT}


async def activo():
    st = await _estado()
    if not st.get("enabled"):
        return False
    ahora = datetime.now(TZ_CL)
    hoy = ahora.strftime("%Y-%m-%d")
    ini, fin = st.get("fecha_inicio") or hoy, st.get("fecha_fin") or st.get("fecha_inicio") or hoy
    if not (ini <= hoy <= fin):
        return False
    # hora_fin: en el último día, la prueba termina a esa hora (ej: martes 26 en la mañana)
    if hoy == fin and st.get("hora_fin") is not None and ahora.hour >= int(st["hora_fin"]):
        return False
    return True


def _fila(label, valor):
    return (f"<tr><td style='padding:5px 10px;color:#FCF6BA;white-space:nowrap'><b>{label}</b></td>"
            f"<td style='padding:5px 10px;color:#e8e2cf'>{valor}</td></tr>")


async def _faltantes_de(item):
    """Faltantes: por criterios de la carpeta si existe; si no, por categorías de apertura."""
    from folders_service import DOCS_APERTURA_VALIDOS, MISSING_LABELS, cat_de_texto
    fid = item.get("drive_folder_id")
    if fid:
        try:
            from server import _criterios_folder
            f = await db.folders.find_one({"id": fid})
            if f:
                return [c["nombre"] for c in _criterios_folder(f)
                        if not c["ok"] and c["nombre"] not in ("Enviada a mesa", "Datos financieros completos")]
        except Exception as e:
            logging.warning(f"modo_prueba faltantes carpeta: {e}")
    docs = (item.get("classification") or {}).get("documentos") or []
    cats = {cat_de_texto(f"{d.get('filename','')} {d.get('tipo','')}") for d in docs}
    return [MISSING_LABELS.get(c, c) for c in sorted(DOCS_APERTURA_VALIDOS - cats)]


async def reportar_item(item):
    """Envía el resultado completo del procesamiento al correo de prueba (NO al cliente)."""
    import email_service as mail
    from server import _email_institucional
    st = await _estado()
    destino = st.get("destino") or DESTINO_DEFAULT
    cl = item.get("classification") or {}
    docs = cl.get("documentos") or []
    faltantes = await _faltantes_de(item)
    filas_docs = "".join(
        f"<tr style='background:{'#141416' if i % 2 == 0 else '#0f0f11'}'>"
        f"<td style='padding:5px 10px;color:#e8e2cf'>{d.get('filename','')}</td>"
        f"<td style='padding:5px 10px;color:#d4af37'><b>{d.get('tipo','—')}</b></td>"
        f"<td style='padding:5px 10px;color:#8a7a5a'>{d.get('metodo','')} · conf {d.get('confianza','—')}</td></tr>"
        for i, d in enumerate(docs)) or "<tr><td colspan=3 style='padding:5px 10px;color:#8a7a5a'>Sin adjuntos clasificados</td></tr>"
    cuerpo = (
        "<p style='margin:0 0 12px'>🧪 <b>MODO PRUEBA DE CLASIFICACIÓN</b> — resultado del "
        "procesamiento automático (el cliente NO fue notificado).</p>"
        "<table style='border-collapse:collapse;font-size:13px;width:100%;margin:4px 0 14px'>"
        + _fila("👤 Cliente detectado", f"{cl.get('cliente') or '⚠️ NO DETECTADO'}"
                + (f" · RUT {cl.get('rut')}" if cl.get('rut') else ""))
        + _fila("✉ Correo origen", f"{item.get('sender','')} — «{(item.get('subject') or '')[:110]}»")
        + _fila("📊 Estado del ítem", item.get("status", ""))
        + _fila("📁 Carpeta", item.get("drive_folder_id") or "no creada")
        + _fila("📄 Documentos recibidos", str(len(docs)))
        + _fila("❌ Documentos faltantes", ", ".join(faltantes) or "Ninguno — set completo")
        + "</table>"
        "<h3 style='color:#b8860b;font-size:14px;margin:12px 0 4px'>Clasificación por archivo</h3>"
        f"<table style='border-collapse:collapse;font-size:13px;width:100%'>{filas_docs}</table>")
    html = _email_institucional("Administración", cuerpo)
    asunto = f"🧪 PRUEBA CLASIFICACIÓN — {cl.get('cliente') or 'Cliente no detectado'} · {item.get('id','')[:8]}"
    res = await asyncio.to_thread(mail.send_mail, destino, asunto, html, [], "principal")
    await db.modo_prueba_reportes.insert_one({
        "id": str(uuid.uuid4()), "proc_id": item.get("id"), "cliente": cl.get("cliente"),
        "docs": len(docs), "faltantes": faltantes, "destino": destino,
        "enviado": bool(res.get("success")), "error": res.get("error", ""), "fecha": _now()})
    await db.proc_queue.update_one({"id": item.get("id")}, {"$set": {"modo_prueba_reportado": True}})
    return bool(res.get("success"))


async def reportar_pendientes(limit=10):
    """Reporta los ítems procesados que aún no tienen su informe de prueba."""
    if not await activo():
        return 0
    items = await db.proc_queue.find({
        "status": {"$in": ["clasificado", "revisar", "procesado"]},
        "modo_prueba_reportado": {"$ne": True}}).sort("date_iso", -1).limit(limit).to_list(limit)
    n = 0
    for it in items:
        try:
            n += 1 if await reportar_item(it) else 0
        except Exception as e:
            logging.warning(f"modo_prueba reporte: {e}")
    if n:
        logging.info(f"🧪 Modo prueba: {n} reporte(s) de clasificación enviados al admin")
    return n


# ── Endpoints (solo admin) ──
@modop.get("/estado")
async def modo_prueba_estado(request: Request):
    _exigir_admin(request)
    st = await _estado()
    st["activo_ahora"] = await activo()
    st["reportes_enviados"] = await db.modo_prueba_reportes.count_documents({})
    st["retenidos_cliente"] = await db.notif_cola.count_documents({"estado_cola": "retenido_modo_prueba"})
    return st


@modop.post("/activar")
async def modo_prueba_activar(request: Request, payload: dict = None):
    _exigir_admin(request)
    p = payload or {}
    fi = (p.get("fecha_inicio") or "").strip()
    if not fi:
        raise HTTPException(status_code=400, detail="fecha_inicio requerida (YYYY-MM-DD)")
    await db.config.update_one({"_key": KEY}, {"$set": {
        "enabled": True, "fecha_inicio": fi, "fecha_fin": (p.get("fecha_fin") or fi).strip(),
        "hora_fin": p.get("hora_fin"),
        "destino": (p.get("destino") or DESTINO_DEFAULT).strip(),
        "activado_en": _now()}}, upsert=True)
    return await _estado()


async def _despachar_retenido(item):
    from server import _autocorreo_cliente_aprobado, _autocorreo_cliente_rechazado
    est = (item.get("estado") or "").lower()
    if est in ("aprobacion", "aprobado"):
        r = await _autocorreo_cliente_aprobado(item, forzar=True)
    else:
        r = await _autocorreo_cliente_rechazado(item, forzar=True)
    ok = bool((r or {}).get("ok"))
    await db.notif_cola.update_one({"seg_id": item.get("seg_id")}, {"$set": {
        "estado_cola": "enviado" if ok else "retenido_modo_prueba",
        "resultado": {k: str(v)[:200] for k, v in (r or {}).items() if k != "html"},
        "despachado_en": _now()}})
    return ok, (r or {})


@modop.get("/retenidos")
async def retenidos_listar(request: Request):
    _exigir_admin(request)
    docs = await db.notif_cola.find({"estado_cola": "retenido_modo_prueba"}, {"_id": 0}) \
        .sort("retenido_en", -1).to_list(200)
    return {"total": len(docs), "retenidos": docs}


@modop.post("/retenidos/aprobar-todos")
async def retenidos_aprobar_todos(request: Request):
    _exigir_admin(request)
    items = await db.notif_cola.find({"estado_cola": "retenido_modo_prueba"}).to_list(200)
    res = []
    for it in items:
        try:
            ok, r = await _despachar_retenido(it)
        except Exception as e:
            ok, r = False, {"motivo": str(e)[:150]}
        res.append({"seg_id": it.get("seg_id"), "cliente": it.get("cliente"),
                    "enviado": ok, "motivo": r.get("motivo", "")})
    return {"ok": True, "procesados": len(res), "enviados": sum(1 for x in res if x["enviado"]), "detalle": res}


@modop.post("/retenidos/descartar-todos")
async def retenidos_descartar_todos(request: Request):
    _exigir_admin(request)
    r = await db.notif_cola.update_many(
        {"estado_cola": "retenido_modo_prueba"},
        {"$set": {"estado_cola": "descartado", "descartado_en": _now(),
                  "descartado_por": "admin"}})
    return {"ok": True, "descartados": r.modified_count}


@modop.post("/retenidos/{rid}/aprobar")
async def retenido_aprobar(rid: str, request: Request):
    _exigir_admin(request)
    it = await db.notif_cola.find_one({"seg_id": rid, "estado_cola": "retenido_modo_prueba"})
    if not it:
        raise HTTPException(status_code=404, detail="Correo retenido no encontrado")
    ok, r = await _despachar_retenido(it)
    if not ok:
        raise HTTPException(status_code=409, detail=f"No se pudo enviar: {r.get('motivo', 'error')}")
    return {"ok": True, "enviado": True, "cliente": it.get("cliente")}


@modop.post("/retenidos/{rid}/descartar")
async def retenido_descartar(rid: str, request: Request):
    _exigir_admin(request)
    r = await db.notif_cola.update_one(
        {"seg_id": rid, "estado_cola": "retenido_modo_prueba"},
        {"$set": {"estado_cola": "descartado", "descartado_en": _now(), "descartado_por": "admin"}})
    if not r.modified_count:
        raise HTTPException(status_code=404, detail="Correo retenido no encontrado")
    return {"ok": True, "descartado": True}


@modop.post("/desactivar")
async def modo_prueba_desactivar(request: Request):
    _exigir_admin(request)
    await db.config.update_one({"_key": KEY}, {"$set": {"enabled": False, "desactivado_en": _now()}}, upsert=True)
    return await _estado()
