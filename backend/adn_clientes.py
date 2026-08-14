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

adn = APIRouter(prefix="/adn")
_now = lambda: datetime.now(timezone.utc).isoformat()

CERTIFICACION = "Maserati Certificado: {n} Reglas Activas, Bóveda ADN Iniciada y Dashboard Gerencial Operativo"


def _norm_rut(rut):
    return re.sub(r"[^0-9kK]", "", str(rut or "")).lower()


def _registro_desde_folder(fd):
    df = fd.get("datos_financieros") or {}
    p = fd.get("perfil_consolidado") or {}
    return {
        "rut": fd.get("rut") or "",
        "rut_norm": _norm_rut(fd.get("rut")),
        "identidad": {"nombre": fd.get("nombre") or "", "nombre_completo": fd.get("nombre_completo") or "",
                      "email": p.get("email") or "", "telefono": p.get("telefono") or "",
                      "ciudad": p.get("ciudad") or ""},
        "financiero": {"monto_credito_uf": df.get("monto_credito"), "valor_propiedad_uf": df.get("valor_propiedad"),
                       "plazo_anos": df.get("plazo_anos"), "tasa": df.get("tasa"),
                       "con_subsidio": bool(df.get("con_subsidio"))},
        "propiedad": {"inmobiliaria": fd.get("inmobiliaria") or "", "proyecto": fd.get("proyecto") or "",
                      "direccion": p.get("direccion") or "", "comuna": p.get("comuna") or "",
                      "rol": p.get("rol_propiedad") or "", "tipo_operacion": fd.get("tipo_operacion") or ""},
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


async def _expediente_360(fd):
    """EXPEDIENTE_360 — réplica total: titular, codeudor (amarrado por RUT), propiedad
    con fojas/número/año, hitos legales y links verificables a la Bóveda Local."""
    rut_f = _norm_rut(fd.get("rut"))
    sim = {}
    if rut_f:
        sim = await db.simulaciones.find_one(
            {"rut": {"$regex": rut_f[:8], "$options": "i"}}, sort=[("timestamp", -1)]) or {}
    comp = await db.compromisos.find_one({"folder_id": fd.get("id")}) or {}
    cdat = comp.get("datos") or {}
    cprop = cdat.get("propiedad") or {}
    cvend = cdat.get("vendedor") or {}
    df = fd.get("datos_financieros") or {}
    p = fd.get("perfil_consolidado") or {}
    nombre_carpeta = fd.get("nombre") or ""
    documentos = [{"archivo": a, "link_boveda": f"{nombre_carpeta}/{a}", "fuente": "boveda_local"}
                  for a in (fd.get("archivos") or []) if isinstance(a, str)][:150]
    rep_raw = fd.get("estudio_reparos")
    rep_estado = rep_raw.get("estado", "") if isinstance(rep_raw, dict) else (rep_raw or "")
    rep_textos = " | ".join((r.get("texto") or "")[:250] for r in (fd.get("reparos_alertas") or [])[:5])
    return {
        "titular": {"nombre": fd.get("nombre_completo") or fd.get("nombre") or "",
                    "rut": fd.get("rut") or "",
                    "renta_liquida": sim.get("renta_liquida") or df.get("renta_liquida"),
                    "deudas_cmf": sim.get("carga_fin_individual"),
                    "afp": p.get("afp") or "",
                    "telefono": sim.get("telefono") or p.get("telefono") or "",
                    "email": sim.get("correo") or p.get("email") or ""},
        "codeudor": {"presente": bool(sim.get("tiene_codeudor")),
                     "rut": p.get("rut_codeudor") or "", "nombre": p.get("nombre_codeudor") or "",
                     "renta": sim.get("div_renta_codeudor"), "deudas_cmf": sim.get("carga_fin_codeudor"),
                     "afp": p.get("afp_codeudor") or "", "contacto": p.get("contacto_codeudor") or ""},
        "propiedad": {"direccion": cprop.get("direccion") or p.get("direccion") or "",
                      "comuna": cprop.get("comuna") or p.get("comuna") or "",
                      "rol": cprop.get("rol_avaluo") or p.get("rol_propiedad") or "",
                      "fojas": cprop.get("fojas") or "", "numero": cprop.get("numero") or "",
                      "anio": cprop.get("anio") or "", "cbr": cprop.get("cbr") or "",
                      "inmobiliaria": fd.get("inmobiliaria") or "", "proyecto": fd.get("proyecto") or "",
                      "tasacion": {"fecha": fd.get("tasacion_fecha") or "",
                                   "informe_recibido_at": fd.get("tasacion_informe_recibido_at") or "",
                                   "asunto_informe": fd.get("tasacion_informe_asunto") or ""},
                      "contacto_vendedor": {"nombre": cvend.get("nombre") or "", "rut": cvend.get("rut") or ""}},
        "hitos_legales": {"estudio_titulos_recibido": fd.get("estudio_recibido_at") or "",
                          "estudio_titulos_terminado": fd.get("estudio_titulo_terminado_at") or "",
                          "estudio_reparos": rep_textos or rep_estado,
                          "tasacion_estado": ("Informe Recibido" if fd.get("tasacion_informe_recibido_at")
                                              else "Visita" if fd.get("tasacion_fecha")
                                              else "Solicitada" if (fd.get("reclamos_gerencia") or {}).get("tasacion")
                                              else "Pendiente"),
                          "firma_cesion": ("Confirmada" if fd.get("firma_cesion_confirmada_at")
                                           or fd.get("escritura_confirmada_at")
                                           or fd.get("escritura_notaria_detectada_at") else "Pendiente"),
                          "reparos": rep_textos or rep_estado,
                          "borrador_escritura": fd.get("escritura_confirmada_at") or "",
                          "fecha_firma": fd.get("fecha_firma") or fd.get("fecha_firma_detectada") or "",
                          "anexos_notaria": fd.get("anexos_notaria") or ""},
        "documentos": documentos,
    }


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
    ok, rechazados = 0, 0
    async for fd in db.folders.find({}):
        reg = _registro_desde_folder(fd)
        reg["expediente_360"] = await _expediente_360(fd)
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
        "ultima": _now(), "procesados": ok, "rechazados_rut": rechazados}}, upsert=True)
    return {"procesados": ok, "rechazados_rut": rechazados}


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
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        texto = {"$or": [{"rut": rx}, {"identidad.nombre": rx}, {"identidad.email": rx},
                         {"propiedad.inmobiliaria": rx}, {"propiedad.proyecto": rx}]}
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


@adn.get("/expediente/{rut}")
async def adn_expediente(request: Request, rut: str):
    """EXPEDIENTE_360 con MANDO ÚNICO DE ACCESO y búsqueda bidireccional titular↔codeudor."""
    rutn = _norm_rut(rut)
    if not rutn:
        raise HTTPException(status_code=400, detail="RUT inválido")
    doc = await db.adn_clientes_360.find_one(
        {"$or": [{"rut_norm": rutn},
                 {"expediente_360.codeudor.rut": {"$regex": rutn[:8], "$options": "i"}}]}, {"_id": 0})
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
                          if k in ("direccion", "comuna", "inmobiliaria", "proyecto")},
            "hitos_legales": exp.get("hitos_legales"), "acceso": "piezas_modulo (Regla #66)"}


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
