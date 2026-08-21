"""Tests iteración 52 — Auditoría flujos, digest MESA, Martín chat + confirmación."""
import os
import re
import uuid
import requests
import pytest
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://espejo-hibrido.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/auth/login", json={"rut": "administrador", "password": "141617575"}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def hdr(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def mongo():
    return MongoClient(MONGO_URL)[DB_NAME]


# ------- Auditoría flujos -------
def test_auditoria_ejecutar(hdr):
    r = requests.post(f"{BASE}/api/auditoria-flujos/ejecutar", headers=hdr, timeout=180)
    assert r.status_code == 200, r.text
    data = r.json()
    items = data.get("items") or data.get("detalle") or []
    total = data.get("total") or len(items)
    incorrectos = data.get("incorrectos", sum(1 for i in items if i.get("resultado") != "correcto"))
    print(f"total={total} incorrectos={incorrectos}")
    assert total >= 17, f"Se esperaban >=17 items, got {total}"
    assert incorrectos == 0, f"Hay {incorrectos} items no-correcto: {[i for i in items if i.get('resultado')!='correcto']}"


def test_auditoria_ultima(hdr):
    r = requests.get(f"{BASE}/api/auditoria-flujos/ultima", headers=hdr, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert (data.get("total") or len(data.get("items", []))) >= 1


def test_auditoria_pdf(hdr):
    r = requests.get(f"{BASE}/api/auditoria-flujos/pdf", headers=hdr, timeout=60)
    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    assert "application/pdf" in ct, ct
    assert r.content[:4] == b"%PDF"


# ------- Digest MESA -------
def test_digest_enviadas_mesa(hdr):
    r = requests.get(f"{BASE}/api/resumen-diario/preview", headers=hdr, params={"tipo": "digest"}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "enviadas_mesa" in (data.get("datos") or data), f"faltan enviadas_mesa: {list((data.get('datos') or data).keys())}"
    html = data.get("html", "")
    assert "Solicitudes enviadas a MESA ayer" in html, "HTML no contiene sección MESA"


# ------- Martín contexto -------
def test_martin_estado_espejo(hdr):
    sid = f"qa-{uuid.uuid4().hex[:8]}"
    r = requests.post(f"{BASE}/api/central/chat", headers=hdr, json={
        "message": "¿cuál es el estado del sistema y del algoritmo espejo?",
        "session_id": sid
    }, timeout=90)
    assert r.status_code == 200, r.text
    reply = (r.json().get("response") or r.json().get("reply") or r.json().get("respuesta") or "").lower()
    assert reply, "respuesta vacía"
    assert any(k in reply for k in ["carpeta", "espejo", "sistema"]), f"reply sin contexto: {reply[:300]}"


# ------- Martín flujo correo con cancelación -------
def test_martin_correo_cancelacion(hdr, mongo):
    sid = f"qa-mail-{uuid.uuid4().hex[:8]}"
    # 1) solicitar envío
    r1 = requests.post(f"{BASE}/api/central/chat", headers=hdr, json={
        "message": "Envía un correo a ethangerardobarr@gmail.com con asunto Prueba QA y mensaje hola",
        "session_id": sid
    }, timeout=90)
    assert r1.status_code == 200, r1.text
    reply1 = (r1.json().get("response") or r1.json().get("reply") or r1.json().get("respuesta") or "")
    print(f"reply1: {reply1[:300]}")
    assert re.search(r"confirm", reply1, re.I), f"no pide confirmación: {reply1}"

    # verificar pendiente creado
    pend = list(mongo.martin_pendientes.find({"session_id": sid}))
    assert pend, "no se creó pendiente"

    # 2) cancelar
    r2 = requests.post(f"{BASE}/api/central/chat", headers=hdr, json={
        "message": "cancelar",
        "session_id": sid
    }, timeout=60)
    assert r2.status_code == 200, r2.text
    reply2 = (r2.json().get("response") or r2.json().get("reply") or r2.json().get("respuesta") or "").lower()
    print(f"reply2: {reply2[:300]}")
    assert "cancel" in reply2, f"no cancela: {reply2}"

    pend2 = list(mongo.martin_pendientes.find({"session_id": sid}))
    estados = [p.get("estado") for p in pend2]
    assert "cancelado" in estados, f"estados: {estados}"


# ------- resultado_mesa en folders -------
def test_folders_resultado_mesa(mongo):
    SIN = ["MESA CLIENTES", "Central Mutuos", "Fabiola Pérez Arias", "Gerardo Barrera", "CLIENTE PRUEBA SEPTIEMBRE"]
    CON = {"Juan Antonio Moya olave": "reprobado", "GONZALO ARAOS": "aprobado"}
    for nombre in SIN:
        docs = list(mongo.folders.find({"nombre": {"$regex": f"^{re.escape(nombre)}$", "$options": "i"}}))
        for d in docs:
            assert not d.get("resultado_mesa"), f"{nombre} tiene resultado_mesa={d.get('resultado_mesa')}"
    for nombre, esperado in CON.items():
        docs = list(mongo.folders.find({"nombre": {"$regex": re.escape(nombre), "$options": "i"}}))
        assert docs, f"no se encontró carpeta {nombre}"
        vals = [d.get("resultado_mesa") for d in docs]
        assert any(v == esperado for v in vals), f"{nombre} esperado {esperado} got {vals}"
