"""Iteración 53 — Regresión backend ConCreces (Módulo Victoria)."""
import os
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://espejo-hibrido.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json={"rut": "administrador", "password": "141617575"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def H(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def mongo():
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    cli = MongoClient(os.environ["MONGO_URL"])
    return cli[os.environ.get("DB_NAME", "test_database")]


@pytest.fixture(scope="module")
def test_folder(mongo):
    """Crea una carpeta de PRUEBA aislada. Se limpia al terminar."""
    fid = f"TEST-CONCRECES-{uuid.uuid4().hex[:8]}"
    doc = {
        "id": fid,
        "nombre": "TEST_ConCreces Cliente Prueba",
        "rut": "11111111-1",
        "descartada": False,
        "archivos": [
            "cedula_frente.pdf", "cedula_reverso.pdf",
            "liquidacion_enero.pdf", "liquidacion_febrero.pdf", "liquidacion_marzo.pdf",
            "liquidacion_abril.pdf", "liquidacion_mayo.pdf", "liquidacion_junio.pdf",
            "afp_certificado_24m.pdf", "dps_firmado.pdf",
            "informe_deuda_cmf.pdf",
        ],
    }
    mongo.folders.insert_one(doc)
    yield fid
    # Cleanup
    mongo.folders.delete_many({"id": fid})
    mongo.concreces_flujo.delete_many({"folder_id": fid})
    mongo.concreces_estado.delete_many({"folder_id": fid})
    mongo.concreces_cargas.delete_many({"folder_id": fid})


# --- 1) Regresión rápida: reglas de oro ---
def test_reglas_oro_total_10(H):
    r = requests.get(f"{API}/concreces/reglas-oro", headers=H, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] == 10, f"Expected 10 rules, got {data['total']}"
    claves = {x["norma_clave"] for x in data["reglas"]}
    assert claves == {f"ORO_CONCRECES_{i}" for i in range(1, 11)}


# --- 2) Flujo e2e ---
def test_flujo_get_crea_flujo_y_pasos(H, test_folder):
    r = requests.get(f"{API}/concreces/flujo/{test_folder}", headers=H, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["pasos"]) == 6
    assert data["siguiente"] is not None
    # auto-detección debería marcar varios items ANEXO I
    items = {i["clave"]: i["ok"] for i in data["checklist_items"]}
    assert items["ci"] is True  # cedula detectada
    assert items["liq3"] is True


def test_resolucion_sin_checklist_403(H, mongo):
    # Carpeta vacía → checklist incompleto
    fid = f"TEST-CONC-EMPTY-{uuid.uuid4().hex[:6]}"
    mongo.folders.insert_one({"id": fid, "nombre": "TEST vacío", "rut": "22222222-2", "descartada": False, "archivos": []})
    try:
        # Forzar flujo (sin checklist marcado)
        requests.get(f"{API}/concreces/flujo/{fid}", headers=H, timeout=15)
        r = requests.post(f"{API}/concreces/flujo/{fid}/resolucion",
                          headers=H, json={"resolucion": "aprobado"}, timeout=15)
        assert r.status_code == 403, r.text
        assert "REGLA DE ORO CONCRECES 1" in r.text
    finally:
        mongo.folders.delete_many({"id": fid})
        mongo.concreces_flujo.delete_many({"folder_id": fid})


def test_put_checklist_completo_y_politica_ok(H, test_folder):
    payload = {
        "tipo_trabajador": "dependiente",
        "checklist": {"ci": True, "permanencia": True, "dps": True, "liq3": True, "liq6": True, "afp24": True, "deudas": True},
        "compra": {
            "fecha_entrega": "2026-06-01", "monto_vivienda": 2500, "monto_credito": 1800,
            "monto_subsidio": 200, "monto_pie": 500, "inmobiliaria": "Inmob TEST",
            "proyecto": "Proyecto TEST", "comuna": "Santiago",
        },
        "politica": {
            "renta_uf": 60, "dividendo_uf": 12, "carga_financiera_pct": 38,
            "valor_venta_uf": 2500, "tasacion_uf": 2400, "monto_credito_uf": 1800,
            "plazo_anios": 30, "edad": 40,
        },
        "formularios": {f: True for f in [
            "Estado de Situación / Solicitud de Crédito",
            "Solicitud incorporación Seguro Incendio y Sismo", "DPS",
            "Autorización para contratar seguros", "Solicitud incorporación seguro Cesantía",
            "Formulario condiciones generales de cobranza externa",
            "Formulario autorización solicitud antecedentes endeudamiento",
            "Formulario Persona Expuesta Políticamente", "Declaración DFL2",
        ]},
        "gop": {"pagado": True, "socio": ""},
    }
    r = requests.put(f"{API}/concreces/flujo/{test_folder}", headers=H, json=payload, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    for c in data["politica_checks"]:
        assert c["ok"] is True, f"Check {c['regla']} debería ok=true, got {c['ok']} ({c['detalle']})"


def test_resolucion_aprobado_carta(H, test_folder):
    r = requests.post(f"{API}/concreces/flujo/{test_folder}/resolucion",
                      headers=H, json={"resolucion": "aprobado", "detalle": "TEST"}, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["carta_titulo"] == "Carta de Aprobación"
    assert "Carta de Aprobación" in data["carta_html"]


def test_revision_html_y_listo(H, test_folder):
    r = requests.get(f"{API}/concreces/flujo/{test_folder}/revision", headers=H, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "Documento de Revisión ConCreces" in data["html"]
    assert data["listo_para_enviar"] is True, f"validaciones: {data['validaciones']}"


def test_enviar_sin_confirmado_400(H, test_folder):
    r = requests.post(f"{API}/concreces/flujo/{test_folder}/enviar",
                      headers=H, json={}, timeout=15)
    assert r.status_code == 400


def test_enviar_confirmado_ok(H, test_folder, mongo):
    r = requests.post(f"{API}/concreces/flujo/{test_folder}/enviar",
                      headers=H, json={"confirmado": True}, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    est = mongo.concreces_estado.find_one({"folder_id": test_folder})
    assert est and est["estado"] == "enviado"


def test_reparo_y_subsanar(H, test_folder, mongo):
    r = requests.post(f"{API}/concreces/flujo/{test_folder}/reparo",
                      headers=H, json={"detalle": "Falta timbre notaría"}, timeout=15)
    assert r.status_code == 200
    rid = r.json()["reparo"]["id"]
    est = mongo.concreces_estado.find_one({"folder_id": test_folder})
    assert est["estado"] == "reparado"
    r2 = requests.post(f"{API}/concreces/flujo/{test_folder}/subsanar/{rid}", headers=H, timeout=15)
    assert r2.status_code == 200
    est2 = mongo.concreces_estado.find_one({"folder_id": test_folder})
    assert est2["estado"] == "enviado"


# --- 3) Validación política negativa ---
def test_politica_invalida_marca_ok_false(H, mongo):
    fid = f"TEST-CONC-POL-{uuid.uuid4().hex[:6]}"
    mongo.folders.insert_one({
        "id": fid, "nombre": "TEST política mala", "rut": "33333333-3", "descartada": False,
        "archivos": ["cedula.pdf", "liquidacion.pdf", "afp.pdf", "dps.pdf", "cmf.pdf"],
    })
    try:
        payload = {
            "tipo_trabajador": "dependiente",
            "checklist": {"ci": True, "permanencia": True, "dps": True, "liq3": True, "liq6": True, "afp24": True, "deudas": True},
            "compra": {k: "x" for k in ["fecha_entrega", "monto_vivienda", "monto_credito", "monto_subsidio",
                                        "monto_pie", "inmobiliaria", "proyecto", "comuna"]},
            "politica": {
                "renta_uf": 60, "dividendo_uf": 25,   # 41.7% > 30%
                "carga_financiera_pct": 38,
                "valor_venta_uf": 1000, "tasacion_uf": 1000,
                "monto_credito_uf": 500,   # < 700
                "plazo_anios": 30, "edad": 40,
            },
        }
        r = requests.put(f"{API}/concreces/flujo/{fid}", headers=H, json=payload, timeout=15)
        assert r.status_code == 200
        checks = {c["regla"]: c for c in r.json()["politica_checks"]}
        assert checks["Dividendo/renta ≤ 30%"]["ok"] is False
        assert checks["Monto mínimo UF 700"]["ok"] is False
        # Revision no debería estar lista
        rev = requests.get(f"{API}/concreces/flujo/{fid}/revision", headers=H, timeout=15).json()
        assert rev["listo_para_enviar"] is False
    finally:
        mongo.folders.delete_many({"id": fid})
        mongo.concreces_flujo.delete_many({"folder_id": fid})
