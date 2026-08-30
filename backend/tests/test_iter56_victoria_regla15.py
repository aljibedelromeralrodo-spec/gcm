"""Iteración 56 — Módulo Victoria: Regla de Oro 15 (validación de ingreso
irrenunciable + cuarentena + PIN), trazabilidad de datos críticos y demo.
Se ejecuta contra localhost:8001 para evitar el edge timeout Cloudflare (60s).
"""
import io
import os
import uuid
import pytest
import requests
from datetime import datetime, timezone
from reportlab.pdfgen import canvas
from pymongo import MongoClient
from _tok import tok as _login_tok

BASE = "http://localhost:8001/api"
PUB_BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://espejo-hibrido.preview.emergentagent.com").rstrip("/") + "/api"
VICTORIA_EMAIL = "victoria.vilches@centralmutuos.cl"
VICTORIA_PASS = "Victoria2024"
ADMIN_USER = "administrador"
ADMIN_PASS = "141617575"


def _pdf(lineas):
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 780
    for ln in lineas:
        c.drawString(60, y, ln)
        y -= 22
    c.save()
    return buf.getvalue()


def _mongo():
    mc = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    return mc[os.environ.get("DB_NAME", "test_database")]


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/auth/login", json={"rut": VICTORIA_EMAIL, "password": VICTORIA_PASS}, timeout=60)
    assert r.status_code == 200, r.text
    return _login_tok(r)


@pytest.fixture(scope="module")
def H(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE}/auth/login", json={"rut": ADMIN_USER, "password": ADMIN_PASS}, timeout=60)
    assert r.status_code == 200, r.text
    return _login_tok(r)


@pytest.fixture(scope="module")
def cliente(H):
    """Crea CLIENTE QA REGLA15 y limpia al final (junto con docs/avisos/eventos)."""
    r = requests.post(f"{BASE}/victoria/clientes", headers=H,
                      json={"nombre": "CLIENTE QA REGLA15", "rut": "11.111.111-1"}, timeout=30)
    assert r.status_code == 200, r.text
    c = r.json()["cliente"]
    cid = c["id"]
    yield cid
    # ── LIMPIEZA FINAL ──
    try:
        db = _mongo()
        db.victoria_clientes.delete_many({"id": cid})
        db.victoria_docs.delete_many({"$or": [{"cliente_id": cid}, {"candidato_cliente_id": cid},
                                               {"archivo": {"$regex": "^qa_"}}]})
        db.victoria_avisos.delete_many({"$or": [{"cliente_id": cid},
                                                 {"detalle": {"$regex": "qa_", "$options": "i"}}]})
        db.victoria_eventos.delete_many({"$or": [{"cliente_id": cid},
                                                  {"archivo": {"$regex": "^qa_"}}]})
        db.victoria_contactos.delete_many({"cliente_id": cid})
        db.concreces_estado.delete_many({"victoria_cliente_id": cid})
        # borrar PIN de victoria
        db.users.update_one({"codigo": VICTORIA_EMAIL}, {"$unset": {"pin_seguridad_hash": ""}})
    except Exception as e:
        print("cleanup warn:", e)


# ══════════ 1. REGLA DE ORO 15 · asociación OK y bloqueo 409 ══════════
class TestRegla15:
    def test_subir_ok_datos_coinciden(self, H, cliente):
        pdf = _pdf([
            "Informe de Tasacion",
            "Cliente: CLIENTE QA REGLA15",
            "RUT: 11.111.111-1",
            "Rol de avaluo fiscal: 5555-55",
            "Direccion: Calle Falsa 123, Santiago",
            "Fecha: 15/01/2026",
            "Firmado electronicamente",
        ])
        files = {"file": ("qa_tasacion_ok.pdf", pdf, "application/pdf")}
        data = {"tipo": "tasacion"}
        r = requests.post(f"{BASE}/victoria/clientes/{cliente}/subir",
                          headers=H, files=files, data=data, timeout=120)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body.get("forzado") is False
        assert body["doc"]["tipo"] == "tasacion"

    def test_subir_bloqueado_409_datos_no_coinciden(self, H, cliente):
        pdf = _pdf([
            "Informe de Tasacion",
            "Cliente: CLIENTE QA REGLA15",
            "RUT: 22.222.222-2",
            "Rol de avaluo fiscal: 9999-99",
            "Direccion: Otra Calle 999",
            "Fecha: 15/01/2026",
        ])
        files = {"file": ("qa_tasacion_conflicto.pdf", pdf, "application/pdf")}
        data = {"tipo": "tasacion"}
        r = requests.post(f"{BASE}/victoria/clientes/{cliente}/subir",
                          headers=H, files=files, data=data, timeout=120)
        assert r.status_code == 409, r.text
        detail = r.json().get("detail")
        assert isinstance(detail, dict), detail
        assert detail.get("codigo") == "VALIDACION_BLOQUEADA"
        assert isinstance(detail.get("fallas"), list) and len(detail["fallas"]) > 0
        assert "pin_configurado" in detail


# ══════════ 2. PIN de seguridad ══════════
class TestPin:
    def test_pin_formato_invalido(self, H):
        r = requests.post(f"{BASE}/victoria/pin", headers=H,
                          json={"pin": "12ab", "confirmacion": "12ab"}, timeout=30)
        assert r.status_code == 400, r.text

    def test_pin_crear_ok(self, H):
        # asegurar que no hay PIN previo
        _mongo().users.update_one({"codigo": VICTORIA_EMAIL}, {"$unset": {"pin_seguridad_hash": ""}})
        r = requests.post(f"{BASE}/victoria/pin", headers=H,
                          json={"pin": "2468", "confirmacion": "2468"}, timeout=30)
        assert r.status_code == 200, r.text
        u = _mongo().users.find_one({"codigo": VICTORIA_EMAIL}) or {}
        assert u.get("pin_seguridad_hash"), "PIN no persistido en db.users"

    def test_forzar_subida_pin_incorrecto(self, H, cliente):
        pdf = _pdf([
            "Informe de Tasacion",
            "RUT: 22.222.222-2",
            "Rol: 9999-99",
            "Direccion: Otra Calle 999",
        ])
        files = {"file": ("qa_forzado_incorrecto.pdf", pdf, "application/pdf")}
        data = {"tipo": "tasacion", "pin": "0000"}
        r = requests.post(f"{BASE}/victoria/clientes/{cliente}/subir",
                          headers=H, files=files, data=data, timeout=120)
        assert r.status_code == 403, r.text
        assert "pin" in (r.json().get("detail") or "").lower()

    def test_forzar_subida_pin_correcto(self, H, cliente):
        pdf = _pdf([
            "Informe de Tasacion",
            "RUT: 22.222.222-2",
            "Rol: 9999-99",
            "Direccion: Otra Calle 999",
        ])
        files = {"file": ("qa_forzado_ok.pdf", pdf, "application/pdf")}
        data = {"tipo": "tasacion", "pin": "2468"}
        r = requests.post(f"{BASE}/victoria/clientes/{cliente}/subir",
                          headers=H, files=files, data=data, timeout=120)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["ok"] is True
        assert b.get("forzado") is True

    def test_dashboard_evento_manual_forzado(self, H):
        r = requests.get(f"{BASE}/victoria/dashboard", headers=H, timeout=60)
        assert r.status_code == 200
        d = r.json()
        evs = d.get("eventos", [])
        assert any(e.get("resultado") == "manual_forzado" for e in evs), \
            f"No hay evento manual_forzado; muestreo: {[e.get('resultado') for e in evs[:5]]}"
        avs = d.get("avisos", [])
        assert any(a.get("tipo") == "forzado_manual" for a in avs), \
            f"No hay aviso forzado_manual en avisos"
        assert d.get("pin_configurado") is True


# ══════════ 3. CUARENTENA ══════════
class TestCuarentena:
    @pytest.fixture(scope="class")
    def doc_cuar_id(self, cliente):
        db = _mongo()
        did = str(uuid.uuid4())
        db.victoria_docs.insert_one({
            "id": did, "cliente_id": None, "cuarentena": True,
            "candidato_cliente_id": cliente, "candidato_nombre": "CLIENTE QA REGLA15",
            "tipo": "tasacion", "archivo": "qa_cuarentena.pdf",
            "validaciones_ingreso": [{"campo": "rut_titular", "etiqueta": "RUT del cliente principal",
                                       "ok": False, "esperado": "11.111.111-1", "detectado": "99.999.999-9"}],
            "datos": {"rut_titular": "11.111.111-1", "_legible": True,
                      "rol_avaluo": "5555-55"},
            "recibido": datetime.now(timezone.utc).isoformat(),
            "origen": "correo"
        })
        yield did

    def test_dashboard_lista_cuarentena(self, H, doc_cuar_id):
        r = requests.get(f"{BASE}/victoria/dashboard", headers=H, timeout=60)
        assert r.status_code == 200
        cuar = r.json().get("cuarentena", [])
        assert any(d.get("id") == doc_cuar_id for d in cuar), \
            "El doc en cuarentena no aparece en dashboard.cuarentena"

    def test_revalidar_asocia(self, H, cliente, doc_cuar_id):
        r = requests.post(f"{BASE}/victoria/cuarentena/{doc_cuar_id}/revalidar",
                          headers=H, json={"cliente_id": cliente}, timeout=60)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b.get("asociado") is True, b
        doc = _mongo().victoria_docs.find_one({"id": doc_cuar_id})
        assert doc.get("cliente_id") == cliente
        assert not doc.get("cuarentena")

    def test_asignar_bloqueado_para_cuarentena(self, H, cliente):
        """Un doc con cuarentena=True NO se puede asignar via /sin-clasificar/{did}/asignar → 404."""
        db = _mongo()
        did = str(uuid.uuid4())
        db.victoria_docs.insert_one({
            "id": did, "cliente_id": None, "cuarentena": True,
            "tipo": "tasacion", "archivo": "qa_no_asignar.pdf",
            "datos": {}, "recibido": datetime.now(timezone.utc).isoformat(),
            "origen": "correo"
        })
        r = requests.post(f"{BASE}/victoria/sin-clasificar/{did}/asignar", headers=H,
                          json={"cliente_id": cliente, "tipo": "tasacion"}, timeout=30)
        assert r.status_code == 404, r.text

    def test_descartar_sin_motivo(self, H, cliente):
        db = _mongo()
        did = str(uuid.uuid4())
        db.victoria_docs.insert_one({
            "id": did, "cliente_id": None, "cuarentena": True,
            "candidato_cliente_id": cliente,
            "tipo": "tasacion", "archivo": "qa_desc.pdf",
            "datos": {}, "recibido": datetime.now(timezone.utc).isoformat(),
            "origen": "correo"
        })
        r1 = requests.post(f"{BASE}/victoria/documentos/{did}/descartar",
                           headers=H, json={}, timeout=30)
        assert r1.status_code == 400, r1.text
        r2 = requests.post(f"{BASE}/victoria/documentos/{did}/descartar",
                           headers=H, json={"motivo": "qa test"}, timeout=30)
        assert r2.status_code == 200, r2.text
        dash = requests.get(f"{BASE}/victoria/dashboard", headers=H, timeout=60).json()
        assert not any(d.get("id") == did for d in dash.get("cuarentena", []))
        assert not any(d.get("id") == did for d in dash.get("sin_clasificar", []))


# ══════════ 4. TRAZABILIDAD ══════════
class TestTrazabilidad:
    def test_origen_dato_rut_titular(self, H, cliente):
        r = requests.get(f"{BASE}/victoria/clientes/{cliente}/origen-dato/rut_titular",
                         headers=H, timeout=60)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b.get("doc_id")
        assert b.get("archivo")
        assert isinstance(b.get("pagina"), int) and b["pagina"] >= 1
        assert "RUT del cliente principal" in b.get("etiqueta", "")

    def test_origen_dato_campo_invalido(self, H, cliente):
        r = requests.get(f"{BASE}/victoria/clientes/{cliente}/origen-dato/telefono",
                         headers=H, timeout=30)
        assert r.status_code == 400, r.text

    def test_documento_envio_traz_y_postmessage(self, H, cliente):
        r = requests.get(f"{BASE}/victoria/clientes/{cliente}/documento-envio",
                         headers=H, timeout=60)
        assert r.status_code == 200, r.text
        html = r.json().get("html", "")
        assert "class='traz'" in html or 'class="traz"' in html, "faltan spans .traz"
        assert "data-campo" in html
        assert "postMessage" in html
        assert "dato-trazable" in html


# ══════════ 5. DEMO ══════════
class TestDemo:
    def test_demo_video_ok(self, admin_token):
        r = requests.get(f"{BASE}/victoria/demo/video",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=60)
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("video/mp4")
        size = len(r.content)
        assert 900_000 < size < 1_000_000, f"tamaño inesperado del mp4: {size}"

    def test_demo_video_sin_token(self):
        r = requests.get(f"{BASE}/victoria/demo/video", timeout=30)
        assert r.status_code in (401, 403), r.text


# ══════════ 6. REGRESIÓN mínima ══════════
class TestRegresion:
    def test_dashboard_kpis_estructura(self, H):
        r = requests.get(f"{BASE}/victoria/dashboard", headers=H, timeout=60)
        assert r.status_code == 200
        d = r.json()
        for k in ("clientes_pendientes", "docs_faltantes", "validaciones_aprobadas",
                  "alertas_activas", "despachados", "listos_envio", "estado_general_pct"):
            assert k in d.get("kpis", {}), f"KPI ausente: {k}"
        assert isinstance(d.get("clientes"), list)

    def test_ficha_cliente_stepper(self, H, cliente):
        r = requests.get(f"{BASE}/victoria/clientes/{cliente}", headers=H, timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert d.get("cliente", {}).get("id") == cliente
        assert "formularios_auto" in d
        assert d.get("siguiente") is not None or d["cliente"].get("despachado")
