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
                           "telefono": _v("telefono"), "rut": _v("rut"),
                           "proyecto": _v("proyecto")})
    return prospectos


def mensaje_jose_martin(nombre, proyecto="", link_simulador="", pixel_url=""):
    """Borrador con la voz de José Martín Benavente. Asunto con formato obligatorio."""
    primer = (nombre or "").split()[0].title() or "amigo(a)"
    subject = f"Propuesta Exclusiva de Central Mutuos para {nombre.title()}"
    ref_proyecto = f" para su futuro hogar en <b>{proyecto}</b>" if proyecto else ""
    body = f"""
<div style="font-family:Georgia,'Times New Roman',serif;width:100%;max-width:600px;margin:0 auto;color:#0f172a">
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


def mensaje_seguimiento(nombre, proyecto="", link_simulador="", pixel_url="", interes="nuevo"):
    """Correo de seguimiento a los 14 días, con gancho según el interés detectado."""
    primer = (nombre or "").split()[0].title() or "amigo(a)"
    subject = f"¿Seguimos con tu crédito, {primer}? — Central Mutuos"
    if interes == "uso_simulador":
        gancho = f"Vi que usaste mi simulador VIP — ¡bien ahí, {primer}! 🎯 El siguiente paso es simple: me mandas tus documentos y yo me encargo de todo el resto con Gerardo."
    elif interes == "hizo_clic":
        gancho = "Vi que le echaste un ojo a mi simulador. Si algún número te dejó pensando, lo revisamos juntos en 5 minutos — sin compromiso."
    elif interes == "abrio_correo":
        gancho = "Sé que leíste mi correo anterior 😉. Las condiciones preferentes que te conté siguen vigentes, pero no duran para siempre."
    else:
        gancho = "Hace un par de semanas te escribí y no quiero que se te pase: las condiciones preferentes de financiamiento siguen disponibles."
    ref_proyecto = f" para tu futuro hogar en <b>{proyecto}</b>" if proyecto else ""
    body = f"""
<div style="font-family:Georgia,'Times New Roman',serif;max-width:560px;margin:0 auto;color:#0f172a">
  <div style="background:#0f172a;padding:26px 30px;border-radius:14px 14px 0 0">
    <div style="color:#e2e8f0;font-size:20px;font-weight:700;letter-spacing:0.18em">CENTRAL MUTUOS</div>
    <div style="color:#94a3b8;font-size:11px;letter-spacing:0.12em;margin-top:4px">BANCA HIPOTECARIA PRIVADA</div>
  </div>
  <div style="background:#ffffff;border:1px solid #e2e8f0;border-top:none;padding:30px;border-radius:0 0 14px 14px">
    <p style="font-size:16px">Hola {primer}, ¡José Martín de nuevo por acá! 👋</p>
    <p style="line-height:1.75;color:#334155">{gancho}</p>
    <p style="line-height:1.75;color:#334155">Sigo teniendo condiciones preferentes de financiamiento hipotecario{ref_proyecto}.
    Retoma tu simulación cuando quieras — 30 segundos desde el celular:</p>
    <div style="text-align:center;margin:26px 0">
      <a href="{link_simulador}" style="background:#0f172a;color:#fff;text-decoration:none;font-family:Arial;
      font-weight:700;font-size:14px;padding:14px 34px;border-radius:999px;display:inline-block">
      Retomar mi simulación VIP →</a>
    </div>
    <p style="line-height:1.75;color:#334155">Y si prefieres, me respondes este correo y coordinamos una llamada.
    Para eso estoy, de verdad. ¡Un abrazo! 💪</p>
    <p style="color:#0f172a;font-weight:700;margin-top:26px">José Martín Benavente<br>
    <span style="font-weight:400;color:#64748b;font-size:12px">Asesor Comercial VIP · Central Mutuos</span></p>
  </div>
  <img src="{pixel_url}" width="1" height="1" alt="" style="display:block">
</div>"""
    return {"subject": subject, "body": body}


def mensaje_invitacion_vip(nombre, proyecto="", link_portal="", pixel_url=""):
    """PLANTILLA MASERATI: Negro Carbono, bordes Oro 24K, logo metálico Central Mutuos."""
    primer = (nombre or "").title() or "Cliente"
    proy = (proyecto or "").strip()
    subject = f"Invitación VIP — Pre-Calificación Reservada para {primer}"
    ref_proy = f' para su proyecto <b style="color:#FCF6BA">{proy}</b>' if proy else ""
    body = f"""
<div style="background:#000000;padding:34px 14px;font-family:Georgia,'Times New Roman',serif">
  <div style="width:100%;max-width:600px;margin:0 auto;background:#050505;border:1px solid #D4AF37">
    <div style="border-bottom:1px solid #7a6a2f;padding:30px 34px;text-align:center;
                background:linear-gradient(165deg,#0d0b06,#050505)">
      <div style="font-size:24px;font-weight:700;letter-spacing:0.24em;color:#D4AF37;
                  text-shadow:0 1px 0 #FCF6BA">CENTRAL MUTUOS</div>
      <div style="color:#9a8c52;font-size:10px;letter-spacing:0.32em;margin-top:6px">
        BANCA HIPOTECARIA PRIVADA · CON CRECES</div>
    </div>
    <div style="padding:36px 34px;color:#e5e5e5">
      <p style="font-size:17px;color:#FCF6BA;margin:0 0 18px">Estimado(a) {primer},</p>
      <p style="line-height:1.85;font-size:14.5px;color:#c9c9c9;margin:0 0 16px">
        <b style="color:#F5E7B8">Central Mutuos</b> ha reservado para usted una sesión de
        <b style="color:#F5E7B8">Pre-Calificación VIP</b>{ref_proy}.</p>
      <p style="line-height:1.85;font-size:14.5px;color:#c9c9c9;margin:0 0 26px">
        Haga clic en el botón de abajo para subir sus documentos de forma segura
        y asegurar su financiamiento hoy mismo.</p>
      <div style="text-align:center;margin:30px 0">
        <a href="{link_portal}" style="display:inline-block;text-decoration:none;
           background:linear-gradient(135deg,#BF953F,#FCF6BA 45%,#AA771C);color:#0a0a0a;
           font-family:Arial,sans-serif;font-weight:800;font-size:14px;letter-spacing:0.08em;
           padding:16px 40px;border:1px solid #FCF6BA">
           INICIAR MI PRE-CALIFICACIÓN VIP →</a>
      </div>
      <p style="line-height:1.7;font-size:12px;color:#8a8a8a;text-align:center;margin:22px 0 0">
        🔒 Conexión cifrada — sus documentos viajan protegidos directamente a nuestra bóveda.</p>
    </div>
    <div style="border-top:1px solid #33290f;padding:18px 34px;text-align:center">
      <div style="color:#D4AF37;font-size:12px;font-weight:700">Gerardo Barrera</div>
      <div style="color:#6b6b6b;font-size:10.5px;letter-spacing:0.1em;margin-top:3px">
        DIRECCIÓN COMERCIAL · CENTRAL MUTUOS</div>
    </div>
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
    seguimientos = [o for o in oportunidades if o.get("status") == "seguimiento_listo"]
    lineas = [f"Gerardo, ¡buenas! José Martín reportándose — {hoy} 📋",
              f"Tenemos {total} oportunidades en cartera."]
    if calientes:
        lineas.append("🔥 CALIENTES (usaron el simulador o hicieron clic): "
                      + ", ".join(o["nombre"] for o in calientes[:8]) + ". Yo los llamaría HOY.")
    if abrieron:
        lineas.append(f"👀 {len(abrieron)} abrieron nuestro correo — la propuesta está gustando.")
    if seguimientos:
        lineas.append(f"📬 Pasaron los 14 días de {len(seguimientos)} prospecto(s) y ya les dejé el correo de "
                      f"seguimiento LISTO para tu 'Autorizar Envío': "
                      + ", ".join(o["nombre"] for o in seguimientos[:8]) + ".")
    if pendientes:
        lineas.append(f"✍️ Tengo {len(pendientes)} borradores listos esperando tu 'Autorizar Envío': "
                      + ", ".join(o["nombre"] for o in pendientes[:8]) + ".")
    if not (calientes or abrieron or pendientes or seguimientos):
        lineas.append("Día tranquilo: sube un listado nuevo y me pongo a trabajar altiro.")
    lineas.append("Nada sale sin tu visto bueno, jefe. Un abrazo — J.M.")
    return {"fecha": hoy, "nota": "\n".join(lineas), "total": total,
            "calientes": len(calientes), "abrieron": len(abrieron),
            "pendientes": len(pendientes), "seguimientos": len(seguimientos)}


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
        if await db.prospectos.find_one(q):
            duplicados += 1
            continue
        await db.prospectos.insert_one({
            "id": str(uuid.uuid4()), **p, "status": "pendiente_autorizacion",
            "modo": "PROSPECCIÓN",
            "estado_interes": "nuevo", "borrador": None, "aperturas": 0, "clics": 0,
            "bloqueado_hasta": "", "creado_en": datetime.now(timezone.utc).isoformat()})
        nuevos += 1
    return {"nuevos": nuevos, "duplicados": duplicados}


async def listar():
    return await db.prospectos.find({"estado": {"$ne": "PROMOVIDO"}}, {"_id": 0}).sort("creado_en", -1).to_list(500)


async def preparar_borrador(oid, base_url, link_click):
    op = await db.prospectos.find_one({"id": oid})
    if not op:
        raise ValueError("Oportunidad no encontrada")
    pixel = f"{base_url}/api/oportunidades/track/{oid}/pixel.gif"
    msg = mensaje_jose_martin(op["nombre"], op.get("proyecto", ""), link_click, pixel)
    await db.prospectos.update_one({"id": oid}, {"$set": {"borrador": msg}})
    return {**msg, "to": op.get("email", ""), "nombre": op["nombre"]}


async def autorizar_envio(oid, send_fn):
    """CANDADO: solo se ejecuta cuando Gerardo presiona 'Autorizar Envío'.
    Tras enviar, bloqueo de seguimiento de 14 días (no se puede reenviar)."""
    op = await db.prospectos.find_one({"id": oid})
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
    await db.prospectos.update_one({"id": oid}, {"$set": {
        "status": "enviado", "enviado_en": ahora, "bloqueado_hasta": hasta,
        "autorizado_por": "Gerardo"}})
    return {"ok": True, "to": to, "bloqueado_hasta": hasta}


async def track(oid, tipo):
    campo = "aperturas" if tipo == "pixel" else "clics"
    estado = "abrio_correo" if tipo == "pixel" else "hizo_clic"
    op = await db.prospectos.find_one({"id": oid})
    if not op:
        return None
    upd = {"$inc": {campo: 1}}
    if _ORDEN_INTERES.get(estado, 0) > _ORDEN_INTERES.get(op.get("estado_interes", "nuevo"), 0):
        upd["$set"] = {"estado_interes": estado}
    await db.prospectos.update_one({"id": oid}, upd)
    return op


async def marcar_uso_simulador(oid):
    await db.prospectos.update_one({"id": oid}, {"$set": {"estado_interes": "uso_simulador"}})


async def proponer_seguimientos(base_url):
    """RECORDATORIO AUTOMÁTICO: al vencer el bloqueo de 14 días, José Martín deja el
    correo de seguimiento LISTO — Gerardo solo debe presionar 'Autorizar Envío'."""
    ahora = datetime.now(timezone.utc).isoformat()
    listos = 0
    ops_vencidas = await db.prospectos.find({"status": "enviado",
                                                "bloqueado_hasta": {"$nin": ["", None], "$lte": ahora}}).to_list(200)
    for op in ops_vencidas:
        if "@" not in (op.get("email") or ""):
            continue
        link_click = f"{base_url}/api/oportunidades/track/{op['id']}/click"
        pixel = f"{base_url}/api/oportunidades/track/{op['id']}/pixel.gif"
        msg = mensaje_seguimiento(op["nombre"], op.get("proyecto", ""), link_click, pixel,
                                  op.get("estado_interes", "nuevo"))
        await db.prospectos.update_one({"id": op["id"]}, {"$set": {
            "status": "seguimiento_listo", "borrador": msg, "bloqueado_hasta": "",
            "seguimiento_n": int(op.get("seguimiento_n") or 0) + 1,
            "seguimiento_propuesto_en": ahora}})
        listos += 1
    return listos


async def desde_expediente_vip(nombre, rut, sim):
    """Lead viable del Simulador Martín entra directo al Centro de Ventas VIP."""
    sim = sim or {}
    ya = await db.prospectos.find_one({"nombre": {"$regex": f"^{re.escape(nombre)}$", "$options": "i"}})
    if ya:
        await db.prospectos.update_one({"id": ya["id"]}, {"$set": {
            "estado_interes": "uso_simulador", "expediente_vip": True, "simulacion": sim, "rut": rut}})
        return ya["id"]
    oid = str(uuid.uuid4())
    await db.prospectos.insert_one({
        "id": oid, "nombre": nombre, "email": "", "telefono": "", "proyecto": "",
        "rut": rut, "status": "expediente_vip", "estado_interes": "uso_simulador",
        "expediente_vip": True, "simulacion": sim, "borrador": None,
        "aperturas": 0, "clics": 0, "bloqueado_hasta": "",
        "creado_en": datetime.now(timezone.utc).isoformat()})
    return oid

