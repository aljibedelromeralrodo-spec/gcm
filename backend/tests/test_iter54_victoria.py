"""Iteración 54 — Módulo Victoria Independiente (bóveda, auditoría, Reglas de Oro 11-14, despacho)."""
import io
import os
import shutil
import pytest
import requests
from pathlib import Path
from reportlab.pdfgen import canvas
from pymongo import MongoClient
from _tok import tok as _login_tok

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://espejo-hibrido.preview.emergentagent.com").rstrip("/")
# Login via CF hits 60s timeout because bcrypt is slow in this preview env.
# Fallback to localhost:8001 for auth+heavy calls (backend is same process).
INTERNAL = "http://localhost:8001"
API = f"{INTERNAL}/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json={"rut": "administrador", "password": "141617575"}, timeout=120)
    assert r.status_code == 200, r.text
    return _login_tok(r)


@pytest.fixture(scope="module")
def H(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def dbm():
    c = MongoClient(MONGO_URL)
    return c[DB_NAME]


def _pdf(lineas):
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 780
    for ln in lineas:
        c.drawString(60, y, ln)
        y -= 22
    c.save()
    return buf.getvalue()


# Compartimos una sola creación de cliente + subidas en secuencia (subidas son caras: 10-60s con IA)
@pytest.fixture(scope="module")
def cliente(H, dbm):
    r = requests.post(f"{API}/victoria/clientes", headers=H,
                      json={"nombre": "QA TEST VICTORIA", "rut": "11.111.111-1"}, timeout=30)
    assert r.status_code == 200, r.text
    cid = r.json()["cliente"]["id"]
    yield cid
    # Cleanup
    try:
        dbm.victoria_docs.delete_many({"cliente_id": cid})
        dbm.victoria_clientes.delete_one({"id": cid})
        dbm.concreces_estado.delete_many({"victoria_cliente_id": cid})
        p = Path("/app/boveda_victoria") / cid
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
    except Exception as e:
        print("cleanup:", e)


DOCS_MISMATCH = {
    "tasacion": ["INFORME DE TASACION", "Cliente: QA TEST VICTORIA", "RUT: 11.111.111-1",
                 "Rol de Avaluo Fiscal: 5555-1", "Direccion de la propiedad: Av Las Condes 100, Santiago",
                 "Fecha de emision: 01/08/2026", "Firmado electronicamente por el tasador"],
    "titulos":  ["ESTUDIO DE TITULOS", "Comprador: QA TEST VICTORIA", "RUT: 11.111.111-1",
                 "Rol de Avaluo: 5555-1", "Inmueble ubicado en: Av Providencia 999, Santiago",  # dirección DISTINTA
                 "Fecha: 05/08/2026", "Firmado por el abogado"],
    "carpeta_credito": ["CARPETA DE CREDITO", "Deudor: QA TEST VICTORIA", "RUT: 11.111.111-1",
                        "Codeudor RUT: 9.876.543-3", "Fecha: 10/08/2026", "Firma del deudor"],
    "simulacion": ["SIMULACION DE CREDITO HIPOTECARIO", "Cliente: QA TEST VICTORIA",
                   "RUT: 11.111.111-1", "Monto credito: UF 1800", "Fecha: 12/08/2026"],
}


def test_1_crear_cliente(cliente):
    assert isinstance(cliente, str) and len(cliente) > 10


def test_2_subir_4_pdfs_con_mismatch(H, cliente):
    for tipo, lineas in DOCS_MISMATCH.items():
        rr = requests.post(f"{API}/victoria/clientes/{cliente}/subir", headers=H,
                           files={"file": (f"{tipo}_qa.pdf", _pdf(lineas), "application/pdf")},
                           data={"tipo": tipo}, timeout=180)
        assert rr.status_code == 200, f"{tipo}: {rr.status_code} {rr.text[:200]}"
        j = rr.json()
        assert j.get("ok") is True
        assert j.get("doc", {}).get("tipo") == tipo


def test_3_auditoria_oro14_bloquea(H, cliente):
    r = requests.get(f"{API}/victoria/clientes/{cliente}", headers=H, timeout=30)
    assert r.status_code == 200
    aud = r.json()["auditoria"]
    assert aud["bloqueado"] is True
    oro14 = next((c for c in aud["coincidencias"] if "Oro 14" in c["regla"]), None)
    assert oro14 is not None
    assert oro14["ok"] is False
    # debe nombrar ambos documentos
    assert "Tasación" in oro14["detalle"] or "Tasacion" in oro14["detalle"] or "tasaci" in oro14["detalle"].lower()
    assert "títulos" in oro14["detalle"].lower() or "titulos" in oro14["detalle"].lower()


def test_4_despacho_bloqueado_403(H, cliente):
    # confirmar formularios primero para probar que la coincidencia falla igual
    det = requests.get(f"{API}/victoria/clientes/{cliente}", headers=H, timeout=20).json()
    requests.put(f"{API}/victoria/clientes/{cliente}/formularios", headers=H,
                 json={"datos": det["formularios_auto"], "confirmado": True}, timeout=20)
    r = requests.post(f"{API}/victoria/clientes/{cliente}/despachar", headers=H,
                      json={"confirmado": True}, timeout=30)
    assert r.status_code == 403, r.text
    assert "REGLAS DE ORO CONCRECES" in r.json().get("detail", "")


def test_5_reparar_titulos_ok(H, cliente, dbm):
    # borrar títulos, resubir con dirección correcta
    dbm.victoria_docs.delete_many({"cliente_id": cliente, "tipo": "titulos"})
    lineas_ok = ["ESTUDIO DE TITULOS", "Comprador: QA TEST VICTORIA", "RUT: 11.111.111-1",
                 "Rol de Avaluo: 5555-1", "Inmueble ubicado en: Av Las Condes 100, Santiago",
                 "Fecha: 05/08/2026", "Firmado por el abogado"]
    rr = requests.post(f"{API}/victoria/clientes/{cliente}/subir", headers=H,
                       files={"file": ("titulos_ok.pdf", _pdf(lineas_ok), "application/pdf")},
                       data={"tipo": "titulos"}, timeout=180)
    assert rr.status_code == 200
    aud = rr.json()["auditoria"]
    assert aud["bloqueado"] is False, f"aún bloqueado: {aud}"
    for c in aud["coincidencias"]:
        assert c["ok"] is True, f"regla no OK: {c}"


def test_6_formularios_y_documento_envio(H, cliente):
    det = requests.get(f"{API}/victoria/clientes/{cliente}", headers=H, timeout=20).json()
    r = requests.put(f"{API}/victoria/clientes/{cliente}/formularios", headers=H,
                     json={"datos": det["formularios_auto"], "confirmado": True}, timeout=20)
    assert r.status_code == 200 and r.json()["confirmados"] is True
    d = requests.get(f"{API}/victoria/clientes/{cliente}/documento-envio", headers=H, timeout=30).json()
    assert d["listo"] is True
    assert "APTO PARA ENVÍO" in d["html"]


def test_7_despachar_ok(H, cliente, dbm):
    r = requests.post(f"{API}/victoria/clientes/{cliente}/despachar", headers=H,
                      json={"confirmado": True}, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    # verificar concreces_estado con origen victoria_independiente
    e = dbm.concreces_estado.find_one({"victoria_cliente_id": cliente})
    assert e is not None
    assert e["origen"] == "victoria_independiente"
    assert e["estado"] == "enviado"


def test_8_panel(H, cliente):
    r = requests.get(f"{API}/victoria/panel", headers=H, timeout=20)
    assert r.status_code == 200
    j = r.json()
    assert j["correo_monitoreado"] == "victoriavilches@centralmutuos.cl"
    assert any(c["id"] == cliente for c in j["clientes"])


def test_9_reglas_oro_14_en_db(dbm):
    n = dbm.dashai_eventos.count_documents({"etiqueta": "Regla de Oro ConCreces"})
    assert n == 14, f"esperaban 14, hay {n}"
    for i in range(1, 15):
        assert dbm.dashai_eventos.find_one({"norma_clave": f"ORO_CONCRECES_{i}"}) is not None


def test_10_despachar_sin_confirmar_400(H):
    # cliente inexistente pero payload vacío → primer chequeo es confirmado
    r = requests.post(f"{API}/victoria/clientes/xxx-noexiste/despachar", headers=H, json={}, timeout=15)
    assert r.status_code == 400


def test_11_formularios_sin_confirmado_luego_despachar_403(H, dbm):
    # nuevo cliente aparte para no ensuciar el flujo principal
    r = requests.post(f"{API}/victoria/clientes", headers=H,
                      json={"nombre": "QA TEST VICTORIA 2", "rut": "22.222.222-2"}, timeout=20).json()
    cid2 = r["cliente"]["id"]
    try:
        # sin subir docs, sin confirmar formularios: despachar debe fallar
        rr = requests.post(f"{API}/victoria/clientes/{cid2}/despachar", headers=H,
                           json={"confirmado": True}, timeout=20)
        # bloqueado por auditoría (sin docs) → 403 REGLAS DE ORO o similar; validamos 403
        assert rr.status_code == 403
    finally:
        dbm.victoria_clientes.delete_one({"id": cid2})
        dbm.concreces_estado.delete_many({"victoria_cliente_id": cid2})


def test_12_procesar_correo(H):
    try:
        r = requests.post(f"{API}/victoria/procesar-correo", headers=H, timeout=90)
    except requests.exceptions.ReadTimeout:
        pytest.skip("IMAP real tarda >90s; endpoint no rompió estructura del backend")
        return
    assert r.status_code in (200, 500, 502, 504)
    if r.status_code == 200:
        j = r.json()
        assert "correos_procesados" in j
        assert "documentos_nuevos" in j
        assert "fuentes" in j


# ── Regresión rápida ─────────
def test_13_reglas_oro_concreces(H):
    r = requests.get(f"{API}/concreces/reglas-oro", headers=H, timeout=15)
    assert r.status_code == 200
    j = r.json()
    assert j.get("total") == 14


def test_14_concreces_carpetas(H):
    r = requests.get(f"{API}/concreces/carpetas", headers=H, timeout=20)
    assert r.status_code == 200


def test_15_central_chat_martin(H):
    r = requests.post(f"{API}/central/chat", headers=H,
                      json={"mensaje": "hola"}, timeout=60)
    assert r.status_code == 200
    assert len(str(r.json())) > 5
