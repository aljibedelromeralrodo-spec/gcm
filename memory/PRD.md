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
