"""Motor de crédito: amortización, LTV 79,5%, endeudamiento 2% y Espejo Mesa (sin Mongo)."""
import sys
from pathlib import Path

BACKEND_DIR = str(Path(__file__).resolve().parents[1])
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import credit_engine as ce  # noqa: E402

UF = 39000.0


class TestAmortizacion:
    def test_dividendo_cero(self):
        assert ce.dividendo(0, 0.06, 25) == 0.0
        assert ce.capacidad_desde_dividendo(0, 0.06, 25) == 0.0

    def test_ida_y_vuelta_capacidad(self):
        monto = 1500.0
        div = ce.dividendo(monto, 0.06, 25)
        rec = ce.capacidad_desde_dividendo(div, 0.06, 25)
        assert abs(rec - monto) < 0.05

    def test_tasa_cero_es_cuota_lineal(self):
        assert abs(ce.dividendo(1200, 0, 20) - 1200 / 240) < 1e-9


class TestEndeudamiento:
    def test_cuota_teorica_2_por_ciento(self):
        assert ce.cuota_teorica(10_000_000) == 200_000.0

    def test_titular_mas_codeudor(self):
        d = ce.endeudamiento_mensual(
            {"deuda_cmf_total": 8_000_000, "deuda_cmf_codeudor": 5_000_000, "pav_saldo": 0},
            UF)
        assert d["deuda_cmf_total_clp"] == 13_000_000
        assert d["endeudamiento_mensual_clp"] == 260_000

    def test_deuda_en_uf_usa_uf_del_dia(self):
        d = ce.endeudamiento_mensual({"deuda_cmf_uf": 100}, 40_000)
        assert d["deuda_cmf_total_clp"] == 4_000_000
        assert d["cuota_teorica_cmf_clp"] == 80_000


class TestLTV63:
    def test_constante_795(self):
        assert abs(ce.LTV_MAX_63 - 0.795) < 1e-12

    def test_credito_maximo_no_pasa_795(self):
        ce.UF_SII_CACHE["v"] = UF
        r = ce.simular_credito({
            "valor_uf": UF,
            "renta_titular": 2_500_000,
            "plazo_anos": 25,
            "tasa_anual": 0.06,
            "valor_propiedad_uf": 2606.007,
            "credito_solicitado_uf": 0,
            "tipo_deudor": 1,
        })
        ltv = r["credito_maximo_uf"] / 2606.007
        assert ltv <= ce.LTV_MAX_63 + 1e-6
        assert r["ltv_maximo_795"] == ce.LTV_MAX_63

    def test_ajuste_pie_si_solicita_sobre_795(self):
        ce.UF_SII_CACHE["v"] = UF
        r = ce.simular_credito({
            "valor_uf": UF,
            "renta_titular": 4_000_000,
            "plazo_anos": 25,
            "tasa_anual": 0.05,
            "valor_propiedad_uf": 2000,
            "credito_solicitado_uf": 1800,  # 90%
            "tipo_deudor": 1,
        })
        assert r["ajuste_pie_795"] is True
        assert abs(r["credito_ajustado_795_uf"] / 2000 - ce.LTV_MAX_63) < 0.001

    def test_morosidad_rechaza(self):
        ce.UF_SII_CACHE["v"] = UF
        r = ce.simular_credito({
            "valor_uf": UF,
            "renta_titular": 3_000_000,
            "valor_propiedad_uf": 2000,
            "morosidad_dicom": True,
        })
        assert r["precalificacion_aprobada"] is False
        assert any("DICOM" in x for x in r["razones_rechazo"])


class TestTecho:
    def test_sin_renta_no_suficiente(self):
        t = ce.techo_hipotecario({}, {}, {}, UF)
        assert t["datos_suficientes"] is False
        assert t["mejor_escenario"]["credito_maximo_uf"] == 0

    def test_con_renta_hay_techo(self):
        t = ce.techo_hipotecario(
            {"renta_liquida": 2_000_000, "con_subsidio": False},
            {"btg_pactual": {"sin_subsidio": {"carga_financiera_max": 0.40, "div_renta_max": 0.30}}},
            {"tasa_sin_subsidio": 0.06},
            UF, 25)
        assert t["datos_suficientes"] is True
        assert t["mejor_escenario"]["credito_maximo_uf"] > 0


class TestEspejoMesa:
    def test_regresion_linea_perfecta(self):
        a, b, r2 = ce._regresion_lineal([1.0, 2.0, 3.0], [10.0, 20.0, 30.0])
        assert abs(a - 10) < 1e-9
        assert abs(b) < 1e-9
        assert r2 > 0.99

    def test_entrenar_y_simular(self):
        casos = [
            {"renta_disponible_clp": 1_000_000, "tope_uf": 800, "con_subsidio": False},
            {"renta_disponible_clp": 2_000_000, "tope_uf": 1600, "con_subsidio": False},
            {"renta_disponible_clp": 3_000_000, "tope_uf": 2400, "con_subsidio": False},
        ]
        m = ce.entrenar_espejo_mesa(casos)
        assert m["listo"] is True
        assert m["n"] == 3
        s = ce.simular_como_mesa(
            {"renta_liquida_clp": 2_000_000, "endeudamiento_mensual_clp": 0, "con_subsidio": False},
            m)
        assert s["disponible"] is True
        assert abs(s["monto_uf"] - 1600) < 5

    def test_sin_casos_no_disponible(self):
        m = ce.entrenar_espejo_mesa([])
        assert m["listo"] is False
        s = ce.simular_como_mesa({"renta_liquida_clp": 1_000_000}, m)
        assert s["disponible"] is False
