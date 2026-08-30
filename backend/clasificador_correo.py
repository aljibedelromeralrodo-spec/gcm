"""Clasificador contextual de correos entrantes con Claude (Universal Key).
Reemplaza las reglas de palabras clave: cada correo se clasifica por CONTEXTO."""
import os
import re
import json
import uuid
import hashlib
import logging
from datetime import datetime, timezone
def _db():
    from database import db
    return db

CATEGORIAS = ("solicitud_nueva", "consulta_administrativa", "aprobacion_mesa",
              "rechazo_mesa", "peticion_documentos_mesa", "no_relacionado")

# Hitos del flujo (campo extra; NO reemplaza las 6 categorías constitucionales).
# Solo estos se capturan en cola además de solicitud_nueva.
HITOS = (
    "solicitud_credito", "aprobacion_mesa", "rechazo_mesa", "tasacion",
    "estudio_titulo", "escritura", "faltantes", "administrativo", "otro",
)
HITOS_CAPTURAR = frozenset((
    "solicitud_credito", "aprobacion_mesa", "rechazo_mesa", "tasacion",
    "estudio_titulo", "escritura", "faltantes",
))
HITO_LABELS = {
    "solicitud_credito": "Solicitud de crédito",
    "aprobacion_mesa": "Aprobación Mesa",
    "rechazo_mesa": "Rechazo Mesa",
    "tasacion": "Tasación",
    "estudio_titulo": "Estudio de títulos",
    "escritura": "Escritura",
    "faltantes": "Petición de documentos",
    "administrativo": "Administrativo",
    "otro": "Otro",
}

_RX_TASACION = re.compile(
    r"tasaci[oó]n|value\s*property|valueproperty|volvetproperty|avalu[oó]\s+comercial", re.I)
_RX_ESTUDIO = re.compile(
    r"estudio\s+de\s+t[ií]tulos?|estudio\s+titulo|mardones|majluf|mardluf|"
    r"inscripci[oó]n\s+de\s+dominio|cbr\b|conservador", re.I)
_RX_ESCRITURA = re.compile(
    r"escritur|notar[ií]a|repertorio|firma\s+de\s+escritura|confecci[oó]n\s+de\s+borrador", re.I)


def detectar_hito(categoria="", subject="", sender="", body="", adjuntos=None):
    """Hito operativo a partir de la categoría constitucional + texto (sin LLM)."""
    cat = (categoria or "").strip()
    if cat == "solicitud_nueva":
        return "solicitud_credito"
    if cat == "aprobacion_mesa":
        return "aprobacion_mesa"
    if cat == "rechazo_mesa":
        return "rechazo_mesa"
    if cat == "peticion_documentos_mesa":
        return "faltantes"
    txt = " ".join([
        subject or "", sender or "", body or "",
        " ".join(str(a) for a in (adjuntos or [])[:20]),
    ])
    if _RX_TASACION.search(txt):
        return "tasacion"
    if _RX_ESTUDIO.search(txt):
        return "estudio_titulo"
    if _RX_ESCRITURA.search(txt):
        return "escritura"
    if cat == "consulta_administrativa":
        return "administrativo"
    if cat == "no_relacionado":
        return "otro"
    return "otro"

_SISTEMA = (
    "Eres el clasificador de correos de Central Mutuos, corredora chilena de créditos "
    "hipotecarios (mutuos endosables). Recibes UN correo (remitente, asunto, cuerpo y nombres "
    "de adjuntos) y respondes SOLO un objeto JSON válido, sin texto adicional, con claves: "
    "categoria, confianza (0 a 1), cliente (nombre completo del cliente evaluado o ''), "
    "razon (una frase corta en español).\n\n"
    "CATEGORÍAS (elige exactamente una):\n"
    "1. solicitud_nueva — Una ejecutiva inmobiliaria (Ecomac, Boetsch, Maestra, etc.), una "
    "ejecutiva interna o un cliente envía ANTECEDENTES/DOCUMENTOS para evaluar el crédito de un "
    "cliente: liquidaciones de sueldo, cédula, certificado AFP, informe CMF, boletas de "
    "honorarios, declaración de renta. Asuntos típicos: 'SOLICITUD CREDITO MUTUO // NOMBRE', "
    "'EVALUAR ENTREGA INMEDIATA_NOMBRE_RUT', 'EVALUACION CLIENTE ...', 'Liquidaciones de ...', "
    "'SOLICITUD DE ANTECEDENTES ...'. Incluye RE:/RV:/Fwd: con documentación complementaria del "
    "cliente o de su codeudor/aval.\n"
    "2. aprobacion_mesa — Veredicto de la MESA (remitente aprobaciones@centralmutuos.cl) que "
    "APRUEBA: 'Tenemos el agrado de informar que el crédito solicitado califica para un mutuo "
    "hipotecario endosable', puede traer Carta_Aprobacion o Simulador adjuntos.\n"
    "3. rechazo_mesa — Veredicto de la MESA que RECHAZA: 'no cumple parámetros objetivos "
    "mínimos', 'muy pasado en carga financiera', 'ingresos no son suficientes', 'ingresos de "
    "sociedad SPA no podemos considerar'.\n"
    "4. peticion_documentos_mesa — La mesa u operaciones pide documentos adicionales o "
    "aclaraciones sobre un caso ya presentado: 'favor revisar', 'falta ...', 'necesitamos ...'.\n"
    "5. consulta_administrativa — Consultas generales, coordinación comercial, bases de "
    "clientes, temas administrativos u operativos SIN documentos de evaluación de un cliente.\n"
    "6. no_relacionado — Spam, marketing, newsletters, notificaciones automáticas de "
    "plataformas, temas ajenos al negocio hipotecario.\n\n"
    "REGLAS: Un correo con varios PDFs de documentos personales (liquidaciones, cédula, AFP, "
    "CMF) casi siempre es solicitud_nueva aunque el asunto sea vago. Los veredictos de mesa "
    "vienen de aprobaciones@centralmutuos.cl. INTEGRIDAD: no inventes nombres; si el cliente no "
    "aparece literalmente, deja cliente=''. Responde SOLO el JSON."
)


def _huella(subject, date_iso):
    return hashlib.sha256(
        f"{(subject or '').strip().lower()}|{(date_iso or '').strip()}".encode()).hexdigest()


async def clasificar_correo(subject, sender, body, nombres_adjuntos=None, date_iso="", cachear=True):
    """Clasifica un correo con Claude. Devuelve {categoria, confianza, cliente, razon, metodo}.
    categoria='' significa que la IA no estuvo disponible (usar fallback de palabras clave)."""
    h = _huella(subject, date_iso)
    if cachear:
        prev = await _db().clasificaciones_ia.find_one({"huella": h}, {"_id": 0})
        if prev:
            prev["cacheado"] = True
            if not prev.get("hito"):
                prev["hito"] = detectar_hito(
                    prev.get("categoria"), subject, sender, body, nombres_adjuntos)
            return prev
    res = await _clasificar_claude(subject, sender, body, nombres_adjuntos or [])
    res["hito"] = detectar_hito(
        res.get("categoria"), subject, sender, body, nombres_adjuntos)
    if res.get("metodo") == "claude" and cachear:
        reg = {"id": str(uuid.uuid4()), "huella": h, "subject": (subject or "")[:200],
               "sender": (sender or "")[:150], "fecha_correo": date_iso or "",
               "clasificado_en": datetime.now(timezone.utc).isoformat(), **res}
        try:
            await _db().clasificaciones_ia.insert_one(dict(reg))
        except Exception as e:
            logging.warning(f"clasificaciones_ia insert: {e}")
    return res


_KB_CACHE = {"texto": "", "ts": 0.0}


async def _contexto_sistema():
    """Base de conocimiento permanente (aprendizaje histórico) inyectada al clasificador."""
    import time
    if time.time() - _KB_CACHE["ts"] < 600:
        return _KB_CACHE["texto"]
    try:
        doc = await _db().config.find_one({"_key": "base_conocimiento"}, {"resumen_clasificador": 1})
        _KB_CACHE.update({"texto": (doc or {}).get("resumen_clasificador") or "", "ts": time.time()})
    except Exception:
        _KB_CACHE["ts"] = time.time()
    return _KB_CACHE["texto"]


_SISTEMA_LOTE_EXTRA = (
    "\n\nMODO LOTE: Recibirás VARIOS correos numerados (### CORREO N). Responde SOLO un "
    "array JSON (sin texto adicional) con un objeto por correo, EN EL MISMO ORDEN, cada uno "
    "con claves: n (número del correo), categoria, confianza, cliente, razon.")


async def clasificar_lote(correos, cachear=True):
    """Clasifica una lista de correos en UNA sola llamada a Claude (ahorro de créditos).
    correos: [{subject, sender, body, date_iso}] → lista de resultados en el mismo orden."""
    resultados = [None] * len(correos)
    pendientes = []
    for i, c in enumerate(correos):
        if cachear:
            try:
                prev = await _db().clasificaciones_ia.find_one(
                    {"huella": _huella(c.get("subject"), c.get("date_iso"))}, {"_id": 0})
            except Exception:
                prev = None
            if prev:
                prev["cacheado"] = True
                if not prev.get("hito"):
                    prev["hito"] = detectar_hito(
                        prev.get("categoria"), c.get("subject"), c.get("sender"),
                        c.get("body"), None)
                resultados[i] = prev
                continue
        pendientes.append(i)
    if not pendientes:
        return resultados
    key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not key or os.environ.get("AI_EMERGENCY_STOP") == "1":
        for idx in pendientes:
            resultados[idx] = {"categoria": "", "confianza": 0, "cliente": "",
                               "razon": "IA no disponible", "metodo": "sin_llm"}
        return resultados
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import ai_extract as _aix
        kb = await _contexto_sistema()
        sistema = _SISTEMA + _SISTEMA_LOTE_EXTRA + (
            f"\n\nCONTEXTO REAL DEL SISTEMA (aprendizaje histórico):\n{kb}" if kb else "")
        chat = LlmChat(api_key=key, session_id=f"clasif-lote-{uuid.uuid4()}",
                       system_message=sistema).with_model("anthropic", "claude-sonnet-4-6")
        bloques = []
        for j, idx in enumerate(pendientes, 1):
            c = correos[idx]
            bloques.append(f"### CORREO {j}\nRemitente: {c.get('sender') or ''}\n"
                           f"Asunto: {c.get('subject') or ''}\n"
                           f"Cuerpo:\n{(c.get('body') or '')[:800]}")
        resp = await _aix._enviar(chat, UserMessage(text="\n\n".join(bloques)))
        raw = resp if isinstance(resp, str) else str(resp)
        m = re.search(r"\[.*\]", raw, re.S)
        arr = json.loads(m.group(0)) if m else []
        for j, idx in enumerate(pendientes):
            d = arr[j] if j < len(arr) and isinstance(arr[j], dict) else {}
            cat = (d.get("categoria") or "").strip()
            if cat not in CATEGORIAS:
                cat = "no_relacionado"
            c0 = correos[idx]
            res = {"categoria": cat, "confianza": float(d.get("confianza") or 0.7),
                   "cliente": (d.get("cliente") or "").strip()[:120],
                   "razon": (d.get("razon") or "")[:250], "metodo": "claude_lote"}
            res["hito"] = detectar_hito(cat, c0.get("subject"), c0.get("sender"),
                                        c0.get("body"), None)
            resultados[idx] = res
            if cachear:
                c = correos[idx]
                try:
                    await _db().clasificaciones_ia.insert_one({
                        "id": str(uuid.uuid4()),
                        "huella": _huella(c.get("subject"), c.get("date_iso")),
                        "subject": (c.get("subject") or "")[:200],
                        "sender": (c.get("sender") or "")[:150],
                        "fecha_correo": c.get("date_iso") or "",
                        "clasificado_en": datetime.now(timezone.utc).isoformat(), **res})
                except Exception as e:
                    logging.warning(f"clasificaciones_ia lote insert: {e}")
    except Exception as e:
        logging.warning(f"clasificador claude lote: {str(e)[:150]}")
        for idx in pendientes:
            if resultados[idx] is None:
                resultados[idx] = {"categoria": "", "confianza": 0, "cliente": "",
                                   "razon": f"error IA lote: {str(e)[:100]}", "metodo": "error"}
    return resultados


async def _clasificar_claude(subject, sender, body, nombres_adjuntos):
    key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not key or os.environ.get("AI_EMERGENCY_STOP") == "1":
        return {"categoria": "", "confianza": 0, "cliente": "", "razon": "IA no disponible",
                "metodo": "sin_llm"}
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        import ai_extract as _aix
        kb = await _contexto_sistema()
        sistema = _SISTEMA + (f"\n\nCONTEXTO REAL DEL SISTEMA (aprendizaje histórico):\n{kb}" if kb else "")
        chat = LlmChat(api_key=key, session_id=f"clasif-correo-{uuid.uuid4()}",
                       system_message=sistema).with_model("anthropic", "claude-sonnet-4-6")
        um = UserMessage(text=(
            f"Remitente: {sender or ''}\n"
            f"Asunto: {subject or ''}\n"
            f"Adjuntos ({len(nombres_adjuntos)}): {', '.join((nombres_adjuntos or [])[:15]) or '(sin adjuntos)'}\n\n"
            f"Cuerpo:\n{(body or '')[:2500]}"))
        resp = await _aix._enviar(chat, um)
        raw = resp if isinstance(resp, str) else str(resp)
        m = re.search(r"\{.*\}", raw, re.S)
        d = json.loads(m.group(0)) if m else {}
        cat = (d.get("categoria") or "").strip()
        if cat not in CATEGORIAS:
            cat = "no_relacionado"
        return {"categoria": cat,
                "confianza": float(d.get("confianza") or 0.7),
                "cliente": (d.get("cliente") or "").strip()[:120],
                "razon": (d.get("razon") or "")[:250], "metodo": "claude"}
    except Exception as e:
        logging.warning(f"clasificador claude: {str(e)[:150]}")
        return {"categoria": "", "confianza": 0, "cliente": "",
                "razon": f"error IA: {str(e)[:120]}", "metodo": "error"}
