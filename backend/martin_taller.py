"""🔧 MARTÍN VIGÍA — TALLER DE REPARACIÓN KINTSUGI (V16.4).
Filosofía: lo roto se une con oro y queda MÁS FUERTE, documentado. Martín tiene libertad
total para diagnosticar, reparar y mejorar. SOLO los envíos masivos / fuera de la bandeja
requieren autorización de Gerardo. Nada se borra: cada reparación guarda antes y después."""
import os
import re
import time
import uuid
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request
from database import db

martin = APIRouter(prefix="/martin")

HERRAMIENTAS = [
    ("ver_logs_blindaje", False, True, "Ver todos los logs de correos, parser y envíos", "diagnostico"),
    ("ver_carpetas_faltantes", False, True, "Ver carpetas con conteo 6 liquidaciones real", "diagnostico"),
    ("diagnosticar_tasa_rota", False, True, "Detectar tasas rotas o desactualizadas", "diagnostico"),
    ("diagnosticar_parser_caido", False, True, "Ver si el parser no corrió hace >5 min", "diagnostico"),
    ("diagnosticar_dns", False, True, "Ver estado SPF/DKIM/DMARC de centralmutuos.cl", "diagnostico"),
    ("recontar_6_liquidaciones", False, True, "Recalcular 0/6→6/6 si se contó mal — une con oro", "reparacion"),
    ("reparsear_correo_fallido", False, True, "Reprocesar correo que no se clasificó — une con oro", "reparacion"),
    ("corregir_protocolo_mal_clasificado", False, True, "Cambiar protocolo si la IA se equivocó (ej: dependiente→mixto)", "reparacion"),
    ("reparar_tasa_rota_con_oro", False, True, "Tasa rota o nula → recalcular y guardar con marca de oro", "reparacion"),
    ("reenriquecer_carpeta_manual", False, True, "Forzar recálculo de estado de carpeta si no enriqueció solo", "reparacion"),
    ("reindexar_memoria_total", False, True, "Reindexar colecciones calientes si la búsqueda está lenta", "reparacion"),
    ("reiniciar_parser_cron", False, True, "Correr el parser ahora mismo y resetear su latido", "reparacion"),
    ("reintentar_envio_rebotado", False, True, "Reintentar envío rebotado por error temporal", "reparacion"),
    ("mejorar_prompt_claude", False, True, "Agregar conocimiento al clasificador sin pedir permiso", "mejora"),
    ("enviar_masivo", True, False, "Correo masivo a >10 destinatarios — REQUIERE autorización de Gerardo", "envio"),
    ("enviar_correo_sin_autorizacion", True, False, "Envío fuera de la bandeja de autorización — REQUIERE autorización", "envio"),
    ("cambiar_from_email", True, False, "Cambiar el FROM de gerardo.ext — REQUIERE autorización", "envio"),
]
TASA_MIN, TASA_MAX = 0.01, 0.10


def _now():
    return datetime.now(timezone.utc).isoformat()


def _user(request):
    return getattr(request.state, "user", {}) or {}


def _exigir_martin(request):
    u = _user(request)
    ident = f"{u.get('sub') or ''} {u.get('nombre') or ''}".lower()
    if u.get("rol") not in ("admin", "maestro") and "martin" not in ident and "martín" not in ident:
        raise HTTPException(status_code=403, detail="Taller Kintsugi: solo Martín y el Administrador")


async def seed_martin():
    for hid, req, puede, desc, cat in HERRAMIENTAS:
        await db.sistema_herramientas_permisos.update_one({"id": hid}, {"$set": {
            "requiere_autorizacion_gerardo": req, "puede_usar_martin": puede,
            "descripcion": desc, "categoria": cat}}, upsert=True)
    try:
        await db.sistema_reparaciones_log.create_index([("created_at", -1)])
        await db.martin_fallas.create_index([("estado", 1), ("huella", 1)])
    except Exception:
        pass
    logging.info("🔧 Taller Kintsugi: herramientas de Martín sembradas")


async def _log_reparacion(tipo_falla, herramienta, accion, antes, despues, caso_id="", rut="", ms=0, reparador="martin"):
    await db.sistema_reparaciones_log.insert_one({
        "id": str(uuid.uuid4()), "reparador": reparador, "tipo_falla": tipo_falla,
        "herramienta_usada": herramienta, "accion_reparacion": accion,
        "caso_id": caso_id, "cliente_rut": rut, "antes": antes, "despues": despues,
        "quedo_con_oro": True, "tiempo_reparacion_ms": ms, "created_at": _now()})
    import blindaje_correos as b
    await b._log("reparacion_con_oro_por_martin",
                 {"falla": tipo_falla, "herramienta": herramienta, "caso": rut or caso_id,
                  "antes": antes, "despues": despues, "oro": True})
    await db.dashai_eventos.insert_one({
        "tipo": "reparacion_kintsugi", "fecha": _now(),
        "detalle": f"🔨 {reparador.title()} reparó con oro: {tipo_falla} {rut or caso_id} — quedó más fuerte"})


# ═══════════════ HERRAMIENTAS REPARADORAS (libertad total, kintsugi) ═══════════════
async def _real_liq(caso_id):
    import blindaje_correos as b
    doc0 = await db.clientes_carpetas_documentos.find_one({"caso_id": caso_id})
    if not doc0:
        return None, None
    proto = doc0.get("protocolo_id") or "dependiente_simple"
    return await b._estado_carpeta(caso_id, proto), proto


async def reparar_liquidaciones(caso_id="", rut=""):
    import blindaje_correos as b
    t0 = time.time()
    if not caso_id and rut:
        d = await db.clientes_carpetas_documentos.find_one({"cliente_rut_norm": b._norm_rut(rut)})
        caso_id = (d or {}).get("caso_id", "")
    est, proto = await _real_liq(caso_id)
    if not est:
        raise HTTPException(status_code=404, detail="Caso sin carpeta de documentos")
    reparados = []
    for col, campos in ((db.correos_autorizacion_admin, {"documentos_tiene": est["tiene"], "documentos_faltan": est["faltan"],
                                                         "liquidaciones_tiene": est["liq_tiene"], "liquidaciones_faltan": est["liq_faltan"]}),
                        (db.correos_salida_cola_blindada, {"documentos_faltantes": est["faltan"],
                                                           "liquidaciones_tiene": est["liq_tiene"], "liquidaciones_faltan": est["liq_faltan"]})):
        async for r in col.find({"caso_id": caso_id, "estado": {"$in": ["pendiente", "pendiente_autorizacion"]}}):
            antes = {"liquidaciones_tiene": r.get("liquidaciones_tiene"), "faltan": len(r.get("documentos_faltan") or r.get("documentos_faltantes") or [])}
            if antes["liquidaciones_tiene"] != est["liq_tiene"] or antes["faltan"] != len(est["faltan"]):
                await col.update_one({"id": r["id"]}, {"$set": campos})
                reparados.append(antes)
    ms = int((time.time() - t0) * 1000)
    despues = {"liq_tiene": est["liq_tiene"], "faltan": len(est["faltan"])}
    if reparados:
        await _log_reparacion("liquidacion_mal_contada", "recontar_6_liquidaciones",
                              f"Recontadas liquidaciones reales del caso ({est['liq_tiene']}/6)",
                              reparados[0], despues, caso_id, rut, ms)
    return {"ok": True, "reparados": len(reparados), "estado_real": despues, "ms": ms,
            "mensaje": "✨ Conteo unido con oro" if reparados else "El conteo ya estaba correcto"}


async def reparar_tasa_rota():
    from criterios_data import DEFAULT_TASAS
    t0 = time.time()
    cfg = await db.config.find_one({"_key": "tasas"}) or {}
    antes, despues, rotas = {}, {}, []
    for k, dflt in DEFAULT_TASAS.items():
        v = cfg.get(k)
        try:
            v = float(v)
        except (TypeError, ValueError):
            v = None
        if v is None or v < TASA_MIN or v > TASA_MAX:
            rotas.append(k)
            antes[k] = cfg.get(k)
            despues[k] = dflt
    if rotas:
        nota = (f"Tasa rota el {_now()[:10]} → reparada con oro por Martín — Kintsugi — "
                f"queda más fuerte y documentada: {', '.join(rotas)}")
        await db.config.update_one({"_key": "tasas"}, {"$set": {**despues, "reparado_con_oro": True,
                                                                "nota_kintsugi": nota}}, upsert=True)
        await _log_reparacion("tasa_rota", "reparar_tasa_rota_con_oro", nota, antes, despues,
                              ms=int((time.time() - t0) * 1000))
        return {"ok": True, "reparadas": rotas, "antes": antes, "despues": despues,
                "mensaje": "✨ Tasa rota unida con oro — quedó más fuerte"}
    return {"ok": True, "reparadas": [], "mensaje": "Las 3 tasas están sanas (entre 1% y 10%)"}


async def reparsear_correo(message_id):
    import blindaje_correos as b
    import email_service as mail
    t0 = time.time()
    prev = await db.correos_clasificacion.find_one({"message_id": message_id}, {"_id": 0})
    correos = await asyncio.to_thread(mail.fetch_recent_full, 40)
    c = next((x for x in correos or [] if x.get("id") == message_id), None)
    if not c:
        raise HTTPException(status_code=404, detail="Correo no encontrado en los últimos 40 del inbox")
    await db.correos_clasificacion.delete_one({"message_id": message_id})
    reg = await b.procesar_correo(c)
    if not reg:
        raise HTTPException(status_code=502, detail="La IA no pudo clasificar el correo (reintentar)")
    await _log_reparacion("protocolo_mal_clasificado" if prev else "parser_caido", "reparsear_correo_fallido",
                          "Correo reprocesado con Claude y carpeta re-enriquecida",
                          {"clasificacion": (prev or {}).get("clasificacion"), "protocolo": (prev or {}).get("protocolo_detectado")},
                          {"clasificacion": reg["clasificacion"], "protocolo": reg["protocolo_detectado"]},
                          reg.get("caso_id", ""), reg.get("cliente_rut", ""), int((time.time() - t0) * 1000))
    return {"ok": True, "antes": (prev or {}).get("protocolo_detectado"), "despues": reg["protocolo_detectado"],
            "mensaje": "✨ Correo reparado con oro"}


async def corregir_protocolo(caso_id, protocolo_correcto):
    import blindaje_correos as b
    t0 = time.time()
    if protocolo_correcto not in b.PROTO_IDS:
        raise HTTPException(status_code=400, detail=f"Protocolo inválido. Válidos: {sorted(b.PROTO_IDS)}")
    doc0 = await db.clientes_carpetas_documentos.find_one({"caso_id": caso_id})
    if not doc0:
        raise HTTPException(status_code=404, detail="Caso sin carpeta")
    antes_proto = doc0.get("protocolo_id")
    proto = await db.credito_protocolos_tipo.find_one({"id": protocolo_correcto}) or {}
    reqs = set(proto.get("documentos_requeridos") or [])
    await db.clientes_carpetas_documentos.delete_many(
        {"caso_id": caso_id, "estado": "faltante", "documento_tipo": {"$nin": list(reqs)}})
    await db.clientes_carpetas_documentos.update_many(
        {"caso_id": caso_id}, {"$set": {"protocolo_id": protocolo_correcto, "updated_at": _now()}})
    rut = doc0.get("cliente_rut", "")
    await b._asegurar_docs(caso_id, rut, protocolo_correcto)
    await db.blindaje_casos.update_one({"id": caso_id}, {"$set": {"protocolo_id": protocolo_correcto,
                                                                  "reparado_con_oro": True}})
    est = await b._estado_carpeta(caso_id, protocolo_correcto)
    await db.correos_autorizacion_admin.update_many(
        {"caso_id": caso_id, "estado": "pendiente"},
        {"$set": {"protocolo_detectado": protocolo_correcto, "documentos_tiene": est["tiene"],
                  "documentos_faltan": est["faltan"], "liquidaciones_tiene": est["liq_tiene"],
                  "liquidaciones_faltan": est["liq_faltan"]}})
    await _log_reparacion("protocolo_mal_clasificado", "corregir_protocolo_mal_clasificado",
                          f"Protocolo corregido {antes_proto} → {protocolo_correcto}; requeridos regenerados sin mezclar prohibidos",
                          {"protocolo": antes_proto}, {"protocolo": protocolo_correcto, "faltan": est["faltan"]},
                          caso_id, rut, int((time.time() - t0) * 1000))
    return {"ok": True, "antes": antes_proto, "despues": protocolo_correcto, "faltan": est["faltan"],
            "mensaje": "✨ Protocolo unido con oro"}


async def reintentar_envio(cola_id):
    import blindaje_correos as b
    t0 = time.time()
    r = await db.correos_salida_cola_blindada.find_one({"id": cola_id})
    if not r:
        raise HTTPException(status_code=404, detail="Registro de cola no encontrado")
    if r["estado"] not in ("rebotado", "error"):
        raise HTTPException(status_code=409, detail=f"El correo está '{r['estado']}', no requiere reparación")
    await db.correos_salida_cola_blindada.update_one({"id": cola_id}, {"$set": {
        "estado": "autorizado", "intentos": 0, "reintento_at": None, "ultimo_error": ""}})
    res = await b.enviar_correo_blindado(cola_id)
    await _log_reparacion("envio_rebotado", "reintentar_envio_rebotado",
                          "Supresión limpiada y envío reintentado",
                          {"estado": r["estado"], "intentos": r.get("intentos")},
                          {"resultado": "enviado" if res.get("ok") else res.get("motivo", "error")},
                          r.get("caso_id", ""), r.get("cliente_rut", ""), int((time.time() - t0) * 1000))
    return {"ok": res.get("ok", False), "resultado": res,
            "mensaje": "✨ Envío reparado con oro" if res.get("ok") else "Reintentado — sigue con error, ver detalle"}


async def reiniciar_parser():
    import blindaje_correos as b
    import email_service as mail
    t0 = time.time()
    correos = await asyncio.to_thread(mail.fetch_recent_full, 10)
    n = 0
    for c in correos or []:
        try:
            if await b.procesar_correo(c):
                n += 1
        except Exception as e:
            logging.warning(f"martin reiniciar parser: {str(e)[:100]}")
    await db.config.update_one({"_key": "blindaje_heartbeat"}, {"$set": {"ultimo_run": _now(),
                                                                         "forzado_por": "martin"}}, upsert=True)
    await _log_reparacion("parser_caido", "reiniciar_parser_cron",
                          f"Parser forzado ahora: {len(correos or [])} correos revisados, {n} procesados",
                          {"latido": "vencido"}, {"latido": "renovado", "procesados": n},
                          ms=int((time.time() - t0) * 1000))
    return {"ok": True, "revisados": len(correos or []), "procesados": n, "mensaje": "✨ Parser reanimado con oro"}


async def reindexar_memoria():
    t0 = time.time()
    hechos = []
    for col, campo in (("correos_clasificacion", "cliente_rut"), ("clientes_carpetas_documentos", "cliente_rut_norm"),
                       ("sistema_reparaciones_log", "created_at"), ("correos_blindaje_log", "evento"),
                       ("folders", "rut")):
        try:
            await db[col].create_index(campo)
            hechos.append(f"{col}.{campo}")
        except Exception:
            pass
    await _log_reparacion("memoria_corrupta", "reindexar_memoria_total",
                          "Índices calientes reconstruidos", {"indices": "sin verificar"},
                          {"indices": hechos}, ms=int((time.time() - t0) * 1000))
    return {"ok": True, "indices": hechos, "mensaje": "✨ Memoria reindexada con oro"}


async def mejorar_conocimiento(texto, autor="martin"):
    if not (texto or "").strip():
        raise HTTPException(status_code=400, detail="Escribe qué mejorar")
    linea = f"\n[Mejora {_now()[:10]} · {autor} · Kintsugi] {texto.strip()[:400]}"
    await db.config.update_one({"_key": "base_conocimiento"},
                               {"$set": {"actualizado": _now()},
                                "$setOnInsert": {"resumen_clasificador": ""}}, upsert=True)
    doc = await db.config.find_one({"_key": "base_conocimiento"})
    nuevo = ((doc or {}).get("resumen_clasificador") or "")[-6000:] + linea
    await db.config.update_one({"_key": "base_conocimiento"}, {"$set": {"resumen_clasificador": nuevo}})
    try:
        import clasificador_correo as cc
        cc._KB_CACHE["ts"] = 0
    except Exception:
        pass
    await _log_reparacion("mejora_sistema", "mejorar_prompt_claude",
                          "Conocimiento agregado al clasificador Claude (efecto inmediato)",
                          {}, {"mejora": texto.strip()[:200]})
    return {"ok": True, "mensaje": "✨ Mejora incorporada al cerebro del clasificador — sin pedir permiso"}


# ═══════════════ VIGÍA AUTOMÁTICO (cada 10 min) ═══════════════
async def _detectar_falla(tipo, huella, descripcion, herramienta, params=None):
    prev = await db.martin_fallas.find_one({"huella": huella, "estado": "pendiente"})
    if prev:
        return False
    await db.martin_fallas.insert_one({
        "id": str(uuid.uuid4()), "tipo_falla": tipo, "huella": huella, "descripcion": descripcion,
        "herramienta_recomendada": herramienta, "params": params or {}, "estado": "pendiente",
        "created_at": _now()})
    return True


async def diagnostico_vigia():
    nuevas = 0
    hb = await db.config.find_one({"_key": "blindaje_heartbeat"}) or {}
    try:
        ultimo = datetime.fromisoformat(hb.get("ultimo_run"))
        vencido = (datetime.now(timezone.utc) - ultimo) > timedelta(minutes=5)
    except (TypeError, ValueError):
        vencido = bool(hb)
    if vencido and hb:
        nuevas += await _detectar_falla("parser_caido", f"parser_{_now()[:13]}",
                                        f"El parser de correos no corre desde {str(hb.get('ultimo_run'))[:16]}",
                                        "reiniciar_parser_cron")
    from criterios_data import DEFAULT_TASAS
    cfg = await db.config.find_one({"_key": "tasas"}) or {}
    for k in DEFAULT_TASAS:
        try:
            v = float(cfg.get(k))
            rota = v < TASA_MIN or v > TASA_MAX
        except (TypeError, ValueError):
            rota = True
        if rota:
            nuevas += await _detectar_falla("tasa_rota", f"tasa_{k}",
                                            f"💔 Tasa rota: {k} = {cfg.get(k)!r} (fuera de 1%-10% o nula)",
                                            "reparar_tasa_rota_con_oro")
    errores = await db.correos_salida_cola_blindada.count_documents({"estado": {"$in": ["error", "rebotado"]}})
    if errores > 5:
        nuevas += await _detectar_falla("envio_rebotado", "cola_errores",
                                        f"💔 {errores} correos en error/rebotados en la cola blindada",
                                        "reintentar_envio_rebotado")
    async for a in db.correos_autorizacion_admin.find({"estado": "pendiente"}).limit(30):
        import blindaje_correos as b
        est, _p = await _real_liq(a.get("caso_id"))
        if est and (a.get("liquidaciones_tiene") != est["liq_tiene"]
                    or len(a.get("documentos_faltan") or []) != len(est["faltan"])):
            nuevas += await _detectar_falla(
                "liquidacion_mal_contada", f"liq_{a['caso_id']}",
                f"💔 Conteo desalineado en {a.get('cliente_nombre') or a.get('cliente_rut')}: "
                f"bandeja dice {a.get('liquidaciones_tiene')}/6, la carpeta real tiene {est['liq_tiene']}/6",
                "recontar_6_liquidaciones", {"caso_id": a["caso_id"]})
    mas6 = await db.clientes_carpetas_documentos.count_documents({"documento_tipo": "liquidacion_7"})
    if mas6:
        nuevas += await _detectar_falla("liquidacion_mal_contada", "liq_sobre_6",
                                        "💔 Existen carpetas con más de 6 liquidaciones registradas",
                                        "recontar_6_liquidaciones")
    return nuevas


async def martin_vigia_loop():
    await asyncio.sleep(240)
    while True:
        try:
            n = await diagnostico_vigia()
            if n:
                logging.info(f"🔧 Vigía Martín: {n} falla(s) nueva(s) detectada(s)")
        except Exception as e:
            logging.warning(f"vigía martín: {str(e)[:150]}")
        await asyncio.sleep(600)


# ═══════════════ RUTAS ═══════════════
DISPATCH = {
    "recontar_6_liquidaciones": lambda p: reparar_liquidaciones(p.get("caso_id", ""), p.get("rut", "")),
    "reparar_tasa_rota_con_oro": lambda p: reparar_tasa_rota(),
    "reparsear_correo_fallido": lambda p: reparsear_correo(p.get("message_id", "")),
    "corregir_protocolo_mal_clasificado": lambda p: corregir_protocolo(p.get("caso_id", ""), p.get("protocolo", "")),
    "reenriquecer_carpeta_manual": lambda p: reparar_liquidaciones(p.get("caso_id", ""), p.get("rut", "")),
    "reiniciar_parser_cron": lambda p: reiniciar_parser(),
    "reintentar_envio_rebotado": lambda p: reintentar_envio(p.get("cola_id", "")),
    "reindexar_memoria_total": lambda p: reindexar_memoria(),
}


@martin.get("/reparaciones")
async def taller(request: Request):
    _exigir_martin(request)
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fallas = await db.martin_fallas.find({"estado": "pendiente"}, {"_id": 0}).sort("created_at", -1).to_list(50)
    historial = await db.sistema_reparaciones_log.find({}, {"_id": 0}).sort("created_at", -1).to_list(80)
    herramientas = await db.sistema_herramientas_permisos.find({}, {"_id": 0}).to_list(30)
    detectadas_hoy = await db.martin_fallas.count_documents({"created_at": {"$gte": hoy}})
    reparadas_hoy = sum(1 for h in historial if (h.get("created_at") or "") >= hoy)
    tiempos = [h["tiempo_reparacion_ms"] for h in historial if h.get("tiempo_reparacion_ms")]
    oro = sum(1 for h in historial if h.get("quedo_con_oro"))
    return {"fallas": fallas, "historial": historial, "herramientas": herramientas,
            "kpis": {"fallas_hoy": detectadas_hoy, "reparadas_hoy": reparadas_hoy,
                     "tiempo_promedio_ms": int(sum(tiempos) / len(tiempos)) if tiempos else 0,
                     "tasa_oro": f"{round(100 * oro / len(historial))}%" if historial else "100%"}}


@martin.post("/reparar")
async def reparar(request: Request, payload: dict):
    _exigir_martin(request)
    herramienta = (payload or {}).get("herramienta", "")
    params = (payload or {}).get("params") or {}
    perm = await db.sistema_herramientas_permisos.find_one({"id": herramienta})
    if not perm:
        raise HTTPException(status_code=404, detail="Herramienta desconocida")
    u = _user(request)
    if perm.get("requiere_autorizacion_gerardo"):
        await db.correos_autorizacion_admin.insert_one({
            "id": str(uuid.uuid4()), "correo_salida_id": "", "caso_id": "",
            "cliente_nombre": f"SOLICITUD DE MARTÍN: {herramienta}", "cliente_rut": "",
            "protocolo_detectado": "solicitud_masivo", "clasificacion_ia": "solicitud_herramienta_protegida",
            "confianza_ia": 100, "documentos_tiene": [], "documentos_faltan": [],
            "mensaje_propuesto": (f"<p>🔒 <b>{u.get('nombre') or 'Martín'}</b> solicita usar la herramienta "
                                  f"protegida <b>{herramienta}</b>.<br>{perm.get('descripcion')}"
                                  f"<br>Detalle: {str(params)[:300]}</p>"),
            "estado": "pendiente", "tipo": "solicitud_masivo", "created_at": _now()})
        import blindaje_correos as b
        await b._log("solicitud_herramienta_protegida", {"herramienta": herramienta, "por": u.get("nombre")})
        return {"ok": True, "requiere_autorizacion": True,
                "mensaje": "🔒 Solicitud enviada a Gerardo en la bandeja de autorización — nada se ejecutó"}
    fn = DISPATCH.get(herramienta)
    if not fn:
        raise HTTPException(status_code=400, detail="Herramienta de solo diagnóstico: usa el dashboard")
    res = await fn(params)
    if payload.get("falla_id"):
        await db.martin_fallas.update_one({"id": payload["falla_id"]},
                                          {"$set": {"estado": "reparada", "reparada_at": _now()}})
    return res


@martin.post("/vigia-ahora")
async def vigia_ahora(request: Request):
    _exigir_martin(request)
    n = await diagnostico_vigia()
    return {"ok": True, "fallas_nuevas": n}


@martin.post("/mejorar")
async def mejorar(request: Request, payload: dict):
    _exigir_martin(request)
    u = _user(request)
    return await mejorar_conocimiento((payload or {}).get("texto", ""), u.get("nombre") or "martin")


@martin.post("/fallas/{fid}/descartar")
async def descartar_falla(fid: str, request: Request):
    _exigir_martin(request)
    await db.martin_fallas.update_one({"id": fid}, {"$set": {"estado": "descartada"}})
    return {"ok": True}
