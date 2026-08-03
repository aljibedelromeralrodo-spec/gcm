"""Tests iter13 — Correo Mesa preview no-persist, tasacion RUT fallback,
mesa_respuesta aprobada por carta, estudio etapa2, estudio vendedor_email,
forzar verificacion_cedula, regresion light/prefill."""
import os
import time
import pytest
import requests

with open("/app/frontend/.env") as f:
    for ln in f:
        if ln.startswith("REACT_APP_BACKEND_URL="):
            BASE = ln.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE}/api"

SEBASTIAN_ID = "0d1047b1-3891-4994-9078-e4af502fdd45"


@pytest.fixture(scope="module")
def hdr():
    r = requests.post(f"{API}/auth/login",
                      json={"codigo": "administrador", "password": "141617575"},
                      timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def folders(hdr):
    r = requests.get(f"{API}/clientes/folders", headers=hdr, timeout=60)
    assert r.status_code == 200
    return r.json()["folders"]


def _find(folders, needle):
    n = needle.lower()
    for f in folders:
        if n in (f.get("nombre") or "").lower():
            return f
    return None


# ==== Feature 1: send-email preview no persiste ejecutivo_interno ====
def test_send_email_preview_no_persiste_ejecutivo(hdr):
    r0 = requests.get(f"{API}/clientes/folders/{SEBASTIAN_ID}", headers=hdr, timeout=30)
    assert r0.status_code == 200, r0.text
    before = (r0.json().get("folder") or r0.json()).get("ejecutivo_interno", "")

    r = requests.post(f"{API}/clientes/folders/{SEBASTIAN_ID}/send-email",
                      json={"confirm": False, "ejecutivo_interno": "TEST NO PERSIST",
                            "to_addr": "aprobaciones@centralmutuos.cl", "include_merged": False},
                      headers=hdr, timeout=60)
    assert r.status_code == 200, r.text

    r1 = requests.get(f"{API}/clientes/folders/{SEBASTIAN_ID}", headers=hdr, timeout=30)
    after = (r1.json().get("folder") or r1.json()).get("ejecutivo_interno", "")
    assert after == before, f"preview persistió ejecutivo_interno: '{before}' -> '{after}'"


# ==== Feature 2: tasacion subject con nombre + Rut de la carpeta ====
def test_tasacion_subject_incluye_nombre(hdr):
    r = requests.post(f"{API}/tasacion/enviar",
                      json={"nombre": "SEBASTIAN SEPULVEDA", "direccion": "test",
                            "confirm": False, "folder_id": SEBASTIAN_ID},
                      headers=hdr, timeout=60)
    assert r.status_code == 200, r.text
    subject = r.json().get("subject", "")
    assert "SOLICITUD TASACION" in subject
    assert "SEBASTIAN SEPULVEDA" in subject
    # Debe incluir "Rut:" si la carpeta tiene RUT registrado
    # (si no lo incluye reportar como bug)
    print(f"Tasacion subject: {subject}")


def test_tasacion_subject_sin_folder_id(hdr):
    # Sin folder_id ni rut en payload — subject debe al menos tener nombre
    r = requests.post(f"{API}/tasacion/enviar",
                      json={"nombre": "SEBASTIAN SEPULVEDA", "direccion": "test",
                            "confirm": False},
                      headers=hdr, timeout=60)
    assert r.status_code == 200, r.text
    subject = r.json().get("subject", "")
    assert subject == "SOLICITUD TASACION // SEBASTIAN SEPULVEDA" or "Rut:" in subject
    print(f"Tasacion subject (sin folder_id): {subject}")


# ==== Feature 3: mesa_respuesta aprobada por carta ====
@pytest.mark.parametrize("nombre", ["LUIS GUERRERO", "JAVIERA SALGADO",
                                     "CATALINA CASTILLO", "FRANCISCA DIAZ",
                                     "CLAUDIA ANDREA ZURITA SOTO"])
def test_mesa_respuesta_aprobada_por_carta(folders, nombre):
    f = _find(folders, nombre)
    if not f:
        pytest.skip(f"{nombre} no encontrado")
    mesa = f.get("mesa_respuesta")
    assert mesa == "aprobada", \
        f"{nombre}: mesa_respuesta={mesa} (prob={f.get('prob_aprobacion', {}).get('porcentaje')})"


# ==== Feature 4: estudio-titulo/etapa2 ====
def test_estudio_etapa2_ok(hdr):
    r = requests.post(f"{API}/estudio-titulo/etapa2/{SEBASTIAN_ID}",
                      json={"confirm": False}, headers=hdr, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("to") == "contacto@hipotecariogestion.cl"
    cc = data.get("cc") or []
    assert any("victoriavilches@centralmutuos.cl" in c.lower() for c in cc), f"cc={cc}"
    subj = data.get("subject", "")
    assert "SOLICITUD ESTUDIO DE TITULOS" in subj
    assert "SEBASTIAN SEPULVEDA" in subj
    assert isinstance(data.get("attachments"), list)
    assert len(data["attachments"]) >= 1, "faltan adjuntos de 07_estudio_titulo"


def test_estudio_etapa2_sin_docs_400(hdr, folders):
    # buscar una carpeta que NO tenga docs de estudio (que sea distinta a SEBASTIAN)
    for f in folders:
        if f["id"] == SEBASTIAN_ID:
            continue
        r = requests.post(f"{API}/estudio-titulo/etapa2/{f['id']}",
                          json={"confirm": False}, headers=hdr, timeout=60)
        if r.status_code == 400:
            return  # OK
    pytest.skip("no se encontró carpeta sin docs de estudio para validar 400")


# ==== Feature 5: estudio/enviar vivienda usada con vendedor_email ====
def test_estudio_enviar_vendedor_email_primero(hdr):
    r = requests.post(f"{API}/estudio-titulo/enviar",
                      json={"nombre": "SEBASTIAN SEPULVEDA",
                            "tipo_vivienda": "usada",
                            "vendedor_email": "vendedor.test@correo.cl",
                            "docs_lista": ["Copia de escritura",
                                           "Certificado de dominio vigente"],
                            "confirm": False},
                      headers=hdr, timeout=60)
    assert r.status_code == 200, r.text
    data = r.json()
    to = data.get("to") or []
    if isinstance(to, str):
        to = [to]
    assert to and to[0].lower() == "vendedor.test@correo.cl", \
        f"vendedor_email debe ser primer destinatario: {to}"
    body = data.get("body", "")
    assert "Copia de escritura" in body
    assert "Certificado de dominio vigente" in body


# ==== Feature 6: forzar carpeta con verificacion_cedula (LENTO) ====
@pytest.mark.slow
def test_forzar_verificacion_cedula(hdr):
    r = requests.post(f"{API}/clientes/folders/forzar",
                      json={"nombre": "SEBASTIAN SEPULVEDA", "clave": "0586"},
                      headers=hdr, timeout=320)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ok") is True
    assert "verificacion_cedula" in data, f"falta key verificacion_cedula: {list(data.keys())}"
    vc = data["verificacion_cedula"]
    if vc is not None:
        assert isinstance(vc, dict)
        for k in ("nombre_cedula", "rut_cedula", "cambios"):
            assert k in vc, f"falta {k} en verificacion_cedula: {vc}"


# ==== Regresión ====
def test_folders_light_regresion(hdr):
    t0 = time.time()
    r = requests.get(f"{API}/clientes/folders-light", headers=hdr, timeout=15)
    assert r.status_code == 200
    assert time.time() - t0 < 8


def test_folders_regresion(hdr):
    t0 = time.time()
    r = requests.get(f"{API}/clientes/folders", headers=hdr, timeout=60)
    assert r.status_code == 200
    dur = time.time() - t0
    assert dur < 60, f"folders demoró {dur:.1f}s"


def test_gastos_prefill_regresion(hdr):
    r = requests.get(f"{API}/gastos-operacionales/prefill",
                     params={"nombre": "SEBASTIAN"}, headers=hdr, timeout=240)
    assert r.status_code == 200
