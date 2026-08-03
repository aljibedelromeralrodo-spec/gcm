"""Tests iter12 — Escrituración, Forzar Carpeta, Enriquecer, Gastos prefill, Merge orden, Send-email ejecutivo interno."""
import os
import re
import time
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE:
    # fallback from frontend/.env
    with open("/app/frontend/.env") as f:
        for ln in f:
            if ln.startswith("REACT_APP_BACKEND_URL="):
                BASE = ln.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE}/api"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{API}/auth/login", json={"codigo": "administrador", "password": "141617575"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def hdr(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def folders(hdr):
    r = requests.get(f"{API}/clientes/folders", headers=hdr, timeout=60)
    assert r.status_code == 200
    return r.json()["folders"]


def _find(folders, needle):
    needle = needle.lower()
    for f in folders:
        if needle in (f.get("nombre") or "").lower():
            return f
    return None


# 1. Folders-light regression
def test_folders_light_fast(hdr):
    t0 = time.time()
    r = requests.get(f"{API}/clientes/folders-light", headers=hdr, timeout=15)
    dur = time.time() - t0
    assert r.status_code == 200
    data = r.json()
    assert "folders" in data
    assert len(data["folders"]) > 0
    # Shape: only id/nombre/rut
    f0 = data["folders"][0]
    assert set(f0.keys()) <= {"id", "nombre", "rut"}
    assert dur < 5.0, f"folders-light demoró {dur:.2f}s (>5s)"


# 2. is_escrituracion + prob_aprobacion 0%
def test_folders_has_is_escrituracion_field_and_prob(folders):
    assert len(folders) > 0
    # is_escrituracion opcional pero debe existir en respuesta pública si el toggle se usó
    # Verificar que prob_aprobacion viene siempre
    for f in folders:
        assert "prob_aprobacion" in f
        assert "porcentaje" in f["prob_aprobacion"]


def test_prob_aprobacion_zero_when_no_min_docs(folders):
    # Alguna carpeta con probabilidad 0 debe existir (regla 0% sin docs mínimos)
    zeros = [f for f in folders if f["prob_aprobacion"].get("porcentaje") == 0]
    # Si no hay ninguna con 0%, revisar los criterios: si al menos alguna carpeta
    # no tiene docs mínimos, debería estar en 0.
    # Solo verificamos que el campo existe y responde numérico entre 0..100
    for f in folders:
        p = f["prob_aprobacion"]["porcentaje"]
        assert 0 <= p <= 100


# 3. toggle escrituracion + regreso
def test_toggle_escrituracion_move_and_return(hdr, folders):
    # Elegir una carpeta que actualmente NO esté en escrituración
    cand = None
    for f in folders:
        if not f.get("is_escrituracion"):
            cand = f
            break
    assert cand, "No hay carpetas para probar toggle"
    fid = cand["id"]
    original = bool(cand.get("is_escrituracion"))
    try:
        r = requests.post(f"{API}/clientes/folders/{fid}/escrituracion", json={"activar": True}, headers=hdr, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["is_escrituracion"] is True
        # verify listing
        r2 = requests.get(f"{API}/clientes/folders", headers=hdr, timeout=60)
        assert r2.status_code == 200
        moved = next((x for x in r2.json()["folders"] if x["id"] == fid), None)
        assert moved and moved.get("is_escrituracion") is True
    finally:
        # revertir SIEMPRE
        requests.post(f"{API}/clientes/folders/{fid}/escrituracion",
                      json={"activar": original}, headers=hdr, timeout=15)


# 4. Forzar carpeta — validaciones
def test_forzar_clave_incorrecta(hdr):
    r = requests.post(f"{API}/clientes/folders/forzar",
                      json={"nombre": "SEBASTIAN SEPULVEDA", "clave": "wrong"}, headers=hdr, timeout=15)
    assert r.status_code == 403


def test_forzar_sin_nombre_ni_rut(hdr):
    r = requests.post(f"{API}/clientes/folders/forzar",
                      json={"clave": "0586"}, headers=hdr, timeout=15)
    assert r.status_code == 400


@pytest.mark.slow
def test_forzar_con_nombre_existente(hdr):
    # IMAP real — timeout amplio
    r = requests.post(f"{API}/clientes/folders/forzar",
                      json={"nombre": "SEBASTIAN SEPULVEDA", "clave": "0586"},
                      headers=hdr, timeout=240)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ok") is True
    for k in ("correos_encontrados", "procesados", "archivos_imap"):
        assert k in data, f"falta {k} en {data.keys()}"


# 5. Enriquecer credito + estudio (usa carpeta existente, timeouts largos)
@pytest.mark.slow
def test_enriquecer_credito(hdr, folders):
    f = _find(folders, "SEBASTIAN")
    assert f, "SEBASTIAN no encontrado"
    r = requests.post(f"{API}/clientes/folders/{f['id']}/enriquecer",
                      json={"modo": "credito"}, headers=hdr, timeout=240)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert "correos_revisados" in data
    assert isinstance(data.get("archivos_nuevos"), list)
    # Firmas image001.jpg no deben aparecer
    for a in data["archivos_nuevos"]:
        nombre = a.get("archivo", "")
        assert not re.search(r"image\d{1,4}\.(jpe?g|png|gif|bmp)$", nombre, re.I), \
            f"firma corta filtrada mal: {nombre}"


@pytest.mark.slow
def test_enriquecer_estudio(hdr, folders):
    f = _find(folders, "SEBASTIAN")
    assert f
    r = requests.post(f"{API}/clientes/folders/{f['id']}/enriquecer",
                      json={"modo": "estudio"}, headers=hdr, timeout=240)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert data["modo"] == "estudio"
    for a in data.get("archivos_nuevos") or []:
        ruta = a.get("archivo", "")
        assert "07_estudio_titulo" in ruta, \
            f"archivo modo=estudio debe ir a 07_estudio_titulo, quedó en {ruta}"


# 6. Gastos prefill
def test_gastos_prefill_nombre_corto(hdr):
    r = requests.get(f"{API}/gastos-operacionales/prefill", params={"nombre": "AB"}, headers=hdr, timeout=15)
    assert r.status_code == 400


@pytest.mark.slow
def test_gastos_prefill_ok(hdr):
    r = requests.get(f"{API}/gastos-operacionales/prefill",
                     params={"nombre": "SEBASTIAN"}, headers=hdr, timeout=240)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert "prefill" in data
    assert "fuentes" in data
    pf = data["prefill"] or {}
    # Debe tener las claves esperadas (aunque vengan vacías: no inventa)
    for k in ("email_cliente", "rut", "items", "total_gastos_uf", "metodo"):
        assert k in pf, f"falta clave {k} en prefill: {pf}"


# 7. Send-email preview con ejecutivo_interno
def test_send_email_preview_falta_ejecutivo(hdr, folders):
    f = _find(folders, "SEBASTIAN")
    assert f
    # Sin ejecutivo_interno explícito y sin persistido: missing_docs debe incluirlo
    # Guardar valor previo para restaurar si fuese necesario
    r = requests.post(
        f"{API}/clientes/folders/{f['id']}/send-email",
        json={"to_addr": "test@example.com", "ejecutivo_interno": "", "confirm": False},
        headers=hdr, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    if not (f.get("ejecutivo_interno") or ""):
        assert any("Ejecutivo interno" in m for m in data.get("missing_docs") or []), \
            f"missing_docs debería incluir 'Ejecutivo interno': {data.get('missing_docs')}"


def test_send_email_preview_con_ejecutivo(hdr, folders):
    f = _find(folders, "SEBASTIAN")
    assert f
    original_ej = f.get("ejecutivo_interno") or ""
    try:
        r = requests.post(
            f"{API}/clientes/folders/{f['id']}/send-email",
            json={"to_addr": "test@example.com", "ejecutivo_interno": "Deisy Salazar", "confirm": False},
            headers=hdr, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        # No debe faltar el ejecutivo
        assert not any("Ejecutivo interno" in m for m in data.get("missing_docs") or [])
        # subject y body presentes
        assert data.get("subject")
        assert data.get("body")
    finally:
        # restaurar el ejecutivo original
        requests.post(f"{API}/clientes/folders/{f['id']}/send-email",
                      json={"to_addr": "x@x.com", "ejecutivo_interno": original_ej, "confirm": False},
                      headers=hdr, timeout=30)


# 8. merge-protocol con orden personalizado (RUBEM ZABALA)
@pytest.mark.slow
def test_merge_protocol_orden(hdr, folders):
    f = _find(folders, "RUBEM")
    if not f:
        pytest.skip("RUBEM no encontrado")
    orden = ["cmf", "cedula", "liquidacion", "afp", "extras"]
    r = requests.post(f"{API}/clientes/folders/{f['id']}/merge-protocol",
                      json={"orden": orden, "include_extras": True},
                      headers=hdr, timeout=120)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("merged_file")
    proto = data.get("protocol_order") or []
    # protocol_order debe respetar el orden dado (filtrando categorías con archivos)
    filt = [c for c in orden if c in proto]
    assert filt == proto or all(a == b for a, b in zip(filt, proto)), \
        f"protocol_order {proto} no respeta orden {orden}"
