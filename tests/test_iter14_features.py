"""Iter 14 backend tests: Cierres, Aprendizaje IA, Estudio de Título (nueva)."""
import os
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE}/api"


@pytest.fixture(scope="module")
def s():
    return requests.Session()


# ---------- MÓDULO CIERRES ----------
class TestCierres:
    def test_list_cierres(self, s):
        r = s.get(f"{API}/cierres?todos=true", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "cierres" in data and "ventana" in data
        assert "desde" in data["ventana"] and "hasta_domingo" in data["ventana"]
        # Solo aprobadas
        for f in data["cierres"]:
            for k in ["id", "nombre", "ejecutivo_nombre", "ejecutivo_email",
                      "proyecto", "entrega_inmediata", "toca_preguntar",
                      "dias_desde_consulta", "consultas"]:
                assert k in f, f"missing {k} in {f}"
        pytest.cierres_data = data

    def test_list_filter_entrega_inmediata(self, s):
        r = s.get(f"{API}/cierres?solo_entrega_inmediata=true&todos=true", timeout=30)
        assert r.status_code == 200
        for f in r.json()["cierres"]:
            assert f["entrega_inmediata"] is True

    def test_patch_and_verify(self, s):
        data = getattr(pytest, "cierres_data", None) or s.get(f"{API}/cierres?todos=true").json()
        assert data["cierres"], "No hay carpetas aprobadas para probar PATCH"
        fid = data["cierres"][0]["id"]
        payload = {"ejecutivo_nombre": "Carla", "ejecutivo_email": "carla@test.cl",
                   "proyecto": "Test", "entrega_inmediata": True}
        r = s.patch(f"{API}/cierres/{fid}", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True
        r2 = s.get(f"{API}/cierres?todos=true", timeout=30)
        row = next((x for x in r2.json()["cierres"] if x["id"] == fid), None)
        assert row is not None
        assert row["ejecutivo_nombre"] == "Carla"
        assert row["ejecutivo_email"] == "carla@test.cl"
        assert row["proyecto"] == "Test"
        assert row["entrega_inmediata"] is True
        pytest.tested_fid = fid

    def test_consultar_preview_contains_both_buttons(self, s):
        fid = getattr(pytest, "tested_fid", None)
        assert fid, "PATCH previo necesario"
        r = s.post(f"{API}/cierres/{fid}/consultar", json={"confirm": False}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json().get("body", "")
        assert "el cliente continúa con ustedes" in body
        assert "no continuará el crédito con ustedes" in body
        assert "/api/cierres/respuesta/" in body

    def test_consultar_sin_correo_400(self, s):
        # Encontrar una carpeta aprobada, limpiar correo y consultar
        data = s.get(f"{API}/cierres?todos=true").json()
        assert data["cierres"]
        fid = data["cierres"][-1]["id"]
        s.patch(f"{API}/cierres/{fid}", json={"ejecutivo_email": ""}, timeout=30)
        r = s.post(f"{API}/cierres/{fid}/consultar", json={"confirm": False}, timeout=30)
        assert r.status_code == 400
        detail = r.json().get("detail", "")
        assert "correo" in detail.lower()

    def test_respuesta_token_inexistente(self, s):
        r = s.get(f"{API}/cierres/respuesta/token-fake-inexistente-xxx?r=si", timeout=30)
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "").lower()
        assert "Enlace no válido o ya utilizado" in r.text


# ---------- APRENDIZAJE IA ----------
class TestAprendizaje:
    def test_aprendizaje_get(self, s):
        r = s.get(f"{API}/aprendizaje", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "analisis" in data and "notas" in data
        assert isinstance(data["analisis"], list)
        assert isinstance(data["notas"], list)

    def test_aprendizaje_nota_post(self, s):
        r = s.post(f"{API}/aprendizaje/nota",
                   json={"texto": "nota de prueba del flujo"}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True
        r2 = s.get(f"{API}/aprendizaje", timeout=30)
        textos = [n.get("texto") for n in r2.json()["notas"]]
        assert "nota de prueba del flujo" in textos

    def test_aprendizaje_analizar(self, s):
        r = s.post(f"{API}/aprendizaje/analizar", timeout=200)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ["resumen", "aprendizajes", "cuellos_botella", "mejoras"]:
            assert k in data, f"missing {k}"
        # metodo debería ser 'ia' o al menos existir
        assert data.get("resumen"), "resumen vacío"


# ---------- ESTUDIO DE TÍTULO ----------
class TestEstudio:
    def test_defaults(self, s):
        r = s.get(f"{API}/estudio-titulo/defaults", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert len(data["docs_usada"]) == 7
        assert len(data["docs_nueva"]) == 11
        for d in data["docs_usada"] + data["docs_nueva"]:
            assert "tasaci" not in d.lower()

    def test_enviar_preview_nueva_reserva(self, s):
        payload = {"nombre": "SEBASTIAN SEPULVEDA", "tipo_vivienda": "nueva",
                   "docs_lista": ["Permiso de edificación municipal"],
                   "confirm": False}
        r = s.post(f"{API}/estudio-titulo/enviar", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json().get("body", "")
        assert "Permiso de edificación municipal" in body
        assert "nos reservamos la posibilidad de seguir solicitando antecedentes" in body


# ---------- REGRESIÓN ----------
class TestRegresion:
    def test_folders_list(self, s):
        r = s.get(f"{API}/clientes/folders", timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), (list, dict))
