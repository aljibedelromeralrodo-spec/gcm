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

    def test_estado_tras_mensaje_reabre(self):
        assert t.estado_tras_mensaje("abierta", True) == "respondida"
        assert t.estado_tras_mensaje("respondida", False) == "abierta"
        assert t.estado_tras_mensaje("abierta", False, cerrar_explicit=True) == "respondida"

    def test_folder_es_de_broker(self):
        fd = {"broker_codigo": "mutuaria", "broker_origen": "Mutuaria y Leasing"}
        assert t.folder_es_de_broker(fd, {"sub": "mutuaria", "nombre": "Mutuaria y Leasing"})
        assert not t.folder_es_de_broker(fd, {"sub": "otro", "nombre": "X"})

    def test_filtro_broker_incluye_origen(self):
        f = t.filtro_carpetas_broker({"sub": "mutuaria", "nombre": "Mutuaria y Leasing"})
        campos = {list(x.keys())[0] for x in f["$or"]}
        assert "broker_codigo" in campos
        assert "proyeccion_broker" in campos
        assert "broker_origen" in campos
        vacio = t.filtro_carpetas_broker({})
        assert vacio.get("id") == "__ninguna__"
