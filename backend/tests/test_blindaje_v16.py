"""Tests V16 Blindaje de Correos — protocolos, autorizaciones, dashboard, seguridad."""
import os
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE:
    # fallback to frontend/.env value if not exported
    with open("/app/frontend/.env") as f:
        for l in f:
            if l.startswith("REACT_APP_BACKEND_URL"):
                BASE = l.split("=", 1)[1].strip()
BASE = BASE.rstrip("/")


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"rut": "administrador", "password": "141617575"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def broker_token():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"rut": "broker", "password": "Broker2026"}, timeout=30)
    if r.status_code == 200:
        return r.json().get("token")
    return None


# ── Protocolos ─────────────────────────────────────────
def test_protocolos_devuelve_5(headers):
    r = requests.get(f"{BASE}/api/blindaje/protocolos", headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    ps = r.json().get("protocolos", [])
    ids = {p["id"] for p in ps}
    assert {"dependiente_simple", "independiente", "mixto", "con_codeudor", "con_licencia_medica"} <= ids
    dep = next(p for p in ps if p["id"] == "dependiente_simple")
    req = set(dep["documentos_requeridos"])
    assert {"liquidacion_1", "liquidacion_2", "liquidacion_3", "liquidacion_4", "liquidacion_5", "liquidacion_6"} <= req
    assert {"certificado_antiguedad", "cedula", "cotizaciones_12", "contrato_trabajo"} <= req
    assert "carpeta_tributaria_2_anos" in set(dep["nunca_pedir"])
    ind = next(p for p in ps if p["id"] == "independiente")
    assert not any(x.startswith("liquidacion_") for x in ind["documentos_requeridos"])


# ── Seguridad ──────────────────────────────────────────
def test_sin_token_devuelve_401_403():
    for path in ["/api/blindaje/protocolos", "/api/blindaje/autorizaciones", "/api/blindaje/dashboard"]:
        r = requests.get(f"{BASE}{path}", timeout=20)
        assert r.status_code in (401, 403), f"{path} → {r.status_code}"


def test_broker_no_admin_devuelve_403(broker_token):
    if not broker_token:
        pytest.skip("broker login no disponible")
    h = {"Authorization": f"Bearer {broker_token}"}
    r = requests.get(f"{BASE}/api/blindaje/protocolos", headers=h, timeout=20)
    assert r.status_code in (401, 403)


# ── Autorizaciones + Dashboard ─────────────────────────
@pytest.fixture(scope="module")
def autorizaciones(headers):
    r = requests.get(f"{BASE}/api/blindaje/autorizaciones", headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def test_autorizaciones_kpis_y_pendientes(autorizaciones):
    assert "kpis" in autorizaciones and "pendientes" in autorizaciones
    ps = autorizaciones["pendientes"]
    assert len(ps) >= 2, f"esperaba >=2 pendientes sintéticas, hay {len(ps)}"
    nombres = " ".join((p.get("cliente_nombre") or "") for p in ps).upper()
    assert "CLIENTE PRUEBA V16" in nombres or "11.111.111" in " ".join(p.get("cliente_rut", "") for p in ps)
    assert "PRUEBA AUTORIZAR SEGURO" in nombres or "22.222.222" in " ".join(p.get("cliente_rut", "") for p in ps)


def test_dashboard_estructura(headers):
    r = requests.get(f"{BASE}/api/blindaje/dashboard", headers=headers, timeout=45)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "kpis" in data and "log" in data and "cola" in data and "checklist" in data
    assert len(data["checklist"]) == 7


def test_carpeta_caso(headers, autorizaciones):
    caso_id = None
    for p in autorizaciones["pendientes"]:
        if p.get("caso_id"):
            caso_id = p["caso_id"]
            break
    assert caso_id, "ninguna pendiente tiene caso_id"
    r = requests.get(f"{BASE}/api/blindaje/casos/{caso_id}/carpeta", headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    docs = r.json().get("documentos", [])
    assert len(docs) > 0
    assert all("estado" in d and "label" in d for d in docs)


def _find_by_rut(pendientes, rut_prefix):
    rp = rut_prefix.replace(".", "").replace("-", "").lower()
    for p in pendientes:
        r = (p.get("cliente_rut") or "").replace(".", "").replace("-", "").lower()
        if r.startswith(rp):
            return p
    return None


def test_rechazar_cliente_prueba_v16(headers, autorizaciones):
    p = _find_by_rut(autorizaciones["pendientes"], "11111111")
    if not p:
        pytest.skip("no hay pendiente RUT 11.111.111-1")
    aid = p["id"]
    r = requests.post(f"{BASE}/api/blindaje/autorizaciones/{aid}/rechazar",
                      headers=headers, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True
    # Verificar estado
    r2 = requests.get(f"{BASE}/api/blindaje/autorizaciones", headers=headers, timeout=30)
    still = [x for x in r2.json()["pendientes"] if x["id"] == aid]
    assert not still, "sigue en pendientes tras rechazar"


def test_autorizar_prueba_autorizar_seguro(headers, autorizaciones):
    p = _find_by_rut(autorizaciones["pendientes"], "22222222")
    if not p:
        pytest.skip("no hay pendiente RUT 22.222.222-2")
    aid = p["id"]
    r = requests.post(f"{BASE}/api/blindaje/autorizaciones/{aid}/autorizar",
                      headers=headers, json={}, timeout=90)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True
    assert "envio" in body
    # Verificar en dashboard: cola contiene ese correo con estado enviado|error|rebotado
    dash = requests.get(f"{BASE}/api/blindaje/dashboard", headers=headers, timeout=45).json()
    cola = dash["cola"]
    row = next((c for c in cola if c["id"] == p["correo_salida_id"]), None)
    assert row, "correo autorizado no aparece en cola"
    assert row["estado"] in ("enviado", "error", "rebotado", "autorizado"), row["estado"]
    if row["estado"] == "error":
        assert row.get("reintento_at"), "estado error debe tener reintento_at"
    # Evento envio_autorizado
    eventos = [e["evento"] for e in dash["log"]]
    assert "envio_autorizado" in eventos


# ── Regresión ──────────────────────────────────────────
def test_regresion_correos_preview(headers):
    r = requests.get(f"{BASE}/api/correos-preview", headers=headers, timeout=45)
    assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
