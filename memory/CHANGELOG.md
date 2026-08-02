# CHANGELOG — Central Mutuos (continuación de PRD.md "Implementado")

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
- P0: Bug parsing titular vs codeudor (Vanesa Ocampo / Jonathan Araya: "complementa
  renta" = codeudor; extraer proyecto y montos del cuerpo). REPORTADO, NO RESUELTO.
- P1: Crear carpetas de brokers que pidieron escrituración el último mes
  (Work Consultores, Gestión Hipotecaria, Maestra, Bosch, Ecomac).
- P2: Prueba en vivo de Correo a Mesa con saldo eCert real (espera al usuario).
- El usuario indicó que estos cambios quedan permanentes para subir a PRODUCCIÓN
  (redeploy) y partir desde este punto.
