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
    {"n": 22, "id": "jerarquia_ab", "titulo": "Jerarquía de usuarios A y B",
     "ley": "Solo el administrador supremo puede gestionar los niveles de acceso A y B. DashAI monitorea que ningún usuario A acceda a funciones de auditoría."},
    {"n": 23, "id": "eficiencia_creditos", "titulo": "Ley de Eficiencia y Ahorro de Créditos",
     "ley": "El objetivo es construir el mejor sistema con el menor consumo posible: Economía de Código, Minimización de Llamadas, Bypass Pesado, Detección de Bucle y Estimación Previa. La inteligencia no es gastar más, sino gastar mejor."},
    {"n": 24, "id": "contraste_rut_rol", "titulo": "Contraste RUT/Rol contra SII",
     "ley": "La automatización administrativa solo procede si el RUT y el Rol de Propiedad han sido contrastados y validados al 100% contra el SII. Sin respaldo OCR, el envío queda bloqueado."},
    {"n": 25, "id": "reporte_gerencia", "titulo": "Reporte de Gerencia Comercial",
     "ley": "El reporte de Gerencia Comercial es la fuente oficial de metas. Los datos de avance deben ser auditados por DashAI cada 6 horas."},
    {"n": 31, "id": "protocolo_excepcion", "titulo": "Protocolo de Autorización de Excepción",
     "ley": "Toda regla puede ser saltada manualmente por un ejecutivo autorizado, siempre que quede registro inmutable de su identidad y motivo bajo el Protocolo de Excepción. No hay avance manual sin firma digital del ejecutivo."},
    {"n": 32, "id": "division_operativa", "titulo": "División Operativa Daniela/Victoria",
     "ley": "La operación se divide en dos fases: Revisión (Daniela) y Carga (Victoria). Ambas deben usar sus respectivos módulos para mantener el orden administrativo. Funciones definitivas solo por instrucción final de Gerardo."},
    {"n": 34, "id": "malla_inteligencia_rut", "titulo": "Malla de Inteligencia — Validación por RUT",
     "ley": "Toda actualización de hito por correo externo debe ser validada por DashAI mediante el RUT del cliente en el asunto o cuerpo del mail. REGLA DE HIERRO: el RUT es el pegamento; si DashAI no encuentra un RUT en el mail externo, el hito no se marca para evitar falsos positivos."},
    {"n": 35, "id": "control_auditor_informativo", "titulo": "Módulo Control — Auditor Informativo",
     "ley": "El Módulo Control solo tiene facultades de Auditoría e Información. La decisión operativa final recae exclusivamente en Gerencia de Riesgo y Concreces. El hallazgo de una inconsistencia NUNCA bloquea el flujo de la operación: solo se marca visualmente y se informa por correo responsivo y purificado."},
    {"n": 36, "id": "gestion_fuentes_firmada", "titulo": "Gestión de Fuentes firmada por módulo",
     "ley": "Cada ejecutivo gestiona sus propios aliados y fuentes de datos. Todo cambio en la red de escucha debe quedar firmado digitalmente por el responsable del módulo. REGLA DE HIERRO: DashAI solo procesa correos de las fuentes activas en el Gestor; si se borra un correo, el sistema deja de escucharlo inmediatamente."},
    {"n": 37, "id": "fuentes_transitorias_permanentes", "titulo": "Fuentes Transitorias vs Permanentes",
     "ley": "Las fuentes de datos se dividen en Transitorias (Vendedores) y Permanentes (Inmobiliarias). DashAI debe archivar la información siguiendo este flujo. REGLA DE HIERRO: el RUT del cliente es el único eje que une al vendedor de una usada con el estudio del abogado, para evitar cruces de carpetas."},
    {"n": 38, "id": "salud_buzon_trazabilidad_broker", "titulo": "Salud del buzón y trazabilidad del Broker",
     "ley": "Cada ejecutivo es responsable de la salud técnica de su buzón. El sistema garantiza la trazabilidad del Broker desde el ingreso hasta la entrega final. REGLA DE HIERRO: si una clave de aplicación falla, el sistema notifica '⚠️ Su conexión de correo necesita actualización' en lugar de detener todo el Maserati. Las credenciales se cifran con AES-256 y solo el dueño o Gerardo (PIN 0586) acceden."},
    {"n": 41, "id": "sincronizacion_forzada_grid", "titulo": "Sincronización Forzada GRID-DASHAI",
     "ley": "La información en Central Mutuos es única y universal. Todo cambio en un módulo debe propagarse a toda la red local y nube de forma inmediata y forzada. REGLA DE HIERRO: si un computador está en línea, su carpeta de clientes debe ser un espejo exacto del servidor (firmas MD5); no se permiten versiones distintas de un mismo archivo, y está PROHIBIDO cualquier interruptor que detenga la sincronización."},
    {"n": 43, "id": "escrituracion_flujo_real", "titulo": "Escrituración nutrida del flujo real de correos",
     "ley": "La información de escrituración se nutre del flujo real de correos con abogados y tasadores. DashAI es responsable de transcribir los reparos directamente a la ficha del cliente. REGLA DE HIERRO: no se inventan datos; si no hay un correo que respalde la tasación o el reparo, el hito queda como 'Pendiente de Información'."},
    {"n": 49, "id": "comunicacion_manual_brokers", "titulo": "Comunicación normativa manual con Brokers",
     "ley": "La comunicación normativa con los Brokers es una facultad manual de la Gerencia Comercial. El sistema solo provee la herramienta de envío rápido. REGLA DE HIERRO: el Maserati provee los datos, pero Rodrigo Ibáñez provee la decisión; ningún mail de reclamo sale de forma automática sin su intervención."},
    {"n": 52, "id": "gerencia_juez_velocidad", "titulo": "Gerencia Comercial: juez de la velocidad",
     "ley": "La Gerencia Comercial tiene la facultad única de priorizar operaciones y auditar discrepancias. El Dashboard de Rodrigo es el único juez de la velocidad del negocio. REGLA DE HIERRO: cada clic de gestión queda registrado en el Log de Gestión Gerencial para auditar la eficiencia del seguimiento."},
    {"n": 53, "id": "doble_boveda_documental", "titulo": "Doble Bóveda y Respaldo Permanente",
     "ley": "Ningún documento legal es válido si no existe simultáneamente en la Bóveda Local del ejecutivo y en el Espejo Cloud de Central Mutuos. REGLA DE HIERRO: se alerta de inmediato a Gerardo si un archivo lleva más de 2 horas sin respaldo en la bóveda, y se verifica a diario la firma digital (MD5) de cada archivo byte a byte."},
    {"n": 54, "id": "ergonomia_gerencia", "titulo": "Ergonomía y velocidad en Gerencia Comercial",
     "ley": "La interfaz de Gerencia Comercial debe priorizar la ergonomía y la velocidad. Los filtros y botones de acción son las herramientas primarias de mando. REGLA DE DISEÑO: prohibidos los botones estándar HTML; todo con acabado Maserati (Dark Mode, cristal, oro 24K, sombras suaves y contrastes nítidos)."},
    {"n": 55, "id": "supercarpeta_management", "titulo": "Supercarpeta de Management",
     "ley": "La Supercarpeta de Management es la vista de control primario. Debe reflejar la disponibilidad física de los informes de títulos y tasaciones del mes corriente. REGLA DE DISEÑO: interfaz de alta gerencia, iconos metálicos, 20 clientes por pantalla y luz neón verde para informes recibidos en las últimas 24 horas."},
    {"n": 56, "id": "interfaz_fluida_seamless", "titulo": "Interfaz Fluida (Seamless UI)",
     "ley": "La experiencia visual del Maserati es fluida. El sistema debe evitar el uso de marcos, recuadros y divisiones visuales que dificulten la lectura continua de la cartera de clientes. REGLA DE DISEÑO: el foco es la información; el fondo es Dark Slate sólido y las letras e iconos definen la estructura, no las cajas. La separación se logra con espaciado y leves gradientes."},
    {"n": 57, "id": "huella_gestion_botones", "titulo": "Huella visible de gestión",
     "ley": "Toda acción de la Gerencia Comercial debe dejar una huella visible en la interfaz. Los botones deben informar el estado de la última gestión realizada para evitar duplicidad de trabajo. REGLA DE HIERRO: la fecha de cada reclamo se guarda en la carpeta del cliente (persistente a reinicios) y reclamar el mismo hito antes de 12 horas exige confirmación explícita."},
]

REGLAS_EFICIENCIA = [
    {"id": "economia_codigo", "ley": "Economía de Código: ediciones por parches (diff), jamás reescrituras completas de componentes."},
    {"id": "minimizacion_llamadas", "ley": "Minimización de Llamadas: agrupar operaciones en lotes paralelos; una sola verificación al final."},
    {"id": "bypass_pesado", "ley": "Bypass Pesado: servir desde caché lo costoso (UF, IMAP, OCR); refrescar en segundo plano."},
    {"id": "deteccion_bucle", "ley": "Detección de Bucle: al segundo intento fallido, cambiar de estrategia en vez de repetir."},
    {"id": "estimacion_previa", "ley": "Estimación Previa: antes de construir, calcular la ruta de menor costo de créditos según DashAI."},
]

VERSION = 19  # +#56 Seamless UI +#57 Huella de Gestión (botones dinámicos, bloqueo 12h)


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
            "version": VERSION, "reglas": REGLAS_ORO, "reglas_eficiencia": REGLAS_EFICIENCIA,
            "mando": "Gerardo Barrera",
            "master_pin_ref": "MASTER_PIN (0586)",
            "aprendizaje": {
                "fuente_primaria": "buzones IMAP operativos",
                "fuente_secundaria_solo_lectura": (doc or {}).get("aprendizaje", {}).get("fuente_secundaria_solo_lectura", ""),
                "nota": "Slot reservado para el segundo buzón de aprendizaje (solo lectura)."},
        }}, upsert=True)
    # BÓVEDA DE ALGORITMO (SOCKET): protegida, lista para la lógica de aprendizaje externo
    if not await db.config.find_one({"_key": "boveda_algoritmo_espejo"}):
        await db.config.update_one({"_key": "boveda_algoritmo_espejo"}, {"$set": {
            "estado": "socket_listo", "protegido": True, "logica_externa": None,
            "nota": "Recibe la lógica de aprendizaje externo solo por orden del administrador supremo."}},
            upsert=True)
    return await db.config.find_one({"_key": "constitucion_maestra"}, {"_id": 0})
