"""MONITOR DE ENERGÍA — Reserva de funcionamiento (copiloto financiero).

Cuenta cada llamada LLM real de la app y estima el gasto en créditos partiendo de
un saldo inicial que carga el dueño. Proyecta autonomía y prioriza los motores
esenciales (autocorreo + Contralor) ante saldos bajos.
"""
import os
import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter
from database import db

energia = APIRouter(prefix="/energia")

# Umbrales (Regla de Hierro del dueño)
CONSUMO_DIA = float(os.environ.get("ENERGIA_CONSUMO_DIA", "9"))   # créditos/día
COSTO_POR_LLAMADA = float(os.environ.get("ENERGIA_COSTO_LLAMADA", "0.12"))  # crédito/llamada LLM
UMBRAL_BAJO = 50          # banner persistente
UMBRAL_CRITICO = 27       # 3 días de reserva → alerta externa
_now = lambda: datetime.now(timezone.utc).isoformat()


async def registrar_llm(n=1):
    """Suma n llamadas LLM al contador de consumo (no bloquea el flujo si falla)."""
    try:
        await db.config.update_one({"_key": "energia"},
                                   {"$inc": {"llamadas_llm": int(n)},
                                    "$set": {"ultima_llamada": _now()}}, upsert=True)
    except Exception as e:
        logging.warning(f"energia registrar_llm: {e}")


async def _estado():
    cfg = await db.config.find_one({"_key": "energia"}) or {}
    saldo_inicial = float(cfg.get("saldo_inicial") or 0)
    llamadas = int(cfg.get("llamadas_llm") or 0)
    llamadas_base = int(cfg.get("llamadas_base") or 0)
    consumo_dia = float(cfg.get("consumo_dia") or CONSUMO_DIA)
    gasto = round((llamadas - llamadas_base) * COSTO_POR_LLAMADA, 2)
    saldo = max(0.0, round(saldo_inicial - gasto, 2))
    dias = int(saldo // consumo_dia) if consumo_dia > 0 else 0
    if saldo_inicial <= 0:
        nivel, banner = "sin_config", ""
    else:
        nivel = "critico" if saldo < UMBRAL_CRITICO else "bajo" if saldo < UMBRAL_BAJO else "ok"
        banner = ""
        if nivel == "bajo":
            banner = "Reserva de funcionamiento baja. El motor de correos y DashAI podrían detenerse."
        elif nivel == "critico":
            banner = ("Reserva CRÍTICA (menos de 3 días). Recargue ahora para evitar el apagón del "
                      "motor de correos y DashAI.")
    return {
        "saldo_inicial": saldo_inicial, "saldo_actual": saldo, "gasto_estimado": gasto,
        "llamadas_llm": llamadas - llamadas_base, "consumo_dia": consumo_dia,
        "costo_por_llamada": COSTO_POR_LLAMADA, "dias_autonomia": dias,
        "nivel": nivel, "banner": banner,
        "umbral_bajo": UMBRAL_BAJO, "umbral_critico": UMBRAL_CRITICO,
        "modo_ahorro": bool(cfg.get("modo_ahorro")) or nivel == "critico",
        "actualizado": _now(),
    }


async def bloquea_ia_alto_costo():
    """PRIORIZACIÓN DE MOTOR: en saldo crítico se frenan funciones IA de alto costo;
    autocorreo_loop y Contralor NO pasan por aquí (siguen operando)."""
    est = await _estado()
    return est["nivel"] == "critico" or est["modo_ahorro"]


async def _chequear_reserva_y_avisar():
    """Envía UNA sola alerta (por correo) cuando cruza a nivel crítico (<27)."""
    est = await _estado()
    cfg = await db.config.find_one({"_key": "energia"}) or {}
    ya = (cfg.get("aviso_critico_en") or "")[:10]
    hoy = _now()[:10]
    if est["nivel"] == "critico" and ya != hoy and est["saldo_inicial"] > 0:
        try:
            import email_service as mail
            to = os.environ.get("MAIL_NOTIF_TEST") or os.environ.get("MAIL2_USER", "")
            if to:
                cuerpo = (f"<div style='font-family:Arial;color:#000'><b>Alerta de Reserva Crítica</b>"
                          f"<p>Saldo estimado: <b>{est['saldo_actual']} créditos</b> "
                          f"(~{est['dias_autonomia']} día(s) de autonomía a {est['consumo_dia']}/día).</p>"
                          f"<p>Recargue para evitar el apagón del motor de correos y DashAI.</p></div>")
                await asyncio.to_thread(mail.send_mail, to,
                                        "⚠ Reserva crítica de funcionamiento", cuerpo, [], "secundaria")
            # Motor WhatsApp oficial Twilio (Regla #21) — si el número exclusivo ya está activo
            try:
                import whatsapp_twilio_service as _wa
                if _wa.configurado():
                    await _wa.alerta_admin(
                        f"⚠ RESERVA CRÍTICA Central Mutuos: {est['saldo_actual']} créditos "
                        f"(~{est['dias_autonomia']} día(s)). Recargue para evitar el apagón del motor.",
                        tipo="energia_critica")
            except Exception as _e:
                logging.warning(f"energia whatsapp: {_e}")
            await db.config.update_one({"_key": "energia"},
                                       {"$set": {"aviso_critico_en": hoy}}, upsert=True)
        except Exception as e:
            logging.warning(f"energia aviso critico: {e}")
    return est


@energia.get("")
async def energia_estado():
    return await _chequear_reserva_y_avisar()


@energia.post("/cargar")
async def energia_cargar(payload: dict):
    """El dueño carga su saldo real (créditos). Reinicia el contador de consumo."""
    saldo = float((payload or {}).get("saldo") or 0)
    cfg = await db.config.find_one({"_key": "energia"}) or {}
    await db.config.update_one({"_key": "energia"}, {"$set": {
        "saldo_inicial": saldo, "llamadas_base": int(cfg.get("llamadas_llm") or 0),
        "consumo_dia": float((payload or {}).get("consumo_dia") or cfg.get("consumo_dia") or CONSUMO_DIA),
        "aviso_critico_en": "", "cargado_en": _now()}}, upsert=True)
    return await _estado()


@energia.post("/modo-ahorro")
async def energia_modo_ahorro(payload: dict):
    activo = bool((payload or {}).get("activo"))
    await db.config.update_one({"_key": "energia"}, {"$set": {"modo_ahorro": activo}}, upsert=True)
    return {"ok": True, "modo_ahorro": activo}
