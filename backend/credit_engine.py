"""Credit evaluation engine for Central Mutuos / Central PREDIC.

Contains the financial math (French amortization) and the credit
viability evaluators used across the platform.
"""
import math


# ---------------------------------------------------------------------------
# Financial helpers
# ---------------------------------------------------------------------------
def monthly_rate(annual_rate: float) -> float:
    """Convert an effective annual rate to an effective monthly rate."""
    if annual_rate <= 0:
        return 0.0
    return (1 + annual_rate) ** (1 / 12) - 1


def dividendo(monto_uf: float, annual_rate: float, plazo_anos: int) -> float:
    """Monthly payment (dividendo) for a loan, French system."""
    if monto_uf <= 0 or plazo_anos <= 0:
        return 0.0
    i = monthly_rate(annual_rate)
    n = plazo_anos * 12
    if i <= 0:
        return monto_uf / n
    factor = (1 + i) ** n
    return monto_uf * (i * factor) / (factor - 1)


def capacidad_desde_dividendo(div_uf: float, annual_rate: float, plazo_anos: int) -> float:
    """Present value (credit amount) affordable given a monthly payment."""
    if div_uf <= 0 or plazo_anos <= 0:
        return 0.0
    i = monthly_rate(annual_rate)
    n = plazo_anos * 12
    if i <= 0:
        return div_uf * n
    factor = (1 + i) ** n
    return div_uf * (factor - 1) / (i * factor)


def cuota_prestamo(monto: float, annual_rate: float, plazo_anos: int) -> dict:
    """Loan installment breakdown (used by debt calculator)."""
    if monto <= 0 or plazo_anos <= 0:
        return {"cuota_mensual": 0, "total_a_pagar": 0, "total_intereses": 0}
    i = monthly_rate(annual_rate)
    n = plazo_anos * 12
    if i <= 0:
        cuota = monto / n
    else:
        factor = (1 + i) ** n
        cuota = monto * (i * factor) / (factor - 1)
    total = cuota * n
    return {
        "cuota_mensual": round(cuota),
        "total_a_pagar": round(total),
        "total_intereses": round(total - monto),
    }


# ═══════════════════════════════════════════════════════════════════════════
# ESTÁNDAR DE ORO DASHAI — Depuración de endeudamiento (Fórmula 2%)
# Cuota teórica de deudas = 2% mensual del total reportado (proyección 48 meses).
# Se aplica al 100% de la deuda CMF y al saldo de Crédito Interno (PAV).
# ═══════════════════════════════════════════════════════════════════════════
CF_PCT_MENSUAL = 0.02      # 2% mensual
CF_PROYECCION_MESES = 48   # proyección de amortización teórica
CF_TOPE_CARGA = 0.40       # Carga Financiera máxima sobre renta líquida depurada


def cuota_teorica(deuda_total_clp, pct=CF_PCT_MENSUAL):
    """Valor Cuota Teórico = 2% mensual del total de la deuda (CLP)."""
    return max(0.0, float(deuda_total_clp or 0)) * float(pct or CF_PCT_MENSUAL)


def endeudamiento_mensual(df, uf_valor, pct=CF_PCT_MENSUAL):
    """Endeudamiento mensual teórico (CLP) según el estándar de oro DashAI.

    Suma el 100% de la deuda CMF + saldo PAV y aplica el 2% mensual.
    Convierte montos en UF a CLP con la UF del día (fuente SII) antes del %.
    """
    df = df or {}
    uf_valor = float(uf_valor or 39000)

    def _monto(clp_keys, uf_keys):
        for k in clp_keys:
            if df.get(k) not in (None, "", 0, "0"):
                return _n(df.get(k))
        for k in uf_keys:
            if df.get(k) not in (None, "", 0, "0"):
                return _n(df.get(k)) * uf_valor
        return 0.0

    deuda_titular = _monto(
        ["deuda_cmf_total", "deuda_cmf", "deudas_cmf_total", "monto_deuda_cmf", "deuda_total_cmf"],
        ["deuda_cmf_uf", "deuda_cmf_total_uf"])
    deuda_codeudor = _monto(
        ["deuda_cmf_codeudor", "deuda_codeudor_total", "deuda_codeudor"],
        ["deuda_cmf_codeudor_uf"])
    # AGREGACIÓN FINANCIERA CONJUNTA: la deuda total es titular MÁS codeudor
    deuda_cmf = deuda_titular + deuda_codeudor
    pav_saldo = _monto(
        ["credito_interno_pav", "pav_saldo", "credito_pav", "saldo_pav"],
        ["pav_saldo_uf", "credito_pav_uf"])

    cuota_cmf = cuota_teorica(deuda_cmf, pct)
    cuota_pav = cuota_teorica(pav_saldo, pct)
    # Compatibilidad: si no hay totales pero sí una cuota directa histórica, úsala.
    if cuota_cmf == 0 and df.get("cuota_deudas"):
        cuota_cmf = _n(df.get("cuota_deudas"))
    return {
        "deuda_cmf_total_clp": round(deuda_cmf),
        "deuda_cmf_titular_clp": round(deuda_titular),
        "deuda_cmf_codeudor_clp": round(deuda_codeudor),
        "pav_saldo_clp": round(pav_saldo),
        "cuota_teorica_cmf_clp": round(cuota_cmf),
        "cuota_teorica_pav_clp": round(cuota_pav),
        "endeudamiento_mensual_clp": round(cuota_cmf + cuota_pav),
        "pct_mensual": float(pct or CF_PCT_MENSUAL),
        "proyeccion_meses": CF_PROYECCION_MESES,
    }



def _n(v):
    try:
        return float(str(v).replace(".", "").replace(",", ".")) if isinstance(v, str) else float(v or 0)
    except (ValueError, TypeError):
        return 0.0


def techo_hipotecario(df, criterios, tasas, uf_valor, plazo=25, cuota_cmf_clp=None):
    """MOTOR DE CÁLCULO INVERSO (Techo Hipotecario).

    A partir de la renta líquida depurada (con castigos de la Constitución DashAI),
    el tope de Carga Financiera y las deudas CMF, calcula el crédito MÁXIMO en UF
    que la MESA aprobaría, para los escenarios BTG Pactual y Ameris.
    """
    df = df or {}
    criterios = criterios or {}
    tasas = tasas or {}
    uf_valor = float(uf_valor or 39000)

    renta_fija = _n(df.get("renta_liquida"))
    renta_var = _n(df.get("renta_variable"))
    renta_hon = _n(df.get("honorarios"))
    con_sub = bool(df.get("con_subsidio"))
    # ESTÁNDAR DE ORO: endeudamiento = 2% mensual sobre deuda CMF total + saldo PAV
    endeud = endeudamiento_mensual(df, uf_valor)
    if cuota_cmf_clp is not None:
        # override manual del operador (ya es una cuota, no un total)
        endeud["cuota_teorica_cmf_clp"] = round(_n(cuota_cmf_clp))
        endeud["endeudamiento_mensual_clp"] = round(_n(cuota_cmf_clp) + endeud["cuota_teorica_pav_clp"])
    cmf = float(endeud["endeudamiento_mensual_clp"])

    # Castigos de renta desde la Constitución (Ley del RUT / BTG)
    cast = (criterios.get("btg_pactual") or {}).get("castigos_renta") or {}
    c_var = float(cast.get("renta_variable_castigo") or 0.15)
    c_hon = float(cast.get("honorarios_castigo") or 0.20)
    renta_dep = renta_fija + renta_var * (1 - c_var) + renta_hon * (1 - c_hon)

    tasa = float(tasas.get("tasa_subsidio_mayor_2000") if con_sub
                 else tasas.get("tasa_sin_subsidio") or 0.06) or 0.06

    def _escenario(nombre, carga_max, div_renta_max):
        # REGLA MESA (orden del dueño): el dividendo futuro + el endeudamiento presente
        # (cuota teórica de deudas prorrateada a 48) deben cumplir AMBOS niveles sobre renta.
        # Carga: (dividendo + deudas)/renta ≤ carga_max
        div_por_carga = renta_dep * carga_max - cmf
        # Dividendo/renta: (dividendo + deudas)/renta ≤ div_renta_max
        div_por_dr = renta_dep * div_renta_max - cmf
        binding = "Carga Financiera" if div_por_carga <= div_por_dr else "Dividendo/Renta + deudas"
        div_max_clp = max(0.0, min(div_por_carga, div_por_dr))
        div_max_uf = div_max_clp / uf_valor if uf_valor > 0 else 0.0
        credito_uf = capacidad_desde_dividendo(div_max_uf, tasa, plazo)
        return {
            "banco": nombre,
            "credito_maximo_uf": round(credito_uf, 1),
            "dividendo_maximo_clp": round(div_max_clp),
            "dividendo_maximo_uf": round(div_max_uf, 2),
            "carga_max_pct": round(carga_max * 100, 1),
            "div_renta_max_pct": round(div_renta_max * 100, 1),
            "restriccion_activa": binding,
        }

    btg = criterios.get("btg_pactual") or {}
    btg_seg = btg.get("con_subsidio" if con_sub else "sin_subsidio") or {}
    btg_carga = float(btg_seg.get("carga_financiera_max")
                      or btg_seg.get("carga_financiera_max_sin_codeudor") or 0.40)
    btg_dr = float(btg_seg.get("div_renta_max")
                   or btg_seg.get("div_renta_max_sin_codeudor") or 0.30)

    am = (criterios.get("ameris") or {}).get("con_subsidio") or {}
    am_carga = float(am.get("carga_sin_codeudor_max") or 0.35)
    am_dr = float((am.get("div_renta_sin_codeudor") or {}).get("edad_max_40") or 0.30)

    escenarios = [
        _escenario("BTG Pactual", btg_carga, btg_dr),
        _escenario("Ameris", am_carga, am_dr),
    ]
    mejor = max(escenarios, key=lambda e: e["credito_maximo_uf"]) if escenarios else None
    # VALIDACIÓN DE CARGA: el endeudamiento actual (sin nuevo dividendo) ya no debe
    # consumir por sí solo el tope de 40% de la renta líquida depurada.
    carga_actual_pct = round((cmf / renta_dep * 100), 1) if renta_dep > 0 else 0
    alerta_carga = (renta_dep > 0 and cmf > renta_dep * CF_TOPE_CARGA)

    return {
        "renta_liquida_depurada_clp": round(renta_dep),
        "renta_liquida_depurada_uf": round(renta_dep / uf_valor, 2) if uf_valor > 0 else 0,
        "componentes_renta": {
            "renta_liquida_fija": round(renta_fija),
            "renta_variable_castigada": round(renta_var * (1 - c_var)),
            "honorarios_castigados": round(renta_hon * (1 - c_hon)),
            "castigo_variable_pct": round(c_var * 100),
            "castigo_honorarios_pct": round(c_hon * 100),
        },
        "endeudamiento": endeud,
        "deuda_cmf_cuota_clp": round(cmf),
        "carga_actual_pct": carga_actual_pct,
        "alerta_carga_excedida": alerta_carga,
        "con_subsidio": con_sub,
        "tasa_anual_pct": round(tasa * 100, 2),
        "plazo_anos": plazo,
        "uf_valor": round(uf_valor),
        "escenarios": escenarios,
        "mejor_escenario": mejor,
        "datos_suficientes": renta_dep > 0,
    }




def tipo_deudor_texto(t: int, tiene_codeudor: bool) -> str:
    base = {
        1: "Tipo 1 - Dependiente Renta Fija",
        2: "Tipo 2 - Dependiente Renta Variable",
        3: "Tipo 3 - Independiente / Honorarios",
    }.get(int(t or 1), "Tipo 1 - Dependiente Renta Fija")
    return base + (" (con codeudor)" if tiene_codeudor else "")


# ---------------------------------------------------------------------------
# simular-credito  (main platform Simulador)
# ---------------------------------------------------------------------------
def simular_credito(d: dict) -> dict:
    valor_uf = float(d.get("valor_uf") or 39842)
    renta_t = float(d.get("renta_titular") or 0)
    renta_c = float(d.get("renta_codeudor") or 0)
    plazo = int(d.get("plazo_anos") or 25)
    tasa = float(d.get("tasa_anual") or 0.0635)
    carga = float(d.get("carga_financiera") or 0)
    # ESTÁNDAR DE ORO: si vienen totales CMF/PAV, la carga usa la cuota teórica 2%
    _endeud = endeudamiento_mensual(d, valor_uf)
    if _endeud["endeudamiento_mensual_clp"] > 0:
        carga = float(_endeud["endeudamiento_mensual_clp"])
    ahorro = float(d.get("ahorro_uf") or 0)
    subsidio = float(d.get("subsidio_uf") or 0)
    edad_t = int(d.get("edad_cliente") or 0)
    edad_c = int(d.get("edad_codeudor") or 0)
    valor_prop = float(d.get("valor_propiedad_uf") or 0)
    credito_sol = float(d.get("credito_solicitado_uf") or 0)
    tipo_deudor = int(d.get("tipo_deudor") or 1)
    morosidad = bool(d.get("morosidad_dicom"))
    protestos = bool(d.get("protestos_vigentes"))
    continuidad = d.get("continuidad_laboral", True)

    tiene_codeudor = renta_c > 0

    # Renta castigada segun tipo de deudor
    castigo = {1: 0.0, 2: 0.15, 3: 0.20}.get(tipo_deudor, 0.0)
    renta_t_efect = renta_t * (1 - castigo)
    renta_total = renta_t_efect + renta_c
    renta_bruta_total = renta_t + renta_c

    # Umbrales (defaults BTG con-codeudor si vienen)
    u_div = float(d.get("umbral_btg_div_renta") or 0.35)
    u_carga = float(d.get("umbral_btg_carga_fin") or 0.40)
    u_ltv = min(float(d.get("umbral_btg_ltv") or 0.80), LTV_MAX_63)
    u_edad_plazo = float(d.get("umbral_btg_edad_plazo") or 80)
    a_div = float(d.get("umbral_ameris_div_renta") or 0.30)
    a_carga = float(d.get("umbral_ameris_carga_fin") or 0.35)
    a_ltv = min(float(d.get("umbral_ameris_ltv") or 0.80), LTV_MAX_63)
    a_edad_plazo = float(d.get("umbral_ameris_edad_plazo") or 75)

    # Capacidad de credito (tope de dividendo = 30% conjunta)
    ratio_cap = 0.30 if tiene_codeudor else 0.35
    dividendo_tope_clp = max(0.0, renta_total * ratio_cap - carga)
    dividendo_tope_uf = dividendo_tope_clp / valor_uf
    capacidad_uf = capacidad_desde_dividendo(dividendo_tope_uf, tasa, plazo)

    # Credito maximo limitado por LTV de la propiedad
    # REGLA DE ORO #11 + #63: tope 79.50% exacto (10 decimales) y TRUNCADO a 2 (jamás hacia arriba)
    ltv_cap_uf = int(round(valor_prop * u_ltv, 10) * 100) / 100 if valor_prop > 0 else capacidad_uf
    credito_maximo_uf = min(capacidad_uf, ltv_cap_uf) if valor_prop > 0 else capacidad_uf
    credito_maximo_uf = int(credito_maximo_uf * 100) / 100

    dividendo_credito_uf = dividendo(credito_maximo_uf, tasa, plazo)
    dividendo_credito_clp = round(dividendo_credito_uf * valor_uf)

    # Credito a evaluar (solicitado o maximo)
    credito_eval = credito_sol if credito_sol > 0 else credito_maximo_uf
    div_eval_uf = dividendo(credito_eval, tasa, plazo)
    div_eval_clp = div_eval_uf * valor_uf

    def ratio(num, den):
        return (num / den) if den > 0 else 0.0

    div_renta_individual = ratio(div_eval_clp, renta_t_efect)
    div_renta_codeudor = ratio(div_eval_clp, renta_c) if tiene_codeudor else 0.0
    div_renta_conjunta = ratio(div_eval_clp, renta_total)
    carga_fin_individual = ratio(div_eval_clp + carga, renta_t_efect)
    carga_fin_codeudor = ratio(div_eval_clp + carga, renta_c) if tiene_codeudor else 0.0
    carga_fin_conjunta = ratio(div_eval_clp + carga, renta_total)
    ltv = ratio(credito_eval, valor_prop)
    edad_ref = max(edad_t, edad_c) if tiene_codeudor else edad_t
    edad_plazo = edad_ref + plazo

    def evaluar(nombre, max_div, max_carga, max_ltv, max_edad_plazo):
        razones = []
        if div_renta_conjunta > max_div:
            razones.append(f"DIV/Renta {div_renta_conjunta*100:.1f}% supera maximo {max_div*100:.0f}%")
        if carga_fin_conjunta > max_carga:
            razones.append(f"Carga financiera {carga_fin_conjunta*100:.1f}% supera maximo {max_carga*100:.0f}%")
        if valor_prop > 0 and ltv > max_ltv:
            razones.append(f"LTV {ltv*100:.1f}% supera maximo {max_ltv*100:.0f}%")
        if edad_plazo > max_edad_plazo:
            razones.append(f"Edad+Plazo {edad_plazo} supera maximo {int(max_edad_plazo)}")
        if morosidad:
            razones.append("Cliente con morosidad vigente en DICOM")
        if protestos:
            razones.append("Protestos vigentes")
        if not continuidad:
            razones.append("Sin continuidad laboral")
        return ("APROBADO/A" if not razones else "RECHAZADO/A"), razones

    eval_btg, eval_btg_razones = evaluar("BTG", u_div, u_carga, u_ltv, u_edad_plazo)
    eval_ameris, eval_ameris_razones = evaluar("AMERIS", a_div, a_carga, a_ltv, a_edad_plazo)

    aprobada = eval_btg == "APROBADO/A" or eval_ameris == "APROBADO/A"

    # Credito solicitado viable?
    credito_viable = False
    pie_requerido_uf = 0.0
    ajuste_pie_795 = False
    credito_ajustado_795_uf = credito_sol
    if credito_sol > 0:
        credito_viable = credito_sol <= credito_maximo_uf + 0.5 and (valor_prop == 0 or ltv <= max(u_ltv, a_ltv))
        pie_requerido_uf = round(max(0.0, valor_prop - credito_sol - subsidio - ahorro), 2)
        # REGLA DE ORO #63: ratio sobre 79.50% → el Pie sube automáticamente hasta clavar el 79.50%
        if valor_prop > 0 and ltv > LTV_MAX_63:
            ajuste_pie_795 = True
            credito_ajustado_795_uf = int(round(valor_prop * LTV_MAX_63, 10) * 100) / 100
            pie_requerido_uf = round(max(0.0, valor_prop - credito_ajustado_795_uf - subsidio - ahorro), 2)

    valor_maximo_compra_uf = round(credito_maximo_uf + ahorro + subsidio, 2)

    razones_rechazo = []
    if not aprobada:
        # Combinar razones unicas
        seen = set()
        for r in eval_btg_razones + eval_ameris_razones:
            if r not in seen:
                seen.add(r)
                razones_rechazo.append(r)

    return {
        "nombre_completo": d.get("nombre_completo", ""),
        "rut": d.get("rut", ""),
        "telefono": d.get("telefono", ""),
        "correo": d.get("correo", ""),
        "valor_uf": valor_uf,
        "tasa_anual": tasa,
        "plazo_anos": plazo,
        "precalificacion_aprobada": aprobada,
        "capacidad_credito_uf": round(capacidad_uf, 2),
        "capacidad_credito_clp": round(capacidad_uf * valor_uf),
        "credito_maximo_uf": credito_maximo_uf,
        "dividendo_credito_uf": round(dividendo_credito_uf, 2),
        "dividendo_credito_clp": dividendo_credito_clp,
        "dividendo_tope": round(dividendo_tope_clp),
        "valor_maximo_compra_uf": valor_maximo_compra_uf,
        "credito_solicitado_uf": credito_sol,
        "credito_viable": credito_viable,
        "pie_requerido_uf": pie_requerido_uf,
        "ajuste_pie_795": ajuste_pie_795,
        "credito_ajustado_795_uf": credito_ajustado_795_uf,
        "ltv_maximo_795": LTV_MAX_63,
        "valor_propiedad_uf": valor_prop,
        "div_renta_individual": round(div_renta_individual, 4),
        "div_renta_codeudor": round(div_renta_codeudor, 4),
        "div_renta_conjunta": round(div_renta_conjunta, 4),
        "carga_fin_individual": round(carga_fin_individual, 4),
        "carga_fin_codeudor": round(carga_fin_codeudor, 4),
        "carga_fin_conjunta": round(carga_fin_conjunta, 4),
        "ltv": round(ltv, 4),
        "edad_plazo": edad_plazo,
        "tiene_codeudor": tiene_codeudor,
        "tipo_deudor_texto": tipo_deudor_texto(tipo_deudor, tiene_codeudor),
        "eval_btg": eval_btg,
        "eval_btg_razones": eval_btg_razones,
        "eval_ameris": eval_ameris,
        "eval_ameris_razones": eval_ameris_razones,
        "razones_rechazo": razones_rechazo,
        "endeudamiento": _endeud,
        "alerta_carga_40": bool(carga_fin_conjunta > CF_TOPE_CARGA),
    }


# REGLA DE ORO #63 — ULTRA-PRECISIÓN: financiamiento máximo 79.50% EXACTO (10 decimales)
LTV_MAX_63 = round(0.7950000000, 10)


# ---------------------------------------------------------------------------
# inmobiliaria/predict  (Central PREDIC)
# ---------------------------------------------------------------------------
def _plazo_maximo(edad: int, edad_max: float = 80) -> int:
    return max(1, min(40, int(edad_max) - edad))


def predict_inmobiliaria(d: dict, tasas: dict, seguros: dict, valor_uf: float) -> dict:
    modo = d.get("modo", "subsidio")
    valor_prop = float(d.get("valor_propiedad_uf") or 0)
    subsidio = float(d.get("subsidio_uf") or 0)
    pie = float(d.get("pie_uf") or 0)
    monto_credito = float(d.get("monto_credito_uf") or 0)
    renta_fija = float(d.get("renta_fija") or 0)
    renta_var = float(d.get("renta_variable") or 0)
    renta_hon = float(d.get("renta_honorarios") or 0)
    cuota_deudas = float(d.get("cuota_deudas") or 0)
    # ESTÁNDAR DE ORO: cuota teórica 2% sobre deuda CMF total + saldo PAV
    _endeud_pi = endeudamiento_mensual(d, valor_uf)
    if _endeud_pi["endeudamiento_mensual_clp"] > 0:
        cuota_deudas = float(_endeud_pi["endeudamiento_mensual_clp"])
    edad = int(d.get("edad_cliente") or 35)
    tipo_deudor = int(d.get("tipo_deudor") or 1)
    tipo_codeudor = int(d.get("tipo_codeudor") or 0)
    renta_codeudor = float(d.get("renta_codeudor") or 0)
    edad_codeudor = int(d.get("edad_codeudor") or 0)
    antiguedad = int(d.get("antiguedad_laboral_meses") or 24)
    morosidad = bool(d.get("morosidad_dicom"))
    protestos = bool(d.get("protestos_vigentes"))
    continuidad = d.get("continuidad_laboral", True)
    plazo_in = int(d.get("plazo_anos") or 0)

    tiene_codeudor = tipo_codeudor > 0 and renta_codeudor > 0

    castigo_var = renta_var * 0.15
    castigo_hon = renta_hon * 0.20
    renta_efectiva = renta_fija + renta_var * 0.85 + renta_hon * 0.80 + renta_codeudor

    # Tasa
    if modo == "subsidio":
        tasa = tasas["tasa_subsidio_mayor_2000"] if monto_credito > 2000 else tasas["tasa_subsidio_menor_2000"]
        ltv_max = min(float(u.get("ltv_maximo") or 0.80), LTV_MAX_63)
    else:
        tasa = tasas["tasa_sin_subsidio"]
        ltv_max = min(float(u.get("ltv_maximo_sin_subsidio") or 0.90), LTV_MAX_63)
    tasa_aplicada = round(tasa * 100, 2)

    plazo_max = _plazo_maximo(max(edad, edad_codeudor) if tiene_codeudor else edad, u_edad)
    plazo = plazo_in if plazo_in > 0 else min(30, plazo_max)
    plazo = min(plazo, plazo_max)
    plazo_alternativo = max(10, plazo - 5) if plazo - 5 >= 10 else min(plazo_max, plazo + 5)
    if plazo_alternativo == plazo:
        plazo_alternativo = 0

    # Capacidad
    ratio_cap = 0.30
    div_tope_clp = max(0.0, renta_efectiva * ratio_cap - cuota_deudas)
    div_tope_uf = div_tope_clp / valor_uf
    capacidad_uf = capacidad_desde_dividendo(div_tope_uf, tasa, plazo)

    ltv_cap_uf = round(valor_prop * ltv_max, 10) if valor_prop > 0 else capacidad_uf
    candidates = [capacidad_uf]
    if valor_prop > 0:
        candidates.append(ltv_cap_uf)
    if monto_credito > 0:
        candidates.append(monto_credito)
    monto_aprobado_uf = round(max(0.0, min(candidates)), 1)

    div_uf = dividendo(monto_aprobado_uf, tasa, plazo)
    div_clp = round(div_uf * valor_uf)
    div_alt_uf = dividendo(monto_aprobado_uf, tasa, plazo_alternativo) if plazo_alternativo else 0
    div_alt_clp = round(div_alt_uf * valor_uf) if plazo_alternativo else 0

    ltv = (monto_aprobado_uf / valor_prop) if valor_prop > 0 else 0.0
    div_renta_pct = round((div_clp / renta_efectiva * 100) if renta_efectiva > 0 else 0, 1)
    carga_fin_pct = round(((div_clp + cuota_deudas) / renta_efectiva * 100) if renta_efectiva > 0 else 0, 1)
    ltv_pct = round(ltv * 100, 1)
    edad_final = (max(edad, edad_codeudor) if tiene_codeudor else edad) + plazo

    def evaluar_escenario(pl, dv_clp):
        razones = []
        if renta_efectiva <= 0:
            razones.append("Ingrese la renta del titular")
        if dv_clp > 0 and renta_efectiva > 0 and (dv_clp / renta_efectiva) > 0.35:
            razones.append(f"DIV/Renta {(dv_clp/renta_efectiva*100):.0f}% supera 35%")
        if renta_efectiva > 0 and ((dv_clp + cuota_deudas) / renta_efectiva) > 0.40:
            razones.append("Carga financiera supera 40%")
        if valor_prop > 0 and ltv > ltv_max:
            razones.append(f"LTV {ltv*100:.0f}% supera {int(ltv_max*100)}%")
        if edad + pl > 80:
            razones.append(f"Edad+Plazo {edad+pl} supera 80")
        if antiguedad < 12:
            razones.append("Antiguedad laboral menor a 12 meses")
        if morosidad:
            razones.append("Morosidad DICOM vigente")
        if protestos:
            razones.append("Protestos vigentes")
        if not continuidad:
            razones.append("Sin continuidad laboral")
        if monto_aprobado_uf < 300:
            razones.append("Monto de credito bajo el minimo (300 UF)")
        return ("VIABLE" if not razones else "NO VIABLE"), razones

    eval1, eval1_raz = evaluar_escenario(plazo, div_clp)
    eval2, eval2_raz = evaluar_escenario(plazo_alternativo, div_alt_clp) if plazo_alternativo else ("NO APLICA", [])

    viable = eval1 == "VIABLE" or eval2 == "VIABLE"

    # Seguros
    desg_base = seguros["seguro_desgravamen"]
    desg = desg_base * 2 if tiene_codeudor else desg_base
    incendio = seguros["seguro_incendio"]
    total_seg = desg + incendio
    seguros_out = {
        "seguro_desgravamen": desg,
        "seguro_desgravamen_base": desg_base,
        "tiene_codeudor": tiene_codeudor,
        "seguro_incendio": incendio,
        "total_seguros": total_seg,
        "dividendo_final": div_clp + total_seg,
        "dividendo_final_alt": (div_alt_clp + total_seg) if plazo_alternativo else 0,
    }

    # Central Score
    cap_score = 25 if div_renta_pct <= 25 else 18 if div_renta_pct <= 30 else 10 if div_renta_pct <= 35 else 3
    ltv_score = 25 if ltv_pct <= 70 else 18 if ltv_pct <= 80 else 10 if ltv_pct <= 90 else 3
    edad_score = 25 if edad_final <= 70 else 18 if edad_final <= 75 else 10 if edad_final <= 80 else 2
    perfil_score = 25
    if morosidad:
        perfil_score -= 12
    if protestos:
        perfil_score -= 8
    if not continuidad:
        perfil_score -= 6
    if antiguedad < 12:
        perfil_score -= 6
    perfil_score = max(0, perfil_score)
    total_score = cap_score + ltv_score + edad_score + perfil_score
    if total_score >= 80:
        risk_level, risk_color = "BAJO", "#00b894"
    elif total_score >= 60:
        risk_level, risk_color = "MEDIO", "#fdcb6e"
    elif total_score >= 40:
        risk_level, risk_color = "ALTO", "#e17055"
    else:
        risk_level, risk_color = "MUY ALTO", "#d63031"

    central_score = {
        "score": total_score,
        "methodology": "Evaluacion ponderada: Capacidad, LTV, Edad y Perfil",
        "risk_level": risk_level,
        "risk_color": risk_color,
        "factors": [
            {"factor": "Capacidad Pago", "score": cap_score},
            {"factor": "LTV", "score": ltv_score},
            {"factor": "Edad+Plazo", "score": edad_score},
            {"factor": "Perfil Riesgo", "score": perfil_score},
        ],
    }

    razones = []
    sugerencias = []
    if not viable:
        razones = eval1_raz or eval2_raz
        if div_renta_pct > 35:
            sugerencias.append("Aumentar el plazo o reducir el monto para bajar el dividendo")
        if ltv_pct > ltv_max * 100:
            sugerencias.append("Aportar mayor pie para reducir el LTV")
        if edad_final > 80:
            sugerencias.append("Reducir el plazo para cumplir edad+plazo <= 80")
        if antiguedad < 12:
            sugerencias.append("Esperar a cumplir 12 meses de antiguedad laboral")
        if not sugerencias:
            sugerencias.append("Considerar incorporar un codeudor con renta")

    return {
        "viable": viable,
        "modo": modo,
        "valor_uf_usado": valor_uf,
        "valor_propiedad_uf": valor_prop,
        "valor_propiedad_clp": round(valor_prop * valor_uf),
        "credito_solicitado_uf": monto_credito,
        "credito_solicitado_clp": round(monto_credito * valor_uf),
        "monto_aprobado_uf": monto_aprobado_uf,
        "monto_aprobado_clp": round(monto_aprobado_uf * valor_uf),
        "financiamiento_maximo_uf": monto_aprobado_uf,
        "dividendo_estimado_uf": round(div_uf, 2),
        "dividendo_estimado_clp": div_clp,
        "dividendo_alternativo_uf": round(div_alt_uf, 2) if plazo_alternativo else 0,
        "dividendo_alternativo_clp": div_alt_clp,
        "plazo_anos": plazo,
        "plazo_alternativo": plazo_alternativo,
        "plazo_maximo": plazo_max,
        "plazo_recomendado": min(30, plazo_max),
        "plazo_en_rango_preferido": plazo <= min(30, plazo_max),
        "capacidad_credito_uf": round(capacidad_uf, 1),
        "carga_financiera_pct": carga_fin_pct,
        "div_renta_pct": div_renta_pct,
        "ltv_pct": ltv_pct,
        "tasa_aplicada": tasa_aplicada,
        "tipo_deudor": tipo_deudor_texto(tipo_deudor, tiene_codeudor),
        "edad_plazo": edad + plazo,
        "edad_final_referencia": edad_final,
        "edad_plazo_codeudor": (edad_codeudor + plazo) if tiene_codeudor and edad_codeudor else 0,
        "castigo_renta_variable": round(castigo_var),
        "castigo_renta_honorarios": round(castigo_hon),
        "renta_efectiva": round(renta_efectiva),
        "eval_escenario_1": eval1,
        "eval_escenario_1_razones": eval1_raz,
        "eval_escenario_2": eval2,
        "eval_escenario_2_razones": eval2_raz,
        "razones": razones,
        "sugerencias_optimizacion": sugerencias,
        "seguros": seguros_out,
        "central_score": central_score,
    }


# ---------------------------------------------------------------------------
# ia/predict  (real-time predictive panel)
# ---------------------------------------------------------------------------
def ia_predict(d: dict) -> dict:
    valor_uf = float(d.get("valor_uf") or 39842)
    renta_t = float(d.get("renta_titular") or 0)
    renta_c = float(d.get("renta_codeudor") or 0)
    plazo = int(d.get("plazo_anos") or 0)
    tasa = float(d.get("tasa_anual") or 0.0635)
    credito = float(d.get("credito_solicitado_uf") or 0)
    valor_prop = float(d.get("valor_propiedad_uf") or 0)
    edad = int(d.get("edad_cliente") or 0)
    carga = float(d.get("carga_financiera") or 0)
    morosidad = bool(d.get("morosidad_dicom"))
    protestos = bool(d.get("protestos_vigentes"))
    continuidad = d.get("continuidad_laboral", True)

    renta_total = renta_t + renta_c
    eval_credit = credito if credito > 0 else capacidad_desde_dividendo(
        max(0, renta_total * 0.30 - carga) / valor_uf, tasa, plazo or 25)
    div_uf = dividendo(eval_credit, tasa, plazo or 25)
    div_clp = div_uf * valor_uf

    div_renta_ind = round((div_clp / renta_t * 100) if renta_t > 0 else 0, 1)
    ltv = round((eval_credit / valor_prop * 100) if valor_prop > 0 else 0, 1)
    edad_plazo = edad + (plazo or 25)
    carga_total = round(((div_clp + carga) / renta_total * 100) if renta_total > 0 else 0, 1)

    # Probabilidad heuristica
    prob = 100.0
    prob -= max(0, div_renta_ind - 30) * 2.5
    prob -= max(0, ltv - 75) * 1.8
    prob -= max(0, edad_plazo - 75) * 3
    prob -= max(0, carga_total - 35) * 2
    if morosidad:
        prob -= 40
    if protestos:
        prob -= 25
    if not continuidad:
        prob -= 20
    prob = max(2, min(98, prob))

    score_btg = max(0, min(100, prob + 4))
    score_ameris = max(0, min(100, prob - 3))
    mejor = "Institucion 1" if score_btg >= score_ameris else "Institucion 2"

    nivel = "MUY ALTA" if prob >= 80 else "ALTA" if prob >= 60 else "MEDIA" if prob >= 40 else "BAJA" if prob >= 20 else "MUY BAJA"
    mensaje = {
        "MUY ALTA": "Perfil solido, alta probabilidad de aprobacion.",
        "ALTA": "Buen perfil, probabilidad favorable de aprobacion.",
        "MEDIA": "Perfil ajustado, revise las metricas destacadas.",
        "BAJA": "Perfil con riesgos, requiere ajustes para aprobar.",
        "MUY BAJA": "Perfil no viable con los parametros actuales.",
    }[nivel]

    factores = []
    if div_renta_ind > 35:
        factores.append({"factor": "DIV/Renta alto", "valor": f"{div_renta_ind}%", "umbral": "35%", "severidad": "alta"})
    elif div_renta_ind > 30:
        factores.append({"factor": "DIV/Renta ajustado", "valor": f"{div_renta_ind}%", "umbral": "30%", "severidad": "media"})
    if ltv > 80:
        factores.append({"factor": "LTV elevado", "valor": f"{ltv}%", "umbral": "80%", "severidad": "alta"})
    if edad_plazo > 80:
        factores.append({"factor": "Edad+Plazo excede", "valor": str(edad_plazo), "umbral": "80", "severidad": "alta"})
    if morosidad:
        factores.append({"factor": "Morosidad DICOM", "valor": "Si", "umbral": "No", "severidad": "alta"})

    sugerencias = []
    if div_renta_ind > 30:
        sugerencias.append("Aumente el plazo o incorpore un codeudor para bajar el DIV/Renta")
    if ltv > 80:
        sugerencias.append("Incremente el pie para reducir el LTV bajo 80%")
    if edad_plazo > 80:
        sugerencias.append("Reduzca el plazo para cumplir edad+plazo <= 80")

    cap_seguro_uf = capacidad_desde_dividendo(
        max(0, renta_total * 0.28 - carga) / valor_uf, tasa, plazo or 25)

    return {
        "probabilidad": round(prob, 1),
        "nivel": nivel,
        "mensaje": mensaje,
        "score_btg": round(score_btg, 1),
        "score_ameris": round(score_ameris, 1),
        "mejor_banco": mejor,
        "metricas": {
            "div_renta_individual": div_renta_ind,
            "ltv": ltv,
            "edad_plazo": edad_plazo,
            "carga_financiera_total": carga_total,
        },
        "optimo": {"credito_maximo_seguro_uf": round(cap_seguro_uf, 1)},
        "factores_riesgo": factores,
        "sugerencias": sugerencias,
        "comparacion_historica": {
            "tasa_aprobacion_global": 62,
            "su_probabilidad_vs_promedio": round(prob - 62, 1),
        },
    }


# ---------------------------------------------------------------------------
# ai/analizar  (scenario analysis)
# ---------------------------------------------------------------------------
def ai_analizar(resultado: dict, valor_uf: float) -> dict:
    renta = 0.0
    # derive an affordable dividend from the result
    cap_clp = float(resultado.get("capacidad_credito_clp") or 0)
    tasa = float(resultado.get("tasa_anual") or 0.0635)
    valor_prop = float(resultado.get("valor_propiedad_uf") or 0)
    edad_plazo = int(resultado.get("edad_plazo") or 0)
    plazo_base = int(resultado.get("plazo_anos") or 25)
    edad = max(0, edad_plazo - plazo_base)
    div_tope_uf = (float(resultado.get("dividendo_tope") or 0)) / valor_uf

    escenarios = []
    mejor_plazo = plazo_base
    mejor_cap = 0.0
    for pl in [15, 20, 25, 30]:
        cap = capacidad_desde_dividendo(div_tope_uf, tasa, pl)
        if valor_prop > 0:
            cap = min(cap, valor_prop * 0.80)
        dv = dividendo(cap, tasa, pl)
        ep = edad + pl
        viable = ep <= 80 and cap > 0
        escenarios.append({
            "plazo": pl,
            "viable": viable,
            "capacidad_uf": round(cap, 1),
            "dividendo_uf": round(dv, 2),
            "dividendo_clp": round(dv * valor_uf),
            "edad_plazo": ep,
        })
        if viable and cap > mejor_cap:
            mejor_cap = cap
            mejor_plazo = pl

    recomendacion = (
        f"## Recomendacion\n"
        f"El **plazo optimo** es de **{mejor_plazo} anos**, alcanzando una capacidad "
        f"de **{round(mejor_cap,1)} UF**.\n\n"
        f"Se sugiere mantener el DIV/Renta bajo 35% y el LTV bajo 80% para maximizar "
        f"la probabilidad de aprobacion en comite."
    )

    return {
        "escenarios": escenarios,
        "monto_maximo_viable_uf": round(mejor_cap, 1),
        "monto_maximo_viable_clp": round(mejor_cap * valor_uf),
        "mejor_plazo": mejor_plazo,
        "recomendacion_ia": recomendacion,
    }


# ---------------------------------------------------------------------------
# comparar-competidores
# ---------------------------------------------------------------------------
BANCOS = [
    ("Banco Estado", 0.0490),
    ("Banco de Chile", 0.0475),
    ("Santander", 0.0468),
    ("BCI", 0.0472),
    ("Scotiabank", 0.0480),
    ("Itau", 0.0485),
]


def comparar_competidores(d: dict, seguros: dict, valor_uf: float) -> dict:
    monto = float(d.get("monto_credito_uf") or 0)
    plazo = int(d.get("plazo_anos") or 30)
    pie_pct = float(d.get("pie_pct") or 20)
    tasa_mut = float(d.get("tasa_mutuaria") or 6.5)
    div_mut_clp = float(d.get("dividendo_mutuaria_clp") or 0)
    if div_mut_clp <= 0:
        div_mut_clp = round(dividendo(monto, tasa_mut / 100, plazo) * valor_uf)

    competidores = []
    for banco, tasa in BANCOS:
        dv_uf = dividendo(monto, tasa, plazo)
        competidores.append({
            "banco": banco,
            "tasa": round(tasa * 100, 2),
            "dividendo_clp": round(dv_uf * valor_uf),
        })
    tasas_bancos = [c["tasa"] for c in competidores]
    tasa_prom = round(sum(tasas_bancos) / len(tasas_bancos), 2)
    dif = round(sum(c["dividendo_clp"] for c in competidores) / len(competidores) - div_mut_clp)

    return {
        "datos_comparacion": {
            "monto_credito_uf": round(monto, 1),
            "plazo_anos": plazo,
            "pie_pct": round(pie_pct),
        },
        "resumen": {
            "tasa_mutuaria": round(tasa_mut, 2),
            "tasa_promedio_bancos": tasa_prom,
            "diferencia_dividendo_mensual": dif,
        },
        "competidores": competidores,
        "mensaje_comercial": {
            "titular": "Tu credito con Central Mutuos",
            "subtitulo": "Comparativa referencial de dividendo mensual incluyendo seguros de desgravamen e incendio.",
            "puntos_clave": [
                "Asesoria personalizada durante todo el proceso",
                "Gestion directa con multiples instituciones",
                "Seguros con cobertura completa incluidos en el dividendo",
            ],
            "conclusion": "Elige la opcion que mejor se ajuste a tu presupuesto mensual.",
        },
    }



# ═══════════════════════════════════════════════════════════════════════════
# ALGORITMO ESPEJO MESA — Ingeniería inversa por regresión sobre el
# comportamiento real de los evaluadores (no reglas fijas). Se re-entrena
# cada 24h para reflejar el "humor" del mercado.
# ═══════════════════════════════════════════════════════════════════════════
def _regresion_lineal(xs, ys):
    """Mínimos cuadrados: y = a*x + b. Devuelve (a, b, r2)."""
    n = len(xs)
    if n < 2:
        return 0.0, (ys[0] if ys else 0.0), 0.0
    sx, sy = sum(xs), sum(ys)
    sxy = sum(x * y for x, y in zip(xs, ys))
    sxx = sum(x * x for x in xs)
    den = n * sxx - sx * sx
    if den == 0:
        return 0.0, sy / n, 0.0
    a = (n * sxy - sx * sy) / den
    b = (sy - a * sx) / n
    my = sy / n
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (a * x + b)) ** 2 for x, y in zip(xs, ys))
    r2 = (1 - ss_res / ss_tot) if ss_tot > 0 else 1.0
    return a, b, max(0.0, min(1.0, r2))


def entrenar_espejo_mesa(casos):
    """RECONSTRUCCIÓN COMPLETA DEL ALGORITMO MESA (regresión segmentada jerárquica).

    Variable base: renta disponible = (renta titular + renta codeudor) −
    (cuota CMF 2% + crédito interno PAV). Se entrena UNA regresión por cada
    combinación de criterios (tipo de codeudor × subsidio × tramo de edad) y
    en cascada hacia segmentos más generales cuando falta muestra. Así el
    Espejo captura los cortes silenciosos de la MESA por cada ápice de criterio.
    """
    casos = [c for c in (casos or [])
             if c.get("renta_disponible_clp", c.get("renta_liquida_clp", 0)) > 0
             and c.get("tope_uf", 0) > 0]
    n = len(casos)

    def _x(c):
        return float(c.get("renta_disponible_clp") or c.get("renta_liquida_clp")) / 1_000_000

    def _niveles(c):
        cod = c.get("codeudor_tipo") or ("con_codeudor" if c.get("con_codeudor") else "ninguno")
        sub = "sub" if c.get("con_subsidio") else "nosub"
        edad = c.get("edad_bucket") or "s/i"
        return [f"{cod}|{sub}|{edad}", f"{cod}|{sub}", f"{cod}", "GLOBAL"]

    def _entrenar(grupo):
        xs = [_x(c) for c in grupo]
        ys = [float(c["tope_uf"]) for c in grupo]
        a, b, r2 = _regresion_lineal(xs, ys)
        errs = [abs((a * x + b) - y) / y for x, y in zip(xs, ys) if y > 0]
        mape = (sum(errs) / len(errs)) if errs else 0.0
        return {"a": round(a, 4), "b": round(b, 2), "r2": round(r2, 3), "n": len(grupo),
                "mape_pct": round(mape * 100, 1),
                "precision_pct": round(max(0.0, min(1.0, 1 - mape)) * 100)}

    segmentos = {}
    for c in casos:
        for seg in _niveles(c):
            segmentos.setdefault(seg, []).append(c)
    modelo_segs = {seg: _entrenar(grupo) for seg, grupo in segmentos.items()}
    glob = modelo_segs.get("GLOBAL") or {"precision_pct": 0, "n": 0}
    return {
        "n": n, "listo": n >= 2,
        "segmentos": modelo_segs,
        "dimensiones": ["codeudor_tipo (ninguno/familiar/tercero)", "con_subsidio",
                        "edad_bucket (<40 / 40_59 / 60+)",
                        "renta_disponible = renta conjunta − (CMF 2% + PAV)"],
        "precision_pct": glob.get("precision_pct", 0),
        "r2": glob.get("r2", 0), "mape_pct": glob.get("mape_pct"),
        "cobertura_segmentos": len([s for s in modelo_segs if s != "GLOBAL"]),
        "nota": None if n >= 2 else
        "Datos insuficientes: el Espejo se calibra al acumular aprobaciones con renta y monto.",
    }


def simular_como_mesa(features, modelo):
    """Veredicto del Algoritmo Espejo: busca el segmento MÁS específico que
    coincida con los criterios del cliente (codeudor/subsidio/edad) y con
    muestra suficiente; si no, cae en cascada a segmentos más generales."""
    modelo = modelo or {}
    segs = modelo.get("segmentos") or {}
    if not modelo.get("listo") or not segs:
        return {"disponible": False, "precision_pct": modelo.get("precision_pct", 0),
                "n": modelo.get("n", 0),
                "nota": modelo.get("nota") or "Espejo en calibración (re-entrena cada 24h)"}
    f = features or {}
    renta_total = _n(f.get("renta_liquida_clp")) + _n(f.get("renta_codeudor_clp"))
    renta_disp = max(0.0, renta_total - _n(f.get("endeudamiento_mensual_clp")))
    if renta_disp <= 0:
        return {"disponible": False, "nota": "Sin renta disponible para proyectar el Espejo"}
    cod = f.get("codeudor_tipo") or ("con_codeudor" if f.get("con_codeudor") else "ninguno")
    sub = "sub" if f.get("con_subsidio") else "nosub"
    edad = f.get("edad_bucket") or ("60+" if f.get("edad_mayor_60") else "s/i")
    cascada = [f"{cod}|{sub}|{edad}", f"{cod}|{sub}", f"{cod}", "GLOBAL"]
    elegido, seg_id = None, "GLOBAL"
    for sid in cascada:
        s = segs.get(sid)
        if s and s["n"] >= (3 if sid != "GLOBAL" else 2):
            elegido, seg_id = s, sid
            break
    if not elegido:
        elegido, seg_id = segs.get("GLOBAL"), "GLOBAL"
    if not elegido:
        return {"disponible": False, "nota": "Espejo sin segmento entrenado"}
    x = renta_disp / 1_000_000
    monto = max(0.0, elegido["a"] * x + elegido["b"])
    return {"disponible": True, "monto_uf": round(monto, 1),
            "precision_pct": elegido.get("precision_pct", 0),
            "n": elegido.get("n", 0), "segmento": seg_id,
            "renta_disponible_clp": round(renta_disp),
            "r2": elegido.get("r2"), "n_total_modelo": modelo.get("n", 0)}
