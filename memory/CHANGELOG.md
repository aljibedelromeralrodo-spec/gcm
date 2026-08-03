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
