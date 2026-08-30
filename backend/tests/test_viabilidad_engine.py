"""Viabilidad Mutuaria vs Espejo Concreces (sin Mongo)."""
import sys
from pathlib import Path

BACKEND_DIR = str(Path(__file__).resolve().parents[1])
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import viabilidad_engine as ve  # noqa: E402


DOCS_OK = [
    {"nombre": "cedula.pdf", "subfolder": "01_cedula"},
    {"nombre": "liq.pdf", "subfolder": "02_liquidaciones"},
    {"nombre": "afp.pdf", "subfolder": "03_afp"},
    {"nombre": "cmf.pdf", "subfolder": "04_cmf"},
]


def _doc(**df):
    return {
        "nombre": "Cliente Test",
        "credit_request": {"client_type": "dependiente"},
        "datos_financieros": df,
    }


class TestViabilidadInterna:
    def test_hierro_deja_en_cero(self, monkeypatch):
        monkeypatch.setattr(ve, "_quiebres_hierro",
                            lambda d: [{"regla": "LTV máximo", "detalle": "LTV 95%"}])
        r = ve.viabilidad_interna(_doc(), {"base": 0.8}, archivos=DOCS_OK)
        assert r["porcentaje"] == 0
        assert "NO VIABLE" in r["alerta_critica"]

    def test_sin_docs_cero(self, monkeypatch):
        monkeypatch.setattr(ve, "_quiebres_hierro", lambda d: [])
        r = ve.viabilidad_interna(_doc(), {"base": 0.85, "aprobadas": 10, "rechazadas": 2},
                                  archivos=[])
        assert r["porcentaje"] == 0

    def test_con_docs_no_es_cero(self, monkeypatch):
        monkeypatch.setattr(ve, "_quiebres_hierro", lambda d: [])
        r = ve.viabilidad_interna(
            _doc(monto_credito=2200, valor_propiedad=3000, con_subsidio=True),
            {"base": 0.85, "aprobadas": 10, "rechazadas": 2},
            archivos=DOCS_OK)
        assert r["porcentaje"] >= 5
        assert r["origen"] == "mutuaria"


class TestEspejoConcreces:
    def test_sin_modelo_no_disponible(self):
        r = ve.probabilidad_concreces(_doc(monto_credito=2000), {}, uf_valor=39000)
        assert r["disponible"] is False
        assert r["porcentaje"] is None

    def test_monto_sobre_tope(self, monkeypatch):
        monkeypatch.setattr(ve.ce, "simular_como_mesa", lambda f, m: {
            "disponible": True, "monto_uf": 1000, "precision_pct": 70, "n": 12, "segmento": "GLOBAL"})
        monkeypatch.setattr(ve.ce, "endeudamiento_mensual",
                            lambda df, uf: {"endeudamiento_mensual_clp": 0})
        r = ve.probabilidad_concreces(
            _doc(monto_credito=2000, renta_liquida=1_200_000),
            {"listo": True, "segmentos": {"GLOBAL": {}}},
            uf_valor=39000)
        assert r["disponible"] is True
        assert r["porcentaje"] < 50
        assert r["ratio"] > 1.15

    def test_monto_bajo_tope(self, monkeypatch):
        monkeypatch.setattr(ve.ce, "simular_como_mesa", lambda f, m: {
            "disponible": True, "monto_uf": 2000, "precision_pct": 80, "n": 20, "segmento": "GLOBAL"})
        monkeypatch.setattr(ve.ce, "endeudamiento_mensual",
                            lambda df, uf: {"endeudamiento_mensual_clp": 0})
        r = ve.probabilidad_concreces(
            _doc(monto_credito=1400, renta_liquida=1_200_000),
            {"listo": True, "segmentos": {"GLOBAL": {}}},
            uf_valor=39000)
        assert r["porcentaje"] >= 70


class TestDiscrepancia:
    def test_alineados(self):
        d = ve.discrepancia({"porcentaje": 72},
                            {"disponible": True, "porcentaje": 68, "monto_espejo_uf": 1800})
        assert d["hay"] is False
        assert d["nivel"] == "alineados"

    def test_mutuaria_optimista_alerta(self):
        d = ve.discrepancia({"porcentaje": 85},
                            {"disponible": True, "porcentaje": 20, "monto_espejo_uf": 1200},
                            techo_uf=2500)
        assert d["hay"] is True
        assert d["nivel"] == "alerta"
        assert "rechazo" in d["mensaje"].lower()

    def test_evaluar_folder_expone_ambos(self, monkeypatch):
        monkeypatch.setattr(ve, "_quiebres_hierro", lambda d: [])
        monkeypatch.setattr(ve, "probabilidad_concreces", lambda *a, **k: {
            "origen": "concreces", "disponible": True, "porcentaje": 30,
            "monto_espejo_uf": 1100})
        r = ve.evaluar_folder(
            _doc(monto_credito=2200, valor_propiedad=3000, con_subsidio=True),
            {"base": 0.85, "aprobadas": 8, "rechazadas": 2},
            modelo_espejo={"listo": True}, uf_valor=39000, techo_uf=2400,
            archivos=DOCS_OK)
        assert "mutuaria" in r and "concreces" in r and "discrepancia" in r
        assert r["porcentaje"] == r["mutuaria"]["porcentaje"]
