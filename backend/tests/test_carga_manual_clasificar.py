"""Carga manual / Buscar Adjuntos: ubicación por tipo sin tocar IMAP."""
import sys
from pathlib import Path

BACKEND_DIR = str(Path(__file__).resolve().parents[1])
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import folders_service as fsvc  # noqa: E402


import ai_extract  # noqa: E402


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


def test_nombres_con_guion_bajo():
    assert fsvc.cat_de_texto("licencia_medica.pdf") == "licencia"
    assert fsvc.cat_de_texto("contrato_trabajo.pdf") == "contrato"
    assert fsvc.cat_de_texto("informe_CMF.pdf") == "cmf"
    assert fsvc.cat_de_texto("CI_TITULAR.pdf") == "cedula"
    assert fsvc.cat_de_texto("CI_CODEUDOR.pdf") == "cedula"
    assert fsvc.cat_de_texto("RSH_registro.pdf") == "rsh"
    assert fsvc.cat_de_texto("estudio_titulo.pdf") == "estudio_titulo"
    assert fsvc.cat_de_texto("renta_vitalicia.pdf") == "renta_vitalicia"
    assert fsvc.cat_de_texto("TASACION_informe.pdf") == "tasacion"
    assert fsvc.cat_de_texto("Carta_Aprobacion.pdf") == "resolucion"


def test_ubicar_tipos_avanzados():
    _, sub = fsvc.ubicar_carga_manual("licencia_medica.pdf")
    assert sub == "06_licencias"
    _, sub = fsvc.ubicar_carga_manual("scan001.pdf", tipo_ia="contrato_trabajo")
    assert sub == "05_contratos"
    _, sub = fsvc.ubicar_carga_manual("scan001.pdf", tipo_ia="registro_social_hogares")
    assert sub == "08_rsh"
    _, sub = fsvc.ubicar_carga_manual("x.pdf", tipo_ia="tasacion")
    assert sub == "09_tasacion"
    _, sub = fsvc.ubicar_carga_manual("x.pdf", tipo_ia="escritura")
    assert sub == "10_escritura"
    _, sub = fsvc.ubicar_carga_manual("x.pdf", tipo_ia="carta_aprobacion")
    assert sub == "11_resoluciones"
    _, sub = fsvc.ubicar_carga_manual("x.pdf", tipo_ia="gastos_operacionales")
    assert sub == "12_gop"


def test_hito_ruteo_no_cae_en_99():
    assert fsvc.subfolder_de_hito("tasacion") == "09_tasacion"
    assert fsvc.subfolder_de_hito("escritura") == "10_escritura"
    assert fsvc.subfolder_de_hito("aprobacion_mesa") == "11_resoluciones"
    assert fsvc.subfolder_de_hito("rechazo_mesa") == "11_resoluciones"
    assert fsvc.subfolder_de_hito("estudio_titulo") == "07_estudio_titulo"
    assert fsvc.subfolder_de_hito("solicitud_credito") == ""
    assert fsvc.subfolder_de_hito("faltantes") == ""
    assert fsvc.subfolder_de_hito("gop") == "12_gop"
    assert fsvc.HITO_A_SUBFOLDER["faltantes"] == fsvc.CLASIFICAR_POR_OCR


def test_ocr_rescate_solo_si_nombre_no_clasifica():
    assert fsvc.necesita_ocr_rescate("scan001.pdf", "otro") is True
    assert fsvc.necesita_ocr_rescate("scan001.pdf", "cedula") is False
    assert fsvc.necesita_ocr_rescate("Liquidacion_marzo.pdf", "otro") is False
    assert fsvc.necesita_ocr_rescate("informe_CMF.pdf") is False


def test_asegurar_estructura_crea_09_a_12():
    import tempfile
    prev = fsvc.CLIENTES_DIR
    td = Path(tempfile.mkdtemp())
    try:
        fsvc.CLIENTES_DIR = td
        base = fsvc.asegurar_estructura("JUAN PRUEBA")
        for sub in ("01_cedula", "09_tasacion", "10_escritura",
                    "11_resoluciones", "12_gop", "99_otros", "05_codeudor"):
            assert (base / sub).is_dir(), sub
    finally:
        fsvc.CLIENTES_DIR = prev


def test_ocr_rescate_texto_licencia_en_scan():
    texto = "Licencia Medica reposo laboral 12 dias"
    fn, sub = fsvc.ubicar_carga_manual("scan001.pdf", texto_ocr=texto)
    assert sub == "06_licencias"
    assert fn.startswith("06_Licencia_")


def test_ia_tipos_avanzados_y_fallback():
    for t in ("licencia_medica", "contrato_trabajo", "registro_social_hogares",
              "tasacion", "escritura", "gastos_operacionales"):
        assert t in ai_extract.TIPOS
    assert ai_extract._fallback_clasificar("", "CI_TITULAR.pdf") == "cedula"
    assert ai_extract._fallback_clasificar("", "informe_CMF.pdf") == "certificado_smf"
    assert ai_extract._fallback_clasificar("Licencia medica reposo", "scan001.pdf") == "licencia_medica"
    assert ai_extract._fallback_clasificar("gastos operacionales", "voucher.pdf") == "gastos_operacionales"
