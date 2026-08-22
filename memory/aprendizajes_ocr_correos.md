# Aprendizajes (sesión anti-duplicados + OCR)
- OSD de tesseract gira MAL fotos comprimidas: usar puntaje de palabras reales probando 0/90/180/270.
- tesseract/poppler son binarios apt: NO persisten en pod nuevo -> guard en startup() de server.py los reinstala.
- Duplicados de correo: 2 casillas IMAP reciben el mismo mail con UID distinto -> dedup SIEMPRE por huella de contenido, no por UID.
- send_mail tiene escudo global Regla #68: cualquier envío idéntico en 7 días se bloquea (permitir_duplicado=True para override).
- uvicorn --reload puede colgarse en shutdown por los ~40 loops de fondo: usar supervisorctl restart backend.
