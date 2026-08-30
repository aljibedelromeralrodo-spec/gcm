"""🗂️ EXTENSIONES DE CARPETAS (solo agregar, sin tocar módulos existentes):
1) Considerar/Descartar solicitudes desde el calendario (sale del flujo sin eliminarse).
2) Enviar Aprobación/Rechazo al Ejecutivo con preview de correo + PDFs guardados.
3) Widget en vivo 'Correos de Solicitud - Hoy' para el dashboard del administrador.
"""
import re
import uuid
import base64
import asyncio
from datetime import datetime, timezone, timedelta
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
    """Resultado del caso: PRIORIDAD 1 la Fuente de Verdad de Mesa (resultado_mesa),
    PRIORIDAD 2 la última simulación del Motor por RUT."""
    if f.get("resultado_mesa") in ("aprobado", "reprobado"):
        return f["resultado_mesa"], str(f.get("resultado_mesa_at") or "")[:10]
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


# ────────────────── CONFIRMACIÓN DE ESCRITURACIÓN (desde el correo de aprobación) ──────────────────

def _pagina_confirm(titulo, mensaje, ok=True):
    color = "#d4af37" if ok else "#fb7185"
    icono = "&#10003;" if ok else "&#9888;"
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Central Mutuos</title></head>
<body style="margin:0;background:#050505;font-family:Arial,Helvetica,sans-serif;color:#e8e3d3">
<div style="max-width:560px;margin:8vh auto;padding:0 18px;text-align:center">
  <div style="font-family:Georgia,serif;letter-spacing:6px;color:#d4af37;font-size:20px;margin-bottom:6px">CENTRAL MUTUOS</div>
  <div style="color:#8a7a3a;font-size:10px;letter-spacing:4px;margin-bottom:36px">CON CRECES</div>
  <div style="border:1px solid rgba(212,175,55,0.4);background:#0c0c0c;padding:38px 30px">
    <div style="font-size:44px;color:{color};margin-bottom:14px">{icono}</div>
    <h1 style="margin:0 0 14px;font-size:22px;color:{color}">{titulo}</h1>
    <p style="margin:0;font-size:14.5px;line-height:1.8;color:#c9c4b4">{mensaje}</p>
  </div>
  <p style="margin-top:26px;font-size:11px;color:#6a6a6a">Especialistas en cr&eacute;ditos hipotecarios &middot; Ya puede cerrar esta ventana.</p>
</div></body></html>"""


@carpres.get("/escrituracion/confirmar/{token}")
async def escrituracion_confirmar(token: str):
    """Ruta PÚBLICA (link del correo de aprobación): registra la confirmación del
    cliente en su carpeta y notifica automáticamente al ejecutivo asignado."""
    from fastapi.responses import HTMLResponse
    doc = await db.escrituracion_confirmaciones.find_one({"token": token})
    if not doc:
        return HTMLResponse(_pagina_confirm("Enlace no válido",
                            "Este enlace de confirmaci&oacute;n no existe o ha expirado. "
                            "Por favor cont&aacute;ctese con su ejecutivo.", ok=False), status_code=404)
    nombre = doc.get("cliente") or "el cliente"
    if doc.get("usado"):
        fch = str(doc.get("confirmado_en") or "")[:16].replace("T", " ")
        return HTMLResponse(_pagina_confirm("Confirmaci&oacute;n ya registrada",
                            f"Su intenci&oacute;n de continuar con la escrituraci&oacute;n ya fue registrada el <b>{fch}</b> (UTC). "
                            "Su ejecutivo ya fue notificado — no es necesario volver a confirmar."))
    ahora = _now()
    hora_cl = datetime.now(ZoneInfo("America/Santiago")).strftime("%d/%m/%Y %H:%M")
    await db.escrituracion_confirmaciones.update_one(
        {"token": token}, {"$set": {"usado": True, "confirmado_en": ahora}})
    # Registrar en la carpeta del cliente (fecha y hora)
    f = None
    if doc.get("folder_id"):
        f = await db.folders.find_one({"id": doc["folder_id"]})
    if not f and nombre:
        toks = [t for t in re.split(r"\s+", nombre) if len(t) >= 3]
        if toks:
            f = await db.folders.find_one(
                {"$and": [{"nombre": {"$regex": re.escape(t), "$options": "i"}} for t in toks[:2]]})
    n_carpeta = (f or {}).get("id") or doc.get("folder_id") or "sin carpeta asociada"
    if f:
        await db.folders.update_one({"id": f["id"]}, {"$set": {
            "escrituracion_confirmada_at": ahora,
            "escrituracion_confirmada_via": "boton_correo_aprobacion",
            "escrituracion_confirmada_hora_cl": hora_cl}})
    # Notificar automáticamente al ejecutivo asignado
    destinos = []
    if f:
        eje = (f.get("ejecutivo_externo_email") or "").strip()
        if eje and "@" in eje:
            destinos.append(eje.lower())
        for d in await _destinos_ejecutivo(f):
            if d not in destinos:
                destinos.append(d)
    enviado_a = []
    if destinos:
        from server import _email_institucional
        import email_service as mail
        rut_txt = f" (RUT {doc.get('rut')})" if doc.get("rut") else ""
        cuerpo = (
            f"<p style='margin:0 0 12px'>El cliente <b>{nombre}</b>{rut_txt} "
            f"<b>confirm&oacute; su intenci&oacute;n de avanzar con el proceso de escrituraci&oacute;n</b> "
            f"presionando el bot&oacute;n de su correo de aprobaci&oacute;n.</p>"
            f"<p style='margin:0 0 12px'>N&uacute;mero de carpeta: <b>{n_carpeta}</b><br>"
            f"Fecha y hora de la confirmaci&oacute;n: <b>{hora_cl}</b> (hora de Chile)</p>"
            f"<p style='margin:0 0 12px'>Por favor contacte al cliente para coordinar los siguientes pasos.</p>")
        html = _email_institucional("Ejecutivo/a", cuerpo)
        r = await asyncio.to_thread(mail.send_mail, ", ".join(destinos),
                                    f"✅ Cliente confirma escrituración — {nombre}", html)
        if r.get("success"):
            enviado_a = destinos
    await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "escrituracion_confirmada", "leida": False,
                                 "cliente": nombre,
                                 "mensaje": (f"🖋️ {nombre} CONFIRMÓ continuar con la escrituración (carpeta {n_carpeta}, {hora_cl})"
                                             + (f" — ejecutivo notificado: {', '.join(enviado_a)}" if enviado_a
                                                else " — ⚠️ SIN correo de ejecutivo asociado, contactar manualmente")),
                                 "fecha": ahora})
    return HTMLResponse(_pagina_confirm("&iexcl;Confirmaci&oacute;n registrada!",
                        f"Gracias, <b>{nombre}</b>. Su intenci&oacute;n de continuar con el proceso de "
                        f"escrituraci&oacute;n qued&oacute; registrada el <b>{hora_cl}</b> (hora de Chile). "
                        "Su ejecutivo fue notificado y lo contactar&aacute; a la brevedad."))


# ────────────────── PANEL DE ESTADO EN CARPETA DE CLIENTE ──────────────────

def _dias_habiles_entre(desde, hasta):
    d, n = desde.date(), 0
    while d < hasta.date():
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


@carpres.get("/clientes/folders/{fid}/panel-estado")
async def panel_estado_folder(fid: str, request: Request):
    _exigir(request)
    f = await db.folders.find_one({"id": fid})
    if not f:
        raise HTTPException(status_code=404, detail="Carpeta no encontrada")
    from server import _criterios_folder
    nombre = f.get("nombre") or ""
    resultado, fecha_res = await _resultado_folder(f)
    # ENVIADO POR SISTEMA (autocorreo/mesa vía plataforma)
    log_sis = await db.autocorreo_log.find_one(
        {"cliente": {"$regex": f"^{re.escape(nombre[:25])}", "$options": "i"}, "status": "sent"},
        {"_id": 0, "processed_at": 1, "subject": 1, "attachments_info": 1}, sort=[("processed_at", -1)])
    env_sis = bool(f.get("mesa_enviado_at") or f.get("emails_sent_count") or log_sis)
    det_sis = {"fecha": str((log_sis or {}).get("processed_at") or f.get("mesa_enviado_at") or "")[:16].replace("T", " "),
               "destinatario": "Mesa de análisis (vía sistema)",
               "contenido": (log_sis or {}).get("subject") or "",
               "adjuntos": (log_sis or {}).get("attachments_info") or ""} if env_sis else None
    # ENVIADO POR CORREO (correo directo espejado en la casilla de mesa)
    from auditoria_mesa import _norm_tokens, _match_nombre, _rut_limpio
    ftoks, frut = _norm_tokens(nombre), _rut_limpio(f.get("rut"))
    det_cor, env_cor = None, False
    async for m in db.mesa_enviados.find({}, {"_id": 0, "cliente": 1, "nombre": 1, "rut": 1,
                                              "enviado_at": 1, "subject": 1}).sort("enviado_at", -1):
        mtoks, mrut = _norm_tokens(m.get("cliente") or m.get("nombre")), _rut_limpio(m.get("rut"))
        if (frut and mrut and frut == mrut) or _match_nombre(ftoks, mtoks):
            env_cor = True
            det_cor = {"fecha": str(m.get("enviado_at") or "")[:16].replace("T", " "),
                       "destinatario": "Casilla de mesa (correo directo)",
                       "contenido": m.get("subject") or "", "adjuntos": ""}
            break
    # INACTIVIDAD: días hábiles sin movimiento
    hitos = [f.get(k) for k in ("updated_at", "mesa_enviado_at", "estudio_titulo_solicitado_at",
                                "tasacion_solicitada_at", "faltantes_pedidos_at",
                                "escrituracion_confirmada_at", "created_at")]
    ult = max((_dtp(h) for h in hitos if _dtp(h)), default=None)
    dias_par = _dias_habiles_entre(ult, datetime.now(timezone.utc)) if ult else 0
    # DOCUMENTOS FALTANTES (alertas específicas por perfil y mes)
    import validacion_documental as vdoc
    faltantes = vdoc.textos_faltantes(vdoc.validar_folder(f))
    if not faltantes:
        faltantes = [c["nombre"] for c in _criterios_folder(f)
                     if not c["ok"] and c["nombre"] not in ("Enviada a mesa", "Datos financieros completos")]
    return {"resultado": resultado, "fecha_resultado": fecha_res,
            "enviado_sistema": env_sis, "detalle_sistema": det_sis,
            "enviado_correo": env_cor, "detalle_correo": det_cor,
            "dias_sin_movimiento": dias_par, "alerta_inactividad": dias_par > 2,
            "documentos_faltantes": faltantes,
            "destinatario_solicitud": f.get("source_email") or "",
            "simulacion_desactualizada": bool(f.get("simulacion_desactualizada")),
            "simulacion_desactualizada_motivo": f.get("simulacion_desactualizada_motivo") or ""}


def _dtp(ts):
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


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
