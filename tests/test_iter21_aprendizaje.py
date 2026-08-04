"""Iteration 21 - Motor de Extracción Enriquecida + Guardar y Aprender."""
import os
import re
import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

CLIENTE = "Franco Bahamondes"
TEST_TOKEN = "TESTITER21"  # sentinel for cleanup
TEST_EMAIL_CORRECTO = f"franco.test.{TEST_TOKEN.lower()}@example.com"

client = MongoClient(MONGO_URL)
db = client[DB_NAME]


@pytest.fixture(scope="module")
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def test_enriquecer_devuelve_estructura(http):
    """GET /aprendizaje/datos-cliente devuelve estructura con confianza/fuentes."""
    r = http.get(f"{BASE}/aprendizaje/datos-cliente",
                 params={"nombre": CLIENTE}, timeout=120)
    assert r.status_code == 200, r.text
    data = r.json()
    for k in ("email", "rut", "telefono", "confianza", "fuentes", "remitente", "fuente"):
        assert k in data, f"falta {k} en respuesta: {list(data.keys())}"
    assert isinstance(data["confianza"], dict)
    assert isinstance(data["fuentes"], dict)
    # Al menos un campo con contenido para Franco Bahamondes
    tiene_algo = any(data.get(c) for c in ("email", "rut", "telefono"))
    assert tiene_algo, f"Ningún campo autocompletado: {data}"
    # confianza por campo debe ser alta|dudosa cuando hay valor
    for campo in ("email", "rut", "telefono"):
        if data.get(campo):
            assert data["confianza"].get(campo) in ("alta", "dudosa"), data["confianza"]


def test_alias_aprobacion_cliente(http):
    """Alias GET /aprobacion-cliente/datos-cliente devuelve equivalente."""
    r = http.get(f"{BASE}/aprobacion-cliente/datos-cliente",
                 params={"nombre": CLIENTE}, timeout=120)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "confianza" in data and "fuentes" in data


def test_correccion_campo_invalido(http):
    """POST /aprendizaje/correccion con campo inválido → 400."""
    r = http.post(f"{BASE}/aprendizaje/correccion",
                  json={"cliente": CLIENTE, "campo": "no_existe",
                        "valor_correcto": "x"}, timeout=30)
    assert r.status_code == 400


def test_correccion_sin_valor(http):
    """POST /aprendizaje/correccion sin valor_correcto → 400."""
    r = http.post(f"{BASE}/aprendizaje/correccion",
                  json={"cliente": CLIENTE, "campo": "email",
                        "valor_correcto": ""}, timeout=30)
    assert r.status_code == 400


def test_ciclo_correccion_aprendido(http):
    """POST corrección → GET devuelve valor corregido con confianza alta y fuente 'aprendido'.
    Luego limpia patrones y revierte folders."""
    # snapshot previo del email en folders (para revertir)
    toks = [t.lower() for t in CLIENTE.split() if len(t) > 2]
    rx = ".*".join(re.escape(t) for t in toks[:2])
    folder_prev = db.folders.find_one({"nombre": {"$regex": rx, "$options": "i"}}) or {}
    email_prev = folder_prev.get("email")

    try:
        # 1. Correccion
        r = http.post(f"{BASE}/aprendizaje/correccion",
                      json={"cliente": CLIENTE, "campo": "email",
                            "valor_correcto": TEST_EMAIL_CORRECTO,
                            "valor_extraido": "malo@ejemplo.com",
                            "remitente": "tester@example.com"}, timeout=30)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("ok") is True
        assert isinstance(j.get("patrones_totales"), int) and j["patrones_totales"] >= 1

        # 2. Verificar patrón guardado en DB
        pat = db.patrones_aprendidos.find_one({"valor_correcto": TEST_EMAIL_CORRECTO})
        assert pat is not None, "patrón no persistido"

        # 3. Enriquecer debe devolver el aprendido
        r2 = http.get(f"{BASE}/aprendizaje/datos-cliente",
                      params={"nombre": CLIENTE}, timeout=120)
        assert r2.status_code == 200
        d = r2.json()
        assert d.get("email") == TEST_EMAIL_CORRECTO, f"email esperado {TEST_EMAIL_CORRECTO}, got {d.get('email')}"
        assert d["confianza"].get("email") == "alta"
        assert "aprendido" in d["fuentes"].get("email", [])
    finally:
        # CLEANUP
        db.patrones_aprendidos.delete_many({"valor_correcto": TEST_EMAIL_CORRECTO})
        # Revertir folder email si lo pisamos
        if email_prev is not None:
            db.folders.update_one({"nombre": {"$regex": rx, "$options": "i"}},
                                  {"$set": {"email": email_prev}})
        else:
            db.folders.update_many({"email": TEST_EMAIL_CORRECTO},
                                   {"$unset": {"email": ""}})
        # confirmar cleanup
        assert db.patrones_aprendidos.find_one({"valor_correcto": TEST_EMAIL_CORRECTO}) is None


def test_nombre_muy_corto(http):
    r = http.get(f"{BASE}/aprendizaje/datos-cliente",
                 params={"nombre": "xy"}, timeout=30)
    assert r.status_code == 400
