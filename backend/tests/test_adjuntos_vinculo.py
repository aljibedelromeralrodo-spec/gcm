"""Fase 0+1: motivos de descarte y fallback RUT en PDF (sin IMAP, sin Mongo)."""
import sys
from pathlib import Path

BACKEND_DIR = str(Path(__file__).resolve().parents[1])
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import adjuntos_vinculo as v  # noqa: E402


RUT = "12345678-9"
NUCLEO = v.norm_rut(RUT)  # 123456789
TOKENS = ["juan", "perez"]


class TestNucleo:
    def test_sin_rut_vacio(self):
        assert v.nucleo_rut_carpeta("") == ""
        assert v.nucleo_rut_carpeta("12.345") == ""

    def test_rut_completo(self):
        assert v.nucleo_rut_carpeta("12.345.678-9") == "123456789"
        assert len(v.nucleo_rut_carpeta(RUT)) >= 7


class TestEvaluarVinculo:
    def test_carpeta_sin_rut(self):
        ok, motivo = v.evaluar_vinculo_correo(
            "SOLICITUD JUAN PEREZ", "a@ecomac.cl", "hola", TOKENS, "")
        assert ok is False and motivo == "carpeta_sin_rut"

    def test_nombre_no_coincide(self):
        ok, motivo = v.evaluar_vinculo_correo(
            "SOLICITUD MARIA LOPEZ", "a@ecomac.cl", "", TOKENS, NUCLEO)
        assert ok is False and motivo == "nombre_no_coincide"

    def test_rut_en_asunto(self):
        ok, motivo = v.evaluar_vinculo_correo(
            f"SOLICITUD JUAN PEREZ Rut: {RUT}", "a@ecomac.cl", "", TOKENS, NUCLEO)
        assert ok is True and motivo is None

    def test_sin_rut_en_texto_sin_fallback(self):
        ok, motivo = v.evaluar_vinculo_correo(
            "SOLICITUD CREDITO // JUAN PEREZ", "a@ecomac.cl", "adjunto cédula",
            TOKENS, NUCLEO, ruts_por_pdf=[{NUCLEO}], fallback_ocr_rut=False)
        assert ok is False and motivo == "rut_ausente_en_texto"

    def test_fallback_pdf_rut_exacto(self):
        ok, motivo = v.evaluar_vinculo_correo(
            "SOLICITUD CREDITO // JUAN PEREZ", "a@ecomac.cl", "adjunto cédula",
            TOKENS, NUCLEO, ruts_por_pdf=[{NUCLEO}], fallback_ocr_rut=True)
        assert ok is True and motivo is None

    def test_fallback_no_acepta_rut_parcial(self):
        parcial = NUCLEO[:5]  # 12345 — no es el RUT completo
        ok, motivo = v.evaluar_vinculo_correo(
            "SOLICITUD CREDITO // JUAN PEREZ", "a@ecomac.cl", "",
            TOKENS, NUCLEO, ruts_por_pdf=[{parcial}], fallback_ocr_rut=True)
        assert ok is False and motivo == "rut_ausente_en_texto"

    def test_fallback_otro_rut_no_mezcla(self):
        ok, motivo = v.evaluar_vinculo_correo(
            "SOLICITUD CREDITO // JUAN PEREZ", "a@ecomac.cl", "",
            TOKENS, NUCLEO, ruts_por_pdf=[{"98765432k"}], fallback_ocr_rut=True)
        assert ok is False and motivo == "rut_ausente_en_texto"

    def test_fallback_pdf_sin_ruts(self):
        ok, motivo = v.evaluar_vinculo_correo(
            "SOLICITUD CREDITO // JUAN PEREZ", "a@ecomac.cl", "",
            TOKENS, NUCLEO, ruts_por_pdf=[set()], fallback_ocr_rut=True)
        assert ok is False and motivo == "rut_ausente_en_texto"


class TestDescartes:
    def test_resumen_cuenta_motivos(self):
        ds = [
            v.item_descarte("remitente_no_reconocido", "A", "x@y.cl"),
            v.item_descarte("remitente_no_reconocido", "B", "z@y.cl"),
            v.item_descarte("ley_del_rut", "C", "x@y.cl", "cedula.pdf"),
            v.item_descarte("duplicado", "D", "x@y.cl", "liq.pdf"),
        ]
        r = v.resumen_descartes(ds)
        assert r["remitente_no_reconocido"] == 2
        assert r["ley_del_rut"] == 1
        assert r["duplicado"] == 1

    def test_texto_desglose(self):
        ds = [
            v.item_descarte("ley_del_rut", filename="a.pdf"),
            v.item_descarte("duplicado", filename="b.pdf"),
        ]
        t = v.texto_resumen_descartes(ds)
        assert "No se guardaron:" in t
        assert "el RUT del PDF no coincide" in t
        assert "ya estaba en la carpeta" in t

    def test_mensaje_carpeta_sin_rut(self):
        assert "no tiene RUT registrado" in v.MSG_CARPETA_SIN_RUT
        assert "Importar desde correo" in v.MSG_CARPETA_SIN_RUT
