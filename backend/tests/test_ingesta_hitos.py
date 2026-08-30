"""Ingesta: detección de hitos (sin LLM, sin Mongo)."""
import sys
from pathlib import Path

BACKEND_DIR = str(Path(__file__).resolve().parents[1])
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import clasificador_correo as c  # noqa: E402


class TestDetectarHito:
    def test_solicitud_por_categoria(self):
        assert c.detectar_hito("solicitud_nueva", "x", "a@b.cl") == "solicitud_credito"

    def test_mesa_aprobacion_y_rechazo(self):
        assert c.detectar_hito("aprobacion_mesa", "Resultado", "aprobaciones@centralmutuos.cl") == "aprobacion_mesa"
        assert c.detectar_hito("rechazo_mesa", "Resultado", "aprobaciones@centralmutuos.cl") == "rechazo_mesa"

    def test_tasacion_por_texto(self):
        h = c.detectar_hito("", "SOLICITUD TASACION // PEREZ", "contacto@valueproperty.cl",
                            "se envía solicitud de tasación", ["carta_aprobacion.pdf"])
        assert h == "tasacion"

    def test_estudio_titulo_por_texto(self):
        h = c.detectar_hito("", "SOLICITUD ESTUDIO DE TITULOS // ROJAS",
                            "contacto@hipotecariogestion.cl", "", [])
        assert h == "estudio_titulo"

    def test_escritura_por_texto(self):
        h = c.detectar_hito("", "Confección borrador escritura Pérez", "notaria@sada.cl", "", [])
        assert h == "escritura"

    def test_spam_no_se_captura(self):
        h = c.detectar_hito("no_relacionado", "50% OFF", "promo@shop.com", "", [])
        assert h == "otro"
        assert h not in c.HITOS_CAPTURAR

    def test_solicitud_si_se_captura(self):
        assert "solicitud_credito" in c.HITOS_CAPTURAR
        assert "tasacion" in c.HITOS_CAPTURAR

    def test_categorias_constitucionales_intactas(self):
        assert c.CATEGORIAS == (
            "solicitud_nueva", "consulta_administrativa", "aprobacion_mesa",
            "rechazo_mesa", "peticion_documentos_mesa", "no_relacionado")
