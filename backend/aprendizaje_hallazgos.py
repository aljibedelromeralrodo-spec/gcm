"""Hallazgos reales del flujo comercial — consolidación por categoría."""
import re

H = lambda titulo, detalle, tipo, fuente: {"titulo": titulo, "detalle": detalle, "tipo": tipo, "fuente": fuente}

# tipo: patron | regla | correccion | comportamiento
HALLAZGOS_BASE = {
    "correos": [
        H("Remitentes de solicitudes con confianza MUY ALTA",
          "Ecomac (@ecomac.cl): Ximena T. Gómez Pino es la más activa (~25 correos), junto a Sara/Gina Gómez, Marisela Ortiz y Carla Paz. Boetsch (@boetsch.cl): Rodrigo Salazar y Celinda Soria (envía bases de clientes en Excel). Maestra (@maestra.cl): Fabiola Pérez, María José Moreno, Karla Pavez. Internas: Yerile, Kimberlyn Aragón y Deisy Salazar.",
          "patron", "Análisis 400 correos Gmail + IMAP (30 días)"),
        H("Patrones de asunto por ejecutiva",
          "«SOLICITUD CREDITO MUTUO // NOMBRE RUT: X» (Kimberlyn/Yerile) · «EVALUAR ENTREGA INMEDIATA_NOMBRE_RUT» (Marisela, Ecomac) · «EVALUACION NOMBRE// ENTREGA X// CON|SIN SUBSIDIO» (Carla Paz) · «EVALUACION CLIENTE NOMBRE RUT: X CONDOMINIO Y» (Rodrigo Salazar) · «Liquidaciones de {cliente} rut {rut}… valor Xuf subsidio Xuf» (Ximena Gómez — trae todos los datos financieros en el asunto).",
          "patron", "APRENDIZAJE_CORREOS.md §2"),
        H("Palabras clave de Mesa verificadas en 32 veredictos reales",
          "✅ Aprobación: «Tenemos el agrado de informar que el crédito solicitado califica para un mutuo hipotecario endosable» + adjuntos Carta_Aprobacion y Simulador. ❌ Rechazo: «no cumple parámetros objetivos mínimos», «muy pasado en carga financiera», «ingresos de sociedad SPA no podemos considerar». ⚠️ Observación: «Favor revisar», «la aprobación está por UF X».",
          "patron", "aprobaciones@centralmutuos.cl (32 veredictos)"),
        H("Una aprobación puede anularse minutos después",
          "Caso real: Mesa envió «FAVOR CANCELAR EMAIL DE APROBACIÓN» minutos después de aprobar. Regla aprendida: nunca cerrar el estado del folder con el primer correo de aprobación — se implementó la ventana anti-cancelación de 30-60 minutos antes de notificar al ejecutivo.",
          "correccion", "Casos límite 120 días + mesa_verdad.py"),
        H("Correos duplicados por doble casilla IMAP",
          "Dos casillas reciben el mismo correo con UID distinto. Corrección aplicada: deduplicación SIEMPRE por huella de contenido, nunca por UID. Además, la Regla #68 bloquea cualquier envío idéntico dentro de 7 días.",
          "correccion", "Sesión anti-duplicados OCR"),
        H("Correos ilegibles o con documentos prometidos",
          "Si un correo de gestión trae archivos ilegibles (OCR < 50 caracteres en archivos relevantes) o el cuerpo promete documentos que no vienen adjuntos, el sistema lo marca para seguimiento en vez de clasificarlo en falso.",
          "regla", "Constitución dashai_eventos"),
    ],
    "ventas": [
        H("Comportamiento por ejecutiva: Ximena Gómez (Ecomac)",
          "Única ejecutiva cuya ficha trae el campo «Edad:» y todos los datos financieros (valor, subsidio, ahorro, crédito) directamente en el asunto. Además renegocia activamente: en el caso Eduar Araya (55 años, 2 rechazos) movió al cliente a una casa de menor valor al 80% de financiamiento.",
          "comportamiento", "Casos reales 120 días"),
        H("Comportamiento por ejecutiva: Carla Paz y Marisela Ortiz",
          "Carla Paz siempre declara en el asunto si la operación es CON o SIN SUBSIDIO y el tipo de entrega (futura/inmediata/próxima). Marisela usa el formato EVALUAR ENTREGA INMEDIATA con RUT y condominio — ambas permiten clasificación automática sin abrir el correo.",
          "comportamiento", "APRENDIZAJE_CORREOS.md §2"),
        H("La renta múltiple es titular + codeudor, nunca doble contrato",
          "En 120 días: CERO casos de un mismo RUT con dos empleadores. La renta múltiple se materializa como TITULAR + CODEUDOR/COMPLEMENTO (100 correos «codeudor», 55 «complementa»). Señales en asunto: «+AVAL SU PADRE», «y complemento», «(Aval {Titular})».",
          "patron", "Análisis 120 días"),
        H("Clientes independientes: Mesa aprueba con TOPE",
          "Tipo de cliente independiente (boletas de honorarios / F22): Mesa suele aprobar con tope de monto («por máximo posible de UF X»). Caso Valeska Díaz: 6 boletas + 4 renta → aprobada «máximo posible UF 1500». El documento que desbloquea la evaluación es el RESUMEN ANUAL SII, no las boletas sueltas.",
          "comportamiento", "Casos reales: Valeska Díaz, Catalina Aguilera, Nicolás Guevara"),
        H("Clientas con pre/postnatal no se descartan",
          "Patrón real: clienta con licencia maternal presenta liquidaciones bajas o en cero + subsidio maternal de Isapre/CCAF. La renta se acredita con liquidaciones previas + comprobantes de pago de licencia + certificado prenatal. Suele complementarse con aval (caso Javiera + Rodrigo Espinoza).",
          "patron", "Casos especiales 60 días"),
        H("Los ejecutivos de inmobiliarias responden mejor los martes por la mañana",
          "Nota operativa registrada por el equipo comercial y confirmada en el flujo de respuestas de correo.",
          "comportamiento", "Nota del flujo comercial"),
    ],
    "mora": [
        H("ORO-73 — Gestión de pago de mora autovalidada",
          "En la ficha del cliente moroso el ejecutivo dispone de 3 acciones: (1) enviar link/instrucciones de pago con el monto exacto y los datos oficiales MUTUARIAS Y LEASING LIMITADA (Mercado Pago, Cta Vista 1030937838) con referencia única MORA-XXXXXXXX; (2) subir comprobante de pago; (3) subir formulario manual de regularización.",
          "regla", "REGLAS_MAESTRAS.md · Regla de Oro #73"),
        H("Validación automática del comprobante de pago",
          "El comprobante se valida sin intervención humana: legibilidad OCR + palabras de pago + monto detectado ≥ 95% de la mora registrada en el CMF. Si valida, el sistema cierra la alerta solo, archiva en 04_cmf y marca cmf_morosidad.aclarada. Si falla, el ejecutivo recibe el motivo exacto del rechazo.",
          "regla", "REGLAS_MAESTRAS.md · Regla de Oro #73"),
        H("Formulario manual de regularización",
          "Se acepta como alternativa al comprobante: debe pasar OCR de legibilidad, contener términos de regularización (convenio, compromiso de pago, repactación) y la identidad del cliente (nombre o RUT presente en el documento).",
          "regla", "REGLAS_MAESTRAS.md · Regla de Oro #73"),
        H("La morosidad se detecta leyendo el informe CMF",
          "La auditoría del Contralor extrae la mora directamente del informe de deudas CMF (informe_deudas_{rut}.pdf) que llega en el primer correo de cada cliente, y levanta la alerta en la ficha antes de que la carpeta avance a mesa.",
          "patron", "Auditoría Pre-Mesa · Contralor"),
    ],
    "documentos": [
        H("Secuencia habitual de llegada de documentos por cliente",
          "Primer correo de la ejecutiva: 6-27 PDFs sueltos — 6 liquidaciones, certificado AFP, informe CMF, cédula + firmas basura (image001.png ×2). Variante frecuente: UN SOLO PDF combinado «{Nombre} EV.pdf» (10-14 páginas) → se aplica el divisor multi-documento. Luego llegan complementos «RE:/RV:» y papeles del codeudor.",
          "patron", "APRENDIZAJE_CORREOS.md §3"),
        H("Regla 67 — mínimo 3 categorías válidas para abrir carpeta",
          "Una carpeta solo se abre si el set trae al menos 3 categorías documentales válidas. El divisor multi-documento ayuda a cumplirla al separar el PDF combinado en sus partes.",
          "regla", "Reglas operativas confirmadas por el administrador"),
        H("Orden oficial del set a Mesa",
          "01_Cedula → 02_Liquidaciones/Impuesto_Renta → 03_AFP/Boletas → 04_CMF → 05_codeudor/contratos → 99_otros. Ningún documento se rechaza: los no clasificados van a 99_otros y SIEMPRE se incluyen al final del PDF combinado. Excepción única: Ley del RUT (RUT distinto → Buzón de Rescate).",
          "regla", "Reglas operativas confirmadas por el administrador"),
        H("Licencias médicas: extraer días trabajados y días licencia",
          "Toda liquidación se lee extrayendo «Días Trabajados» y «Días Licencia». Si licencia > 0 o trabajados < 30, el sueldo del mes está incompleto → se exige el PAGO DE LICENCIA (CCAF Los Andes/Los Héroes o Isapre) como respaldo de renta. Detectados por contenido: Yan Carmona, Gloria Bolados, Julieth Marin, Ignacio Pizarro.",
          "correccion", "Casos especiales 60 días + proc_rules"),
        H("Fotos de WhatsApp requieren corrección de rotación",
          "El OSD de Tesseract gira MAL las fotos comprimidas de WhatsApp. Corrección aplicada: probar rotaciones 0/90/180/270 y elegir por puntaje de palabras reales, más upscaling de imágenes de baja resolución.",
          "correccion", "aprendizajes_ocr_correos.md"),
        H("Papeles del codeudor van a subcarpeta separada",
          "Los documentos del aval/codeudor se guardan en 05_codeudor/{Nombre}/ con prefijo CODEUDOR_ y el PDF combinado del titular los EXCLUYE (merge aparte). La Ley del RUT rutea automáticamente cada archivo por RUT a su anexo.",
          "regla", "Casos reales: Jonathan Galleguillos, Silvia Meriño, Javiera Espinoza"),
    ],
    "criterios": [
        H("Financiamiento máximo: 79.50% exacto, jamás 80.01%",
          "El crédito nunca supera el 80% del precio. El LTV se calcula a 10 decimales y se TRUNCA a 2: si el ratio original es superior, el sistema lo baja a 79.50% exacto.",
          "regla", "Constitución dashai_eventos"),
        H("Crédito mínimo 2000 UF — solo aplica SIN subsidio",
          "Corrección aplicada al Contralor: la regla del mínimo de 2000 UF solo rige para operaciones sin subsidio. Las operaciones DS19/con subsidio quedan exentas de este mínimo.",
          "correccion", "Auditoría Pre-Mesa · corrección del administrador"),
        H("Carga financiera máxima 40% (alerta, no bloqueo)",
          "El Contralor audita la carga financiera contra el 40% de la renta. La auditoría es de solo alerta: la decisión operativa final recae exclusivamente en Mesa.",
          "regla", "Bóveda criterios_auditoria"),
        H("El efecto edad es INVISIBLE en los correos de Mesa",
          "Mesa nunca escribe «por edad» ni «acorta el plazo»: el efecto aparece solo como tope de monto («el crédito posible estaría por debajo de las UF 2000») o dentro del Simulador PDF adjunto. Regla derivada: si edad ≥ 55, marcar la carpeta edad_titular y alertar tope probable. Caso ancla: Eduar Araya Collao, 55 años.",
          "patron", "Casos límite 120 días"),
        H("Antigüedad laboral mínima: 6 meses a plazo fijo",
          "Rechazo textual real de Mesa: «necesitamos al menos 6 meses de empleabilidad a plazo fijo» (caso Yan Carmona, técnico de construcción). La antigüedad se lee de la fecha de ingreso en las liquidaciones.",
          "patron", "Frases nuevas de Mesa · proc_rules"),
        H("El valor UF es SIEMPRE el del SII del día",
          "Prohibido usar valores antiguos o por defecto en documentos. El sistema sincroniza la UF del SII (America/Santiago) automáticamente y el endpoint de paridad valida que producción tenga el mismo valor.",
          "regla", "Constitución dashai_eventos + /api/paridad"),
        H("Rechazo más frecuente: DIV/Renta supera el máximo",
          "El motivo de rechazo dominante detectado por el ciclo de aprendizaje es «DIV/Renta X supera máximo X», con 28-34 casos acumulados en ventanas de 60 días. Es el primer criterio que el ejecutivo debe pre-chequear antes de enviar a mesa.",
          "patron", "dashai_eventos · ciclo de aprendizaje"),
    ],
}

CATEGORIAS_META = [
    ("correos", "Correos", "fa-envelope-o"),
    ("ventas", "Ventas", "fa-line-chart"),
    ("mora", "Mora", "fa-exclamation-circle"),
    ("documentos", "Documentos", "fa-file-text-o"),
    ("criterios", "Criterios", "fa-balance-scale"),
]

_KW = [
    ("mora", re.compile(r"\bmora\b|moros", re.I)),
    ("correos", re.compile(r"correo|mail|imap|gmail|remitente|buz[oó]n|asunto|env[ií]o", re.I)),
    ("documentos", re.compile(r"documento|ocr|pdf|liquidaci|c[eé]dula|archivo|storage|firma|licencia", re.I)),
    ("criterios", re.compile(r"\buf\b|ltv|financiamiento|renta|div/|cr[eé]dito|rechazo|aprobaci|mesa|subsidio|edad|normativ", re.I)),
    ("ventas", re.compile(r"ejecutiv|broker|cliente|inmobiliaria|prospecto|lead|campa[ñn]a|gerencia|meta", re.I)),
]


def _categorizar(texto):
    for cat, rx in _KW:
        if rx.search(texto or ""):
            return cat
    return None


async def construir_hallazgos(db):
    data = {k: list(v) for k, v in HALLAZGOS_BASE.items()}

    vistos = set()
    reglas_oro = await db.dashai_eventos.find(
        {"motivo": {"$in": ["regla_oro", "manual"]}, "patron": {"$exists": True}}
    ).sort("fecha", -1).limit(120).to_list(120)
    for ev in reglas_oro:
        p = (ev.get("patron") or "").strip()
        if not p or len(p) < 40 or p in vistos or p.startswith("Aprendido: Rechazo por DIV"):
            continue
        vistos.add(p)
        cat = _categorizar(p)
        if not cat:
            continue
        tipo = "regla" if ev.get("motivo") == "regla_oro" else "patron"
        data[cat].append(H(p[:90] + ("…" if len(p) > 90 else ""), p, tipo,
                           f"Constitución dashai_eventos · {str(ev.get('fecha') or '')[:10]}"))

    correcciones = await db.patrones_aprendidos.find({}).sort("creado_en", -1).limit(20).to_list(20)
    for c in correcciones:
        cli, campo = c.get("cliente") or "cliente", c.get("campo") or "dato"
        data["correos"].append(H(
            f"Corrección aplicada: {campo} de {cli}",
            f"La extracción automática del campo «{campo}» falló para {cli} "
            f"(extraído: «{c.get('valor_extraido') or 'vacío'}») y fue corregida manualmente a "
            f"«{c.get('valor_correcto')}». El patrón quedó memorizado para futuras extracciones del mismo remitente.",
            "correccion", f"patrones_aprendidos · {str(c.get('creado_en') or '')[:10]}"))

    try:
        mora_total = await db.folders.count_documents({"cmf_morosidad": {"$exists": True}})
        mora_aclarada = await db.folders.count_documents({"cmf_morosidad.aclarada": True})
        if mora_total:
            data["mora"].append(H(
                f"Estado actual: {mora_total} carpeta(s) con mora detectada en CMF",
                f"De las {mora_total} carpetas con morosidad detectada por la lectura automática del informe CMF, "
                f"{mora_aclarada} han sido aclaradas mediante comprobante o formulario validado. "
                f"El resto mantiene la alerta activa en la ficha del cliente.",
                "comportamiento", "folders · lectura en vivo"))
    except Exception:
        pass

    categorias = []
    for key, nombre, icono in CATEGORIAS_META:
        items = data[key]
        categorias.append({"key": key, "nombre": nombre, "icono": icono,
                           "total": len(items), "hallazgos": items})
    return {"categorias": categorias, "total": sum(c["total"] for c in categorias)}
