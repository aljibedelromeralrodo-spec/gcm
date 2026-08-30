"""Lectura de PDFs de hitos (tasación, estudio de títulos, escritura).

Texto embebido primero; OCR solo si el PDF es escaneado y se pide explícito.
Sin LLM: no toca el clasificador constitucional de correos.
"""
from __future__ import annotations

import re
from pathlib import Path

_RX_UF = re.compile(
    r"(?:valor(?:\s+de)?\s+(?:comercial|tasaci[oó]n|mercado)|tasaci[oó]n(?:\s+comercial)?)"
    r"[^\n]{0,40}?(?:UF|U\.F\.)\s*[:\s]*([\d]{1,3}(?:[.\s]\d{3})*(?:,\d+)?|\d+(?:[.,]\d+)?)"
    r"|"
    r"(?:UF|U\.F\.)\s*[:\s]*([\d]{1,3}(?:[.\s]\d{3})*(?:,\d+)?|\d+(?:[.,]\d+)?)"
    r"[^\n]{0,30}?(?:valor|tasaci|comercial)",
    re.I,
)
_RX_UF_SIMPLE = re.compile(
    r"(?:UF|U\.F\.)\s*[:\s]*([\d]{1,3}(?:[.\s]\d{3})*(?:,\d+)?|\d+(?:[.,]\d+)?)", re.I)
_RX_CLP = re.compile(
    r"(?:valor(?:\s+de)?\s+(?:comercial|tasaci[oó]n)|\$)\s*[:\s]*\$?\s*"
    r"([\d]{1,3}(?:[.\s]\d{3})+(?:,\d+)?)", re.I)
_RX_ROL = re.compile(
    r"rol(?:\s+de)?\s+aval[uú]o\s*[:nº°.\s]*([0-9]{2,6}\s*[-–]\s*[0-9]{2,6})", re.I)
_RX_COMUNA = re.compile(r"comuna\s+(?:de\s+)?([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑa-záéíóúñ]+){0,3})", re.I)
_RX_FOJAS = re.compile(
    r"fojas\s*[:\s]*([\d.]+)\s*(?:,|\s+)?(?:n[uú]mero|n[º°]|nro\.?|#)\s*[:\s]*([\d.]+)"
    r"\s*(?:del\s+a[nñ]o|de|/|-)?\s*(20\d{2}|\d{4})?", re.I)
_RX_CBR = re.compile(
    r"conservador\s+de\s+bienes\s+ra[ií]ces\s+(?:de\s+)?([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s]{2,40})", re.I)
_RX_GRAV = re.compile(r"hipoteca|gravamen|prohibici[oó]n|embargo", re.I)
_RX_REPERTORIO = re.compile(r"repertorio\s*[:nº°nro.\s]*([0-9]{2,8})", re.I)
_RX_NOTARIA = re.compile(
    r"notar[ií]a\s+(?:de\s+)?([A-ZÁÉÍÓÚÑ][^\n,]{3,60})", re.I)
_RX_FECHA = re.compile(
    r"(?:fecha(?:\s+de)?\s+(?:tasaci[oó]n|estudio|firma|escritura|emisi[oó]n)?)\s*[:\s]*"
    r"(\d{1,2}[/\-]\d{1,2}[/\-]20\d{2}|\d{1,2}\s+de\s+\w+\s+de\s+20\d{2})", re.I)
_RX_FECHA_SOLTA = re.compile(r"\b(\d{1,2}[/\-]\d{1,2}[/\-]20\d{2})\b")
_RX_TASADOR = re.compile(
    r"(?:tasador|value\s*property|volvet|informe\s+de\s+tasaci[oó]n[^\n]{0,40})"
    r"[^\n]{0,50}", re.I)


def _num(s):
    if not s:
        return None
    t = str(s).strip().replace(" ", "")
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")
    elif t.count(".") > 1:
        t = t.replace(".", "")
    try:
        return float(t)
    except ValueError:
        return None


def _primera(*vals):
    for v in vals:
        if v not in (None, "", [], {}):
            return v
    return None


def extraer_tasacion(texto):
    t = texto or ""
    uf = None
    m = _RX_UF.search(t)
    if m:
        uf = _num(m.group(1) or m.group(2))
    if uf is None:
        m = _RX_UF_SIMPLE.search(t)
        if m:
            uf = _num(m.group(1))
    clp = None
    m = _RX_CLP.search(t)
    if m:
        clp = _num(m.group(1))
    rol = None
    m = _RX_ROL.search(t)
    if m:
        rol = re.sub(r"\s+", "", m.group(1).replace("–", "-"))
    comuna = None
    m = _RX_COMUNA.search(t)
    if m:
        comuna = m.group(1).strip()
    fecha = _fecha(t)
    tasador = ""
    m = _RX_TASADOR.search(t)
    if m:
        tasador = re.sub(r"\s+", " ", m.group(0)).strip()[:80]
    return _limpio({
        "valor_uf": uf, "valor_clp": clp, "rol_avaluo": rol,
        "comuna": comuna, "fecha": fecha, "tasador": tasador,
    })


def extraer_estudio(texto):
    t = texto or ""
    fojas = numero = anio = cbr = None
    m = _RX_FOJAS.search(t)
    if m:
        fojas, numero, anio = m.group(1), m.group(2), m.group(3)
    m = _RX_CBR.search(t)
    if m:
        cbr = re.sub(r"\s+", " ", m.group(1)).strip(" .")[:40]
    return _limpio({
        "fojas": fojas, "numero": numero, "anio": anio, "cbr": cbr,
        "fecha": _fecha(t),
        "menciona_gravamen": bool(_RX_GRAV.search(t)),
    })


def extraer_escritura(texto):
    t = texto or ""
    repertorio = notaria = None
    m = _RX_REPERTORIO.search(t)
    if m:
        repertorio = m.group(1)
    m = _RX_NOTARIA.search(t)
    if m:
        notaria = re.sub(r"\s+", " ", m.group(1)).strip(" .")[:60]
    return _limpio({
        "repertorio": repertorio, "notaria": notaria, "fecha_firma": _fecha(t),
    })


def extraer_campos(hito, texto):
    h = (hito or "").lower()
    if h == "tasacion":
        return extraer_tasacion(texto)
    if h == "estudio_titulo":
        return extraer_estudio(texto)
    if h == "escritura":
        return extraer_escritura(texto)
    return {}


def _fecha(texto):
    m = _RX_FECHA.search(texto or "")
    if m:
        return m.group(1)
    m = _RX_FECHA_SOLTA.search(texto or "")
    return m.group(1) if m else None


def _limpio(d):
    return {k: v for k, v in d.items() if v not in (None, "", False)}


def leer_pdf(path, permitir_ocr=False):
    """Devuelve (texto, metodo). OCR solo si embebido < 80 chars y se autoriza."""
    p = Path(path)
    try:
        raw = p.read_bytes()
    except OSError:
        return "", "vacio"
    try:
        import ocr_service
        emb = ocr_service.texto_embebido(raw, max_pages=4)
        if len(emb) >= 80:
            return emb, "embebido"
        if permitir_ocr and len(raw) <= 12_000_000:
            texto, metodo = ocr_service.extraer_texto(raw, p.name, force_ocr=False)
            return texto or emb, metodo or "ocr"
        return emb, "embebido" if emb else "vacio"
    except Exception:
        return "", "error"


def hito_de_rel(rel, nombre=""):
    """Clasifica un archivo de carpeta como hito de tasación/estudio/escritura."""
    blob = f"{rel or ''} {nombre or ''}".lower().replace("\\", "/")
    if "tasac" in blob or "/tasacion" in blob or blob.startswith("tasacion"):
        return "tasacion"
    if "07_estudio_titulo" in blob or "estudio_titulo" in blob or "estudio_" in blob.split("/")[-1]:
        return "estudio_titulo"
    fn = blob.split("/")[-1]
    if fn.startswith("escritura") or "notaria" in blob or "repertorio" in blob:
        return "escritura"
    return ""


def patch_sin_pisar(fd, hito, campos, ahora=""):
    """$set para la carpeta. Nunca pisa renta, monto de crédito ni OCR ya lleno."""
    campos = campos or {}
    df = fd.get("datos_financieros") or {}
    out = {}
    h = (hito or "").lower()
    if h == "tasacion":
        if ahora and not fd.get("tasacion_informe_recibido_at"):
            out["tasacion_informe_recibido_at"] = ahora
        if campos.get("valor_uf") and not df.get("valor_tasacion_uf"):
            out["datos_financieros.valor_tasacion_uf"] = campos["valor_uf"]
        if campos.get("rol_avaluo") and not (df.get("rol_avaluo") or df.get("rol_propiedad")):
            out["datos_financieros.rol_avaluo"] = campos["rol_avaluo"]
        existente = fd.get("tasacion_ocr") if isinstance(fd.get("tasacion_ocr"), dict) else {}
        merged = dict(existente)
        for k, v in campos.items():
            if v not in (None, "") and not merged.get(k):
                merged[k] = v
        if merged and merged != existente:
            out["tasacion_ocr"] = merged
    elif h == "estudio_titulo":
        if ahora and not fd.get("estudio_recibido_at"):
            out["estudio_recibido_at"] = ahora
        existente = fd.get("estudio_ocr") if isinstance(fd.get("estudio_ocr"), dict) else {}
        merged = dict(existente)
        for k, v in campos.items():
            if v not in (None, "") and not merged.get(k):
                merged[k] = v
        if merged and merged != existente:
            out["estudio_ocr"] = merged
    elif h == "escritura":
        existente = fd.get("escritura_ocr") if isinstance(fd.get("escritura_ocr"), dict) else {}
        merged = dict(existente)
        for k, v in campos.items():
            if v not in (None, "") and not merged.get(k):
                merged[k] = v
        if merged and merged != existente:
            out["escritura_ocr"] = merged
    return out


def analizar_adjuntos(hito, paths, permitir_ocr=False, max_ocr=2):
    """Fusiona campos de varios PDFs del mismo correo-hito."""
    hito = (hito or "").lower()
    archivos, merged = [], {}
    ocr_left = max_ocr if permitir_ocr else 0
    for path in paths or []:
        p = Path(path)
        if not p.is_file() or p.suffix.lower() != ".pdf":
            continue
        usar_ocr = ocr_left > 0
        texto, metodo = leer_pdf(p, permitir_ocr=usar_ocr)
        if metodo == "ocr":
            ocr_left -= 1
        campos = extraer_campos(hito, texto)
        archivos.append({"filename": p.name, "metodo": metodo, "chars": len(texto),
                         "campos": campos})
        for k, v in campos.items():
            merged.setdefault(k, v)
    return {"hito": hito, "campos": merged, "archivos": archivos}
