# PRD — Central Mutuos / Predictor (clon de predic-credit.emergent.host)

## Problema original
Clon pixel-perfect de la app Central Mutuos (Predictor) con backend reconstruido:
evaluación de créditos, correo IMAP/SMTP (2 casillas reales), OCR de documentos,
manipulación de PDFs y reenvío automático de solicitudes/rechazos (Autocorreo).

Idioma del usuario: **Español** (responder siempre en español).

## Arquitectura
- Frontend: React (recuperado de source maps — NO alterar layout), Tailwind, axios. `/app/frontend`
- Backend: FastAPI + Motor/MongoDB. `/app/backend`
  - `server.py` — rutas API (~2280 líneas)
  - `email_service.py` — IMAP/SMTP (2 cuentas: MAIL_USER principal, MAIL2_USER secundaria)
  - `folders_service.py` — archivos de carpetas cliente (scan, categorías, merges, split, zip)
  - `pdf_service.py` — manipulación PDF / conversión a PDF
  - `ocr_service.py` — Tesseract + texto embebido
  - `ai_extract.py` — extracción con Emergent LLM Key (litellm/emergentintegrations)
- Almacenamiento archivos: `/app/backend/storage/{autocorreo,proc,clientes}`
- Carpetas cliente en disco: `storage/clientes/<nombre>/` con subcarpetas protocolo
  (01_cedula, 02_liquidaciones, 02_impuesto_renta, 03_afp, 03_boletas, 04_cmf, 99_otros, 00_combinados)

## Credenciales
- Login app: `administrador` / `141617575` (backup `admin` / `0586`)
- IMAP/SMTP: en `/app/backend/.env` (MAIL_USER, MAIL2_USER + app passwords)

## Implementado
> ⚠️ Desde 2026-08-02 las entradas nuevas van en `/app/memory/CHANGELOG.md`.

- 2026-08-01 (parte 8) — **Automatización 24/7 blindada + Resumen diario + Logo**:
  - **Ingesta de carpetas 24/7**: `_proc_auto_state` fuerza enabled=True siempre + resetea
    flag "running" colgado (>30 min). Todos los loops de fondo van dentro de
    `_task_blindada` (supervisor que loguea el error en db.system_log y reinicia el loop).
  - **BUG CRÍTICO RESUELTO**: al activar la ingesta 24/7 el backend se CONGELÓ (0% CPU,
    API muerta) porque `pdfs.convertir_a_pdf` corría síncrono en el event loop →
    ahora va en `asyncio.to_thread`. Blindaje extra: `socket.setdefaulttimeout(90)` en
    email_service (ningún IMAP/SMTP puede colgarse indefinidamente). Se requirió
    `supervisorctl restart backend`.
  - **Faltantes automáticos AL TIRO**: `_enviar_faltantes_auto` en proc_upload_drive —
    si tras procesar el correo faltan documentos y hay source_email, envía el correo de
    faltantes automáticamente (una vez por lista, guarda faltantes_auto_lista + alerta).
  - **Fecha tasación automática**: `_tasacion_fecha_loop` cada 60 min busca respuestas de
    Value Property para carpetas con tasación solicitada sin fecha.
  - **Resumen diario Martín**: GET /api/central/resumen-diario (faltantes, listas para
    mesa, tasación sin fecha, escritura sin confirmar). CentralChat lo muestra y LO LEE EN
    VOZ ALTA al abrir el chat la primera vez del día (localStorage martin_resumen_dia).
  - **Logo sidebar**: "Central Mutuos" Playfair dorado grande + "CON CRECES" espaciado con
    línea dorada (mismo estilo de los documentos enviados).
  - Verificado: ingesta creó carpetas nuevas sola (Vanesa, Lilian), resumen OK, saludo con
    voz OK, logo OK.

- 2026-08-01 (parte 7) — **Criterios mesa + Pedir faltantes + Volver + Voz Martín**:
  - Tarjeta: junto al % de aprobación, cuadro MESA (✅ APROBADA / ❌ RECHAZADA / Sin
    respuesta, cruzado con db.seguimiento por nombre) + contador "criterios N/M". Abajo,
    chips ✓/✗ por criterio (docs requeridos según tipo cliente, datos financieros,
    enviada a mesa) — `_criterios_folder` y `_mesa_respuesta_folder` en list_folders.
  - "📥 Solicitud recibida de: {source_email}" SIEMPRE visible en tarjeta (dato clave del
    vendedor/inmobiliaria/broker remitente, se preserva en merges).
  - **Pedir faltantes**: botón en tarjeta → modal (destinatario prefill = remitente
    original, lista editable, mensaje extra, preview) → POST
    /api/clientes/folders/{fid}/pedir-faltantes. Marca faltantes_pedidos_at (✓).
  - **Botón Volver** a Carpeta Clientes en Gastos, Aprobación y Set de Crédito
    (prop onNavigate desde App.js).
  - **Tasación**: adjuntos restringidos — SOLO carta de aprobación/oferta y voucher
    habilitados; el resto bloqueado (🔒 disabled).
  - **Voz de Martín**: /api/central/tts real con OpenAITextToSpeech (emergentintegrations,
    tts-1, voz onyx) → devuelve {audio: base64 mp3}; el frontend CentralChat ya lo consumía.
  - Testeado: curls (criterios Paula, pedir-faltantes a xgomez@ecomac.cl, TTS 47KB audio)
    + screenshots UI. Aprobación Cliente ya incluía carta + PDF ajustado del autocorreo
    (endpoint /aprobacion-cliente/archivos preexistente).

- 2026-08-01 (parte 6) — **Tasación v3 + Estudio v2 + Chat Martín REAL**:
  - Tasación: destinatarios SIEMPRE fijos (Value Property + Victoria; el mail de la
    inmobiliaria YA NO se agrega a destinatarios). Canal: inmobiliaria (plantilla) / broker
    (select que prellena contacto desde db.brokers) / vivienda usada (vendedor libre).
    Contacto para el tasador (nombre, teléfono, mail opcional) SIEMPRE va en el cuerpo.
    Voucher de pago: upload (usa folders/{fid}/upload-file → 99_otros), se adjunta y agrega
    "Adjunto voucher de pago tasación" al final. Intro editable + preview antes de enviar.
    Fecha de tasación de Value Property: POST /api/tasacion/detectar-fecha/{fid} (busca IMAP
    respuesta "coordinó para el X"), PATCH /api/tasacion/fecha/{fid} manual; se muestra 📅
    en el botón de la tarjeta.
  - Estudio de Título: destinatario = BROKER elegido (Gestión Hipotecaria es un broker más,
    ya no default) + Victoria SIEMPRE (default solo Victoria). Inmobiliaria con plantilla
    compartida (autofill + se guarda al enviar). Vivienda usada: vendedor libre nombre +
    mail + teléfono (opcional) en el cuerpo. Intro editable.
  - Brokers: PUT /api/brokers/{id} (editar nombre/contactos/emails); BrokersPanel con
    lápiz de edición + agregar/quitar; modo soloAdmin dentro del canal broker de tasación.
  - **Chat Martín ACTIVADO** (antes mocked): /api/central/chat usa emergentintegrations
    (gpt-5.4-mini, EMERGENT_LLM_KEY), respuestas cortas en español (máx 3 frases), contexto
    = todas las carpetas (docs, faltantes, % aprobación, estados tasación/estudio/escritura/
    mesa, codeudor) + memoria por session_id (últimos 6 turnos desde db.conversaciones).
    Probado: responde estado de Paula, recuerda contexto ("ella"), dice qué documento falta.

- 2026-08-01 (parte 5) — **Brokers + Vendedor libre + Firma de Escritura**:
  - **Brokers administrables** (`db.brokers`, GET/POST/DELETE /api/brokers), seed con emails
    reales encontrados en el correo: World Consultores (jgarrido@ y fdelacuadra@
    worldconsultores.com — Javier Garrido y Felipe de la Cuadra), Kiara Fernández
    (kiara.fernandez0312@gmail.com), Gestión Hipotecaria (contacto@hipotecariogestion.cl).
    Panel `BrokersPanel` en modales de Tasación y Estudio de Título: checkbox agrega/quita
    sus correos de los destinatarios + agregar/eliminar brokers manualmente.
  - **Vendedor libre**: campos nombre + mail en ambos modales; el mail se agrega al envío
    pero NO aparece en el texto del correo.
  - **Firma de Escritura** (botón rosado en tarjeta): notarías por ciudad (`db.notarias`,
    seed: La Serena — Av. Cristóbal Colón 352 Local 2 Edif. Studio Office; Santiago —
    Notaría Cristian Camilla, Paseo Ahumada 179 piso 7; Osorno — Notaría Sada, Manuel
    Antonio Matta 680) con CRUD + campo email de notaría. Modal: correo cliente, notaría,
    fecha (calendario), hora (10:00 por defecto / horario a sugerir). Correo entusiasta al
    cliente con botón "CONFIRMO QUE ASISTIRÉ" → página pública
    `/api/escritura/confirmar/{token}` que pregunta con quién asistirá (solo / mandatario /
    codeudor / ambos). Al confirmar: email automático a la notaría ("Cliente X RUT Y
    confirmó asistencia...") y a Victoria Vilches + Daniela Galindo + Rodrigo Ibáñez con
    día, hora y acompañantes. Botón de tarjeta muestra ✓ (enviada) / ✅ confirmada.
  - Testeado: seeds OK, preview OK, página de confirmación renderiza (token válido e
    inválido), broker checkbox suma correos, screenshots OK. NO se enviaron correos reales
    (la confirmación POST avisa a los correos reales del equipo).

- 2026-08-01 (parte 4) — **Tasación v2 + Estudio de Título funcional**:
  - Tasación: destinatarios EDITABLES (Victoria Vilches siempre se fuerza server-side),
    selector vivienda nueva (inmobiliaria) / usada. Inmobiliaria: input con datalist de
    plantillas guardadas (`db.tasacion_contactos`, GET /api/tasacion/contactos) — al enviar
    se guarda/actualiza el contacto (nombre+email) como plantilla y el email del contacto
    se agrega a los destinatarios. Vivienda usada: campos nombre + mail del vendedor
    (aparecen en el cuerpo). Saludo: "Estimados, se envía solicitud de tasación para X,
    con copia a la inmobiliaria Y y a Victoria Vilches". Adjuntos: SOLO la carta de
    aprobación va preseleccionada (regex carta|oferta|aprobaci en el nombre), nada más.
  - Estudio de Título: `POST /api/estudio-titulo/enviar` (preview/confirm),
    `GET /api/estudio-titulo/defaults`, `GET /api/estudio-titulo/log`. Destinatario por
    defecto **contacto@hipotecariogestion.cl** (detectado en el correo real) + Victoria
    SIEMPRE. Asunto "SOLICITUD ESTUDIO DE TITULOS // {nombre} {rut}". Vivienda nueva:
    solicitud formal sin listado. Vivienda usada: listado editable de 8 documentos estándar
    (derivado de los hilos reales del correo: escritura anterior/personería, inscripción
    dominio CBR, GP, no expropiación, contribuciones, gastos comunes, junta accionistas,
    tasación). Marca `estudio_titulo_solicitado_at` (botón muestra ✓).
  - Frontend: modal `estudio-modal` + tasación ampliado, botón Estudio de Título activado
    (teal). Verificado: curl previews OK + screenshots de ambos modales OK. NO se enviaron
    correos reales.

- 2026-08-01 (parte 3) — **Solicitud de Tasación funcional**:
  - Formulario armado según las solicitudes reales cruzadas con **contacto@valueproperty.cl**
    (OJO: el usuario dijo "volvetproperty" pero el dominio real en los correos es
    **valueproperty.cl**). Campos: tipo de tasación, dirección (obligatoria), rol de avalúo,
    valor aproximado UF (Value lo pide), vendedor, contacto para coordinar (nombre+teléfono),
    observaciones y adjuntos opcionales desde la carpeta del cliente (carta oferta/comprobante).
  - Backend: `POST /api/tasacion/enviar` (preview/confirm), `GET /api/tasacion/log`.
    Destinatarios FIJOS: contacto@valueproperty.cl + victoriavilches@centralmutuos.cl.
    Asunto: "SOLICITUD TASACION // {nombre} Rut: {rut}". Envía desde gerardo.ext (secundaria).
    Marca `tasacion_solicitada_at` en la carpeta (el botón muestra ✓).
  - Frontend: modal `tasacion-modal` en ClientesModule, botón activado en la tarjeta
    (naranja). Verificado con screenshot: preview OK, validación de dirección OK.
    NO se envió correo real a Value Property (para no molestar con pruebas).

- 2026-08-01 (esta sesión, parte 2) — **Botones de módulos en la tarjeta del cliente**:
  - Cada tarjeta de Carpeta Clientes ahora tiene una fila de botones (sin abrir la carpeta),
    en orden: Enviar Aprobación Cliente → GASTO OPERACIONAL (grande, dorado) →
    Firma Set de Crédito → Solicitud de Tasación (placeholder en blanco) →
    Solicitud de Estudio de Título (placeholder en blanco).
  - Mecanismo: `sessionStorage.cm_prefill_cliente` + `onNavigate` (App.js pasa
    `setActiveModule` a ClientesModule). Cada módulo (Gastos, Aprobación, SetCredito) lee el
    prefill al montar: Gastos/Aprobación resuelven email vía su `buscar-cliente` y
    autocompletan; SetCredito abre el set existente del cliente o precarga el formulario
    "Nuevo Set". Verificado con screenshots (los 3 módulos precargan a PAULA correctamente).
  - testids: `btn-aprobacion-{id}`, `btn-gastos-{id}`, `btn-setcredito-{id}`,
    `btn-tasacion-{id}`, `btn-estudio-titulo-{id}`, `modulos-carpeta-{id}`.

- 2026-08-01 (esta sesión) — **Codeudor + porcentaje visible en tarjeta**:
  - FIX P0: `GET /api/clientes/folders` daba 500 (`_prob_aprobacion_folder` no existía,
    quedó a medias en sesión anterior) → función creada (score por docs faltantes, CMF,
    monto, subsidio, tipo cliente, calibrada con mesa).
  - **Detección de codeudor en ingesta** (`proc_upload_drive`): keyword codeudor/aval en
    asunto+cuerpo + match de titular existente por nombre/RUT (`_buscar_titular_en_texto`).
    Correo del codeudor → archivos van a `05_codeudor/CODEUDOR_*` DENTRO de la carpeta del
    titular (no crea carpeta separada), enriquece `codeudor_nombre/rut` y
    `credit_request.codeudor` (aditivo), genera COMBINADO_CODEUDOR, y NUNCA pisa los datos
    financieros del titular. `Carpeta_<cliente>.pdf` ahora excluye 05_codeudor y COMBINADO_.
  - **UI tarjetas** (ClientesModule.js): % de aprobación EN GRANDE (36px, verde/amarillo/rojo,
    tooltip con factores, testid `prob-aprobacion-{id}`) + documentos faltantes por nombre
    ("⚠️ FALTA: Cédula…", testid `missing-docs-{id}`) sin abrir la carpeta.
  - **UI detalle**: sección "Subcarpeta Codeudor: {nombre}" (caja punteada violeta,
    testid `codeudor-subfolder`) agrupando los archivos 05_codeudor.
  - Testeado e2e con correo simulado de codeudora para titular real (ruteo, enriquecimiento,
    sin carpeta duplicada) + screenshots UI OK. Datos de prueba limpiados.

- 2026-07 (sesiones previas): frontend recuperado; motor de score; Autocorreo (pág 1 + reenvío
  con datos del ejecutivo); reenvío de Rechazos sin PDF; OCR+IA en Procesamiento Correo;
  validaciones de campos obligatorios antes de mesa; login actualizado.
- 2026-07-28 (esta sesión) — **FIX P0: adjuntos ahora se guardan en las carpetas de clientes**:
  - Nuevo `folders_service.py`: escaneo de disco, clasificación por categoría, merge por
    protocolo, merge selectivo, split de PDF empaquetado, ZIP.
  - Endpoints nuevos en `/api/clientes/...`: download/{ruta} (+inline), download-all (ZIP),
    upload-file (auto-clasifica subcarpeta + regenera combinado en background), delete-file,
    merge-pdfs, merge-protocol, split-bundled, save-attachment (baja adjunto real de Gmail por
    id `rol|uid`), save-all-attachments (job en background con polling — busca por nombre con
    X-GM-RAW), clasificacion (manual_override + reset), datos-financieros (GET/PATCH + OCR),
    envio-manual, send-email (preview/confirm, adjunta COMBINADO_PROTOCOLO), send-missing-docs.
  - `GET /api/clientes/emails` ahora devuelve id + adjuntos reales (fetch_recent_full).
  - `proc_upload_drive` guarda en subcarpetas protocolo y enriquece el folder doc
    (source_email, credit_request, datos_financieros desde los campos OCR).
  - UF: `?refresh=true` actualiza desde mindicador.cl; PATCH acepta `valor`.
  - Frontend: `saveAllAttachments` usa polling de job (evita timeout 60s del ingress).
  - Testing: 25/25 backend, frontend OK (`/app/test_reports/iteration_3.json`).

- 2026-07-28 (esta sesión, parte 2):
  - **Procesamiento automático 24/7**: loop en backend (config `proc_auto`: enabled/interval_min)
    que ingesta correos → OCR/IA → arma carpetas → genera alertas cuando una carpeta queda
    lista para mesa. Endpoints: GET/POST `/procesamiento/auto/{status,toggle,run-now}`.
    Alertas reales en `db.alertas` (+ marcar leída). Badge verde en topbar (App.js) y panel
    de control + lista de alertas en EmailProcessingModule.
  - **Columna "Reenviado a" en Autocorreo**: `ac_status` cruza el historial con la carpeta
    Enviados de Gmail (fetch_sent_headers, caché + background) y detecta si el usuario reenvió
    cada correo y a quién (solo envíos posteriores al procesamiento, hacia externos, o con Fwd:).
  - **Reporte diario 10:00 AM (hora Chile)**: loop `_daily_report_loop` envía cada día al
    destino el listado de solicitudes recibidas y enviadas a mesa (nombre, RUT, inmobiliaria,
    ejecutivo) del período 10:00 → 10:00. Config `reporte_diario` (enabled/hora/last_sent_date).
    Endpoints `/reportes/diario/{status,preview,toggle,enviar-ahora}`. Panel en AutocorreoModule.

- 2026-07-28 (parte 3):
  - **Módulo Gastos Operacionales**: plantilla profesional (buscar cliente por nombre/RUT
    autocompleta + email OCR, cuadro editable con autosuma, datos de pago editables, preview,
    envío desde gerardo.ext, plantilla por defecto guardable, historial). Endpoints
    `/api/gastos-operacionales/{defaults,buscar-cliente,enviar,log}`.
  - **UF siempre actualizada desde SII** (`_uf_desde_sii` parsea www.sii.cl, fallback
    mindicador.cl) con loop cada 6 hrs (`_uf_auto_loop`).
  - **Regla inviolable carta intacta**: `clasificar_documento` marca carta por filename
    primero; `_procesar_mesa` doble chequeo; rechazos con asunto "RECHAZO - {cliente}" +
    texto de mesa; log guarda `subject_original` para dedupe.
  - **Prueba E2E con 3 últimos clientes reales**: Roberto Duran, Claudia Zurita (Maestra),
    Franco Bahamondes — carpetas creadas con archivos vía OCR pipeline (script
    `/app/backend/scripts_test_e2e.py`).
  - **Módulo Envío Aprobación Cliente**: correo comercial de felicitaciones (asunto
    "¡Felicitaciones! Ha obtenido su crédito hipotecario", banner dorado, botón grande
    mailto "DESEO CONTINUAR CON EL PROCESO DE ESCRITURACIÓN"), detección automática de los
    PDFs del cliente (simulación ajustada + carta intacta, por carpeta/filename fuzzy/log
    del autocorreo), email del cliente auto-detectado (OCR) o manual, plantillas POR CLIENTE
    (db.aprobacion_templates) + default, historial. Endpoints `/api/aprobacion-cliente/*`.
  - `_extraer_nombre` mejorado (asuntos de mesa "Re: Nombre (…)") + migrados 164 logs con
    cliente "Mesa Clientes" → nombre real.
  - Testing: iteration_4.json (17/17 backend, frontend OK). Módulo Aprobación testeado
    manualmente (curl + screenshot E2E).

- 2026-07-28 (parte 4) — **App móvil para ejecutivos (PWA Share Target)**:
  - `public/manifest.json` con share_target (POST /share-receive multipart), iconos CM
    192/512 generados, `public/sw.js` (service worker que acumula archivos compartidos en
    IndexedDB `cm-share`, máx 20, expira 15 min) y registro del SW en index.html.
  - El frontend original ya traía `/share-target` (acumulación, elegir carpeta existente o
    crear nueva, titular/codeudor) y `/portal` (consulta de estado por RUT) — ahora con
    backend completo: `upload-file` acepta `route_to_codeudor` (guarda en 05_codeudor con
    prefijo CODEUDOR_ y genera COMBINADO_CODEUDOR automático, excluido del combinado del
    titular), y `GET /api/portal/consulta?rut=` real (carpetas + proc_queue + autocorreo_log
    → estado aprobado/rechazado/en proceso + simulaciones).
  - Tarjeta de instrucciones + "Copiar link" + "Enviar por WhatsApp" en el módulo WhatsApp.
  - E2E verificado: SW registrado, archivo compartido → share-target → carpeta de Franco
    Bahamondes ✓; portal consulta RUT 18.312.893-0 → "Aprobado" con proyecto ✓.
  - LIMITACIÓN: Web Share Target funciona en Android/Chrome con la app instalada;
    iOS/Safari no lo soporta (los ejecutivos con iPhone deben subir desde la app instalada
    con el selector de archivos del módulo Clientes).

## Backlog priorizado
- ✅ HECHO: Techo Hipotecario (motor inverso BTG/Ameris) 2026-08-10.
- 2026-07-28 (parte 5) — **Módulo Set de Crédito + Firma electrónica (migrup/eCert)**:
  - Correcciones pedidas: "Con Creces Asesorías" → "Central Mutuos - Con Creces" en todos los
    correos/PDFs; detección de aprobación cliente ahora solo pre-selecciona la simulación
    AJUSTADA (nombre con "ajustada") + carta de aprobación.
  - Exploración migrup.cl: es plataforma eCert Chile con API `ApiGatewayGrup`. Login por API
    funciona (`Usuarios/UsuariosPorRutyClave` con RutUsuario/DVUsuario/ClaveUsuario → JWT).
    Endpoints de firma: `ProcesoFirma/{CargaDocumentos,ProcesoFirmaDocumentos,FirmarTercero,
    ValidaTercero,...}`, `Dashboard/{ListadoDocumentosConFiltros,TraerSemaforo}`. Campos del
    firmante tercero: nombres, aPaterno, aMaterno, rut, email.
  - `backend/migrup_service.py`: login cacheado (JWT 20min), semaforo, listar_documentos,
    enviar_a_firmar_tercero (soporta firmar_todas_paginas). Credenciales en .env
    (MIGRUP_RUT/MIGRUP_CLAVE).
  - Módulo **Set de Crédito** (`SetCreditoModule.js`): sets por cliente, subir docs manual
    (seguros, solicitud_credito, declaracion_salud), ver/descargar/eliminar, estado migrup,
    "Combinar y enviar a firmar todo" (une todos los PDFs en uno y firma en TODAS las páginas
    = firmar todo de una vez), y firma individual por documento. Endpoints
    `/api/set-credito/*` y `/api/migrup/{status,documentos}`.
  - VERIFICADO: login migrup + semáforo (15 firmas terceros disp.) + listado docs +
    crear set + upload + combinar (4 págs) + UI. NO se probó un envío de firma real
    (firma en nombre del titular y correo a terceros).
  - ⚠️ PENDIENTE DE VALIDACIÓN: el payload de `ProcesoFirma/ProcesoFirmaDocumentos` es
    best-effort (no se capturó un envío exitoso real por ser sobre terceros reales). Requiere
    UNA prueba real con el usuario para confirmar/ajustar el formato exacto (posición de firma,
    nombres de campos). La API es interna de migrup y podría cambiar.

## Backlog priorizado
- ✅ HECHO: Techo Hipotecario (motor inverso BTG/Ameris) 2026-08-10.
- **P1**: Reporte 2 — cruce de solicitudes vs enviadas a mesa usando RUT real del OCR
  (pendiente, pedido del usuario en sesiones previas).
- **P2**: Integración real de WhatsApp (hoy mock).
- **P2**: Chat IA interno de Central Mutuos (hoy mock/deshabilitado).
- Refactor: dividir `server.py` en routers por dominio.
- Menor: color del badge "ENVIADO (manual)" es rojo (semántica confusa, el usuario lo pidió así — confirmar).

## Notas operativas
- Endpoints IMAP tardan 20-60s (ingress corta a 60s) — trabajos largos van en background
  (colección `save_jobs`, TTL 1 día).
- `POST /api/procesamiento/ingest-from-inbox` puede exceder 60s vía ingress (preexistente).
- No enviar correos reales en tests (usar previews `confirm:false`).
- Usar yarn, no npm. No tocar .env keys protegidas.

## Sesión Junio 2026 (fork) — Completado
- VERIFICADO en UI: ingesta de "Set de Crédito" desde correo evaluacionesmutuos@gmail.com
  (búsqueda por job async, import-from-email crea el set con Titular/Codeudor, combinar OK).
- **Reporte 2 (diario)**: cruce Solicitudes vs Enviadas a mesa ahora por **RUT y NOMBRE**
  contra la carpeta Enviados (además del flag `autocorreo_enviado`). `_datos_reporte_diario`
  devuelve `enviada_mesa`, `match` (app/rut/nombre) y `pendientes`. La tabla HTML del correo
  muestra columna "¿A mesa?" (✓ con método / ✗ Pendiente). Verificado con preview: 3/3 matched.
- **Contactos eCert (migrup)**: nuevo requisito — SIEMPRE crear el contacto del cliente antes
  de firmar. Implementado:
  - `migrup_service.py`: `listar_contactos`, `buscar_contacto_por_rut`, `crear_contacto`,
    `asegurar_contacto` (auto-crea el contacto dentro de `enviar_a_firmar_tercero`).
  - Endpoints: `GET/POST /api/migrup/contactos` (con validación email/email2, RUN, dedup por
    RUT) y `POST /api/migrup/ocr-cedula` (foto/PDF de cédula → OCR tesseract → IA extrae
    nombres/apellidos/RUN).
  - UI (`SetCreditoModule.js`): botón "Nuevo contacto eCert" + modal réplica del form de eCert
    (Nombres, Ap. Paterno, Ap. Materno, RUN, Correo, Confirmar correo) con botón
    "Capturar desde cédula (OCR)" y prefill desde el set abierto.
  - VERIFICADO contra API real: ListarContactos (27 contactos), CrearContacto (creado y luego
    eliminado contacto de prueba vía `Contacto/EliminarContacto {IdContacto}`), OCR cédula OK.
- ⚠️ Dependencias de sistema: `poppler-utils`, `tesseract-ocr`, `tesseract-ocr-spa` se
  reinstalaron en el fork (se pierden al forkear; reinstalar con apt si OCR devuelve vacío).

## Validación REAL de firma eCert — EXITOSA (Jun 2026)
- Payload REAL de `ProcesoFirma/ProcesoFirmaDocumentos` (extraído del bundle JS):
  `{usuarioId, comentario, nroDocumentos, texto: <clave certificado, "" si solo firman
  terceros>, documentos: [{doctoBase64, doctoNombre (MÁX 20 chars), modoFirma: 1,
  firmantes: [{usuarioId: null, contactoId: <contId eCert>, firmaOrden, firmaPagina,
  firmaPosX, firmaPosY}]}], enviarCopiaAMi, enviarCopiaAFirmantes, listaCorreosEnvioCopia}`.
  Éxito = `{codigo: 200}`. Límites: 10MB, 6 docs, nombre 20 chars.
- REGLAS CONFIRMADAS:
  - El firmante tercero SIEMPRE se referencia por `contactoId` → el contacto debe existir
    (auto-creado vía `asegurar_contacto`). REGLA DEL USUARIO: siempre agregar al cliente
    como contacto de terceros.
  - eCert NO permite crear contacto con el RUT del dueño ("el usuario no puede agregarse
    como contacto"). Si firmante == dueño, el código usa modo "mi firma" (usuarioId).
  - `texto` (clave del certificado) va VACÍO cuando solo firman terceros. Con la clave de
    login da error 147 "La clave no es correcta". Env opcional: MIGRUP_CLAVE_CERT.
- PRUEBA REAL: set combinado de Javier Perez (25 págs) enviado al contacto yerile barrera
  (delabarreraethan@gmail.com — correo del propio usuario). Resultado: codigo 200, doc
  "SET_JavierPerez_TEST" en estado "Por Firmar Otros", semáforo 15→14 firmas de terceros.
- `crear_contacto` ahora detecta errores de validación RFC7231 (`errors`/`status` 400).

## Envío real a Benjamín Rivera Chandía — OK (Jun 2026)
- Set combinado (25 págs) enviado vía endpoint real a contacto eCert existente
  (RUT 20912882-9, briverachandia@gmail.com). Doc "COMBINADO_SET_Javier" quedó
  "Por Firmar Otros". Firmas terceros 15→14.
- Endpoints eCert nuevos descubiertos: `ProcesoFirma/CancelarSolicitud`
  {idDocumento, idUsuario, mantenerDoc} (codigo 200, devuelve la firma al plan);
  `ProcesoFirma/EliminarDocumento` {idDocumento, texto, idUsuario} (falla si el doc
  tiene proceso pendiente).
- ⚠️ CUSTODIA eCert AL 98.8%: si un envío falla con "No queda espacio en custodia",
  hay que cancelar/eliminar docs antiguos en migrup o ampliar el plan.

## Estampas múltiples "Firma cliente" (Jun 2026)
- Requisito del usuario: la firma debe estamparse en TODAS las etiquetas: "Firma cliente",
  "Firma asegurado", "Firma cliente o representante legal", "Firma declarante" (decl. jurada
  estado civil), designación de apoderado, DPS, etc.
- Implementado: `pdf_service.posiciones_firma_cliente()` (pdfplumber) detecta las etiquetas
  "firma + (cliente|asegurad|declarante|apoderad|poderdante|mandante|representante|solicitante|
  titular|codeudor)" y devuelve página/x/top. `enviar_a_firmar_tercero(posiciones=...)` genera
  un firmante por estampa con firmaOrden incremental. Ambos endpoints de firma lo usan.
- En el set real de Javier Perez detectó 7 estampas (págs 6,7,10,14,20,23,25).
- DESCUBRIMIENTO DE COSTOS eCert: cada estampa (firmaOrden distinto) consume 1 firma de
  terceros (respuesta: firmasTerceroVaUtilizar=4 con 4 posiciones). Entradas duplicadas con
  el MISMO firmaOrden se deduplican (1 estampa, 1 firma).
- ⚠️ BLOQUEADO: "No quedan firmas prepagadas para enviar a terceros" (codigo 145). El envío
  de Benjamín usó la última adicional (18/18 usadas). El usuario debe comprar firmas en
  migrup.cl → AJUSTES. PENDIENTE validar tras la compra: ¿el cliente firma 1 vez y se
  estampan todas, o debe firmar N veces?
- pdfplumber agregado a requirements.txt.

## Solución "1 firma, constancia en todas partes" (Jun 2026)
- El usuario NO quiere pagar 1 firma por estampa. Solución implementada:
  - La estampa OFICIAL de eCert va en la PRIMERA etiqueta detectada (posiciones[:1]) →
    consume solo 1 firma de terceros.
  - En las demás etiquetas, `pdf_service.estampar_referencias_firma()` imprime ANTES del
    envío una marca: "Firmado con Firma Electrónica Avanzada / <NOMBRE> / FEA e-CertChile
    válida para todo el documento (Ley 19.799)" (reportlab overlay + pypdf merge).
  - Aplicado en ambos endpoints (enviar-firma y enviar-firma-completo). Respuesta incluye
    estampas y firmas_consumidas=1.
- Verificado localmente: 7 etiquetas en set Javier Perez (oficial pág 6, referencias en
  7,10,14,20,23,25); preview de la marca correcta sobre "Firma Cliente".
- PENDIENTE: envío real cuando el usuario compre firmas (eCert codigo 145: 0 prepagadas).

## Reglas de posiciones de firma refinadas por el usuario (Jun 2026)
- Cliente principal = DEUDOR (nunca firma en etiquetas de codeudor). Codeudor solo codeudor.
- `posiciones_firma_cliente(pdf_bytes, rol="titular"|"codeudor")` reescrita:
  titular = firma + (cliente|asegurad|declarante|deudor|titular|solicitante|representante|
  poderdante|mandante|apoderad), + líneas "nombre y firma", + línea con SOLO "firma"
  (apoderado notificante, PEP). Excluye "firma ejecutivo" y "firma codeudor".
- Set Javier Perez (titular): 10 etiquetas → págs 6 (asegurado Sura, ahí va la estampa
  OFICIAL), 7 cliente, 9 nombre y firma (origen de fondos), 10 declarante, 11 firma sola
  (apoderado), 14 cliente, 20 asegurado, 21 firma sola (PEP), 23 deudor, 25 deudor.
  Codeudor: págs 23 y 25 (quedan libres para el codeudor).
- Ejemplo v2 enviado por correo al usuario (2 cuentas) con estampa simulada pág 6 +
  marcas FEA en las otras 9. Verificado visualmente (pág 23 no pisa codeudor).
- Script de ejemplo: /tmp/enviar_ejemplo.py (regenerable).

## Orden de documentos a mesa + Set firmado separado (Ago 2026)
NOTA: App DEPLOYADA en producción (https://risk-assess-17.emergent.host). Cambios en preview
requieren re-deploy para llegar a producción.
1. ORDEN CARPETA → MESA (proc_upload_drive):
   - ORDEN_INDEPENDIENTE corregido: cedula → impuesto_renta → boleta_honorarios →
     certificado_smf (antes CMF iba 2do). Dependiente ya estaba bien: cedula → liquidacion →
     AFP → CMF. Extras siempre al final.
   - Causa raíz del desorden: OCR clasifica muchos docs como "otro". Se agregó respaldo por
     NOMBRE de archivo (fsvc.cat_de_texto → _cat_a_tipo) en el _rank. Verificado con caso
     real FRANCO BAHAMONDES (CARNET→LIQUIDACIONES→AFP→informe_deudas→extras).
   - ORDEN MANUAL: endpoint POST /api/procesamiento/queue/{qid}/ordenar-docs {filenames}
     guarda classification.documentos + flag docs_orden_manual y REGENERA Carpeta_<cliente>.pdf.
     upload-drive respeta el orden manual. UI: sección "Orden de los documentos" con flechas
     ↑/↓ en el DetailModal de Procesamiento (data-testid docs-orden-section).
2. SET FIRMADO (SetCreditoModule):
   - migrup.get_file(idDocumento) → Dashboard/GetFile (base64). listar_documentos ahora hace
     login() primero (bug uid=None tras hot-reload).
   - POST /set-credito/sets/{sid}/traer-firmado: busca en eCert el COMBINADO_SET_* Finalizado,
     descarga y SEPARA en los archivos originales (por conteo de páginas, mismo orden de
     _set_combinar) → carpeta firmados/ (FIRMADO_*.pdf + _FIRMADO_COMPLETO.pdf).
     VERIFICADO con el set real de Benjamín: 8 archivos, páginas calzan 1:1.
   - POST /set-credito/sets/{sid}/enviar-firmados {correos}: envía los FIRMADO_* adjuntos.
     Default: danielagalindo@centralmutuos.cl, victoriavilches@centralmutuos.cl (editable).
     VERIFICADO enviando a ethangerardobarr@gmail.com (8 adjuntos OK).
   - _set_archivos excluye firmados/ para no re-combinarlos. UI sección verde
     "Set firmado por el cliente" con input de correos + botón enviar.
   - Bug arreglado: correosEnvio no declarado (ReferenceError) + JSX duplicado previo.

## Rastro de firma en extractos + autocorreo con archivo madre (Ago 2026)
- HALLAZGO CONFIRMADO: al separar el PDF firmado, los extractos PIERDEN la firma
  criptográfica (AcroForm/Sig solo sobrevive en el archivo madre). Verificado con pypdf.
- Solución implementada:
  - `pdf_service.estampar_pie_rastro()`: pie en TODAS las páginas de cada extracto:
    "EXTRACTO DE DOCUMENTO FIRMADO ELECTRONICAMENTE - FEA e-CertChile (Ley 19.799)..." +
    archivo madre + Doc eCert ID + huella SHA-256 del madre.
  - `_set_separar_firmado(nombre, bytes, ecert_id)` aplica el rastro al separar.
  - `_enviar_firmados_interno` adjunta TAMBIÉN el archivo madre (*_FIRMADO_COMPLETO.pdf)
    y explica en el cuerpo cómo verificar (la FEA se valida en eCert con el madre).
- Autocorreo automático `_firmados_auto_loop()` (cada 10 min): detecta sets Finalizados en
  eCert → descarga → separa con rastro → envía a SETCRED_ENVIO_DEFAULT (Daniela Galindo +
  Victoria Vilches) sin intervención. Solo sets sin firmado_recibido_en (sin duplicados).
- VERIFICADO: re-split del set Javier Perez con rastro (render OK) + envío real con 9
  adjuntos (8 extractos + madre) a ethangerardobarr@gmail.com.
- ⚠️ poppler-utils se volvió a desinstalar del entorno (2ª vez); reinstalar con apt si
  pdf2image falla. PENDIENTE re-deploy para llevar todo esto a producción.

## Rearmado de carpetas + regla anti-vacías + % aprobación (Ago 2026)
1. CARPETAS REARMADAS: backup de carpetas antiguas en storage/clientes_backup_20260801_1614,
   db.folders limpiada, y se armaron SOLO las de hoy (ERNESTO LEONARDO DÍAZ SILVA y PAULA
   MACARENA RIVERA ROMERO) con orden de protocolo + subcarpetas 01_cedula...04_cmf/99_otros.
2. REGLA DEL USUARIO (inviolable): NUNCA crear carpeta sin adjuntos descargados/clasificados.
   proc_upload_drive ahora responde 409 si no hay docs físicos; además deduplica documentos
   por filename (antes copiaba/mergeaba duplicados).
3. Patrón CMF ampliado en folders_service: infnomat|informe_de_deuda|informe_deudas.
4. % POSIBILIDAD DE APROBACIÓN calibrado con mesa:
   - `_stats_mesa()`: base = aprobaciones/(apro+rech) de db.seguimiento (auto-recalibra con
     cada respuesta real de mesa; hoy 2/0 → 100%).
   - `_prob_aprobacion(item, stats)`: ajustes por docs clave faltantes (-8% c/u, según
     dependiente/independiente), falta CMF (-5%), monto (≤2000UF +4% / >4000UF -8%),
     subsidio (+5%), independiente (-5%). Clamp 5-98%.
   - Expuesto en GET /procesamiento/queue y /{qid} como prob_aprobacion {porcentaje, factores}.
   - UI: columna "% Aprobación" con badge de color (verde ≥75, amarillo ≥50, rojo <50) +
     desglose de factores en el DetailModal (data-testid prob-aprobacion-detalle).
   - VERIFICADO: curl + screenshot (7 badges, detalle 92% Paula).

## Enriquecimiento de carpetas multi-correo (Ago 2026)
- REGLA: documentos de la MISMA persona llegados en DISTINTOS correos van a la MISMA carpeta.
- `_buscar_carpeta_existente(cliente, rut)`: matchea por RUT normalizado o por nombre
  similar (tokens del nombre corto contenidos en el largo, ej "Ernesto Diaz Silva" ⊆
  "ERNESTO LEONARDO DÍAZ SILVA").
- `_regen_carpeta_cliente(cliente, orden_manual)`: reconstruye Carpeta_<cliente>.pdf con
  TODO lo acumulado de todos los correos, orden por prefijos de subcarpeta (01_cedula →
  02_* → 03_* → 04_cmf → 99_otros); el orden manual (ordenar-docs) va primero.
- Subcarpeta ahora se asigna con `_tipo_efectivo` (fallback por nombre de archivo), y al
  reubicar un archivo se elimina su copia vieja de otra subcarpeta (sin duplicados).
- db.folders "archivos" acumula (union) en vez de sobrescribir.
- VERIFICADO con datos reales de hoy: 2 correos de Ernesto Díaz → 1 sola carpeta,
  Carpeta combinada 12 págs en orden cédula→liquidaciones→AFP→CMF→otros, sin duplicados.

## Datos financieros por orden de tiempo (Ago 2026)
- REGLA: el correo MÁS RECIENTE manda en datos financieros de la carpeta.
- db.folders ahora guarda `datos_financieros_fecha` (date_iso del correo vigente).
- En proc_upload_drive: si date_iso del correo >= fecha vigente → sobrescribe
  datos_financieros (y credit_request salvo manual_override) y actualiza la fecha.
  Si es un correo antiguo → solo completa campos vacíos, nunca pisa lo más nuevo.
- VERIFICADO con los 2 correos reales de Ernesto (14:13 y 14:17): procesando
  nuevo→viejo, la fecha vigente quedó en 14:17 y los datos no fueron pisados.

## Correos formales + Vouchers en mini-programa de compartir (Jun 2026)
- `_marca_wrap(inner, subtitulo)` en server.py: wrapper HTML formal (header navy #1a1f2e,
  dorado #d4af37, "Central Mutuos / CON CRECES ASESORÍAS", footer confidencialidad).
  Aplicado a: _tasacion_html, _estudio_html, _escritura_html y pedir-faltantes.
  (Gastos Operacionales y Aprobación ya tenían su propio diseño formal, sin cambios.)
- ShareTargetPage (/share-target): selector "¿Qué estás enviando?" con 3 destinos:
  1. Documentos crédito (flujo existente: carpeta nueva o existente, titular/codeudor)
  2. Voucher Tasación → 99_otros/VOUCHER_TASACION_*
  3. Voucher Gasto Op. → 99_otros/VOUCHER_GASTO_OP_*
  Los vouchers exigen carpeta existente, NO regeneran COMBINADO y se registran en
  db.folders.vouchers [{tipo, archivo, subido_en}].
- Backend: upload-file acepta Form "categoria" (voucher_tasacion|voucher_gasto_operacional).
- VERIFICADO: curl (ambas categorías + previews de los 4 correos con marca) y screenshot
  del selector con destino Voucher Tasación activo.
- NOTA: hot-reload del backend puede colgarse en shutdown (loops de polling); usar
  `sudo supervisorctl restart backend` tras editar server.py.

## Reparos de Estudio de Título + Cobro de Tasación (Jun 2026)
### Reparos Estudio de Título
- Loop `_estudio_reparos_loop` (45 min): busca respuestas del abogado en el hilo IMAP
  (por asunto "SOLICITUD ESTUDIO DE TITULOS // {nombre}"), clasifica con IA (gpt-5.4-mini):
  tipo reparos → extrae ítems, los reenvía AUTOMÁTICAMENTE al vendedor (CC Victoria) y
  aprende el correo del abogado (db.config estudio_abogado_email);
  tipo satisfecho → marca todo resuelto y avisa a admin + vendedor + Victoria
  ("se procede con el estudio de título en tiempo y forma").
- Recordatorio ÚNICO a los 5 días en el mismo hilo (In-Reply-To) — SOLO vivienda usada.
- UI: botón "Reparos E. Título" en card (badge pendientes) + modal con checkbox
  "Reparo satisfecho" por ítem y botón "Declaro que han quedado satisfechos todos los reparos"
  (habilitado solo cuando todos marcados). Endpoints: GET/scan/PATCH item/POST declarar
  bajo /api/estudio-titulo/reparos/{fid}.
- estudio_enviar ahora persiste en folder: estudio_titulo_subject, tipo_vivienda, vendedor.
- mail.buscar_hilo_por_asunto + send_mail(cc=, headers=) nuevos en email_service.py.
### Cobro de Tasación (SOLO vivienda usada) — 4,5 UF
- REGLA INVIOLABLE: el correo de cobro de tasación se envía SOLO al solicitante, SIN COPIA A NADIE JAMÁS.
- Cuenta Recaudadora (gastos op + cobro tasación): MUTUARIAS Y LEASING LIMITADA ·
  RUT 77.771.552-6 · Mercado Pago · Cuenta Vista · 1030937838. Email gastos dice "Cuenta Recaudadora".
- Loop `_cobro_tasacion_loop` (30 min): detecta correos entrantes con "tasacion" en asunto,
  excluye valueproperty/centralmutuos, IA confirma que es SOLICITUD de tasación de vivienda
  USADA (no inmobiliaria, no coordinación) → responde en el hilo pidiendo datos + voucher
  4,5 UF (equivalente CLP con UF del día). Solo procesa correos posteriores a la activación
  (db.config cobro_tasacion.since). Registro en db.tasacion_cobros.
- UI Gastos Operacionales: sección "Cobro de Tasación — Vivienda Usada" con envío manual,
  "Buscar solicitudes" y botón "Tasación pagada" por cobro.
- VERIFICADO: curl (previews con marca/cuenta/monto $183.802, GET/PATCH/scan reparos,
  scan cobros), IA clasificadores (reparos/satisfecho y solicitud usada vs coordinación
  vs inmobiliaria) y screenshots (modal reparos + sección cobros).

## Recordatorio Faltantes + Auto-Pago Tasación + Panel Dashboard (Jun 2026)
- `_faltantes_recordatorio_loop` (1h): a los 3 días de pedido de faltantes, si siguen
  faltando docs, envía UN recordatorio formal (_marca_wrap) al source_email y registra
  alerta. Se resetea (\$unset faltantes_recordatorio_at) al volver a pedir faltantes
  (manual y automático). Email auto-faltantes ahora también usa _marca_wrap.
- `_detectar_pagos_tasacion` (dentro de _cobro_tasacion_loop y del scan): revisa el hilo
  del cobro (mismo remitente, posterior a respondido_at), heurística por nombre de adjunto
  (voucher/comprobante/transferencia/pago) + IA confirma pago → marca pagado
  automáticamente (pagado_origen "auto") + alerta en db.alertas. buscar_hilo_por_asunto
  ahora devuelve nombres de adjuntos.
- GET cobros-tasacion incluye `resumen` mensual {enviadas, pagadas, pendientes, montos CLP}.
- Dashboard: panel "Cobros de Tasación — Vivienda Usada" (testid panel-cobros-tasacion)
  con 3 estadísticas. Solo se muestra si hay resumen.
- PENDIENTE (bloqueado por usuario): prueba en vivo Autocorreo eCert — requiere recargar
  firmas prepagadas en migrup.cl.
- VERIFICADO: curl resumen, dry-run query recordatorio, screenshot panel con datos de
  ejemplo (luego eliminados).
- LECCIÓN: algunos search_replace reportan éxito pero no persisten (3 casos en esta
  sesión). SIEMPRE re-grep después de editar archivos frontend grandes.

## Ajustes reglas de envío (Jun 2026)
- REGLA INVIOLABLE ampliada: gastos operacionales Y cobro de tasación se envían SOLO al
  cliente/solicitante, SIN COPIA A NADIE JAMÁS, y el gasto operacional es SIEMPRE manual
  (verificado: gastos_enviar no lleva CC y solo se dispara por botón).
- Recordatorio de documentos faltantes ahora es RECURRENTE: se reenvía CADA 3 días
  mientras sigan faltando documentos (faltantes_recordatorio_at = último envío).
- Al detectar pago de tasación automáticamente, además de marcar el botón "Tasación
  pagada" y la alerta, se envía CORREO DE AVISO al administrador (cuenta principal)
  con cliente, solicitante y monto.
- Prueba eCert en vivo: usuario confirmó que la hará después (sin firmas prepagadas aún).

## Tope de recordatorios (Jun 2026)
- Recordatorios de documentos faltantes: MÁXIMO 2 (cada 3 días). Al llegar al 2°,
  correo de aviso al administrador ("requiere gestión directa") y se detienen.
- Contador faltantes_recordatorio_count se resetea al volver a pedir faltantes
  (manual y automático). Alertas muestran "Recordatorio n/2".

## Resumen Semanal Martín + Historial Mensual de Pagos (Jun 2026)
- `_resumen_semanal_loop`: cada lunes ≥08:00 (hora Chile), envía por correo al admin
  (cuenta principal) el "Resumen Semanal de Martín" con: cobros de tasación del mes
  (enviados/pagados/pendientes + montos CLP) y carpetas que necesitan acción
  (faltantes, mesa, tasación sin fecha, firma sin confirmar, reparos pendientes).
  Dedupe por semana ISO (db.config resumen_semanal.last_sent_week).
  Endpoint manual: POST /central/resumen-semanal/enviar (confirm:false = preview).
- `_acciones_pendientes()`: helper compartido con resumen-diario; ahora incluye
  reparos de estudio de título pendientes.
- GET /gastos-operacionales/cobros-tasacion/historial: tasaciones PAGADAS agrupadas
  por mes (cantidad, total UF/CLP, detalle con cliente/fecha/origen auto-manual).
- UI Gastos Operacionales: tarjeta "Historial Mensual — Tasaciones Pagadas"
  (testid historial-pagos-card). Se refresca al marcar/desmarcar pagado.
- DECISIONES USUARIO: WhatsApp NO — todo por correo oficial. Prueba eCert en la semana.
- VERIFICADO: preview resumen semanal (marca+cobros+acciones), historial endpoint,
  screenshot UI con registro demo (luego eliminado).

## Blindaje + Testing completo (Jun 2026)
- 10 loops de fondo blindados con _task_blindada (auto-reinicio + registro en db.system_log).
- Testing agent iteración 6: 14/14 backend PASSED + frontend E2E 100% (reparos modal,
  panel dashboard, cobros gastos, uploads voucher, previews con marca, regla sin-CC).
- Reporte: /app/test_reports/iteration_6.json · Tests: /app/tests/test_reparos_cobros_marca.py
- NOTA testing: NO poner tests en /app/backend/tests (reload loop); usar /app/tests.

## Marca en correo de gastos operacionales (Jun 2026)
- REGLA: el correo de costo de gasto operacional va SOLO con "Central Mutuos"
  (sin "Con Creces" en header ni firma). El resto de los correos mantiene la marca
  completa Central Mutuos + Con Creces. VERIFICADO por curl (preview sin 'Con Creces').

## CC en Estudio de Título (Jun 2026)
- Modal Solicitud de Estudio de Título: campo "Con copia (CC)" (testid estudio-cc) con
  chips rápidos: + Cliente/Solicitante (source_email) y + cada correo de brokers
  (Gestión Hipotecaria, Kiara Fernández, World Consultores...).
- Backend estudio_enviar: acepta payload.cc (string o lista), dedupe y excluye correos
  ya en destinatarios; se envía con Cc y se persiste en folder.estudio_titulo_cc.
- _reparos_cc(doc, excluir): Victoria + estudio_titulo_cc → aplicado a los 3 correos del
  hilo de reparos (reenvío al vendedor, recordatorio al abogado, resolución) para que
  todos (vendedor, nosotros, oficina abogado, cliente) sigan informados del proceso.
- VERIFICADO: preview curl (cc parseado, Victoria excluida) + screenshot del modal.

## Plantillas manuales + activación detección (Jun 2026)
- CRUD /api/plantillas (tipo estudio|gastos): guardar/aplicar/eliminar SOLO manual.
- Estudio de Título: fila "📋 Plantillas" en modal (select aplicar, guardar, eliminar).
  Guarda destinatarios, cc, tipo_vivienda, intro, docs_texto, observaciones.
- Gastos Op: "Guardar como plantilla" (con nombre) + "Guardar como predeterminada"
  (PATCH defaults, función renombrada guardarPredeterminada para evitar duplicado
  que causó SyntaxError reportado por el usuario — FIXED).
- Detección de solicitudes de tasación ACTIVA desde 2026-08-01T19:52 (config
  cobro_tasacion.since). Usuario hará redeploy.

## REGLA INVIOLABLE armado de carpetas (Jun 2026) — caso LILIAN NAVARRO
- Solo se arma carpeta NUEVA desde un correo si: (1) el texto dice "solicitud de
  financiamiento" o "solicitud de crédito" (debe traer monto, con/sin subsidio, fecha
  entrega) y (2) adjunta MÍNIMO 3 documentos básicos (dependiente: liquidaciones/AFP/
  CMF/cédula/cotización inmobiliaria; independiente: cédula/boletas/imp.renta/CMF).
- Si no cumple → NO se arma carpeta y NO se piden faltantes. Item queda status
  "descartado" en proc_queue (con motivo) + alerta "solicitud_descartada" en Dashboard.
- Implementado en _regla_solicitud_ok() + gate HTTP 412 en proc_upload_drive (solo
  aplica a carpetas NUEVAS: correos de codeudor o que enriquecen carpetas existentes
  pasan igual, para no romper el flujo de docs faltantes).
- VERIFICADO: el correo real de Navarro ahora sería descartado (sin frase, docs 'otro');
  casos simulados OK.

## Reporte Diario de Correos 10:00 (Jun 2026)
- _reporte_correos_loop: todos los días a las 10:00 (hora Chile), correo al admin con
  (últimas 24h): correos de gestión recibidos, carpetas enviadas a mesa
  (last_email_sent_at), NO enviadas por documentos faltantes (detalle), correos
  descartados por la regla inviolable (motivo) y correos sin leer/pendientes de revisión.
  Dedupe por día (db.config reporte_correos.last_sent_day).
- Endpoint manual: POST /central/reporte-correos/enviar (sin confirm = preview).
- VERIFICADO: preview curl con las 5 secciones y marca formal.
- NOTA: app ya desplegada en producción (https://risk-assess-17.emergent.host);
  cambios nuevos requieren redeploy del usuario.

## Clave 0586 + PDF simulación sin "ajustado" (Jun 2026)
- Forzar armado de carpeta (saltando regla inviolable): SOLO con clave 0586.
  Backend: proc_upload_drive(force, clave) → 403 si clave incorrecta, 412 si regla
  no se cumple sin force. Frontend: prompt de clave al recibir 412 + botón
  "Armar carpeta manualmente" en detalle de items descartados (con motivo visible).
- PDF de simulación procesado por autocorreo ahora se llama {nombre}_CM.pdf
  (antes _ajustada.pdf — el usuario prohibió la palabra "ajustado" en el nombre).
  _tipo_pdf_aprobacion detecta _cm.pdf y mantiene compatibilidad con archivos legados.
- ACLARADO al usuario: carpetas Franco Bahamondes / Claudia Zurita se armaron en
  PRODUCCIÓN (sin la regla aún) — requiere redeploy. En preview el correo de
  Bahamondes es descartado (412 verificado). Carpeta de prueba creada por error
  durante testing fue eliminada y el item devuelto a "clasificado".
- INCIDENTE: server.py quedó con bloque duplicado al final (SyntaxError) — corregido
  con sed. Verificar SIEMPRE ast.parse tras ediciones múltiples.

## Reevaluación retroactiva de carpetas (Jun 2026)
- POST /procesamiento/reevaluar {clave: 0586, desde: iso}: revisa proc_queue desde la
  fecha, arma carpetas que cumplen la regla inviolable y BORRA (doc + disco) las que no
  (solo carpetas creadas dentro de la ventana). Items no conformes → status descartado.
- Botón "🧹 Reevaluar (regla)" en Procesamiento (pide clave; desde = viernes anterior).
- EJECUTADO en preview (desde 2026-07-31): 6 correos revisados, 0 creadas,
  4 BORRADAS (Lilian Navarro, Paula Rivera, Ernesto Díaz, Vanesa Ocampo — sin frase
  "solicitud de crédito/financiamiento"). NOTA: la carpeta de Ernesto tenía los datos
  de prueba de reparos (eliminados con ella).
- HALLAZGO para el usuario: los brokers escriben "EVALUACION ..." en vez de
  "solicitud de crédito", por eso 0 carpetas calificaron. Si esto es muy estricto,
  el usuario debe decidir si amplía la frase permitida.
- En producción: correr el botón Reevaluar después del redeploy.

## Regla ampliada con "evaluación" + montos (Jun 2026)
- _regla_solicitud_ok ahora exige: (1) frase evaluación / solicito evaluación /
  solicitud|solicito financiamiento|crédito, (2) montos presentes (_MONTO_RE:
  monto | N uf | $N), (3) mínimo 3 documentos básicos. Si falta cualquiera → 412.
- VERIFICADO: Bahamondes pasa frase+monto pero se rechaza por 1 doc básico (412);
  reevaluación re-ejecutada desde 31-07: 0 creadas, Vanesa Ocampo descartada por
  solo 2 docs básicos, resto sin frase. Sistema consistente con la orden del usuario.

## Armado retroactivo + Informe Final (Jun 2026)
- Por orden explícita del usuario: se armaron las 4 carpetas de los correos del período
  viernes 31-07 → hoy usando force + clave 0586 (ninguna cumplía la regla completa):
  ERNESTO DÍAZ (7 arch), LILIAN NAVARRO (3), PAULA RIVERA (12), VANESA OCAMPO (15).
- Informe final HTML formal enviado al correo del admin con detalle por carpeta:
  archivos descargados + estado de cumplimiento de la regla.
- La regla inviolable sigue activa para correos NUEVOS (frase evaluación/solicitud +
  montos + 3 docs básicos; forzar solo con clave 0586).

## Cuentas separadas (Jun 2026)
- GASTOS OPERACIONALES → Gerardo Nicolás Barrera Pérez · RUT 14.161.757-5 ·
  Mercado Pago · Cuenta Vista · 1014622077 · ethangerardobarr@gmail.com
  (defaults código + DB + campo Correo agregado al editor y al correo HTML).
- COBRO DE TASACIÓN (4,5 UF) → constante TASACION_CUENTA: MUTUARIAS Y LEASING
  LIMITADA · RUT 77.771.552-6 · Mercado Pago · Cuenta Vista · 1030937838
  (ya NO usa los defaults de gastos).
- VERIFICADO por curl: gastos muestra cuenta Gerardo+correo, tasación muestra
  MUTUARIAS; sin cruces entre cuentas.

## Forzar Carpeta Manual (Jun 2026)
- POST /clientes/folders/forzar {nombre, clave 0586}: busca en proc_queue todos los
  correos del cliente (subject/classification/body), procesa cada uno con force
  (archivos + datos financieros + campos) y si no hay correos crea carpeta vacía.
- Botón "⚡ Forzar Carpeta" (btn-forzar-folder) junto a "Nueva Carpeta" en
  Carpeta Clientes: pide nombre + clave, muestra resumen de correos/archivos.
- VERIFICADO: clave mala 403; con clave armó Franco Bahamondes (1 correo, 8 archivos).

## Importar desde Correo — motor transversal (2026-06)
- GET /api/correos/buscar?q= (sugerencias IMAP en vivo, cabeceras con message_id).
- POST /api/correos/importar {destino: carpeta|estudio_titulo|set_credito, destino_id, nombre, message_ids}
  con dedupe por nombre de archivo; estudio_titulo va SIEMPRE a 07_estudio_titulo.
- Componente reutilizable: /app/frontend/src/components/ImportarCorreo.js
  (testids: importar-correo-btn-{destino}, -q, -item-{i}, -ejecutar, -msg).
- Integrado en: SetCreditoModule, ClientesModule (detalle: 2 botones), GastosOperacionalesModule, AprobacionClienteModule.
- Testing iteración 15: backend 7/7, frontend 5/5 PASS. Listado de correos con letra grande (pedido del usuario).

## Sesión 2026-08-03 (iteración 16 — 100% PASS, ver CHANGELOG.md para detalle)
- Regla de carpetas flexible (sin monto obligatorio, docs por nombre de archivo) + fix extracción de nombre (Melisa Rivera OK).
- Seguimiento del último mes (31 días) con ejecutivo externo real + export Excel.
- Pagos en Gastos Operacionales (pagado/saldo/estado + detección de transferencias).
- Log SMTP completo en db.correos_smtp_log.
- Autocorreos de aprobación SOLO TEXTO ahora procesados; carpetas asegurada con carta+simulación.
- BLINDAJE INVIOLABLE en send_mail: ninguna simulación sale con >1 página (bypass solo con clave 0586).
- Reportes internos auto-enviados desde Gmail principal (fin de bloqueos "Se bloqueó tu mensaje").

## Backlog priorizado
- ✅ HECHO: Techo Hipotecario (motor inverso BTG/Ameris) 2026-08-10.
- P0: Confirmar con usuario el RUT correcto de DILIMAR CEDEÑO (carpeta dice 67422911, CMF dice 26.545.507-7).
- P1: Alertas WhatsApp VIP a Gerardo cuando viabilidad >= 75%.
- P1: Informe Semanal Ventas (José Martín, lunes).
- P2: Panel del Búnker en Salud (archivos GridFS + último respaldo).
- P2: Botón "Reenviar a MESA" para hallazgos PERDIDA en Contraloría.
- P1: Panel de "Correos Descartados" con rescate a 1 clic (crear carpeta desde correo descartado).
- P1: Vista/alerta de errores SMTP en la UI (ya existe GET /api/correos/smtp-log?solo_errores=true).
- P2: Afinar detección automática de transferencias cuando el usuario comparta un comprobante bancario real.
- P2: Modularizar server.py (~8900 líneas; extracción/aprendizaje ya movidos a ai_extract.py 2026-08-04).
- Pendiente usuario: prueba en vivo de Auto-correo con saldo eCert.
