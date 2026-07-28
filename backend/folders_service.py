"""Helpers de carpetas de clientes: archivos en disco, categorias, merges y split."""
import io
import re
import zipfile
from pathlib import Path
from pypdf import PdfReader, PdfWriter

CLIENTES_DIR = Path(__file__).parent / "storage" / "clientes"
CLIENTES_DIR.mkdir(parents=True, exist_ok=True)

# tipo de documento (OCR/IA) -> subcarpeta protocolo
SUBFOLDER_POR_TIPO = {
    "cedula": "01_cedula",
    "liquidacion": "02_liquidaciones",
    "impuesto_renta": "02_impuesto_renta",
    "cotizacion_afp": "03_afp",
    "certificado_afp": "03_afp",
    "boleta_honorarios": "03_boletas",
    "certificado_smf": "04_cmf",
}

CAT_A_SUBFOLDER = {
    "cedula": "01_cedula", "liquidacion": "02_liquidaciones",
    "imp_renta": "02_impuesto_renta", "afp": "03_afp",
    "boletas": "03_boletas", "cmf": "04_cmf", "extras": "99_otros",
}
SUBFOLDER_A_CAT = {
    "01_cedula": "cedula", "02_liquidaciones": "liquidacion",
    "02_impuesto_renta": "imp_renta", "03_afp": "afp",
    "03_boletas": "boletas", "04_cmf": "cmf", "99_otros": "extras",
    "05_codeudor": "codeudor",
}

CAT_KEYWORDS = [
    ("cedula", r"c[eé]?dula|carnet|identidad|registro civil"),
    ("liquidacion", r"liquidaci[oó]?n|sueldo|remuneraci|haberes|\bliq[\d_ ]|^liq"),
    ("afp", r"afp|cotizaci|previred|afiliaci|habitat|provida|planvital|cuprum|capital"),
    ("cmf", r"cmf|smf|sbif|informe de deuda|deuda"),
    ("imp_renta", r"impuesto|renta|formulario 22|f22|declaraci[oó]n"),
    ("boletas", r"boleta|honorario"),
]

MISSING_LABELS = {
    "cedula": "Cédula de identidad",
    "liquidacion": "Liquidaciones de sueldo (últimas 6)",
    "afp": "Cotizaciones AFP (últimas 12)",
    "cmf": "Informe de deudas CMF",
    "imp_renta": "Última declaración de impuesto a la renta",
    "boletas": "Resumen de boletas de honorarios",
}


def safe_name(name):
    return re.sub(r"[^A-Za-z0-9._ -]", "_", (name or "").strip()) or "cliente"


def folder_dir(nombre):
    return CLIENTES_DIR / safe_name(nombre)


def required_cats(client_type):
    if client_type == "independiente":
        return ["cedula", "imp_renta", "boletas", "cmf"]
    return ["cedula", "liquidacion", "afp", "cmf"]


def es_combinado(nombre_archivo):
    low = (nombre_archivo or "").lower()
    return low.startswith("combinado") or low.startswith("carpeta_")


def cat_de_archivo(nombre, subfolder=""):
    sub = (subfolder or "").split("/")[0]
    if es_combinado(nombre) or sub == "00_combinados":
        return "combinado"
    if sub == "05_codeudor" or (nombre or "").upper().startswith("CODEUDOR_"):
        return "codeudor"
    if sub in SUBFOLDER_A_CAT:
        return SUBFOLDER_A_CAT[sub]
    return cat_de_texto(nombre)


def cat_de_texto(texto):
    low = (texto or "").lower()
    for cat, pat in CAT_KEYWORDS:
        if re.search(pat, low):
            return cat
    return "extras"


def scan_archivos(nombre):
    base = folder_dir(nombre)
    out = []
    if base.exists():
        for p in sorted(base.rglob("*")):
            if p.is_file():
                rel = p.relative_to(base).as_posix()
                sub = rel.rsplit("/", 1)[0] if "/" in rel else ""
                out.append({"nombre": p.name, "ruta": rel, "subfolder": sub,
                            "tamano": p.stat().st_size})
    out.sort(key=lambda a: (a["subfolder"], a["nombre"]))
    return out


def resolver_ruta(nombre, rel_path):
    """Resuelve una ruta relativa dentro de la carpeta, prevenir path traversal."""
    base = folder_dir(nombre).resolve()
    target = (base / rel_path).resolve()
    if not str(target).startswith(str(base)):
        raise ValueError("Ruta inválida")
    return target


def guardar_archivo(nombre_carpeta, filename, raw, subfolder=""):
    """Guarda bytes en la carpeta. Si subfolder vacío, clasifica por nombre."""
    fn = safe_name(filename)
    sub = safe_name(subfolder) if subfolder else ""
    if not sub:
        cat = cat_de_texto(fn)
        sub = CAT_A_SUBFOLDER.get(cat, "") if cat != "extras" else ""
    dest = folder_dir(nombre_carpeta) / sub if sub else folder_dir(nombre_carpeta)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / fn).write_bytes(raw)
    return f"{sub}/{fn}" if sub else fn


def merge_protocol(nombre, client_type="dependiente", include_extras=True):
    base = folder_dir(nombre)
    order = required_cats(client_type) + (["extras"] if include_extras else [])
    usable = []
    for a in scan_archivos(nombre):
        if not a["nombre"].lower().endswith(".pdf"):
            continue
        cat = cat_de_archivo(a["nombre"], a["subfolder"])
        if cat in ("combinado", "codeudor"):
            continue
        if cat not in order:
            if not include_extras:
                continue
            cat = "extras"
        usable.append((order.index(cat), cat, a))
    usable.sort(key=lambda t: (t[0], t[2]["ruta"]))
    writer = PdfWriter()
    used, errors = [], []
    for _, cat, a in usable:
        try:
            reader = PdfReader(str(base / a["ruta"]))
            for pg in reader.pages:
                writer.add_page(pg)
            used.append({"cat": cat, "rel": a["ruta"]})
        except Exception as e:
            errors.append(f"{a['ruta']}: {str(e)[:120]}")
    merged_name = f"COMBINADO_PROTOCOLO_{safe_name(nombre)}.pdf"
    if used:
        base.mkdir(parents=True, exist_ok=True)
        with open(base / merged_name, "wb") as f:
            writer.write(f)
    return {"merged_file": merged_name if used else "", "files_used": used,
            "errors": errors, "client_type": client_type,
            "protocol_order": order}


def merge_codeudor(nombre):
    """Combina los PDFs del codeudor (05_codeudor) en COMBINADO_CODEUDOR_*.pdf."""
    base = folder_dir(nombre)
    sub = base / "05_codeudor"
    if not sub.exists():
        return {"merged_file": "", "files_used": [], "errors": []}
    writer = PdfWriter()
    used, errors = [], []
    for p in sorted(sub.glob("*.pdf")):
        if es_combinado(p.name):
            continue
        try:
            reader = PdfReader(str(p))
            for pg in reader.pages:
                writer.add_page(pg)
            used.append(f"05_codeudor/{p.name}")
        except Exception as e:
            errors.append(f"{p.name}: {str(e)[:120]}")
    merged_name = f"COMBINADO_CODEUDOR_{safe_name(nombre)}.pdf"
    if used:
        with open(base / merged_name, "wb") as f:
            writer.write(f)
    return {"merged_file": merged_name if used else "", "files_used": used, "errors": errors}


def merge_pdfs(nombre, rel_files):
    from datetime import datetime
    base = folder_dir(nombre)
    writer = PdfWriter()
    used, errors = [], []
    for rel in rel_files:
        if not rel.lower().endswith(".pdf"):
            continue
        try:
            p = resolver_ruta(nombre, rel)
            reader = PdfReader(str(p))
            for pg in reader.pages:
                writer.add_page(pg)
            used.append(rel)
        except Exception as e:
            errors.append(f"{rel}: {str(e)[:120]}")
    if not used:
        return {"merged_file": "", "files_used": [], "errors": errors or ["Sin PDFs válidos"]}
    sub = base / "00_combinados"
    sub.mkdir(parents=True, exist_ok=True)
    merged_name = f"COMBINADO_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    with open(sub / merged_name, "wb") as f:
        writer.write(f)
    return {"merged_file": f"00_combinados/{merged_name}", "files_used": used, "errors": errors}


def _texto_pagina(reader, idx, pdf_bytes, permitir_ocr=True):
    try:
        texto = reader.pages[idx].extract_text() or ""
    except Exception:
        texto = ""
    if len(texto.strip()) >= 40 or not permitir_ocr:
        return texto
    try:
        from pdf2image import convert_from_bytes
        import pytesseract
        imgs = convert_from_bytes(pdf_bytes, dpi=150, first_page=idx + 1, last_page=idx + 1)
        if imgs:
            try:
                return pytesseract.image_to_string(imgs[0], lang="spa")
            except Exception:
                return pytesseract.image_to_string(imgs[0])
    except Exception:
        pass
    return texto


def split_bundled(nombre, rel_path, route_to_codeudor=False, delete_original=False):
    """Divide un PDF empaquetado en archivos por categoría (páginas consecutivas)."""
    src = resolver_ruta(nombre, rel_path)
    if not src.exists():
        raise FileNotFoundError(rel_path)
    raw = src.read_bytes()
    reader = PdfReader(io.BytesIO(raw))
    n_pages = len(reader.pages)
    permitir_ocr = n_pages <= 30
    cats = []
    for i in range(n_pages):
        texto = _texto_pagina(reader, i, raw, permitir_ocr)
        cats.append(cat_de_texto(texto) if len((texto or "").strip()) >= 15 else None)
    # Paginas sin texto heredan la categoría anterior (continuación)
    last = None
    for i in range(n_pages):
        if cats[i] is None:
            cats[i] = last or "extras"
        else:
            last = cats[i]
    # Agrupar consecutivas
    groups = []
    for i, c in enumerate(cats):
        if groups and groups[-1]["category"] == c:
            groups[-1]["pages"].append(i + 1)
        else:
            groups.append({"category": c, "pages": [i + 1]})
    prefix = "CODEUDOR_" if route_to_codeudor else ""
    written = []
    contador = {}
    for g in groups:
        contador[g["category"]] = contador.get(g["category"], 0) + 1
        writer = PdfWriter()
        for pg in g["pages"]:
            writer.add_page(reader.pages[pg - 1])
        fn = f"{prefix}{g['category']}_{contador[g['category']]}.pdf"
        sub = CAT_A_SUBFOLDER.get(g["category"], "99_otros")
        dest = folder_dir(nombre) / sub
        dest.mkdir(parents=True, exist_ok=True)
        buf = io.BytesIO()
        writer.write(buf)
        (dest / fn).write_bytes(buf.getvalue())
        written.append({"category": g["category"], "rel": f"{sub}/{fn}", "pages": g["pages"]})
    deleted = False
    if delete_original:
        try:
            src.unlink()
            deleted = True
        except Exception:
            pass
    return {"n_groups": len(groups), "n_pages": n_pages, "written": written,
            "deleted_original": deleted}


def zip_folder(nombre):
    base = folder_dir(nombre)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for a in scan_archivos(nombre):
            z.write(base / a["ruta"], arcname=a["ruta"])
    buf.seek(0)
    return buf.getvalue()
