"""Validación documental: perfiles, vigencia por mes y alertas específicas (sin Mongo)."""
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = str(Path(__file__).resolve().parents[1])
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import validacion_documental as v  # noqa: E402
import folders_service as fsvc  # noqa: E402

AHORA = datetime(2026, 8, 29, tzinfo=timezone.utc)


def _a(nombre, sub="", tamano=1000):
    return {"nombre": nombre, "subfolder": sub, "tamano": tamano, "protegido": False}


def _msgs(val, nivel="faltante"):
    return [a["mensaje"] for a in val["alertas"] if a["nivel"] == nivel]


class TestPeriodoNombre:
    def test_mes_en_espanol_con_guion_bajo(self):
        assert v.periodo_de_nombre("liquidacion_abril.pdf", AHORA) == (2026, 4)

    def test_iso_yyyy_mm(self):
        assert v.periodo_de_nombre("liq_2026-04.pdf", AHORA) == (2026, 4)

    def test_yyyymm(self):
        assert v.periodo_de_nombre("sueldo_202603.pdf", AHORA) == (2026, 3)

    def test_mes_sin_anio_usa_anio_actual(self):
        assert v.periodo_de_nombre("liquidacion_mayo.pdf", AHORA) == (2026, 5)

    def test_mes_futuro_sin_anio_cae_al_anterior(self):
        assert v.periodo_de_nombre("liquidacion_diciembre.pdf", AHORA) == (2025, 12)


class TestPerfiles:
    def test_dependiente_no_pide_boletas_ni_f22(self):
        archivos = [
            _a("01_Cedula.pdf", "01_cedula"),
            _a("liq_febrero_2026.pdf", "02_liquidaciones"),
            _a("liq_marzo_2026.pdf", "02_liquidaciones"),
            _a("liq_abril_2026.pdf", "02_liquidaciones"),
            _a("liq_mayo_2026.pdf", "02_liquidaciones"),
            _a("liq_junio_2026.pdf", "02_liquidaciones"),
            _a("liq_julio_2026.pdf", "02_liquidaciones"),
            _a("certificado_afp_24m.pdf", "03_afp"),
            _a("informe_cmf.pdf", "04_cmf"),
        ]
        val = v.validar_documentos("dependiente", archivos, ahora=AHORA)
        blob = " ".join(_msgs(val)).lower()
        assert "boleta" not in blob
        assert "f22" not in blob
        assert "honorario" not in blob
        assert val["completo"] is True

    def test_independiente_no_pide_liquidaciones_ni_afp(self):
        archivos = [
            _a("cedula.pdf", "01_cedula"),
            _a("carpeta tributaria f22.pdf", "02_impuesto_renta"),
            _a("dai_boletas_2025.pdf", "03_boletas"),
            _a("informe_cmf.pdf", "04_cmf"),
        ]
        val = v.validar_documentos("independiente", archivos, ahora=AHORA)
        blob = " ".join(_msgs(val)).lower()
        assert "liquidaci" not in blob
        assert "afp" not in blob
        assert "cotizaci" not in blob
        assert val["completo"] is True

    def test_mixto_exige_ambos_conjuntos(self):
        solo_dep = [
            _a("cedula.pdf", "01_cedula"),
            _a("liq_febrero_2026.pdf", "02_liquidaciones"),
            _a("liq_marzo_2026.pdf", "02_liquidaciones"),
            _a("liq_abril_2026.pdf", "02_liquidaciones"),
            _a("liq_mayo_2026.pdf", "02_liquidaciones"),
            _a("liq_junio_2026.pdf", "02_liquidaciones"),
            _a("liq_julio_2026.pdf", "02_liquidaciones"),
            _a("afp.pdf", "03_afp"),
            _a("cmf.pdf", "04_cmf"),
        ]
        val = v.validar_documentos("mixto", solo_dep, ahora=AHORA)
        blob = " ".join(_msgs(val)).lower()
        assert "boleta" in blob or "dai" in blob
        assert "f22" in blob or "tributaria" in blob
        assert val["completo"] is False

    def test_desconocido_no_exige_liquidaciones(self):
        val = v.validar_documentos("desconocido", [_a("cedula.pdf", "01_cedula")], ahora=AHORA)
        blob = " ".join(_msgs(val)).lower()
        assert "liquidaci" not in blob
        assert "boleta" not in blob
        assert any("cmf" in m.lower() for m in _msgs(val))

    def test_exento_afp_no_pide_cotizaciones(self):
        archivos = [
            _a("cedula.pdf", "01_cedula"),
            _a("liq_febrero_2026.pdf", "02_liquidaciones"),
            _a("liq_marzo_2026.pdf", "02_liquidaciones"),
            _a("liq_abril_2026.pdf", "02_liquidaciones"),
            _a("liq_mayo_2026.pdf", "02_liquidaciones"),
            _a("liq_junio_2026.pdf", "02_liquidaciones"),
            _a("liq_julio_2026.pdf", "02_liquidaciones"),
            _a("cmf.pdf", "04_cmf"),
        ]
        val = v.validar_documentos("dependiente", archivos, exento_afp=True, ahora=AHORA)
        assert "afp" not in val["cats_faltantes"]
        blob = " ".join(_msgs(val)).lower()
        assert "afp" not in blob


class TestAlertasMes:
    def test_no_inventa_meses_si_hay_archivos_sin_fecha(self):
        """6 liquidaciones, solo una con mes en el nombre → no dispara «falta febrero»."""
        archivos = [
            _a("cedula.pdf", "01_cedula"),
            _a("liq_abril_2026.pdf", "02_liquidaciones"),
            _a("liq2.pdf", "02_liquidaciones"),
            _a("liq3.pdf", "02_liquidaciones"),
            _a("liq4.pdf", "02_liquidaciones"),
            _a("liq5.pdf", "02_liquidaciones"),
            _a("liq6.pdf", "02_liquidaciones"),
            _a("afp.pdf", "03_afp"),
            _a("cmf.pdf", "04_cmf"),
        ]
        val = v.validar_documentos("dependiente", archivos, ahora=AHORA)
        msgs = _msgs(val)
        assert not any("febrero" in m.lower() or "marzo" in m.lower() for m in msgs)
        assert val["completo"] is True

    def test_conteo_si_faltan_archivos_sin_mes(self):
        archivos = [
            _a("cedula.pdf", "01_cedula"),
            _a("liq1.pdf", "02_liquidaciones"),
            _a("liq2.pdf", "02_liquidaciones"),
            _a("afp.pdf", "03_afp"),
            _a("cmf.pdf", "04_cmf"),
        ]
        val = v.validar_documentos("dependiente", archivos, ahora=AHORA)
        msgs = _msgs(val)
        assert any("hay 2 de 6" in m.lower() for m in msgs)
        assert not any("abril" in m.lower() for m in msgs)

    def test_periodo_en_texto_de_liquidacion(self):
        assert v.periodo_de_texto("Remuneraciones del mes de abril de 2026", AHORA) == (2026, 4)
        assert v.periodo_de_texto("Periodo: 01/04/2026 al 30/04/2026", AHORA) == (2026, 4)

    def test_mixto_desde_tipos_de_ingesta(self):
        assert v.tipo_laboral_de_tipos(["cedula", "liquidacion", "boleta_honorarios"]) == "mixto"
        assert v.tipo_laboral_de_tipos(["impuesto_renta", "boleta_honorarios"]) == "independiente"
        assert v.tipo_laboral_de_tipos(["cedula", "liquidacion", "certificado_afp"]) == "dependiente"

    def test_falta_liquidacion_de_abril(self):
        archivos = [
            _a("cedula.pdf", "01_cedula"),
            _a("liq_febrero_2026.pdf", "02_liquidaciones"),
            _a("liq_marzo_2026.pdf", "02_liquidaciones"),
            _a("liq_mayo_2026.pdf", "02_liquidaciones"),
            _a("liq_junio_2026.pdf", "02_liquidaciones"),
            _a("liq_julio_2026.pdf", "02_liquidaciones"),
            _a("afp.pdf", "03_afp"),
            _a("cmf.pdf", "04_cmf"),
        ]
        val = v.validar_documentos("dependiente", archivos, ahora=AHORA)
        msgs = _msgs(val)
        assert any("abril" in m.lower() for m in msgs)
        assert any("liquidación de sueldo del mes de abril" in m.lower() for m in msgs)
        assert not any("febrero" in m.lower() for m in msgs)

    def test_sin_liquidaciones_alerta_generica(self):
        archivos = [
            _a("cedula.pdf", "01_cedula"),
            _a("afp.pdf", "03_afp"),
            _a("cmf.pdf", "04_cmf"),
        ]
        val = v.validar_documentos("dependiente", archivos, ahora=AHORA)
        assert any("liquidaciones de sueldo" in m.lower() for m in _msgs(val))


class TestFormato:
    def test_archivo_vacio(self):
        val = v.validar_documentos("dependiente", [_a("cedula.pdf", "01_cedula", tamano=0)], ahora=AHORA)
        assert any(a["nivel"] == "formato" and "vacío" in a["mensaje"].lower() for a in val["alertas"])

    def test_extension_invalida(self):
        val = v.validar_documentos("dependiente", [
            {"nombre": "notas.exe", "subfolder": "99_otros", "tamano": 10, "protegido": False},
        ], ahora=AHORA)
        assert any(a["nivel"] == "formato" for a in val["alertas"])


class TestCodeudor:
    def test_remap_codeudor_por_nombre(self):
        arch = [_a("CODEUDOR_liquidacion_abril_2026.pdf", "05_codeudor")]
        rem = v.remap_codeudor(arch)
        assert len(rem) == 1
        assert rem[0]["subfolder"] == "02_liquidaciones"

    def test_codeudor_dependiente_pide_cedula(self):
        titular = [
            _a("cedula.pdf", "01_cedula"),
            _a("liq_febrero_2026.pdf", "02_liquidaciones"),
            _a("liq_marzo_2026.pdf", "02_liquidaciones"),
            _a("liq_abril_2026.pdf", "02_liquidaciones"),
            _a("liq_mayo_2026.pdf", "02_liquidaciones"),
            _a("liq_junio_2026.pdf", "02_liquidaciones"),
            _a("liq_julio_2026.pdf", "02_liquidaciones"),
            _a("afp.pdf", "03_afp"),
            _a("cmf.pdf", "04_cmf"),
            _a("CODEUDOR_liq_abril.pdf", "05_codeudor"),
        ]
        doc = {"nombre": "X", "codeudor_nombre": "Aval",
               "credit_request": {"client_type": "dependiente", "codeudor_tipo": "dependiente"}}
        val = v.validar_documentos("dependiente", titular, ahora=AHORA)
        val = v.anexar_codeudor(doc, titular, val, ahora=AHORA)
        blob = " ".join(_msgs(val)).lower()
        assert "codeudor" in blob
        assert "cédula" in blob or "cedula" in blob

    def test_sin_codeudor_no_alerta(self):
        archivos = [_a("cedula.pdf", "01_cedula"), _a("cmf.pdf", "04_cmf")]
        val = v.validar_documentos("desconocido", archivos, ahora=AHORA)
        val = v.anexar_codeudor({"credit_request": {}}, archivos, val, ahora=AHORA)
        assert not any(a.get("codeudor") for a in val["alertas"])


class TestKeywords:
    def test_dai_es_boletas(self):
        assert fsvc.cat_de_texto("DAI_resumen_anual.pdf") == "boletas"

    def test_f22_es_imp_renta(self):
        assert fsvc.cat_de_texto("formulario_F22.pdf") == "imp_renta"

    def test_f29_detectable(self):
        assert fsvc.cat_de_texto("F29_marzo.pdf") == "f29"

    def test_carpeta_tributaria(self):
        assert fsvc.cat_de_texto("carpeta tributaria SII.pdf") == "imp_renta"
        assert fsvc.cat_de_archivo("carpeta_tributaria_f22.pdf", "02_impuesto_renta") == "imp_renta"
        assert fsvc.es_combinado("Carpeta_JuanPerez.pdf") is True
        assert fsvc.es_combinado("carpeta_tributaria.pdf") is False

    def test_required_cats_mixto(self):
        cats = fsvc.required_cats("mixto")
        assert "liquidacion" in cats and "boletas" in cats and "imp_renta" in cats
        assert "afp" in cats
        solo_ind = fsvc.required_cats("independiente")
        assert "liquidacion" not in solo_ind
        assert "afp" not in solo_ind
