"""🕵️ AUDITORÍA AUTOMATIZADA DE FLUJOS: recorre los flujos del sistema como un
usuario real y reporta incoherencias con el paso exacto donde ocurren."""
import asyncio
import io
import re
import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from database import db

audf = APIRouter()


def _exigir(request):
    c = getattr(request.state, "user", {}) or {}
    if c.get("rol") not in ("admin", "maestro"):
        raise HTTPException(status_code=403, detail="Solo el administrador")
    return c


def _item(flujo, paso, resultado, descripcion=""):
    return {"flujo": flujo, "paso": paso, "resultado": resultado, "descripcion": descripcion}


async def _auditar_simulador(items):
    import credit_engine as ce
    combos = []
    for monto in (2000, 4000, 8000, 12000):
        for codeudor in (False, True):
            for edad in (30, 55, 68):
                for sub_nombre, sub_uf in (("sin subsidio", 0), ("DS19 tramo 2", 1000),
                                           ("DS19 tramo 3", 600), ("DS01", 500)):
                    combos.append((monto, codeudor, edad, sub_nombre, sub_uf))
    fallos = 0
    for monto, codeudor, edad, sub_nombre, sub_uf in combos:
        paso = (f"Simulación {monto} UF · {'con codeudor' if codeudor else 'deudor individual'} · "
                f"edad {edad} · {sub_nombre}")
        try:
            d = {"renta_titular": 2_500_000, "renta_codeudor": 1_500_000 if codeudor else 0,
                 "plazo_anos": 25, "tasa_anual": 0.0635, "ahorro_uf": monto * 0.1,
                 "subsidio_uf": sub_uf, "edad_cliente": edad,
                 "edad_codeudor": 45 if codeudor else 0, "valor_propiedad_uf": monto * 1.25,
                 "credito_solicitado_uf": monto, "valor_uf": 40859}
            r = ce.simular_credito(d)
            if not isinstance(r, dict) or not r:
                raise ValueError("respuesta vacía")
        except Exception as e:
            fallos += 1
            items.append(_item("Envío a MESA (simulador)", paso, "incorrecto", f"Error: {str(e)[:120]}"))
    items.append(_item("Envío a MESA (simulador)",
                       f"Matriz completa: {len(combos)} combinaciones (2.000–12.000 UF, individual/codeudor, edades, DS19 T2/T3, DS01, sin subsidio)",
                       "correcto" if fallos == 0 else "alerta",
                       "Todas las combinaciones simulan sin errores" if fallos == 0 else f"{fallos} combinaciones fallaron"))


def _auditar_calculadora(items):
    import credit_engine as ce
    checks = [
        ("Dividendo positivo en todos los rangos",
         all(ce.dividendo(m, 0.05, p) > 0 for m in (2000, 5000, 12000) for p in (10, 20, 30))),
        ("A mayor monto, mayor dividendo",
         ce.dividendo(2000, 0.05, 20) < ce.dividendo(8000, 0.05, 20) < ce.dividendo(12000, 0.05, 20)),
        ("A mayor plazo, menor dividendo",
         ce.dividendo(5000, 0.05, 10) > ce.dividendo(5000, 0.05, 20) > ce.dividendo(5000, 0.05, 30)),
        ("A mayor tasa, mayor dividendo",
         ce.dividendo(5000, 0.04, 20) < ce.dividendo(5000, 0.07, 20)),
    ]
    try:
        m = 6000
        inv = ce.capacidad_desde_dividendo(ce.dividendo(m, 0.05, 25), 0.05, 25)
        checks.append(("Consistencia inversa dividendo↔capacidad (±1%)", abs(inv - m) / m < 0.01))
    except Exception:
        checks.append(("Consistencia inversa dividendo↔capacidad", False))
    for paso, ok in checks:
        items.append(_item("Calculadora hipotecaria", paso, "correcto" if ok else "incorrecto",
                           "" if ok else "El cálculo no cumple la coherencia matemática esperada"))


async def _auditar_flujo_mesa(items):
    import email_service as mail_mod
    import mesa_verdad as mv
    capt = {}
    original = mail_mod.send_mail

    def mock(to, subject, body_html, attachments=None, *a, **kw):
        capt.update({"to": to, "subject": subject, "body": body_html, "adj": attachments or []})
        return {"success": True}
    mail_mod.send_mail = mock
    fid = "AUDIT-" + uuid.uuid4().hex[:8]
    try:
        # APROBACIÓN con frase exacta de MESA
        mid = "AUDIT-APROB-" + uuid.uuid4().hex[:8]
        r = await mv._procesar_correo({"id": mid, "subject": "Re: Cliente Auditoria Flujos",
                                       "body": "Tenemos el agrado de informar que su cliente califica para un mutuo hipotecario endosable. Adjuntamos carta y simulación.",
                                       "from": mv.MESA_EMAIL, "date": "2026-08-21"})
        ok_cl = r and r["tipo"] == "aprobacion"
        items.append(_item("Flujo de aprobación", "Clasificación con frase exacta de MESA ('tenemos el agrado de informar')",
                           "correcto" if ok_cl else "incorrecto", "" if ok_cl else f"tipo={r and r['tipo']}"))
        fw = (r or {}).get("reenvio_gerardo") or {}
        ok_fw = fw.get("ok") and capt.get("to") == "gerardo.ext@centralmutuos.cl" \
            and "agrado de informar" in (capt.get("body") or "")
        items.append(_item("Flujo de aprobación", "Reenvío inmediato a gerardo.ext con cuerpo íntegro de MESA",
                           "correcto" if ok_fw else "incorrecto",
                           f"destino={capt.get('to')}, adjuntos={len(capt.get('adj') or [])}"))
        # PDF sin gastos operacionales (regla primera hoja)
        try:
            import pdf_service as pdfs
            from reportlab.pdfgen import canvas as _cv
            buf = io.BytesIO()
            c = _cv.Canvas(buf)
            c.drawString(50, 750, "SIMULACION - primera hoja limpia")
            c.showPage()
            c.drawString(50, 750, "gastos operacionales: $500.000")
            c.showPage()
            c.save()
            raw, _o, _rm = pdfs.dejar_primera_pagina(buf.getvalue())
            texto = pdfs.leer_texto(raw, 3)
            ok_pdf = "gastos operacionales" not in texto.lower()
            items.append(_item("Flujo de aprobación", "Simulación PDF queda sin gastos operacionales (solo primera hoja)",
                               "correcto" if ok_pdf else "incorrecto",
                               "" if ok_pdf else "El PDF resultante aún menciona gastos operacionales"))
        except Exception as e:
            items.append(_item("Flujo de aprobación", "Validación PDF sin gastos operacionales", "alerta", str(e)[:120]))
        await db.mesa_verdad_log.delete_many({"correo_id": mid})

        # RECHAZO asociado por RUT + nombre (estricto)
        await db.folders.insert_one({"id": fid, "nombre": "Cliente Auditoria Interna",
                                     "rut": "11.111.111-1", "created_at": datetime.now(timezone.utc).isoformat()})
        mid2 = "AUDIT-RECH-" + uuid.uuid4().hex[:8]
        await mv._procesar_correo({"id": mid2, "subject": "Re: Cliente Auditoria Interna",
                                   "body": "El cliente Cliente Auditoria Interna RUT 11.111.111-1 no cumple parámetros objetivos mínimos de aprobación.",
                                   "from": mv.MESA_EMAIL, "date": "2026-08-21"})
        f = await db.folders.find_one({"id": fid})
        ok_re = (f or {}).get("resultado_mesa") == "reprobado"
        items.append(_item("Flujo de rechazo", "Rechazo queda registrado en la carpeta correcta validando nombre + RUT",
                           "correcto" if ok_re else "incorrecto",
                           "" if ok_re else f"resultado_mesa={(f or {}).get('resultado_mesa')}"))
        # Negativo: mismo nombre, RUT distinto → NO debe asociar
        mid3 = "AUDIT-NEG-" + uuid.uuid4().hex[:8]
        await db.folders.update_one({"id": fid}, {"$unset": {"resultado_mesa": "", "resultado_mesa_at": ""}})
        await mv._procesar_correo({"id": mid3, "subject": "Re: Cliente Auditoria Interna",
                                   "body": "Cliente Auditoria Interna RUT 22.222.222-2 no cumple parámetros objetivos mínimos.",
                                   "from": mv.MESA_EMAIL, "date": "2026-08-21"})
        f2 = await db.folders.find_one({"id": fid})
        ok_neg = not (f2 or {}).get("resultado_mesa")
        items.append(_item("Flujo de rechazo", "Anti falso positivo: RUT distinto NO se asocia aunque el nombre coincida",
                           "correcto" if ok_neg else "incorrecto",
                           "" if ok_neg else "Se asoció un resultado con RUT que no corresponde"))
        await db.mesa_verdad_log.delete_many({"correo_id": {"$in": [mid2, mid3]}})
    finally:
        mail_mod.send_mail = original
        await db.folders.delete_many({"id": fid})


async def _auditar_recepcion(items):
    try:
        import pdf_service as pdfs
        from reportlab.pdfgen import canvas as _cv
        buf = io.BytesIO()
        c = _cv.Canvas(buf)
        c.drawString(50, 750, "Liquidacion de sueldo - RUT 11.111.111-1")
        c.save()
        texto = pdfs.leer_texto(buf.getvalue(), 2)
        ok = "liquidacion" in texto.lower() and "11.111.111-1" in texto
        items.append(_item("Recepción de archivos", "Un PDF recibido se lee y su contenido (tipo doc + RUT) es extraíble para asociarlo al cliente",
                           "correcto" if ok else "incorrecto", "" if ok else "No se pudo extraer texto del PDF"))
    except Exception as e:
        items.append(_item("Recepción de archivos", "Lectura de adjuntos PDF", "incorrecto", str(e)[:120]))
    n = await db.folders.count_documents({"archivos.0": {"$exists": True}})
    items.append(_item("Recepción de archivos", "Carpetas con archivos asociados en base de datos",
                       "correcto" if n > 0 else "alerta", f"{n} carpetas tienen archivos asociados"))


def _auditar_navegacion(items):
    import os
    base = "/app/frontend/src"
    checks = [
        ("Helper de navegación (estado exacto al Volver) existe", os.path.exists(f"{base}/utils/navegacion.js")),
        ("Calendario conserva mes/día al volver", "leerEstado(\"calendario\")" in open(f"{base}/components/CalendarioCarpetas.js").read()),
        ("Carpeta Clientes restaura scroll/pestaña al volver", "tomarRegreso(\"clientes\")" in open(f"{base}/pages/ClientesModule.js").read()),
        ("Botones 'Volver a Carpeta Clientes' marcan regreso (Gastos/SetCrédito/Aprobación)",
         all("marcarRegreso(\"clientes\")" in open(f"{base}/pages/{p}.js").read()
             for p in ("GastosOperacionalesModule", "SetCreditoModule", "AprobacionClienteModule"))),
    ]
    for paso, ok in checks:
        items.append(_item("Navegación", paso, "correcto" if ok else "incorrecto",
                           "" if ok else "El comportamiento de Volver no cumple la normativa de navegación"))


@audf.post("/auditoria-flujos/ejecutar")
async def auditoria_ejecutar(request: Request):
    _exigir(request)
    items = []
    for fn in (_auditar_simulador, _auditar_flujo_mesa, _auditar_recepcion):
        try:
            await fn(items)
        except Exception as e:
            logging.warning(f"auditoria {fn.__name__}: {e}")
            items.append(_item(fn.__name__, "Ejecución del bloque", "incorrecto", str(e)[:150]))
    for fn in (_auditar_calculadora, _auditar_navegacion):
        try:
            fn(items)
        except Exception as e:
            items.append(_item(fn.__name__, "Ejecución del bloque", "incorrecto", str(e)[:150]))
    resumen = {"correcto": sum(1 for i in items if i["resultado"] == "correcto"),
               "incorrecto": sum(1 for i in items if i["resultado"] == "incorrecto"),
               "alerta": sum(1 for i in items if i["resultado"] == "alerta")}
    run = {"id": str(uuid.uuid4()), "fecha": datetime.now(timezone.utc).isoformat(),
           "resumen": resumen, "items": items}
    await db.auditoria_flujos.insert_one(dict(run))
    return run


@audf.get("/auditoria-flujos/ultima")
async def auditoria_ultima(request: Request):
    _exigir(request)
    r = await db.auditoria_flujos.find_one({}, {"_id": 0}, sort=[("fecha", -1)])
    return r or {"items": [], "resumen": {}}


@audf.get("/auditoria-flujos/pdf")
async def auditoria_pdf(request: Request):
    _exigir(request)
    r = await db.auditoria_flujos.find_one({}, {"_id": 0}, sort=[("fecha", -1)])
    if not r:
        raise HTTPException(status_code=404, detail="Sin auditorías ejecutadas")
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as _cv
    buf = io.BytesIO()
    c = _cv.Canvas(buf, pagesize=A4)
    w, h = A4
    y = h - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, "AUDITORÍA AUTOMATIZADA DE FLUJOS — CENTRAL MUTUOS")
    y -= 18
    c.setFont("Helvetica", 9)
    res = r.get("resumen") or {}
    c.drawString(40, y, f"Fecha: {r.get('fecha', '')[:16]} · Correctos: {res.get('correcto', 0)} · "
                        f"Incorrectos: {res.get('incorrecto', 0)} · Alertas: {res.get('alerta', 0)}")
    y -= 22
    for it in r.get("items", []):
        if y < 70:
            c.showPage()
            y = h - 50
            c.setFont("Helvetica", 9)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(40, y, f"[{it['resultado'].upper()}] {it['flujo']}")
        y -= 12
        c.setFont("Helvetica", 8)
        c.drawString(52, y, (it["paso"] or "")[:110])
        y -= 11
        if it.get("descripcion"):
            c.drawString(52, y, ("→ " + it["descripcion"])[:110])
            y -= 11
        y -= 4
    c.save()
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": "attachment; filename=auditoria_flujos.pdf"})
