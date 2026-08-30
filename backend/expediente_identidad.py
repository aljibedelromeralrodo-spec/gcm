"""Identidad y contenido de la supercarpeta (expediente único por cliente).

Claves de unicidad: RUT titular, RUT codeudor (validación cruzada) y Rol de Avalúo.
No inventa montos ni envía a plataformas externas: solo consolida y arma el payload.
"""
from __future__ import annotations

import re

import folders_service as fsvc

# Mapeo de carga a Concreces (espejo de bodega_concreces.CONCRECES_MAPEO + extras del expediente).
MAPEO_CONCRECES = {
    "Ingreso_Mesa": [
        "rut_titular", "rut_codeudor", "renta_promedio", "renta_codeudor",
        "monto_credito_uf", "subsidio", "plazo_anos", "tipo_vivienda",
    ],
    "Tasacion": [
        "rol_propiedad", "direccion", "comuna", "valor_propiedad_uf",
        "valor_tasacion_uf", "tipo_vivienda",
    ],
    "Riesgo": [
        "deuda_cmf_total", "deuda_cmf_codeudor", "carga_financiera", "ltv", "renta_promedio",
    ],
    "Escrituracion": [
        "notaria", "repertorio", "fecha_firma", "estado_notaria", "fojas", "numero", "anio", "cbr",
    ],
}

# Campos opcionales: no bloquean listo_para_carga si el codeudor no aplica.
_OPCIONALES_SIN_CODEUDOR = {
    "rut_codeudor", "renta_codeudor", "deuda_cmf_codeudor",
}

_RX_ROL = re.compile(r"^\d{1,6}-\d{1,6}$")
_RX_SEGURO = re.compile(
    r"dps|p[oó]liza|desgravamen|incendio|cesant[ií]a|autorizaci[oó]n.{0,20}seguro", re.I)
_RX_APROB = re.compile(r"aprobaci[oó]n|carta\s+oferta|pre.?aprob", re.I)


def norm_rut(rut):
    return re.sub(r"[^0-9kK]", "", str(rut or "")).lower()


def fmt_rut(rut):
    r = norm_rut(rut)
    if len(r) < 8:
        return str(rut or "").strip()
    cuerpo, dv = r[:-1], r[-1].upper()
    partes = []
    while cuerpo:
        partes.insert(0, cuerpo[-3:])
        cuerpo = cuerpo[:-3]
    return ".".join(partes) + "-" + dv


def dv_ok(rut):
    """Dígito verificador módulo 11 (mismo criterio que Regla #65 / #66)."""
    r = norm_rut(rut)
    if len(r) < 8 or not r[:-1].isdigit():
        return False
    cuerpo, dv = r[:-1], r[-1]
    s, m = 0, 2
    for c in reversed(cuerpo):
        s += int(c) * m
        m = 2 if m == 7 else m + 1
    res = 11 - (s % 11)
    dv_calc = "0" if res == 11 else ("k" if res == 10 else str(res))
    return dv == dv_calc


def norm_rol(rol):
    t = str(rol or "").replace("–", "-").replace("—", "-")
    t = re.sub(r"[^\d-]", "", t)
    m = re.search(r"(\d{1,6})-(\d{1,6})", t)
    if not m:
        return ""
    return f"{m.group(1)}-{m.group(2)}"


def _primera(*vals):
    for v in vals:
        if v not in (None, "", [], {}):
            return v
    return None


def clasificar_clave(q):
    """Detecta si la búsqueda es RUT, rol de avalúo o texto libre."""
    raw = str(q or "").strip()
    if not raw:
        return {"tipo": "vacio", "norm": "", "raw": ""}
    roln = norm_rol(raw)
    rn = norm_rut(raw)
    if dv_ok(raw):
        return {"tipo": "rut", "norm": rn, "raw": raw}
    if roln and _RX_ROL.match(roln) and len(rn) < 8:
        return {"tipo": "rol", "norm": roln, "raw": raw}
    if len(rn) >= 8:
        return {"tipo": "rut", "norm": rn, "raw": raw}
    if roln:
        return {"tipo": "rol", "norm": roln, "raw": raw}
    return {"tipo": "texto", "norm": raw.lower(), "raw": raw}


def filtro_busqueda(q):
    """Filtro Mongo para ADN: RUT titular, RUT codeudor, rol o texto."""
    raw = str(q or "").strip()
    if not raw:
        return None
    rx = {"$regex": re.escape(raw), "$options": "i"}
    clauses = [
        {"rut": rx},
        {"identidad.nombre": rx},
        {"identidad.email": rx},
        {"propiedad.inmobiliaria": rx},
        {"propiedad.proyecto": rx},
        {"codeudor_rut": rx},
        {"rol_avaluo": rx},
        {"propiedad.rol": rx},
    ]
    clave = clasificar_clave(raw)
    if clave["tipo"] == "rut" and clave["norm"]:
        rx8 = {"$regex": re.escape(clave["norm"][:8]), "$options": "i"}
        clauses.extend([
            {"rut_norm": clave["norm"]},
            {"codeudor_rut_norm": clave["norm"]},
            {"expediente_360.codeudor.rut": rx8},
            {"expediente_360.claves.rut_codeudor_norm": clave["norm"]},
        ])
    elif clave["tipo"] == "rol" and clave["norm"]:
        clauses.extend([
            {"rol_norm": clave["norm"]},
            {"expediente_360.propiedad.rol": clave["norm"]},
            {"expediente_360.claves.rol_norm": clave["norm"]},
        ])
    return {"$or": clauses}


def filtro_folder_por_clave(q):
    """Filtro Mongo sobre `folders` por las mismas tres claves."""
    clave = clasificar_clave(q)
    if clave["tipo"] == "rut" and clave["norm"]:
        cuerpo = re.escape(clave["norm"][:8])
        rx = {"$regex": cuerpo, "$options": "i"}
        return {"$or": [{"rut": rx}, {"codeudor_rut": rx}]}
    if clave["tipo"] == "rol" and clave["norm"]:
        rx = {"$regex": re.escape(clave["norm"]), "$options": "i"}
        return {"$or": [
            {"datos_financieros.rol_avaluo": rx},
            {"datos_financieros.rol_propiedad": rx},
            {"tasacion_ocr.rol_avaluo": rx},
            {"perfil_consolidado.rol_propiedad": rx},
            {"roots.rol_propiedad": rx},
        ]}
    raw = str(q or "").strip()
    if len(raw) < 3:
        return None
    rx = {"$regex": re.escape(raw), "$options": "i"}
    return {"$or": [{"nombre": rx}, {"rut": rx}]}


def _fuentes_rol(fd, extras=None):
    extras = extras or {}
    p = fd.get("perfil_consolidado") or {}
    df = fd.get("datos_financieros") or {}
    roots = fd.get("roots") or {}
    tas = fd.get("tasacion_ocr") or {}
    est = fd.get("estudio_ocr") or {}
    comp = extras.get("compromiso") or {}
    cdat = comp.get("datos") if isinstance(comp.get("datos"), dict) else (
        comp if isinstance(comp.get("propiedad"), dict) else {})
    cprop = (cdat or {}).get("propiedad") or {}
    pares = [
        ("compromiso", cprop.get("rol_avaluo") or cprop.get("rol")),
        ("tasacion_ocr", tas.get("rol_avaluo") if isinstance(tas, dict) else None),
        ("datos_financieros", df.get("rol_avaluo") or df.get("rol_propiedad")),
        ("perfil", p.get("rol_propiedad") or p.get("rol_avaluo")),
        ("roots", roots.get("rol_propiedad")),
        ("estudio_ocr", est.get("rol_avaluo") if isinstance(est, dict) else None),
        ("folder", fd.get("rol_avaluo")),
    ]
    out = []
    vistos = set()
    for fuente, val in pares:
        n = norm_rol(val)
        if not n or n in vistos:
            continue
        vistos.add(n)
        out.append({"fuente": fuente, "rol": n, "raw": str(val).strip()})
    return out


def identidad_de_folder(fd, extras=None):
    """Tres claves de la supercarpeta + procedencia de cada una."""
    extras = extras or {}
    p = fd.get("perfil_consolidado") or {}
    df = fd.get("datos_financieros") or {}
    sim = extras.get("simulacion") or {}
    comp = extras.get("compromiso") or {}
    cdat = comp.get("datos") if isinstance(comp.get("datos"), dict) else (
        comp if isinstance(comp.get("comprador"), dict) else {})
    comprador = (cdat or {}).get("comprador") or {}

    rut_t = _primera(fd.get("rut"), comprador.get("rut"), sim.get("rut"), p.get("rut"))
    rut_c = _primera(
        fd.get("codeudor_rut"), p.get("rut_codeudor"),
        sim.get("rut_codeudor"), df.get("rut_codeudor"))
    nom_c = _primera(
        fd.get("codeudor_nombre"), p.get("nombre_codeudor"), sim.get("nombre_codeudor"))
    roles = _fuentes_rol(fd, extras)
    rol = roles[0]["rol"] if roles else ""
    return {
        "rut_titular": fmt_rut(rut_t) if rut_t else (str(rut_t or "").strip()),
        "rut_titular_norm": norm_rut(rut_t),
        "rut_codeudor": fmt_rut(rut_c) if rut_c else (str(rut_c or "").strip()),
        "rut_codeudor_norm": norm_rut(rut_c),
        "codeudor_nombre": nom_c or "",
        "rol_avaluo": rol,
        "rol_norm": rol,
        "fuentes": {
            "rut_titular": "folder.rut" if fd.get("rut") else (
                "compromiso" if comprador.get("rut") else "simulacion" if sim.get("rut") else ""),
            "rut_codeudor": "folder.codeudor_rut" if fd.get("codeudor_rut") else (
                "perfil" if p.get("rut_codeudor") else "simulacion" if sim.get("rut_codeudor") else ""),
            "rol": roles[0]["fuente"] if roles else "",
        },
        "roles_fuentes": roles,
    }


def validar_identidad(ident):
    """Validación cruzada: DV, titular ≠ codeudor, rol único entre fuentes."""
    ident = ident or {}
    alertas = []
    rt = ident.get("rut_titular_norm") or ""
    rc = ident.get("rut_codeudor_norm") or ""
    titular_ok = dv_ok(rt) if rt else False
    if not rt:
        alertas.append("RUT del titular ausente: la supercarpeta no tiene eje de unicidad")
    elif not titular_ok:
        alertas.append("RUT del titular con dígito verificador inválido")
    codeudor_ok = None
    ruts_distintos = None
    if rc:
        codeudor_ok = dv_ok(rc)
        if not codeudor_ok:
            alertas.append("RUT del codeudor con dígito verificador inválido")
        if rt and rc == rt:
            ruts_distintos = False
            alertas.append("Validación cruzada: el RUT del codeudor coincide con el del titular")
        elif rt:
            ruts_distintos = True
    roles = ident.get("roles_fuentes") or []
    normas = {r["rol"] for r in roles if r.get("rol")}
    rol_ok = None
    if len(normas) > 1:
        rol_ok = False
        detalle = ", ".join(f"{r['fuente']}={r['rol']}" for r in roles)
        alertas.append(f"Rol de avalúo desalineado entre fuentes: {detalle}")
    elif len(normas) == 1:
        rol_ok = True
    elif not ident.get("rol_norm"):
        alertas.append("Rol de avalúo de la propiedad no registrado")
    return {
        "ok": not alertas,
        "alertas": alertas,
        "titular_dv_ok": titular_ok,
        "codeudor_dv_ok": codeudor_ok,
        "ruts_distintos": ruts_distintos,
        "rol_consistente": rol_ok,
    }


def conflictos_unicidad(ident, otros):
    """Detecta otra carpeta con el mismo RUT titular, mismo codeudor o mismo rol."""
    ident = ident or {}
    rt = ident.get("rut_titular_norm") or ""
    rc = ident.get("rut_codeudor_norm") or ""
    rol = ident.get("rol_norm") or ""
    out = []
    for o in otros or []:
        fid = o.get("id") or o.get("folder_id") or ""
        ot = norm_rut(o.get("rut") or o.get("rut_titular") or "")
        oc = norm_rut(o.get("codeudor_rut") or o.get("rut_codeudor") or "")
        orol = norm_rol(o.get("rol_avaluo") or o.get("rol") or "")
        if rt and ot and rt == ot:
            out.append({"tipo": "rut_titular", "folder_id": fid, "valor": rt})
        if rc and ot and rc == ot:
            out.append({"tipo": "codeudor_es_titular_de_otra", "folder_id": fid, "valor": rc})
        if rt and oc and rt == oc:
            out.append({"tipo": "titular_es_codeudor_de_otra", "folder_id": fid, "valor": rt})
        if rol and orol and rol == orol and ot != rt:
            out.append({"tipo": "rol_avaluo", "folder_id": fid, "valor": rol})
    return out


def tipo_vivienda_de(fd, df=None):
    df = df if df is not None else (fd.get("datos_financieros") or {})
    tv = str(df.get("tipo_vivienda") or "").strip().lower()
    if tv in ("nueva", "usada"):
        return tv
    op = str(fd.get("tipo_operacion") or "").strip().lower()
    if op == "usada":
        return "usada"
    if op in ("nueva", "inmobiliaria"):
        return "nueva"
    return ""


def _cat_rel(rel):
    rel = str(rel or "").replace("\\", "/")
    parts = rel.split("/")
    sub = parts[0] if len(parts) > 1 else ""
    return fsvc.cat_de_archivo(parts[-1], sub)


def _docs_perfil(fd):
    archivos = [a for a in (fd.get("archivos") or []) if isinstance(a, str)]
    por_cat = {}
    docs = []
    nombre = fd.get("nombre") or ""
    for a in archivos[:200]:
        cat = _cat_rel(a)
        por_cat.setdefault(cat or "extras", []).append(a)
        docs.append({"archivo": a, "categoria": cat or "extras",
                     "link_boveda": f"{nombre}/{a}" if nombre else a,
                     "fuente": "boveda_local"})
    return docs, por_cat


def _num(v):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _ltv(df, tasacion_uf=None):
    m = _num(df.get("monto_credito") or df.get("monto_credito_uf"))
    v = _num(df.get("valor_propiedad") or df.get("valor_propiedad_uf") or tasacion_uf)
    if m is not None and v and v > 0:
        return round(m / v * 100, 1)
    return _num(df.get("ltv"))


def construir_expediente(fd, extras=None):
    """Expediente centralizado. extras: simulacion, compromiso, gastos, set_credito, hilo_estudio."""
    extras = extras or {}
    sim = extras.get("simulacion") or {}
    comp = extras.get("compromiso") or {}
    cdat = comp.get("datos") if isinstance(comp.get("datos"), dict) else {}
    cprop = cdat.get("propiedad") or {}
    cvend = cdat.get("vendedor") or {}
    df = fd.get("datos_financieros") or {}
    p = fd.get("perfil_consolidado") or {}
    tas = fd.get("tasacion_ocr") if isinstance(fd.get("tasacion_ocr"), dict) else {}
    est = fd.get("estudio_ocr") if isinstance(fd.get("estudio_ocr"), dict) else {}
    esc = fd.get("escritura_ocr") if isinstance(fd.get("escritura_ocr"), dict) else {}
    ident = identidad_de_folder(fd, extras)
    cruzada = validar_identidad(ident)
    docs, por_cat = _docs_perfil(fd)
    tv = tipo_vivienda_de(fd, df)
    valor_tas = _primera(tas.get("valor_uf"), df.get("valor_tasacion_uf"))
    gastos_doc = extras.get("gastos") or fd.get("gastos_operacionales") or {}
    setc = extras.get("set_credito") or {}
    hilo = extras.get("hilo_estudio") or []
    rep_raw = fd.get("estudio_reparos")
    rep_estado = rep_raw.get("estado", "") if isinstance(rep_raw, dict) else (rep_raw or "")
    rep_textos = " | ".join((r.get("texto") or "")[:250] for r in (fd.get("reparos_alertas") or [])[:5])
    presente_cod = bool(
        ident.get("rut_codeudor_norm") or ident.get("codeudor_nombre") or sim.get("tiene_codeudor"))
    polizas = [a for a in (fd.get("archivos") or []) if isinstance(a, str) and _RX_SEGURO.search(a)]
    aprob_arch = [a for a in (fd.get("archivos") or []) if isinstance(a, str) and _RX_APROB.search(a)]
    tasacion_estado = (
        "Informe Recibido" if fd.get("tasacion_informe_recibido_at")
        else "Visita" if fd.get("tasacion_fecha")
        else "Solicitada" if (fd.get("reclamos_gerencia") or {}).get("tasacion")
        or fd.get("tasacion_solicitada_at")
        else "Pendiente")
    hitos = {
        "estudio_titulos_recibido": fd.get("estudio_recibido_at") or "",
        "estudio_titulos_terminado": fd.get("estudio_titulo_terminado_at") or "",
        "estudio_reparos": rep_textos or rep_estado,
        "tasacion_estado": tasacion_estado,
        "firma_cesion": ("Confirmada" if fd.get("firma_cesion_confirmada_at")
                         or fd.get("escritura_confirmada_at")
                         or fd.get("escritura_notaria_detectada_at") else "Pendiente"),
        "reparos": rep_textos or rep_estado,
        "borrador_escritura": fd.get("escritura_confirmada_at") or "",
        "fecha_firma": fd.get("fecha_firma") or fd.get("fecha_firma_detectada") or "",
        "set_credito": {"estado": fd.get("set_credito_estado") or setc.get("estado") or "",
                        "evidencia": fd.get("set_credito_evidencia") or "",
                        "fecha": str(fd.get("set_credito_at") or setc.get("created_at") or "")[:19]},
        "anexos_notaria": fd.get("anexos_notaria") or "",
    }
    return {
        "claves": ident,
        "validacion_cruzada": cruzada,
        "titular": {
            "nombre": fd.get("nombre_completo") or fd.get("nombre") or "",
            "rut": ident.get("rut_titular") or fd.get("rut") or "",
            "renta_liquida": sim.get("renta_liquida") or df.get("renta_liquida"),
            "deudas_cmf": sim.get("carga_fin_individual") or df.get("deuda_cmf"),
            "afp": p.get("afp") or "",
            "telefono": sim.get("telefono") or p.get("telefono") or "",
            "email": sim.get("correo") or p.get("email") or "",
        },
        "codeudor": {
            "presente": presente_cod,
            "rut": ident.get("rut_codeudor") or "",
            "nombre": ident.get("codeudor_nombre") or "",
            "renta": sim.get("div_renta_codeudor") or df.get("renta_codeudor"),
            "deudas_cmf": sim.get("carga_fin_codeudor") or df.get("deuda_cmf_codeudor"),
            "afp": p.get("afp_codeudor") or "",
            "contacto": p.get("contacto_codeudor") or "",
        },
        "propiedad": {
            "direccion": cprop.get("direccion") or p.get("direccion") or tas.get("direccion") or "",
            "comuna": cprop.get("comuna") or p.get("comuna") or tas.get("comuna") or "",
            "rol": ident.get("rol_avaluo") or "",
            "fojas": cprop.get("fojas") or est.get("fojas") or "",
            "numero": cprop.get("numero") or est.get("numero") or "",
            "anio": cprop.get("anio") or est.get("anio") or "",
            "cbr": cprop.get("cbr") or est.get("cbr") or "",
            "inmobiliaria": fd.get("inmobiliaria") or "",
            "proyecto": fd.get("proyecto") or "",
            "tasacion": {
                "fecha": fd.get("tasacion_fecha") or tas.get("fecha") or "",
                "informe_recibido_at": fd.get("tasacion_informe_recibido_at") or "",
                "asunto_informe": fd.get("tasacion_informe_asunto") or "",
            },
            "contacto_vendedor": {
                "nombre": cvend.get("nombre") or "",
                "rut": cvend.get("rut") or "",
            },
        },
        "perfil_documental": {
            "por_categoria": {k: len(v) for k, v in por_cat.items()},
            "acreditacion": {
                cat: por_cat.get(cat) or []
                for cat in ("cedula", "liquidacion", "afp", "cmf", "imp_renta", "boletas", "f29", "contrato")
                if por_cat.get(cat)
            },
            "codeudor": por_cat.get("codeudor") or [],
        },
        "gastos_operacionales": {
            "total": gastos_doc.get("total") if isinstance(gastos_doc, dict) else None,
            "items": gastos_doc.get("items") if isinstance(gastos_doc, dict) else [],
            "enviado_en": gastos_doc.get("enviado_en") if isinstance(gastos_doc, dict) else "",
            "to": gastos_doc.get("to") if isinstance(gastos_doc, dict) else "",
        },
        "tasacion": {
            "tipo_vivienda": tv,
            "estado": tasacion_estado,
            "solicitada_at": fd.get("tasacion_solicitada_at") or "",
            "visita_at": fd.get("tasacion_fecha") or "",
            "informe_at": fd.get("tasacion_informe_recibido_at") or "",
            "valor_uf": valor_tas,
            "valor_clp": tas.get("valor_clp"),
            "rol_avaluo": ident.get("rol_avaluo") or tas.get("rol_avaluo") or "",
            "comuna": tas.get("comuna") or cprop.get("comuna") or p.get("comuna") or "",
            "tasador": tas.get("tasador") or "",
        },
        "estudio_titulos": {
            "recibido_at": fd.get("estudio_recibido_at") or "",
            "terminado_at": fd.get("estudio_titulo_terminado_at") or "",
            "solicitado_at": fd.get("estudio_titulo_solicitado_at") or "",
            "reparos": rep_textos or rep_estado,
            "fojas": est.get("fojas") or cprop.get("fojas") or "",
            "numero": est.get("numero") or cprop.get("numero") or "",
            "anio": est.get("anio") or cprop.get("anio") or "",
            "cbr": est.get("cbr") or cprop.get("cbr") or "",
            "menciona_gravamen": bool(est.get("menciona_gravamen")),
            "hilo": hilo[:30] if isinstance(hilo, list) else [],
        },
        "aprobaciones": {
            "archivos": aprob_arch[:20],
            "mesa_estado": fd.get("estado_mesa") or "",
            "carta_oferta_at": str((fd.get("bitacora_solicitudes") or [{}])[0].get("en") or "")[:19]
            if fd.get("bitacora_solicitudes") else "",
        },
        "polizas_seguros": {
            "dps_recibido": bool(fd.get("dps_recibido_at")),
            "dps_at": str(fd.get("dps_recibido_at") or "")[:19],
            "archivos": polizas[:20],
        },
        "serie_credito": {
            "estado": fd.get("set_credito_estado") or setc.get("estado") or "",
            "evidencia": fd.get("set_credito_evidencia") or "",
            "fecha": str(fd.get("set_credito_at") or setc.get("created_at") or "")[:19],
            "firmado": bool(fd.get("set_firmado") or fd.get("set_credito_firmado")),
            "escritura_at": str(fd.get("escritura_confirmada_at") or "")[:19],
            "notaria": fd.get("notaria") or esc.get("notaria") or "",
            "repertorio": esc.get("repertorio") or "",
        },
        "financiero": {
            "monto_credito_uf": df.get("monto_credito"),
            "valor_propiedad_uf": df.get("valor_propiedad"),
            "plazo_anos": df.get("plazo_anos"),
            "tasa": df.get("tasa"),
            "con_subsidio": bool(df.get("con_subsidio")),
        },
        "hitos_legales": hitos,
        "documentos": [{"archivo": d["archivo"], "link_boveda": d["link_boveda"],
                        "fuente": d["fuente"]} for d in docs[:150]],
    }


def _valores_concreces(exp):
    exp = exp or {}
    tit = exp.get("titular") or {}
    cod = exp.get("codeudor") or {}
    prop = exp.get("propiedad") or {}
    tas = exp.get("tasacion") or {}
    serie = exp.get("serie_credito") or {}
    est = exp.get("estudio_titulos") or {}
    claves = exp.get("claves") or {}
    # financiero puede vivir en el registro ADN, no en expediente_360
    fin = exp.get("financiero") or {}
    df_monto = _primera(fin.get("monto_credito_uf"), tit.get("monto_credito_uf"))
    valor_prop = _primera(fin.get("valor_propiedad_uf"), tas.get("valor_uf"), prop.get("valor_uf"))
    ltv = exp.get("ltv")
    if ltv is None and df_monto and valor_prop:
        try:
            ltv = round(float(df_monto) / float(valor_prop) * 100, 1)
        except (TypeError, ValueError, ZeroDivisionError):
            ltv = None
    return {
        "rut_titular": claves.get("rut_titular") or tit.get("rut") or "",
        "rut_codeudor": claves.get("rut_codeudor") or (cod.get("rut") if cod.get("presente") else "") or "",
        "renta_promedio": tit.get("renta_liquida"),
        "renta_codeudor": cod.get("renta"),
        "monto_credito_uf": df_monto,
        "subsidio": bool(fin.get("con_subsidio")),
        "plazo_anos": fin.get("plazo_anos"),
        "tipo_vivienda": tas.get("tipo_vivienda") or "",
        "rol_propiedad": claves.get("rol_avaluo") or prop.get("rol") or tas.get("rol_avaluo") or "",
        "direccion": prop.get("direccion") or "",
        "comuna": prop.get("comuna") or tas.get("comuna") or "",
        "valor_propiedad_uf": valor_prop,
        "valor_tasacion_uf": tas.get("valor_uf"),
        "deuda_cmf_total": tit.get("deudas_cmf"),
        "deuda_cmf_codeudor": cod.get("deudas_cmf"),
        "carga_financiera": tit.get("deudas_cmf"),
        "ltv": ltv,
        "notaria": serie.get("notaria") or "",
        "repertorio": serie.get("repertorio") or "",
        "fecha_firma": serie.get("fecha") or (exp.get("hitos_legales") or {}).get("fecha_firma") or "",
        "estado_notaria": (exp.get("hitos_legales") or {}).get("firma_cesion") or "",
        "fojas": est.get("fojas") or prop.get("fojas") or "",
        "numero": est.get("numero") or prop.get("numero") or "",
        "anio": est.get("anio") or prop.get("anio") or "",
        "cbr": est.get("cbr") or prop.get("cbr") or "",
    }


def payload_concreces(exp, financiero=None):
    """Payload de auto-relleno. No envía nada: comercial y riesgo leen el mismo expediente."""
    exp = dict(exp or {})
    if financiero:
        exp["financiero"] = financiero
    valores = _valores_concreces(exp)
    hay_codeudor = bool((exp.get("codeudor") or {}).get("presente") or valores.get("rut_codeudor"))
    secciones, faltantes, completos = {}, {}, {}
    for sec, campos in MAPEO_CONCRECES.items():
        secciones[sec] = {c: valores.get(c) for c in campos}
        miss, ok = [], []
        for c in campos:
            if c in _OPCIONALES_SIN_CODEUDOR and not hay_codeudor:
                ok.append(c)
                continue
            if valores.get(c) in (None, ""):
                miss.append(c)
            else:
                ok.append(c)
        faltantes[sec] = miss
        completos[sec] = ok
    return {
        "secciones": secciones,
        "faltantes": faltantes,
        "completos": completos,
        "listo_para_carga": not any(faltantes.values()),
        "origen": "expediente_unico",
        "envio": "manual",
        "nota": ("Datos consolidados de la supercarpeta para auto-rellenar Concreces. "
                 "No se envían solos: comercial y riesgo usan el mismo origen."),
    }


def fusionar_vacios(base, extra):
    """Completa huecos. Nunca pisa un valor ya ingresado y no inventa vacíos."""
    out = dict(base or {})
    for k, v in (extra or {}).items():
        if v in (None, "", [], {}):
            continue
        if out.get(k) in (None, "", [], {}):
            out[k] = v
    return out


def campos_mutuos(exp):
    """Campos de las etapas Victoria/Mutuos desde el expediente único (solo lo hallado)."""
    exp = exp or {}
    claves = exp.get("claves") or {}
    tit = exp.get("titular") or {}
    cod = exp.get("codeudor") or {}
    prop = exp.get("propiedad") or {}
    tas = exp.get("tasacion") or {}
    fin = exp.get("financiero") or {}
    serie = exp.get("serie_credito") or {}
    est = exp.get("estudio_titulos") or {}
    return {
        "rut_titular": claves.get("rut_titular") or tit.get("rut") or "",
        "nombre_cliente": tit.get("nombre") or "",
        "rut_codeudor": claves.get("rut_codeudor") or (cod.get("rut") if cod.get("presente") else "") or "",
        "nombre_codeudor": cod.get("nombre") or "",
        "email": tit.get("email") or "",
        "telefono": tit.get("telefono") or "",
        "direccion_propiedad": prop.get("direccion") or "",
        "comuna": prop.get("comuna") or tas.get("comuna") or "",
        "rol_avaluo": claves.get("rol_avaluo") or prop.get("rol") or tas.get("rol_avaluo") or "",
        "valor_tasacion": tas.get("valor_uf") if tas.get("valor_uf") not in (None, "") else "",
        "precio_vivienda": _primera(fin.get("valor_propiedad_uf"), tas.get("valor_uf")),
        "credito_uf": fin.get("monto_credito_uf"),
        "plazo_anos": fin.get("plazo_anos"),
        "subsidio": "con subsidio" if fin.get("con_subsidio") else "",
        "notaria": serie.get("notaria") or "",
        "fecha_estudio_titulo": str(est.get("solicitado_at") or est.get("recibido_at") or "")[:10],
        "fecha_escrituracion": str(serie.get("escritura_at") or "")[:10],
    }


_CAMPOS_ETAPA = {
    1: ("rut_titular", "nombre_cliente", "rut_codeudor", "nombre_codeudor", "email", "telefono"),
    2: ("direccion_propiedad", "comuna"),
    3: ("rol_avaluo", "valor_tasacion"),
    4: ("precio_vivienda", "credito_uf", "plazo_anos", "subsidio"),
    5: ("notaria", "fecha_estudio_titulo", "fecha_escrituracion"),
}


def aplicar_campos_mutuos(etapas, exp):
    """Rellena etapas vacías. No toca autorizadas ni valores ya digitados."""
    extra = campos_mutuos(exp)
    out = {}
    src = etapas or {}
    for n, campos in _CAMPOS_ETAPA.items():
        key = str(n)
        bloque = dict(src.get(key) or {})
        datos = dict(bloque.get("datos") or {})
        for c in campos:
            v = extra.get(c)
            if v in (None, "", [], {}):
                continue
            if datos.get(c) in (None, "", [], {}):
                datos[c] = v
        bloque["datos"] = datos
        out[key] = bloque
    for k, v in src.items():
        if k not in out:
            out[k] = v
    return out
