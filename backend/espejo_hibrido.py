"""ALGORITMO ESPEJO HÍBRIDO ADMINISTRATIVO — fuente principal: correos IMAP.

Fuentes: Victoria (primaria, input Concreces), Daniela (administrativa complementaria),
Javier (postventa / seguimiento de escritura).
Capas: aprobación (evaluación) · administrativa (documentación/plazos) · postventa (escritura).
Credenciales: 1º variables de entorno IMAP_<FUENTE>_*, 2º panel del Admin (cifradas Fernet).
Sin credenciales → EN ESPERA, sin errores. Cada barrido queda auditado en espejo_barridos.
"""
import os
import re
import json
import uuid
import asyncio
import hashlib
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from database import db

hibrido = APIRouter(prefix="/espejo-hibrido")

MODELO = "claude-sonnet-4-6"
INTERVALO_SEG = 300
MAX_CORREOS_BARRIDO = 10

FUENTES = [
    {"fid": "victoria", "eid": "victoria_vilchez", "nombre": "Victoria Vílchez",
     "email": "victoriavilches@centralmutuos.cl", "prioridad": "PRIMARIA",
     "descripcion": "Fuente primaria del Algoritmo Espejo — todo lo de Concreces es el input principal",
     "env": "VICTORIA", "usuario_codigo": "victoria"},
    {"fid": "daniela", "eid": "daniela_galindo", "nombre": "Daniela Galindo",
     "email": "danielagalindo@centralmutuos.cl", "prioridad": "COMPLEMENTARIA",
     "descripcion": "Fuente administrativa complementaria",
     "env": "DANIELA", "usuario_codigo": "daniela"},
    {"fid": "javier", "eid": "javier_urrutia", "nombre": "Javier Urrutia",
     "email": "javierurrutia@centralmutuos.cl", "prioridad": "POSTVENTA",
     "descripcion": "Fuente del módulo postventa y seguimiento de escritura",
     "env": "JAVIER", "usuario_codigo": "postventa"},
]

PROMPT_HIBRIDO = """Eres el analista del Algoritmo Espejo Híbrido Administrativo de Central Mutuos (crédito hipotecario chileno).
Analizas correos entrantes (principalmente de Concreces) y extraes datos estructurados.

Responde ÚNICAMENTE con un JSON válido (sin markdown) con esta estructura exacta:
{
  "tipo_comunicacion": "aprobación|rechazo|observaciones|requerimiento|documentación|plazo|instrucción administrativa|seguimiento escritura|otro",
  "nro_operacion": "número de operación si aparece, sino ''",
  "rut": "RUT del cliente si aparece, sino ''",
  "estado": "estado normalizado: Aprobada|Rechazada|Cursada|Escriturada|Con Observaciones|En Estudio|Pendiente|''",
  "requerimientos": ["documentos o acciones solicitadas"],
  "alertas": ["alertas de riesgo, incumplimientos o menciones normativas"],
  "plazos": ["plazos mencionados, con días y contexto"],
  "capa": "aprobacion|administrativa|postventa",
  "discrepancia": true/false,
  "motivo_discrepancia": "si los criterios de Concreces difieren de los criterios estándar del sistema (LTV, renta, subsidio, plazos), explíquelo; sino ''",
  "resumen": "resumen ejecutivo de 1-2 frases en español"
}

REGLAS:
- capa=aprobacion: estados de aprobación, rechazos, observaciones y requerimientos de evaluación.
- capa=administrativa: documentación, plazos, instrucciones administrativas.
- capa=postventa: seguimiento de escritura, notaría, firmas, postventa.
- discrepancia=true SOLO si el correo aplica criterios distintos a los estándar del sistema.
- NO inventes datos. Responde siempre en español."""


def _now():
    return datetime.now(timezone.utc).isoformat()


def _rol(request):
    return (getattr(request.state, "user", {}) or {}).get("rol", "")


def _descifrar(token):
    from cryptography.fernet import Fernet
    return Fernet(os.environ["CRED_CIPHER_KEY"].encode()).decrypt(token.encode()).decode()


async def seed_espejo_hibrido():
    """Registra los correos oficiales de las 3 fuentes (idempotente, no pisa credenciales)."""
    for f in FUENTES:
        doc = await db.ejecutivos_correo.find_one({"eid": f["eid"]})
        if doc and not (doc.get("email") or "").strip():
            await db.ejecutivos_correo.update_one({"eid": f["eid"]}, {"$set": {"email": f["email"]}})
        elif not doc:
            await db.ejecutivos_correo.insert_one({"eid": f["eid"], "nombre": f["nombre"],
                                                   "email": f["email"], "servidor": "imap.gmail.com",
                                                   "activo": False, "creado": _now(), "actualizado": ""})
    logging.info("🪞 Espejo Híbrido: fuentes oficiales registradas (Victoria, Daniela, Javier)")


async def _credenciales(f):
    """Orden: 1º entorno (IMAP_<F>_*), 2º panel del Admin (cifradas). None → EN ESPERA."""
    e = f["env"]
    host = (os.environ.get(f"IMAP_{e}_HOST") or "").strip()
    user = (os.environ.get(f"IMAP_{e}_USER") or "").strip()
    pwd = (os.environ.get(f"IMAP_{e}_PASS") or "").strip()
    try:
        port = int(os.environ.get(f"IMAP_{e}_PORT") or 0)
    except ValueError:
        port = 0
    if user and pwd:
        return {"host": host or "imap.gmail.com", "port": port or 993,
                "user": user, "pwd": pwd, "origen": "entorno"}
    doc = await db.ejecutivos_correo.find_one({"eid": f["eid"]}) or {}
    if doc.get("email") and doc.get("clave_enc") and doc.get("activo"):
        try:
            return {"host": doc.get("servidor") or "imap.gmail.com", "port": 993,
                    "user": doc["email"], "pwd": _descifrar(doc["clave_enc"]), "origen": "panel"}
        except Exception as ex:
            logging.warning(f"espejo híbrido {f['fid']}: no fue posible descifrar credenciales: {ex}")
    return None


def _scan_imap(host, port, user, pwd, maxn=MAX_CORREOS_BARRIDO):
    import imaplib
    import email as emlib
    from email.header import decode_header
    M = imaplib.IMAP4_SSL(host, port or 993, timeout=25)
    M.login(user, pwd)
    M.select("INBOX", readonly=True)
    _, data = M.search(None, "ALL")
    ids = (data[0].split() or [])[-maxn * 3:]
    out = []
    for i in reversed(ids):
        try:
            _, msg_data = M.fetch(i, "(RFC822)")
            msg = emlib.message_from_bytes(msg_data[0][1])
            subj = ""
            for part, enc in decode_header(msg.get("Subject") or ""):
                subj += part.decode(enc or "utf-8", "ignore") if isinstance(part, bytes) else part
            body = ""
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "ignore")
                    break
            out.append({"subject": subj.strip(), "body": body[:5000],
                        "fecha": msg.get("Date") or "", "remitente": msg.get("From") or "",
                        "mid": msg.get("Message-ID") or ""})
        except Exception:
            continue
    M.logout()
    return out


async def _analizar(asunto, cuerpo, fecha):
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    key = os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        raise ValueError("EMERGENT_LLM_KEY no configurada")
    chat = LlmChat(api_key=key, session_id=f"espejo-hibrido-{uuid.uuid4()}",
                   system_message=PROMPT_HIBRIDO).with_model("anthropic", MODELO)
    texto = f"ASUNTO: {asunto or '(sin asunto)'}\nFECHA: {fecha or 'no indicada'}\n\nCUERPO:\n{(cuerpo or '')[:6000]}"
    resp = await chat.send_message(UserMessage(text=texto))
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
    capa = str(d.get("capa") or "").strip().lower()
    salida = {
        "tipo_comunicacion": str(d.get("tipo_comunicacion") or "").strip()[:80],
        "nro_operacion": str(d.get("nro_operacion") or "").strip()[:60],
        "rut": str(d.get("rut") or "").strip()[:20],
        "estado": str(d.get("estado") or "").strip()[:40],
        "requerimientos": [str(x)[:200] for x in (d.get("requerimientos") or []) if x][:10],
        "alertas": [str(x)[:200] for x in (d.get("alertas") or []) if x][:10],
        "plazos": [str(x)[:120] for x in (d.get("plazos") or []) if x][:8],
        "capa": capa if capa in ("aprobacion", "administrativa", "postventa") else "administrativa",
        "discrepancia": bool(d.get("discrepancia")),
        "motivo_discrepancia": str(d.get("motivo_discrepancia") or "").strip()[:300],
        "resumen": str(d.get("resumen") or "").strip()[:400],
        "modelo": MODELO, "analizado_en": _now(),
    }
    # AUTORIDAD SUPREMA: el Cerebro DashAI autoriza el análisis antes de aplicarse
    from constitucion import consultar_cerebro
    await consultar_cerebro(db, "espejo_hibrido_analisis_ia",
                            texto_ia=json.dumps(salida, ensure_ascii=False), modulo="espejo_hibrido.py")
    return salida


def _norm_rut(r):
    return re.sub(r"[^0-9kK]", "", r or "").lower()


async def _aplicar(f, correo, ia):
    """Aplica el análisis: vincula la operación; discrepancia → EN REVISIÓN (no procesa)."""
    ops_actualizadas = 0
    folder = None
    if ia.get("rut"):
        rn = _norm_rut(ia["rut"])
        if rn:
            async for fd in db.folders.find({}, {"id": 1, "nombre": 1, "datos_financieros.rut": 1}):
                if _norm_rut((fd.get("datos_financieros") or {}).get("rut", "")) == rn:
                    folder = fd
                    break
    if ia.get("discrepancia"):
        await db.alertas.insert_one({
            "id": str(uuid.uuid4()), "tipo": "espejo_revision", "leida": False, "fecha": _now(),
            "creado": _now(), "folder_id": (folder or {}).get("id", ""),
            "titulo": f"🪞 EN REVISIÓN — discrepancia de criterios ({f['nombre']})",
            "mensaje": f"Correo '{correo['subject'][:120]}': {ia.get('motivo_discrepancia') or 'criterios de Concreces difieren del sistema'}. "
                       f"La operación queda marcada para revisión antes de procesar."})
        if folder:
            await db.folders.update_one({"id": folder["id"]}, {"$set": {
                "espejo_revision": {"fecha": _now(), "motivo": ia.get("motivo_discrepancia") or "",
                                    "fuente": f["fid"], "asunto": correo["subject"][:200]}}})
            ops_actualizadas = 1
        return ops_actualizadas, True
    if folder:
        await db.folders.update_one({"id": folder["id"]}, {"$push": {
            "espejo_eventos": {"fecha": _now(), "fuente": f["fid"], "capa": ia["capa"],
                               "tipo": ia["tipo_comunicacion"], "estado": ia["estado"],
                               "resumen": ia["resumen"], "asunto": correo["subject"][:200]}}})
        ops_actualizadas = 1
    return ops_actualizadas, False


async def barrido_fuente(f, creds):
    """Un barrido completo de una fuente, con auditoría obligatoria."""
    inicio = datetime.now(timezone.utc)
    procesados = nuevos = ops_total = discrepancias = 0
    estado, error = "ok", ""
    try:
        correos = await asyncio.to_thread(_scan_imap, creds["host"], creds["port"],
                                          creds["user"], creds["pwd"])
        for c in correos:
            hid = hashlib.sha256(f"{f['fid']}|{c.get('mid') or c['subject']}|{c['fecha']}".encode()).hexdigest()
            if await db.espejo_hibrido_correos.find_one({"hid": hid}):
                continue
            if nuevos >= MAX_CORREOS_BARRIDO:
                break
            nuevos += 1
            try:
                ia = await _analizar(c["subject"], c["body"], c["fecha"])
                ops, disc = await _aplicar(f, c, ia)
                ops_total += ops
                discrepancias += 1 if disc else 0
                await db.espejo_hibrido_correos.insert_one({
                    "id": str(uuid.uuid4()), "hid": hid, "fecha": _now(), "fuente": f["fid"],
                    "asunto": c["subject"][:200], "remitente": c["remitente"][:150],
                    "capa": ia["capa"], "discrepancia": ia["discrepancia"],
                    "estado_proceso": "en_revision" if ia["discrepancia"] else "procesado", "ia": ia})
                procesados += 1
            except Exception as ex:
                logging.warning(f"espejo híbrido {f['fid']}: análisis falló: {ex}")
    except Exception as ex:
        estado, error = "error", str(ex)[:300]
    dur = int((datetime.now(timezone.utc) - inicio).total_seconds() * 1000)
    reg = {"id": str(uuid.uuid4()), "fecha": _now(), "fuente": f["fid"], "fuente_nombre": f["nombre"],
           "correos_procesados": procesados, "correos_nuevos": nuevos,
           "operaciones_actualizadas": ops_total, "discrepancias": discrepancias,
           "estado": estado, "error": error, "origen_credenciales": creds["origen"], "duracion_ms": dur}
    await db.espejo_barridos.insert_one(dict(reg))
    reg.pop("_id", None)
    return reg


async def _estado_fuente(f):
    creds = await _credenciales(f)
    ult = await db.espejo_barridos.find_one({"fuente": f["fid"]}, {"_id": 0}, sort=[("fecha", -1)])
    total = await db.espejo_hibrido_correos.count_documents({"fuente": f["fid"]})
    revision = await db.espejo_hibrido_correos.count_documents({"fuente": f["fid"], "discrepancia": True})
    if not creds:
        estado = "en_espera"
    elif ult and ult.get("estado") == "error":
        estado = "error"
    else:
        estado = "activo"
    return {"fid": f["fid"], "nombre": f["nombre"], "email": f["email"],
            "prioridad": f["prioridad"], "descripcion": f["descripcion"],
            "estado": estado, "origen_credenciales": creds["origen"] if creds else "ninguna",
            "ultimo_barrido": ult, "correos_totales": total, "en_revision": revision}


@hibrido.get("/estado")
async def hibrido_estado(request: Request):
    claims = getattr(request.state, "user", {}) or {}
    rol, sub = claims.get("rol", ""), claims.get("sub", "")
    if rol in ("admin", "maestro", "gerencia", "contralor"):
        visibles = FUENTES
    else:
        visibles = [f for f in FUENTES if f["usuario_codigo"] == sub]
        if not visibles:
            raise HTTPException(status_code=403, detail="Solo puede ver el estado de sincronización de su propio correo")
    fuentes = [await _estado_fuente(f) for f in visibles]
    fids = [f["fid"] for f in visibles]
    bitacora = await db.espejo_barridos.find({"fuente": {"$in": fids}}, {"_id": 0}).sort("fecha", -1).to_list(20)
    return {"fuentes": fuentes, "bitacora": bitacora, "intervalo_seg": INTERVALO_SEG,
            "puede_barrer": rol in ("admin", "maestro"),
            "nota": "Las credenciales jamás se exponen. Solo el Admin puede ingresarlas o modificarlas."}


@hibrido.post("/barrido")
async def hibrido_barrido_manual(request: Request):
    if _rol(request) not in ("admin", "maestro"):
        raise HTTPException(status_code=403, detail="El barrido manual es exclusivo del Administrador")
    resultados = []
    for f in FUENTES:
        creds = await _credenciales(f)
        if not creds:
            resultados.append({"fuente": f["fid"], "estado": "en_espera",
                               "detalle": "Sin credenciales — el sistema queda en espera sin errores"})
            continue
        resultados.append(await barrido_fuente(f, creds))
    return {"ok": True, "resultados": resultados}


async def espejo_hibrido_loop():
    """Barrido automático cada 5 minutos. Se activa solo cuando existen credenciales."""
    await asyncio.sleep(45)
    while True:
        for f in FUENTES:
            try:
                creds = await _credenciales(f)
                if creds:
                    await barrido_fuente(f, creds)
            except Exception as ex:
                logging.warning(f"espejo híbrido loop {f['fid']}: {ex}")
        await asyncio.sleep(INTERVALO_SEG)
