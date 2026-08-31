# 🔒 Módulos FINALIZADOS Y PROTEGIDOS (no tocar sin orden explícita del usuario)

## Motor de Firma eCert (declarado inviolable el 2026-08-06)
- `server.py` sección "PORTAL DE FIRMA VIP": `/api/firma/generar-link`, `GET /api/firma/{token}`,
  `POST /api/firma/{token}/firmar`, `POST /api/firma/{token}/click`, `_MSG_FIRMA_OK`.
- `migrup_service.py`: `login`, `asegurar_contacto`, `crear_contacto`, `enviar_a_firmar_tercero`,
  `listar_documentos`, `get_file`, `semaforo`.
- Reglas selladas:
  1. La firma SIEMPRE va por `enviar_a_firmar_tercero` (contactoId por RUT, texto=clave cert si es propio).
  2. El portal /api/firma/{token} es terminal privada Central Mutuos SIN enlaces externos.
  3. Cero fricción: RUT/email se resuelven solos desde set_credito/folders; el cliente solo pone
     Clave Única y códigos en el flujo eCert.
  4. Mensaje de éxito DORADO (negro carbono + borde #D4AF37 + texto #F5E7B8).
- Cualquier edición futura en server.py debe dejar intactas las líneas de esta sección.

## REGLA USUARIO (2026-06): PLANTILLAS APROBADAS — NO MODIFICAR
- Las plantillas de solicitud de documentos, gasto operacional y formas de envío existentes están APROBADAS.
- PROHIBIDO modificarlas en pruebas o features nuevas. Features nuevas usan plantillas propias separadas.
