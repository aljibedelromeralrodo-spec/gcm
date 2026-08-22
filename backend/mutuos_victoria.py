"""📘 MÓDULO VICTORIA VILCHES — Gestión de Mutuos según Guía de Usuario ConCreces.
Puente de datos: lee la bóveda de Daniela Galindo (clientes/documentos) para autocompletar
y validar; nunca escribe sobre ella. Reglas de Oro Victoria en la Constitución."""
import re
import uuid
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from database import db
from victoria_independiente import (_exigir, _now, _docs_validos, _formularios_auto,
                                    _norm_rut, _norm_rol, _norm_dir, _aviso)

mut = APIRouter(prefix="/mutuos")

ETAPAS_GUIA = [
    {"n": 1, "titulo": "Etapa 1 — Evaluación del Cliente",
     "descripcion": "Se registran los datos del titular, cónyuge y codeudor (Guía: Evaluación Clientes). Los campos llegan autocompletados desde la bóveda. Sigue: Registro de la Operación.",
     "campos": [["rut_titular", "RUT del cliente (formato 12.345.678-9)"], ["nombre_cliente", "Nombre completo del titular"],
                ["estado_civil", "Estado civil"], ["rut_codeudor", "RUT del codeudor (vacío si no hay)"],
                ["nombre_codeudor", "Nombre del codeudor"], ["email", "Correo electrónico"], ["telefono", "Teléfono"]]},
    {"n": 2, "titulo": "Etapa 2 — Registro de la Operación",
     "descripcion": "Se registra la propiedad y su localización (Guía: Registro información de la operación). Sigue: Tasación.",
     "campos": [["direccion_propiedad", "Dirección exacta de la propiedad"], ["comuna", "Comuna"],
                ["region", "Región"], ["situacion_habitacional", "Situación habitacional"]]},
    {"n": 3, "titulo": "Etapa 3 — Tasación",
     "descripcion": "Se ingresan los datos de la tasación (Guía: Acción 3). Sin tasación NO se puede avanzar a operaciones. Sigue: Datos del Crédito.",
     "campos": [["rol_avaluo", "Rol de avalúo fiscal (rol vivienda)"], ["avaluo_fiscal", "Avalúo fiscal (UF)"],
                ["valor_tasacion", "Valor de tasación (UF)"], ["m2_construidos", "M² construidos"],
                ["ano_construccion", "Año de construcción"]]},
    {"n": 4, "titulo": "Etapa 4 — Datos del Crédito y Montos",
     "descripcion": "Condiciones del crédito (Guía: Acción 4). Regla: el crédito no puede superar el 80% del valor de tasación. Sigue: Seguimiento de la Operación.",
     "campos": [["precio_vivienda", "Precio de la vivienda (UF)"], ["credito_uf", "Crédito solicitado (UF)"],
                ["plazo_anos", "Plazo (años)"], ["tasa", "Tasa del crédito (%)"],
                ["subsidio", "Subsidio (monto UF o 'sin subsidio')"], ["pie", "Pie / ahorro (UF)"]]},
    {"n": 5, "titulo": "Etapa 5 — Seguimiento de la Operación",
     "descripcion": "Hitos del proceso (Guía: Acción 5): estudio de título, escrituración, notaría y CBR. Sigue: Validación final y envío a revisión de riesgo.",
     "campos": [["fecha_estudio_titulo", "Estudio de título — fecha de envío al abogado"],
                ["fecha_escrituracion", "Escrituración — fecha de envío"],
                ["notaria", "Notaría"], ["fecha_ingreso_cbr", "Ingreso CBR — fecha"]]},
    {"n": 6, "titulo": "Etapa 6 — Validación Final y Envío a Revisión de Riesgo",
     "descripcion": "Se confirma que no queden campos pendientes ni validaciones en rojo (Guía: Seguimiento operación, Pasos 1 y 2). Con la autorización de Victoria, la operación se envía a revisión de riesgo en ConCreces.",
     "campos": []},
]
OBLIGATORIOS = {1: ["rut_titular", "nombre_cliente"], 2: ["direccion_propiedad"],
                3: ["rol_avaluo", "valor_tasacion"], 4: ["precio_vivienda", "credito_uf", "plazo_anos"],
                5: [], 6: []}


def _num(v):
    try:
        return float(str(v).replace(".", "").replace(",", "."))
    except Exception:
        return None


async def _validaciones_op(op, cliente):
    """4 validaciones irrenunciables contra los documentos de la bóveda (puente Daniela→Victoria)."""
    docs = await _docs_validos(cliente["id"])
    boveda = _formularios_auto(cliente, docs)
    datos = {}
    for e in op.get("etapas", {}).values():
        datos.update(e.get("datos") or {})
    out = []
    for campo, etiqueta, norm in (("rut_titular", "RUT del cliente vs documentos", _norm_rut),
                                  ("rut_codeudor", "RUT del codeudor vs documentos", _norm_rut),
                                  ("rol_avaluo", "Rol de avalúo vs tasación y estudio de títulos", _norm_rol),
                                  ("direccion_propiedad", "Dirección vs tasación y estudio de títulos", _norm_dir)):
        ing = str(datos.get(campo) or "").strip()
        doc = str(boveda.get(campo) or "").strip()
        ok = None if (not ing or not doc) else (norm(ing) == norm(doc))
        out.append({"campo": campo, "etiqueta": etiqueta, "ok": ok, "ingresado": ing, "documento": doc})
    # Regla 80% deuda/garantía (Guía: Antecedentes Operación / Acción 7)
    credito, tasacion = _num(datos.get("credito_uf")), _num(datos.get("valor_tasacion"))
    if credito and tasacion:
        pct = round(100 * credito / tasacion, 1)
        out.append({"campo": "deuda_garantia", "etiqueta": "Relación deuda/garantía (máximo 80% del valor de tasación)",
                    "ok": pct <= 80, "ingresado": f"{pct}%", "documento": "tope 80%"})
    else:
        out.append({"campo": "deuda_garantia", "etiqueta": "Relación deuda/garantía (máximo 80% del valor de tasación)",
                    "ok": None, "ingresado": "", "documento": "tope 80%"})
    return out


async def _detalle_op(op):
    cliente = await db.victoria_clientes.find_one({"id": op["cliente_id"]}, {"_id": 0})
    validaciones = await _validaciones_op(op, cliente) if cliente else []
    pendientes = {}
    for n, req in OBLIGATORIOS.items():
        datos = (op.get("etapas", {}).get(str(n)) or {}).get("datos") or {}
        faltan = [c for c in req if not str(datos.get(c) or "").strip()]
        if faltan:
            pendientes[n] = faltan
    bloqueos = [v for v in validaciones if v["ok"] is False]
    lista = not pendientes and not bloqueos and all(
        (op.get("etapas", {}).get(str(n)) or {}).get("autorizada") for n in range(1, 6))
    return {"operacion": op, "cliente": cliente, "etapas_guia": ETAPAS_GUIA,
            "validaciones": validaciones, "pendientes": pendientes,
            "lista_para_riesgo": lista}


@mut.get("/panel")
async def panel_mutuos(request: Request):
    _exigir(request)
    ops = await db.victoria_operaciones.find({}, {"_id": 0}).sort("creado", -1).to_list(200)
    clientes = await db.victoria_clientes.find({}, {"_id": 0, "auditoria": 0}).sort("creado", -1).to_list(200)
    out = []
    for op in ops:
        c = next((x for x in clientes if x["id"] == op["cliente_id"]), {})
        autorizadas = sum(1 for e in op.get("etapas", {}).values() if e.get("autorizada"))
        out.append({"id": op["id"], "numero": op.get("numero"), "cliente": c.get("nombre", "—"),
                    "rut": c.get("rut", ""), "etapa_actual": op.get("etapa_actual", 1),
                    "estado": op.get("estado", "en_proceso"), "autorizadas": autorizadas,
                    "creado": op.get("creado", ""), "enviada_en": op.get("enviada_en", "")})
    usados = {op["cliente_id"] for op in ops if op.get("estado") != "enviada_riesgo"}
    disponibles = [{"id": c["id"], "nombre": c["nombre"], "rut": c.get("rut", "")}
                   for c in clientes if c["id"] not in usados]
    return {"operaciones": out,
            "kpis": {"en_proceso": sum(1 for o in out if o["estado"] == "en_proceso"),
                     "enviadas_riesgo": sum(1 for o in out if o["estado"] == "enviada_riesgo"),
                     "clientes_boveda": len(clientes)},
            "clientes_disponibles": disponibles}


@mut.post("/operaciones")
async def crear_operacion(payload: dict, request: Request):
    u = _exigir(request)
    cid = payload.get("cliente_id")
    c = await db.victoria_clientes.find_one({"id": cid}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Cliente no encontrado en la bóveda")
    docs = await _docs_validos(cid)
    auto = _formularios_auto(c, docs)
    numero = await db.victoria_operaciones.count_documents({}) + 1
    op = {"id": str(uuid.uuid4()), "numero": numero, "cliente_id": cid,
          "creado": _now(), "creado_por": u.get("sub", ""), "estado": "en_proceso", "etapa_actual": 1,
          "etapas": {
              "1": {"datos": {"rut_titular": auto.get("rut_titular", ""), "nombre_cliente": auto.get("nombre_cliente", ""),
                              "rut_codeudor": auto.get("rut_codeudor", ""), "nombre_codeudor": "",
                              "estado_civil": "", "email": c.get("email", ""), "telefono": c.get("telefono", "")}},
              "2": {"datos": {"direccion_propiedad": auto.get("direccion_propiedad", ""), "comuna": "", "region": "",
                              "situacion_habitacional": ""}},
              "3": {"datos": {"rol_avaluo": auto.get("rol_avaluo", ""), "avaluo_fiscal": "", "valor_tasacion": "",
                              "m2_construidos": "", "ano_construccion": ""}},
              "4": {"datos": {"precio_vivienda": "", "credito_uf": "", "plazo_anos": "", "tasa": "", "subsidio": "", "pie": ""}},
              "5": {"datos": {"fecha_estudio_titulo": "", "fecha_escrituracion": "", "notaria": "", "fecha_ingreso_cbr": ""}},
              "6": {"datos": {}}}}
    await db.victoria_operaciones.insert_one({**op})
    return {"ok": True, "operacion_id": op["id"], "numero": numero,
            "mensaje": f"Operación #{numero} creada para {c['nombre']}: campos autocompletados desde la bóveda"}


@mut.get("/operaciones/{oid}")
async def detalle_operacion(oid: str, request: Request):
    _exigir(request)
    op = await db.victoria_operaciones.find_one({"id": oid}, {"_id": 0})
    if not op:
        raise HTTPException(status_code=404, detail="Operación no encontrada")
    return await _detalle_op(op)


@mut.put("/operaciones/{oid}/etapa/{n}")
async def guardar_etapa(oid: str, n: int, payload: dict, request: Request):
    _exigir(request)
    if not 1 <= n <= 6:
        raise HTTPException(status_code=400, detail="Etapa inválida")
    op = await db.victoria_operaciones.find_one({"id": oid}, {"_id": 0})
    if not op:
        raise HTTPException(status_code=404, detail="Operación no encontrada")
    if op.get("estado") == "enviada_riesgo":
        raise HTTPException(status_code=403, detail="La operación ya fue enviada a revisión de riesgo: no se puede modificar")
    datos = payload.get("datos") or {}
    rut = str(datos.get("rut_titular") or "").strip()
    if rut and not re.fullmatch(r"\d{1,2}\.?\d{3}\.?\d{3}-[0-9kK]", rut):
        raise HTTPException(status_code=400, detail="RUT inválido: debe ir con puntos y guion (Ej.: 07.654.321-1)")
    await db.victoria_operaciones.update_one({"id": oid}, {"$set": {
        f"etapas.{n}.datos": datos, f"etapas.{n}.autorizada": False}})
    op = await db.victoria_operaciones.find_one({"id": oid}, {"_id": 0})
    return {"ok": True, "detalle": await _detalle_op(op)}


@mut.post("/operaciones/{oid}/autorizar/{n}")
async def autorizar_etapa(oid: str, n: int, payload: dict, request: Request):
    """Pantalla de autorización: Victoria revisa y aprueba la etapa antes de continuar."""
    u = _exigir(request)
    op = await db.victoria_operaciones.find_one({"id": oid}, {"_id": 0})
    if not op:
        raise HTTPException(status_code=404, detail="Operación no encontrada")
    if not payload.get("confirmado"):
        raise HTTPException(status_code=400, detail="Debe declarar que revisó la etapa antes de autorizarla")
    detalle = await _detalle_op(op)
    if n in detalle["pendientes"]:
        raise HTTPException(status_code=403, detail=f"Campos obligatorios pendientes en la etapa {n}: {', '.join(detalle['pendientes'][n])}")
    bloqueos = [v for v in detalle["validaciones"] if v["ok"] is False]
    if n in (1, 2, 3, 4) and bloqueos:
        raise HTTPException(status_code=403, detail="Validación irrenunciable en rojo: " + bloqueos[0]["etiqueta"])
    await db.victoria_operaciones.update_one({"id": oid}, {"$set": {
        f"etapas.{n}.autorizada": True, f"etapas.{n}.autorizada_en": _now(),
        f"etapas.{n}.autorizada_por": u.get("sub", ""), "etapa_actual": min(6, n + 1)}})
    op = await db.victoria_operaciones.find_one({"id": oid}, {"_id": 0})
    return {"ok": True, "mensaje": f"Etapa {n} autorizada por Victoria: puede continuar con la siguiente",
            "detalle": await _detalle_op(op)}


@mut.post("/operaciones/{oid}/enviar-riesgo")
async def enviar_riesgo(oid: str, payload: dict, request: Request):
    u = _exigir(request)
    op = await db.victoria_operaciones.find_one({"id": oid}, {"_id": 0})
    if not op:
        raise HTTPException(status_code=404, detail="Operación no encontrada")
    if not payload.get("confirmado"):
        raise HTTPException(status_code=400, detail="Debe declarar la revisión final antes de enviar a riesgo")
    detalle = await _detalle_op(op)
    if not detalle["lista_para_riesgo"]:
        raise HTTPException(status_code=403, detail="Regla de Oro Victoria: hay etapas sin autorizar, campos pendientes o validaciones en rojo — no se puede enviar a revisión de riesgo")
    await db.victoria_operaciones.update_one({"id": oid}, {"$set": {
        "estado": "enviada_riesgo", "enviada_en": _now(), "enviada_por": u.get("sub", ""),
        "etapas.6.autorizada": True, "etapas.6.autorizada_en": _now()}})
    await _aviso("mutuos", f"Victoria Vilches envió la operación #{op.get('numero')} a revisión de riesgo en ConCreces (puente informativo a la bóveda).", op["cliente_id"])
    return {"ok": True, "mensaje": f"Operación #{op.get('numero')} enviada a revisión de riesgo en ConCreces"}


REGLAS_ORO_VICTORIA = [
    ("REGLA_ORO_VICTORIA-1", "Flujo exacto de la Guía Mutuos", "El módulo de Victoria Vilches sigue el flujo exacto de la Guía de Usuario Mutuos: Evaluación del Cliente → Registro de la Operación → Tasación → Datos del Crédito → Seguimiento → Validación final y envío a revisión de riesgo. Ninguna etapa puede saltarse."),
    ("REGLA_ORO_VICTORIA-2", "Autocompletado desde la bóveda", "Todos los campos posibles se autocompletan con la información de la bóveda (puente de solo lectura con el módulo de Daniela Galindo). Victoria solo revisa, corrige y autoriza."),
    ("REGLA_ORO_VICTORIA-3", "Validaciones irrenunciables", "En cada etapa relevante se valida: RUT del cliente con RUT en documentos, RUT del codeudor con RUT del codeudor, rol de avalúo fiscal con tasación y estudio de títulos, dirección con dirección. Sin estas validaciones aprobadas no se puede avanzar."),
    ("REGLA_ORO_VICTORIA-4", "Autorización previa a ConCreces", "Cada etapa importante termina en una pantalla de autorización donde Victoria revisa y aprueba antes de continuar. El envío a revisión de riesgo exige todas las etapas autorizadas."),
    ("REGLA_ORO_VICTORIA-5", "Trazabilidad de datos críticos", "Nombre, RUT, rol y dirección muestran un indicador al pasar el cursor y, con un clic, abren el documento físico de origen en un panel flotante, sin salir de la pantalla."),
    ("REGLA_ORO_VICTORIA-6", "Tope deuda/garantía y formato RUT", "El crédito no puede superar el 80% del valor de tasación (Guía: Antecedentes Operación). El RUT se ingresa con puntos y guion; si es menor a 10 millones se antepone un 0."),
    ("REGLA_ORO_VICTORIA-7", "Llenado automatizado estricto (Daniela y Victoria)", "El sistema completa automáticamente todos los campos posibles cruzando los documentos cargados, con validaciones obligatorias: RUT titular vs documentos, RUT codeudor vs documentos, Rol de avalúo vs documentos, Dirección vs documentos y todos los datos de tasación. Solo se llena lo hallado con certeza documental. Está ABSOLUTAMENTE PROHIBIDO inventar datos, asumir valores o completar campos sin respaldo. Lo no hallado queda vacío y marcado como PENDIENTE."),
    ("REGLA_ORO_VICTORIA-8", "Vista de auditoría con preview de origen (Daniela y Victoria)", "Daniela Galindo y Victoria Vilches disponen de una vista de auditoría donde cada campo del sistema muestra de qué documento proviene, en qué página aparece y cómo se ve el fragmento original, permitiendo verificación aleatoria sin revisar documentos completos."),
]


async def seed_reglas_oro_victoria():
    for codigo, titulo, detalle in REGLAS_ORO_VICTORIA:
        await db.dashai_eventos.update_one({"codigo": codigo}, {"$set": {
            "tipo": "regla_oro", "etiqueta": "Regla de Oro Victoria", "titulo": titulo,
            "detalle": detalle, "activa": True, "inviolable": True,
            "actualizado": datetime.now(timezone.utc).isoformat()},
            "$setOnInsert": {"id": str(uuid.uuid4()), "fecha": datetime.now(timezone.utc).isoformat()}}, upsert=True)
