# 🧠 BASE DE CONOCIMIENTO PERMANENTE — Central Mutuos
> Generada por el Análisis de Aprendizaje Total (día 1 → 26-08-2026).
> Alimenta al Clasificador IA (Claude) y al Monitor de Autorreparación vía `db.config._key=base_conocimiento`.
> Regenerar con: `python3 /app/backend/analisis_total.py`

## 1. Flujo completo real (como si la IA lo hubiera ejecutado)
1. **Llegada**: correo entra por IMAP (2 casillas: gmail principal + gerardo.ext corporativa).
2. **Clasificación de entrada**: hoy con Claude (6 categorías); históricamente con palabras clave.
3. **Cola**: entra a `proc_queue`; adjuntos se convierten a PDF, se dividen si son multi-documento y se guardan en el búnker (Object Store).
4. **Extracción**: OCR + IA extraen cliente, RUT, tipo de documento, montos, ejecutivo.
5. **Carpeta**: si cumple la Regla 67 (≥3 categorías de documentos) → carpeta de cliente con subcarpetas protocolo. Si no → faltantes automáticos / buzón de rescate.
6. **Set a Mesa**: PDF combinado ordenado (cédula→liquidaciones→AFP→CMF→codeudor→otros) → aprobaciones@centralmutuos.cl.
7. **Veredicto**: mesa_verdad monitorea la casilla oficial → aprobación (reenvío constitucional con carta+simulación) o rechazo (Plantilla C, texto exacto).
8. **Notificación**: hoy TODO correo saliente pasa por Preview Obligatorio (confirmación del Admin) y sale SOLO desde gerardo.ext (MAIL2).

## 2. Volumen real de operaciones (2026-07-27 → 2026-08-26)
| Métrica | Valor |
|---|---|
| Correos de gestión procesados (proc_queue) | 282 (257 clasificados, 258 con carpeta) |
| Carpetas de clientes | 135 (94 por procesamiento automático, 26 por aprobación de mesa, 9 forzadas, 5 manuales) |
| Envíos/eventos de seguimiento a Mesa | 132 (81 aprobación, 47 observación, 4 rechazo) |
| Veredictos verificados de Mesa (mesa_verdad_log) | 61 (23 aprobaciones, 19 rechazos, 11 backlog, 8 otros) |
| Correos SALIENTES SMTP | 555 (100% exitosos; 463 vía gmail histórico, 92 vía gerardo.ext) |
| Autocorreo (reenvío solicitudes) | 293 (233 sent, 60 failed históricos) |
| Duplicados bloqueados (Regla Oro #68) | 9 · Omitidos por normativa: 3 |
| Rechazos notificados | 5 · Alertas del sistema: 5.729 |

## 3. Patrones de clasificación documental (1.990 docs analizados)
- liquidacion 422 · certificado_smf (CMF) 84 · cedula 78 · cotizacion_afp 71 · certificado_afp 57 · simulacion 49 · carta_aprobacion 42 · boleta_honorarios 35 · impuesto_renta 21.
- **1.130 documentos (57%) cayeron en "otro"**: firmas de imagen, contratos, certificados varios. Su presencia NO invalida una solicitud (van a 99_otros).
- Confianza IA promedio: **0.818**. Adjuntos promedio por solicitud: **7,1**.
- Clientes: 259 dependientes vs 13 independientes (boletas/renta). La Mesa aprueba a independientes con TOPE de monto.
- Remitentes top: ecomac.cl (101), centralmutuos.cl reenvíos (52), gmail clientes (37), maestra.cl (33), boetsch.cl (31).

## 4. Errores recurrentes y causas
1. **"No se arma carpeta — el texto no menciona evaluación"** (11 descartes): filtro de palabras clave demasiado literal → CAUSA RAÍZ del cambio al Clasificador Contextual IA.
2. **Autocorreo failed (60 históricos)**: adjuntos perdidos tras redespliegues (antes del búnker) + duplicados. Corregido con Object Store + refetch del correo de origen.
3. **Detección tardía de veredictos** (mediana 29,7 h): cuelgues IMAP del monitor (bloqueo de 27 h resuelto con candados + socket timeout 90s).
4. **Envíos "fallidos" que eran preview**: al activar Preview Obligatorio, los módulos de rechazo/aprobación marcaban fallo. CORREGIDO 26-08: `preview` = entrega correcta al Admin.
5. **OVERQUOTA IMAP en gerardo.ext**: límite de comandos del proveedor bajo barridos intensos — la autorreparación lo detecta y reintenta.

## 5. Tiempos promedio reales por etapa
| Etapa | Mediana | Promedio | n |
|---|---|---|---|
| Correo → Carpeta creada | **2,2 h** | 9,7 h | 100 |
| Carpeta → Veredicto de Mesa | **5,5 días** (133 h) | 7,1 días | 21 |
| Veredicto emitido → Detectado por el sistema | 29,7 h | 23,5 h | 50 |

## 6. Real vs. ideal (aprendizajes)
- **Ideal**: clasificación por contexto → **Real**: keywords descartaban solicitudes válidas (11 casos) y dejaban pasar administrativos. → Clasificador Claude activo desde 26-08.
- **Ideal**: veredicto detectado en minutos → **Real**: mediana 29,7 h por cuelgues. → Candados + autorreparación Nivel 1 vigilan el loop.
- **Ideal**: cuenta única corporativa → **Real**: 83% del histórico salió por gmail. → Regla constitucional MAIL2 activa (histórico no se altera).
- **Ideal**: ningún correo sin control → **Real**: 555 salieron directo. → Preview Obligatorio intercepta el 100% desde su promulgación.
- **Ideal**: adjuntos siempre disponibles → **Real**: 60 fallos por almacenamiento efímero. → Object Store + refetch del origen.
