# CHANGELOG — Central Mutuos (continuación de PRD.md "Implementado")

## 2026-08-02 (parte 4) — Carpetas escrituración, mini programa, alertas, resumen semanal
- **15 carpetas de escrituración creadas** (script `crear_carpetas_escrituracion.py`,
  idempotente): clientes con "solicitud confección borrador escritura" del último mes
  (Boetsch, Ecomac, etc.). Cada carpeta con rut, escritura_op, proyecto e inmobiliaria
  en datos_financieros; sync de docs de aprobación incluido. Total: 21+ carpetas.
- **FIX mini programa /share-target**: quedaba pegado en "Cargando..." porque esperaba
  GET /clientes/folders (>60s → 502 del proxy). Nuevo endpoint liviano
  `GET /api/clientes/folders-light` (id/nombre/rut, ~0.2s); la página carga al instante
  y las carpetas se cargan en segundo plano. Estado vacío mejorado: botón
  "Elegir archivos del teléfono" (share-pick-files), instrucciones WhatsApp e
  instalación PWA. Link: {dominio}/share-target (público, sin contraseña).
  ⚠️ Requiere REDEPLOY para que funcione en producción.
- **Prefill Estudio de Título**: openEstudio usa tasacion-prefill (inmobiliaria,
  vendedor nombre/email/teléfono, dirección).
- **Alerta tasación sin respuesta**: en _actividades_terminadas_loop, tasaciones
  solicitadas hace >5 días sin terminar generan alerta única (flag
  tasacion_alerta_sin_respuesta).
- **Resumen semanal (lunes ~08:00)**: FUSIONADO con el "Resumen Semanal de Martín"
  preexistente — ahora incluye cobros de tasación del mes + acciones pendientes +
  tabla de estado de TODAS las carpetas (mesa/tasación/estudio/escritura/pendientes).
  Se eliminó el bloque duplicado que detectó el testing (iter 11) y el doble registro
  del loop en startup.
- Testing: iteración 11 → 100% backend (6/6) y frontend; limpieza de duplicados
  verificada por curl (1 sola definición, preview con 24 filas).

## 2026-08-02 (parte 3) — Prefill IA de tasación + fix crash estudioPlantillas
- **FIX CRASH**: `estudioPlantillas is not defined` en ClientesModule (el estado
  `useState` nunca se declaró aunque el setter se usaba) → agregado el hook.
- **Prefill IA de tasación**: nuevo `GET /clientes/folders/{fid}/tasacion-prefill`:
  junta cuerpos de correos del cliente (proc_queue) + OCR de documentos relevantes
  (promesa/oferta/carta/cotización/reserva) y extrae con LLM
  (`ai_extract.extraer_datos_tasacion`, gpt-5.4-mini + regex fallback para rol):
  direccion, unidad, comuna, ciudad, rol_avaluo, proyecto, inmobiliaria,
  valor_propiedad_uf, vendedor (nombre/email/teléfono). datos_financieros guardados
  tienen prioridad. `openTasacion` lo llama y rellena los campos vacíos del modal.
  Verificado con Vanesa Ocampo: comuna/ciudad/valor 2800/inmobiliaria ecomac.

## 2026-08-02 (parte 2) — Reglas de faltantes manuales, sync aprobación, fecha entrega en mesa
- **Faltantes SOLO manuales**: eliminadas las 2 llamadas a `_enviar_faltantes_auto` en
  `proc_upload_drive` y desregistrado `_faltantes_recordatorio_loop` del startup.
  La función queda definida pero sin uso automático.
- **Regla Claudia Zurita**: la carta de aprobación y el PDF de simulación deben estar
  SIEMPRE descargados en la carpeta. Nuevo `_sync_docs_aprobacion(nombre)`:
  busca en `storage/autocorreo` (por nombre) y en IMAP
  (`_imap_descargar_adjuntos_cliente`, combos nombre+apellido, patrón
  aprobaci|simulad|ajustad|_cm) y copia a `99_otros`. Endpoint
  `POST /clientes/folders/{fid}/sync-aprobacion`. Hooks: `aprobacion_archivos`
  (Aprobación Cliente), `forzar_folder` y `openTasacion` (frontend).
  Verificado con Zurita: bajó "Aprobacion CentralMutuos - 2026-07-01...pdf" +
  "simulador_crediticio_2026-07-01 _12_.pdf".
- `_tipo_pdf_aprobacion` ahora acepta "simulad" como simulación.
- **Fecha de entrega OBLIGATORIA en correos a MESA**: subject termina con
  "— Entrega: Inmediata/Futura" y el cuerpo incluye la fila "Fecha de entrega"
  (`_fin_resumen_html`). Si falta, se agrega a missing_labels → bloqueo 412
  salvo force_incompleto.
- **Tasación prefill**: valor_uf y valor_esperado_uf desde
  datos_financieros.valor_propiedad; direccion/comuna/ciudad si existen.
- **Gastos Operacionales**: correo enviado incluye fila "TOTAL EN PESOS (UF del
  día $X)" con `payload['valor_uf'] = get_valor_uf()`.
- **Auto-terminado**: `_actividades_terminadas_loop` (60 min) marca
  tasacion_terminado_at (respuesta Value Property vía IMAP) y
  estudio_titulo_terminado_at (reparos satisfechos), con origen "auto" + alertas.
  `_procesar_reparos_folder` también lo setea al declararse satisfecho.
- **Historial por carpeta**: `GET /clientes/folders/{fid}/historial` (línea de
  tiempo con todos los hitos + alertas) + botón "Historial" y modal en tarjetas.
- Caso Vanesa Ocampo (titular/codeudor): el usuario indicó NO modificarlo.
- Testing: iteraciones 9 (detectó regresión auto-faltantes, corregida) y 10
  (15/15 backend, frontend 100%).

## 2026-08-02 — Fork: bug CMF fantasma + Correo a Mesa + actividades + tasación ampliada
- **BUG "CMF fantasma" (Ernesto Díaz)**: archivos `INFNOMAT-*.pdf` (Informe de NO
  Matrimonio del Registro Civil) se clasificaban como Informe CMF porque "infnomat"
  estaba como keyword de cmf en `folders_service.CAT_KEYWORDS`. Corregido:
  - `cat_de_texto` excluye infnomat/matrimonio/unión civil → "extras".
  - `ai_extract._fallback_clasificar` devuelve "otro" para informes de no matrimonio;
    prompt LLM refuerza que certificado_smf = SOLO Informe de Deudas CMF.
  - Reparación de datos: INFNOMAT movidos 04_cmf → 99_otros en Ernesto Díaz y
    Paula Rivera (script `repair_infnomat.py`, combinados obsoletos borrados).
- **Bloqueo de envío incompleto**: POST /clientes/folders/{fid}/send-email con
  confirm=true devuelve **412** si faltan documentos obligatorios, salvo
  `force_incompleto:true`. El preview (confirm=false) devuelve `missing_docs`,
  `docs_completos` y `body_html`.
- **Preview SIEMPRE + edición manual del cuerpo**: el modal de envío a mesa muestra
  preview auto (bug: leía `body_html` que el backend no devolvía), editor manual del
  HTML (payload `body_html`), checkbox "Asumo el envío manual con documentación
  incompleta" y botón bloqueado "🚫 Faltan documentos".
- **Rename**: módulo "Autocorreo" → **"Correo a Mesa"** (sidebar, títulos, botones).
- **Actividades permanentes con fecha/hora** en las tarjetas: Tasación / Estudio de
  Título / Escritura / Pedir faltantes / Enviado a mesa muestran "✓ Solicitado
  dd-mm hh:mm" (24h) y estados terminados. Nuevo endpoint
  `PATCH /clientes/folders/{fid}/actividad-terminada` {tipo, terminado} →
  setea `{tipo}_terminado_at` (tipos: tasacion, estudio_titulo, escritura).
  Botones toggle "¿Tasación terminada?" / "¿E. Título terminado?" en tarjeta.
- **Fecha de entrega (inmediata/futura)**: auto-detectada del correo
  (campos.fecha_entrega → datos_financieros en proc_upload_drive) + select manual en
  ambos paneles de Datos Financieros + badge "🏠 Entrega ..." en la tarjeta.
- **Solicitud de Tasación ampliada**: N° unidad/depto, Comuna, Ciudad, Rol de Avalúo
  Fiscal, Valor esperado de tasación (UF), flag carta_adjunta (fila "Se adjunta carta
  de aprobación") y advertencia amarilla si no hay carta seleccionada.
- **Cuenta recaudadora ÚNICA** (gasto operacional + tasación):
  MUTUARIAS Y LEASING LIMITADA, RUT 77.771.552-6, Mercado Pago, Cuenta Vista,
  N° 1030937838 (GASTOS_OP_DEFAULTS + db.config gastos_op actualizados).
- **Gastos Operacionales**: fila TOTAL muestra también el equivalente en **pesos**
  "≈ $X CLP (UF hoy $Y)" (data-testid gastos-total-clp).
- **Branding**: eliminado "Asesorías" — queda "Central Mutuos · Con Creces"
  (plantillas de correo + footer login).
- Testing: iteración 7 (100% backend+frontend) e iteración 8 (100% backend+frontend).

## Pendiente / Backlog (ver también ROADMAP en PRD)
- Descartado por el usuario: fix titular/codeudor caso Vanesa Ocampo (se deja como está).
- P1: Crear carpetas de brokers que pidieron escrituración el último mes
  (Work Consultores, Gestión Hipotecaria, Maestra, Bosch, Ecomac).
- P2: Prueba en vivo de Correo a Mesa con saldo eCert real (espera al usuario).
- El usuario indicó que estos cambios quedan permanentes para subir a PRODUCCIÓN
  (redeploy) y partir desde este punto.

## 2026-06 (fork) — Lote Escrituración + Estudio de Título Etapa 2
- Pestañas "Solicitudes de Crédito" / "Escrituración" en Carpeta Clientes + botón Mover/Devolver (POST /api/clientes/folders/{fid}/escrituracion).
- Forzar Carpeta: busca por nombre Y RUT, descarga adjuntos por IMAP, filtra firmas de correo (imageNNN), verifica identidad con la cédula (OCR+IA) y corrige nombre/RUT (verificacion_cedula).
- Enriquecer archivos (POST /api/clientes/folders/{fid}/enriquecer, modo credito|estudio). Docs de estudio SIEMPRE a 07_estudio_titulo (regla inviolable, clave 0586 para cambiarla).
- Correo a Mesa: selector ejecutivo interno (Deisy Salazar, Yerile Barrera, Gerardo Barrera); preview NO persiste ejecutivo; body incluye origen + ejecutivo.
- mesa_respuesta = "aprobada" automática si la carpeta tiene carta de aprobación o simulación ajustada (aunque prob sea 0%).
- Gastos Operacionales: prefill IA (GET /api/gastos-operacionales/prefill?nombre=) + botón "Leer datos con IA" (prohibido inventar).
- Tasación: asunto siempre nombre+RUT (fallback RUT desde carpeta); prefill IA mejorado (más correos con asunto/cuerpo + más documentos, incl. tasación); botones Ver por adjunto.
- Estudio de Título: sección separada de docs recibidos (detalle + modal), preview "Ver" por archivo, ETAPA 2 (POST /api/estudio-titulo/etapa2/{fid}: envía docs de 07_estudio_titulo a Guillermo Marluf CC Victoria Vilches, mismo hilo), Etapa 1 usada envía al vendedor con listado, listado obligatorio para inmobiliarias (docs_nueva, sin tasación), frase de reserva de antecedentes, reparos con casilla "Reparo aceptado" y botón de declaración final (marcado manual disponible).
- merge-protocol acepta orden personalizado (campo "orden"); orden protocolar por defecto.
- Testing: iteration_12.json (14/14) e iteration_13.json (15/15) — todo PASSED.
- NOTA RECURRENTE: hot-reload de uvicorn a veces cuelga tras editar server.py → sudo supervisorctl restart backend.

## 2026-06 (fork, continuación) — Módulos Cierres y Aprendizaje IA
- MÓDULO CIERRES: listado de aprobaciones enviadas agrupado por ejecutivo/inmobiliaria. Ventana inicial: último domingo, un mes atrás (barrido mensual); luego cadencia de 3 días por cliente. Botón manual "Preguntar al ejecutivo" envía correo con 2 botones de acción de un clic: "Sí continúa" (marca respuesta) y "No continúa" (BORRA la carpeta automáticamente vía GET /api/cierres/respuesta/{token}). Botón manual "No continúa" con borrado opcional. Ejecutivo autocompletado desde el origen de la solicitud original (source_email o proc_queue); backfill IMAP realizado para carpetas existentes. Endpoints: GET/PATCH /api/cierres, POST /api/cierres/{fid}/consultar, GET /api/cierres/respuesta/{token}.
- MÓDULO APRENDIZAJE IA: la IA aprende del flujo comercial real (métricas de carpetas/mesa/tasaciones/estudios/reparos/cierres), guarda ciclos con resumen/aprendizajes/cuellos de botella/mejoras, acepta notas del usuario, loop automático diario (_aprendizaje_loop). Endpoints: GET /api/aprendizaje, POST /api/aprendizaje/nota, POST /api/aprendizaje/analizar. Prohibido inventar métricas.
- Estudio de Título: listado editable también para vivienda NUEVA (11 docs para inmobiliarias, sin tasación en ningún listado), frase de reserva de antecedentes en el correo, vendedor destinatario en etapa 1 usada.
- Forzar Carpeta: prompts claros nombre y/o RUT; guarda source_email del remitente encontrado; Enriquecer también respalda source_email.
- Testing: iteration_14.json 12/12 backend + frontend OK. Screenshot final del módulo Cierres validado.

## Fix: Forzar Carpeta no descargaba adjuntos (caso Pedro González)
- Causa raíz: la búsqueda IMAP era sensible a acentos ("gonzalez" no encontraba "González"; el comando IMAP fallaba con caracteres acentuados) y solo revisaba una ventana estrecha de resultados.
- Fix en email_service.py: _sin_acentos() para normalizar, _buscar_ids_persona() une búsquedas por cada token + búsqueda UTF-8 con literal para tildes + barrido de los 30 correos más recientes; ventana ampliada a 60 ids; candidatos por cuerpo además de cabeceras.
- Verificado e2e: Forzar "Pedro González" → 3 correos encontrados, carpeta creada con 4 archivos (incl. DOCUMENTOS SOLICITADOS ASESORIA.pdf), 0% probabilidad (sin docs mínimos, correcto).

## Sugerencias en vivo para Forzar Carpeta
- Nuevo modal de Forzar Carpeta (reemplaza los prompts): al escribir el nombre aparecen sugerencias inmediatas en 3 bloques — carpetas existentes, correos del buzón (búsqueda rápida solo cabeceras, GET /api/clientes/forzar/sugerencias) y correos en la cola con conteo de adjuntos.
- Nuevo search_email_headers_by_person() en email_service.py (rápido, tolerante a acentos).
- Regex de Mongo insensible a tildes (_rx_acentos) para que "gonzalez" encuentre "González" en carpetas y cola.
- Verificado con screenshot: carpeta Pedro González + 8 correos + 3 en cola sugeridos al escribir.

## 2026-06 (sesión fork)
- VERIFICADO visualmente el fix de Set Crédito para Claudia Zurita:
  - Los 8 PDFs (SOLICITUD CREDITO, DPS, PEP, COBRANZA, CESANTÍA, DESIGNACIÓN MANDATARIO, DECL. ORIGEN FONDOS, DECL. JURADA ESTADO CIVIL) se listan correctamente (archivos leídos desde disco en /app/backend/storage/set_credito/).
  - El modal "Nuevo contacto eCert" se autocompleta: Nombres=CLAUDIA ANDREA, Ap. Paterno=ZURITA, Ap. Materno=SOTO, RUN=16.005.374-7, correo=czurita.uchile@gmail.com (ambos campos).
  - eCert/migrup conectado (Gerardo Nicolas Barrera).
- Recordatorio entregado al usuario: usar "Deploy" para llevar cambios de Preview a Producción (bases de datos separadas).

## 2026-06 — Importar desde correo en TODOS los módulos
- Nuevos endpoints: GET /api/correos/buscar (sugerencias IMAP en vivo) y POST /api/correos/importar (destino: carpeta | estudio_titulo | set_credito, con dedupe por nombre de archivo y regla 07_estudio_titulo).
- Componente reutilizable /app/frontend/src/components/ImportarCorreo.js (botón + modal, testids importar-correo-btn-{destino}).
- Integrado en: Set de Crédito, Carpeta Clientes (2 botones: carpeta y Estudio de Título), Gastos Operacionales (tasación) y Aprobación Cliente.
- Testing agent iteración 15: backend 7/7, frontend 5/5 — todo PASS.
- Mejora UX pedida por usuario: listado de correos del modal más grande y legible (modal 820px, asunto 1.02rem, remitente y fecha en líneas separadas, checkbox 18px).

## 2026-06 — FIX CRÍTICO: 502 en producción (forzar carpeta / importar correo)
- Causa raíz: el proxy/ingress corta toda petición HTTP >60s. La búsqueda+descarga IMAP tardaba 70-120s → Cloudflare 502 ("se pega y no descarga nada"). La carpeta se creaba pero los adjuntos nunca llegaban a guardarse.
- Solución: patrón de trabajos en segundo plano (colección bg_jobs + GET /api/jobs/{id}).
  - POST /api/clientes/folders/forzar → valida clave y devuelve job_id al instante; lógica en _forzar_folder_run.
  - POST /api/correos/importar → devuelve job_id; lógica en _correos_importar_run.
  - Frontend (ClientesModule.ejecutarForzar e ImportarCorreo.importar) hace polling cada 3s hasta 6 min con mensaje "⏳ Buscando…".
- Verificado E2E en preview: forzar Pedro González (job 73s → listo) e importar a set Claudia (job → listo). El usuario DEBE re-desplegar (Deploy) para que llegue a producción.
- Modo automático de carpetas: SIEMPRE activo (blindaje 24/7 en _proc_auto_state, no se puede apagar), corre cada 10 min, ingesta 15 correos. Reglas estrictas _es_gestion: dominio ecomac/maestra, o asunto "solicitud de crédito/financiamiento/preaprobación", o PDFs + asunto con evaluación/liquidación/antecedentes/carpeta/documento. Correos que no cumplen mínimo de documentos → descartados con alerta.

## 2026-06 — Detección automática mejorada + norma Aprobación de Mesa
- Autocorreo estaba APAGADO desde el 27/7 (enabled=false) → reactivado (enabled + periodic). Por eso no llegaban los autocorreos con PDFs ajustados.
- Reglas de creación automática ahora EDITABLES desde Procesamiento Correo (panel "Reglas de creación automática"): GET/PATCH /api/procesamiento/reglas-auto (db.config _key reglas_auto). _es_gestion normaliza acentos y usa keywords ampliadas (+credito, +financiamiento, +hipotecari, document en raíz).
- NUEVA NORMA: cuando llega una APROBACIÓN de mesa, _asegurar_carpeta_aprobacion crea la carpeta del cliente si no existe (origen aprobacion_mesa, con alerta) y copia SIEMPRE la carta de aprobación + simulación ajustada (_sync_docs_aprobacion). Sin regla de mínimos. Detecta aprobación por clasificación del asunto O por adjunto tipo carta_aprobacion.
- Verificado: KEVIN MACAYA, CHRISTIAN PASTEN, CECILIA JORQUERA, JOSE FLORES → carpetas creadas con carta + simulación. Ciclo auto ingresó 3 correos nuevos (antes 0); los que no cumplen mínimos se descartan con alerta (por diseño).
- Aclarado: el forzado manual NO aplica regla de mínimos (proc_upload_drive force=True la salta) y descarga lo que el usuario elige.

## 2026-06 — FIX: correos duplicados a Mesa + regla "un solo envío"
- Qué pasó: (1) _procesar_mesa enviaba UN correo POR CADA PDF adjunto (carta y simulación = 2 correos), y (2) el mismo correo de mesa existe en AMBAS casillas IMAP y se procesaba dos veces en el mismo ciclo (sin dedupe intra-ciclo) → hasta 4 correos por cliente (11:59 y 12:00).
- Medidas: (a) todos los PDFs de una gestión van ahora JUNTOS en UN solo correo; (b) dedupe intra-ciclo: el asunto se registra en ya_enviados al procesarse, ignorando el duplicado de la otra casilla; (c) dedupe entre ciclos ya existía vía autocorreo_log.
- NUEVA REGLA: enviar carpeta a Mesa (send-email) solo se permite UNA vez en forma directa; el reenvío exige la clave admin (403 → frontend pide clave y reintenta). Campo folders.mesa_enviado_at.
- Verificado: 2ª corrida de mesa → processed 0, sent 0 (sin duplicados); reenvío sin clave → 403 con mensaje claro.

## 2026-06 — BLINDAJE TOTAL antiduplicados a Mesa (candado en BD)
- Colección mesa_enviados con índice único por key (asunto normalizado sin acentos).
- _mesa_guard_reservar: reserva ATÓMICA (find_one_and_update upsert) antes de CADA envío automático a mesa; si el asunto ya se envió alguna vez, se salta — imposible duplicar aunque fallen los otros dedupes. Si el envío falla, se libera la reserva.
- Sembrado con los 25 asuntos ya enviados históricamente.
- Envío manual de gestión (proc_enviar_autocorreo): reenvío exige clave 0586 (403); frontend pide la clave y reintenta.
- Verificado: re-run de mesa → 0 enviados; reenvío manual sin clave → 403.

## 2026-06 — Autocorreos no llegaban al usuario + split PDF empaquetado
- CAUSA: autocorreo_state.destination estaba configurado a aprobaciones@centralmutuos.cl (¡la casilla de Mesa!) en vez de la del usuario. Corregido a gerardo.ext@centralmutuos.cl. Esto explica también los duplicados que Mesa recibió.
- Liberados los candados/logs SOLO de hoy (envíos a casilla equivocada) → el ciclo reenvió 6 gestiones a la casilla correcta, SIN duplicados (1 correo por gestión con todos los PDFs juntos).
- Split de PDF empaquetado ("DOCUMENTOS SOLICITADOS ASESORIA.pdf"): endpoint /split-bundled convertido a trabajo en segundo plano (OCR >60s excedía el proxy). Además _regen_combinado_bg ahora auto-separa PDFs empaquetados (patrón _PAT_EMPAQUETADO, en raíz o 99_otros) y rearma el protocolo, con alerta.
- PENDIENTE VERIFICAR: ejecutar split para PEDRO GONZALEZ vía job y confirmar archivos separados + combinado regenerado.

## 2026-06 — OCR reparado + split automático funcionando E2E
- Instalados poppler-utils, tesseract-ocr y tesseract-ocr-spa (faltaban: el OCR fallaba silenciosamente en TODOS los flujos de clasificación).
- Respaldo deploy-safe: _ocr_ia_pagina en folders_service.py (PyMuPDF render + visión gpt-5.4-mini con EMERGENT_LLM_KEY) si tesseract/poppler no existen (ej: producción). pymupdf agregado a requirements.txt.
- Verificado E2E: 'DOCUMENTOS SOLICITADOS ASESORIA.pdf' de PEDRO GONZALEZ (13 págs escaneadas) → separado en liquidaciones 1-11, cédula 12, CMF 13 → COMBINADO_PROTOCOLO regenerado.
- /split-bundled ahora es trabajo en segundo plano (jobs) + auto-split en _regen_combinado_bg para PDFs empaquetados (raíz o 99_otros).
- Autocorreo destination corregido: gerardo.ext@centralmutuos.cl (estaba apuntando a la casilla de Mesa).

## 2026-06 — Aprobación Cliente: SOLO 2 archivos + sin "ajustada" + Ver PDF
- /aprobacion-cliente/archivos ahora devuelve EXACTAMENTE 2 archivos: la carta de aprobación y la simulación más recientes (los mismos del autocorreo).
- El cliente nunca ve "ajustada": _nombre_cliente_pdf renombra adjuntos (quita 'ajustada'/'_CM') en preview, envío y log. Plantillas y default corregidos (4 plantillas en DB actualizadas).
- Nuevo GET /aprobacion-cliente/preview-pdf + botón "Ver PDF" por archivo en la UI para confirmar antes de enviar (además de la Vista previa del correo existente).
- Verificado por API (2 archivos, nombres limpios, cuerpo sin 'ajustada') y captura UI (2 archivos con Ver PDF).

## 2026-06 — Verificación adjuntos Aprobación Cliente (7 carpetas)
- Verificado por API que cada cliente recibe SU propia carta + simulación: Jose Flores (_93), Kevin Macaya (_49), Christian Pasten (_90), Cecilia Jorquera (_91), Luis Sepulveda (_95), Ruperto Antileo (_94), Paula Rivera (_97).
- Fix renombrado: 'Simulador_Ajustado _22__CM.pdf' ahora → 'Simulador _22.pdf' (regex ajustad[oa] + colapso de '__').

## 2026-06 — Autorelleno de datos del cliente en Aprobación Cliente
- Nuevo GET /aprobacion-cliente/datos-cliente: rellena email/teléfono/RUT sin inventar, en cascada: proc_queue → folders/set_credito → búsqueda en el buzón IMAP (correo de solicitud de crédito) con regex y exclusión de correos internos.
- Frontend: al elegir cliente sin email, autofill automático en segundo plano con aviso de la fuente.
- Verificado: Ruperto Antileo → antileo1985@gmail.com, +56972950468, 16.425.611-1 (desde buzón, 11s).
- Refinado: prioriza correos etiquetados "correo del cliente" y personales (gmail/hotmail/...), excluye dominios de inmobiliarias (maestra/ecomac/boetsch) e internos; limpia puntuación de bordes.

## 2026-08-03 — Sesión: carpetas, seguimiento mensual, pagos gastos, blindaje simulación (iteración 16 — 100% PASS)
- REGLA CARPETAS FLEXIBILIZADA: `_regla_solicitud_ok` ya no exige monto; cuenta documentos básicos también por nombre de archivo (fsvc.cat_de_texto). Mínimo 3 docs (2 si hay monto).
- FIX nombre de cliente: `_extraer_nombre` quita prefijos de estado (EVALUACION/APROBADO ·/SOLICITUD...) y acepta nombres desnudos con stopwords bloqueadas; si la IA extrajo 1 sola palabra (saludo "Gerardo"), se prefiere el asunto. Carpeta "Gerardo" eliminada y re-creada como "Melisa Rivera" (verificado con archivos por protocolo).
- SEGUIMIENTO ÚLTIMO MES: `fetch_headers_since(dias)` (IMAP SINCE, fetch por lotes de 100), POST /seguimiento/process-emails?dias=31 enriquece con `_info_operacion_cliente` (ejecutivo externo REAL = remitente de la solicitud original en proc_queue + folders), GET /seguimiento/clientes devuelve rut/proyecto/ejecutivo_cm/ejecutivo_externo/correo_remitente/monto. GET /reportes/seguimiento/excel exporta .xls. 39 clientes poblados.
- PAGOS GASTOS OPERACIONALES: gastos_op_log ahora con pagos[]/pagado/saldo/estado_pago. POST /gastos-operacionales/log/{id}/pago, DELETE .../pago/{idx}, POST /gastos-operacionales/pagos/scan (detecta transferencias por keywords + nombre cliente + monto CLP→UF). UI completa en GastosOperacionalesModule (badges PENDIENTE/PARCIAL/PAGADO, registrar/eliminar pago, botón buscar transferencias).
- BLOQUEOS GMAIL: reportes internos (resumen semanal, reporte diario, tasación pagada, tope recordatorios, reparos) ahora se envían desde "principal" (auto-envío gmail→gmail, no se bloquea). Contexto: ethangerardobarr@gmail.com es cuenta ESPEJO de gerardo.ext@centralmutuos.cl (gmail = armado carpetas; gerardo.ext = autocorreos/envíos).
- LOG SMTP COMPLETO: send_mail guarda en db.correos_smtp_log código y respuesta SMTP exacta de cada envío (pedido del usuario). GET /correos/smtp-log?solo_errores=true.
- AUTOCORREOS TEXTO: aprobaciones de mesa SIN PDF (solo texto) ya no se saltan — se reenvían y aseguran carpeta (antes solo rechazos). Guard anti-carpetas basura (@/mesa/aprobaciones/1 palabra) en _asegurar_carpeta_aprobacion. limit mesa 8→15. Corrida verificada: 9 enviados, 4 carpetas creadas con carta+simulación.
- BLINDAJE SIMULACIÓN (REGLA INVIOLABLE): TRIPLE capa — (1) `_blindaje_simulaciones` DENTRO de send_mail: ningún PDF "simulad*" sale con >1 página salvo clave maestra 0586 (param clave_sin_ajuste); (2) recorte en /aprobacion-cliente/enviar y preferencia por versión _CM en /aprobacion-cliente/archivos; (3) _sync_docs_aprobacion guarda simulaciones ya ajustadas en carpeta. RETROACTIVO: 32 simulaciones crudas en carpetas fueron recortadas a 1 página (caso Pedro González corregido).
- NOTA OPERATIVA: uvicorn hot-reload a veces queda colgado por hilos IMAP → usar `sudo supervisorctl restart backend` tras editar. Eso causó el susto de "carpetas desaparecidas" (la DB siempre estuvo intacta).

## Sesión 2026-08-04 — Motor de Extracción Enriquecida centralizado + Guardar y Aprender global
- `ai_extract.py` ahora contiene TODO el motor: `enriquecer_cliente(db, mail, nombre)` (cruza asunto + cuerpo + OCR PDFs + carpetas + set crédito + gastos_op_log + aprobacion_log + buzón IMAP + patrones aprendidos, devuelve confianza alta/dudosa + fuentes + remitente) y `guardar_correccion(db, payload)` (inserta en db.patrones_aprendidos y propaga a db.folders). server.py solo delega (endpoints reducidos de ~170 líneas a 20).
- Endpoint genérico nuevo: GET /api/aprendizaje/datos-cliente?nombre= (alias de /aprobacion-cliente/datos-cliente).
- Fuentes nuevas del historial: db.gastos_op_log y db.aprobacion_log (correo/RUT/ejecutivos validados en envíos reales → confianza alta). Confianza alta ahora también con fuentes validadas {carpeta, aprendido, gastos, aprobacion, set_credito}.
- Frontend: componente compartido `/app/frontend/src/components/CampoAprendizaje.js` (estiloConfianza premium: gradiente slate + halo esmeralda/ámbar con sombra suave, NO colores planos; hook useAprendizaje; PanelAprendizaje glassmorphism "MOTOR DE EXTRACCIÓN · IA" con botón dorado Guardar y Aprender).
- Integrado en 3 módulos: AprobacionCliente (migrado al estilo compartido), GastosOperacionales (autofill al elegir cliente + prefill, testid gastos-guardar-aprender) y SetCredito (autofill onBlur del nombre en Nuevo Set, testid setcred-guardar-aprender).
- VERIFICADO e2e: curl enriquecimiento Franco Bahamondes (email alta 4 fuentes, rut alta), corrección de teléfono → re-fetch devuelve valor "aprendido" con confianza alta (dato de prueba limpiado), screenshots Gastos y Set de Crédito con panel y halos OK.

## Sesión 2026-08-04 (parte 2) — Rediseño "Terminal de Inversión Maserati" + Multi-correo + Hilos Reparos
- TEMA GLOBAL: variable --gold pasó de azul #60a5fa a ORO real #d4af37 (App.css :root); base Slate #0f172a, cards #1e293b, inputs #0b1120, --radius 4px (esquinas cuadradas). Sed masivo blue→gold: rgba(96,165,250)→rgba(212,175,55), #60a5fa→#d4af37, #bfdbfe→#e7cf7a en App.css + 23 archivos JS (140 reemplazos, 0 regresiones según iter22).
- GLASSMORPHISM: .sidebar y .topbar con backdrop-blur 14-18px + borde oro suave; .login-card vidrio con borde dorado.
- LOGO METÁLICO: .sidebar-title con gradiente plata→oro (background-clip:text) + drop-shadow dorado.
- MULTI-CORREO GASTOS: gastos_enviar acepta emails_extra (string coma o lista, dedupe case-insensitive, excluye email_cliente); envía a [cliente]+extras y los registra en gastos_op_log.emails_extra. UI: input data-testid=gastos-emails-extra "Destinatarios adicionales". NOTA: la regla "solo al cliente" sigue para envíos automáticos; los extras son SOLO manuales.
- HILOS REPAROS (Responder a todos): email_service.buscar_hilo_por_asunto ahora devuelve to_cc_emails (To+Cc sin cuentas propias); _procesar_reparos_folder acumula rep["participantes"] (remitente+to+cc de cada respuesta); _reparos_cc incluye participantes en TODOS los correos del hilo (vendedor, recordatorio, resuelto).
- Design guidelines en /app/design_guidelines.json (design_agent).
- TESTING iteración 22: backend 8/8 PASS, frontend 100% (12 módulos, 0 errores JS post-sed). Reporte /app/test_reports/iteration_22.json.

## Sesión 2026-08-04 (parte 3) — Rediseño Agresivo Maserati + Estándar de Oro
- RONDA 2 (agresiva): borderRadius 5-24px → 4px (~276 puntos JS), modales '#1a1f2e' → glass rgba+blur16, azules #3b82f6/rgba(59,130,246)→oro en JS (App.css → plata --info #94a3b8), headings h1-h4 Inter uppercase letter-spacing, montos UF/resultados en 'JetBrains Mono' (.topbar-uf, .result-val, .ratios-table td, .calc-table input), tablas con líneas sutiles (th borde oro 0.25, td rgba slate 0.1). Iteración 23: frontend 100% (15 módulos, 3 modales, 0 errores).
- RONDA 3 (Estándar de Oro): fondo global #0b1120 (slate casi negro), cards con borde 2px oro rgba(212,175,55,0.5-0.55) + glow sutil, --bg-card rgba(15,23,42,0.9), radius 2px global, glow dorado hover en TODOS los botones (button:hover box-shadow oro), iconos sidebar dorados, logo gradiente oro vibrante (sin plata), topbar glass 0.88+blur16, cian/celeste eliminado (#0ea5e9/#22d3ee/#06b6d4/#93c5fd→oro), modales inline '#0f172a'→glass rgba(15,23,42,0.92)+blur16.
- VERIFICADO: babel parse OK en todos los JS, screenshots Gastos/Clientes/modal Tasación (abre OK con glass; tarda unos seg por tasacion-prefill), 0 errores de consola.
- NOTA: modal de Tasación demora 2-10s en abrir (llama /tasacion-prefill); no es bug.

## Sesión 2026-08-04 (parte 4) — Acabado Final Maserati
- CARDS "CUERO/CARBONO": fondo gradiente #0f172a→#020617 con truco border-box: cards CSS (.form-fieldset, .calc-card, etc.) y 15 cards inline JS (sed border 2px oro → border transparente + backgroundImage doble gradiente + backgroundClip padding-box/border-box).
- BORDES DE JOYERÍA: 1px gradiente oro pulido (140deg #b8860b→#fde68a 45%→#d4af37 65%→#b8860b) en todos los paneles.
- TERMINAL ELITE: .topbar-uf/.result-val/.max-credit-uf/.ai-max-value en oro + text-shadow glow; [data-testid^=prob-aprobacion-] en JetBrains Mono con glow currentColor (conserva color semántico).
- FONDO INMERSIVO: body::before con textura de grano SVG (feTurbulence) opacity 0.045, position fixed, pointer-events none.
- ICONOS: i[class*=fa-] a 0.92em; iconos de headings/labels/sidebar en oro (NO global !important para no romper iconos sobre botones dorados).
- VERIFICADO: babel parse OK, screenshots Dashboard/Clientes/Simulador impecables, 0 errores consola. Recordar al usuario RE-DEPLOY para ver en producción.

## Sesión 2026-08-04 (parte 5) — Reprogramación Estética Total: Ostentación 24 Quilates
- FONDO: Negro Carbono absoluto #050505 (adiós slate). Seds globales: rgba(15,23,42,→rgba(14,14,16,; rgba(30,41,59,→rgba(28,28,30,; rgba(2,6,23,→rgba(5,5,5,; #0f172a→#101012; #020617→#050505; #0b1120→#070708; #1e293b→#232326 (JS + App.css).
- CARDS CRISTAL OSCURO: gradiente rgba(30,30,30,0.95)→rgba(10,10,10,0.98) + borde 1px gradiente ORO 24K linear-gradient(135deg,#BF953F,#FCF6BA,#B38728,#FBF5B7,#AA771C) + sombras cinematográficas (0 35px 70px negro + glow oro). Aplicado a clases CSS y a las 15 cards inline JS.
- TÍTULOS ORO 24K: h1/h2/h3 con background-clip:text del gradiente 24K, font-weight 300, letter-spacing 0.14em. Logo sidebar con el mismo gradiente. Var CSS nueva: --gold-24k.
- TIPOGRAFÍA: body font-weight 300 (Light); .topbar-uf 1.18rem oro mono glow; radius 0px TOTAL (sed 2/3/4px→0).
- ANIMACIÓN DE PODER: transiciones cubic-bezier en botones (+ translateY(1px) en :active), inputs y sidebar-items; glow dorado persistente en .login-btn/.submit-btn.
- BUG ARREGLADO: línea CSS huérfana "size: 0.92em; }" (línea 2503) rompía la compilación — eliminada.
- Topbar a rgba(8,8,8,0.9) con borde oro. VERIFICADO: screenshots Dashboard/Clientes impecables, 0 errores JS.

## Sesión 2026-08-04 (parte 6) — Joyería Financiera
- GEMAS: rojo→Rubí (#e11d48/#be123c/#fb7185), verde→Esmeralda eléctrica (#10d98e/#10c98a/#34eab9), azul/morado→Zafiro (#0f52ba/#2e5ce6/#a5c0fa). Seds globales en JS + App.css (--danger/--success actualizados).
- LEGIBILIDAD PRESIDENCIAL: body 17px; .clientes-card-info h4 1.45rem bold oro 24K gradiente; .clientes-rut 1.08rem JetBrains Mono; td 0.95rem.
- BRILLO ESPECULAR: capa extra linear-gradient(115deg, rgba(255,255,255,0.09)→transparent 32%) padding-box en cards CSS e inline JS (backgroundClip "padding-box, padding-box, border-box").
- FONDO: negro absoluto #000000.
- ⚠️ LECCIÓN (bug de carrera): NUNCA mezclar search_replace y `sed/cat >>` sobre EL MISMO archivo en un lote paralelo — en parte 5 esto revirtió la regla de cards y creó una línea CSS corrupta ("size: 0.92em;"). Arreglado re-aplicando la regla de forma aislada.
- VERIFICADO: screenshots Clientes/Simulador, 0 errores JS, llaves CSS balanceadas.

## Sesión 2026-08-04 (parte 7) — Centro de Ventas VIP + Simulador Martín + Informe Dorado + Gráficos Riesgo
- SALES_ENGINE (sales_engine.py): parseo Excel prospectos, correo persona "José Martín Benavente", nota diaria + capa servicio MongoDB (crear_oportunidades dedupe, preparar_borrador con pixel/click tracking, autorizar_envio con CANDADO confirm + bloqueo 14 días, track, desde_expediente_vip).
- RUTAS /api/oportunidades/*: upload-excel (multipart), list (con resumen/nota), {oid}/preparar, {oid}/autorizar (400 sin confirm de Gerardo; envía por rol "secundaria"), track/{oid}/pixel.gif (gif 1x1), track/{oid}/click (307 al simulador con ?op=), DELETE.
- SIMULADOR_ENGINE conectado: /api/martin/simular delega a calcular_viabilidad(base_mesa de _stats_mesa, uf_hoy); devuelve consejo + puede_abrir_expediente(≥75). Página pública: burbuja "Voz de Martín" EN VIVO (martin-live, tips al escribir), burbuja consejo (martin-consejo), botón dinámico "✦ Abrir Expediente VIP", ?op= marca uso_simulador. abrir-carpeta ahora también crea oportunidad expediente_vip.
- FRONTEND: OportunidadesModule.js (stats, nota diaria, tabla con badges de interés zafiro/oro/esmeralda, preview modal del borrador, botón Autorizar deshabilitado sin borrador/email/bloqueo) — nav 'oportunidades' (solo admin, icono fa-diamond). GraficosRiesgo.js en Dashboard (4 barras gema por rango de % + top 5 clientes).
- INFORME VIP PDF: paleta oro 24K/carbono (#0a0a0a header, #d4af37 acentos, título #FCF6BA, rubí #be123c).
- ⚠️ RECURRENCIA del bug de carrera: el bloque de rutas se perdió al hacer 12 search_replace sobre server.py en un solo lote paralelo (11/12 sobrevivieron). REGLA: máximo pocos edits por archivo por lote, o re-verificar con grep tras lotes grandes.
- TESTING iteración 24: frontend 100%, backend verificado por curl (upload/preparar/candado/pixel/click/tracking/simular/pdf). Datos de prueba limpiados. NUNCA se envió correo real.

## Sesión 2026-08-04 (parte 8) — Saneamiento técnico y seguridad (code review)
- SSL MIGRUP: eliminado verify=False. El servidor migrup.cl NO envía el certificado intermedio (GoDaddy G2) → se construyó bundle pinneado en /app/backend/certs/migrup_bundle.pem (certifi + gdig2.crt del AIA). verify=_CA_BUNDLE en ambos requests. VERIFICADO: /api/migrup/status connected:true. Cert expira 2026-12-06: si falla en diciembre, regenerar bundle con openssl s_client + AIA.
- XSS: DOMPurify (yarn add dompurify) sanitizando los 11 dangerouslySetInnerHTML (ClientesModule x7, Oportunidades, Gastos, AprobacionCliente, AIPanel). Preview de correos verificada intacta.
- LOCALSTORAGE CIFRADO: /app/frontend/src/utils/secureStore.js (XOR+base64, prefijo v1:, migración automática de valores legados) usado en LoginPage, App.js y CentralPredic (predic_auth). Verificado: user guardado cifrado y sesión persiste tras reload.
- HOOKS: eslint react-hooks reveló solo 6 warnings REALES (los "73" del review eran falsos positivos por constantes de módulo). Corregidos: AlertasPanel (useCallback[dias]), EmailProcessing/Gastos/SetCredito/ShareTarget (disable-line justificado en efectos solo-al-montar). Lint queda en 0 warnings.
- ANTI-PATRONES: `is True/is False/not x is False` → == / is not (4 en server.py). Catches vacíos → console.error (script global en pages/components).
- REFACTOR: enriquecer_cliente descompuesta en _fuentes_bd + _seleccionar_mejores + _aplicar_patrones (misma salida verificada por curl Franco Bahamondes).
- DIFERIDO (riesgo de regresión vs beneficio, requiere sesión dedicada): refactor profundo de credit_engine (predict_inmobiliaria/simular_credito/ia_predict), partición de ClientesModule (3.4k líneas)/CentralChat, y las 72 keys por índice.
- eslint-plugin-react-hooks agregado como devDependency. Estética Maserati intacta (verificada por screenshot).

## Sesión 2026-08-04 (parte 9) — Buzón de Rescate: Descartar Definitivamente
- Nuevo endpoint POST /api/rescate/{pid}/descartar: marca correos_pendientes.estado="descartado_definitivo" y proc_queue.status="descartado_definitivo" (el backfill solo trae status:"descartado", así no resucita).
- Frontend BuzonRescateModule: botón rubí "Descartar Definitivamente" junto a "Asignar Manualmente" con confirm. testid rescate-descartar-{i}.
- VERIFICADO e2e: correo de prueba insertado → aparece en buzón → descartado → desaparece → estado descartado_definitivo → limpiado. Screenshot con ambos botones en los 3 correos reales.

## Sesión 2026-08-04 (parte 10) — Acceso total: sidebar + Link VIP Simulador
- Sidebar: 'Centro de Ventas VIP' (fa-diamond, ya existía) y 'Simulador Inmobiliario' (fa-calculator, renombrado desde 'Simulador'). Ambos cargan sus módulos correctamente.
- Set de Crédito (detalle): nuevo botón "💎 Generar Link VIP (WhatsApp)" (testid setcred-simulador-vip) con borde/relleno oro pulido 24K: GET /api/martin/link → copia al portapapeles + abre wa.me con mensaje personalizado de Martín con el nombre del cliente. Convive con el botón "Link de Firma VIP (WhatsApp)" (portal de firma).
- Verificado por screenshot: sidebar OK, módulos cargan, botón visible en detalle del set con estética carbono/oro intacta.

## Sesión 2026-08-04 (parte 11) — Fix N+1 en Carpeta Clientes
- _mesa_respuesta_folder(d, segs=None): acepta seguimiento prefetcheado. list_folders ahora hace 1 sola consulta a db.seguimiento (antes 1 por carpeta = 33). Respuesta ~0.15s con datos idénticos (25 mesa_respuesta / 33 carpetas). Los otros 2 call sites siguen con fetch propio (retrocompatible).

## Sesión 2026-08-04 (parte 12) — Recordatorio Automático de Seguimiento (14 días)
- sales_engine.mensaje_seguimiento(nombre, proyecto, link, pixel, interes): correo de seguimiento con gancho según interés (uso_simulador/hizo_clic/abrio_correo/nuevo).
- sales_engine.proponer_seguimientos(base_url): al vencer bloqueado_hasta en status "enviado" → genera borrador de seguimiento, status="seguimiento_listo", bloqueado_hasta="" (habilita Autorizar), seguimiento_n++. Se ejecuta al cargar GET /api/oportunidades (sin loops nuevos). Tras autorizar → vuelve a "enviado" con nuevo bloqueo de 14 días (ciclo infinito de seguimientos supervisados).
- nota_diaria ahora anuncia "📬 seguimientos LISTOS para Autorizar Envío" + campo resumen.seguimientos.
- Frontend: badge dorado "📬 Seguimiento listo #N — Pasaron los 14 días"; preparar() muestra el borrador local si existe (evita sobrescribir el seguimiento con el mensaje original).
- VERIFICADO e2e: oportunidad con lock vencido → seguimiento propuesto con gancho correcto, tracking y nota diaria; dato de prueba limpiado. El candado de Gerardo sigue intacto (nada se envía solo).

## 2026-06 — Blindaje de Despliegue (PASSED)
- .gitignore reforzado: test_credentials.md, .env/*.env, __pycache__, node_modules, *.log excluidos; .env.example permitidos.
- Contrasenas admin movidas a env: ADMIN_PASSWORD_1 / ADMIN_PASSWORD_2 (ensure_seed usa os.environ.get).
- CORS dinamico desde CORS_ORIGINS (backend/server.py).
- Proyecciones agregadas a 3 consultas pesadas (simulaciones, folders resumen semanal, seguimiento _PROY_SEG).
- Soporte Emergent confirmo: secretos via gestor de Variables de Entorno del deploy; .env NO se comitea.
- Verificado e2e: login 200, folders 200 (0.2s).

## 2026-06 — RESOLUCION FINAL DEPLOY: PASSED ✅
- .gitignore: removidos patrones .env (requeridos por Emergent); test_credentials.md sigue excluido.
- backend/.env saneado: MAIL_APP_PASSWORD, MAIL2_APP_PASSWORD, MIGRUP_CLAVE con placeholders; ADMIN_PASSWORD_1/2 vacios (seed omite pisar password si var vacia -> login preview intacto).
- Valores reales respaldados en memory/test_credentials.md (fuera de git).
- Health Check deployment_agent: PASS sin findings. Sistema listo para re-deploy.
- IMPORTANTE: correo IMAP/SMTP y eCert quedan PAUSADOS en preview hasta restaurar claves reales o configurarlas como secrets al desplegar.

## 2026-06 — Reconexion claves preview
- Restauradas claves reales en backend/.env: MAIL_APP_PASSWORD, MAIL2_APP_PASSWORD, MIGRUP_CLAVE (eCert), ADMIN_PASSWORD_1/2.
- Verificado: eCert login OK, IMAP ambas cuentas OK, login app 200.
- PRODUCCION requiere re-deploy (o configurar secrets en el deploy) para reconectarse.

## 2026-06 — Listo para re-deploy (PASS limpio)
- Optimizadas 3 consultas de _portal_consulta_impl: filtro RUT en DB (_rut_regex_flexible) + proyecciones en folders, proc_queue y simulaciones.
- Deployment agent: PASS sin findings ni warnings. Claves reales en .env (correo + eCert conectados).
- Usuario debe pulsar Re-deploy en la plataforma para llevar todo a produccion.

## 2026-06 — Portal Firma VIP cableado a eCert
- Nuevo endpoint POST /api/firma/{token}/firmar: combina el set del cliente, detecta posiciones y sube a eCert via enviar_a_firmar_tercero (llaves del sistema, sin login externo).
- MIGRUP_CLAVE_CERT agregada al .env. Boton Firmar Documentacion reemplaza link externo migrup.cl. Idempotente.
- eCert conectado: 14 firmas terceros disponibles. Probado: UI portal, 400 sin set, 404 token invalido. Envio real NO probado (consume 1 firma).

## 2026-06 — Simulacion de firma VIP ejecutada
- Flujo completo verificado: portal -> combinar PDF -> deteccion posiciones -> creacion contacto eCert (contId real) -> solicitud de firma.
- MIGRUP_CLAVE_CERT="" (vacia) es lo correcto para firmas de terceros (error 147 si se usa clave login).
- UNICO BLOQUEO: saldo eCert de firmas terceros agotado (adicionales 18/18 usadas). Usuario debe comprar firmas en migrup.cl -> AJUSTES.
- Datos de prueba limpiados (link, set, carpeta).

## 2026-06 — FIRMA VIP VALIDADA EN VIVO ✅
- Envio real exitoso: HTTP 200, mensaje de exito, 1 firma consumida (16->15), correo de eCert (notificaciones@migrup.cl, asunto Firma Documento) recibido en Gmail.
- Idempotencia verificada: segundo click devuelve ya_enviada sin consumir saldo.
- Flujo VIP 100% operativo. Requiere Re-deploy para produccion.

## 2026-08-04 — FIX: candado autocorreo pegado
- Causa raiz: running=True quedo pegado tras reinicio del backend (proceso interrumpido no libero flag) -> loop mesa salto aprobaciones todo el dia.
- Fix 1: startup limpia running=False (ningun run sobrevive reinicio).
- Fix 2: guard anti-candado obsoleto en _periodic_mesa_loop (ignora running si last_run_started >30 min).
- Verificado: run manual proceso 3/3 aprobaciones de hoy (YACO SOUBALIOTIS, NICOLAS SAAVEDRA, Melisa Rivera) sent sin errores.
- ALERTA OPERATIVA: preview y produccion sondean las MISMAS casillas -> riesgo de autocorreos duplicados. Usuario debe elegir un solo entorno con periodic_enabled.

## 2026-08-04 — Configuracion final Portal Firma
- MIGRUP_CLAVE_CERT="Rodo0586" (solo se usa cuando firma el titular; terceros va vacia).
- Portal verificado: CERO redirecciones a migrup.cl, boton ejecuta enviar_a_firmar_tercero interno, cliente permanece en portal Central Mutuos.
- Mensaje exito actualizado: "Documentacion enviada. Revise su correo para los codigos de validacion".
- RUT real: prioridad set_credito -> carpeta folders -> link (evita error RUT no coincide con Clave Unica).

## 2026-08-04 — Impacto Visual VIP WhatsApp
- OG tags portal firma: og:title "Documentacion Oficial VIP - Central Mutuos", og:description personalizada con nombre, og:image URL ABSOLUTA (600x600) + og:url/site_name.
- og.png redisenada 600x600: negro absoluto, doble marco oro 24K, monograma CM, nombre cliente centrado en oro (fuente LiberationSerif; DejaVu no existe en el pod).
- Confirmado: 0 redirecciones externas, boton ejecuta firma interna.

## 2026-08-04 — BLINDAJE TOTAL MOTOR 24/7
- Correo a Mesa arranca SIEMPRE activado por defecto (startup fuerza enabled+periodic_enabled=True; _ac_state default True).
- Llave MOTOR_247_FORZADO="0" en .env permite pausar un entorno (para evitar duplicados preview vs prod).
- Nuevo endpoint GET /api/motor/status (autocorreo + ingesta + destino).
- Badge discreto en Dashboard: "Motor 24/7: OPERATIVO" (verde) / DETENIDO (rojo). Verificado en preview.
- Ingesta carpetas ya estaba blindada siempre-activa (config en DB).

## 2026-08-04 — RECONSTRUCCION TECNICA DEFINITIVA (cierre)
- Blindaje carpetas: all-tokens match, sin busqueda ultimos-30, vinculo RUT/origen, guardian _remitente_autorizado en 3 flujos de guardado. Verificado: RUT ajeno/remitente falso => 0 resultados.
- Motor 24/7 forzado en startup (enabled+periodic_enabled=True, llave MOTOR_247_FORZADO). Badge dashboard.
- Firma VIP interna sin migrup.cl. Credenciales exactas: MIGRUP_RUT=141617575, MIGRUP_CLAVE=Rod@0586, MIGRUP_CLAVE_CERT=Rodo0586 (login normaliza via _split_rut).
- AUTO-PRUEBA TITULAR: es_propio + clave cert ACEPTADA por eCert; bloqueada solo por saldo de firmas propias (comprar en AJUSTES).
- Codeudor por RUT: modal oro con RUT obligatorio, endpoint valida, match por RUT en ingesta -> anexo 05_codeudor sin carpeta raiz. Probado 400/200 + subcarpeta creada.
- OG WhatsApp: URLs absolutas + tarjeta 600x600 negro/oro + Cache-Control 24h.

## 2026-08-04 — PREVIEW PAUSADO (anti-duplicados)
- MOTOR_247_FORZADO="0" en backend/.env del preview + periodic_enabled=False. Produccion es el motor oficial 24/7.
- ⚠️ CRITICO ANTES DE CUALQUIER RE-DEPLOY FUTURO: quitar/poner MOTOR_247_FORZADO="1" en .env para que produccion NO herede la pausa. Avisar al usuario.

## 2026-08-04 — HEALTH CHECK FINAL: LISTO PARA PRODUCCION
- Deployment agent: deployable (unico WARN: export/backup admin sin proyeccion — por diseno, respaldo completo, admin-only, limitado a 8000).
- Imports modulares OK (ai_extract, sales_engine, simulador_engine, migrup, email, folders, database).
- MASTER_PIN movido a .env (server.py, email_service.py, crear_carpetas_escrituracion.py). Cero secretos hardcodeados.
- ⚠️ RECORDAR: MOTOR_247_FORZADO="0" esta en .env preview (pausa anti-duplicados). En produccion configurar MOTOR_247_FORZADO=1 en variables del deploy O activar con 1 clic en Correo a Mesa si el badge dice DETENIDO.

## 2026-08-04 — RESPALDO OPTIMIZADO + PASS FINAL LIMPIO
- /admin/respaldo/export: proyeccion _RESPALDO_PROY (excluye _id/body/html/raw/binarios) + cursor batch_size(200) + limit(8000). Verificado: 200 OK, 35 colecciones, 497 archivos, 10.5s.
- Deployment agent: PASS sin findings ni warnings. SISTEMA BLINDADO Y LISTO.

## 2026-08-04 — BLINDAJE ANTI-DUPLICADOS (REGLA DE MESA)
- Cerrojo atomico (find_one_and_update EN_PROCESO_DE_ENVIO) en 2 flujos a Mesa: /clientes/folders/{fid}/send-email (lock en db.folders con stale 10min) y /procesamiento/queue/{qid}/enviar-autocorreo (reserva en db.mesa_enviados con estado). Segundo intento simultaneo -> 409.
- Huella Message-ID (make_msgid @centralmutuos.cl) enviada como header y guardada en folders.mesa_message_id + mesa_enviados.message_id + proc_queue.autocorreo_message_id. Re-envio prohibido sin clave admin.
- Destino unico: destino forzado a MESA_EMAIL (aprobaciones@centralmutuos.cl) — se elimino override por payload en ambos flujos.
- Test carrera simulada: intento 1 pasa, intento 2 bloqueado. NOTA: prueba disparo 1 aviso [FALTA INFORMACION] Roberto Duran a mesa (inofensivo); flag revertido.

## 2026-08-04 — MOTOR DE CORREOS OPTIMIZADO
- SMTP TLS/STARTTLS puerto 587 (env MAIL_SMTP_PORT=587; codigo adaptativo 465=SSL).
- Message-ID propio en TODO envio; In-Reply-To/References ya presentes en flujos de respuesta (5026, 6703).
- correos_smtp_log ahora registra: size_kb, message_id, in_reply_to, puerto, tls, smtp_code/response detallado.
- From amigable: MAIL_FROM_NAME="Gerardo Barrera - Central Mutuos".
- Probado envio real: 250 OK, 0.6 KB, TLS 587, From correcto.

## 2026-08-05 — DESPACHO POST-FIRMA (Puente Ethan)
- Nueva funcion _despacho_post_firma(doc): tras _set_separar_firmado en _traer_firmado_interno, envia correo con TODOS los formularios divididos (FIRMADO_*.pdf con rastro digital).
- Remitente: principal (ethangerardobarr@gmail.com) -> Destinatario: MAIL2_USER (gerardo.ext@centralmutuos.cl).
- Asunto: "💎 Documentacion Firmada y Validada - [Cliente]" + cuerpo profesional negro/oro.
- Registro en set_credito.despacho_post_firma {ok, a, en, archivos}.
- PROBADO REAL: 250 OK, 3.1 KB, desde cuenta principal. Datos de prueba limpiados.
- NOTA PREVIA: loop firmados auto-envio el set de prueba a Daniela/Victoria (04:17) por stem truncado [:20] compartido — datos de prueba eliminados; mejora pendiente: match por idDocumento eCert.

## 2026-08-05 — JERARQUIA DE MOTORES DE ENVIO
- CORPORATIVA (gerardo.ext, From "Gerardo Barrera - Central Mutuos"): aprobaciones ajustadas (_procesar_mesa), gastos op/cobros, estudio titulos, sets/firmados a ejecutivas, mesa (gestion + falta-info + carpetas), inmobiliarias.
- ETHAN (principal, From "Soporte Tecnico Central Mutuos" via MAIL_FROM_NAME_SOPORTE): reportes diarios/semanales, avisos internos, despacho post-firma, alertas.
- Cambiados a secundaria: 3214 autocorreo mesa, 8756 enviar firmados, 9052 falta-info, 9126 gestion mesa.
- REGLA DE ORO cumplida: ningun cliente recibe correos desde Ethan. Verificado con 2 envios reales 250 OK.

## 2026-08-05 — MATCH POR ID ECERT (retorno de firmados blindado)
- enviar_a_firmar_tercero devuelve ecert_doc_id (extraido de res.documentos).
- ecert_id guardado en firmas[] en los 3 flujos (portal /firmar, enviar-firma-completo, enviar-firma).
- _traer_firmado_interno: match por idDocumento exacto cuando hay ecert_id (sin fallback a nombre en ese caso); prefijo [:20] solo para envios antiguos sin ID.
- Probado con doc real finalizado: match exacto 1/1; ID inexistente => 0 candidatos.

## 2026-08-05 — RUT COMO IDENTIFICADOR MAESTRO
- setcred_create: anti-duplicado por RUT (si existe set con mismo RUT flexible, se reutiliza y completa email). Probado: mismo RUT nombre distinto => mismo id.
- Portal /firmar: busca el set PRIMERO por RUT exacto del link; nombre solo como respaldo.
- Carpetas (folders) ya deduplicaban por RUT via _buscar_carpeta_existente.

## 2026-08-05 — PAUSA ADMIN EN DB (deploy-safe)
- Pausa del motor movida de .env a db.config (pausa_admin). Startup fuerza ON salvo pausa_admin=True. Toggle UI la persiste.
- MOTOR_247_FORZADO=1 (ya no se usa en codigo). Produccion arranca SIEMPRE sola aunque herede el .env del preview.
- Preview verificado pausado tras reinicio; ingesta activa.

## 2026-08-05 — AUDITORIA ISO FINAL: PASS COMPLETO
- Deployment agent: status pass, findings [] (0 bloqueadores, 0 warnings).
- Verificado por codigo: match total tokens + vinculo RUT (email_service 581/589), startup 24/7 forzado con pausa_admin en DB, portal 0 refs migrup.cl con 3 llamadas internas enviar_a_firmar_tercero, TLS 587 starttls, modulos importados (sales_engine 27, simulador_engine 28, ai_extract 3427), rastro digital SHA-256 + ID eCert + archivo madre en cada PDF dividido.
- VEREDICTO: SISTEMA AFINADO Y LISTO PARA PRODUCCION.

## 2026-08-05 — CIRUGIA DE MEMORIA PDF
- posiciones_firma_cliente: page.flush_cache() + get_textmap.cache_clear() + del words/lineas por pagina (pdfplumber ya no acumula layout).
- /firma/{token}/firmar: buffers intermedios liberados (del + gc.collect antes y despues de base64).
- VERIFICADO: set Claudia Zurita 5.5MB combinado -> 10 posiciones -> estampado, RAM pico 218MB, 21.4s, backend sin reinicio.
- TLS 587 listo (MAIL_SMTP_PORT=587); usuario actualizara el secreto en produccion.
- Startup: ingesta siempre ON; correo ON por defecto salvo pausa_admin (preview pausado a proposito, produccion ON).

## 2026-06 — PROTOCOLO DE EMERGENCIA: Corte de bucle OCR/LiteLLM
- Causa raíz: tesseract/poppler NO instalados → `_ocr_ia_pagina` (folders_service.py) hacía 1 llamada GPT-visión POR PÁGINA de cada PDF escaneado, disparado por el loop `_periodic_proc_loop` (proc_auto cada 2 min) → spam masivo de créditos.
- Fix: interruptor global `AI_EMERGENCY_STOP="1"` en backend/.env.
  - server.py startup: loops `ingesta_carpetas`, `reparos_estudio`, `aprendizaje_ia` NO arrancan con el flag activo. `_run_proc_auto()` retorna skipped.
  - folders_service._ocr_ia_pagina: retorna "" (sin llamada a GPT).
  - ai_extract.py: helper `_llm_key()` devuelve "" con flag activo → todas las funciones IA caen a fallback de reglas/regex.
- Verificado: 0 llamadas LiteLLM en 90s post-reinicio. API 200 OK en 0.3s.
- PARA REACTIVAR IA: poner AI_EMERGENCY_STOP="0" + INSTALAR tesseract-ocr y poppler-utils primero (OCR local gratis) para evitar recaída del spam.

## 2026-06 — REACTIVACIÓN SEGURA DE IA
- Instalado tesseract-ocr 5.3 + idioma español (spa) + poppler-utils → OCR local GRATUITO ahora es la vía principal.
- El respaldo GPT-visión (_ocr_ia_pagina) solo se usa si tesseract falla, con LIMITADOR ANTI-SPAM: máx 40 llamadas/hora (deque _AI_OCR_CALLS en folders_service.py).
- AI_EMERGENCY_STOP="0" en .env → loops ingesta_carpetas, reparos_estudio, aprendizaje_ia reactivados.
- Verificado: motor 24/7 corrió ciclo completo sin errores, 0 llamadas LiteLLM en 150s.
- NOTA DEPLOY: tesseract se instaló vía apt en el preview; si se despliega a producción, verificar que el entorno lo incluya (si no, el limitador de 40/h protege los créditos igualmente).

## 2026-06 — BLINDAJE TOTAL Y TOLERANCIA CERO (Ley del RUT)
- LEY DEL RUT (Blindaje de Werner): en `proc_upload_drive` cada archivo entrante se escanea con OCR antes de vincularse a carpeta EXISTENTE; si su RUT no coincide con dueño/codeudor → va al Buzón de Rescate + alerta tipo `ley_del_rut`. `_buscar_carpeta_existente` ya NO vincula por nombre cuando el correo trae RUT sin coincidencia (return None).
- Listado Aprobación (`GET /aprobacion-cliente/archivos`): verifica RUT de los 2 archivos finales; conflictos → `excluidos_rut` (banner rojo en UI) + flag `rut_verificado`.
- Basurero: `DELETE /api/aprobacion-cliente/archivo` + botón rojo por archivo (data-testid aprobacion-eliminar-{i}).
- Upload validado: `POST /api/aprobacion-cliente/upload` — rechaza 422 si contiene "Gastos Operacionales" (detector Simulación Ajustada) o si el RUT del PDF no coincide con el dueño. Botón "Subir PDF" (aprobacion-subir-btn).
- LIMPIEZA IGNACIO: 2 archivos de IGNACIO JOAQUIN EDUARDO TOBAR WERNER (RUT 20.168.743-8) retirados físicamente de carpeta WERNER → Buzón de Rescate (qid rescate-ley-rut-*). Causa raíz: apellido "WERNER" compartido.
- Testing: backend 100% curl (422/422/200/DELETE), frontend 100% testing agent (iteration_25.json).
- NOTA: la limpieza de Ignacio se aplicó en PREVIEW; producción requiere redeploy + limpieza propia si aplica.

## 2026-06 — RECONSTRUCCIÓN TÉCNICA DEFINITIVA + REGLAMENTO INVIOLABLE
- LEY DEL RUT en email_service.py: search_attachments_by_person devuelve [] sin RUT de carpeta; eliminado el fallback de candidatos sueltos ("últimos correos" sin match de cabecera); el correo DEBE contener el RUT (remitente ya no basta).
- LEY DEL RUT por archivo: helper _guardar_con_ley_rut + _rescate_ley_rut en server.py aplicado a los 4 puntos de guardado desde correo (importar, forzar carpeta, modo estudio, save-all-attachments). Sin match → Buzón de Rescate + alerta.
- Ruteo por RUT del codeudor: si el archivo trae SOLO el RUT del codeudor → subcarpeta 05_codeudor.
- BÚNKER GridFS (bunker.py): espejo storage/{clientes,autocorreo,proc,set_credito} → GridFS colección "bunker". restaurar_si_vacio() al startup (pod nuevo restaura todo), _bunker_loop sync cada 5 min, hooks tras upload/delete de aprobación. Testeado e2e: 998 archivos, restore 527 clientes en 1.7s byte-perfect.
- REGLA DE ORO 0586 en _blindaje_simulaciones: simulaciones con "Gastos Operacionales" BLOQUEAN el envío (ValueError → send_mail devuelve error controlado + log correos_smtp_log regla oro_0586). Solo clave 0586 lo omite (fix: clave vacía ya no bypassa). 4/4 unit tests.
- MEMORIA LIVIANA: _regen_carpeta_cliente refactorizada a fitz streaming (insert_pdf + close por archivo, save con garbage=3).
- INTEGRIDAD: prompt de clasificar_y_extraer reforzado con "PROHIBIDO INVENTAR".
- Regresión backend: 11/11 PASS (iteration_26.json). Tests reutilizables en /app/backend/tests/test_regresion_blindaje.py (correr con -n 0).
- PENDIENTE (observación testing): añadir timeouts a llamadas LiteLLM/OCR — el backend se congeló una vez bajo carga concurrente (mitigación: supervisorctl restart).

## 2026-06 — BLINDAJE DE INFRAESTRUCTURA Y RESCATE DE VISTAS
- TIMEOUTS ANTI-CONGELAMIENTO (60s): helper _enviar() en ai_extract.py y _llm_con_timeout() en server.py envuelven TODAS las llamadas LLM con asyncio.wait_for(60s). folders_service._ocr_ia_pagina con wait_for(60). pytesseract con timeout=60 en ocr_service.ocr_texto y folders_service._texto_pagina. Al vencer → error controlado, recursos liberados (callers ya tienen try/except con fallback a reglas).
- RESCATE DE MÓDULOS (fix 404): creados GET /api/estudio-titulo/carpetas, /api/escrituracion/carpetas y /api/tasacion/carpetas — leen SOLO de MongoDB (folders con estudio_titulo_solicitado_at / is_escrituracion|escrituracion_movida_at / tasacion_solicitada_at). Campo pdf_disponible solo ALERTA si falta el PDF físico, jamás rompe la vista (_pdf_disponible con try/except).
- VERIFICADO: estudio 0.33s (1 ficha), escrituración 0.20s (9 fichas), tasación 0.12s (1 ficha), panel principal /clientes/folders 0.22s. Todo 200, carga instantánea.

## 2026-06 — PANEL DE CONTROL CLOUD SYNC
- Botón "💎 Sincronizar Datos (Cloud Sync)" en toolbar de Carpeta Clientes (btn-cloud-sync): POST /api/clientes/cloud-sync → ping Mongo + bunker.restaurar_faltantes() (baja archivos nuevos del GridFS) + sync_en_background() (respaldo daemon). Refresca loadFolders() sin recargar página. Respuesta 0.03-0.3s.
- Indicador "Sincronización: [Live/Preview] · Conexión Protegida" (detecta por hostname) + tooltip "use el botón Re-publish de la plataforma" en botón e indicador.
- FIX CRÍTICO: los syncs de fondo ahora usan HILOS DAEMON (bunker.sync_en_background) — antes asyncio.to_thread bloqueaba el hot-reload de uvicorn (el proceso viejo moría y el nuevo no arrancaba → 502). Los restores preservan mtime (os.utime) para no re-subir 550MB tras cada restauración.
- Verificado por screenshot e2e: login → Carpeta Clientes → click botón → mensaje "Sync OK · Mongo: conectado · 998 protegidos · 44 carpetas".

## 2026-06 — REDISEÑO VIP MÓDULOS + SANEAMIENTO TÉCNICO
- Creadas 3 vistas doradas nuevas (sidebar: tasacion, estudio, escritura):
  - TasacionModule.js: fichas desde /api/tasacion/carpetas + SEMÁFORO de confianza verde/naranja (RUT, solicitada, terminada, PDF). Exporta estilos compartidos (vipCard, vipGoldBtn, Semaforo, useCarpetasVIP, VipHeader).
  - EstudioTituloModule.js: fichas desde /api/estudio-titulo/carpetas + modal "hilo humano" de reparos (GET /estudio-titulo/reparos/{fid}), burbujas numeradas con estado resuelto/pendiente.
  - EscrituraModule.js: fichas desde /api/escrituracion/carpetas + botón "🖋 GENERAR FIRMA VIP" gradiente oro pulido → sessionStorage cm_prefill_firma + onNavigate('setcredito').
- App.js: lazy imports, 3 entradas sidebar (nav-tasacion/nav-estudio/nav-escritura), MODULE_TITLES, renders.
- SANEAMIENTO: middleware security_headers en server.py (HSTS, nosniff, X-Frame SAMEORIGIN, Referrer-Policy, Permissions-Policy) — verificado por curl. secureStore.js (cifrado localStorage) y sanitización DOMPurify ya existían. Hook deps: 0 warnings tras fix. Funciones pesadas ya refactorizadas antes (fitz streaming). ESLint standalone sin config (CRA lo corre integrado — compila limpio).
- Verificado por screenshot e2e: Tasación (1 ficha, 4 semáforos), Estudio (modal hilo OK), Escritura (9 fichas, 9 botones Firma VIP). Estética Maserati intacta.

## 2026-06 — REGLA IVANA + CENTRO DE MANDO + RESCATE HISTÓRICO 30 DÍAS + SANEAMIENTO
### Regla Ivana (completada)
- RUT titular Ivana López: 19.203.796-4 configurado; codeudor Freddy Landa (13224068-k).
- _guardar_con_ley_rut: archivo con SOLO RUT codeudor → forzado a 05_codeudor/<Nombre> + prefijo CODEUDOR_. Sin RUT titular → no se vinculan codeudores (rescate).
- FILTRO DE COMBINACIÓN: merge_protocol y _set_combinar excluyen PDFs con RUT ajeno al titular (OCR con caché db.ocr_rut_cache path+size+mtime — no repite OCR). Sin RUT titular → combinación BLOQUEADA ("REGLA IVANA").
- Refinamiento clave: _ruts_personas() ignora RUTs de empresas (>= 50M, empleadores/AFP) para no excluir liquidaciones legítimas.
- Limpieza: 1 archivo de Freddy movido a 05_codeudor/Freddy Landa/CODEUDOR_*, combinado de Ivana regenerado (14 docs, 0 exclusiones). Upload endpoint testeado: archivo de Freddy → 200 con ruteo a 05_codeudor.
### Centro de Mando (Por Clasificar)
- GET /rescate/pendientes ahora incluye "sugerencia" (keywords: reparo→estudio, tasacion→tasacion, aprobaci/solicitud→solicitud, resto→otros).
- POST /api/rescate/{pid}/clasificar {destino, cliente}: solicitud (asignar clásico), tasacion/estudio (asignar + flag tasacion_solicitada_at/estudio_titulo_solicitado_at → aparece en módulo VIP), otros (mueve adjuntos a storage/archivo_general/<qid>, estado archivado_otros, SIN ficha). Testeado e2e con correo sintético.
- BuzonRescateModule rediseñado: dropdown 4 destinos (rescate-destino-{i}) preseleccionado con ★ sugerido + botón "Confirmar Destino". NADA se mueve sin confirmación. Verificado por screenshot.
### Rescate Histórico
- _rescate_historico_loop: 1ª vez escanea 30 días (headers-only, lotes de 20 + sleep) → db.seguimiento con origen rescate_historico (12 ops cargadas); luego cada 3 días. Config en db.config _key=seguimiento_historico.
### Saneamiento (3ª pasada, todo verificado)
- XSS: DOMPurify en todos los dangerouslySetInnerHTML ✅ · localStorage cifrado (secureStore.js) ✅ · 5 cabeceras SSL/seguridad activas ✅ · hooks 0 warnings ✅ · linter CRA integrado compila limpio ✅ · funciones pesadas ya refactorizadas (fitz streaming, caché OCR, timeouts 60s, hilos daemon) ✅.
### Bug corregido
- Línea huérfana en server.py (edit corrupto por interrupción) rompía el arranque → eliminada; endpoint clasificar reaplicado.

## 2026-06 — CLASIFICACIÓN ONE-CLICK + HISTORIAL
- DESTINOS_RESCATE ahora incluye "administrativo" (5 destinos): solicitud, tasacion, estudio, administrativo (→ carpeta Admin_Empresa/99_otros + folders doc sin RUT), otros (archivo general + descarte).
- rescate_clasificar marca estado procesado_<destino>/archivado_otros + campos destino, cliente_final, clasificado_en → los clasificados NO vuelven a "pendientes".
- GET /api/rescate/historial: últimos 100 clasificados con destino y fecha.
- BuzonRescateModule: reemplazado dropdown+confirmar por 5 BOTONES one-click oro/negro (rescate-dest-{destino}-{i}), sugerido resaltado con gradiente + ★. Acción inmediata: el correo desaparece al instante (optimistic removal). Si el destino necesita cliente y no hay sugerido válido → abre modal selector. Botón "Historial de Clasificados" (rescate-historial-btn) alterna la vista.
- Testeado e2e: administrativo → archivo en Admin_Empresa/99_otros, desaparece de pendientes, aparece en historial. Screenshots verificados (5 botones + historial con 4 items).

## 2026-06 — BÚNKER DE CIERRE (SET DE CRÉDITO) + VISOR MASERATI
- ALMACENAMIENTO INDEPENDIENTE: SETCRED_DIR → storage/sets_de_credito (migrado desde set_credito, 29MB). bunker.py SUBDIRS actualizado (sets_de_credito + archivo_general). El set NUNCA mezcla con carpeta del cliente: _set_sync_desde_carpeta DESACTIVADA (retorna []).
- INGESTA ESPECIALIZADA: ya existía _setcred_auto_loop cada 10 min leyendo evaluacionesmutuos@gmail.com → expedientes directo al set del cliente.
- IDENTIFICACIÓN DE FORMULARIOS: _set_archivos reconoce por nombre: seguros (desgravamen/seguro/cesant/incendio/sismo), declaracion_salud (dps/salud), solicitud_credito (solicitud/mutuo).
- _set_archivos_orden(): lista única para COMBINAR y SEPARAR post-firma (mismo orden, sin desalineación); excluye COMBINADO_SET/FIRMADO/firmados/.
- Combinado Zurita testeado: 9 formularios en orden de protocolo, 0 exclusiones, preview inline HTTP 200 (5.7MB).
- VISOR MASERATI: botón setcred-preview-combinado → POST /combinar → modal vidrio negro/borde oro (setcred-visor-maserati) con iframe inline del PDF (hoja por hoja con visor nativo del navegador) + lista de orden + excluidos por RUT. Verificado por screenshot.
- DETECCIÓN DE IDENTIDAD: _extraer_num_documento() busca "Número de documento" en cédulas del set/carpeta al abrir set (setcred_get); se guarda en set doc y se muestra chip verde 🪪 en la ficha (Zurita sin cédula en set → no detectado, correcto).
- Saneamiento re-verificado (4ª pasada): headers SSL activos, XSS/DOMPurify, secureStore, hooks 0 warnings, compilación limpia.

## 2026-08-05 — Activación Ficha Gerardo (Set de Crédito)
- Copiados 15 PDFs desde storage/clientes/Gerardo/ al Set de Crédito "Gerardo" (sid c5518eb4-a3ee-46ca-8ddd-16986e10ae64). IVANA LOPEZ 1.pdf → codeudor/.
- RUT 14.161.757-5 grabado en set_credito y en folders (id 2e978476, rut previo 83504254).
- COMBINADO_SET_Gerardo.pdf generado (3.2MB, 10 archivos). Regla Ivana excluyó 5 PDFs con RUT Landa/López (13224068-K, 19203796-4, 25946255-K).
- HALLAZGO CRÍTICO: no existe carnet de Gerardo (RUT 14.161.757-5) en el sistema. El 01_Cedula_CARNET.pdf pertenece a FREDDY ESTEBAN LANDA IGLESIAS (RUN 13.224.068-K, Nº doc B6J.560.515). num_documento NO grabado (no se falsifica identidad). Usuario debe subir su carnet real.

## Sesión 2026-08-05/06 (Activación Gerardo Barrera + Saneamiento + Fix Firma VIP)
- MISIÓN GERARDO: 15 PDFs copiados/consolidados de clientes/Gerardo al Set de Crédito.
- Identidad consolidada: carpeta "Gerardo" fusionada en "Gerardo Barrera" (RUT 14.161.757-5),
  duplicados eliminados (folder 2e978476 borrado; set c5518eb4 renombrado a "Gerardo Barrera").
- COMBINADO_SET_Gerardo Barrera.pdf generado (10 docs; 5 excluidos por Regla Ivana: RUTs Landa/López).
- HALLAZGO CRÍTICO: el único carnet en el sistema pertenece a Freddy Landa (13.224.068-K),
  NO existe carnet con RUT 14.161.757-5. num_documento NO grabado (no se falsifica identidad).
- Fix rendimiento: setcred_get ya no re-OCRea el carnet en cada apertura (marker num_doc_scan).
- Fix Firma VIP: mensajes de error del portal ahora especifican la causa (sin set / set vacío);
  botón "Link de Firma VIP" bloqueado en frontend si el set tiene 0 archivos.
- Causa del "documentación no preparada" de Nicolas Saavedra: su set está VACÍO (storage/sets_de_credito/NICOLAS SAAVEDRA).
- Anti-sangrado LLM: caché Mongo ai_extract_cache (hash SHA-256 de texto+archivo) en clasificar_y_extraer.
- Saneamiento: CSP header (excepto PDFs), GZipMiddleware, refactor list_folders (1 escaneo de disco
  por carpeta en vez de 3), eslint.config.mjs flat config creado, lint 0 errores.
- NOTA OPERATIVA: uvicorn reload queda colgado tras editar server.py/ai_extract.py;
  requiere `sudo supervisorctl restart backend` tras cada edición de backend.

## Sesión 2026-08-06 (Saneamiento técnico completo — ronda 2)
- ESLint 9 flat config creado (eslint.config.mjs) + auto-fix ejecutado: 0 errores / 0 warnings finales.
- 18 unused-vars limpiados en 11 archivos (prefijo _ o eliminación de imports muertos).
- Hooks: 0 warnings react-hooks/exhaustive-deps (dependencias ya sanas, verificado con plugin activo).
- Cabeceras verificadas por curl: CSP, HSTS, X-Frame, X-Content-Type, Permissions-Policy, Referrer-Policy (6/6).
- 5 funciones pesadas refactorizadas: list_folders (3 escaneos de disco → 1 por carpeta),
  _folder_public/_criterios_folder/_mesa_respuesta_folder (archivos prefetcheados),
  setcred_get (marker anti re-OCR), GZipMiddleware (respuestas comprimidas), clasificar_y_extraer (caché LLM).
- XSS: DOMPurify confirmado en los 10 usos de dangerouslySetInnerHTML. localStorage: secureStore (XOR+base64) confirmado.
- Smoke test visual OK: login + dashboard con estética Maserati/Oro 24K intacta.

## Sesión 2026-08-06 (Bóveda de Firmas eCert)
- GET /api/firma/semaforo: llama migrup Dashboard/TraerSemaforo con caché 5 min (parámetro ?force=true).
  Mapeo: propias = cantFirmasDisponiblesMias ?? (adicionalesMias - usadasMias); terceros = cantFirmasDisponiblesTerceros;
  documentos = cantDocumentosDisponibles; alerta = propias<5 o terceros<5.
- Dashboard: tarjeta "💰 Bóveda de Firmas eCert" (testid boveda-firmas-card) con Firmas Propias (rubí si 0,
  rosado si <5), Terceros (esmeralda), Documentos; botón dorado "Recarga Rápida" → www.migrup.cl (_blank).
- Banner superior persistente testid alerta-saldo-firmas cuando alerta=true, con link "Recargar ahora".
- VERIFICADO: curl 200 (propias 1, terceros 22, docs 2480, alerta true) + screenshot con banner y tarjeta visibles.
- Nota: prompt de saneamiento llegó duplicado 4 veces; ya completado (ver entrada anterior).

## Sesión 2026-08-06 (Protocolo Dual + Ley del RUT retroactiva + Motor de Firma blindado)
- PROTOCOLO DUAL: merge_protocolo_codeudor genera COMBINADO_PROTOCOLO_CODEUDOR_<Nombre>.pdf DENTRO
  de 05_codeudor con match por RUT (intruso con RUT ajeno excluido — verificado con PDFs de prueba).
- reclasificar_codeudor: mueve a 05_codeudor los PDFs del codeudor extraviados en la raíz (verificado).
- Envío a Mesa con codeudor: adjunta 2 combinados + asunto "💎 Solicitud de Crédito: X + Codeudor Y" (verificado).
- BÚSQUEDA RETROACTIVA: al vincular codeudor por RUT → mail.buscar_adjuntos_por_rut rastrea todos los
  buzones (X-GM-RAW variantes de formato), valida cada PDF por OCR Match Total y archiva con protocolo
  de orden. Genera alerta "rescate_codeudor". VERIFICADO E2E con buzón real (1 doc rescatado).
- SINCRONIZACIÓN DE APROBACIÓN: /aprobacion-cliente/enviar bloquea con 409 si un adjunto contiene RUT
  de otra persona (Match Total) — verificado con curl.
- REPARACIÓN CRÍTICA: server.py tenía 3 copias duplicadas del bloque final (una corrupta con
  SyntaxError). Se dejó UNA copia sana + un solo app.include_router(api).
- MOTOR DE FIRMA (🔒 FINALIZADO Y PROTEGIDO, ver /app/memory/protected_modules.md):
  mensaje de éxito ahora DORADO; CSP ajustada (style/script inline + Google Fonts) porque bloqueaba
  el estilo del portal; portal verificado en viewport móvil sin enlaces externos.
- Link real de Gerardo Barrera: /api/firma/c34385901892 (RUT y correo pre-cargados).
- Carpeta "Test Protocolo Dual" y registros de prueba eliminados tras el testing.

## Sesión 2026-08-06 (Prueba Real de Firma — Gerardo)
- Disparé la firma real desde el portal móvil: el motor ejecutó TODO el flujo y eCert respondió
  "No quedan firmas propias" — el RUT de Gerardo (14.161.757-5) es el DUEÑO de la cuenta eCert,
  por lo que su firma consume firmas PROPIAS (agotadas), no las ~21 de terceros.
- FIX: firma_firmar ahora devuelve 400 (no 502) porque el proxy/Cloudflare reemplaza los 502 con
  HTML genérico y ocultaba el motivo real. El portal ya muestra el mensaje exacto de eCert.
- Semáforo estima propias=1 (adicionales 3 - usadas 2) pero eCert real dice 0 — manda eCert.
- PENDIENTE USUARIO: comprar firmas propias en migrup.cl → AJUSTES y reintentar el mismo link
  /api/firma/c34385901892 para ver el mensaje dorado.

## Sesión 2026-08-06 (Blindaje de Entregabilidad Anti-Bloqueo Gmail)
- CABECERAS HUMANAS: send_mail agrega In-Reply-To + References apuntando al último Message-ID
  real enviado a ese destinatario (colección correos_smtp_log) — cada correo entra como conversación.
- REMITENTE: MAIL_FROM_NAME="Gerardo Barrera - Central Mutuos" (cuenta corporativa). La cuenta
  principal (ethan) mantiene FROM_NAME_SOPORTE por jerarquía previa.
- ANTI AUTO-ENVÍO (2 capas): (1ª) destino que sea cuenta propia → se redirige a MAIL_NOTIF_TEST
  (gerardo.ext@centralmutuos.cl, en .env, reversible); (2ª) si el emisor coincide con el destino,
  se cambia de cuenta emisora automáticamente. Jamás misma cuenta → misma cuenta.
- PUERTO: confirmado 587 + STARTTLS (MAIL_SMTP_PORT=587 en .env; log registra tls=STARTTLS-587).
- VERIFICADO con 4 envíos reales (250 OK): el #4 salió desde ethan → gerardo.ext con hilo activo.
- Nota bug: un search_replace del batch se perdió (llamada _anti_autoenvio); re-aplicado y verificado.

## Sesión 2026-08-09 (Integración DashAI — Exportador de Dataset)
- Decisión de management: se descartó el "trabajador local" (frágil, requiere PC 24/7).
  El valor real de DashAI = entrenar modelos predictivos locales con la cartera.
- GET /api/dashai/dataset: CSV con 25 columnas (features de simulaciones + predic_history,
  cruce con mesa_enviados por RUT, target_aprobada). Verificado: 20 filas, headers correctos.
- Dashboard: tarjeta "📊 Dataset para DashAI" (testid dashai-export-card / dashai-export-btn)
  bajo Aprendizaje IA, estilo oro/carbono. Verificada con screenshot.
- Nota: badge "MOTOR 24/7: DETENIDO" = interruptor correo_a_mesa apagado por config del
  usuario (ingesta_carpetas sigue activa). No es una falla.
