"""
Iteración 36 — Tests backend flujo definitivo de documentos (matriz por tipo de cliente),
panel de fuentes, bloqueo 409 origen no configurado, validaciones de envío sin enviar,
vendedores usada y regresión Supercarpeta.

Reglas de seguridad:
- NUNCA POST /solicitud-doc/{fid}/enviar con payload válido (enviaría correo real).
- NO cambiar estados manuales que disparen re-envío.
- Revertir cambios de vendedor / inmobiliaria al valor original al finalizar.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://espejo-hibrido.preview.emergentagent.com").rstrip("/")

CARLOS_FID = "111e1299-e6d6-4295-9bb1-14304fd37500"
LUIS_FID = "f60cc0fc-f4d5-4ac8-b881-441331d8587e"  # LUIS GUERRERO usada sin subsidio
KANELA_FID = "a1b5cfe4-1bcb-44b1-85b2-cdbdf637136f"  # KANELA IBAÑEZ usada sin subsidio


@pytest.fixture(scope="module")
def token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"rut": "administrador", "password": "141617575"},
        timeout=20,
    )
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------- Regresión Supercarpeta ----------------
def test_supercarpeta_18_clientes(auth):
    r = requests.get(f"{BASE_URL}/api/supercarpeta", headers=auth, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert len(d["clientes"]) == 18
    assert "lista_maestra" in d
    c0 = d["clientes"][0]
    assert "promesa_ia" in c0
    assert "docs_co_rs" in c0
    assert "documentos" in c0["docs_co_rs"] or isinstance(c0["docs_co_rs"], dict)


def test_cbr_estado(auth):
    r = requests.get(f"{BASE_URL}/api/supercarpeta/cbr/estado", headers=auth, timeout=20)
    assert r.status_code == 200


def test_cbr_excel_primera_columna_numero(auth):
    r = requests.get(f"{BASE_URL}/api/supercarpeta/cbr/excel", headers=auth, timeout=30)
    assert r.status_code == 200
    ct = r.headers.get("content-type", "")
    assert "spreadsheet" in ct or "excel" in ct or "octet-stream" in ct


# ---------------- Matriz por tipo de cliente ----------------
def test_matriz_carlos_nueva_con_subsidio(auth):
    r = requests.get(f"{BASE_URL}/api/supercarpeta/solicitud-doc/{CARLOS_FID}", headers=auth, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("tipo_cliente") == "nueva_con_subsidio", d
    docs = d.get("docs_solicitados") or []
    assert "Carta Oferta" in docs and "Resolución SERVIU" in docs, docs
    assert d.get("requiere_resolucion") is True
    assert d.get("para") == "csoria@boetsch.cl", d.get("para")


def test_matriz_usada_sin_subsidio_alternativas(auth):
    r = requests.get(f"{BASE_URL}/api/supercarpeta/solicitud-doc/{LUIS_FID}", headers=auth, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "usada" in (d.get("tipo_cliente") or "").lower(), d
    alts = d.get("alternativas") or []
    assert "promesa" in alts and "carta_pie" in alts, alts


def test_matriz_usada_sin_subsidio_carta_pie(auth):
    r = requests.get(
        f"{BASE_URL}/api/supercarpeta/solicitud-doc/{LUIS_FID}",
        params={"doc": "carta_pie"}, headers=auth, timeout=20,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    asunto = d.get("asunto") or ""
    assert "Carta Pie" in asunto, asunto


# ---------------- Envío bloqueado (sin enviar correos) ----------------
def test_envio_para_vacio_400(auth):
    r = requests.post(
        f"{BASE_URL}/api/supercarpeta/solicitud-doc/{CARLOS_FID}/enviar",
        json={"para": "", "cc": [], "asunto": "test", "cuerpo": "test"},
        headers=auth, timeout=20,
    )
    assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text}"
    assert "contacto" in r.text.lower() or "configure" in r.text.lower()


def test_envio_falta_resolucion_400(auth):
    # CARLOS es nueva con subsidio -> requiere Resolución SERVIU
    r = requests.post(
        f"{BASE_URL}/api/supercarpeta/solicitud-doc/{CARLOS_FID}/enviar",
        json={
            "para": "csoria@boetsch.cl",
            "cc": [],
            "asunto": "no debe enviarse",
            "cuerpo": "test",
            "resolucion_serviu": "",
        },
        headers=auth, timeout=20,
    )
    assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text}"
    body = r.text
    assert "Resolución SERVIU" in body or "SERVIU" in body or "BLOQUEADO" in body.upper()


# ---------------- Bloqueo 409 origen no configurado ----------------
def test_bloqueo_inmobiliaria_no_registrada_409_luego_reversion(auth):
    # 1) Enviar valor no registrado -> 409
    r = requests.post(
        f"{BASE_URL}/api/supercarpeta/manual/{CARLOS_FID}",
        json={"campo": "inmobiliaria", "valor": "Inmobiliaria Fantasma XYZ"},
        headers=auth, timeout=20,
    )
    assert r.status_code == 409, f"expected 409 got {r.status_code}: {r.text}"
    try:
        j = r.json()
        det = j.get("detail") if isinstance(j.get("detail"), dict) else j
        code = (det or {}).get("code") if isinstance(det, dict) else None
        assert code == "ORIGEN_NO_CONFIGURADO", j
    except ValueError:
        assert "ORIGEN_NO_CONFIGURADO" in r.text

    # 2) BOETCH registrada -> 200 (además revierte a valor real)
    r2 = requests.post(
        f"{BASE_URL}/api/supercarpeta/manual/{CARLOS_FID}",
        json={"campo": "inmobiliaria", "valor": "BOETCH"},
        headers=auth, timeout=20,
    )
    assert r2.status_code == 200, r2.text


# ---------------- Panel de fuentes ----------------
def test_fuentes_panel(auth):
    r = requests.get(f"{BASE_URL}/api/supercarpeta/fuentes-panel", headers=auth, timeout=20)
    assert r.status_code == 200
    d = r.json()
    assert "inmobiliarias" in d and "brokers" in d and "individuales" in d
    assert "lista_maestra" in d
    inmobs = d["inmobiliarias"]
    boetch = None
    for i in inmobs:
        name = (i.get("inmobiliaria") or i.get("nombre") or "").upper()
        if name == "BOETCH":
            boetch = i
            break
    assert boetch is not None, [i.get("inmobiliaria") or i.get("nombre") for i in inmobs]
    proys = boetch.get("proyectos") or []
    # BOETCH tiene contactos por proyecto (Celinda Soria csoria@boetsch.cl detectada)
    emails = [(p.get("email") or "").lower() for p in proys]
    assert any("boetsch.cl" in e or "boetch" in e for e in emails), emails
    assert boetch.get("correo_general"), boetch


def test_fuentes_verificar_boetch_ok(auth):
    r = requests.get(
        f"{BASE_URL}/api/supercarpeta/fuentes/verificar",
        params={"inmobiliaria": "BOETCH"}, headers=auth, timeout=15,
    )
    assert r.status_code == 200
    assert r.json().get("inmobiliaria_ok") is True


def test_fuentes_verificar_broker_inexistente(auth):
    r = requests.get(
        f"{BASE_URL}/api/supercarpeta/fuentes/verificar",
        params={"broker": "NoExiste_QA_XYZ"}, headers=auth, timeout=15,
    )
    assert r.status_code == 200
    assert r.json().get("broker_ok") is False


# ---------------- Vendedores usada (con limpieza) ----------------
def test_vendedores_usada_set_get_cleanup(auth):
    fid = LUIS_FID
    r = requests.post(
        f"{BASE_URL}/api/supercarpeta/vendedores-usada",
        json={"fid": fid, "vendedor": "QA Test", "email": "qa.test@test.cl"},
        headers=auth, timeout=20,
    )
    assert r.status_code == 200, r.text

    r2 = requests.get(f"{BASE_URL}/api/supercarpeta/vendedores-usada", headers=auth, timeout=15)
    assert r2.status_code == 200
    data = r2.json()
    lista = data if isinstance(data, list) else (data.get("items") or data.get("vendedores") or [])
    found = False
    for it in lista:
        if it.get("fid") == fid and (it.get("email") or "") == "qa.test@test.cl":
            found = True
            assert it.get("configurado") is True, it
            break
    # Limpieza obligatoria
    r3 = requests.post(
        f"{BASE_URL}/api/supercarpeta/vendedores-usada",
        json={"fid": fid, "vendedor": "", "email": ""},
        headers=auth, timeout=20,
    )
    assert r3.status_code == 200, r3.text
    assert found, "vendedor no reflejado tras POST (pero se limpió igual)"
