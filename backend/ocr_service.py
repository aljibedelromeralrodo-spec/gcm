"""OCR: extrae texto de PDFs. Usa texto embebido (pypdf) y si es escaneado
cae a OCR con Tesseract (via pdf2image + pytesseract).
Blindaje de legibilidad: EXIF → upscaling (fotos chicas/WhatsApp ≈300 DPI)
→ auto-rotación por OSD → contraste y nitidez, ANTES de leer."""
import io
import re


def preprocesar_imagen(im, min_lado=1500, max_escala=4.0):
    """Devuelve la imagen lista para OCR o para convertir a PDF legible."""
    from PIL import Image, ImageOps, ImageEnhance
    try:
        im = ImageOps.exif_transpose(im)
    except Exception:
        pass
    if im.mode != "RGB":
        im = im.convert("RGB")
    lado = min(im.size)
    if 0 < lado < min_lado:
        f = min(max_escala, min_lado / float(lado))
        if f > 1.05:
            im = im.resize((int(im.width * f), int(im.height * f)), Image.LANCZOS)
    try:
        im = ImageEnhance.Contrast(im).enhance(1.25)
        im = ImageEnhance.Sharpness(im).enhance(1.6)
    except Exception:
        pass
    return im


def _tess(im):
    try:
        import pytesseract
        try:
            return pytesseract.image_to_string(im, lang="spa", timeout=90).strip()
        except Exception:
            return pytesseract.image_to_string(im, timeout=90).strip()
    except Exception:
        return ""


def _puntaje_texto(t):
    """Palabras reales (≥3 letras) — mide si la lectura tiene sentido o es basura girada."""
    return len(re.findall(r"[A-Za-zÁÉÍÓÚÑÜáéíóúñü]{3,}", t or ""))


def ocr_imagen(im, preprocesar=True):
    """OCR con auto-orientación: lee derecho y, si el texto no tiene sentido,
    prueba 90/180/270 y se queda con la mejor lectura. Devuelve (texto, imagen_corregida)."""
    if preprocesar:
        im = preprocesar_imagen(im)
    mejor_txt, mejor_im, mejor_p = "", im, -1
    for ang in (0, 90, 180, 270):
        cand = im if ang == 0 else im.rotate(ang, expand=True, fillcolor="white")
        txt = _tess(cand)
        p = _puntaje_texto(txt)
        if p > mejor_p:
            mejor_txt, mejor_im, mejor_p = txt, cand, p
        if ang == 0 and p >= 12:
            break
    return mejor_txt, mejor_im


def texto_embebido(pdf_bytes, max_pages=6):
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        out = []
        for i, page in enumerate(reader.pages):
            if i >= max_pages:
                break
            try:
                out.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(out).strip()
    except Exception:
        return ""


def ocr_texto(pdf_bytes, max_pages=4):
    try:
        from pdf2image import convert_from_bytes
        imgs = convert_from_bytes(pdf_bytes, dpi=250, first_page=1, last_page=max_pages)
        out = []
        for im in imgs:
            texto, _ = ocr_imagen(im, preprocesar=True)
            if texto:
                out.append(texto)
        return "\n".join(out).strip()
    except Exception:
        return ""


def extraer_texto(pdf_bytes, filename="", force_ocr=False):
    """Devuelve (texto, metodo). Usa embebido si hay suficiente; si no, OCR."""
    if not force_ocr:
        emb = texto_embebido(pdf_bytes)
        if len(emb) >= 80:
            return emb, "embebido"
    ocr = ocr_texto(pdf_bytes)
    if ocr:
        return ocr, "ocr"
    emb = texto_embebido(pdf_bytes)
    return emb, "embebido" if emb else "vacio"
