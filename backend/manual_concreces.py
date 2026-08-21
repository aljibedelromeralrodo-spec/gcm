"""📘 MÓDULO VICTORIA — ConCreces: flujo guiado paso a paso según el Manual de
Procedimiento Crédito Hipotecario (Central Mutuos, Nov 2024, Victoria Vilches)."""
import re
import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from database import db

mconc = APIRouter(prefix="/concreces")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _exigir(request):
    c = getattr(request.state, "user", {}) or {}
    if c.get("rol") not in ("admin", "maestro", "administracion"):
        raise HTTPException(status_code=403, detail="Solo Administración o el Administrador")
    return c


# ══════════ REGLAS DE ORO CONCRECES (del manual — si se rompen, invalidan la operación) ══════════
REGLAS_ORO = [
    ("ORO_CONCRECES_1", "Sin el checklist ANEXO I completo (antecedentes personales, laborales, financieros y de la compra) NO puede comenzar la evaluación del crédito."),
    ("ORO_CONCRECES_2", "Postulantes extranjeros deben contar con permanencia definitiva; sin ella la operación es inválida."),
    ("ORO_CONCRECES_3", "Mientras los Gastos Operacionales (GOP) no estén pagados NO se envía a escriturar (única excepción: socio Gerardo Barrera)."),
    ("ORO_CONCRECES_4", "Política de crédito: dividendo/renta hasta 30% y carga financiera hasta 50%. Fuera de rango la operación no es viable sin comité."),
    ("ORO_CONCRECES_5", "Financiamiento máximo 80% sobre el MENOR valor entre precio de venta y tasación de la propiedad."),
    ("ORO_CONCRECES_6", "Monto mínimo del crédito UF 700 y plazo máximo 30 años (40 solo por excepción autorizada)."),
    ("ORO_CONCRECES_7", "Todo crédito debe contar con Seguro de Incendio con adicional Sismo y Seguro de Desgravamen; con subsidio habitacional además Cesantía o ITP 2/3."),
    ("ORO_CONCRECES_8", "Mutuario mayor de 65 años o que no pueda contratar desgravamen exige aval u otra caución complementaria."),
    ("ORO_CONCRECES_9", "TODA la documentación debe subirse a la administradora (ConCreces) para su revisión, y los reparos deben ser subsanados."),
    ("ORO_CONCRECES_10", "La resolución solo puede ser Aprobado (Carta de Aprobación), Reparado (Carta Aprobación Preliminar) o Rechazado (mail de respaldo); el envío a ConCreces exige resolución Aprobado."),
]


async def seed_reglas_oro():
    for clave, texto in REGLAS_ORO:
        await db.dashai_eventos.update_one({"norma_clave": clave}, {"$set": {
            "motivo": "normativa", "etiqueta": "Regla de Oro ConCreces", "norma_clave": clave,
            "patron": f"REGLA DE ORO CONCRECES — {texto}", "inviolable": True,
            "nivel_calibracion": 100, "fecha": _now(),
        }, "$setOnInsert": {"id": str(uuid.uuid4())}}, upsert=True)
    logging.info("📘 Reglas de Oro ConCreces sembradas en la Constitución (dashai_eventos)")


# ══════════ CHECKLIST ANEXO I ══════════
_CHK_BASE = [
    ("ci", "C.I. ambos lados (deudor y codeudor)", r"cedula|c\.?i\b|carnet|identidad"),
    ("permanencia", "Extranjeros: permanencia definitiva (si aplica)", r"permanencia"),
    ("dps", "DPS completados y firmados", r"\bdps\b|declaracion.*salud"),
]
_CHK_FIN = [("deudas", "Acreditación de deudas en instituciones bancarias", r"cmf|deuda|infocom|informe.*comercial")]
CHECKLIST = {
    "dependiente": _CHK_BASE + [
        ("liq3", "Liquidaciones últimos 3 meses", r"liquidacion"),
        ("liq6", "Liquidaciones últimos 6 meses (o menos si antigüedad < 6 meses)", r"liquidacion"),
        ("afp24", "Certificado de AFP últimos 24 meses", r"\bafp\b|cotizacion"),
    ] + _CHK_FIN,
    "independiente": _CHK_BASE + [
        ("boletas", "Boletas del año en curso", r"boleta"),
        ("renta", "Última declaración de renta (no exigible con más de 6 boletas consecutivas)", r"\brenta\b|f22|declaracion.*impuesto"),
    ] + _CHK_FIN,
}
COMPRA = [
    ("fecha_entrega", "Fecha de entrega (recepción del proyecto)"), ("monto_vivienda", "Monto vivienda (UF)"),
    ("monto_credito", "Monto crédito (UF)"), ("monto_subsidio", "Monto subsidio (UF)"),
    ("monto_pie", "Monto pie (UF)"), ("inmobiliaria", "Inmobiliaria"),
    ("proyecto", "Proyecto"), ("comuna", "Comuna"),
]
FORMULARIOS = [
    "Estado de Situación / Solicitud de Crédito", "Solicitud incorporación Seguro Incendio y Sismo",
    "DPS", "Autorización para contratar seguros", "Solicitud incorporación seguro Cesantía",
    "Formulario condiciones generales de cobranza externa", "Formulario autorización solicitud antecedentes endeudamiento",
    "Formulario Persona Expuesta Políticamente", "Declaración DFL2",
]


async def _get_folder(fid):
    fd = await db.folders.find_one({"id": fid}, {"_id": 0})
    if not fd:
        raise HTTPException(status_code=404, detail="Carpeta no encontrada")
    return fd


async def _get_flujo(fid):
    fl = await db.concreces_flujo.find_one({"folder_id": fid}, {"_id": 0})
    if not fl:
        fl = {"id": str(uuid.uuid4()), "folder_id": fid, "tipo_trabajador": "dependiente",
              "checklist": {}, "compra": {}, "formularios": {}, "politica": {},
              "gop": {"pagado": False, "socio": ""}, "resolucion": None, "enviado": False,
              "reparos": [], "creado": _now()}
        await db.concreces_flujo.insert_one({**fl})
        fl.pop("_id", None)
    return fl


def _autofill_checklist(archivos, tipo):
    nombres = " | ".join(a.lower() for a in (archivos or []))
    return {clave: bool(re.search(rx, nombres)) for clave, _et, rx in CHECKLIST[tipo]}


async def _autofill_compra(fd):
    sug = {}
    comp = await db.compromisos.find_one({"folder_id": fd["id"]}) or {}
    for src in (fd, comp, fd.get("perfil_consolidado") or {}, fd.get("inmobiliaria_contacto") or {}):
        for k, _et in COMPRA:
            v = src.get(k) or src.get(k.replace("monto_", ""))
            if v and not sug.get(k):
                sug[k] = v
    if not sug.get("inmobiliaria"):
        ic = fd.get("inmobiliaria_contacto") or {}
        sug["inmobiliaria"] = ic.get("inmobiliaria") or fd.get("inmobiliaria") or ""
    return {k: v for k, v in sug.items() if v}


def _politica_eval(p):
    def num(k):
        try:
            return float(str(p.get(k, "")).replace(",", "."))
        except (TypeError, ValueError):
            return None
    renta, div = num("renta_uf"), num("dividendo_uf")
    cf, venta, tasa = num("carga_financiera_pct"), num("valor_venta_uf"), num("tasacion_uf")
    cred, plazo, edad = num("monto_credito_uf"), num("plazo_anios"), num("edad")
    checks = []

    def add(regla, ok, detalle):
        checks.append({"regla": regla, "ok": ok, "detalle": detalle})
    if renta and div is not None:
        r = round(div / renta * 100, 1)
        add("Dividendo/renta ≤ 30%", r <= 30, f"{r}%")
    else:
        add("Dividendo/renta ≤ 30%", None, "faltan renta o dividendo")
    add("Carga financiera ≤ 50%", None if cf is None else cf <= 50, f"{cf}%" if cf is not None else "falta CF")
    if cred and venta and tasa:
        tope = 0.8 * min(venta, tasa)
        add("Financiamiento ≤ 80% del menor valor venta/tasación", cred <= tope, f"crédito UF{cred:g} vs tope UF{tope:g}")
    else:
        add("Financiamiento ≤ 80% del menor valor venta/tasación", None, "faltan crédito, venta o tasación")
    add("Monto mínimo UF 700", None if cred is None else cred >= 700, f"UF{cred:g}" if cred else "falta monto")
    if plazo is not None:
        ok = plazo <= 30 or (plazo <= 40 and str(p.get("excepcion_40", "")).lower() in ("true", "1", "si", "sí"))
        add("Plazo máx 30 años (40 por excepción)", ok, f"{plazo:g} años")
    else:
        add("Plazo máx 30 años (40 por excepción)", None, "falta plazo")
    if str(p.get("extranjero", "")).lower() in ("true", "1", "si", "sí"):
        add("Extranjero con permanencia definitiva", str(p.get("permanencia_definitiva", "")).lower() in ("true", "1", "si", "sí"), "obligatoria (Regla de Oro 2)")
    if edad is not None and edad > 65:
        add("Mayor de 65: aval o caución complementaria", str(p.get("aval", "")).lower() in ("true", "1", "si", "sí"), "exigida por manual")
    return checks


def _chk_items(fl, auto_chk):
    tipo = fl.get("tipo_trabajador", "dependiente")
    extranjero = str((fl.get("politica") or {}).get("extranjero", "")).lower() in ("true", "1", "si", "sí")
    items = []
    for clave, et, _rx in CHECKLIST[tipo]:
        manual = bool((fl.get("checklist") or {}).get(clave))
        auto = auto_chk.get(clave, False)
        no_aplica = clave == "permanencia" and not extranjero
        items.append({"clave": clave, "etiqueta": et + (" — no aplica (no es extranjero)" if no_aplica else ""),
                      "auto": auto, "manual": manual, "ok": manual or auto or no_aplica})
    return items


def _estado(fl, auto_chk, checks):
    items = _chk_items(fl, auto_chk)
    compra_falt = [et for k, et in COMPRA if not str((fl.get("compra") or {}).get(k, "")).strip()]
    chk_falt = [i["etiqueta"] for i in items if not i["ok"]]
    pol_mal = [c for c in checks if c["ok"] is False]
    pol_pend = [c for c in checks if c["ok"] is None]
    forms_falt = [f for f in FORMULARIOS if not (fl.get("formularios") or {}).get(f)]
    gop = fl.get("gop") or {}
    gop_ok = bool(gop.get("pagado")) or "gerardo barrera" in str(gop.get("socio", "")).lower()
    pasos = [
        {"n": 1, "titulo": "Solicitud — Checklist ANEXO I", "completo": not chk_falt, "faltan": chk_falt},
        {"n": 2, "titulo": "Antecedentes de la compra", "completo": not compra_falt, "faltan": compra_falt},
        {"n": 3, "titulo": "Evaluación — Política de crédito y resolución",
         "completo": not pol_mal and not pol_pend and fl.get("resolucion") == "aprobado",
         "faltan": [c["regla"] for c in pol_mal + pol_pend] + ([] if fl.get("resolucion") else ["Registrar resolución"])},
        {"n": 4, "titulo": "Formularios del cliente (ANEXO IV)", "completo": not forms_falt, "faltan": forms_falt},
        {"n": 5, "titulo": "Gastos Operacionales (GOP)", "completo": gop_ok,
         "faltan": [] if gop_ok else ["GOP pendientes de pago — no se envía a escriturar"]},
        {"n": 6, "titulo": "Revisión y envío a ConCreces", "completo": bool(fl.get("enviado")),
         "faltan": [] if fl.get("enviado") else ["Generar documento de revisión, validar y enviar"]},
    ]
    siguiente = next((p for p in pasos if not p["completo"]), None)
    return pasos, siguiente, gop_ok


async def _estado_completo(fid):
    fd = await _get_folder(fid)
    fl = await _get_flujo(fid)
    auto_chk = _autofill_checklist(fd.get("archivos"), fl.get("tipo_trabajador", "dependiente"))
    checks = _politica_eval(fl.get("politica") or {})
    pasos, siguiente, gop_ok = _estado(fl, auto_chk, checks)
    return fd, fl, auto_chk, checks, pasos, siguiente, gop_ok


@mconc.get("/carpetas")
async def carpetas(request: Request):
    _exigir(request)
    regs = await db.folders.find({"descartada": {"$ne": True}}, {"_id": 0, "id": 1, "nombre": 1, "rut": 1}).sort("nombre", 1).to_list(400)
    return {"carpetas": regs}


@mconc.get("/reglas-oro")
async def reglas_oro(request: Request):
    _exigir(request)
    regs = await db.dashai_eventos.find({"etiqueta": "Regla de Oro ConCreces"}, {"_id": 0, "norma_clave": 1, "patron": 1}).to_list(20)
    return {"reglas": regs, "total": len(regs)}


@mconc.get("/flujo/{fid}")
async def flujo_get(fid: str, request: Request):
    _exigir(request)
    fd, fl, auto_chk, checks, pasos, siguiente, gop_ok = await _estado_completo(fid)
    tipo = fl.get("tipo_trabajador", "dependiente")
    items = _chk_items(fl, auto_chk)
    sugerencias = await _autofill_compra(fd)
    return {"carpeta": {"id": fd["id"], "nombre": fd.get("nombre"), "rut": fd.get("rut"),
                        "archivos": fd.get("archivos") or []},
            "flujo": fl, "checklist_items": items, "compra_campos": COMPRA,
            "compra_sugerencias": sugerencias, "formularios": FORMULARIOS,
            "politica_checks": checks, "pasos": pasos, "siguiente": siguiente, "gop_ok": gop_ok}


@mconc.put("/flujo/{fid}")
async def flujo_put(fid: str, payload: dict, request: Request):
    u = _exigir(request)
    await _get_flujo(fid)
    sets = {"actualizado": _now(), "actualizado_por": u.get("sub", "")}
    for k in ("tipo_trabajador", "checklist", "compra", "formularios", "politica", "gop"):
        if k in payload:
            sets[k] = payload[k]
    await db.concreces_flujo.update_one({"folder_id": fid}, {"$set": sets})
    return await flujo_get(fid, request)


@mconc.post("/flujo/{fid}/resolucion")
async def flujo_resolucion(fid: str, payload: dict, request: Request):
    u = _exigir(request)
    fd, fl, auto_chk, checks, pasos, _sig, _g = await _estado_completo(fid)
    if pasos[0]["faltan"]:
        raise HTTPException(status_code=403, detail=f"REGLA DE ORO CONCRECES 1: checklist ANEXO I incompleto — faltan: {', '.join(pasos[0]['faltan'][:4])}")
    res = (payload.get("resolucion") or "").lower()
    if res not in ("aprobado", "reparado", "rechazado"):
        raise HTTPException(status_code=400, detail="Resolución inválida (aprobado/reparado/rechazado)")
    carta_titulo = {"aprobado": "Carta de Aprobación", "reparado": "Carta de Aprobación Preliminar",
                    "rechazado": "Mail de respaldo — Rechazo"}[res]
    detalle = (payload.get("detalle") or "").strip()
    carta = (f"<div style='font-family:Georgia,serif;padding:24px;color:#111'>"
             f"<h2 style='color:#8a6d1a'>CENTRAL MUTUOS — {carta_titulo}</h2>"
             f"<p>Cliente: <b>{fd.get('nombre','')}</b> · RUT {fd.get('rut','—')}</p>"
             f"<p>Resolución de la evaluación: <b style='text-transform:uppercase'>{res}</b></p>"
             + (f"<p>{'Antecedentes adicionales solicitados' if res == 'reparado' else 'Detalle'}: {detalle}</p>" if detalle else "")
             + ("<p>Se adjuntará simulación del crédito y estimación de Gastos Operacionales (GOP) para conocimiento y aprobación del cliente.</p>" if res == "aprobado" else "")
             + f"<p style='color:#666;font-size:12px'>Emitido según Manual de Procedimiento Crédito Hipotecario · {_now()[:16].replace('T', ' ')} UTC · por {u.get('sub','')}</p></div>")
    await db.concreces_flujo.update_one({"folder_id": fid}, {"$set": {
        "resolucion": res, "resolucion_detalle": detalle, "carta_html": carta,
        "carta_titulo": carta_titulo, "resolucion_en": _now(), "resolucion_por": u.get("sub", "")}})
    return {"ok": True, "resolucion": res, "carta_titulo": carta_titulo, "carta_html": carta}


def _html_revision(fd, fl, items, checks, pasos, validaciones):
    filas_chk = "".join(f"<tr><td>{i['etiqueta']}</td><td>{'✅' + (' (AUTO)' if i['auto'] and not i['manual'] else '') if i['ok'] else '❌ FALTA'}</td></tr>" for i in items)
    filas_com = "".join(f"<tr><td>{et}</td><td>{(fl.get('compra') or {}).get(k, '') or '❌ FALTA'}</td></tr>" for k, et in COMPRA)
    filas_pol = "".join(f"<tr><td>{c['regla']}</td><td>{'✅' if c['ok'] else ('⏳' if c['ok'] is None else '❌')} {c['detalle']}</td></tr>" for c in checks)
    filas_frm = "".join(f"<tr><td>{f}</td><td>{'✅' if (fl.get('formularios') or {}).get(f) else '❌ FALTA'}</td></tr>" for f in FORMULARIOS)
    filas_oro = "".join(f"<tr><td>{v['regla']}</td><td>{'✅ CUMPLE' if v['ok'] else '❌ NO CUMPLE — INVALIDA LA OPERACIÓN'}</td></tr>" for v in validaciones)
    gop = fl.get("gop") or {}
    tabla = "border-collapse:collapse;width:100%;font-size:13px"
    return (f"<html><body style='font-family:Georgia,serif;color:#111;max-width:820px;margin:auto;padding:18px'>"
            f"<h1 style='color:#8a6d1a;border-bottom:3px solid #8a6d1a'>CENTRAL MUTUOS — Documento de Revisión ConCreces</h1>"
            f"<p><b>Cliente:</b> {fd.get('nombre','')} · <b>RUT:</b> {fd.get('rut','—')} · <b>Fecha:</b> {_now()[:16].replace('T',' ')} UTC</p>"
            f"<p><b>Tipo de trabajador:</b> {fl.get('tipo_trabajador','')} · <b>Resolución:</b> {(fl.get('resolucion') or 'SIN RESOLUCIÓN').upper()}"
            f" · <b>GOP:</b> {'PAGADOS' if gop.get('pagado') else 'PENDIENTES'} · <b>Socio:</b> {gop.get('socio') or '—'}</p>"
            f"<h3>1. Checklist ANEXO I</h3><table border=1 cellpadding=5 style='{tabla}'>{filas_chk}</table>"
            f"<h3>2. Antecedentes de la compra</h3><table border=1 cellpadding=5 style='{tabla}'>{filas_com}</table>"
            f"<h3>3. Política de crédito</h3><table border=1 cellpadding=5 style='{tabla}'>{filas_pol}</table>"
            f"<h3>4. Formularios del cliente (ANEXO IV)</h3><table border=1 cellpadding=5 style='{tabla}'>{filas_frm}</table>"
            f"<h3>5. Documentos de la carpeta a enviar ({len(fd.get('archivos') or [])})</h3>"
            f"<p style='font-size:12px'>{'<br>'.join(fd.get('archivos') or []) or 'Sin archivos'}</p>"
            f"<h3>6. Validación Reglas de Oro ConCreces</h3><table border=1 cellpadding=5 style='{tabla}'>{filas_oro}</table>"
            f"<p style='background:#fdf6e3;border:1px solid #8a6d1a;padding:10px;font-weight:bold'>Este documento debe ser revisado y validado"
            f" por Victoria Vilches ANTES de enviar los archivos a ConCreces. La firma de validación queda registrada en el sistema.</p>"
            f"</body></html>")


def _validaciones_oro(fl, items, checks, gop_ok):
    pol_mal = [c for c in checks if c["ok"] is False]
    pol_pend = [c for c in checks if c["ok"] is None]
    return [
        {"regla": "Checklist ANEXO I completo antes de evaluar (Oro 1)", "ok": all(i["ok"] for i in items)},
        {"regla": "Antecedentes de la compra completos (Oro 1)", "ok": all(str((fl.get('compra') or {}).get(k, '')).strip() for k, _ in COMPRA)},
        {"regla": "Política de crédito cumplida (Oro 4/5/6)", "ok": not pol_mal and not pol_pend},
        {"regla": "Resolución APROBADO para enviar a ConCreces (Oro 10)", "ok": fl.get("resolucion") == "aprobado"},
        {"regla": "GOP pagados o excepción Gerardo Barrera para escriturar (Oro 3)", "ok": gop_ok},
    ]


@mconc.get("/flujo/{fid}/revision")
async def flujo_revision(fid: str, request: Request):
    _exigir(request)
    fd, fl, auto_chk, checks, pasos, _sig, gop_ok = await _estado_completo(fid)
    tipo = fl.get("tipo_trabajador", "dependiente")
    items = _chk_items(fl, auto_chk)
    validaciones = _validaciones_oro(fl, items, checks, gop_ok)
    html = _html_revision(fd, fl, items, checks, pasos, validaciones)
    await db.concreces_flujo.update_one({"folder_id": fid}, {"$set": {"revision_generada": _now()}})
    return {"html": html, "validaciones": validaciones,
            "listo_para_enviar": all(v["ok"] for v in validaciones if "escriturar" not in v["regla"])}


@mconc.post("/flujo/{fid}/enviar")
async def flujo_enviar(fid: str, payload: dict, request: Request):
    u = _exigir(request)
    if not payload.get("confirmado"):
        raise HTTPException(status_code=400, detail="Victoria debe confirmar la validación del documento de revisión antes de enviar")
    fd, fl, auto_chk, checks, _p, _s, gop_ok = await _estado_completo(fid)
    tipo = fl.get("tipo_trabajador", "dependiente")
    items = _chk_items(fl, auto_chk)
    fallas = [v["regla"] for v in _validaciones_oro(fl, items, checks, gop_ok)
              if not v["ok"] and "escriturar" not in v["regla"]]
    if fallas:
        raise HTTPException(status_code=403, detail=f"REGLAS DE ORO CONCRECES incumplidas: {' · '.join(fallas)}")
    archivos = fd.get("archivos") or []
    cargas = [{"id": str(uuid.uuid4()), "folder_id": fid, "archivo": a, "estado": "subido",
               "subido_en": _now(), "subido_por": u.get("sub", "")} for a in archivos]
    if cargas:
        await db.concreces_cargas.delete_many({"folder_id": fid})
        await db.concreces_cargas.insert_many([dict(c) for c in cargas])
    await db.concreces_estado.update_one({"folder_id": fid}, {"$set": {
        "folder_id": fid, "cliente": fd.get("nombre"), "rut": fd.get("rut"),
        "estado": "enviado", "enviado_en": _now(), "enviado_por": u.get("sub", ""),
        "documentos": archivos, "n_documentos": len(archivos),
        "snapshot": {"tipo_trabajador": tipo, "compra": fl.get("compra"), "resolucion": fl.get("resolucion"),
                     "gop": fl.get("gop"), "politica": fl.get("politica")}}}, upsert=True)
    await db.concreces_flujo.update_one({"folder_id": fid}, {"$set": {
        "enviado": True, "enviado_en": _now(), "enviado_por": u.get("sub", ""),
        "validado_por_victoria": True}})
    await db.folders.update_one({"id": fid}, {"$set": {"concreces_enviado": True, "concreces_enviado_en": _now()}})
    return {"ok": True, "enviados": len(archivos),
            "mensaje": f"Carpeta de {fd.get('nombre')} enviada a la bóveda ConCreces con {len(archivos)} documento(s). Queda a la espera de revisión de la administradora."}


@mconc.post("/flujo/{fid}/reparo")
async def flujo_reparo(fid: str, payload: dict, request: Request):
    u = _exigir(request)
    detalle = (payload.get("detalle") or "").strip()
    if not detalle:
        raise HTTPException(status_code=400, detail="Detalle del reparo obligatorio")
    rep = {"id": str(uuid.uuid4()), "detalle": detalle, "estado": "pendiente",
           "creado": _now(), "por": u.get("sub", "")}
    await db.concreces_flujo.update_one({"folder_id": fid}, {"$push": {"reparos": rep}})
    await db.concreces_estado.update_one({"folder_id": fid}, {"$set": {"estado": "reparado"}})
    return {"ok": True, "reparo": rep}


@mconc.post("/flujo/{fid}/subsanar/{rid}")
async def flujo_subsanar(fid: str, rid: str, request: Request):
    u = _exigir(request)
    await db.concreces_flujo.update_one({"folder_id": fid, "reparos.id": rid}, {"$set": {
        "reparos.$.estado": "subsanado", "reparos.$.subsanado_en": _now(), "reparos.$.subsanado_por": u.get("sub", "")}})
    fl = await db.concreces_flujo.find_one({"folder_id": fid}, {"_id": 0, "reparos": 1})
    if not any(r.get("estado") == "pendiente" for r in (fl or {}).get("reparos", [])):
        await db.concreces_estado.update_one({"folder_id": fid}, {"$set": {"estado": "enviado"}})
    return {"ok": True}
