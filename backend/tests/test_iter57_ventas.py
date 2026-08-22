"""Iteración 57 — Módulo VENTAS + Renombre Daniela + regresión Victoria/Admin."""
import os
import io
import pytest
import requests
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

BASE = "http://localhost:8001"  # localhost para evitar edge timeouts
PREVIEW = os.environ.get("PREVIEW_URL", "https://espejo-hibrido.preview.emergentagent.com")

RUTS = ("31.111.111-1", "32.222.222-2", "33.333.333-3")
NOMBRES = ("QA VENTAS A", "QA VENTAS B", "QA VENTAS C")


def _login(rut, password, base=BASE):
    r = requests.post(f"{base}/api/auth/login",
                      json={"rut": rut, "password": password}, timeout=90)
    return r


@pytest.fixture(scope="module")
def tokens():
    admin = _login("administrador", "141617575").json()["token"]
    yer = _login("yerile.barrera@centralmutuos.cl", "Yerile2024").json()["token"]
    dey = _login("deysi.salazar@centralmutuos.cl", "Deysi2024").json()["token"]
    dan = _login("daniela.galindo@centralmutuos.cl", "Daniela2024").json()["token"]
    return {"admin": admin, "yerile": yer, "deysi": dey, "daniela": dan}


def H(t):
    return {"Authorization": f"Bearer {t}"}


# ══════════ FASE 0: reset round-robin y limpieza previa ══════════
@pytest.fixture(scope="module", autouse=True)
def reset_and_cleanup(tokens):
    # Reset del round-robin via mongo (borrar "ultimo")
    from pymongo import MongoClient
    mc = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    dbn = os.environ.get("DB_NAME", "test_database")
    db = mc[dbn]
    db.config.update_one({"_key": "ventas_rr"}, {"$unset": {"ultimo": ""}}, upsert=True)
    # borrar clientes QA previos
    for rut in RUTS:
        cli = db.victoria_clientes.find_one({"rut": rut})
        if cli:
            db.victoria_docs.delete_many({"cliente_id": cli["id"]})
            db.victoria_avisos.delete_many({"cliente_id": cli["id"]})
            db.victoria_eventos.delete_many({"cliente_id": cli["id"]})
            db.victoria_clientes.delete_one({"id": cli["id"]})
    yield
    # Cleanup final: borrar QA VENTAS A/B/C creados en este test
    for rut in RUTS:
        cli = db.victoria_clientes.find_one({"rut": rut})
        if cli:
            db.victoria_docs.delete_many({"cliente_id": cli["id"]})
            db.victoria_avisos.delete_many({"cliente_id": cli["id"]})
            db.victoria_eventos.delete_many({"cliente_id": cli["id"]})
            db.victoria_clientes.delete_one({"id": cli["id"]})
    db.config.update_one({"_key": "ventas_rr"}, {"$unset": {"ultimo": ""}}, upsert=True)
    mc.close()


# ══════════ BACKEND round-robin ══════════
class TestRoundRobin:
    def test_1_solicitud_a_yerile(self, tokens):
        r = requests.post(f"{BASE}/api/ventas/solicitudes",
                          json={"nombre": NOMBRES[0], "rut": RUTS[0], "entrega_inmediata": True},
                          headers=H(tokens["yerile"]), timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["asignado"] is True
        assert "Yerile" in data["ejecutivo"], data
        pytest.first_cid = data["cliente_id"]

    def test_2_solicitud_b_deysi(self, tokens):
        r = requests.post(f"{BASE}/api/ventas/solicitudes",
                          json={"nombre": NOMBRES[1], "rut": RUTS[1], "entrega_inmediata": True},
                          headers=H(tokens["yerile"]), timeout=30)
        assert r.status_code == 200, r.text
        assert "Deysi" in r.json()["ejecutivo"], r.json()

    def test_3_solicitud_c_yerile(self, tokens):
        r = requests.post(f"{BASE}/api/ventas/solicitudes",
                          json={"nombre": NOMBRES[2], "rut": RUTS[2], "entrega_inmediata": True},
                          headers=H(tokens["yerile"]), timeout=30)
        assert r.status_code == 200, r.text
        assert "Yerile" in r.json()["ejecutivo"], r.json()

    def test_4_sin_entrega_inmediata(self, tokens):
        r = requests.post(f"{BASE}/api/ventas/solicitudes",
                          json={"nombre": "QA VENTAS D", "rut": "34.444.444-4",
                                "entrega_inmediata": False},
                          headers=H(tokens["yerile"]), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["asignado"] is False
        assert "NO cumple" in d["mensaje"]
        # cleanup: borrar ese cliente inmediatamente
        from pymongo import MongoClient
        mc = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        dbn = os.environ.get("DB_NAME", "test_database")
        mc[dbn].victoria_clientes.delete_one({"id": d["cliente_id"]})
        mc.close()

    def test_5_sin_rut(self, tokens):
        r = requests.post(f"{BASE}/api/ventas/solicitudes",
                          json={"nombre": "QA SIN RUT"},
                          headers=H(tokens["yerile"]), timeout=30)
        assert r.status_code == 400


# ══════════ BACKEND paneles ══════════
class TestPaneles:
    def test_panel_yerile(self, tokens):
        r = requests.get(f"{BASE}/api/ventas/panel/yerile",
                         headers=H(tokens["yerile"]), timeout=30)
        assert r.status_code == 200
        d = r.json()
        # 2 QA VENTAS asignados a Yerile (A y C)
        ruts_yerile = [c["rut"] for c in d["clientes"] if c["nombre"].startswith("QA VENTAS")]
        assert set(ruts_yerile) == {RUTS[0], RUTS[2]}, ruts_yerile
        assert d["kpis"]["asignados"] >= 2

    def test_panel_deysi(self, tokens):
        r = requests.get(f"{BASE}/api/ventas/panel/deysi",
                         headers=H(tokens["deysi"]), timeout=30)
        assert r.status_code == 200
        d = r.json()
        ruts_deysi = [c["rut"] for c in d["clientes"] if c["nombre"].startswith("QA VENTAS")]
        assert set(ruts_deysi) == {RUTS[1]}, ruts_deysi

    def test_panel_inexistente(self, tokens):
        r = requests.get(f"{BASE}/api/ventas/panel/inexistente",
                         headers=H(tokens["admin"]), timeout=30)
        assert r.status_code == 404

    def test_panel_sin_token(self):
        r = requests.get(f"{BASE}/api/ventas/panel/yerile", timeout=30)
        assert r.status_code in (401, 403)


# ══════════ BACKEND gestión ══════════
class TestGestion:
    def _cid_yerile(self, tokens):
        r = requests.get(f"{BASE}/api/ventas/panel/yerile",
                         headers=H(tokens["yerile"]), timeout=30).json()
        for c in r["clientes"]:
            if c["rut"] == RUTS[0]:
                return c["id"]
        return None

    def test_contacto_sin_nota(self, tokens):
        cid = self._cid_yerile(tokens)
        r = requests.post(f"{BASE}/api/ventas/clientes/{cid}/contacto-registro",
                          json={"canal": "llamada"},
                          headers=H(tokens["yerile"]), timeout=30)
        assert r.status_code == 400

    def test_contacto_ok(self, tokens):
        cid = self._cid_yerile(tokens)
        r = requests.post(f"{BASE}/api/ventas/clientes/{cid}/contacto-registro",
                          json={"canal": "llamada", "nota": "Primer contacto QA iter57"},
                          headers=H(tokens["yerile"]), timeout=30)
        assert r.status_code == 200, r.text
        # verificar aparece en panel como ultimo_contacto
        panel = requests.get(f"{BASE}/api/ventas/panel/yerile",
                             headers=H(tokens["yerile"]), timeout=30).json()
        c = next(x for x in panel["clientes"] if x["id"] == cid)
        assert c["ultimo_contacto"] is not None
        assert c["ultimo_contacto"]["nota"] == "Primer contacto QA iter57"

    def test_estado_invalido(self, tokens):
        cid = self._cid_yerile(tokens)
        r = requests.put(f"{BASE}/api/ventas/clientes/{cid}/estado",
                         json={"estado": "cualquier_cosa"},
                         headers=H(tokens["yerile"]), timeout=30)
        assert r.status_code == 400

    def test_estado_ok(self, tokens):
        cid = self._cid_yerile(tokens)
        r = requests.put(f"{BASE}/api/ventas/clientes/{cid}/estado",
                         json={"estado": "esperando_documentos"},
                         headers=H(tokens["yerile"]), timeout=30)
        assert r.status_code == 200
        assert r.json()["estado"] == "esperando_documentos"

    def test_reporte_admin(self, tokens):
        r = requests.get(f"{BASE}/api/ventas/reporte",
                         headers=H(tokens["admin"]), timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "yerile" in d["ejecutivos"] and "deysi" in d["ejecutivos"]
        y = d["ejecutivos"]["yerile"]
        assert y["total"] >= 2
        assert "faltantes_total" in y
        # cada cliente resumen tiene dias_gestion
        assert all("dias_gestion" in c for c in y["clientes"])


# ══════════ BACKEND Regla de Oro 15 en Ventas ══════════
class TestReglaOroEnVentas:
    def test_subir_pdf_rut_distinto_409(self, tokens):
        # Buscar cliente QA VENTAS A (RUT 31.111.111-1)
        panel = requests.get(f"{BASE}/api/ventas/panel/yerile",
                             headers=H(tokens["yerile"]), timeout=30).json()
        cid = next(c["id"] for c in panel["clientes"] if c["rut"] == RUTS[0])
        # generar PDF con reportlab con RUT DISTINTO
        try:
            from reportlab.pdfgen import canvas
        except ImportError:
            pytest.skip("reportlab no instalado")
        buf = io.BytesIO()
        cpdf = canvas.Canvas(buf)
        cpdf.drawString(100, 800, "CERTIFICADO DE TASACION")
        cpdf.drawString(100, 780, "RUT: 99.999.999-9")  # distinto al del cliente
        cpdf.drawString(100, 760, "Nombre: OTRA PERSONA DISTINTA")
        cpdf.save()
        pdf_bytes = buf.getvalue()
        r = requests.post(f"{BASE}/api/victoria/clientes/{cid}/subir",
                          headers=H(tokens["yerile"]),
                          files={"file": ("tasacion_qa.pdf", pdf_bytes, "application/pdf")},
                          data={"tipo": "tasacion"}, timeout=60)
        assert r.status_code == 409, f"esperaba 409, got {r.status_code}: {r.text[:400]}"
        detail = r.json().get("detail", {})
        assert detail.get("codigo") == "VALIDACION_BLOQUEADA"


# ══════════ BACKEND regresión Daniela + Victoria antiguo ══════════
class TestRenombreDaniela:
    def test_login_daniela_ok(self, tokens):
        assert tokens["daniela"], "Daniela login falló"

    def test_login_victoria_antiguo_falla(self):
        r = _login("victoria.vilches@centralmutuos.cl", "Victoria2024")
        assert r.status_code in (400, 401, 403), r.status_code

    def test_daniela_solo_modulo_victoria(self, tokens):
        # verificar payload del login
        r = _login("daniela.galindo@centralmutuos.cl", "Daniela2024")
        assert r.status_code == 200
        d = r.json()
        assert d.get("solo_modulo") == "victoria"


# ══════════ BACKEND demos ══════════
class TestDemos:
    def test_demo_victoria(self, tokens):
        r = requests.get(f"{BASE}/api/victoria/demo/video?modulo=victoria",
                         headers=H(tokens["admin"]), timeout=30)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("video/mp4")
        assert len(r.content) > 1_000_000

    def test_demo_ventas(self, tokens):
        r = requests.get(f"{BASE}/api/victoria/demo/video?modulo=ventas",
                         headers=H(tokens["admin"]), timeout=30)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("video/mp4")
        assert len(r.content) > 500_000
