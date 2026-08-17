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

## Sesión 2026-08-09 (Cerebro Predictivo + Contraloría + Panel 0586 + Reglamento Maestro)
- mesa_brain.py: modelo local (180 días, sin créditos): base de aprobación, motivos de rechazo
  minados, recalibración automática si el modelo tiene >24h (aprendizaje continuo).
- Endpoints: POST /api/mesa-brain/calibrar, GET /api/mesa-brain/modelo, GET /api/contraloria/casos.
- Pestaña '🔍 Contraloría' (ContraloriaModule.js): tabla Aprobaciones vs. Realidad; aprobaciones de
  MESA que rompen criterios (docs faltantes, CMF, 2.000 UF, LTV>máx, DIV/renta>máx) → BAJO AUDITORÍA
  (rubí); validados en oro. Marca estado_auditoria en seguimiento.
- Oportunidades: prob_mesa + objetivo_whatsapp (>=85% badge dorado 🎯), orden descendente.
- Panel Criterios editable (CriteriosModule.js reescrito): 'Configuración de Escenarios' BTG/Ameris,
  inputs numéricos, botón dorado Guardar → modal clave. Clave errónea = 403 + alerta seguridad +
  cambios descartados; 0586 = guardado con prioridad suprema (manual_override en db.config criterios).
- Reglamento Maestro soldado: _stats_mesa entrega criterios+valor_uf; _prob_aprobacion_folder marca
  NO VIABLE (0%) si renta < renta_min_uf (30 UF BTG sin subsidio); castigos 15%/20% ya existían en
  credit_engine (verificado). Contraloría valida LTV y DIV/renta exactos por última simulación.
- BUGS REPARADOS EN SESIÓN: (1) fragmento duplicado al final de server.py (SyntaxError) tras edición
  — recortado; (2) babel RangeError por componente JSX recursivo en CriteriosModule → función plana.
- TESTING: iteration_27.json — frontend 100%, 0 bugs, sin regresiones. Criterios restaurados tras test.

## Sesión 2026-08-09 (Calibración Prioritaria 60 días)
- mesa_brain._analisis_60: ventana_60 (base, apro/rech 60d), cruce con reglamento BTG/Ameris de
  db.config criterios: aprobaciones sobre LTV/DIV máximos → "Ajuste de Mercado sugerido";
  base 60d << 180d → alerta de MESA más estricta. Tendencia: categoría dominante de rechazos
  ("La MESA está priorizando X sobre Y").
- Contraloría: default dias=60 (Regla de Oro), tarjetas Regla de Oro 60d + base 180d,
  bloque tendencia (testid contraloria-tendencia) y ajustes (contraloria-ajustes).
- Dashboard: nota "DashAI: Tendencia últimos 60 días..." (testid dashai-tendencia).
- BUGS: colisión de batch en mesa_brain.py (edición perdida, reaplicada) y cola duplicada en
  ContraloriaModule.js (recortada + bloques reinsertados). LECCIÓN: no editar el mismo archivo
  con 2 search_replace en un mismo batch paralelo.
- VERIFICADO: calibrar → base 60d 97.8%, 45/1, tendencia "renta mínima sobre carga financiera";
  screenshot Contraloría + Dashboard OK.

- 2026-08-09 — **Modo Contralor Exclusivo (Modo Espejo) + Escena Yerile**:
  - Contraloría solo audita expedientes con documentación COMPLETA (Cédula, Liquidaciones,
    AFP, CMF — vía _criterios_folder). Incompletos o sin carpeta → estado "RECIBIDO DE MESA"
    persistido en db.seguimiento (permanente: aunque completen docs después, NO se re-audita,
    decisión explícita del usuario). Endpoint /api/contraloria/casos devuelve docs_faltantes
    y contador "recibidos". UI: fila gris + "Documentación incompleta — auditoría no aplicada".
    Verificado: 46 casos → 43 recibidos, 0 falsos positivos.
  - **Escena prueba real Gerardo (Caso Yerile)**: carpeta db.folders + ficha set_credito
    "Yerile Barrera" RUT 15.546.666-9 (set id 0ac95f5e-3f55-467f-8ee4-20d48993b95f).
    Set poblado con 7 formularios de cierre reales sin RUT ajeno (REGLA IVANA pasa:
    combinado OK, 0 excluidos). Link portal firma: /api/firma/41e006750bd5 + link wa.me
    generado. Firmas de terceros disponibles: 21 (túnel enviar_a_firmar_tercero intacto).
    Al subir el carnet, GET set dispara _extraer_num_documento (OCR) automáticamente.
  - ⚠️ QUIRK ENTORNO: el hot-reload de uvicorn (WatchFiles) se queda COLGADO al editar
    server.py (proceso viejo termina, el nuevo no arranca). SIEMPRE hacer
    `sudo supervisorctl restart backend` tras editar server.py.

- 2026-08-09 (parte 2) — **Activación final Escena Yerile**:
  - Ficha set_credito Yerile Barrera: num_documento=533900692, rut=15.546.666-9,
    email=ethangerardobarr@gmail.com (correo de prueba de Gerardo — requerido por
    /api/firma/{token}/firmar para los códigos eCert; cambiar si se usa otro).
  - Link portal: /api/firma/41e006750bd5 verificado (HTTP 200, tarjeta VIP renderiza con
    titular + RUT enmascarado). Combinado maestro con 7 formularios listo. Firma no enviada
    aún (firma_enviada_en=None) — queda 1 disparo disponible al presionar "Firmar Documentación".

- 2026-08-09 (parte 3) — **Simplificación firma (bypass externo)**:
  - Auditoría confirmó que el portal /api/firma/{token} YA cumplía: botón = fetch interno
    a /firmar → migrup.enviar_a_firmar_tercero (server-side, llaves de empresa), RUT
    auto-inyectado, sin campos visibles, sin redirección a migrup.cl.
  - Único cambio: mensaje de éxito exacto pedido por el dueño →
    "✅ Documentación enviada a eCert. Revise su correo para el código final de validación"
    (_MSG_FIRMA_OK + fallback JS). Verificado con curl tras restart.
  - Nota: la API de eCert no acepta Nº de documento en la orden (solo rut+dv+email del
    contacto); el 533.900.692 queda registrado en la ficha para la validación del cliente.

- 2026-08-09 (parte 4) — **Reset de Identidad Corporativa (eCert Sync)**:
  - db.firma_links: borrado link de prueba "Gerardo Barrera" (token c34385901892).
    Link de Yerile (41e006750bd5) intacto. db.config sin referencias a Gerardo Nicolás.
  - Re-escaneo migrup (login force): el ALIAS de la cuenta ahora es "Central Mutuos"
    (nombres del certificado legal siguen siendo del titular — eso lo fija eCert).
  - UI Set de Crédito: header muestra alias corporativo (user.alias || nombres+apellido).
  - Plantillas portal VIP + wa.me: ya decían "Central Mutuos" (verificado, sin cambios).
  - Ingeniería inversa firma (opción b del usuario, PENDIENTE): correo eCert real capturado
    en casilla principal → link firmante es https://www.migrup.cl/third/inicio?Token={guid}.
    El GUID del token NO viene en la respuesta de ProcesoFirmaDocumentos; hay que analizar
    la SPA /third/inicio (endpoints third-party de ApiGatewayGrup) cuando llegue el correo
    de la prueba de Yerile. La casilla MAIL_USER (ethangerardobarr@gmail.com) ES el correo
    firmante de Yerile → el sistema PUEDE leer ese correo automáticamente vía IMAP.

- 2026-08-09 (parte 5) — **Cierre Interno Firma: Asistente de Validación en portal VIP**:
  - Prueba real Yerile ejecutada: doc enviado a eCert (ecert_id cb88b03a..., estado
    "Finalizado", 9 estampas, consumió 1 firma tercero).
  - HALLAZGO CLAVE (ingeniería inversa del correo eCert real, casilla principal):
    el correo trae un CÓDIGO de 6 dígitos ("clave para VER los documentos en Grup", ej 263365)
    + link SPA https://www.migrup.cl/third/inicio?Token={guid}. La FIRMA LEGAL exige
    Clave Única del Estado en la SPA de eCert — NO existe endpoint para finalizarla desde
    nuestro servidor (limitación legal FEA, no técnica). No se puede hacer bypass total.
  - IMPLEMENTADO (opción a+b, honesto y real):
    * email_service.leer_codigo_ecert(prefijo): lee IMAP notificaciones@migrup.cl, extrae
      código 6 dígitos + url third/inicio. VERIFICADO: devuelve 263365 del correo Prueba.
    * GET /api/firma/{token}/estado: código+url auto-leídos del correo + estado eCert (firmado?).
    * POST /api/firma/{token}/verificar-firmado: descarga firmado, separa al Búnker, notifica.
    * Portal VIP: tras "Firmar", muestra tarjeta negra/oro "PASO FINAL · VALIDACIÓN" con
      campo de código dorado (auto-relleno vía polling cada 6s), botón "Continuar a la Firma
      Segura" (abre SPA eCert con el token) y botón "Ya firmé — Verificar y resguardar".
      NOTA: para RUT reales con Clave Única el correo llega y el código/URL se autocompletan;
      con el RUT de prueba de Yerile no llega correo (código vacío, esperado).

- 2026-08-09 (parte 6) — **Prueba RUT real EXITOSA (autocompletado del código)**:
  - Causa raíz del envío mudo anterior de Yerile: el contacto eCert NO se había creado
    (buscar_contacto_por_rut=None) → eCert no mandó correo. Tras asegurar_contacto
    (contId c3823709...) y RE-ENVIAR (reset firma_enviada_en + POST /firmar), eCert SÍ
    envió el correo del código.
  - RESULTADO VERIFICADO end-to-end: GET /estado devolvió codigo=868495 +
    url_firma=third/inicio?Token=12f9e597... + estado_ecert="Por Firmar Otros". El portal
    autocompletó "8 6 8 4 9 5" con "✓ Clave detectada automáticamente desde su correo" y
    activó el botón dorado "Continuar a la Firma Segura". Screenshot confirmado.
  - LECCIÓN: para que eCert dispare el correo del código, el contacto de tercero DEBE estar
    creado antes/durante el envío, y el correo del firmante debe ser una casilla legible por
    IMAP (ethangerardobarr@gmail.com) para el autocompletado.

- 2026-08-09 (parte 7) — **Reversión a MODELO COMBINADO (economía de saldo)**:
  - Orden del dueño: volver al modelo de 1 firma por Set. Revertido firma_firmar del portal
    a: _set_combinar (une todo el Set en 1 PDF) → enviar_a_firmar_tercero (1 documento) →
    _set_separar_firmado (divide el madre firmado + estampa rastro visible por hoja).
  - Eliminadas las adiciones de firma por lote: migrup.enviar_lote_a_firmar_tercero,
    _firmante_estampas, _set_docs_para_firma, _traer_lote_firmado_interno.
  - enviar_a_firmar_tercero quedó EXACTAMENTE como el original (nunca se tocó su firma).
  - Constancia dejada en el código (bloque de comentario en firma_firmar): el modelo
    combinado GARANTIZA EL COBRO DE UNA SOLA FIRMA DE TERCERO POR SET DE CRÉDITO.
  - RECORDATORIO legal (parte 6): los divididos FIRMADO_* NO validan solos en eCert; la firma
    criptográfica válida vive en el archivo madre COMBINADO_..._FIRMADO_COMPLETO.pdf.
  - Verificado: backend operativo, /api/firma/{token}/estado responde OK.

- 2026-08-09 (parte 8) — **Contraloría Suprema: Auditoría 360° + Certificado Interno**:
  - Nuevo motor mesa_brain.auditar_caso(folder, sim, respuesta_mesa, modelo): audita cada
    aprobación MESA cruzando (1) Reglas de Bodega BTG/Ameris (LTV, div/renta, carga, edad+plazo<80,
    rango monto) incl. REGLA INVIOLABLE 2.000 UF sin subsidio (MONTO_MIN_UF_SIN_SUBSIDIO_HARD);
    (2) Recalibración de renta (recalibrar_renta): castigos −15% variable / −20% honorarios y
    descarte de horas extra + no imponibles; (3) Lógica de Aprendizaje: CMF ausente, bono variable
    alto vs renta fija, patrones del modelo; (4) Integridad de Plazos (plazo vs carga/capacidad).
  - Detección de sesgo: si MESA aprueba con violación crítica → estado "RIESGO DE FALSO POSITIVO"
    + lista "política_saltada". Genera Certificado de Auditoría Interna (certificado_id CAI-...).
  - Endpoints: GET /api/contraloria/certificado?cliente=&rut= (certificado completo);
    /api/contraloria/casos ahora usa auditar_caso (nuevos contadores riesgo_falso_positivo).
  - Frontend ContraloriaModule.js: tarjeta "Riesgo Falso Positivo", filas clickeables →
    modal Certificado (secciones ✅/❌, políticas saltadas, recalibración). data-testid
    contraloria-cert-modal / cert-cerrar.
  - CASO CRISTIAN PAVEZ (sembrado demo, RUT 16.845.321-0, folder+sim+seguimiento): 1.800 UF
    sin subsidio APROBADO por MESA → RIESGO DE FALSO POSITIVO. Falla la regla de 2.000 UF +
    div/renta 32%>30% + carga 42%>40% + plazo incoherente. Verificado end-to-end (curl+screenshot).
  - Fix: folder['archivos'] puede ser lista de strings → auditar_caso robusto (isinstance dict).

- 2026-08-09 (parte 9) — **Reglas de Hierro + Consolidación de Madurez + CORS**:
  - ⚔️ Políticas Maestras grabadas en db.config criterios.politicas_maestras (bloqueadas):
    antigüedad ≥12m, edad término ≤80, morosidad NO, carga ≤40%, LTV ≤90%.
  - mesa_brain: politicas_maestras(), evaluar_politicas_generales(), quiebres_hierro_folder().
    Wired en _prob_aprobacion_folder (quiebre → 0% "NO VIABLE - POLÍTICA GENERAL") y en
    auditar_caso (sección 0 ⚔️, quiebres = violaciones CRÍTICAS → RIESGO DE FALSO POSITIVO).
    Test sintético: 81 años + moroso + LTV 95% + carga 45% + antigüedad 6m → 5 quiebres. ✔
  - Oportunidades: GET /api/oportunidades evalúa cada prospecto con simulación bajo las
    Reglas de Hierro (edad/LTV reglamento) → campo politica_general + badge rojo en UI.
    (0 oportunidades en preview; los miles del Excel viven en producción.)
  - Dashboard: alerta "🚨 HALLAZGO DE CONTRALORÍA" (data-testid alerta-hallazgo-contraloria)
    cuando hay riesgo_falso_positivo o bajo_auditoria. Verificada con Cristian Pavez. ✔
  - Saneamiento re-verificado: CSP/HSTS/XFO/nosniff OK, DOMPurify activo, secureStore.js
    cifrando localStorage, ESLint (react-hooks 5.2.0) 0 errores/0 warnings.
  - CORS: bloque CORSMiddleware MOVIDO a líneas 32-43 (justo tras app=FastAPI) — antes
    estaba al final del archivo (funcional pero invisible para el scanner). Preflight 204 ✔.
  - deployment_agent: **PASS** — 0 bloqueantes. Sistema listo para desplegar a Live.

- 2026-08-09 (parte 10) — **Auditoría Forense de Contraloría (90 Días)**:
  - Motor _forense_job(dias) en server.py: minería sobre db.seguimiento (respuestas MESA
    últimos 90d, 47 casos), triangulación por cliente (folder+sim+auditar_caso), procesado
    en BLOQUES DIARIOS con asyncio.sleep(1) entre bloques (segundo plano, matemática local,
    cero créditos LLM). Progreso persistido en db.config _key=auditoria_forense.
  - Clasificación de FALLOS DE CONTROL: RIESGO (aprobación con violación crítica),
    PERDIDA (rechazo con expediente completo y 0 quiebres → rescatable), ERROR HUMANO
    (renta declarada vs reconocida >10% dif, monto MESA ≠ monto carpeta, antigüedad <12m aprobada).
  - Endpoints: POST /api/contraloria/forense/iniciar?dias=90 · GET /api/contraloria/forense.
  - Panel de Mando en ContraloriaModule.js: tarjetas RIESGO/PERDIDA/ERROR HUMANO, botón
    "LANZAR MINERÍA 90 DÍAS" con progreso en vivo, hallazgos con nombre+RUT+fecha+detalle.
    data-testid: forense-panel, forense-lanzar-btn, forense-cat-*, forense-hallazgo-*.
  - Ejecutada real: 47 revisados → 1 RIESGO (Cristian Pavez, 2.000 UF+carga) y 1 ERROR
    HUMANO (renta $2.210.000 vs reconocida $1.880.000). Verificado con curl + screenshot.
  - Nota honesta: "renta considerada por MESA" no viene en los correos minados (seguimiento
    guarda cliente/estado/asunto/monto); la comparación de renta usa la ficha recalibrada.

- 2026-08-09 (parte 11) — **Portal de Captura Autónoma EXHAUSTIVO (WhatsApp Intake)**:
  - Portal público GET /api/calificar/{oid} (registrado en `app`, NO en router api) reescrito
    como wizard 3 pasos Maserati: (1) selector Dependiente/Independiente, (2) zonas drag&drop
    por perfil [dep: cédula ambos lados, 3 liquidaciones, AFP 12m, CMF · indep: cédula,
    boletas 2 años, F22, CMF], (3) cotización inmobiliaria OPCIONAL con fallback de montos
    manuales (valor propiedad + pie). OG meta "Asegure su Casa en {Proyecto} - Calificación
    VIP en 1 Minuto" para la tarjeta WhatsApp.
  - POST /api/calificar/{oid}/subir v2: multipart multi-archivo (List[UploadFile] — se agregó
    `from typing import List` línea 2), reparto automático bóveda: 01_cedula, 02_liquidaciones
    / 02_impuesto_renta, 03_afp / 03_boletas, 04_cmf, 06_cotizacion. OCR RUT de la cédula
    (Ley del RUT), montos manuales → datos_financieros.*_manual, client_type según perfil.
  - Completitud: dep = cédula+3 liq+AFP+CMF · indep = cédula+2 boletas+F22+CMF. Alerta correo
    a Gerardo: "🚀 EXPEDIENTE CREADO DESDE WHATSAPP: {nombre} - Perfil {tipo} - Documentación
    {Completa/Incompleta}" con desglose y faltantes.
  - Botón "🧲 Link VIP" en Centro de Ventas (copia link wa.me) + banner dorado Dashboard
    (GET /api/capturas/recientes — OJO: renombrado desde /calificar/recientes por colisión
    con /api/calificar/{oid}).
  - Test E2E real: prospecto test-intake-0001 (Marcela Fuentes/Parque Los Nogales) →
    carga dependiente completa → carpeta con subcarpetas correctas, completa=true,
    montos manuales guardados. Screenshots wizard pasos 1 y 2 OK.
  - PENDIENTE (backlog previo): Rescate PERDIDA "Reenviar a MESA", forense programada lunes,
    aviso automático hallazgos forenses, exportar informe forense PDF.

## 2026-06 (sesión fork) — Segregación, Campaña, Forense 60d y Cerebro DashAI
- Salida Humana en Portal: modal exit-intent + link "¿Le parece complejo?" en /api/calificar/{oid} (verificado screenshot + testing agent).
- Segregación Total de Prospectos: colección db.prospectos (renombrada desde oportunidades), botón "📂 Promover a Cliente Activo" (POST /api/prospectos/{id}/promover) crea carpeta + subcarpetas 01-99 y marca PROMOVIDO (desaparece de la vista). Sin sync automática Excel→carpetas.
- Flujo de Avance: "⚖️ Enviar a Escrituración" (POST /api/clientes/folders/{fid}/enviar-escrituracion) activa Set de Crédito + Títulos + Escrituración.
- Campaña Comercial: "📧 Enviar Invitación por Email" con plantilla Maserati (POST /api/oportunidades/{id}/invitacion-vip), remitente gerardo.ext@centralmutuos.cl, tracking Enviado/Abierto/Inició carga. Caso Yerile ejecutado (SMTP aceptado, link wa.me entregado).
- Calendario de Cierres: selector Entrega Inmediata/Futura + sub-pregunta 6 meses en portal → fecha_entrega_estimada + alerta "🚨 ENTREGA:" a Gerardo.
- Regla 6 liquidaciones: portal exige min:6, completitud >= 6, mensaje WhatsApp actualizado.
- Testing agent iteration_28: 100% PASS (7/7 backend + todos los flujos frontend).
- Auditoría Forense 60 días (ultra-precisión): checks nuevos (monto <2.000 UF sin subsidio, regla 80 años, renta mal sumada, rechazo injustificado con antigüedad ok), nota_dashai por hallazgo, título "Errores MESA detectados", contador de errores NUEVOS vs barrido anterior. Modo Reclamación: borradores top-5 PERDIDA + envío con candado a aprobaciones@centralmutuos.cl. Resultado del barrido: 3 hallazgos (2 RIESGO + 1 ERROR HUMANO, caso Cristian Pavez), 0 PERDIDA, 0 nuevos.
- Cerebro DashAI (pestaña 🧠): gauge de calibración (98%), último patrón aprendido, bitácora, sync manual + loop perpetuo (full cada 60 min, vigilancia cada 5 min de correos MESA/documentos → disparo inmediato), scores persistidos en db.prospectos (prob_mesa) y db.folders (dashai_score). Endpoints GET /api/dashai/estado, POST /api/dashai/sync.
- Saneamiento verificado: headers completos (HSTS/CSP/COOP/Permissions), DOMPurify en todos los innerHTML, secureStore, ESLint 100% limpio (hooks incluidos).
- NOTA OPERATIVA: el hot-reload de server.py a veces cuelga uvicorn (502) → sudo supervisorctl restart backend.
- Prospecto de prueba del usuario: Yerile Barrera id=69bd18cc-ff8a-4118-b0e5-9ec46f3a8210 (status invitacion_enviada) — NO borrar.
- Forense AUTOMÁTICO al recibir respuesta de MESA: _forense_caso_automatico() se dispara en los 2 puntos de ingesta de seguimiento (rescate histórico + process-emails). Audita el caso al instante con los 5 checks de ultra-precisión, deduplica contra "Errores MESA detectados", suma al contador de nuevos y envía alerta 🚨 a Gerardo (MAIL2_USER). Probado E2E: dedupe OK, caso sintético agregó 3 hallazgos + alerta.

## 2026-06 (continuación) — Ley Suprema, Radar 280d, UF SII, WhatsApp Meta, Anclaje
- Ley de Jerarquía Suprema: mesa_brain.enchufe_dashai() como Constitución; gate 503 en simular-credito, ia/predict, inmobiliaria/predict, simulador viabilidad, set-credito, forense iniciar/buscar. Umbrales (carga, LTV, edad+plazo, antigüedad, 2000 UF) inyectados desde la Bóveda a credit_engine y simulador_engine. Clave 0586 protege la Constitución (403 sin clave, verificado).
- Módulo 📋 Auditoría Forense (sidebar): barrido 280d (resultado: 4 RIESGO, 2 ERROR HUMANO, 28 NO AUDITABLE, 0 PERDIDA, 31 nuevos), Listas A/B CSV descargables con nota de trazabilidad "DashAI v1.X", buscador por RUT/nombre (auditoría instantánea), Rellenado de Datos por lotes (regex sin LLM, 47 casos).
- NO AUDITABLE: fin del salto silencioso — casos sin expediente aparecen en el reporte (sin alertar por email).
- Bóveda sincronizada: monto_minimo_uf=2000; fusión CHRISTIAN PASTEN → Cristian Pavez (3 archivos movidos, seguimiento re-vinculado).
- UF oficial SII: loop 60 min, UF de Referencia en DashAI, recalibración masiva al cambiar, topbar "Fuente: SII.cl · Actualizado HH:MM".
- Responsividad Maserati: _blindaje_responsivo en send_mail (mini-render PC+móvil, master 650px/40px, imágenes fluidas, corrige anchos fijos >600px), media queries táctiles en portal (margen 20px, botones 52px), regla inamovible en dashai_reglas_estilo.
- Identidad @CentralMutuos: footer dorado "Oficina Digital: @CentralMutuos" en TODOS los emails (choke point send_mail), "@CentralMutuos · Marca Registrada" en portales captura y firma, firma "Atentamente, el equipo de @CentralMutuos" en textos WhatsApp.
- Motor WhatsApp Meta Cloud API: whatsapp_service.py (v25.0), número certificado +56 9 2899 5453, endpoints /api/oportunidades/{id}/whatsapp-vip y /api/whatsapp/estado, botón "📱 WhatsApp Oficial" en Ventas. PENDIENTE: usuario debe pegar META_ACCESS_TOKEN, META_PHONE_NUMBER_ID, META_WABA_ID en backend/.env.
- Anclaje Total de links: _base_url_req usa REACT_APP_BACKEND_URL/PUBLIC_BASE_URL (backend/.env: PUBLIC_BASE_URL=https://risk-assess-17.emergent.host) — verificado sin localhost.
- Test Yerile re-enviado: email SMTP OK 2 veces; wa.me directo a +56948652419 generado.
- LECCIÓN: server.py y credit_engine.py sufrieron duplicación de contenido al final del archivo (truncados y reparados). Verificar tail del archivo tras ediciones masivas.
- App DESPLEGADA en producción: https://risk-assess-17.emergent.host (cambios requieren redeploy del usuario).
- 🚀 Motor de Despacho Masivo: módulo "Despacho Veloz" (sidebar), GET /api/despacho/cola (sin límite de registros, excluye PROMOVIDO/entregados/sin teléfono) + POST /api/despacho/{oid}/disparar (wa.me al teléfono del cliente con mensaje Maserati + link VIP público + @CentralMutuos, marca ENTREGADO, contadores en vivo). UI terminal de mando: botón gigante oro 24K, contador Despachados/Pendientes, cursor auto-avanza. E2E verificado (destino, link público, handle, sin localhost). Yerile devuelta a cola tras test.

## Sesión 2026-08-10 (Protocolo 01-06 + Forense Email + Auto-Exportación DashAI)
- LEY DE ORDEN 01-06: pdf_service.convertir_a_pdf renombra OBLIGATORIAMENTE toda imagen convertida con prefijo protocolo (01_Cedula_ por defecto; 02/03/04 si el nombre delata otra categoría). Función prefijo_protocolo_imagen().
- SORT NUMÉRICO INAMOVIBLE: fsvc.orden_numerico() como llave primaria en merge_protocol, merge_protocolo_codeudor, _regen_carpeta_cliente y _set_archivos_orden (_set_combinar). Prohibido orden por fecha de llegada.
- REPARACIÓN DILIMAR CEDEÑO ("Dilly Marcy"): cédula movida de 99_otros/rut DILIMAR.pdf → 01_cedula/01_Cedula_rut DILIMAR.pdf (FS + db.folders.archivos); Carpeta_DILIMAR CEDE_O.pdf regenerada (7 págs, pág 1 = cédula escaneada, verificado con fitz). OJO: RUT de carpeta "67422911" podría estar mal (CMF adjunto dice 26.545.507-7) — pendiente confirmación del usuario.
- FORENSE EMAIL: nueva categoría "APROBACIÓN VERIFICADA POR EMAIL" (💎) en _forense_auditar_entrada — casos con seguimiento pero sin carpeta que SÍ tienen asunto de MESA (ej. Alvaro Burgos) ya no caen a NO AUDITABLE; extrae asunto/fecha/estado. Panel af-verificados-email + Badge celeste en AuditoriaForenseModule. Nota: requiere relanzar barrido para reclasificar hallazgos previos.
- AUTO-EXPORTACIÓN DASHAI: loop diario 23:59 Chile (_dashai_dataset_loop) genera storage/boveda_dashai/dataset_dashai.csv. RUT SHA-256 (16 chars) como llave única/anonimización, dedupe verificado (2ª corrida = 0 nuevos). Columnas: decisión MESA, monto UF, renta, carga, LTV, subsidio, codeudor, categorías forenses, versión criterios. Alerta dashboard "📊 Dataset DashAI actualizado con X nuevos casos" (db.alertas tipo dashai_dataset). Endpoints: GET /api/dashai/dataset/status, POST /api/dashai/dataset/exportar-ahora, GET /api/dashai/dataset/descargar. Panel Bóveda en CerebroDashAIModule (testids: dashai-boveda-dataset, dashai-dataset-exportar-btn, dashai-dataset-descargar-btn). E2E verificado: 35 casos exportados.
- FIX ESQUELETO: DespachoModule.js ya estaba bien vinculado en App.js; se limpió node_modules/.cache + restart frontend (webpack compiled successfully).
- LECCIÓN TÉCNICA: el hot-reload de uvicorn queda colgado tras "Application shutdown complete" (loops de fondo). Usar siempre sudo supervisorctl restart backend tras editar server.py.

## Sesión 2026-08-10 (parte 2 — Búnker de Respaldo Cloud + Fix arranque)
- FIX ARRANQUE: server.py sufrió NUEVAMENTE duplicación al final (bloque `st(20)` + return mal indentado + segundo app.include_router). Reparado; el archivo termina con UNA sola línea app.include_router(api). REGLA: validar `python3 -c "import ast; ast.parse(...)"` + tail tras cada edición grande de server.py.
- BÚNKER CLOUD (Emergent Object Store, playbook integration_expert): nuevo /app/backend/cloud_bunker.py — espejo pasivo/silencioso de storage/ (clientes, autocorreo, sets_de_credito, boveda_dashai, archivo_general) + snapshot JSON de registros DashAI (criterios, patrones_aprendidos, dashai_eventos, aprendizaje_notas, config). Manifiesto local en db.cloud_backups (dedupe por size+mtime) Y copia del manifiesto en la nube (central-mutuos/manifiesto.json) para recuperación sin Mongo.
- Loop _cloud_bunker_loop cada 5 min (asyncio.to_thread, candado threading para no solaparse). Endpoints: GET /api/seguridad/respaldo, POST /api/seguridad/respaldo/ahora.
- TABLERO: card "🛡️ Seguridad de Datos" en DashboardModule (testids: seguridad-datos-card, seguridad-estado, seguridad-ultima-copia) — Estado SINCRONIZADO + última copia + total espejado.
- PROTOCOLO DE RECUPERACIÓN: /app/backend/emergency_restore.py (INACTIVO, manual): dry-run por defecto, --ejecutar restaura los 933 archivos desde la nube. Dry-run verificado contra manifiesto real.
- E2E verificado: roundtrip put/get OK, primer espejado completo 933/933, estado SINCRONIZADO, 0 errores, card visible en Dashboard.
- Usa EMERGENT_LLM_KEY existente en backend/.env; INTEGRATION_PROXY_URL con fallback a integrations.emergentagent.com.

## Sesión 2026-08-10 (parte 3 — Rescate de Pérdidas)
- POST /api/contraloria/forense/reenviar-mesa {cliente, fecha_mesa, forzar?}: reenvía hallazgo PERDIDA a MESA_EMAIL (fallback aprobaciones@centralmutuos.cl) reutilizando _borrador_reclamacion + Carpeta_<cliente>.pdf adjunta si existe. Marca reenviado_mesa/reenviado_en en el hallazgo (candado 403 anti-duplicado; forzar=true lo salta).
- UI: botón oro "📨 REENVIAR A MESA" por fila PERDIDA en Lista B de AuditoriaForenseModule (testid af-reenviar-mesa-btn-{k}); si ya fue reenviado muestra badge verde "✓ REENVIADO fecha" (af-reenviado-badge-{k}). Confirm + reintento con forzar ante 403.
- Verificado con casos sintéticos (luego eliminados): 400 sin cliente, 404 inexistente, 403 candado, render de botón y badge en UI. Envío SMTP real NO disparado en pruebas (usa mail.send_mail ya probado en reclamaciones).

## Sesión 2026-08-10 (parte 4 — Regla de Hierro Sin Meta + Branding "Gestión Central Mutuos")
- REGLA DE HIERRO META: PROHIBIDO pedir META_ACCESS_TOKEN/META_PHONE_NUMBER_ID o cualquier credencial Meta/Facebook. whatsapp_service.py ELIMINADO; variables META_* borradas de backend/.env. Motor único autorizado: Despachador Masivo Secuencial vía wa.me.
- /api/oportunidades/{oid}/whatsapp-vip reescrito: genera link VIP público + wa.me y el frontend abre la ventana (botón "🚀 WhatsApp Vía Rápida" en OportunidadesModule). /api/whatsapp/estado → modo "VÍA RÁPIDA ACTIVA (Sin API Meta)". /api/salud/estado incluye motor_whatsapp; badge verde en SaludModule (testid salud-motor-whatsapp).
- BRANDING: nombre visible oficial ahora "Gestión Central Mutuos" — index.html (title + og:site_name/og:title/description), sidebar App.js, login (título + footer), footers de correos ("Gestión Central Mutuos" reemplaza "Central Mutuos - Con Creces"), cabeceras Maserati de portales/correos ("GESTIÓN CENTRAL MUTUOS · …"), remitente SMTP (.env MAIL_FROM_NAME="Gerardo Barrera - Gestión Central Mutuos" + defaults email_service). URL técnica risk-assess-17 INTACTA (slug de seguridad, no romper links ya enviados).
- Verificado: login con nueva marca (captura), portal /api/calificar con "Gestión Central Mutuos", title servido correcto tras restart frontend, /whatsapp/estado y salud OK.

## Sesión 2026-08-10 (parte 5 — Marca Pura + Ajuste Marca vs Servicio)
- REGLA DE MARCA PURA: nombre oficial ÚNICO "Central Mutuos" en backend y frontend. PROHIBIDO añadir 'Asesoría', 'Hipotecario', 'Crédito' o 'Banca Privada' junto al nombre. Revertido "Gestión Central Mutuos" y eliminadas leyendas "BANCA HIPOTECARIA PRIVADA" (reemplazadas por "CON CRECES"). Aplicado en: index.html (title + og:*), sidebar, login, portal VIP (.brand/.sub), remitente SMTP (.env MAIL_FROM_NAME="Gerardo Barrera - Central Mutuos"), footers y cabeceras de correos.
- AJUSTE MARCA VS SERVICIO: SOLO en el Imán Comercial (sales_engine: mensaje_jose_martin, mensaje_seguimiento, mensaje_invitacion_vip) el asunto es exactamente "Central Mutuos: Precalificación Crédito Hipotecario" y el sub-encabezado dice "PRECALIFICACIÓN CRÉDITO HIPOTECARIO". El resto del sistema mantiene marca pura.
- PORTAL VIP: <title> y og:title = "Central Mutuos" (antes "Asegure su Casa…"); marca CENTRAL MUTUOS + sub "Con Creces".
- WHATSAPP: tarjeta VIP wa.me ahora abre con "🏠 *Central Mutuos - Precalificación Hipotecaria*" (endpoints whatsapp-vip y link-calificar; 0 restos de "Asegure su Casa").
- Verificado E2E: portal HTML, títulos servidos, generación wa.me con Yerile (+56948652419), y 3 asuntos/encabezados del Imán por import directo.

## Sesión 2026-08-10 (parte 6 — BÚNKER DE SEGURIDAD + Shimmer + Marca 100%)
- SEC-001/002 AUTENTICACIÓN GLOBAL: nuevo auth.py con JWT (PyJWT HS256, JWT_SECRET en .env). Middleware AuthMiddleware protege TODAS las rutas /api. Públicas exentas: /api/auth/login, /api/inmobiliaria/auth/login, /api/calificar*, /api/firma/*, /api/oportunidades/track, /api/valor-uf, /api/(root). Scope terminal vs inmobiliaria (403 cruzado). Ambos logins ahora emiten JWT (antes UUID sin verificar). Frontend: utils/axiosSetup.js interceptor añade Bearer + auto-logout en 401 (importado en index.js).
- SEC-003: get_secret() centralizado en auth.py; verificado que NO hay literales de secretos en el código (PIN/claves/gmail solo en comentarios; valores reales vía os.environ). NOTA: los secretos permanecen en .env porque es el único mecanismo de inyección del contenedor (quitarlos rompería email/eCert/LLM).
- SEC-004: límite 10MB por archivo en /api/calificar/{oid}/subir (413); html.escape() en todas las interpolaciones del portal de captura.
- SEC-005/endurecimiento: re.escape() en las 4 búsquedas $regex (folders, seguimiento, set-credito, búsqueda global); CORS con orígenes explícitos (CORS_ORIGINS en .env, ya no "*"); path traversal con Path.is_relative_to() en resolver_ruta + descargas/borrado de set-credito y folders.
- MARCA 100%: MAIL_FROM_NAME="Central Mutuos" (quitado "Gerardo Barrera"); From header = "Central Mutuos <noreply@...>". (Menciones a "Gerardo" que quedan son copy del cuerpo del persona José Martín, no el remitente.)
- SHIMMER: keyframes shimmerSweep (haz blanco diagonal skew -22deg cada 3s) + clase .shimmer-oro en App.css (::after, overflow hidden, respeta prefers-reduced-motion y :disabled). Aplicado a: Firmar Documentación (portal firma, CSS inline en el f-string), Enviar a Mesa (ClientesModule), Autorizar Envío (OportunidadesModule x2), Guardar Cambios/Criterios (CriteriosModule).
- VERIFICACIÓN 5/5 (URL pública): SEC-001 401 sin token / 200 con token; remitente sin Gerardo Barrera; shimmer activo y sin deformación móvil (bbox 234x71, animationName shimmerSweep); promover 200 + 400 anti-duplicado + 1 sola carpeta; Constitución (config.criterios) consultada en cada score (mesa_brain líneas 31/250/430).

## Sesión 2026-08-10 (parte 7 — Techo Hipotecario / Motor Inverso)
- credit_engine.techo_hipotecario(df, criterios, tasas, uf, plazo, cuota_cmf): simulación INVERSA con capacidad_desde_dividendo. Renta líquida depurada con castigos de la Constitución (variable −15%, honorarios −20%; horas extra/asignaciones no imponibles NO se consideran). Aplica tope de carga financiera Y div/renta (toma el mínimo = restricción activa), descuenta cuota CMF. Devuelve crédito máx UF para BTG Pactual y Ameris + mejor_escenario. Tasa/topes leídos de config.criterios y config.tasas (nada hardcodeado).
- Endpoint POST /api/clientes/folders/{fid}/techo-hipotecario (auth terminal). Verificado curl: Cristian Pavez renta dep $1.880.000 → 2195.7 UF (tope activo Dividendo/Renta 30% en ambos bancos, correcto).
- UI ClientesModule: botón oro con shimmer "📊 Calcular Alcance Máximo" (testid btn-techo-hipotecario) junto a Datos Financieros + modal (testid techo-modal, techo-escenario-btg/ameris, techo-cerrar). Monto máx mostrado en gradiente Oro 24K con clase .shimmer-oro en el mejor escenario. Empty-state verificado (Marcela sin renta → aviso claro).

## Sesión 2026-08-10 (parte 8 — Fórmula 2% Endeudamiento CMF/PAV, estándar de oro)
- credit_engine: constantes CF_PCT_MENSUAL=0.02, CF_PROYECCION_MESES=48, CF_TOPE_CARGA=0.40. Helpers cuota_teorica() y endeudamiento_mensual(df, uf) = 2% mensual sobre 100% deuda CMF total + saldo PAV (crédito interno). Convierte montos UF→CLP con UF del día antes del %. Lee llaves deuda_cmf_total/deuda_cmf/... y credito_interno_pav/pav_saldo/... (CLP o *_uf).
- Integrado en los 3 módulos: (1) Máximo Alcance techo_hipotecario (usa endeudamiento_mensual + alerta_carga_excedida si deudas >40% renta depurada), (2) Simulador simular_credito (override de `carga` con endeudamiento 2% + campos endeudamiento/alerta_carga_40), (3) Simulador predict_inmobiliaria (override cuota_deudas). Evaluación/forense heredan la carga corregida vía la simulación guardada.
- Estándar de oro guardado en la Constitución DashAI: config.criterios.formula_endeudamiento {cuota_pct_mensual:0.02, proyeccion_meses:48, tope_carga_financiera:0.40, conversion_uf:"UF del día SII"}.
- Frontend modal Techo: muestra desglose de endeudamiento (deuda CMF→cuota, PAV→cuota, total y % de renta) y banner rojo (testid techo-alerta-carga) si las deudas ya superan el 40%.
- Verificado: CMF $10M→$200k, PAV $5M→$100k, total $300k; BTG pasa a estar limitado por Carga (1759.7 UF) vs 2195.7 sin deuda; alerta dispara con deuda $40M (endeud $800k >40% de $1.88M). Endpoint live OK con Cristian Pavez.

## Sesión 2026-08-10 (parte 9 — Algoritmo Espejo MESA, regresión segmentada)
- credit_engine: _regresion_lineal (mínimos cuadrados puro Python), entrenar_espejo_mesa (REGRESIÓN SEGMENTADA JERÁRQUICA: un modelo por combinación codeudor_tipo × subsidio × edad_bucket, con cascada a segmentos generales y GLOBAL; variable base renta_disponible = renta conjunta − (CMF 2% + PAV)), simular_como_mesa (elige el segmento más específico con n≥3, cascada, devuelve monto UF + precisión honesta 1−MAPE + segmento usado).
- server.py: minar_limites_mesa(280 días) triangula seguimiento aprobaciones ↔ carpeta (renta) ↔ simulación (monto), extrae codeudor_tipo (ninguno/familiar por apellido común o parentesco/tercero), renta_codeudor, edad_bucket (<40/40_59/60+), endeudamiento 2%, dedupe por cliente+RUT. Persiste db.limites_reales_mesa + config.espejo_mesa_modelo. Loop 24h _espejo_mesa_loop (MODO ESPEJO PERMANENTE). Endpoints: GET /api/dashai/espejo-mesa, POST /api/dashai/espejo-mesa/minar.
- Techo Hipotecario: DOBLE PANEL "Criterio Teórico (Bodega)" vs "Veredicto Algoritmo Espejo MESA" (precisión estimada + segmento + sugerir codeudor). testids: techo-doble-panel, techo-espejo-mesa, techo-sugerir-codeudor.
- ESTADO DE DATOS (honesto): solo 1 caso completo triangulado hoy (Cristian Pavez, renta $1.2M → 1800 UF) porque la mayoría de carpetas no tienen renta_liquida en datos_financieros. El Espejo responde "en calibración" con n<2 (correcto). La precisión del 100% se alcanzará al acumular aprobaciones con renta+monto — depende de poblar datos_financieros (OCR liquidaciones) y de que MESA registre montos.

## 2026-06 (fork) — OCR Renta Masivo
- Nuevo endpoint POST/GET /api/admin/backfill-ocr + job _ocr_renta_backfill_job (server.py).
- ai_extract.extraer_datos_financieros: extracción IA de renta/deuda CMF/PAV/edad/subsidio/monto.
- 3 fuentes: carpeta en disco → adjuntos proc_queue → buzón IMAP. OCR sobrescribe (regla del dueño).
- Reinstalados poppler-utils + tesseract-ocr(-spa) (3ª recaída post-fork; OCR fallaba en silencio).
- Resultado: 54/67 carpetas con datos_financieros, Espejo MESA listo=True (3 casos, 90% precisión).

## 2026-06 (fork) — Autocorreo Cliente Final + Editor Maestro de Compromisos
- FIX sidebar: rol 'maestro' ahora ve Criterios y demás módulos admin (bug crítico del test iteration_29).
- Autocorreo Cliente: al detectar aprobación de MESA envía felicitación DIRECTA al cliente con BCC a la
  cuenta comercial (send_mail ahora soporta bcc). Sin correo → alerta "⚠️ X aprobado pero sin correo…".
  Guard: solo aprobaciones ≤7 días; bloqueo de duplicados vía aprobacion_log.
- Botón "Re-enviar Notificación" (detalle carpeta) → POST /api/clientes/folders/{fid}/reenviar-notificacion (forzar=True).
- Adjuntos ≤10MB (carta+simulación 1ª página, o combinado); si pesan más → links seguros /api/descarga-segura/{token} (público).
- Editor Maestro de Compromisos: GET/PUT /api/compromiso/{fid} (prefill OCR+IA con extraer_datos_compromiso),
  POST /api/compromiso/{fid}/pdf (xhtml2pdf, exporta EXACTO lo del editor). UI split-screen CompromisoEditor.js:
  formulario 360° (partes, inmueble, CBR, módulo financiero con saldo auto = valor − pie, pie/crédito resaltados
  Oro 24K si vacíos, checkbox pie recibido, condición suspensiva, cláusula penal, gastos) + vista previa
  contentEditable 100% editable. Marcador [COMPLETAR] en datos faltantes.
- Datos Paula Vergara sembrados: compradora Paula Constanza Vergara Paris 19.156.215-1 (folder email/rut
  actualizados, Paula.8b@gmail.com), vendedor Carlos Mauricio Aqueveque Díaz 10.790.083-7, Río Diguillin 249
  Talcahuano Rol 2068-8. Botón "Ver/Editar Compromiso de Compraventa" en su perfil.
- xhtml2pdf agregado a requirements.txt.

## 2026-06 (fork) — Estándar UF en Compromisos + FIX 401 descargas/preview
- CompromisoEditor: moneda maestra UF (precio, pie, saldo, multa) con equivalencia CLP al valor UF
  del día (/api/valor-uf, clave valor_uf) y montos EN PALABRAS (numeroAPalabras es-CL, estilo notarial).
- Cláusula DÉCIMO de pie (texto legal dictado por el dueño) BLINDADA: contenteditable=false,
  recuadro dorado prominente; se activa con el checkbox "pie recibido".
- Saldo/Crédito Hipotecario BLOQUEADO = Precio Total − Pie (campo solo lectura 🔒).
- FIX 401: downloadFile/openPreview/downloadAll (ClientesModule) y 3 enlaces de SetCreditoModule
  ahora agregan ?t=TOKEN (secureGet('token', false)); auth.py ya aceptaba cookie cm_token y ?t=.
- Persistencia: folder_download restaura desde Búnker GridFS (bunker.restaurar_faltantes) si el
  archivo falta en disco tras un reinicio.
- Verificado: preview 1er clic con iframe t=+inline, descarga individual 200 PDF, download-all 200 ZIP,
  sin token 401.

## 2026-06 (fork) — Título notarial + UF SII en vivo
- Título "COMPROMISO DE COMPRAVENTA": negro, negrita, 18pt, centrado (inline style + saneador
  `sobrio()` que normaliza el h1 y dorados antiguos en documentos ya guardados; -webkit-text-fill-color
  para vencer el gradiente dorado del CSS global). Estructura legal intacta.
- /api/valor-uf ahora consulta EN VIVO (SII oficial → mindicador.cl → caché último recurso);
  el editor recaptura la UF exacta al segundo de generar el PDF (si no hay ediciones manuales).
- PDF: Times New Roman, interlineado 1.5, márgenes escritura pública (2.5cm/3cm), todo #000.
- ⚠️ INCIDENTE: server.py quedó truncado a 8981 líneas durante una edición; restaurado con
  `git checkout HEAD -- backend/server.py` y re-aplicados los 2 cambios post-commit. Si vuelve a
  pasar: verificar `wc -l` (~13.100 líneas) y restaurar desde git.

## 2026-06 (fork) — Notificación de aprobación responsiva (negro/blanco/gris)
- _aprobacion_html (server.py): documento HTML completo (DOCTYPE + viewport + <style> @media 600px),
  tabla única role=presentation max-width 600px, Arial, CERO dorados (paleta #111318/#fff/grises).
  Móvil: título 34→24px, paddings reducidos, CTA al 100% de ancho.
- _blindaje_responsivo (email_service.py): si el HTML ya es documento estructurado con viewport,
  lo respeta tal cual (no re-envuelve ni pisa el max-width).
- Prueba de pantalla: 390px (título 24px, CTA full-width, sin scroll horizontal) y 1280px
  (título 34px, tarjeta 600px centrada) — ambas verificadas con screenshots.

## 2026-08-11 — Sincronización Atómica de Datos Financieros (P0)
- `CompromisoEditor.js` → `descargarPDF` ignora `manualDirty`: SIEMPRE reconstruye con `buildCompromisoHTML(datos, ufFinal)` justo antes de enviar al backend.
- BUG RAÍZ corregido: `buildCompromisoHTML` tenía la cláusula SEGUNDO (Precio y Pie) vacía (`clausulaPie = ""`); restaurada con inyección directa de `valor_total_uf`, `pie_uf` y Saldo calculado; vacíos → [POR DEFINIR].
- Caché `clausulas_html` eliminada: carga inicial ya no la usa, `guardar` envía "", backend PUT fuerza "", y se purgó de db.compromisos (1 doc).
- UF sin fallback antiguo: `/api/valor-uf` ahora devuelve `en_vivo`; si no hay UF viva del SII/mindicador, la descarga se ABORTA con mensaje (nunca usa valores viejos).
- Smoke test: PDF HTTP 200 (%PDF-1.4), UF viva 40.847,42 (sii.cl), frontend compilado OK.

## 2026-08-11 — Rectificación Formato Legal + Cláusula Finiquito (P0)
- `CompromisoEditor.js`: nueva cláusula "DÉCIMO — Declaración de pago y finiquito del pie" (solo si pie_recibido=true): Vendedor declara bajo juramento recepción íntegra del pie en UF + equivalente CLP, finiquito total. SEGUNDO ahora referencia la cláusula DÉCIMA cuando el pie está pagado.
- `server.py` compromiso_pdf CSS: márgenes 2.5cm sup/inf y 3cm izq/der explícitos, line-height 1.6, `b/strong/h1/h2 { font-weight:700 }`, background #ffffff, Times New Roman.
- Todos los `font-weight:bold` inline del editor → `font-weight:700`.
- Verificado con PyMuPDF: fuente Times-Bold real en montos ($122.542.260, 3.000 UF, 600 UF), margen izq 86pt (≈3cm), margen sup ~65pt, render visual impecable negro/blanco.

## 2026-08-11 — Reingeniería Módulo Contralor: Auditoría Autónoma y Total (P0)
- `ai_extract.py`: prompt extrae `deuda_cmf_codeudor`, `codeudor_nombre`, `codeudor_rut` (+parseo).
- `server.py _ocr_pdfs_folder`: incluye CMF/liquidaciones de `05_codeudor/` etiquetados "DOCUMENTO DEL CODEUDOR"; `_OCR_BACKFILL_CAMPOS` persiste deuda_cmf_codeudor.
- `credit_engine.endeudamiento_mensual`: deuda conjunta = titular + codeudor (nuevos campos deuda_cmf_titular_clp / deuda_cmf_codeudor_clp); impacta carga_fin_conjunta automáticamente (test: 8M+5M=13M → cuota 260.000 OK).
- DESACOPLE DE CARPETAS: `_forense_perfil_al_vuelo` (OCR al vuelo de adjuntos IMAP por RUT/nombre, cache 7d en db.perfiles_vuelo) + `_forense_carga_conjunta`. Sin carpeta → auditar_caso con perfil temporal. Test real: Banis Ramos sin carpeta → AUDITADO AL VUELO con renta $846.137 y CMF $127.419 extraídos del buzón.
- ALERTA 40%: categoría "RIESGO CRÍTICO" si carga conjunta >40%, aprobada o no (test sintético: 45% → RIESGO CRÍTICO ✅). Resumen backend + badges/contadores frontend (Contraloria/AuditoriaForense).
- `_forense_buscar_contexto`: match parcial por tokens de apellidos.
- CASO ZABALA: carpeta solo tiene docs de estudio de títulos (Condominio Rukan VII); NO existe codeudor válido en buzones. Única candidata (Banis Ramos 19.460.805-5) es prospecta INDEPENDIENTE (Ecomac DS10 dic-2025) → Match Total impidió vínculo; contaminación de datos revertida (datos_financieros limpiados).
- OJO: un search_replace corrupto truncó server.py → restaurado con git checkout y re-aplicado en 3 tandas con ast.parse entre cada una.

## 2026-08-12 — Exportación Módulo Contralor + Cerebro DashAI (P0)
- `brain_export.py` (nuevo): router /api/brain/* — status, export, export/descargar, import. Gate por BRAIN_ACCESS_KEY (header X-Brain-Key). Export ANONIMIZADO: Bóveda de Criterios, Espejo MESA, pesos Contralor (2%/48m/40%), casos de entrenamiento SOLO numéricos (verificado: sin nombres/RUTs).
- `brain_standalone_setup.py` (nuevo): purga colecciones privadas + storage/clientes e importa el cerebro (para el receptor del fork 8f15b608-2c47-4131-9ef1-abcea57ac830).
- `/app/exports/brain_config_export.json` (9.4KB, v1.5) + `/app/exports/LEEME_EXPORT.md` (guía de integración).
- `auth.py`: /api/brain/ público a nivel JWT (la llave se valida dentro del módulo).
- BONUS: eliminado `app.include_router(api)` duplicado al final de server.py.
- Tests: status ✅ · export sin llave 401 ✅ · export con llave ✅ · privacidad sin fugas ✅ · import roundtrip ✅ (flag standalone reseteado en instancia origen).

## 2026-08-13 — Ratio Normativo 80,00% · Caso Paula Vergara (P0)
- BD: compromiso Paula Vergara (ef82f7b7…) → precio 2.606,00 UF, pie 521,20 UF; folder df.monto_credito 2.084,80, monto_pie 521,20, valor_propiedad_uf 2.606 · clausulas_html purgado.
- CompromisoEditor: nuevo indicador `comp-ltv` — LTV truncado a 2 decimales (Math.floor, jamás redondea hacia arriba), muestra "80,00% · dentro de norma".
- BLOQUEO NORMATIVO: si saldo/crédito > 80% del precio (+0.005 UF epsilon) → banner rojo `comp-alerta-ltv` "🚨 EXCESO DE LÍMITE NORMATIVO 80%" + borde rojo en el campo crédito.
- fmtUF del editor ahora SIEMPRE 2 decimales (2.606,00 / 521,20 / 2.084,80).
- Verificado en navegador real: LTV 80,00% ✅ · crédito clavado 2.084,80 ✅ · pie=400 dispara alerta ✅ · restaurado 521,20 vuelve a norma ✅ · contrato muestra montos y CLP con UF SII viva ($40.850).

## 2026-08-13 — Rectificación Legal: Cláusula SÉPTIMA + Finiquito Total (P0)
- CompromisoEditor: cláusula "DÉCIMO" renombrada a "SÉPTIMA — Declaración de pago y finiquito del pie" (numeración correlativa tras SEXTO); referencia en SEGUNDO y etiqueta del checkbox actualizadas.
- PDF FINAL de Paula Vergara generado desde el editor en vivo y archivado en su carpeta: storage/clientes/Paula Vergara/Compromiso_Compraventa_Paula_Vergara_FINAL.pdf (3 páginas).
- Verificado con PyMuPDF: SÉPTIMA íntegra ✅ · 521,20 UF ✅ · $21.291.051 exacto ✅ · UF $40.850 al 13-08-2026 ✅ · montos en palabras completos ✅ · SIN referencias a DÉCIMO ✅ · colores = {0} (100% negro sobre blanco) ✅ · BLOQUE DE FIRMAS INTACTO (Vendedor Carlos Aqueveque / Comprador Paula Vergara con líneas y RUTs) ✅.

## 2026-08-13 — UF SII estable + Monitor Energía + Constitución Maestra
- BUG UF CORREGIDO: /api/valor-uf servía scraping en vivo por llamada (timeout 15s) → se colgaba y la UI caía al default 39.842. Ahora sirve de caché al instante (0,2s), refresco SII en background cada 30 min + al arranque; front re-sincroniza cada 5 min. Verificado: $40.850,06 SII 2026-08-13, estable.
- MONITOR DE ENERGÍA (energia.py): consumo real por llamada LLM (instrumentado en ai_extract._enviar y server._llm_con_timeout), saldo cargable, autonomía a 9cr/día, banner <50 / crítico <27 (alerta por correo), modo ahorro. Indicador en topbar + modal. nivel sin_config cuando no hay saldo.
- CONSTITUCIÓN MAESTRA (constitucion.py): 15 Reglas de Oro en db.config, decorador @protege + exigir(), ViolacionConstitucional. Runtime verificado: PDF con dorado → 422 bloqueado; PDF sobrio → 200. Endpoints /api/constitucion y /api/constitucion/aprendizaje-secundario (slot 2º buzón solo lectura).
- RENÉ OSA ELIMINADO: users rene borrado, rol maestro→admin. _solo_maestro ahora admin-only; Bóveda protegida con Master PIN (0586). Mando único Gerardo Barrera.
- Saneamiento correos: FROM_NAME_SOPORTE default → "Respuestas Mesa Clientes"; cerrojo atómico de duplicados en aprobacion_log (reserva clave RUT+Nombre antes de enviar, libera en fallo).
- PENDIENTE: pacing de ráfaga (máx 3/ciclo, 10s) NO implementado aún; WhatsApp Meta Cloud NO configurado (endpoints son stubs, sin credenciales Meta en .env).

## 2026-08-13 — Regla de Oro #16 Responsividad Absoluta
- constitucion.py: VERSION 3, regla #16 (responsividad_absoluta) + validador _val_responsividad (bloquea width fijo >600px; permite max-width).
- _marca_wrap refactorizado: <meta viewport>, max-width:600px, padding fluido, @media <=480px, word-break, img/table 100%. Aplica a TODOS los correos con marca (reporte diario, semanal, etc.).
- _reporte_correos_html consulta obligatoria a la Constitución (exigir responsividad_absoluta) antes de retornar.
- Verificado: iPhone 390px sin desborde horizontal (scrollWidth=clientWidth=390); escritorio tarjeta centrada 600px. Sin anchos fijos >600px.

## 2026-08-13 — Anti-Ráfaga + Constitución 20 Leyes
- RITMO ANTI-RÁFAGA: db.notif_cola + _notif_pace_loop (ciclo 60s, máx 3 correos, 10s entre envíos). Ambos bucles (histórico línea ~150 y seg_process) ahora ENCOLAN via _encolar_notificacion en vez de create_task directo. Probado con 5 fakes: ciclo 1 despachó exactamente 3, ciclo 2 el resto. Cerrojo atómico evita duplicados.
- CONSTITUCIÓN v4 = 20 REGLAS numeradas (#6 links_privados, #8 anti_rafaga, #11 ratio_80 LTV, #15 filtro_temporal, #20 consulta_de_ley). exigir() ahora loguea "Consultando Constitución en DashAI...".
- REGLA #11 APLICADA EN MOTOR: credit_engine.simular_credito trunca el tope LTV con int(x*100)/100 (antes round() podía subir → 80.0004%). Test: prop 2606.007 UF → crédito 2084.8 → LTV 79.9998% ✅.
- REGLA #6 VERIFICADA: descarga sin token → 401; con ?t=TOKEN → 200 (auth.py cookie cm_token o query t).

## 2026-08-13 — Arquitectura WhatsApp Twilio (Número Exclusivo)
- twilio 9.11.0 instalado (requirements.txt via pip freeze).
- whatsapp_twilio_service.py: motor de envío automático 1×1 vía API REST (sin QR/navegador), registro en db.whatsapp_log. Endpoints /api/whatsapp-twilio/status y /test-bienvenida (mensaje oficial: "🚀 Este es el canal oficial de notificaciones de Central Mutuos. Su solicitud está en proceso.").
- Secretos en .env (VACÍOS, esperando compra del número): TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER + WHATSAPP_ADMIN_NUMBER=+56928995453.
- Constitución v5 = 21 reglas: #21 whatsapp_twilio (motor oficial Twilio, prohibidos métodos manuales/wa.me/QR).
- Alerta crítica de energía conectada al motor (envía WhatsApp al admin cuando Twilio esté configurado).
- Tests: status → configurado:false con lista de secretos faltantes ✅ · bienvenida sin credenciales → 503 con instrucción ✅.

## 2026-08-14 — Jerarquía A/B + Bodega Concreces + Gerencia Comercial + Excepciones + Daniela/Victoria
- JERARQUÍA A/B (Regla #22): perfil en users/token; PERFIL_BLOQUEOS en auth.py (A vetado de contraloría/dashai/admin/gerencia/bodega; B vetado de clientes/simulador/compromiso). Endpoints revocar/reactivar (+clave reset) en /api/admin/users. Login bloquea activo:false. UsuariosModule con select perfil + botón Revocar. Test: usuario A → contraloría 403, clientes 200 ✅.
- CONSTITUCIÓN v8: reglas #22-#25, #31 (excepción), #32 (Daniela/Victoria) + 5 Leyes de Eficiencia + BOVEDA_ALGORITMO_ESPEJO socket (config protegido).
- BODEGA_DE_DATOS_CONCRECES (bodega_concreces.py): GET /api/bodega (94 registros: RUTs, renta, rol, dirección, respaldo OCR), POST /contrastar/{fid} (motor RUT eje central, expulsa mismatch), mapeo Concreces (Ingreso_Mesa/Tasacion/Riesgo/Escrituracion). Envío BLOQUEADO sin OCR+contraste (Regla #24).
- GERENCIA_COMERCIAL: /api/gerencia/cartera (63 ops del mes, hitos docs/firma/concreces/notaría, alertas notaría por regex en seguimiento), export-xlsx (openpyxl, HTTP 200 ✅), costo desarrollo (4.08 cr), audit loop 6h (Regla #25). UI glassmorphism dark slate + oro.
- PROTOCOLO EXCEPCIÓN (Regla #31): POST /api/excepciones/autorizar (re-valida clave bcrypt/password → firma digital, justificación ≥10 chars, registro INMUTABLE en excepciones_log — sin endpoints de borrado, alerta a Gerencia). Tests: clave mala 403 ✅, firma válida 200 con registro ✅. Modal AutorizacionExcepcion en Administración.
- DIVISIÓN OPERATIVA (Regla #32): paneles espejo Daniela Galindo (Revisión) / Victoria Vilche (Carga) en Administración, auto-selección por nombre de usuario logueado, banner de esqueleto (funciones definitivas bloqueadas hasta orden de Gerardo).
- Verificado visualmente: Administración (paneles+bodega) y Gerencia (tabla+export+costo) renderizan perfecto.

## Sesión 14-Jun-2026 (fork) — Malla de Inteligencia, Brokers y Centro de Mando Gerencial
Constitución Maestra: VERSION 16 (nuevas Reglas de Oro #34, #35, #36, #37, #38, #41, #43, #49, #52, #53, #54).

### Backend nuevo
- `malla_inteligencia.py`: routers broker/fuentes/hitos/flujos/mi-correo.
  - Módulo Brokers (perfil D): carpetas propias + 6 subcarpetas, proyección mensual, Estado de Situación, huella broker_activity_log, carga masiva con AUDITORÍA DE RUT por OCR (422 si el RUT del PDF no coincide).
  - Fuentes IMAP por panel (victoria/daniela/postventa/brokers/broker_<codigo>): etiqueta obligatoria, firma digital con clave, fuentes_auditoria_log (Regla #36).
  - Malla: hitos externos validados por RUT (Regla #34 — sin RUT → hitos_descartados), valueproperty→Tasación Solicitada, gmardones→Estudio Recibido + archivo PDF, motor de reparos (mardluf/gmardones/olave/ibarra), vendedores transitorios (Regla #37).
  - Radar Escrituración: doc20_folder (AFP+Liquidación+CMF → 'Pendiente de Información'), firmas_folder (Titular/Codeudor/Mandatario/Anexos — firma parcial JAMÁS verde), fecha firma manual + captura de correos notariales.
  - Auditoría real (POST /flujos/auditoria-real): escaneo IMAP inmediato (Regla #43, no inventar).
  - Mi Correo (Regla #38): IMAP validado en vivo, credencial AES-256-GCM en correos_ejecutivos, revelar solo dueño o admin+PIN, lector_ejecutivos_loop con pausas y alerta '⚠️ Su conexión de correo necesita actualización'.
- `grid_dashai.py` (Reglas #41/#53): espejo MD5 disco↔GridFS (espejo_concreces_cloud), eventos push (SSE /grid/stream + webhooks), resync sin interruptor, alerta 2h sin respaldo, POST /grid/disaster-recovery.
- `bodega_concreces.py`: router control (Regla #35 — discrepancias Bodega vs Ingreso, correo sobrio al Destinatario Maestro, NO bloquea); gerencia_cartera con resumen Subsidio/SinSubsidio/Total, brokers, divergencia_control, datos_incompletos ('Broker no actualizado'), inactivo_96h, radar, tipo_operacion, broker_origen; POST /gerencia/reclamo/{fid} (Regla #49 — manual, CC Victoria/Daniela, 'Solicitado el [fecha]') + gestion_gerencial_log (Regla #52).
- `auth.py`: whitelist perfil D. Seguridad: middleware cabeceras (HSTS/nosniff/X-Frame/XSS/Referrer/Permissions). ESLint --fix: 0 errores.

### Frontend
- Nuevos: BrokersModule.js, MiCorreoModule.js, components/GestorFuentesIMAP.js.
- AdministracionModule: paneles Daniela/Victoria/Postventa + GRID estado + Fuentes IMAP + Flujos Usada/Inmobiliaria + Control Auditor.
- GerenciaComercialModule: Centro de Mando — tarjetas segmentadas filtrantes, filtros multi-variable, feed 1s, iconografía ✅⏳⚠️, Maserati Action Buttons (.maserati-btn en App.css, 44px cristal JetBrains Mono), reclamos manuales, divergencia, filas roja/gris.
- CerebroDashAI: Destinatario Maestro. TasacionModule: Contacto de Visita. UsuariosModule: opción perfil D.

### Datos reales y credenciales
- Broker Maestro mutuaria/mutuaria2026 (Mutuaria y Leasing Limitada — Gerardo) con las 10 carpetas de Escrituración. Broker prueba broker1/broker123.
- Inmobiliarias seed: Maestra, Comac, Bestal. Auditoría real: 60 correos, 1 estudio detectado (CATALINA CASTILLO).

### Testing
- iteration_30: backend 22/22 OK; bug wiring App.js (brokers/micorreo) CORREGIDO y verificado en DOM + screenshots de Gerencia y Panel Broker.

### Pendiente
- Object Storage externo (S3/Emergent) como espejo adicional (hoy Espejo Cloud = GridFS). Twilio .env. 2º buzón IMAP. Alerta Cumpleaños (ofrecida, sin confirmar). OCR se pierde al forkar: reinstalar poppler-utils + tesseract-ocr(-spa).

## Sesión 14-Jun-2026 (cont.) — Bóveda Externa, Buzón Aprendizaje, Supercarpeta, Seamless UI, Huella #57
Constitución VERSION 19 (nuevas reglas #55, #56, #57).
- **Bóveda Externa (Object Storage Emergent)**: grid_dashai.py sube el espejo a `centralmutuos/espejo/*` (973/973 archivos respaldados). Delta en cada resync + backfill automático (30/min en grid_loop) + POST /grid/respaldo-externo (background). Disaster Recovery restaura también desde la nube externa (_bajar_nube). Usa EMERGENT_LLM_KEY + INTEGRATION_PROXY_URL (init /objstore).
- **Buzón de Aprendizaje**: router /buzon-aprendizaje (configurar con validación IMAP + AES-256, estado). Loop cada 15 min lee SOLO LECTURA (readonly + BODY.PEEK), clasifica asuntos (tasación/estudio/reparo/notaría) en db.buzon_aprendizaje. UI en Cerebro DashAI (dashai-buzon-aprendizaje). PENDIENTE: usuario debe ingresar email+clave de aplicación del 2º buzón en el panel DashAI.
- **Supercarpeta de Management (Regla #55)**: /api/supercarpeta (disponibilidad física de Tasación/Estudio/Borrador por cliente del mes, recién_24h) + /api/supercarpeta/archivo/{fid}?ruta= (preview PDF inline, anti path-traversal). Frontend SupercarpetaModule.js: 20 clientes/pantalla, iconos metálicos (.folder-metal), neón verde 24h (tr.neon-verde), modal iframe de PDF, filtro recién llegados. Nav fija 'supercarpeta' (admin + perfil B).
- **Seamless UI (Regla #56)**: clase .seamless-scope (App.css) — sin bordes/sombras en tablas y bloques de clientes de Gerencia/Administración/Supercarpeta/Brokers, separación por zebra-gradiente y espaciado, fondo Dark Slate.
- **Huella de Gestión (Regla #57)**: botones de reclamo con colores vibrantes (azul/verde/naranja + glow hover), al reclamar mutan a desaturado (.mb-hecho) con marca de tiempo exacta debajo (persistida en folder.reclamos_gerencia); confirmación si se reintenta en <12h.
- Fix de estabilidad: backfill externo movido a background task (evita 502 del gateway).

## 2026-08-14 — Sesión Fork: Reglas #58-#66, Bóveda ADN, Monitor SMTP, Flota Agosto
- **Regla #58 Identidad Inmobiliaria**: Carlos Salgado rectificado (RUT 13.820.383-2, BOETSCH · ALTO PARQUE, 1.290 UF, tipo inmobiliaria). `_origen_folder()` en bodega_concreces.py: prohibido 'DIRECTO' — prioridad Inmobiliaria > Broker > USADO > "⚠️ Falta Identidad de Inmobiliaria". Cartera ordenada por origen.
- **Regla #62 Monitor SMTP**: backend/monitor_envios.py — correos_fallidos (payload completo para re-envío atómico), GET /api/correos/fallidos, POST /api/correos/fallidos/{id}/reintentar, GET /api/correos/briefing. email_service.send_mail registra fallos (param registro_fallo). Guard exigir_correo_ok en flujos/firmas (409 si hay correo fallido del cliente). Frontend: EstadoSalida.js (headers Admin/Brokers) + BriefingMananero.js (modal 1er login del día).
- **Regla #63 Ultra-Precisión 79.50%**: credit_engine LTV_MAX_63=0.795 (10 decimales), ajuste_pie_795 automático en simular_credito; PUT /api/compromiso/{fid} ajusta pie en usadas; compromiso_pdf bloquea PDF (422) si usada > 79.5%.
- **Regla #64 Verdad DashAI**: backend/perfil_consolidado.py — cosechar/cosechar_carpeta/imap_permitido (gates IMAP en server.py: adjuntos aprobación, ocr backfill, perfil vuelo, tasación fecha), cosecha_loop 30 min, POST /api/perfil/{fid}/validar (defensa admin).
- **Regla #65 Certeza 100%**: discrepancias rut/monto/rol → campos_bloqueados estado rojo. validar_rut_chileno (módulo 11) en base_historica.py + rutValido en ClientesModule (badge ✓100%).
- **Base de Datos Histórica**: backend/base_historica.py — historia_loop resumible (bloques de 100, checkpoint db.config), REGLA: sin email no entra; export xlsx en memoria. Frontend BaseHistoricaModule.js (nav basehistorica). Motor pausado por defecto (iniciar/pausar).
- **Regla #66 Bóveda ADN + EXPEDIENTE_360**: backend/adn_clientes.py — adn_clientes_360 (54 registros, 10 rechazados por RUT), expediente (titular/codeudor/propiedad fojas-número-año/hitos legales/documentos con link_boveda), máscara de privacidad por rol (admin/B global, resto cartera propia — aplicada también a 'piezas_modulo'), POST /api/adn/succionar/{rut} (OCR PDFs locales), adn_loop 60 min. Certificación: "Maserati Certificado: 66 Reglas Activas...". Integrado en CompromisoEditor (GET compromiso prellenado desde ADN) y Contraloría (adn_360 en certificado).
- **Supercarpeta V3**: lee de ADN (sin escanear PDFs), columnas Estado Tasación/Estudio Títulos/ESTADO LEGAL (✅/⚠️ clickeable con texto del abogado/⏳)/Detalle Reparos (celda naranja)/Cesión. PENDIENTE en rojo.
- **Minado de reparos PDF**: _minar_reparos_pdf en malla (OBS_RE extrae texto exacto de Observaciones/Reparos). Alertas a Malla (db.alertas, Ejecutivos A y B) + upsert ADN al detectar hito. auditoria_loop tiempo real cada 10 min (dias=2). flujos_auditoria_real(limit, dias).
- **Cosechas ejecutadas**: 15 días (150 correos, 6 tasaciones) + 30 días (300 correos: tasación Claudia Zurita, 2 estudios Catalina Castillo, 1 reparo transcrito, 0 sin respaldo).
- **FLOTA AGOSTO (purga de vistas)**: POST /api/supercarpeta/flota (solo admin) — 17 autorizados (13 con carpeta: Luis Guerrero, Kanela Ibañez, Yuritza Bravo, Luis Sepulveda, Catalina Castillo, John Diaz, Javiera Salgado, Karla Soto, Héctor Curi, Claudia Zurita, Paula Vergara, Kevin Olivos, Carlos Salgado; 4 sin carpeta: Ruben Zabala, Marioli Montero, Miguel Escalona, Jose Olivares). Supercarpeta y Gerencia filtran solo la flota. Carpetas intactas en Bóveda (modo seguro).
- **Fixes**: loops zombie post hot-reload (_task_blindada termina en "after close" — causa del cuelgue recurrente y del deploy fallido 03:04), bloque de routers duplicado/corrupto al final de server.py (NameError de_router), gerencia/cartera sin N+1 (0.24s, antes colgaba), shape mismatch modal reparos Gerencia (reparos.items + alertas), reparos-btn en ClientesModule cuenta estudio_reparos.items + reparos_alertas, "Soporte Técnico" → "Respuestas Mesa Clientes" (5 registros seguimiento).
- **Constitución v24** (reglas hasta #66). Testing: iteration_31 (19/19 OK) e iteration_32 (backend 9/9; bug frontend de Gerencia corregido después).

## 2026-08-14 (2ª tanda) — Bitácora de Tiempos + Rescate Catalina Castillo
- **Bitácora de Tiempos**: GET /api/supercarpeta/bitacora/{fid}?hito=tasacion|estudio — fecha de solicitud (correos_smtp_log > seguimiento > hitos_externos > huella gerencial), destinatario, días/horas transcurridos, extracto de lo pedido, demora_48h en ROJO, y "ERROR DE SEGUIMIENTO" si no hay respaldo (Regla de Hierro). Vista supercarpeta incluye bitacora por fila; frontend: estados clickeables (bitacora-tasacion-{id}, bitacora-legal-{id}) → modal bitacora-modal.
- **Detección firma cesión**: NOTARIA_KW ampliado (cesión, serie de créditos, firma confirmada) → folder.firma_cesion_confirmada_at; expediente_360.hitos_legales ahora con campos exactos estudio_reparos / tasacion_estado / firma_cesion.
- **Rescate RUTs Flota**: Catalina Castillo 20.064.076-4 rescatado de hitos_externos (validado DV). Sin RUT interno disponible: Kanela Ibañez, Yuritza Bravo, Javiera Salgado, Luis Sepúlveda, Héctor Curi, Kevin Olivos (fuera del ADN hasta que llegue el dato real — Reglas #64/#65, no se inventa).
- **Catalina Castillo sincronizada**: en ADN (55 registros), informe ESTUDIO_Informe Catalina Andrea Castillo Pauvif en 07_estudio_titulo, Ver PDF apunta al Informe (prioridad 'informe' en matching de documentos), bitácora resuelta (13/08 · Abogados · respondido), PDF servido 200/2.9MB.

## 2026-08-14 (3ª tanda) — Rescate RUTs desde el Cerebro DashAI (sin IMAP)
- Fuente: minería SOLO en colecciones internas (ai_extract_cache, gastos_op_log, mesa_enviados, proc_queue, folders) — el usuario ordenó NO minar GridFS/buzón por ahora.
- **YURITZA BRAVO** = 18.865.076-7 (carpeta duplicada "YARITZA BRAVO" tenía el RUT; DV validado). En ADN ✓.
- **HÉCTOR CURI Y COMPLEMENTO** = 25.426.472-5 (HECTOR JOHAN CURI CAMPOS, gastos_op_log). Complemento: madre DANA BANEZA CAMPOS ESPINOZA 22.544.754-3 → perfil_consolidado.rut_codeudor. Proyecto Uvas y el Viento / Boetsch / con subsidio. En ADN ✓ con codeudor amarrado.
- **KEVIN OLIVOS** = 19.930.960-9 (KEVIN ARNOLD WILLIAMS OLIVOS ABARCA, ai_extract_cache confianza 0.99; el "25802753" de la carpeta era un teléfono, no RUT). En ADN ✓.
- Descartes con evidencia: 21.256.138-K es de Natalia Javiera Illanes Santana (NO Javiera Salgado); 10.568.791-5 es de Patricia Cabezas (ejecutiva Andrea Salgado).
- SIN RUT interno (agotado el cerebro): KANELA IBAÑEZ (su "25790880" no pasa DV, parece teléfono), JAVIERA SALGADO, LUIS SEPÚLVEDA. Requieren dato del usuario o pasada IMAP futura.
- Volcado ADN ejecutado vía POST /api/adn/volcar (59 procesados). Verificado en /api/supercarpeta: en_adn=true para los 3.

## 2026-08-14 (4ª tanda) — Reparación Total Supercarpeta (Orden Crítica Consolidada P0-P12)
- P0: 17 clientes exactos Proyección Agosto seedados (4 creados: Ruben Zabala, Marioli Montero, Miguel Escalona, Jose Olivares). Meta 41.717 UF, suma 39.717 (José Olivares monto pendiente → alerta Gerencia activa).
- P1/P5: Vista lee ADN-first. Columnas: Cliente, RUT, Inmobiliaria (Casa Usada/Directa/nombre), Proyecto, Ciudad, NOTARÍA (Por Asignar + coherencia ciudad), Broker (forzado Mutuaria y Leasing p/ flota), Monto UF + subsidio pill + REACTIVACIÓN (Karla Soto).
- P2: Cosecha reparada: REPARO_REMITENTES corregido (majluf/vilches/amvabogados — antes 'mardluf' typo = nunca matcheaba), _auditar_lote extrae y PERSISTE en folder + EXPEDIENTE_360; perfil_consolidado.cosechar sincroniza ADN inmediato.
- P3: Barrido forzado POST /api/flujos/barrido-forzado?dias=N (tarea background + GET /barrido-estado). Solo 2 cuentas IMAP con credenciales (contacto@centralmutuos.cl SIN credenciales — pedir app password al usuario).
- P4: Bitácora 48h ya existente, integrada al Panel Lateral.
- P6: Ingreso manual respaldo POST /supercarpeta/manual/{fid} (rut c/ DV, inmobiliaria, broker, monto, proyecto, ciudad, notaria).
- P7: Estados manuales con bitácora inmutable (estado_manual_log), marca ✏️, conflicto auto-vs-manual con resolver mantener/sobreescribir. 8 hitos: tasacion, estudio, serviu, promesa, set_credito, carpeta_notaria, escritura, cesion.
- P8: Fuentes por columna reestructuradas: BLOQUE GLOBAL + BLOQUE INDIVIDUAL, casillas ilimitadas con nombre descriptivo, agregar/quitar inmediato (accion-based API), última detección, bitácora fuentes_log. Notaría = fuente SOLO individual.
- P9: Set de Crédito: 'Set Para la Firma'=⏳ esperando; 'Set Firmado' exige verificación de firmas en PDF (_verificar_firmas_pdf: AcroForm SigFlags, texto firma electrónica, imagen manuscrita + OCR) → ✅ o ⚠️ Verificación Pendiente.
- P10: Agregar/Eliminar cliente (eliminación solo de vista, ficha ADN histórica, bitácora supercarpeta_log).
- P11: Parser proyección broker (Excel/PDF/CSV) → _aplicar_proyeccion: upsert + reemplazo sin duplicados + alerta resumen a Gerencia.
- P12: Rediseño planilla alto contraste: filas #1E2A3A/#253347, separadores blancos, encabezado dorado 15%, estados como botones (#1A5C2A/#1A3A5C/#7A4A00/#5C1A1A/manual #3A3A3A+amarillo/N/A), fila totales dorada con barra de avance, hover borde dorado.
- CASO KANELA: estudio 'Con Reparos' con texto de reparos visible en Bóveda/panel ✓.
- REGLA DE ORO UF (violación corregida): eliminado fallback mindicador.cl — SII EXCLUSIVO; si SII cae → último valor MongoDB + alerta discreta a Gerencia; eliminados defaults 39842/39000 (credit_engine._uf_oficial + UF_SII_CACHE).
- CONSTITUCIÓN v26: Regla #67 (Supremacía Bóveda en pantalla) + Regla de Oro de Eficiencia perpetua (reutilizar, cambios quirúrgicos, arranque liviano).
- FIXES: server.py cola duplicada corrupta (r(_hist_mod...)), constitucion.py duplicado, SupercarpetaModule panel state perdido (crash 'panel is not defined' reportado por testing iteration_33 — corregido y verificado sin referencias indefinidas).

## 2026-08-14 (sesión fork — lote grande)
- Cuenta de Barrido (solo lectura) en Panel ⚙️: designación de casilla existente, barrido manual + loop 20 min, cosecha de RUTs faltantes.
- Auditoría de Bóveda (4 fuentes: ficha ADN → EXPEDIENTE_360 → PDFs → correos 90d): 7 RUTs encontrados y escritos; endpoint POST/GET /api/supercarpeta/auditoria-boveda + modal reporte.
- Edición en línea (doble clic) de TODOS los campos de identidad con bitácora valor anterior/nuevo (estado_manual_log).
- Reset de estados falsos de firma (migración v1) + FIRMA_REAL_RE: la firma SOLO se confirma con evidencia real de correo fuente.
- Encabezados sticky dorados + columnas Cliente/RUT fijas (Supercarpeta y Gerencia).
- Gerencia Comercial: orden inamovible de 14 columnas, botones de estado por color, columnas Doc2.0/Firmas/Divergencia/Concreces/Mesa ELIMINADAS por orden del usuario, feed Malla eliminado, filas compactas.
- Navegación mensual (selector de mes), traslado "Pasar a Septiembre" con etiqueta Arrastre, eliminación por fila con confirmación (ficha ADN intacta).
- Avance por cliente (7 etapas ponderadas, serviu redistribuido sin subsidio) + Panel de Meta (UF proyectadas/en avance/cerradas, % global) + notificaciones 100% cliente y hitos 50/75/100% + snapshot diario en ADN + sync cumplimiento_broker a Gerencia.
- ORDEN SUPREMA: _hitos de Gerencia lee la bóveda con escritura obligatoria de vuelta + alerta roja de error de lectura (caso Miguel Escalona reparado).
- Panel de Gestión por Ejecutivo (Daniela/Victoria/Postventa): detección automática por nombre desde las 2 casillas del admin (cero configuración), métricas hoy/semana/mes, barras por hora, tipos, clientes gestionados, comparativa semanal, extras postventa, privacidad absoluta (solo cabeceras).
- Captura automática de remitentes por hito + panel 📡 Confirmar/Reubicar/Eliminar/Bloquear con aprendizaje acumulativo (2 correcciones = criterio permanente).
- Limpieza total autorizada: 4 scripts huérfanos + 29 tests antiguos + backup storage + 4 carpetas prueba/duplicadas eliminadas; índice redundante drop; RUT falso de Carlos Salgado retirado (auditoría encontró el real 13.820.383-2 en ADN); inmobiliarias de la planilla oficial escritas en bóveda.
- Fix cuelgue hot-reload: cancelación de loops de fondo en shutdown (_BG_TASKS).
- Tests: iteration_34 (pass) e iteration_35 (100% backend+frontend, 17 clientes visibles verificados).

## Sesión 2026-08-17 (fork) — Módulo CBR + Comisiones (EXCLUSIVO Admin General)
- Nuevo módulo "💰 CBR Mesa" en Supercarpeta (botón solo visible para rol admin/maestro).
- Backend: `fetch_simulacion_attachments()` en email_service.py — búsqueda DIRIGIDA por cliente
  (X-GM-RAW `from:aprobaciones@centralmutuos.cl "<nombre>"`, últimos 3 correos c/u, All Mail, solo lectura).
- Extracción: `_extraer_cbr_pdf()` en malla_inteligencia.py — 2ª página, sección "Gastos Operacionales",
  fila "CBR (Inscripción Registro Propiedad + Hipoteca)". REGLA DE HIERRO: sin valor → NO ENCONTRADO.
- Guardado: campo `costo_CBR` en db.folders + ADN_CLIENTES_360 (12/17 clientes poblados).
- Comisiones: BOETCH/ECOMAC/POCH 1%, COMOD 0.8%, USADA 0.5%, WORD/URBANIZATE/MAESTRA → "REVISAR CON GERENCIA".
- Excel (openpyxl): Nombre, Broker, Monto crédito UF, Valor CBR, Comisión, % aplicado, Moneda, Fecha correo, Estado.
- Endpoints: GET/POST /api/supercarpeta/cbr/{estado,extraer,excel} — todos con _exigir_admin_general (403 verificado).
- Resultado real: 12/17 ENCONTRADO. NO ENCONTRADO (sin correo de aprobaciones@): José Olivares,
  Kanela Ibáñez, Marioli Montero, Rubén Zabala, Yuritza Bravo.
- Aprendizaje: la búsqueda genérica from:aprobaciones@ + descarga total era demasiado lenta (>10 min,
  colgaba el reload); la búsqueda dirigida por nombre la baja a ~2-4 min.

## Sesión 2026-08-17 (cont.) — CBR: edición manual + totales
- POST /api/supercarpeta/cbr/manual (solo Admin General): edita valor_cbr o comision por cliente,
  marca origen "manual" y guarda de inmediato en db.folders + ADN_CLIENTES_360 (costo_CBR / comision).
- UI: doble clic en Valor CBR y Comisión → input inline (Enter/blur guarda, Escape cancela).
  Gris = automático, azul = manual. Fila TOTAL fija (total_cbr, total_comision) recalculada por backend.
- Excel: fila TOTAL al final. REGLA: totales solo suman filas con dato (auto o manual).
- Verificado e2e: manual Kanela 14,5 UF y Paula comisión 20 UF → ADN actualizado, totales 171,34/171,23 UF.

## Sesión 2026-08-17 (cont. 2) — CBR: doble moneda + Tasación + Est. Títulos + Total Pagado
- Extracción ampliada: _extraer_gastos_pdf saca CBR + Tasación + Estudio de Títulos de la misma
  simulación (2ª página, Gastos Operacionales). Guardados en folders + ADN como costo_CBR,
  costo_tasacion, costo_estudio_titulos.
- Columnas editables con doble clic (valor_cbr, tasacion, est_titulos, comision) vía POST /cbr/manual.
  Manual = azul, automático = gris. Valores manuales se PRESERVAN entre corridas (old_map).
- Total Pagado por fila = CBR+Tasación+Títulos, con ⚠ si falta algún dato (no editable).
- Totales doble moneda (REGLA: nunca mezclar UF con CLP): fila TOTAL EN UF (azul #1e3a8a) y
  TOTAL EN PESOS (verde #14532d), sticky al fondo. Incluye gran_total_uf/clp.
- Excel 12 columnas + 2 filas de totales por moneda. Celda Total Pagado amarilla si incompleto.
- Verificado e2e: 12/17, tasación/títulos 3.0 UF extraídos, gran total 340,09 UF, ADN actualizado.
- Aprendizaje: el backend tarda ~30-60s en reiniciar con hot reload; reintentar login con loop.

## Sesión 2026-08-17 (cont. 3) — Carta Oferta + Inmobiliarias + Solicitud CO/RS + Editabilidad total CBR
- Columna "Carta Oferta" en Supercarpeta (hito carta_oferta: HITOS_VALIDOS, FUENTES_HITOS, estados
  manuales, gear de fuentes, mismos colores). Estados: Pendiente/Solicitada/Recibida/Aprobada/Rechazada.
- Inmobiliarias: GET/POST /api/supercarpeta/inmobiliarias (db.inmobiliarias). Detección automática desde
  clientes de la Bóveda + alta manual. Cada una con encargado + correo.
- Solicitud CO+RS (UN solo botón 📨 por fila): GET /solicitud-doc/{fid} (vista previa autocompletada:
  inmobiliaria detectada, encargado, RUT, proyecto) + POST /solicitud-doc/{fid}/enviar (send_mail desde
  gerardo.ext/secundaria, SMTP 250 verificado). Al enviar marca carta_oferta y serviu = "Solicitada"
  con bitácora (bitacora_solicitudes). Sin correo configurado → advertencia + botón deshabilitado.
- CBR REGLA ABSOLUTA DE EDITABILIDAD: TODOS los campos editables con doble clic (cliente, rut, broker,
  proyecto, tipo, subsidio, monto, cbr, tasación, títulos, total_pagado, comisión, %, moneda, estado).
  total_pagado manual = deja de recalcularse (gran total lo respeta — verificado 350,59).
  pct editado → recalcula comisión si no es manual (verificado 283,6). Persistencia por campo:
  folder+_sync_adn (rut/broker/proyecto/tipo/subsidio/monto), costo_* docs, adn.comision,
  adn.total_pagado, adn.cbr_overrides.{campo}. Filas ahora llevan fid.
- Tabla CBR: 16 columnas + totales sticky doble moneda. Excel usa _cbr_total_fila (override manual).

## Sesión 2026-08-17 (cont. 4) — Módulo Carta Oferta DEFINITIVO + Firma + Valores Base
- Contactos por INMOBILIARIA + PROYECTO: db.contactos_carta, GET/POST /supercarpeta/contactos-carta
  (alta/edición/desactivar, nunca eliminar). Selección automática: combinación exacta → general → legado
  db.inmobiliarias → alerta. Verificado: Boetsch+"Las Uvas y el Viento" → Rodrigo Quintero.
- CC GLOBALES obligatorios: config cc_globales (semilla Victoria Vilche + Daniela Galindo), GET/POST
  /supercarpeta/cc-globales (solo desactivar, no eliminar). CC server-enforced en cada envío.
- Plantilla definitiva: asunto "Carta Oferta - [Cliente] - [Proyecto]"; saludo por género
  (termina en 'a' → Estimada); VALIDACIÓN BLOQUEANTE si falta RUT/Proyecto/Resolución SERVIU
  (mensaje exacto, verificado 400). resolucion_serviu se persiste en folder + _sync_adn.
- Registro en ADN: push envios_carta_oferta {fecha, para, cc, estado, smtp_code} (verificado).
- Marcado ficha: _marcado_docs → ✅verde/🟡amarillo(cuál falta)/🔴rojo/🔵azul(verif. manual).
  Estado nuevo "Pendiente verificación manual" (chip azul #1A3A8A). Badge en celda Carta Oferta.
- FIRMA: imagen definitiva azul/dorada "CENTRAL MUTUOS / Concreces" (config firma_correo) + firma
  personal "Gerardo Barrera P. / Asesor Jefe Externo / Canal Inmobiliarias y Brokers / Central Mutuos".
  CORRECCIÓN: el texto escrito dice SOLO "Central Mutuos" (el logo mantiene su diseño).
- VALORES BASE OPERACIONALES: Tasación 2,5 UF / Est. Títulos 2 UF (config valores_base, POST
  /supercarpeta/valores-base, editable doble clic en modal CBR). Se precargan en clientes sin dato;
  manuales intactos. Backfill aplicado (10 celdas).
- NOTA: verificación automática de firma en compromisos de compraventa (usadas) queda como estado
  manual "Pendiente verificación manual" — automatización pendiente.

## 2026-06 (fork) — Verificación IA de firma de Promesa + Numeración correlativa
- **Verificación de Firma Compromiso/Promesa (IA)**: `_verificar_compromiso_ia` en malla_inteligencia.py.
  Al detectar correo con promesa/compromiso de compraventa (regex asunto+cuerpo) en `_auditar_lote`
  (loop 24/7 + auditoría real + barrido), descarga el PDF adjunto, corre `_verificar_firmas_pdf`
  (heurística AcroForm/texto/OCR) + `ai_extract.verificar_firma_compromiso` (gpt-5.4-mini, prohibido
  inventar). Firmado con confianza alta → estado VERDE "Firmada (verificada IA)"; cualquier duda o
  sin firma → AZUL "Pendiente verificación manual". Guarda `promesa_verificacion` +
  `promesa_verificada_at` en folder; columna Promesa CV la lee (est_promesa) con 🤖 detalle/tooltip
  (testid promesa-ia-{id}). Override manual del Admin ya operativo vía estados manuales (lápiz) con
  detección de conflicto (auto_marks.promesa). Adjuntos archivados como PROMESA_* en 99_otros.
  Solo aplica a correos nuevos (sin retroactivo, decisión del usuario). PASS test firmado/sin firma.
- **Numeración correlativa (solo lectura, recalculada auto)**: Supercarpeta columna N° sticky
  (testid super-numero-{id}) a la izquierda del Cliente (sticky lefts 0/46/286); tabla CBR modal
  con N°; Excel CBR con "N°" primera columna (fills/estado corridos a col 8/13). Gastos
  Operacionales: números en Envíos y Seguimiento de Pagos (gastos-log-numero-{i}), Cobros de
  Tasación (cobro-numero-{i}) e Historial mensual. Verificado: UI 1-18 Supercarpeta, 1-10 Gastos,
  Excel openpyxl OK.

## 2026-06 (fork) — Flujo definitivo CO+RS + Resumen Gerencia + Vista Móvil + Comisiones
- **COMISIONES (reglas del dueño)**: Maestra 0,5% sin subsidio (Claudia Zurita) / 1% con subsidio;
  Ecomac 0,8% con subsidio / 1% sin subsidio. `_comision_cliente(fd, monto, con_subsidio)`. 6/6 PASS.
- **PARTE 1 CO+RS**: semilla contactos (Boetsch→Celinda Soria general, Rodrigo Quintero→Las Uvas y
  el Viento, Rodrigo Salazar→Fuchslocker, Maestra/Ecomac a configurar — correos vacíos = alerta
  bloqueante). `_contacto_para` tolera Boetch/Boetsch (contención). VIVIENDA USADA: solicitud de
  Compromiso de Compraventa al VENDEDOR directo del cliente (folder.vendedor_usada), asunto/cuerpo
  propios, sin exigir proyecto/resolución. GET/POST /supercarpeta/vendedores-usada.
- **PARTE 2 Reenvío automático**: `_reenvio_co_rs` — SOLO cuando carta_oferta Y serviu están en
  (Recibida|Aprobada) reenvía JUNTOS a destinatarios globales activos (Victoria/Daniela) con
  adjuntos detectados en la carpeta (regex carta.oferta / serviu|resoluc). Nunca parciales, nunca
  duplica (co_rs_reenviado_at). Hook en POST /supercarpeta/estado + loop 30 min (reenvio_co_rs_loop,
  blindado en server.py). 3/3 PASS con send_mail simulado.
- **PARTE 4 Marcado**: _marcado_docs ahora indica en verde si el reenvío fue ejecutado o está en curso;
  azul (verificación manual) NO reenvía.
- **RESUMEN SEMANAL GERENCIA**: lunes ≥08:00 Chile (resumen_gerencia_loop, dedupe semana ISO) —
  avance % por cliente de la Flota, proyección UF vs meta y cuellos de botella (_cuellos_cliente:
  faltantes, tasación +48h, reparos, promesa sin verificar, CO+RS incompletos, sin fecha de firma,
  set pendiente). Destinatarios editables (default rodrigoibanez + cc globales). Endpoints:
  GET /supercarpeta/resumen-gerencia, POST .../config, POST .../enviar (preview confirm:false OK).
- **VISTA MÓVIL (≤768px)**: Supercarpeta y Gerencia Comercial renderizan TARJETAS apiladas
  (N°, cliente, RUT, monto, avance, chips de estados clicables → panel, pedir CO+RS/Compromiso,
  fecha firma, reclamos). Tabla intacta en escritorio. Verificado con screenshots 390x844.
- **UI**: modal 🏢 con sección "Vendedores — Vivienda Usada" (alerta sin configurar); modal de
  solicitud adaptado a usada (título Compromiso CV, sin campos serviu, PARA=vendedor); botón por
  fila "📨 Pedir Compromiso CV" en clientes Casa Usada.

## 2026-06 (fork) — Matriz de Documentos + Panel de Fuentes + Confirmación + Auto-envío Mesa
- **AUDITORÍA ADN**: inmobiliarias unificadas a canónico (BOETCH/WORD/MAESTRA/ECOMAC/URBANIZATE/
  CASA USADA) en folders + ADN. Proyectos: UVAS Y EL VIENTO (confirmado por Gerencia) corregido;
  UVAS Y EL VIENTO 2 y FUCHSLOCKER validados; pendientes confirmar: Escalona (UVAS/LA GRANJA) y
  C. Salgado (Proyecto Test vs ALTO PARQUE). Listas maestras en config.lista_maestra_origenes.
- **MATRIZ DOCUMENTOS POR TIPO** (_tipo_cliente/_docs_de_tipo/_marcado_documentos): nueva c/sub
  → CO+RS · nueva s/sub → CO · usada c/sub → Compromiso+Cert Subsidio · usada s/sub → Compromiso
  O Carta Pie (elige ejecutivo). Nuevos hitos cert_subsidio/carta_pie. Marcado por documento
  ✅🟡🔴🔵 (badges en tabla y tarjetas, testid doc-badge-{hito}-{id}). Reenvío automático a
  Victoria/Daniela SOLO con TODOS los docs del tipo confirmados (_reenvio_co_rs generalizado).
- **BARRIDO detecta llegadas**: carta oferta/resolución/cert subsidio/carta pie entrantes →
  _marcar_doc_llegada = azul "Pendiente verificación manual" (jamás confirma sola) + alerta.
- **PANEL DE FUENTES** (GET /supercarpeta/fuentes-panel): Sección 1 inmobiliarias (correo general
  db.inmobiliarias + proyectos con contactos por función CO/tasación/estudio, ⚙ expandible),
  Sección 2 brokers (db.brokers_fuentes, word_consultor/autocorredor, 3 contactos), Sección 3
  individuales usada (tipo + docs auto). Registro completo (reg-nueva-inmobiliaria/reg-nuevo-broker).
  Orden destinatario: individual → proyecto → general → broker. _norm_inmo unifica boetsch→boetch.
- **BLOQUEO ORIGEN**: POST /supercarpeta/manual campo inmobiliaria/broker inexistente → 409
  ORIGEN_NO_CONFIGURADO → frontend abre registro prefilleado. lista_maestra en vista.
- **CUADRO CONFIRMACIÓN** (siempre, sin excepción): modal 70%+ pantalla, no cierra con clic fuera,
  campos bloqueados hasta EDITAR, CC fijos no editables, CONFIRMAR/EDITAR/CANCELAR. APRENDIZAJE:
  destinatario editado → se guarda en fuentes (contactos_carta o vendedor_usada) al enviar.
- **AUTO-ENVÍO EXCLUSIVO MESA**: barrido activo=True cada 20 min; simulación PDF de aprobaciones@
  → extrae CBR pág. 2 (_extraer_gastos_pdf) → correo ajustado c/ gastos base (2,5+2 UF) + PDF a
  gerardo.ext@centralmutuos.cl SIN confirm (db.auto_envios_aprobaciones dedupe, 11 históricos
  omitidos). Sin CBR legible → NO envía + alerta Admin. Todo lo demás mantiene confirm manual.
- **CONTACTOS DETECTADOS EN BUZÓN** (verificar): Celinda Soria=csoria@boetsch.cl ✓ cargado;
  Uvas y el Viento 2=uvasyelviento2@boetsch.cl; Ecomac general=xgomez@ecomac.cl; Maestra
  general=fabiola.perez@maestra.cl. Rodrigo Salazar: NO encontrado (pendiente usuario).
  Quintero mantiene correo de prueba del usuario (ethangerardobarr@gmail.com).
- TESTS: 6/6 matriz+reenvío PASS · auto-envío 2/2 PASS (con CBR envía, sin CBR alerta, no duplica)
  · 409 verificado · previews por tipo verificados · screenshots UI OK.
- 2026-06: Comisión WORD y URBANIZATE = 0,5% (regla del dueño) — testeado 4/4 PASS
- 2026-06: Rodrigo Salazar (BOETCH/Fuchslocker) = fuchslocher@boetsch.cl — confirmado por el dueño, cargado en contactos_carta
- 2026-06: Proyectos confirmados por Gerencia: Escalona → UVAS Y EL VIENTO; C. Salgado → ALTO PARQUE (folder + ADN). Lista maestra sin pendientes.
- 2026-06: Testing agent iteración 36: backend 13/13 PASS, frontend 100% (flujo documentos e2e, panel fuentes, 409, confirmación, móvil). Hallazgo de datos: KANELA IBAÑEZ duplicada (RUT 20.219.355-2 vs 25790773) — pendiente decisión del dueño.
