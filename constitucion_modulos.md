# 📜 CONSTITUCIÓN DE MÓDULOS — Central Mutuos

> **REGLA INAMOVIBLE**: antes de modificar cualquier módulo listado aquí, el agente
> DEBE mostrar el impacto del cambio (qué archivos toca, qué flujos podrían romperse)
> y **esperar la aprobación explícita del Administrador**. Sin aprobación, no se toca.
>
> Antes de cada redespliegue: ejecutar `bash /app/scripts/pre_deploy_check.sh`.
> Si alguna prueba falla → alerta clara y **NO subir a producción**.

## Módulos estables y funcionando (26-08-2026)

| # | Módulo | Archivos clave | Estado |
|---|--------|----------------|--------|
| 1 | Correos salientes — Cuenta Única (gerardo.ext@centralmutuos.cl) | `backend/email_service.py` | 🟢 CRÍTICO |
| 2 | Creación de carpetas (ingesta, clasificación, Regla 3 documentos) | `backend/server.py` (proc_ingest, _clasificar_item, proc_upload_drive, _regla_solicitud_ok) | 🟢 CRÍTICO |
| 3 | Aprobaciones de Mesa (monitor verdad, carta + simulación ajustada, SIN gastos) | `backend/mesa_verdad.py`, `server.py` (_autocorreo_cliente_aprobado, _tipo_pdf_aprobacion) | 🟢 CRÍTICO |
| 4 | Rechazos de Mesa (texto exacto, plantilla C, botón codeudor) | `backend/rechazo_notificacion.py`, `server.py` (_autocorreo_cliente_rechazado) | 🟢 CRÍTICO |
| 5 | Gasto Operacional (MASTER_PIN, cuenta fija MAIL2) | `server.py` (gastos-operacionales) | 🟢 CRÍTICO |
| 6 | Almacenamiento durable (Emergent Object Store + manifiesto Mongo; GridFS solo lectura legado) | `backend/bunker.py`, `folders_service.py` | 🟢 CRÍTICO |
| 7 | Carpeta de Clientes (vista documentos, PDFs protegidos, faltantes, compromiso) | `frontend/src/pages/ClientesModule.js`, `folders_service.py` | 🟢 |
| 8 | Compromiso de Compraventa (editor, Regla #63 LTV 79.5%, modo independiente) | `frontend/src/pages/CompromisoEditor.js`, `server.py` (/compromiso) | 🟢 |
| 9 | Autenticación y roles (admin, gerencia, ventas, contralor, lectura) | `backend/auth.py`, seeds en `server.py` | 🟢 CRÍTICO |
| 10 | Dashboard Admin (alertas, retenidos modo prueba, carpetas faltantes) | `frontend/src/pages/DashboardModule.js`, componentes | 🟢 |
| 11 | Simulador / Calculadora / Set de Crédito | `frontend` + `credit_engine.py` | 🟢 |
| 12 | Publicidad y Campañas (email marketing) | `backend/publicidad.py` | 🟢 |
| 13 | Martín Suma UC (app independiente, TTS/STT) | `backend/martin_financiero.py`, `frontend/public/martin-*.html` | 🟢 |
| 14 | Portal del Cliente / Aprobación Cliente | `server.py` (aprobacion-cliente) | 🟢 |
| 15 | Contraloría / Módulo Control (solo lectura sin excepción) | `backend/espejo_*.py` | 🟢 |
| 16 | Ingesta Gmail (push/pubsub y polling IMAP) | `backend/gmail_pubsub.py`, `email_service.py` | 🟢 CRÍTICO |
| 17 | Constitución / DashAI / Normativas fijas | `server.py` (NORMATIVAS_FIJAS), `constitucion.py` | 🟢 CRÍTICO |

## Normativas constitucionales vigentes (resumen)
- **CUENTA ÚNICA DE ENVÍO**: todo correo sale solo desde gerardo.ext@centralmutuos.cl (MAIL2_*).
- **APROBACIÓN SIN GASTOS**: el correo de aprobación jamás incluye adjuntos/información de Gasto Operacional.
- **RECHAZO TEXTO EXACTO**: el motivo del rechazo es el texto literal del canal oficial; sin texto → se retiene.
- **REGLA 3 DOCUMENTOS (#67)**: carpeta solo con ≥3 documentos obligatorios válidos (sin frases exactas requeridas).
- **SIN BORRADO DESTRUCTIVO**: la reevaluación marca para revisión; jamás borra carpetas.
- **CONSTITUCIÓN DE MÓDULOS**: este archivo. Modificaciones a módulos listados requieren aprobación explícita.

## Pruebas críticas
- Suite: `backend/tests/test_criticos.py` (correos salientes, carpetas, Mesa, rechazos, Gasto Operacional, API smoke).
- Runner pre-despliegue: `scripts/pre_deploy_check.sh` — corre todo y muestra ✅ APTO o 🚨 NO DESPLEGAR.
