"""🗂️ EXTENSIONES DE CARPETAS (solo agregar, sin tocar módulos existentes):
1) Considerar/Descartar solicitudes desde el calendario (sale del flujo sin eliminarse).
2) Enviar Aprobación/Rechazo al Ejecutivo con preview de correo + PDFs guardados.
3) Widget en vivo 'Correos de Solicitud - Hoy' para el dashboard del administrador.
"""
import re
import uuid
import base64
import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from database import db
import folders_service as fsvc

carpres = APIRouter()

ROLES = ("admin", "maestro", "administracion", "gerencia", "contralor")
ROLES_WIDGET = ("admin", "maestro", "administracion")

DOC_LABELS = {"cedula": "Carnet de Identidad", "afp": "Certificado AFP", "cmf": "Informe CMF",
              "boletas": "Boletas de Honorarios", "liquidacion": "Liquidación de Sueldo",
              "imp_renta": "Declaración de Impuestos"}


def _exigir(request, roles=ROLES):
    c = getattr(request.state, "user", {}) or {}
    if c.get("rol") not in roles:
        raise HTTPException(status_code=403, detail="Su rol no tiene acceso a esta función")
    return c


def _now():
    return datetime.now(timezone.utc).isoformat()


# ────────────────── 1) CONSIDERAR / DESCARTAR ──────────────────

@carpres.post("/clientes/folders/{fid}/descartar")
async def folder_descartar(fid: str, request: Request):
    claims = _exigir(request)
    f = await db.folders.find_one({"id": fid}, {"_id": 0, "id": 1, "nombre": 1})
    if not f:
        raise HTTPException(status_code=404, detail="Carpeta no encontrada")
    await db.folders.update_one({"id": fid}, {"$set": {
        "descartada": True, "descartada_at": _now(), "descartada_por": claims.get("sub")}})
    await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "solicitud_descartada", "leida": True,
                                 "mensaje": f"🚫 Solicitud DESCARTADA (fuera del flujo, sin eliminar) — {f.get('nombre')} (por {claims.get('sub')})",
                                 "fecha": _now()})
    return {"ok": True, "descartada": True}


@carpres.post("/clientes/folders/{fid}/considerar")
async def folder_considerar(fid: str, request: Request):
    claims = _exigir(request)
    f = await db.folders.find_one({"id": fid}, {"_id": 0, "id": 1, "nombre": 1})
    if not f:
        raise HTTPException(status_code=404, detail="Carpeta no encontrada")
    await db.folders.update_one({"id": fid}, {"$set": {
        "descartada": False, "considerada_at": _now(), "considerada_por": claims.get("sub")}})
    await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "solicitud_considerada", "leida": True,
                                 "mensaje": f"✅ Solicitud CONSIDERADA (activa en el flujo) — {f.get('nombre')} (por {claims.get('sub')})",
                                 "fecha": _now()})
    return {"ok": True, "descartada": False}


# ────────────────── 2) ENVIAR APROBACIÓN/RECHAZO AL EJECUTIVO ──────────────────

def _rut_norm(r):
    return re.sub(r"[^0-9kK]", "", r or "").lower()


async def _resultado_folder(f):
    """Último resultado del Motor por RUT: 'aprobado' | 'reprobado' | None."""
    rn = _rut_norm(f.get("rut"))
    if not rn:
        return None, None
    ultima = None
    async for s in db.simulaciones.find(
            {}, {"_id": 0, "rut": 1, "precalificacion_aprobada": 1, "timestamp": 1}).sort("timestamp", -1):
        if _rut_norm(s.get("rut"))[:8] == rn[:8]:
            ultima = s
            break
    if not ultima:
        return None, None
    v = ultima.get("precalificacion_aprobada")
    if isinstance(v, str):
        v = v.strip().lower() in ("true", "1", "si", "sí")
    if v is None:
        return None, None
    return ("aprobado" if v else "reprobado"), str(ultima.get("timestamp") or "")[:10]


async def _destinos_ejecutivo(f):
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
    return [d for d in destinos if not d.endswith("@centralmutuos.cl")] or destinos


def _cuerpos(f, resultado):
    nombre = f.get("nombre") or "el cliente"
    rut = f.get("rut") or ""
    rut_txt = f" (RUT {rut})" if rut else ""
    if resultado == "aprobado":
        asunto = f"Aprobación de Crédito Hipotecario — {nombre}"
        cuerpo = (
            f"<p style='margin:0 0 12px'>Junto con saludar, nos complace informar que la solicitud de crédito "
            f"hipotecario de <b>{nombre}</b>{rut_txt} fue <b>APROBADA</b>.</p>"
            f"<p style='margin:0 0 12px'>Se adjuntan la <b>carta de aprobación</b> y la <b>simulación del crédito</b> "
            f"para su conocimiento y gestión con el cliente.</p>"
            f"<p style='margin:0 0 12px'>Quedamos atentos para coordinar los siguientes pasos del proceso.</p>")
    else:
        asunto = f"Resultado de evaluación — {nombre}"
        cuerpo = (
            f"<p style='margin:0 0 12px'>Junto con saludar, le informamos que la solicitud de crédito hipotecario de "
            f"<b>{nombre}</b>{rut_txt} fue evaluada y, en esta instancia, <b>el cliente no calificó</b> "
            f"para continuar el proceso.</p>"
            f"<p style='margin:0 0 12px'>Quedamos atentos a nuevos antecedentes que permitan reevaluar el caso.</p>")
    return asunto, cuerpo


@carpres.get("/clientes/folders/{fid}/resultado-ejecutivo")
async def resultado_ejecutivo(fid: str, request: Request):
    _exigir(request)
    f = await db.folders.find_one({"id": fid})
    if not f:
        raise HTTPException(status_code=404, detail="Carpeta no encontrada")
    resultado, fecha = await _resultado_folder(f)
    if not resultado:
        return {"resultado": None}
    from server import _email_institucional, aprobacion_archivos
    asunto, cuerpo = _cuerpos(f, resultado)
    archivos = []
    if resultado == "aprobado":
        r = await aprobacion_archivos(cliente=f.get("nombre") or "")
        archivos = [{"nombre": a["nombre"], "tipo": a["tipo"], "ruta": a["ruta"], "origen": a["origen"]}
                    for a in (r.get("archivos") or [])]
    destinos = await _destinos_ejecutivo(f)
    return {"resultado": resultado, "fecha_resultado": fecha, "asunto": asunto,
            "cuerpo_html": _email_institucional("Ejecutivo/a", cuerpo),
            "destinatarios": destinos, "archivos": archivos,
            "ya_enviado_at": f.get("resultado_enviado_at")}


@carpres.post("/clientes/folders/{fid}/enviar-resultado-ejecutivo")
async def enviar_resultado_ejecutivo(fid: str, request: Request):
    claims = _exigir(request)
    f = await db.folders.find_one({"id": fid})
    if not f:
        raise HTTPException(status_code=404, detail="Carpeta no encontrada")
    resultado, _fecha = await _resultado_folder(f)
    if not resultado:
        raise HTTPException(status_code=400, detail="La carpeta no tiene un resultado registrado")
    destinos = await _destinos_ejecutivo(f)
    if not destinos:
        raise HTTPException(status_code=400, detail="La carpeta no tiene ejecutivo/solicitante con correo asociado")
    from server import _email_institucional, aprobacion_archivos, STORAGE_DIR
    import email_service as mail
    asunto, cuerpo = _cuerpos(f, resultado)
    adjuntos = []
    if resultado == "aprobado":
        r = await aprobacion_archivos(cliente=f.get("nombre") or "")
        for a in (r.get("archivos") or []):
            try:
                if a["origen"] == "clientes":
                    p = fsvc.resolver_ruta(f.get("nombre") or "", a["ruta"])
                else:
                    p = STORAGE_DIR / a["ruta"]
                adjuntos.append({"filename": a["nombre"],
                                 "content_b64": base64.b64encode(p.read_bytes()).decode()})
            except Exception:
                continue
        if not adjuntos:
            raise HTTPException(status_code=409, detail="No se encontraron los PDF de aprobación guardados en la carpeta del cliente")
    html = _email_institucional("Ejecutivo/a", cuerpo)
    r = await asyncio.to_thread(mail.send_mail, ", ".join(destinos), asunto, html, adjuntos)
    if not r.get("success"):
        raise HTTPException(status_code=502, detail=f"No fue posible enviar el correo: {r.get('error')}")
    await db.folders.update_one({"id": fid}, {"$set": {
        "resultado_enviado_at": _now(), "resultado_enviado_tipo": resultado,
        "resultado_enviado_a": destinos}})
    await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "resultado_enviado_ejecutivo", "leida": True,
                                 "mensaje": f"📧 {'Aprobación' if resultado == 'aprobado' else 'Rechazo'} enviado al ejecutivo ({', '.join(destinos)}) — {f.get('nombre')} (por {claims.get('sub')})",
                                 "fecha": _now()})
    return {"ok": True, "resultado": resultado, "destinatarios": destinos, "adjuntos": len(adjuntos)}


@carpres.post("/seguridad/verificar-pin-maestro")
async def verificar_pin_maestro(payload: dict, request: Request):
    """Desbloqueo del protector de pantalla del Administrador con el Master PIN."""
    import os
    claims = _exigir(request, ("admin", "maestro"))
    pin = os.environ.get("MASTER_PIN", "")
    if not pin or str(payload.get("pin") or "") != pin:
        await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "seguridad", "leida": False,
                                     "mensaje": f"🚨 Protector de pantalla: intento de PIN maestro FALLIDO (usuario {claims.get('sub')})",
                                     "fecha": _now()})
        raise HTTPException(status_code=403, detail="PIN maestro incorrecto")
    return {"ok": True}


# ────────────────── 3) WIDGET 'CORREOS DE SOLICITUD - HOY' ──────────────────

def _docs_correo(it):
    nombres = list(it.get("attachments") or [])
    for d in ((it.get("classification") or {}).get("documentos") or []):
        if d.get("filename"):
            nombres.append(d["filename"])
    cats = fsvc.docs_apertura_cats(nombres)
    return sorted(DOC_LABELS[c] for c in cats)


@carpres.get("/dashboard/correos-solicitud-hoy")
async def correos_solicitud_hoy(request: Request):
    _exigir(request, ROLES_WIDGET)
    hoy = datetime.now(ZoneInfo("America/Santiago")).strftime("%Y-%m-%d")
    items = await db.proc_queue.find(
        {"date_iso": {"$gte": hoy}},
        {"_id": 0, "id": 1, "sender": 1, "subject": 1, "date_iso": 1, "attachments": 1,
         "status": 1, "drive_folder_id": 1, "classification.cliente": 1,
         "classification.documentos.filename": 1}).sort("date_iso", -1).limit(60).to_list(60)
    salida = []
    for it in items:
        docs = _docs_correo(it)
        estado = "nuevo"
        if it.get("status") == "descartado":
            estado = "descartado"
        elif it.get("drive_folder_id") or it.get("status") == "procesado":
            estado = "carpeta_creada"
        salida.append({"id": it.get("id"), "remitente": it.get("sender") or "",
                       "asunto": it.get("subject") or "(Sin asunto)",
                       "hora": str(it.get("date_iso") or "")[11:16],
                       "cliente": ((it.get("classification") or {}).get("cliente")) or "",
                       "adjuntos": it.get("attachments") or [],
                       "documentos_detectados": docs,
                       "puede_crear": len(docs) >= 3,
                       "estado": estado})
    return {"fecha": hoy, "correos": salida, "total": len(salida)}


@carpres.post("/dashboard/correos-solicitud-hoy/{qid}/no-tomar")
async def correo_no_tomar(qid: str, request: Request):
    claims = _exigir(request, ROLES_WIDGET)
    r = await db.proc_queue.update_one({"id": qid}, {"$set": {
        "status": "descartado", "descartado_motivo": f"No tomado en cuenta (widget dashboard, por {claims.get('sub')})",
        "descartado_en": _now()}})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Correo no encontrado")
    return {"ok": True}


@carpres.post("/dashboard/correos-solicitud-hoy/{qid}/crear-carpeta")
async def correo_crear_carpeta(qid: str, request: Request):
    _exigir(request, ROLES_WIDGET)
    it = await db.proc_queue.find_one({"id": qid}, {"_id": 0, "id": 1})
    if not it:
        raise HTTPException(status_code=404, detail="Correo no encontrado")
    # REGLA CONSTITUCIONAL #67 se valida dentro del pipeline oficial (sin excepciones)
    from server import proc_upload_drive
    r = await proc_upload_drive(qid)
    return {"ok": True, "carpeta": r.get("folder_name") or "", "archivos": len(r.get("uploaded") or [])}
