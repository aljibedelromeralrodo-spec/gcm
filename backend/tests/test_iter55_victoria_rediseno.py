"""Iteración 55 — Rediseño Módulo Victoria (dashboard KPIs, preview docs,
revisión aceptar/rechazar, contactabilidad, correo, tipos, despacho).
Se ejecuta contra localhost:8001 para evitar el edge timeout de Cloudflare (60s)."""
import io
import os
import pytest
import requests
from reportlab.pdfgen import canvas

BASE = "http://localhost:8001/api"
VICTORIA_EMAIL = "victoria.vilches@centralmutuos.cl"
VICTORIA_PASS = "Victoria2024"


def _pdf(lineas):
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 780
    for ln in lineas:
        c.drawString(60, y, ln)
        y -= 22
    c.save()
    return buf.getvalue()


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/auth/login", json={"rut": VICTORIA_EMAIL, "password": VICTORIA_PASS}, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("solo_modulo") == "victoria"
    assert d.get("clave_temporal") is True
    return d["token"]


@pytest.fixture(scope="module")
def H(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def cliente(H):
    """Crea el cliente TEST_QA_ITER55 (bloque atómico) y limpia al final."""
    r = requests.post(f"{BASE}/victoria/clientes", headers=H,
                      json={"nombre": "TEST_QA_ITER55 CLIENTE", "rut": "18.765.432-1"}, timeout=30)
    assert r.status_code == 200, r.text
    cid = r.json()["cliente"]["id"]
    yield cid
    # cleanup
    try:
        from pymongo import MongoClient
        mc = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        dbn = os.environ.get("DB_NAME", "test_database")
        mc[dbn].victoria_clientes.delete_many({"id": cid})
        mc[dbn].victoria_docs.delete_many({"cliente_id": cid})
        mc[dbn].victoria_contactos.delete_many({"cliente_id": cid})
        mc[dbn].victoria_avisos.delete_many({"cliente_id": cid})
        mc[dbn].concreces_estado.delete_many({"victoria_cliente_id": cid})
    except Exception as e:
        print("cleanup warn:", e)


# ─────────── Auth & seed ───────────
class TestAuthVictoria:
    def test_login_devuelve_solo_modulo_y_clave_temporal(self, token):
        assert token and len(token) > 20

    def test_sin_token_dashboard_401(self):
        r = requests.get(f"{BASE}/victoria/dashboard", timeout=15)
        assert r.status_code in (401, 403)

    def test_cambiar_clave_valida_actual(self, H):
        # NO cambiar realmente: enviar actual mal → 400
        r = requests.post(f"{BASE}/auth/cambiar-clave", headers=H,
                          json={"clave_actual": "MAL", "clave_nueva": "Nueva12345", "confirmacion": "Nueva12345"},
                          timeout=15)
        assert r.status_code == 400
        assert "actual" in r.json().get("detail", "").lower()


# ─────────── Dashboard ───────────
class TestDashboard:
    def test_dashboard_estructura_kpis(self, H):
        r = requests.get(f"{BASE}/victoria/dashboard", headers=H, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        for key in ("kpis", "clientes", "avisos", "sin_clasificar", "tipos", "docs_requeridos"):
            assert key in d, f"falta {key}"
        for k in ("clientes_pendientes", "docs_faltantes", "validaciones_aprobadas",
                  "alertas_activas", "estado_general_pct", "despachados", "listos_envio"):
            assert k in d["kpis"]
            assert isinstance(d["kpis"][k], int)


# ─────────── Contacto ───────────
class TestContacto:
    def test_email_invalido_400(self, H, cliente):
        r = requests.put(f"{BASE}/victoria/clientes/{cliente}/contacto", headers=H,
                         json={"email": "sinarroba", "telefono": ""}, timeout=15)
        assert r.status_code == 400

    def test_guardar_contacto_persiste(self, H, cliente):
        r = requests.put(f"{BASE}/victoria/clientes/{cliente}/contacto", headers=H,
                         json={"email": "cliente.test@example.com", "telefono": "+56911112222"},
                         timeout=15)
        assert r.status_code == 200
        det = requests.get(f"{BASE}/victoria/clientes/{cliente}", headers=H, timeout=15).json()
        assert det["cliente"]["email"] == "cliente.test@example.com"
        assert det["cliente"]["telefono"] == "+56911112222"

    def test_enviar_correo_sin_email_400(self, H, cliente):
        # limpiar email primero
        requests.put(f"{BASE}/victoria/clientes/{cliente}/contacto", headers=H,
                     json={"email": "", "telefono": ""}, timeout=15)
        r = requests.post(f"{BASE}/victoria/clientes/{cliente}/enviar-correo", headers=H,
                         json={"asunto": "hola", "mensaje": "test"}, timeout=15)
        assert r.status_code == 400
        assert "correo" in r.json().get("detail", "").lower()

    def test_enviar_correo_sin_asunto_400(self, H, cliente):
        r = requests.post(f"{BASE}/victoria/clientes/{cliente}/enviar-correo", headers=H,
                         json={"email": "x@y.cl", "asunto": "", "mensaje": ""}, timeout=15)
        assert r.status_code == 400


# ─────────── Documentos: subir, preview, revisión ───────────
class TestDocumentos:
    @pytest.fixture(scope="class")
    def doc_id(self, H, cliente):
        raw = _pdf(["INFORME DE TASACION - Value Property",
                    "Cliente: TEST QA ITER55",
                    "RUT: 18.765.432-1",
                    "Rol de Avaluo: 9999-01",
                    "Direccion propiedad: Av Test 100, Santiago",
                    "Fecha: 01/06/2026",
                    "Firmado electronicamente"])
        r = requests.post(f"{BASE}/victoria/clientes/{cliente}/subir", headers=H,
                          files={"file": ("tasacion_qa55.pdf", raw, "application/pdf")},
                          data={"tipo": "tasacion"}, timeout=120)
        assert r.status_code == 200, r.text
        return r.json()["doc"]["id"]

    def test_contenido_devuelve_pdf(self, H, doc_id):
        r = requests.get(f"{BASE}/victoria/documentos/{doc_id}/contenido", headers=H, timeout=30)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"

    def test_revision_decision_invalida_400(self, H, doc_id):
        r = requests.post(f"{BASE}/victoria/documentos/{doc_id}/revision", headers=H,
                          json={"decision": "loquesea"}, timeout=15)
        assert r.status_code == 400

    def test_revision_rechazo_sin_motivo_400(self, H, doc_id):
        r = requests.post(f"{BASE}/victoria/documentos/{doc_id}/revision", headers=H,
                          json={"decision": "rechazado", "motivo": ""}, timeout=15)
        assert r.status_code == 400

    def test_reclasificar_tipo(self, H, doc_id):
        r = requests.put(f"{BASE}/victoria/documentos/{doc_id}/tipo", headers=H,
                        json={"tipo": "otro"}, timeout=30)
        assert r.status_code == 200
        assert r.json()["tipo"] == "otro"
        # dejar como tasacion nuevamente
        requests.put(f"{BASE}/victoria/documentos/{doc_id}/tipo", headers=H,
                     json={"tipo": "tasacion"}, timeout=30)

    def test_tipo_invalido_400(self, H, doc_id):
        r = requests.put(f"{BASE}/victoria/documentos/{doc_id}/tipo", headers=H,
                        json={"tipo": "ZZZ"}, timeout=15)
        assert r.status_code == 400

    def test_rechazo_excluye_de_auditoria(self, H, cliente, doc_id):
        # subir un segundo doc para que quede uno tras rechazar
        raw = _pdf(["OTRO DOC TEST QA55", "RUT: 18.765.432-1"])
        rr = requests.post(f"{BASE}/victoria/clientes/{cliente}/subir", headers=H,
                          files={"file": ("otro.pdf", raw, "application/pdf")},
                          data={"tipo": "otro"}, timeout=120).json()
        did2 = rr["doc"]["id"]
        # rechazar el segundo
        r = requests.post(f"{BASE}/victoria/documentos/{did2}/revision", headers=H,
                         json={"decision": "rechazado", "motivo": "prueba QA"}, timeout=30)
        assert r.status_code == 200
        # verificar en detalle
        det = requests.get(f"{BASE}/victoria/clientes/{cliente}", headers=H, timeout=15).json()
        found = [d for d in det["docs"] if d["id"] == did2]
        assert found and (found[0].get("revision") or {}).get("decision") == "rechazado"


# ─────────── Despacho bloqueado (Reglas de Oro) ───────────
class TestDespacho:
    def test_despacho_sin_confirmado_400(self, H, cliente):
        r = requests.post(f"{BASE}/victoria/clientes/{cliente}/despachar", headers=H,
                         json={"confirmado": False}, timeout=15)
        assert r.status_code == 400

    def test_despacho_bloqueado_por_reglas_de_oro(self, H, cliente):
        # cliente tiene sólo tasacion (faltan titulos+carpeta+simulacion) → bloqueado
        r = requests.post(f"{BASE}/victoria/clientes/{cliente}/despachar", headers=H,
                         json={"confirmado": True}, timeout=30)
        assert r.status_code == 403
        det = r.json().get("detail", "")
        assert "REGLAS DE ORO" in det.upper() or "BLOQUEA" in det.upper() or "form" in det.lower()


# ─────────── Documento envío ───────────
class TestDocumentoEnvio:
    def test_documento_envio_html(self, H, cliente):
        r = requests.get(f"{BASE}/victoria/clientes/{cliente}/documento-envio", headers=H, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "html" in d and "<html" in d["html"].lower()
        assert d["bloqueado"] is True  # falta set completo
        assert d["listo"] is False


# ─────────── Regresión admin ───────────
class TestRegresionAdmin:
    def test_login_admin_no_solo_modulo(self):
        r = requests.post(f"{BASE}/auth/login", json={"rut": "administrador", "password": "141617575"}, timeout=60)
        assert r.status_code == 200
        d = r.json()
        # admin no debe tener solo_modulo
        assert not d.get("solo_modulo")
        assert d.get("rol") == "admin"
