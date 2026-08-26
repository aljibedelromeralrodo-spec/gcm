"""Análisis de aprendizaje TOTAL del sistema (día 1 → hoy). Genera stats + base de conocimiento."""
import asyncio
import os
import re
import json
from collections import Counter
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
from motor.motor_asyncio import AsyncIOMotorClient

db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _dt(s):
    try:
        d = datetime.fromisoformat((s or "").replace("Z", "+00:00"))
        return d.replace(tzinfo=None)
    except Exception:
        return None


async def main():
    S = {}
    # ── 1. Correos entrantes / cola de procesamiento
    pq = await db.proc_queue.find({}, {"attachments_bytes_dir": 0, "body_full": 0}).to_list(3000)
    S["proc_total"] = len(pq)
    S["proc_status"] = dict(Counter((p.get("status") or "?") for p in pq).most_common())
    S["proc_con_carpeta"] = sum(1 for p in pq if p.get("drive_folder_id"))
    S["proc_fechas"] = [min((p.get("date_iso") or "9999") for p in pq)[:10],
                        max((p.get("date_iso") or "") for p in pq)[:10]]
    S["proc_top_dominios"] = dict(Counter(
        re.search(r"@([\w.-]+)", p.get("sender") or "").group(1).lower()
        for p in pq if re.search(r"@([\w.-]+)", p.get("sender") or "")).most_common(10))
    # documentos clasificados
    tipos, conf, adj_por_correo = Counter(), [], []
    tipo_cliente = Counter()
    for p in pq:
        cl = p.get("classification") or {}
        docs = cl.get("documentos") or []
        adj_por_correo.append(len(p.get("attachments") or []))
        if cl.get("tipo_cliente"):
            tipo_cliente[cl["tipo_cliente"]] += 1
        if cl.get("confianza") is not None:
            conf.append(float(cl.get("confianza") or 0))
        for d in docs:
            tipos[(d.get("tipo") or "desconocido")] += 1
    S["docs_tipos"] = dict(tipos.most_common(15))
    S["docs_total"] = sum(tipos.values())
    S["confianza_promedio"] = round(sum(conf) / len(conf), 3) if conf else None
    S["adjuntos_promedio"] = round(sum(adj_por_correo) / len(adj_por_correo), 1) if adj_por_correo else 0
    S["tipo_cliente"] = dict(tipo_cliente)
    # errores en cola
    S["proc_errores"] = dict(Counter(
        (p.get("error") or p.get("descartado_motivo") or "")[:70]
        for p in pq if p.get("status") in ("error", "descartado") and
        (p.get("error") or p.get("descartado_motivo"))).most_common(8))

    # ── 2. Carpetas
    fl = await db.folders.find({}, {"archivos": 1, "created_at": 1, "origen": 1, "id": 1,
                                    "codeudor_nombre": 1, "nombre": 1, "credit_request": 1,
                                    "resultado_mesa": 1, "source_email": 1}).to_list(1000)
    S["folders_total"] = len(fl)
    S["folders_origen"] = dict(Counter((f.get("origen") or "manual/desconocido") for f in fl).most_common())
    S["folders_con_codeudor"] = sum(1 for f in fl if f.get("codeudor_nombre"))
    S["folders_fechas"] = [min((f.get("created_at") or "9999") for f in fl)[:10],
                           max((f.get("created_at") or "") for f in fl)[:10]]
    S["folders_archivos_prom"] = round(sum(len(f.get("archivos") or []) for f in fl) / max(len(fl), 1), 1)
    S["folders_resultado_mesa"] = dict(Counter(
        (str(f.get("resultado_mesa") or {}).lower()[:0] or (f.get("resultado_mesa") or {}).get("tipo", "sin_veredicto")
         if isinstance(f.get("resultado_mesa"), dict) else "sin_veredicto") for f in fl).most_common())

    # ── 3. Envíos a Mesa / seguimiento
    seg = await db.seguimiento.find({}).to_list(2000)
    S["seguimiento_total"] = len(seg)
    S["seguimiento_estado"] = dict(Counter((s.get("estado") or "?") for s in seg).most_common())

    # ── 4. Veredictos de Mesa
    mv = await db.mesa_verdad_log.find({}).to_list(1000)
    S["mesa_total"] = len(mv)
    S["mesa_tipos"] = dict(Counter((m.get("tipo") or m.get("accion") or "?") for m in mv).most_common())

    # ── 5. Correos SALIENTES
    sm = await db.correos_smtp_log.find({}).to_list(3000)
    S["smtp_total"] = len(sm)
    S["smtp_ok"] = sum(1 for x in sm if x.get("success"))
    S["smtp_errores"] = dict(Counter((x.get("error") or "")[:60] for x in sm if not x.get("success") and x.get("error")).most_common(6))
    S["smtp_desde"] = dict(Counter((x.get("desde") or "?") for x in sm).most_common())
    S["smtp_fechas"] = [min((x.get("fecha") or "9999") for x in sm)[:10], max((x.get("fecha") or "") for x in sm)[:10]]
    cat = Counter()
    for x in sm:
        s = (x.get("subject") or "").lower()
        if "rechaz" in s: cat["rechazos"] += 1
        elif "aprobac" in s or "aprobado" in s or "califica" in s: cat["aprobaciones"] += 1
        elif "faltan" in s or "falta" in s or "pendiente" in s: cat["faltantes/documentos"] += 1
        elif "antecedentes" in s or "credito" in s or "crédito" in s: cat["sets a mesa/antecedentes"] += 1
        elif "resumen" in s or "informe" in s or "reporte" in s: cat["informes/resúmenes"] += 1
        elif "gasto" in s: cat["gastos operacionales"] += 1
        elif "tasaci" in s: cat["tasaciones"] += 1
        else: cat["otros"] += 1
    S["smtp_categorias"] = dict(cat.most_common())
    S["duplicados_bloqueados"] = await db.correos_duplicados_bloqueados.count_documents({})
    S["omitidos_normativa"] = await db.correos_omitidos_normativa.count_documents({})
    S["preview_estados"] = {}
    async for g in db.correos_preview.aggregate([{"$group": {"_id": "$estado", "n": {"$sum": 1}}}]):
        S["preview_estados"][g["_id"]] = g["n"]

    # ── 6. Rechazos / aprobaciones notificadas + autocorreo
    S["rechazos_notificados"] = await db.rechazos_notificados.count_documents({})
    S["rechazos_pendientes"] = await db.rechazos_pendientes.count_documents({})
    ac = await db.autocorreo_log.find({}).to_list(2000)
    S["autocorreo_total"] = len(ac)
    S["autocorreo_status"] = dict(Counter((a.get("status") or "?") for a in ac).most_common())

    # ── 7. Alertas (síntomas del sistema)
    S["alertas_total"] = await db.alertas.count_documents({})
    S["alertas_tipos"] = {}
    async for g in db.alertas.aggregate([{"$group": {"_id": "$tipo", "n": {"$sum": 1}}},
                                         {"$sort": {"n": -1}}, {"$limit": 12}]):
        S["alertas_tipos"][g["_id"] or "?"] = g["n"]

    # ── 8. Clasificaciones IA (nuevo clasificador)
    S["clasif_ia_total"] = await db.clasificaciones_ia.count_documents({})
    S["clasif_ia_cats"] = {}
    async for g in db.clasificaciones_ia.aggregate([{"$group": {"_id": "$categoria", "n": {"$sum": 1}}}]):
        S["clasif_ia_cats"][g["_id"] or "?"] = g["n"]

    # ── 9. TIEMPOS promedio por etapa
    # correo → carpeta (proc_queue.date_iso → folder.created_at, unidos por drive_folder_id)
    # correo → carpeta (drive_folder_id guarda el NOMBRE del cliente → unir por nombre)
    fmap = {f.get("id"): f for f in fl}
    fnom = {(f.get("nombre") or "").strip().lower(): f for f in fl}
    d1 = []
    for p in pq:
        f = fnom.get((p.get("drive_folder_id") or "").strip().lower())
        if not f:
            continue
        a, b = _dt(p.get("date_iso")), _dt(f.get("created_at"))
        if a and b and b >= a:
            d1.append((b - a).total_seconds() / 3600)
    S["t_correo_a_carpeta_h"] = {"n": len(d1), "prom": round(sum(d1) / len(d1), 1) if d1 else None,
                                 "mediana": round(sorted(d1)[len(d1) // 2], 1) if d1 else None}
    # carpeta → veredicto de mesa (folder.created_at → mesa_verdad_log.fecha_correo por folder_id)
    d2 = []
    for m in mv:
        f = fmap.get(m.get("folder_id"))
        if not f:
            continue
        a, b = _dt(f.get("created_at")), _dt(m.get("fecha_correo") or m.get("procesado_en"))
        if a and b and b >= a:
            d2.append((b - a).total_seconds() / 3600)
    S["t_carpeta_a_veredicto_h"] = {"n": len(d2), "prom": round(sum(d2) / len(d2), 1) if d2 else None,
                                    "mediana": round(sorted(d2)[len(d2) // 2], 1) if d2 else None}
    # veredicto mesa → detección por el sistema (fecha_correo → procesado_en)
    d3 = []
    for m in mv:
        a, b = _dt(m.get("fecha_correo")), _dt(m.get("procesado_en"))
        if a and b and b >= a:
            d3.append((b - a).total_seconds() / 60)
    S["t_veredicto_a_deteccion_min"] = {"n": len(d3), "prom": round(sum(d3) / len(d3), 1) if d3 else None,
                                        "mediana": round(sorted(d3)[len(d3) // 2], 1) if d3 else None}
    print(json.dumps(S, ensure_ascii=False, indent=1, default=str))

    # ── 10. PERSISTIR BASE DE CONOCIMIENTO (para clasificador IA y autorreparación)
    resumen_clasificador = (
        f"Datos REALES del sistema ({S['proc_fechas'][0]} → {S['proc_fechas'][1]}): "
        f"{S['proc_total']} correos de gestión procesados, {S['folders_total']} carpetas creadas. "
        f"Remitentes más frecuentes de solicitudes: ecomac.cl ({S['proc_top_dominios'].get('ecomac.cl', 0)}), "
        f"maestra.cl ({S['proc_top_dominios'].get('maestra.cl', 0)}), boetsch.cl ({S['proc_top_dominios'].get('boetsch.cl', 0)}), "
        f"gmail.com de clientes directos ({S['proc_top_dominios'].get('gmail.com', 0)}) y reenvíos internos de "
        f"centralmutuos.cl ({S['proc_top_dominios'].get('centralmutuos.cl', 0)}). "
        f"Una solicitud real trae en promedio {S['adjuntos_promedio']} adjuntos. Distribución documental real: "
        f"liquidaciones {S['docs_tipos'].get('liquidacion', 0)}, cédulas {S['docs_tipos'].get('cedula', 0)}, "
        f"CMF {S['docs_tipos'].get('certificado_smf', 0)}, AFP {S['docs_tipos'].get('cotizacion_afp', 0) + S['docs_tipos'].get('certificado_afp', 0)}, "
        f"boletas honorarios {S['docs_tipos'].get('boleta_honorarios', 0)} (solo {S['tipo_cliente'].get('independiente', 0)} "
        f"clientes independientes vs {S['tipo_cliente'].get('dependiente', 0)} dependientes). "
        f"OJO: {S['docs_tipos'].get('otro', 0)} de {S['docs_total']} documentos cayeron en 'otro' — muchos correos "
        f"reales traen firmas de imagen, contratos y papeles complementarios; su presencia NO invalida una solicitud. "
        f"La Mesa (aprobaciones@centralmutuos.cl) emitió {S['mesa_tipos'].get('aprobacion', 0)} aprobaciones y "
        f"{S['mesa_tipos'].get('rechazo', 0)} rechazos verificados. Los veredictos usan frases fijas: "
        "'Tenemos el agrado de informar…' (aprobación) y 'no cumple parámetros objetivos' / 'carga financiera' (rechazo).")
    resumen_flujo = (
        f"FLUJO REAL: correo entra (IMAP 2 casillas) → cola proc_queue → clasificación+OCR → carpeta "
        f"({S['proc_con_carpeta']}/{S['proc_total']} correos terminaron con carpeta; mediana correo→carpeta "
        f"{S['t_correo_a_carpeta_h']['mediana']} h) → set a Mesa → veredicto (mediana carpeta→veredicto "
        f"{S['t_carpeta_a_veredicto_h']['mediana']} h ≈ {round((S['t_carpeta_a_veredicto_h']['mediana'] or 0) / 24, 1)} días) "
        f"→ notificación. Debilidad histórica: la detección del veredicto tardaba mediana "
        f"{round((S['t_veredicto_a_deteccion_min']['mediana'] or 0) / 60, 1)} h (cuelgues IMAP ya corregidos con candados). "
        f"Salientes: {S['smtp_ok']}/{S['smtp_total']} SMTP exitosos; {S['duplicados_bloqueados']} duplicados bloqueados; "
        f"autocorreo: {S['autocorreo_status'].get('sent', 0)} enviados, {S['autocorreo_status'].get('failed', 0)} fallidos históricos.")
    from datetime import timezone
    await db.config.update_one({"_key": "base_conocimiento"}, {"$set": {
        "resumen_clasificador": resumen_clasificador, "resumen_flujo": resumen_flujo,
        "stats": json.loads(json.dumps(S, default=str)),
        "generado_en": datetime.now(timezone.utc).isoformat()}}, upsert=True)
    print("\n✅ base_conocimiento guardada en db.config", file=os.sys.stderr)

asyncio.run(main())
