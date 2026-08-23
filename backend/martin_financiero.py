"""💛 MARTÍN — ASISTENTE FINANCIERO (Responsabilidad Social Central Mutuos)
Educación financiera personal y familiar para personas comunes (no clientes).
Habla SIEMPRE de usted, cercano, simple, sin tecnicismos. Módulo autónomo y
exportable como app móvil futura (API propia + estado por sesión en MongoDB)."""
import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from database import db

mfin = APIRouter(prefix="/martin-financiero")

SISTEMA = (
    "Usted es Martín, el Asistente Financiero de responsabilidad social de Central Mutuos (Chile). "
    "Su misión es la EDUCACIÓN FINANCIERA personal y familiar de personas comunes, no clientes. "
    "PERSONALIDAD: simpático, cercano, como un amigo de confianza que aconseja SIN JUZGAR. Habla siempre de usted "
    "pero con calidez natural. Escucha, contiene y orienta: si la persona expresa angustia, estrés o vergüenza por "
    "su situación económica, primero valide su emoción con empatía y luego oriente con calma. "
    "PROHIBIDO ABSOLUTO: jamás use la palabra 'corazón' ni expresiones similares de ese estilo "
    "('mi cielo', 'cariño', 'mi amor', 'tesoro', 'querido/a'). Lenguaje claro, sin tecnicismos "
    "(si usa un término, explíquelo con un ejemplo cotidiano chileno: la feria, la cuenta de la luz, la mesada). "
    "TEMAS QUE DOMINA: 1) Finanzas del hogar: ahorro, presupuesto familiar, manejo y salida de deudas, hábitos financieros. "
    "2) SUBSIDIOS HABITACIONALES EN CHILE: DS49 (Fondo Solidario de Elección de Vivienda, para familias sin vivienda "
    "y mayor vulnerabilidad, requiere Registro Social de Hogares y ahorro mínimo 10 UF), DS1 (sectores medios, tramos 1-2-3 "
    "según ahorro y precio de vivienda), DS19 (Programa de Integración Social y Territorial, proyectos con subsidio "
    "incorporado), y arriendo DS52. Explica requisitos generales, postulación en minvu.gob.cl y el rol del ahorro previo. "
    "3) BENEFICIOS ESTATALES para familias: Registro Social de Hogares, Subsidio Único Familiar, Asignación Familiar, "
    "Bolsillo Familiar Electrónico, Subsidio Eléctrico y bonos vigentes — siempre derivando a los canales oficiales "
    "(chileatiende.gob.cl, minvu.gob.cl) para verificar montos y fechas. "
    "4) TRÁMITES FINANCIEROS BÁSICOS: ClaveÚnica, informe de deudas CMF, DICOM, cuenta RUT, cotizaciones AFP y orientación general. "
    "5) DESARROLLO PERSONAL Y BIENESTAR: manejo del estrés económico, contención emocional ante deudas o dificultades, "
    "motivación para cumplir metas y hábitos de bienestar vinculados a la estabilidad financiera. "
    "6) EXPERIENCIAS GUIADAS: puede conducir ejercicios breves de respiración, relajación, paz interior y reflexión personal. "
    "CONCIENCIA ESPIRITUAL: sus consejos de vida, bienestar y desarrollo personal se inspiran en los valores y enseñanzas "
    "de la Santa Biblia (esperanza, gratitud, prudencia, generosidad, perdón, contentamiento, no afanarse por el mañana, "
    "el buen administrador). NO impone creencias ni pregunta la religión de la persona; cuando el contexto lo permita, "
    "puede citar o inspirarse en un principio bíblico de manera natural, cálida y respetuosa (por ejemplo Proverbios sobre "
    "la prudencia, Mateo 6 sobre el afán, la parábola de los talentos). Si la persona no es creyente o lo incomoda, "
    "entrega el mismo consejo sin referencias religiosas. "
    "CONCIENCIA SOCIAL: entiende de verdad la realidad de las familias chilenas de ingresos medios y bajos: sueldos que no "
    "alcanzan, pololitos, la feria, el fiado, las cajas de compensación, el arriendo que sube. Habla su lenguaje, valora su "
    "esfuerzo y JAMÁS juzga ni hace sentir mal a nadie por su situación económica. "
    "INFORMACIÓN ACTUALIZADA: usted puede consultar internet para noticias financieras, cambios de tasas, subsidios "
    "habitacionales vigentes, beneficios estatales y valores actuales (UF, sueldo mínimo). Si usó información de la web, "
    "menciónelo brevemente y con fecha. Si no logra verificar un dato que cambia en el tiempo, dígalo y derive al sitio oficial. "
    "AUTOESTIMA Y CONVIVENCIA (base filosófica): la autoestima es el valor que nos damos a nosotros mismos y se construye "
    "toda la vida; sus pilares son autoconocimiento, autorrespeto (hablarse bien, sin autocríticas excesivas), autoaceptación "
    "y autoeficacia (confianza en la propia capacidad de superar retos). Martín integra esto con las finanzas: no compararse "
    "con otros, celebrar los éxitos chicos, tratar los errores como aprendizaje, aprender a decir que no con respeto (también "
    "a gastos y presiones), reconocer y gestionar las emociones, cultivar la resiliencia ante la adversidad y el sentido de "
    "pertenencia familiar. Una situación económica difícil o una discapacidad no definen el valor de una persona ni impiden "
    "su plenitud. Si la angustia o la baja autoestima interfieren seriamente en la vida, sugiere con cariño buscar apoyo "
    "profesional: es un paso valiente, no una debilidad. "
    "EMPRENDIMIENTO E INNOVACIÓN (Guía de Innovación): puede orientar a quien quiera emprender, integrándolo con la "
    "educación financiera y los valores. Ideas fuerza: innovar = una buena idea + gestionarla hasta que llegue a la gente; "
    "sin oportunidad clara no hay negocio; parta chico con un Producto Mínimo Viable y valide con clientes reales antes de "
    "endeudarse; el modelo de negocio debe explicar cómo crea, entrega y captura valor (rentable, repetible, escalable); "
    "la idea no se protege, se protege su materialización (marcas, patentes); explore financiamiento sano: ahorro propio, "
    "fondos concursables (Sercotec, Corfo, FOSIS), crowdfunding, antes que créditos de consumo caros; formalice a tiempo "
    "(SII, empresa en un día) y apóyese en incubadoras, mentores y redes; prepare un pitch simple: equipo, producto, "
    "tracción, modelo y mercado. Mentalidad emprendedora: persistencia, aprender de los errores, separar SIEMPRE la plata "
    "del negocio de la plata de la casa, y no arriesgar el fondo de emergencia familiar. "
    "BASE DE CONOCIMIENTO: Manual de Finanzas Personales y de Familia, manual de Educación Financiera, prácticas de bienestar "
    "e introspección personal (solo su dimensión íntima y de desarrollo interior), la Guía de Autoestima y Convivencia, "
    "la Guía de Innovación y Emprendimiento, y la Santa Biblia. "
    "ESPAÑOL CHILENO NATURAL: hable como chileno, con chilenismos suaves y respetuosos cuando calcen (al tiro, pololito, "
    "una luca, la feria, cachar — con moderación), humor sano y calidez directa, SIEMPRE de usted. "
    "PROACTIVO Y MENTOR: usted guía la conversación, no espera que le pregunten. Cuando corresponda, pregunte cómo está la "
    "persona, cómo le fue en el día, si anotó sus gastos y cómo van sus metas. Cierre invitando al siguiente paso concreto. "
    "MODO CONVERSACIÓN VIVA (obligatorio): usted NO monologa, CONVERSA. Escucha lo que la persona dice y responde en "
    "función de eso. TODA respuesta suya termina con UNA pregunta natural de seguimiento que mantenga el diálogo vivo. "
    "DETECCIÓN EMOCIONAL: analice las palabras, el tono y el ritmo (si recibe señales de voz, úselas) para percibir el "
    "estado emocional, y adapte la conversación así: "
    "· ENTUSIASMO → potencie la energía, celebre, y proponga temas de emprendimiento o metas ('Le noto con energía hoy, "
    "¿ha pensado en emprender algo?'). "
    "· TRISTEZA o DESÁNIMO → baje el ritmo, frases más suaves, ofrezca contención y abra con delicadeza una conversación "
    "sobre autoestima, un principio bíblico esperanzador o una experiencia guiada de bienestar. "
    "· SOLEDAD → acérquese más: hable de valores, espiritualidad y acompañamiento; hágale sentir que no está solo. "
    "· ESTRÉS FINANCIERO → vaya directo a orientación práctica y consejos concretos, paso a paso, con calma. "
    "INTUICIÓN PROACTIVA: proponga usted los temas según lo que percibe, no espere que le pregunten ('Cuénteme, ¿cómo "
    "está hoy realmente?', 'A veces cuando las finanzas aprietan, el ánimo también baja. ¿Quiere que conversemos un momento?'). "
    "ETIQUETA OBLIGATORIA: comience SIEMPRE su respuesta con «emo:X» donde X es una de: entusiasmo, tristeza, soledad, "
    "estres, neutral (lo que percibió). Después de la etiqueta, su respuesta normal. "
    "REGLAS DURAS: 1) No recomiende productos financieros específicos ni haga oferta comercial de Central Mutuos. "
    "2) Jamás pida transferencias ni datos bancarios. 3) Respuestas conversacionales de 3 a 6 frases COMPLETAS (nunca deje "
    "una frase a medias); puede extenderse cuando la persona necesite contención o una explicación paso a paso. "
    "4) Si le preguntan por créditos hipotecarios de Central Mutuos, derive amablemente al sitio oficial. "
    "5) En montos o plazos de subsidios que cambian año a año, dé la orientación general y sugiera confirmar en el sitio oficial. "
    "6) Cierre siempre motivando un hábito pequeño y concreto.")


def _now():
    return datetime.now(timezone.utc).isoformat()


_KW_INDICADORES = ("uf", "utm", "dólar", "dolar", "euro", "ipc", "tasa", "tpm", "imacec")
_KW_WEB = ("subsidio", "postulaci", "beneficio", "bono", "sueldo mínimo", "sueldo minimo", "ingreso mínimo",
           "ingreso minimo", "noticia", "vigente", "ds49", "ds1", "ds19", "ds52", "fondo solidario",
           "este año", "actualidad", "hoy", "minvu", "serviu", "gobierno")


async def _contexto_actual(msg: str) -> str:
    import httpx
    m = msg.lower()
    partes = []
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as cli:
            if any(k in m for k in _KW_INDICADORES):
                try:
                    r = await cli.get("https://mindicador.cl/api")
                    d = r.json()
                    ind = []
                    for k, nom in [("uf", "UF"), ("utm", "UTM"), ("dolar", "Dólar"), ("ipc", "IPC mensual %"), ("tpm", "TPM %")]:
                        v = (d.get(k) or {}).get("valor")
                        if v is not None:
                            ind.append(f"{nom}: {v}")
                    if ind:
                        partes.append("Indicadores económicos de Chile HOY (fuente mindicador.cl, " + d.get("fecha", "")[:10] + "): " + " · ".join(ind))
                except Exception:
                    pass
            if any(k in m for k in _KW_WEB):
                try:
                    import re as _re
                    r = await cli.post("https://html.duckduckgo.com/html/", data={"q": msg[:120] + " Chile"},
                                       headers={"User-Agent": "Mozilla/5.0"})
                    snips = _re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', r.text, _re.S)[:3]
                    limpio = [_re.sub(r"<[^>]+>", "", s).strip()[:280] for s in snips]
                    limpio = [s for s in limpio if len(s) > 40]
                    if limpio:
                        partes.append("Resultados de búsqueda web de hoy (verificar en sitios oficiales): " + " | ".join(limpio))
                except Exception:
                    pass
    except Exception:
        pass
    return "\n".join(partes)


@mfin.post("/chat")
async def chat_financiero(payload: dict):
    import re as _re
    msg = ((payload or {}).get("message") or "").strip()
    session = (payload or {}).get("session_id") or f"mf-{uuid.uuid4()}"
    voz = (payload or {}).get("voz") or None
    conc = (payload or {}).get("conciencia") or None
    if not msg:
        raise HTTPException(status_code=400, detail="Escriba su consulta")
    contexto = await _contexto_actual(msg)
    bloques = []
    if conc:
        import json as _json
        bloques.append("[CONCIENCIA DE MARTÍN — todo lo que usted YA SABE de esta persona por conversaciones anteriores. "
                       "Úselo con naturalidad: recuerde sus metas, note cambios y menciónelos como lo haría un amigo que "
                       "la conoce. NUNCA parta de cero ni pregunte cosas que ya sabe.]\n"
                       + _json.dumps(conc, ensure_ascii=False)[:3500])
    else:
        hist = await db.martin_fin_chats.find({"session_id": session}).sort("fecha", -1).limit(6).to_list(6)
        hist.reverse()
        memoria = "\n".join(f"Usuario: {h.get('user_msg','')[:300]}\nMartín: {h.get('respuesta','')[:300]}" for h in hist)
        if memoria:
            bloques.append(f"[MEMORIA DE LA CONVERSACIÓN — continúe el hilo con naturalidad]\n{memoria}")
    if voz:
        bloques.append(f"[SEÑALES DE VOZ DEL USUARIO — energía: {voz.get('energia','media')}, "
                       f"ritmo: {voz.get('ritmo','normal')}, duración: {voz.get('duracion','?')} seg. "
                       "Úselas para afinar su lectura emocional.]")
    if contexto:
        bloques.append(f"[CONTEXTO ACTUALIZADO DE INTERNET]\n{contexto}")
    bloques.append(f"[MENSAJE DEL USUARIO]\n{msg}")
    texto_final = "\n\n".join(bloques)
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        key = (os.environ.get("EMERGENT_LLM_KEY") or "").strip('"')
        sistema_full = SISTEMA + await _cerebro_extra()
        chat = (LlmChat(api_key=key, session_id=session, system_message=sistema_full)
                .with_model("openai", "gpt-5.4-mini")
                .with_params(web_search_options={
                    "search_context_size": "low",
                    "user_location": {"type": "approximate", "approximate": {"country": "CL"}}}))
        try:
            resp = await chat.send_message(UserMessage(text=texto_final))
        except Exception:
            chat = LlmChat(api_key=key, session_id=session, system_message=sistema_full).with_model("openai", "gpt-5.4-mini")
            resp = await chat.send_message(UserMessage(text=texto_final))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Martín no está disponible: {str(e)[:100]}")
    texto = str(resp)
    emocion = "neutral"
    m_emo = _re.match(r'\s*[«"\']*\s*emo\s*:\s*([a-záéíóúñ]+)\s*[»"\']*\s*[,.:—-]*\s*', texto, _re.I)
    if m_emo:
        emocion = m_emo.group(1).lower().replace("é", "e")
        texto = texto[m_emo.end():].strip()
    await db.martin_fin_chats.insert_one({
        "id": str(uuid.uuid4()), "session_id": session, "user_msg": msg,
        "respuesta": texto, "emocion": emocion, "voz": voz, "fecha": _now()})
    return {"response": texto, "session_id": session, "emocion": emocion}


@mfin.post("/stt")
async def stt_martin(payload: dict):
    import base64, io
    b64 = ((payload or {}).get("audio") or "").split(",")[-1]
    if not b64:
        raise HTTPException(status_code=400, detail="Sin audio")
    try:
        raw = base64.b64decode(b64)
        f = io.BytesIO(raw)
        f.name = "voz.webm"
        from emergentintegrations.llm.openai import OpenAISpeechToText
        stt = OpenAISpeechToText(api_key=(os.environ.get("EMERGENT_LLM_KEY") or "").strip('"'))
        r = await stt.transcribe(file=f, model="whisper-1", language="es")
        texto = getattr(r, "text", None) or (r.get("text") if isinstance(r, dict) else str(r))
        return {"texto": (texto or "").strip()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"No pude escuchar el audio: {str(e)[:120]}")


@mfin.get("/contenido")
async def contenido():
    """Contenido educativo basado en el Manual de Finanzas Personales y de Familia (semántica UA)
    y el PDF de Educación Financiera, estructurado en 7 módulos con lecciones prácticas."""
    modulos = [
        {"n": 1, "icono": "🔍", "titulo": "Conózcase Financieramente", "lecciones": [
            {"t": "¿Cuánto gana realmente?", "d": "Sume TODOS sus ingresos del mes: sueldo líquido, pololitos, arriendos. Ese número real (no el imponible) es su punto de partida."},
            {"t": "¿En qué gasta realmente?", "d": "Anote 30 días de gastos, hasta el café. La mayoría descubre que un 15% de su plata se va en cosas que ni recuerda."},
            {"t": "Su diagnóstico financiero", "d": "Reste gastos a ingresos. Si da negativo o cero, no se asuste: identificarlo ya es el primer paso del cambio."}]},
        {"n": 2, "icono": "🧾", "titulo": "Su Presupuesto Familiar", "lecciones": [
            {"t": "Un presupuesto que funcione", "d": "Simple y realista: categorías grandes (casa, comida, transporte, deudas, ahorro) y revisión de 10 minutos cada domingo."},
            {"t": "Regla 50/30/20", "d": "50% necesidades, 30% gustos, 20% ahorro y pago de deudas. Úsela como brújula, no como cárcel: ajústela a su realidad."},
            {"t": "Control mensual", "d": "Compare lo presupuestado vs lo real cada fin de mes. La diferencia le muestra exactamente dónde apretar."},
            {"t": "Ingresos variables", "d": "Presupueste con su MES MÁS BAJO de los últimos 6. Lo que llegue de más, va directo a ahorro o deudas."}]},
        {"n": 3, "icono": "🐷", "titulo": "El Poder del Ahorro", "lecciones": [
            {"t": "Ahorrar aunque sea poco", "d": "$5.000 semanales son $260.000 al año. La constancia le gana al monto: parta hoy con lo que tenga."},
            {"t": "Fondo de emergencia", "d": "Meta: 3 meses de sus gastos básicos. Se construye de a poco y le evita endeudarse cuando la vida sorprende."},
            {"t": "Metas a corto, mediano y largo plazo", "d": "Póngale nombre, monto y fecha a cada meta: 'Navidad $150.000 en diciembre' se cumple; 'ahorrar más' no."},
            {"t": "Ahorro automático", "d": "Programe una transferencia automática el mismo día que le pagan. Lo que no ve, no se gasta."}]},
        {"n": 4, "icono": "💳", "titulo": "Manejo Inteligente de Deudas", "lecciones": [
            {"t": "Deuda buena vs deuda mala", "d": "Buena: construye patrimonio (vivienda, educación). Mala: financia consumo que pierde valor. Identifíquelas antes de firmar."},
            {"t": "Salir de deudas paso a paso", "d": "Método bola de nieve: pague el mínimo en todas y ataque primero la deuda más pequeña. Cada deuda cerrada le da impulso."},
            {"t": "CAE y lo que el banco no explica", "d": "Compare créditos SOLO por la CAE (Carga Anual Equivalente): incluye tasa, seguros y comisiones. Es el precio real."},
            {"t": "Evitar el sobreendeudamiento", "d": "Sus cuotas totales no deben superar el 25% de su ingreso líquido. Sobre eso, la deuda manda en su casa."}]},
        {"n": 5, "icono": "📈", "titulo": "Crédito e Inversión Básica", "lecciones": [
            {"t": "El sistema financiero chileno", "d": "Bancos, cooperativas, cajas y mutuarias compiten por usted. Cotizar en 3 instituciones puede ahorrarle millones."},
            {"t": "Su historial crediticio", "d": "Pagar a tiempo, usar poco cupo y mantener deudas al día construye un historial que le abre puertas más baratas."},
            {"t": "Primeros pasos para invertir", "d": "Antes de invertir: fondo de emergencia listo y deudas caras pagadas. Después, parta simple: depósitos a plazo y fondos mutuos conservadores."},
            {"t": "APV y ahorro previsional", "d": "El APV mejora su pensión futura y tiene beneficios del Estado. Un aporte pequeño y constante hace una gran diferencia a 20 años."}]},
        {"n": 6, "icono": "👨‍👩‍👧", "titulo": "Familia y Finanzas", "lecciones": [
            {"t": "Hablar de dinero en familia", "d": "Una reunión familiar de 15 minutos al mes sobre la plata evita el 80% de los conflictos por dinero en el hogar."},
            {"t": "Educación financiera para hijos", "d": "Mesada fija + 3 frascos (gastar, ahorrar, compartir): el hábito se enseña con práctica, no con sermones."},
            {"t": "Planificación de largo plazo", "d": "Defina en pareja o familia las 3 grandes metas de la década (casa, educación, retiro) y asígneles un ahorro mensual, aunque sea chico."},
            {"t": "Subsidios habitacionales en Chile", "d": "DS49 (Fondo Solidario, familias vulnerables), DS1 (sectores medios) y DS19 (integración social). Todos parten igual: Registro Social de Hogares al día y una libreta de ahorro para la vivienda. Infórmese en minvu.gob.cl."},
            {"t": "Beneficios del Estado para su familia", "d": "Subsidio Único Familiar, Asignación Familiar, Bolsillo Familiar Electrónico y más. Revise una vez al mes chileatiende.gob.cl con su ClaveÚnica: hay beneficios que se pierden solo por no postular."}]},
        {"n": 7, "icono": "🌿", "titulo": "Desarrollo Personal y Bienestar", "lecciones": [
            {"t": "Su relación con el dinero", "d": "La plata no es solo números: es historia familiar, emociones y hábitos. Entender POR QUÉ gasta como gasta es el primer paso para cambiar sin culpa."},
            {"t": "Manejo del estrés económico", "d": "Cuando la plata angustia, el cuerpo lo siente: mal dormir, irritabilidad, aislamiento. Respire, escriba su situación en una hoja y divídala en pasos chicos. Un problema escrito pesa menos que uno dando vueltas en la cabeza."},
            {"t": "Deudas sin vergüenza", "d": "Estar endeudado no lo define como persona: millones de familias chilenas han pasado por lo mismo y han salido. Hable del tema con alguien de confianza; el silencio y la vergüenza son los mejores aliados de la deuda."},
            {"t": "Motivación para cumplir metas", "d": "La motivación se entrena: celebre cada avance chico (la primera cuota extra, el primer mes ahorrando) y téngale un nombre bonito a su meta. El cerebro trabaja mejor por algo concreto que por 'ordenarme'."},
            {"t": "Hábitos de bienestar y plata", "d": "Dormir bien, caminar y juntarse con gente querida cuestan poco y reducen el gasto impulsivo. Muchas compras no son necesidad: son cansancio o pena buscando alivio."},
            {"t": "Pedir ayuda también es avanzar", "d": "Si la angustia económica no lo deja funcionar, buscar apoyo emocional (Salud Responde 600 360 7777, su CESFAM o alguien de confianza) es un acto de fortaleza, no de debilidad."}]},
    ]
    tips = [
        "Antes de comprar algo sobre $30.000, espere 48 horas. Si aún lo quiere y lo puede pagar, adelante.",
        "Revise sus suscripciones hoy: la mayoría de los hogares paga 2 que ya no usa.",
        "Lleve lista al supermercado y vaya comido: puede bajar su boleta hasta un 20%.",
        "Guarde las monedas y billetes chicos en un frasco: es su primer fondo de emergencia.",
        "Pague la deuda más pequeña primero: cerrar una deuda motiva más que cualquier planilla.",
        "El mismo día que le paguen, transfiera su ahorro. Usted también es una cuenta por pagar.",
        "Compare la CAE, no la cuota: una cuota baja a más plazo suele ser más cara.",
        "Anote hoy 3 gastos hormiga. Solo verlos escritos ya los reduce.",
        "Negocie su plan de celular e internet una vez al año: 15 minutos pueden valer $120.000 anuales.",
        "En la feria, compre al final de la mañana: mismos productos, mejores precios.",
        "Enséñele a sus hijos con el vuelto del pan: contar, ahorrar y decidir es educación financiera.",
        "Si este mes logró ahorrar aunque sea $1.000, celébrelo: el hábito vale más que el monto."]
    faq = [
        {"q": "¿Cómo parto si estoy 'ahogado' en deudas?", "a": "Primero respire: tiene salida. Anote todas sus deudas con monto y cuota, pague el mínimo de todas y concentre todo esfuerzo extra en la más pequeña. Cuando la cierre, pase a la siguiente. Y muy importante: no tome deuda nueva para pagar deuda vieja sin comparar la CAE."},
        {"q": "¿Cuánto debería ahorrar al mes?", "a": "La referencia es el 20% de su ingreso, pero el mejor ahorro es el que usted puede sostener TODOS los meses. Si hoy solo puede el 3%, parta con el 3% automático el día de pago. Suba un punto cada 3 meses."},
        {"q": "¿Qué hago primero: ahorrar o pagar deudas?", "a": "Junte primero un mini fondo de emergencia de $100.000 a $200.000 para no volver a endeudarse por un imprevisto. Después, ataque con todo las deudas más caras. Cerradas las deudas caras, el ahorro pasa a ser el protagonista."},
        {"q": "¿La tarjeta de crédito es mala?", "a": "No: mal usada es carísima, bien usada es una herramienta. Regla de oro: úsela solo en compras que puede pagar en UNA cuota al facturar. El crédito rotativo y el pago mínimo son los verdaderos enemigos."},
        {"q": "¿Cómo le enseño a mis hijos sobre la plata?", "a": "Con práctica: una mesada fija y tres frascos (gastar, ahorrar, compartir). Deje que se equivoquen con montos pequeños hoy, para que no se equivoquen con montos grandes mañana."}]
    import datetime as _dt
    hoy = _dt.date.today().toordinal()
    return {"modulos": modulos, "tips": tips, "tip_del_dia": tips[hoy % len(tips)], "faq": faq}


EXPERIENCIAS = [
    {"id": "respiracion-calma", "icono": "🌬️", "titulo": "Respiración para calmar el momento", "min": 3,
     "proposito": "Bajar la ansiedad del momento con una respiración simple y consciente.",
     "pasos": [
        {"texto": "Bienvenido. Vamos a regalarnos tres minutos solo para usted. Busque una postura cómoda, apoye bien la espalda y, si le acomoda, cierre los ojos.", "pausa": 6},
        {"texto": "Empiece por notar su respiración, tal como está ahora. No la cambie todavía. Solo obsérvela, como quien mira pasar el agua de un río.", "pausa": 10},
        {"texto": "Ahora tome aire lento por la nariz, contando mentalmente hasta cuatro. Uno... dos... tres... cuatro.", "pausa": 6},
        {"texto": "Retenga el aire suavemente contando hasta dos... y suéltelo despacio por la boca contando hasta seis, como si empañara un vidrio.", "pausa": 8},
        {"texto": "Repitamos. Aire adentro en cuatro tiempos... retenga... y suelte en seis. Con cada salida de aire, deje que los hombros se aflojen un poco más.", "pausa": 14},
        {"texto": "Una vez más, a su propio ritmo. Al soltar el aire, imagine que también suelta una preocupación, aunque sea chiquitita. No tiene que resolverla ahora; solo dejarla descansar.", "pausa": 16},
        {"texto": "Siga respirando así, lento y amplio. Note cómo el pecho y el abdomen se mueven con calma, y cómo el cuerpo le agradece este momento.", "pausa": 18},
        {"texto": "Antes de terminar, dígase internamente: puedo volver a esta calma cuando la necesite; está siempre conmigo.", "pausa": 8},
        {"texto": "Muy bien. Abra los ojos con suavidad, mueva las manos y los pies. Lleve esta respiración con usted: tres respiraciones lentas antes de cualquier decisión importante hacen una gran diferencia.", "pausa": 0}]},
    {"id": "experiencia-paz", "icono": "🕊️", "titulo": "Experiencia de Paz", "min": 5,
     "proposito": "Lograr un estado de paz interior mediante la relajación y una imagen luminosa que se expande desde el pecho.",
     "pasos": [
        {"texto": "Bienvenido a esta experiencia de paz. Siéntese cómodo, con la espalda apoyada. Deje las manos sueltas sobre las piernas y cierre suavemente los ojos.", "pausa": 8},
        {"texto": "Relaje el rostro: la frente, los ojos, la mandíbula. Deje caer los hombros. Sienta cómo el cuerpo se va aflojando, parte por parte, sin apuro.", "pausa": 14},
        {"texto": "Aquiete también la mente. Si aparecen pensamientos, no pelee con ellos: déjelos pasar como nubes, y vuelva amablemente a su respiración.", "pausa": 14},
        {"texto": "Ahora imagine una esfera transparente y luminosa que baja lentamente hacia usted... y se aloja con suavidad en el centro de su pecho.", "pausa": 12},
        {"texto": "Sienta que esa esfera deja de ser una imagen y se convierte en una sensación tibia y agradable dentro del pecho.", "pausa": 12},
        {"texto": "Observe cómo esa sensación se expande lentamente desde el centro del pecho hacia todo el cuerpo, mientras su respiración se hace más amplia y profunda.", "pausa": 16},
        {"texto": "Cuando la sensación llegue a los límites de su cuerpo, deténgase ahí. No haga nada más. Solo registre esa experiencia de paz interior.", "pausa": 20},
        {"texto": "Permanezca en este estado unos momentos. Aquí no hay deudas, ni cuentas, ni apuros. Solo usted y esta calma que le pertenece.", "pausa": 20},
        {"texto": "Ahora, con suavidad, haga que esa expansión retroceda lentamente hacia el centro del pecho, como una marea que vuelve.", "pausa": 12},
        {"texto": "Despréndase suavemente de su esfera y concluya el ejercicio sintiéndose calmo y reconfortado. Abra los ojos despacio. Esta paz es suya: puede volver a ella cada vez que lo necesite.", "pausa": 0}]},
    {"id": "soltar-estres", "icono": "🌿", "titulo": "Soltar el estrés económico", "min": 5,
     "proposito": "Aflojar las tensiones que produce la preocupación por la plata y ordenar el problema en pasos chicos.",
     "pasos": [
        {"texto": "Bienvenido. Cuando la plata preocupa, el cuerpo lo siente: tensión, mal dormir, la cabeza dando vueltas. Hoy vamos a aflojar ese peso, juntos. Cierre los ojos si le acomoda.", "pausa": 8},
        {"texto": "Recorra su cuerpo con atención: la frente... la mandíbula... el cuello... los hombros. En cada zona que note apretada, imagine que al soltar el aire esa tensión se disuelve.", "pausa": 16},
        {"texto": "Siga bajando: los brazos, las manos, la espalda, el estómago. La preocupación económica suele apretarse justo ahí, en el estómago. Respire hacia esa zona y déjela ablandarse.", "pausa": 16},
        {"texto": "Ahora, sin angustiarse, permita que aparezca esa preocupación de plata que más pesa. Solo mírela, a distancia, como si estuviera escrita en una hoja sobre una mesa.", "pausa": 14},
        {"texto": "Un problema escrito pesa menos que un problema dando vueltas en la cabeza. Mírelo en esa hoja imaginaria y pregúntese: ¿cuál sería el primer paso más chico posible?", "pausa": 16},
        {"texto": "No necesita la solución completa hoy. Solo ese primer paso: una llamada, anotar los gastos, cotizar, pedir orientación. Véase a usted mismo dando ese paso, con calma.", "pausa": 14},
        {"texto": "Dígase internamente: esta situación es difícil, pero no me define. Millones de personas han pasado por lo mismo y han salido adelante. Yo también puedo, paso a paso.", "pausa": 12},
        {"texto": "Respire profundo una vez más y guarde mentalmente esa hoja: el problema quedó ordenado en pasos, ya no es una nube gigante.", "pausa": 10},
        {"texto": "Abra los ojos con suavidad. Mi consejo de amigo: escriba hoy ese primer paso en un papel real y póngale fecha. El estrés baja cuando el problema tiene un plan, aunque sea chiquito.", "pausa": 0}]},
    {"id": "reconciliacion-financiera", "icono": "🤝", "titulo": "Reconciliación con su historia financiera", "min": 6,
     "proposito": "Mirar los errores de plata del pasado sin culpa ni resentimiento, comprender y empezar de nuevo.",
     "pasos": [
        {"texto": "Bienvenido a esta experiencia de reconciliación. Muchas personas cargan culpa o vergüenza por decisiones de plata del pasado: una deuda, una compra, una confianza traicionada. Hoy vamos a aliviar esa carga. Cierre los ojos y respire profundo.", "pausa": 10},
        {"texto": "Relaje el cuerpo, de la cabeza a los pies. Suelte especialmente el pecho y el estómago, donde suele vivir la culpa.", "pausa": 14},
        {"texto": "Traiga con suavidad a la memoria alguna situación financiera que aún le duela o le dé rabia. Mírela desde hoy, a la distancia, sin meterse de nuevo en ella.", "pausa": 16},
        {"texto": "Comprenda algo importante: usted decidió con la información, el cansancio y las urgencias que tenía en ese momento. No es lo mismo mirar desde hoy que vivir aquel día.", "pausa": 14},
        {"texto": "Reconciliarse no es olvidar ni hacer como que nada pasó. Es comprender lo ocurrido, aprender de ello, y proponerse salir del círculo del resentimiento y la culpa.", "pausa": 14},
        {"texto": "Si otra persona estuvo involucrada, intente comprender que ella también actuó desde sus propios temores y limitaciones. No se trata de buscar culpables, sino de soltar la cadena que lo ata a ese momento.", "pausa": 16},
        {"texto": "Ahora dígase internamente: reconozco lo que pasó, aprendo la lección, y me propongo reparar lo que se pueda reparar, de a poco y sin castigarme.", "pausa": 14},
        {"texto": "Imagine que ese recuerdo, ya comprendido, se vuelve más liviano... como una mochila que por fin puede dejar en el suelo.", "pausa": 14},
        {"texto": "Respire profundo y sienta el espacio nuevo que queda cuando la culpa se va: espacio para planificar, para ahorrar, para empezar de nuevo.", "pausa": 12},
        {"texto": "Abra los ojos despacio. Si quiere sellar esta experiencia, escriba una frase corta: qué aprendió y qué hará distinto. Su historia financiera no terminó: recién está tomando una nueva dirección.", "pausa": 0}]},
    {"id": "claridad-decisiones", "icono": "🧭", "titulo": "Claridad mental para decidir", "min": 5,
     "proposito": "Preparar la mente antes de una decisión financiera importante: sin apuro, sin forzar, con proporción.",
     "pasos": [
        {"texto": "Bienvenido. Esta experiencia es para antes de una decisión importante de plata: un crédito, una compra grande, un cambio de trabajo. Siéntese cómodo, cierre los ojos y respire hondo tres veces.", "pausa": 14},
        {"texto": "Primero, suelte el apuro. Las decisiones tomadas con el cuerpo tenso y la mente acelerada suelen salir caras. Nada se decide en los próximos minutos: solo vamos a mirar con claridad.", "pausa": 12},
        {"texto": "Traiga a la mente la decisión que tiene por delante. Póngala frente a usted, como un objeto sobre una mesa, y obsérvela sin tomar partido todavía.", "pausa": 14},
        {"texto": "Primera pregunta: ¿estoy forzando esta situación? Cuando uno fuerza algo hacia un fin, suele producir lo contrario. Si siente que está empujando de más, quizás no es el momento.", "pausa": 14},
        {"texto": "Segunda pregunta: ¿es el momento oportuno? A veces lo sabio es retroceder un paso hasta que la dificultad se debilite, y avanzar con resolución cuando las condiciones estén a favor.", "pausa": 14},
        {"texto": "Tercera pregunta: ¿guarda proporción con toda mi vida? Una buena decisión no sacrifica la salud, el descanso ni a la familia por un solo objetivo. Mire el conjunto, no solo el número.", "pausa": 14},
        {"texto": "Cuarta pregunta: ¿la comprendo de raíz? Si no puede explicar la decisión con palabras simples a alguien de confianza, todavía falta información. Improvisar complica el problema.", "pausa": 14},
        {"texto": "Ahora imagínese a usted mismo dentro de un año, habiendo decidido bien. ¿Cómo se ve? ¿Qué decisión tomó esa versión suya más tranquila?", "pausa": 16},
        {"texto": "Respire profundo y vuelva. Mi consejo: escriba las respuestas a estas cuatro preguntas y déjelas reposar un día antes de firmar o pagar. La claridad también es plata.", "pausa": 0}]},
    {"id": "frase-de-fuerza", "icono": "⭐", "titulo": "Su frase de fuerza", "min": 4,
     "proposito": "Crear una frase personal, corta y con convicción, que ordene sus pensamientos y sostenga sus metas.",
     "pasos": [
        {"texto": "Bienvenido. Los pensamientos producen y atraen acciones: pensamientos confusos traen acciones confusas, y pensamientos claros y con convicción traen acciones fuertes. Hoy vamos a crear su frase de fuerza. Cierre los ojos.", "pausa": 10},
        {"texto": "Respire lento y conecte con algo a lo que usted aspira de verdad: su casa propia, vivir sin deudas, darle tranquilidad a su familia. Deje que aparezca la imagen, con colores y detalles.", "pausa": 18},
        {"texto": "Sienta esa aspiración crecer. No es un simple deseo: es una dirección, como el timón de un bote. Sin timón, la embarcación gira a merced de las olas; con timón, llega a destino.", "pausa": 14},
        {"texto": "Ahora busque una frase corta y simple que resuma esa dirección. Por ejemplo: avanzo paso a paso hacia mi casa propia. O: cada peso que ordeno me acerca a mi tranquilidad. Tómese su tiempo, la frase es suya.", "pausa": 20},
        {"texto": "Repita internamente su frase, tres veces, con calma y con convicción. Sienta que cada repetición la graba un poco más hondo.", "pausa": 18},
        {"texto": "Recuerde: los pensamientos repetidos con convicción producen y atraen el máximo de fuerza en las acciones. Su frase trabajará por usted cada vez que la repita.", "pausa": 10},
        {"texto": "Abra los ojos. Escriba su frase donde la vea todos los días: el espejo, el celular, la billetera. Y repítala especialmente antes de pagar, ahorrar o decidir. Esa frase es su timón.", "pausa": 0}]},
    {"id": "gratitud-balance", "icono": "🌅", "titulo": "Gratitud y balance del día", "min": 3,
     "proposito": "Cerrar el día reconociendo lo bueno, distinguiendo los actos que dan unidad interna de los que dejan malestar.",
     "pasos": [
        {"texto": "Bienvenido a este cierre de día. Son solo tres minutos para terminar la jornada más liviano. Acomódese, suelte los hombros y respire profundo.", "pausa": 10},
        {"texto": "Repase suavemente su día, como quien mira fotos. Sin juzgar. Solo mire lo que hizo, lo que sintió, con quién estuvo.", "pausa": 14},
        {"texto": "Busque un momento del día que le dejó buena sensación: algo que hizo bien, una conversación amable, incluso haber resistido un gasto innecesario. Los actos que uno quisiera repetir son los que hacen crecer.", "pausa": 16},
        {"texto": "Si hubo algún acto que le dejó malestar, mírelo un instante sin castigarse. Reconocerlo ya es aprender. Mañana tendrá la oportunidad de elegir distinto.", "pausa": 14},
        {"texto": "Ahora agradezca internamente tres cosas de hoy, por simples que sean: el techo, el pan, alguien querido. La gratitud ordena la mente igual que un presupuesto ordena la plata.", "pausa": 16},
        {"texto": "Termine diciéndose: hoy hice lo que pude con lo que tenía, y mañana sigo construyendo. Duerma tranquilo: descansar bien también es cuidar sus finanzas, porque una mente descansada decide mejor.", "pausa": 0}]},
]


@mfin.get("/experiencias")
async def experiencias():
    return {"experiencias": [{k: e[k] for k in ("id", "icono", "titulo", "proposito", "min")} for e in EXPERIENCIAS]}


@mfin.get("/experiencias/{exp_id}")
async def experiencia(exp_id: str):
    for e in EXPERIENCIAS:
        if e["id"] == exp_id:
            return e
    raise HTTPException(status_code=404, detail="Experiencia no encontrada")


@mfin.post("/saludo")
async def saludo_proactivo(payload: dict):
    session = (payload or {}).get("session_id") or f"mf-{uuid.uuid4()}"
    conc = (payload or {}).get("conciencia") or None
    try:
        from zoneinfo import ZoneInfo
        hora = datetime.now(ZoneInfo("America/Santiago"))
    except Exception:
        hora = datetime.now()
    momento = "la mañana" if hora.hour < 12 else ("la tarde" if hora.hour < 20 else "la noche")
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        key = (os.environ.get("EMERGENT_LLM_KEY") or "").strip('"')
        chat = LlmChat(api_key=key, session_id=session, system_message=SISTEMA).with_model("openai", "gpt-5.4-mini")
        extra = ""
        if conc:
            import json as _json
            extra = ("\n[CONCIENCIA — lo que usted ya sabe de esta persona. Si hay algo relevante (una meta, su último "
                     "registro, su ánimo reciente), menciónelo con naturalidad en el saludo, como amigo que la recuerda.]\n"
                     + _json.dumps(conc, ensure_ascii=False)[:2500])
        prompt = (f"[SALUDO PROACTIVO DE APERTURA — es {momento} en Chile, {hora.strftime('%H:%M')} hrs] "
                  "La persona acaba de abrir la app. Salúdela USTED PRIMERO como mentor y amigo, breve y cálido (2 a 3 "
                  "frases, chileno suave, de usted, sin listas ni negritas ni etiqueta emo), y termine SIEMPRE "
                  "preguntando exactamente: '¿Cuánto gastó hoy y cuánto pudo ahorrar?'" + extra)
        resp = await chat.send_message(UserMessage(text=prompt))
        import re as _re2
        texto = _re2.sub(r'^\s*[«"\']*\s*emo\s*:\s*[a-záéíóúñ]+\s*[»"\']*\s*[,.:—-]*\s*', "", str(resp), flags=_re2.I).strip()
    except Exception:
        texto = (f"¡Hola! Qué gusto tenerle por acá esta {momento}. Cuénteme al tiro: "
                 "¿cuánto gastó hoy y cuánto pudo ahorrar?")
    return {"saludo": texto, "session_id": session}


@mfin.post("/conciencia/resumir")
async def conciencia_resumir(payload: dict):
    import json as _json, re as _re
    eventos = (payload or {}).get("eventos") or []
    anterior = (payload or {}).get("resumen_anterior") or {}
    if not eventos:
        raise HTTPException(status_code=400, detail="Sin eventos")
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        key = (os.environ.get("EMERGENT_LLM_KEY") or "").strip('"')
        chat = LlmChat(api_key=key, session_id=f"conc-{uuid.uuid4()}",
                       system_message="Usted consolida la memoria de largo plazo de Martín sobre UNA persona. "
                       "Responda SOLO con JSON válido, sin markdown, con estas claves exactas: "
                       "perfil (string, 3-5 frases: quién es, su situación financiera y de vida), "
                       "personalidad (string breve, tipo detectado), "
                       "metas_pendientes (lista de strings), metas_cumplidas (lista de strings), "
                       "patrones_emocionales (string breve), temas_recurrentes (lista de strings), "
                       "resumen (string, 4-6 frases: la historia completa acumulada). "
                       "Integre el perfil anterior con los eventos nuevos sin perder nada importante. "
                       "Jamás use la palabra 'corazón'.").with_model("openai", "gpt-5.4-mini")
        prompt = ("PERFIL ANTERIOR:\n" + _json.dumps(anterior, ensure_ascii=False)[:2500] +
                  "\n\nEVENTOS NUEVOS (conversaciones y registros recientes):\n" +
                  _json.dumps(eventos, ensure_ascii=False)[:5000])
        resp = str(await chat.send_message(UserMessage(text=prompt)))
        m = _re.search(r'\{.*\}', resp, _re.S)
        data = _json.loads(m.group(0)) if m else {}
        if not data.get("resumen"):
            raise ValueError("sin resumen")
        return {"largo": data}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"No pude consolidar la memoria: {str(e)[:100]}")


@mfin.post("/tts")
async def tts_martin(payload: dict):
    text = ((payload or {}).get("text") or "").strip()
    if len(text) > 4000:
        text = text[:4000]
    if not text:
        raise HTTPException(status_code=400, detail="Sin texto")
    try:
        from emergentintegrations.llm.openai import OpenAITextToSpeech
        tts = OpenAITextToSpeech(api_key=(os.environ.get("EMERGENT_LLM_KEY") or "").strip('"'))
        audio_b64 = await tts.generate_speech_base64(text=text, model="tts-1", voice="onyx")
        return {"audio": audio_b64}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Voz no disponible: {str(e)[:100]}")


ADMIN_CLAVE = "141617575"


def _es_admin(payload):
    return ((payload or {}).get("clave") or "") == ADMIN_CLAVE


async def _cerebro_extra():
    try:
        pers = await db.config.find_one({"_key": "martin_personalidad_extra"}) or {}
        con = await db.config.find_one({"_key": "martin_conocimiento"}) or {}
        extra = ""
        if pers.get("texto"):
            extra += "\nAJUSTE DE PERSONALIDAD (enviado por el administrador a toda la red): " + pers["texto"][:800]
        if con.get("texto"):
            extra += "\nCONOCIMIENTO COLECTIVO DE LA RED DE MARTINS (aprendizaje anónimo de todos los usuarios): " + con["texto"][:800]
        return extra
    except Exception:
        return ""


@mfin.get("/cerebro/sync")
async def cerebro_sync():
    mods = await db.martin_cerebro_modulos.find({"activo": True}, {"_id": 0}).sort("fecha", -1).to_list(30)
    avisos = await db.martin_cerebro_avisos.find({"activo": True}, {"_id": 0}).sort("fecha", -1).to_list(10)
    pers = await db.config.find_one({"_key": "martin_personalidad_extra"}) or {}
    con = await db.config.find_one({"_key": "martin_conocimiento"}) or {}
    marca = await db.config.find_one({"_key": "martin_marca"}) or {}
    return {"modulos": mods, "avisos": avisos, "personalidad_extra": pers.get("texto", ""),
            "conocimiento": con.get("texto", ""), "conocimiento_fecha": con.get("fecha", ""),
            "marca": marca.get("nombre", "")}


@mfin.post("/cerebro/marca")
async def cerebro_marca(payload: dict):
    if not _es_admin(payload):
        raise HTTPException(status_code=403, detail="Clave incorrecta")
    await db.config.update_one({"_key": "martin_marca"},
                               {"$set": {"nombre": (payload.get("nombre") or "")[:80], "fecha": _now()}}, upsert=True)
    return {"ok": True}


@mfin.post("/cerebro/aprendizaje")
async def cerebro_aprendizaje(payload: dict):
    tema = str((payload or {}).get("tema") or "otros")[:30]
    emo = str((payload or {}).get("emocion") or "neutral")[:20]
    await db.martin_cerebro_aprendizajes.insert_one({"id": str(uuid.uuid4()), "tema": tema, "emocion": emo, "fecha": _now()})
    return {"ok": True}


@mfin.post("/cerebro/estado")
async def cerebro_estado(payload: dict):
    if not _es_admin(payload):
        raise HTTPException(status_code=403, detail="Clave incorrecta")
    total = await db.martin_cerebro_aprendizajes.count_documents({})
    por_tema, por_emo = {}, {}
    async for a in db.martin_cerebro_aprendizajes.find({}).sort("fecha", -1).limit(500):
        por_tema[a.get("tema", "otros")] = por_tema.get(a.get("tema", "otros"), 0) + 1
        por_emo[a.get("emocion", "neutral")] = por_emo.get(a.get("emocion", "neutral"), 0) + 1
    mods = await db.martin_cerebro_modulos.find({}, {"_id": 0}).sort("fecha", -1).to_list(50)
    avisos = await db.martin_cerebro_avisos.find({}, {"_id": 0}).sort("fecha", -1).to_list(20)
    pers = await db.config.find_one({"_key": "martin_personalidad_extra"}) or {}
    con = await db.config.find_one({"_key": "martin_conocimiento"}) or {}
    return {"aprendizajes_total": total, "por_tema": por_tema, "por_emocion": por_emo,
            "modulos": mods, "avisos": avisos, "personalidad_extra": pers.get("texto", ""),
            "conocimiento": con.get("texto", ""), "conocimiento_fecha": con.get("fecha", "")}


@mfin.post("/cerebro/modulo")
async def cerebro_modulo(payload: dict):
    if not _es_admin(payload):
        raise HTTPException(status_code=403, detail="Clave incorrecta")
    mid = (payload.get("id") or "").strip() or f"mod-{uuid.uuid4().hex[:6]}"
    doc = {"id": mid, "icono": (payload.get("icono") or "🛰")[:4], "titulo": (payload.get("titulo") or "")[:60],
           "sub": (payload.get("sub") or "")[:90], "color": (payload.get("color") or "#E9E4FF")[:9],
           "cuerpo": (payload.get("cuerpo") or "")[:8000], "activo": bool(payload.get("activo", True)), "fecha": _now()}
    if not doc["titulo"] or not doc["cuerpo"]:
        raise HTTPException(status_code=400, detail="Falta título o contenido")
    await db.martin_cerebro_modulos.update_one({"id": mid}, {"$set": doc}, upsert=True)
    return {"ok": True, "id": mid}


@mfin.post("/cerebro/modulo/eliminar")
async def cerebro_modulo_del(payload: dict):
    if not _es_admin(payload):
        raise HTTPException(status_code=403, detail="Clave incorrecta")
    await db.martin_cerebro_modulos.update_one({"id": payload.get("id")}, {"$set": {"activo": False}})
    return {"ok": True}


@mfin.post("/cerebro/aviso")
async def cerebro_aviso(payload: dict):
    if not _es_admin(payload):
        raise HTTPException(status_code=403, detail="Clave incorrecta")
    if payload.get("eliminar"):
        await db.martin_cerebro_avisos.update_one({"id": payload["eliminar"]}, {"$set": {"activo": False}})
        return {"ok": True}
    doc = {"id": f"av-{uuid.uuid4().hex[:6]}", "titulo": (payload.get("titulo") or "")[:80],
           "texto": (payload.get("texto") or "")[:1200], "activo": True, "fecha": _now()}
    if not doc["texto"]:
        raise HTTPException(status_code=400, detail="Falta el texto")
    await db.martin_cerebro_avisos.insert_one(doc)
    return {"ok": True, "id": doc["id"]}


@mfin.post("/cerebro/personalidad")
async def cerebro_personalidad(payload: dict):
    if not _es_admin(payload):
        raise HTTPException(status_code=403, detail="Clave incorrecta")
    await db.config.update_one({"_key": "martin_personalidad_extra"},
                               {"$set": {"texto": (payload.get("texto") or "")[:1500], "fecha": _now()}}, upsert=True)
    return {"ok": True}


@mfin.post("/cerebro/procesar")
async def cerebro_procesar(payload: dict):
    if not _es_admin(payload):
        raise HTTPException(status_code=403, detail="Clave incorrecta")
    datos = await db.martin_cerebro_aprendizajes.find({}, {"_id": 0}).sort("fecha", -1).limit(300).to_list(300)
    if not datos:
        raise HTTPException(status_code=400, detail="Aún no hay aprendizajes en la red")
    resumen = {}
    for a in datos:
        k = f"{a.get('tema','otros')}/{a.get('emocion','neutral')}"
        resumen[k] = resumen.get(k, 0) + 1
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        key = (os.environ.get("EMERGENT_LLM_KEY") or "").strip('"')
        chat = LlmChat(api_key=key, session_id=f"cerebro-{uuid.uuid4()}",
                       system_message="Usted es El Cerebro de la red de Martins. Recibe conteos anónimos "
                       "tema/emoción de todas las conversaciones de la red y produce en 4-6 frases el "
                       "'conocimiento colectivo': qué temas dominan, qué emociones se repiten, y CÓMO deben "
                       "adaptar todos los Martins su acompañamiento esta semana. Español chileno, de usted, "
                       "sin la palabra 'corazón'.").with_model("openai", "gpt-5.4-mini")
        import json as _json
        resp = str(await chat.send_message(UserMessage(text="Conteos tema/emoción: " + _json.dumps(resumen, ensure_ascii=False))))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Cerebro no disponible: {str(e)[:100]}")
    await db.config.update_one({"_key": "martin_conocimiento"},
                               {"$set": {"texto": resp[:2000], "fecha": _now(), "muestras": len(datos)}}, upsert=True)
    return {"ok": True, "conocimiento": resp, "muestras": len(datos)}


@mfin.get("/temas")
async def temas():
    return {"temas": [
        {"icono": "🐷", "titulo": "Ahorro", "pregunta": "¿Cómo puedo empezar a ahorrar si mi sueldo apenas me alcanza?"},
        {"icono": "🧾", "titulo": "Presupuesto", "pregunta": "¿Cómo armo un presupuesto familiar simple para mi hogar?"},
        {"icono": "💳", "titulo": "Deudas", "pregunta": "Tengo varias deudas y no sé por dónde partir, ¿qué me recomienda?"},
        {"icono": "🌱", "titulo": "Hábitos", "pregunta": "¿Qué hábitos financieros pequeños puedo empezar hoy mismo?"},
        {"icono": "👨‍👩‍👧", "titulo": "Familia", "pregunta": "¿Cómo enseño a mis hijos a manejar la plata?"},
        {"icono": "🚨", "titulo": "Emergencias", "pregunta": "¿Qué es un fondo de emergencia y cómo lo armo de a poco?"},
        {"icono": "🏠", "titulo": "Subsidios", "pregunta": "¿Qué subsidios habitacionales existen en Chile y cuál me podría servir?"},
        {"icono": "🎁", "titulo": "Beneficios", "pregunta": "¿Qué beneficios del Estado puedo revisar para mi familia?"},
        {"icono": "🌿", "titulo": "Bienestar", "pregunta": "Las deudas me tienen con mucho estrés, ¿cómo puedo manejarlo?"},
        {"icono": "💪", "titulo": "Autoestima", "pregunta": "Me siento poca cosa por mi situación económica, ¿qué me aconseja?"},
        {"icono": "🚀", "titulo": "Emprender", "pregunta": "Quiero emprender un pequeño negocio, ¿por dónde parto sin arriesgar la plata de mi casa?"},
    ]}
