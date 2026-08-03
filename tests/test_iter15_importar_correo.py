"""Iter15 — Tests for /api/correos/buscar and /api/correos/importar (importable from ALL modules)."""
import os
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://risk-assess-17.preview.emergentagent.com").rstrip("/")
TIMEOUT = 90
SET_CLAUDIA_ID = "364f70bf-25dc-4101-b6e8-764739ee8c71"


@pytest.fixture(scope="module")
def correos_zurita():
    r = requests.get(f"{BASE}/api/correos/buscar", params={"q": "zurita"}, timeout=TIMEOUT)
    assert r.status_code == 200, f"buscar zurita -> {r.status_code}: {r.text[:200]}"
    data = r.json()
    assert "correos" in data
    return data["correos"]


# ---------- GET /api/correos/buscar ----------
def test_buscar_minimo_3_letras():
    r = requests.get(f"{BASE}/api/correos/buscar", params={"q": "ab"}, timeout=30)
    assert r.status_code == 400


def test_buscar_zurita_retorna_lista(correos_zurita):
    assert isinstance(correos_zurita, list)
    # puede estar vacío en el buzón, pero si hay correos verificamos shape
    if correos_zurita:
        c = correos_zurita[0]
        for k in ("subject", "from", "date", "cuenta", "message_id"):
            assert k in c, f"Falta campo {k} en respuesta buscar: {c}"


# ---------- POST /api/correos/importar ----------
def test_importar_sin_mids_400():
    r = requests.post(f"{BASE}/api/correos/importar",
                      json={"destino": "carpeta", "nombre": "CLAUDIA ANDREA ZURITA SOTO", "message_ids": []},
                      timeout=30)
    assert r.status_code == 400


def test_importar_set_credito_dedupe(correos_zurita):
    if not correos_zurita:
        pytest.skip("Buzón sin resultados 'zurita'")
    mid = next((c["message_id"] for c in correos_zurita if c.get("message_id")), None)
    if not mid:
        pytest.skip("No message_id disponible")
    payload = {"destino": "set_credito", "destino_id": SET_CLAUDIA_ID, "message_ids": [mid]}
    r = requests.post(f"{BASE}/api/correos/importar", json=payload, timeout=180)
    assert r.status_code == 200, f"importar set_credito -> {r.status_code}: {r.text[:300]}"
    data = r.json()
    assert data.get("ok") is True
    assert "guardados" in data
    # Reimportar el mismo correo → dedupe: no debe duplicar
    r2 = requests.post(f"{BASE}/api/correos/importar", json=payload, timeout=180)
    assert r2.status_code == 200
    guardados2 = r2.json().get("guardados", [])
    assert guardados2 == [], f"Dedupe fallo: {guardados2}"


def test_importar_carpeta_por_nombre(correos_zurita):
    if not correos_zurita:
        pytest.skip("Buzón sin resultados 'zurita'")
    mid = next((c["message_id"] for c in correos_zurita if c.get("message_id")), None)
    if not mid:
        pytest.skip("No message_id disponible")
    payload = {"destino": "carpeta", "nombre": "CLAUDIA ANDREA ZURITA SOTO", "message_ids": [mid]}
    r = requests.post(f"{BASE}/api/correos/importar", json=payload, timeout=180)
    assert r.status_code == 200, f"importar carpeta -> {r.status_code}: {r.text[:300]}"
    data = r.json()
    assert data.get("ok") is True


def test_importar_estudio_titulo_subfolder(correos_zurita):
    if not correos_zurita:
        pytest.skip("Buzón sin resultados 'zurita'")
    mid = next((c["message_id"] for c in correos_zurita if c.get("message_id")), None)
    if not mid:
        pytest.skip("No message_id disponible")
    payload = {"destino": "estudio_titulo", "nombre": "CLAUDIA ANDREA ZURITA SOTO", "message_ids": [mid]}
    r = requests.post(f"{BASE}/api/correos/importar", json=payload, timeout=180)
    assert r.status_code == 200, f"importar estudio_titulo -> {r.status_code}: {r.text[:300]}"
    data = r.json()
    assert data.get("ok") is True
    for rel in data.get("guardados", []):
        assert "07_estudio_titulo" in rel, f"Archivo NO en subfolder correcto: {rel}"


# ---------- Regresión rápida ----------
def test_forzar_folder_sigue_existiendo():
    # sin clave → 403
    r = requests.post(f"{BASE}/api/clientes/folders/forzar", json={"nombre": "test", "clave": "xx"}, timeout=30)
    assert r.status_code == 403
