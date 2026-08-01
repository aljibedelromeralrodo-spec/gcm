"""Servicio de manipulacion de PDF para el flujo de Autocorreo.

Flujo de mesa:
  - Llega una simulacion (PDF) desde mesa (aprobaciones@centralmutuos.cl).
  - Se deja SOLO la pagina 1 (se eliminan plazos y gastos operacionales de la pag 2+).
  - El PDF ajustado se archiva por cliente y se puede reenviar.
"""
import io
import re
from pypdf import PdfReader, PdfWriter


def leer_texto(pdf_bytes, max_pages=2):
    """Extrae texto de las primeras paginas para clasificar el documento."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        out = []
        for i, page in enumerate(reader.pages):
            if i >= max_pages:
                break
            try:
                out.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(out)
    except Exception:
        return ""


def contar_paginas(pdf_bytes):
    try:
        return len(PdfReader(io.BytesIO(pdf_bytes)).pages)
    except Exception:
        return 0


def clasificar_documento(pdf_bytes, filename=""):
    """Devuelve 'simulacion', 'carta_aprobacion' u 'otro'.

    REGLA INVIOLABLE: cualquier indicio de que es una carta de aprobacion
    (nombre o contenido) la clasifica como carta y NUNCA se modifica.
    """
    fn = (filename or "").lower()
    if re.search(r"carta|aprobaci[oó]n|aprobacion", fn):
        return "carta_aprobacion"
    texto = (leer_texto(pdf_bytes) + " " + fn).lower()
    if re.search(r"agrado de informar|ha sido aprobad|carta de aprobaci|mutuo hipotecario.*aprobad", texto):
        return "carta_aprobacion"
    if re.search(r"simulaci[oó]n|dividendo|gastos operacionales|tasa|plazo|financiamiento|pie", texto):
        return "simulacion"
    return "otro"


def dejar_primera_pagina(pdf_bytes):
    """Genera un PDF nuevo con SOLO la primera pagina.

    Devuelve: (nuevos_bytes, paginas_originales, paginas_removidas)
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    total = len(reader.pages)
    if total <= 1:
        return pdf_bytes, total, 0
    writer = PdfWriter()
    writer.add_page(reader.pages[0])
    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return buf.getvalue(), total, total - 1


def extraer_texto_aprobacion(pdf_bytes):
    """Devuelve el parrafo de aprobacion si existe en el documento."""
    texto = leer_texto(pdf_bytes, max_pages=3)
    m = re.search(r"(estimad[oa][^.]*agrado de informar.*?)(?:\n\n|atentamente|saludos|$)",
                  texto, re.I | re.S)
    if m:
        return m.group(1).strip()
    return ""


IMG_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".heic")


def convertir_a_pdf(raw_bytes, filename):
    """Convierte un archivo a PDF si no lo es.

    - PDF: se devuelve tal cual.
    - Imagenes (jpg/png/etc): se convierten con img2pdf/PIL.
    - Texto plano: se genera un PDF simple.
    Devuelve: (pdf_bytes, nuevo_nombre, convertido:bool). Lanza ValueError si no es soportado.
    """
    fn = (filename or "archivo").strip()
    low = fn.lower()
    if low.endswith(".pdf") or raw_bytes[:5] == b"%PDF-":
        return raw_bytes, fn, False
    base = fn.rsplit(".", 1)[0]
    if low.endswith(IMG_EXT):
        try:
            import img2pdf
            pdf = img2pdf.convert(raw_bytes)
            return pdf, base + ".pdf", True
        except Exception:
            # Fallback PIL (convierte modos no soportados, ej. RGBA)
            from PIL import Image
            im = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
            buf = io.BytesIO()
            im.save(buf, format="PDF")
            return buf.getvalue(), base + ".pdf", True
    if low.endswith((".txt", ".csv")):
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        y = 800
        for line in raw_bytes.decode("utf-8", errors="ignore").splitlines()[:120]:
            c.drawString(40, y, line[:110])
            y -= 14
            if y < 40:
                c.showPage(); y = 800
        c.showPage(); c.save(); buf.seek(0)
        return buf.getvalue(), base + ".pdf", True
    raise ValueError(f"Formato no soportado para conversion: {fn}")


ROLES_TITULAR = re.compile(
    r"^(del?\s+|de\s+la\s+)?(cliente|asegurad|declarante|deudor|titular|"
    r"solicitante|representante|poderdante|mandante|apoderad)")
ROLES_CODEUDOR = re.compile(r"^(del?\s+|de\s+la\s+)?codeudor")


def posiciones_firma_cliente(pdf_bytes, rol="titular"):
    """Detecta las etiquetas donde debe firmar el cliente y devuelve sus posiciones
    [{pagina, x, top, alto_pagina, ancho_pagina, etiqueta}].

    Reglas (rol=titular, el cliente principal):
      - "Firma cliente/asegurado/declarante/deudor/titular/..." (NUNCA codeudor)
      - "Nombre y firma ..." (ej: declaración origen de fondos)
      - "Firma" sola en su línea (ej: designación de apoderado, PEP)
      - Se excluye "Firma ejecutivo ..."
    Con rol=codeudor solo se toman las etiquetas de codeudor."""
    import io as _io
    import unicodedata
    import pdfplumber

    def _norm(s):
        s = unicodedata.normalize("NFD", (s or "").lower())
        return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")

    out = []
    with pdfplumber.open(_io.BytesIO(pdf_bytes)) as pdf:
        for pnum, page in enumerate(pdf.pages, start=1):
            try:
                words = page.extract_words() or []
            except Exception:
                continue
            lineas = {}
            for w in words:
                lineas.setdefault(round(w["top"] / 4), []).append(w)
            for ws in lineas.values():
                ws.sort(key=lambda w: w["x0"])
                texto_linea = _norm(" ".join(x["text"] for x in ws))
                for i, w in enumerate(ws):
                    wt = _norm(w["text"])
                    if not wt.startswith("firma"):
                        continue
                    resto = _norm(" ".join(x["text"] for x in ws[i + 1:i + 4]))
                    prev = _norm(" ".join(x["text"] for x in ws[max(0, i - 2):i]))
                    es_codeudor_lbl = bool(ROLES_CODEUDOR.match(resto))
                    if rol == "codeudor":
                        ok = es_codeudor_lbl
                        etiqueta = "firma codeudor"
                    else:
                        if es_codeudor_lbl or resto.startswith("ejecutiv"):
                            continue
                        sola = re.fullmatch(r"firma[\s:_.]*", texto_linea) is not None
                        nombre_y = prev.endswith("nombre y")
                        con_rol = bool(ROLES_TITULAR.match(resto))
                        ok = con_rol or nombre_y or sola
                        etiqueta = ("firma " + resto.split(" ")[0]) if con_rol else \
                            ("nombre y firma" if nombre_y else "firma")
                    if ok:
                        out.append({"pagina": pnum, "x": float(w["x0"]),
                                    "top": float(w["top"]),
                                    "alto_pagina": float(page.height),
                                    "ancho_pagina": float(page.width),
                                    "etiqueta": etiqueta})
    return out


def estampar_referencias_firma(pdf_bytes, posiciones, nombre_firmante):
    """Imprime en cada etiqueta (menos la primera) una marca de referencia a la
    Firma Electrónica Avanzada única que cubre todo el documento (Ley 19.799)."""
    if not posiciones:
        return pdf_bytes
    from reportlab.pdfgen import canvas
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(io.BytesIO(pdf_bytes))
    por_pagina = {}
    for p in posiciones:
        por_pagina.setdefault(int(p["pagina"]), []).append(p)
    writer = PdfWriter()
    for i, page in enumerate(reader.pages, start=1):
        marcas = por_pagina.get(i)
        if marcas:
            w = float(page.mediabox.width)
            h = float(page.mediabox.height)
            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=(w, h))
            for m in marcas:
                x = max(8, min(float(m["x"]), w - 210))
                y = h - float(m["top"]) + 3
                c.setFillColorRGB(0.13, 0.23, 0.42)
                c.setFont("Helvetica-Bold", 7.5)
                c.drawString(x, y + 17, "Firmado con Firma Electrónica Avanzada")
                c.setFont("Helvetica", 7.5)
                c.drawString(x, y + 8, (nombre_firmante or "").upper()[:48])
                c.setFont("Helvetica-Oblique", 6.3)
                c.drawString(x, y, "FEA e-CertChile válida para todo el documento (Ley 19.799)")
            c.save()
            buf.seek(0)
            overlay = PdfReader(buf).pages[0]
            page.merge_page(overlay)
        writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def estampar_pie_rastro(pdf_bytes, lineas):
    """Imprime un pie de rastro (trazabilidad de firma) en todas las páginas."""
    from reportlab.pdfgen import canvas
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    for page in reader.pages:
        w = float(page.mediabox.width)
        h = float(page.mediabox.height)
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(w, h))
        c.setFillColorRGB(0.32, 0.32, 0.32)
        y = 7
        for ln in reversed(lineas):
            c.setFont("Helvetica", 5.6)
            c.drawString(14, y, ln[:170])
            y += 7
        c.save()
        buf.seek(0)
        page.merge_page(PdfReader(buf).pages[0])
        writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
