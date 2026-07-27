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
    """Devuelve 'simulacion', 'carta_aprobacion' u 'otro'."""
    texto = (leer_texto(pdf_bytes) + " " + (filename or "")).lower()
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
