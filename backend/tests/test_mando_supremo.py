"""
Regression tests for 'Mando Supremo — Administrador Maestro René Osa'.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback read
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"rut": "administrador", "password": "141617575"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("rol") == "admin" or data.get("scope") == "terminal"
    return data["token"]


@pytest.fixture(scope="module")
def rene_token():
    r = requests.post(f"{API}/auth/login", json={"rut": "rene", "password": "OsaMaestro2026"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("rol") == "maestro", f"expected maestro, got {data}"
    return data["token"]


def _h(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- AUTH ----------
def test_login_legado_admin(admin_token):
    assert admin_token


def test_login_rene_maestro(rene_token):
    assert rene_token


def test_login_rene_clave_incorrecta():
    r = requests.post(f"{API}/auth/login", json={"rut": "rene", "password": "clave_mala_xxx"})
    assert r.status_code == 401


def test_crear_clave_rene_ya_existe():
    # Rene ya tiene clave -> debe 403
    r = requests.post(f"{API}/auth/crear-clave", json={"rut": "rene", "clave": "otraClave2026", "clave2": "otraClave2026"})
    assert r.status_code == 403, r.text


# ---------- CRITERIOS ----------
def test_criterios_admin_no_puede_guardar(admin_token):
    # Obtener criterios actuales primero (GET debería estar accesible)
    g = requests.get(f"{API}/admin/criterios", headers=_h(admin_token))
    assert g.status_code == 200, g.text
    criterios = g.json()
    r = requests.post(
        f"{API}/admin/criterios",
        headers=_h(admin_token),
        json={"clave": "OsaMaestro2026", "criterios": criterios},
    )
    assert r.status_code == 403
    assert "René" in r.text or "Maestro" in r.text or "Rene" in r.text


def test_criterios_rene_clave_incorrecta(rene_token):
    g = requests.get(f"{API}/admin/criterios", headers=_h(rene_token))
    assert g.status_code == 200
    criterios = g.json()
    r = requests.post(
        f"{API}/admin/criterios",
        headers=_h(rene_token),
        json={"clave": "clave_mala", "criterios": criterios},
    )
    assert r.status_code == 403


def test_criterios_rene_ok_y_auditoria(rene_token):
    g = requests.get(f"{API}/admin/criterios", headers=_h(rene_token))
    assert g.status_code == 200
    criterios = g.json()
    # Guardar sin modificar → subir versión + auditoría
    r = requests.post(
        f"{API}/admin/criterios",
        headers=_h(rene_token),
        json={"clave": "OsaMaestro2026", "criterios": criterios},
    )
    assert r.status_code == 200, r.text
    # Auditoría
    a = requests.get(f"{API}/admin/criterios/auditoria", headers=_h(rene_token))
    assert a.status_code == 200
    audit = a.json()
    entries = audit if isinstance(audit, list) else (audit.get("historial") or audit.get("entradas") or audit.get("auditoria") or [])
    assert len(entries) > 0
    # Al menos una entrada menciona a René Osa
    joined = str(entries).lower()
    assert "rené osa" in joined or "rene osa" in joined or "política modificada" in joined.lower()


# ---------- DASHAI ESPEJO MESA ----------
def test_espejo_mesa_admin_forbidden(admin_token):
    r = requests.post(f"{API}/dashai/espejo-mesa/minar", headers=_h(admin_token), json={})
    assert r.status_code == 403


def test_espejo_mesa_rene_ok(rene_token):
    r = requests.post(f"{API}/dashai/espejo-mesa/minar", headers=_h(rene_token), json={})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "minados" in data or "precision_pct" in data or "precision" in data


# ---------- SUPERVISION ----------
def test_supervision_listado(rene_token):
    r = requests.get(f"{API}/admin/supervision", headers=_h(rene_token))
    assert r.status_code == 200
    data = r.json()
    assert "pendientes" in data and "resueltos" in data


def test_supervision_admin_forbidden(admin_token):
    # Necesitamos un id — pero admin debe ser 403 sin importar el id
    r = requests.post(f"{API}/admin/supervision/xxx-inexistente/resolver", headers=_h(admin_token),
                      json={"clave": "OsaMaestro2026", "decision": "aprobar"})
    assert r.status_code == 403


# ---------- COOKIE DOWNLOAD ----------
def test_download_con_cookie(admin_token):
    # Buscar carpeta con archivo
    r = requests.get(f"{API}/clientes/folders", headers=_h(admin_token))
    assert r.status_code == 200
    folders = r.json()
    if isinstance(folders, dict):
        folders = folders.get("folders") or folders.get("items") or []
    folder_id = None
    archivo = None
    for f in folders[:30]:
        fid = f.get("id") or f.get("_id") or f.get("folder_id")
        detail = requests.get(f"{API}/clientes/folders/{fid}", headers=_h(admin_token))
        if detail.status_code != 200:
            continue
        arch = detail.json().get("archivos") or []
        # tomar el primer archivo pdf-ish
        for a in arch:
            nombre = a.get("nombre") if isinstance(a, dict) else a
            if nombre and (nombre.lower().endswith(".pdf") or "." in nombre):
                folder_id = fid
                archivo = nombre
                break
        if folder_id:
            break
    if not folder_id or not archivo:
        pytest.skip("No hay archivos en carpetas para probar descarga")

    url = f"{API}/clientes/folders/{folder_id}/download/{archivo}?inline=true"
    # con cookie
    r_cookie = requests.get(url, cookies={"cm_token": admin_token})
    assert r_cookie.status_code == 200, f"expected 200 with cookie, got {r_cookie.status_code}: {r_cookie.text[:200]}"
    # sin auth
    r_none = requests.get(url)
    assert r_none.status_code == 401, f"expected 401 without auth, got {r_none.status_code}"
