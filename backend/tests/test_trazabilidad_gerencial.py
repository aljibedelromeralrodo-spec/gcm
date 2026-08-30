"""Hitos automáticos y consultas de Gerencia (sin Mongo, sin correo)."""
import sys
from pathlib import Path

BACKEND_DIR = str(Path(__file__).resolve().parents[1])
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import hitos_pipeline as t  # noqa: E402


class TestEstadosHitos:
    def test_tasacion_ok_por_ocr(self):
        fd = {"tasacion_ocr": {"rol_avaluo": "12345-67", "valor_uf": 2000}}
        assert t.estados_hitos(fd)["tasacion"] == "ok"

    def test_estudio_alerta_con_reparos(self):
        fd = {"estudio_recibido_at": "2026-08-01", "reparos_alertas": [{"texto": "falta hipoteca"}]}
        assert t.estados_hitos(fd)["estudio"] == "alerta"

    def test_serie_firmada(self):
        fd = {"set_credito_estado": "firmado"}
        assert t.estados_hitos(fd)["serie"] == "ok"
        fd2 = {"set_enviado": True}
        assert t.estados_hitos(fd2)["serie"] == "proceso"

    def test_cuello_es_primer_hito_pendiente(self):
        fd = {"estudio_recibido_at": "2026-08-01"}
        c = t.cuello_botella(fd)
        assert c["hito"] == "tasacion"
        assert "tasación" in c["pregunta"].lower()

    def test_preguntas_no_inventan_envio(self):
        assert set(t.PREGUNTAS) == {"tasacion", "estudio", "serie"}
