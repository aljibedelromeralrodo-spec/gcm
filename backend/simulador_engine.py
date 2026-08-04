"""Motor de cálculo del Simulador Inmobiliario VIP (José Martín).
Recibe la base calibrada con la MESA (Calibración de Riesgo) y devuelve
viabilidad + veredicto + consejos con la voz de José Martín Benavente."""


def _num(v):
    try:
        return float(str(v or 0).replace(".", "").replace(",", "."))
    except ValueError:
        return 0.0


def calcular_viabilidad(payload, base_mesa=0.85, uf_hoy=39000):
    """base_mesa: fracción 0-1 calibrada con respuestas reales de la mesa."""
    valor, monto = _num(payload.get("valor_propiedad")), _num(payload.get("monto_credito"))
    renta, deudas = _num(payload.get("renta")), _num(payload.get("deudas"))
    con_sub = bool(payload.get("con_subsidio"))
    if monto <= 0 or valor <= 0:
        raise ValueError("Indica valor de la propiedad y monto del crédito (UF)")
    base = float(base_mesa) * 100.0
    prob, factores = base, [f"Base calibrada con la mesa: {round(base)}%"]
    alerta = ""
    if monto < 2000 and not con_sub:
        alerta = "ALERTA: No cumple criterio mínimo de 2.000 UF sin subsidio. Avisar a jefatura."
        factores.append(f"🔴 {alerta}")
    ltv = monto / valor if valor else 1
    if ltv <= 0.8:
        prob += 8
        factores.append(f"+8%: financiamiento del {round(ltv*100)}% (pie sano)")
    elif ltv <= 0.9:
        prob += 2
        factores.append(f"+2%: financiamiento del {round(ltv*100)}%")
    else:
        prob -= 10
        factores.append(f"-10%: financiamiento del {round(ltv*100)}% (pie muy bajo)")
    if con_sub:
        prob += 6
        factores.append("+6%: cuenta con subsidio habitacional")
    cuota_clp, carga = None, None
    if renta > 0:
        r_m = 0.046 / 12
        cuota_uf = monto * r_m / (1 - (1 + r_m) ** -360)
        cuota_clp = cuota_uf * uf_hoy
        carga = (cuota_clp + deudas) / renta
        if carga <= 0.28:
            prob += 12
            factores.append(f"+12%: carga financiera {round(carga*100)}% de la renta (excelente)")
        elif carga <= 0.40:
            prob += 3
            factores.append(f"+3%: carga financiera {round(carga*100)}% (aceptable)")
        else:
            prob -= 18
            factores.append(f"-18%: carga financiera {round(carga*100)}% (sobre el 40% la mesa rechaza)")
    else:
        prob -= 5
        factores.append("-5%: sin renta informada la mesa no puede medir capacidad de pago")
    prob = max(3, min(97, round(prob)))
    if alerta:
        prob = min(prob, 10)
    return {"porcentaje": prob, "factores": factores, "alerta_critica": alerta,
            "cuota_estimada_clp": round(cuota_clp) if cuota_clp else None,
            "carga": carga, "ltv": ltv, "con_subsidio": con_sub,
            "veredicto": veredicto_jose_martin(prob, alerta),
            "consejo": consejo_jose_martin(prob, ltv, carga, con_sub, monto),
            "puede_abrir_carpeta": prob > 70,
            "puede_abrir_expediente": prob >= 75}


def veredicto_jose_martin(prob, alerta=""):
    if alerta:
        return "Alto ahí ✋: bajo 2.000 UF sin subsidio la mesa no lo evalúa. Subamos el monto o traigamos el subsidio, ¡y lo damos vuelta!"
    if prob >= 85:
        return f"¡Hola! José Martín por acá 👋. Según mis cálculos, este crédito tiene un {prob}% de éxito. ¡Vamos con todo, mi amor por los números no me falla!"
    if prob >= 70:
        return f"José Martín al habla. Un {prob}% de probabilidad: esto viene regio, muy bien encaminado. ¡Hagámoslo!"
    if prob >= 40:
        return f"Ojo, un {prob}%. Se puede, pero ajustemos el pie o las deudas antes de presentar. Conversemos, que yo sé cómo darle brillo."
    return f"Te seré franco, cariño: con estos números llegamos a un {prob}%. Mejor ajustar el monto o sumar subsidio antes de golpear la puerta de la mesa."


def consejo_jose_martin(prob, ltv, carga, con_sub, monto):
    """Consejo financiero dinámico en tiempo real según los inputs."""
    if carga is not None and carga > 0.40:
        return "💡 Consejo de José Martín: tu carga pasa del 40% de la renta. Bajemos deudas o sumemos un complemento de renta, ¡y esto despega!"
    if ltv > 0.9:
        return "💡 Consejo de José Martín: con esta renta estamos rozando el éxito, ¡ajustemos el pie! Con un 10-20% de pie la mesa te mira con otros ojos."
    if not con_sub and monto < 2500:
        return "💡 Consejo de José Martín: si calificas a subsidio DS19/DS1, actívalo — son puntos de aprobación gratis."
    if carga is not None and carga <= 0.28 and prob >= 85:
        return "💡 José Martín dice: números de lujo, perfil de portada. Abre tu expediente VIP y déjame el resto a mí."
    return "💡 José Martín dice: buen punto de partida. Completa tu expediente y le sacamos brillo a tu carpeta."
