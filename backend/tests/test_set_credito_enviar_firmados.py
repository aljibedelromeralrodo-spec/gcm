"""Backend test: envío de set firmado por correo + verificación IMAP INBOX."""
import os
import re
import time
import ssl
import imaplib
import pytest
import requests
from pathlib import Path
from dotenv import dotenv_values

# Load env
FE_ENV = dotenv_values("/app/frontend/.env")
BE_ENV = dotenv_values("/app/backend/.env")

BASE_URL = FE_ENV.get("REACT_APP_BACKEND_URL", "").rstrip("/")
SET_ID = "264f84d0-8ffb-4a76-8da1-bcfa2e166ac6"
TO_EMAIL = "ethangerardobarr@gmail.com"
SUBJECT_TAG = f"[TEST AGENT] Set firmado - verificacion {int(time.time())}"

MAIL_USER = BE_ENV.get("MAIL_USER", "").strip('"')
MAIL_APP_PASSWORD = BE_ENV.get("MAIL_APP_PASSWORD", "").strip('"').replace(" ", "")
IMAP_HOST = BE_ENV.get("MAIL_IMAP_HOST", "imap.gmail.com").strip('"')


def test_1_enviar_firmados_ok():
    url = f"{BASE_URL}/api/set-credito/sets/{SET_ID}/enviar-firmados"
    r = requests.post(url, json={"correos": TO_EMAIL, "asunto": SUBJECT_TAG}, timeout=180)
    print("STATUS:", r.status_code, "BODY:", r.text[:800])
    assert r.status_code == 200, f"esperado 200 got {r.status_code}: {r.text}"
    data = r.json()
    assert data.get("ok") is True, f"ok!=True: {data}"
    enviados = data.get("enviados") or []
    assert TO_EMAIL in enviados, f"correo no en enviados: {enviados}"
    archivos = data.get("archivos")
    assert archivos == 9, f"archivos != 9, got {archivos}. data={data}"


def test_2_imap_verify_delivery():
    if not MAIL_USER or not MAIL_APP_PASSWORD:
        pytest.skip("Credenciales IMAP no disponibles")

    ctx = ssl.create_default_context()
    found = False
    last_err = None
    deadline = time.time() + 90
    attempts = 0
    while time.time() < deadline and not found:
        attempts += 1
        try:
            M = imaplib.IMAP4_SSL(IMAP_HOST, ssl_context=ctx)
            M.login(MAIL_USER, MAIL_APP_PASSWORD)
            M.select("INBOX")
            # Buscar por SUBJECT tag; imap SEARCH requires quoted string
            typ, data = M.search(None, 'SUBJECT', f'"{SUBJECT_TAG}"')
            ids = (data[0].split() if data and data[0] else [])
            print(f"attempt {attempts}: found {len(ids)} messages with subject tag")
            if ids:
                found = True
                # dump last subject
                typ, msg = M.fetch(ids[-1], "(BODY[HEADER.FIELDS (SUBJECT FROM TO)])")
                print("HEADERS:", msg[0][1].decode(errors="ignore") if msg and msg[0] else "n/a")
            M.close()
            M.logout()
        except Exception as e:
            last_err = e
            print("IMAP error:", e)
        if not found:
            time.sleep(6)
    assert found, f"Correo con SUBJECT '{SUBJECT_TAG}' no encontrado en INBOX tras {attempts} intentos. last_err={last_err}"


def test_3_correo_invalido_400():
    url = f"{BASE_URL}/api/set-credito/sets/{SET_ID}/enviar-firmados"
    r = requests.post(url, json={"correos": "sin-arroba"}, timeout=30)
    print("STATUS:", r.status_code, "BODY:", r.text[:400])
    assert r.status_code == 400, f"esperado 400, got {r.status_code}"
    body = r.text.lower()
    assert "correo" in body and ("v" in body), f"mensaje inesperado: {r.text}"


def test_4_get_set_firmados_9_archivos():
    url = f"{BASE_URL}/api/set-credito/sets/{SET_ID}"
    r = requests.get(url, timeout=60)
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:400]}"
    data = r.json()
    firmados = data.get("firmados")
    assert firmados is not None, f"campo 'firmados' ausente. keys={list(data.keys())}"
    # firmados puede ser lista de strings o dicts
    names = []
    for it in firmados:
        if isinstance(it, str):
            names.append(it)
        elif isinstance(it, dict):
            names.append(it.get("nombre") or it.get("name") or it.get("filename") or "")
    print("firmados names:", names)
    assert len(firmados) == 9, f"esperado 9 firmados, got {len(firmados)}: {names}"
    firmado_prefix = [n for n in names if "FIRMADO_" in n and "FIRMADO_COMPLETO" not in n]
    completo = [n for n in names if "FIRMADO_COMPLETO" in n]
    assert len(firmado_prefix) == 8, f"esperado 8 FIRMADO_* extractos, got {len(firmado_prefix)}: {names}"
    assert len(completo) == 1, f"esperado 1 *_FIRMADO_COMPLETO.pdf, got {len(completo)}: {names}"
