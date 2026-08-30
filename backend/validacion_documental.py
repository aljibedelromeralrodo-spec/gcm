"""Validación documental por perfil laboral (dependiente / independiente / mixto).

Fuente única de: documentos requeridos, vigencia de fechas y alertas específicas
(ej. «Falta liquidación de sueldo del mes de abril»). No mezcla requisitos
prohibidos entre perfiles — así se evitan alertas erróneas.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import folders_service as fsvc

MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}
_MES_NOM = {
    "enero": 1, "ene": 1, "january": 1, "jan": 1,
    "febrero": 2, "feb": 2, "february": 2,
    "marzo": 3, "mar": 3, "march": 3,
    "abril": 4, "abr": 4, "april": 4, "apr": 4,
    "mayo": 5, "may": 5,
    "junio": 6, "jun": 6, "june": 6,
    "julio": 7, "jul": 7, "july": 7,
    "agosto": 8, "ago": 8, "august": 8, "aug": 8,
    "septiembre": 9, "setiembre": 9, "sep": 9, "sept": 9, "september": 9,
    "octubre": 10, "oct": 10, "october": 10,
    "noviembre": 11, "nov": 11, "november": 11,
    "diciembre": 12, "dic": 12, "dec": 12, "december": 12,
}
_MES_RX = re.compile(
    r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|"
    r"octubre|noviembre|diciembre|january|february|march|april|june|july|"
    r"august|september|october|november|december|"
    r"ene|feb|mar|abr|may|jun|jul|ago|sept|sep|oct|nov|dic|jan|apr|aug|dec)\b",
    re.I,
)
RX_F22 = re.compile(r"formulario[\s_\-]?22|f22|carpeta[\s_]?tributaria", re.I)
RX_F29 = re.compile(r"formulario[\s_\-]?29|(?:^|[\s_\-])f29(?:[\s_\-.]|$)", re.I)
RX_DAI = re.compile(r"(?:^|[\s_\-])dai(?:[\s_\-.]|$)|declaraci[oó]n anual de ingresos", re.I)
RX_CONTRATO = re.compile(r"contrato\s+de\s+trabajo|anexo\s+de\s+contrato", re.I)
RX_FIRMA = re.compile(r"^image\d{1,4}\.(jpe?g|png|gif|bmp)$", re.I)

EXT_OK = {
    ".pdf", ".jpg", ".jpeg", ".png", ".heic", ".heif", ".tif", ".tiff",
    ".doc", ".docx", ".xls", ".xlsx",
}
CATS_IGNORAR = {"combinado", "codeudor", "estudio_titulo"}

LIQ_MESES = 6
AFP_MESES = 12
CMF_DIAS = 90

LABELS = {
    "cedula": "Cédula de identidad",
    "liquidacion": "Liquidaciones de sueldo",
    "afp": "Cotizaciones previsionales AFP",
    "cmf": "Informe CMF",
    "boletas": "Boletas de honorarios / DAI",
    "imp_renta": "Carpeta tributaria / Formulario F22",
    "f29": "Formulario F29",
    "contrato": "Contrato de trabajo",
}


def cats_requeridas(tipo, exento_afp=False):
    """Categorías obligatorias según perfil. `desconocido` solo pide lo común (evita falsos)."""
    tipo = (tipo or "dependiente").lower().strip()
    if tipo in ("desconocido", "por_revisar"):
        return ["cedula", "cmf"]
    if tipo == "independiente":
        return ["cedula", "imp_renta", "boletas", "cmf"]
    if tipo == "mixto":
        docs = ["cedula", "liquidacion", "boletas", "imp_renta", "cmf"]
        if not exento_afp:
            docs.insert(2, "afp")
        return docs
    # dependiente (default)
    docs = ["cedula", "liquidacion", "cmf"]
    if not exento_afp:
        docs.insert(2, "afp")
    return docs


def periodo_de_nombre(nombre, ahora=None):
    """Extrae (año, mes) del nombre de archivo. None si no hay fecha reconocible."""
    return periodo_de_texto(nombre or "", ahora=ahora)


def periodo_de_texto(texto, ahora=None):
    """Extrae (año, mes) de un nombre o del texto de una liquidación/CMF."""
    if not texto:
        return None
    ahora = ahora or datetime.now(timezone.utc)
    low = re.sub(r"[._\-]+", " ", str(texto).lower())
    # Contexto típico de liquidación chilena: «periodo / mes de / remuneraciones»
    ctx = re.search(
        r"(?:per[ií]odo|mes(?:\s+de)?|remuneraci\w*|l[ií]quido a pagar)[^\n]{0,80}",
        low)
    chunk = (ctx.group(0) + " " + low[:1200]) if ctx else low[:1500]
    m = re.search(r"(20\d{2})[-_/ ](0[1-9]|1[0-2])\b", chunk)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"\b(0[1-9]|1[0-2])[-_/ ](20\d{2})\b", chunk)
    if m:
        return int(m.group(2)), int(m.group(1))
    # dd/mm/yyyy (Chile)
    m = re.search(r"\b(\d{1,2})[/\-](\d{1,2})[/\-](20\d{2})\b", chunk)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if mo > 12 and 1 <= d <= 12:
            d, mo = mo, d
        if 1 <= mo <= 12:
            return y, mo
    m = re.search(r"(20\d{2})(0[1-9]|1[0-2])(?:\D|$)", chunk)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = _MES_RX.search(chunk)
    if m:
        mes = _MES_NOM[m.group(1).lower()]
        y = re.search(r"(20\d{2})", chunk)
        year = int(y.group(1)) if y else ahora.year
        if not y and mes > ahora.month:
            year -= 1
        return year, mes
    return None


def tipo_laboral_de_tipos(tipos):
    """Ingesta: mixto si hay renta dependiente E independiente en el mismo correo."""
    s = {(t or "").lower() for t in (tipos or [])}
    dep = bool(s & {"liquidacion", "cotizacion_afp", "certificado_afp", "afp"})
    ind = bool(s & {"boleta_honorarios", "impuesto_renta", "boletas", "imp_renta", "f29"})
    if dep and ind:
        return "mixto"
    if ind:
        return "independiente"
    return "dependiente"


_PERIODO_MEM = {}


def periodo_desde_pdf(path, ahora=None):
    """Texto embebido (sin OCR visión) + caché path/mtime/tamaño. None si no hay fecha."""
    p = Path(path)
    try:
        st = p.stat()
    except OSError:
        return None
    key = (str(p), int(st.st_mtime), st.st_size)
    if key in _PERIODO_MEM:
        return _PERIODO_MEM[key]
    per = None
    db = None
    try:
        from bunker import _fs
        _f, db = _fs()
        hit = db.ocr_periodo_cache.find_one({"path": str(p), "size": st.st_size, "mtime": int(st.st_mtime)})
        if hit is not None:
            if hit.get("anio") and hit.get("mes"):
                per = (int(hit["anio"]), int(hit["mes"]))
            _PERIODO_MEM[key] = per
            return per
    except Exception:
        db = None
    try:
        import ocr_service
        texto = ocr_service.texto_embebido(p.read_bytes(), max_pages=2)
        per = periodo_de_texto(texto, ahora=ahora)
    except Exception:
        per = None
    _PERIODO_MEM[key] = per
    if len(_PERIODO_MEM) > 4000:
        _PERIODO_MEM.clear()
    if db is not None:
        try:
            doc = {"path": str(p), "size": st.st_size, "mtime": int(st.st_mtime),
                   "anio": per[0] if per else None, "mes": per[1] if per else None}
            db.ocr_periodo_cache.replace_one({"path": str(p)}, doc, upsert=True)
        except Exception:
            pass
    return per


def meses_ventana(n, ahora=None, cerrados=True):
    """Últimos `n` meses calendario (cerrados = excluye el mes en curso)."""
    ahora = ahora or datetime.now(timezone.utc)
    y, m = ahora.year, ahora.month
    if cerrados:
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    out = []
    for _ in range(n):
        out.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    out.reverse()
    return out


def _nombre_mes(ym, con_anio=False):
    y, m = ym
    n = MESES_ES.get(m, str(m))
    return f"{n} de {y}" if con_anio else n


def _alerta(nivel, mensaje, cat="", mes=None):
    a = {"nivel": nivel, "mensaje": mensaje, "cat": cat}
    if mes:
        a["mes"] = {"anio": mes[0], "mes": mes[1]}
    return a


def _texto_faltante_mes(label_singular, ym, ventana):
    anios = {y for y, _m in ventana}
    return f"Falta {label_singular} del mes de {_nombre_mes(ym, con_anio=len(anios) > 1)}"


def _periodo_archivo(a, ahora, base_dir=None):
    """Nombre → campo `periodo` → texto embebido del PDF (caché). No inventa mes."""
    if a.get("periodo"):
        try:
            y, m = a["periodo"][0], a["periodo"][1]
            return int(y), int(m)
        except (TypeError, ValueError, IndexError, KeyError):
            pass
    p = periodo_de_nombre(a.get("nombre") or "", ahora=ahora)
    if p:
        return p
    ruta = a.get("ruta") or ""
    if base_dir and ruta and str(ruta).lower().endswith(".pdf"):
        try:
            return periodo_desde_pdf(Path(base_dir) / ruta, ahora=ahora)
        except Exception:
            return None
    return None


def _vigencia_mensual(archivos, n, label_plural, label_singular, ahora, base_dir=None):
    """Devuelve (ok, alertas). Mes específico solo si TODOS los archivos tienen fecha.

    Si hay PDFs sin mes en el nombre/texto, no se inventan «falta abril»: se cae a conteo.
    """
    alertas = []
    cat = "liquidacion" if "liquidaci" in label_plural else "afp"
    if not archivos:
        alertas.append(_alerta(
            "faltante", f"Faltan {label_plural} (últimos {n} meses)", cat=cat))
        return False, alertas
    ventana = meses_ventana(n, ahora=ahora, cerrados=True)
    parsed, n_sin_fecha = set(), 0
    for a in archivos:
        p = _periodo_archivo(a, ahora, base_dir=base_dir)
        if p:
            parsed.add(p)
            a["periodo"] = p
        else:
            n_sin_fecha += 1
    if n_sin_fecha:
        # Hay archivos sin mes: no listar meses inventados.
        if len(archivos) >= n:
            return True, alertas
        faltan_n = n - len(archivos)
        alertas.append(_alerta(
            "faltante",
            f"Faltan {faltan_n} {label_plural} (hay {len(archivos)} de {n} requeridas)",
            cat=cat))
        return False, alertas
    if not parsed:
        if len(archivos) >= n:
            return True, alertas
        faltan_n = n - len(archivos)
        alertas.append(_alerta(
            "faltante",
            f"Faltan {faltan_n} {label_plural} (hay {len(archivos)} de {n} requeridas)",
            cat=cat))
        return False, alertas
    faltan = [ym for ym in ventana if ym not in parsed]
    for ym in faltan:
        alertas.append(_alerta(
            "faltante",
            _texto_faltante_mes(label_singular, ym, ventana),
            cat=cat, mes=ym))
    return not faltan, alertas


def _vigencia_cmf(archivos, ahora):
    """Existencia = obligatorio. Antigüedad > 90 días = aviso de vigencia (no bloquea)."""
    alertas = []
    if not archivos:
        alertas.append(_alerta("faltante", "Falta Informe CMF", cat="cmf"))
        return False, alertas
    fechas = []
    for a in archivos:
        p = periodo_de_nombre(a.get("nombre") or "", ahora=ahora)
        if p:
            try:
                fechas.append(datetime(p[0], p[1], 1, tzinfo=timezone.utc))
            except ValueError:
                pass
        mtime = a.get("mtime")
        if mtime:
            try:
                fechas.append(datetime.fromtimestamp(float(mtime), tz=timezone.utc))
            except (TypeError, ValueError, OSError):
                pass
    if fechas:
        mas_reciente = max(fechas)
        edad = (ahora - mas_reciente).days
        if edad > CMF_DIAS:
            alertas.append(_alerta(
                "vigencia",
                f"Informe CMF con vigencia vencida ({edad} días; máximo {CMF_DIAS})",
                cat="cmf"))
    return True, alertas


def _formato_archivo(a):
    nom = a.get("nombre") or ""
    if RX_FIRMA.match(nom):
        return None
    ext = Path(nom).suffix.lower()
    if ext and ext not in EXT_OK:
        return _alerta("formato", f"Formato no válido en «{nom}» (se espera PDF o imagen)", cat="")
    if a.get("tamano") == 0:
        return _alerta("formato", f"Archivo vacío: «{nom}»", cat="")
    if a.get("protegido"):
        return _alerta("formato", f"PDF protegido con clave: «{nom}» — solicitar clave al remitente", cat="")
    return None


def validar_documentos(tipo, archivos, exento_afp=False, ahora=None, base_dir=None):
    """Evalúa completitud + vigencia + formato. Nunca pide docs del perfil contrario."""
    ahora = ahora or datetime.now(timezone.utc)
    tipo = (tipo or "dependiente").lower().strip() or "dependiente"
    por_cat = {}
    cats = set()
    alertas = []
    for a in archivos or []:
        cat = fsvc.cat_de_archivo(a.get("nombre") or "", a.get("subfolder") or "")
        if cat in CATS_IGNORAR:
            continue
        cats.add(cat)
        por_cat.setdefault(cat, []).append(a)
        fmt = _formato_archivo(a)
        if fmt:
            alertas.append(fmt)

    req = cats_requeridas(tipo, exento_afp=exento_afp)
    criterios = []
    cats_faltantes = []

    for cat in req:
        presentes = por_cat.get(cat, [])
        label = LABELS.get(cat, cat)
        if cat == "liquidacion":
            ok, al = _vigencia_mensual(
                presentes, LIQ_MESES, "liquidaciones de sueldo",
                "liquidación de sueldo", ahora, base_dir=base_dir)
            alertas.extend(al)
            criterios.append({"nombre": label, "ok": ok, "cat": cat})
            if not ok:
                cats_faltantes.append(cat)
        elif cat == "afp":
            # Un certificado AFP de 12/24 meses cubre el período; solo se exige
            # mes a mes si hay una serie de archivos con mes en el nombre/PDF.
            parsed = [_periodo_archivo(a, ahora, base_dir) for a in presentes]
            parsed = [p for p in parsed if p]
            if presentes and len(parsed) < 2:
                ok = True
                criterios.append({"nombre": label, "ok": True, "cat": cat})
            else:
                ok, al = _vigencia_mensual(
                    presentes, AFP_MESES, "cotizaciones previsionales AFP",
                    "cotización previsional", ahora, base_dir=base_dir)
                alertas.extend(al)
                criterios.append({"nombre": label, "ok": ok, "cat": cat})
                if not ok:
                    cats_faltantes.append(cat)
        elif cat == "cmf":
            ok, al = _vigencia_cmf(presentes, ahora)
            alertas.extend(al)
            criterios.append({"nombre": label, "ok": ok, "cat": cat})
            if not ok:
                cats_faltantes.append(cat)
        else:
            ok = bool(presentes)
            criterios.append({"nombre": label, "ok": ok, "cat": cat})
            if not ok:
                cats_faltantes.append(cat)
                alertas.append(_alerta("faltante", f"Falta {label}", cat=cat))

    nombres = " ".join((a.get("nombre") or "") for a in (archivos or []))
    if tipo in ("independiente", "mixto"):
        tiene_f29 = bool(RX_F29.search(nombres))
        tiene_carpeta = bool(RX_F22.search(nombres) and "carpeta" in nombres.lower())
        if not tiene_f29 and not tiene_carpeta:
            alertas.append(_alerta(
                "recomendado",
                "Falta formulario F29 (pago provisional mensual)",
                cat="f29"))
        if tipo == "independiente" and not RX_DAI.search(nombres) and "boletas" not in cats:
            pass  # ya cubierto por cat boletas
    if tipo in ("dependiente", "mixto") and "contrato" not in cats and not RX_CONTRATO.search(nombres):
        alertas.append(_alerta(
            "recomendado",
            "Falta contrato de trabajo",
            cat="contrato"))

    completo = not any(a["nivel"] == "faltante" for a in alertas)
    return {
        "tipo": tipo,
        "exento_afp": bool(exento_afp),
        "cats_presentes": sorted(cats),
        "cats_faltantes": cats_faltantes,
        "criterios": criterios,
        "alertas": alertas,
        "completo": completo,
    }


def validar_folder(doc, archivos=None):
    cr = (doc or {}).get("credit_request") or {}
    nombre = (doc or {}).get("nombre") or ""
    if archivos is None:
        archivos = fsvc.scan_archivos(nombre)
    return validar_documentos(
        cr.get("client_type") or "dependiente",
        archivos,
        exento_afp=bool(cr.get("exento_afp")),
        base_dir=str(fsvc.folder_dir(nombre)),
    )


def textos_faltantes(val):
    """Mensajes específicos para chips, correos y panel de estado."""
    return [a["mensaje"] for a in (val or {}).get("alertas") or []
            if a.get("nivel") in ("faltante", "vigencia")]


def snapshot_publico(val):
    return {
        "tipo": val.get("tipo"),
        "cats_faltantes": val.get("cats_faltantes") or [],
        "alertas": val.get("alertas") or [],
        "completo": bool(val.get("completo")),
    }
