"""EXPORTACIÓN BLINDADA DE LA CONSTITUCIÓN — Cerebro DashAI.
Manual: botón del Admin → PIN maestro → JSON/PDF. PIN incorrecto = cancelado + auditoría.
Automática: al agregar/modificar una normativa queda una exportación pendiente con
recordatorio visible hasta completarse. PIN maestro: variable de entorno MASTER_PIN,
con override configurable por el Admin (hash SHA-256 en db.config, nunca en código).
"""
import io
import os
import uuid
import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, JSONResponse
from database import db

export_r = APIRouter(prefix="/cerebro-export")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _admin(request):
    u = getattr(request.state, "user", {}) or {}
    if u.get("rol") not in ("admin", "maestro"):
        raise HTTPException(status_code=403, detail="La exportación del Cerebro es exclusiva del Administrador")
    return u


async def _pin_valido(pin):
    pin = (pin or "").strip()
    if not pin:
        return False
    cfg = await db.config.find_one({"_key": "master_pin_cfg"}) or {}
    if cfg.get("hash"):
        return hashlib.sha256(pin.encode()).hexdigest() == cfg["hash"]
    return pin == os.environ.get("MASTER_PIN", "")


async def _auditar_intento(admin, resultado, detalle=""):
    await db.normativas_auditoria.insert_one({
        "id": str(uuid.uuid4()), "fecha": _now(), "administrador": admin.get("nombre") or admin.get("sub"),
        "accion": "exportacion_constitucion", "resultado": resultado, "detalle": detalle})


async def _verificar_o_registrar(request, pin):
    admin = _admin(request)
    if not await _pin_valido(pin):
        await _auditar_intento(admin, "PIN_INCORRECTO", "Exportación cancelada: PIN maestro inválido")
        raise HTTPException(status_code=403, detail=(
            "PIN maestro incorrecto — la exportación fue cancelada y el intento quedó "
            "registrado en el log de auditoría."))
    return admin


async def marcar_pendiente(motivo):
    await db.config.update_one({"_key": "export_pendiente"}, {"$set": {
        "pendiente": True, "motivo": motivo, "fecha": _now()}}, upsert=True)


async def _completar_export(admin, formato):
    await db.config.update_one({"_key": "export_pendiente"}, {"$set": {
        "pendiente": False, "completada": _now(), "formato": formato}}, upsert=True)
    await _auditar_intento(admin, "EXPORTADA", f"Constitución exportada en formato {formato}")


async def _reglas_completas():
    cons = await db.config.find_one({"_key": "constitucion_maestra"}, {"_id": 0}) or {}
    docs = await db.dashai_eventos.find(
        {"motivo": {"$in": ["regla_oro", "regla_eficiencia", "regla_operativa",
                            "regla_inviolable", "normativa"]}}, {"_id": 0}).sort("norma_clave", 1).to_list(300)
    return cons, docs


@export_r.get("/estado")
async def export_estado(request: Request):
    _admin(request)
    p = await db.config.find_one({"_key": "export_pendiente"}, {"_id": 0}) or {}
    cfg = await db.config.find_one({"_key": "master_pin_cfg"}) or {}
    return {"pendiente": bool(p.get("pendiente")), "motivo": p.get("motivo") or "",
            "fecha": p.get("fecha") or "", "ultima_export": p.get("completada") or "",
            "pin_personalizado": bool(cfg.get("hash"))}


@export_r.post("/verificar-pin")
async def export_verificar_pin(payload: dict, request: Request):
    await _verificar_o_registrar(request, (payload or {}).get("pin"))
    return {"ok": True, "mensaje": "PIN correcto — opciones de descarga habilitadas"}


@export_r.get("/json")
async def export_json(request: Request, pin: str = ""):
    admin = await _verificar_o_registrar(request, pin)
    cons, docs = await _reglas_completas()
    data = {"sistema": "Central Mutuos — Cerebro DashAI", "exportado": _now(),
            "exportado_por": admin.get("nombre") or admin.get("sub"),
            "version_constitucion": cons.get("version"), "total_reglas": len(docs),
            "estado": "inamovible e inviolable", "reglas": docs}
    await _completar_export(admin, "JSON")
    fn = f"constitucion-central-mutuos-{datetime.now(timezone.utc).strftime('%Y%m%d')}.json"
    return JSONResponse(content=data, headers={"Content-Disposition": f'attachment; filename="{fn}"'})


@export_r.get("/pdf")
async def export_pdf(request: Request, pin: str = ""):
    admin = await _verificar_o_registrar(request, pin)
    cons, docs = await _reglas_completas()
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas as _canvas
    buf = io.BytesIO()
    c = _canvas.Canvas(buf, pagesize=letter)
    w, h = letter
    y = h - 2 * cm
    c.setFont("Times-Bold", 16)
    c.drawCentredString(w / 2, y, "CONSTITUCIÓN OFICIAL — CENTRAL MUTUOS")
    y -= 0.7 * cm
    c.setFont("Times-Roman", 10)
    c.drawCentredString(w / 2, y, f"Cerebro DashAI · v{cons.get('version')} · {len(docs)} reglas "
                                  f"inamovibles e inviolables · Exportado: {datetime.now(timezone.utc).strftime('%d/%m/%Y')}")
    y -= 1.1 * cm
    orden = {"regla_oro": "REGLAS DE ORO", "regla_eficiencia": "REGLAS DE EFICIENCIA",
             "normativa": "NORMATIVAS MAESTRAS", "regla_operativa": "REGLAS OPERATIVAS",
             "regla_inviolable": "REGLAS INVIOLABLES"}
    import textwrap
    for motivo, titulo in orden.items():
        grupo = [d for d in docs if d.get("motivo") == motivo]
        if not grupo:
            continue
        if y < 4 * cm:
            c.showPage(); y = h - 2 * cm
        c.setFont("Times-Bold", 12)
        c.drawString(2 * cm, y, f"{titulo} ({len(grupo)})")
        y -= 0.55 * cm
        for d in grupo:
            lineas = textwrap.wrap(f"{d.get('norma_clave')} · {d.get('titulo') or ''} — {d.get('patron') or ''}", 105)
            if y < 2.5 * cm + 0.4 * cm * len(lineas[:6]):
                c.showPage(); y = h - 2 * cm
            c.setFont("Times-Bold", 8.5)
            c.drawString(2 * cm, y, lineas[0][:120])
            c.setFont("Times-Roman", 8.5)
            for ln in lineas[1:6]:
                y -= 0.38 * cm
                c.drawString(2.4 * cm, y, ln)
            y -= 0.55 * cm
    c.setFont("Times-Italic", 8)
    c.drawCentredString(w / 2, 1.4 * cm, "Documento sobrio 100% negro sobre blanco (Regla de Oro #3). "
                                         "Ningún módulo, rol ni proceso puede operar en contradicción con estas reglas.")
    c.save()
    await _completar_export(admin, "PDF")
    fn = f"constitucion-central-mutuos-{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf"
    return Response(content=buf.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fn}"'})


@export_r.post("/config-pin")
async def export_config_pin(payload: dict, request: Request):
    admin = _admin(request)
    actual = ((payload or {}).get("pin_actual") or "").strip()
    nuevo = ((payload or {}).get("pin_nuevo") or "").strip()
    if not await _pin_valido(actual):
        await _auditar_intento(admin, "PIN_INCORRECTO", "Intento de cambio de PIN con PIN actual inválido")
        raise HTTPException(status_code=403, detail="PIN actual incorrecto — intento registrado en auditoría")
    if len(nuevo) < 4:
        raise HTTPException(status_code=400, detail="El nuevo PIN debe tener al menos 4 dígitos")
    await db.config.update_one({"_key": "master_pin_cfg"}, {"$set": {
        "hash": hashlib.sha256(nuevo.encode()).hexdigest(), "modificado": _now(),
        "por": admin.get("nombre") or admin.get("sub")}}, upsert=True)
    await _auditar_intento(admin, "PIN_ACTUALIZADO", "PIN maestro reconfigurado desde el panel (hash SHA-256)")
    return {"ok": True, "mensaje": "PIN maestro actualizado — almacenado como hash protegido, nunca en código"}
