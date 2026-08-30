"""Concreces Perfecto: 27 reglas MHE, renta depurada y UF viva (sin Mongo)."""
import sys
from pathlib import Path

BACKEND_DIR = str(Path(__file__).resolve().parents[1])
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import concreces_perfecto as cp  # noqa: E402
from criterios_data import DEFAULT_CRITERIOS  # noqa: E402

UF = 40871.14
MHE = DEFAULT_CRITERIOS["concreces_mhe"]


def _base(**over):
    d = dict(
        liquidaciones=[1_100_000, 1_180_000, 1_250_000, 1_350_000, 1_420_000, 1_480_000],
        afp=1_300_000,
        edad=34,
        valor_propiedad_uf=2360,
        monto_credito_uf=1876,  # 79,49% — bajo el LTV duro 79,50%
        pie=20,
        plazo=30,
        dividendo=400_000,
        deudas_titular=80_000,
        haberes=120_000,
        viaticos=80_000,
        antiguedad=8,
        continuidad=12,
        actividad="dependiente",
        contrato="indefinido",
        con_subsidio=True,
        tipo_codeudor="sin",
        vivienda_nueva_usada=True,
        casa_depto=True,
        habitacional=True,
        nacionalidad_ok=True,
        deuda_prohibida=False,
        docs=["cedula", "liquidacion", "afp", "cmf"],
        fecha_entrega="Inmediata",
        ejec_interno="Deisy Salazar",
        rut_titular="12.345.678-9",
    )
    d.update(over)
    return d


class TestRenta:
    def test_depurada_min_liq_vs_afp(self):
        renta, prom = cp.renta_depurada(
            [1_100_000, 1_180_000, 1_250_000, 1_350_000, 1_420_000, 1_480_000],
            1_300_000)
        assert abs(prom - 1_296_666.666) < 1
        assert abs(renta - min(prom * 0.85, 1_300_000 * 0.90)) < 1

    def test_haberes_exceso_resta(self):
        r0, _ = cp.renta_depurada([1_000_000] * 6, 2_000_000, haberes=0)
        r1, _ = cp.renta_depurada([1_000_000] * 6, 2_000_000, haberes=250_000)
        assert abs((r0 - r1) - 50_000) < 1

    def test_viaticos_mitad_si_pasan_50(self):
        r0, _ = cp.renta_depurada([1_000_000] * 6, 2_000_000, viaticos=0)
        r1, _ = cp.renta_depurada([1_000_000] * 6, 2_000_000, viaticos=600_000)
        assert abs(r1 - r0 * 0.5) < 1


class TestUfViva:
    def test_respaldo_si_uf_cero(self):
        r = cp.evaluar(_base(), uf=0, mhe=MHE)
        assert r["uf_usada"] == cp.UF_RESPALDO
        assert r["uf_respaldo"] is True

    def test_renta_minima_cambia_con_uf(self):
        a = cp.evaluar(_base(), uf=40_000, mhe=MHE)
        b = cp.evaluar(_base(), uf=50_000, mhe=MHE)
        assert a["renta_minima_clp"] == round(15 * 40_000)
        assert b["renta_minima_clp"] == round(15 * 50_000)
        assert a["valor_propiedad_clp"] != b["valor_propiedad_clp"]

    def test_hoy_40871(self):
        r = cp.evaluar(_base(), uf=UF, mhe=MHE)
        assert r["uf_usada"] == 40871.14
        assert r["valor_propiedad_clp"] == round(2360 * UF)


class TestVeintisieteReglas:
    def test_aprobado_con_subsidio(self):
        r = cp.evaluar(_base(), uf=UF, mhe=MHE)
        assert r["estado"] == "APROBADO"
        assert r["n_ok"] == r["n_reglas"]
        assert r["n_reglas"] >= 19

    def test_valor_fuera_rechaza(self):
        r = cp.evaluar(_base(valor_propiedad_uf=500), uf=UF, mhe=MHE)
        assert r["estado"] == "RECHAZADO"
        assert any("fuera" in c["txt"] for c in r["checks"] if not c["ok"])

    def test_plazo_corto_rechaza(self):
        r = cp.evaluar(_base(plazo=15), uf=UF, mhe=MHE)
        assert r["semaforo"] == "RECHAZO"
        assert "Plazo fuera" in r["motivos"]

    def test_plazo_largo_sin_subsidio_rechaza(self):
        r = cp.evaluar(_base(con_subsidio=False, plazo=40, valor_propiedad_uf=2000,
                             monto_credito_uf=1500), uf=UF, mhe=MHE)
        assert r["estado"] == "RECHAZADO"

    def test_deuda_prohibida_rechaza(self):
        r = cp.evaluar(_base(deuda_prohibida=True), uf=UF, mhe=MHE)
        assert r["estado"] == "RECHAZADO"

    def test_div_renta_rechazo_motivo(self):
        r = cp.evaluar(_base(dividendo=520_000, deudas_titular=380_000), uf=UF, mhe=MHE)
        assert r["semaforo"] == "RECHAZO"
        assert any("Div/Renta > 40%" == m or "Carga > 55%" == m for m in r["motivos"])
        assert any("Div/Renta" in c["txt"] for c in r["checks"] if not c["ok"])

    def test_independiente_corto_rechaza(self):
        r = cp.evaluar(_base(actividad="independiente", antiguedad=12,
                             docs=["cedula", "imp_renta", "boletas", "cmf"]), uf=UF, mhe=MHE)
        assert r["semaforo"] == "RECHAZO"
        assert any("Independiente" in c["txt"] for c in r["checks"] if not c["ok"])

    def test_directo_cf_tit_70(self):
        r = cp.evaluar(_base(tipo_codeudor="directo", renta_codeudor=2_000_000,
                             deudas_titular=900_000, dividendo=100_000), uf=UF, mhe=MHE)
        assert any("Directo" in c["txt"] for c in r["checks"])

    def test_tercero_aporte_50(self):
        r = cp.evaluar(_base(tipo_codeudor="tercero", renta_codeudor=3_000_000,
                             deudas_titular=50_000, dividendo=200_000), uf=UF, mhe=MHE)
        assert any("Aporte tit" in c["txt"] for c in r["checks"] if not c["ok"])

    def test_sin_subsidio_umbrales(self):
        pol = cp.politica(False, MHE)
        assert pol["vmin"] == 1250
        assert pol["dmax"] == 0.35
        assert pol["cmax"] == 0.50
        assert pol["pmax"] == 30

    def test_con_subsidio_umbrales_boveda(self):
        pol = cp.politica(True, MHE)
        assert pol["vmin"] == 1000
        assert pol["mmax"] == 3200
        assert pol["dmax"] == 0.40
        assert pol["cmax"] == 0.55
        assert pol["pmax"] == 40
        assert pol["amin_i"] == 3

    def test_rechazo_no_baja_a_comite(self):
        r = cp.evaluar(_base(valor_propiedad_uf=500, plazo=15), uf=UF, mhe=MHE)
        assert r["estado"] == "RECHAZADO"

    def test_motivo_valor_min(self):
        r = cp.evaluar(_base(valor_propiedad_uf=500), uf=UF, mhe=MHE)
        assert "Valor UF fuera" in r["motivos"]

    def test_motivo_edad_termino(self):
        r = cp.evaluar(_base(edad=62, plazo=20), uf=UF, mhe=MHE)
        assert any("Edad termino >" in m for m in r["motivos"])

    def test_pmt_si_no_hay_dividendo(self):
        d = _base()
        d["dividendo"] = 0
        r = cp.evaluar(d, uf=UF, mhe=MHE)
        assert r["dividendo_pmt"] > 0
        assert r["dividendo_fuente"] == "pmt+seguros"

    def test_semaforo_observado_si_base_pasa_real_corta(self):
        real = {
            "listo": True,
            "con_subsidio": {"div_max_real": 0.30, "carga_max_real": 0.40, "n_ventana": 20},
            "sin_subsidio": {},
        }
        r = cp.evaluar(_base(dividendo=400_000, deudas_titular=80_000),
                       uf=UF, mhe=MHE, real=real)
        assert r["base_ok"] is True
        assert r["real_ok"] is False
        assert r["semaforo"] == "OBSERVADO"

    def test_politica_madre(self):
        assert cp.POLITICA_BASE["con_subsidio"]["div_renta_max"] == 0.40
        assert cp.POLITICA_BASE["sin_subsidio"]["div_renta_max"] == 0.35
        assert cp.POLITICA_BASE["con_subsidio"]["carga_max"] == 0.55
        assert cp.POLITICA_BASE["sin_subsidio"]["carga_max"] == 0.50
        assert cp.POLITICA_BASE["con_subsidio"]["ltv_duro"] == 0.795
        assert cp.politica(True)["ltv_max"] == 0.795


class TestMadreV6:
    def test_ltv_duro_795(self):
        r = cp.evaluar(_base(valor_propiedad_uf=2500, monto_credito_uf=2000, renta=1_200_000),
                       uf=UF)
        assert r["semaforo"] == "RECHAZO"
        assert "LTV supera duro 79.50%" in r["motivos"]

    def test_carga_usa_2_por_ciento_cmf(self):
        r = cp.evaluar(_base(renta=1_200_000, dividendo=400_000, deudas_titular=150_000), uf=UF)
        esperado = (400_000 + 150_000 * 0.02) / 1_200_000
        assert abs(r["carga"] - round(esperado, 4)) < 1e-6
        assert r["cuota_cmf"] == 3000

    def test_pmt_nominal_como_html(self):
        # i=6.35/100/12, n=360, m=2000*40871.14
        div = cp.pmt_dividendo(2000, 6.35, 30, UF)
        i = 6.35 / 100 / 12
        n = 360
        m = 2000 * UF
        esperado = m * (i * (1 + i) ** n) / ((1 + i) ** n - 1)
        assert abs(div - esperado) < 0.01

    def test_licencia_bloquea(self):
        r = cp.evaluar(_base(licencia_medica=True, renta=1_200_000), uf=UF)
        assert r["semaforo"] == "BLOQUEADO"
        assert "BLOQUEO licencia" in r["motivos"]

    def test_html_defaults_kpi(self):
        r = cp.evaluar(_base(
            valor_propiedad_uf=2500, monto_credito_uf=1987, plazo=30,
            tasa=6.35, renta=1_200_000, deudas_titular=150_000, edad=35,
            con_subsidio=True, client_type="dependiente",
        ), uf=UF)
        assert r["ltv"] <= 0.7950000000 + 1e-12
        assert "kpi" in r


class TestV7:
    def test_tasa_hasta_2000(self):
        assert cp.tasa_madre(True, 2000) == 6.5
        assert cp.tasa_madre(True, 2001) == 6.35
        assert cp.tasa_madre(False, 3000) == 5.9

    def test_ltv_trunc_no_redondea_a_795(self):
        # 0.79499 → display 79.49, no 79.50
        assert cp.ltv_trunc_pct(0.79499) == 79.49
        assert cp.ltv_10(1987.5, 2500) == round(1987.5 / 2500, 10)

    def test_412_bloquea_sin_docs(self):
        r = cp.evaluar({
            "valor_propiedad_uf": 2500, "monto_credito_uf": 1987, "renta": 1_200_000,
            "plazo": 30, "edad": 35, "con_subsidio": True, "client_type": "dependiente",
        }, uf=UF)
        assert r["semaforo"] == "BLOQUEO 412"
        assert any("faltan" in m.lower() for m in r["motivos"])

    def test_412_force_permite(self):
        r = cp.evaluar({
            "valor_propiedad_uf": 2500, "monto_credito_uf": 1987, "renta": 1_200_000,
            "plazo": 30, "edad": 35, "con_subsidio": True, "client_type": "dependiente",
            "force_incompleto": True,
        }, uf=UF)
        assert r["semaforo"] != "BLOQUEO 412"
        assert r["force_incompleto"] is True

    def test_jubilado_sin_subsidio_412(self):
        f = cp.checklist_412({"client_type": "jubilado", "con_subsidio": False,
                              "fecha_entrega": "Inmediata", "ejec_interno": "Deisy",
                              "rut_titular": "12345678-9", "docs": ["cedula", "renta_vitalicia", "cmf"]})
        assert any("subsidio" in x for x in f)

    def test_independiente_checklist(self):
        f = cp.checklist_412({"client_type": "independiente", "con_subsidio": True,
                              "fecha_entrega": "Futura", "ejec_interno": "Yerile Barrera",
                              "rut_titular": "12345678-9",
                              "docs": ["cedula", "imp_renta", "boletas", "cmf"]})
        assert f == []
