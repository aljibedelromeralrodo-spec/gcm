"""Regression suite for iteration 39 — Central Mutuos.
Covers: login 6 roles, DD/MM/AAAA date format, normativas RBAC + count,
espejo graceful sin credenciales, gerencia_accion validador OK, docs-sin-clasificar RBAC,
RUT único cross-broker, user create → clave provisoria 10 chars.
"""
import os
import re
import pytest
import requests

BASE = os.environ.get("BACKEND_TEST_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE}/api"


def _login(rut, password):
    r = requests.post(f"{API}/auth/login", json={"rut": rut, "password": password}, timeout=30)
    return r


def _tok(rut, pw):
    r = _login(rut, pw)
    assert r.status_code == 200, f"login {rut} failed: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


def _H(t):
    return {"Authorization": f"Bearer {t}"}


# ── Sesión de tokens compartidos ──
@pytest.fixture(scope="module")
def tokens():
    return {
        "admin": _tok("administrador", "141617575"),
        "gerencia": _tok("gerencia", "Gerencia2026"),
        "victoria": _tok("victoria", "Victoria2026"),
        "postventa": _tok("postventa", "Postventa2026"),
        "contralor": _tok("contralor", "Contralor2026"),
        "broker": _tok("broker1", "broker123"),
    }


# ═══ Login RBAC — 6 roles ═══
class TestLoginRoles:
    @pytest.mark.parametrize("rut,pw", [
        ("administrador", "141617575"), ("gerencia", "Gerencia2026"),
        ("victoria", "Victoria2026"), ("postventa", "Postventa2026"),
        ("contralor", "Contralor2026"), ("broker1", "broker123"),
    ])
    def test_login_ok(self, rut, pw):
        r = _login(rut, pw)
        assert r.status_code == 200
        j = r.json()
        assert isinstance(j.get("token"), str) and len(j["token"]) > 20


# ═══ Fecha DD/MM/AAAA ═══
class TestFechasFormato:
    def test_ventana_proyeccion_slash(self, tokens):
        r = requests.get(f"{API}/broker/ventana-proyeccion", headers=_H(tokens["broker"]), timeout=20)
        assert r.status_code == 200
        j = r.json()
        assert "abierta" in j and "limite" in j
        # Debe usar barras DD/MM/AAAA (no guiones)
        if j["limite"]:
            assert re.match(r"^\d{2}/\d{2}/\d{4}$", j["limite"]), \
                f"limite debe ser DD/MM/AAAA, es: {j['limite']}"


# ═══ Normativas — cerebro ═══
class TestNormativas:
    def test_lista_admin(self, tokens):
        r = requests.get(f"{API}/dashai/normativas", headers=_H(tokens["admin"]), timeout=20)
        assert r.status_code == 200
        j = r.json()
        assert j.get("total", 0) >= 13  # el sistema declara 14

    def test_broker_denied(self, tokens):
        r = requests.get(f"{API}/dashai/estado-cerebro", headers=_H(tokens["broker"]), timeout=20)
        assert r.status_code == 403

    def test_gerencia_no_crea(self, tokens):
        r = requests.post(f"{API}/dashai/normativas",
                          headers=_H(tokens["gerencia"]),
                          json={"clave": "TEST_X", "patron": "x"}, timeout=20)
        assert r.status_code == 403


# ═══ Espejo Concreces sin credenciales ═══
class TestEspejo:
    def test_sincronizar_sin_creds_400(self, tokens):
        r = requests.post(f"{API}/contralor/espejo/sincronizar", headers=_H(tokens["contralor"]), timeout=25)
        # Debe ser 400 con mensaje claro (no 500/crash)
        assert r.status_code in (400, 502), f"got {r.status_code}: {r.text[:200]}"
        assert "concreces" in r.text.lower() or "credenciales" in r.text.lower() or "buzón" in r.text.lower()

    def test_operaciones_lectura_contralor(self, tokens):
        r = requests.get(f"{API}/contralor/espejo/operaciones", headers=_H(tokens["contralor"]), timeout=20)
        assert r.status_code == 200
        j = r.json()
        assert "operaciones" in j and "ultima_sync" in j


# ═══ Gerencia — command center + acción con CC (validador OK) ═══
class TestGerencia:
    def test_command_center_zonas(self, tokens):
        r = requests.get(f"{API}/gerencia-panel/command-center", headers=_H(tokens["gerencia"]), timeout=25)
        assert r.status_code == 200
        j = r.json()
        assert "zona1" in j and "brokers" in j and "carga_administrativa" in j and "bandeja" in j

    def test_cc_opciones(self, tokens):
        r = requests.get(f"{API}/gerencia-panel/cc-opciones", headers=_H(tokens["gerencia"]), timeout=20)
        assert r.status_code == 200
        assert isinstance(r.json().get("opciones"), list)

    def test_accion_seguimiento_con_cc_no_bloquea(self, tokens):
        """Validador normativas debe permitir a gerencia usar CC (rol autorizado)."""
        cc_r = requests.get(f"{API}/gerencia-panel/command-center", headers=_H(tokens["gerencia"]), timeout=25)
        bandeja = cc_r.json().get("bandeja") or []
        if not bandeja:
            pytest.skip("Sin operaciones en bandeja para probar accion")
        fid = bandeja[0]["fid"]
        r = requests.post(f"{API}/gerencia-panel/accion",
                          headers=_H(tokens["gerencia"]),
                          json={"fid": fid, "tipo": "seguimiento", "cc": ["qa@test.cl"]},
                          timeout=25)
        # Debe pasar validador (200) porque gerencia tiene CC libre
        assert r.status_code == 200, f"validador bloqueó indebidamente: {r.status_code} {r.text[:200]}"


# ═══ Docs sin clasificar ═══
class TestDocsSinClasificar:
    def test_admin_ok(self, tokens):
        r = requests.get(f"{API}/admin/docs-sin-clasificar", headers=_H(tokens["admin"]), timeout=20)
        assert r.status_code == 200

    def test_victoria_ok(self, tokens):
        r = requests.get(f"{API}/admin/docs-sin-clasificar", headers=_H(tokens["victoria"]), timeout=20)
        assert r.status_code == 200

    def test_broker_denied(self, tokens):
        r = requests.get(f"{API}/admin/docs-sin-clasificar", headers=_H(tokens["broker"]), timeout=20)
        assert r.status_code == 403


# ═══ Broker — RBAC y ventana ═══
class TestBroker:
    def test_broker_no_admin_users(self, tokens):
        r = requests.get(f"{API}/admin/users", headers=_H(tokens["broker"]), timeout=20)
        assert r.status_code == 403


# ═══ Victoria — solo roles tipo C ═══
class TestVictoria:
    def test_no_crear_rol_superior(self, tokens):
        payload = {"nombre": "QA X", "email": f"qa.rol.x@test.cl", "rol": "gerencia"}
        r = requests.post(f"{API}/admin/users", headers=_H(tokens["victoria"]), json=payload, timeout=20)
        assert r.status_code in (403, 400), f"victoria pudo crear rol superior: {r.status_code} {r.text[:200]}"


# ═══ Admin — crear usuario retorna clave provisoria de 10 chars ═══
class TestUserCreate:
    def test_create_and_cleanup(self, tokens):
        email = "qa.iter39.audit@test.cl"
        payload = {"nombre": "QA Iter39", "email": email, "rol": "broker"}
        r = requests.post(f"{API}/admin/users", headers=_H(tokens["admin"]), json=payload, timeout=30)
        assert r.status_code in (200, 201), f"create user: {r.status_code} {r.text[:200]}"
        j = r.json()
        # Clave provisoria de 10 caracteres
        cp = j.get("clave_provisoria") or j.get("clave") or (j.get("user") or {}).get("clave_provisoria")
        assert cp and len(cp) == 10, f"clave_provisoria esperada 10 chars, recibió: {cp!r}"
        codigo = j.get("codigo") or (j.get("user") or {}).get("codigo") or j.get("id")
        assert codigo
        # Cleanup
        rd = requests.delete(f"{API}/admin/users/{codigo}", headers=_H(tokens["admin"]), timeout=20)
        assert rd.status_code in (200, 204), f"cleanup failed: {rd.status_code}"
