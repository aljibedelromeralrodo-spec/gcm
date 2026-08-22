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
