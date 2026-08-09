"""Cerebro Predictivo DashAI — 100% local, sin créditos de nube.
Minería del historial real de la MESA (aprobaciones@centralmutuos.cl) y
recalibración automática en segundo plano (aprendizaje continuo)."""
import os
import re
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

VENTANA_DIAS = 180
_cli = None


def _db():
    global _cli
    if _cli is None:
        _cli = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    return _cli


def _analisis_60(db, base180):
    """FOCO 60 DÍAS: cruza aprobaciones/rechazos recientes con el reglamento BTG/Ameris.
    Detecta si la MESA está más laxa o estricta que el papel → Ajustes de Mercado."""
    desde60 = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    q60 = {"fecha": {"$gte": desde60}}
    apro = list(db.seguimiento.find({"estado": {"$in": ["aprobacion", "aprobado"]}, **q60},
                                    {"cliente": 1}))
    rech = list(db.seguimiento.find({"estado": {"$in": ["rechazo", "rechazado"]}, **q60},
                                    {"cliente": 1, "asunto": 1}))
    total = len(apro) + len(rech)
    base60 = (len(apro) / total) if total else base180
    crit = db.config.find_one({"_key": "criterios"}) or {}
    btg = (crit.get("btg_pactual") or {}).get("sin_subsidio") or {}
    ltv_max = float(btg.get("ltv_max") or 0.9)
    div_max = float(btg.get("div_renta_max") or btg.get("div_renta_max_sin_codeudor") or 0.30)
    ajustes = []
    ltv_sobre, div_sobre = [], []
    for s in apro:
        cli = (s.get("cliente") or "").strip()[:20]
        if not cli:
            continue
        sim = db.simulaciones.find_one(
            {"nombre_completo": {"$regex": re.escape(cli), "$options": "i"}},
            sort=[("timestamp", -1)])
        if not sim:
            continue
        ltv = float(sim.get("ltv") or 0)
        divr = float(sim.get("div_renta_individual") or 0)
        if ltv > ltv_max:
            ltv_sobre.append(ltv)
        if divr > div_max:
            div_sobre.append(divr)
    if ltv_sobre:
        ajustes.append(f"MESA más laxa en LTV: aprobó hasta {round(max(ltv_sobre)*100)}% "
                       f"(papel: {round(ltv_max*100)}%) → Ajuste de Mercado sugerido: "
                       f"ltv_max {round(max(ltv_sobre), 2)}")
    if div_sobre:
        ajustes.append(f"MESA más laxa en Dividendo/Renta: aprobó hasta {round(max(div_sobre)*100, 1)}% "
                       f"(papel: {round(div_max*100)}%) → Ajuste de Mercado sugerido: "
                       f"div_renta_max {round(max(div_sobre), 2)}")
    if base60 < base180 - 0.08:
        ajustes.append(f"MESA más estricta que el histórico: tasa 60d {round(base60*100)}% vs "
                       f"180d {round(base180*100)}% → revisar carpetas límite antes de enviar")
    # Tendencia: qué criterio pesa más en los rechazos recientes
    CATS = {"carga financiera": r"carga\s*financiera|endeuda", "renta mínima": r"renta",
            "LTV/financiamiento": r"ltv|financiamiento|pie", "antigüedad laboral": r"antig|laboral",
            "monto del crédito": r"monto|2\.?000\s*UF"}
    cuenta = {k: 0 for k in CATS}
    textos = [a for s in rech for a in [(s.get("asunto") or "")]]
    for sim in db.simulaciones.find({"razones_rechazo": {"$ne": []},
                                     "timestamp": {"$gte": desde60}}, {"razones_rechazo": 1}):
        textos.extend(sim.get("razones_rechazo", []))
    for t in textos:
        for k, rx in CATS.items():
            if re.search(rx, t, re.I):
                cuenta[k] += 1
    top = sorted(cuenta.items(), key=lambda kv: -kv[1])
    if top and top[0][1] > 0:
        segundo = top[1][0] if len(top) > 1 and top[1][1] > 0 else "los demás criterios"
        tendencia = (f"Tendencia últimos 60 días: La MESA está priorizando {top[0][0]} "
                     f"sobre {segundo} ({top[0][1]} casos analizados).")
    else:
        tendencia = ("Tendencia últimos 60 días: La MESA mantiene consistencia con el "
                     "reglamento BTG/Ameris — sin desviaciones detectadas.")
    return {"base": round(base60, 4), "aprobadas": len(apro), "rechazadas": len(rech),
            "ajustes_mercado": ajustes, "tendencia": tendencia}


def calibrar():
    """Minería local de 180 días: patrones de éxito y motivos de rechazo de la MESA."""
    db = _db()
    desde = (datetime.now(timezone.utc) - timedelta(days=VENTANA_DIAS)).isoformat()
    q_fecha = {"fecha": {"$gte": desde}}
    apro = db.seguimiento.count_documents({"estado": {"$in": ["aprobacion", "aprobado"]}, **q_fecha})
    rech = db.seguimiento.count_documents({"estado": {"$in": ["rechazo", "rechazado"]}, **q_fecha})
    total = apro + rech
    base = (apro / total) if total else 0.85
    motivos = {}
    for s in db.simulaciones.find({"razones_rechazo": {"$exists": True, "$ne": []}},
                                  {"razones_rechazo": 1}):
        for r0 in s.get("razones_rechazo", []):
            clave = re.sub(r"[\d.,%]+", "X", r0).strip()
            motivos[clave] = motivos.get(clave, 0) + 1
    for s in db.seguimiento.find({"estado": {"$in": ["rechazo", "rechazado"]}, **q_fecha},
                                 {"asunto": 1}):
        m = re.search(r"rechaz\w*\s*[:\-—]\s*(.{5,80})", s.get("asunto") or "", re.I)
        if m:
            k = m.group(1).strip()
            motivos[k] = motivos.get(k, 0) + 1
    top = sorted(motivos.items(), key=lambda kv: -kv[1])[:8]
    modelo = {"_key": "mesa_brain_modelo", "ventana_dias": VENTANA_DIAS,
              "base": round(base, 4), "aprobadas": apro, "rechazadas": rech,
              "muestras": total,
              "motivos_rechazo": [{"motivo": k, "casos": v} for k, v in top],
              "calibrado_en": datetime.now(timezone.utc).isoformat()}
    # CALIBRACIÓN PRIORITARIA: ventana de 60 días = Regla de Oro del Contralor
    modelo["ventana_60"] = _analisis_60(db, base)
    modelo["tendencia"] = modelo["ventana_60"]["tendencia"]
    modelo["ajustes_mercado"] = modelo["ventana_60"]["ajustes_mercado"]
    db.config.replace_one({"_key": "mesa_brain_modelo"}, modelo, upsert=True)
    return modelo


def modelo_actual(max_age_horas=24):
    """Modelo vigente; recalibra solo si venció (MODO APRENDIZAJE CONTINUO, costo cero)."""
    m = _db().config.find_one({"_key": "mesa_brain_modelo"}, {"_id": 0})
    if m:
        try:
            edad = datetime.now(timezone.utc) - datetime.fromisoformat(m["calibrado_en"])
            if edad.total_seconds() < max_age_horas * 3600:
                return m
        except Exception:
            return m
    return calibrar()
