# 🏛 REGLAS MAESTRAS — Constitución del Sistema Central Mutuos

> Estas normas son PERMANENTES E INAMOVIBLES. Solo pueden modificarse con el **PIN maestro**
> del Administrador. Copia espejo de las reglas registradas en `dashai_eventos` (motivo `regla_oro`).

## ORO-73 — Gestión de Pago de Mora (autovalidada)
En la ficha del cliente moroso, el ejecutivo dispone de **tres acciones**:
1. **Enviar link/instrucciones de pago al cliente**: correo con el monto exacto de la mora y los
   datos oficiales de transferencia (MUTUARIAS Y LEASING LIMITADA · RUT 77.771.552-6 · Mercado Pago ·
   Cuenta Vista 1030937838 · gerardo.ext@centralmutuos.cl), con referencia única MORA-XXXXXXXX.
2. **Subir comprobante de pago**: validación automática — legibilidad OCR + palabras de pago +
   monto detectado ≥ 95% de la mora registrada en el CMF.
3. **Subir formulario manual de regularización**: validación automática — legibilidad OCR +
   términos de regularización (convenio, compromiso de pago, repactación) + identidad del cliente
   (nombre o RUT presente en el documento).

Al validar (2) o (3), el sistema **cierra la alerta de mora SIN intervención del administrador**,
archiva el documento en `04_cmf`, registra el evento en el historial de la carpeta y marca
`cmf_morosidad.aclarada`. Si la validación falla, el ejecutivo recibe el **motivo exacto** del rechazo.
Mientras el modo prueba de clasificación esté activo, los correos al cliente se interceptan al Administrador.

## ORO-74 — Gestor de Credenciales Crece
Las credenciales de la plataforma **Crece** se administran en el gestor central
(colección `credenciales_crece`, módulo "Credenciales Crece"):
- **Ejecutivos**: acceso EXCLUSIVAMENTE en modo lectura (consultar usuario/clave para operar en Crece).
- **Crear, editar o eliminar**: potestad EXCLUSIVA del Administrador (roles `admin`/`maestro`),
  con bloqueo **403 en el backend** para cualquier otro rol.
- El perfil Gerencia Comercial no tiene acceso al gestor (bloqueo por perfil en backend y menú).

## ORO-75 — Candado Maestro de Campañas (PIN obligatorio)
Ninguna campaña de publicidad (correo o WhatsApp) puede dispararse sin que el Administrador
ingrese el **PIN maestro** como confirmación final, validado en el backend. Sin PIN validado,
el botón de envío **no ejecuta ninguna acción**. Aplica a **todos los perfiles sin excepción**,
incluido el Administrador. Complementos permanentes:
1. **Control manual de volumen**: el Administrador decide cuántos registros enviar en cada
   campaña (primeros 50, 100 o el número que elija). El sistema jamás envía toda la base sola.
2. **Registro de envíos**: cada correo y número de WhatsApp contactado queda registrado con
   fecha en `publicidad_contactados`.
3. **Regla anti-fatiga de 3 meses**: un contacto que recibió publicidad hace menos de 3 meses
   se excluye automáticamente del envío, informando al Administrador cuántos fueron excluidos.
   Solo tras 3 meses puede volver a recibir campaña.

---
*Registradas el 2026-08-22 en dashai_eventos como Reglas de Oro #73 y #74 (inamovibles, nivel de
calibración 100). ORO-75 registrada el 2026-08-23. Cualquier modificación requiere PIN maestro.*
