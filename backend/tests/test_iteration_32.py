"""Iteration 32: Bóveda ADN_CLIENTES_360 (Regla #66) + Supercarpeta V2 + Auditoria real."""
import os
import sys
import pytest
import requests
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL missing"
LOCAL_URL = "http://localhost:8001"

CARLOS_RUT = "13.820.383-2"


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"codigo": "administrador", "password": "141617575"}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    assert tok, f"token missing: {data}"
    return tok


@pytest.fixture(scope="session")
def broker_token():
    """Genera token no-admin usando auth.create_token del backend."""
    from auth import create_token
    return create_token("broker1", "D")


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def broker_headers(broker_token):
    return {"Authorization": f"Bearer {broker_token}"}


# ── ADN estado / certificación ──
def test_adn_estado(admin_headers):
    r = requests.get(f"{BASE_URL}/api/adn/estado", headers=admin_headers, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "certificacion" in data
    assert "Maserati" in data["certificacion"]
    assert "66" in data["certificacion"]
    assert data["registros"] >= 0


# ── Expediente 360 admin ──
def test_adn_expediente_admin_carlos(admin_headers):
    r = requests.get(f"{BASE_URL}/api/adn/expediente/{CARLOS_RUT}",
                     headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("acceso") == "360_completo"
    exp = data.get("expediente_360") or {}
    titular_nombre = ((exp.get("titular") or {}).get("nombre") or "").upper()
    assert "SALGADO" in titular_nombre, f"titular: {titular_nombre}"
    inm = ((exp.get("propiedad") or {}).get("inmobiliaria") or "").upper()
    assert "BOETSCH" in inm, f"inmobiliaria: {inm}"
    docs = exp.get("documentos") or []
    if docs:
        assert "link_boveda" in docs[0]


# ── Máscara de privacidad: broker (rol D) → piezas_modulo ──
def test_adn_expediente_broker_privacidad(broker_headers):
    r = requests.get(f"{BASE_URL}/api/adn/expediente/{CARLOS_RUT}",
                     headers=broker_headers, timeout=30)
    # Broker no dueño puede recibir 404 (cartera propia) o 200 con piezas_modulo
    assert r.status_code in (200, 404), r.text
    if r.status_code == 200:
        data = r.json()
        assert "piezas_modulo" in (data.get("acceso") or "")
        # NO debe tener datos financieros de codeudor
        assert "codeudor" not in data or not (data.get("codeudor") or {}).get("renta")
        # No debe traer expediente_360 completo con finanzas
        exp = data.get("expediente_360")
        assert exp is None, "broker no debe recibir expediente_360 completo"


def test_adn_buscar_broker_cartera_propia(broker_headers):
    r = requests.get(f"{BASE_URL}/api/adn/buscar?q=", headers=broker_headers, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("acceso") == "cartera_propia"


def test_adn_buscar_admin_global(admin_headers):
    r = requests.get(f"{BASE_URL}/api/adn/buscar?q=SALGADO", headers=admin_headers, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("acceso") == "global"


# ── Autorización volcar ──
def test_adn_volcar_broker_403(broker_headers):
    r = requests.post(f"{BASE_URL}/api/adn/volcar", headers=broker_headers, timeout=20)
    assert r.status_code == 403, r.text


# ── Succionar RUT inexistente ──
def test_adn_succionar_rut_inexistente(admin_headers):
    r = requests.post(f"{BASE_URL}/api/adn/succionar/99999999-9",
                      headers=admin_headers, timeout=30)
    assert r.status_code == 404, r.text


# ── Supercarpeta V2 ──
def test_supercarpeta_v2_fields(admin_headers):
    r = requests.get(f"{BASE_URL}/api/supercarpeta", headers=admin_headers, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    clientes = data.get("clientes") or []
    assert len(clientes) > 0, "no hay clientes en supercarpeta"
    for c in clientes:
        assert "estado_tasacion" in c
        assert "estudio_titulos" in c
        assert "detalle_reparos" in c
        assert "cesion" in c
    # Buscar Carlos con BOETSCH
    carlos = [c for c in clientes if "SALGADO" in (c.get("cliente") or "").upper()]
    if carlos:
        assert "BOETSCH" in (carlos[0].get("broker_origen") or "").upper(), \
            f"carlos broker_origen: {carlos[0].get('broker_origen')}"
    # Buscar CATALINA con reparos
    catalinas = [c for c in clientes if "CATALINA" in (c.get("cliente") or "").upper()
                 and "CASTILLO" in (c.get("cliente") or "").upper()]
    if catalinas:
        cat = catalinas[0]
        # Puede o no tener reparos según estado actual
        if cat.get("estudio_titulos") == "Con Reparos":
            assert cat.get("detalle_reparos"), "Catalina Con Reparos pero detalle vacío"


# ── Auditoría real (puede tardar; usar localhost) ──
def test_auditoria_real(admin_headers):
    # Ir directo a localhost para evitar 502 en gateway
    r = requests.post(f"{LOCAL_URL}/api/flujos/auditoria-real?limit=15&dias=2",
                      headers=admin_headers, timeout=180)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "correos_revisados" in data or "revisados" in data or data.get("ok") is not None
