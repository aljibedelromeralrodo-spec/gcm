"""CONSTITUCIÓN MAESTRA — Fuente de verdad inmutable de DashAI (Central Mutuos).

Las 15 Reglas de Oro viven en db.config {_key: "constitucion_maestra"}. Ninguna
actualización de código puede pisar estos valores. Cada función crítica (correos,
PDFs, cálculo financiero) consulta la Constitución ANTES de actuar mediante el
decorador @protege(...) o la llamada inline exigir(...).
"""
import re
import logging
from functools import wraps

# ── LAS 20 REGLAS DE ORO (numeración canónica — fuente de verdad) ──────────
REGLAS_ORO = [
    {"n": 1, "id": "uf_sii", "titulo": "UF coordinada con el SII",
     "ley": "El valor UF es SIEMPRE el del SII del día (America/Santiago). Prohibido usar valores antiguos o por defecto en documentos y cálculos."},
    {"n": 2, "id": "purificacion_correos", "titulo": "Purificación de correos al cliente",
     "ley": "Las notificaciones al solicitante no pueden contener correos externos, datos del remitente técnico ni rastro de la MESA. El sistema es el único intermediario."},
    {"n": 3, "id": "sobriedad_pdf", "titulo": "Sobriedad de documentos legales",
     "ley": "Los PDF legales (Compromisos) son 100% negro sobre blanco, Times/Arial, sin dorados ni estilos corporativos."},
    {"n": 4, "id": "bloqueo_rut", "titulo": "Bloqueo de RUT (Match Total)",
     "ley": "Ningún documento se vincula a una carpeta sin coincidencia exacta de RUT. Nunca contaminar datos entre personas distintas."},
    {"n": 5, "id": "firmas_ecert", "titulo": "Integridad de firmas eCert",
     "ley": "Jamás replicar, copiar o falsificar una firma eCert. Solo firmas genuinas emitidas por eCert. Los documentos firmados son inmutables."},
    {"n": 6, "id": "links_privados", "titulo": "Links privados con token",
     "ley": "Ningún archivo del sistema es accesible sin token de sesión válido (?t=TOKEN o cookie cm_token). Prohibidos los links públicos a documentos de clientes."},
    {"n": 7, "id": "cerrojo_duplicados", "titulo": "Cerrojo atómico de duplicados",
     "ley": "Toda notificación reserva su clave (RUT+Nombre) antes de enviar. Prohibidos los correos repetidos tras un reinicio."},
    {"n": 8, "id": "anti_rafaga", "titulo": "Ritmo anti-ráfaga",
     "ley": "Máximo 3 correos por ciclo y 10 segundos entre envíos. El backlog sale goteando por la cola pausada, jamás en ráfaga."},
    {"n": 9, "id": "carga_conjunta_40", "titulo": "Carga financiera conjunta 40%",
     "ley": "Si la carga conjunta (titular + codeudor) supera el 40%, es RIESGO CRÍTICO, mande lo que mande la MESA."},
    {"n": 10, "id": "codeudor_total", "titulo": "Codeudor Total",
     "ley": "La deuda CMF se agrega titular + codeudor. El OCR procesa también la subcarpeta 05_codeudor/."},
    {"n": 11, "id": "ratio_80", "titulo": "LTV 80 sin redondeo hacia arriba",
     "ley": "El crédito nunca supera el 80% del precio. El LTV se TRUNCA a 2 decimales; el sistema jamás entrega un 80.01%."},
    {"n": 12, "id": "renta_anticipos", "titulo": "Renta con anticipos",
     "ley": "La renta reconocida suma el líquido más los anticipos/avances de cada mes y promedia sobre los meses disponibles (política 6 meses)."},
    {"n": 13, "id": "bunker_gridfs", "titulo": "Búnker GridFS",
     "ley": "Todo archivo se respalda en espejo disco→GridFS. Si falta en disco tras un reinicio, se restaura desde el Búnker antes de servirlo."},
    {"n": 14, "id": "notificacion_ejecutivo", "titulo": "Notificación al ejecutivo",
     "ley": "Remitente visible: 'Respuestas Mesa Clientes'. Asuntos limpios y corporativos, sin términos técnicos ('ajustado', 'técnico')."},
    {"n": 15, "id": "filtro_temporal", "titulo": "Filtro temporal (nada retroactivo)",
     "ley": "Las notificaciones automáticas solo operan para correos procesados desde su fecha de activación. Prohibido notificar casos antiguos."},
    {"n": 16, "id": "responsividad_absoluta", "titulo": "Responsividad Absoluta",
     "ley": "Todo correo, reporte o documento generado por el sistema DEBE ser 100% responsivo. Prohibido el uso de anchos fijos superiores a 600px. El diseño se auto-adapta a teléfonos y PCs, con tipografía legible, proporciones elegantes y sin desbordes visuales."},
    {"n": 17, "id": "privacidad_cerebro", "titulo": "Privacidad del Cerebro exportable",
     "ley": "El Cerebro DashAI se exporta sin datos privados de clientes: solo inteligencia y casos anonimizados."},
    {"n": 18, "id": "mando_unico", "titulo": "Mando único",
     "ley": "El sistema responde únicamente a Gerardo Barrera (rol admin) y al Master PIN 0586. No existen otros administradores maestros."},
    {"n": 19, "id": "master_pin", "titulo": "Master PIN 0586",
     "ley": "El Master PIN 0586 es la autoridad suprema de override del sistema."},
    {"n": 20, "id": "consulta_de_ley", "titulo": "Consulta de Ley obligatoria",
     "ley": "Antes de aplicar cualquier arreglo de bug o cambio de código, el agente consulta la Constitución en DashAI y verifica que no rompe una Regla de Oro. Si DashAI no lo autoriza, no se publica."},
    {"n": 21, "id": "whatsapp_twilio", "titulo": "Motor WhatsApp oficial: Twilio",
     "ley": "Motor WhatsApp oficial: Twilio (Número Exclusivo). Prohibido usar métodos manuales, links wa.me o sesiones de navegador/QR. El número exclusivo es solo para automatización vía API."},
]

VERSION = 5  # 21 reglas


class ViolacionConstitucional(Exception):
    """Se lanza cuando una acción intenta violar una Regla de Oro."""
    pass


# ── VALIDADORES RUNTIME (context-based) ─────────────────────────────────────
_ORO_HEX = re.compile(r"#(d4af37|b8942e|bf953f|fcf6ba|b38728|aa771c|c7b36a|9a8c52)", re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _val_sobriedad_pdf(ctx):
    html = ctx.get("html", "") or ""
    if _ORO_HEX.search(html):
        return "documento legal con color dorado (viola sobriedad negro/blanco)"
    return None


def _val_purificacion(ctx):
    texto = f"{ctx.get('subject','')} {ctx.get('html','')}"
    if _EMAIL.search(re.sub(r"<[^>]+>", " ", texto)):
        return "correo al cliente con dirección de email externa en el cuerpo"
    if re.search(r"\b(mesa|aprobaciones@|reenviad)\b", texto, re.I):
        return "correo al cliente con rastro de la MESA/remitente"
    return None


def _val_ratio_80(ctx):
    precio = float(ctx.get("precio_uf") or 0)
    credito = float(ctx.get("credito_uf") or 0)
    if precio > 0 and credito > precio * 0.80 + 0.01:
        return f"crédito {credito} UF supera el 80% del precio {precio} UF"
    return None


def _val_uf_sii(ctx):
    if ctx.get("uf_al_dia") is False:
        return "UF utilizada no está coordinada con el SII del día"
    return None


_ANCHO_FIJO = re.compile(r"width\s*:\s*(\d{3,})\s*px", re.I)


def _val_responsividad(ctx):
    html = ctx.get("html", "") or ""
    for m in _ANCHO_FIJO.finditer(html):
        # max-width está permitido; solo se prohíbe width fijo > 600px
        prefijo = html[max(0, m.start() - 4):m.start()].lower()
        if "max-" in prefijo:
            continue
        if int(m.group(1)) > 600:
            return f"ancho fijo {m.group(1)}px supera el máximo responsivo de 600px"
    return None


VALIDADORES = {
    "sobriedad_pdf": _val_sobriedad_pdf,
    "purificacion_correos": _val_purificacion,
    "ratio_80": _val_ratio_80,
    "uf_sii": _val_uf_sii,
    "responsividad_absoluta": _val_responsividad,
}


def exigir(regla, **ctx):
    """Consulta previa obligatoria: valida `regla` contra el contexto. Si la viola,
    lanza ViolacionConstitucional. Uso inline en funciones críticas."""
    logging.info(f"Consultando Constitución en DashAI... [{regla}]")
    val = VALIDADORES.get(regla)
    if val:
        problema = val(ctx)
        if problema:
            logging.error(f"⛔ Violación Constitucional detectada [{regla}]: {problema}")
            raise ViolacionConstitucional(
                f"ERROR: Acción bloqueada por violación de Regla de Oro en DashAI ({regla}): {problema}")
    return True


def protege(*reglas):
    """Decorador que envuelve una función crítica. Antes de ejecutar valida las
    reglas indicadas contra el kwarg `_ctx` (dict) si viene; registra la violación."""
    def deco(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            ctx = kwargs.get("_ctx") or {}
            for r in reglas:
                exigir(r, **ctx)
            return await fn(*args, **kwargs)
        return wrapper
    return deco


async def seed_constitucion(db):
    """Graba/actualiza la Constitución SOLO si falta o cambió la versión. Nunca
    pisa personalizaciones del dueño una vez creada su versión vigente."""
    doc = await db.config.find_one({"_key": "constitucion_maestra"})
    if not doc or int(doc.get("version") or 0) < VERSION:
        await db.config.update_one({"_key": "constitucion_maestra"}, {"$set": {
            "version": VERSION, "reglas": REGLAS_ORO, "mando": "Gerardo Barrera",
            "master_pin_ref": "MASTER_PIN (0586)",
            "aprendizaje": {
                "fuente_primaria": "buzones IMAP operativos",
                "fuente_secundaria_solo_lectura": (doc or {}).get("aprendizaje", {}).get("fuente_secundaria_solo_lectura", ""),
                "nota": "Slot reservado para el segundo buzón de aprendizaje (solo lectura)."},
        }}, upsert=True)
    return await db.config.find_one({"_key": "constitucion_maestra"}, {"_id": 0})
