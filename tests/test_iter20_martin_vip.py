"""Iteration 20 - Slate redesign / Informes VIP / Simulador Martín backend tests."""
import os
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://risk-assess-17.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{BASE}/api/auth/login", json={"codigo": "administrador", "password": "141617575"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="session")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"} if admin_token else {}


# ---------------- Martín ----------------
class TestMartin:
    def test_link(self):
        r = requests.get(f"{BASE}/api/martin/link", timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "url" in d and "token" in d
        pytest.martin_token = d["token"]
        pytest.martin_url = d["url"]

    def test_simular_viable(self):
        r = requests.post(f"{BASE}/api/martin/simular", json={
            "valor_propiedad": 4500, "monto_credito": 3600,
            "renta": 1800000, "deudas": 250000, "con_subsidio": True
        }, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("porcentaje", 0) > 70, d
        assert "Martín" in d.get("veredicto", "") or "martin" in d.get("veredicto", "").lower()
        assert d.get("puede_abrir_carpeta") is True
        assert isinstance(d.get("cuota_estimada_clp"), (int, float))

    def test_simular_no_viable(self):
        r = requests.post(f"{BASE}/api/martin/simular", json={
            "valor_propiedad": 2000, "monto_credito": 1500,
            "renta": 900000, "con_subsidio": False
        }, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("porcentaje", 100) <= 10, d
        assert "2.000 UF" in (d.get("alerta_critica") or "")

    def test_simular_missing_400(self):
        r = requests.post(f"{BASE}/api/martin/simular", json={"renta": 1000000}, timeout=15)
        assert r.status_code == 400, r.status_code

    def test_martin_vip_html(self):
        token = getattr(pytest, "martin_token", None)
        assert token
        r = requests.get(f"{BASE}/api/martin-vip/{token}", timeout=20)
        assert r.status_code == 200
        assert "Simulador Martín" in r.text or "Simulador Mart" in r.text

    def test_martin_vip_404(self):
        r = requests.get(f"{BASE}/api/martin-vip/token-invalido-xxx", timeout=15)
        assert r.status_code == 404

    def test_abrir_carpeta_bad_token(self):
        r = requests.post(f"{BASE}/api/martin/abrir-carpeta", json={
            "token": "wrong", "nombre": "Cliente Prueba Martin",
            "rut": "11.111.111-1", "simulacion": {"porcentaje": 93}
        }, timeout=20)
        assert r.status_code == 403

    def test_abrir_carpeta_nombre_invalido(self):
        token = getattr(pytest, "martin_token", None)
        r = requests.post(f"{BASE}/api/martin/abrir-carpeta", json={
            "token": token, "nombre": "Cliente",
            "rut": "11.111.111-1", "simulacion": {"porcentaje": 93}
        }, timeout=20)
        assert r.status_code == 400

    def test_abrir_carpeta_ok_and_cleanup(self, auth_headers):
        token = getattr(pytest, "martin_token", None)
        r = requests.post(f"{BASE}/api/martin/abrir-carpeta", json={
            "token": token, "nombre": "Cliente Prueba Martin",
            "rut": "11.111.111-1", "simulacion": {"porcentaje": 93}
        }, timeout=25)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True
        fid = d.get("folder_id") or d.get("fid") or d.get("id")
        # verify label in folders-light
        fl = requests.get(f"{BASE}/api/clientes/folders-light", headers=auth_headers, timeout=30)
        assert fl.status_code == 200
        folders = fl.json().get("folders", fl.json()) if isinstance(fl.json(), dict) else fl.json()
        found = False
        for f in folders:
            nombre = (f.get("nombre") or f.get("cliente") or "")
            if f.get("id") == fid or "Cliente Prueba Martin" in nombre:
                fid = fid or f.get("id")
                found = True
                break
        assert found, "folder not found or missing tag"
        # cleanup
        if fid:
            requests.delete(f"{BASE}/api/clientes/folders/{fid}", headers=auth_headers, timeout=20)


# ---------------- Informes VIP ----------------
class TestInformesVIP:
    def _find_melisa(self, auth_headers):
        r = requests.get(f"{BASE}/api/clientes/folders-light", headers=auth_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        folders = data.get("folders", data) if isinstance(data, dict) else data
        for f in folders:
            nom = (f.get("nombre") or f.get("cliente") or "").upper()
            if "MELISA" in nom and "RIVERA" in nom:
                return f.get("id")
        return None

    def test_pdf(self, auth_headers):
        fid = self._find_melisa(auth_headers)
        assert fid, "MELISA RIVERA folder not found"
        r = requests.get(f"{BASE}/api/informes/vip/{fid}/pdf", headers=auth_headers, timeout=60)
        assert r.status_code == 200, r.text[:400]
        assert "application/pdf" in r.headers.get("content-type", "")
        assert r.content[:4] == b"%PDF"

    def test_enviar(self, auth_headers):
        fid = self._find_melisa(auth_headers)
        assert fid
        r = requests.post(f"{BASE}/api/informes/vip/{fid}/enviar",
                          headers=auth_headers,
                          json={"to": "ethangerardobarr@gmail.com"}, timeout=60)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert d.get("ok") is True or d.get("status") in ("ok", "sent")


# ---------------- Regression ----------------
class TestRegression:
    @pytest.mark.parametrize("path", [
        "/api/salud/estado",
        "/api/calibracion/estado",
        "/api/rescate/pendientes",
        "/api/gastos-operacionales/log",
    ])
    def test_endpoint_200(self, auth_headers, path):
        r = requests.get(f"{BASE}{path}", headers=auth_headers, timeout=30)
        assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"
