"""Tests iteration 63 — Bug fix carpetas: rescate búnker + refetch + filtro flexible +
zip/rar + reevaluación no destructiva + endpoint recuperar-perdidos.
"""
import os
import io
import sys
import shutil
import zipfile
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

BACKEND_DIR = Path("/app/backend")
load_dotenv(BACKEND_DIR / ".env")
load_dotenv("/app/frontend/.env")
sys.path.insert(0, str(BACKEND_DIR))

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")


# ─── fixtures ─────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"rut": "administrador", "password": "141617575"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    tok = r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def lectura_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"rut": "Clave", "password": "1234"},
        timeout=30,
    )
    if r.status_code != 200:
        pytest.skip(f"login lectura no disponible: {r.status_code} {r.text[:120]}")
    return r.json().get("token")


# ─── 1. endpoint recuperar-perdidos ───────────────────────────────────
def test_recuperar_perdidos_endpoint(admin_headers):
    r = requests.post(
        f"{BASE_URL}/api/procesamiento/recuperar-perdidos?dias=60",
        headers=admin_headers,
        timeout=180,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    for k in ("revisados", "creadas", "recuperados_correo", "fallidos"):
        assert k in body, f"falta clave {k} en respuesta {body}"
    assert isinstance(body["revisados"], int)


# ─── 2. filtro flexible ───────────────────────────────────────────────
def test_regla_solicitud_ok_flexible_3_docs():
    from server import _regla_solicitud_ok
    item = {
        "subject": "Carpeta Juan Pérez DS19",
        "body_preview": "",
        "classification": {"documentos": [
            {"tipo": "cedula", "filename": "cedula.pdf"},
            {"tipo": "liquidacion", "filename": "liq.pdf"},
            {"tipo": "certificado_smf", "filename": "cmf.pdf"},
        ]},
    }
    ok, motivo = _regla_solicitud_ok(item)
    assert ok is True, f"esperado True con 3 docs; motivo={motivo}"


def test_regla_solicitud_ok_rechaza_1_doc_sin_frase():
    from server import _regla_solicitud_ok
    item = {
        "subject": "Carpeta Juan Pérez DS19",
        "body_preview": "",
        "classification": {"documentos": [
            {"tipo": "cedula", "filename": "cedula.pdf"},
        ]},
    }
    ok, motivo = _regla_solicitud_ok(item)
    assert ok is False
    assert motivo


# ─── 3. zip/rar ────────────────────────────────────────────────────────
def test_bsdtar_binary_disponible():
    assert shutil.which("bsdtar"), "bsdtar no está instalado"


def test_expandir_zip_con_pdf_interno():
    from email_service import expandir_zip
    buf = io.BytesIO()
    pdf_bytes = b"%PDF-1.4\n%test\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("adjunto.pdf", pdf_bytes)
    resultado = expandir_zip("paquete.zip", buf.getvalue())
    assert len(resultado) == 1
    nombre, contenido = resultado[0]
    assert nombre.lower().endswith(".pdf")
    assert contenido == pdf_bytes


def test_expandir_zip_rar_corrupto_no_explota():
    from email_service import expandir_zip
    out = expandir_zip("basura.rar", b"esto no es un rar valido " * 20)
    assert out == []


# ─── 4. durabilidad búnker (scan_archivos restaura desde GridFS) ──────
def test_scan_archivos_restaura_desde_bunker():
    import folders_service as fsvc
    import bunker

    nombre = "YARITZA BRAVO"
    base = fsvc.folder_dir(nombre)
    if not base.exists():
        pytest.skip("Carpeta 'YARITZA BRAVO' no existe en preview")

    # Sube a GridFS lo que hay ahora (idempotente)
    try:
        bunker.sync_diff()
    except Exception as e:
        pytest.skip(f"búnker no disponible: {e}")

    orig = fsvc.scan_archivos(nombre)
    docs_orig = len(orig)
    assert docs_orig > 0, "carpeta original vacía en preview"

    bak = base.with_name(base.name + "_BAK_TEST")
    if bak.exists():
        shutil.rmtree(bak)
    shutil.move(str(base), str(bak))
    try:
        assert not base.exists(), "no debería existir tras mover"
        restaurada = fsvc.scan_archivos(nombre)  # dispara restauración desde GridFS
        assert base.exists(), "scan_archivos no restauró el directorio"
        assert len(restaurada) >= docs_orig, (
            f"restauración parcial: {len(restaurada)} vs {docs_orig}"
        )
    finally:
        # limpieza: restaurar SIEMPRE el directorio original desde _BAK
        if base.exists():
            shutil.rmtree(base, ignore_errors=True)
        shutil.move(str(bak), str(base))


# ─── 5. refetch adjuntos desde correo (IMAP real, lento) ──────────────
@pytest.mark.timeout(180)
def test_refetch_adjuntos_correo_real():
    from email_service import refetch_adjuntos, configured
    if not configured():
        pytest.skip("IMAP no configurado en preview")
    res = refetch_adjuntos(
        "EVALUACION - JORGE MANUEL SALAZAR GUAJARDO",
        "2026-08-25T21:35:08",
    )
    assert isinstance(res, list)
    assert len(res) > 5, f"esperados >5 adjuntos, obtenidos {len(res)}"
    for a in res:
        assert "filename" in a and "content_bytes" in a


# ─── 6. code-level: reevaluación no destructiva ───────────────────────
def test_reevaluacion_sin_shutil_rmtree_ni_delete_one():
    src = (BACKEND_DIR / "server.py").read_text()
    idx = src.find("SIN BORRADO DESTRUCTIVO")
    assert idx > 0, "marcador SIN BORRADO DESTRUCTIVO ausente"
    # ventana amplia alrededor del bloque de reevaluación
    inicio = src.rfind("async def", 0, idx)
    fin = src.find("\n\n@api.", idx)
    bloque = src[inicio:fin] if fin > 0 else src[inicio:idx + 4000]
    assert "shutil.rmtree" not in bloque, "reevaluación aún llama shutil.rmtree"
    assert "db.folders.delete_one" not in bloque, "reevaluación aún llama db.folders.delete_one"
    assert "revision_regla" in bloque, "no marca revision_regla"


# ─── 7. regresión endpoints + bloqueo lectura ─────────────────────────
@pytest.mark.parametrize("path", [
    "/api/central/dashboard-batch",
    "/api/carpetas/faltantes",
    "/api/clientes/folders",
])
def test_regresion_endpoints_get(admin_headers, path):
    r = requests.get(f"{BASE_URL}{path}", headers=admin_headers, timeout=60)
    assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"


def test_lectura_post_bloqueado(lectura_token):
    headers = {"Authorization": f"Bearer {lectura_token}"}
    # POST cualquiera protegido → debe ser 403 (o 401)
    r = requests.post(
        f"{BASE_URL}/api/procesamiento/recuperar-perdidos?dias=1",
        headers=headers,
        timeout=30,
    )
    assert r.status_code in (401, 403), f"esperaba 401/403, obtuve {r.status_code} {r.text[:200]}"
