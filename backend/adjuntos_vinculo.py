"""Vínculo correo↔carpeta: match de nombre/RUT y motivos de descarte (sin IMAP)."""
import re
import unicodedata

MSG_CARPETA_SIN_RUT = (
    "Esta carpeta no tiene RUT registrado. No puedo buscar adjuntos solo por nombre "
    "(hay personas con el mismo nombre). Cargá el RUT del cliente o usá «Importar desde correo»."
)

MOTIVO_LABELS = {
    "carpeta_sin_rut": "carpeta sin RUT",
    "rut_ausente_en_texto": "sin RUT en el correo ni en el PDF",
    "nombre_no_coincide": "el nombre no coincide",
    "remitente_no_reconocido": "remitente no reconocido",
    "ley_del_rut": "el RUT del PDF no coincide con el de la carpeta",
    "duplicado": "ya estaba en la carpeta",
}


def sin_acentos(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def norm_rut(r):
    return re.sub(r"[^0-9kK]", "", (r or "")).lower()


def nucleo_rut_carpeta(rut):
    n = norm_rut(rut)
    return n if len(n) >= 7 else ""


def item_descarte(motivo, subject="", sender="", filename="", detalle=""):
    return {
        "motivo": motivo,
        "subject": (subject or "")[:120],
        "from": (sender or "")[:80],
        "filename": (filename or "")[:80],
        "detalle": (detalle or "")[:240],
    }


def evaluar_vinculo_correo(subject, sender, body, tokens, rut_nucleo,
                           ruts_por_pdf=None, fallback_ocr_rut=False):
    """Decide si un correo puede vincularse a la carpeta. Sin IMAP, sin disco.

    tokens: palabras del nombre ya en minúsculas sin tildes.
    rut_nucleo: RUT normalizado (≥7) de la carpeta.
    ruts_por_pdf: lista de sets de RUTs ya extraídos (normalizados, match exacto).
    Devuelve (aceptar: bool, motivo: str|None).
    """
    nucleo = norm_rut(rut_nucleo)
    if len(nucleo) < 7:
        return False, "carpeta_sin_rut"
    blob = sin_acentos(f"{subject or ''} {sender or ''} {body or ''}")
    toks = [t for t in (tokens or []) if t]
    if toks:
        hits = sum(1 for t in toks if t in blob)
        if hits < len(toks):
            return False, "nombre_no_coincide"
    blob_rut = re.sub(r"[.\-\s]", "", blob)
    if nucleo in blob_rut:
        return True, None
    if fallback_ocr_rut:
        for ruts in (ruts_por_pdf or []):
            normalizados = {norm_rut(x) for x in (ruts or [])}
            if nucleo in normalizados:
                return True, None
        return False, "rut_ausente_en_texto"
    return False, "rut_ausente_en_texto"


def resumen_descartes(descartes):
    counts = {}
    for d in descartes or []:
        m = d.get("motivo") or "otro"
        counts[m] = counts.get(m, 0) + 1
    return counts


def texto_resumen_descartes(descartes):
    counts = resumen_descartes(descartes)
    if not counts:
        return ""
    partes = [f"{n} {MOTIVO_LABELS.get(m, m)}" for m, n in counts.items()]
    return "No se guardaron: " + ", ".join(partes) + "."
