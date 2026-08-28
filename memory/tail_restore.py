api.include_router(_audf_mod.audf)

# ⚖️ FUENTE DE VERDAD DE MESA — endpoints de estado/log del monitor
import mesa_verdad as _mesav_router
api.include_router(_mesav_router.mesav)

# 📡 GMAIL API + PUB/SUB — recepción en tiempo real (reemplaza polling IMAP de la cuenta principal)
import gmail_pubsub as _gmailps_mod
api.include_router(_gmailps_mod.gmailr)

# 🧪 MODO PRUEBA DE CLASIFICACIÓN — flujo completo sin notificar al cliente
import modo_prueba as _modop_mod
api.include_router(_modop_mod.modop)

# 📦 IMPORTADOR .MBOX de gran tamaño (streaming por fragmentos)
import mbox_import as _mbox_mod
api.include_router(_mbox_mod.mbox)

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
