"""Motor comercial del Centro de Ventas VIP — José Martín Benavente.
Identidad: chileno, carismático, gay, comercial de élite y leal a Gerardo.
REGLA INVIOLABLE: este motor solo PREPARA; nada sale sin 'Autorizar Envío' de Gerardo."""
import io
import re
from datetime import datetime, timezone

CAMPOS_EXCEL = {
    "nombre": re.compile(r"nombre|cliente|contacto", re.I),
    "email": re.compile(r"mail|correo", re.I),
    "telefono": re.compile(r"fono|tel[eé]fono|celular|m[oó]vil", re.I),
    "proyecto": re.compile(r"proyecto|inmobiliaria|obra", re.I),
}


def parsear_excel(raw_bytes):
    """Lee un listado Excel de prospectos y devuelve [{nombre,email,telefono,proyecto}]."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), data_only=True)
    ws = wb.worksheets[0]
    filas = list(ws.iter_rows(values_only=True))
    if not filas:
        return []
    encabezados = [str(c or "").strip() for c in filas[0]]
    mapa = {}
    for idx, h in enumerate(encabezados):
        for campo, rx in CAMPOS_EXCEL.items():
            if campo not in mapa and rx.search(h):
                mapa[campo] = idx
    if "nombre" not in mapa:
        mapa = {"nombre": 0}
        if len(encabezados) > 1:
            mapa["email"] = 1
        if len(encabezados) > 2:
            mapa["telefono"] = 2
        datos = filas
    else:
        datos = filas[1:]
    prospectos = []
    for fila in datos:
        def _v(campo):
            i = mapa.get(campo)
            return str(fila[i]).strip() if i is not None and i < len(fila) and fila[i] not in (None, "") else ""
        nombre = _v("nombre")
        if len(nombre) < 3 or nombre.lower() in ("nombre", "cliente"):
            continue
        prospectos.append({"nombre": nombre.title(), "email": _v("email").lower(),
                           "telefono": _v("telefono"), "proyecto": _v("proyecto")})
    return prospectos


def mensaje_jose_martin(nombre, proyecto="", link_simulador="", pixel_url=""):
    """Borrador con la voz de José Martín Benavente. Asunto con formato obligatorio."""
    primer = (nombre or "").split()[0].title() or "amigo(a)"
    subject = f"Propuesta Exclusiva de Central Mutuos para {nombre.title()}"
    ref_proyecto = f" para su futuro hogar en <b>{proyecto}</b>" if proyecto else ""
    body = f"""
<div style="font-family:Georgia,'Times New Roman',serif;max-width:560px;margin:0 auto;color:#0f172a">
  <div style="background:#0f172a;padding:26px 30px;border-radius:14px 14px 0 0">
    <div style="color:#e2e8f0;font-size:20px;font-weight:700;letter-spacing:0.18em">CENTRAL MUTUOS</div>
    <div style="color:#94a3b8;font-size:11px;letter-spacing:0.12em;margin-top:4px">BANCA HIPOTECARIA PRIVADA</div>
  </div>
  <div style="background:#ffffff;border:1px solid #e2e8f0;border-top:none;padding:30px;border-radius:0 0 14px 14px">
    <p style="font-size:16px">Hola {primer}, ¡un gusto saludarte! 👋</p>
    <p style="line-height:1.75;color:#334155">Soy <b>José Martín Benavente</b>, asesor comercial de Central Mutuos.
    Revisé tu caso con cariño y te tengo buenas noticias: tenemos condiciones preferentes de financiamiento
    hipotecario{ref_proyecto}, de esas que uno no deja pasar.</p>
    <p style="line-height:1.75;color:#334155">Te preparé un <b>simulador VIP</b> — en 30 segundos y desde el celular
    sabes exactamente dónde estás parado(a). Sin letra chica, te lo prometo:</p>
    <div style="text-align:center;margin:26px 0">
      <a href="{link_simulador}" style="background:#0f172a;color:#fff;text-decoration:none;font-family:Arial;
      font-weight:700;font-size:14px;padding:14px 34px;border-radius:999px;display:inline-block">
      Simular mi crédito VIP →</a>
    </div>
    <p style="line-height:1.75;color:#334155">Cualquier duda me escribes no más, que para eso estoy.
    Con Gerardo y todo el equipo vamos a dejar tu crédito <i>impecable</i>. ¡Vamos con todo! 💪</p>
    <p style="color:#0f172a;font-weight:700;margin-top:26px">José Martín Benavente<br>
    <span style="font-weight:400;color:#64748b;font-size:12px">Asesor Comercial VIP · Central Mutuos</span></p>
  </div>
  <img src="{pixel_url}" width="1" height="1" alt="" style="display:block">
</div>"""
    return {"subject": subject, "body": body}


def nota_diaria(oportunidades):
    """Resumen diario de José Martín para Gerardo."""
    hoy = datetime.now(timezone.utc).strftime("%d-%m-%Y")
    total = len(oportunidades)
    abrieron = [o for o in oportunidades if o.get("estado_interes") in ("abrio_correo", "hizo_clic", "uso_simulador")]
    calientes = [o for o in oportunidades if o.get("estado_interes") in ("hizo_clic", "uso_simulador")]
    pendientes = [o for o in oportunidades if o.get("status") == "pendiente_autorizacion" and o.get("borrador")]
    lineas = [f"Gerardo, ¡buenas! José Martín reportándose — {hoy} 📋",
              f"Tenemos {total} oportunidades en cartera."]
    if calientes:
        lineas.append("🔥 CALIENTES (usaron el simulador o hicieron clic): "
                      + ", ".join(o["nombre"] for o in calientes[:8]) + ". Yo los llamaría HOY.")
    if abrieron:
        lineas.append(f"👀 {len(abrieron)} abrieron nuestro correo — la propuesta está gustando.")
    if pendientes:
        lineas.append(f"✍️ Tengo {len(pendientes)} borradores listos esperando tu 'Autorizar Envío': "
                      + ", ".join(o["nombre"] for o in pendientes[:8]) + ".")
    if not (calientes or abrieron or pendientes):
        lineas.append("Día tranquilo: sube un listado nuevo y me pongo a trabajar altiro.")
    lineas.append("Nada sale sin tu visto bueno, jefe. Un abrazo — J.M.")
    return {"fecha": hoy, "nota": "\n".join(lineas), "total": total,
            "calientes": len(calientes), "abrieron": len(abrieron), "pendientes": len(pendientes)}


# ===================== CAPA DE SERVICIO (MongoDB) =====================
import uuid
import asyncio
from datetime import timedelta
from database import db

_ORDEN_INTERES = {"nuevo": 0, "abrio_correo": 1, "hizo_clic": 2, "uso_simulador": 3}


async def crear_oportunidades(prospectos):
    nuevos, duplicados = 0, 0
    for p in prospectos:
        q = {"email": p["email"]} if p.get("email") else {"nombre": p["nombre"]}
        if await db.oportunidades.find_one(q):
            duplicados += 1
            continue
        await db.oportunidades.insert_one({
            "id": str(uuid.uuid4()), **p, "status": "pendiente_autorizacion",
            "estado_interes": "nuevo", "borrador": None, "aperturas": 0, "clics": 0,
            "bloqueado_hasta": "", "creado_en": datetime.now(timezone.utc).isoformat()})
        nuevos += 1
    return {"nuevos": nuevos, "duplicados": duplicados}


async def listar():
    return await db.oportunidades.find({}, {"_id": 0}).sort("creado_en", -1).to_list(500)


async def preparar_borrador(oid, base_url, link_click):
    op = await db.oportunidades.find_one({"id": oid})
    if not op:
        raise ValueError("Oportunidad no encontrada")
    pixel = f"{base_url}/api/oportunidades/track/{oid}/pixel.gif"
    msg = mensaje_jose_martin(op["nombre"], op.get("proyecto", ""), link_click, pixel)
    await db.oportunidades.update_one({"id": oid}, {"$set": {"borrador": msg}})
    return {**msg, "to": op.get("email", ""), "nombre": op["nombre"]}


async def autorizar_envio(oid, send_fn):
    """CANDADO: solo se ejecuta cuando Gerardo presiona 'Autorizar Envío'.
    Tras enviar, bloqueo de seguimiento de 14 días (no se puede reenviar)."""
    op = await db.oportunidades.find_one({"id": oid})
    if not op:
        raise ValueError("Oportunidad no encontrada")
    if not op.get("borrador"):
        raise ValueError("Primero prepara el borrador de José Martín")
    to = (op.get("email") or "").strip()
    if "@" not in to:
        raise ValueError("La oportunidad no tiene un correo válido")
    ahora = datetime.now(timezone.utc).isoformat()
    bloq = op.get("bloqueado_hasta") or ""
    if bloq and bloq > ahora:
        raise ValueError(f"Seguimiento activo: bloqueado hasta {bloq[:10]} (regla de 14 días)")
    res = await asyncio.to_thread(send_fn, to, op["borrador"]["subject"], op["borrador"]["body"])
    if not res.get("success"):
        raise RuntimeError(res.get("error", "Error de envío"))
    hasta = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
    await db.oportunidades.update_one({"id": oid}, {"$set": {
        "status": "enviado", "enviado_en": ahora, "bloqueado_hasta": hasta,
        "autorizado_por": "Gerardo"}})
    return {"ok": True, "to": to, "bloqueado_hasta": hasta}


async def track(oid, tipo):
    campo = "aperturas" if tipo == "pixel" else "clics"
    estado = "abrio_correo" if tipo == "pixel" else "hizo_clic"
    op = await db.oportunidades.find_one({"id": oid})
    if not op:
        return None
    upd = {"$inc": {campo: 1}}
    if _ORDEN_INTERES.get(estado, 0) > _ORDEN_INTERES.get(op.get("estado_interes", "nuevo"), 0):
        upd["$set"] = {"estado_interes": estado}
    await db.oportunidades.update_one({"id": oid}, upd)
    return op


async def marcar_uso_simulador(oid):
    await db.oportunidades.update_one({"id": oid}, {"$set": {"estado_interes": "uso_simulador"}})


async def desde_expediente_vip(nombre, rut, sim):
    """Lead viable del Simulador Martín entra directo al Centro de Ventas VIP."""
    sim = sim or {}
    ya = await db.oportunidades.find_one({"nombre": {"$regex": f"^{re.escape(nombre)}$", "$options": "i"}})
    if ya:
        await db.oportunidades.update_one({"id": ya["id"]}, {"$set": {
            "estado_interes": "uso_simulador", "expediente_vip": True, "simulacion": sim, "rut": rut}})
        return ya["id"]
    oid = str(uuid.uuid4())
    await db.oportunidades.insert_one({
        "id": oid, "nombre": nombre, "email": "", "telefono": "", "proyecto": "",
        "rut": rut, "status": "expediente_vip", "estado_interes": "uso_simulador",
        "expediente_vip": True, "simulacion": sim, "borrador": None,
        "aperturas": 0, "clics": 0, "bloqueado_hasta": "",
        "creado_en": datetime.now(timezone.utc).isoformat()})
    return oid

