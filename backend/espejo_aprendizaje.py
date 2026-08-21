"""🪞 ALGORITMO ESPEJO — CAPA 1 (aprobaciones@centralmutuos.cl).
Aprende los criterios de mesa desde los datos ya espejados (simulaciones,
resultados de mesa en carpetas y correos a mesa) y predice la probabilidad
de aprobación de cada carpeta con sus factores de mayor peso.
PERÍODO DE APRENDIZAJE: siempre los últimos 3 MESES CALENDARIO desde la fecha
actual, actualizado automáticamente cada día — sin límite de cantidad de casos
dentro del período: se procesan TODOS. Lo que sale del rango se descarta y lo
nuevo se suma solo.
DISEÑO MODULAR POR CAPAS: cada caso de aprendizaje lleva `origen`
("capa1_simulaciones", "capa1_mesa", "capa2_mbox"). Cuando lleguen los
13.000 correos históricos (.mbox de Daniela Galindo) solo se insertan casos
con origen capa2 y se re-entrena: NADA de la capa 1 se reescribe."""
import asyncio
import logging
import math
import re
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from database import db

espia = APIRouter()
ROLES_VER = ("admin", "maestro", "administracion", "gerencia", "contralor", "broker", "postventa")


def _exigir(request, roles=ROLES_VER):
    c = getattr(request.state, "user", {}) or {}
    if c.get("rol") not in roles:
        raise HTTPException(status_code=403, detail="Su rol no tiene acceso a esta función")
    return c


def _now():
    return datetime.now(timezone.utc).isoformat()


def _rut8(r):
    return re.sub(r"[^0-9kK]", "", r or "").lower()[:8]


def _corte_3_meses():
    """Inicio del período de aprendizaje: 3 meses calendario atrás desde hoy."""
    hoy = datetime.now(timezone.utc)
    m = hoy.month - 3
    y = hoy.year + (m - 1) // 12
    m = (m - 1) % 12 + 1
    return hoy.replace(year=y, month=m, day=min(hoy.day, 28))


def _dtu(ts):
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


# ── Extracción de rasgos (compartida por todas las capas) ──
def _bucket_monto(uf):
    if not uf:
        return None
    return "monto<1500UF" if uf < 1500 else "monto1500-3000UF" if uf < 3000 \
        else "monto3000-5000UF" if uf < 5000 else "monto>5000UF"


def _bucket_plazo(a):
    if not a:
        return None
    return "plazo<=15a" if a <= 15 else "plazo16-25a" if a <= 25 else "plazo>25a"


def _bucket_ltv(v):
    if v is None:
        return None
    return "ltv<=70" if v <= 70 else "ltv71-80" if v <= 80 else "ltv>80"


def _bucket_carga(v):
    if v is None:
        return None
    return "carga<=25%" if v <= 25 else "carga26-35%" if v <= 35 else "carga>35%"


def _features_sim(s):
    fts = [_bucket_monto(s.get("credito_solicitado_uf") or s.get("credito_maximo_uf")),
           _bucket_plazo(s.get("plazo_anos")),
           _bucket_ltv(s.get("ltv")),
           _bucket_carga(s.get("carga_fin_conjunta") or s.get("carga_fin_individual")),
           "con_codeudor" if s.get("tiene_codeudor") else "sin_codeudor"]
    return [f for f in fts if f]


def _features_folder(f, criterios):
    fts = []
    for c in criterios:
        n = c.get("nombre") or ""
        if n in ("Enviada a mesa", "Datos financieros completos"):
            continue
        fts.append(("doc_ok:" if c.get("ok") else "doc_falta:") + n)
    return fts


ETIQUETAS = {"monto<1500UF": "Monto solicitado bajo 1.500 UF", "monto1500-3000UF": "Monto entre 1.500 y 3.000 UF",
             "monto3000-5000UF": "Monto entre 3.000 y 5.000 UF", "monto>5000UF": "Monto sobre 5.000 UF",
             "plazo<=15a": "Plazo hasta 15 años", "plazo16-25a": "Plazo 16 a 25 años", "plazo>25a": "Plazo sobre 25 años",
             "ltv<=70": "Financiamiento ≤70% (LTV)", "ltv71-80": "Financiamiento 71–80% (LTV)", "ltv>80": "Financiamiento >80% (LTV)",
             "carga<=25%": "Carga financiera ≤25%", "carga26-35%": "Carga financiera 26–35%", "carga>35%": "Carga financiera >35%",
             "con_codeudor": "Con codeudor", "sin_codeudor": "Sin codeudor",
             "edad<30": "Solicitante menor de 30 años", "edad30-45": "Edad 30–45 años",
             "edad46-60": "Edad 46–60 años", "edad>60": "Edad sobre 60 años",
             "renta<1M": "Renta bajo $1.000.000", "renta1-2M": "Renta $1M–$2M", "renta>2M": "Renta sobre $2.000.000",
             "con_subsidio": "Con subsidio estatal", "sin_subsidio": "Sin subsidio",
             "vivienda_nueva": "Vivienda nueva / entrega futura", "vivienda_usada": "Vivienda usada",
             "casa": "Propiedad tipo casa", "departamento": "Propiedad tipo departamento",
             "adjuntos_1-3": "Envío con 1–3 adjuntos", "adjuntos_4-6": "Envío con 4–6 adjuntos",
             "adjuntos_7+": "Envío con 7 o más adjuntos"}

# tipos de documento detectables en los nombres de archivos adjuntos enviados a mesa
DOC_PATRONES = [("adj:Liquidaciones de sueldo", r"liquidaci"), ("adj:Cédula de identidad", r"cedula|c%c3%a9dula|carnet|ci_"),
                ("adj:Cotizaciones AFP", r"afp|cotizaci|previsional"), ("adj:Informe CMF", r"cmf|deuda"),
                ("adj:Boletas de honorarios", r"boleta|honorario"), ("adj:Declaración de impuestos", r"impuesto|renta|tributar|f22"),
                ("adj:Contrato de trabajo", r"contrato|vigencia"), ("adj:Simulación/Precalificación", r"simulaci|precalific"),
                ("adj:Certificado de subsidio", r"subsidio|serviu|ds19|ds49|ds1")]


def _features_adjuntos(nombres):
    fts = set()
    texto = " ".join(n.lower() for n in nombres)
    for feat, pat in DOC_PATRONES:
        if re.search(pat, texto):
            fts.add(feat)
    n = len(nombres)
    if n:
        fts.add("adjuntos_1-3" if n <= 3 else "adjuntos_4-6" if n <= 6 else "adjuntos_7+")
    return sorted(fts)


def _etiqueta(f):
    if f.startswith("doc_ok:"):
        return f"Documento presente: {f[7:]}"
    if f.startswith("doc_falta:"):
        return f"Documento faltante: {f[10:]}"
    if f.startswith("adj:"):
        return f"Adjunto enviado a mesa: {f[4:]}"
    return ETIQUETAS.get(f, f)


# ── Datos financieros desde los PDF del hilo (monto, plazo, edad, renta, subsidio, vivienda) ──
def _bucket_edad(e):
    if not e:
        return None
    return "edad<30" if e < 30 else "edad30-45" if e <= 45 else "edad46-60" if e <= 60 else "edad>60"


def _bucket_renta(r):
    if not r:
        return None
    return "renta<1M" if r < 1_000_000 else "renta1-2M" if r <= 2_000_000 else "renta>2M"


def _num(s):
    try:
        return float(s.replace(".", "").replace(",", "."))
    except (ValueError, AttributeError):
        return None


def _datos_desde_texto_pdf(texto):
    t = (texto or "").lower()
    d = {}
    m = re.search(r"(?:monto|cr[eé]dito)(?:\s+\w+){0,4}?[:\s]+(?:uf\s*)?([\d.,]+)\s*(?:uf)?", t)
    if m and (v := _num(m.group(1))) and 100 < v < 20000:
        d["monto_uf"] = v
    m = re.search(r"plazo(?:\s+\w+){0,3}?[:\s]+(\d{1,2})\s*a[ñn]os", t)
    if m:
        d["plazo_anos"] = int(m.group(1))
    m = re.search(r"edad(?:\s+\w+){0,2}?[:\s]+(\d{2})", t)
    if m and 18 <= int(m.group(1)) <= 80:
        d["edad"] = int(m.group(1))
    m = re.search(r"renta(?:\s+\w+){0,4}?[:\s]+\$?\s*([\d.,]{6,})", t)
    if m and (v := _num(m.group(1))):
        d["renta"] = v
    d["subsidio"] = "con_subsidio" if re.search(r"subsidio|ds\s?19|ds\s?49|ds\s?1\b|serviu", t) else "sin_subsidio"
    if re.search(r"vivienda\s+nueva|entrega\s+inmediata|en\s+verde|futura", t):
        d["vivienda"] = "vivienda_nueva"
    elif re.search(r"vivienda\s+usada", t):
        d["vivienda"] = "vivienda_usada"
    if re.search(r"\bdepartamento\b|\bdepto\b", t):
        d["tipo_prop"] = "departamento"
    elif re.search(r"\bcasa\b", t):
        d["tipo_prop"] = "casa"
    return d


def _features_datos(d):
    fts = [_bucket_monto(d.get("monto_uf")), _bucket_plazo(d.get("plazo_anos")),
           _bucket_edad(d.get("edad")), _bucket_renta(d.get("renta")),
           d.get("subsidio"), d.get("vivienda"), d.get("tipo_prop")]
    return [f for f in fts if f]


async def _enriquecer_hilos(hilos, max_nuevos=12):
    """Baja los PDF del hilo (con caché en db.espejo_hilos_datos) y agrega los
    datos financieros como rasgos del caso. Máx N descargas nuevas por corrida
    para cuidar la cuota IMAP; el resto se completa en corridas siguientes."""
    nuevos = 0
    for h in hilos:
        cache = await db.espejo_hilos_datos.find_one({"clave": h["clave"]})
        if cache:
            h["datos"] = cache.get("datos") or {}
            h["features"] = sorted(set(h["features"] + (cache.get("features") or [])))
            continue
        if nuevos >= max_nuevos:
            continue
        nuevos += 1
        nombre = re.sub(r"\(.*", "", h.get("asunto") or "").replace("Re:", "").strip()[:40]
        datos = {}
        try:
            from server import _imap_descargar_adjuntos_cliente
            import pdf_service as pdfs
            pares = await asyncio.to_thread(_imap_descargar_adjuntos_cliente, nombre)
            for _fn, raw in (pares or [])[:4]:
                try:
                    texto = await asyncio.to_thread(pdfs.leer_texto, raw, 3)
                    for k, v in _datos_desde_texto_pdf(texto).items():
                        datos.setdefault(k, v)
                except Exception:
                    continue
        except Exception as e:
            logging.warning(f"espejo datos pdf {nombre}: {e}")
        fts = _features_datos(datos)
        await db.espejo_hilos_datos.update_one({"clave": h["clave"]}, {"$set": {
            "clave": h["clave"], "nombre": nombre, "datos": datos, "features": fts,
            "actualizado": _now()}}, upsert=True)
        h["datos"] = datos
        h["features"] = sorted(set(h["features"] + fts))
    return hilos
RE_VEREDICTO_OK = re.compile(r"tenemos\s+el\s+agrado\s+de\s+informar|califica\s+para\s+un\s+mutuo\s+hipotecari"
                             r"|mutuo\s+hipotecario\s+endosable|adjuntamos\s+carta\s+y\s+simulaci[oó]n"
                             r"|subsidio\s+estatal|\bpre.?aprobad|\baprobad[oa]|\bviable\b|\bprocede\b", re.I)
RE_VEREDICTO_NO = re.compile(r"no\s+cumple\s+(?:los\s+)?par[aá]metros\s+objetivos\s+m[ií]nimos"
                             r"|par[aá]metros\s+objetivos\s+m[ií]nimos\s+de\s+aprobaci[oó]n"
                             r"|\brechaz|\bno\s+cumple|\bno\s+aprobad|\bdeclinad|\bno\s+califica"
                             r"|pasad[oa]\s+en\s+carga|sobre.?endeud|excede\s+(la\s+)?(carga|renta)", re.I)
RE_LIMPIA_ASUNTO = re.compile(r"^\s*((re|rv|fw|fwd|reenv\w*)\s*:\s*)+", re.I)


def _asunto_norm(s):
    s = RE_LIMPIA_ASUNTO.sub("", s or "").lower()
    return re.sub(r"[^a-z0-9áéíóúñ]+", " ", s).strip()[:80]


def _fetch_tuplas(m, ids, query, chunk=60):
    out = []
    for k in range(0, len(ids), chunk):
        sub = b",".join(ids[k:k + chunk])
        try:
            _, data = m.fetch(sub, query)
        except Exception:
            break
        out.extend(t for t in data if isinstance(t, tuple) and t[1])
    return out


def _bodystructures(m, ids, chunk=100):
    """BODYSTRUCTURE por mensaje (sin descargar adjuntos): seq → nombres de archivo."""
    res = {}
    for k in range(0, len(ids), chunk):
        sub = b",".join(ids[k:k + chunk])
        try:
            _, data = m.fetch(sub, "(BODYSTRUCTURE)")
        except Exception:
            break
        for item in data:
            s = ((item[0] + b" " + item[1]) if isinstance(item, tuple) else item or b"").decode(errors="ignore")
            mm = re.match(r"(\d+)\s", s)
            if not mm:
                continue
            nombres = re.findall(r'"(?:name|filename)\*?"\s+"([^"]{3,120})"', s, re.I)
            res[mm.group(1)] = [_dec_nombre(n) for n in nombres if "." in n or "=?" in n]
    return res


def _dec_nombre(n):
    try:
        import email_service as mail
        return mail._dec(n)
    except Exception:
        return n


def _decodifica_snippet(b):
    """Elige la decodificación (plano / quoted-printable / base64) con más texto legible."""
    import base64 as b64
    import quopri
    candidatos = [b or b""]
    try:
        candidatos.append(quopri.decodestring(b))
    except Exception:
        pass
    try:
        limpio = re.sub(rb"\s", b"", b or b"")
        candidatos.append(b64.b64decode(limpio + b"=" * (-len(limpio) % 4)))
    except Exception:
        pass
    mejor, score = "", -1
    for c in candidatos:
        t = c.decode("utf-8", errors="ignore")
        s = sum(ch.isalpha() or ch.isspace() for ch in t[:400])
        if s > score:
            mejor, score = t, s
    return mejor


def _leer_hilos_mesa(dias=92):
    """Lee el buzón completo (3 meses) de forma LIVIANA (sin descargar adjuntos):
    encabezados + nombres de adjuntos (BODYSTRUCTURE) + 2KB del texto de la
    respuesta de mesa. Empareja envío → veredicto por asunto normalizado."""
    import email as email_lib
    import email_service as mail
    import os as _os
    mesa = _os.environ.get("MESA_EMAIL", "aprobaciones@centralmutuos.cl")
    if not mail.configured():
        return []
    acc = next((a for a in mail.ACCOUNTS if a["rol"] == "secundaria"), mail.ACCOUNTS[0])
    m = mail._connect(acc)
    try:
        folder = mail._all_mail_folder(m)
        m.select(f'"{folder}"' if folder else "INBOX", readonly=True)
        desde = (datetime.now(timezone.utc) - timedelta(days=dias)).strftime("%d-%b-%Y")

        def _ids(criterio):
            try:
                _, data = m.search(None, criterio)
                return (data[0] or b"").split()[-600:]
            except Exception:
                return []

        ids_env = _ids(f'(SINCE "{desde}" TO "{mesa}")')
        ids_res = _ids(f'(SINCE "{desde}" FROM "{mesa}")')

        # ENVIADOS: asunto + nombres de adjuntos (sin bajar contenido)
        enviados = {}
        heads = _fetch_tuplas(m, ids_env, "(BODY.PEEK[HEADER.FIELDS (SUBJECT DATE)])")
        estructuras = _bodystructures(m, ids_env)
        for idx, t in enumerate(heads):
            h = email_lib.message_from_bytes(t[1])
            subject = mail._dec(h.get("Subject"))
            clave = _asunto_norm(subject)
            if not clave:
                continue
            seq = (re.match(rb"(\d+)\s", t[0]) or [None, b""])[1].decode() if re.match(rb"(\d+)\s", t[0]) else \
                (ids_env[idx].decode() if idx < len(ids_env) else "")
            adjuntos = estructuras.get(seq) or []
            prev = enviados.get(clave)
            if not prev or len(adjuntos) > len(prev["adjuntos"]):
                enviados[clave] = {"subject": subject, "adjuntos": adjuntos, "fecha": mail._dec(h.get("Date"))}

        # RESPUESTAS DE MESA: asunto + 2KB del texto para detectar veredicto
        respuestas = []
        heads_r = _fetch_tuplas(m, ids_res, "(BODY.PEEK[HEADER.FIELDS (SUBJECT DATE)])")
        cuerpos = _fetch_tuplas(m, ids_res, "(BODY.PEEK[1]<0.2048>)")
        for idx, t in enumerate(heads_r):
            h = email_lib.message_from_bytes(t[1])
            subject = mail._dec(h.get("Subject"))
            clave = _asunto_norm(subject)
            if not clave:
                continue
            snippet = _decodifica_snippet(cuerpos[idx][1]) if idx < len(cuerpos) else ""
            fecha_raw = h.get("Date")
            try:
                from email.utils import parsedate_to_datetime
                fecha = parsedate_to_datetime(fecha_raw).isoformat()
            except Exception:
                fecha = _now()
            respuestas.append({"clave": clave, "subject": subject, "texto": f"{subject} {snippet}", "fecha": fecha})

        casos = []
        for resp in respuestas:
            if RE_VEREDICTO_NO.search(resp["texto"]):
                resultado = "reprobado"
            elif RE_VEREDICTO_OK.search(resp["texto"]):
                resultado = "aprobado"
            else:
                continue
            envio = enviados.get(resp["clave"]) or next(
                (v for k, v in enviados.items() if k and (k in resp["clave"] or resp["clave"] in k)), None)
            if not envio or not envio["adjuntos"]:
                continue
            casos.append({"clave": resp["clave"], "resultado": resultado, "fecha_caso": resp["fecha"],
                          "features": _features_adjuntos(envio["adjuntos"]),
                          "adjuntos": envio["adjuntos"][:15], "asunto": envio["subject"][:120],
                          "respuesta_asunto": resp["subject"][:120]})
        return casos
    finally:
        try:
            m.logout()
        except Exception:
            pass


# ── Construcción de casos CAPA 1 (ventana móvil de 3 meses, TODOS los casos) ──
async def _reconstruir_casos_capa1():
    corte = _corte_3_meses()
    await db.espejo_casos.delete_many({"origen": {"$regex": "^capa1"}})
    casos = []
    async for s in db.simulaciones.find({"precalificacion_aprobada": {"$in": [True, False]}}):
        if (_dtu(s.get("timestamp")) or datetime.now(timezone.utc)) < corte:
            continue
        casos.append({"id": str(uuid.uuid4()), "origen": "capa1_simulaciones",
                      "fecha_caso": s.get("timestamp") or _now(),
                      "resultado": "aprobado" if s.get("precalificacion_aprobada") else "reprobado",
                      "features": _features_sim(s),
                      "razones": [r for r in (s.get("razones_rechazo") or []) if r][:6],
                      "rut": _rut8(s.get("rut"))})
    from server import _criterios_folder
    sims_por_rut = {}
    async for s in db.simulaciones.find({}).sort("timestamp", -1).limit(3000):
        sims_por_rut.setdefault(_rut8(s.get("rut")), s)
    async for f in db.folders.find({"resultado_mesa": {"$in": ["aprobado", "reprobado"]}}):
        fecha = f.get("resultado_mesa_at") or f.get("updated_at") or _now()
        if (_dtu(fecha) or datetime.now(timezone.utc)) < corte:
            continue
        try:
            crit = _criterios_folder(f)
        except Exception:
            crit = []
        fts = _features_folder(f, crit)
        sim = sims_por_rut.get(_rut8(f.get("rut")))
        if sim:
            fts += _features_sim(sim)
        casos.append({"id": str(uuid.uuid4()), "origen": "capa1_mesa",
                      "fecha_caso": fecha, "resultado": f.get("resultado_mesa"),
                      "features": sorted(set(fts)), "razones": [], "rut": _rut8(f.get("rut"))})
    if casos:
        await db.espejo_casos.insert_many(casos)
    # HILOS CON MESA: envío con adjuntos → respuesta con veredicto (fuente principal)
    try:
        hilos = await asyncio.to_thread(_leer_hilos_mesa, 92)
    except Exception as e:
        logging.warning(f"espejo hilos mesa: {e}")
        hilos = []
    if hilos:
        hilos = await _enriquecer_hilos(hilos)
        docs = [{"id": str(uuid.uuid4()), "origen": "capa1_hilos",
                 "fecha_caso": h["fecha_caso"], "resultado": h["resultado"],
                 "features": h["features"], "razones": [], "datos": h.get("datos") or {},
                 "adjuntos": h["adjuntos"], "asunto": h["asunto"],
                 "respuesta_asunto": h["respuesta_asunto"], "rut": ""} for h in hilos]
        await db.espejo_casos.insert_many(docs)
        casos += docs
    return len(casos)


# ── Entrenamiento: TODAS las capas, solo casos dentro de los últimos 3 meses ──
async def entrenar():
    n_capa1 = await _reconstruir_casos_capa1()
    corte = _corte_3_meses()
    todos = await db.espejo_casos.find({}, {"_id": 0}).to_list(None)
    casos = [c for c in todos if (_dtu(c.get("fecha_caso")) or corte) >= corte]
    n = len(casos)
    aprob = [c for c in casos if c["resultado"] == "aprobado"]
    n_a = len(aprob)
    base = (n_a + 1) / (n + 2)                       # suavizado de Laplace
    base_logit = math.log(base / (1 - base))
    conteo_f, conteo_fa = Counter(), Counter()
    for c in casos:
        for f in set(c.get("features") or []):
            conteo_f[f] += 1
            if c["resultado"] == "aprobado":
                conteo_fa[f] += 1
    pesos = {}
    for f, nf in conteo_f.items():
        p = (conteo_fa[f] + 1) / (nf + 2)
        peso = max(-1.8, min(1.8, math.log(p / (1 - p)) - base_logit))
        pesos[f] = round(peso, 3)
    razones = Counter()
    for c in casos:
        for r in c.get("razones") or []:
            razones[r.strip()[:90]] += 1
    razones_top = [{"razon": r, "casos": k} for r, k in razones.most_common(10)]
    origen_stats = Counter(c["origen"] for c in casos)
    # Registro de EVOLUCIÓN: qué aprendió de nuevo esta versión
    prev = await db.espejo_modelo.find_one({}, sort=[("version", -1)]) or {}
    nuevos_f = sorted(set(pesos) - set(prev.get("pesos") or {}))
    nuevas_r = [r["razon"] for r in razones_top if r["razon"] not in
                {x["razon"] for x in (prev.get("razones_top") or [])}]
    aprendizajes = ([f"Nuevo patrón aprendido: {_etiqueta(f)} (peso {pesos[f]:+.2f})" for f in nuevos_f[:8]]
                    + [f"Nuevo criterio de rechazo de mesa: {r}" for r in nuevas_r[:6]])
    if not prev:
        aprendizajes.insert(0, f"Capa 1 del Algoritmo Espejo inicializada con {n} casos de aprobaciones@centralmutuos.cl")
    if n != prev.get("n_casos"):
        aprendizajes.append(f"Base de casos: {prev.get('n_casos') or 0} → {n}")
    version = int(prev.get("version") or 0) + 1
    doc = {"version": version, "fecha": _now(), "n_casos": n, "n_aprobados": n_a,
           "n_reprobados": n - n_a,
           "n_capa1": n_capa1, "origenes": dict(origen_stats),
           "periodo": {"desde": corte.isoformat(), "hasta": _now(), "regla": "últimos 3 meses calendario, móvil diario"},
           "tasa_base": round(base, 4), "base_logit": round(base_logit, 4),
           "pesos": pesos, "razones_top": razones_top, "aprendizajes": aprendizajes}
    await db.espejo_modelo.insert_one(dict(doc))
    logging.info(f"🪞 Espejo capa 1 entrenado: v{version} · {n} casos · {len(pesos)} patrones")
    return doc


async def _modelo_actual():
    return await db.espejo_modelo.find_one({}, {"_id": 0}, sort=[("version", -1)])


# ── Predicción por carpeta ──
async def predecir_folder(f):
    m = await _modelo_actual()
    if not m:
        m = await entrenar()
        m.pop("_id", None)
    from server import _criterios_folder
    try:
        crit = _criterios_folder(f)
    except Exception:
        crit = []
    fts = _features_folder(f, crit)
    sim = await db.simulaciones.find_one({"rut": {"$regex": _rut8(f.get("rut")) or "^$", "$options": "i"}},
                                         sort=[("timestamp", -1)]) if f.get("rut") else None
    if not sim and f.get("nombre"):
        sim = await db.simulaciones.find_one({"nombre_completo": {"$regex": re.escape(f["nombre"][:18]), "$options": "i"}},
                                             sort=[("timestamp", -1)])
    if sim:
        fts += _features_sim(sim)
    fts = sorted(set(fts))
    pesos = m.get("pesos") or {}
    logit = m.get("base_logit") or 0
    factores = []
    for ft in fts:
        w = pesos.get(ft)
        if w is None:
            continue
        logit += w
        factores.append({"factor": _etiqueta(ft), "peso": w,
                         "direccion": "a favor" if w > 0 else "en contra" if w < 0 else "neutro"})
    prob = 1 / (1 + math.exp(-logit))
    nivel = "alta" if prob >= 0.65 else "media" if prob >= 0.40 else "baja"
    factores.sort(key=lambda x: -abs(x["peso"]))
    return {"probabilidad": round(prob * 100, 1), "nivel": nivel,
            "factores": factores[:6], "resultado_real": f.get("resultado_mesa"),
            "modelo_version": m.get("version"), "modelo_fecha": m.get("fecha"),
            "casos_aprendidos": m.get("n_casos"), "capas": m.get("origenes") or {}}


# ── Loop: ventana móvil de 3 meses re-entrenada automáticamente CADA DÍA ──
async def espejo_aprendizaje_loop():
    await asyncio.sleep(120)
    while True:
        try:
            hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            n_sim = await db.simulaciones.count_documents({"precalificacion_aprobada": {"$in": [True, False]}})
            n_mesa = await db.folders.count_documents({"resultado_mesa": {"$in": ["aprobado", "reprobado"]}})
            m = await _modelo_actual()
            firma = f"{hoy}|{n_sim}|{n_mesa}"           # cambia cada día → la ventana avanza sola
            if not m or m.get("firma_datos") != firma:
                doc = await entrenar()
                await db.espejo_modelo.update_one({"version": doc["version"]}, {"$set": {"firma_datos": firma}})
        except Exception as e:
            logging.warning(f"espejo_aprendizaje_loop: {e}")
        await asyncio.sleep(3600)


# ── Endpoints ──
@espia.get("/espejo-ia/prediccion/{fid}")
async def espejo_prediccion(fid: str, request: Request):
    _exigir(request)
    f = await db.folders.find_one({"id": fid})
    if not f:
        raise HTTPException(status_code=404, detail="Carpeta no encontrada")
    return await predecir_folder(f)


@espia.get("/espejo-ia/modelo")
async def espejo_modelo(request: Request):
    _exigir(request, ("admin", "maestro"))
    m = await _modelo_actual()
    return m or {"version": 0, "n_casos": 0, "pesos": {}, "aprendizajes": []}


@espia.get("/espejo-ia/evolucion")
async def espejo_evolucion(request: Request):
    _exigir(request, ("admin", "maestro"))
    vs = await db.espejo_modelo.find({}, {"_id": 0, "pesos": 0}).sort("version", -1).limit(50).to_list(50)
    return {"versiones": vs, "total": len(vs)}


@espia.post("/espejo-ia/entrenar")
async def espejo_entrenar(request: Request):
    _exigir(request, ("admin", "maestro"))
    doc = await entrenar()
    doc.pop("_id", None)
    return doc
