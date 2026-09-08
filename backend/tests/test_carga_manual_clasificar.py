"""Carga manual / Buscar Adjuntos: ubicación por tipo sin tocar IMAP."""
import sys
from pathlib import Path

BACKEND_DIR = str(Path(__file__).resolve().parents[1])
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import folders_service as fsvc  # noqa: E402


def test_nombre_generico_scan():
    assert fsvc.nombre_generico("scan001.pdf")
    assert fsvc.nombre_generico("documento.pdf")
    assert fsvc.nombre_generico("image.jpg")
    assert not fsvc.nombre_generico("Cedula_Juan.pdf")
    assert not fsvc.nombre_generico("01_Cedula_x.pdf")


def test_ubicar_ia_cedula_en_scan():
    fn, sub = fsvc.ubicar_carga_manual("scan001.pdf", tipo_ia="cedula")
    assert sub == "01_cedula"
    assert fn.startswith("01_Cedula_")


def test_ubicar_ia_otro_cae_en_99():
    fn, sub = fsvc.ubicar_carga_manual("scan001.pdf", tipo_ia="otro")
    assert sub == "99_otros"
    assert fn.startswith("99_Otros_")


def test_ubicar_por_nombre_sin_ia():
    fn, sub = fsvc.ubicar_carga_manual("Liquidacion_marzo.pdf")
    assert sub == "02_liquidaciones"
    assert "02_Liquidaciones" in fn


def test_ubicar_ya_prefijado_no_renombra():
    fn, sub = fsvc.ubicar_carga_manual("01_Cedula_scan001.pdf")
    assert fn == "01_Cedula_scan001.pdf"
    assert sub == "01_cedula"


def test_ubicar_ocr_texto_liquidacion():
    texto = "LIQUIDACION DE REMUNERACIONES  Haberes  Liquido a pagar"
    fn, sub = fsvc.ubicar_carga_manual("scan001.pdf", texto_ocr=texto)
    assert sub == "02_liquidaciones"


def test_codeudor_no_se_mueve():
    fn, sub = fsvc.ubicar_carga_manual("CODEUDOR_cedula.pdf")
    assert fn.startswith("CODEUDOR_")
    assert sub == ""
