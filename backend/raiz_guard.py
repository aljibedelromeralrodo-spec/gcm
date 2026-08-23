"""🌳 RAÍZ GUARD — Reglas obligatorias de roots en carpetas de clientes.
Ninguna carpeta puede existir sin root (RUT del cliente). Correspondencia obligatoria:
cliente↔RUT · codeudor↔RUT codeudor · valor fiscal↔rol de la propiedad ·
tasación↔dirección exacta · estudio de título↔rol fiscal y dirección de la tasación ·
informe de título↔estudio de título. Inconsistencia = bloqueo + alerta al Administrador."""
import re
import uuid
import logging
from datetime import datetime, timezone
from database import db

RX_RUT = re.compile(r"^\d{1,2}\.?\d{3}\.?\d{3}-?[\dkK]$")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _rut_ok(rut):
    return bool(RX_RUT.match(str(rut or "").strip()))


def _norm(s):
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


def validar_roots(doc):
    """Valida la correspondencia obligatoria. Retorna lista exacta de lo que NO coincide."""
    problemas = []
    if not _rut_ok(doc.get("rut")):
        problemas.append("Root del cliente principal ausente o inválido (falta RUT en la carpeta)")
    if (doc.get("codeudor_nombre") or "").strip() and not _rut_ok(doc.get("codeudor_rut")):
        problemas.append(f"Root del codeudor '{doc.get('codeudor_nombre')}' ausente o inválido (falta RUT del codeudor)")
    roots = doc.get("roots") or {}
    df = doc.get("datos_financieros") or {}
    rol_fiscal = _norm(roots.get("rol_propiedad") or df.get("rol_propiedad") or df.get("rol_avaluo"))
    dir_tas = _norm(roots.get("direccion_tasacion"))
    rol_est = _norm(roots.get("rol_estudio_titulo"))
    dir_est = _norm(roots.get("direccion_estudio_titulo"))
    rol_inf = _norm(roots.get("rol_informe_titulo"))
    if rol_fiscal and rol_est and rol_fiscal != rol_est:
        problemas.append(f"Rol de valor fiscal ({rol_fiscal}) NO coincide con el rol del estudio de título ({rol_est})")
    if dir_tas and dir_est and dir_tas != dir_est:
        problemas.append(f"Dirección de la tasación ('{dir_tas}') NO coincide con la del estudio de título ('{dir_est}')")
    if rol_inf and rol_est and rol_inf != rol_est:
        problemas.append(f"Rol del informe de título ({rol_inf}) NO coincide con el del estudio de título ({rol_est})")
    return problemas


async def alertar_admin(doc, problemas):
    detalle = " · ".join(problemas)
    await db.alertas.insert_one({
        "id": str(uuid.uuid4()), "tipo": "roots_inconsistentes", "cliente": doc.get("nombre", ""),
        "folder_id": doc.get("id", ""), "mensaje": f"🌳 ROOTS INCONSISTENTES en {doc.get('nombre','')}: {detalle}",
        "fecha": _now(), "leida": False})
    await db.martin_avisos.insert_one({
        "id": str(uuid.uuid4()), "estado": "pendiente", "creado": _now(),
        "texto": f"Atención: la carpeta de {doc.get('nombre','')} quedó bloqueada por roots inconsistentes. {detalle}"})


async def auditoria_general():
    """Escanea todas las carpetas: sin root (inválidas) e inconsistencias de correspondencia."""
    sin_root, inconsistentes = [], []
    async for d in db.folders.find({}):
        probs = validar_roots(d)
        if any("Root del cliente principal" in p for p in probs):
            sin_root.append({"id": d.get("id"), "nombre": d.get("nombre", ""), "created_at": d.get("created_at", "")})
        elif probs:
            inconsistentes.append({"id": d.get("id"), "nombre": d.get("nombre", ""), "problemas": probs})
    return {"sin_root": sin_root, "inconsistentes": inconsistentes}


async def purgar_sin_root(ejecutado_por="sistema"):
    """Elimina las carpetas sin root (registros de prueba o errores). Se archivan en
    folders_papelera para trazabilidad — los archivos físicos/GridFS no se tocan."""
    aud = await auditoria_general()
    eliminadas = []
    for f in aud["sin_root"]:
        doc = await db.folders.find_one({"id": f["id"]})
        if not doc:
            continue
        doc["_papelera"] = {"motivo": "sin_root", "eliminada_at": _now(), "por": ejecutado_por}
        await db.folders_papelera.insert_one(doc)
        await db.folders.delete_one({"id": f["id"]})
        eliminadas.append(f["nombre"])
    if eliminadas:
        await db.dashai_eventos.insert_one({
            "tipo": "purga_sin_root", "fecha": _now(), "total": len(eliminadas),
            "carpetas": eliminadas, "por": ejecutado_por})
        logging.info(f"🌳 Purga sin root: {len(eliminadas)} carpeta(s) eliminadas (archivadas en papelera)")
    return {"eliminadas": len(eliminadas), "nombres": eliminadas,
            "inconsistentes_restantes": len(aud["inconsistentes"])}
