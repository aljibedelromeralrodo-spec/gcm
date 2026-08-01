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
