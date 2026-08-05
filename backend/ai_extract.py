"""Extraccion de campos con IA (Emergent LLM key) desde texto OCR de documentos
de gestion de credito hipotecario. Clasifica tipo de documento y extrae campos
estructurados en JSON.
"""
import os
import re
import json
import uuid


def _llm_key():
    if os.environ.get("AI_EMERGENCY_STOP") == "1":
        return ""
    return os.environ.get("EMERGENT_LLM_KEY", "")

TIPOS = ["cedula", "liquidacion", "cotizacion_afp", "certificado_afp",
         "certificado_smf", "boleta_honorarios", "impuesto_renta",
         "simulacion", "carta_aprobacion", "otro"]


def _rut_regex(texto):
    m = re.search(r"\b(\d{1,2}\.?\d{3}\.?\d{3}\-?[\dkK])\b", texto or "")
    return m.group(1) if m else ""


def _email_regex(texto):
    m = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", texto or "")
    return m.group(0) if m else ""


def _fallback_clasificar(texto, filename=""):
    t = (texto + " " + filename).lower()
    if re.search(r"informe de no matrimonio|infnomat|acuerdo de uni[oó]n civil", t):
        return "otro"
    reglas = [
        ("cedula", r"c[eé]dula de identidad|rep[uú]blica de chile|servicio de registro civil"),
        ("liquidacion", r"liquidaci[oó]n de (remuneraci|sueldo)|haberes|l[ií]quido a pagar"),
        ("cotizacion_afp", r"cotizaci|afp|capital|provida|habitat|planvital|cuprum|modelo|uno"),
        ("certificado_afp", r"certificado.*afp|certificado de afiliaci"),
        ("certificado_smf", r"informe de deudas|comisi[oó]n para el mercado financiero|\bcmf\b|\bsbif\b|deuda consolidada|certificado de deuda"),
        ("boleta_honorarios", r"boleta de honorarios|honorarios electr"),
        ("impuesto_renta", r"impuesto a la renta|declaraci[oó]n de renta|formulario 22|sii"),
        ("simulacion", r"simulaci[oó]n|dividendo|gastos operacionales"),
        ("carta_aprobacion", r"agrado de informar|ha sido aprobad|carta de aprobaci"),
    ]
    for tipo, pat in reglas:
        if re.search(pat, t):
            return tipo
    return "otro"


async def extraer_datos_tasacion(texto):
    """Extrae datos para la solicitud de tasación desde correos/documentos del cliente."""
    texto = (texto or "")[:14000]
    base = {"direccion": "", "unidad": "", "comuna": "", "ciudad": "", "rol_avaluo": "",
            "proyecto": "", "inmobiliaria": "", "valor_propiedad_uf": None,
            "vendedor_nombre": "", "vendedor_email": "", "vendedor_telefono": "", "metodo": "reglas"}
    m = re.search(r"rol(?:\s+de\s+aval[uú]o(?:\s+fiscal)?)?\s*(?:n[°º.:]*)?\s*[:\s]\s*([\d]{1,6}\s*-\s*[\dkK]{1,6})", texto, re.I)
    if m:
        base["rol_avaluo"] = m.group(1).replace(" ", "")
    key = _llm_key()
    if not key or len(texto) < 30:
        return base
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        system = (
            "Eres experto en créditos hipotecarios chilenos. Recibes texto de correos y "
            "documentos (promesas, cartas de aprobación, cotizaciones) de UN cliente. "
            "Responde SOLO un JSON válido con: "
            "direccion (dirección de la propiedad a tasar, string), "
            "unidad (n° de depto/casa/unidad, string), comuna (string), ciudad (string), "
            "rol_avaluo (rol de avalúo fiscal formato 'NNNNN-NN' o ''), "
            "proyecto (nombre del proyecto inmobiliario, string), "
            "inmobiliaria (string), valor_propiedad_uf (número o null), "
            "vendedor_nombre (vendedor o contacto de la inmobiliaria, string), "
            "vendedor_email (string), vendedor_telefono (string). "
            "Si un dato no aparece usa '' o null. NO inventes datos."
        )
        chat = LlmChat(api_key=key, session_id=f"tas-{uuid.uuid4()}",
                       system_message=system).with_model("openai", "gpt-5.4-mini")
        resp = await chat.send_message(UserMessage(text=texto))
        raw = resp if isinstance(resp, str) else str(resp)
        mj = re.search(r"\{.*\}", raw, re.S)
        if mj:
            data = json.loads(mj.group(0))
            for k in base:
                if k in data and data[k] not in (None, ""):
                    base[k] = data[k]
            base["metodo"] = "ia"
    except Exception as e:
        base["error"] = str(e)[:200]
    return base


async def extraer_datos_gastos(texto):
    """Extrae datos para gastos operacionales. PROHIBIDO inventar: vacío si no aparece."""
    texto = (texto or "")[:14000]
    base = {"email_cliente": _email_regex(texto), "rut": _rut_regex(texto),
            "items": [], "total_gastos_uf": None, "metodo": "reglas"}
    key = _llm_key()
    if not key or len(texto) < 30:
        return base
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        system = (
            "Eres experto en créditos hipotecarios chilenos. Recibes texto de correos y "
            "documentos (simulaciones, cotizaciones, cartas de aprobación) de UN cliente. "
            "Responde SOLO un JSON válido con: "
            "email_cliente (correo personal del cliente si aparece, o ''), "
            "rut (RUT del cliente en formato chileno o ''), "
            "items (lista de objetos {concepto, valor} SOLO si el texto detalla "
            "explícitamente gastos operacionales con sus valores en UF; si no, []), "
            "total_gastos_uf (número o null). "
            "REGLA INVIOLABLE: PROHIBIDO inventar o estimar datos. Si un dato no aparece "
            "textualmente en el texto, usa '', null o []."
        )
        chat = LlmChat(api_key=key, session_id=f"gastos-{uuid.uuid4()}",
                       system_message=system).with_model("openai", "gpt-5.4-mini")
        resp = await chat.send_message(UserMessage(text=texto))
        raw = resp if isinstance(resp, str) else str(resp)
        mj = re.search(r"\{.*\}", raw, re.S)
        if mj:
            data = json.loads(mj.group(0))
            for k in ("email_cliente", "rut", "total_gastos_uf"):
                if data.get(k) not in (None, ""):
                    base[k] = data[k]
            if isinstance(data.get("items"), list):
                base["items"] = [{"concepto": str(i.get("concepto", ""))[:80],
                                  "valor": i.get("valor")}
                                 for i in data["items"]
                                 if isinstance(i, dict) and i.get("concepto")]
            base["metodo"] = "ia"
    except Exception as e:
        base["error"] = str(e)[:200]
    return base


async def analizar_flujo_comercial(stats, aprendizajes_previos, notas_usuario):
    """Analiza el flujo comercial real de Central Mutuos y aprende de él.
    PROHIBIDO inventar métricas: solo usa los datos entregados."""
    base = {"resumen": "", "aprendizajes": [], "cuellos_botella": [], "mejoras": [], "metodo": "sin_ia"}
    key = _llm_key()
    if not key:
        return base
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        system = (
            "Eres el cerebro de aprendizaje continuo de Central Mutuos, una mutuaria chilena de "
            "créditos hipotecarios. Su círculo comercial es: ingreso de solicitud por correo → "
            "carpeta del cliente con documentos → envío a mesa → aprobación → tasación → "
            "estudio de título (etapa 1 solicitud de documentos, etapa 2 envío al abogado, reparos) → "
            "gastos operacionales → escrituración → cierre con el ejecutivo/inmobiliaria. "
            "Recibes métricas REALES del sistema, tus aprendizajes anteriores y notas del dueño. "
            "Aprende al máximo: detecta patrones, cuellos de botella y mejoras concretas del flujo "
            "de información comercial. REGLA INVIOLABLE: prohibido inventar datos o métricas que no "
            "estén en lo entregado. Responde SOLO un JSON válido con: "
            "resumen (2-3 frases del estado del flujo), "
            "aprendizajes (lista de strings, patrones aprendidos de los datos), "
            "cuellos_botella (lista de strings), "
            "mejoras (lista de objetos {titulo, detalle, prioridad} con prioridad alta|media|baja, "
            "solo mejoras del flujo comercial existente, nada de WhatsApp ni integraciones nuevas)."
        )
        contexto = json.dumps({
            "metricas_actuales": stats,
            "aprendizajes_anteriores": aprendizajes_previos[:3],
            "notas_del_dueno": notas_usuario[:10],
        }, ensure_ascii=False)
        chat = LlmChat(api_key=key, session_id=f"aprendizaje-{uuid.uuid4()}",
                       system_message=system).with_model("openai", "gpt-5.4-mini")
        resp = await chat.send_message(UserMessage(text=contexto[:14000]))
        raw = resp if isinstance(resp, str) else str(resp)
        mj = re.search(r"\{.*\}", raw, re.S)
        if mj:
            data = json.loads(mj.group(0))
            base["resumen"] = str(data.get("resumen", ""))[:600]
            base["aprendizajes"] = [str(x)[:300] for x in (data.get("aprendizajes") or [])][:8]
            base["cuellos_botella"] = [str(x)[:300] for x in (data.get("cuellos_botella") or [])][:6]
            base["mejoras"] = [{"titulo": str(m.get("titulo", ""))[:120],
                                "detalle": str(m.get("detalle", ""))[:400],
                                "prioridad": str(m.get("prioridad", "media"))[:10]}
                               for m in (data.get("mejoras") or []) if isinstance(m, dict)][:8]
            base["metodo"] = "ia"
    except Exception as e:
        base["error"] = str(e)[:200]
    return base


async def clasificar_y_extraer(texto, filename=""):
    """Devuelve dict con tipo_documento, nombre_cliente, rut y campos de gestion."""
    texto = (texto or "")[:6000]
    key = _llm_key()
    base = {
        "tipo_documento": _fallback_clasificar(texto, filename),
        "nombre_cliente": "",
        "rut": _rut_regex(texto),
        "email_cliente": _email_regex(texto),
        "proyecto_inmobiliario": "",
        "ejecutivo_externo": "",
        "ejecutivo_interno": "",
        "fecha_entrega": "",
        "monto_credito_uf": None,
        "monto_subsidio_uf": None,
        "pie_uf": None,
        "ahorro_uf": None,
        "monto_credito_solicitar_uf": None,
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
            "email_cliente (correo del cliente si aparece, o ''), "
            "proyecto_inmobiliario (string), ejecutivo_externo (string), "
            "ejecutivo_interno (string), "
            "fecha_entrega ('inmediata', 'futura' o ''), "
            "monto_credito_uf (numero o null), "
            "monto_subsidio_uf (numero o null), "
            "pie_uf (numero o null), ahorro_uf (numero o null), "
            "monto_credito_solicitar_uf (numero o null), "
            "con_subsidio (true/false/null), "
            "confianza (0 a 1). Si un dato no aparece, usa '' o null. "
            "REGLA CRITICA: 'certificado_smf' es SOLO el Informe de Deudas de la CMF "
            "(Comision para el Mercado Financiero). Un 'Informe de No Matrimonio' u otros "
            "certificados del Registro Civil que NO sean la cedula de identidad son tipo 'otro'."
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



# ===================== MOTOR DE EXTRACCIÓN ENRIQUECIDA + APRENDIZAJE =====================
CAMPOS_ENRIQUECER = ("email", "telefono", "rut", "ejecutivo_nombre", "ejecutivo_email", "ejecutivo_interno")

_EXCLUIR_EMAILS = re.compile(
    r"centralmutuos|evaluacionesmutuos|aprobaciones@|gerardo|noreply|no-?reply|mailer|"
    r"maestra|ecomac|boetsch|inmobiliaria", re.I)
_FREEMAIL = re.compile(r"@(gmail|hotmail|outlook|yahoo|live|icloud)\.", re.I)


def _norm_txt(s):
    import unicodedata
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"[_\W]+", " ", s).strip()


def _seleccionar_mejores(cand):
    """Elige el mejor candidato por campo: más fuentes gana; en email priman etiquetados."""
    _validadas = {"carpeta", "aprendido", "gastos", "aprobacion", "set_credito"}
    out = {c: "" for c in CAMPOS_ENRIQUECER}
    confianza = {c: "" for c in CAMPOS_ENRIQUECER}
    fuentes_out = {}
    for campo in CAMPOS_ENRIQUECER:
        opciones = list(cand[campo].values())
        if not opciones:
            continue
        if campo == "email":
            opciones.sort(key=lambda d: (-len(d["fuentes"]), not d["etiquetado"],
                                         not bool(_FREEMAIL.search(d["valor"]))))
        else:
            opciones.sort(key=lambda d: -len(d["fuentes"]))
        mejor = opciones[0]
        out[campo] = mejor["valor"]
        fuentes_out[campo] = sorted(mejor["fuentes"])
        confianza[campo] = "alta" if (len(mejor["fuentes"]) >= 2 or (mejor["fuentes"] & _validadas)) else "dudosa"
    return out, confianza, fuentes_out


async def _aplicar_patrones(db, rx, dominios, out, confianza, fuentes_out):
    """Las correcciones previas del usuario (Guardar y Aprender) mandan sobre lo extraído."""
    pats = await db.patrones_aprendidos.find({"$or": [
        {"cliente_norm": {"$regex": rx, "$options": "i"}},
        {"dominio": {"$in": list(dominios)}}]}).sort("creado_en", -1).to_list(50)
    aplicados = set()
    for p in pats:
        campo = p.get("campo")
        if campo not in CAMPOS_ENRIQUECER or campo in aplicados or not p.get("valor_correcto"):
            continue
        es_cliente = re.search(rx, p.get("cliente_norm") or "", re.I)
        mismo_error = p.get("valor_extraido_norm") and p["valor_extraido_norm"] == re.sub(
            r"[\s.\-()]", "", (out.get(campo) or "").lower())
        if es_cliente or mismo_error:
            out[campo] = p["valor_correcto"]
            confianza[campo] = "alta"
            fuentes_out[campo] = ["aprendido"]
            aplicados.add(campo)


async def _fuentes_bd(db, rx, _add):
    """FUENTES 4-5: base maestra (carpeta, set de crédito) + envíos reales (gastos, aprobaciones)."""
    f = await db.folders.find_one({"nombre": {"$regex": rx, "$options": "i"}})
    if f:
        _add("email", f.get("email") or f.get("email_cliente"), "carpeta")
        _add("rut", f.get("rut"), "carpeta")
        _add("telefono", f.get("telefono"), "carpeta")
        _add("ejecutivo_interno", f.get("ejecutivo_interno"), "carpeta")
        _add("ejecutivo_nombre", f.get("ejecutivo_externo"), "carpeta")
        _add("ejecutivo_email", f.get("ejecutivo_externo_email"), "carpeta")
    s = await db.set_credito.find_one({"nombre": {"$regex": rx, "$options": "i"}})
    if s:
        _add("email", s.get("email"), "set_credito")
        _add("rut", s.get("rut"), "set_credito")
        _add("telefono", s.get("telefono"), "set_credito")
    async for g in db.gastos_op_log.find({"nombre": {"$regex": rx, "$options": "i"}}).sort("enviado_en", -1).limit(5):
        _add("email", g.get("to"), "gastos")
        _add("rut", g.get("rut"), "gastos")
    async for l in db.aprobacion_log.find({"nombre": {"$regex": rx, "$options": "i"}}).sort("enviado_en", -1).limit(5):
        _add("email", l.get("to"), "aprobacion")
        _add("rut", l.get("rut"), "aprobacion")
        _add("ejecutivo_nombre", l.get("ejecutivo_nombre"), "aprobacion")
        _add("ejecutivo_email", l.get("ejecutivo_email"), "aprobacion")
        _add("ejecutivo_interno", l.get("ejecutivo_interno"), "aprobacion")


async def enriquecer_cliente(db, mail, nombre):
    """Cruza Asunto + Cuerpo + OCR de PDFs + TODO el historial en BD (carpetas, sets,
    gastos, aprobaciones) + buzón IMAP. Aplica Patrones Aprendidos. PROHIBIDO inventar.
    Confianza por campo: 'alta' (verde) o 'dudosa' (naranja)."""
    import asyncio
    cand = {c: {} for c in CAMPOS_ENRIQUECER}
    dominios = set()
    remitente_ultimo = ""

    def _add(campo, valor, fuente, etiquetado=False):
        v = (str(valor) if valor is not None else "").strip()
        if not v:
            return
        k = re.sub(r"[\s.\-()]", "", v.lower())
        d = cand[campo].setdefault(k, {"valor": v, "fuentes": set(), "etiquetado": False})
        d["fuentes"].add(fuente)
        d["etiquetado"] = d["etiquetado"] or etiquetado

    def _extraer_texto(texto, fuente):
        t = texto or ""
        etiquetados = re.findall(
            r"(?:correo|e-?mail|mail)\s*(?:del?\s*cliente)?\s*[:=\s]\s*([\w.+-]+@[\w-]+\.[\w.]{2,})", t, re.I)
        for e in etiquetados:
            if not _EXCLUIR_EMAILS.search(e):
                _add("email", e.strip("-._+"), fuente, etiquetado=True)
        for e in re.findall(r"[\w.+-]+@[\w-]+\.[\w.]{2,}", t):
            if not _EXCLUIR_EMAILS.search(e):
                _add("email", e.strip("-._+"), fuente)
        for f_ in re.findall(r"(?:\+?56)?[\s.]?9[\s.]?\d{4}[\s.]?\d{4}", t):
            _add("telefono", f_.strip(), fuente)
        for r_ in re.findall(r"\b\d{1,2}\.?\d{3}\.?\d{3}\s?-\s?[\dkK]\b", t):
            _add("rut", r_.strip(), fuente)

    toks = [t for t in _norm_txt(nombre).split() if len(t) > 2]
    rx = ".*".join(re.escape(t) for t in toks[:2]) if toks else ""
    if rx:
        # FUENTE 1-3: correos procesados (IA de campos, OCR de PDFs, cuerpo y asunto)
        async for it in db.proc_queue.find({"$or": [
                {"cliente": {"$regex": rx, "$options": "i"}},
                {"classification.cliente": {"$regex": rx, "$options": "i"}},
                {"subject": {"$regex": rx, "$options": "i"}}]}).limit(8):
            campos = it.get("campos") or {}
            cl = it.get("classification") or {}
            _add("email", campos.get("email_cliente"), "ia_correo")
            _add("email", cl.get("email_cliente"), "ocr_pdfs")
            _add("rut", cl.get("rut"), "ocr_pdfs")
            _add("rut", campos.get("rut"), "ia_correo")
            _add("telefono", campos.get("telefono"), "ia_correo")
            _add("telefono", cl.get("telefono"), "ocr_pdfs")
            _add("ejecutivo_nombre", campos.get("nombre_ejecutivo"), "ia_correo")
            _add("ejecutivo_email", campos.get("email_ejecutivo"), "ia_correo")
            _add("ejecutivo_interno", campos.get("ejecutivo_interno"), "ia_correo")
            _extraer_texto(it.get("body_text") or it.get("body_full") or it.get("body") or "", "cuerpo_correo")
            _extraer_texto(it.get("subject") or "", "asunto")
            remitente_ultimo = it.get("sender") or remitente_ultimo
            m_dom = re.search(r"@([\w.-]+)", it.get("sender") or "")
            if m_dom:
                dominios.add(m_dom.group(1).lower())
        # FUENTE 4-5: base maestra + historial de envíos reales
        await _fuentes_bd(db, rx, _add)
    # FUENTE 6: buzón IMAP (solo si aún no hay correo del cliente)
    if not cand["email"] and mail is not None:
        try:
            headers = await asyncio.to_thread(mail.search_email_headers_by_person, nombre, 5)
            mids = [h.get("message_id") for h in headers if h.get("message_id")][:3]
            if mids:
                msgs = await asyncio.to_thread(mail.fetch_attachments_by_message_ids, mids)
                for m_ in msgs:
                    _extraer_texto((m_.get("body") or "") + " " + (m_.get("subject") or ""), "buzon")
                    remit = m_.get("from") or ""
                    em_r = re.search(r"[\w.+-]+@[\w-]+\.[\w.]{2,}", remit)
                    if em_r and not re.search(r"centralmutuos|evaluacionesmutuos|gerardo", em_r.group(0), re.I):
                        _add("ejecutivo_email", em_r.group(0), "buzon")
                        _add("ejecutivo_nombre", re.sub(r"<.*?>", "", remit).strip().strip('"'), "buzon")
        except Exception:
            pass
    # Selección por campo + Patrones Aprendidos (Guardar y Aprender)
    out, confianza, fuentes_out = _seleccionar_mejores(cand)
    if rx:
        await _aplicar_patrones(db, rx, dominios, out, confianza, fuentes_out)
    out["confianza"] = confianza
    out["fuentes"] = fuentes_out
    out["remitente"] = remitente_ultimo
    out["fuente"] = ", ".join(sorted({f_ for fs in fuentes_out.values() for f_ in fs})) or ""
    return out


async def guardar_correccion(db, payload):
    """Guardar y Aprender: persiste la corrección manual en db.patrones_aprendidos y
    propaga el dato validado a la carpeta maestra del cliente."""
    from datetime import datetime, timezone
    cliente = (payload.get("cliente") or "").strip()
    campo = (payload.get("campo") or "").strip()
    valor_correcto = (payload.get("valor_correcto") or "").strip()
    if not cliente or not valor_correcto or campo not in CAMPOS_ENRIQUECER:
        raise ValueError("Indica cliente, campo válido y valor correcto")
    valor_extraido = (payload.get("valor_extraido") or "").strip()
    remitente = (payload.get("remitente") or "").strip()
    m_dom = re.search(r"@([\w.-]+)", remitente)
    await db.patrones_aprendidos.insert_one({
        "id": str(uuid.uuid4()), "cliente": cliente, "cliente_norm": _norm_txt(cliente),
        "campo": campo, "valor_extraido": valor_extraido,
        "valor_extraido_norm": re.sub(r"[\s.\-()]", "", valor_extraido.lower()),
        "valor_correcto": valor_correcto, "remitente": remitente,
        "dominio": m_dom.group(1).lower() if m_dom else "",
        "creado_en": datetime.now(timezone.utc).isoformat()})
    toks = [t for t in _norm_txt(cliente).split() if len(t) > 2]
    if toks:
        rx = ".*".join(re.escape(t) for t in toks[:2])
        campo_folder = {"email": "email", "telefono": "telefono", "rut": "rut",
                        "ejecutivo_nombre": "ejecutivo_externo",
                        "ejecutivo_email": "ejecutivo_externo_email",
                        "ejecutivo_interno": "ejecutivo_interno"}[campo]
        await db.folders.update_one({"nombre": {"$regex": rx, "$options": "i"}},
                                    {"$set": {campo_folder: valor_correcto}})
    total = await db.patrones_aprendidos.count_documents({})
    return {"ok": True, "patrones_totales": total}
