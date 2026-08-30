"""BODEGA_DE_DATOS_CONCRECES (Módulo A) + GERENCIA_COMERCIAL (Torre de Control VIP).

Regla #24: sin RUT/Rol contrastados y respaldo OCR, el envío queda BLOQUEADO.
Regla #25: el reporte de Gerencia es la fuente oficial de metas (auditoría cada 6h).
"""
import io
import re
import os
import uuid
import bcrypt
import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from database import db
from criterios_data import now_iso

bodega = APIRouter(prefix="/bodega")
gerencia = APIRouter(prefix="/gerencia")
excepciones = APIRouter(prefix="/excepciones")
_now = lambda: datetime.now(timezone.utc).isoformat()
_rut_limpio = lambda r: re.sub(r"[^0-9kK]", "", str(r or "")).lower()

# PREPARACIÓN MÓDULO B: mapeo de campos del sistema de ingreso de Concreces
CONCRECES_MAPEO = {
    "Ingreso_Mesa": ["rut_titular", "rut_codeudor", "renta_promedio", "monto_credito_uf", "subsidio"],
    "Tasacion": ["rol_propiedad", "direccion", "comuna", "valor_propiedad_uf"],
    "Riesgo": ["deuda_cmf_total", "deuda_cmf_codeudor", "carga_financiera", "ltv"],
    "Escrituracion": ["notaria", "repertorio", "fecha_firma", "estado_notaria"],
}


async def _registro_bodega(fd):
    df = fd.get("datos_financieros") or {}
    comp = await db.compromisos.find_one({"folder_id": fd.get("id")}) or {}
    prop = (comp.get("datos") or {}).get("propiedad") or {}
    contraste = await db.bodega_contraste.find_one({"folder_id": fd.get("id")}, {"_id": 0}) or {}
    excep = await db.excepciones_log.find_one({"folder_id": fd.get("id"), "hito": "envio_bodega"})
    respaldo_ocr = bool(fd.get("datos_financieros_ocr_fecha")) and bool(df)
    try:
        import expediente_identidad as _expid
        ident = _expid.identidad_de_folder(fd, {"compromiso": comp})
        rol_prop = ident.get("rol_avaluo") or prop.get("rol") or df.get("rol_propiedad") or ""
        rut_cod = ident.get("rut_codeudor") or fd.get("codeudor_rut") or ""
    except Exception:
        ident = {}
        rol_prop = prop.get("rol") or df.get("rol_propiedad") or df.get("rol_avaluo") or ""
        rut_cod = fd.get("codeudor_rut") or ""
        tas = fd.get("tasacion_ocr") if isinstance(fd.get("tasacion_ocr"), dict) else {}
        rol_prop = rol_prop or tas.get("rol_avaluo") or ""
    return {
        "folder_id": fd.get("id"), "cliente": fd.get("nombre"),
        "rut_titular": fd.get("rut") or "", "rut_codeudor": rut_cod,
        "renta_promedio": df.get("renta_liquida"), "renta_codeudor": df.get("renta_codeudor"),
        "rol_propiedad": rol_prop,
        "direccion": prop.get("direccion") or "", "comuna": prop.get("comuna") or "",
        "monto_credito_uf": df.get("monto_credito"), "subsidio": bool(df.get("con_subsidio")),
        "inmobiliaria": fd.get("inmobiliaria") or prop.get("inmobiliaria") or "",
        "respaldo_ocr": respaldo_ocr,
        "contraste": contraste.get("estado", "pendiente"),
        "contraste_detalle": contraste.get("detalle", ""),
        "excepcion_autorizada": bool(excep),
        "excepcion_por": (excep or {}).get("usuario", ""),
        # REGLA DE HIERRO #24: sin respaldo OCR + contraste validado → envío bloqueado
        # REGLA #31: una Autorización de Excepción firmada desbloquea con registro inmutable
        "envio_bloqueado": not ((respaldo_ocr and contraste.get("estado") == "validado") or excep),
    }


@bodega.get("")
async def bodega_listar():
    regs = [await _registro_bodega(fd) async for fd in db.folders.find({}).sort("nombre", 1)]
    return {"registros": regs, "total": len(regs), "mapeo_concreces": CONCRECES_MAPEO}


@bodega.get("/autofill/{fid}")
async def bodega_autofill(fid: str):
    """Mismo payload que ADN: comercial y riesgo auto-rellenan sin doble digitación ni envío."""
    fd = await db.folders.find_one({"id": fid})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    import expediente_identidad as _expid
    rut = fd.get("rut") or ""
    exp = None
    if rut:
        filtro = _expid.filtro_busqueda(rut)
        doc = await db.adn_clientes_360.find_one(filtro, {"_id": 0}) if filtro else None
        if doc:
            exp = dict(doc.get("expediente_360") or {})
            if doc.get("financiero"):
                exp["financiero"] = doc["financiero"]
    if not exp:
        comp = await db.compromisos.find_one({"folder_id": fid}) or {}
        exp = _expid.construir_expediente(fd, {"compromiso": comp})
    payload = _expid.payload_concreces(exp)
    ident = exp.get("claves") or _expid.identidad_de_folder(fd)
    return {
        "ok": True,
        "folder_id": fid,
        "claves": ident,
        "validacion_cruzada": exp.get("validacion_cruzada") or _expid.validar_identidad(ident),
        "payload": payload,
        "mapeo": CONCRECES_MAPEO,
        "envio": "manual",
    }


@bodega.post("/contrastar/{fid}")
async def bodega_contrastar(fid: str):
    """MOTOR DE CONTRASTE RUT/ROL: el RUT es el eje. Si un dato no coincide, se EXPULSA."""
    fd = await db.folders.find_one({"id": fid})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    rut = _rut_limpio(fd.get("rut"))
    problemas = []
    if not rut or len(rut) < 8:
        problemas.append("RUT titular ausente o inválido en la carpeta")
    df = fd.get("datos_financieros") or {}
    if not df or not fd.get("datos_financieros_ocr_fecha"):
        problemas.append("Datos financieros sin respaldo OCR")
    comp = await db.compromisos.find_one({"folder_id": fid}) or {}
    prop = (comp.get("datos") or {}).get("propiedad") or {}
    tas = fd.get("tasacion_ocr") if isinstance(fd.get("tasacion_ocr"), dict) else {}
    try:
        import expediente_identidad as _expid
        ident = _expid.identidad_de_folder(fd, {"compromiso": comp})
        cruzada = _expid.validar_identidad(ident)
        rol_ok = bool(ident.get("rol_norm"))
        for a in cruzada.get("alertas") or []:
            if "coincide con el del titular" in a:
                problemas.append(f"EXPULSADO: {a}")
            elif "desalineado" in a:
                problemas.append(a)
        if ident.get("rut_titular_norm") and rut and ident["rut_titular_norm"] != rut:
            problemas.append(
                f"EXPULSADO: RUT consolidado ({ident.get('rut_titular_norm')}) no coincide con el titular ({rut})")
    except Exception:
        ident, cruzada, rol_ok = {}, {}, bool(prop.get("rol") or df.get("rol_propiedad") or tas.get("rol_avaluo"))
    if not rol_ok:
        problemas.append("Rol de Propiedad no registrado (pendiente validación SII)")
    rut_comp = _rut_limpio(((comp.get("datos") or {}).get("comprador") or {}).get("rut"))
    if rut and rut_comp and rut != rut_comp:
        problemas.append(f"EXPULSADO: RUT del compromiso ({rut_comp}) no coincide con el titular ({rut})")
    estado = "validado" if not problemas else ("expulsado" if any("EXPULSADO" in p for p in problemas) else "observado")
    doc = {"folder_id": fid, "estado": estado, "detalle": " · ".join(problemas) or "RUT y Rol contrastados al 100%",
           "contrastado_en": _now()}
    await db.bodega_contraste.update_one({"folder_id": fid}, {"$set": doc}, upsert=True)
    return doc


NOTARIA_RE = re.compile(r"notar[ií]a|firma\s+(faltante|pendiente)|falta\s+firma", re.I)

ALERTA_SIN_INMOBILIARIA = "⚠️ Falta Identidad de Inmobiliaria"


def _origen_folder(fd):
    """Regla #58: prohibido 'Directo'. Prioridad: Inmobiliaria (individualizada) > Broker > Usado > alerta."""
    inmo = (fd.get("inmobiliaria") or "").strip()
    if inmo and inmo != "—":
        proy = (fd.get("proyecto") or "").strip()
        return f"{inmo.upper()} · {proy.upper()}" if proy else inmo.upper()
    broker = (fd.get("broker_origen") or fd.get("broker_nombre") or "").strip()
    if broker and broker.upper() != "DIRECTO":
        return f"BROKER · {broker.upper()}"
    if (fd.get("tipo_operacion") or "").lower() == "usada":
        return "USADO"
    return ALERTA_SIN_INMOBILIARIA


async def _hitos(fd, cache=None):
    import malla_inteligencia as _mi
    _firmas_info = _mi.firmas_folder(fd)
    fid, nombre = fd.get("id"), fd.get("nombre") or ""
    n_arch = len(fd.get("archivos") or []) or await db.fs_indice.count_documents({"folder_id": fid}) if False else len(fd.get("archivos") or [])
    if cache is not None:
        # REFACCIÓN DE COMPLEJIDAD: sin N+1 — todo pre-cargado en un solo viaje a Mongo
        reg = cache["contraste"].get(fid) or {}
        conc = cache["concreces"].get(fid) or {}
        clave = nombre[:20].lower()
        segs = [s for s in cache["seguimiento"] if clave and clave in (s.get("cliente") or "").lower()]
        seg = segs[0] if segs else {}
        alerta_notaria = next((s.get("asunto", "")[:120] for s in segs[:20]
                               if NOTARIA_RE.search(s.get("asunto") or "")), "")
    else:
        reg = await db.bodega_contraste.find_one({"folder_id": fid}) or {}
        conc = await db.concreces_estado.find_one({"folder_id": fid}) or {}
        seg = await db.seguimiento.find_one(
            {"cliente": {"$regex": re.escape(nombre[:20]), "$options": "i"}}, sort=[("fecha", -1)]) or {}
        alerta_notaria = ""
        async for s in db.seguimiento.find({"cliente": {"$regex": re.escape(nombre[:20]), "$options": "i"}}).limit(20):
            if NOTARIA_RE.search(s.get("asunto") or ""):
                alerta_notaria = (s.get("asunto") or "")[:120]
                break
    df = fd.get("datos_financieros") or {}
    # ── ORDEN SUPREMA: la Bóveda ADN_CLIENTES_360 manda en TODOS los módulos ──
    adn = None
    if fd.get("rut"):
        try:
            import adn_clientes as _adn
            adn = await db.adn_clientes_360.find_one({"rut_norm": _adn._norm_rut(fd["rut"])})
        except Exception:
            adn = None
    fin_a = (adn or {}).get("financiero") or {}
    prop_a = (adn or {}).get("propiedad") or {}
    exp_p = ((adn or {}).get("expediente_360") or {}).get("propiedad") or {}
    ident_a = (adn or {}).get("identidad") or {}
    monto_v = df.get("monto_credito") or fd.get("proyeccion_uf") or fin_a.get("monto_credito_uf")
    sub_v = (bool(df.get("con_subsidio")) or "con" in (fd.get("subsidio_proyeccion") or "").lower()
             or fin_a.get("con_subsidio") is True)
    proyecto_v = fd.get("proyecto") or prop_a.get("proyecto") or exp_p.get("proyecto") or ""
    ciudad_v = fd.get("ciudad") or ident_a.get("ciudad") or exp_p.get("comuna") or prop_a.get("comuna") or ""
    inmob_v = fd.get("inmobiliaria") or prop_a.get("inmobiliaria") or exp_p.get("inmobiliaria") or ""
    # ESCRITURA OBLIGATORIA + ALERTA DE INCONSISTENCIA (Corrección 5): reparación inmediata
    repara = {}
    for campo, v_fd, v_adn in (("proyecto", fd.get("proyecto"), proyecto_v),
                               ("ciudad", fd.get("ciudad"), ciudad_v),
                               ("inmobiliaria", fd.get("inmobiliaria"), inmob_v),
                               ("proyeccion_uf", fd.get("proyeccion_uf") or df.get("monto_credito"), monto_v)):
        if not v_fd and v_adn:
            repara[campo] = v_adn
    if repara:
        await db.folders.update_one({"id": fid}, {"$set": repara})
        if not fd.get("alerta_lectura_enviada"):
            await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "lectura_boveda",
                "mensaje": f"🔴 Campo(s) {', '.join(repara)} vacío(s) para {nombre}. Dato disponible en bóveda. "
                           f"Error de lectura detectado y reparado automáticamente.",
                "fecha": now_iso(), "leida": False})
            await db.folders.update_one({"id": fid}, {"$set": {"alerta_lectura_enviada": True}})
    return {
        "folder_id": fid, "cliente": nombre, "rut": fd.get("rut") or "",
        "broker_origen": fd.get("broker_origen") or fd.get("broker_nombre") or "",
        "origen": _origen_folder(fd),  # Regla #58: nunca 'Directo'
        "monto_credito_uf": monto_v,
        "subsidio": sub_v,
        "resolucion_serviu": bool(df.get("resolucion_serviu")),
        "tipo_vivienda": (str(df.get("tipo_vivienda") or "").lower()
                          if str(df.get("tipo_vivienda") or "").lower() in ("nueva", "usada")
                          else ("usada" if (fd.get("tipo_operacion") or "").lower() == "usada" else "nueva")),
        "inmobiliaria": inmob_v,
        "proyecto": proyecto_v,
        "ciudad": ciudad_v,
        "notaria_nombre": fd.get("notaria") or "",
        "notaria_estado_escritura": ("Escritura Lista Para Firmar" if fd.get("escritura_notaria_detectada_at")
                                     else "En Preparación" if fd.get("escritura_solicitada_at")
                                     else "Pendiente"),
        "escritura_firmada": bool(fd.get("escritura_confirmada_at")),
        "documentacion": "ok" if fd.get("datos_financieros_ocr_fecha") else ("proceso" if n_arch else "bloqueo"),
        "firma_set": "ok" if fd.get("set_firmado") else ("proceso" if fd.get("set_enviado") else "pendiente"),
        "ingreso_concreces": conc.get("estado", "pendiente"),
        "notaria": "alerta" if alerta_notaria else (conc.get("notaria", "pendiente")),
        "alerta_notaria": alerta_notaria,
        "estado_mesa": seg.get("estado", ""),
        "contraste": reg.get("estado", "pendiente"),
        # Regla #37: distinguir claramente USADA vs INMOBILIARIA en Gerencia
        "tipo_operacion": (fd.get("tipo_operacion") or "").upper(),
        # Regla #43: estado real por correos — sin respaldo = Pendiente de Información
        "tasacion_estado": ("ok" if fd.get("tasacion_informe_recibido_at")
                            else ("proceso" if fd.get("tasacion_solicitada_at") else "pendiente_informacion")),
        "estudio_estado": ("alerta" if (fd.get("reparos_alertas") or [])
                           else ("ok" if fd.get("estudio_recibido_at")
                                 else ("proceso" if fd.get("estudio_titulo_solicitado_at") else "pendiente_informacion"))),
        "reparos_pendientes": len(fd.get("reparos_alertas") or []),
        # RADAR DE ESCRITURACIÓN: Documentación 2.0 + Log de Firmas + Fecha de Firma
        "doc20": _mi.doc20_folder(fd),
        "firmas": _firmas_info[0], "hito_firmas": _firmas_info[1],
        "fecha_firma": fd.get("fecha_firma") or fd.get("fecha_firma_detectada") or "",
    }


@gerencia.get("/cartera")
async def gerencia_cartera():
    mes = datetime.now(timezone.utc).strftime("%Y-%m")
    ahora = datetime.now(timezone.utc)
    filas = []
    flota_cfg = await db.config.find_one({"_key": "flota_agosto"}) or {}
    flota = {n.strip().upper() for n in (flota_cfg.get("nombres") or [])} if flota_cfg.get("activo") else set()
    cache = {
        "contraste": {d.get("folder_id"): d async for d in db.bodega_contraste.find({})},
        "concreces": {d.get("folder_id"): d async for d in db.concreces_estado.find({})},
        "seguimiento": await db.seguimiento.find(
            {}, {"cliente": 1, "estado": 1, "asunto": 1, "fecha": 1}).sort("fecha", -1).to_list(3000),
    }
    async for fd in db.folders.find({}).sort("nombre", 1):
        if flota:
            # REGLA DE HIERRO (Flota Agosto): solo existe la flota autorizada en las vistas
            nombre_u = (fd.get("nombre") or "").strip().upper()
            if not any(nf in nombre_u or nombre_u in nf for nf in flota):
                continue
        act = (fd.get("updated_at") or fd.get("created") or fd.get("created_at") or "")[:7]
        if flota or act == mes or (fd.get("datos_financieros") or {}).get("monto_credito"):
            h = await _hitos(fd, cache)
            # COLUMNA DE DIVERGENCIA: inconsistencia detectada por Módulo Control (Regla #35)
            h["divergencia_control"] = bool(await _difs_folder(fd))
            # BLOQUEO DE DATOS INCOMPLETOS: sin RUT, Monto o Inmobiliaria → Broker no actualizado
            # REGLA DE HIERRO (Exp. 360): prohibido reportar 'datos incompletos' si la info
            # está en la historia documental (perfil consolidado / Bóveda ADN)
            p_inc = fd.get("perfil_consolidado") or {}
            h["datos_incompletos"] = not (
                (h.get("rut") or p_inc.get("rut")) and
                (h.get("monto_credito_uf") or p_inc.get("monto_credito")) and
                (h.get("inmobiliaria") or p_inc.get("inmobiliaria")
                 or (fd.get("tipo_operacion") or "").lower() == "usada"))
            # ALERTA DE INACTIVIDAD 96H
            ult = fd.get("updated_at") or fd.get("created_at") or fd.get("created") or ""
            try:
                dt_u = datetime.fromisoformat(str(ult)).astimezone(timezone.utc)
                h["inactivo_96h"] = (ahora - dt_u).total_seconds() > 96 * 3600
            except Exception:
                h["inactivo_96h"] = True
            h["reclamos"] = fd.get("reclamos_gerencia") or {}
            h["actualizado"] = str(ult)[:10]
            h["creado"] = str(fd.get("created_at") or "")[:10]
            h["dicom"] = bool((fd.get("datos_financieros") or {}).get("morosidad_dicom"))
            filas.append(h)
    # Regla #58: cartera ordenada por Inmobiliaria/Usado, cada inmobiliaria individualizada; alertas al final
    filas.sort(key=lambda f: (f["origen"] == ALERTA_SIN_INMOBILIARIA, f["origen"], f["cliente"]))
    energia = await db.config.find_one({"_key": "energia"}) or {}
    gasto = round((int(energia.get("llamadas_llm") or 0) - int(energia.get("llamadas_base") or 0)) * 0.12, 2)
    audit = await db.config.find_one({"_key": "gerencia_audit"}) or {}
    excs = await db.excepciones_log.find({}, {"_id": 0}).sort("fecha", -1).to_list(5)
    # CABECERA SEGMENTADA: Subsidio / Sin Subsidio / Total
    con_sub = [f for f in filas if f.get("subsidio")]
    sin_sub = [f for f in filas if not f.get("subsidio")]
    _uf = lambda fs: round(sum(float(f.get("monto_credito_uf") or 0) for f in fs), 2)
    return {"mes": mes, "cartera": filas, "total": len(filas),
            "resumen": {"subsidio": {"n": len(con_sub), "uf": _uf(con_sub)},
                        "sin_subsidio": {"n": len(sin_sub), "uf": _uf(sin_sub)},
                        "total": {"n": len(filas), "uf": _uf(filas)}},
            "brokers": sorted({f["origen"] for f in filas}),
            "costo_desarrollo_creditos": gasto,
            "ultima_auditoria_dashai": audit.get("fecha", ""),
            "excepciones_recientes": excs,
            "cumplimiento_broker": await db.config.find_one({"_key": "avance_global_2026-08"}, {"_id": 0}) or {},
            "alertas_notaria": sum(1 for f in filas if f["notaria"] == "alerta")}


# ── MANDO MANUAL DE GERENCIA (Reglas #49 y #52) — Rodrigo decide, DashAI provee ─
RECLAMOS_DEF = {
    "tasacion": ("Reclamo de Tasación Pendiente", "victoria"),
    "serviu": ("Reclamo de Resolución SERVIU", None),
    "actualizacion": ("Reclamo de Actualización Documental", "daniela"),
    "firmas": ("Reclamo de Firmas Pendientes", None),
    "movimiento": ("Reclamo de Movimiento — carpeta sin actividad 96 horas", None),
}


def _reclamo_html(titulo, cliente, rut, cuerpo):
    return (
        '<div style="max-width:600px;margin:0 auto;font-family:Arial,Helvetica,sans-serif;'
        'color:#000;background:#fff;padding:18px;">'
        f'<h2 style="font-size:17px;margin:0 0 4px;">{titulo}</h2>'
        '<p style="font-size:13px;margin:0 0 14px;">Central Mutuos — Gerencia Comercial</p>'
        f'<p style="font-size:14px;margin:0 0 12px;"><b>Cliente:</b> {cliente}<br/><b>RUT:</b> {rut or "—"}</p>'
        f'<p style="font-size:13px;line-height:1.6;margin:0 0 14px;">{cuerpo}</p>'
        '<p style="font-size:12px;margin:14px 0 0;">Agradeceremos gestionar este requerimiento a la '
        'brevedad e informar su avance respondiendo este correo.</p>'
        '</div>')


@gerencia.post("/reclamo/{fid}")
async def gerencia_reclamo(fid: str, payload: dict, request: Request):
    """ACCIÓN ÚNICA (Regla #49): el mail SOLO sale cuando Rodrigo pincha el botón."""
    tipo = (payload.get("tipo") or "").strip()
    if tipo not in RECLAMOS_DEF:
        raise HTTPException(status_code=400, detail="Tipo de reclamo inválido")
    fd = await db.folders.find_one({"id": fid})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    titulo, cc_panel = RECLAMOS_DEF[tipo]
    # Destinatario: correo del Broker responsable
    destinatario = (payload.get("destinatario") or "").strip()
    if not destinatario:
        cfgb = await db.correos_ejecutivos.find_one({"codigo": fd.get("broker_codigo") or "‽"}) or {}
        usr = await db.users.find_one({"codigo": fd.get("broker_codigo") or "‽"}) or {}
        destinatario = cfgb.get("email") or usr.get("email") or ""
    if not destinatario:
        raise HTTPException(status_code=400,
            detail="El Broker no tiene correo configurado — indique el destinatario o pida al Broker configurar 'Mi Correo'")
    cc = []
    if cc_panel:  # MANTENER COPIAS: Victoria (Tasación) · Daniela (Actualizaciones)
        cfg = await db.config.find_one({"_key": f"fuentes_imap_{cc_panel}"}) or {}
        if cfg.get("correo_principal"):
            cc.append(cfg["correo_principal"])
    cuerpo = ((payload.get("mensaje") or "").strip()
              or f"Se requiere su gestión inmediata sobre el hito «{titulo}» de la operación indicada, "
                 "actualmente pendiente en nuestro tablero de Gerencia Comercial.")
    subject = f"{titulo} — {fd.get('nombre','')}"
    body = _reclamo_html(titulo, fd.get("nombre", ""), fd.get("rut", ""), cuerpo)
    exigir("responsividad_absoluta", html=body)
    exigir("purificacion_correos", subject=subject, html=body)
    res = await asyncio.to_thread(_mail.send_mail, destinatario, subject, body, cc or None)
    if not (res or {}).get("success"):
        raise HTTPException(status_code=502, detail=(res or {}).get("error", "Error de envío"))
    claims = getattr(request.state, "user", None) or {}
    marca = {"fecha": _now(), "por": claims.get("nombre", claims.get("sub", "")),
             "destinatario": destinatario, "cc": cc}
    await db.folders.update_one({"id": fid}, {"$set": {f"reclamos_gerencia.{tipo}": marca}})
    # LOG DE GESTIÓN GERENCIAL (Regla #52): cada clic queda auditado
    await db.gestion_gerencial_log.insert_one({
        "id": str(uuid.uuid4()), "usuario": claims.get("nombre", claims.get("sub", "")),
        "accion": f"reclamo_{tipo}", "cliente": fd.get("nombre", ""), "rut": fd.get("rut", ""),
        "destinatario": destinatario, "cc": cc, "fecha": _now()})
    return {"ok": True, "tipo": tipo, "destinatario": destinatario, "cc": cc,
            "solicitado_el": marca["fecha"],
            "regla": "#49 — Ningún reclamo sale sin la intervención de Gerencia"}


@gerencia.get("/gestion-log")
async def gerencia_gestion_log():
    regs = await db.gestion_gerencial_log.find({}, {"_id": 0}).sort("fecha", -1).to_list(100)
    return {"gestion": regs, "total": len(regs)}


@gerencia.get("/export-xlsx")
async def gerencia_export():
    from openpyxl import Workbook
    data = await gerencia_cartera()
    wb = Workbook()
    ws = wb.active
    ws.title = f"Cartera {data['mes']}"
    ws.append(["Cliente", "Origen (Regla #58)", "RUT", "Tipo Operación", "Monto Crédito (UF)", "Subsidio", "Inmobiliaria",
               "Documentación", "Doc 2.0", "Firmas", "Fecha Firma", "Firma Set", "Ingreso Concreces", "Notaría", "Estado Mesa", "Alerta Notaría"])
    for f in data["cartera"]:
        firmas_txt = " · ".join(f"{x['label']}: {x['estado']}" for x in (f.get("firmas") or []))
        doc20 = f.get("doc20") or {}
        doc20_txt = "OK" if doc20.get("estado") == "ok" else "Pendiente de Información: " + ", ".join(doc20.get("faltantes") or [])
        ws.append([f["cliente"], f.get("origen") or ALERTA_SIN_INMOBILIARIA, f["rut"], f.get("tipo_operacion") or "—", f["monto_credito_uf"], "Sí" if f["subsidio"] else "No",
                   f["inmobiliaria"], f["documentacion"], doc20_txt, firmas_txt, f.get("fecha_firma") or "—",
                   f["firma_set"], f["ingreso_concreces"],
                   f["notaria"], f["estado_mesa"], f["alerta_notaria"]])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="Reporte_Gerencia_{data["mes"]}.xlsx"'})


async def gerencia_audit_loop():
    """Regla #25: DashAI audita el avance de la cartera cada 6 horas."""
    await asyncio.sleep(60)
    while True:
        try:
            data = await gerencia_cartera()
            await db.config.update_one({"_key": "gerencia_audit"}, {"$set": {
                "fecha": _now(), "total": data["total"],
                "alertas_notaria": data["alertas_notaria"]}}, upsert=True)
        except Exception as e:
            logging.warning(f"gerencia audit: {e}")
        await asyncio.sleep(6 * 3600)


@excepciones.post("/autorizar")
async def excepcion_autorizar(payload: dict, request: Request):
    """PROTOCOLO DE EXCEPCIÓN (Regla #31): re-valida la clave del ejecutivo, exige
    justificación y graba registro INMUTABLE. Notifica a Gerencia Comercial."""
    claims = getattr(request.state, "user", None) or {}
    codigo = claims.get("sub") or claims.get("codigo") or ""
    clave = (payload.get("clave") or "").strip()
    justificacion = (payload.get("justificacion") or "").strip()
    folder_id = (payload.get("folder_id") or "").strip()
    hito = (payload.get("hito") or "envio_bodega").strip()
    if len(justificacion) < 10:
        raise HTTPException(status_code=400, detail="La Justificación de la Excepción es obligatoria (mínimo 10 caracteres)")
    user = await db.users.find_one({"codigo": {"$regex": f"^{re.escape(codigo)}$", "$options": "i"}})
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no identificado")
    # FIRMA DIGITAL: re-validación de la clave del propio ejecutivo
    ok = False
    if user.get("clave_hash"):
        ok = bool(clave) and bcrypt.checkpw(clave.encode(), user["clave_hash"].encode())
    else:
        ok = bool(clave) and user.get("password") == clave
    if not ok and user.get("rol") == "admin":
        import auth as _auth_pin
        ok = _auth_pin.master_pin_ok(clave)
    if not ok:
        raise HTTPException(status_code=403, detail="Clave incorrecta — la excepción exige su firma digital")
    fd = await db.folders.find_one({"id": folder_id}) or {}
    reg = {"id": str(uuid.uuid4()), "usuario": user.get("nombre", codigo), "codigo": codigo,
           "rut_usuario": user.get("rut", codigo), "perfil": user.get("perfil", ""),
           "folder_id": folder_id, "cliente": fd.get("nombre", ""), "hito": hito,
           "justificacion": justificacion, "fecha": _now(), "inmutable": True}
    await db.excepciones_log.insert_one(dict(reg))
    await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "excepcion",
        "mensaje": f"⚠️ EXCEPCIÓN AUTORIZADA por {reg['usuario']} — hito '{hito}' de {reg['cliente'] or folder_id}: {justificacion[:120]}",
        "fecha": _now(), "leida": False})
    return {"ok": True, "registro": {k: v for k, v in reg.items() if k != "_id"}}


@excepciones.get("")
async def excepciones_listar():
    """Registro de auditoría INMUTABLE: sin endpoints de borrado ni edición."""
    regs = await db.excepciones_log.find({}, {"_id": 0}).sort("fecha", -1).to_list(200)
    return {"excepciones": regs, "total": len(regs)}


# ═════════ MÓDULO CONTROL — AUDITOR INFORMATIVO (Regla de Oro #35) ═════════
# Detecta y documenta discrepancias entre la Bodega y el Ingreso de Concreces.
# NO-INTERFERENCIA: un hallazgo JAMÁS bloquea la operación; solo marca e informa.
import email_service as _mail
from constitucion import exigir

control = APIRouter(prefix="/control")

CAMPOS_CONTROL = {
    "rut_titular": "RUT Titular", "rut_codeudor": "RUT Codeudor",
    "renta_promedio": "Renta Promedio", "monto_credito_uf": "Monto Crédito UF",
    "rol_propiedad": "Rol Propiedad", "direccion": "Dirección", "subsidio": "Subsidio",
}


async def _difs_folder(fd):
    conc = await db.concreces_estado.find_one({"folder_id": fd.get("id")}) or {}
    ingreso = conc.get("datos") or {}
    if not ingreso:
        return []
    reg = await _registro_bodega(fd)
    difs = []
    for campo, label in CAMPOS_CONTROL.items():
        vi = ingreso.get(campo)
        if vi in (None, ""):
            continue
        vb = reg.get(campo)
        if campo.startswith("rut"):
            igual = _rut_limpio(vb) == _rut_limpio(vi)
        else:
            igual = str(vb if vb is not None else "").strip().lower() == str(vi).strip().lower()
        if not igual:
            difs.append({"campo": label, "valor_bodega": vb, "valor_ingreso": vi,
                         "motivo": f"{label} difiere entre la Bodega y el registro de Ingreso"})
    return difs


@control.get("/discrepancias")
async def control_discrepancias():
    out = []
    async for fd in db.folders.find({}).sort("nombre", 1):
        difs = await _difs_folder(fd)
        if difs:
            alerta = await db.control_alertas.find_one({"folder_id": fd["id"]}, sort=[("fecha", -1)])
            out.append({"folder_id": fd["id"], "cliente": fd.get("nombre"), "rut": fd.get("rut") or "",
                        "diferencias": difs, "alerta_enviada": bool(alerta),
                        "alerta_fecha": (alerta or {}).get("fecha", "")})
    cfg = await db.config.find_one({"_key": "control_inconsistencias"}) or {}
    return {"discrepancias": out, "total": len(out),
            "destinatario_maestro": cfg.get("destinatario_maestro", ""),
            "no_interferencia": True}


@control.get("/config")
async def control_config_get():
    cfg = await db.config.find_one({"_key": "control_inconsistencias"}, {"_id": 0}) or {}
    return {"destinatario_maestro": cfg.get("destinatario_maestro", "")}


@control.post("/config")
async def control_config_set(payload: dict, request: Request):
    dest = (payload.get("destinatario_maestro") or "").strip().lower()
    if dest and not re.match(r"^[\w.+-]+@[\w-]+\.[\w.-]+$", dest):
        raise HTTPException(status_code=400, detail="Correo de destinatario inválido")
    claims = getattr(request.state, "user", None) or {}
    await db.config.update_one({"_key": "control_inconsistencias"}, {"$set": {
        "destinatario_maestro": dest, "actualizado_por": claims.get("nombre", ""),
        "actualizado": _now()}}, upsert=True)
    return {"ok": True, "destinatario_maestro": dest}


def _alerta_html(cliente, rut, difs, motivo):
    fmt = lambda v: "—" if v in (None, "") else ("Sí" if v is True else ("No" if v is False else str(v)))
    filas = "".join(
        f"<tr><td style='padding:8px 10px;border:1px solid #000;'>{d['campo']}</td>"
        f"<td style='padding:8px 10px;border:1px solid #000;'>{fmt(d['valor_bodega'])}</td>"
        f"<td style='padding:8px 10px;border:1px solid #000;'>{fmt(d['valor_ingreso'])}</td></tr>"
        for d in difs)
    return (
        '<div style="max-width:600px;margin:0 auto;font-family:Arial,Helvetica,sans-serif;'
        'color:#000;background:#fff;padding:18px;">'
        '<h2 style="font-size:18px;margin:0 0 4px;">Alerta de Inconsistencia de Datos</h2>'
        '<p style="font-size:13px;margin:0 0 16px;">Central Mutuos — Módulo Control (Auditoría e Información)</p>'
        f'<p style="font-size:14px;margin:0 0 14px;"><b>Nombre Cliente:</b> {cliente}<br/><b>RUT:</b> {rut or "—"}</p>'
        '<table style="width:100%;border-collapse:collapse;font-size:13px;">'
        '<tr><th style="padding:8px 10px;border:1px solid #000;text-align:left;">Dato</th>'
        '<th style="padding:8px 10px;border:1px solid #000;text-align:left;">Registro en Bodega</th>'
        '<th style="padding:8px 10px;border:1px solid #000;text-align:left;">Registro en Ingreso</th></tr>'
        f'{filas}</table>'
        f'<p style="font-size:13px;margin:14px 0 8px;"><b>Motivo de la alerta:</b> {motivo}</p>'
        '<p style="font-size:12px;margin:14px 0 0;">Este informe es de carácter exclusivamente auditor e '
        'informativo. La decisión operativa final recae en Gerencia de Riesgo y Concreces.</p>'
        '</div>')


@control.post("/alerta/{fid}")
async def control_alerta(fid: str, payload: dict, request: Request):
    fd = await db.folders.find_one({"id": fid})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    difs = await _difs_folder(fd)
    if not difs:
        raise HTTPException(status_code=400, detail="Sin discrepancias vigentes para esta carpeta")
    cfg = await db.config.find_one({"_key": "control_inconsistencias"}) or {}
    destinatario = ((payload or {}).get("destinatario") or cfg.get("destinatario_maestro") or "").strip()
    if not destinatario:
        raise HTTPException(status_code=400,
                            detail="Configure el Destinatario Maestro de Inconsistencias en el panel de DashAI")
    motivo = ((payload or {}).get("motivo") or "").strip() or "; ".join(d["motivo"] for d in difs)
    subject = f"Alerta de Inconsistencia de Datos — {fd.get('nombre','')}"
    body = _alerta_html(fd.get("nombre", ""), fd.get("rut", ""), difs, motivo)
    # REGLA DE HIERRO: 100% responsivo y libre de rastro técnico (Purificación)
    exigir("responsividad_absoluta", html=body)
    exigir("purificacion_correos", subject=subject, html=body)
    res = await asyncio.to_thread(_mail.send_mail, destinatario, subject, body)
    if not (res or {}).get("success"):
        raise HTTPException(status_code=502, detail=(res or {}).get("error", "Error de envío"))
    claims = getattr(request.state, "user", None) or {}
    reg = {"id": str(uuid.uuid4()), "folder_id": fid, "cliente": fd.get("nombre", ""),
           "rut": fd.get("rut", ""), "destinatario": destinatario, "diferencias": difs,
           "motivo": motivo, "usuario": claims.get("nombre", claims.get("sub", "")),
           "fecha": _now()}
    await db.control_alertas.insert_one(dict(reg))
    return {"ok": True, "no_interferencia": True, "destinatario": destinatario,
            "diferencias": len(difs)}
