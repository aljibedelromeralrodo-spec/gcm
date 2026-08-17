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
from fastapi.responses import Response
from database import db
import email_service as mail
import folders_service as fsvc

broker = APIRouter(prefix="/broker")
fuentes = APIRouter(prefix="/fuentes")
hitos = APIRouter(prefix="/hitos")
flujos = APIRouter(prefix="/flujos")
micorreo = APIRouter(prefix="/mi-correo")
buzon = APIRouter(prefix="/buzon-aprendizaje")
supercarpeta = APIRouter(prefix="/supercarpeta")

# MOTOR DE REPAROS: remitentes de los abogados de estudio de título / escrituración
REPARO_REMITENTES = ("mardluf", "majluf", "gmardones", "olave", "ibarra",
                     "victoriavilches", "ecerda", "amvabogados")

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
# REGLA DE HIERRO: la firma SOLO se confirma con evidencia REAL en pasado (jamás agendamientos)
FIRMA_REAL_RE = re.compile(
    r"(escritura\s+(?:fue\s+)?firmad[ao]|se\s+firm[óo]\b|firmad[ao]\s+(?:la\s+)?escritura"
    r"|firma\s+(?:realizada|efectuada|concretada|exitosa)|firmaron\s+la\s+escritura"
    r"|cesi[óo]n\s+firmad[ao]|firmad[ao]\s+(?:la\s+)?cesi[óo]n)", re.I)
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


INMO_KW = {"boetsch": "Boetsch", "boetch": "Boetsch", "word": "Word", "urbanizate": "Urbanizate",
           "maestra": "Maestra", "ecomac": "Ecomac"}


def _parsear_proyeccion(ruta):
    """P11 — extrae filas (nombre, inmobiliaria, tipo, subsidio, monto UF) desde Excel/PDF/CSV."""
    filas, lineas = [], []
    suf = str(ruta).lower()
    if suf.endswith((".xlsx", ".xls")):
        import openpyxl
        wb = openpyxl.load_workbook(ruta, data_only=True)
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                lineas.append(" | ".join(str(c) for c in row if c is not None))
    elif suf.endswith(".pdf"):
        from pypdf import PdfReader
        r = PdfReader(str(ruta))
        for p in r.pages:
            lineas += (p.extract_text() or "").splitlines()
    else:
        lineas = ruta.read_text(errors="ignore").splitlines()
    nombre_re = re.compile(r"([A-ZÁÉÍÓÚÑ][a-zA-ZÁÉÍÓÚÑáéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑa-zA-Záéíóúñ]+){1,3})")
    monto_re = re.compile(r"\$?\s*(\d{1,2}[.,]\d{3}(?:[.,]\d+)?|\d{3,5})")
    for ln in lineas:
        t = ln.strip()
        if len(t) < 8:
            continue
        tl = t.lower()
        inmo = next((v for k, v in INMO_KW.items() if k in tl), "")
        usada = "usad" in tl
        monto = None
        for m in monto_re.finditer(t):
            try:
                v = float(m.group(1).replace(".", "").replace(",", "."))
                if 100 <= v <= 99999:
                    monto = v
                    break
            except Exception:
                continue
        m_n = nombre_re.search(t)
        nombre = (m_n.group(1).strip().upper() if m_n else "")
        nombre = re.sub(r"\b(CASA USADA|SIN SUBSIDIO|CON SUBSIDIO|UF)\b.*", "", nombre).strip()
        if not nombre or len(nombre.split()) < 2 or not (monto or inmo or usada):
            continue
        filas.append({"nombre": nombre, "inmobiliaria": inmo,
                      "tipo": "usada" if usada else "nueva",
                      "subsidio": ("Con Subsidio" if ("con subsidio" in tl or "ds1" in tl)
                                   else "Sin Subsidio" if "sin subsidio" in tl else ""),
                      "monto_uf": monto})
    vistos, out = set(), []
    for f in filas:
        if f["nombre"] not in vistos:
            vistos.add(f["nombre"])
            out.append(f)
    return out


async def _aplicar_proyeccion(broker_codigo, broker_nombre, mes, clientes_p):
    """P11 — CARGA AUTOMÁTICA: upsert de los clientes de la proyección en carpetas + Bóveda ADN.
    Reemplaza la lista anterior de ese broker para ese mes (sin duplicados) y alerta a Gerencia."""
    creados, actualizados, faltantes = 0, 0, []
    ahora = _now()
    nombres_nuevos = []
    for c in clientes_p:
        nombre = c["nombre"]
        nombres_nuevos.append(nombre)
        fd = await db.folders.find_one({"nombre": {"$regex": f"^{re.escape(nombre)}$", "$options": "i"}})
        setd = {"inmobiliaria": c.get("inmobiliaria") or "", "tipo_operacion": c.get("tipo") or "nueva",
                "subsidio_proyeccion": c.get("subsidio") or "", "proyeccion_uf": c.get("monto_uf"),
                "broker_origen": broker_nombre, "proyeccion_broker": broker_codigo,
                "proyeccion_mes": mes, "updated_at": ahora}
        setd = {k: v for k, v in setd.items() if v not in (None, "")}
        if fd:
            await db.folders.update_one({"id": fd["id"]},
                                        {"$set": setd, "$unset": {"oculto_supercarpeta": ""}})
            actualizados += 1
            fid = fd["id"]
        else:
            fid = str(uuid.uuid4())
            await db.folders.insert_one({"id": fid, "nombre": nombre, "rut": "", "archivos": [],
                                         "created": ahora, **setd})
            creados += 1
        if not c.get("monto_uf"):
            faltantes.append(f"{nombre}: monto UF")
        await _sync_adn(fid)
    async for f in db.folders.find({"proyeccion_broker": broker_codigo, "proyeccion_mes": mes}):
        if (f.get("nombre") or "").strip().upper() not in nombres_nuevos:
            await db.folders.update_one({"id": f["id"]}, {"$set": {"oculto_supercarpeta": {
                "en": ahora, "por": f"proyeccion_{broker_codigo}"}}})
    cfg = await db.config.find_one({"_key": "flota_agosto"}) or {}
    if cfg.get("activo") and len(nombres_nuevos) >= 5:
        await db.config.update_one({"_key": "flota_agosto"}, {"$set": {"nombres": nombres_nuevos}})
    total_uf = round(sum(c.get("monto_uf") or 0 for c in clientes_p), 1)
    meta_cfg = await db.config.find_one({"_key": "proyeccion_agosto"}) or {}
    meta_uf = meta_cfg.get("meta_uf") or 41717
    resumen = (f"📊 Proyección {mes} de {broker_nombre}: {len(clientes_p)} clientes cargados, "
               f"{total_uf} UF proyectadas (meta {meta_uf} UF). "
               + (f"⚠️ Faltan datos: {'; '.join(faltantes[:6])}. " if faltantes else "")
               + (f"⚠️ Diferencia vs meta: {round(meta_uf - total_uf, 1)} UF."
                  if abs(meta_uf - total_uf) > 0.5 else "✅ Cuadra con la meta."))
    await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "proyeccion_broker",
                                 "destino": "Gerencia Comercial", "mensaje": resumen,
                                 "fecha": ahora, "leida": False})
    return {"clientes": len(clientes_p), "creados": creados, "actualizados": actualizados,
            "total_uf": total_uf, "faltantes": faltantes, "resumen": resumen}


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
    resultado = {}
    try:
        filas = await asyncio.to_thread(_parsear_proyeccion, destino)
        if filas:
            resultado = await _aplicar_proyeccion(codigo, c.get("nombre") or codigo, mes, filas)
            await db.broker_proyecciones.update_one({"id": reg["id"]}, {"$set": {"parseo": resultado}})
    except Exception as e:
        logging.warning(f"proyeccion parse: {e}")
    await _log_broker(c, "proyeccion_subida", {"archivo": destino.name, "mes": mes})
    return {"ok": True, "archivo": destino.name, "mes": mes, "carga_automatica": resultado}


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


async def auditoria_loop():
    """REGLA DE ORO (Supercarpeta V2): actualización en tiempo real — cada 10 minutos se
    revisan los correos recientes de brokers y tasadores autorizados."""
    await asyncio.sleep(240)
    while True:
        try:
            await flujos_auditoria_real(limit=40, dias=2)
        except Exception as e:
            if "after close" in str(e):
                break
            logging.warning(f"auditoria loop: {e}")
        await asyncio.sleep(600)


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
NOTARIA_KW = ("notar", "escritura", "repertorio", "cesión", "cesion", "serie de crédito", "serie de credito", "firma confirmada")


OBS_RE = re.compile(r"(observaci[oó]n(?:es)?|reparos?)\s*[:\-\n]?\s*(.{40,900}?)(?:\n\s*\n|$)",
                    re.I | re.S)


async def _minar_reparos_pdf(fd):
    """REGLA DE MINADO: extrae el texto EXACTO de 'Observaciones'/'Reparos' desde los PDFs
    de Estudio de Títulos archivados en la Bóveda Local (celda NARANJA en la Supercarpeta)."""
    import ocr_service as _ocr
    base = fsvc.folder_dir(fd.get("nombre") or "")
    if not base.exists():
        return 0
    pdfs = sorted([p for p in base.rglob("*.pdf")
                   if "estudio" in p.name.lower() or p.parent.name == "07_estudio_titulo"],
                  key=lambda x: -x.stat().st_mtime)[:2]
    existentes = {(r.get("texto") or "")[:80] for r in (fd.get("reparos_alertas") or [])}
    nuevos = 0
    for p in pdfs:
        try:
            texto = await asyncio.to_thread(_ocr.ocr_texto, p.read_bytes(), 8) or ""
        except Exception:
            continue
        for m in OBS_RE.finditer(texto):
            exacto = re.sub(r"\s+", " ", m.group(2)).strip()[:800]
            if len(exacto) < 40 or exacto[:80] in existentes:
                continue
            reparo = {"asunto": f"Minado PDF: {p.name[:120]}", "texto": exacto,
                      "de": "minado_pdf", "fecha": _now(), "detectado": _now(),
                      "origen": "minado_pdf", "celda": "naranja", "archivo_fuente": p.name}
            await db.folders.update_one({"id": fd["id"]}, {"$push": {"reparos_alertas": reparo}})
            existentes.add(exacto[:80])
            nuevos += 1
            break  # una sección por PDF: el texto íntegro ya quedó copiado
    return nuevos


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


FUENTES_HITOS = ("tasacion", "estudio", "cesion", "set_credito", "notaria",
                 "serviu", "promesa", "carpeta_notaria", "escritura", "fecha_firma")


def _norm_fuente(x):
    if isinstance(x, dict):
        return {"correo": (x.get("correo") or "").strip().lower(),
                "nombre": (x.get("nombre") or "").strip()}
    return {"correo": str(x).strip().lower(), "nombre": ""}


def _correos_de(lst):
    return [f["correo"] for f in (_norm_fuente(x) for x in (lst or [])) if f["correo"]]


async def _fuentes_documentos_meta():
    cfg = await db.config.find_one({"_key": "fuentes_documentos"}) or {}
    fu = cfg.get("fuentes") or {}
    base = {"tasacion": [{"correo": "contacto@valueproperty.cl", "nombre": "Value Property - Tasaciones"},
                         {"correo": "contacto@valuedproperty.cl", "nombre": "Value Property - Tasaciones"}],
            "estudio": [{"correo": "victoriavilches@centralmutuos.cl", "nombre": "Victoria Vilches - Estudios"},
                        {"correo": "gmajluf@amvabogados.cl", "nombre": "Guillermo Majluf - Abogado"}]}
    out = {}
    for h in FUENTES_HITOS:
        lst = fu.get(h) if h in fu else base.get(h, [])
        out[h] = [f for f in (_norm_fuente(x) for x in (lst or [])) if f["correo"]]
    return out


async def _fuentes_documentos():
    """Regla #67 (P8): correos fuente configurables por tipo de documento (solo direcciones)."""
    meta = await _fuentes_documentos_meta()
    return {h: [f["correo"] for f in lst] for h, lst in meta.items()}


async def _sync_adn(fid):
    """Regla #67: todo cambio termina ESCRITO en la Bóveda ADN_CLIENTES_360."""
    import adn_clientes as _adn
    fd = await db.folders.find_one({"id": fid})
    if not fd:
        return False
    reg = _adn._registro_desde_folder(fd)
    reg["expediente_360"] = await _adn._expediente_360(fd)
    return await _adn._upsert_adn(reg)


def _verificar_firmas_pdf(pdf_bytes):
    """P9 — REGLA DE HIERRO: 'Set Firmado' en el asunto NO basta; debe haber evidencia
    documental de firma dentro del PDF (firma digital, texto de firma o firma manuscrita)."""
    try:
        import io
        from pypdf import PdfReader
        r = PdfReader(io.BytesIO(pdf_bytes))
        try:
            af = r.trailer["/Root"].get("/AcroForm")
            if af and int(af.get("/SigFlags", 0) or 0) >= 1:
                return True, "firma digital detectada (AcroForm/SigFlags)"
        except Exception:
            pass
        texto = " ".join((p.extract_text() or "") for p in r.pages[-3:]).lower()
        kws = ("firmado electronicamente", "firmado electrónicamente", "firma electrónica",
               "firma electronica", "e-cert", "ecert", "firmado ante notario", "firman en señal")
        if any(k in texto for k in kws):
            return True, "texto de firma electrónica dentro del documento"
        tiene_img = False
        for p in r.pages[-2:]:
            try:
                xo = (p.get("/Resources") or {}).get("/XObject")
                if xo:
                    for k in xo:
                        if xo[k].get_object().get("/Subtype") == "/Image":
                            tiene_img = True
            except Exception:
                continue
        if tiene_img and "firma" in texto:
            return True, "imagen de firma manuscrita en las últimas páginas"
        if not texto.strip():
            try:
                import ocr_service as _ocr
                texto_ocr = (_ocr.ocr_texto(pdf_bytes, 3) or "").lower()
                if any(k in texto_ocr for k in kws) or ("firma" in texto_ocr and tiene_img):
                    return True, "firma detectada vía OCR del documento escaneado"
            except Exception:
                pass
        return False, "sin evidencia verificable de firmas dentro del PDF"
    except Exception as e:
        return False, f"no se pudo abrir el PDF para verificar firmas ({str(e)[:80]})"


async def _capturar_remitente(fd, hito, e):
    """CAPTURA AUTOMÁTICA DE REMITENTES: aprende quién envía qué. Queda 'Pendiente de
    Confirmación' hasta que Gerencia lo valide (Regla de Hierro) + registro por broker."""
    try:
        de_raw = e.get("from") or ""
        m = re.search(r"[\w.+-]+@[\w.-]+", de_raw)
        if not m:
            return
        correo = m.group(0).lower()
        bloqueados = (await db.config.find_one({"_key": "remitentes_bloqueados"}) or {}).get("correos") or []
        if correo in bloqueados or correo in {a["user"].lower() for a in mail.ACCOUNTS}:
            return
        nm = re.match(r'^\s*"?([^"<]+?)"?\s*<', de_raw)
        nombre_rem = (nm.group(1).strip() if nm else correo.split("@")[0])
        apr = await db.remitentes_registro.find_one({"correo": correo}) or {}
        hito_final = apr.get("hito_forzado") or hito
        ya_fuente = correo in _correos_de((fd.get("fuentes_doc") or {}).get(hito_final))
        detectadas = (fd.get("fuentes_detectadas") or {}).get(hito_final) or []
        if not ya_fuente and not any(d.get("correo") == correo for d in detectadas):
            hoy = _now()[:10]
            await db.folders.update_one({"id": fd["id"]}, {"$push": {
                f"fuentes_detectadas.{hito_final}": {
                    "correo": correo, "nombre": nombre_rem, "primera_vez": _now(),
                    "estado": "pendiente_confirmacion",
                    "etiqueta": f"Detectado automáticamente el {hoy}"}}})
            await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "remitente_detectado",
                "mensaje": f"📡 Nuevo remitente detectado: {nombre_rem} ({correo}) agregado como fuente de "
                           f"{hito_final} para {fd.get('nombre')} — Pendiente de Confirmación.",
                "fecha": _now(), "leida": False})
        await db.remitentes_registro.update_one({"correo": correo}, {
            "$set": {"nombre": nombre_rem, "ultima": _now()},
            "$inc": {f"hitos.{hito_final}": 1,
                     f"brokers.{(fd.get('inmobiliaria') or fd.get('broker_origen') or 'sin_broker').replace('.', '·').replace('$', '')}": 1}},
            upsert=True)
    except Exception as ex:
        logging.warning(f"captura remitente: {ex}")


async def _auditar_lote(correos):
    """Procesa un lote de correos (Regla #67): detecta tasaciones (Value Property),
    estudios de títulos (Victoria Vilches / Guillermo Majluf) y notaría, y ESCRIBE
    cada hallazgo en la carpeta y en el EXPEDIENTE_360 de la Bóveda ADN.
    REGLA DE HIERRO: leer correos sin persistir el hallazgo es violación constitucional."""
    folders = await db.folders.find({}, {"id": 1, "nombre": 1, "rut": 1}).to_list(2000)
    por_rut = {_rut_limpio(f.get("rut")): f for f in folders if len(_rut_limpio(f.get("rut"))) >= 8}
    res = {"correos_revisados": len(correos or []), "tasaciones_detectadas": 0,
           "estudios_detectados": 0, "sets_detectados": 0,
           "reparos_transcritos": 0, "sin_respaldo": 0, "detalle": []}
    fu = await _fuentes_documentos()
    tas_src = [s.lower() for s in fu.get("tasacion", []) if s]
    est_src = [s.lower() for s in fu.get("estudio", []) if s]
    ces_src = [s.lower() for s in fu.get("cesion", []) if s]
    set_src = [s.lower() for s in fu.get("set_credito", []) if s]
    async for f in db.folders.find({"fuentes_doc": {"$exists": True}}, {"fuentes_doc": 1}):
        fdoc = f.get("fuentes_doc") or {}
        tas_src += _correos_de(fdoc.get("tasacion"))
        est_src += _correos_de(fdoc.get("estudio"))
        ces_src += _correos_de(fdoc.get("cesion"))
        set_src += _correos_de(fdoc.get("set_credito"))
    notaria_srcs = []
    async for f in db.folders.find({"fuentes_doc.notaria": {"$exists": True}},
                                   {"id": 1, "nombre": 1, "ciudad": 1, "fuentes_doc": 1}):
        for s in _correos_de((f.get("fuentes_doc") or {}).get("notaria")):
            notaria_srcs.append((s, f))
    for e in correos or []:
        de = (e.get("from") or "").lower()
        asunto = e.get("subject") or ""
        cuerpo = e.get("body") or ""
        texto = f"{asunto} {cuerpo}"
        # ── NOTARÍA (fuente por cliente): confirma firma de escritura + coherencia de ciudad ──
        fd_n = next((f for s, f in notaria_srcs if s in de), None)
        if fd_n:
            tx = texto.lower()
            partes = [p for p in (fd_n.get("nombre") or "").lower().split() if len(p) > 3]
            if partes and not any(p in tx for p in partes):
                continue
            setn = {"escritura_notaria_detectada_at": e.get("date") or _now()}
            hito_txt = "Actividad de notaría detectada"
            if FIRMA_REAL_RE.search(tx):
                setn["escritura_confirmada_at"] = e.get("date") or _now()
                setn["fecha_firma_detectada"] = str(e.get("date") or _now())[:10]
                hito_txt = "FIRMA DE ESCRITURA confirmada por correo de la notaría"
            ciudad = (fd_n.get("ciudad") or "").strip().lower()
            if ciudad and ciudad not in tx:
                setn["alerta_notaria_ciudad"] = True
            await db.folders.update_one({"id": fd_n["id"]}, {"$set": setn})
            await db.hitos_externos.insert_one({
                "id": str(uuid.uuid4()), "folder_id": fd_n["id"], "hito": "notaria",
                "asunto": asunto[:160], "fecha": e.get("date") or "", "fuente": "correo notaría",
                "direccion": de[:80], "creado": _now()})
            await _sync_adn(fd_n["id"])
            await _capturar_remitente(fd_n, "notaria", e)
            res["detalle"].append({"asunto": asunto[:100], "cliente": fd_n.get("nombre"),
                                   "hito": hito_txt, "match": "fuente notaría"})
            continue
        es_tasacion = ("valueproperty" in de or "valuedproperty" in de
                       or any(s in de for s in tas_src)
                       or ("tasaci" in asunto.lower()
                           and ("valueproperty" in texto.lower() or "valuedproperty" in texto.lower())))
        es_estudio = (any(r in de for r in REPARO_REMITENTES) or any(s in de for s in est_src)
                      or "estudio de titulo" in asunto.lower().replace("í", "i"))
        es_notaria = (any(s in de for s in ces_src)
                      or (any(k in asunto.lower() for k in NOTARIA_KW)
                          and (any(r in de for r in REPARO_REMITENTES) or "notar" in de)))
        asunto_l = asunto.lower()
        frase_set = "set firmado" in asunto_l or "set para la firma" in asunto_l
        es_set = frase_set and (not set_src or any(s in de for s in set_src))
        es_serviu = any(k in asunto_l for k in ("serviu", "subsidio", "resolucion", "resolución"))
        if not (es_tasacion or es_estudio or es_notaria or es_set or es_serviu):
            continue
        fd, metodo = _match_carpeta(texto, por_rut, folders)
        if not fd:
            res["sin_respaldo"] += 1
            res["detalle"].append({"asunto": asunto[:100], "estado": "Pendiente de Información",
                                   "motivo": "sin RUT ni nombre de cliente identificable"})
            continue
        hito_cap = ("tasacion" if es_tasacion else "estudio" if es_estudio else
                    "cesion" if es_notaria else "set_credito" if es_set else "serviu")
        await _capturar_remitente(fd, hito_cap, e)
        if es_serviu and not (es_tasacion or es_estudio or es_notaria or es_set):
            continue
        clave = "aud-" + hashlib.md5(f"{de}|{asunto}|{e.get('date','')}".encode()).hexdigest()
        if await db.hitos_externos.find_one({"clave": clave}):
            continue
        if es_set:
            # P9 — SET DE CRÉDITO: 'Set Para la Firma' = pendiente; 'Set Firmado' exige
            # verificación de firmas reales dentro del PDF adjunto
            if "set firmado" in asunto_l:
                firmado, evidencia = False, "sin adjunto PDF para verificar firmas"
                if e.get("id"):
                    try:
                        atts = await asyncio.to_thread(mail.fetch_attachments_by_id, e["id"])
                        for a in atts or []:
                            if (a.get("filename") or "").lower().endswith(".pdf") and a.get("content_bytes"):
                                firmado, evidencia = await asyncio.to_thread(
                                    _verificar_firmas_pdf, a["content_bytes"])
                                if firmado:
                                    break
                    except Exception as ex:
                        evidencia = f"error al abrir adjuntos ({str(ex)[:60]})"
                estado_set = "firmado" if firmado else "verificacion_pendiente"
            else:
                estado_set = "esperando_firma"
                evidencia = "asunto 'Set Para la Firma': pendiente de firma del cliente (NO firmado)"
            await db.folders.update_one({"id": fd["id"]}, {"$set": {
                "set_credito_estado": estado_set, "set_credito_asunto": asunto[:180],
                "set_credito_evidencia": evidencia, "set_credito_at": e.get("date") or _now()}})
            if e.get("id"):
                await _archivar_adjuntos(fd, e["id"], "SETCRED", subdir="99_otros")
            hito_n, res_k = f"Set de Crédito: {estado_set} ({evidencia[:80]})", "sets_detectados"
        elif es_tasacion:
            await db.folders.update_one({"id": fd["id"]}, {"$set": {
                "tasacion_informe_recibido_at": e.get("date") or _now(),
                "tasacion_informe_asunto": asunto[:180]}})
            # MOTOR DE COSECHA (Regla #64): el dato queda en DashAI, sin re-consultar IMAP
            try:
                import perfil_consolidado as _pc
                await _pc.cosechar(fd["id"], {"fecha_informe_tasacion": e.get("date") or _now()},
                                   "informe_tasacion")
            except Exception:
                pass
            if e.get("id"):
                await _archivar_adjuntos(fd, e["id"], "TASACION", subdir="99_otros")
            hito_n, res_k = "Informe de Tasación Recibido", "tasaciones_detectadas"
        elif es_notaria:
            # RADAR ESCRITURACIÓN: envío a notaría / cesión / firma serie de créditos
            marcas = {"escritura_notaria_detectada_at": e.get("date") or _now()}
            if FIRMA_REAL_RE.search(texto):
                marcas["firma_cesion_confirmada_at"] = e.get("date") or _now()
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
                # REGLA DE MINADO: si el PDF del estudio trae 'Observaciones'/'Reparos',
                # el texto EXACTO se copia a la columna Detalle de Reparos (celda naranja)
                try:
                    n_min = await _minar_reparos_pdf(fd)
                    res["reparos_transcritos"] += n_min
                except Exception as ex:
                    logging.warning(f"minado reparos pdf: {ex}")
            hito_n, res_k = "Informe Estudio de Títulos Recibido", "estudios_detectados"
        # ALERTAS DE ACCIÓN: notificación automática a la Malla (Ejecutivos A y B) + hito ✅
        try:
            await db.alertas.insert_one({
                "id": str(uuid.uuid4()), "tipo": "malla_inteligencia",
                "destino": "Ejecutivos A y B", "cliente": fd.get("nombre") or "",
                "mensaje": f"✅ {hito_n}: {fd.get('nombre')} ({fd.get('rut') or 'sin RUT'}) — "
                           f"detectado en el correo y guardado en el EXPEDIENTE_360",
                "fecha": _now(), "leida": False})
        except Exception:
            pass
        # VINCULACIÓN EXPEDIENTE_360: el hallazgo queda para siempre en la Bóveda de ADN
        try:
            import adn_clientes as _adn
            fd_full = await db.folders.find_one({"id": fd["id"]})
            if fd_full:
                reg = _adn._registro_desde_folder(fd_full)
                reg["expediente_360"] = await _adn._expediente_360(fd_full)
                await _adn._upsert_adn(reg)
        except Exception:
            pass
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
    return res


@flujos.post("/auditoria-real")
async def flujos_auditoria_real(limit: int = 60, dias: int = 0):
    """Escaneo inmediato del correo (Regla #43) sobre los correos recientes de TODAS
    las cuentas. REGLA DE HIERRO: sin correo de respaldo → el hito queda 'Pendiente
    de Información' (jamás se inventan datos)."""
    correos = await asyncio.to_thread(mail.fetch_recent_full, min(max(limit, 10), 400))
    if dias > 0:
        from datetime import timedelta
        corte = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
        correos = [e for e in (correos or []) if (e.get("date") or "9999") >= corte[:10] or not e.get("date")]
    res = await _auditar_lote(correos)
    await db.config.update_one({"_key": "auditoria_real"}, {"$set": {
        "ultima": _now(), "resultado": {k: v for k, v in res.items() if k != "detalle"}}}, upsert=True)
    return res


BARRIDO_REMITENTES = ("valueproperty", "valuedproperty", "victoriavilches", "gmajluf",
                      "amvabogados", "mardluf", "majluf", "gmardones")


@flujos.post("/barrido-forzado")
async def flujos_barrido_forzado(dias: int = 60):
    """BARRIDO FORZADO: rastrea los últimos N días en TODAS las cuentas IMAP priorizando
    a Value Property, Victoria Vilches y Guillermo Majluf, y persiste cada hallazgo en
    la carpeta y el EXPEDIENTE_360 de la Bóveda ADN (Regla #67)."""
    fu = await _fuentes_documentos()
    senders = set(BARRIDO_REMITENTES)
    for lst in fu.values():
        senders.update(s.strip().lower() for s in (lst or []) if s)
    async for f in db.folders.find({"fuentes_doc": {"$exists": True}}, {"fuentes_doc": 1}):
        for lst in (f.get("fuentes_doc") or {}).values():
            senders.update(_correos_de(lst))
    async def _run():
        try:
            await db.config.update_one({"_key": "barrido_forzado"}, {"$set": {
                "estado": "en_proceso", "inicio": _now(), "dias": dias}}, upsert=True)
            correos = await asyncio.to_thread(mail.fetch_since_by_senders, dias, sorted(senders))
            res = await _auditar_lote(correos)
            await db.config.update_one({"_key": "barrido_forzado"}, {"$set": {
                "estado": "completado", "ultima": _now(), "dias": dias,
                "resultado": {k: v for k, v in res.items() if k != "detalle"}}}, upsert=True)
        except Exception as ex:
            logging.warning(f"barrido forzado: {ex}")
            await db.config.update_one({"_key": "barrido_forzado"}, {"$set": {
                "estado": f"error: {str(ex)[:120]}", "ultima": _now()}}, upsert=True)
    asyncio.create_task(_run())
    return {"ok": True, "lanzado": True, "dias": dias,
            "seguimiento": "GET /api/flujos/barrido-estado"}


@flujos.get("/barrido-estado")
async def flujos_barrido_estado():
    return await db.config.find_one({"_key": "barrido_forzado"}, {"_id": 0}) or {"estado": "nunca_ejecutado"}


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
    if estado == "firmado":
        # REGLA DE HIERRO #62: sin salida SMTP confirmada, el hito no se completa
        import monitor_envios as _me
        await _me.exigir_correo_ok(fd.get("nombre") or "")
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


# ── BUZÓN DE APRENDIZAJE (2º IMAP, SOLO LECTURA) — entrena DashAI ───────────
_CLASIF = [("tasac", "tasacion"), ("reparo", "reparo"), ("estudio", "estudio_titulo"),
           ("notar", "notaria"), ("escritura", "escrituracion"), ("subsidio", "subsidio")]


def _leer_buzon_ro(host, email_u, clave, limit=25):
    """Lectura SOLO LECTURA (readonly + BODY.PEEK): jamás marca ni altera correos."""
    import imaplib
    import socket
    import email as _em
    from email.header import decode_header
    socket.setdefaulttimeout(25)
    m = imaplib.IMAP4_SSL(host)
    m.login(email_u, clave)
    m.select("INBOX", readonly=True)
    _, data = m.search(None, "ALL")
    ids = (data[0].split() or [])[-limit:]
    out = []
    for i in reversed(ids):
        try:
            _, md = m.fetch(i, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            msg = _em.message_from_bytes(md[0][1])
            def _dec(v):
                try:
                    return " ".join(t.decode(e or "utf-8", "ignore") if isinstance(t, bytes) else t
                                    for t, e in decode_header(v or ""))
                except Exception:
                    return v or ""
            out.append({"de": _dec(msg.get("From")), "asunto": _dec(msg.get("Subject")),
                        "fecha": msg.get("Date", "")})
        except Exception:
            continue
    m.logout()
    return out


@buzon.get("")
async def buzon_estado():
    cfg = await db.config.find_one({"_key": "buzon_aprendizaje"}, {"_id": 0, "cred_enc": 0}) or {}
    total = await db.buzon_aprendizaje.count_documents({})
    return {"configurado": bool(cfg.get("email")), "email": cfg.get("email", ""),
            "ingeridos": total, "ultima_lectura": cfg.get("ultima_lectura", ""),
            "estado": cfg.get("estado", ""), "modo": "solo_lectura"}


@buzon.post("/configurar")
async def buzon_configurar(payload: dict):
    em = (payload.get("email") or "").strip().lower()
    clave = (payload.get("app_password") or "").strip()
    host = (payload.get("imap_host") or "imap.gmail.com").strip()
    if not em or not EMAIL_RE.match(em) or not clave:
        raise HTTPException(status_code=400, detail="Correo y clave de aplicación son obligatorios")
    try:
        await asyncio.to_thread(_probar_imap, host, em, clave)
    except Exception:
        raise HTTPException(status_code=400, detail="⚠️ No fue posible conectar: verifique el correo y la clave de aplicación")
    await db.config.update_one({"_key": "buzon_aprendizaje"}, {"$set": {
        "email": em, "imap_host": host, "cred_enc": _enc_aes(clave),
        "estado": "ok", "configurado_en": _now()}}, upsert=True)
    return {"ok": True, "email": em, "modo": "solo_lectura",
            "nota": "DashAI leerá este buzón sin marcar ni mover correos (AES-256)"}


async def buzon_aprendizaje_loop():
    """Cada 15 min ingiere encabezados del buzón de aprendizaje para entrenar DashAI."""
    await asyncio.sleep(150)
    while True:
        try:
            cfg = await db.config.find_one({"_key": "buzon_aprendizaje"}) or {}
            if cfg.get("email") and cfg.get("cred_enc"):
                try:
                    correos = await asyncio.to_thread(_leer_buzon_ro, cfg.get("imap_host", "imap.gmail.com"),
                                                      cfg["email"], _dec_aes(cfg["cred_enc"]))
                    nuevos = 0
                    for c in correos or []:
                        clave_h = hashlib.md5(f"{c['de']}|{c['asunto']}|{c['fecha']}".encode()).hexdigest()
                        if await db.buzon_aprendizaje.find_one({"clave": clave_h}):
                            continue
                        t = c["asunto"].lower()
                        clasif = next((v for k, v in _CLASIF if k in t), "otro")
                        m = RUT_RE.search(c["asunto"])
                        await db.buzon_aprendizaje.insert_one({
                            "id": str(uuid.uuid4()), "clave": clave_h, **c,
                            "clasificacion": clasif, "rut_detectado": m.group(1) if m else "",
                            "ingerido": _now()})
                        nuevos += 1
                    await db.config.update_one({"_key": "buzon_aprendizaje"}, {"$set": {
                        "estado": "ok", "ultima_lectura": _now(), "ultimos_nuevos": nuevos}})
                except Exception as e:
                    await db.config.update_one({"_key": "buzon_aprendizaje"}, {"$set": {"estado": "requiere_actualizacion"}})
                    logging.warning(f"buzón aprendizaje: {e}")
        except Exception as e:
            logging.warning(f"buzón loop: {e}")
        await asyncio.sleep(900)


# ── SUPERCARPETA DE MANAGEMENT (Regla de Oro #55) — vista de control primario ─
def _informes_folder(fd):
    base = fsvc.folder_dir(fd.get("nombre") or "")
    inf = {"tasacion": None, "estudio": None, "borrador": None}
    if base.exists():
        for p in sorted(base.rglob("*.pdf"), key=lambda x: -x.stat().st_mtime):
            n = p.name.lower()
            rel = f"{p.parent.name}/{p.name}" if p.parent != base else p.name
            mt = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat()
            if not inf["tasacion"] and "tasac" in n:
                inf["tasacion"] = {"disponible": True, "archivo": rel, "fecha": mt}
            elif not inf["estudio"] and (p.parent.name == "07_estudio_titulo" or "estudio" in n):
                inf["estudio"] = {"disponible": True, "archivo": rel, "fecha": mt}
            elif not inf["borrador"] and ("escritura" in n or "borrador" in n):
                inf["borrador"] = {"disponible": True, "archivo": rel, "fecha": mt}
    for k in inf:
        if not inf[k]:
            inf[k] = {"disponible": False, "archivo": "", "fecha": ""}
    return inf


def _estado_tasacion(fd):
    if fd.get("tasacion_informe_recibido_at"):
        return "Informe Recibido"
    if fd.get("tasacion_fecha"):
        return "Visita"
    if (fd.get("reclamos_gerencia") or {}).get("tasacion") or fd.get("tasacion_solicitada_at"):
        return "Solicitada"
    return "Pendiente"


def _estado_estudio(fd):
    reparos = [r for r in (fd.get("reparos_alertas") or []) if not r.get("resuelto")]
    if reparos:
        return "Con Reparos", " | ".join((r.get("texto") or r.get("asunto") or "")[:300] for r in reparos[:4])
    if fd.get("estudio_titulo_terminado_at"):
        return "Aprobado", ""
    return "En Proceso", ""


def _estado_cesion(fd):
    """REGLA DE HIERRO: 'Confirmada' SOLO con evidencia real de firma detectada en un
    correo de la fuente configurada. Actividad de notaría o inferencias NO confirman."""
    if fd.get("firma_cesion_confirmada_at") or fd.get("escritura_confirmada_at"):
        return "Confirmada"
    return "Pendiente"


def _parse_fecha(s):
    from email.utils import parsedate_to_datetime
    s = str(s or "")
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        try:
            return parsedate_to_datetime(s)
        except Exception:
            return None


async def _bitacora_hito(fd, hito):
    """BITÁCORA DE TIEMPOS: respaldo de fecha/hora de cada solicitud 'En Proceso'.
    REGLA DE HIERRO: sin registro de solicitud → 'ERROR DE SEGUIMIENTO'."""
    nombre = (fd.get("nombre") or "").strip()
    kw = "TASACION" if hito == "tasacion" else "ESTUDIO"
    rx_n = {"$regex": re.escape(nombre[:18]), "$options": "i"}
    envio = await db.correos_smtp_log.find_one(
        {"success": True, "$and": [{"subject": rx_n},
                                   {"subject": {"$regex": kw, "$options": "i"}}]},
        sort=[("fecha", -1)])
    seg = None
    hx = None
    if not envio:
        seg = await db.seguimiento.find_one(
            {"$and": [{"$or": [{"cliente": rx_n}, {"asunto": rx_n}]},
                      {"asunto": {"$regex": kw, "$options": "i"}}]}, sort=[("fecha", -1)])
    if not envio and not seg:
        hx = await db.hitos_externos.find_one(
            {"$and": [{"$or": [{"cliente": rx_n}, {"asunto": rx_n}]},
                      {"asunto": {"$regex": kw, "$options": "i"}}]}, sort=[("fecha", -1)])
    rec = (fd.get("reclamos_gerencia") or {}).get(hito) or {}
    fecha_raw = ((envio or {}).get("fecha") or (seg or {}).get("fecha") or (hx or {}).get("fecha")
                 or rec.get("fecha") or rec.get("en") or "")
    if not fecha_raw:
        return {"hito": hito, "error_seguimiento": True, "estado": "ERROR DE SEGUIMIENTO",
                "detalle": "Regla de Hierro: no hay registro de cuándo se solicitó este hito"}
    destinatario = ((envio or {}).get("to")
                    or ((seg or {}).get("de") or "registro de seguimiento" if seg else "")
                    or ((hx or {}).get("fuente") or "radar de correos" if hx else "")
                    or ("Gerencia Comercial (reclamo manual)" if rec else ""))
    resumen = ((envio or {}).get("subject") or (seg or {}).get("asunto")
               or (hx or {}).get("asunto") or rec.get("hito") or "")
    respondido_at = (fd.get("tasacion_informe_recibido_at") if hito == "tasacion"
                     else fd.get("estudio_recibido_at") or fd.get("estudio_titulo_terminado_at"))
    dt = _parse_fecha(fecha_raw)
    horas = dias = None
    if dt:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        horas = round(delta.total_seconds() / 3600, 1)
        dias = delta.days
    return {"hito": hito, "error_seguimiento": False,
            "fecha_solicitud": str(fecha_raw)[:19],
            "destinatario": destinatario, "resumen": resumen[:220],
            "fuente": "correo SMTP" if envio else ("seguimiento" if seg else "huella de gestión"),
            "dias_transcurridos": dias, "horas_transcurridas": horas,
            "respondido": bool(respondido_at), "respondido_at": str(respondido_at or "")[:19],
            "demora_48h": bool(horas is not None and horas > 48 and not respondido_at)}


@supercarpeta.get("/bitacora/{fid}")
async def supercarpeta_bitacora(fid: str, hito: str = "tasacion"):
    fd = await db.folders.find_one({"id": fid})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    b = await _bitacora_hito(fd, "tasacion" if hito == "tasacion" else "estudio")
    b["cliente"] = fd.get("nombre") or ""
    return b


@supercarpeta.get("/flota")
async def flota_ver():
    cfg = await db.config.find_one({"_key": "flota_agosto"}, {"_id": 0}) or {}
    return {"activo": bool(cfg.get("activo")), "nombres": cfg.get("nombres") or [],
            "definida": _now() if cfg else None}


@supercarpeta.post("/flota")
async def flota_definir(request: Request, payload: dict):
    """PURGA TOTAL (Flota Agosto): solo el administrador define el universo de trabajo.
    Bloquea el ingreso de nuevos prospectos a las vistas sin autorización expresa."""
    user = getattr(request.state, "user", {}) or {}
    if (user.get("rol") or "") not in ("admin", "maestro"):
        raise HTTPException(status_code=403, detail="Solo el administrador define la Flota Agosto")
    nombres = [str(n).strip().upper() for n in (payload.get("nombres") or []) if str(n).strip()]
    activo = bool(payload.get("activo", True)) and len(nombres) > 0
    await db.config.update_one({"_key": "flota_agosto"}, {"$set": {
        "nombres": nombres, "activo": activo, "definida": _now(),
        "por": user.get("sub") or "admin"}}, upsert=True)
    return {"ok": True, "activo": activo, "total": len(nombres),
            "regla_hierro": "Solo existen estos clientes en las vistas activas hasta nueva autorización"}


_AVANCE_OK_RE = re.compile(
    r"(aprobad|firmad[ao]|verificado\b|informe recibido|recibid[ao]|confirmad[ao]|limpio|inscrita)", re.I)


async def _avance_notificar(mes_sel, clientes, pct_global):
    """Notifica a Rodrigo Ibáñez (100% por cliente) y a Gerencia General (hitos 50/75/100%)."""
    try:
        cfg = await db.config.find_one({"_key": f"avance_hitos_{mes_sel}"}) or {}
        upd, notif100 = {}, list(cfg.get("clientes_100") or [])
        for c in clientes:
            if (c.get("avance") or {}).get("pct", 0) >= 100 and c["id"] not in notif100:
                await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "avance_100",
                    "mensaje": f"🏆 Cliente {c['cliente']} ha completado todas las etapas. "
                               f"Crédito listo para escriturar. UF: {c.get('monto_uf') or 0}",
                    "fecha": _now(), "leida": False, "destino": "gerencia"})
                notif100.append(c["id"])
                upd["clientes_100"] = notif100
        for hito in (50, 75, 100):
            if pct_global >= hito and not cfg.get(f"hito_{hito}"):
                await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "avance_global",
                    "mensaje": f"📈 Proyección {mes_sel}: el cumplimiento global superó el {hito}% "
                               f"(actual: {pct_global}%). Hito informado a Gerencia General.",
                    "fecha": _now(), "leida": False, "destino": "gerencia_general"})
                upd[f"hito_{hito}"] = _now()
        if upd:
            await db.config.update_one({"_key": f"avance_hitos_{mes_sel}"}, {"$set": upd}, upsert=True)
    except Exception as e:
        logging.warning(f"avance notificar: {e}")


async def avance_snapshot_loop():
    """HISTÓRICO DE AVANCE: foto diaria del % de cada cliente, guardada en ADN_CLIENTES_360."""
    import adn_clientes as _adn
    await asyncio.sleep(300)
    while True:
        try:
            hoy = _now()[:10]
            cfg = await db.config.find_one({"_key": "avance_snapshot"}) or {}
            if cfg.get("dia") != hoy:
                meses = {m for m in await db.folders.distinct("mes_proyeccion") if m} | {"2026-08"}
                for mes_s in meses:
                    data = await supercarpeta_vista(mes_s)
                    for c in data.get("clientes", []):
                        if c.get("rut"):
                            await db.adn_clientes_360.update_one(
                                {"rut_norm": _adn._norm_rut(c["rut"])},
                                {"$push": {"avance_historico": {"fecha": hoy, "mes": mes_s,
                                           "pct": (c.get("avance") or {}).get("pct", 0)}}})
                await db.config.update_one({"_key": "avance_snapshot"},
                                           {"$set": {"dia": hoy, "en": _now()}}, upsert=True)
        except Exception as e:
            logging.warning(f"avance snapshot: {e}")
        await asyncio.sleep(3600)


@supercarpeta.get("")
async def supercarpeta_vista(mes: str = ""):
    """Regla #55 (V3): consulta directa a la Bóveda ADN_CLIENTES_360 — sin escanear PDFs físicos.
    NAVEGACIÓN MENSUAL: ?mes=YYYY-MM muestra la proyección de ese mes (bóveda compartida)."""
    from datetime import timedelta
    import adn_clientes as _adn
    from base_historica import validar_rut_chileno as _vrut, _fmt_rut
    mes_cal = datetime.now(timezone.utc).strftime("%Y-%m")
    mes_sel = (mes or "").strip() or "2026-08"
    limite24 = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    flota_cfg = await db.config.find_one({"_key": "flota_agosto"}) or {}
    flota = ({n.strip().upper() for n in (flota_cfg.get("nombres") or [])}
             if flota_cfg.get("activo") and mes_sel == "2026-08" else set())
    adn_map = {}
    async for r in db.adn_clientes_360.find({}, {"rut_norm": 1, "rut": 1, "expediente_360": 1,
                                                 "actualizado": 1, "identidad": 1, "propiedad": 1,
                                                 "financiero": 1, "origen": 1}):
        adn_map[r.get("rut_norm")] = r
    clientes = []
    async for fd in db.folders.find({}).sort("nombre", 1):
        nombre_u = (fd.get("nombre") or "").strip().upper()
        if fd.get("oculto_supercarpeta"):
            continue  # P10: eliminado de la vista por Gerencia (ficha ADN intacta)
        if (fd.get("mes_proyeccion") or "2026-08") != mes_sel:
            continue  # NAVEGACIÓN MENSUAL: cada mes muestra solo su proyección
        if flota:
            # REGLA DE HIERRO (Flota Agosto): solo existe la flota autorizada
            if not any(nf in nombre_u or nombre_u in nf for nf in flota):
                continue
        elif mes_sel == "2026-08":
            act = (fd.get("updated_at") or fd.get("created") or fd.get("created_at") or "")[:7]
            if act != mes_cal and not (fd.get("datos_financieros") or {}).get("monto_credito"):
                continue
        reg = adn_map.get(_adn._norm_rut(fd.get("rut"))) or {}
        exp = reg.get("expediente_360") or {}
        docs = exp.get("documentos") or []

        def _doc(kws, preferir="informe"):
            cands = [d for d in docs if any(k in (d.get("archivo") or "").lower() for k in kws)]
            cands.sort(key=lambda d: 0 if preferir in (d.get("archivo") or "").lower() else 1)
            return cands[0] if cands else None

        inf = {}
        for k, sel in (("tasacion", _doc(["tasac"])), ("estudio", _doc(["estudio"])),
                       ("borrador", _doc(["escritura", "borrador"], preferir="borrador"))):
            inf[k] = ({"disponible": True, "archivo": sel.get("archivo") or "",
                       "fecha": reg.get("actualizado") or ""} if sel
                      else {"disponible": False, "archivo": "", "fecha": ""})
        est_estudio, detalle_reparos = _estado_estudio(fd)
        hl = exp.get("hitos_legales") or {}
        if not detalle_reparos and hl.get("reparos"):
            detalle_reparos = hl["reparos"]
            est_estudio = "Con Reparos"
        # ── P7: ESTADOS MANUALES (Gerencia) con trazabilidad y detección de conflicto ──
        em = fd.get("estados_manuales") or {}
        est_tas = _estado_tasacion(fd)
        est_ces = _estado_cesion(fd)
        man = {"tasacion": False, "estudio": False, "cesion": False, "set_credito": False}
        conf = {"tasacion": False, "estudio": False, "cesion": False, "set_credito": False}
        auto_marks = {"tasacion": str(fd.get("tasacion_informe_recibido_at") or ""),
                      "estudio": str(fd.get("estudio_titulo_terminado_at")
                                     or fd.get("estudio_recibido_at") or ""),
                      "cesion": str(fd.get("firma_cesion_confirmada_at")
                                    or fd.get("escritura_confirmada_at") or ""),
                      "set_credito": str(fd.get("set_credito_at") or ""),
                      "serviu": "", "promesa": "",
                      "carpeta_notaria": str(fd.get("escritura_notaria_detectada_at") or ""),
                      "escritura": str(fd.get("escritura_confirmada_at") or "")}
        set_est = fd.get("set_credito_estado") or ""
        est_serviu = est_promesa = "Pendiente"
        est_carpeta = "Enviada" if fd.get("escritura_notaria_detectada_at") else "Pendiente"
        est_escritura = ("Firmada" if fd.get("escritura_confirmada_at")
                         else "Agendada" if (fd.get("fecha_firma") or fd.get("fecha_firma_detectada"))
                         else "Pendiente")
        for h in ("tasacion", "estudio", "cesion", "set_credito",
                  "serviu", "promesa", "carpeta_notaria", "escritura"):
            mh = em.get(h) or {}
            if mh.get("estado"):
                man[h] = True
                conf[h] = bool(auto_marks[h] and auto_marks[h] > str(mh.get("en") or "")
                               and not mh.get("resuelto"))
                if h == "tasacion":
                    est_tas = mh["estado"]
                elif h == "estudio":
                    est_estudio = mh["estado"]
                elif h == "cesion":
                    est_ces = mh["estado"]
                elif h == "set_credito":
                    set_est = mh["estado"]
                elif h == "serviu":
                    est_serviu = mh["estado"]
                elif h == "promesa":
                    est_promesa = mh["estado"]
                elif h == "carpeta_notaria":
                    est_carpeta = mh["estado"]
                else:
                    est_escritura = mh["estado"]
        estado_legal = ("⚠️ Con Reparos" if est_estudio == "Con Reparos"
                        else "✅ Limpio" if est_estudio in ("Aprobado", "Aprobada") else "⏳ En Proceso")
        # ── P1/P5: la Bóveda ADN manda — cada campo se lee primero de ADN_CLIENTES_360 ──
        prop_adn = reg.get("propiedad") or {}
        exp_prop = exp.get("propiedad") or {}
        ident = reg.get("identidad") or {}
        fin_adn = reg.get("financiero") or {}
        monto_v = fd.get("proyeccion_uf") or fin_adn.get("monto_credito_uf")
        sub_adn = fin_adn.get("con_subsidio")
        subsidio_v = (fd.get("subsidio_proyeccion")
                      or ("Con Subsidio" if sub_adn is True else "Sin Subsidio" if sub_adn is False else ""))
        rut_v = fd.get("rut") or reg.get("rut") or ""
        tipo_op = (fd.get("tipo_operacion") or prop_adn.get("tipo_operacion") or "").lower()
        inmo_dato = (fd.get("inmobiliaria") or prop_adn.get("inmobiliaria")
                     or exp_prop.get("inmobiliaria") or "").strip()
        if "usad" in tipo_op:
            inmobiliaria = "Casa Usada"
        elif inmo_dato:
            inmobiliaria = inmo_dato
        else:
            inmobiliaria = "Directa"
        if flota:
            broker_v = "Mutuaria y Leasing Limitada"
        else:
            broker_v = (fd.get("broker_origen") or fd.get("broker_nombre")
                        or (reg.get("origen") or {}).get("broker_origen") or "").strip()
        proyecto_v = (fd.get("proyecto") or prop_adn.get("proyecto") or exp_prop.get("proyecto")
                      or (fd.get("perfil_consolidado") or {}).get("proyecto") or "").strip()
        if not proyecto_v and "usad" in tipo_op:
            proyecto_v = (exp_prop.get("direccion") or prop_adn.get("direccion")
                          or (fd.get("perfil_consolidado") or {}).get("direccion") or "").strip()
        ciudad_v = (fd.get("ciudad") or ident.get("ciudad")
                    or (fd.get("perfil_consolidado") or {}).get("ciudad")
                    or exp_prop.get("comuna") or prop_adn.get("comuna") or "").strip()
        notaria_v = (fd.get("notaria") or exp_prop.get("notaria") or "").strip()
        # ── P6: FALTANTES = alerta de fallo de cosecha → botón de ingreso manual ──
        faltantes = []
        if not _vrut(rut_v):
            faltantes.append("rut")
        if not inmo_dato and "usad" not in tipo_op:
            faltantes.append("inmobiliaria")
        if not broker_v:
            faltantes.append("broker")
        if not monto_v:
            faltantes.append("monto")
        if not proyecto_v:
            faltantes.append("proyecto")
        if not ciudad_v:
            faltantes.append("ciudad")
        # BITÁCORA rápida por hito pendiente (respaldo de fecha o ERROR DE SEGUIMIENTO)
        bit = {}
        try:
            if _estado_tasacion(fd) != "Informe Recibido":
                bit["tasacion"] = await _bitacora_hito(fd, "tasacion")
            if est_estudio not in ("Aprobado", "Aprobada"):
                bit["estudio"] = await _bitacora_hito(fd, "estudio")
        except Exception:
            bit = {}
        fechas = [v["fecha"] for v in inf.values() if v["disponible"]]
        # ── AVANCE POR CLIENTE (Regla de Hierro): solo etapas realmente completadas ──
        con_sub_av = "con" in subsidio_v.lower()
        etapas_av = [
            ("docs", "Documentos Comerciales recibidos y actualizados", 15,
             bool(fd.get("datos_financieros_ocr_fecha"))),
            ("tasacion", "Tasación aprobada", 15, bool(_AVANCE_OK_RE.search(est_tas or ""))),
            ("estudio", "Estudio de Títulos aprobado", 20, est_estudio in ("Aprobado", "Aprobada")),
            ("serviu", "Resolución Serviu aprobada", 15, bool(_AVANCE_OK_RE.search(est_serviu or ""))),
            ("set", "Cédula de Crédito (SET) firmada y verificada", 15,
             bool(re.search(r"firmad|verificado\b|aprobad", set_est or "", re.I))
             and "esperando" not in (set_est or "").lower()),
            ("borrador", "Borrador de Escritura listo en Notaría", 10,
             est_carpeta == "Enviada" or inf["borrador"]["disponible"]),
            ("escritura", "Firma de Escritura en Notaría", 10, est_escritura == "Firmada"),
        ]
        if not con_sub_av:
            etapas_av = [e for e in etapas_av if e[0] != "serviu"]
        peso_tot = sum(e[2] for e in etapas_av) or 1
        avance_pct = round(sum(e[2] for e in etapas_av if e[3]) * 100 / peso_tot)
        avance = {"pct": avance_pct,
                  "etapas": [{"clave": k, "etapa": lb, "peso": round(p * 100 / peso_tot, 1),
                              "completada": ok_} for k, lb, p, ok_ in etapas_av]}
        clientes.append({"id": fd["id"], "cliente": fd.get("nombre"),
                         "avance": avance,
                         "rut": _fmt_rut(rut_v) if _vrut(rut_v) else (rut_v or ""),
                         "manual_identidad": list((fd.get("ingreso_manual") or {}).keys()),
                         "arrastre": fd.get("arrastre_desde") or "",
                         "inmobiliaria": inmobiliaria,
                         "proyecto": proyecto_v,
                         "ciudad": ciudad_v or "Por Confirmar",
                         "notaria": notaria_v,
                         "alerta_notaria_ciudad": bool(fd.get("alerta_notaria_ciudad")),
                         "alerta_reparos": bool(fd.get("alerta_reparos_sin_procesar")),
                         "broker": broker_v or "",
                         "broker_origen": broker_v or inmobiliaria,
                         "monto_uf": monto_v,
                         "subsidio": subsidio_v,
                         "reactivacion": bool(fd.get("reactivacion")),
                         "faltantes": faltantes,
                         "contacto": {"email": ident.get("email") or "",
                                      "telefono": ident.get("telefono") or ""},
                         "informes": inf,
                         "estado_tasacion": est_tas,
                         "estudio_titulos": est_estudio,
                         "estado_legal": estado_legal,
                         "detalle_reparos": detalle_reparos,
                         "cesion": est_ces,
                         "serviu": est_serviu, "promesa": est_promesa,
                         "carpeta_notaria": est_carpeta, "escritura": est_escritura,
                         "fecha_firma": fd.get("fecha_firma") or fd.get("fecha_firma_detectada") or "",
                         "con_subsidio": "con" in subsidio_v.lower(),
                         "set_credito": {"estado": set_est,
                                         "evidencia": fd.get("set_credito_evidencia") or "",
                                         "asunto": fd.get("set_credito_asunto") or "",
                                         "fecha": str(fd.get("set_credito_at") or "")[:19]},
                         "manual": man, "conflicto": conf,
                         "bitacora": bit,
                         "en_adn": bool(reg),
                         "recien_24h": any(f >= limite24 for f in fechas)})
    if mes_sel == "2026-08":
        meta_cfg = await db.config.find_one({"_key": "proyeccion_agosto"}) or {}
        meta_uf = meta_cfg.get("meta_uf") or 41717
    else:
        meta_cfg = await db.config.find_one({"_key": f"proyeccion_{mes_sel}"})
        if meta_cfg is None:
            # PROYECCIÓN DEL MES: estructura creada automáticamente, lista para recibir clientes
            await db.config.update_one({"_key": f"proyeccion_{mes_sel}"},
                                       {"$setOnInsert": {"creada": _now(), "meta_uf": 0}}, upsert=True)
            meta_cfg = {}
        meta_uf = meta_cfg.get("meta_uf") or 0
    suma_uf = sum(c.get("monto_uf") or 0 for c in clientes)
    pendientes_monto = [c["cliente"] for c in clientes if not c.get("monto_uf")]
    proyeccion = {"meta_uf": meta_uf, "suma_uf": round(suma_uf, 1),
                  "avance_pct": round(suma_uf * 100 / meta_uf, 1) if meta_uf else 0,
                  "diferencia_uf": round(meta_uf - suma_uf, 1),
                  "alerta_diferencia": bool(meta_uf and abs(meta_uf - suma_uf) > 0.5),
                  "pendientes_monto": pendientes_monto,
                  "broker": "Mutuaria y Leasing Limitada"}
    meses = sorted({m for m in await db.folders.distinct("mes_proyeccion") if m} | {"2026-08", "2026-09"})
    # ── META DE PROYECCIÓN: consolidado hacia Gerencia General y Rodrigo Ibáñez ──
    avance_prom = round(sum((c.get("avance") or {}).get("pct", 0) for c in clientes) / len(clientes), 1) if clientes else 0
    uf_en_avance = round(sum(c.get("monto_uf") or 0 for c in clientes if (c.get("avance") or {}).get("pct", 0) > 50), 1)
    uf_cerradas = round(sum(c.get("monto_uf") or 0 for c in clientes if (c.get("avance") or {}).get("pct", 0) >= 100), 1)
    pct_global = round(uf_cerradas * 100 / meta_uf, 1) if meta_uf else 0
    proyeccion.update({"avance_promedio": avance_prom, "uf_en_avance": uf_en_avance,
                       "uf_cerradas": uf_cerradas, "pct_global": pct_global})
    await _avance_notificar(mes_sel, clientes, pct_global)
    await db.config.update_one({"_key": f"avance_global_{mes_sel}"}, {"$set": {
        "pct_global": pct_global, "avance_promedio": avance_prom, "uf_cerradas": uf_cerradas,
        "uf_en_avance": uf_en_avance, "meta_uf": meta_uf, "actualizado": _now()}}, upsert=True)
    return {"mes": mes_cal, "mes_proyeccion": mes_sel, "meses": meses,
            "clientes": clientes, "total": len(clientes),
            "proyeccion": proyeccion,
            "flota_activa": bool(flota), "flota_total": len(flota),
            "fuente": "ADN_CLIENTES_360 (Regla #66) — sin escaneo de PDFs físicos",
            "recien_llegados": sum(1 for c in clientes if c["recien_24h"])}


HITOS_VALIDOS = ("tasacion", "estudio", "cesion", "set_credito",
                 "serviu", "promesa", "carpeta_notaria", "escritura", "notaria")


ESTADOS_MANUALES_BASE = ["Tasación Piloto", "Solicitada", "En Proceso",
                         "Con Observaciones", "Aprobada", "Rechazada"]


def _exigir_gerencia(request):
    user = getattr(request.state, "user", {}) or {}
    if (user.get("rol") or "") not in ("admin", "maestro", "gerencia"):
        raise HTTPException(status_code=403, detail="Solo el perfil Gerencia/Administrador puede realizar esta acción")
    return user


@supercarpeta.post("/manual/{fid}")
async def supercarpeta_manual(fid: str, payload: dict, request: Request):
    """P6 — INGRESO MANUAL DE RESPALDO: alerta de fallo de cosecha. El dato se guarda
    de inmediato en la carpeta y en la Bóveda ADN_CLIENTES_360 (Regla #67).
    BITÁCORA: valor anterior, valor nuevo, fecha/hora y usuario (inmutable)."""
    from base_historica import validar_rut_chileno, _fmt_rut
    user = getattr(request.state, "user", {}) or {}
    campo = (payload.get("campo") or "").strip().lower()
    valor = (payload.get("valor") or "").strip()
    if campo not in ("rut", "nombre", "inmobiliaria", "broker", "tipo_operacion", "monto",
                     "proyecto", "ciudad", "notaria", "subsidio") or not valor:
        raise HTTPException(status_code=400, detail="Campo o valor inválido")
    fd = await db.folders.find_one({"id": fid})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    if campo == "rut":
        if not validar_rut_chileno(valor):
            raise HTTPException(status_code=400,
                                detail="RUT inválido: no pasa el Dígito Verificador (Regla #66)")
        valor = _fmt_rut(valor)
    if campo == "nombre":
        valor = valor.upper()
        if len(valor) < 5 or len(valor.split()) < 2:
            raise HTTPException(status_code=400, detail="Nombre inválido (nombre y apellido)")
    if campo == "monto":
        try:
            valor = float(str(valor).replace("$", "").replace(" ", "").replace(".", "").replace(",", "."))
        except Exception:
            raise HTTPException(status_code=400, detail="Monto UF inválido")
    destino = {"rut": "rut", "nombre": "nombre", "inmobiliaria": "inmobiliaria",
               "broker": "broker_origen", "tipo_operacion": "tipo_operacion",
               "monto": "proyeccion_uf", "proyecto": "proyecto", "ciudad": "ciudad",
               "notaria": "notaria", "subsidio": "subsidio_proyeccion"}[campo]
    anterior = fd.get(destino)
    ahora = _now()
    await db.estado_manual_log.insert_one({
        "id": str(uuid.uuid4()), "folder_id": fid, "cliente": fd.get("nombre") or "",
        "hito": f"identidad_{campo}", "estado_anterior": str(anterior or ""),
        "estado_nuevo": str(valor), "por": user.get("sub") or "usuario",
        "fecha": ahora, "inmutable": True})
    await db.folders.update_one({"id": fid}, {"$set": {
        destino: valor, "updated_at": ahora,
        f"ingreso_manual.{campo}": {"valor": valor, "anterior": anterior,
                                    "por": user.get("sub") or "usuario", "en": ahora}}})
    if campo == "nombre" and (fd.get("nombre") or "") != valor:
        try:
            viejo, nuevo = fsvc.folder_dir(fd.get("nombre") or ""), fsvc.folder_dir(valor)
            if viejo.exists() and not nuevo.exists():
                viejo.rename(nuevo)
        except Exception:
            pass
    en_adn = await _sync_adn(fid)
    return {"ok": True, "campo": campo, "valor": valor, "anterior": anterior,
            "en_adn": bool(en_adn), "marca": "✏️ manual",
            "alerta": "Ingreso manual registrado en bitácora inmutable (Regla #67)"}


@supercarpeta.post("/estado/{fid}")
async def supercarpeta_estado_manual(fid: str, payload: dict, request: Request):
    """P7 — EDICIÓN MANUAL DE ESTADOS (solo Gerencia): bitácora inmutable con quién,
    fecha/hora, estado anterior y nuevo. Se marca ✏️ y se guarda en la Bóveda ADN."""
    user = _exigir_gerencia(request)
    hito = (payload.get("hito") or "").strip().lower()
    estado = (payload.get("estado") or "").strip()
    if hito not in HITOS_VALIDOS or not estado or len(estado) > 60:
        raise HTTPException(status_code=400, detail="Hito o estado inválido")
    fd = await db.folders.find_one({"id": fid})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    anterior = (((fd.get("estados_manuales") or {}).get(hito) or {}).get("estado")
                or (_estado_tasacion(fd) if hito == "tasacion"
                    else _estado_estudio(fd)[0] if hito == "estudio"
                    else fd.get("set_credito_estado") or "Pendiente" if hito == "set_credito"
                    else _estado_cesion(fd)))
    ahora = _now()
    await db.estado_manual_log.insert_one({
        "id": str(uuid.uuid4()), "folder_id": fid, "cliente": fd.get("nombre") or "",
        "hito": hito, "estado_anterior": anterior, "estado_nuevo": estado,
        "por": user.get("sub") or "gerencia", "fecha": ahora, "inmutable": True})
    await db.folders.update_one({"id": fid}, {"$set": {
        f"estados_manuales.{hito}": {"estado": estado, "por": user.get("sub") or "gerencia",
                                     "en": ahora, "anterior": anterior},
        "updated_at": ahora}})
    await _sync_adn(fid)
    return {"ok": True, "hito": hito, "estado": estado, "anterior": anterior,
            "marca": "✏️ manual", "bitacora": "estado_manual_log (inmutable)"}


@supercarpeta.post("/estado/{fid}/resolver")
async def supercarpeta_estado_resolver(fid: str, payload: dict, request: Request):
    """P7 — CONFLICTO: el correo detectó un dato posterior al estado manual.
    Gerencia decide: mantener el manual o sobreescribir con lo detectado."""
    user = _exigir_gerencia(request)
    hito = (payload.get("hito") or "").strip().lower()
    accion = (payload.get("accion") or "").strip().lower()
    if hito not in HITOS_VALIDOS or accion not in ("mantener", "sobreescribir"):
        raise HTTPException(status_code=400, detail="Hito o acción inválida")
    fd = await db.folders.find_one({"id": fid})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    ahora = _now()
    if accion == "sobreescribir":
        await db.folders.update_one({"id": fid}, {"$unset": {f"estados_manuales.{hito}": ""},
                                                  "$set": {"updated_at": ahora}})
        detalle = "Estado manual eliminado: manda lo detectado automáticamente por correo"
    else:
        await db.folders.update_one({"id": fid}, {"$set": {
            f"estados_manuales.{hito}.resuelto": ahora, "updated_at": ahora}})
        detalle = "Estado manual confirmado por Gerencia sobre el dato detectado"
    await db.estado_manual_log.insert_one({
        "id": str(uuid.uuid4()), "folder_id": fid, "cliente": fd.get("nombre") or "",
        "hito": hito, "accion_conflicto": accion, "detalle": detalle,
        "por": user.get("sub") or "gerencia", "fecha": ahora, "inmutable": True})
    await _sync_adn(fid)
    return {"ok": True, "accion": accion, "detalle": detalle}


@supercarpeta.get("/estado-log/{fid}")
async def supercarpeta_estado_log(fid: str):
    regs = await db.estado_manual_log.find({"folder_id": fid}, {"_id": 0}).sort("fecha", -1).to_list(50)
    return {"log": regs, "total": len(regs)}


@supercarpeta.get("/fuentes-doc")
async def fuentes_doc_get():
    """P8 — Fuentes por columna: BLOQUE GLOBAL (todos los clientes) + BLOQUE INDIVIDUAL (por cliente)."""
    meta = await _fuentes_documentos_meta()
    for h, lst in meta.items():
        for f in lst:
            hx = await db.hitos_externos.find_one(
                {"direccion": {"$regex": re.escape(f["correo"]), "$options": "i"}}, sort=[("creado", -1)])
            f["ultima_deteccion"] = (hx or {}).get("creado") or ""
            f["tipo"] = "Global"
    alternativas = []
    async for f in db.folders.find({"fuentes_doc": {"$exists": True}},
                                   {"_id": 0, "id": 1, "nombre": 1, "fuentes_doc": 1}):
        fdoc = {}
        for h, lst in (f.get("fuentes_doc") or {}).items():
            fdoc[h] = [{**_norm_fuente(x), "tipo": "Individual"}
                       for x in (lst or []) if _norm_fuente(x)["correo"]]
        alternativas.append({"id": f["id"], "nombre": f.get("nombre"), "fuentes_doc": fdoc})
    return {"fuentes": meta, "alternativas_cliente": alternativas,
            "estados_disponibles": ESTADOS_MANUALES_BASE}


EMAIL_VALID_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")


async def _log_fuente(user, ambito, hito, accion, correo, nombre, cliente=""):
    await db.fuentes_log.insert_one({
        "id": str(uuid.uuid4()), "ambito": ambito, "hito": hito, "accion": accion,
        "correo": correo, "nombre": nombre, "cliente": cliente,
        "por": user.get("sub") or "gerencia", "fecha": _now(), "inmutable": True})


@supercarpeta.post("/fuentes-doc")
async def fuentes_doc_set(payload: dict, request: Request):
    """P8 — FUENTES GLOBALES: agregar/quitar casillas sin límite; efecto inmediato + bitácora."""
    user = _exigir_gerencia(request)
    hito = (payload.get("hito") or "").strip().lower()
    accion = (payload.get("accion") or "").strip().lower()
    if hito in FUENTES_HITOS and accion in ("agregar", "quitar"):
        correo = (payload.get("correo") or "").strip().lower()
        nombre = (payload.get("nombre") or "").strip()
        if not EMAIL_VALID_RE.match(correo):
            raise HTTPException(status_code=400, detail="Correo fuente inválido")
        meta = await _fuentes_documentos_meta()
        lst = [f for f in meta.get(hito, []) if f["correo"] != correo]
        if accion == "agregar":
            lst.append({"correo": correo, "nombre": nombre})
        meta[hito] = lst
        await db.config.update_one({"_key": "fuentes_documentos"}, {"$set": {
            "fuentes": meta, "actualizado": _now(), "por": user.get("sub") or "gerencia"}}, upsert=True)
        await _log_fuente(user, "global", hito, accion, correo, nombre)
        return {"ok": True, "hito": hito, "accion": accion, "fuentes": meta[hito],
                "nota": "Monitoreo actualizado de inmediato (sin reiniciar)"}
    meta = await _fuentes_documentos_meta()
    cambiado = {}
    for h in FUENTES_HITOS:
        if h in payload:
            meta[h] = [{"correo": c, "nombre": ""} for c in _correos_de(payload.get(h))
                       if EMAIL_VALID_RE.match(c)]
            cambiado[h] = meta[h]
    if not cambiado:
        raise HTTPException(status_code=400, detail="Nada que actualizar")
    await db.config.update_one({"_key": "fuentes_documentos"}, {"$set": {
        "fuentes": meta, "actualizado": _now(), "por": user.get("sub") or "gerencia"}}, upsert=True)
    return {"ok": True, "fuentes": cambiado}


@supercarpeta.post("/fuentes-doc/{fid}")
async def fuentes_doc_cliente(fid: str, payload: dict, request: Request):
    """P8 — FUENTES INDIVIDUALES: solo para ese cliente (ej. vivienda usada). Sin límite."""
    user = _exigir_gerencia(request)
    fd = await db.folders.find_one({"id": fid})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    fdoc = fd.get("fuentes_doc") or {}
    hito = (payload.get("hito") or "").strip().lower()
    accion = (payload.get("accion") or "").strip().lower()
    if hito in FUENTES_HITOS and accion in ("agregar", "quitar"):
        correo = (payload.get("correo") or "").strip().lower()
        nombre = (payload.get("nombre") or "").strip()
        if not EMAIL_VALID_RE.match(correo):
            raise HTTPException(status_code=400, detail="Correo fuente inválido")
        lst = [f for f in (_norm_fuente(x) for x in (fdoc.get(hito) or []))
               if f["correo"] and f["correo"] != correo]
        if accion == "agregar":
            lst.append({"correo": correo, "nombre": nombre})
        fdoc[hito] = lst
        await _log_fuente(user, "individual", hito, accion, correo, nombre, fd.get("nombre") or "")
    else:
        for h in FUENTES_HITOS:
            if h in payload:
                fdoc[h] = [{"correo": c, "nombre": ""} for c in _correos_de(payload.get(h))
                           if EMAIL_VALID_RE.match(c)]
    await db.folders.update_one({"id": fid}, {"$set": {"fuentes_doc": fdoc, "updated_at": _now()}})
    await _sync_adn(fid)
    return {"ok": True, "cliente": fd.get("nombre"), "fuentes_doc": fdoc}


# ── COSTOS CBR — extracción desde adjuntos "Simulación" de Mesa ─────────────
_CBR_FILA_RE = re.compile(r"(\bC\.?\s?B\.?\s?R\.?\b|conservador(?:\s+de)?\s+bienes\s+ra[ií]ces|\bconservador\b)", re.I)
_CBR_UF_RE = re.compile(r"(?:UF\s*\$?\s*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*UF\b)", re.I)
_CBR_CLP_RE = re.compile(r"\$\s*(\d{1,3}(?:\.\d{3})+|\d{4,9})|\b(\d{1,3}(?:\.\d{3})+)\b")


def _monto_en_linea(l):
    m_uf = _CBR_UF_RE.search(l)
    if m_uf:
        try:
            return float((m_uf.group(1) or m_uf.group(2)).replace(",", ".")), "UF"
        except ValueError:
            pass
    m_clp = _CBR_CLP_RE.search(l)
    if m_clp:
        try:
            return int((m_clp.group(1) or m_clp.group(2)).replace(".", "")), "CLP"
        except ValueError:
            pass
    m_num = re.search(r"\b(\d{4,9})\b", l)
    if m_num:
        return int(m_num.group(1)), "CLP"
    return None


def _extraer_cbr_texto(texto):
    """REGLA DE HIERRO: solo lee filas reales — jamás inventa valores.
    Si existe la sección 'Gastos Operacionales', busca desde ahí hacia abajo."""
    d = _extraer_gastos_texto(texto)
    return d.get("valor_cbr")


_GASTO_FILAS = [
    ("valor_cbr", _CBR_FILA_RE),
    ("tasacion", re.compile(r"\btasaci[oó]n\b", re.I)),
    ("est_titulos", re.compile(r"estudio\s+de\s+t[ií]tulos|\best\.?\s*t[ií]tulos", re.I)),
]


def _extraer_gastos_texto(texto):
    lineas = [l.strip() for l in (texto or "").splitlines() if l.strip()]
    idx = next((i for i, l in enumerate(lineas) if "gastos operacionales" in l.lower()), None)
    ambito = lineas[idx:] if idx is not None else lineas
    out = {}
    for campo, rx in _GASTO_FILAS:
        for i, l in enumerate(ambito):
            if not rx.search(l):
                continue
            r = _monto_en_linea(l)
            if not r and i + 1 < len(ambito):
                r = _monto_en_linea(ambito[i + 1])
            if r:
                out[campo] = {"valor": r[0], "moneda": r[1], "linea": l[:180]}
                break
    return out


def _extraer_gastos_pdf(pdf_bytes):
    """Abre el adjunto: prioriza la SEGUNDA página (Gastos Operacionales), luego el resto.
    Extrae CBR + Tasación + Estudio de Títulos en una sola pasada."""
    import io as _io
    import pdfplumber
    acumulado = {}
    try:
        with pdfplumber.open(_io.BytesIO(pdf_bytes)) as pdf:
            paginas = pdf.pages
            orden = ([1] if len(paginas) > 1 else []) + [i for i in range(len(paginas)) if i != 1]
            for i in orden:
                try:
                    d = _extraer_gastos_texto(paginas[i].extract_text() or "")
                except Exception:
                    d = {}
                for k, v in d.items():
                    acumulado.setdefault(k, {**v, "pagina": i + 1})
                if len(acumulado) == len(_GASTO_FILAS):
                    break
    except Exception:
        pass
    return acumulado


def _extraer_cbr_pdf(pdf_bytes):
    return (_extraer_gastos_pdf(pdf_bytes) or {}).get("valor_cbr")


# COMISIÓN (USO INTERNO — SOLO GERENCIA): % según broker/inmobiliaria
_COMISION_PCT = {"boetsch": 1.0, "boetch": 1.0, "ecomac": 1.0, "poch": 1.0,
                 "comod": 0.8, "usada": 0.5}


def _comision_cliente(fd, monto_uf):
    """Regla de cálculo: % sobre el monto del crédito según broker. Sin regla → revisar."""
    tipo = (fd.get("tipo_operacion") or "").lower()
    b = mail._sin_acentos((fd.get("inmobiliaria") or fd.get("broker_origen") or "").lower())
    pct = 0.5 if ("usad" in tipo or "usada" in b) else next(
        (p for k, p in _COMISION_PCT.items() if k in b), None)
    if pct is None:
        return None, "REVISAR CON GERENCIA"
    com = round(float(monto_uf or 0) * pct / 100, 2) if monto_uf else ""
    return com, f"{pct}%"


async def _ejecutar_cbr():
    import adn_clientes as _adn
    await db.config.update_one({"_key": "cbr_extraccion"}, {"$set": {
        "estado": "en_proceso", "inicio": _now()}}, upsert=True)
    try:
        flota_cfg = await db.config.find_one({"_key": "flota_agosto"}) or {}
        flota = ({n.strip().upper() for n in (flota_cfg.get("nombres") or [])}
                 if flota_cfg.get("activo") else set())
        carpetas = []
        async for fd in db.folders.find({}).sort("nombre", 1):
            if fd.get("oculto_supercarpeta"):
                continue
            if (fd.get("mes_proyeccion") or "2026-08") != "2026-08":
                continue
            nombre_u = (fd.get("nombre") or "").strip().upper()
            if flota and not any(nf in nombre_u or nombre_u in nf for nf in flota):
                continue
            carpetas.append(fd)
        # BÚSQUEDA DIRIGIDA: solo correos de aprobaciones@ que mencionan a cada cliente
        nombres = [" ".join((fd.get("nombre") or "").split()[:2]) for fd in carpetas]
        correos = await asyncio.to_thread(mail.fetch_simulacion_attachments, 60,
                                          "aprobaciones@centralmutuos.cl", nombres)
        adn_map = {}
        async for r in db.adn_clientes_360.find({}, {
                "rut_norm": 1, "financiero": 1, "costo_CBR": 1,
                "costo_tasacion": 1, "costo_estudio_titulos": 1, "comision": 1}):
            adn_map[r.get("rut_norm")] = r
        viejo = await db.config.find_one({"_key": "cbr_extraccion"}) or {}
        old_map = {(r.get("cliente") or "").strip().upper(): r
                   for r in viejo.get("resultados") or []}
        resultados = []
        for fd in carpetas:
            nombre_u = (fd.get("nombre") or "").strip().upper()
            toks = [t for t in mail._sin_acentos(nombre_u.lower()).split() if len(t) > 2]
            necesarios = min(2, len(toks)) or 1
            gastos, meta = None, None
            for e in correos:  # ya vienen ordenados del más reciente al más antiguo
                blob = mail._sin_acentos(" ".join(
                    [e.get("subject") or "", e.get("body") or ""]
                    + [p.get("filename") or "" for p in e.get("pdfs") or []]).lower())
                if sum(1 for t in toks if t in blob) < necesarios:
                    continue
                for p in e.get("pdfs") or []:
                    g = await asyncio.to_thread(_extraer_gastos_pdf, p.get("content_bytes") or b"")
                    if g:
                        gastos = g
                        meta = {"fecha_correo": (e.get("date") or "")[:10],
                                "archivo": p.get("filename") or "",
                                "fuente": e.get("cuenta") or "correo"}
                        break
                if gastos:
                    break
            cbr = (gastos or {}).get("valor_cbr")
            reg = adn_map.get(_adn._norm_rut(fd.get("rut"))) if fd.get("rut") else None
            monto_uf = (fd.get("proyeccion_uf")
                        or ((reg or {}).get("financiero") or {}).get("monto_credito_uf") or "")
            comision, pct_txt = _comision_cliente(fd, monto_uf)
            fila = {
                "cliente": fd.get("nombre") or "",
                "broker": fd.get("inmobiliaria") or fd.get("broker_origen") or "",
                "monto_credito": monto_uf,
                "comision": comision if comision is not None else "",
                "pct_aplicado": pct_txt,
                "valor_cbr": cbr["valor"] if cbr else "",
                "moneda": cbr["moneda"] if cbr else "",
                "tasacion": "", "tasacion_moneda": "",
                "est_titulos": "", "est_titulos_moneda": "",
                "fecha_correo": (meta or {}).get("fecha_correo", ""),
                "archivo": (meta or {}).get("archivo", ""),
                "linea": (cbr or {}).get("linea", ""),
                "estado": "ENCONTRADO" if cbr else "NO ENCONTRADO"}
            for campo in ("tasacion", "est_titulos"):
                g = (gastos or {}).get(campo)
                if g:
                    fila[campo] = g["valor"]
                    fila[f"{campo}_moneda"] = g["moneda"]
            # respaldo desde la Bóveda ADN si la extracción no trajo el dato
            for campo, mon_key, adn_f in _CBR_CAMPOS:
                if campo == "comision" or fila.get(campo) not in ("", None):
                    continue
                doc = (reg or {}).get(adn_f) or {}
                if doc.get("valor") not in ("", None):
                    fila[campo] = doc["valor"]
                    fila[mon_key] = doc.get("moneda") or "UF"
                    if doc.get("origen") == "manual":
                        fila[f"{campo}_origen"] = "manual"
            # preservar valores ingresados manualmente en corridas anteriores
            old = old_map.get(nombre_u) or {}
            for campo, mon_key, _f in _CBR_CAMPOS:
                if (old.get(f"{campo}_origen") == "manual"
                        and old.get(campo) not in ("", None)
                        and fila.get(campo) in ("", None)):
                    fila[campo] = old[campo]
                    fila[f"{campo}_origen"] = "manual"
                    if old.get(mon_key):
                        fila[mon_key] = old[mon_key]
            if old.get("comision_origen") == "manual" and old.get("comision") not in ("", None):
                fila["comision"] = old["comision"]
                fila["comision_origen"] = "manual"
            resultados.append(fila)
            # persistencia: carpeta + Bóveda ADN_CLIENTES_360
            sets_f = {}
            for campo, doc_key in (("valor_cbr", "costo_CBR"), ("tasacion", "costo_tasacion"),
                                   ("est_titulos", "costo_estudio_titulos")):
                g = (gastos or {}).get(campo)
                if g:
                    sets_f[doc_key] = {"valor": g["valor"], "moneda": g["moneda"],
                                       "fecha_correo": meta["fecha_correo"], "archivo": meta["archivo"],
                                       "extraido": _now(), "origen": "aprobaciones@centralmutuos.cl"}
            if sets_f:
                await db.folders.update_one({"id": fd["id"]}, {"$set": {
                    **sets_f, "updated_at": _now()}})
                await _sync_adn(fd["id"])
                if fd.get("rut"):
                    await db.adn_clientes_360.update_one(
                        {"rut_norm": _adn._norm_rut(fd["rut"])}, {"$set": sets_f})
        await db.config.update_one({"_key": "cbr_extraccion"}, {"$set": {
            "estado": "completado", "ultima": _now(), "resultados": resultados,
            "remitente": "aprobaciones@centralmutuos.cl",
            "encontrados": sum(1 for r in resultados if r["estado"] == "ENCONTRADO"),
            "total": len(resultados), "correos_revisados": len(correos)}}, upsert=True)
    except Exception as ex:
        logging.warning(f"cbr extraccion: {ex}")
        await db.config.update_one({"_key": "cbr_extraccion"}, {"$set": {
            "estado": f"error: {str(ex)[:150]}", "ultima": _now()}}, upsert=True)


def _es_admin_general(request):
    """ACCESO EXCLUSIVO: solo el Administrador General (Gerardo) ve CBR y comisiones."""
    return ((getattr(request.state, "user", {}) or {}).get("rol") or "") in ("admin", "maestro")


def _exigir_admin_general(request):
    if not _es_admin_general(request):
        raise HTTPException(status_code=403,
            detail="Acceso denegado: módulo de Comisiones y CBR exclusivo del Administrador General")


# campos de gasto: (campo, clave de moneda, campo en ADN/folder)
_CBR_CAMPOS = [("valor_cbr", "moneda", "costo_CBR"),
               ("tasacion", "tasacion_moneda", "costo_tasacion"),
               ("est_titulos", "est_titulos_moneda", "costo_estudio_titulos"),
               ("comision", "comision_moneda", "comision")]


def _cbr_totales(res):
    """REGLA DE CONVERSIÓN: NUNCA se mezclan monedas — UF suma con UF, CLP con CLP."""
    prefijos = {"valor_cbr": "total_cbr", "tasacion": "total_tasacion",
                "est_titulos": "total_titulos", "comision": "total_comision"}
    tot = {f"{p}_{s}": 0.0 for p in prefijos.values() for s in ("uf", "clp")}
    for r in res:
        for campo, mon_key, _ in _CBR_CAMPOS:
            v = r.get(campo)
            if v in ("", None):
                continue
            try:
                v = float(v)
            except (TypeError, ValueError):
                continue
            suf = "clp" if (r.get(mon_key) or "UF").upper() == "CLP" else "uf"
            tot[f"{prefijos[campo]}_{suf}"] += v
    for s in ("uf", "clp"):
        tot[f"gran_total_{s}"] = (tot[f"total_cbr_{s}"] + tot[f"total_tasacion_{s}"]
                                  + tot[f"total_titulos_{s}"])
    return {k: round(v, 2) for k, v in tot.items()}


@supercarpeta.get("/cbr/estado")
async def cbr_estado(request: Request):
    _exigir_admin_general(request)
    d = (await db.config.find_one({"_key": "cbr_extraccion"}, {"_id": 0})
         or {"estado": "nunca_ejecutado", "resultados": []})
    d.update(_cbr_totales(d.get("resultados") or []))
    return d


@supercarpeta.post("/cbr/manual")
async def cbr_manual(request: Request, payload: dict):
    """Edición manual del Admin General: guarda de inmediato en ADN_CLIENTES_360."""
    _exigir_admin_general(request)
    import adn_clientes as _adn
    campo = payload.get("campo")
    campos_validos = {c: (mk, af) for c, mk, af in _CBR_CAMPOS}
    if campo not in campos_validos:
        raise HTTPException(status_code=400,
                            detail="campo inválido: use valor_cbr, tasacion, est_titulos o comision")
    bruto = str(payload.get("valor") if payload.get("valor") is not None else "").strip().replace(",", ".")
    valor = ""
    if bruto:
        try:
            valor = round(float(bruto), 2)
        except ValueError:
            raise HTTPException(status_code=400, detail="valor numérico inválido")
    cfg = await db.config.find_one({"_key": "cbr_extraccion"}) or {}
    res = cfg.get("resultados") or []
    cliente = (payload.get("cliente") or "").strip().upper()
    fila = next((r for r in res if (r.get("cliente") or "").strip().upper() == cliente), None)
    if not fila:
        raise HTTPException(status_code=404, detail="cliente no está en el reporte CBR")
    fila[campo] = valor
    fila[f"{campo}_origen"] = "manual" if valor != "" else ""
    mon_key, adn_field = campos_validos[campo]
    if valor != "" and not fila.get(mon_key):
        fila[mon_key] = "UF"
    await db.config.update_one({"_key": "cbr_extraccion"}, {"$set": {"resultados": res}})
    fd = await db.folders.find_one({"nombre": fila["cliente"]})
    if fd:
        doc = {"valor": valor, "moneda": fila.get(mon_key) or "UF",
               "origen": "manual", "actualizado": _now()}
        if campo == "comision":
            if fd.get("rut"):
                await db.adn_clientes_360.update_one(
                    {"rut_norm": _adn._norm_rut(fd["rut"])}, {"$set": {"comision": doc}})
        else:
            await db.folders.update_one({"id": fd["id"]}, {"$set": {
                adn_field: doc, "updated_at": _now()}})
            await _sync_adn(fd["id"])
            if fd.get("rut"):
                await db.adn_clientes_360.update_one(
                    {"rut_norm": _adn._norm_rut(fd["rut"])}, {"$set": {adn_field: doc}})
    return {"ok": True, **_cbr_totales(res)}


@supercarpeta.post("/cbr/extraer")
async def cbr_extraer(request: Request):
    """Lanza la búsqueda de correos de aprobaciones@ y extrae el CBR de cada cliente."""
    _exigir_admin_general(request)
    from datetime import timedelta
    cfg = await db.config.find_one({"_key": "cbr_extraccion"}) or {}
    if cfg.get("estado") == "en_proceso" and (cfg.get("inicio") or "") > (
            datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat():
        return {"ok": True, "estado": "en_proceso", "nota": "Extracción CBR ya en curso"}
    asyncio.create_task(_ejecutar_cbr())
    return {"ok": True, "lanzado": True, "seguimiento": "GET /api/supercarpeta/cbr/estado"}


@supercarpeta.get("/cbr/excel")
async def cbr_excel(request: Request):
    """ACCESO EXCLUSIVO: el Excel de CBR + comisiones solo para el Administrador General."""
    _exigir_admin_general(request)
    cfg = await db.config.find_one({"_key": "cbr_extraccion"}) or {}
    res = cfg.get("resultados") or []
    if not res:
        raise HTTPException(status_code=404, detail="Sin resultados CBR: ejecute primero la extracción")
    import io as _io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "Costos CBR"
    ws.append(["Nombre del cliente", "Broker", "Monto del crédito (UF)",
               "Valor CBR (Inscripción Registro Propiedad + Hipoteca)",
               "Tasación", "Estudio de Títulos", "Total Pagado",
               "Comisión (monto calculado)", "Porcentaje aplicado",
               "Moneda", "Fecha del correo fuente", "Estado CBR"])
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F2937")
    for r in res:
        vals = [r.get(k) for k in ("valor_cbr", "tasacion", "est_titulos")]
        nums = [float(v) for v in vals if v not in ("", None)]
        total_pagado = round(sum(nums), 2) if nums else ""
        incompleto = len(nums) < 3
        ws.append([r.get("cliente", ""), r.get("broker", ""), r.get("monto_credito", ""),
                   r.get("valor_cbr", ""), r.get("tasacion", ""), r.get("est_titulos", ""),
                   f"{total_pagado} ⚠ incompleto" if incompleto and total_pagado != "" else total_pagado,
                   r.get("comision", ""), r.get("pct_aplicado", ""),
                   r.get("moneda", ""), r.get("fecha_correo", ""), r.get("estado", "")])
        if incompleto:
            ws.cell(row=ws.max_row, column=7).fill = PatternFill("solid", fgColor="FEF3C7")
        ws.cell(row=ws.max_row, column=12).font = Font(
            bold=True, color="15803D" if r.get("estado") == "ENCONTRADO" else "B91C1C")
    tot = _cbr_totales(res)
    ws.append(["TOTAL EN UF", "", "", tot["total_cbr_uf"], tot["total_tasacion_uf"],
               tot["total_titulos_uf"], tot["gran_total_uf"], tot["total_comision_uf"],
               "", "UF", "", ""])
    for c in ws[ws.max_row]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1E3A8A")
    ws.append(["TOTAL EN PESOS", "", "", tot["total_cbr_clp"], tot["total_tasacion_clp"],
               tot["total_titulos_clp"], tot["gran_total_clp"], tot["total_comision_clp"],
               "", "CLP", "", ""])
    for c in ws[ws.max_row]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="14532D")
    for col, w in zip("ABCDEFGHIJKL", (34, 24, 18, 24, 12, 16, 16, 20, 18, 9, 16, 16)):
        ws.column_dimensions[col].width = w
    buf = _io.BytesIO()
    wb.save(buf)
    return Response(content=buf.getvalue(),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="costos_CBR.xlsx"'})


# ── CUENTA DE BARRIDO (SOLO LECTURA) — categoría propia del Panel ⚙️ ────────
def _dv_rut(cuerpo):
    s, f = 0, 2
    for d in reversed(cuerpo):
        s += int(d) * f
        f = 2 if f == 7 else f + 1
    r = 11 - (s % 11)
    return "0" if r == 11 else "k" if r == 10 else str(r)


async def _cosechar_ruts_faltantes(correos):
    """Regla #66: si un correo trae el nombre de un cliente SIN RUT + exactamente un
    RUT válido (DV verificado), se cosecha y queda ESCRITO en carpeta + Bóveda ADN."""
    sin_rut = await db.folders.find(
        {"oculto_supercarpeta": {"$exists": False},
         "$or": [{"rut": ""}, {"rut": None}, {"rut": {"$exists": False}}]},
        {"id": 1, "nombre": 1}).to_list(200)
    if not sin_rut:
        return 0
    usados = {_rut_limpio(f.get("rut")) async for f in db.folders.find({"rut": {"$nin": ["", None]}}, {"rut": 1})}
    hallados = 0
    for e in correos or []:
        texto = f"{e.get('subject', '')} {e.get('body', '')}".lower()
        ruts = list({_rut_limpio(m) for m in RUT_RE.findall(texto)})
        ruts = [r for r in ruts if len(r) >= 8 and _dv_rut(r[:-1]) == r[-1] and r not in usados]
        if len(ruts) != 1:
            continue
        for fd in list(sin_rut):
            toks = [x for x in (fd.get("nombre") or "").lower().split() if len(x) > 2]
            if len(toks) >= 2 and sum(1 for x in toks if x in texto) >= 2:
                rut_fmt = f"{ruts[0][:-1]}-{ruts[0][-1].upper()}"
                await db.folders.update_one({"id": fd["id"]}, {"$set": {
                    "rut": rut_fmt, "rut_origen": "cuenta_barrido", "updated_at": _now()}})
                await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "cuenta_barrido",
                    "mensaje": f"🧬 RUT cosechado por la Cuenta de Barrido: {fd.get('nombre')} → {rut_fmt}",
                    "fecha": _now(), "leida": False})
                await _sync_adn(fd["id"])
                sin_rut.remove(fd)
                usados.add(ruts[0])
                hallados += 1
                break
    return hallados


async def _ejecutar_barrido_cuenta(dias, origen):
    cfg = await db.config.find_one({"_key": "cuenta_barrido"}) or {}
    rol = cfg.get("rol")
    if not rol:
        return {"error": "sin cuenta designada"}
    await db.config.update_one({"_key": "cuenta_barrido"}, {"$set": {
        "barrido_estado": "en_proceso", "barrido_inicio": _now(), "barrido_origen": origen}}, upsert=True)
    try:
        correos = await asyncio.to_thread(mail.fetch_recent_account, rol, dias)
        res = await _auditar_lote(correos)
        res["ruts_cosechados"] = await _cosechar_ruts_faltantes(correos)
        resumen = {k: v for k, v in res.items() if k != "detalle"}
        await db.config.update_one({"_key": "cuenta_barrido"}, {"$set": {
            "barrido_estado": "completado", "ultima_lectura": _now(),
            "barrido_origen": origen, "ultimo_resultado": resumen}}, upsert=True)
        return resumen
    except Exception as ex:
        logging.warning(f"barrido cuenta: {ex}")
        await db.config.update_one({"_key": "cuenta_barrido"}, {"$set": {
            "barrido_estado": f"error: {str(ex)[:120]}", "ultima_lectura": _now()}}, upsert=True)
        return {"error": str(ex)[:200]}


@supercarpeta.get("/cuenta-barrido")
async def cuenta_barrido_get():
    cfg = await db.config.find_one({"_key": "cuenta_barrido"}, {"_id": 0}) or {}
    disponibles = [{"rol": a["rol"], "correo": a["user"]} for a in mail.ACCOUNTS]
    correo = next((a["user"] for a in mail.ACCOUNTS if a["rol"] == cfg.get("rol")), "")
    return {"configurada": bool(cfg.get("rol")), "rol": cfg.get("rol", ""), "correo": correo,
            "activo": cfg.get("activo", True), "modo": "solo_lectura",
            "ultima_lectura": cfg.get("ultima_lectura", ""),
            "barrido_estado": cfg.get("barrido_estado", ""),
            "ultimo_resultado": cfg.get("ultimo_resultado") or {},
            "cuentas_disponibles": disponibles,
            "nota": "Lectura BODY.PEEK (solo lectura): jamás marca, mueve ni envía correos"}


@supercarpeta.post("/cuenta-barrido")
async def cuenta_barrido_set(payload: dict, request: Request):
    """Designa la casilla existente que actúa como Cuenta de Barrido (Solo Lectura)."""
    user = _exigir_gerencia(request)
    rol = (payload.get("rol") or "").strip().lower()
    if rol and rol not in [a["rol"] for a in mail.ACCOUNTS]:
        raise HTTPException(status_code=400, detail="Esa cuenta no existe en el sistema")
    upd = {"actualizado": _now(), "por": user.get("sub") or "gerencia"}
    if rol:
        upd["rol"] = rol
    if "activo" in payload:
        upd["activo"] = bool(payload.get("activo"))
    await db.config.update_one({"_key": "cuenta_barrido"}, {"$set": upd}, upsert=True)
    correo = next((a["user"] for a in mail.ACCOUNTS if a["rol"] == rol), "")
    if rol:
        await _log_fuente(user, "cuenta_barrido", "todas", "designar", correo,
                          "Cuenta de Barrido (Solo Lectura)")
    cfg = await db.config.find_one({"_key": "cuenta_barrido"}) or {}
    return {"ok": True, "rol": cfg.get("rol", ""), "correo": correo or "",
            "activo": cfg.get("activo", True)}


@supercarpeta.post("/cuenta-barrido/barrer")
async def cuenta_barrido_barrer(request: Request, dias: int = 7):
    """Barrido manual 'Barrer ahora': corre en segundo plano (solo lectura)."""
    _exigir_gerencia(request)
    cfg = await db.config.find_one({"_key": "cuenta_barrido"}) or {}
    if not cfg.get("rol"):
        raise HTTPException(status_code=400, detail="Primero designa la cuenta de barrido en el Panel ⚙️")
    d = min(max(int(dias or 7), 1), 90)
    asyncio.create_task(_ejecutar_barrido_cuenta(d, "manual"))
    return {"ok": True, "lanzado": True, "dias": d,
            "seguimiento": "GET /api/supercarpeta/cuenta-barrido"}


async def cuenta_barrido_loop():
    """Cada 20 min barre la cuenta designada (solo lectura) y persiste cada hallazgo
    en la carpeta y la Bóveda ADN (estados, PDFs firmados, RUTs, notaría)."""
    await asyncio.sleep(200)
    while True:
        try:
            cfg = await db.config.find_one({"_key": "cuenta_barrido"}) or {}
            if cfg.get("rol") and cfg.get("activo", True):
                await _ejecutar_barrido_cuenta(2, "automatico")
        except Exception as e:
            logging.warning(f"cuenta barrido loop: {e}")
        await asyncio.sleep(1200)


# ── AUDITORÍA DE BÓVEDA (Regla de Hierro): RUT en 4 fuentes + campos de identidad ──
def _rut_en_pdfs(nombre):
    """Busca un RUT válido (DV verificado) en el texto de los PDFs del cliente."""
    from base_historica import validar_rut_chileno as _v
    base = fsvc.folder_dir(nombre or "")
    if not base.exists():
        return "", ""
    from pypdf import PdfReader
    for p in sorted(base.rglob("*.pdf"))[:40]:
        try:
            rd = PdfReader(str(p))
            texto = ""
            for pg in rd.pages[:5]:
                texto += pg.extract_text() or ""
            for m in RUT_RE.findall(texto):
                if _v(m):
                    return m, p.name
        except Exception:
            continue
    return "", ""


async def _buscar_rut_cliente(fd, usados):
    """Orden obligatorio: 1) ficha ADN → 2) EXPEDIENTE_360 → 3) documentos → 4) correos 90d."""
    from base_historica import validar_rut_chileno as _v
    import json as _json
    nombre = (fd.get("nombre") or "").strip()
    toks = [t for t in nombre.lower().split() if len(t) > 2][:2]
    reg = None
    if toks:
        rx = ".*".join(re.escape(t) for t in toks)
        reg = await db.adn_clientes_360.find_one({"identidad.nombre": {"$regex": rx, "$options": "i"}})
    if reg and _v(reg.get("rut")) and _rut_limpio(reg["rut"]) not in usados:
        return reg["rut"], "ficha ADN_CLIENTES_360"
    if reg:
        blob = _json.dumps(reg.get("expediente_360") or {}, ensure_ascii=False, default=str)
        for m in RUT_RE.findall(blob):
            if _v(m) and _rut_limpio(m) not in usados:
                return m, "EXPEDIENTE_360"
    rut_doc, archivo = await asyncio.to_thread(_rut_en_pdfs, nombre)
    if rut_doc and _rut_limpio(rut_doc) not in usados:
        return rut_doc, f"documento ({archivo})"
    try:
        correos = await asyncio.to_thread(mail.fetch_since_text, 90, nombre, 15)
        for e in correos or []:
            texto = f"{e.get('subject', '')} {e.get('body', '')}"
            for m in RUT_RE.findall(texto):
                if _v(m) and _rut_limpio(m) not in usados:
                    return m, f"correo ({(e.get('subject') or '')[:60]})"
    except Exception:
        pass
    return "", ""


async def _auditoria_boveda_run(user_sub):
    """Audita los clientes activos de la flota: RUT (4 fuentes, escritura obligatoria)
    + campos de identidad. Cada hallazgo se ESCRIBE en la Bóveda ADN (Regla #66/#67)."""
    from base_historica import validar_rut_chileno as _v, _fmt_rut
    await db.config.update_one({"_key": "auditoria_boveda"}, {"$set": {
        "estado": "en_proceso", "inicio": _now()}}, upsert=True)
    try:
        flota_cfg = await db.config.find_one({"_key": "flota_agosto"}) or {}
        flota = {n.strip().upper() for n in (flota_cfg.get("nombres") or [])}
        folders = []
        async for fd in db.folders.find({"oculto_supercarpeta": {"$exists": False}}):
            nu = (fd.get("nombre") or "").strip().upper()
            if not flota or any(nf in nu or nu in nf for nf in flota):
                folders.append(fd)
        usados = {_rut_limpio(f.get("rut")) for f in folders if _v(f.get("rut"))}
        rep = {"clientes_auditados": len(folders), "con_rut_boveda": 0, "sin_rut_inicial": 0,
               "ruts_encontrados": [], "ruts_por_confirmar": [],
               "campos_vacios": 0, "campos_poblados": 0, "detalle_campos": [], "fecha": _now()}
        for fd in folders:
            ahora = _now()
            if _v(fd.get("rut")):
                rep["con_rut_boveda"] += 1
                await _sync_adn(fd["id"])
            else:
                rep["sin_rut_inicial"] += 1
                rut, fuente = await _buscar_rut_cliente(fd, usados)
                if rut:
                    rut_f = _fmt_rut(rut)
                    usados.add(_rut_limpio(rut))
                    await db.folders.update_one({"id": fd["id"]}, {"$set": {
                        "rut": rut_f, "rut_origen": f"auditoria_boveda:{fuente}", "updated_at": ahora}})
                    await db.estado_manual_log.insert_one({
                        "id": str(uuid.uuid4()), "folder_id": fd["id"], "cliente": fd.get("nombre") or "",
                        "hito": "identidad_rut", "estado_anterior": str(fd.get("rut") or ""),
                        "estado_nuevo": rut_f, "por": f"auditoria_boveda ({user_sub})",
                        "fecha": ahora, "inmutable": True})
                    await _sync_adn(fd["id"])
                    rep["ruts_encontrados"].append({"cliente": fd.get("nombre"), "rut": rut_f, "fuente": fuente})
                else:
                    await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "auditoria_boveda",
                        "mensaje": f"🔴 RUT Por Confirmar: {fd.get('nombre')} — no está en ficha ADN, "
                                   f"EXPEDIENTE_360, documentos ni correos de 90 días. Requiere ingreso manual.",
                        "fecha": ahora, "leida": False})
                    rep["ruts_por_confirmar"].append(fd.get("nombre"))
            # ── Campos de identidad: si está vacío en carpeta pero existe en ADN, se escribe ──
            rut_actual = fd.get("rut")
            if not _v(rut_actual):
                rut_actual = next((x["rut"] for x in rep["ruts_encontrados"]
                                   if x["cliente"] == fd.get("nombre")), None)
            reg = await db.adn_clientes_360.find_one({"rut_norm": _adn_norm(rut_actual)}) if rut_actual else None
            prop = (reg or {}).get("propiedad") or {}
            exp_p = ((reg or {}).get("expediente_360") or {}).get("propiedad") or {}
            ident = (reg or {}).get("identidad") or {}
            fuentes_campo = {
                "inmobiliaria": prop.get("inmobiliaria") or exp_p.get("inmobiliaria") or "",
                "proyecto": prop.get("proyecto") or exp_p.get("proyecto") or "",
                "ciudad": ident.get("ciudad") or exp_p.get("comuna") or prop.get("comuna") or "",
                "broker_origen": "Mutuaria y Leasing Limitada" if flota else "",
                "notaria": exp_p.get("notaria") or ""}
            upd = {}
            for campo, valor in fuentes_campo.items():
                if fd.get(campo):
                    continue
                if campo == "inmobiliaria" and "usad" in (fd.get("tipo_operacion") or "").lower():
                    continue
                rep["campos_vacios"] += 1
                if valor:
                    upd[campo] = valor
                    rep["campos_poblados"] += 1
                    rep["detalle_campos"].append({"cliente": fd.get("nombre"), "campo": campo, "valor": valor})
            fin_a = (reg or {}).get("financiero") or {}
            if not fd.get("proyeccion_uf"):
                rep["campos_vacios"] += 1
                if fin_a.get("monto_credito_uf"):
                    upd["proyeccion_uf"] = fin_a["monto_credito_uf"]
                    rep["campos_poblados"] += 1
                    rep["detalle_campos"].append({"cliente": fd.get("nombre"), "campo": "monto_uf",
                                                  "valor": fin_a["monto_credito_uf"]})
            if not fd.get("subsidio_proyeccion"):
                rep["campos_vacios"] += 1
                if fin_a.get("con_subsidio") is not None:
                    sub_v = "Con Subsidio" if fin_a["con_subsidio"] else "Sin Subsidio"
                    upd["subsidio_proyeccion"] = sub_v
                    rep["campos_poblados"] += 1
                    rep["detalle_campos"].append({"cliente": fd.get("nombre"), "campo": "subsidio", "valor": sub_v})
            if upd:
                await db.folders.update_one({"id": fd["id"]}, {"$set": {**upd, "updated_at": ahora}})
                await _sync_adn(fd["id"])
        rep["requieren_ingreso_manual"] = len(rep["ruts_por_confirmar"])
        await db.config.update_one({"_key": "auditoria_boveda"}, {"$set": {
            "estado": "completado", "ultima": _now(), "reporte": rep}}, upsert=True)
        return rep
    except Exception as ex:
        logging.warning(f"auditoria boveda: {ex}")
        await db.config.update_one({"_key": "auditoria_boveda"}, {"$set": {
            "estado": f"error: {str(ex)[:120]}", "ultima": _now()}}, upsert=True)
        return {"error": str(ex)[:200]}


def _adn_norm(rut):
    import adn_clientes as _adn
    return _adn._norm_rut(rut)


@supercarpeta.post("/auditoria-boveda")
async def auditoria_boveda_post(request: Request):
    """REGLA DE HIERRO: un cliente sin RUT es falla crítica — auditoría en segundo plano."""
    user = _exigir_gerencia(request)
    asyncio.create_task(_auditoria_boveda_run(user.get("sub") or "gerencia"))
    return {"ok": True, "lanzada": True, "seguimiento": "GET /api/supercarpeta/auditoria-boveda"}


@supercarpeta.get("/auditoria-boveda")
async def auditoria_boveda_get():
    return await db.config.find_one({"_key": "auditoria_boveda"}, {"_id": 0}) or {"estado": "nunca_ejecutada"}


async def migracion_reset_firmas():
    """LIMPIEZA DE ESTADOS FALSOS (una sola vez por BD): resetea TODA firma a Pendiente.
    Solo un correo fuente con evidencia real podrá volver a marcarla (bitácora incluida)."""
    if await db.config.find_one({"_key": "migracion_reset_firmas_v1"}):
        return
    reseteados = 0
    async for fd in db.folders.find({"$or": [
            {"escritura_confirmada_at": {"$exists": True}},
            {"firma_cesion_confirmada_at": {"$exists": True}},
            {"fecha_firma_detectada": {"$exists": True}},
            {"estado_manual.cesion.estado": {"$regex": "firm|confirm", "$options": "i"}},
            {"estado_manual.escritura.estado": {"$regex": "firm|confirm", "$options": "i"}}]}):
        unset = {k: "" for k in ("escritura_confirmada_at", "firma_cesion_confirmada_at",
                                 "fecha_firma_detectada") if fd.get(k)}
        em = fd.get("estado_manual") or {}
        for h in ("cesion", "escritura"):
            est = ((em.get(h) or {}).get("estado") or "")
            if re.search(r"firm|confirm", est, re.I):
                unset[f"estado_manual.{h}"] = ""
                await db.estado_manual_log.insert_one({
                    "id": str(uuid.uuid4()), "folder_id": fd["id"],
                    "cliente": fd.get("nombre") or "", "hito": h,
                    "estado_anterior": est, "estado_nuevo": "Pendiente",
                    "por": "sistema (limpieza de estados falsos de firma)",
                    "fecha": _now(), "inmutable": True})
        if unset:
            await db.folders.update_one({"id": fd["id"]}, {"$unset": unset})
            reseteados += 1
            await db.estado_manual_log.insert_one({
                "id": str(uuid.uuid4()), "folder_id": fd["id"],
                "cliente": fd.get("nombre") or "", "hito": "firma",
                "estado_anterior": "estado de firma sin respaldo de correo fuente",
                "estado_nuevo": "Pendiente",
                "por": "sistema (Regla de Hierro: la firma solo se confirma desde correo)",
                "fecha": _now(), "inmutable": True})
    await db.config.update_one({"_key": "migracion_reset_firmas_v1"}, {"$set": {
        "en": _now(), "carpetas_reseteadas": reseteados}}, upsert=True)
    logging.info(f"🧹 Reset de firmas falsas: {reseteados} carpeta(s) devueltas a Pendiente")


# ── REMITENTES DETECTADOS: revisión y control manual de la captura automática ──
@supercarpeta.get("/remitentes-detectados")
async def remitentes_detectados_get():
    items = []
    async for f in db.folders.find({"fuentes_detectadas": {"$exists": True}},
                                   {"id": 1, "nombre": 1, "fuentes_detectadas": 1}):
        for hito, lst in (f.get("fuentes_detectadas") or {}).items():
            for d in lst or []:
                items.append({**d, "cliente": f.get("nombre"), "folder_id": f["id"], "hito": hito})
    items.sort(key=lambda x: x.get("primera_vez", ""), reverse=True)
    bloqueados = (await db.config.find_one({"_key": "remitentes_bloqueados"}) or {}).get("correos") or []
    registro = [r async for r in db.remitentes_registro.find({}, {"_id": 0}).sort("ultima", -1).limit(50)]
    return {"detectados": items, "bloqueados": bloqueados, "registro": registro,
            "hitos_validos": list(FUENTES_HITOS)}


@supercarpeta.post("/remitentes-detectados/accion")
async def remitentes_accion(payload: dict, request: Request):
    """CONFIRMAR / REUBICAR / ELIMINAR / BLOQUEAR con aprendizaje acumulativo."""
    user = _exigir_gerencia(request)
    fid = payload.get("folder_id") or ""
    hito = (payload.get("hito") or "").strip()
    correo = (payload.get("correo") or "").strip().lower()
    accion = (payload.get("accion") or "").strip().lower()
    destino = (payload.get("hito_destino") or "").strip()
    if accion not in ("confirmar", "reubicar", "eliminar", "bloquear") or not correo:
        raise HTTPException(status_code=400, detail="Acción o correo inválido")
    fd = await db.folders.find_one({"id": fid})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    await db.folders.update_one({"id": fid}, {"$pull": {f"fuentes_detectadas.{hito}": {"correo": correo}}})
    if accion == "confirmar":
        await db.folders.update_one({"id": fid}, {"$addToSet": {f"fuentes_doc.{hito}": correo}})
    elif accion == "reubicar":
        if destino not in FUENTES_HITOS:
            raise HTTPException(status_code=400, detail=f"Hito destino inválido ({', '.join(FUENTES_HITOS)})")
        await db.folders.update_one({"id": fid}, {"$addToSet": {f"fuentes_doc.{destino}": correo}})
        reg = await db.remitentes_registro.find_one({"correo": correo}) or {}
        seguidas = (reg.get("reubicaciones") or 0) + 1 if reg.get("ultimo_destino") == destino else 1
        upd = {"ultimo_destino": destino, "reubicaciones": seguidas}
        if seguidas >= 2:
            upd["hito_forzado"] = destino  # aprendizaje permanente tras 2 correcciones iguales
        await db.remitentes_registro.update_one({"correo": correo}, {"$set": upd}, upsert=True)
    elif accion == "bloquear":
        await db.config.update_one({"_key": "remitentes_bloqueados"},
                                   {"$addToSet": {"correos": correo}}, upsert=True)
    await _log_fuente(user, "remitente_detectado", destino or hito or "todas", accion, correo,
                      "captura automática", fd.get("nombre") or "")
    await _sync_adn(fid)
    return {"ok": True, "accion": accion, "correo": correo,
            "aprendizaje": "el sistema ajusta su criterio con cada corrección de Gerencia"}


@supercarpeta.post("/cliente")
async def supercarpeta_cliente_agregar(payload: dict, request: Request):
    """P10 — Gerencia agrega un cliente manualmente: crea la ficha y la suma a la vista.
    Válvula operativa (el flujo normal es la carga automática desde la proyección del broker)."""
    user = _exigir_gerencia(request)
    nombre = (payload.get("nombre") or "").strip().upper()
    if len(nombre) < 5 or len(nombre.split()) < 2:
        raise HTTPException(status_code=400, detail="Nombre inválido (nombre y apellido)")
    if await db.folders.find_one({"nombre": {"$regex": f"^{re.escape(nombre)}$", "$options": "i"},
                                  "oculto_supercarpeta": {"$exists": False}}):
        raise HTTPException(status_code=409, detail="Ese cliente ya existe en la Supercarpeta")
    monto = payload.get("monto_uf")
    try:
        monto = float(str(monto).replace("$", "").replace(" ", "").replace(".", "").replace(",", ".")) if monto else None
    except Exception:
        monto = None
    ahora = _now()
    fd = {"id": str(uuid.uuid4()), "nombre": nombre, "rut": (payload.get("rut") or "").strip(),
          "inmobiliaria": (payload.get("inmobiliaria") or "").strip(),
          "proyecto": (payload.get("proyecto") or "").strip(),
          "ciudad": (payload.get("ciudad") or "").strip(),
          "tipo_operacion": "usada" if "usad" in (payload.get("tipo_propiedad") or "").lower() else
                            ((payload.get("tipo_propiedad") or "").strip().lower() or "nueva"),
          "subsidio_proyeccion": (payload.get("subsidio") or "").strip(),
          "proyeccion_uf": monto,
          "broker_origen": (payload.get("broker") or "Mutuaria y Leasing Limitada").strip(),
          "mes_proyeccion": ((payload.get("mes") or "").strip() or "2026-08"),
          "archivos": [], "created": ahora, "updated_at": ahora,
          "origen_alta": {"manual": True, "por": user.get("sub") or "gerencia", "en": ahora}}
    await db.folders.insert_one(dict(fd))
    cfg = await db.config.find_one({"_key": "flota_agosto"}) or {}
    if cfg.get("activo") and fd["mes_proyeccion"] == "2026-08":
        await db.config.update_one({"_key": "flota_agosto"}, {"$addToSet": {"nombres": nombre}})
    await db.supercarpeta_log.insert_one({
        "id": str(uuid.uuid4()), "accion": "cliente_agregado", "folder_id": fd["id"],
        "cliente": nombre, "por": user.get("sub") or "gerencia", "fecha": ahora, "inmutable": True})
    await _sync_adn(fd["id"])
    return {"ok": True, "id": fd["id"], "cliente": nombre,
            "nota": "Ficha creada y agregada a la vista; queda en bitácora inmutable"}


@supercarpeta.post("/mes-siguiente/{fid}")
async def supercarpeta_mes_siguiente(fid: str, request: Request, payload: dict = None):
    """TRASLADO MENSUAL: mueve al cliente a la proyección del mes siguiente conservando
    TODOS sus datos y estados. NUNCA borra nada; la ficha ADN queda íntegra + bitácora."""
    import adn_clientes as _adn
    user = _exigir_gerencia(request)
    fd = await db.folders.find_one({"id": fid})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    actual = fd.get("mes_proyeccion") or "2026-08"
    y, m = int(actual[:4]), int(actual[5:7])
    destino = (((payload or {}).get("mes_destino") or "").strip()
               or (f"{y + 1}-01" if m == 12 else f"{y}-{m + 1:02d}"))
    ahora = _now()
    await db.folders.update_one({"id": fid}, {"$set": {
        "mes_proyeccion": destino, "arrastre_desde": actual, "updated_at": ahora}})
    await db.estado_manual_log.insert_one({
        "id": str(uuid.uuid4()), "folder_id": fid, "cliente": fd.get("nombre") or "",
        "hito": "traslado_mes", "estado_anterior": actual, "estado_nuevo": destino,
        "por": user.get("sub") or "gerencia", "fecha": ahora, "inmutable": True})
    await db.config.update_one({"_key": f"proyeccion_{destino}"},
                               {"$setOnInsert": {"creada": ahora, "meta_uf": 0}}, upsert=True)
    if fd.get("rut"):
        await db.adn_clientes_360.update_one({"rut_norm": _adn._norm_rut(fd["rut"])}, {"$push": {
            "traslados": {"de": actual, "a": destino, "fecha": ahora,
                          "por": user.get("sub") or "gerencia"}}})
    await _sync_adn(fid)
    return {"ok": True, "cliente": fd.get("nombre"), "de": actual, "a": destino,
            "etiqueta": f"Arrastre {actual}",
            "regla": "El traslado nunca borra datos; la ficha ADN_CLIENTES_360 se conserva íntegra"}


@supercarpeta.post("/cliente/{fid}/eliminar")
async def supercarpeta_cliente_eliminar(fid: str, request: Request):
    """P10 — Elimina al cliente de la VISTA Supercarpeta. La ficha ADN_CLIENTES_360 se
    conserva como registro histórico. Bitácora inmutable con fecha, hora y usuario."""
    user = _exigir_gerencia(request)
    fd = await db.folders.find_one({"id": fid})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    ahora = _now()
    await db.folders.update_one({"id": fid}, {"$set": {
        "oculto_supercarpeta": {"en": ahora, "por": user.get("sub") or "gerencia"},
        "updated_at": ahora}})
    nombre_u = (fd.get("nombre") or "").strip().upper()
    await db.config.update_one({"_key": "flota_agosto"}, {"$pull": {"nombres": nombre_u}})
    await db.supercarpeta_log.insert_one({
        "id": str(uuid.uuid4()), "accion": "cliente_eliminado_vista", "folder_id": fid,
        "cliente": fd.get("nombre") or "", "por": user.get("sub") or "gerencia",
        "fecha": ahora, "inmutable": True,
        "nota": "Solo se ocultó de la vista; la ficha ADN se conserva como histórico"})
    return {"ok": True, "cliente": fd.get("nombre"),
            "nota": "Eliminado de la Supercarpeta; ficha ADN conservada como registro histórico"}


@supercarpeta.get("/panel/{fid}")
async def supercarpeta_panel(fid: str, hito: str = "tasacion"):
    """SECCIÓN 5 — Panel Lateral: fuentes activas, correos detectados, notas, bitácora."""
    fd = await db.folders.find_one({"id": fid})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    nombre = fd.get("nombre") or ""
    fu = await _fuentes_documentos()
    fuentes_hito = _correos_de((fd.get("fuentes_doc") or {}).get(hito)) or fu.get(hito) or []
    correos = await db.hitos_externos.find(
        {"folder_id": fid}, {"_id": 0, "hito": 1, "asunto": 1, "fecha": 1,
                             "fuente": 1, "direccion": 1, "creado": 1}).sort("creado", -1).to_list(15)
    rx = {"$regex": re.escape(nombre[:16]), "$options": "i"}
    envios = await db.correos_smtp_log.find(
        {"subject": rx}, {"_id": 0, "subject": 1, "to": 1, "fecha": 1, "success": 1}).sort("fecha", -1).to_list(8)
    log = await db.estado_manual_log.find(
        {"folder_id": fid, "hito": hito}, {"_id": 0}).sort("fecha", -1).to_list(30)
    notas = ((fd.get("notas_estados") or {}).get(hito)) or []
    bit = None
    if hito in ("tasacion", "estudio"):
        try:
            bit = await _bitacora_hito(fd, hito)
        except Exception:
            bit = None
    reparos = ""
    if hito == "estudio":
        reparos = " | ".join((r.get("texto") or "")[:300]
                             for r in (fd.get("reparos_alertas") or []) if not r.get("resuelto"))[:900]
    return {"cliente": nombre, "hito": hito, "fuentes": fuentes_hito,
            "correos_detectados": correos, "envios": envios,
            "notas": notas, "bitacora_cambios": log, "bitacora_tiempos": bit,
            "detalle_reparos": reparos,
            "estado_manual": (fd.get("estados_manuales") or {}).get(hito) or {}}


@supercarpeta.post("/nota/{fid}")
async def supercarpeta_nota(fid: str, payload: dict, request: Request):
    """SECCIÓN 5 — Notas manuales por estado, guardadas en la Bóveda ADN."""
    user = getattr(request.state, "user", {}) or {}
    hito = (payload.get("hito") or "").strip().lower()
    texto = (payload.get("texto") or "").strip()
    if hito not in HITOS_VALIDOS or not texto or len(texto) > 600:
        raise HTTPException(status_code=400, detail="Hito o nota inválida")
    fd = await db.folders.find_one({"id": fid})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    nota = {"texto": texto, "por": user.get("sub") or "usuario", "en": _now()}
    await db.folders.update_one({"id": fid}, {"$push": {f"notas_estados.{hito}": nota}})
    await _sync_adn(fid)
    return {"ok": True, "nota": nota}


@supercarpeta.get("/archivo/{fid}")
async def supercarpeta_archivo(fid: str, ruta: str):
    """VISUALIZADOR RÁPIDO: sirve el PDF para previsualizar sin entrar a la ficha."""
    fd = await db.folders.find_one({"id": fid})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    base = fsvc.folder_dir(fd.get("nombre") or "").resolve()
    p = (base / ruta).resolve()
    if not str(p).startswith(str(base)) or not p.exists() or not p.name.lower().endswith(".pdf"):
        raise HTTPException(status_code=404, detail="Informe no disponible")
    return Response(content=p.read_bytes(), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{p.name}"'})
