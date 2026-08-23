# 🧠 INFORME EXHAUSTIVO — Clasificación Documental y Aprendizaje (2026-06)

## 1. Reglas obligatorias implementadas (fuente: clasificador_documental.py)
- **Dependiente**: cédula + liquidaciones de sueldo + AFP + CMF. JAMÁS boletas ni impuesto a la renta.
- **Independiente**: cédula + boletas de honorarios + última declaración de impuesto a la renta + CMF. JAMÁS liquidaciones ni AFP.
- **Mixto**: ambos conjuntos según cada fuente de ingreso.
- **Carabineros / Ejército / Gendarmería (incl. Dipreca/Capredena)**: exentos de AFP — detección automática por OCR de las liquidaciones.
- **Codeudor**: requerimiento documental independiente según su tipo (detectado por sus propios documentos en 05_codeudor).
- **Licencia médica**: se registra en credit_request.licencia_medica y se considera en el análisis SIN bloquear el proceso.

## 2. Errores detectados (diagnóstico de lo que estaba fallando)
1. La clasificación era BINARIA (dependiente/independiente): no existía el tipo MIXTO → clientes con ambas fuentes quedaban con requerimientos incompletos o pedidos prohibidos.
2. No existía exención AFP institucional: a uniformados se les exigía certificado AFP que no existe.
3. El codeudor no generaba requerimiento documental propio (solo se archivaban sus archivos).
4. La licencia médica solo existía como bloqueo de mesa (Regla #70), no como registro de análisis.
5. El tipo de cliente se fijaba por defecto en 'dependiente' al crear la carpeta, sin releer la evidencia documental adjunta de los correos.
6. El aviso de mora CMF llegaba solo al ejecutivo: el cliente no recibía la solicitud institucional del comprobante ni tenía dónde subirlo.

## 3. Correcciones aplicadas
- _criterios_folder ahora usa reglas por tipo (con mixto, exención AFP, entrada de codeudor y sin documentos prohibidos). Esto corrige EN CADENA: correo automático de faltantes (_enviar_faltantes_auto), resumen diario, auditoría del Contralor y PDF a mesa.
- Barrido de aprendizaje sobre los últimos 6 meses (endpoint POST /api/clientes/clasificacion/barrido) con corrección basada en evidencia.
- Flujo CMF completo: aviso institucional automático al cliente (usted, formato exacto) + portal público de comprobante + validación automática (monto ≥95% de la mora CMF, keywords de pago, legibilidad) + marca de regularización + continuación del proceso.

## 4. Resultados del barrido de 6 meses (123 carpetas revisadas)
- Corregidas automáticamente: **9**
- Distribución por evidencia documental: dependientes 63 · independientes 4 · mixtos 4 · sin evidencia suficiente 52
- Exentos de AFP detectados: 1 (ej: PEDRO GONZALEZ — Capredena) · Licencias médicas: 3 · Con codeudor: 2

### Correcciones aplicadas (detalle)
| Cliente | Tipo guardado | Corrección |
|---|---|---|
| Francisca Hernandez | dependiente | licencia médica registrada (no bloquea el proceso) |
| AYLEM MARIELYS DIAZ RODRIGUEZ | independiente | tipo 'independiente' → 'mixto' (evidencia documental) |
| Rodrigo Jara Bustamante | independiente | tipo 'independiente' → 'mixto' (evidencia documental) · licencia médica registrada (no bloquea el proceso) |
| VALESKA DIAZ DIAZ | dependiente | tipo 'dependiente' → 'mixto' (evidencia documental) |
| Catalina Alejandra Aguilera Martin | independiente | tipo 'independiente' → 'mixto' (evidencia documental) |
| Eric Aravena Escobar | dependiente | licencia médica registrada (no bloquea el proceso) |
| Patricia Cabezas | dependiente | tipo 'dependiente' → 'independiente' (evidencia documental) |
| PEDRO GONZALEZ | dependiente | exención AFP detectada: Capredena |
| CLAUDIA ANDREA ZURITA SOTO | dependiente | tipo 'dependiente' → 'independiente' (evidencia documental) |

## 5. Caso de prueba: Víctor Manuel Marin Toro
- Estado verificado tras la corrección: client_type **dependiente** ✅ con evidencia documental coincidente (cats: cédula, liquidación, AFP, CMF).
- Documentos requeridos que ahora se le exigen: cédula + liquidaciones + AFP + CMF (jamás boletas ni renta).
- Resultado del clasificador: sin hallazgos pendientes — clasificación correcta y consistente.

## 6. Verificación del flujo completo
1. **Recepción**: correo entrante → apertura de carpeta (Regla #67: mínimo 3 documentos válidos) → clasificación automática por evidencia.
2. **Faltantes**: _enviar_faltantes_auto responde al remitente con la lista EXACTA según el tipo de cliente (una sola vez por lista, tono institucional).
3. **Unificación**: los documentos se combinan en PDF ordenado según client_type (flujo existente, ahora alimentado por la clasificación corregida).
4. **Mesa**: envío exclusivo a la casilla oficial MESA_EMAIL, ahora bloqueado si los roots no coinciden (Raíz Guard) o si hay licencia sin pago (Regla #70).
5. **Respuesta de mesa**: se registra en seguimiento/carpeta con estado de auditoría (flujo Contralor, verificado en código).

## 7. Patrones de aprendizaje identificados
- Clientes "independientes" con liquidaciones adjuntas suelen ser MIXTOS (4 casos corregidos).
- Las liquidaciones de instituciones uniformadas mencionan Dipreca/Capredena → señal directa de exención AFP.
- "Sin evidencia" (52 casos) = carpetas sin documentos de renta aún: mantener tipo declarado hasta que llegue evidencia.
