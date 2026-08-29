# CHANGELOG — Central Mutuos

## 2026-06 — Acceso exclusivo Victoria Vilches (COMPLETADO)
- Usuario sembrado: victoria.vilches@centralmutuos.cl / clave temporal Victoria2024
  (rol administracion + solo_modulo="victoria" + clave_temporal=true, seed idempotente en ensure_seed).
- Al ingresar ve SOLO su módulo de trabajo (VictoriaWorkspace.js: VictoriaBoveda + ManualConcreces),
  sin sidebar, sin dashboard ni paneles de administrador. Gate en App.js (user.solo_modulo === "victoria").
- Cambio de contraseña: banner de clave temporal al primer ingreso + botón "Cambiar contraseña" en
  el header (siempre disponible desde su perfil). Endpoint POST /api/auth/cambiar-clave
  (verifica clave actual, valida mín 8 chars + mayúscula + número, limpia clave_temporal).
- Verificado: curl E2E (login, clave incorrecta 400, clave débil 400, cambio OK, re-login case-insensitive)
  + screenshot (workspace exclusivo, banner visible, sidebar ausente).

## PENDIENTE INMEDIATO
- Importar listado "ds19 01 inmoboliarias" al Módulo Publicidad desde la imagen de 174 proyectos
  usatusubsidio.cl enviada por el usuario (solo emails válidos, deduplicar, excluir @ecomac.cl).
  Asset: https://customer-assets-gfyr7b9c.emergentagent.net/job_96f233fb-cd92-45e9-8847-7be7b345f873/artifacts/yuc588dl_image.webp

## 2026-06 — REDISEÑO COMPLETO Módulo Victoria (COMPLETADO, iteración 55: 100%)
- Nuevo workspace exclusivo (negro mate + dorado, Playfair Display, info grande):
  /app/frontend/src/victoria/{theme.js, VictoriaDashboard.js, VictoriaFicha.js, DocViewer.js}
  + shell /app/frontend/src/pages/VictoriaWorkspace.js (nav stack en sessionStorage vw_nav_v2).
- Dashboard de entrada: 5 KPIs (pendientes, docs faltantes, validaciones aprobadas, alertas, estado general),
  lista clientes con estado/siguiente acción, avisos, sin clasificar con asignación, buscador+filtro, crear ficha.
- Flujo guiado 4 pasos: 1 Recepción/clasificación (historial + subir + reclasificar + preview),
  2 Validación Reglas de Oro 11-14 + formularios editables, 3 Checklist + documento de envío en iframe +
  confirmar formularios, 4 Envío a ConCreces con checkbox de declaración + botón descriptivo.
- Preview instantáneo: GET /api/victoria/documentos/{did}/contenido (inline PDF/imagen vía blob);
  Aceptar/Rechazar con motivo → POST /api/victoria/documentos/{did}/revision; rechazados quedan
  excluidos de auditar_cliente y generan aviso.
- Contactabilidad: PUT /clientes/{cid}/contacto (email/tel), POST /clientes/{cid}/enviar-correo
  (send_mail secundaria, historial en victoria_contactos), link wa.me pre-armado con faltantes.
- Navegación con memoria: Volver conserva búsqueda/filtro/scroll; F5 restaura misma ficha y paso.
- Nuevos endpoints extra: GET /api/victoria/dashboard (consolidado), PUT /documentos/{did}/tipo.
- Testing: iteration_55.json — backend 18/18, frontend 100%, regresión admin OK. Sin bugs.
- Notas menores del reporte (no bloqueantes): polling 30/45s sin backoff con pestaña oculta;
  bcrypt cold-start 40-50s tras restart (conocido).

## 2026-06 — Regla de Oro 15 + Trazabilidad + Demo (COMPLETADO, iteración 56: backend 18/18)
1. VALIDACIÓN DE INGRESO IRRENUNCIABLE (Regla de Oro 15, sembrada en Constitución):
   - _validar_ingreso contrasta RUT titular/RUT codeudor/rol/dirección de cada doc entrante vs ficha.
   - Correo: mismatch → doc en CUARENTENA (cliente_id null + candidato + validaciones_ingreso) + aviso crítico.
   - Manual: 409 VALIDACION_BLOQUEADA {codigo, fallas, pin_configurado}; carga forzada exige PIN 4 dígitos
     (bcrypt en users.pin_seguridad_hash, POST /api/victoria/pin) y queda registrada (forzado_manual + aviso).
   - Endpoints: POST /cuarentena/{did}/revalidar (asocia si ya coincide), /cuarentena/{did}/asociar (con PIN),
     /documentos/{did}/descartar (motivo obligatorio). /sin-clasificar/{did}/asignar bloqueado para cuarentena.
   - Nuevos tipos doc: liquidacion, cert_matrimonio, certificado_avaluo, cedula.
   - Dashboard: secciones Cuarentena + Monitor en tiempo real (victoria_eventos, chips ✓/✕/— por validación).
   - Frontend: Cuarentena.js, MonitorCorreo.js (ChipsValidacion), PinModal.js; Paso1 maneja 409+PIN.
2. TRAZABILIDAD: documento-envio envuelve datos críticos en <span class='traz'> (hover lupa, clic → postMessage);
   GET /clientes/{cid}/origen-dato/{campo} devuelve doc origen + página (pypdf búsqueda normalizada);
   PreviewFlotante.js abre el PDF en la página exacta; cerrar vuelve al punto exacto. Mapeo: RUT→cédula/carpeta,
   rol→tasación, dirección→títulos.
3. DEMO VICTORIA: DemoVictoria.js (9 escenas animadas, datos ficticios Juan Pérez Soto 3.500 UF, cronómetro,
   tiempos por paso, total 58,3 s; controles reproducir/pausar/reiniciar; gate #demo-victoria en App.js).
   Video MP4 1:20 (933KB) generado con Playwright+ffmpeg (/app/tests/grabar_demo_victoria.py) en
   /app/backend/demos/demo_victoria.mp4; GET /api/victoria/demo/video (descarga en DemoCard.js, panel admin
   Administración→Victoria); POST /api/victoria/demo/enviar → correo ENVIADO a gerardo.ext@centralmutuos.cl.
- Testing: iteration_56.json backend 18/18 + demo UI verificada; limpieza QA total; PIN de Victoria sin configurar
  (lo elegirá ella); clave_temporal sigue activa hasta que cambie su contraseña.

## 2026-06 — Demo con voz de Martín + Revisión Constitucional (COMPLETADO)
1. VOZ DE MARTÍN EN LA DEMO:
   - Demo interactiva: narración sincronizada por escena vía Web Speech API (es-CL, se cancela al pausar/salir).
   - Escenas extendidas a 96s para calzar la narración (NARRACION[] en DemoVictoria.js).
   - Video: 9 audios TTS OpenAI (emergentintegrations, tts-1-hd voz onyx, generador /app/tests/gen_narracion_martin.py)
     muxeados con ffmpeg (adelay+amix) sobre regrabación Playwright → /app/backend/demos/demo_victoria.mp4
     (1:30, video H264 + audio AAC, 1.5MB). Se abre con "Hola, soy Martín..." y cierra "…listo para ConCreces."
   - ENVIADO por correo a gerardo.ext@centralmutuos.cl con asunto "Demo módulo Victoria con Martín - Central Mutuos ConCreces"
     (endpoint demo/enviar ahora acepta asunto opcional en payload).
2. REVISIÓN CONSTITUCIONAL PRE-REDESPLIEGUE (/app/tests/revision_constitucional.py — re-ejecutable):
   - 7 reglas canónicas escritas y activas en dashai_eventos (codigo REDESPLIEGUE-1..7): lectura completa de correos,
     validación ConCreces 4 contrastes, único correo 8AM, MESA automática, Victoria independiente,
     Visualizador perpetuo, Martín con autorización + stop "para".
   - Verificado: _daily_report_loop y _reporte_correos_loop DESACTIVADOS (comentados en server.py);
     ORO_CONCRECES_1..15 sembradas (norma_clave); solo_modulo victoria activo.
   - Incidente: hot-reload de uvicorn quedó colgado en shutdown → sudo supervisorctl restart backend lo resolvió
     (bcrypt cold-start: hacer warm-up login local tras restart).

## PENDIENTE INMEDIATO (sin cambios)
- Listado "ds19 01 inmoboliarias": imagen 599x2000px con 174 filas; el texto de correos es de ~4px y el extractor
  alucina. Recortes de columna en /tmp/v_0..9.png (7x) listos para lectura manual. RECOMENDACIÓN: pedir al usuario
  el CSV/Excel de origen para fidelidad 100% antes de una campaña real (correos mal leídos = rebotes).

## 2026-06 — Sesión grande: Ventas, renombre Daniela, Mutuos (Guía), voz Martín
1. MÓDULO VENTAS (iter57 20/20 + iter58): Yerile Barrera (yerile.barrera@) y Deysi Salazar (deysi.salazar@),
   solo_modulo="ventas"; round-robin automático (doc incompleta + entrega inmediata, detectada por texto o checkbox);
   /app/backend/ventas.py; panel+ficha+contactos+estados; reporte admin (Administración→Panel Ventas);
   validación formato RUT; correos de aviso por ejecutiva (PUT /api/ventas/ejecutivos/{ej}/avisos-email,
   avisos enviados a ejecutiva ALEATORIA vía _notificar_aviso_ventas). Demo con voz enviada por correo.
2. RENOMBRE: módulo bóveda ConCreces ahora es "Módulo Daniela Galindo" (daniela.galindo@ / Daniela2024,
   solo_modulo="victoria" interno); todos los textos visibles renombrados; usuario victoria.vilches viejo migrado.
3. MÓDULO VICTORIA VILCHES · MUTUOS (iter58 11/11): /app/backend/mutuos_victoria.py + MutuosWorkspace/Panel/Ficha;
   victoria.vilches@ / Victoria2024 (solo_modulo="mutuos", gerente de operaciones). Flujo 6 etapas según Guía de
   Usuario Mutuos (PDF en assets jxy15tj9): Evaluación Cliente → Registro Operación → Tasación → Datos Crédito →
   Seguimiento → Validación final/envío a riesgo. Autocompletado desde la bóveda (PUENTE de solo lectura con módulo
   Daniela), 4 validaciones irrenunciables + regla 80% deuda/garantía + formato RUT con puntos/guion, pantalla de
   autorización por etapa, trazabilidad clic→documento origen (PreviewFlotante), envío a riesgo bloqueado hasta
   todo autorizado. 6 "Regla de Oro Victoria" sembradas (etiqueta en dashai_eventos, seed idempotente).
4. VOZ MARTÍN corregida: utils/vozMartin.js (selector estricto voz española es-419/es-US primero, rate 1.0)
   aplicado a DemoVictoria, DemoVentas y CentralChat; videos regenerados con tts-1-hd onyx speed 1.0;
   demo Victoria/bóveda REENVIADA a gerardo.ext con asunto "voz corregida". demo_ventas.mp4 y demo_victoria.mp4
   en /app/backend/demos (GET /api/victoria/demo/video?modulo=).
5. Constitución: REGLA_ARQ_SEPARACION (módulos independientes, admin única visión transversal) actualizada
   con nombres correctos; REDESPLIEGUE-5 actualizado.
- Testing: iteration_57.json (backend 20/20), iteration_58.json (frontend 11/11, sin bugs).
- Nota menor pendiente: warning consola "span cannot be child of option" (no funcional).
- PENDIENTE: listado publicidad "ds19 01 inmoboliarias" sigue esperando CSV/Excel del usuario (imagen ilegible).


## Actualización 2026-08-22 (post-fork)
1. RESUELTO P0: correos duplicados — Regla de Oro #68 (escudo por huella en send_mail + cerrojo atómico MESA + claim atómico resumen 8AM + backlog limpiado). Constitución v29.
2. NUEVO: Gmail API + Pub/Sub en tiempo real (gmail_pubsub.py) — reemplaza polling IMAP de ethangerardobarr@gmail.com. Pendiente: configuración GCP + consentimiento OAuth del usuario (ver CHANGELOG).
3. RESUELTO P1: OCR/conversión JPG-PNG->PDF — 6/6 en test (flujo: convertir->preprocesar->OCR->clasificar por contenido->renombrar). Binarios tesseract/poppler con auto-reinstalación al arranque.

### Backlog vigente
- P2: Gestor de credenciales plataforma 'Crece' (solo Admin edita).
- P2: Reporte de Campaña (aperturas de correo en Módulo Publicidad).
- P2: Botón Hilo Frío (tarjetas inactivas 7+ días -> correo de seguimiento).
- P2: Listado Publicidad ds19 (BLOQUEADO: falta Excel/CSV del usuario).
- P2: Backoff exponencial IMAP (EOF Gmail) — mitigado parcialmente al migrar la cuenta principal a Gmail API push.

4. NUEVO (2026-08-22): Modo Prueba de Clasificación armado para el lunes 2026-08-25 — procesa todo pero reporta a gerardo.ext y NO notifica clientes (modo_prueba.py). Desactivar tras la prueba con POST /api/modo-prueba/desactivar.

5. NUEVO (2026-08-22): Centro de comando 'Publicidad y Captación' unificado (4 secciones) con importación Excel/CSV de listados y formulario de credenciales Twilio. Pendientes visibles: ds19 (falta archivo del usuario) y Twilio (faltan credenciales).

6. NUEVO (2026-08-22): Divisor de PDF multi-documento integrado en ambas vías de ingesta (IMAP + Gmail push). Reglas de clasificación aprendidas de 30 días de correos reales (reglas_auto + proc_rules). Gmail Push operativo en tiempo real (suscripción Pub/Sub activa, verificada con correos reales).

## 2026-08-22 (sesión fork) — Análisis 120 días casos límite
- Ejecutados scripts de extracción sobre Gmail (120d): edad/plazo, multi-empleo, renta mixta.
- Hallazgos: Mesa nunca menciona "edad" textualmente (efecto solo en tope UF/Simulador PDF); 0 casos de 2-3 empleos dependientes del mismo RUT (renta múltiple = siempre codeudor); dep+indep ocurre a nivel pareja (doc clave: informe resumen boletas SII); aprobaciones pueden anularse minutos después.
- proc_rules: 2 reglas actualizadas (rechazo, observación) + 3 nuevas (aprobación con tope, alerta edad 55+, renta mixta). Validadas 14/14 regex tests.
- APRENDIZAJE_CORREOS.md: agregada sección 7 (casos límite 120d).
- Informe 2 partes entregado en chat (técnico + evaluación honesta: 97-98% docs, 95% veredictos, 85-90% casos financieros límite; 100% imposible).
- Recomendación pendiente de aprobación: ventana de espera 30-60 min antes de notificar aprobaciones (riesgo de anulación); parsear plazo desde Simulador_*.pdf.

## 2026-08-22 — Auditoría Pre-Mesa (Reglas de Oro #71/#72) en módulo contralor
- Lógica integrada en espejo_postventa.py (módulo contralor existente, sin módulos nuevos).
- #71: auditoría automática contra Bóveda de Criterios antes de todo envío a mesa; bloqueo HTTP 412 (forzable solo con MASTER_PIN) + alerta crítica al admin (cliente, regla, acción recomendada). Corre proactiva en ingesta y con barrido en background (/api/admin/alertas/refresh).
- #72: edad calculada por OCR desde cédula (fecha_nacimiento + edad_titular persistidos, evento en historial, marca edad_ocr_fallido para no repetir OCR); valida edad min/max y plazo máximo por edad (término ≤80).
- CORRECCIÓN: mínimo UF 2.000 aplica SOLO sin subsidio; con subsidio SIN mínimo (Bóveda v6: sin_subsidio.monto_credito_min_uf=2000, con_subsidio=0; ORO-71 y espejo_criterios actualizados; registro en criterios_auditoria).
- Endpoints: GET /clientes/folders/{fid}/auditoria, GET/POST /admin/alertas (+/refresh, /{aid}/leida ahora reales).
- Verificado: bloqueo 412 (Cristian Pavez 1.800 UF sin subsidio), sin falso positivo con subsidio (Lilian 1.722 UF), 42 alertas en barrido, edades extraídas (7 carpetas).

## 2026-08-22 — Auditoría del Contralor basada SOLO en fuentes escritas (rediseño final)
- Fuentes leídas completas: Bóveda de Criterios v6, 114 reglas dashai_eventos (53 oro + 5 inviolables + 10 operativas + 6 eficiencia + 40 normativas), Algoritmo Espejo (config espejo_mesa_modelo + limites_reales_mesa, veredictos reales 280d).
- Jerarquía implementada según texto literal:
  · INV-3 (min UF 2.000 sin subsidio, "ninguna evaluación puede aprobarse bajo ese monto") = ÚNICO bloqueo, HTTP 422 con detalle exacto según OP-7, forzable solo con MASTER_PIN.
  · ORO-9 (carga conjunta >40% = "RIESGO CRÍTICO mande lo que mande la MESA") = alerta crítica, sin bloqueo; fórmula endeudamiento 2% mensual reutilizando credit_engine.endeudamiento_mensual (EF-1).
  · Resto Bóveda (montos máx, LTV, edad, plazo por edad, antigüedad 12m) = alertas informativas (ORO-35: el Contralor audita e informa).
  · Algoritmo Espejo: tope empírico por vecindad de veredictos reales; monto >115% del tope → alerta con sugerencia de codeudor.
- Cada violación cita su fuente exacta (campo `fuente` en alertas). ORO-71 reescrito en dashai_eventos + espejo_criterios con la jerarquía.
- Verificado: 422 INV-3 (Cristian Pavez), carga 705% crítica sin bloqueo (Lilian), tope espejo UF 2.065 vs 4.000 (sintético).

## 2026-08-22 — 3 features nuevas (testing agent: 100% backend + 100% frontend, iteration_60)
1. VENTANA ANTI-ANULACIÓN (mesa_verdad.py): aprobaciones de Mesa se encolan 45 min (config mesa_verdad.ventana_antianulacion_min) en db.aprobaciones_en_espera antes del reenvío a gerardo.ext; tipo "anulacion" (RX_ANULA, caso Viviana) cancela el reenvío, revierte folder a resultado_mesa=anulado, alerta crítica + aviso Martín. procesar_aprobaciones_en_espera() corre en mesa_verdad_loop; respaldo: si la cola falla, reenvío inmediato.
2. LECTOR DE SIMULADOR (espejo_postventa.py): leer_simulador_sync extrae plazo/monto/dividendo/tasa de PDFs Simulador* (2 formatos validados); persiste simulador_extraido + datos_financieros.plazo_anos + historial; alimenta auditoría (plazo por edad + nueva violación div_renta con dividendo real vs Bóveda div_renta_max). Cache simulador_scan_at.
3. PANEL DE HALLAZGOS (ContralorModule.js + GET /contralor/espejo/hallazgos): alertas de auditoría agrupadas por carpeta con regla, nivel, fuente citada; expandible; visible para contralor/admin/gerencia/administracion.
- Backfill de campo fuente en alertas antiguas aplicado.

## 2026-08-22 — Morosidad desde CMF (último criterio de la Bóveda auditado)
- leer_cmf_sync (espejo_postventa.py): parsea filas "Total \$ \$ \$ \$ \$" del Informe de Deudas CMF (Directa+Indirecta, columnas 30-59/60-89/90+ días, montos en miles ×1000); persiste cmf_morosidad + historial, cache cmf_scan_at.
- Auditoría: si morosidad_clp>0 y Bóveda morosidad_permitida=No → alerta CRÍTICA (no bloquea, ORO-35) con desglose y fuente. Validado: 8 CMFs reales (mora \$0), sintético moroso (\$300.000 detectado), carpeta real sin falso positivo.
- ORO-71 actualizado en dashai_eventos + espejo_criterios (ahora incluye morosidad en la lista auditada).

## 2026-08-22 — Paridad Preview↔Producción
- Diagnóstico: producción tiene DB y entorno propios; los ajustes hechos por DB en preview NO viajan con un redeploy. Divergencias código↔DB encontradas y corregidas:
  1. DEFAULT_CRITERIOS (criterios_data.py) traía mins antiguos (1000/500) → actualizado a 2000/0 con notas INV-3.
  2. proc_rules (10 reglas aprendidas) no tenían seed → exportadas a seeds/proc_rules_seed.json + upsert por nombre al arrancar.
  3. espejo_criterios ORO-71/72 era insert-only → ahora sincroniza texto en cada arranque.
- Nuevo seed_paridad_produccion() (espejo_postventa.py, corre al arrancar, idempotente): migra Bóveda a INV-3 (con registro en criterios_auditoria + bump de versión) y siembra proc_rules. Probado: corrige 1000/500→2000/0 (v7) y no re-ejecuta si ya está bien.
- Nuevo endpoint público GET /api/paridad (whitelisted en auth.py): stamp de código, UF (valor/día/fuente/al_día), Bóveda (versión+mins+carga+edad), hash proc_rules, conteos dashai_eventos, contralor (criterios+hash ORO-71+espejo listo), ventana anti-anulación. Comparar preview vs https://mutuariasyleasing.cl/api/paridad tras redeploy.
- UF: preview al día con sii.cl (40.861,91); producción se autocorrige al redeploy vía _uf_auto_loop (cada 30 min) salvo bloqueo de egreso (→ soporte Emergent).

## 2026-08-22 — Cuenta bancaria oficial única (MUTUARIAS Y LEASING LIMITADA)
- Cuenta oficial en todos los flujos de cobro: MUTUARIAS Y LEASING LIMITADA · RUT 77.771.552-6 · Mercado Pago · Cuenta Vista · 1030937838 · gerardo.ext@centralmutuos.cl.
- Lugares verificados/actualizados: config gastos_op.datos_pago (ya estaba), defaults hardcodeados server.py (email vacío → completado), TASACION_CUENTA (ya estaba), plantilla "ok" tipo gastos (tenía cuenta personal antigua 1014622077 → reemplazada).
- Historial (correos ya enviados en seguimiento/grid_eventos/adn) NO se reescribió (trazabilidad); carpeta del cliente "Gerardo Barrera" no tocada (su RUT es identidad, no cuenta de cobro).
- Verificado: 0 restos de la cuenta antigua en plantillas/config/colas activas.
- (adición) seed_paridad_produccion paso 3: cuenta bancaria oficial (MUTUARIAS/Mercado Pago/1030937838) se aplica al arrancar en config gastos_op + todas las plantillas tipo gastos con cuenta distinta. Probado con simulación de producción e idempotencia. PARIDAD_STAMP → v2.

## 2026-08-22 — Menú en 6 supermódulos + 3 perfiles de acceso (testing agent 95%→100% tras fix)
- App.js: SUPERMODULOS (acordeón dorado/negro: Ventas, Simulación y Análisis, Captación y Publicidad, Operación y Clientes, Control y Postventa, Administración y Sistema) + PERFIL_MODS estrictos.
- Perfiles: ventas (Yerile/Deisy: Ventas+Simulación+Captación/Publicidad+Clientes+Supercarpeta, Postventa/Contralor lectura, aterrizan en Módulo Ventas embebido) · gerencia_comercial (Daniela/Victoria/Javier: Gerencia, Módulo Daniela=VictoriaWorkspace, Módulo Victoria=MutuosWorkspace, Postventa, Contralor) · admin/maestro todo.
- Módulos no asignados: fuera del DOM + redirección automática si el estado apunta a uno bloqueado; demos #demo-* solo admin; workspaces exclusivos (solo_modulo) se omiten si hay perfil.
- Usuarios: perfil asignado a 7 cuentas; Javier Urrutia NUEVO (javier.urrutia@centralmutuos.cl / Urrutia2026!, bcrypt, clave_temporal); usuario 'javier' antiguo alineado. Todo dentro de seed_paridad_produccion paso 4 (PARIDAD_STAMP v3) → producción lo toma al redeploy.
- BUGFIX preexistente: CerebroDashAIModule 'fdd is not defined' (helper movido a nivel de módulo) — verificado con screenshot.
- test_credentials.md actualizado.

## 2026-08-22 — Aclaración de Mora con comprobante (autovalidada)
- POST /clientes/folders/{fid}/aclarar-mora: el ejecutivo sube el comprobante desde la ficha (banner rojo MORA CMF en ClientesModule); validación automática en espejo_postventa.validar_comprobante_mora (legibilidad + keywords de pago + monto ≥95% de la mora); si valida → guarda en 04_cmf (dual write), marca cmf_morosidad.aclarada, evento en historial y cierra alertas auditoria71:morosidad SIN admin; si falla → 422 con mensaje claro (mostrado en el banner).
- Auditoría #71 omite morosidad cuando aclarada=true. Banner verde "MORA ACLARADA" tras validar.
- Testeado e2e vía API: no-comprobante rechazado, monto insuficiente rechazado con comparación, válido cierra 1 alerta, re-subida bloqueada; UI verificada con screenshot.

## 2026-08-22 — Lote pre-deploy (6 puntos, testing agent iteration_62: backend 100%, frontend 38 módulos barridos)
1. Menú 6 supermódulos + 3 perfiles: ya implementado antes, re-verificado en barrido.
2. Mora — 3 acciones en ficha: enviar link/instrucciones de pago al cliente (POST /clientes/folders/{fid}/mora-link-pago, correo con cuenta oficial + referencia MORA-XXXX, respeta modo_prueba), subir comprobante (tipo=comprobante) y formulario de regularización (tipo=formulario, validador RX_REGULARIZACION + identidad cliente). Ambos autovalidan y cierran alerta sin admin. Testeado e2e.
3. Gestor Credenciales Crece: db.credenciales_crece + endpoints GET (todos autenticados, editable flag) / POST/DELETE (solo admin 403 resto) + CreceModule.js (tabla, ver/ocultar clave, CRUD admin). En menú sm_operacion, perfil ventas en LECTURA, gerencia bloqueado. Credencial real creada: Ejecutivas — Acceso Crece / centralmutuos@crece.cl.
4. Constitución: ORO-73 (Gestión de Pago de Mora) y ORO-74 (Credenciales Crece) sembradas en dashai_eventos (inamovibles) + /app/memory/REGLAS_MAESTRAS.md creado.
5. Revisión exhaustiva: 38 módulos barridos como admin (36 OK, aprendizaje/autocorreo escasos por diseño), CRUD Crece verificado, perfiles verificados en UI.
6. Seguridad: PERFIL_RUTAS_BLOQUEADAS en auth.py (ventas: sin admin/users, dashai, auditoria-forense; gerencia: además sin clientes/folders, supercarpeta, crece; criterios write solo admin). 8/8 checks curl OK. FIX: gerencia_comercial._exigir acepta perfil gerencia_comercial (Centro de Mando daba error a Javier → ahora 200; export-pdf sigue PIN-protegido).
- Deudas menores (LOW, no bloqueantes): warnings React (span dentro de option, keys duplicadas en un select), módulos aprendizaje/autocorreo con poco contenido inicial.

## 2026-08-22 — Módulo Aprendizaje IA poblado con hallazgos reales
- Nuevo endpoint `GET /api/aprendizaje/hallazgos` (backend/aprendizaje_hallazgos.py): consolida 78 hallazgos reales desde dashai_eventos, REGLAS_MAESTRAS.md, APRENDIZAJE_CORREOS.md, patrones_aprendidos y estado de mora en vivo.
- 5 categorías: Correos (27), Ventas (15), Mora (7), Documentos (18), Criterios (11). Tipos: patrón detectado, regla aprendida, corrección aplicada, comportamiento.
- Frontend: panel "Hallazgos reales del flujo comercial" con pestañas en AprendizajeModule.js (negro mate, dorado, blanco). Contenido curado vive en el código → paridad automática con producción.
- Verificado: curl con token admin + screenshots UI (pestañas Correos y Criterios).

## 2026-08-22 — Aviso de Mora al ejecutivo (ORO-73 extendido)
- Al detectar mora CMF no aclarada, `auditar_folder` (espejo_postventa.py, `_avisar_mora_ejecutivo`) envía UN correo al ejecutivo (email extraído de source_email; fallback admin) con monto, desglose de atrasos y link directo a la ficha.
- Anti-duplicado: claim atómico en `cmf_morosidad.aviso_ejecutivo_at` (un solo aviso por carpeta). Respeta modo prueba (intercepta a gerardo.ext). Evento registrado en historial.
- Deep-link nuevo: `/#cliente-{folderId}` abre directamente la ficha (App.js + ClientesModule.js).
- Verificado: correo real enviado (SMTP success), anti-duplicado en 2ª auditoría, deep-link con screenshot.

## 2026-08-23 — Leader Guard para loops periódicos (multi-réplica producción)
- Nuevo `backend/leader_guard.py`: mutex distribuido con lease atómico en Mongo (config._key=leader_lock). Renovación cada 15s, expiración 45s, failover automático si el pod líder muere.
- `_task_blindada` (server.py) ahora espera liderazgo antes de ejecutar cada loop → los ~40 loops 24/7 (ingesta_carpetas, mesa, espejo, resúmenes, etc.) corren SOLO en la instancia líder.
- El lease (`lider_loop`) corre en TODAS las réplicas vía `_task_blindada_sin_guard`. Shutdown libera el lock para traspaso inmediato.
- Verificado: claim exclusivo (réplica 2 no roba lease vigente), takeover con lease expirado, renovación propia, liberación en shutdown y recuperación automática del backend real.

## 2026-08-23 — Limpieza de consola React
- Causa raíz keys duplicadas: dos usuarias "Daniela Galindo" en `users` (códigos `daniela` y `daniela.galindo@centralmutuos.cl`) duplicaban filas en el Panel Ejecutivo del Centro de Mando (key={e.nombre}).
- Fix: dedupe por nombre en backend (gerencia_comercial.py, panel ejecutivos) + key compuesta nombre-rol-índice en GerenciaCommandCenter.js.
- Warning span-dentro-de-option: NO existe en el código actual (barrido estático de todos los <option>/<select> del frontend + recorrido de 38 módulos como admin y módulos gerencia con captura de consola = 0 ocurrencias). Probablemente era efecto del render duplicado ya corregido.
- Verificado: consola impecable (0 warnings/errores React) en ambos perfiles.

## 2026-08-23 — Publicidad: tipos de destinatario + distribución automática Excel
- Nuevo selector de tipo de destinatario en Campañas de Correo y WhatsApp: Broker Inmobiliario / Cliente Directo / Cliente Individual (backend: campo tipo_destinatario en publicidad_listados, Form en /listados/importar).
- Una sola subida de Excel con columnas de correo y WhatsApp distribuye automáticamente: correos → campaña de mail, teléfonos → campaña WhatsApp (el parser ya extraía ambos; ahora el mensaje muestra el desglose y el tipo).
- Los selects de listados muestran la etiqueta del tipo. Verificado end-to-end con Excel real (3 correos + 3 teléfonos → distribución correcta, UI muestra el listado en ambas campañas).

## 2026-08-23 — Publicidad: carga de base + candado ORO-75 + controles de envío
- Parseo por FILA de Excel (nombre/correo/WhatsApp en mismo archivo): resumen al cargar (registros, con correo, con WhatsApp, con ambos). Filtros anti-falsos (fechas, RUTs). Normalización +569XXXXXXXX. Base real "base usa tu subsidio 01" cargada: 1028 registros (1010 correos, 1009 teléfonos).
- ORO-75 (inamovible): ninguna campaña (correo/WhatsApp) se dispara sin PIN maestro validado en backend (403 sin PIN, aplica a todos los perfiles). Sembrada en dashai_eventos (seed idempotente en startup → paridad producción) y REGLAS_MAESTRAS.md.
- Controles: límite manual de registros por envío, registro publicidad_contactados (valor, canal, fecha, campaña), exclusión automática de contactos con publicidad <3 meses + aviso de cuántos fueron excluidos (al cargar y al enviar).
- Plantillas activadas: correo "Clientes Directos — carta corporativa" (opción C, asunto precargado, botón → formulario público /api/publicidad/contacto → solicitudes_llamada) y WhatsApp opción B (botón "Plantilla Clientes Directos", links → /api/publicidad/antecedentes que crea prospecto y abre portal calificar, y /api/publicidad/contacto).
- Todo verificado por curl end-to-end.

## 2026-08-23 — Base de Inmobiliarias en Publicidad
- Nuevo tipo de destinatario "Inmobiliaria" (backend TIPOS_DESTINATARIO + selectores UI correo/WA) — bases separadas de clientes directos por tipo_destinatario.
- Parser Excel por fila ahora captura columnas "Inmobiliaria/Empresa" y "Nombre de Contacto" (guardadas por contacto como empresa/nombre). Resumen al cargar: registros / con correo / con WhatsApp / con ambos.
- ORO-75 (PIN maestro) y regla anti-fatiga 3 meses aplican automáticamente (mismos endpoints). Verificado: import con empresa+contacto correctos, 403 sin PIN.

## 2026-08-23 — Base "inmobiliarias ds19" cargada (pendiente histórico resuelto)
- Parser mejorado: detecta la fila de encabezados en las primeras 3 filas y soporta títulos en inglés (Name/Phone/Email/Contact).
- Base real importada como tipo Inmobiliaria: 63 registros con contacto (de 174 proyectos usatusubsidio.cl) → 51 con correo · 44 con WhatsApp · 32 con ambos → 50 correos y 44 teléfonos distribuidos a sus campañas.
- NOTA: en producción habrá que recargar el mismo archivo (la base vive en la BD de preview).

## 2026-08-23 — Leader election por BD + Búnker no destructivo
- leader_guard.py reescrito: claim atómico con find_one_and_update sobre db.config (_key=leader_lock), identidad de pod vía HOSTNAME, heartbeat 15s / TTL 45s. Todos los loops periódicos (server.py startup, vía _task_blindada) corren solo en el pod líder.
- bunker.sync_diff: YA NO borra entradas de GridFS según el disco local (GridFS = fuente de verdad). Nuevo bunker.eliminar()/eliminar_bg() para borrado explícito (GridFS + disco), conectado en los 11 puntos de eliminación intencional (server.py: borrar carpeta/archivo/set, reclasificar, reset drive; folders_service.py: moves de codeudor y split).
- Verificado: claim exclusivo/expiración/liberación con HOSTNAME, sync no destructivo, restauración desde BD, borrado explícito end-to-end.

## 2026-08-23 — .dockerignore (PASO 3)
- Creado /app/.dockerignore: excluye backend/storage/ (1.8 GB de archivos de clientes que viven en GridFS), node_modules, build, __pycache__, logs y test_reports de la imagen de despliegue.

## 2026-08-23 — Módulo Ventas: guard de ejecutivo vacío + selector admin
- VentasPanel.js: si ejecutivo viene vacío NO llama a /api/ventas/panel/ y muestra "Seleccione un ejecutivo de Ventas" (antes quedaba en Cargando infinito).
- VentasWorkspace.js: admin sin ventas_ejecutivo ve barra selectora (Yerile Barrera / Deisy Salazar), persistida en sessionStorage. Verificado con screenshots.

## 2026-08-23 — Panel Estado de Bases de Datos (Publicidad)
- Nuevo endpoint GET /api/publicidad/estado-bases: por base → registros, correos disp./cargados, WhatsApp disp./cargados, bloqueados 3 meses.
- Panel visible ANTES de las campañas con tabla por base + botón "Usar esta base" (selecciona el listado en correo y WA) + campo "Cantidad de destinatarios para el envío actual" que sincroniza el límite de ambas campañas. Verificado con screenshot (bases reales: ds19 94 reg · usa tu subsidio 2019 reg).

## 2026-08-23 — Panel Daniela/Victoria restringido + Gerardo Barrera ejecutivo
- /api/victoria/panel: usuarios no-admin (Daniela/Victoria, rol administracion) solo ven clientes origen="manual" (subidos por el Admin) Y con doc de escritura (etapa escrituración). Cero correlación automática. Admin ve todo. Verificado con caso negativo (0 de 5 automáticos) y positivo (1 manual con escritura).
- EJECUTIVOS_VENTAS += gerardo ("Gerardo Barrera"). Usuario seed idempotente `gerardo.barrera` (email vacío, clave temporal Gerardo2026). Selector admin de VentasWorkspace incluye a Gerardo.
- asignar_a_ventas_si_corresponde reescrito: ficha COMPLETA → Gerardo automático (reasignable por admin); ficha INCOMPLETA → random.choice entre Yerile y Deisy (reemplaza el balance/round-robin).

## 2026-06 (fork) — Verificación Panel Estado de Bases
- Verificado E2E en preview: endpoint /api/publicidad/estado-bases responde (2 bases: inmobiliarias ds19 y base usa tu subsidio 01), panel visible en Publicidad y Captación con campo de cantidad manual y botón "Usar esta base". ORO-75 (Master PIN) confirmado en código antes de cualquier envío. Sin cambios de código necesarios.

## 2026-06 (fork) — Rediseño de los 3 prototipos de landing (nuevas especificaciones)
- Reconstruidos landing-opcion-a/b/c.html en /app/frontend/public/ según nuevo brief:
  - A "Banco Privado": serif Cormorant/Garamond, bloques dorados estructurados, filetes ◆, formal institucional.
  - B "Emocional Cercano": sans Outfit, hero con foto de familia, calculadora interactiva con 3 sliders (monto/plazo/pie) y recálculo en vivo.
  - C "Fintech Moderno": Space Grotesk + IBM Plex Mono, grid geométrico dorado, cifras destacadas (30s/UF12.000/90%/40años), simulador con barra de progreso animada, galería grid compacto.
- Los 3 incluyen: simulador 30s, galería Ecomac/Besalco/Boetch, panel Mi Crédito, botón pago AMH (portal.amhpago.cl), noticias SEO, switcher A/B/C flotante.
- Seed PROTOTIPOS_WEB actualizado en publicidad.py (nombres/descripciones nuevas). Verificado E2E: 3 páginas HTTP 200, simuladores calculan correctamente (A: UF 16.67, B: recálculo live, C: barra animada + resultado).

## 2026-06 (fork) — Video comercial de los 3 prototipos (2:04 min)
- Generado video MP4 (1280x720, 8MB, 124s) con locución en español (OpenAI TTS tts-1-hd, voz onyx, Emergent LLM Key): intro con placa dorada → recorrido Prototipo A → B (calculadora en acción) → C (barra animada) → cierre "Tu Casa, Tu Decisión".
- Pipeline: guion 5 segmentos → TTS mp3 → grabación Playwright (scroll suave + interacción con simuladores) → ffmpeg (x264+aac, concat).
- Descarga pública directa: {REACT_APP_BACKEND_URL}/demo-proyectos-web.mp4 (en /app/frontend/public/).
- También integrado al endpoint autenticado de demos: GET /api/victoria/demo/video?modulo=web (archivo /app/backend/demos/demo_web.mp4; mapeo "web" agregado en victoria_independiente.py).
- Verificado: HTTP 200 (8.168.126 bytes), frames revisados en 40s/70s/100s/118s confirman los 5 segmentos.

## 2026-06 (fork) — Video comercial v2 (2:07) + links de preview
- Regrabado video con guion ampliado (8 fortalezas: simulador 30s→leads, galería Ecomac/Besalco/Boetch, panel Mi Crédito, pago AMH, noticias SEO, diseño negro/dorado/blanco, velocidad móvil, 3 identidades visuales).
- Placa final de 25s con los 3 links de preview etiquetados (Prototipo A/B/C) en tarjetas doradas.
- Reemplazó /app/frontend/public/demo-proyectos-web.mp4 y /app/backend/demos/demo_web.mp4 (7.7MB, 127s). Verificado HTTP 200 + frame de placa final.
- Links entregados al usuario: /landing-opcion-{a,b,c}.html sobre el preview URL.

## 2026-06 (fork) — Correo Propuesta Sitio Web enviado
- Enviado correo HTML (negro #0a0a0a / dorado #d4af37 / blanco, estilo campañas) a gerardo.ext@centralmutuos.cl. Asunto: "Propuesta Sitio Web Institucional — Central Mutuos". Dirigido a Rodrigo y René.
- Incluye: 3 tarjetas con links de prototipos A/B/C, botón dorado de descarga del video, y el video adjunto (Presentacion_Sitio_Web_Central_Mutuos.mp4, 7.7MB).
- Resultado SMTP 250 OK · remitente ethangerardobarr@gmail.com (capa anti auto-envío activó cuenta principal al detectar destino = cuenta secundaria) · tamaño total 10.2MB.

## 2026-06 (fork) — Historial de Contactados + Botón Hilo Frío
### Historial de Contactados (Módulo Publicidad)
- GET /api/publicidad/historial-contactados?tipo= → por contactado: nombre, correo, teléfono, canal, fecha contactado, fecha desbloqueo (+90 días), estado bloqueado/desbloqueado, base y listado. Enriquecimiento cruzando publicidad_contactados con publicidad_listados (hermanos por nombre para correo↔teléfono).
- GET /api/publicidad/historial-contactados/excel?tipo= → export .xlsx (openpyxl, encabezado dorado).
- Frontend: sección "Historial de Contactados" en PublicidadModule.js con filtro por base (Inmobiliaria/Brokers/Clientes Directos/Individual) y botón Exportar a Excel (blob). data-testids: historial-contactados, historial-filtro-base, historial-exportar-excel, historial-fila-{i}.
### Botón Hilo Frío (Módulo Ventas)
- _resumen_cliente ahora expone hilo_frio=true si semáforo dias_sin_movimiento>=7 y caso no cerrado.
- POST /api/ventas/clientes/{cid}/hilo-frio: solo admin/maestro o perfil "ventas"; exige MASTER_PIN (ORO-75 vía _exigir_pin_maestro); valida inactividad>=7 días y correo en ficha; envía correo institucional (usted, negro/dorado) firmado por el ejecutivo asignado; registra en ventas.contactos + timeline (resetea semáforo).
- Frontend VentasPanel.js: botón "🧊 Hilo Frío · N días inactivo" (data-testid ventas-hilo-frio-{id}) con confirm + prompt de PIN maestro.
- TESTEADO E2E: PIN inválido→403 ORO-75, PIN válido→correo enviado (SMTP OK), re-envío inmediato→400 (<7 días), excel con Content-Disposition correcto, UI verificada con screenshot. Datos de prueba eliminados tras el test.

## 2026-06 (fork) — Rechazo de Mesa: Plantilla C APROBADA y flujo activo
- Admin aprobó la Opción C (minimalista elegante, todo blanco, nombre centrado) vía POST /api/rechazo-notif/aprobar. Guardada en db.config (_key: rechazo_plantilla, aprobada: "c").
- Al aprobar se enviaron automáticamente los 3 casos pendientes reales (Anita Álvarez, Catalina Aguilera, Jorge Alcayaga) → gerardo.ext@centralmutuos.cl, SMTP 250 OK cada uno.
- Prueba real Anita Álvarez (DS19, parámetro objetivo → cambiar titular por codeudor) enviada con éxito; el segundo intento idéntico fue bloqueado correctamente por Regla de Oro #68 (anti-duplicados), confirmando el escudo.
- Desde ahora, todo rechazo detectado por mesa_verdad se notifica automáticamente al ejecutivo con la plantilla C, sin intervención manual.

## 2026-06 (fork) — Fix visibilidad correos de Rechazo
- Problema reportado: los correos de rechazo "no aparecían". Causa raíz (verificada por IMAP): (1) remitente cambiado a cta respaldo gmail por capa anti auto-envío → no estaban en Enviados de gerardo.ext; (2) cabecera In-Reply-To los anidaba dentro de hilos antiguos; (3) nombre visible del remitente era "Respuestas Mesa Clientes" (violaba regla de enmascarar Mesa).
- Fix: email_service.send_mail acepta from_name= y hilo_nuevo= (opcionales, sin afectar otros flujos). rechazo_notificacion._enviar usa from_name="Central Mutuos" + hilo_nuevo=True; escudo anti-duplicados intacto (forzar solo en /probar).
- Verificado E2E por IMAP: nuevo correo de prueba Anita Álvarez llegó a INBOX como "Central Mutuos", hilo NUEVO (independiente), 24-ago 09:28 PDT.

## 2026-06 (fork) — REGLA ABSOLUTA: Cuenta Única de Envío (MAIL2)
- Mandato del Administrador: TODOS los correos salientes (cualquier módulo, presente o futuro) salen SOLO desde gerardo.ext@centralmutuos.cl (credenciales MAIL2_*). PROHIBIDO ethangerardobarr@gmail.com como remitente.
- Implementación central en email_service.send_mail: parámetro `desde` ignorado (forzado a secundaria); eliminada la 2ª capa anti auto-envío que cambiaba el remitente a gmail; sin MAIL2 configurada el envío se BLOQUEA con error explícito (jamás usa otra cuenta de respaldo).
- Gasto Operacional: envía con cuenta_fija=True (anclado a MAIL2).
- Documentada como NORMATIVA CONSTITUCIONAL "CUENTA UNICA DE ENVIO" en NORMATIVAS_FIJAS (server.py) — se auto-siembra en preview y PRODUCCIÓN al arranque (verificado en dashai_eventos).
- Verificado con SMTP simulado (4 casos): desde="principal"→corporativa, destino=cuenta propia→se mantiene corporativa, gasto operacional→corporativa, sin MAIL2→bloqueo. La cuenta gmail queda solo para RECEPCIÓN/monitoreo (GMAIL_WATCH_ACCOUNT), nunca como remitente.

## 2026-06 (fork) — Vista Admin: Correos Retenidos por Modo Prueba
- Backend (modo_prueba.py): GET /api/modo-prueba/retenidos · POST /retenidos/{seg_id}/aprobar (envía ya, forzar=True vía _autocorreo_cliente_aprobado/_rechazado) · POST /retenidos/{seg_id}/descartar (marca estado_cola=descartado, no envía) · POST /retenidos/aprobar-todos · POST /retenidos/descartar-todos. Solo admin. Error de envío → 409 con detalle (502 lo interceptaba el proxy).
- Frontend: components/RetenidosModoPrueba.js integrado en DashboardModule (panel principal). Muestra destinatario, asunto, fecha/hora, motivo, estado APROBADO/RECHAZO; botones por fila + globales con confirm. data-testids: retenidos-modo-prueba, retenido-fila-{i}, retenido-aprobar-{i}, retenido-descartar-{i}, retenidos-aprobar-todos, retenidos-descartar-todos.
- Verificado: API con token admin (9 retenidos), aprobar sin correo en ficha falla limpio (sin_correo, nada enviado), UI renderizada en dashboard (screenshot OK).
- Nota: varios retenidos tienen cliente mal extraído ("Respuestas Mesa Clientes") y sin email — problema upstream de extracción de cliente en mesa_verdad, pendiente si el usuario lo pide.

## 2026-06 (fork) — Detección de PDFs protegidos con clave + otras entregas de la sesión
- scan_archivos (folders_service) marca cada archivo con protegido:bool y etiqueta "Protegido — requiere clave" (pypdf is_encrypted + fallback /Encrypt, con caché por mtime).
- Alerta automática al Admin (db.alertas tipo pdf_protegido, dedupe en pdfs_protegidos_notificados) al abrir carpeta y al ingresar docs nuevos por correo.
- Frontend ClientesModule: insignia ámbar "🔒 Protegido — requiere clave" en la vista de documentos (data-testid file-protegido-{i}).
- Verificado E2E con PDF cifrado real: detección, endpoint y alerta OK; datos de prueba eliminados.
- FIX CRÍTICO previo: procesador de cola paralizado 27h (avalancha de ciclos concurrentes) → _PROC_AUTO_LOCK + wait_for(600s) en ingesta; backlog de 18 correos procesado, carpetas creadas (incl. Jorge Salazar Guajardo).
- Otras entregas: soporte ZIP en ingesta (expandir_zip en email_service aplicado a fetch_pdf_attachments y fetch_attachments_by_message_ids); vista Admin "Carpetas con documentos faltantes" (GET /api/carpetas/faltantes + CarpetasFaltantes.js en Dashboard); botón codeudor en rechazo cliente (endpoint público /api/rechazo-codeudor/{token}); normativas constitucionales: CUENTA UNICA DE ENVIO, APROBACION SIN GASTOS, RECHAZO TEXTO EXACTO; informe PDF contratos arriendo enviado por correo.

## 2026-06 (fork) — Usuario Solo Lectura "Clave"
- Usuario: codigo "clave" (login "Clave", tolerante a mayúsculas) / clave "1234" (bcrypt) / rol "lectura". Sembrado idempotente al arranque (server.py) → también se creará en PRODUCCIÓN al redesplegar.
- Backend (auth.py): rol "lectura" en ROL_BLOQUEO_ESCRITURA con lista blanca vacía → TODO POST/PUT/PATCH/DELETE bloqueado con 403.
- Frontend (App.js): ACCESOS_ROL.lectura = solo dashboard en modo lectura; etiqueta "SOLO LECTURA"; banner MODO LECTURA.
- Verificado E2E: login OK, GET 200, POST/DELETE 403, vista admin renderizada con banner (screenshot).

## 2026-08-28 (fork) — Corrección UF y Carta Oferta sin Gastos Operacionales
- UF corregida en docs Castillo: valor oficial SII $40.868,50 (27/08/2026, hora Chile) mostrado con decimales (antes se redondeaba a $40.869). Montos recalculados: precio $78.671.863, pie $1.626.158, saldo $77.045.705, multa $408.685; tabla cuadra exacta.
- Carta Oferta: eliminada por completo la sección "V. GASTOS OPERACIONALES" (pedido explícito del usuario).
- Links descarga segura entregados al usuario (tokens en db.descargas_seguras, /api/descarga-segura/{token}).
- Lint bloqueante corregido: import DEFAULT_UF en espejo_postventa; base indefinida y bloque constitucion duplicado + import FileResponse duplicado en server.py; import marcarRegreso en AprobacionClienteModule y SetCreditoModule; upload de proyecciones broker ahora persiste vía bunker.guardar_bytes (Object Store + espejo local, "brokers" agregado a SUBDIRS).

## 2026-08-28 (fork) — Políticas de Crédito MHE embellecidas
- Excel del usuario "Resumen MHE Sin/Con Subsidio" convertido a PDF profesional (generar_politicas_credito.py → Politicas_Credito_MHE.pdf): 5 secciones (Propiedad, Financiamiento, Perfil, Comportamiento financiero, Codeudores), cuadro comparativo con/sin subsidio, tipografía corregida.
- Revisión de privacidad: SIN datos personales (no RUT/nombres/contactos); se eliminó la mención "POLITICAS CONCRECES" (nombre de institución) del documento final.
- Link descarga segura entregado (token en db.descargas_seguras).

## 2026-08-28 (fork) — Políticas Concreces MHE agregadas a la Bóveda
- Nuevo bloque `concreces_mhe` (con_subsidio + sin_subsidio) en db.config criterios (v8) y en DEFAULT_CRITERIOS (criterios_data.py, para deploys frescos). Todos los criterios de la planilla del usuario: valores UF propiedad/crédito, LTV 80%, pie 20%, plazos, div/renta 40%/35%, carga 55%/50%, rentas mínimas, edades, antigüedad, excluyentes de morosidad, codeudores y complemento de renta.
- Registro en criterios_auditoria. Verificado vía GET /api/admin/criterios con token admin.
- Nota: el auditor #71 sigue usando btg_pactual como bloque activo; concreces_mhe queda disponible en la Bóveda (pendiente si el usuario quiere que el Contralor valide contra MHE).

## 2026-08-29 (fork) — Módulo "Solicitudes La Cruz" (evaluaciones de crédito por correo)
- Backend nuevo: solicitudes_lacruz.py — pipeline: IMAP fetch de daniela.rodriguez@lacruzinmobiliaria.cl → agrupación por RUT del asunto → extracción IA (Claude sonnet-4-6, JSON estructurado: datos cliente, docs, fechas emisión, líquidos mensuales, deudas CMF) → análisis determinista (vigencia CMF/AFP ≤15 días; liquidaciones exigidas feb–jul 2026; ratios MHE con subsidio: div/renta ≤40%, carga ≤55%, LTV ≤80%, renta mín UF15/25; máx crédito posible vía capacidad_desde_dividendo, cap LTV 80% y UF 3.200; semáforo ALTA/MEDIA/BAJA + prioridad por score) → carpetas creadas (db.folders origen lacruz_auto, archivos clasificados, codeudor con prefijo CODEUDOR_, cotizaciones a raíz) → persiste db.lacruz_solicitudes.
- Endpoints: GET /api/lacruz/solicitudes · POST /api/lacruz/procesar (solo admin).
- Frontend: pages/SolicitudesLaCruz.js registrado en App.js (supermódulo Ventas, key 'lacruz'). Tabla con prioridad, cliente, RUT, teléfono, proyecto, crédito solicitado UF, máx crédito posible UF, semáforo, chips docs, fila expandible con detalle. data-testids lacruz-*.
- Resultado real (verificado E2E con datos reales + screenshot): #1 Christian Salazar (MEDIA, faltan liq feb/mar, AFP+CMF vencidos 18d, cédula ilegible) · #2 Gabriela Berríos + codeudor César Zamora (MEDIA, faltan cédula/AFP titular, liq feb codeudor, cédula codeudor ilegible) · #3 Jonathan Quijada (BAJA, div/renta 42%, faltan cédula/AFP/CMF) · #4 Héctor Donoso + Priscila Herrera (BAJA, renta insuficiente, AFP ambos vencidos, faltan cédulas y liq codeudor).
- Nota: cuenta secundaria IMAP con OVERQUOTA temporal (se usa la principal).

## 2026-08-29 (fork) — Análisis Rodrigo Jara + limpieza de disco
- Rodrigo Jara Bustamante (15.435.814-5, Maestra/Vistamar Coquimbo UF 3.616): analizados 33 contratos de arriendo (OCR, $10.009.000/mes), planilla cliente (41 props, $16,1M), F22 (contraste: tributa solo $26M/año), dossier laboral (PwC $2.895.490 prom feb–jul), CMF $564,7M vigente sin morosidad. Conclusión: no califica como dependiente; viable solo como inversionista acreditando arriendos. PDF Informe_Arriendos_Rodrigo_Jara.pdf generado (scripts_lacruz/).
- Correo con análisis completo en el cuerpo + PDF de arriendos adjunto ENVIADO a gerardo.ext@centralmutuos.cl (vía Preview Obligatorio, confirmado por admin).
- DISCO: liberado de 97%→85% (1,6G libres). Eliminado: node_modules/.cache (234M), Carpeta_*.pdf regenerables (989M), __pycache__, adjuntos temporales. ⚠️ git gc FALLÓ por espacio (tmp_pack llenó el disco al 100%, se limpió; Mongo se recuperó). NO intentar git gc con <2,5G libres. Pendiente OK usuario: /app/vidwork (61M) y /app/boveda_victoria (90M).
- Minero gerardo.ext@centralmutuos.cl sigue esperando OVERQUOTA de Google (scripts_lacruz/mineria_gerardo.py activo, reintenta cada 30 min).

## 2026-08-29 (fork) — Limpieza Profunda round 2 (post-cuelgue)
- Durante un cuelgue de hot-reload, un proceso con código viejo re-descargó 112 carpetas + 80 Carpeta_*.pdf (~700MB). Purga repetida en orden seguro (local→manifiesto→gridfs→re-archivar): 114 carpetas re-archivadas, 398MB de PDFs purgados.
- Estado final: DISCO 76% (2,5 GB libres, antes 97%/343MB), 160 prefijos archivados en config.bunker_archivados, 85 carpetas locales activas, cloud-sync estable (1 restauración legítima), app 200 OK.
- Lección: NUNCA editar bunker.py con procesos de restauración en curso; reiniciar backend limpio antes de purgar.

## 2026-08-29 (fork) — Informe Histórico Ecomac COMPLETO (casilla gerardo.ext liberada)
- Google liberó la casilla gerardo.ext: mineria_gerardo.py terminó con ÉXITO → 11.031 encabezados históricos (Sep 2024 → Ago 2026) en scripts_lacruz/gerardo_headers.json.
- Análisis (scripts_lacruz/analisis_ecomac.py): 1.109 solicitudes de evaluación (676 RUTs únicos), 121 clientes en escrituración, 20 llegaron a firma/títulos, conversión hilo→escritura 17% (193 hilos, 31 firmadas por match). Mediana 1ª respuesta 11,3 h; tasa de respuesta subió de 35% (pre Nov-2025) a 75% (con Central Mutuos).
- Ejecutivas: Gabriela Muñoz 70 sol/30 esc/5 firmas · Rita Arancibia 46/27/6 · Yerko Villanueva 35/14/1 · Amalia Galleguillos 26/12/1 · Scarlett Aguilar 6/2/0.
- PDF Informe_Historico_Ecomac.pdf (mes a mes desde inicio real, cuadro 3 meses FUTURA vs escrituradas, tiempos de respuesta, ejecutivas) ENCOLADO en Preview Obligatorio → gerardo.ext (preview_id 05f69bf0). Verificado visible en Dashboard.
- Pendiente refinamiento: cuerpos_gerardo.py reintenta cada 30 min descargar primeros 1.5KB de cuerpos (Google volvió a OVERQUOTA tras la minería); al llegar gerardo_bodies.json se pueden precisar aprobaciones exactas por cuerpo.

## 2026-08-29 (fork) — Informe Ecomac DETALLADO cliente por cliente
- Nuevo scripts_lacruz/pdf_informe_ecomac_detallado.py: PDF de 47 páginas con los 1.109 clientes enviados desde Sep 2024 listados uno por uno (fecha, nombre, RUT, ejecutiva, horas 1ª respuesta, estado en color, fecha escritura). 407 en verde (aprobados/escriturando). Últimos 3 meses: 161 enviados, 75 en verde. Sección IV: los 121 escriturados con etapas y fechas. Enriquecido con veredictos de Mesa del sistema (mesa_verdad_log: 30 aprobaciones, 22 rechazos + aprobacion_log).
- Preview anterior (versión solo estadística, 05f69bf0) descartado; versión detallada encolada en Preview Obligatorio (preview_id 2795d415).

## 2026-08-29 (fork) — Informe Ecomac FINAL exclusivo Ecomac (aprobado por usuario)
- pdf_informe_ecomac_final.py: filtro EXCLUSIVO Ecomac en escrituraciones (remitente/destino @ecomac.cl, proyecto Ecomac en asunto, o cliente proveniente de solicitud Ecomac por RUT/nombre) + blacklist de nombres genéricos ("casa usada"). Escrituraciones 121→92 (se excluyeron 29 de Maestra/usadas/otras). KPIs finales: 1.109 enviados | 319 verdes | 92 escrituraciones | 12 firmas. 3 meses: 161 enviados / 16 con escritura / 2 firma-títulos (Christel Casanova, Rodrigo Valencia). INMEDIATA: 189/109/13/2.
- Cuadros aprobados por el usuario: tabla INMEDIATA, cuadro venta en verde 3 meses, muestra random 15 tiempos de respuesta (semilla 29), promedios por ejecutiva.
- PDF 51 páginas con anexos A (3 meses cliente x cliente) y B (histórico completo). Encolado preview e13b2054; versiones anteriores descartadas.

## 2026-08-29 (fork) — Informe "Alianza Central Mutuos–Ecomac" (persuasivo, para Ecomac)
- pdf_alianza_ecomac.py: PDF 10 páginas dirigido a Ecomac para retener el acuerdo comercial. Narrativa aprobada por usuario: rapidez (mediana 11,3h, cuadro random 15 casos 100%<25h, promedios por ejecutiva), apuesta a venta en verde (161 enviados/16 escrituras 3m), 92 escrituraciones acompañadas, hitos/ferias/reuniones, 11 testimonios de clientes con citas + popurrí de 11 pantallazos WhatsApp (testimonios/w01-11.jpg; w04 Karina RECORTADA para eliminar comentario privado sensible sobre "10 millones a la prima"), cierre "mantengamos esta alianza". Nota: cifras solo gestión propia, sin De Manet.
- Encolado preview ecdf5a95. El informe interno detallado (Informe_Historico_Ecomac_FINAL.pdf, 51 págs) queda guardado en disco por si se quiere reenviar.
- Disco al 83% tras imágenes/PDFs — vigilar.

## 2026-08-29 (fork) — Correo formal Alianza Ecomac + montos escriturados + links descarga
- Google liberó la casilla: cuerpos_gerardo.py descargó 4.376 cuerpos (gerardo_bodies.json).
- montos_escriturados.py: crédito por escriturado desde cuerpos (61/92 con monto, suma UF 125.263; proyección total ≈UF 180.000 ≈ $7.500MM aprobada por usuario). Duplicados y 550UF sospechosos informados en pantalla.
- correo_alianza_ecomac.py: correo FORMAL a las dos encargadas Ecomac con cuadro resumen ejecutivo al inicio (UF 180.000+/$7.500MM, 11,3h, 1.109 evaluados, 319 en verde, 92 escrituraciones), rapidez primero, adjuntos Felicitaciones_Clientes_Ecomac.pdf y Clientes_Enviados_Ecomac.pdf. Encolado preview 286c1447.
- pdf_alianza_ecomac.py ahora solo genera el PDF (KPI banner con escriturado total incluido, sección valor escrituración UF 180.000+).
- 4 links de descarga segura generados (Alianza, Detallado 51p, Felicitaciones, Clientes Enviados).
