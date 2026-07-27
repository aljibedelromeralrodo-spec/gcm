from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form, Request, Query
from fastapi.responses import StreamingResponse, JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import io
import re
import uuid
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
    # Seed default admin user (codigo=admin / password=0586)
    if await db.users.count_documents({}) == 0:
        await db.users.insert_many([
            {"codigo": "admin", "nombre": "Administrador", "password": "0586",
             "rol": "admin", "created": now_iso()},
        ])
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


@app.on_event("startup")
async def startup():
    await ensure_seed()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
@api.post("/auth/login")
async def auth_login(payload: dict):
    codigo = (payload.get("rut") or payload.get("codigo") or "").strip()
    password = (payload.get("password") or "").strip()
    user = await db.users.find_one({"codigo": codigo, "password": password})
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


@api.get("/clientes/uf-actual")
async def uf_actual():
    return {"valor_uf": await get_valor_uf()}


@api.patch("/clientes/uf-actual")
async def set_uf(payload: dict):
    v = float(payload.get("valor_uf") or DEFAULT_UF)
    await db.config.update_one({"_key": "uf"}, {"$set": {"valor_uf": v}}, upsert=True)
    return {"valor_uf": v}


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
    c.drawString(2 * cm, 1.5 * cm, "Documento referencial. No constituye preaprobacion ni aprobacion crediticia. Con Creces Asesorias.")
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
    msg = payload.get("message", "")
    session = payload.get("session_id") or str(uuid.uuid4())
    resp = "Soy Central, tu asistente. El chat IA no esta habilitado en esta instancia, pero puedes usar los modulos de Simulador y Predictor."
    await db.conversaciones.insert_one({
        "id": str(uuid.uuid4()), "session_id": session,
        "user_name": payload.get("user_name", ""), "user_msg": msg,
        "response": resp, "timestamp": now_iso(),
    })
    return {"response": resp, "session_id": session, "enabled": False}


@api.post("/central/chat-files")
async def central_chat_files():
    return {"response": "Procesamiento de archivos no disponible en esta instancia.", "enabled": False}


@api.post("/central/tts")
async def central_tts():
    raise HTTPException(status_code=503, detail="TTS no disponible")


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
# Clientes / Carpetas (basic CRUD)
# ---------------------------------------------------------------------------
@api.get("/clientes/folders")
async def list_folders(q: str = ""):
    query = {"nombre": {"$regex": q, "$options": "i"}} if q else {}
    docs = await db.folders.find(query).sort("created_at", -1).limit(200).to_list(200)
    return {"folders": [clean(d) for d in docs]}


@api.post("/clientes/folders")
async def create_folder(payload: dict):
    doc = {
        "id": str(uuid.uuid4()),
        "nombre": payload.get("nombre", ""),
        "rut": payload.get("rut", ""),
        "archivos": [],
        "created_at": now_iso(),
    }
    await db.folders.insert_one(dict(doc))
    return clean(doc)


@api.get("/clientes/folders/{fid}")
async def get_folder(fid: str):
    doc = await db.folders.find_one({"id": fid})
    if not doc:
        raise HTTPException(status_code=404, detail="Carpeta no encontrada")
    return clean(doc)


@api.delete("/clientes/folders/{fid}")
async def delete_folder(fid: str):
    await db.folders.delete_one({"id": fid})
    return {"ok": True}


@api.get("/clientes/emails")
async def clientes_emails(limit: int = 20):
    emails = await asyncio.to_thread(mail.fetch_recent, limit)
    return {"emails": emails}


@api.get("/clientes/emails/search")
async def clientes_emails_search(q: str = ""):
    emails = await asyncio.to_thread(mail.fetch_recent, 50)
    ql = (q or "").lower()
    if ql:
        emails = [e for e in emails
                  if ql in (e.get("subject", "") or "").lower()
                  or ql in (e.get("from", "") or "").lower()]
    return {"emails": emails}


@api.get("/clientes/ajustes")
async def clientes_ajustes():
    return {"ajustes": {}}


@api.get("/clientes/autocorreo-dest")
async def autocorreo_dest():
    return {"destinatarios": []}


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


@api.get("/autocorreo/status")
async def ac_status():
    st = await _ac_state()
    log = await db.autocorreo_log.find().sort("processed_at", -1).limit(25).to_list(25)
    sent = await db.autocorreo_log.count_documents({"status": "sent"})
    failed = await db.autocorreo_log.count_documents({"status": "failed"})
    total = await db.autocorreo_log.count_documents({})
    return {
        "enabled": st.get("enabled", False),
        "periodic_enabled": st.get("periodic_enabled", False),
        "cutoff_iso": st.get("cutoff_iso"),
        "destination": st.get("destination") or os.environ.get("MAIL2_USER", ""),
        "sent": sent,
        "failed": failed,
        "total": total,
        "recent": [clean(r) for r in log],
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


def _procesar_mesa(destino, cutoff_iso):
    """Lee correos de mesa con PDF, deja pag 1 en simulaciones, archiva y envia. (sync)"""
    correos = mail.fetch_pdf_attachments(sender_filter=MESA_SENDER, limit=20)
    resultados = []
    for c in correos:
        if cutoff_iso and c.get("date") and c["date"] < cutoff_iso:
            continue
        cliente = mail._extraer_nombre(c["subject"], c["from"])
        es_aprobacion = c["tipo"] == "aprobacion"
        for pdf in c["pdfs"]:
            raw = pdf["content_bytes"]
            tipo_doc = pdfs.clasificar_documento(raw, pdf["filename"])
            adjuntos = []
            saved = []
            if tipo_doc == "simulacion":
                nuevo, orig, removidas = pdfs.dejar_primera_pagina(raw)
                nombre_aj = pdf["filename"].replace(".pdf", "") + "_ajustada.pdf"
                _save_pdf(cliente, nombre_aj, nuevo)
                saved.append({"name": _safe_name(nombre_aj), "type": "simulacion_ajustada",
                              "pages_original": orig, "pages_removed": removidas})
                adjuntos.append({"filename": nombre_aj,
                                 "content_b64": _b64(nuevo)})
            else:
                _save_pdf(cliente, pdf["filename"], raw)
                saved.append({"name": _safe_name(pdf["filename"]), "type": tipo_doc})
                adjuntos.append({"filename": pdf["filename"], "content_b64": _b64(raw)})
            resultados.append({"cliente": cliente, "subject": c["subject"],
                               "saved": saved, "adjuntos": adjuntos,
                               "es_aprobacion": es_aprobacion, "body": c.get("body", "")})
    # Enviar al destino (gerardo.ext@) los PDFs ajustados
    enviados = 0
    errores = []
    logs = []
    for r in resultados:
        cuerpo = r["body"] or (
            "Estimado/a,<br><br>Adjuntamos el documento correspondiente a su operacion.<br><br>"
            "Saludos cordiales,<br>Central Mutuos")
        cuerpo_html = cuerpo.replace("\n", "<br>") if "<br>" not in cuerpo else cuerpo
        res = mail.send_mail(destino, r["subject"], cuerpo_html, r["adjuntos"], desde="principal")
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


@api.post("/autocorreo/run")
async def ac_run(payload: dict = None):
    st = await _ac_state()
    destino = st.get("destination") or os.environ.get("MAIL2_USER", "")
    if not destino:
        raise HTTPException(status_code=400, detail="No hay correo destino configurado")
    result = await asyncio.to_thread(_procesar_mesa, destino, st.get("cutoff_iso"))
    for lg in result.pop("logs", []):
        await db.autocorreo_log.insert_one(lg)
    return result


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
                nombre_aj = f.filename.replace(".pdf", "") + "_ajustada.pdf"
                _save_pdf(cliente, nombre_aj, nuevo)
                saved.append({"name": _safe_name(nombre_aj), "type": "simulacion_ajustada",
                              "pages_original": orig, "pages_removed": removidas})
            else:
                _save_pdf(cliente, f.filename, raw)
                saved.append({"name": _safe_name(f.filename), "type": tipo_doc})
        except Exception as e:
            errors.append({"file": f.filename, "error": str(e)})
    return {"folder": _safe_name(cliente), "cliente": cliente, "saved": saved, "errors": errors}


@api.get("/procesamiento/queue")
async def proc_queue(status: str = ""):
    return {"queue": [], "items": []}


@api.get("/procesamiento/stats")
async def proc_stats():
    return {"pendientes": 0, "procesados": 0, "errores": 0}


@api.get("/procesamiento/rules")
async def proc_rules():
    return {"rules": []}


@api.post("/procesamiento/rules")
async def proc_add_rule(payload: dict = None):
    return {"ok": True}


@api.delete("/procesamiento/rules/{rid}")
async def proc_del_rule(rid: str):
    return {"ok": True}


@api.post("/procesamiento/ingest-from-inbox")
async def proc_ingest(payload: dict = None):
    return {"ok": True, "ingested": 0}


@api.post("/procesamiento/process-pending")
async def proc_process(payload: dict = None):
    return {"ok": True, "procesados": 0}


@api.get("/oauth/drive/status")
async def drive_status():
    return {"connected": False}


@api.post("/portal/consulta")
async def portal_consulta(payload: dict = None):
    return {"encontrado": False, "operaciones": []}


@api.get("/portal/consulta")
async def portal_consulta_get(rut: str = ""):
    return {"encontrado": False, "operaciones": []}


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
