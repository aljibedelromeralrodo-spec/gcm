"""Iteration 51 — Validación backend:
- Test 1: mesa_verdad._clasificar (regex ampliada de rechazo/aprobación)
- Test 2: email_service.send_mail bloquea destinos de prueba (test.cl / qa.audit)
- Test 3: Flujo constitucional MESA — reenvío inmediato a gerardo.ext (con mock)
- Test 4: API regresión (login, normativas, resumen-diario/estado, visualizador/estado)
"""
import os
import sys
import uuid
import asyncio
import pytest
import requests
from dotenv import load_dotenv

# Cargar backend/.env antes de importar módulos que leen os.environ
BACKEND_DIR = "/app/backend"
load_dotenv(os.path.join(BACKEND_DIR, ".env"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or "https://espejo-hibrido.preview.emergentagent.com"
BASE_URL = BASE_URL.rstrip("/")


# ── Test 1: clasificador puro ─────────────────────────────────────────────
class TestClasificar:
    def test_rechazo_no_cumple_requisitos(self):
        from mesa_verdad import _clasificar
        assert _clasificar("el cliente no cumple requisitos") == "rechazo"

    def test_rechazo_pasado_en_carga(self):
        from mesa_verdad import _clasificar
        assert _clasificar("Está muy pasado en carga financiera") == "rechazo"

    def test_rechazo_sobreendeudado(self):
        from mesa_verdad import _clasificar
        assert _clasificar("Cliente sobreendeudado") == "rechazo"

    def test_rechazo_renta_insuficiente(self):
        from mesa_verdad import _clasificar
        assert _clasificar("Renta insuficiente para el dividendo") == "rechazo"

    def test_aprobacion(self):
        from mesa_verdad import _clasificar
        assert _clasificar("Cliente aprobado, favor continuar") == "aprobacion"


# ── Test 2: bloqueo de destinos de prueba ─────────────────────────────────
class TestBloqueoDestinoPrueba:
    def test_bloquea_qa_audit_test_cl(self):
        import email_service
        res = email_service.send_mail("qa.audit.2026@test.cl", "x", "<p>x</p>")
        assert res.get("success") is False
        err = (res.get("error") or "").lower()
        assert "prueba" in err or "test.cl" in err, f"Error inesperado: {res}"


# ── Test 3: flujo constitucional con monkeypatch ──────────────────────────
def test_flujo_constitucional_reenvio_gerardo(monkeypatch):
    asyncio.run(_flujo_constitucional_impl(monkeypatch))


async def _flujo_constitucional_impl(monkeypatch):
    import mesa_verdad
    import email_service
    from database import db

    captured = {}

    def fake_send_mail(to, subject, body_html, attachments=None, desde="secundaria",
                      cc=None, headers=None, clave_sin_ajuste="", bcc=None, registro_fallo=True):
        captured["to"] = to
        captured["subject"] = subject
        captured["body_html"] = body_html
        captured["attachments"] = attachments
        return {"success": True}

    monkeypatch.setattr(email_service, "send_mail", fake_send_mail)

    correo_id = f"TEST-APROB-{uuid.uuid4()}"
    msg = {
        "id": correo_id,
        "subject": "Re: Prueba QA Constitucional",
        "body": "cliente aprobado por mesa",
        "from": "aprobaciones@centralmutuos.cl",
        "date": "2026-08-21",
    }

    try:
        registro = await mesa_verdad._procesar_correo(msg)
        assert registro is not None, "El registro devuelto no debe ser None"
        assert registro.get("tipo") == "aprobacion", f"tipo={registro.get('tipo')}"
        reenvio = registro.get("reenvio_gerardo") or {}
        assert reenvio.get("ok") is True, f"reenvio_gerardo={reenvio}"
        assert captured.get("to") == "gerardo.ext@centralmutuos.cl", f"to={captured.get('to')}"
        assert "cliente aprobado por mesa" in (captured.get("body_html") or ""), \
            "El cuerpo reenviado no contiene el body original"
    finally:
        await db.mesa_verdad_log.delete_many({"correo_id": correo_id})


# ── Test 4: regresión de APIs ─────────────────────────────────────────────
@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"rut": "administrador", "password": "141617575"}, timeout=30)
    assert r.status_code == 200, f"login: {r.status_code} {r.text[:200]}"
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    assert tok, f"sin token: {data}"
    return tok


@pytest.fixture(scope="module")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


class TestAPIRegresion:
    def test_normativas_contiene_flujo_y_visualizador(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/dashai/normativas", headers=auth_headers, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        data = r.json()
        claves = {n.get("clave") for n in data.get("normativas", [])}
        assert "FLUJO APROBACION MESA" in claves, f"faltante FLUJO APROBACION MESA. claves={claves}"
        assert "VISUALIZADOR COGNITIVO" in claves, f"faltante VISUALIZADOR COGNITIVO. claves={claves}"
        assert data.get("total") == 25, f"total={data.get('total')} esperado 25"

    def test_resumen_diario_estado(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/resumen-diario/estado", headers=auth_headers, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        data = r.json()
        assert data.get("hora") == 8, f"hora={data.get('hora')}"
        assert data.get("destino") == "gerardo.ext@centralmutuos.cl", f"destino={data.get('destino')}"
        assert data.get("envios_automaticos") is False, f"envios_automaticos={data.get('envios_automaticos')}"

    def test_visualizador_estado(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/visualizador/estado", headers=auth_headers, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
