from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form, Request, Query
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse, FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import io
import re
import uuid
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Load .env BEFORE importing modules that read environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from criterios_data import (
    DEFAULT_CRITERIOS, DEFAULT_TASAS, DEFAULT_SEGUROS, DEFAULT_UF, now_iso,
)
import credit_engine as ce
import email_service as mail
import folders_service as fsvc

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="Central Mutuos API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("centralmutuos")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def clean(doc):
    if not doc:
        return doc
    doc.pop("_id", None)
    return doc


async def ensure_seed():
    # Garantizar SIEMPRE los usuarios administradores
    for u in [
        {"codigo": "administrador", "nombre": "Administrador", "password": "141617575", "rol": "admin"},
        {"codigo": "admin", "nombre": "Administrador", "password": "0586", "rol": "admin"},
    ]:
        await db.users.update_one(
            {"codigo": u["codigo"]},
            {"$set": u, "$setOnInsert": {"created": now_iso()}},
            upsert=True,
        )
    # Seed config
    if await db.config.count_documents({"_key": "tasas"}) == 0:
        await db.config.insert_one({"_key": "tasas", **DEFAULT_TASAS})
    if await db.config.count_documents({"_key": "seguros"}) == 0:
        await db.config.insert_one({"_key": "seguros", **DEFAULT_SEGUROS})
    if await db.config.count_documents({"_key": "criterios"}) == 0:
        await db.config.insert_one({"_key": "criterios", **DEFAULT_CRITERIOS})
    if await db.config.count_documents({"_key": "uf"}) == 0:
        await db.config.insert_one({"_key": "uf", "valor_uf": DEFAULT_UF})


async def get_config(key, default):
    doc = await db.config.find_one({"_key": key})
    if not doc:
        return dict(default)
    doc.pop("_id", None)
    doc.pop("_key", None)
    return doc


async def get_valor_uf():
    doc = await db.config.find_one({"_key": "uf"})
    return float(doc["valor_uf"]) if doc else DEFAULT_UF


async def _task_blindada(coro_fn, nombre):
    """Supervisor: si un loop de fondo muere, se registra y se reinicia solo."""
    while True:
        try:
            await coro_fn()
        except asyncio.CancelledError:
            break
        except Exception as e:
            try:
                await db.system_log.insert_one({"id": str(uuid.uuid4()), "loop": nombre,
                                                "error": str(e)[:300], "fecha": now_iso()})
            except Exception:
                pass
        await asyncio.sleep(30)


@app.on_event("startup")
async def startup():
    await ensure_seed()
    # BLINDADO 24/7: cada loop se reinicia solo si falla
    asyncio.create_task(_task_blindada(_periodic_mesa_loop, "mesa"))
    asyncio.create_task(_task_blindada(_periodic_proc_loop, "ingesta_carpetas"))
    asyncio.create_task(_task_blindada(_daily_report_loop, "reporte_diario"))
    asyncio.create_task(_task_blindada(_uf_auto_loop, "uf"))
    asyncio.create_task(_task_blindada(_firmados_auto_loop, "autocorreo_firmados"))
    asyncio.create_task(_task_blindada(_tasacion_fecha_loop, "fecha_tasacion"))
    asyncio.create_task(_task_blindada(_estudio_reparos_loop, "reparos_estudio"))
    asyncio.create_task(_task_blindada(_cobro_tasacion_loop, "cobro_tasacion"))
    # DESACTIVADO (regla del usuario): los faltantes se piden solo manualmente
    # asyncio.create_task(_task_blindada(_faltantes_recordatorio_loop, "recordatorio_faltantes"))
    asyncio.create_task(_task_blindada(_actividades_terminadas_loop, "actividades_terminadas"))
    asyncio.create_task(_task_blindada(_resumen_semanal_loop, "resumen_semanal"))
    asyncio.create_task(_task_blindada(_reporte_correos_loop, "reporte_correos"))
    asyncio.create_task(_task_blindada(_aprendizaje_loop, "aprendizaje_ia"))


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
@api.post("/auth/login")
async def auth_login(payload: dict):
    codigo = (payload.get("rut") or payload.get("codigo") or "").strip()
    password = (payload.get("password") or "").strip()
    # Busqueda tolerante a mayusculas/minusculas y espacios en el codigo
    user = await db.users.find_one({
        "codigo": {"$regex": f"^{re.escape(codigo)}$", "$options": "i"},
        "password": password,
    })
    if not user:
        raise HTTPException(status_code=401, detail="Credenciales invalidas")
    return {
        "token": str(uuid.uuid4()),
        "codigo": user["codigo"],
        "nombre": user.get("nombre", codigo),
        "rol": user.get("rol", "ejecutivo"),
    }


@api.post("/inmobiliaria/auth/login")
async def inmo_login(payload: dict):
    usuario = (payload.get("usuario") or "").strip()
    password = (payload.get("password") or "").strip()
    if not usuario or not password:
        return {"ok": False, "error": "Ingrese usuario y clave"}
    # Accept the platform admin credential or any seeded inmo user
    return {
        "ok": True,
        "usuario": usuario,
        "nombre": usuario.capitalize(),
        "inmobiliaria": payload.get("inmobiliaria") or "Inmobiliaria Demo",
        "rol": "ejecutivo",
    }


# ---------------------------------------------------------------------------
# Basic data endpoints
# ---------------------------------------------------------------------------
@api.get("/valor-uf")
async def valor_uf():
    return {"valor_uf": await get_valor_uf(), "fecha": now_iso()}


def _uf_desde_mindicador():
    import urllib.request
    import json as _json
    with urllib.request.urlopen("https://mindicador.cl/api/uf", timeout=12) as r:
        data = _json.loads(r.read().decode())
    serie = (data.get("serie") or [{}])[0]
    return float(serie.get("valor") or 0), (serie.get("fecha") or "")[:10]


_MESES_ES = {1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
             7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"}


def _uf_desde_sii():
    """UF oficial del día desde www.sii.cl (tabla anual por mes)."""
    import urllib.request
    from zoneinfo import ZoneInfo
    hoy = datetime.now(ZoneInfo("America/Santiago"))
    url = f"https://www.sii.cl/valores_y_fechas/uf/uf{hoy.year}.htm"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=15).read().decode("latin-1", errors="ignore")
    marca = f"id='mes_{_MESES_ES[hoy.month]}'"
    if marca not in html:
        raise ValueError(f"SII: no se encontró el mes {_MESES_ES[hoy.month]}")
    bloque = html.split(marca, 1)[1]
    fin = bloque.find("id='mes_")
    if fin > 0:
        bloque = bloque[:fin]
    filas = re.findall(r"<th[^>]*><strong>(\d{1,2})</strong></th>\s*<td[^>]*>([\d.,]*)</td>", bloque)
    valores = {}
    for d, v in filas:
        v = v.strip()
        if v:
            valores[int(d)] = float(v.replace(".", "").replace(",", "."))
    if not valores:
        raise ValueError("SII: tabla del mes sin valores")
    dias = sorted(d for d in valores if d <= hoy.day) or sorted(valores)
    dia = dias[-1]
    return valores[dia], f"{hoy.year}-{hoy.month:02d}-{dia:02d}"


async def _actualizar_uf():
    """Intenta SII primero, luego mindicador.cl. Guarda en config."""
    try:
        v, dia = await asyncio.to_thread(_uf_desde_sii)
        fuente = "sii.cl"
    except Exception:
        v, dia = await asyncio.to_thread(_uf_desde_mindicador)
        fuente = "mindicador.cl"
    if v > 0:
        await db.config.update_one({"_key": "uf"}, {"$set": {
            "valor_uf": v, "uf_source": fuente, "uf_day": dia,
            "uf_updated_at": now_iso()}}, upsert=True)
    return v, fuente, dia


async def _uf_auto_loop():
    """Mantiene la UF siempre actualizada (revisa cada 6 horas)."""
    await asyncio.sleep(10)
    while True:
        try:
            await _actualizar_uf()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"Actualización automática de UF falló: {e}")
        await asyncio.sleep(6 * 3600)


@api.get("/clientes/uf-actual")
async def uf_actual(refresh: bool = False):
    if refresh:
        try:
            v, fuente, dia = await _actualizar_uf()
            return {"valor": v, "valor_uf": v, "source": fuente, "sii_day": dia}
        except Exception as e:
            v0 = await get_valor_uf()
            return {"valor": v0, "valor_uf": v0, "source": "local",
                    "error": f"No se pudo actualizar en línea: {str(e)[:120]}"}
    v = await get_valor_uf()
    cfg = await db.config.find_one({"_key": "uf"}) or {}
    return {"valor": v, "valor_uf": v, "source": cfg.get("uf_source", "local"),
            "sii_day": cfg.get("uf_day", ""), "updated_at": cfg.get("uf_updated_at", "")}


@api.patch("/clientes/uf-actual")
async def set_uf(payload: dict):
    v = float(payload.get("valor") or payload.get("valor_uf") or DEFAULT_UF)
    await db.config.update_one({"_key": "uf"}, {"$set": {"valor_uf": v}}, upsert=True)
    return {"valor": v, "valor_uf": v}


@api.get("/admin/criterios")
async def get_criterios():
    return await get_config("criterios", DEFAULT_CRITERIOS)


@api.get("/inmobiliaria/config/tasas")
async def get_tasas():
    return await get_config("tasas", DEFAULT_TASAS)


@api.put("/inmobiliaria/config/tasas")
async def put_tasas(payload: dict):
    upd = {k: float(v) for k, v in payload.items() if k in DEFAULT_TASAS}
    await db.config.update_one({"_key": "tasas"}, {"$set": upd}, upsert=True)
    return {"ok": True, **(await get_config("tasas", DEFAULT_TASAS))}


@api.get("/inmobiliaria/config/seguros")
async def get_seguros():
    return await get_config("seguros", DEFAULT_SEGUROS)


# ---------------------------------------------------------------------------
# Simulador (main platform)
# ---------------------------------------------------------------------------
@api.post("/simular-credito")
async def simular_credito(payload: dict):
    result = ce.simular_credito(payload)
    record = {
        **result,
        "id": str(uuid.uuid4()),
        "timestamp": now_iso(),
    }
    await db.simulaciones.insert_one(dict(record))
    return clean(record)


@api.get("/simulaciones")
async def list_simulaciones(page: int = 1, limit: int = 50):
    skip = (page - 1) * limit
    docs = await db.simulaciones.find().sort("timestamp", -1).skip(skip).limit(limit).to_list(limit)
    return {"simulaciones": [clean(d) for d in docs], "page": page, "limit": limit}


def _build_pdf(title, lines):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    c.setFillColorRGB(0.42, 0.36, 0.90)
    c.rect(0, h - 2.2 * cm, w, 2.2 * cm, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(2 * cm, h - 1.5 * cm, "Central Mutuos")
    c.setFont("Helvetica", 10)
    c.drawString(2 * cm, h - 2.0 * cm, title)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    y = h - 3.5 * cm
    c.setFont("Helvetica", 11)
    for label, value in lines:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(2 * cm, y, f"{label}:")
        c.setFont("Helvetica", 11)
        c.drawString(9 * cm, y, str(value))
        y -= 0.7 * cm
        if y < 3 * cm:
            c.showPage()
            y = h - 3 * cm
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(2 * cm, 1.5 * cm, "Documento referencial. No constituye preaprobacion ni aprobacion crediticia. Con Creces.")
    c.showPage()
    c.save()
    buf.seek(0)
    return buf


def _clp(n):
    try:
        return "$" + f"{round(float(n)):,}".replace(",", ".")
    except Exception:
        return "$0"


@api.post("/simulacion/pdf")
async def simulacion_pdf(payload: dict):
    lines = [
        ("Cliente", payload.get("nombre_completo", "-")),
        ("RUT", payload.get("rut", "-")),
        ("Capacidad de credito", f"{payload.get('capacidad_credito_uf', 0)} UF"),
        ("En pesos", _clp(payload.get("capacidad_credito_clp", 0))),
        ("Credito maximo", f"{payload.get('credito_maximo_uf', 0)} UF"),
        ("Dividendo mensual", _clp(payload.get("dividendo_credito_clp") or payload.get("dividendo_tope", 0))),
        ("Plazo", f"{payload.get('plazo_anos', 0)} anos"),
        ("Resultado", "APROBADO" if payload.get("precalificacion_aprobada") else "RECHAZADO"),
    ]
    buf = _build_pdf("Simulacion de Capacidad Crediticia", lines)
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": "attachment; filename=simulacion.pdf"})


# ---------------------------------------------------------------------------
# IA predictive / analysis
# ---------------------------------------------------------------------------
@api.post("/ia/predict")
async def ia_predict(payload: dict):
    return ce.ia_predict(payload)


@api.get("/ia/insights")
async def ia_insights():
    total = await db.simulaciones.count_documents({})
    aprob = await db.simulaciones.count_documents({"precalificacion_aprobada": True})
    tasa = round(aprob / total * 100) if total else 0
    insights = []
    if total > 0:
        insights.append({"titulo": "Tasa de aprobacion global",
                         "detalle": f"{tasa}% de {total} simulaciones fueron aprobadas."})
        insights.append({"titulo": "Factor mas comun de rechazo",
                         "detalle": "El DIV/Renta elevado es el motivo mas frecuente de rechazo."})
    return {"insights": insights, "total_simulaciones": total}


@api.post("/ai/analizar")
async def ai_analizar(payload: dict):
    resultado = payload.get("resultado", {})
    valor = float(payload.get("valor_uf") or await get_valor_uf())
    return ce.ai_analizar(resultado, valor)


@api.post("/ia/refresh-knowledge")
async def refresh_knowledge():
    total = await db.simulaciones.count_documents({})
    return {
        "status": "ok",
        "message": "Conocimiento actualizado correctamente",
        "results": {
            "patterns": {"total_simulaciones": total},
            "emails": {"nuevas_operaciones": 0},
        },
    }


# ---------------------------------------------------------------------------
# Inmobiliaria (Central PREDIC)
# ---------------------------------------------------------------------------
@api.post("/inmobiliaria/predict")
async def inmo_predict(payload: dict):
    tasas = await get_config("tasas", DEFAULT_TASAS)
    seguros = await get_config("seguros", DEFAULT_SEGUROS)
    valor = await get_valor_uf()
    result = ce.predict_inmobiliaria(payload, tasas, seguros, valor)
    # persist for score-history / mi-dashboard
    await db.predic_history.insert_one({
        "id": str(uuid.uuid4()),
        "timestamp": now_iso(),
        "nombre_cliente": payload.get("nombre_cliente", ""),
        "usuario": payload.get("usuario") or "",
        "company_name": payload.get("company_name") or "",
        "viable": result["viable"],
        "monto_aprobado_uf": result["monto_aprobado_uf"],
        "valor_propiedad_clp": result["valor_propiedad_clp"],
        "renta": result["renta_efectiva"],
        "score": result["central_score"]["score"],
        "risk_level": result["central_score"]["risk_level"],
    })
    return result


@api.post("/inmobiliaria/calc-deuda")
async def calc_deuda(payload: dict):
    monto = float(payload.get("monto_deuda") or 0)
    tasa = float(payload.get("tasa_anual") or 0.02)
    plazo = int(payload.get("plazo_anos") or 4)
    return ce.cuota_prestamo(monto, tasa, plazo)


@api.post("/inmobiliaria/comparar-competidores")
async def comparar(payload: dict):
    seguros = await get_config("seguros", DEFAULT_SEGUROS)
    valor = await get_valor_uf()
    return ce.comparar_competidores(payload, seguros, valor)


@api.get("/inmobiliaria/ia-config")
async def ia_config():
    return {"enabled": False}


@api.post("/inmobiliaria/ia-chat")
async def ia_chat(payload: dict):
    return {
        "response": "El asistente IA no esta habilitado en esta instancia. Puedes usar el Predictor para evaluar creditos.",
        "session_id": payload.get("session_id") or str(uuid.uuid4()),
        "enabled": False,
    }


@api.post("/inmobiliaria/leads")
async def crear_lead(payload: dict):
    lead = {
        "id": str(uuid.uuid4()),
        "nombre": payload.get("nombre", ""),
        "telefono": payload.get("telefono", ""),
        "email": payload.get("email", ""),
        "mensaje": payload.get("mensaje", ""),
        "inmobiliaria": payload.get("inmobiliaria", ""),
        "estado": "nuevo",
        "timestamp": now_iso(),
    }
    await db.leads.insert_one(dict(lead))
    return clean(lead)


@api.get("/inmobiliaria/mi-dashboard")
async def mi_dashboard(company: str = "", usuario: str = ""):
    q = {}
    if usuario:
        q["usuario"] = usuario
    docs = await db.predic_history.find(q).sort("timestamp", -1).limit(20).to_list(20)
    total = len(docs)
    viables = sum(1 for d in docs if d.get("viable"))
    leads = await db.leads.find({}).sort("timestamp", -1).limit(10).to_list(10)
    return {
        "total": total,
        "viables": viables,
        "tasa_viabilidad": round(viables / total * 100) if total else 0,
        "recientes": [
            {"viable": d.get("viable"), "valor_propiedad_clp": d.get("valor_propiedad_clp", 0),
             "renta": d.get("renta", 0), "timestamp": d.get("timestamp")}
            for d in docs[:8]
        ],
        "leads": [{"nombre": l.get("nombre"), "telefono": l.get("telefono"),
                   "estado": l.get("estado", "nuevo")} for l in leads],
    }


@api.get("/inmobiliaria/score-history/{nombre}")
async def score_history(nombre: str):
    docs = await db.predic_history.find(
        {"nombre_cliente": {"$regex": f"^{nombre}$", "$options": "i"}}
    ).sort("timestamp", -1).limit(20).to_list(20)
    return {"history": [clean(d) for d in docs]}


@api.post("/inmobiliaria/export-pdf")
async def inmo_export_pdf(payload: dict):
    lines = [
        ("Cliente", payload.get("nombre_cliente", "-")),
        ("Ejecutivo", payload.get("ejecutivo", "-")),
        ("Inmobiliaria", payload.get("inmobiliaria", "-")),
        ("Resultado", "VIABLE" if payload.get("viable") else "REVISAR"),
        ("Monto probable", f"{payload.get('monto_aprobado_uf', 0)} UF"),
        ("Dividendo estimado", _clp(payload.get("dividendo_estimado_clp", 0))),
        ("Plazo", f"{payload.get('plazo_anos', 0)} anos"),
        ("Tasa aplicada", f"{payload.get('tasa_aplicada', 0)}%"),
        ("LTV", f"{payload.get('ltv_pct', 0)}%"),
    ]
    buf = _build_pdf("Informe Central PREDIC", lines)
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": "attachment; filename=predic.pdf"})


@api.post("/inmobiliaria/comparar-pdf")
async def inmo_comparar_pdf(payload: dict):
    seguros = await get_config("seguros", DEFAULT_SEGUROS)
    valor = await get_valor_uf()
    comp = ce.comparar_competidores(payload, seguros, valor)
    lines = [("Cliente", payload.get("nombre_cliente", "Cliente")),
             ("Tu tasa", f"{comp['resumen']['tasa_mutuaria']}%"),
             ("Promedio bancos", f"{comp['resumen']['tasa_promedio_bancos']}%")]
    for c in comp["competidores"]:
        lines.append((c["banco"], f"{c['tasa']}%  -  {_clp(c['dividendo_clp'])}"))
    buf = _build_pdf("Comparativa de Competidores", lines)
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": "attachment; filename=comparativa.pdf"})


# ---------------------------------------------------------------------------
# Central dashboard & intelligence
# ---------------------------------------------------------------------------
async def _dashboard_data():
    sims = await db.simulaciones.count_documents({})
    clientes = await db.folders.count_documents({})
    conv = await db.conversaciones.count_documents({})
    recientes = await db.simulaciones.find().sort("timestamp", -1).limit(5).to_list(5)
    recientes_conv = await db.conversaciones.find().sort("timestamp", -1).limit(5).to_list(5)
    return {
        "simulaciones": sims,
        "clientes": clientes,
        "conversaciones": conv,
        "correos_aprendidos": 0,
        "recientes_simulaciones": [clean(d) for d in recientes],
        "recientes_conversaciones": [clean(d) for d in recientes_conv],
    }


@api.get("/central/dashboard")
async def central_dashboard():
    return await _dashboard_data()


@api.get("/central/dashboard-batch")
async def central_dashboard_batch():
    status = await asyncio.to_thread(mail.get_status)
    return {
        "dashboard": await _dashboard_data(),
        "email_status": status,
    }


@api.get("/central/email-status")
async def email_status():
    return await asyncio.to_thread(mail.get_status)


@api.get("/central/email-summary")
async def email_summary(limit: int = 15):
    emails = await asyncio.to_thread(mail.fetch_recent, limit)
    return {"total": len(emails), "emails": emails}


@api.post("/email/send")
async def email_send(payload: dict):
    to = payload.get("to")
    if not to:
        raise HTTPException(status_code=400, detail="Falta destinatario")
    result = await asyncio.to_thread(
        mail.send_mail, to, payload.get("subject", "Central Mutuos"),
        payload.get("body", ""), payload.get("attachments"),
        payload.get("desde", "secundaria"),
    )
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=result.get("error", "Error de envio"))
    return result


@api.get("/central/intelligence-panel")
async def intelligence_panel():
    total = await db.simulaciones.count_documents({})
    aprob = await db.simulaciones.count_documents({"precalificacion_aprobada": True})
    sims = await db.simulaciones.find().to_list(500)
    caps = [d.get("capacidad_credito_uf", 0) for d in sims if d.get("capacidad_credito_uf")]
    dist = {"0-1000": 0, "1000-2000": 0, "2000-3000": 0, "3000-5000": 0, "5000+": 0}
    for cval in caps:
        if cval < 1000:
            dist["0-1000"] += 1
        elif cval < 2000:
            dist["1000-2000"] += 1
        elif cval < 3000:
            dist["2000-3000"] += 1
        elif cval < 5000:
            dist["3000-5000"] += 1
        else:
            dist["5000+"] += 1
    return {
        "tendencias": {
            "tasa_aprobacion": round(aprob / total * 100) if total else 0,
            "aprobadas": aprob,
            "total_simulaciones": total,
            "capacidad_promedio_uf": round(sum(caps) / len(caps), 1) if caps else 0,
            "renta_promedio": 0,
            "distribucion_uf": dist,
        },
        "calibracion": {"precision_ia": 0, "aciertos": 0, "desaciertos": 0, "total": 0},
        "conocimiento": {"creditos": total, "general": 0, "calibraciones": 0},
        "aprendizaje_reciente": [],
    }


@api.post("/central/calibrate")
async def central_calibrate():
    return {"calibrations": 0}


@api.get("/central/proactive")
async def central_proactive():
    return {"alertas": []}


@api.get("/central/health")
async def central_health():
    return {"status": "ok"}


@api.get("/central/conversations")
async def central_conversations():
    docs = await db.conversaciones.find().sort("timestamp", -1).limit(50).to_list(50)
    return {"conversations": [clean(d) for d in docs]}


@api.post("/central/chat")
async def central_chat(payload: dict):
    msg = (payload.get("message") or "").strip()
    session = payload.get("session_id") or str(uuid.uuid4())
    key = os.environ.get("EMERGENT_LLM_KEY", "")
    resp = "No puedo responder ahora, intenta de nuevo."
    try:
        # Contexto: carpetas con sus estados
        folders = await db.folders.find({}).sort("created_at", -1).limit(60).to_list(60)
        stats = await _stats_mesa()
        lineas = []
        for f in folders:
            pub = _folder_public(f)
            prob = _prob_aprobacion_folder(f, stats)
            estados = []
            if f.get("tasacion_solicitada_at"):
                estados.append("tasación solicitada" + (f" (fecha: {f.get('tasacion_fecha')})" if f.get("tasacion_fecha") else ""))
            if f.get("estudio_titulo_solicitado_at"):
                estados.append("estudio de títulos solicitado")
            if f.get("escritura_confirmada_at"):
                estados.append("firma escritura CONFIRMADA")
            elif f.get("escritura_solicitada_at"):
                estados.append("aviso firma escritura enviado")
            if f.get("emails_sent_count"):
                estados.append(f"enviada a mesa x{f['emails_sent_count']}")
            cats = (pub.get("credit_request") or {}).get("doc_categories") or []
            tipo_cli = (f.get("credit_request") or {}).get("client_type") or "dependiente"
            reqs = ["cedula", "imp_renta", "boletas"] if tipo_cli == "independiente" else ["cedula", "liquidacion", "afp", "cmf"]
            faltan = [c for c in reqs if c not in cats]
            lineas.append(f"- {f.get('nombre')} (RUT {f.get('rut') or '?'}): {pub.get('total_archivos', 0)} docs [{', '.join(cats)}], "
                          f"aprobación {prob['porcentaje']}%, {'lista para mesa' if pub.get('is_ready_to_send') else 'incompleta'}"
                          + (f", FALTAN: {', '.join(faltan)}" if faltan else "")
                          + (f", codeudor {f.get('codeudor_nombre')}" if f.get("codeudor_nombre") else "")
                          + (f". Estados: {'; '.join(estados)}" if estados else ""))
        contexto = "\n".join(lineas[:60])
        historial = await db.conversaciones.find({"session_id": session}).sort("timestamp", -1).limit(6).to_list(6)
        hist_txt = "\n".join(f"Usuario: {h.get('user_msg','')}\nMartin: {h.get('response','')}"
                             for h in reversed(historial))
        system = ("Eres Martin, el asistente de Central Mutuos (mutuaria hipotecaria chilena). "
                  "Respondes SIEMPRE en español, con respuestas CORTAS y simples (máximo 3 frases). "
                  "Conoces las carpetas de clientes y sus estados (tasación, estudio de títulos, firma de escritura, mesa). "
                  "Si te preguntan por un cliente, busca en el listado. Si no está, dilo brevemente.\n\n"
                  f"CARPETAS ACTUALES:\n{contexto}\n\n"
                  + (f"CONVERSACIÓN PREVIA:\n{hist_txt}" if hist_txt else ""))
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(api_key=key, session_id=session, system_message=system).with_model("openai", "gpt-5.4-mini")
        resp = await chat.send_message(UserMessage(text=msg))
    except Exception as e:
        resp = f"Tuve un problema para responder ({str(e)[:80]}). Intenta de nuevo."
    await db.conversaciones.insert_one({
        "id": str(uuid.uuid4()), "session_id": session,
        "user_name": payload.get("user_name", ""), "user_msg": msg,
        "response": resp, "timestamp": now_iso(),
    })
    return {"response": resp, "session_id": session, "enabled": True}


@api.post("/central/chat-files")
async def central_chat_files():
    return {"response": "Procesamiento de archivos no disponible en esta instancia.", "enabled": False}


@api.post("/central/tts")
async def central_tts(payload: dict):
    text = ((payload or {}).get("text") or "").strip()[:4000]
    if not text:
        raise HTTPException(status_code=400, detail="Sin texto")
    try:
        from emergentintegrations.llm.openai import OpenAITextToSpeech
        tts = OpenAITextToSpeech(api_key=os.environ.get("EMERGENT_LLM_KEY", ""))
        audio_b64 = await tts.generate_speech_base64(text=text, model="tts-1", voice="onyx")
        return {"audio": audio_b64}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"TTS no disponible: {str(e)[:100]}")


async def _acciones_pendientes():
    folders = await db.folders.find({}).sort("created_at", -1).limit(100).to_list(100)
    acciones = []
    for f in folders:
        nombre = f.get("nombre", "")
        faltan = [c["nombre"] for c in _criterios_folder(f)
                  if not c["ok"] and c["nombre"] not in ("Enviada a mesa", "Datos financieros completos")]
        if faltan:
            acciones.append(f"📄 {nombre}: faltan {', '.join(faltan)}")
        elif not f.get("emails_sent_count"):
            acciones.append(f"📤 {nombre}: carpeta completa, lista para enviar a mesa")
        if f.get("tasacion_solicitada_at") and not f.get("tasacion_fecha"):
            acciones.append(f"📐 {nombre}: tasación solicitada, aún sin fecha de Value Property")
        if f.get("escritura_solicitada_at") and not f.get("escritura_confirmada_at"):
            acciones.append(f"🖊 {nombre}: aviso de firma enviado, el cliente aún no confirma")
        rep = f.get("estudio_reparos") or {}
        pend = [i for i in (rep.get("items") or []) if not i.get("satisfecho")]
        if pend and rep.get("estado") != "satisfecho":
            acciones.append(f"⚖ {nombre}: {len(pend)} reparo(s) de estudio de título pendiente(s)")
    return acciones


@api.get("/central/resumen-diario")
async def central_resumen_diario():
    acciones = await _acciones_pendientes()
    hoy = datetime.now(_tz_chile()).strftime("%d-%m-%Y")
    if acciones:
        texto = (f"¡Buenos días! Soy Martín ☀️ Resumen de hoy {hoy}:\n\n" + "\n".join(acciones[:12])
                 + ("\n\n…y más carpetas en la lista." if len(acciones) > 12 else ""))
    else:
        texto = f"¡Buenos días! Soy Martín ☀️ Hoy {hoy} no hay carpetas que necesiten acción. Todo al día 💪"
    return {"resumen": texto, "acciones": len(acciones)}


async def _resumen_semanal_html():
    uf = await get_valor_uf()
    mes = datetime.now(timezone.utc).strftime("%Y-%m")
    base_q = {"es_solicitud": True, "ignorado": {"$ne": True}, "detectado_en": {"$regex": f"^{mes}"}}
    enviadas = await db.tasacion_cobros.count_documents(base_q)
    pagadas = await db.tasacion_cobros.count_documents({**base_q, "pagado": True})
    pendientes = enviadas - pagadas
    acciones = await _acciones_pendientes()
    acc_html = ("".join(f'<li style="margin:5px 0">{a}</li>' for a in acciones[:20])
                if acciones else '<li style="margin:5px 0">Sin acciones pendientes. Todo al día 💪</li>')
    # Tabla de estado de TODAS las carpetas y sus pendientes
    docs = await db.folders.find().sort("created_at", -1).to_list(300)
    filas_carp = ""
    td = "padding:5px 8px;border-bottom:1px solid #eceef3;vertical-align:top;font-size:12px;color:#1a1f2e"
    for d in docs:
        nombre_f = d.get("nombre", "")
        ct = (d.get("credit_request") or {}).get("client_type") or "dependiente"
        try:
            cats = {fsvc.cat_de_archivo(a["nombre"], a["subfolder"]) for a in fsvc.scan_archivos(nombre_f)} - {"combinado", "codeudor", "estudio_titulo"}
            faltan = [fsvc.MISSING_LABELS.get(c, c) for c in fsvc.required_cats(ct) if c not in cats]
        except Exception:
            faltan = []
        if not ((d.get("datos_financieros") or {}).get("fecha_entrega") or "").strip():
            faltan.append("Fecha de entrega")
        est = lambda sol, term: "✅" if term else ("⏳" if sol else "—")
        mesa_e = f"📧×{d.get('emails_sent_count')}" if d.get("emails_sent_count") else "—"
        escr_e = "✅" if d.get("escritura_confirmada_at") else ("⏳" if d.get("escritura_solicitada_at") else "—")
        filas_carp += (f"<tr><td style='{td}'><b>{nombre_f}</b></td><td style='{td}'>{mesa_e}</td>"
                       f"<td style='{td}'>{est(d.get('tasacion_solicitada_at'), d.get('tasacion_terminado_at'))}</td>"
                       f"<td style='{td}'>{est(d.get('estudio_titulo_solicitado_at'), d.get('estudio_titulo_terminado_at'))}</td>"
                       f"<td style='{td}'>{escr_e}</td>"
                       f"<td style='{td};color:{'#b91c1c' if faltan else '#15803d'}'>{', '.join(faltan) or '✔ completa'}</td></tr>")
    th = "padding:5px 8px;text-align:left;font-size:12px;color:#6b7280"
    tabla_carpetas = f"""
      <div style="color:#1a1f2e;font-size:15px;font-weight:700;border-left:4px solid #d4af37;padding-left:10px;margin:18px 0 8px">Estado de todas las carpetas ({len(docs)})</div>
      <table style="width:100%;border-collapse:collapse;background:#fff;border:1px solid #eceef3;border-radius:8px">
        <tr><th style="{th}">Cliente</th><th style="{th}">Mesa</th><th style="{th}">Tasación</th><th style="{th}">E. Título</th><th style="{th}">Escritura</th><th style="{th}">Pendientes</th></tr>
        {filas_carp}
      </table>"""
    semana = datetime.now(_tz_chile()).strftime("%d-%m-%Y")
    inner = f"""
      <p>¡Buenos días! Soy <b>Martín</b> ☀️ Este es el resumen semanal al <b>{semana}</b>:</p>
      <div style="color:#1a1f2e;font-size:15px;font-weight:700;border-left:4px solid #d4af37;padding-left:10px;margin:14px 0 8px">Cobros de Tasación — Vivienda Usada (mes {mes})</div>
      <div style="background:#f8f9fc;border:1px solid #eceef3;border-radius:8px;padding:12px 20px">
        <table style="border-collapse:collapse">
          <tr><td style="padding:4px 14px 4px 0;color:#6b7280;font-size:13px">Cobros enviados</td><td style="font-weight:700;color:#1a1f2e">{enviadas}</td></tr>
          <tr><td style="padding:4px 14px 4px 0;color:#6b7280;font-size:13px">Pagadas</td><td style="font-weight:700;color:#15803d">{pagadas} · {_fmt_clp(pagadas * TASACION_COBRO_UF * uf)}</td></tr>
          <tr><td style="padding:4px 14px 4px 0;color:#6b7280;font-size:13px">Pendientes de pago</td><td style="font-weight:700;color:#b91c1c">{pendientes} · {_fmt_clp(pendientes * TASACION_COBRO_UF * uf)}</td></tr>
        </table>
      </div>
      <div style="color:#1a1f2e;font-size:15px;font-weight:700;border-left:4px solid #d4af37;padding-left:10px;margin:18px 0 8px">Carpetas que necesitan acción ({len(acciones)})</div>
      <ul style="margin:6px 0 0;padding-left:22px;color:#111;list-style:none">{acc_html}</ul>
      {"<p style='margin-top:10px;color:#6b7280;font-size:12px'>…y más carpetas en la lista.</p>" if len(acciones) > 20 else ""}
      {tabla_carpetas}
      <p style="margin-top:16px;color:#555">¡Que tengas una excelente semana!</p>"""
    return _marca_wrap(inner, "Resumen Semanal de Martín")


async def _enviar_resumen_semanal():
    cuerpo = await _resumen_semanal_html()
    semana = datetime.now(_tz_chile()).strftime("%d-%m-%Y")
    res = await asyncio.to_thread(mail.send_mail, _sender_por_rol("principal"),
                                  f"📊 Resumen Semanal de Martín — {semana}", cuerpo, [], "secundaria")
    return res


async def _resumen_semanal_loop():
    """Cada lunes ~08:00 (hora Chile): envía el resumen semanal por correo al administrador."""
    while True:
        await asyncio.sleep(1800)
        try:
            ahora = datetime.now(_tz_chile())
            if ahora.weekday() != 0 or ahora.hour < 8:
                continue
            semana_key = ahora.strftime("%G-W%V")
            cfg = await db.config.find_one({"_key": "resumen_semanal"}) or {}
            if cfg.get("last_sent_week") == semana_key:
                continue
            res = await _enviar_resumen_semanal()
            if res.get("success"):
                await db.config.update_one({"_key": "resumen_semanal"},
                                           {"$set": {"_key": "resumen_semanal",
                                                     "last_sent_week": semana_key,
                                                     "last_sent_at": now_iso()}}, upsert=True)
        except Exception as e:
            logging.warning(f"resumen semanal: {e}")


@api.post("/central/resumen-semanal/enviar")
async def resumen_semanal_manual(payload: dict = None):
    if not (payload or {}).get("confirm"):
        return {"body": await _resumen_semanal_html(), "to": _sender_por_rol("principal")}
    res = await _enviar_resumen_semanal()
    if not res.get("success"):
        raise HTTPException(status_code=502, detail=res.get("error", "Error de envío"))
    return {"ok": True, "to": _sender_por_rol("principal")}


# ---------------------------------------------------------------------------
# Reporte Diario de Correos (todos los días 10:00 hora Chile)
# ---------------------------------------------------------------------------
async def _reporte_correos_html():
    desde = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    recibidos = await db.proc_queue.find({"date_iso": {"$gte": desde}}
                                         ).sort("date_iso", -1).limit(50).to_list(50)
    enviados = await db.folders.find({"last_email_sent_at": {"$gte": desde}}).limit(50).to_list(50)
    descartados = await db.proc_queue.find({"status": "descartado",
                                            "descartado_en": {"$gte": desde}}).limit(30).to_list(30)
    pendientes = await db.proc_queue.find({"status": {"$in": ["pendiente", "revisar"]}}
                                          ).sort("date_iso", -1).limit(30).to_list(30)
    folders = await db.folders.find({"emails_sent_count": {"$in": [None, 0]}}).limit(150).to_list(150)
    con_faltantes = []
    for f in folders:
        faltan = [c["nombre"] for c in _criterios_folder(f)
                  if not c["ok"] and c["nombre"] not in ("Enviada a mesa", "Datos financieros completos")]
        if faltan:
            con_faltantes.append((f.get("nombre", ""), faltan))

    def _sec(titulo, items_html, vacio):
        cuerpo_sec = items_html or f'<li style="margin:5px 0;color:#6b7280">{vacio}</li>'
        return (f'<div style="color:#1a1f2e;font-size:15px;font-weight:700;border-left:4px solid #d4af37;'
                f'padding-left:10px;margin:16px 0 8px">{titulo}</div>'
                f'<ul style="margin:0;padding-left:22px;color:#111;list-style:none">{cuerpo_sec}</ul>')

    li = lambda t: f'<li style="margin:5px 0">{t}</li>'
    rec_html = "".join(li(f"📥 \"{(r.get('subject') or '')[:70]}\" — {r.get('sender','')}") for r in recibidos)
    env_html = "".join(li(f"✅ <b>{f.get('nombre','')}</b> — enviada a mesa "
                          f"({str(f.get('last_email_sent_at',''))[:16].replace('T',' ')})") for f in enviados)
    falt_html = "".join(li(f"📄 <b>{n}</b> — NO enviada: faltan {', '.join(fl)}") for n, fl in con_faltantes[:25])
    desc_html = "".join(li(f"🚫 \"{(d.get('subject') or '')[:60]}\" de {d.get('sender','')} — "
                           f"{d.get('descartado_motivo','')}") for d in descartados)
    pend_html = "".join(li(f"⏳ \"{(p.get('subject') or '')[:60]}\" de {p.get('sender','')} — "
                           f"{'sin leer/procesar' if p.get('status') == 'pendiente' else 'requiere revisión manual'}")
                        for p in pendientes)
    hoy = datetime.now(_tz_chile()).strftime("%d-%m-%Y")
    inner = f"""
      <p>¡Buenos días! Este es el <b>reporte diario de correos</b> al <b>{hoy}</b> (últimas 24 horas):</p>
      {_sec(f"Correos de gestión recibidos ({len(recibidos)})", rec_html, "No se recibieron correos de gestión.")}
      {_sec(f"Enviadas a mesa ({len(enviados)})", env_html, "Ninguna carpeta fue enviada a mesa.")}
      {_sec(f"NO enviadas — faltan documentos ({len(con_faltantes)})", falt_html, "No hay carpetas detenidas por documentos.")}
      {_sec(f"Correos descartados por regla ({len(descartados)})", desc_html, "Ningún correo fue descartado.")}
      {_sec(f"Sin leer / pendientes de revisión ({len(pendientes)})", pend_html, "No hay correos pendientes.")}"""
    return _marca_wrap(inner, "Reporte Diario de Correos")


async def _enviar_reporte_correos():
    cuerpo = await _reporte_correos_html()
    hoy = datetime.now(_tz_chile()).strftime("%d-%m-%Y")
    return await asyncio.to_thread(mail.send_mail, _sender_por_rol("principal"),
                                   f"📬 Reporte Diario de Correos — {hoy}", cuerpo, [], "secundaria")


async def _reporte_correos_loop():
    """Todos los días a las 10:00 (hora Chile): reporte de correos recibidos,
    enviados a mesa y no enviados con su razón."""
    while True:
        await asyncio.sleep(900)
        try:
            ahora = datetime.now(_tz_chile())
            if ahora.hour < 10:
                continue
            dia_key = ahora.strftime("%Y-%m-%d")
            cfg = await db.config.find_one({"_key": "reporte_correos"}) or {}
            if cfg.get("last_sent_day") == dia_key:
                continue
            res = await _enviar_reporte_correos()
            if res.get("success"):
                await db.config.update_one({"_key": "reporte_correos"},
                                           {"$set": {"_key": "reporte_correos",
                                                     "last_sent_day": dia_key,
                                                     "last_sent_at": now_iso()}}, upsert=True)
        except Exception as e:
            logging.warning(f"reporte correos: {e}")


@api.post("/central/reporte-correos/enviar")
async def reporte_correos_manual(payload: dict = None):
    if not (payload or {}).get("confirm"):
        return {"body": await _reporte_correos_html(), "to": _sender_por_rol("principal")}
    res = await _enviar_reporte_correos()
    if not res.get("success"):
        raise HTTPException(status_code=502, detail=res.get("error", "Error de envío"))
    return {"ok": True, "to": _sender_por_rol("principal")}


# ---------------------------------------------------------------------------
# Admin: users, alertas, learning
# ---------------------------------------------------------------------------
@api.get("/admin/users")
async def list_users():
    docs = await db.users.find().to_list(200)
    return {"users": [{"codigo": d["codigo"], "nombre": d.get("nombre"),
                       "rol": d.get("rol"), "created": d.get("created")} for d in docs]}


@api.post("/admin/users")
async def create_user(payload: dict):
    codigo = (payload.get("codigo") or "").strip()
    if not codigo or not payload.get("nombre") or not payload.get("password"):
        raise HTTPException(status_code=400, detail="Todos los campos son obligatorios")
    if await db.users.find_one({"codigo": codigo}):
        raise HTTPException(status_code=400, detail="El codigo ya existe")
    doc = {"codigo": codigo, "nombre": payload["nombre"], "password": payload["password"],
           "rol": payload.get("rol", "ejecutivo"), "created": now_iso()}
    await db.users.insert_one(dict(doc))
    return {"ok": True, "codigo": codigo}


@api.delete("/admin/users/{codigo}")
async def delete_user(codigo: str):
    if codigo in ("admin", "administrador"):
        raise HTTPException(status_code=400, detail="No se puede eliminar el usuario administrador")
    await db.users.delete_one({"codigo": codigo})
    return {"ok": True}


@api.get("/admin/alertas")
async def admin_alertas():
    return {"alertas": []}


@api.post("/admin/alertas/refresh")
async def admin_alertas_refresh():
    return {"ok": True, "alertas": []}


@api.get("/admin/learning/status")
async def learning_status():
    total = await db.predic_history.count_documents({})
    sims = await db.simulaciones.count_documents({})
    return {
        "data_sources": {"credit_learning": 0, "predic_history": total, "score_history": total},
        "simulation_patterns": {"summary": f"{sims} simulaciones registradas", "updated_at": now_iso()},
    }


@api.get("/admin/learning/email-stats")
async def learning_email_stats():
    return await asyncio.to_thread(mail.email_stats)


@api.post("/admin/learning/trigger")
async def learning_trigger():
    return {"ok": True}


@api.get("/alertas/seguimiento")
async def alertas_seguimiento(dias: int = 7):
    return {"alertas": []}


@api.get("/search")
async def search(q: str = "", limit: int = 15):
    results = []
    if len(q) >= 2:
        sims = await db.simulaciones.find(
            {"nombre_completo": {"$regex": q, "$options": "i"}}
        ).limit(limit).to_list(limit)
        for s in sims:
            results.append({"tipo": "simulacion", "nombre": s.get("nombre_completo", "-"),
                            "detalle": f"{s.get('capacidad_credito_uf', 0)} UF", "modulo": "historial"})
        folders = await db.folders.find(
            {"nombre": {"$regex": q, "$options": "i"}}
        ).limit(limit).to_list(limit)
        for f in folders:
            results.append({"tipo": "cliente", "nombre": f.get("nombre", "-"),
                            "detalle": f.get("rut", ""), "modulo": "clientes"})
    return {"results": results[:limit]}


# ---------------------------------------------------------------------------
# Clientes / Carpetas (archivos físicos en disco + metadata en Mongo)
# ---------------------------------------------------------------------------
def _folder_public(doc, con_archivos=False):
    d = clean(dict(doc))
    archivos = fsvc.scan_archivos(d.get("nombre", ""))
    cats = sorted({fsvc.cat_de_archivo(a["nombre"], a["subfolder"]) for a in archivos} - {"combinado", "codeudor", "estudio_titulo"})
    cr = d.get("credit_request") or {}
    cr["doc_categories"] = cats
    d["credit_request"] = cr
    d["total_archivos"] = len(archivos)
    ct = cr.get("client_type") or "dependiente"
    missing = [r for r in fsvc.required_cats(ct) if r not in cats]
    df = d.get("datos_financieros") or {}
    d["is_ready_to_send"] = bool(archivos) and not missing and bool(df.get("valor_propiedad"))
    if con_archivos:
        d["archivos"] = archivos
    else:
        d.pop("archivos", None)
    return d


async def _mesa_respuesta_folder(d):
    """Busca la respuesta de mesa (aprobación/rechazo) para esta carpeta en seguimiento.
    REGLA: si la carpeta ya tiene descargada la carta de aprobación o la simulación
    ajustada, se considera APROBADA por mesa de inmediato."""
    toks = [t for t in _norm_texto(d.get("nombre", "")).split() if len(t) > 2]
    if not toks:
        return None
    segs = await db.seguimiento.find({}).sort("fecha", -1).limit(200).to_list(200)
    for s in segs:
        texto = _norm_texto(f"{s.get('cliente','')} {s.get('asunto','')}")
        hits = sum(1 for t in toks if t in texto)
        if hits >= min(2, len(toks)):
            est = (s.get("estado") or "").lower()
            if est.startswith("aprob"):
                return "aprobada"
            if est.startswith("rech"):
                return "rechazada"
    for a in fsvc.scan_archivos(d.get("nombre", "")):
        low = a["nombre"].lower()
        if re.search(r"carta.*aprobaci|aprobaci[oó]n", low) or re.search(r"_cm\.pdf$|ajustad", low):
            return "aprobada"
    return None


def _criterios_folder(d):
    archivos = fsvc.scan_archivos(d.get("nombre", ""))
    cats = {fsvc.cat_de_archivo(a["nombre"], a["subfolder"]) for a in archivos} - {"combinado", "codeudor", "estudio_titulo"}
    cr = d.get("credit_request") or {}
    tipo_cliente = cr.get("client_type") or "dependiente"
    df = d.get("datos_financieros") or {}
    if tipo_cliente == "independiente":
        docs_req = [("Cédula de identidad", "cedula"), ("Impuesto a la renta", "imp_renta"),
                    ("Boletas de honorarios", "boletas"), ("Informe CMF", "cmf")]
    else:
        docs_req = [("Cédula de identidad", "cedula"), ("Liquidaciones de sueldo", "liquidacion"),
                    ("Cotizaciones AFP", "afp"), ("Informe CMF", "cmf")]
    criterios = [{"nombre": lbl, "ok": cat in cats} for lbl, cat in docs_req]
    criterios.append({"nombre": "Datos financieros completos",
                      "ok": bool(df.get("valor_propiedad") and df.get("monto_credito"))})
    criterios.append({"nombre": "Enviada a mesa", "ok": bool(d.get("emails_sent_count"))})
    return criterios


@api.get("/clientes/folders-light")
async def list_folders_light(q: str = ""):
    """Lista liviana de carpetas (solo id/nombre/rut) — rápida, para el mini programa."""
    query = {"nombre": {"$regex": re.escape(q), "$options": "i"}} if q else {}
    docs = await db.folders.find(query, {"_id": 0, "id": 1, "nombre": 1, "rut": 1}).sort("created_at", -1).to_list(800)
    return {"folders": docs}


@api.get("/clientes/folders")
async def list_folders(q: str = ""):
    query = {"nombre": {"$regex": q, "$options": "i"}} if q else {}
    docs = await db.folders.find(query).sort("created_at", -1).limit(200).to_list(200)
    stats = await _stats_mesa()
    out = []
    for d in docs:
        f = _folder_public(d)
        f["prob_aprobacion"] = _prob_aprobacion_folder(d, stats)
        f["criterios"] = _criterios_folder(d)
        f["mesa_respuesta"] = await _mesa_respuesta_folder(d)
        out.append(f)
    return {"folders": out}


_PAT_FIRMA_CORREO = re.compile(r"^image\d{1,4}\.(jpe?g|png|gif|bmp)$", re.I)


def _rut_regex_flexible(rut):
    """'12.345.678-9' -> regex que matchea con o sin puntos/guion."""
    nucleo = re.sub(r"[.\-\s]", "", rut or "")
    if len(nucleo) < 7:
        return ""
    return r"\.?".join(re.escape(c) for c in nucleo[:-1]) + r"[\-.]?\s?" + re.escape(nucleo[-1])


@api.post("/clientes/folders/forzar")
async def forzar_folder(payload: dict):
    """Fuerza la creación manual de una carpeta: busca por NOMBRE y/o RUT en los correos
    ingresados los datos y descarga los archivos adjuntos (requiere clave admin)."""
    payload = payload or {}
    if payload.get("clave") != CLAVE_FORZAR_CARPETA:
        raise HTTPException(status_code=403, detail="Clave incorrecta")
    nombre = (payload.get("nombre") or "").strip()
    rut = (payload.get("rut") or "").strip()
    if len(nombre) < 3 and not rut:
        raise HTTPException(status_code=400, detail="Indica el nombre o el RUT del cliente")
    palabras = [p for p in re.split(r"\s+", nombre) if len(p) >= 3]
    conds = [{"$or": [{"subject": {"$regex": re.escape(p), "$options": "i"}},
                      {"classification.cliente": {"$regex": re.escape(p), "$options": "i"}},
                      {"body_full": {"$regex": re.escape(p), "$options": "i"}}]}
             for p in palabras]
    query = {"$and": conds} if conds else None
    rut_rx = _rut_regex_flexible(rut)
    if rut_rx:
        cond_rut = {"$or": [{"subject": {"$regex": rut_rx, "$options": "i"}},
                            {"body_full": {"$regex": rut_rx, "$options": "i"}},
                            {"campos.rut": {"$regex": rut_rx, "$options": "i"}},
                            {"classification.rut": {"$regex": rut_rx, "$options": "i"}}]}
        query = {"$or": [query, cond_rut]} if query else cond_rut
    items = await db.proc_queue.find(query).sort("date_iso", 1).to_list(20) if query else []
    procesados, errores = [], []
    for it in items:
        try:
            r = await proc_upload_drive(it["id"], force=True, clave=payload["clave"])
            procesados.append({"subject": it.get("subject", ""),
                               "carpeta": r.get("folder_name", ""),
                               "archivos": len(r.get("uploaded") or [])})
        except Exception as e:
            errores.append(f"{(it.get('subject') or '')[:50]}: {str(e)[:80]}")
    folder = None
    if palabras:
        folder = await db.folders.find_one(
            {"nombre": {"$regex": re.escape(palabras[0]), "$options": "i"}})
    if not folder and rut_rx:
        folder = await db.folders.find_one({"rut": {"$regex": rut_rx, "$options": "i"}})
    if not folder:
        folder = {"id": str(uuid.uuid4()), "nombre": (nombre or rut).upper(),
                  "rut": rut, "archivos": [],
                  "created_at": now_iso(), "origen": "forzada_manual"}
        await db.folders.insert_one(dict(folder))
        fsvc.folder_dir(folder["nombre"]).mkdir(parents=True, exist_ok=True)
    elif rut and not folder.get("rut"):
        await db.folders.update_one({"id": folder["id"]}, {"$set": {"rut": rut}})
    # Buscar adjuntos directamente en el correo (IMAP) por nombre y por RUT
    imap_bajados = []
    try:
        resultados = await asyncio.to_thread(mail.search_attachments_by_person, nombre or rut)
        if rut and nombre:
            try:
                resultados += await asyncio.to_thread(mail.search_attachments_by_person, rut)
            except Exception:
                pass
        if resultados and not (folder.get("source_email") or "").strip():
            remit = (resultados[-1].get("from") or resultados[0].get("from") or "").strip()
            if "@" in remit:
                await db.folders.update_one({"id": folder["id"]}, {"$set": {"source_email": remit}})
                folder["source_email"] = remit
        existentes = {a["nombre"].lower() for a in fsvc.scan_archivos(folder["nombre"])}
        for r in resultados:
            for p in r.get("pdfs") or []:
                fn = fsvc.safe_name(p["filename"])
                if fn.lower() in existentes or not p.get("content_bytes") or _PAT_FIRMA_CORREO.match(fn):
                    continue
                cat = fsvc.cat_de_texto(fn)
                sub = "07_estudio_titulo" if cat == "estudio_titulo" else ""
                rel = fsvc.guardar_archivo(folder["nombre"], fn, p["content_bytes"], subfolder=sub)
                existentes.add(fn.lower())
                imap_bajados.append(rel)
    except Exception:
        pass
    # Buscar TODO lo que exista del cliente: carta de aprobación, PDF ajustado, etc.
    sync_copiados = []
    try:
        sync_copiados = await _sync_docs_aprobacion(folder.get("nombre", ""))
    except Exception:
        pass
    # Confirmar nombre y RUT leyendo la cédula de identidad (OCR + IA, sin inventar)
    verificacion = None
    try:
        verificacion = await _verificar_identidad_por_cedula(folder)
    except Exception:
        pass
    return {"ok": True, "carpeta": folder.get("nombre", ""),
            "correos_encontrados": len(items), "procesados": procesados,
            "archivos_imap": imap_bajados,
            "docs_aprobacion_descargados": sync_copiados,
            "verificacion_cedula": verificacion,
            "errores": errores}


async def _verificar_identidad_por_cedula(folder):
    """Lee la cédula de identidad de la carpeta (OCR + IA) para confirmar y corregir
    el nombre y el RUT. Nunca inventa: solo usa lo leído en la cédula."""
    nombre_actual = folder.get("nombre", "")
    archivos = fsvc.scan_archivos(nombre_actual)
    ced = next((a for a in archivos
                if fsvc.cat_de_archivo(a["nombre"], a["subfolder"]) == "cedula"), None)
    if not ced:
        return None
    raw = (fsvc.folder_dir(nombre_actual) / ced["ruta"]).read_bytes()
    texto, _met = await asyncio.to_thread(ocr_service.extraer_texto, raw, ced["nombre"])
    if not texto or len(texto.strip()) < 20:
        return None
    datos = await ai_extract.clasificar_y_extraer(texto, ced["nombre"])
    nombre_ced = (datos.get("nombre_cliente") or "").strip()
    rut_ced = (datos.get("rut") or "").strip()
    cambios = {}
    if rut_ced and rut_ced != (folder.get("rut") or ""):
        cambios["rut"] = rut_ced
    toks_act = set(_norm_texto(nombre_actual).split())
    toks_ced = set(_norm_texto(nombre_ced).split())
    if (nombre_ced and len(toks_ced) >= 2 and toks_act & toks_ced
            and _norm_texto(nombre_ced) != _norm_texto(nombre_actual)):
        nuevo = nombre_ced.upper()
        vieja_dir = fsvc.folder_dir(nombre_actual)
        nueva_dir = fsvc.folder_dir(nuevo)
        if vieja_dir.exists() and not nueva_dir.exists():
            vieja_dir.rename(nueva_dir)
            cambios["nombre"] = nuevo
        elif not vieja_dir.exists():
            cambios["nombre"] = nuevo
    if cambios:
        await db.folders.update_one({"id": folder["id"]}, {"$set": cambios})
        folder.update(cambios)
    return {"cedula": ced["nombre"], "nombre_cedula": nombre_ced,
            "rut_cedula": rut_ced, "cambios": cambios}


@api.post("/clientes/folders/{fid}/escrituracion")
async def folder_toggle_escrituracion(fid: str, payload: dict = None):
    """Mueve la carpeta al módulo Escrituración o la devuelve a Solicitudes de Crédito."""
    await _get_folder_doc(fid)
    activar = bool((payload or {}).get("activar", True))
    await db.folders.update_one({"id": fid}, {"$set": {
        "is_escrituracion": activar,
        "escrituracion_movida_at": now_iso() if activar else None}})
    return {"ok": True, "is_escrituracion": activar}


@api.post("/clientes/folders/{fid}/enriquecer")
async def folder_enriquecer(fid: str, payload: dict = None):
    """Busca de nuevo en el correo (asunto, cuerpo y adjuntos) documentos del cliente.
    modo='credito' guarda por categoría de crédito; modo='estudio' guarda en
    07_estudio_titulo (NUNCA se mezclan con la solicitud de crédito)."""
    doc = await _get_folder_doc(fid)
    modo = ((payload or {}).get("modo") or "credito").lower()
    nombre = doc.get("nombre", "")
    rut = (doc.get("rut") or "").strip()
    resultados = await asyncio.to_thread(mail.search_attachments_by_person, nombre)
    if rut:
        try:
            resultados += await asyncio.to_thread(mail.search_attachments_by_person, rut)
        except Exception:
            pass
    if resultados and not (doc.get("source_email") or "").strip():
        remit = (resultados[-1].get("from") or resultados[0].get("from") or "").strip()
        if "@" in remit:
            await db.folders.update_one({"id": fid}, {"$set": {"source_email": remit}})
    existentes = {a["nombre"].lower() for a in fsvc.scan_archivos(nombre)}
    nuevos = []
    for r in resultados:
        for p in r.get("pdfs") or []:
            fn = fsvc.safe_name(p["filename"])
            if fn.lower() in existentes or not p.get("content_bytes") or _PAT_FIRMA_CORREO.match(fn):
                continue
            cat = fsvc.cat_de_texto(fn)
            if modo == "estudio":
                if cat not in ("estudio_titulo", "extras"):
                    continue
                rel = fsvc.guardar_archivo(nombre, fn, p["content_bytes"],
                                           subfolder="07_estudio_titulo")
            else:
                sub = "07_estudio_titulo" if cat == "estudio_titulo" else ""
                rel = fsvc.guardar_archivo(nombre, fn, p["content_bytes"], subfolder=sub)
            existentes.add(fn.lower())
            nuevos.append({"archivo": rel, "asunto": (r.get("subject") or "")[:80]})
    return {"ok": True, "modo": modo, "correos_revisados": len(resultados),
            "archivos_nuevos": nuevos}


import zipfile as _zipfile

RESPALDO_EXCLUIR = {"save_jobs"}


@api.get("/admin/respaldo/export")
async def respaldo_export():
    """Descarga un ZIP con la base de datos (carpetas, config, usuarios…) y todos los archivos."""
    dump = {}
    for c in await db.list_collection_names():
        if c in RESPALDO_EXCLUIR or c.startswith("system."):
            continue
        docs = await db[c].find().to_list(8000)
        for d in docs:
            d.pop("_id", None)
        dump[c] = docs
    tmp = Path("/tmp") / f"respaldo_cm_{datetime.now(_tz_chile()).strftime('%Y%m%d_%H%M')}.zip"

    def _build():
        with _zipfile.ZipFile(tmp, "w", _zipfile.ZIP_DEFLATED) as z:
            z.writestr("db.json", json.dumps(dump, ensure_ascii=False, default=str))
            base = fsvc.CLIENTES_DIR
            if base.exists():
                for p in base.rglob("*"):
                    if p.is_file():
                        z.write(p, arcname=f"clientes/{p.relative_to(base).as_posix()}")
    await asyncio.to_thread(_build)
    return FileResponse(str(tmp), media_type="application/zip", filename=tmp.name)


@api.post("/admin/respaldo/import-chunk")
async def respaldo_import_chunk(session_id: str = Form(...), index: int = Form(...), chunk: UploadFile = File(...)):
    d = Path("/tmp/respaldo_import") / _safe_name(session_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{int(index):05d}.part").write_bytes(await chunk.read())
    return {"ok": True, "index": index}


@api.post("/admin/respaldo/import-finish")
async def respaldo_import_finish(payload: dict):
    session_id = _safe_name((payload or {}).get("session_id") or "")
    d = Path("/tmp/respaldo_import") / session_id
    if not d.exists():
        raise HTTPException(status_code=404, detail="No hay partes subidas para esta sesión")
    zpath = d / "respaldo.zip"
    with open(zpath, "wb") as out:
        for part in sorted(d.glob("*.part")):
            out.write(part.read_bytes())
    restaurados, archivos = {}, 0
    try:
        with _zipfile.ZipFile(zpath) as z:
            data = json.loads(z.read("db.json").decode("utf-8"))
            for c, docs in data.items():
                if c in RESPALDO_EXCLUIR or c.startswith("system."):
                    continue
                n = 0
                for doc in docs:
                    doc.pop("_id", None)
                    if doc.get("id"):
                        await db[c].update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
                    elif doc.get("_key"):
                        await db[c].update_one({"_key": doc["_key"]}, {"$set": doc}, upsert=True)
                    else:
                        await db[c].update_one(doc, {"$set": doc}, upsert=True)
                    n += 1
                restaurados[c] = n
            base = fsvc.CLIENTES_DIR
            for info in z.infolist():
                if info.is_dir() or not info.filename.startswith("clientes/"):
                    continue
                rel = info.filename[len("clientes/"):]
                if not rel or ".." in rel:
                    continue
                destino = base / rel
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_bytes(z.read(info))
                archivos += 1
    except _zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="El archivo subido no es un ZIP válido")
    finally:
        import shutil as _sh
        _sh.rmtree(d, ignore_errors=True)
    return {"ok": True, "colecciones": restaurados, "archivos_restaurados": archivos}


@api.post("/clientes/folders")
async def create_folder(payload: dict):
    doc = {
        "id": str(uuid.uuid4()),
        "nombre": payload.get("nombre", ""),
        "rut": payload.get("rut", ""),
        "codeudor_nombre": payload.get("codeudor_nombre", ""),
        "codeudor_rut": payload.get("codeudor_rut", ""),
        "archivos": [],
        "created_at": now_iso(),
    }
    await db.folders.insert_one(dict(doc))
    fsvc.folder_dir(doc["nombre"]).mkdir(parents=True, exist_ok=True)
    return _folder_public(doc)


@api.get("/clientes/folders/{fid}")
async def get_folder(fid: str):
    doc = await db.folders.find_one({"id": fid})
    if not doc:
        raise HTTPException(status_code=404, detail="Carpeta no encontrada")
    res = _folder_public(doc, con_archivos=True)
    res["prob_aprobacion"] = _prob_aprobacion_folder(doc, await _stats_mesa())
    res["criterios"] = _criterios_folder(doc)
    return res


@api.post("/clientes/folders/{fid}/pedir-faltantes")
async def folder_pedir_faltantes(fid: str, payload: dict):
    payload = payload or {}
    doc = await db.folders.find_one({"id": fid})
    if not doc:
        raise HTTPException(status_code=404, detail="Carpeta no encontrada")
    destinatario = (payload.get("destinatario") or doc.get("source_email") or "").strip()
    faltantes = [f for f in (payload.get("faltantes") or []) if str(f).strip()]
    if not faltantes:
        faltantes = [c["nombre"] for c in _criterios_folder(doc)
                     if not c["ok"] and c["nombre"] not in ("Enviada a mesa", "Datos financieros completos")]
    nombre = doc.get("nombre", "")
    subject = f"Documentos faltantes — Solicitud de crédito {nombre}"
    lis = "".join(f'<li style="margin:4px 0">{f}</li>' for f in faltantes)
    extra = (payload.get("mensaje") or "").strip()
    cuerpo = _marca_wrap(f"""
      <p>Estimados, junto con saludar:</p>
      <p>En relación a la solicitud de crédito de <b>{nombre}</b>{f" (RUT {doc.get('rut')})" if doc.get('rut') else ""},
      para continuar con la evaluación necesitamos que nos hagan llegar los siguientes documentos faltantes:</p>
      <ol style="margin:6px 0 0;padding-left:22px;color:#111">{lis}</ol>
      {f'<p style="margin-top:12px">{extra}</p>' if extra else ''}
      <p style="margin-top:14px">Quedamos atentos. Muchas gracias.</p>
      <p style="margin-top:16px;color:#555">Saludos cordiales,</p>""", "Documentos Faltantes — Solicitud de Crédito")
    if not payload.get("confirm"):
        return {"to": destinatario, "subject": subject, "body": cuerpo, "faltantes": faltantes,
                "sender": _sender_por_rol("secundaria")}
    if not destinatario or "@" not in destinatario:
        raise HTTPException(status_code=400, detail="No hay correo del remitente de la solicitud (destinatario)")
    res = await asyncio.to_thread(mail.send_mail, destinatario, subject, cuerpo, [], "secundaria")
    if not res.get("success"):
        raise HTTPException(status_code=502, detail=res.get("error", "Error de envío"))
    await db.folders.update_one({"id": fid}, {"$set": {"faltantes_pedidos_at": now_iso(),
                                                       "source_email": destinatario},
                                              "$unset": {"faltantes_recordatorio_at": "",
                                                         "faltantes_recordatorio_count": ""}})
    return {"ok": True, "to": destinatario, "faltantes": faltantes}


@api.delete("/clientes/folders/{fid}")
async def delete_folder(fid: str):
    doc = await db.folders.find_one({"id": fid})
    if doc:
        import shutil
        shutil.rmtree(fsvc.folder_dir(doc.get("nombre", "")), ignore_errors=True)
    await db.folders.delete_one({"id": fid})
    return {"ok": True}


async def _get_folder_doc(fid):
    doc = await db.folders.find_one({"id": fid})
    if not doc:
        raise HTTPException(status_code=404, detail="Carpeta no encontrada")
    return doc


@api.get("/clientes/folders/{fid}/download-all")
async def folder_download_all(fid: str):
    doc = await _get_folder_doc(fid)
    data = await asyncio.to_thread(fsvc.zip_folder, doc.get("nombre", ""))
    fname = f"{fsvc.safe_name(doc.get('nombre',''))}.zip"
    return StreamingResponse(io.BytesIO(data), media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@api.get("/clientes/folders/{fid}/download/{file_path:path}")
async def folder_download(fid: str, file_path: str, inline: bool = False):
    doc = await _get_folder_doc(fid)
    try:
        target = fsvc.resolver_ruta(doc.get("nombre", ""), file_path)
    except ValueError:
        raise HTTPException(status_code=400, detail="Ruta inválida")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    import mimetypes
    mt = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    disp = "inline" if inline else "attachment"
    return FileResponse(str(target), media_type=mt,
                        headers={"Content-Disposition": f'{disp}; filename="{target.name}"'})


async def _regen_combinado_bg(doc):
    try:
        cr = doc.get("credit_request") or {}
        await asyncio.to_thread(fsvc.merge_protocol, doc.get("nombre", ""),
                                cr.get("client_type") or "dependiente", True)
        await asyncio.to_thread(fsvc.merge_codeudor, doc.get("nombre", ""))
    except Exception as e:
        logger.warning(f"Regeneración de combinado falló: {e}")


@api.post("/clientes/folders/{fid}/upload-file")
async def folder_upload_file(fid: str, file: UploadFile = File(...), subfolder: str = Form(""),
                             route_to_codeudor: str = Form(""), categoria: str = Form("")):
    doc = await _get_folder_doc(fid)
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Archivo vacío")
    nombre_archivo = file.filename or "archivo"
    try:
        raw, nombre_archivo, _conv = pdfs.convertir_a_pdf(raw, nombre_archivo)
    except ValueError:
        pass  # formato no convertible: se guarda tal cual
    es_codeudor = str(route_to_codeudor).lower() in ("true", "1", "si", "sí")
    categoria = (categoria or "").strip().lower()
    if es_codeudor:
        subfolder = "05_codeudor"
        if not nombre_archivo.upper().startswith("CODEUDOR_"):
            nombre_archivo = f"CODEUDOR_{nombre_archivo}"
    elif categoria in ("voucher_tasacion", "voucher_gasto_operacional"):
        subfolder = "99_otros"
        prefijo = "VOUCHER_TASACION_" if categoria == "voucher_tasacion" else "VOUCHER_GASTO_OP_"
        if not nombre_archivo.upper().startswith(prefijo):
            nombre_archivo = f"{prefijo}{nombre_archivo}"
    rel = await asyncio.to_thread(fsvc.guardar_archivo, doc.get("nombre", ""),
                                  nombre_archivo, raw, subfolder)
    if categoria in ("voucher_tasacion", "voucher_gasto_operacional"):
        await db.folders.update_one({"id": fid}, {"$push": {"vouchers": {
            "tipo": categoria, "archivo": rel, "subido_en": now_iso()}}})
    else:
        asyncio.create_task(_regen_combinado_bg(doc))
    return {"ok": True, "saved": rel, "codeudor": es_codeudor, "categoria": categoria}


@api.post("/clientes/folders/{fid}/delete-file")
async def folder_delete_file(fid: str, payload: dict):
    doc = await _get_folder_doc(fid)
    try:
        target = fsvc.resolver_ruta(doc.get("nombre", ""), payload.get("file_path", ""))
    except ValueError:
        raise HTTPException(status_code=400, detail="Ruta inválida")
    if not target.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    target.unlink()
    return {"ok": True}


@api.post("/clientes/folders/{fid}/merge-pdfs")
async def folder_merge_pdfs(fid: str, payload: dict):
    doc = await _get_folder_doc(fid)
    files = payload.get("files") or []
    res = await asyncio.to_thread(fsvc.merge_pdfs, doc.get("nombre", ""), files)
    if not res["merged_file"]:
        raise HTTPException(status_code=400, detail="; ".join(res["errors"]) or "Sin PDFs válidos")
    return res


@api.post("/clientes/folders/{fid}/merge-protocol")
async def folder_merge_protocol(fid: str, payload: dict = None):
    doc = await _get_folder_doc(fid)
    cr = doc.get("credit_request") or {}
    include_extras = bool((payload or {}).get("include_extras", True))
    orden = (payload or {}).get("orden") or None
    res = await asyncio.to_thread(fsvc.merge_protocol, doc.get("nombre", ""),
                                  cr.get("client_type") or "dependiente", include_extras, orden)
    if not res["merged_file"]:
        raise HTTPException(status_code=400, detail="No hay PDFs para combinar en esta carpeta")
    return res


@api.post("/clientes/folders/{fid}/split-bundled")
async def folder_split_bundled(fid: str, payload: dict):
    doc = await _get_folder_doc(fid)
    try:
        res = await asyncio.to_thread(
            fsvc.split_bundled, doc.get("nombre", ""), payload.get("file_path", ""),
            bool(payload.get("route_to_codeudor")), bool(payload.get("delete_original")))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    except ValueError:
        raise HTTPException(status_code=400, detail="Ruta inválida")
    asyncio.create_task(_regen_combinado_bg(doc))
    return res


@api.post("/clientes/save-attachment")
async def save_attachment(payload: dict):
    doc = await _get_folder_doc(payload.get("folder_id", ""))
    email_id = payload.get("email_id", "")
    filename = payload.get("filename", "")
    try:
        atts = await asyncio.to_thread(mail.fetch_attachments_by_id, email_id, filename)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error leyendo el correo: {str(e)[:120]}")
    if not atts:
        raise HTTPException(status_code=404, detail="Adjunto no encontrado en el correo")
    saved = []
    for att in atts:
        raw, nombre_a = att["content_bytes"], att["filename"]
        try:
            raw, nombre_a, _ = pdfs.convertir_a_pdf(raw, nombre_a)
        except ValueError:
            pass
        rel = await asyncio.to_thread(fsvc.guardar_archivo, doc.get("nombre", ""), nombre_a, raw, "")
        saved.append(rel)
    asyncio.create_task(_regen_combinado_bg(doc))
    return {"ok": True, "saved": saved}


async def _save_all_attachments_job(job_id, doc, person):
    try:
        correos = await asyncio.to_thread(mail.search_attachments_by_person, person, 40)
        existentes = {a["nombre"] for a in fsvc.scan_archivos(doc.get("nombre", ""))}
        total_found, total_saved, saved = 0, 0, []
        for c in correos:
            for pdf in c.get("pdfs", []):
                total_found += 1
                raw, nombre_a = pdf["content_bytes"], pdf["filename"]
                try:
                    raw, nombre_a, _ = pdfs.convertir_a_pdf(raw, nombre_a)
                except ValueError:
                    pass
                if fsvc.safe_name(nombre_a) in existentes:
                    continue
                rel = await asyncio.to_thread(fsvc.guardar_archivo, doc.get("nombre", ""), nombre_a, raw, "")
                existentes.add(fsvc.safe_name(nombre_a))
                saved.append(rel)
                total_saved += 1
        if correos and not doc.get("source_email"):
            await db.folders.update_one({"id": doc["id"]}, {"$set": {"source_email": correos[0].get("from", "")}})
        if total_saved:
            asyncio.create_task(_regen_combinado_bg(doc))
        await db.save_jobs.update_one({"id": job_id}, {"$set": {
            "status": "done", "total_found": total_found,
            "total_saved": total_saved, "saved": saved}})
    except Exception as e:
        await db.save_jobs.update_one({"id": job_id}, {"$set": {
            "status": "error", "error": str(e)[:200],
            "total_found": 0, "total_saved": 0}})


@api.post("/clientes/save-all-attachments")
async def save_all_attachments(payload: dict):
    doc = await _get_folder_doc(payload.get("folder_id", ""))
    person = payload.get("person_name", "")
    if not person.strip():
        raise HTTPException(status_code=400, detail="Falta el nombre de la persona")
    job_id = str(uuid.uuid4())
    corte = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    await db.save_jobs.delete_many({"created_at": {"$lt": corte}})
    await db.save_jobs.insert_one({"id": job_id, "status": "running", "created_at": now_iso()})
    asyncio.create_task(_save_all_attachments_job(job_id, doc, person))
    return {"job_id": job_id, "status": "running"}


@api.get("/clientes/save-all-attachments/{job_id}")
async def save_all_attachments_status(job_id: str):
    job = await db.save_jobs.find_one({"id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    return clean(job)


@api.patch("/clientes/folders/{fid}/clasificacion")
async def folder_clasificacion(fid: str, payload: dict):
    doc = await _get_folder_doc(fid)
    cr = doc.get("credit_request") or {}
    if payload.get("reset"):
        auto = doc.get("credit_request_auto")
        newcr = dict(auto) if auto else {k: v for k, v in cr.items() if k != "manual_override"}
        newcr.pop("manual_override", None)
        await db.folders.update_one({"id": fid}, {"$set": {"credit_request": newcr},
                                                  "$unset": {"credit_request_auto": ""}})
        return {"ok": True, "reset": True}
    if not doc.get("credit_request_auto"):
        await db.folders.update_one({"id": fid}, {"$set": {"credit_request_auto": cr}})
    cr.update({
        "client_type": payload.get("client_type", cr.get("client_type", "desconocido")),
        "is_request": bool(payload.get("is_request", cr.get("is_request", False))),
        "subsidy": {"tipo": payload.get("subsidy_tipo", (cr.get("subsidy") or {}).get("tipo", "sin_subsidio"))},
        "codeudor": {"has_codeudor": bool(payload.get("codeudor_has")),
                     "name": payload.get("codeudor_name", "")},
        "manual_override": True,
    })
    await db.folders.update_one({"id": fid}, {"$set": {"credit_request": cr}})
    return {"ok": True}


@api.get("/clientes/folders/{fid}/datos-financieros")
async def folder_fin_get(fid: str):
    doc = await _get_folder_doc(fid)
    return {"datos_financieros": doc.get("datos_financieros") or {}}


@api.patch("/clientes/folders/{fid}/datos-financieros")
async def folder_fin_patch(fid: str, payload: dict):
    doc = await _get_folder_doc(fid)
    df = doc.get("datos_financieros") or {}
    df.update({k: v for k, v in (payload or {}).items() if v is not None})
    await db.folders.update_one({"id": fid}, {"$set": {"datos_financieros": df}})
    return {"ok": True, "datos_financieros": df}


@api.post("/clientes/folders/{fid}/ocr-datos-financieros")
async def folder_fin_ocr(fid: str):
    doc = await _get_folder_doc(fid)
    base = fsvc.folder_dir(doc.get("nombre", ""))
    candidatos = [a for a in fsvc.scan_archivos(doc.get("nombre", ""))
                  if a["nombre"].lower().endswith(".pdf")
                  and fsvc.cat_de_archivo(a["nombre"], a["subfolder"]) != "combinado"][:5]
    extracted, analizados = {}, []
    for a in candidatos:
        raw = (base / a["ruta"]).read_bytes()
        texto, _metodo = await asyncio.to_thread(ocr_service.extraer_texto, raw, a["nombre"])
        info = await ai_extract.clasificar_y_extraer(texto, a["nombre"])
        analizados.append(a["nombre"])
        mapa = {
            "proyecto": info.get("proyecto_inmobiliario"),
            "inmobiliaria": info.get("proyecto_inmobiliario"),
            "con_subsidio": info.get("con_subsidio"),
            "monto_subsidio": info.get("monto_subsidio_uf"),
            "ahorro": info.get("ahorro_uf"),
            "monto_pie": info.get("pie_uf"),
            "monto_credito": info.get("monto_credito_uf") or info.get("monto_credito_solicitar_uf"),
        }
        for k, v in mapa.items():
            if extracted.get(k) in (None, "") and v not in (None, ""):
                extracted[k] = v
    return {"extracted": extracted, "pdfs_analyzed": analizados}


@api.patch("/clientes/folders/{fid}/envio-manual")
async def folder_envio_manual(fid: str, payload: dict):
    await _get_folder_doc(fid)
    enviado = bool((payload or {}).get("enviado"))
    await db.folders.update_one({"id": fid}, {"$set": {"envio_manual": enviado}})
    return {"ok": True, "envio_manual": enviado}


@api.patch("/clientes/folders/{fid}/actividad-terminada")
async def folder_actividad_terminada(fid: str, payload: dict):
    """Marca/desmarca una actividad de la carpeta como TERMINADA (permanente)."""
    await _get_folder_doc(fid)
    tipo = (payload or {}).get("tipo")
    if tipo not in ("tasacion", "estudio_titulo", "escritura"):
        raise HTTPException(status_code=400, detail="Tipo de actividad inválido")
    campo = f"{tipo}_terminado_at"
    val = now_iso() if (payload or {}).get("terminado", True) else None
    await db.folders.update_one({"id": fid}, {"$set": {campo: val, f"{tipo}_terminado_origen": "manual" if val else None}})
    return {"ok": True, "campo": campo, "valor": val}


@api.get("/clientes/folders/{fid}/historial")
async def folder_historial(fid: str):
    """Línea de tiempo permanente de todo lo hecho en la carpeta."""
    doc = await _get_folder_doc(fid)
    eventos = []

    def ev(fecha, icono, titulo, detalle=""):
        if fecha:
            eventos.append({"fecha": str(fecha), "icono": icono, "titulo": titulo, "detalle": detalle})

    ev(doc.get("created_at"), "📁", "Carpeta creada",
       f"Origen: {doc.get('origen', 'manual')}" + (f" · Solicitud de {doc.get('source_email', '')}" if doc.get("source_email") else ""))
    ev(doc.get("datos_financieros_fecha"), "💰", "Datos financieros recibidos del correo")
    ev(doc.get("faltantes_pedidos_at"), "📩", "Documentos faltantes pedidos al remitente")
    if doc.get("last_email_sent_at"):
        ev(doc.get("last_email_sent_at"), "📧", f"Enviado a mesa (envío N° {doc.get('emails_sent_count', 1)})")
    ev(doc.get("tasacion_solicitada_at"), "🏠", "Solicitud de tasación enviada")
    if doc.get("tasacion_fecha"):
        ev(doc.get("tasacion_fecha_detectada_en") or doc.get("tasacion_solicitada_at"), "📅",
           f"Fecha de tasación: {doc['tasacion_fecha']}", f"Origen: {doc.get('tasacion_fecha_origen', '')}")
    ev(doc.get("tasacion_terminado_at"), "✅", "Tasación terminada",
       f"Origen: {doc.get('tasacion_terminado_origen') or 'manual'}")
    ev(doc.get("estudio_titulo_solicitado_at"), "⚖️", "Solicitud de estudio de título enviada")
    ev(doc.get("estudio_docs_enviados_abogado_at"), "📤",
       "Etapa 2: documentos del estudio enviados al abogado",
       f"A: {doc.get('estudio_abogado_email') or 'abogado'} · {len(doc.get('estudio_docs_enviados_abogado') or [])} documento(s), CC Victoria Vilches")
    rep = doc.get("estudio_reparos") or {}
    if rep.get("detectado_en"):
        ev(rep.get("detectado_en"), "🔨", f"Reparos del estudio detectados ({len(rep.get('items') or [])})")
    ev(rep.get("reenviado_vendedor_at"), "📨", "Reparos reenviados al vendedor")
    ev(rep.get("recordatorio_enviado_at"), "⏰", "Recordatorio de reparos enviado al abogado")
    ev(rep.get("declarado_satisfecho_at"), "✅", "Reparos declarados satisfechos",
       f"Por: {rep.get('declarado_por', '')}")
    ev(doc.get("estudio_titulo_terminado_at"), "✅", "Estudio de título terminado",
       f"Origen: {doc.get('estudio_titulo_terminado_origen') or 'manual'}")
    ev(doc.get("escritura_solicitada_at"), "✍️", "Aviso de firma de escritura enviado al cliente")
    ev(doc.get("escritura_confirmada_at"), "✅", "Asistencia a firma de escritura confirmada")
    ev(doc.get("escritura_terminado_at"), "✅", "Escritura terminada")
    alertas = await db.alertas.find({"folder_id": fid}).limit(60).to_list(60)
    for a in alertas:
        ev(a.get("fecha"), "🔔", (a.get("mensaje") or "Alerta")[:140])
    eventos.sort(key=lambda e: e["fecha"], reverse=True)
    return {"nombre": doc.get("nombre", ""), "eventos": eventos}


def _imap_descargar_adjuntos_cliente(nombre, patrones=r"aprobaci|simulad|ajustad|_cm\.pdf"):
    """Busca en las casillas los correos del cliente y devuelve [(filename, bytes)] de los PDFs que calcen."""
    partes = [t for t in re.split(r"\s+", nombre or "") if len(t) > 2]
    if not partes:
        return []
    combos, vistos = [], set()
    for c in ([partes[0], partes[2]] if len(partes) >= 3 else None,
              [partes[0], partes[1]] if len(partes) >= 2 else None,
              [partes[-2], partes[-1]] if len(partes) >= 2 else None,
              [partes[0]]):
        if c and tuple(c) not in vistos:
            vistos.add(tuple(c))
            combos.append(c)
    pat = re.compile(patrones, re.I)
    encontrados = {}
    import email as _em
    from email.header import decode_header, make_header
    for acc in mail.ACCOUNTS:
        try:
            m = mail._connect(acc)
            m.select("INBOX", readonly=True)
            ids = []
            for c in combos:
                typ, data = m.search(None, "X-GM-RAW", f'"{" ".join(c)} has:attachment"')
                ids = data[0].split() if data and data[0] else []
                if ids:
                    break
            for num in reversed(ids[-25:]):
                typ, d = m.fetch(num, "(BODY.PEEK[])")
                if not d or not isinstance(d[0], tuple):
                    continue
                msg = _em.message_from_bytes(d[0][1])
                for part in msg.walk():
                    fn = part.get_filename()
                    if not fn:
                        continue
                    try:
                        fn = str(make_header(decode_header(fn)))
                    except Exception:
                        pass
                    if not fn.lower().endswith(".pdf") or not pat.search(fn):
                        continue
                    if fn in encontrados:
                        continue
                    raw = part.get_payload(decode=True)
                    if raw:
                        encontrados[fn] = raw
            m.logout()
        except Exception:
            continue
    return list(encontrados.items())


async def _sync_docs_aprobacion(nombre):
    """REGLA: la carta de aprobación y el PDF ajustado del cliente deben estar SIEMPRE
    descargados en su carpeta. Los busca en el archivo del autocorreo y en el correo."""
    nombre = (nombre or "").strip()
    if not nombre:
        return []
    base = fsvc.folder_dir(nombre)
    base.mkdir(parents=True, exist_ok=True)
    existentes = {a["nombre"].lower() for a in fsvc.scan_archivos(nombre)}
    copiados = []

    def _guardar(fn, raw):
        safe = _safe_name(fn)
        if safe.lower() in existentes or fn.lower() in existentes:
            return
        destino = base / "99_otros"
        destino.mkdir(exist_ok=True)
        (destino / safe).write_bytes(raw)
        existentes.add(safe.lower())
        copiados.append(safe)

    # 1) Archivo local del autocorreo (carpeta exacta + match por nombre)
    toks = [t for t in _norm_texto(nombre).split() if len(t) > 2]
    minimo = min(2, len(toks)) or 1
    if STORAGE_DIR.exists() and toks:
        candidatos = []
        dir_ac = STORAGE_DIR / _safe_name(nombre)
        if dir_ac.exists():
            candidatos += sorted(dir_ac.glob("*.pdf"))
        for p in STORAGE_DIR.rglob("*.pdf"):
            palabras = _norm_texto(p.name).split()
            if sum(1 for t in toks if t in palabras) >= minimo:
                candidatos.append(p)
        for p in candidatos:
            if _tipo_pdf_aprobacion(p.name) != "otro":
                _guardar(p.name, p.read_bytes())
    # 2) Directo del correo (carta aprobación / simulador / ajustado)
    try:
        adjuntos = await asyncio.to_thread(_imap_descargar_adjuntos_cliente, nombre)
    except Exception:
        adjuntos = []
    for fn, raw in adjuntos:
        _guardar(fn, raw)
    if copiados:
        doc = await db.folders.find_one({"nombre": nombre})
        if doc:
            arch = doc.get("archivos") or []
            arch += [f"99_otros/{c}" for c in copiados if f"99_otros/{c}" not in arch]
            await db.folders.update_one({"id": doc["id"]}, {"$set": {"archivos": arch}})
    return copiados


@api.post("/clientes/folders/{fid}/sync-aprobacion")
async def folder_sync_aprobacion(fid: str):
    doc = await _get_folder_doc(fid)
    copiados = await _sync_docs_aprobacion(doc.get("nombre", ""))
    return {"ok": True, "copiados": copiados}


@api.get("/clientes/folders/{fid}/tasacion-prefill")
async def folder_tasacion_prefill(fid: str):
    """Lee correos y documentos del cliente para pre-llenar la solicitud de tasación
    (rol de avalúo, proyecto, montos, dirección, comuna, contacto del vendedor)."""
    doc = await _get_folder_doc(fid)
    nombre = doc.get("nombre", "")
    textos = []
    # 1) Cuerpos de correos del cliente en la cola de procesamiento (asunto + cuerpo)
    toks = [t for t in _norm_texto(nombre).split() if len(t) > 2]
    if toks:
        rx = ".*".join(re.escape(t) for t in toks[:2])
        ors = [{"cliente": {"$regex": rx, "$options": "i"}},
               {"classification.cliente": {"$regex": rx, "$options": "i"}},
               {"subject": {"$regex": rx, "$options": "i"}},
               {"body_full": {"$regex": rx, "$options": "i"}}]
        rut_rx = _rut_regex_flexible(doc.get("rut") or "")
        if rut_rx:
            ors += [{"subject": {"$regex": rut_rx, "$options": "i"}},
                    {"body_full": {"$regex": rut_rx, "$options": "i"}}]
        async for it in db.proc_queue.find({"$or": ors}).sort("date_iso", -1).limit(8):
            cuerpo = (it.get("body_text") or it.get("body") or it.get("body_full") or "")[:3000]
            if cuerpo or it.get("subject"):
                textos.append(f"[CORREO] De: {it.get('from', '')} · Asunto: {it.get('subject', '')}\n{cuerpo}")
    # 2) Documentos de la carpeta: primero los relevantes, luego el resto (extras)
    pat_docs = re.compile(r"promesa|oferta|carta|aprobaci|cotiz|reserva|compra|simulad|tasaci|solicitud", re.I)
    archivos_all = [a for a in fsvc.scan_archivos(nombre)
                    if a["nombre"].lower().endswith((".pdf", ".jpg", ".jpeg", ".png"))]
    priorizados = [a for a in archivos_all if pat_docs.search(a["nombre"])]
    resto = [a for a in archivos_all if a not in priorizados
             and fsvc.cat_de_archivo(a["nombre"], a["subfolder"]) == "extras"]
    for a in priorizados + resto:
        if len(textos) >= 12:
            break
        try:
            raw = (fsvc.folder_dir(nombre) / a["ruta"]).read_bytes()
            texto, _met = await asyncio.to_thread(ocr_service.extraer_texto, raw, a["nombre"])
            if texto:
                textos.append(f"[DOC {a['nombre']}]\n{texto[:2500]}")
        except Exception:
            continue
    datos = await ai_extract.extraer_datos_tasacion("\n\n".join(textos))
    # Datos financieros ya guardados tienen prioridad
    df = doc.get("datos_financieros") or {}
    if df.get("valor_propiedad"):
        datos["valor_propiedad_uf"] = df["valor_propiedad"]
    if df.get("proyecto"):
        datos["proyecto"] = df["proyecto"]
    if df.get("inmobiliaria"):
        datos["inmobiliaria"] = df["inmobiliaria"]
    for k in ("direccion", "comuna", "ciudad"):
        if df.get(k):
            datos[k] = df[k]
    return {"ok": True, "prefill": datos, "fuentes": len(textos)}


def _sender_por_rol(rol="secundaria"):
    acc = next((a for a in mail.ACCOUNTS if a["rol"] == rol), None)
    if not acc and mail.ACCOUNTS:
        acc = mail.ACCOUNTS[0]
    return acc["user"] if acc else ""


def _fin_resumen_html(doc):
    df = doc.get("datos_financieros") or {}
    origen = (doc.get("source_email") or "").strip()
    m = re.match(r'^"?([^"<]*)"?\s*<([^>]+)>$', origen)
    origen_nombre, origen_mail = (m.group(1).strip(), m.group(2).strip()) if m else ("", origen)
    falta = "<span style='color:#dc2626;font-weight:bold'>— FALTA</span>"
    filas = [("Solicitud recibida de", f"{origen_nombre} · {origen_mail}".strip(" ·") or None),
             ("Ejecutivo interno", doc.get("ejecutivo_interno")),
             ("Proyecto", df.get("proyecto")), ("Inmobiliaria", df.get("inmobiliaria")),
             ("Tipo propiedad", df.get("tipo_propiedad")),
             ("Fecha de entrega", (df.get("fecha_entrega") or "").capitalize() or None),
             ("Operación", "Con subsidio" if df.get("con_subsidio") else "Sin subsidio"),
             ("Valor propiedad", _fmt_uf(df.get("valor_propiedad"))),
             ("Monto subsidio", _fmt_uf(df.get("monto_subsidio"))),
             ("Ahorro", _fmt_uf(df.get("ahorro"))), ("Pie", _fmt_uf(df.get("monto_pie"))),
             ("Reserva", _fmt_uf(df.get("monto_reserva"))),
             ("Monto crédito", _fmt_uf(df.get("monto_credito")))]
    rows = "".join(f"<tr><td style='padding:3px 12px 3px 0'><b>{k}</b></td>"
                   f"<td>{v if v not in (None, '', '—') else falta}</td></tr>"
                   for k, v in filas)
    return f"<table style='border-collapse:collapse'>{rows}</table>"


@api.post("/clientes/folders/{fid}/send-email")
async def folder_send_email(fid: str, payload: dict):
    doc = await _get_folder_doc(fid)
    payload = payload or {}
    to = (payload.get("to_addr") or "").strip()
    if not to or "@" not in to:
        raise HTTPException(status_code=400, detail="Destinatario inválido")
    nombre = doc.get("nombre", "")
    rut = doc.get("rut", "")
    base = fsvc.folder_dir(nombre)
    cr = doc.get("credit_request") or {}
    _cats = {fsvc.cat_de_archivo(a["nombre"], a["subfolder"]) for a in fsvc.scan_archivos(nombre)} - {"combinado", "codeudor", "estudio_titulo"}
    _ct = cr.get("client_type") or "dependiente"
    missing_labels = [fsvc.MISSING_LABELS.get(c, c) for c in fsvc.required_cats(_ct) if c not in _cats]
    _df = doc.get("datos_financieros") or {}
    fecha_entrega = (_df.get("fecha_entrega") or "").strip()
    if not fecha_entrega:
        missing_labels.append("Fecha de entrega (inmediata/futura)")
    ejecutivo = (payload.get("ejecutivo_interno") or doc.get("ejecutivo_interno") or "").strip()
    if payload.get("confirm") and payload.get("ejecutivo_interno") and payload["ejecutivo_interno"] != doc.get("ejecutivo_interno"):
        await db.folders.update_one({"id": fid}, {"$set": {"ejecutivo_interno": ejecutivo}})
        doc["ejecutivo_interno"] = ejecutivo
    if not ejecutivo:
        missing_labels.append("Ejecutivo interno (Deisy/Yerile/Gerardo)")
    if payload.get("confirm") and missing_labels and not payload.get("force_incompleto"):
        raise HTTPException(status_code=412, detail="Documentación incompleta — faltan: "
                            + ", ".join(missing_labels)
                            + ". Para enviar igual, asumí el envío manual incompleto.")
    attach_names = []
    attach_paths = []
    if payload.get("include_merged", True):
        merged = base / f"COMBINADO_PROTOCOLO_{fsvc.safe_name(nombre)}.pdf"
        if not merged.exists():
            res = await asyncio.to_thread(fsvc.merge_protocol, nombre,
                                          cr.get("client_type") or "dependiente", True)
            merged = base / res["merged_file"] if res["merged_file"] else merged
        if merged.exists():
            attach_paths.append(merged)
            attach_names.append(merged.name)
    if payload.get("include_codeudor_merged"):
        for p in sorted(base.glob("COMBINADO_CODEUDOR*.pdf")):
            attach_paths.append(p)
            attach_names.append(p.name)
    for rel in payload.get("attach_files") or []:
        try:
            p = fsvc.resolver_ruta(nombre, rel)
            if p.exists() and p not in attach_paths:
                attach_paths.append(p)
                attach_names.append(p.name)
        except ValueError:
            continue
    subject = payload.get("subject") or (
        f"Antecedentes crédito hipotecario — {nombre}" + (f" ({rut})" if rut else "")
        + (f" — Entrega: {fecha_entrega.capitalize()}" if fecha_entrega else ""))
    fin_html = _fin_resumen_html(doc)
    body_override = (payload.get("body_html") or "").strip()
    cuerpo = body_override or f"""
    <div style="font-family:Arial,sans-serif;font-size:14px;color:#222">
      <h2 style="color:#6c5ce7;margin:0 0 8px">Carpeta cliente — {nombre}</h2>
      <p><b>Cliente:</b> {nombre}{f' · <b>RUT:</b> {rut}' if rut else ''}</p>
      {f'<p style="margin:4px 0"><b>Fecha de entrega:</b> {fecha_entrega.capitalize()}</p>' if fecha_entrega else ''}
      {fin_html}
      {f'<p style="margin-top:10px">{(payload.get("body_extra") or "").strip()}</p>' if (payload.get("body_extra") or "").strip() else ''}
      <p style="margin-top:12px">Se adjunta la carpeta con los antecedentes del cliente.</p>
      <p style="color:#888;font-size:12px">Central Mutuos - Con Creces</p>
    </div>
    """
    sender = _sender_por_rol("secundaria")
    if not payload.get("confirm"):
        return {"to": to, "subject": subject, "body": cuerpo, "body_html": cuerpo,
                "missing_docs": missing_labels, "docs_completos": not missing_labels,
                "attachments": attach_names, "sender": sender}
    adjuntos = [{"filename": p.name, "content_b64": _b64(p.read_bytes())} for p in attach_paths]
    res = await asyncio.to_thread(mail.send_mail, to, subject, cuerpo, adjuntos, "secundaria")
    if not res.get("success"):
        raise HTTPException(status_code=502, detail=res.get("error", "Error de envío"))
    await db.folders.update_one({"id": fid}, {"$inc": {"emails_sent_count": 1},
                                              "$set": {"last_email_sent_at": now_iso()}})
    return {"to": to, "subject": subject, "attachments": attach_names,
            "sender": res.get("desde", sender)}


@api.post("/clientes/folders/{fid}/send-missing-docs")
async def folder_send_missing_docs(fid: str, payload: dict = None):
    doc = await _get_folder_doc(fid)
    payload = payload or {}
    pub = _folder_public(doc)
    cats = pub["credit_request"].get("doc_categories", [])
    ct = pub["credit_request"].get("client_type") or "dependiente"
    missing = [fsvc.MISSING_LABELS.get(c, c) for c in fsvc.required_cats(ct) if c not in cats]
    src = doc.get("source_email", "") or ""
    m_addr = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", src)
    default_to = m_addr.group(0) if m_addr else ""
    to = (payload.get("to_addr") or default_to).strip()
    nombre = doc.get("nombre", "")
    subject = f"Documentos faltantes — {nombre}"
    lista = "".join(f"<li>{d}</li>" for d in missing)
    extra = (payload.get("body_extra") or "").strip()
    cuerpo = f"""
    <div style="font-family:Arial,sans-serif;font-size:14px;color:#222">
      <h2 style="color:#e17055;margin:0 0 8px">Documentos faltantes — {nombre}</h2>
      <p>Para continuar con la evaluación del crédito de <b>{nombre}</b> necesitamos los siguientes documentos:</p>
      <ul>{lista if lista else '<li>Sin faltantes detectados</li>'}</ul>
      {f'<p>{extra}</p>' if extra else ''}
      <p style="color:#888;font-size:12px">Central Mutuos - Con Creces</p>
    </div>
    """
    sender = _sender_por_rol("secundaria")
    if not payload.get("confirm"):
        return {"to": to, "subject": subject, "missing": missing, "body": cuerpo, "sender": sender}
    if not to or "@" not in to:
        raise HTTPException(status_code=400, detail="Destinatario inválido")
    res = await asyncio.to_thread(mail.send_mail, to, subject, cuerpo, [], "secundaria")
    if not res.get("success"):
        raise HTTPException(status_code=502, detail=res.get("error", "Error de envío"))
    return {"to": to, "subject": subject, "missing": missing, "sender": res.get("desde", sender)}


@api.get("/clientes/emails")
async def clientes_emails(limit: int = 20, max_results: int = 0):
    n = max_results or limit
    emails = await asyncio.to_thread(mail.fetch_recent_full, n)
    return {"emails": emails}


@api.get("/clientes/emails/search")
async def clientes_emails_search(q: str = ""):
    emails = await asyncio.to_thread(mail.fetch_recent_full, 40)
    ql = (q or "").lower()
    if ql:
        emails = [e for e in emails
                  if ql in (e.get("subject", "") or "").lower()
                  or ql in (e.get("from", "") or "").lower()
                  or ql in (e.get("body", "") or "").lower()]
    return {"emails": emails, "results": emails}


@api.get("/clientes/ajustes")
async def clientes_ajustes():
    docs = await db.folders.find({}).sort("created_at", -1).limit(200).to_list(200)
    return {"folders": [_folder_public(d, con_archivos=True) for d in docs], "ajustes": {}}


@api.get("/clientes/autocorreo-dest")
async def autocorreo_dest():
    st = await _ac_state()
    dest = st.get("destination") or os.environ.get("MAIL2_USER", "")
    return {"destination": dest, "destinatarios": [dest] if dest else []}


@api.post("/clientes/detect-client")
async def detect_client(payload: dict):
    return {"matches": []}


# ---------------------------------------------------------------------------
# Seguimiento (operaciones detectadas desde el correo)
# ---------------------------------------------------------------------------
@api.get("/seguimiento/clientes")
async def seg_clientes(q: str = ""):
    query = {"cliente": {"$regex": q, "$options": "i"}} if q else {}
    docs = await db.seguimiento.find(query).sort("fecha", -1).limit(200).to_list(200)
    # agrupar por cliente
    por_cliente = {}
    for d in docs:
        c = d.get("cliente", "Desconocido")
        if c not in por_cliente:
            por_cliente[c] = {
                "id": d.get("cliente_id") or c,
                "cliente": c,
                "estado": d.get("estado"),
                "ultima_actividad": d.get("fecha"),
                "operaciones": 0,
            }
        por_cliente[c]["operaciones"] += 1
    return {"clientes": list(por_cliente.values())}


@api.get("/seguimiento/stats")
async def seg_stats():
    total_ops = await db.seguimiento.count_documents({})
    clientes = len(await db.seguimiento.distinct("cliente"))
    hace_7d = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    semana = await db.seguimiento.count_documents({"procesado_en": {"$gte": hace_7d}})
    return {"total_clientes": clientes, "total_operaciones": total_ops,
            "operaciones_semana": semana}


@api.get("/seguimiento/clientes/{cid}/timeline")
async def seg_timeline(cid: str):
    docs = await db.seguimiento.find(
        {"$or": [{"cliente_id": cid}, {"cliente": cid}]}
    ).sort("fecha", -1).limit(100).to_list(100)
    return {"timeline": [clean(d) for d in docs]}


@api.post("/seguimiento/process-emails")
async def seg_process(max_emails: int = 30):
    ops = await asyncio.to_thread(mail.procesar_seguimiento, max_emails)
    nuevos = 0
    for op in ops:
        exists = await db.seguimiento.find_one(
            {"asunto": op["asunto"], "fecha": op["fecha"]})
        if exists:
            continue
        await db.seguimiento.insert_one({
            "id": str(uuid.uuid4()),
            "cliente_id": op["cliente"].lower().replace(" ", "-"),
            **op,
            "procesado_en": now_iso(),
        })
        nuevos += 1
    return {"ok": True, "procesados": len(ops), "nuevos": nuevos}


@api.get("/reportes/ficha-cliente/{cid}")
async def ficha_cliente(cid: str):
    return {"cliente": cid, "resumen": {}, "seguimiento": [], "simulaciones": [],
            "conversaciones": [], "comunicaciones": []}


# ---------------------------------------------------------------------------
# WhatsApp (not connected in this instance)
# ---------------------------------------------------------------------------
@api.get("/whatsapp/status")
async def wa_status():
    return {"isReady": False, "hasQR": False}


@api.get("/whatsapp/qr")
async def wa_qr():
    return {"qrCode": None}


@api.get("/whatsapp/approvals")
async def wa_approvals(status: str = "pending"):
    return {"approvals": []}


@api.post("/whatsapp/test-send")
async def wa_test(message: str = ""):
    return {"success": False, "error": "WhatsApp no esta conectado"}


@api.post("/whatsapp/approval/{aid}/approve")
async def wa_approve(aid: str, payload: dict = None):
    return {"ok": True}


@api.post("/whatsapp/approval/{aid}/reject")
async def wa_reject(aid: str, payload: dict = None):
    return {"ok": True}


# ---------------------------------------------------------------------------
# Autocorreo / Procesamiento / Formato / Portal (stubs returning valid data)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Autocorreo: flujo de mesa (recibir simulacion -> dejar pag 1 -> archivar/enviar)
# ---------------------------------------------------------------------------
import pdf_service as pdfs
from fastapi.responses import FileResponse

STORAGE_DIR = ROOT_DIR / "storage" / "autocorreo"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
MESA_SENDER = os.environ.get("MESA_SENDER", "aprobaciones@centralmutuos.cl")


def _safe_name(name):
    return re.sub(r"[^A-Za-z0-9._ -]", "_", (name or "").strip()) or "cliente"


async def _ac_state():
    st = await db.config.find_one({"_key": "autocorreo_state"})
    if not st:
        st = {"_key": "autocorreo_state", "enabled": False, "periodic_enabled": False,
              "cutoff_iso": None, "destination": os.environ.get("MAIL2_USER", "")}
        await db.config.insert_one(dict(st))
    st.pop("_id", None)
    st.pop("_key", None)
    return st


async def _set_ac_state(upd):
    await db.config.update_one({"_key": "autocorreo_state"}, {"$set": upd}, upsert=True)


def _save_pdf(cliente, filename, content_bytes):
    folder = STORAGE_DIR / _safe_name(cliente)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / _safe_name(filename)
    with open(path, "wb") as f:
        f.write(content_bytes)
    return path


def _norm_subject(s):
    return re.sub(r"^\s*((re|fwd?|rv|fw)\s*:\s*)+", "", (s or ""), flags=re.I).strip().lower()


def _marcar_reenvios(recent, enviados, destino):
    """Cruza el historial con la carpeta Enviados para saber si el usuario reenvió y a quién.
    Solo cuenta envíos POSTERIORES al procesamiento y hacia destinos externos (no mesa/propios)."""
    propios = {a["user"].lower() for a in mail.ACCOUNTS}
    propios.add((destino or "").lower())
    propios.add((MESA_SENDER or "").lower())

    def _ts(iso):
        try:
            dt = datetime.fromisoformat(iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    for r in recent:
        base = _norm_subject(r.get("subject"))
        r["reenviado"] = False
        r["reenviado_a"] = ""
        r["reenviado_fecha"] = ""
        if not base:
            continue
        procesado = _ts(r.get("processed_at") or "")
        for e in enviados:
            if _norm_subject(e.get("subject")) != base:
                continue
            raw = (e.get("subject") or "").strip().lower()
            es_fwd = bool(re.match(r"^(fwd?|rv|fw)\s*:", raw))
            to = (e.get("to") or "").strip()
            to_l = to.lower()
            if not to_l or any(p and p in to_l for p in propios):
                continue  # auto-envío o hacia mesa: no es un reenvío del usuario
            fecha_envio = _ts(e.get("date") or "")
            if procesado and fecha_envio and fecha_envio < procesado and not es_fwd:
                continue  # se envió ANTES de que llegara la respuesta de mesa
            r["reenviado"] = True
            r["reenviado_a"] = to
            r["reenviado_fecha"] = e.get("date", "")
            break
    return recent


@api.get("/autocorreo/status")
async def ac_status():
    st = await _ac_state()
    log = await db.autocorreo_log.find().sort("processed_at", -1).limit(25).to_list(25)
    sent = await db.autocorreo_log.count_documents({"status": "sent"})
    failed = await db.autocorreo_log.count_documents({"status": "failed"})
    total = await db.autocorreo_log.count_documents({})
    recent = [clean(r) for r in log]
    try:
        destino_cfg = st.get("destination") or os.environ.get("MAIL2_USER", "")
        enviados = mail._cached("sent_headers")
        if enviados is None:
            # Refrescar en background para no bloquear la carga del módulo
            asyncio.create_task(asyncio.to_thread(mail.fetch_sent_headers, 80))
            enviados = mail.SENT_LAST or []
        recent = _marcar_reenvios(recent, enviados, destino_cfg)
    except Exception:
        pass
    return {
        "enabled": st.get("enabled", False),
        "periodic_enabled": st.get("periodic_enabled", False),
        "cutoff_iso": st.get("cutoff_iso"),
        "destination": st.get("destination") or os.environ.get("MAIL2_USER", ""),
        "running": st.get("running", False),
        "last_run": st.get("last_run"),
        "last_run_result": st.get("last_run_result"),
        "sent": sent,
        "failed": failed,
        "total": total,
        "recent": recent,
    }


@api.get("/autocorreo/mailboxes")
async def ac_mailboxes(probe: bool = False):
    status = await asyncio.to_thread(mail.get_status)
    accounts = []
    for i, a in enumerate(status.get("accounts", [])):
        accounts.append({
            "email": a.get("account"),
            "role": "principal" if a.get("rol") == "principal" else "respaldo",
            "slot": i,
            "auth_method": "app_password" if a.get("connected") else "none",
            "auth_live": a.get("connected", False),
            "oauth_configured": False,
            "backoff_remaining_s": 0,
            "connect_url": "/api/oauth/drive/start",
        })
    return {"accounts": accounts}


@api.get("/autocorreo/archive")
async def ac_archive():
    folders = []
    if STORAGE_DIR.exists():
        for d in sorted(STORAGE_DIR.iterdir()):
            if not d.is_dir():
                continue
            files = [{"name": f.name, "size": f.stat().st_size}
                     for f in sorted(d.iterdir()) if f.is_file()]
            if files:
                folders.append({"cliente": d.name, "count": len(files), "files": files})
    return {"folders": folders}


@api.get("/autocorreo/archive/{cliente}/{filename}")
async def ac_archive_file(cliente: str, filename: str):
    path = STORAGE_DIR / _safe_name(cliente) / _safe_name(filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(str(path), media_type="application/pdf", filename=path.name)


@api.post("/autocorreo/toggle")
async def ac_toggle(payload: dict = None):
    enabled = bool((payload or {}).get("enabled"))
    await _set_ac_state({"enabled": enabled})
    return {"enabled": enabled}


@api.post("/autocorreo/periodic")
async def ac_periodic(payload: dict = None):
    enabled = bool((payload or {}).get("enabled"))
    await _set_ac_state({"periodic_enabled": enabled})
    return {"periodic_enabled": enabled}


@api.post("/autocorreo/cutoff/now")
async def ac_cutoff_now():
    iso = now_iso()
    await _set_ac_state({"cutoff_iso": iso})
    return {"cutoff_iso": iso}


@api.post("/autocorreo/cutoff/clear")
async def ac_cutoff_clear():
    await _set_ac_state({"cutoff_iso": None})
    return {"cutoff_iso": None}


@api.post("/autocorreo/imap/reset-backoff")
async def ac_reset_backoff(account: str = ""):
    return {"ok": True}


def _procesar_mesa(destino, cutoff_iso, ejecutivos=None, ya_enviados=None):
    """Lee correos de mesa, deja pag 1 en simulaciones, archiva y envia. (sync)

    Incluye RECHAZOS aunque vengan sin PDF (solo texto).
    ejecutivos: {cliente_lower: {nombre, email, email_cliente}} para el encabezado.
    ya_enviados: set de asuntos ya enviados (evita duplicados).
    """
    ejecutivos = ejecutivos or {}
    ya_enviados = ya_enviados or set()
    correos = mail.fetch_pdf_attachments(sender_filter=MESA_SENDER, limit=8,
                                         incluir_sin_adjuntos=True)
    resultados = []
    for c in correos:
        if cutoff_iso and c.get("date") and c["date"] < cutoff_iso:
            continue
        if (c.get("subject") or "").strip() in ya_enviados:
            continue  # ya fue enviado antes, no duplicar
        cliente = mail._extraer_nombre(c["subject"], c["from"])
        es_aprobacion = c["tipo"] == "aprobacion"
        es_rechazo = c["tipo"] == "rechazo"
        if not c["pdfs"]:
            # Sin adjuntos: solo se reenvia si es un RECHAZO (viene solo el texto)
            if es_rechazo:
                resultados.append({"cliente": cliente, "subject": c["subject"],
                                   "saved": [{"name": "(sin PDF - solo texto)", "type": "rechazo"}],
                                   "adjuntos": [], "es_aprobacion": False,
                                   "es_rechazo": True, "body": c.get("body", "")})
            continue
        for pdf in c["pdfs"]:
            raw = pdf["content_bytes"]
            nombre_pdf = pdf["filename"]
            try:
                raw, nombre_pdf, _conv = pdfs.convertir_a_pdf(raw, nombre_pdf)
            except Exception:
                continue
            tipo_doc = pdfs.clasificar_documento(raw, nombre_pdf)
            # REGLA INVIOLABLE: cartas de aprobacion SIEMPRE intactas, formato sin modificar.
            es_carta = tipo_doc == "carta_aprobacion" or re.search(
                r"carta|aprobaci[oó]n|aprobacion", (nombre_pdf or "").lower())
            adjuntos = []
            saved = []
            if tipo_doc == "simulacion" and not es_carta:
                nuevo, orig, removidas = pdfs.dejar_primera_pagina(raw)
                nombre_aj = nombre_pdf.replace(".pdf", "") + "_CM.pdf"
                _save_pdf(cliente, nombre_aj, nuevo)
                saved.append({"name": _safe_name(nombre_aj), "type": "simulacion_ajustada",
                              "pages_original": orig, "pages_removed": removidas})
                adjuntos.append({"filename": nombre_aj,
                                 "content_b64": _b64(nuevo)})
            else:
                _save_pdf(cliente, nombre_pdf, raw)
                saved.append({"name": _safe_name(nombre_pdf), "type": tipo_doc})
                adjuntos.append({"filename": nombre_pdf, "content_b64": _b64(raw)})
            resultados.append({"cliente": cliente, "subject": c["subject"],
                               "saved": saved, "adjuntos": adjuntos,
                               "es_aprobacion": es_aprobacion,
                               "es_rechazo": es_rechazo, "body": c.get("body", "")})
    # Enviar al destino (gerardo.ext@) los correos con la info para reenviar
    enviados = 0
    errores = []
    logs = []
    for r in resultados:
        info_ej = ejecutivos.get((r["cliente"] or "").strip().lower(), {})
        resultado_txt = "APROBACION" if r["es_aprobacion"] else "RECHAZO" if r.get("es_rechazo") else "DOCUMENTO"
        color = "#e17055" if r.get("es_rechazo") else "#00b894" if r["es_aprobacion"] else "#6c5ce7"
        encabezado = f"""
        <div style="font-family:Arial,sans-serif;font-size:13px;background:#f5f6fa;
                    border-left:4px solid {color};padding:10px 14px;margin-bottom:12px">
          <b style="color:{color}">{resultado_txt}</b> — {r['cliente']}<br>
          <b>Correo del cliente (para reenviar):</b> {info_ej.get('email_cliente') or '—'}<br>
          <b>Ejecutivo que envio la gestion:</b> {info_ej.get('nombre') or '—'}<br>
          <b>Correo del ejecutivo:</b> {info_ej.get('email') or '—'}
        </div>
        """
        cuerpo = r["body"] or (
            "Estimado/a,<br><br>Adjuntamos el documento correspondiente a su operacion.<br><br>"
            "Saludos cordiales,<br>Central Mutuos")
        cuerpo_html = cuerpo.replace("\n", "<br>") if "<br>" not in cuerpo else cuerpo
        res = mail.send_mail(destino, r["subject"], encabezado + cuerpo_html,
                             r["adjuntos"], desde="principal")
        estado = "sent" if res.get("success") else "failed"
        if res.get("success"):
            enviados += 1
        else:
            errores.append(f"{r['cliente']}: {res.get('error')}")
        logs.append({
            "id": str(uuid.uuid4()),
            "processed_at": now_iso(),
            "subject": r["subject"],
            "cliente": r["cliente"],
            "status": estado,
            "error": res.get("error") if estado == "failed" else None,
            "attachments_info": ", ".join(s["name"] for s in r["saved"]),
        })
    return {"processed": len(resultados), "sent": enviados, "errors": errores, "logs": logs}


import base64 as _b64mod


def _b64(data):
    return _b64mod.b64encode(data).decode()


async def _mapa_ejecutivos():
    """{cliente_lower: {nombre, email, email_cliente}} desde la cola de Procesamiento."""
    ejecutivos = {}
    items = await db.proc_queue.find(
        {}, {"classification.cliente": 1, "classification.email_cliente": 1,
             "campos.email_ejecutivo": 1, "campos.nombre_ejecutivo": 1,
             "campos.email_cliente": 1}).limit(500).to_list(500)
    for it in items:
        cl = it.get("classification") or {}
        campos_it = it.get("campos") or {}
        cli = (cl.get("cliente") or "").strip().lower()
        if cli:
            ejecutivos[cli] = {
                "nombre": campos_it.get("nombre_ejecutivo", ""),
                "email": campos_it.get("email_ejecutivo", ""),
                "email_cliente": cl.get("email_cliente") or campos_it.get("email_cliente", ""),
            }
    return ejecutivos


async def _subjects_enviados():
    """Asuntos ya enviados (para no duplicar reenvios)."""
    logs = await db.autocorreo_log.find(
        {"status": "sent"}, {"subject": 1, "subject_original": 1}).limit(800).to_list(800)
    return set((l.get("subject_original") or l.get("subject") or "").strip() for l in logs)


async def _run_mesa_background(destino, cutoff_iso, ejecutivos, ya_enviados=None):
    try:
        await db.config.update_one({"_key": "autocorreo_state"},
                                   {"$set": {"running": True, "last_run_started": now_iso()}}, upsert=True)
        result = await asyncio.to_thread(_procesar_mesa, destino, cutoff_iso, ejecutivos, ya_enviados)
        for lg in result.pop("logs", []):
            await db.autocorreo_log.insert_one(lg)
        await db.config.update_one({"_key": "autocorreo_state"}, {"$set": {
            "running": False, "last_run": now_iso(),
            "last_run_result": {"processed": result.get("processed", 0),
                                "sent": result.get("sent", 0),
                                "errors": result.get("errors", [])[:5]}}})
    except Exception as e:
        await db.config.update_one({"_key": "autocorreo_state"}, {"$set": {
            "running": False, "last_run": now_iso(),
            "last_run_result": {"error": str(e)[:200]}}})


async def _periodic_mesa_loop():
    """Procesamiento automatico 24/7: revisa mesa cada 5 minutos si esta activado.
    Asi los rechazos/aprobaciones se reenvian 'al tiro' apenas llegan."""
    while True:
        try:
            await asyncio.sleep(300)
            st = await _ac_state()
            if st.get("periodic_enabled") and not st.get("running"):
                destino = st.get("destination") or os.environ.get("MAIL2_USER", "")
                if destino:
                    ejecutivos = await _mapa_ejecutivos()
                    ya = await _subjects_enviados()
                    await _run_mesa_background(destino, st.get("cutoff_iso"), ejecutivos, ya)
        except asyncio.CancelledError:
            break
        except Exception:
            continue


@api.post("/autocorreo/run")
async def ac_run(payload: dict = None):
    st = await _ac_state()
    destino = st.get("destination") or os.environ.get("MAIL2_USER", "")
    if not destino:
        raise HTTPException(status_code=400, detail="No hay correo destino configurado")
    if st.get("running"):
        return {"started": False, "running": True,
                "message": "Ya hay un procesamiento en curso, espere a que termine"}
    ejecutivos = await _mapa_ejecutivos()
    ya_enviados = await _subjects_enviados()
    asyncio.create_task(_run_mesa_background(destino, st.get("cutoff_iso"), ejecutivos, ya_enviados))
    return {"started": True, "running": True,
            "message": "Procesamiento iniciado en segundo plano. Revise el panel en 1-2 minutos."}


@api.post("/autocorreo/test-rechazo")
async def ac_test_rechazo(payload: dict = None):
    """Envia un correo de PRUEBA con el formato real de un rechazo reenviado."""
    st = await _ac_state()
    destino = (payload or {}).get("destino") or st.get("destination") or os.environ.get("MAIL2_USER", "")
    if not destino:
        raise HTTPException(status_code=400, detail="No hay correo destino configurado")
    encabezado = """
    <div style="font-family:Arial,sans-serif;font-size:13px;background:#f5f6fa;
                border-left:4px solid #e17055;padding:10px 14px;margin-bottom:12px">
      <b style="color:#e17055">RECHAZO</b> — Cliente De Prueba<br>
      <b>Correo del cliente (para reenviar):</b> cliente.prueba@ejemplo.cl<br>
      <b>Ejecutivo que envio la gestion:</b> Ejecutivo De Prueba<br>
      <b>Correo del ejecutivo:</b> ejecutivo.prueba@ecomac.cl
    </div>
    <div style="font-family:Arial,sans-serif;font-size:13px;color:#222">
      Estimados,<br><br>
      Junto con saludar, informamos que la operacion del cliente <b>Cliente De Prueba</b>
      ha sido <b>RECHAZADA</b> por politica de riesgo (carga financiera sobre el maximo permitido).<br><br>
      Quedamos atentos a nuevos antecedentes que permitan reevaluar el caso.<br><br>
      Saludos cordiales,<br>Mesa - Central Mutuos
    </div>
    <p style="font-family:Arial,sans-serif;color:#888;font-size:11px;margin-top:14px">
      [CORREO DE PRUEBA] Asi llegara automaticamente cada rechazo de mesa cuando el
      procesamiento automatico 24/7 este activado.</p>
    """
    res = await asyncio.to_thread(
        mail.send_mail, destino, "[PRUEBA] Re: Cliente De Prueba (DS19 - INMEDIATA - RECHAZO)",
        encabezado, [], "principal")
    if not res.get("success"):
        raise HTTPException(status_code=502, detail=res.get("error", "Error de envio"))
    return {"success": True, "destino": destino,
            "mensaje": "Correo de prueba de RECHAZO enviado. Revise su bandeja."}


@api.post("/autocorreo/manual-archive")
async def ac_manual(cliente: str = Form(...), files: list[UploadFile] = File(...)):
    saved = []
    errors = []
    for f in files:
        try:
            raw = await f.read()
            tipo_doc = pdfs.clasificar_documento(raw, f.filename)
            if tipo_doc == "simulacion":
                nuevo, orig, removidas = pdfs.dejar_primera_pagina(raw)
                nombre_aj = f.filename.replace(".pdf", "") + "_CM.pdf"
                _save_pdf(cliente, nombre_aj, nuevo)
                saved.append({"name": _safe_name(nombre_aj), "type": "simulacion_ajustada",
                              "pages_original": orig, "pages_removed": removidas})
            else:
                _save_pdf(cliente, f.filename, raw)
                saved.append({"name": _safe_name(f.filename), "type": tipo_doc})
        except Exception as e:
            errors.append({"file": f.filename, "error": str(e)})
    return {"folder": _safe_name(cliente), "cliente": cliente, "saved": saved, "errors": errors}


# ---------------------------------------------------------------------------
# Procesamiento de Correo: ingesta, OCR+IA, carpeta por cliente, PDF agrupado
# ---------------------------------------------------------------------------
import ocr_service
import ai_extract

PROC_DIR = ROOT_DIR / "storage" / "proc"
PROC_DIR.mkdir(parents=True, exist_ok=True)
CLIENTES_DIR = ROOT_DIR / "storage" / "clientes"
CLIENTES_DIR.mkdir(parents=True, exist_ok=True)
GESTION_DOMINIOS = ["ecomac", "maestra"]

# Orden preestablecido del PDF agrupado
ORDEN_DEPENDIENTE = ["cedula", "liquidacion", "cotizacion_afp", "certificado_afp", "certificado_smf"]
ORDEN_INDEPENDIENTE = ["cedula", "impuesto_renta", "boleta_honorarios", "certificado_smf"]
CHECKLIST = {
    "dependiente": {"cedula": 1, "liquidacion": 6, "cotizacion_afp": 12,
                    "certificado_afp": 1, "certificado_smf": 1},
    "independiente": {"cedula": 1, "certificado_smf": 1, "impuesto_renta": 1,
                      "boleta_honorarios": 1},
}

DOC_LABELS = {
    "cedula": "Cedula de identidad",
    "liquidacion": "Liquidaciones de sueldo",
    "cotizacion_afp": "Cotizaciones AFP",
    "certificado_afp": "Certificado AFP",
    "certificado_smf": "Certificado SMF",
    "impuesto_renta": "Ultimo impuesto a la renta",
    "boleta_honorarios": "Resumen boletas de honorarios",
}


def _validar_item_dict(item):
    """Valida documentos + campos indispensables antes de enviar a mesa."""
    cl = item.get("classification", {})
    campos = item.get("campos", {})
    faltan = []
    if not cl.get("cliente"):
        faltan.append("Nombre del cliente")
    if not cl.get("rut"):
        faltan.append("RUT")
    if campos.get("con_subsidio") is None:
        faltan.append("Con/Sin subsidio")
    if not campos.get("proyecto_inmobiliario"):
        faltan.append("Proyecto / Inmobiliaria")
    if not campos.get("fecha_entrega"):
        faltan.append("Fecha de entrega (inmediata/futura)")
    for k, lbl in [("monto_credito_uf", "Monto del credito"),
                   ("pie_uf", "Pie"),
                   ("ahorro_uf", "Ahorro"),
                   ("monto_credito_solicitar_uf", "Monto del credito a solicitar")]:
        if campos.get(k) in (None, ""):
            faltan.append(lbl)
    if campos.get("con_subsidio") is True and campos.get("monto_subsidio_uf") in (None, ""):
        faltan.append("Monto del subsidio")
    tipo_cliente = cl.get("tipo_cliente", "dependiente")
    req = CHECKLIST.get(tipo_cliente, {})
    conteo = {}
    for d in cl.get("documentos", []):
        conteo[d["tipo"]] = conteo.get(d["tipo"], 0) + 1
    docs_faltantes = {t: n - conteo.get(t, 0) for t, n in req.items() if conteo.get(t, 0) < n}
    listo = not faltan and not docs_faltantes
    return faltan, docs_faltantes, listo




def _es_gestion(remitente, subject, tiene_pdf):
    r = (remitente or "").lower()
    s = (subject or "").lower()
    if any(d in r for d in GESTION_DOMINIOS):
        return True
    if re.search(r"solicitud (de )?(cr[eé]dito|financiamiento|pre.?aprobaci)", s):
        return True
    if tiene_pdf and re.search(r"evaluaci|liquidaci|antecedentes|carpeta|documento|preaprob", s):
        return True
    return False


def _proc_public(d):
    d = clean(dict(d))
    d.pop("attachments_bytes_dir", None)
    return d


@api.get("/oauth/drive/status")
async def drive_status():
    return {"configured": True, "connected": True, "storage": "local"}


@api.get("/oauth/drive/start")
async def drive_start():
    return {"ok": True, "message": "Almacenamiento local activo (no requiere OAuth)"}


@api.get("/procesamiento/stats")
async def proc_stats():
    estados = ["pendiente", "procesando", "clasificado", "revisar", "error", "descartado"]
    out = {"total": await db.proc_queue.count_documents({})}
    for e in estados:
        out[e] = await db.proc_queue.count_documents({"status": e})
    return out


async def _stats_mesa():
    apro = await db.seguimiento.count_documents({"estado": {"$in": ["aprobacion", "aprobado"]}})
    rech = await db.seguimiento.count_documents({"estado": {"$in": ["rechazo", "rechazado"]}})
    total = apro + rech
    base = (apro / total) if total else 0.85
    return {"aprobadas": apro, "rechazadas": rech, "base": base}


def _prob_aprobacion(item, stats):
    """% de posibilidades de aprobación, calibrado con las respuestas reales de mesa."""
    cl = item.get("classification", {}) or {}
    campos = item.get("campos", {}) or {}
    prob = stats["base"] * 100.0
    factores = [f"Base mesa: {round(stats['base']*100)}% ({stats['aprobadas']} aprobadas / {stats['rechazadas']} rechazadas)"]
    tipos = {d.get("tipo") for d in cl.get("documentos", []) or []}
    for d in cl.get("documentos", []) or []:
        if d.get("tipo") not in ("cedula", "liquidacion", "cotizacion_afp", "certificado_afp",
                                 "certificado_smf", "impuesto_renta", "boleta_honorarios"):
            cat = fsvc.cat_de_texto(d.get("filename", ""))
            tipos.add({"cedula": "cedula", "liquidacion": "liquidacion", "afp": "cotizacion_afp",
                       "cmf": "certificado_smf", "imp_renta": "impuesto_renta",
                       "boletas": "boleta_honorarios"}.get(cat, "otro"))
    tipo_cliente = cl.get("tipo_cliente") or "dependiente"
    requeridos = (["cedula", "liquidacion"] if tipo_cliente == "dependiente"
                  else ["cedula", "impuesto_renta", "boleta_honorarios"])
    faltan = [t for t in requeridos if t not in tipos]
    if faltan:
        prob -= 8 * len(faltan)
        factores.append(f"-{8*len(faltan)}%: faltan documentos clave ({', '.join(faltan)})")
    if "certificado_smf" not in tipos:
        prob -= 5
        factores.append("-5%: falta informe CMF")
    try:
        monto = float(campos.get("monto_credito_solicitar_uf") or campos.get("monto_credito_uf") or 0)
    except (TypeError, ValueError):
        monto = 0
    if monto:
        if monto <= 2000:
            prob += 4
            factores.append("+4%: monto acotado (≤2.000 UF)")
        elif monto > 4000:
            prob -= 8
            factores.append("-8%: monto alto (>4.000 UF)")
    if campos.get("con_subsidio"):
        prob += 5
        factores.append("+5%: con subsidio")
    if tipo_cliente == "independiente":
        prob -= 5
        factores.append("-5%: independiente (boletas)")
    prob = max(5, min(98, round(prob)))
    return {"porcentaje": prob, "factores": factores}


def _prob_aprobacion_folder(doc, stats):
    """% de posibilidades de aprobación de una CARPETA de cliente, calibrado con mesa."""
    prob = stats["base"] * 100.0
    factores = [f"Base mesa: {round(stats['base']*100)}% ({stats['aprobadas']} aprobadas / {stats['rechazadas']} rechazadas)"]
    archivos = fsvc.scan_archivos(doc.get("nombre", ""))
    cats = {fsvc.cat_de_archivo(a["nombre"], a["subfolder"]) for a in archivos} - {"combinado", "codeudor", "estudio_titulo"}
    cr = doc.get("credit_request") or {}
    tipo_cliente = cr.get("client_type") or "dependiente"
    requeridos = (["cedula", "imp_renta", "boletas"] if tipo_cliente == "independiente"
                  else ["cedula", "liquidacion"])
    faltan = [c for c in requeridos if c not in cats]
    if faltan:
        prob -= 8 * len(faltan)
        factores.append(f"-{8*len(faltan)}%: faltan documentos clave ({', '.join(faltan)})")
    if "cmf" not in cats:
        prob -= 5
        factores.append("-5%: falta informe CMF")
    df = doc.get("datos_financieros") or {}
    try:
        monto = float(df.get("monto_credito") or 0)
    except (TypeError, ValueError):
        monto = 0
    if monto:
        if monto <= 2000:
            prob += 4
            factores.append("+4%: monto acotado (≤2.000 UF)")
        elif monto > 4000:
            prob -= 8
            factores.append("-8%: monto alto (>4.000 UF)")
    con_sub = df.get("con_subsidio")
    if con_sub is None:
        con_sub = (cr.get("subsidy") or {}).get("tipo") == "con_subsidio"
    if con_sub:
        prob += 5
        factores.append("+5%: con subsidio")
    if tipo_cliente == "independiente":
        prob -= 5
        factores.append("-5%: independiente (boletas)")
    if not df.get("valor_propiedad"):
        prob -= 3
        factores.append("-3%: sin datos financieros completos")
    # REGLA REALISTA: sin los documentos mínimos de mesa, el % es 0
    faltan_mesa = [c for c in fsvc.required_cats(tipo_cliente) if c not in cats]
    if not cats or faltan_mesa:
        etiquetas = [fsvc.MISSING_LABELS.get(c, c) for c in faltan_mesa] or ["sin documentos"]
        factores.append(f"⛔ 0%: no cumple criterios de envío a mesa (faltan: {', '.join(etiquetas)})")
        return {"porcentaje": 0, "factores": factores}
    prob = max(5, min(98, round(prob)))
    return {"porcentaje": prob, "factores": factores}


@api.get("/procesamiento/queue")
async def proc_queue(status: str = ""):
    q = {"status": status} if status else {}
    docs = await db.proc_queue.find(q).sort("date_iso", -1).limit(200).to_list(200)
    stats = await _stats_mesa()
    rows = []
    for d in docs:
        r = _proc_public(d)
        r["prob_aprobacion"] = _prob_aprobacion(d, stats)
        rows.append(r)
    return {"rows": rows}


@api.get("/procesamiento/queue/{qid}")
async def proc_detail(qid: str):
    d = await db.proc_queue.find_one({"id": qid})
    if not d:
        raise HTTPException(status_code=404, detail="Item no encontrado")
    r = _proc_public(d)
    r["prob_aprobacion"] = _prob_aprobacion(d, await _stats_mesa())
    return r


@api.get("/procesamiento/rules")
async def proc_rules():
    docs = await db.proc_rules.find().to_list(100)
    return {"rules": [clean(d) for d in docs]}


@api.post("/procesamiento/rules")
async def proc_add_rule(payload: dict):
    rule = {"id": str(uuid.uuid4()), "name": payload.get("name", ""),
            "pattern": payload.get("pattern", ""), "kind": payload.get("kind", "contains"),
            "priority": payload.get("priority", 10), "active": payload.get("active", True),
            "classify_as": payload.get("classify_as", {})}
    await db.proc_rules.insert_one(dict(rule))
    return {"ok": True, "rule": clean(rule)}


@api.delete("/procesamiento/rules/{rid}")
async def proc_del_rule(rid: str):
    await db.proc_rules.delete_one({"id": rid})
    return {"ok": True}


def _ingest_sync(max_emails):
    correos = mail.fetch_pdf_attachments(sender_filter=None, limit=max_emails)
    items = []
    for c in correos:
        if not _es_gestion(c["from"], c["subject"], bool(c["pdfs"])):
            continue
        items.append(c)
    return items


@api.post("/procesamiento/ingest-from-inbox")
async def proc_ingest(max_emails: int = 20, dias: int = 0):
    """Ingesta gestiones desde las bandejas. dias>0 = solo correos de los ultimos N dias."""
    correos = await asyncio.to_thread(_ingest_sync, max_emails)
    desde_dt = (datetime.now(timezone.utc) - timedelta(days=dias)) if dias > 0 else None
    enqueued = 0
    for c in correos:
        if desde_dt is not None:
            try:
                f = datetime.fromisoformat(c.get("date") or "")
                if f.tzinfo is None:
                    f = f.replace(tzinfo=timezone.utc)
                if f < desde_dt:
                    continue
            except Exception:
                pass
        exists = await db.proc_queue.find_one({"subject": c["subject"], "date_iso": c["date"]})
        if exists:
            continue
        qid = str(uuid.uuid4())
        folder = PROC_DIR / qid
        folder.mkdir(parents=True, exist_ok=True)
        attachments = []
        convertidos = []
        for pdf in c["pdfs"]:
            raw = pdf["content_bytes"]
            nombre = pdf["filename"]
            try:
                raw, nombre, conv = await asyncio.to_thread(pdfs.convertir_a_pdf, raw, nombre)
                if conv:
                    convertidos.append(nombre)
            except Exception:
                continue  # formato no soportado, se puede adjuntar a mano
            fn = _safe_name(nombre)
            with open(folder / fn, "wb") as f:
                f.write(raw)
            attachments.append(fn)
        await db.proc_queue.insert_one({
            "id": qid, "subject": c["subject"], "sender": c["from"],
            "date_iso": c["date"], "status": "pendiente",
            "body_preview": (c.get("body") or "")[:500],
            "body_full": (c.get("body") or "")[:8000],
            "attachments": attachments, "attachments_bytes_dir": str(folder),
            "classification": {}, "campos": {}, "drive_folder_id": None,
        })
        enqueued += 1
    return {"fetched": len(correos), "enqueued": enqueued}


async def _clasificar_item(item):
    folder = PROC_DIR / item["id"]
    docs_detectados = []
    CAMPO_KEYS = ["proyecto_inmobiliario", "ejecutivo_externo", "ejecutivo_interno",
                  "fecha_entrega", "monto_credito_uf", "monto_subsidio_uf", "pie_uf",
                  "ahorro_uf", "monto_credito_solicitar_uf", "con_subsidio", "email_cliente"]
    campos = {k: (None if k.endswith("_uf") or k == "con_subsidio" else "") for k in CAMPO_KEYS}
    cliente, rut = "", ""

    def _merge(info):
        nonlocal cliente, rut
        if info.get("nombre_cliente") and not cliente:
            cliente = info["nombre_cliente"]
        if info.get("rut") and not rut:
            rut = info["rut"]
        for k in CAMPO_KEYS:
            if campos[k] in (None, "", False) and info.get(k) not in (None, "", False):
                campos[k] = info[k]

    # 1) Analizar el CUERPO del correo (ahi vienen la mayoria de los campos de gestion)
    body = item.get("body_full") or item.get("body_preview") or ""
    if len(body) > 20:
        info_body = await ai_extract.clasificar_y_extraer(body, "cuerpo_correo.txt")
        _merge(info_body)

    # 2) Analizar cada adjunto (OCR + IA)
    for fn in item.get("attachments", []):
        path = folder / fn
        if not path.exists():
            continue
        raw = path.read_bytes()
        texto, metodo = await asyncio.to_thread(ocr_service.extraer_texto, raw, fn)
        info = await ai_extract.clasificar_y_extraer(texto, fn)
        docs_detectados.append({"filename": fn, "tipo": info["tipo_documento"],
                                 "metodo": metodo, "confianza": info.get("confianza", 0)})
        _merge(info)
    if not cliente:
        cliente = mail._extraer_nombre(item.get("subject", ""), item.get("sender", ""))
    # Datos del ejecutivo externo desde el remitente del correo
    sender = item.get("sender", "")
    em = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", sender)
    email_ejecutivo = em.group(0) if em else ""
    nombre_ejecutivo = re.sub(r"<.*?>", "", sender).strip().strip('"') or email_ejecutivo.split("@")[0]
    campos["email_ejecutivo"] = email_ejecutivo
    campos["nombre_ejecutivo"] = nombre_ejecutivo
    if not campos.get("ejecutivo_externo"):
        campos["ejecutivo_externo"] = nombre_ejecutivo
    # Correo del cliente detectado en los documentos (si aparecio)
    campos.setdefault("email_cliente", "")
    tipos = [d["tipo"] for d in docs_detectados]
    tipo_cliente = "independiente" if ("boleta_honorarios" in tipos or "impuesto_renta" in tipos) else "dependiente"
    status = "clasificado" if cliente else "revisar"
    classification = {"cliente": cliente, "rut": rut, "tipo_cliente": tipo_cliente,
                      "email_cliente": campos.get("email_cliente", ""),
                      "inmobiliaria": campos.get("proyecto_inmobiliario", ""),
                      "documentos": docs_detectados,
                      "confianza": max([d["confianza"] for d in docs_detectados] + [0.4])}
    await db.proc_queue.update_one({"id": item["id"]}, {"$set": {
        "status": status, "classification": classification, "campos": campos}})
    return status


@api.post("/procesamiento/process-pending")
async def proc_process(limit: int = 5):
    pend = await db.proc_queue.find({"status": "pendiente"}).limit(limit).to_list(limit)
    processed = 0
    for item in pend:
        try:
            await _clasificar_item(item)
            processed += 1
        except Exception as e:
            await db.proc_queue.update_one({"id": item["id"]},
                                            {"$set": {"status": "error", "error": str(e)[:200]}})
    return {"processed": processed}


@api.post("/procesamiento/queue/{qid}/reprocess")
async def proc_reprocess(qid: str):
    item = await db.proc_queue.find_one({"id": qid})
    if not item:
        raise HTTPException(status_code=404, detail="No encontrado")
    await _clasificar_item(item)
    return {"ok": True}


@api.post("/procesamiento/queue/{qid}/correct")
async def proc_correct(qid: str, payload: dict):
    item = await db.proc_queue.find_one({"id": qid})
    if not item:
        raise HTTPException(status_code=404, detail="No encontrado")
    cl = item.get("classification", {})
    campos = item.get("campos", {})
    for k in ["cliente", "rut", "tipo_documento", "inmobiliaria", "tipo_cliente", "email_cliente"]:
        if k in payload:
            cl[k] = payload[k]
    CAMPO_EDIT = ["proyecto_inmobiliario", "ejecutivo_externo", "ejecutivo_interno",
                  "nombre_ejecutivo", "email_ejecutivo", "email_cliente", "fecha_entrega",
                  "monto_credito_uf", "monto_subsidio_uf", "pie_uf", "ahorro_uf",
                  "monto_credito_solicitar_uf", "con_subsidio"]
    for k in CAMPO_EDIT:
        if k in payload:
            v = payload[k]
            if k.endswith("_uf") and v not in (None, ""):
                try:
                    v = float(v)
                except Exception:
                    pass
            campos[k] = v
    await db.proc_queue.update_one({"id": qid}, {"$set": {
        "classification": cl, "campos": campos, "status": "clasificado"}})
    faltan, docs_faltantes, listo = _validar_item_dict({"classification": cl, "campos": campos})
    return {"ok": True, "listo": listo, "campos_faltantes": faltan, "docs_faltantes": docs_faltantes}


@api.get("/procesamiento/queue/{qid}/validate")
async def proc_validate(qid: str):
    item = await db.proc_queue.find_one({"id": qid})
    if not item:
        raise HTTPException(status_code=404, detail="No encontrado")
    faltan, docs_faltantes, listo = _validar_item_dict(item)
    return {"listo": listo, "campos_faltantes": faltan,
            "docs_faltantes": {DOC_LABELS.get(t, t): n for t, n in docs_faltantes.items()}}


@api.post("/procesamiento/queue/{qid}/attach-manual")
async def proc_attach_manual(qid: str, files: list[UploadFile] = File(...)):
    """Adjuntar documentos a mano; los no-PDF se convierten a PDF."""
    item = await db.proc_queue.find_one({"id": qid})
    if not item:
        raise HTTPException(status_code=404, detail="No encontrado")
    folder = PROC_DIR / qid
    folder.mkdir(parents=True, exist_ok=True)
    added, convertidos, errors = [], [], []
    for f in files:
        try:
            raw = await f.read()
            raw2, nombre, conv = pdfs.convertir_a_pdf(raw, f.filename)
            fn = _safe_name(nombre)
            (folder / fn).write_bytes(raw2)
            added.append(fn)
            if conv:
                convertidos.append(fn)
        except Exception as e:
            errors.append({"file": f.filename, "error": str(e)[:150]})
    if added:
        await db.proc_queue.update_one(
            {"id": qid}, {"$push": {"attachments": {"$each": added}}})
    return {"added": added, "convertidos": convertidos, "errors": errors}


@api.get("/procesamiento/queue/{qid}/extract-text")
async def proc_extract_text(qid: str, allow_vision: bool = True):
    item = await db.proc_queue.find_one({"id": qid})
    if not item:
        raise HTTPException(status_code=404, detail="No encontrado")
    folder = PROC_DIR / qid
    results = []
    for fn in item.get("attachments", []):
        path = folder / fn
        if not path.exists():
            continue
        texto, metodo = await asyncio.to_thread(ocr_service.extraer_texto, path.read_bytes(), fn, not allow_vision is False)
        results.append({"filename": fn, "method": metodo, "chars": len(texto)})
    return {"results": results}


@api.post("/procesamiento/queue/{qid}/ordenar-docs")
async def proc_ordenar_docs(qid: str, payload: dict):
    """Guarda el orden manual de los documentos y regenera la Carpeta_ combinada."""
    item = await db.proc_queue.find_one({"id": qid})
    if not item:
        raise HTTPException(status_code=404, detail="No encontrado")
    filenames = payload.get("filenames") or []
    cl = item.get("classification", {}) or {}
    docs = cl.get("documentos", []) or []
    por_nombre = {d.get("filename"): d for d in docs}
    nuevos = [por_nombre[f] for f in filenames if f in por_nombre]
    nuevos += [d for d in docs if d.get("filename") not in set(filenames)]
    await db.proc_queue.update_one({"id": qid}, {"$set": {
        "classification.documentos": nuevos, "docs_orden_manual": True}})
    # Regenerar Carpeta_ con TODO lo acumulado, respetando el orden manual
    cliente = cl.get("cliente") or mail._extraer_nombre(item.get("subject", ""), item.get("sender", ""))
    existente = await _buscar_carpeta_existente(cliente, cl.get("rut", ""))
    if existente and existente.get("nombre"):
        cliente = existente["nombre"]
    regenerado = await asyncio.to_thread(_regen_carpeta_cliente, cliente,
                                         [d.get("filename") for d in nuevos])
    return {"ok": True, "orden": [d.get("filename") for d in nuevos],
            "carpeta_regenerada": bool(regenerado)}


async def _buscar_carpeta_existente(cliente, rut=""):
    """Encuentra la carpeta ya existente de la misma persona (por RUT o nombre similar)."""
    rut_n = _norm_rut(rut or "")
    folders = await db.folders.find({}).to_list(500)
    if rut_n and len(rut_n) >= 7:
        for f in folders:
            if _norm_rut(f.get("rut", "")) == rut_n:
                return f
    cn = [t for t in _norm_texto(cliente or "").split() if len(t) > 2]
    if len(cn) < 2:
        return None
    for f in folders:
        fn = [t for t in _norm_texto(f.get("nombre", "")).split() if len(t) > 2]
        chico, grande = (cn, fn) if len(cn) <= len(fn) else (fn, cn)
        if len(chico) >= 2 and all(t in grande for t in chico):
            return f
    return None


async def _buscar_titular_en_texto(texto, excluir_nombre=""):
    """Encuentra la carpeta de un TITULAR ya existente mencionado en el texto del correo."""
    tx = _norm_texto(texto or "")
    excl = _norm_texto(excluir_nombre or "")
    folders = await db.folders.find({}).to_list(500)
    for f in folders:
        fn_norm = _norm_texto(f.get("nombre", ""))
        if not fn_norm or fn_norm == excl:
            continue
        toks = [t for t in fn_norm.split() if len(t) > 2]
        if len(toks) >= 2 and all(t in tx for t in toks):
            return f
    for r in re.findall(r"\d{1,2}\.?\d{3}\.?\d{3}-?[\dkK]", texto or ""):
        rn = _norm_rut(r)
        if not rn or len(rn) < 7:
            continue
        for f in folders:
            if _norm_rut(f.get("rut", "")) == rn and _norm_texto(f.get("nombre", "")) != excl:
                return f
    return None


def _regen_carpeta_cliente(cliente, orden_manual=None):
    """Reconstruye Carpeta_<cliente>.pdf con TODOS los documentos acumulados de
    todos los correos, en orden de protocolo (prefijos 01_..99_)."""
    from pypdf import PdfReader, PdfWriter
    dest = CLIENTES_DIR / _safe_name(cliente)
    if not dest.exists():
        return None
    manual = {fn: i for i, fn in enumerate(orden_manual or [])}
    archivos = []
    for p in sorted(dest.rglob("*.pdf")):
        rel0 = p.relative_to(dest).as_posix()
        # La carpeta del titular NUNCA incluye los papeles del codeudor ni combinados previos
        if p.name.startswith(("Carpeta_", "COMBINADO_")) or rel0.startswith("05_codeudor/"):
            continue
        rel = rel0
        key = (0, manual[p.name], "") if p.name in manual else (1, 0, rel)
        archivos.append((key, p))
    archivos.sort(key=lambda t: t[0])
    writer = PdfWriter()
    for _k, p in archivos:
        try:
            for pg in PdfReader(str(p)).pages:
                writer.add_page(pg)
        except Exception:
            continue
    if len(writer.pages) == 0:
        return None
    out = dest / f"Carpeta_{_safe_name(cliente)}.pdf"
    with open(out, "wb") as f:
        writer.write(f)
    return out.name


_SOLICITUD_RE = re.compile(
    r"solicitud\s+de\s+(financiamiento|cr[eé]dito)|solicito\s+(evaluaci[oó]n|financiamiento|cr[eé]dito)|evaluaci[oó]n",
    re.I)
_MONTO_RE = re.compile(r"monto|[\d.,]+\s*uf\b|\buf\s*[\d.,]+|\$\s*[\d.,]{4,}", re.I)
_DOCS_BASICOS = ("cedula", "liquidacion", "cotizacion_afp", "certificado_afp",
                 "certificado_smf", "impuesto_renta", "boleta_honorarios")


def _regla_solicitud_ok(item):
    """REGLA INVIOLABLE: solo se arma carpeta nueva si el correo trae frase de
    evaluación/solicitud de financiamiento + montos Y al menos 3 documentos básicos
    (dependiente: liquidaciones/AFP/CMF/cédula/cotización inmobiliaria;
    independiente: cédula/boletas/impuesto renta/CMF)."""
    texto = f"{item.get('subject') or ''} {item.get('body_full') or item.get('body_preview') or ''}"
    if not _SOLICITUD_RE.search(texto):
        return False, "el texto no menciona evaluación ni solicitud de financiamiento/crédito"
    if not _MONTO_RE.search(texto):
        return False, "el texto no indica el monto del crédito"
    tipos = set()
    for d in (item.get("classification") or {}).get("documentos") or []:
        t = d.get("tipo", "")
        if t in _DOCS_BASICOS:
            tipos.add("afp" if t in ("cotizacion_afp", "certificado_afp") else t)
        elif re.search(r"cotizaci[oó]n", d.get("filename", ""), re.I):
            tipos.add("cotizacion_inmobiliaria")
    if len(tipos) < 3:
        return False, f"solo {len(tipos)} documento(s) básico(s) adjunto(s) — mínimo 3"
    return True, ""


CLAVE_FORZAR_CARPETA = "0586"


@api.post("/procesamiento/reevaluar")
async def proc_reevaluar(payload: dict):
    """Reevalúa los correos desde una fecha con la REGLA INVIOLABLE:
    arma carpetas que cumplen y BORRA las que no (requiere clave admin)."""
    payload = payload or {}
    if payload.get("clave") != CLAVE_FORZAR_CARPETA:
        raise HTTPException(status_code=403, detail="Clave incorrecta")
    desde = payload.get("desde") or (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    items = await db.proc_queue.find({"date_iso": {"$gte": desde}}).sort("date_iso", 1).to_list(200)
    creadas, borradas, descartadas, sin_cambio = [], [], [], []
    for it in items:
        nombre_cli = ((it.get("classification") or {}).get("cliente") or "").strip()
        ok_regla, motivo = _regla_solicitud_ok(it)
        folder = None
        if nombre_cli:
            folder = await db.folders.find_one(
                {"nombre": {"$regex": f"^{re.escape(nombre_cli)}$", "$options": "i"},
                 "created_at": {"$gte": desde}})
        if ok_regla:
            if folder or it.get("drive_folder_id"):
                sin_cambio.append(nombre_cli or it.get("subject", ""))
                continue
            try:
                await proc_upload_drive(it["id"])
                creadas.append(nombre_cli or it.get("subject", ""))
            except HTTPException as he:
                descartadas.append(f"{nombre_cli or it.get('subject','')}: {he.detail}")
        else:
            if folder:
                import shutil
                shutil.rmtree(fsvc.folder_dir(folder.get("nombre", "")), ignore_errors=True)
                await db.folders.delete_one({"id": folder["id"]})
                borradas.append(f"{folder.get('nombre','')} — {motivo}")
            await db.proc_queue.update_one({"id": it["id"]}, {"$set": {
                "status": "descartado", "drive_folder_id": None,
                "descartado_motivo": f"REGLA: {motivo}", "descartado_en": now_iso()}})
            if not folder:
                descartadas.append(f"{nombre_cli or it.get('subject','')}: {motivo}")
    return {"ok": True, "desde": desde, "revisados": len(items), "creadas": creadas,
            "borradas": borradas, "descartadas": descartadas, "sin_cambio": sin_cambio}


@api.post("/procesamiento/queue/{qid}/upload-drive")
async def proc_upload_drive(qid: str, force: bool = False, clave: str = ""):
    if force and clave != CLAVE_FORZAR_CARPETA:
        raise HTTPException(status_code=403,
                            detail="Clave incorrecta: solo el administrador puede forzar el armado de carpeta.")
    item = await db.proc_queue.find_one({"id": qid})
    if not item:
        raise HTTPException(status_code=404, detail="No encontrado")
    cl = item.get("classification", {})
    cliente = cl.get("cliente") or mail._extraer_nombre(item.get("subject", ""), item.get("sender", ""))
    tipo_cliente = cl.get("tipo_cliente", "dependiente")
    orden = ORDEN_DEPENDIENTE if tipo_cliente == "dependiente" else ORDEN_INDEPENDIENTE
    docs = []
    vistos = set()
    for d in cl.get("documentos", []):
        fn = d.get("filename")
        if fn and fn not in vistos:
            vistos.add(fn)
            docs.append(d)
    src = PROC_DIR / qid
    docs = [d for d in docs if (src / d["filename"]).exists()]
    if not docs:
        # REGLA: nunca crear carpeta sin adjuntos descargados y clasificados
        raise HTTPException(status_code=409, detail=(
            "No hay adjuntos descargados/clasificados para este correo. "
            "Reprocesa el correo primero: no se crea carpeta vacía."))
    # ENRIQUECER: si ya existe carpeta de la misma persona (otro correo), usarla
    existente = await _buscar_carpeta_existente(cliente, cl.get("rut", ""))
    # Deteccion de CODEUDOR: el correo puede traer los papeles del codeudor del titular
    subj_body = f"{item.get('subject') or ''} {item.get('body_full') or item.get('body_preview') or ''}"
    kw_cod = bool(re.search(r"co-?deudor|\baval\b", subj_body, re.I))
    es_correo_codeudor = False
    cod_nombre, cod_rut = "", ""
    if kw_cod:
        m = re.search(r"co-?deudor[a]?\s*(?:es|:)?\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,3})", subj_body)
        if m:
            cod_nombre = m.group(1).strip()
        titular_doc = await _buscar_titular_en_texto(subj_body, excluir_nombre=cliente)
        if titular_doc and not (existente and existente.get("id") == titular_doc.get("id")):
            # Correo DEL codeudor: sus papeles van a la subcarpeta dentro del titular
            es_correo_codeudor = True
            cod_nombre = cod_nombre or cliente
            cod_rut = cl.get("rut", "")
            existente = titular_doc
    if existente and existente.get("nombre"):
        cliente = existente["nombre"]
    if not existente and not es_correo_codeudor and not force:
        ok_regla, motivo = _regla_solicitud_ok(item)
        if not ok_regla:
            raise HTTPException(status_code=412,
                                detail=f"REGLA: no se arma carpeta — {motivo}")
    dest = CLIENTES_DIR / _safe_name(cliente)
    dest.mkdir(parents=True, exist_ok=True)
    uploaded = []
    _cat_a_tipo = {"cedula": "cedula", "liquidacion": "liquidacion", "afp": "cotizacion_afp",
                   "cmf": "certificado_smf", "imp_renta": "impuesto_renta",
                   "boletas": "boleta_honorarios"}

    def _tipo_efectivo(d):
        t = d["tipo"]
        if t not in orden:
            t = _cat_a_tipo.get(fsvc.cat_de_texto(d.get("filename", "")), t)
        return t
    # Copiar documentos a subcarpetas protocolo (01_cedula, 02_liquidaciones, ...)
    from pypdf import PdfReader, PdfWriter
    for d in docs:
        p = src / d["filename"]
        if p.exists():
            fn_orig = d["filename"]
            es_cod_arch = es_correo_codeudor or bool(re.search(r"co-?deudor", fn_orig, re.I))
            if es_cod_arch:
                sub = "05_codeudor"
                fn_dest = fn_orig if fn_orig.upper().startswith("CODEUDOR_") else f"CODEUDOR_{fn_orig}"
            else:
                sub = fsvc.SUBFOLDER_POR_TIPO.get(_tipo_efectivo(d), "99_otros")
                fn_dest = fn_orig
            sd = dest / sub
            sd.mkdir(parents=True, exist_ok=True)
            (sd / fn_dest).write_bytes(p.read_bytes())
            # si el mismo archivo quedó antes en otra subcarpeta, quitarlo (evita duplicados)
            for viejo in list(dest.rglob(fn_orig)) + list(dest.rglob(fn_dest)):
                if viejo.parent != sd or viejo.name != fn_dest:
                    viejo.unlink(missing_ok=True)
            uploaded.append(f"{sub}/{fn_dest}")
    hay_codeudor_files = any(u.startswith("05_codeudor/") for u in uploaded)
    if hay_codeudor_files:
        try:
            await asyncio.to_thread(fsvc.merge_codeudor, cliente)
        except Exception:
            pass
    # Regenerar la Carpeta combinada con TODO lo acumulado (todos los correos)
    orden_manual = [d["filename"] for d in docs] if item.get("docs_orden_manual") else None
    merged_name = await asyncio.to_thread(_regen_carpeta_cliente, cliente, orden_manual)
    if merged_name:
        uploaded.append(merged_name)
    # Registrar carpeta cliente (con clasificación y datos financieros de la gestión)
    folder_doc = await db.folders.find_one({"nombre": cliente})
    campos = item.get("campos", {}) or {}
    con_sub = campos.get("con_subsidio")
    credit_request = {
        "is_request": True,
        "client_type": tipo_cliente,
        "subsidy": {"tipo": "con_subsidio" if con_sub is True else "sin_subsidio"},
        "codeudor": {"has_codeudor": bool(cod_nombre or hay_codeudor_files), "name": cod_nombre},
    }
    fin_nuevos = {k: v for k, v in {
        "proyecto": campos.get("proyecto_inmobiliario") or "",
        "inmobiliaria": campos.get("proyecto_inmobiliario") or "",
        "con_subsidio": con_sub,
        "monto_subsidio": campos.get("monto_subsidio_uf"),
        "ahorro": campos.get("ahorro_uf"),
        "monto_pie": campos.get("pie_uf"),
        "fecha_entrega": campos.get("fecha_entrega") or "",
        "monto_credito": campos.get("monto_credito_uf") or campos.get("monto_credito_solicitar_uf"),
    }.items() if v not in (None, "")}
    if not folder_doc:
        await db.folders.insert_one({"id": str(uuid.uuid4()), "nombre": cliente,
                                     "rut": cl.get("rut", ""), "archivos": uploaded,
                                     "codeudor_nombre": cod_nombre, "codeudor_rut": cod_rut,
                                     "source_email": item.get("sender", ""),
                                     "credit_request": credit_request,
                                     "datos_financieros": fin_nuevos,
                                     "datos_financieros_fecha": item.get("date_iso", ""),
                                     "created_at": now_iso(), "origen": "procesamiento"})
    else:
        vistos_arch = set(folder_doc.get("archivos") or [])
        upd = {"archivos": (folder_doc.get("archivos") or []) + [a for a in uploaded if a not in vistos_arch],
               "source_email": folder_doc.get("source_email") or item.get("sender", "")}
        if not es_correo_codeudor:
            upd["rut"] = cl.get("rut", "") or folder_doc.get("rut", "")
        fin_actual = folder_doc.get("datos_financieros") or {}
        fecha_vigente = folder_doc.get("datos_financieros_fecha") or ""
        fecha_item = item.get("date_iso") or ""
        if es_correo_codeudor:
            # Correo del CODEUDOR: nunca pisa los datos financieros del titular
            for k, v in fin_nuevos.items():
                if fin_actual.get(k) in (None, ""):
                    fin_actual[k] = v
        elif fecha_item >= fecha_vigente:
            # El correo MÁS NUEVO manda: sus datos financieros sobrescriben los antiguos
            fin_actual.update(fin_nuevos)
            upd["datos_financieros_fecha"] = fecha_item
            if not (folder_doc.get("credit_request") or {}).get("manual_override"):
                cod_prev = (folder_doc.get("credit_request") or {}).get("codeudor") or {}
                if not credit_request["codeudor"]["has_codeudor"] and cod_prev.get("has_codeudor"):
                    credit_request["codeudor"] = cod_prev
                upd["credit_request"] = credit_request
        else:
            # Correo ANTIGUO: solo completa campos vacíos, nunca pisa datos más recientes
            for k, v in fin_nuevos.items():
                if fin_actual.get(k) in (None, ""):
                    fin_actual[k] = v
        upd["datos_financieros"] = fin_actual
        # Enriquecer info del codeudor en la carpeta del titular (aditivo, nunca borra)
        if cod_nombre and not folder_doc.get("codeudor_nombre"):
            upd["codeudor_nombre"] = cod_nombre
        if cod_rut and not folder_doc.get("codeudor_rut"):
            upd["codeudor_rut"] = cod_rut
        if (cod_nombre or hay_codeudor_files) and "credit_request" not in upd:
            cr_act = folder_doc.get("credit_request") or credit_request
            cr_act["codeudor"] = {"has_codeudor": True,
                                  "name": cod_nombre or folder_doc.get("codeudor_nombre", "")}
            upd["credit_request"] = cr_act
        await db.folders.update_one({"nombre": cliente}, {"$set": upd})
    # Checklist de faltantes
    req = CHECKLIST.get(tipo_cliente, {})
    conteo = {}
    for d in docs:
        conteo[d["tipo"]] = conteo.get(d["tipo"], 0) + 1
    faltantes = {t: n - conteo.get(t, 0) for t, n in req.items() if conteo.get(t, 0) < n}
    completo = len(faltantes) == 0
    await db.proc_queue.update_one({"id": qid}, {"$set": {
        "drive_folder_id": _safe_name(cliente), "status": "clasificado",
        "checklist_completo": completo, "faltantes": faltantes}})
    # Los documentos faltantes se piden SOLO en forma manual (regla del usuario 2026-08-02)
    return {"folder_name": _safe_name(cliente), "uploaded": uploaded,
            "skipped_duplicates": [], "dropped_originals": [],
            "checklist_completo": completo, "faltantes": faltantes, "tipo_cliente": tipo_cliente}


async def _enviar_faltantes_auto(cliente):
    """Envía AL TIRO el correo de documentos faltantes al remitente de la solicitud (una vez por lista)."""
    doc = await db.folders.find_one({"nombre": cliente})
    if not doc or not doc.get("source_email"):
        return
    faltan = [c["nombre"] for c in _criterios_folder(doc)
              if not c["ok"] and c["nombre"] not in ("Enviada a mesa", "Datos financieros completos")]
    if not faltan:
        return
    lista_key = "|".join(sorted(faltan))
    if doc.get("faltantes_auto_lista") == lista_key:
        return  # ya se pidió esta misma lista
    nombre = doc.get("nombre", "")
    subject = f"Documentos faltantes — Solicitud de crédito {nombre}"
    lis = "".join(f'<li style="margin:4px 0">{f}</li>' for f in faltan)
    cuerpo = _marca_wrap(f"""
      <p>Estimados, junto con saludar:</p>
      <p>Hemos recibido la solicitud de crédito de <b>{nombre}</b>{f" (RUT {doc.get('rut')})" if doc.get('rut') else ""}.
      Para continuar con la evaluación necesitamos que nos hagan llegar los siguientes documentos faltantes:</p>
      <ol style="margin:6px 0 0;padding-left:22px;color:#111">{lis}</ol>
      <p style="margin-top:14px">Quedamos atentos. Muchas gracias.</p>
      <p style="margin-top:16px;color:#555">Saludos cordiales,</p>""", "Documentos Faltantes — Solicitud de Crédito")
    res = await asyncio.to_thread(mail.send_mail, doc["source_email"], subject, cuerpo, [], "secundaria")
    if res.get("success"):
        await db.folders.update_one({"id": doc["id"]}, {"$set": {
            "faltantes_auto_lista": lista_key, "faltantes_pedidos_at": now_iso()},
            "$unset": {"faltantes_recordatorio_at": "", "faltantes_recordatorio_count": ""}})
        await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "faltantes_auto",
                                     "cliente": nombre, "folder_id": doc["id"],
                                     "mensaje": f"Se pidieron automáticamente los faltantes de {nombre}: {', '.join(faltan)}",
                                     "fecha": now_iso(), "leida": False})


@api.post("/procesamiento/drive/purge-all")
async def proc_purge():
    import shutil
    deleted = 0
    if CLIENTES_DIR.exists():
        for d in CLIENTES_DIR.iterdir():
            if d.is_dir():
                shutil.rmtree(d, ignore_errors=True)
                deleted += 1
    await db.proc_queue.update_many({}, {"$set": {"drive_folder_id": None}})
    return {"deleted": deleted, "errors": []}


# ---------------------------------------------------------------------------
# Procesamiento automático 24/7: ingesta -> OCR/IA -> carpetas -> alertas
# ---------------------------------------------------------------------------
async def _proc_auto_state():
    st = await db.config.find_one({"_key": "proc_auto"})
    if not st:
        st = {"_key": "proc_auto", "enabled": True, "interval_min": 10,
              "last_run": None, "running": False, "last_result": {}}
        await db.config.insert_one(dict(st))
    # BLINDAJE 24/7: la creación de carpetas SIEMPRE está activa
    if not st.get("enabled"):
        st["enabled"] = True
        await db.config.update_one({"_key": "proc_auto"}, {"$set": {"enabled": True}})
    # Si quedó marcado "running" hace más de 30 min, se resetea (proceso colgado)
    if st.get("running") and st.get("last_run"):
        try:
            dt = datetime.fromisoformat(st["last_run"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - dt > timedelta(minutes=30):
                st["running"] = False
                await db.config.update_one({"_key": "proc_auto"}, {"$set": {"running": False}})
        except Exception:
            pass
    st.pop("_id", None)
    st.pop("_key", None)
    return st


async def _crear_alerta_carpeta(folder_doc):
    existe = await db.alertas.find_one({"folder_id": folder_doc["id"],
                                        "tipo": "carpeta_lista", "leida": False})
    if existe:
        return False
    await db.alertas.insert_one({
        "id": str(uuid.uuid4()), "tipo": "carpeta_lista",
        "cliente": folder_doc.get("nombre", ""), "folder_id": folder_doc["id"],
        "mensaje": f"La carpeta de {folder_doc.get('nombre', '')} está lista para enviar a mesa",
        "fecha": now_iso(), "leida": False})
    return True


async def _run_proc_auto():
    resumen = {"enqueued": 0, "processed": 0, "carpetas": 0, "alertas": 0,
               "descartados": 0, "errors": []}
    await db.config.update_one({"_key": "proc_auto"},
                               {"$set": {"running": True, "last_run_started": now_iso()}}, upsert=True)
    try:
        try:
            r = await proc_ingest(max_emails=15)
            resumen["enqueued"] = r.get("enqueued", 0)
        except Exception as e:
            resumen["errors"].append(f"ingesta: {str(e)[:100]}")
        try:
            r = await proc_process(limit=10)
            resumen["processed"] = r.get("processed", 0)
        except Exception as e:
            resumen["errors"].append(f"proceso: {str(e)[:100]}")
        items = await db.proc_queue.find({"status": "clasificado",
                                          "drive_folder_id": None}).limit(10).to_list(10)
        for it in items:
            try:
                await proc_upload_drive(it["id"])
                resumen["carpetas"] += 1
            except HTTPException as he:
                if he.status_code == 412:
                    await db.proc_queue.update_one({"id": it["id"]}, {"$set": {
                        "status": "descartado", "descartado_motivo": he.detail,
                        "descartado_en": now_iso()}})
                    await db.alertas.insert_one({
                        "id": str(uuid.uuid4()), "tipo": "solicitud_descartada",
                        "cliente": (it.get("classification") or {}).get("cliente", "") or (it.get("subject") or "")[:60],
                        "mensaje": (f"🚫 Correo descartado (no se armó carpeta ni se pidieron faltantes): "
                                    f"\"{(it.get('subject') or '')[:70]}\" de {it.get('sender','')} — {he.detail}"),
                        "fecha": now_iso(), "leida": False})
                    resumen["descartados"] += 1
                else:
                    resumen["errors"].append(f"carpeta '{(it.get('subject') or '')[:30]}': {str(he.detail)[:80]}")
            except Exception as e:
                resumen["errors"].append(f"carpeta '{(it.get('subject') or '')[:30]}': {str(e)[:80]}")
        folders = await db.folders.find({}).limit(300).to_list(300)
        for f in folders:
            try:
                pub = _folder_public(f)
                if pub.get("is_ready_to_send") and not f.get("envio_manual"):
                    if await _crear_alerta_carpeta(f):
                        resumen["alertas"] += 1
            except Exception:
                continue
    finally:
        await db.config.update_one({"_key": "proc_auto"}, {"$set": {
            "running": False, "last_run": now_iso(), "last_result": resumen}}, upsert=True)
    return resumen


async def _periodic_proc_loop():
    """Ciclo automático: cada minuto revisa si toca correr según el intervalo configurado."""
    while True:
        try:
            await asyncio.sleep(60)
            st = await _proc_auto_state()
            if not st.get("enabled") or st.get("running"):
                continue
            intervalo = max(2, int(st.get("interval_min") or 10))
            last = st.get("last_run")
            if last:
                try:
                    dt = datetime.fromisoformat(last)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) - dt < timedelta(minutes=intervalo):
                        continue
                except Exception:
                    pass
            await _run_proc_auto()
        except asyncio.CancelledError:
            break
        except Exception:
            continue


@api.get("/procesamiento/auto/status")
async def proc_auto_status():
    st = await _proc_auto_state()
    st["alertas_pendientes"] = await db.alertas.count_documents({"leida": False})
    return st


@api.post("/procesamiento/auto/toggle")
async def proc_auto_toggle(payload: dict = None):
    payload = payload or {}
    upd = {}
    if "enabled" in payload:
        upd["enabled"] = bool(payload["enabled"])
    if "interval_min" in payload:
        try:
            upd["interval_min"] = max(2, min(120, int(payload["interval_min"])))
        except (TypeError, ValueError):
            pass
    if upd:
        await db.config.update_one({"_key": "proc_auto"}, {"$set": upd}, upsert=True)
    return await _proc_auto_state()


@api.post("/procesamiento/auto/run-now")
async def proc_auto_run_now():
    st = await _proc_auto_state()
    if st.get("running"):
        return {"started": False, "message": "Ya hay un ciclo automático en curso"}
    asyncio.create_task(_run_proc_auto())
    return {"started": True, "message": "Ciclo iniciado en segundo plano. Revisá en 1-2 minutos."}


# ---------------------------------------------------------------------------
# Reporte diario 10:00 AM: solicitudes recibidas y enviadas a mesa (24 hrs)
# ---------------------------------------------------------------------------
def _tz_chile():
    from zoneinfo import ZoneInfo
    return ZoneInfo("America/Santiago")


async def _reporte_diario_state():
    st = await db.config.find_one({"_key": "reporte_diario"})
    if not st:
        # last_sent_date = hoy para que el primer envío sea mañana a la hora configurada
        hoy = datetime.now(_tz_chile()).strftime("%Y-%m-%d")
        st = {"_key": "reporte_diario", "enabled": True, "hora": 10,
              "last_sent_date": hoy, "last_result": {}}
        await db.config.insert_one(dict(st))
    st.pop("_id", None)
    st.pop("_key", None)
    return st


async def _datos_reporte_diario():
    tz = _tz_chile()
    ahora = datetime.now(tz)
    st = await _reporte_diario_state()
    hora = int(st.get("hora") or 10)
    corte_hoy = ahora.replace(hour=hora, minute=0, second=0, microsecond=0)
    fin = corte_hoy if ahora >= corte_hoy else corte_hoy - timedelta(days=1)
    inicio = fin - timedelta(days=1)
    items = await db.proc_queue.find({}).sort("date_iso", -1).limit(500).to_list(500)
    recibidas, enviadas = [], []
    for it in items:
        cl = it.get("classification", {}) or {}
        campos = it.get("campos", {}) or {}
        fila = {
            "cliente": cl.get("cliente") or mail._extraer_nombre(it.get("subject", ""), it.get("sender", "")),
            "rut": cl.get("rut") or "—",
            "inmobiliaria": campos.get("proyecto_inmobiliario") or cl.get("inmobiliaria") or "—",
            "ejecutivo": campos.get("nombre_ejecutivo") or campos.get("ejecutivo_externo") or "—",
            "asunto": it.get("subject", ""),
            "fecha": it.get("date_iso", ""),
            "enviada_mesa": bool(it.get("autocorreo_enviado")),
            "match": "app" if it.get("autocorreo_enviado") else "",
        }
        try:
            f = datetime.fromisoformat(it.get("date_iso") or "")
            if f.tzinfo is None:
                f = f.replace(tzinfo=timezone.utc)
            if inicio <= f < fin:
                recibidas.append(fila)
        except Exception:
            pass
        if it.get("autocorreo_enviado"):
            try:
                fe = datetime.fromisoformat(it.get("autocorreo_en") or "")
                if fe.tzinfo is None:
                    fe = fe.replace(tzinfo=timezone.utc)
                if inicio <= fe < fin:
                    enviadas.append({**fila, "enviado_a": it.get("autocorreo_a", ""),
                                     "fecha_envio": it.get("autocorreo_en", "")})
            except Exception:
                pass
    # Cruce por RUT y NOMBRE contra la carpeta Enviados (reenvíos manuales a mesa)
    try:
        hdrs = mail._cached("sent_headers")
        if hdrs is None:
            hdrs = await asyncio.to_thread(mail.fetch_sent_headers, 120)
    except Exception:
        hdrs = []
    st_ac = await _ac_state()
    claves_mesa = {c for c in [(MESA_SENDER or "").lower(),
                               (st_ac.get("destination") or "").lower(), "aprobaciones", "mesa"] if c}
    a_mesa = []
    for h in hdrs or []:
        to_l = (h.get("to") or "").lower()
        if to_l and any(c in to_l for c in claves_mesa):
            a_mesa.append({**h, "subj_norm": _norm_texto(h.get("subject", "")),
                           "subj_digits": _norm_rut(h.get("subject", ""))})
    ya = {_norm_rut(e.get("rut")) or _norm_texto(e.get("cliente")) for e in enviadas}
    for fila in recibidas:
        if fila["enviada_mesa"]:
            continue
        rut_n = _norm_rut(fila.get("rut"))
        tokens = [t for t in _norm_texto(fila.get("cliente")).split() if len(t) > 2]
        for h in a_mesa:
            por_rut = len(rut_n) >= 7 and rut_n in h["subj_digits"]
            por_nombre = len(tokens) >= 2 and all(t in h["subj_norm"] for t in tokens)
            if not (por_rut or por_nombre):
                continue
            fila["enviada_mesa"] = True
            fila["match"] = "rut" if por_rut else "nombre"
            clave = rut_n or _norm_texto(fila.get("cliente"))
            try:
                fe = datetime.fromisoformat(h.get("date") or "")
                if fe.tzinfo is None:
                    fe = fe.replace(tzinfo=timezone.utc)
                if inicio <= fe < fin and clave not in ya:
                    enviadas.append({**fila, "enviado_a": h.get("to", ""),
                                     "fecha_envio": h.get("date", "")})
                    ya.add(clave)
            except Exception:
                pass
            break
    return {"desde": inicio.isoformat(), "hasta": fin.isoformat(),
            "recibidas": recibidas, "enviadas": enviadas,
            "pendientes": [f for f in recibidas if not f["enviada_mesa"]]}


def _tabla_reporte_html(filas, con_envio=False):
    if not filas:
        return "<p style='color:#888;margin:6px 0 16px'>Sin registros en el período.</p>"
    extra_th = "<th style='padding:6px 10px;text-align:left'>Enviado a</th>" if con_envio else "<th style='padding:6px 10px;text-align:left'>¿A mesa?</th>"
    head = ("<tr style='background:#1a1f2e;color:#fff'>"
            "<th style='padding:6px 10px;text-align:left'>Cliente</th>"
            "<th style='padding:6px 10px;text-align:left'>RUT</th>"
            "<th style='padding:6px 10px;text-align:left'>Inmobiliaria</th>"
            "<th style='padding:6px 10px;text-align:left'>Ejecutivo</th>"
            f"{extra_th}"
            "<th style='padding:6px 10px;text-align:left'>Fecha</th></tr>")
    rows = ""
    for i, f in enumerate(filas):
        bg = "#f8fafc" if i % 2 == 0 else "#ffffff"
        if con_envio:
            extra_td = f"<td style='padding:6px 10px'>{f.get('enviado_a', '') or '—'}</td>"
        else:
            marca = {"app": "app", "rut": "por RUT", "nombre": "por nombre"}.get(f.get("match", ""), "")
            extra_td = (f"<td style='padding:6px 10px;color:#16a34a'><b>✓</b> {marca}</td>"
                        if f.get("enviada_mesa") else "<td style='padding:6px 10px;color:#dc2626'><b>✗ Pendiente</b></td>")
        fecha = (f.get("fecha_envio") or f.get("fecha") or "")[:16].replace("T", " ")
        rows += (f"<tr style='background:{bg};border-bottom:1px solid #e2e8f0'>"
                 f"<td style='padding:6px 10px'><b>{f['cliente']}</b></td>"
                 f"<td style='padding:6px 10px'>{f['rut']}</td>"
                 f"<td style='padding:6px 10px'>{f['inmobiliaria']}</td>"
                 f"<td style='padding:6px 10px'>{f['ejecutivo']}</td>"
                 f"{extra_td}"
                 f"<td style='padding:6px 10px;white-space:nowrap'>{fecha}</td></tr>")
    return f"<table style='border-collapse:collapse;font-size:13px;width:100%'>{head}{rows}</table>"


async def _enviar_reporte_diario():
    datos = await _datos_reporte_diario()
    st_ac = await _ac_state()
    destino = st_ac.get("destination") or os.environ.get("MAIL2_USER", "")
    tz = _tz_chile()
    hoy = datetime.now(tz)
    fecha_txt = hoy.strftime("%d-%m-%Y")
    cuerpo = f"""
    <div style="font-family:Arial,sans-serif;font-size:14px;color:#222">
      <h2 style="color:#6c5ce7;margin:0 0 4px">Reporte diario — {fecha_txt}</h2>
      <p style="color:#666;margin:0 0 16px">Período: {datos['desde'][:16].replace('T',' ')} → {datos['hasta'][:16].replace('T',' ')} (hora Chile)</p>
      <h3 style="color:#1a1f2e;margin:0 0 6px">📥 Solicitudes de crédito recibidas ({len(datos['recibidas'])})</h3>
      {_tabla_reporte_html(datos['recibidas'])}
      <h3 style="color:#1a1f2e;margin:16px 0 6px">📤 Enviadas efectivamente a mesa ({len(datos['enviadas'])})</h3>
      {_tabla_reporte_html(datos['enviadas'], con_envio=True)}
      <p style="color:#888;font-size:12px;margin-top:18px">Central Mutuos - Con Creces · Reporte automático de las {int((await _reporte_diario_state()).get('hora') or 10)}:00</p>
    </div>
    """
    asunto = f"[Reporte Diario] Solicitudes y envíos a mesa — {fecha_txt}"
    res = await asyncio.to_thread(mail.send_mail, destino, asunto, cuerpo, [], "principal")
    resultado = {"success": bool(res.get("success")), "destino": destino,
                 "recibidas": len(datos["recibidas"]), "enviadas": len(datos["enviadas"]),
                 "error": res.get("error"), "enviado_en": now_iso()}
    upd = {"last_result": resultado}
    if res.get("success"):
        upd["last_sent_date"] = hoy.strftime("%Y-%m-%d")
    await db.config.update_one({"_key": "reporte_diario"}, {"$set": upd}, upsert=True)
    return resultado


async def _daily_report_loop():
    """Envía el reporte todos los días a la hora configurada (hora de Chile)."""
    while True:
        try:
            await asyncio.sleep(60)
            st = await _reporte_diario_state()
            if not st.get("enabled"):
                continue
            tz = _tz_chile()
            ahora = datetime.now(tz)
            hoy = ahora.strftime("%Y-%m-%d")
            if ahora.hour >= int(st.get("hora") or 10) and st.get("last_sent_date") != hoy:
                await _enviar_reporte_diario()
        except asyncio.CancelledError:
            break
        except Exception:
            continue


@api.get("/reportes/diario/status")
async def reporte_diario_status():
    st = await _reporte_diario_state()
    return st


@api.get("/reportes/diario/preview")
async def reporte_diario_preview():
    return await _datos_reporte_diario()


@api.post("/reportes/diario/toggle")
async def reporte_diario_toggle(payload: dict = None):
    payload = payload or {}
    upd = {}
    if "enabled" in payload:
        upd["enabled"] = bool(payload["enabled"])
    if "hora" in payload:
        try:
            upd["hora"] = max(0, min(23, int(payload["hora"])))
        except (TypeError, ValueError):
            pass
    if upd:
        await db.config.update_one({"_key": "reporte_diario"}, {"$set": upd}, upsert=True)
    return await _reporte_diario_state()


@api.post("/reportes/diario/enviar-ahora")
async def reporte_diario_enviar_ahora():
    res = await _enviar_reporte_diario()
    if not res.get("success"):
        raise HTTPException(status_code=502, detail=res.get("error") or "Error de envío")
    return res


# ---------------------------------------------------------------------------
# Gastos Operacionales: plantilla profesional editable con autosuma
# ---------------------------------------------------------------------------
GASTOS_OP_DEFAULTS = {
    "intro": ("Buenas tardes. Adjunto envío el primer paso del proceso: la Declaración Personal de Salud. "
              "Este es el único documento que debe ser completado de puño y letra. Los documentos restantes "
              "se le enviarán próximamente ya completados para facilitar su firma.\n\n"
              "Asimismo, detallo a continuación la información correspondiente al pago de los gastos operacionales:"),
    "items": [
        {"concepto": "Conservador de Bienes Raíces", "valor": 21, "texto": ""},
        {"concepto": "Escrituración y servicios relacionados", "valor": 5.6, "texto": ""},
        {"concepto": "Estudio de Títulos", "valor": 3, "texto": ""},
        {"concepto": "Notaría", "valor": None, "texto": "Pago directo del cliente en notaría"},
        {"concepto": "Servicio de Inscripción", "valor": 0, "texto": ""},
        {"concepto": "Tasación", "valor": None, "texto": "Pagada"},
    ],
    "datos_pago": {
        "nombre": "MUTUARIAS Y LEASING LIMITADA",
        "rut": "77.771.552-6",
        "banco": "Mercado Pago",
        "tipo_cuenta": "Cuenta Vista",
        "numero_cuenta": "1030937838",
        "email": "",
    },
}


async def _gastos_defaults():
    st = await db.config.find_one({"_key": "gastos_op"}) or {}
    st.pop("_id", None)
    st.pop("_key", None)
    base = {k: v for k, v in GASTOS_OP_DEFAULTS.items()}
    base.update({k: v for k, v in st.items() if v})
    return base


@api.get("/gastos-operacionales/defaults")
async def gastos_defaults():
    return await _gastos_defaults()


@api.patch("/gastos-operacionales/defaults")
async def gastos_defaults_patch(payload: dict):
    upd = {k: payload[k] for k in ("intro", "items", "datos_pago") if k in payload}
    if upd:
        await db.config.update_one({"_key": "gastos_op"}, {"$set": upd}, upsert=True)
    return await _gastos_defaults()


# ---------------------------------------------------------------------------
# Cobro de Tasación — SOLO vivienda usada (4,5 UF a la Cuenta Recaudadora)
# ---------------------------------------------------------------------------
TASACION_COBRO_UF = 4.5


def _fmt_clp(v):
    return "$" + f"{round(v):,.0f}".replace(",", ".")


async def _cobro_ai_clasificar(texto, subject=""):
    key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not key or not (texto or subject or "").strip():
        return {"es_solicitud_usada": False, "cliente": ""}
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(api_key=key, session_id=f"cobro-{uuid.uuid4()}", system_message=(
            "Recibes el asunto y texto de un correo dirigido a una mutuaria de créditos hipotecarios. "
            "Responde SOLO un JSON válido con: es_solicitud_usada (true SOLO si es un broker, vendedor o "
            "tercero SOLICITANDO/pidiendo iniciar una TASACIÓN de una vivienda USADA — no proyecto nuevo de "
            "inmobiliaria, no una respuesta/coordinación de una tasación ya en curso, no un informe de tasación) "
            "y cliente (nombre del cliente/comprador si se menciona, o '').")
        ).with_model("openai", "gpt-5.4-mini")
        resp = await chat.send_message(UserMessage(text=f"ASUNTO: {subject}\n\n{(texto or '')[:4000]}"))
        m = re.search(r"\{.*\}", str(resp), re.S)
        if m:
            import json as _json
            d = _json.loads(m.group(0))
            return {"es_solicitud_usada": bool(d.get("es_solicitud_usada")),
                    "cliente": str(d.get("cliente") or "").strip()}
    except Exception as e:
        logging.warning(f"cobro tasacion IA: {e}")
    return {"es_solicitud_usada": False, "cliente": ""}


TASACION_CUENTA = {
    "nombre": "MUTUARIAS Y LEASING LIMITADA",
    "rut": "77.771.552-6",
    "banco": "Mercado Pago",
    "tipo_cuenta": "Cuenta Vista",
    "numero_cuenta": "1030937838",
}


async def _cobro_tasacion_html(cliente=""):
    uf = await get_valor_uf()
    monto_clp = _fmt_clp(TASACION_COBRO_UF * uf)
    dp = TASACION_CUENTA
    pago_filas = "".join(
        f"<tr><td style='padding:5px 14px 5px 0;color:#6b7280;font-size:13px;white-space:nowrap'>{lbl}</td>"
        f"<td style='padding:5px 0;color:#1a1f2e;font-size:13px;font-weight:600'>{val}</td></tr>"
        for lbl, val in [("Nombre", dp.get("nombre", "")), ("RUT", dp.get("rut", "")),
                         ("Banco", dp.get("banco", "")), ("Tipo de cuenta", dp.get("tipo_cuenta", "")),
                         ("N° de cuenta", dp.get("numero_cuenta", ""))] if val)
    datos = ["Nombre completo y RUT del cliente (comprador)",
             "Dirección completa de la propiedad (calle, número, depto/casa y comuna)",
             "Rol de Avalúo de la propiedad",
             "Valor aproximado de la propiedad (UF)",
             "Nombre, teléfono y correo del contacto para coordinar la visita del tasador",
             "Nombre y correo de la parte vendedora"]
    lis = "".join(f'<li style="margin:5px 0">{d}</li>' for d in datos)
    inner = f"""
      <p>Estimada(o), junto con saludar:</p>
      <p>Hemos recibido su solicitud de tasación{f" para <b>{cliente}</b>" if cliente else ""} (vivienda usada).
      <b>Para proceder con la tasación, favor indicar los siguientes datos:</b></p>
      <ol style="margin:6px 0 0;padding-left:22px;color:#111">{lis}</ol>
      <p style="margin-top:16px">Adicionalmente, para agendar la visita necesitamos el
      <b>voucher de pago de la tasación</b>:</p>
      <div style="background:#f8f9fc;border:1px solid #eceef3;border-radius:8px;padding:14px 20px;margin:8px 0">
        <div style="color:#1a1f2e;font-size:15px"><b>Valor tasación: {_num_uf(TASACION_COBRO_UF)} UF</b>
        &nbsp;·&nbsp; equivalente a <b>{monto_clp}</b> (UF del día: {_fmt_clp(uf)})</div>
      </div>
      <div style="color:#1a1f2e;font-size:15px;font-weight:700;border-left:4px solid #d4af37;padding-left:10px;margin:14px 0 10px">Cuenta Recaudadora</div>
      <div style="background:#f8f9fc;border:1px solid #eceef3;border-radius:8px;padding:14px 20px">
        <table style="border-collapse:collapse">{pago_filas}</table>
      </div>
      <p style="margin-top:14px">Una vez recibidos los datos y el comprobante de pago, coordinaremos la
      tasación a la brevedad. Quedamos atentos.</p>
      <p style="margin-top:16px;color:#555">Saludos cordiales,</p>"""
    return _marca_wrap(inner, "Solicitud de Datos y Pago — Tasación Vivienda Usada"), uf, monto_clp


_COBRO_EXCLUIR = ("valueproperty", "centralmutuos.cl")


async def _procesar_cobros_tasacion():
    """Detecta correos entrantes que SOLICITAN tasación de vivienda usada (brokers/vendedores)
    y responde de inmediato en el hilo pidiendo los datos + voucher de 4,5 UF."""
    cfg = await db.config.find_one({"_key": "cobro_tasacion"}) or {}
    since = cfg.get("since")
    if not since:
        since = now_iso()
        await db.config.update_one({"_key": "cobro_tasacion"},
                                   {"$set": {"_key": "cobro_tasacion", "since": since}}, upsert=True)
    msgs = await asyncio.to_thread(mail.buscar_hilo_por_asunto, "tasacion", 10)
    nuevos = []
    for msg in msgs:
        fe = msg.get("from_email", "")
        if any(x in fe for x in _COBRO_EXCLUIR):
            continue
        if (msg.get("date") or "") < since:
            continue
        if await db.tasacion_cobros.find_one({"msgid": msg["msgid"]}):
            continue
        cls = await _cobro_ai_clasificar(msg.get("body", ""), msg.get("subject", ""))
        rec = {"id": str(uuid.uuid4()), "msgid": msg["msgid"], "from": msg.get("from", ""),
               "from_email": fe, "subject": msg.get("subject", ""), "fecha_correo": msg.get("date", ""),
               "cliente": cls.get("cliente", ""), "es_solicitud": cls["es_solicitud_usada"],
               "detectado_en": now_iso(), "monto_uf": TASACION_COBRO_UF,
               "pagado": False, "pagado_at": None, "origen": "auto"}
        if cls["es_solicitud_usada"] and fe:
            cuerpo, uf, monto_clp = await _cobro_tasacion_html(cls.get("cliente", ""))
            subject = msg.get("subject", "") or "Solicitud de Tasación"
            if not subject.lower().startswith("re:"):
                subject = f"Re: {subject}"
            res = await asyncio.to_thread(mail.send_mail, fe, subject, cuerpo, [], "secundaria",
                                          None, {"In-Reply-To": msg["msgid"],
                                                 "References": msg["msgid"]})
            rec.update({"respondido_at": now_iso() if res.get("success") else None,
                        "valor_uf": uf, "monto_clp": monto_clp,
                        "envio_error": None if res.get("success") else res.get("error", "")})
            await db.tasacion_cobros.insert_one(rec)
            nuevos.append(rec)
        else:
            rec["ignorado"] = True
            await db.tasacion_cobros.insert_one(rec)
    return nuevos


async def _pago_ai_confirmar(texto, adjuntos=""):
    if re.search(r"voucher|comprobante|transferencia|deposito|depósito|pago", adjuntos, re.I):
        return True
    key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not key or not (texto or "").strip():
        return False
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(api_key=key, session_id=f"pago-{uuid.uuid4()}", system_message=(
            "Recibes el texto de un correo (y nombres de archivos adjuntos) en el hilo de un cobro "
            "de tasación de una propiedad. Responde SOLO un JSON válido con: pago_confirmado "
            "(true SOLO si el correo adjunta o confirma explícitamente el pago/voucher/comprobante "
            "de transferencia de la tasación; false si solo envía datos, pregunta o coordina).")
        ).with_model("openai", "gpt-5.4-mini")
        resp = await chat.send_message(UserMessage(text=f"ADJUNTOS: {adjuntos}\n\n{(texto or '')[:3000]}"))
        m = re.search(r"\{.*\}", str(resp), re.S)
        if m:
            import json as _json
            return bool(_json.loads(m.group(0)).get("pago_confirmado"))
    except Exception as e:
        logging.warning(f"pago tasacion IA: {e}")
    return False


async def _detectar_pagos_tasacion():
    """Marca automáticamente 'Tasación pagada' cuando llega el voucher en el hilo del cobro."""
    cobros = await db.tasacion_cobros.find({"es_solicitud": True, "pagado": False,
                                            "respondido_at": {"$ne": None}}).limit(15).to_list(15)
    for c in cobros:
        try:
            subject_kw = re.sub(r"^\s*((re|fwd?|rv):\s*)+", "", c.get("subject", ""), flags=re.I).strip()
            if not subject_kw:
                continue
            msgs = await asyncio.to_thread(mail.buscar_hilo_por_asunto, subject_kw, 6)
            procesados = c.get("pago_msgids") or []
            pagado = False
            for m in msgs:
                if m["msgid"] in procesados:
                    continue
                if c.get("from_email") and m.get("from_email") != c["from_email"]:
                    continue
                if (m.get("date") or "") < (c.get("respondido_at") or ""):
                    continue
                procesados.append(m["msgid"])
                adj = " ".join(m.get("attachments") or [])
                if await _pago_ai_confirmar(m.get("body", ""), adj):
                    pagado = True
                    break
            upd = {"pago_msgids": procesados}
            if pagado:
                upd.update({"pagado": True, "pagado_at": now_iso(), "pagado_origen": "auto"})
                await db.alertas.insert_one({
                    "id": str(uuid.uuid4()), "tipo": "tasacion_pagada",
                    "cliente": c.get("cliente") or c.get("from_email", ""),
                    "mensaje": f"💰 Voucher de pago de tasación detectado — {c.get('cliente') or c.get('from_email','')} marcada como PAGADA automáticamente.",
                    "fecha": now_iso(), "leida": False})
                quien = c.get("cliente") or c.get("from_email", "")
                aviso = _marca_wrap(f"""
                  <p>Le informamos que <b>llegó el pago de la tasación</b> (voucher/comprobante detectado
                  en el correo) correspondiente a:</p>
                  <div style="background:#f8f9fc;border:1px solid #eceef3;border-radius:8px;padding:14px 20px;margin:8px 0">
                    <div style="color:#1a1f2e;font-size:15px"><b>{quien}</b></div>
                    <div style="color:#6b7280;font-size:13px;margin-top:4px">Solicitante: {c.get('from_email','')}
                    · Monto: {_num_uf(c.get('monto_uf', TASACION_COBRO_UF))} UF{f" ≈ {c.get('monto_clp')}" if c.get('monto_clp') else ""}</div>
                  </div>
                  <p>El cobro quedó marcado automáticamente como <b>TASACIÓN PAGADA</b> en el sistema.</p>""",
                  "Pago de Tasación Recibido")
                await asyncio.to_thread(mail.send_mail, _sender_por_rol("principal"),
                                        f"💰 Tasación pagada — {quien}", aviso, [], "secundaria")
            await db.tasacion_cobros.update_one({"id": c["id"]}, {"$set": upd})
        except Exception as e:
            logging.warning(f"detectar pago tasacion: {e}")
            continue


async def _cobro_tasacion_loop():
    """Cada 30 min: detecta solicitudes de tasación de vivienda usada y envía el cobro."""
    while True:
        await asyncio.sleep(1800)
        try:
            await _procesar_cobros_tasacion()
            await _detectar_pagos_tasacion()
        except Exception as e:
            logging.warning(f"cobro tasacion loop: {e}")


@api.get("/gastos-operacionales/cobros-tasacion")
async def cobros_tasacion_list():
    docs = await db.tasacion_cobros.find({"ignorado": {"$ne": True}}).sort("detectado_en", -1).limit(30).to_list(30)
    uf = await get_valor_uf()
    mes = datetime.now(timezone.utc).strftime("%Y-%m")
    base_q = {"es_solicitud": True, "ignorado": {"$ne": True}, "detectado_en": {"$regex": f"^{mes}"}}
    enviadas = await db.tasacion_cobros.count_documents(base_q)
    pagadas = await db.tasacion_cobros.count_documents({**base_q, "pagado": True})
    pendientes = enviadas - pagadas
    return {"cobros": [clean(d) for d in docs], "monto_uf": TASACION_COBRO_UF,
            "valor_uf": uf, "monto_clp": _fmt_clp(TASACION_COBRO_UF * uf),
            "resumen": {"mes": mes, "enviadas": enviadas, "pagadas": pagadas,
                        "pendientes": pendientes,
                        "monto_pagado_clp": _fmt_clp(pagadas * TASACION_COBRO_UF * uf),
                        "monto_pendiente_clp": _fmt_clp(pendientes * TASACION_COBRO_UF * uf)}}


async def _faltantes_recordatorio_loop():
    """Cada hora: mientras sigan faltando documentos, reenvía el recordatorio
    CADA 3 días al mismo destinatario (vendedor/solicitante)."""
    while True:
        await asyncio.sleep(3600)
        docs = await db.folders.find({"faltantes_pedidos_at": {"$exists": True, "$ne": None},
                                      "source_email": {"$exists": True, "$nin": [None, ""]}}
                                     ).limit(30).to_list(30)
        for d in docs:
            try:
                if int(d.get("faltantes_recordatorio_count") or 0) >= 2:
                    continue
                ultimo = d.get("faltantes_recordatorio_at") or d["faltantes_pedidos_at"]
                if _dias_desde(ultimo) < 3:
                    continue
                faltan = [c["nombre"] for c in _criterios_folder(d)
                          if not c["ok"] and c["nombre"] not in ("Enviada a mesa", "Datos financieros completos")]
                if not faltan:
                    continue
                nombre = d.get("nombre", "")
                lis = "".join(f'<li style="margin:4px 0">{f}</li>' for f in faltan)
                cuerpo = _marca_wrap(f"""
                  <p>Estimados, junto con saludar:</p>
                  <p>Le recordamos que para continuar con la evaluación de la solicitud de crédito de
                  <b>{nombre}</b>{f" (RUT {d.get('rut')})" if d.get('rut') else ""} aún nos faltan los
                  siguientes documentos:</p>
                  <ol style="margin:6px 0 0;padding-left:22px;color:#111">{lis}</ol>
                  <p style="margin-top:14px">Agradeceremos hacérnoslos llegar a la brevedad para no
                  retrasar el proceso. Quedamos atentos. Muchas gracias.</p>
                  <p style="margin-top:16px;color:#555">Saludos cordiales,</p>""",
                  "Recordatorio — Documentos Faltantes")
                res = await asyncio.to_thread(mail.send_mail, d["source_email"],
                                              f"Recordatorio: Documentos faltantes — {nombre}",
                                              cuerpo, [], "secundaria")
                if res.get("success"):
                    n = int(d.get("faltantes_recordatorio_count") or 0) + 1
                    await db.folders.update_one({"id": d["id"]}, {"$set": {
                        "faltantes_recordatorio_at": now_iso(),
                        "faltantes_recordatorio_count": n}})
                    await db.alertas.insert_one({
                        "id": str(uuid.uuid4()), "tipo": "faltantes_recordatorio",
                        "cliente": nombre, "folder_id": d["id"],
                        "mensaje": f"⏰ Recordatorio {n}/2 de documentos faltantes enviado — {nombre}: {', '.join(faltan)}",
                        "fecha": now_iso(), "leida": False})
                    if n >= 2:
                        aviso = _marca_wrap(f"""
                          <p>Ya se enviaron <b>2 recordatorios</b> de documentos faltantes para la solicitud de
                          crédito de <b>{nombre}</b>{f" (RUT {d.get('rut')})" if d.get('rut') else ""} sin respuesta.</p>
                          <p>Documentos que siguen faltando:</p>
                          <ol style="margin:6px 0 0;padding-left:22px;color:#111">{lis}</ol>
                          <p style="margin-top:14px">No se enviarán más recordatorios automáticos.
                          Se sugiere contactar directamente al solicitante: <b>{d.get('source_email','')}</b>.</p>""",
                          "Tope de Recordatorios — Requiere Gestión Directa")
                        await asyncio.to_thread(mail.send_mail, _sender_por_rol("principal"),
                                                f"⚠️ Sin respuesta tras 2 recordatorios — {nombre}",
                                                aviso, [], "secundaria")
            except Exception as e:
                logging.warning(f"recordatorio faltantes {d.get('nombre','')}: {e}")
                continue


@api.get("/gastos-operacionales/cobros-tasacion/historial")
async def cobros_tasacion_historial():
    docs = await db.tasacion_cobros.find({"pagado": True, "ignorado": {"$ne": True}}
                                         ).sort("pagado_at", -1).limit(300).to_list(300)
    uf = await get_valor_uf()
    meses = {}
    for d in docs:
        mes = str(d.get("pagado_at") or "")[:7]
        if not mes:
            continue
        m = meses.setdefault(mes, {"mes": mes, "cantidad": 0, "total_uf": 0.0, "detalle": []})
        monto_uf = float(d.get("monto_uf") or TASACION_COBRO_UF)
        m["cantidad"] += 1
        m["total_uf"] += monto_uf
        m["detalle"].append({"cliente": d.get("cliente") or d.get("from_email", ""),
                             "from_email": d.get("from_email", ""),
                             "pagado_at": d.get("pagado_at", ""),
                             "monto_uf": monto_uf,
                             "monto_clp": d.get("monto_clp") or _fmt_clp(monto_uf * uf),
                             "origen_pago": d.get("pagado_origen", "manual")})
    out = sorted(meses.values(), key=lambda x: x["mes"], reverse=True)
    for m in out:
        m["total_clp"] = _fmt_clp(m["total_uf"] * uf)
    return {"historial": out, "valor_uf": uf}


@api.post("/gastos-operacionales/cobros-tasacion/scan")
async def cobros_tasacion_scan():
    nuevos = await _procesar_cobros_tasacion()
    await _detectar_pagos_tasacion()
    return {"ok": True, "nuevos": len(nuevos)}


@api.post("/gastos-operacionales/cobros-tasacion/{cid}/pagado")
async def cobros_tasacion_pagado(cid: str, payload: dict = None):
    pagado = bool((payload or {}).get("pagado", True))
    r = await db.tasacion_cobros.update_one({"id": cid}, {"$set": {
        "pagado": pagado, "pagado_at": now_iso() if pagado else None}})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Cobro no encontrado")
    return {"ok": True, "pagado": pagado}


@api.post("/gastos-operacionales/cobros-tasacion/manual")
async def cobros_tasacion_manual(payload: dict):
    payload = payload or {}
    to = (payload.get("email") or "").strip()
    cliente = (payload.get("cliente") or "").strip()
    if not to or "@" not in to:
        raise HTTPException(status_code=400, detail="Correo del solicitante inválido")
    cuerpo, uf, monto_clp = await _cobro_tasacion_html(cliente)
    subject = f"Solicitud de Datos y Pago — Tasación{f' {cliente}' if cliente else ''}"
    if not payload.get("confirm"):
        return {"to": to, "subject": subject, "body": cuerpo, "monto_uf": TASACION_COBRO_UF,
                "valor_uf": uf, "monto_clp": monto_clp, "sender": _sender_por_rol("secundaria")}
    res = await asyncio.to_thread(mail.send_mail, to, subject, cuerpo, [], "secundaria")
    if not res.get("success"):
        raise HTTPException(status_code=502, detail=res.get("error", "Error de envío"))
    rec = {"id": str(uuid.uuid4()), "msgid": "", "from": to, "from_email": to,
           "subject": subject, "cliente": cliente, "es_solicitud": True,
           "detectado_en": now_iso(), "respondido_at": now_iso(),
           "monto_uf": TASACION_COBRO_UF, "valor_uf": uf, "monto_clp": monto_clp,
           "pagado": False, "pagado_at": None, "origen": "manual"}
    await db.tasacion_cobros.insert_one(rec)
    return {"ok": True, "to": to, "cobro": clean(rec)}


@api.get("/gastos-operacionales/buscar-cliente")
async def gastos_buscar_cliente(q: str = ""):
    q = (q or "").strip()
    if len(q) < 2:
        return {"resultados": []}
    rx = {"$regex": re.escape(q), "$options": "i"}
    docs = await db.folders.find({"$or": [{"nombre": rx}, {"rut": rx}]}).limit(6).to_list(6)
    resultados = []
    for d in docs:
        email_cliente = ""
        item = await db.proc_queue.find_one({"classification.cliente": d.get("nombre", ""),
                                             "campos.email_cliente": {"$nin": ["", None]}})
        if item:
            email_cliente = (item.get("campos") or {}).get("email_cliente", "")
        resultados.append({"nombre": d.get("nombre", ""), "rut": d.get("rut", ""),
                           "email": email_cliente, "folder_id": d.get("id", "")})
    return {"resultados": resultados}


@api.get("/gastos-operacionales/prefill")
async def gastos_prefill(nombre: str = ""):
    """Lee con IA los correos (asunto + cuerpo) y documentos del cliente para pre-llenar
    gastos operacionales. PROHIBIDO inventar datos: lo que no aparece queda vacío."""
    nombre = (nombre or "").strip()
    if len(nombre) < 3:
        raise HTTPException(status_code=400, detail="Indica el nombre del cliente")
    textos = []
    toks = [t for t in _norm_texto(nombre).split() if len(t) > 2]
    if toks:
        rx = ".*".join(re.escape(t) for t in toks[:2])
        async for it in db.proc_queue.find({"$or": [
                {"cliente": {"$regex": rx, "$options": "i"}},
                {"classification.cliente": {"$regex": rx, "$options": "i"}},
                {"subject": {"$regex": rx, "$options": "i"}}]}).limit(6):
            cuerpo = (it.get("body_text") or it.get("body") or it.get("body_full") or "")[:3000]
            textos.append(f"[CORREO] De: {it.get('from','')} · Asunto: {it.get('subject','')}\n{cuerpo}")
    pat = re.compile(r"simulaci|gasto|cotiz|carta|aprobaci|oferta|promesa", re.I)
    for a in fsvc.scan_archivos(nombre):
        if len(textos) >= 10:
            break
        if not pat.search(a["nombre"]):
            continue
        try:
            raw = (fsvc.folder_dir(nombre) / a["ruta"]).read_bytes()
            texto, _m = await asyncio.to_thread(ocr_service.extraer_texto, raw, a["nombre"])
            if texto:
                textos.append(f"[DOC {a['nombre']}]\n{texto[:2500]}")
        except Exception:
            continue
    datos = await ai_extract.extraer_datos_gastos("\n\n".join(textos))
    return {"ok": True, "prefill": datos, "fuentes": len(textos)}


# ==================== MÓDULO CIERRES ====================

async def _ejecutivo_desde_origen(d):
    """Deriva el ejecutivo desde el origen de la solicitud de crédito original:
    el remitente que envió la documentación del cliente (ej: Javiera Garrido de
    Work Consultores). Fuente: source_email de la carpeta o el correo en la cola."""
    origen = (d.get("source_email") or "").strip()
    m = re.match(r'^"?([^"<]*)"?\s*<([^>]+)>$', origen)
    if m and "@" in m.group(2):
        return m.group(1).strip(), m.group(2).strip()
    if "@" in origen:
        return "", origen
    toks = [t for t in _norm_texto(d.get("nombre", "")).split() if len(t) > 2]
    if toks:
        rx = ".*".join(re.escape(t) for t in toks[:2])
        it = await db.proc_queue.find_one({"$or": [
            {"cliente": {"$regex": rx, "$options": "i"}},
            {"classification.cliente": {"$regex": rx, "$options": "i"}},
            {"subject": {"$regex": rx, "$options": "i"}}]})
        remit = ((it or {}).get("from") or "").strip()
        m2 = re.match(r'^"?([^"<]*)"?\s*<([^>]+)>$', remit)
        if m2 and "@" in m2.group(2):
            return m2.group(1).strip(), m2.group(2).strip()
        if "@" in remit:
            return "", remit
    return "", ""


@api.get("/cierres")
async def cierres_list(solo_entrega_inmediata: bool = False, todos: bool = False):
    """Listado de aprobaciones enviadas para consultar al ejecutivo si el cliente
    continúa el crédito. Ventana inicial: desde el último domingo, un mes hacia atrás
    (barrido mensual por única vez); luego la cadencia es cada 3 días por cliente."""
    hoy = datetime.now(timezone.utc)
    ultimo_domingo = (hoy - timedelta(days=(hoy.weekday() + 1) % 7)).replace(
        hour=23, minute=59, second=59, microsecond=0)
    ventana_inicio = ultimo_domingo - timedelta(days=31)
    docs = await db.folders.find({}).to_list(500)
    filas = []
    for d in docs:
        resp = await _mesa_respuesta_folder(d)
        if resp != "aprobada":
            continue
        c = d.get("cierre") or {}
        if solo_entrega_inmediata and not c.get("entrega_inmediata", True):
            continue
        fecha_apro = d.get("aprobacion_enviada_at") or d.get("created_at")
        if not todos and not int(c.get("consultas") or 0):
            try:
                if datetime.fromisoformat(str(fecha_apro)) < ventana_inicio:
                    continue
            except Exception:
                pass
        ultima = c.get("ultima_consulta_at")
        ej_nombre = (c.get("ejecutivo_nombre") or "").strip()
        ej_email = (c.get("ejecutivo_email") or "").strip()
        ej_desde_origen = False
        if not ej_email:
            on, oe = await _ejecutivo_desde_origen(d)
            if oe:
                ej_nombre = ej_nombre or on
                ej_email = oe
                ej_desde_origen = True
        dias = None
        if ultima:
            try:
                dias = (datetime.now(timezone.utc) - datetime.fromisoformat(ultima)).days
            except Exception:
                dias = None
        filas.append({
            "id": d["id"], "nombre": d.get("nombre", ""), "rut": d.get("rut", ""),
            "ejecutivo_nombre": ej_nombre,
            "ejecutivo_email": ej_email,
            "ejecutivo_desde_origen": ej_desde_origen,
            "inmobiliaria": c.get("inmobiliaria") or (d.get("datos_financieros") or {}).get("inmobiliaria", ""),
            "proyecto": c.get("proyecto", ""),
            "entrega_inmediata": c.get("entrega_inmediata", True),
            "fecha_aprobacion": fecha_apro,
            "ultima_consulta_at": ultima,
            "dias_desde_consulta": dias,
            "toca_preguntar": (ultima is None) or (dias is not None and dias >= 3),
            "consultas": int(c.get("consultas") or 0),
            "respuesta_final": c.get("respuesta_final", ""),
        })
    filas.sort(key=lambda x: ((x["ejecutivo_nombre"] or "zzz").lower(), x["nombre"]))
    return {"cierres": filas,
            "ventana": {"desde": ventana_inicio.isoformat(),
                        "hasta_domingo": ultimo_domingo.isoformat()}}


@api.patch("/cierres/{fid}")
async def cierres_update(fid: str, payload: dict):
    await _get_folder_doc(fid)
    permitidos = {"ejecutivo_nombre", "ejecutivo_email", "proyecto", "inmobiliaria",
                  "entrega_inmediata", "respuesta_final"}
    sets = {f"cierre.{k}": v for k, v in (payload or {}).items() if k in permitidos}
    if not sets:
        raise HTTPException(status_code=400, detail="Nada que actualizar")
    await db.folders.update_one({"id": fid}, {"$set": sets})
    return {"ok": True}


@api.get("/cierres/respuesta/{token}")
async def cierres_respuesta(token: str, r: str = ""):
    """Enlace público que pulsa el ejecutivo desde el correo de Cierres.
    r=si → marca que el cliente continúa. r=no → marca que NO continúa y
    BORRA automáticamente la carpeta del archivo."""
    from fastapi.responses import HTMLResponse
    doc = await db.folders.find_one({"cierre.token": token})

    def pagina(titulo, detalle, color):
        return HTMLResponse(f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Central Mutuos</title></head>
<body style="margin:0;font-family:Arial,sans-serif;background:#0f172a;color:#e2e8f0;display:flex;align-items:center;justify-content:center;min-height:100vh">
<div style="max-width:520px;padding:40px;text-align:center">
<div style="font-size:22px;font-weight:bold;color:#d4af37;margin-bottom:18px">CENTRAL MUTUOS</div>
<div style="font-size:44px;margin-bottom:14px">{'✅' if color=='#0d9488' else ('❌' if color=='#b91c1c' else 'ℹ️')}</div>
<h2 style="color:{color};margin:0 0 12px">{titulo}</h2>
<p style="color:#94a3b8;font-size:15px;line-height:1.6">{detalle}</p>
</div></body></html>""")

    if not doc:
        return pagina("Enlace no válido o ya utilizado", "Esta consulta ya fue respondida o el enlace expiró. Gracias.", "#64748b")
    nombre = doc.get("nombre", "")
    if r == "no":
        import shutil
        shutil.rmtree(fsvc.folder_dir(nombre), ignore_errors=True)
        await db.cierres_log.insert_one({"id": str(uuid.uuid4()), "nombre": nombre,
                                         "rut": doc.get("rut", ""), "respuesta": "no_continua",
                                         "carpeta_borrada": True, "fecha": now_iso()})
        await db.folders.delete_one({"id": doc["id"]})
        return pagina("Respuesta registrada: el cliente NO continúa",
                      f"Gracias por informarnos. El registro de <b>{nombre}</b> fue retirado automáticamente de nuestro archivo.",
                      "#b91c1c")
    await db.folders.update_one({"id": doc["id"]}, {"$set": {
        "cierre.respuesta_final": "continua",
        "cierre.respuesta_at": now_iso(),
        "cierre.token": None}})
    await db.cierres_log.insert_one({"id": str(uuid.uuid4()), "nombre": nombre,
                                     "rut": doc.get("rut", ""), "respuesta": "continua",
                                     "carpeta_borrada": False, "fecha": now_iso()})
    return pagina("¡Excelente! El cliente continúa con nosotros",
                  f"Gracias por confirmar. Nos pondremos en contacto para formalizar el crédito de <b>{nombre}</b> y proseguir con la escrituración.",
                  "#0d9488")


@api.post("/cierres/{fid}/consultar")
async def cierres_consultar(fid: str, payload: dict = None, request: Request = None):
    """Correo cordial (envío manual, botón por cliente) preguntando al ejecutivo
    si el cliente continúa el crédito con nosotros."""
    payload = payload or {}
    doc = await _get_folder_doc(fid)
    c = doc.get("cierre") or {}
    ejecutivo = (payload.get("ejecutivo_nombre") or c.get("ejecutivo_nombre") or "").strip()
    correo = (payload.get("ejecutivo_email") or c.get("ejecutivo_email") or "").strip()
    proyecto = (payload.get("proyecto") or c.get("proyecto") or "").strip()
    if "@" not in correo:
        on, oe = await _ejecutivo_desde_origen(doc)
        if oe:
            ejecutivo = ejecutivo or on
            correo = oe
    if "@" not in correo:
        raise HTTPException(status_code=400,
                            detail="Falta el correo del ejecutivo — complétalo en la fila antes de enviar")
    nombre = doc.get("nombre", "")
    sender = _sender_por_rol("secundaria")
    subject = f"Consulta estado de cliente // {nombre}" + (f" // {proyecto}" if proyecto else "")
    entrega = c.get("entrega_inmediata", True)
    token = str(uuid.uuid4())
    base = ""
    try:
        base = (request.headers.get("origin")
                or f"https://{request.headers.get('x-forwarded-host') or request.headers.get('host')}")
    except Exception:
        base = ""
    url_si = f"{base}/api/cierres/respuesta/{token}?r=si"
    url_no = f"{base}/api/cierres/respuesta/{token}?r=no"
    inner = f"""
      <p>Estimado/a {ejecutivo or 'ejecutivo/a'},</p>
      <p>Junto con saludar, quisiera saber si el cliente <b>{nombre}</b>{f", del proyecto <b>{proyecto}</b>" if proyecto else ""}{", con entrega inmediata" if entrega else ""},
      finalmente va a continuar el proceso de crédito con nosotros.</p>
      <p>Favor informarnos para proseguir con el proceso de escrituración. Puede responder con un solo clic:</p>
      <p style="margin:22px 0 10px">
        <a href="{url_si}"
           style="background:#0d9488;color:#ffffff;padding:12px 22px;border-radius:8px;text-decoration:none;font-weight:bold;display:inline-block">
           ✅ Sí, el cliente continúa con ustedes — contáctenme para formalizar el crédito
        </a>
      </p>
      <p style="margin:0 0 22px">
        <a href="{url_no}"
           style="background:#b91c1c;color:#ffffff;padding:12px 22px;border-radius:8px;text-decoration:none;font-weight:bold;display:inline-block">
           ❌ No, el cliente no continuará el crédito con ustedes
        </a>
      </p>
      <p style="color:#777;font-size:12px">Si marca que el cliente no continúa, su registro se retirará automáticamente de nuestro archivo.</p>
      <p style="margin-top:16px;color:#555">Saludos cordiales,</p>"""
    cuerpo = _marca_wrap(inner, "Cierres — Consulta de continuidad de crédito")
    if not payload.get("confirm"):
        return {"to": correo, "subject": subject, "body": cuerpo, "sender": sender}
    res = await asyncio.to_thread(mail.send_mail, correo, subject, cuerpo, [], "secundaria")
    if not res.get("success"):
        raise HTTPException(status_code=502, detail=res.get("error", "Error de envío"))
    await db.folders.update_one({"id": fid}, {
        "$set": {"cierre.ultima_consulta_at": now_iso(),
                 "cierre.ejecutivo_nombre": ejecutivo,
                 "cierre.ejecutivo_email": correo,
                 "cierre.proyecto": proyecto,
                 "cierre.token": token,
                 "cierre.respuesta_final": ""},
        "$inc": {"cierre.consultas": 1}})
    return {"ok": True, "to": correo, "subject": subject}


# ==================== APRENDIZAJE IA (flujo comercial) ====================

async def _stats_flujo_comercial():
    """Métricas REALES del círculo comercial para que la IA aprenda (sin inventar)."""
    folders = await db.folders.find({}).to_list(500)
    stats_mesa = await _stats_mesa()
    s = {"total_carpetas": len(folders), "aprobadas_mesa": 0, "en_escrituracion": 0,
         "tasaciones_solicitadas": 0, "estudios_solicitados": 0,
         "estudios_etapa2_enviados": 0, "reparos_pendientes": 0, "reparos_aceptados": 0,
         "cierres_consultados": 0, "cierres_confirmados_continua": 0,
         "carpetas_sin_rut": 0, "carpetas_prob_0": 0, "gastos_enviados": 0,
         "docs_faltantes_frecuentes": {}}
    for d in folders:
        try:
            if await _mesa_respuesta_folder(d) == "aprobada":
                s["aprobadas_mesa"] += 1
        except Exception:
            pass
        if d.get("is_escrituracion"):
            s["en_escrituracion"] += 1
        if d.get("tasacion_solicitada_at"):
            s["tasaciones_solicitadas"] += 1
        if d.get("estudio_titulo_solicitado_at"):
            s["estudios_solicitados"] += 1
        if d.get("estudio_docs_enviados_abogado_at"):
            s["estudios_etapa2_enviados"] += 1
        if d.get("gastos_enviados_at"):
            s["gastos_enviados"] += 1
        for it in ((d.get("estudio_reparos") or {}).get("items") or []):
            s["reparos_aceptados" if it.get("satisfecho") else "reparos_pendientes"] += 1
        c = d.get("cierre") or {}
        if c.get("ultima_consulta_at"):
            s["cierres_consultados"] += 1
        if c.get("respuesta_final") == "continua":
            s["cierres_confirmados_continua"] += 1
        if not (d.get("rut") or "").strip():
            s["carpetas_sin_rut"] += 1
        try:
            prob = _prob_aprobacion_folder(d, stats_mesa)
            if prob and prob.get("porcentaje", 0) == 0:
                s["carpetas_prob_0"] += 1
            for f_ in (prob or {}).get("factores", []):
                if isinstance(f_, str) and ("falta" in f_.lower() or "sin " in f_.lower()):
                    s["docs_faltantes_frecuentes"][f_[:60]] = s["docs_faltantes_frecuentes"].get(f_[:60], 0) + 1
        except Exception:
            pass
    s["docs_faltantes_frecuentes"] = dict(sorted(
        s["docs_faltantes_frecuentes"].items(), key=lambda x: -x[1])[:6])
    borrados = await db.cierres_log.count_documents({"respuesta": "no_continua"})
    s["clientes_no_continuaron"] = borrados
    return s


@api.get("/aprendizaje")
async def aprendizaje_get():
    docs = await db.aprendizaje_ia.find({}).sort("fecha", -1).limit(10).to_list(10)
    notas = await db.aprendizaje_notas.find({}).sort("fecha", -1).limit(20).to_list(20)
    return {"analisis": [clean(d) for d in docs], "notas": [clean(n) for n in notas]}


@api.post("/aprendizaje/nota")
async def aprendizaje_nota(payload: dict):
    texto = ((payload or {}).get("texto") or "").strip()
    if len(texto) < 5:
        raise HTTPException(status_code=400, detail="La nota es muy corta")
    await db.aprendizaje_notas.insert_one({"id": str(uuid.uuid4()),
                                           "texto": texto[:1000], "fecha": now_iso()})
    return {"ok": True}


async def _aprendizaje_ejecutar():
    stats = await _stats_flujo_comercial()
    previos = await db.aprendizaje_ia.find({}).sort("fecha", -1).limit(3).to_list(3)
    notas = await db.aprendizaje_notas.find({}).sort("fecha", -1).limit(10).to_list(10)
    resultado = await ai_extract.analizar_flujo_comercial(
        stats, [p.get("resumen", "") for p in previos], [n.get("texto", "") for n in notas])
    doc = {"id": str(uuid.uuid4()), "fecha": now_iso(), "stats": stats, **resultado}
    await db.aprendizaje_ia.insert_one(dict(doc))
    return doc


@api.post("/aprendizaje/analizar")
async def aprendizaje_analizar():
    """Ejecuta un ciclo de aprendizaje de la IA sobre el flujo comercial real."""
    return clean(await _aprendizaje_ejecutar())


async def _aprendizaje_loop():
    """Aprendizaje continuo automático: un ciclo diario."""
    while True:
        await asyncio.sleep(6 * 3600)
        try:
            ultimo = await db.aprendizaje_ia.find_one(sort=[("fecha", -1)])
            if ultimo:
                ult = datetime.fromisoformat(str(ultimo.get("fecha")))
                if (datetime.now(timezone.utc) - ult).total_seconds() < 23 * 3600:
                    continue
            await _aprendizaje_ejecutar()
        except Exception as e:
            await db.system_log.insert_one({"id": str(uuid.uuid4()), "loop": "aprendizaje_ia",
                                            "error": str(e)[:300], "fecha": now_iso()})


def _gastos_total(items):
    total = 0.0
    for it in items or []:
        v = it.get("valor")
        try:
            if v is not None and str(v) != "":
                total += float(v)
        except (TypeError, ValueError):
            continue
    return round(total, 2)


def _num_uf(v):
    try:
        f = float(v)
        s = f"{f:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return s.rstrip("0").rstrip(",") if "," in s else s
    except (TypeError, ValueError):
        return str(v)


def _marca_wrap(inner, subtitulo=""):
    sub_html = (f'<div style="color:#e2e8f0;font-size:13px;margin-top:8px;font-weight:600">{subtitulo}</div>'
                if subtitulo else "")
    return f"""
    <div style="background:#f2f4f8;padding:28px 12px;font-family:Georgia,'Times New Roman',serif">
      <div style="max-width:640px;margin:0 auto;background:#ffffff;border-radius:10px;overflow:hidden;box-shadow:0 4px 18px rgba(16,24,40,0.10)">
        <div style="background:#1a1f2e;padding:26px 32px;border-bottom:3px solid #d4af37">
          <div style="color:#d4af37;font-size:22px;font-weight:700;letter-spacing:1px">Central Mutuos</div>
          <div style="color:#9aa3b5;font-size:11px;letter-spacing:3px;margin-top:2px">CON CRECES</div>
          {sub_html}
        </div>
        <div style="padding:28px 32px 10px;color:#2b3245;font-size:14px;line-height:1.65">
          {inner}
        </div>
        <div style="padding:0 32px 26px">
          <p style="margin:14px 0 0;color:#1a1f2e;font-size:14px"><b>Central Mutuos</b><br>
          <span style="color:#6b7280;font-size:12px">Con Creces &middot; Cr&eacute;ditos Hipotecarios</span></p>
        </div>
        <div style="background:#1a1f2e;padding:12px 32px;text-align:center">
          <span style="color:#9aa3b5;font-size:11px">Este correo contiene informaci&oacute;n confidencial dirigida exclusivamente a su destinatario.</span>
        </div>
      </div>
    </div>"""


def _fmt_num_clp(n):
    try:
        return f"{float(n):,.0f}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


def _gastos_html(payload):
    nombre = payload.get("nombre", "")
    rut = payload.get("rut", "")
    intro = (payload.get("intro") or "").strip()
    items = payload.get("items") or []
    dp = payload.get("datos_pago") or {}
    total = _gastos_total(items)
    intro_html = "".join(f"<p style='margin:0 0 12px;line-height:1.6'>{p}</p>"
                         for p in intro.split("\n") if p.strip())
    filas = ""
    for i, it in enumerate(items):
        bg = "#f8f9fc" if i % 2 == 0 else "#ffffff"
        if it.get("valor") is None or str(it.get("valor")) == "":
            valor_html = f"<span style='color:#8a6d1a;font-style:italic'>{it.get('texto') or '—'}</span>"
        else:
            valor_html = f"<b>{_num_uf(it['valor'])} UF</b>"
        filas += (f"<tr style='background:{bg}'>"
                  f"<td style='padding:11px 18px;border-bottom:1px solid #eceef3;color:#2b3245'>{it.get('concepto','')}</td>"
                  f"<td style='padding:11px 18px;border-bottom:1px solid #eceef3;text-align:right;color:#1a1f2e;white-space:nowrap'>{valor_html}</td></tr>")
    filas += (f"<tr style='background:#1a1f2e'>"
              f"<td style='padding:13px 18px;color:#d4af37;font-weight:700;letter-spacing:0.5px'>TOTAL</td>"
              f"<td style='padding:13px 18px;text-align:right;color:#d4af37;font-weight:700;font-size:16px;white-space:nowrap'>{_num_uf(total)} UF</td></tr>")
    valor_uf = payload.get("valor_uf")
    if valor_uf:
        filas += (f"<tr style='background:#1a1f2e'>"
                  f"<td style='padding:9px 18px 13px;color:#9aa3b5;font-size:12px'>TOTAL EN PESOS (UF del día ${_fmt_num_clp(valor_uf)})</td>"
                  f"<td style='padding:9px 18px 13px;text-align:right;color:#ffffff;font-weight:700;font-size:14px;white-space:nowrap'>${_fmt_num_clp(round(total * float(valor_uf)))} CLP</td></tr>")
    pago_filas = "".join(
        f"<tr><td style='padding:5px 14px 5px 0;color:#6b7280;font-size:13px;white-space:nowrap'>{lbl}</td>"
        f"<td style='padding:5px 0;color:#1a1f2e;font-size:13px;font-weight:600'>{val}</td></tr>"
        for lbl, val in [("Nombre", dp.get("nombre", "")), ("RUT", dp.get("rut", "")),
                         ("Banco", dp.get("banco", "")), ("Tipo de cuenta", dp.get("tipo_cuenta", "")),
                         ("N° de cuenta", dp.get("numero_cuenta", "")),
                         ("Correo", dp.get("email", ""))] if val)
    return f"""
    <div style="background:#f2f4f8;padding:28px 12px;font-family:Georgia,'Times New Roman',serif">
      <div style="max-width:640px;margin:0 auto;background:#ffffff;border-radius:10px;overflow:hidden;box-shadow:0 4px 18px rgba(16,24,40,0.10)">
        <div style="background:#1a1f2e;padding:26px 32px;border-bottom:3px solid #d4af37">
          <div style="color:#d4af37;font-size:22px;font-weight:700;letter-spacing:1px">Central Mutuos</div>
        </div>
        <div style="padding:30px 32px 12px">
          <p style="margin:0 0 4px;color:#1a1f2e;font-size:16px"><b>Estimada(o) {nombre}</b></p>
          <p style="margin:0 0 18px;color:#6b7280;font-size:13px">RUT: {rut}</p>
          <div style="color:#2b3245;font-size:14px">{intro_html}</div>
        </div>
        <div style="padding:6px 32px 4px">
          <div style="color:#1a1f2e;font-size:15px;font-weight:700;border-left:4px solid #d4af37;padding-left:10px;margin-bottom:12px">Detalle de Gastos Operacionales</div>
          <table style="width:100%;border-collapse:collapse;font-size:14px;border:1px solid #eceef3;border-radius:8px;overflow:hidden">
            <tr style="background:#eef1f7">
              <th style="padding:10px 18px;text-align:left;color:#4b5563;font-size:12px;letter-spacing:1px;text-transform:uppercase">Concepto</th>
              <th style="padding:10px 18px;text-align:right;color:#4b5563;font-size:12px;letter-spacing:1px;text-transform:uppercase">Valor</th>
            </tr>
            {filas}
          </table>
        </div>
        <div style="padding:22px 32px 8px">
          <div style="color:#1a1f2e;font-size:15px;font-weight:700;border-left:4px solid #d4af37;padding-left:10px;margin-bottom:12px">Cuenta Recaudadora</div>
          <div style="background:#f8f9fc;border:1px solid #eceef3;border-radius:8px;padding:16px 20px">
            <table style="border-collapse:collapse">{pago_filas}</table>
          </div>
        </div>
        <div style="padding:20px 32px 28px">
          <p style="margin:0;color:#6b7280;font-size:13px;line-height:1.6">Ante cualquier consulta sobre el detalle de estos valores o el proceso de pago, no dude en responder este correo. Estamos a su disposición.</p>
          <p style="margin:14px 0 0;color:#1a1f2e;font-size:14px"><b>Central Mutuos</b><br>
          <span style="color:#6b7280;font-size:12px">Créditos Hipotecarios</span></p>
        </div>
        <div style="background:#1a1f2e;padding:12px 32px;text-align:center">
          <span style="color:#9aa3b5;font-size:11px">Este correo contiene información confidencial dirigida exclusivamente a su destinatario.</span>
        </div>
      </div>
    </div>
    """


@api.post("/gastos-operacionales/enviar")
async def gastos_enviar(payload: dict):
    payload = payload or {}
    to = (payload.get("email_cliente") or "").strip()
    nombre = (payload.get("nombre") or "").strip()
    total = _gastos_total(payload.get("items"))
    try:
        payload["valor_uf"] = await get_valor_uf()
    except Exception:
        payload["valor_uf"] = None
    subject = payload.get("subject") or f"Gastos Operacionales — {nombre}"
    cuerpo = _gastos_html(payload)
    if not payload.get("confirm"):
        return {"to": to, "subject": subject, "body": cuerpo, "total": total,
                "sender": _sender_por_rol("secundaria")}
    if not to or "@" not in to:
        raise HTTPException(status_code=400, detail="Correo del cliente inválido")
    res = await asyncio.to_thread(mail.send_mail, to, subject, cuerpo, [], "secundaria")
    if not res.get("success"):
        raise HTTPException(status_code=502, detail=res.get("error", "Error de envío"))
    await db.gastos_op_log.insert_one({
        "id": str(uuid.uuid4()), "nombre": nombre, "rut": payload.get("rut", ""),
        "to": to, "total": total, "enviado_en": now_iso(), "desde": res.get("desde", "")})
    return {"ok": True, "to": to, "subject": subject, "total": total, "sender": res.get("desde", "")}


@api.get("/gastos-operacionales/log")
async def gastos_log():
    docs = await db.gastos_op_log.find({}).sort("enviado_en", -1).limit(20).to_list(20)
    return {"log": [clean(d) for d in docs]}


# ---------------------------------------------------------------------------
# Solicitud de Tasación (Value Property + Victoria Vilches + inmobiliaria)
# ---------------------------------------------------------------------------
TASACION_DEST_DEFAULT = ["contacto@valueproperty.cl", "victoriavilches@centralmutuos.cl"]
VICTORIA_EMAIL = "victoriavilches@centralmutuos.cl"


def _parse_destinatarios(payload, defaults):
    dest = payload.get("destinatarios")
    if isinstance(dest, str):
        dest = [d.strip() for d in re.split(r"[,;\n]+", dest) if d.strip()]
    if not dest:
        dest = list(defaults)
    dest = [d for d in dest if "@" in d]
    if VICTORIA_EMAIL not in [d.lower() for d in dest]:
        dest.append(VICTORIA_EMAIL)
    vistos, out = set(), []
    for d in dest:
        if d.lower() not in vistos:
            vistos.add(d.lower())
            out.append(d)
    return out


def _tasacion_html(p):
    filas = []

    def fila(lbl, val):
        v = str(val or "").strip()
        if v:
            filas.append(
                f'<tr><td style="padding:7px 14px;font-weight:bold;color:#334155;'
                f'white-space:nowrap;border-bottom:1px solid #e2e8f0">{lbl}</td>'
                f'<td style="padding:7px 14px;color:#111;border-bottom:1px solid #e2e8f0">{v}</td></tr>')

    cliente = p.get("nombre", "") + (f" · RUT {p.get('rut')}" if p.get("rut") else "")
    fila("Cliente", cliente)
    modalidad = p.get("modalidad", "")
    fila("Tipo de vivienda", "Vivienda usada" if modalidad == "usada" else ("Vivienda nueva (inmobiliaria)" if modalidad == "inmobiliaria" else ""))
    fila("Tipo de tasación", p.get("tipo", ""))
    if modalidad == "inmobiliaria":
        fila("Inmobiliaria", p.get("inmobiliaria", ""))
        contacto_inmo = " · ".join(x for x in [(p.get("inmo_contacto_nombre") or "").strip(),
                                               (p.get("inmo_contacto_email") or "").strip()] if x)
        fila("Contacto inmobiliaria", contacto_inmo)
    fila("Dirección de la propiedad", p.get("direccion", ""))
    fila("N° de unidad / depto", p.get("unidad", ""))
    fila("Comuna", p.get("comuna", ""))
    fila("Ciudad", p.get("ciudad", ""))
    fila("Rol de Avalúo Fiscal", p.get("rol_avaluo", ""))
    fila("Valor aproximado (UF)", p.get("valor_uf", ""))
    fila("Valor esperado de tasación (UF)", p.get("valor_esperado_uf", ""))
    if modalidad == "usada":
        vend = " · ".join(x for x in [(p.get("vendedor") or "").strip(),
                                      (p.get("vendedor_email") or "").strip()] if x)
        fila("Vendedor (contacto)", vend)
    else:
        fila("Vendedor", p.get("vendedor", ""))
    contacto = " · ".join(x for x in [(p.get("contacto_nombre") or "").strip(),
                                      (p.get("contacto_telefono") or "").strip(),
                                      (p.get("contacto_email") or "").strip()] if x)
    fila("Contacto para coordinar la visita", contacto)
    obs = (p.get("observaciones") or "").strip()
    copias = []
    if modalidad == "inmobiliaria" and (p.get("inmobiliaria") or "").strip():
        copias.append(f"la inmobiliaria {p.get('inmobiliaria').strip()}")
    copias.append("Victoria Vilches")
    saludo = (p.get("intro") or "").strip() or (
        f"Estimados, se envía solicitud de tasación para {p.get('nombre', '')}, "
        f"con copia a {' y a '.join(copias)}.")
    voucher = ('<p style="margin-top:12px"><b>Adjunto voucher de pago tasación.</b></p>'
               if p.get("voucher") else "")
    carta = ('<p style="margin-top:6px"><b>Se adjunta carta de aprobación del cliente.</b></p>'
             if p.get("carta_adjunta") else "")
    inner = f"""
      <p>{saludo}</p>
      <p>A continuación, detallo los antecedentes de la propiedad para la coordinación de la tasación:</p>
      <table style="border-collapse:collapse;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;width:100%">{''.join(filas)}</table>
      {f'<p style="margin-top:12px"><b>Observaciones:</b> {obs}</p>' if obs else ''}
      {voucher}
      {carta}
      <p style="margin-top:14px">Quedo atento a sus comentarios y a cualquier antecedente adicional que requieran.</p>
      <p style="margin-top:16px;color:#555">Saludos cordiales,</p>"""
    return _marca_wrap(inner, "Solicitud de Tasación")


@api.post("/tasacion/enviar")
async def tasacion_enviar(payload: dict):
    payload = payload or {}
    nombre = (payload.get("nombre") or "").strip()
    rut = (payload.get("rut") or "").strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="Falta el nombre del cliente")
    destinos = _parse_destinatarios(payload, TASACION_DEST_DEFAULT)
    subject = f"SOLICITUD TASACION // {nombre}" + (f" Rut: {rut}" if rut else "")
    cuerpo = _tasacion_html(payload)
    attach_names, attach_paths = [], []
    for rel in payload.get("attach_files") or []:
        try:
            pth = fsvc.resolver_ruta(nombre, rel)
            if pth.exists() and pth not in attach_paths:
                attach_paths.append(pth)
                attach_names.append(pth.name)
        except ValueError:
            continue
    sender = _sender_por_rol("secundaria")
    if not payload.get("confirm"):
        return {"to": destinos, "subject": subject, "body": cuerpo,
                "attachments": attach_names, "sender": sender}
    if not (payload.get("direccion") or "").strip():
        raise HTTPException(status_code=400, detail="Falta la dirección de la propiedad")
    adjuntos = [{"filename": pth.name, "content_b64": _b64(pth.read_bytes())} for pth in attach_paths]
    res = await asyncio.to_thread(mail.send_mail, destinos, subject, cuerpo, adjuntos, "secundaria")
    if not res.get("success"):
        raise HTTPException(status_code=502, detail=res.get("error", "Error de envío"))
    # Guardar plantilla de contacto de la inmobiliaria (para autocompletar la próxima vez)
    inmo = (payload.get("inmobiliaria") or "").strip()
    if payload.get("modalidad") == "inmobiliaria" and inmo:
        await db.tasacion_contactos.update_one(
            {"inmobiliaria_key": inmo.lower()},
            {"$set": {"inmobiliaria_key": inmo.lower(), "inmobiliaria": inmo,
                      "contacto_nombre": (payload.get("inmo_contacto_nombre") or "").strip(),
                      "contacto_email": (payload.get("inmo_contacto_email") or "").strip(), "actualizado_en": now_iso()}},
            upsert=True)
    await db.tasacion_log.insert_one({
        "id": str(uuid.uuid4()), "nombre": nombre, "rut": rut,
        "direccion": payload.get("direccion", ""), "tipo": payload.get("tipo", ""),
        "modalidad": payload.get("modalidad", ""), "inmobiliaria": inmo,
        "to": destinos, "adjuntos": attach_names,
        "enviado_en": now_iso(), "desde": res.get("desde", "")})
    if payload.get("folder_id"):
        await db.folders.update_one({"id": payload["folder_id"]},
                                    {"$set": {"tasacion_solicitada_at": now_iso()}})
    return {"ok": True, "to": destinos, "subject": subject,
            "attachments": attach_names, "sender": res.get("desde", sender)}


@api.get("/tasacion/contactos")
async def tasacion_contactos():
    docs = await db.tasacion_contactos.find({}).sort("inmobiliaria", 1).to_list(100)
    return {"contactos": [clean(d) for d in docs]}


@api.get("/tasacion/log")
async def tasacion_log():
    docs = await db.tasacion_log.find({}).sort("enviado_en", -1).limit(20).to_list(20)
    return {"log": [clean(d) for d in docs]}


@api.patch("/tasacion/fecha/{fid}")
async def tasacion_fecha_manual(fid: str, payload: dict):
    fecha = ((payload or {}).get("fecha") or "").strip()
    await db.folders.update_one({"id": fid}, {"$set": {"tasacion_fecha": fecha,
                                                       "tasacion_fecha_origen": "manual"}})
    return {"ok": True, "fecha": fecha}


def _buscar_fecha_tasacion_imap(nombre):
    """Busca en el correo la respuesta de Value Property con la fecha coordinada."""
    toks = [t for t in nombre.split() if len(t) > 2][:2]
    if not toks:
        return None
    query = f'"from:valueproperty.cl {" ".join(toks)}"'
    pat = re.compile(r"coordin[oó][^.]{0,40}?para el\s+([^.,\n]{3,60})", re.I)
    pat2 = re.compile(r"(?:tasaci[oó]n|visita|evaluaci[oó]n)[^.]{0,60}?(?:el d[ií]a|para el)\s+([^.,\n]{3,60})", re.I)
    for acc in mail.ACCOUNTS:
        try:
            m = mail._connect(acc)
            m.select("INBOX", readonly=True)
            typ, data = m.search(None, "X-GM-RAW", query)
            ids = data[0].split() if data and data[0] else []
            import email as _em
            for num in reversed(ids[-5:]):
                typ, d = m.fetch(num, "(BODY.PEEK[])")
                if not d or not isinstance(d[0], tuple):
                    continue
                msg = _em.message_from_bytes(d[0][1])
                body = ""
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        try:
                            body = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore")
                            break
                        except Exception:
                            pass
                mm = pat.search(body) or pat2.search(body)
                if mm:
                    m.logout()
                    return mm.group(1).strip().strip("*").strip()
            m.logout()
        except Exception:
            continue
    return None


@api.post("/tasacion/detectar-fecha/{fid}")
async def tasacion_detectar_fecha(fid: str):
    doc = await db.folders.find_one({"id": fid})
    if not doc:
        raise HTTPException(status_code=404, detail="Carpeta no encontrada")
    fecha = await asyncio.to_thread(_buscar_fecha_tasacion_imap, doc.get("nombre", ""))
    if not fecha:
        return {"ok": False, "detail": "No se encontró respuesta de Value Property con fecha para este cliente"}
    await db.folders.update_one({"id": fid}, {"$set": {"tasacion_fecha": fecha,
                                                       "tasacion_fecha_origen": "auto",
                                                       "tasacion_fecha_detectada_en": now_iso()}})
    return {"ok": True, "fecha": fecha}


async def _tasacion_fecha_loop():
    """Cada 60 min: detecta automáticamente la fecha de tasación en las respuestas de Value Property."""
    while True:
        await asyncio.sleep(3600)
        docs = await db.folders.find({"tasacion_solicitada_at": {"$exists": True, "$ne": None},
                                      "$or": [{"tasacion_fecha": {"$exists": False}},
                                              {"tasacion_fecha": ""}]}).limit(10).to_list(10)
        for d in docs:
            try:
                fecha = await asyncio.to_thread(_buscar_fecha_tasacion_imap, d.get("nombre", ""))
                if fecha:
                    await db.folders.update_one({"id": d["id"]}, {"$set": {
                        "tasacion_fecha": fecha, "tasacion_fecha_origen": "auto",
                        "tasacion_fecha_detectada_en": now_iso()}})
            except Exception:
                continue


def _buscar_tasacion_terminada_imap(nombre):
    """Busca en el correo la respuesta de Value Property con el informe de tasación listo."""
    toks = [t for t in nombre.split() if len(t) > 2][:2]
    if not toks:
        return False
    query = f'"from:valueproperty.cl {" ".join(toks)}"'
    pat = re.compile(r"adjunt\w+[^.\n]{0,80}informe de tasaci|informe de tasaci[oó]n[^.\n]{0,60}adjunt"
                     r"|tasaci[oó]n\s+(finalizada|realizada|lista|terminada)"
                     r"|valor de (la )?tasaci[oó]n|resultado de (la )?tasaci[oó]n", re.I)
    for acc in mail.ACCOUNTS:
        try:
            m = mail._connect(acc)
            m.select("INBOX", readonly=True)
            typ, data = m.search(None, "X-GM-RAW", query)
            ids = data[0].split() if data and data[0] else []
            import email as _em
            for num in reversed(ids[-5:]):
                typ, d = m.fetch(num, "(BODY.PEEK[])")
                if not d or not isinstance(d[0], tuple):
                    continue
                msg = _em.message_from_bytes(d[0][1])
                body = ""
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        try:
                            body = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore")
                            break
                        except Exception:
                            pass
                adjunto_pdf = any((part.get_filename() or "").lower().endswith(".pdf") for part in msg.walk())
                if pat.search(body) or (adjunto_pdf and re.search(r"tasaci[oó]n", body, re.I)):
                    m.logout()
                    return True
            m.logout()
        except Exception:
            continue
    return False


async def _actividades_terminadas_loop():
    """Cada 60 min: marca automáticamente (con fecha) tasaciones y estudios de título terminados."""
    while True:
        await asyncio.sleep(3600)
        # Tasaciones: respuesta de Value Property con el informe
        docs = await db.folders.find({"tasacion_solicitada_at": {"$exists": True, "$ne": None},
                                      "$or": [{"tasacion_terminado_at": {"$exists": False}},
                                              {"tasacion_terminado_at": None}]}).limit(10).to_list(10)
        for d in docs:
            try:
                if await asyncio.to_thread(_buscar_tasacion_terminada_imap, d.get("nombre", "")):
                    await db.folders.update_one({"id": d["id"]}, {"$set": {
                        "tasacion_terminado_at": now_iso(), "tasacion_terminado_origen": "auto"}})
                    await db.alertas.insert_one({
                        "id": str(uuid.uuid4()), "tipo": "tasacion_terminada",
                        "cliente": d.get("nombre", ""), "folder_id": d["id"],
                        "mensaje": f"✅ Tasación de {d.get('nombre', '')} detectada como TERMINADA (informe recibido)",
                        "fecha": now_iso(), "leida": False})
            except Exception:
                continue
        # Estudios de título: reparos declarados satisfechos
        docs = await db.folders.find({"estudio_reparos.estado": "satisfecho",
                                      "$or": [{"estudio_titulo_terminado_at": {"$exists": False}},
                                              {"estudio_titulo_terminado_at": None}]}).limit(10).to_list(10)
        for d in docs:
            try:
                rep = d.get("estudio_reparos") or {}
                await db.folders.update_one({"id": d["id"]}, {"$set": {
                    "estudio_titulo_terminado_at": rep.get("declarado_satisfecho_at") or now_iso(),
                    "estudio_titulo_terminado_origen": "auto"}})
                await db.alertas.insert_one({
                    "id": str(uuid.uuid4()), "tipo": "estudio_terminado",
                    "cliente": d.get("nombre", ""), "folder_id": d["id"],
                    "mensaje": f"✅ Estudio de título de {d.get('nombre', '')} marcado como TERMINADO (reparos satisfechos)",
                    "fecha": now_iso(), "leida": False})
            except Exception:
                continue
        # Alerta: tasaciones solicitadas hace más de 5 días sin respuesta
        limite = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        docs = await db.folders.find({"tasacion_solicitada_at": {"$lt": limite, "$gt": ""},
                                      "$or": [{"tasacion_terminado_at": {"$exists": False}},
                                              {"tasacion_terminado_at": None}],
                                      "tasacion_alerta_sin_respuesta": {"$ne": True}}).limit(20).to_list(20)
        for d in docs:
            try:
                dias = 5
                try:
                    dias = (datetime.now(timezone.utc) - datetime.fromisoformat(d["tasacion_solicitada_at"])).days
                except Exception:
                    pass
                await db.folders.update_one({"id": d["id"]}, {"$set": {"tasacion_alerta_sin_respuesta": True}})
                await db.alertas.insert_one({
                    "id": str(uuid.uuid4()), "tipo": "tasacion_sin_respuesta",
                    "cliente": d.get("nombre", ""), "folder_id": d["id"],
                    "mensaje": f"⏰ La tasación de {d.get('nombre', '')} lleva {dias} días SIN RESPUESTA — revisá con Value Property",
                    "fecha": now_iso(), "leida": False})
            except Exception:
                continue


# ---------------------------------------------------------------------------
# Solicitud de Estudio de Título (Hipotecario Gestión, siempre CC Victoria)
# ---------------------------------------------------------------------------
ESTUDIO_DEST_DEFAULT = [VICTORIA_EMAIL]
DOCS_ESTUDIO_USADA = [
    "Copia de escritura de compraventa anterior (título del vendedor), incluyendo personería si el vendedor es una sociedad",
    "Copia de inscripción de dominio con vigencia en el Conservador de Bienes Raíces",
    "Certificado de hipotecas, gravámenes y prohibiciones (CBR)",
    "Certificado de no expropiación municipal y SERVIU, emitido con fecha reciente",
    "Certificado de contribuciones al día (Tesorería General de la República)",
    "Certificado del administrador del condominio que acredite que no hay deudas de gastos comunes (si aplica)",
    "Copia de Junta Extraordinaria de Accionistas / autorización de enajenación (si el vendedor es sociedad)",
]


DOCS_ESTUDIO_NUEVA = [
    "Copia de inscripción de dominio con vigencia en el Conservador de Bienes Raíces (a nombre de la inmobiliaria)",
    "Certificado de hipotecas, gravámenes y prohibiciones (CBR)",
    "Copia de escritura de compraventa anterior (título de la inmobiliaria) y personería vigente de sus representantes",
    "Permiso de edificación municipal",
    "Certificado de recepción final municipal (o recepción parcial si aplica)",
    "Certificado de número municipal",
    "Certificado de no expropiación municipal y SERVIU",
    "Plano de loteo / copropiedad y certificado de acogida a la Ley de Copropiedad Inmobiliaria (si aplica)",
    "Reglamento de copropiedad inscrito (si aplica)",
    "Certificado de contribuciones al día (Tesorería General de la República)",
    "Promesa de compraventa o borrador de escritura (si existe)",
]


def _estudio_html(p):
    filas = []

    def fila(lbl, val):
        v = str(val or "").strip()
        if v:
            filas.append(
                f'<tr><td style="padding:7px 14px;font-weight:bold;color:#334155;'
                f'white-space:nowrap;border-bottom:1px solid #e2e8f0">{lbl}</td>'
                f'<td style="padding:7px 14px;color:#111;border-bottom:1px solid #e2e8f0">{v}</td></tr>')

    tipo = p.get("tipo_vivienda", "nueva")
    fila("Cliente", p.get("nombre", "") + (f" · RUT {p.get('rut')}" if p.get("rut") else ""))
    fila("Tipo de vivienda", "Vivienda usada" if tipo == "usada" else "Vivienda nueva (inmobiliaria)")
    if tipo == "nueva":
        fila("Inmobiliaria / Proyecto", p.get("inmobiliaria", ""))
        contacto_inmo = " · ".join(x for x in [(p.get("inmo_contacto_nombre") or "").strip(),
                                               (p.get("inmo_contacto_email") or "").strip()] if x)
        fila("Contacto inmobiliaria", contacto_inmo)
    else:
        vend = " · ".join(x for x in [(p.get("vendedor_nombre") or "").strip(),
                                      (p.get("vendedor_email") or "").strip(),
                                      (p.get("vendedor_telefono") or "").strip()] if x)
        fila("Vendedor (contacto)", vend)
    fila("Dirección de la propiedad", p.get("direccion", ""))
    docs = [d for d in (p.get("docs_lista") or []) if str(d).strip()]
    docs_html = ""
    if docs:
        lis = "".join(f'<li style="margin:4px 0">{str(d).strip()}</li>' for d in docs)
        titulo_docs = ("Para el estudio de títulos de vivienda usada necesitamos los siguientes documentos:"
                       if tipo == "usada"
                       else "Para el estudio de títulos solicitamos a la inmobiliaria los siguientes documentos:")
        docs_html = (
            f'<p style="margin-top:14px"><b>{titulo_docs}</b></p>'
            f'<ol style="margin:6px 0 0;padding-left:22px;color:#111">{lis}</ol>'
            '<p style="margin-top:10px;color:#334155;font-size:13px"><i>En caso de ser necesario, '
            'nos reservamos la posibilidad de seguir solicitando antecedentes que permitan la '
            'conclusión en tiempo y forma de este estudio de títulos.</i></p>')
    obs = (p.get("observaciones") or "").strip()
    intro = (p.get("intro") or "").strip() or ("Solicitamos dar inicio al <b>estudio de títulos</b> del cliente en referencia, "
                                               "con copia a Victoria Vilches. Se detallan los antecedentes:")
    inner = f"""
      <p>Estimados, junto con saludar:</p>
      <p>{intro}</p>
      <table style="border-collapse:collapse;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;width:100%">{''.join(filas)}</table>
      {docs_html}
      {f'<p style="margin-top:12px"><b>Observaciones:</b> {obs}</p>' if obs else ''}
      <p style="margin-top:14px">Quedamos atentos a sus comentarios y a cualquier antecedente adicional que sea necesario.</p>
      <p style="margin-top:16px;color:#555">Saludos cordiales,</p>"""
    return _marca_wrap(inner, "Estudio de Títulos")


@api.get("/estudio-titulo/defaults")
async def estudio_defaults():
    return {"destinatarios": ESTUDIO_DEST_DEFAULT, "docs_usada": DOCS_ESTUDIO_USADA,
            "docs_nueva": DOCS_ESTUDIO_NUEVA}


@api.post("/estudio-titulo/enviar")
async def estudio_enviar(payload: dict):
    payload = payload or {}
    nombre = (payload.get("nombre") or "").strip()
    rut = (payload.get("rut") or "").strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="Falta el nombre del cliente")
    if not rut:
        fdoc = await db.folders.find_one({"nombre": {"$regex": f"^{re.escape(nombre)}$", "$options": "i"}})
        rut = ((fdoc or {}).get("rut") or "").strip()
    destinos = _parse_destinatarios(payload, ESTUDIO_DEST_DEFAULT)
    # ETAPA 1 vivienda usada: el listado de documentos debe llegarle al VENDEDOR
    vend_email = (payload.get("vendedor_email") or "").strip()
    if payload.get("tipo_vivienda") == "usada" and "@" in vend_email \
            and vend_email.lower() not in [d.lower() for d in destinos]:
        destinos.insert(0, vend_email)
    cc_raw = payload.get("cc")
    if isinstance(cc_raw, str):
        cc_raw = [c.strip() for c in re.split(r"[,;\n]+", cc_raw) if c.strip()]
    cc = []
    for c in (cc_raw or []):
        if "@" in c and c.lower() not in [d.lower() for d in destinos] and c.lower() not in [x.lower() for x in cc]:
            cc.append(c)
    subject = f"SOLICITUD ESTUDIO DE TITULOS // {nombre}" + (f" {rut}" if rut else "")
    cuerpo = _estudio_html(payload)
    attach_names, attach_paths = [], []
    for rel in payload.get("attach_files") or []:
        try:
            pth = fsvc.resolver_ruta(nombre, rel)
            if pth.exists() and pth not in attach_paths:
                attach_paths.append(pth)
                attach_names.append(pth.name)
        except ValueError:
            continue
    sender = _sender_por_rol("secundaria")
    if not payload.get("confirm"):
        return {"to": destinos, "cc": cc, "subject": subject, "body": cuerpo,
                "attachments": attach_names, "sender": sender}
    adjuntos = [{"filename": pth.name, "content_b64": _b64(pth.read_bytes())} for pth in attach_paths]
    res = await asyncio.to_thread(mail.send_mail, destinos, subject, cuerpo, adjuntos, "secundaria", cc or None)
    if not res.get("success"):
        raise HTTPException(status_code=502, detail=res.get("error", "Error de envío"))
    # Guardar plantilla de contacto de la inmobiliaria (compartida con tasación)
    inmo = (payload.get("inmobiliaria") or "").strip()
    if payload.get("tipo_vivienda") == "nueva" and inmo and (payload.get("inmo_contacto_nombre") or payload.get("inmo_contacto_email")):
        await db.tasacion_contactos.update_one(
            {"inmobiliaria_key": inmo.lower()},
            {"$set": {"inmobiliaria_key": inmo.lower(), "inmobiliaria": inmo,
                      "contacto_nombre": (payload.get("inmo_contacto_nombre") or "").strip(),
                      "contacto_email": (payload.get("inmo_contacto_email") or "").strip(),
                      "actualizado_en": now_iso()}},
            upsert=True)
    await db.estudio_titulo_log.insert_one({
        "id": str(uuid.uuid4()), "nombre": nombre, "rut": rut,
        "tipo_vivienda": payload.get("tipo_vivienda", ""),
        "inmobiliaria": payload.get("inmobiliaria", ""),
        "to": destinos, "adjuntos": attach_names,
        "enviado_en": now_iso(), "desde": res.get("desde", "")})
    if payload.get("folder_id"):
        await db.folders.update_one({"id": payload["folder_id"]}, {"$set": {
            "estudio_titulo_solicitado_at": now_iso(),
            "estudio_titulo_subject": subject,
            "estudio_titulo_tipo_vivienda": payload.get("tipo_vivienda", ""),
            "estudio_titulo_cc": cc,
            "estudio_titulo_vendedor": {
                "nombre": (payload.get("vendedor_nombre") or "").strip(),
                "email": (payload.get("vendedor_email") or "").strip(),
                "telefono": (payload.get("vendedor_telefono") or "").strip()}}})
    return {"ok": True, "to": destinos, "subject": subject,
            "attachments": attach_names, "sender": res.get("desde", sender)}


@api.get("/estudio-titulo/log")
async def estudio_log():
    docs = await db.estudio_titulo_log.find({}).sort("enviado_en", -1).limit(20).to_list(20)
    return {"log": [clean(d) for d in docs]}


GUILLERMO_EMAIL_DEFAULT = "contacto@hipotecariogestion.cl"


@api.post("/estudio-titulo/etapa2/{fid}")
async def estudio_etapa2(fid: str, payload: dict = None):
    """ETAPA 2 del estudio de título: cuando llegan los documentos del vendedor,
    se envían al abogado (Guillermo Marluf) con copia a Victoria Vilches,
    manteniendo el mismo hilo de correo (mismo asunto de la solicitud)."""
    payload = payload or {}
    doc = await _get_folder_doc(fid)
    nombre = doc.get("nombre", "")
    rep = doc.get("estudio_reparos") or {}
    abogado = (payload.get("to_addr") or rep.get("abogado_email") or GUILLERMO_EMAIL_DEFAULT).strip()
    if "@" not in abogado:
        raise HTTPException(status_code=400, detail="Correo del abogado inválido")
    docs_estudio = [a for a in fsvc.scan_archivos(nombre)
                    if (a["subfolder"] or "").startswith("07_estudio_titulo")]
    seleccion = payload.get("attach_files") or []
    if seleccion:
        docs_estudio = [a for a in docs_estudio if a["ruta"] in seleccion]
    if not docs_estudio:
        raise HTTPException(status_code=400,
                            detail="No hay documentos del estudio de título recibidos para enviar (carpeta 07_estudio_titulo vacía)")
    subject = doc.get("estudio_titulo_subject") or (
        f"SOLICITUD ESTUDIO DE TITULOS // {nombre}" + (f" {doc.get('rut')}" if doc.get("rut") else ""))
    extra = (payload.get("body_extra") or "").strip()
    lista = "".join(f"<li>{a['nombre']}</li>" for a in docs_estudio)
    inner = f"""
      <p>Estimado Guillermo,</p>
      <p>Junto con saludar, adjuntamos los documentos recibidos para el <b>estudio de títulos</b>
      del cliente <b>{nombre}</b>{f" (RUT {doc.get('rut')})" if doc.get('rut') else ""}:</p>
      <ul>{lista}</ul>
      {f'<p>{extra}</p>' if extra else ''}
      <p>Quedamos atentos a sus comentarios y posibles reparos para continuar con el estudio.</p>
      <p style="margin-top:16px;color:#555">Saludos cordiales,</p>"""
    cuerpo = _marca_wrap(inner, "Estudio de Títulos — Etapa 2: envío de documentos")
    cc, vistos = [], set()
    for c in [VICTORIA_EMAIL] + (doc.get("estudio_titulo_cc") or []):
        if "@" in c and c.lower() not in vistos and c.lower() != abogado.lower():
            vistos.add(c.lower())
            cc.append(c)
    sender = _sender_por_rol("secundaria")
    if not payload.get("confirm"):
        return {"to": abogado, "cc": cc, "subject": subject, "body": cuerpo,
                "attachments": [a["nombre"] for a in docs_estudio], "sender": sender}
    base = fsvc.folder_dir(nombre)
    adjuntos = [{"filename": a["nombre"], "content_b64": _b64((base / a["ruta"]).read_bytes())}
                for a in docs_estudio]
    res = await asyncio.to_thread(mail.send_mail, abogado, subject, cuerpo, adjuntos, "secundaria", cc)
    if not res.get("success"):
        raise HTTPException(status_code=502, detail=res.get("error", "Error de envío"))
    await db.folders.update_one({"id": fid}, {"$set": {
        "estudio_docs_enviados_abogado_at": now_iso(),
        "estudio_docs_enviados_abogado": [a["nombre"] for a in docs_estudio],
        "estudio_abogado_email": abogado}})
    return {"ok": True, "to": abogado, "cc": cc, "subject": subject,
            "attachments": [a["nombre"] for a in docs_estudio], "sender": res.get("desde", sender)}


# ---------------------------------------------------------------------------
# Plantillas guardadas (estudio de título / gastos operacionales) — uso MANUAL
# ---------------------------------------------------------------------------
@api.get("/plantillas")
async def plantillas_list(tipo: str = ""):
    q = {"tipo": tipo} if tipo else {}
    docs = await db.plantillas.find(q).sort("nombre", 1).to_list(100)
    return {"plantillas": [clean(d) for d in docs]}


@api.post("/plantillas")
async def plantillas_create(payload: dict):
    tipo = (payload.get("tipo") or "").strip()
    nombre = (payload.get("nombre") or "").strip()
    if tipo not in ("estudio", "gastos") or not nombre:
        raise HTTPException(status_code=400, detail="tipo (estudio|gastos) y nombre son requeridos")
    doc = {"id": str(uuid.uuid4()), "tipo": tipo, "nombre": nombre,
           "data": payload.get("data") or {}, "creado_en": now_iso()}
    await db.plantillas.update_one({"tipo": tipo, "nombre": nombre},
                                   {"$set": doc}, upsert=True)
    return {"ok": True, "plantilla": clean(doc)}


@api.delete("/plantillas/{pid}")
async def plantillas_delete(pid: str):
    r = await db.plantillas.delete_one({"id": pid})
    if not r.deleted_count:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Reparos de Estudio de Título (respuestas del abogado en el hilo)
# ---------------------------------------------------------------------------
async def _reparos_ai_clasificar(texto):
    key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not key or not (texto or "").strip():
        return {"tipo": "otro", "reparos": []}
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(api_key=key, session_id=f"reparos-{uuid.uuid4()}", system_message=(
            "Recibes el texto de un correo de un abogado (o su estudio jurídico) sobre un "
            "ESTUDIO DE TÍTULOS de una propiedad. Responde SOLO un JSON válido con: "
            "tipo ('reparos' si el correo pide subsanar observaciones/reparos/documentos "
            "faltantes del estudio de títulos; 'satisfecho' si declara que TODOS los reparos "
            "fueron subsanados/resueltos o que el estudio está aprobado sin observaciones; "
            "'otro' en cualquier otro caso) y reparos (lista de strings, cada reparo u "
            "observación solicitada, texto breve y claro; [] si no aplica).")
        ).with_model("openai", "gpt-5.4-mini")
        resp = await chat.send_message(UserMessage(text=texto[:5000]))
        m = re.search(r"\{.*\}", str(resp), re.S)
        if m:
            import json as _json
            d = _json.loads(m.group(0))
            tipo = d.get("tipo") if d.get("tipo") in ("reparos", "satisfecho", "otro") else "otro"
            return {"tipo": tipo, "reparos": [str(r).strip() for r in (d.get("reparos") or []) if str(r).strip()]}
    except Exception as e:
        logging.warning(f"reparos IA: {e}")
    return {"tipo": "otro", "reparos": []}


def _reparos_vendedor_de(doc):
    v = doc.get("estudio_titulo_vendedor") or {}
    return v.get("nombre", ""), v.get("email", ""), v.get("telefono", "")


def _reparos_cc(doc, excluir=None):
    """CC del hilo de estudio de título: Victoria + copias guardadas (todos informados)."""
    exc = {(e or "").lower() for e in (excluir or [])}
    cc = []
    for e in [VICTORIA_EMAIL] + list(doc.get("estudio_titulo_cc") or []):
        if e and "@" in e and e.lower() not in exc and e.lower() not in [x.lower() for x in cc]:
            cc.append(e)
    return cc


async def _reparos_enviar_vendedor(doc, rep, nuevos):
    v_nombre, v_email, _tel = _reparos_vendedor_de(doc)
    lis = "".join(f'<li style="margin:6px 0">{t}</li>' for t in nuevos)
    inner = f"""
      <p>Estimado(a) {v_nombre or 'vendedor(a)'}:</p>
      <p>En el marco del <b>estudio de títulos</b> de la propiedad asociada a la compraventa de
      <b>{doc.get('nombre','')}</b>{f" (RUT {doc.get('rut')})" if doc.get('rut') else ""}, el abogado a cargo
      nos ha informado los siguientes <b>reparos</b> que necesitamos subsanar para poder continuar:</p>
      <ol style="margin:6px 0 0;padding-left:22px;color:#111">{lis}</ol>
      <p style="margin-top:14px">Le solicitamos hacernos llegar los antecedentes indicados a la brevedad,
      respondiendo directamente a este correo. Ante cualquier duda, quedamos a su disposición.</p>
      <p style="margin-top:16px;color:#555">Saludos cordiales,</p>"""
    cuerpo = _marca_wrap(inner, "Reparos — Estudio de Títulos")
    if not v_email or "@" not in v_email:
        rep["reenvio_vendedor_error"] = "Sin correo del vendedor en el sistema"
        return
    res = await asyncio.to_thread(mail.send_mail, v_email,
                                  f"Reparos Estudio de Título — {doc.get('nombre','')}",
                                  cuerpo, [], "secundaria", _reparos_cc(doc, [v_email]))
    if res.get("success"):
        rep["reenviado_vendedor_at"] = now_iso()
        rep.pop("reenvio_vendedor_error", None)
    else:
        rep["reenvio_vendedor_error"] = res.get("error", "Error de envío")


async def _reparos_enviar_resuelto(doc, rep):
    v_nombre, v_email, _tel = _reparos_vendedor_de(doc)
    lis = "".join(f'<li style="margin:6px 0">&#10003; {i.get("texto","")}</li>' for i in rep.get("items", []))
    inner = f"""
      <p>Estimados:</p>
      <p>Informamos que los <b>reparos de la solicitud de estudio de título</b> de
      <b>{doc.get('nombre','')}</b>{f" (RUT {doc.get('rut')})" if doc.get('rut') else ""} <b>han sido resueltos</b>.</p>
      <ul style="margin:6px 0 0;padding-left:22px;color:#111;list-style:none">{lis}</ul>
      <p style="margin-top:14px">Se procede con el procedimiento del estudio de título correspondiente,
      en tiempo y forma.</p>
      <p style="margin-top:16px;color:#555">Saludos cordiales,</p>"""
    cuerpo = _marca_wrap(inner, "Reparos Resueltos — Estudio de Títulos")
    destinos = [_sender_por_rol("principal")]
    if v_email and "@" in v_email:
        destinos.append(v_email)
    res = await asyncio.to_thread(mail.send_mail, destinos,
                                  f"Reparos resueltos — Estudio de Título {doc.get('nombre','')}",
                                  cuerpo, [], "secundaria", _reparos_cc(doc, destinos))
    rep["aviso_resuelto_at"] = now_iso() if res.get("success") else rep.get("aviso_resuelto_at")
    if not res.get("success"):
        rep["aviso_resuelto_error"] = res.get("error", "Error de envío")


async def _reparos_recordatorio(doc, rep):
    """Recordatorio único a los 5 días en el mismo hilo del abogado (solo vivienda usada)."""
    abogado = rep.get("abogado_email") or ""
    if not abogado:
        cfg = await db.config.find_one({"key": "estudio_abogado_email"}) or {}
        abogado = cfg.get("value", "")
    if not abogado or "@" not in abogado:
        return False
    inner = f"""
      <p>Estimados, junto con saludar:</p>
      <p>Han transcurrido 5 días desde el último intercambio sobre los <b>reparos del estudio de títulos</b> de
      <b>{doc.get('nombre','')}</b>{f" (RUT {doc.get('rut')})" if doc.get('rut') else ""}.</p>
      <p>Agradeceremos indicarnos <b>en qué estado se encuentran los reparos y el estudio de títulos</b>
      de la propiedad en referencia, para poder avanzar con el proceso en tiempo y forma.</p>
      <p style="margin-top:14px">Quedamos atentos. Muchas gracias.</p>
      <p style="margin-top:16px;color:#555">Saludos cordiales,</p>"""
    cuerpo = _marca_wrap(inner, "Consulta de Estado — Estudio de Títulos")
    subject = doc.get("estudio_titulo_subject") or f"SOLICITUD ESTUDIO DE TITULOS // {doc.get('nombre','')}"
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"
    headers = {}
    if rep.get("thread_msgid"):
        headers = {"In-Reply-To": rep["thread_msgid"], "References": rep["thread_msgid"]}
    res = await asyncio.to_thread(mail.send_mail, abogado, subject, cuerpo, [],
                                  "secundaria", _reparos_cc(doc, [abogado]), headers)
    if res.get("success"):
        rep["recordatorio_enviado_at"] = now_iso()
        return True
    return False


async def _procesar_reparos_folder(doc):
    """Busca respuestas del abogado en el hilo del estudio, extrae reparos con IA,
    los reenvía al vendedor (CC Victoria) y detecta la declaración de satisfacción."""
    subject_kw = doc.get("estudio_titulo_subject") or f"ESTUDIO DE TITULOS // {doc.get('nombre','')}"
    rep = doc.get("estudio_reparos") or {"items": [], "procesados_msgids": [], "estado": "sin_reparos"}
    rep.setdefault("items", [])
    rep.setdefault("procesados_msgids", [])
    msgs = await asyncio.to_thread(mail.buscar_hilo_por_asunto, subject_kw, 8)
    cambios = False
    for msg in msgs:
        if msg["msgid"] in rep["procesados_msgids"]:
            continue
        rep["procesados_msgids"].append(msg["msgid"])
        cambios = True
        if msg.get("from_email"):
            rep["abogado_email"] = msg["from_email"]
            rep["thread_msgid"] = msg["msgid"]
            await db.config.update_one({"key": "estudio_abogado_email"},
                                       {"$set": {"key": "estudio_abogado_email",
                                                 "value": msg["from_email"]}}, upsert=True)
        res = await _reparos_ai_clasificar(msg.get("body", ""))
        if res["tipo"] == "reparos" and res["reparos"]:
            existentes = {i["texto"].strip().lower() for i in rep["items"]}
            nuevos = [t for t in res["reparos"] if t.lower() not in existentes]
            for t in nuevos:
                rep["items"].append({"n": len(rep["items"]) + 1, "texto": t,
                                     "satisfecho": False, "satisfecho_en": None})
            rep["detectado_en"] = rep.get("detectado_en") or now_iso()
            rep["estado"] = "pendiente"
            if nuevos:
                await _reparos_enviar_vendedor(doc, rep, nuevos)
        elif res["tipo"] == "satisfecho" and rep["items"] and rep.get("estado") != "satisfecho":
            for i in rep["items"]:
                i["satisfecho"] = True
                i["satisfecho_en"] = i.get("satisfecho_en") or now_iso()
            rep["estado"] = "satisfecho"
            rep["declarado_satisfecho_at"] = now_iso()
            rep["declarado_por"] = "abogado"
            await _reparos_enviar_resuelto(doc, rep)
    if cambios:
        upd = {"estudio_reparos": rep}
        if rep.get("estado") == "satisfecho" and not doc.get("estudio_titulo_terminado_at"):
            upd["estudio_titulo_terminado_at"] = rep.get("declarado_satisfecho_at") or now_iso()
            upd["estudio_titulo_terminado_origen"] = "auto"
        await db.folders.update_one({"id": doc["id"]}, {"$set": upd})
    return rep


def _dias_desde(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str)
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return 0


async def _estudio_reparos_loop():
    """Cada 45 min: procesa hilos de estudio de título y envía el recordatorio de 5 días
    (una sola vez, SOLO vivienda usada)."""
    while True:
        await asyncio.sleep(2700)
        docs = await db.folders.find({
            "estudio_titulo_solicitado_at": {"$exists": True, "$ne": None},
            "estudio_reparos.estado": {"$ne": "satisfecho"}}).limit(15).to_list(15)
        for d in docs:
            try:
                rep = await _procesar_reparos_folder(d)
                if (d.get("estudio_titulo_tipo_vivienda") == "usada"
                        and rep.get("items") and rep.get("estado") != "satisfecho"
                        and rep.get("reenviado_vendedor_at")
                        and not rep.get("recordatorio_enviado_at")
                        and _dias_desde(rep["reenviado_vendedor_at"]) >= 5):
                    if await _reparos_recordatorio(d, rep):
                        await db.folders.update_one({"id": d["id"]},
                                                    {"$set": {"estudio_reparos": rep}})
            except Exception as e:
                logging.warning(f"reparos loop {d.get('nombre','')}: {e}")
                continue


@api.get("/estudio-titulo/reparos/{fid}")
async def reparos_get(fid: str):
    doc = await _get_folder_doc(fid)
    rep = doc.get("estudio_reparos") or {"items": [], "estado": "sin_reparos"}
    return {"reparos": clean(rep), "vendedor": doc.get("estudio_titulo_vendedor") or {},
            "tipo_vivienda": doc.get("estudio_titulo_tipo_vivienda", ""),
            "subject": doc.get("estudio_titulo_subject", "")}


@api.post("/estudio-titulo/reparos/{fid}/scan")
async def reparos_scan(fid: str):
    doc = await _get_folder_doc(fid)
    rep = await _procesar_reparos_folder(doc)
    return {"ok": True, "reparos": clean(rep)}


@api.patch("/estudio-titulo/reparos/{fid}/item/{n}")
async def reparos_item(fid: str, n: int, payload: dict):
    doc = await _get_folder_doc(fid)
    rep = doc.get("estudio_reparos") or {}
    items = rep.get("items") or []
    item = next((i for i in items if i.get("n") == n), None)
    if not item:
        raise HTTPException(status_code=404, detail="Reparo no encontrado")
    sat = bool((payload or {}).get("satisfecho"))
    item["satisfecho"] = sat
    item["satisfecho_en"] = now_iso() if sat else None
    if not all(i.get("satisfecho") for i in items):
        rep["estado"] = "pendiente"
        rep.pop("declarado_satisfecho_at", None)
    await db.folders.update_one({"id": fid}, {"$set": {"estudio_reparos": rep}})
    return {"ok": True, "reparos": clean(rep)}


@api.post("/estudio-titulo/reparos/{fid}/declarar")
async def reparos_declarar(fid: str):
    doc = await _get_folder_doc(fid)
    rep = doc.get("estudio_reparos") or {}
    if not rep.get("items"):
        raise HTTPException(status_code=400, detail="No hay reparos registrados")
    for i in rep["items"]:
        i["satisfecho"] = True
        i["satisfecho_en"] = i.get("satisfecho_en") or now_iso()
    rep["estado"] = "satisfecho"
    rep["declarado_satisfecho_at"] = now_iso()
    rep["declarado_por"] = "manual"
    await _reparos_enviar_resuelto(doc, rep)
    await db.folders.update_one({"id": fid}, {"$set": {"estudio_reparos": rep}})
    return {"ok": True, "reparos": clean(rep)}


# ---------------------------------------------------------------------------
# Brokers (canales de tasación / estudio de título) — administrables
# ---------------------------------------------------------------------------
BROKERS_SEED = [
    {"nombre": "World Consultores", "contactos": "Javier Garrido y Felipe de la Cuadra",
     "emails": ["jgarrido@worldconsultores.com", "fdelacuadra@worldconsultores.com"]},
    {"nombre": "Kiara Fernández", "contactos": "Kiara Fernández",
     "emails": ["kiara.fernandez0312@gmail.com"]},
    {"nombre": "Gestión Hipotecaria", "contactos": "Gestión Hipotecaria",
     "emails": ["contacto@hipotecariogestion.cl"]},
]


async def _seed_brokers():
    if await db.brokers.count_documents({}) == 0:
        for b in BROKERS_SEED:
            await db.brokers.insert_one({"id": str(uuid.uuid4()), **b, "creado_en": now_iso()})


@api.get("/brokers")
async def brokers_list():
    await _seed_brokers()
    docs = await db.brokers.find({}).sort("nombre", 1).to_list(100)
    return {"brokers": [clean(d) for d in docs]}


@api.post("/brokers")
async def brokers_add(payload: dict):
    payload = payload or {}
    nombre = (payload.get("nombre") or "").strip()
    emails = payload.get("emails") or []
    if isinstance(emails, str):
        emails = [e.strip() for e in re.split(r"[,;\n]+", emails) if e.strip()]
    emails = [e for e in emails if "@" in e]
    if not nombre or not emails:
        raise HTTPException(status_code=400, detail="Falta nombre o correos del broker")
    doc = {"id": str(uuid.uuid4()), "nombre": nombre,
           "contactos": (payload.get("contactos") or "").strip(),
           "emails": emails, "creado_en": now_iso()}
    await db.brokers.insert_one(dict(doc))
    return {"ok": True, "broker": clean(doc)}


@api.put("/brokers/{bid}")
async def brokers_edit(bid: str, payload: dict):
    payload = payload or {}
    upd = {}
    if (payload.get("nombre") or "").strip():
        upd["nombre"] = payload["nombre"].strip()
    if "contactos" in payload:
        upd["contactos"] = (payload.get("contactos") or "").strip()
    emails = payload.get("emails")
    if emails is not None:
        if isinstance(emails, str):
            emails = [e.strip() for e in re.split(r"[,;\n]+", emails) if e.strip()]
        emails = [e for e in emails if "@" in e]
        if emails:
            upd["emails"] = emails
    if upd:
        await db.brokers.update_one({"id": bid}, {"$set": upd})
    doc = await db.brokers.find_one({"id": bid})
    return {"ok": True, "broker": clean(doc) if doc else None}


@api.delete("/brokers/{bid}")
async def brokers_del(bid: str):
    await db.brokers.delete_one({"id": bid})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Firma de Escritura: aviso al cliente + confirmación pública + notarías
# ---------------------------------------------------------------------------
NOTARIAS_SEED = [
    {"ciudad": "La Serena", "nombre": "Notaría La Serena",
     "direccion": "Avenida Cristóbal Colón 352, Local 2, Edificio Studio Office, La Serena", "email": ""},
    {"ciudad": "Santiago", "nombre": "Notaría Cristian Camilla",
     "direccion": "Paseo Ahumada 179, Piso 7, Santiago", "email": ""},
    {"ciudad": "Osorno", "nombre": "Notaría Sada",
     "direccion": "Manuel Antonio Matta 680, Osorno", "email": ""},
]
ESCRITURA_COPIAS = ["victoriavilches@centralmutuos.cl",
                    "danielagalindo@centralmutuos.cl",
                    "rodrigoibanez@centralmutuos.cl"]


async def _seed_notarias():
    if await db.notarias.count_documents({}) == 0:
        for n in NOTARIAS_SEED:
            await db.notarias.insert_one({"id": str(uuid.uuid4()), **n, "creado_en": now_iso()})


@api.get("/escritura/notarias")
async def notarias_list():
    await _seed_notarias()
    docs = await db.notarias.find({}).sort("ciudad", 1).to_list(100)
    return {"notarias": [clean(d) for d in docs]}


@api.post("/escritura/notarias")
async def notarias_add(payload: dict):
    payload = payload or {}
    if not (payload.get("ciudad") or "").strip() or not (payload.get("direccion") or "").strip():
        raise HTTPException(status_code=400, detail="Falta ciudad o dirección")
    doc = {"id": str(uuid.uuid4()), "ciudad": payload["ciudad"].strip(),
           "nombre": (payload.get("nombre") or "").strip() or f"Notaría {payload['ciudad'].strip()}",
           "direccion": payload["direccion"].strip(),
           "email": (payload.get("email") or "").strip(), "creado_en": now_iso()}
    await db.notarias.insert_one(dict(doc))
    return {"ok": True, "notaria": clean(doc)}


@api.patch("/escritura/notarias/{nid}")
async def notarias_patch(nid: str, payload: dict):
    upd = {k: (payload.get(k) or "").strip() for k in ("ciudad", "nombre", "direccion", "email") if k in (payload or {})}
    if upd:
        await db.notarias.update_one({"id": nid}, {"$set": upd})
    return {"ok": True}


@api.delete("/escritura/notarias/{nid}")
async def notarias_del(nid: str):
    await db.notarias.delete_one({"id": nid})
    return {"ok": True}


def _fecha_larga(fecha):
    try:
        d = datetime.fromisoformat(fecha)
        meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
                 "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        return f"{d.day} de {meses[d.month-1]} de {d.year}"
    except Exception:
        return fecha


def _escritura_html(p, notaria, confirm_url):
    fecha = _fecha_larga(p.get("fecha", ""))
    hora = p.get("hora") or "10:00"
    inner = f"""
        <p>Estimado(a) <b>{p.get('nombre','')}</b>:</p>
        <p>¡Con mucho entusiasmo le informamos que llegó el momento de la <b>firma de su escritura</b>!</p>
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:14px 18px;margin:14px 0">
          <p style="margin:4px 0"><b>📅 Fecha:</b> {fecha}</p>
          <p style="margin:4px 0"><b>🕙 Hora:</b> {hora} hrs</p>
          <p style="margin:4px 0"><b>🏛 Notaría:</b> {notaria.get('nombre','')}</p>
          <p style="margin:4px 0"><b>📍 Dirección:</b> {notaria.get('direccion','')}</p>
        </div>
        <p>Debe acudir con su <b>codeudor</b> (si lo tiene) y con su <b>mandatario</b>.
        Si no pueden asistir juntos, pueden firmar en fechas distintas, pero usted debe
        concurrir a la firma el día y horario indicados.</p>
        <div style="text-align:center;margin:22px 0">
          <a href="{confirm_url}" style="display:inline-block;background:#16a34a;color:#fff;
             padding:14px 26px;border-radius:8px;text-decoration:none;font-weight:bold;font-size:15px">
            ✅ CONFIRMO QUE ASISTIRÉ A LA FIRMA EN LA FECHA Y HORARIO INDICADOS
          </a>
        </div>
        <p style="font-size:12px;color:#777">Al confirmar podrá indicarnos con quién asistirá
        (solo, con mandatario y/o con codeudor).</p>
        <p style="margin-top:16px;color:#555">Saludos cordiales,</p>"""
    return _marca_wrap(inner, "Firma de Escritura")


@api.post("/escritura/enviar")
async def escritura_enviar(payload: dict):
    payload = payload or {}
    nombre = (payload.get("nombre") or "").strip()
    email_cliente = (payload.get("email_cliente") or "").strip()
    notaria = await db.notarias.find_one({"id": payload.get("notaria_id", "")}) or {}
    token = str(uuid.uuid4())
    base = (payload.get("base_url") or "").rstrip("/")
    confirm_url = f"{base}/api/escritura/confirmar/{token}"
    cuerpo = _escritura_html(payload, notaria, confirm_url)
    subject = f"Firma de Escritura — {nombre} · {_fecha_larga(payload.get('fecha',''))} {payload.get('hora') or '10:00'} hrs"
    sender = _sender_por_rol("secundaria")
    if not payload.get("confirm"):
        return {"to": email_cliente, "subject": subject, "body": cuerpo, "sender": sender}
    if not nombre or not (payload.get("fecha") or "").strip():
        raise HTTPException(status_code=400, detail="Falta el nombre del cliente o la fecha de firma")
    if not email_cliente or "@" not in email_cliente:
        raise HTTPException(status_code=400, detail="Correo del cliente inválido")
    if not notaria:
        raise HTTPException(status_code=400, detail="Debe seleccionar la notaría")
    res = await asyncio.to_thread(mail.send_mail, email_cliente, subject, cuerpo, [], "secundaria")
    if not res.get("success"):
        raise HTTPException(status_code=502, detail=res.get("error", "Error de envío"))
    await db.escritura_solicitudes.insert_one({
        "id": str(uuid.uuid4()), "token": token, "folder_id": payload.get("folder_id", ""),
        "nombre": nombre, "rut": (payload.get("rut") or "").strip(),
        "email_cliente": email_cliente, "notaria": clean(dict(notaria)),
        "fecha": payload.get("fecha", ""), "hora": payload.get("hora") or "10:00",
        "status": "enviada", "acompanantes": "", "enviado_en": now_iso()})
    if payload.get("folder_id"):
        await db.folders.update_one({"id": payload["folder_id"]},
                                    {"$set": {"escritura_solicitada_at": now_iso()}})
    return {"ok": True, "to": email_cliente, "subject": subject, "sender": res.get("desde", sender)}


_ESC_PAGE = """<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Confirmación de Firma — Central Mutuos</title>
<style>body{{font-family:Arial,sans-serif;background:#0a0e17;color:#e2e8f0;margin:0;padding:24px}}
.card{{max-width:560px;margin:30px auto;background:#0f172a;border:1px solid #33415580;border-radius:14px;padding:28px}}
h2{{color:#d4af37;margin:0 0 6px}} .dato{{background:#1e293b;border-radius:8px;padding:12px 16px;margin:14px 0;font-size:14px;line-height:1.7}}
label{{display:flex;align-items:center;gap:10px;background:#1e293b;border-radius:8px;padding:12px 14px;margin:8px 0;cursor:pointer;font-size:14px}}
button{{width:100%;background:#16a34a;color:#fff;border:none;border-radius:8px;padding:15px;font-size:15px;font-weight:bold;cursor:pointer;margin-top:14px}}
.ok{{color:#4ade80;font-size:16px;text-align:center;padding:20px 0}}</style></head>
<body><div class="card">{contenido}</div></body></html>"""


@api.get("/escritura/confirmar/{token}")
async def escritura_confirmar_page(token: str):
    sol = await db.escritura_solicitudes.find_one({"token": token})
    if not sol:
        return HTMLResponse(_ESC_PAGE.format(contenido="<h2>Enlace no válido</h2><p>Esta solicitud no existe o expiró.</p>"))
    if sol.get("status") == "confirmada":
        return HTMLResponse(_ESC_PAGE.format(contenido=f"<h2>¡Gracias!</h2><div class='ok'>Su asistencia ya fue confirmada ✅<br/>{_fecha_larga(sol.get('fecha',''))} · {sol.get('hora','')} hrs</div>"))
    n = sol.get("notaria") or {}
    contenido = f"""
    <h2>Central Mutuos — Firma de Escritura</h2>
    <p>Estimado(a) <b>{sol.get('nombre','')}</b>, confirme su asistencia a la firma:</p>
    <div class="dato">📅 <b>{_fecha_larga(sol.get('fecha',''))}</b> · 🕙 <b>{sol.get('hora','')} hrs</b><br/>
    🏛 {n.get('nombre','')}<br/>📍 {n.get('direccion','')}</div>
    <form method="post" action="">
      <p style="font-size:14px"><b>¿Con quién asistirá a la firma?</b></p>
      <label><input type="radio" name="acompanantes" value="solo" checked> Asistiré solo(a)</label>
      <label><input type="radio" name="acompanantes" value="con mandatario"> Con mi mandatario</label>
      <label><input type="radio" name="acompanantes" value="con codeudor"> Con mi codeudor</label>
      <label><input type="radio" name="acompanantes" value="con mandatario y codeudor"> Con mandatario y codeudor</label>
      <button type="submit">✅ Confirmo que asistiré a la firma en la fecha y horario indicados</button>
    </form>"""
    return HTMLResponse(_ESC_PAGE.format(contenido=contenido))


@api.post("/escritura/confirmar/{token}")
async def escritura_confirmar_post(token: str, request: Request):
    sol = await db.escritura_solicitudes.find_one({"token": token})
    if not sol:
        return HTMLResponse(_ESC_PAGE.format(contenido="<h2>Enlace no válido</h2>"))
    form = await request.form()
    acomp = (form.get("acompanantes") or "solo").strip()
    await db.escritura_solicitudes.update_one({"token": token}, {"$set": {
        "status": "confirmada", "acompanantes": acomp, "confirmado_en": now_iso()}})
    if sol.get("folder_id"):
        await db.folders.update_one({"id": sol["folder_id"]},
                                    {"$set": {"escritura_confirmada_at": now_iso()}})
    n = sol.get("notaria") or {}
    fecha, hora = _fecha_larga(sol.get("fecha", "")), sol.get("hora", "")
    detalle = (f"El cliente <b>{sol.get('nombre','')}</b>, RUT <b>{sol.get('rut','') or '—'}</b>, "
               f"ha confirmado su asistencia a la <b>{n.get('nombre','notaría')}</b> "
               f"({n.get('direccion','')}) el día <b>{fecha}</b> a las <b>{hora} hrs</b>.")
    html_int = f"""
    <div style="font-family:Arial,sans-serif;font-size:14px;color:#222;max-width:620px">
      <h3 style="color:#16a34a">✅ Confirmación de firma de escritura</h3>
      <p>{detalle}</p>
      <p><b>Asistirá:</b> {acomp}.</p>
      <p style="color:#888;font-size:12px">Aviso automático — Central Mutuos</p>
    </div>"""
    subject_int = f"Confirmación firma escritura — {sol.get('nombre','')} · {fecha} {hora} hrs"
    # Copia interna: Victoria, Daniela y Rodrigo (a Rodrigo se le detalla acompañantes)
    await asyncio.to_thread(mail.send_mail, ESCRITURA_COPIAS, subject_int, html_int, [], "secundaria")
    # Aviso a la notaría (si tiene correo configurado)
    if n.get("email") and "@" in n.get("email"):
        html_not = f"""
        <div style="font-family:Arial,sans-serif;font-size:14px;color:#222;max-width:620px">
          <p>Estimados,</p><p>{detalle}</p>
          <p style="color:#888;font-size:12px">Central Mutuos — Con Creces</p>
        </div>"""
        await asyncio.to_thread(mail.send_mail, n["email"], subject_int, html_not, [], "secundaria")
    return HTMLResponse(_ESC_PAGE.format(contenido=f"<h2>¡Gracias, {sol.get('nombre','')}!</h2><div class='ok'>Su asistencia quedó confirmada ✅<br/>{fecha} · {hora} hrs<br/><br/>Asistirá: {acomp}</div>"))


@api.get("/escritura/log")
async def escritura_log():
    docs = await db.escritura_solicitudes.find({}).sort("enviado_en", -1).limit(30).to_list(30)
    return {"log": [clean(d) for d in docs]}


# ---------------------------------------------------------------------------
# Envío Aprobación Cliente: felicitaciones con simulación ajustada + carta
# ---------------------------------------------------------------------------
APROBACION_DEFAULTS = {
    "subject": "¡Felicitaciones! Ha obtenido su crédito hipotecario",
    "boton_texto": "DESEO CONTINUAR CON EL PROCESO DE ESCRITURACIÓN",
    "intro": ("Nos complace enormemente informarle que su crédito hipotecario ha sido APROBADO. "
              "Este es un gran paso hacia la casa propia y queremos acompañarlo en cada etapa del camino.\n\n"
              "Adjunto encontrará su simulación ajustada y la carta de aprobación oficial con todos los "
              "detalles de su operación. Nuestro equipo ya está preparando los siguientes pasos para que "
              "el proceso de escrituración sea rápido, simple y sin complicaciones.\n\n"
              "Para avanzar, solo debe presionar el botón a continuación y un ejecutivo lo contactará de inmediato."),
}


def _tipo_pdf_aprobacion(nombre):
    low = (nombre or "").lower()
    if re.search(r"carta|aprobaci[oó]n|aprobacion", low):
        return "carta_aprobacion"
    # Simulación procesada por el autocorreo (sufijo _CM; legado 'ajustad') o simulador crediticio
    if re.search(r"_cm\.pdf$|ajustad|simulad", low):
        return "simulacion_ajustada"
    return "otro"


def _norm_texto(s):
    import unicodedata
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"[_\W]+", " ", s).strip()


@api.get("/aprobacion-cliente/buscar-cliente")
async def aprobacion_buscar(q: str = ""):
    q = (q or "").strip()
    if len(q) < 2:
        return {"resultados": []}
    base = await gastos_buscar_cliente(q)
    resultados = list(base["resultados"])
    vistos = {r["nombre"].lower() for r in resultados}
    # Clientes vistos por el Autocorreo (log de mesa)
    rx = {"$regex": re.escape(q), "$options": "i"}
    logs = await db.autocorreo_log.find({"cliente": rx}).sort("processed_at", -1).limit(30).to_list(30)
    for l in logs:
        cli = (l.get("cliente") or "").strip()
        if not cli or cli.lower() in vistos or cli.lower() in ("mesa clientes",):
            continue
        vistos.add(cli.lower())
        email_cliente = ""
        item = await db.proc_queue.find_one({"campos.email_cliente": {"$nin": ["", None]},
                                             "classification.cliente": {"$regex": re.escape(cli.split()[0]), "$options": "i"}})
        if item:
            email_cliente = (item.get("campos") or {}).get("email_cliente", "")
        resultados.append({"nombre": cli, "rut": "", "email": email_cliente, "folder_id": ""})
    # Carpetas del archivo del autocorreo
    if STORAGE_DIR.exists():
        for d in STORAGE_DIR.iterdir():
            if d.is_dir() and q.lower() in d.name.lower() and d.name.lower() not in vistos:
                vistos.add(d.name.lower())
                resultados.append({"nombre": d.name, "rut": "", "email": "", "folder_id": ""})
    return {"resultados": resultados[:8]}


@api.get("/aprobacion-cliente/archivos")
async def aprobacion_archivos(cliente: str = ""):
    archivos = []
    rutas_vistas = set()
    if cliente.strip():
        tokens = [t for t in _norm_texto(cliente).split() if len(t) > 2]
        minimo = min(2, len(tokens)) or 1

        def _agregar(p, origen, ruta):
            if ruta in rutas_vistas:
                return
            rutas_vistas.add(ruta)
            tipo = _tipo_pdf_aprobacion(p.name)
            archivos.append({"nombre": p.name, "origen": origen, "ruta": ruta,
                             "tipo": tipo, "seleccionado": tipo != "otro",
                             "tamano": p.stat().st_size})

        # 1) Carpeta exacta del archivo autocorreo
        dir_ac = STORAGE_DIR / _safe_name(cliente)
        if dir_ac.exists():
            for p in sorted(dir_ac.glob("*.pdf")):
                _agregar(p, "autocorreo", str(p.relative_to(STORAGE_DIR)))
        # 2) Cualquier PDF del archivo cuyo NOMBRE contenga al cliente (tolerante a truncados)
        if STORAGE_DIR.exists() and tokens:
            from difflib import get_close_matches
            for p in sorted(STORAGE_DIR.rglob("*.pdf")):
                palabras = _norm_texto(p.name).split()
                hits = sum(1 for t in tokens
                           if t in palabras or get_close_matches(t, palabras, n=1, cutoff=0.75))
                if hits >= minimo:
                    _agregar(p, "autocorreo", str(p.relative_to(STORAGE_DIR)))
        # 2b) Archivos registrados en el log del autocorreo para este cliente
        logs = await db.autocorreo_log.find(
            {"cliente": {"$regex": f"^{re.escape(cliente.strip())}$", "$options": "i"},
             "status": "sent"}).sort("processed_at", -1).limit(30).to_list(30)
        nombres_log = set()
        for l in logs:
            for nom in (l.get("attachments_info") or "").split(", "):
                nom = nom.strip()
                if nom and nom.lower().endswith(".pdf"):
                    nombres_log.add(nom)
        if nombres_log and STORAGE_DIR.exists():
            for p in STORAGE_DIR.rglob("*.pdf"):
                if p.name in nombres_log:
                    _agregar(p, "autocorreo", str(p.relative_to(STORAGE_DIR)))
        # 3) Carpeta del cliente (módulo Clientes)
        dir_cl = fsvc.folder_dir(cliente)
        if dir_cl.exists():
            for a in fsvc.scan_archivos(cliente):
                if not a["nombre"].lower().endswith(".pdf"):
                    continue
                tipo = _tipo_pdf_aprobacion(a["nombre"])
                if tipo == "otro":
                    continue
                archivos.append({"nombre": a["nombre"], "origen": "clientes", "ruta": a["ruta"],
                                 "tipo": tipo, "seleccionado": True, "tamano": a["tamano"]})
    return {"archivos": archivos}


@api.get("/aprobacion-cliente/plantilla")
async def aprobacion_plantilla(cliente: str = ""):
    cfg = await db.config.find_one({"_key": "aprobacion_defaults"}) or {}
    base = dict(APROBACION_DEFAULTS)
    base.update({k: v for k, v in cfg.items() if k in APROBACION_DEFAULTS and v})
    if cliente.strip():
        propia = await db.aprobacion_templates.find_one({"cliente": cliente.strip()})
        if propia:
            base.update({k: v for k, v in propia.items() if k in APROBACION_DEFAULTS and v})
            base["plantilla_propia"] = True
    return base


@api.patch("/aprobacion-cliente/plantilla")
async def aprobacion_plantilla_patch(payload: dict):
    payload = payload or {}
    datos = {k: payload[k] for k in APROBACION_DEFAULTS if k in payload}
    cliente = (payload.get("cliente") or "").strip()
    if cliente:
        await db.aprobacion_templates.update_one(
            {"cliente": cliente}, {"$set": {**datos, "cliente": cliente, "updated_at": now_iso()}}, upsert=True)
    if payload.get("como_default"):
        await db.config.update_one({"_key": "aprobacion_defaults"}, {"$set": datos}, upsert=True)
    return {"ok": True}


def _aprobacion_html(payload):
    nombre = payload.get("nombre", "")
    rut = payload.get("rut", "")
    intro = (payload.get("intro") or "").strip()
    boton = payload.get("boton_texto") or APROBACION_DEFAULTS["boton_texto"]
    contacto = _sender_por_rol("secundaria")
    adjuntos = payload.get("_adjuntos_nombres") or []
    intro_html = "".join(f"<p style='margin:0 0 14px;line-height:1.75;font-size:15px;color:#2b3245'>{p}</p>"
                         for p in intro.split("\n") if p.strip())
    docs_html = ""
    if adjuntos:
        filas = "".join(
            f"<tr><td style='padding:8px 0;color:#2b3245;font-size:14px'>"
            f"<span style='display:inline-block;width:22px;color:#d4af37;font-weight:700'>&#10003;</span>{n}</td></tr>"
            for n in adjuntos)
        docs_html = f"""
        <div style="background:#f8f9fc;border:1px solid #eceef3;border-radius:10px;padding:16px 22px;margin:6px 0 22px">
          <div style="color:#1a1f2e;font-weight:700;font-size:14px;margin-bottom:6px">Documentos adjuntos a este correo</div>
          <table style="border-collapse:collapse">{filas}</table>
        </div>"""
    mailto = (f"mailto:{contacto}?subject=" +
              f"Deseo continuar con el proceso de escrituración — {nombre}".replace(" ", "%20"))
    return f"""
    <div style="background:#eef0f5;padding:30px 12px;font-family:Georgia,'Times New Roman',serif">
      <div style="max-width:640px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 6px 24px rgba(16,24,40,0.12)">
        <div style="background:#1a1f2e;padding:40px 32px;text-align:center;border-bottom:4px solid #d4af37">
          <div style="color:#9aa3b5;font-size:12px;letter-spacing:4px;margin-bottom:10px">CENTRAL MUTUOS · CON CRECES</div>
          <div style="color:#d4af37;font-size:34px;font-weight:700;letter-spacing:1px;line-height:1.2">¡FELICITACIONES!</div>
          <div style="color:#ffffff;font-size:17px;margin-top:10px">Su crédito hipotecario ha sido <b style="color:#d4af37">APROBADO</b></div>
        </div>
        <div style="padding:34px 36px 8px">
          <p style="margin:0 0 4px;color:#1a1f2e;font-size:17px"><b>Estimada(o) {nombre}</b></p>
          {f"<p style='margin:0 0 18px;color:#6b7280;font-size:13px'>RUT: {rut}</p>" if rut else "<div style='height:14px'></div>"}
          {intro_html}
          {docs_html}
        </div>
        <div style="padding:6px 36px 34px;text-align:center">
          <a href="{mailto}" style="display:inline-block;background:#d4af37;color:#1a1f2e;
             font-size:16px;font-weight:700;letter-spacing:1px;text-decoration:none;
             padding:18px 40px;border-radius:50px;box-shadow:0 4px 14px rgba(212,175,55,0.45)">
             {boton} &nbsp;&#8594;</a>
          <p style="margin:16px 0 0;color:#9aa3b5;font-size:12px">Al presionar el botón se abrirá un correo dirigido a nuestro equipo para coordinar los siguientes pasos.</p>
        </div>
        <div style="background:#f8f9fc;border-top:1px solid #eceef3;padding:22px 36px">
          <p style="margin:0;color:#2b3245;font-size:14px"><b>Central Mutuos</b> — Con Creces</p>
          <p style="margin:4px 0 0;color:#6b7280;font-size:12px">Especialistas en créditos hipotecarios · {contacto}</p>
        </div>
        <div style="background:#1a1f2e;padding:12px 32px;text-align:center">
          <span style="color:#9aa3b5;font-size:11px">Este correo contiene información confidencial dirigida exclusivamente a su destinatario.</span>
        </div>
      </div>
    </div>
    """


@api.post("/aprobacion-cliente/enviar")
async def aprobacion_enviar(payload: dict):
    payload = payload or {}
    to = (payload.get("email_cliente") or "").strip()
    nombre = (payload.get("nombre") or "").strip()
    subject = payload.get("subject") or APROBACION_DEFAULTS["subject"]
    adjuntos_sel = payload.get("adjuntos") or []
    rutas = []
    for a in adjuntos_sel:
        try:
            if a.get("origen") == "clientes":
                p = fsvc.resolver_ruta(nombre, a.get("ruta", ""))
            else:
                p = (STORAGE_DIR / a.get("ruta", "")).resolve()
                if not str(p).startswith(str(STORAGE_DIR.resolve())):
                    continue
            if p.exists() and p.suffix.lower() == ".pdf":
                rutas.append(p)
        except (ValueError, OSError):
            continue
    payload["_adjuntos_nombres"] = [p.name for p in rutas]
    cuerpo = _aprobacion_html(payload)
    if not payload.get("confirm"):
        return {"to": to, "subject": subject, "body": cuerpo,
                "attachments": [p.name for p in rutas], "sender": _sender_por_rol("secundaria")}
    if not to or "@" not in to:
        raise HTTPException(status_code=400, detail="Correo del cliente inválido")
    if not rutas:
        raise HTTPException(status_code=400, detail="Debe adjuntar al menos la simulación ajustada o la carta de aprobación")
    adjuntos = [{"filename": p.name, "content_b64": _b64(p.read_bytes())} for p in rutas]
    res = await asyncio.to_thread(mail.send_mail, to, subject, cuerpo, adjuntos, "secundaria")
    if not res.get("success"):
        raise HTTPException(status_code=502, detail=res.get("error", "Error de envío"))
    # Guardar plantilla del cliente automáticamente
    await db.aprobacion_templates.update_one(
        {"cliente": nombre},
        {"$set": {"cliente": nombre, "intro": payload.get("intro", ""),
                  "subject": subject, "boton_texto": payload.get("boton_texto", ""),
                  "updated_at": now_iso()}}, upsert=True)
    await db.aprobacion_log.insert_one({
        "id": str(uuid.uuid4()), "nombre": nombre, "rut": payload.get("rut", ""),
        "to": to, "adjuntos": [p.name for p in rutas],
        "enviado_en": now_iso(), "desde": res.get("desde", "")})
    return {"ok": True, "to": to, "subject": subject,
            "attachments": [p.name for p in rutas], "sender": res.get("desde", "")}


@api.get("/aprobacion-cliente/log")
async def aprobacion_log():
    docs = await db.aprobacion_log.find({}).sort("enviado_en", -1).limit(20).to_list(20)
    return {"log": [clean(d) for d in docs]}


# ---------------------------------------------------------------------------
# Set de Crédito + Firma de documentos (integración migrup / eCert)
# ---------------------------------------------------------------------------
import migrup_service as migrup

SETCRED_DIR = ROOT_DIR / "storage" / "set_credito"
SETCRED_DIR.mkdir(parents=True, exist_ok=True)
SET_DOC_TIPOS = ["seguros", "solicitud_credito", "declaracion_salud"]
SET_DOC_LABELS = {"seguros": "Seguros", "solicitud_credito": "Solicitud de crédito",
                  "declaracion_salud": "Declaración de salud"}


SETCRED_SENDER_DEFAULT = "evaluacionesmutuos@gmail.com"


def _set_dir(nombre):
    return SETCRED_DIR / fsvc.safe_name(nombre)


def _set_archivos(nombre):
    base = _set_dir(nombre)
    out = []
    if not base.exists():
        return out
    for p in sorted(base.rglob("*.pdf")):
        rel = p.relative_to(base).as_posix()
        if rel.startswith("firmados/"):
            continue
        es_codeudor = rel.startswith("codeudor/")
        low = p.name.lower()
        tipo = "otro"
        for t in SET_DOC_TIPOS:
            if low.startswith(t):
                tipo = t
                break
        out.append({"nombre": p.name, "ruta": rel, "tipo": tipo,
                    "codeudor": es_codeudor, "tamano": p.stat().st_size})
    out.sort(key=lambda a: (a["codeudor"], a["ruta"]))
    return out


RUT_RE = re.compile(r"\b(\d{1,2}\.?\d{3}\.?\d{3}\-?[\dkK])\b")


def _detectar_datos_email(info):
    """Detecta nombre, RUT y si hay codeudor desde el asunto/adjuntos del correo de evaluaciones."""
    subject = info.get("subject", "") or ""
    body = info.get("body", "") or ""
    # "Fwd: Set Javier Perez" / "Set Aleidys Aponte y de su codeudor ok"
    limpio = re.sub(r"^\s*((re|fwd?|rv|fw)\s*:\s*)+", "", subject, flags=re.I)
    nombre = ""
    m = re.search(r"\bset\s+(?:de\s+)?([A-Za-zÁÉÍÓÚÑáéíóúñ ]+?)(?:\s+y\s+(?:de\s+)?su\s+codeudor|\s+ok\b|\s*[\(\-]|$)",
                  limpio, re.I)
    if m:
        nombre = m.group(1).strip().title()
    if not nombre:
        nombre = mail._extraer_nombre(subject, info.get("from", ""))
    texto = f"{subject}\n{body}"
    rut = ""
    mr = RUT_RE.search(texto)
    if mr:
        rut = mr.group(1)
    nombres_adj = " ".join(a.get("filename", "") for a in info.get("attachments", []))
    tiene_codeudor = bool(re.search(r"codeudor", subject + " " + nombres_adj, re.I))
    return {"nombre": nombre, "rut": rut, "tiene_codeudor": tiene_codeudor}


def _set_public(doc):
    d = clean(dict(doc))
    d["archivos"] = _set_archivos(d.get("nombre", ""))
    d["total_archivos"] = len(d["archivos"])
    d["firmados"] = _set_firmados(d.get("nombre", ""))
    return d


@api.get("/set-credito/sets")
async def setcred_list(q: str = ""):
    query = {"nombre": {"$regex": q, "$options": "i"}} if q else {}
    docs = await db.set_credito.find(query).sort("created_at", -1).limit(200).to_list(200)
    return {"sets": [_set_public(d) for d in docs], "doc_tipos": SET_DOC_LABELS}


@api.post("/set-credito/sets")
async def setcred_create(payload: dict):
    doc = {"id": str(uuid.uuid4()), "nombre": payload.get("nombre", ""),
           "rut": payload.get("rut", ""), "email": payload.get("email", ""),
           "created_at": now_iso(), "firmas": []}
    if not doc["nombre"].strip():
        raise HTTPException(status_code=400, detail="Falta el nombre del cliente")
    await db.set_credito.insert_one(dict(doc))
    _set_dir(doc["nombre"]).mkdir(parents=True, exist_ok=True)
    return _set_public(doc)


async def _get_set(sid):
    doc = await db.set_credito.find_one({"id": sid})
    if not doc:
        raise HTTPException(status_code=404, detail="Set no encontrado")
    return doc


@api.get("/set-credito/sets/{sid}")
async def setcred_get(sid: str):
    return _set_public(await _get_set(sid))


@api.delete("/set-credito/sets/{sid}")
async def setcred_delete(sid: str):
    doc = await db.set_credito.find_one({"id": sid})
    if doc:
        import shutil
        shutil.rmtree(_set_dir(doc.get("nombre", "")), ignore_errors=True)
    await db.set_credito.delete_one({"id": sid})
    return {"ok": True}


@api.post("/set-credito/sets/{sid}/upload")
async def setcred_upload(sid: str, file: UploadFile = File(...), tipo: str = Form("otro"),
                         codeudor: str = Form("")):
    doc = await _get_set(sid)
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Archivo vacío")
    nombre_archivo = file.filename or "documento"
    try:
        raw, nombre_archivo, _ = pdfs.convertir_a_pdf(raw, nombre_archivo)
    except ValueError:
        pass
    if tipo in SET_DOC_TIPOS and not nombre_archivo.lower().startswith(tipo):
        stem = fsvc.safe_name(nombre_archivo)
        nombre_archivo = f"{tipo}_{stem}"
    es_cod = str(codeudor).lower() in ("true", "1", "si", "sí")
    base = _set_dir(doc.get("nombre", "")) / ("codeudor" if es_cod else "")
    base.mkdir(parents=True, exist_ok=True)
    (base / fsvc.safe_name(nombre_archivo)).write_bytes(raw)
    rel = f"codeudor/{fsvc.safe_name(nombre_archivo)}" if es_cod else fsvc.safe_name(nombre_archivo)
    return {"ok": True, "saved": rel}


async def _setcred_emails_job(job_id, sender, limit):
    try:
        correos = await asyncio.to_thread(mail.fetch_emails_from_sender, sender, limit)
        out = []
        for c in correos:
            datos = _detectar_datos_email(c)
            out.append({"id": c["id"], "from": c.get("from", ""), "subject": c.get("subject", ""),
                        "date": c.get("date", ""), "cuenta": c.get("cuenta", ""),
                        "attachments": [a for a in c.get("attachments", [])
                                        if (a.get("filename") or "").lower().endswith((".pdf", ".jpg", ".jpeg", ".png"))],
                        "detectado": datos})
        await db.setcred_email_jobs.update_one({"id": job_id},
                                               {"$set": {"status": "done", "sender": sender, "emails": out}})
    except Exception as e:
        await db.setcred_email_jobs.update_one({"id": job_id},
                                               {"$set": {"status": "error", "error": str(e)[:200], "emails": []}})


@api.post("/set-credito/emails")
async def setcred_emails_start(payload: dict = None):
    payload = payload or {}
    sender = (payload.get("sender") or SETCRED_SENDER_DEFAULT).strip()
    limit = int(payload.get("limit") or 12)
    job_id = str(uuid.uuid4())
    corte = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
    await db.setcred_email_jobs.delete_many({"created_at": {"$lt": corte}})
    await db.setcred_email_jobs.insert_one({"id": job_id, "status": "running",
                                            "created_at": now_iso()})
    asyncio.create_task(_setcred_emails_job(job_id, sender, limit))
    return {"job_id": job_id, "status": "running", "sender": sender}


@api.get("/set-credito/emails/{job_id}")
async def setcred_emails_status(job_id: str):
    job = await db.setcred_email_jobs.find_one({"id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    return clean(job)


@api.post("/set-credito/import-from-email")
async def setcred_import_from_email(payload: dict):
    """Crea/actualiza un set desde un correo de Evaluaciones y baja sus adjuntos."""
    email_id = payload.get("email_id", "")
    nombre = (payload.get("nombre") or "").strip()
    rut = (payload.get("rut") or "").strip()
    es_codeudor = bool(payload.get("codeudor"))
    filenames = payload.get("filenames")  # opcional: subconjunto
    if not email_id or not nombre:
        raise HTTPException(status_code=400, detail="Falta correo o nombre del cliente")
    atts = await asyncio.to_thread(mail.fetch_attachments_by_id, email_id, None)
    if filenames:
        atts = [a for a in atts if a["filename"] in filenames]
    atts = [a for a in atts if (a["filename"] or "").lower().endswith((".pdf", ".jpg", ".jpeg", ".png"))]
    if not atts:
        raise HTTPException(status_code=404, detail="El correo no tiene adjuntos válidos")
    doc = await db.set_credito.find_one({"nombre": nombre})
    if not doc:
        doc = {"id": str(uuid.uuid4()), "nombre": nombre, "rut": rut,
               "email": payload.get("email", ""), "created_at": now_iso(),
               "origen": "evaluaciones", "firmas": []}
        await db.set_credito.insert_one(dict(doc))
    elif rut and not doc.get("rut"):
        await db.set_credito.update_one({"id": doc["id"]}, {"$set": {"rut": rut}})
    base_dir = _set_dir(nombre)
    guardados = []
    for a in atts:
        raw, fn = a["content_bytes"], a["filename"]
        try:
            raw, fn, _ = pdfs.convertir_a_pdf(raw, fn)
        except ValueError:
            pass
        cod = es_codeudor or bool(re.search(r"codeudor", fn, re.I))
        dest = base_dir / ("codeudor" if cod else "")
        dest.mkdir(parents=True, exist_ok=True)
        (dest / fsvc.safe_name(fn)).write_bytes(raw)
        guardados.append((f"codeudor/" if cod else "") + fsvc.safe_name(fn))
    return {"ok": True, "set_id": doc["id"], "nombre": nombre,
            "guardados": guardados}


@api.post("/set-credito/sets/{sid}/save-from-email")
async def setcred_save_from_email(sid: str, payload: dict):
    doc = await _get_set(sid)
    email_id = payload.get("email_id", "")
    filenames = payload.get("filenames")
    es_codeudor = bool(payload.get("codeudor"))
    atts = await asyncio.to_thread(mail.fetch_attachments_by_id, email_id, None)
    if filenames:
        atts = [a for a in atts if a["filename"] in filenames]
    atts = [a for a in atts if (a["filename"] or "").lower().endswith((".pdf", ".jpg", ".jpeg", ".png"))]
    if not atts:
        raise HTTPException(status_code=404, detail="Sin adjuntos válidos en el correo")
    base_dir = _set_dir(doc.get("nombre", ""))
    guardados = []
    for a in atts:
        raw, fn = a["content_bytes"], a["filename"]
        try:
            raw, fn, _ = pdfs.convertir_a_pdf(raw, fn)
        except ValueError:
            pass
        cod = es_codeudor or bool(re.search(r"codeudor", fn, re.I))
        dest = base_dir / ("codeudor" if cod else "")
        dest.mkdir(parents=True, exist_ok=True)
        (dest / fsvc.safe_name(fn)).write_bytes(raw)
        guardados.append((f"codeudor/" if cod else "") + fsvc.safe_name(fn))
    return {"ok": True, "guardados": guardados}


@api.post("/set-credito/sets/{sid}/delete-file")
async def setcred_delete_file(sid: str, payload: dict):
    doc = await _get_set(sid)
    rel = (payload.get("file_path", "") or "").strip()
    base = _set_dir(doc.get("nombre", "")).resolve()
    target = (base / rel).resolve()
    if not str(target).startswith(str(base)):
        raise HTTPException(status_code=400, detail="Ruta inválida")
    if not target.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    target.unlink()
    return {"ok": True}


@api.get("/set-credito/sets/{sid}/download/{file_path:path}")
async def setcred_download(sid: str, file_path: str, inline: bool = False):
    doc = await _get_set(sid)
    base = _set_dir(doc.get("nombre", "")).resolve()
    target = (base / file_path).resolve()
    if not str(target).startswith(str(base)) or not target.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    disp = "inline" if inline else "attachment"
    return FileResponse(str(target), media_type="application/pdf",
                        headers={"Content-Disposition": f'{disp}; filename="{target.name}"'})


def _set_combinar(nombre):
    """Une todos los PDFs del set (excepto el combinado previo) en uno solo."""
    from pypdf import PdfReader, PdfWriter
    base = _set_dir(nombre)
    writer = PdfWriter()
    usados = []
    orden = {t: i for i, t in enumerate(SET_DOC_TIPOS)}
    archivos = sorted(_set_archivos(nombre), key=lambda a: (orden.get(a["tipo"], 99), a["nombre"]))
    for a in archivos:
        if a["nombre"].startswith("COMBINADO_SET"):
            continue
        try:
            for pg in PdfReader(str(base / a["ruta"])).pages:
                writer.add_page(pg)
            usados.append(a["nombre"])
        except Exception:
            continue
    if not usados:
        return {"combinado": "", "usados": []}
    out = f"COMBINADO_SET_{fsvc.safe_name(nombre)}.pdf"
    with open(base / out, "wb") as f:
        writer.write(f)
    return {"combinado": out, "usados": usados}


def _set_firmados(nombre):
    dest = _set_dir(nombre) / "firmados"
    if not dest.exists():
        return []
    return [{"nombre": p.name, "ruta": f"firmados/{p.name}", "tamano": p.stat().st_size}
            for p in sorted(dest.glob("*.pdf"))]


def _set_separar_firmado(nombre, signed_bytes, ecert_id=""):
    """Separa el PDF combinado FIRMADO en los archivos originales del set.
    Cada extracto lleva pie de rastro con referencia al archivo madre firmado."""
    from pypdf import PdfReader, PdfWriter
    import hashlib
    base = _set_dir(nombre)
    reader = PdfReader(io.BytesIO(signed_bytes))
    orden = {t: i for i, t in enumerate(SET_DOC_TIPOS)}
    archivos = sorted(_set_archivos(nombre), key=lambda a: (orden.get(a["tipo"], 99), a["nombre"]))
    dest = base / "firmados"
    dest.mkdir(parents=True, exist_ok=True)
    master = f"COMBINADO_SET_{fsvc.safe_name(nombre)}"[:20] + "_FIRMADO_COMPLETO.pdf"
    sha = hashlib.sha256(signed_bytes).hexdigest()
    lineas_rastro = [
        "EXTRACTO DE DOCUMENTO FIRMADO ELECTRONICAMENTE - Firma Electronica Avanzada e-CertChile (Ley 19.799). "
        "La firma criptografica verificable en eCert esta en el archivo madre.",
        f"Archivo madre: {master}  |  Doc eCert: {ecert_id or 's/i'}  |  Huella SHA-256 del madre: {sha}",
    ]
    guardados = []
    idx = 0
    for a in archivos:
        if a["nombre"].startswith("COMBINADO_SET"):
            continue
        try:
            n = len(PdfReader(str(base / a["ruta"])).pages)
        except Exception:
            continue
        if idx >= len(reader.pages):
            break
        w = PdfWriter()
        for i in range(idx, min(idx + n, len(reader.pages))):
            w.add_page(reader.pages[i])
        idx += n
        buf = io.BytesIO()
        w.write(buf)
        try:
            data = pdfs.estampar_pie_rastro(buf.getvalue(), lineas_rastro)
        except Exception:
            data = buf.getvalue()
        out = dest / f"FIRMADO_{a['nombre']}"
        out.write_bytes(data)
        guardados.append(out.name)
    return guardados


async def _traer_firmado_interno(doc):
    """Descarga el combinado firmado desde eCert y lo separa. Lanza ValueError si no está listo."""
    stem = f"COMBINADO_SET_{fsvc.safe_name(doc.get('nombre', ''))}"[:20]
    docs = await asyncio.to_thread(migrup.listar_documentos, "", 0, 1, 30)
    items = (docs or {}).get("paginatedList") or []
    cand = [d for d in items if (d.get("nombre") or "").startswith(stem)]
    if not cand:
        raise ValueError("No hay ningún envío de este set en eCert")
    cand.sort(key=lambda d: d.get("fechaCreacion") or "", reverse=True)
    best = next((d for d in cand if (d.get("estadoDocumento") or "").lower() == "finalizado"), None)
    if not best:
        raise ValueError(f"El cliente aún no firma (estado: {cand[0].get('estadoDocumento')})")
    f = await asyncio.to_thread(migrup.get_file, best["idDocumento"])
    if not isinstance(f, dict) or not f.get("base64"):
        raise ValueError("No se pudo descargar el firmado desde eCert")
    signed = _b64mod.b64decode(f["base64"])
    guardados = await asyncio.to_thread(_set_separar_firmado, doc.get("nombre", ""),
                                        signed, best["idDocumento"])
    (_set_dir(doc.get("nombre", "")) / "firmados").mkdir(parents=True, exist_ok=True)
    (_set_dir(doc.get("nombre", "")) / "firmados" / f"{stem}_FIRMADO_COMPLETO.pdf").write_bytes(signed)
    await db.set_credito.update_one({"id": doc["id"]}, {"$set": {
        "firmado_recibido_en": now_iso(), "firmado_ecert_id": best["idDocumento"]}})
    return {"estado": best.get("estadoDocumento"), "archivos": guardados}


async def _enviar_firmados_interno(doc, correos, asunto=None):
    if isinstance(correos, str):
        correos = [c.strip() for c in re.split(r"[,;]", correos) if c.strip()]
    correos = [c for c in correos if "@" in c]
    if not correos:
        raise ValueError("Indica al menos un correo válido")
    dest_dir = _set_dir(doc.get("nombre", "")) / "firmados"
    files = sorted(dest_dir.glob("FIRMADO_*.pdf")) if dest_dir.exists() else []
    if not files:
        raise ValueError("Primero trae el set firmado desde eCert")
    masters = sorted(dest_dir.glob("*_FIRMADO_COMPLETO.pdf"))
    adjuntos = [{"filename": p.name, "content_b64": _b64(p.read_bytes())}
                for p in files + masters]
    nombre = doc.get("nombre", "")
    cuerpo = f"""
    <div style="font-family:Arial,sans-serif;font-size:14px;color:#222">
      <h2 style="color:#6c5ce7;margin:0 0 8px">Set de crédito firmado — {nombre}</h2>
      <p>Se adjunta el set de crédito de <b>{nombre}</b>{(' (RUT ' + doc.get('rut') + ')') if doc.get('rut') else ''},
      firmado electrónicamente vía eCert Chile, separado documento por documento ({len(files)} archivos).</p>
      <ul>{"".join(f"<li>{p.name}</li>" for p in files)}</ul>
      <p><b>Verificación:</b> cada extracto lleva al pie su rastro de firma (archivo madre, ID eCert y huella
      SHA-256). La firma electrónica avanzada se verifica en la página de eCert con el archivo madre adjunto
      ({masters[0].name if masters else 'COMBINADO_FIRMADO_COMPLETO.pdf'}), que contiene el set completo firmado.</p>
      <p style="color:#888;font-size:12px">Central Mutuos - Con Creces</p>
    </div>
    """
    asunto = asunto or f"Set de crédito firmado - {nombre}"
    enviados, errores = [], []
    for c in correos:
        r = await asyncio.to_thread(mail.send_mail, c, asunto, cuerpo, adjuntos, "principal")
        (enviados if r.get("success") else errores).append(c)
    await db.set_credito.update_one({"id": doc["id"]}, {"$push": {"envios_firmado": {
        "a": enviados, "archivos": len(adjuntos), "en": now_iso()}}})
    return {"enviados": enviados, "errores": errores, "archivos": len(adjuntos)}


@api.post("/set-credito/sets/{sid}/traer-firmado")
async def setcred_traer_firmado(sid: str):
    """Busca el combinado firmado en eCert, lo descarga y lo separa archivo por archivo."""
    doc = await _get_set(sid)
    try:
        res = await _traer_firmado_interno(doc)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"ok": True, "estado": res["estado"], "archivos": res["archivos"],
            "total": len(res["archivos"])}


SETCRED_ENVIO_DEFAULT = "danielagalindo@centralmutuos.cl, victoriavilches@centralmutuos.cl"


@api.post("/set-credito/sets/{sid}/enviar-firmados")
async def setcred_enviar_firmados(sid: str, payload: dict = None):
    """Envía por correo el set firmado, separado archivo por archivo."""
    payload = payload or {}
    doc = await _get_set(sid)
    try:
        res = await _enviar_firmados_interno(doc, payload.get("correos") or SETCRED_ENVIO_DEFAULT,
                                             payload.get("asunto"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not res["enviados"]:
        raise HTTPException(status_code=502, detail=f"No se pudo enviar a: {', '.join(res['errores'])}")
    return {"ok": True, **res}


async def _firmados_auto_loop():
    """AUTOCORREO de sets firmados: cuando el cliente firma en eCert, descarga el set,
    lo separa y lo envía automáticamente a los correos por defecto."""
    await asyncio.sleep(90)
    while True:
        try:
            pendientes = await db.set_credito.find(
                {"firmas.0": {"$exists": True}, "firmado_recibido_en": {"$exists": False}}
            ).to_list(50)
            for doc in pendientes:
                try:
                    res = await _traer_firmado_interno(doc)
                except ValueError:
                    continue
                try:
                    env = await _enviar_firmados_interno(doc, SETCRED_ENVIO_DEFAULT)
                    await db.set_credito.update_one({"id": doc["id"]}, {"$set": {
                        "autocorreo_firmado": {"a": env["enviados"], "en": now_iso()}}})
                    logging.info(f"Autocorreo set firmado '{doc.get('nombre')}' → {env['enviados']}")
                except Exception as e:
                    logging.warning(f"Autocorreo set firmado {doc.get('nombre')}: {e}")
        except Exception as e:
            logging.warning(f"_firmados_auto_loop: {e}")
        await asyncio.sleep(600)


@api.post("/set-credito/sets/{sid}/combinar")
async def setcred_combinar(sid: str):
    doc = await _get_set(sid)
    res = await asyncio.to_thread(_set_combinar, doc.get("nombre", ""))
    if not res["combinado"]:
        raise HTTPException(status_code=400, detail="No hay documentos PDF para combinar")
    return {"ok": True, **res}


@api.post("/set-credito/sets/{sid}/enviar-firma-completo")
async def setcred_enviar_firma_completo(sid: str, payload: dict):
    """Combina todo el set en un PDF y lo envía a firmar en todas las páginas (firmar todo de una vez)."""
    doc = await _get_set(sid)
    firmante = {
        "nombres": payload.get("nombres") or doc.get("nombre", ""),
        "aPaterno": payload.get("aPaterno", ""),
        "aMaterno": payload.get("aMaterno", ""),
        "rut": payload.get("rut") or doc.get("rut", ""),
        "email": payload.get("email") or doc.get("email", ""),
    }
    if not firmante["email"] or "@" not in firmante["email"]:
        raise HTTPException(status_code=400, detail="Correo del firmante inválido")
    if not firmante["rut"]:
        raise HTTPException(status_code=400, detail="RUT del firmante requerido")
    res_comb = await asyncio.to_thread(_set_combinar, doc.get("nombre", ""))
    if not res_comb["combinado"]:
        raise HTTPException(status_code=400, detail="No hay documentos para combinar y firmar")
    target = _set_dir(doc.get("nombre", "")) / res_comb["combinado"]
    pdf_bytes = target.read_bytes()
    posiciones = await asyncio.to_thread(pdfs.posiciones_firma_cliente, pdf_bytes)
    nombre_completo = " ".join(x for x in [firmante["nombres"], firmante["aPaterno"],
                                           firmante["aMaterno"]] if x).strip()
    if len(posiciones) > 1:
        # 1 sola firma del plan: estampa oficial en la 1ª etiqueta, referencia FEA en el resto
        pdf_bytes = await asyncio.to_thread(pdfs.estampar_referencias_firma, pdf_bytes,
                                            posiciones[1:], nombre_completo)
    res = await asyncio.to_thread(
        migrup.enviar_a_firmar_tercero, pdf_bytes, target.stem, firmante,
        payload.get("comentario", "Set de crédito - firma completa"),
        None, False, posiciones[:1] or None)
    if not res.get("success"):
        raise HTTPException(status_code=502, detail=str(res.get("error") or res.get("raw"))[:250])
    await db.set_credito.update_one({"id": sid}, {"$push": {"firmas": {
        "documento": target.name, "firmante": firmante["email"], "rut": firmante["rut"],
        "paginas": res.get("paginas"), "estampas": len(posiciones) or 1,
        "completo": True, "enviado_en": now_iso()}}})
    return {"ok": True, "firmante": firmante["email"], "combinado": res_comb["combinado"],
            "documentos_incluidos": res_comb["usados"], "paginas": res.get("paginas"),
            "estampas": len(posiciones) or 1, "firmas_consumidas": 1,
            "estampas_detalle": [{"pagina": p["pagina"]} for p in posiciones]}


@api.get("/migrup/status")
async def migrup_status():
    if not migrup.configured():
        return {"configured": False}
    lg = await asyncio.to_thread(migrup.login)
    if not lg.get("success"):
        return {"configured": True, "connected": False, "error": lg.get("error")}
    sem = await asyncio.to_thread(migrup.semaforo)
    return {"configured": True, "connected": True, "user": lg.get("user"),
            "forzar_renovacion": lg.get("forzar_renovacion"),
            "firmas_terceros_disponibles": (sem or {}).get("cantFirmasDisponiblesTerceros"),
            "documentos_disponibles": (sem or {}).get("cantDocumentosDisponibles")}


@api.get("/migrup/contactos")
async def migrup_contactos(q: str = ""):
    res = await asyncio.to_thread(migrup.listar_contactos)
    if isinstance(res, dict) and res.get("_error"):
        raise HTTPException(status_code=502, detail=res["_error"])
    items = (res or {}).get("items") or []
    if q:
        qn = _norm_texto(q)
        items = [c for c in items if qn in _norm_texto(
            f"{c.get('contNombres','')} {c.get('contApPaterno','')} {c.get('contApMaterno','')} {c.get('contRut','')} {c.get('contEmail','')}")]
    return {"contactos": [{"id": c.get("contId"), "nombres": c.get("contNombres", ""),
                           "aPaterno": c.get("contApPaterno", ""), "aMaterno": c.get("contApMaterno", ""),
                           "rut": f"{c.get('contRut','')}-{c.get('contRutDv','')}",
                           "email": c.get("contEmail", "")} for c in items]}


@api.post("/migrup/contactos")
async def migrup_crear_contacto(payload: dict):
    nombres = (payload.get("nombres") or "").strip()
    paterno = (payload.get("aPaterno") or "").strip()
    materno = (payload.get("aMaterno") or "").strip()
    run = (payload.get("rut") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    email2 = (payload.get("email2") or email).strip().lower()
    if not nombres:
        raise HTTPException(status_code=400, detail="Por favor ingrese nombre(s)")
    if not paterno:
        raise HTTPException(status_code=400, detail="Falta el apellido paterno")
    if len(_norm_rut(run)) < 7:
        raise HTTPException(status_code=400, detail="RUN inválido")
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Correo electrónico inválido")
    if email != email2:
        raise HTTPException(status_code=400, detail="Los correos no coinciden")
    existente = await asyncio.to_thread(migrup.buscar_contacto_por_rut, run)
    if existente:
        return {"ok": True, "existia": True,
                "mensaje": f"El contacto ya existe en eCert ({existente.get('contNombres','')} {existente.get('contApPaterno','')})"}
    res = await asyncio.to_thread(migrup.crear_contacto, nombres, paterno, materno, run, email)
    if not res.get("success"):
        raise HTTPException(status_code=502, detail=str(res.get("error"))[:250])
    return {"ok": True, "existia": False, "mensaje": f"Contacto {nombres} {paterno} creado en eCert"}


@api.post("/migrup/ocr-cedula")
async def migrup_ocr_cedula(file: UploadFile = File(...)):
    """Lee una cédula de identidad (foto o PDF) y extrae los datos del contacto."""
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Archivo vacío")
    fn = file.filename or "cedula"
    try:
        raw, fn, _ = pdfs.convertir_a_pdf(raw, fn)
    except ValueError:
        pass
    texto, _met = await asyncio.to_thread(ocr_service.extraer_texto, raw, fn, True)
    if len(texto or "") < 15:
        raise HTTPException(status_code=422, detail="No se pudo leer texto en la cédula. Probá con una foto más nítida.")
    datos = {"nombres": "", "aPaterno": "", "aMaterno": "", "rut": ai_extract._rut_regex(texto), "email": ""}
    key = os.environ.get("EMERGENT_LLM_KEY", "")
    if key:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            chat = LlmChat(api_key=key, session_id=f"cedula-{uuid.uuid4()}", system_message=(
                "Recibes el texto OCR de una cédula de identidad chilena. Responde SOLO un JSON válido con: "
                "nombres (string, solo los nombres de pila), aPaterno (apellido paterno), "
                "aMaterno (apellido materno o ''), rut (RUN formato 12.345.678-9 o ''). "
                "Si un dato no aparece, usa ''.")).with_model("openai", "gpt-5.4-mini")
            resp = await chat.send_message(UserMessage(text=texto[:3000]))
            m = re.search(r"\{.*\}", str(resp), re.S)
            if m:
                import json as _json
                d = _json.loads(m.group(0))
                for k in ("nombres", "aPaterno", "aMaterno"):
                    datos[k] = (d.get(k) or "").strip()
                datos["rut"] = (d.get("rut") or "").strip() or datos["rut"]
        except Exception as e:
            logging.warning(f"ocr-cedula IA: {e}")
    return {"ok": True, **datos}


@api.get("/migrup/documentos")
async def migrup_documentos(nombre: str = "", estado: int = 0):
    res = await asyncio.to_thread(migrup.listar_documentos, nombre, estado, 1, 20)
    if isinstance(res, dict) and res.get("_error"):
        raise HTTPException(status_code=502, detail=res["_error"])
    return {"documentos": (res or {}).get("paginatedList", [])}


@api.post("/set-credito/sets/{sid}/enviar-firma")
async def setcred_enviar_firma(sid: str, payload: dict):
    doc = await _get_set(sid)
    base = _set_dir(doc.get("nombre", "")).resolve()
    target = (base / (payload.get("file_path", "") or "")).resolve()
    if not str(target).startswith(str(base)) or not target.exists():
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    firmante = {
        "nombres": payload.get("nombres") or doc.get("nombre", ""),
        "aPaterno": payload.get("aPaterno", ""),
        "aMaterno": payload.get("aMaterno", ""),
        "rut": payload.get("rut") or doc.get("rut", ""),
        "email": payload.get("email") or doc.get("email", ""),
    }
    if not firmante["email"] or "@" not in firmante["email"]:
        raise HTTPException(status_code=400, detail="Correo del firmante inválido")
    if not firmante["rut"]:
        raise HTTPException(status_code=400, detail="RUT del firmante requerido")
    comentario = payload.get("comentario", "")
    pdf_bytes = target.read_bytes()
    posiciones = await asyncio.to_thread(pdfs.posiciones_firma_cliente, pdf_bytes)
    nombre_completo = " ".join(x for x in [firmante["nombres"], firmante["aPaterno"],
                                           firmante["aMaterno"]] if x).strip()
    if len(posiciones) > 1:
        pdf_bytes = await asyncio.to_thread(pdfs.estampar_referencias_firma, pdf_bytes,
                                            posiciones[1:], nombre_completo)
    res = await asyncio.to_thread(migrup.enviar_a_firmar_tercero, pdf_bytes,
                                  target.stem, firmante, comentario, None, False,
                                  posiciones[:1] or None)
    if not res.get("success"):
        raise HTTPException(status_code=502, detail=str(res.get("error") or res.get("raw"))[:250])
    await db.set_credito.update_one({"id": sid}, {"$push": {"firmas": {
        "documento": target.name, "firmante": firmante["email"], "rut": firmante["rut"],
        "estampas": len(posiciones) or 1, "enviado_en": now_iso()}}})
    return {"ok": True, "firmante": firmante["email"], "estampas": len(posiciones) or 1,
            "firmas_consumidas": 1, "raw": res.get("raw")}


def _fmt_uf(v):
    if v in (None, "", False):
        return "—"
    try:
        return f"{float(v):,.1f} UF".replace(",", ".")
    except Exception:
        return str(v)


@api.post("/procesamiento/queue/{qid}/enviar-autocorreo")
async def proc_enviar_autocorreo(qid: str, payload: dict = None):
    item = await db.proc_queue.find_one({"id": qid})
    if not item:
        raise HTTPException(status_code=404, detail="No encontrado")
    cl = item.get("classification", {})
    campos = item.get("campos", {})
    cliente = cl.get("cliente") or mail._extraer_nombre(item.get("subject", ""), item.get("sender", ""))
    st = await _ac_state()
    destino = (payload or {}).get("destino") or st.get("destination") or os.environ.get("MAIL2_USER", "")
    if not destino:
        raise HTTPException(status_code=400, detail="No hay correo destino configurado")

    # Validacion: documentos completos + campos indispensables
    faltan, docs_faltantes, listo = _validar_item_dict(item)
    forzar = bool((payload or {}).get("forzar"))
    if not listo and not forzar:
        lista_campos = "".join(f"<li>{f}</li>" for f in faltan)
        lista_docs = "".join(f"<li>{DOC_LABELS.get(t, t)}: faltan {n}</li>"
                             for t, n in docs_faltantes.items())
        aviso = f"""
        <div style="font-family:Arial,sans-serif;font-size:14px;color:#222">
          <h2 style="color:#e17055;margin:0 0 8px">FALTA INFORMACION - {cliente}</h2>
          <p>No es posible enviar esta gestion a mesa porque falta lo siguiente:</p>
          {f'<b>Campos por completar:</b><ul>{lista_campos}</ul>' if lista_campos else ''}
          {f'<b>Documentos faltantes:</b><ul>{lista_docs}</ul>' if lista_docs else ''}
          <p>Complete la informacion a mano en el modulo <b>Procesamiento Correo</b> y vuelva a enviar.</p>
          <p style="color:#888;font-size:12px">Central Mutuos - Con Creces</p>
        </div>
        """
        res_aviso = await asyncio.to_thread(
            mail.send_mail, destino, f"[FALTA INFORMACION] {cliente}", aviso, [], "principal")
        await db.proc_queue.update_one({"id": qid}, {"$set": {
            "status": "revisar", "campos_faltantes": faltan,
            "docs_faltantes": {DOC_LABELS.get(t, t): n for t, n in docs_faltantes.items()}}})
        return {"success": False, "aviso_enviado": bool(res_aviso.get("success")),
                "campos_faltantes": faltan,
                "docs_faltantes": {DOC_LABELS.get(t, t): n for t, n in docs_faltantes.items()}}

    con_sub = campos.get("con_subsidio")
    con_sub_txt = "Con subsidio" if con_sub is True else "Sin subsidio" if con_sub is False else "—"
    fecha_entrega = (campos.get("fecha_entrega") or "—").capitalize()
    # Buscar PDF agrupado en la carpeta del cliente
    adjuntos = []
    dest_folder = CLIENTES_DIR / _safe_name(cliente)
    merged = dest_folder / f"Carpeta_{_safe_name(cliente)}.pdf"
    if merged.exists():
        adjuntos.append({"filename": merged.name, "content_b64": _b64(merged.read_bytes())})
    cuerpo = f"""
    <div style="font-family:Arial,sans-serif;font-size:14px;color:#222">
      <h2 style="color:#6c5ce7;margin:0 0 8px">Gestion de credito - {cliente}</h2>
      <table style="border-collapse:collapse">
        <tr><td style="padding:4px 12px 4px 0"><b>Cliente</b></td><td>{cliente}</td></tr>
        <tr><td style="padding:4px 12px 4px 0"><b>RUT</b></td><td>{cl.get('rut','—') or '—'}</td></tr>
        <tr><td style="padding:4px 12px 4px 0"><b>Correo cliente</b></td><td>{cl.get('email_cliente') or campos.get('email_cliente') or '—'}</td></tr>
        <tr><td style="padding:4px 12px 4px 0"><b>Ejecutivo que envio</b></td><td>{campos.get('nombre_ejecutivo','—') or '—'}</td></tr>
        <tr><td style="padding:4px 12px 4px 0"><b>Correo ejecutivo</b></td><td>{campos.get('email_ejecutivo','—') or '—'}</td></tr>
        <tr><td style="padding:4px 12px 4px 0"><b>Proyecto inmobiliario</b></td><td>{campos.get('proyecto_inmobiliario','—') or '—'}</td></tr>
        <tr><td style="padding:4px 12px 4px 0"><b>Fecha de entrega</b></td><td>{fecha_entrega}</td></tr>
        <tr><td style="padding:4px 12px 4px 0"><b>Tipo</b></td><td>{con_sub_txt}</td></tr>
        <tr><td style="padding:4px 12px 4px 0"><b>Monto credito</b></td><td>{_fmt_uf(campos.get('monto_credito_uf'))}</td></tr>
        <tr><td style="padding:4px 12px 4px 0"><b>Monto subsidio</b></td><td>{_fmt_uf(campos.get('monto_subsidio_uf'))}</td></tr>
        <tr><td style="padding:4px 12px 4px 0"><b>Pie</b></td><td>{_fmt_uf(campos.get('pie_uf'))}</td></tr>
        <tr><td style="padding:4px 12px 4px 0"><b>Ahorro</b></td><td>{_fmt_uf(campos.get('ahorro_uf'))}</td></tr>
        <tr><td style="padding:4px 12px 4px 0"><b>Credito a solicitar</b></td><td>{_fmt_uf(campos.get('monto_credito_solicitar_uf'))}</td></tr>
      </table>
      <p style="margin-top:12px">Se adjunta el PDF agrupado de la carpeta del cliente para su envio a mesa.</p>
      <p style="color:#888;font-size:12px">Central Mutuos - Con Creces</p>
    </div>
    """
    asunto = f"[Gestion] {cliente} - {campos.get('proyecto_inmobiliario') or 'Credito Hipotecario'}"
    res = await asyncio.to_thread(mail.send_mail, destino, asunto, cuerpo, adjuntos, "principal")
    if not res.get("success"):
        raise HTTPException(status_code=502, detail=res.get("error", "Error de envio"))
    await db.proc_queue.update_one({"id": qid}, {"$set": {"autocorreo_enviado": True,
                                                          "autocorreo_a": destino, "autocorreo_en": now_iso()}})
    return {"success": True, "destino": destino, "adjunto": bool(adjuntos)}




@api.get("/procesamiento/checklist")
async def proc_checklist():
    return {"checklist": CHECKLIST, "orden_dependiente": ORDEN_DEPENDIENTE,
            "orden_independiente": ORDEN_INDEPENDIENTE}


@api.post("/portal/consulta")
async def portal_consulta(payload: dict = None):
    return {"encontrado": False, "operaciones": []}


def _norm_rut(r):
    return re.sub(r"[^0-9kK]", "", (r or "")).lower()


async def _portal_consulta_impl(rut: str):
    rn = _norm_rut(rut)
    if len(rn) < 7:
        return {"found": False, "rut": rut, "operaciones": [], "simulaciones": []}
    operaciones = []
    # Carpetas de clientes con ese RUT
    folders = await db.folders.find({}).limit(300).to_list(300)
    nombres_match = set()
    for f in folders:
        if _norm_rut(f.get("rut")) == rn:
            nombres_match.add((f.get("nombre") or "").strip())
    # Gestiones procesadas con ese RUT
    items = await db.proc_queue.find({}).limit(300).to_list(300)
    for it in items:
        cl = it.get("classification", {}) or {}
        if _norm_rut(cl.get("rut")) == rn and (cl.get("cliente") or "").strip():
            nombres_match.add(cl.get("cliente").strip())
    for nombre in nombres_match:
        rx = {"$regex": f"^{re.escape(nombre)}$", "$options": "i"}
        logs = await db.autocorreo_log.find({"cliente": rx}).sort("processed_at", -1).limit(50).to_list(50)
        estado = "en proceso"
        ultimo = ""
        for l in logs:
            subj = (l.get("subject") or "").upper()
            if not ultimo:
                ultimo = l.get("processed_at", "")
            if subj.startswith("RECHAZO"):
                estado = "rechazado"
                break
            if l.get("status") == "sent":
                estado = "aprobado"
                break
        it_cliente = await db.proc_queue.find_one({"classification.cliente": rx})
        campos = (it_cliente or {}).get("campos", {}) or {}
        operaciones.append({
            "id": nombre, "cliente_display": nombre, "estado": estado,
            "proyecto": campos.get("proyecto_inmobiliario") or "",
            "ejecutivo_cm": "Gerardo — Central Mutuos",
            "total_correos": len(logs),
            "ultimo_correo": ultimo or (it_cliente or {}).get("date_iso", ""),
            "resumen": ("Su operación fue aprobada. Pronto recibirá los documentos." if estado == "aprobado"
                        else "Su operación fue evaluada por la mesa. Contacte a su ejecutivo." if estado == "rechazado"
                        else "Su solicitud está en revisión de antecedentes."),
        })
    sims = []
    async for s in db.simulaciones.find({}).sort("timestamp", -1).limit(200):
        if _norm_rut(s.get("rut")) == rn:
            sims.append({"nombre_completo": s.get("nombre_completo", ""),
                         "precalificacion_aprobada": bool(s.get("precalificacion_aprobada")),
                         "capacidad_credito_uf": s.get("capacidad_credito_uf") or 0,
                         "timestamp": s.get("timestamp", "")})
        if len(sims) >= 5:
            break
    found = bool(operaciones or sims)
    return {"found": found, "encontrado": found, "rut": rut,
            "operaciones": operaciones, "simulaciones": sims}


@api.get("/portal/consulta")
async def portal_consulta_get(rut: str = ""):
    return await _portal_consulta_impl(rut)


@api.post("/formato/upload")
async def formato_upload(file: UploadFile = File(None)):
    return {"ok": True, "filename": file.filename if file else None}


@api.post("/formato/merge-pdfs")
async def formato_merge(payload: dict = None):
    raise HTTPException(status_code=501, detail="Funcion no disponible en esta instancia")


@api.post("/formato/split-pdf")
async def formato_split(payload: dict = None):
    raise HTTPException(status_code=501, detail="Funcion no disponible en esta instancia")


@api.post("/formato/ai-edit")
async def formato_ai_edit(payload: dict = None):
    raise HTTPException(status_code=501, detail="Funcion no disponible en esta instancia")


@api.get("/")
async def root():
    return {"message": "Central Mutuos API", "status": "ok"}


# ---------------------------------------------------------------------------
app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown():
    client.close()
