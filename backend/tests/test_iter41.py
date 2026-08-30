"""Backend sanity tests for iteration 41 features (session 7 tasks)."""
import os
import requests
import pytest
from _tok import tok as _login_tok

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE:
    # fallback read frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE}/api"


def login(rut, password):
    r = requests.post(f"{API}/auth/login", json={"rut": rut, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {rut} failed {r.status_code} {r.text}"
    return _login_tok(r)


@pytest.fixture(scope="module")
def admin_token():
    return login("administrador", "141617575")


@pytest.fixture(scope="module")
def gerencia_token():
    return login("gerencia", "Gerencia2026")


@pytest.fixture(scope="module")
def admin_h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def gerencia_h(gerencia_token):
    return {"Authorization": f"Bearer {gerencia_token}"}


@pytest.fixture(scope="module")
def administracion_h():
    tok = login("administracion", "Administracion2026")
    return {"Authorization": f"Bearer {tok}"}


# --- (A) Visión operaciones ---
def test_vision_operaciones(admin_h):
    r = requests.get(f"{API}/gerencia-comercial/vision-operaciones", headers=admin_h, timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "operaciones" in j
    assert "proyecciones_mes" in j
    if j["operaciones"]:
        o = j["operaciones"][0]
        for k in ["con_subsidio", "resolucion_serviu", "tipo_vivienda", "inmobiliaria", "proyecto", "monto_uf", "mes_creacion", "semaforo"]:
            assert k in o, f"missing field {k}"


# --- (C) Ejecutivos desempeño ---
def test_ejecutivos_desempeno(admin_h):
    r = requests.get(f"{API}/gerencia-comercial/ejecutivos-desempeno", headers=admin_h, timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    ejec = j.get("ejecutivos", [])
    assert len(ejec) == 3
    codes = {e["codigo"] for e in ejec}
    assert {"victoria", "daniela", "postventa"} <= codes
    for e in ejec:
        for k in ["modulo", "tareas", "tareas_pendientes", "tareas_vencidas", "ratio_cumplimiento", "historial_mensual"]:
            assert k in e
    assert "consolidado" in j


def test_ejecutivos_put_admin(admin_h):
    payload = {"tareas": [{"id": "t1", "titulo": "Test", "estado": "pendiente"}]}
    r = requests.put(f"{API}/gerencia-comercial/ejecutivos-modulo/victoria", headers=admin_h, json=payload, timeout=15)
    assert r.status_code in (200, 204), r.text


def test_ejecutivos_put_forbidden(administracion_h):
    r = requests.put(f"{API}/gerencia-comercial/ejecutivos-modulo/victoria", headers=administracion_h, json={"tareas": []}, timeout=15)
    assert r.status_code == 403


# --- (B) Correo destinatarios ---
def test_correo_destinatarios_list(admin_h):
    r = requests.get(f"{API}/correo-destinatarios", headers=admin_h, timeout=15)
    assert r.status_code == 200, r.text
    items = r.json().get("acciones", [])
    accs = [i for i in items if i.get("accion_id") == "respuestas_brokers"]
    assert accs, f"respuestas_brokers not found in {items}"
    a = accs[0]
    to_list = a.get("to") or a.get("destinatarios") or []
    assert any("victoriavilches" in e for e in to_list)
    assert any("danielagalindo" in e for e in to_list)


def test_correo_destinatarios_invalid_email(admin_h):
    # first find id
    r = requests.get(f"{API}/correo-destinatarios", headers=admin_h, timeout=15)
    items = r.json().get("acciones", [])
    if not items:
        pytest.skip("no items")
    tgt = None
    for i in items:
        if i.get("accion_id") != "respuestas_brokers":
            tgt = i
            break
    if not tgt:
        tgt = items[0]
    _id = tgt.get("accion_id")
    r = requests.put(f"{API}/correo-destinatarios/{_id}", headers=admin_h, json={"to": ["notanemail"]}, timeout=15)
    assert r.status_code == 400


def test_correo_destinatarios_forbidden(administracion_h):
    r = requests.get(f"{API}/correo-destinatarios", headers=administracion_h, timeout=15)
    assert r.status_code == 403


# --- (E) Admin verificar password ---
def test_admin_verificar_password_ok(admin_h):
    r = requests.post(f"{API}/admin/verificar-password", headers=admin_h, json={"password": "141617575"}, timeout=15)
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_admin_verificar_password_bad(admin_h):
    r = requests.post(f"{API}/admin/verificar-password", headers=admin_h, json={"password": "wrong"}, timeout=15)
    assert r.status_code == 401


def test_admin_verificar_password_forbidden(gerencia_h):
    r = requests.post(f"{API}/admin/verificar-password", headers=gerencia_h, json={"password": "141617575"}, timeout=15)
    assert r.status_code == 403


# --- (F) ADN helice estado ---
def test_adn_helice_estado_admin(admin_h):
    r = requests.get(f"{API}/adn-helice/estado", headers=admin_h, timeout=15)
    assert r.status_code == 200
    j = r.json()
    for k in ["procesados", "esperados", "faltantes", "estado"]:
        assert k in j


def test_adn_helice_estado_gerencia(gerencia_h):
    r = requests.get(f"{API}/adn-helice/estado", headers=gerencia_h, timeout=15)
    assert r.status_code == 200


def test_adn_helice_estado_forbidden(administracion_h):
    r = requests.get(f"{API}/adn-helice/estado", headers=administracion_h, timeout=15)
    assert r.status_code == 403


# --- (G) Espejo Híbrido ---
def test_espejo_hibrido_estado_admin(admin_h):
    r = requests.get(f"{API}/espejo-hibrido/estado", headers=admin_h, timeout=15)
    assert r.status_code == 200
    j = r.json()
    fuentes = j.get("fuentes", [])
    assert len(fuentes) == 3
    codes = {f.get("codigo") or f.get("usuario") for f in fuentes}
    for f in fuentes:
        assert f.get("estado") == "en_espera"


def test_espejo_hibrido_barrido(admin_h):
    r = requests.post(f"{API}/espejo-hibrido/barrido", headers=admin_h, timeout=30)
    assert r.status_code == 200
    j = r.json()
    # should be en_espera with no errors
    assert "resultados" in j or "fuentes" in j or j.get("estado")
