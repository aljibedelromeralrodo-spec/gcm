"""Iteration 19 backend tests: aprobación cliente enriquecida, aprendizaje,
calibración de riesgo, portal firma VIP, Office→PDF, regresiones."""
import io
import os
import re
import pytest
import requests

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"
CLIENT = "Melisa Rivera"
MELISA_FID = "ed93f803-9dee-4da6-9e7f-fef3f5e6f6b9"


# -------- Aprobación Cliente: extracción enriquecida --------
def test_datos_cliente_confianza_y_fuentes():
    r = requests.get(f"{API}/aprobacion-cliente/datos-cliente",
                     params={"nombre": CLIENT}, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert isinstance(d.get("confianza"), dict), "falta confianza dict"
    assert isinstance(d.get("fuentes"), dict), "falta fuentes dict"
    for campo in ("email", "rut"):
        assert campo in d["confianza"]
        if d.get(campo):
            assert d["confianza"][campo] in ("alta", "dudosa"), d["confianza"][campo]
    print("datos-cliente:", {k: d.get(k) for k in ("email", "rut", "telefono")})
    print("confianza:", d["confianza"])
    print("fuentes:", d["fuentes"])


def test_datos_cliente_nombre_corto_400():
    r = requests.get(f"{API}/aprobacion-cliente/datos-cliente",
                     params={"nombre": "xx"}, timeout=30)
    assert r.status_code == 400


# -------- Aprendizaje corrección --------
def test_aprendizaje_correccion_ok_y_aplica_patron():
    payload = {"cliente": CLIENT, "campo": "telefono",
               "valor_correcto": "+56 9 1234 5678", "valor_extraido": ""}
    r = requests.post(f"{API}/aprendizaje/correccion", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("ok") is True
    assert j.get("patrones_totales", 0) >= 1
    # aplica al siguiente GET
    d = requests.get(f"{API}/aprobacion-cliente/datos-cliente",
                     params={"nombre": CLIENT}, timeout=60).json()
    assert d.get("telefono") == "+56 9 1234 5678", d
    assert d["confianza"]["telefono"] == "alta"


def test_aprendizaje_correccion_campo_invalido_400():
    r = requests.post(f"{API}/aprendizaje/correccion",
                      json={"cliente": CLIENT, "campo": "foo", "valor_correcto": "x"},
                      timeout=30)
    assert r.status_code == 400


# -------- Calibración de riesgo --------
def test_calibracion_estado():
    r = requests.get(f"{API}/calibracion/estado", timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("mensaje", "").startswith("He calibrado mis criterios"), d.get("mensaje")
    assert d.get("respuestas_mesa", 0) > 0, d
    assert "asertividad" in d
    assert isinstance(d.get("detalle"), list)
    if d["detalle"]:
        row = d["detalle"][0]
        for k in ("prediccion", "mesa", "acierto", "cliente"):
            assert k in row, row


# -------- Portal Firma VIP --------
@pytest.fixture(scope="module")
def firma_token():
    r = requests.post(f"{API}/firma/generar-link", json={"cliente": CLIENT}, timeout=30)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("url") and j.get("whatsapp")
    assert "/api/firma/" in j["url"]
    return j["token"]


def test_firma_portal_html(firma_token):
    # sin autenticación
    r = requests.get(f"{API}/firma/{firma_token}", timeout=30)
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    html = r.text
    assert "Bienvenido a su Firma de" in html
    assert "Validar Identidad y Firmar con Clave Única" in html
    assert 'property="og:image"' in html


def test_firma_og_png(firma_token):
    r = requests.get(f"{API}/firma/{firma_token}/og.png", timeout=30)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("image/png")
    # verify 1200x630
    from PIL import Image
    img = Image.open(io.BytesIO(r.content))
    assert img.size == (1200, 630), img.size


def test_firma_token_invalido_404():
    r = requests.get(f"{API}/firma/zzzzzzzzzzzz_invalid", timeout=30)
    assert r.status_code == 404


# -------- Office → PDF --------
def _build_docx():
    from docx import Document
    doc = Document()
    doc.add_paragraph("TEST iter19 conversión docx→pdf")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_upload_docx_se_convierte_a_pdf():
    fid = MELISA_FID
    try:
        raw = _build_docx()
    except Exception:
        pytest.skip("python-docx no disponible")
    filename = "TEST_iter19_office.docx"
    files = {"file": (filename, raw,
                      "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    r = requests.post(f"{API}/clientes/folders/{fid}/upload-file", files=files, timeout=120)
    assert r.status_code == 200, r.text
    j = r.json()
    saved = j.get("saved", "")
    print("saved:", saved)
    assert saved.lower().endswith(".pdf"), f"esperaba .pdf, saved={saved}"
    # cleanup
    dr = requests.post(f"{API}/clientes/folders/{fid}/delete-file",
                       json={"file_path": saved}, timeout=30)
    assert dr.status_code == 200, dr.text
    assert dr.json().get("ok") is True


# -------- Regresiones --------
@pytest.mark.parametrize("ep", [
    "/salud/estado",
    "/rescate/pendientes",
    "/gastos-operacionales/log",
    "/seguimiento/clientes",
])
def test_regresiones_200(ep):
    r = requests.get(f"{API}{ep}", timeout=60)
    assert r.status_code == 200, f"{ep} -> {r.status_code}: {r.text[:200]}"
