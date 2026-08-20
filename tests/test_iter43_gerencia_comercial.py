"""Tests for iteration 43 - Gerencia Comercial redesign (centro-mando, ficha, export PDF)."""
import os
import requests
import pytest

# Preview proxy sometimes fronts with WAF returning HTML on some paths — the review
# request recommends localhost for curl when needed.
PUBLIC = os.environ.get("REACT_APP_BACKEND_URL", "https://espejo-hibrido.preview.emergentagent.com").rstrip("/")
LOCAL = "http://localhost:8001"


def _login(base, rut, password):
    r = requests.post(f"{base}/api/auth/login", json={"rut": rut, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed {rut}: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def base_url():
    # Prefer public URL, fall back to localhost if public returns HTML/WAF
    try:
        r = requests.get(f"{PUBLIC}/api/valor-uf", timeout=10)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json"):
            return PUBLIC
    except Exception:
        pass
    return LOCAL


@pytest.fixture(scope="module")
def gerencia_token(base_url):
    return _login(base_url, "gerencia", "Gerencia2026")


@pytest.fixture(scope="module")
def admin_token(base_url):
    return _login(base_url, "administrador", "141617575")


@pytest.fixture(scope="module")
def broker_token(base_url):
    return _login(base_url, "broker", "Broker2026")


# ---------- centro-mando ----------
class TestCentroMando:
    def test_centro_mando_gerencia_ok(self, base_url, gerencia_token):
        r = requests.get(
            f"{base_url}/api/gerencia-comercial/centro-mando",
            headers={"Authorization": f"Bearer {gerencia_token}"},
            timeout=20,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        # kpis
        kpis = data.get("kpis", {})
        assert "cartera_total_uf" in kpis
        assert "operaciones_activas" in kpis
        assert "mora_vigente" in kpis and "n" in kpis["mora_vigente"]
        assert "nuevas_mes" in kpis
        # ranking
        ranking = data.get("ranking", [])
        assert isinstance(ranking, list) and len(ranking) >= 3
        # ejecutivos
        ejecs = data.get("ejecutivos", [])
        assert isinstance(ejecs, list) and len(ejecs) >= 3
        for ej in ejecs:
            assert "cartera_uf" in ej
            assert "cartera_ops" in ej
            assert "ops_activas" in ej
            assert "tasa_cierre" in ej
            assert "mora_generada" in ej
            assert "imap" in ej and "estado" in ej["imap"]
            assert ej["imap"]["estado"] in ("activo", "error", "en_espera")
        # alertas
        alertas = data.get("alertas", {})
        for k in ("ejecutivos_mora_alta", "operaciones_vencidas", "clientes_sin_actividad"):
            assert k in alertas, f"missing alerta {k}"

    def test_centro_mando_broker_403(self, base_url, broker_token):
        r = requests.get(
            f"{base_url}/api/gerencia-comercial/centro-mando",
            headers={"Authorization": f"Bearer {broker_token}"},
            timeout=15,
        )
        assert r.status_code == 403, f"expected 403, got {r.status_code}"

    def test_centro_mando_admin_ok(self, base_url, admin_token):
        r = requests.get(
            f"{base_url}/api/gerencia-comercial/centro-mando",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=20,
        )
        assert r.status_code == 200


# ---------- ficha ejecutivo ----------
class TestFichaEjecutivo:
    def test_ficha_victoria(self, base_url, gerencia_token):
        r = requests.get(
            f"{base_url}/api/gerencia-comercial/ejecutivo/victoria/ficha",
            headers={"Authorization": f"Bearer {gerencia_token}"},
            timeout=20,
        )
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert "ejecutivo" in d
        ej = d["ejecutivo"]
        assert "nombre" in ej and "email" in ej
        assert "metricas" in d
        assert "historial_operaciones" in d
        assert isinstance(d["historial_operaciones"], list)
        if d["historial_operaciones"]:
            row = d["historial_operaciones"][0]
            for k in ("cliente", "monto_uf", "dicom", "dias_sin_movimiento"):
                assert k in row, f"missing {k} in historial row"
        assert "comunicaciones" in d
        com = d["comunicaciones"]
        assert "enviadas" in com and "espejo" in com

    def test_ficha_inexistente_404(self, base_url, gerencia_token):
        r = requests.get(
            f"{base_url}/api/gerencia-comercial/ejecutivo/inexistente/ficha",
            headers={"Authorization": f"Bearer {gerencia_token}"},
            timeout=15,
        )
        assert r.status_code == 404


# ---------- export PDF ----------
class TestExportPDF:
    def test_pin_incorrecto_403(self, base_url, gerencia_token):
        r = requests.get(
            f"{base_url}/api/gerencia-comercial/export-pdf",
            params={"pin": "9999"},
            headers={"Authorization": f"Bearer {gerencia_token}"},
            timeout=15,
        )
        assert r.status_code == 403

    def test_pin_correcto_devuelve_pdf(self, base_url, gerencia_token):
        r = requests.get(
            f"{base_url}/api/gerencia-comercial/export-pdf",
            params={"pin": "0586"},
            headers={"Authorization": f"Bearer {gerencia_token}"},
            timeout=30,
        )
        assert r.status_code == 200, r.text[:300]
        ct = r.headers.get("content-type", "")
        assert "application/pdf" in ct, f"unexpected content-type: {ct}"
        assert r.content[:4] == b"%PDF", f"not a PDF: {r.content[:20]!r}"


# ---------- regresion gerencia/cartera ----------
class TestGerenciaCartera:
    def test_cartera_incluye_creado_y_dicom(self, base_url, gerencia_token):
        r = requests.get(
            f"{base_url}/api/gerencia/cartera",
            headers={"Authorization": f"Bearer {gerencia_token}"},
            timeout=30,
        )
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        # response may be dict with "filas" or a list
        filas = d.get("cartera") if isinstance(d, dict) else d
        assert isinstance(filas, list) and len(filas) > 0, "no filas returned"
        row = filas[0]
        assert "creado" in row, f"missing 'creado' in row keys: {list(row.keys())[:15]}"
        assert "dicom" in row, f"missing 'dicom' in row keys: {list(row.keys())[:15]}"
        assert isinstance(row["dicom"], bool), f"dicom must be bool, got {type(row['dicom'])}"
