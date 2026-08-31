"""Pro Flujo operativo — una línea: captación → carpeta → Mesa → GOP → escrituración.

No reemplaza módulos. Lee el estado real y dice la siguiente acción.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from database import db

flujo = APIRouter(prefix="/pro-flujo")

COLUMNAS = (
    ("captacion", "Captación", "Publicidad y prospectos"),
    ("clasificar", "Clasificar", "Carpeta con docs mal o incompletos"),
    ("autorizar", "Autorizar mail", "Pedir faltantes (el Admin confirma)"),
    ("listo_mesa", "Enviar a Mesa", "Carpeta completa"),
    ("gop", "Gasto operacional", "Enviar o cobrar GOP"),
    ("en_mesa", "En Mesa", "Esperar aprobación / rechazo"),
    ("escrituracion", "Escrituración", "Tasación · títulos · escritura"),
    ("cerrado", "Cerrado", "Firma hecha / postventa"),
)


def _now():
    return datetime.now(timezone.utc).isoformat()


def etapa_operacion(fd, *, faltan, auth_pend, gop_enviado, gop_pagado, carta):
    """Una carpeta → una columna + siguiente acción (sin inventar datos)."""
    fd = fd or {}
    if fd.get("escritura_confirmada_at"):
        return "cerrado", "Escritura confirmada. Abrir Postventa."
    en_esc = bool(
        carta
        or fd.get("tasacion_solicitada_at")
        or fd.get("estudio_titulo_solicitado_at")
        or fd.get("escritura_solicitada_at")
        or (fd.get("mesa_respuesta") or "") == "aprobada"
    )
    if en_esc:
        if not fd.get("tasacion_solicitada_at"):
            return "escrituracion", "Solicitar tasación."
        if not fd.get("estudio_titulo_solicitado_at"):
            return "escrituracion", "Solicitar estudio de títulos."
        if not fd.get("escritura_solicitada_at"):
            return "escrituracion", "Solicitar escritura."
        return "escrituracion", "Seguir tasación / títulos / escritura."
    mesa_enviada = bool(fd.get("mesa_enviado_at") or fd.get("emails_sent_count"))
    if mesa_enviada:
        if (fd.get("mesa_respuesta") or "") == "rechazada":
            return "en_mesa", "Mesa rechazó. Revisar y no seguir escrituración."
        if not gop_pagado:
            return "gop", "Cobrar o registrar el gasto operacional."
        return "en_mesa", "Esperar veredicto de Mesa."
    if auth_pend:
        return "autorizar", "Autorizar el mail pidiendo documentos faltantes."
    if faltan:
        return "clasificar", "Completar y clasificar documentos de la carpeta."
    if not gop_enviado:
        return "gop", "Enviar gasto operacional y después Mesa."
    return "listo_mesa", "Enviar carpeta a Mesa de aprobación."


def accion_de(etapa, fd, *, gop_enviado=False):
    """Qué botón mostrar. No envía nada por sí sola."""
    if etapa == "clasificar":
        return "sincronizar"
    if etapa == "autorizar":
        return "autorizar_faltantes"
    if etapa == "gop":
        return "registrar_gop" if (fd or {}).get("mesa_enviado_at") or gop_enviado else "enviar_gop"
    if etapa == "listo_mesa":
        return "enviar_mesa"
    if etapa == "escrituracion":
        if not (fd or {}).get("tasacion_solicitada_at"):
            return "enviar_tasacion"
        if not (fd or {}).get("estudio_titulo_solicitado_at"):
            return "enviar_estudio"
        if not (fd or {}).get("escritura_solicitada_at"):
            return "mover_escrituracion"
        return "abrir_escritura"
    if etapa == "cerrado":
        return "abrir_postventa"
    if etapa == "captacion":
        return "abrir_publicidad"
    return "abrir_supercarpeta"


def _email_de(fd):
    src = ((fd or {}).get("email") or (fd or {}).get("source_email") or "").strip()
    m = re.search(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", src)
    return (m.group(0) if m else src).strip()


def _modulo_de(etapa):
    return {
        "captacion": "publicidad",
        "clasificar": "clientes",
        "autorizar": "procesamiento",
        "listo_mesa": "autocorreo",
        "gop": "gastos",
        "en_mesa": "supercarpeta",
        "escrituracion": "supercarpeta",
        "cerrado": "postventa",
    }.get(etapa, "clientes")


@flujo.get("")
async def api_tablero(request: Request):
    """Tablero Pro Flujo + bloqueos para llegar al 100%."""
    claims = getattr(request.state, "user", {}) or {}
    if claims.get("rol") not in ("admin", "maestro", "gerencia", "administracion"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Pro Flujo: Admin / Gerencia / Administración")

    folders = await db.folders.find({}, {
        "_id": 0, "id": 1, "nombre": 1, "rut": 1, "source_email": 1,
        "protocolo_id": 1, "protocolo_nombre": 1, "protocolo_faltan": 1,
        "protocolo_completo": 1, "credit_request": 1, "codeudor_nombre": 1,
        "mesa_enviado_at": 1, "emails_sent_count": 1, "mesa_respuesta": 1,
        "tasacion_solicitada_at": 1, "tasacion_terminado_at": 1,
        "estudio_titulo_solicitado_at": 1, "estudio_titulo_terminado_at": 1,
        "escritura_solicitada_at": 1, "escritura_confirmada_at": 1,
        "created_at": 1,
    }).sort("created_at", -1).to_list(250)

    auth_pend = {}
    async for a in db.correos_autorizacion_admin.find(
            {"estado": "pendiente"}, {"_id": 0, "id": 1, "folder_id": 1, "caso_id": 1}):
        k = a.get("folder_id") or a.get("caso_id")
        if k:
            auth_pend[k] = a.get("id")

    gop_por_nombre = {}
    async for g in db.gastos_op_log.find({}, {"_id": 0, "id": 1, "nombre": 1, "enviado_en": 1,
                                              "pagado": 1, "estado_pago": 1}):
        nom = (g.get("nombre") or "").strip().lower()
        if nom:
            gop_por_nombre[nom] = g

    cols = {k: [] for k, *_ in COLUMNAS}
    for fd in folders:
        if fd.get("protocolo_faltan") is None and fd.get("protocolo_completo") is None:
            faltan = ["pendiente_clasificacion"]
        else:
            faltan = list(fd.get("protocolo_faltan") or [])
            if fd.get("protocolo_completo") is False and not faltan:
                faltan = ["revisar"]
        g = gop_por_nombre.get((fd.get("nombre") or "").strip().lower()) or {}
        gop_env = bool(g.get("enviado_en"))
        gop_ok = bool(g.get("pagado") or (g.get("estado_pago") or "").upper() == "PAGADO")
        cr = fd.get("credit_request") or {}
        carta = bool((cr.get("carta_aprobacion") or fd.get("mesa_respuesta") == "aprobada"))
        etapa, next_a = etapa_operacion(
            fd, faltan=bool(faltan), auth_pend=fd.get("id") in auth_pend,
            gop_enviado=gop_env, gop_pagado=gop_ok, carta=carta)
        sub = []
        if fd.get("tasacion_solicitada_at"):
            sub.append("tasación" + (" ✓" if fd.get("tasacion_terminado_at") else ""))
        if fd.get("estudio_titulo_solicitado_at"):
            sub.append("títulos" + (" ✓" if fd.get("estudio_titulo_terminado_at") else ""))
        if fd.get("escritura_solicitada_at"):
            sub.append("escritura" + (" ✓" if fd.get("escritura_confirmada_at") else ""))
        cols[etapa].append({
            "id": fd.get("id"),
            "nombre": fd.get("nombre") or "—",
            "rut": fd.get("rut") or "",
            "email": _email_de(fd),
            "protocolo": fd.get("protocolo_nombre") or fd.get("protocolo_id") or "",
            "faltan": faltan[:8],
            "siguiente": next_a,
            "accion": accion_de(etapa, fd, gop_enviado=gop_env),
            "auth_id": auth_pend.get(fd.get("id")),
            "gop_id": g.get("id"),
            "modulo": _modulo_de(etapa),
            "hitos": sub,
            "mesa": bool(fd.get("mesa_enviado_at") or fd.get("emails_sent_count")),
        })

    prospectos = []
    async for p in db.prospectos.find({}, {"_id": 0, "id": 1, "nombre": 1, "telefono": 1,
                                           "proyecto": 1, "status": 1}).sort("creado_en", -1).limit(40):
        prospectos.append({
            "id": p.get("id"), "nombre": p.get("nombre") or "—",
            "rut": "", "protocolo": p.get("proyecto") or "",
            "faltan": [], "siguiente": "Captar / enviar a portal de documentos.",
            "accion": "abrir_publicidad",
            "modulo": "publicidad", "hitos": [], "mesa": False,
            "prospecto": True,
        })
    cols["captacion"] = prospectos + cols["captacion"]

    twilio = bool((os.environ.get("TWILIO_ACCOUNT_SID") or "").strip() and
                  (os.environ.get("TWILIO_AUTH_TOKEN") or "").strip())
    try:
        import whatsapp_twilio_service as wa
        twilio = twilio or wa.configurado()
    except Exception:
        pass
    ds19 = await db.publicidad_listados.find_one({"nombre": {"$regex": "ds19", "$options": "i"}})
    mail2 = bool((os.environ.get("MAIL2_USER") or "").strip() and
                 (os.environ.get("MAIL2_APP_PASSWORD") or "").strip())

    bloqueos = []
    if not twilio:
        bloqueos.append({"id": "twilio", "modulo": "publicidad",
                         "falta": "Credenciales Twilio (WhatsApp automático de campañas)."})
    if not ds19:
        bloqueos.append({"id": "ds19", "modulo": "publicidad",
                         "falta": "Excel/CSV del listado ds19 inmobiliarias (la imagen no se pudo leer)."})
    if not mail2:
        bloqueos.append({"id": "mail2", "modulo": "operaciones",
                         "falta": "MAIL2 (gerardo.ext) para que salgan los correos de faltantes y Mesa."})
    if not os.environ.get("MASTER_PIN"):
        bloqueos.append({"id": "pin", "modulo": "publicidad",
                         "falta": "MASTER_PIN en el entorno: sin él no se disparan campañas (ORO-75)."})

    tablero = [{"id": cid, "titulo": tit, "hint": hint, "n": len(cols[cid]), "items": cols[cid]}
               for cid, tit, hint in COLUMNAS]
    return {
        "columnas": tablero,
        "total_carpetas": len(folders),
        "total_prospectos": len(prospectos),
        "autorizaciones_pendientes": len(auth_pend),
        "bloqueos_100": bloqueos,
        "listo_para_operar": not any(b["id"] in ("mail2",) for b in bloqueos),
        "actualizado": _now(),
    }


def _exige(request):
    claims = getattr(request.state, "user", {}) or {}
    if claims.get("rol") not in ("admin", "maestro", "gerencia", "administracion"):
        raise HTTPException(status_code=403, detail="Pro Flujo: Admin / Gerencia / Administración")
    return claims


@flujo.get("/ficha/{fid}")
async def api_ficha(fid: str, request: Request):
    """Detalle + preview del siguiente paso. No envía correo."""
    _exige(request)
    fd = await db.folders.find_one({"id": fid}, {"_id": 0})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    auth = await db.correos_autorizacion_admin.find_one(
        {"estado": "pendiente", "$or": [{"folder_id": fid}, {"caso_id": fid}]}, {"_id": 0})
    g = await db.gastos_op_log.find_one(
        {"nombre": {"$regex": f"^{re.escape(fd.get('nombre') or '')}$", "$options": "i"}},
        {"_id": 0}) or {}
    faltan = list(fd.get("protocolo_faltan") or [])
    if fd.get("protocolo_faltan") is None and fd.get("protocolo_completo") is None:
        faltan = ["pendiente_clasificacion"]
    gop_env = bool(g.get("enviado_en"))
    gop_ok = bool(g.get("pagado") or (str(g.get("estado_pago") or "")).upper() == "PAGADO")
    cr = fd.get("credit_request") or {}
    carta = bool(cr.get("carta_aprobacion") or fd.get("mesa_respuesta") == "aprobada")
    etapa, next_a = etapa_operacion(
        fd, faltan=bool(faltan), auth_pend=bool(auth),
        gop_enviado=gop_env, gop_pagado=gop_ok, carta=carta)
    accion = accion_de(etapa, fd, gop_enviado=gop_env)
    preview = await _preview(fid, fd, accion, auth, request)
    return {
        "id": fid, "nombre": fd.get("nombre"), "rut": fd.get("rut") or "",
        "email": _email_de(fd), "etapa": etapa, "siguiente": next_a, "accion": accion,
        "modulo": _modulo_de(etapa), "faltan": faltan, "auth_id": (auth or {}).get("id"),
        "gop_id": g.get("id"), "preview": preview,
    }


async def _preview(fid, fd, accion, auth, request):
    """Llama los endpoints existentes con confirm=false. Si falta un dato, lo dice."""
    import server as s
    nombre = fd.get("nombre") or ""
    try:
        if accion == "autorizar_faltantes" and auth:
            return {
                "tipo": "mail", "to": auth.get("destinatario"),
                "subject": auth.get("asunto_propuesto"),
                "body": auth.get("mensaje_propuesto"),
                "faltan": auth.get("documentos_faltan") or [],
                "hint": "El Admin autoriza. Recién ahí sale el correo (V15.9).",
            }
        if accion in ("sincronizar", "pedir_faltantes"):
            r = await s.folder_pedir_faltantes(fid, {"confirm": False})
            return {"tipo": "mail", "to": r.get("to"), "subject": r.get("subject"),
                    "body": r.get("body"), "faltan": r.get("faltantes") or [],
                    "hint": "Primero se sincroniza el protocolo. El mail queda en autorización, no sale solo."}
        if accion == "enviar_mesa":
            r = await s.folder_send_email(fid, {"confirm": False})
            return {"tipo": "mail", "to": r.get("to") or r.get("destino"),
                    "subject": r.get("subject"), "body": r.get("body_html") or r.get("body"),
                    "missing": r.get("missing_docs") or r.get("missing_labels"),
                    "hint": "Preview constitucional: si confirmás, entra a la cola de confirmación o sale a Mesa."}
        if accion == "enviar_gop":
            defs = await s._gastos_defaults()
            payload = {
                "nombre": nombre, "rut": fd.get("rut") or "",
                "email_cliente": _email_de(fd),
                "items": defs.get("items"), "intro": defs.get("intro"),
                "datos_pago": defs.get("datos_pago"), "confirm": False,
            }
            r = await s.gastos_enviar(payload, request)
            return {"tipo": "mail", "to": r.get("to"), "subject": r.get("subject"),
                    "body": r.get("body"), "total": r.get("total"),
                    "hint": "Requiere MASTER_PIN. Exclusivo Admin / Deisy.",
                    "pide_pin": True}
        if accion == "registrar_gop":
            return {"tipo": "info",
                    "hint": "Registrá el pago en Gastos Operacionales (PIN). Se abre el módulo con el cliente cargado."}
        if accion == "enviar_tasacion":
            pre = {}
            try:
                pre = await s.folder_tasacion_prefill(fid)
            except Exception:
                pre = {}
            df = fd.get("datos_financieros") or {}
            direccion = (pre.get("direccion") or df.get("direccion") or "").strip()
            payload = {
                "nombre": nombre, "rut": fd.get("rut") or "",
                "folder_id": fid, "direccion": direccion,
                "confirm": False,
            }
            r = await s.tasacion_enviar(payload)
            return {"tipo": "mail", "to": r.get("to"), "subject": r.get("subject"),
                    "body": r.get("body"),
                    "need_fields": [] if direccion else ["direccion"],
                    "direccion": direccion,
                    "hint": "Si falta la dirección, complétala aquí. El envío respeta preview."}
        if accion == "enviar_estudio":
            r = await s.estudio_preview_carpeta(fid)
            return {"tipo": "mail", "to": r.get("para"), "subject": r.get("asunto"),
                    "body": r.get("body"), "faltan": r.get("faltantes") or [],
                    "payload_envio": r.get("payload_envio") or {},
                    "hint": "Usa la plantilla propia de Estudio de Título."}
        if accion == "mover_escrituracion":
            return {"tipo": "info",
                    "hint": "Mueve la ficha a Escrituración (Set de Crédito y Títulos). No envía correo."}
    except HTTPException as e:
        return {"tipo": "error", "hint": e.detail, "status": e.status_code}
    except Exception as e:
        return {"tipo": "error", "hint": str(e)[:200]}
    return {"tipo": "info", "hint": "Abrir el módulo correspondiente."}


@flujo.post("/actuar")
async def api_actuar(payload: dict, request: Request):
    """Ejecuta el siguiente paso usando los endpoints que ya existen. No inventa envíos."""
    _exige(request)
    payload = payload or {}
    fid = (payload.get("fid") or payload.get("id") or "").strip()
    accion = (payload.get("accion") or "").strip()
    confirm = bool(payload.get("confirm"))
    if not fid or not accion:
        raise HTTPException(status_code=400, detail="Falta carpeta o acción")
    fd = await db.folders.find_one({"id": fid})
    if not fd and accion not in ("abrir_publicidad",):
        raise HTTPException(status_code=404, detail="Carpeta no existe")
    import server as s
    nombre = (fd or {}).get("nombre") or ""

    if accion == "sincronizar":
        import blindaje_correos as bl
        inv = await bl.enriquecer_desde_ingesta(fd, None)
        return {"ok": True, "resultado": "protocolo_sincronizado",
                "protocolo": inv.get("protocolo_nombre"),
                "faltan": inv.get("documentos_faltan") or [],
                "completo": inv.get("completo"),
                "mensaje": ("Protocolo " + (inv.get("protocolo_nombre") or "")
                            + (". Listo para Mesa." if inv.get("completo")
                               else ". Faltantes en bandeja de autorización."))}

    if accion == "autorizar_faltantes":
        aid = (payload.get("auth_id") or "").strip()
        if not aid:
            a = await db.correos_autorizacion_admin.find_one(
                {"estado": "pendiente", "$or": [{"folder_id": fid}, {"caso_id": fid}]})
            aid = (a or {}).get("id") or ""
        if not aid:
            raise HTTPException(status_code=404, detail="No hay mail de faltantes pendiente")
        if not confirm:
            return {"ok": True, "preview": True, "auth_id": aid,
                    "mensaje": "Confirmá para autorizar y encolar el envío."}
        return await _decidir_faltantes(aid, payload, request)

    if accion == "enviar_mesa":
        body = {"confirm": confirm, "ejecutivo_interno": payload.get("ejecutivo_interno") or "",
                "force_incompleto": bool(payload.get("force_incompleto")),
                "force_discrepancia": bool(payload.get("force_discrepancia")),
                "clave": payload.get("clave") or ""}
        r = await s.folder_send_email(fid, body)
        return {"ok": True, "preview": not confirm, "data": r,
                "mensaje": "Preview de Mesa listo." if not confirm else (
                    "En cola de preview constitucional o enviado a Mesa.")}

    if accion == "enviar_gop":
        defs = await s._gastos_defaults()
        body = {
            "nombre": nombre, "rut": (fd or {}).get("rut") or "",
            "email_cliente": payload.get("email") or _email_de(fd),
            "items": defs.get("items"), "intro": defs.get("intro"),
            "datos_pago": defs.get("datos_pago"),
            "confirm": confirm, "master_pin": payload.get("master_pin") or "",
        }
        r = await s.gastos_enviar(body, request)
        return {"ok": True, "preview": not confirm, "data": r,
                "mensaje": "Preview de GOP." if not confirm else "GOP enviado (o en preview constitucional)."}

    if accion == "enviar_tasacion":
        pre = {}
        try:
            pre = await s.folder_tasacion_prefill(fid)
        except Exception:
            pre = {}
        df = (fd or {}).get("datos_financieros") or {}
        direccion = (payload.get("direccion") or pre.get("direccion") or df.get("direccion") or "").strip()
        body = {"nombre": nombre, "rut": (fd or {}).get("rut") or "", "folder_id": fid,
                "direccion": direccion, "confirm": confirm}
        if confirm and not direccion:
            raise HTTPException(status_code=400, detail="Falta la dirección de la propiedad")
        r = await s.tasacion_enviar(body)
        return {"ok": True, "preview": not confirm, "data": r,
                "mensaje": "Preview de tasación." if not confirm else "Solicitud de tasación enviada (o en preview)."}

    if accion == "enviar_estudio":
        prev = await s.estudio_preview_carpeta(fid)
        env = dict(prev.get("payload_envio") or {})
        env.update({"nombre": nombre, "rut": (fd or {}).get("rut") or "", "confirm": confirm,
                    "folder_id": fid})
        if payload.get("para"):
            env["inmo_contacto_email"] = payload["para"]
            env["vendedor_email"] = payload["para"]
        r = await s.estudio_enviar(env)
        return {"ok": True, "preview": not confirm, "data": r,
                "mensaje": "Preview de estudio de títulos." if not confirm else "Estudio solicitado (o en preview)."}

    if accion == "mover_escrituracion":
        r = await s.folder_enviar_escrituracion(fid)
        return {"ok": True, "data": r, "mensaje": r.get("mensaje") or "Movido a escrituración."}

    raise HTTPException(status_code=400, detail=f"Acción no ejecutable aquí: {accion}. Abrí el módulo.")


async def _decidir_faltantes(aid, payload, request):
    import blindaje_correos as bl
    return await bl.api_decidir(aid, {
        "accion": "autorizar",
        "asunto": payload.get("asunto"),
        "body_html": payload.get("body_html"),
        "destinatario": payload.get("destinatario") or payload.get("email"),
    }, request)
