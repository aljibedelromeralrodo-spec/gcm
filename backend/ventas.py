"""🧲 MÓDULO VENTAS — Yerile Barrera & Deysi Salazar (independiente, Regla de Oro de arquitectura)"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from database import db
from victoria_independiente import (_exigir, _now, _docs_validos, _buscar_o_crear_cliente,
                                    DOCS_REQUERIDOS, ETIQUETAS, EJECUTIVOS_VENTAS,
                                    asignar_a_ventas_si_corresponde)

vtas = APIRouter(prefix="/ventas")

ESTADOS_VENTAS = {"en_gestion": "En gestión", "contactado": "Contactado",
                  "esperando_documentos": "Esperando documentos",
                  "documentacion_completa": "Documentación completa",
                  "sin_respuesta": "Sin respuesta"}


async def _resumen_cliente(c):
    docs = await _docs_validos(c["id"])
    presentes = {d["tipo"] for d in docs}
    faltantes = [ETIQUETAS[t] for t in DOCS_REQUERIDOS if t not in presentes]
    v = c.get("ventas") or {}
    contactos = v.get("contactos") or []
    dias = 0
    try:
        asig = datetime.fromisoformat(str(v.get("asignado_en", "")).replace("Z", "+00:00"))
        dias = max(0, (datetime.now(timezone.utc) - asig).days)
    except Exception:
        pass
    return {"id": c["id"], "nombre": c["nombre"], "rut": c.get("rut", ""),
            "email": c.get("email", ""), "telefono": c.get("telefono", ""),
            "estado": v.get("estado", "en_gestion"),
            "estado_etiqueta": ESTADOS_VENTAS.get(v.get("estado", "en_gestion"), v.get("estado", "")),
            "faltantes": faltantes, "n_docs": len(docs), "docs_completos": not faltantes,
            "asignado_en": v.get("asignado_en", ""), "dias_gestion": dias,
            "ejecutivo": v.get("ejecutivo", ""), "ejecutivo_nombre": v.get("ejecutivo_nombre", ""),
            "ultimo_contacto": (contactos[-1] if contactos else None),
            "n_contactos": len(contactos)}


@vtas.get("/panel/{ejecutivo}")
async def panel_ventas(ejecutivo: str, request: Request):
    _exigir(request)
    if ejecutivo not in EJECUTIVOS_VENTAS:
        raise HTTPException(status_code=404, detail="Ejecutivo no registrado en el Módulo Ventas")
    clientes = await db.victoria_clientes.find({"ventas.ejecutivo": ejecutivo}, {"_id": 0}).sort("ventas.asignado_en", -1).to_list(200)
    out = [await _resumen_cliente(c) for c in clientes]
    kpis = {"asignados": len(out),
            "incompletos": sum(1 for x in out if not x["docs_completos"]),
            "completos": sum(1 for x in out if x["docs_completos"]),
            "faltantes_total": sum(len(x["faltantes"]) for x in out)}
    return {"ejecutivo": ejecutivo, "nombre": EJECUTIVOS_VENTAS[ejecutivo],
            "kpis": kpis, "clientes": out, "estados": ESTADOS_VENTAS}


@vtas.post("/solicitudes")
async def nueva_solicitud(payload: dict, request: Request):
    _exigir(request)
    nombre = (payload.get("nombre") or "").strip()
    rut = (payload.get("rut") or "").strip()
    if not nombre or not rut:
        raise HTTPException(status_code=400, detail="Indique el nombre y el RUT del solicitante")
    import re as _re
    if not _re.fullmatch(r"\d{1,2}\.?\d{3}\.?\d{3}-[0-9kK]", rut):
        raise HTTPException(status_code=400, detail="RUT inválido: use el formato 12.345.678-9")
    cliente = await _buscar_o_crear_cliente(rut, nombre, "ventas_manual")
    if not cliente:
        raise HTTPException(status_code=400, detail="RUT inválido: no se pudo crear la solicitud")
    sets = {}
    for k in ("email", "telefono"):
        val = (payload.get(k) or "").strip()
        if val:
            sets[k] = val
    if payload.get("entrega_inmediata"):
        sets["entrega_inmediata"] = True
    if sets:
        await db.victoria_clientes.update_one({"id": cliente["id"]}, {"$set": sets})
    ej = await asignar_a_ventas_si_corresponde(cliente["id"])
    if ej:
        return {"ok": True, "asignado": True, "cliente_id": cliente["id"],
                "ejecutivo": EJECUTIVOS_VENTAS[ej],
                "mensaje": f"Solicitud asignada automáticamente a {EJECUTIVOS_VENTAS[ej]} (turno alternado)"}
    c2 = await db.victoria_clientes.find_one({"id": cliente["id"]}, {"_id": 0})
    if (c2 or {}).get("ventas"):
        n = c2["ventas"].get("ejecutivo_nombre", "")
        return {"ok": True, "asignado": True, "cliente_id": cliente["id"], "ejecutivo": n,
                "mensaje": f"Esta solicitud ya estaba asignada a {n}"}
    return {"ok": True, "asignado": False, "cliente_id": cliente["id"],
            "mensaje": "NO cumple las condiciones del Módulo Ventas (requiere documentación "
                       "incompleta Y entrega inmediata): quedó como cliente normal de la bóveda"}


@vtas.post("/clientes/{cid}/contacto-registro")
async def registrar_contacto(cid: str, payload: dict, request: Request):
    u = _exigir(request)
    canal = payload.get("canal") or "llamada"
    nota = (payload.get("nota") or "").strip()
    if not nota:
        raise HTTPException(status_code=400, detail="Describa el contacto realizado con el cliente")
    c = await db.victoria_clientes.find_one({"id": cid, "ventas": {"$exists": True}})
    if not c:
        raise HTTPException(status_code=404, detail="Cliente no encontrado en el Módulo Ventas")
    reg = {"canal": canal, "nota": nota, "por": u.get("sub", ""), "fecha": _now()}
    await db.victoria_clientes.update_one({"id": cid}, {
        "$push": {"ventas.contactos": reg}, "$set": {"ventas.ultimo_contacto": _now()}})
    return {"ok": True, "contacto": reg}


@vtas.put("/clientes/{cid}/estado")
async def estado_ventas(cid: str, payload: dict, request: Request):
    _exigir(request)
    estado = payload.get("estado")
    if estado not in ESTADOS_VENTAS:
        raise HTTPException(status_code=400, detail="Estado inválido")
    r = await db.victoria_clientes.update_one({"id": cid, "ventas": {"$exists": True}},
                                              {"$set": {"ventas.estado": estado}})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Cliente no encontrado en el Módulo Ventas")
    return {"ok": True, "estado": estado, "etiqueta": ESTADOS_VENTAS[estado]}


@vtas.get("/reporte")
async def reporte_ventas(request: Request):
    """Reporte transversal en tiempo real para el Administrador."""
    _exigir(request)
    ejecutivos = {}
    for ej, nombre in EJECUTIVOS_VENTAS.items():
        clientes = await db.victoria_clientes.find({"ventas.ejecutivo": ej}, {"_id": 0}).sort("ventas.asignado_en", -1).to_list(200)
        res = [await _resumen_cliente(c) for c in clientes]
        inc = [x for x in res if not x["docs_completos"]]
        ejecutivos[ej] = {"nombre": nombre, "clientes": res, "total": len(res),
                          "incompletos": len(inc),
                          "faltantes_total": sum(len(x["faltantes"]) for x in res),
                          "dias_promedio_sin_completar":
                              round(sum(x["dias_gestion"] for x in inc) / len(inc), 1) if inc else 0}
    return {"ejecutivos": ejecutivos, "estados": ESTADOS_VENTAS, "generado": _now()}


@vtas.put("/ejecutivos/{ej}/avisos-email")
async def set_avisos_email(ej: str, payload: dict, request: Request):
    """Espacios de correo por ejecutiva para recibir avisos del sistema de gestión."""
    _exigir(request)
    if ej not in EJECUTIVOS_VENTAS:
        raise HTTPException(status_code=404, detail="Ejecutivo no registrado")
    emails = [e.strip().lower() for e in (payload.get("emails") or []) if "@" in e][:5]
    await db.config.update_one({"_key": "ventas_emails"}, {"$set": {ej: emails}}, upsert=True)
    return {"ok": True, "ejecutivo": ej, "emails": emails}


@vtas.get("/avisos-email")
async def get_avisos_email(request: Request):
    _exigir(request)
    cfg = await db.config.find_one({"_key": "ventas_emails"}, {"_id": 0}) or {}
    return {ej: cfg.get(ej, []) for ej in EJECUTIVOS_VENTAS}
