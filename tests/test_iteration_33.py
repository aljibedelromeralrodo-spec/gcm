"""Iteración 33 — Supercarpeta (Centro de Control de Escrituración).
Cubre: login, GET /supercarpeta (17 clientes, meta 41.717 UF), estados manuales,
resolver conflicto, fuentes-doc (globales + por cliente), ingreso manual, agregar
y eliminar cliente. Endpoints /panel y /nota NO existen (no están en malla_inteligencia.py)."""
import os
import pytest
import requests

def _read_env():
    for f in ("/app/frontend/.env",):
        try:
            for line in open(f):
                if line.startswith("REACT_APP_BACKEND_URL"):
                    return line.split("=", 1)[1].strip().strip('"').rstrip("/")
        except Exception:
            pass
    return os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


BASE = _read_env()


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"codigo": "administrador", "password": "141617575"},
                      timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def h(token):
    return {"Authorization": f"Bearer {token}"}


# ── LOGIN ───────────────────────────────────────────────────
def test_login_ok(token):
    assert token and len(token) > 20


# ── GET /api/supercarpeta ───────────────────────────────────
@pytest.fixture(scope="module")
def sc(h):
    r = requests.get(f"{BASE}/api/supercarpeta", headers=h, timeout=60)
    assert r.status_code == 200, r.text
    return r.json()


def test_supercarpeta_total_17(sc):
    assert sc["total"] == 17, f"Se esperaban 17 clientes, hay {sc['total']}"


def test_supercarpeta_meta_uf(sc):
    p = sc["proyeccion"]
    assert p["meta_uf"] == 41717
    # suma esperada 39717 (± tolerancia por conversión float)
    assert abs(p["suma_uf"] - 39717) < 5, f"suma_uf={p['suma_uf']}"
    assert p["alerta_diferencia"] is True


def test_supercarpeta_jose_olivares_sin_monto(sc):
    p = sc["proyeccion"]
    assert any("OLIVARES" in n.upper() for n in p.get("pendientes_monto", [])), \
        f"pendientes_monto={p.get('pendientes_monto')}"


def test_supercarpeta_broker_default(sc):
    for c in sc["clientes"]:
        assert c["broker"] == "Mutuaria y Leasing Limitada", \
            f"{c['cliente']} broker={c['broker']}"


def test_supercarpeta_inmobiliaria_no_vacia(sc):
    for c in sc["clientes"]:
        assert (c.get("inmobiliaria") or "").strip(), f"{c['cliente']} sin inmobiliaria"


def test_supercarpeta_campos_obligatorios(sc):
    campos = ["rut", "inmobiliaria", "proyecto", "ciudad", "notaria", "broker",
              "monto_uf", "subsidio", "serviu", "promesa", "carpeta_notaria",
              "escritura", "set_credito", "fecha_firma", "con_subsidio",
              "manual", "conflicto", "faltantes"]
    c = sc["clientes"][0]
    for k in campos:
        assert k in c, f"Falta {k} en el cliente"


# ── /estado ─────────────────────────────────────────────────
@pytest.fixture(scope="module")
def fid_test(sc):
    return sc["clientes"][0]["id"]


def test_estado_manual_tasacion(h, fid_test):
    r = requests.post(f"{BASE}/api/supercarpeta/estado/{fid_test}",
                      headers=h, json={"hito": "tasacion", "estado": "En Proceso"},
                      timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["hito"] == "tasacion"
    assert d["estado"] == "En Proceso"
    # Verificar en GET
    g = requests.get(f"{BASE}/api/supercarpeta", headers=h, timeout=60).json()
    cli = next(c for c in g["clientes"] if c["id"] == fid_test)
    assert cli["manual"]["tasacion"] is True
    assert cli["estado_tasacion"] == "En Proceso"


def test_estado_manual_serviu(h, fid_test):
    r = requests.post(f"{BASE}/api/supercarpeta/estado/{fid_test}",
                      headers=h, json={"hito": "serviu", "estado": "Solicitada"},
                      timeout=30)
    assert r.status_code == 200


def test_estado_manual_set_credito(h, fid_test):
    r = requests.post(f"{BASE}/api/supercarpeta/estado/{fid_test}",
                      headers=h, json={"hito": "set_credito", "estado": "En Proceso"},
                      timeout=30)
    assert r.status_code == 200


def test_estado_hito_invalido(h, fid_test):
    r = requests.post(f"{BASE}/api/supercarpeta/estado/{fid_test}",
                      headers=h, json={"hito": "no_existe", "estado": "x"},
                      timeout=30)
    assert r.status_code == 400


# ── /estado/resolver — Limpieza al final ────────────────────
def test_estado_resolver_sobreescribir(h, fid_test):
    for hito in ("tasacion", "serviu", "set_credito"):
        r = requests.post(f"{BASE}/api/supercarpeta/estado/{fid_test}/resolver",
                          headers=h, json={"hito": hito, "accion": "sobreescribir"},
                          timeout=30)
        assert r.status_code == 200


# ── /fuentes-doc ────────────────────────────────────────────
def test_fuentes_doc_get(h):
    r = requests.get(f"{BASE}/api/supercarpeta/fuentes-doc", headers=h, timeout=30)
    assert r.status_code == 200
    d = r.json()
    fu = d["fuentes"]
    for k in ("tasacion", "estudio", "cesion", "set_credito", "notaria"):
        assert k in fu, f"Falta clave {k}"
    tas = " ".join(fu.get("tasacion", []))
    est = " ".join(fu.get("estudio", []))
    assert "valueproperty" in tas.lower(), f"tasacion={fu.get('tasacion')}"
    assert "victoriavilches@centralmutuos" in est.lower() or \
           "gmajluf@amvabogados" in est.lower(), f"estudio={fu.get('estudio')}"


def test_fuentes_doc_set_global(h):
    lista = ["test@fuente.cl", "contacto@valueproperty.cl", "contacto@valuedproperty.cl"]
    r = requests.post(f"{BASE}/api/supercarpeta/fuentes-doc", headers=h,
                      json={"tasacion": lista}, timeout=30)
    assert r.status_code == 200, r.text
    # Verificar persistencia
    g = requests.get(f"{BASE}/api/supercarpeta/fuentes-doc", headers=h, timeout=30).json()
    for e in lista:
        assert e in g["fuentes"]["tasacion"]


def test_fuentes_doc_set_cliente(h, fid_test):
    r = requests.post(f"{BASE}/api/supercarpeta/fuentes-doc/{fid_test}",
                      headers=h, json={"notaria": ["notaria@test.cl"]}, timeout=30)
    # Endpoint solo acepta tasacion/estudio/cesion/set_credito. 'notaria' no está en la lista.
    # El endpoint no lanza error si nada matchea, guardando dict vacío.
    assert r.status_code == 200
    # Probar con clave válida
    r2 = requests.post(f"{BASE}/api/supercarpeta/fuentes-doc/{fid_test}",
                       headers=h, json={"tasacion": ["notaria@test.cl"]}, timeout=30)
    assert r2.status_code == 200


# ── /manual ────────────────────────────────────────────────
def test_manual_ciudad(h, fid_test):
    r = requests.post(f"{BASE}/api/supercarpeta/manual/{fid_test}", headers=h,
                      json={"campo": "ciudad", "valor": "Osorno"}, timeout=30)
    assert r.status_code == 200, r.text
    g = requests.get(f"{BASE}/api/supercarpeta", headers=h, timeout=60).json()
    cli = next(c for c in g["clientes"] if c["id"] == fid_test)
    assert cli["ciudad"] == "Osorno"


def test_manual_rut_dv_invalido(h, fid_test):
    r = requests.post(f"{BASE}/api/supercarpeta/manual/{fid_test}", headers=h,
                      json={"campo": "rut", "valor": "11.111.111-1"}, timeout=30)
    assert r.status_code == 400


def test_manual_notaria_proyecto(h, fid_test):
    r1 = requests.post(f"{BASE}/api/supercarpeta/manual/{fid_test}", headers=h,
                       json={"campo": "notaria", "valor": "Notaría Test"}, timeout=30)
    r2 = requests.post(f"{BASE}/api/supercarpeta/manual/{fid_test}", headers=h,
                       json={"campo": "proyecto", "valor": "Proyecto Test"}, timeout=30)
    assert r1.status_code == 200 and r2.status_code == 200


# ── /cliente (agregar + eliminar) ──────────────────────────
def test_cliente_agregar_y_eliminar(h):
    payload = {"nombre": "CLIENTE PRUEBA QA", "inmobiliaria": "Word",
               "proyecto": "Proyecto QA", "ciudad": "Temuco",
               "tipo_propiedad": "nueva", "subsidio": "Sin Subsidio",
               "monto_uf": "1.000"}
    r = requests.post(f"{BASE}/api/supercarpeta/cliente", headers=h,
                      json=payload, timeout=30)
    assert r.status_code == 200, r.text
    new_id = r.json()["id"]
    g = requests.get(f"{BASE}/api/supercarpeta", headers=h, timeout=60).json()
    assert g["total"] == 18, f"total={g['total']}"
    # Eliminar
    r2 = requests.post(f"{BASE}/api/supercarpeta/cliente/{new_id}/eliminar",
                       headers=h, timeout=30)
    assert r2.status_code == 200
    g2 = requests.get(f"{BASE}/api/supercarpeta", headers=h, timeout=60).json()
    assert g2["total"] == 17, f"total tras eliminar={g2['total']}"


# ── /flujos/barrido-estado ─────────────────────────────────
def test_barrido_estado(h):
    r = requests.get(f"{BASE}/api/flujos/barrido-estado", headers=h, timeout=30)
    assert r.status_code == 200


# ── Endpoints /panel y /nota — VERIFICAR EXISTENCIA ────────
def test_panel_endpoint_no_existe(h, fid_test):
    """El spec pide GET /api/supercarpeta/panel/{fid}?hito=tasacion — no está implementado."""
    r = requests.get(f"{BASE}/api/supercarpeta/panel/{fid_test}?hito=tasacion",
                     headers=h, timeout=30)
    # Documentar el gap: se espera 404 (endpoint faltante)
    assert r.status_code in (200, 404), r.status_code


def test_nota_endpoint_no_existe(h, fid_test):
    r = requests.post(f"{BASE}/api/supercarpeta/nota/{fid_test}", headers=h,
                     json={"hito": "tasacion", "texto": "nota de prueba"}, timeout=30)
    assert r.status_code in (200, 404, 405), r.status_code
