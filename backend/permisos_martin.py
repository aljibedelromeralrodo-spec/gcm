"""PermisosMartinV2 — permisos totales con 2 frenos (email/mesa) y log obligatorio."""
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import folders_service as fsvc

PERMISOS = {
    "puede": [
        "fs.mkdir", "fs.rename", "fs.move", "fs.copy",
        "bunker.clasificar", "bunker.separarRUT", "bunker.juntarRUT",
        "pdf.generar", "combinado.generar", "informe.generar",
    ],
    "requiere_confirmacion": ["email.enviar", "mesa.enviar"],
    "prohibido": ["fs.deletePermanente", "bunker.purge"],
    "mensaje_bloqueo": "¿Lo envío? / ¿Lo envío a mesa?",
}

PAPELERA = Path(__file__).parent / "storage" / "papelera"

_PREFIJOS_CONOCIDOS = re.compile(
    r"^(01_Cedula|02_Liquidaciones|02_Impuesto_Renta|03_Certificado_AFP|"
    r"03_Resumen_Impuestos|04_CMF)_", re.I)


def _sin_prefijo(fn):
    """Quita el prefijo de nomenclatura para releer la categoría real del nombre.
    Primero los prefijos completos conocidos (evita dejar 'Impuestos_' colgando)."""
    limpio = _PREFIJOS_CONOCIDOS.sub("", fn)
    if limpio != fn:
        return limpio
    return re.sub(r"^\d{2}_[A-Za-z_]*?_", "", fn)


def permitido(accion):
    if accion in PERMISOS["prohibido"]:
        return "prohibido"
    if accion in PERMISOS["requiere_confirmacion"]:
        return "confirmar"
    return "libre"


def _now():
    return datetime.now(timezone.utc).isoformat()


async def log_accion(db, accion, origen, destino, rollback_path="", usuario="martin"):
    await db.logs_permisos.insert_one({
        "usuario": usuario, "accion": accion, "origen": origen,
        "destino": destino, "timestamp": _now(), "rollback_path": rollback_path})


def a_papelera(path):
    """Nada se borra: mover a papelera con timestamp (fs.deletePermanente prohibido).
    Se marca el origen en el búnker (soft-delete) para que el cloud sync no lo resucite."""
    import bunker
    PAPELERA.mkdir(parents=True, exist_ok=True)
    dest = PAPELERA / f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{Path(path).name}"
    shutil.move(str(path), str(dest))
    bunker.eliminar_bg(str(path))
    return str(dest)


def _mover(base, rel_origen, sub_destino, nuevo_nombre=None):
    import bunker
    src = base / rel_origen
    fn = nuevo_nombre or src.name
    dest_dir = base / sub_destino if sub_destino else base
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / fn
    if dest.exists():
        a_papelera(src)
        return None
    shutil.move(str(src), str(dest))
    bunker.eliminar_bg(str(src))
    bunker.subir_archivo_bg(dest)
    return dest.relative_to(base).as_posix()


async def revisar_carpeta(db, folder):
    """Corrige clasificación de UNA carpeta según protocolo: archivos en raíz van a su
    subcarpeta de categoría; CODEUDOR_ suelto va a 05_codeudor. Solo movimientos seguros;
    las discrepancias en subcarpetas ya clasificadas se informan sin mover."""
    nombre = folder.get("nombre", "")
    base = fsvc.folder_dir(nombre)
    movidos, sospechas = [], []
    for a in fsvc.scan_archivos(nombre):
        fn, sub, rel = a["nombre"], a["subfolder"], a["ruta"]
        if fsvc.es_combinado(fn) or sub.startswith(("00_combinados", "07_estudio_titulo")):
            continue
        if fn.upper().startswith("CODEUDOR_"):
            if not sub.startswith("05_codeudor"):
                nuevo = _mover(base, rel, "05_codeudor")
                if nuevo:
                    movidos.append({"de": rel, "a": nuevo})
                    await log_accion(db, "fs.move", f"clientes/{nombre}/{rel}",
                                     f"clientes/{nombre}/{nuevo}", rollback_path=rel)
            continue
        if sub == "":
            cat = fsvc.cat_de_texto(fn)
            destino = fsvc.CAT_A_SUBFOLDER.get(cat, "") if cat != "extras" else ""
            if destino:
                nuevo = _mover(base, rel, destino, fsvc.safe_name(fsvc.nombre_con_prefijo(fn, cat)))
                if nuevo:
                    movidos.append({"de": rel, "a": nuevo})
                    await log_accion(db, "bunker.clasificar", f"clientes/{nombre}/{rel}",
                                     f"clientes/{nombre}/{nuevo}", rollback_path=rel)
        else:
            cat_sub = fsvc.SUBFOLDER_A_CAT.get(sub.split("/")[0], "")
            fn_limpio = _sin_prefijo(fn)
            cat_texto = fsvc.cat_de_texto(fn_limpio)
            if (cat_sub and cat_texto not in ("extras", cat_sub)
                    and fsvc.CAT_A_SUBFOLDER.get(cat_texto, "") != sub.split("/")[0]):
                sospechas.append({"archivo": rel, "clasificado_como": cat_sub,
                                  "parece": cat_texto})
    return {"carpeta": nombre, "movidos": movidos, "sospechas": sospechas}


async def separar_codeudor_en_carpeta(db, folder_id, nuevo_nombre, patron="CODEUDOR_"):
    """Separación literal en 2 carpetas (caso Berríos): mueve los archivos del codeudor
    a una carpeta nueva propia, quitando el prefijo CODEUDOR_ y reclasificando."""
    import uuid
    folder = await db.folders.find_one({"id": folder_id})
    if not folder:
        return {"error": "carpeta origen no encontrada"}
    origen_nombre = folder.get("nombre", "")
    base_origen = fsvc.folder_dir(origen_nombre)
    destino = await db.folders.find_one({"nombre": nuevo_nombre})
    if not destino:
        destino = {"id": str(uuid.uuid4()), "nombre": nuevo_nombre, "rut": "",
                   "archivos": [], "created_at": _now(), "origen": "separacion_martin",
                   "separado_de": origen_nombre}
        await db.folders.insert_one(dict(destino))
        fsvc.folder_dir(nuevo_nombre).mkdir(parents=True, exist_ok=True)
        await log_accion(db, "fs.mkdir", f"clientes/{origen_nombre}",
                         f"clientes/{nuevo_nombre}")
    movidos = []
    for a in fsvc.scan_archivos(origen_nombre):
        fn, rel = a["nombre"], a["ruta"]
        if not fn.upper().startswith(patron.upper()):
            continue
        raw = (base_origen / rel).read_bytes()
        fn_limpio = re.sub(r"(?i)^codeudor_", "", fn)
        nuevo_rel = fsvc.guardar_archivo(nuevo_nombre, fn_limpio, raw)
        rollback = a_papelera(base_origen / rel)
        movidos.append({"de": f"{origen_nombre}/{rel}", "a": f"{nuevo_nombre}/{nuevo_rel}"})
        await log_accion(db, "bunker.separarRUT", f"clientes/{origen_nombre}/{rel}",
                         f"clientes/{nuevo_nombre}/{nuevo_rel}", rollback_path=rollback)
    return {"carpeta_origen": origen_nombre, "carpeta_nueva": nuevo_nombre,
            "movidos": movidos}


async def aplicar_correcciones_clasificacion(db):
    """LUZ VERDE del usuario: aplica las sospechas de clasificación detectadas en modo
    nocturno — mueve cada archivo a la subcarpeta de su categoría real, renombrando con
    el prefijo correcto. NO toca combinados, estudio_titulo ni 05_codeudor."""
    reporte = {"carpetas": [], "total_corregidos": 0, "omitidos_codeudor": 0}
    async for f in db.folders.find({}, {"id": 1, "nombre": 1}):
        nombre = f.get("nombre", "")
        base = fsvc.folder_dir(nombre)
        corregidos = []
        try:
            for a in fsvc.scan_archivos(nombre):
                fn, sub, rel = a["nombre"], a["subfolder"], a["ruta"]
                if fsvc.es_combinado(fn) or sub == "" or fn.upper().startswith("CODEUDOR_"):
                    continue
                if sub.startswith(("00_combinados", "07_estudio_titulo")):
                    continue
                cat_sub = fsvc.SUBFOLDER_A_CAT.get(sub.split("/")[0], "")
                fn_limpio = _sin_prefijo(fn)
                cat_texto = fsvc.cat_de_texto(fn_limpio)
                if not cat_sub or cat_texto in ("extras", cat_sub):
                    continue
                if cat_sub == "codeudor":
                    reporte["omitidos_codeudor"] += 1
                    continue
                destino = fsvc.CAT_A_SUBFOLDER.get(cat_texto, "")
                if not destino or destino == sub.split("/")[0]:
                    continue
                nuevo = _mover(base, rel, destino,
                               fsvc.safe_name(fsvc.nombre_con_prefijo(fn_limpio, cat_texto)))
                if nuevo:
                    corregidos.append({"de": rel, "a": nuevo, "categoria": cat_texto})
                    await log_accion(db, "bunker.clasificar", f"clientes/{nombre}/{rel}",
                                     f"clientes/{nombre}/{nuevo}", rollback_path=rel)
        except Exception as e:
            reporte["carpetas"].append({"carpeta": nombre, "error": str(e)[:120]})
            continue
        if corregidos:
            reporte["carpetas"].append({"carpeta": nombre, "corregidos": corregidos})
            reporte["total_corregidos"] += len(corregidos)
    await log_accion(db, "informe.generar", "orden:aplicar-correcciones",
                     f"corregidos={reporte['total_corregidos']}")
    import bunker
    bunker.sync_en_background()
    return reporte


async def mover_docs_a_carpeta(db, nombre_origen, nombre_destino, rutas):
    """Mueve archivos puntuales de una carpeta cliente a otra (mismo subfolder),
    con log y rollback vía papelera. Caso: liquidaciones de Fabián Escalante que
    quedaron mezcladas en Felipe De La Cuadra."""
    origen = await db.folders.find_one({"nombre": nombre_origen})
    destino = await db.folders.find_one({"nombre": nombre_destino})
    if not origen or not destino:
        return {"error": "carpeta origen o destino no encontrada"}
    import bunker
    base_origen = fsvc.folder_dir(nombre_origen)
    disponibles = {a["ruta"]: a for a in fsvc.scan_archivos(nombre_origen)}
    movidos, no_encontrados = [], []
    for rel in rutas:
        a = disponibles.get(rel)
        if not a:
            no_encontrados.append(rel)
            continue
        raw = (base_origen / rel).read_bytes()
        nuevo_rel = fsvc.guardar_archivo(nombre_destino, a["nombre"], raw,
                                         subfolder=a["subfolder"])
        bunker.subir_archivo_bg(fsvc.folder_dir(nombre_destino) / nuevo_rel)
        rollback = a_papelera(base_origen / rel)
        movidos.append({"de": f"{nombre_origen}/{rel}", "a": f"{nombre_destino}/{nuevo_rel}"})
        await log_accion(db, "fs.move", f"clientes/{nombre_origen}/{rel}",
                         f"clientes/{nombre_destino}/{nuevo_rel}", rollback_path=rollback)
    bunker.sync_en_background()
    return {"origen": nombre_origen, "destino": nombre_destino,
            "movidos": movidos, "no_encontrados": no_encontrados}


async def ejecutar_orden_revision(db, separaciones=None):
    """Orden: 'revisa todas las carpetas, separa RUTs mezclados y corrige clasificación'."""
    reporte = {"separaciones": [], "carpetas": [], "total_movidos": 0, "total_sospechas": 0}
    for s in separaciones or []:
        r = await separar_codeudor_en_carpeta(db, s["folder_id"], s["nuevo_nombre"],
                                              s.get("patron", "CODEUDOR_"))
        reporte["separaciones"].append(r)
    async for f in db.folders.find({}, {"id": 1, "nombre": 1}):
        try:
            r = await revisar_carpeta(db, f)
            if r["movidos"] or r["sospechas"]:
                reporte["carpetas"].append(r)
                reporte["total_movidos"] += len(r["movidos"])
                reporte["total_sospechas"] += len(r["sospechas"])
        except Exception as e:
            reporte["carpetas"].append({"carpeta": f.get("nombre", ""), "error": str(e)[:120]})
    await log_accion(db, "informe.generar", "orden:revisar-carpetas",
                     f"movidos={reporte['total_movidos']} sospechas={reporte['total_sospechas']}")
    import bunker
    bunker.sync_en_background()
    return reporte
