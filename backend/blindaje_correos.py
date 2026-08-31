"""🛡️ BLINDAJE CORREOS V16 CENTRALIZADO — Clasificación por protocolo de crédito,
6 liquidaciones, enriquecimiento automático de carpeta y bandeja de autorización Admin.
REGLA DURA: ningún correo de faltantes sale sin autorización explícita del Administrador.
Envío: Resend dedicado si hay RESEND_API_KEY; si no, SMTP cuenta única gerardo.ext (confirmado)."""
import os
import re
import json
import uuid
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request
from database import db

blindaje = APIRouter(prefix="/blindaje")

ADJ_DIR = Path(__file__).parent / "storage" / "blindaje_adjuntos"
LIQ_KEYS = [f"liquidacion_{i}" for i in range(1, 7)]
RX_EMAIL = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
RX_RUT = re.compile(r"\b(\d{1,2}\.?\d{3}\.?\d{3}-?[\dkK])\b")

PROTOCOLOS = [
    {"id": "dependiente_simple", "nombre": "Dependiente Simple (6 liquidaciones)",
     "documentos_requeridos": LIQ_KEYS + ["certificado_antiguedad", "cedula", "cotizaciones_12", "contrato_trabajo"],
     "nunca_pedir": ["carpeta_tributaria_2_anos", "balance", "declaracion_iva_6m", "certificado_deudas", "boleta"],
     "modulo_mesa": "riesgo"},
    {"id": "independiente", "nombre": "Independiente (SII / Carpeta Tributaria)",
     "documentos_requeridos": ["carpeta_tributaria_2_anos", "balance", "cedula", "declaracion_iva_6m", "certificado_deudas"],
     "nunca_pedir": LIQ_KEYS + ["certificado_antiguedad", "contrato_trabajo", "cotizaciones_12"],
     "modulo_mesa": "riesgo"},
    {"id": "mixto", "nombre": "Mixto (liquidaciones + carpeta tributaria)",
     "documentos_requeridos": LIQ_KEYS + ["carpeta_tributaria_2_anos", "certificado_antiguedad", "cedula",
                                          "cotizaciones_12", "contrato_trabajo", "declaracion_iva_6m"],
     "nunca_pedir": [], "modulo_mesa": "riesgo"},
    {"id": "con_codeudor", "nombre": "Con Codeudor (12 liquidaciones)",
     "documentos_requeridos": ([f"liquidacion_{i}_titular" for i in range(1, 7)]
                               + [f"liquidacion_{i}_codeudor" for i in range(1, 7)]
                               + ["certificado_antiguedad_titular", "certificado_antiguedad_codeudor",
                                  "cedula_titular", "cedula_codeudor",
                                  "cotizaciones_12_titular", "cotizaciones_12_codeudor"]),
     "nunca_pedir": [], "modulo_mesa": "riesgo"},
    {"id": "con_licencia_medica", "nombre": "Con Licencia Médica",
     "documentos_requeridos": LIQ_KEYS + ["certificado_antiguedad", "cedula", "cotizaciones_12", "contrato_trabajo",
                                          "licencia_medica_detalle", "certificado_fonasa_licencias"],
     "nunca_pedir": ["carpeta_tributaria_2_anos", "balance", "declaracion_iva_6m"],
     "modulo_mesa": "contralor"},
]
PROTO_IDS = {p["id"] for p in PROTOCOLOS}
DOC_LABELS = {
    "certificado_antiguedad": "Certificado de antigüedad laboral", "cedula": "Cédula de identidad (ambos lados)",
    "cotizaciones_12": "Cotizaciones AFP últimos 12 meses", "contrato_trabajo": "Contrato de trabajo",
    "carpeta_tributaria_2_anos": "Carpeta tributaria SII últimos 2 años", "balance": "Balance",
    "declaracion_iva_6m": "Declaraciones de IVA últimos 6 meses", "certificado_deudas": "Certificado de deudas",
    "licencia_medica_detalle": "Detalle de licencia médica", "certificado_fonasa_licencias": "Certificado FONASA de licencias",
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _label(doc):
    if doc.startswith("liquidacion_"):
        suf = " (titular)" if doc.endswith("_titular") else " (codeudor)" if doc.endswith("_codeudor") else ""
        num = re.search(r"liquidacion_(\d)", doc)
        return f"Liquidación de sueldo #{num.group(1) if num else '?'}{suf}"
    return DOC_LABELS.get(doc, doc.replace("_", " ").capitalize())


def _rol(request):
    return (getattr(request.state, "user", {}) or {}).get("rol", "")


def _exigir(request, roles=("admin", "maestro")):
    if _rol(request) not in roles:
        raise HTTPException(status_code=403, detail="Solo el Administrador puede acceder al Blindaje de Correos")


def _norm_rut(r):
    return re.sub(r"[^0-9kK]", "", str(r or "")).lower()


async def _log(evento, detalle=None, correo_salida_id="", correo_entrada_id=""):
    await db.correos_blindaje_log.insert_one({
        "id": str(uuid.uuid4()), "evento": evento, "detalle": detalle or {},
        "correo_salida_id": correo_salida_id, "correo_entrada_id": correo_entrada_id,
        "created_at": _now()})


async def seed_blindaje():
    for p in PROTOCOLOS:
        await db.credito_protocolos_tipo.update_one(
            {"id": p["id"]}, {"$set": {**p, "activo": True, "updated_at": _now()}}, upsert=True)
    await db.config.update_one({"_key": "blindaje_config"}, {"$setOnInsert": {
        "from_email": os.environ.get("MAIL2_USER", "gerardo.ext@centralmutuos.cl"),
        "from_name": "Gerardo - Central Mutuos - Súper Carpeta",
        "liquidaciones_requeridas": 6, "creado": _now()}}, upsert=True)
    try:
        await db.correos_clasificacion.create_index("message_id", unique=True)
        await db.clientes_carpetas_documentos.create_index([("caso_id", 1), ("documento_tipo", 1)], unique=True)
        await db.clientes_carpetas_documentos.create_index([("caso_id", 1), ("estado", 1)])
        await db.correos_salida_cola_blindada.create_index([("estado", 1), ("reintento_at", 1)])
        await db.correos_autorizacion_admin.create_index([("estado", 1), ("created_at", -1)])
    except Exception as e:
        logging.warning(f"blindaje índices: {e}")
    logging.info("🛡️ Blindaje V16: 5 protocolos de crédito sembrados")


# ═══════════════ CLASIFICACIÓN CLAUDE (determinística, temperatura baja) ═══════════════
_SISTEMA_CLASIF = (
    "Eres el clasificador de protocolos de crédito de Central Mutuos (Chile, Súper Carpeta). "
    "Clasifica el protocolo: dependiente_simple (solo liquidaciones de sueldo, SIN carpeta tributaria), "
    "independiente (solo SII: carpeta tributaria/balance/IVA, SIN liquidaciones), "
    "mixto (liquidaciones + carpeta tributaria), "
    "con_codeudor (detecta 2 RUTs o palabras codeudor/aval/segundo deudor/complemento de renta), "
    "con_licencia_medica (palabras licencia médica/reposo/subsidio FONASA/incapacidad). "
    "Extrae RUT chileno formato 12.345.678-9 y nombre del cliente. "
    "Por CADA adjunto detecta su tipo: liquidacion_1..liquidacion_6 (detecta mes YYYY-MM del nombre), "
    "cedula, cotizaciones_12, contrato_trabajo, certificado_antiguedad, carpeta_tributaria_2_anos, balance, "
    "declaracion_iva_6m, certificado_deudas, licencia_medica_detalle, certificado_fonasa_licencias, otro. "
    "Si un PDF parece contener VARIAS liquidaciones juntas, marca es_pdf_con_multiples_liquidaciones=true y cantidad. "
    "clasificacion: solicitud_credito|aprobacion_banco|tasacion|reparo_cbr|vale_vista|sede_firmada|desistimiento|"
    "documentacion_faltante|otro. INTEGRIDAD: no inventes RUT ni nombre; si no aparecen, deja ''. "
    "Responde SOLO JSON válido sin markdown: {\"protocolo_detectado\": \"\", \"clasificacion\": \"\", "
    "\"cliente_rut\": \"\", \"cliente_nombre\": \"\", \"confianza\": 0, "
    "\"documentos_adjuntos_detectados\": [{\"filename\": \"\", \"tipo_detectado\": \"\", \"mes\": \"\", "
    "\"es_pdf_con_multiples_liquidaciones\": false, \"cantidad_liquidaciones_en_pdf\": 0}], "
    "\"tiene_licencia_medica\": false, \"tiene_codeudor\": false, \"es_mixto\": false, "
    "\"palabras_clave_detectadas\": [], \"justificacion\": \"\"}")


async def clasificar_protocolo(remitente, asunto, body, adjuntos_nombres):
    key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not key or os.environ.get("AI_EMERGENCY_STOP") == "1":
        return {}
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import ai_extract as _aix
        chat = LlmChat(api_key=key, session_id=f"blindaje-{uuid.uuid4()}",
                       system_message=_SISTEMA_CLASIF).with_model("anthropic", "claude-sonnet-4-6")
        um = UserMessage(text=(f"DE: {remitente}\nASUNTO: {asunto}\n"
                               f"ADJUNTOS: {', '.join(adjuntos_nombres or []) or '(sin adjuntos)'}\n\n"
                               f"BODY:\n{(body or '')[:2000]}"))
        resp = await _aix._enviar(chat, um)
        raw = resp if isinstance(resp, str) else str(resp)
        m = re.search(r"\{.*\}", raw, re.S)
        d = json.loads(m.group(0)) if m else {}
        if d.get("protocolo_detectado") not in PROTO_IDS:
            d["protocolo_detectado"] = ("con_codeudor" if d.get("tiene_codeudor")
                                        else "con_licencia_medica" if d.get("tiene_licencia_medica")
                                        else "mixto" if d.get("es_mixto") else "dependiente_simple")
        return d
    except Exception as e:
        logging.warning(f"blindaje clasificación Claude: {str(e)[:150]}")
        return {}


# ═══════════════ CARPETA: creación determinística + enriquecimiento auto ═══════════════
async def _obtener_caso(rut, nombre, protocolo_id):
    """1 cliente = 1 RUT = 1 caso. Reutiliza la carpeta real (folders) si existe."""
    rn = _norm_rut(rut)
    if rn:
        prev = await db.clientes_carpetas_documentos.find_one({"cliente_rut_norm": rn}, {"caso_id": 1})
        if prev:
            return prev["caso_id"], False
        fd = None
        async for f in db.folders.find({"rut": {"$exists": True, "$ne": ""}}, {"id": 1, "rut": 1}).limit(1500):
            if _norm_rut(f.get("rut")) == rn:
                fd = f
                break
        if fd:
            return fd["id"], False
    caso = await db.blindaje_casos.find_one({"cliente_rut_norm": rn}) if rn else None
    if caso:
        return caso["id"], False
    cid = str(uuid.uuid4())
    await db.blindaje_casos.insert_one({
        "id": cid, "cliente_nombre": nombre or "", "cliente_rut": rut or "",
        "cliente_rut_norm": rn, "protocolo_id": protocolo_id, "estado": "en_proceso", "created_at": _now()})
    return cid, True


async def _asegurar_docs(caso_id, rut, protocolo_id):
    proto = await db.credito_protocolos_tipo.find_one({"id": protocolo_id}) or PROTOCOLOS[0]
    for doc in proto["documentos_requeridos"]:
        await db.clientes_carpetas_documentos.update_one(
            {"caso_id": caso_id, "documento_tipo": doc},
            {"$setOnInsert": {"id": str(uuid.uuid4()), "cliente_rut": rut or "",
                              "cliente_rut_norm": _norm_rut(rut), "protocolo_id": protocolo_id,
                              "estado": "faltante", "fuente": "", "created_at": _now(), "updated_at": _now()}},
            upsert=True)
    return proto


async def _marcar_recibido(caso_id, documento_tipo, correo_id, url, filename, mes=""):
    r = await db.clientes_carpetas_documentos.update_one(
        {"caso_id": caso_id, "documento_tipo": documento_tipo,
         "estado": {"$nin": ["recibido", "recibido_por_correo_auto", "validado"]}},
        {"$set": {"estado": "recibido_por_correo_auto", "fuente": "correo_entrada_auto",
                  "correo_origen_id": correo_id, "url_archivo": url, "nombre_archivo": filename,
                  "mes_detectado": mes or "", "updated_at": _now()}})
    return r.modified_count > 0


async def _enriquecer(caso_id, rut, protocolo_id, adjuntos_det, correo_id, urls):
    """Enriquecimiento automático: por cada adjunto detectado marca el doc como recibido."""
    enriquecidos = []
    con_sufijo = protocolo_id == "con_codeudor"
    for a in adjuntos_det or []:
        tipo = (a.get("tipo_detectado") or "").strip()
        fn = a.get("filename") or ""
        url = urls.get(fn, "")
        mes = (a.get("mes") or "")[:7]
        if not tipo or tipo == "otro":
            continue
        if tipo.startswith("liquidacion"):
            n_multi = int(a.get("cantidad_liquidaciones_en_pdf") or 0) if a.get("es_pdf_con_multiples_liquidaciones") else 1
            suf = "_titular" if con_sufijo and "codeudor" not in fn.lower() else ("_codeudor" if con_sufijo else "")
            llenados = 0
            for i in range(1, 7):
                if llenados >= max(1, n_multi):
                    break
                if await _marcar_recibido(caso_id, f"liquidacion_{i}{suf}", correo_id, url, fn, mes):
                    llenados += 1
                    enriquecidos.append(f"liquidacion_{i}{suf}")
        else:
            base = tipo
            if con_sufijo and not tipo.endswith(("_titular", "_codeudor")):
                base = tipo + ("_codeudor" if "codeudor" in fn.lower() else "_titular")
            if await _marcar_recibido(caso_id, base, correo_id, url, fn, mes):
                enriquecidos.append(base)
            elif base != tipo and await _marcar_recibido(caso_id, tipo, correo_id, url, fn, mes):
                enriquecidos.append(tipo)
    return enriquecidos


async def _estado_carpeta(caso_id, protocolo_id):
    """Cálculo DETERMINÍSTICO de faltantes. Regla anti-mezcla: jamás pedir docs prohibidos
    del protocolo ni docs ya recibidos."""
    proto = await db.credito_protocolos_tipo.find_one({"id": protocolo_id}) or {}
    prohibidos = set(proto.get("nunca_pedir") or [])
    tiene, faltan, meses = [], [], []
    async for d in db.clientes_carpetas_documentos.find({"caso_id": caso_id}):
        if d["estado"] in ("recibido", "recibido_por_correo_auto", "validado"):
            tiene.append(d["documento_tipo"])
            if d.get("mes_detectado"):
                meses.append(d["mes_detectado"])
        elif d["documento_tipo"] not in prohibidos:
            faltan.append(d["documento_tipo"])
    liq_tiene = sum(1 for t in tiene if t.startswith("liquidacion"))
    liq_faltan = sum(1 for t in faltan if t.startswith("liquidacion"))
    return {"tiene": sorted(tiene), "faltan": sorted(faltan), "liq_tiene": liq_tiene,
            "liq_faltan": liq_faltan, "meses_tiene": sorted(set(meses)),
            "modulo_mesa": proto.get("modulo_mesa", "riesgo")}


# ═══════════════ GENERADOR DE CORREO DE FALTANTES (propone, JAMÁS envía solo) ═══════════
async def _generar_correo_faltantes(nombre, rut, protocolo_id, est):
    faltan_labels = [_label(d) for d in est["faltan"]]
    tiene_labels = [_label(d) for d in est["tiene"]]
    asunto = (f"Documentación pendiente - {nombre or rut} - Faltan {len(est['faltan'])} documento(s)"
              + (f" ({est['liq_faltan']} liquidaciones)" if est["liq_faltan"] else ""))
    lista = "".join(f"<li>{d}</li>" for d in faltan_labels)
    cuerpo = (f"<div style='font-family:Arial,sans-serif;font-size:14px;color:#222'>"
              f"<p>Estimado(a),</p>"
              f"<p>Junto con saludar, y para continuar con la evaluación del crédito hipotecario de "
              f"<b>{nombre or 'su cliente'}</b>{f' (RUT {rut})' if rut else ''}, necesitamos que nos haga llegar "
              f"la siguiente documentación pendiente:</p><ul>{lista}</ul>"
              + (f"<p>A la fecha hemos recibido correctamente: {', '.join(tiene_labels)}.</p>" if tiene_labels else "")
              + "<p>Quedamos atentos a su respuesta para avanzar a la brevedad.</p>"
                "<p>Saludos cordiales,<br><b>Gerardo — Central Mutuos</b></p></div>")
    key = os.environ.get("EMERGENT_LLM_KEY", "")
    if key and os.environ.get("AI_EMERGENCY_STOP") != "1":
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            import ai_extract as _aix
            chat = LlmChat(api_key=key, session_id=f"blindaje-gen-{uuid.uuid4()}",
                           system_message=("Redactas correos formales chilenos de Central Mutuos, firmados "
                                           "'Gerardo — Central Mutuos'. Tono formal cercano, lista clara en HTML. "
                                           "REGLA: pide SOLO los documentos de la lista FALTAN, jamás otros, "
                                           "jamás lo que ya tiene. Responde SOLO JSON {\"asunto\": \"\", \"body_html\": \"\"}"))\
                .with_model("anthropic", "claude-sonnet-4-6")
            um = UserMessage(text=(f"Cliente {nombre} RUT {rut} protocolo {protocolo_id}. "
                                   f"Liquidaciones: tiene {est['liq_tiene']}/6, faltan {est['liq_faltan']}. "
                                   f"TIENE: {', '.join(tiene_labels) or 'nada'}. "
                                   f"FALTAN: {', '.join(faltan_labels)}."))
            resp = await _aix._enviar(chat, um)
            m = re.search(r"\{.*\}", str(resp), re.S)
            d = json.loads(m.group(0)) if m else {}
            if d.get("body_html"):
                return (d.get("asunto") or asunto), d["body_html"]
        except Exception as e:
            logging.warning(f"blindaje generador Claude: {str(e)[:120]}")
    return asunto, cuerpo


async def _encolar_faltantes(caso_id, rut, nombre, protocolo_id, est, destinatario, clasif, correo_entrada_id):
    ya = await db.correos_autorizacion_admin.find_one({"caso_id": caso_id, "estado": "pendiente"})
    if ya and set(ya.get("documentos_faltan") or []) == set(est["faltan"]):
        return None
    asunto, body_html = await _generar_correo_faltantes(nombre, rut, protocolo_id, est)
    cola_id = str(uuid.uuid4())
    await db.correos_salida_cola_blindada.insert_one({
        "id": cola_id, "caso_id": caso_id, "cliente_rut": rut or "", "destinatario": destinatario,
        "asunto": asunto, "body_html": body_html, "tipo": "solicitud_documentos_faltantes",
        "protocolo_tipo": protocolo_id, "documentos_faltantes": est["faltan"],
        "liquidaciones_tiene": est["liq_tiene"], "liquidaciones_faltan": est["liq_faltan"],
        "estado": "pendiente_autorizacion", "requiere_autorizacion_admin": True,
        "from_email": os.environ.get("MAIL2_USER", "gerardo.ext@centralmutuos.cl"),
        "proveedor_envio": "resend_dedicado" if os.environ.get("RESEND_API_KEY") else "smtp_gerardo_ext",
        "intentos": 0, "created_at": _now()})
    await db.correos_autorizacion_admin.insert_one({
        "id": str(uuid.uuid4()), "correo_salida_id": cola_id, "caso_id": caso_id,
        "cliente_nombre": nombre or "", "cliente_rut": rut or "", "protocolo_detectado": protocolo_id,
        "clasificacion_ia": clasif.get("clasificacion") or "", "confianza_ia": float(clasif.get("confianza") or 0),
        "documentos_tiene": est["tiene"], "documentos_faltan": est["faltan"],
        "liquidaciones_tiene": est["liq_tiene"], "liquidaciones_faltan": est["liq_faltan"],
        "mensaje_propuesto": body_html, "correo_entrada_id": correo_entrada_id,
        "estado": "pendiente", "created_at": _now()})
    await _log("faltante_detectado_pendiente_autorizacion",
               {"caso_id": caso_id, "faltan": est["faltan"], "liq_faltan": est["liq_faltan"]}, cola_id, correo_entrada_id)
    return cola_id


# ═══════════════ PROCESAMIENTO DE UN CORREO ENTRANTE ═══════════════
async def procesar_correo(c):
    import email_service as mail
    message_id = c.get("id") or ""
    if not message_id or await db.correos_clasificacion.find_one({"message_id": message_id}):
        return None
    remitente = c.get("from") or c.get("sender") or ""
    asunto = c.get("subject") or ""
    body = (c.get("body") or "")[:2000]
    adj_meta = c.get("attachments") or []
    adj_nombres = [a.get("filename") or "" for a in adj_meta if a.get("filename")]
    clasif = await clasificar_protocolo(remitente, asunto, body, adj_nombres)
    if not clasif:
        return None
    rut = (clasif.get("cliente_rut") or "").strip()
    if not rut:
        m = RX_RUT.search(asunto + " " + body)
        rut = m.group(1) if m else ""
    nombre = (clasif.get("cliente_nombre") or "").strip()
    protocolo_id = clasif.get("protocolo_detectado") or "dependiente_simple"
    es_solicitud = clasif.get("clasificacion") in ("solicitud_credito", "documentacion_faltante")
    caso_previo = bool(rut) and bool(await db.clientes_carpetas_documentos.find_one({"cliente_rut_norm": _norm_rut(rut)}))
    reg = {"id": str(uuid.uuid4()), "message_id": message_id, "remitente": remitente[:200],
           "asunto": asunto[:250], "body_text": body[:1000], "fecha_recepcion": c.get("date") or _now(),
           "clasificacion": clasif.get("clasificacion") or "otro", "protocolo_detectado": protocolo_id,
           "cliente_rut": rut, "cliente_nombre": nombre, "confianza": float(clasif.get("confianza") or 0),
           "modelo_ia": "claude-sonnet-4-6", "documentos_tiene": [], "created_at": _now()}
    if not (es_solicitud or (caso_previo and adj_nombres)):
        await db.correos_clasificacion.insert_one(reg)
        await _log("entrante_clasificado", {"clasificacion": reg["clasificacion"], "accion": "sin_carpeta"},
                   correo_entrada_id=reg["id"])
        return reg
    caso_id, nuevo = await _obtener_caso(rut, nombre, protocolo_id)
    if caso_previo and not nuevo:
        doc0 = await db.clientes_carpetas_documentos.find_one({"caso_id": caso_id}, {"protocolo_id": 1})
        if doc0:
            protocolo_id = doc0.get("protocolo_id") or protocolo_id
    await _asegurar_docs(caso_id, rut, protocolo_id)
    urls = {}
    if adj_nombres:
        try:
            atts = await asyncio.to_thread(mail.fetch_attachments_by_id, message_id, None)
            base = ADJ_DIR / (_norm_rut(rut) or "sin_rut")
            base.mkdir(parents=True, exist_ok=True)
            for a in atts or []:
                fn = re.sub(r"[^\w.\-]+", "_", a.get("filename") or "adjunto.pdf")
                (base / fn).write_bytes(a.get("content_bytes") or b"")
                urls[a.get("filename") or fn] = str((base / fn).relative_to(ADJ_DIR.parent))
                try:
                    import bunker
                    bunker.subir_archivo_bg(base / fn)
                except Exception:
                    pass
        except Exception as e:
            logging.warning(f"blindaje adjuntos {message_id}: {str(e)[:120]}")
    enriquecidos = await _enriquecer(caso_id, rut, protocolo_id,
                                     clasif.get("documentos_adjuntos_detectados"), reg["id"], urls)
    if enriquecidos and not nuevo:
        await _log("carpeta_enriquecida", {"caso_id": caso_id, "docs": enriquecidos,
                                           "enriquecido_auto": True}, correo_entrada_id=reg["id"])
    est = await _estado_carpeta(caso_id, protocolo_id)
    reg.update({"caso_id": caso_id, "documentos_tiene": est["tiene"], "documentos_faltan": est["faltan"]})
    await db.correos_clasificacion.insert_one(dict(reg))
    await _log("entrante_clasificado", {"protocolo": protocolo_id, "caso_id": caso_id,
                                        "nuevo_caso": nuevo, "enriquecidos": enriquecidos}, correo_entrada_id=reg["id"])
    if not est["faltan"]:
        if not await db.mesa_entrada_bandeja.find_one({"caso_id": caso_id, "estado": "pendiente"}):
            await db.mesa_entrada_bandeja.insert_one({
                "id": str(uuid.uuid4()), "correo_id": reg["id"], "caso_id": caso_id,
                "protocolo_id": protocolo_id, "tipo": "carpeta_completa_lista_mesa",
                "prioridad": "alta", "estado": "pendiente", "modulo_asignado": est["modulo_mesa"],
                "requiere_accion": True, "sla_horas": 24,
                "vence_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
                "created_at": _now()})
            await _log("carpeta_completa_lista_mesa", {"caso_id": caso_id, "modulo": est["modulo_mesa"]},
                       correo_entrada_id=reg["id"])
    else:
        m = RX_EMAIL.search(remitente)
        if m:
            await _encolar_faltantes(caso_id, rut, nombre, protocolo_id, est, m.group(0), clasif, reg["id"])
    return reg


# ═══════════════ ENVÍO BLINDADO (Resend dedicado → fallback SMTP cuenta única) ═════════
FOOTER = ("<br><hr><p style='font-size:11px;color:#888'>Central Mutuos - Gerencia Comercial - "
          "gerardo.ext@centralmutuos.cl - Santiago, Chile</p>")


def _mx_ok(correo):
    try:
        import dns.resolver
        dom = correo.split("@")[1]
        return bool(dns.resolver.resolve(dom, "MX", lifetime=6))
    except Exception:
        return True


async def enviar_correo_blindado(cola_id):
    import email_service as mail
    reg = await db.correos_salida_cola_blindada.find_one({"id": cola_id})
    if not reg or reg["estado"] in ("enviado", "rebotado", "rechazado", "pendiente_autorizacion"):
        return {"ok": False, "motivo": "estado no enviable"}
    dest = (reg.get("destinatario") or "").strip()
    if not RX_EMAIL.fullmatch(dest) or not await asyncio.to_thread(_mx_ok, dest):
        await db.correos_salida_cola_blindada.update_one({"id": cola_id}, {"$set": {
            "estado": "rebotado", "ultimo_error": "destinatario inválido o sin MX"}})
        await _log("rebote", {"destinatario": dest}, cola_id)
        return {"ok": False, "motivo": "destinatario inválido"}
    html = (reg.get("body_html") or "") + FOOTER
    from_email = os.environ.get("MAIL2_USER", "gerardo.ext@centralmutuos.cl")
    from_name = "Gerardo - Central Mutuos - Súper Carpeta"
    rk = os.environ.get("RESEND_API_KEY", "")
    err = ""
    if rk:
        try:
            import requests as _rq
            r = await asyncio.to_thread(_rq.post, "https://api.resend.com/emails",
                                        headers={"Authorization": f"Bearer {rk}", "Content-Type": "application/json"},
                                        json={"from": f"{from_name} <{from_email}>", "to": [dest],
                                              "reply_to": from_email, "subject": reg["asunto"], "html": html,
                                              "tags": [{"name": "protocolo", "value": reg.get("protocolo_tipo") or "na"}]},
                                        timeout=30)
            if r.status_code in (200, 201):
                mid = (r.json() or {}).get("id", "")
                await db.correos_salida_cola_blindada.update_one({"id": cola_id}, {
                    "$set": {"estado": "enviado", "enviado_at": _now(), "provider_message_id": mid,
                             "proveedor_envio": "resend_dedicado"}, "$inc": {"intentos": 1}})
                await _log("envio_exitoso", {"provider": "resend", "message_id": mid,
                                             "anti_spam": "spf_dkim_dmarc"}, cola_id)
                return {"ok": True, "provider": "resend", "message_id": mid}
            err = f"resend {r.status_code}: {r.text[:150]}"
        except Exception as e:
            err = f"resend: {str(e)[:150]}"
    try:
        res = await asyncio.to_thread(
            lambda: mail.send_mail(dest, reg["asunto"], html, [], desde="secundaria",
                                   from_name=from_name, permitir_duplicado=False, confirmado=True))
        if res.get("success"):
            await db.correos_salida_cola_blindada.update_one({"id": cola_id}, {
                "$set": {"estado": "enviado", "enviado_at": _now(),
                         "provider_message_id": res.get("message_id", ""),
                         "proveedor_envio": "smtp_gerardo_ext"}, "$inc": {"intentos": 1}})
            await _log("envio_exitoso", {"provider": "smtp_gerardo_ext"}, cola_id)
            return {"ok": True, "provider": "smtp"}
        err = err or res.get("error", "smtp error")
    except Exception as e:
        err = err or str(e)[:200]
    intentos = int(reg.get("intentos") or 0) + 1
    estado = "rebotado" if intentos >= 5 else "error"
    await db.correos_salida_cola_blindada.update_one({"id": cola_id}, {"$set": {
        "estado": estado, "ultimo_error": err[:300],
        "reintento_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()},
        "$inc": {"intentos": 1}})
    await _log("error_envio", {"error": err[:200], "intentos": intentos}, cola_id)
    return {"ok": False, "motivo": err}


# ═══════════════ LOOPS: parser 90s + retry 3 min ═══════════════
async def blindaje_parser_loop():
    import email_service as mail
    await asyncio.sleep(120)
    while True:
        try:
            await db.config.update_one({"_key": "blindaje_heartbeat"},
                                       {"$set": {"ultimo_run": _now()}}, upsert=True)
            correos = await asyncio.to_thread(mail.fetch_recent_full, 15)
            for c in correos or []:
                try:
                    await procesar_correo(c)
                except Exception as e:
                    logging.warning(f"blindaje procesar {c.get('id')}: {str(e)[:150]}")
        except Exception as e:
            logging.warning(f"blindaje parser loop: {str(e)[:150]}")
        await asyncio.sleep(90)


async def blindaje_retry_loop():
    await asyncio.sleep(180)
    while True:
        try:
            ahora = _now()
            async for r in db.correos_salida_cola_blindada.find(
                    {"estado": {"$in": ["autorizado", "error"]}, "intentos": {"$lt": 5},
                     "$or": [{"reintento_at": None}, {"reintento_at": {"$exists": False}},
                             {"reintento_at": {"$lte": ahora}}]}).limit(10):
                await enviar_correo_blindado(r["id"])
            hace24 = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            async for a in db.correos_autorizacion_admin.find(
                    {"estado": "pendiente", "created_at": {"$lt": hace24}, "alerta_24h": {"$ne": True}}).limit(5):
                await db.correos_autorizacion_admin.update_one({"id": a["id"]}, {"$set": {"alerta_24h": True}})
                await db.dashai_eventos.insert_one({
                    "tipo": "correo_pendiente_autorizacion_24h", "fecha": _now(),
                    "detalle": f"Correo de faltantes para {a.get('cliente_nombre') or a.get('cliente_rut')} "
                               "lleva más de 24h esperando autorización del Admin"})
        except Exception as e:
            logging.warning(f"blindaje retry loop: {str(e)[:150]}")
        await asyncio.sleep(180)


# ═══════════════ RUTAS API ═══════════════
@blindaje.get("/autorizaciones")
async def autorizaciones_lista(request: Request):
    _exigir(request)
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pendientes = await db.correos_autorizacion_admin.find(
        {"estado": "pendiente"}, {"_id": 0}).sort("created_at", -1).to_list(100)
    aut_hoy = await db.correos_autorizacion_admin.count_documents(
        {"estado": "autorizado", "revisado_at": {"$gte": hoy}})
    pend_hoy = sum(1 for p in pendientes if (p.get("created_at") or "") >= hoy)
    tiempos = []
    async for a in db.correos_autorizacion_admin.find(
            {"estado": "autorizado", "revisado_at": {"$exists": True}}).sort("revisado_at", -1).limit(30):
        try:
            t0 = datetime.fromisoformat(a["created_at"])
            t1 = datetime.fromisoformat(a["revisado_at"])
            tiempos.append((t1 - t0).total_seconds() / 60)
        except Exception:
            pass
    return {"pendientes": pendientes, "kpis": {
        "pendientes_hoy": pend_hoy, "pendientes_total": len(pendientes), "autorizados_hoy": aut_hoy,
        "tiempo_promedio_min": round(sum(tiempos) / len(tiempos), 1) if tiempos else 0}}


async def _get_aut(aid):
    a = await db.correos_autorizacion_admin.find_one({"id": aid}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Autorización no encontrada")
    return a


@blindaje.post("/autorizaciones/{aid}/autorizar")
async def autorizar(aid: str, request: Request, payload: dict = None):
    _exigir(request)
    a = await _get_aut(aid)
    if a["estado"] != "pendiente":
        raise HTTPException(status_code=409, detail=f"Ya está en estado '{a['estado']}'")
    user = (getattr(request.state, "user", {}) or {}).get("nombre") or "admin"
    payload = payload or {}
    upd_cola = {"estado": "autorizado", "autorizado_por": user, "autorizado_at": _now()}
    if payload.get("asunto"):
        upd_cola["asunto"] = payload["asunto"][:250]
    if payload.get("body_html"):
        upd_cola["body_html"] = payload["body_html"]
    await db.correos_salida_cola_blindada.update_one({"id": a["correo_salida_id"]}, {"$set": upd_cola})
    await db.correos_autorizacion_admin.update_one({"id": aid}, {"$set": {
        "estado": "autorizado", "revisado_por": user, "revisado_at": _now()}})
    await _log("envio_autorizado", {"autorizado_por": user, "editado": bool(payload.get("body_html"))},
               a["correo_salida_id"])
    res = await enviar_correo_blindado(a["correo_salida_id"])
    return {"ok": True, "envio": res}


@blindaje.post("/autorizaciones/{aid}/rechazar")
async def rechazar(aid: str, request: Request):
    _exigir(request)
    a = await _get_aut(aid)
    user = (getattr(request.state, "user", {}) or {}).get("nombre") or "admin"
    await db.correos_autorizacion_admin.update_one({"id": aid}, {"$set": {
        "estado": "rechazado", "revisado_por": user, "revisado_at": _now()}})
    await db.correos_salida_cola_blindada.update_one({"id": a["correo_salida_id"]},
                                                     {"$set": {"estado": "rechazado"}})
    await _log("envio_rechazado", {"rechazado_por": user}, a["correo_salida_id"])
    return {"ok": True}


@blindaje.get("/autorizaciones/{aid}/correo-original")
async def correo_original(aid: str, request: Request):
    _exigir(request)
    a = await _get_aut(aid)
    c = await db.correos_clasificacion.find_one({"id": a.get("correo_entrada_id")}, {"_id": 0})
    return {"correo": c or {}}


@blindaje.get("/casos/{caso_id}/carpeta")
async def carpeta_caso(caso_id: str, request: Request):
    _exigir(request)
    docs = await db.clientes_carpetas_documentos.find(
        {"caso_id": caso_id}, {"_id": 0}).sort("documento_tipo", 1).to_list(60)
    for d in docs:
        d["label"] = _label(d["documento_tipo"])
    return {"documentos": docs}


@blindaje.get("/dashboard")
async def dashboard(request: Request):
    _exigir(request)
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entrantes = await db.correos_clasificacion.count_documents({"created_at": {"$gte": hoy}})
    enriquecidas = await db.correos_blindaje_log.count_documents(
        {"evento": "carpeta_enriquecida", "created_at": {"$gte": hoy}})
    pend = await db.correos_autorizacion_admin.count_documents({"estado": "pendiente"})
    enviados = await db.correos_salida_cola_blindada.count_documents(
        {"estado": "enviado", "enviado_at": {"$gte": hoy}})
    rebotados = await db.correos_salida_cola_blindada.count_documents({"estado": "rebotado"})
    mesa = await db.mesa_entrada_bandeja.count_documents({"estado": "pendiente"})
    log = await db.correos_blindaje_log.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    cola = await db.correos_salida_cola_blindada.find(
        {}, {"_id": 0, "body_html": 0}).sort("created_at", -1).to_list(50)
    return {"kpis": {"entrantes_hoy": entrantes, "enriquecidas_hoy": enriquecidas,
                     "pendiente_autorizacion": pend, "enviados_hoy": enviados,
                     "rebotados": rebotados, "listas_mesa": mesa},
            "log": log, "cola": cola, "checklist": await _checklist_dns()}


async def _checklist_dns():
    def _txt(nombre):
        try:
            import dns.resolver
            return [str(r).strip('"') for r in dns.resolver.resolve(nombre, "TXT", lifetime=6)]
        except Exception:
            return []
    dom = "centralmutuos.cl"
    spf = await asyncio.to_thread(_txt, dom)
    dmarc = await asyncio.to_thread(_txt, f"_dmarc.{dom}")
    dkim_g = await asyncio.to_thread(_txt, f"google._domainkey.{dom}")
    dkim_r = await asyncio.to_thread(_txt, f"resend._domainkey.{dom}")
    spf_rec = next((t for t in spf if t.lower().startswith("v=spf1")), "")
    return [
        {"item": "SPF del dominio", "ok": bool(spf_rec), "detalle": spf_rec or "sin registro v=spf1"},
        {"item": "DKIM (Google Workspace)", "ok": bool(dkim_g), "detalle": "presente" if dkim_g else "no encontrado"},
        {"item": "DKIM (Resend)", "ok": bool(dkim_r), "detalle": "presente" if dkim_r else "no configurado (opcional)"},
        {"item": "DMARC", "ok": bool(dmarc), "detalle": (dmarc[0][:80] if dmarc else "sin _dmarc")},
        {"item": "Remitente único verificado", "ok": True, "detalle": "gerardo.ext@centralmutuos.cl (cuenta única constitucional)"},
        {"item": "Proveedor de envío", "ok": True,
         "detalle": "Resend dedicado" if os.environ.get("RESEND_API_KEY") else "SMTP Gmail Workspace directo (0 dependencia Emergent)"},
        {"item": "Supresión de rebotes", "ok": True, "detalle": "automática a los 5 intentos o MX inválido"},
    ]


@blindaje.post("/procesar-ahora")
async def procesar_ahora(request: Request):
    _exigir(request)
    cool = await db.config.find_one({"_key": "blindaje_procesar_cooldown"}) or {}
    if (cool.get("ultimo") or "") > (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat():
        raise HTTPException(status_code=429, detail="Espera 1 minuto entre procesamientos manuales (ahorro IA/IMAP)")
    await db.config.update_one({"_key": "blindaje_procesar_cooldown"}, {"$set": {"ultimo": _now()}}, upsert=True)
    import email_service as mail
    correos = await asyncio.to_thread(mail.fetch_recent_full, 10)
    procesados = []
    for c in correos or []:
        try:
            r = await procesar_correo(c)
            if r:
                procesados.append({"asunto": r["asunto"], "protocolo": r["protocolo_detectado"],
                                   "clasificacion": r["clasificacion"]})
        except Exception as e:
            logging.warning(f"blindaje manual {c.get('id')}: {str(e)[:120]}")
    return {"procesados": procesados, "total_revisados": len(correos or [])}


@blindaje.get("/protocolos")
async def protocolos_lista(request: Request):
    _exigir(request)
    ps = await db.credito_protocolos_tipo.find({}, {"_id": 0}).to_list(10)
    return {"protocolos": ps}
