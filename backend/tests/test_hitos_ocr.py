"""OCR de hitos: extracción de UF, fojas y notaría desde texto (sin Mongo)."""
import sys
from pathlib import Path

BACKEND_DIR = str(Path(__file__).resolve().parents[1])
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import hitos_ocr as h  # noqa: E402


TASACION = """
INFORME DE TASACIÓN
Value Property
Rol de Avalúo: 12345-67
Comuna de Las Condes
Valor comercial: UF 2.450,50
Fecha de tasación: 15/03/2026
"""

ESTUDIO = """
ESTUDIO DE TÍTULOS
El dominio se encuentra inscrito a fojas 45.231 número 43.651 del año 2001
en el Registro de Propiedad del Conservador de Bienes Raíces de Santiago.
Se informa hipoteca vigente a favor del banco.
Fecha de estudio: 01/08/2026
"""

ESCRITURA = """
BORRADOR DE ESCRITURA
Notaría de Santiago don Pedro Pérez
Repertorio N° 12890
Fecha de firma: 20/08/2026
"""


class TestTasacion:
    def test_valor_uf_y_rol(self):
        c = h.extraer_tasacion(TASACION)
        assert c.get("valor_uf") == 2450.5
        assert c.get("rol_avaluo") == "12345-67"
        assert "Condes" in (c.get("comuna") or "")
        assert "15/03/2026" in (c.get("fecha") or "")


class TestEstudio:
    def test_fojas_cbr_gravamen(self):
        c = h.extraer_estudio(ESTUDIO)
        assert c.get("fojas")
        assert c.get("numero")
        assert c.get("anio") == "2001"
        assert "Santiago" in (c.get("cbr") or "")
        assert c.get("menciona_gravamen") is True


class TestEscritura:
    def test_repertorio_notaria(self):
        c = h.extraer_escritura(ESCRITURA)
        assert c.get("repertorio") == "12890"
        assert "Santiago" in (c.get("notaria") or "")
        assert "20/08/2026" in (c.get("fecha_firma") or "")


class TestDispatch:
    def test_por_hito(self):
        assert h.extraer_campos("tasacion", TASACION).get("valor_uf")
        assert h.extraer_campos("estudio_titulo", ESTUDIO).get("fojas")
        assert h.extraer_campos("escritura", ESCRITURA).get("repertorio")
        assert h.extraer_campos("faltantes", TASACION) == {}


class TestBackfill:
    def test_necesita_backfill_si_hay_pdf_sin_ocr(self):
        fd = {"archivos": ["99_otros/TASACION_informe.pdf"], "datos_financieros": {}, "tasacion_ocr": {}}
        assert h.folder_necesita_backfill(fd) is True
        fd["tasacion_ocr"] = {"rol_avaluo": "12345-67"}
        assert h.folder_necesita_backfill(fd) is False
        assert h.folder_necesita_backfill({"archivos": ["02_liquidaciones/liq.pdf"]}) is False

    def test_hito_de_archivo_protocolo(self):
        assert h.hito_de_rel("99_otros/TASACION_informe.pdf") == "tasacion"
        assert h.hito_de_rel("07_estudio_titulo/ESTUDIO_dominio.pdf") == "estudio_titulo"
        assert h.hito_de_rel("99_otros/escritura_borrador.pdf") == "escritura"
        assert h.hito_de_rel("02_liquidaciones/liq_abril.pdf") == ""

    def test_patch_no_pisa_renta_ni_ocr_lleno(self):
        fd = {
            "datos_financieros": {"renta_liquida": 1800, "monto_credito": 2000, "rol_avaluo": "111-1"},
            "tasacion_ocr": {"rol_avaluo": "111-1"},
        }
        patch = h.patch_sin_pisar(fd, "tasacion", {"rol_avaluo": "999-9", "valor_uf": 2500}, "2026-08-01")
        assert "renta_liquida" not in patch
        assert "monto_credito" not in str(patch)
        assert "datos_financieros.rol_avaluo" not in patch
        assert patch.get("tasacion_ocr", {}).get("rol_avaluo") == "111-1"
        assert patch.get("tasacion_ocr", {}).get("valor_uf") == 2500
        assert patch.get("datos_financieros.valor_tasacion_uf") == 2500
