"""Supercarpeta: unicidad RUT/rol, expediente centralizado y payload Concreces (sin Mongo)."""
import sys
from pathlib import Path

BACKEND_DIR = str(Path(__file__).resolve().parents[1])
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import expediente_identidad as e  # noqa: E402

RUT_T = "11.111.111-1"
RUT_C = "22.222.222-2"
ROL = "12345-67"


def _fd(**over):
    base = {
        "id": "f1",
        "nombre": "Cliente Prueba",
        "nombre_completo": "Cliente Prueba",
        "rut": RUT_T,
        "codeudor_rut": RUT_C,
        "codeudor_nombre": "Codeudor Uno",
        "tipo_operacion": "usada",
        "inmobiliaria": "",
        "proyecto": "",
        "notaria": "Notaría Santiago",
        "set_credito_estado": "firmado",
        "set_credito_at": "2026-08-01T10:00:00",
        "set_firmado": True,
        "dps_recibido_at": "2026-07-20T12:00:00",
        "tasacion_informe_recibido_at": "2026-07-15T09:00:00",
        "estudio_recibido_at": "2026-07-18T11:00:00",
        "tasacion_ocr": {"rol_avaluo": ROL, "valor_uf": 2500, "comuna": "Las Condes"},
        "estudio_ocr": {"fojas": "45231", "numero": "43651", "anio": "2001", "cbr": "Santiago"},
        "escritura_ocr": {"notaria": "Pedro Pérez", "repertorio": "12890"},
        "datos_financieros": {
            "renta_liquida": 1800,
            "renta_codeudor": 900,
            "monto_credito": 2000,
            "valor_propiedad": 2500,
            "plazo_anos": 20,
            "con_subsidio": False,
            "tipo_vivienda": "usada",
            "deuda_cmf": 0.28,
        },
        "perfil_consolidado": {"email": "a@b.cl", "telefono": "912345678", "comuna": "Las Condes",
                               "direccion": "Los Leones 123"},
        "archivos": [
            "01_cedula/01_Cedula.pdf",
            "02_liquidaciones/liq_abril.pdf",
            "04_cmf/informe_cmf.pdf",
            "05_codeudor/CODEUDOR_cedula.pdf",
            "99_otros/DPS_firmado.pdf",
            "99_otros/carta_aprobacion.pdf",
        ],
        "reparos_alertas": [{"texto": "Falta certificado de hipotecas"}],
    }
    base.update(over)
    return base


class TestClaves:
    def test_rut_valido_y_rol(self):
        assert e.dv_ok(RUT_T)
        assert e.dv_ok(RUT_C)
        assert e.norm_rol("12.345 - 67") == "12345-67"
        assert e.clasificar_clave(RUT_T)["tipo"] == "rut"
        assert e.clasificar_clave(ROL)["tipo"] == "rol"

    def test_identidad_lee_codeudor_de_carpeta_y_rol_de_tasacion(self):
        ident = e.identidad_de_folder(_fd(perfil_consolidado={}))
        assert ident["rut_codeudor_norm"] == e.norm_rut(RUT_C)
        assert ident["rol_norm"] == ROL
        assert ident["fuentes"]["rut_codeudor"] == "folder.codeudor_rut"
        assert ident["fuentes"]["rol"] == "tasacion_ocr"

    def test_cruzada_rechaza_mismo_rut(self):
        ident = e.identidad_de_folder(_fd(codeudor_rut=RUT_T))
        v = e.validar_identidad(ident)
        assert v["ok"] is False
        assert v["ruts_distintos"] is False
        assert any("codeudor" in a.lower() for a in v["alertas"])

    def test_cruzada_dv_invalido(self):
        ident = e.identidad_de_folder(_fd(rut="11.111.111-2"))
        v = e.validar_identidad(ident)
        assert v["titular_dv_ok"] is False
        assert v["ok"] is False

    def test_rol_desalineado_entre_fuentes(self):
        ident = e.identidad_de_folder(_fd(), extras={
            "compromiso": {"datos": {"propiedad": {"rol_avaluo": "99999-01"}}},
        })
        v = e.validar_identidad(ident)
        assert v["rol_consistente"] is False
        assert any("desalineado" in a.lower() for a in v["alertas"])

    def test_rol_consistente(self):
        ident = e.identidad_de_folder(_fd(datos_financieros={"rol_avaluo": ROL}))
        v = e.validar_identidad(ident)
        assert v["rol_consistente"] is True
        assert v["ruts_distintos"] is True

    def test_unicidad_mismo_rol_otra_carpeta(self):
        ident = e.identidad_de_folder(_fd())
        conflictos = e.conflictos_unicidad(ident, [
            {"id": "f2", "rut": RUT_C, "rol_avaluo": ROL},
        ])
        tipos = {c["tipo"] for c in conflictos}
        assert "rol_avaluo" in tipos
        assert "codeudor_es_titular_de_otra" in tipos


class TestExpediente:
    def test_claves_historicas_siguen(self):
        exp = e.construir_expediente(_fd())
        for k in ("titular", "codeudor", "propiedad", "hitos_legales", "documentos"):
            assert k in exp
        assert exp["codeudor"]["presente"] is True
        assert e.norm_rut(exp["codeudor"]["rut"]) == e.norm_rut(RUT_C)
        assert exp["propiedad"]["rol"] == ROL

    def test_contenido_centralizado(self):
        exp = e.construir_expediente(_fd(), extras={
            "gastos": {"total": 12.5, "items": [{"glosa": "CBR", "uf": 4}],
                       "enviado_en": "2026-08-10", "to": "c@x.cl"},
            "hilo_estudio": [{"asunto": "Informe de títulos", "hito": "estudio_titulo"}],
        })
        assert exp["gastos_operacionales"]["total"] == 12.5
        assert exp["tasacion"]["tipo_vivienda"] == "usada"
        assert exp["tasacion"]["valor_uf"] == 2500
        assert exp["estudio_titulos"]["hilo"]
        assert "Falta certificado" in exp["estudio_titulos"]["reparos"]
        assert exp["polizas_seguros"]["dps_recibido"] is True
        assert any("DPS" in a for a in exp["polizas_seguros"]["archivos"])
        assert exp["serie_credito"]["firmado"] is True
        assert exp["perfil_documental"]["por_categoria"].get("cedula")
        assert exp["perfil_documental"]["codeudor"]

    def test_no_inventa_tipo_vivienda(self):
        fd = _fd(tipo_operacion="", datos_financieros={"renta_liquida": 1})
        fd["tasacion_ocr"] = {"rol_avaluo": ROL}
        assert e.tipo_vivienda_de(fd) == ""
        assert e.construir_expediente(fd)["tasacion"]["tipo_vivienda"] == ""

    def test_codeudor_sin_simulacion(self):
        exp = e.construir_expediente(_fd())
        assert exp["codeudor"]["presente"] is True
        assert exp["claves"]["rut_codeudor_norm"] == e.norm_rut(RUT_C)


class TestPayload:
    def test_autofill_concreces_sin_envio(self):
        exp = e.construir_expediente(_fd())
        p = e.payload_concreces(exp)
        mesa = p["secciones"]["Ingreso_Mesa"]
        assert e.norm_rut(mesa["rut_titular"]) == e.norm_rut(RUT_T)
        assert e.norm_rut(mesa["rut_codeudor"]) == e.norm_rut(RUT_C)
        assert mesa["monto_credito_uf"] == 2000
        assert p["secciones"]["Tasacion"]["rol_propiedad"] == ROL
        assert p["envio"] == "manual"
        assert p["origen"] == "expediente_unico"
        assert "Riesgo" in p["secciones"]
        assert "Escrituracion" in p["secciones"]

    def test_codeudor_opcional_no_bloquea(self):
        fd = _fd(codeudor_rut="", codeudor_nombre="")
        exp = e.construir_expediente(fd)
        p = e.payload_concreces(exp)
        assert "rut_codeudor" not in p["faltantes"]["Ingreso_Mesa"]

    def test_filtro_busca_las_tres_claves(self):
        fr = e.filtro_busqueda(RUT_C)
        campos = {list(c.keys())[0] for c in fr["$or"]}
        assert "codeudor_rut_norm" in campos
        frol = e.filtro_busqueda(ROL)
        campos_r = {list(c.keys())[0] for c in frol["$or"]}
        assert "rol_norm" in campos_r
        ff = e.filtro_folder_por_clave(ROL)
        assert any("tasacion_ocr.rol_avaluo" in x for x in ff["$or"])
