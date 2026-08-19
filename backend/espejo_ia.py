"""ANÁLISIS IA DEL ALGORITMO ESPEJO — Claude Sonnet 4.6 (Llave Universal Emergent).
Lee e interpreta correos de la empresa matriz: extrae datos estructurados, genera
resumen interpretativo ante ambigüedad y detecta urgencias (normativas, plazos, riesgo).
"""
import os
import json
import uuid
import logging
from datetime import datetime, timezone

MODELO = "claude-sonnet-4-6"

PROMPT_SISTEMA = """Eres el analista experto del Algoritmo Espejo de Central Mutuos (mercado hipotecario chileno).
Analizas correos de la empresa matriz sobre operaciones de crédito y extraes datos estructurados.

Responde ÚNICAMENTE con un JSON válido (sin markdown, sin texto extra) con esta estructura exacta:
{
  "nro_operacion": "número de operación si aparece, sino ''",
  "rut": "RUT del cliente si aparece (formato tal cual), sino ''",
  "estado": "estado de la operación normalizado: Aprobada|Rechazada|Cursada|Escriturada|Con Observaciones|En Estudio|Pendiente|'' ",
  "monto": "monto en UF o pesos tal como aparece, sino ''",
  "fecha": "fecha relevante mencionada en el texto (DD/MM/AAAA) o ''",
  "observaciones": "observaciones relevantes del correo, máx 300 caracteres",
  "requerimientos": ["lista de requerimientos o documentos solicitados, implícitos o explícitos"],
  "alertas": ["alertas de riesgo, plazos vencidos o menciones a normativas detectadas"],
  "urgente": true/false,
  "motivo_urgencia": "por qué es urgente (mención a normativas, plazos vencidos o riesgo), sino ''",
  "ambiguo": true/false,
  "resumen_interpretativo": "si el correo es ambiguo o incompleto, resumen interpretativo claro de 2-3 frases para el Contralor; si es claro, resumen ejecutivo de 1 frase"
}

REGLAS:
- urgente=true SOLO si hay mención a normativas, plazos vencidos, incumplimientos o alertas de riesgo.
- ambiguo=true si el lenguaje es confuso, faltan datos clave o hay información contradictoria.
- NO inventes datos: si algo no aparece en el correo, deja el campo vacío.
- Responde siempre en español."""


def _now():
    return datetime.now(timezone.utc).isoformat()


async def analizar_correo(asunto, cuerpo, fecha_correo=""):
    """Análisis Claude de un correo de la matriz → dict estructurado con marca de tiempo."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise ValueError("EMERGENT_LLM_KEY no configurada")
    chat = LlmChat(api_key=key, session_id=f"espejo-ia-{uuid.uuid4()}",
                   system_message=PROMPT_SISTEMA).with_model("anthropic", MODELO)
    texto = f"ASUNTO: {asunto or '(sin asunto)'}\nFECHA DEL CORREO: {fecha_correo or 'no indicada'}\n\nCUERPO:\n{(cuerpo or '')[:6000]}"
    resp = await chat.send_message(UserMessage(text=texto))
    _ctx_chars = len(texto)
    raw = str(resp).strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1].lstrip("json").strip()
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        ini, fin = raw.find("{"), raw.rfind("}")
        d = json.loads(raw[ini:fin + 1]) if ini >= 0 and fin > ini else {}
    if not isinstance(d, dict):
        d = {}
    return {
        "nro_operacion": str(d.get("nro_operacion") or "").strip(),
        "rut": str(d.get("rut") or "").strip(),
        "estado": str(d.get("estado") or "").strip(),
        "monto": str(d.get("monto") or "").strip(),
        "fecha": str(d.get("fecha") or "").strip(),
        "observaciones": str(d.get("observaciones") or "").strip()[:400],
        "requerimientos": [str(x)[:200] for x in (d.get("requerimientos") or []) if x][:10],
        "alertas": [str(x)[:200] for x in (d.get("alertas") or []) if x][:10],
        "urgente": bool(d.get("urgente")),
        "motivo_urgencia": str(d.get("motivo_urgencia") or "").strip()[:300],
        "ambiguo": bool(d.get("ambiguo")),
        "resumen_interpretativo": str(d.get("resumen_interpretativo") or "").strip()[:600],
        "modelo": MODELO, "analizado_en": _now(), "contexto_chars": _ctx_chars,
    }


async def registrar_interpretacion(db, ia, asunto, folder_id="", simulado=False):
    """Toda interpretación queda registrada con marca de tiempo (revisable por el Admin)."""
    reg = {"id": str(uuid.uuid4()), "fecha": _now(), "asunto": (asunto or "")[:200],
           "folder_id": folder_id or "", "simulado": bool(simulado), "accion": "analisis",
           "ia": ia}
    try:
        await db.espejo_ia_log.insert_one(dict(reg))
    except Exception as e:
        logging.warning(f"espejo_ia log: {e}")
    return reg["id"]
