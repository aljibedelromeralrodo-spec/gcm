"""SOLICITUDES LA CRUZ — ingesta, extracción IA y análisis de evaluaciones de crédito
recibidas desde la inmobiliaria La Cruz (daniela.rodriguez@lacruzinmobiliaria.cl)."""
import asyncio
import io
import json
import logging
import os
import re
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, HTTPException, Request
from database import db
import folders_service as fsvc
import credit_engine as ce
from criterios_data import DEFAULT_TASAS, DEFAULT_UF, now_iso

lacruz = APIRouter(prefix="/lacruz")

SENDER_DEFAULT = "daniela.rodriguez@lacruzinmobiliaria.cl"
VIGENCIA_DIAS = 15
MESES_LIQ_REQ = ["2026-02", "2026-03", "2026-04", "2026-05", "2026-06", "2026-07"]
MES_NOMBRE = {"02": "febrero", "03": "marzo", "04": "abril", "05": "mayo", "06": "junio", "07": "julio"}
DOCS_REQ = ["cedula", "liquidacion", "afp", "cmf"]
LABEL = {"cedula": "Cédula de identidad", "liquidacion": "Liquidaciones de sueldo",
         "afp": "Certificado AFP", "cmf": "Informe de deudas CMF"}
RUT_RX = re.compile(r"(\d{1,2}\.?\d{3}\.?\d{3})\s*[-–]\s*([\dkK])")

_SISTEMA = """Eres un analista hipotecario chileno experto. Recibes el texto de correos y de sus PDFs
adjuntos (cotizaciones, liquidaciones de sueldo, certificados AFP, informes CMF, cédulas, contratos).
Devuelves SOLO un JSON válido, sin comentarios, con esta estructura exacta:
{"titular": {"nombre": "", "rut": "", "telefono": "", "email": "", "tipo_contrato": "", "fecha_ingreso_laboral": "YYYY-MM-DD", "empleador": ""},
 "codeudor": null | {"nombre": "", "rut": "", "telefono": "", "email": "", "tipo_contrato": "", "fecha_ingreso_laboral": "", "empleador": ""},
 "proyecto": "", "monto_credito_uf": 0, "valor_propiedad_uf": 0, "subsidio_uf": 0, "ahorro_uf": 0,
 "documentos": [{"archivo": "", "propietario": "titular|codeudor", "tipo": "cedula|liquidacion|afp|cmf|cotizacion|contrato|otro", "fecha_emision": "YYYY-MM-DD" | null, "meses_liquidaciones": ["YYYY-MM"], "legible": true}],
 "liquidos_titular": {"YYYY-MM": 0}, "liquidos_codeudor": {"YYYY-MM": 0},
 "deuda_cmf_titular_clp": 0, "deuda_cmf_codeudor_clp": 0, "observaciones": ""}
Reglas: un mismo archivo PDF puede contener VARIOS documentos (lista una entrada por documento interno).
"liquidos_*" = ALCANCE LÍQUIDO / LÍQUIDO A PAGAR / LÍQUIDO A RECIBIR mensual en pesos.
Si un PDF casi no tiene texto es un escaneo: legible=false (típico en cédulas). Montos en números, sin puntos."""


def _rut_subject(s):
    m = RUT_RX.search(s or "")
    return (re.sub(r"\D", "", m.group(1)) + "-" + m.group(2).lower()) if m else ""


def _fetch_correos(sender):
    import email as email_lib
    import email_service as es
    out = []
    for acc in es.ACCOUNTS:
        try:
            m = es._connect(acc)
            m.select("INBOX", readonly=True)
            typ, data = m.search(None, "FROM", f'"{sender}"')
            ids = data[0].split() if data and data[0] else []
            for num in ids[-40:]:
                typ, md = m.fetch(num, "(UID BODY.PEEK[])")
                if not md or not isinstance(md[0], tuple):
                    continue
                desc = md[0][0]
                desc = desc.decode(errors="ignore") if isinstance(desc, bytes) else str(desc)
                mu = re.search(r"UID (\d+)", desc)
                info = es._parse_full_message(email_lib.message_from_bytes(md[0][1]), with_bytes=True)
                info["uid"] = f"{acc['rol']}|{mu.group(1) if mu else num.decode()}"
                out.append(info)
            m.logout()
        except Exception as e:
            logging.warning(f"lacruz imap {acc.get('rol')}: {e}")
    return out


def _texto_pdf(raw):
    from pdfminer.high_level import extract_text
    try:
        return extract_text(io.BytesIO(raw)) or ""
    except Exception:
        return ""


async def _extraer_ia(cuerpos, textos):
    key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not key:
        raise HTTPException(status_code=503, detail="IA no disponible (sin EMERGENT_LLM_KEY)")
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    import ai_extract as _aix
    partes = ["CORREOS:\n" + "\n---\n".join(cuerpos)[:4000]]
    for fn, t in textos.items():
        tt = " ".join((t or "").split())
        partes.append(f"\n===== PDF: {fn} ({len(tt)} chars de texto) =====\n{tt[:16000] or '(SIN TEXTO — escaneo/imagen)'}")
    chat = LlmChat(api_key=key, session_id=f"lacruz-{uuid.uuid4()}",
                   system_message=_SISTEMA).with_model("anthropic", "claude-sonnet-4-6")
    resp = await _aix._enviar(chat, UserMessage(text="\n".join(partes)))
    raw = resp if isinstance(resp, str) else str(resp)
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError("IA sin JSON")
    return json.loads(m.group(0))


def _hoy_chile():
    return datetime.now(ZoneInfo("America/Santiago")).date()


def _num(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _analizar(ext, uf):
    hoy = _hoy_chile()
    docs = ext.get("documentos") or []
    personas = ["titular"] + (["codeudor"] if ext.get("codeudor") else [])
    estado_docs, faltantes, vencidos = {}, [], []
    for p in personas:
        tipos, meses = set(), set()
        for d in docs:
            if (d.get("propietario") or "titular") != p:
                continue
            tipos.add(d.get("tipo"))
            if d.get("tipo") == "liquidacion":
                meses |= set(d.get("meses_liquidaciones") or [])
            if d.get("tipo") in ("afp", "cmf") and d.get("fecha_emision"):
                try:
                    fe = datetime.strptime(d["fecha_emision"], "%Y-%m-%d").date()
                    if (hoy - fe).days > VIGENCIA_DIAS:
                        vencidos.append(f"{LABEL[d['tipo']]} de {p} emitido el {fe.strftime('%d/%m/%Y')} "
                                        f"({(hoy - fe).days} días — máx. {VIGENCIA_DIAS})")
                except Exception:
                    pass
            if d.get("tipo") == "cedula" and d.get("legible") is False:
                vencidos.append(f"Cédula de {p} ilegible (escaneo de baja calidad) — reenviar")
        for c in DOCS_REQ:
            if c not in tipos:
                faltantes.append(f"{LABEL[c]} ({p})")
        liq_falt = [MES_NOMBRE[mm[-2:]] for mm in MESES_LIQ_REQ if mm not in meses]
        if "liquidacion" in tipos and liq_falt:
            faltantes.append(f"Liquidaciones de {', '.join(liq_falt)} 2026 ({p})")
        estado_docs[p] = {"tipos": sorted(t for t in tipos if t), "meses_liq": sorted(meses)}

    liq_t = [v for v in (ext.get("liquidos_titular") or {}).values() if _num(v) > 0]
    liq_c = [v for v in (ext.get("liquidos_codeudor") or {}).values() if _num(v) > 0]
    renta_t = sum(map(_num, liq_t)) / len(liq_t) if liq_t else 0
    renta_c = sum(map(_num, liq_c)) / len(liq_c) if liq_c else 0
    renta = renta_t + renta_c
    monto = _num(ext.get("monto_credito_uf"))
    valor_prop = _num(ext.get("valor_propiedad_uf")) or 2330
    tasa = DEFAULT_TASAS["tasa_subsidio_menor_2000"] if monto < 2000 else DEFAULT_TASAS["tasa_subsidio_mayor_2000"]
    plazo = 30
    div_clp = ce.dividendo(monto, tasa, plazo) * uf
    deuda = _num(ext.get("deuda_cmf_titular_clp")) + _num(ext.get("deuda_cmf_codeudor_clp"))
    cuota_cmf = deuda * 0.02
    dr = div_clp / renta if renta else None
    carga = (div_clp + cuota_cmf) / renta if renta else None
    ltv = monto / valor_prop if valor_prop else None
    razones = []
    if dr is not None and dr > 0.40:
        razones.append(f"Dividendo/renta {dr*100:.1f}% supera el máximo 40% (MHE con subsidio)")
    if carga is not None and carga > 0.55:
        razones.append(f"Carga financiera {carga*100:.1f}% supera el máximo 55%")
    if ltv is not None and ltv > 0.801:
        razones.append(f"LTV {ltv*100:.0f}% supera el máximo 80%")
    renta_min = (25 if ext.get("codeudor") else 15) * uf
    if renta and renta < renta_min:
        razones.append(f"Renta ${renta:,.0f} bajo el mínimo MHE (UF {25 if ext.get('codeudor') else 15})")
    div_max_clp = max(0, min(renta * 0.40, renta * 0.55 - cuota_cmf)) if renta else 0
    max_uf = ce.capacidad_desde_dividendo(div_max_clp / uf, tasa, plazo) if div_max_clp else 0
    max_uf = round(min(max_uf, valor_prop * 0.80, 3200), 1)
    if razones:
        semaforo, posibilidad = "BAJA", "Excede los ratios de la política MHE — requiere ajuste o más renta"
    elif faltantes or vencidos:
        semaforo = "MEDIA"
        posibilidad = "Ratios OK — falta completar/actualizar documentación para evaluar en Mesa"
    else:
        semaforo, posibilidad = "ALTA", "Cumple ratios MHE y documentación completa/vigente"
    docs_ok = 1 - min(1, (len(faltantes) + len(vencidos)) / 8)
    score = round((0 if razones else 50) + docs_ok * 50)
    return {"renta_titular_clp": round(renta_t), "renta_codeudor_clp": round(renta_c),
            "renta_total_clp": round(renta), "deuda_cmf_clp": round(deuda),
            "tasa_pct": tasa * 100, "plazo_anos": plazo,
            "dividendo_estimado_clp": round(div_clp),
            "div_renta_pct": round(dr * 100, 1) if dr is not None else None,
            "carga_financiera_pct": round(carga * 100, 1) if carga is not None else None,
            "ltv_pct": round(ltv * 100, 1) if ltv is not None else None,
            "max_credito_posible_uf": max_uf, "razones": razones,
            "semaforo": semaforo, "posibilidad": posibilidad,
            "faltantes": faltantes, "vencidos": vencidos, "estado_docs": estado_docs,
            "score": score}


async def _guardar_carpeta(ext, adjuntos):
    nombre = (ext.get("titular", {}).get("nombre") or "").strip().upper()
    rut = ext.get("titular", {}).get("rut") or ""
    if not nombre:
        return None
    fol = await db.folders.find_one({"$or": [{"rut": rut}, {"nombre": nombre}]}) if rut else \
        await db.folders.find_one({"nombre": nombre})
    if not fol:
        fol = {"id": str(uuid.uuid4()), "nombre": nombre, "rut": rut, "archivos": [],
               "telefono": ext.get("titular", {}).get("telefono") or "",
               "email": ext.get("titular", {}).get("email") or "",
               "codeudor_nombre": (ext.get("codeudor") or {}).get("nombre") or "",
               "codeudor_rut": (ext.get("codeudor") or {}).get("rut") or "",
               "credit_request": {"client_type": "dependiente"},
               "created_at": now_iso(), "origen": "lacruz_auto"}
        await db.folders.insert_one(dict(fol))
        fsvc.folder_dir(nombre).mkdir(parents=True, exist_ok=True)
    dueno, solo_cotizacion = {}, {}
    for d in (ext.get("documentos") or []):
        arch = d.get("archivo")
        if (d.get("propietario") or "titular") == "codeudor":
            dueno[arch] = "codeudor"
        solo_cotizacion.setdefault(arch, set()).add(d.get("tipo"))
    for a in adjuntos:
        fn = a["filename"]
        if dueno.get(fn) == "codeudor" and not fn.upper().startswith("CODEUDOR_"):
            fn = f"CODEUDOR_{fn}"
        try:
            if solo_cotizacion.get(a["filename"]) == {"cotizacion"}:
                # cotización de la propiedad → raíz de la carpeta (no es certificado AFP)
                dest = fsvc.folder_dir(nombre) / fsvc.safe_name(fn)
                await asyncio.to_thread(dest.write_bytes, a["bytes"])
            else:
                await asyncio.to_thread(fsvc.guardar_archivo, nombre, fn, a["bytes"])
        except Exception as e:
            logging.warning(f"lacruz guardar {fn}: {e}")
    try:
        import bunker
        bunker.sync_en_background()
    except Exception:
        pass
    return fol["id"]


async def procesar(sender=SENDER_DEFAULT):
    correos = await asyncio.to_thread(_fetch_correos, sender)
    casos = {}
    for c in correos:
        rut = _rut_subject(c.get("subject"))
        if rut:
            casos.setdefault(rut, []).append(c)
    uf = float(((await db.config.find_one({"_key": "uf"})) or {}).get("valor_uf") or DEFAULT_UF)
    resultados = []
    for rut, mails in casos.items():
        mails.sort(key=lambda x: x.get("date", ""))
        adjuntos, textos, cuerpos = [], {}, []
        for mm in mails:
            cuerpos.append(f"[{mm.get('date', '')[:16]}] {mm.get('subject', '')}\n{mm.get('body', '')}")
            for a in mm.get("attachments") or []:
                if not (a.get("filename") or "").lower().endswith(".pdf"):
                    continue
                if any(x["filename"] == a["filename"] for x in adjuntos):
                    continue
                adjuntos.append({"filename": a["filename"], "bytes": a.get("content_bytes") or b""})
        for a in adjuntos:
            textos[a["filename"]] = await asyncio.to_thread(_texto_pdf, a["bytes"])
        try:
            ext = await _extraer_ia(cuerpos, textos)
        except Exception as e:
            logging.warning(f"lacruz IA {rut}: {e}")
            continue
        analisis = _analizar(ext, uf)
        folder_id = await _guardar_carpeta(ext, adjuntos)
        reg = {"id": str(uuid.uuid4()), "rut": rut,
               "nombre": ext.get("titular", {}).get("nombre") or "",
               "telefono": ext.get("titular", {}).get("telefono") or "",
               "email": ext.get("titular", {}).get("email") or "",
               "proyecto": ext.get("proyecto") or "",
               "monto_credito_uf": _num(ext.get("monto_credito_uf")),
               "valor_propiedad_uf": _num(ext.get("valor_propiedad_uf")),
               "subsidio_uf": _num(ext.get("subsidio_uf")), "ahorro_uf": _num(ext.get("ahorro_uf")),
               "codeudor": ext.get("codeudor"),
               "tipo_contrato": ext.get("titular", {}).get("tipo_contrato") or "",
               "fecha_ingreso_laboral": ext.get("titular", {}).get("fecha_ingreso_laboral") or "",
               "observaciones_ia": ext.get("observaciones") or "",
               "analisis": analisis, "folder_id": folder_id,
               "correos": [mm["uid"] for mm in mails], "n_adjuntos": len(adjuntos),
               "valor_uf_usado": uf, "actualizado": now_iso()}
        await db.lacruz_solicitudes.update_one({"rut": rut}, {"$set": reg}, upsert=True)
        resultados.append(reg)
    orden = sorted(resultados, key=lambda r: -r["analisis"]["score"])
    for i, r in enumerate(orden, 1):
        await db.lacruz_solicitudes.update_one({"rut": r["rut"]}, {"$set": {"prioridad": i}})
    return {"ok": True, "casos": len(resultados), "correos_leidos": len(correos)}


@lacruz.get("/solicitudes")
async def listar_solicitudes():
    docs = await db.lacruz_solicitudes.find({}, {"_id": 0}).sort("prioridad", 1).to_list(100)
    return {"total": len(docs), "solicitudes": docs}


@lacruz.post("/procesar")
async def procesar_endpoint(request: Request):
    claims = getattr(request.state, "user", None) or {}
    if claims.get("rol") not in ("admin", "maestro"):
        raise HTTPException(status_code=403, detail="Solo el Administrador puede reprocesar")
    return await procesar()
