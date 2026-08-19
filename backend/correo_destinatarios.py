"""PANEL DE DESTINATARIOS DE CORREO POR ACCIÓN.
Visible y editable por el Admin y Gerencia Comercial. Cada acción define TO/CC/BCC
editables desde el panel, con correo de prueba real antes de activar.
REGLA PERMANENTE: respuestas de brokers externos → Victoria y Daniela como principales.
"""
import re
import uuid
import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from database import db

correo_dest = APIRouter(prefix="/correo-destinatarios")

_EDITAN = ("admin", "maestro", "gerencia")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

VICTORIA = "victoriavilches@centralmutuos.cl"
DANIELA = "danielagalindo@centralmutuos.cl"

ACCIONES_BASE = [
    {"accion_id": "reclamo_mutuaria", "nombre": "Reclamo o consulta a Mutuaria y Leasing (broker interno)",
     "descripcion": "Reclamos y consultas dirigidos al broker interno Mutuaria y Leasing.",
     "to": [], "cc": [], "bcc": [], "permanente": False},
    {"accion_id": "respuestas_brokers", "nombre": "Comunicación directa a brokers — respuestas entrantes",
     "descripcion": "REGLA PERMANENTE: las respuestas de brokers externos se enrutan siempre a Victoria y Daniela como destinatarias principales. Solo Admin o Gerencia Comercial pueden modificarla desde este panel.",
     "to": [VICTORIA, DANIELA], "cc": [], "bcc": [], "permanente": True},
    {"accion_id": "operaciones_nuevas", "nombre": "Notificaciones de operaciones nuevas",
     "descripcion": "Avisos automáticos cuando ingresa una operación nueva al sistema.",
     "to": [], "cc": [], "bcc": [], "permanente": False},
    {"accion_id": "docs_faltantes", "nombre": "Alertas de documentos faltantes",
     "descripcion": "Alertas por carpetas con documentación incompleta.",
     "to": [], "cc": [], "bcc": [], "permanente": False},
    {"accion_id": "plazos_escritura", "nombre": "Alertas de plazos vencidos en escritura",
     "descripcion": "Alertas del Tracker de Escritura cuando un paso supera su plazo en días hábiles.",
     "to": [], "cc": [], "bcc": [], "permanente": False},
    {"accion_id": "bienvenida_usuarios", "nombre": "Correos de bienvenida a nuevos usuarios",
     "descripcion": "Copias configurables de los correos de bienvenida enviados a usuarios nuevos.",
     "to": [], "cc": [], "bcc": [], "permanente": False},
]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _claims(request):
    return getattr(request.state, "user", {}) or {}


def _exigir(request):
    c = _claims(request)
    if c.get("rol") not in _EDITAN:
        raise HTTPException(status_code=403, detail="Solo el Administrador y Gerencia Comercial pueden gestionar los destinatarios de correo")
    return c


def _validar_lista(correos):
    limpios = []
    for e in correos or []:
        e = str(e).strip().lower()
        if not e:
            continue
        if not _EMAIL_RE.match(e):
            raise HTTPException(status_code=400, detail=f"Correo inválido: {e}")
        if e not in limpios:
            limpios.append(e)
    return limpios


async def seed_correo_destinatarios():
    """Siembra idempotente de las 6 acciones base."""
    for a in ACCIONES_BASE:
        await db.correo_destinatarios.update_one({"accion_id": a["accion_id"]}, {"$setOnInsert": {
            "id": str(uuid.uuid4()), **a, "base": True, "creado": _now(), "por": "sistema"}}, upsert=True)
    logging.info("📧 Destinatarios de correo por acción: acciones base sembradas")


async def destinatarios_de(accion_id):
    """Helper para módulos del sistema: devuelve (to, cc, bcc) de una acción."""
    doc = await db.correo_destinatarios.find_one({"accion_id": accion_id}) or {}
    return doc.get("to") or [], doc.get("cc") or [], doc.get("bcc") or []


@correo_dest.get("")
async def listar(request: Request):
    c = _exigir(request)
    acciones = await db.correo_destinatarios.find({}, {"_id": 0}).sort("creado", 1).to_list(100)
    return {"acciones": acciones, "puede_editar": True,
            "puede_crear": c.get("rol") in ("admin", "maestro", "gerencia"),
            "puede_eliminar": c.get("rol") in ("admin", "maestro")}


@correo_dest.put("/{accion_id}")
async def editar(accion_id: str, payload: dict, request: Request):
    c = _exigir(request)
    doc = await db.correo_destinatarios.find_one({"accion_id": accion_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Acción de correo no encontrada")
    to = _validar_lista((payload or {}).get("to"))
    cc = _validar_lista((payload or {}).get("cc"))
    bcc = _validar_lista((payload or {}).get("bcc"))
    if doc.get("permanente") and not to:
        raise HTTPException(status_code=400, detail="REGLA PERMANENTE: esta acción debe mantener al menos un destinatario principal")
    upd = {"to": to, "cc": cc, "bcc": bcc, "modificado": _now(),
           "modificado_por": c.get("nombre") or c.get("sub") or ""}
    if not doc.get("base"):
        if (payload or {}).get("nombre"):
            upd["nombre"] = str(payload["nombre"]).strip()[:160]
        if (payload or {}).get("descripcion") is not None:
            upd["descripcion"] = str(payload["descripcion"]).strip()[:400]
    await db.correo_destinatarios.update_one({"accion_id": accion_id}, {"$set": upd})
    await db.correo_dest_log.insert_one({"id": str(uuid.uuid4()), "fecha": _now(), "accion_id": accion_id,
                                         "evento": "edicion", "por": upd["modificado_por"],
                                         "to": to, "cc": cc, "bcc": bcc})
    return {"ok": True, "accion_id": accion_id, "to": to, "cc": cc, "bcc": bcc}


@correo_dest.post("")
async def crear(payload: dict, request: Request):
    c = _exigir(request)
    nombre = str((payload or {}).get("nombre") or "").strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="La nueva acción requiere un nombre")
    accion_id = re.sub(r"[^a-z0-9]+", "_", nombre.lower()).strip("_")[:60] or str(uuid.uuid4())[:8]
    if await db.correo_destinatarios.find_one({"accion_id": accion_id}):
        raise HTTPException(status_code=400, detail="Ya existe una acción con ese nombre")
    doc = {"id": str(uuid.uuid4()), "accion_id": accion_id, "nombre": nombre[:160],
           "descripcion": str((payload or {}).get("descripcion") or "").strip()[:400],
           "to": _validar_lista((payload or {}).get("to")),
           "cc": _validar_lista((payload or {}).get("cc")),
           "bcc": _validar_lista((payload or {}).get("bcc")),
           "permanente": False, "base": False, "creado": _now(),
           "por": c.get("nombre") or c.get("sub") or ""}
    await db.correo_destinatarios.insert_one(dict(doc))
    return {"ok": True, "accion": {k: v for k, v in doc.items() if k != "_id"}}


@correo_dest.delete("/{accion_id}")
async def eliminar(accion_id: str, request: Request):
    c = _claims(request)
    if c.get("rol") not in ("admin", "maestro"):
        raise HTTPException(status_code=403, detail="Solo el Administrador puede eliminar acciones de correo")
    doc = await db.correo_destinatarios.find_one({"accion_id": accion_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Acción no encontrada")
    if doc.get("base"):
        raise HTTPException(status_code=400, detail="Las acciones base del sistema no pueden eliminarse")
    await db.correo_destinatarios.delete_one({"accion_id": accion_id})
    return {"ok": True}


@correo_dest.post("/{accion_id}/prueba")
async def enviar_prueba(accion_id: str, request: Request):
    c = _exigir(request)
    doc = await db.correo_destinatarios.find_one({"accion_id": accion_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Acción no encontrada")
    to, cc, bcc = doc.get("to") or [], doc.get("cc") or [], doc.get("bcc") or []
    if not (to or cc or bcc):
        raise HTTPException(status_code=400, detail="Configure al menos un destinatario antes de enviar la prueba")
    quien = c.get("nombre") or c.get("sub") or "Usuario autorizado"
    html = f"""
    <div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:0 auto;background:#0f172a;border-radius:12px;overflow:hidden">
      <div style="background:#0a0a0a;padding:18px 24px;text-align:center;border-bottom:2px solid #d4af37">
        <span style="color:#d4af37;font-size:18px;font-weight:800;letter-spacing:2px">CENTRAL MUTUOS</span>
        <div style="color:#94a3b8;font-size:10px;letter-spacing:4px;margin-top:2px">CON CRECES</div>
      </div>
      <div style="padding:24px;color:#e2e8f0">
        <h2 style="color:#d4af37;font-size:15px;margin:0 0 10px">🧪 Correo de prueba de configuración</h2>
        <p style="font-size:13px;line-height:1.6;margin:0 0 12px">
          Este es un correo de <b>prueba</b> de la acción:<br/>
          <b style="color:#fff">{doc.get('nombre')}</b></p>
        <table style="font-size:12px;color:#cbd5e1;border-collapse:collapse">
          <tr><td style="padding:3px 10px 3px 0"><b>Para:</b></td><td>{', '.join(to) or '—'}</td></tr>
          <tr><td style="padding:3px 10px 3px 0"><b>CC:</b></td><td>{', '.join(cc) or '—'}</td></tr>
          <tr><td style="padding:3px 10px 3px 0"><b>CCO:</b></td><td>{', '.join(bcc) or '—'}</td></tr>
        </table>
        <p style="font-size:11px;color:#94a3b8;margin-top:16px">
          Si recibió este mensaje, la configuración de destinatarios es correcta.<br/>
          Prueba solicitada por: {quien} · {_now()[:16].replace('T', ' ')} UTC</p>
      </div>
    </div>"""
    import email_service as mail
    destino = to or cc or bcc
    res = await asyncio.to_thread(mail.send_mail, destino,
                                  f"🧪 Prueba de configuración — {doc.get('nombre')}", html,
                                  None, "secundaria", cc or None, None, "", bcc or None)
    await db.correo_dest_log.insert_one({"id": str(uuid.uuid4()), "fecha": _now(), "accion_id": accion_id,
                                         "evento": "prueba", "por": quien, "to": to, "cc": cc, "bcc": bcc,
                                         "resultado": bool(res.get("success")), "detalle": str(res.get("error") or "")[:300]})
    if not res.get("success"):
        raise HTTPException(status_code=502, detail=f"El servidor de correo rechazó la prueba: {res.get('error') or 'error desconocido'}")
    return {"ok": True, "enviado_a": destino, "cc": cc, "bcc": bcc}
