"""⚖️ REGLA CONSTITUCIONAL — FUENTE DE VERDAD DE MESA (aprobaciones@centralmutuos.cl)
Monitoreo permanente y autónomo del canal oficial de mesa. Clasificación 100% LOCAL
(regex, sin consumo de IA): aprobación, rechazo, cambio de tasa, plazo o criterio.
- Aprobación/Rechazo → actualiza la carpeta y activa los botones de envío al ejecutivo.
- Cambio de tasa/plazo/criterio → registro + alerta dashboard + correo al administrador
  + todas las carpetas activas quedan marcadas 'Simulación desactualizada'.
- Todo correo procesado queda en db.mesa_verdad_log (fecha, hora, tipo, parámetros antes/después).
"""
import os
import re
import uuid
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from database import db

mesav = APIRouter(prefix="/mesa-verdad")

MESA_EMAIL = os.environ.get("MESA_EMAIL", "aprobaciones@centralmutuos.cl")
ROLES = ("admin", "maestro", "administracion", "gerencia", "contralor")
INTERVALO_SEG = 120

RX_CAMBIO = re.compile(r"cambio|nueva?s?\b|actualiza|ajust|modific|sube|baja|pasa a|queda en|rige|vigente", re.I)
RX_TASA = re.compile(r"\btasas?\b", re.I)
RX_PLAZO = re.compile(r"\bplazos?\b", re.I)
RX_CRITERIO = re.compile(r"criterios?|renta\s+m[ií]nima|carga\s+financiera|\bltv\b|financiamiento\s+m[aá]x|"
                         r"dividendo\s+m[aá]x|pol[ií]tica\s+de\s+evaluaci[oó]n|score", re.I)
RX_APROB = re.compile(r"tenemos\s+el\s+agrado\s+de\s+informar|califica\s+para\s+un\s+mutuo\s+hipotecari"
                      r"|mutuo\s+hipotecario\s+endosable|adjuntamos\s+carta\s+y\s+simulaci[oó]n"
                      r"|subsidio\s+estatal|\baprobad[oa]s?\b|pre-?aprobad|\bviable\b|curse|cursad", re.I)
RX_RECH = re.compile(r"no\s+cumple\s+(?:los\s+)?par[aá]metros\s+objetivos\s+m[ií]nimos"
                     r"|par[aá]metros\s+objetivos\s+m[ií]nimos\s+de\s+aprobaci[oó]n"
                     r"|\brechazad[oa]s?\b|\brechaz[oa]\b|no\s+califica|reprobad[oa]|no\s+aprobad|desistid"
                     r"|no\s+cumple|declinad|sobre.?endeud|excede\s+(la\s+)?(carga|renta)"
                     r"|pasad[oa]\s+en\s+carga|renta\s+insuficiente|no\s+procede", re.I)
RX_PCT = re.compile(r"\d{1,2}[.,]?\d{0,2}\s*%")
RX_ANIOS = re.compile(r"\d{1,2}\s*a[ñn]os", re.I)
RX_UF = re.compile(r"\d[\d.,]*\s*uf", re.I)
RX_ANULA = re.compile(r"favor\s+cancelar\s+(el\s+)?(email|correo|mail)\s+de\s+aprobaci[oó]n"
                      r"|cancelar\s+la?\s+aprobaci[oó]n|anular\s+la?\s+aprobaci[oó]n"
                      r"|se\s+anula\s+(la\s+)?aprobaci[oó]n|aprobaci[oó]n\s+(queda\s+)?anulad[oa]"
                      r"|dejar\s+sin\s+efecto\s+la\s+aprobaci[oó]n"
                      r"|no\s+considerar\s+la\s+aprobaci[oó]n", re.I)
VENTANA_ANTIANULACION_MIN = 45  # caso Viviana: la Mesa anuló una aprobación 13 min después


def _now():
    return datetime.now(timezone.utc).isoformat()


def _hora_cl():
    return datetime.now(ZoneInfo("America/Santiago")).strftime("%d/%m/%Y %H:%M")


def _clasificar(texto):
    """Clasificación LOCAL (sin IA). Prioridad: anulación > cambios estructurales > resultado."""
    if RX_ANULA.search(texto):
        return "anulacion"
    if RX_TASA.search(texto) and RX_CAMBIO.search(texto) and RX_PCT.search(texto):
        return "cambio_tasa"
    if RX_PLAZO.search(texto) and RX_CAMBIO.search(texto) and RX_ANIOS.search(texto):
        return "cambio_plazo"
    if RX_CRITERIO.search(texto) and RX_CAMBIO.search(texto):
        return "cambio_criterio"
    if RX_RECH.search(texto):
        return "rechazo"
    if RX_APROB.search(texto):
        return "aprobacion"
    return "otro"


def _parametros(texto):
    return {"tasas": RX_PCT.findall(texto)[:4], "plazos": RX_ANIOS.findall(texto)[:4],
            "montos_uf": RX_UF.findall(texto)[:4]}


def _norm_toks(s):
    import unicodedata
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return [t for t in re.split(r"[^a-z]+", s) if len(t) >= 3]


async def _buscar_carpeta(texto):
    """Correspondencia ESTRICTA (regla del usuario): nombre completo Y RUT deben coincidir.
    Si el correo trae RUT, el RUT de la carpeta debe calzar además del nombre.
    Si el correo NO trae RUT, se exige match FUERTE de nombre completo (todos los
    tokens principales presentes) para evitar falsos positivos."""
    ruts = set(re.sub(r"[^0-9kK]", "", r).lower()[:8]
               for r in re.findall(r"\d{1,2}\.?\d{3}\.?\d{3}-?[\dkK]", texto))
    toks_txt = set(_norm_toks(texto))
    async for f in db.folders.find({}, {"_id": 0, "id": 1, "nombre": 1, "rut": 1}):
        ft = _norm_toks(f.get("nombre"))
        if len(ft) < 2:
            continue
        coincidencias = sum(1 for t in ft if t in toks_txt)
        fr = re.sub(r"[^0-9kK]", "", f.get("rut") or "").lower()[:8]
        if ruts:                                   # el correo trae RUT → deben calzar AMBOS
            if coincidencias >= 2 and fr and fr in ruts:
                return f
            continue
        if coincidencias >= min(len(ft), 3):       # sin RUT en el correo → nombre completo fuerte
            return f
    return None


async def _param_anteriores(tipo):
    prev = await db.mesa_verdad_log.find_one({"tipo": tipo}, {"_id": 0, "parametros_nuevos": 1},
                                             sort=[("procesado_en", -1)])
    return (prev or {}).get("parametros_nuevos") or {}


async def _reenviar_aprobacion_gerardo(msg, f_caso, subject):
    """NORMATIVA CONSTITUCIONAL — FLUJO APROBACIÓN MESA (única excepción al resumen 8AM):
    reenvío INMEDIATO del correo de aprobación de MESA a gerardo.ext@centralmutuos.cl,
    cuerpo original ÍNTEGRO + PDF carta de aprobación y simulación (sin gastos operacionales)."""
    import base64
    import email_service as mail
    destino = "gerardo.ext@centralmutuos.cl"
    cuerpo_original = (msg.get("body") or msg.get("body_html_text") or msg.get("preview") or "").strip()
    nombre = (f_caso or {}).get("nombre") or ""
    adjuntos = []
    try:
        from server import _imap_descargar_adjuntos_cliente
        import pdf_service as pdfs
        if nombre:
            pares = await asyncio.to_thread(_imap_descargar_adjuntos_cliente, nombre)
            for fname, raw in (pares or [])[:6]:
                es_carta = bool(re.search(r"carta|aprobaci[oó]n", fname, re.I))
                if not es_carta and re.search(r"simulad|simulaci[oó]n", fname, re.I):
                    try:
                        raw, _o, _r = pdfs.dejar_primera_pagina(raw)  # sin gastos operacionales
                    except Exception:
                        pass
                adjuntos.append({"filename": fname, "content_b64": base64.b64encode(raw).decode()})
    except Exception as e:
        logging.warning(f"flujo aprobacion mesa adjuntos: {e}")
    html = (f"<p style='margin:0 0 10px'><b>APROBACIÓN DE MESA</b> — reenvío automático constitucional "
            f"({MESA_EMAIL}){' · Cliente: <b>' + nombre + '</b>' if nombre else ''}</p>"
            f"<hr style='border:none;border-top:1px solid #d4af37;margin:10px 0'>"
            f"<div style='white-space:pre-wrap'>{cuerpo_original}</div>")
    res = await asyncio.to_thread(mail.send_mail, destino, f"✅ APROBACIÓN MESA — {subject[:140]}",
                                  html, adjuntos, "principal")
    return {"ok": bool(res.get("success")), "adjuntos": len(adjuntos), "error": res.get("error")}


def _huella_msg(msg, subject, body):
    """Huella de CONTENIDO (idéntica aunque el correo llegue a varias cuentas IMAP)."""
    import hashlib
    base = (f"{(msg.get('from') or '').strip().lower()}|{subject.strip().lower()}|"
            f"{str(msg.get('date') or '')[:25]}|{body[:500]}")
    return hashlib.sha256(base.encode()).hexdigest()


async def _procesar_correo(msg):
    mid = msg.get("id") or ""
    if not mid:
        return None
    subject = msg.get("subject") or ""
    # cuerpo completo: texto plano + texto extraído del HTML (nunca solo el asunto)
    body = f"{msg.get('body') or msg.get('body_full') or msg.get('preview') or ''}\n{msg.get('body_html_text') or ''}"[:8000]
    # ⛡ CERROJO ATÓMICO ANTI-DUPLICADOS (Regla de Oro #68): el registro se RESERVA
    # ANTES de reenviar. Dedup por UID (correo_id) Y por huella de contenido, para
    # que el mismo correo llegado a 2 cuentas o un barrido paralelo jamás se repita.
    huella = _huella_msg(msg, subject, body)
    if await db.mesa_verdad_log.find_one({"$or": [{"correo_id": mid}, {"huella": huella}]}):
        return None
    try:
        await db.mesa_verdad_log.insert_one({
            "id": str(uuid.uuid4()), "correo_id": mid, "huella": huella,
            "tipo": "procesando", "subject": subject[:200], "procesado_en": _now()})
    except Exception:
        return None  # índice único de huella: otro proceso ya lo reservó
    texto = f"{subject}\n{body}"
    tipo = _clasificar(texto)
    # REGLA ANTI-FALSO-POSITIVO: si el correo corresponde a un CASO de cliente
    # (carpeta coincidente), NUNCA es un cambio estructural global.
    f_caso = await _buscar_carpeta(texto)
    if tipo.startswith("cambio_") and f_caso:
        tipo = "aprobacion" if RX_APROB.search(texto) else ("rechazo" if RX_RECH.search(texto) else "otro")
    registro = {"correo_id": mid, "huella": huella, "tipo": tipo,
                "subject": subject[:200], "sender": msg.get("from") or MESA_EMAIL,
                "fecha_correo": str(msg.get("date") or "")[:25],
                "procesado_en": _now(), "hora_cl": _hora_cl(),
                "parametros_nuevos": _parametros(texto), "parametros_anteriores": {},
                "folder_id": "", "accion": ""}
    if tipo in ("aprobacion", "rechazo"):
        f = f_caso
        if tipo == "aprobacion":
            # ⏳ VENTANA ANTI-ANULACIÓN: el reenvío al ejecutivo se programa (no inmediato)
            # para captar cancelaciones de la Mesa (caso Viviana: anulada 13 min después).
            try:
                cfg_v = await db.config.find_one({"_key": "mesa_verdad"}) or {}
                ventana_min = int(cfg_v.get("ventana_antianulacion_min") or VENTANA_ANTIANULACION_MIN)
                notificar_en = (datetime.now(timezone.utc) + timedelta(minutes=ventana_min)).isoformat()
                await db.aprobaciones_en_espera.insert_one({
                    "id": str(uuid.uuid4()), "estado": "en_espera",
                    "folder_id": (f_caso or {}).get("id", ""), "cliente": (f_caso or {}).get("nombre", ""),
                    "subject": subject[:200], "correo_id": mid,
                    "msg": {"from": msg.get("from"), "date": str(msg.get("date") or "")[:25],
                            "body": (msg.get("body") or msg.get("body_html_text") or msg.get("preview") or "")[:6000]},
                    "creado": _now(), "notificar_despues": notificar_en, "ventana_min": ventana_min})
                registro["ventana_antianulacion"] = {"min": ventana_min, "notificar_despues": notificar_en}
                registro["accion"] = (f"⏳ Ventana anti-anulación: reenvío a gerardo.ext programado "
                                      f"en {ventana_min} min ({notificar_en[:16]}Z). ")
            except Exception as e:
                logging.warning(f"ventana anti-anulación: {e}")
                # Respaldo: si la cola falla, se reenvía de inmediato (flujo constitucional)
                fw = await _reenviar_aprobacion_gerardo(msg, f_caso, subject)
                registro["reenvio_gerardo"] = fw
                registro["accion"] = (f"Reenvío constitucional inmediato (cola falló) "
                                      f"({'OK' if fw.get('ok') else 'FALLÓ'}). ")
        if f:
            resultado = "aprobado" if tipo == "aprobacion" else "reprobado"
            await db.folders.update_one({"id": f["id"]}, {"$set": {
                "resultado_mesa": resultado, "resultado_mesa_at": _now(),
                "resultado_mesa_fuente": MESA_EMAIL, "resultado_mesa_asunto": subject[:200],
                "resultado_mesa_texto": body.strip()[:4000]}})
            registro["folder_id"] = f["id"]
            registro["accion"] = (registro.get("accion") or "") + f"Carpeta {f.get('nombre')} → {resultado.upper()} (botones de envío al ejecutivo activados)"
            if tipo == "rechazo":
                # 📩 NOTIFICACIÓN AUTOMÁTICA DE RECHAZO al ejecutivo (comunicación directa,
                # sin mencionar el canal de origen). Plantilla fija aprobada por el Admin.
                try:
                    import rechazo_notificacion as _rn
                    rn = await _rn.procesar_rechazo(f, body, subject)
                    registro["notificacion_rechazo"] = rn
                    registro["accion"] += (f" · Notificación al ejecutivo "
                                           f"{'ENVIADA a ' + str(rn.get('destinatario')) if rn.get('enviado') else 'en espera de diseño aprobado'}")
                except Exception as e:
                    logging.warning(f"notificación rechazo: {e}")
            await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "mesa_verdad", "leida": False,
                                         "cliente": f.get("nombre"),
                                         "mensaje": f"⚖️ MESA ({MESA_EMAIL}): {f.get('nombre')} → {resultado.upper()} — botón de envío al ejecutivo ACTIVADO",
                                         "fecha": _now()})
            # MARTÍN PROACTIVO: aviso hablado al administrador sin abrir el chat
            await db.martin_avisos.insert_one({
                "id": str(uuid.uuid4()), "tipo": f"mesa_{resultado}",
                "cliente": f.get("nombre"), "estado": "pendiente", "creado": _now(),
                "mensaje": (f"Atención jefe: llegó el veredicto de mesa para {f.get('nombre')}. "
                            + (f"¡Fue aprobada! El aviso al ejecutivo quedó programado por la ventana "
                               f"anti-anulación ({registro.get('ventana_antianulacion', {}).get('min', VENTANA_ANTIANULACION_MIN)} minutos)."
                               if resultado == "aprobado"
                               else "Fue reprobada. Te recomiendo revisar la carpeta y sus reparos."))})
        else:
            registro["accion"] = (registro.get("accion") or "") + "Sin carpeta coincidente — requiere revisión manual"
    elif tipo == "anulacion":
        # 🚫 ANULACIÓN DE APROBACIÓN (caso Viviana): cancelar el reenvío pendiente y revertir
        pend = None
        if f_caso:
            pend = await db.aprobaciones_en_espera.find_one({"folder_id": f_caso["id"], "estado": "en_espera"})
        if not pend:
            subj_n = re.sub(r"^(re|rv|fwd?)\s*:\s*", "", subject.strip(), flags=re.I).lower()[:60]
            for p in await db.aprobaciones_en_espera.find({"estado": "en_espera"}).sort("creado", -1).to_list(20):
                p_n = re.sub(r"^(re|rv|fwd?)\s*:\s*", "", (p.get("subject") or "").strip(), flags=re.I).lower()[:60]
                if subj_n and p_n and (subj_n in p_n or p_n in subj_n):
                    pend = p
                    break
        if pend:
            await db.aprobaciones_en_espera.update_one({"id": pend["id"]}, {"$set": {
                "estado": "anulada", "anulada_en": _now(), "anulada_por_correo": mid,
                "motivo_anulacion": subject[:200]}})
            registro["accion"] = (f"🚫 APROBACIÓN ANULADA por la Mesa dentro de la ventana anti-anulación: "
                                  f"reenvío a gerardo.ext CANCELADO ({pend.get('cliente') or pend.get('subject', '')[:60]})")
        else:
            registro["accion"] = "🚫 Anulación recibida SIN aprobación pendiente en la ventana — revisar manualmente"
        fid_an = (f_caso or {}).get("id") or (pend or {}).get("folder_id") or ""
        cliente_an = (f_caso or {}).get("nombre") or (pend or {}).get("cliente") or subject[:60]
        if fid_an:
            await db.folders.update_one({"id": fid_an}, {"$set": {
                "resultado_mesa": "anulado", "resultado_mesa_at": _now(),
                "resultado_mesa_fuente": MESA_EMAIL, "resultado_mesa_asunto": subject[:200]}})
            registro["folder_id"] = fid_an
        await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "mesa_verdad_anulacion",
                                     "nivel": "critica", "leida": False, "cliente": cliente_an,
                                     "folder_id": fid_an,
                                     "mensaje": (f"🚫 MESA ANULÓ UNA APROBACIÓN — {cliente_an}: «{subject[:110]}». "
                                                 + ("Reenvío al ejecutivo cancelado a tiempo por la ventana anti-anulación."
                                                    if pend else "No había reenvío pendiente: verificar si el ejecutivo ya fue notificado.")),
                                     "fecha": _now()})
        await db.martin_avisos.insert_one({
            "id": str(uuid.uuid4()), "tipo": "mesa_anulacion", "cliente": cliente_an,
            "estado": "pendiente", "creado": _now(),
            "mensaje": (f"Ojo jefe: la Mesa ANULÓ la aprobación de {cliente_an}. "
                        + ("Alcancé a frenar el aviso al ejecutivo." if pend
                           else "Revisa si el ejecutivo ya fue avisado, porque no había reenvío pendiente."))})
    elif tipo in ("cambio_tasa", "cambio_plazo", "cambio_criterio"):
        registro["parametros_anteriores"] = await _param_anteriores(tipo)
        etiqueta = {"cambio_tasa": "CAMBIO DE TASA", "cambio_plazo": "CAMBIO DE PLAZO",
                    "cambio_criterio": "CAMBIO DE CRITERIO DE EVALUACIÓN"}[tipo]
        r = await db.folders.update_many(
            {"descartada": {"$ne": True}},
            {"$set": {"simulacion_desactualizada": True,
                      "simulacion_desactualizada_motivo": f"{etiqueta} informado por mesa — {subject[:120]}",
                      "simulacion_desactualizada_at": _now()}})
        registro["accion"] = f"{etiqueta}: {r.modified_count} carpeta(s) activas marcadas 'Simulación desactualizada'"
        await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "mesa_verdad_cambio", "nivel": "critica",
                                     "leida": False,
                                     "mensaje": (f"🚨 {etiqueta} desde {MESA_EMAIL} — '{subject[:110]}' · "
                                                 f"nuevos: {registro['parametros_nuevos']} · "
                                                 f"{r.modified_count} carpeta(s) → Simulación desactualizada"),
                                     "fecha": _now()})
        # Correo de notificación al administrador — sujeto a NORMATIVA CORREOS:
        # durante el día solo se registra; el cambio viaja en el Resumen Diario 8AM.
        try:
            from resumen_diario import notificaciones_permitidas, registrar_omitido
            from server import _email_institucional
            import email_service as mail
            admin_to = os.environ.get("MAIL2_USER") or os.environ.get("MAIL_NOTIF_TEST") or ""
            if admin_to and not await notificaciones_permitidas():
                await registrar_omitido("mesa_verdad", f"{etiqueta} — {subject[:140]}")
            elif admin_to:
                nuevos = registro["parametros_nuevos"]
                antes = registro["parametros_anteriores"]
                cuerpo = (
                    f"<p style='margin:0 0 12px'>La mesa ({MESA_EMAIL}) inform&oacute; un <b>{etiqueta}</b>.</p>"
                    f"<p style='margin:0 0 12px'>Asunto: <b>{subject[:150]}</b><br>"
                    f"Fecha y hora: <b>{registro['hora_cl']}</b> (hora de Chile)</p>"
                    f"<p style='margin:0 0 12px'>Par&aacute;metros anteriores: <b>{antes or '—'}</b><br>"
                    f"Par&aacute;metros nuevos: <b>{nuevos or '—'}</b></p>"
                    f"<p style='margin:0 0 12px'>Las carpetas activas quedaron marcadas como "
                    f"<b>'Simulaci&oacute;n desactualizada'</b> hasta regenerar sus simulaciones.</p>")
                html = _email_institucional("Administrador", cuerpo)
                await asyncio.to_thread(mail.send_mail, admin_to, f"🚨 {etiqueta} — Fuente de Verdad de Mesa", html)
        except Exception as e:
            logging.warning(f"mesa_verdad notificación admin: {e}")
    await db.mesa_verdad_log.update_one({"correo_id": mid}, {"$set": dict(registro)})
    return registro


async def barrido_mesa(dias=2):
    import email_service as mail
    if not mail.configured():
        return {"ok": False, "error": "Correo no configurado"}
    msgs = await asyncio.to_thread(mail.fetch_since_by_senders, dias, [MESA_EMAIL], 60)
    procesados = []
    for m in msgs:
        try:
            r = await _procesar_correo(m)
            if r:
                procesados.append({"tipo": r["tipo"], "subject": r["subject"][:80], "accion": r["accion"]})
        except Exception as e:
            logging.warning(f"mesa_verdad procesar: {e}")
    await db.config.update_one({"_key": "mesa_verdad"},
                               {"$set": {"ultimo_barrido": _now(), "revisados": len(msgs),
                                         "nuevos_procesados": len(procesados)}}, upsert=True)
    return {"ok": True, "revisados": len(msgs), "nuevos": len(procesados), "detalle": procesados}


async def procesar_aprobaciones_en_espera():
    """⏳ Ventana anti-anulación: reenvía a gerardo.ext las aprobaciones cuya ventana venció
    y que NO fueron anuladas por la Mesa en el intertanto."""
    ahora = _now()
    enviadas = 0
    for p in await db.aprobaciones_en_espera.find({"estado": "en_espera",
                                                   "notificar_despues": {"$lte": ahora}}).to_list(20):
        anul = None
        if p.get("folder_id"):
            anul = await db.mesa_verdad_log.find_one({
                "tipo": {"$in": ["anulacion", "rechazo"]}, "folder_id": p["folder_id"],
                "procesado_en": {"$gte": p["creado"]}})
        if anul:
            await db.aprobaciones_en_espera.update_one({"id": p["id"]}, {"$set": {
                "estado": "anulada", "anulada_en": _now(),
                "motivo_anulacion": f"{anul['tipo']}: {anul.get('subject', '')[:150]}"}})
            continue
        f_caso = await db.folders.find_one({"id": p["folder_id"]}) if p.get("folder_id") else None
        try:
            fw = await _reenviar_aprobacion_gerardo(p["msg"], f_caso, p["subject"])
        except Exception as e:
            fw = {"ok": False, "error": str(e)[:150]}
        await db.aprobaciones_en_espera.update_one({"id": p["id"]}, {"$set": {
            "estado": "notificada" if fw.get("ok") else "error_envio",
            "notificada_en": _now(), "reenvio_gerardo": fw}})
        await db.mesa_verdad_log.update_one({"correo_id": p.get("correo_id")}, {"$set": {
            "reenvio_gerardo": fw,
            "accion_ventana": (f"Ventana anti-anulación cumplida ({p.get('ventana_min')} min) → reenvío a "
                               f"gerardo.ext {'OK' if fw.get('ok') else 'FALLÓ'} ({fw.get('adjuntos', 0)} PDF)")}})
        if fw.get("ok"):
            enviadas += 1
            await db.martin_avisos.insert_one({
                "id": str(uuid.uuid4()), "tipo": "mesa_aprobado_notificado",
                "cliente": p.get("cliente") or "", "estado": "pendiente", "creado": _now(),
                "mensaje": (f"Listo jefe: pasó la ventana anti-anulación de {p.get('cliente') or 'la carpeta'} "
                            "sin cancelaciones de la Mesa y ya reenvié la aprobación al ejecutivo.")})
    return enviadas


async def mesa_verdad_loop():
    """Monitoreo permanente y autónomo (REGLA CONSTITUCIONAL — inamovible)."""
    await asyncio.sleep(25)
    try:  # ⛡ Regla de Oro #68: índice único de huella (cerrojo a nivel de BD)
        await db.mesa_verdad_log.create_index("huella", unique=True, sparse=True)
    except Exception as e:
        logging.warning(f"mesa_verdad índice huella: {e}")
    while True:
        try:
            await barrido_mesa(dias=2)
        except Exception as e:
            logging.warning(f"mesa_verdad loop: {e}")
        try:
            await procesar_aprobaciones_en_espera()
        except Exception as e:
            logging.warning(f"ventana anti-anulación loop: {e}")
        await asyncio.sleep(INTERVALO_SEG)


def _exigir(request):
    c = getattr(request.state, "user", {}) or {}
    if c.get("rol") not in ROLES:
        raise HTTPException(status_code=403, detail="Su rol no tiene acceso a esta función")
    return c


@mesav.get("/estado")
async def mesa_verdad_estado(request: Request):
    _exigir(request)
    cfg = await db.config.find_one({"_key": "mesa_verdad"}, {"_id": 0}) or {}
    total = await db.mesa_verdad_log.count_documents({})
    por_tipo = {}
    async for g in db.mesa_verdad_log.aggregate([{"$group": {"_id": "$tipo", "n": {"$sum": 1}}}]):
        por_tipo[g["_id"]] = g["n"]
    return {"canal_oficial": MESA_EMAIL, "monitoreo": "activo", "intervalo_seg": INTERVALO_SEG,
            "ultimo_barrido": cfg.get("ultimo_barrido"), "total_procesados": total, "por_tipo": por_tipo}


@mesav.get("/log")
async def mesa_verdad_log(request: Request, limit: int = 50):
    _exigir(request)
    docs = await db.mesa_verdad_log.find({}, {"_id": 0}).sort("procesado_en", -1).limit(min(limit, 200)).to_list(200)
    return {"registros": docs, "total": len(docs)}


@mesav.post("/procesar-ahora")
async def mesa_verdad_ahora(request: Request):
    """Dispara un barrido inmediato en segundo plano (el IMAP puede tardar minutos)."""
    _exigir(request)
    asyncio.create_task(barrido_mesa(dias=3))
    return {"ok": True, "estado": "barrido_iniciado",
            "mensaje": "Barrido de la casilla de mesa iniciado en segundo plano — revise /api/mesa-verdad/log en unos minutos"}
