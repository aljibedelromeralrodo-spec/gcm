"""Cerebro Predictivo DashAI — 100% local, sin créditos de nube.
Minería del historial real de la MESA (aprobaciones@centralmutuos.cl) y
recalibración automática en segundo plano (aprendizaje continuo)."""
import os
import re
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

VENTANA_DIAS = 180
_cli = None


def _db():
    global _cli
    if _cli is None:
        _cli = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    return _cli


def _analisis_60(db, base180):
    """FOCO 60 DÍAS: cruza aprobaciones/rechazos recientes con el reglamento BTG/Ameris.
    Detecta si la MESA está más laxa o estricta que el papel → Ajustes de Mercado."""
    desde60 = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    q60 = {"fecha": {"$gte": desde60}}
    apro = list(db.seguimiento.find({"estado": {"$in": ["aprobacion", "aprobado"]}, **q60},
                                    {"cliente": 1}))
    rech = list(db.seguimiento.find({"estado": {"$in": ["rechazo", "rechazado"]}, **q60},
                                    {"cliente": 1, "asunto": 1}))
    total = len(apro) + len(rech)
    base60 = (len(apro) / total) if total else base180
    crit = db.config.find_one({"_key": "criterios"}) or {}
    btg = (crit.get("btg_pactual") or {}).get("sin_subsidio") or {}
    ltv_max = float(btg.get("ltv_max") or 0.9)
    div_max = float(btg.get("div_renta_max") or btg.get("div_renta_max_sin_codeudor") or 0.30)
    ajustes = []
    ltv_sobre, div_sobre = [], []
    for s in apro:
        cli = (s.get("cliente") or "").strip()[:20]
        if not cli:
            continue
        sim = db.simulaciones.find_one(
            {"nombre_completo": {"$regex": re.escape(cli), "$options": "i"}},
            sort=[("timestamp", -1)])
        if not sim:
            continue
        ltv = float(sim.get("ltv") or 0)
        divr = float(sim.get("div_renta_individual") or 0)
        if ltv > ltv_max:
            ltv_sobre.append(ltv)
        if divr > div_max:
            div_sobre.append(divr)
    if ltv_sobre:
        ajustes.append(f"MESA más laxa en LTV: aprobó hasta {round(max(ltv_sobre)*100)}% "
                       f"(papel: {round(ltv_max*100)}%) → Ajuste de Mercado sugerido: "
                       f"ltv_max {round(max(ltv_sobre), 2)}")
    if div_sobre:
        ajustes.append(f"MESA más laxa en Dividendo/Renta: aprobó hasta {round(max(div_sobre)*100, 1)}% "
                       f"(papel: {round(div_max*100)}%) → Ajuste de Mercado sugerido: "
                       f"div_renta_max {round(max(div_sobre), 2)}")
    if base60 < base180 - 0.08:
        ajustes.append(f"MESA más estricta que el histórico: tasa 60d {round(base60*100)}% vs "
                       f"180d {round(base180*100)}% → revisar carpetas límite antes de enviar")
    # Tendencia: qué criterio pesa más en los rechazos recientes
    CATS = {"carga financiera": r"carga\s*financiera|endeuda", "renta mínima": r"renta",
            "LTV/financiamiento": r"ltv|financiamiento|pie", "antigüedad laboral": r"antig|laboral",
            "monto del crédito": r"monto|2\.?000\s*UF"}
    cuenta = {k: 0 for k in CATS}
    textos = [a for s in rech for a in [(s.get("asunto") or "")]]
    for sim in db.simulaciones.find({"razones_rechazo": {"$ne": []},
                                     "timestamp": {"$gte": desde60}}, {"razones_rechazo": 1}):
        textos.extend(sim.get("razones_rechazo", []))
    for t in textos:
        for k, rx in CATS.items():
            if re.search(rx, t, re.I):
                cuenta[k] += 1
    top = sorted(cuenta.items(), key=lambda kv: -kv[1])
    if top and top[0][1] > 0:
        segundo = top[1][0] if len(top) > 1 and top[1][1] > 0 else "los demás criterios"
        tendencia = (f"Tendencia últimos 60 días: La MESA está priorizando {top[0][0]} "
                     f"sobre {segundo} ({top[0][1]} casos analizados).")
    else:
        tendencia = ("Tendencia últimos 60 días: La MESA mantiene consistencia con el "
                     "reglamento BTG/Ameris — sin desviaciones detectadas.")
    return {"base": round(base60, 4), "aprobadas": len(apro), "rechazadas": len(rech),
            "ajustes_mercado": ajustes, "tendencia": tendencia}


def calibrar():
    """Minería local de 180 días: patrones de éxito y motivos de rechazo de la MESA."""
    db = _db()
    desde = (datetime.now(timezone.utc) - timedelta(days=VENTANA_DIAS)).isoformat()
    q_fecha = {"fecha": {"$gte": desde}}
    apro = db.seguimiento.count_documents({"estado": {"$in": ["aprobacion", "aprobado"]}, **q_fecha})
    rech = db.seguimiento.count_documents({"estado": {"$in": ["rechazo", "rechazado"]}, **q_fecha})
    total = apro + rech
    base = (apro / total) if total else 0.85
    motivos = {}
    for s in db.simulaciones.find({"razones_rechazo": {"$exists": True, "$ne": []}},
                                  {"razones_rechazo": 1}):
        for r0 in s.get("razones_rechazo", []):
            clave = re.sub(r"[\d.,%]+", "X", r0).strip()
            motivos[clave] = motivos.get(clave, 0) + 1
    for s in db.seguimiento.find({"estado": {"$in": ["rechazo", "rechazado"]}, **q_fecha},
                                 {"asunto": 1}):
        m = re.search(r"rechaz\w*\s*[:\-—]\s*(.{5,80})", s.get("asunto") or "", re.I)
        if m:
            k = m.group(1).strip()
            motivos[k] = motivos.get(k, 0) + 1
    top = sorted(motivos.items(), key=lambda kv: -kv[1])[:8]
    modelo = {"_key": "mesa_brain_modelo", "ventana_dias": VENTANA_DIAS,
              "base": round(base, 4), "aprobadas": apro, "rechazadas": rech,
              "muestras": total,
              "motivos_rechazo": [{"motivo": k, "casos": v} for k, v in top],
              "calibrado_en": datetime.now(timezone.utc).isoformat()}
    # CALIBRACIÓN PRIORITARIA: ventana de 60 días = Regla de Oro del Contralor
    modelo["ventana_60"] = _analisis_60(db, base)
    modelo["tendencia"] = modelo["ventana_60"]["tendencia"]
    modelo["ajustes_mercado"] = modelo["ventana_60"]["ajustes_mercado"]
    db.config.replace_one({"_key": "mesa_brain_modelo"}, modelo, upsert=True)
    return modelo


def modelo_actual(max_age_horas=24):
    """Modelo vigente; recalibra solo si venció (MODO APRENDIZAJE CONTINUO, costo cero)."""
    m = _db().config.find_one({"_key": "mesa_brain_modelo"}, {"_id": 0})
    if m:
        try:
            edad = datetime.now(timezone.utc) - datetime.fromisoformat(m["calibrado_en"])
            if edad.total_seconds() < max_age_horas * 3600:
                return m
        except Exception:
            return m
    return calibrar()


# ══════════════════════════════════════════════════════════════════════════
# 🏛 CONTRALORÍA SUPREMA — Auditoría 360° (Reglas de Bodega + Aprendizaje)
# ══════════════════════════════════════════════════════════════════════════
# Regla inviolable del dueño: SIN SUBSIDIO el crédito mínimo es 2.000 UF.
MONTO_MIN_UF_SIN_SUBSIDIO_HARD = 2000


def _num(x, d=0.0):
    try:
        return float(x)
    except Exception:
        return d


def _criterios():
    return _db().config.find_one({"_key": "criterios"}) or {}


def recalibrar_renta(sim, folder, castigos):
    """RECALIBRACIÓN DE INGRESOS — aplica los castigos del reglamento sobre la renta y
    descarta horas extra / asignaciones no imponibles. Devuelve dict con detalle y notas.
    Degrada con nota honesta si no hay desglose de renta en los documentos."""
    df = (folder or {}).get("datos_financieros") or {}
    cr = (folder or {}).get("credit_request") or {}
    renta_fija = _num(df.get("renta_liquida") or df.get("renta_fija") or cr.get("renta_liquida"))
    renta_variable = _num(df.get("renta_variable") or df.get("bonos_variables"))
    honorarios = _num(df.get("honorarios") or df.get("renta_honorarios"))
    horas_extra = _num(df.get("horas_extra"))
    no_imponibles = _num(df.get("asignaciones_no_imponibles") or df.get("movilizacion_colacion"))
    castigo_var = _num((castigos or {}).get("renta_variable_castigo"), 0.15)
    castigo_hon = _num((castigos or {}).get("honorarios_castigo"), 0.20)
    if not (renta_fija or renta_variable or honorarios):
        return {"disponible": False,
                "nota": ("No hay desglose de renta líquida en la ficha/documentos parseados. "
                         "Cargue las liquidaciones para recalibrar la renta con castigos reglamentarios."),
                "renta_reconocida": None, "descartado": [], "castigos": []}
    detalle_castigos = []
    renta_var_castigada = renta_variable * (1 - castigo_var)
    if renta_variable:
        detalle_castigos.append(f"Renta variable ${int(renta_variable):,} castigada −{int(castigo_var*100)}% → ${int(renta_var_castigada):,}")
    honorarios_castigados = honorarios * (1 - castigo_hon)
    if honorarios:
        detalle_castigos.append(f"Honorarios ${int(honorarios):,} castigados −{int(castigo_hon*100)}% → ${int(honorarios_castigados):,}")
    descartado = []
    if horas_extra:
        descartado.append(f"Horas extra ${int(horas_extra):,} (no imponible reglamentario)")
    if no_imponibles:
        descartado.append(f"Asignaciones no imponibles ${int(no_imponibles):,}")
    renta_reconocida = renta_fija + renta_var_castigada + honorarios_castigados
    return {"disponible": True, "renta_reconocida": round(renta_reconocida),
            "renta_declarada": round(renta_fija + renta_variable + honorarios + horas_extra + no_imponibles),
            "castigos": detalle_castigos, "descartado": descartado,
            "nota": "Renta líquida recalibrada según reglamento (castigos + descarte de no imponibles)."}


def auditar_caso(folder, sim, respuesta_mesa, modelo=None):
    """AUDITORÍA 360° de una decisión de la MESA. Devuelve un Certificado de Auditoría Interna
    con secciones (Reglas de Bodega, Recalibración de Ingresos, Aprendizaje, Integridad de Plazos),
    lista de violaciones y veredicto/estado. Detecta RIESGO DE FALSO POSITIVO."""
    from datetime import datetime, timezone
    crit = _criterios()
    modelo = modelo or {}
    folder = folder or {}
    sim = sim or {}
    df = folder.get("datos_financieros") or {}
    con_subsidio = bool(df.get("con_subsidio"))
    btg = (crit.get("btg_pactual") or {}).get("con_subsidio" if con_subsidio else "sin_subsidio") or {}
    castigos = (crit.get("btg_pactual") or {}).get("castigos_renta") or {}

    monto = _num(df.get("monto_credito") or sim.get("credito_solicitado_uf") or sim.get("credito_maximo_uf"))
    ltv = _num(sim.get("ltv"))
    tiene_cod = bool(sim.get("tiene_codeudor"))
    divr = _num(sim.get("div_renta_conjunta") if tiene_cod else sim.get("div_renta_individual"))
    carga = _num(sim.get("carga_fin_conjunta") if tiene_cod else sim.get("carga_fin_individual"))
    edad_plazo = _num(sim.get("edad_plazo"))
    plazo = _num(sim.get("plazo_anos"))

    violaciones = []
    secciones = []

    # ── 0. ⚔️ REGLAS DE HIERRO (Políticas Maestras — BLOQUEADAS) ──────────
    pol = politicas_maestras()
    quiebres_hierro = evaluar_politicas_generales(folder, sim)
    quebradas = {q["regla"] for q in quiebres_hierro}
    items_hierro = [
        {"regla": "Antigüedad laboral mínima", "real": "quiebre detectado" if "Antigüedad laboral" in quebradas else "cumple/sin dato",
         "esperado": f"≥ {pol['antiguedad_minima_meses']} meses", "ok": "Antigüedad laboral" not in quebradas},
        {"regla": "Edad máxima al término del crédito", "real": "quiebre detectado" if "Edad máxima crédito" in quebradas else "cumple/sin dato",
         "esperado": f"≤ {pol['edad_maxima_credito']} años", "ok": "Edad máxima crédito" not in quebradas},
        {"regla": "Morosidad", "real": "MOROSO" if "Morosidad" in quebradas else "sin morosidad detectada",
         "esperado": "NO permitida", "ok": "Morosidad" not in quebradas},
        {"regla": "Carga financiera máxima", "real": "quiebre detectado" if "Carga financiera" in quebradas else "cumple/sin dato",
         "esperado": f"≤ {pol['carga_financiera_maxima']*100:.0f}%", "ok": "Carga financiera" not in quebradas},
        {"regla": "LTV máximo base", "real": "quiebre detectado" if "LTV máximo" in quebradas else "cumple/sin dato",
         "esperado": f"≤ {pol['ltv_maximo_base']*100:.0f}%", "ok": "LTV máximo" not in quebradas},
    ]
    for q in quiebres_hierro:
        violaciones.append({"regla": f"⚔️ REGLA DE HIERRO · {q['regla']}",
                            "detalle": f"POLÍTICA GENERAL QUEBRADA: {q['detalle']}", "critico": True})
    secciones.append({"titulo": "⚔️ Reglas de Hierro · Políticas Maestras (bloqueadas)",
                      "items": items_hierro,
                      "nota": "Cualquier quiebre = NO VIABLE - POLÍTICA GENERAL (viabilidad 0%). La IA no puede ponderarlas."})

    # ── 1. REGLAS DE BODEGA (BTG/Ameris) ──────────────────────────────────
    reglas = []

    def _chk(nombre, real, cmp_ok, esperado, critico=False):
        reglas.append({"regla": nombre, "real": real, "esperado": esperado, "ok": cmp_ok})
        if not cmp_ok:
            violaciones.append({"regla": nombre, "detalle": f"{nombre}: {real} (límite {esperado})",
                                "critico": critico})

    # Regla dura 2.000 UF sin subsidio (INVIOLABLE)
    if not con_subsidio and monto:
        ok = monto >= MONTO_MIN_UF_SIN_SUBSIDIO_HARD
        _chk("Monto mínimo SIN subsidio (regla inviolable 2.000 UF)",
             f"{monto:.0f} UF", ok, f"≥ {MONTO_MIN_UF_SIN_SUBSIDIO_HARD} UF", critico=True)

    ltv_max = _num(btg.get("ltv_max"), 0.9 if not con_subsidio else 0.8)
    if ltv:
        _chk("LTV / Financiamiento", f"{ltv*100:.0f}%", ltv <= ltv_max + 1e-6, f"≤ {ltv_max*100:.0f}%")
    div_max = _num(btg.get("div_renta_max_sin_codeudor") or btg.get("div_renta_max"), 0.30)
    if tiene_cod:
        div_max = _num(btg.get("div_renta_max_con_codeudor_conjunto") or btg.get("div_renta_max") or div_max, div_max)
    if divr:
        _chk("Dividendo / Renta", f"{divr*100:.1f}%", divr <= div_max + 1e-6, f"≤ {div_max*100:.0f}%")
    carga_max = _num(btg.get("carga_financiera_max") or btg.get("carga_financiera_max_sin_codeudor") or btg.get("carga_fin_max"), 0.40)
    if carga:
        _chk("Carga financiera", f"{carga*100:.1f}%", carga <= carga_max + 1e-6, f"≤ {carga_max*100:.0f}%")
    edad_plazo_max = _num(btg.get("edad_plazo_max") or btg.get("edad_termino_max"), 80)
    if edad_plazo:
        _chk("Edad + Plazo al término", f"{edad_plazo:.0f} años", edad_plazo <= edad_plazo_max, f"< {edad_plazo_max:.0f}")
    mmin = _num(btg.get("monto_credito_min_uf"))
    mmax = _num(btg.get("monto_credito_max_uf"))
    if monto and mmax:
        _chk("Monto crédito en rango bodega", f"{monto:.0f} UF",
             (monto >= mmin if mmin else True) and monto <= mmax, f"{mmin:.0f}–{mmax:.0f} UF")
    secciones.append({"titulo": "Reglas de Bodega · BTG/Ameris", "items": reglas})

    # ── 2. RECALIBRACIÓN DE INGRESOS ──────────────────────────────────────
    renta = recalibrar_renta(sim, folder, castigos)
    items_renta = []
    if renta["disponible"]:
        items_renta.append({"regla": "Renta líquida reconocida (post castigos)",
                            "real": f"${renta['renta_reconocida']:,}", "esperado": "vs. declarada", "ok": True})
        for c in renta["castigos"]:
            items_renta.append({"regla": "Castigo aplicado", "real": c, "esperado": "reglamento", "ok": True})
        for d in renta["descartado"]:
            items_renta.append({"regla": "Descartado del cálculo", "real": d, "esperado": "no imponible", "ok": True})
    else:
        items_renta.append({"regla": "Recalibración de renta", "real": renta["nota"], "esperado": "liquidaciones", "ok": None})
    secciones.append({"titulo": "Recalibración de Ingresos (castigos −15% variable / −20% honorarios)",
                      "items": items_renta, "nota": renta["nota"]})

    # ── 3. LÓGICA DE APRENDIZAJE (patrones de rechazo históricos) ─────────
    aprendizaje = []
    # CMF: deudas no declaradas
    cmf_declara = df.get("deudas_cmf") if df.get("deudas_cmf") is not None else None
    tiene_cmf_doc = any("cmf" in ((a.get("subfolder", "") + a.get("nombre", "")) if isinstance(a, dict) else str(a)).lower()
                        for a in (folder.get("archivos") or []))
    if not tiene_cmf_doc:
        aprendizaje.append({"regla": "Informe CMF presente", "real": "No detectado", "esperado": "obligatorio", "ok": False})
        violaciones.append({"regla": "Informe CMF", "detalle": "Sin informe CMF: no se puede validar deuda no declarada (patrón histórico de rechazo)", "critico": False})
    # Bono variable vs renta fija (patrón aprendido)
    df_var = _num(df.get("renta_variable") or df.get("bonos_variables"))
    df_fija = _num(df.get("renta_liquida") or df.get("renta_fija"))
    if df_var and df_fija and df_var > df_fija * 0.4:
        aprendizaje.append({"regla": "Composición renta (variable vs fija)",
                            "real": f"variable {df_var/ (df_fija+df_var)*100:.0f}% del total", "esperado": "predominio de renta fija", "ok": False})
        violaciones.append({"regla": "Renta variable alta", "detalle": "Alta proporción de bono variable sobre renta fija (patrón histórico de rechazo)", "critico": False})
    # patrones del modelo aprendido
    for mo in (modelo.get("motivos_rechazo") or [])[:5]:
        aprendizaje.append({"regla": "Patrón histórico detectado", "real": f"{mo.get('motivo')} ({mo.get('casos')} casos)", "esperado": "referencia", "ok": None})
    secciones.append({"titulo": "Lógica de Aprendizaje · Dinámicas Detectadas", "items": aprendizaje})

    # ── 4. INTEGRIDAD DE PLAZOS ───────────────────────────────────────────
    plazos = []
    if edad_plazo:
        plazos.append({"regla": "Edad + Plazo < 80", "real": f"{edad_plazo:.0f}", "esperado": "< 80", "ok": edad_plazo < 80})
    plazo_max = _num(btg.get("plazo_max_anos"), 30)
    if plazo:
        coherente_carga = (carga <= carga_max + 1e-6) if carga else None
        plazos.append({"regla": "Plazo dentro de política", "real": f"{plazo:.0f} años", "esperado": f"≤ {plazo_max:.0f} años", "ok": plazo <= plazo_max})
        plazos.append({"regla": "Plazo coherente con capacidad de ahorro/carga",
                       "real": f"carga {carga*100:.1f}%" if carga else "sin dato de carga",
                       "esperado": f"carga ≤ {carga_max*100:.0f}%", "ok": coherente_carga})
        if coherente_carga is False:
            violaciones.append({"regla": "Plazo vs carga", "detalle": "El plazo otorgado no es coherente: la carga financiera supera el máximo (riesgo de sobreendeudamiento)", "critico": False})
    secciones.append({"titulo": "Integridad de Plazos", "items": plazos})

    # ── VEREDICTO Y DETECCIÓN DE SESGO MESA ───────────────────────────────
    criticas = [v for v in violaciones if v.get("critico")]
    n_viol = len(violaciones)
    aprobada = respuesta_mesa in ("aprobacion", "aprobado")
    if aprobada and criticas:
        estado = "RIESGO DE FALSO POSITIVO"
        veredicto = "INVIABLE según reglamento"
    elif aprobada and n_viol >= 2:
        estado = "BAJO AUDITORÍA"
        veredicto = "Aprobación con desviaciones"
    elif not aprobada:
        estado = "VALIDADO"
        veredicto = "Rechazo consistente con reglamento" if n_viol else "Rechazo (sin desviaciones detectadas)"
    else:
        estado = "VALIDADO"
        veredicto = "Aprobación consistente con reglamento"

    politica_saltada = [v["detalle"] for v in violaciones]

    return {
        "cliente": folder.get("nombre") or sim.get("nombre_completo") or "",
        "rut": folder.get("rut") or sim.get("rut") or "",
        "respuesta_mesa": "aprobacion" if aprobada else "rechazo",
        "con_subsidio": con_subsidio,
        "monto_uf": round(monto) if monto else None,
        "estado_auditoria": estado,
        "veredicto_dashai": veredicto,
        "secciones": secciones,
        "violaciones": violaciones,
        "criticas": criticas,
        "politica_saltada": politica_saltada,
        "certificado_id": f"CAI-{(folder.get('rut') or sim.get('rut') or 'SN').replace('.','').replace('-','')[:9]}-{datetime.now(timezone.utc).strftime('%Y%m%d')}",
        "generado_en": datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════
# ⚔️ REGLAS DE HIERRO — Políticas Maestras Generales (BLOQUEADAS, la IA no
# puede ignorarlas ni ponderarlas: cualquier quiebre = 0% viabilidad).
# ══════════════════════════════════════════════════════════════════════════
POLITICAS_MAESTRAS_DEFAULT = {
    "antiguedad_minima_meses": 12,
    "edad_maxima_credito": 80,
    "morosidad_permitida": False,
    "carga_financiera_maxima": 0.40,
    "ltv_maximo_base": 0.90,
}


def politicas_maestras():
    crit = _criterios()
    pol = dict(POLITICAS_MAESTRAS_DEFAULT)
    pol.update({k: v for k, v in (crit.get("politicas_maestras") or {}).items()
                if k in POLITICAS_MAESTRAS_DEFAULT and v is not None})
    return pol


def evaluar_politicas_generales(folder, sim=None):
    """Evalúa las 5 Reglas de Hierro. Devuelve lista de quiebres (vacía = cumple).
    Cada quiebre: {"regla", "detalle"}. Solo evalúa reglas con dato disponible."""
    pol = politicas_maestras()
    folder = folder or {}
    sim = sim or {}
    df = folder.get("datos_financieros") or {}
    cr = folder.get("credit_request") or {}
    quiebres = []
    # 1. Antigüedad laboral mínima
    antig = _num(df.get("antiguedad_laboral_meses") or df.get("antiguedad_meses")
                 or cr.get("antiguedad_laboral_meses"), -1)
    if antig >= 0 and antig < _num(pol["antiguedad_minima_meses"], 12):
        quiebres.append({"regla": "Antigüedad laboral",
                         "detalle": f"Antigüedad {antig:.0f} meses < mínimo {pol['antiguedad_minima_meses']} meses"})
    # 2. Edad máxima al término del crédito
    edad_term = _num(sim.get("edad_plazo") or df.get("edad_termino_credito"))
    if edad_term and edad_term > _num(pol["edad_maxima_credito"], 80):
        quiebres.append({"regla": "Edad máxima crédito",
                         "detalle": f"Edad al término {edad_term:.0f} años > máximo {pol['edad_maxima_credito']} años"})
    # 3. Morosidad no permitida
    moroso = df.get("morosidad") or df.get("moroso") or sim.get("morosidad") or cr.get("morosidad")
    if (not pol["morosidad_permitida"]) and bool(moroso):
        quiebres.append({"regla": "Morosidad",
                         "detalle": "Cliente registra morosidad vigente (política general: morosidad NO permitida)"})
    # 4. Carga financiera máxima
    carga = _num(sim.get("carga_fin_conjunta") if sim.get("tiene_codeudor") else sim.get("carga_fin_individual"))
    if not carga:
        carga = _num(df.get("carga_financiera"))
    cmax = _num(pol["carga_financiera_maxima"], 0.40)
    if carga and carga > cmax + 1e-6:
        quiebres.append({"regla": "Carga financiera",
                         "detalle": f"Carga financiera {carga*100:.1f}% > máximo {cmax*100:.0f}%"})
    # 5. LTV máximo base
    ltv = _num(sim.get("ltv") or df.get("ltv"))
    lmax = _num(pol["ltv_maximo_base"], 0.90)
    if ltv and ltv > lmax + 1e-6:
        quiebres.append({"regla": "LTV máximo",
                         "detalle": f"LTV {ltv*100:.1f}% > máximo base {lmax*100:.0f}%"})
    return quiebres


def quiebres_hierro_folder(folder):
    """Busca la última simulación del cliente y evalúa las Reglas de Hierro (sync)."""
    import re as _re
    folder = folder or {}
    sim = None
    try:
        d = _db()
        rut_f = _re.sub(r"[^0-9kK]", "", (folder.get("rut") or "")).lower()
        if rut_f:
            sim = d.simulaciones.find_one({"rut": {"$regex": rut_f[:8], "$options": "i"}},
                                          sort=[("timestamp", -1)])
        if not sim and folder.get("nombre"):
            sim = d.simulaciones.find_one(
                {"nombre_completo": {"$regex": _re.escape(folder["nombre"][:20]), "$options": "i"}},
                sort=[("timestamp", -1)])
    except Exception:
        pass
    return evaluar_politicas_generales(folder, sim)
