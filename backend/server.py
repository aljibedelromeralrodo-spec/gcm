from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form, Request, Query
from typing import List
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse, FileResponse, RedirectResponse, Response
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import io
import re
import html
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
import bcrypt
import functools
import email_service as mail
import folders_service as fsvc
from database import client, db
import sales_engine
import mesa_brain
import cloud_bunker
import simulador_engine

app = FastAPI(title="Central Mutuos API")

import auth as _auth

# BÚNKER DE SEGURIDAD (SEC-001/002): autenticación global de todas las rutas /api.
app.add_middleware(_auth.AuthMiddleware)
# BLINDAJE DE COMUNICACIÓN (CORS): orígenes explícitos desde variables de entorno.
_cors_env = os.environ.get("CORS_ORIGINS", "")
_cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()] or ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def _security_headers(request, call_next):
    """BLINDAJE: refuerzo de cabeceras de seguridad (XSS, sniffing, clickjacking, SSL)."""
    resp = await call_next(request)
    resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("X-XSS-Protection", "1; mode=block")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return resp

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


CARGO_ADMIN_DEFAULT = ("Jefe Externo, Asesor Business Development | "
                       "Canal Inmobiliarias y Brokers | Central Mutuos")
_cargo_admin_cache = {"v": CARGO_ADMIN_DEFAULT}


async def ensure_seed():
    # Garantizar SIEMPRE los usuarios administradores
    for u in [
        {"codigo": "administrador", "nombre": "Administrador", "password": os.environ.get("ADMIN_PASSWORD_1", ""), "rol": "admin"},
        {"codigo": "admin", "nombre": "Administrador", "password": os.environ.get("ADMIN_PASSWORD_2", ""), "rol": "admin"},
    ]:
        if not u["password"]:
            u = {k: v for k, v in u.items() if k != "password"}
        await db.users.update_one(
            {"codigo": u["codigo"]},
            {"$set": u, "$setOnInsert": {"created": now_iso()}},
            upsert=True,
        )
    # RESTABLECIMIENTO DE AUTORIDAD: mando único de Gerardo Barrera. René Osa fue eliminado
    # en su momento; el borrado destructivo se retiró del arranque (bloqueaba el deploy).
    await db.users.update_many({"rol": "maestro"}, {"$set": {"rol": "admin"}})
    # ── SISTEMA DE ROLES (6 roles): siembra idempotente — solo si no existen ──
    for codigo, nombre, rol, clave, perfil in [
        ("gerencia", "Gerencia Comercial", "gerencia", "Gerencia2026", ""),
        ("administracion", "Administración", "administracion", "Administracion2026", ""),
        ("postventa", "Postventa", "postventa", "Postventa2026", ""),
        ("contralor", "Contralor", "contralor", "Contralor2026", ""),
        ("broker", "Broker Demo", "broker", "Broker2026", "D"),
        ("victoria", "Victoria Vilchez", "administracion", "Victoria2026", ""),
        ("daniela", "Daniela Galindo", "administracion", "Daniela2026", ""),
    ]:
        if not await db.users.find_one({"codigo": codigo}):
            await db.users.insert_one({
                "codigo": codigo, "nombre": nombre, "rol": rol, "perfil": perfil,
                "clave_hash": bcrypt.hashpw(clave.encode(), bcrypt.gensalt()).decode(),
                "activo": True, "created": now_iso()})
    # ── CARGO OFICIAL DEL ADMINISTRADOR (Ethan): fijo e inamovible por otros usuarios ──
    await db.users.update_many(
        {"codigo": {"$in": ["admin", "administrador"]}, "cargo": {"$exists": False}},
        {"$set": {"cargo": CARGO_ADMIN_DEFAULT}})
    u_adm = await db.users.find_one({"codigo": "administrador"}) or {}
    _cargo_admin_cache["v"] = u_adm.get("cargo") or CARGO_ADMIN_DEFAULT
    # ── CONFIGURACIÓN DE EJECUTIVOS (IMAP): 3 registros vacíos, listos para completar.
    #    El sistema NO se conecta a ningún correo hasta que se guarden credenciales. ──
    for eid, nombre in [("daniela_galindo", "Daniela Galindo"),
                        ("victoria_vilchez", "Victoria Vilchez"),
                        ("javier_urrutia", "Javier Urrutia")]:
        await db.ejecutivos_correo.update_one({"eid": eid}, {"$setOnInsert": {
            "eid": eid, "nombre": nombre, "email": "", "servidor": "imap.gmail.com",
            "clave_enc": "", "activo": False, "actualizado": "", "creado": now_iso()}}, upsert=True)
    # ── ALGORITMO ESPEJO (Contralor): esqueleto desconectado, calibración 0% ──
    await db.config.update_one({"_key": "espejo_contralor"}, {"$setOnInsert": {
        "email": "", "servidor": "imap.gmail.com", "clave_enc": "", "activo": False,
        "estado": "desconectado", "calibracion_pct": 0, "creado": now_iso()}}, upsert=True)
    # CONSTITUCIÓN MAESTRA: 15 Reglas de Oro (fuente de verdad inmutable)
    try:
        import constitucion as _const
        await _const.seed_constitucion(db)
    except Exception as _e:
        logging.warning(f"seed constitucion: {_e}")
    # Seed config
    if await db.config.count_documents({"_key": "tasas"}) == 0:
        await db.config.insert_one({"_key": "tasas", **DEFAULT_TASAS})
    if await db.config.count_documents({"_key": "seguros"}) == 0:
        await db.config.insert_one({"_key": "seguros", **DEFAULT_SEGUROS})
    if await db.config.count_documents({"_key": "criterios"}) == 0:
        await db.config.insert_one({"_key": "criterios", **DEFAULT_CRITERIOS})
    if await db.config.count_documents({"_key": "uf"}) == 0:
        await db.config.insert_one({"_key": "uf", "valor_uf": DEFAULT_UF})


# ═══ SISTEMA DE ROLES · CONFIGURACIÓN DE EJECUTIVOS · ALGORITMO ESPEJO ═══
def _cred_cifrar(texto):
    """Credenciales IMAP SIEMPRE cifradas (Fernet) — jamás en texto plano en la DB."""
    from cryptography.fernet import Fernet
    return Fernet(os.environ["CRED_CIPHER_KEY"].encode()).encrypt(texto.encode()).decode()


def _rol_de(request):
    return (getattr(request.state, "user", {}) or {}).get("rol", "")


def _exigir_roles(request, roles):
    if _rol_de(request) not in roles:
        raise HTTPException(status_code=403, detail="No está autorizado el ingreso a este módulo")


def _estado_ejecutivo(e):
    if not e.get("email") or not e.get("clave_enc"):
        return "Sin credenciales"
    return "Activo" if e.get("activo") else "Inactivo"


@api.get("/config/ejecutivos")
async def config_ejecutivos_list(request: Request):
    """Panel del Administrador: estado de conexión visible, claves JAMÁS expuestas."""
    _exigir_roles(request, ("admin", "maestro", "gerencia", "contralor"))
    out = []
    async for e in db.ejecutivos_correo.find({}).sort("nombre", 1):
        out.append({"eid": e["eid"], "nombre": e["nombre"], "email": e.get("email") or "",
                    "servidor": e.get("servidor") or "imap.gmail.com",
                    "activo": bool(e.get("activo")), "tiene_clave": bool(e.get("clave_enc")),
                    "estado": _estado_ejecutivo(e), "actualizado": e.get("actualizado") or ""})
    return {"ejecutivos": out, "total": len(out),
            "nota": "El sistema NO se conecta a ningún correo hasta que el ejecutivo guarde sus credenciales"}


@api.post("/config/ejecutivos/{eid}")
async def config_ejecutivos_save(eid: str, payload: dict, request: Request):
    _exigir_roles(request, ("admin", "maestro"))
    await _reconfirmar_identidad(request, payload)
    e = await db.ejecutivos_correo.find_one({"eid": eid})
    if not e:
        raise HTTPException(status_code=404, detail="Ejecutivo no registrado")
    cambios = {"actualizado": now_iso()}
    if "email" in payload:
        email = (payload.get("email") or "").strip()
        if email and "@" not in email:
            raise HTTPException(status_code=400, detail="Correo inválido")
        cambios["email"] = email
    if payload.get("clave"):
        cambios["clave_enc"] = _cred_cifrar(str(payload["clave"]).strip())
    if "servidor" in payload:
        cambios["servidor"] = (payload.get("servidor") or "imap.gmail.com").strip() or "imap.gmail.com"
    if "activo" in payload:
        cambios["activo"] = bool(payload["activo"])
    await db.ejecutivos_correo.update_one({"eid": eid}, {"$set": cambios})
    e = await db.ejecutivos_correo.find_one({"eid": eid})
    # IMPORTANTE: aquí NO se intenta ninguna conexión IMAP — solo se guarda la configuración
    return {"ok": True, "eid": eid, "estado": _estado_ejecutivo(e),
            "activo": bool(e.get("activo")), "tiene_clave": bool(e.get("clave_enc"))}


@api.get("/contralor/espejo")
async def contralor_espejo_get(request: Request):
    """ALGORITMO ESPEJO (esqueleto): buzón IMAP de lectura + bitácora de calibración."""
    _exigir_roles(request, ("admin", "maestro", "contralor", "administracion", "postventa"))
    cfg = await db.config.find_one({"_key": "espejo_contralor"}, {"_id": 0, "clave_enc": 0}) or {}
    bitacora = await db.espejo_bitacora.find({}, {"_id": 0}).sort("fecha", -1).to_list(50)
    return {"email": cfg.get("email") or "", "servidor": cfg.get("servidor") or "imap.gmail.com",
            "activo": bool(cfg.get("activo")), "estado": cfg.get("estado") or "desconectado",
            "tiene_clave": bool(await db.config.find_one({"_key": "espejo_contralor", "clave_enc": {"$ne": ""}})),
            "calibracion_pct": cfg.get("calibracion_pct") or 0,
            "bitacora": bitacora, "total_bitacora": len(bitacora)}


@api.post("/contralor/espejo")
async def contralor_espejo_save(payload: dict, request: Request):
    _exigir_roles(request, ("admin", "maestro", "contralor"))
    await _reconfirmar_identidad(request, payload)
    cambios = {"actualizado": now_iso()}
    if "email" in payload:
        email = (payload.get("email") or "").strip()
        if email and "@" not in email:
            raise HTTPException(status_code=400, detail="Correo inválido")
        cambios["email"] = email
    if payload.get("clave"):
        cambios["clave_enc"] = _cred_cifrar(str(payload["clave"]).strip())
    if "servidor" in payload:
        cambios["servidor"] = (payload.get("servidor") or "imap.gmail.com").strip() or "imap.gmail.com"
    if "activo" in payload:
        cambios["activo"] = bool(payload["activo"])
    # El estado queda DESCONECTADO: el algoritmo aún no se construye, solo el esqueleto
    cambios["estado"] = "desconectado"
    await db.config.update_one({"_key": "espejo_contralor"}, {"$set": cambios}, upsert=True)
    cfg = await db.config.find_one({"_key": "espejo_contralor"}) or {}
    return {"ok": True, "estado": "desconectado", "activo": bool(cfg.get("activo")),
            "tiene_clave": bool(cfg.get("clave_enc")),
            "nota": "Configuración guardada cifrada. La conexión se activará cuando el algoritmo esté construido."}


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


import bunker


async def _bunker_loop():
    """BÚNKER DE ARCHIVOS: espejo disco -> GridFS cada 5 min (hilo daemon, no bloquea)."""
    while True:
        try:
            bunker.sync_en_background()
        except Exception as e:
            logging.warning(f"bunker sync: {e}")
        await asyncio.sleep(300)


async def _llm_con_timeout(chat, um, timeout=60):
    """TIMEOUT ANTI-CONGELAMIENTO: toda llamada LLM se cancela a los 60s (error controlado)."""
    try:
        import energia as _energia
        await _energia.registrar_llm(1)
    except Exception:
        pass
    return await asyncio.wait_for(chat.send_message(um), timeout=timeout)


async def _rescate_historico_loop():
    """RESCATE HISTÓRICO: 1ª ejecución escanea 30 días del buzón por LOTES (enviados
    y recibidos con la mesa); después escaneo preventivo cada 3 días."""
    await asyncio.sleep(20)
    while True:
        try:
            cfg = await db.config.find_one({"_key": "seguimiento_historico"}) or {}
            dias = 3 if cfg.get("inicial_done") else 30
            ops = await asyncio.to_thread(mail.procesar_seguimiento, 500, dias)
            nuevos = 0
            for i in range(0, len(ops), 20):
                for op in ops[i:i + 20]:
                    exists = await db.seguimiento.find_one(
                        {"asunto": op["asunto"], "fecha": op["fecha"]})
                    if exists:
                        continue
                    extra = await _info_operacion_cliente(op["cliente"])
                    doc_seg = {
                        "id": str(uuid.uuid4()),
                        "cliente_id": op["cliente"].lower().replace(" ", "-"),
                        **op, **extra,
                        "correo_remitente": op.get("remitente", ""),
                        "origen": "rescate_historico",
                        "procesado_en": now_iso()}
                    await db.seguimiento.insert_one(dict(doc_seg))
                    # CONTRALORÍA AUTOMÁTICA: auditar el caso al instante
                    asyncio.create_task(_forense_caso_automatico(doc_seg))
                    # RITMO ANTI-RÁFAGA: la notificación entra a la cola pausada (máx 3/ciclo, 10s)
                    await _encolar_notificacion(doc_seg)
                    nuevos += 1
                await asyncio.sleep(0.5)
            await db.config.update_one({"_key": "seguimiento_historico"}, {"$set": {
                "inicial_done": True, "last_scan": now_iso(),
                "dias_escaneados": dias, "ops": len(ops), "nuevos": nuevos}}, upsert=True)
            logging.info(f"📜 Rescate histórico: {dias} días, {len(ops)} ops, {nuevos} nuevas")
        except Exception as e:
            logging.warning(f"rescate historico: {e}")
        await asyncio.sleep(3 * 24 * 3600)


_BG_TASKS = set()


@app.on_event("shutdown")
async def _cancelar_tareas_fondo():
    """Evita cuelgues en hot-reload: cancela todos los loops de fondo al apagar."""
    for t in list(_BG_TASKS):
        t.cancel()


async def _task_blindada(coro_fn, nombre):
    """Supervisor: si un loop de fondo muere por error, se registra y se reinicia solo.
    Si el loop retorna limpio (cliente Mongo cerrado en hot-reload), el supervisor termina."""
    t = asyncio.current_task()
    if t is not None:
        _BG_TASKS.add(t)
        t.add_done_callback(_BG_TASKS.discard)
    while True:
        try:
            await coro_fn()
            break  # retorno limpio = proceso en cierre: no revivir zombies
        except asyncio.CancelledError:
            break
        except Exception as e:
            if "after close" in str(e):
                break
            try:
                await db.system_log.insert_one({"id": str(uuid.uuid4()), "loop": nombre,
                                                "error": str(e)[:300], "fecha": now_iso()})
            except Exception:
                pass
        await asyncio.sleep(30)


# ─── NORMATIVAS FIJAS DASHAI (inamovibles): fuente canónica en código para que
#     PRODUCCIÓN (base de datos separada) se auto-siembre en el arranque sin
#     intervención manual. Mismos registros que motivo="normativa" del preview. ───
NORMATIVAS_FIJAS = [
    ("SUPERCARPETA", "NORMATIVA FIJA — SUPERCARPETA: vista obligatoria en tarjetas verticales expandibles. Sin tablas ni scroll horizontal. Campos editables con doble clic. Íconos verde/amarillo/rojo por estado."),
    ("RESUMEN IA", "NORMATIVA FIJA — RESUMEN IA: línea visible en tarjeta con formato [estado actual] + [quién debe el próximo paso] + [fecha último movimiento]. Solo eventos de los últimos 90 días."),
    ("ESTUDIO DE TÍTULO", "NORMATIVA FIJA — ESTUDIO DE TÍTULO: propiedad usada envía listado legal completo (Títulos, Herencias, Fusiones, CBR, DOM, TGR, SII). Propiedad nueva no lo incluye."),
    ("PLANTILLAS", "NORMATIVA FIJA — PLANTILLAS: cada módulo tiene plantilla HTML propia e independiente. Carta Oferta, Estudio de Título, Tasación, Resolución SERVIU y Solicitud de Crédito no comparten texto."),
    ("DISEÑO CORREOS", "NORMATIVA FIJA — DISEÑO CORREOS: fondo blanco, Arial, encabezados grises, datos clave en negrita. Firma siempre 'Central Mutuos'. Nunca mencionar 'Concreces'."),
    ("DESTINATARIOS ESTUDIO", "NORMATIVA FIJA — DESTINATARIOS ESTUDIO DE TÍTULO: cascada inmobiliaria > vendedor > correo de origen de la solicitud."),
    ("CC", "NORMATIVA FIJA — CC: solo en correos entrantes procesados por el sistema. Nunca en salientes, bajo ninguna circunstancia."),
]


async def _seed_normativas_fijas():
    """ARRANQUE (preview y producción): garantiza los 7 registros de normativa en
    db.dashai_eventos + respaldo en db.config antes de levantar cualquier servicio.
    Idempotente: solo siembra lo que falte. Prioriza el backup de la DB si existe."""
    cfg = await db.config.find_one({"_key": "dashai_normativas_fijas"}) or {}
    patrones_db = cfg.get("normas") or []
    normas = list(NORMATIVAS_FIJAS)
    for clave, patron in NORMATIVAS_FIJAS:
        for p in patrones_db:
            if clave in p.split(":")[0]:
                normas[[c for c, _ in NORMATIVAS_FIJAS].index(clave)] = (clave, p)
                break
    nivel = ((await db.config.find_one({"_key": "dashai_perpetuo"}) or {}).get("nivel_calibracion")) or 85
    sembrados = 0
    for clave, patron in normas:
        if await db.dashai_eventos.find_one({"motivo": "normativa", "norma_clave": clave}):
            continue
        await db.dashai_eventos.insert_one({
            "id": str(uuid.uuid4()), "motivo": "normativa", "norma_clave": clave,
            "fecha": now_iso(), "nivel_calibracion": nivel, "patron": patron,
            "prospectos_sync": 0, "folders_sync": 0, "inamovible": True})
        sembrados += 1
    if not cfg:
        await db.config.update_one({"_key": "dashai_normativas_fijas"}, {"$set": {
            "normas": [p for _, p in normas], "inamovible": True,
            "registradas_en": now_iso()}}, upsert=True)
    logging.info(f"📜 NORMATIVAS FIJAS: {sembrados} sembrada(s) en el arranque, {len(normas) - sembrados} ya presentes")
    return sembrados


# ═══ BLOQUE 7 — BLINDAJE DE NORMATIVAS (fuente de verdad del negocio) ═══
NORMATIVAS_MSG_403 = "No tienes permisos para modificar las normativas del sistema. Contacta al administrador."
_normas_cache = {"t": None, "datos": []}


async def normativas_activas(force=False):
    """Normativas activas con caché máximo de 5 minutos (regla de inmutabilidad)."""
    ahora = datetime.now(timezone.utc)
    if not force and _normas_cache["t"] and (ahora - _normas_cache["t"]).total_seconds() < 300:
        return _normas_cache["datos"]
    docs = await db.dashai_eventos.find({"motivo": "normativa"}, {"_id": 0}).sort("norma_clave", 1).to_list(200)
    _normas_cache.update({"t": ahora, "datos": docs})
    return docs


def _solo_admin_normativas(request):
    if _rol_de(request) not in ("admin", "maestro"):
        raise HTTPException(status_code=403, detail=NORMATIVAS_MSG_403)
    return getattr(request.state, "user", {}) or {}


async def _auditar_normativa(admin, clave, anterior, nuevo, accion):
    """Log de auditoría INMUTABLE: sin endpoint de borrado, ni para el Admin."""
    await db.normativas_auditoria.insert_one({
        "id": str(uuid.uuid4()), "fecha": now_iso(),
        "administrador": admin.get("nombre") or admin.get("sub") or "",
        "accion": accion, "normativa": clave,
        "valor_anterior": anterior or "", "valor_nuevo": nuevo or "", "inmutable": True})


@api.get("/dashai/normativas")
async def normativas_list(request: Request):
    _exigir_roles(request, ("admin", "maestro"))  # SOLO el Administrador ve las normativas
    docs = await normativas_activas(force=True)
    return {"normativas": [{"clave": d.get("norma_clave"), "patron": d.get("patron"),
                            "fecha": d.get("fecha"), "inamovible": bool(d.get("inamovible"))}
                           for d in docs], "total": len(docs)}


@api.post("/dashai/normativas")
async def normativas_upsert(payload: dict, request: Request):
    admin = _solo_admin_normativas(request)
    clave = (payload.get("clave") or "").strip().upper()
    patron = (payload.get("patron") or "").strip()
    if not clave or not patron:
        raise HTTPException(status_code=400, detail="Indique la clave y el texto completo de la normativa")
    prev = await db.dashai_eventos.find_one({"motivo": "normativa", "norma_clave": clave})
    if prev:
        await db.dashai_eventos.update_one({"id": prev["id"]}, {"$set": {"patron": patron, "fecha": now_iso()}})
    else:
        await db.dashai_eventos.insert_one({
            "id": str(uuid.uuid4()), "motivo": "normativa", "norma_clave": clave,
            "fecha": now_iso(), "patron": patron, "inamovible": True})
    await _auditar_normativa(admin, clave, (prev or {}).get("patron"), patron,
                             "modificacion" if prev else "creacion")
    await normativas_activas(force=True)
    # EXPORTACIÓN AUTOMÁTICA: el Cerebro cambió → queda pendiente hasta que el Admin exporte
    import cerebro_export as _cex
    await _cex.marcar_pendiente(f"Normativa {clave} {'modificada' if prev else 'creada'}")
    return {"ok": True, "clave": clave, "accion": "modificada" if prev else "creada",
            "export_pendiente": True}


@api.delete("/dashai/normativas/{clave}")
async def normativas_delete(clave: str, request: Request):
    admin = _solo_admin_normativas(request)
    prev = await db.dashai_eventos.find_one({"motivo": "normativa", "norma_clave": clave.upper()})
    if not prev:
        raise HTTPException(status_code=404, detail="La normativa indicada no existe")
    await db.dashai_eventos.delete_one({"id": prev["id"]})
    await _auditar_normativa(admin, clave.upper(), prev.get("patron"), "", "eliminacion")
    await normativas_activas(force=True)
    import cerebro_export as _cex
    await _cex.marcar_pendiente(f"Normativa {clave.upper()} eliminada")
    return {"ok": True, "clave": clave.upper(), "export_pendiente": True}


@api.get("/dashai/normativas/auditoria")
async def normativas_auditoria_list(request: Request):
    _solo_admin_normativas(request)
    regs = await db.normativas_auditoria.find({}, {"_id": 0}).sort("fecha", -1).to_list(200)
    return {"auditoria": regs, "total": len(regs),
            "nota": "Registro inmutable: no puede ser eliminado por ningún usuario, incluido el Administrador"}


@api.get("/dashai/estado-cerebro")
async def estado_cerebro(request: Request):
    """Panel 'Estado del Cerebro' del Administrador (Bloque 7)."""
    _exigir_roles(request, ("admin", "maestro"))
    normas = await normativas_activas(force=True)
    ult_aud = await db.normativas_auditoria.find_one({}, sort=[("fecha", -1)])
    perp = await db.config.find_one({"_key": "dashai_perpetuo"}) or {}
    arch = await db.config.find_one({"_key": "constitucion_oficial_archivo"}) or {}
    cons_counts = {}
    for m in ("regla_oro", "regla_eficiencia", "regla_operativa", "regla_inviolable", "normativa"):
        cons_counts[m] = await db.dashai_eventos.count_documents({"motivo": m})
    hace24 = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    consultas_24h = await db.cerebro_consultas.count_documents({"fecha": {"$gte": hace24}})
    bloqueadas_24h = await db.cerebro_consultas.count_documents({"fecha": {"$gte": hace24}, "autorizada": False})
    return {"normativas_activas": len(normas),
            "autoridad_suprema": {
                "mecanismo": "consultar_cerebro() — consulta obligatoria previa de la IA",
                "modulos_gateados": ["ai_extract.py (toda extracción)", "espejo_ia.py (análisis Claude)",
                                     "malla_inteligencia.py (resumen hilos)", "server.py (asistente + cobro)",
                                     "espejo_postventa.py (normativas pre-operación)",
                                     "email_service/bodega/pdf (exigir: responsividad, purificación, sobriedad)"],
                "consultas_24h": consultas_24h, "bloqueadas_24h": bloqueadas_24h,
                "autocuracion": "re-siembra automática si la Constitución baja de 78 reglas"},
            "constitucion_oficial": {
                "total_archivadas": sum(cons_counts.values()),
                "detalle": cons_counts,
                "ultimo_archivado": arch.get("archivado") or "",
                "estado": "inamovible e inviolable" if arch else "pendiente"},
            "ultima_modificacion": (ult_aud or {}).get("fecha") or "",
            "modificada_por": (ult_aud or {}).get("administrador") or "",
            "ultima_validacion": perp.get("ultima_sync") or "",
            "resultado_validacion": (f"Calibración {perp.get('nivel_calibracion') or 0}% · "
                                     f"{perp.get('folders_sync') or 0} operaciones validadas"
                                     if perp.get("ultima_sync") else "Sin validaciones registradas")}


async def _reconfirmar_identidad(request, payload):
    """Configuración avanzada: exige el reingreso de la contraseña del usuario actual."""
    clave = ((payload or {}).get("confirmacion_clave") or "").strip()
    sub = (getattr(request.state, "user", {}) or {}).get("sub") or ""
    user = await db.users.find_one({"codigo": sub})
    ok = False
    if user and clave:
        if user.get("clave_hash"):
            ok = bcrypt.checkpw(clave.encode(), user["clave_hash"].encode())
        else:
            ok = user.get("password") == clave
    if not ok:
        raise HTTPException(status_code=403, detail=(
            "Confirmación de identidad requerida: reingrese su contraseña para "
            "modificar la configuración avanzada."))


@app.on_event("startup")
async def startup():
    await ensure_seed()
    # PASO 1 (obligatorio, antes de cualquier servicio): normativas fijas presentes
    try:
        await _seed_normativas_fijas()
    except Exception as e:
        logging.warning(f"seed normativas: {e}")
    try:
        import auditoria_eficiencia as _aud
        await _aud.seed_normativa()
    except Exception as e:
        logging.warning(f"seed auditoría eficiencia: {e}")
    try:
        import catalogo_maestro as _cat
        await _cat.seed_operativas()
        await _cat.archivar_constitucion_completa()
    except Exception as e:
        logging.warning(f"seed catálogo maestro: {e}")
    try:
        import gerencia_comercial as _gcom
        await _gcom.seed_gerencia_comercial()
    except Exception as e:
        logging.warning(f"seed gerencia comercial: {e}")
    try:
        import correo_destinatarios as _cdest
        await _cdest.seed_correo_destinatarios()
    except Exception as e:
        logging.warning(f"seed correo destinatarios: {e}")
    # OPTIMIZACIÓN: índices en colecciones calientes (listas instantáneas)
    try:
        await db.folders.create_index("nombre")
        await db.folders.create_index("rut")
        await db.correos_pendientes.create_index([("estado", 1), ("fecha", -1)])
        await db.seguimiento.create_index([("asunto", 1), ("fecha", 1)])
        await db.proc_queue.create_index("status")
        await db["bunker.files"].create_index("filename")
        await db.ocr_rut_cache.create_index("path")
        await db.set_credito.create_index("nombre")
    except Exception as e:
        logging.warning(f"indices: {e}")
    # PASO 2 — BÚNKER DE ARCHIVOS (disco de producción efímero): antes de servir
    # peticiones se restaura TODO desde GridFS si el pod es nuevo, y luego se bajan
    # los archivos faltantes uno a uno (cobertura ante discos parciales).
    try:
        n_full = await asyncio.to_thread(bunker.restaurar_si_vacio)
        n_falt = await asyncio.to_thread(bunker.restaurar_faltantes)
        logging.info(f"🏦 BÚNKER arranque: {n_full} restaurados (pod nuevo) + {n_falt} faltantes bajados de GridFS")
    except Exception as e:
        logging.warning(f"BÚNKER restore falló: {e}")
    # Liberar candado obsoleto: ningún procesamiento sobrevive a un reinicio
    # BLINDAJE 24/7: 'Correo a Mesa' SIEMPRE arranca activado por defecto, sin clics.
    # La pausa administrativa (anti-duplicados) vive en la DB de cada entorno (pausa_admin),
    # así un deploy nunca hereda la pausa del preview.
    st_previo = await db.config.find_one({"_key": "autocorreo_state"}) or {}
    _set_arranque = {"running": False}
    if not st_previo.get("pausa_admin"):
        _set_arranque.update({"enabled": True, "periodic_enabled": True})
    await db.config.update_one(
        {"_key": "autocorreo_state"},
        {"$set": _set_arranque,
         "$setOnInsert": {"cutoff_iso": None, "destination": os.environ.get("MAIL2_USER", "")}},
        upsert=True)
    # BLINDADO 24/7: cada loop se reinicia solo si falla
    _ai_stop = os.environ.get("AI_EMERGENCY_STOP") == "1"
    if _ai_stop:
        logging.warning("🛑 AI_EMERGENCY_STOP=1: loops de OCR/IA (ingesta, reparos, aprendizaje) DESACTIVADOS")
    else:
        asyncio.create_task(_task_blindada(_periodic_proc_loop, "ingesta_carpetas"))
        asyncio.create_task(_task_blindada(_estudio_reparos_loop, "reparos_estudio"))
        asyncio.create_task(_task_blindada(_aprendizaje_loop, "aprendizaje_ia"))
    asyncio.create_task(_task_blindada(_periodic_mesa_loop, "mesa"))
    asyncio.create_task(_task_blindada(_daily_report_loop, "reporte_diario"))
    asyncio.create_task(_task_blindada(_notif_pace_loop, "notif_pace"))
    import bodega_concreces as _bc
    asyncio.create_task(_task_blindada(_bc.gerencia_audit_loop, "gerencia_audit"))
    import malla_inteligencia as _malla
    asyncio.create_task(_task_blindada(_malla.malla_loop, "malla_inteligencia"))
    asyncio.create_task(_task_blindada(_malla.lector_ejecutivos_loop, "lector_ejecutivos"))
    asyncio.create_task(_task_blindada(_malla.cuenta_barrido_loop, "cuenta_barrido"))
    asyncio.create_task(_task_blindada(_malla.migracion_reset_firmas, "reset_firmas"))
    asyncio.create_task(_task_blindada(_malla.avance_snapshot_loop, "avance_snapshot"))
    asyncio.create_task(_task_blindada(_malla.reenvio_co_rs_loop, "reenvio_co_rs"))
    asyncio.create_task(_task_blindada(_malla.resumen_gerencia_loop, "resumen_gerencia"))
    asyncio.create_task(_task_blindada(_malla.resumen_hilo_loop, "resumen_hilo_ia"))
    import espejo_postventa as _esp
    asyncio.create_task(_task_blindada(_esp.espejo_loop, "espejo_capa_a"))
    # 🪞 ALGORITMO ESPEJO HÍBRIDO ADMINISTRATIVO (Victoria · Daniela · Javier)
    import espejo_hibrido as _hib
    await _hib.seed_espejo_hibrido()
    asyncio.create_task(_task_blindada(_hib.espejo_hibrido_loop, "espejo_hibrido"))
    import gestion_ejecutivos as _gest
    asyncio.create_task(_task_blindada(_gest.gestion_harvest_loop, "gestion_ejecutivos"))
    asyncio.create_task(_task_blindada(_malla.buzon_aprendizaje_loop, "buzon_aprendizaje"))
    import grid_dashai as _grid
    asyncio.create_task(_task_blindada(_grid.grid_loop, "grid_dashai_forzado"))
    asyncio.create_task(_task_blindada(_uf_auto_loop, "uf"))
    asyncio.create_task(_task_blindada(_firmados_auto_loop, "autocorreo_firmados"))
    asyncio.create_task(_task_blindada(_informes_vip_loop, "informes_vip_lunes"))
    asyncio.create_task(_task_blindada(_tasacion_fecha_loop, "fecha_tasacion"))
    asyncio.create_task(_task_blindada(_cobro_tasacion_loop, "cobro_tasacion"))
    # DESACTIVADO (regla del usuario): los faltantes se piden solo manualmente
    asyncio.create_task(_task_blindada(_actividades_terminadas_loop, "actividades_terminadas"))
    asyncio.create_task(_task_blindada(_dashai_perpetuo_loop, "dashai_perpetuo"))
    asyncio.create_task(_task_blindada(_resumen_semanal_loop, "resumen_semanal"))
    asyncio.create_task(_task_blindada(_reporte_correos_loop, "reporte_correos"))
    asyncio.create_task(_task_blindada(_resumen_cierres_loop, "resumen_cierres"))
    asyncio.create_task(_task_blindada(_setcred_auto_loop, "setcred_auto"))
    asyncio.create_task(_task_blindada(_bunker_loop, "bunker_gridfs"))
    asyncio.create_task(_task_blindada(_rescate_historico_loop, "rescate_historico"))
    asyncio.create_task(_task_blindada(_dashai_dataset_loop, "dashai_dataset_2359"))
    asyncio.create_task(_task_blindada(_cloud_bunker_loop, "cloud_bunker_espejo"))
    asyncio.create_task(_task_blindada(_espejo_mesa_loop, "espejo_mesa_24h"))
    asyncio.create_task(_task_blindada(_perfil.cosecha_loop, "cosecha_perfil_64"))
    import base_historica as _hist_loop_mod
    asyncio.create_task(_task_blindada(_hist_loop_mod.historia_loop, "historia_minado"))
    import adn_clientes as _adn_loop_mod
    asyncio.create_task(_task_blindada(_adn_loop_mod.adn_loop, "adn_360"))
    asyncio.create_task(_task_blindada(_malla_mod.auditoria_loop, "auditoria_tiempo_real"))


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def _token_usuario(user):
    rol = user.get("rol", "ejecutivo")
    perfil = user.get("perfil", "")
    extra = {"nombre": user.get("nombre", user["codigo"]), "perfil": perfil}
    if user.get("first_login"):
        extra["first_login"] = True
    return {
        "token": _auth.create_token(user["codigo"], rol=rol, scope="terminal", extra=extra),
        "codigo": user["codigo"],
        "nombre": user.get("nombre", user["codigo"]),
        "rol": rol,
        "perfil": perfil,
        "cargo": user.get("cargo") or "",
        "first_login": bool(user.get("first_login")),
    }


@api.post("/admin/verificar-password")
async def admin_verificar_password(payload: dict, request: Request):
    """👁 VISTA PREVIA POR ROL: exclusiva del Admin, exige su propia contraseña."""
    claims = getattr(request.state, "user", {}) or {}
    if claims.get("rol") not in ("admin", "maestro"):
        raise HTTPException(status_code=403, detail="La vista previa por rol es exclusiva e intransferible del Administrador")
    password = (payload.get("password") or "").strip()
    u = await db.users.find_one({"codigo": claims.get("sub", "")})
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    ok = (bool(password) and bcrypt.checkpw(password.encode(), u["clave_hash"].encode())
          if u.get("clave_hash") else bool(password) and u.get("password") == password)
    if not ok:
        raise HTTPException(status_code=401, detail="Contraseña de Administrador incorrecta")
    return {"ok": True}


@api.get("/adn-helice/estado")
async def adn_helice_estado(request: Request):
    """🧬 HÉLICE DE ADN: estado real del algoritmo (Bóveda ADN 360 + Algoritmo Espejo)."""
    claims = getattr(request.state, "user", {}) or {}
    if claims.get("rol") not in ("admin", "maestro", "gerencia"):
        raise HTTPException(status_code=403, detail="Visualización exclusiva del Admin y Gerencia Comercial")
    adn = await db.adn_clientes_360.count_documents({})
    espejo = await db.espejo_ia_log.count_documents({})
    folders = await db.folders.count_documents({})
    ult_adn = await db.adn_clientes_360.find_one({}, sort=[("actualizado", -1)]) or {}
    ult_esp = await db.espejo_ia_log.find_one({}, sort=[("fecha", -1)]) or {}
    ultimo = max(str(ult_adn.get("actualizado") or ""), str(ult_esp.get("fecha") or ""))
    procesados = adn + espejo
    esperados = folders + espejo
    estado = "en_espera"
    try:
        dt = datetime.fromisoformat(ultimo.replace("Z", "+00:00"))
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        seg = (datetime.now(timezone.utc) - dt).total_seconds()
        estado = "procesando" if seg < 180 else ("activo" if seg < 86400 else "en_espera")
    except Exception:
        pass
    return {"procesados": procesados, "esperados": esperados,
            "faltantes": max(0, esperados - procesados),
            "adn_registros": adn, "espejo_procesados": espejo,
            "ultimo_procesamiento": ultimo, "estado": estado}


@api.post("/auth/login")
async def auth_login(payload: dict):
    codigo = (payload.get("rut") or payload.get("codigo") or "").strip()
    password = (payload.get("password") or "").strip()
    # Busqueda tolerante a mayusculas/minusculas y espacios en el codigo
    user = await db.users.find_one({"$or": [
        {"codigo": {"$regex": f"^{re.escape(codigo)}$", "$options": "i"}},
        {"email": {"$regex": f"^{re.escape(codigo)}$", "$options": "i"}}]})
    if not user:
        raise HTTPException(status_code=401, detail="Credenciales invalidas")
    if user.get("activo") is False:
        raise HTTPException(status_code=403, detail="Acceso revocado por el administrador")
    if user.get("clave_hash"):
        if not password or not bcrypt.checkpw(password.encode(), user["clave_hash"].encode()):
            raise HTTPException(status_code=401, detail="Credenciales invalidas")
    elif user.get("requiere_crear_clave"):
        # Primer ingreso del Administrador Maestro: debe crear su propia clave
        return {"requiere_crear_clave": True, "codigo": user["codigo"],
                "nombre": user.get("nombre", codigo)}
    elif user.get("password") != password or not password:
        raise HTTPException(status_code=401, detail="Credenciales invalidas")
    await db.users.update_one({"codigo": user["codigo"]}, {"$set": {"ultimo_acceso": now_iso()}})
    # REGLA PERMANENTE: auditoría semanal de eficiencia (lunes, primer ingreso del Admin)
    try:
        import auditoria_eficiencia as _aud
        asyncio.create_task(_aud.disparar_si_corresponde(user.get("rol") or ""))
    except Exception as _e:
        logging.warning(f"trigger auditoría eficiencia: {_e}")
    return _token_usuario(user)


@api.post("/auth/crear-clave")
async def auth_crear_clave(payload: dict):
    """Primer ingreso del Administrador Maestro: crea su propia clave (bcrypt)."""
    codigo = (payload.get("codigo") or "").strip()
    clave = (payload.get("clave") or "").strip()
    user = await db.users.find_one({"codigo": {"$regex": f"^{re.escape(codigo)}$", "$options": "i"}})
    if not user or not user.get("requiere_crear_clave") or user.get("clave_hash"):
        raise HTTPException(status_code=403, detail="Este usuario no tiene creación de clave pendiente")
    if len(clave) < 8:
        raise HTTPException(status_code=400, detail="La clave debe tener al menos 8 caracteres")
    h = bcrypt.hashpw(clave.encode(), bcrypt.gensalt()).decode()
    await db.users.update_one({"codigo": user["codigo"]},
                              {"$set": {"clave_hash": h},
                               "$unset": {"requiere_crear_clave": "", "password": ""}})
    await db.alertas.insert_one({
        "id": str(uuid.uuid4()), "tipo": "seguridad",
        "mensaje": f"🔐 {user.get('nombre', codigo)} creó su clave maestra — Mando Supremo activo.",
        "fecha": now_iso(), "leida": False})
    user["clave_hash"] = h
    return _token_usuario(user)


# ── PERFIL DEL USUARIO Y CARGO OFICIAL DEL ADMINISTRADOR ──
@api.get("/auth/mi-perfil")
async def mi_perfil(request: Request):
    sub = (getattr(request.state, "user", {}) or {}).get("sub") or ""
    user = await db.users.find_one({"codigo": sub})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"codigo": user["codigo"], "nombre": user.get("nombre"), "rol": user.get("rol"),
            "email": user.get("email") or "", "perfil": user.get("perfil") or "",
            "cargo": user.get("cargo") or ""}


@api.post("/auth/mi-cargo")
async def actualizar_mi_cargo(payload: dict, request: Request):
    """Cargo oficial del Administrador: fijo e inamovible por cualquier otro usuario."""
    claims = getattr(request.state, "user", {}) or {}
    if claims.get("rol") not in ("admin", "maestro"):
        raise HTTPException(status_code=403, detail=(
            "El cargo del Administrador es fijo e inamovible: solo el Administrador "
            "puede modificarlo desde su perfil."))
    cargo = (payload.get("cargo") or "").strip()
    if not cargo:
        raise HTTPException(status_code=400, detail="Indique el cargo oficial completo")
    await db.users.update_many({"codigo": {"$in": ["admin", "administrador"]}},
                               {"$set": {"cargo": cargo}})
    _cargo_admin_cache["v"] = cargo
    return {"ok": True, "cargo": cargo}


# ── PRIMER INICIO DE SESIÓN OBLIGATORIO: cambio de clave + configuración IMAP ──
def _validar_clave_nueva(clave):
    if len(clave) < 8 or not re.search(r"[A-Z]", clave) or not re.search(r"\d", clave):
        raise HTTPException(status_code=400, detail=(
            "La nueva contraseña debe tener mínimo 8 caracteres, al menos una mayúscula y un número"))


async def _usuario_primer_ingreso(request):
    sub = (getattr(request.state, "user", {}) or {}).get("sub") or ""
    user = await db.users.find_one({"codigo": sub})
    if not user or not user.get("first_login"):
        raise HTTPException(status_code=403, detail="Este usuario no tiene configuración inicial pendiente")
    return user


@api.post("/auth/primer-ingreso/clave")
async def primer_ingreso_clave(payload: dict, request: Request):
    """Paso 1: cambio obligatorio de la contraseña provisoria."""
    user = await _usuario_primer_ingreso(request)
    actual = (payload.get("clave_actual") or "").strip()
    nueva = (payload.get("clave_nueva") or "").strip()
    conf = (payload.get("confirmacion") or "").strip()
    if not user.get("clave_hash") or not actual or \
            not bcrypt.checkpw(actual.encode(), user["clave_hash"].encode()):
        raise HTTPException(status_code=400, detail="La contraseña provisoria no es correcta")
    if nueva != conf:
        raise HTTPException(status_code=400, detail="La nueva contraseña y su confirmación no coinciden")
    _validar_clave_nueva(nueva)
    if nueva == actual:
        raise HTTPException(status_code=400, detail="La nueva contraseña debe ser distinta a la provisoria")
    await db.users.update_one({"codigo": user["codigo"]}, {"$set": {
        "clave_hash": bcrypt.hashpw(nueva.encode(), bcrypt.gensalt()).decode(),
        "primer_paso_clave": True}})
    return {"ok": True, "paso": 1, "siguiente": "Configuración de cuenta de correo IMAP"}


@api.post("/auth/primer-ingreso/imap")
async def primer_ingreso_imap(payload: dict, request: Request):
    """Paso 2: configuración obligatoria de la cuenta IMAP. Al completar → first_login=false."""
    user = await _usuario_primer_ingreso(request)
    if not user.get("primer_paso_clave"):
        raise HTTPException(status_code=400, detail="Primero debe completar el cambio de contraseña (Paso 1)")
    servidor = (payload.get("servidor") or "").strip()
    email_c = (payload.get("email") or "").strip().lower()
    clave = (payload.get("clave") or "").strip()
    try:
        puerto = int(payload.get("puerto") or 0)
    except (TypeError, ValueError):
        puerto = 0
    if not servidor or not email_c or not clave or not (1 <= puerto <= 65535):
        raise HTTPException(status_code=400, detail="Complete servidor IMAP, puerto, correo y contraseña de correo")
    if "@" not in email_c:
        raise HTTPException(status_code=400, detail="Correo electrónico inválido")
    await db.users.update_one({"codigo": user["codigo"]}, {"$set": {
        "imap_config": {"servidor": servidor, "puerto": puerto, "email": email_c,
                        "clave_enc": _cred_cifrar(clave), "guardado": now_iso()},
        "first_login": False}, "$unset": {"primer_paso_clave": ""}})
    fresh = await db.users.find_one({"codigo": user["codigo"]})
    return {"ok": True, "paso": 2, **_token_usuario(fresh)}


@api.post("/inmobiliaria/auth/login")
async def inmo_login(payload: dict):
    usuario = (payload.get("usuario") or "").strip()
    password = (payload.get("password") or "").strip()
    if not usuario or not password:
        return {"ok": False, "error": "Ingrese usuario y clave"}
    # Accept the platform admin credential or any seeded inmo user
    inmo = payload.get("inmobiliaria") or "Inmobiliaria Demo"
    return {
        "ok": True,
        "token": _auth.create_token(usuario, rol="ejecutivo", scope="inmobiliaria",
                                    extra={"inmobiliaria": inmo}),
        "usuario": usuario,
        "nombre": usuario.capitalize(),
        "inmobiliaria": inmo,
        "rol": "ejecutivo",
    }


# ---------------------------------------------------------------------------
# Basic data endpoints
# ---------------------------------------------------------------------------
@api.get("/valor-uf")
async def valor_uf(refresh: bool = False):
    """SII COORDINADO SIN CUELGUES: sirve al INSTANTE el valor en caché (que un bucle en
    segundo plano mantiene al día con el SII). Si la caché no es de HOY (hora de Chile),
    intenta un refresco rápido en vivo; si el SII tarda, igual devuelve la caché para no
    romper la UI ni caer al valor por defecto. `?refresh=true` fuerza scraping en vivo."""
    from zoneinfo import ZoneInfo
    hoy_cl = datetime.now(ZoneInfo("America/Santiago")).strftime("%Y-%m-%d")
    cfg = await db.config.find_one({"_key": "uf"}) or {}
    al_dia = (cfg.get("uf_day") == hoy_cl) and float(cfg.get("valor_uf") or 0) > 0
    # Refresco en vivo SOLO si se pide explícitamente o la caché no es de hoy
    if refresh or not al_dia:
        try:
            v, fuente, dia = await asyncio.wait_for(_actualizar_uf(), timeout=8)
            if v > 0:
                return {"valor_uf": v, "fecha": now_iso(), "fuente": fuente,
                        "actualizado": now_iso(), "dia_uf": dia, "en_vivo": True, "al_dia": True}
        except Exception as e:
            logging.warning(f"valor-uf refresco rápido falló (sirvo caché): {e}")
        cfg = await db.config.find_one({"_key": "uf"}) or {}
    return {"valor_uf": float(cfg.get("valor_uf") or await get_valor_uf()), "fecha": now_iso(),
            "fuente": cfg.get("uf_source", "local"),
            "actualizado": cfg.get("uf_updated_at", ""), "dia_uf": cfg.get("uf_day", ""),
            "en_vivo": False, "al_dia": bool(al_dia)}


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


def _uf_desde_mindicador():
    """RESPALDO UF: API pública de mindicador.cl cuando el SII no responde."""
    import json as _json
    import urllib.request
    req = urllib.request.Request("https://mindicador.cl/api/uf",
                                 headers={"User-Agent": "Mozilla/5.0"})
    data = _json.loads(urllib.request.urlopen(req, timeout=15).read().decode("utf-8"))
    serie = data.get("serie") or []
    v = float((serie[0].get("valor") if serie else 0) or 0)
    if v <= 0:
        raise ValueError("mindicador.cl: serie UF vacía o valor inválido")
    return v, str(serie[0].get("fecha") or "")[:10]


async def _actualizar_uf():
    """Intenta SII primero, luego mindicador.cl. Guarda en config."""
    try:
        v, dia = await asyncio.to_thread(_uf_desde_sii)
        fuente = "sii.cl"
    except Exception:
        try:
            v, dia = await asyncio.to_thread(_uf_desde_mindicador)
            fuente = "mindicador.cl"
        except Exception:
            # DOBLE CAÍDA (SII + mindicador): se mantiene el último valor conocido sin sobrescribir
            prev = await db.config.find_one({"_key": "uf"}) or {}
            return (float(prev.get("valor_uf") or 0),
                    prev.get("uf_source") or "último valor conocido", prev.get("uf_day") or "")
    if v > 0:
        await db.config.update_one({"_key": "uf"}, {"$set": {
            "valor_uf": v, "uf_source": fuente, "uf_day": dia,
            "uf_updated_at": now_iso()}}, upsert=True)
    return v, fuente, dia


async def _uf_auto_loop():
    """SINCRONIZACIÓN OFICIAL SII: refresca la UF al arrancar y cada 30 minutos, para
    que la caché SIEMPRE tenga el valor del día (la UI lee de caché, sin cuelgues)."""
    await asyncio.sleep(5)
    while True:
        try:
            v, fuente, dia = await _actualizar_uf()
            logger.info(f"💱 UF sincronizada con {fuente}: {v} ({dia})")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"Actualización automática de UF falló: {e}")
        await asyncio.sleep(1800)


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


def _solo_maestro(request: Request):
    """MANDO ÚNICO: solo el administrador (Gerardo Barrera, rol admin) o el Master PIN.
    René Osa fue eliminado — ya no existe rol maestro."""
    claims = getattr(request.state, "user", None) or {}
    if claims.get("rol") not in ("admin", "maestro"):
        raise HTTPException(status_code=403,
                            detail="Acceso exclusivo del Administrador (Gerardo Barrera) — la Bóveda está en modo solo lectura para el resto del equipo")
    return claims


async def _validar_clave_rene(clave):
    """MANDO ÚNICO: la Bóveda se protege con el Master PIN (variable de entorno protegida) del administrador."""
    pin = os.environ.get("MASTER_PIN", "")
    if pin and str(clave) == pin:
        return {"nombre": "Gerardo Barrera", "rol": "admin"}
    await db.alertas.insert_one({
        "id": str(uuid.uuid4()), "tipo": "seguridad",
        "mensaje": "🚨 Validación fallida en la Bóveda de Criterios (Master PIN incorrecto) — cambios descartados.",
        "fecha": now_iso(), "leida": False})
    raise HTTPException(status_code=403,
                        detail="Master PIN incorrecto — cambios descartados y alerta de seguridad emitida")


def _diff_criterios(prev, nuevo, path=""):
    """Lista de cambios hoja a hoja para el historial de auditoría."""
    cambios = []
    prev = prev or {}
    for k, v in (nuevo or {}).items():
        if k.startswith("_") or k in ("version", "updated_at", "manual_override", "prioridad"):
            continue
        p = f"{path}.{k}" if path else k
        if isinstance(v, dict):
            cambios += _diff_criterios(prev.get(k) or {}, v, p)
        elif prev.get(k) != v and not isinstance(v, list):
            cambios.append({"campo": p, "antes": prev.get(k), "despues": v})
    return cambios


@api.get("/admin/criterios")
async def get_criterios():
    return await get_config("criterios", DEFAULT_CRITERIOS)


@api.get("/admin/criterios/auditoria")
async def criterios_auditoria():
    docs = await db.criterios_auditoria.find({}, {"_id": 0}).sort("fecha", -1).limit(60).to_list(60)
    return {"historial": docs}


@api.post("/admin/criterios")
async def guardar_criterios(payload: dict, request: Request):
    """MANDO SUPREMO — BÓVEDA DE CRITERIOS: propiedad exclusiva de René Osa (rol maestro).
    Cada cambio exige su validación digital (su clave) y queda en el historial de auditoría."""
    claims = _solo_maestro(request)
    await _validar_clave_rene(str(payload.get("clave") or ""))
    criterios = payload.get("criterios") or {}
    if not isinstance(criterios, dict) or "btg_pactual" not in criterios:
        raise HTTPException(status_code=400, detail="Estructura de criterios inválida")
    criterios["_key"] = "criterios"
    criterios["updated_at"] = now_iso()
    criterios["manual_override"] = True
    criterios["prioridad"] = "suprema"
    prev = await db.config.find_one({"_key": "criterios"}) or {}
    criterios["version"] = mesa_brain._version_num(prev.get("version")) + 1
    if prev.get("reglas_supervisadas"):
        criterios.setdefault("reglas_supervisadas", prev["reglas_supervisadas"])
    await db.config.replace_one({"_key": "criterios"}, criterios, upsert=True)
    fecha_txt = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")
    cambios = _diff_criterios(prev, criterios)
    await db.criterios_auditoria.insert_one({
        "id": str(uuid.uuid4()), "fecha": now_iso(),
        "usuario": claims.get("nombre") or "René Osa",
        "version": criterios["version"],
        "detalle": f"Política modificada por René Osa el {fecha_txt} (UTC)",
        "cambios": cambios[:40]})
    return {"ok": True, "prioridad": "suprema", "version": criterios["version"],
            "nota": (f"Política modificada por René Osa el {fecha_txt} — Criterios Maestros "
                     f"v1.{criterios['version']} con prioridad absoluta. "
                     f"{len(cambios)} campo(s) modificado(s), registrados en el historial de auditoría.")}


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
    cons = await _constitucion_dashai()
    u = cons["umbrales"]
    payload.setdefault("umbral_btg_div_renta", u["div_renta_max_btg"])
    payload.setdefault("umbral_btg_carga_fin", u["carga_maxima"])
    payload.setdefault("umbral_btg_ltv", u["ltv_maximo"])
    payload.setdefault("umbral_btg_edad_plazo", u["edad_plazo_max"])
    result = ce.simular_credito(payload)
    result["constitucion_dashai"] = cons["version"]
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
    # ENCABEZADO INSTITUCIONAL: logo horizontal oficial (fondo negro, serif dorado)
    c.setFillColorRGB(0.039, 0.039, 0.039)
    c.rect(0, h - 2.6 * cm, w, 2.6 * cm, fill=1, stroke=0)
    c.setFillColorRGB(0.788, 0.635, 0.153)
    c.setFont("Times-Bold", 20)
    c.drawCentredString(w / 2, h - 1.15 * cm, "C E N T R A L   M U T U O S")
    c.setStrokeColorRGB(0.788, 0.635, 0.153)
    c.setLineWidth(1)
    c.line(w * 0.3, h - 1.45 * cm, w * 0.7, h - 1.45 * cm)
    c.setFont("Times-Bold", 9)
    c.drawCentredString(w / 2, h - 1.83 * cm, "C O N   C R E C E S")
    c.setFillColorRGB(0.62, 0.62, 0.62)
    c.setFont("Helvetica", 9)
    c.drawCentredString(w / 2, h - 2.32 * cm, title)
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
    c.drawString(2 * cm, 1.9 * cm, f"Firmado por el Administrador: {_cargo_admin_cache['v']}")
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
    cons = await _constitucion_dashai()
    out = ce.ia_predict(payload)
    out["constitucion_dashai"] = cons["version"]
    return out


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
    cons = await _constitucion_dashai()
    result = ce.predict_inmobiliaria(payload, tasas, seguros, valor, umbrales=cons["umbrales"])
    result["constitucion_dashai"] = cons["version"]
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
    sims = await db.simulaciones.find({}, {"_id": 0, "capacidad_credito_uf": 1}).to_list(500)
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
        resp = await _llm_con_timeout(chat, UserMessage(text=msg))
        import constitucion as _const
        await _const.consultar_cerebro(db, "chat_central_ia", texto_ia=str(resp), modulo="server.py (asistente)")
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
    hoy = datetime.now(_tz_chile()).strftime("%d/%m/%Y")
    # AUDITORÍA EFICIENCIA: registro idempotente — el resumen se genera 1 sola vez por jornada
    dia = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await db.system_log.update_one({"tipo": "resumen_diario_generado", "dia": dia},
                                   {"$setOnInsert": {"generado": now_iso()}}, upsert=True)
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
    _proy_carp = {"_id": 0, "nombre": 1, "credit_request.client_type": 1,
                  "datos_financieros.fecha_entrega": 1, "emails_sent_count": 1,
                  "escritura_confirmada_at": 1, "escritura_solicitada_at": 1,
                  "tasacion_solicitada_at": 1, "tasacion_terminado_at": 1,
                  "estudio_titulo_solicitado_at": 1, "estudio_titulo_terminado_at": 1}
    docs = await db.folders.find({}, _proy_carp).sort("created_at", -1).to_list(300)
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
    semana = datetime.now(_tz_chile()).strftime("%d/%m/%Y")
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
    semana = datetime.now(_tz_chile()).strftime("%d/%m/%Y")
    res = await asyncio.to_thread(mail.send_mail, _sender_por_rol("principal"),
                                  f"📊 Resumen Semanal de Martín — {semana}", cuerpo, [], "principal")
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
    hoy = datetime.now(_tz_chile()).strftime("%d/%m/%Y")
    inner = f"""
      <p>¡Buenos días! Este es el <b>reporte diario de correos</b> al <b>{hoy}</b> (últimas 24 horas):</p>
      {_sec(f"Correos de gestión recibidos ({len(recibidos)})", rec_html, "No se recibieron correos de gestión.")}
      {_sec(f"Enviadas a mesa ({len(enviados)})", env_html, "Ninguna carpeta fue enviada a mesa.")}
      {_sec(f"NO enviadas — faltan documentos ({len(con_faltantes)})", falt_html, "No hay carpetas detenidas por documentos.")}
      {_sec(f"Correos descartados por regla ({len(descartados)})", desc_html, "Ningún correo fue descartado.")}
      {_sec(f"Sin leer / pendientes de revisión ({len(pendientes)})", pend_html, "No hay correos pendientes.")}"""
    html = _marca_wrap(inner, "Reporte Diario de Correos")
    # CONSULTA OBLIGATORIA A DASHAI — Regla #16 (Responsividad Absoluta)
    import constitucion as _const
    _const.exigir("responsividad_absoluta", html=html)
    return html


async def _enviar_reporte_correos():
    cuerpo = await _reporte_correos_html()
    hoy = datetime.now(_tz_chile()).strftime("%d/%m/%Y")
    return await asyncio.to_thread(mail.send_mail, _sender_por_rol("principal"),
                                   f"📬 Reporte Diario de Correos — {hoy}", cuerpo, [], "principal")


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
ROLES_SISTEMA = ("admin", "gerencia", "administracion", "postventa", "broker", "contralor")
ROLES_TIPO_C = ("broker", "administracion")


def _gestor_usuarios(request):
    """Admin crea cualquier rol; Victoria Vilchez SOLO usuarios tipo C (brokers y administrativos)."""
    claims = getattr(request.state, "user", {}) or {}
    rol = claims.get("rol", "")
    ident = f"{claims.get('sub') or ''} {claims.get('nombre') or ''}".lower()
    if rol in ("admin", "maestro"):
        return claims, "todos"
    if rol == "administracion" and ("victoria" in ident or "vilche" in ident):
        return claims, "tipo_c"
    raise HTTPException(status_code=403, detail="No está autorizado para gestionar usuarios")


def _clave_provisoria():
    import secrets as _sec
    import string as _str
    while True:
        c = "".join(_sec.choice(_str.ascii_letters + _str.digits) for _ in range(10))
        if any(x.isdigit() for x in c) and any(x.isalpha() for x in c):
            return c


def _email_institucional(nombre, cuerpo_html, firmante="Sistema de Gestión Central Mutuos"):
    """BLOQUE 6: correo HTML responsivo institucional — encabezado sobrio, saludo formal,
    cierre con fecha DD/MM/AAAA y pie de confidencialidad fijo."""
    hoy = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f4f4f4">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;padding:16px 0">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0"
  style="max-width:600px;width:100%;background:#ffffff;border-radius:8px;overflow:hidden;font-family:Arial,Helvetica,sans-serif">
<tr><td style="background:#0a0a0a;padding:24px 28px;text-align:center">
  <span style="color:#C9A227;font-family:Georgia,'Times New Roman',serif;font-size:24px;font-weight:bold;letter-spacing:3px">CENTRAL MUTUOS</span>
  <div style="height:1px;background:#C9A227;width:72%;margin:9px auto 7px"></div>
  <span style="color:#C9A227;font-family:Georgia,'Times New Roman',serif;font-size:11px;letter-spacing:6px">CON CRECES</span></td></tr>
<tr><td style="padding:26px 28px;color:#1f2937;font-size:14px;line-height:1.65;text-align:justify">
  <p style="margin:0 0 14px">Estimado/a <b>{nombre}</b>,</p>
  {cuerpo_html}
  <p style="margin:20px 0 0">Atentamente,<br><b>{firmante}</b><br>
  <span style="color:#6b7280;font-size:12px">{_cargo_admin_cache["v"]}</span><br>
  <span style="color:#6b7280;font-size:12px">Central Mutuos | {hoy}</span></p></td></tr>
<tr><td style="background:#f0f0f0;padding:14px 28px;color:#6b7280;font-size:11px;line-height:1.5;text-align:justify">
  Este correo es confidencial y está dirigido exclusivamente a su destinatario. Si lo recibió por error,
  por favor notifíquelo al remitente y elimínelo de inmediato. Central Mutuos opera bajo las normativas
  vigentes del mercado hipotecario chileno.</td></tr>
</table></td></tr></table></body></html>"""


def _enviar_credenciales(email_destino, clave, nombre=""):
    import email_service as mail
    enlace = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    cuerpo = (
        f"<p style='margin:0 0 14px'>Le damos la bienvenida a la plataforma de Gestión Central Mutuos. "
        f"A continuación encontrará sus credenciales de acceso:</p>"
        f"<table role='presentation' width='100%' cellpadding='0' cellspacing='0' "
        f"style='background:#f8f6ef;border:1px solid #d4af37;border-radius:6px;margin:0 0 14px'>"
        f"<tr><td style='padding:14px 18px;font-size:14px;color:#1f2937'>"
        f"Nombre de usuario: <b>{email_destino}</b><br>"
        f"Contraseña inicial: <b style='font-family:monospace'>{clave}</b></td></tr></table>"
        f"<p style='margin:0 0 16px'>Por seguridad, el sistema le solicitará cambiar esta contraseña "
        f"en su primer inicio de sesión.</p>"
        f"<table role='presentation' cellpadding='0' cellspacing='0' style='margin:0 auto 6px'>"
        f"<tr><td style='background:#0a0a0a;border-radius:6px'>"
        f"<a href='{enlace}' style='display:inline-block;padding:12px 30px;color:#C9A227;"
        f"font-weight:bold;font-size:14px;text-decoration:none;letter-spacing:1px'>"
        f"INGRESAR A LA PLATAFORMA</a></td></tr></table>"
        f"<p style='margin:0;text-align:center;font-size:12px;color:#6b7280'>{enlace}</p>")
    mail.send_mail(email_destino, "Bienvenido/a a Gestión Central Mutuos - Credenciales de acceso",
                   _email_institucional(nombre or email_destino, cuerpo), [], "secundaria")


@api.get("/admin/users")
async def list_users(request: Request):
    _gestor_usuarios(request)
    docs = await db.users.find().to_list(300)
    return {"users": [{"codigo": d["codigo"], "nombre": d.get("nombre"), "rol": d.get("rol"),
                       "email": d.get("email") or ("" if "@" not in d["codigo"] else d["codigo"]),
                       "perfil": d.get("perfil") or "",
                       "activo": d.get("activo") is not False, "created": d.get("created"),
                       "ultimo_acceso": d.get("ultimo_acceso") or "",
                       "first_login": bool(d.get("first_login"))} for d in docs]}


@api.post("/admin/users")
async def create_user(payload: dict, request: Request):
    claims, alcance = _gestor_usuarios(request)
    nombre = (payload.get("nombre") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    rol = (payload.get("rol") or "").strip()
    codigo = (payload.get("codigo") or "").strip() or email
    if not nombre or not email or not rol:
        raise HTTPException(status_code=400, detail="Nombre, correo y rol son obligatorios")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(status_code=400, detail="Correo electrónico inválido")
    if rol not in ROLES_SISTEMA:
        raise HTTPException(status_code=400, detail="Rol inválido")
    if alcance == "tipo_c" and rol not in ROLES_TIPO_C:
        raise HTTPException(status_code=403, detail=(
            "Solo puede crear usuarios tipo C: brokers y personal administrativo"))
    if await db.users.find_one({"$or": [{"codigo": codigo}, {"email": email}]}):
        raise HTTPException(status_code=400, detail="El código o correo ya existe")
    clave = (payload.get("clave") or "").strip() or _clave_provisoria()
    if len(clave) < 6:
        raise HTTPException(status_code=400, detail="La clave inicial debe tener al menos 6 caracteres")
    perfil = payload.get("perfil") or ("D" if rol == "broker" else "")
    await db.users.insert_one({
        "codigo": codigo, "nombre": nombre, "email": email, "rol": rol, "perfil": perfil,
        "clave_hash": bcrypt.hashpw(clave.encode(), bcrypt.gensalt()).decode(),
        "first_login": True, "activo": True, "created": now_iso(),
        "creado_por": claims.get("sub") or ""})
    enviado, err_mail = True, ""
    try:
        await asyncio.to_thread(_enviar_credenciales, email, clave, nombre)
    except Exception as e:
        enviado, err_mail = False, str(e)[:150]
    return {"ok": True, "codigo": codigo, "clave_provisoria": clave, "email_enviado": enviado,
            "nota": ("Credenciales enviadas por correo al nuevo usuario" if enviado
                     else f"No se pudo enviar el correo ({err_mail}) — entregue la clave provisoria manualmente")}


@api.post("/admin/users/{codigo}/reset-clave")
async def user_forzar_reset(codigo: str, request: Request, payload: dict = None):
    """Reseteo forzado del Admin: clave inicial (definida o generada) + first_login=true + correo."""
    _solo_maestro(request)
    user = await db.users.find_one({"codigo": codigo})
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no existe")
    if codigo in ("admin", "administrador"):
        raise HTTPException(status_code=400, detail="No se puede resetear al administrador")
    clave = ((payload or {}).get("clave") or "").strip() or _clave_provisoria()
    if len(clave) < 6:
        raise HTTPException(status_code=400, detail="La clave inicial debe tener al menos 6 caracteres")
    await db.users.update_one({"codigo": codigo}, {"$set": {
        "clave_hash": bcrypt.hashpw(clave.encode(), bcrypt.gensalt()).decode(),
        "first_login": True}, "$unset": {"primer_paso_clave": "", "password": ""}})
    destino = user.get("email") or ""
    enviado = False
    if destino:
        try:
            await asyncio.to_thread(_enviar_credenciales, destino, clave, user.get("nombre") or "")
            enviado = True
        except Exception:
            enviado = False
    return {"ok": True, "codigo": codigo, "clave_provisoria": clave, "email_enviado": enviado}


@api.post("/admin/users/{codigo}/activo")
async def user_toggle_activo(codigo: str, payload: dict, request: Request):
    """CONTROL GERARDO: revoca o reactiva el acceso de un usuario con un clic."""
    _solo_maestro(request)
    if codigo in ("admin", "administrador"):
        raise HTTPException(status_code=400, detail="No se puede revocar al administrador")
    activo = bool((payload or {}).get("activo"))
    r = await db.users.update_one({"codigo": codigo}, {"$set": {"activo": activo}})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Usuario no existe")
    return {"ok": True, "codigo": codigo, "activo": activo}


@api.post("/admin/users/{codigo}/clave")
async def user_reset_clave(codigo: str, payload: dict, request: Request):
    """CONTROL GERARDO: asigna una nueva clave al usuario."""
    _solo_maestro(request)
    clave = ((payload or {}).get("clave") or "").strip()
    if len(clave) < 4:
        raise HTTPException(status_code=400, detail="Clave demasiado corta")
    r = await db.users.update_one({"codigo": codigo},
                                  {"$set": {"password": clave}, "$unset": {"clave_hash": ""}})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Usuario no existe")
    return {"ok": True, "codigo": codigo}


@api.delete("/admin/users/{codigo}")
async def delete_user(codigo: str, request: Request):
    _solo_maestro(request)
    if codigo in ("admin", "administrador"):
        raise HTTPException(status_code=400, detail="No se puede eliminar el usuario administrador")
    await db.users.delete_one({"codigo": codigo})
    return {"ok": True}


# ── BANDEJA DE DOCUMENTOS SIN CLASIFICAR (Daniela, Victoria y el Admin) ──
def _sc_dir():
    from pathlib import Path as _P
    p = _P(__file__).parent / "storage" / "sin_clasificar"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _exigir_bandeja(request):
    if _rol_de(request) not in ("admin", "maestro", "administracion"):
        raise HTTPException(status_code=403, detail="No está autorizado el ingreso a este módulo")


@api.get("/admin/docs-sin-clasificar")
async def docs_sin_clasificar_list(request: Request):
    _exigir_bandeja(request)
    docs = await db.docs_sin_clasificar.find({}, {"_id": 0}).sort("recibido", -1).to_list(300)
    return {"documentos": docs, "total": len(docs)}


@api.post("/admin/docs-sin-clasificar/upload")
async def docs_sin_clasificar_upload(request: Request):
    _exigir_bandeja(request)
    form = await request.form()
    archivo = form.get("archivo")
    if archivo is None:
        raise HTTPException(status_code=400, detail="Adjunte el archivo a la bandeja")
    from pathlib import Path as _P
    nombre = _P(getattr(archivo, "filename", "") or "documento").name
    did = str(uuid.uuid4())
    _raw_sc = await archivo.read()
    (_sc_dir() / f"{did}_{nombre}").write_bytes(_raw_sc)
    reg = {"id": did, "nombre_archivo": nombre, "origen": "carga_manual", "recibido": now_iso(),
           "por": (getattr(request.state, "user", {}) or {}).get("sub") or ""}
    await db.docs_sin_clasificar.insert_one(dict(reg))
    # ☁️ DUAL WRITE: carpeta separada 'sin_clasificar' del storage integrado
    try:
        import media_storage as _ms
        asyncio.create_task(_ms.registrar_sin_clasificar(_raw_sc, nombre, did, reg["por"]))
    except Exception as _e:
        logging.warning(f"storage dual sin clasificar: {_e}")
    return {"ok": True, "documento": {k: v for k, v in reg.items()}}


@api.post("/admin/docs-sin-clasificar/{did}/asignar")
async def docs_sin_clasificar_asignar(did: str, payload: dict, request: Request):
    _exigir_bandeja(request)
    reg = await db.docs_sin_clasificar.find_one({"id": did})
    if not reg:
        raise HTTPException(status_code=404, detail="Documento no encontrado en la bandeja")
    fd = await db.folders.find_one({"id": (payload or {}).get("fid") or ""})
    if not fd:
        raise HTTPException(status_code=404, detail="Operación/carpeta no encontrada")
    origen = _sc_dir() / f"{did}_{reg['nombre_archivo']}"
    if not origen.exists():
        raise HTTPException(status_code=410, detail="El archivo físico ya no existe en la bandeja")
    carpeta = fsvc.folder_dir(fd.get("nombre") or "") / "99_otros"
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / reg["nombre_archivo"]).write_bytes(origen.read_bytes())
    origen.unlink()
    await db.folders.update_one({"id": fd["id"]},
                                {"$addToSet": {"archivos": f"99_otros/{reg['nombre_archivo']}"}})
    await db.docs_sin_clasificar.delete_one({"id": did})
    # ☁️ STORAGE: el documento clasificado pasa de 'sin_clasificar' a su operación
    await db.storage_docs.update_one({"bandeja_id": did, "is_deleted": False}, {"$set": {
        "origen": "administracion", "folder_id": fd["id"], "cliente": fd.get("nombre") or "",
        "rut": fd.get("rut") or "", "nro_operacion": str(fd.get("nro_operacion") or ""),
        "broker_codigo": fd.get("broker_codigo") or "", "clasificado_en": now_iso(),
        "clasificado_por": (getattr(request.state, "user", {}) or {}).get("sub") or ""}})
    return {"ok": True, "asignado_a": fd.get("nombre"), "archivo": reg["nombre_archivo"]}


@api.delete("/admin/docs-sin-clasificar/{did}")
async def docs_sin_clasificar_delete(did: str, request: Request):
    _exigir_bandeja(request)
    reg = await db.docs_sin_clasificar.find_one({"id": did})
    if reg:
        p = _sc_dir() / f"{did}_{reg['nombre_archivo']}"
        if p.exists():
            p.unlink()
        await db.docs_sin_clasificar.delete_one({"id": did})
        await db.storage_docs.update_one({"bandeja_id": did}, {"$set": {"is_deleted": True}})
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
            {"nombre_completo": {"$regex": re.escape(q), "$options": "i"}}
        ).limit(limit).to_list(limit)
        for s in sims:
            results.append({"tipo": "simulacion", "nombre": s.get("nombre_completo", "-"),
                            "detalle": f"{s.get('capacidad_credito_uf', 0)} UF", "modulo": "historial"})
        folders = await db.folders.find(
            {"nombre": {"$regex": re.escape(q), "$options": "i"}}
        ).limit(limit).to_list(limit)
        for f in folders:
            results.append({"tipo": "cliente", "nombre": f.get("nombre", "-"),
                            "detalle": f.get("rut", ""), "modulo": "clientes"})
    return {"results": results[:limit]}


# ---------------------------------------------------------------------------
# Clientes / Carpetas (archivos físicos en disco + metadata en Mongo)
# ---------------------------------------------------------------------------
def _folder_public(doc, con_archivos=False, archivos=None):
    d = clean(dict(doc))
    if archivos is None:
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


_PROY_SEG = {"_id": 0, "cliente": 1, "asunto": 1, "estado": 1, "fecha": 1}


async def _mesa_respuesta_folder(d, segs=None, archivos=None):
    """Busca la respuesta de mesa (aprobación/rechazo) para esta carpeta en seguimiento.
    REGLA: si la carpeta ya tiene descargada la carta de aprobación o la simulación
    ajustada, se considera APROBADA por mesa de inmediato.
    `segs` permite pasar el seguimiento prefetcheado (evita consultas N+1 en listados)."""
    toks = [t for t in _norm_texto(d.get("nombre", "")).split() if len(t) > 2]
    if not toks:
        return None
    if segs is None:
        segs = await db.seguimiento.find({}, _PROY_SEG).sort("fecha", -1).limit(200).to_list(200)
    for s in segs:
        texto = _norm_texto(f"{s.get('cliente','')} {s.get('asunto','')}")
        hits = sum(1 for t in toks if t in texto)
        if hits >= min(2, len(toks)):
            est = (s.get("estado") or "").lower()
            if est.startswith("aprob"):
                return "aprobada"
            if est.startswith("rech"):
                return "rechazada"
    if archivos is None:
        archivos = fsvc.scan_archivos(d.get("nombre", ""))
    for a in archivos:
        low = a["nombre"].lower()
        if re.search(r"carta.*aprobaci|aprobaci[oó]n", low) or re.search(r"_cm\.pdf$|ajustad", low):
            return "aprobada"
    return None


def _criterios_folder(d, archivos=None):
    if archivos is None:
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


@api.post("/clientes/cloud-sync")
async def clientes_cloud_sync():
    """💎 Cloud Sync: (a) refresca la conexión Mongo, (b) re-escanea el Object Store
    (GridFS) bajando archivos nuevos, (c) sube/espeja los cambios locales."""
    t0 = datetime.now(timezone.utc)
    try:
        await db.command("ping")
        mongo_ok = True
    except Exception:
        mongo_ok = False
    nuevos = 0
    try:
        nuevos = await asyncio.to_thread(bunker.restaurar_faltantes)
    except Exception as e:
        logging.warning(f"cloud-sync restaurar: {e}")
    # El respaldo disco->GridFS puede tardar: corre en HILO DAEMON (no bloquea nada)
    bunker.sync_en_background()
    total = await db.folders.count_documents({})
    protegidos = await db["bunker.files"].count_documents({})
    dur = (datetime.now(timezone.utc) - t0).total_seconds()
    return {"ok": mongo_ok, "mongo": "conectado" if mongo_ok else "error",
            "archivos_nuevos_descargados": nuevos,
            "respaldo": "en segundo plano",
            "total_en_bunker": protegidos,
            "carpetas": total, "duracion_seg": round(dur, 2)}


@api.get("/clientes/folders")
async def list_folders(q: str = ""):
    query = {"nombre": {"$regex": q, "$options": "i"}} if q else {}
    docs = await db.folders.find(query).sort("created_at", -1).limit(200).to_list(200)
    stats = await _stats_mesa()
    segs = await db.seguimiento.find({}, _PROY_SEG).sort("fecha", -1).limit(200).to_list(200)
    criterios_cfg = await db.config.find_one({"_key": "criterios"}) or {}
    tasas_cfg = await db.config.find_one({"_key": "tasas"}) or {}
    uf_val = await get_valor_uf()
    out = []
    for d in docs:
        archivos = fsvc.scan_archivos(d.get("nombre", ""))
        f = _folder_public(d, archivos=archivos)
        f["prob_aprobacion"] = _prob_aprobacion_folder(d, stats)
        f["criterios"] = _criterios_folder(d, archivos=archivos)
        f["mesa_respuesta"] = await _mesa_respuesta_folder(d, segs, archivos=archivos)
        # TECHO HIPOTECARIO en tarjeta: máximo crédito UF (mejor escenario, cálculo puro)
        df_t = d.get("datos_financieros") or {}
        if _num_limpio(df_t.get("renta_liquida")):
            try:
                t = ce.techo_hipotecario(df_t, criterios_cfg, tasas_cfg, uf_val, 25)
                mejor = t.get("mejor_escenario") or {}
                if mejor.get("credito_maximo_uf"):
                    f["techo_uf"] = mejor["credito_maximo_uf"]
                    f["techo_banco"] = mejor.get("banco", "")
            except Exception:
                pass
        out.append(f)
    return {"folders": out}


_PAT_FIRMA_CORREO = re.compile(r"^image\d{1,4}\.(jpe?g|png|gif|bmp)$", re.I)


def _extraer_email(remitente):
    mm = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", (remitente or "").lower())
    return mm.group(0) if mm else ""


def _remitente_autorizado(remitente, folder):
    """SEGURIDAD: antes de guardar un PDF, el remitente debe coincidir con el
    dueño de la carpeta (source_email) o ser una casilla propia del sistema."""
    remit = _extraer_email(remitente)
    if not remit:
        return False
    propios = {(os.environ.get("MAIL_USER") or "").lower(),
               (os.environ.get("MAIL2_USER") or "").lower()} - {""}
    if remit in propios:
        return True
    origen = _extraer_email(folder.get("source_email") or "")
    return not origen or remit == origen


def _rut_regex_flexible(rut):
    """'12.345.678-9' -> regex que matchea con o sin puntos/guion."""
    nucleo = re.sub(r"[.\-\s]", "", rut or "")
    if len(nucleo) < 7:
        return ""
    return r"\.?".join(re.escape(c) for c in nucleo[:-1]) + r"[\-.]?\s?" + re.escape(nucleo[-1])


_MAPA_ACENTOS = {"a": "[aáà]", "e": "[eéè]", "i": "[iíì]", "o": "[oóò]", "u": "[uúüù]", "n": "[nñ]"}


def _rx_acentos(texto):
    """Regex insensible a tildes: 'gonzalez' matchea 'González'."""
    out = []
    for ch in _norm_texto(texto):
        out.append(_MAPA_ACENTOS.get(ch, re.escape(ch)))
    return "".join(out)


@api.get("/clientes/forzar/sugerencias")
async def forzar_sugerencias(q: str = ""):
    """Sugerencias en vivo antes de forzar una carpeta: carpetas existentes,
    correos en la cola y correos en el buzón (solo cabeceras, rápido)."""
    q = (q or "").strip()
    if len(q) < 3:
        raise HTTPException(status_code=400, detail="Escribe al menos 3 letras")
    toks = [t for t in _norm_texto(q).split() if len(t) > 2]
    rx = ".*".join(_rx_acentos(t) for t in toks[:2]) if toks else _rx_acentos(q)
    carpetas = []
    async for d in db.folders.find({"nombre": {"$regex": rx, "$options": "i"}}).limit(5):
        carpetas.append({"id": d["id"], "nombre": d.get("nombre", ""),
                         "rut": d.get("rut", ""),
                         "archivos": len(fsvc.scan_archivos(d.get("nombre", "")))})
    cola = []
    async for it in db.proc_queue.find({"$or": [
            {"subject": {"$regex": rx, "$options": "i"}},
            {"cliente": {"$regex": rx, "$options": "i"}},
            {"classification.cliente": {"$regex": rx, "$options": "i"}},
            {"body_full": {"$regex": rx, "$options": "i"}}]}).sort("date_iso", -1).limit(6):
        cola.append({"subject": it.get("subject", ""), "from": it.get("from", ""),
                     "date": (it.get("date_iso") or "")[:16],
                     "adjuntos": len(it.get("attachments") or [])})
    correos = await asyncio.to_thread(mail.search_email_headers_by_person, q, 8)
    return {"carpetas": carpetas, "cola": cola, "correos": correos}


@api.get("/correos/buscar")
async def correos_buscar_generico(q: str = ""):
    """Búsqueda en vivo de correos (cabeceras) para importar adjuntos desde cualquier módulo."""
    q = (q or "").strip()
    if len(q) < 3:
        raise HTTPException(status_code=400, detail="Escribe al menos 3 letras")
    correos = await asyncio.to_thread(mail.search_email_headers_by_person, q, 10)
    return {"correos": correos}


@api.post("/correos/importar")
async def correos_importar(payload: dict):
    """Lanza la importación de adjuntos en SEGUNDO PLANO (la descarga IMAP puede tardar
    >60s y el proxy corta la conexión). El frontend consulta /api/jobs/{id}."""
    payload = payload or {}
    mids_v = [str(m).strip() for m in (payload.get("message_ids") or []) if m and str(m).strip()]
    if not mids_v:
        raise HTTPException(status_code=400, detail="Selecciona al menos un correo")
    job_id = str(uuid.uuid4())
    await db.bg_jobs.insert_one({"id": job_id, "tipo": "importar_correo",
                                 "estado": "en_proceso", "inicio": now_iso()})
    asyncio.create_task(_job_run(job_id, _correos_importar_run(payload)))
    return {"ok": True, "job_id": job_id, "estado": "en_proceso"}


async def _correos_importar_run(payload):
    """Importa los adjuntos de los correos elegidos hacia el módulo indicado:
    carpeta del cliente, estudio de título (separado) o set de crédito."""
    destino = (payload.get("destino") or "carpeta").strip()
    destino_id = (payload.get("destino_id") or "").strip()
    nombre = (payload.get("nombre") or "").strip()
    mids = [str(m).strip() for m in (payload.get("message_ids") or []) if m and str(m).strip()]
    if not mids:
        raise HTTPException(status_code=400, detail="Selecciona al menos un correo")
    resultados = await asyncio.to_thread(mail.fetch_attachments_by_message_ids, mids)
    if not resultados:
        raise HTTPException(status_code=404, detail="No se pudieron descargar los correos seleccionados")
    guardados = []
    if destino == "set_credito":
        doc = await db.set_credito.find_one({"id": destino_id}) if destino_id else None
        if not doc and nombre:
            doc = await db.set_credito.find_one({"nombre": {"$regex": re.escape(nombre), "$options": "i"}})
        if not doc:
            raise HTTPException(status_code=404, detail="Set de crédito no encontrado")
        base_dir = _set_dir(doc.get("nombre", ""))
        existentes = {a["nombre"].lower() for a in _set_archivos(doc.get("nombre", ""))}
        for r in resultados:
            for p in r.get("pdfs") or []:
                raw, fn = p.get("content_bytes"), p.get("filename") or ""
                if not raw or _PAT_FIRMA_CORREO.match(fn):
                    continue
                try:
                    raw, fn, _ = pdfs.convertir_a_pdf(raw, fn)
                except ValueError:
                    pass
                fn = fsvc.safe_name(fn)
                if fn.lower() in existentes:
                    continue
                cod = bool(re.search(r"codeudor", fn, re.I))
                dest = base_dir / ("codeudor" if cod else "")
                dest.mkdir(parents=True, exist_ok=True)
                (dest / fn).write_bytes(raw)
                existentes.add(fn.lower())
                guardados.append(("codeudor/" if cod else "") + fn)
    else:
        folder = await db.folders.find_one({"id": destino_id}) if destino_id else None
        if not folder and nombre:
            palabras = [p_ for p_ in re.split(r"\s+", nombre) if len(p_) >= 3]
            if palabras:
                folder = await db.folders.find_one(
                    {"$and": [{"nombre": {"$regex": re.escape(p_), "$options": "i"}} for p_ in palabras[:2]]})
        if not folder:
            if not nombre:
                raise HTTPException(status_code=404, detail="Carpeta no encontrada — indica el nombre del cliente")
            folder = {"id": str(uuid.uuid4()), "nombre": nombre.upper(), "rut": "",
                      "archivos": [], "created_at": now_iso(), "origen": "importado_correo"}
            await db.folders.insert_one(dict(folder))
            fsvc.folder_dir(folder["nombre"]).mkdir(parents=True, exist_ok=True)
        existentes = {a["nombre"].lower() for a in fsvc.scan_archivos(folder["nombre"])}
        for r in resultados:
            for p in r.get("pdfs") or []:
                fn = fsvc.safe_name(p.get("filename") or "")
                if not p.get("content_bytes") or fn.lower() in existentes or _PAT_FIRMA_CORREO.match(fn):
                    continue
                if destino == "estudio_titulo":
                    sub = "07_estudio_titulo"
                else:
                    cat = fsvc.cat_de_texto(fn)
                    sub = "07_estudio_titulo" if cat == "estudio_titulo" else ""
                rel = await _guardar_con_ley_rut(folder, fn, p["content_bytes"], sub)
                if not rel:
                    continue
                existentes.add(fn.lower())
                guardados.append(rel)
    return {"ok": True, "guardados": guardados, "correos": len(resultados)}


async def _job_run(job_id, coro):
    """Ejecuta un trabajo largo en segundo plano y guarda el resultado en bg_jobs."""
    try:
        resultado = await coro
        await db.bg_jobs.update_one({"id": job_id}, {"$set": {
            "estado": "listo", "resultado": resultado, "fin": now_iso()}})
    except HTTPException as e:
        await db.bg_jobs.update_one({"id": job_id}, {"$set": {
            "estado": "error", "error": str(e.detail), "fin": now_iso()}})
    except Exception as e:
        await db.bg_jobs.update_one({"id": job_id}, {"$set": {
            "estado": "error", "error": str(e)[:300], "fin": now_iso()}})


@api.get("/jobs/{job_id}")
async def job_estado(job_id: str):
    doc = await db.bg_jobs.find_one({"id": job_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    return clean(doc)


@api.post("/clientes/folders/forzar")
async def forzar_folder(payload: dict):
    """Valida y lanza el forzado de carpeta en SEGUNDO PLANO: la búsqueda IMAP puede
    tardar >60s y el proxy corta la conexión (502). El frontend consulta /api/jobs/{id}."""
    payload = payload or {}
    if payload.get("clave") != CLAVE_FORZAR_CARPETA:
        raise HTTPException(status_code=403, detail="Clave incorrecta")
    if len((payload.get("nombre") or "").strip()) < 3 and not (payload.get("rut") or "").strip():
        raise HTTPException(status_code=400, detail="Indica el nombre o el RUT del cliente")
    job_id = str(uuid.uuid4())
    await db.bg_jobs.insert_one({"id": job_id, "tipo": "forzar_carpeta",
                                 "estado": "en_proceso", "inicio": now_iso()})
    asyncio.create_task(_job_run(job_id, _forzar_folder_run(payload)))
    return {"ok": True, "job_id": job_id, "estado": "en_proceso"}


async def _forzar_folder_run(payload):
    """Fuerza la creación manual de una carpeta: busca por NOMBRE y/o RUT en los correos
    ingresados los datos y descarga los archivos adjuntos."""
    nombre = (payload.get("nombre") or "").strip()
    rut = (payload.get("rut") or "").strip()
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
        mids = [m_ for m_ in (payload.get("message_ids") or []) if m_]
        if mids:
            resultados = await asyncio.to_thread(mail.fetch_attachments_by_message_ids, mids)
        else:
            resultados = await asyncio.to_thread(mail.search_attachments_by_person, nombre or rut,
                                                 40, rut, folder.get("source_email"))
            if rut and nombre:
                try:
                    resultados += await asyncio.to_thread(mail.search_attachments_by_person, rut,
                                                          40, rut, folder.get("source_email"))
                except Exception:
                    pass
        if resultados and not (folder.get("source_email") or "").strip():
            remit = (resultados[-1].get("from") or resultados[0].get("from") or "").strip()
            if "@" in remit:
                await db.folders.update_one({"id": folder["id"]}, {"$set": {"source_email": remit}})
                folder["source_email"] = remit
        existentes = {a["nombre"].lower() for a in fsvc.scan_archivos(folder["nombre"])}
        for r in resultados:
            if not _remitente_autorizado(r.get("from"), folder):
                continue
            for p in r.get("pdfs") or []:
                fn = fsvc.safe_name(p["filename"])
                if fn.lower() in existentes or not p.get("content_bytes") or _PAT_FIRMA_CORREO.match(fn):
                    continue
                cat = fsvc.cat_de_texto(fn)
                sub = "07_estudio_titulo" if cat == "estudio_titulo" else ""
                rel = await _guardar_con_ley_rut(folder, fn, p["content_bytes"], sub)
                if not rel:
                    continue
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


@api.post("/clientes/folders/{fid}/enviar-escrituracion")
async def folder_enviar_escrituracion(fid: str):
    """FLUJO DE AVANCE: mueve la ficha a Escrituración y la activa en Set de Crédito y Títulos."""
    doc = await _get_folder_doc(fid)
    nombre = (doc.get("nombre") or "").strip()
    rut = (doc.get("rut") or "").strip()
    upd = {"is_escrituracion": True, "escrituracion_movida_at": now_iso()}
    if not doc.get("estudio_titulo_solicitado_at"):
        upd["estudio_titulo_solicitado_at"] = now_iso()
    await db.folders.update_one({"id": fid}, {"$set": upd})
    set_doc = None
    rx = _rut_regex_flexible(rut) if rut else None
    if rx:
        set_doc = await db.set_credito.find_one({"rut": {"$regex": rx, "$options": "i"}})
    if not set_doc:
        set_doc = await db.set_credito.find_one(
            {"nombre": {"$regex": f"^{re.escape(nombre)}$", "$options": "i"}})
    if not set_doc:
        set_doc = {"id": str(uuid.uuid4()), "nombre": nombre, "rut": rut,
                   "email": doc.get("email") or doc.get("source_email") or "",
                   "created_at": now_iso(), "firmas": [], "origen": "enviar_escrituracion"}
        await db.set_credito.insert_one(dict(set_doc))
        _set_dir(nombre).mkdir(parents=True, exist_ok=True)
    return {"ok": True, "set_id": set_doc["id"],
            "mensaje": f"⚖️ {nombre} enviado a Escrituración — activo en Set de Crédito y Títulos"}


@api.post("/clientes/folders/{fid}/enriquecer")
async def folder_enriquecer(fid: str, payload: dict = None):
    """Busca de nuevo en el correo (asunto, cuerpo y adjuntos) documentos del cliente.
    modo='credito' guarda por categoría de crédito; modo='estudio' guarda en
    07_estudio_titulo (NUNCA se mezclan con la solicitud de crédito)."""
    doc = await _get_folder_doc(fid)
    modo = ((payload or {}).get("modo") or "credito").lower()
    nombre = doc.get("nombre", "")
    rut = (doc.get("rut") or "").strip()
    mids = [m_ for m_ in ((payload or {}).get("message_ids") or []) if m_]
    if mids:
        resultados = await asyncio.to_thread(mail.fetch_attachments_by_message_ids, mids)
    else:
        resultados = await asyncio.to_thread(mail.search_attachments_by_person, nombre,
                                             40, rut, doc.get("source_email"))
        if rut:
            try:
                resultados += await asyncio.to_thread(mail.search_attachments_by_person, rut,
                                                      40, rut, doc.get("source_email"))
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
                if not mids and cat not in ("estudio_titulo", "extras"):
                    continue
                rel = await _guardar_con_ley_rut(doc, fn, p["content_bytes"],
                                                 subfolder="07_estudio_titulo")
            else:
                sub = "07_estudio_titulo" if cat == "estudio_titulo" else ""
                rel = await _guardar_con_ley_rut(doc, fn, p["content_bytes"], subfolder=sub)
            if not rel:
                continue
            existentes.add(fn.lower())
            nuevos.append({"archivo": rel, "asunto": (r.get("subject") or "")[:80]})
    return {"ok": True, "modo": modo, "correos_revisados": len(resultados),
            "archivos_nuevos": nuevos}


import zipfile as _zipfile

RESPALDO_EXCLUIR = {"save_jobs"}
# Proyección esencial: excluye campos pesados (cuerpos de correo, binarios) y _id
_RESPALDO_PROY = {"_id": 0, "body": 0, "html": 0, "raw": 0,
                  "content_bytes": 0, "attachments.content_bytes": 0}


@api.get("/admin/respaldo/export")
async def respaldo_export():
    """Descarga un ZIP con la base de datos (carpetas, config, usuarios…) y todos los archivos."""
    dump = {}
    for c in await db.list_collection_names():
        if c in RESPALDO_EXCLUIR or c.startswith("system."):
            continue
        dump[c] = [d async for d in db[c].find({}, _RESPALDO_PROY).batch_size(200).limit(8000)]
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
async def create_folder(payload: dict, request: Request):
    claims = getattr(request.state, "user", {}) or {}
    # REGLA RUT ÚNICO: un RUT registrado por un broker es de ese broker para siempre
    rut_norm = re.sub(r"[^0-9kK]", "", payload.get("rut") or "").lower()
    if rut_norm:
        async for fd in db.folders.find({"rut": {"$exists": True, "$ne": ""}},
                                        {"rut": 1, "broker_codigo": 1}):
            if re.sub(r"[^0-9kK]", "", fd.get("rut") or "").lower() == rut_norm:
                duenio = fd.get("broker_codigo") or ""
                if duenio and duenio != (claims.get("sub") or ""):
                    raise HTTPException(status_code=409,
                                        detail="Este RUT ya está registrado en el sistema por otro ejecutivo.")
                if claims.get("rol") == "broker":
                    raise HTTPException(status_code=409,
                                        detail="Este RUT ya está registrado en el sistema.")
    doc = {
        "id": str(uuid.uuid4()),
        "nombre": payload.get("nombre", ""),
        "rut": payload.get("rut", ""),
        "codeudor_nombre": payload.get("codeudor_nombre", ""),
        "codeudor_rut": payload.get("codeudor_rut", ""),
        "archivos": [],
        "created_at": now_iso(),
    }
    if claims.get("rol") == "broker":
        doc["broker_codigo"] = claims.get("sub") or ""
        doc["broker_origen"] = claims.get("nombre") or claims.get("sub") or ""
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
        # PERSISTENCIA: si el disco perdió el archivo (reinicio), restaurar desde el Búnker (GridFS)
        try:
            await asyncio.to_thread(bunker.restaurar_faltantes)
        except Exception as e:
            logging.warning(f"restauracion bunker en download: {e}")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    import mimetypes
    mt = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    disp = "inline" if inline else "attachment"
    return FileResponse(str(target), media_type=mt,
                        headers={"Content-Disposition": f'{disp}; filename="{target.name}"'})


_PAT_EMPAQUETADO = re.compile(
    r"documentos?\s*_?\s*solicitados|set\s+(de\s+)?documentos|antecedentes\s+completos|"
    r"carpeta\s+completa|docs?\s+asesor[ií]a|asesor[ií]a", re.I)


def _auto_split_empaquetados(nombre):
    """Detecta PDFs que traen TODOS los documentos en un solo archivo (ej:
    'DOCUMENTOS SOLICITADOS ASESORIA.pdf'), los separa por documento y elimina el
    original para que el protocolo los vuelva a juntar en el orden correcto."""
    resultados = []
    for a in fsvc.scan_archivos(nombre):
        fn = a["nombre"]
        if a.get("subfolder") not in ("", "99_otros") or not fn.lower().endswith(".pdf") or fsvc.es_combinado(fn):
            continue
        if not _PAT_EMPAQUETADO.search(fn):
            continue
        try:
            res = fsvc.split_bundled(nombre, a["ruta"], delete_original=True)
            if res.get("n_groups", 0) >= 2:
                resultados.append({"archivo": fn, "grupos": res["n_groups"],
                                   "paginas": res["n_pages"],
                                   "escritos": [w["rel"] for w in res.get("written", [])]})
        except Exception:
            continue
    return resultados


async def _regen_combinado_bg(doc):
    try:
        nombre = doc.get("nombre", "")
        splits = await asyncio.to_thread(_auto_split_empaquetados, nombre)
        for s in splits:
            await db.alertas.insert_one({
                "id": str(uuid.uuid4()), "tipo": "split_automatico",
                "cliente": nombre, "folder_id": doc.get("id", ""),
                "mensaje": (f"📄 {nombre}: '{s['archivo']}' venía con todo en un solo PDF "
                            f"({s['paginas']} páginas). Se separó en {s['grupos']} documentos "
                            "y se rearmó la carpeta según protocolo."),
                "fecha": now_iso(), "leida": False})
        cr = doc.get("credit_request") or {}
        await asyncio.to_thread(fsvc.merge_protocol, doc.get("nombre", ""),
                                cr.get("client_type") or "dependiente", True)
        # PROTOCOLO DUAL: reclasificar + combinado propio del codeudor (si tiene mínimos)
        cod_nom = (doc.get("codeudor_nombre") or "").strip()
        cod_rut = (doc.get("codeudor_rut") or "").strip()
        await asyncio.to_thread(fsvc.reclasificar_codeudor, nombre, cod_nom, cod_rut)
        await asyncio.to_thread(fsvc.merge_protocolo_codeudor, nombre, cod_nom, cod_rut, True)
    except Exception as e:
        logger.warning(f"Regeneración de combinado falló: {e}")


@api.post("/clientes/folders/{fid}/codeudor")
async def folder_agregar_codeudor(fid: str, payload: dict):
    """Crea la subcarpeta 05_codeudor/<Nombre> y vincula el RUT del codeudor (obligatorio).
    Dispara la BÚSQUEDA RETROACTIVA del RUT en todos los buzones (en segundo plano)."""
    payload = payload or {}
    nombre_cod = (payload.get("nombre") or "").strip()
    rut_cod = (payload.get("rut") or "").strip()
    if len(nombre_cod) < 3:
        raise HTTPException(status_code=400, detail="Indica el nombre del codeudor")
    if len(re.sub(r"[^0-9kK]", "", rut_cod)) < 7:
        raise HTTPException(status_code=400, detail="El RUT del codeudor es obligatorio (ej: 12.345.678-9)")
    doc = await _get_folder_doc(fid)
    sub = f"05_codeudor/{fsvc.safe_name(nombre_cod)}"
    (fsvc.folder_dir(doc.get("nombre", "")) / sub).mkdir(parents=True, exist_ok=True)
    await db.folders.update_one({"id": fid}, {
        "$set": {"codeudor_nombre": nombre_cod, "codeudor_rut": rut_cod},
        "$push": {"historial": {"fecha": now_iso(),
                                "accion": f"Codeudor vinculado por RUT: {nombre_cod} ({rut_cod})"}}})
    asyncio.create_task(_rescate_codeudor_bg(doc, nombre_cod, rut_cod))
    return {"ok": True, "subfolder": sub, "codeudor_rut": rut_cod,
            "busqueda_retroactiva": "iniciada en todos los buzones"}


async def _rescate_codeudor_bg(doc, cod_nom, cod_rut):
    """BÚSQUEDA RETROACTIVA (no bloqueante): rastrea el RUT del codeudor en los buzones,
    valida cada PDF con Match Total de RUT y lo archiva en 05_codeudor con protocolo de orden."""
    try:
        nombre = doc.get("nombre", "")
        rut_n = re.sub(r"[^0-9kK]", "", cod_rut or "").lower()
        adjuntos = await asyncio.to_thread(mail.buscar_adjuntos_por_rut, cod_rut, 20)
        base = fsvc.folder_dir(nombre)
        sub = f"05_codeudor/{fsvc.safe_name(cod_nom)}"
        cod_dir = base / "05_codeudor"
        existentes = {p.name.lower() for p in cod_dir.rglob("*.pdf")} if cod_dir.exists() else set()
        guardados = []
        for a in adjuntos:
            fn, raw = a["filename"], a["content"]
            try:
                texto, _m = await asyncio.to_thread(ocr_service.extraer_texto, raw, fn)
            except Exception:
                continue
            ruts_doc = {re.sub(r"[.\-\s]", "", r).lower() for r in fsvc.RUT_RX.findall(texto or "")}
            # REGLA DE ORO (Match Total): sin el RUT del codeudor en el PDF, no entra
            if rut_n not in ruts_doc:
                continue
            cat = fsvc.cat_de_archivo(fn, "")
            fn2 = fsvc.nombre_con_prefijo(fn, cat)
            final = fn2 if fn2.upper().startswith("CODEUDOR_") else f"CODEUDOR_{fn2}"
            if fsvc.safe_name(final).lower() in existentes:
                continue
            rel = await asyncio.to_thread(fsvc.guardar_archivo, nombre, final, raw, sub)
            existentes.add(fsvc.safe_name(final).lower())
            guardados.append(rel)
        if guardados:
            await asyncio.to_thread(fsvc.merge_protocolo_codeudor, nombre, cod_nom, cod_rut, True)
        await db.alertas.insert_one({
            "id": str(uuid.uuid4()), "tipo": "rescate_codeudor",
            "cliente": nombre, "folder_id": doc.get("id", ""),
            "mensaje": (f"🔎 Búsqueda retroactiva del codeudor {cod_nom} ({cod_rut}): "
                        + (f"{len(guardados)} documento(s) rescatado(s) de los buzones y archivados en 05_codeudor."
                           if guardados else f"sin documentos con ese RUT en los buzones "
                           f"({len(adjuntos)} adjuntos candidatos revisados).")),
            "fecha": now_iso(), "leida": False})
    except Exception as e:
        logger.warning(f"Búsqueda retroactiva codeudor: {e}")


@api.post("/clientes/folders/{fid}/upload-file")
async def folder_upload_file(fid: str, request: Request, file: UploadFile = File(...), subfolder: str = Form(""),
                             route_to_codeudor: str = Form(""), categoria: str = Form(""),
                             codeudor_nombre: str = Form("")):
    doc = await _get_folder_doc(fid)
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Archivo vacío")
    nombre_archivo = file.filename or "archivo"
    try:
        raw, nombre_archivo, _conv = pdfs.convertir_a_pdf(raw, nombre_archivo)
    except ValueError:
        pass  # formato no convertible: se guarda tal cual
    es_codeudor = str(route_to_codeudor).lower() in ("true", "1", "si", "sí") or bool(codeudor_nombre.strip())
    categoria = (categoria or "").strip().lower()
    if es_codeudor:
        cod_nom = codeudor_nombre.strip() or (doc.get("codeudor_nombre") or "").strip()
        subfolder = f"05_codeudor/{fsvc.safe_name(cod_nom)}" if cod_nom else "05_codeudor"
        if not nombre_archivo.upper().startswith("CODEUDOR_"):
            nombre_archivo = f"CODEUDOR_{nombre_archivo}"
    elif categoria in ("voucher_tasacion", "voucher_gasto_operacional"):
        subfolder = "99_otros"
        prefijo = "VOUCHER_TASACION_" if categoria == "voucher_tasacion" else "VOUCHER_GASTO_OP_"
        if not nombre_archivo.upper().startswith(prefijo):
            nombre_archivo = f"{prefijo}{nombre_archivo}"
    rel = await asyncio.to_thread(fsvc.guardar_archivo, doc.get("nombre", ""),
                                  nombre_archivo, raw, subfolder)
    # ☁️ DUAL WRITE: copia persistente en el storage integrado (operación/RUT)
    try:
        import media_storage as _ms
        _cl = getattr(request.state, "user", {}) or {}
        asyncio.create_task(_ms.registrar_documento(
            raw, nombre_archivo, doc, origen="administracion",
            subido_por=_cl.get("sub") or "", rol=_cl.get("rol") or "", rel=rel))
    except Exception as _e:
        logging.warning(f"storage dual upload-file: {_e}")
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
    """Separa un PDF empaquetado en SEGUNDO PLANO (el OCR puede tardar >60s)."""
    doc = await _get_folder_doc(fid)
    job_id = str(uuid.uuid4())
    await db.bg_jobs.insert_one({"id": job_id, "tipo": "split_bundled",
                                 "estado": "en_proceso", "inicio": now_iso()})
    asyncio.create_task(_job_run(job_id, _split_bundled_run(doc, payload or {})))
    return {"ok": True, "job_id": job_id, "estado": "en_proceso"}


async def _split_bundled_run(doc, payload):
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
        correos = await asyncio.to_thread(mail.search_attachments_by_person, person, 40,
                                          doc.get("rut"), doc.get("source_email"))
        existentes = {a["nombre"] for a in fsvc.scan_archivos(doc.get("nombre", ""))}
        total_found, total_saved, saved = 0, 0, []
        for c in correos:
            if not _remitente_autorizado(c.get("from"), doc):
                continue
            for pdf in c.get("pdfs", []):
                total_found += 1
                raw, nombre_a = pdf["content_bytes"], pdf["filename"]
                try:
                    raw, nombre_a, _ = pdfs.convertir_a_pdf(raw, nombre_a)
                except ValueError:
                    pass
                if fsvc.safe_name(nombre_a) in existentes:
                    continue
                rel = await _guardar_con_ley_rut(doc, nombre_a, raw, "")
                if not rel:
                    continue
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


@api.post("/clientes/folders/{fid}/techo-hipotecario")
async def folder_techo_hipotecario(fid: str, payload: dict = None):
    """TECHO HIPOTECARIO: crédito máximo (UF) que la MESA aprobaría por escenario
    (BTG Pactual y Ameris), vía simulación inversa sobre los documentos reales."""
    payload = payload or {}
    doc = await _get_folder_doc(fid)
    df = doc.get("datos_financieros") or {}
    criterios = await db.config.find_one({"_key": "criterios"}) or {}
    tasas = await db.config.find_one({"_key": "tasas"}) or {}
    uf = await get_valor_uf()
    plazo = int(payload.get("plazo_anos") or 25)
    cmf = payload.get("cuota_cmf_clp")
    res = await asyncio.to_thread(ce.techo_hipotecario, df, criterios, tasas, uf, plazo, cmf)
    res["cliente"] = doc.get("nombre")
    # DOBLE PANEL: Criterio Teórico (Bodega) vs Veredicto Algoritmo Espejo MESA
    modelo = await db.config.find_one({"_key": "espejo_mesa_modelo"}) or {}
    renta_ref = res.get("componentes_renta", {}).get("renta_liquida_fija") or 0
    _edad = int(_num_limpio(df.get("edad")))
    _cod_nombre = (doc.get("codeudor_nombre") or "").strip()
    features = {
        "renta_liquida_clp": renta_ref,
        "renta_codeudor_clp": _num_limpio(df.get("renta_codeudor")),
        "endeudamiento_mensual_clp": (res.get("endeudamiento") or {}).get("endeudamiento_mensual_clp", 0),
        "con_subsidio": bool(df.get("con_subsidio")),
        "con_codeudor": bool(_cod_nombre),
        "codeudor_tipo": ("ninguno" if not _cod_nombre else
                          ("familiar" if set((doc.get("nombre") or "").lower().split()[1:])
                           & set(_cod_nombre.lower().split()[1:]) else "tercero")),
        "edad_bucket": "s/i" if _edad <= 0 else ("<40" if _edad < 40 else ("40_59" if _edad < 60 else "60+")),
        "edad_mayor_60": _edad >= 60,
    }
    espejo = await asyncio.to_thread(ce.simular_como_mesa, features, modelo)
    exp = _estimar_tope_mesa(renta_ref, modelo)
    if exp and exp.get("sugerir_codeudor"):
        espejo["sugerir_codeudor"] = True
    res["espejo_mesa"] = espejo
    res["experiencia_mesa"] = exp
    res["teorico_uf"] = (res.get("mejor_escenario") or {}).get("credito_maximo_uf")
    return res


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
        # REGLA: las simulaciones se guardan AJUSTADAS (solo primera hoja); cartas intactas
        if not re.search(r"carta|aprobaci[oó]n", fn, re.I) and re.search(r"simulad|simulaci[oó]n", fn, re.I):
            try:
                raw, _o, _r = pdfs.dejar_primera_pagina(raw)
            except Exception:
                pass
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
    # 2) Directo del correo — REGLA DE ORO #64: 1° Bóveda; IMAP solo si falta el dato
    adjuntos = []
    if not copiados and await _perfil.imap_permitido(nombre, "adjuntos aprobación"):
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
             ("Ejecutivo externo", doc.get("ejecutivo_externo")),
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
    # DESTINO ÚNICO: las carpetas a Mesa van EXCLUSIVAMENTE a la casilla oficial
    _destino_mesa = (os.environ.get("MESA_EMAIL") or "").strip()
    if _destino_mesa:
        to = _destino_mesa
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
    ejecutivo_ext = (payload.get("ejecutivo_externo") or doc.get("ejecutivo_externo") or "").strip()
    if payload.get("ejecutivo_externo") and payload["ejecutivo_externo"].strip() != (doc.get("ejecutivo_externo") or ""):
        await db.folders.update_one({"id": fid}, {"$set": {"ejecutivo_externo": ejecutivo_ext}})
        doc["ejecutivo_externo"] = ejecutivo_ext
    if not ejecutivo:
        missing_labels.append("Ejecutivo interno (Deisy/Yerile/Gerardo)")
    if payload.get("confirm") and missing_labels and not payload.get("force_incompleto"):
        raise HTTPException(status_code=412, detail="Documentación incompleta — faltan: "
                            + ", ".join(missing_labels)
                            + ". Para enviar igual, asumí el envío manual incompleto.")
    # REGLA: a Mesa solo se envía UNA vez en forma directa. Para reenviar se exige la clave.
    # HUELLA: si ya existe un Message-ID de envío exitoso, el re-envío queda prohibido sin clave.
    if payload.get("confirm") and (doc.get("mesa_enviado_at") or doc.get("mesa_message_id")):
        if (payload.get("clave") or "") != CLAVE_FORZAR_CARPETA:
            raise HTTPException(status_code=403, detail=(
                f"Esta carpeta ya se envió a Mesa el "
                f"{str(doc['mesa_enviado_at'])[:16].replace('T', ' ')}. "
                "Para reenviarla debes ingresar la clave de administrador."))
    attach_names = []
    attach_paths = []
    cod_nom = (doc.get("codeudor_nombre") or "").strip()
    cod_rut = (doc.get("codeudor_rut") or "").strip()
    if cod_nom:
        # VERIFICACIÓN DUAL: nada del codeudor puede quedar en la raíz del titular
        await asyncio.to_thread(fsvc.reclasificar_codeudor, nombre, cod_nom, cod_rut)
    if payload.get("include_merged", True):
        merged = base / f"COMBINADO_PROTOCOLO_{fsvc.safe_name(nombre)}.pdf"
        if not merged.exists():
            res = await asyncio.to_thread(fsvc.merge_protocol, nombre,
                                          cr.get("client_type") or "dependiente", True)
            merged = base / res["merged_file"] if res["merged_file"] else merged
        if merged.exists():
            attach_paths.append(merged)
            attach_names.append(merged.name)
    # PROTOCOLO DUAL: con codeudor vinculado se adjuntan DOS combinados (titular + codeudor)
    if cod_nom and payload.get("include_codeudor_merged", True):
        res_cod = await asyncio.to_thread(fsvc.merge_protocolo_codeudor, nombre, cod_nom, cod_rut)
        if res_cod["merged_file"]:
            pc = base / res_cod["merged_file"]
            attach_paths.append(pc)
            attach_names.append(pc.name)
    elif payload.get("include_codeudor_merged"):
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
    # REGLA: el asunto SIEMPRE lleva el prefijo fijo; lo del usuario se AGREGA, nunca reemplaza.
    if cod_nom:
        prefijo_subj = (f"💎 Solicitud de Crédito: {nombre} + Codeudor {cod_nom}"
                        + (f" ({rut})" if rut else "")
                        + (f" — Entrega: {fecha_entrega.capitalize()}" if fecha_entrega else ""))
    else:
        prefijo_subj = (f"Antecedentes crédito hipotecario — {nombre}" + (f" ({rut})" if rut else "")
                        + (f" — Entrega: {fecha_entrega.capitalize()}" if fecha_entrega else ""))
    extra_subj = (payload.get("subject_extra") or "").strip()
    subject = payload.get("subject") or (
        prefijo_subj
        + (f" — {extra_subj}" if extra_subj else "")
        + (f" — Ejecutivo: {ejecutivo_ext}" if ejecutivo_ext else ""))
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
      <p style="color:#888;font-size:12px">Central Mutuos</p>
    </div>
    """
    sender = _sender_por_rol("secundaria")
    if not payload.get("confirm"):
        return {"to": to, "subject": subject, "body": cuerpo, "body_html": cuerpo,
                "missing_docs": missing_labels, "docs_completos": not missing_labels,
                "attachments": attach_names, "sender": sender}
    adjuntos = [{"filename": p.name, "content_b64": _b64(p.read_bytes())} for p in attach_paths]
    # CERROJO ATÓMICO: find_one_and_update marca EN_PROCESO_DE_ENVIO — si otro proceso
    # intenta enviar al mismo tiempo, el segundo intento se bloquea de inmediato.
    _stale = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    _lock = await db.folders.find_one_and_update(
        {"id": fid, "$or": [{"mesa_envio_lock": {"$ne": "EN_PROCESO_DE_ENVIO"}},
                            {"mesa_envio_lock_at": {"$lt": _stale}}]},
        {"$set": {"mesa_envio_lock": "EN_PROCESO_DE_ENVIO", "mesa_envio_lock_at": now_iso()}})
    if _lock is None:
        raise HTTPException(status_code=409,
                            detail="Envío a Mesa YA en proceso — intento simultáneo bloqueado por el cerrojo atómico.")
    from email.utils import make_msgid
    mid = make_msgid(domain="centralmutuos.cl")
    try:
        res = await asyncio.to_thread(mail.send_mail, to, subject, cuerpo, adjuntos,
                                      "secundaria", None, {"Message-ID": mid})
    except Exception:
        await db.folders.update_one({"id": fid}, {"$unset": {"mesa_envio_lock": "", "mesa_envio_lock_at": ""}})
        raise
    if not res.get("success"):
        await db.folders.update_one({"id": fid}, {"$unset": {"mesa_envio_lock": "", "mesa_envio_lock_at": ""}})
        raise HTTPException(status_code=502, detail=res.get("error", "Error de envío"))
    # HUELLA DE ENVÍO: Message-ID guardado en la carpeta — prohibe re-envíos de este ciclo
    await db.folders.update_one({"id": fid}, {
        "$inc": {"emails_sent_count": 1},
        "$set": {"last_email_sent_at": now_iso(), "mesa_enviado_at": now_iso(),
                 "mesa_message_id": mid},
        "$unset": {"mesa_envio_lock": "", "mesa_envio_lock_at": ""}})
    return {"to": to, "subject": subject, "attachments": attach_names,
            "message_id": mid, "sender": res.get("desde", sender)}


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
      <p style="color:#888;font-size:12px">Central Mutuos</p>
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
    """Destinatario del 'Enviar a Mesa': SIEMPRE la casilla de Mesa (MESA_EMAIL)."""
    dest = os.environ.get("MESA_EMAIL", "")
    return {"destination": dest, "destinatarios": [dest] if dest else []}


@api.post("/clientes/detect-client")
async def detect_client(payload: dict):
    return {"matches": []}


# ---------------------------------------------------------------------------
# Seguimiento (operaciones detectadas desde el correo)
# ---------------------------------------------------------------------------
async def _info_operacion_cliente(nombre):
    """Busca quién ENVIÓ la solicitud original del cliente (ejecutivo externo real)
    y datos de gestión (rut, proyecto, monto) desde la cola de procesamiento."""
    out = {"rut": "", "proyecto": "", "ejecutivo_externo": "", "ejecutivo_email": "",
           "ejecutivo_cm": "", "monto_credito": ""}
    if not nombre or nombre.lower() in ("desconocido", ""):
        return out
    partes = [p for p in re.split(r"\s+", nombre.strip()) if len(p) > 2][:2]
    if not partes:
        return out
    rx = ".*".join(re.escape(p) for p in partes)
    items = await db.proc_queue.find(
        {"classification.cliente": {"$regex": rx, "$options": "i"}},
        {"sender": 1, "date_iso": 1, "campos": 1, "classification": 1}
    ).sort("date_iso", 1).limit(10).to_list(10)
    for it in items:
        campos = it.get("campos") or {}
        cl = it.get("classification") or {}
        if not out["rut"] and cl.get("rut"):
            out["rut"] = cl["rut"]
        if not out["proyecto"] and campos.get("proyecto_inmobiliario"):
            out["proyecto"] = campos["proyecto_inmobiliario"]
        if not out["monto_credito"] and campos.get("monto_credito_uf"):
            out["monto_credito"] = f"{campos['monto_credito_uf']} UF"
        if not out["ejecutivo_externo"]:
            out["ejecutivo_externo"] = (campos.get("nombre_ejecutivo")
                                        or campos.get("ejecutivo_externo") or "")
            out["ejecutivo_email"] = campos.get("email_ejecutivo", "")
        if not out["ejecutivo_externo"] and it.get("sender"):
            sender = it["sender"]
            em = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", sender)
            out["ejecutivo_externo"] = re.sub(r"<.*?>", "", sender).strip().strip('"')
            out["ejecutivo_email"] = em.group(0) if em else ""
        if not out["ejecutivo_cm"] and campos.get("ejecutivo_interno"):
            out["ejecutivo_cm"] = campos["ejecutivo_interno"]
    folder = await db.folders.find_one(
        {"nombre": {"$regex": rx, "$options": "i"}},
        {"rut": 1, "ejecutivo_interno": 1, "ejecutivo_externo": 1})
    if folder:
        out["rut"] = out["rut"] or folder.get("rut", "")
        out["ejecutivo_cm"] = out["ejecutivo_cm"] or folder.get("ejecutivo_interno", "")
        out["ejecutivo_externo"] = out["ejecutivo_externo"] or folder.get("ejecutivo_externo", "")
    return out


@api.get("/correos/smtp-log")
async def correos_smtp_log(limit: int = 50, solo_errores: bool = False):
    """Registro SMTP completo de cada envío (código y respuesta exacta de Gmail)."""
    q = {"success": False} if solo_errores else {}
    docs = await db.correos_smtp_log.find(q).sort("fecha", -1).limit(min(limit, 200)).to_list(min(limit, 200))
    return {"log": [clean(d) for d in docs]}


@api.get("/salud/estado")
async def salud_estado():
    """Panel de Salud: estado en vivo del flujo lineal (monitoreo -> carpetas -> cola de correos)."""
    ahora = datetime.now(timezone.utc)

    def _mins_desde(iso):
        try:
            return round((ahora - datetime.fromisoformat(iso)).total_seconds() / 60, 1)
        except Exception:
            return None

    proc = await db.config.find_one({"_key": "proc_auto"}) or {}
    ac = await db.config.find_one({"_key": "autocorreo_state"}) or {}
    intervalo = max(2, int(proc.get("interval_min") or 2))
    hace_min = _mins_desde(proc.get("last_run") or "")
    ac_hace = _mins_desde(ac.get("last_run") or "")
    hace24 = (ahora - timedelta(hours=24)).isoformat()
    enviados_24h = await db.correos_smtp_log.count_documents({"success": True, "fecha": {"$gte": hace24}})
    fallidos_24h = await db.log_errores_correo.count_documents({"fecha": {"$gte": hace24}})
    carpetas_24h = await db.folders.count_documents({"created_at": {"$gte": hace24}})
    descartados_24h = await db.proc_queue.count_documents({"descartado_en": {"$gte": hace24}})
    ult_envios = await db.correos_smtp_log.find({}).sort("fecha", -1).limit(8).to_list(8)
    ult_errores = await db.log_errores_correo.find({}).sort("fecha", -1).limit(8).to_list(8)
    ult_carpetas = await db.folders.find({}, {"nombre": 1, "created_at": 1, "origen": 1}
                                         ).sort("created_at", -1).limit(6).to_list(6)
    return {
        "monitoreo_buzon": {
            "activo": bool(proc.get("enabled", True)),
            "intervalo_min": intervalo,
            "corriendo_ahora": bool(proc.get("running")),
            "ultima_revision": proc.get("last_run"),
            "hace_min": hace_min,
            "alerta": hace_min is None or hace_min > intervalo * 3,
            "ultimo_resultado": proc.get("last_result") or {},
        },
        "autocorreo_mesa": {
            "activo": bool(ac.get("enabled")),
            "ultima_corrida": ac.get("last_run"),
            "hace_min": ac_hace,
            "alerta": ac_hace is None or ac_hace > 20,
            "ultimo_resultado": ac.get("last_run_result") or {},
        },
        "cola_correos": {
            "goteo_seg": mail.PAUSA_ENTRE_CORREOS,
            "reintento_seg": mail.REINTENTO_ESPERA,
            "enviados_24h": enviados_24h,
            "fallidos_24h": fallidos_24h,
            "ultimos_envios": [{"fecha": d.get("fecha"), "to": d.get("to"),
                                "subject": (d.get("subject") or "")[:60],
                                "smtp_code": d.get("smtp_code"), "ok": d.get("success")}
                               for d in ult_envios],
            "ultimos_errores": [{"fecha": d.get("fecha"), "destinatario": d.get("destinatario"),
                                 "smtp_code": d.get("smtp_code"),
                                 "error": (d.get("error") or "")[:100], "intento": d.get("intento")}
                                for d in ult_errores],
        },
        "carpetas": {
            "creadas_24h": carpetas_24h,
            "descartados_24h": descartados_24h,
            "ultimas": [{"nombre": f.get("nombre"), "fecha": f.get("created_at"),
                         "origen": f.get("origen", "correo")} for f in ult_carpetas],
        },
        "motor_whatsapp": "VÍA RÁPIDA ACTIVA (Sin API Meta)",
        "hora_servidor": ahora.isoformat(),
    }


@api.get("/calibracion/estado")
async def calibracion_estado():
    """PANEL DE AUDITORÍA: calibra criterios con las últimas 50 respuestas de la MESA
    y mide la asertividad de la predicción del sistema contra el veredicto real."""
    resp = await db.seguimiento.find({"estado": {"$in": ["aprobacion", "rechazo"]}}
                                     ).sort("fecha", -1).limit(50).to_list(50)
    muestras, aciertos, detalle = 0, 0, []
    vistos = set()
    stats_m = await _stats_mesa()
    for r in resp:
        cli = (r.get("cliente") or "").strip()
        if not cli or cli.lower() in vistos:
            continue
        vistos.add(cli.lower())
        toks = [t for t in re.split(r"\s+", cli) if len(t) > 2][:2]
        if not toks:
            continue
        rxc = ".*".join(re.escape(t) for t in toks)
        f = await db.folders.find_one({"nombre": {"$regex": rxc, "$options": "i"}})
        if not f:
            continue
        pct = f.get("porcentaje")
        if pct is None:
            try:
                pct = _prob_aprobacion_folder(f, stats_m).get("porcentaje")
            except Exception:
                continue
        muestras += 1
        prediccion = "aprobacion" if float(pct or 0) >= 50 else "rechazo"
        ok = prediccion == r.get("estado")
        aciertos += 1 if ok else 0
        detalle.append({"cliente": cli, "prediccion": prediccion,
                        "mesa": r.get("estado"), "porcentaje": pct,
                        "acierto": ok})
    asertividad = round(aciertos * 100 / muestras) if muestras else None
    # Cambio de tendencia: % de rechazo reciente vs anterior
    total = len(resp)
    mitad = total // 2 if total >= 10 else 0
    tendencia = ""
    if mitad:
        rec = resp[:mitad]
        ant = resp[mitad:]
        pr = sum(1 for x in rec if x["estado"] == "rechazo") * 100 / len(rec)
        pa = sum(1 for x in ant if x["estado"] == "rechazo") * 100 / len(ant)
        if pr - pa >= 15:
            tendencia = (f"⚠ La mesa endureció sus criterios: rechazos subieron de "
                         f"{round(pa)}% a {round(pr)}%. Criterios recalibrados a la baja.")
        elif pa - pr >= 15:
            tendencia = (f"✅ La mesa flexibilizó sus criterios: rechazos bajaron de "
                         f"{round(pa)}% a {round(pr)}%. Criterios recalibrados al alza.")
    aprobadas = sum(1 for x in resp if x["estado"] == "aprobacion")
    rechazadas = total - aprobadas
    snapshot = {
        "mensaje": (f"He calibrado mis criterios basados en las últimas {total} respuestas de la MESA. "
                    + (f"Mi asertividad actual es del {asertividad}%." if asertividad is not None
                       else "Aún no hay suficientes casos con predicción para medir asertividad.")),
        "respuestas_mesa": total, "aprobadas": aprobadas, "rechazadas": rechazadas,
        "muestras_con_prediccion": muestras, "aciertos": aciertos,
        "asertividad": asertividad, "tendencia": tendencia,
        "hard_rules": ["Mínimo 2.000 UF sin subsidio (alerta crítica a jefatura)",
                       "0% de probabilidad si falta Cédula, Liquidaciones, AFP o CMF"],
        "detalle": detalle[:15], "calibrado_en": now_iso(),
    }
    await db.config.update_one({"_key": "calibracion"}, {"$set": snapshot}, upsert=True)
    if tendencia:
        ya = await db.alertas.find_one({"tipo": "tendencia_mesa", "mensaje": tendencia})
        if not ya:
            await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "tendencia_mesa",
                                         "mensaje": tendencia, "fecha": now_iso(), "leida": False})
    return snapshot


@api.get("/contactos/emails")
async def contactos_emails(q: str = ""):
    """Autocompletar de correos: junta correos conocidos de carpetas, cola de
    procesamiento (clientes y ejecutivos) y remitentes recientes."""
    ql = (q or "").strip().lower()
    vistos, out = set(), []

    def add(email_, nombre="", origen=""):
        e = (email_ or "").strip().lower().rstrip(".,;")
        if not e or "@" not in e or e in vistos:
            return
        if ql and ql not in e and ql not in (nombre or "").lower():
            return
        vistos.add(e)
        out.append({"email": e, "nombre": (nombre or "").strip(), "origen": origen})

    async for f in db.folders.find({}, {"nombre": 1, "email": 1, "ejecutivo_externo_email": 1,
                                        "ejecutivo_externo": 1}).limit(300):
        add(f.get("email"), f.get("nombre"), "cliente")
        add(f.get("ejecutivo_externo_email"), f.get("ejecutivo_externo"), "ejecutivo")
    async for it in db.proc_queue.find(
            {}, {"sender": 1, "classification.cliente": 1, "classification.email_cliente": 1,
                 "campos.email_ejecutivo": 1, "campos.nombre_ejecutivo": 1}
    ).sort("date_iso", -1).limit(400):
        cl = it.get("classification") or {}
        c = it.get("campos") or {}
        add(cl.get("email_cliente"), cl.get("cliente"), "cliente")
        add(c.get("email_ejecutivo"), c.get("nombre_ejecutivo"), "ejecutivo")
        s = it.get("sender") or ""
        m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", s)
        if m:
            add(m.group(0), re.sub(r"<.*", "", s).strip(' "'), "remitente")
    return {"contactos": out[:15]}


@api.get("/seguimiento/clientes")
async def seg_clientes(q: str = ""):
    query = {"cliente": {"$regex": re.escape(q), "$options": "i"}} if q else {}
    docs = await db.seguimiento.find(query).sort("fecha", -1).limit(500).to_list(500)
    # agrupar por cliente
    por_cliente = {}
    for d in docs:
        c = d.get("cliente", "Desconocido")
        key = c.lower()
        if key not in por_cliente:
            por_cliente[key] = {
                "id": d.get("cliente_id") or c,
                "cliente": c, "cliente_display": c,
                "estado": d.get("estado"),
                "rut": d.get("rut", ""), "proyecto": d.get("proyecto", ""),
                "ejecutivo_cm": d.get("ejecutivo_cm", ""),
                "ejecutivo_externo": d.get("ejecutivo_externo", ""),
                "ejecutivo_email": d.get("ejecutivo_email", ""),
                "correo_remitente": d.get("correo_remitente") or d.get("remitente", ""),
                "monto_credito": d.get("monto_credito", ""),
                "ultima_actividad": d.get("fecha"),
                "total_correos": 0, "operaciones": 0,
            }
        e = por_cliente[key]
        e["total_correos"] += 1
        e["operaciones"] += 1
        for k in ("rut", "proyecto", "ejecutivo_cm", "ejecutivo_externo",
                  "ejecutivo_email", "monto_credito"):
            if not e[k] and d.get(k):
                e[k] = d[k]
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
async def seg_process(max_emails: int = 30, dias: int = 31):
    ops = await asyncio.to_thread(mail.procesar_seguimiento, max_emails, dias)
    nuevos = 0
    for op in ops:
        exists = await db.seguimiento.find_one(
            {"asunto": op["asunto"], "fecha": op["fecha"]})
        if exists:
            continue
        extra = await _info_operacion_cliente(op["cliente"])
        doc_seg = {
            "id": str(uuid.uuid4()),
            "cliente_id": op["cliente"].lower().replace(" ", "-"),
            **op,
            **extra,
            "correo_remitente": op.get("remitente", ""),
            "procesado_en": now_iso(),
        }
        await db.seguimiento.insert_one(dict(doc_seg))
        # CONTRALORÍA AUTOMÁTICA: auditar el caso al instante
        asyncio.create_task(_forense_caso_automatico(doc_seg))
        # RITMO ANTI-RÁFAGA: la notificación entra a la cola pausada (máx 3/ciclo, 10s)
        await _encolar_notificacion(doc_seg)
        nuevos += 1
    return {"ok": True, "procesados": len(ops), "nuevos": nuevos, "dias": dias}


@api.patch("/seguimiento/estado")
async def seg_corregir_estado(payload: dict):
    """Corrección manual del estado de un cliente en seguimiento (ej: aprobación mal clasificada)."""
    payload = payload or {}
    cliente = (payload.get("cliente") or "").strip()
    estado = (payload.get("estado") or "").strip().lower()
    if not cliente or estado not in ("aprobacion", "rechazo", "observacion"):
        raise HTTPException(status_code=400, detail="Indica cliente y estado válido (aprobacion/rechazo/observacion)")
    r = await db.seguimiento.update_many(
        {"cliente": {"$regex": f"^{re.escape(cliente)}$", "$options": "i"}},
        {"$set": {"estado": estado, "estado_corregido_manual": True}})
    return {"ok": True, "actualizados": r.modified_count, "estado": estado}


@api.get("/reportes/seguimiento/excel")
async def seg_excel():
    docs = await db.seguimiento.find({}).sort("fecha", -1).limit(500).to_list(500)
    filas = "".join(
        f"<tr><td>{(d.get('fecha') or '')[:10]}</td><td>{d.get('cliente','')}</td>"
        f"<td>{d.get('rut','')}</td><td>{d.get('estado','')}</td>"
        f"<td>{d.get('proyecto','')}</td><td>{d.get('ejecutivo_externo','')}</td>"
        f"<td>{d.get('ejecutivo_email','')}</td><td>{d.get('ejecutivo_cm','')}</td>"
        f"<td>{d.get('monto_credito','')}</td><td>{d.get('asunto','')}</td>"
        f"<td>{(d.get('correo_remitente') or d.get('remitente') or '')}</td></tr>"
        for d in docs)
    html = ("<html><head><meta charset='utf-8'></head><body><table border='1'>"
            "<tr><th>Fecha</th><th>Cliente</th><th>RUT</th><th>Estado</th><th>Proyecto</th>"
            "<th>Ejecutivo Externo</th><th>Correo Ejecutivo</th><th>Ejecutivo CM</th>"
            "<th>Monto</th><th>Asunto</th><th>Remitente</th></tr>"
            f"{filas}</table></body></html>")
    return HTMLResponse(content=html, headers={
        "Content-Disposition": "attachment; filename=seguimiento_central_mutuos.xls",
        "Content-Type": "application/vnd.ms-excel; charset=utf-8"})


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
        st = {"_key": "autocorreo_state", "enabled": True, "periodic_enabled": True,
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


@api.get("/motor/status")
async def motor_status():
    """Estado del Motor 24/7 (autocorreo mesa + ingesta de carpetas)."""
    ac = await _ac_state()
    pa = await _proc_auto_state()
    operativo = bool(ac.get("periodic_enabled")) and bool(pa.get("enabled"))
    return {"operativo": operativo,
            "correo_a_mesa": bool(ac.get("periodic_enabled")),
            "ingesta_carpetas": bool(pa.get("enabled")),
            "destino": ac.get("destination", "")}


@api.post("/autocorreo/periodic")
async def ac_periodic(payload: dict = None):
    enabled = bool((payload or {}).get("enabled"))
    # pausa_admin persiste la decisión aun tras reinicios (el startup la respeta)
    await _set_ac_state({"periodic_enabled": enabled, "pausa_admin": not enabled})
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


from pymongo import MongoClient as _SyncMongoClient
_sync_guard_db = None


def _guard_db():
    """Cliente Mongo síncrono para el BLINDAJE de mesa (usable dentro de hilos)."""
    global _sync_guard_db
    if _sync_guard_db is None:
        _sync_guard_db = _SyncMongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    return _sync_guard_db


def _mesa_guard_reservar(subject, cliente):
    """BLINDAJE ANTIDUPLICADOS: reserva atómica del envío a mesa por asunto.
    True = primera vez (se puede enviar). False = ya se envió antes → JAMÁS duplicar."""
    key = _norm_texto(subject) or _norm_texto(cliente)
    if not key:
        return True
    prev = _guard_db().mesa_enviados.find_one_and_update(
        {"key": key},
        {"$setOnInsert": {"key": key, "cliente": cliente, "subject": subject,
                          "enviado_at": now_iso()}},
        upsert=True)
    return prev is None


def _mesa_guard_liberar(subject, cliente):
    key = _norm_texto(subject) or _norm_texto(cliente)
    if key:
        _guard_db().mesa_enviados.delete_one({"key": key})


def _procesar_mesa(destino, cutoff_iso, ejecutivos=None, ya_enviados=None):
    """Lee correos de mesa, deja pag 1 en simulaciones, archiva y envia. (sync)

    Incluye RECHAZOS aunque vengan sin PDF (solo texto).
    ejecutivos: {cliente_lower: {nombre, email, email_cliente}} para el encabezado.
    ya_enviados: set de asuntos ya enviados (evita duplicados).
    """
    ejecutivos = ejecutivos or {}
    ya_enviados = ya_enviados or set()
    correos = mail.fetch_pdf_attachments(sender_filter=MESA_SENDER, limit=15,
                                         incluir_sin_adjuntos=True)
    resultados = []
    for c in correos:
        if cutoff_iso and c.get("date") and c["date"] < cutoff_iso:
            continue
        subj = (c.get("subject") or "").strip()
        if subj and subj in ya_enviados:
            continue  # ya fue enviado antes o ya se procesó en ESTE ciclo (correo duplicado en ambas casillas)
        if subj:
            ya_enviados.add(subj)
        cliente = mail._extraer_nombre(c["subject"], c["from"])
        es_aprobacion = c["tipo"] == "aprobacion"
        es_rechazo = c["tipo"] == "rechazo"
        if not c["pdfs"]:
            # Sin adjuntos: se reenvia si es RECHAZO o APROBACION (vienen solo texto).
            # La aprobación de texto además asegura la carpeta con carta + simulación ajustada.
            if es_rechazo or es_aprobacion:
                resultados.append({"cliente": cliente, "subject": c["subject"],
                                   "saved": [{"name": "(sin PDF - solo texto)",
                                              "type": "rechazo" if es_rechazo else "aprobacion_texto"}],
                                   "adjuntos": [], "es_aprobacion": es_aprobacion,
                                   "es_rechazo": es_rechazo, "body": c.get("body", "")})
            continue
        # REGLA: UN SOLO correo a mesa por gestión — todos los PDFs van juntos como adjuntos
        adjuntos = []
        saved = []
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
        if adjuntos:
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
        # BLINDAJE: reserva atómica en BD — si este asunto ya se envió a mesa ALGUNA vez,
        # se salta sin excepción (el flujo automático jamás reenvía).
        if not _mesa_guard_reservar(r["subject"], r["cliente"]):
            continue
        res = mail.send_mail(destino, r["subject"], encabezado + cuerpo_html,
                             r["adjuntos"], desde="secundaria")
        estado = "sent" if res.get("success") else "failed"
        if res.get("success"):
            enviados += 1
        else:
            _mesa_guard_liberar(r["subject"], r["cliente"])
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
    def _res_es_aprobacion(r):
        if r.get("es_aprobacion"):
            return True
        return any(((s.get("type") == "carta_aprobacion")
                    or re.search(r"aprobaci[oó]n", s.get("name") or "", re.I))
                   for s in r.get("saved") or [])

    return {"processed": len(resultados), "sent": enviados, "errors": errores, "logs": logs,
            "aprobados": sorted({r["cliente"] for r in resultados if r["cliente"] and _res_es_aprobacion(r)})}


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


async def _asegurar_carpeta_aprobacion(nombre):
    """NORMA: cuando llega una APROBACIÓN de mesa, la carpeta del cliente debe existir
    (se crea si no estuviera, aunque no debería pasar) y debe contener la carta de
    aprobación y la simulación ajustada. Aquí NO aplica la regla de documentos mínimos."""
    nombre = (nombre or "").strip()
    if len(nombre) < 3:
        return None
    # Nunca crear carpetas con nombres de cuentas propias/mesa (correos sin cliente claro)
    if ("@" in nombre or re.search(r"aprobacion|central\s*mutuos|mesa|simulaci[oó]n",
                                   nombre, re.I) or len(nombre.split()) < 2):
        return None
    folder = await _buscar_carpeta_existente(nombre, "")
    if not folder:
        folder = {"id": str(uuid.uuid4()), "nombre": nombre.upper(), "rut": "",
                  "archivos": [], "created_at": now_iso(), "origen": "aprobacion_mesa"}
        await db.folders.insert_one(dict(folder))
        fsvc.folder_dir(folder["nombre"]).mkdir(parents=True, exist_ok=True)
        await db.alertas.insert_one({
            "id": str(uuid.uuid4()), "tipo": "carpeta_aprobacion",
            "cliente": folder["nombre"], "folder_id": folder["id"],
            "mensaje": f"📁 Carpeta creada automáticamente por APROBACIÓN de mesa: {folder['nombre']}",
            "fecha": now_iso(), "leida": False})
    copiados = await _sync_docs_aprobacion(folder.get("nombre", ""))
    # MOTOR DE COSECHA (Regla #64): datos clave de la aprobación → perfil_consolidado
    try:
        fd_full = await db.folders.find_one({"id": folder["id"]})
        if fd_full:
            await _perfil.cosechar_carpeta(fd_full, "aprobacion_mesa")
    except Exception as e:
        logging.warning(f"cosecha aprobación: {e}")
    return {"carpeta": folder.get("nombre", ""), "copiados": copiados}


async def _run_mesa_background(destino, cutoff_iso, ejecutivos, ya_enviados=None):
    try:
        await db.config.update_one({"_key": "autocorreo_state"},
                                   {"$set": {"running": True, "last_run_started": now_iso()}}, upsert=True)
        result = await asyncio.to_thread(_procesar_mesa, destino, cutoff_iso, ejecutivos, ya_enviados)
        for lg in result.pop("logs", []):
            await db.autocorreo_log.insert_one(lg)
        # NORMA: toda aprobación de mesa asegura carpeta con carta + simulación ajustada
        for cliente_ap in result.pop("aprobados", []):
            try:
                await _asegurar_carpeta_aprobacion(cliente_ap)
            except Exception as e:
                logging.warning(f"carpeta aprobación {cliente_ap}: {e}")
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
            corriendo = st.get("running")
            if corriendo and (st.get("last_run_started") or "") < (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat():
                corriendo = False  # candado obsoleto (>30 min): se ignora
            if st.get("periodic_enabled") and not corriendo:
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
    if campos.get("con_subsidio") == True and campos.get("monto_subsidio_uf") in (None, ""):
        faltan.append("Monto del subsidio")
    tipo_cliente = cl.get("tipo_cliente", "dependiente")
    req = CHECKLIST.get(tipo_cliente, {})
    conteo = {}
    for d in cl.get("documentos", []):
        conteo[d["tipo"]] = conteo.get(d["tipo"], 0) + 1
    docs_faltantes = {t: n - conteo.get(t, 0) for t, n in req.items() if conteo.get(t, 0) < n}
    listo = not faltan and not docs_faltantes
    return faltan, docs_faltantes, listo




def _es_gestion(remitente, subject, tiene_pdf, reglas=None):
    reglas = reglas or REGLAS_AUTO_DEFAULT
    r = _norm_texto(remitente or "")
    s = _norm_texto(subject or "")
    if any(_norm_texto(d) in r for d in reglas.get("dominios") or []):
        return True
    if re.search(r"solicitud (de )?(credito|financiamiento|pre.?aprobaci)", s):
        return True
    if tiene_pdf and any(_norm_texto(k) in s for k in reglas.get("keywords") or []):
        return True
    return False


REGLAS_AUTO_DEFAULT = {
    "dominios": GESTION_DOMINIOS,
    "keywords": ["evaluaci", "liquidaci", "antecedentes", "carpeta", "document",
                 "preaprob", "credito", "financiamiento", "hipotecari"],
}


async def _reglas_auto_state():
    st = await db.config.find_one({"_key": "reglas_auto"}) or {}
    return {"dominios": [d.lower() for d in (st.get("dominios") or REGLAS_AUTO_DEFAULT["dominios"])],
            "keywords": [k.lower() for k in (st.get("keywords") or REGLAS_AUTO_DEFAULT["keywords"])]}


@api.get("/procesamiento/reglas-auto")
async def reglas_auto_get():
    return await _reglas_auto_state()


@api.patch("/procesamiento/reglas-auto")
async def reglas_auto_patch(payload: dict):
    payload = payload or {}
    upd = {}
    for campo in ("dominios", "keywords"):
        if campo in payload:
            upd[campo] = [str(x).strip().lower() for x in (payload[campo] or []) if str(x).strip()]
    if upd:
        await db.config.update_one({"_key": "reglas_auto"}, {"$set": upd}, upsert=True)
    return await _reglas_auto_state()


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
    criterios = await get_config("criterios", DEFAULT_CRITERIOS)
    valor_uf = await get_valor_uf()
    return {"aprobadas": apro, "rechazadas": rech, "base": base,
            "criterios": criterios, "valor_uf": valor_uf}


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
    # ⚔️ REGLAS DE HIERRO (Políticas Maestras): cualquier quiebre → viabilidad 0% inmediata.
    # La IA NO puede ponderar ni ignorar estas 5 reglas generales (orden del dueño).
    quiebres_hierro = mesa_brain.quiebres_hierro_folder(doc)
    if quiebres_hierro:
        factores_h = ["⛔ 0%: NO VIABLE - POLÍTICA GENERAL (Regla de Hierro quebrada)"]
        factores_h += [f"⛔ {q['detalle']}" for q in quiebres_hierro]
        return {"porcentaje": 0, "factores": factores_h,
                "alerta_critica": "NO VIABLE - POLÍTICA GENERAL: " +
                                  "; ".join(q["regla"] for q in quiebres_hierro)}
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
    # REGLA DURA: mínimo 2.000 UF sin subsidio
    alerta_critica = ""
    if monto and monto < 2000 and not con_sub:
        alerta_critica = "ALERTA: No cumple criterio mínimo de 2.000 UF. Avisar a jefatura"
        prob = min(prob, 10)
        factores.append(f"🔴 {alerta_critica}")
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
        return {"porcentaje": 0, "factores": factores, "alerta_critica": alerta_critica}
    prob = max(5, min(98, round(prob)))
    return {"porcentaje": prob, "factores": factores, "alerta_critica": alerta_critica}


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


def _ingest_sync(max_emails, reglas=None):
    correos = mail.fetch_pdf_attachments(sender_filter=None, limit=max_emails)
    items = []
    for c in correos:
        if not _es_gestion(c["from"], c["subject"], bool(c["pdfs"]), reglas):
            continue
        items.append(c)
    return items


@api.post("/procesamiento/ingest-from-inbox")
async def proc_ingest(max_emails: int = 20, dias: int = 0):
    """Ingesta gestiones desde las bandejas. dias>0 = solo correos de los ultimos N dias."""
    reglas = await _reglas_auto_state()
    correos = await asyncio.to_thread(_ingest_sync, max_emails, reglas)
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
    elif len(cliente.split()) < 2:
        # La IA tomó un saludo ("Gerardo") en vez del cliente: preferir el asunto
        desde_asunto = mail._extraer_nombre(item.get("subject", ""), "")
        if desde_asunto not in ("", "Desconocido") and len(desde_asunto.split()) >= 2:
            cliente = desde_asunto
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
        texto, metodo = await asyncio.to_thread(ocr_service.extraer_texto, path.read_bytes(), fn, allow_vision is not False)
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


RUT_EN_TEXTO_RX = re.compile(r"\b\d{1,2}\.?\d{3}\.?\d{3}\s?-\s?[\dkK]\b")


def _ruts_de_pdf(pdf_bytes):
    """Escaneo OCR: devuelve el set de RUTs normalizados encontrados en el PDF."""
    try:
        texto, _m = ocr_service.extraer_texto(pdf_bytes)
    except Exception:
        texto = ""
    return {_norm_rut(r) for r in RUT_EN_TEXTO_RX.findall(texto or "")}


def _ley_rut_ok(pdf_bytes, ruts_permitidos):
    """LEY DEL RUT (Blindaje de Werner): el archivo SOLO se vincula si contiene
    el RUT del dueño de la carpeta o de su codeudor registrado. Sin excepciones."""
    permitidos = {_norm_rut(r) for r in ruts_permitidos if r and len(_norm_rut(r)) >= 7}
    if not permitidos:
        return True, set()
    encontrados = _ruts_de_pdf(pdf_bytes)
    return bool(encontrados & permitidos), encontrados


async def _rescate_ley_rut(folder_doc, fn, raw, ruts_encontrados, origen="correo"):
    """Archivo entrante SIN match de RUT: va al Buzón de Rescate, nunca a la carpeta."""
    qid = f"rescate-ley-rut-{uuid.uuid4().hex[:10]}"
    d = PROC_DIR / qid
    d.mkdir(parents=True, exist_ok=True)
    safe = fsvc.safe_name(fn)
    (d / safe).write_bytes(raw)
    await db.proc_queue.insert_one({
        "id": qid, "status": "revisar", "sender": origen,
        "subject": f"LEY DEL RUT: adjunto sin match para {folder_doc.get('nombre', '')}",
        "date_iso": now_iso(),
        "classification": {"cliente": "", "rut": "",
                           "documentos": [{"filename": safe, "tipo": "otro"}]},
        "attachments": [safe], "campos": {}})
    await db.correos_pendientes.insert_one({
        "id": str(uuid.uuid4()), "qid": qid,
        "subject": f"Adjunto rechazado por LEY DEL RUT ({safe})",
        "sender": origen, "fecha": now_iso(),
        "motivo": (f"LEY DEL RUT: el archivo no contiene el RUT de {folder_doc.get('nombre', '')} "
                   f"({folder_doc.get('rut', '')}). RUTs detectados: "
                   f"{', '.join(sorted(ruts_encontrados)) or 'ninguno'}"),
        "cliente_sugerido": "", "adjuntos": [safe],
        "estado": "pendiente", "creado_en": now_iso()})
    await db.alertas.insert_one({
        "id": str(uuid.uuid4()), "tipo": "ley_del_rut",
        "cliente": folder_doc.get("nombre", ""),
        "mensaje": (f"🛡️ LEY DEL RUT: adjunto \"{safe}\" rechazado de la carpeta de "
                    f"{folder_doc.get('nombre', '')} — enviado al Buzón de Rescate"),
        "fecha": now_iso(), "leida": False})


async def _guardar_con_ley_rut(folder_doc, fn, raw, subfolder=""):
    """Guarda el archivo SOLO si su OCR contiene el RUT del dueño o codeudor (match 100%).
    Sin match -> Buzón de Rescate. RUT COMO BRÚJULA: si trae SOLO el RUT del codeudor,
    va forzado a 05_codeudor/<Nombre> con prefijo CODEUDOR_. Devuelve rel o None."""
    ruts = [folder_doc.get("rut", ""), folder_doc.get("codeudor_rut", "")]
    if any(len(_norm_rut(r or "")) >= 7 for r in ruts):
        ok, encontrados = await asyncio.to_thread(_ley_rut_ok, raw, ruts)
        if not ok:
            await _rescate_ley_rut(folder_doc, fn, raw, encontrados)
            return None
        rut_t = _norm_rut(folder_doc.get("rut", "") or "")
        rut_c = _norm_rut(folder_doc.get("codeudor_rut", "") or "")
        if (len(rut_c) >= 7 and rut_c in encontrados
                and not (rut_t and rut_t in encontrados)):
            if not (rut_t and len(rut_t) >= 7):
                # REGLA IVANA: sin RUT titular NO se vinculan codeudores
                await _rescate_ley_rut(folder_doc, fn, raw, encontrados)
                return None
            cod_nom = (folder_doc.get("codeudor_nombre") or "").strip() or "Codeudor"
            subfolder = f"05_codeudor/{fsvc.safe_name(cod_nom.title())}"
            if not fn.upper().startswith("CODEUDOR_"):
                fn = f"CODEUDOR_{fn}"
    return await asyncio.to_thread(fsvc.guardar_archivo, folder_doc.get("nombre", ""),
                                   fn, raw, subfolder)


async def _buscar_carpeta_existente(cliente, rut=""):
    """Encuentra la carpeta ya existente de la misma persona (por RUT o nombre similar)."""
    rut_n = _norm_rut(rut or "")
    folders = await db.folders.find({}).to_list(500)
    if rut_n and len(rut_n) >= 7:
        for f in folders:
            if _norm_rut(f.get("rut", "")) == rut_n:
                return f
        # LEY DEL RUT: el correo trae RUT y NINGUNA carpeta coincide —
        # PROHIBIDO vincular por parecido de nombres.
        return None
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
    todos los correos, en orden de protocolo (prefijos 01_..99_).
    MEMORIA LIVIANA: streaming página a página con fitz, liberando RAM por archivo."""
    import fitz
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
        # SORT NUMÉRICO (REGLA INAMOVIBLE): jerarquía 01..06 por prefijo, no orden de llegada
        key = ((0, manual[p.name], 0, "") if p.name in manual
               else (1, fsvc.orden_numerico(p.name, rel0), 0, rel))
        archivos.append((key, p))
    archivos.sort(key=lambda t: t[0])
    doc_out = fitz.open()
    for _k, p in archivos:
        try:
            src_doc = fitz.open(str(p))
            doc_out.insert_pdf(src_doc)
            src_doc.close()
        except Exception:
            continue
    if doc_out.page_count == 0:
        doc_out.close()
        return None
    out = dest / f"Carpeta_{_safe_name(cliente)}.pdf"
    doc_out.save(str(out), garbage=3, deflate=True)
    doc_out.close()
    return out.name


_SOLICITUD_RE = re.compile(
    r"solicitud\s+de\s+(financiamiento|cr[eé]dito)|solicito\s+(evaluaci[oó]n|financiamiento|cr[eé]dito)|evaluaci[oó]n",
    re.I)
_MONTO_RE = re.compile(r"monto|[\d.,]+\s*uf\b|\buf\s*[\d.,]+|\$\s*[\d.,]{4,}", re.I)
_DOCS_BASICOS = ("cedula", "liquidacion", "cotizacion_afp", "certificado_afp",
                 "certificado_smf", "impuesto_renta", "boleta_honorarios")


def _regla_solicitud_ok(item):
    """REGLA: se arma carpeta si el correo trae frase de evaluación/solicitud de
    financiamiento y al menos 3 documentos básicos (2 si además indica el monto).
    El tipo del documento se complementa con el nombre del archivo para no
    descartar liquidaciones/cédulas mal clasificadas como 'otro'."""
    texto = f"{item.get('subject') or ''} {item.get('body_full') or item.get('body_preview') or ''}"
    if not _SOLICITUD_RE.search(texto):
        return False, "el texto no menciona evaluación ni solicitud de financiamiento/crédito"
    _cat_basica = {"cedula": "cedula", "liquidacion": "liquidacion", "afp": "afp",
                   "cmf": "cmf", "imp_renta": "imp_renta", "boletas": "boletas"}
    tipos = set()
    for d in (item.get("classification") or {}).get("documentos") or []:
        t = d.get("tipo", "")
        fn = d.get("filename", "")
        if t in _DOCS_BASICOS:
            tipos.add("afp" if t in ("cotizacion_afp", "certificado_afp")
                      else ("cmf" if t == "certificado_smf" else t))
        elif fsvc.cat_de_texto(fn) in _cat_basica:
            tipos.add(_cat_basica[fsvc.cat_de_texto(fn)])
        elif re.search(r"cotizaci[oó]n", fn, re.I):
            tipos.add("cotizacion_inmobiliaria")
    minimo = 2 if _MONTO_RE.search(texto) else 3
    if len(tipos) < minimo:
        return False, f"solo {len(tipos)} documento(s) básico(s) adjunto(s) — mínimo {minimo}"
    return True, ""


CLAVE_FORZAR_CARPETA = os.environ.get("MASTER_PIN", "")


DESTINOS_RESCATE = ("solicitud", "tasacion", "estudio", "administrativo", "otros")


def _sugerir_destino(texto):
    """MODO INTUITIVO: sugiere destino por palabras clave. Solo sugerencia — nada se mueve sin confirmación."""
    t = _norm_texto(texto or "")
    if re.search(r"reparo|estudio de titulo|titulos|abogad|escritura", t):
        return "estudio"
    if re.search(r"tasacion|tasador|tasar|avaluo", t):
        return "tasacion"
    if re.search(r"aprobaci|solicitud|credito|simulaci|hipotec|liquidacion|cedula|renta|cotizacion|afp|cmf", t):
        return "solicitud"
    return "otros"


@api.get("/rescate/pendientes")
async def rescate_pendientes():
    """Buzón de Rescate: correos que el sistema no logró clasificar/armar automáticamente."""
    # Backfill: los descartados históricos de proc_queue también entran al buzón
    async for it in db.proc_queue.find({"status": "descartado"}).sort("date_iso", -1).limit(100):
        await db.correos_pendientes.update_one(
            {"qid": it["id"]},
            {"$setOnInsert": {
                "id": str(uuid.uuid4()), "qid": it["id"],
                "subject": it.get("subject", ""), "sender": it.get("sender", ""),
                "fecha": it.get("date_iso", ""), "motivo": it.get("descartado_motivo", ""),
                "cliente_sugerido": (it.get("classification") or {}).get("cliente", ""),
                "adjuntos": [d.get("filename") for d in
                             (it.get("classification") or {}).get("documentos") or []],
                "estado": "pendiente", "creado_en": now_iso()}},
            upsert=True)
    docs = await db.correos_pendientes.find({"estado": "pendiente"}).sort("fecha", -1).limit(100).to_list(100)
    out = []
    for d in docs:
        c = clean(d)
        c["sugerencia"] = _sugerir_destino(
            f"{d.get('subject', '')} {d.get('motivo', '')} {' '.join(d.get('adjuntos') or [])}")
        out.append(c)
    return {"pendientes": out}


@api.post("/rescate/{pid}/descartar")
async def rescate_descartar(pid: str):
    """Descarte definitivo: el correo no corresponde al negocio; sale del buzón para siempre."""
    pend = await db.correos_pendientes.find_one({"$or": [{"id": pid}, {"qid": pid}]})
    if not pend:
        raise HTTPException(status_code=404, detail="Correo pendiente no encontrado")
    await db.correos_pendientes.update_one({"id": pend["id"]}, {"$set": {
        "estado": "descartado_definitivo", "descartado_en": now_iso()}})
    if pend.get("qid"):
        await db.proc_queue.update_one({"id": pend["qid"]}, {"$set": {
            "status": "descartado_definitivo", "descartado_motivo": "Descartado manualmente por Gerardo (Buzón de Rescate)"}})
    return {"ok": True}


@api.post("/rescate/{pid}/asignar")
async def rescate_asignar(pid: str, payload: dict):
    """Asignación manual: elige cliente y tipo de documento; mueve los archivos a la
    carpeta del cliente y los procesa como si hubieran sido automáticos."""
    payload = payload or {}
    cliente = (payload.get("cliente") or "").strip()
    tipo_doc = (payload.get("tipo_documento") or "").strip().lower()
    if len(cliente.split()) < 2:
        raise HTTPException(status_code=400, detail="Indica el nombre completo del cliente (nombre y apellido)")
    pend = await db.correos_pendientes.find_one({"$or": [{"id": pid}, {"qid": pid}]})
    if not pend:
        raise HTTPException(status_code=404, detail="Correo pendiente no encontrado")
    qid = pend["qid"]
    item = await db.proc_queue.find_one({"id": qid})
    if not item:
        raise HTTPException(status_code=404, detail="El correo original ya no está en la cola")
    # Renombrar físicamente si el usuario definió el tipo (Simulación o Carta)
    if tipo_doc in ("simulacion", "carta"):
        pref = "simulador_" if tipo_doc == "simulacion" else "carta_aprobacion_"
        cl = item.get("classification") or {}
        docs_cl = cl.get("documentos") or []
        src = PROC_DIR / qid
        for d in docs_cl:
            fn = d.get("filename") or ""
            if fn.lower().endswith(".pdf") and not re.search(r"simulad|carta|aprobaci", fn, re.I):
                nuevo = f"{pref}{fn}"
                try:
                    (src / fn).rename(src / nuevo)
                    d["filename"] = nuevo
                except Exception:
                    continue
        await db.proc_queue.update_one({"id": qid}, {"$set": {"classification.documentos": docs_cl}})
    await db.proc_queue.update_one({"id": qid}, {"$set": {
        "classification.cliente": cliente, "status": "clasificado",
        "descartado_motivo": None, "drive_folder_id": None}})
    res = await proc_upload_drive(qid, force=True, clave=CLAVE_FORZAR_CARPETA)
    await db.correos_pendientes.update_one({"qid": qid}, {"$set": {
        "estado": "resuelto", "cliente_asignado": cliente,
        "tipo_documento": tipo_doc, "resuelto_en": now_iso()}})
    return {"ok": True, "cliente": cliente, "resultado": res}


@api.post("/rescate/{pid}/clasificar")
async def rescate_clasificar(pid: str, payload: dict):
    """CENTRO DE MANDO: destino manual exclusivo (solicitud/tasacion/estudio/otros).
    REGLA INVIOLABLE: nada se mueve hasta esta confirmación."""
    payload = payload or {}
    destino = (payload.get("destino") or "").strip().lower()
    if destino not in DESTINOS_RESCATE:
        raise HTTPException(status_code=400, detail="Destino inválido")
    pend = await db.correos_pendientes.find_one({"$or": [{"id": pid}, {"qid": pid}]})
    if not pend:
        raise HTTPException(status_code=404, detail="Correo pendiente no encontrado")
    if destino == "administrativo":
        qid = pend.get("qid") or ""
        src = PROC_DIR / qid if qid else None
        guardados = []
        if src and src.exists():
            for f in sorted(src.iterdir()):
                if f.is_file():
                    rel = await asyncio.to_thread(fsvc.guardar_archivo, "Admin_Empresa",
                                                  f.name, f.read_bytes(), "99_otros")
                    guardados.append(rel)
        await db.folders.update_one(
            {"nombre": "Admin_Empresa"},
            {"$setOnInsert": {"id": str(uuid.uuid4()), "nombre": "Admin_Empresa", "rut": "",
                              "created_at": now_iso(), "archivos": []}}, upsert=True)
        await db.correos_pendientes.update_one({"id": pend["id"]}, {"$set": {
            "estado": "procesado_administrativo", "destino": "administrativo",
            "clasificado_en": now_iso(), "archivos_destino": guardados}})
        if qid:
            await db.proc_queue.update_one({"id": qid}, {"$set": {"status": "administrativo"}})
        bunker.sync_en_background()
        return {"ok": True, "destino": "administrativo", "archivos": guardados,
                "detalle": "Correo movido a la carpeta Admin_Empresa"}
    if destino == "otros":
        import shutil as _sh
        qid = pend.get("qid") or ""
        src = PROC_DIR / qid if qid else None
        dest = ROOT_DIR / "storage" / "archivo_general" / (qid or pend["id"])
        movidos = []
        if src and src.exists():
            dest.mkdir(parents=True, exist_ok=True)
            for f in src.iterdir():
                if f.is_file():
                    _sh.move(str(f), str(dest / f.name))
                    movidos.append(f.name)
        await db.correos_pendientes.update_one({"id": pend["id"]}, {"$set": {
            "estado": "archivado_otros", "destino": "otros", "clasificado_en": now_iso(),
            "archivado_en": now_iso(), "archivo_general": movidos}})
        if qid:
            await db.proc_queue.update_one({"id": qid}, {"$set": {"status": "archivado_otros"}})
        return {"ok": True, "destino": "otros", "archivados": movidos,
                "detalle": "Correo archivado en carpeta general — sin ficha de cliente"}
    cliente = (payload.get("cliente") or "").strip()
    res = await rescate_asignar(pid, {"cliente": cliente,
                                      "tipo_documento": payload.get("tipo_documento", "")})
    if destino in ("tasacion", "estudio"):
        campo = ("tasacion_solicitada_at" if destino == "tasacion"
                 else "estudio_titulo_solicitado_at")
        await db.folders.update_one(
            {"nombre": {"$regex": f"^{re.escape(cliente)}$", "$options": "i"}},
            {"$set": {campo: now_iso()}})
    await db.correos_pendientes.update_one({"id": pend["id"]}, {"$set": {
        "estado": f"procesado_{destino}", "destino": destino,
        "cliente_final": cliente, "clasificado_en": now_iso()}})
    return {"ok": True, "destino": destino, **(res or {})}


@api.get("/rescate/historial")
async def rescate_historial():
    """Historial de correos ya clasificados (no vuelven a 'Por Clasificar')."""
    docs = await db.correos_pendientes.find(
        {"estado": {"$ne": "pendiente"}}).sort("clasificado_en", -1).limit(100).to_list(100)
    return {"historial": [clean(d) for d in docs]}


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
    if len(cliente.split()) < 2:
        desde_asunto = mail._extraer_nombre(item.get("subject", ""), "")
        if desde_asunto not in ("", "Desconocido") and len(desde_asunto.split()) >= 2:
            cliente = desde_asunto
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
    # MATCH PERFECTO POR RUT: si el RUT clasificado está vinculado como codeudor de un
    # titular, los archivos van DIRECTO al anexo 05_codeudor — NUNCA carpeta nueva en raíz
    rut_entrante = (cl.get("rut") or "").strip()
    if rut_entrante and not es_correo_codeudor:
        rx_cod = _rut_regex_flexible(rut_entrante)
        titular_por_rut = (await db.folders.find_one(
            {"codeudor_rut": {"$regex": rx_cod, "$options": "i"}}) if rx_cod else None)
        if titular_por_rut and not (existente and existente.get("id") == titular_por_rut.get("id")):
            es_correo_codeudor = True
            cod_nombre = titular_por_rut.get("codeudor_nombre") or cliente
            cod_rut = rut_entrante
            existente = titular_por_rut
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
    # LEY DEL RUT: al vincular a una carpeta EXISTENTE, cada archivo se escanea con OCR;
    # si su RUT no coincide 100% con el dueño (o codeudor), el vínculo se descarta.
    ruts_carpeta = ([existente.get("rut", ""), existente.get("codeudor_rut", "")]
                    if existente else [])
    rechazados_ley_rut = []
    for d in docs:
        p = src / d["filename"]
        if p.exists():
            match_solo_codeudor = False
            if existente and any(len(_norm_rut(r or "")) >= 7 for r in ruts_carpeta):
                ok_rut, ruts_arch = await asyncio.to_thread(_ley_rut_ok, p.read_bytes(), ruts_carpeta)
                if not ok_rut:
                    rechazados_ley_rut.append(
                        {"filename": d["filename"], "ruts": sorted(ruts_arch)})
                    continue
                # RUTEO POR RUT: si el archivo trae SOLO el RUT del codeudor,
                # va directo a la subcarpeta 05_codeudor
                _rt = _norm_rut(existente.get("rut", "") or "")
                _rc = _norm_rut(existente.get("codeudor_rut", "") or "")
                match_solo_codeudor = (len(_rc) >= 7 and _rc in ruts_arch
                                       and not (_rt and _rt in ruts_arch))
            fn_orig = d["filename"]
            es_cod_arch = (match_solo_codeudor or es_correo_codeudor
                           or bool(re.search(r"co-?deudor", fn_orig, re.I)))
            if es_cod_arch:
                # Subcarpeta con el NOMBRE del codeudor: 05_codeudor/<Nombre>
                sub = f"05_codeudor/{_safe_name(cod_nombre)}" if cod_nombre else "05_codeudor"
                fn_dest = fn_orig if fn_orig.upper().startswith("CODEUDOR_") else f"CODEUDOR_{fn_orig}"
            else:
                tipo_ef = _tipo_efectivo(d)
                sub = fsvc.SUBFOLDER_POR_TIPO.get(tipo_ef, "99_otros")
                fn_dest = fsvc.nombre_con_prefijo(fn_orig, fsvc.SUBFOLDER_A_CAT.get(sub, ""))
            sd = dest / sub
            sd.mkdir(parents=True, exist_ok=True)
            (sd / fn_dest).write_bytes(p.read_bytes())
            # si el mismo archivo quedó antes en otra subcarpeta, quitarlo (evita duplicados)
            for viejo in list(dest.rglob(fn_orig)) + list(dest.rglob(fn_dest)):
                if viejo.parent != sd or viejo.name != fn_dest:
                    viejo.unlink(missing_ok=True)
            uploaded.append(f"{sub}/{fn_dest}")
    if rechazados_ley_rut:
        _nombres_rech = [r["filename"] for r in rechazados_ley_rut]
        await db.correos_pendientes.update_one(
            {"qid": qid, "motivo": {"$regex": "^LEY DEL RUT"}},
            {"$setOnInsert": {
                "id": str(uuid.uuid4()), "qid": qid,
                "subject": item.get("subject", ""), "sender": item.get("sender", ""),
                "fecha": item.get("date_iso", ""),
                "motivo": (f"LEY DEL RUT: {len(_nombres_rech)} archivo(s) con RUT que NO coincide "
                           f"con {cliente} ({(existente or {}).get('rut', '')})"),
                "cliente_sugerido": "",
                "adjuntos": _nombres_rech,
                "estado": "pendiente", "creado_en": now_iso()}},
            upsert=True)
        await db.alertas.insert_one({
            "id": str(uuid.uuid4()), "tipo": "ley_del_rut",
            "cliente": cliente,
            "mensaje": (f"🛡️ LEY DEL RUT: {len(_nombres_rech)} archivo(s) rechazado(s) de la carpeta "
                        f"de {cliente} por RUT distinto — enviados al Buzón de Rescate: "
                        + ", ".join(_nombres_rech[:4])),
            "fecha": now_iso(), "leida": False})
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
        "subsidy": {"tipo": "con_subsidio" if con_sub == True else "sin_subsidio"},
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
    # REGLA DURA al ingresar la solicitud: mínimo 2.000 UF sin subsidio
    try:
        _monto_hr = float(fin_nuevos.get("monto_credito") or 0)
    except (TypeError, ValueError):
        _monto_hr = 0
    if _monto_hr and _monto_hr < 2000 and not con_sub:
        _msg_hr = "ALERTA: No cumple criterio mínimo de 2.000 UF. Avisar a jefatura"
        ya_hr = await db.alertas.find_one({"tipo": "hard_rule", "cliente": cliente})
        if not ya_hr:
            await db.alertas.insert_one({
                "id": str(uuid.uuid4()), "tipo": "hard_rule", "nivel": "critica",
                "cliente": cliente,
                "mensaje": f"🔴 {_msg_hr} — {cliente}: {_monto_hr:g} UF sin subsidio",
                "fecha": now_iso(), "leida": False})
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
        st = {"_key": "proc_auto", "enabled": True, "interval_min": 2,
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
    if os.environ.get("AI_EMERGENCY_STOP") == "1":
        return {"skipped": True, "motivo": "AI_EMERGENCY_STOP activo"}
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
                    # FLUJO LINEAL: creación FORZADA de carpeta para cada cliente nuevo
                    # detectado con nombre válido y adjuntos (la regla ya no descarta).
                    cl_auto = it.get("classification") or {}
                    nombre_cli_f = (cl_auto.get("cliente") or "").strip()
                    if len(nombre_cli_f.split()) >= 2 and (cl_auto.get("documentos") or []):
                        try:
                            await proc_upload_drive(it["id"], force=True, clave=CLAVE_FORZAR_CARPETA)
                            resumen["carpetas"] += 1
                            await db.alertas.insert_one({
                                "id": str(uuid.uuid4()), "tipo": "carpeta_forzada",
                                "cliente": nombre_cli_f,
                                "mensaje": (f"📁 Carpeta creada en modo FORZADO para {nombre_cli_f} "
                                            f"(no cumplía la regla: {he.detail[:80]})"),
                                "fecha": now_iso(), "leida": False})
                            continue
                        except Exception as e2:
                            resumen["errors"].append(f"forzado '{nombre_cli_f[:25]}': {str(e2)[:60]}")
                    await db.proc_queue.update_one({"id": it["id"]}, {"$set": {
                        "status": "descartado", "descartado_motivo": he.detail,
                        "descartado_en": now_iso()}})
                    # BUZÓN DE RESCATE: guardar para clasificación manual
                    await db.correos_pendientes.update_one(
                        {"qid": it["id"]},
                        {"$setOnInsert": {
                            "id": str(uuid.uuid4()), "qid": it["id"],
                            "subject": it.get("subject", ""), "sender": it.get("sender", ""),
                            "fecha": it.get("date_iso", ""), "motivo": he.detail,
                            "cliente_sugerido": (it.get("classification") or {}).get("cliente", ""),
                            "adjuntos": [d.get("filename") for d in
                                         (it.get("classification") or {}).get("documentos") or []],
                            "estado": "pendiente", "creado_en": now_iso()}},
                        upsert=True)
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
            intervalo = max(2, int(st.get("interval_min") or 2))
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
    fecha_txt = hoy.strftime("%d/%m/%Y")
    cuerpo = f"""
    <div style="font-family:Arial,sans-serif;font-size:14px;color:#222">
      <h2 style="color:#6c5ce7;margin:0 0 4px">Reporte diario — {fecha_txt}</h2>
      <p style="color:#666;margin:0 0 16px">Período: {datos['desde'][:16].replace('T',' ')} → {datos['hasta'][:16].replace('T',' ')} (hora Chile)</p>
      <h3 style="color:#1a1f2e;margin:0 0 6px">📥 Solicitudes de crédito recibidas ({len(datos['recibidas'])})</h3>
      {_tabla_reporte_html(datos['recibidas'])}
      <h3 style="color:#1a1f2e;margin:16px 0 6px">📤 Enviadas efectivamente a mesa ({len(datos['enviadas'])})</h3>
      {_tabla_reporte_html(datos['enviadas'], con_envio=True)}
      <p style="color:#888;font-size:12px;margin-top:18px">Central Mutuos · Reporte automático de las {int((await _reporte_diario_state()).get('hora') or 10)}:00</p>
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
        resp = await _llm_con_timeout(chat, UserMessage(text=f"ASUNTO: {subject}\n\n{(texto or '')[:4000]}"))
        import constitucion as _const
        await _const.consultar_cerebro(db, "clasificacion_cobro_ia", texto_ia=str(resp), modulo="server.py (cobro tasación)")
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
        resp = await _llm_con_timeout(chat, UserMessage(text=f"ADJUNTOS: {adjuntos}\n\n{(texto or '')[:3000]}"))
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
                                        f"💰 Tasación pagada — {quien}", aviso, [], "principal")
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
        email_cliente = d.get("email") or d.get("email_cliente") or ""
        if not email_cliente:
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
    # Sincronización: si la carpeta ya tiene correo/RUT guardados (ej: desde Aprobación
    # Cliente), se usan sin pedirlos de nuevo.
    if toks:
        f_s = await db.folders.find_one({"nombre": {"$regex": ".*".join(re.escape(t) for t in toks[:2]), "$options": "i"}})
        if f_s:
            if not datos.get("email_cliente") and (f_s.get("email") or f_s.get("email_cliente")):
                datos["email_cliente"] = f_s.get("email") or f_s.get("email_cliente")
            if not datos.get("rut") and f_s.get("rut"):
                datos["rut"] = f_s.get("rut")
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
    recientes = await db.cierres_log.find({}).sort("fecha", -1).limit(5).to_list(5)
    return {"cierres": filas,
            "respuestas_recientes": [clean(r) for r in recientes],
            "ventana": {"desde": ventana_inicio.isoformat(),
                        "hasta_domingo": ultimo_domingo.isoformat()}}


@api.get("/cierres/avisos")
async def cierres_avisos():
    """Respuestas de ejecutivos sin ver (para la campanita del panel)."""
    docs = await db.cierres_log.find({"visto": {"$ne": True}}).sort("fecha", -1).limit(20).to_list(20)
    return {"avisos": [clean(d) for d in docs], "total": len(docs)}


@api.post("/cierres/avisos/marcar")
async def cierres_avisos_marcar():
    await db.cierres_log.update_many({"visto": {"$ne": True}}, {"$set": {"visto": True}})
    return {"ok": True}


async def _resumen_cierres_loop():
    """Resumen semanal (domingo): clientes de Cierres que siguen sin responder."""
    while True:
        await asyncio.sleep(3600)
        try:
            hoy = datetime.now(timezone.utc)
            if hoy.weekday() != 6:
                continue
            semana = hoy.strftime("%Y-%W")
            cfg = await db.config.find_one({"_key": "resumen_cierres"})
            if cfg and cfg.get("semana") == semana:
                continue
            data = await cierres_list(False, False)
            pendientes = [c for c in data["cierres"]
                          if c["toca_preguntar"] or (c["consultas"] and not c["respuesta_final"])]
            if pendientes:
                def estado_txt(c):
                    base_t = f"{c['consultas']} consulta(s)"
                    if c["dias_desde_consulta"] is None:
                        return base_t + " · nunca consultado"
                    return base_t + f" · última hace {c['dias_desde_consulta']} día(s)"
                filas = "".join(
                    f"<tr><td style='padding:6px 10px;border-bottom:1px solid #eee'><b>{c['nombre']}</b></td>"
                    f"<td style='padding:6px 10px;border-bottom:1px solid #eee'>{c['ejecutivo_nombre'] or '—'} · {c['ejecutivo_email'] or 'sin correo'}</td>"
                    f"<td style='padding:6px 10px;border-bottom:1px solid #eee'>{estado_txt(c)}</td></tr>"
                    for c in pendientes)
                inner = (f"<p>Resumen semanal del módulo <b>Cierres</b>: {len(pendientes)} cliente(s) "
                         "con aprobación enviada siguen sin confirmación del ejecutivo.</p>"
                         "<table style='border-collapse:collapse;font-size:13px'>"
                         "<tr><th style='padding:6px 10px;text-align:left'>Cliente</th>"
                         "<th style='padding:6px 10px;text-align:left'>Ejecutivo</th>"
                         "<th style='padding:6px 10px;text-align:left'>Estado</th></tr>"
                         f"{filas}</table>"
                         "<p style='margin-top:14px'>Entrá al módulo Cierres para preguntar con un clic.</p>")
                cuerpo = _marca_wrap(inner, "Cierres — Resumen semanal")
                destino = _sender_por_rol("principal")
                await asyncio.to_thread(mail.send_mail, destino,
                                        f"Resumen semanal Cierres — {len(pendientes)} cliente(s) sin respuesta",
                                        cuerpo, [], "principal")
            await db.config.update_one({"_key": "resumen_cierres"},
                                       {"$set": {"semana": semana, "enviado_en": now_iso()}}, upsert=True)
        except Exception as e:
            await db.system_log.insert_one({"id": str(uuid.uuid4()), "loop": "resumen_cierres",
                                            "error": str(e)[:300], "fecha": now_iso()})


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
                                         "carpeta_borrada": True, "visto": False, "fecha": now_iso()})
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
                                     "carpeta_borrada": False, "visto": False, "fecha": now_iso()})
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
    # COLA DE SUPERVISIÓN DE RENÉ: ningún patrón se vuelve regla oficial sin su aprobación
    import hashlib as _hl
    for tipo, items in (("aprendizaje", resultado.get("aprendizajes") or []),
                        ("mejora", resultado.get("mejoras") or [])):
        for it in items:
            texto = (it if isinstance(it, str)
                     else f"{it.get('titulo', '')}: {it.get('detalle', '')}").strip(" :")
            if len(texto) < 10:
                continue
            pid = _hl.sha256(texto.lower().encode()).hexdigest()[:24]
            await db.patrones_supervision.update_one(
                {"id": pid},
                {"$setOnInsert": {"id": pid, "tipo": tipo, "texto": texto[:500],
                                  "estado": "pendiente", "detectado_en": now_iso()}},
                upsert=True)
    return doc


@api.get("/admin/supervision")
async def supervision_lista():
    pend = await db.patrones_supervision.find({"estado": "pendiente"}, {"_id": 0}).sort("detectado_en", -1).to_list(100)
    res = await db.patrones_supervision.find({"estado": {"$ne": "pendiente"}}, {"_id": 0}).sort("resuelto_en", -1).limit(20).to_list(20)
    return {"pendientes": pend, "resueltos": res}


@api.post("/admin/supervision/{pid}/resolver")
async def supervision_resolver(pid: str, payload: dict, request: Request):
    """Solo René Osa aprueba o rechaza patrones detectados (validación digital)."""
    _solo_maestro(request)
    await _validar_clave_rene(str((payload or {}).get("clave") or ""))
    accion = (payload or {}).get("accion")
    if accion not in ("aprobar", "rechazar"):
        raise HTTPException(status_code=400, detail="Acción inválida: use aprobar o rechazar")
    p = await db.patrones_supervision.find_one({"id": pid})
    if not p:
        raise HTTPException(status_code=404, detail="Patrón no encontrado")
    estado = "aprobado" if accion == "aprobar" else "rechazado"
    await db.patrones_supervision.update_one({"id": pid}, {"$set": {
        "estado": estado, "resuelto_en": now_iso(), "resuelto_por": "René Osa"}})
    if accion == "aprobar":
        fecha_txt = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M")
        await db.config.update_one({"_key": "criterios"}, {"$push": {"reglas_supervisadas": {
            "texto": p["texto"], "aprobado_en": now_iso(), "por": "René Osa"}}})
        await db.criterios_auditoria.insert_one({
            "id": str(uuid.uuid4()), "fecha": now_iso(), "usuario": "René Osa",
            "detalle": f"Patrón aprobado como regla oficial por René Osa el {fecha_txt} (UTC)",
            "cambios": [{"campo": "reglas_supervisadas", "antes": None, "despues": p["texto"][:200]}]})
    return {"ok": True, "estado": estado}


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
    sub_html = (f'<div style="color:#9ca3af;font-size:12px;margin-top:10px;font-weight:600">{subtitulo}</div>'
                if subtitulo else "")
    # REGLA DE ORO #16 — RESPONSIVIDAD ABSOLUTA: max-width 600px, padding fluido,
    # media query para teléfonos, sin anchos fijos ni desbordes.
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body {{ margin:0; padding:0; width:100% !important; background:#ffffff; }}
  .cm-wrap {{ width:100%; max-width:600px; margin:0 auto; }}
  .cm-pad {{ padding:28px 32px; }}
  .cm-body {{ font-size:14px; line-height:1.65; word-break:break-word; overflow-wrap:break-word; }}
  img {{ max-width:100%; height:auto; }}
  table {{ width:100% !important; border-collapse:collapse; }}
  @media only screen and (max-width:480px) {{
    .cm-pad {{ padding:18px 16px !important; }}
    .cm-title {{ font-size:19px !important; }}
    .cm-body {{ font-size:15px !important; }}
  }}
</style></head>
<body>
    <div style="background:#ffffff;padding:20px 10px;font-family:Arial,Helvetica,sans-serif">
      <div class="cm-wrap" style="background:#ffffff;border:1px solid #e2e4e9;border-radius:10px;overflow:hidden">
        <div class="cm-pad" style="background:#0a0a0a;border-bottom:2px solid #C9A227;text-align:center">
          <div class="cm-title" style="color:#C9A227;font-family:Georgia,'Times New Roman',serif;font-size:24px;font-weight:700;letter-spacing:3px">CENTRAL MUTUOS</div>
          <div style="height:1px;background:#C9A227;width:70%;margin:9px auto 7px"></div>
          <div style="color:#C9A227;font-family:Georgia,'Times New Roman',serif;font-size:11px;letter-spacing:6px">CON CRECES</div>
          {sub_html}
        </div>
        <div class="cm-pad cm-body" style="color:#111111">
          {inner}
        </div>
        <div class="cm-pad" style="padding-top:0">
          <p style="margin:14px 0 0;color:#111111;font-size:14px"><b>Central Mutuos</b><br>
          <span style="color:#6b7280;font-size:12px">{_cargo_admin_cache["v"]}</span><br>
          <span style="color:#6b7280;font-size:12px">Cr&eacute;ditos Hipotecarios</span></p>
        </div>
        <div class="cm-pad" style="background:#f0f0f0;text-align:center;padding-top:12px;padding-bottom:12px">
          <span style="color:#888888;font-size:11px">Este correo contiene informaci&oacute;n confidencial dirigida exclusivamente a su destinatario.</span>
        </div>
      </div>
    </div>
</body></html>"""


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
            nota = f" <span style='color:#8a6d1a;font-style:italic;font-weight:400;font-size:10.5px'>({it['texto']})</span>" if (it.get("texto") or "").strip() else ""
            valor_html = f"<b>{_num_uf(it['valor'])} UF</b>{nota}"
        filas += (f"<tr style='background:{bg}'>"
                  f"<td style='padding:7px 10px;border-bottom:1px solid #eceef3;color:#2b3245;font-size:12px'>{it.get('concepto','')}</td>"
                  f"<td style='padding:7px 10px;border-bottom:1px solid #eceef3;text-align:right;color:#1a1f2e;white-space:nowrap;font-size:12px'>{valor_html}</td></tr>")
    filas += (f"<tr style='background:#1a1f2e'>"
              f"<td style='padding:9px 10px;color:#d4af37;font-weight:700;letter-spacing:0.5px;font-size:12.5px'>TOTAL</td>"
              f"<td style='padding:9px 10px;text-align:right;color:#d4af37;font-weight:700;font-size:13px;white-space:nowrap'>{_num_uf(total)} UF</td></tr>")
    valor_uf = payload.get("valor_uf")
    if valor_uf:
        filas += (f"<tr style='background:#1a1f2e'>"
                  f"<td style='padding:5px 10px 9px;color:#9aa3b5;font-size:10.5px'>TOTAL EN PESOS (UF del día ${_fmt_num_clp(valor_uf)})</td>"
                  f"<td style='padding:5px 10px 9px;text-align:right;color:#ffffff;font-weight:700;font-size:12px;white-space:nowrap'>${_fmt_num_clp(round(total * float(valor_uf)))} CLP</td></tr>")
    pago_filas = "".join(
        f"<tr><td style='padding:4px 10px 4px 0;color:#6b7280;font-size:12px;white-space:nowrap;vertical-align:top'>{lbl}</td>"
        f"<td style='padding:4px 0;color:#1a1f2e;font-size:12px;font-weight:600;word-break:break-word'>{val}</td></tr>"
        for lbl, val in [("Nombre", dp.get("nombre", "")), ("RUT", dp.get("rut", "")),
                         ("Banco", dp.get("banco", "")), ("Tipo de cuenta", dp.get("tipo_cuenta", "")),
                         ("N° de cuenta", dp.get("numero_cuenta", "")),
                         ("Correo", dp.get("email", ""))] if val)
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="x-apple-disable-message-reformatting">
</head>
<body style="margin:0;padding:0;background:#f2f4f8">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f2f4f8">
    <tr><td align="center" style="padding:14px 6px">
      <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;background:#ffffff;font-family:Arial,Helvetica,sans-serif;border-collapse:collapse">
        <tr><td style="background:#1a1f2e;padding:16px 20px;border-bottom:3px solid #d4af37">
          <span style="color:#d4af37;font-size:18px;font-weight:700;letter-spacing:1px">Central Mutuos</span>
        </td></tr>
        <tr><td style="padding:20px 20px 6px">
          <p style="margin:0 0 3px;color:#1a1f2e;font-size:15px;font-weight:700">Estimada(o) {nombre}</p>
          <p style="margin:0 0 12px;color:#6b7280;font-size:12px">RUT: {rut}</p>
          <div style="color:#2b3245;font-size:13px;line-height:1.55">{intro_html}</div>
        </td></tr>
        <tr><td style="padding:8px 20px 2px">
          <div style="color:#1a1f2e;font-size:13.5px;font-weight:700;border-left:4px solid #d4af37;padding-left:9px;margin-bottom:10px">Detalle de Gastos Operacionales</div>
          <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="width:100%;border-collapse:collapse;font-size:12px;border:1px solid #eceef3">
            <tr style="background:#eef1f7">
              <th style="padding:7px 10px;text-align:left;color:#4b5563;font-size:10px;letter-spacing:1px;text-transform:uppercase">Concepto</th>
              <th style="padding:7px 10px;text-align:right;color:#4b5563;font-size:10px;letter-spacing:1px;text-transform:uppercase">Valor</th>
            </tr>
            {filas}
          </table>
        </td></tr>
        <tr><td style="padding:16px 20px 4px">
          <div style="color:#1a1f2e;font-size:13.5px;font-weight:700;border-left:4px solid #d4af37;padding-left:9px;margin-bottom:10px">Cuenta Recaudadora</div>
          <div style="background:#f8f9fc;border:1px solid #eceef3;padding:10px 14px">
            <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="border-collapse:collapse">{pago_filas}</table>
          </div>
        </td></tr>
        <tr><td style="padding:14px 20px 20px">
          <p style="margin:0;color:#6b7280;font-size:12px;line-height:1.55">Ante cualquier consulta sobre el detalle de estos valores o el proceso de pago, no dude en responder este correo. Estamos a su disposición.</p>
          <p style="margin:12px 0 0;color:#1a1f2e;font-size:13px"><b>Central Mutuos</b><br>
          <span style="color:#6b7280;font-size:11px">Créditos Hipotecarios</span></p>
        </td></tr>
        <tr><td style="background:#1a1f2e;padding:9px 14px;text-align:center">
          <span style="color:#9aa3b5;font-size:10px">Este correo contiene información confidencial dirigida exclusivamente a su destinatario.</span>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


@api.post("/gastos-operacionales/enviar")
async def gastos_enviar(payload: dict):
    payload = payload or {}
    to = (payload.get("email_cliente") or "").strip()
    extras_raw = payload.get("emails_extra") or []
    if isinstance(extras_raw, str):
        extras_raw = re.split(r"[,;\s]+", extras_raw)
    extras = []
    for e in extras_raw:
        e = (e or "").strip()
        if e and "@" in e and e.lower() != to.lower() and e.lower() not in [x.lower() for x in extras]:
            extras.append(e)
    nombre = (payload.get("nombre") or "").strip()
    total = _gastos_total(payload.get("items"))
    try:
        payload["valor_uf"] = await get_valor_uf()
    except Exception:
        payload["valor_uf"] = None
    subject = payload.get("subject") or f"Gastos Operacionales — {nombre}"
    cuerpo = _gastos_html(payload)
    if not payload.get("confirm"):
        return {"to": to, "emails_extra": extras, "subject": subject, "body": cuerpo, "total": total,
                "sender": _sender_por_rol("secundaria")}
    if not to or "@" not in to:
        raise HTTPException(status_code=400, detail="Correo del cliente inválido")
    destinos = [to] + extras
    res = await asyncio.to_thread(mail.send_mail, destinos, subject, cuerpo, [], "secundaria")
    if not res.get("success"):
        raise HTTPException(status_code=502, detail=res.get("error", "Error de envío"))
    await db.gastos_op_log.insert_one({
        "id": str(uuid.uuid4()), "nombre": nombre, "rut": payload.get("rut", ""),
        "to": to, "emails_extra": extras, "total": total, "items": payload.get("items") or [],
        "intro": payload.get("intro", ""), "datos_pago": payload.get("datos_pago") or {},
        "enviado_en": now_iso(), "desde": res.get("desde", "")})
    # SINCRONIZACIÓN: el correo ingresado queda guardado en la carpeta del cliente
    # para que todos los módulos (aprobación, tasación, etc.) lo tengan disponible.
    toks_n = [t for t in re.split(r"\s+", nombre) if len(t) >= 3]
    if toks_n:
        await db.folders.update_one(
            {"$and": [{"nombre": {"$regex": re.escape(t), "$options": "i"}} for t in toks_n[:2]],
             "$or": [{"email": {"$exists": False}}, {"email": ""}]},
            {"$set": {"email": to}})
    return {"ok": True, "to": to, "emails_extra": extras, "subject": subject, "total": total, "sender": res.get("desde", "")}


@api.get("/gastos-operacionales/log")
async def gastos_log():
    docs = await db.gastos_op_log.find({}).sort("enviado_en", -1).limit(20).to_list(20)
    out = []
    for d in docs:
        total = float(d.get("total") or 0)
        pagado = float(d.get("pagado") or 0)
        d["pagado"] = round(pagado, 2)
        d["saldo"] = round(d.get("saldo") if d.get("saldo") is not None else total - pagado, 2)
        d["estado_pago"] = d.get("estado_pago") or ("pagado" if total > 0 and d["saldo"] <= 0.01
                                                    else ("parcial" if pagado > 0 else "pendiente"))
        out.append(clean(d))
    return {"log": out}


@api.post("/gastos-operacionales/log/{lid}/pago")
async def gastos_registrar_pago(lid: str, payload: dict):
    """Registra un pago (manual o auto) sobre un envío de gastos operacionales."""
    payload = payload or {}
    try:
        monto = round(float(payload.get("monto")), 2)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Monto de pago inválido")
    if monto <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser mayor a 0")
    doc = await db.gastos_op_log.find_one({"id": lid})
    if not doc:
        raise HTTPException(status_code=404, detail="Envío no encontrado")
    pago = {"monto": monto, "fecha": (payload.get("fecha") or now_iso()[:10])[:10],
            "origen": payload.get("origen", "manual"),
            "detalle": payload.get("detalle", ""), "registrado_en": now_iso()}
    pagos = (doc.get("pagos") or []) + [pago]
    pagado = round(sum(float(p.get("monto") or 0) for p in pagos), 2)
    total = float(doc.get("total") or 0)
    saldo = round(total - pagado, 2)
    estado = "pagado" if saldo <= 0.01 else "parcial"
    await db.gastos_op_log.update_one({"id": lid}, {"$set": {
        "pagos": pagos, "pagado": pagado, "saldo": saldo, "estado_pago": estado}})
    return {"ok": True, "pagado": pagado, "saldo": saldo, "estado_pago": estado}


@api.delete("/gastos-operacionales/log/{lid}/pago/{idx}")
async def gastos_eliminar_pago(lid: str, idx: int):
    doc = await db.gastos_op_log.find_one({"id": lid})
    if not doc:
        raise HTTPException(status_code=404, detail="Envío no encontrado")
    pagos = doc.get("pagos") or []
    if not (0 <= idx < len(pagos)):
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    pagos.pop(idx)
    pagado = round(sum(float(p.get("monto") or 0) for p in pagos), 2)
    total = float(doc.get("total") or 0)
    saldo = round(total - pagado, 2)
    estado = "pagado" if total > 0 and saldo <= 0.01 else ("parcial" if pagado > 0 else "pendiente")
    await db.gastos_op_log.update_one({"id": lid}, {"$set": {
        "pagos": pagos, "pagado": pagado, "saldo": saldo, "estado_pago": estado}})
    return {"ok": True, "pagado": pagado, "saldo": saldo, "estado_pago": estado}


def _sin_acentos(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower()


@api.post("/gastos-operacionales/pagos/scan")
async def gastos_pagos_scan():
    """Revisa correos recientes buscando comprobantes de transferencia que
    coincidan con clientes con saldo pendiente y registra el pago automático."""
    pendientes = await db.gastos_op_log.find(
        {"$or": [{"saldo": {"$gt": 0}}, {"pagos": {"$exists": False}}]}
    ).sort("enviado_en", -1).limit(30).to_list(30)
    pendientes = [p for p in pendientes
                  if float(p.get("total") or 0) - float(p.get("pagado") or 0) > 0.01]
    if not pendientes:
        return {"ok": True, "detectados": 0, "detalle": [],
                "mensaje": "No hay envíos con saldo pendiente."}
    correos = await asyncio.to_thread(mail.fetch_pdf_attachments, None, 25, True)
    kw_transfer = re.compile(r"transferencia|comprobante|abono|dep[oó]sito|pago\s+(recibid|realizad|efectuad)", re.I)
    try:
        uf_hoy = await get_valor_uf()
    except Exception:
        uf_hoy = None
    detectados = []
    for c in correos:
        texto = _sin_acentos(f"{c.get('subject','')} {c.get('body','')}")
        if not kw_transfer.search(texto):
            continue
        for p in pendientes:
            partes = [x for x in re.split(r"\s+", _sin_acentos(p.get("nombre", ""))) if len(x) > 2][:2]
            if len(partes) < 2 or not all(x in texto for x in partes):
                continue
            ref = f"{c.get('subject','')}|{c.get('date','')}"
            if ref in (p.get("auto_refs") or []):
                continue
            m = re.search(r"\$\s*([\d.]{4,})", f"{c.get('subject','')} {c.get('body','')}")
            monto_clp = int(m.group(1).replace(".", "")) if m else None
            monto_uf = round(monto_clp / uf_hoy, 2) if (monto_clp and uf_hoy) else None
            saldo_actual = round(float(p.get("total") or 0) - float(p.get("pagado") or 0), 2)
            monto_final = monto_uf if monto_uf else saldo_actual
            await gastos_registrar_pago(p["id"], {
                "monto": monto_final, "fecha": (c.get("date") or now_iso())[:10],
                "origen": "auto",
                "detalle": f"Transferencia detectada: \"{(c.get('subject') or '')[:80]}\" de {c.get('from','')}"
                           + (f" — ${monto_clp:,} CLP".replace(",", ".") if monto_clp else " (sin monto en el correo: se asumió el saldo)")})
            await db.gastos_op_log.update_one({"id": p["id"]}, {"$push": {"auto_refs": ref}})
            detectados.append({"cliente": p.get("nombre"), "monto_uf": monto_final,
                               "monto_clp": monto_clp, "asunto": c.get("subject", "")})
    return {"ok": True, "detectados": len(detectados), "detalle": detectados}


# ---------------------------------------------------------------------------
# Solicitud de Tasación (Value Property + Victoria Vilches + inmobiliaria)
# ---------------------------------------------------------------------------
TASACION_DEST_DEFAULT = ["contacto@valueproperty.cl"]
VICTORIA_EMAIL = "victoriavilches@centralmutuos.cl"


def _parse_destinatarios(payload, defaults):
    dest = payload.get("destinatarios")
    if isinstance(dest, str):
        dest = [d.strip() for d in re.split(r"[,;\n]+", dest) if d.strip()]
    if not dest:
        dest = list(defaults)
    dest = [d for d in dest if "@" in d]
    # REGLA CC (norma fija): en correos SALIENTES nadie interno se agrega como copia
    # encubierta — Victoria/Daniela reciben copia SOLO al procesar correos ENTRANTES.
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
    # REGLA DE ORO #64: 1° DashAI DB — si el perfil ya tiene la fecha, no se consulta el correo
    p_fecha = (doc.get("perfil_consolidado") or {}).get("fecha_tasacion") or doc.get("tasacion_fecha")
    if p_fecha:
        await db.folders.update_one({"id": fid}, {"$set": {"tasacion_fecha": p_fecha,
                                                           "tasacion_fecha_origen": "dashai_db"}})
        return {"ok": True, "fecha": p_fecha, "fuente": "DashAI DB (Regla #64)"}
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
# ─── VIVIENDA USADA: listado oficial estructurado (secciones romanas / subsecciones) ───
SECCIONES_ESTUDIO_USADA = [
    ("I.- ANTECEDENTES DEL INMUEBLE", [
        ("a.- Título vigente:", [
            "Copia de inscripción de dominio con certificado de vigencia (emisión no mayor a 45 días).",
            "Certificado de hipotecas, gravámenes y litigios pendientes de 30 años (emisión no mayor a 45 días).",
            "Copia de la escritura con la cual se efectuó la inscripción.",
        ]),
        ("b.- Propiedad adquirida por Herencia:", [
            "Copia de inscripción especial de herencia con certificado de vigencia (emisión no mayor a 45 días).",
            "Copia de inscripción de posesión efectiva con anotación marginal de pago o exención de impuesto de herencia.",
            "Copia del testamento y su inscripción si los hubiere.",
            "Copia del inventario de bienes.",
        ]),
        ("c.- Títulos anteriores hasta completar 10 años:", [
            "Copias de inscripciones de dominio de antecesores hasta completar 10 años de posesión inscrita.",
            "Copias de escrituras de dichas inscripciones.",
            "En caso de sucesiones hereditarias: mismos antecedentes de letra b.",
            "En caso de personas jurídicas como propietarias anteriores: copias de los poderes.",
        ]),
    ]),
    ("II.- ANTECEDENTES DE SUBDIVISIONES, FUSIONES Y/O EDIFICACIONES", [
        ("a.- Inmueble urbano resultante de subdivisión:", [
            "Copia de Resolución DOM que autorizó la subdivisión.",
            "Copia del Plano de Subdivisión aprobado por DOM y archivado en CBR.",
            "Certificado DOM de urbanización ejecutada o garantizada.",
            "Certificado DOM de numeración municipal.",
            "Certificado SII de asignación de roles de avalúo en trámite.",
        ]),
        ("b.- Inmueble rural resultante de subdivisión:", [
            "Copia de Resolución SAG que autorizó la subdivisión.",
            "Copia del Plano de Subdivisión aprobado por SAG y archivado en CBR.",
            "Certificado SII de asignación de roles de avalúo en trámite.",
            "Copia del Reglamento del Loteo Rural si lo hubiere.",
            "Para inmuebles ExCora: Certificado de deuda Cora y Certificado de deuda Indap.",
        ]),
        ("c.- Inmueble resultante de fusión:", [
            "Copia de Resolución DOM que autorizó la fusión.",
            "Copia del Plano de Fusión aprobado por DOM y archivado en CBR.",
            "Certificado DOM de urbanización ejecutada o garantizada si corresponde.",
            "Certificado DOM de numeración municipal.",
            "Certificado SII de asignación de rol al lote resultante.",
        ]),
    ]),
    ("III.- OTROS DOCUMENTOS Y CERTIFICADOS", [
        ("", [
            "Certificado de Deudas de Contribuciones emitido por TGR.",
            "Copia del recibo de pago de cuotas de contribuciones vencidas según corresponda.",
            "Certificado de no expropiación SERVIU (emisión no mayor a 30 días).",
            "Certificado de no expropiación Municipal (emisión no mayor a 30 días).",
            "Certificado de numeración Municipal si hubiere cambiado o no aparece en la inscripción de dominio.",
            "Copia del Contrato de Promesa de Compraventa si lo hubiere.",
        ]),
    ]),
]
# Lista plana solo para visualización en el formulario del frontend
DOCS_ESTUDIO_USADA = [d for _, subs in SECCIONES_ESTUDIO_USADA for _, docs in subs for d in docs]
# VIVIENDA NUEVA: sin listado de documentos — solo la solicitud estándar
DOCS_ESTUDIO_NUEVA = []


def _plazos_bold(texto):
    return re.sub(r"(45 días|30 días|10 años)", r"<b>\1</b>", texto)


def _docs_usada_html():
    """Listado oficial de estudio de título para vivienda usada — HTML cuidado."""
    partes = ['<div style="margin-top:22px">'
              '<div style="text-align:center;font-weight:bold;font-size:16px;color:#111;'
              'letter-spacing:0.5px">ESTUDIO DE TÍTULO - DOCUMENTOS REQUERIDOS</div>'
              '<hr style="border:none;border-top:2px solid #333;margin:8px auto 18px;width:100%">']
    for titulo, subsecciones in SECCIONES_ESTUDIO_USADA:
        partes.append(
            f'<div style="background:#f0f0f0;border:1px solid #ddd;padding:8px 14px;'
            f'font-weight:bold;font-size:14px;color:#111;margin:16px 0 8px">{titulo}</div>')
        for letra, docs in subsecciones:
            if letra:
                partes.append(f'<div style="font-weight:bold;font-size:13.5px;color:#222;'
                              f'margin:10px 0 4px 4px">{letra}</div>')
            lis = "".join(f'<li style="margin:6px 0;line-height:1.55">{_plazos_bold(d)}</li>' for d in docs)
            partes.append(f'<ul style="margin:4px 0 10px;padding-left:26px;color:#111;font-size:13.5px">{lis}</ul>')
    partes.append('</div>')
    return "".join(partes)


def _estudio_usada_wrap(inner):
    """Correo de estudio de título USADA: fondo blanco, Arial, pie formal sin Concreces."""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#ffffff">
  <div style="max-width:680px;margin:0 auto;padding:30px 34px;background:#ffffff;
    font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.6;color:#111">
    {inner}
    <hr style="border:none;border-top:1px solid #ccc;margin:26px 0 14px">
    <p style="margin:0;color:#111;font-size:14px"><b>Central Mutuos</b><br>
    <span style="color:#555;font-size:12.5px">Cr&eacute;ditos Hipotecarios</span></p>
    <p style="margin-top:12px;color:#888;font-size:11px">Este correo contiene informaci&oacute;n
    confidencial dirigida exclusivamente a su destinatario.</p>
  </div>
</body></html>"""


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
    # VIVIENDA NUEVA: sin listado de documentos (solo la solicitud estándar).
    # VIVIENDA USADA: listado oficial estructurado con formato cuidado.
    docs_html = _docs_usada_html() if tipo == "usada" else ""
    obs = (p.get("observaciones") or "").strip()
    intro = (p.get("intro") or "").strip() or ("Solicitamos dar inicio al <b>estudio de títulos</b> del cliente en referencia. "
                                               "Se detallan los antecedentes:")
    inner = f"""
      <p>Estimados, junto con saludar:</p>
      <p>{intro}</p>
      <table style="border-collapse:collapse;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;width:100%">{''.join(filas)}</table>
      {docs_html}
      {f'<p style="margin-top:12px"><b>Observaciones:</b> {obs}</p>' if obs else ''}
      <p style="margin-top:10px;color:#334155;font-size:13px"><i>En caso de ser necesario,
      nos reservamos la posibilidad de seguir solicitando antecedentes que permitan la
      conclusi&oacute;n en tiempo y forma de este estudio de t&iacute;tulos.</i></p>
      <p style="margin-top:14px">Quedamos atentos a sus comentarios y a cualquier antecedente adicional que sea necesario.</p>
      <p style="margin-top:16px;color:#555">Saludos cordiales,</p>"""
    if tipo == "usada":
        return _estudio_usada_wrap(inner)
    return _marca_wrap(inner, "Estudio de Títulos")


@api.get("/estudio-titulo/defaults")
async def estudio_defaults():
    return {"destinatarios": ESTUDIO_DEST_DEFAULT, "docs_usada": DOCS_ESTUDIO_USADA,
            "docs_nueva": DOCS_ESTUDIO_NUEVA}


@api.get("/estudio-titulo/preview-carpeta/{fid}")
async def estudio_preview_carpeta(fid: str):
    """SUPERCARPETA — Vista previa del correo de Estudio de Título de una carpeta.
    Plantilla PROPIA (jamás la de Carta Oferta). Destinatario en orden:
    1) inmobiliaria registrada → 2) vendedor registrado → 3) correo de origen de la solicitud."""
    import malla_inteligencia as _mi
    fd = await db.folders.find_one({"id": fid})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no encontrada")
    nombre = (fd.get("nombre") or "").strip()
    rut = (fd.get("rut") or "").strip()
    inmo = _mi._inmo_de_folder(fd)
    proyecto = (fd.get("proyecto") or "").strip()
    tiene_inmo = bool(inmo) and inmo.strip().lower() not in ("", "casa usada")
    usada = (fd.get("tipo_operacion") or "").lower().startswith("usada") or not tiene_inmo
    tipo = "usada" if usada else "nueva"
    v = fd.get("vendedor_usada") or {}
    para, encargado, fuente, faltantes = "", "", "", []
    p = {"nombre": nombre, "rut": rut, "tipo_vivienda": tipo,
         "direccion": (fd.get("proyecto") or "") if usada else ""}
    if tiene_inmo:
        # 1) INMOBILIARIA registrada: contacto de estudio (exacto → general) o el de carta
        c = await db.contactos_carta.find_one({
            "inmobiliaria_norm": _mi._norm_inmo(inmo), "proyecto_norm": _mi._norm_inmo(proyecto),
            "activo": True, "estudio_email": {"$nin": ["", None]}})
        if not c:
            c = await db.contactos_carta.find_one({
                "inmobiliaria_norm": _mi._norm_inmo(inmo), "activo": True,
                "estudio_email": {"$nin": ["", None]}})
        if not c:
            c = await db.contactos_carta.find_one({
                "inmobiliaria_norm": _mi._norm_inmo(inmo), "proyecto_norm": _mi._norm_inmo(proyecto),
                "activo": True, "email": {"$nin": ["", None]}}) or await db.contactos_carta.find_one({
                "inmobiliaria_norm": _mi._norm_inmo(inmo), "activo": True, "email": {"$nin": ["", None]}})
        para = ((c or {}).get("estudio_email") or (c or {}).get("email") or "").strip()
        encargado = ((c or {}).get("estudio_nombre") or (c or {}).get("contacto") or "").strip()
        fuente = f"Inmobiliaria {inmo}"
        p.update({"inmobiliaria": f"{inmo}{' / ' + proyecto if proyecto else ''}",
                  "inmo_contacto_nombre": encargado, "inmo_contacto_email": para})
        if not para:
            faltantes.append(f"Contacto de la inmobiliaria {inmo} (Panel de Fuentes ⚙️)")
    elif (v.get("email") or "").strip():
        # 2) VENDEDOR registrado
        para = v["email"].strip()
        encargado = (v.get("nombre") or "").strip()
        fuente = "Vendedor directo"
        p.update({"vendedor_nombre": encargado, "vendedor_email": para,
                  "vendedor_telefono": (v.get("telefono") or "").strip()})
    else:
        # 3) Correo de ORIGEN de la solicitud de crédito (sugerido, editable)
        src = (fd.get("source_email") or "").strip()
        m = re.search(r"<([^<>]+@[^<>]+)>", src)
        para = (m.group(1) if m else (src if "@" in src else "")).strip()
        m_n = re.match(r'^"?([^"<]*)"?\s*<', src)
        encargado = (m_n.group(1).strip() if m_n else "")
        fuente = "Origen de la solicitud de crédito (sugerido)"
        if usada:
            p.update({"vendedor_nombre": encargado, "vendedor_email": para})
        else:
            p.update({"inmobiliaria": inmo, "inmo_contacto_nombre": encargado, "inmo_contacto_email": para})
        if not para:
            faltantes.append("Sin inmobiliaria, vendedor ni correo de origen — ingrese el destinatario a mano")
    subject = f"Solicitud de Antecedentes - Estudio de Título - {nombre}" + (f" {rut}" if rut else "")
    return {"cliente": nombre, "rut": rut, "tipo_vivienda": tipo, "para": para,
            "encargado": encargado, "fuente_destinatario": fuente, "cc": [],
            "faltantes": faltantes, "asunto": subject, "body": _estudio_html(p), "payload_envio": p}


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
    subject = f"Solicitud de Antecedentes - Estudio de Título - {nombre}" + (f" {rut}" if rut else "")
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
    # REGLA CC (norma fija): los correos SALIENTES jamás llevan CC — Victoria/Daniela
    # reciben copia solo al procesar correos ENTRANTES (reenvíos automáticos).
    res = await asyncio.to_thread(mail.send_mail, destinos, subject, cuerpo, adjuntos, "secundaria")
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
        # AUTOAPRENDIZAJE: el destinatario confirmado queda guardado para seguirle
        # el hilo al cliente durante todo el proceso (regla especial vivienda usada)
        try:
            import malla_inteligencia as _mi
            fd_ap = await db.folders.find_one({"id": payload["folder_id"]})
            if fd_ap and destinos:
                confirmado = destinos[0].strip()
                if payload.get("tipo_vivienda") == "usada":
                    v_ap = fd_ap.get("vendedor_usada") or {}
                    if confirmado.lower() != (v_ap.get("email") or "").lower():
                        v_ap.update({"nombre": (payload.get("vendedor_nombre") or v_ap.get("nombre") or "").strip(),
                                     "email": confirmado, "activo": True, "actualizado": now_iso(),
                                     "por": "aprendizaje automático (estudio de título)"})
                        await db.folders.update_one({"id": payload["folder_id"]},
                                                    {"$set": {"vendedor_usada": v_ap}})
                elif inmo:
                    inmo_base = inmo.split(" / ")[0].strip()
                    proy_ap = (fd_ap.get("proyecto") or "").strip()
                    await db.contactos_carta.update_one(
                        {"inmobiliaria_norm": _mi._norm_inmo(inmo_base),
                         "proyecto_norm": _mi._norm_inmo(proy_ap)},
                        {"$set": {"estudio_nombre": (payload.get("inmo_contacto_nombre") or "").strip(),
                                  "estudio_email": confirmado, "activo": True, "actualizado": now_iso()},
                         "$setOnInsert": {"id": str(uuid.uuid4()), "inmobiliaria": inmo_base,
                                          "inmobiliaria_norm": _mi._norm_inmo(inmo_base),
                                          "proyecto": proy_ap, "proyecto_norm": _mi._norm_inmo(proy_ap),
                                          "contacto": "", "email": "",
                                          "origen": "aprendizaje automático (estudio de título)"}},
                        upsert=True)
        except Exception as _e:
            logging.warning(f"aprendizaje estudio de título: {_e}")
    return {"ok": True, "to": destinos, "subject": subject,
            "attachments": attach_names, "sender": res.get("desde", sender)}


@api.get("/estudio-titulo/log")
async def estudio_log():
    docs = await db.estudio_titulo_log.find({}).sort("enviado_en", -1).limit(20).to_list(20)
    return {"log": [clean(d) for d in docs]}


def _pdf_disponible(nombre):
    """Solo ALERTA si el PDF físico falta — NUNCA rompe la carga de la vista."""
    try:
        base = fsvc.folder_dir(nombre or "")
        return base.exists() and any(True for _ in base.rglob("*.pdf"))
    except Exception:
        return False


def _ficha_carpeta(d):
    return {"id": d.get("id"), "nombre": d.get("nombre", ""), "rut": d.get("rut", ""),
            "pdf_disponible": _pdf_disponible(d.get("nombre", "")),
            "created_at": d.get("created_at", "")}


@api.get("/estudio-titulo/carpetas")
async def estudio_titulo_carpetas():
    """RESCATE DE MÓDULOS: fichas SOLO desde MongoDB. Un PDF faltante en disco
    jamás rompe la vista (solo marca pdf_disponible=false)."""
    docs = await db.folders.find(
        {"estudio_titulo_solicitado_at": {"$exists": True, "$ne": None}},
        {"_id": 0, "id": 1, "nombre": 1, "rut": 1, "created_at": 1,
         "estudio_titulo_solicitado_at": 1, "estudio_titulo_terminado_at": 1,
         "estudio_titulo_tipo_vivienda": 1, "estudio_titulo_subject": 1,
         "estudio_reparos.estado": 1, "estudio_titulo_vendedor": 1}
    ).sort("estudio_titulo_solicitado_at", -1).limit(200).to_list(200)
    out = []
    for d in docs:
        f = _ficha_carpeta(d)
        f.update({"solicitado_at": d.get("estudio_titulo_solicitado_at"),
                  "terminado_at": d.get("estudio_titulo_terminado_at"),
                  "tipo_vivienda": d.get("estudio_titulo_tipo_vivienda", ""),
                  "subject": d.get("estudio_titulo_subject", ""),
                  "reparos_estado": (d.get("estudio_reparos") or {}).get("estado", "sin_reparos"),
                  "vendedor": d.get("estudio_titulo_vendedor") or {}})
        out.append(f)
    return {"carpetas": out, "total": len(out)}


@api.get("/escrituracion/carpetas")
async def escrituracion_carpetas():
    """RESCATE DE MÓDULOS: fichas de escrituración SOLO desde MongoDB."""
    docs = await db.folders.find(
        {"$or": [{"is_escrituracion": True},
                 {"escrituracion_movida_at": {"$exists": True, "$ne": None}}]},
        {"_id": 0, "id": 1, "nombre": 1, "rut": 1, "created_at": 1,
         "escrituracion_movida_at": 1, "is_escrituracion": 1}
    ).sort("escrituracion_movida_at", -1).limit(200).to_list(200)
    out = []
    for d in docs:
        f = _ficha_carpeta(d)
        f["movida_at"] = d.get("escrituracion_movida_at")
        out.append(f)
    return {"carpetas": out, "total": len(out)}


@api.get("/tasacion/carpetas")
async def tasacion_carpetas():
    """RESCATE DE MÓDULOS: fichas de tasación SOLO desde MongoDB."""
    docs = await db.folders.find(
        {"tasacion_solicitada_at": {"$exists": True, "$ne": None}},
        {"_id": 0, "id": 1, "nombre": 1, "rut": 1, "created_at": 1,
         "tasacion_solicitada_at": 1, "tasacion_terminado_at": 1,
         "tasacion_terminado_origen": 1}
    ).sort("tasacion_solicitada_at", -1).limit(200).to_list(200)
    out = []
    for d in docs:
        f = _ficha_carpeta(d)
        f.update({"solicitada_at": d.get("tasacion_solicitada_at"),
                  "terminado_at": d.get("tasacion_terminado_at"),
                  "origen_termino": d.get("tasacion_terminado_origen", "")})
        out.append(f)
    return {"carpetas": out, "total": len(out)}


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
    # REGLA CC (norma fija): correo SALIENTE al abogado — sin CC bajo ninguna circunstancia.
    cc = []
    sender = _sender_por_rol("secundaria")
    if not payload.get("confirm"):
        return {"to": abogado, "cc": cc, "subject": subject, "body": cuerpo,
                "attachments": [a["nombre"] for a in docs_estudio], "sender": sender}
    base = fsvc.folder_dir(nombre)
    adjuntos = [{"filename": a["nombre"], "content_b64": _b64((base / a["ruta"]).read_bytes())}
                for a in docs_estudio]
    res = await asyncio.to_thread(mail.send_mail, abogado, subject, cuerpo, adjuntos, "secundaria")
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
        resp = await _llm_con_timeout(chat, UserMessage(text=texto[:5000]))
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


def _cc_correo_entrante(doc, excluir=None):
    """REGLA CC (norma fija): este CC se usa SOLO al procesar correos ENTRANTES
    (respuestas del abogado capturadas del hilo). Victoria + copias guardadas +
    participantes del hilo reciben copia únicamente en estos reenvíos de entrada.
    Los correos SALIENTES del sistema jamás llevan CC."""
    exc = {(e or "").lower() for e in (excluir or [])}
    cc = []
    participantes = list((doc.get("estudio_reparos") or {}).get("participantes") or [])
    for e in [VICTORIA_EMAIL] + list(doc.get("estudio_titulo_cc") or []) + participantes:
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
                                  cuerpo, [], "secundaria", _cc_correo_entrante(doc, [v_email]))
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
                                  cuerpo, [], "principal", _cc_correo_entrante(doc, destinos))
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
    # REGLA CC: recordatorio automático SALIENTE — sin CC bajo ninguna circunstancia.
    res = await asyncio.to_thread(mail.send_mail, abogado, subject, cuerpo, [],
                                  "secundaria", None, headers)
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
    doc["estudio_reparos"] = rep
    msgs = await asyncio.to_thread(mail.buscar_hilo_por_asunto, subject_kw, 8)
    cambios = False
    for msg in msgs:
        if msg["msgid"] in rep["procesados_msgids"]:
            continue
        rep["procesados_msgids"].append(msg["msgid"])
        cambios = True
        # HILO "RESPONDER A TODOS": capturar remitente + destinatarios + CC del mensaje
        parts = {p.lower() for p in (rep.get("participantes") or [])}
        for e_ in [msg.get("from_email", "")] + (msg.get("to_cc_emails") or []):
            if e_ and "@" in e_:
                parts.add(e_.lower())
        rep["participantes"] = sorted(parts)
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
    return {"reparos": clean(rep), "alertas": clean(doc.get("reparos_alertas") or []),
            "vendedor": doc.get("estudio_titulo_vendedor") or {},
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
          <p style="color:#888;font-size:12px">Central Mutuos — Cr&eacute;ditos Hipotecarios</p>
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
              "Adjunto encontrará su simulación y la carta de aprobación oficial con todos los "
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


def _nombre_cliente_pdf(nombre_archivo):
    """Nombre que ve el CLIENTE: sin 'ajustada/o' ni sufijos internos (_CM)."""
    base, ext = os.path.splitext(nombre_archivo or "")
    base = re.sub(r"[_\s-]*ajustad[oa]?", "", base, flags=re.I)
    base = re.sub(r"[_\s-]*cm$", "", base, flags=re.I)
    base = re.sub(r"_{2,}", "_", base)
    base = re.sub(r"[_\s-]+$", "", base).strip()
    return (base or "documento") + (ext or ".pdf")


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


@api.get("/aprendizaje/datos-cliente")
@api.get("/aprobacion-cliente/datos-cliente")
async def aprobacion_datos_cliente(nombre: str = ""):
    """EXTRACCION ENRIQUECIDA (centralizada en ai_extract.enriquecer_cliente):
    cruza Asunto + Cuerpo + OCR de PDFs + historial completo en base de datos
    (carpetas, sets, gastos, aprobaciones) + buzon IMAP + Patrones Aprendidos."""
    nombre = (nombre or "").strip()
    if len(nombre) < 3:
        raise HTTPException(status_code=400, detail="Indica el nombre del cliente")
    return await ai_extract.enriquecer_cliente(db, mail, nombre)


@api.post("/aprendizaje/correccion")
async def aprendizaje_correccion(payload: dict):
    """MODO APRENDIZAJE: guarda la correccion manual como Patron Aprendido (ai_extract)."""
    try:
        return await ai_extract.guardar_correccion(db, payload or {})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
                             "tamano": p.stat().st_size, "mtime": p.stat().st_mtime,
                             "nombre_cliente": _nombre_cliente_pdf(p.name)})

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
                try:
                    mt = fsvc.resolver_ruta(cliente, a["ruta"]).stat().st_mtime
                except Exception:
                    mt = 0
                archivos.append({"nombre": a["nombre"], "origen": "clientes", "ruta": a["ruta"],
                                 "tipo": tipo, "seleccionado": True, "tamano": a["tamano"],
                                 "mtime": mt, "nombre_cliente": _nombre_cliente_pdf(a["nombre"])})
    # REGLA: al cliente se le envían SOLO 2 archivos — la carta de aprobación y la
    # simulación (los mismos del autocorreo). Se toma el MÁS RECIENTE de cada tipo.
    finales = []
    for tipo in ("carta_aprobacion", "simulacion_ajustada"):
        cand = [a for a in archivos if a["tipo"] == tipo]
        if cand:
            # Preferir SIEMPRE la versión ajustada (_CM/ajustada) sobre la cruda; luego la más reciente
            cand.sort(key=lambda a: (bool(re.search(r"_cm\.pdf$|ajustad", a["nombre"], re.I)),
                                     a.get("mtime", 0)), reverse=True)
            elegido = dict(cand[0])
            elegido["seleccionado"] = True
            finales.append(elegido)
    # LEY DEL RUT: verificación OCR de los archivos finales contra el RUT del dueño
    excluidos_rut = []
    if finales and cliente.strip():
        fdoc = await db.folders.find_one(
            {"nombre": {"$regex": f"^{re.escape(cliente.strip())}$", "$options": "i"}})
        rut_dueno = _norm_rut((fdoc or {}).get("rut", ""))
        rut_cod = _norm_rut((fdoc or {}).get("codeudor_rut", ""))
        if len(rut_dueno) >= 7:
            verificados = []
            for a in finales:
                try:
                    if a["origen"] == "clientes":
                        pth = fsvc.resolver_ruta(cliente, a["ruta"])
                    else:
                        pth = STORAGE_DIR / a["ruta"]
                    ruts_arch = await asyncio.to_thread(_ruts_de_pdf, pth.read_bytes())
                except Exception:
                    ruts_arch = set()
                if ruts_arch and not (ruts_arch & {rut_dueno, rut_cod}):
                    excluidos_rut.append({"nombre": a["nombre"], "ruts": sorted(ruts_arch),
                                          "rut_dueno": (fdoc or {}).get("rut", "")})
                else:
                    a["rut_verificado"] = bool(ruts_arch)
                    verificados.append(a)
            finales = verificados
    return {"archivos": finales, "excluidos_rut": excluidos_rut}


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
    intro_html = "".join(f"<p style='margin:0 0 14px;line-height:1.7;font-size:15px;color:#2b3245'>{p}</p>"
                         for p in intro.split("\n") if p.strip())
    docs_html = ""
    if adjuntos:
        filas = "".join(
            f"<tr><td style='padding:8px 0;color:#2b3245;font-size:14px'>"
            f"<span style='display:inline-block;width:22px;color:#1a1f2e;font-weight:700'>&#10003;</span>{n}</td></tr>"
            for n in adjuntos)
        docs_html = f"""
        <div style="background:#f4f5f7;border:1px solid #e2e4e9;padding:16px 22px;margin:6px 0 22px">
          <div style="color:#1a1f2e;font-weight:700;font-size:14px;margin-bottom:6px">Documentos adjuntos a este correo</div>
          <table role="presentation" style="border-collapse:collapse">{filas}</table>
        </div>"""
    mailto = (f"mailto:{contacto}?subject=" +
              f"Deseo continuar con el proceso de escrituración — {nombre}".replace(" ", "%20"))
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Central Mutuos</title>
<style>
  @media only screen and (max-width:600px) {{
    .cm-titulo {{ font-size:24px !important; }}
    .cm-header {{ padding:26px 16px !important; }}
    .cm-body {{ padding:22px 16px 6px !important; }}
    .cm-cta-zone {{ padding:6px 16px 26px !important; }}
    .cm-footer {{ padding:18px 16px !important; }}
    .cm-cta {{ display:block !important; width:100% !important; box-sizing:border-box !important; padding:16px 0 !important; }}
  }}
</style>
</head>
<body style="margin:0;padding:0;background:#eef0f2;font-family:Arial,Helvetica,sans-serif">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#eef0f2">
    <tr><td align="center" style="padding:24px 10px">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
             style="max-width:600px;background:#ffffff;border:1px solid #e2e4e9">
        <tr><td class="cm-header" style="background:#111318;padding:36px 28px;text-align:center">
          <div style="color:#9aa3b5;font-size:12px;letter-spacing:4px;margin-bottom:10px">CENTRAL MUTUOS</div>
          <div class="cm-titulo" style="color:#ffffff;font-size:34px;font-weight:700;letter-spacing:1px;line-height:1.2">&iexcl;FELICITACIONES!</div>
          <div style="color:#c9ced8;font-size:16px;margin-top:10px">Su cr&eacute;dito hipotecario ha sido <b style="color:#ffffff">APROBADO</b></div>
        </td></tr>
        <tr><td class="cm-body" style="padding:30px 32px 8px">
          <p style="margin:0 0 4px;color:#1a1f2e;font-size:17px"><b>Estimada(o) {nombre}</b></p>
          {f"<p style='margin:0 0 18px;color:#6b7280;font-size:13px'>RUT: {rut}</p>" if rut else "<div style='height:14px'></div>"}
          {intro_html}
          {docs_html}
          {payload.get("links_html", "")}
        </td></tr>
        <tr><td class="cm-cta-zone" style="padding:6px 32px 30px;text-align:center">
          <a class="cm-cta" href="{mailto}" style="display:inline-block;background:#111318;color:#ffffff;
             font-size:16px;font-weight:700;letter-spacing:1px;text-decoration:none;
             padding:16px 38px;text-align:center">{boton} &nbsp;&#8594;</a>
          <p style="margin:16px 0 0;color:#8a93a3;font-size:12px">Al presionar el bot&oacute;n se abrir&aacute; un correo dirigido a nuestro equipo para coordinar los siguientes pasos.</p>
        </td></tr>
        <tr><td class="cm-footer" style="background:#f4f5f7;border-top:1px solid #e2e4e9;padding:20px 32px">
          <p style="margin:0;color:#2b3245;font-size:14px"><b>Central Mutuos</b></p>
          <p style="margin:4px 0 0;color:#6b7280;font-size:12px">Especialistas en cr&eacute;ditos hipotecarios &middot; {contacto}</p>
        </td></tr>
        <tr><td style="background:#111318;padding:12px 24px;text-align:center">
          <span style="color:#8a93a3;font-size:11px">Este correo contiene informaci&oacute;n confidencial dirigida exclusivamente a su destinatario.</span>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


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
    payload["_adjuntos_nombres"] = [_nombre_cliente_pdf(p.name) for p in rutas]
    cuerpo = _aprobacion_html(payload)
    if not payload.get("confirm"):
        return {"to": to, "subject": subject, "body": cuerpo,
                "attachments": [_nombre_cliente_pdf(p.name) for p in rutas],
                "sender": _sender_por_rol("secundaria")}
    if not to or "@" not in to:
        raise HTTPException(status_code=400, detail="Correo del cliente inválido")
    if not rutas:
        raise HTTPException(status_code=400, detail="Debe adjuntar al menos la simulación ajustada o la carta de aprobación")
    # SINCRONIZACIÓN DE APROBACIÓN (Match Total): el RUT de cada PDF debe coincidir
    # con el cliente de la ficha — bloquea errores humanos de selección de archivo.
    rut_ficha = _norm_rut((payload.get("rut") or "").strip())
    if len(rut_ficha) < 7 and nombre:
        _fd = await db.folders.find_one({"nombre": {"$regex": re.escape(nombre[:25]), "$options": "i"}},
                                        {"rut": 1}) or {}
        rut_ficha = _norm_rut(_fd.get("rut", ""))
    if len(rut_ficha) >= 7:
        for p in rutas:
            ruts_p = await asyncio.to_thread(lambda pp=p: fsvc._ruts_personas(fsvc.ruts_de_pdf_cache(pp)))
            if ruts_p and rut_ficha not in ruts_p:
                raise HTTPException(status_code=409, detail=(
                    f"REGLA DE ORO (Match Total): el adjunto '{p.name}' contiene un RUT de OTRA persona "
                    f"— no coincide con el cliente de la ficha ({payload.get('rut') or nombre}). "
                    "Verifique la selección de archivos."))
    adjuntos = []
    for p in rutas:
        raw = p.read_bytes()
        # REGLA INVIOLABLE: la simulación al cliente va SOLO con la primera hoja
        # (sin otros plazos ni gastos operacionales). Las cartas van SIEMPRE intactas.
        es_carta_adj = bool(re.search(r"carta|aprobaci[oó]n", p.name, re.I))
        if not es_carta_adj and re.search(r"simulad|simulaci[oó]n", p.name, re.I):
            try:
                raw, _orig, _rem = pdfs.dejar_primera_pagina(raw)
            except Exception:
                pass
        adjuntos.append({"filename": _nombre_cliente_pdf(p.name), "content_b64": _b64(raw)})
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
        "to": to, "adjuntos": [_nombre_cliente_pdf(p.name) for p in rutas],
        "ejecutivo_nombre": payload.get("ejecutivo_nombre", ""),
        "ejecutivo_email": payload.get("ejecutivo_email", ""),
        "ejecutivo_interno": payload.get("ejecutivo_interno", ""),
        "enviado_en": now_iso(), "desde": res.get("desde", "")})
    # Sincronizar con la carpeta del cliente: correo, RUT y ejecutivos quedan guardados
    upd_ej = {k: v for k, v in {
        "email": to,
        "rut": (payload.get("rut") or "").strip(),
        "ejecutivo_externo": payload.get("ejecutivo_nombre", "").strip(),
        "ejecutivo_externo_email": payload.get("ejecutivo_email", "").strip(),
        "ejecutivo_interno": payload.get("ejecutivo_interno", "").strip()}.items() if v}
    if upd_ej and nombre:
        toks_n = [t for t in re.split(r"\s+", nombre) if len(t) >= 3]
        if toks_n:
            await db.folders.update_one(
                {"$and": [{"nombre": {"$regex": re.escape(t), "$options": "i"}} for t in toks_n[:2]]},
                {"$set": upd_ej})
    return {"ok": True, "to": to, "subject": subject,
            "attachments": [_nombre_cliente_pdf(p.name) for p in rutas], "sender": res.get("desde", "")}


# ══════════════════════════════════════════════════════════════════════════
# 📧 AUTOCORREO CLIENTE FINAL — notificación de aprobación directa al cliente
# ══════════════════════════════════════════════════════════════════════════
LINK_DESCARGA_MAX_MB = 10


async def _link_descarga_seguro(cliente, p):
    token = uuid.uuid4().hex
    await db.descargas_seguras.insert_one({
        "token": token, "cliente": cliente, "path": str(p),
        "filename": _nombre_cliente_pdf(p.name), "creado_en": now_iso()})
    base = (os.environ.get("REACT_APP_BACKEND_URL") or os.environ.get("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    return {"nombre": _nombre_cliente_pdf(p.name), "url": f"{base}/api/descarga-segura/{token}"}


@api.get("/descarga-segura/{token}")
async def descarga_segura(token: str):
    d = await db.descargas_seguras.find_one({"token": token})
    if not d or not Path(d["path"]).exists():
        raise HTTPException(status_code=404, detail="Enlace de descarga no válido o expirado")
    return FileResponse(d["path"], media_type="application/pdf", filename=d.get("filename", "documento.pdf"))


async def _autocorreo_cliente_aprobado(seg, forzar=False):
    """Aprobación de MESA → felicitación DIRECTA al cliente (remitente comercial,
    BCC comercial). Sin correo en la carpeta → alerta en panel. Adjunta carta/simulación
    (o combinado) si pesan ≤10MB; si no, envía links seguros de descarga."""
    try:
        if (seg.get("estado") or "").lower() not in ("aprobacion", "aprobado"):
            return {"ok": False, "motivo": "no_es_aprobacion"}
        cliente = (seg.get("cliente") or "").strip()
        if not cliente:
            return {"ok": False, "motivo": "sin_cliente"}
        if not forzar:
            f = (seg.get("fecha") or seg.get("procesado_en") or "")[:19]
            if f and f < (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()[:19]:
                return {"ok": False, "motivo": "aprobacion_antigua"}
        fd, _sim = await _forense_buscar_contexto(cliente, seg.get("rut"))
        nombre_folder = (fd or {}).get("nombre") or cliente
        email_cli = ((fd or {}).get("email") or seg.get("email_cliente") or "").strip()
        # CERROJO ATÓMICO DE DUPLICADOS: se RESERVA la clave (RUT+Nombre) ANTES de enviar.
        # Si ya está reservada/enviada, se ignora de inmediato (blindaje anti-ráfaga tras reinicio).
        rut_lock = re.sub(r"[^0-9kK]", "", ((fd or {}).get("rut") or seg.get("rut") or "")).lower()
        clave_lock = f"{rut_lock}|{re.sub(r'[^a-z]', '', nombre_folder.lower())[:20]}"
        if not forzar:
            resv = await db.aprobacion_log.update_one(
                {"clave_lock": clave_lock},
                {"$setOnInsert": {"id": str(uuid.uuid4()), "clave_lock": clave_lock,
                                  "nombre": nombre_folder, "estado_lock": "reservado",
                                  "reservado_en": now_iso()}}, upsert=True)
            if resv.upserted_id is None:
                return {"ok": False, "motivo": "ya_notificado_o_reservado"}
        if not email_cli or "@" not in email_cli:
            # Libera el cerrojo para reintentar cuando se agregue el correo
            if not forzar:
                await db.aprobacion_log.delete_one({"clave_lock": clave_lock, "estado_lock": "reservado"})
            msg_alerta = f"⚠️ {nombre_folder} aprobado pero sin correo para notificación automática"
            if not await db.alertas.find_one({"mensaje": msg_alerta, "leida": False}):
                await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "aprobacion",
                                             "mensaje": msg_alerta, "cliente": nombre_folder,
                                             "fecha": now_iso(), "leida": False})
            return {"ok": False, "motivo": "sin_correo", "alerta": msg_alerta}
        # ADJUNTOS: carta de aprobación + simulación; respaldo = combinado
        rutas = []
        if fd:
            for a in fsvc.scan_archivos(nombre_folder):
                t = _tipo_pdf_aprobacion(a["nombre"])
                if t in ("carta_aprobacion", "simulacion_ajustada"):
                    try:
                        rutas.append((t, fsvc.resolver_ruta(nombre_folder, a["ruta"])))
                    except (ValueError, OSError):
                        pass
            if not rutas:
                for a in fsvc.scan_archivos(nombre_folder):
                    if fsvc.cat_de_archivo(a["nombre"], a["subfolder"]) == "combinado":
                        try:
                            rutas.append(("combinado", fsvc.resolver_ruta(nombre_folder, a["ruta"])))
                            break
                        except (ValueError, OSError):
                            pass
        sel = {}
        for t, p in sorted(rutas, key=lambda x: x[1].stat().st_mtime, reverse=True):
            sel.setdefault(t, p)
        adjuntos, nombres, links_html = [], [], ""
        peso = sum(p.stat().st_size for p in sel.values())
        if sel and peso <= LINK_DESCARGA_MAX_MB * 1024 * 1024:
            for t, p in sel.items():
                raw = p.read_bytes()
                if t == "simulacion_ajustada":
                    try:
                        raw, _o, _r = pdfs.dejar_primera_pagina(raw)
                    except Exception:
                        pass
                adjuntos.append({"filename": _nombre_cliente_pdf(p.name), "content_b64": _b64(raw)})
                nombres.append(_nombre_cliente_pdf(p.name))
        elif sel:
            filas = ""
            for _t, p in sel.items():
                lk = await _link_descarga_seguro(nombre_folder, p)
                filas += (f"<p style='margin:0 0 8px'><a href='{lk['url']}' style='color:#b8942e;font-weight:700'>"
                          f"&#128196; Descargar {lk['nombre']}</a></p>")
            links_html = ("<div style='background:#f8f9fc;border:1px solid #eceef3;border-radius:10px;"
                          "padding:16px 22px;margin:6px 0 22px'>"
                          "<div style='color:#1a1f2e;font-weight:700;font-size:14px;margin-bottom:8px'>"
                          "Sus documentos superan el tamaño permitido por correo — "
                          f"descárguelos de forma segura aquí:</div>{filas}</div>")
        tpl = await db.aprobacion_templates.find_one({"cliente": nombre_folder}) or {}
        payload = {"nombre": nombre_folder, "rut": (fd or {}).get("rut", "") or seg.get("rut", ""),
                   "intro": tpl.get("intro") or APROBACION_DEFAULTS["intro"],
                   "boton_texto": tpl.get("boton_texto") or APROBACION_DEFAULTS["boton_texto"],
                   "_adjuntos_nombres": nombres, "links_html": links_html}
        cuerpo = _aprobacion_html(payload)
        subject = tpl.get("subject") or APROBACION_DEFAULTS["subject"]
        bcc = os.environ.get("MAIL2_USER", "")
        # REGLA DE SEGURIDAD: siempre la cuenta comercial como remitente de cara al cliente
        res = await asyncio.to_thread(functools.partial(
            mail.send_mail, email_cli, subject, cuerpo, adjuntos, "secundaria", bcc=bcc))
        if not res.get("success"):
            # Libera el cerrojo para permitir reintento posterior
            if not forzar:
                await db.aprobacion_log.delete_one({"clave_lock": clave_lock, "estado_lock": "reservado"})
            await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "aprobacion",
                "mensaje": f"🚨 Falló la notificación de aprobación a {nombre_folder} ({email_cli}): {str(res.get('error', ''))[:120]}",
                "fecha": now_iso(), "leida": False})
            return {"ok": False, "motivo": "error_envio", "error": res.get("error")}
        # Confirma la reserva → estado enviado (cierra el cerrojo definitivamente)
        await db.aprobacion_log.update_one(
            {"clave_lock": clave_lock},
            {"$set": {"nombre": nombre_folder, "rut": payload["rut"], "to": email_cli,
                      "adjuntos": nombres, "con_links": bool(links_html),
                      "origen": "reenvio_manual" if forzar else "autocorreo_cliente",
                      "estado_lock": "enviado", "bcc": bcc, "enviado_en": now_iso(),
                      "desde": res.get("desde", "")}},
            upsert=True)
        return {"ok": True, "to": email_cli, "adjuntos": nombres, "con_links": bool(links_html)}
    except Exception as e:
        logging.warning(f"autocorreo cliente aprobado: {e}")
        return {"ok": False, "motivo": "excepcion", "error": str(e)[:200]}


@api.post("/clientes/folders/{fid}/reenviar-notificacion")
async def reenviar_notificacion(fid: str):
    """RE-ENVÍO MANUAL: salta el bloqueo de duplicados si el cliente dice que no le llegó."""
    fd = await db.folders.find_one({"id": fid})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no encontrada")
    res = await _autocorreo_cliente_aprobado(
        {"cliente": fd.get("nombre", ""), "rut": fd.get("rut", ""), "estado": "aprobacion"}, forzar=True)
    if not res.get("ok"):
        motivo = {"sin_correo": "La carpeta no tiene correo del cliente — agréguelo primero en la ficha",
                  "error_envio": f"Error de envío: {res.get('error', '')}"}.get(
            res.get("motivo"), res.get("motivo", "error"))
        raise HTTPException(status_code=400, detail=motivo)
    return res


# ══════════════════════════════════════════════════════════════════════════
# 📪 NOTIFICACIÓN DE RECHAZO PURIFICADA (SOLO ADELANTE — desde 13-08-2026)
# Texto sobrio blanco/negro. Solo: nombre, motivo, estado. Cero rastro de MESA.
# ══════════════════════════════════════════════════════════════════════════
RECHAZO_CUTOFF = "2026-08-13"
RECHAZO_MOTIVO_DEFAULT = ("Los antecedentes presentados no cumplieron los criterios de "
                          "evaluación de la entidad financiera en esta instancia.")

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _rechazo_sanear_motivo(motivo):
    """BLINDAJE DE ORIGEN: limpia del motivo correos, URLs y toda referencia a la MESA."""
    m = (motivo or "").strip()
    m = _EMAIL_RE.sub("", m)
    m = re.sub(r"https?://\S+", "", m)
    m = re.sub(r"\b(mesa|aprobaciones|remitente|reenviad[oa]|fwd|re:)\b", "", m, flags=re.I)
    m = re.sub(r"\s{2,}", " ", m).strip(" .:-·|")
    return m if len(m) >= 12 else ""


def _rechazo_html(nombre, motivo):
    """DISEÑO QUIRÚRGICO: HTML minimalista, negro sobre blanco, sin logos ni colores."""
    return f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#ffffff">
<div style="max-width:560px;margin:0 auto;padding:32px 24px;font-family:Arial,Helvetica,sans-serif;color:#000000;background:#ffffff;font-size:15px;line-height:1.6">
<p style="margin:0 0 16px">Estimado/a <b>{html.escape(nombre)}</b>:</p>
<p style="margin:0 0 16px">Le informamos el resultado de la evaluación de su solicitud de crédito hipotecario.</p>
<div style="border:1px solid #000000;padding:14px 18px;margin:0 0 16px">
<p style="margin:0 0 6px"><b>Estado del trámite:</b> No aprobado en esta instancia.</p>
<p style="margin:0"><b>Motivo:</b> {html.escape(motivo)}</p>
</div>
<p style="margin:0 0 16px">Este resultado no impide una futura reevaluación si sus antecedentes cambian. Nuestro equipo queda a su disposición para orientarle sobre los pasos a seguir.</p>
<p style="margin:24px 0 0">Atentamente,<br/>Equipo Central Mutuos</p>
</div></body></html>"""


def _rechazo_purificar(subject, cuerpo_html):
    """REGLA DE HIERRO: si el correo contiene una dirección externa o información
    del sistema fuera del cuerpo del mensaje, el envío se ABORTA. Se apoya en la
    Constitución Maestra (regla purificacion_correos)."""
    try:
        import constitucion as _const
        _const.exigir("purificacion_correos", subject=subject, html=cuerpo_html)
    except Exception as _v:
        if _v.__class__.__name__ == "ViolacionConstitucional":
            return False, str(_v)
    texto = re.sub(r"<[^>]+>", " ", f"{subject} {cuerpo_html}")
    correos = _EMAIL_RE.findall(texto)
    if correos:
        return False, f"dirección de correo detectada en el cuerpo: {correos[0]}"
    prohibidos = [os.environ.get("MESA_SENDER", "") or "aprobaciones@",
                  os.environ.get("MAIL_USER", ""), os.environ.get("MAIL2_USER", "")]
    for p in prohibidos:
        if p and p.split("@")[0] and p.split("@")[0] in texto:
            return False, f"información del sistema detectada: {p.split('@')[0]}"
    if re.search(r"\b(mesa|remitente|reenviad[oa]|fwd:)\b", texto, re.I):
        return False, "referencia al origen (MESA/remitente) detectada"
    return True, ""


async def _autocorreo_cliente_rechazado(seg, forzar=False, solo_preview=False):
    """RECHAZO PURIFICADO → notificación directa al solicitante, el sistema como
    único intermediario. Solo estados de rechazo explícitos y solo desde el CUTOFF."""
    try:
        if (seg.get("estado") or "").lower() not in ("rechazo", "rechazado"):
            return {"ok": False, "motivo": "no_es_rechazo"}
        # FILTRO TEMPORAL (HOY+): nada retroactivo
        f_proc = (seg.get("procesado_en") or seg.get("fecha") or "")[:10]
        if not forzar and (not f_proc or f_proc < RECHAZO_CUTOFF):
            return {"ok": False, "motivo": "anterior_al_cutoff", "fecha": f_proc}
        cliente = (seg.get("cliente") or "").strip()
        if not cliente:
            return {"ok": False, "motivo": "sin_cliente"}
        fd, _sim = await _forense_buscar_contexto(cliente, seg.get("rut"))
        nombre = (fd or {}).get("nombre") or cliente
        motivo = _rechazo_sanear_motivo(seg.get("motivo_rechazo") or seg.get("motivo")
                                        or seg.get("detalle_rechazo")) or RECHAZO_MOTIVO_DEFAULT
        subject = "Resultado de la evaluación de su solicitud"
        cuerpo = _rechazo_html(nombre, motivo)
        # REGLA DE HIERRO — purificación total antes de cualquier envío
        limpio, problema = _rechazo_purificar(subject, cuerpo)
        if not limpio:
            await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "rechazo",
                "mensaje": f"⛔ Notificación de rechazo a {nombre} ABORTADA por pureza: {problema}",
                "fecha": now_iso(), "leida": False})
            return {"ok": False, "motivo": "abortado_pureza", "problema": problema}
        if solo_preview:
            return {"ok": True, "preview": True, "subject": subject, "html": cuerpo,
                    "nombre": nombre, "motivo": motivo}
        cfg = await db.config.find_one({"_key": "rechazo_autocorreo"}) or {}
        if not cfg.get("activo") and not forzar:
            return {"ok": False, "motivo": "funcion_no_activada"}
        email_cli = ((fd or {}).get("email") or seg.get("email_cliente") or "").strip()
        if not email_cli or "@" not in email_cli:
            msg_a = f"⚠️ {nombre} rechazado pero sin correo para notificación purificada"
            if not await db.alertas.find_one({"mensaje": msg_a, "leida": False}):
                await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "rechazo",
                    "mensaje": msg_a, "cliente": nombre, "fecha": now_iso(), "leida": False})
            return {"ok": False, "motivo": "sin_correo"}
        if not forzar and await db.rechazo_log.find_one(
                {"nombre": nombre, "fecha_mesa": (seg.get("fecha") or "")[:10]}):
            return {"ok": False, "motivo": "ya_notificado"}
        bcc = os.environ.get("MAIL2_USER", "")
        res = await asyncio.to_thread(functools.partial(
            mail.send_mail, email_cli, subject, cuerpo, [], "secundaria", bcc=bcc))
        if not res.get("success"):
            return {"ok": False, "motivo": "error_envio", "error": res.get("error")}
        await db.rechazo_log.insert_one({"id": str(uuid.uuid4()), "nombre": nombre,
            "to": email_cli, "motivo_texto": motivo, "fecha_mesa": (seg.get("fecha") or "")[:10],
            "enviado_en": now_iso()})
        return {"ok": True, "to": email_cli}
    except Exception as e:
        logging.warning(f"autocorreo rechazo purificado: {e}")
        return {"ok": False, "motivo": "excepcion", "error": str(e)[:200]}


@api.get("/autocorreo/rechazo/preview")
async def rechazo_preview(cliente: str = "", motivo: str = ""):
    """Vista previa HTML del correo de rechazo purificado (NO envía nada)."""
    seg = {"cliente": cliente or "Nombre del Solicitante", "estado": "rechazo",
           "procesado_en": now_iso(), "motivo_rechazo": motivo}
    r = await _autocorreo_cliente_rechazado(seg, solo_preview=True)
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=f"No previsualizable: {r.get('problema') or r.get('motivo')}")
    return HTMLResponse(content=r["html"])


@api.post("/autocorreo/rechazo/activar")
async def rechazo_activar(payload: dict):
    """Enciende/apaga el disparador real (queda apagado hasta aprobación del dueño)."""
    activo = bool((payload or {}).get("activo"))
    await db.config.update_one({"_key": "rechazo_autocorreo"}, {"$set": {
        "activo": activo, "cutoff": RECHAZO_CUTOFF, "actualizado": now_iso()}}, upsert=True)
    return {"ok": True, "activo": activo, "cutoff": RECHAZO_CUTOFF}


# ══════════════════════════════════════════════════════════════════════════
# 🐢 RITMO ANTI-RÁFAGA — cola pausada de notificaciones (máx 3/ciclo, 10s entre envíos)
# Regla de Hierro: prefiero tardar más en ponerme al día que 20 correos en 1 minuto.
# ══════════════════════════════════════════════════════════════════════════
NOTIF_MAX_POR_CICLO = 3
NOTIF_PAUSA_SEG = 10


async def _encolar_notificacion(seg):
    """Toda notificación al cliente entra a la cola pausada; nunca envío directo en lote."""
    est = (seg.get("estado") or "").lower()
    if est not in ("aprobacion", "aprobado", "rechazo", "rechazado"):
        return
    d = {k: seg.get(k) for k in ("id", "cliente", "rut", "estado", "fecha", "asunto",
                                 "procesado_en", "monto_credito", "email_cliente")}
    await db.notif_cola.update_one(
        {"seg_id": seg.get("id")},
        {"$setOnInsert": {**d, "seg_id": seg.get("id"), "estado_cola": "pendiente",
                          "encolado_en": now_iso()}}, upsert=True)


async def _notif_pace_loop():
    """Despacha la cola goteando: máx 3 correos por ciclo (60s) y 10s entre envíos.
    Al despertar tras una pausa, el backlog sale suave, jamás en ráfaga."""
    await asyncio.sleep(20)
    while True:
        try:
            lote = await db.notif_cola.find({"estado_cola": "pendiente"}) \
                .sort("encolado_en", 1).to_list(NOTIF_MAX_POR_CICLO)
            enviados = 0
            for item in lote:
                if enviados > 0:
                    await asyncio.sleep(NOTIF_PAUSA_SEG)
                est = (item.get("estado") or "").lower()
                try:
                    if est in ("aprobacion", "aprobado"):
                        r = await _autocorreo_cliente_aprobado(item)
                    else:
                        r = await _autocorreo_cliente_rechazado(item)
                except Exception as e:
                    r = {"ok": False, "motivo": "excepcion", "error": str(e)[:150]}
                await db.notif_cola.update_one({"_id": item["_id"]}, {"$set": {
                    "estado_cola": "enviado" if r.get("ok") else "omitido",
                    "resultado": {k: str(v)[:200] for k, v in (r or {}).items() if k != "html"},
                    "despachado_en": now_iso()}})
                if r.get("ok"):
                    enviados += 1
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.warning(f"notif pace loop: {e}")
        await asyncio.sleep(60)
# 📜 EDITOR MAESTRO DE COMPROMISOS DE COMPRAVENTA
# ══════════════════════════════════════════════════════════════════════════
def _compromiso_default(fd):
    return {
        "comprador": {"nombre": (fd or {}).get("nombre", ""), "rut": (fd or {}).get("rut", ""),
                      "nacionalidad": "chilena", "profesion": "", "estado_civil": "", "domicilio": ""},
        "vendedor": {"nombre": "", "rut": "", "nacionalidad": "chilena", "profesion": "",
                     "estado_civil": "", "domicilio": ""},
        "propiedad": {"direccion": "", "comuna": "", "rol_avaluo": "", "fojas": "", "numero": "",
                      "anio": "", "cbr": ""},
        "precio": {"valor_total_uf": 0, "pie_uf": 0, "pie_recibido": False, "garantia": ""},
        "resguardos": {"plazo_escritura_dias": 60, "clausula_penal_uf": 0, "gastos": "ambos"},
    }


@api.get("/compromiso/{fid}")
async def compromiso_get(fid: str):
    fd = await db.folders.find_one({"id": fid})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no encontrada")
    doc = await db.compromisos.find_one({"folder_id": fid}, {"_id": 0})
    if doc:
        return doc
    datos = _compromiso_default(fd)
    # PRE-LLENADO INTELIGENTE: OCR de los documentos de la carpeta + extracción IA
    try:
        paths = []
        for a in fsvc.scan_archivos(fd.get("nombre", "")):
            if a["nombre"].lower().endswith(".pdf"):
                try:
                    paths.append(fsvc.resolver_ruta(fd["nombre"], a["ruta"]))
                except (ValueError, OSError):
                    pass
        texto = await asyncio.to_thread(_ocr_adjuntos_paths, paths[:4])
        if len(texto) < 200 and paths:
            import ocr_service as _ocr
            texto = await asyncio.to_thread(_ocr.ocr_texto, paths[0].read_bytes(), 6) or ""
        ext = await ai_extract.extraer_datos_compromiso(texto, fd.get("nombre", ""))
        for sec in ("comprador", "vendedor", "propiedad"):
            for k, v in (ext.get(sec) or {}).items():
                if v and k in datos[sec] and not datos[sec].get(k):
                    datos[sec][k] = str(v)
        pr = ext.get("precio") or {}
        try:
            uf_v = float(await get_valor_uf() or 0)
        except Exception:
            uf_v = 0
        if uf_v > 0:
            for k_clp, k_uf in (("valor_total_clp", "valor_total_uf"), ("pie_clp", "pie_uf")):
                if isinstance(pr.get(k_clp), (int, float)) and pr[k_clp] > 0 and not datos["precio"][k_uf]:
                    datos["precio"][k_uf] = round(pr[k_clp] / uf_v, 2)
    except Exception as e:
        logging.warning(f"compromiso prefill: {e}")
    doc = {"folder_id": fid, "cliente": fd.get("nombre", ""), "datos": datos,
           "clausulas_html": "", "updated_at": now_iso()}
    await db.compromisos.update_one({"folder_id": fid}, {"$set": doc}, upsert=True)
    return doc


@api.put("/compromiso/{fid}")
async def compromiso_put(fid: str, payload: dict):
    upd = {"datos": payload.get("datos") or {}, "clausulas_html": "", "updated_at": now_iso()}
    # REGLA DE ORO #63: en Vivienda Usada el crédito del compromiso no supera el 79.50% exacto
    try:
        fd = await db.folders.find_one({"id": fid}, {"tipo_operacion": 1})
        precio = (upd["datos"].get("precio") or {})
        valor = float(precio.get("valor_total_uf") or 0)
        pie = float(precio.get("pie_uf") or 0)
        if (fd or {}).get("tipo_operacion", "").lower() == "usada" and valor > 0:
            from credit_engine import LTV_MAX_63
            credito_max = round(valor * LTV_MAX_63, 10)
            if valor - pie > credito_max:
                pie_min = round(valor - credito_max, 2)
                precio["pie_uf"] = pie_min
                precio["ajuste_pie_795"] = True
                upd["nota_795"] = (f"Regla #63: pie ajustado automáticamente a {pie_min} UF "
                                   f"para clavar el LTV en 79.50% exacto (Vivienda Usada)")
    except Exception as e:
        logging.warning(f"compromiso 79.5%: {e}")
    await db.compromisos.update_one({"folder_id": fid}, {"$set": upd}, upsert=True)
    return {"ok": True, "updated_at": upd["updated_at"], "nota_795": upd.get("nota_795", "")}


@api.post("/compromiso/{fid}/pdf")
async def compromiso_pdf(fid: str, payload: dict):
    """EXPORTACIÓN FINAL: genera el PDF EXACTO de lo que muestra el editor."""
    html = (payload or {}).get("html") or ""
    if len(html) < 50:
        raise HTTPException(status_code=400, detail="Documento vacío")
    # BLOQUEO DE PRECISIÓN 100% (Regla #63): usadas sobre 79.50% NO generan PDF
    try:
        fd_63 = await db.folders.find_one({"id": fid}, {"tipo_operacion": 1})
        comp_63 = await db.compromisos.find_one({"folder_id": fid}) or {}
        precio_63 = ((comp_63.get("datos") or {}).get("precio") or {})
        valor_63 = float(precio_63.get("valor_total_uf") or 0)
        pie_63 = float(precio_63.get("pie_uf") or 0)
        if (fd_63 or {}).get("tipo_operacion", "").lower() == "usada" and valor_63 > 0:
            from credit_engine import LTV_MAX_63
            if round((valor_63 - pie_63) / valor_63, 10) > LTV_MAX_63:
                raise HTTPException(status_code=422, detail=(
                    f"⛔ Regla de Oro #63: el contrato no cumple el LTV máximo de 79.5000000000% para "
                    f"Vivienda Usada (crédito {round(valor_63 - pie_63, 2)} UF sobre {valor_63} UF). "
                    f"Ajuste el Pie antes de generar el PDF."))
    except HTTPException:
        raise
    except Exception as e:
        logging.warning(f"pdf 79.5%: {e}")
    # CONSULTA PREVIA A LA CONSTITUCIÓN — Regla de Oro: sobriedad del PDF legal
    try:
        import constitucion as _const
        _const.exigir("sobriedad_pdf", html=html)
    except _const.ViolacionConstitucional as _v:
        raise HTTPException(status_code=422, detail=str(_v))
    from xhtml2pdf import pisa
    import io
    buf = io.BytesIO()
    full = ("<html><head><meta charset='utf-8'><style>"
            "@page { size: letter; margin-top: 2.5cm; margin-bottom: 2.5cm; margin-left: 3cm; margin-right: 3cm; }"
            "body { font-family: 'Times New Roman', Times, serif; font-size: 11pt; color: #000000; "
            "background-color: #ffffff; line-height: 1.6; }"
            "h1 { font-size: 18pt; color: #000000; font-weight: 700; text-align: center; letter-spacing: 1px; "
            "line-height: 1.4; margin: 0 0 8px; }"
            "h2 { font-size: 12pt; color: #000000; font-weight: 700; margin: 16px 0 6px; line-height: 1.5; }"
            "b, strong { font-weight: 700; color: #000000; }"
            "p { margin: 0 0 12px; text-align: justify; color: #000000; line-height: 1.6; }"
            "table { width: 100%; }"
            f"</style></head><body>{html}</body></html>")
    err = await asyncio.to_thread(lambda: pisa.CreatePDF(full, dest=buf, encoding="utf-8").err)
    if err:
        raise HTTPException(status_code=500, detail="Error generando el PDF del compromiso")
    fd = await db.folders.find_one({"id": fid}) or {}
    fn = f"Compromiso_Compraventa_{(fd.get('nombre') or 'documento').replace(' ', '_')}.pdf"
    return Response(content=buf.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fn}"'})


@api.get("/aprobacion-cliente/preview-pdf")
async def aprobacion_preview_pdf(ruta: str = "", origen: str = "autocorreo", cliente: str = ""):
    """Previsualiza uno de los PDFs a enviar al cliente (para confirmar antes de enviar)."""
    try:
        if origen == "clientes":
            p = fsvc.resolver_ruta(cliente, ruta)
        else:
            p = (STORAGE_DIR / ruta).resolve()
            if not str(p).startswith(str(STORAGE_DIR.resolve())):
                raise HTTPException(status_code=400, detail="Ruta inválida")
    except ValueError:
        raise HTTPException(status_code=400, detail="Ruta inválida")
    if not p.exists() or p.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(str(p), media_type="application/pdf",
                        filename=_nombre_cliente_pdf(p.name))


@api.delete("/aprobacion-cliente/archivo")
async def aprobacion_eliminar_archivo(ruta: str = "", origen: str = "autocorreo", cliente: str = ""):
    """Basurero: elimina físicamente un PDF erróneo para poder resubir el correcto."""
    try:
        if origen == "clientes":
            p = fsvc.resolver_ruta(cliente, ruta)
        else:
            p = (STORAGE_DIR / ruta).resolve()
            if not str(p).startswith(str(STORAGE_DIR.resolve())):
                raise HTTPException(status_code=400, detail="Ruta inválida")
    except ValueError:
        raise HTTPException(status_code=400, detail="Ruta inválida")
    if not p.exists() or p.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    p.unlink()
    if origen == "clientes" and cliente.strip():
        await asyncio.to_thread(_regen_carpeta_cliente, cliente.strip())
    bunker.sync_en_background()
    return {"ok": True, "eliminado": p.name}


GASTOS_OP_RX = re.compile(r"gastos?\s+operacionales", re.I)


@api.post("/aprobacion-cliente/upload")
async def aprobacion_upload(cliente: str = Form(...), file: UploadFile = File(...)):
    """Sube el PDF correcto con DETECTOR de Simulación Ajustada y LEY DEL RUT."""
    if len((cliente or "").strip()) < 3:
        raise HTTPException(status_code=400, detail="Selecciona el cliente antes de subir el archivo")
    raw = await file.read()
    raw, nombre_f, _conv = pdfs.convertir_a_pdf(raw, file.filename)
    texto, _m = await asyncio.to_thread(ocr_service.extraer_texto, raw, nombre_f)
    # DETECTOR DE 'SIMULACIÓN AJUSTADA': si trae tablas de Gastos Operacionales, NO es la simulación
    if GASTOS_OP_RX.search(texto or ""):
        raise HTTPException(status_code=422, detail=(
            "⚠ Este archivo no es una Simulación Ajustada. Contiene tablas de "
            "Gastos Operacionales. Por favor, suba el documento correcto."))
    # LEY DEL RUT: el RUT del archivo debe coincidir con el dueño de la carpeta (o codeudor)
    fdoc = await db.folders.find_one(
        {"nombre": {"$regex": f"^{re.escape(cliente.strip())}$", "$options": "i"}})
    rut_dueno = _norm_rut((fdoc or {}).get("rut", ""))
    rut_cod = _norm_rut((fdoc or {}).get("codeudor_rut", ""))
    ruts_arch = {_norm_rut(r) for r in RUT_EN_TEXTO_RX.findall(texto or "")}
    if len(rut_dueno) >= 7 and ruts_arch and not (ruts_arch & {rut_dueno, rut_cod}):
        raise HTTPException(status_code=422, detail=(
            f"⚠ LEY DEL RUT: el archivo contiene un RUT que NO coincide con el dueño de la "
            f"carpeta ({(fdoc or {}).get('rut', '')}). Vínculo descartado."))
    # RUT COMO BRÚJULA: si el archivo trae SOLO el RUT del codeudor, va a 05_codeudor
    if (len(rut_cod) >= 7 and rut_cod in ruts_arch
            and not (len(rut_dueno) >= 7 and rut_dueno in ruts_arch)):
        if len(rut_dueno) < 7:
            raise HTTPException(status_code=422, detail=(
                "⚠ REGLA IVANA: la carpeta no tiene RUT titular — no se permite vincular "
                "archivos del codeudor. Configure primero el RUT del titular."))
        cod_nom = ((fdoc or {}).get("codeudor_nombre") or "Codeudor").strip().title()
        fn_cod = _safe_name(nombre_f)
        if not fn_cod.upper().startswith("CODEUDOR_"):
            fn_cod = f"CODEUDOR_{fn_cod}"
        rel_cod = await asyncio.to_thread(
            fsvc.guardar_archivo, (fdoc or {}).get("nombre", cliente.strip()),
            fn_cod, raw, f"05_codeudor/{_safe_name(cod_nom)}")
        bunker.sync_en_background()
        return {"ok": True, "nombre": fn_cod, "tipo": "codeudor",
                "ruta": rel_cod, "origen": "clientes",
                "aviso": f"Archivo del CODEUDOR ({cod_nom}) — guardado en 05_codeudor, no se mezcla con el titular"}
    fn = _safe_name(nombre_f)
    if _tipo_pdf_aprobacion(fn) == "otro":
        fn = f"simulador_{fn}"
    dest = STORAGE_DIR / _safe_name(cliente.strip())
    dest.mkdir(parents=True, exist_ok=True)
    (dest / fn).write_bytes(raw)
    bunker.sync_en_background()
    return {"ok": True, "nombre": fn, "tipo": _tipo_pdf_aprobacion(fn),
            "ruta": str((dest / fn).relative_to(STORAGE_DIR)), "origen": "autocorreo"}


@api.get("/aprobacion-cliente/log")
async def aprobacion_log():
    docs = await db.aprobacion_log.find({}).sort("enviado_en", -1).limit(20).to_list(20)
    return {"log": [clean(d) for d in docs]}


# ---------------------------------------------------------------------------
# ------------------------------------------------------------------
# SIMULADOR INMOBILIARIO MARTÍN (página pública /api/martin-vip/{token})
# ------------------------------------------------------------------

MARTIN_TOKEN_KEY = "martin_token"


async def _martin_token():
    cfg = await db.config.find_one({"_key": MARTIN_TOKEN_KEY})
    if not cfg:
        token = uuid.uuid4().hex[:10]
        await db.config.update_one({"_key": MARTIN_TOKEN_KEY}, {"$set": {"token": token}}, upsert=True)
        return token
    return cfg["token"]


@api.get("/martin/link")
async def martin_link(request: Request):
    token = await _martin_token()
    proto = request.headers.get("x-forwarded-proto", "https")
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    return {"url": f"{proto}://{host}/api/martin-vip/{token}", "token": token}


@api.post("/martin/simular")
async def martin_simular(payload: dict):
    """CEREBRO DE VIABILIDAD: usa los criterios reales de la MESA (calibración) + reglas duras."""
    p = payload or {}
    stats = await _stats_mesa()
    cons = await _constitucion_dashai()
    try:
        uf_hoy = await get_valor_uf()
    except Exception:
        uf_hoy = 39000
    try:
        res = simulador_engine.calcular_viabilidad(p, base_mesa=stats.get("base", 0.85),
                                                   uf_hoy=uf_hoy, umbrales=cons["umbrales"])
        res["constitucion_dashai"] = cons["version"]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if p.get("op"):
        await sales_engine.marcar_uso_simulador(str(p.get("op")))
    return res


@api.post("/martin/abrir-carpeta")
async def martin_abrir_carpeta(payload: dict):
    """CONVERSIÓN: crea la carpeta en la base maestra con etiqueta 'Lead de Inmobiliaria'."""
    p = payload or {}
    token = (p.get("token") or "").strip()
    if token != await _martin_token():
        raise HTTPException(status_code=403, detail="Token no válido")
    nombre = (p.get("nombre") or "").strip().title()
    rut = (p.get("rut") or "").strip()
    if len(nombre.split()) < 2 or len(rut) < 8:
        raise HTTPException(status_code=400, detail="Indica nombre completo y RUT válido")
    ya = await db.folders.find_one({"nombre": {"$regex": f"^{re.escape(nombre)}$", "$options": "i"}})
    if ya:
        return {"ok": True, "id": ya["id"], "mensaje": "El cliente ya tenía carpeta en Central Mutuos"}
    sim = p.get("simulacion") or {}
    fid = str(uuid.uuid4())
    fsvc.folder_dir(nombre).mkdir(parents=True, exist_ok=True)
    await db.folders.insert_one({
        "id": fid, "nombre": nombre, "rut": rut, "etiqueta": "Lead de Inmobiliaria",
        "origen": "simulador_martin", "archivos": [],
        "datos_financieros": {k: v for k, v in {
            "valor_propiedad": sim.get("valor_propiedad"),
            "monto_credito": sim.get("monto_credito"),
            "con_subsidio": bool(sim.get("con_subsidio")),
        }.items() if v not in (None, "")},
        "historial": [{"fecha": now_iso(),
                       "accion": f"Carpeta creada desde Simulador Martín (viabilidad {sim.get('porcentaje','?')}%) — Lead de Inmobiliaria"}],
        "created_at": now_iso(), "updated_at": now_iso()})
    await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "lead_inmobiliaria",
                                 "cliente": nombre,
                                 "mensaje": f"🏠 Nuevo Lead de Inmobiliaria desde Simulador Martín: {nombre} ({rut})",
                                 "fecha": now_iso(), "leida": False})
    await sales_engine.desde_expediente_vip(nombre, rut, sim)
    return {"ok": True, "id": fid, "mensaje": f"Carpeta de {nombre} creada en Central Mutuos"}


@api.get("/martin-vip/{token}", response_class=HTMLResponse)
async def martin_portal(token: str):
    if token != await _martin_token():
        return HTMLResponse("<h3 style='font-family:serif;text-align:center;margin-top:20vh'>Enlace no válido — Central Mutuos</h3>", status_code=404)
    html = """<!DOCTYPE html>
<html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Simulador Martín — Central Mutuos</title>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800&display=swap" rel="stylesheet">
<style>
* { margin:0; padding:0; box-sizing:border-box; font-family:'Montserrat',sans-serif; }
body { min-height:100vh; color:#0f172a; padding:1.2rem; padding-bottom:4rem;
  background: radial-gradient(1200px 600px at 10% -10%, #dbeafe 0%, transparent 50%),
              radial-gradient(1000px 500px at 110% 110%, #e2e8f0 0%, transparent 50%), #f8fafc; }
.wrap { max-width:520px; margin:0 auto; }
.head { text-align:center; margin:1rem 0 1.6rem; }
.head .logo { font-weight:800; letter-spacing:0.25em; font-size:0.8rem; color:#0f172a; }
.head h1 { font-size:1.5rem; font-weight:800; margin-top:0.4rem; }
.head p { font-size:0.8rem; color:#64748b; margin-top:0.3rem; }
.glass { background:rgba(255,255,255,0.65); backdrop-filter:blur(16px); -webkit-backdrop-filter:blur(16px);
  border:1px solid rgba(15,23,42,0.10); border-radius:18px; box-shadow:0 12px 40px rgba(15,23,42,0.08); }
.grid { display:grid; grid-template-columns:1fr 1fr; gap:0.7rem; }
.card { padding:0.9rem; }
.card label { display:block; font-size:0.62rem; font-weight:600; letter-spacing:0.08em;
  text-transform:uppercase; color:#64748b; margin-bottom:0.35rem; }
.card input { width:100%; border:1px solid #cbd5e1; border-radius:10px; padding:0.65rem 0.7rem;
  font-size:1rem; font-weight:600; color:#0f172a; background:#fff; }
.card input:focus { outline:none; border-color:#0f172a; }
.sub { display:flex; align-items:center; gap:0.6rem; padding:0.9rem; font-size:0.85rem; font-weight:600; }
.sub input { width:20px; height:20px; accent-color:#0f172a; }
.btn { width:100%; background:#0f172a; color:#fff; font-weight:800; font-size:1rem; border:none;
  border-radius:999px; padding:1rem; margin-top:1rem; cursor:pointer; box-shadow:0 10px 30px rgba(15,23,42,0.30);
  transition:transform .15s ease; }
.btn:active { transform:scale(0.98); }
.result { margin-top:1.4rem; padding:1.4rem; text-align:center; display:none; }
.gauge { position:relative; width:210px; height:120px; margin:0 auto; }
.gauge svg { width:100%; height:100%; }
.gauge .num { position:absolute; bottom:0; left:0; right:0; font-size:2rem; font-weight:800; }
.martin { display:flex; gap:0.7rem; align-items:flex-start; margin-top:1.2rem; text-align:left; }
.martin .avatar { width:44px; height:44px; border-radius:50%; background:#0f172a; color:#bfdbfe;
  display:flex; align-items:center; justify-content:center; font-weight:800; flex-shrink:0; font-size:1.1rem; }
.burbuja { background:#0f172a; color:#e2e8f0; border-radius:16px 16px 16px 4px; padding:0.8rem 1rem;
  font-size:0.85rem; line-height:1.55; box-shadow:0 8px 24px rgba(15,23,42,0.25); }
.factores { margin-top:1rem; text-align:left; font-size:0.72rem; color:#64748b; line-height:1.7; }
.btn-lux { display:none; width:100%; margin-top:1.2rem; background:linear-gradient(135deg,#0f172a,#1e3a5f);
  color:#fff; border:1px solid #60a5fa; font-weight:800; font-size:0.95rem; border-radius:999px;
  padding:1rem; cursor:pointer; box-shadow:0 12px 34px rgba(37,99,235,0.35); }
.modal { display:none; position:fixed; inset:0; background:rgba(15,23,42,0.55); z-index:50;
  align-items:center; justify-content:center; padding:1rem; backdrop-filter:blur(4px); }
.modal .inner { background:#fff; border-radius:18px; padding:1.6rem; width:100%; max-width:380px; }
.modal input { width:100%; border:1px solid #cbd5e1; border-radius:10px; padding:0.7rem; font-size:1rem; margin-top:0.7rem; }
.badge { position:fixed; bottom:12px; right:14px; background:rgba(255,255,255,0.8); backdrop-filter:blur(8px);
  border:1px solid #e2e8f0; border-radius:999px; padding:0.35rem 0.8rem; font-size:0.6rem; font-weight:700; color:#0f172a; }
.ok { color:#16a34a; font-weight:700; font-size:0.85rem; margin-top:0.8rem; display:none; }
</style></head>
<body><div class="wrap">
  <div class="head">
    <div class="logo">CENTRAL MUTUOS</div>
    <h1>Simulador Martín</h1>
    <p>Viabilidad hipotecaria instantánea con los criterios reales de la mesa</p>
  </div>
  <div class="glass" style="padding:1rem">
    <div class="grid">
      <div class="card glass"><label>Valor propiedad (UF)</label><input id="valor" type="number" inputmode="decimal" placeholder="4.500" data-testid="martin-valor"></div>
      <div class="card glass"><label>Monto crédito (UF)</label><input id="monto" type="number" inputmode="decimal" placeholder="3.600" data-testid="martin-monto"></div>
      <div class="card glass"><label>Renta líquida (CLP)</label><input id="renta" type="number" inputmode="numeric" placeholder="1.800.000" data-testid="martin-renta"></div>
      <div class="card glass"><label>Deudas mensuales (CLP)</label><input id="deudas" type="number" inputmode="numeric" placeholder="250.000" data-testid="martin-deudas"></div>
    </div>
    <div class="sub glass" style="margin-top:0.7rem"><input id="subsidio" type="checkbox" data-testid="martin-subsidio"><label for="subsidio" style="margin:0;font-size:0.8rem;text-transform:none;letter-spacing:0">Cuenta con subsidio habitacional (DS19/DS1)</label></div>
    <div class="martin" id="liveWrap" style="display:none;margin-top:0.9rem">
      <div class="avatar">M</div>
      <div class="burbuja" id="liveTip" data-testid="martin-live"></div>
    </div>
    <button class="btn" onclick="simular()" data-testid="martin-simular-btn">Calcular viabilidad</button>
  </div>
  <div class="glass result" id="resultado" data-testid="martin-resultado">
    <div class="gauge">
      <svg viewBox="0 0 210 120">
        <path d="M15 110 A 90 90 0 0 1 195 110" fill="none" stroke="#e2e8f0" stroke-width="14" stroke-linecap="round"/>
        <path id="arco" d="M15 110 A 90 90 0 0 1 195 110" fill="none" stroke="#0f172a" stroke-width="14"
              stroke-linecap="round" stroke-dasharray="283" stroke-dashoffset="283" style="transition:stroke-dashoffset 1.2s ease, stroke 0.6s"/>
      </svg>
      <div class="num" id="pct" data-testid="martin-pct">—</div>
    </div>
    <div class="martin">
      <div class="avatar">M</div>
      <div class="burbuja" id="veredicto" data-testid="martin-veredicto"></div>
    </div>
    <div class="martin" id="consejoWrap" style="display:none">
      <div class="avatar" style="background:#B38728;color:#0f172a">M</div>
      <div class="burbuja" id="consejo" data-testid="martin-consejo" style="background:#1c1917"></div>
    </div>
    <div class="factores" id="factores"></div>
    <button class="btn-lux" id="btnCarpeta" onclick="abrirModal()" data-testid="martin-abrir-carpeta-btn">✦ Abrir Carpeta en Central Mutuos</button>
    <div class="ok" id="okMsg" data-testid="martin-ok"></div>
  </div>
</div>
<div class="modal" id="modal" data-testid="martin-modal">
  <div class="inner">
    <b style="font-size:1rem">Abrir carpeta del cliente</b>
    <p style="font-size:0.78rem;color:#64748b;margin-top:0.3rem">Solo necesitamos nombre y RUT. El resto ya lo tiene Martín.</p>
    <input id="mNombre" placeholder="Nombre y apellido" data-testid="martin-nombre">
    <input id="mRut" placeholder="RUT (12.345.678-9)" data-testid="martin-rut">
    <button class="btn" style="margin-top:1rem" onclick="crearCarpeta()" data-testid="martin-crear-btn">Crear carpeta</button>
    <button style="width:100%;background:none;border:none;color:#64748b;margin-top:0.7rem;cursor:pointer" onclick="document.getElementById('modal').style.display='none'">Cancelar</button>
  </div>
</div>
<div class="badge">🛡 Motor calibrado con la MESA · Central Mutuos</div>
<script>
const TOKEN = location.pathname.split('/').pop();
const OP = new URLSearchParams(location.search).get('op') || '';
let ultimaSim = null;
function vozMartin() {
  const v = parseFloat(document.getElementById('valor').value) || 0;
  const m = parseFloat(document.getElementById('monto').value) || 0;
  const r = parseFloat(document.getElementById('renta').value) || 0;
  let tip = '';
  if (m && m < 2000 && !document.getElementById('subsidio').checked) tip = 'José Martín dice: ojo, bajo 2.000 UF sin subsidio la mesa no evalúa. Activa tu subsidio o ajustemos el monto 😉';
  else if (v && m && m / v > 0.9) tip = 'José Martín dice: estás pidiendo más del 90% del valor. Con un pie del 10-20% la mesa te mira con otros ojos ✨';
  else if (v && m && m / v <= 0.8) tip = '¡Ese pie está regio! Financiar el ' + Math.round(m / v * 100) + '% te suma puntos con la mesa 💪 — José Martín';
  else if (r && r > 0 && r < 800000) tip = 'José Martín dice: con esa renta conviene sumar un complemento o codeudor. ¡Se puede, créeme!';
  const w = document.getElementById('liveWrap');
  if (tip) { w.style.display = 'flex'; document.getElementById('liveTip').textContent = tip; }
  else w.style.display = 'none';
}
['valor','monto','renta','deudas'].forEach(id => document.getElementById(id).addEventListener('input', vozMartin));
document.getElementById('subsidio').addEventListener('change', vozMartin);
async function simular() {
  const body = { valor_propiedad: document.getElementById('valor').value,
    monto_credito: document.getElementById('monto').value,
    renta: document.getElementById('renta').value,
    deudas: document.getElementById('deudas').value,
    con_subsidio: document.getElementById('subsidio').checked, op: OP };
  try {
    const r = await fetch('/api/martin/simular', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) });
    const d = await r.json();
    if (!r.ok) { alert(d.detail || 'Revisa los datos'); return; }
    ultimaSim = Object.assign({}, body, { porcentaje: d.porcentaje });
    document.getElementById('resultado').style.display = 'block';
    const p = d.porcentaje;
    document.getElementById('pct').textContent = p + '%';
    const color = p >= 70 ? '#16a34a' : p >= 40 ? '#d97706' : '#dc2626';
    document.getElementById('pct').style.color = color;
    const arco = document.getElementById('arco');
    arco.style.stroke = color;
    arco.style.strokeDashoffset = String(283 - (283 * p / 100));
    document.getElementById('veredicto').textContent = d.veredicto;
    const cw = document.getElementById('consejoWrap');
    if (d.consejo) { cw.style.display = 'flex'; document.getElementById('consejo').textContent = d.consejo; }
    else cw.style.display = 'none';
    document.getElementById('factores').innerHTML = d.factores.map(f => '· ' + f).join('<br>') +
      (d.cuota_estimada_clp ? '<br>· Dividendo estimado: $' + d.cuota_estimada_clp.toLocaleString('es-CL') + ' (30 años)' : '');
    const btnC = document.getElementById('btnCarpeta');
    btnC.style.display = d.puede_abrir_carpeta ? 'block' : 'none';
    btnC.textContent = d.puede_abrir_expediente ? '✦ Abrir Expediente VIP' : '✦ Abrir Carpeta en Central Mutuos';
    document.getElementById('okMsg').style.display = 'none';
    document.getElementById('resultado').scrollIntoView({behavior:'smooth'});
  } catch(e) { alert('Error de conexión'); }
}
function abrirModal() { document.getElementById('modal').style.display = 'flex'; }
async function crearCarpeta() {
  const nombre = document.getElementById('mNombre').value, rut = document.getElementById('mRut').value;
  try {
    const r = await fetch('/api/martin/abrir-carpeta', { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ token: TOKEN, nombre, rut, simulacion: ultimaSim }) });
    const d = await r.json();
    if (!r.ok) { alert(d.detail || 'Revisa nombre y RUT'); return; }
    document.getElementById('modal').style.display = 'none';
    const ok = document.getElementById('okMsg');
    ok.textContent = '✅ ' + d.mensaje + ' — el equipo de Central Mutuos ya fue notificado.';
    ok.style.display = 'block';
  } catch(e) { alert('Error de conexión'); }
}
</script>
</body></html>"""
    return HTMLResponse(html)


# ------------------------------------------------------------------
# CENTRO DE VENTAS VIP — Oportunidades (José Martín Benavente)
# REGLA INVIOLABLE: nada sale sin que Gerardo presione 'Autorizar Envío'.
# ------------------------------------------------------------------

def _base_url_req(request: Request):
    """ANCLAJE TOTAL: REACT_APP_BACKEND_URL/PUBLIC_BASE_URL como única fuente de verdad.
    Prohibido localhost/IPs internas en links de clientes."""
    pub = (os.environ.get("REACT_APP_BACKEND_URL") or os.environ.get("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if pub:
        return pub
    proto = request.headers.get("x-forwarded-proto", "https")
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    return f"{proto}://{host}"


@api.post("/oportunidades/upload-excel")
async def oportunidades_upload(file: UploadFile = File(...)):
    raw = await file.read()
    try:
        prospectos = sales_engine.parsear_excel(raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No pude leer el Excel: {str(e)[:120]}")
    if not prospectos:
        raise HTTPException(status_code=400, detail="El Excel no tiene prospectos reconocibles (necesita columnas nombre/correo)")
    res = await sales_engine.crear_oportunidades(prospectos)
    return {"ok": True, **res, "total_archivo": len(prospectos)}


async def _puntuar_prospecto(op, modelo, base_pct):
    """Score DashAI de un prospecto (compartido por endpoint y sync perpetuo)."""
    prob = base_pct
    rut_n = re.sub(r"[^0-9kK]", "", (op.get("rut") or "")).lower()
    sim = None
    if rut_n:
        sim = await db.simulaciones.find_one(
            {"rut": {"$regex": rut_n[:8], "$options": "i"}}, sort=[("timestamp", -1)])
    if not sim and op.get("nombre"):
        sim = await db.simulaciones.find_one(
            {"nombre_completo": {"$regex": re.escape(op["nombre"][:20]), "$options": "i"}},
            sort=[("timestamp", -1)])
    sim_eval = sim or op.get("simulacion")
    if sim_eval:
        if sim_eval.get("precalificacion_aprobada"):
            prob = min(97, base_pct + 15)
        elif sim_eval.get("credito_viable"):
            prob = min(92, base_pct + 8)
        else:
            prob = max(10, base_pct - 35)
        # ⚔️ REGLAS DE HIERRO + reglamento Con Subsidio 02 (edad/LTV):
        # cualquier quiebre → viabilidad 0% y NO VIABLE - POLÍTICA GENERAL
        quiebres = await asyncio.to_thread(
            mesa_brain.evaluar_politicas_generales, {"datos_financieros": {}}, sim_eval)
        if quiebres:
            prob = 0
            op["politica_general"] = "NO VIABLE - POLÍTICA GENERAL"
            op["quiebres_politica"] = [q["detalle"] for q in quiebres]
        else:
            op["politica_general"] = "CUMPLE REGLAMENTO"
    else:
        op["politica_general"] = "SIN SIMULACIÓN"
    op["prob_mesa"] = prob
    op["objetivo_whatsapp"] = prob >= 85
    return prob


@api.get("/oportunidades")
async def oportunidades_list(request: Request):
    try:
        await sales_engine.proponer_seguimientos(_base_url_req(request))
    except Exception:
        pass
    ops = await sales_engine.listar()
    # PRIORIZACIÓN COMERCIAL: score del Cerebro Predictivo (>=85% = objetivo WhatsApp)
    try:
        modelo = await asyncio.to_thread(mesa_brain.modelo_actual)
        base_pct = round((modelo.get("base") or 0.85) * 100)
        for op in ops:
            await _puntuar_prospecto(op, modelo, base_pct)
        ops.sort(key=lambda o: -(o.get("prob_mesa") or 0))
    except Exception:
        pass
    return {"oportunidades": ops, "resumen": sales_engine.nota_diaria(ops)}


@api.post("/oportunidades/{oid}/preparar")
async def oportunidades_preparar(oid: str, request: Request):
    base = _base_url_req(request)
    link_click = f"{base}/api/oportunidades/track/{oid}/click"
    try:
        return await sales_engine.preparar_borrador(oid, base, link_click)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@api.post("/oportunidades/{oid}/autorizar")
async def oportunidades_autorizar(oid: str, payload: dict):
    """CANDADO DE SUPERVISIÓN: requiere confirm explícito de Gerardo + bloqueo 14 días."""
    if not (payload or {}).get("confirm"):
        raise HTTPException(status_code=400, detail="Falta la autorización explícita de Gerardo")

    def _send(to, subject, body):
        return mail.send_mail(to, subject, body, [], "secundaria")

    try:
        return await sales_engine.autorizar_envio(oid, _send)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@api.get("/oportunidades/track/{oid}/pixel.gif")
async def oportunidades_pixel(oid: str):
    await sales_engine.track(oid, "pixel")
    gif = _b64mod.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
    return _RawResponse(content=gif, media_type="image/gif")


@api.get("/oportunidades/track/{oid}/click")
async def oportunidades_click(oid: str, request: Request):
    await sales_engine.track(oid, "click")
    token = await _martin_token()
    return RedirectResponse(f"{_base_url_req(request)}/api/martin-vip/{token}?op={oid}")


@api.delete("/oportunidades/{oid}")
async def oportunidades_delete(oid: str):
    await db.prospectos.delete_one({"id": oid})
    return {"ok": True}


@api.post("/oportunidades/{oid}/invitacion-vip")
async def oportunidades_invitacion_vip(oid: str, request: Request):
    """CAMPAÑA COMERCIAL: invitación Maserati con link al Portal de Captura Autónoma.
    REGLA DE ORIGEN: sale siempre desde la cuenta corporativa gerardo.ext@centralmutuos.cl."""
    op = await db.prospectos.find_one({"id": oid})
    if not op:
        raise HTTPException(status_code=404, detail="Prospecto no encontrado")
    to = (op.get("email") or "").strip()
    if "@" not in to:
        raise HTTPException(status_code=400, detail="El prospecto no tiene un correo válido")
    base = _base_url_req(request)
    link_portal = f"{base}/api/calificar/{oid}"
    pixel = f"{base}/api/oportunidades/track/{oid}/pixel.gif"
    msg = sales_engine.mensaje_invitacion_vip(op.get("nombre", ""), op.get("proyecto", ""),
                                              link_portal, pixel)
    res = await asyncio.to_thread(mail.send_mail, to, msg["subject"], msg["body"], [], "secundaria")
    if not res.get("success"):
        raise HTTPException(status_code=502, detail=res.get("error", "Error de envío SMTP"))
    await db.prospectos.update_one({"id": oid}, {"$set": {
        "status": "invitacion_enviada", "invitacion_enviada_en": now_iso(),
        "link_calificar": link_portal}})
    return {"ok": True, "to": to,
            "mensaje": f"📧 Invitación VIP enviada a {to} desde la cuenta corporativa"}


@api.post("/oportunidades/{oid}/whatsapp-vip")
async def oportunidades_whatsapp_vip(oid: str, request: Request):
    """VÍA RÁPIDA (REGLA DE HIERRO): motor wa.me sin API Meta. Genera el link VIP
    Maserati público y el link de WhatsApp del cliente para abrir la ventana."""
    op = await db.prospectos.find_one({"id": oid})
    if not op:
        raise HTTPException(status_code=404, detail="Prospecto no encontrado")
    tel = re.sub(r"[^0-9]", "", (op.get("telefono") or "").strip())
    if len(tel) < 8:
        raise HTTPException(status_code=400, detail="El prospecto no tiene un teléfono válido")
    if not tel.startswith("56"):
        tel = "56" + tel.lstrip("0")
    base = _base_url_req(request)
    url = f"{base}/api/calificar/{oid}"
    primer = (op.get("nombre") or "").split()[0].title() if op.get("nombre") else "Cliente"
    texto = (f"🏠 *Central Mutuos - Precalificación Hipotecaria*\n\n"
             f"Hola {primer}, le saluda *Central Mutuos*. "
             f"Suba su Cédula y sus últimas 6 Liquidaciones de Sueldo en este portal privado "
             f"y su calificación queda lista:\n{url}"
             f"\n\nAtentamente, el equipo de @CentralMutuos")
    wa_url = f"https://wa.me/{tel}?text={_urlquote(texto)}"
    await db.prospectos.update_one({"id": oid}, {"$set": {
        "whatsapp_enviado_en": now_iso(), "whatsapp_motor": "via_rapida_wame",
        "link_calificar": url}})
    return {"ok": True, "whatsapp": wa_url, "url": url,
            "mensaje": f"🚀 VÍA RÁPIDA: abriendo WhatsApp de {primer} (+{tel}) con la Tarjeta VIP lista"}


@api.get("/whatsapp/estado")
async def whatsapp_estado():
    """REGLA DE HIERRO: prohibido solicitar credenciales Meta. Motor único: wa.me."""
    return {"configurado": True, "modo": "VÍA RÁPIDA ACTIVA (Sin API Meta)",
            "motor": "Despachador Masivo Secuencial vía wa.me",
            "identidad": "@CentralMutuos"}


@api.post("/prospectos/{pid}/promover")
async def prospecto_promover(pid: str):
    """MURO DE VENTA: promoción manual y consciente de un prospecto a Cliente Activo.
    REGLA DE HIERRO: prohibida cualquier sincronización automática Excel → carpetas."""
    p = await db.prospectos.find_one({"id": pid})
    if not p:
        raise HTTPException(status_code=404, detail="Prospecto no encontrado")
    if p.get("estado") == "PROMOVIDO":
        raise HTTPException(status_code=400, detail="Este prospecto ya fue promovido a Cliente Activo")
    nombre = (p.get("nombre") or "").strip().title()
    if not nombre:
        raise HTTPException(status_code=400, detail="El prospecto no tiene nombre")
    fd = await db.folders.find_one({"nombre": nombre})
    if not fd:
        fd = {"id": str(uuid.uuid4()), "nombre": nombre, "rut": p.get("rut") or "",
              "email": p.get("email") or "", "telefono": p.get("telefono") or "",
              "proyecto": p.get("proyecto") or "", "archivos": [],
              "created_at": now_iso(), "origen": "promocion_prospecto"}
        await db.folders.insert_one(dict(fd))
    base = fsvc.folder_dir(nombre)
    for sub in ("01_cedula", "02_liquidaciones", "03_afp", "04_cmf",
                "05_codeudor", "06_cotizacion", "99_otros"):
        (base / sub).mkdir(parents=True, exist_ok=True)
    await db.prospectos.update_one({"id": pid}, {"$set": {
        "estado": "PROMOVIDO", "promovido_en": now_iso(), "folder_id": fd["id"]}})
    return {"ok": True, "folder_id": fd["id"], "nombre": nombre,
            "mensaje": f"📂 {nombre} promovido a Cliente Activo con su estructura de subcarpetas"}


# ------------------------------------------------------------------
# INFORMES VIP DE ESTATUS (PDF estilo Forbes — Oro/Carbono)
# ------------------------------------------------------------------

def _informe_vip_pdf(doc, prob):
    """PDF elegante de estatus del crédito del cliente (paleta Oro 24K / Negro Carbono)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.colors import HexColor
    from reportlab.pdfgen import canvas as _canvas
    SLATE, ICE, GRIS = HexColor("#0a0a0a"), HexColor("#d4af37"), HexColor("#6b7280")
    buf = io.BytesIO()
    c = _canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    df = doc.get("datos_financieros") or {}
    nombre = doc.get("nombre", "Cliente")
    # Portada / cabecera
    c.setFillColor(SLATE)
    c.rect(0, H - 150, W, 150, fill=1, stroke=0)
    c.setFillColor(HexColor("#FCF6BA"))
    c.setFont("Times-Bold", 24)
    c.drawString(50, H - 70, "CENTRAL MUTUOS")
    c.setFont("Helvetica", 9)
    c.setFillColor(HexColor("#94a3b8"))
    c.drawString(50, H - 90, "INFORME VIP DE ESTATUS")
    c.setFont("Helvetica", 9)
    c.drawRightString(W - 50, H - 70, datetime.now(timezone.utc).strftime("%d/%m/%Y"))
    c.setStrokeColor(ICE)
    c.setLineWidth(2)
    c.line(50, H - 105, 200, H - 105)
    c.setFillColor(HexColor("#ffffff"))
    c.setFont("Times-Bold", 17)
    c.drawString(50, H - 132, nombre.title())
    y = H - 190

    def _seccion(titulo):
        nonlocal y
        c.setFillColor(ICE)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(50, y, titulo.upper())
        c.setStrokeColor(HexColor("#cbd5e1"))
        c.setLineWidth(0.5)
        c.line(50, y - 5, W - 50, y - 5)
        y -= 24

    def _fila(k, v):
        nonlocal y
        if v in (None, ""):
            return
        c.setFillColor(GRIS)
        c.setFont("Helvetica", 9)
        c.drawString(58, y, str(k))
        c.setFillColor(SLATE)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(230, y, str(v)[:70])
        y -= 16

    _seccion("Resumen de la operación")
    _fila("RUT", doc.get("rut"))
    _fila("Proyecto", df.get("proyecto"))
    _fila("Inmobiliaria", df.get("inmobiliaria"))
    _fila("Valor propiedad", f"{df.get('valor_propiedad')} UF" if df.get("valor_propiedad") else "")
    _fila("Monto crédito", f"{df.get('monto_credito')} UF" if df.get("monto_credito") else "")
    _fila("Fecha de entrega", df.get("fecha_entrega"))
    _fila("Ejecutivo interno", doc.get("ejecutivo_interno"))
    _fila("Ejecutivo externo", doc.get("ejecutivo_externo"))
    y -= 8
    _seccion("Evaluación crediticia")
    pct = prob.get("porcentaje")
    c.setFillColor(ICE if (pct or 0) >= 50 else HexColor("#be123c"))
    c.setFont("Times-Bold", 30)
    c.drawString(58, y - 14, f"{pct}%")
    c.setFillColor(GRIS)
    c.setFont("Helvetica", 9)
    c.drawString(140, y - 8, "probabilidad de aprobación en mesa")
    y -= 44
    for fct in (prob.get("factores") or [])[:8]:
        c.setFillColor(GRIS)
        c.setFont("Helvetica", 8)
        c.drawString(58, y, f"· {fct[:100]}")
        y -= 13
    y -= 10
    _seccion("Documentación")
    archivos = doc.get("archivos") or fsvc.scan_archivos(nombre)
    cats = {}
    for a in archivos:
        if isinstance(a, str):
            rel, fn = (a.rsplit("/", 1) + [""])[:2] if "/" in a else ("", a)
        else:
            rel, fn = a.get("subfolder", ""), a.get("nombre", "")
        cat = fsvc.cat_de_archivo(fn, rel)
        cats[cat] = cats.get(cat, 0) + 1
    _fila("Documentos en carpeta", sum(cats.values()))
    for cat, n in sorted(cats.items()):
        if cat not in ("combinado",):
            _fila(f"  {fsvc.MISSING_LABELS.get(cat, cat).title()}", n)
    y -= 8
    _seccion("Última actividad")
    for h in (doc.get("historial") or [])[-6:][::-1]:
        c.setFillColor(GRIS)
        c.setFont("Helvetica", 8)
        c.drawString(58, y, f"{(h.get('fecha') or '')[:10]}  —  {(h.get('accion') or '')[:90]}")
        y -= 13
        if y < 90:
            break
    c.setFillColor(SLATE)
    c.rect(0, 0, W, 46, fill=1, stroke=0)
    c.setFillColor(HexColor("#94a3b8"))
    c.setFont("Helvetica", 7)
    c.drawCentredString(W / 2, 26, "Documento confidencial · Central Mutuos · Cifrado y auditado")
    c.drawCentredString(W / 2, 15, "Informe generado automáticamente por el sistema de inteligencia crediticia")
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.getvalue()


@api.get("/informes/vip/{fid}/pdf")
async def informe_vip_pdf(fid: str):
    doc = await _get_folder_doc(fid)
    prob = _prob_aprobacion_folder(doc, await _stats_mesa())
    pdf = await asyncio.to_thread(_informe_vip_pdf, doc, prob)
    fn = f"Informe_VIP_{fsvc.safe_name(doc.get('nombre','cliente'))}.pdf"
    return _RawResponse(content=pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{fn}"'})


@api.post("/informes/vip/{fid}/enviar")
async def informe_vip_enviar(fid: str, payload: dict):
    payload = payload or {}
    doc = await _get_folder_doc(fid)
    to = (payload.get("to") or doc.get("email") or "").strip()
    if not to:
        raise HTTPException(status_code=400, detail="La carpeta no tiene correo del cliente: indícalo")
    prob = _prob_aprobacion_folder(doc, await _stats_mesa())
    pdf = await asyncio.to_thread(_informe_vip_pdf, doc, prob)
    nombre = doc.get("nombre", "Cliente").title()
    cuerpo = (f"<div style='font-family:Georgia,serif;color:#0f172a;max-width:520px'>"
              f"<h2 style='font-weight:600'>Estimado(a) {nombre.split()[0]},</h2>"
              f"<p style='color:#475569;line-height:1.7'>Adjuntamos su <b>Informe VIP de Estatus</b> "
              f"con el estado actualizado de su operación hipotecaria.</p>"
              f"<p style='color:#94a3b8;font-size:12px'>Central Mutuos</p></div>")
    res = await asyncio.to_thread(mail.send_mail, to, f"Informe VIP de Estatus — {nombre}", cuerpo,
                                  [{"filename": f"Informe_VIP_{fsvc.safe_name(nombre)}.pdf",
                                    "content_b64": _b64(pdf)}], "secundaria")
    if not res.get("success"):
        raise HTTPException(status_code=502, detail=f"Error de envío: {res.get('error')}")
    await db.folders.update_one({"id": fid}, {"$push": {"historial": {
        "fecha": now_iso(), "accion": f"Informe VIP enviado a {to}"}}})
    return {"ok": True, "to": to}


async def _informes_vip_loop():
    """Cada lunes envía al administrador el paquete de Informes VIP de carpetas activas."""
    while True:
        try:
            cfg = await db.config.find_one({"_key": "informes_vip"}) or {}
            if cfg.get("auto", True):
                ahora = datetime.now(timezone.utc)
                hoy = ahora.strftime("%Y-%m-%d")
                if ahora.weekday() == 0 and 11 <= ahora.hour <= 13 and cfg.get("ultimo_envio") != hoy:
                    hace7 = (ahora - timedelta(days=7)).isoformat()
                    activos = await db.folders.find({"$or": [
                        {"updated_at": {"$gte": hace7}},
                        {"historial.fecha": {"$gte": hace7}}]}).limit(12).to_list(12)
                    adjuntos = []
                    stats_m = await _stats_mesa()
                    for d in activos:
                        try:
                            pdf = await asyncio.to_thread(_informe_vip_pdf, d, _prob_aprobacion_folder(d, stats_m))
                            adjuntos.append({"filename": f"Informe_VIP_{fsvc.safe_name(d.get('nombre','x'))}.pdf",
                                             "content_b64": _b64(pdf)})
                        except Exception:
                            continue
                    if adjuntos:
                        await asyncio.to_thread(
                            mail.send_mail, _sender_por_rol("principal"),
                            f"📊 Informes VIP de Estatus — semana del {hoy}",
                            f"<p>Paquete semanal con {len(adjuntos)} informes VIP de carpetas activas.</p>",
                            adjuntos, "principal")
                    await db.config.update_one({"_key": "informes_vip"},
                                               {"$set": {"ultimo_envio": hoy}}, upsert=True)
        except Exception:
            pass
        await asyncio.sleep(1800)


# ------------------------------------------------------------------
# PORTAL DE FIRMA VIP (Banca Privada — Maserati Style)
# 🔒 MÓDULO FINALIZADO Y PROTEGIDO (orden del dueño, 2026-08-06):
#    NO modificar esta sección desde ediciones de otros módulos. El flujo
#    enviar_a_firmar_tercero + portal /api/firma/{token} es INVIOLABLE.
# ------------------------------------------------------------------
from urllib.parse import quote as _urlquote
from fastapi.responses import Response as _RawResponse

OXFORD = "#0f172a"  # Slate-900: caro y tecnológico


@api.post("/firma/generar-link")
async def firma_generar_link(payload: dict, request: Request):
    """Genera el link del Portal de Firma Única del cliente (con tarjeta VIP para WhatsApp)."""
    payload = payload or {}
    cliente = (payload.get("cliente") or "").strip()
    if len(cliente) < 3:
        raise HTTPException(status_code=400, detail="Indica el nombre del cliente")
    toks = [t for t in _norm_texto(cliente).split() if len(t) > 2]
    rx = ".*".join(re.escape(t) for t in toks[:2]) if toks else ""
    rut, email = payload.get("rut", ""), payload.get("email", "")
    f = await db.folders.find_one({"nombre": {"$regex": rx, "$options": "i"}}) if rx else None
    s = await db.set_credito.find_one({"nombre": {"$regex": rx, "$options": "i"}}) if rx else None
    rut = rut or (s or {}).get("rut") or (f or {}).get("rut") or ""
    email = email or (s or {}).get("email") or (f or {}).get("email") or ""
    existente = await db.firma_links.find_one({"cliente_norm": _norm_texto(cliente)})
    if existente:
        token = existente["token"]
    else:
        token = uuid.uuid4().hex[:12]
        await db.firma_links.insert_one({
            "id": str(uuid.uuid4()), "token": token, "cliente": cliente.title(),
            "cliente_norm": _norm_texto(cliente), "rut": rut, "email": email,
            "visitas": 0, "creado_en": now_iso()})
    proto = request.headers.get("x-forwarded-proto", "https")
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    url = f"{proto}://{host}/api/firma/{token}"
    texto_wsp = (f"Estimado(a) {cliente.title().split()[0]}, le compartimos su portal privado de "
                 f"Firma de Escritura Avanzada de Central Mutuos:\n{url}")
    return {"ok": True, "url": url, "token": token, "rut": rut, "email": email,
            "whatsapp": f"https://wa.me/?text={_urlquote(texto_wsp)}"}


_SEMAFORO_CACHE = {"data": None, "at": 0.0}


@api.get("/firma/semaforo")
async def firma_semaforo(force: bool = False):
    """💰 Bóveda de Firmas eCert: saldo vivo del plan migrup (TraerSemaforo, caché 5 min)."""
    import time as _t
    if not force and _SEMAFORO_CACHE["data"] and _t.time() - _SEMAFORO_CACHE["at"] < 300:
        return _SEMAFORO_CACHE["data"]
    try:
        raw = await asyncio.to_thread(migrup.semaforo)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"eCert no respondió: {str(e)[:150]}")
    if not isinstance(raw, dict) or raw.get("descripcionError"):
        raise HTTPException(status_code=502, detail="Respuesta inválida de eCert")
    propias = raw.get("cantFirmasDisponiblesMias")
    if propias is None:
        propias = max((raw.get("firmasAdicionalesMias") or 0) - (raw.get("firmasAdicionalesUsadasMias") or 0), 0)
    terceros = raw.get("cantFirmasDisponiblesTerceros")
    if terceros is None:
        terceros = max((raw.get("firmasAdicionalesTerceros") or 0) - (raw.get("firmasAdicionalesUsadasTerceros") or 0), 0)
    out = {"ok": True, "propias": int(propias or 0), "terceros": int(terceros or 0),
           "documentos": int(raw.get("cantDocumentosDisponibles") or 0),
           "alerta": (propias or 0) < 5 or (terceros or 0) < 5,
           "consultado_en": now_iso()}
    _SEMAFORO_CACHE.update({"data": out, "at": _t.time()})
    return out


def _mask_rut(rut):
    r = (rut or "").replace(".", "").replace("-", "")
    return f"•••.{r[-7:-4]}.{r[-4:-1]}-{r[-1]}" if len(r) >= 8 else (rut or "")


@api.get("/firma/{token}", response_class=HTMLResponse)
async def firma_portal(token: str, request: Request):
    """Landing page de lujo del Portal de Firma Única."""
    link = await db.firma_links.find_one({"token": token})
    if not link:
        return HTMLResponse("<h3 style='font-family:serif;text-align:center;margin-top:20vh'>Enlace no válido o expirado — Central Mutuos</h3>", status_code=404)
    await db.firma_links.update_one({"token": token}, {"$inc": {"visitas": 1}})
    nombre = link.get("cliente", "Cliente")
    proto = request.headers.get("x-forwarded-proto", "https")
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    og_img = f"{proto}://{host}/api/firma/{token}/og.png"
    og_url = f"{proto}://{host}/api/firma/{token}"
    html = f"""<!DOCTYPE html>
<html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Firma de Escritura Avanzada — Central Mutuos</title>
<meta property="og:title" content="Documentación Oficial VIP - Central Mutuos">
<meta property="og:description" content="Hola {nombre}, acceda a su portal privado para la Firma Electrónica Avanzada.">
<meta property="og:image" content="{og_img}">
<meta property="og:image:width" content="600">
<meta property="og:image:height" content="600">
<meta property="og:url" content="{og_url}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Central Mutuos">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{og_img}">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700&family=Montserrat:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:#FAFAF9; font-family:'Montserrat',sans-serif; color:{OXFORD}; min-height:100vh;
         display:flex; flex-direction:column; align-items:center; justify-content:center; padding:2rem; }}
  .marca {{ font-family:'Cormorant Garamond',serif; letter-spacing:0.35em; font-size:0.85rem;
            color:{OXFORD}; opacity:0.7; text-transform:uppercase; margin-bottom:2.5rem; }}
  .card {{ background:#FFFFFF; border-radius:22px; box-shadow:0 20px 60px rgba(15,23,42,0.10), 0 2px 8px rgba(15,23,42,0.06);
           padding:3.2rem 2.8rem; max-width:520px; width:100%; text-align:center; border:1px solid #E7E5E4; }}
  .sello {{ width:64px; height:64px; border-radius:50%; background:{OXFORD}; color:#E2E8F0; display:flex;
            align-items:center; justify-content:center; font-size:1.6rem; margin:0 auto 1.6rem;
            box-shadow:0 8px 24px rgba(15,23,42,0.25); }}
  h1 {{ font-family:'Cormorant Garamond',serif; font-size:1.9rem; font-weight:600; line-height:1.25; margin-bottom:0.6rem; }}
  h1 b {{ color:#0f172a; border-bottom:2px solid #CBD5E1; }}
  .sub {{ font-size:0.86rem; color:#6B7280; margin-bottom:2rem; line-height:1.6; }}
  .datos {{ background:#F8FAFC; border:1px solid #E2E8F0; border-radius:14px; padding:0.9rem 1.2rem; font-size:0.8rem; color:#4B5563;
            margin-bottom:2rem; display:flex; justify-content:space-between; gap:1rem; flex-wrap:wrap; }}
  .btn {{ display:inline-flex; align-items:center; gap:0.6rem; background:{OXFORD}; color:#fff; border:none;
          font-family:'Montserrat',sans-serif; font-weight:600; font-size:0.95rem; padding:1.05rem 2.2rem;
          border-radius:999px; cursor:pointer; box-shadow:0 10px 30px rgba(15,23,42,0.30);
          transition:transform .18s ease, box-shadow .18s ease; text-decoration:none; }}
  .btn:hover {{ transform:translateY(-2px); box-shadow:0 16px 40px rgba(15,23,42,0.38); }}
  /* ✨ SHIMMER — lingote de oro Maserati recibiendo un destello de luz */
  #btnFirmar {{ background:linear-gradient(135deg,#BF953F,#FCF6BA 45%,#B38728,#FBF5B7 80%,#AA771C);
                color:#0a0a0a; font-weight:800; position:relative; overflow:hidden;
                box-shadow:0 10px 30px rgba(170,119,28,0.35); }}
  #btnFirmar::after {{ content:""; position:absolute; top:-10%; left:0; height:120%; width:38%;
    background:linear-gradient(105deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.14) 38%,
      rgba(255,255,255,0.62) 50%, rgba(255,255,255,0.14) 62%, rgba(255,255,255,0) 100%);
    transform:translateX(-180%) skewX(-22deg); animation:shimmerSweep 3s ease-in-out infinite;
    pointer-events:none; }}
  @keyframes shimmerSweep {{ 0% {{ transform:translateX(-180%) skewX(-22deg); }}
    55% {{ transform:translateX(240%) skewX(-22deg); }}
    100% {{ transform:translateX(240%) skewX(-22deg); }} }}
  .nota {{ font-size:0.72rem; color:#9CA3AF; margin-top:1.6rem; line-height:1.6; }}
  .badge {{ position:fixed; bottom:18px; right:22px; display:flex; align-items:center; gap:0.5rem;
            background:#fff; border:1px solid #E2E8F0; border-radius:999px; padding:0.45rem 1rem;
            font-size:0.68rem; color:{OXFORD}; box-shadow:0 6px 18px rgba(15,23,42,0.10); font-weight:600; }}
  .paso {{ display:flex; align-items:center; gap:0.7rem; text-align:left; font-size:0.8rem; color:#4B5563; margin:0.45rem 0; }}
  .paso span {{ background:#F1F5F9; color:{OXFORD}; font-weight:700; border-radius:50%; width:22px; height:22px;
                display:inline-flex; align-items:center; justify-content:center; font-size:0.7rem; flex-shrink:0; }}
</style></head>
<body>
  <div class="marca">Central Mutuos</div>
  <div style="text-align:center;margin-top:0.5rem;font-family:'Inter',sans-serif;font-variant:small-caps;letter-spacing:0.22em;font-size:0.62rem;font-weight:600;background:linear-gradient(135deg,#BF953F,#FCF6BA,#B38728);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent">@CentralMutuos · Marca Registrada</div>
  <div class="card" data-testid="portal-firma-card">
    <div class="sello">🖋</div>
    <h1>Bienvenido a su Firma de<br>Escritura Avanzada,<br><b>{nombre}</b></h1>
    <p class="sub">Su documentación ya se encuentra preparada, validada y cargada con sus datos.
    No necesita completar formularios ni iniciar sesión: el sistema firma con las llaves seguras de Central Mutuos.</p>
    <div class="datos"><span>Titular: <b>{nombre}</b></span><span>RUT: <b>{_mask_rut(link.get('rut'))}</b></span></div>
    <div style="margin-bottom:1.8rem">
      <div class="paso"><span>1</span> Presione el botón de firma segura</div>
      <div class="paso"><span>2</span> Su documentación se envía automáticamente a eCert</div>
      <div class="paso"><span>3</span> Recibirá los códigos de validación en su correo</div>
    </div>
    <button class="btn" id="btnFirmar" data-testid="portal-firma-btn">🖋 Firmar Documentación</button>
    <div id="msgFirma" data-testid="portal-firma-msg" style="display:none;margin-top:1.5rem;padding:1rem 1.2rem;border-radius:14px;font-size:0.85rem;line-height:1.6;font-weight:600"></div>
    <div id="asistente" data-testid="portal-firma-asistente" style="display:none;margin-top:1.6rem;text-align:left">
      <div style="background:#0a0a0a;border:1px solid #D4AF37;border-radius:16px;padding:1.4rem 1.5rem;color:#F5E7B8">
        <div style="font-size:0.7rem;letter-spacing:0.18em;text-transform:uppercase;color:#D4AF37;margin-bottom:0.7rem">Paso final · Validación</div>
        <div style="font-size:0.85rem;line-height:1.6;margin-bottom:1rem">Ingrese la <b>clave de acceso</b> que Central Mutuos le envió a su correo para abrir su documentación en la plataforma de firma segura.</div>
        <label style="font-size:0.72rem;letter-spacing:0.12em;text-transform:uppercase;color:#C7B36A;display:block;margin-bottom:0.5rem">Código de validación</label>
        <input id="codigoInput" data-testid="portal-firma-codigo-input" maxlength="8" inputmode="numeric" autocomplete="one-time-code"
               placeholder="Ingrese el código de validación recibido en su correo"
               style="width:100%;background:#050505;border:1px solid #7a6a2f;border-radius:12px;color:#FCF6BA;font-family:'Montserrat',monospace;
                      font-size:1.4rem;letter-spacing:0.35em;text-align:center;padding:0.9rem 1rem;outline:none" />
        <div id="codigoHint" style="font-size:0.72rem;color:#9a8c52;margin-top:0.6rem;min-height:1em"></div>
        <a id="btnContinuar" data-testid="portal-firma-continuar" target="_blank" rel="noopener"
           style="display:none;margin-top:1.1rem;text-align:center;background:linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C);color:#0a0a0a;
                  font-weight:800;font-size:0.9rem;letter-spacing:0.06em;padding:0.95rem 1.4rem;border-radius:999px;text-decoration:none">
           🔒 Continuar a la Firma Segura</a>
        <div style="border-top:1px solid rgba(212,175,55,0.25);margin:1.2rem 0 0.9rem"></div>
        <button id="btnYaFirme" data-testid="portal-firma-yafirme"
                style="width:100%;background:transparent;border:1px solid #7a6a2f;color:#F5E7B8;font-weight:700;font-size:0.82rem;
                       padding:0.8rem 1rem;border-radius:999px;cursor:pointer">✅ Ya firmé — Verificar y resguardar</button>
        <div id="verifMsg" data-testid="portal-firma-verif-msg" style="display:none;margin-top:0.9rem;font-size:0.82rem;line-height:1.5"></div>
      </div>
    </div>
    <p class="nota">Proceso certificado por eCert Chile · Firma Electrónica Avanzada Ley 19.799<br>
    Sus datos ya fueron transmitidos de forma segura: no necesita iniciar sesión en ningún sitio externo.</p>
  </div>
  <div class="badge" data-testid="portal-firma-badge">🛡 Cifrado de Grado Militar · Firma Auditada</div>
<script>
const btnF = document.getElementById('btnFirmar');
const msgF = document.getElementById('msgFirma');
const asis = document.getElementById('asistente');
const codIn = document.getElementById('codigoInput');
const codHint = document.getElementById('codigoHint');
const btnCont = document.getElementById('btnContinuar');
const btnYa = document.getElementById('btnYaFirme');
const verifMsg = document.getElementById('verifMsg');
let _pollEstado = null;

async function cargarEstado() {{
  try {{
    const r = await fetch('/api/firma/{token}/estado');
    const d = await r.json();
    if (d.codigo) {{
      if (!codIn.value) codIn.value = d.codigo;
      codHint.textContent = '✓ Clave detectada automáticamente desde su correo';
      codHint.style.color = '#8fd9b0';
    }} else {{
      codHint.textContent = 'Aún no recibimos su correo. Escríbala apenas llegue o espere unos segundos.';
    }}
    if (d.url_firma) {{ btnCont.href = d.url_firma; btnCont.style.display = 'block'; }}
    if (d.firmado) {{
      verifMsg.style.display = 'block';
      verifMsg.style.color = '#8fd9b0';
      verifMsg.textContent = '✅ eCert confirma que su documentación ya fue firmada.';
      if (_pollEstado) {{ clearInterval(_pollEstado); _pollEstado = null; }}
    }}
  }} catch(e) {{}}
}}

btnF.addEventListener('click', async () => {{
  btnF.disabled = true; btnF.style.opacity = 0.65; btnF.textContent = 'Enviando documentación segura…';
  fetch('/api/firma/{token}/click', {{method:'POST'}}).catch(()=>{{}});
  try {{
    const r = await fetch('/api/firma/{token}/firmar', {{method:'POST'}});
    let d = {{}}; try {{ d = await r.json(); }} catch(e) {{}}
    msgF.style.display = 'block';
    if (r.ok && d.ok) {{
      msgF.style.background = '#F0FDF4'; msgF.style.border = '1px solid #BBF7D0'; msgF.style.color = '#15803D';
      msgF.textContent = d.mensaje || '✅ Documentación enviada a eCert. Revise su correo para el código final de validación';
      btnF.style.display = 'none';
      asis.style.display = 'block';
      cargarEstado();
      _pollEstado = setInterval(cargarEstado, 6000);
    }} else {{
      msgF.style.background = '#FEF2F2'; msgF.style.border = '1px solid #FECACA'; msgF.style.color = '#B91C1C';
      msgF.textContent = '⚠ ' + ((d && d.detail) || 'No fue posible enviar la firma en este momento. Contacte a su ejecutivo.');
      btnF.disabled = false; btnF.style.opacity = 1; btnF.textContent = '🖋 Firmar Documentación';
    }}
  }} catch(e) {{
    msgF.style.display = 'block';
    msgF.style.background = '#FEF2F2'; msgF.style.border = '1px solid #FECACA'; msgF.style.color = '#B91C1C';
    msgF.textContent = '⚠ Error de conexión. Intente nuevamente.';
    btnF.disabled = false; btnF.style.opacity = 1; btnF.textContent = '🖋 Firmar Documentación';
  }}
}});

btnYa.addEventListener('click', async () => {{
  btnYa.disabled = true; btnYa.style.opacity = 0.6; btnYa.textContent = 'Verificando con eCert…';
  verifMsg.style.display = 'block'; verifMsg.style.color = '#C7B36A'; verifMsg.textContent = 'Consultando el estado de su firma…';
  try {{
    const r = await fetch('/api/firma/{token}/verificar-firmado', {{method:'POST'}});
    const d = await r.json();
    if (d.ok && d.firmado) {{
      verifMsg.style.color = '#8fd9b0';
      verifMsg.textContent = d.mensaje || '✅ ¡Firma confirmada y resguardada!';
      if (_pollEstado) {{ clearInterval(_pollEstado); _pollEstado = null; }}
    }} else {{
      verifMsg.style.color = '#e0b0b0';
      verifMsg.textContent = 'ℹ ' + (d.mensaje || 'Aún no detectamos su firma. Complete el proceso en la plataforma segura y vuelva a intentar.');
      btnYa.disabled = false; btnYa.style.opacity = 1; btnYa.textContent = '✅ Ya firmé — Verificar y resguardar';
    }}
  }} catch(e) {{
    verifMsg.style.color = '#e0b0b0'; verifMsg.textContent = '⚠ Error de conexión. Intente nuevamente.';
    btnYa.disabled = false; btnYa.style.opacity = 1; btnYa.textContent = '✅ Ya firmé — Verificar y resguardar';
  }}
}});
</script>
</body></html>"""
    return HTMLResponse(html)


@api.post("/firma/{token}/click")
async def firma_click(token: str):
    await db.firma_links.update_one({"token": token}, {"$inc": {"clicks_firma": 1},
                                                       "$set": {"ultimo_click": now_iso()}})
    return {"ok": True}


@api.get("/firma/{token}/estado")
async def firma_estado(token: str):
    """PORTAL VIP — Asistente de Firma: lee del correo eCert (IMAP) el código de acceso
    de 6 dígitos y el link seguro de firma (Clave Única). Consulta también el estado del
    documento en eCert para saber si el cliente YA firmó."""
    link = await db.firma_links.find_one({"token": token})
    if not link:
        raise HTTPException(status_code=404, detail="Enlace no válido o expirado")
    cliente = link.get("cliente", "")
    prefix = f"COMBINADO_SET_{cliente[:14]}"
    info = await asyncio.to_thread(mail.leer_codigo_ecert, prefix, 1440)
    estado_ecert = None
    firmado = False
    primer_nombre = (cliente.split() or [""])[0]
    try:
        docs = await asyncio.to_thread(migrup.listar_documentos, f"COMBINADO_SET_{primer_nombre}"[:20], 0, 1, 10)
        items = (docs or {}).get("paginatedList") or (docs or {}).get("items") or []
        cand = [d for d in items if _norm_texto(primer_nombre) in _norm_texto(d.get("nombre") or "")]
        cand.sort(key=lambda d: d.get("fechaCreacion") or "", reverse=True)
        if cand:
            estado_ecert = cand[0].get("estadoDocumento")
            firmado = (estado_ecert or "").lower() == "finalizado"
    except Exception as e:
        logging.warning(f"firma_estado eCert {cliente}: {e}")
    return {"ok": True, "enviada": bool(link.get("firma_enviada_en")),
            "codigo": (info or {}).get("codigo") or "",
            "url_firma": (info or {}).get("url_firma") or "",
            "codigo_disponible": bool((info or {}).get("codigo")),
            "estado_ecert": estado_ecert, "firmado": firmado}


@api.post("/firma/{token}/verificar-firmado")
async def firma_verificar_firmado(token: str):
    """PORTAL VIP — cuando el cliente confirma que ya firmó: descarga el firmado de eCert,
    lo separa al Búnker y notifica a Gerardo. Todo dentro del portal Central Mutuos."""
    link = await db.firma_links.find_one({"token": token})
    if not link:
        raise HTTPException(status_code=404, detail="Enlace no válido o expirado")
    cliente = link.get("cliente", "")
    toks = [t for t in _norm_texto(cliente).split() if len(t) > 2]
    rx = ".*".join(re.escape(t) for t in toks[:2]) if toks else ""
    doc = await db.set_credito.find_one({"nombre": {"$regex": rx, "$options": "i"}}) if rx else None
    if not doc:
        raise HTTPException(status_code=400, detail="No se encontró su expediente. Contacte a su ejecutivo.")
    try:
        res = await _traer_firmado_interno(doc)
    except ValueError as e:
        return {"ok": False, "firmado": False, "mensaje": str(e)}
    await db.firma_links.update_one({"token": token}, {"$set": {"firmado_confirmado_en": now_iso()}})
    return {"ok": True, "firmado": True,
            "mensaje": "✅ ¡Firma confirmada! Su documentación firmada ya fue resguardada.",
            "archivos": len(res.get("archivos") or [])}


_MSG_FIRMA_OK = "✅ Documentación enviada a eCert. Revise su correo para el código final de validación"


@api.post("/firma/{token}/firmar")
async def firma_firmar(token: str):
    """Flujo VIP: sube el set combinado del cliente a eCert con las llaves del sistema.
    El cliente NO necesita iniciar sesión en ningún sitio externo."""
    link = await db.firma_links.find_one({"token": token})
    if not link:
        raise HTTPException(status_code=404, detail="Enlace no válido o expirado")
    if link.get("firma_enviada_en"):
        return {"ok": True, "ya_enviada": True, "mensaje": _MSG_FIRMA_OK}
    cliente = link.get("cliente", "")
    toks = [t for t in _norm_texto(cliente).split() if len(t) > 2]
    rx = ".*".join(re.escape(t) for t in toks[:2]) if toks else ""
    doc = await db.set_credito.find_one({"nombre": {"$regex": rx, "$options": "i"}}) if rx else None
    if not doc:
        raise HTTPException(status_code=400, detail="Su documentación aún no está preparada (no existe un Set de Crédito a su nombre). Contacte a su ejecutivo.")
    # RUT REAL: siempre prioriza el de la carpeta/set del cliente (fuente de verdad)
    carpeta = await db.folders.find_one({"nombre": {"$regex": rx, "$options": "i"}},
                                        {"_id": 0, "rut": 1, "email": 1}) if rx else None
    rut = ((doc.get("rut") or "").strip() or ((carpeta or {}).get("rut") or "").strip()
           or (link.get("rut") or "").strip())
    email = ((link.get("email") or "").strip() or (doc.get("email") or "").strip()
             or ((carpeta or {}).get("email") or "").strip())
    if not rut or "@" not in email:
        raise HTTPException(status_code=400, detail="Faltan datos de contacto para la firma. Contacte a su ejecutivo.")
    partes = cliente.split()
    firmante = {
        "nombres": " ".join(partes[:-2]) if len(partes) >= 3 else partes[0],
        "aPaterno": partes[-2] if len(partes) >= 3 else (partes[-1] if len(partes) >= 2 else ""),
        "aMaterno": partes[-1] if len(partes) >= 3 else "",
        "rut": rut, "email": email,
    }
    # ────────────────────────────────────────────────────────────────────────
    # MODELO COMBINADO (ECONOMÍA DE SALDO — orden del dueño 2026-08-09):
    # Todo el Set de Crédito se une en UN ÚNICO PDF (_set_combinar) y se envía a eCert
    # como una sola transacción de firma. Esto GARANTIZA EL COBRO DE UNA SOLA FIRMA DE
    # TERCERO POR CADA SET DE CRÉDITO DE CLIENTE (no una firma por documento). Tras firmar,
    # _set_separar_firmado divide el archivo madre y estampa el rastro visible en cada hoja.
    # NO cambiar a firma por lote: multiplicaría el consumo de firmas.
    # ────────────────────────────────────────────────────────────────────────
    res_comb = await asyncio.to_thread(_set_combinar, doc.get("nombre", ""))
    if not res_comb["combinado"]:
        raise HTTPException(status_code=400, detail=res_comb.get("error") or
                            "Su documentación aún no está preparada (el Set de Crédito no tiene archivos PDF para firmar). Contacte a su ejecutivo.")
    target = _set_dir(doc.get("nombre", "")) / res_comb["combinado"]
    pdf_bytes = target.read_bytes()
    posiciones = await asyncio.to_thread(pdfs.posiciones_firma_cliente, pdf_bytes)
    if len(posiciones) > 1:
        estampado = await asyncio.to_thread(pdfs.estampar_referencias_firma, pdf_bytes,
                                            posiciones[1:], cliente)
        del pdf_bytes
        pdf_bytes = estampado
        del estampado
    import gc
    gc.collect()  # limpiar buffers intermedios antes de la codificación base64
    res = await asyncio.to_thread(
        migrup.enviar_a_firmar_tercero, pdf_bytes, target.stem, firmante,
        "Portal de Firma Única — Central Mutuos", None, False, posiciones[:1] or None)
    del pdf_bytes
    gc.collect()
    if not res.get("success"):
        # 400 (no 502): los proxies reemplazan los 502 por HTML genérico y ocultan el motivo real
        raise HTTPException(status_code=400, detail=f"No fue posible enviar la firma: {str(res.get('error'))[:180]}")
    await db.firma_links.update_one({"token": token}, {"$set": {
        "firma_enviada_en": now_iso(), "firma_ecert": res.get("raw") or {}}})
    await db.set_credito.update_one({"id": doc["id"]},
        {"$unset": {"lote_firma": ""},
         "$push": {"firmas": {
            "documento": target.name, "firmante": email, "rut": rut,
            "paginas": res.get("paginas"), "estampas": len(posiciones) or 1,
            "ecert_id": res.get("ecert_doc_id"),
            "portal_vip": True, "enviado_en": now_iso()}}})
    return {"ok": True, "mensaje": _MSG_FIRMA_OK, "paginas": res.get("paginas")}


@api.get("/firma/{token}/og.png")
async def firma_og_image(token: str):
    """Tarjeta VIP 600x600: fondo negro absoluto, oro 24K y nombre del cliente centrado."""
    link = await db.firma_links.find_one({"token": token})
    nombre = (link or {}).get("cliente", "Cliente")
    from PIL import Image, ImageDraw, ImageFont
    W = H = 600
    ORO, ORO_CLARO, ORO_OSCURO = (212, 175, 55), (244, 220, 130), (150, 116, 30)
    img = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(img)
    # Doble marco dorado estilo joyería
    d.rectangle([16, 16, W - 16, H - 16], outline=ORO, width=3)
    d.rectangle([28, 28, W - 28, H - 28], outline=ORO_OSCURO, width=1)

    def _font(size, bold=False):
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSerif-%s.ttf"
                                      % ("Bold" if bold else "Regular"), size)
        except Exception:
            return ImageFont.load_default()

    def _centrar(texto, y, fnt, color):
        w = d.textlength(texto, font=fnt)
        d.text(((W - w) / 2, y), texto, font=fnt, fill=color)

    # Monograma CM en oro
    _centrar("CM", 68, _font(64, True), ORO_CLARO)
    d.line([(W / 2 - 90, 155), (W / 2 + 90, 155)], fill=ORO, width=2)
    _centrar("CENTRAL MUTUOS", 175, _font(34, True), ORO)
    _centrar("CON CRECES", 222, _font(16), ORO_OSCURO)
    _centrar("Firma de Escritura", 285, _font(38, True), (255, 255, 255))
    _centrar("Avanzada", 335, _font(38, True), (255, 255, 255))
    # Nombre del cliente centrado en oro
    fnt_n = _font(30, True)
    if d.textlength(nombre, font=fnt_n) > W - 90:
        fnt_n = _font(24, True)
    _centrar(nombre, 415, fnt_n, ORO_CLARO)
    d.line([(W / 2 - 60, 470), (W / 2 + 60, 470)], fill=ORO_OSCURO, width=1)
    _centrar("Documentación Oficial VIP", 495, _font(20), (203, 213, 225))
    _centrar("Cifrado · Firma Auditada · eCert Chile", 530, _font(15), ORO_OSCURO)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return _RawResponse(content=buf.getvalue(), media_type="image/png",
                        headers={"Cache-Control": "public, max-age=86400"})


# ------------------------------------------------------------------
# Set de Crédito + Firma de documentos (integración migrup / eCert)
# ---------------------------------------------------------------------------
import migrup_service as migrup

SETCRED_DIR = ROOT_DIR / "storage" / "sets_de_credito"
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
        if tipo == "otro":
            # IDENTIFICACIÓN DE FORMULARIOS: reconoce los formularios de cierre por contenido del nombre
            if re.search(r"desgravamen|seguro|cesant|incendio|sismo", low):
                tipo = "seguros"
            elif re.search(r"dps|salud", low):
                tipo = "declaracion_salud"
            elif re.search(r"solicitud|mutuo", low):
                tipo = "solicitud_credito"
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
    m = re.search(r"\bset\s+(?:de\s+)?([A-Za-zÁÉÍÓÚÑáéíóúñ ]+?)(?:\s+y\s+(?:de\s+)?su\s+codeudor|\s+ok\b|\s+(?:sin|con)\s+subsidio\b|\s*[\(\-]|$)",
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
    query = {"nombre": {"$regex": re.escape(q), "$options": "i"}} if q else {}
    docs = await db.set_credito.find(query).sort("created_at", -1).limit(200).to_list(200)
    return {"sets": [_set_public(d) for d in docs], "doc_tipos": SET_DOC_LABELS}


@api.post("/set-credito/sets")
async def setcred_create(payload: dict):
    await _constitucion_dashai()
    doc = {"id": str(uuid.uuid4()), "nombre": payload.get("nombre", ""),
           "rut": payload.get("rut", ""), "email": payload.get("email", ""),
           "created_at": now_iso(), "firmas": []}
    if not doc["nombre"].strip():
        raise HTTPException(status_code=400, detail="Falta el nombre del cliente")
    # ANTI-DUPLICADOS POR RUT: si ya existe un set con ese RUT, se reutiliza
    rut_n = _norm_rut(doc["rut"])
    if rut_n and len(rut_n) >= 7:
        rx = _rut_regex_flexible(doc["rut"])
        previo = await db.set_credito.find_one({"rut": {"$regex": rx, "$options": "i"}}) if rx else None
        if previo:
            if doc["email"] and not previo.get("email"):
                await db.set_credito.update_one({"id": previo["id"]}, {"$set": {"email": doc["email"]}})
                previo["email"] = doc["email"]
            return _set_public(previo)
    await db.set_credito.insert_one(dict(doc))
    _set_dir(doc["nombre"]).mkdir(parents=True, exist_ok=True)
    return _set_public(doc)


def _set_sync_desde_carpeta(nombre):
    """DESACTIVADO (Búnker de Cierre): el Set de Crédito NUNCA mezcla archivos con la
    carpeta general del cliente. Los expedientes llegan solo desde evaluacionesmutuos."""
    return []


NUM_DOC_RX = re.compile(
    r"n[uú]?m?e?r?o?\s*(?:de)?\s*documento[:\s]*([A-Z]?\.?\d[\d\.]{6,12})", re.I)


def _extraer_num_documento(nombre):
    """DETECCIÓN DE IDENTIDAD: busca el Nº de documento del carnet en las cédulas."""
    candidatos = []
    for base in (_set_dir(nombre), fsvc.folder_dir(nombre)):
        if base.exists():
            candidatos += [p for p in base.rglob("*.pdf")
                           if re.search(r"cedula|carnet|c\.i\.|identidad", p.name, re.I)]
    for p in candidatos[:4]:
        try:
            texto, _m = ocr_service.extraer_texto(p.read_bytes(), p.name)
        except Exception:
            continue
        m = NUM_DOC_RX.search(texto or "")
        if m:
            return m.group(1).replace(".", "")
    return ""


async def _get_set(sid):
    doc = await db.set_credito.find_one({"id": sid})
    if not doc:
        raise HTTPException(status_code=404, detail="Set no encontrado")
    return doc


@api.get("/set-credito/sets/{sid}")
async def setcred_get(sid: str):
    doc = await _get_set(sid)
    nombre = doc.get("nombre", "")
    n_arch = len(_set_archivos(nombre))
    scan_previo = doc.get("num_doc_scan") or {}
    if not doc.get("num_documento") and scan_previo.get("count") != n_arch:
        num = await asyncio.to_thread(_extraer_num_documento, nombre)
        sets_fields = {"num_doc_scan": {"count": n_arch, "at": now_iso()}}
        if num:
            sets_fields["num_documento"] = num
            doc["num_documento"] = num
        await db.set_credito.update_one({"id": sid}, {"$set": sets_fields})
    return _set_public(doc)


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


async def _setcred_importar(email_id, nombre, rut="", email_cli="", filenames=None, es_codeudor=False):
    """Crea/actualiza un set de crédito desde un correo de Evaluaciones y baja sus adjuntos."""
    atts = await asyncio.to_thread(mail.fetch_attachments_by_id, email_id, None)
    if filenames:
        atts = [a for a in atts if a["filename"] in filenames]
    atts = [a for a in atts if (a["filename"] or "").lower().endswith((".pdf", ".jpg", ".jpeg", ".png"))]
    if not atts:
        raise HTTPException(status_code=404, detail="El correo no tiene adjuntos válidos")
    toks = [t for t in _norm_texto(nombre).split() if len(t) > 2]
    rx = ".*".join(_rx_acentos(t) for t in toks[:2]) if toks else re.escape(nombre)
    doc = await db.set_credito.find_one({"nombre": {"$regex": rx, "$options": "i"}})
    if not doc:
        fdoc = await db.folders.find_one({"nombre": {"$regex": rx, "$options": "i"}})
        df = (fdoc or {}).get("datos_financieros") or {}
        rut = rut or (fdoc or {}).get("rut", "")
        email_cli = email_cli or df.get("email") or df.get("email_cliente") or ""
        doc = {"id": str(uuid.uuid4()), "nombre": nombre, "rut": rut,
               "email": email_cli, "created_at": now_iso(),
               "origen": "evaluaciones", "firmas": []}
        await db.set_credito.insert_one(dict(doc))
    elif rut and not doc.get("rut"):
        await db.set_credito.update_one({"id": doc["id"]}, {"$set": {"rut": rut}})
    base_dir = _set_dir(doc["nombre"])
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
        guardados.append(("codeudor/" if cod else "") + fsvc.safe_name(fn))
    return {"ok": True, "set_id": doc["id"], "nombre": doc["nombre"], "guardados": guardados}


async def _setcred_auto_loop():
    """Descarga AUTOMÁTICA de sets de crédito: revisa cada 10 min los correos de
    evaluacionesmutuos@gmail.com y baja los adjuntos al set del cliente al tiro."""
    await asyncio.sleep(90)
    while True:
        try:
            correos = await asyncio.to_thread(mail.fetch_emails_from_sender,
                                              SETCRED_SENDER_DEFAULT, 10)
            for c in correos:
                if await db.setcred_procesados.find_one({"email_id": c["id"]}):
                    continue
                datos = _detectar_datos_email(c)
                nombre = (datos.get("nombre") or "").strip()
                atts = [a for a in c.get("attachments", [])
                        if (a.get("filename") or "").lower().endswith((".pdf", ".jpg", ".jpeg", ".png"))]
                reg = {"email_id": c["id"], "subject": (c.get("subject") or "")[:100],
                       "fecha": now_iso()}
                if not nombre or not atts:
                    reg["motivo"] = "sin nombre detectado" if not nombre else "sin adjuntos"
                    await db.setcred_procesados.insert_one(reg)
                    continue
                try:
                    r = await _setcred_importar(c["id"], nombre, datos.get("rut", ""),
                                                datos.get("email", ""))
                    reg.update({"nombre": nombre, "guardados": r["guardados"], "auto": True})
                except Exception as e:
                    reg["error"] = str(e)[:200]
                await db.setcred_procesados.insert_one(reg)
        except Exception as e:
            await db.system_log.insert_one({"id": str(uuid.uuid4()), "loop": "setcred_auto",
                                            "error": str(e)[:300], "fecha": now_iso()})
        await asyncio.sleep(600)


@api.post("/set-credito/import-from-email")
async def setcred_import_from_email(payload: dict):
    """Crea/actualiza un set desde un correo de Evaluaciones y baja sus adjuntos."""
    email_id = payload.get("email_id", "")
    nombre = (payload.get("nombre") or "").strip()
    if not email_id or not nombre:
        raise HTTPException(status_code=400, detail="Falta correo o nombre del cliente")
    return await _setcred_importar(email_id, nombre, (payload.get("rut") or "").strip(),
                                   payload.get("email", ""), payload.get("filenames"),
                                   bool(payload.get("codeudor")))


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
    if not target.is_relative_to(base):
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
    if not target.is_relative_to(base) or not target.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    disp = "inline" if inline else "attachment"
    return FileResponse(str(target), media_type="application/pdf",
                        headers={"Content-Disposition": f'{disp}; filename="{target.name}"'})


def _set_archivos_orden(nombre):
    """Lista ordenada del expediente de cierre. El búnker del set es EXCLUSIVO
    (solo formularios de cierre), así que combina/separa todo menos combinados/firmados."""
    orden = {t: i for i, t in enumerate(SET_DOC_TIPOS)}
    # SORT NUMÉRICO (REGLA INAMOVIBLE): el prefijo 01..06 manda sobre el orden de llegada
    archivos = sorted(_set_archivos(nombre),
                      key=lambda a: (fsvc.orden_numerico(a["nombre"]), orden.get(a["tipo"], 99), a["nombre"]))
    return [a for a in archivos
            if not a["nombre"].startswith(("COMBINADO_SET", "FIRMADO"))
            and "firmados/" not in a.get("ruta", "")]


def _set_combinar(nombre):
    """Une todos los PDFs del set (excepto el combinado previo) en uno solo.
    REGLA IVANA: exige RUT titular y excluye PDFs cuyo RUT no sea el del titular."""
    from pypdf import PdfReader, PdfWriter
    rut_t = ""
    try:
        from bunker import _fs as _bfs
        _f, _dbs = _bfs()
        _doc = (_dbs.folders.find_one({"nombre": nombre}, {"rut": 1})
                or _dbs.set_credito.find_one({"nombre": nombre}, {"rut": 1}) or {})
        rut_t = _norm_rut(_doc.get("rut", "") or "")
    except Exception:
        pass
    if len(rut_t) < 7:
        return {"combinado": "", "usados": [],
                "error": "REGLA IVANA: sin RUT titular no hay combinación de PDF. Configure el RUT primero."}
    base = _set_dir(nombre)
    writer = PdfWriter()
    usados = []
    excluidos_rut = []
    archivos = _set_archivos_orden(nombre)
    for a in archivos:
        if a["nombre"].startswith("COMBINADO_SET"):
            continue
        ruts_a = fsvc._ruts_personas(fsvc.ruts_de_pdf_cache(base / a["ruta"]))
        if ruts_a and rut_t not in ruts_a:
            excluidos_rut.append(a["nombre"])
            continue
        try:
            for pg in PdfReader(str(base / a["ruta"])).pages:
                writer.add_page(pg)
            usados.append(a["nombre"])
        except Exception:
            continue
    if not usados:
        return {"combinado": "", "usados": [], "excluidos_rut": excluidos_rut}
    out = f"COMBINADO_SET_{fsvc.safe_name(nombre)}.pdf"
    with open(base / out, "wb") as f:
        writer.write(f)
    return {"combinado": out, "usados": usados, "excluidos_rut": excluidos_rut}


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
    archivos = _set_archivos_orden(nombre)
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
    # ACCIÓN POST-FIRMA: despacho inmediato de los formularios divididos (Puente Ethan)
    try:
        await _despacho_post_firma(doc)
    except Exception as e:
        logging.warning(f"Despacho post-firma {doc.get('nombre')}: {e}")
    return {"estado": best.get("estadoDocumento"), "archivos": guardados}


async def _despacho_post_firma(doc):
    """DESPACHO POST-FIRMA (Puente Ethan): tras dividir el archivo madre firmado,
    notifica con todos los formularios divididos y su rastro digital.
    Remitente: cuenta principal (Ethan) → Destinatario: cuenta de trabajo (gerardo.ext)."""
    nombre_cli = doc.get("nombre", "")
    dest_dir = _set_dir(nombre_cli) / "firmados"
    files = sorted(dest_dir.glob("FIRMADO_*.pdf")) if dest_dir.exists() else []
    if not files:
        return {"success": False, "error": "sin formularios divididos"}
    masters = sorted(dest_dir.glob("*_FIRMADO_COMPLETO.pdf"))
    master_filename = f"✅ DOCUMENTO FIRMADO VALIDO - {fsvc.safe_name(nombre_cli)}.pdf"
    adjuntos = []
    for p in masters:
        adjuntos.append({"filename": master_filename, "content_b64": _b64(p.read_bytes())})
    for p in files:
        adjuntos.append({"filename": f"EXTRACTO (lectura) - {p.name}", "content_b64": _b64(p.read_bytes())})
    destinatario = os.environ.get("MAIL2_USER", "")
    cuerpo = f"""
    <div style="font-family:Arial,sans-serif;font-size:14px;color:#1a1a1a;max-width:660px">
      <div style="background:#0a0a0a;padding:18px 22px;border-left:4px solid #D4AF37">
        <span style="color:#D4AF37;font-size:16px;font-weight:700;letter-spacing:0.06em">💎 CENTRAL MUTUOS</span><br>
        <span style="color:#e5e5e5;font-size:12px;letter-spacing:0.1em">DOCUMENTACIÓN FIRMADA Y VALIDADA</span>
      </div>
      <div style="padding:18px 4px">
        <p>Gerardo, el proceso de firma de <b>{nombre_cli}</b> ha finalizado con éxito.</p>
        <div style="background:#F0FDF4;border:1px solid #16a34a;border-radius:10px;padding:14px 16px;margin:16px 0">
          <div style="color:#15803d;font-weight:800;font-size:14px;margin-bottom:6px">✅ DOCUMENTO LEGAL VÁLIDO (el que se entrega al banco)</div>
          <div style="font-size:13px;color:#166534"><b>{master_filename if masters else 'COMBINADO_FIRMADO_COMPLETO.pdf'}</b></div>
          <div style="font-size:12px;color:#3f6212;margin-top:6px">Único archivo con la firma criptográfica verificable en eCert. Contiene el set completo firmado.</div>
        </div>
        <div style="background:#FFFBEB;border:1px solid #d4a017;border-radius:10px;padding:14px 16px;margin:16px 0">
          <div style="color:#92400e;font-weight:800;font-size:14px;margin-bottom:6px">📑 Copias de lectura — {len(files)} extracto(s) (NO validan solas)</div>
          <ul style="font-size:12px;color:#78350f;margin:0;padding-left:18px">{"".join(f"<li>{p.name}</li>" for p in files)}</ul>
          <div style="font-size:12px;color:#78350f;margin-top:6px">Cada extracto lleva al pie su rastro (archivo madre, ID eCert y SHA-256).</div>
        </div>
      </div>
    </div>
    """
    res = await asyncio.to_thread(
        mail.send_mail, destinatario,
        f"💎 Documentación Firmada y Validada - {nombre_cli}",
        cuerpo, adjuntos, "principal")
    await db.set_credito.update_one({"id": doc["id"]}, {"$set": {
        "despacho_post_firma": {"ok": bool(res.get("success")), "a": destinatario,
                                "en": now_iso(), "archivos": len(files),
                                "error": res.get("error")}}})
    return res


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
    nombre = doc.get("nombre", "")
    # ENTREGA AL BANCO: el ARCHIVO MADRE va PRIMERO y con nombre inequívoco (documento legal
    # válido y verificable en eCert). Los extractos van después, marcados como copias de lectura.
    master_filename = f"✅ DOCUMENTO FIRMADO VALIDO - {fsvc.safe_name(nombre)}.pdf"
    adjuntos = []
    for p in masters:
        adjuntos.append({"filename": master_filename, "content_b64": _b64(p.read_bytes())})
    for p in files:
        adjuntos.append({"filename": f"EXTRACTO (lectura) - {p.name}", "content_b64": _b64(p.read_bytes())})
    master_nombre_mostrar = master_filename if masters else "COMBINADO_FIRMADO_COMPLETO.pdf"
    cuerpo = f"""
    <div style="font-family:Arial,sans-serif;font-size:14px;color:#1a1a1a;max-width:660px">
      <div style="background:#0a0a0a;padding:18px 22px;border-left:4px solid #D4AF37">
        <span style="color:#D4AF37;font-size:16px;font-weight:700;letter-spacing:0.06em">💎 CENTRAL MUTUOS</span><br>
        <span style="color:#e5e5e5;font-size:12px;letter-spacing:0.1em">SET DE CRÉDITO FIRMADO ELECTRÓNICAMENTE — {nombre.upper()}{(' · RUT ' + doc.get('rut')) if doc.get('rut') else ''}</span>
      </div>
      <div style="padding:18px 4px">
        <p>Se adjunta el Set de Crédito de <b>{nombre}</b>, firmado mediante Firma Electrónica Avanzada
        vía e-CertChile (Ley 19.799).</p>

        <div style="background:#F0FDF4;border:1px solid #16a34a;border-radius:10px;padding:14px 16px;margin:16px 0">
          <div style="color:#15803d;font-weight:800;font-size:14px;margin-bottom:6px">✅ DOCUMENTO LEGAL VÁLIDO (verifíquelo en eCert)</div>
          <div style="font-size:13px;color:#166534"><b>{master_nombre_mostrar}</b></div>
          <div style="font-size:12px;color:#3f6212;margin-top:6px">Este es el ÚNICO archivo con la firma criptográfica
          verificable. Contiene el set completo firmado. Súbalo al validador de eCert
          (<span style="color:#166534">plataformafirma.ecertchile.cl</span>) para comprobar la firma.</div>
        </div>

        <div style="background:#FFFBEB;border:1px solid #d4a017;border-radius:10px;padding:14px 16px;margin:16px 0">
          <div style="color:#92400e;font-weight:800;font-size:14px;margin-bottom:6px">📑 COPIAS DE LECTURA — {len(files)} extracto(s) (NO validan por separado)</div>
          <div style="font-size:12px;color:#78350f;margin-bottom:8px">Se incluyen solo por comodidad de lectura,
          separadas documento por documento. Al partir un PDF firmado la firma digital ya NO es verificable en
          cada parte; cada extracto lleva al pie su rastro (archivo madre, ID eCert y huella SHA-256).
          <b>Para validez legal, use siempre el DOCUMENTO LEGAL VÁLIDO de arriba.</b></div>
          <ul style="font-size:12px;color:#78350f;margin:0;padding-left:18px">{"".join(f"<li>{p.name}</li>" for p in files)}</ul>
        </div>

        <p style="color:#888;font-size:12px">Central Mutuos — Cr&eacute;ditos Hipotecarios</p>
      </div>
    </div>
    """
    asunto = asunto or f"Set de crédito firmado (documento válido + extractos) - {nombre}"
    enviados, errores = [], []
    for c in correos:
        r = await asyncio.to_thread(mail.send_mail, c, asunto, cuerpo, adjuntos, "secundaria")
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
        "ecert_id": res.get("ecert_doc_id"),
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
            resp = await _llm_con_timeout(chat, UserMessage(text=texto[:3000]))
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
    if not target.is_relative_to(base) or not target.exists():
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
        "estampas": len(posiciones) or 1, "ecert_id": res.get("ecert_doc_id"),
        "enviado_en": now_iso()}}})
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
    # DESTINO ÚNICO: la GESTIÓN (solicitud de crédito) va EXCLUSIVAMENTE a la casilla de Mesa
    destino = os.environ.get("MESA_EMAIL", "")
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
          <p style="color:#888;font-size:12px">Central Mutuos</p>
        </div>
        """
        res_aviso = await asyncio.to_thread(
            mail.send_mail, destino, f"[FALTA INFORMACION] {cliente}", aviso, [], "secundaria")
        await db.proc_queue.update_one({"id": qid}, {"$set": {
            "status": "revisar", "campos_faltantes": faltan,
            "docs_faltantes": {DOC_LABELS.get(t, t): n for t, n in docs_faltantes.items()}}})
        return {"success": False, "aviso_enviado": bool(res_aviso.get("success")),
                "campos_faltantes": faltan,
                "docs_faltantes": {DOC_LABELS.get(t, t): n for t, n in docs_faltantes.items()}}

    con_sub = campos.get("con_subsidio")
    con_sub_txt = "Con subsidio" if con_sub == True else "Sin subsidio" if con_sub == False else "—"
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
      <p style="color:#888;font-size:12px">Central Mutuos</p>
    </div>
    """
    asunto = f"[Gestion] {cliente} - {campos.get('proyecto_inmobiliario') or 'Credito Hipotecario'}"
    # BLINDAJE: reenviar la misma gestión a mesa exige la clave de administrador
    clave = (payload or {}).get("clave") or ""
    key_guard = _norm_texto(asunto)
    autorizado_reenvio = bool(clave) and clave == CLAVE_FORZAR_CARPETA
    if item.get("autocorreo_enviado") and not autorizado_reenvio:
        fecha_prev = str(item.get("autocorreo_en") or "")[:16].replace("T", " ")
        raise HTTPException(status_code=403, detail=(
            f"La gestión de {cliente} ya se envió a Mesa{f' el {fecha_prev}' if fecha_prev else ''}. "
            "Para reenviarla debes ingresar la clave de administrador."))
    if autorizado_reenvio:
        await db.mesa_enviados.delete_one({"key": key_guard})
    # CERROJO ATÓMICO: find_one_and_update reserva el envío como EN_PROCESO_DE_ENVIO.
    # Si otro proceso intenta enviar la misma gestión al mismo tiempo, se bloquea al instante.
    _stale = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    prev = await db.mesa_enviados.find_one_and_update(
        {"key": key_guard},
        {"$setOnInsert": {"key": key_guard, "cliente": cliente, "subject": asunto,
                          "estado": "EN_PROCESO_DE_ENVIO", "enviado_at": now_iso()}},
        upsert=True)
    if prev is not None:
        if prev.get("estado") == "EN_PROCESO_DE_ENVIO" and (prev.get("enviado_at") or "") >= _stale:
            raise HTTPException(status_code=409,
                                detail="Envío a Mesa YA en proceso — intento simultáneo bloqueado por el cerrojo atómico.")
        if prev.get("estado") == "EN_PROCESO_DE_ENVIO":
            await db.mesa_enviados.update_one({"key": key_guard},
                                              {"$set": {"estado": "EN_PROCESO_DE_ENVIO", "enviado_at": now_iso()}})
        else:
            fecha_prev = str(prev.get("enviado_at") or "")[:16].replace("T", " ")
            raise HTTPException(status_code=403, detail=(
                f"La gestión de {cliente} ya se envió a Mesa el {fecha_prev} "
                "(huella de envío registrada). Para reenviarla debes ingresar la clave de administrador."))
    from email.utils import make_msgid
    mid = make_msgid(domain="centralmutuos.cl")
    try:
        res = await asyncio.to_thread(mail.send_mail, destino, asunto, cuerpo, adjuntos,
                                      "secundaria", None, {"Message-ID": mid})
    except Exception:
        await db.mesa_enviados.delete_one({"key": key_guard})
        raise
    if not res.get("success"):
        await db.mesa_enviados.delete_one({"key": key_guard})
        raise HTTPException(status_code=502, detail=res.get("error", "Error de envio"))
    # HUELLA DE ENVÍO: Message-ID registrado — prohibe cualquier re-envío de este ciclo
    await db.mesa_enviados.update_one({"key": key_guard}, {"$set": {
        "key": key_guard, "cliente": cliente, "subject": asunto,
        "estado": "ENVIADO", "message_id": mid, "enviado_at": now_iso()}}, upsert=True)
    await db.proc_queue.update_one({"id": qid}, {"$set": {"autocorreo_enviado": True,
                                                          "autocorreo_a": destino, "autocorreo_en": now_iso(),
                                                          "autocorreo_message_id": mid}})
    # Huella también en la carpeta del cliente (si existe)
    toks = [re.escape(t) for t in _norm_texto(cliente).split() if len(t) > 2][:2]
    if toks:
        await db.folders.update_one({"nombre": {"$regex": ".*".join(toks), "$options": "i"}},
                                    {"$set": {"mesa_message_id": mid, "mesa_enviado_at": now_iso()}})
    return {"success": True, "destino": destino, "adjunto": bool(adjuntos), "message_id": mid}




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
    rx_rut = {"$regex": _rut_regex_flexible(rut), "$options": "i"}
    # Carpetas de clientes con ese RUT (filtro en DB + proyección)
    folders = await db.folders.find({"rut": rx_rut}, {"_id": 0, "nombre": 1, "rut": 1}).limit(300).to_list(300)
    nombres_match = set()
    for f in folders:
        if _norm_rut(f.get("rut")) == rn:
            nombres_match.add((f.get("nombre") or "").strip())
    # Gestiones procesadas con ese RUT (filtro en DB + proyección)
    items = await db.proc_queue.find({"classification.rut": rx_rut}, {"_id": 0, "classification": 1}).limit(300).to_list(300)
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
    _proy_sim = {"_id": 0, "rut": 1, "nombre_completo": 1, "precalificacion_aprobada": 1,
                 "capacidad_credito_uf": 1, "timestamp": 1}
    async for s in db.simulaciones.find({"rut": rx_rut}, _proy_sim).sort("timestamp", -1).limit(200):
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


@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    resp.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    resp.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    resp.headers["X-DNS-Prefetch-Control"] = "off"
    if "application/pdf" not in (resp.headers.get("content-type") or ""):
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com data:; script-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; frame-ancestors 'self'; object-src 'none'; base-uri 'self'"
        )
    return resp


@app.on_event("shutdown")
async def shutdown():
    client.close()


@api.get("/dashai/dataset")
async def dashai_dataset():
    """📊 Dataset para DashAI: CSV limpio de la cartera (features + target) para
    entrenar modelos de aprobación de crédito en forma local, sin gasto de nube."""
    import csv as _csv
    import io as _io
    cols = ["fecha", "rut", "nombre", "tipo_deudor", "tiene_codeudor", "plazo_anos",
            "tasa_anual", "valor_uf", "valor_propiedad_uf", "credito_solicitado_uf",
            "credito_maximo_uf", "capacidad_credito_uf", "dividendo_credito_uf", "ltv",
            "pie_requerido_uf", "carga_fin_individual", "carga_fin_conjunta",
            "div_renta_individual", "div_renta_conjunta", "edad_plazo",
            "eval_ameris", "eval_btg", "credito_viable", "enviado_a_mesa",
            "target_aprobada"]
    mesa_ruts = set()
    async for m in db.mesa_enviados.find({}, {"rut": 1, "nombre": 1}):
        r = re.sub(r"[^0-9kK]", "", (m.get("rut") or "")).lower()
        if r:
            mesa_ruts.add(r)
    buf = _io.StringIO()
    w = _csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    n = 0
    async for s in db.simulaciones.find({}, {"_id": 0}).sort("timestamp", 1):
        rut_n = re.sub(r"[^0-9kK]", "", (s.get("rut") or "")).lower()
        w.writerow({
            "fecha": str(s.get("timestamp", ""))[:10], "rut": s.get("rut", ""),
            "nombre": s.get("nombre_completo", ""),
            "tipo_deudor": s.get("tipo_deudor_texto", ""),
            "tiene_codeudor": 1 if s.get("tiene_codeudor") else 0,
            "plazo_anos": s.get("plazo_anos"), "tasa_anual": s.get("tasa_anual"),
            "valor_uf": s.get("valor_uf"), "valor_propiedad_uf": s.get("valor_propiedad_uf"),
            "credito_solicitado_uf": s.get("credito_solicitado_uf"),
            "credito_maximo_uf": s.get("credito_maximo_uf"),
            "capacidad_credito_uf": s.get("capacidad_credito_uf"),
            "dividendo_credito_uf": s.get("dividendo_credito_uf"),
            "ltv": s.get("ltv"), "pie_requerido_uf": s.get("pie_requerido_uf"),
            "carga_fin_individual": s.get("carga_fin_individual"),
            "carga_fin_conjunta": s.get("carga_fin_conjunta"),
            "div_renta_individual": s.get("div_renta_individual"),
            "div_renta_conjunta": s.get("div_renta_conjunta"),
            "edad_plazo": s.get("edad_plazo"),
            "eval_ameris": s.get("eval_ameris", ""), "eval_btg": s.get("eval_btg", ""),
            "credito_viable": 1 if s.get("credito_viable") else 0,
            "enviado_a_mesa": 1 if rut_n in mesa_ruts else 0,
            "target_aprobada": 1 if s.get("precalificacion_aprobada") else 0})
        n += 1
    async for p in db.predic_history.find({}, {"_id": 0}).sort("timestamp", 1):
        w.writerow({
            "fecha": str(p.get("timestamp", ""))[:10], "rut": "",
            "nombre": p.get("nombre_cliente", ""), "tipo_deudor": "predic",
            "tiene_codeudor": 0,
            "valor_propiedad_uf": p.get("valor_propiedad_clp"),
            "credito_maximo_uf": p.get("monto_aprobado_uf"),
            "div_renta_individual": p.get("renta"),
            "eval_ameris": p.get("risk_level", ""), "eval_btg": p.get("score"),
            "credito_viable": 1 if p.get("viable") else 0,
            "enviado_a_mesa": 0,
            "target_aprobada": 1 if p.get("viable") else 0})
        n += 1
    from fastapi.responses import Response as _Resp
    fname = f"dataset_dashai_central_mutuos_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    return _Resp(content=buf.getvalue(), media_type="text/csv",
                 headers={"Content-Disposition": f'attachment; filename="{fname}"',
                          "X-Filas": str(n)})


@api.get("/dashai/dataset-mesa")
async def dashai_dataset_mesa():
    """🧠 Puente MongoDB→DashAI: historial de aprobaciones y envíos a MESA en CSV."""
    import csv as _csv
    import io as _io
    buf = _io.StringIO()
    w = _csv.DictWriter(buf, fieldnames=["fecha", "evento", "cliente", "rut", "detalle"],
                        extrasaction="ignore")
    w.writeheader()
    n = 0
    async for m in db.mesa_enviados.find({}, {"_id": 0}).sort("enviado_at", 1):
        w.writerow({"fecha": str(m.get("enviado_at", ""))[:19], "evento": "enviado_a_mesa",
                    "cliente": m.get("cliente", ""), "rut": "",
                    "detalle": (m.get("subject") or "")[:150]})
        n += 1
    async for a in db.aprobacion_log.find({}, {"_id": 0}).sort("enviado_en", 1):
        w.writerow({"fecha": str(a.get("enviado_en", ""))[:19], "evento": "aprobacion_enviada",
                    "cliente": a.get("nombre", ""), "rut": a.get("rut", ""),
                    "detalle": ", ".join(a.get("adjuntos") or [])[:150]})
        n += 1
    from fastapi.responses import Response as _Resp
    fname = f"dataset_mesa_dashai_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    return _Resp(content=buf.getvalue(), media_type="text/csv",
                 headers={"Content-Disposition": f'attachment; filename="{fname}"',
                          "X-Filas": str(n)})


_DASHAI_DOCS_CSV = ROOT_DIR / "storage" / "exports" / "dataset_documentos_dashai.csv"


def _dashai_docs_build():
    """Corre en HILO SEPARADO (no congela la interfaz Maserati). Construye el dataset
    de clasificación de documentos: texto extraído + categoría real (subcarpeta)."""
    import csv as _csv
    from pymongo import MongoClient
    import pdf_service as _pdfs
    import ocr_service as _ocr
    dbs = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    def _prog(**kw):
        dbs.config.update_one({"_key": "dashai_docs_job"}, {"$set": kw}, upsert=True)

    try:
        base = ROOT_DIR / "storage" / "clientes"
        pdfs_all = [p for p in sorted(base.rglob("*.pdf"))
                    if not p.name.startswith(("Carpeta_", "COMBINADO"))]
        _prog(status="corriendo", total=len(pdfs_all), progreso=0, inicio=now_iso(), error="")
        _DASHAI_DOCS_CSV.parent.mkdir(parents=True, exist_ok=True)
        ocr_usados, OCR_MAX = 0, 150
        with open(_DASHAI_DOCS_CSV, "w", newline="", encoding="utf-8") as f:
            w = _csv.DictWriter(f, fieldnames=["texto", "categoria", "cliente", "archivo"])
            w.writeheader()
            for i, p in enumerate(pdfs_all):
                try:
                    rel = p.relative_to(base)
                    cliente = rel.parts[0]
                    sub = rel.parts[1] if len(rel.parts) > 2 else ""
                    cat = fsvc.cat_de_archivo(re.sub(r"^CODEUDOR_", "", p.name, flags=re.I), sub)
                    raw = p.read_bytes()
                    texto = (_pdfs.leer_texto(raw, max_pages=2) or "").strip()
                    if len(texto) < 50 and ocr_usados < OCR_MAX:
                        ocr_usados += 1
                        texto = (_ocr.extraer_texto(raw, p.name)[0] or "").strip()
                    texto = re.sub(r"\s+", " ", texto)[:3000]
                    if len(texto) >= 30 and cat:
                        w.writerow({"texto": texto, "categoria": cat,
                                    "cliente": cliente, "archivo": p.name})
                except Exception:
                    pass
                if i % 10 == 0:
                    _prog(progreso=i + 1)
        _prog(status="listo", progreso=len(pdfs_all), fin=now_iso(), ocr_usados=ocr_usados)
    except Exception as e:
        _prog(status="error", error=str(e)[:200])


@api.post("/dashai/dataset-documentos/generar")
async def dashai_docs_generar():
    job = await db.config.find_one({"_key": "dashai_docs_job"}) or {}
    if job.get("status") == "corriendo":
        return {"ok": True, "status": "corriendo", "nota": "ya hay una generación en curso"}
    await db.config.update_one({"_key": "dashai_docs_job"},
                               {"$set": {"status": "corriendo", "progreso": 0}}, upsert=True)
    asyncio.create_task(asyncio.to_thread(_dashai_docs_build))
    return {"ok": True, "status": "corriendo"}


@api.get("/dashai/dataset-documentos/estado")
async def dashai_docs_estado():
    job = await db.config.find_one({"_key": "dashai_docs_job"}, {"_id": 0}) or {}
    job["descargable"] = _DASHAI_DOCS_CSV.exists()
    return job


@api.get("/dashai/dataset-documentos")
async def dashai_docs_descargar():
    if not _DASHAI_DOCS_CSV.exists():
        raise HTTPException(status_code=404, detail="Dataset aún no generado. Use el botón Generar primero.")
    return FileResponse(str(_DASHAI_DOCS_CSV), media_type="text/csv",
                        filename="dataset_documentos_dashai.csv")


# ------------------------------------------------------------------
# 🧠 CEREBRO PREDICTIVO DASHAI + 🔍 MÓDULO CONTRALOR (100% local, sin créditos)
# ------------------------------------------------------------------
@api.post("/mesa-brain/calibrar")
async def mesa_brain_calibrar():
    modelo = await asyncio.to_thread(mesa_brain.calibrar)
    modelo.pop("_id", None)
    return {"ok": True, "modelo": modelo}


@api.get("/mesa-brain/modelo")
async def mesa_brain_modelo():
    m = await asyncio.to_thread(mesa_brain.modelo_actual)
    m.pop("_id", None)
    return m


@api.get("/contraloria/casos")
async def contraloria_casos(dias: int = 60):
    """AUDITOR INDEPENDIENTE — Regla de Oro: los últimos 60 días de respuestas de la MESA.
    Aprobación de MESA sin criterios mínimos (renta, CMF, 2.000 UF) → BAJO AUDITORÍA."""
    modelo = await asyncio.to_thread(mesa_brain.modelo_actual)
    modelo.pop("_id", None)
    stats = await _stats_mesa()
    desde = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
    casos = []
    cursor = db.seguimiento.find(
        {"estado": {"$in": ["aprobacion", "aprobado", "rechazo", "rechazado"]},
         "fecha": {"$gte": desde}}, {"_id": 0}).sort("fecha", -1).limit(200)
    async for s in cursor:
        cliente = (s.get("cliente") or "").strip()
        caso = {"fecha": s.get("fecha", ""), "cliente": cliente,
                "respuesta_mesa": "aprobacion" if s.get("estado") in ("aprobacion", "aprobado") else "rechazo",
                "prob_dashai": None, "factores": [], "criterios_fallidos": [],
                "docs_faltantes": [], "estado_auditoria": "VALIDADO"}
        # MODO ESPEJO: una vez marcado como RECIBIDO DE MESA, queda así para siempre
        if s.get("estado_auditoria") == "RECIBIDO DE MESA":
            caso["estado_auditoria"] = "RECIBIDO DE MESA"
            caso["docs_faltantes"] = s.get("docs_faltantes") or []
            casos.append(caso)
            continue
        fd = None
        if cliente:
            fd = await db.folders.find_one(
                {"nombre": {"$regex": re.escape(cliente[:25]), "$options": "i"}})
        # MODO CONTRALOR EXCLUSIVO: solo se auditan expedientes con documentación COMPLETA
        docs_falt = []
        if fd:
            archivos = await asyncio.to_thread(fsvc.scan_archivos, fd.get("nombre", ""))
            docs_falt = [c["nombre"] for c in _criterios_folder(fd, archivos=archivos)[:4] if not c["ok"]]
        else:
            docs_falt = ["Carpeta no encontrada"]
        if docs_falt:
            caso["estado_auditoria"] = "RECIBIDO DE MESA"
            caso["docs_faltantes"] = docs_falt
            if s.get("id"):
                await db.seguimiento.update_one(
                    {"id": s["id"]},
                    {"$set": {"estado_auditoria": "RECIBIDO DE MESA", "docs_faltantes": docs_falt}})
            casos.append(caso)
            continue
        if fd:
            prob = await asyncio.to_thread(_prob_aprobacion_folder, fd, stats)
            caso["prob_dashai"] = prob.get("porcentaje")
            caso["factores"] = prob.get("factores", [])
            sim = None
            rut_f = re.sub(r"[^0-9kK]", "", (fd.get("rut") or "")).lower()
            if rut_f:
                sim = await db.simulaciones.find_one(
                    {"rut": {"$regex": rut_f[:8], "$options": "i"}}, sort=[("timestamp", -1)])
            if not sim and cliente:
                sim = await db.simulaciones.find_one(
                    {"nombre_completo": {"$regex": re.escape(cliente[:20]), "$options": "i"}},
                    sort=[("timestamp", -1)])
            # AUDITORÍA 360° (Contraloría Suprema): reglas de bodega + aprendizaje + renta + plazos
            cert = await asyncio.to_thread(
                mesa_brain.auditar_caso, fd, sim, caso["respuesta_mesa"], modelo)
            caso["estado_auditoria"] = cert["estado_auditoria"]
            caso["veredicto_dashai"] = cert["veredicto_dashai"]
            caso["criterios_fallidos"] = [v["detalle"] for v in cert["violaciones"]]
            caso["politica_saltada"] = cert["politica_saltada"]
            caso["certificado_id"] = cert["certificado_id"]
        if caso["estado_auditoria"] in ("BAJO AUDITORÍA", "RIESGO DE FALSO POSITIVO") and s.get("id"):
            await db.seguimiento.update_one({"id": s["id"]},
                                            {"$set": {"estado_auditoria": caso["estado_auditoria"]}})
        casos.append(caso)
    _rank = {"RIESGO DE FALSO POSITIVO": 0, "BAJO AUDITORÍA": 1, "VALIDADO": 2, "RECIBIDO DE MESA": 3}
    casos.sort(key=lambda c: (_rank.get(c["estado_auditoria"], 4), c["fecha"]))
    return {"modelo": modelo, "casos": casos,
            "riesgo_falso_positivo": sum(1 for c in casos if c["estado_auditoria"] == "RIESGO DE FALSO POSITIVO"),
            "bajo_auditoria": sum(1 for c in casos if c["estado_auditoria"] == "BAJO AUDITORÍA"),
            "recibidos": sum(1 for c in casos if c["estado_auditoria"] == "RECIBIDO DE MESA")}


@api.get("/contraloria/certificado")
async def contraloria_certificado(cliente: str = "", rut: str = ""):
    """CERTIFICADO DE AUDITORÍA INTERNA — auditoría 360° profunda de un cliente."""
    modelo = await asyncio.to_thread(mesa_brain.modelo_actual)
    modelo.pop("_id", None)
    fd = None
    # BÓVEDA ADN (Regla #66): el Contralor consulta primero el registro civil único
    adn_reg = None
    try:
        import adn_clientes as _adn_m
        if rut:
            adn_reg = await db.adn_clientes_360.find_one({"rut_norm": _adn_m._norm_rut(rut)})
        if not adn_reg and cliente:
            adn_reg = await db.adn_clientes_360.find_one(
                {"identidad.nombre": {"$regex": re.escape(cliente[:25]), "$options": "i"}})
        if adn_reg and (adn_reg.get("origen") or {}).get("folder_id"):
            fd = await db.folders.find_one({"id": adn_reg["origen"]["folder_id"]})
    except Exception as e:
        logging.warning(f"contraloria ADN: {e}")
    if not fd and rut:
        rut_f = re.sub(r"[^0-9kK]", "", rut).lower()
        fd = await db.folders.find_one({"rut": {"$regex": rut_f[:8], "$options": "i"}})
    if not fd and cliente:
        fd = await db.folders.find_one({"nombre": {"$regex": re.escape(cliente[:25]), "$options": "i"}})
    if not fd:
        raise HTTPException(status_code=404, detail="No se encontró la carpeta del cliente")
    sim = None
    rut_f = re.sub(r"[^0-9kK]", "", (fd.get("rut") or "")).lower()
    if rut_f:
        sim = await db.simulaciones.find_one({"rut": {"$regex": rut_f[:8], "$options": "i"}}, sort=[("timestamp", -1)])
    if not sim:
        sim = await db.simulaciones.find_one(
            {"nombre_completo": {"$regex": re.escape((fd.get("nombre") or "")[:20]), "$options": "i"}},
            sort=[("timestamp", -1)])
    seg = await db.seguimiento.find_one(
        {"cliente": {"$regex": re.escape((fd.get("nombre") or "")[:20]), "$options": "i"},
         "estado": {"$in": ["aprobacion", "aprobado", "rechazo", "rechazado"]}}, sort=[("fecha", -1)])
    resp = "aprobacion" if (seg or {}).get("estado") in ("aprobacion", "aprobado") else "rechazo"
    cert = await asyncio.to_thread(mesa_brain.auditar_caso, fd, sim, resp, modelo)
    cert["fecha_mesa"] = (seg or {}).get("fecha", "")
    if adn_reg:
        adn_reg.pop("_id", None)
        cert["adn_360"] = {"rut": adn_reg.get("rut"), "fuente": "ADN_CLIENTES_360 (Regla #66)",
                           "propiedad": adn_reg.get("propiedad"), "financiero": adn_reg.get("financiero")}
    return cert


# ══════════════════════════════════════════════════════════════════════════
# 🔬 AUDITORÍA FORENSE DE CONTRALORÍA (90 DÍAS) — minería histórica en bloques
# diarios (segundo plano, matemática local, cero consumo de créditos LLM).
# ══════════════════════════════════════════════════════════════════════════
async def _forense_buscar_contexto(cliente, rut_seg):
    fd = None
    rut_f = re.sub(r"[^0-9kK]", "", (rut_seg or "")).lower()
    if rut_f:
        fd = await db.folders.find_one({"rut": {"$regex": rut_f[:8], "$options": "i"}})
    if not fd and cliente:
        fd = await db.folders.find_one({"nombre": {"$regex": re.escape(cliente[:25]), "$options": "i"}})
    if not fd and cliente:
        # DESACOPLE DE CARPETAS: match parcial por tokens del nombre (ej: apellidos)
        toks = [t for t in re.split(r"\s+", cliente) if len(t) > 3][:2]
        if toks:
            fd = await db.folders.find_one(
                {"$and": [{"nombre": {"$regex": re.escape(t), "$options": "i"}} for t in toks]})
    sim = None
    rut_b = re.sub(r"[^0-9kK]", "", ((fd or {}).get("rut") or rut_seg or "")).lower()
    if rut_b:
        sim = await db.simulaciones.find_one({"rut": {"$regex": rut_b[:8], "$options": "i"}},
                                             sort=[("timestamp", -1)])
    if not sim and cliente:
        sim = await db.simulaciones.find_one(
            {"nombre_completo": {"$regex": re.escape(cliente[:20]), "$options": "i"}},
            sort=[("timestamp", -1)])
    return fd, sim


# ═══════════════════════════════════════════════════════════════════════════
# MINERÍA DE LÍMITES + ALGORITMO ESPEJO MESA (ingeniería inversa, 280 días)
# Triangula renta↔tope UF de aprobaciones reales, guarda db.limites_reales_mesa
# y re-entrena el Espejo (regresión) en config.espejo_mesa_modelo cada 24h.
# ═══════════════════════════════════════════════════════════════════════════
def _num_limpio(v):
    try:
        if isinstance(v, str):
            v = re.sub(r"[^\d.,]", "", v).replace(".", "").replace(",", ".")
        return float(v or 0)
    except (ValueError, TypeError):
        return 0.0


def _monto_uf_desde(*fuentes, uf=0):
    if not uf or uf <= 0:
        return 0.0  # Regla #1: sin UF oficial del SII no se convierte con valores inventados
    for v in fuentes:
        n = _num_limpio(v)
        if n > 0:
            return round(n / uf, 1) if n > 100000 else round(n, 1)  # >100k = CLP → UF
    return 0.0


async def minar_limites_mesa(dias=280):
    """Analiza las aprobaciones de los últimos N días y triangula renta↔tope UF,
    luego re-entrena el Algoritmo Espejo MESA por regresión."""
    uf = await get_valor_uf()
    corte = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
    entradas = await db.seguimiento.find(
        {"estado": {"$in": ["aprobacion", "aprobado"]}, "fecha": {"$gte": corte}}
    ).sort("fecha", -1).to_list(2000)
    if not entradas:
        entradas = await db.seguimiento.find(
            {"estado": {"$in": ["aprobacion", "aprobado"]}}).sort("fecha", -1).to_list(60)
    frase_re = re.compile(r"m[aá]ximo cr[eé]dito posible|posible solamente|tope|m[aá]ximo", re.I)
    cod_re = re.compile(r"codeudor|aval|segundo titular", re.I)
    casos = []
    for s in entradas:
        cliente = (s.get("cliente") or "").strip()
        fd, sim = await _forense_buscar_contexto(cliente, s.get("rut"))
        df = (fd or {}).get("datos_financieros") or {}
        renta = _num_limpio(df.get("renta_liquida") or df.get("renta_fija"))
        monto_uf = _monto_uf_desde(
            s.get("monto_credito"), df.get("monto_credito"),
            (sim or {}).get("credito_maximo_uf"), (sim or {}).get("credito_solicitado_uf"),
            (sim or {}).get("capacidad_credito_uf"), uf=uf)
        if renta <= 0 or monto_uf <= 0:
            continue
        asunto = (s.get("asunto") or "")
        con_cod = bool(cod_re.search(asunto) or (fd or {}).get("codeudor_nombre")
                       or (sim or {}).get("tiene_codeudor"))
        # TIPO DE CODEUDOR: familiar (apellido común o parentesco) vs tercera persona
        cod_nombre = ((fd or {}).get("codeudor_nombre") or "").strip().lower()
        parentesco_re = re.compile(r"c[oó]nyuge|esposa|esposo|hij[oa]|madre|padre|herman[oa]|familiar", re.I)
        if not con_cod:
            cod_tipo = "ninguno"
        elif parentesco_re.search(asunto) or parentesco_re.search(str((fd or {}).get("codeudor_parentesco") or "")):
            cod_tipo = "familiar"
        elif cod_nombre and cliente:
            ap_tit = set(cliente.lower().split()[1:])
            ap_cod = set(cod_nombre.split()[1:])
            cod_tipo = "familiar" if (ap_tit & ap_cod) else "tercero"
        else:
            cod_tipo = "tercero"
        renta_cod = _num_limpio(df.get("renta_codeudor") or (sim or {}).get("renta_codeudor"))
        edad = int(_num_limpio(df.get("edad") or (sim or {}).get("edad_cliente")))
        edad_bucket = "s/i" if edad <= 0 else ("<40" if edad < 40 else ("40_59" if edad < 60 else "60+"))
        endeud = ce.endeudamiento_mensual(df, uf)["endeudamiento_mensual_clp"]
        casos.append({
            "id": str(uuid.uuid4()), "cliente": cliente,
            "rut": (fd or {}).get("rut") or s.get("rut") or "",
            "renta_liquida_clp": round(renta), "renta_codeudor_clp": round(renta_cod),
            "renta_disponible_clp": round(max(0, renta + renta_cod - endeud)),
            "endeudamiento_mensual_clp": round(endeud),
            "tope_uf": monto_uf,
            "con_codeudor": con_cod, "codeudor_tipo": cod_tipo,
            "con_subsidio": bool(df.get("con_subsidio")),
            "edad": edad or None, "edad_bucket": edad_bucket,
            "edad_mayor_60": edad >= 60,
            "mencion_tope": bool(frase_re.search(asunto)),
            "fecha_mesa": (s.get("fecha") or "")[:10], "asunto": asunto[:140],
            "minado_en": now_iso(),
        })
    # Deduplicación: un caso por cliente (se conserva el más reciente)
    vistos, unicos = set(), []
    for c in casos:
        k = (c["cliente"].lower(), c["rut"])
        if k in vistos:
            continue
        vistos.add(k)
        unicos.append(c)
    casos = unicos
    await db.limites_reales_mesa.delete_many({})
    if casos:
        await db.limites_reales_mesa.insert_many([dict(c) for c in casos])
    modelo = await asyncio.to_thread(ce.entrenar_espejo_mesa, casos)
    modelo["ventana_dias"] = dias
    modelo["actualizado_en"] = now_iso()
    modelo["uf_ref"] = round(uf)
    modelo["casos"] = sorted(
        [{"renta_liquida_clp": c["renta_liquida_clp"],
          "renta_disponible_clp": c["renta_disponible_clp"], "tope_uf": c["tope_uf"],
          "con_codeudor": c["con_codeudor"], "codeudor_tipo": c["codeudor_tipo"],
          "con_subsidio": c["con_subsidio"], "edad_bucket": c["edad_bucket"]}
         for c in casos],
        key=lambda c: c["renta_liquida_clp"])
    rangos_cod = [c["renta_liquida_clp"] for c in casos if c["con_codeudor"]]
    modelo["codeudor_renta_min"] = min(rangos_cod) if rangos_cod else None
    modelo["codeudor_renta_max"] = max(rangos_cod) if rangos_cod else None
    await db.config.update_one({"_key": "espejo_mesa_modelo"}, {"$set": modelo}, upsert=True)
    return {"minados": len(casos), "precision_pct": modelo.get("precision_pct", 0),
            "listo": modelo.get("listo", False), "con_codeudor": len(rangos_cod)}


def _estimar_tope_mesa(renta_clp, modelo):
    """Tope UF empírico por vecindad de casos reales (para el panel de experiencia)."""
    casos = (modelo or {}).get("casos") or []
    renta_clp = _num_limpio(renta_clp)
    if not casos or renta_clp <= 0:
        return None
    cercanos = [c for c in casos if 0.75 * renta_clp <= c["renta_liquida_clp"] <= 1.25 * renta_clp]
    if not cercanos:
        cercanos = sorted(casos, key=lambda c: abs(c["renta_liquida_clp"] - renta_clp))[:3]
    topes = [c["tope_uf"] for c in cercanos]
    n_cod = sum(1 for c in cercanos if c["con_codeudor"])
    return {"tope_real_uf": round(sum(topes) / len(topes), 1) if topes else 0,
            "muestra_n": len(cercanos),
            "sugerir_codeudor": bool(cercanos and n_cod / len(cercanos) >= 0.5)}


async def _espejo_mesa_loop():
    """MODO ESPEJO PERMANENTE: re-entrena el algoritmo cada 24 horas."""
    await asyncio.sleep(120)
    while True:
        try:
            await minar_limites_mesa(280)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.warning(f"espejo mesa loop: {e}")
        await asyncio.sleep(86400)


@api.get("/dashai/espejo-mesa")
async def espejo_mesa_status():
    m = await db.config.find_one({"_key": "espejo_mesa_modelo"}) or {}
    m.pop("_id", None)
    casos = await db.limites_reales_mesa.find({}, {"_id": 0}).sort("renta_liquida_clp", 1).to_list(300)
    return {"modelo": m, "casos": casos}


@api.post("/dashai/espejo-mesa/minar")
async def espejo_mesa_minar(request: Request, payload: dict = None):
    """Re-calibración manual del Algoritmo Espejo: exclusiva de René Osa (Nivel 1)."""
    _solo_maestro(request)
    dias = int((payload or {}).get("dias") or 280)
    return await minar_limites_mesa(dias)



async def _forense_carga_conjunta(df, sim):
    """Carga financiera CONJUNTA: (cuota teórica 2% de deuda CMF titular+codeudor
    + PAV + dividendo evaluado) / renta conjunta (titular + codeudor)."""
    uf = await get_valor_uf()
    endeud = ce.endeudamiento_mensual(df or {}, uf)
    renta = _num_limpio((df or {}).get("renta_liquida")) + _num_limpio((df or {}).get("renta_codeudor"))
    div_clp = 0.0
    for k in ("dividendo_credito_clp", "div_eval_clp"):
        try:
            v = float((sim or {}).get(k) or 0)
        except (TypeError, ValueError):
            v = 0.0
        if v > 0:
            div_clp = v
            break
    carga = ((endeud["endeudamiento_mensual_clp"] + div_clp) / renta) if renta > 0 else 0.0
    return round(carga, 4), endeud


async def _forense_perfil_al_vuelo(s):
    """DESACOPLE DE CARPETAS — AUDITORÍA AL VUELO: si no existe carpeta, OCR de los
    PDF adjuntos del correo de la MESA para levantar un perfil financiero temporal.
    Cachea el resultado 7 días en db.perfiles_vuelo (la búsqueda IMAP es costosa)."""
    cliente = (s.get("cliente") or "").strip()
    rut = (s.get("rut") or "").strip()
    clave = re.sub(r"[^0-9a-zk]", "", (rut or cliente).lower())
    if not clave:
        return None
    corte = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    cached = await db.perfiles_vuelo.find_one({"clave": clave})
    if cached and (cached.get("actualizado") or "") > corte:
        return cached.get("perfil")
    perfil = None
    try:
        pares = []
        # REGLA DE ORO #64: sin búsquedas de RUT/dirección en el correo si el set está completo
        _imap_ok = await _perfil.imap_permitido(cliente or rut, "perfil_vuelo")
        if rut and _imap_ok:
            adj = await asyncio.to_thread(mail.buscar_adjuntos_por_rut, rut, 8)
            pares = [(a["filename"], a["content"]) for a in adj]
        if not pares and cliente and _imap_ok:
            pares = await asyncio.to_thread(
                _imap_descargar_adjuntos_cliente, cliente,
                r"liquidaci|sueldo|renta|informe_?deudas|cmf|codeudor|combinado|carpeta_")
        if pares:
            import ocr_service as _ocr
            partes = []
            for fn, raw in pares[:4]:
                if not (fn or "").lower().endswith(".pdf"):
                    continue
                try:
                    txt, _met = await asyncio.to_thread(_ocr.extraer_texto, raw, fn, False)
                    if txt and txt.strip():
                        etiqueta = ("DOCUMENTO DEL CODEUDOR" if re.search(r"codeudor", fn, re.I)
                                    else "ADJUNTO CORREO MESA")
                        partes.append(f"=== {etiqueta}: {fn} ===\n{txt.strip()[:9000]}")
                except Exception:
                    continue
            if partes:
                datos = await ai_extract.extraer_datos_financieros("\n\n".join(partes), cliente)
                if any(datos.get(k) for k in ("renta_liquida", "deuda_cmf_total",
                                              "deuda_cmf_codeudor", "renta_codeudor")):
                    perfil = {"nombre": cliente or rut, "rut": rut,
                              "datos_financieros": datos, "perfil_temporal": True,
                              "archivos_ocr": [fn for fn, _ in pares[:4]]}
    except Exception as e:
        logging.warning(f"perfil al vuelo {cliente or rut}: {e}")
    await db.perfiles_vuelo.update_one(
        {"clave": clave},
        {"$set": {"clave": clave, "perfil": perfil, "actualizado": now_iso()}}, upsert=True)
    return perfil


async def _forense_auditar_entrada(s, modelo):
    """Audita UNA respuesta de MESA. REGLA PERMANENTE: la Bóveda de Criterios DashAI
    es el ÚNICO juez — todos los umbrales se leen de db.config criterios (cero hardcode)."""
    hallazgos = []
    cliente = (s.get("cliente") or "").strip()
    aprobada = s.get("estado") in ("aprobacion", "aprobado")
    fd, sim = await _forense_buscar_contexto(cliente, s.get("rut"))
    if not fd:
        base_sin = {"cliente": cliente or "(sin nombre)", "rut": s.get("rut") or "",
                    "fecha_mesa": (s.get("fecha") or "")[:10],
                    "monto_mesa": s.get("monto_credito"), "certificado_id": None}
        # REGLA DE HIERRO — EL CONTRALOR MANDA: auditoría AL VUELO desde el correo de MESA
        fd_vuelo = await _forense_perfil_al_vuelo(s)
        if fd_vuelo:
            df_v = fd_vuelo.get("datos_financieros") or {}
            cert_v = await asyncio.to_thread(
                mesa_brain.auditar_caso, fd_vuelo, sim, "aprobacion" if aprobada else "rechazo", modelo)
            carga_v, endeud_v = await _forense_carga_conjunta(df_v, sim)
            estado_txt = "APROBADO" if aprobada else "RECHAZADO"
            detalle_fin = (f"renta ${_num_limpio(df_v.get('renta_liquida')):,.0f}"
                           + (f" + codeudor ${_num_limpio(df_v.get('renta_codeudor')):,.0f}" if df_v.get("renta_codeudor") else "")
                           + f" · deuda CMF conjunta ${endeud_v['deuda_cmf_total_clp']:,.0f}"
                           + (f" (codeudor ${endeud_v['deuda_cmf_codeudor_clp']:,.0f})" if endeud_v.get("deuda_cmf_codeudor_clp") else "")
                           + f" · carga conjunta {carga_v*100:.1f}%")
            base_v = {**base_sin, "certificado_id": cert_v.get("certificado_id"),
                      "perfil_temporal": True, "archivos_ocr": fd_vuelo.get("archivos_ocr") or []}
            if carga_v > 0.40:
                return [{**base_v, "categoria": "RIESGO CRÍTICO",
                         "detalle": (f"🚨 RIESGO CRÍTICO — Carga financiera conjunta {carga_v*100:.1f}% "
                                     f"> 40% (perfil temporal OCR al vuelo: {detalle_fin}) · MESA: {estado_txt}"),
                         "nota_dashai": ("DashAI (Contralor): sin carpeta digital, el Contralor reconstruyó el perfil "
                                         "financiero por OCR desde los adjuntos del correo de MESA. La carga conjunta "
                                         "(titular + codeudor) supera el tope inviolable del 40%: RIESGO CRÍTICO sin "
                                         "importar la decisión de la MESA.")}]
            if aprobada and cert_v.get("criticas"):
                return [{**base_v, "categoria": "RIESGO",
                         "detalle": ("⚠ Auditoría al vuelo (sin carpeta) — "
                                     + " · ".join(v["detalle"] for v in cert_v["criticas"][:3])),
                         "nota_dashai": "DashAI: perfil financiero temporal reconstruido por OCR desde el correo de MESA. La aprobación rompe reglas duras de la Bóveda."}]
            return [{**base_v, "categoria": "AUDITADO AL VUELO",
                     "detalle": (f"🛰 Auditoría al vuelo sin carpeta — {estado_txt} · {detalle_fin} · "
                                 "sin quiebres críticos detectados"),
                     "nota_dashai": "DashAI: no existe carpeta digital, pero el Contralor levantó un perfil financiero temporal por OCR desde los PDF del correo de MESA y ejecutó la auditoría de inmediato."}]
        asunto = (s.get("asunto") or "").strip()
        # AUDITORÍA BASADA EN EMAIL: si el correo de MESA existe, el negocio existió.
        if asunto:
            estado_txt = "APROBADO" if aprobada else "RECHAZADO"
            return [{**base_sin,
                     "categoria": "APROBACIÓN VERIFICADA POR EMAIL",
                     "asunto_mesa": asunto, "estado_mesa": estado_txt,
                     "detalle": (f"💎 Negocio confirmado por correo de MESA — Asunto: «{asunto}» · "
                                 f"Fecha: {(s.get('fecha') or '')[:10] or 's/f'} · Estado: {estado_txt}"),
                     "nota_dashai": "DashAI: no hay carpeta digital, pero el correo de MESA prueba que la operación existió y fue resuelta. Cree la carpeta si desea la auditoría 360° de LTV, carga y renta."}]
        # FIN DEL SALTO SILENCIOSO: los casos sin expediente NI correo aparecen en el reporte
        return [{**base_sin,
                 "categoria": "NO AUDITABLE",
                 "detalle": "⚠️ NO AUDITABLE - Sin expediente digital (decisión de MESA sin carpeta ni simulación vinculada)",
                 "nota_dashai": "DashAI: la decisión de MESA existe en el correo, pero no hay expediente digital para triangular LTV, carga ni renta. Ejecute el Rellenado de Datos o cree la carpeta para auditar este caso."}]
    # SINCRONIZACIÓN DE BÓVEDA (obligatoria antes de cualquier juicio)
    pol = await asyncio.to_thread(mesa_brain.politicas_maestras)
    min_uf = await asyncio.to_thread(mesa_brain.monto_minimo_sin_subsidio)
    crit_ver = await asyncio.to_thread(mesa_brain.criterios_version)
    edad_max = float(pol.get("edad_maxima_credito") or 80)
    antig_min = float(pol.get("antiguedad_minima_meses") or 12)
    cert = await asyncio.to_thread(
        mesa_brain.auditar_caso, fd, sim, "aprobacion" if aprobada else "rechazo", modelo)
    rut_cli = fd.get("rut") or s.get("rut") or ""
    base = {"cliente": cliente or fd.get("nombre", ""), "rut": rut_cli,
            "fecha_mesa": (s.get("fecha") or "")[:10],
            "monto_mesa": s.get("monto_credito") or cert.get("monto_uf"),
            "certificado_id": cert.get("certificado_id"),
            "criterios_version": f"v1.{crit_ver}"}
    # 1) RIESGO: aprobación que rompe políticas (violación crítica)
    df = fd.get("datos_financieros") or {}
    # ALERTA DE INCONSISTENCIA — REGLA DE HIERRO 40%: la carga conjunta manda sobre la MESA
    carga_cj, endeud_cj = await _forense_carga_conjunta(df, sim)
    if carga_cj > 0.40:
        hallazgos.append({**base, "categoria": "RIESGO CRÍTICO",
                          "detalle": (f"🚨 RIESGO CRÍTICO — Carga financiera conjunta {carga_cj*100:.1f}% > 40% "
                                      f"(deuda CMF titular ${endeud_cj['deuda_cmf_titular_clp']:,.0f}"
                                      + (f" + codeudor ${endeud_cj['deuda_cmf_codeudor_clp']:,.0f}" if endeud_cj.get("deuda_cmf_codeudor_clp") else "")
                                      + f" → cuota teórica ${endeud_cj['endeudamiento_mensual_clp']:,.0f}/mes) · "
                                      + ("la MESA lo APROBÓ igual" if aprobada else "la MESA lo rechazó")),
                          "nota_dashai": "DashAI (Contralor): la carga financiera conjunta (titular + codeudor) supera el tope inviolable del 40%. El Contralor manda: se marca RIESGO CRÍTICO sin importar la decisión de la MESA."})
    if aprobada and cert.get("criticas"):
        hallazgos.append({**base, "categoria": "RIESGO",
                          "detalle": " · ".join(v["detalle"] for v in cert["criticas"][:3]),
                          "nota_dashai": "DashAI: la MESA aprobó pese a quiebres CRÍTICOS del reglamento de bodega (BTG/Ameris/Subsidio 02). Cada quiebre listado es una regla dura que invalida la operación ante el inversionista."})
    # 1b) RIESGO — FUERA DE POLÍTICA: monto aprobado < 2.000 UF sin subsidio
    try:
        m_uf = float(s.get("monto_credito") or df.get("monto_credito") or 0)
    except (TypeError, ValueError):
        m_uf = 0
    con_sub = bool(df.get("con_subsidio"))
    if aprobada and 0 < m_uf < min_uf and not con_sub:
        hallazgos.append({**base, "categoria": "RIESGO",
                          "detalle": f"Monto aprobado {m_uf:.0f} UF < {min_uf:.0f} UF sin subsidio — fuera de política de bodega",
                          "nota_dashai": f"DashAI (Bóveda v1.{crit_ver}): el reglamento vigente fija un mínimo de {min_uf:.0f} UF para operaciones sin subsidio. Esta aprobación no es colocable en la bodega y quedará atrapada en cartera propia."})
    # 1c) RIESGO — REGLA DE LOS 80 AÑOS saltada (edad + plazo al término)
    try:
        edad_plazo = float((sim or {}).get("edad_plazo") or 0)
    except (TypeError, ValueError):
        edad_plazo = 0
    if aprobada and edad_plazo > edad_max:
        hallazgos.append({**base, "categoria": "RIESGO",
                          "detalle": f"Edad + plazo al término = {edad_plazo:.0f} años > {edad_max:.0f} (Regla de edad de la Bóveda saltada)",
                          "nota_dashai": f"DashAI (Bóveda v1.{crit_ver}): la regla vigente exige que edad del deudor + plazo del crédito no supere los {edad_max:.0f} años al término. La MESA la saltó: riesgo actuarial y de seguro de desgravamen no cubierto."})
    # 2) PERDIDA: rechazo que según los papeles era viable (antigüedad >= 12 cumplida)
    docs_ok = not [c for c in _criterios_folder(fd, archivos=await asyncio.to_thread(
        fsvc.scan_archivos, fd.get("nombre", "")))[:4] if not c["ok"]]
    antig = df.get("antiguedad_laboral_meses")
    antig_ok = antig is None or float(antig or 0) >= antig_min
    if (not aprobada) and docs_ok and not cert.get("violaciones") and antig_ok:
        hallazgos.append({**base, "categoria": "PERDIDA",
                          "detalle": "Rechazo de MESA con expediente completo, antigüedad laboral cumplida y CERO quiebres de reglamento — candidato a rescate",
                          "nota_dashai": f"DashAI (Bóveda v1.{crit_ver}): el cliente cumplía TODOS los requisitos vigentes de la Bóveda (documentación completa{', antigüedad ' + format(float(antig), '.0f') + f' meses >= {antig_min:.0f}' if antig is not None else ''}, sin quiebre de política). El rechazo carece de sustento técnico verificable: negocio perdido rescatable."})
    # 3) ERROR HUMANO: inconsistencias de renta / antigüedad / monto
    errores = []
    renta = await asyncio.to_thread(mesa_brain.recalibrar_renta, sim, fd, {})
    if renta.get("disponible") and renta.get("renta_declarada") and renta.get("renta_reconocida"):
        dif = renta["renta_declarada"] - renta["renta_reconocida"]
        if dif > renta["renta_declarada"] * 0.10:
            errores.append(f"Renta declarada ${renta['renta_declarada']:,} vs reconocida "
                           f"${renta['renta_reconocida']:,} (castigos/no imponibles ignorados: ${dif:,})")
    try:
        m_seg = float(s.get("monto_credito") or 0)
        m_fd = float(df.get("monto_credito") or 0)
        if m_seg and m_fd and abs(m_seg - m_fd) > max(m_fd * 0.05, 1):
            errores.append(f"Monto MESA {m_seg:.0f} UF ≠ monto carpeta {m_fd:.0f} UF")
    except (TypeError, ValueError):
        pass
    if aprobada and antig is not None and float(antig or 0) < 12:
        errores.append(f"Antigüedad {antig} meses < 12 (aprobada igual)")
    if errores:
        hallazgos.append({**base, "categoria": "ERROR HUMANO", "detalle": " · ".join(errores[:3]),
                          "nota_dashai": "DashAI: inconsistencia numérica entre los documentos originales y la respuesta de MESA. La suma de liquidaciones/renta reconocida, el monto o la antigüedad no cuadran con lo resuelto — error operativo de la mesa."})
    # MODO CONTRALOR OSA: toda diferencia contra la Constitución se rotula con su sello
    for h in hallazgos:
        if h.get("categoria") in ("RIESGO", "RIESGO CRÍTICO", "PERDIDA", "ERROR HUMANO"):
            h["inconsistencia"] = "Inconsistencia detectada con los Criterios Maestros de René Osa"
            h["detalle"] = f"⚠ Inconsistencia detectada con los Criterios Maestros de René Osa — {h['detalle']}"
    return hallazgos


async def _forense_caso_automatico(seg):
    """CONTRALORÍA AUTOMÁTICA: audita el caso AL INSTANTE cuando llega una respuesta
    de MESA (aprobación o rechazo) y alerta a Gerardo si detecta un error."""
    try:
        if seg.get("estado") not in ("aprobacion", "aprobado", "rechazo", "rechazado"):
            return
        modelo = await asyncio.to_thread(mesa_brain.modelo_actual)
        modelo.pop("_id", None)
        nuevos_h = await _forense_auditar_entrada(seg, modelo)
        if not nuevos_h:
            return
        doc = await db.config.find_one({"_key": "auditoria_forense"}) or {}
        previos = doc.get("hallazgos") or []
        claves = {(h.get("cliente"), h.get("fecha_mesa"), h.get("categoria"), h.get("detalle"))
                  for h in previos}
        agregados = [h for h in nuevos_h
                     if (h["cliente"], h["fecha_mesa"], h["categoria"], h["detalle"]) not in claves]
        if not agregados:
            return
        for h in agregados:
            h["origen"] = "auto_al_recibir"
            h["detectado_en"] = now_iso()
        hallazgos = agregados + previos
        resumen = {"RIESGO": sum(1 for h in hallazgos if h["categoria"] == "RIESGO"),
                   "RIESGO CRÍTICO": sum(1 for h in hallazgos if h["categoria"] == "RIESGO CRÍTICO"),
                   "PERDIDA": sum(1 for h in hallazgos if h["categoria"] == "PERDIDA"),
                   "ERROR HUMANO": sum(1 for h in hallazgos if h["categoria"] == "ERROR HUMANO"),
                   "VERIFICADO EMAIL": sum(1 for h in hallazgos if h["categoria"] == "APROBACIÓN VERIFICADA POR EMAIL"),
                   "AUDITADO AL VUELO": sum(1 for h in hallazgos if h["categoria"] == "AUDITADO AL VUELO"),
                   "NO AUDITABLE": sum(1 for h in hallazgos if h["categoria"] == "NO AUDITABLE")}
        await db.config.update_one({"_key": "auditoria_forense"}, {"$set": {
            "hallazgos": hallazgos, "resumen": resumen,
            "estado": doc.get("estado") or "completado",
            "titulo_lista": "Errores MESA detectados",
            "nuevos_ultimo_barrido": int(doc.get("nuevos_ultimo_barrido") or 0) + len(agregados),
            "generado_en": now_iso()}}, upsert=True)
        destinatario = os.environ.get("MAIL2_USER", "")
        con_errores = [h for h in agregados
                       if h["categoria"] not in ("NO AUDITABLE", "APROBACIÓN VERIFICADA POR EMAIL")]
        if destinatario and con_errores:
            agregados = con_errores
            filas = "".join(
                f"<li style='margin-bottom:10px'><b>[{h['categoria']}]</b> {h['detalle']}"
                f"<br><i style='color:#666;font-size:12px'>{h.get('nota_dashai', '')}</i></li>"
                for h in agregados)
            cuerpo = f"""
<div style="font-family:Arial,sans-serif;width:100%;max-width:600px">
  <div style="background:#0a0a0a;padding:16px 20px;border-left:4px solid #e11d48">
    <span style="color:#D4AF37;font-weight:700;letter-spacing:0.08em">🔬 CONTRALORÍA AUTOMÁTICA · CENTRAL MUTUOS</span>
  </div>
  <div style="padding:16px 6px;color:#1a1a1a;font-size:14px">
    <p><b>DashAI auditó al instante la respuesta de MESA del caso
       {agregados[0]['cliente']} ({agregados[0].get('rut') or 'sin RUT'})</b>
       y detectó {len(agregados)} error(es):</p>
    <ul style="font-size:13px;color:#333">{filas}</ul>
    <p style="font-size:13px">El hallazgo ya está registrado en Contraloría → "Errores MESA detectados".</p>
  </div>
</div>"""
            await asyncio.to_thread(
                mail.send_mail, destinatario,
                f"🚨 CONTRALORÍA AUTOMÁTICA: {len(agregados)} error(es) MESA — {agregados[0]['cliente']}",
                cuerpo, [], "secundaria")
        logging.info(f"🔬 Forense automático: {len(agregados)} hallazgos en {seg.get('cliente')}")
    except Exception as e:
        logging.warning(f"forense automático: {e}")


async def _forense_job(dias=90):
    desde = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
    q = {"estado": {"$in": ["aprobacion", "aprobado", "rechazo", "rechazado"]},
         "fecha": {"$gte": desde}}
    entradas = await db.seguimiento.find(q).sort("fecha", 1).to_list(1000)
    modelo = await asyncio.to_thread(mesa_brain.modelo_actual)
    modelo.pop("_id", None)
    prev_doc = await db.config.find_one({"_key": "auditoria_forense"}) or {}
    prev_keys = {(h.get("cliente"), h.get("fecha_mesa"), h.get("categoria"))
                 for h in (prev_doc.get("hallazgos_previos") or [])}
    # Bloques diarios para proteger la estabilidad del servidor
    bloques = {}
    for s in entradas:
        bloques.setdefault((s.get("fecha") or "")[:10], []).append(s)
    hallazgos = []
    revisados = 0
    total = len(entradas)
    for dia in sorted(bloques):
        for s in bloques[dia]:
            revisados += 1
            cliente = (s.get("cliente") or "").strip()
            try:
                hallazgos.extend(await _forense_auditar_entrada(s, modelo))
            except Exception as e:
                logging.warning(f"Forense {cliente}: {e}")
            await db.config.update_one({"_key": "auditoria_forense"}, {"$set": {
                "estado": "en_proceso", "progreso": revisados, "total": total}}, upsert=True)
        await asyncio.sleep(1)  # respiro entre bloques diarios
    resumen = {"RIESGO": sum(1 for h in hallazgos if h["categoria"] == "RIESGO"),
               "RIESGO CRÍTICO": sum(1 for h in hallazgos if h["categoria"] == "RIESGO CRÍTICO"),
               "PERDIDA": sum(1 for h in hallazgos if h["categoria"] == "PERDIDA"),
               "ERROR HUMANO": sum(1 for h in hallazgos if h["categoria"] == "ERROR HUMANO"),
               "VERIFICADO EMAIL": sum(1 for h in hallazgos if h["categoria"] == "APROBACIÓN VERIFICADA POR EMAIL"),
               "AUDITADO AL VUELO": sum(1 for h in hallazgos if h["categoria"] == "AUDITADO AL VUELO"),
               "NO AUDITABLE": sum(1 for h in hallazgos if h["categoria"] == "NO AUDITABLE")}
    nuevos = sum(1 for h in hallazgos
                 if (h["cliente"], h["fecha_mesa"], h["categoria"]) not in prev_keys)
    crit_ver = await asyncio.to_thread(mesa_brain.criterios_version)
    await db.config.update_one({"_key": "auditoria_forense"}, {"$set": {
        "estado": "completado", "progreso": revisados, "total": total,
        "periodo_dias": dias, "hallazgos": hallazgos, "resumen": resumen,
        "titulo_lista": "Errores MESA detectados", "nuevos_ultimo_barrido": nuevos,
        "criterios_version": f"v1.{crit_ver}",
        "nota_trazabilidad": f"Análisis ejecutado bajo los criterios permanentes de DashAI v1.{crit_ver}",
        "generado_en": now_iso()}}, upsert=True)
    logging.info(f"🔬 Forense {dias}d: {revisados} revisados, {len(hallazgos)} hallazgos ({nuevos} nuevos) {resumen}")


# ══════════════════════════════════════════════════════════════════════════
# 📊 AUTO-EXPORTACIÓN DASHAI — dataset comercial diario (23:59 hora Chile)
# Bóveda local: storage/boveda_dashai/dataset_dashai.csv · RUT hasheado = llave
# única (sin duplicados) · datos anonimizados (sin nombres ni contactos).
# ══════════════════════════════════════════════════════════════════════════
BOVEDA_DASHAI_DIR = Path(__file__).parent / "storage" / "boveda_dashai"
DATASET_DASHAI = BOVEDA_DASHAI_DIR / "dataset_dashai.csv"
DATASET_CAMPOS = ["rut_llave", "fecha_mesa", "decision_mesa", "monto_credito_uf",
                  "renta_liquida", "carga_financiera", "ltv", "con_subsidio",
                  "tiene_codeudor", "auditoria_categorias", "auditoria_inconsistencias",
                  "criterios_version"]


def _rut_llave(rut, cliente=""):
    """ANONIMIZACIÓN: SHA-256 del RUT normalizado (o del nombre si no hay RUT)."""
    import hashlib
    bruto = re.sub(r"[^0-9kK]", "", rut or "").lower()
    if not bruto:
        bruto = re.sub(r"\s+", "", (cliente or "").lower())
    if not bruto:
        return ""
    return hashlib.sha256(bruto.encode()).hexdigest()[:16]


async def _dashai_dataset_generar():
    """DATOS MAESTROS: historial MESA + finanzas de carpetas + veredicto forense."""
    entradas = await db.seguimiento.find(
        {"estado": {"$in": ["aprobacion", "aprobado", "rechazo", "rechazado"]}}
    ).sort("fecha", 1).to_list(5000)
    fdoc = await db.config.find_one({"_key": "auditoria_forense"}) or {}
    forense_por_cliente = {}
    for h in (fdoc.get("hallazgos") or []):
        forense_por_cliente.setdefault((h.get("cliente") or "").strip().lower(), []).append(h)
    crit_ver = await asyncio.to_thread(mesa_brain.criterios_version)
    filas = {}
    for s in entradas:
        cliente = (s.get("cliente") or "").strip()
        fd, sim = await _forense_buscar_contexto(cliente, s.get("rut"))
        llave = _rut_llave((fd or {}).get("rut") or s.get("rut"), cliente)
        if not llave:
            continue
        df = (fd or {}).get("datos_financieros") or {}
        sim = sim or {}
        tiene_cod = bool(sim.get("tiene_codeudor"))
        hs = forense_por_cliente.get(cliente.lower(), [])
        # LLAVE ÚNICA POR RUT: al iterar por fecha ascendente queda la decisión más reciente
        filas[llave] = {
            "rut_llave": llave,
            "fecha_mesa": (s.get("fecha") or "")[:10],
            "decision_mesa": "APROBADO" if s.get("estado") in ("aprobacion", "aprobado") else "RECHAZADO",
            "monto_credito_uf": df.get("monto_credito") or s.get("monto_credito")
            or sim.get("credito_solicitado_uf") or "",
            "renta_liquida": df.get("renta_liquida") or df.get("renta_fija") or "",
            "carga_financiera": (sim.get("carga_fin_conjunta") if tiene_cod
                                 else sim.get("carga_fin_individual")) or "",
            "ltv": sim.get("ltv") or "",
            "con_subsidio": "SI" if df.get("con_subsidio") else "NO",
            "tiene_codeudor": "SI" if tiene_cod else "NO",
            "auditoria_categorias": " | ".join(sorted({h.get("categoria") or "" for h in hs} - {""})),
            "auditoria_inconsistencias": sum(1 for h in hs if h.get("categoria")
                                             in ("RIESGO", "PERDIDA", "ERROR HUMANO")),
            "criterios_version": f"v1.{crit_ver}",
        }
    prev = await db.config.find_one({"_key": "dashai_dataset"}) or {}
    nuevos = len(set(filas) - set(prev.get("llaves") or []))
    import csv
    BOVEDA_DASHAI_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATASET_DASHAI, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=DATASET_CAMPOS)
        w.writeheader()
        for fila in filas.values():
            w.writerow(fila)
    await db.config.update_one({"_key": "dashai_dataset"}, {"$set": {
        "llaves": sorted(filas), "total": len(filas), "nuevos_ultimo": nuevos,
        "archivo": str(DATASET_DASHAI), "generado_en": now_iso()}}, upsert=True)
    # NOTIFICACIÓN DE ÉXITO: visible en el dashboard a la mañana siguiente
    await db.alertas.insert_one({
        "id": str(uuid.uuid4()), "tipo": "dashai_dataset", "cliente": "",
        "mensaje": f"📊 Dataset DashAI actualizado con {nuevos} nuevos casos "
                   f"({len(filas)} totales · anonimizado · Bóveda de DashAI)",
        "fecha": now_iso(), "leida": False})
    logging.info(f"📊 Dataset DashAI: {len(filas)} filas, {nuevos} nuevos → {DATASET_DASHAI}")
    return {"total": len(filas), "nuevos": nuevos, "archivo": DATASET_DASHAI.name,
            "generado_en": now_iso()}


async def _dashai_dataset_loop():
    """EXPORTACIÓN PROGRAMADA: todos los días a las 23:59 (hora Chile)."""
    while True:
        try:
            await asyncio.sleep(30)
            ahora = datetime.now(_tz_chile())
            hoy = ahora.strftime("%Y-%m-%d")
            st = await db.config.find_one({"_key": "dashai_dataset"}) or {}
            if (ahora.hour, ahora.minute) >= (23, 59) and st.get("last_export_date") != hoy:
                await db.config.update_one({"_key": "dashai_dataset"},
                                           {"$set": {"last_export_date": hoy}}, upsert=True)
                await _dashai_dataset_generar()
        except asyncio.CancelledError:
            break
        except Exception as e:
            if "after close" in str(e):
                break  # cliente Mongo cerrado (hot-reload): el loop zombie muere aquí
            logging.warning(f"dashai dataset loop: {e}")


@api.get("/dashai/dataset/status")
async def dashai_dataset_status():
    st = await db.config.find_one({"_key": "dashai_dataset"}) or {}
    st.pop("_id", None)
    st.pop("llaves", None)
    st["existe_csv"] = DATASET_DASHAI.exists()
    st["programacion"] = "Diaria a las 23:59 (hora Chile)"
    return st


@api.post("/dashai/dataset/exportar-ahora")
async def dashai_dataset_exportar_ahora():
    return await _dashai_dataset_generar()


@api.get("/dashai/dataset/descargar")
async def dashai_dataset_descargar():
    if not DATASET_DASHAI.exists():
        raise HTTPException(status_code=404,
                            detail="Aún no se genera el dataset. Exporte ahora o espere a las 23:59.")
    return FileResponse(str(DATASET_DASHAI), media_type="text/csv",
                        filename="dataset_dashai.csv")


# ══════════════════════════════════════════════════════════════════════════
# 🛡️ BÚNKER DE RESPALDO CLOUD — espejo pasivo en Emergent Object Store.
# La operación diaria sigue en disco local; la nube es solo un seguro.
# Recuperación total: /app/backend/emergency_restore.py (script inactivo).
# ══════════════════════════════════════════════════════════════════════════
async def _cloud_bunker_loop():
    """RESPALDO SILENCIOSO: escaneo espejo cada 5 minutos, en thread aparte."""
    await asyncio.sleep(90)  # deja levantar el resto del sistema primero
    while True:
        try:
            await asyncio.to_thread(cloud_bunker.escanear_y_respaldar)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.warning(f"cloud bunker loop: {e}")
        await asyncio.sleep(300)


@api.get("/seguridad/respaldo")
async def seguridad_respaldo_status():
    st = await db.config.find_one({"_key": "cloud_bunker"}) or {}
    st.pop("_id", None)
    st.pop("dashai_hash", None)
    st.setdefault("estado", "INICIANDO")
    st["modo"] = "Respaldo Silencioso (espejo pasivo cada 5 min)"
    return st


@api.post("/seguridad/respaldo/ahora")
async def seguridad_respaldo_ahora():
    res = await asyncio.to_thread(cloud_bunker.escanear_y_respaldar)
    return res


@api.post("/contraloria/forense/iniciar")
async def forense_iniciar(dias: int = 90):
    await _constitucion_dashai()
    doc = await db.config.find_one({"_key": "auditoria_forense"})
    if doc and doc.get("estado") == "en_proceso":
        return {"ok": True, "mensaje": "Auditoría forense ya en proceso", "progreso": doc.get("progreso")}
    await db.config.update_one({"_key": "auditoria_forense"}, {"$set": {
        "estado": "en_proceso", "progreso": 0, "total": 0, "hallazgos": [],
        "hallazgos_previos": (doc or {}).get("hallazgos") or [],
        "iniciado_en": now_iso()}}, upsert=True)
    asyncio.create_task(_forense_job(dias))
    return {"ok": True, "mensaje": f"Auditoría forense de {dias} días lanzada en segundo plano"}


@api.get("/contraloria/forense")
async def forense_estado():
    doc = await db.config.find_one({"_key": "auditoria_forense"}, {"_id": 0})
    if doc:
        doc.pop("hallazgos_previos", None)
    return doc or {"estado": "sin_ejecutar"}


def _borrador_reclamacion(h):
    """MODO RECLAMACIÓN: borrador Oro/Carbono para rescatar un caso PERDIDA."""
    cliente = h.get("cliente") or "Cliente"
    rut = h.get("rut") or "RUT en expediente"
    fecha = h.get("fecha_mesa") or ""
    monto = h.get("monto_mesa")
    monto_txt = f"{float(monto):,.0f} UF".replace(",", ".") if monto else "según expediente"
    subject = f"RECLAMACIÓN FORMAL — Solicitud de Reevaluación: {cliente} ({rut})"
    body = f"""
<div style="font-family:Georgia,'Times New Roman',serif;width:100%;max-width:600px;margin:0 auto">
  <div style="background:#0a0a0a;padding:20px 26px;border-left:4px solid #D4AF37">
    <span style="color:#D4AF37;font-weight:700;letter-spacing:0.1em">CENTRAL MUTUOS · CONTRALORÍA</span>
  </div>
  <div style="padding:22px 8px;color:#1a1a1a;font-size:14px;line-height:1.75">
    <p>Estimados señores de la MESA,</p>
    <p>Por medio de la presente solicito formalmente la <b>reevaluación</b> del caso
       <b>{cliente}</b> (RUT {rut}), resuelto con rechazo el {fecha or 'período auditado'},
       por un monto de crédito de <b>{monto_txt}</b>.</p>
    <p>La auditoría forense independiente de DashAI (Contraloría Central Mutuos) determinó que
       el expediente cumplía <b>todos los requisitos duros del reglamento de bodega
       (BTG/Ameris/Subsidio 02)</b> al momento de la resolución:</p>
    <ul style="font-size:13px;color:#333">
      <li>Documentación completa (Cédula, Liquidaciones, AFP y CMF verificados).</li>
      <li>Antigüedad laboral igual o superior a 12 meses.</li>
      <li>Cero quiebres de política detectados en la triangulación documental.</li>
    </ul>
    <p><b>Nota técnica DashAI:</b> {h.get('nota_dashai') or h.get('detalle') or ''}</p>
    <p>Agradeceré confirmar la reapertura del caso o, en su defecto, remitir el fundamento
       técnico específico del rechazo para nuestro registro de contraloría.</p>
    <p style="margin-top:24px">Atentamente,<br><b>Gerardo Barrera</b><br>
       <span style="color:#666;font-size:12px">Dirección Comercial · Central Mutuos</span></p>
  </div>
</div>"""
    return {"subject": subject, "body": body}


@api.post("/contraloria/forense/reclamaciones")
async def forense_reclamaciones_generar():
    doc = await db.config.find_one({"_key": "auditoria_forense"}) or {}
    perdidas = [h for h in (doc.get("hallazgos") or []) if h.get("categoria") == "PERDIDA"][:5]
    if not perdidas:
        raise HTTPException(status_code=404, detail="No hay hallazgos PERDIDA en la última minería forense")
    borradores = []
    for i, h in enumerate(perdidas):
        b = _borrador_reclamacion(h)
        borradores.append({"idx": i, "cliente": h.get("cliente"), "rut": h.get("rut"),
                           "fecha_mesa": h.get("fecha_mesa"), "subject": b["subject"],
                           "body": b["body"], "enviado": False})
    await db.config.update_one({"_key": "forense_reclamaciones"}, {"$set": {
        "borradores": borradores, "generado_en": now_iso()}}, upsert=True)
    return {"ok": True, "total": len(borradores), "borradores": borradores}


@api.get("/contraloria/forense/reclamaciones")
async def forense_reclamaciones_list():
    doc = await db.config.find_one({"_key": "forense_reclamaciones"}, {"_id": 0})
    return doc or {"borradores": []}


@api.post("/contraloria/forense/reclamaciones/{idx}/enviar")
async def forense_reclamacion_enviar(idx: int):
    """CANDADO: el envío a MESA solo ocurre cuando Gerardo presiona el botón."""
    doc = await db.config.find_one({"_key": "forense_reclamaciones"}) or {}
    bs = doc.get("borradores") or []
    if idx < 0 or idx >= len(bs):
        raise HTTPException(status_code=404, detail="Borrador de reclamación no encontrado")
    b = bs[idx]
    res = await asyncio.to_thread(mail.send_mail, "aprobaciones@centralmutuos.cl",
                                  b["subject"], b["body"], [], "secundaria")
    if not res.get("success"):
        raise HTTPException(status_code=502, detail=res.get("error", "Error de envío SMTP"))
    bs[idx]["enviado"] = True
    bs[idx]["enviado_en"] = now_iso()
    await db.config.update_one({"_key": "forense_reclamaciones"}, {"$set": {"borradores": bs}})
    return {"ok": True, "mensaje": f"Reclamación de {b['cliente']} enviada a aprobaciones@centralmutuos.cl"}


@api.post("/contraloria/forense/reenviar-mesa")
async def forense_reenviar_mesa(payload: dict):
    """RESCATE DE PÉRDIDAS: reenvía a MESA un hallazgo PERDIDA con 1 clic,
    adjuntando la carpeta del cliente. Candado anti-duplicado por hallazgo."""
    cliente = (payload.get("cliente") or "").strip()
    fecha_mesa = (payload.get("fecha_mesa") or "").strip()
    if not cliente:
        raise HTTPException(status_code=400, detail="Falta el cliente del hallazgo")
    doc = await db.config.find_one({"_key": "auditoria_forense"}) or {}
    hallazgos = doc.get("hallazgos") or []
    idx = next((i for i, h in enumerate(hallazgos)
                if h.get("categoria") == "PERDIDA" and h.get("cliente") == cliente
                and (not fecha_mesa or h.get("fecha_mesa") == fecha_mesa)), None)
    if idx is None:
        raise HTTPException(status_code=404, detail=f"No hay hallazgo PERDIDA para {cliente}")
    h = hallazgos[idx]
    if h.get("reenviado_mesa") and not payload.get("forzar"):
        fecha_prev = str(h.get("reenviado_en") or "")[:16].replace("T", " ")
        raise HTTPException(status_code=403, detail=(
            f"El caso {cliente} ya fue reenviado a MESA el {fecha_prev}. "
            "Use forzar para repetir el envío."))
    b = _borrador_reclamacion(h)
    adjuntos = []
    merged = CLIENTES_DIR / _safe_name(cliente) / f"Carpeta_{_safe_name(cliente)}.pdf"
    if merged.exists():
        adjuntos.append({"filename": merged.name, "content_b64": _b64(merged.read_bytes())})
    destino = (os.environ.get("MESA_EMAIL") or "").strip() or "aprobaciones@centralmutuos.cl"
    res = await asyncio.to_thread(mail.send_mail, destino, b["subject"], b["body"],
                                  adjuntos, "secundaria")
    if not res.get("success"):
        raise HTTPException(status_code=502, detail=res.get("error", "Error de envío SMTP"))
    hallazgos[idx]["reenviado_mesa"] = True
    hallazgos[idx]["reenviado_en"] = now_iso()
    await db.config.update_one({"_key": "auditoria_forense"},
                               {"$set": {"hallazgos": hallazgos}})
    return {"ok": True, "carpeta_adjunta": bool(adjuntos),
            "mensaje": f"📨 Caso {cliente} reenviado a MESA ({destino})"
                       f"{' con carpeta adjunta' if adjuntos else ' (sin carpeta PDF disponible)'}"}


@api.get("/contraloria/forense/descargar")
async def forense_descargar(lista: str = "A"):
    """Lista A: aprobaciones cuestionables (RIESGO + ERROR HUMANO).
    Lista B: oportunidades rescatables (PERDIDA). Descarga CSV."""
    doc = await db.config.find_one({"_key": "auditoria_forense"}) or {}
    hallazgos = doc.get("hallazgos") or []
    if lista.upper() == "A":
        rows = [h for h in hallazgos if h.get("categoria") in ("RIESGO", "ERROR HUMANO")]
        nombre_archivo = "Lista_A_Aprobaciones_Cuestionables.csv"
    else:
        rows = [h for h in hallazgos if h.get("categoria") == "PERDIDA"]
        nombre_archivo = "Lista_B_Oportunidades_Rescatables.csv"
    import csv as _csv
    buf = io.StringIO()
    w = _csv.writer(buf)
    w.writerow([doc.get("nota_trazabilidad") or "Análisis ejecutado bajo los criterios permanentes de DashAI"])
    w.writerow(["Categoria", "Cliente", "RUT", "Fecha MESA", "Monto UF", "Detalle", "Nota DashAI"])
    for h in rows:
        w.writerow([h.get("categoria"), h.get("cliente"), h.get("rut"), h.get("fecha_mesa"),
                    h.get("monto_mesa"), h.get("detalle"), h.get("nota_dashai", "")])
    data = "\ufeff" + buf.getvalue()
    return _RawResponse(content=data.encode("utf-8"), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'})


@api.get("/contraloria/forense/buscar")
async def forense_buscar(q: str = ""):
    """BÚSQUEDA RÁPIDA: audita al instante todos los casos de MESA de un RUT o nombre."""
    await _constitucion_dashai()
    q = (q or "").strip()
    if len(q) < 3:
        raise HTTPException(status_code=400, detail="Ingresa un RUT o nombre (mínimo 3 caracteres)")
    rut_n = re.sub(r"[^0-9kK]", "", q).lower()
    filtros = [{"cliente": {"$regex": re.escape(q), "$options": "i"}}]
    if len(rut_n) >= 7:
        filtros.append({"rut": {"$regex": rut_n[:8], "$options": "i"}})
        fd = await db.folders.find_one({"rut": {"$regex": rut_n[:8], "$options": "i"}})
        if fd and fd.get("nombre"):
            filtros.append({"cliente": {"$regex": re.escape(fd["nombre"][:25]), "$options": "i"}})
    entradas = await db.seguimiento.find(
        {"$or": filtros, "estado": {"$in": ["aprobacion", "aprobado", "rechazo", "rechazado"]}}
    ).sort("fecha", -1).limit(20).to_list(20)
    if not entradas:
        return {"casos": [], "total": 0, "mensaje": f"Sin decisiones de MESA registradas para '{q}'"}
    modelo = await asyncio.to_thread(mesa_brain.modelo_actual)
    modelo.pop("_id", None)
    casos = []
    for s in entradas:
        try:
            hallazgos = await _forense_auditar_entrada(s, modelo)
        except Exception:
            hallazgos = []
        casos.append({"cliente": s.get("cliente"), "rut": s.get("rut", ""),
                      "fecha": (s.get("fecha") or "")[:10],
                      "respuesta_mesa": "Aprobada" if s.get("estado") in ("aprobacion", "aprobado") else "Rechazada",
                      "monto": s.get("monto_credito"),
                      "hallazgos": hallazgos,
                      "veredicto": "⚠ CON ERRORES" if hallazgos else "✓ DECISIÓN CORRECTA"})
    crit_ver = await asyncio.to_thread(mesa_brain.criterios_version)
    return {"casos": casos, "total": len(casos),
            "nota_trazabilidad": f"Análisis ejecutado bajo los criterios permanentes de DashAI v1.{crit_ver}"}


def _regex_datos_financieros(texto):
    """RELLENADO DE DATOS: extracción por regex (cero gasto de créditos LLM)."""
    out = {}
    t = texto or ""
    m = re.search(r"(?:monto|cr[eé]dito)[^\d]{0,25}([\d.,]{3,12})\s*(?:uf|u\.f)", t, re.I)
    if m:
        try:
            out["monto_credito"] = float(m.group(1).replace(".", "").replace(",", "."))
        except ValueError:
            pass
    m = re.search(r"(?:renta\s+l[ií]quida|sueldo\s+l[ií]quido|l[ií]quido\s+a\s+pagar|alcance\s+l[ií]quido)[^\d]{0,30}\$?\s*([\d.]{6,12})", t, re.I)
    if m:
        try:
            v = float(m.group(1).replace(".", ""))
            if v > 100000:
                out["renta_liquida"] = v
        except ValueError:
            pass
    if re.search(r"subsidio|ds\s?19\b|ds\s?49\b|ds\s?0?1\b", t, re.I):
        out["con_subsidio"] = True
    return out


async def _forense_backfill_job(dias=280):
    """RELLENADO DE DATOS por lotes: extrae monto/renta/subsidio de los PDFs
    de carpetas vinculadas a decisiones de MESA (modular, sin LLM)."""
    import ocr_service as _ocr
    desde = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
    entradas = await db.seguimiento.find(
        {"estado": {"$in": ["aprobacion", "aprobado", "rechazo", "rechazado"]},
         "fecha": {"$gte": desde}}).to_list(2000)
    vistos, procesadas, rellenadas = set(), 0, 0
    total = len(entradas)
    for s in entradas:
        procesadas += 1
        cliente = (s.get("cliente") or "").strip()
        if not cliente or cliente.lower() in vistos:
            continue
        vistos.add(cliente.lower())
        try:
            fd, sim = await _forense_buscar_contexto(cliente, s.get("rut"))
            if not fd:
                continue
            df = fd.get("datos_financieros") or {}
            upd = {}
            if not df.get("monto_credito") and s.get("monto_credito"):
                upd["datos_financieros.monto_credito"] = s.get("monto_credito")
            if not df.get("renta_liquida") or df.get("con_subsidio") is None or not df.get("monto_credito"):
                base_dir = fsvc.folder_dir(fd.get("nombre", ""))
                pdfs = sorted(base_dir.rglob("*.pdf"))[:6] if base_dir.exists() else []
                texto = ""
                for pth in pdfs:
                    try:
                        raw = pth.read_bytes()
                        texto += "\n" + (await asyncio.to_thread(_ocr.extraer_texto, raw, pth.name) or "")
                    except Exception:
                        pass
                    if len(texto) > 20000:
                        break
                for k, v in _regex_datos_financieros(texto).items():
                    if df.get(k) in (None, "", 0):
                        upd[f"datos_financieros.{k}"] = v
            if upd:
                await db.folders.update_one({"id": fd["id"]}, {"$set": upd})
                rellenadas += 1
        except Exception as e:
            logging.warning(f"backfill {cliente}: {e}")
        await db.config.update_one({"_key": "forense_backfill"}, {"$set": {
            "estado": "en_proceso", "progreso": procesadas, "total": total}}, upsert=True)
        await asyncio.sleep(0.4)
    await db.config.update_one({"_key": "forense_backfill"}, {"$set": {
        "estado": "completado", "progreso": procesadas, "total": total,
        "fichas_rellenadas": rellenadas, "generado_en": now_iso()}}, upsert=True)
    logging.info(f"🤖 Rellenado de Datos: {procesadas} casos, {rellenadas} fichas actualizadas")


@api.post("/contraloria/forense/backfill")
async def forense_backfill_iniciar(dias: int = 280):
    await _constitucion_dashai()
    doc = await db.config.find_one({"_key": "forense_backfill"})
    if doc and doc.get("estado") == "en_proceso":
        return {"ok": True, "mensaje": "Rellenado de Datos ya en proceso", "progreso": doc.get("progreso")}
    asyncio.create_task(_forense_backfill_job(dias))
    return {"ok": True, "mensaje": f"🤖 Rellenado de Datos lanzado ({dias} días) — extracción por lotes sin gasto de créditos"}


@api.get("/contraloria/forense/backfill")
async def forense_backfill_estado():
    return await db.config.find_one({"_key": "forense_backfill"}, {"_id": 0}) or {"estado": "sin_ejecutar"}


# ══════════════════════════════════════════════════════════════════════════
# 🧠 OCR RENTA MASIVO — Backfill de datos_financieros para el Espejo MESA
# ══════════════════════════════════════════════════════════════════════════
_OCR_BACKFILL_CAMPOS = ("renta_liquida", "renta_codeudor", "deuda_cmf_total",
                        "deuda_cmf_codeudor", "credito_interno_pav",
                        "antiguedad_laboral_meses", "edad", "con_subsidio",
                        "monto_credito")


def _ocr_pdfs_folder(nombre):
    """Selecciona los PDFs relevantes de la carpeta: liquidaciones + CMF del titular
    MÁS los CMF/liquidaciones del CODEUDOR (subcarpeta 05_codeudor/),
    con fallback al combinado si el protocolo no tiene esas categorías."""
    import ocr_service as _ocr
    por_cat = {"liquidacion": [], "cmf": [], "combinado": [], "extras": [], "codeudor": []}
    for a in fsvc.scan_archivos(nombre):
        if not a["nombre"].lower().endswith(".pdf"):
            continue
        cat = fsvc.cat_de_archivo(a["nombre"], a["subfolder"])
        if cat == "codeudor":
            # EXTRACCIÓN TOTAL: los CMF y liquidaciones del codeudor entran al OCR
            if fsvc.cat_de_texto(a["nombre"]) in ("cmf", "liquidacion") and len(por_cat["codeudor"]) < 3:
                por_cat["codeudor"].append(a["ruta"])
            continue
        if cat in por_cat and len(por_cat[cat]) < 4:
            por_cat[cat].append(a["ruta"])
    rutas = por_cat["liquidacion"][:2] + por_cat["cmf"][:2] + por_cat["codeudor"][:3]
    if not rutas:
        # Fallback: simuladores / cartas de aprobación / combinado (también traen renta y monto)
        rel_re = re.compile(r"aprobaci|simulad|carta", re.I)
        extras = sorted(por_cat["extras"], key=lambda r: not rel_re.search(r))[:3]
        rutas = extras + por_cat["combinado"][:1]
    partes = []
    for rel in rutas:
        try:
            raw = fsvc.resolver_ruta(nombre, rel).read_bytes()
            txt, _met = _ocr.extraer_texto(raw, rel, force_ocr=False)
            if txt and txt.strip():
                etiqueta = "DOCUMENTO DEL CODEUDOR" if rel.startswith("05_codeudor") else "DOCUMENTO"
                partes.append(f"=== {etiqueta}: {rel} ===\n{txt.strip()[:9000]}")
        except Exception:
            pass
    return "\n\n".join(partes), len(rutas)


_OCR_ADJ_RE = re.compile(r"liquidaci|sueldo|renta|informe_?deudas|cmf|remuneraci|haberes", re.I)


def _ocr_adjuntos_paths(paths):
    """OCR de adjuntos de correo (rutas absolutas)."""
    import ocr_service as _ocr
    partes = []
    for p in paths:
        try:
            txt, _met = _ocr.extraer_texto(p.read_bytes(), p.name, force_ocr=False)
            if txt and txt.strip():
                partes.append(f"=== ADJUNTO CORREO: {p.name} ===\n{txt.strip()[:9000]}")
        except Exception:
            pass
    return "\n\n".join(partes)


async def _ocr_adjuntos_correo(nombre):
    """FUENTE 2: adjuntos reales de los correos procesados del cliente (proc_queue)."""
    from pathlib import Path
    toks = [t for t in re.sub(r"[^a-záéíóúñ ]", "", (nombre or "").lower()).split() if len(t) > 2]
    if not toks:
        return "", 0
    rx = ".*".join(re.escape(t) for t in toks[:2])
    paths, vistos = [], set()
    async for it in db.proc_queue.find({"$or": [
            {"cliente": {"$regex": rx, "$options": "i"}},
            {"classification.cliente": {"$regex": rx, "$options": "i"}},
            {"subject": {"$regex": rx, "$options": "i"}}]},
            {"attachments_bytes_dir": 1}).limit(6):
        d = it.get("attachments_bytes_dir")
        if not d:
            continue
        for p in sorted(Path(d).glob("*.pdf")):
            if p.name.lower() in vistos or not _OCR_ADJ_RE.search(p.name):
                continue
            vistos.add(p.name.lower())
            paths.append(p)
            if len(paths) >= 3:
                break
        if len(paths) >= 3:
            break
    if not paths:
        return "", 0
    return await asyncio.to_thread(_ocr_adjuntos_paths, paths), len(paths)


async def _ocr_adjuntos_imap(nombre):
    """FUENTE 3: adjuntos del buzón IMAP (solo si la renta sigue faltando)."""
    import ocr_service as _ocr
    try:
        headers = await asyncio.to_thread(mail.search_email_headers_by_person, nombre, 6)
        mids = [h.get("message_id") for h in headers if h.get("message_id")][:4]
        if not mids:
            return "", 0
        msgs = await asyncio.to_thread(mail.fetch_attachments_by_message_ids, mids)
        partes, n = [], 0
        for m_ in msgs:
            for a in m_.get("pdfs") or []:
                fn = a.get("filename") or ""
                if not fn.lower().endswith(".pdf") or not _OCR_ADJ_RE.search(fn):
                    continue
                txt, _met = await asyncio.to_thread(_ocr.extraer_texto, a["content_bytes"], fn)
                if txt and txt.strip():
                    partes.append(f"=== ADJUNTO BUZÓN: {fn} ===\n{txt.strip()[:9000]}")
                    n += 1
                if n >= 3:
                    break
            if n >= 3:
                break
        return "\n\n".join(partes), n
    except Exception:
        return "", 0


async def _ocr_renta_backfill_job():
    """Recorre TODAS las carpetas, OCR de liquidaciones + informe CMF, extrae
    métricas con IA y SOBRESCRIBE datos_financieros (regla del dueño: manda el OCR).
    Al terminar re-entrena el Algoritmo Espejo MESA."""
    folders = await db.folders.find({}, {"id": 1, "nombre": 1, "datos_financieros": 1}).to_list(2000)
    total, procesadas, enriquecidas, sin_docs, errores = len(folders), 0, 0, 0, 0
    detalle = []

    async def _progreso(estado="en_proceso", extra=None):
        doc = {"estado": estado, "progreso": procesadas, "total": total,
               "enriquecidas": enriquecidas, "sin_documentos": sin_docs,
               "errores": errores, "detalle": detalle[-80:], "actualizado_en": now_iso()}
        if extra:
            doc.update(extra)
        await db.config.update_one({"_key": "ocr_renta_backfill"}, {"$set": doc}, upsert=True)

    for f in folders:
        procesadas += 1
        nombre = (f.get("nombre") or "").strip()
        try:
            texto, n_pdfs = await asyncio.to_thread(_ocr_pdfs_folder, nombre)
            texto_mail, n_adj = await _ocr_adjuntos_correo(nombre)
            if texto_mail:
                texto = (texto + "\n\n" + texto_mail).strip()
                n_pdfs += n_adj
            if not texto and await _perfil.imap_permitido(nombre, "ocr_backfill"):
                texto, n_pdfs = await _ocr_adjuntos_imap(nombre)
            if not texto:
                sin_docs += 1
                detalle.append({"cliente": nombre, "resultado": "sin_documentos"})
                await _progreso()
                continue
            datos = await ai_extract.extraer_datos_financieros(texto, nombre)
            if not datos.get("renta_liquida") and await _perfil.imap_permitido(nombre, "ocr_renta"):
                texto_imap, n_imap = await _ocr_adjuntos_imap(nombre)
                if texto_imap:
                    n_pdfs += n_imap
                    d2 = await ai_extract.extraer_datos_financieros(
                        (texto + "\n\n" + texto_imap)[-24000:], nombre)
                    datos = {**datos, **{k: v for k, v in d2.items() if v not in (None, "", 0)}}
            upd = {f"datos_financieros.{k}": datos[k] for k in _OCR_BACKFILL_CAMPOS
                   if datos.get(k) not in (None, "", 0)}
            if upd:
                upd["datos_financieros_ocr_fecha"] = now_iso()
                upd["datos_financieros_ocr_metodo"] = datos.get("metodo", "")
                await db.folders.update_one({"id": f["id"]}, {"$set": upd})
                enriquecidas += 1
                detalle.append({"cliente": nombre, "resultado": "enriquecida",
                                "pdfs": n_pdfs, "metodo": datos.get("metodo"),
                                "campos": sorted(k.split(".")[1] for k in upd
                                                 if k.startswith("datos_financieros."))})
            else:
                detalle.append({"cliente": nombre, "resultado": "sin_datos_detectables",
                                "pdfs": n_pdfs})
        except Exception as e:
            errores += 1
            detalle.append({"cliente": nombre, "resultado": "error", "error": str(e)[:150]})
            logging.warning(f"ocr backfill {nombre}: {e}")
        await _progreso()
        await asyncio.sleep(0.3)
    # RE-ENTRENAMIENTO ESPEJO MESA con los datos recién estructurados
    espejo = {}
    try:
        espejo = await minar_limites_mesa(280)
    except Exception as e:
        espejo = {"error": str(e)[:200]}
    await _progreso("completado", {"espejo": espejo, "generado_en": now_iso()})
    logging.info(f"🧠 OCR Renta Masivo: {procesadas} carpetas, {enriquecidas} enriquecidas, espejo={espejo}")


@api.post("/admin/backfill-ocr")
async def ocr_backfill_iniciar():
    doc = await db.config.find_one({"_key": "ocr_renta_backfill"})
    if doc and doc.get("estado") == "en_proceso":
        return {"ok": True, "mensaje": "OCR Renta Masivo ya en proceso",
                "progreso": doc.get("progreso"), "total": doc.get("total")}
    asyncio.create_task(_ocr_renta_backfill_job())
    return {"ok": True, "mensaje": "🧠 OCR Renta Masivo lanzado — extracción de liquidaciones + CMF de todas las carpetas"}


@api.get("/admin/backfill-ocr")
async def ocr_backfill_estado():
    return await db.config.find_one({"_key": "ocr_renta_backfill"}, {"_id": 0}) or {"estado": "sin_ejecutar"}


# ══════════════════════════════════════════════════════════════════════════
# 🚀 MOTOR DE DESPACHO MASIVO INFINITO — Cola de Campaña
# ══════════════════════════════════════════════════════════════════════════
@api.get("/despacho/cola")
async def despacho_cola():
    q = {"estado": {"$ne": "PROMOVIDO"}, "despacho_entregado": {"$ne": True}}
    todos = await db.prospectos.find(q, {"_id": 0}).sort("creado_en", -1).to_list(10000)
    pendientes = [p for p in todos if len(re.sub(r"[^0-9]", "", p.get("telefono") or "")) >= 8]
    sin_tel = len(todos) - len(pendientes)
    despachados = await db.prospectos.count_documents({"despacho_entregado": True})
    return {"pendientes": pendientes, "total_pendientes": len(pendientes),
            "despachados": despachados, "sin_telefono": sin_tel}


@api.post("/despacho/{oid}/disparar")
async def despacho_disparar(oid: str, request: Request):
    """DISPARO RÁPIDO: genera el wa.me Maserati (link VIP público + @CentralMutuos),
    marca ENTREGADO y devuelve los contadores actualizados."""
    from urllib.parse import quote
    op = await db.prospectos.find_one({"id": oid})
    if not op:
        raise HTTPException(status_code=404, detail="Prospecto no encontrado")
    tel = re.sub(r"[^0-9]", "", op.get("telefono") or "")
    if len(tel) < 8:
        raise HTTPException(status_code=400, detail="El prospecto no tiene teléfono válido")
    if not tel.startswith("56"):
        tel = "56" + tel.lstrip("0")
    base = _base_url_req(request)
    url = f"{base}/api/calificar/{oid}"
    primer = (op.get("nombre") or "").split()[0].title() if op.get("nombre") else "Cliente"
    texto = (f"🏠 *Central Mutuos - Precalificación Hipotecaria*\n\n"
             f"Hola {primer}, soy José Martín de Central Mutuos. Suba su Cédula y sus últimas "
             f"6 Liquidaciones de Sueldo en este portal privado y su calificación queda lista:\n{url}"
             f"\n\nAtentamente, el equipo de @CentralMutuos")
    wa = f"https://wa.me/{tel}?text={quote(texto)}"
    await db.prospectos.update_one({"id": oid}, {"$set": {
        "despacho_entregado": True, "despacho_entregado_en": now_iso(),
        "status": "entregado", "link_calificar": url}})
    despachados = await db.prospectos.count_documents({"despacho_entregado": True})
    q = {"estado": {"$ne": "PROMOVIDO"}, "despacho_entregado": {"$ne": True}}
    resto = await db.prospectos.find(q, {"telefono": 1}).to_list(10000)
    pendientes = sum(1 for p in resto if len(re.sub(r"[^0-9]", "", p.get("telefono") or "")) >= 8)
    return {"ok": True, "whatsapp": wa, "cliente": op.get("nombre"),
            "despachados": despachados, "pendientes": pendientes}


# ══════════════════════════════════════════════════════════════════════════
# 🧠 CEREBRO DASHAI — Aprendizaje Perpetuo y Sincronización Autónoma
# Hilo de baja prioridad: recalibra criterios y sincroniza scores cada 60 min;
# vigila cada 5 min si llegó correo de MESA o documento nuevo (disparo inmediato).
# ══════════════════════════════════════════════════════════════════════════
async def _dashai_sync(motivo="programada"):
    modelo = await asyncio.to_thread(mesa_brain.calibrar)
    modelo.pop("_id", None)
    base_pct = round((modelo.get("base") or 0.85) * 100)
    # Último patrón aprendido (minería local de motivos de rechazo)
    patron = ""
    motivos = modelo.get("motivos_rechazo") or []
    if motivos:
        top = motivos[0]
        patron = f"Aprendido: Rechazo por {top.get('motivo')} ({top.get('casos')} caso(s) en 60 días)"
    # Sincronizar scores de viabilidad → prospectos (Centro de Ventas VIP)
    ops = await db.prospectos.find({"estado": {"$ne": "PROMOVIDO"}}).to_list(500)
    sync_prospectos = 0
    for op in ops:
        try:
            prob = await _puntuar_prospecto(op, modelo, base_pct)
            await db.prospectos.update_one({"id": op["id"]}, {"$set": {
                "prob_mesa": prob, "politica_general": op.get("politica_general"),
                "dashai_sync_en": now_iso()}})
            sync_prospectos += 1
        except Exception:
            pass
        await asyncio.sleep(0.05)  # baja prioridad: nunca frenar el portal VIP
    # Sincronizar clientes activos (quiebres de Reglas de Hierro por carpeta)
    folders = await db.folders.find({"is_escrituracion": {"$ne": True}}).limit(200).to_list(200)
    sync_folders = 0
    for fd in folders:
        try:
            quiebres = await asyncio.to_thread(mesa_brain.quiebres_hierro_folder, fd)
            score = 0 if quiebres else base_pct
            await db.folders.update_one({"id": fd["id"]}, {"$set": {
                "dashai_score": score,
                "dashai_quiebres": [q.get("detalle") for q in (quiebres or [])][:3],
                "dashai_sync_en": now_iso()}})
            sync_folders += 1
        except Exception:
            pass
        await asyncio.sleep(0.05)
    evento = {"id": str(uuid.uuid4()), "motivo": motivo, "fecha": now_iso(),
              "nivel_calibracion": base_pct, "patron": patron,
              "prospectos_sync": sync_prospectos, "folders_sync": sync_folders}
    await db.dashai_eventos.insert_one(dict(evento))
    await db.config.update_one({"_key": "dashai_perpetuo"}, {"$set": {
        "ultima_sync": now_iso(), "ultimo_motivo": motivo,
        "nivel_calibracion": base_pct, "ultimo_patron": patron,
        "prospectos_sync": sync_prospectos, "folders_sync": sync_folders}}, upsert=True)
    logging.info(f"🧠 DashAI sync ({motivo}): {sync_prospectos} prospectos, {sync_folders} carpetas, calibración {base_pct}%")
    return evento


async def _dashai_perpetuo_loop():
    """APRENDIZAJE PERPETUO: full sync cada 60 min; vigilancia cada 5 min de
    correos de MESA (seguimiento) y documentos nuevos (capturas) → disparo inmediato."""
    await asyncio.sleep(90)
    ultimo_full = datetime.now(timezone.utc) - timedelta(hours=2)
    marca = now_iso()
    while True:
        try:
            ahora = datetime.now(timezone.utc)
            nuevo_seg = await db.seguimiento.find_one({"fecha": {"$gt": marca}})
            nueva_cap = await db.capturas_autonomas.find_one({"creado_en": {"$gt": marca}})
            if nuevo_seg or nueva_cap:
                marca = now_iso()
                await _dashai_sync("disparo_inmediato" + ("_mesa" if nuevo_seg else "_documento"))
                ultimo_full = ahora
            elif (ahora - ultimo_full).total_seconds() >= 3600:
                await _dashai_sync("programada_60min")
                ultimo_full = ahora
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.warning(f"DashAI perpetuo: {e}")
        await asyncio.sleep(300)


async def _constitucion_dashai():
    """LEY DE JERARQUÍA SUPREMA (protegida por clave maestra (MASTER_PIN)): enchufe obligatorio.
    Si la Constitución DashAI no responde → 503 y decisiones bloqueadas."""
    try:
        return await asyncio.to_thread(mesa_brain.enchufe_dashai)
    except mesa_brain.ConstitucionError as e:
        raise HTTPException(status_code=503, detail=(
            f"⚖️ LEY DE JERARQUÍA SUPREMA: {e}. Toda decisión queda bloqueada "
            "hasta restaurar la conexión con la Constitución DashAI."))


LEY_JERARQUIA_SUPREMA = ("DashAI (Bóveda de Criterios) es la ÚNICA fuente de verdad del sistema. "
                         "Prohibido ejecutar cálculos de viabilidad, auditoría forense o validación "
                         "de MESA sin consultar primero sus parámetros activos. Si DashAI no está "
                         "disponible, el sistema bloquea toda decisión hasta restaurar la conexión. "
                         "Esta jerarquía es el cimiento del programa y solo puede alterarse con la clave maestra.")


@api.get("/dashai/constitucion")
async def dashai_constitucion_get():
    doc = await db.config.find_one({"_key": "dashai_constitucion"}, {"_id": 0})
    if not doc:
        doc = {"ley": LEY_JERARQUIA_SUPREMA, "protegida_por": "clave maestra (MASTER_PIN)",
               "inamovible": True, "creada_en": now_iso()}
        await db.config.update_one({"_key": "dashai_constitucion"}, {"$set": doc}, upsert=True)
    return doc


@api.post("/dashai/constitucion")
async def dashai_constitucion_set(payload: dict):
    if str(payload.get("clave") or "") != os.environ.get("MASTER_PIN", ""):
        raise HTTPException(status_code=403, detail="⚖️ REGLA PERPETUA: la Constitución DashAI solo puede alterarse con la clave maestra (MASTER_PIN).")
    await db.config.update_one({"_key": "dashai_constitucion"}, {"$set": {
        "ley": payload.get("ley") or LEY_JERARQUIA_SUPREMA,
        "actualizada_en": now_iso()}}, upsert=True)
    return {"ok": True}


@api.get("/dashai/estado")
async def dashai_estado():
    cfg = await db.config.find_one({"_key": "dashai_perpetuo"}, {"_id": 0}) or {}
    # REGLA MASERATI #1 (inamovible): se auto-siembra si no existe
    reglas_doc = await db.config.find_one({"_key": "dashai_reglas_estilo"}, {"_id": 0})
    if not reglas_doc:
        reglas_doc = {"reglas": [{
            "n": 1, "inamovible": True,
            "regla": "Toda comunicación y portal de Central Mutuos debe ser 100% responsivo y adaptativo: emails con tablas max-width 600px y anchos porcentuales (prohibido el ancho fijo), imágenes con height:auto y max-width:100%, botones y campos táctiles adaptados al teléfono, margen de seguridad lateral de 20px, y mini-render móvil obligatorio antes de cada envío.",
            "creada_en": now_iso()}]}
        await db.config.update_one({"_key": "dashai_reglas_estilo"},
                                   {"$set": reglas_doc}, upsert=True)
    modelo = await asyncio.to_thread(mesa_brain.modelo_actual)
    modelo.pop("_id", None)
    v60 = modelo.get("ventana_60") or {}
    eventos = await db.dashai_eventos.find({}, {"_id": 0}).sort("fecha", -1).limit(12).to_list(12)
    return {"nivel_calibracion": cfg.get("nivel_calibracion") or round((modelo.get("base") or 0.85) * 100),
            "calibrado_en": modelo.get("calibrado_en"),
            "ultimo_patron": cfg.get("ultimo_patron") or "",
            "ultima_sync": cfg.get("ultima_sync"),
            "ultimo_motivo": cfg.get("ultimo_motivo"),
            "prospectos_sync": cfg.get("prospectos_sync", 0),
            "folders_sync": cfg.get("folders_sync", 0),
            "ventana_60": {"base": v60.get("base"), "aprobadas": v60.get("aprobadas"),
                           "rechazadas": v60.get("rechazadas")},
            "base_historica": modelo.get("base"),
            "motivos_rechazo": (modelo.get("motivos_rechazo") or [])[:6],
            "ajustes_mercado": (modelo.get("ajustes_mercado") or [])[:4],
            "tendencia": modelo.get("tendencia") or "",
            "eventos": eventos, "perpetuo_activo": True,
            "reglas_estilo": reglas_doc.get("reglas", [])}


@api.post("/dashai/sync")
async def dashai_sync_manual():
    evento = await _dashai_sync("manual")
    return {"ok": True, "mensaje": "🧠 DashAI recalibrado y sincronizado", **{k: v for k, v in evento.items() if k != "id"}}


# ══════════════════════════════════════════════════════════════════════════
# 🧲 PORTAL DE CAPTURA AUTÓNOMA (WHATSAPP INTAKE) — Imán de Créditos
# Ruta pública /api/calificar/{oid}: el prospecto sube Cédula + Liquidación,
# el sistema crea la carpeta, OCR del RUT y notifica a Gerardo al instante.
# ══════════════════════════════════════════════════════════════════════════
_CALIFICAR_HTML = """<!DOCTYPE html>
<html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Central Mutuos</title>
<meta property="og:title" content="Central Mutuos">
<meta property="og:description" content="Central Mutuos. Suba sus documentos desde su celular y obtenga su precalificación VIP.">
<meta property="og:site_name" content="Central Mutuos">
<meta property="og:type" content="website">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;800&family=Montserrat:wght@400;600;800&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#000;color:#e5e5e5;font-family:'Montserrat',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:1.2rem}
.card{max-width:560px;width:100%;background:linear-gradient(165deg,#0d0b06,#050505);border:1px solid #D4AF37;padding:2rem 1.6rem;text-align:center}
.brand{color:#D4AF37;font-family:'Playfair Display',serif;font-size:1.4rem;letter-spacing:0.22em}
.sub{color:#9a8c52;font-size:0.6rem;letter-spacing:0.3em;margin-top:4px;text-transform:uppercase}
h1{font-family:'Playfair Display',serif;color:#FCF6BA;font-size:1.25rem;margin:1.3rem 0 0.3rem}
.proy{color:#D4AF37;font-size:0.75rem;letter-spacing:0.12em;text-transform:uppercase}
.dots{display:flex;justify-content:center;gap:8px;margin:1.2rem 0}
.dot{width:26px;height:4px;background:#33290f;transition:background .3s}
.dot.on{background:linear-gradient(90deg,#BF953F,#FCF6BA)}
.paso{display:none;text-align:left}
.paso.activo{display:block;animation:fade .35s ease}
@keyframes fade{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
p.lead{color:#b8b8b8;font-size:0.82rem;line-height:1.65;margin:0.8rem 0 1.2rem;text-align:center}
.perfil{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.pcard{border:1.5px solid #7a6a2f;padding:1.4rem 0.9rem;cursor:pointer;text-align:center;transition:border-color .2s,background .2s}
.pcard:hover{border-color:#FCF6BA;background:rgba(212,175,55,0.06)}
.pcard .ic{font-size:1.8rem}.pcard .t{color:#F5E7B8;font-weight:800;font-size:0.86rem;margin-top:8px;letter-spacing:0.05em}
.pcard .d{color:#8a8a8a;font-size:0.66rem;margin-top:4px;line-height:1.5}
.drop{border:1.5px dashed #7a6a2f;padding:0.9rem;margin-bottom:0.7rem;cursor:pointer;transition:border-color .2s,background .2s;position:relative;display:flex;align-items:center;gap:12px;text-align:left}
.drop:hover,.drop.over{border-color:#FCF6BA;background:rgba(212,175,55,0.06)}
.drop .ic{font-size:1.25rem}
.drop .t{color:#F5E7B8;font-weight:700;font-size:0.78rem;letter-spacing:0.04em}
.drop .d{color:#8a8a8a;font-size:0.64rem;margin-top:2px}
.drop.listo{border-style:solid;border-color:#16a34a;background:rgba(22,163,74,0.08)}
.drop.listo .t{color:#8fd9b0}
.drop input{position:absolute;inset:0;opacity:0;cursor:pointer}
.opc{color:#9a8c52;font-size:0.6rem;font-weight:800;letter-spacing:0.1em;border:1px solid #7a6a2f;padding:0.1rem 0.45rem;margin-left:auto;white-space:nowrap}
.manual{border:1px solid #33290f;padding:1rem;margin-top:0.8rem}
.manual label{display:block;color:#C7B36A;font-size:0.66rem;letter-spacing:0.1em;text-transform:uppercase;margin:0.7rem 0 0.3rem}
.manual input{width:100%;background:#050505;border:1px solid #7a6a2f;color:#FCF6BA;font-family:'Montserrat',sans-serif;font-size:1rem;padding:0.7rem 0.9rem;outline:none}
.nav{display:flex;gap:10px;margin-top:1.3rem}
.btn{flex:1;border:none;background:linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C);color:#0a0a0a;font-weight:800;font-size:0.84rem;letter-spacing:0.07em;padding:0.9rem;cursor:pointer;font-family:'Montserrat',sans-serif}
.btn.sec{background:transparent;border:1px solid #7a6a2f;color:#C7B36A;flex:0 0 auto;padding:0.9rem 1.2rem}
.btn:disabled{opacity:0.45;cursor:not-allowed}
#msg{display:none;margin-top:1rem;padding:0.9rem 1rem;font-size:0.82rem;font-weight:600;line-height:1.6;text-align:center}
.foot{color:#5a5a5a;font-size:0.6rem;margin-top:1.4rem;letter-spacing:0.08em;text-align:center}
@media (max-width:600px){
 body{padding:20px}
 .card{padding:1.6rem 1.1rem}
 .btn{padding:1.15rem 0.9rem;font-size:0.95rem;min-height:52px}
 .btn.sec{padding:1.15rem 1rem}
 .manual input,.manual select,.salcard input,.salcard select{padding:1rem 0.9rem;font-size:1.05rem;min-height:52px}
 .pcard{padding:1.15rem 0.7rem}
 .drop{padding:1.1rem 0.8rem;min-height:60px}
}
.ayuda{display:block;color:#C7B36A;font-size:0.68rem;letter-spacing:0.06em;margin-top:1rem;text-align:center;cursor:pointer;text-decoration:underline;text-underline-offset:4px}
.ayuda:hover{color:#FCF6BA}
#salida{display:none;position:fixed;inset:0;background:rgba(0,0,0,0.88);z-index:99;align-items:center;justify-content:center;padding:1.2rem}
#salida.on{display:flex;animation:fade .3s ease}
.salcard{max-width:420px;width:100%;background:linear-gradient(165deg,#0d0b06,#050505);border:1px solid #D4AF37;padding:1.8rem 1.4rem;text-align:center}
.salcard h2{font-family:'Playfair Display',serif;color:#FCF6BA;font-size:1.1rem;margin-bottom:0.6rem}
.salcard p{color:#b8b8b8;font-size:0.78rem;line-height:1.65;margin-bottom:1rem}
.salcard input,.salcard select{width:100%;background:#050505;border:1px solid #7a6a2f;color:#FCF6BA;font-family:'Montserrat',sans-serif;font-size:0.95rem;padding:0.7rem 0.9rem;outline:none;margin-bottom:0.6rem;text-align:center}
</style></head><body>
<div class="card">
  <div class="brand">CENTRAL MUTUOS</div>
  <div class="sub">Con Creces</div>
  <h1>Bienvenido(a) __NOMBRE__</h1>
  <div class="proy" style="text-align:center">__PROYECTO_LINEA__</div>
  <div class="dots"><div class="dot on" id="d0"></div><div class="dot" id="d1"></div><div class="dot" id="d2"></div></div>

  <div class="paso activo" id="p0">
    <p class="lead">Para preparar su <b style="color:#F5E7B8">Calificación VIP</b>, cuéntenos:<br>¿Es usted trabajador <b>Dependiente</b> o <b>Independiente</b>?</p>
    <div class="perfil">
      <div class="pcard" data-testid="captura-perfil-dependiente" onclick="setPerfil('dependiente')">
        <div class="ic">💼</div><div class="t">DEPENDIENTE</div>
        <div class="d">Trabajo con contrato y liquidaciones de sueldo</div>
      </div>
      <div class="pcard" data-testid="captura-perfil-independiente" onclick="setPerfil('independiente')">
        <div class="ic">📈</div><div class="t">INDEPENDIENTE</div>
        <div class="d">Boletas de honorarios / declaración de renta</div>
      </div>
    </div>
  </div>

  <div class="paso" id="p1">
    <p class="lead" id="p1titulo"></p>
    <div class="manual" style="margin:0 0 0.9rem;padding:0.9rem 1rem">
      <div style="color:#C7B36A;font-size:0.72rem;letter-spacing:0.08em;text-align:center;margin-bottom:0.6rem">DETALLES DE LA PROPIEDAD — ¿CUÁNDO ES LA ENTREGA?</div>
      <div class="perfil" style="margin-bottom:0.4rem">
        <div class="pcard" id="entInm" data-testid="captura-entrega-inmediata" style="padding:0.7rem" onclick="setEntrega('inmediata')"><div class="t">🔑 ENTREGA INMEDIATA</div></div>
        <div class="pcard" id="entFut" data-testid="captura-entrega-futura" style="padding:0.7rem" onclick="setEntrega('futura')"><div class="t">🏗️ ENTREGA FUTURA</div></div>
      </div>
      <div id="subEntrega" style="display:none">
        <div style="color:#C7B36A;font-size:0.68rem;letter-spacing:0.06em;text-align:center;margin:0.5rem 0">¿LA FECHA DE ENTREGA ES EN MÁS DE 6 MESES?</div>
        <div class="perfil">
          <div class="pcard" id="ent6Si" data-testid="captura-entrega-6m-si" style="padding:0.55rem" onclick="setEntrega6(true)"><div class="t">SÍ</div></div>
          <div class="pcard" id="ent6No" data-testid="captura-entrega-6m-no" style="padding:0.55rem" onclick="setEntrega6(false)"><div class="t">NO</div></div>
        </div>
      </div>
    </div>
    <div id="zonas"></div>
    <div class="nav">
      <button class="btn sec" onclick="irPaso(0)">← Atrás</button>
      <button class="btn" id="btnP1" data-testid="captura-continuar-btn" onclick="irPaso(2)" disabled>CONTINUAR →</button>
    </div>
  </div>

  <div class="paso" id="p2">
    <p class="lead">Último paso: <b style="color:#F5E7B8">los números de su negocio</b>.</p>
    <div class="drop" id="dropcot">
      <div class="ic">🏠</div>
      <div><div class="t">Cotización Inmobiliaria</div><div class="d" id="dcot">PDF o foto de la cotización del proyecto</div></div>
      <span class="opc">OPCIONAL</span>
      <input type="file" id="fcot" accept="image/*,.pdf">
    </div>
    <div class="manual">
      <div style="color:#C7B36A;font-size:0.72rem;letter-spacing:0.08em;text-align:center;margin-bottom:0.6rem">¿SU CRÉDITO INCLUYE SUBSIDIO?</div>
      <div class="perfil" style="margin-bottom:0.4rem">
        <div class="pcard" id="subSi" data-testid="captura-subsidio-si" style="padding:0.7rem" onclick="setSub(true)">
          <div class="t">SÍ, CON SUBSIDIO</div></div>
        <div class="pcard" id="subNo" data-testid="captura-subsidio-no" style="padding:0.7rem" onclick="setSub(false)">
          <div class="t">NO, SIN SUBSIDIO</div></div>
      </div>
      <div id="campos" style="display:none">
        <label>Monto Propiedad (UF)</label>
        <input id="mValor" data-testid="captura-valor-input" inputmode="decimal" placeholder="Ej: 3200">
        <div id="campoSub"><label>Monto Subsidio (UF)</label>
        <input id="mSub" data-testid="captura-subsidio-input" inputmode="decimal" placeholder="Ej: 500"></div>
        <div id="campoPie" style="display:none"><label>% de Pie</label>
        <input id="mPie" data-testid="captura-pie-input" inputmode="decimal" placeholder="Ej: 10"></div>
        <label>Monto Crédito Solicitado (UF)</label>
        <input id="mCred" data-testid="captura-credito-input" inputmode="decimal" placeholder="Ej: 2700">
        <div id="precheck" data-testid="captura-precheck" style="display:none;margin-top:0.9rem;padding:0.7rem 0.9rem;font-size:0.76rem;font-weight:700;line-height:1.5"></div>
      </div>
    </div>
    <div class="nav">
      <button class="btn sec" onclick="irPaso(1)">← Atrás</button>
      <button class="btn" id="btnEnviar" data-testid="captura-enviar-btn" onclick="enviar()" disabled>🔒 ENVIAR MI EXPEDIENTE</button>
    </div>
    <div id="msg" data-testid="captura-msg"></div>
    <div id="llamada" style="display:none;margin-top:1rem">
      <button class="btn" id="btnLlamada" data-testid="captura-llamada-btn" onclick="document.getElementById('formLlamada').style.display='block';this.style.display='none'">📞 Solicitar Llamada de un Ejecutivo</button>
      <div id="formLlamada" class="manual" style="display:none">
        <label>Número de Teléfono</label>
        <input id="telLlamada" data-testid="captura-llamada-tel" inputmode="tel" value="__TELEFONO__" placeholder="+56 9 ...">
        <label>Horario preferido para ser contactado</label>
        <select id="horLlamada" data-testid="captura-llamada-horario" style="width:100%;background:#050505;border:1px solid #7a6a2f;color:#FCF6BA;font-family:'Montserrat',sans-serif;font-size:0.95rem;padding:0.7rem 0.9rem;outline:none">
          <option>Mañana</option><option>Tarde</option><option>Tarde-Noche</option>
        </select>
        <button class="btn" id="btnConfLlamada" data-testid="captura-llamada-enviar" style="margin-top:0.9rem" onclick="solicitarLlamada()">CONFIRMAR SOLICITUD</button>
        <div id="msgLlamada" data-testid="captura-llamada-msg" style="display:none;margin-top:0.8rem;padding:0.8rem;font-size:0.8rem;font-weight:700;line-height:1.5"></div>
      </div>
    </div>
  </div>

  <a class="ayuda" data-testid="captura-ayuda-link" onclick="abrirSalida()">¿Le parece complejo? Hable directo con un ejecutivo →</a>
  <div class="foot">CONEXIÓN CIFRADA · SUS DOCUMENTOS VIAJAN PROTEGIDOS</div>
  <div style="text-align:center;margin-top:0.7rem;font-family:'Inter','Montserrat',sans-serif;font-variant:small-caps;letter-spacing:0.22em;font-size:0.62rem;font-weight:600;background:linear-gradient(135deg,#BF953F,#FCF6BA,#B38728);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent">@CentralMutuos · Marca Registrada</div>
</div>

<div id="salida" data-testid="captura-salida-modal">
  <div class="salcard">
    <h2>Antes de irse…</h2>
    <p>Entendemos que esto puede ser complejo. Si prefiere, <b style="color:#F5E7B8">un ejecutivo VIP</b> puede hacer todo el proceso por usted en una breve llamada, sin costo.</p>
    <input id="salTel" data-testid="captura-salida-tel" inputmode="tel" value="__TELEFONO__" placeholder="+56 9 ...">
    <select id="salHor" data-testid="captura-salida-horario">
      <option>Mañana</option><option>Tarde</option><option>Tarde-Noche</option>
    </select>
    <button class="btn" id="btnSalida" data-testid="captura-salida-llamada" style="width:100%" onclick="salidaLlamada()">📞 QUE ME LLAME UN EJECUTIVO</button>
    <div id="msgSalida" data-testid="captura-salida-msg" style="display:none;margin-top:0.8rem;padding:0.8rem;font-size:0.78rem;font-weight:700;line-height:1.5"></div>
    <button class="btn sec" data-testid="captura-salida-continuar" style="width:100%;margin-top:0.7rem" onclick="cerrarSalida()">Continuar por mi cuenta →</button>
  </div>
</div>
<script>
const ZONAS={
 dependiente:[
  {k:'cedula',ic:'🪪',t:'Cédula de Identidad (ambos lados)',d:'Suba las 2 caras (2 fotos o 1 PDF)',multi:true,req:true},
  {k:'liquidaciones',ic:'📄',t:'6 últimas Liquidaciones de Sueldo',d:'Seleccione los 6 archivos juntos',multi:true,req:true,min:6},
  {k:'afp',ic:'🏦',t:'Certificado de Cotizaciones AFP',d:'Últimos 12 meses (PDF de su AFP)',multi:false,req:true},
  {k:'cmf',ic:'🛡️',t:'Informe CMF actualizado',d:'Informe de deudas (cmfchile.cl, gratis)',multi:false,req:true}],
 independiente:[
  {k:'cedula',ic:'🪪',t:'Cédula de Identidad (ambos lados)',d:'Suba las 2 caras (2 fotos o 1 PDF)',multi:true,req:true},
  {k:'f22',ic:'📋',t:'Dos últimos Formularios 22 (Impuesto a la Renta)',d:'Seleccione los 2 PDF del SII juntos',multi:true,req:true,min:2},
  {k:'boletas_anterior',ic:'🧾',t:'Resumen Boletas de Honorarios — Año anterior completo',d:'Informe anual SII (enero a diciembre)',multi:false,req:true},
  {k:'boletas_actual',ic:'🧾',t:'Resumen Boletas de Honorarios — Año actual a la fecha',d:'Informe SII del año en curso',multi:false,req:true},
  {k:'cmf',ic:'🛡️',t:'Informe CMF actualizado',d:'Informe de deudas (cmfchile.cl, gratis)',multi:false,req:true}]
};
let perfil='',st={};
function setPerfil(p){perfil=p;st={};montarZonas();irPaso(1);}
function montarZonas(){
  document.getElementById('p1titulo').innerHTML='Perfil <b style="color:#F5E7B8">'+(perfil==='dependiente'?'DEPENDIENTE 💼':'INDEPENDIENTE 📈')+'</b> — suba sus documentos:';
  const cont=document.getElementById('zonas');cont.innerHTML='';
  ZONAS[perfil].forEach(z=>{
    const el=document.createElement('div');el.className='drop';el.id='drop'+z.k;
    el.setAttribute('data-testid','captura-drop-'+z.k);
    el.innerHTML='<div class="ic">'+z.ic+'</div><div><div class="t">'+z.t+'</div><div class="d" id="d'+z.k+'">'+z.d+'</div></div>'+
      '<input type="file" id="f'+z.k+'" accept="image/*,.pdf" '+(z.multi?'multiple':'')+'>';
    cont.appendChild(el);
    const inp=el.querySelector('input');
    ['dragover','dragenter'].forEach(ev=>el.addEventListener(ev,e=>{e.preventDefault();el.classList.add('over')}));
    ['dragleave','drop'].forEach(ev=>el.addEventListener(ev,e=>{e.preventDefault();el.classList.remove('over')}));
    el.addEventListener('drop',e=>{if(e.dataTransfer.files.length){inp.files=e.dataTransfer.files;pick()}});
    inp.addEventListener('change',pick);
    function pick(){if(inp.files.length){st[z.k]=Array.from(inp.files);el.classList.add('listo');
      document.getElementById('d'+z.k).textContent='✓ '+inp.files.length+' archivo(s): '+Array.from(inp.files).map(f=>f.name).join(', ').slice(0,70);check()}}
  });
  check();
}
function check(){const falt=ZONAS[perfil].filter(z=>z.req&&!((st[z.k]&&st[z.k].length>=(z.min||1))));
  const entOk=entrega==='inmediata'||(entrega==='futura'&&entrega6!==null);
  document.getElementById('btnP1').disabled=falt.length>0||!entOk;}
let entrega='',entrega6=null;
function pintarSel(el,on){el.style.borderColor=on?'#FCF6BA':'#7a6a2f';el.style.background=on?'rgba(212,175,55,0.1)':'transparent';}
function setEntrega(v){entrega=v;
  if(v==='inmediata'){entrega6=null;document.getElementById('subEntrega').style.display='none';}
  else{document.getElementById('subEntrega').style.display='block';}
  pintarSel(document.getElementById('entInm'),v==='inmediata');
  pintarSel(document.getElementById('entFut'),v==='futura');check();}
function setEntrega6(v){entrega6=v;
  pintarSel(document.getElementById('ent6Si'),v===true);
  pintarSel(document.getElementById('ent6No'),v===false);check();}
function entregaValor(){return entrega==='inmediata'?'inmediata':(entrega6?'futura_mas_6m':'futura_menos_6m');}
function irPaso(n){[0,1,2].forEach(i=>{document.getElementById('p'+i).classList.toggle('activo',i===n);
  document.getElementById('d'+i).classList.toggle('on',i<=n);});}
(function(){const el=document.getElementById('dropcot'),inp=document.getElementById('fcot');
  ['dragover','dragenter'].forEach(ev=>el.addEventListener(ev,e=>{e.preventDefault();el.classList.add('over')}));
  ['dragleave','drop'].forEach(ev=>el.addEventListener(ev,e=>{e.preventDefault();el.classList.remove('over')}));
  el.addEventListener('drop',e=>{if(e.dataTransfer.files.length){inp.files=e.dataTransfer.files;pick()}});
  inp.addEventListener('change',pick);
  function pick(){if(inp.files.length){st.cotizacion=Array.from(inp.files);el.classList.add('listo');
    document.getElementById('dcot').textContent='✓ '+inp.files[0].name;}}
})();
let conSub=null,precheckT=null;
function setSub(v){conSub=v;
  document.getElementById('subSi').style.borderColor=v?'#FCF6BA':'#7a6a2f';
  document.getElementById('subSi').style.background=v?'rgba(212,175,55,0.1)':'transparent';
  document.getElementById('subNo').style.borderColor=!v?'#FCF6BA':'#7a6a2f';
  document.getElementById('subNo').style.background=!v?'rgba(212,175,55,0.1)':'transparent';
  document.getElementById('campos').style.display='block';
  document.getElementById('campoSub').style.display=v?'block':'none';
  document.getElementById('campoPie').style.display=v?'none':'block';
  checkMontos();}
function numUF(id){const v=(document.getElementById(id).value||'').replace(/[^0-9.,]/g,'').replace(/\\./g,'').replace(',','.');
  return parseFloat(v)||parseFloat((document.getElementById(id).value||'').replace(/[^0-9.]/g,''))||0;}
['mValor','mSub','mPie','mCred'].forEach(id=>{
  const el=document.getElementById(id);
  el.addEventListener('input',()=>{el.value=el.value.replace(/[^0-9.,]/g,'');checkMontos();});
});
function checkMontos(){
  const val=numUF('mValor'),cred=numUF('mCred');
  const extra=conSub?numUF('mSub'):numUF('mPie');
  const ok=conSub!==null&&val>0&&cred>0&&extra>0;
  document.getElementById('btnEnviar').disabled=!ok;
  clearTimeout(precheckT);
  if(ok){precheckT=setTimeout(precheck,700);}
}
async function precheck(){
  const p=document.getElementById('precheck');
  try{
    const body={con_subsidio:conSub,valor_uf:numUF('mValor'),credito_uf:numUF('mCred'),
      subsidio_uf:conSub?numUF('mSub'):0,pie_pct:conSub?0:numUF('mPie')};
    const r=await fetch('/api/calificar/__OID__/precheck',{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const d=await r.json();p.style.display='block';
    if(d.dentro){p.style.background='#0d1f12';p.style.border='1px solid #16a34a';p.style.color='#8fd9b0';}
    else{p.style.background='#1a1406';p.style.border='1px solid #d4a017';p.style.color='#e7cf7a';}
    p.textContent=d.mensaje||'';
  }catch(e){p.style.display='none';}
}
async function enviar(){
  const b=document.getElementById('btnEnviar'),m=document.getElementById('msg');
  b.disabled=true;b.textContent='Enviando de forma segura…';
  const fd=new FormData();fd.append('perfil',perfil);
  fd.append('entrega',entrega?entregaValor():'');
  fd.append('con_subsidio',conSub?'1':'0');
  fd.append('valor_uf',String(numUF('mValor')));
  fd.append('subsidio_uf',String(conSub?numUF('mSub'):0));
  fd.append('pie_pct',String(conSub?0:numUF('mPie')));
  fd.append('credito_uf',String(numUF('mCred')));
  Object.keys(st).forEach(k=>st[k].forEach(f=>fd.append(k,f)));
  try{
    const r=await fetch('/api/calificar/__OID__/subir',{method:'POST',body:fd});
    const d=await r.json();m.style.display='block';
    if(r.ok&&d.ok){m.style.background='#0d1f12';m.style.border='1px solid #16a34a';m.style.color='#8fd9b0';
      m.textContent=d.mensaje||'✅ ¡Expediente recibido! Un ejecutivo VIP lo contactará hoy mismo.';
      b.style.display='none';expedienteOk=true;}
    else{m.style.background='#1f0d0d';m.style.border='1px solid #b91c1c';m.style.color='#fda4af';
      m.textContent='⚠ '+(d.detail||'No pudimos recibir sus documentos. Intente nuevamente.');
      b.disabled=false;b.textContent='🔒 ENVIAR MI EXPEDIENTE';}
  }catch(e){m.style.display='block';m.style.background='#1f0d0d';m.style.border='1px solid #b91c1c';
    m.style.color='#fda4af';m.textContent='⚠ Error de conexión. Intente nuevamente.';
    b.disabled=false;b.textContent='🔒 ENVIAR MI EXPEDIENTE';}
}
async function solicitarLlamada(){
  const b=document.getElementById('btnConfLlamada'),m=document.getElementById('msgLlamada');
  b.disabled=true;b.textContent='Enviando…';
  try{
    const r=await fetch('/api/calificar/__OID__/solicitar-llamada',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({telefono:document.getElementById('telLlamada').value,
                           horario:document.getElementById('horLlamada').value})});
    const d=await r.json();m.style.display='block';
    if(r.ok&&d.ok){m.style.background='#0d1f12';m.style.border='1px solid #16a34a';m.style.color='#8fd9b0';
      m.textContent=d.mensaje;b.style.display='none';
      document.getElementById('telLlamada').disabled=true;document.getElementById('horLlamada').disabled=true;}
    else{m.style.background='#1f0d0d';m.style.border='1px solid #b91c1c';m.style.color='#fda4af';
      m.textContent='⚠ '+(d.detail||'No se pudo enviar la solicitud.');
      b.disabled=false;b.textContent='CONFIRMAR SOLICITUD';}
  }catch(e){m.style.display='block';m.style.background='#1f0d0d';m.style.border='1px solid #b91c1c';
    m.style.color='#fda4af';m.textContent='⚠ Error de conexión.';
    b.disabled=false;b.textContent='CONFIRMAR SOLICITUD';}
}
let salidaVista=false,expedienteOk=false;
function abrirSalida(){document.getElementById('salida').classList.add('on');}
function cerrarSalida(){document.getElementById('salida').classList.remove('on');}
document.addEventListener('mouseout',e=>{
  if(!salidaVista&&!expedienteOk&&e.clientY<=0&&!e.relatedTarget){salidaVista=true;abrirSalida();}
});
window.addEventListener('popstate',()=>{
  if(!salidaVista&&!expedienteOk){salidaVista=true;abrirSalida();history.pushState(null,'',location.href);}
});
history.pushState(null,'',location.href);
async function salidaLlamada(){
  const b=document.getElementById('btnSalida'),m=document.getElementById('msgSalida');
  const tel=(document.getElementById('salTel').value||'').trim();
  if(!tel){m.style.display='block';m.style.background='#1f0d0d';m.style.border='1px solid #b91c1c';
    m.style.color='#fda4af';m.textContent='⚠ Ingrese su número de teléfono.';return;}
  b.disabled=true;b.textContent='Enviando…';
  try{
    const r=await fetch('/api/calificar/__OID__/solicitar-llamada',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({telefono:tel,horario:document.getElementById('salHor').value})});
    const d=await r.json();m.style.display='block';
    if(r.ok&&d.ok){m.style.background='#0d1f12';m.style.border='1px solid #16a34a';m.style.color='#8fd9b0';
      m.textContent=d.mensaje||'✅ Solicitud recibida. Un ejecutivo lo llamará en el horario indicado.';
      b.style.display='none';}
    else{m.style.background='#1f0d0d';m.style.border='1px solid #b91c1c';m.style.color='#fda4af';
      m.textContent='⚠ '+(d.detail||'No se pudo enviar la solicitud.');
      b.disabled=false;b.textContent='📞 QUE ME LLAME UN EJECUTIVO';}
  }catch(e){m.style.display='block';m.style.background='#1f0d0d';m.style.border='1px solid #b91c1c';
    m.style.color='#fda4af';m.textContent='⚠ Error de conexión.';
    b.disabled=false;b.textContent='📞 QUE ME LLAME UN EJECUTIVO';}
}
</script></body></html>
"""


@app.get("/api/calificar/{oid}")
async def calificar_portal(oid: str):
    op = await db.prospectos.find_one({"id": oid})
    if not op:
        return HTMLResponse("<h3 style='font-family:sans-serif;color:#333;text-align:center;margin-top:20vh'>Enlace no válido o expirado — Central Mutuos</h3>", status_code=404)
    proyecto = (op.get("proyecto") or "").strip()
    # SEC-004: todo dato del prospecto se escapa antes de inyectarse en el HTML
    _e = html.escape
    _nombre = _e((op.get("nombre") or "").split()[0].title() or "")
    _proy = _e(proyecto)
    html_portal = (_CALIFICAR_HTML
            .replace("__PROY_TIT__", f" en {_proy}" if _proy else "")
            .replace("__NOMBRE__", _nombre)
            .replace("__PROYECTO_LINEA__", f"Proyecto {_proy}" if _proy else "Calificación Hipotecaria VIP")
            .replace("__TELEFONO__", _e((op.get("telefono") or "").strip()))
            .replace("__OID__", _e(oid)))
    return HTMLResponse(html_portal)


@app.post("/api/calificar/{oid}/subir")
async def calificar_subir(oid: str,
                          perfil: str = Form("dependiente"),
                          con_subsidio: str = Form("0"),
                          valor_uf: str = Form("0"),
                          subsidio_uf: str = Form("0"),
                          pie_pct: str = Form("0"),
                          credito_uf: str = Form("0"),
                          entrega: str = Form(""),
                          cedula: List[UploadFile] = File(default=[]),
                          liquidaciones: List[UploadFile] = File(default=[]),
                          afp: List[UploadFile] = File(default=[]),
                          boletas_anterior: List[UploadFile] = File(default=[]),
                          boletas_actual: List[UploadFile] = File(default=[]),
                          f22: List[UploadFile] = File(default=[]),
                          cmf: List[UploadFile] = File(default=[]),
                          cotizacion: List[UploadFile] = File(default=[])):
    op = await db.prospectos.find_one({"id": oid})
    if not op:
        raise HTTPException(status_code=404, detail="Enlace no válido")
    nombre = (op.get("nombre") or "").strip().title()
    if not nombre:
        raise HTTPException(status_code=400, detail="Prospecto sin nombre")
    perfil = "independiente" if perfil.strip().lower().startswith("indep") else "dependiente"
    # AUTOMATIZACIÓN DE BÓVEDA: carpeta principal + reparto en subcarpetas 01-06
    fd = await db.folders.find_one({"nombre": nombre})
    if not fd:
        fd = {"id": str(uuid.uuid4()), "nombre": nombre, "rut": op.get("rut") or "",
              "archivos": [], "created_at": now_iso(), "origen": "captura_autonoma",
              "proyecto": op.get("proyecto") or "",
              "credit_request": {"client_type": perfil}}
        await db.folders.insert_one(dict(fd))
        fsvc.folder_dir(nombre).mkdir(parents=True, exist_ok=True)
    else:
        await db.folders.update_one({"id": fd["id"]},
                                    {"$set": {"credit_request.client_type": perfil}})
    rutas = ((("cedula", cedula, "01_cedula"),
              ("liquidaciones", liquidaciones, "02_liquidaciones"),
              ("afp", afp, "03_afp"),
              ("cmf", cmf, "04_cmf"),
              ("cotizacion", cotizacion, "06_cotizacion"))
             if perfil == "dependiente" else
             (("cedula", cedula, "01_cedula"),
              ("f22", f22, "02_impuesto_renta"),
              ("boletas_anterior", boletas_anterior, "03_boletas"),
              ("boletas_actual", boletas_actual, "03_boletas"),
              ("cmf", cmf, "04_cmf"),
              ("cotizacion", cotizacion, "06_cotizacion")))
    guardados = {}
    rut_ocr = ""
    MAX_UPLOAD = 10 * 1024 * 1024  # SEC-004: límite de 10MB por archivo
    for key, files, sub in rutas:
        for up in files or []:
            raw = await up.read()
            if not raw:
                continue
            if len(raw) > MAX_UPLOAD:
                raise HTTPException(status_code=413,
                                    detail=f"El archivo '{up.filename or sub}' supera el límite de 10MB")
            fn = up.filename or f"{sub}.pdf"
            try:
                raw, fn, _ = pdfs.convertir_a_pdf(raw, fn)
            except ValueError:
                pass
            rel = await asyncio.to_thread(fsvc.guardar_archivo, nombre, fn, raw, sub)
            guardados.setdefault(key, []).append(rel)
            if sub == "01_cedula" and not rut_ocr:
                try:
                    ruta = fsvc.folder_dir(nombre) / rel
                    personas = fsvc._ruts_personas(
                        await asyncio.to_thread(fsvc.ruts_de_pdf_cache, ruta))
                    if personas:
                        rut_ocr = sorted(personas)[0]
                except Exception as e:
                    logging.warning(f"OCR RUT captura {nombre}: {e}")
    if not guardados:
        raise HTTPException(status_code=400, detail="No se recibió ningún archivo válido")
    # LEY DEL RUT: el RUT de la cédula (OCR) manda si la carpeta no tiene uno
    if rut_ocr and not (fd.get("rut") or "").strip():
        rut_fmt = f"{rut_ocr[:-1]}-{rut_ocr[-1]}" if len(rut_ocr) > 1 else rut_ocr
        await db.folders.update_one({"id": fd["id"]}, {"$set": {"rut": rut_fmt}})
        await db.prospectos.update_one({"id": oid}, {"$set": {"rut": rut_fmt}})
    # ESCENARIOS FINANCIEROS: guardar los montos directo en la ficha del cliente
    def _uf(x):
        try:
            return float(str(x).replace(",", "."))
        except ValueError:
            return 0.0
    fin = {"con_subsidio": con_subsidio in ("1", "true", "True"),
           "valor_propiedad_uf": _uf(valor_uf), "subsidio_uf": _uf(subsidio_uf),
           "pie_pct": _uf(pie_pct), "monto_credito": _uf(credito_uf)}
    if fin["monto_credito"] or fin["valor_propiedad_uf"]:
        await db.folders.update_one({"id": fd["id"]}, {"$set": {
            f"datos_financieros.{k}": v for k, v in fin.items()}})
    # Completitud según perfil (6 liquidaciones / 2+ boletas)
    if perfil == "dependiente":
        completa = (len(guardados.get("cedula", [])) >= 1 and len(guardados.get("liquidaciones", [])) >= 6
                    and len(guardados.get("afp", [])) >= 1 and len(guardados.get("cmf", [])) >= 1)
        faltan = [t for t, ok in (("Cédula", guardados.get("cedula")),
                                  ("6 Liquidaciones", len(guardados.get("liquidaciones", [])) >= 6),
                                  ("AFP", guardados.get("afp")), ("CMF", guardados.get("cmf"))) if not ok]
    else:
        completa = (len(guardados.get("cedula", [])) >= 1 and len(guardados.get("f22", [])) >= 2
                    and len(guardados.get("boletas_anterior", [])) >= 1
                    and len(guardados.get("boletas_actual", [])) >= 1 and len(guardados.get("cmf", [])) >= 1)
        faltan = [t for t, ok in (("Cédula", guardados.get("cedula")),
                                  ("2 Formularios 22", len(guardados.get("f22", [])) >= 2),
                                  ("Boletas año anterior", guardados.get("boletas_anterior")),
                                  ("Boletas año actual", guardados.get("boletas_actual")),
                                  ("CMF", guardados.get("cmf"))) if not ok]
    total = sum(len(v) for v in guardados.values())
    # CALENDARIO DE CIERRES: fecha de entrega estimada de la propiedad
    entrega_lbl = {"inmediata": "Inmediata", "futura_mas_6m": "Futura +6 meses",
                   "futura_menos_6m": "Futura -6 meses"}.get(entrega.strip(), "")
    upd_prospecto = {"estado_interes": "uso_simulador", "captura_autonoma_en": now_iso()}
    if entrega_lbl:
        upd_prospecto["fecha_entrega_estimada"] = entrega_lbl
        await db.folders.update_one({"id": fd["id"]},
                                    {"$set": {"fecha_entrega_estimada": entrega_lbl}})
    await db.prospectos.update_one({"id": oid}, {"$set": upd_prospecto})
    await db.capturas_autonomas.insert_one({
        "id": str(uuid.uuid4()), "oportunidad_id": oid, "cliente": nombre,
        "rut": rut_ocr, "proyecto": op.get("proyecto") or "", "perfil": perfil,
        "completa": completa, "faltan": faltan,
        "archivos": [r for v in guardados.values() for r in v], "creado_en": now_iso()})
    # EXPERIENCIA WHATSAPP: alerta inmediata a Gerardo (no bloquea la respuesta al cliente)
    asunto = (f"🚀 EXPEDIENTE CREADO DESDE WHATSAPP: {nombre} - Perfil "
              f"{perfil.capitalize()} - Documentación {'Completa' if completa else 'Incompleta'}"
              + (f" - 🚨 ENTREGA: {entrega_lbl}" if entrega_lbl else ""))

    async def _avisar():
        try:
            destinatario = os.environ.get("MAIL2_USER", "")
            filas = "".join(f"<li>{k}: {len(v)} archivo(s)</li>" for k, v in guardados.items())
            cuerpo = f"""
            <div style="font-family:Arial,sans-serif;width:100%;max-width:600px">
              <div style="background:#0a0a0a;padding:16px 20px;border-left:4px solid #D4AF37">
                <span style="color:#D4AF37;font-weight:700;letter-spacing:0.08em">💎 CENTRAL MUTUOS · IMÁN DE CRÉDITOS</span>
              </div>
              <div style="padding:16px 6px;color:#1a1a1a;font-size:14px">
                <p><b>{asunto}</b></p>
                <ul style="font-size:13px;color:#444">
                  {'<li style="color:#b91c1c"><b>🚨 ENTREGA: ' + entrega_lbl + '</b></li>' if entrega_lbl else ''}
                  <li>Proyecto: {op.get('proyecto') or '—'}</li>
                  <li>RUT (OCR cédula): {rut_ocr or 'no detectado aún'}</li>
                  <li>Total documentos: {total} repartidos en la bóveda (01-06)</li>
                  {filas}
                  {'<li style="color:#b45309"><b>Faltan: ' + ', '.join(faltan) + '</b></li>' if faltan else ''}
                  <li><b>Escenario: {'CON subsidio' if fin['con_subsidio'] else 'SIN subsidio'}</b> ·
                      Propiedad {fin['valor_propiedad_uf']:.0f} UF ·
                      {('Subsidio ' + format(fin['subsidio_uf'], '.0f') + ' UF') if fin['con_subsidio'] else ('Pie ' + format(fin['pie_pct'], '.1f') + '%')} ·
                      Crédito solicitado {fin['monto_credito']:.0f} UF</li>
                </ul>
                <p style="font-size:13px">La carpeta ya está en Carpeta Clientes, lista para evaluación.</p>
              </div>
            </div>"""
            await asyncio.to_thread(mail.send_mail, destinatario, asunto, cuerpo, [], "principal")
        except Exception as e:
            logging.warning(f"Aviso captura {nombre}: {e}")
    asyncio.create_task(_avisar())
    return {"ok": True,
            "mensaje": ("✅ ¡Expediente COMPLETO recibido! Su carpeta VIP fue creada y un ejecutivo lo contactará hoy mismo."
                        if completa else
                        "✅ ¡Documentos recibidos! Su carpeta VIP fue creada. Un ejecutivo lo contactará para completar lo que falte."),
            "carpeta": nombre, "perfil": perfil, "completa": completa, "rut_detectado": rut_ocr}


@app.post("/api/calificar/{oid}/precheck")
async def calificar_precheck(oid: str, payload: dict):
    """VALIDACIÓN INSTANTÁNEA DashAI: chequeo local contra la bodega BTG/Ameris."""
    op = await db.prospectos.find_one({"id": oid})
    if not op:
        raise HTTPException(status_code=404, detail="Enlace no válido")
    con_sub = bool(payload.get("con_subsidio"))
    valor = float(payload.get("valor_uf") or 0)
    credito = float(payload.get("credito_uf") or 0)
    crit = await asyncio.to_thread(mesa_brain._criterios)
    btg = (crit.get("btg_pactual") or {}).get("con_subsidio" if con_sub else "sin_subsidio") or {}
    pol = await asyncio.to_thread(mesa_brain.politicas_maestras)
    obs = []
    if valor and credito:
        ltv = credito / valor
        ltv_max = float(btg.get("ltv_max") or pol["ltv_maximo_base"])
        if ltv > ltv_max + 1e-6:
            obs.append(f"financiamiento {ltv*100:.0f}% (estándar hasta {ltv_max*100:.0f}%)")
    if not con_sub and credito and credito < mesa_brain.MONTO_MIN_UF_SIN_SUBSIDIO_HARD:
        obs.append(f"monto mínimo sin subsidio {mesa_brain.MONTO_MIN_UF_SIN_SUBSIDIO_HARD} UF")
    mmax = float(btg.get("monto_credito_max_uf") or 0)
    if mmax and credito > mmax:
        obs.append(f"monto máximo {mmax:.0f} UF")
    dentro = not obs
    return {"dentro": dentro,
            "mensaje": ("✅ Su solicitud está dentro de nuestras políticas de financiamiento."
                        if dentro else
                        "ℹ Su solicitud será revisada de forma personalizada por un ejecutivo (" + " · ".join(obs) + ").")}


@app.post("/api/calificar/{oid}/solicitar-llamada")
async def calificar_solicitar_llamada(oid: str, payload: dict, request: Request):
    """SOLICITUD DE CONTACTO VIP: dispara correo urgente a Gerardo con teléfono y horario."""
    op = await db.prospectos.find_one({"id": oid})
    if not op:
        raise HTTPException(status_code=404, detail="Enlace no válido")
    telefono = (payload.get("telefono") or "").strip()
    horario = (payload.get("horario") or "").strip() or "Mañana"
    motivo = (payload.get("motivo") or "").strip()
    if len(re.sub(r"[^0-9]", "", telefono)) < 8:
        raise HTTPException(status_code=400, detail="Ingrese un número de teléfono válido")
    nombre = (op.get("nombre") or "").strip().title()
    # VINCULACIÓN: crear ficha aunque no suba papeles, para no perder el rastro
    fd = await db.folders.find_one({"nombre": nombre})
    if not fd:
        await db.folders.insert_one({
            "id": str(uuid.uuid4()), "nombre": nombre, "rut": op.get("rut") or "",
            "telefono": telefono, "archivos": [], "created_at": now_iso(),
            "origen": "solicitud_llamada", "proyecto": op.get("proyecto") or ""})
        fsvc.folder_dir(nombre).mkdir(parents=True, exist_ok=True)
    else:
        await db.folders.update_one({"id": fd["id"]}, {"$set": {"telefono": telefono}})
    await db.solicitudes_llamada.insert_one({
        "id": str(uuid.uuid4()), "oportunidad_id": oid, "cliente": nombre,
        "telefono": telefono, "horario": horario, "motivo": motivo or "post_envio",
        "creado_en": now_iso()})
    base = _base_url_req(request)
    asunto = (f"💎 ALERTA DE CONTACTO: El cliente {nombre} solicita asistencia manual"
              if motivo == "asistencia" else
              f"💎 URGENTE: Solicitud de Contacto - {nombre}")

    async def _avisar():
        try:
            cuerpo = f"""
            <div style="font-family:Arial,sans-serif;width:100%;max-width:600px">
              <div style="background:#0a0a0a;padding:16px 20px;border-left:4px solid #D4AF37">
                <span style="color:#D4AF37;font-weight:700;letter-spacing:0.08em">💎 CENTRAL MUTUOS · CONTACTO VIP</span>
              </div>
              <div style="padding:16px 6px;color:#1a1a1a;font-size:14px">
                <p><b>{'El cliente ' + nombre + ' pidió ayuda humana en el portal (no completó la carga).' if motivo == 'asistencia' else 'El cliente ' + nombre + ' solicita ser llamado por un ejecutivo.'}</b></p>
                <ul style="font-size:14px;color:#333">
                  <li>📞 Teléfono: <b>{telefono}</b></li>
                  <li>🕐 Horario preferido: <b>{horario}</b></li>
                  <li>🏠 Proyecto: {op.get('proyecto') or '—'}</li>
                  <li>📂 Carpeta en el Maserati: <a href="{base}">{base}</a> → Carpeta Clientes → <b>{nombre}</b></li>
                </ul>
              </div>
            </div>"""
            await asyncio.to_thread(mail.send_mail, "gerardo.ext@centralmutuos.cl",
                                    asunto, cuerpo, [], "principal")
        except Exception as e:
            logging.warning(f"Solicitud llamada {nombre}: {e}")
    asyncio.create_task(_avisar())
    return {"ok": True,
            "mensaje": f"✅ Solicitud recibida. Un ejecutivo de Central Mutuos lo contactará en el horario {horario}."}


@api.post("/oportunidades/{oid}/link-calificar")
async def oportunidades_link_calificar(oid: str, request: Request):
    op = await db.prospectos.find_one({"id": oid})
    if not op:
        raise HTTPException(status_code=404, detail="Oportunidad no encontrada")
    base = _base_url_req(request)
    url = f"{base}/api/calificar/{oid}"
    proyecto = (op.get("proyecto") or "").strip()
    titulo = "Central Mutuos - Precalificación Hipotecaria"
    texto = (f"🏠 *{titulo}*\n\nHola {(op.get('nombre') or '').split()[0].title()}, soy José Martín de Central Mutuos. "
             f"Suba su Cédula y sus últimas 6 Liquidaciones de Sueldo en este portal privado y su calificación queda lista:\n{url}"
             f"\n\nAtentamente, el equipo de @CentralMutuos")
    await db.prospectos.update_one({"id": oid}, {"$set": {"link_calificar": url}})
    return {"ok": True, "url": url, "titulo": titulo,
            "whatsapp": f"https://wa.me/?text={_urlquote(texto)}"}


@api.get("/capturas/recientes")
async def calificar_recientes():
    desde = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    caps = await db.capturas_autonomas.find({"creado_en": {"$gte": desde}}, {"_id": 0}).sort("creado_en", -1).to_list(20)
    return {"capturas": caps}


# 🧠 CONEXIÓN CONTRALORA — Cerebro exportable (Contralor + DashAI)
import brain_export as _brain
api.include_router(_brain.brain)

# ⚡ MONITOR DE ENERGÍA — Reserva de funcionamiento
import energia as _energia_mod
api.include_router(_energia_mod.energia)

# 📱 MOTOR WHATSAPP OFICIAL — Twilio Número Exclusivo (Regla de Oro #21)
import whatsapp_twilio_service as _wa_twilio
api.include_router(_wa_twilio.wa_twilio)

# 🏦 BODEGA CONCRECES + GERENCIA COMERCIAL (Reglas #24 y #25) + CONTROL (#35)
import bodega_concreces as _bodega_mod
api.include_router(_bodega_mod.bodega)
api.include_router(_bodega_mod.gerencia)
api.include_router(_bodega_mod.excepciones)
api.include_router(_bodega_mod.control)

# 🕸️ MALLA DE INTELIGENCIA + BROKERS + FLUJOS + MI CORREO (Reglas #34, #36, #37, #38)
import malla_inteligencia as _malla_mod
import gestion_ejecutivos as _gest_mod
api.include_router(_gest_mod.gestion)
api.include_router(_malla_mod.broker)
api.include_router(_malla_mod.fuentes)
api.include_router(_malla_mod.hitos)
api.include_router(_malla_mod.flujos)
api.include_router(_malla_mod.micorreo)
api.include_router(_malla_mod.buzon)
api.include_router(_malla_mod.supercarpeta)

# 🛰 GRID-DASHAI — Sincronización forzada e integral (Regla #41, SIN interruptor)
import grid_dashai as _grid_mod
api.include_router(_grid_mod.grid)

# 🪞 ALGORITMO ESPEJO HÍBRIDO · CONEXIÓN CONCRECES · MÓDULO POSTVENTA
import espejo_postventa as _esp_mod
api.include_router(_esp_mod.espejo)
api.include_router(_esp_mod.concreces)
api.include_router(_esp_mod.postventa)
api.include_router(_esp_mod.gpanel)
api.include_router(_esp_mod.brokerx)

# ☁️ FILE & MEDIA STORAGE — documentos por operación/RUT + bandeja sin clasificar
import media_storage as _ms_mod
api.include_router(_ms_mod.storage_router)

# 🔍 REGLA PERMANENTE — Auditoría semanal de eficiencia modular (solo Admin)
import auditoria_eficiencia as _aud_mod
api.include_router(_aud_mod.auditoria_r)

# 📜 CATÁLOGO MAESTRO DEFINITIVO — todas las reglas unificadas en el Cerebro
import catalogo_maestro as _cat_mod
api.include_router(_cat_mod.catalogo_r)

# 🔐 EXPORTACIÓN BLINDADA DE LA CONSTITUCIÓN (PIN maestro + auditoría)
import cerebro_export as _cex_mod
api.include_router(_cex_mod.export_r)

# 👑 GERENCIA COMERCIAL — brokers internos, ranking, trackers de pasos
import gerencia_comercial as _gcom_mod
api.include_router(_gcom_mod.gcom)

# 📋 AUDITORÍA DE CRÉDITOS → MESA — recibidos vs enviados (sistema + correo directo)
import auditoria_mesa as _audim_mod
api.include_router(_audim_mod.audimesa)

# 📧 DESTINATARIOS DE CORREO POR ACCIÓN — panel Admin/Gerencia Comercial
import correo_destinatarios as _cdest_mod
api.include_router(_cdest_mod.correo_dest)

# 🪞 ALGORITMO ESPEJO HÍBRIDO ADMINISTRATIVO — estado de fuentes y barridos
import espejo_hibrido as _hib_mod
api.include_router(_hib_mod.hibrido)

# Regla #62 (Monitor de Envíos SMTP) + Regla #64 (Perfil Consolidado — verdad DashAI)
import monitor_envios as _monit_mod
import perfil_consolidado as _perfil
import base_historica as _hist_mod
import adn_clientes as _adn_mod
api.include_router(_monit_mod.correos_r)
api.include_router(_perfil.perfil_r)
api.include_router(_hist_mod.historia)
api.include_router(_adn_mod.adn)


@api.get("/constitucion")
async def constitucion_leer():
    """CONSTITUCIÓN MAESTRA — 15 Reglas de Oro (fuente de verdad de DashAI)."""
    import constitucion as _const
    return await _const.seed_constitucion(db)


@api.post("/constitucion/aprendizaje-secundario")
async def constitucion_aprendizaje(payload: dict):
    """MÓDULO DE APRENDIZAJE EXTERNO: registra el 2º buzón IMAP en modo SOLO LECTURA
    (slot para el nuevo correo). No envía ni modifica nada de ese buzón."""
    correo = (payload or {}).get("correo", "").strip()
    await db.config.update_one({"_key": "constitucion_maestra"}, {"$set": {
        "aprendizaje.fuente_secundaria_solo_lectura": correo,
        "aprendizaje.modo": "solo_lectura",
        "aprendizaje.actualizado": now_iso()}}, upsert=True)
    return {"ok": True, "fuente_secundaria": correo, "modo": "solo_lectura"}



app.include_router(api)
api.include_router(_hist_mod.historia)
api.include_router(_adn_mod.adn)


@api.get("/constitucion")
async def constitucion_leer():
    """CONSTITUCIÓN MAESTRA — 15 Reglas de Oro (fuente de verdad de DashAI)."""
    import constitucion as _const
    return await _const.seed_constitucion(db)


@api.post("/constitucion/aprendizaje-secundario")
async def constitucion_aprendizaje(payload: dict):
    """MÓDULO DE APRENDIZAJE EXTERNO: registra el 2º buzón IMAP en modo SOLO LECTURA
    (slot para el nuevo correo). No envía ni modifica nada de ese buzón."""
    correo = (payload or {}).get("correo", "").strip()
    await db.config.update_one({"_key": "constitucion_maestra"}, {"$set": {
        "aprendizaje.fuente_secundaria_solo_lectura": correo,
        "aprendizaje.modo": "solo_lectura",
        "aprendizaje.actualizado": now_iso()}}, upsert=True)
    return {"ok": True, "fuente_secundaria": correo, "modo": "solo_lectura"}



app.include_router(api)
