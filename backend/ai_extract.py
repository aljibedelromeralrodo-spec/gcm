"""Extraccion de campos con IA (Emergent LLM key) desde texto OCR de documentos
de gestion de credito hipotecario. Clasifica tipo de documento y extrae campos
estructurados en JSON.
"""
import os
import re
import json
import uuid

TIPOS = ["cedula", "liquidacion", "cotizacion_afp", "certificado_afp",
         "certificado_smf", "boleta_honorarios", "impuesto_renta",
         "simulacion", "carta_aprobacion", "otro"]


def _rut_regex(texto):
    m = re.search(r"\b(\d{1,2}\.?\d{3}\.?\d{3}\-?[\dkK])\b", texto or "")
    return m.group(1) if m else ""


def _fallback_clasificar(texto, filename=""):
    t = (texto + " " + filename).lower()
    reglas = [
        ("cedula", r"c[eé]dula de identidad|rep[uú]blica de chile|servicio de registro civil"),
        ("liquidacion", r"liquidaci[oó]n de (remuneraci|sueldo)|haberes|l[ií]quido a pagar"),
        ("cotizacion_afp", r"cotizaci|afp|capital|provida|habitat|planvital|cuprum|modelo|uno"),
        ("certificado_afp", r"certificado.*afp|certificado de afiliaci"),
        ("certificado_smf", r"informe de deudas|cmf|sbif|deuda consolidada"),
        ("boleta_honorarios", r"boleta de honorarios|honorarios electr"),
        ("impuesto_renta", r"impuesto a la renta|declaraci[oó]n de renta|formulario 22|sii"),
        ("simulacion", r"simulaci[oó]n|dividendo|gastos operacionales"),
        ("carta_aprobacion", r"agrado de informar|ha sido aprobad|carta de aprobaci"),
    ]
    for tipo, pat in reglas:
        if re.search(pat, t):
            return tipo
    return "otro"


async def clasificar_y_extraer(texto, filename=""):
    """Devuelve dict con tipo_documento, nombre_cliente, rut y campos de gestion."""
    texto = (texto or "")[:6000]
    key = os.environ.get("EMERGENT_LLM_KEY", "")
    base = {
        "tipo_documento": _fallback_clasificar(texto, filename),
        "nombre_cliente": "",
        "rut": _rut_regex(texto),
        "proyecto_inmobiliario": "",
        "ejecutivo_externo": "",
        "ejecutivo_interno": "",
        "monto_credito_uf": None,
        "monto_subsidio_uf": None,
        "con_subsidio": None,
        "confianza": 0.4,
        "metodo": "reglas",
    }
    if not key or len(texto) < 20:
        return base
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        system = (
            "Eres un asistente experto en documentos de credito hipotecario chileno. "
            "Recibes el texto (posiblemente de OCR) de UN documento y debes responder "
            "SOLO con un objeto JSON valido, sin texto adicional, con estas claves: "
            "tipo_documento (uno de: " + ", ".join(TIPOS) + "), "
            "nombre_cliente (string), rut (string formato chileno o ''), "
            "proyecto_inmobiliario (string), ejecutivo_externo (string), "
            "ejecutivo_interno (string), monto_credito_uf (numero o null), "
            "monto_subsidio_uf (numero o null), con_subsidio (true/false/null), "
            "confianza (0 a 1). Si un dato no aparece, usa '' o null."
        )
        chat = LlmChat(api_key=key, session_id=f"extract-{uuid.uuid4()}",
                       system_message=system).with_model("openai", "gpt-5.4-mini")
        resp = await chat.send_message(UserMessage(text=f"Nombre de archivo: {filename}\n\nTexto:\n{texto}"))
        raw = resp if isinstance(resp, str) else str(resp)
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            data = json.loads(m.group(0))
            base.update({k: data.get(k, base.get(k)) for k in base if k in data})
            if data.get("tipo_documento") in TIPOS:
                base["tipo_documento"] = data["tipo_documento"]
            base["rut"] = data.get("rut") or base["rut"] or _rut_regex(texto)
            base["metodo"] = "ia"
            base["confianza"] = float(data.get("confianza", 0.8) or 0.8)
    except Exception as e:
        base["metodo"] = "reglas_fallback"
        base["error"] = str(e)[:200]
    return base
