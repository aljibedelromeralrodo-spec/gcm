"""
Iteration 31 backend tests: Reglas #58, #62, #63, #64, #65 + Base Histórica.
"""
import os
import time
import pytest
import requests
from datetime import datetime, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://risk-assess-17.preview.emergentagent.com").rstrip("/")
CARLOS_FID = "111e1299-e6d6-4295-9bb1-14304fd37500"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"codigo": "administrador", "password": "141617575"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def H(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def mongo():
    from motor.motor_asyncio import AsyncIOMotorClient
    from pymongo import MongoClient
    url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    dbn = os.environ.get("DB_NAME", "test_database")
    return MongoClient(url)[dbn]


# ---------- Regla #58 Gerencia Cartera ----------
def test_gerencia_cartera_carlos_boetsch(H):
    t0 = time.time()
    r = requests.get(f"{BASE_URL}/api/gerencia/cartera", headers=H, timeout=30)
    dt = time.time() - t0
    assert r.status_code == 200, r.text
    assert dt < 5, f"cartera tardó {dt:.2f}s"
    data = r.json()
    cartera = data.get("cartera") or data.get("rows") or data if isinstance(data, list) else data.get("cartera", [])
    if isinstance(data, dict) and "cartera" in data:
        cartera = data["cartera"]
    elif isinstance(data, list):
        cartera = data
    assert cartera, f"cartera vacía: {str(data)[:400]}"
    carlos = None
    for row in cartera:
        fid = row.get("folder_id") or row.get("id") or row.get("fid")
        if fid == CARLOS_FID:
            carlos = row
            break
    assert carlos is not None, f"No se encontró Carlos {CARLOS_FID}"
    origen = carlos.get("origen") or ""
    print(f"CARLOS origen={origen!r} rut={carlos.get('rut')} monto={carlos.get('monto_credito_uf')}")
    assert "BOETSCH" in origen and "ALTO PARQUE" in origen, f"origen={origen}"
    assert carlos.get("rut") == "13.820.383-2"
    assert float(carlos.get("monto_credito_uf") or 0) == 1290
    # NO DIRECTO solo:
    directos = [r for r in cartera if (r.get("origen") or "").strip().upper() == "DIRECTO"]
    assert not directos, f"registros DIRECTO puros: {len(directos)}"


# ---------- Regla #62 Monitor de fallos ----------
def test_correos_fallidos_list(H):
    r = requests.get(f"{BASE_URL}/api/correos/fallidos?horas=24", headers=H, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, (list, dict))


def test_correos_briefing(H):
    r = requests.get(f"{BASE_URL}/api/correos/briefing", headers=H, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("dia", "exitosos", "fallidos_dia", "fallidos_pendientes"):
        assert k in d, f"falta {k} en {d}"


def test_correos_reintentar_404(H):
    r = requests.post(f"{BASE_URL}/api/correos/fallidos/no-existe-xyz/reintentar", headers=H, timeout=15)
    assert r.status_code == 404, r.text


def test_regla_hierro_62_firma_bloqueo(H, mongo):
    # Insertar correo fallido con subject conteniendo CARLOS SALGADO
    doc = {
        "id": "test-62-block",
        "estado": "fallido",
        "subject": "Reclamo — CARLOS SALGADO",
        "to": "x@test.cl",
        "fecha": datetime.now(timezone.utc).isoformat()
    }
    mongo.correos_fallidos.delete_one({"id": "test-62-block"})
    mongo.correos_fallidos.insert_one(doc)
    try:
        # Debe bloquear con 409
        r = requests.post(f"{BASE_URL}/api/flujos/firmas/{CARLOS_FID}", headers=H,
                          json={"rol": "titular", "estado": "firmado"}, timeout=20)
        assert r.status_code == 409, f"esperado 409, obtenido {r.status_code}: {r.text[:300]}"
        assert "62" in r.text or "Regla" in r.text.lower() or "correo" in r.text.lower()
    finally:
        mongo.correos_fallidos.delete_one({"id": "test-62-block"})
    # Ahora debe pasar
    r = requests.post(f"{BASE_URL}/api/flujos/firmas/{CARLOS_FID}", headers=H,
                      json={"rol": "titular", "estado": "firmado"}, timeout=20)
    assert r.status_code == 200, r.text
    # Volver a pendiente
    r = requests.post(f"{BASE_URL}/api/flujos/firmas/{CARLOS_FID}", headers=H,
                      json={"rol": "titular", "estado": "pendiente"}, timeout=20)
    assert r.status_code == 200, r.text


# ---------- Regla #63 Ultra-precisión 79.50% ----------
def test_simular_credito_ajuste_795():
    import sys
    sys.path.insert(0, "/app/backend")
    from credit_engine import simular_credito
    r1 = simular_credito({"valor_propiedad_uf": 2000, "credito_solicitado_uf": 1700})
    print("SIM 2000/1700:", {k: r1.get(k) for k in ("ajuste_pie_795", "credito_ajustado_795_uf", "pie_requerido_uf")})
    assert r1.get("ajuste_pie_795") is True
    assert abs(float(r1.get("credito_ajustado_795_uf")) - 1590.0) < 0.001
    assert abs(float(r1.get("pie_requerido_uf")) - 410.0) < 0.001
    r2 = simular_credito({"valor_propiedad_uf": 2000, "credito_solicitado_uf": 1500})
    assert r2.get("ajuste_pie_795") is False


def test_compromiso_ajuste_usada(H, mongo):
    fid = None
    original_tipo = None
    for c in mongo.folders.find({"id": {"$ne": CARLOS_FID}}, {"id": 1, "tipo_operacion": 1}).limit(5):
        if c.get("id"):
            fid = c["id"]
            original_tipo = c.get("tipo_operacion")
            break
    assert fid, "No hay folders para probar"
    mongo.folders.update_one({"id": fid}, {"$set": {"tipo_operacion": "usada"}})
    try:
        payload = {"datos": {"precio": {"valor_total_uf": 1000, "pie_uf": 100}}}
        r = requests.put(f"{BASE_URL}/api/compromiso/{fid}", headers=H, json=payload, timeout=20)
        print("compromiso resp:", r.status_code, r.text[:500])
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("nota_795"), f"esperado nota_795, resp={d}"
        c2 = mongo.compromisos.find_one({"folder_id": fid})
        pie_final = ((c2.get("datos") or {}).get("precio") or {}).get("pie_uf")
        print("pie final:", pie_final)
        assert abs(float(pie_final) - 205.0) < 0.5, f"pie_final={pie_final}"
    finally:
        if original_tipo is None:
            mongo.folders.update_one({"id": fid}, {"$unset": {"tipo_operacion": ""}})
        else:
            mongo.folders.update_one({"id": fid}, {"$set": {"tipo_operacion": original_tipo}})


# ---------- Regla #64 Perfil Consolidado ----------
def test_perfil_get(H):
    r = requests.get(f"{BASE_URL}/api/perfil/{CARLOS_FID}", headers=H, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d


def test_perfil_validar(H):
    r = requests.post(f"{BASE_URL}/api/perfil/{CARLOS_FID}/validar", headers=H,
                      json={"campo": "rut"}, timeout=15)
    assert r.status_code == 200, r.text


# ---------- Base Histórica ----------
def test_historia_estado(H):
    r = requests.get(f"{BASE_URL}/api/historia/estado", headers=H, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("rescatados", "revision_manual", "checkpoint"):
        assert k in d, f"falta {k}: {d}"


def test_historia_iniciar_pausar(H):
    r = requests.post(f"{BASE_URL}/api/historia/iniciar", headers=H, timeout=15)
    assert r.status_code == 200, r.text
    time.sleep(1)
    r = requests.post(f"{BASE_URL}/api/historia/pausar", headers=H, timeout=15)
    assert r.status_code == 200, r.text
    # Verificar activo=False
    r = requests.get(f"{BASE_URL}/api/historia/estado", headers=H, timeout=10)
    d = r.json()
    assert d.get("activo") in (False, None), f"motor sigue activo: {d}"


def test_historia_clientes(H):
    r = requests.get(f"{BASE_URL}/api/historia/clientes?q=test", headers=H, timeout=15)
    assert r.status_code == 200, r.text


def test_historia_export_xlsx(H):
    r = requests.get(f"{BASE_URL}/api/historia/export-xlsx", headers=H, timeout=30)
    assert r.status_code == 200, r.text
    ct = r.headers.get("content-type", "")
    assert "spreadsheet" in ct or "xlsx" in ct or "octet-stream" in ct, f"content-type={ct}"
    assert len(r.content) > 100


def test_validar_rut_chileno():
    import sys
    sys.path.insert(0, "/app/backend")
    from base_historica import validar_rut_chileno
    assert validar_rut_chileno("13.820.383-2") is True
    assert validar_rut_chileno("13.820.383-9") is False


# ---------- Constitución v22 ----------
def test_constitucion_v22(mongo):
    doc = mongo.config.find_one({"_key": "constitucion_maestra"})
    assert doc, "no existe constitucion_maestra en db.config"
    assert doc.get("version") == 22, f"version={doc.get('version')}"
    reglas = doc.get("reglas") or []
    ns = {(r.get("n") if isinstance(r, dict) else None) for r in reglas}
    for n in (58, 62, 63, 64, 65):
        assert n in ns, f"falta regla #{n} en constitución"
