"""Vigía: parser de cartas/liquidaciones, aprendizaje y alerta Base vs Real."""
import sys
from pathlib import Path

BACKEND_DIR = str(Path(__file__).resolve().parents[1])
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import vigia_concreces as vg  # noqa: E402


CARTA_OK = """
CARTA DE APROBACIÓN HIPOTECARIA
Nos es grato informar que su crédito ha sido aprobado.
Monto del crédito UF 1.888
Valor de la propiedad UF 2.360
Tasa anual 6,35%
Dividendo total $ 480.000
Seguro desgravamen $ 10.245
Seguro incendio $ 23.702
Relación dividendo/renta 38,2%
Carga financiera 51,0%
Pie 20%
Operación con subsidio habitacional
"""

CARTA_RZ = """
CARTA DE RECHAZO
El crédito no ha sido aprobado.
Monto crédito UF 2.100
Div/Renta 39,4%
Carga financiera 54,0%
con subsidio
"""

LIQ = """
LIQUIDACIÓN DE SUELDO
Sueldo base 1.200.000
Haberes no imponibles 120.000
Viáticos 80.000
LÍQUIDO A PAGAR 1.100.000
"""


class TestParser:
    def test_carta_aprobacion(self):
        c = vg.parse_carta(CARTA_OK, "carta_aprobacion.pdf")
        assert c["resultado"] == "aprobado"
        assert c["monto_uf"] == 1888
        assert abs(c["tasa"] - 0.0635) < 1e-6
        assert c["dividendo_total"] == 480000
        assert abs(c["div_renta"] - 0.382) < 0.002
        assert abs(c["carga"] - 0.51) < 0.002
        assert c["con_subsidio"] is True
        assert c["seguro_desgravamen"] == 10245

    def test_carta_rechazo(self):
        c = vg.parse_carta(CARTA_RZ, "rechazo_mesa.pdf")
        assert c["resultado"] == "rechazado"
        assert abs(c["div_renta"] - 0.394) < 0.002

    def test_liquidacion_liquido(self):
        L = vg.parse_liquidacion(LIQ)
        assert L["liquido"] == 1_100_000
        assert L["haberes"] == 120_000
        assert L["viaticos"] == 80_000


class TestAprender:
    def test_alerta_div_mas_estricto(self):
        casos = []
        for i in range(20):
            casos.append({
                "resultado": "aprobado", "div_renta": 0.385, "carga": 0.50,
                "con_subsidio": True, "pie": 0.20, "valor_uf": 2300, "monto_uf": 1800,
            })
        for _ in range(3):
            casos.append({
                "resultado": "rechazado", "div_renta": 0.392, "carga": 0.52,
                "con_subsidio": True,
            })
        real = vg.aprender(casos)
        assert real["listo"] is True
        assert abs(real["con_subsidio"]["div_max_real"] - 0.385) < 0.002
        alertas = vg.comparar(real)
        assert any("40%" in a["txt"] and "38.5%" in a["txt"] for a in alertas)
        assert any("3 rechazos" in a["txt"] for a in alertas)

    def test_sin_muestra_no_alerta(self):
        real = vg.aprender([])
        assert real["listo"] is False
        assert vg.comparar(real) == []
