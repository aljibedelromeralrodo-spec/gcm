"""Backend tests for .mbox streaming import (iter 48)."""
import os
import re
import time
import uuid
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL") or open("/app/frontend/.env").read()
m = re.search(r"REACT_APP_BACKEND_URL=(\S+)", BASE)
if m:
    BASE = m.group(1)
BASE = BASE.rstrip("/")

ADMIN = {"rut": "administrador", "password": "141617575"}


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def h(token):
    return {"Authorization": f"Bearer {token}"}


def _build_mbox(n=30, tag="qa-mbox"):
    lines = []
    for i in range(n):
        lines.append(f"From remitente{i}@test.cl Wed Jan  1 00:00:00 2025")
        lines.append(f"From: Remitente {i} <remitente{i}@test.cl>")
        lines.append("To: qa@test.cl")
        lines.append(f"Subject: Correo QA {i}")
        lines.append("Date: Wed, 01 Jan 2025 00:00:00 +0000")
        lines.append(f"Message-ID: <{tag}-{i}@test.cl>")
        lines.append("Content-Type: text/plain; charset=utf-8")
        lines.append("")
        lines.append(f"Cuerpo del correo QA numero {i}. Contenido de prueba." * 20)
        lines.append("")
    return ("\n".join(lines)).encode("utf-8")


# Iniciar / chunk / finalizar happy path (mini flow, se usa como sanity backend)
def test_mbox_flow_completo(h):
    data = _build_mbox(5, tag=f"qa-mbox-be-{uuid.uuid4().hex[:6]}")
    r = requests.post(f"{BASE}/api/mbox/iniciar",
                      json={"filename": "qa.mbox", "total_bytes": len(data)}, headers=h, timeout=30)
    assert r.status_code == 200, r.text
    sid = r.json()["sid"]
    # subir en 2 chunks para probar reconstruccion
    mid = len(data) // 2
    for chunk in (data[:mid], data[mid:]):
        rr = requests.post(f"{BASE}/api/mbox/chunk/{sid}", data=chunk,
                           headers={**h, "Content-Type": "application/octet-stream"}, timeout=60)
        assert rr.status_code == 200, rr.text
    fin = requests.post(f"{BASE}/api/mbox/finalizar/{sid}", headers=h, timeout=30)
    assert fin.status_code == 200
    assert fin.json()["correos_importados"] >= 5
    # estado
    est = requests.get(f"{BASE}/api/mbox/estado/{sid}", headers=h, timeout=30)
    assert est.status_code == 200
    assert est.json()["estado"] == "completado"


# 400 si total_bytes = 0
def test_mbox_iniciar_tamano_invalido_cero(h):
    r = requests.post(f"{BASE}/api/mbox/iniciar",
                      json={"filename": "x.mbox", "total_bytes": 0}, headers=h, timeout=30)
    assert r.status_code == 400


# 400 si total_bytes > 100 GB
def test_mbox_iniciar_tamano_invalido_grande(h):
    r = requests.post(f"{BASE}/api/mbox/iniciar",
                      json={"filename": "x.mbox", "total_bytes": 200_000_000_000}, headers=h, timeout=30)
    assert r.status_code == 400


# 403 para rol sin permiso (broker1)
def test_mbox_iniciar_403_broker():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"rut": "broker1", "password": "broker123"}, timeout=30)
    if r.status_code != 200:
        pytest.skip("broker1 no disponible")
    bt = r.json()["token"]
    rr = requests.post(f"{BASE}/api/mbox/iniciar",
                       json={"filename": "x.mbox", "total_bytes": 100},
                       headers={"Authorization": f"Bearer {bt}"}, timeout=30)
    assert rr.status_code == 403, rr.text
