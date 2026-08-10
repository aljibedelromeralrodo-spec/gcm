"""Helpers de carpetas de clientes: archivos en disco, categorias, merges y split."""
import io
import os
import re
import uuid
import base64
import zipfile
import time
from collections import deque
from pathlib import Path
from pypdf import PdfReader, PdfWriter

# ANTI-SPAM: máximo de llamadas OCR-IA (GPT visión) por hora en todo el proceso
_AI_OCR_CALLS = deque()
_AI_OCR_MAX_HORA = 40


def _ai_ocr_permitido():
    ahora = time.time()
    while _AI_OCR_CALLS and ahora - _AI_OCR_CALLS[0] > 3600:
        _AI_OCR_CALLS.popleft()
    if len(_AI_OCR_CALLS) >= _AI_OCR_MAX_HORA:
        return False
    _AI_OCR_CALLS.append(ahora)
    return True

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
    "estudio_titulo": "07_estudio_titulo",
}
SUBFOLDER_A_CAT = {
    "01_cedula": "cedula", "02_liquidaciones": "liquidacion",
    "02_impuesto_renta": "imp_renta", "03_afp": "afp",
    "03_boletas": "boletas", "04_cmf": "cmf", "99_otros": "extras",
    "05_codeudor": "codeudor", "07_estudio_titulo": "estudio_titulo",
}

CAT_KEYWORDS = [
    ("estudio_titulo", r"estudio de t[ií]tulo|dominio vigente|hipotecas? y grav|grav[aá]men|prohibici[oó]n|expropiaci|conservador de bienes|\bcbr\b|escritura de compraventa|copia de escritura|inscripci[oó]n de dominio"),
    ("cedula", r"c[eé]?dula|carnet|identidad|registro civil"),
    ("liquidacion", r"liquidaci[oó]?n|sueldo|remuneraci|haberes|\bliq[\d_ ]|^liq"),
    ("afp", r"afp|cotizaci|previred|afiliaci|habitat|provida|planvital|cuprum|capital"),
    ("cmf", r"\bcmf\b|\bsmf\b|\bsbif\b|informe[_ ]de[_ ]deuda|informe_deudas|certificado[_ ]de[_ ]deuda|deuda consolidada"),
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


# NOMENCLATURA POR ORDEN: prefijos numéricos en cada archivo para forzar el orden
PREFIJO_POR_CAT = {
    "cedula": "01_Cedula", "liquidacion": "02_Liquidaciones",
    "afp": "03_Certificado_AFP", "cmf": "04_CMF",
    "imp_renta": "02_Impuesto_Renta", "boletas": "03_Resumen_Impuestos",
}


def orden_numerico(nombre, subfolder=""):
    """SORT NUMÉRICO (REGLA INAMOVIBLE): jerarquía por prefijo 01..99 del archivo
    o, en su defecto, de la subcarpeta protocolo. Sin prefijo = 99 (al final)."""
    m = re.match(r"^(\d{2})_", nombre or "")
    if not m:
        m = re.match(r"^(\d{2})_", (subfolder or "").split("/")[0])
    return int(m.group(1)) if m else 99


def nombre_con_prefijo(filename, cat):
    """Antepone el prefijo numérico de la categoría si el archivo aún no lo tiene."""
    pref = PREFIJO_POR_CAT.get(cat)
    if not pref or re.match(r"^\d{2}_", filename or "") or (filename or "").upper().startswith("CODEUDOR_"):
        return filename
    return f"{pref}_{filename}"


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
    if sub.startswith("05_codeudor") or (nombre or "").upper().startswith("CODEUDOR_"):
        return "codeudor"
    if sub in SUBFOLDER_A_CAT:
        return SUBFOLDER_A_CAT[sub]
    return cat_de_texto(nombre)


def cat_de_texto(texto):
    low = (texto or "").lower()
    if re.search(r"infnomat|no[_ ]matrimonio|matrimonio|uni[oó]n civil", low):
        return "extras"
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
    if not target.is_relative_to(base):
        raise ValueError("Ruta inválida")
    return target


def guardar_archivo(nombre_carpeta, filename, raw, subfolder=""):
    """Guarda bytes en la carpeta. Si subfolder vacío, clasifica por nombre.
    Aplica la nomenclatura por orden (01_Cedula, 02_..., 04_CMF)."""
    fn = safe_name(filename)
    sub = subfolder.strip("/ ") if subfolder else ""
    if sub:
        sub = "/".join(safe_name(s) for s in sub.split("/"))
        cat = SUBFOLDER_A_CAT.get(sub.split("/")[0], "")
    else:
        cat = cat_de_texto(fn)
        sub = CAT_A_SUBFOLDER.get(cat, "") if cat != "extras" else ""
    fn = safe_name(nombre_con_prefijo(fn, cat))
    dest = folder_dir(nombre_carpeta) / sub if sub else folder_dir(nombre_carpeta)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / fn).write_bytes(raw)
    return f"{sub}/{fn}" if sub else fn


RUT_RX = re.compile(r"\b\d{1,2}\.?\d{3}\.?\d{3}\s?-\s?[\dkK]\b")


def _norm_rut_fs(r):
    return re.sub(r"[.\-\s]", "", (r or "")).lower()


def ruts_de_pdf_cache(path):
    """RUTs de un PDF con caché Mongo (path+size+mtime): no repite OCR jamás."""
    from bunker import _fs
    p = Path(path)
    try:
        st = p.stat()
    except OSError:
        return set()
    try:
        _f, db = _fs()
        key = {"path": str(p), "size": st.st_size, "mtime": int(st.st_mtime)}
        hit = db.ocr_rut_cache.find_one(key)
        if hit is not None:
            return set(hit.get("ruts") or [])
    except Exception:
        db = None
    import ocr_service
    try:
        texto, _m = ocr_service.extraer_texto(p.read_bytes(), p.name)
    except Exception:
        texto = ""
    ruts = sorted({_norm_rut_fs(r) for r in RUT_RX.findall(texto or "")})
    if db is not None:
        try:
            db.ocr_rut_cache.replace_one({"path": str(p)}, {**key, "ruts": ruts}, upsert=True)
        except Exception:
            pass
    return set(ruts)


def _ruts_personas(ruts):
    """Filtra solo RUTs de personas naturales (< 50.000.000). Los RUT de empresas
    (empleadores, AFP, municipalidades) no cuentan para exclusión."""
    out = set()
    for r in ruts:
        num = re.sub(r"[^0-9]", "", (r or "")[:-1])
        try:
            if num and int(num) < 50000000:
                out.add(r)
        except ValueError:
            continue
    return out


def _rut_titular_de(nombre):
    try:
        from bunker import _fs
        _f, db = _fs()
        d = db.folders.find_one({"nombre": nombre}, {"rut": 1}) or {}
        return _norm_rut_fs(d.get("rut", ""))
    except Exception:
        return ""


def merge_protocol(nombre, client_type="dependiente", include_extras=True, order=None):
    base = folder_dir(nombre)
    # REGLA IVANA: sin RUT titular NO hay combinación de PDF
    rut_t = _rut_titular_de(nombre)
    if len(rut_t) < 7:
        return {"merged_file": "", "files_used": [],
                "errors": ["REGLA IVANA: la carpeta no tiene RUT titular — combinación bloqueada. Configure el RUT primero."],
                "client_type": client_type, "protocol_order": order or [], "excluidos_rut": []}
    order = list(order) if order else (required_cats(client_type) + (["extras"] if include_extras else []))
    usable = []
    for a in scan_archivos(nombre):
        if not a["nombre"].lower().endswith(".pdf"):
            continue
        cat = cat_de_archivo(a["nombre"], a["subfolder"])
        if cat in ("combinado", "codeudor", "estudio_titulo"):
            continue
        if cat not in order:
            if not include_extras:
                continue
            cat = "extras"
        usable.append((order.index(cat), cat, a))
    # SORT NUMÉRICO: los prefijos 01..06 mandan; el orden de llegada no importa
    usable.sort(key=lambda t: (orden_numerico(t[2]["nombre"], t[2]["subfolder"]), t[0], t[2]["ruta"]))
    writer = PdfWriter()
    used, errors = [], []
    excluidos_rut = []
    for _, cat, a in usable:
        # FILTRO DE COMBINACIÓN (REGLA IVANA): si el PDF trae RUTs y NINGUNO es el
        # del titular, queda FUERA del combinado — aunque esté en carpeta normal.
        ruts_a = _ruts_personas(ruts_de_pdf_cache(base / a["ruta"]))
        if ruts_a and rut_t not in ruts_a:
            excluidos_rut.append(a["ruta"])
            continue
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
            "protocol_order": order, "excluidos_rut": excluidos_rut}


def merge_codeudor(nombre):
    """Combina los PDFs del codeudor (05_codeudor y subcarpetas por nombre)."""
    base = folder_dir(nombre)
    sub = base / "05_codeudor"
    if not sub.exists():
        return {"merged_file": "", "files_used": [], "errors": []}
    writer = PdfWriter()
    used, errors = [], []
    for p in sorted(sub.rglob("*.pdf")):
        if es_combinado(p.name):
            continue
        try:
            reader = PdfReader(str(p))
            for pg in reader.pages:
                writer.add_page(pg)
            used.append(p.relative_to(base).as_posix())
        except Exception as e:
            errors.append(f"{p.name}: {str(e)[:120]}")
    merged_name = f"COMBINADO_CODEUDOR_{safe_name(nombre)}.pdf"
    if used:
        with open(base / merged_name, "wb") as f:
            writer.write(f)
    return {"merged_file": merged_name if used else "", "files_used": used, "errors": errors}


def reclasificar_codeudor(nombre, codeudor_nombre="", codeudor_rut=""):
    """VERIFICACIÓN DUAL: mueve a 05_codeudor los PDFs del codeudor que quedaron en la
    raíz u otras subcarpetas del titular (prefijo CODEUDOR_ o RUT exclusivo del codeudor)."""
    import shutil
    base = folder_dir(nombre)
    if not base.exists():
        return []
    rut_c = _norm_rut_fs(codeudor_rut)
    dest = base / "05_codeudor" / (safe_name(codeudor_nombre) if codeudor_nombre else "")
    movidos = []
    for p in sorted(base.rglob("*.pdf")):
        rel = p.relative_to(base).as_posix()
        if rel.startswith(("05_codeudor/", "00_combinados/", "07_estudio_titulo/")) or es_combinado(p.name):
            continue
        es_cod = p.name.upper().startswith("CODEUDOR_")
        if not es_cod and len(rut_c) >= 7:
            ruts = _ruts_personas(ruts_de_pdf_cache(p))
            es_cod = bool(ruts) and ruts == {rut_c}
        if not es_cod:
            continue
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / (p.name if p.name.upper().startswith("CODEUDOR_") else f"CODEUDOR_{p.name}")
        if target.exists():
            p.unlink()
        else:
            shutil.move(str(p), str(target))
        movidos.append(target.relative_to(base).as_posix())
    return movidos


CODEUDOR_MIN_CATS = ("cedula", "liquidacion")


def merge_protocolo_codeudor(nombre, codeudor_nombre="", codeudor_rut="", solo_si_minimos=False):
    """PROTOCOLO DUAL: genera COMBINADO_PROTOCOLO_CODEUDOR_<Nombre>.pdf DENTRO de
    05_codeudor bajo las mismas reglas del titular. Match por RUT: solo entran
    documentos cuyo OCR contenga el RUT del codeudor (o sin RUTs de persona)."""
    base = folder_dir(nombre)
    sub = base / "05_codeudor"
    out = {"merged_file": "", "files_used": [], "errors": [], "excluidos_rut": [], "faltan_minimos": []}
    if not sub.exists():
        return out
    rut_c = _norm_rut_fs(codeudor_rut)

    def _cat(p):
        return cat_de_archivo(re.sub(r"^CODEUDOR_", "", p.name, flags=re.I), "")

    files = [p for p in sorted(sub.rglob("*.pdf")) if not es_combinado(p.name)]
    cats = {_cat(p) for p in files}
    out["faltan_minimos"] = [c for c in CODEUDOR_MIN_CATS if c not in cats]
    if solo_si_minimos and out["faltan_minimos"]:
        return out
    orden = {"cedula": 0, "liquidacion": 1, "afp": 2, "cmf": 3, "imp_renta": 4, "boletas": 5}
    files.sort(key=lambda p: (orden_numerico(re.sub(r"^CODEUDOR_", "", p.name, flags=re.I)),
                              orden.get(_cat(p), 9), p.name))
    writer = PdfWriter()
    for p in files:
        if len(rut_c) >= 7:
            ruts = _ruts_personas(ruts_de_pdf_cache(p))
            if ruts and rut_c not in ruts:
                out["excluidos_rut"].append(p.name)
                continue
        try:
            for pg in PdfReader(str(p)).pages:
                writer.add_page(pg)
            out["files_used"].append(p.relative_to(base).as_posix())
        except Exception as e:
            out["errors"].append(f"{p.name}: {str(e)[:120]}")
    if out["files_used"]:
        merged_name = f"COMBINADO_PROTOCOLO_CODEUDOR_{safe_name(codeudor_nombre or nombre)}.pdf"
        with open(sub / merged_name, "wb") as f:
            writer.write(f)
        out["merged_file"] = f"05_codeudor/{merged_name}"
    return out


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


def _ocr_ia_pagina(pdf_bytes, idx):
    """Respaldo OCR con IA (visión): renderiza la página con PyMuPDF y transcribe
    con el modelo de visión. Se usa cuando tesseract/poppler no están disponibles."""
    if os.environ.get("AI_EMERGENCY_STOP") == "1":
        return ""
    if not _ai_ocr_permitido():
        return ""
    key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not key:
        return ""
    import fitz
    import asyncio as _aio
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pix = doc[idx].get_pixmap(dpi=120)
    b64 = base64.b64encode(pix.tobytes("png")).decode()
    doc.close()
    from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

    async def _run():
        chat = LlmChat(api_key=key, session_id=f"ocr-{uuid.uuid4()}",
                       system_message=("Transcribe TODO el texto visible de la imagen de un "
                                       "documento chileno. Responde SOLO el texto plano, sin "
                                       "comentarios ni formato.")).with_model("openai", "gpt-5.4-mini")
        return await chat.send_message(UserMessage(
            text="Transcribe el texto de esta página:",
            file_contents=[ImageContent(image_base64=b64)]))
    resp = _aio.run(_aio.wait_for(_run(), timeout=60))
    return resp if isinstance(resp, str) else str(resp)


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
                t = pytesseract.image_to_string(imgs[0], lang="spa", timeout=60)
            except Exception:
                t = pytesseract.image_to_string(imgs[0], timeout=60)
            if (t or "").strip():
                return t
    except Exception:
        pass
    try:
        t = _ocr_ia_pagina(pdf_bytes, idx)
        if (t or "").strip():
            return t
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
        base_fn = f"{prefix}{g['category']}_{contador[g['category']]}.pdf"
        fn = base_fn if prefix else nombre_con_prefijo(base_fn, g["category"])
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
