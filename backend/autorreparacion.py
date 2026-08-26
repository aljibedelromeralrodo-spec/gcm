"""🛠 AUTORREPARACIÓN INTELIGENTE — 2 niveles (normativa constitucional).
Nivel 1 (automático): reintentos de envío ya CONFIRMADOS, reproceso de correos
atascados, reconexión de servicios, limpieza de colas bloqueadas.
Nivel 2 (diagnóstico + aprobación): si el problema requiere cambio de código o
redespliegue, envía un diagnóstico a gerardo.ext@centralmutuos.cl y NO toca nada."""
import uuid
import asyncio
import logging
import functools
from datetime import datetime, timezone, timedelta
from database import db
import email_service as mail

ADMIN_MAIL = "gerardo.ext@centralmutuos.cl"
MODULOS_VIGILADOS = ("correos salientes", "creación de carpetas", "clasificación IA",
                     "aprobaciones de mesa", "rechazos de mesa")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _hace(horas=0, minutos=0):
    return (datetime.now(timezone.utc) - timedelta(hours=horas, minutes=minutos)).isoformat()


async def ciclo(clasificar_item=None):
    """Un ciclo completo de vigilancia + reparación. Devuelve el informe."""
    inf = {"fecha": _now(), "nivel1": [], "nivel2": [], "servicios": {}, "errores": []}

    # ── NIVEL 1.1 · Correos YA CONFIRMADOS por el Admin cuyo SMTP falló → reintento
    try:
        for p in await db.correos_preview.find(
                {"estado": "error_envio", "intentos_autorrep": {"$not": {"$gte": 3}}}).to_list(5):
            adjs = []
            async for a in db.correos_preview_adj.find({"preview_id": p["id"]}):
                import base64 as _b64
                adjs.append({"filename": a.get("filename"),
                             "content_b64": _b64.b64encode(bytes(a.get("data") or b"")).decode()})
            res = await asyncio.to_thread(functools.partial(
                mail.send_mail, p["to"], p["subject"], p["body_html"], adjs,
                confirmado=True, permitir_duplicado=True, hilo_nuevo=True,
                from_name="Central Mutuos"))
            ok = bool(res.get("success"))
            await db.correos_preview.update_one({"id": p["id"]}, {"$set": {
                "estado": "enviado" if ok else "error_envio",
                "reparado_en": _now() if ok else None},
                "$inc": {"intentos_autorrep": 1}})
            inf["nivel1"].append(
                f"{'✅ reenviado' if ok else '⚠ reintento fallido'}: «{(p.get('subject') or '')[:60]}» → {p.get('to')}")
    except Exception as e:
        inf["errores"].append(f"reintento correos: {str(e)[:120]}")

    # ── NIVEL 1.2 · Correos atascados en la cola de procesamiento → reproceso
    try:
        if clasificar_item:
            corte = _hace(minutos=45)
            atascados = await db.proc_queue.find(
                {"status": {"$in": ["pendiente", "error"]},
                 "intentos_autorrep": {"$not": {"$gte": 2}},
                 "date_iso": {"$lt": corte}}).sort("date_iso", 1).to_list(4)
            for it in atascados:
                try:
                    await clasificar_item(it)
                    inf["nivel1"].append(f"🔁 reprocesado: «{(it.get('subject') or '')[:60]}»")
                except Exception as e:
                    inf["nivel1"].append(f"⚠ reproceso falló: «{(it.get('subject') or '')[:50]}» — {str(e)[:80]}")
                await db.proc_queue.update_one({"id": it["id"]}, {"$inc": {"intentos_autorrep": 1}})
    except Exception as e:
        inf["errores"].append(f"cola atascada: {str(e)[:120]}")

    # ── NIVEL 1.3 · Reconexión de servicios de correo (IMAP por cuenta)
    caidas = []
    for acc in mail.ACCOUNTS:
        try:
            def _test(a=acc):
                m = mail._connect(a)
                m.select("INBOX", readonly=True)
                m.logout()
                return True
            await asyncio.wait_for(asyncio.to_thread(_test), timeout=45)
            inf["servicios"][acc["user"]] = "🟢 conectado"
        except Exception as e:
            inf["servicios"][acc["user"]] = f"🔴 caído: {str(e)[:60]}"
            caidas.append(acc["user"])
    if caidas:
        st = await db.config.find_one({"_key": "autorrep_imap_fallos"}) or {}
        n = int(st.get("consecutivos") or 0) + 1
        await db.config.update_one({"_key": "autorrep_imap_fallos"},
                                   {"$set": {"consecutivos": n, "ultimo": _now()}}, upsert=True)
        inf["nivel1"].append(f"🔌 IMAP caído en {', '.join(caidas)} (fallo consecutivo #{n}) — se reintenta el próximo ciclo")
        if n >= 3:
            await _diagnostico_nivel2(
                "conexion_correo",
                f"La conexión IMAP a {', '.join(caidas)} lleva {n} ciclos consecutivos caída.",
                "Verificar credenciales MAIL_*/MAIL2_* en backend/.env, estado del servidor de correo "
                "y posibles bloqueos del proveedor. Puede requerir actualizar contraseñas de aplicación y redesplegar.",
                ["email_service.py", "ingesta de carpetas", "mesa de la verdad", "correos salientes"], inf)
    else:
        await db.config.update_one({"_key": "autorrep_imap_fallos"},
                                   {"$set": {"consecutivos": 0}}, upsert=True)

    # ── NIVEL 1.4 · Colas bloqueadas: flag 'running' colgado >30 min → liberación
    try:
        pa = await db.config.find_one({"_key": "proc_auto"}) or {}
        ini = pa.get("last_run_started") or ""
        if pa.get("running") and ini and ini < _hace(minutos=30):
            await db.config.update_one({"_key": "proc_auto"}, {"$set": {"running": False}})
            inf["nivel1"].append("🔓 cola de ingesta liberada (flag 'running' colgado >30 min)")
        rp = await db.config.find_one({"_key": "reproceso_ia"}) or {}
        if rp.get("estado") == "corriendo" and (rp.get("actualizado") or "") < _hace(minutos=45):
            await db.config.update_one({"_key": "reproceso_ia"},
                                       {"$set": {"estado": "interrumpido"}})
            inf["nivel1"].append("🔓 reproceso IA marcado como interrumpido (sin avance >45 min)")
    except Exception as e:
        inf["errores"].append(f"colas: {str(e)[:120]}")

    # ── NIVEL 2 · Detección de problemas que requieren intervención del Admin
    try:
        fallos = await db.log_errores_correo.count_documents({"fecha": {"$gte": _hace(horas=24)}})
        if fallos >= 3:
            await _diagnostico_nivel2(
                "correos_salientes",
                f"Se registraron {fallos} errores SMTP en las últimas 24 horas (colección log_errores_correo).",
                "Revisar el detalle de los errores en el log SMTP. Si el error es de autenticación, renovar la "
                "clave de aplicación MAIL2_*. Si es de contenido/tamaño, ajustar el módulo emisor. Puede requerir redespliegue.",
                ["email_service.py", "correos salientes"], inf)
    except Exception as e:
        inf["errores"].append(f"detección smtp: {str(e)[:120]}")
    try:
        en_error = await db.proc_queue.count_documents({"status": "error", "intentos_autorrep": {"$gte": 2}})
        if en_error >= 3:
            await _diagnostico_nivel2(
                "creacion_carpetas",
                f"Hay {en_error} correos en estado de ERROR persistente en la cola de carpetas pese a los reintentos automáticos.",
                "Revisar el campo 'error' de cada ítem en proc_queue. Suele ser un formato de adjunto no soportado "
                "u OCR fallido; podría requerir un ajuste de código en _clasificar_item o pdf_service.",
                ["server.py (_clasificar_item)", "pdf_service.py", "ocr_service.py", "creación de carpetas"], inf)
    except Exception as e:
        inf["errores"].append(f"detección carpetas: {str(e)[:120]}")
    try:
        ult = await db.clasificaciones_ia.find_one({"metodo": "claude"}, sort=[("clasificado_en", -1)])
        hubo_intentos = await db.proc_queue.count_documents({"date_iso": {"$gte": _hace(horas=24)}})
        if hubo_intentos and ult and (ult.get("clasificado_en") or "") < _hace(horas=24):
            await _diagnostico_nivel2(
                "clasificacion_ia",
                "El clasificador IA (Claude) no registra clasificaciones exitosas en las últimas 24 horas "
                "aunque siguen llegando correos (el sistema está operando con el respaldo de palabras clave).",
                "Verificar saldo/estado de la EMERGENT_LLM_KEY y los logs del backend. Puede requerir recargar "
                "saldo de la llave universal o corregir clasificador_correo.py.",
                ["clasificador_correo.py", "clasificación IA"], inf)
    except Exception as e:
        inf["errores"].append(f"detección clasificador: {str(e)[:120]}")
    try:
        ult_mesa = await db.mesa_verdad_log.find_one({}, sort=[("fecha", -1)])
        if ult_mesa and (ult_mesa.get("fecha") or "") < _hace(horas=6):
            pend_rech = await db.rechazos_pendientes.count_documents({"estado": {"$ne": "enviado"}})
            if pend_rech:
                await _diagnostico_nivel2(
                    "mesa_aprobacion_rechazo",
                    f"El monitor de Mesa no registra actividad hace más de 6 horas y hay {pend_rech} "
                    "notificaciones de rechazo pendientes.",
                    "Revisar mesa_verdad_loop en los logs del backend (posible cuelgue IMAP). "
                    "El candado anti-cuelgue debería liberarlo; si persiste, requiere reinicio del backend.",
                    ["mesa_verdad.py", "rechazo_notificacion.py", "aprobaciones de mesa", "rechazos de mesa"], inf)
    except Exception as e:
        inf["errores"].append(f"detección mesa: {str(e)[:120]}")

    await db.config.update_one({"_key": "autorreparacion_estado"},
                               {"$set": {"ultimo_informe": inf, "actualizado": _now()}}, upsert=True)
    if inf["nivel1"] or inf["nivel2"]:
        logging.info(f"🛠 Autorreparación: {len(inf['nivel1'])} acción(es) nivel 1, {len(inf['nivel2'])} diagnóstico(s) nivel 2")
    return inf


async def _diagnostico_nivel2(tipo, que_fallo, propuesta, modulos, inf):
    """NIVEL 2: alerta + correo de diagnóstico al Admin. JAMÁS toca código ni redespliega.
    Anti-spam: un diagnóstico por tipo de problema cada 24 h."""
    ya = await db.autorreparacion_diagnosticos.find_one(
        {"tipo": tipo, "creado": {"$gte": _hace(horas=24)}})
    if ya:
        return
    did = str(uuid.uuid4())
    doc = {"id": did, "tipo": tipo, "que_fallo": que_fallo, "propuesta": propuesta,
           "modulos": modulos, "estado": "pendiente_aprobacion", "creado": _now()}
    await db.autorreparacion_diagnosticos.insert_one(dict(doc))
    await db.alertas.insert_one({
        "id": str(uuid.uuid4()), "tipo": "autorreparacion_nivel2",
        "cliente": tipo, "mensaje": f"🛠 Diagnóstico Nivel 2 ({tipo}): {que_fallo[:140]}",
        "fecha": _now(), "leida": False})
    filas = "".join(f"<li style='margin:4px 0'>{m}</li>" for m in modulos)
    html = (
        "<div style='font-family:Georgia,serif;max-width:640px;margin:0 auto;color:#1a1a1a'>"
        "<h2 style='color:#8a6d1d;border-bottom:2px solid #d4af37;padding-bottom:8px'>"
        "🛠 Autorreparación — Diagnóstico Nivel 2</h2>"
        "<p><b>Qué falló:</b><br>" + que_fallo + "</p>"
        "<p><b>Qué propone corregir:</b><br>" + propuesta + "</p>"
        "<p><b>Módulos afectados:</b></p><ul>" + filas + "</ul>"
        "<p style='background:#fdf6e3;border-left:4px solid #d4af37;padding:10px 14px'>"
        "Conforme a la normativa constitucional de AUTORREPARACIÓN, el sistema <b>NO tocará código "
        "ni redesplegará nada</b> sin su aprobación explícita. Responda este correo o indique la "
        "corrección en el chat del agente para autorizarla.</p>"
        f"<p style='font-size:12px;color:#777'>ID diagnóstico: {did} · {_now()[:16].replace('T', ' ')} UTC</p></div>")
    try:
        res = await asyncio.to_thread(functools.partial(
            mail.send_mail, ADMIN_MAIL,
            f"🛠 [Central Mutuos] Diagnóstico de autorreparación: {tipo.replace('_', ' ')}",
            html, permitir_duplicado=True, hilo_nuevo=True, from_name="Central Mutuos · Autorreparación"))
        await db.autorreparacion_diagnosticos.update_one(
            {"id": did}, {"$set": {"correo": "en_preview" if res.get("preview") else
                                   ("enviado" if res.get("success") else f"error: {res.get('error','')[:80]}")}})
    except Exception as e:
        logging.warning(f"diagnóstico nivel 2 correo: {e}")
    inf["nivel2"].append(f"📋 {tipo}: diagnóstico enviado al Admin (espera aprobación)")
