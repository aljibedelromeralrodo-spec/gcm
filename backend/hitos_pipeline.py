"""Estados automáticos del pipeline de escrituración (sin I/O)."""

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

    def _est(ok, proc, alerta=False):
        if alerta:
            return "alerta"
        if ok:
            return "ok"
        if proc:
            return "proceso"
        return "pendiente"

    return {
        "tasacion": _est(tas_ok, tas_proc),
        "estudio": _est(est_ok, est_proc, est_alerta),
        "serie": _est(serie_ok, serie_proc),
        "escritura": _est(esc_ok, esc_proc),
    }


def cuello_botella(fd, estados=None):
    """Hito más atrasado para el botón de seguimiento."""
    est = estados or estados_hitos(fd)
    for hito, pregunta in PREGUNTAS.items():
        if est.get(hito) not in ("ok",):
            return {"hito": hito, "pregunta": pregunta, "estado": est.get(hito)}
    return None
