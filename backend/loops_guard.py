"""Inventario y freno cooperativo de loops de fondo.

Todo arranca ENCENDIDO. Solo el Administrador puede pausar loops marcados
como pausables (redundantes / IMAP pesado). Mesa verdad, ingesta, autocorreo,
preview, autorreparación y Gmail watch NO se pausan.
"""
import asyncio
import logging
import uuid
from contextlib import suppress
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from criterios_data import now_iso


def _db():
    from database import db
    return db

loops_r = APIRouter(prefix="/loops")
KEY = "loops_guard"

# ── Catálogo (nombres = los de _task_blindada). pausable=False ⇒ no hay botón. ──
CATALOGO = {
    "ingesta_carpetas": {
        "titulo": "Ingesta de carpetas", "imap": True, "pausable": False, "riesgo": "crítico",
        "solapa": [], "motivo": "Crea carpetas 24/7 (Regla 67). No se pausa."},
    "mesa": {
        "titulo": "Autocorreo de Mesa", "imap": True, "pausable": False, "riesgo": "crítico",
        "solapa": ["mesa_verdad"],
        "motivo": "Reenvío constitucional de veredictos. Solapa con mesa_verdad; no se pausa."},
    "mesa_verdad": {
        "titulo": "Mesa verdad (aprobaciones@)", "imap": True, "pausable": False, "riesgo": "crítico",
        "solapa": ["mesa"], "motivo": "Fuente de verdad de Mesa. No se pausa."},
    "autorreparacion": {
        "titulo": "Autorreparación", "imap": False, "pausable": False, "riesgo": "crítico",
        "solapa": [], "motivo": "Vigilancia Nivel 1. No se pausa."},
    "gmail_watch": {
        "titulo": "Gmail watch (Pub/Sub)", "imap": False, "pausable": False, "riesgo": "crítico",
        "solapa": ["ingesta_carpetas"], "motivo": "Renueva el push de Gmail. No se pausa."},
    "resumen_diario_8am": {
        "titulo": "Resumen diario 8:00", "imap": False, "pausable": False, "riesgo": "alto",
        "solapa": [], "motivo": "Único correo diario constitucional."},
    "notif_pace": {
        "titulo": "Goteo de notificaciones", "imap": False, "pausable": False, "riesgo": "alto",
        "solapa": [], "motivo": "Cola de correos al cliente (preview)."},
    "reparos_estudio": {
        "titulo": "Reparos estudio de título", "imap": True, "pausable": False, "riesgo": "alto",
        "solapa": [], "motivo": "Hilos de estudio de título."},
    "aprendizaje_ia": {
        "titulo": "Aprendizaje IA", "imap": False, "pausable": False, "riesgo": "medio",
        "solapa": ["espejo_aprendizaje"], "motivo": "Ciclo diario de aprendizaje comercial."},
    "victoria_mail": {
        "titulo": "Correo módulo Victoria", "imap": True, "pausable": False, "riesgo": "alto",
        "solapa": [], "motivo": "Buzón del módulo Victoria."},
    "espejo_aprendizaje": {
        "titulo": "Espejo aprendizaje", "imap": False, "pausable": False, "riesgo": "medio",
        "solapa": ["aprendizaje_ia"], "motivo": "Reentrena el modelo de 3 meses."},
    "gerencia_audit": {
        "titulo": "Auditoría gerencia", "imap": False, "pausable": False, "riesgo": "medio",
        "solapa": [], "motivo": "Auditoría de cartera cada 6 h."},
    "malla_inteligencia": {
        "titulo": "Malla de inteligencia", "imap": True, "pausable": False, "riesgo": "alto",
        "solapa": ["lector_ejecutivos"], "motivo": "Scan de aliados IMAP."},
    "lector_ejecutivos": {
        "titulo": "Lector IMAP ejecutivos", "imap": True, "pausable": True, "riesgo": "medio",
        "solapa": ["malla_inteligencia", "gestion_ejecutivos"],
        "motivo": "N conexiones IMAP a buzones de ejecutivos. Candidato: pausar si OVERQUOTA."},
    "cuenta_barrido": {
        "titulo": "Barrido de cuenta", "imap": True, "pausable": True, "riesgo": "medio",
        "solapa": ["ingesta_carpetas"],
        "motivo": "Barrido extra + auto-envío. Candidato si el buzón ya entra por push."},
    "reset_firmas": {
        "titulo": "Reset firmas (una vez)", "imap": False, "pausable": False, "riesgo": "bajo",
        "solapa": [], "motivo": "Migración puntual."},
    "avance_snapshot": {
        "titulo": "Snapshot de avance", "imap": False, "pausable": False, "riesgo": "bajo",
        "solapa": ["adn_360"], "motivo": "Foto horaria hacia ADN."},
    "reenvio_co_rs": {
        "titulo": "Reenvío CO/RS", "imap": False, "pausable": False, "riesgo": "medio",
        "solapa": [], "motivo": "Reenvío de comprobantes."},
    "resumen_gerencia": {
        "titulo": "Resumen gerencia", "imap": False, "pausable": False, "riesgo": "medio",
        "solapa": ["resumen_diario_8am"], "motivo": "Resumen semanal de flota."},
    "resumen_hilo_ia": {
        "titulo": "Resumen IA por hilo", "imap": False, "pausable": False, "riesgo": "medio",
        "solapa": [], "motivo": "LLM por carpeta cada 15 min."},
    "espejo_capa_a": {
        "titulo": "Espejo contralor (capa A)", "imap": True, "pausable": False, "riesgo": "alto",
        "solapa": ["espejo_hibrido"], "motivo": "IMAP contralor + Concreces."},
    "espejo_hibrido": {
        "titulo": "Espejo híbrido (3 IMAP)", "imap": True, "pausable": True, "riesgo": "medio",
        "solapa": ["espejo_capa_a", "victoria_mail"],
        "motivo": "Victoria/Daniela/Javier cada 5 min. Candidato: pausar si hay OVERQUOTA."},
    "gestion_ejecutivos": {
        "titulo": "Cosecha ejecutivos", "imap": True, "pausable": False, "riesgo": "medio",
        "solapa": ["lector_ejecutivos"], "motivo": "Cabeceras IMAP de ejecutivos."},
    "cierre_fallidos": {
        "titulo": "Cierre SMTP fallidos", "imap": False, "pausable": False, "riesgo": "bajo",
        "solapa": [], "motivo": "Cierra envíos fallidos >24 h."},
    "buzon_aprendizaje": {
        "titulo": "Buzón aprendizaje (solo lectura)", "imap": True, "pausable": True, "riesgo": "bajo",
        "solapa": ["ingesta_carpetas"], "motivo": "IMAP RO del 2º buzón. Candidato a pausa."},
    "grid_dashai_forzado": {
        "titulo": "Grid DashAI", "imap": False, "pausable": False, "riesgo": "medio",
        "solapa": ["bunker_gridfs"], "motivo": "MD5 disco↔nube."},
    "uf": {
        "titulo": "Valor UF", "imap": False, "pausable": False, "riesgo": "bajo",
        "solapa": [], "motivo": "Actualiza UF desde SII."},
    "autocorreo_firmados": {
        "titulo": "Autocorreo eCert firmados", "imap": True, "pausable": False, "riesgo": "alto",
        "solapa": [], "motivo": "Detecta firmas eCert."},
    "informes_vip_lunes": {
        "titulo": "Informes VIP lunes", "imap": False, "pausable": False, "riesgo": "bajo",
        "solapa": [], "motivo": "PDF VIP semanal."},
    "fecha_tasacion": {
        "titulo": "Fecha de tasación", "imap": True, "pausable": False, "riesgo": "medio",
        "solapa": ["actividades_terminadas"], "motivo": "Busca respuesta de Value Property."},
    "cobro_tasacion": {
        "titulo": "Cobro de tasación", "imap": True, "pausable": False, "riesgo": "medio",
        "solapa": [], "motivo": "Detecta cobros/pagos de tasación."},
    "actividades_terminadas": {
        "titulo": "Actividades terminadas", "imap": True, "pausable": False, "riesgo": "medio",
        "solapa": ["fecha_tasacion"], "motivo": "Cierra tasación/estudio por IMAP."},
    "dashai_perpetuo": {
        "titulo": "DashAI perpetuo", "imap": False, "pausable": False, "riesgo": "medio",
        "solapa": ["aprendizaje_ia"], "motivo": "Sync de aprendizaje."},
    "resumen_semanal": {
        "titulo": "Resumen semanal Martín", "imap": False, "pausable": False, "riesgo": "medio",
        "solapa": ["resumen_diario_8am"], "motivo": "Lunes 08:00."},
    "resumen_cierres": {
        "titulo": "Resumen de cierres", "imap": False, "pausable": False, "riesgo": "bajo",
        "solapa": [], "motivo": "Domingo, cierres sin respuesta."},
    "setcred_auto": {
        "titulo": "Set de crédito auto", "imap": True, "pausable": False, "riesgo": "alto",
        "solapa": [], "motivo": "evaluacionesmutuos@gmail.com."},
    "bunker_gridfs": {
        "titulo": "Búnker archivos", "imap": False, "pausable": False, "riesgo": "alto",
        "solapa": ["cloud_bunker_espejo"], "motivo": "Espejo disco→object store. Se queda."},
    "rescate_historico": {
        "titulo": "Rescate histórico IMAP", "imap": True, "pausable": True, "riesgo": "bajo",
        "solapa": ["historia_minado"],
        "motivo": "Barrido masivo cada 3 días. Candidato a pausa."},
    "dashai_dataset_2359": {
        "titulo": "Dataset DashAI 23:59", "imap": False, "pausable": False, "riesgo": "bajo",
        "solapa": [], "motivo": "CSV anonimizado diario."},
    "cloud_bunker_espejo": {
        "titulo": "Cloud búnker (2º espejo)", "imap": False, "pausable": True, "riesgo": "bajo",
        "solapa": ["bunker_gridfs"],
        "motivo": "Segundo espejo a la nube cada 5 min. Redundante con bunker_gridfs."},
    "espejo_mesa_24h": {
        "titulo": "Espejo Mesa 24 h", "imap": False, "pausable": False, "riesgo": "medio",
        "solapa": ["mesa_verdad"], "motivo": "Reentrena límites de Mesa."},
    "cosecha_perfil_64": {
        "titulo": "Cosecha perfil", "imap": False, "pausable": False, "riesgo": "bajo",
        "solapa": ["adn_360"], "motivo": "Perfil consolidado sin IMAP."},
    "historia_minado": {
        "titulo": "Minado histórico IMAP", "imap": True, "pausable": True, "riesgo": "bajo",
        "solapa": ["rescate_historico"],
        "motivo": "Barrido IMAP histórico por bloques. Candidato a pausa."},
    "adn_360": {
        "titulo": "ADN 360", "imap": False, "pausable": False, "riesgo": "medio",
        "solapa": ["cosecha_perfil_64"], "motivo": "Volcado a la bóveda ADN."},
    "auditoria_tiempo_real": {
        "titulo": "Auditoría tiempo real", "imap": True, "pausable": False, "riesgo": "medio",
        "solapa": [], "motivo": "Brokers/tasadores IMAP."},
}

RECOMENDADOS_PAUSA = (
    "cloud_bunker_espejo", "rescate_historico", "historia_minado", "espejo_hibrido",
)


def meta(nombre):
    return CATALOGO.get(nombre) or {
        "titulo": nombre, "imap": False, "pausable": False, "riesgo": "alto",
        "solapa": [], "motivo": "Loop no catalogado: se observa, no se pausa."}


def puede_pausar(nombre):
    return bool(meta(nombre).get("pausable"))


def _now():
    return datetime.now(timezone.utc).isoformat()


def _claims(request):
    return getattr(request.state, "user", None) or {}


def _exigir_admin(request):
    if _claims(request).get("rol") not in ("admin", "maestro"):
        raise HTTPException(status_code=403,
                            detail="Solo el Administrador puede pausar loops de fondo")


async def _doc():
    return await _db().config.find_one({"_key": KEY}) or {}


async def esta_pausado(nombre):
    if not puede_pausar(nombre):
        return False
    try:
        d = await _doc()
        p = ((d.get("pausados") or {}).get(nombre) or {})
        return bool(p.get("pausado"))
    except Exception:
        return False


async def _set_metrica(nombre, **campos):
    campos = {k: v for k, v in campos.items() if v is not None}
    if not campos:
        return
    try:
        sets = {f"metricas.{nombre}.{k}": v for k, v in campos.items()}
        sets["actualizado"] = _now()
        await _db().config.update_one({"_key": KEY}, {"$set": sets}, upsert=True)
    except Exception as e:
        logging.warning(f"loops_guard metrica {nombre}: {e}")


async def marcar_error(nombre, exc):
    await _set_metrica(nombre, estado="error", ultimo_error=str(exc)[:300],
                       error_en=_now())
    try:
        await _db().config.update_one(
            {"_key": KEY}, {"$inc": {f"metricas.{nombre}.reinicios": 1}}, upsert=True)
    except Exception:
        pass


async def correr_o_esperar(coro_fn, nombre):
    """Ejecuta el loop. True = terminó limpio (apagar supervisor). False = reintentar.

    Loops pausables se pueden cancelar a mitad de ciclo. Los protegidos nunca se cancelan.
    """
    await _set_metrica(nombre, visto_en=_now(), titulo=meta(nombre)["titulo"])
    if await esta_pausado(nombre):
        await _set_metrica(nombre, estado="pausado", heartbeat=_now())
        await asyncio.sleep(15)
        return False

    await _set_metrica(nombre, estado="corriendo", inicio=_now(), heartbeat=_now(),
                       ultimo_error="")
    child = asyncio.create_task(coro_fn())
    pausable = puede_pausar(nombre)
    try:
        while not child.done():
            try:
                await asyncio.wait_for(asyncio.shield(child), timeout=12)
            except asyncio.TimeoutError:
                await _set_metrica(nombre, heartbeat=_now(), estado="corriendo")
                if pausable and await esta_pausado(nombre):
                    child.cancel()
                    with suppress(asyncio.CancelledError, Exception):
                        await child
                    await _set_metrica(nombre, estado="pausado", heartbeat=_now())
                    return False
        await child
        await _set_metrica(nombre, estado="detenido_limpio", heartbeat=_now())
        return True
    except asyncio.CancelledError:
        if not child.done():
            child.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await child
        raise
    except Exception as e:
        await marcar_error(nombre, e)
        raise


def _fila(nombre, d, pausados):
    m = meta(nombre)
    met = (d.get("metricas") or {}).get(nombre) or {}
    p = (pausados or {}).get(nombre) or {}
    hb = met.get("heartbeat") or ""
    atrasado = False
    if hb and met.get("estado") == "corriendo":
        try:
            atrasado = (datetime.now(timezone.utc) -
                        datetime.fromisoformat(hb)).total_seconds() > 180
        except Exception:
            atrasado = False
    return {
        "nombre": nombre,
        "titulo": m["titulo"],
        "imap": bool(m.get("imap")),
        "pausable": bool(m.get("pausable")),
        "riesgo": m.get("riesgo") or "",
        "solapa": list(m.get("solapa") or []),
        "motivo": m.get("motivo") or "",
        "recomendado": nombre in RECOMENDADOS_PAUSA,
        "pausado": bool(p.get("pausado")),
        "pausado_por": p.get("por") or "",
        "pausado_en": p.get("en") or "",
        "estado": "pausado" if p.get("pausado") else (met.get("estado") or "sin_datos"),
        "heartbeat": hb,
        "inicio": met.get("inicio") or "",
        "reinicios": int(met.get("reinicios") or 0),
        "ultimo_error": met.get("ultimo_error") or "",
        "atrasado": atrasado,
    }


@loops_r.get("/estado")
async def loops_estado(request: Request):
    d = await _doc()
    pausados = d.get("pausados") or {}
    nombres = list(CATALOGO.keys())
    extra = [k for k in (d.get("metricas") or {}) if k not in CATALOGO]
    filas = [_fila(n, d, pausados) for n in nombres + extra]
    imap_vivos = sum(1 for f in filas if f["imap"] and f["estado"] == "corriendo")
    pausados_n = sum(1 for f in filas if f["pausado"])
    atrasados = [f["nombre"] for f in filas if f["atrasado"]]
    return {
        "loops": filas,
        "total": len(filas),
        "imap_corriendo": imap_vivos,
        "pausados": pausados_n,
        "atrasados": atrasados,
        "editable": _claims(request).get("rol") in ("admin", "maestro"),
        "nota": ("Todo sigue encendido por defecto. Pausar solo loops redundantes; "
                 "Mesa, ingesta y cuenta única no se tocan."),
        "actualizado": d.get("actualizado") or "",
    }


@loops_r.post("/{nombre}/pausa")
async def loops_pausa(nombre: str, payload: dict, request: Request):
    _exigir_admin(request)
    if not puede_pausar(nombre):
        raise HTTPException(
            status_code=403,
            detail=f"«{meta(nombre)['titulo']}» está protegido y no se puede pausar.")
    pausar = bool((payload or {}).get("pausado"))
    motivo = str((payload or {}).get("motivo") or "")[:200]
    por = _claims(request).get("sub") or "admin"
    await _db().config.update_one(
        {"_key": KEY},
        {"$set": {f"pausados.{nombre}": {
            "pausado": pausar, "por": por, "en": _now(), "motivo": motivo}}},
        upsert=True)
    await _set_metrica(nombre, estado="pausado" if pausar else "reanudando")
    try:
        await _db().system_log.insert_one({
            "id": str(uuid.uuid4()), "loop": nombre, "fecha": now_iso(),
            "evento": "pausa" if pausar else "reanudar",
            "por": por, "motivo": motivo})
    except Exception:
        pass
    return {"ok": True, "nombre": nombre, "pausado": pausar}
