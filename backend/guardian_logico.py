"""🧠 GUARDIÁN LÓGICO V16.5 — Mente humana con backtracking.
Mapea el sistema, detecta nudos (lo que da vueltas), simplifica a UNA sola verdad,
valida coherencia en cada caso y SABE CUÁNDO RETROCEDER (máx 3 niveles).
Vigila cada 10 min que todo sea lógico, simple, sencillo y fluido."""
import time
import uuid
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request
from database import db

guardian = APIRouter(prefix="/guardian")

FLUJO_UNICO = [
    {"paso": "entrada", "icono": "📥", "nombre": "Entrada correo gerardo.ext", "detalle": "IMAP cada 5 min (cuida la cuota de Google), dedup por message_id"},
    {"paso": "clasifica", "icono": "🧠", "nombre": "¿Solicitud de crédito?", "detalle": "Claude clasifica protocolo + docs adjuntos; NO → archiva"},
    {"paso": "carpeta", "icono": "📁", "nombre": "¿Carpeta existe por RUT?", "detalle": "NO → crea con 6 liquidaciones + docs del protocolo faltantes"},
    {"paso": "enriquece", "icono": "⚡", "nombre": "¿Adjuntos traen docs faltantes?", "detalle": "Enriquece auto (incluye PDF 6-en-1) → recalcula 0/6→6/6"},
    {"paso": "completa", "icono": "✅", "nombre": "¿Carpeta 6/6 completa?", "detalle": "SÍ → Mesa (riesgo/contralor) prioridad alta, fluido"},
    {"paso": "autorizacion", "icono": "🔒", "nombre": "Faltan docs → Autorización Admin", "detalle": "Genera correo SOLO con lo que falta real; JAMÁS envía solo"},
    {"paso": "envio", "icono": "📤", "nombre": "Envío blindado gerardo.ext", "detalle": "Resend/SMTP + retry + supresión rebotes"},
    {"paso": "vuelta", "icono": "🔄", "nombre": "Llega respuesta con doc", "detalle": "Retrocede lógico → re-enriquece → vuelve a ¿6/6?"},
]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _exigir(request):
    u = getattr(request.state, "user", {}) or {}
    ident = f"{u.get('sub') or ''} {u.get('nombre') or ''}".lower()
    if u.get("rol") not in ("admin", "maestro") and "martin" not in ident:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Guardián Lógico: solo Admin y Martín")


async def _log_backtrack(caso_id, rut, paso, incoherencia, retrocede_a, correccion, quedo_logico, ms):
    await db.sistema_backtracking_log.insert_one({
        "id": str(uuid.uuid4()), "caso_id": caso_id, "cliente_rut": rut, "paso_actual": paso,
        "incoherencia_detectada": incoherencia, "retrocede_a": retrocede_a,
        "razon_backtracking": "Mente humana detecta que no cuadra",
        "correccion_aplicada": correccion, "quedo_logico": quedo_logico,
        "tiempo_ms": ms, "created_at": _now()})


# ═══════════ BACKTRACKING MENTE HUMANA (máx 3 niveles) ═══════════
async def validar_caso(caso_id, nivel=0):
    """Valida la lógica de un caso; si hay incoherencia RETROCEDE, corrige y re-valida."""
    import blindaje_correos as b
    import martin_taller as mt
    if nivel >= 3:
        return {"logico": False, "motivo": "límite de backtracking (3 niveles)"}
    t0 = time.time()
    doc0 = await db.clientes_carpetas_documentos.find_one({"caso_id": caso_id})
    if not doc0:
        return {"logico": True, "motivo": "sin carpeta"}
    proto_id = doc0.get("protocolo_id") or "dependiente_simple"
    rut = doc0.get("cliente_rut", "")
    proto = await db.credito_protocolos_tipo.find_one({"id": proto_id}) or {}
    prohibidos = set(proto.get("nunca_pedir") or [])

    # 1) INCOHERENCIA: la carpeta tiene faltantes PROHIBIDOS por el protocolo (ej dependiente pidiendo carpeta tributaria)
    mal = await db.clientes_carpetas_documentos.find(
        {"caso_id": caso_id, "estado": "faltante", "documento_tipo": {"$in": list(prohibidos)}}).to_list(20)
    if mal:
        nombres = [m["documento_tipo"] for m in mal]
        await db.clientes_carpetas_documentos.delete_many(
            {"caso_id": caso_id, "estado": "faltante", "documento_tipo": {"$in": nombres}})
        await mt.reparar_liquidaciones(caso_id=caso_id)
        await _log_backtrack(caso_id, rut, "generar_faltantes",
                             f"Protocolo {proto_id} no puede pedir: {', '.join(nombres)}",
                             "clasificar_protocolo", f"Docs prohibidos eliminados de faltantes ({len(nombres)})",
                             True, int((time.time() - t0) * 1000))
        return await validar_caso(caso_id, nivel + 1)

    est = await b._estado_carpeta(caso_id, proto_id)
    # 2) INCOHERENCIA: liquidaciones sobre el tope (liquidacion_7+) o conteo fuera de rango
    tope = 12 if proto_id == "con_codeudor" else 6
    extra = await db.clientes_carpetas_documentos.find(
        {"caso_id": caso_id, "documento_tipo": {"$regex": r"^liquidacion_([7-9]|\d{2})$"}}).to_list(20)
    if extra or est["liq_tiene"] > tope or est["liq_tiene"] < 0:
        if extra:
            await db.clientes_carpetas_documentos.delete_many(
                {"id": {"$in": [e["id"] for e in extra]}})
        await mt.reparar_liquidaciones(caso_id=caso_id)
        await _log_backtrack(caso_id, rut, "conteo_liquidaciones",
                             f"Liquidaciones sobre el tope o fuera de rango (liq_tiene={est['liq_tiene']}, extra={len(extra)})",
                             "recontar_6_liquidaciones", "Liquidaciones sobre el tope eliminadas y recontadas",
                             True, int((time.time() - t0) * 1000))
        return await validar_caso(caso_id, nivel + 1)

    # 3) INCOHERENCIA: correo pendiente pide documentos que YA están recibidos
    async for a in db.correos_autorizacion_admin.find({"caso_id": caso_id, "estado": "pendiente"}):
        pide_recibidos = set(a.get("documentos_faltan") or []) & set(est["tiene"])
        desalineado = (a.get("liquidaciones_tiene") != est["liq_tiene"]
                       or set(a.get("documentos_faltan") or []) != set(est["faltan"]))
        if pide_recibidos or desalineado:
            if not est["faltan"]:
                await db.correos_autorizacion_admin.update_one({"id": a["id"]}, {"$set": {
                    "estado": "rechazado", "revisado_por": "guardian_logico",
                    "revisado_at": _now(), "nota": "Carpeta ya completa — correo innecesario cortado (anti-loop)"}})
                await db.correos_salida_cola_blindada.update_one(
                    {"id": a.get("correo_salida_id", "")}, {"$set": {"estado": "rechazado"}})
                correccion = "Loop cortado: carpeta completa, correo de faltantes anulado"
            else:
                asunto, body = await b._generar_correo_faltantes(a.get("cliente_nombre"), rut, proto_id, est)
                await db.correos_autorizacion_admin.update_one({"id": a["id"]}, {"$set": {
                    "documentos_tiene": est["tiene"], "documentos_faltan": est["faltan"],
                    "liquidaciones_tiene": est["liq_tiene"], "liquidaciones_faltan": est["liq_faltan"],
                    "mensaje_propuesto": body}})
                await db.correos_salida_cola_blindada.update_one(
                    {"id": a.get("correo_salida_id", "")},
                    {"$set": {"asunto": asunto, "body_html": body, "documentos_faltantes": est["faltan"],
                              "liquidaciones_tiene": est["liq_tiene"], "liquidaciones_faltan": est["liq_faltan"]}})
                correccion = f"Correo regenerado pidiendo SOLO lo que falta real ({len(est['faltan'])} docs)"
            await _log_backtrack(caso_id, rut, "correo_faltantes",
                                 ("Pedía docs ya recibidos: " + ", ".join(sorted(pide_recibidos))) if pide_recibidos
                                 else "Conteo del correo desalineado con la carpeta real",
                                 "enriquecer_carpeta", correccion, True, int((time.time() - t0) * 1000))
            return await validar_caso(caso_id, nivel + 1)

    # 4) INCOHERENCIA: marcada lista para mesa pero faltan docs (o al revés)
    mesa = await db.mesa_entrada_bandeja.find_one({"caso_id": caso_id, "estado": "pendiente"})
    if mesa and est["faltan"]:
        await db.mesa_entrada_bandeja.update_one({"id": mesa["id"]}, {"$set": {
            "estado": "retirada", "nota": "Guardián: la carpeta aún tiene faltantes — retrocedida de mesa"}})
        await _log_backtrack(caso_id, rut, "mesa", "Estaba en mesa con documentos faltantes",
                             "verificar_completa", "Retirada de mesa hasta completar", True,
                             int((time.time() - t0) * 1000))
        return await validar_caso(caso_id, nivel + 1)
    return {"logico": True, "liq": est["liq_tiene"], "faltan": len(est["faltan"])}


# ═══════════ MAPA DEL SISTEMA + NUDOS (lo que da vueltas) ═══════════
COMPONENTES = [
    ("flujo", "blindaje_parser_loop", "Lee inbox cada 90s, clasifica con Claude, crea/enriquece carpeta", ["clasificador", "carpeta"], 3),
    ("funcion", "_estado_carpeta", "ÚNICA VERDAD del conteo 6 liquidaciones y faltantes (anti-mezcla)", ["carpeta"], 1),
    ("funcion", "_enriquecer", "Marca docs recibidos, expande PDF 6-en-1", ["_estado_carpeta"], 2),
    ("flujo", "bandeja_autorizacion", "Correos de faltantes esperan autorización del Admin — jamás salen solos", ["_estado_carpeta"], 1),
    ("flujo", "enviar_correo_blindado", "Envío Resend/SMTP con retry, supresión y footer anti-spam", ["bandeja_autorizacion"], 2),
    ("flujo", "martin_vigia_loop", "Vigía cada 10 min: parser, tasas, conteos, cola", ["taller"], 2),
    ("flujo", "guardian_logico_loop", "Mente humana: valida coherencia + backtracking cada 10 min", ["todo"], 2),
    ("coleccion", "clientes_carpetas_documentos", "Estado real de cada documento por caso (fuente única)", [], 1),
    ("prompt", "clasificador_protocolos", "UN solo prompt Claude clasifica protocolo + adjuntos", [], 1),
]


async def detectar_nudos():
    """Nudos REALES desde los datos: duplicados, contradicciones, loops."""
    nudos = []

    async def _nudo(nombre, hace, duplica, complejidad, fix, params=None):
        nudos.append({"id": str(uuid.uuid4()), "componente": "nudo", "nombre": nombre, "hace": hace,
                      "duplica_a": duplica, "complejidad": complejidad, "es_nudo": True,
                      "simplificable": True, "fix": fix, "params": params or {}, "created_at": _now()})

    pipeline = [{"$match": {"estado": "pendiente"}}, {"$group": {"_id": "$caso_id", "n": {"$sum": 1}}},
                {"$match": {"n": {"$gt": 1}}}]
    async for g in db.correos_autorizacion_admin.aggregate(pipeline):
        await _nudo(f"Autorizaciones duplicadas caso {str(g['_id'])[:8]}",
                    f"{g['n']} correos pendientes para el MISMO caso — da vueltas",
                    ["correos_autorizacion_admin"], 6, "backtrack_caso", {"caso_id": g["_id"]})
    async for g in db.mesa_entrada_bandeja.aggregate(pipeline):
        await _nudo(f"Mesa duplicada caso {str(g['_id'])[:8]}", f"{g['n']} entradas de mesa para el mismo caso",
                    ["mesa_entrada_bandeja"], 5, "backtrack_caso", {"caso_id": g["_id"]})
    for d in await db.clientes_carpetas_documentos.aggregate([
            {"$match": {"estado": "faltante"}},
            {"$lookup": {"from": "credito_protocolos_tipo", "localField": "protocolo_id",
                         "foreignField": "id", "as": "p"}},
            {"$unwind": "$p"},
            {"$match": {"$expr": {"$in": ["$documento_tipo", "$p.nunca_pedir"]}}},
            {"$group": {"_id": "$caso_id", "docs": {"$addToSet": "$documento_tipo"}}}]).to_list(20):
        await _nudo(f"Incoherencia protocolo caso {str(d['_id'])[:8]}",
                    f"Pide docs prohibidos por su protocolo: {', '.join(d['docs'])} (error de clasificación)",
                    ["clientes_carpetas_documentos"], 8, "backtrack_caso", {"caso_id": d["_id"]})
    extra = await db.clientes_carpetas_documentos.distinct(
        "caso_id", {"documento_tipo": {"$regex": "^liquidacion_([7-9]|\\d{2})$"}})
    for c in extra[:10]:
        await _nudo(f"Más de 6 liquidaciones caso {str(c)[:8]}", "Conteo dio vuelta sobre el tope de 6",
                    ["clientes_carpetas_documentos"], 7, "backtrack_caso", {"caso_id": c})
    return nudos


async def calcular_score():
    nudos = await db.sistema_mapa_logico.count_documents({"es_nudo": True, "estado": {"$ne": "simplificado"}})
    hace24 = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    incoherencias = await db.sistema_backtracking_log.count_documents(
        {"created_at": {"$gte": hace24}, "quedo_logico": False})
    simplicidad = max(0, 100 - nudos * 10)
    logica = max(0, 100 - incoherencias * 10)
    tiempos = []
    async for m in db.mesa_entrada_bandeja.find({}).sort("created_at", -1).limit(20):
        c = await db.correos_clasificacion.find_one({"caso_id": m.get("caso_id")}, {"created_at": 1})
        if c:
            try:
                dt = (datetime.fromisoformat(m["created_at"]) - datetime.fromisoformat(c["created_at"])).total_seconds()
                if 0 <= dt < 3600:
                    tiempos.append(dt)
            except Exception:
                pass
    fluidez_seg = round(sum(tiempos) / len(tiempos), 1) if tiempos else 0
    fluidez = 100 if fluidez_seg <= 20 else 70 if fluidez_seg <= 30 else 40
    total = round((simplicidad + logica + fluidez) / 3)
    return {"total": total, "simplicidad": simplicidad, "logica": logica,
            "fluidez": fluidez, "fluidez_seg": fluidez_seg, "nudos": nudos,
            "incoherencias_24h": incoherencias}


async def revision_completa():
    """Mente humana on-demand: mapea → detecta nudos → backtracking donde no cuadra → score."""
    t0 = time.time()
    await db.sistema_mapa_logico.delete_many({"componente": {"$ne": "nudo_simplificado"}})
    for tipo, nombre, hace, dep, comp in COMPONENTES:
        await db.sistema_mapa_logico.insert_one({
            "id": str(uuid.uuid4()), "componente": tipo, "nombre": nombre, "hace": hace,
            "depende_de": dep, "duplica_a": [], "complejidad": comp, "es_nudo": False,
            "simplificable": False, "created_at": _now()})
    nudos = await detectar_nudos()
    if nudos:
        await db.sistema_mapa_logico.insert_many([dict(n) for n in nudos])
    backtracks = 0
    casos = {n["params"]["caso_id"] for n in nudos if n.get("params", {}).get("caso_id")}
    async for a in db.correos_autorizacion_admin.find({"estado": "pendiente"}, {"caso_id": 1}).limit(40):
        if a.get("caso_id"):
            casos.add(a["caso_id"])
    resultados = []
    for cid in list(casos)[:40]:
        r = await validar_caso(cid)
        if not r.get("motivo", "").startswith("sin"):
            resultados.append(r)
        backtracks += 0 if r.get("logico") and "liq" in r else 0
    hace1m = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    backtracks = await db.sistema_backtracking_log.count_documents({"created_at": {"$gte": hace1m}})
    for n in nudos:
        if n.get("params", {}).get("caso_id"):
            await db.sistema_mapa_logico.update_one({"id": n["id"]}, {"$set": {"estado": "simplificado"}})
    score = await calcular_score()
    reporte = (f"Revisé el sistema como mente humana: {len(nudos)} nudo(s) detectado(s), "
               f"{backtracks} backtracking(s) — retrocedí donde había que retroceder. "
               f"Sistema ahora {score['total']}% lógico, simple, sencillo y fluido.")
    await db.dashai_eventos.insert_one({"tipo": "guardian_logico_revision", "fecha": _now(),
                                        "detalle": reporte})
    return {"reporte": reporte, "nudos": len(nudos), "backtrackings": backtracks,
            "score": score, "ms": int((time.time() - t0) * 1000)}


async def guardian_loop():
    await asyncio.sleep(300)
    while True:
        try:
            r = await revision_completa()
            if r["score"]["total"] < 80:
                await db.dashai_eventos.insert_one({
                    "tipo": "guardian_alerta_score", "fecha": _now(),
                    "detalle": f"⚠️ Sistema {r['score']['total']}% lógico (<80) — {r['reporte']}"})
        except Exception as e:
            logging.warning(f"guardián lógico: {str(e)[:150]}")
        await asyncio.sleep(600)


# ═══════════ RUTAS ═══════════
@guardian.get("/estado")
async def estado(request: Request):
    _exigir(request)
    score = await calcular_score()
    nudos = await db.sistema_mapa_logico.find(
        {"es_nudo": True, "estado": {"$ne": "simplificado"}}, {"_id": 0}).sort("created_at", -1).to_list(30)
    mapa = await db.sistema_mapa_logico.find(
        {"es_nudo": {"$ne": True}}, {"_id": 0}).to_list(30)
    backs = await db.sistema_backtracking_log.find({}, {"_id": 0}).sort("created_at", -1).to_list(60)
    return {"score": score, "flujo": FLUJO_UNICO, "nudos": nudos, "mapa": mapa, "backtracking": backs}


@guardian.post("/revisar-ahora")
async def revisar_ahora(request: Request):
    _exigir(request)
    return await revision_completa()


@guardian.post("/nudos/{nid}/simplificar")
async def simplificar_nudo(nid: str, request: Request):
    _exigir(request)
    n = await db.sistema_mapa_logico.find_one({"id": nid})
    if not n:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Nudo no encontrado")
    caso_id = (n.get("params") or {}).get("caso_id", "")
    res = await validar_caso(caso_id) if caso_id else {"logico": True}
    dups = await db.correos_autorizacion_admin.find(
        {"caso_id": caso_id, "estado": "pendiente"}).sort("created_at", -1).to_list(10)
    for d in dups[1:]:
        await db.correos_autorizacion_admin.update_one({"id": d["id"]}, {"$set": {
            "estado": "rechazado", "revisado_por": "guardian_logico", "nota": "Duplicado simplificado con oro"}})
        await db.correos_salida_cola_blindada.update_one({"id": d.get("correo_salida_id", "")},
                                                         {"$set": {"estado": "rechazado"}})
    mesas = await db.mesa_entrada_bandeja.find({"caso_id": caso_id, "estado": "pendiente"}).to_list(10)
    for m in mesas[1:]:
        await db.mesa_entrada_bandeja.update_one({"id": m["id"]}, {"$set": {"estado": "retirada"}})
    await db.sistema_mapa_logico.update_one({"id": nid}, {"$set": {"estado": "simplificado",
                                                                   "simplificado_at": _now()}})
    import martin_taller as mt
    await mt._log_reparacion("nudo_logico", "simplificar_con_oro",
                             f"Nudo simplificado: {n.get('nombre')}", {"nudo": n.get("hace")},
                             {"resultado": res}, caso_id, reparador="guardian_logico")
    return {"ok": True, "resultado": res, "mensaje": "✨ Nudo simplificado con oro — quedó una sola verdad"}
