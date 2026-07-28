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
