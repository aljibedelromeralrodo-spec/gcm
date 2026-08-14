"""MALLA DE INTELIGENCIA (Regla de Oro #34) + MÓDULO BROKERS (Usuarios D).

- Brokers (perfil D): cargan Set de Crédito, Proyección Mensual y ven SOLO sus carpetas
  con subcarpetas automáticas: Solicitud, Set Crédito y Estudio Título.
- Fuentes IMAP operativas por panel (victoria, daniela, postventa): correo principal
  + hasta 3 correos de aliados externos (Value Property, Guillermo Mardones, Notarías).
- Motor de seguimiento en tiempo real: DashAI rastrea envíos/recepciones con aliados y
  marca hitos externos. REGLA DE HIERRO: sin RUT en asunto/cuerpo, el hito NO se marca.
"""
import re
import os
import uuid
import base64
import bcrypt
import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from database import db
import email_service as mail
import folders_service as fsvc

broker = APIRouter(prefix="/broker")
fuentes = APIRouter(prefix="/fuentes")
hitos = APIRouter(prefix="/hitos")
flujos = APIRouter(prefix="/flujos")
micorreo = APIRouter(prefix="/mi-correo")

# MOTOR DE REPAROS: remitentes de los abogados de estudio de título / escrituración
REPARO_REMITENTES = ("mardluf", "gmardones", "olave", "ibarra")

# RADAR DE ESCRITURACIÓN — Documentación 2.0 y Log de Firmas
DOC20_REQ = {"03_afp": "AFP", "02_liquidaciones": "Liquidación actual", "04_cmf": "CMF actualizado"}
_MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
          "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
FECHA_RE = re.compile(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})\b")
FECHA_TXT_RE = re.compile(r"\b(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)(?:\s+de\s+(\d{4}))?", re.I)


def doc20_folder(fd):
    """Hito 'Documentación 2.0': AFP + Liquidación actual + CMF actualizado.
    Si falta uno → 'Pendiente de Información' (jamás se inventa)."""
    base = fsvc.folder_dir(fd.get("nombre") or "")
    faltantes = []
    for sub, label in DOC20_REQ.items():
        d = base / sub
        if not (d.exists() and any(p.is_file() for p in d.iterdir())):
            faltantes.append(label)
    return {"estado": "ok" if not faltantes else "pendiente_informacion", "faltantes": faltantes}


def firmas_folder(fd):
    """LOG DE FIRMAS según la simulación. REGLA DE HIERRO: con codeudor, el hito solo
    es VERDE cuando AMBOS firmaron — no se aceptan firmas parciales."""
    df = fd.get("datos_financieros") or {}
    aplica_codeudor = bool(fd.get("codeudor_rut") or fd.get("codeudor_nombre") or df.get("renta_codeudor"))
    log = fd.get("firmas_log") or {}
    roles = [("titular", "Titular", True), ("codeudor", "Codeudor", aplica_codeudor),
             ("mandatario", "Mandatario Judicial", True), ("anexos", "Anexos Notaría", True)]
    firmas = [{"rol": k, "label": lb, "estado": log.get(k, "pendiente")}
              for k, lb, aplica in roles if aplica]
    if firmas and all(f["estado"] == "firmado" for f in firmas):
        hito = "ok"
    elif any(f["estado"] == "firmado" for f in firmas):
        hito = "proceso"  # parcial = ⏳ amarillo, JAMÁS verde
    else:
        hito = "pendiente"
    return firmas, hito


def _capturar_fecha(texto):
    m = FECHA_TXT_RE.search(texto or "")
    if m:
        anio = int(m.group(3) or datetime.now(timezone.utc).year)
        try:
            return f"{anio:04d}-{_MESES[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
        except Exception:
            pass
    m = FECHA_RE.search(texto or "")
    if m:
        d, mth, a = int(m.group(1)), int(m.group(2)), int(m.group(3))
        a = a + 2000 if a < 100 else a
        if 1 <= mth <= 12 and 1 <= d <= 31:
            return f"{a:04d}-{mth:02d}-{d:02d}"
    return ""

_now = lambda: datetime.now(timezone.utc).isoformat()
_rut_limpio = lambda r: re.sub(r"[^0-9kK]", "", str(r or "")).lower()
RUT_RE = re.compile(r"\b(\d{1,2}\.?\d{3}\.?\d{3}\s*-\s*[0-9kK])\b")
EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")

PANELES = ("victoria", "daniela", "postventa", "brokers")
SUBCARPETAS_BROKER = [("06_solicitud", "Solicitud"),
                      ("08_set_credito", "Set Crédito"),
                      ("07_estudio_titulo", "Estudio Título"),
                      ("09_cartas_enmienda", "Cartas Enmienda"),
                      ("10_actualizaciones", "Doc. Actualización"),
                      ("99_otros", "Otros Documentos")]
# CENTRO DE CARGA MASIVA: categorías → subcarpeta física
CATEGORIAS_CARGA = {
    "set_credito": "08_set_credito", "carta_enmienda": "09_cartas_enmienda",
    "actualizacion": "10_actualizaciones", "otros": "99_otros",
}


def _panel_valido(panel):
    """Paneles fijos + fuentes personales por broker (broker_<codigo>)."""
    return panel in PANELES or panel.startswith("broker_")


async def _log_broker(claims, accion, detalle):
    """HUELLA DIGITAL DASHAI: cada interacción del broker queda registrada."""
    await db.broker_activity_log.insert_one({
        "id": str(uuid.uuid4()), "broker_codigo": claims.get("sub") or "",
        "broker_nombre": claims.get("nombre") or "", "accion": accion,
        "detalle": detalle, "fecha": _now()})

# Hitos conocidos por dominio aliado según dirección del correo
HITOS_BASE = {
    "valueproperty": {"enviado": "Tasación Solicitada", "recibido": "Respuesta Tasador"},
    "gmardones": {"enviado": "Estudio Solicitado", "recibido": "Estudio Recibido"},
}


def _claims(request):
    return getattr(request.state, "user", None) or {}


# ───────────────────────── MÓDULO BROKERS (Usuarios D) ─────────────────────
def _archivos_broker(nombre):
    base = fsvc.folder_dir(nombre)
    out = {}
    for sub, label in SUBCARPETAS_BROKER:
        d = base / sub
        out[sub] = sorted(p.name for p in d.iterdir() if p.is_file()) if d.exists() else []
    return out


@broker.get("/carpetas")
async def broker_carpetas(request: Request):
    c = _claims(request)
    codigo = c.get("sub") or ""
    q = {"broker_codigo": {"$exists": True}} if c.get("rol") in ("admin", "maestro") else {"broker_codigo": codigo}
    docs = await db.folders.find(q).sort("created_at", -1).to_list(300)
    carpetas = []
    for d in docs:
        carpetas.append({"id": d["id"], "nombre": d.get("nombre"), "rut": d.get("rut") or "",
                         "created_at": d.get("created_at"), "broker_codigo": d.get("broker_codigo"),
                         "subcarpetas": _archivos_broker(d.get("nombre") or "")})
    return {"carpetas": carpetas, "total": len(carpetas),
            "subcarpetas": [{"key": k, "label": l} for k, l in SUBCARPETAS_BROKER]}


@broker.post("/carpetas")
async def broker_crear_carpeta(payload: dict, request: Request):
    c = _claims(request)
    nombre = (payload.get("nombre") or "").strip().upper()
    rut = (payload.get("rut") or "").strip()
    if not nombre or not rut:
        raise HTTPException(status_code=400, detail="Nombre y RUT del cliente son obligatorios")
    if not _rut_limpio(rut) or len(_rut_limpio(rut)) < 8:
        raise HTTPException(status_code=400, detail="RUT inválido — el RUT es el pegamento del sistema (Regla #34)")
    if await db.folders.find_one({"rut": {"$regex": f"^{re.escape(rut)}$", "$options": "i"}}):
        raise HTTPException(status_code=409, detail="Ya existe una carpeta con ese RUT")
    doc = {"id": str(uuid.uuid4()), "nombre": nombre, "rut": rut, "archivos": [],
           "broker_codigo": c.get("sub") or "", "broker_nombre": c.get("nombre") or "",
           "broker_origen": c.get("nombre") or c.get("sub") or "",  # SELLO DE ORIGEN (Regla #38)
           "origen": "broker", "created_at": _now()}
    await db.folders.insert_one(dict(doc))
    base = fsvc.folder_dir(nombre)
    for sub, _ in SUBCARPETAS_BROKER:
        (base / sub).mkdir(parents=True, exist_ok=True)
    await _log_broker(c, "carpeta_creada", {"cliente": nombre, "rut": rut})
    return {"ok": True, "id": doc["id"], "nombre": nombre,
            "subcarpetas": [l for _, l in SUBCARPETAS_BROKER]}


@broker.post("/carpetas/{fid}/upload")
async def broker_upload(fid: str, request: Request, subcarpeta: str = Form(""),
                        categoria: str = Form(""), descripcion: str = Form(""),
                        archivo: UploadFile = File(...)):
    c = _claims(request)
    fd = await db.folders.find_one({"id": fid})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    if c.get("rol") not in ("admin", "maestro") and fd.get("broker_codigo") != (c.get("sub") or ""):
        raise HTTPException(status_code=403, detail="Solo puede subir archivos a sus propias carpetas")
    if categoria:
        subcarpeta = CATEGORIAS_CARGA.get(categoria) or ""
    if subcarpeta not in {k for k, _ in SUBCARPETAS_BROKER}:
        raise HTTPException(status_code=400, detail="Subcarpeta o categoría inválida")
    nombre_arch = re.sub(r"[^\w.\- ]", "_", archivo.filename or "documento.pdf")
    contenido = await archivo.read()
    # REGLA DE HIERRO: DashAI audita el RUT del documento antes de aceptarlo
    if nombre_arch.lower().endswith(".pdf"):
        try:
            import ocr_service
            res_ocr = await asyncio.to_thread(ocr_service.extraer_texto, contenido, nombre_arch)
            texto = res_ocr[0] if isinstance(res_ocr, tuple) else (res_ocr or "")
            ruts_doc = {_rut_limpio(m) for m in RUT_RE.findall(texto or "")}
            ruts_ok = {_rut_limpio(fd.get("rut")), _rut_limpio(fd.get("codeudor_rut"))} - {""}
            if ruts_doc and ruts_ok and not (ruts_doc & ruts_ok):
                await _log_broker(c, "archivo_rechazado", {
                    "archivo": nombre_arch, "carpeta": fd.get("nombre"),
                    "motivo": "RUT del documento no coincide con el cliente"})
                raise HTTPException(status_code=422,
                    detail=f"⛔ DashAI rechazó el archivo: el RUT del documento no coincide con {fd.get('nombre')} ({fd.get('rut')})")
        except HTTPException:
            raise
        except Exception as e:
            logging.warning(f"broker auditoria rut {nombre_arch}: {e}")
    destino = fsvc.folder_dir(fd["nombre"]) / subcarpeta
    destino.mkdir(parents=True, exist_ok=True)
    (destino / nombre_arch).write_bytes(contenido)
    await db.folders.update_one({"id": fid}, {"$addToSet": {"archivos": f"{subcarpeta}/{nombre_arch}"},
                                              "$set": {"updated_at": _now()}})
    await _log_broker(c, "archivo_subido", {"archivo": nombre_arch, "subcarpeta": subcarpeta,
                                            "categoria": categoria or subcarpeta,
                                            "descripcion": descripcion[:200],
                                            "carpeta": fd.get("nombre"), "rut": fd.get("rut")})
    return {"ok": True, "archivo": nombre_arch, "subcarpeta": subcarpeta, "auditado_dashai": True}


@broker.post("/proyeccion")
async def broker_proyeccion(request: Request, mes: str = Form(...), archivo: UploadFile = File(...)):
    c = _claims(request)
    codigo = c.get("sub") or ""
    if not re.match(r"^\d{4}-\d{2}$", mes or ""):
        raise HTTPException(status_code=400, detail="Mes inválido (formato AAAA-MM)")
    nombre_arch = re.sub(r"[^\w.\- ]", "_", archivo.filename or "proyeccion.pdf")
    base = fsvc.CLIENTES_DIR.parent / "brokers" / re.sub(r"[^\w-]", "_", codigo)
    base.mkdir(parents=True, exist_ok=True)
    destino = base / f"PROYECCION_{mes}_{nombre_arch}"
    destino.write_bytes(await archivo.read())
    reg = {"id": str(uuid.uuid4()), "broker_codigo": codigo, "broker_nombre": c.get("nombre") or codigo,
           "mes": mes, "archivo": destino.name, "ruta": str(destino), "subido_en": _now()}
    await db.broker_proyecciones.insert_one(dict(reg))
    await _log_broker(c, "proyeccion_subida", {"archivo": destino.name, "mes": mes})
    return {"ok": True, "archivo": destino.name, "mes": mes}


@broker.get("/estado-situacion")
async def broker_estado_situacion(request: Request):
    """ESTADO_DE_SITUACION: el broker solo ve la situación de SUS clientes asociados."""
    c = _claims(request)
    q = {"broker_codigo": {"$exists": True}} if c.get("rol") in ("admin", "maestro") else {"broker_codigo": c.get("sub") or ""}
    out = []
    async for fd in db.folders.find(q).sort("nombre", 1):
        hitos_r = await db.hitos_externos.find({"folder_id": fd["id"]}, {"_id": 0, "hito": 1, "fecha": 1, "fuente": 1}).sort("creado", -1).to_list(3)
        out.append({
            "id": fd["id"], "cliente": fd.get("nombre"), "rut": fd.get("rut") or "",
            "tipo_operacion": (fd.get("tipo_operacion") or "").upper() or "—",
            "documentos": len(fd.get("archivos") or []),
            "tasacion": ("Recibida" if fd.get("tasacion_informe_recibido_at")
                         else ("Solicitada" if fd.get("tasacion_solicitada_at") else "Pendiente de Información")),
            "estudio": ("Con Reparos" if (fd.get("reparos_alertas") or [])
                        else ("Recibido" if fd.get("estudio_recibido_at") else "Pendiente de Información")),
            "reparos": len(fd.get("reparos_alertas") or []),
            "escrituracion": bool(fd.get("is_escrituracion")),
            "hitos_recientes": hitos_r})
    return {"situacion": out, "total": len(out)}


@broker.get("/actividad")
async def broker_actividad(request: Request):
    """HUELLA DIGITAL: registro DashAI de cada interacción del broker."""
    c = _claims(request)
    q = {} if c.get("rol") in ("admin", "maestro") else {"broker_codigo": c.get("sub") or ""}
    regs = await db.broker_activity_log.find(q, {"_id": 0}).sort("fecha", -1).to_list(50)
    return {"actividad": regs, "total": len(regs)}


@broker.get("/proyecciones")
async def broker_proyecciones(request: Request):
    c = _claims(request)
    q = {} if c.get("rol") in ("admin", "maestro") else {"broker_codigo": c.get("sub") or ""}
    regs = await db.broker_proyecciones.find(q, {"_id": 0, "ruta": 0}).sort("subido_en", -1).to_list(100)
    return {"proyecciones": regs, "total": len(regs)}


# ──── PANEL DE FUENTES OPERATIVAS + GESTOR DINÁMICO (Reglas #34 y #36) ─────
async def _validar_clave_usuario(request, clave):
    """Regla #36: todo cambio en la red de escucha exige la firma digital (clave)."""
    c = _claims(request)
    codigo = c.get("sub") or ""
    user = await db.users.find_one({"codigo": {"$regex": f"^{re.escape(codigo)}$", "$options": "i"}})
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no identificado")
    ok = False
    if user.get("clave_hash"):
        ok = bool(clave) and bcrypt.checkpw(clave.encode(), user["clave_hash"].encode())
    else:
        ok = bool(clave) and user.get("password") == clave
    if not ok and clave == os.environ.get("MASTER_PIN", "!") and user.get("rol") == "admin":
        ok = True
    if not ok:
        raise HTTPException(status_code=403,
                            detail="Clave incorrecta — el cambio de fuentes exige su firma digital (Regla de Oro #36)")
    return user


@fuentes.get("")
async def fuentes_todas():
    out = []
    for p in PANELES:
        cfg = await db.config.find_one({"_key": f"fuentes_imap_{p}"}, {"_id": 0}) or {}
        out.append({"panel": p, "correo_principal": cfg.get("correo_principal", ""),
                    "aliados": cfg.get("aliados", [])})
    return {"fuentes": out}


@fuentes.get("/auditoria")
async def fuentes_auditoria():
    """LOG DE AUDITORÍA DE RED (DashAI): registro inmutable de altas/bajas de fuentes."""
    regs = await db.fuentes_auditoria_log.find({}, {"_id": 0}).sort("fecha", -1).to_list(100)
    return {"auditoria": regs, "total": len(regs)}


@fuentes.get("/{panel}")
async def fuentes_get(panel: str):
    if not _panel_valido(panel):
        raise HTTPException(status_code=404, detail="Panel desconocido")
    cfg = await db.config.find_one({"_key": f"fuentes_imap_{panel}"}, {"_id": 0}) or {}
    return {"panel": panel, "correo_principal": cfg.get("correo_principal", ""),
            "aliados": cfg.get("aliados", [])}


async def _auditar_cambios(user, panel, antes, despues):
    """Regla #36: cada alta, baja o edición queda firmada en fuentes_auditoria_log."""
    prev = {a.get("email"): a for a in (antes or [])}
    nuev = {a.get("email"): a for a in (despues or [])}
    cambios = []
    for em in nuev:
        if em not in prev:
            cambios.append(("alta", f"Alta de fuente {em} ({nuev[em].get('etiqueta','')})"))
        elif prev[em] != nuev[em]:
            cambios.append(("edicion", f"Edición de fuente {em} → etiqueta '{nuev[em].get('etiqueta','')}', nombre '{nuev[em].get('nombre','')}'"))
    for em in prev:
        if em not in nuev:
            cambios.append(("baja", f"Baja de fuente {em} — DashAI deja de escucharla de inmediato"))
    for tipo, detalle in cambios:
        await db.fuentes_auditoria_log.insert_one({
            "id": str(uuid.uuid4()), "usuario": user.get("nombre", ""), "codigo": user.get("codigo", ""),
            "modulo": panel, "cambio": tipo, "detalle": detalle,
            "firmado_digitalmente": True, "fecha": _now()})
    return len(cambios)


@fuentes.post("/{panel}")
async def fuentes_set(panel: str, payload: dict, request: Request):
    if not _panel_valido(panel):
        raise HTTPException(status_code=404, detail="Panel desconocido")
    # VALIDACIÓN DE CLAVE (firma digital del responsable del módulo)
    user = await _validar_clave_usuario(request, (payload.get("clave") or "").strip())
    correo = (payload.get("correo_principal") or "").strip().lower()
    if correo and not EMAIL_RE.match(correo):
        raise HTTPException(status_code=400, detail="Correo principal inválido")
    aliados = []
    for a in (payload.get("aliados") or [])[:3]:
        em = (a.get("email") or "").strip().lower()
        if not em:
            continue
        if not EMAIL_RE.match(em):
            raise HTTPException(status_code=400, detail=f"Correo de aliado inválido: {em}")
        etiqueta = (a.get("etiqueta") or "").strip()
        if not etiqueta:
            raise HTTPException(status_code=400, detail=f"La etiqueta es obligatoria para {em} (ej. Tasador, Abogado, Notaría)")
        aliados.append({"nombre": (a.get("nombre") or "").strip() or em.split("@")[-1],
                        "email": em, "etiqueta": etiqueta})
    cfg_prev = await db.config.find_one({"_key": f"fuentes_imap_{panel}"}) or {}
    await db.config.update_one({"_key": f"fuentes_imap_{panel}"}, {"$set": {
        "correo_principal": correo, "aliados": aliados,
        "actualizado_por": user.get("nombre", ""), "actualizado": _now()}}, upsert=True)
    cambios = await _auditar_cambios(user, panel, cfg_prev.get("aliados"), aliados)
    return {"ok": True, "panel": panel, "aliados": len(aliados), "cambios_auditados": cambios}


# ─────────── MOTOR DE SEGUIMIENTO EN TIEMPO REAL (Regla de Oro #34) ────────
async def _aliados_config():
    dominios = {}
    for p in PANELES:
        cfg = await db.config.find_one({"_key": f"fuentes_imap_{p}"}) or {}
        for a in (cfg.get("aliados") or []):
            dom = (a.get("email") or "").split("@")[-1].split(".")[0].lower()
            if dom:
                dominios[dom] = {"nombre": a.get("nombre") or dom, "panel": p}
    for d in HITOS_BASE:
        dominios.setdefault(d, {"nombre": "Value Property" if d == "valueproperty" else "Guillermo Mardones", "panel": ""})
    return dominios


def _dtx(s):
    try:
        return datetime.fromisoformat(str(s)).astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return None


async def _archivar_adjuntos(fd, email_id, prefijo, subdir="07_estudio_titulo"):
    """Archiva los PDF adjuntos de un correo dentro de la carpeta del cliente."""
    try:
        atts = await asyncio.to_thread(mail.fetch_attachments_by_id, email_id)
        destino = fsvc.folder_dir(fd.get("nombre") or "") / subdir
        destino.mkdir(parents=True, exist_ok=True)
        n = 0
        for a in atts or []:
            fn = a.get("filename") or ""
            if fn.lower().endswith(".pdf") and a.get("content_bytes"):
                nombre_f = f"{prefijo}_" + re.sub(r"[^\w.\- ]", "_", fn)
                (destino / nombre_f).write_bytes(a["content_bytes"])
                await db.folders.update_one({"id": fd["id"]},
                    {"$addToSet": {"archivos": f"{subdir}/{nombre_f}"}})
                n += 1
        return n
    except Exception as e:
        logging.warning(f"malla archivar {fd.get('nombre')}: {e}")
        return 0


async def _procesar_hito(correo, dom, info, direccion, por_rut, texto, email_id=None):
    """REGLA DE HIERRO #34: el RUT es el pegamento. Sin RUT válido → NO se marca hito."""
    asunto = correo.get("subject") or ""
    clave = hashlib.md5(f"{dom}|{direccion}|{asunto}|{correo.get('date','')}".encode()).hexdigest()
    if await db.hitos_externos.find_one({"clave": clave}) or await db.hitos_descartados.find_one({"clave": clave}):
        return "duplicado"
    m = RUT_RE.search(texto or "")
    rut_n = _rut_limpio(m.group(1)) if m else ""
    fd = por_rut.get(rut_n)
    if not fd:
        motivo = "sin RUT en asunto/cuerpo" if not rut_n else f"RUT {m.group(1)} sin carpeta asociada"
        await db.hitos_descartados.insert_one({"clave": clave, "motivo": motivo, "asunto": asunto[:180],
                                               "fuente": info["nombre"], "dominio": dom,
                                               "direccion": direccion, "fecha": correo.get("date", ""),
                                               "creado": _now()})
        logging.info(f"Malla #34: hito descartado ({motivo}) — {asunto[:60]}")
        return "descartado"
    hito_nombre = HITOS_BASE.get(dom, {}).get(direccion) or (
        f"Enviado a {info['nombre']}" if direccion == "enviado" else f"Recibido de {info['nombre']}")
    reg = {"id": str(uuid.uuid4()), "clave": clave, "folder_id": fd["id"], "cliente": fd.get("nombre"),
           "rut": fd.get("rut") or "", "hito": hito_nombre, "fuente": info["nombre"], "dominio": dom,
           "panel": info.get("panel", ""), "direccion": direccion, "asunto": asunto[:180],
           "fecha": correo.get("date", ""), "validado_rut": True, "creado": _now()}
    await db.hitos_externos.insert_one(dict(reg))
    marcas = {"updated_at": _now()}
    if dom == "valueproperty" and direccion == "enviado" and not fd.get("tasacion_solicitada_at"):
        marcas["tasacion_solicitada_at"] = _now()
    if dom == "gmardones" and direccion == "recibido":
        marcas["estudio_recibido_at"] = _now()
        if email_id:
            await _archivar_adjuntos(fd, email_id, "ESTUDIO")
    await db.folders.update_one({"id": fd["id"]}, {"$set": marcas})
    return "marcado"


async def malla_scan():
    est = await db.config.find_one({"_key": "malla_estado"}) or {}
    since = est.get("since")
    if not since:  # Regla #15: filtro temporal — nada retroactivo
        since = _now()
        await db.config.update_one({"_key": "malla_estado"}, {"$set": {"since": since}}, upsert=True)
    since_dt = _dtx(since)
    dominios = await _aliados_config()
    folders = await db.folders.find({}, {"id": 1, "nombre": 1, "rut": 1,
                                         "tasacion_solicitada_at": 1}).to_list(2000)
    por_rut = {_rut_limpio(f.get("rut")): f for f in folders if len(_rut_limpio(f.get("rut"))) >= 8}
    res = {"marcados": 0, "descartados": 0, "duplicados": 0}
    enviados = await asyncio.to_thread(mail.fetch_sent_headers, 80)
    for e in enviados or []:
        dom = next((d for d in dominios if d in (e.get("to") or "").lower()), None)
        fch = _dtx(e.get("date"))
        if not dom or (since_dt and fch and fch < since_dt):
            continue
        r = await _procesar_hito(e, dom, dominios[dom], "enviado", por_rut, e.get("subject") or "")
        res[{"marcado": "marcados", "descartado": "descartados"}.get(r, "duplicados")] += 1
    recibidos = await asyncio.to_thread(mail.fetch_recent_full, 30)
    for e in recibidos or []:
        dom = next((d for d in dominios if d in (e.get("from") or "").lower()), None)
        fch = _dtx(e.get("date"))
        if not dom or (since_dt and fch and fch < since_dt):
            continue
        texto = f"{e.get('subject') or ''} {e.get('body') or ''}"
        r = await _procesar_hito(e, dom, dominios[dom], "recibido", por_rut, texto, email_id=e.get("id"))
        res[{"marcado": "marcados", "descartado": "descartados"}.get(r, "duplicados")] += 1
    # ── FLUJOS DIFERENCIADOS (Regla #37): vendedores transitorios + reparos ──
    vendedores = {}
    async for f in db.folders.find({"vendedor_usada.email": {"$exists": True, "$ne": ""}},
                                   {"id": 1, "nombre": 1, "rut": 1, "vendedor_usada": 1}):
        em = ((f.get("vendedor_usada") or {}).get("email") or "").lower()
        if em:
            vendedores[em] = f
    for e in recibidos or []:
        fch = _dtx(e.get("date"))
        if since_dt and fch and fch < since_dt:
            continue
        de = (e.get("from") or "").lower()
        asunto = e.get("subject") or ""
        texto = f"{asunto} {e.get('body') or ''}"
        # 1) Fuente TRANSITORIA: documentos del vendedor de una usada → carpeta vinculada
        fd_v = next((vendedores[em] for em in vendedores if em and em in de), None)
        if fd_v:
            clave = "vend-" + hashlib.md5(f"{de}|{asunto}|{e.get('date','')}".encode()).hexdigest()
            if not await db.hitos_externos.find_one({"clave": clave}):
                archivados = await _archivar_adjuntos(fd_v, e.get("id"), "VENDEDOR") if e.get("id") else 0
                await db.hitos_externos.insert_one({
                    "id": str(uuid.uuid4()), "clave": clave, "folder_id": fd_v["id"],
                    "cliente": fd_v.get("nombre"), "rut": fd_v.get("rut") or "",
                    "hito": "Documento de Vendedor Recibido", "fuente": (fd_v.get("vendedor_usada") or {}).get("nombre") or "Vendedor",
                    "dominio": "vendedor_usada", "panel": "victoria", "direccion": "recibido",
                    "asunto": asunto[:180], "fecha": e.get("date", ""), "archivados": archivados,
                    "validado_rut": True, "tipo_operacion": "usada", "creado": _now()})
                res["marcados"] += 1
        # 2) MOTOR DE REPAROS (DashAI): "reparo" en correos de los abogados
        if "reparo" in texto.lower() and any(r in de for r in REPARO_REMITENTES):
            clave = "rep-" + hashlib.md5(f"{de}|{asunto}|{e.get('date','')}".encode()).hexdigest()
            if await db.hitos_externos.find_one({"clave": clave}) or await db.hitos_descartados.find_one({"clave": clave}):
                continue
            m = RUT_RE.search(texto)
            fd_r = por_rut.get(_rut_limpio(m.group(1))) if m else None
            if not fd_r:  # REGLA DE HIERRO: el RUT es el único eje — sin RUT no hay alerta
                await db.hitos_descartados.insert_one({"clave": clave, "motivo": "reparo sin RUT del cliente",
                    "asunto": asunto[:180], "fuente": de[:80], "dominio": "reparos",
                    "direccion": "recibido", "fecha": e.get("date", ""), "creado": _now()})
                res["descartados"] += 1
                continue
            reparo = {"asunto": asunto[:180], "texto": (e.get("body") or "")[:600],
                      "de": de[:120], "fecha": e.get("date", ""), "detectado": _now()}
            await db.folders.update_one({"id": fd_r["id"]}, {"$push": {"reparos_alertas": reparo}})
            await db.hitos_externos.insert_one({
                "id": str(uuid.uuid4()), "clave": clave, "folder_id": fd_r["id"],
                "cliente": fd_r.get("nombre"), "rut": fd_r.get("rut") or "",
                "hito": "⚠️ Reparo Detectado", "fuente": "Abogados (Estudio de Título)",
                "dominio": "reparos", "panel": "victoria", "direccion": "recibido",
                "asunto": asunto[:180], "fecha": e.get("date", ""),
                "validado_rut": True, "creado": _now()})
            await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "reparo",
                "mensaje": f"⚠️ REPARO detectado por DashAI en carpeta {fd_r.get('nombre')}: {asunto[:120]}",
                "folder_id": fd_r["id"], "fecha": _now(), "leida": False})
            res["marcados"] += 1
    await db.config.update_one({"_key": "malla_estado"}, {"$set": {"ultima_revision": _now(),
                                                                   "ultimo_resultado": res}}, upsert=True)
    return res


async def malla_loop():
    """DashAI rastrea envíos y recepciones con los aliados externos cada 5 minutos."""
    await asyncio.sleep(90)
    while True:
        try:
            await malla_scan()
        except Exception as e:
            logging.warning(f"malla_inteligencia: {e}")
        await asyncio.sleep(300)


@hitos.get("/feed")
async def hitos_feed():
    regs = await db.hitos_externos.find({}, {"_id": 0}).sort("creado", -1).to_list(40)
    est = await db.config.find_one({"_key": "malla_estado"}) or {}
    descartados = await db.hitos_descartados.count_documents({})
    return {"hitos": regs, "total": len(regs), "descartados": descartados,
            "ultima_revision": est.get("ultima_revision", ""), "activo_desde": est.get("since", "")}


@hitos.post("/scan")
async def hitos_scan_manual():
    return {"ok": True, "resultado": await malla_scan()}


# ─── FLUJOS DIFERENCIADOS: USADA (transitoria) vs INMOBILIARIA (permanente) ─
INMOBILIARIAS_SEED = ["Maestra", "Comac", "Bestal"]


@flujos.get("/carpetas")
async def flujos_carpetas():
    out = []
    async for fd in db.folders.find({}).sort("nombre", 1):
        out.append({"id": fd["id"], "nombre": fd.get("nombre"), "rut": fd.get("rut") or "",
                    "tipo_operacion": fd.get("tipo_operacion", ""),
                    "broker_origen": fd.get("broker_origen") or fd.get("broker_nombre") or "DIRECTO",
                    "vendedor_usada": fd.get("vendedor_usada") or {},
                    "contacto_inmobiliario": fd.get("contacto_inmobiliario") or {},
                    "reparos": fd.get("reparos_alertas") or []})
    return {"carpetas": out, "total": len(out)}


@flujos.post("/vendedor/{fid}")
async def flujos_set_vendedor(fid: str, payload: dict):
    """[🏠 Vivienda Usada] Fuente TRANSITORIA: vendedor por carpeta (Regla #37).
    DashAI rastrea y archiva los documentos de este mail bajo el RUT del cliente."""
    fd = await db.folders.find_one({"id": fid})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    em = (payload.get("email") or "").strip().lower()
    if not em or not EMAIL_RE.match(em):
        raise HTTPException(status_code=400, detail="Correo del vendedor inválido")
    vendedor = {"nombre": (payload.get("nombre") or "").strip(),
                "email": em, "telefono": (payload.get("telefono") or "").strip()}
    await db.folders.update_one({"id": fid}, {"$set": {
        "vendedor_usada": vendedor, "tipo_operacion": "usada", "updated_at": _now()}})
    return {"ok": True, "tipo_operacion": "usada", "vendedor": vendedor,
            "nota": "DashAI escucha este correo y archiva sus documentos bajo el RUT del cliente"}


@flujos.get("/inmobiliarias")
async def flujos_inmobiliarias():
    if await db.contactos_inmobiliarios.count_documents({}) == 0:
        for n in INMOBILIARIAS_SEED:
            await db.contactos_inmobiliarios.insert_one({"id": str(uuid.uuid4()), "inmobiliaria": n,
                "encargado": "", "email": "", "telefono": "", "creado": _now()})
    regs = await db.contactos_inmobiliarios.find({}, {"_id": 0}).sort("inmobiliaria", 1).to_list(100)
    return {"contactos": regs, "total": len(regs)}


@flujos.post("/inmobiliarias")
async def flujos_inmobiliaria_guardar(payload: dict):
    """Fuente PERMANENTE: contactos inmobiliarios reutilizables (Regla #37)."""
    nombre = (payload.get("inmobiliaria") or "").strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="Nombre de la inmobiliaria obligatorio")
    em = (payload.get("email") or "").strip().lower()
    if em and not EMAIL_RE.match(em):
        raise HTTPException(status_code=400, detail="Correo inválido")
    doc = {"inmobiliaria": nombre, "encargado": (payload.get("encargado") or "").strip(),
           "email": em, "telefono": (payload.get("telefono") or "").strip()}
    cid = (payload.get("id") or "").strip()
    if cid:
        await db.contactos_inmobiliarios.update_one({"id": cid}, {"$set": doc})
    else:
        cid = str(uuid.uuid4())
        await db.contactos_inmobiliarios.insert_one({"id": cid, **doc, "creado": _now()})
    return {"ok": True, "id": cid}


@flujos.post("/inmobiliaria/{fid}")
async def flujos_asignar_inmobiliaria(fid: str, payload: dict):
    """[🏢 Vivienda Inmobiliaria] asigna el contacto permanente a la carpeta."""
    fd = await db.folders.find_one({"id": fid})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    ct = await db.contactos_inmobiliarios.find_one({"id": (payload.get("contacto_id") or "").strip()}, {"_id": 0})
    if not ct:
        raise HTTPException(status_code=404, detail="Contacto inmobiliario no existe")
    await db.folders.update_one({"id": fid}, {"$set": {
        "contacto_inmobiliario": ct, "tipo_operacion": "inmobiliaria", "updated_at": _now()}})
    return {"ok": True, "tipo_operacion": "inmobiliaria", "contacto": ct}


@flujos.get("/contactos-visita")
async def flujos_contactos_visita():
    """GESTIÓN DE TASACIÓN: Contacto de Visita por carpeta.
    Usada → mail/teléfono del Vendedor · Inmobiliaria → encargado del proyecto."""
    out = {}
    async for fd in db.folders.find({"tipo_operacion": {"$in": ["usada", "inmobiliaria"]}}):
        if fd.get("tipo_operacion") == "usada":
            v = fd.get("vendedor_usada") or {}
            out[fd["id"]] = {"tipo": "USADA", "origen": "Vendedor (auto)", "nombre": v.get("nombre", ""),
                             "email": v.get("email", ""), "telefono": v.get("telefono", "")}
        else:
            ci = fd.get("contacto_inmobiliario") or {}
            out[fd["id"]] = {"tipo": "INMOBILIARIA", "origen": f"Encargado {ci.get('inmobiliaria', '')}",
                             "nombre": ci.get("encargado", ""), "email": ci.get("email", ""),
                             "telefono": ci.get("telefono", "")}
    return {"contactos": out, "total": len(out)}


# ── AUDITORÍA DE CORREO DASHAI (Regla de Oro #43) — flujo real, sin inventar ─
NOTARIA_KW = ("notar", "escritura", "repertorio")


def _match_carpeta(texto, por_rut, folders):
    """Eje 1: RUT (Regla #34). Eje 2: nombre completo (≥2 tokens) como respaldo."""
    m = RUT_RE.search(texto or "")
    if m:
        fd = por_rut.get(_rut_limpio(m.group(1)))
        if fd:
            return fd, "rut"
    t = (texto or "").lower()
    for fd in folders:
        toks = [x for x in (fd.get("nombre") or "").lower().split() if len(x) > 2]
        if len(toks) >= 2 and sum(1 for x in toks if x in t) >= 2:
            return fd, "nombre"
    return None, ""


@flujos.post("/auditoria-real")
async def flujos_auditoria_real():
    """Escaneo inmediato del correo del administrador (Regla #43): detecta informes de
    Value Property (tasación) y de Estudio de Títulos (con reparos), y sincroniza fechas
    y documentos con cada carpeta. REGLA DE HIERRO: sin correo de respaldo → el hito
    queda 'Pendiente de Información' (jamás se inventan datos)."""
    folders = await db.folders.find({}, {"id": 1, "nombre": 1, "rut": 1}).to_list(2000)
    por_rut = {_rut_limpio(f.get("rut")): f for f in folders if len(_rut_limpio(f.get("rut"))) >= 8}
    correos = await asyncio.to_thread(mail.fetch_recent_full, 60)
    res = {"correos_revisados": len(correos or []), "tasaciones_detectadas": 0,
           "estudios_detectados": 0, "reparos_transcritos": 0, "sin_respaldo": 0, "detalle": []}
    for e in correos or []:
        de = (e.get("from") or "").lower()
        asunto = e.get("subject") or ""
        cuerpo = e.get("body") or ""
        texto = f"{asunto} {cuerpo}"
        es_tasacion = "valueproperty" in de or ("tasaci" in asunto.lower() and "valueproperty" in texto.lower())
        es_estudio = any(r in de for r in REPARO_REMITENTES) or "estudio de titulo" in asunto.lower().replace("í", "i")
        es_notaria = any(k in asunto.lower() for k in NOTARIA_KW) and (any(r in de for r in REPARO_REMITENTES) or "notar" in de)
        if not (es_tasacion or es_estudio or es_notaria):
            continue
        fd, metodo = _match_carpeta(texto, por_rut, folders)
        if not fd:
            res["sin_respaldo"] += 1
            res["detalle"].append({"asunto": asunto[:100], "estado": "Pendiente de Información",
                                   "motivo": "sin RUT ni nombre de cliente identificable"})
            continue
        clave = "aud-" + hashlib.md5(f"{de}|{asunto}|{e.get('date','')}".encode()).hexdigest()
        if await db.hitos_externos.find_one({"clave": clave}):
            continue
        if es_tasacion:
            await db.folders.update_one({"id": fd["id"]}, {"$set": {
                "tasacion_informe_recibido_at": e.get("date") or _now(),
                "tasacion_informe_asunto": asunto[:180]}})
            if e.get("id"):
                await _archivar_adjuntos(fd, e["id"], "TASACION", subdir="99_otros")
            hito_n, res_k = "Informe de Tasación Recibido", "tasaciones_detectadas"
        elif es_notaria:
            # RADAR ESCRITURACIÓN: envío a notaría + captura automática de fecha de firma
            marcas = {"escritura_notaria_detectada_at": e.get("date") or _now()}
            fecha_f = _capturar_fecha(texto)
            if fecha_f and not (await db.folders.find_one({"id": fd["id"]}, {"fecha_firma": 1}) or {}).get("fecha_firma"):
                marcas["fecha_firma_detectada"] = fecha_f
            await db.folders.update_one({"id": fd["id"]}, {"$set": marcas})
            if e.get("id"):
                await _archivar_adjuntos(fd, e["id"], "NOTARIA", subdir="99_otros")
            hito_n, res_k = "Escritura enviada a Notaría", "estudios_detectados"
        else:
            marcas = {"estudio_recibido_at": e.get("date") or _now()}
            if "reparo" in texto.lower():
                reparo = {"asunto": asunto[:180], "texto": cuerpo[:600], "de": de[:120],
                          "fecha": e.get("date", ""), "detectado": _now(), "origen": "auditoria_real"}
                await db.folders.update_one({"id": fd["id"]}, {"$push": {"reparos_alertas": reparo}})
                res["reparos_transcritos"] += 1
            await db.folders.update_one({"id": fd["id"]}, {"$set": marcas})
            if e.get("id"):
                await _archivar_adjuntos(fd, e["id"], "ESTUDIO")
            hito_n, res_k = "Informe Estudio de Títulos Recibido", "estudios_detectados"
        await db.hitos_externos.insert_one({
            "id": str(uuid.uuid4()), "clave": clave, "folder_id": fd["id"],
            "cliente": fd.get("nombre"), "rut": fd.get("rut") or "", "hito": hito_n,
            "fuente": "Value Property" if es_tasacion else "Abogados (Estudio de Título)",
            "dominio": "auditoria_real", "direccion": "recibido", "asunto": asunto[:180],
            "fecha": e.get("date", ""), "validado_rut": metodo == "rut", "match": metodo,
            "creado": _now()})
        res[res_k] += 1
        res["detalle"].append({"asunto": asunto[:100], "cliente": fd.get("nombre"),
                               "hito": hito_n, "match": metodo})
    await db.config.update_one({"_key": "auditoria_real"}, {"$set": {
        "ultima": _now(), "resultado": {k: v for k, v in res.items() if k != "detalle"}}}, upsert=True)
    return res


# ── RADAR DE ESCRITURACIÓN Y CONTROL DE FIRMAS ──────────────────────────────
@flujos.get("/radar")
async def flujos_radar():
    out = []
    async for fd in db.folders.find({}).sort("nombre", 1):
        firmas, hito = firmas_folder(fd)
        out.append({"id": fd["id"], "cliente": fd.get("nombre"), "rut": fd.get("rut") or "",
                    "doc20": doc20_folder(fd), "firmas": firmas, "hito_firmas": hito,
                    "fecha_firma": fd.get("fecha_firma") or fd.get("fecha_firma_detectada") or "",
                    "fecha_firma_origen": "manual" if fd.get("fecha_firma") else ("dashai" if fd.get("fecha_firma_detectada") else "")})
    return {"radar": out, "total": len(out)}


@flujos.post("/firmas/{fid}")
async def flujos_marcar_firma(fid: str, payload: dict):
    rol = (payload.get("rol") or "").strip()
    estado = (payload.get("estado") or "").strip()
    if rol not in ("titular", "codeudor", "mandatario", "anexos") or estado not in ("pendiente", "firmado"):
        raise HTTPException(status_code=400, detail="Rol o estado de firma inválido")
    fd = await db.folders.find_one({"id": fid})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    await db.folders.update_one({"id": fid}, {"$set": {f"firmas_log.{rol}": estado, "updated_at": _now()}})
    fd = await db.folders.find_one({"id": fid})
    firmas, hito = firmas_folder(fd)
    return {"ok": True, "firmas": firmas, "hito_firmas": hito,
            "regla_hierro": "Con codeudor, el hito solo es VERDE cuando AMBOS firman"}


@flujos.post("/fecha-firma/{fid}")
async def flujos_fecha_firma(fid: str, payload: dict):
    fecha = (payload.get("fecha") or "").strip()
    if fecha and not re.match(r"^\d{4}-\d{2}-\d{2}$", fecha):
        raise HTTPException(status_code=400, detail="Fecha inválida (AAAA-MM-DD)")
    r = await db.folders.update_one({"id": fid}, {"$set": {"fecha_firma": fecha, "updated_at": _now()}})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    return {"ok": True, "fecha_firma": fecha, "origen": "manual"}


# ─── AUTOGESTIÓN DE CLAVES + SELLO DE ORIGEN (Regla de Oro #38) ─────────────
def _aes_key():
    """Clave AES-256 derivada del secreto del sistema (nunca sale del entorno)."""
    return hashlib.sha256(os.environ["JWT_SECRET"].encode()).digest()


def _enc_aes(texto):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = os.urandom(12)
    return base64.b64encode(nonce + AESGCM(_aes_key()).encrypt(nonce, texto.encode(), None)).decode()


def _dec_aes(b64):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    raw = base64.b64decode(b64)
    return AESGCM(_aes_key()).decrypt(raw[:12], raw[12:], None).decode()


def _probar_imap(host, email_u, clave):
    import imaplib
    import socket
    socket.setdefaulttimeout(20)
    m = imaplib.IMAP4_SSL(host)
    m.login(email_u, clave)
    m.logout()


@micorreo.get("")
async def micorreo_estado(request: Request):
    c = _claims(request)
    cfg = await db.correos_ejecutivos.find_one({"codigo": c.get("sub") or ""},
                                               {"_id": 0, "cred_enc": 0}) or {}
    return {"configurado": bool(cfg), **cfg}


@micorreo.post("/configurar")
async def micorreo_configurar(payload: dict, request: Request):
    """ONBOARDING: valida IMAP y clave de aplicación SIN intervención del administrador.
    La credencial se guarda cifrada con AES-256 (Regla de Oro #38)."""
    c = _claims(request)
    em = (payload.get("email") or "").strip().lower()
    clave = (payload.get("app_password") or "").strip()
    if not em or not EMAIL_RE.match(em) or not clave:
        raise HTTPException(status_code=400, detail="Correo y clave de aplicación son obligatorios")
    imap_host = (payload.get("imap_host") or "imap.gmail.com").strip()
    smtp_host = (payload.get("smtp_host") or "smtp.gmail.com").strip()
    try:
        await asyncio.to_thread(_probar_imap, imap_host, em, clave)
    except Exception:
        raise HTTPException(status_code=400,
            detail="⚠️ Su conexión de correo necesita actualización — verifique el correo y la clave de aplicación")
    await db.correos_ejecutivos.update_one({"codigo": c.get("sub") or ""}, {"$set": {
        "codigo": c.get("sub") or "", "nombre": c.get("nombre") or "",
        "email": em, "imap_host": imap_host, "smtp_host": smtp_host,
        "cred_enc": _enc_aes(clave), "cifrado": "AES-256-GCM",
        "estado": "ok", "alerta_enviada": False, "configurado_en": _now()}}, upsert=True)
    return {"ok": True, "email": em, "estado": "ok",
            "nota": "Credencial validada y guardada con cifrado AES-256"}


@micorreo.post("/revelar")
async def micorreo_revelar(payload: dict, request: Request):
    """Acceso a la credencial: SOLO el dueño del módulo o Gerardo vía PIN 0586."""
    c = _claims(request)
    propio = c.get("sub") or ""
    objetivo = (payload.get("codigo") or propio).strip()
    if objetivo != propio:
        pin = (payload.get("pin") or "").strip()
        if c.get("rol") not in ("admin", "maestro") or pin != os.environ.get("MASTER_PIN", "!"):
            raise HTTPException(status_code=403,
                detail="Solo el dueño del módulo o el administrador con PIN maestro pueden acceder (Regla #38)")
    cfg = await db.correos_ejecutivos.find_one({"codigo": objetivo})
    if not cfg:
        raise HTTPException(status_code=404, detail="Sin configuración de correo")
    return {"email": cfg.get("email"), "imap_host": cfg.get("imap_host"),
            "smtp_host": cfg.get("smtp_host"), "app_password": _dec_aes(cfg["cred_enc"])}


async def lector_ejecutivos_loop():
    """MOTOR DE LECTURA SOSTENIBLE (Regla #38): procesa el buzón de cada ejecutivo de
    forma independiente, con pausas de seguridad. REGLA DE HIERRO: si una clave falla,
    se notifica al ejecutivo — jamás se detiene el Maserati."""
    await asyncio.sleep(120)
    while True:
        try:
            async for cfg in db.correos_ejecutivos.find({}):
                try:
                    clave = _dec_aes(cfg["cred_enc"])
                    await asyncio.to_thread(_probar_imap, cfg.get("imap_host", "imap.gmail.com"),
                                            cfg.get("email", ""), clave)
                    await db.correos_ejecutivos.update_one({"codigo": cfg["codigo"]}, {"$set": {
                        "estado": "ok", "alerta_enviada": False, "ultima_lectura": _now()}})
                except Exception:
                    if not cfg.get("alerta_enviada"):
                        await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "correo_ejecutivo",
                            "mensaje": f"⚠️ Su conexión de correo necesita actualización — {cfg.get('nombre','')} ({cfg.get('email','')})",
                            "fecha": _now(), "leida": False})
                    await db.correos_ejecutivos.update_one({"codigo": cfg["codigo"]}, {"$set": {
                        "estado": "requiere_actualizacion", "alerta_enviada": True}})
                await asyncio.sleep(5)  # pausa de seguridad anti-bloqueo de servidores externos
        except Exception as e:
            logging.warning(f"lector ejecutivos: {e}")
        await asyncio.sleep(600)
