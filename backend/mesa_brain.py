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
