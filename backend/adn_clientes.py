"""Regla de Oro #66 — Bóveda Central de ADN de Clientes (ADN_CLIENTES_360).

Registro civil único de Central Mutuos. Acceso restringido por propiedad de cartera.
REGLA DE HIERRO: ningún dato entra sin pasar por el Validador de Dígito Verificador de RUT.
"""
import re
import uuid
import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from database import db
from base_historica import validar_rut_chileno
import expediente_identidad as _expid

adn = APIRouter(prefix="/adn")
_now = lambda: datetime.now(timezone.utc).isoformat()

CERTIFICACION = "Maserati Certificado: {n} Reglas Activas, Bóveda ADN Iniciada y Dashboard Gerencial Operativo"


def _norm_rut(rut):
    return re.sub(r"[^0-9kK]", "", str(rut or "")).lower()


def _registro_desde_folder(fd):
    df = fd.get("datos_financieros") or {}
    p = fd.get("perfil_consolidado") or {}
    ident = _expid.identidad_de_folder(fd)
    return {
        "rut": fd.get("rut") or "",
        "rut_norm": _norm_rut(fd.get("rut")),
        "codeudor_rut": ident.get("rut_codeudor") or fd.get("codeudor_rut") or "",
        "codeudor_rut_norm": ident.get("rut_codeudor_norm") or "",
        "rol_avaluo": ident.get("rol_avaluo") or "",
        "rol_norm": ident.get("rol_norm") or "",
        "identidad": {"nombre": fd.get("nombre") or "", "nombre_completo": fd.get("nombre_completo") or "",
                      "email": p.get("email") or "", "telefono": p.get("telefono") or "",
                      "ciudad": p.get("ciudad") or ""},
        "financiero": {"monto_credito_uf": df.get("monto_credito"), "valor_propiedad_uf": df.get("valor_propiedad"),
                       "plazo_anos": df.get("plazo_anos"), "tasa": df.get("tasa"),
                       "con_subsidio": bool(df.get("con_subsidio"))},
        "propiedad": {"inmobiliaria": fd.get("inmobiliaria") or "", "proyecto": fd.get("proyecto") or "",
                      "direccion": p.get("direccion") or "", "comuna": p.get("comuna") or "",
                      "rol": ident.get("rol_avaluo") or p.get("rol_propiedad") or "",
                      "tipo_operacion": fd.get("tipo_operacion") or ""},
        "titulos": {"estudio_recibido_at": fd.get("estudio_recibido_at") or "",
                    "estudio_terminado_at": fd.get("estudio_titulo_terminado_at") or ""},
        "tasacion": {"fecha": fd.get("tasacion_fecha") or "",
                     "informe_recibido_at": fd.get("tasacion_informe_recibido_at") or ""},
        "origen": {"folder_id": fd.get("id"), "broker_origen": fd.get("broker_origen") or "",
                   "ejecutivo": fd.get("ejecutivo") or fd.get("panel") or "", "fuente": "carpeta_activa"},
        "actualizado": _now(),
    }


def _registro_desde_historico(c):
    return {
        "rut": c.get("rut") or "",
        "rut_norm": _norm_rut(c.get("rut")),
        "identidad": {"nombre": c.get("nombre") or "", "nombre_completo": "",
                      "email": c.get("email") or "", "telefono": c.get("telefono") or "",
                      "ciudad": c.get("ciudad") or ""},
        "financiero": {}, "titulos": {}, "tasacion": {},
        "propiedad": {"inmobiliaria": c.get("inmobiliaria") or "", "proyecto": c.get("proyecto") or "",
                      "direccion": "", "comuna": "", "rol": "", "tipo_operacion": ""},
        "origen": {"folder_id": "", "broker_origen": "", "ejecutivo": "", "fuente": "minado_historico"},
        "actualizado": _now(),
    }


async def _extras_expediente(fd):
    """Simulación, compromiso, gastos y serie de crédito asociados a la carpeta."""
    rut_f = _norm_rut(fd.get("rut"))
    fid = fd.get("id")
    nombre = fd.get("nombre") or ""
    rx_nom = {"$regex": re.escape(nombre[:20]), "$options": "i"} if len(nombre) >= 3 else None

    async def _sim():
        if not rut_f:
            return {}
        return await db.simulaciones.find_one(
            {"rut": {"$regex": rut_f[:8], "$options": "i"}}, sort=[("timestamp", -1)]) or {}

    async def _comp():
        if not fid:
            return {}
        return await db.compromisos.find_one({"folder_id": fid}) or {}

    async def _por_rut_o_nombre(col, sort_campo):
        clauses = []
        if rut_f:
            clauses.append({"rut": {"$regex": rut_f[:8], "$options": "i"}})
        if rx_nom:
            clauses.append({"nombre": rx_nom})
        if not clauses:
            return None
        return await col.find_one({"$or": clauses}, sort=[(sort_campo, -1)])

    sim, comp, gastos, setc = await asyncio.gather(
        _sim(), _comp(),
        _por_rut_o_nombre(db.gastos_op_log, "enviado_en"),
        _por_rut_o_nombre(db.set_credito, "created_at"),
    )
    hilo = []
    if fid:
        try:
            async for h in db.hitos_externos.find(
                    {"folder_id": fid, "hito": {"$regex": "estudio", "$options": "i"}},
                    {"_id": 0, "hito": 1, "asunto": 1, "fecha": 1, "fuente": 1, "creado": 1}
            ).sort("creado", -1).limit(20):
                hilo.append(h)
        except Exception:
            hilo = []
    return {"simulacion": sim or {}, "compromiso": comp or {},
            "gastos": gastos, "set_credito": setc, "hilo_estudio": hilo}


async def _expediente_360(fd):
    """EXPEDIENTE_360 — réplica total: titular, codeudor (amarrado por RUT), rol de avalúo,
    perfil financiero, gastos, tasación, estudio de títulos, pólizas y serie de crédito."""
    extras = await _extras_expediente(fd)
    return _expid.construir_expediente(fd, extras)


async def _upsert_adn(reg):
    """REGLA DE HIERRO #66: sin RUT con dígito verificador válido, el registro NO entra."""
    if not validar_rut_chileno(reg.get("rut")):
        return False
    existente = await db.adn_clientes_360.find_one({"rut_norm": reg["rut_norm"]})
    if existente:
        # No degradar: solo completar vacíos y refrescar carpeta activa sobre histórico
        merged = dict(existente)
        for sec in ("identidad", "financiero", "propiedad", "titulos", "tasacion", "origen"):
            base = dict(existente.get(sec) or {})
            for k, v in (reg.get(sec) or {}).items():
                if v not in (None, "", 0) or not base.get(k):
                    if v not in (None, ""):
                        base[k] = v
            merged[sec] = base
        if reg.get("expediente_360"):
            merged["expediente_360"] = reg["expediente_360"]
            if existente.get("fuentes_succion"):
                merged["fuentes_succion"] = existente["fuentes_succion"]
        for k in ("codeudor_rut", "codeudor_rut_norm", "rol_avaluo", "rol_norm"):
            v = reg.get(k)
            if v not in (None, ""):
                merged[k] = v
        merged["actualizado"] = _now()
        merged.pop("_id", None)
        await db.adn_clientes_360.update_one({"rut_norm": reg["rut_norm"]}, {"$set": merged})
    else:
        reg["id"] = str(uuid.uuid4())
        reg["creado"] = _now()
        await db.adn_clientes_360.insert_one(reg)
    return True


async def volcar_adn():
    """ALIMENTACIÓN RETROACTIVA: carpetas activas + minado histórico → ADN_CLIENTES_360."""
    import hitos_ocr
    ok, rechazados, backfills = 0, 0, 0
    async for fd in db.folders.find({}):
        if backfills < 15 and hitos_ocr.folder_necesita_backfill(fd):
            try:
                r = await _backfill_hitos_folder(fd, permitir_ocr=False)
                if r.get("cambios"):
                    backfills += 1
                    fd = await db.folders.find_one({"id": fd.get("id")}) or fd
            except Exception as e:
                logging.warning(f"adn backfill {fd.get('nombre')}: {e}")
        reg = _registro_desde_folder(fd)
        exp = await _expediente_360(fd)
        reg["expediente_360"] = exp
        claves = exp.get("claves") or {}
        if claves.get("rut_codeudor_norm"):
            reg["codeudor_rut"] = claves.get("rut_codeudor") or reg.get("codeudor_rut") or ""
            reg["codeudor_rut_norm"] = claves["rut_codeudor_norm"]
        if claves.get("rol_norm"):
            reg["rol_avaluo"] = claves.get("rol_avaluo") or ""
            reg["rol_norm"] = claves["rol_norm"]
            (reg.setdefault("propiedad", {}))["rol"] = claves.get("rol_avaluo") or ""
        if await _upsert_adn(reg):
            ok += 1
        elif fd.get("rut"):
            rechazados += 1
    async for c in db.clientes_historicos.find({}):
        if c.get("rut"):
            if await _upsert_adn(_registro_desde_historico(c)):
                ok += 1
            else:
                rechazados += 1
    await db.config.update_one({"_key": "adn_volcado"}, {"$set": {
        "ultima": _now(), "procesados": ok, "rechazados_rut": rechazados,
        "hitos_releidos": backfills}}, upsert=True)
    return {"procesados": ok, "rechazados_rut": rechazados, "hitos_releidos": backfills}


def _mask_query(user):
    """MÁSCARA DE PRIVACIDAD (Regla #66): admin/maestro/Gerencia(B) global; el resto, su cartera."""
    rol = (user or {}).get("rol") or ""
    perfil = (user or {}).get("perfil") or ""
    if rol in ("admin", "maestro") or perfil == "B":
        return {}
    sub = str((user or {}).get("sub") or "")
    nombre = str((user or {}).get("nombre") or sub)
    cond = []
    if nombre:
        cond.append({"origen.broker_origen": {"$regex": re.escape(nombre[:25]), "$options": "i"}})
    if sub:
        cond.append({"origen.ejecutivo": {"$regex": re.escape(sub[:25]), "$options": "i"}})
    return {"$or": cond} if cond else {"_id": None}


async def _reglas_activas():
    doc = await db.config.find_one({"_key": "constitucion_maestra"}) or {}
    ns = [r.get("n", 0) for r in (doc.get("reglas") or [])]
    return max(ns) if ns else 0


@adn.get("/estado")
async def adn_estado():
    total = await db.adn_clientes_360.count_documents({})
    volcado = await db.config.find_one({"_key": "adn_volcado"}, {"_id": 0}) or {}
    n = await _reglas_activas()
    return {"registros": total, "ultimo_volcado": volcado,
            "certificacion": CERTIFICACION.format(n=n),
            "regla_hierro": "Ningún dato entra sin pasar el Validador de Dígito Verificador de RUT"}


@adn.post("/volcar")
async def adn_volcar(request: Request):
    user = getattr(request.state, "user", {}) or {}
    if (user.get("rol") or "") not in ("admin", "maestro"):
        raise HTTPException(status_code=403, detail="Solo el administrador puede ejecutar el volcado de ADN")
    r = await volcar_adn()
    return {"ok": True, **r}


@adn.get("/buscar")
async def adn_buscar(request: Request, q: str = "", limite: int = 50):
    user = getattr(request.state, "user", {}) or {}
    filtro = _mask_query(user)
    if q.strip():
        texto = _expid.filtro_busqueda(q)
        if texto:
            filtro = {"$and": [filtro, texto]} if filtro else texto
    docs = await db.adn_clientes_360.find(filtro, {"_id": 0}).sort("identidad.nombre", 1).to_list(min(limite, 200))
    return {"registros": docs, "total": len(docs),
            "acceso": "global" if not _mask_query(user) else "cartera_propia"}


@adn.get("/rut/{rut}")
async def adn_por_rut(request: Request, rut: str):
    user = getattr(request.state, "user", {}) or {}
    filtro = {"rut_norm": _norm_rut(rut)}
    mask = _mask_query(user)
    if mask:
        filtro = {"$and": [filtro, mask]}
    doc = await db.adn_clientes_360.find_one(filtro, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404,
                            detail="Registro no encontrado o fuera de su cartera (Regla #66 — privacidad)")
    return doc


async def _adn_por_clave(q):
    """Única supercarpeta: RUT titular, RUT codeudor o rol de avalúo."""
    raw = str(q or "").strip()
    if not raw:
        return None
    filtro = _expid.filtro_busqueda(raw)
    if filtro:
        doc = await db.adn_clientes_360.find_one(filtro, {"_id": 0})
        if doc:
            return doc
    ff = _expid.filtro_folder_por_clave(raw)
    if not ff:
        return None
    fd = await db.folders.find_one(ff)
    if not fd:
        return None
    exp = await _expediente_360(fd)
    reg = _registro_desde_folder(fd)
    reg["expediente_360"] = exp
    reg["fuente_resolucion"] = "carpeta_activa"
    return reg


def _puede_360(user):
    return (user.get("rol") or "") in ("admin", "maestro") or (user.get("perfil") or "") == "B"


@adn.get("/por-clave")
async def adn_por_clave(request: Request, q: str = ""):
    """Resuelve la carpeta única por RUT titular, RUT codeudor o Rol de Avalúo."""
    if not str(q or "").strip():
        raise HTTPException(status_code=400, detail="Indique RUT o rol de avalúo")
    doc = await _adn_por_clave(q)
    if not doc:
        raise HTTPException(status_code=404, detail="No hay supercarpeta con esa clave")
    user = getattr(request.state, "user", {}) or {}
    if not _puede_360(user):
        mask = _mask_query(user)
        if mask:
            propio = await db.adn_clientes_360.find_one(
                {"$and": [{"rut_norm": doc.get("rut_norm")}, mask]}, {"_id": 1})
            if not propio:
                raise HTTPException(status_code=403,
                                    detail="Regla #66: esta clave no pertenece a su cartera de gestión")
    clave = _expid.clasificar_clave(q)
    cruzada = ((doc.get("expediente_360") or {}).get("validacion_cruzada")
               or _expid.validar_identidad((doc.get("expediente_360") or {}).get("claves") or {}))
    return {**doc, "clave_usada": clave, "validacion_cruzada": cruzada,
            "acceso": "360_completo" if _puede_360(user) else "cartera_propia"}


@adn.get("/expediente/{rut}")
async def adn_expediente(request: Request, rut: str):
    """EXPEDIENTE_360 con MANDO ÚNICO DE ACCESO y búsqueda bidireccional titular↔codeudor↔rol."""
    rutn = _norm_rut(rut)
    roln = _expid.norm_rol(rut)
    if not rutn and not roln:
        raise HTTPException(status_code=400, detail="RUT o rol de avalúo inválido")
    doc = await _adn_por_clave(rut)
    if not doc:
        raise HTTPException(status_code=404, detail="Expediente no existe en la Bóveda ADN")
    user = getattr(request.state, "user", {}) or {}
    rol = user.get("rol") or ""
    perfil = user.get("perfil") or ""
    if rol in ("admin", "maestro") or perfil == "B":
        doc["acceso"] = "360_completo"
        return doc
    # MÁSCARA DE CARTERA también en piezas: el ejecutivo solo consulta RUTs de su gestión
    mask = _mask_query(user)
    if mask:
        propio = await db.adn_clientes_360.find_one({"$and": [{"rut_norm": doc.get("rut_norm")}, mask]},
                                                    {"_id": 1})
        if not propio:
            raise HTTPException(status_code=403,
                                detail="Regla #66: este RUT no pertenece a su cartera de gestión")
    # Ejecutivos: solo las piezas necesarias para su módulo (sin finanzas de codeudor ni CMF)
    exp = doc.get("expediente_360") or {}
    return {"rut": doc.get("rut"), "identidad": doc.get("identidad"),
            "propiedad": {k: v for k, v in (exp.get("propiedad") or {}).items()
                          if k in ("direccion", "comuna", "inmobiliaria", "proyecto", "rol")},
            "hitos_legales": exp.get("hitos_legales"),
            "claves": exp.get("claves") or {},
            "validacion_cruzada": exp.get("validacion_cruzada") or {},
            "acceso": "piezas_modulo (Regla #66)"}


@adn.get("/expediente/{rut}/autofill")
async def adn_autofill(request: Request, rut: str):
    """Payload para auto-rellenar Concreces desde el expediente único (sin envío)."""
    user = getattr(request.state, "user", {}) or {}
    doc = await _adn_por_clave(rut)
    if not doc:
        raise HTTPException(status_code=404, detail="Expediente no existe en la Bóveda ADN")
    if not _puede_360(user):
        mask = _mask_query(user)
        if mask:
            propio = await db.adn_clientes_360.find_one(
                {"$and": [{"rut_norm": doc.get("rut_norm")}, mask]}, {"_id": 1})
            if not propio:
                raise HTTPException(status_code=403,
                                    detail="Regla #66: este RUT no pertenece a su cartera de gestión")
    exp = dict(doc.get("expediente_360") or {})
    fid = (doc.get("origen") or {}).get("folder_id")
    if fid:
        fd = await db.folders.find_one({"id": fid})
        if fd:
            exp = await _expediente_360(fd)
    payload = _expid.payload_concreces(exp, financiero=doc.get("financiero"))
    cruzada = exp.get("validacion_cruzada") or _expid.validar_identidad(exp.get("claves") or {})
    return {
        "ok": True,
        "rut": doc.get("rut"),
        "folder_id": fid or "",
        "claves": exp.get("claves") or {},
        "validacion_cruzada": cruzada,
        "payload": payload,
        "mapeo": _expid.MAPEO_CONCRECES,
    }


async def _backfill_hitos_folder(fd, permitir_ocr=False):
    """Lee PDFs ya archivados (tasación/estudio/escritura) y llena huecos. No pisa renta/monto."""
    import folders_service as fsvc
    import hitos_ocr
    nombre = fd.get("nombre") or ""
    if not nombre:
        return {"folder_id": fd.get("id"), "cambios": 0, "motivo": "sin_nombre"}
    archivos = await asyncio.to_thread(fsvc.scan_archivos, nombre)
    por_hito = {"tasacion": [], "estudio_titulo": [], "escritura": []}
    for a in archivos:
        if not str(a.get("nombre") or "").lower().endswith(".pdf"):
            continue
        h = hitos_ocr.hito_de_rel(a.get("ruta") or "", a.get("nombre") or "")
        if h in por_hito:
            try:
                por_hito[h].append(fsvc.resolver_ruta(nombre, a["ruta"]))
            except (ValueError, OSError):
                pass
    ahora = _now()
    set_all, detalle = {}, []
    fd_work = dict(fd)
    fd_work["datos_financieros"] = dict(fd.get("datos_financieros") or {})
    for hito, paths in por_hito.items():
        if not paths:
            continue
        datos = await asyncio.to_thread(hitos_ocr.analizar_adjuntos, hito, paths[:4], permitir_ocr)
        campos = (datos or {}).get("campos") or {}
        if not campos:
            continue
        patch = hitos_ocr.patch_sin_pisar(fd_work, hito, campos, ahora)
        if not patch:
            continue
        set_all.update(patch)
        for k, v in patch.items():
            if k.startswith("datos_financieros."):
                fd_work["datos_financieros"][k.split(".", 1)[1]] = v
            else:
                fd_work[k] = v
        detalle.append({"hito": hito, "campos": sorted(campos.keys())})
    if set_all:
        set_all["updated_at"] = ahora
        await db.folders.update_one({"id": fd["id"]}, {"$set": set_all})
        fd2 = await db.folders.find_one({"id": fd["id"]}) or fd_work
        if fd2.get("rut"):
            try:
                reg = _registro_desde_folder(fd2)
                exp = await _expediente_360(fd2)
                reg["expediente_360"] = exp
                claves = exp.get("claves") or {}
                if claves.get("rol_norm"):
                    reg["rol_avaluo"] = claves.get("rol_avaluo") or ""
                    reg["rol_norm"] = claves["rol_norm"]
                if claves.get("rut_codeudor_norm"):
                    reg["codeudor_rut"] = claves.get("rut_codeudor") or ""
                    reg["codeudor_rut_norm"] = claves["rut_codeudor_norm"]
                await _upsert_adn(reg)
            except Exception as e:
                logging.warning(f"adn refresh post-backfill: {e}")
    return {"folder_id": fd.get("id"), "cliente": nombre, "cambios": len(set_all), "hitos": detalle}


@adn.post("/backfill-hitos")
async def adn_backfill_hitos(request: Request, payload: dict = None):
    """Admin: extrae rol/UF/fojas de PDFs ya en la carpeta. Sin OCR salvo pedido. Sin envío."""
    user = getattr(request.state, "user", {}) or {}
    if (user.get("rol") or "") not in ("admin", "maestro"):
        raise HTTPException(status_code=403, detail="Solo el administrador puede relleer hitos archivados")
    payload = payload or {}
    fid = str(payload.get("folder_id") or "").strip()
    permitir_ocr = bool(payload.get("permitir_ocr"))
    limite = max(1, min(int(payload.get("limite") or 25), 80))
    if fid:
        fd = await db.folders.find_one({"id": fid})
        if not fd:
            raise HTTPException(status_code=404, detail="Carpeta no existe")
        r = await _backfill_hitos_folder(fd, permitir_ocr=permitir_ocr)
        return {"ok": True, "procesados": 1, "con_cambios": 1 if r["cambios"] else 0, "detalle": [r]}
    detalle, con = [], 0
    carpetas = await db.folders.find({}).sort("nombre", 1).to_list(limite)
    for fd in carpetas:
        r = await _backfill_hitos_folder(fd, permitir_ocr=False)
        detalle.append(r)
        if r.get("cambios"):
            con += 1
    return {"ok": True, "procesados": len(detalle), "con_cambios": con, "detalle": detalle,
            "nota": "Solo texto embebido. OCR explícito: POST con folder_id y permitir_ocr."}


@adn.post("/succionar/{rut}")
async def adn_succionar(request: Request, rut: str):
    """MODO BODEGA SOBERANA: si falta un dato, se succiona del PDF histórico y queda para siempre."""
    user = getattr(request.state, "user", {}) or {}
    if (user.get("rol") or "") not in ("admin", "maestro"):
        raise HTTPException(status_code=403, detail="Solo el administrador puede succionar PDFs históricos")
    rutn = _norm_rut(rut)
    doc = await db.adn_clientes_360.find_one({"rut_norm": rutn})
    if not doc:
        raise HTTPException(status_code=404, detail="Expediente no existe en la Bóveda ADN")
    fid = (doc.get("origen") or {}).get("folder_id")
    fd = await db.folders.find_one({"id": fid}) if fid else None
    if not fd:
        raise HTTPException(status_code=404, detail="Sin carpeta local asociada al expediente")
    import folders_service as fsvc
    import ai_extract
    import ocr_service as _ocr
    paths = []
    for a in fsvc.scan_archivos(fd.get("nombre", "")):
        if a["nombre"].lower().endswith(".pdf"):
            try:
                paths.append((a["nombre"], fsvc.resolver_ruta(fd["nombre"], a["ruta"])))
            except (ValueError, OSError):
                pass
    texto, fuente_pdf = "", ""
    for nom, pth in paths[:4]:
        try:
            t = await asyncio.to_thread(_ocr.ocr_texto, pth.read_bytes(), 6) or ""
            if t:
                texto += "\n" + t
                fuente_pdf = fuente_pdf or nom
        except Exception:
            continue
    if not texto:
        raise HTTPException(status_code=422, detail="No hay PDFs legibles en la Bóveda Local para succionar")
    ext = await ai_extract.extraer_datos_compromiso(texto[:24000], fd.get("nombre", ""))
    exp = doc.get("expediente_360") or await _expediente_360(fd)
    fuentes = doc.get("fuentes_succion") or {}
    llenados = []
    e_prop = ext.get("propiedad") or {}
    mapa = {"direccion": "direccion", "comuna": "comuna", "rol_avaluo": "rol",
            "fojas": "fojas", "numero": "numero", "anio": "anio", "cbr": "cbr"}
    for k_src, k_dst in mapa.items():
        v = e_prop.get(k_src)
        if v and not (exp.get("propiedad") or {}).get(k_dst):
            exp.setdefault("propiedad", {})[k_dst] = str(v)
            fuentes[f"propiedad.{k_dst}"] = fuente_pdf
            llenados.append(k_dst)
    e_comp = ext.get("comprador") or {}
    if e_comp.get("profesion") and not (exp.get("titular") or {}).get("profesion"):
        exp.setdefault("titular", {})["profesion"] = str(e_comp["profesion"])
        fuentes["titular.profesion"] = fuente_pdf
        llenados.append("profesion")
    await db.adn_clientes_360.update_one({"rut_norm": rutn}, {"$set": {
        "expediente_360": exp, "fuentes_succion": fuentes, "actualizado": _now()}})
    return {"ok": True, "campos_succionados": llenados, "fuente_pdf": fuente_pdf,
            "detalle": "Datos guardados para siempre en la Bodega Soberana (Regla #66)"}


async def adn_loop():
    """Cosecha de ADN silenciosa: re-volcado interno cada 60 min (cero consultas a Gmail)."""
    await asyncio.sleep(180)
    while True:
        try:
            r = await volcar_adn()
            logging.info(f"🧬 ADN 360: {r['procesados']} registro(s), {r['rechazados_rut']} rechazado(s) por RUT")
        except Exception as e:
            logging.warning(f"adn loop: {e}")
        await asyncio.sleep(3600)
