"""🗄️ MÓDULO VICTORIA INDEPENDIENTE — bóveda propia, monitoreo del correo de
Victoria, clasificación de sets de crédito, auditoría automática según manual
ConCreces y validación de coincidencias (Reglas de Oro 11-14, irrenunciables)."""
import os
import re
import json
import uuid
import asyncio
import hashlib
import logging
import unicodedata
from pathlib import Path
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from database import db

vict = APIRouter(prefix="/victoria")
BOVEDA_DIR = Path("/app/boveda_victoria")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _exigir(request):
    c = getattr(request.state, "user", {}) or {}
    if c.get("rol") not in ("admin", "maestro", "administracion"):
        raise HTTPException(status_code=403, detail="Solo Administración o el Administrador")
    return c


# ══════════ REGLAS DE ORO DE COINCIDENCIA (irrenunciables) ══════════
REGLAS_ORO_COINCIDENCIA = [
    ("ORO_CONCRECES_11", "El RUT del cliente principal debe coincidir EXACTAMENTE en todos los documentos donde aparezca. Cualquier diferencia bloquea el avance con alerta crítica."),
    ("ORO_CONCRECES_12", "El RUT del codeudor debe coincidir EXACTAMENTE en todos los documentos donde aparezca. Cualquier diferencia bloquea el avance con alerta crítica."),
    ("ORO_CONCRECES_13", "El Rol de avalúo fiscal debe coincidir EXACTAMENTE entre la tasación y el estudio de títulos. Cualquier diferencia bloquea el avance con alerta crítica."),
    ("ORO_CONCRECES_14", "La dirección de la propiedad debe coincidir EXACTAMENTE entre la tasación y el estudio de títulos. Cualquier diferencia bloquea el avance con alerta crítica. NO se puede enviar a ConCreces hasta que todo coincida. Estas validaciones son IRRENUNCIABLES y ninguna actualización puede omitirlas."),
    ("ORO_CONCRECES_15", "VALIDACIÓN DE INGRESO IRRENUNCIABLE: todo documento recibido (correo o manual) debe contrastar RUT del cliente principal, RUT del codeudor, Rol de avalúo fiscal y dirección de la propiedad contra la ficha del cliente ANTES de asociarse. Cualquier no coincidencia exacta envía el documento a CUARENTENA con alerta crítica y NO se asocia hasta que Victoria lo corrija. Una carga forzada manual exige PIN de seguridad de 4 dígitos y queda registrada. Sin excepción."),
]


async def seed_reglas_coincidencia():
    for clave, texto in REGLAS_ORO_COINCIDENCIA:
        await db.dashai_eventos.update_one({"norma_clave": clave}, {"$set": {
            "motivo": "normativa", "etiqueta": "Regla de Oro ConCreces", "norma_clave": clave,
            "patron": f"REGLA DE ORO CONCRECES — {texto}", "inviolable": True,
            "nivel_calibracion": 100, "fecha": _now()},
            "$setOnInsert": {"id": str(uuid.uuid4())}}, upsert=True)
    logging.info("🥇 Reglas de Oro ConCreces 11-14 (coincidencias) sembradas")


# ══════════ CLASIFICACIÓN Y EXTRACCIÓN ══════════
TIPOS_DOC = ("tasacion", "titulos", "carpeta_credito", "simulacion", "escritura",
             "liquidacion", "cert_matrimonio", "certificado_avaluo", "cedula", "otro")
DOCS_REQUERIDOS = ("tasacion", "titulos", "carpeta_credito", "simulacion")
ETIQUETAS = {"tasacion": "Informe de Tasación", "titulos": "Estudio de Títulos",
             "carpeta_credito": "Carpeta de Crédito", "simulacion": "Simulación",
             "escritura": "Escritura / Borrador", "liquidacion": "Liquidaciones de Sueldo",
             "cert_matrimonio": "Certificado de Matrimonio",
             "certificado_avaluo": "Certificado de Avalúo Fiscal",
             "cedula": "Cédula de Identidad", "otro": "Otro documento"}
VIGENCIA_DIAS = {"tasacion": 90, "titulos": 90, "simulacion": 60, "carpeta_credito": 180,
                 "escritura": 365, "liquidacion": 90, "cert_matrimonio": 90, "certificado_avaluo": 90}
FIRMA_OBLIGATORIA = ("titulos", "carpeta_credito", "escritura")
_KW_SET = re.compile(r"set\s+(de\s+)?cr[eé]dito|tasaci[oó]n|estudio\s+de\s+t[ií]tulos|carpeta\s+(de\s+)?cr[eé]dito|simulaci[oó]n|escritura", re.I)


def _clasificar_tipo(filename, texto=""):
    base = f"{filename} {texto[:800]}".lower()
    if re.search(r"tasaci", base):
        return "tasacion"
    if re.search(r"titulo|estudio\s+de\s+t", base):
        return "titulos"
    if re.search(r"matrimonio", base):
        return "cert_matrimonio"
    if re.search(r"c[eé]dula|carne|identidad", base):
        return "cedula"
    if re.search(r"liquidaci", base):
        return "liquidacion"
    if re.search(r"certificado\s+de\s+aval|aval[uú]o\s+fiscal", base):
        return "certificado_avaluo"
    if re.search(r"escritura|borrador", base):
        return "escritura"
    if re.search(r"simulaci", base):
        return "simulacion"
    if re.search(r"carpeta|set|solicitud\s+de\s+cr", base):
        return "carpeta_credito"
    return "otro"


def _norm_rut(r):
    r = re.sub(r"[.\s]", "", str(r or "")).upper().strip()
    return r if re.match(r"^\d{7,8}-?[\dK]$", r.replace("-", "") + "") or "-" in r else r


def _norm_dir(d):
    d = unicodedata.normalize("NFD", str(d or "").lower())
    d = "".join(c for c in d if unicodedata.category(c) != "Mn")
    d = re.sub(r"[.,#°º]", " ", d)
    d = re.sub(r"\b(n|nro|numero|num)\b", "", d)
    return re.sub(r"\s+", " ", d).strip()


def _norm_rol(r):
    return re.sub(r"[.\s]", "", str(r or "")).strip()


def _regex_fallback(texto):
    ruts = re.findall(r"\b(\d{1,2}\.?\d{3}\.?\d{3}\s?-\s?[\dkK])\b", texto or "")
    rol = ""
    m = re.search(r"rol(?:\s+de\s+aval[uú]o)?(?:\s+fiscal)?\s*(?:n[°º:.\s]*)?[:\s]*([\d]{1,6}\s*-\s*[\dkK\d]{1,5})", texto or "", re.I)
    if m:
        rol = m.group(1)
    firma = bool(re.search(r"\bfirma(do|s)?\b|firma\s+electr[oó]nica|suscrito|p\.p\.|rubrica", texto or "", re.I))
    fecha = ""
    m = re.search(r"\b(\d{1,2})[/\-](\d{1,2})[/\-](20\d{2})\b", texto or "")
    if m:
        fecha = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    else:
        m = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", texto or "")
        if m:
            fecha = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return {"rut_titular": ruts[0] if ruts else "", "rut_codeudor": ruts[1] if len(ruts) > 1 else "",
            "rol_avaluo": rol, "direccion_propiedad": "", "fecha_documento": fecha,
            "firmado": firma, "nombre_cliente": ""}


async def _extraer_campos(texto, filename=""):
    """Extracción con IA (JSON) + fallback por regex."""
    base = _regex_fallback(texto)
    key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not key or len((texto or "").strip()) < 40:
        return base
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(api_key=key, session_id=f"vict-{uuid.uuid4()}",
                       system_message=("Extraes datos de documentos hipotecarios chilenos. Respondes SOLO un JSON "
                                       "con: nombre_cliente, rut_titular, rut_codeudor (vacío si no hay), rol_avaluo "
                                       "(rol de avalúo fiscal de la propiedad, ej 1234-56), direccion_propiedad, "
                                       "fecha_documento (YYYY-MM-DD, fecha de emisión), firmado (true/false si el "
                                       "documento muestra firma o mención de firma). Vacío si un dato no aparece.")
                       ).with_model("openai", "gpt-5.4-mini")
        resp = await asyncio.wait_for(chat.send_message(UserMessage(
            text=f"Documento: {filename}\n\n{(texto or '')[:5500]}")), timeout=60)
        m = re.search(r"\{.*\}", str(resp), re.S)
        if m:
            data = json.loads(m.group(0))
            out = dict(base)
            for k in ("nombre_cliente", "rut_titular", "rut_codeudor", "rol_avaluo",
                      "direccion_propiedad", "fecha_documento"):
                v = str(data.get(k) or "").strip()
                if v and v.lower() not in ("null", "none", "n/a"):
                    out[k] = v
            if isinstance(data.get("firmado"), bool):
                out["firmado"] = data["firmado"] or base["firmado"]
            return out
    except Exception as e:
        logging.warning(f"victoria extraccion IA: {e}")
    return base


# ══════════ BÓVEDA ══════════
async def _guardar_doc(cliente_id, filename, raw, tipo, origen, subido_por="", datos=None):
    import ocr_service
    if datos is None:
        texto, _met = await asyncio.to_thread(ocr_service.extraer_texto, raw, filename)
        datos = await _extraer_campos(texto, filename)
        datos["_legible"] = len((texto or "").strip()) >= 50
    carpeta = BOVEDA_DIR / (cliente_id or "_sin_clasificar")
    carpeta.mkdir(parents=True, exist_ok=True)
    nombre = re.sub(r"[^\w.\-]", "_", filename)[:120] or "documento.pdf"
    ruta = carpeta / f"{uuid.uuid4().hex[:8]}_{nombre}"
    ruta.write_bytes(raw)
    doc = {"id": str(uuid.uuid4()), "cliente_id": cliente_id, "tipo": tipo,
           "archivo": filename, "ruta": str(ruta), "origen": origen,
           "subido_por": subido_por, "recibido": _now(), "datos": datos}
    await db.victoria_docs.insert_one(dict(doc))
    return doc


async def _get_cliente(cid):
    c = await db.victoria_clientes.find_one({"id": cid}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Cliente no encontrado en la bóveda de Daniela")
    return c


async def _buscar_o_crear_cliente(rut, nombre, origen="correo"):
    rutn = _norm_rut(rut)
    if rutn:
        c = await db.victoria_clientes.find_one({"rut_norm": rutn}, {"_id": 0})
        if c:
            return c
    if not rutn and nombre:
        c = await db.victoria_clientes.find_one(
            {"nombre": {"$regex": re.escape(nombre[:25]), "$options": "i"}}, {"_id": 0})
        if c:
            return c
    if not rutn and not nombre:
        return None
    c = {"id": str(uuid.uuid4()), "nombre": (nombre or f"CLIENTE {rutn}").strip().upper()[:80],
         "rut": rut or "", "rut_norm": rutn, "rut_codeudor": "", "origen": origen,
         "creado": _now(), "formularios": {}, "formularios_confirmados": False, "despachado": False}
    await db.victoria_clientes.insert_one(dict(c))
    return c


async def _aviso(tipo, detalle, cliente_id=None):
    await db.victoria_avisos.insert_one({"id": str(uuid.uuid4()), "tipo": tipo, "detalle": detalle,
                                         "cliente_id": cliente_id, "fecha": _now(), "leido": False})


# ══════════ VALIDACIÓN DE INGRESO IRRENUNCIABLE (Regla de Oro 15) ══════════
CAMPOS_VALIDACION_INGRESO = [
    ("rut_titular", "RUT del cliente principal", _norm_rut),
    ("rut_codeudor", "RUT del codeudor", _norm_rut),
    ("rol_avaluo", "Rol de avalúo fiscal", _norm_rol),
    ("direccion_propiedad", "Dirección de la propiedad", _norm_dir),
]


def _validar_ingreso(cliente, docs_previos, datos):
    """Contrasta el documento entrante contra la ficha del cliente. ok True/False/None."""
    esperados = _formularios_auto(cliente, docs_previos)
    out = []
    for campo, etiqueta, norm in CAMPOS_VALIDACION_INGRESO:
        esp = str(esperados.get(campo) or "").strip()
        det = str((datos or {}).get(campo) or "").strip()
        ok = None if (not esp or not det) else (norm(esp) == norm(det))
        out.append({"campo": campo, "etiqueta": etiqueta, "ok": ok, "esperado": esp, "detectado": det})
    return out


async def _docs_validos(cid):
    docs = await db.victoria_docs.find({"cliente_id": cid}, {"_id": 0, "ruta": 0}).to_list(100)
    return [d for d in docs if (d.get("revision") or {}).get("decision") != "rechazado"]


async def _evento(archivo, tipo, resultado, cliente=None, validaciones=None, origen="correo"):
    await db.victoria_eventos.insert_one({
        "id": str(uuid.uuid4()), "fecha": _now(), "archivo": archivo, "tipo": tipo,
        "tipo_etiqueta": ETIQUETAS.get(tipo, tipo), "resultado": resultado,
        "cliente": (cliente or {}).get("nombre", ""), "cliente_id": (cliente or {}).get("id"),
        "validaciones": validaciones or [], "origen": origen})


async def _verificar_pin(sub, pin):
    u_doc = await db.users.find_one({"codigo": sub}) or {}
    h = u_doc.get("pin_seguridad_hash")
    if not h:
        raise HTTPException(status_code=403, detail="Aún no tiene PIN de seguridad: créelo primero (4 dígitos)")
    import bcrypt as _b
    if not pin or not _b.checkpw(str(pin).encode(), h.encode()):
        raise HTTPException(status_code=403, detail="PIN de seguridad incorrecto")


# ══════════ AUDITORÍA AUTOMÁTICA (manual ConCreces) ══════════
def _vigente(doc):
    f = (doc.get("datos") or {}).get("fecha_documento") or ""
    dias = VIGENCIA_DIAS.get(doc.get("tipo"), 365)
    if not f:
        return None, f"sin fecha detectada (vigencia exigida: {dias} días)"
    try:
        fd = datetime.fromisoformat(f[:10]).replace(tzinfo=timezone.utc)
    except ValueError:
        return None, f"fecha ilegible «{f}»"
    edad = (datetime.now(timezone.utc) - fd).days
    if fd > datetime.now(timezone.utc) + timedelta(days=1):
        return False, f"fecha futura {f[:10]} — inválida"
    return edad <= dias, f"emitido {f[:10]} ({edad} días; máx {dias})"


def _coincidencias(docs):
    """Reglas de Oro 11-14: devuelve validaciones con detalle exacto de qué no coincide."""
    por_tipo = {}
    for d in docs:
        por_tipo.setdefault(d["tipo"], d)
    res = []

    def cruce(regla, campo, norm, solo_tipos=None):
        vistos = {}
        for d in docs:
            if solo_tipos and d["tipo"] not in solo_tipos:
                continue
            v = (d.get("datos") or {}).get(campo) or ""
            if not str(v).strip():
                continue
            vistos.setdefault(norm(v), []).append((ETIQUETAS.get(d["tipo"], d["tipo"]), d["archivo"], str(v).strip()))
        if len(vistos) == 0:
            return {"regla": regla, "ok": None, "detalle": "dato aún no detectado en ningún documento", "docs": []}
        if len(vistos) == 1:
            docs_l = next(iter(vistos.values()))
            return {"regla": regla, "ok": True,
                    "detalle": f"coincide en {len(docs_l)} documento(s): «{docs_l[0][2]}»",
                    "docs": [f"{t} ({a})" for t, a, _v in docs_l]}
        det = " ≠ ".join(f"«{ls[0][2]}» en {', '.join(t for t, _a, _v in ls)}" for ls in vistos.values())
        return {"regla": regla, "ok": False, "detalle": f"NO COINCIDE: {det}",
                "docs": [f"{t} ({a})" for ls in vistos.values() for t, a, _v in ls]}

    res.append(cruce("Oro 11 · RUT cliente principal idéntico en todos los documentos", "rut_titular", _norm_rut))
    res.append(cruce("Oro 12 · RUT codeudor idéntico en todos los documentos donde aparece", "rut_codeudor", _norm_rut))
    ambos = "tasacion" in por_tipo and "titulos" in por_tipo
    r13 = cruce("Oro 13 · Rol de avalúo fiscal idéntico entre Tasación y Estudio de Títulos", "rol_avaluo", _norm_rol, ("tasacion", "titulos"))
    r14 = cruce("Oro 14 · Dirección de la propiedad idéntica entre Tasación y Estudio de Títulos", "direccion_propiedad", _norm_dir, ("tasacion", "titulos"))
    if not ambos:
        falt = [ETIQUETAS[t] for t in ("tasacion", "titulos") if t not in por_tipo]
        for r in (r13, r14):
            if r["ok"] is not False:
                r["ok"] = None
                r["detalle"] = f"pendiente: falta {', '.join(falt)}"
    res.extend([r13, r14])
    return res


async def auditar_cliente(cid):
    docs = await db.victoria_docs.find({"cliente_id": cid}, {"_id": 0}).to_list(100)
    docs = [d for d in docs if (d.get("revision") or {}).get("decision") != "rechazado"]
    alertas = []
    presentes = {d["tipo"] for d in docs}
    for t in DOCS_REQUERIDOS:
        if t not in presentes:
            alertas.append({"nivel": "critica", "doc": ETIQUETAS[t],
                            "detalle": f"FALTA el documento requerido: {ETIQUETAS[t]}"})
    for d in docs:
        datos = d.get("datos") or {}
        if datos.get("_legible") is False:
            alertas.append({"nivel": "critica", "doc": d["archivo"],
                            "detalle": "Documento ilegible: no se pudo extraer texto (formato inválido o escaneo deficiente)"})
        ok, det = _vigente(d)
        if ok is False:
            alertas.append({"nivel": "critica", "doc": d["archivo"], "detalle": f"Fuera de plazo: {det}"})
        elif ok is None:
            alertas.append({"nivel": "alerta", "doc": d["archivo"], "detalle": f"Revisar fecha: {det}"})
        if d["tipo"] in FIRMA_OBLIGATORIA and not datos.get("firmado"):
            alertas.append({"nivel": "alerta", "doc": d["archivo"],
                            "detalle": f"No se detectó firma en {ETIQUETAS[d['tipo']]} — verificar que esté firmado donde corresponde"})
    coincidencias = _coincidencias(docs)
    criticas_coin = [c for c in coincidencias if c["ok"] is False]
    for c in criticas_coin:
        alertas.append({"nivel": "critica", "doc": "COINCIDENCIA", "detalle": f"{c['regla']}: {c['detalle']}"})
    bloqueado = any(a["nivel"] == "critica" for a in alertas) or any(c["ok"] is not True for c in coincidencias)
    resultado = {"alertas": alertas, "coincidencias": coincidencias, "bloqueado": bloqueado,
                 "auditado_en": _now(), "n_docs": len(docs)}
    await db.victoria_clientes.update_one({"id": cid}, {"$set": {"auditoria": resultado}})
    return resultado


def _formularios_auto(cliente, docs):
    """Rellena los formularios con los datos ya guardados en la bóveda."""
    mejor = {}
    orden = {"carpeta_credito": 0, "titulos": 1, "tasacion": 2, "simulacion": 3, "escritura": 4, "otro": 9}
    for d in sorted(docs, key=lambda x: orden.get(x["tipo"], 9)):
        for k in ("nombre_cliente", "rut_titular", "rut_codeudor", "rol_avaluo", "direccion_propiedad"):
            v = str((d.get("datos") or {}).get(k) or "").strip()
            if v and not mejor.get(k):
                mejor[k] = v
    auto = {"nombre_cliente": mejor.get("nombre_cliente") or cliente.get("nombre", ""),
            "rut_titular": mejor.get("rut_titular") or cliente.get("rut", ""),
            "rut_codeudor": mejor.get("rut_codeudor") or cliente.get("rut_codeudor", ""),
            "rol_avaluo": mejor.get("rol_avaluo", ""),
            "direccion_propiedad": mejor.get("direccion_propiedad", "")}
    return {**auto, **{k: v for k, v in (cliente.get("formularios") or {}).items() if str(v).strip()}}


def _paso_siguiente(cliente, docs, aud):
    if not docs:
        return {"n": 1, "titulo": "Recibir documentos", "detalle": "Aún no hay documentos: espera el correo o súbelos manualmente"}
    faltan = [ETIQUETAS[t] for t in DOCS_REQUERIDOS if t not in {d["tipo"] for d in docs}]
    if faltan:
        return {"n": 1, "titulo": "Completar set de crédito", "detalle": f"Faltan: {', '.join(faltan)}"}
    if not aud:
        return {"n": 2, "titulo": "Auditar documentos", "detalle": "Ejecuta la auditoría automática"}
    crit = [a for a in aud.get("alertas", []) if a["nivel"] == "critica"]
    if any(c["ok"] is False for c in aud.get("coincidencias", [])):
        return {"n": 3, "titulo": "Resolver coincidencias (BLOQUEANTE)", "detalle": "Hay datos que NO coinciden entre documentos — corrígelos y vuelve a auditar"}
    if crit:
        return {"n": 2, "titulo": "Corregir alertas críticas", "detalle": crit[0]["detalle"][:100]}
    if any(c["ok"] is None for c in aud.get("coincidencias", [])):
        return {"n": 3, "titulo": "Completar datos de coincidencia", "detalle": "Faltan datos por detectar (rol/dirección/RUT) — revisa los documentos"}
    if not cliente.get("formularios_confirmados"):
        return {"n": 4, "titulo": "Revisar y confirmar formularios", "detalle": "Los formularios ya están auto-rellenados: revisa, corrige lo alertado y confirma"}
    if not cliente.get("despachado"):
        return {"n": 5, "titulo": "Generar documento de envío y despachar", "detalle": "Todo listo: genera el documento, revísalo y despacha a ConCreces con un clic"}
    return None


# ══════════ MONITOREO DEL CORREO DE VICTORIA ══════════
async def procesar_correo_victoria(limit=25):
    import email_service as mail
    import ocr_service
    cfg = await db.config.find_one({"_key": "fuentes_imap_victoria"}) or {}
    fuentes = [cfg.get("correo_principal", "")] + [a.get("email", "") for a in cfg.get("aliados", [])]
    fuentes = [f.lower() for f in fuentes if f]
    correos = await asyncio.to_thread(mail.fetch_pdf_attachments, None, limit)
    procesados, nuevos_docs = 0, 0
    for c in correos:
        remitente = (c.get("from") or "").lower()
        texto_corto = f"{c.get('subject','')} {c.get('body','')[:400]}"
        es_fuente = any(f in remitente for f in fuentes)
        es_set = bool(_KW_SET.search(texto_corto))
        if not (es_fuente or es_set) or not c.get("pdfs"):
            continue
        mid = hashlib.sha256(f"{c.get('from')}|{c.get('subject')}|{c.get('date')}".encode()).hexdigest()
        if await db.victoria_mail_log.find_one({"mid": mid}):
            continue
        await db.victoria_mail_log.insert_one({"mid": mid, "subject": c.get("subject", ""),
                                               "from": c.get("from", ""), "fecha": c.get("date", ""),
                                               "procesado_en": _now(), "adjuntos": len(c["pdfs"])})
        procesados += 1
        for pdf in c["pdfs"]:
            raw = pdf.get("content_bytes") or b""
            if not raw:
                continue
            try:
                texto, _met = await asyncio.to_thread(ocr_service.extraer_texto, raw, pdf["filename"])
                datos = await _extraer_campos(texto, pdf["filename"])
                datos["_legible"] = len((texto or "").strip()) >= 50
                tipo = _clasificar_tipo(pdf["filename"], texto)
                cliente = await _buscar_o_crear_cliente(datos.get("rut_titular"),
                                                        datos.get("nombre_cliente") or "", "correo")
                if not cliente:
                    await _guardar_doc(None, pdf["filename"], raw, tipo, "correo", datos=datos)
                    await _aviso("sin_clasificar",
                                 f"No pude identificar al cliente del documento «{pdf['filename']}» "
                                 f"(correo: {c.get('subject','')[:60]}). Súbelo o asígnalo manualmente.")
                    await _evento(pdf["filename"], tipo, "sin_cliente")
                    continue
                # Regla de Oro 15: validación de ingreso irrenunciable
                validaciones = _validar_ingreso(cliente, await _docs_validos(cliente["id"]), datos)
                fallas = [v for v in validaciones if v["ok"] is False]
                if fallas:
                    doc = await _guardar_doc(None, pdf["filename"], raw, tipo, "correo", datos=datos)
                    await db.victoria_docs.update_one({"id": doc["id"]}, {"$set": {
                        "cuarentena": True, "candidato_cliente_id": cliente["id"],
                        "candidato_nombre": cliente["nombre"], "validaciones_ingreso": validaciones}})
                    det_f = " · ".join(f"{v['etiqueta']}: ficha «{v['esperado']}» ≠ documento «{v['detectado']}»" for v in fallas)
                    await _aviso("cuarentena",
                                 f"ALERTA CRÍTICA: «{pdf['filename']}» NO se asoció a {cliente['nombre']} — {det_f}. "
                                 f"Resuélvalo en el panel de Cuarentena.", cliente["id"])
                    await _evento(pdf["filename"], tipo, "cuarentena", cliente, validaciones)
                    continue
                doc = await _guardar_doc(cliente["id"], pdf["filename"], raw, tipo, "correo", datos=datos)
                await db.victoria_docs.update_one({"id": doc["id"]}, {"$set": {"validaciones_ingreso": validaciones}})
                nuevos_docs += 1
                await auditar_cliente(cliente["id"])
                await _evento(pdf["filename"], tipo, "asociado", cliente, validaciones)
                await asignar_a_ventas_si_corresponde(cliente["id"], f"{texto_corto} {texto[:600]}")
            except Exception as e:
                logging.warning(f"victoria adjunto {pdf.get('filename')}: {e}")
                await _aviso("error_adjunto", f"No pude procesar «{pdf.get('filename')}» — súbelo manualmente. ({str(e)[:80]})")
    return {"correos_procesados": procesados, "documentos_nuevos": nuevos_docs, "fuentes": fuentes}


async def victoria_mail_loop():
    await asyncio.sleep(90)
    while True:
        try:
            await procesar_correo_victoria()
        except Exception as e:
            logging.warning(f"victoria_mail_loop: {e}")
        await asyncio.sleep(600)


# ══════════ ENDPOINTS ══════════
@vict.get("/panel")
async def panel(request: Request):
    u = _exigir(request)
    es_admin = u.get("rol") in ("admin", "maestro")
    # 🔒 Daniela/Victoria: SOLO clientes en etapa de escrituración subidos MANUALMENTE
    # por el Administrador. Nada del flujo automático del Administrador es visible.
    filtro = {} if es_admin else {"origen": "manual"}
    clientes = await db.victoria_clientes.find(filtro, {"_id": 0}).sort("creado", -1).to_list(200)
    out = []
    for c in clientes:
        docs = await db.victoria_docs.find({"cliente_id": c["id"]}, {"_id": 0, "tipo": 1}).to_list(50)
        if not es_admin and "escritura" not in {d["tipo"] for d in docs}:
            continue
        aud = c.get("auditoria")
        out.append({"id": c["id"], "nombre": c["nombre"], "rut": c.get("rut", ""),
                    "n_docs": len(docs), "despachado": c.get("despachado", False),
                    "bloqueado": (aud or {}).get("bloqueado", True),
                    "siguiente": _paso_siguiente(c, docs, aud)})
    avisos = await db.victoria_avisos.find({"leido": False}, {"_id": 0}).sort("fecha", -1).to_list(30)
    sin_clasificar = await db.victoria_docs.find({"cliente_id": None, "cuarentena": {"$ne": True}, "descartado": {"$ne": True}}, {"_id": 0, "ruta": 0}).sort("recibido", -1).to_list(30)
    cfg = await db.config.find_one({"_key": "fuentes_imap_victoria"}, {"_id": 0}) or {}
    return {"clientes": out, "avisos": avisos, "sin_clasificar": sin_clasificar,
            "correo_monitoreado": cfg.get("correo_principal", ""),
            "aliados": cfg.get("aliados", []), "tipos": ETIQUETAS,
            "docs_requeridos": [ETIQUETAS[t] for t in DOCS_REQUERIDOS]}


@vict.post("/clientes")
async def crear_cliente(payload: dict, request: Request):
    _exigir(request)
    nombre = (payload.get("nombre") or "").strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="Nombre obligatorio")
    c = {"id": str(uuid.uuid4()), "nombre": nombre.upper()[:80], "rut": (payload.get("rut") or "").strip(),
         "rut_norm": _norm_rut(payload.get("rut")), "rut_codeudor": (payload.get("rut_codeudor") or "").strip(),
         "origen": "manual", "creado": _now(), "formularios": {}, "formularios_confirmados": False,
         "despachado": False}
    await db.victoria_clientes.insert_one(dict(c))
    c.pop("_id", None)
    return {"ok": True, "cliente": c}


@vict.get("/clientes/{cid}")
async def detalle(cid: str, request: Request):
    _exigir(request)
    c = await _get_cliente(cid)
    docs = await db.victoria_docs.find({"cliente_id": cid}, {"_id": 0, "ruta": 0}).sort("recibido", -1).to_list(100)
    docs_ok = [d for d in docs if (d.get("revision") or {}).get("decision") != "rechazado"]
    aud = c.get("auditoria")
    concreces = await db.concreces_estado.find_one({"victoria_cliente_id": cid}, {"_id": 0, "snapshot": 0})
    auto = _formularios_auto(c, docs_ok)
    rut = c.get("rut") or auto.get("rut_titular")
    if rut:
        try:
            import expediente_identidad as _ei
            filtro = _ei.filtro_busqueda(rut)
            doc = await db.adn_clientes_360.find_one(filtro, {"_id": 0}) if filtro else None
            extra = {}
            if doc:
                exp = dict(doc.get("expediente_360") or {})
                extra = _ei.campos_victoria(exp)
            else:
                ff = _ei.filtro_folder_por_clave(rut)
                fd = await db.folders.find_one(ff) if ff else None
                if fd:
                    extra = _ei.campos_victoria(_ei.construir_expediente(fd))
            auto = _ei.fusionar_vacios(auto, extra)
        except Exception:
            pass
    return {"cliente": c, "docs": docs, "auditoria": aud,
            "formularios_auto": auto,
            "siguiente": _paso_siguiente(c, docs_ok, aud), "tipos": ETIQUETAS,
            "concreces": concreces,
            "requeridos": {t: ETIQUETAS[t] for t in DOCS_REQUERIDOS}}


@vict.post("/clientes/{cid}/subir")
async def subir(cid: str, request: Request, file: UploadFile = File(...), tipo: str = Form(""), pin: str = Form("")):
    u = _exigir(request)
    c = await _get_cliente(cid)
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Archivo vacío")
    tipo = tipo if tipo in TIPOS_DOC else ""
    import ocr_service
    texto, _met = await asyncio.to_thread(ocr_service.extraer_texto, raw, file.filename or "doc.pdf")
    datos = await _extraer_campos(texto, file.filename or "")
    datos["_legible"] = len((texto or "").strip()) >= 50
    tipo_final = tipo or _clasificar_tipo(file.filename or "", texto)
    # Regla de Oro 15: la validación de ingreso aplica también a la carga manual
    validaciones = _validar_ingreso(c, await _docs_validos(cid), datos)
    fallas = [v for v in validaciones if v["ok"] is False]
    forzado = False
    if fallas:
        if not pin:
            u_doc = await db.users.find_one({"codigo": u.get("sub", "")}) or {}
            raise HTTPException(status_code=409, detail={
                "codigo": "VALIDACION_BLOQUEADA",
                "mensaje": "Los datos del documento NO coinciden exactamente con la ficha del cliente (Regla de Oro 15)",
                "fallas": [{"etiqueta": v["etiqueta"], "esperado": v["esperado"], "detectado": v["detectado"]} for v in fallas],
                "pin_configurado": bool(u_doc.get("pin_seguridad_hash"))})
        await _verificar_pin(u.get("sub", ""), pin)
        forzado = True
    doc = await _guardar_doc(cid, file.filename or "documento.pdf", raw, tipo_final, "manual",
                             u.get("sub", ""), datos=datos)
    sets = {"validaciones_ingreso": validaciones}
    if forzado:
        sets["forzado_manual"] = {"por": u.get("sub", ""), "fecha": _now()}
        await _aviso("forzado_manual",
                     f"REGISTRO: {u.get('sub','')} forzó con PIN la carga manual de «{doc['archivo']}» "
                     f"en {c['nombre']} pese a validación de ingreso no coincidente.", cid)
    await db.victoria_docs.update_one({"id": doc["id"]}, {"$set": sets})
    aud = await auditar_cliente(cid)
    await _evento(doc["archivo"], tipo_final, "manual_forzado" if forzado else "manual", c, validaciones, origen="manual")
    return {"ok": True, "doc": {k: v for k, v in doc.items() if k != "ruta"}, "auditoria": aud, "forzado": forzado}


@vict.post("/clientes/{cid}/auditar")
async def auditar(cid: str, request: Request):
    _exigir(request)
    await _get_cliente(cid)
    import constitucion as _const
    await _const.consultar_cerebro(db, "validacion_cruzada_daniela",
                                   texto_ia=f"Validación cruzada RUT-Rol-Dirección del cliente {cid} (módulo Daniela Galindo)",
                                   modulo="victoria_independiente.py (auditar)")
    return {"ok": True, "auditoria": await auditar_cliente(cid)}


@vict.put("/clientes/{cid}/formularios")
async def formularios(cid: str, payload: dict, request: Request):
    u = _exigir(request)
    await _get_cliente(cid)
    sets = {"formularios": payload.get("datos") or {},
            "formularios_confirmados": bool(payload.get("confirmado")),
            "formularios_actualizado": _now(), "formularios_por": u.get("sub", "")}
    await db.victoria_clientes.update_one({"id": cid}, {"$set": sets})
    return {"ok": True, "confirmados": sets["formularios_confirmados"]}


@vict.get("/clientes/{cid}/documento-envio")
async def documento_envio(cid: str, request: Request):
    _exigir(request)
    c = await _get_cliente(cid)
    docs = await db.victoria_docs.find({"cliente_id": cid}, {"_id": 0, "ruta": 0}).to_list(100)
    aud = c.get("auditoria") or await auditar_cliente(cid)
    forms = _formularios_auto(c, docs)

    def _traz(campo, valor):
        v = str(valor or "").strip()
        if not v:
            return "—"
        return f"<span class='traz' data-campo='{campo}' title='Clic: ver el documento de origen de este dato'>{v}</span>"
    filas_docs = "".join(
        f"<tr><td>{ETIQUETAS.get(d['tipo'], d['tipo'])}</td><td>{d['archivo']}</td>"
        f"<td>{(d.get('datos') or {}).get('fecha_documento') or '—'}</td>"
        f"<td>{'✅' if (d.get('datos') or {}).get('firmado') else '—'}</td><td>{d['origen']}</td></tr>" for d in docs)
    filas_coin = "".join(
        f"<tr><td>{x['regla']}</td><td>{'✅ COINCIDE' if x['ok'] else ('⏳ PENDIENTE' if x['ok'] is None else '🚨 NO COINCIDE')}</td>"
        f"<td>{x['detalle']}</td></tr>" for x in aud.get("coincidencias", []))
    filas_alertas = "".join(
        f"<tr><td>{'🚨' if a['nivel'] == 'critica' else '⚠️'}</td><td>{a['doc']}</td><td>{a['detalle']}</td></tr>"
        for a in aud.get("alertas", [])) or "<tr><td colspan=3>Sin alertas</td></tr>"
    filas_forms = "".join(
        f"<tr><td>{k.replace('_', ' ').title()}</td><td>{_traz(k, v) if k in CAMPOS_TRAZABLES else (v or '—')}</td></tr>"
        for k, v in forms.items())
    tabla = "border-collapse:collapse;width:100%;font-size:13px"
    html = (f"<html><body style='font-family:Georgia,serif;color:#111;max-width:840px;margin:auto;padding:18px'>"
            f"<h1 style='color:#8a6d1a;border-bottom:3px solid #8a6d1a'>CENTRAL MUTUOS — Documento de Envío a ConCreces</h1>"
            f"<p><b>Cliente:</b> {_traz('nombre_cliente', c['nombre'])} · <b>RUT:</b> {_traz('rut_titular', forms.get('rut_titular') or c.get('rut'))} · <b>Fecha:</b> {_now()[:16].replace('T', ' ')} UTC</p>"
            f"<h3>1. Documentos del set de crédito ({len(docs)})</h3>"
            f"<table border=1 cellpadding=5 style='{tabla}'><tr><th>Tipo</th><th>Archivo</th><th>Fecha doc.</th><th>Firma</th><th>Origen</th></tr>{filas_docs}</table>"
            f"<h3>2. Validación de coincidencias — Reglas de Oro ConCreces 11-14 (IRRENUNCIABLES)</h3>"
            f"<table border=1 cellpadding=5 style='{tabla}'>{filas_coin}</table>"
            f"<h3>3. Alertas de auditoría</h3><table border=1 cellpadding=5 style='{tabla}'>{filas_alertas}</table>"
            f"<h3>4. Formularios (auto-rellenados y confirmados por Victoria)</h3>"
            f"<table border=1 cellpadding=5 style='{tabla}'>{filas_forms}</table>"
            f"<p style='background:#fdf6e3;border:1px solid #8a6d1a;padding:10px;font-weight:bold'>"
            f"{'✅ APTO PARA ENVÍO: todas las coincidencias validadas.' if not aud.get('bloqueado') else '⛔ BLOQUEADO: no se puede enviar a ConCreces hasta que todo coincida y no haya alertas críticas.'}"
            f" Documento generado para revisión final de Daniela Galindo.</p>"
            f"<style>.traz{{cursor:pointer;border-bottom:1.5px dashed #b08d2a;transition:background .2s}}"
            f".traz:hover{{background:#f5e9c8;border-bottom-style:solid}}"
            f".traz:hover::after{{content:' 🔍';font-size:11px}}</style>"
            f"<script>document.addEventListener('click',function(e){{var s=e.target.closest('.traz');"
            f"if(s)parent.postMessage({{tipo:'dato-trazable',campo:s.getAttribute('data-campo'),valor:s.textContent}},'*');}});</script>"
            f"</body></html>")
    listo = (not aud.get("bloqueado")) and c.get("formularios_confirmados")
    return {"html": html, "bloqueado": aud.get("bloqueado", True),
            "formularios_confirmados": c.get("formularios_confirmados", False), "listo": listo}


@vict.post("/clientes/{cid}/despachar")
async def despachar(cid: str, payload: dict, request: Request):
    u = _exigir(request)
    if not payload.get("confirmado"):
        raise HTTPException(status_code=400, detail="Victoria debe revisar el documento de envío y confirmar antes de despachar")
    c = await _get_cliente(cid)
    aud = await auditar_cliente(cid)
    if aud.get("bloqueado"):
        malas = [x["detalle"] for x in aud.get("coincidencias", []) if x["ok"] is not True]
        crit = [a["detalle"] for a in aud.get("alertas", []) if a["nivel"] == "critica"]
        raise HTTPException(status_code=403, detail="REGLAS DE ORO CONCRECES (11-14): envío BLOQUEADO — " + " · ".join((malas + crit)[:4]))
    if not c.get("formularios_confirmados"):
        raise HTTPException(status_code=403, detail="Los formularios deben ser revisados y confirmados por Victoria antes de despachar")
    import constitucion as _const
    await _const.consultar_cerebro(db, "despacho_concreces",
                                   texto_ia=f"Despacho del set de crédito de {c.get('nombre')} a ConCreces",
                                   modulo="victoria_independiente.py (despachar)")
    docs = await db.victoria_docs.find({"cliente_id": cid}, {"_id": 0, "ruta": 0}).to_list(100)
    await db.concreces_estado.update_one({"victoria_cliente_id": cid}, {"$set": {
        "victoria_cliente_id": cid, "cliente": c["nombre"], "rut": c.get("rut", ""),
        "estado": "enviado", "origen": "victoria_independiente", "enviado_en": _now(),
        "enviado_por": u.get("sub", ""), "n_documentos": len(docs),
        "documentos": [d["archivo"] for d in docs],
        "snapshot": {"formularios": c.get("formularios"), "auditoria": aud}}}, upsert=True)
    await db.victoria_clientes.update_one({"id": cid}, {"$set": {
        "despachado": True, "despachado_en": _now(), "despachado_por": u.get("sub", "")}})
    return {"ok": True, "mensaje": f"Set de crédito de {c['nombre']} despachado a ConCreces "
                                   f"({len(docs)} documentos). Coincidencias validadas al 100%."}


@vict.post("/procesar-correo")
async def procesar_correo(request: Request):
    _exigir(request)
    asyncio.create_task(procesar_correo_victoria())
    return {"ok": True, "en_segundo_plano": True,
            "mensaje": "Revisión del correo iniciada en segundo plano: los documentos nuevos aparecerán solos en la bóveda al terminar"}


@vict.post("/sin-clasificar/{did}/asignar")
async def asignar(did: str, payload: dict, request: Request):
    _exigir(request)
    cid = payload.get("cliente_id")
    await _get_cliente(cid)
    tipo = payload.get("tipo") if payload.get("tipo") in TIPOS_DOC else None
    sets = {"cliente_id": cid}
    if tipo:
        sets["tipo"] = tipo
    r = await db.victoria_docs.update_one({"id": did, "cliente_id": None, "cuarentena": {"$ne": True}}, {"$set": sets})
    if not r.modified_count:
        raise HTTPException(status_code=404, detail="Documento sin clasificar no encontrado")
    aud = await auditar_cliente(cid)
    return {"ok": True, "auditoria": aud}


@vict.post("/avisos/{aid}/leido")
async def aviso_leido(aid: str, request: Request):
    _exigir(request)
    await db.victoria_avisos.update_one({"id": aid}, {"$set": {"leido": True}})
    return {"ok": True}


# ══════════ REDISEÑO 2026: dashboard consolidado, preview, revisión y contacto ══════════
@vict.get("/dashboard")
async def dashboard(request: Request):
    u = _exigir(request)
    clientes = await db.victoria_clientes.find({}, {"_id": 0}).sort("creado", -1).to_list(300)
    out, tot_falt, tot_valid_ok, tot_criticas, listos = [], 0, 0, 0, 0
    for c in clientes:
        docs = await db.victoria_docs.find({"cliente_id": c["id"]}, {"_id": 0, "ruta": 0}).to_list(100)
        docs_ok = [d for d in docs if (d.get("revision") or {}).get("decision") != "rechazado"]
        presentes = {d["tipo"] for d in docs_ok}
        faltantes = [ETIQUETAS[t] for t in DOCS_REQUERIDOS if t not in presentes]
        aud = c.get("auditoria") or {}
        coin = aud.get("coincidencias", [])
        v_ok = sum(1 for x in coin if x.get("ok") is True)
        n_crit = sum(1 for a in aud.get("alertas", []) if a.get("nivel") == "critica")
        es_listo = (not aud.get("bloqueado", True)) and c.get("formularios_confirmados") and not c.get("despachado")
        if not c.get("despachado"):
            tot_falt += len(faltantes)
            tot_criticas += n_crit
        tot_valid_ok += v_ok
        listos += 1 if es_listo else 0
        out.append({"id": c["id"], "nombre": c["nombre"], "rut": c.get("rut", ""),
                    "email": c.get("email", ""), "telefono": c.get("telefono", ""),
                    "n_docs": len(docs_ok), "faltantes": faltantes,
                    "despachado": c.get("despachado", False), "listo_envio": es_listo,
                    "bloqueado": aud.get("bloqueado", True) if aud else None,
                    "validaciones_ok": v_ok, "validaciones_total": len(coin),
                    "alertas_criticas": n_crit, "creado": c.get("creado", ""),
                    "siguiente": _paso_siguiente(c, docs_ok, c.get("auditoria"))})
    avisos = await db.victoria_avisos.find({"leido": False}, {"_id": 0}).sort("fecha", -1).to_list(30)
    sin_clasificar = await db.victoria_docs.find({"cliente_id": None, "cuarentena": {"$ne": True}, "descartado": {"$ne": True}}, {"_id": 0, "ruta": 0}).sort("recibido", -1).to_list(30)
    despachados = sum(1 for c in out if c["despachado"])
    pendientes = len(out) - despachados
    cfg = await db.config.find_one({"_key": "fuentes_imap_victoria"}, {"_id": 0}) or {}
    cuarentena = await db.victoria_docs.find({"cuarentena": True, "descartado": {"$ne": True}}, {"_id": 0, "ruta": 0}).sort("recibido", -1).to_list(30)
    eventos = await db.victoria_eventos.find({}, {"_id": 0}).sort("fecha", -1).to_list(25)
    u_doc = await db.users.find_one({"codigo": u.get("sub", "")}) or {}
    return {"kpis": {"clientes_pendientes": pendientes, "docs_faltantes": tot_falt,
                     "validaciones_aprobadas": tot_valid_ok,
                     "alertas_activas": len(avisos) + tot_criticas + len(cuarentena),
                     "despachados": despachados, "listos_envio": listos,
                     "estado_general_pct": round(100 * despachados / len(out)) if out else 0},
            "clientes": out, "avisos": avisos, "sin_clasificar": sin_clasificar,
            "cuarentena": cuarentena, "eventos": eventos,
            "pin_configurado": bool(u_doc.get("pin_seguridad_hash")),
            "correo_monitoreado": cfg.get("correo_principal", ""), "tipos": ETIQUETAS,
            "docs_requeridos": [ETIQUETAS[t] for t in DOCS_REQUERIDOS]}


@vict.get("/documentos/{did}/contenido")
async def doc_contenido(did: str, request: Request):
    """Preview instantáneo: entrega el archivo inline (PDF/imagen) sin descarga."""
    from fastapi.responses import Response as _Resp
    _exigir(request)
    d = await db.victoria_docs.find_one({"id": did})
    if not d or not d.get("ruta"):
        raise HTTPException(status_code=404, detail="Documento no encontrado en la bóveda")
    p = Path(d["ruta"])
    if not p.exists():
        raise HTTPException(status_code=404, detail="El archivo físico no está disponible en esta sesión")
    import mimetypes
    mt = mimetypes.guess_type(d.get("archivo", ""))[0] or "application/pdf"
    return _Resp(content=p.read_bytes(), media_type=mt,
                 headers={"Content-Disposition": f'inline; filename="{d.get("archivo", "documento")}"'})


@vict.post("/documentos/{did}/revision")
async def doc_revision(did: str, payload: dict, request: Request):
    """Victoria acepta o rechaza el documento tras verlo en el preview."""
    u = _exigir(request)
    decision = payload.get("decision")
    if decision not in ("aceptado", "rechazado"):
        raise HTTPException(status_code=400, detail="Decisión inválida: debe ser 'aceptado' o 'rechazado'")
    motivo = (payload.get("motivo") or "").strip()
    if decision == "rechazado" and not motivo:
        raise HTTPException(status_code=400, detail="Indique el motivo del rechazo del documento")
    d = await db.victoria_docs.find_one({"id": did}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    await db.victoria_docs.update_one({"id": did}, {"$set": {"revision": {
        "decision": decision, "motivo": motivo, "por": u.get("sub", ""), "fecha": _now()}}})
    if decision == "rechazado":
        await _aviso("doc_rechazado", f"Daniela rechazó «{d.get('archivo','')}»: {motivo}", d.get("cliente_id"))
    aud = await auditar_cliente(d["cliente_id"]) if d.get("cliente_id") else None
    return {"ok": True, "decision": decision, "auditoria": aud}


@vict.put("/documentos/{did}/tipo")
async def doc_tipo(did: str, payload: dict, request: Request):
    _exigir(request)
    tipo = payload.get("tipo")
    if tipo not in TIPOS_DOC:
        raise HTTPException(status_code=400, detail="Tipo de documento inválido")
    d = await db.victoria_docs.find_one({"id": did}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    await db.victoria_docs.update_one({"id": did}, {"$set": {"tipo": tipo}})
    aud = await auditar_cliente(d["cliente_id"]) if d.get("cliente_id") else None
    return {"ok": True, "tipo": tipo, "auditoria": aud}


@vict.put("/clientes/{cid}/contacto")
async def contacto(cid: str, payload: dict, request: Request):
    _exigir(request)
    await _get_cliente(cid)
    email_c = (payload.get("email") or "").strip().lower()
    tel = re.sub(r"[^\d+]", "", payload.get("telefono") or "")
    if email_c and "@" not in email_c:
        raise HTTPException(status_code=400, detail="Correo del cliente inválido")
    await db.victoria_clientes.update_one({"id": cid}, {"$set": {"email": email_c, "telefono": tel}})
    return {"ok": True, "email": email_c, "telefono": tel}


@vict.post("/clientes/{cid}/enviar-correo")
async def enviar_correo_cliente(cid: str, payload: dict, request: Request):
    """Contactabilidad directa: Victoria envía un correo al cliente desde el sistema."""
    u = _exigir(request)
    c = await _get_cliente(cid)
    email_dest = (payload.get("email") or c.get("email") or "").strip().lower()
    asunto = (payload.get("asunto") or "").strip()
    mensaje = (payload.get("mensaje") or "").strip()
    if not email_dest or "@" not in email_dest:
        raise HTTPException(status_code=400, detail="El cliente no tiene correo registrado: guárdelo primero en la ficha")
    if not asunto or not mensaje:
        raise HTTPException(status_code=400, detail="Complete el asunto y el mensaje del correo")
    cuerpo = mensaje.replace("\n", "<br>")
    html = (f"<div style='font-family:Georgia,serif;color:#1a1a1a;max-width:640px'>"
            f"<p>{cuerpo}</p><hr style='border:none;border-top:2px solid #8a6d1a'>"
            f"<p style='color:#8a6d1a;font-weight:bold'>Daniela Galindo<br>"
            f"Central Mutuos · Con Creces</p></div>")
    import email_service as mail
    r = await asyncio.to_thread(mail.send_mail, email_dest, asunto, html, None, "secundaria")
    if not r.get("success"):
        raise HTTPException(status_code=502, detail=f"No se pudo enviar el correo: {str(r.get('error'))[:120]}")
    await db.victoria_contactos.insert_one({
        "id": str(uuid.uuid4()), "cliente_id": cid, "canal": "correo", "destino": email_dest,
        "asunto": asunto, "mensaje": mensaje, "por": u.get("sub", ""), "fecha": _now()})
    return {"ok": True, "mensaje": f"Correo enviado a {email_dest}"}

# ══════════ PIN DE SEGURIDAD Y CUARENTENA (Regla de Oro 15) ══════════
@vict.post("/pin")
async def pin_config(payload: dict, request: Request):
    """Crea o cambia el PIN de seguridad de 4 dígitos para cargas forzadas."""
    u = _exigir(request)
    import bcrypt as _b
    pin = str(payload.get("pin") or "").strip()
    conf = str(payload.get("confirmacion") or "").strip()
    if not re.match(r"^\d{4}$", pin):
        raise HTTPException(status_code=400, detail="El PIN debe ser exactamente 4 dígitos numéricos")
    if pin != conf:
        raise HTTPException(status_code=400, detail="El PIN y su confirmación no coinciden")
    u_doc = await db.users.find_one({"codigo": u.get("sub", "")}) or {}
    if u_doc.get("pin_seguridad_hash"):
        actual = str(payload.get("pin_actual") or "").strip()
        if not actual or not _b.checkpw(actual.encode(), u_doc["pin_seguridad_hash"].encode()):
            raise HTTPException(status_code=403, detail="El PIN actual no es correcto")
    await db.users.update_one({"codigo": u.get("sub", "")},
                              {"$set": {"pin_seguridad_hash": _b.hashpw(pin.encode(), _b.gensalt()).decode()}})
    return {"ok": True, "mensaje": "PIN de seguridad guardado"}


@vict.post("/cuarentena/{did}/revalidar")
async def cuarentena_revalidar(did: str, payload: dict, request: Request):
    """Re-contrasta el documento contra la ficha (ya corregida). Si todo coincide, se asocia solo."""
    _exigir(request)
    d = await db.victoria_docs.find_one({"id": did, "cuarentena": True}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Documento en cuarentena no encontrado")
    cid = payload.get("cliente_id") or d.get("candidato_cliente_id")
    c = await _get_cliente(cid)
    validaciones = _validar_ingreso(c, await _docs_validos(cid), d.get("datos"))
    fallas = [v for v in validaciones if v["ok"] is False]
    if fallas:
        await db.victoria_docs.update_one({"id": did}, {"$set": {
            "validaciones_ingreso": validaciones, "candidato_cliente_id": cid, "candidato_nombre": c["nombre"]}})
        return {"ok": True, "asociado": False, "validaciones": validaciones,
                "mensaje": f"Aún hay {len(fallas)} validación(es) que no coinciden: sigue en cuarentena"}
    await db.victoria_docs.update_one({"id": did}, {
        "$set": {"cliente_id": cid, "validaciones_ingreso": validaciones},
        "$unset": {"cuarentena": "", "candidato_cliente_id": "", "candidato_nombre": ""}})
    aud = await auditar_cliente(cid)
    await _evento(d.get("archivo", ""), d.get("tipo", "otro"), "asociado", c, validaciones, origen="revalidacion")
    return {"ok": True, "asociado": True, "auditoria": aud,
            "mensaje": f"Las 4 validaciones coinciden: «{d.get('archivo','')}» quedó en la bóveda de {c['nombre']}"}


@vict.post("/cuarentena/{did}/asociar")
async def cuarentena_asociar(did: str, payload: dict, request: Request):
    """Asociación forzada con PIN de seguridad: queda registrada como carga forzada."""
    u = _exigir(request)
    d = await db.victoria_docs.find_one({"id": did, "cuarentena": True}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Documento en cuarentena no encontrado")
    await _verificar_pin(u.get("sub", ""), str(payload.get("pin") or ""))
    cid = payload.get("cliente_id") or d.get("candidato_cliente_id")
    c = await _get_cliente(cid)
    await db.victoria_docs.update_one({"id": did}, {
        "$set": {"cliente_id": cid, "forzado_manual": {"por": u.get("sub", ""), "fecha": _now()}},
        "$unset": {"cuarentena": "", "candidato_cliente_id": "", "candidato_nombre": ""}})
    await _aviso("forzado_manual",
                 f"REGISTRO: {u.get('sub','')} asoció con PIN «{d.get('archivo','')}» a {c['nombre']} "
                 f"pese a validación de ingreso no coincidente.", cid)
    aud = await auditar_cliente(cid)
    await _evento(d.get("archivo", ""), d.get("tipo", "otro"), "manual_forzado", c,
                  d.get("validaciones_ingreso"), origen="cuarentena")
    return {"ok": True, "auditoria": aud, "mensaje": f"Documento asociado a {c['nombre']} con registro de carga forzada"}


@vict.post("/documentos/{did}/descartar")
async def doc_descartar(did: str, payload: dict, request: Request):
    u = _exigir(request)
    motivo = (payload.get("motivo") or "").strip()
    if not motivo:
        raise HTTPException(status_code=400, detail="Indique el motivo para descartar el documento")
    d = await db.victoria_docs.find_one({"id": did}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    await db.victoria_docs.update_one({"id": did}, {
        "$set": {"descartado": True, "descartado_info": {"por": u.get("sub", ""), "motivo": motivo, "fecha": _now()}},
        "$unset": {"cuarentena": ""}})
    await _evento(d.get("archivo", ""), d.get("tipo", "otro"), "descartado", None, None, origen="manual")
    return {"ok": True, "mensaje": f"«{d.get('archivo','')}» descartado definitivamente"}

# ══════════ TRAZABILIDAD DE DATOS CRÍTICOS (clic → documento de origen) ══════════
CAMPOS_TRAZABLES = {"nombre_cliente", "rut_titular", "rut_codeudor", "rol_avaluo", "direccion_propiedad"}
ETIQUETA_CAMPO = {"nombre_cliente": "Nombre del cliente", "rut_titular": "RUT del cliente principal",
                  "rut_codeudor": "RUT del codeudor", "rol_avaluo": "Rol de avalúo fiscal",
                  "direccion_propiedad": "Dirección de la propiedad"}
MAPEO_ORIGEN = {
    "rut_titular": ["cedula", "carpeta_credito", "tasacion", "titulos", "simulacion"],
    "nombre_cliente": ["cedula", "carpeta_credito", "tasacion", "titulos"],
    "rut_codeudor": ["cedula", "carpeta_credito", "titulos", "tasacion"],
    "rol_avaluo": ["tasacion", "titulos", "certificado_avaluo"],
    "direccion_propiedad": ["titulos", "tasacion"],
}


def _pagina_de(ruta, valor, campo):
    """Busca en qué página del PDF aparece el dato (1-indexado)."""
    try:
        from pypdf import PdfReader
        rd = PdfReader(ruta)
    except Exception:
        return 1
    if campo in ("rut_titular", "rut_codeudor", "rol_avaluo"):
        aguja = re.sub(r"[^0-9kK]", "", str(valor)).lower()
        prep = lambda t: re.sub(r"[^0-9a-zk]", "", t.lower())
    else:
        aguja = re.sub(r"\s+", " ", str(valor).lower()).strip()
        prep = lambda t: re.sub(r"\s+", " ", t.lower())
    if not aguja:
        return 1
    for i, pg in enumerate(rd.pages[:60]):
        try:
            tx = prep(pg.extract_text() or "")
        except Exception:
            continue
        if aguja in tx:
            return i + 1
    return 1


@vict.get("/clientes/{cid}/origen-dato/{campo}")
async def origen_dato(cid: str, campo: str, request: Request):
    """Devuelve el documento físico (y la página) de donde se extrajo un dato crítico."""
    _exigir(request)
    if campo not in MAPEO_ORIGEN:
        raise HTTPException(status_code=400, detail="Dato no trazable")
    c = await _get_cliente(cid)
    docs = await _docs_validos(cid)
    forms = _formularios_auto(c, docs)
    valor = str(forms.get(campo) or "").strip()
    if not valor:
        raise HTTPException(status_code=404, detail=f"No hay valor registrado para {ETIQUETA_CAMPO[campo]}")
    if campo in ("rut_titular", "rut_codeudor"):
        norm = _norm_rut
    elif campo == "rol_avaluo":
        norm = _norm_rol
    elif campo == "direccion_propiedad":
        norm = _norm_dir
    else:
        norm = lambda s: re.sub(r"\s+", " ", str(s).lower().strip())
    objetivo = norm(valor)
    prioridad = MAPEO_ORIGEN[campo]

    def rank(d):
        try:
            p = prioridad.index(d.get("tipo"))
        except ValueError:
            p = 99
        datos = d.get("datos") or {}
        contiene = any(norm(str(datos.get(k) or "")) == objetivo
                       for k in ("rut_titular", "rut_codeudor", "rol_avaluo", "direccion_propiedad", "nombre_cliente")
                       if datos.get(k))
        return (0 if contiene else 1, p)

    candidatos = sorted(docs, key=rank)
    if not candidatos:
        raise HTTPException(status_code=404, detail="No hay documentos en la bóveda para rastrear este dato")
    elegido = candidatos[0]
    full = await db.victoria_docs.find_one({"id": elegido["id"]}) or {}
    ruta = full.get("ruta")
    pagina = 1
    if ruta and Path(ruta).exists():
        pagina = await asyncio.to_thread(_pagina_de, ruta, valor, campo)
    return {"doc_id": elegido["id"], "archivo": elegido.get("archivo", ""),
            "tipo": elegido.get("tipo", ""), "tipo_etiqueta": ETIQUETAS.get(elegido.get("tipo"), ""),
            "pagina": pagina, "campo": campo, "etiqueta": ETIQUETA_CAMPO[campo], "valor": valor}


def _doc_origen(docs, campo, valor):
    """Mejor documento candidato del cual proviene un dato (mismo criterio que origen-dato)."""
    if campo in ("rut_titular", "rut_codeudor"):
        norm = _norm_rut
    elif campo == "rol_avaluo":
        norm = _norm_rol
    elif campo == "direccion_propiedad":
        norm = _norm_dir
    else:
        norm = lambda s: re.sub(r"\s+", " ", str(s).lower().strip())
    objetivo = norm(valor)
    prioridad = MAPEO_ORIGEN.get(campo, [])

    def rank(d):
        try:
            p = prioridad.index(d.get("tipo"))
        except ValueError:
            p = 99
        datos = d.get("datos") or {}
        contiene = any(norm(str(datos.get(k) or "")) == objetivo
                       for k in ("rut_titular", "rut_codeudor", "rol_avaluo", "direccion_propiedad", "nombre_cliente")
                       if datos.get(k))
        return (0 if contiene else 1, p)

    cand = sorted(docs, key=rank)
    return cand[0] if cand else None


@vict.get("/clientes/{cid}/auditoria-campos")
async def auditoria_campos(cid: str, request: Request):
    """REGLA IRRENUNCIABLE 2 — Vista de auditoría: cada campo con su documento de origen,
    página exacta y acceso al fragmento original. Lo no hallado queda vacío y PENDIENTE."""
    _exigir(request)
    c = await _get_cliente(cid)
    docs = await _docs_validos(cid)
    forms = _formularios_auto(c, docs)
    out = []
    for campo in ("nombre_cliente", "rut_titular", "rut_codeudor", "rol_avaluo", "direccion_propiedad"):
        valor = str(forms.get(campo) or "").strip()
        item = {"campo": campo, "etiqueta": ETIQUETA_CAMPO[campo], "valor": valor,
                "pendiente": not valor, "doc_id": "", "archivo": "", "tipo_etiqueta": "", "pagina": 0}
        if valor and docs:
            elegido = _doc_origen(docs, campo, valor)
            if elegido:
                full = await db.victoria_docs.find_one({"id": elegido["id"]}) or {}
                ruta = full.get("ruta")
                pagina = 1
                if ruta and Path(ruta).exists():
                    pagina = await asyncio.to_thread(_pagina_de, ruta, valor, campo)
                item.update({"doc_id": elegido["id"], "archivo": elegido.get("archivo", ""),
                             "tipo_etiqueta": ETIQUETAS.get(elegido.get("tipo"), ""), "pagina": pagina})
        out.append(item)
    pendientes = [x["etiqueta"] for x in out if x["pendiente"]]
    return {"campos": out, "pendientes": pendientes,
            "regla": ("Llenado automatizado estricto: el sistema solo completa lo que encuentra con "
                      "certeza en los documentos. Está prohibido inventar o asumir valores; lo no "
                      "hallado queda vacío y marcado como pendiente.")}


@vict.get("/documentos/{did}/fragmento")
async def fragmento_documento(did: str, request: Request, q: str = "", pagina: int = 1):
    """Renderiza el fragmento original del documento donde aparece el dato (recorte de la página)."""
    _exigir(request)
    d = await db.victoria_docs.find_one({"id": did}) or {}
    ruta = d.get("ruta")
    if not ruta or not Path(ruta).exists():
        raise HTTPException(status_code=404, detail="El documento físico no está disponible en la bóveda")

    def render():
        import fitz
        pdf = fitz.open(ruta)
        idx = min(max(0, (pagina or 1) - 1), len(pdf) - 1)
        page = pdf[idx]
        rects = []
        for v in dict.fromkeys([q.strip(), q.strip().upper(), q.strip().lower()]):
            if not v:
                continue
            try:
                rects = page.search_for(v)
            except Exception:
                rects = []
            if rects:
                break
        if rects:
            r0 = rects[0]
            for r in rects[1:3]:
                r0 |= r
            m = 55
            clip = fitz.Rect(max(0, r0.x0 - m), max(0, r0.y0 - m),
                             min(page.rect.x1, r0.x1 + m * 3), min(page.rect.y1, r0.y1 + m))
            pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), clip=clip)
        else:
            pix = page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6))
        data = pix.tobytes("png")
        pdf.close()
        return data, bool(rects)

    data, hallado = await asyncio.to_thread(render)
    from fastapi.responses import Response as _Resp
    return _Resp(content=data, media_type="image/png",
                 headers={"X-Fragmento-Hallado": "1" if hallado else "0"})


# ══════════ DEMO MÓDULO VICTORIA: video descargable y envío por correo ══════════
_ROOT = Path("/app/backend") if Path("/app/backend").is_dir() else Path(__file__).resolve().parent
DEMOS_DIR = _ROOT / "demos"
DEMOS_DIR.mkdir(parents=True, exist_ok=True)


@vict.get("/demo/video")
async def demo_video(request: Request, modulo: str = "victoria"):
    _exigir(request)
    archivo = {"victoria": "demo_victoria.mp4", "ventas": "demo_ventas.mp4", "mutuos": "demo_mutuos.mp4", "web": "demo_web.mp4"}.get(modulo)
    if not archivo:
        raise HTTPException(status_code=400, detail="Módulo de demo inválido")
    p = DEMOS_DIR / archivo
    if not p.exists():
        raise HTTPException(status_code=404, detail="El video de la demo aún no ha sido generado")
    from fastapi.responses import FileResponse
    return FileResponse(p, media_type="video/mp4", filename=f"Demo_Modulo_{modulo.title()}_Central_Mutuos.mp4")


@vict.post("/demo/enviar")
async def demo_enviar(payload: dict, request: Request):
    u = _exigir(request)
    modulo = payload.get("modulo") or "victoria"
    archivo = {"victoria": "demo_victoria.mp4", "ventas": "demo_ventas.mp4", "mutuos": "demo_mutuos.mp4", "web": "demo_web.mp4"}.get(modulo)
    if not archivo:
        raise HTTPException(status_code=400, detail="Módulo de demo inválido")
    p = DEMOS_DIR / archivo
    if not p.exists():
        raise HTTPException(status_code=404, detail="El video de la demo aún no ha sido generado")
    import base64
    import email_service as mail
    dest = (payload.get("email") or "gerardo.ext@centralmutuos.cl").strip()
    asunto = (payload.get("asunto") or f"Demo módulo {modulo.title()} - Central Mutuos ConCreces").strip()
    b64 = base64.b64encode(p.read_bytes()).decode()
    html = (f"<div style='font-family:Georgia,serif;color:#1a1a1a;max-width:640px'>"
            f"<h2 style='color:#8a6d1a'>{asunto}</h2>"
            f"<p>Se adjunta el video de la demo del módulo {modulo.title()} de Central Mutuos, "
            f"narrado por Martín, con datos ficticios.</p>"
            "<hr style='border:none;border-top:2px solid #8a6d1a'>"
            "<p style='color:#8a6d1a;font-weight:bold'>Central Mutuos · Con Creces</p></div>")
    r = await asyncio.to_thread(mail.send_mail, dest, asunto,
                                html, [{"filename": f"Demo_Modulo_{modulo.title()}_Central_Mutuos.mp4", "content_b64": b64}],
                                "secundaria")
    if not r.get("success"):
        raise HTTPException(status_code=502, detail=f"No se pudo enviar el correo: {str(r.get('error'))[:120]}")
    return {"ok": True, "mensaje": f"Video de la demo enviado a {dest}"}

# ══════════ MÓDULO VENTAS: asignación alternada automática ══════════
EJECUTIVOS_VENTAS = {"yerile": "Yerile Barrera", "deysi": "Deisy Salazar", "gerardo": "Gerardo Barrera"}
EJECUTIVOS_INCOMPLETOS = ("yerile", "deysi")  # distribución aleatoria de fichas incompletas


async def asignar_a_ventas_si_corresponde(cid, texto=""):
    """Regla Ventas (entrega inmediata): ficha COMPLETA → Gerardo Barrera automático
    (reasignable manualmente por el Administrador); ficha INCOMPLETA → distribución
    aleatoria entre Yerile Barrera y Deisy Salazar."""
    c = await db.victoria_clientes.find_one({"id": cid})
    if not c or c.get("ventas") or c.get("despachado"):
        return None
    inmediata = bool(c.get("entrega_inmediata")) or bool(re.search(r"entrega\s+inmediata", (texto or "").lower()))
    if not inmediata:
        return None
    docs = await _docs_validos(cid)
    presentes = {d["tipo"] for d in docs}
    completa = all(t in presentes for t in DOCS_REQUERIDOS)
    if completa:
        sig = "gerardo"
        motivo = ("Ficha completa: asignación automática a Gerardo Barrera "
                  "(el Administrador puede reasignar manualmente a otro ejecutivo).")
    else:
        import random
        sig = random.choice(EJECUTIVOS_INCOMPLETOS)
        motivo = (f"Ficha incompleta: distribución aleatoria entre Yerile Barrera y Deisy Salazar — "
                  f"queda a cargo de {EJECUTIVOS_VENTAS[sig]} mientras no haya asignación definitiva.")
    import constitucion as _const
    await _const.consultar_cerebro(db, "asignacion_ventas",
                                   texto_ia=f"Asignación de {c['nombre']} a {EJECUTIVOS_VENTAS[sig]}: {motivo}",
                                   modulo="victoria_independiente.py (asignar_a_ventas)")
    await db.victoria_clientes.update_one({"id": cid}, {"$set": {
        "entrega_inmediata": True,
        "ventas": {"ejecutivo": sig, "ejecutivo_nombre": EJECUTIVOS_VENTAS[sig],
                   "asignado_en": _now(), "estado": "en_gestion", "contactos": [],
                   "ultimo_evento": _now(),
                   "timeline": [{"fecha": _now(), "por": "sistema", "accion": motivo}]}}})
    await _aviso("ventas", f"Nueva gestión asignada — {c['nombre']} queda bajo la responsabilidad de "
                           f"{EJECUTIVOS_VENTAS[sig]}. {motivo} "
                           f"Se espera el primer contacto dentro de las próximas 24 horas.", cid)
    try:
        await _notificar_aviso_ventas(c, sig)
    except Exception:
        pass
    return sig


async def _notificar_aviso_ventas(cliente, ejecutivo_asignado):
    """Aviso del sistema por correo, asignado ALEATORIAMENTE entre las ejecutivas de Ventas."""
    import random
    cfg = await db.config.find_one({"_key": "ventas_emails"}) or {}
    ej_aviso = random.choice(list(EJECUTIVOS_VENTAS.keys()))
    emails = cfg.get(ej_aviso) or []
    if not emails:
        return
    import email_service as mail_srv
    html = (f"<div style='font-family:Georgia,serif;background:#0a0a0a;color:#f4f4f5;padding:28px 32px;border-radius:10px;max-width:620px'>"
            f"<div style='color:#C9A227;font-size:20px;font-weight:bold;letter-spacing:2px'>CENTRAL MUTUOS</div>"
            f"<div style='height:1px;background:#C9A227;margin:10px 0 18px'></div>"
            f"<h3 style='color:#C9A227;margin:0 0 12px'>Nueva gestión asignada — Módulo Ventas</h3>"
            f"<p style='line-height:1.7;margin:0 0 12px'>Estimada {EJECUTIVOS_VENTAS[ej_aviso].split()[0]}:</p>"
            f"<p style='line-height:1.7;margin:0 0 12px'>El sistema ha asignado la gestión de "
            f"<b style='color:#FCF6BA'>{cliente['nombre']}</b> (RUT {cliente.get('rut','—')}) a "
            f"<b style='color:#FCF6BA'>{EJECUTIVOS_VENTAS[ejecutivo_asignado]}</b>, aplicando el criterio de "
            f"balance de carga inteligente. La solicitud presenta documentación incompleta y propiedad de "
            f"entrega inmediata: se espera el primer contacto dentro de las próximas 24 horas.</p>"
            f"<p style='color:#a1a1aa;font-size:13px;margin:16px 0 0'>Este aviso fue dirigido a usted según la "
            f"distribución aleatoria de notificaciones del módulo.</p>"
            f"<div style='height:1px;background:#333;margin:18px 0 12px'></div>"
            f"<p style='color:#C9A227;font-weight:bold;margin:0'>Central Mutuos · Módulo Ventas</p></div>")
    for em in emails:
        try:
            await asyncio.to_thread(mail_srv.send_mail, em,
                                    f"Nueva solicitud en Módulo Ventas: {cliente['nombre']}", html, None, "secundaria")
        except Exception:
            pass
