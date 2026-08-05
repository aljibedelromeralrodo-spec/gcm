"""Regresión backend BLINDAJE TOTAL (Central Mutuos / Predictor).

Verifica endpoints núcleo tras la reconstrucción técnica:
  - LEY DEL RUT en upload (rechaza RUT ajeno / Gastos Operacionales)
  - Búnker GridFS (colección bunker.files poblada)
  - Motor 24/7 (procesamiento auto status)
  - Buzón de Rescate incluye entradas 'LEY DEL RUT'
  - Endpoints regresión (plantilla, log aprobación, log estudio de título, salud)
"""
import io
import os
import re
import pytest
import requests
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback: leer /app/frontend/.env
    with open("/app/frontend/.env") as f:
        for ln in f:
            if ln.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = ln.split("=", 1)[1].strip().rstrip("/")

API = f"{BASE_URL}/api"

WERNER_NOMBRE = "WERNER ALEXANDER JARA ROJAS"
WERNER_RUT = "20.792.369-9"


# ---------- helpers ----------
def _pdf_bytes(texto: str) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 750
    for line in texto.split("\n"):
        c.drawString(50, y, line)
        y -= 20
    c.save()
    return buf.getvalue()


@pytest.fixture(scope="module")
def s():
    ses = requests.Session()
    ses.headers.update({"Accept": "application/json"})
    return ses


# ---------- Motor 24/7 ----------
def test_procesamiento_auto_status(s):
    r = s.get(f"{API}/procesamiento/auto/status", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("enabled") is True, f"motor 24/7 debe estar enabled: {data}"


# ---------- Listado de carpetas ----------
def test_clientes_folders_incluye_werner(s):
    r = s.get(f"{API}/clientes/folders", timeout=90)
    assert r.status_code == 200, r.text
    data = r.json()
    folders = data if isinstance(data, list) else data.get("folders", data.get("items", []))
    assert isinstance(folders, list) and folders, "esperaba lista de folders"
    nombres = " | ".join(str((f or {}).get("nombre", "")) for f in folders)
    assert WERNER_NOMBRE in nombres, f"WERNER no en la lista. muestra={nombres[:400]}"


# ---------- Aprobación cliente: listado con excluidos_rut ----------
def test_aprobacion_archivos_werner(s):
    r = s.get(f"{API}/aprobacion-cliente/archivos",
              params={"cliente": WERNER_NOMBRE}, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "excluidos_rut" in data, f"falta campo excluidos_rut: {data.keys()}"
    archivos = data.get("archivos", [])
    tipos = sorted({a.get("tipo") for a in archivos})
    # deben aparecer los 2 tipos: carta_aprobacion y simulacion_ajustada
    assert "carta_aprobacion" in tipos and "simulacion_ajustada" in tipos, (
        f"esperaba carta + simulación. tipos={tipos} archivos={[a.get('nombre') for a in archivos]}")
    assert len(archivos) == 2, f"esperaba 2 archivos, obtuvo {len(archivos)}"


# ---------- REGLA DE ORO 0586 / DETECTOR SIMULACION ----------
def test_upload_rechaza_gastos_operacionales(s):
    pdf = _pdf_bytes("SIMULACION CREDITICIA\nGASTOS OPERACIONALES\nMonto: UF 1000")
    files = {"file": ("fake_sim.pdf", pdf, "application/pdf")}
    data = {"cliente": WERNER_NOMBRE}
    r = s.post(f"{API}/aprobacion-cliente/upload", data=data, files=files, timeout=90)
    assert r.status_code == 422, f"esperaba 422, obtuvo {r.status_code}: {r.text}"
    body = r.json()
    detail = str(body.get("detail", ""))
    assert "no es una Simulación Ajustada" in detail or "Simulaci" in detail, (
        f"mensaje inesperado: {detail}")


# ---------- LEY DEL RUT: upload con RUT correcto y luego DELETE ----------
def test_upload_werner_rut_correcto_y_delete(s):
    pdf = _pdf_bytes(
        "SIMULACION CREDITICIA AJUSTADA\n"
        f"Cliente: {WERNER_NOMBRE}\n"
        f"RUT: {WERNER_RUT}\n"
        "Dividendo: UF 12,5\nPlazo: 20 años"
    )
    files = {"file": ("TEST_regresion_werner.pdf", pdf, "application/pdf")}
    data = {"cliente": WERNER_NOMBRE}
    r = s.post(f"{API}/aprobacion-cliente/upload", data=data, files=files, timeout=120)
    assert r.status_code == 200, f"upload esperaba 200: {r.status_code} {r.text}"
    body = r.json()
    ruta = body.get("ruta")
    assert ruta, f"no vino ruta en la respuesta: {body}"
    # cleanup
    rd = s.delete(f"{API}/aprobacion-cliente/archivo",
                  params={"ruta": ruta, "origen": body.get("origen", "autocorreo"),
                          "cliente": WERNER_NOMBRE},
                  timeout=30)
    assert rd.status_code == 200, f"DELETE falló: {rd.status_code} {rd.text}"


# ---------- Buzón de Rescate con LEY DEL RUT ----------
def test_rescate_pendientes_incluye_ley_del_rut(s):
    r = s.get(f"{API}/rescate/pendientes", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    items = data if isinstance(data, list) else data.get("items", data.get("pendientes", []))
    assert isinstance(items, list) and items, "esperaba lista no vacía en rescate"
    encontrados = [it for it in items
                   if re.search(r"LEY DEL RUT", str(it.get("motivo", "")), re.I)]
    assert encontrados, f"no hay entradas 'LEY DEL RUT' en rescate: {items[:2]}"


# ---------- Panel de salud ----------
def test_salud_estado(s):
    r = s.get(f"{API}/salud/estado", timeout=30)
    assert r.status_code == 200, f"/salud/estado: {r.status_code} {r.text[:200]}"


# ---------- Búnker GridFS en MongoDB ----------
def test_bunker_gridfs_mirror():
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")
    if not db_name:
        with open("/app/backend/.env") as f:
            for ln in f:
                if ln.startswith("DB_NAME"):
                    db_name = ln.split("=", 1)[1].strip().strip('"').strip("'")
    cli = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
    db = cli[db_name]
    coll_names = db.list_collection_names()
    assert "bunker.files" in coll_names, f"no existe colección bunker.files. cols={coll_names[:20]}"
    n = db["bunker.files"].count_documents({})
    # umbral tolerante (~998 esperados)
    assert n > 500, f"bunker.files tiene solo {n} docs (esperaba ~998)"


# ---------- Regresión: endpoints simples ----------
def test_aprobacion_plantilla(s):
    r = s.get(f"{API}/aprobacion-cliente/plantilla",
              params={"cliente": WERNER_NOMBRE}, timeout=30)
    assert r.status_code == 200, r.text


def test_aprobacion_log(s):
    r = s.get(f"{API}/aprobacion-cliente/log", timeout=30)
    assert r.status_code == 200, r.text


def test_estudio_titulo_log(s):
    r = s.get(f"{API}/estudio-titulo/log", timeout=30)
    assert r.status_code == 200, r.text
