"""AUDITORÍA SEMANAL DE EFICIENCIA MODULAR — REGLA PERMANENTE de arquitectura base.
Se ejecuta automáticamente cada lunes al primer ingreso del Admin (sin intervención manual).
Verifica eficiencia de File & Media Storage y Claude AI. Solo el Admin puede desactivarla.
"""
import re
import uuid
import logging
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from database import db

auditoria_r = APIRouter(prefix="/auditoria-eficiencia")
_BASE = Path(__file__).parent

NORMATIVA_CLAVE = "AUDITORÍA EFICIENCIA"
NORMATIVA_TEXTO = ("NORMATIVA FIJA — AUDITORÍA SEMANAL DE EFICIENCIA: cada lunes, al primer ingreso del "
                   "Admin, el sistema audita automáticamente la eficiencia de File & Media Storage (sin cargas "
                   "anticipadas, vistas bajo demanda, indicadores desde base local) y de Claude AI (solo ante "
                   "correo nuevo, resumen diario una vez por jornada, informes solo a pedido, contexto mínimo, "
                   "validación previa en base de datos). Registro con marca de tiempo; alertas solo al Admin. "
                   "Regla de arquitectura base: solo el Admin puede desactivarla.")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _semana_iso():
    hoy = datetime.now(timezone.utc)
    y, w, _ = hoy.isocalendar()
    return f"{y}-W{w:02d}"


def _src(nombre):
    try:
        return (_BASE / nombre).read_text(encoding="utf-8")
    except Exception:
        return ""


def _chk(clave, categoria, ok, detalle, corregido=False):
    return {"clave": clave, "categoria": categoria, "ok": bool(ok),
            "detalle": detalle, "corregido": bool(corregido)}


async def ejecutar_auditoria(trigger="login_admin"):
    """Ejecuta los controles de eficiencia y registra el resultado con marca de tiempo."""
    checks = []
    ms_src = _src("media_storage.py")
    esp_src = _src("espejo_postventa.py")
    ia_src = _src("espejo_ia.py")
    srv_src = _src("server.py")

    # ═══ FILE & MEDIA STORAGE ═══
    m = await db.config.find_one({"_key": "storage_metrics"}) or {}
    gets, demanda = int(m.get("gets") or 0), int(m.get("gets_demanda") or 0)
    corregido = False
    if not m:
        await db.config.update_one({"_key": "storage_metrics"},
                                   {"$setOnInsert": {"gets": 0, "gets_demanda": 0, "puts": 0}}, upsert=True)
        corregido = True
    checks.append(_chk("storage_sin_cargas_anticipadas", "storage", gets <= demanda,
                       f"Lecturas al storage: {gets} · bajo demanda explícita (visor): {demanda}. "
                       + ("Sin lecturas anticipadas en segundo plano." if gets <= demanda
                          else f"{gets - demanda} lectura(s) fuera de demanda del usuario."), corregido))
    checks.append(_chk("storage_vistas_bajo_demanda", "storage",
                       "storage_ver" in ms_src and 'Content-Disposition' in ms_src,
                       "La vista previa solo se sirve por GET /storage/ver/{id} cuando el usuario la solicita."))
    ok_db_local = 'db.storage_docs.find' in ms_src and '"storage_path": 0' in ms_src
    checks.append(_chk("storage_indicadores_desde_db", "storage", ok_db_local,
                       "Los listados e indicadores de documentos se calculan desde db.storage_docs "
                       "(base local), sin tocar el storage remoto."))
    lista_fn = ms_src.split("async def storage_docs_list")[-1].split("async def")[0] if "storage_docs_list" in ms_src else ""
    checks.append(_chk("storage_sin_llamadas_al_navegar", "storage",
                       "_get(" not in lista_fn and "_put(" not in lista_fn,
                       "Cargar pantallas o navegar entre módulos no genera llamadas al storage: "
                       "el endpoint de listado consulta solo la base de datos."))

    # ═══ CLAUDE AI MODELS ═══
    core = esp_src.split("async def _sync_concreces_core")[-1] if "_sync_concreces_core" in esp_src else ""
    pos_dedupe, pos_ia = core.find("espejo_sync_log.find_one"), core.find("analizar_correo")
    checks.append(_chk("claude_solo_correo_nuevo", "claude",
                       0 <= pos_dedupe < pos_ia,
                       "Claude se invoca solo tras el filtro de deduplicación (espejo_sync_log): "
                       "únicamente ante correos nuevos, nunca en bucle ni en segundo plano."))
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    n_resumen_hoy = await db.system_log.count_documents({"tipo": "resumen_diario_generado", "dia": hoy})
    checks.append(_chk("claude_resumen_diario_unico", "claude", n_resumen_hoy <= 1,
                       f"Resumen ejecutivo diario generado {n_resumen_hoy} vez/veces hoy "
                       "(límite: 1 por jornada, al primer ingreso; sesiones posteriores reutilizan el del día)."))
    sin_loop = "informe_rechazos_loop" not in srv_src and "informe_rechazos_loop" not in esp_src
    checks.append(_chk("claude_informe_mensual_manual", "claude", sin_loop,
                       "El informe mensual de rechazos no tiene generación automática: solo se produce "
                       "cuando el usuario lo solicita explícitamente."))
    docs_ctx = await db.espejo_ia_log.find({}, {"ia.contexto_chars": 1}).sort("fecha", -1).to_list(50)
    max_ctx = max([int(((d.get("ia") or {}).get("contexto_chars")) or 0) for d in docs_ctx] or [0])
    checks.append(_chk("claude_contexto_minimo", "claude",
                       "[:6000]" in ia_src and max_ctx <= 6500,
                       f"Cada llamada envía solo asunto+cuerpo del correo (tope 6.000 caracteres, sin "
                       f"historial). Máximo observado: {max_ctx} caracteres."))
    pos_regex = core.find("_extraer_datos_operacion")
    checks.append(_chk("claude_validacion_db_primero", "claude",
                       0 <= pos_regex < pos_ia,
                       "Las alertas se validan primero con lógica local (extracción por patrones y base "
                       "de datos) antes de invocar a Claude."))

    fallas = [c for c in checks if not c["ok"]]
    reg = {"id": str(uuid.uuid4()), "semana": _semana_iso(), "fecha": _now(), "trigger": trigger,
           "resultado": "aprobada" if not fallas else "con_hallazgos",
           "checks": checks, "fallas": len(fallas),
           "correcciones_automaticas": sum(1 for c in checks if c.get("corregido"))}
    await db.auditorias_eficiencia.insert_one(dict(reg))
    if fallas:
        await db.alertas.insert_one({
            "id": str(uuid.uuid4()), "tipo": "auditoria_eficiencia", "leida": False,
            "creado": _now(), "destinatarios": ["admin"],
            "titulo": f"⚠️ Auditoría de eficiencia: {len(fallas)} hallazgo(s)",
            "mensaje": " · ".join(f"{c['clave']}: {c['detalle']}" for c in fallas)[:800]})
    logging.info(f"🔍 Auditoría eficiencia {reg['semana']}: {reg['resultado']} ({len(fallas)} fallas)")
    return reg


async def disparar_si_corresponde(rol):
    """Trigger automático: lunes + primer ingreso del Admin + sin auditoría esta semana."""
    if rol not in ("admin", "maestro"):
        return
    cfg = await db.config.find_one({"_key": "auditoria_eficiencia"}) or {}
    if cfg.get("activa") is False:
        return
    if datetime.now(timezone.utc).isocalendar()[2] != 1:  # 1 = lunes
        return
    if await db.auditorias_eficiencia.find_one({"semana": _semana_iso()}):
        return
    try:
        await ejecutar_auditoria("login_admin_lunes")
    except Exception as e:
        logging.warning(f"auditoría eficiencia auto: {e}")


async def seed_normativa():
    """Registra la regla como normativa inamovible de arquitectura base (idempotente)."""
    if not await db.dashai_eventos.find_one({"motivo": "normativa", "norma_clave": NORMATIVA_CLAVE}):
        await db.dashai_eventos.insert_one({
            "id": str(uuid.uuid4()), "motivo": "normativa", "norma_clave": NORMATIVA_CLAVE,
            "fecha": _now(), "patron": NORMATIVA_TEXTO, "inamovible": True})
        logging.info("📜 Normativa AUDITORÍA EFICIENCIA registrada")


def _solo_admin(request):
    if (getattr(request.state, "user", {}) or {}).get("rol") not in ("admin", "maestro"):
        raise HTTPException(status_code=403, detail=(
            "La auditoría de eficiencia es parte de la arquitectura base: solo el Administrador "
            "puede consultarla o modificarla."))


@auditoria_r.get("")
async def auditoria_historial(request: Request):
    _solo_admin(request)
    cfg = await db.config.find_one({"_key": "auditoria_eficiencia"}) or {}
    regs = await db.auditorias_eficiencia.find({}, {"_id": 0}).sort("fecha", -1).to_list(52)
    return {"activa": cfg.get("activa") is not False, "historial": regs, "total": len(regs),
            "regla": NORMATIVA_TEXTO}


@auditoria_r.post("/ejecutar")
async def auditoria_ejecutar_manual(request: Request):
    _solo_admin(request)
    reg = await ejecutar_auditoria("manual_admin")
    reg.pop("_id", None)
    return {"ok": True, "auditoria": reg}


@auditoria_r.post("/config")
async def auditoria_config(payload: dict, request: Request):
    _solo_admin(request)
    activa = bool((payload or {}).get("activa", True))
    await db.config.update_one({"_key": "auditoria_eficiencia"}, {"$set": {
        "activa": activa, "modificado": _now(),
        "por": (getattr(request.state, "user", {}) or {}).get("sub") or ""}}, upsert=True)
    return {"ok": True, "activa": activa}
