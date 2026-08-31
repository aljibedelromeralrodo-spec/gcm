"""🫀 TEMA VIVO V17 — Fase 1. Hambre nocturna 3am, espejo de pensamiento humano,
orgullo de oro y voz proactiva '¿La paso a mesa?' con autorización chica de 1 click.
RESTRICCIÓN FASE 1: solo el masivo >10 queda bloqueado; pasar 1 carpeta a mesa y
consultar a 1 cliente se permiten con el click chico de Gerardo."""
import uuid
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from fastapi import APIRouter, HTTPException, Request
from database import db

temavivo = APIRouter(prefix="/tema-vivo")

PERMISOS_V17 = [
    ("reparar_archivo_malo_luego_bueno", False, True, "Si llega archivo malo ignorado y luego el bueno 6/6, repara solo con oro", "reparacion"),
    ("simplificar_nudos", False, True, "Simplificar lo que da vueltas a 1 función única verdad — hambre 3am", "mejora"),
    ("aprender_solo_3am", False, True, "Hambre nocturna: aprende solo a las 3am sin pedir permiso", "mejora"),
    ("pasar_a_mesa_autorizacion_chica", True, True, "Cuando 6/6 pregunta '¿Corazón, la paso a mesa?' — 1 click de Gerardo — PERMITIDO", "envio"),
    ("enviar_consulta_autorizacion_chica", True, True, "Consulta a 1 cliente por docs faltantes — 1 click de Gerardo — PERMITIDO", "envio"),
    ("enviar_masivo_10", True, False, "Masivo >10 destinatarios — BLOQUEADO — única restricción Fase 1", "envio"),
]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _exigir(request):
    u = getattr(request.state, "user", {}) or {}
    ident = f"{u.get('sub') or ''} {u.get('nombre') or ''}".lower()
    if u.get("rol") not in ("admin", "maestro") and "martin" not in ident:
        raise HTTPException(status_code=403, detail="Tema Vivo: solo Admin y Martín")


async def seed_tema_vivo():
    for hid, req, puede, desc, cat in PERMISOS_V17:
        await db.sistema_herramientas_permisos.update_one({"id": hid}, {"$set": {
            "requiere_autorizacion_gerardo": req, "puede_usar_martin": puede,
            "descripcion": desc, "categoria": cat}}, upsert=True)
    try:
        await db.notificaciones_mesa_pendiente.create_index([("estado", 1), ("created_at", -1)])
        await db.tema_vivo_espejo.create_index([("created_at", -1)])
    except Exception:
        pass
    logging.info("🫀 Tema Vivo V17: permisos Fase 1 sembrados (solo masivo >10 bloqueado)")


async def espejo(pensamiento, caso_id="", rut="", paso="", duda="", retrocedio_a="", correccion="", logico=True, ms=0):
    await db.tema_vivo_espejo.insert_one({
        "id": str(uuid.uuid4()), "caso_id": caso_id, "cliente_rut": rut, "pensamiento": pensamiento,
        "paso_actual": paso, "duda_detectada": duda, "retrocedio_a": retrocedio_a,
        "correccion": correccion, "quedo_logico": logico, "tiempo_ms": ms, "created_at": _now()})


async def notificar_mesa(caso_id, rut, nombre, protocolo_id, est, correo_id=""):
    """Voz proactiva: carpeta 6/6 completa → pregunta '¿la paso a mesa?' (autorización chica)."""
    if await db.notificaciones_mesa_pendiente.find_one(
            {"caso_id": caso_id, "estado": "pendiente_autorizacion_chica"}):
        return None
    if await db.mesa_entrada_bandeja.find_one({"caso_id": caso_id, "estado": "pendiente"}):
        return None
    hubo_malo = await db.correos_blindaje_log.find_one(
        {"evento": "archivo_malo_ignorado", "detalle.caso_id": caso_id})
    meses = est.get("meses_tiene") or []
    rango = f" {meses[0][5:]}→{meses[-1][5:]}" if len(meses) >= 2 else ""
    proto = await db.credito_protocolos_tipo.find_one({"id": protocolo_id}) or {}
    liq_req = sum(1 for d in (proto.get("documentos_requeridos") or []) if d.startswith("liquidacion"))
    barra = (f"{est['liq_tiene']}/{liq_req}" if liq_req
             else f"{len(est['tiene'])}/{len(est['tiene'])} docs")
    msg = (f"Corazón, {'arreglé' if hubo_malo else 'completé'} la carpeta de {nombre or rut}"
           + (f" — llegó el archivo bueno, antes estaba malo y lo ignoré," if hubo_malo else " —")
           + f" ahora está {barra}{rango} completa"
           + (", encontré el documento que faltaba y lo reparé con oro" if hubo_malo else "")
           + ". ¿La paso a mesa de riesgo?")
    nid = str(uuid.uuid4())
    await db.notificaciones_mesa_pendiente.insert_one({
        "id": nid, "caso_id": caso_id, "cliente_rut": rut or "", "cliente_nombre": nombre or "",
        "protocolo_id": protocolo_id, "barra": barra,
        "meses_tiene": meses, "mensaje_vivo": msg,
        "estado": "pendiente_autorizacion_chica", "reparada_con_oro": bool(hubo_malo),
        "antes": "archivo malo ignorado" if hubo_malo else "",
        "despues": f"{barra} completa", "correo_id": correo_id,
        "modulo_mesa": est.get("modulo_mesa", "riesgo"), "created_at": _now()})
    if hubo_malo:
        import martin_taller as mt
        await mt._log_reparacion("archivo_malo_luego_bueno", "reparar_archivo_malo_luego_bueno",
                                 "Llegó el archivo bueno tras uno malo ignorado — carpeta completada sola",
                                 {"estado": "archivo malo ignorado"},
                                 {"estado": f"{barra} con oro{rango}"},
                                 caso_id, rut, reparador="tema_vivo")
        await espejo(f"Llegó el archivo bueno de {rut}… antes estaba malo y lo ignoré… "
                     f"ahora {barra}{rango}… reparé con oro… lógico y fluido.",
                     caso_id, rut, "reparar_archivo", "archivo malo previo", "esperar el bueno",
                     "carpeta completada con oro")
    import blindaje_correos as b
    await b._log("carpeta_completa_pregunta_mesa", {"caso_id": caso_id, "mensaje": msg[:150]})
    return nid


# ═══════════ LOOP: voz proactiva cada 2 min + hambre nocturna 3am ═══════════
async def tema_vivo_loop():
    import blindaje_correos as b
    await asyncio.sleep(200)
    while True:
        try:
            casos = await db.clientes_carpetas_documentos.distinct("caso_id")
            for cid in casos[:120]:
                d0 = await db.clientes_carpetas_documentos.find_one({"caso_id": cid})
                proto = (d0 or {}).get("protocolo_id") or "dependiente_simple"
                est = await b._estado_carpeta(cid, proto)
                if not est["faltan"] and est["liq_tiene"] > 0:
                    caso = await db.blindaje_casos.find_one({"id": cid}) or {}
                    fold = await db.folders.find_one({"id": cid}, {"nombre": 1, "rut": 1}) or {}
                    await notificar_mesa(cid, d0.get("cliente_rut") or fold.get("rut", ""),
                                         caso.get("cliente_nombre") or fold.get("nombre", ""),
                                         proto, est)
            ahora_scl = datetime.now(ZoneInfo("America/Santiago"))
            hoy = ahora_scl.strftime("%Y-%m-%d")
            if ahora_scl.hour == 3:
                ya = await db.tema_vivo_hambre_log.find_one({"fecha": hoy})
                if not ya:
                    await hambre_nocturna(hoy)
        except Exception as e:
            logging.warning(f"tema vivo loop: {str(e)[:150]}")
        await asyncio.sleep(120)


async def hambre_nocturna(fecha=None):
    """3am: aprende solo — revisa, simplifica nudos y deja registro de lo aprendido."""
    import guardian_logico as g
    fecha = fecha or datetime.now(ZoneInfo("America/Santiago")).strftime("%Y-%m-%d")
    score_antes = (await g.calcular_score())["total"]
    r = await g.revision_completa()
    score_despues = r["score"]["total"]
    aprendizajes = []
    hace24 = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    async for x in db.sistema_backtracking_log.find({"created_at": {"$gte": hace24}}).limit(10):
        aprendizajes.append(f"{x['incoherencia_detectada'][:80]} → {x['correccion_aplicada'][:60]}")
    que_aprendi = (" · ".join(aprendizajes[:3]) if aprendizajes
                   else "Sin incoherencias en 24h — el flujo único se mantiene simple y fluido")
    await db.tema_vivo_hambre_log.insert_one({
        "id": str(uuid.uuid4()), "fecha": fecha, "que_aprendi": que_aprendi,
        "nudo_detectado": f"{r['nudos']} nudo(s)" if r["nudos"] else "sin nudos",
        "simplificacion_aplicada": r["reporte"][:250],
        "score_antes": score_antes, "score_despues": score_despues,
        "quedo_con_oro": True, "created_at": _now()})
    await espejo(f"Hambre nocturna 3am… revisé todo el sistema… {r['nudos']} nudos, "
                 f"{r['backtrackings']} retrocesos… score {score_antes}→{score_despues}… "
                 "aprendí solo, sin pedir permiso, quedó con oro.",
                 paso="hambre_3am", correccion=que_aprendi[:120])
    return {"score_antes": score_antes, "score_despues": score_despues, "aprendi": que_aprendi}


# ═══════════ RUTAS ═══════════
@temavivo.get("/estado")
async def estado(request: Request):
    _exigir(request)
    notifs = await db.notificaciones_mesa_pendiente.find(
        {"estado": "pendiente_autorizacion_chica"}, {"_id": 0}).sort("created_at", -1).to_list(30)
    hambre = await db.tema_vivo_hambre_log.find({}, {"_id": 0}).sort("created_at", -1).to_list(30)
    espejo_nat = await db.tema_vivo_espejo.find({}, {"_id": 0}).sort("created_at", -1).to_list(40)
    backs = await db.sistema_backtracking_log.find({}, {"_id": 0}).sort("created_at", -1).to_list(30)
    for x in backs:
        x["pensamiento"] = (f"Caso {x.get('cliente_rut') or str(x.get('caso_id'))[:8]}… "
                            f"dudé: {x.get('incoherencia_detectada','')[:90]}… "
                            f"retrocedí a {x.get('retrocede_a')}… {x.get('correccion_aplicada','')[:80]}… "
                            f"{'lógico' if x.get('quedo_logico') else 'pendiente'} en {x.get('tiempo_ms')}ms")
        x["origen"] = "backtracking"
    pensamientos = sorted(espejo_nat + backs, key=lambda z: z.get("created_at", ""), reverse=True)[:50]
    oro = await db.sistema_reparaciones_log.find(
        {"quedo_con_oro": True}, {"_id": 0}).sort("created_at", -1).to_list(40)
    return {"notificaciones": notifs, "hambre": hambre, "pensamientos": pensamientos, "orgullo_oro": oro,
            "restriccion": "FASE 1 — Repara solo con oro + pregunta '¿la paso a mesa?' 1 click — Masivo >10 BLOQUEADO"}


@temavivo.post("/mesa/{nid}/pasar")
async def pasar_a_mesa(nid: str, request: Request):
    _exigir(request)
    n = await db.notificaciones_mesa_pendiente.find_one({"id": nid})
    if not n or n["estado"] != "pendiente_autorizacion_chica":
        raise HTTPException(status_code=404, detail="Notificación no encontrada o ya resuelta")
    u = getattr(request.state, "user", {}) or {}
    await db.mesa_entrada_bandeja.insert_one({
        "id": str(uuid.uuid4()), "caso_id": n["caso_id"], "correo_id": n.get("correo_id", ""),
        "protocolo_id": n.get("protocolo_id", ""), "tipo": "carpeta_completa_lista_mesa",
        "prioridad": "alta", "estado": "pendiente", "modulo_asignado": n.get("modulo_mesa", "riesgo"),
        "requiere_accion": True, "sla_horas": 24,
        "vence_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
        "autorizado_chica_por": u.get("nombre") or "admin", "created_at": _now()})
    await db.notificaciones_mesa_pendiente.update_one({"id": nid}, {"$set": {
        "estado": "en_mesa_riesgo", "autorizado_por": u.get("nombre") or "admin", "autorizado_at": _now()}})
    import martin_taller as mt
    await mt._log_reparacion("carpeta_a_mesa", "pasar_a_mesa_autorizacion_chica",
                             f"Autorización chica de {u.get('nombre') or 'Gerardo'}: carpeta pasada a mesa {n.get('modulo_mesa','riesgo')}",
                             {"estado": "pendiente_autorizacion_chica"}, {"estado": "en_mesa_riesgo"},
                             n["caso_id"], n.get("cliente_rut", ""), reparador="tema_vivo")
    await espejo(f"Gerardo dijo que sí con 1 click… carpeta {n.get('cliente_rut')} pasada a mesa "
                 f"{n.get('modulo_mesa','riesgo')}… fluido, sin vueltas.", n["caso_id"],
                 n.get("cliente_rut", ""), "mesa", correccion="en_mesa_riesgo")
    return {"ok": True, "mensaje": f"✅ Carpeta en mesa de {n.get('modulo_mesa', 'riesgo')} — quedó con oro"}


@temavivo.post("/mesa/{nid}/mas-tarde")
async def mas_tarde(nid: str, request: Request):
    _exigir(request)
    await db.notificaciones_mesa_pendiente.update_one(
        {"id": nid}, {"$set": {"estado": "pospuesta", "pospuesta_at": _now()}})
    return {"ok": True}


@temavivo.post("/hambre-ahora")
async def hambre_ahora(request: Request):
    _exigir(request)
    r = await hambre_nocturna()
    return {"ok": True, **r}
