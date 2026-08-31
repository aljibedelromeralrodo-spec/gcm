"""📬 NORMATIVA DE CORREOS DEL SISTEMA — Resumen Diario 8:00 AM (hora Chile).
UN SOLO correo diario a gerardo.ext@centralmutuos.cl. Arranque único (mañana)
con pendientes de las últimas 2 semanas; desde el día siguiente, digest diario.
Prohibidos los correos operacionales sueltos durante el día."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from database import db

resdia = APIRouter()
DESTINO = "gerardo.ext@centralmutuos.cl"
TZ_CL = ZoneInfo("America/Santiago")
KEY = "resumen_diario_8am"
ORO, NEGRO = "#C9A227", "#111827"


def _exigir(request):
    c = getattr(request.state, "user", {}) or {}
    if c.get("rol") not in ("admin", "maestro"):
        raise HTTPException(status_code=403, detail="Solo el administrador")
    return c


async def _estado():
    st = await db.config.find_one({"_key": KEY})
    if not st:
        manana = (datetime.now(TZ_CL) + timedelta(days=1)).strftime("%Y-%m-%d")
        st = {"_key": KEY, "enabled": True, "hora": 8, "destino": DESTINO,
              "arranque_enviado": False, "last_sent_date": None,
              "fecha_inicio": manana, "permitir_notificaciones": False, "last_result": {}}
        await db.config.insert_one(dict(st))
    st.pop("_id", None)
    return st


# ── Gate de la normativa: correos operacionales sueltos quedan bloqueados ──
async def notificaciones_permitidas():
    st = await db.config.find_one({"_key": KEY}) or {}
    return bool(st.get("permitir_notificaciones"))


async def envios_automaticos_permitidos():
    """Interruptor maestro: todos los envíos automáticos apagados salvo el resumen 8AM
    y el flujo constitucional de aprobación de MESA."""
    st = await db.config.find_one({"_key": KEY}) or {}
    return bool(st.get("envios_automaticos"))


async def registrar_omitido(tipo, detalle):
    await db.correos_omitidos_normativa.insert_one({
        "tipo": tipo, "detalle": (detalle or "")[:220],
        "fecha": datetime.now(timezone.utc).isoformat()})


# ── Datos ──
async def _filas_carpetas(query, limite=80):
    from carpetas_resultado import _resultado_folder, _dias_habiles_entre, _dtp
    from server import _criterios_folder
    filas = []
    async for f in db.folders.find({"descartada": {"$ne": True}, "archivada": {"$ne": True}, **query}) \
            .sort("created_at", -1).limit(limite):
        try:
            resultado, _ = await _resultado_folder(f)
        except Exception:
            resultado = f.get("resultado_mesa")
        hitos = [f.get(k) for k in ("updated_at", "mesa_enviado_at", "estudio_titulo_solicitado_at",
                                    "tasacion_solicitada_at", "faltantes_pedidos_at",
                                    "escrituracion_confirmada_at", "created_at")]
        ult = max((_dtp(h) for h in hitos if _dtp(h)), default=None)
        dias = _dias_habiles_entre(ult, datetime.now(timezone.utc)) if ult else 0
        try:
            faltantes = [c["nombre"] for c in _criterios_folder(f)
                         if not c["ok"] and c["nombre"] not in ("Enviada a mesa", "Datos financieros completos")]
        except Exception:
            faltantes = []
        filas.append({"nombre": f.get("nombre") or "—",
                      "estado": (resultado or "en proceso").upper(),
                      "dias_sin_movimiento": dias, "faltantes": faltantes,
                      "created_at": f.get("created_at") or ""})
    return filas


async def _datos_arranque():
    corte = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    filas = await _filas_carpetas({"created_at": {"$gte": corte}}, 120)
    return {"tipo": "arranque", "carpetas": filas}


async def _datos_digest():
    from carpetas_resultado import _dtp
    ahora_cl = datetime.now(TZ_CL)
    fin = ahora_cl.replace(hour=8, minute=0, second=0, microsecond=0)
    if ahora_cl < fin:
        fin -= timedelta(days=1)
    ini = fin - timedelta(days=1)
    ini_u, fin_u = ini.astimezone(timezone.utc), fin.astimezone(timezone.utc)

    def en_ventana(ts):
        d = _dtp(ts)
        return bool(d and ini_u <= d < fin_u)

    todas = await _filas_carpetas({}, 200)
    nuevas = [c for c in todas if en_ventana(c["created_at"])]
    sin_mov = [c for c in todas if c["dias_sin_movimiento"] > 2][:60]
    con_faltantes = [c for c in todas if c["faltantes"]][:40]

    sin_carpeta = []
    async for it in db.proc_queue.find({}, {"_id": 0, "sender": 1, "subject": 1, "date_iso": 1,
                                            "status": 1, "drive_folder_id": 1}).sort("date_iso", -1).limit(300):
        if not en_ventana(it.get("date_iso")):
            continue
        if it.get("drive_folder_id") or it.get("status") == "procesado":
            continue
        sin_carpeta.append({"remitente": (it.get("sender") or "")[:50],
                            "asunto": (it.get("subject") or "")[:80], "fecha": it.get("date_iso")})

    resultados = []
    async for n in db.notif_cola.find({"estado_cola": "enviado"}).sort("despachado_en", -1).limit(120):
        if en_ventana(n.get("despachado_en")):
            resultados.append({"cliente": (n.get("nombre") or n.get("cliente") or "—")[:40],
                               "estado": (n.get("estado") or "").upper()})

    cambios_mesa = []
    async for m in db.mesa_verdad_log.find({}, {"_id": 0}).sort("fecha", -1).limit(30):
        if en_ventana(m.get("fecha")):
            cambios_mesa.append({"detalle": (m.get("mensaje") or m.get("subject") or "cambio de mesa")[:150]})

    alertas = []
    fallidos = await db.correos_fallidos.count_documents({"estado": {"$nin": ["cerrado", "resuelto"]}})
    if fallidos:
        alertas.append(f"{fallidos} correo(s) con fallo de entrega abiertos")
    async for o in db.correos_omitidos_normativa.find({}, {"_id": 0}).sort("fecha", -1).limit(30):
        if en_ventana(o.get("fecha")):
            alertas.append(f"Notificación retenida por normativa ({o.get('tipo')}): {o.get('detalle')}")

    # Consolidación del antiguo reporte 10AM: solicitudes enviadas a MESA en la ventana
    enviadas_mesa = []
    async for it in db.proc_queue.find({"autocorreo_enviado": True},
                                       {"_id": 0, "subject": 1, "sender": 1, "autocorreo_en": 1,
                                        "autocorreo_a": 1, "classification": 1}).sort("autocorreo_en", -1).limit(120):
        if not en_ventana(it.get("autocorreo_en")):
            continue
        cl = it.get("classification") or {}
        enviadas_mesa.append({"cliente": (cl.get("cliente") or it.get("subject") or "—")[:60],
                              "rut": cl.get("rut") or "—",
                              "enviado_a": (it.get("autocorreo_a") or "—")[:60],
                              "fecha": str(it.get("autocorreo_en") or "")[:16].replace("T", " ")})

    return {"tipo": "digest", "desde": ini.strftime("%d/%m/%Y %H:%M"), "hasta": fin.strftime("%d/%m/%Y %H:%M"),
            "nuevas": nuevas, "sin_movimiento": sin_mov, "correos_sin_carpeta": sin_carpeta,
            "resultados_enviados": resultados, "documentos_faltantes": con_faltantes,
            "cambios_mesa": cambios_mesa, "alertas": alertas, "enviadas_mesa": enviadas_mesa}


# ── HTML ──
def _tabla(filas, columnas):
    if not filas:
        return "<p style='color:#6b7280;font-size:13px;margin:4px 0 14px'>Sin registros.</p>"
    head = "".join(
        f"<th style='padding:8px 10px;text-align:left;color:#374151;font-size:11px;"
        f"font-weight:700;background:#f9fafb;border-bottom:2px solid #e5e7eb'>{t}</th>"
        for t, _ in columnas)
    rows = ""
    for i, f in enumerate(filas):
        bg = "#ffffff" if i % 2 else "#f9fafb"
        tds = "".join(
            f"<td style='padding:8px 10px;color:#111827;border-bottom:1px solid #e5e7eb'>{fn(f)}</td>"
            for _, fn in columnas)
        rows += f"<tr style='background:{bg}'>{tds}</tr>"
    return (f"<table style='border-collapse:collapse;font-size:13px;width:100%;margin:4px 0 16px;"
            f"border:1px solid #e5e7eb'>"
            f"<tr>{head}</tr>{rows}</table>")


def _seccion(titulo, contenido):
    return (f"<h3 style='color:#111827;margin:18px 0 6px;font-size:15px;"
            f"border-left:4px solid {ORO};padding-left:10px'>{titulo}</h3>{contenido}")


COLS_CARPETA = [("Cliente", lambda f: f"<b>{f['nombre']}</b>"),
                ("Estado", lambda f: f["estado"]),
                ("Días sin movimiento", lambda f: f["dias_sin_movimiento"]),
                ("Documentos faltantes", lambda f: ", ".join(f["faltantes"]) or "—")]


def _html_arranque(d):
    return (f"<p style='margin:0 0 10px;color:#111827'>Correo de arranque del sistema de resúmenes diarios. "
            f"Listado completo de clientes con carpetas de las últimas dos semanas:</p>"
            + _tabla(d["carpetas"], COLS_CARPETA)
            + "<p style='color:#4b5563;font-size:12px'>Desde mañana recibirá un único resumen diario a las 8:00 AM.</p>")


def _html_digest(d):
    h = f"<p style='margin:0 0 10px;color:#4b5563;font-size:12px'>Período: {d['desde']} → {d['hasta']} (hora de Chile)</p>"
    h += _seccion(f"📁 Carpetas nuevas recibidas ayer ({len(d['nuevas'])})", _tabla(d["nuevas"], COLS_CARPETA))
    h += _seccion(f"⏸ Pendientes sin movimiento +2 días hábiles ({len(d['sin_movimiento'])})",
                  _tabla(d["sin_movimiento"], COLS_CARPETA))
    h += _seccion(f"✉ Correos recibidos que no generaron carpeta ({len(d['correos_sin_carpeta'])})",
                  _tabla(d["correos_sin_carpeta"], [("Remitente", lambda f: f["remitente"]),
                                                    ("Asunto", lambda f: f["asunto"]),
                                                    ("Fecha", lambda f: str(f["fecha"])[:16].replace("T", " "))]))
    h += _seccion(f"📤 Solicitudes enviadas a MESA ayer ({len(d.get('enviadas_mesa') or [])})",
                  _tabla(d.get("enviadas_mesa") or [], [("Cliente", lambda f: f"<b>{f['cliente']}</b>"),
                                                        ("RUT", lambda f: f["rut"]),
                                                        ("Enviado a", lambda f: f["enviado_a"]),
                                                        ("Fecha", lambda f: f["fecha"])]))
    h += _seccion(f"✅ Aprobaciones y rechazos enviados ({len(d['resultados_enviados'])})",
                  _tabla(d["resultados_enviados"], [("Cliente", lambda f: f["cliente"]),
                                                    ("Resultado", lambda f: f["estado"])]))
    h += _seccion(f"📄 Documentos faltantes por solicitar ({len(d['documentos_faltantes'])})",
                  _tabla(d["documentos_faltantes"], COLS_CARPETA))
    h += _seccion(f"⚖ Cambios de tasas o criterios desde mesa ({len(d['cambios_mesa'])})",
                  _tabla(d["cambios_mesa"], [("Detalle", lambda f: f["detalle"])]))
    alertas = "".join(f"<li style='color:#b91c1c;margin:3px 0'>{a}</li>" for a in d["alertas"]) \
        or "<li style='color:#4b5563'>Sin alertas activas.</li>"
    h += _seccion(f"🚨 Alertas activas del sistema ({len(d['alertas'])})",
                  f"<ul style='margin:4px 0 14px;padding-left:20px'>{alertas}</ul>")
    return h


async def _enviar(tipo_forzado=None):
    import email_service as mail
    from server import _email_institucional
    st = await _estado()
    tipo = tipo_forzado or ("digest" if st.get("arranque_enviado") else "arranque")
    hoy_cl = datetime.now(TZ_CL)
    if tipo == "arranque":
        d = await _datos_arranque()
        cuerpo, asunto = _html_arranque(d), f"📋 Arranque — Carpetas pendientes (últimas 2 semanas) — {hoy_cl.strftime('%d/%m/%Y')}"
    else:
        d = await _datos_digest()
        cuerpo, asunto = _html_digest(d), f"📬 Resumen Diario Central Mutuos — {hoy_cl.strftime('%d/%m/%Y')} 8:00 AM"
    html = _email_institucional("Administración", cuerpo)
    destino = st.get("destino") or DESTINO
    res = await asyncio.to_thread(mail.send_mail, destino, asunto, html, [], "principal")
    resultado = {"success": bool(res.get("success")), "tipo": tipo, "destino": destino,
                 "error": res.get("error"), "enviado_en": datetime.now(timezone.utc).isoformat()}
    upd = {"last_result": resultado}
    if res.get("success"):
        upd["last_sent_date"] = hoy_cl.strftime("%Y-%m-%d")
        if tipo == "arranque":
            upd["arranque_enviado"] = True
    await db.config.update_one({"_key": KEY}, {"$set": upd}, upsert=True)
    return resultado


async def resumen_diario_loop():
    """UN SOLO correo diario a las 8:00 AM hora de Chile. Sin repeticiones."""
    await asyncio.sleep(30)
    while True:
        try:
            await asyncio.sleep(60)
            st = await _estado()
            if not st.get("enabled"):
                continue
            ahora = datetime.now(TZ_CL)
            hoy = ahora.strftime("%Y-%m-%d")
            if hoy < (st.get("fecha_inicio") or hoy):
                continue
            if ahora.hour >= int(st.get("hora") or 8) and st.get("last_sent_date") != hoy:
                # ⛡ Regla de Oro #68: reserva ATÓMICA del día ANTES de enviar (sin carreras)
                claim = await db.config.update_one(
                    {"_key": KEY, "last_sent_date": {"$ne": hoy}},
                    {"$set": {"last_sent_date": hoy, "claim_en": datetime.now(timezone.utc).isoformat()}})
                if not claim.modified_count:
                    continue
                r = await _enviar()
                if not r.get("success"):
                    await db.config.update_one({"_key": KEY, "last_sent_date": hoy},
                                               {"$set": {"last_sent_date": st.get("last_sent_date")}})
                logging.info(f"📬 Resumen diario 8AM: {r}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.warning(f"resumen_diario_loop: {e}")


# ── Endpoints (solo admin) ──
@resdia.get("/resumen-diario/estado")
async def resumen_estado(request: Request):
    _exigir(request)
    return await _estado()


@resdia.get("/resumen-diario/preview")
async def resumen_preview(request: Request, tipo: str = None):
    _exigir(request)
    st = await _estado()
    t = tipo or ("digest" if st.get("arranque_enviado") else "arranque")
    d = await (_datos_arranque() if t == "arranque" else _datos_digest())
    from server import _email_institucional
    html = _email_institucional("Administración", _html_arranque(d) if t == "arranque" else _html_digest(d))
    return {"tipo": t, "datos": {k: (len(v) if isinstance(v, list) else v) for k, v in d.items()},
            "html": html}


@resdia.post("/resumen-diario/enviar-ahora")
async def resumen_enviar_ahora(request: Request, payload: dict = None):
    _exigir(request)
    r = await _enviar((payload or {}).get("tipo"))
    if not r.get("success"):
        raise HTTPException(status_code=502, detail=r.get("error") or "Error de envío")
    return r
