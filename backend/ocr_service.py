"""OCR: extrae texto de PDFs. Usa texto embebido (pypdf) y si es escaneado
cae a OCR con Tesseract (via pdf2image + pytesseract)."""
import io


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
        import pytesseract
        imgs = convert_from_bytes(pdf_bytes, dpi=200, first_page=1, last_page=max_pages)
        out = []
        for im in imgs:
            try:
                out.append(pytesseract.image_to_string(im, lang="spa"))
            except Exception:
                out.append(pytesseract.image_to_string(im))
        return "\n".join(out).strip()
    except Exception as e:
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
