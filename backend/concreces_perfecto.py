"""Concreces Motor V7 — POLITICA MADRE REAL + checklist 412 + LTV trunc.

LTV duro 79,50% a 10 decimales, display truncado a 2. Tasas: 6,5% ≤2000 UF
con sub / 6,35% >2000 / 5,9% sin sub. Carga = (div + CMF×2%) / renta.
Checklist 412: docs por perfil + fecha_entrega + ejec_interno + RUT Ivana.
"""
from __future__ import annotations

import re

# Respaldo del 29-08-2026: vendedor en terreno sin señal.
UF_RESPALDO = 40871.14
UF_RESPALDO_FECHA = "2026-08-29"
LTV_DURO = 0.795  # 79,50% — tope de hierro, no el 80% genérico
CF_PCT_CMF = 0.02  # cuota teórica CMF = 2% del stock

# ── POLÍTICA MADRE (constante — 100% la tabla validada) ────────
POLITICA_BASE = {
    "con_subsidio": {
        "vivienda": "Nuevas-Usadas",
        "inmueble": "casas-Departamentos",
        "destino": "Habitacional",
        "valor_min_uf": 1000,
        "valor_max_uf": 4000,
        "financ_max": LTV_DURO,
        "ltv_duro": LTV_DURO,
        "monto_max_uf": 3200,
        "monto_min_uf": 800,
        "pie_min": 0.20,
        "plazo_min": 20,
        "plazo_max": 40,
        "plazo_menor": "comite excepcion",
        "div_renta_max": 0.40,
        "carga_max": 0.55,
        "renta_min_titular_uf": 15,
        "renta_min_conjunta_uf": 25,
        "edad_min": 21,
        "edad_max_ingreso": 65,
        "edad_max_termino": 79.99,
        "antig_indefinido_m": 3,
        "antig_plazo_obra_m": 6,
        "antig_independiente_m": 36,
        "cont_indefinido_m": 6,
        "cont_obra_m": 12,
        "haberes_max_clp": 200000,
        "viaticos_max": 0.50,
        "tasa_hasta_2000": 6.5,
        "tasa_mas_2000": 6.35,
    },
    "sin_subsidio": {
        "vivienda": "Nuevas-Usadas",
        "inmueble": "casas-Departamentos",
        "destino": "Habitacional",
        "valor_min_uf": 1250,
        "valor_max_uf": 5000,
        "financ_max": LTV_DURO,
        "ltv_duro": LTV_DURO,
        "monto_max_uf": 4000,
        "monto_min_uf": 1000,
        "pie_min": 0.20,
        "plazo_min": 20,
        "plazo_max": 30,
        "plazo_menor": "comite excepcion",
        "div_renta_max": 0.35,
        "carga_max": 0.50,
        "renta_min_titular_uf": 25,
        "renta_min_conjunta_uf": 25,
        "edad_min": 21,
        "edad_max_ingreso": 65,
        "edad_max_termino": 79.99,
        "antig_indefinido_m": 6,
        "antig_plazo_obra_m": 6,
        "antig_independiente_m": 36,
        "cont_indefinido_m": 12,
        "cont_obra_m": 24,
        "haberes_max_clp": 200000,
        "viaticos_max": 0.50,
        "codeudor": ("Padres y hermanos. Cónyuge y pareja con hijos en común ratios "
                     "familiares. Directo titular CF máx 70%. Tercero titular CF máx 60% "
                     "y acreditar 50% div/renta"),
        "tasa": 5.9,
    },
    "bloqueos": [
        "Deuda Directa Morosa NO",
        "Deuda Vencida NO",
        "Castigada NO",
        "Indirecta morosa/vencida/castigada NO",
        "Mora Comercial NO",
        "Protestos vigentes NO",
        "Pagares Impagos NO",
        "SAR NO",
    ],
}

SEGUROS_FALLBACK = {"desgravamen": 10245, "incendio": 23702}

_ORDEN = {"APROBADO": 0, "OBSERVADO": 1, "COMITE EXCEPCION": 2, "RECHAZADO": 3,
          "BLOQUEADO": 4, "BLOQUEO 412": 5}

CHECKLIST_412 = {
    "dependiente": ["cedula", "liquidacion", "afp", "cmf"],
    "independiente": ["cedula", "imp_renta", "boletas", "cmf"],
    "mixto": ["cedula", "liquidacion", "afp", "imp_renta", "boletas", "cmf"],
    "jubilado": ["cedula", "renta_vitalicia", "cmf"],
}
LABEL_412 = {
    "cedula": "cédula", "liquidacion": "liquidaciones", "afp": "afp", "cmf": "cmf",
    "imp_renta": "impuesto_renta", "boletas": "boletas", "renta_vitalicia": "renta_vitalicia",
}
EJEC_INTERNOS = ("deisy", "yerile", "gerardo", "deisy salazar", "yerile barrera", "gerardo barrera")
FECHAS_OK = ("inmediata", "futura")


def _n(v, default=0.0):
    if v is None or v == "":
        return float(default)
    if isinstance(v, bool):
        return float(int(v))
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "").replace("$", "")
    if not s:
        return float(default)
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(",") == 1 and s.count(".") == 0:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return float(default)


def _b(v, default=False):
    if isinstance(v, bool):
        return v
    if v is None or v == "":
        return default
    return str(v).strip().lower() in ("1", "true", "si", "sí", "on", "yes")


def _fmt_clp(n):
    return f"${round(n):,}".replace(",", ".")


def politica(con_subsidio, mhe=None, overlay=None):
    """Umbrales internos desde POLITICA_BASE (constante), con overlay opcional."""
    src = dict(POLITICA_BASE["con_subsidio" if con_subsidio else "sin_subsidio"])
    if isinstance(overlay, dict):
        bloq = overlay.get("con_subsidio" if con_subsidio else "sin_subsidio") or overlay
        if isinstance(bloq, dict):
            src.update({k: v for k, v in bloq.items() if v not in (None, "")})
    # Compatibilidad con la Bóveda concreces_mhe (mismos números, otras claves).
    if isinstance(mhe, dict):
        bloque = mhe.get("con_subsidio" if con_subsidio else "sin_subsidio") or {}
        alias = {
            "valor_min_uf": "valor_propiedad_min_uf",
            "valor_max_uf": "valor_propiedad_max_uf",
            "monto_min_uf": "monto_credito_min_uf",
            "monto_max_uf": "monto_credito_max_uf",
            "div_renta_max": "div_renta_max",
            "carga_max": "carga_financiera_max",
            "pie_min": "pie_min",
            "plazo_min": "plazo_min_anos",
            "plazo_max": "plazo_max_anos",
            "financ_max": "ltv_max",
        }
        for dest, origen in alias.items():
            if origen in bloque and bloque[origen] not in (None, "") and dest != "financ_max":
                src[dest] = _n(bloque[origen], src.get(dest, 0))
    src["financ_max"] = min(_n(src.get("financ_max"), LTV_DURO), LTV_DURO)
    src["ltv_duro"] = LTV_DURO
    return {
        "vmin": _n(src["valor_min_uf"]),
        "vmax": _n(src["valor_max_uf"]),
        "mmin": _n(src["monto_min_uf"]),
        "mmax": _n(src["monto_max_uf"]),
        "dmax": _n(src["div_renta_max"]),
        "cmax": _n(src["carga_max"]),
        "rmin_uf": _n(src["renta_min_titular_uf"]),
        "rmin_c_uf": _n(src.get("renta_min_conjunta_uf", src["renta_min_titular_uf"])),
        "amin_i": _n(src["antig_indefinido_m"]),
        "amin_p": _n(src["antig_plazo_obra_m"]),
        "cmin_i": _n(src["cont_indefinido_m"]),
        "cmin_o": _n(src["cont_obra_m"]),
        "pmin": int(_n(src["plazo_min"])),
        "pmax": int(_n(src["plazo_max"])),
        "pie_min": _n(src["pie_min"]),
        "ltv_max": LTV_DURO,
        "ltv_duro": LTV_DURO,
        "hab_max": _n(src.get("haberes_max_clp", 200000)),
        "viat_pct": _n(src.get("viaticos_max", 0.50)),
        "edad_min": int(_n(src["edad_min"])),
        "edad_max": int(_n(src["edad_max_ingreso"])),
        "edad_term": _n(src["edad_max_termino"], 79.99),
        "ind_meses": _n(src["antig_independiente_m"]),
        "src": src,
    }


def renta_depurada(liquidaciones, afp, haberes=0, viaticos=0, exento_afp=False):
    """min(promedio liq × 85%, AFP × 90%), menos exceso de haberes, ×0,5 si viáticos > 50%.
    FFAA/Carabineros (exento_afp) no se cruza con AFP."""
    liqs = [_n(x) for x in (liquidaciones or [])]
    if not liqs:
        liqs = [0.0]
    prom = sum(liqs) / len(liqs)
    afp_val = _n(afp)
    renta = prom * 0.85
    if afp_val > 0 and not exento_afp:
        renta = min(renta, afp_val * 0.90)
    hab = _n(haberes)
    if hab > 200000:
        renta -= (hab - 200000)
    if prom > 0 and _n(viaticos) / prom > 0.50:
        renta *= 0.50
    return max(0.0, renta), prom


def seguros_de(payload, monto_uf, valor_uf, uf, factores=None):
    """Si vienen seguros reales, se usan. Si no, factor aprendido o fallback CLP."""
    p = payload or {}
    desg = _n(p.get("seguro_desgravamen") or p.get("desgravamen"))
    inc = _n(p.get("seguro_incendio") or p.get("incendio"))
    fac = factores or {}
    fuente = "ingresado"
    if desg <= 0:
        fd = fac.get("factor_desg_real")
        if fd:
            desg = round(monto_uf * uf * float(fd))
            fuente = "aprendido"
        else:
            desg = SEGUROS_FALLBACK["desgravamen"]
            fuente = "respaldo"
    if inc <= 0:
        fi = fac.get("factor_inc_real")
        if fi:
            base = (valor_uf or monto_uf) * uf
            inc = round(base * float(fi))
            fuente = "aprendido" if fuente == "aprendido" else fuente
        else:
            inc = SEGUROS_FALLBACK["incendio"]
            if fuente == "ingresado":
                fuente = "respaldo"
    return desg, inc, fuente


def ltv_10(monto, valor):
    """LTV a 10 decimales (tope duro 0.7950000000)."""
    if _n(valor) <= 0:
        return 0.0
    return round(_n(monto) / _n(valor), 10)


def ltv_trunc_pct(ltv10):
    """Display truncado a 2 decimales de porcentaje (79.499 → 79.49, no 79.50)."""
    return int(_n(ltv10) * 10000) / 100.0


def tasa_madre(con_subsidio, monto_uf, tasa_in=None):
    t = _n(tasa_in) if tasa_in not in (None, "") else 0.0
    if t > 0:
        return t * 100.0 if t <= 1 else t
    if con_subsidio:
        return 6.5 if _n(monto_uf) <= 2000 else 6.35
    return 5.9


def _norm_rut(r):
    return re.sub(r"[^0-9kK]", "", str(r or "")).lower()


def checklist_412(payload):
    """Docs por perfil + fecha_entrega + ejec_interno + RUT Ivana. force_incompleto no borra faltantes."""
    p = payload or {}
    tipo = str(p.get("client_type") or p.get("actividad") or "dependiente").strip().lower()
    sub = _b(p.get("con_subsidio"), True)
    exento = _b(p.get("exento_afp"))
    faltan = []
    if tipo == "sin_evidencia":
        faltan.append("clasificación de perfil (SIN_EVIDENCIA)")
    if tipo == "jubilado" and not sub:
        faltan.append("jubilado solo con_subsidio=true")
    req = list(CHECKLIST_412.get(tipo) or CHECKLIST_412["dependiente"])
    if exento and "afp" in req:
        req.remove("afp")
    docs = p.get("docs") or p.get("documentos") or []
    docs_l = {str(d).lower().strip() for d in docs}
    for c in req:
        aliases = {c, LABEL_412.get(c, c), c.replace("_", "")}
        if not (docs_l & aliases):
            faltan.append(LABEL_412.get(c, c))
    fe = str(p.get("fecha_entrega") or "").strip().lower()
    if fe not in FECHAS_OK:
        faltan.append("fecha_entrega (Inmediata/Futura)")
    ej = str(p.get("ejec_interno") or p.get("ejecutivo_interno") or "").strip().lower()
    if not any(x in ej for x in ("deisy", "yerile", "gerardo")):
        faltan.append("ejec_interno (Deisy/Yerile/Gerardo)")
    if len(_norm_rut(p.get("rut_titular") or p.get("rut"))) < 7:
        faltan.append("rut_titular (Regla Ivana)")
    return faltan


def pmt_dividendo(monto_uf, tasa, plazo, uf):
    """PMT de la POLITICA MADRE: i = tasa%/12 (nominal), sobre monto en CLP."""
    tasa_pct = _n(tasa)
    if 0 < tasa_pct <= 1:
        tasa_pct *= 100.0
    if tasa_pct <= 0:
        tasa_pct = 6.35
    i = tasa_pct / 100.0 / 12.0
    n = int(_n(plazo) or 0) * 12
    m = _n(monto_uf) * _n(uf)
    if n <= 0 or m <= 0:
        return 0.0
    if i <= 0:
        return m / n
    return m * (i * (1 + i) ** n) / ((1 + i) ** n - 1)


def evaluar(payload, uf=None, mhe=None, real=None, overlay=None, factores=None):
    """Motor V6. Semáforo: APROBADO | RECHAZO | OBSERVADO | BLOQUEADO."""
    p = payload or {}
    uf = _n(uf if uf not in (None, 0, "") else p.get("valor_uf") or p.get("uf"), 0)
    respaldo = False
    if uf <= 0:
        uf = UF_RESPALDO
        respaldo = True

    liqs = p.get("liquidaciones")
    if not liqs:
        keys = ("l1", "l2", "l3", "l4", "l5", "l6")
        if any(k in p for k in keys):
            liqs = [p.get(k, 0) for k in keys]
    exento_afp = _b(p.get("exento_afp"))
    renta_directa = _n(p.get("renta") or p.get("renta_clp") or 0)
    if renta_directa > 0:
        renta_tit, prom = renta_directa, renta_directa
    else:
        renta_tit, prom = renta_depurada(
            liqs, p.get("afp"), p.get("haberes"), p.get("viaticos"), exento_afp=exento_afp)

    sub = _b(p.get("con_subsidio"), True)
    pol = politica(sub, mhe=mhe, overlay=overlay)
    valor = _n(p.get("valor_propiedad_uf") or p.get("valor"))
    monto = _n(p.get("monto_credito_uf") or p.get("monto"))
    plazo = int(_n(p.get("plazo"), 0))
    edad = int(_n(p.get("edad"), 0))
    _antig_in = p.get("antiguedad") if p.get("antiguedad") is not None else p.get("antig")
    _cont_in = p.get("continuidad") if p.get("continuidad") is not None else p.get("cont")
    tiene_antig = _antig_in not in (None, "")
    tiene_cont = _cont_in not in (None, "")
    antig = _n(_antig_in) if tiene_antig else 0
    cont = _n(_cont_in) if tiene_cont else 0
    tasa = tasa_madre(sub, monto, p.get("tasa"))
    deudas_tit = _n(p.get("deudas_titular") if p.get("deudas_titular") is not None else p.get("deudas"))
    deudas_cod = _n(p.get("deudas_codeudor") if p.get("deudas_codeudor") is not None else p.get("deudasCod"))
    renta_cod = _n(p.get("renta_codeudor") if p.get("renta_codeudor") is not None else p.get("rentaCod"))
    tipo = str(p.get("tipo_codeudor") or p.get("tipo") or "sin").strip().lower()
    if tipo in ("none", "ninguno", ""):
        tipo = "sin"
    client_type = str(p.get("client_type") or p.get("actividad") or "dependiente").strip().lower()
    act = client_type
    if act in ("sin_evidencia", "sinevidencia"):
        act = "sin_evidencia"
    licencia = _b(p.get("licencia_medica"))
    contrato = str(p.get("contrato") or "indefinido").strip().lower()
    if contrato in ("plazo", "plazo_fijo", "plazofijo"):
        contrato = "plazo_fijo"
    if contrato in ("obra", "faena", "obra_faena"):
        contrato = "obra"
    prohib = _b(p.get("deuda_prohibida") or p.get("prohib"))
    bloqueos_on = p.get("bloqueos") or {}
    v_nueva = _b(p.get("vivienda_nueva_usada") if "vivienda_nueva_usada" in p else p.get("vNueva"), True)
    v_casa = _b(p.get("casa_depto") if "casa_depto" in p else p.get("vCasa"), True)
    v_hab = _b(p.get("habitacional") if "habitacional" in p else p.get("vHab"), True)
    nac_ok = _b(p.get("nacionalidad_ok") if "nacionalidad_ok" in p else p.get("nacOk"), True)

    desg, inc, fuente_seg = seguros_de(p, monto, valor, uf, factores)
    div_in = _n(p.get("dividendo") if p.get("dividendo") is not None else p.get("div"))
    div_pmt = pmt_dividendo(monto, tasa, plazo, uf)
    if div_in > 0:
        div = div_in
        div_fuente = "ingresado"
    else:
        div = div_pmt + desg + inc
        div_fuente = "pmt+seguros"

    renta_total = renta_tit + (renta_cod if tipo != "sin" else 0)
    cuota_cmf = (deudas_tit + (deudas_cod if tipo != "sin" else 0)) * CF_PCT_CMF
    carga_tit = (div + deudas_tit * CF_PCT_CMF) / renta_tit if renta_tit > 0 else 99.0
    div_renta_tit = div / renta_tit if renta_tit > 0 else 99.0
    if tipo == "sin":
        renta_eval = renta_tit
        div_renta = div_renta_tit
        carga = carga_tit
    else:
        renta_eval = renta_total
        div_renta = div / renta_eval if renta_eval > 0 else 99.0
        carga = (div + cuota_cmf) / renta_eval if renta_eval > 0 else 99.0

    rmin_uf = pol["rmin_c_uf"] if tipo != "sin" else pol["rmin_uf"]
    rmin_clp = rmin_uf * uf
    if contrato == "indefinido":
        amin_need, cmin_need = pol["amin_i"], pol["cmin_i"]
    elif contrato == "obra":
        amin_need, cmin_need = pol["amin_p"], pol["cmin_o"]
    else:  # plazo fijo
        amin_need, cmin_need = pol["amin_p"], pol["cmin_i"]
    edad_term = edad + plazo
    ltv = ltv_10(monto, valor) if valor > 0 else 99.0
    ltv_pct = ltv_trunc_pct(ltv) if valor > 0 else 0.0
    if p.get("pie") in (None, ""):
        pie = (1.0 - ltv) if valor > 0 else 0.0
    else:
        pie = _n(p.get("pie"), 20)
        if pie > 1:
            pie = pie / 100.0

    estado = "APROBADO"
    chk = []

    def _sube(nuevo):
        nonlocal estado
        if _ORDEN.get(nuevo, 0) > _ORDEN.get(estado, 0):
            estado = nuevo

    def add(ok, txt, acc="", rechazo=False, comite=False, bloqueado=False, motivo=""):
        chk.append({"ok": bool(ok), "txt": txt, "acc": acc or "", "motivo": motivo or ""})
        if ok:
            return
        if bloqueado:
            _sube("BLOQUEADO")
        elif rechazo:
            _sube("RECHAZADO")
        elif comite:
            _sube("COMITE EXCEPCION")
        else:
            _sube("OBSERVADO")

    if licencia:
        add(False, "BLOQUEO licencia médica", bloqueado=True, motivo="BLOQUEO licencia")

    faltan_412 = checklist_412(p)
    force_inc = _b(p.get("force_incompleto"))
    if faltan_412 and not force_inc:
        add(False, "Documentación incompleta — faltan: " + ", ".join(faltan_412),
            bloqueado=True, motivo="BLOQUEO 412 Documentación incompleta — faltan: " + ", ".join(faltan_412))
        _sube("BLOQUEO 412")
    elif faltan_412 and force_inc:
        add(False, "412 con force_incompleto — faltan: " + ", ".join(faltan_412),
            motivo="envío manual incompleto")

    add(v_nueva, "Vivienda Nueva/Usada OK", motivo="" if v_nueva else "Falla Vivienda Nueva-Usadas")
    add(v_casa, "Inmueble Casa/Depto OK", motivo="" if v_casa else "Falla Inmueble casas-Departamentos")
    add(v_hab, "Destino habitacional OK", motivo="" if v_hab else "Falla Destino Habitacional")

    if valor < pol["vmin"]:
        add(False,
            f"Valor {valor:g} UF = {_fmt_clp(valor * uf)} fuera {pol['vmin']:g}-{pol['vmax']:g} UF "
            f"({_fmt_clp(pol['vmin'] * uf)} - {_fmt_clp(pol['vmax'] * uf)})",
            "Ajustar valor de la vivienda", rechazo=True,
            motivo="Valor UF fuera")
    elif valor > pol["vmax"]:
        add(False,
            f"Valor {valor:g} UF = {_fmt_clp(valor * uf)} fuera {pol['vmin']:g}-{pol['vmax']:g} UF "
            f"({_fmt_clp(pol['vmin'] * uf)} - {_fmt_clp(pol['vmax'] * uf)})",
            "Ajustar valor de la vivienda", rechazo=True,
            motivo="Valor UF fuera")
    else:
        add(True, f"Valor {valor:g} UF = {_fmt_clp(valor * uf)} OK")

    if monto < pol["mmin"]:
        add(False, f"Monto {monto:g} UF fuera {pol['mmin']:g}-{pol['mmax']:g} UF",
            "Ajustar monto del crédito", rechazo=True,
            motivo="Monto UF fuera BASE")
    elif monto > pol["mmax"]:
        add(False, f"Monto {monto:g} UF fuera {pol['mmin']:g}-{pol['mmax']:g} UF",
            "Ajustar monto del crédito", rechazo=True,
            motivo="Monto UF fuera BASE")
    else:
        add(True, f"Monto {monto:g} UF = {_fmt_clp(monto * uf)} OK")

    pie_ok = pie + 1e-9 >= pol["pie_min"]
    add(pie_ok, f"Pie {pie * 100:.2f}% {'>=' if pie_ok else '<'} {pol['pie_min'] * 100:.0f}%",
        rechazo=not pie_ok, motivo="" if pie_ok else f"Pie < {pol['pie_min'] * 100:.0f}%")

    ltv_ok = ltv <= round(LTV_DURO, 10) + 1e-12
    add(ltv_ok, f"LTV {ltv_pct:.2f}% (10 dec {ltv:.10f}) {'<=' if ltv_ok else '>'} duro 79.50%",
        rechazo=not ltv_ok, motivo="" if ltv_ok else "LTV supera duro 79.50%")

    if plazo < pol["pmin"] or plazo > pol["pmax"]:
        add(False, f"Plazo {plazo}a fuera {pol['pmin']}-{pol['pmax']}",
            rechazo=True, motivo="Plazo fuera")
    else:
        add(True, f"Plazo {plazo}a OK")

    add(edad >= pol["edad_min"],
        f"Edad ingreso {edad} {'>=' if edad >= pol['edad_min'] else '<'} {pol['edad_min']}",
        rechazo=edad < pol["edad_min"],
        motivo="" if edad >= pol["edad_min"] else f"Falla Edad Min {pol['edad_min']}")
    add(edad <= pol["edad_max"],
        f"Edad ingreso {edad} {'<=' if edad <= pol['edad_max'] else '>'} {pol['edad_max']}",
        rechazo=edad > pol["edad_max"],
        motivo="" if edad <= pol["edad_max"] else f"Falla Edad Max Ingreso {pol['edad_max']}")
    term_ok = edad_term <= pol["edad_term"] + 1e-9
    add(term_ok, f"Edad término {edad_term}a {'<=' if term_ok else '>'} 79a 360d",
        rechazo=not term_ok,
        motivo="" if term_ok else f"Edad termino > {pol['edad_term']}")

    if renta_eval < rmin_clp:
        add(False,
            f"Renta {_fmt_clp(renta_eval)} < mínima UF{rmin_uf:g} = {_fmt_clp(rmin_clp)} "
            f"con UF {_fmt_clp(uf)}",
            "Complementar renta", rechazo=True,
            motivo=f"Falla Renta Min UF {rmin_uf:g}")
    else:
        add(True, f"Renta {_fmt_clp(renta_eval)} >= mínima {_fmt_clp(rmin_clp)} UF{rmin_uf:g} OK")

    add(nac_ok, "Nacionalidad Chilena/Perm Def OK",
        rechazo=not nac_ok, motivo="" if nac_ok else "Falla Nacionalidad Chilena/Perm Def")

    if act == "independiente" and tiene_antig and antig < pol["ind_meses"]:
        add(False, f"Independiente {antig:g}m < {pol['ind_meses']:g}m", rechazo=True,
            motivo=f"Falla Antigüedad independiente {pol['ind_meses']:g} meses")
    else:
        add(True, f"Actividad {act} OK")

    if tiene_antig:
        if antig < amin_need:
            add(False, f"Antigüedad {antig:g}m < {amin_need:g}m", rechazo=True,
                motivo=f"Falla Antigüedad {amin_need:g} meses")
        else:
            add(True, f"Antigüedad {antig:g}m OK")

    if tiene_cont:
        if cont < cmin_need:
            add(False, f"Continuidad {cont:g}m < {cmin_need:g}m", rechazo=True,
                motivo=f"Falla Continuidad {cmin_need:g} meses")
        else:
            add(True, f"Continuidad {cont:g}m OK — 6 liquidaciones validan")

    nombres_bloq = POLITICA_BASE["bloqueos"]
    if prohib or any(_b(bloqueos_on.get(k)) for k in bloqueos_on):
        activos = [k for k, v in (bloqueos_on or {}).items() if _b(v)]
        etiqueta = activos[0] if activos else "Protestos vigentes NO"
        if etiqueta not in nombres_bloq:
            etiqueta = next((b for b in nombres_bloq if etiqueta.lower() in b.lower()),
                            "Protestos vigentes NO")
        add(False, "Deuda prohibida morosa/vencida/castigada/mora/protesto/pagaré/SAR = RECHAZO",
            rechazo=True, motivo=f"Falla {etiqueta}")
    else:
        add(True, "Sin deuda prohibida OK")

    if div_renta > pol["dmax"] + 1e-9:
        add(False, f"Div/Renta {div_renta * 100:.1f}% > {pol['dmax'] * 100:.0f}%",
            f"Bajar dividendo a {_fmt_clp(renta_eval * pol['dmax'])}", rechazo=True,
            motivo=f"Div/Renta > {pol['dmax'] * 100:.0f}%")
    else:
        add(True, f"Div/Renta {div_renta * 100:.1f}% OK")

    if carga > pol["cmax"] + 1e-9:
        add(False, f"Carga {carga * 100:.1f}% > {pol['cmax'] * 100:.0f}%",
            f"Pagar {_fmt_clp((carga - pol['cmax']) * renta_eval)}", rechazo=True,
            motivo=f"Carga > {pol['cmax'] * 100:.0f}%")
    else:
        add(True, f"Carga {carga * 100:.1f}% OK")

    if tipo == "directo":
        if carga_tit > 0.70 + 1e-9:
            add(False, f"CF Tit {carga_tit * 100:.1f}% > 70% Directo", rechazo=True,
                motivo="Falla CF Titular Directo 70%")
        else:
            add(True, f"CF Tit {carga_tit * 100:.1f}% <= 70% Directo OK")
    elif tipo == "tercero":
        if carga_tit > 0.60 + 1e-9:
            add(False, f"CF Tit {carga_tit * 100:.1f}% > 60% Tercero", rechazo=True,
                motivo="Falla CF Titular Tercero 60%")
        else:
            add(True, f"CF Tit {carga_tit * 100:.1f}% <= 60% OK")
        ap = renta_tit / renta_total if renta_total > 0 else 0
        if ap < 0.50:
            add(False, f"Aporte tit {ap * 100:.1f}% < 50%", rechazo=True,
                motivo="Falla Aporte titular 50% div/renta")
        else:
            add(True, f"Aporte tit {ap * 100:.1f}% >= 50% OK")
    elif tipo == "conyuge":
        add(True, "Cónyuge CON hijo — ratios familiares (conjunto)")

    # ── POLITICA REAL (vigía): si BASE pasa y REAL corta más bajo → OBSERVADO ──
    real_checks = []
    real_ok = True
    real_bloque = {}
    if isinstance(real, dict) and real.get("listo"):
        real_bloque = real.get("con_subsidio" if sub else "sin_subsidio") or {}
        dreal = real_bloque.get("div_max_real")
        creal = real_bloque.get("carga_max_real")
        if dreal and div_renta > dreal + 1e-9:
            real_ok = False
            real_checks.append({
                "ok": False,
                "txt": f"REAL corta Div/Renta en {dreal * 100:.1f}% (operación {div_renta * 100:.1f}%)",
                "motivo": f"Falla REAL Div/Renta {dreal * 100:.1f}%",
            })
        if creal and carga > creal + 1e-9:
            real_ok = False
            real_checks.append({
                "ok": False,
                "txt": f"REAL corta Carga en {creal * 100:.1f}% (operación {carga * 100:.1f}%)",
                "motivo": f"Falla REAL Carga {creal * 100:.1f}%",
            })
        pie_real = real_bloque.get("pie_min_real")
        if pie_real and pie + 1e-9 < pie_real:
            real_ok = False
            real_checks.append({
                "ok": False,
                "txt": f"REAL pide pie {pie_real * 100:.1f}% (operación {pie * 100:.0f}%)",
                "motivo": f"Falla REAL Pie Min {pie_real * 100:.1f}%",
            })

    base_ok = estado == "APROBADO"
    if estado == "BLOQUEO 412":
        semaforo = "BLOQUEO 412"
    elif estado == "BLOQUEADO":
        semaforo = "BLOQUEADO"
    elif estado == "RECHAZADO":
        semaforo = "RECHAZO"
    elif estado == "COMITE EXCEPCION":
        semaforo = "COMITE EXCEPCION"
    elif base_ok and not real_ok:
        semaforo = "OBSERVADO"
        _sube("OBSERVADO")
    else:
        semaforo = "APROBADO" if estado == "APROBADO" else estado

    n_ok = sum(1 for c in chk if c["ok"])
    motivos = [c["motivo"] for c in chk if not c["ok"] and c.get("motivo")]
    motivos += [c["motivo"] for c in real_checks if c.get("motivo")]
    return {
        "estado": estado,
        "semaforo": semaforo,
        "motivos": motivos,
        "checks": chk,
        "checks_real": real_checks,
        "base_ok": base_ok,
        "real_ok": real_ok,
        "n_reglas": len(chk),
        "n_ok": n_ok,
        "con_subsidio": sub,
        "tipo_codeudor": tipo,
        "uf_usada": round(uf, 2),
        "uf_respaldo": respaldo,
        "renta_titular": round(renta_tit, 0),
        "renta_total": round(renta_eval, 0),
        "promedio_liq": round(prom, 0),
        "liquidaciones": [_n(x) for x in (liqs or [])],
        "div_renta": round(div_renta, 4),
        "carga": round(carga, 4),
        "carga_titular": round(carga_tit, 4),
        "ltv": round(ltv, 10) if valor > 0 else None,
        "ltv_trunc_pct": ltv_pct,
        "tasa_aplicada": tasa,
        "dividendo": round(div),
        "dividendo_pmt": round(div_pmt),
        "dividendo_fuente": div_fuente,
        "seguro_desgravamen": round(desg),
        "seguro_incendio": round(inc),
        "seguros_fuente": fuente_seg,
        "tasa": tasa / 100.0 if tasa > 1 else tasa,
        "valor_propiedad_clp": round(valor * uf) if valor else 0,
        "monto_credito_clp": round(monto * uf) if monto else 0,
        "renta_minima_clp": round(rmin_clp),
        "politica": {k: pol[k] for k in ("vmin", "vmax", "mmin", "mmax", "dmax", "cmax",
                                         "pmin", "pmax", "pie_min", "ltv_max", "ltv_duro")},
        "politica_real": real_bloque,
        "client_type": client_type,
        "exento_afp": exento_afp,
        "licencia_medica": licencia,
        "cuota_cmf": round(cuota_cmf),
        "pie": round(pie, 4),
        "kpi": (f"LTV {ltv_pct:.2f}% Pie {pie * 100:.2f}% | "
                f"Div/Renta {div_renta * 100:.2f}% | Carga {carga * 100:.2f}%"),
        "faltan_412": faltan_412,
        "force_incompleto": force_inc,
    }
