"""🧠 CLASIFICADOR DOCUMENTAL — Solicitud de Crédito (reglas obligatorias por tipo de cliente).
Dependiente: liquidaciones + AFP (jamás boletas ni impuesto renta).
Independiente: boletas + impuesto renta (jamás liquidaciones ni AFP).
Mixto: ambos conjuntos. Carabineros/Ejército/Gendarmería: exentos de AFP (detección automática).
Codeudor: requerimiento documental independiente según su tipo. Licencia médica: se registra sin bloquear."""
import re
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from database import db
import folders_service as fsvc
import ocr_service

RX_EXENTAS = re.compile(r"carabineros\s+de\s+chile|ej[eé]rcito\s+de\s+chile|gendarmer[ií]a(\s+de\s+chile)?|"
                        r"direcci[oó]n\s+de\s+previsi[oó]n\s+de\s+carabineros|dipreca|capredena", re.I)
RX_LICENCIA = re.compile(r"licencia\s*m[eé]dica|subsidio\s+por\s+incapacidad\s+laboral", re.I)
RX_BOLETA = re.compile(r"boleta", re.I)
RX_LIQ = re.compile(r"liquidaci[oó]n", re.I)


def _now():
    return datetime.now(timezone.utc).isoformat()


def reglas_documentales(tipo, exento_afp=False):
    """Documentos requeridos (label, categoría) según tipo de cliente. Nunca mezcla prohibidos."""
    import validacion_documental as vdoc
    return [(vdoc.LABELS.get(c, c), c) for c in vdoc.cats_requeridas(tipo, exento_afp=exento_afp)]


def analizar_archivos_sync(nombre_folder):
    """Lee los archivos reales de la carpeta: evidencia de tipo, exención AFP (OCR de
    liquidaciones), licencia médica y codeudor (tipo según sus propios documentos)."""
    archivos = fsvc.scan_archivos(nombre_folder)
    base = fsvc.folder_dir(nombre_folder)
    cats, cod_files = set(), []
    licencia = False
    for a in archivos:
        cat = fsvc.cat_de_archivo(a["nombre"], a["subfolder"])
        if RX_LICENCIA.search(a["nombre"] or ""):
            licencia = True
        if cat == "codeudor":
            cod_files.append(a)
        else:
            cats.add(cat)
    tiene_liq = "liquidacion" in cats
    tiene_ind = "boletas" in cats or "imp_renta" in cats
    tipo_evidencia = ("mixto" if (tiene_liq and tiene_ind)
                      else "independiente" if tiene_ind
                      else "dependiente" if tiene_liq else "")
    exento, institucion = False, ""
    revisadas = 0
    for a in archivos:
        if revisadas >= 2 or exento:
            break
        if fsvc.cat_de_archivo(a["nombre"], a["subfolder"]) != "liquidacion":
            continue
        revisadas += 1
        try:
            p = base / a["ruta"]
            texto, _m = ocr_service.extraer_texto(p.read_bytes(), a["nombre"], force_ocr=False)
            m = RX_EXENTAS.search(texto or "")
            if not m and RX_LICENCIA.search(texto or ""):
                licencia = True
            if m:
                exento, institucion = True, m.group(0).title()
        except Exception as e:
            logging.warning(f"clasificador OCR liquidación {a['nombre']}: {e}")
    cod_tipo = ""
    if cod_files:
        c_liq = any(RX_LIQ.search(a["nombre"]) for a in cod_files)
        c_ind = any(RX_BOLETA.search(a["nombre"]) or "renta" in a["nombre"].lower() for a in cod_files)
        cod_tipo = "mixto" if (c_liq and c_ind) else "independiente" if c_ind else "dependiente" if c_liq else "sin documentos"
    return {"tipo_evidencia": tipo_evidencia, "exento_afp": exento, "institucion": institucion,
            "licencia_medica": licencia, "tiene_codeudor_docs": bool(cod_files),
            "codeudor_tipo": cod_tipo, "cats": sorted(cats)}


async def auditar_folder(doc, aplicar=True):
    """Compara la clasificación guardada vs la evidencia documental y corrige si aplica."""
    an = await asyncio.to_thread(analizar_archivos_sync, doc.get("nombre", ""))
    cr = doc.get("credit_request") or {}
    actual = (cr.get("client_type") or "dependiente").lower()
    cambios, hallazgos = {}, []
    if an["tipo_evidencia"] and an["tipo_evidencia"] != actual:
        hallazgos.append(f"tipo '{actual}' → '{an['tipo_evidencia']}' (evidencia documental)")
        cambios["credit_request.client_type"] = an["tipo_evidencia"]
    if an["exento_afp"] and not cr.get("exento_afp"):
        hallazgos.append(f"exención AFP detectada: {an['institucion']}")
        cambios["credit_request.exento_afp"] = True
        cambios["credit_request.exento_afp_institucion"] = an["institucion"]
    if an["licencia_medica"] and not cr.get("licencia_medica"):
        hallazgos.append("licencia médica registrada (no bloquea el proceso)")
        cambios["credit_request.licencia_medica"] = True
    if an["codeudor_tipo"] and an["codeudor_tipo"] != "sin documentos" and cr.get("codeudor_tipo") != an["codeudor_tipo"]:
        hallazgos.append(f"codeudor clasificado como '{an['codeudor_tipo']}'")
        cambios["credit_request.codeudor_tipo"] = an["codeudor_tipo"]
    if aplicar and cambios:
        await db.folders.update_one({"id": doc["id"]}, {
            "$set": cambios,
            "$push": {"historial": {"fecha": _now(), "accion": (
                "🧠 Clasificador documental: " + " · ".join(hallazgos))}}})
    return {"nombre": doc.get("nombre", ""), "tipo_guardado": actual, "analisis": an,
            "hallazgos": hallazgos, "corregido": bool(cambios)}


async def barrido_6_meses(aplicar=True):
    """Revisa todas las solicitudes de los últimos 6 meses, afina patrones y genera el informe."""
    desde = (datetime.now(timezone.utc) - timedelta(days=183)).isoformat()
    folders = await db.folders.find(
        {"$or": [{"created_at": {"$gte": desde}}, {"created_at": {"$exists": False}}]}
    ).sort("created_at", -1).to_list(400)
    resultados, corregidos = [], 0
    stats = {"dependiente": 0, "independiente": 0, "mixto": 0, "sin_evidencia": 0,
             "exentos_afp": 0, "licencias": 0, "codeudores": 0}
    for f in folders:
        try:
            r = await auditar_folder(f, aplicar=aplicar)
        except Exception as e:
            logging.warning(f"barrido {f.get('nombre')}: {e}")
            continue
        an = r["analisis"]
        stats[an["tipo_evidencia"] or "sin_evidencia"] = stats.get(an["tipo_evidencia"] or "sin_evidencia", 0) + 1
        if an["exento_afp"]:
            stats["exentos_afp"] += 1
        if an["licencia_medica"]:
            stats["licencias"] += 1
        if an["tiene_codeudor_docs"]:
            stats["codeudores"] += 1
        if r["corregido"]:
            corregidos += 1
            resultados.append(r)
    await db.dashai_eventos.insert_one({
        "tipo": "clasificador_barrido", "fecha": _now(), "carpetas": len(folders),
        "corregidas": corregidos, "stats": stats})
    return {"carpetas_revisadas": len(folders), "corregidas": corregidos,
            "stats": stats, "correcciones": resultados}
