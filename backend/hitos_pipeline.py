"""Estados automáticos del pipeline de escrituración (sin I/O)."""
import re

PREGUNTAS = {
    "tasacion": "¿Por qué no está la tasación?",
    "estudio": "¿En qué estado está el estudio de título?",
    "serie": "¿En qué estado está la serie de crédito firmada?",
}

_SERIE_OK = {"firmado", "ok", "emitido", "firma", "completa"}


def _serie_ok(fd):
    if fd.get("set_firmado") or fd.get("set_credito_firmado"):
        return True
    est = str(fd.get("set_credito_estado") or "").strip().lower()
    return any(k in est for k in _SERIE_OK)


def _semaforo(ok, proc, alerta=False):
    if alerta:
        return "alerta"
    if ok:
        return "ok"
    if proc:
        return "proceso"
    return "pendiente"


def estados_hitos(fd):
    """Indicadores automáticos: ok / proceso / alerta / pendiente. Sin inventar fechas."""
    fd = fd or {}
    tas = fd.get("tasacion_ocr") if isinstance(fd.get("tasacion_ocr"), dict) else {}
    tas_ok = bool(fd.get("tasacion_informe_recibido_at") or tas.get("valor_uf") or tas.get("rol_avaluo"))
    tas_proc = bool(fd.get("tasacion_solicitada_at") or (fd.get("reclamos_gerencia") or {}).get("tasacion"))
    reparos = fd.get("reparos_alertas") or []
    est_ok = bool(fd.get("estudio_recibido_at") or fd.get("estudio_titulo_terminado_at")) and not reparos
    est_alerta = bool(reparos)
    est_proc = bool(fd.get("estudio_titulo_solicitado_at") or fd.get("estudio_recibido_at"))
    serie_ok = _serie_ok(fd)
    serie_proc = bool(fd.get("set_enviado") or fd.get("set_credito_at"))
    esc_ok = bool(fd.get("escritura_confirmada_at") or fd.get("escritura_firmada"))
    esc_proc = bool(fd.get("escritura_solicitada_at") or fd.get("escritura_notaria_detectada_at"))
    return {
        "tasacion": _semaforo(tas_ok, tas_proc),
        "estudio": _semaforo(est_ok, est_proc, est_alerta),
        "serie": _semaforo(serie_ok, serie_proc),
        "escritura": _semaforo(esc_ok, esc_proc),
    }


def estados_radar(fd):
    """Notaría, CBR y pagaré leídos de la carpeta. No inventa inscripción ni fechas."""
    fd = fd or {}
    h = dict(estados_hitos(fd))
    esc = fd.get("escritura_ocr") if isinstance(fd.get("escritura_ocr"), dict) else {}
    notaria_ok = bool(fd.get("escritura_notaria_detectada_at") or fd.get("escritura_confirmada_at"))
    notaria_alerta = bool(fd.get("alerta_notaria_ciudad")) and not notaria_ok
    notaria_proc = bool(str(fd.get("notaria") or "").strip() or fd.get("escritura_solicitada_at")
                        or fd.get("fecha_firma") or fd.get("fecha_firma_detectada"))
    cbr_ok = bool(fd.get("ingreso_cbr_at") or fd.get("cbr_inscrito_at"))
    cbr_proc = bool(esc.get("repertorio") or notaria_ok or fd.get("fecha_firma"))
    pagare_ok = bool(fd.get("pagare_entregado_at") or fd.get("pagare_at"))
    pagare_proc = bool(notaria_ok and not pagare_ok)
    h["notaria"] = _semaforo(notaria_ok, notaria_proc, notaria_alerta)
    h["cbr"] = _semaforo(cbr_ok, cbr_proc)
    h["pagare"] = _semaforo(pagare_ok, pagare_proc)
    return h


def _dias_iso(iso):
    if not iso:
        return 0
    try:
        from datetime import datetime, timezone
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return round((datetime.now(timezone.utc) - d).total_seconds() / 86400, 1)
    except Exception:
        return 0


def alertas_radar(fd, plazos=None, inicio_iso=""):
    """Alertas de cuello notaría/CBR/pagaré. No envía correo."""
    plazos = plazos or {}
    est = estados_radar(fd)
    ref = inicio_iso or fd.get("escritura_confirmada_at") or fd.get("fecha_firma") or ""
    dias = _dias_iso(ref)
    out = []
    pe = float(plazos.get("escritura") or 15)
    pp = float(plazos.get("entrega_pagare") or 7)
    if est.get("notaria") == "alerta":
        out.append("Notaría: desalineación de ciudad o firma pendiente de confirmar")
    if est.get("notaria") in ("pendiente", "proceso") and dias > pe:
        out.append(f"Notaría sin cierre a {dias} días (plazo escritura {int(pe)}d)")
    if est.get("notaria") == "ok" and est.get("cbr") != "ok" and dias > pe:
        out.append("CBR pendiente: escritura en notaría sin ingreso al Conservador")
    if est.get("pagare") != "ok" and est.get("notaria") == "ok" and dias > pp:
        out.append(f"Pagaré no registrado a {dias} días (plazo {int(pp)}d)")
    return {"hitos": est, "alertas": out, "dias_desde_firma": dias}


def estado_tras_mensaje(estado_actual, autor_es_broker, cerrar_explicit=False):
    """Broker cierra; Gerencia reabre el hilo para que el broker lo vuelva a ver."""
    if autor_es_broker or cerrar_explicit:
        return "respondida"
    return "abierta"


def folder_es_de_broker(fd, user):
    sub = str((user or {}).get("sub") or "").strip()
    nombre = str((user or {}).get("nombre") or "").strip()
    if not sub and not nombre:
        return False
    cod = str((fd or {}).get("broker_codigo") or (fd or {}).get("proyeccion_broker") or "")
    orig = str((fd or {}).get("broker_origen") or (fd or {}).get("broker_nombre") or "")
    if sub and (sub == cod or (len(sub) >= 4 and sub.lower() in orig.lower())):
        return True
    if nombre and len(nombre) >= 4 and nombre.lower() in orig.lower():
        return True
    return False


def filtro_carpetas_broker(user):
    """Carpetas de un broker: código, proyección y nombre de origen."""
    sub = str((user or {}).get("sub") or "").strip()
    nombre = str((user or {}).get("nombre") or "").strip()
    or_ = []
    if sub:
        or_.extend([{"broker_codigo": sub}, {"proyeccion_broker": sub}])
    if nombre:
        rx = {"$regex": re.escape(nombre[:25]), "$options": "i"}
        or_.extend([{"broker_origen": rx}, {"broker_nombre": rx}])
    return {"$or": or_} if or_ else {"id": "__ninguna__"}


def cuello_botella(fd, estados=None):
    """Hito más atrasado para el botón de seguimiento."""
    est = estados or estados_hitos(fd)
    for hito, pregunta in PREGUNTAS.items():
        if est.get(hito) not in ("ok",):
            return {"hito": hito, "pregunta": pregunta, "estado": est.get(hito)}
    return None
