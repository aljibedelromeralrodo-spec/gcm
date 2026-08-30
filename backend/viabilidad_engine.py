"""Viabilidad interna (Mutuaria / sector mutuo) vs Espejo Concreces (mesa).

No reescribe la amortización ni el techo de `credit_engine`. Combina:
  1) reglas internas + documentos + LTV/carga (probabilidad Mutuaria);
  2) tope aprendido de aprobaciones reales de mesa (Espejo Concreces);
  3) discrepancia de riesgo entre ambos, para no enviar a mesa lo que el
     sector mutuo ve viable y Concreces suele rechazar.
"""
from __future__ import annotations

import folders_service as fsvc
import credit_engine as ce


def _quiebres_hierro(doc):
    import mesa_brain
    return mesa_brain.quiebres_hierro_folder(doc)

# Regla #63 (credit_engine.LTV_MAX_63) — se lee al vuelo para no desfasar.
try:
    LTV_TOPE = float(getattr(ce, "LTV_MAX_63", 0.795) or 0.795)
except (TypeError, ValueError):
    LTV_TOPE = 0.795


def _n(v):
    try:
        if isinstance(v, str):
            v = v.replace(".", "").replace(",", ".")
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _features_espejo(doc, uf_valor):
    df = (doc or {}).get("datos_financieros") or {}
    endeud = ce.endeudamiento_mensual(df, uf_valor or 0)
    edad = int(_n(df.get("edad")))
    cod = ((doc or {}).get("codeudor_nombre") or "").strip()
    nom = ((doc or {}).get("nombre") or "")
    if not cod:
        cod_tipo = "ninguno"
    else:
        ap_t = set(nom.lower().split()[1:])
        ap_c = set(cod.lower().split()[1:])
        cod_tipo = "familiar" if (ap_t & ap_c) else "tercero"
    return {
        "renta_liquida_clp": _n(df.get("renta_liquida")),
        "renta_codeudor_clp": _n(df.get("renta_codeudor")),
        "endeudamiento_mensual_clp": (endeud or {}).get("endeudamiento_mensual_clp", 0),
        "con_subsidio": bool(df.get("con_subsidio")),
        "con_codeudor": bool(cod),
        "codeudor_tipo": cod_tipo,
        "edad_bucket": "s/i" if edad <= 0 else ("<40" if edad < 40 else ("40_59" if edad < 60 else "60+")),
        "edad_mayor_60": edad >= 60,
    }


def viabilidad_interna(doc, stats, archivos=None):
    """Probabilidad Mutuaria / sector mutuo. Hierro y docs mínimos siguen mandando."""
    quiebres = _quiebres_hierro(doc)
    if quiebres:
        factores = ["⛔ 0%: NO VIABLE - POLÍTICA GENERAL (Regla de Hierro quebrada)"]
        factores += [f"⛔ {q['detalle']}" for q in quiebres]
        return {
            "origen": "mutuaria",
            "porcentaje": 0,
            "factores": factores,
            "alerta_critica": "NO VIABLE - POLÍTICA GENERAL: " +
                              "; ".join(q["regla"] for q in quiebres),
        }
    stats = stats or {}
    base = float(stats.get("base") or 0.85)
    prob = base * 100.0
    factores = [f"Base mesa: {round(base * 100)}% ({stats.get('aprobadas', 0)} aprobadas / {stats.get('rechazadas', 0)} rechazadas)"]
    if archivos is None:
        archivos = fsvc.scan_archivos((doc or {}).get("nombre") or "")
    cats = {fsvc.cat_de_archivo(a["nombre"], a.get("subfolder")) for a in archivos} - {
        "combinado", "codeudor", "estudio_titulo"}
    cr = (doc or {}).get("credit_request") or {}
    tipo = cr.get("client_type") or "dependiente"
    exento = bool(cr.get("exento_afp"))
    requeridos = [c for c in fsvc.required_cats(tipo, exento_afp=exento) if c != "cmf"]
    faltan = [c for c in requeridos if c not in cats]
    if faltan:
        prob -= 8 * len(faltan)
        factores.append(f"-{8 * len(faltan)}%: faltan documentos clave ({', '.join(faltan)})")
    if "cmf" not in cats:
        prob -= 5
        factores.append("-5%: falta informe CMF")
    df = (doc or {}).get("datos_financieros") or {}
    monto = _n(df.get("monto_credito"))
    valor = _n(df.get("valor_propiedad"))
    if monto:
        if monto <= 2000:
            prob += 4
            factores.append("+4%: monto acotado (≤2.000 UF)")
        elif monto > 4000:
            prob -= 8
            factores.append("-8%: monto alto (>4.000 UF)")
    con_sub = df.get("con_subsidio")
    if con_sub is None:
        con_sub = (cr.get("subsidy") or {}).get("tipo") == "con_subsidio"
    if con_sub:
        prob += 5
        factores.append("+5%: con subsidio")
    alerta_critica = ""
    if monto and monto < 2000 and not con_sub:
        alerta_critica = "ALERTA: No cumple criterio mínimo de 2.000 UF. Avisar a jefatura"
        prob = min(prob, 10)
        factores.append(f"🔴 {alerta_critica}")
    if tipo == "independiente":
        prob -= 5
        factores.append("-5%: independiente (boletas)")
    if not valor:
        prob -= 3
        factores.append("-3%: sin datos financieros completos")
    if monto and valor:
        ltv = monto / valor
        if ltv <= LTV_TOPE:
            prob += 6
            factores.append(f"+6%: LTV {ltv * 100:.1f}% dentro de Regla #63 ({LTV_TOPE * 100:.1f}%)")
        elif ltv <= 0.90:
            prob -= 4
            factores.append(f"-4%: LTV {ltv * 100:.1f}% sobre 79,5% (Regla #63)")
        else:
            prob -= 14
            factores.append(f"-14%: LTV {ltv * 100:.1f}% — Mesa suele rechazar sobre 90%")
    renta = _n(df.get("renta_liquida"))
    uf = _n(df.get("valor_uf")) or float(getattr(ce, "UF_SII_CACHE", {}).get("v") or 0)
    if renta > 0 and monto > 0 and uf > 0:
        try:
            endeud = ce.endeudamiento_mensual(df, uf)
            carga = (endeud.get("endeudamiento_mensual_clp") or 0) / renta
            if carga <= 0.28:
                prob += 8
                factores.append(f"+8%: carga actual {carga * 100:.0f}% de la renta")
            elif carga <= 0.40:
                prob += 2
                factores.append(f"+2%: carga actual {carga * 100:.0f}% (tope 40%)")
            else:
                prob -= 16
                factores.append(f"-16%: carga actual {carga * 100:.0f}% supera el 40% DashAI")
        except Exception:
            pass
    faltan_mesa = [c for c in fsvc.required_cats(tipo, exento_afp=exento) if c not in cats]
    if not cats or faltan_mesa:
        etiquetas = [fsvc.MISSING_LABELS.get(c, c) for c in faltan_mesa] or ["sin documentos"]
        factores.append("⛔ 0%: no cumple criterios de envío a mesa (faltan: " + ", ".join(etiquetas) + ")")
        return {"origen": "mutuaria", "porcentaje": 0, "factores": factores,
                "alerta_critica": alerta_critica}
    return {"origen": "mutuaria", "porcentaje": max(5, min(98, round(prob))),
            "factores": factores, "alerta_critica": alerta_critica}


def probabilidad_concreces(doc, modelo_espejo, uf_valor=None):
    """P(Concreces/mesa aprueba) según tope aprendido vs monto pedido."""
    modelo_espejo = modelo_espejo or {}
    uf_valor = uf_valor or float(getattr(ce, "UF_SII_CACHE", {}).get("v") or 0)
    if not modelo_espejo.get("listo"):
        return {"origen": "concreces", "disponible": False, "porcentaje": None,
                "nota": modelo_espejo.get("nota") or "Espejo Concreces en calibración (re-entrena cada 24h)"}
    if not uf_valor:
        return {"origen": "concreces", "disponible": False, "porcentaje": None,
                "nota": "UF SII no disponible — no se proyecta el Espejo"}
    features = _features_espejo(doc, uf_valor)
    espejo = ce.simular_como_mesa(features, modelo_espejo)
    if not espejo.get("disponible"):
        return {"origen": "concreces", "disponible": False, "porcentaje": None,
                "nota": espejo.get("nota") or "Espejo sin segmento",
                "precision_pct": espejo.get("precision_pct"), "n": espejo.get("n")}
    tope = float(espejo.get("monto_uf") or 0)
    monto = _n(((doc or {}).get("datos_financieros") or {}).get("monto_credito"))
    if tope <= 0:
        return {"origen": "concreces", "disponible": False, "porcentaje": None,
                "nota": "Espejo sin tope UF en el segmento"}
    if monto <= 0:
        prec = int(espejo.get("precision_pct") or 50)
        return {"origen": "concreces", "disponible": True, "porcentaje": max(20, min(80, prec)),
                "monto_espejo_uf": tope, "monto_solicitado_uf": 0,
                "precision_pct": espejo.get("precision_pct"), "n": espejo.get("n"),
                "segmento": espejo.get("segmento"),
                "nota": "Sin monto solicitado: se informa tope Espejo, no P(aprobación) del crédito"}
    ratio = monto / tope
    if ratio <= 0.85:
        pct, det = 84, "monto bajo el tope Espejo Concreces"
    elif ratio <= 1.00:
        pct, det = 70, "monto en el borde del tope Espejo Concreces"
    elif ratio <= 1.15:
        pct, det = 38, "monto hasta 15% sobre el tope Espejo — Mesa suele recortar"
    else:
        pct, det = 16, "monto claramente sobre lo que Concreces aprueba en este segmento"
    prec = float(espejo.get("precision_pct") or 50)
    pct = round(pct * 0.75 + prec * 0.25)
    return {
        "origen": "concreces", "disponible": True,
        "porcentaje": max(5, min(95, pct)),
        "monto_espejo_uf": round(tope, 1),
        "monto_solicitado_uf": round(monto, 1),
        "ratio": round(ratio, 3),
        "detalle": det,
        "precision_pct": espejo.get("precision_pct"),
        "n": espejo.get("n"),
        "segmento": espejo.get("segmento"),
    }


def discrepancia(interna, concreces, techo_uf=None):
    """Brecha Mutuaria (sector mutuo) vs Espejo Concreces (evaluador final)."""
    interna = interna or {}
    concreces = concreces or {}
    if not concreces.get("disponible") or concreces.get("porcentaje") is None:
        return {"hay": False, "puntos": 0, "nivel": "sin_espejo",
                "mensaje": concreces.get("nota") or "Espejo Concreces aún no calibra este caso"}
    p_m = int(interna.get("porcentaje") or 0)
    p_c = int(concreces.get("porcentaje") or 0)
    d = p_m - p_c
    techo = _n(techo_uf)
    tope = _n(concreces.get("monto_espejo_uf"))
    extra = ""
    if techo > 0 and tope > 0 and techo > tope * 1.15:
        extra = f" Techo Mutuaria {techo:.0f} UF vs tope Concreces {tope:.0f} UF."
    if abs(d) < 15:
        return {"hay": False, "puntos": d, "nivel": "alineados",
                "mensaje": f"Mutuaria {p_m}% y Concreces {p_c}% alineados.{extra}".strip()}
    if d >= 25:
        return {"hay": True, "puntos": d, "nivel": "alerta",
                "mensaje": (f"Mutuaria {p_m}% vs Concreces {p_c}%: el sector mutuo ve más viable "
                            f"de lo que el Espejo de mesa proyecta — riesgo de rechazo.{extra}")}
    if d >= 15:
        return {"hay": True, "puntos": d, "nivel": "aviso",
                "mensaje": (f"Mutuaria {p_m}% vs Concreces {p_c}%: sesgo optimista interno.{extra}")}
    return {"hay": True, "puntos": d, "nivel": "aviso",
            "mensaje": (f"Concreces {p_c}% vs Mutuaria {p_m}%: Mesa podría aprobar más "
                        f"de lo que el criterio interno estima.{extra}")}


def evaluar_folder(doc, stats, modelo_espejo=None, uf_valor=None, techo_uf=None, archivos=None):
    """Resultado dual. `porcentaje` = Mutuaria (compatible con la tarjeta actual)."""
    interna = viabilidad_interna(doc, stats, archivos=archivos)
    concreces = probabilidad_concreces(doc, modelo_espejo, uf_valor=uf_valor)
    disc = discrepancia(interna, concreces, techo_uf=techo_uf)
    out = {
        "porcentaje": interna["porcentaje"],
        "factores": list(interna.get("factores") or []),
        "alerta_critica": interna.get("alerta_critica") or "",
        "mutuaria": {"porcentaje": interna["porcentaje"], "factores": interna.get("factores") or []},
        "concreces": concreces,
        "discrepancia": disc,
    }
    if disc.get("hay") and disc.get("mensaje"):
        out["factores"].append("🪞 " + disc["mensaje"])
    return out
