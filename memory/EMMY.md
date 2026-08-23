# 📔 REGISTRO EMMY — Memoria de continuidad entre sesiones
INSTRUCCIÓN PARA TODO AGENTE NUEVO: leer este archivo (y GET /api/emmy/registros como admin)
al inicio de cada sesión y continuar desde el último estado registrado, sin pedir contexto al Administrador.
La colección MongoDB `registro_emmy` es la fuente completa; este archivo es su espejo resumido.

## Estado al cierre de sesión 2026-06 (fork "espejo-hibrido")
- Publicidad: estado de bases + límite manual + historial de contactados (Excel) + preview pantalla completa (visual → MASTER_PIN) OPERATIVOS.
- Landing A/B/C + video 2:07 con TTS + correo de propuesta enviados.
- Voz Martín: pipeline por trozos con prefetch (sin cortes, inicio inmediato).
- Seguridad financiera: Gasto Operacional solo Admin+Deisy con MASTER_PIN; mora-link-pago bloqueado; normativa constitucional sembrada.
- CMF: aviso automático al cliente + portal público de comprobante con validación automática.
- Clasificador documental (dependiente/independiente/mixto/exención AFP/codeudor/licencia) activo en _criterios_folder.
- Raíz Guard: 24 carpetas sin RUT purgadas (papelera); bloqueo de envío a mesa por roots inconsistentes.
- Módulo Emmy: /api/emmy/registros (GET/POST) + /api/emmy/export-pdf, UI en Administración y Sistema (solo Admin).
- PENDIENTE: credenciales Twilio (WhatsApp real); barrido clasificación 6 meses corre en background (/tmp/barrido_result.json → informe).
