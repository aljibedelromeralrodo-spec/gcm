"""📩 NOTIFICACIÓN AUTOMÁTICA DE RECHAZOS — Solicitud de Crédito
Cuando llega un rechazo por el canal oficial, el sistema genera un correo institucional
DIRECTO de Central Mutuos al ejecutivo que gestionó el crédito. Reglas duras:
- JAMÁS menciona a la mesa, JAMÁS parece reenvío, JAMÁS usa la palabra 'aprobación'.
- Incluye siempre: nombre completo del cliente (root), motivo en lenguaje institucional
  (de usted) y una recomendación de acción según el motivo.
- Primera vez: 3 opciones de diseño para aprobación del Administrador; la aprobada queda
  como plantilla fija y los envíos futuros son 100% automáticos.
"""
import os
import re
import uuid
import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from database import db
import auth as _auth
import bcrypt

rechz = APIRouter(prefix="/rechazo-notif")
FALLBACK_EJECUTIVO = "gerardo.ext@centralmutuos.cl"


async def _clave_admin_ok(payload):
    clave = ((payload or {}).get("clave") or "").strip()
    if not clave:
        return False
    if _auth.admin_clave_ok(clave) or _auth.master_pin_ok(clave):
        return True
    try:
        async for user in db.users.find({"rol": {"$in": ["admin", "maestro"]}}):
            if user.get("clave_hash"):
                try:
                    if bcrypt.checkpw(clave.encode(), user["clave_hash"].encode()):
                        return True
                except Exception:
                    continue
            elif user.get("password") and _auth.secret_eq(clave, user.get("password")):
                return True
    except Exception:
        return False
    return False


def _now():
    return datetime.now(timezone.utc).isoformat()


# ── Motivo y recomendación (lenguaje institucional, sin palabras prohibidas) ──
REGLAS = [
    (re.compile(r"par[aá]metros?\s+objetivos?|no\s+cumple\s+(los\s+)?par[aá]metros", re.I),
     "Tras la evaluación de los antecedentes presentados, la operación no cumple los parámetros objetivos mínimos de evaluación vigentes.",
     "Se recomienda reestructurar la operación cambiando el titular por el codeudor, de manera de fortalecer el perfil presentado, y reingresar la solicitud con esa nueva estructura."),
    (re.compile(r"sobre.?endeud|excede\s+(la\s+)?carga|pasad[oa]\s+en\s+carga|carga\s+financiera", re.I),
     "La carga financiera del solicitante excede el máximo admitido por la política de evaluación vigente.",
     "Se recomienda regularizar o reducir las deudas vigentes del solicitante, o bien incorporar un complemento de renta, y reingresar la solicitud una vez mejorada la relación carga/renta."),
    (re.compile(r"renta\s+insuficiente|renta\s+m[ií]nima|no\s+acredita\s+renta", re.I),
     "La renta acreditada resulta insuficiente respecto del dividendo proyectado de la operación.",
     "Se recomienda complementar renta con un codeudor o cónyuge, o ajustar el monto y plazo de la operación, y reingresar la solicitud con la nueva estructura."),
    (re.compile(r"dicom|morosidad|protesto|antecedentes\s+comerciales|deuda\s+castigada|boletín", re.I),
     "El solicitante registra antecedentes comerciales vigentes que impiden continuar con la operación en su estado actual.",
     "Se recomienda regularizar los antecedentes comerciales informados (acreditando los pagos correspondientes) y reingresar la solicitud junto con los comprobantes."),
    (re.compile(r"antig[üu]edad\s+laboral|contrato\s+(a\s+)?plazo|inicio\s+de\s+actividades", re.I),
     "La antigüedad o estabilidad laboral acreditada no alcanza el mínimo requerido por la política de evaluación vigente.",
     "Se recomienda reingresar la solicitud una vez completada la antigüedad mínima, o bien incorporar un codeudor con estabilidad laboral acreditada."),
]
MOTIVO_DEFECTO = ("Tras la evaluación de los antecedentes presentados, la operación no reúne "
                  "las condiciones exigidas por la política de evaluación vigente.")
RECO_DEFECTO = ("Se recomienda revisar la estructura de la operación junto con el cliente "
                "(monto, plazo, titularidad y complementos de renta) y reingresar la solicitud "
                "con los antecedentes fortalecidos.")


def recomendacion_para(texto):
    for rx, _m, reco in REGLAS:
        if rx.search(texto or ""):
            return reco
    return RECO_DEFECTO


def motivo_y_recomendacion(texto):
    # ⛔ NORMATIVA CONSTITUCIONAL — RECHAZO TEXTO EXACTO: el motivo es el texto EXACTO
    # enviado por el canal oficial, sin agregar, modificar ni inventar contenido.
    return (texto or "").strip()[:4000], recomendacion_para(texto)


# Referencias que jamás pueden salir en un correo (origen/reenvío/direcciones)
RX_ORIGEN_PROHIBIDO = re.compile(r"\bmesa\b|reenv[ií]|forward|fwd|[\w.+-]+@[\w-]+\.[\w.-]+", re.I)


PROHIBIDAS = re.compile(r"\bmesa\b|aprobaci[oó]n|reenv[ií]o|forward|fwd", re.I)


def _limpiar(t):
    return PROHIBIDAS.sub("evaluación", t or "")


# ── Las 3 plantillas institucionales (fondo blanco, estilo campañas) ──
def _marco(inner):
    return ("<!DOCTYPE html><html lang='es'><body style='margin:0;padding:0;background-color:#ededee;'>"
            "<table role='presentation' width='100%' cellpadding='0' cellspacing='0' style='background-color:#ededee;padding:26px 0;'>"
            "<tr><td align='center'>" + inner + "</td></tr></table></body></html>")


def _header_negro():
    return ("<tr><td style='background-color:#0e0e10;padding:26px 38px;'>"
            "<table role='presentation' width='100%' cellpadding='0' cellspacing='0'><tr>"
            "<td style='font-family:Georgia,serif;'>"
            "<div style='font-size:21px;letter-spacing:5px;color:#d4af37;'>CENTRAL MUTUOS</div>"
            "<div style='font-size:10px;letter-spacing:4px;color:#f5e7b8;margin-top:4px;'>CON CRECES</div></td>"
            "<td align='right' style='font-family:Georgia,serif;font-size:11px;color:#9a9a9a;vertical-align:bottom;'>Mutuaria regulada por la CMF</td>"
            "</tr></table></td></tr>"
            "<tr><td style='height:4px;background-color:#d4af37;font-size:0;'>&nbsp;</td></tr>")


def _firma():
    return ("<tr><td style='padding:20px 38px 28px;font-family:Georgia,serif;'>"
            "<p style='margin:0;font-size:12.5px;color:#3a3a3a;border-top:1px solid #eeeeee;padding-top:14px;'>"
            "Atentamente,<br><b>Área de Evaluación · Central Mutuos Con Creces</b><br>"
            "<span style='color:#8a6a0f;'>Av. La Dehesa 1822, Of. 511, Torre Sur, Lo Barnechea</span></p></td></tr>")


def plantilla_a(nombre, motivo, reco):
    """A — Clásica institucional: cabecera negra, nombre en banda dorada."""
    inner = ("<table role='presentation' width='620' cellpadding='0' cellspacing='0' style='max-width:620px;width:100%;background-color:#ffffff;'>"
             + _header_negro() +
             f"<tr><td style='background-color:#faf8f1;padding:16px 38px;border-bottom:1px solid #eadfc0;'>"
             f"<div style='font-family:Georgia,serif;font-size:11px;letter-spacing:2px;color:#8a6a0f;'>RESULTADO DE EVALUACIÓN — CLIENTE</div>"
             f"<div style='font-family:Georgia,serif;font-size:22px;color:#111111;margin-top:4px;'><b>{nombre}</b></div></td></tr>"
             f"<tr><td style='padding:26px 38px 6px;font-family:Georgia,serif;color:#222222;font-size:14px;line-height:1.75;'>"
             f"<p style='margin:0 0 14px;'>Estimado(a) ejecutivo(a):</p>"
             f"<p style='margin:0 0 14px;'>Le informamos que la solicitud de crédito del cliente <b>{nombre}</b> no podrá continuar su curso en las condiciones presentadas.</p>"
             f"<p style='margin:0 0 6px;'><b style='color:#8a6a0f;'>Motivo de la resolución</b></p>"
             f"<p style='margin:0 0 16px;'>{motivo}</p>"
             f"<p style='margin:0 0 6px;'><b style='color:#8a6a0f;'>Acción recomendada</b></p>"
             f"<p style='margin:0 0 14px;'>{reco}</p>"
             f"<p style='margin:0 0 8px;'>Quedamos a su disposición para acompañarlo(a) en la reestructuración de la operación.</p></td></tr>"
             + _firma() + "</table>")
    return _marco(inner)


def plantilla_b(nombre, motivo, reco):
    """B — Ficha ejecutiva: nombre en tarjeta central, bloques con borde dorado."""
    inner = ("<table role='presentation' width='620' cellpadding='0' cellspacing='0' style='max-width:620px;width:100%;background-color:#ffffff;'>"
             + _header_negro() +
             f"<tr><td align='center' style='padding:28px 38px 8px;'>"
             f"<table role='presentation' cellpadding='0' cellspacing='0' style='border:2px solid #d4af37;'><tr>"
             f"<td style='padding:14px 34px;font-family:Georgia,serif;text-align:center;'>"
             f"<div style='font-size:10px;letter-spacing:3px;color:#8a6a0f;'>CLIENTE</div>"
             f"<div style='font-size:23px;color:#111111;margin-top:3px;'><b>{nombre}</b></div>"
             f"<div style='font-size:11px;color:#9a9a9a;margin-top:3px;'>Resultado de evaluación de la solicitud</div>"
             f"</td></tr></table></td></tr>"
             f"<tr><td style='padding:22px 38px 4px;font-family:Georgia,serif;font-size:14px;line-height:1.75;color:#222222;'>"
             f"<p style='margin:0 0 14px;'>Estimado(a) ejecutivo(a): la solicitud gestionada por usted para el cliente <b>{nombre}</b> no podrá continuar su curso en las condiciones presentadas.</p></td></tr>"
             f"<tr><td style='padding:0 38px;'>"
             f"<table role='presentation' width='100%' cellpadding='0' cellspacing='0' style='background-color:#faf8f1;border-left:3px solid #d4af37;'>"
             f"<tr><td style='padding:14px 20px;font-family:Georgia,serif;font-size:13.5px;line-height:1.7;color:#222222;'>"
             f"<b style='color:#8a6a0f;'>MOTIVO:</b> {motivo}</td></tr></table>"
             f"<table role='presentation' width='100%' cellpadding='0' cellspacing='0' style='background-color:#f2f6f2;border-left:3px solid #2e7d32;margin-top:10px;'>"
             f"<tr><td style='padding:14px 20px;font-family:Georgia,serif;font-size:13.5px;line-height:1.7;color:#222222;'>"
             f"<b style='color:#2e7d32;'>ACCIÓN RECOMENDADA:</b> {reco}</td></tr></table></td></tr>"
             f"<tr><td style='padding:18px 38px 0;font-family:Georgia,serif;font-size:13.5px;color:#222222;'>"
             f"<p style='margin:0;'>Quedamos a su disposición para acompañarlo(a) en los siguientes pasos.</p></td></tr>"
             + _firma() + "</table>")
    return _marco(inner)


def plantilla_c(nombre, motivo, reco):
    """C — Minimal sobria: blanco puro, nombre grande arriba, línea dorada."""
    inner = ("<table role='presentation' width='600' cellpadding='0' cellspacing='0' style='max-width:600px;width:100%;background-color:#ffffff;'>"
             f"<tr><td align='center' style='padding:34px 38px 0;font-family:Georgia,serif;'>"
             f"<div style='font-size:15px;letter-spacing:5px;color:#111111;'>CENTRAL MUTUOS</div>"
             f"<div style='font-size:9px;letter-spacing:4px;color:#8a6a0f;margin-top:3px;'>CON CRECES · RESULTADO DE EVALUACIÓN</div>"
             f"<div style='width:70px;height:3px;background-color:#d4af37;margin:16px auto;'></div>"
             f"<div style='font-size:24px;color:#111111;'><b>{nombre}</b></div></td></tr>"
             f"<tr><td style='padding:24px 44px 4px;font-family:Georgia,serif;font-size:14px;line-height:1.8;color:#222222;'>"
             f"<p style='margin:0 0 14px;'>Estimado(a) ejecutivo(a):</p>"
             f"<p style='margin:0 0 14px;'>La solicitud de crédito del cliente <b>{nombre}</b>, gestionada por usted, no podrá continuar su curso en las condiciones presentadas.</p>"
             f"<p style='margin:0 0 4px;font-size:11px;letter-spacing:2px;color:#8a6a0f;'><b>MOTIVO DE LA RESOLUCIÓN</b></p>"
             f"<p style='margin:0 0 16px;'>{motivo}</p>"
             f"<p style='margin:0 0 4px;font-size:11px;letter-spacing:2px;color:#8a6a0f;'><b>ACCIÓN RECOMENDADA</b></p>"
             f"<p style='margin:0 0 16px;'>{reco}</p>"
             f"<p style='margin:0;'>Quedamos a su disposición para acompañarlo(a) en la reestructuración de la operación.</p></td></tr>"
             + _firma().replace("38px", "44px") + "</table>")
    return _marco(inner)


PLANTILLAS = {"a": plantilla_a, "b": plantilla_b, "c": plantilla_c}


async def _plantilla_aprobada():
    cfg = await db.config.find_one({"_key": "rechazo_plantilla"}) or {}
    return cfg.get("aprobada")


async def _email_ejecutivo(folder):
    src = (folder.get("source_email") or "").strip().lower()
    if src and "@" in src:
        ej = await db.ejecutivos_correo.find_one({"email": {"$regex": f"^{re.escape(src)}$", "$options": "i"}})
        if ej:
            return ej["email"]
        if src.endswith("@centralmutuos.cl"):
            return src
    return FALLBACK_EJECUTIVO


async def _enviar(pend, plantilla, forzar=False):
    import email_service as mail
    html = PLANTILLAS[plantilla](pend["cliente"], pend["motivo"], pend["recomendacion"])
    asunto = f"Resultado de evaluación — {pend['cliente']}"
    res = await asyncio.to_thread(
        lambda: mail.send_mail(pend["destinatario"], asunto, html,
                               from_name="Central Mutuos", hilo_nuevo=True,
                               permitir_duplicado=forzar))
    ok = bool(res.get("success") or res.get("preview"))
    await db.rechazos_notificados.insert_one({
        "id": str(uuid.uuid4()), "cliente": pend["cliente"], "folder_id": pend.get("folder_id", ""),
        "destinatario": pend["destinatario"], "plantilla": plantilla, "motivo": pend["motivo"],
        "recomendacion": pend["recomendacion"], "enviado": ok,
        "en_preview": bool(res.get("preview")), "smtp": res.get("smtp_code"),
        "fecha": _now()})
    return ok


async def procesar_rechazo(folder, texto, subject):
    """Llamado por mesa_verdad al detectar un rechazo. Si hay plantilla aprobada envía
    automáticamente; si no, deja el caso pendiente de aprobación de diseño.
    NORMATIVA RECHAZO TEXTO EXACTO: el motivo es el texto exacto del canal oficial;
    si viene vacío o contiene referencias prohibidas, se RETIENE para revisión manual."""
    motivo, reco = motivo_y_recomendacion(texto)
    pend = {"id": str(uuid.uuid4()), "cliente": (folder or {}).get("nombre") or "CLIENTE",
            "folder_id": (folder or {}).get("id", ""),
            "destinatario": await _email_ejecutivo(folder or {}),
            "motivo": motivo, "recomendacion": reco,
            "asunto_origen": (subject or "")[:150], "estado": "pendiente", "creado": _now()}
    if not motivo or RX_ORIGEN_PROHIBIDO.search(motivo):
        pend["estado"] = "retenido_revision_manual"
        pend["retencion_causa"] = ("texto de origen vacío" if not motivo else
                                   "el texto exacto contiene referencias al origen o direcciones de correo")
        await db.rechazos_pendientes.insert_one(pend)
        await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "rechazo_retenido",
                                     "leida": False, "cliente": pend["cliente"],
                                     "mensaje": (f"⛔ Notificación de resultado para {pend['cliente']} RETENIDA "
                                                 f"(norma texto exacto): {pend['retencion_causa']} — revisión manual requerida"),
                                     "fecha": _now()})
        return {"enviado": False, "retenido": True, "causa": pend["retencion_causa"]}
    plantilla = await _plantilla_aprobada()
    if plantilla:
        ok = await _enviar(pend, plantilla)
        pend["estado"] = "enviado" if ok else "error_envio"
        await db.rechazos_pendientes.insert_one(pend)
        return {"enviado": ok, "plantilla": plantilla, "destinatario": pend["destinatario"]}
    await db.rechazos_pendientes.insert_one(pend)
    await db.alertas.insert_one({"id": str(uuid.uuid4()), "tipo": "rechazo_diseno_pendiente",
                                 "leida": False, "cliente": pend["cliente"],
                                 "mensaje": (f"📩 Notificación de resultado para {pend['cliente']} en espera: "
                                             "el Administrador debe aprobar el diseño de plantilla en /aprobar-rechazo.html"),
                                 "fecha": _now()})
    return {"enviado": False, "pendiente_diseno": True}


# ─────────────────────────── API ───────────────────────────
CASO_PRUEBA = {"cliente": "ANITA ALVAREZ", "complemento": "DS19",
               "texto": "no cumple parámetro objetivo de evaluación",
               }


@rechz.get("/opciones")
async def opciones(nombre: str = "", motivo_txt: str = ""):
    nombre = nombre or CASO_PRUEBA["cliente"]
    motivo, reco = motivo_y_recomendacion(motivo_txt or CASO_PRUEBA["texto"])
    return {"cliente": nombre, "motivo": motivo, "recomendacion": reco,
            "opciones": {k: fn(nombre, motivo, reco) for k, fn in PLANTILLAS.items()},
            "aprobada": await _plantilla_aprobada()}


@rechz.post("/aprobar")
async def aprobar(payload: dict):
    if not await _clave_admin_ok(payload):
        raise HTTPException(status_code=403, detail="Clave incorrecta")
    p = (payload.get("plantilla") or "").lower()
    if p not in PLANTILLAS:
        raise HTTPException(status_code=400, detail="Plantilla inválida (a, b o c)")
    await db.config.update_one({"_key": "rechazo_plantilla"},
                               {"$set": {"aprobada": p, "aprobada_en": _now()}}, upsert=True)
    enviados = []
    async for pend in db.rechazos_pendientes.find({"estado": "pendiente"}):
        ok = await _enviar(pend, p)
        await db.rechazos_pendientes.update_one({"id": pend["id"]}, {"$set": {
            "estado": "enviado" if ok else "error_envio", "plantilla": p, "enviado_en": _now()}})
        enviados.append({"cliente": pend["cliente"], "destinatario": pend["destinatario"], "ok": ok})
    return {"ok": True, "plantilla_fija": p, "pendientes_enviados": enviados}


@rechz.get("/estado")
async def estado():
    pend = await db.rechazos_pendientes.find({}, {"_id": 0}).sort("creado", -1).to_list(30)
    envi = await db.rechazos_notificados.find({}, {"_id": 0}).sort("fecha", -1).to_list(30)
    return {"plantilla_aprobada": await _plantilla_aprobada(), "pendientes": pend, "notificados": envi}


@rechz.post("/probar")
async def probar(payload: dict):
    """Caso real de prueba: Anita Álvarez, complemento DS19, no cumple parámetro objetivo."""
    if not await _clave_admin_ok(payload):
        raise HTTPException(status_code=403, detail="Clave incorrecta")
    f = await db.folders.find_one({"nombre": {"$regex": "anita\\s+alvarez", "$options": "i"}}) or \
        {"nombre": CASO_PRUEBA["cliente"], "id": "", "source_email": ""}
    motivo, reco = motivo_y_recomendacion(CASO_PRUEBA["texto"])
    pend = {"id": str(uuid.uuid4()), "cliente": f.get("nombre") or CASO_PRUEBA["cliente"],
            "folder_id": f.get("id", ""), "destinatario": await _email_ejecutivo(f),
            "motivo": motivo, "recomendacion": reco,
            "asunto_origen": "Caso Anita Álvarez — complemento DS19",
            "estado": "pendiente", "creado": _now()}
    plantilla = await _plantilla_aprobada()
    if not plantilla:
        r = await procesar_rechazo(f, CASO_PRUEBA["texto"], pend["asunto_origen"])
        return {"ok": True, "resultado": r}
    ok = await _enviar(pend, plantilla, forzar=True)
    pend["estado"] = "enviado" if ok else "error_envio"
    await db.rechazos_pendientes.insert_one(pend)
    return {"ok": True, "resultado": {"enviado": ok, "plantilla": plantilla,
                                      "destinatario": pend["destinatario"]}}
