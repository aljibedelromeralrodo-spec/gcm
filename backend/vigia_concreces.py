"""Vigía matemático — aprende la política REAL desde cartas de
aprobaciones@centralmutuos.cl (aprobación, rechazo, simulación).

No toca la POLITICA_BASE. Solo observa cortes empíricos y arma alertas
del tipo: BASE dice 40% con sub, REAL corta en 38,5%.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from concreces_perfecto import POLITICA_BASE, UF_RESPALDO, _n


def _num_cl(s):
    if s is None or s == "":
        return None
    t = str(s).strip().replace(" ", "").replace("$", "").replace("%", "")
    t = t.replace("UF", "").replace("uf", "")
    if not t:
        return None
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")
    elif t.count(".") > 1:
        t = t.replace(".", "")
    elif t.count(".") == 1:
        izq, der = t.split(".")
        if izq.isdigit() and len(der) == 3:
            t = izq + der
    elif "," in t:
        t = t.replace(",", ".")
    try:
        v = float(t)
        return v if v == v else None
    except ValueError:
        return None


def _pct(s):
    v = _num_cl(s)
    if v is None:
        return None
    return v / 100.0 if v > 1.5 else v


def _rx(pat, texto, flags=re.I):
    m = re.search(pat, texto or "", flags)
    return m


def parse_liquidacion(texto):
    """Líquido a pagar (y haberes/viáticos si vienen) desde una liquidación."""
    t = texto or ""
    liq = None
    for pat in (
        r"l[ií]quido\s*a\s*pagar[^\d$]{0,40}(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d{5,})",
        r"total\s*l[ií]quido[^\d$]{0,30}(\d{1,3}(?:\.\d{3})+|\d{5,})",
        r"neto\s*a\s*pago[^\d$]{0,30}(\d{1,3}(?:\.\d{3})+|\d{5,})",
    ):
        m = _rx(pat, t)
        if m:
            liq = _num_cl(m.group(1))
            if liq and liq > 50_000:
                break
            liq = None
    hab = None
    m = _rx(r"no\s*imponibles?[^\d$]{0,30}(\d{1,3}(?:\.\d{3})+|\d{4,})", t)
    if m:
        hab = _num_cl(m.group(1))
    viat = None
    m = _rx(r"vi[aá]ticos?[^\d$]{0,30}(\d{1,3}(?:\.\d{3})+|\d{4,})", t)
    if m:
        viat = _num_cl(m.group(1))
    return {"liquido": liq, "haberes": hab, "viaticos": viat}


def parse_carta(texto, nombre=""):
    """Extrae monto UF, tasa, dividendo, seguros, div/renta, carga y veredicto."""
    t = texto or ""
    low = t.lower()
    nombre_l = (nombre or "").lower()

    resultado = "desconocido"
    if re.search(r"rechaz|no\s+ha\s+sido\s+aprob|no\s+corresponde\s+aprobar", low):
        resultado = "rechazado"
    elif re.search(r"agrado\s+de\s+informar|ha\s+sido\s+aprobad|carta\s+de\s+aprobaci|"
                   r"pre-?aprob|aprobaci[oó]n\s+preliminar|se\s+aprueba", low):
        resultado = "aprobado"
    elif re.search(r"simulaci[oó]n", low) or "simulac" in nombre_l:
        resultado = "simulacion"
    if "rechaz" in nombre_l:
        resultado = "rechazado"
    if re.search(r"aprobaci", nombre_l) and resultado == "desconocido":
        resultado = "aprobado"

    def _cap(pats):
        for p in pats:
            m = _rx(p, t)
            if m:
                v = _num_cl(m.group(1))
                if v is not None:
                    return v
        return None

    monto_uf = _cap((
        r"monto(?:\s+del)?\s+cr[eé]dito[^\d]{0,40}(?:UF|U\.F\.)\s*[:\s]*([\d.]+(?:,\d+)?)",
        r"(?:UF|U\.F\.)\s*[:\s]*([\d.]+(?:,\d+)?)\s*(?:de\s+)?(?:cr[eé]dito|monto)",
        r"cr[eé]dito(?:\s+aprobado)?[^\d]{0,25}(?:UF|U\.F\.)\s*[:\s]*([\d.]+(?:,\d+)?)",
        r"monto\s*(?:UF|U\.F\.)\s*[:\s]*([\d.]+(?:,\d+)?)",
    ))
    valor_uf = _cap((
        r"valor(?:\s+de)?(?:\s+la)?\s+(?:propiedad|vivienda|inmueble)[^\d]{0,30}(?:UF|U\.F\.)\s*[:\s]*([\d.]+(?:,\d+)?)",
        r"(?:propiedad|vivienda)[^\d]{0,20}(?:UF|U\.F\.)\s*[:\s]*([\d.]+(?:,\d+)?)",
    ))
    tasa = _cap((
        r"tasa(?:\s+anual)?[^\d]{0,20}([\d]+(?:[.,]\d+)?)\s*%",
        r"([\d]+(?:[.,]\d+)?)\s*%\s*(?:anual|tasa)",
    ))
    if tasa is not None and tasa > 1.5:
        tasa = tasa / 100.0
    div = _cap((
        r"dividendo(?:\s+total)?[^\d$]{0,30}\$?\s*([\d.]+(?:,\d+)?)",
        r"cuota(?:\s+mensual)?[^\d$]{0,20}\$?\s*([\d.]+(?:,\d+)?)",
    ))
    desg = _cap((
        r"desgravamen[^\d$]{0,30}\$?\s*([\d.]+(?:,\d+)?)",
        r"seg(?:uro)?\.?\s*desg[^\d$]{0,20}\$?\s*([\d.]+(?:,\d+)?)",
    ))
    inc = _cap((
        r"incendio[^\d$]{0,30}\$?\s*([\d.]+(?:,\d+)?)",
        r"seg(?:uro)?\.?\s*inc[^\d$]{0,20}\$?\s*([\d.]+(?:,\d+)?)",
    ))
    div_renta = None
    m = _rx(r"(?:div(?:idendo)?\s*/\s*renta|relaci[oó]n\s+dividendo)[^\d]{0,20}([\d]+(?:[.,]\d+)?)\s*%", t)
    if m:
        div_renta = _pct(m.group(1))
    carga = None
    m = _rx(r"carga(?:\s+financiera)?[^\d]{0,20}([\d]+(?:[.,]\d+)?)\s*%", t)
    if m:
        carga = _pct(m.group(1))
    pie = None
    m = _rx(r"\bpie\b[^\d]{0,15}([\d]+(?:[.,]\d+)?)\s*%", t)
    if m:
        pie = _pct(m.group(1))
    sub = None
    if re.search(r"con\s+subsidio|ds1\b|ds19\b|subsidio\s+habitacional", low):
        sub = True
    elif re.search(r"sin\s+subsidio", low):
        sub = False

    return {
        "resultado": resultado,
        "monto_uf": monto_uf,
        "valor_uf": valor_uf,
        "tasa": tasa,
        "dividendo_total": div,
        "seguro_desgravamen": desg,
        "seguro_incendio": inc,
        "div_renta": div_renta,
        "carga": carga,
        "pie": pie,
        "con_subsidio": sub,
        "nombre": nombre or "",
    }


def _p95(vals):
    xs = sorted(v for v in vals if v is not None)
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    i = int(round(0.95 * (len(xs) - 1)))
    return xs[min(i, len(xs) - 1)]


def _media(vals):
    xs = [v for v in vals if v is not None and v > 0]
    return (sum(xs) / len(xs)) if xs else None


def aprender(casos, uf=UF_RESPALDO):
    """Cortes empíricos de las últimas cartas. Separa con/sin subsidio."""
    casos = list(casos or [])
    uf = _n(uf, UF_RESPALDO) or UF_RESPALDO
    out = {"n": len(casos), "con_subsidio": {}, "sin_subsidio": {},
           "factores": {}, "listo": False}

    def _stats(grupo):
        ap = [c for c in grupo if c.get("resultado") == "aprobado"]
        rz = [c for c in grupo if c.get("resultado") == "rechazado"]
        ult20 = ap[-20:]
        divs = [c.get("div_renta") for c in ult20]
        cargas = [c.get("carga") for c in ult20]
        pies = [c.get("pie") for c in ult20]
        vals = [c.get("valor_uf") for c in ult20]
        montos = [c.get("monto_uf") for c in ult20]
        div_max = _p95(divs)
        carga_max = _p95(cargas)
        corte_div = max(divs) if any(x is not None for x in divs) else None
        if divs and all(x is None for x in divs):
            corte_div = None
        if ult20:
            corte_div = max((d for d in divs if d is not None), default=None)
            corte_carga = max((d for d in cargas if d is not None), default=None)
        else:
            corte_div = corte_carga = None
        n_rz_div = 0
        if corte_div is not None:
            n_rz_div = sum(1 for c in rz
                           if c.get("div_renta") is not None and c["div_renta"] > corte_div - 1e-9)
        n_rz_carga = 0
        if corte_carga is not None:
            n_rz_carga = sum(1 for c in rz
                             if c.get("carga") is not None and c["carga"] > corte_carga - 1e-9)
        return {
            "n_aprobadas": len(ap),
            "n_rechazadas": len(rz),
            "n_ventana": len(ult20),
            "div_max_real": round(corte_div, 4) if corte_div is not None else None,
            "carga_max_real": round(corte_carga, 4) if corte_carga is not None else None,
            "div_p95": round(div_max, 4) if div_max is not None else None,
            "carga_p95": round(carga_max, 4) if carga_max is not None else None,
            "valor_min_real": min((v for v in vals if v), default=None),
            "valor_max_real": max((v for v in vals if v), default=None),
            "monto_max_real": max((v for v in montos if v), default=None),
            "pie_min_real": min((p for p in pies if p is not None), default=None),
            "rechazos_sobre_div": n_rz_div,
            "rechazos_sobre_carga": n_rz_carga,
        }

    pool_con = [c for c in casos if c.get("con_subsidio") is True]
    pool_sin = [c for c in casos if c.get("con_subsidio") is False]
    # Cartas sin marca de subsidio alimentan ambos cortes con menos peso (ventana propia).
    neutras = [c for c in casos if c.get("con_subsidio") is None]
    out["con_subsidio"] = _stats(pool_con or (casos if not pool_sin else pool_con + neutras))
    out["sin_subsidio"] = _stats(pool_sin or (casos if not pool_con else pool_sin + neutras))

    factores_desg, factores_inc = [], []
    for c in casos:
        monto_clp = None
        if c.get("monto_uf") and uf:
            monto_clp = c["monto_uf"] * uf
        if c.get("seguro_desgravamen") and monto_clp:
            factores_desg.append(c["seguro_desgravamen"] / monto_clp)
        if c.get("seguro_incendio") and c.get("valor_uf") and uf:
            factores_inc.append(c["seguro_incendio"] / (c["valor_uf"] * uf))
        elif c.get("seguro_incendio") and monto_clp:
            factores_inc.append(c["seguro_incendio"] / monto_clp)
    out["factores"] = {
        "factor_desg_real": round(_media(factores_desg), 6) if _media(factores_desg) else None,
        "factor_inc_real": round(_media(factores_inc), 6) if _media(factores_inc) else None,
        "n_desg": len(factores_desg),
        "n_inc": len(factores_inc),
    }
    out["listo"] = (out["con_subsidio"].get("n_aprobadas", 0) +
                    out["sin_subsidio"].get("n_aprobadas", 0)) >= 3
    out["actualizado"] = datetime.now(timezone.utc).isoformat()
    return out


def comparar(real, base=None):
    """Alertas POLITICA_BASE vs cortes aprendidos."""
    base = base or POLITICA_BASE
    real = real or {}
    alertas = []
    pares = (
        ("con_subsidio", "con subsidio",
         base["con_subsidio"]["div_renta_max"], base["con_subsidio"]["carga_max"]),
        ("sin_subsidio", "sin subsidio",
         base["sin_subsidio"]["div_renta_max"], base["sin_subsidio"]["carga_max"]),
    )
    for key, label, div_base, carga_base in pares:
        bloque = real.get(key) or {}
        div_real = bloque.get("div_max_real")
        n = bloque.get("n_ventana") or 0
        rz = bloque.get("rechazos_sobre_div") or 0
        if div_real is not None and n >= 3 and div_real + 1e-9 < div_base:
            alertas.append({
                "campo": "div_renta",
                "subsidio": key,
                "txt": (f"BASE dice div {div_base * 100:.0f}% {label}, pero REAL últimas {n} "
                        f"aprobaciones corta en {div_real * 100:.1f}%"
                        + (f" — {rz} rechazos {div_real * 100:.0f}%+" if rz else "")),
            })
        carga_real = bloque.get("carga_max_real")
        rzc = bloque.get("rechazos_sobre_carga") or 0
        if carga_real is not None and n >= 3 and carga_real + 1e-9 < carga_base:
            alertas.append({
                "campo": "carga",
                "subsidio": key,
                "txt": (f"BASE dice carga {carga_base * 100:.0f}% {label}, pero REAL últimas {n} "
                        f"aprobaciones corta en {carga_real * 100:.1f}%"
                        + (f" — {rzc} rechazos {carga_real * 100:.0f}%+" if rzc else "")),
            })
        pie_real = bloque.get("pie_min_real")
        pie_base = base[key].get("pie_min", 0.20)
        if pie_real is not None and n >= 3 and pie_real > pie_base + 1e-9:
            alertas.append({
                "campo": "pie",
                "subsidio": key,
                "txt": (f"BASE dice pie {pie_base * 100:.0f}% {label}, pero REAL pide "
                        f"{pie_real * 100:.1f}%"),
            })
    return alertas


def evolucion(casos, limite=40):
    out = []
    for c in (casos or [])[-limite:]:
        out.append({
            "fecha": c.get("fecha") or "",
            "resultado": c.get("resultado"),
            "div_renta": c.get("div_renta"),
            "carga": c.get("carga"),
            "monto_uf": c.get("monto_uf"),
            "con_subsidio": c.get("con_subsidio"),
        })
    return out
