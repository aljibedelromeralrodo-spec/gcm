"""CATÁLOGO MAESTRO DEFINITIVO — unificación de TODAS las reglas del sistema en el Cerebro DashAI.
Fuentes: Constitución Maestra (Reglas de Oro + Eficiencia, db.config), Normativas Maestras
(db.dashai_eventos) y Reglas Operativas implementadas en código (migradas aquí como inamovibles).
"""
import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from database import db

catalogo_r = APIRouter(prefix="/dashai/catalogo-maestro")

CATEGORIAS = {
    "jerarquia_roles": "JERARQUÍA Y ROLES",
    "operaciones_contratos": "OPERACIONES Y CONTRATOS",
    "normativa_financiera": "NORMATIVA FINANCIERA",
    "identidad_visual": "IDENTIDAD VISUAL Y COMUNICACIONES",
    "auditoria_trazabilidad": "AUDITORÍA Y TRAZABILIDAD",
}

# Categoría de cada Regla de Oro numerada (Constitución Maestra)
_CAT_ORO = {
    1: "normativa_financiera", 2: "identidad_visual", 3: "identidad_visual",
    4: "operaciones_contratos", 5: "operaciones_contratos", 6: "auditoria_trazabilidad",
    7: "identidad_visual", 8: "identidad_visual", 9: "normativa_financiera",
    10: "normativa_financiera", 11: "normativa_financiera", 12: "normativa_financiera",
    13: "auditoria_trazabilidad", 14: "identidad_visual", 15: "identidad_visual",
    16: "identidad_visual", 17: "auditoria_trazabilidad", 18: "jerarquia_roles",
    19: "jerarquia_roles", 20: "auditoria_trazabilidad", 21: "identidad_visual",
    22: "jerarquia_roles", 23: "auditoria_trazabilidad", 24: "operaciones_contratos",
    25: "auditoria_trazabilidad", 31: "auditoria_trazabilidad", 32: "jerarquia_roles",
    34: "operaciones_contratos", 35: "auditoria_trazabilidad", 36: "jerarquia_roles",
    37: "operaciones_contratos", 38: "jerarquia_roles", 41: "auditoria_trazabilidad",
    43: "operaciones_contratos", 49: "jerarquia_roles", 52: "jerarquia_roles",
    53: "auditoria_trazabilidad", 54: "identidad_visual", 55: "operaciones_contratos",
    56: "identidad_visual", 57: "auditoria_trazabilidad", 58: "operaciones_contratos",
    62: "identidad_visual", 63: "normativa_financiera", 64: "auditoria_trazabilidad",
    65: "operaciones_contratos", 66: "jerarquia_roles",
}

_MOD_ORO = {
    1: "credit_engine.py", 3: "server.py (PDF legal)", 4: "server.py (vinculación)",
    11: "credit_engine.py", 16: "email_service.py", 21: "whatsapp_twilio_service.py",
    22: "auth.py", 24: "server.py (automatización)", 34: "malla_inteligencia.py + auth.py",
    35: "bodega_concreces.py", 36: "malla_inteligencia.py", 38: "malla_inteligencia.py",
    41: "grid_dashai.py", 43: "malla_inteligencia.py", 55: "malla_inteligencia.py",
    62: "monitor_envios.py", 63: "server.py (contratos)", 64: "perfil_consolidado.py",
    66: "adn_clientes.py",
}

# Categoría de cada Normativa Maestra (db.dashai_eventos)
_CAT_NORMA = {
    "SUPERCARPETA": "operaciones_contratos", "VINCULACIÓN RUT": "operaciones_contratos",
    "ROLES 6 DASHBOARDS": "jerarquia_roles", "CC": "identidad_visual",
    "DISEÑO CORREOS": "identidad_visual", "PLANTILLAS": "identidad_visual",
    "DESTINATARIOS ESTUDIO": "identidad_visual", "ESPEJO HÍBRIDO": "operaciones_contratos",
    "ESTUDIO DE TÍTULO": "operaciones_contratos", "POSTVENTA ETAPAS": "operaciones_contratos",
    "RESUMEN IA": "auditoria_trazabilidad", "INTELIGENCIA COMERCIAL": "auditoria_trazabilidad",
    "BROKER VENTANA EXCEL": "operaciones_contratos",
    "IDENTIDAD VISUAL OFICIAL": "identidad_visual",
    "AUDITORÍA EFICIENCIA": "auditoria_trazabilidad",
}

# Reglas Operativas implementadas en código, sin archivo formal previo → SE MIGRAN AL CEREBRO
REGLAS_OPERATIVAS = [
    {"num": "OP-1", "titulo": "RUT único entre brokers",
     "ley": "Un RUT de cliente pertenece permanentemente al primer broker que lo ingresa. Todo segundo ingreso del mismo RUT por otro ejecutivo es rechazado (409) con mensaje claro.",
     "categoria": "operaciones_contratos", "modulo": "malla_inteligencia.py (/broker/carpetas)"},
    {"num": "OP-2", "titulo": "Ventana de proyecciones (día 1-5 hábil)",
     "ley": "La carga de proyecciones mensuales del broker solo está habilitada entre el día 1 y el 5 hábil de cada mes. Fuera de la ventana el botón queda deshabilitado con mensaje explicativo.",
     "categoria": "operaciones_contratos", "modulo": "malla_inteligencia.py (/broker/ventana-proyeccion)"},
    {"num": "OP-3", "titulo": "Primer ingreso obligatorio",
     "ley": "Todo usuario nuevo debe cambiar su contraseña provisoria y configurar su IMAP en el primer ingreso. El asistente no puede saltarse; el flag first_login solo se apaga al completar ambos pasos.",
     "categoria": "jerarquia_roles", "modulo": "server.py (/auth/primer-ingreso) + PrimerIngreso.js"},
    {"num": "OP-4", "titulo": "Contraseña provisoria y bienvenida formal",
     "ley": "La creación de un usuario genera automáticamente una contraseña provisoria de 10 caracteres y envía el correo de bienvenida en HTML responsivo con las credenciales.",
     "categoria": "jerarquia_roles", "modulo": "server.py (/admin/users)"},
    {"num": "OP-5", "titulo": "Creación jerárquica de usuarios",
     "ley": "El rol Administración solo puede crear usuarios tipo C (brokers y administrativos). La creación de roles superiores está bloqueada (403) y reservada al Admin.",
     "categoria": "jerarquia_roles", "modulo": "server.py (/admin/users)"},
    {"num": "OP-6", "titulo": "Contralor: solo lectura absoluta",
     "ley": "El rol Contralor tiene acceso de solo lectura y auditoría absoluta en todo el sistema. Cualquier intento de escritura fuera de su módulo espejo es rechazado.",
     "categoria": "jerarquia_roles", "modulo": "auth.py (ROL_BLOQUEO_ESCRITURA)"},
    {"num": "OP-7", "titulo": "Validación de normativas pre-operación",
     "ley": "El sistema valida las normativas vigentes (caché máximo 5 minutos) antes de aprobar, avanzar o enviar cualquier operación. Ante incumplimiento bloquea con error 422 y el detalle exacto de la normativa violada.",
     "categoria": "auditoria_trazabilidad", "modulo": "espejo_postventa.py (_validar_normativas_op)"},
    {"num": "OP-8", "titulo": "Bandeja de documentos sin clasificar",
     "ley": "Todo documento que no puede asociarse a una operación ingresa a la bandeja de no clasificados, visible solo para Administración, Admin y Contralor, con asignación manual a la carpeta correcta.",
     "categoria": "operaciones_contratos", "modulo": "server.py (/admin/docs-sin-clasificar)"},
    {"num": "OP-9", "titulo": "Storage documental por operación/RUT",
     "ley": "Cada documento subido se almacena también en el storage integrado, organizado por operación y RUT (dual write), con visualización directa sin descarga y control de acceso estricto por rol: cada broker solo ve sus propios documentos.",
     "categoria": "operaciones_contratos", "modulo": "media_storage.py"},
    {"num": "OP-10", "titulo": "IA del Espejo con registro inmutable",
     "ley": "Claude analiza únicamente correos nuevos de la matriz con contexto mínimo. Toda interpretación queda registrada con marca de tiempo; las urgencias (normativas, plazos vencidos, riesgo) notifican al Admin y al Contralor, y solo el Admin puede corregirlas manualmente, dejando huella en el log.",
     "categoria": "auditoria_trazabilidad", "modulo": "espejo_ia.py + espejo_postventa.py"},
]


# Reglas INVIOLABLES recuperadas de la auditoría histórica del código (mandatos absolutos)
REGLAS_INVIOLABLES = [
    {"num": "INV-1", "titulo": "Prohibido inventar datos (IA)",
     "ley": "REGLA INVIOLABLE: la IA tiene PROHIBIDO inventar o estimar datos. Si un dato no aparece literalmente en la fuente, el campo queda vacío o marcado para revisión manual. Aplica a toda extracción, resumen e inteligencia comercial.",
     "categoria": "auditoria_trazabilidad", "modulo": "ai_extract.py"},
    {"num": "INV-2", "titulo": "Blindaje final de simulaciones",
     "ley": "REGLA INVIOLABLE: ninguna simulación sale del sistema con más de 1 página (sin otros plazos ni gastos operacionales). Se aplica a TODO envío (aprobación cliente, autocorreo, etc.). Solo la clave maestra (MASTER_PIN) permite omitirlo.",
     "categoria": "identidad_visual", "modulo": "email_service.py (_blindaje_simulaciones)"},
    {"num": "INV-3", "titulo": "Crédito mínimo 2.000 UF sin subsidio",
     "ley": "REGLA INVIOLABLE DEL DUEÑO: sin subsidio, el crédito mínimo es 2.000 UF (tope duro MONTO_MIN_UF_SIN_SUBSIDIO_HARD). Ninguna evaluación puede aprobarse bajo ese monto.",
     "categoria": "normativa_financiera", "modulo": "mesa_brain.py"},
    {"num": "INV-4", "titulo": "Cartas de aprobación intactas",
     "ley": "REGLA INVIOLABLE: cualquier indicio de que un documento es una carta de aprobación (nombre o contenido) lo clasifica como carta y NUNCA se modifica. Las cartas de aprobación salen SIEMPRE intactas, formato sin alterar.",
     "categoria": "operaciones_contratos", "modulo": "pdf_service.py + server.py"},
    {"num": "INV-5", "titulo": "Centro de Ventas VIP solo prepara",
     "ley": "REGLA INVIOLABLE: el motor comercial del Centro de Ventas VIP solo PREPARA material; nada sale del sistema sin la acción explícita 'Autorizar Envío' del Administrador.",
     "categoria": "jerarquia_roles", "modulo": "sales_engine.py"},
]


def _now():
    return datetime.now(timezone.utc).isoformat()


async def seed_operativas():
    """PASO 2 — migra al Cerebro las reglas operativas del código (idempotente)."""
    migradas = 0
    for r in REGLAS_OPERATIVAS:
        if not await db.dashai_eventos.find_one({"motivo": "regla_operativa", "norma_clave": r["num"]}):
            await db.dashai_eventos.insert_one({
                "id": str(uuid.uuid4()), "motivo": "regla_operativa", "norma_clave": r["num"],
                "titulo": r["titulo"], "patron": r["ley"], "categoria": r["categoria"],
                "modulo": r["modulo"], "fecha": _now(), "inamovible": True})
            migradas += 1
    if migradas:
        await db.config.update_one({"_key": "catalogo_maestro_migracion"}, {"$set": {
            "ultima_migracion": _now(), "migradas": migradas,
            "nota": "Reglas operativas del código migradas formalmente al Cerebro DashAI"}}, upsert=True)
        logging.info(f"📜 Catálogo Maestro: {migradas} reglas operativas migradas al Cerebro")
    return migradas


async def archivar_constitucion_completa():
    """CONSTITUCIÓN OFICIAL — archiva TODAS las reglas en db.dashai_eventos como
    inamovibles e inviolables. Idempotente: si existen, actualiza descripción sin duplicar."""
    cons = await db.config.find_one({"_key": "constitucion_maestra"}) or {}
    nuevas, actualizadas = 0, 0

    async def _upsert(motivo, clave, titulo, ley, categoria, modulo):
        nonlocal nuevas, actualizadas
        campos = {"titulo": titulo, "patron": ley, "categoria": categoria, "modulo": modulo,
                  "inamovible": True, "inviolable": True,
                  "estado": "inamovible e inviolable"}
        ex = await db.dashai_eventos.find_one({"motivo": motivo, "norma_clave": clave})
        if ex:
            await db.dashai_eventos.update_one({"motivo": motivo, "norma_clave": clave},
                                               {"$set": campos})
            actualizadas += 1
        else:
            await db.dashai_eventos.insert_one({"id": str(uuid.uuid4()), "motivo": motivo,
                                                "norma_clave": clave, "fecha": _now(), **campos})
            nuevas += 1

    for r in cons.get("reglas") or []:
        n = int(r.get("n") or 0)
        await _upsert("regla_oro", f"ORO-{n}", r.get("titulo") or r.get("id"), r.get("ley"),
                      _CAT_ORO.get(n, "auditoria_trazabilidad"),
                      _MOD_ORO.get(n, "Motor Central (server.py)"))
    for i, r in enumerate(cons.get("reglas_eficiencia") or [], 1):
        await _upsert("regla_eficiencia", f"EF-{i}", r.get("id", "").replace("_", " ").title(),
                      r.get("ley"), "auditoria_trazabilidad", "Arquitectura (todo el sistema)")
    for r in REGLAS_INVIOLABLES:
        await _upsert("regla_inviolable", r["num"], r["titulo"], r["ley"], r["categoria"], r["modulo"])
    # normativas y operativas ya viven en dashai_eventos → se les sella el estado inviolable
    sellos = await db.dashai_eventos.update_many(
        {"motivo": {"$in": ["normativa", "regla_operativa"]}},
        {"$set": {"inamovible": True, "inviolable": True, "estado": "inamovible e inviolable"}})
    await db.config.update_one({"_key": "constitucion_oficial_archivo"}, {"$set": {
        "archivado": _now(), "nuevas": nuevas, "actualizadas": actualizadas,
        "selladas": sellos.modified_count,
        "nota": "Constitución oficial del sistema: ningún módulo, rol ni proceso puede operar en contradicción con estas reglas."}},
        upsert=True)
    logging.info(f"🏛 Constitución archivada en el Cerebro: {nuevas} nuevas, {actualizadas} actualizadas")
    return {"nuevas": nuevas, "actualizadas": actualizadas, "selladas": sellos.modified_count}


@catalogo_r.get("")
async def catalogo_maestro(request: Request):
    """PASO 3 — listado oficial completo, agrupado por categoría (solo Admin)."""
    if (getattr(request.state, "user", {}) or {}).get("rol") not in ("admin", "maestro"):
        raise HTTPException(status_code=403, detail="El Catálogo Maestro de reglas es visible solo para el Administrador")
    cons = await db.config.find_one({"_key": "constitucion_maestra"}) or {}
    reglas_oro = cons.get("reglas") or []
    reglas_ef = cons.get("reglas_eficiencia") or []
    normas = await db.dashai_eventos.find({"motivo": "normativa"}, {"_id": 0}).to_list(100)
    operativas = await db.dashai_eventos.find({"motivo": "regla_operativa"}, {"_id": 0}).to_list(100)
    inviolables = await db.dashai_eventos.find({"motivo": "regla_inviolable"}, {"_id": 0}).to_list(100)

    grupos = {k: [] for k in CATEGORIAS}
    for r in reglas_oro:
        n = int(r.get("n") or 0)
        grupos[_CAT_ORO.get(n, "auditoria_trazabilidad")].append({
            "num": f"Regla de Oro #{n}", "titulo": r.get("titulo") or r.get("id"),
            "descripcion": r.get("ley"), "estado": "activa · inamovible",
            "modulo": _MOD_ORO.get(n, "Motor Central (server.py)"), "fuente": "Constitución Maestra"})
    for i, r in enumerate(reglas_ef, 1):
        grupos["auditoria_trazabilidad"].append({
            "num": f"Eficiencia E-{i}", "titulo": r.get("id", "").replace("_", " ").title(),
            "descripcion": r.get("ley"), "estado": "activa · perpetua",
            "modulo": "Arquitectura (todo el sistema)", "fuente": "Constitución Maestra"})
    for nm in sorted(normas, key=lambda x: x.get("norma_clave") or ""):
        cl = nm.get("norma_clave") or ""
        grupos[_CAT_NORMA.get(cl, "auditoria_trazabilidad")].append({
            "num": f"Normativa {cl}", "titulo": cl.title(),
            "descripcion": nm.get("patron"), "estado": "activa · inamovible",
            "modulo": "Cerebro DashAI (dashai_eventos)", "fuente": "Normativa Maestra"})
    for op in sorted(operativas, key=lambda x: int((x.get("norma_clave") or "OP-0").split("-")[-1])):
        grupos[op.get("categoria") or "operaciones_contratos"].append({
            "num": op.get("norma_clave"), "titulo": op.get("titulo"),
            "descripcion": op.get("patron"), "estado": "activa · inamovible",
            "modulo": op.get("modulo"), "fuente": "Regla Operativa (migrada)"})
    for iv in sorted(inviolables, key=lambda x: int((x.get("norma_clave") or "INV-0").split("-")[-1])):
        grupos[iv.get("categoria") or "auditoria_trazabilidad"].append({
            "num": iv.get("norma_clave"), "titulo": iv.get("titulo"),
            "descripcion": iv.get("patron"), "estado": "activa · inviolable",
            "modulo": iv.get("modulo"), "fuente": "Regla Inviolable (auditoría histórica)"})

    mig = await db.config.find_one({"_key": "catalogo_maestro_migracion"}, {"_id": 0}) or {}
    archivo = await db.config.find_one({"_key": "constitucion_oficial_archivo"}, {"_id": 0}) or {}
    total = sum(len(v) for v in grupos.values())
    return {"version_constitucion": cons.get("version"),
            "total_reglas": total,
            "resumen": {"reglas_oro": len(reglas_oro), "reglas_eficiencia": len(reglas_ef),
                        "normativas_maestras": len(normas), "reglas_operativas": len(operativas),
                        "reglas_inviolables": len(inviolables)},
            "migracion": mig, "archivo_constitucion": archivo,
            "categorias": [{"clave": k, "nombre": CATEGORIAS[k], "total": len(grupos[k]),
                            "reglas": grupos[k]} for k in CATEGORIAS]}
