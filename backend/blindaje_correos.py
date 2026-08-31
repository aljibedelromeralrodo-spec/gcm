"""V15.9 — Blindaje correos entrada/salida + enriquecimiento de carpeta.

Mongo (no Postgres). El envío NO usa créditos Emergent: plantillas + SMTP MAIL2.
La bandeja de autorización del Admin es el preview constitucional: sin clic, no sale.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from database import db
import folders_service as fsvc

blindaje = APIRouter(prefix="/blindaje-correos")

VERSION = "V15.9"

# ── Protocolos (spec SQL) mapeados a categorías de carpeta ──────────────
DOC_A_CAT = {
    "cedula": "cedula",
    "cedula_titular": "cedula",
    "cedula_codeudor": "codeudor",
    "liquidacion_3_meses": "liquidacion",
    "liquidacion_3_meses_titular": "liquidacion",
    "liquidacion_3_meses_codeudor": "codeudor",
    "cotizaciones_12": "afp",
    "cotizaciones_12_titular": "afp",
    "cotizaciones_12_codeudor": "codeudor",
    "certificado_antiguedad": "contrato",
    "certificado_antiguedad_titular": "contrato",
    "certificado_antiguedad_codeudor": "codeudor",
    "contrato_trabajo": "contrato",
    "contrato_codeudor": "codeudor",
    "carpeta_tributaria": "imp_renta",
    "balance": "imp_renta",
    "declaracion_iva_6m": "f29",
    "certificado_deudas": "cmf",
    "certificado_afp": "afp",
    "licencia_medica_detalle": "licencia",
    "certificado_fonasa_licencias": "pago_licencia",
    "informe_medico": "extras",
}

DOC_LABEL = {
    "cedula": "Cédula de identidad",
    "cedula_titular": "Cédula del titular",
    "cedula_codeudor": "Cédula del codeudor",
    "liquidacion_3_meses": "Liquidaciones de sueldo (3 meses)",
    "liquidacion_3_meses_titular": "Liquidaciones del titular (3 meses)",
    "liquidacion_3_meses_codeudor": "Liquidaciones del codeudor (3 meses)",
    "cotizaciones_12": "Cotizaciones AFP (12 meses)",
    "cotizaciones_12_titular": "Cotizaciones AFP titular (12 meses)",
    "cotizaciones_12_codeudor": "Cotizaciones AFP codeudor (12 meses)",
    "certificado_antiguedad": "Certificado de antigüedad",
    "certificado_antiguedad_titular": "Antigüedad del titular",
    "certificado_antiguedad_codeudor": "Antigüedad del codeudor",
    "contrato_trabajo": "Contrato de trabajo",
    "contrato_codeudor": "Contrato del codeudor",
    "carpeta_tributaria": "Carpeta tributaria / F22",
    "balance": "Balance / carpeta tributaria",
    "declaracion_iva_6m": "Declaración IVA / F29 (6 meses)",
    "certificado_deudas": "Informe de deudas CMF",
    "certificado_afp": "Certificado AFP",
    "licencia_medica_detalle": "Licencia médica (detalle)",
    "certificado_fonasa_licencias": "Certificado Fonasa de licencias",
    "informe_medico": "Informe médico",
}

PROTOCOLOS = (
    {
        "id": "independiente",
        "nombre": "Renta Independiente",
        "documentos_requeridos": ["carpeta_tributaria", "balance", "cedula", "declaracion_iva_6m"],
        "documentos_opcionales": ["certificado_deudas"],
        "valida_con": "sii",
        "dias_licencia_max": 0,
        "requiere_codeudor": False,
    },
    {
        "id": "mixto",
        "nombre": "Renta Mixta Independiente + Dependiente",
        "documentos_requeridos": [
            "carpeta_tributaria", "liquidacion_3_meses", "certificado_antiguedad",
            "cedula", "cotizaciones_12",
        ],
        "documentos_opcionales": ["contrato_trabajo"],
        "valida_con": "sii_fonasa",
        "dias_licencia_max": 0,
        "requiere_codeudor": False,
    },
    {
        "id": "con_codeudor",
        "nombre": "Con Codeudor",
        "documentos_requeridos": [
            "liquidacion_3_meses_titular", "liquidacion_3_meses_codeudor",
            "certificado_antiguedad_titular", "certificado_antiguedad_codeudor",
            "cedula_titular", "cedula_codeudor",
            "cotizaciones_12_titular", "cotizaciones_12_codeudor",
        ],
        "documentos_opcionales": ["contrato_codeudor"],
        "valida_con": "fonasa",
        "dias_licencia_max": 0,
        "requiere_codeudor": True,
    },
    {
        "id": "con_licencia_medica",
        "nombre": "Con Licencia Médica",
        "documentos_requeridos": [
            "liquidacion_3_meses", "certificado_antiguedad", "cedula",
            "cotizaciones_12", "licencia_medica_detalle", "certificado_fonasa_licencias",
        ],
        "documentos_opcionales": ["informe_medico"],
        "valida_con": "fonasa",
        "dias_licencia_max": 90,
        "requiere_codeudor": False,
    },
    {
        "id": "dependiente_simple",
        "nombre": "Dependiente Simple",
        "documentos_requeridos": [
            "liquidacion_3_meses", "certificado_antiguedad", "cedula",
            "cotizaciones_12", "contrato_trabajo",
        ],
        "documentos_opcionales": ["certificado_afp"],
        "valida_con": "fonasa",
        "dias_licencia_max": 15,
        "requiere_codeudor": False,
    },
    {
        "id": "renta_variable",
        "nombre": "Renta Variable",
        "documentos_requeridos": [
            "liquidacion_3_meses", "cedula", "cotizaciones_12", "certificado_antiguedad",
        ],
        "documentos_opcionales": ["contrato_trabajo", "certificado_deudas"],
        "valida_con": "fonasa",
        "dias_licencia_max": 0,
        "requiere_codeudor": False,
    },
)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _es_admin(request):
    c = getattr(request.state, "user", {}) or {}
    if c.get("rol") not in ("admin", "maestro"):
        raise HTTPException(status_code=403, detail="Solo el Administrador")
    return c


def protocolo_por_id(pid):
    for p in PROTOCOLOS:
        if p["id"] == pid:
            return p
    return None


def detectar_protocolo(folder, analisis=None):
    """Prioridad: licencia → codeudor → mixto → independiente → dependiente_simple."""
    cr = (folder or {}).get("credit_request") or {}
    an = analisis or {}
    licencia = bool(cr.get("licencia_medica") or an.get("licencia_medica"))
    codeudor = bool(
        cr.get("codeudor_tipo")
        or (cr.get("codeudor") or {}).get("has_codeudor")
        or (folder or {}).get("codeudor_nombre")
        or (folder or {}).get("codeudor_rut")
        or an.get("tiene_codeudor_docs")
    )
    tipo = (an.get("tipo_evidencia") or cr.get("client_type") or "dependiente").lower()
    if licencia:
        return "con_licencia_medica"
    if codeudor:
        return "con_codeudor"
    if tipo == "mixto":
        return "mixto"
    if tipo == "independiente":
        return "independiente"
    return "dependiente_simple"


def cats_presentes(folder):
    nombre = (folder or {}).get("nombre") or ""
    try:
        archivos = fsvc.scan_archivos(nombre)
    except Exception:
        archivos = []
    cats = set()
    for a in archivos or []:
        cat = fsvc.cat_de_archivo(a.get("nombre"), a.get("subfolder"))
        if cat:
            cats.add(cat)
    return cats


def doc_recibido(documento_tipo, cats):
    cat = DOC_A_CAT.get(documento_tipo, "")
    if not cat:
        return False
    if cat == "codeudor":
        return "codeudor" in cats
    return cat in cats


def etiqueta_doc(documento_tipo):
    return DOC_LABEL.get(documento_tipo) or documento_tipo.replace("_", " ")


def inventario_protocolo(folder, protocolo_id=None, analisis=None):
    pid = protocolo_id or detectar_protocolo(folder, analisis)
    proto = protocolo_por_id(pid) or protocolo_por_id("dependiente_simple")
    cats = cats_presentes(folder)
    req, opc = [], []
    for tipo in proto["documentos_requeridos"]:
        ok = doc_recibido(tipo, cats)
        req.append({
            "documento_tipo": tipo,
            "label": etiqueta_doc(tipo),
            "cat": DOC_A_CAT.get(tipo, ""),
            "estado": "recibido" if ok else "faltante",
            "requerido": True,
        })
    for tipo in (proto.get("documentos_opcionales") or []):
        ok = doc_recibido(tipo, cats)
        opc.append({
            "documento_tipo": tipo,
            "label": etiqueta_doc(tipo),
            "cat": DOC_A_CAT.get(tipo, ""),
            "estado": "recibido" if ok else "faltante",
            "requerido": False,
        })
    faltan = [d["documento_tipo"] for d in req if d["estado"] == "faltante"]
    tiene = [d["documento_tipo"] for d in req if d["estado"] != "faltante"]
    return {
        "protocolo_id": proto["id"],
        "protocolo_nombre": proto["nombre"],
        "valida_con": proto.get("valida_con") or "",
        "requiere_codeudor": bool(proto.get("requiere_codeudor")),
        "requeridos": req,
        "opcionales": opc,
        "documentos_tiene": tiene,
        "documentos_faltan": faltan,
        "completo": not faltan,
    }


def plantilla_faltantes(nombre, rut, protocolo_nombre, faltan):
    lis = "".join(f"<li style='margin:4px 0'>{etiqueta_doc(t)}</li>" for t in faltan)
    rut_txt = f" (RUT {rut})" if rut else ""
    asunto = f"Documentos faltantes — {nombre} · {protocolo_nombre}"
    html = f"""
    <div style="font-family:Georgia,serif;color:#111;line-height:1.5">
      <p>Estimados, junto con saludar:</p>
      <p>Hemos recibido la solicitud de crédito de <b>{nombre}</b>{rut_txt}
      bajo el protocolo <b>{protocolo_nombre}</b>.</p>
      <p>Para continuar la evaluación necesitamos los siguientes documentos:</p>
      <ol style="margin:8px 0 0;padding-left:22px">{lis}</ol>
      <p style="margin-top:14px">Quedamos atentos. Muchas gracias.</p>
      <p style="margin-top:16px;color:#555">Saludos cordiales,<br/>Central Mutuos · Con Creces</p>
    </div>
    """
    texto = (
        f"Documentos faltantes para {nombre}{rut_txt} ({protocolo_nombre}): "
        + "; ".join(etiqueta_doc(t) for t in faltan)
    )
    return asunto, html, texto


async def seed_protocolos():
    now = _now()
    for p in PROTOCOLOS:
        await db.credito_protocolos_tipo.update_one(
            {"id": p["id"]},
            {"$set": {**p, "version": VERSION, "actualizado": now},
             "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
    try:
        await db.clientes_carpetas_documentos.create_index(
            [("folder_id", 1), ("documento_tipo", 1)], unique=True)
        await db.correos_salida_cola_blindada.create_index(
            [("estado", 1), ("reintento_at", 1)])
        await db.correos_autorizacion_admin.create_index(
            [("estado", 1), ("created_at", -1)])
        await db.correos_autorizacion_admin.create_index(
            "correo_salida_id", unique=True)
    except Exception as e:
        logging.warning(f"blindaje índices: {e}")
    return {"ok": True, "n": len(PROTOCOLOS), "version": VERSION}


async def _log(evento, detalle, correo_salida_id="", correo_entrada_id=""):
    await db.correos_blindaje_log.insert_one({
        "id": str(uuid.uuid4()),
        "correo_salida_id": correo_salida_id or None,
        "correo_entrada_id": correo_entrada_id or None,
        "evento": evento,
        "detalle": detalle or {},
        "created_at": _now(),
        "version": VERSION,
    })


async def sincronizar_documentos(folder, inv, fuente="enriquecimiento_auto", correo_origen_id=""):
    now = _now()
    fid = folder.get("id")
    rut = (folder.get("rut") or "").strip()
    pid = inv["protocolo_id"]
    slots = list(inv["requeridos"]) + list(inv["opcionales"])
    for slot in slots:
        estado = "recibido_por_correo_auto" if (
            slot["estado"] != "faltante" and fuente == "correo_entrada_auto"
        ) else slot["estado"]
        q = {"folder_id": fid, "documento_tipo": slot["documento_tipo"]}
        prev = await db.clientes_carpetas_documentos.find_one(q)
        if prev and prev.get("estado") in ("validado", "rechazado") and estado == "faltante":
            continue
        set_doc = {
            "cliente_rut": rut,
            "protocolo_id": pid,
            "label": slot["label"],
            "estado": estado if not (prev and prev.get("estado") == "validado") else prev["estado"],
            "fuente": fuente if estado != "faltante" or not prev else (prev.get("fuente") or fuente),
            "updated_at": now,
            "requerido": slot["requerido"],
        }
        if correo_origen_id and estado != "faltante":
            set_doc["correo_origen_id"] = correo_origen_id
        if estado != "faltante" and not (prev or {}).get("recibido_at"):
            set_doc["recibido_at"] = now
        await db.clientes_carpetas_documentos.update_one(
            q,
            {"$set": set_doc,
             "$setOnInsert": {
                 "id": str(uuid.uuid4()),
                 "folder_id": fid,
                 "caso_id": fid,
                 "documento_tipo": slot["documento_tipo"],
                 "created_at": now,
             }},
            upsert=True,
        )
    await db.folders.update_one(
        {"id": fid},
        {"$set": {
            "protocolo_id": pid,
            "protocolo_nombre": inv["protocolo_nombre"],
            "protocolo_completo": inv["completo"],
            "protocolo_faltan": inv["documentos_faltan"],
            "protocolo_sync_at": now,
        }})


async def encolar_faltantes(folder, inv, correo_entrada_id=""):
    """Propone el correo de faltantes. NO envía: queda en autorización admin."""
    faltan = inv.get("documentos_faltan") or []
    dest = (folder.get("source_email") or "").strip()
    if not faltan or not dest or "@" not in dest:
        return None
    fid = folder.get("id")
    lista_key = "|".join(sorted(faltan))
    ya = await db.correos_salida_cola_blindada.find_one({
        "folder_id": fid,
        "tipo": "solicitud_documentos_faltantes",
        "lista_key": lista_key,
        "estado": {"$in": ["pendiente_autorizacion", "autorizado", "enviando", "enviado"]},
    })
    if ya:
        return ya.get("id")
    asunto, html, texto = plantilla_faltantes(
        folder.get("nombre") or "", folder.get("rut") or "",
        inv["protocolo_nombre"], faltan)
    sid = str(uuid.uuid4())
    now = _now()
    await db.correos_salida_cola_blindada.insert_one({
        "id": sid,
        "folder_id": fid,
        "caso_id": fid,
        "cliente_rut": folder.get("rut") or "",
        "cliente_nombre": folder.get("nombre") or "",
        "destinatario": dest,
        "cc": [],
        "bcc": [],
        "asunto": asunto,
        "body_html": html,
        "body_text": texto,
        "tipo": "solicitud_documentos_faltantes",
        "protocolo_tipo": inv["protocolo_id"],
        "documentos_faltantes": faltan,
        "lista_key": lista_key,
        "estado": "pendiente_autorizacion",
        "requiere_autorizacion_admin": True,
        "proveedor_envio": "smtp_mail2",
        "intentos": 0,
        "created_at": now,
        "version": VERSION,
    })
    await db.correos_autorizacion_admin.insert_one({
        "id": str(uuid.uuid4()),
        "correo_salida_id": sid,
        "caso_id": fid,
        "folder_id": fid,
        "cliente_nombre": folder.get("nombre") or "",
        "cliente_rut": folder.get("rut") or "",
        "protocolo_detectado": inv["protocolo_id"],
        "clasificacion_ia": "",
        "confianza_ia": None,
        "documentos_tiene": inv.get("documentos_tiene") or [],
        "documentos_faltan": faltan,
        "mensaje_propuesto": html,
        "asunto_propuesto": asunto,
        "destinatario": dest,
        "estado": "pendiente",
        "created_at": now,
        "version": VERSION,
    })
    await _log("faltante_detectado", {
        "folder_id": fid, "faltan": faltan, "protocolo": inv["protocolo_id"],
    }, correo_salida_id=sid, correo_entrada_id=correo_entrada_id)
    return sid


async def _analisis_thread(folder):
    import asyncio
    import clasificador_documental as clasif
    return await asyncio.to_thread(clasif.analizar_archivos_sync, folder.get("nombre") or "")


async def enriquecer_desde_ingesta(folder, item=None):
    """Llamado tras armar/enriquecer una carpeta desde un correo."""
    await seed_protocolos()
    analisis = {}
    try:
        analisis = await _analisis_thread(folder)
    except Exception as e:
        logging.warning(f"blindaje análisis: {e}")
    inv = inventario_protocolo(folder, analisis=analisis)
    qid = (item or {}).get("id") or ""
    fuente = "correo_entrada_auto" if item else "enriquecimiento_auto"
    await sincronizar_documentos(folder, inv, fuente=fuente, correo_origen_id=qid)
    await _log("carpeta_enriquecida", {
        "folder_id": folder.get("id"),
        "protocolo": inv["protocolo_id"],
        "faltan": inv["documentos_faltan"],
        "completo": inv["completo"],
        "correo_id": qid,
    }, correo_entrada_id=qid)
    if not inv["completo"]:
        await encolar_faltantes(folder, inv, correo_entrada_id=qid)
    return inv


# ── API ────────────────────────────────────────────────────────────────
@blindaje.get("/estado")
async def api_estado(request: Request):
    _es_admin(request)
    await seed_protocolos()
    pend = await db.correos_autorizacion_admin.count_documents({"estado": "pendiente"})
    cola = await db.correos_salida_cola_blindada.count_documents(
        {"estado": {"$in": ["pendiente_autorizacion", "autorizado", "enviando"]}})
    enviados = await db.correos_salida_cola_blindada.count_documents({"estado": "enviado"})
    return {
        "version": VERSION,
        "protocolos": len(PROTOCOLOS),
        "autorizaciones_pendientes": pend,
        "cola_activa": cola,
        "enviados": enviados,
        "proveedor_envio": "smtp_mail2",
        "sin_creditos_emergent": True,
    }


@blindaje.get("/protocolos")
async def api_protocolos(request: Request):
    _es_admin(request)
    await seed_protocolos()
    docs = await db.credito_protocolos_tipo.find({}, {"_id": 0}).to_list(50)
    return {"protocolos": docs or list(PROTOCOLOS), "version": VERSION}


@blindaje.get("/autorizaciones")
async def api_autorizaciones(request: Request, estado: str = "pendiente"):
    _es_admin(request)
    q = {}
    if estado and estado != "todas":
        q["estado"] = estado
    docs = await db.correos_autorizacion_admin.find(q, {"_id": 0}).sort("created_at", -1).to_list(80)
    return {"autorizaciones": docs, "total": len(docs)}


@blindaje.get("/cola")
async def api_cola(request: Request, estado: str = ""):
    _es_admin(request)
    q = {}
    if estado:
        q["estado"] = estado
    docs = await db.correos_salida_cola_blindada.find(
        q, {"_id": 0, "body_html": 0}).sort("created_at", -1).to_list(80)
    return {"cola": docs, "total": len(docs)}


@blindaje.get("/carpeta/{fid}")
async def api_carpeta(fid: str, request: Request):
    _es_admin(request)
    fd = await db.folders.find_one({"id": fid}, {"_id": 0})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    analisis = {}
    try:
        analisis = await _analisis_thread(fd)
    except Exception:
        pass
    inv = inventario_protocolo(fd, analisis=analisis)
    docs = await db.clientes_carpetas_documentos.find(
        {"folder_id": fid}, {"_id": 0}).to_list(80)
    return {"folder": {"id": fd.get("id"), "nombre": fd.get("nombre"), "rut": fd.get("rut")},
            "inventario": inv, "documentos": docs}


@blindaje.post("/carpeta/{fid}/sincronizar")
async def api_sync_carpeta(fid: str, request: Request):
    _es_admin(request)
    fd = await db.folders.find_one({"id": fid})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    inv = await enriquecer_desde_ingesta(fd, None)
    return {"ok": True, "inventario": inv}


@blindaje.post("/autorizaciones/{aid}/decidir")
async def api_decidir(aid: str, payload: dict, request: Request):
    user = _es_admin(request)
    doc = await db.correos_autorizacion_admin.find_one({"id": aid})
    if not doc:
        raise HTTPException(status_code=404, detail="Autorización no encontrada")
    if doc.get("estado") != "pendiente":
        raise HTTPException(status_code=409, detail="Esta solicitud ya fue revisada")
    accion = (payload.get("accion") or "").strip().lower()
    if accion not in ("autorizar", "rechazar", "editar"):
        raise HTTPException(status_code=400, detail="Acción: autorizar, rechazar o editar")
    now = _now()
    quien = user.get("sub") or user.get("codigo") or "admin"
    cola = await db.correos_salida_cola_blindada.find_one({"id": doc["correo_salida_id"]})
    if not cola:
        raise HTTPException(status_code=404, detail="Correo de cola no encontrado")

    if accion == "rechazar":
        await db.correos_autorizacion_admin.update_one({"id": aid}, {"$set": {
            "estado": "rechazado", "revisado_por": quien, "revisado_at": now,
            "motivo": (payload.get("motivo") or "").strip()}})
        await db.correos_salida_cola_blindada.update_one({"id": cola["id"]}, {"$set": {
            "estado": "rechazado", "autorizado_por": quien, "autorizado_at": now}})
        await _log("envio_rechazado", {"aid": aid, "por": quien}, correo_salida_id=cola["id"])
        return {"ok": True, "estado": "rechazado"}

    asunto = (payload.get("asunto") or cola.get("asunto") or "").strip()
    html = (payload.get("body_html") or cola.get("body_html") or "").strip()
    dest = (payload.get("destinatario") or cola.get("destinatario") or "").strip()
    if not dest or "@" not in dest:
        raise HTTPException(status_code=400, detail="Destinatario inválido")
    if not asunto or not html:
        raise HTTPException(status_code=400, detail="Asunto y cuerpo son obligatorios")

    editado = accion == "editar" or asunto != cola.get("asunto") or html != cola.get("body_html")
    await db.correos_salida_cola_blindada.update_one({"id": cola["id"]}, {"$set": {
        "asunto": asunto, "body_html": html, "destinatario": dest,
        "estado": "autorizado", "autorizado_por": quien, "autorizado_at": now}})
    await db.correos_autorizacion_admin.update_one({"id": aid}, {"$set": {
        "estado": "editado" if editado and accion != "autorizar" else "autorizado",
        "revisado_por": quien, "revisado_at": now,
        "mensaje_propuesto": html, "asunto_propuesto": asunto, "destinatario": dest}})
    await _log("envio_autorizado", {"aid": aid, "por": quien, "editado": editado},
               correo_salida_id=cola["id"])

    envio = await _enviar_autorizado(cola["id"])
    return {"ok": True, "estado": envio.get("estado"), "envio": envio}


async def _enviar_autorizado(sid):
    cola = await db.correos_salida_cola_blindada.find_one({"id": sid})
    if not cola or cola.get("estado") not in ("autorizado", "enviando"):
        return {"estado": cola.get("estado") if cola else "ausente"}
    await db.correos_salida_cola_blindada.update_one({"id": sid}, {"$set": {
        "estado": "enviando", "intentos": int(cola.get("intentos") or 0) + 1}})
    import email_service as mail
    import asyncio
    from functools import partial
    enviar = partial(
        mail.send_mail,
        cola["destinatario"],
        cola.get("asunto") or "",
        cola.get("body_html") or "",
        body_text=cola.get("body_text"),
        confirmado=True,
        registro_fallo=True,
    )
    res = await asyncio.to_thread(enviar)
    now = _now()
    if res.get("success"):
        await db.correos_salida_cola_blindada.update_one({"id": sid}, {"$set": {
            "estado": "enviado", "enviado_at": now,
            "provider_message_id": res.get("message_id") or "",
            "ultimo_error": ""}})
        await _log("envio_exitoso", {"smtp": res.get("smtp_code")}, correo_salida_id=sid)
        return {"estado": "enviado", "smtp": res.get("smtp_code")}
    if res.get("preview"):
        # Si el choke de preview intercepta, queda como autorizado (el Admin ya vio el cuerpo).
        await db.correos_salida_cola_blindada.update_one({"id": sid}, {"$set": {
            "estado": "autorizado", "preview_id": res.get("preview_id"),
            "ultimo_error": "quedó en preview constitucional"}})
        return {"estado": "autorizado", "preview": True, "preview_id": res.get("preview_id")}
    err = res.get("error") or "error de envío"
    await db.correos_salida_cola_blindada.update_one({"id": sid}, {"$set": {
        "estado": "error", "ultimo_error": err, "reintento_at": now}})
    await _log("envio_error", {"error": err}, correo_salida_id=sid)
    return {"estado": "error", "error": err}


@blindaje.get("/log")
async def api_log(request: Request, limit: int = 40):
    _es_admin(request)
    n = max(1, min(int(limit or 40), 200))
    docs = await db.correos_blindaje_log.find({}, {"_id": 0}).sort("created_at", -1).to_list(n)
    return {"eventos": docs}
