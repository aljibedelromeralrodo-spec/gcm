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
