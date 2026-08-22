# 🧠 APRENDIZAJE PERSISTENTE — Correos reales de Central Mutuos (análisis 30 días, 2026-08-22)
Fuente: 400 mensajes de ethangerardobarr@gmail.com (Gmail API) + IMAP gerardo.ext. 230 correos de gestión procesados.

## 1. Remitentes frecuentes de solicitudes (confianza MUY ALTA)
- **Ecomac** (@ecomac.cl): Ximena T. Gomez Pino (la más activa, ~25 correos), Sara/Gina Gomez Pino, Marisela V. Ortiz Araya, Carla F. Paz Valdivia, Amalia A. Galleguillos Urrutia, Viviana González/Rojas.
- **Boetsch** (@boetsch.cl): Rodrigo Salazar (fuchslocher@), Celinda Soria (csoria@ — también envía BASES DE CLIENTES en Excel), cuentas de proyecto "Uvas y el Viento 2/4", "Terrazas del Bicentenario".
- **Maestra** (@maestra.cl / @MAESTRA.CL): Fabiola Pérez Arias, María José Moreno, Ana Pérez Barra, Karla Pavez, Andrea Delgado.
- **Ejecutivas internas**: Yerile (yerile426@gmail.com), Kimberlyn Aragon (@hip...), Deisy Salazar.
- **Clientes directos** (gmail personales): envían "Liquidaciones", "Documentos para evaluación" — válidos si traen PDFs.
- Reenvíos internos: gerardo.ext@centralmutuos.cl (Fwd:/RV: de todo lo anterior).

## 2. Asuntos típicos por patrón
- `SOLICITUD CREDITO MUTUO // {NOMBRE} RUT: {rut}` (Kimberlyn/Yerile)
- `EVALUAR ENTREGA INMEDIATA_{NOMBRE}_RUT_{rut}_CONDOMINIO {X}` / `EVALUAR_PREAPROBACION_...` (Marisela, Ecomac)
- `EVALUACION {NOMBRE}// ENTREGA {FUTURA|INMEDIATA|PROXIMA}// {CON|SIN} SUBSIDIO` (Carla Paz)
- `EVALUACION CLIENTE {NOMBRE} RUT: {rut} CONDOMINIO {X}` (Rodrigo Salazar, Boetsch)
- `EVALUACION CREDITO || {NOMBRE} || {rut}` (Uvas y el Viento)
- `Liquidaciones de {cliente} rut {rut} interesado en {condominio} valor {X}uf subsidio {X}uf ahorro {X}uf credito {X}uf` (Ximena Gómez — trae TODOS los datos financieros en el asunto)
- `SOLICITUD DE ANTECEDENTES - CONDOMINIO {X} {NOMBRE}` (Gina Gómez)
- Set a MESA (manual): `{Nombre} ({DS19|SIN SUBSIDIO} - {INMEDIATA|FUTURA|mes} - {EJECUTIVA})` → aprobaciones@centralmutuos.cl
- Set a MESA (sistema): `Antecedentes crédito hipotecario — {NOMBRE} ({rut}) — Entrega: {X} — Ejecutivo: {Y}`

## 3. Formatos de documentos y secuencia habitual de llegada por cliente
1. **Primer correo** (ejecutiva inmobiliaria): 6-27 PDFs sueltos — 6 liquidaciones (`Liquidacion_{Mes}_{año}-{rut}-FF1.pdf`), certificado AFP/cotizaciones, informe CMF (`informe_deudas_{rut}.pdf`), cédula (`CARNET.pdf`, fotos jpg) + firmas basura (image001.png ×2).
2. **Variante frecuente**: UN SOLO PDF combinado `{Nombre} EV.pdf` (~2-3MB, 10-14 págs: cédula p1-2, contrato, 6-8 liquidaciones, CMF al final) → usar divisor multi-documento.
3. **Correos de complemento** (mismos días): "RE:/RV:" con documentación faltante (boletas, renta), papeles del CODEUDOR/AVAL, o correcciones.
4. **Aval/complemento**: "{cliente} y complemento", "+AVAL {parentesco}" → van a subcarpeta 05_codeudor.
5. **Independientes**: boletas de honorarios ×5-7 + declaración renta/F22 en vez de liquidaciones.
6. Casos WhatsApp: fotos JPG comprimidas de baja resolución (aplicar upscaling + rotación).

## 4. Palabras clave de MESA (aprobaciones@centralmutuos.cl) — verificadas en 32 veredictos
- ✅ APROBACIÓN: "Tenemos el agrado de informar que el crédito solicitado califica para un mutuo hipotecario endosable [con subsidio estatal]" + adjuntos Carta_Aprobacion_*.pdf y Simulador_*.pdf. Condición opcional: "por máximo posible de UF {X}".
- ❌ RECHAZO: "El crédito no cumple parámetros objetivos mínimos de aprobación permitidos", "muy pasado en carga financiera", "ingresos del titular no son suficientes", "ingresos de sociedad SPA no podemos considerar". Recomendaciones: "limitar la deuda a UF {X}", "incorporar un codeudor". Sin adjuntos.
- ⚠️ OBSERVACIÓN: "Favor revisar", "No sé qué pasó aquí", "la aprobación/simulación/ficha está por UF {X}".

## 5. Reglas operativas confirmadas por el administrador (2026-08-22)
- Carpeta enriquecida progresivamente: correos parciales SUMAN documentos (nunca reemplazan) + evento en historial (fecha, remitente, archivos nuevos).
- Documentos no clasificados → "otros" (99_otros), SIEMPRE incluidos al FINAL del PDF combinado a mesa. Ningún documento se rechaza (salvo Ley del RUT: RUT distinto → Buzón de Rescate).
- Orden del set a mesa: 01_Cedula → 02_Liquidaciones/Impuesto_Renta → 03_AFP/Boletas → 04_CMF → 05_codeudor/contratos → 99_otros.
- Regla 67: mínimo 3 categorías válidas para abrir carpeta (el divisor multi-documento ayuda a cumplirla).


## 6. Casos especiales (análisis 60 días, 2026-08-22)
### Codeudor / Aval / Complemento
- Señales en asunto: "+AVAL SU PADRE", "+AVAL MAMA", "y su aval su pareja", "y complemento", "(Aval {Titular})", "y su pareja". El correo del aval puede llegar SEPARADO: "Documentos {Aval} (Aval {Titular})".
- Guardado: subcarpeta 05_codeudor/{Nombre}/ con prefijo CODEUDOR_, campos codeudor_nombre/codeudor_rut en folder; Ley del RUT rutea archivos por RUT al anexo; el PDF combinado del titular EXCLUYE papeles del codeudor (merge_codeudor aparte).
- Mesa: evalúa renta conjunta; rechaza ingresos de sociedad SPA del codeudor; recomienda "incorporar un codeudor" en rechazos por carga.
- Casos: Jonathan Galleguillos(+padre), Silvia Meriño(+mamá), Helen Veas, Nicolás Guevara(pareja, boletas), Camila Collado(pareja), Javiera Espinoza↔Rodrigo Espinoza (correos separados), Javiera Mery, Carlos Arancibia (RECHAZADO por SPA), Ignacio Pizarro, Yan Carmona, Eduar Araya.
### Boletas de honorarios (independientes)
- tipo_cliente=independiente si hay boleta_honorarios o impuesto_renta. Set: cédula → impuesto_renta(F22) → boletas (resumen anual SII / Carpeta_Tributaria_Regular.pdf) → CMF.
- Casos: Valeska Díaz (6 boletas+4 renta → APROBADA "máximo posible UF 1500"), Catalina Aguilera (mixto 7+7), Camila Collado, Nicolás Guevara, Nicolás Muñoz, Carlos Justo y pareja.
- Mesa suele aprobar con TOPE de monto a independientes.
### Licencias médicas (<30 días trabajados)
- Las liquidaciones reales traen campos estructurados: "Días Trabajados: X · Días Licencia: Y · Días Ausencia" (formato constructoras) o "Días trabajados: 29 Días licencia: 0" (pymes). EXTRAER SIEMPRE.
- Si Días Licencia>0 o Trabajados<30: el sueldo del mes está incompleto → exigir PAGO DE LICENCIA (CCAF Los Andes/Los Héroes o Isapre, "subsidio de incapacidad laboral") como respaldo de renta. Hoy ese comprobante NO tiene categoría → cae en 99_otros.
- Candidatos detectados por contenido: Yan Carmona, Gloria Bolados, Julieth Marin, Ignacio Pizarro, Maira Valenzuela.
### Pre/Postnatal
- Patrón: clienta embarazada con licencia maternal → liquidaciones bajas o en cero + subsidio maternal pagado por Isapre/CCAF. Suele complementarse con AVAL (caso Javiera Espinoza + Rodrigo Espinoza).
- Renta se acredita con: liquidaciones previas + comprobantes de pago de licencia maternal (mensuales) + certificado prenatal/postnatal. No descartar por liquidación baja.

## 7. Casos límite (análisis 120 días, 2026-08-22)
### Edad máxima / plazo
- Mesa NUNCA escribe "por edad" ni "acorta el plazo" en sus correos. El efecto edad es INVISIBLE en el texto: aparece solo como tope de monto ("el crédito posible estaría por debajo de las UF 2000") o dentro del Simulador_*.pdf adjunto (campo plazo).
- Caso ancla: **Eduar Araya Collao, 55 años (RUT 11.821.533-8)** → 1º rechazo "no cumple parámetros... incorporar codeudor" → 2º "crédito posible por debajo de UF 2000" → ejecutiva Ximena renegocia a casa de menor valor al 80% de financiamiento.
- Solo el formato de ficha de Ximena Gómez (Ecomac) trae campo "Edad:". El resto de ejecutivas NO informa edad → única fuente alternativa: RUT (correlación aproximada) o cédula OCR (fecha nacimiento).
- Regla nueva: si edad>=55 → marcar folder `edad_titular` y alertar que el monto máximo puede bajar por plazo acortado.
### Antigüedad laboral
- Rechazo textual nuevo: "necesitamos al menos 6 meses de empleabilidad a plazo fijo" (Yan Carmona, 40a, técnico construcción). La antigüedad se lee de las liquidaciones (fecha ingreso) — hoy no la extraemos.
### 2 trabajos dependientes simultáneos
- **CERO casos explícitos en 120 días.** No existe ni un correo con "dos empleadores/dos contratos/segundo empleador" referido a un mismo titular. La renta múltiple en esta operación se materializa como TITULAR + CODEUDOR/COMPLEMENTO (100 correos "codeudor", 55 "complementa"), nunca como doble contrato del mismo RUT.
### Dependiente + independiente
- Ocurre a nivel de PAREJA/COMPLEMENTO, no del mismo RUT: Catalina Aguilera (liquidaciones) + Nelson Barraza (Certificados SII, mixto 7+7); Javiera Espinoza + Rodrigo Espinoza.
- Frase clave de Mesa: "favor enviar informe resumen de boletas de honorarios, con eso podemos evaluar independientes" → el doc que desbloquea la evaluación independiente es el RESUMEN ANUAL SII, no las boletas sueltas.
- Desenlace típico: aprobación CON TOPE ("por máximo posible de UF X") o cambio de titular ("No se puede aprobar con ella como titular").
### 3 trabajos dependientes
- **CERO casos en 120 días.** No crear reglas especulativas.
### Frases nuevas de Mesa (agregadas a proc_rules)
- Rechazo: "no hay posibilidad de aprobar", "estaría por debajo de las UF X", "necesitamos al menos N meses", "No se puede aprobar con ella como titular", "FAVOR CANCELAR EMAIL DE APROBACIÓN".
- Observación: "Favor pedir detalles de la deuda indirecta", "Favor confirmar si es con o sin subsidio", "favor enviar informe resumen de boletas".
- Aprobación con tope: "por máximo posible de UF X", "Adjunto simulación por máximo posible", "POR AMBAS OPCIONES SOLICITADAS".
- OJO: una APROBACIÓN puede ser ANULADA minutos después ("FAVOR CANCELAR EMAIL DE APROBACIÓN") → nunca cerrar el estado del folder con el primer correo de aprobación; esperar ventana de corrección.
