"""Iteration 8 backend tests: fecha_entrega, actividad-terminada, tasacion HTML fields, gastos defaults."""
import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://risk-assess-17.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
ERNESTO_FID = "7a510501-b702-4707-bc10-b1b3d4e8868a"


# --- actividad-terminada ---
def test_actividad_terminada_tasacion_true_then_false_then_invalid():
    # Mark terminado
    r = requests.patch(f"{API}/clientes/folders/{ERNESTO_FID}/actividad-terminada",
                       json={"tipo": "tasacion", "terminado": True}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["campo"] == "tasacion_terminado_at"
    assert data["valor"] and "T" in data["valor"]  # ISO
    # Verify persisted via GET folders
    g = requests.get(f"{API}/clientes/folders", params={"q": "ernesto"}, timeout=90)
    assert g.status_code == 200
    folders = g.json().get("folders", [])
    e = next((f for f in folders if f.get("id") == ERNESTO_FID), None)
    assert e is not None
    assert e.get("tasacion_terminado_at")

    # Unmark
    r2 = requests.patch(f"{API}/clientes/folders/{ERNESTO_FID}/actividad-terminada",
                        json={"tipo": "tasacion", "terminado": False}, timeout=30)
    assert r2.status_code == 200
    assert r2.json()["valor"] is None

    # Invalid tipo
    r3 = requests.patch(f"{API}/clientes/folders/{ERNESTO_FID}/actividad-terminada",
                        json={"tipo": "bogus", "terminado": True}, timeout=30)
    assert r3.status_code == 400


# --- fecha_entrega on datos-financieros ---
def test_fecha_entrega_patch_and_read():
    # Set futura
    r = requests.patch(f"{API}/clientes/folders/{ERNESTO_FID}/datos-financieros",
                       json={"fecha_entrega": "futura"}, timeout=30)
    assert r.status_code == 200, r.text

    g = requests.get(f"{API}/clientes/folders/{ERNESTO_FID}/datos-financieros", timeout=30)
    assert g.status_code == 200
    assert (g.json().get("datos_financieros") or {}).get("fecha_entrega") == "futura"

    # Restore inmediata
    r2 = requests.patch(f"{API}/clientes/folders/{ERNESTO_FID}/datos-financieros",
                        json={"fecha_entrega": "inmediata"}, timeout=30)
    assert r2.status_code == 200
    g2 = requests.get(f"{API}/clientes/folders/{ERNESTO_FID}/datos-financieros", timeout=30)
    assert (g2.json().get("datos_financieros") or {}).get("fecha_entrega") == "inmediata"


# --- tasacion HTML preview with new fields ---
def test_tasacion_preview_contains_new_fields():
    payload = {
        "confirm": False,
        "nombre": "Cliente Test",
        "rut": "11.111.111-1",
        "direccion": "Av Test 123",
        "unidad": "Depto 1204",
        "comuna": "La Florida",
        "ciudad": "Santiago",
        "rol_avaluo": "1234-56",
        "valor_uf": "3000",
        "valor_esperado_uf": "3300",
        "carta_adjunta": True,
        "modalidad": "usada",
        "tipo": "Definitiva",
    }
    r = requests.post(f"{API}/tasacion/enviar", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json().get("body", "")
    for needle in ["N° de unidad / depto", "Depto 1204", "Comuna", "La Florida",
                   "Ciudad", "Santiago", "Rol de Avalúo Fiscal", "1234-56",
                   "Valor esperado de tasación (UF)", "3300",
                   "Se adjunta carta de aprobación"]:
        assert needle in body, f"Missing '{needle}' in tasacion body"


# --- gastos defaults datos_pago ---
def test_gastos_defaults_datos_pago():
    r = requests.get(f"{API}/gastos-operacionales/defaults", timeout=30)
    assert r.status_code == 200
    dp = r.json().get("datos_pago") or {}
    assert dp.get("nombre") == "MUTUARIAS Y LEASING LIMITADA"
    assert dp.get("rut") == "77.771.552-6"
    assert dp.get("banco") == "Mercado Pago"
    assert dp.get("tipo_cuenta") == "Cuenta Vista"
    assert dp.get("numero_cuenta") == "1030937838"
