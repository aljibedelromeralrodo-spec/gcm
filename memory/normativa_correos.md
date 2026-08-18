# NORMATIVA FIJA E INAMOVIBLE — Correos y Supercarpeta (auditada y validada)
No modificable sin instrucción explícita del usuario.

## 1. SUPERCARPETA — Vista de tarjetas
- Navegación por tarjetas verticales expandibles (`SupercarpetaCards.js`). Sin tablas ni scroll horizontal.
- Todos los campos editables con doble clic (`CampoEditable`, POST /api/supercarpeta/manual/{fid}).
- Semáforo por hito: ✅ verde completado · 🟡 amarillo en proceso · 🔴 rojo pendiente (función `semaforo`).

## 2. RESUMEN DEL HILO IA
- Línea visible en cada tarjeta: [estado actual] + [quién debe el próximo paso] + [fecha dd/mm].
- NORMA: solo considera eventos de los últimos 90 días.
- Auto-generación: `resumen_hilo_loop` (cada 15 min, solo si hay correos nuevos — firma SHA-256 de eventos).
- Regeneración manual: botón 🔄 → POST /api/supercarpeta/resumen-hilo/{fid}.
- Guardado en `folders.resumen_hilo` {texto, en, firma}. Modelo: gpt-5.4-mini (Emergent LLM Key).

## 3. ESTUDIO DE TÍTULO — Nueva vs Usada
- USADA: listado legal completo (`_docs_usada_html` / SECCIONES_ESTUDIO_USADA: Títulos de dominio,
  Herencias/Sucesiones, Fusiones/Subdivisiones/Loteos, CBR, DOM, TGR, SII) con wrap propio `_estudio_usada_wrap`.
- NUEVA: sin listado (DOCS_ESTUDIO_NUEVA = []), solo solicitud estándar.

## 4. PLANTILLAS — Compartimentos estancos
- Carta Oferta / Solicitud de Crédito / SERVIU: plantillas propias en malla_inteligencia (solicitud-doc).
- Estudio de Título: `_estudio_html` + `_estudio_usada_wrap` (JAMÁS la plantilla de Carta Oferta).
- Tasación: `_tasacion_html`. Ningún módulo hereda texto de otro.

## 5. DISEÑO HTML de correos
- Fondo blanco, fuente Arial, encabezados en gris (#f0f0f0 / #444), plazos y datos clave en negrita.
- Firma SIEMPRE "Central Mutuos" — PROHIBIDO mencionar "Concreces"/"Con Creces" en correos.
- Wrapper central: `_marca_wrap` (server.py). Firma personal: `_firma_html` (malla, Arial).

## 6. DESTINATARIOS Estudio de Título (cascada)
1) Inmobiliaria registrada → 2) Vendedor registrado → 3) Correo de origen de la solicitud (editable).
(`/api/estudio-titulo/preview-carpeta/{fid}` + autoaprendizaje al enviar).

## 7. REGLA CC — ABSOLUTA
- CC (Victoria, Daniela o cualquier interno) SOLO en correos ENTRANTES procesados por el sistema:
  - `_cc_correo_entrante` (server.py): reenvío de reparos del abogado al vendedor y aviso "reparos resueltos"
    (ambos disparados por la RECEPCIÓN de un correo del abogado).
  - `_reenvio_co_rs` (malla): reenvío de documentos RECIBIDOS a Victoria/Daniela (como destinatarios).
- Correos SALIENTES: SIN CC bajo ninguna circunstancia. Aplicado en:
  - Estudio de Título etapa 1 (/api/estudio-titulo/enviar) y etapa 2 (envío docs al abogado).
  - Recordatorio 5 días al abogado. Carta Oferta / SERVIU / Solicitud de Crédito (cc=[] en solicitud-doc).
  - Tasación (nunca tuvo CC).
- Victoria NUNCA se agrega como TO encubierto: eliminado de `_parse_destinatarios` y de TASACION_DEST_DEFAULT.

## 8. REGISTRO EN CEREBRO DASHAI (2026-08-18)
- Las 7 normativas quedaron registradas como eventos 📜 NORMATIVA en la Bitácora de Aprendizaje
  Perpetuo (db.dashai_eventos, motivo="normativa", inamovible=True) + config `dashai_normativas_fijas`.
- Recalibración manual ejecutada: nivel de calibración 98%.
