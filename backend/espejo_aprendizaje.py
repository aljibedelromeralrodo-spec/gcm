"""🪞 ALGORITMO ESPEJO — CAPA 1 (aprobaciones@centralmutuos.cl).
Aprende los criterios de mesa desde los datos ya espejados (simulaciones,
resultados de mesa en carpetas y correos a mesa) y predice la probabilidad
de aprobación de cada carpeta con sus factores de mayor peso.
DISEÑO MODULAR POR CAPAS: cada caso de aprendizaje lleva `origen`
("capa1_simulaciones", "capa1_mesa", "capa2_mbox"). Cuando lleguen los
13.000 correos históricos (.mbox de Daniela Galindo) solo se insertan casos
con origen capa2 y se re-entrena: NADA de la capa 1 se reescribe."""
import asyncio
import logging
import math
import re
import uuid
from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from database import db

espia = APIRouter()
ROLES_VER = ("admin", "maestro", "administracion", "gerencia", "contralor", "broker", "postventa")


def _exigir(request, roles=ROLES_VER):
    c = getattr(request.state, "user", {}) or {}
    if c.get("rol") not in roles:
        raise HTTPException(status_code=403, detail="Su rol no tiene acceso a esta función")
    return c


def _now():
    return datetime.now(timezone.utc).isoformat()


def _rut8(r):
    return re.sub(r"[^0-9kK]", "", r or "").lower()[:8]


# ── Extracción de rasgos (compartida por todas las capas) ──
def _bucket_monto(uf):
    if not uf:
        return None
    return "monto<1500UF" if uf < 1500 else "monto1500-3000UF" if uf < 3000 \
        else "monto3000-5000UF" if uf < 5000 else "monto>5000UF"


def _bucket_plazo(a):
    if not a:
        return None
    return "plazo<=15a" if a <= 15 else "plazo16-25a" if a <= 25 else "plazo>25a"


def _bucket_ltv(v):
    if v is None:
        return None
    return "ltv<=70" if v <= 70 else "ltv71-80" if v <= 80 else "ltv>80"


def _bucket_carga(v):
    if v is None:
        return None
    return "carga<=25%" if v <= 25 else "carga26-35%" if v <= 35 else "carga>35%"


def _features_sim(s):
    fts = [_bucket_monto(s.get("credito_solicitado_uf") or s.get("credito_maximo_uf")),
           _bucket_plazo(s.get("plazo_anos")),
           _bucket_ltv(s.get("ltv")),
           _bucket_carga(s.get("carga_fin_conjunta") or s.get("carga_fin_individual")),
           "con_codeudor" if s.get("tiene_codeudor") else "sin_codeudor"]
    return [f for f in fts if f]


def _features_folder(f, criterios):
    fts = []
    for c in criterios:
        n = c.get("nombre") or ""
        if n in ("Enviada a mesa", "Datos financieros completos"):
            continue
        fts.append(("doc_ok:" if c.get("ok") else "doc_falta:") + n)
    return fts


ETIQUETAS = {"monto<1500UF": "Monto solicitado bajo 1.500 UF", "monto1500-3000UF": "Monto entre 1.500 y 3.000 UF",
             "monto3000-5000UF": "Monto entre 3.000 y 5.000 UF", "monto>5000UF": "Monto sobre 5.000 UF",
             "plazo<=15a": "Plazo hasta 15 años", "plazo16-25a": "Plazo 16 a 25 años", "plazo>25a": "Plazo sobre 25 años",
             "ltv<=70": "Financiamiento ≤70% (LTV)", "ltv71-80": "Financiamiento 71–80% (LTV)", "ltv>80": "Financiamiento >80% (LTV)",
             "carga<=25%": "Carga financiera ≤25%", "carga26-35%": "Carga financiera 26–35%", "carga>35%": "Carga financiera >35%",
             "con_codeudor": "Con codeudor", "sin_codeudor": "Sin codeudor"}


def _etiqueta(f):
    if f.startswith("doc_ok:"):
        return f"Documento presente: {f[7:]}"
    if f.startswith("doc_falta:"):
        return f"Documento faltante: {f[10:]}"
    return ETIQUETAS.get(f, f)


# ── Construcción de casos CAPA 1 ──
async def _reconstruir_casos_capa1():
    await db.espejo_casos.delete_many({"origen": {"$regex": "^capa1"}})
    casos = []
    async for s in db.simulaciones.find({"precalificacion_aprobada": {"$in": [True, False]}}).limit(2000):
        casos.append({"id": str(uuid.uuid4()), "origen": "capa1_simulaciones",
                      "fecha_caso": s.get("timestamp") or _now(),
                      "resultado": "aprobado" if s.get("precalificacion_aprobada") else "reprobado",
                      "features": _features_sim(s),
                      "razones": [r for r in (s.get("razones_rechazo") or []) if r][:6],
                      "rut": _rut8(s.get("rut"))})
    from server import _criterios_folder
    sims_por_rut = {}
    async for s in db.simulaciones.find({}).sort("timestamp", -1).limit(1000):
        sims_por_rut.setdefault(_rut8(s.get("rut")), s)
    async for f in db.folders.find({"resultado_mesa": {"$in": ["aprobado", "reprobado"]}}).limit(2000):
        try:
            crit = _criterios_folder(f)
        except Exception:
            crit = []
        fts = _features_folder(f, crit)
        sim = sims_por_rut.get(_rut8(f.get("rut")))
        if sim:
            fts += _features_sim(sim)
        casos.append({"id": str(uuid.uuid4()), "origen": "capa1_mesa",
                      "fecha_caso": f.get("resultado_mesa_at") or f.get("updated_at") or _now(),
                      "resultado": f.get("resultado_mesa"), "features": sorted(set(fts)),
                      "razones": [], "rut": _rut8(f.get("rut"))})
    if casos:
        await db.espejo_casos.insert_many(casos)
    return len(casos)


# ── Entrenamiento (lee TODAS las capas presentes en espejo_casos) ──
async def entrenar():
    n_capa1 = await _reconstruir_casos_capa1()
    casos = await db.espejo_casos.find({}, {"_id": 0}).to_list(20000)
    n = len(casos)
    aprob = [c for c in casos if c["resultado"] == "aprobado"]
    n_a = len(aprob)
    base = (n_a + 1) / (n + 2)                       # suavizado de Laplace
    base_logit = math.log(base / (1 - base))
    conteo_f, conteo_fa = Counter(), Counter()
    for c in casos:
        for f in set(c.get("features") or []):
            conteo_f[f] += 1
            if c["resultado"] == "aprobado":
                conteo_fa[f] += 1
    pesos = {}
    for f, nf in conteo_f.items():
        p = (conteo_fa[f] + 1) / (nf + 2)
        peso = max(-1.8, min(1.8, math.log(p / (1 - p)) - base_logit))
        pesos[f] = round(peso, 3)
    razones = Counter()
    for c in casos:
        for r in c.get("razones") or []:
            razones[r.strip()[:90]] += 1
    razones_top = [{"razon": r, "casos": k} for r, k in razones.most_common(10)]
    origen_stats = Counter(c["origen"] for c in casos)
    # Registro de EVOLUCIÓN: qué aprendió de nuevo esta versión
    prev = await db.espejo_modelo.find_one({}, sort=[("version", -1)]) or {}
    nuevos_f = sorted(set(pesos) - set(prev.get("pesos") or {}))
    nuevas_r = [r["razon"] for r in razones_top if r["razon"] not in
                {x["razon"] for x in (prev.get("razones_top") or [])}]
    aprendizajes = ([f"Nuevo patrón aprendido: {_etiqueta(f)} (peso {pesos[f]:+.2f})" for f in nuevos_f[:8]]
                    + [f"Nuevo criterio de rechazo de mesa: {r}" for r in nuevas_r[:6]])
    if not prev:
        aprendizajes.insert(0, f"Capa 1 del Algoritmo Espejo inicializada con {n} casos de aprobaciones@centralmutuos.cl")
    if n != prev.get("n_casos"):
        aprendizajes.append(f"Base de casos: {prev.get('n_casos') or 0} → {n}")
    version = int(prev.get("version") or 0) + 1
    doc = {"version": version, "fecha": _now(), "n_casos": n, "n_aprobados": n_a,
           "n_capa1": n_capa1, "origenes": dict(origen_stats),
           "tasa_base": round(base, 4), "base_logit": round(base_logit, 4),
           "pesos": pesos, "razones_top": razones_top, "aprendizajes": aprendizajes}
    await db.espejo_modelo.insert_one(dict(doc))
    logging.info(f"🪞 Espejo capa 1 entrenado: v{version} · {n} casos · {len(pesos)} patrones")
    return doc


async def _modelo_actual():
    return await db.espejo_modelo.find_one({}, {"_id": 0}, sort=[("version", -1)])


# ── Predicción por carpeta ──
async def predecir_folder(f):
    m = await _modelo_actual()
    if not m:
        m = await entrenar()
        m.pop("_id", None)
    from server import _criterios_folder
    try:
        crit = _criterios_folder(f)
    except Exception:
        crit = []
    fts = _features_folder(f, crit)
    sim = await db.simulaciones.find_one({"rut": {"$regex": _rut8(f.get("rut")) or "^$", "$options": "i"}},
                                         sort=[("timestamp", -1)]) if f.get("rut") else None
    if not sim and f.get("nombre"):
        sim = await db.simulaciones.find_one({"nombre_completo": {"$regex": re.escape(f["nombre"][:18]), "$options": "i"}},
                                             sort=[("timestamp", -1)])
    if sim:
        fts += _features_sim(sim)
    fts = sorted(set(fts))
    pesos = m.get("pesos") or {}
    logit = m.get("base_logit") or 0
    factores = []
    for ft in fts:
        w = pesos.get(ft)
        if w is None:
            continue
        logit += w
        factores.append({"factor": _etiqueta(ft), "peso": w,
                         "direccion": "a favor" if w > 0 else "en contra" if w < 0 else "neutro"})
    prob = 1 / (1 + math.exp(-logit))
    nivel = "alta" if prob >= 0.65 else "media" if prob >= 0.40 else "baja"
    factores.sort(key=lambda x: -abs(x["peso"]))
    return {"probabilidad": round(prob * 100, 1), "nivel": nivel,
            "factores": factores[:6], "resultado_real": f.get("resultado_mesa"),
            "modelo_version": m.get("version"), "modelo_fecha": m.get("fecha"),
            "casos_aprendidos": m.get("n_casos"), "capas": m.get("origenes") or {}}


# ── Loop: re-entrena cuando cambia la base de datos espejada ──
async def espejo_aprendizaje_loop():
    await asyncio.sleep(120)
    while True:
        try:
            n_sim = await db.simulaciones.count_documents({"precalificacion_aprobada": {"$in": [True, False]}})
            n_mesa = await db.folders.count_documents({"resultado_mesa": {"$in": ["aprobado", "reprobado"]}})
            m = await _modelo_actual()
            firma = f"{n_sim}|{n_mesa}"
            if not m or m.get("firma_datos") != firma:
                doc = await entrenar()
                await db.espejo_modelo.update_one({"version": doc["version"]}, {"$set": {"firma_datos": firma}})
        except Exception as e:
            logging.warning(f"espejo_aprendizaje_loop: {e}")
        await asyncio.sleep(6 * 3600)


# ── Endpoints ──
@espia.get("/espejo-ia/prediccion/{fid}")
async def espejo_prediccion(fid: str, request: Request):
    _exigir(request)
    f = await db.folders.find_one({"id": fid})
    if not f:
        raise HTTPException(status_code=404, detail="Carpeta no encontrada")
    return await predecir_folder(f)


@espia.get("/espejo-ia/modelo")
async def espejo_modelo(request: Request):
    _exigir(request, ("admin", "maestro"))
    m = await _modelo_actual()
    return m or {"version": 0, "n_casos": 0, "pesos": {}, "aprendizajes": []}


@espia.get("/espejo-ia/evolucion")
async def espejo_evolucion(request: Request):
    _exigir(request, ("admin", "maestro"))
    vs = await db.espejo_modelo.find({}, {"_id": 0, "pesos": 0}).sort("version", -1).limit(50).to_list(50)
    return {"versiones": vs, "total": len(vs)}


@espia.post("/espejo-ia/entrenar")
async def espejo_entrenar(request: Request):
    _exigir(request, ("admin", "maestro"))
    doc = await entrenar()
    doc.pop("_id", None)
    return doc
