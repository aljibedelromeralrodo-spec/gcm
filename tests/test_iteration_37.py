"""Iteration 37 — Backend tests for Supercarpeta Cards view feature.

Covers:
- GET /api/supercarpeta?mes=2026-08 exposes 'notas' list per client (with texto/por/en/hito)
- POST /api/supercarpeta/nota/{fid} with valid payload -> 200, note appears in next GET
- POST /api/supercarpeta/nota/{fid} validation errors (invalid hito, empty texto) -> 400
- Client CARLOS SALGADO gets a real (persisted) 'nota de prueba QA' as per QA instructions
"""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://risk-assess-17.preview.emergentagent.com").rstrip("/")
MES = "2026-08"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"rut": "administrador", "password": "141617575"}, timeout=20)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def clientes(headers):
    r = requests.get(f"{BASE_URL}/api/supercarpeta", params={"mes": MES}, headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    lst = data.get("clientes") or data.get("items") or data
    assert isinstance(lst, list) and len(lst) > 0
    return lst


def test_supercarpeta_returns_clientes(clientes):
    assert len(clientes) >= 10
    # each cliente must have id and cliente name
    for c in clientes:
        assert "id" in c
        assert "cliente" in c


def test_notas_field_present_on_each_cliente(clientes):
    """Every cliente should have a 'notas' list (may be empty)."""
    for c in clientes:
        assert "notas" in c, f"Cliente {c.get('cliente')} missing 'notas' key"
        assert isinstance(c["notas"], list), f"'notas' should be list on {c.get('cliente')}"


def test_ruben_zabala_has_note(clientes):
    """Existing seed note: RUBEN ZABALA has 1 nota 'falta promesa' in hito 'estudio'."""
    ruben = next((c for c in clientes if "ZABALA" in (c.get("cliente") or "").upper()), None)
    assert ruben is not None, "RUBEN ZABALA not found"
    notas = ruben.get("notas") or []
    assert len(notas) >= 1, f"RUBEN ZABALA should have >=1 nota, got {len(notas)}"
    # Verify the shape of the note
    n = notas[0]
    for k in ("texto", "en", "hito"):
        assert k in n, f"Nota missing field {k}: {n}"


def test_nota_invalid_hito_returns_400(headers, clientes):
    fid = clientes[0]["id"]
    r = requests.post(f"{BASE_URL}/api/supercarpeta/nota/{fid}",
                      json={"hito": "hito_inexistente_xyz", "texto": "algo"},
                      headers=headers, timeout=15)
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"


def test_nota_texto_vacio_returns_400(headers, clientes):
    fid = clientes[0]["id"]
    r = requests.post(f"{BASE_URL}/api/supercarpeta/nota/{fid}",
                      json={"hito": "tasacion", "texto": "   "},
                      headers=headers, timeout=15)
    assert r.status_code == 400, f"Expected 400 empty text, got {r.status_code}: {r.text}"


def test_add_nota_to_carlos_salgado_and_verify_persistence(headers):
    """QA requirement: add 'nota de prueba QA' to CARLOS SALGADO and DO NOT delete."""
    # Fetch first to get carlos id
    r = requests.get(f"{BASE_URL}/api/supercarpeta", params={"mes": MES}, headers=headers, timeout=30)
    assert r.status_code == 200
    data = r.json()
    lst = data.get("clientes") or data
    carlos = next((c for c in lst if "SALGADO" in (c.get("cliente") or "").upper()), None)
    assert carlos is not None, "CARLOS SALGADO not found in mes 2026-08"
    fid = carlos["id"]
    notas_before = len(carlos.get("notas") or [])

    # Post the note
    payload = {"hito": "tasacion", "texto": "nota de prueba QA"}
    r2 = requests.post(f"{BASE_URL}/api/supercarpeta/nota/{fid}",
                       json=payload, headers=headers, timeout=15)
    assert r2.status_code == 200, f"Nota post failed: {r2.status_code} {r2.text}"
    j = r2.json()
    assert j.get("ok") is True
    assert j.get("nota", {}).get("texto") == "nota de prueba QA"

    # Verify via next GET
    r3 = requests.get(f"{BASE_URL}/api/supercarpeta", params={"mes": MES}, headers=headers, timeout=30)
    lst2 = r3.json().get("clientes") or r3.json()
    carlos2 = next((c for c in lst2 if c["id"] == fid), None)
    assert carlos2 is not None
    notas_after = carlos2.get("notas") or []
    assert len(notas_after) == notas_before + 1, \
        f"Expected {notas_before+1} notas, got {len(notas_after)}"
    # Check the new note is present
    found = any(n.get("texto") == "nota de prueba QA" and n.get("hito") == "tasacion"
                for n in notas_after)
    assert found, f"New nota not found in GET after POST. Notas: {notas_after}"
