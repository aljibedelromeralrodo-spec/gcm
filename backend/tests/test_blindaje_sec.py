"""Blindaje de secretos (Frente A) — unitario, sin SMTP ni backend vivo.

Cubre: comparación de PIN sin default '!', política Gmail push compatible,
cifrado Crece con Fernet. No toca flujos de Mesa ni envío de correo.
"""
import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = str(Path(__file__).resolve().parents[1])
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import auth  # noqa: E402


@pytest.fixture(autouse=True)
def _limpiar_env_blindaje(monkeypatch):
    for k in ("MASTER_PIN", "ADMIN_PASSWORD_1", "ADMIN_PASSWORD_2",
              "GMAIL_PUSH_TOKEN", "GMAIL_PUSH_REQUIRE_AUTH", "GMAIL_PUSH_AUDIENCE",
              "CRED_CIPHER_KEY"):
        monkeypatch.delenv(k, raising=False)
    yield


class TestCookieHttpOnly:
    def test_fijar_cookie_es_httponly(self):
        from starlette.responses import JSONResponse
        r = JSONResponse({"ok": True})
        auth.fijar_cookie(r, "jwt.de.prueba")
        sc = (r.headers.get("set-cookie") or "").lower()
        assert "cm_token=" in sc
        assert "httponly" in sc
        assert "samesite=lax" in sc

    def test_borrar_cookie(self):
        from starlette.responses import JSONResponse
        r = JSONResponse({"ok": True})
        auth.borrar_cookie(r)
        sc = (r.headers.get("set-cookie") or "").lower()
        assert "cm_token=" in sc
        assert "max-age=0" in sc or "max-age=0" in sc.replace(" ", "")

    def test_logout_es_ruta_publica(self):
        assert "/api/auth/logout" in auth.PUBLIC_EXACT


class TestSecretos:
    def test_secret_eq_vacio_es_false(self):
        assert auth.secret_eq("", "") is False
        assert auth.secret_eq("abc", "") is False
        assert auth.secret_eq("abc", "abc") is True
        assert auth.secret_eq("abc", "abd") is False

    def test_master_pin_sin_entorno_rechaza_exclamacion(self):
        assert auth.master_pin() == ""
        assert auth.master_pin_ok("!") is False
        assert auth.master_pin_ok("") is False
        assert auth.master_pin_ok("cualquiera") is False

    def test_master_pin_configurado(self, monkeypatch):
        monkeypatch.setenv("MASTER_PIN", "pin-maestro-ok")
        assert auth.master_pin_ok("pin-maestro-ok") is True
        assert auth.master_pin_ok("otro") is False
        assert auth.master_pin_ok("!") is False

    def test_admin_clave_solo_entorno(self, monkeypatch):
        assert auth.admin_clave_ok("141617575") is False
        monkeypatch.setenv("ADMIN_PASSWORD_1", "clave-admin-env")
        assert auth.admin_clave_ok("clave-admin-env") is True
        assert auth.admin_clave_ok("141617575") is False


class TestGmailPush:
    def test_sin_config_acepta_para_no_tumbar_ingesta(self):
        assert auth.gmail_push_permitido() is True
        assert auth.gmail_push_permitido("Bearer basura", "") is True

    def test_token_compartido_exige_coincidencia(self, monkeypatch):
        monkeypatch.setenv("GMAIL_PUSH_TOKEN", "secreto-push")
        assert auth.gmail_push_permitido("", "secreto-push") is True
        assert auth.gmail_push_permitido("", "otro") is False
        assert auth.gmail_push_permitido("", "") is False

    def test_oidc_valido_pasa_aunque_haya_token(self, monkeypatch):
        monkeypatch.setenv("GMAIL_PUSH_TOKEN", "secreto-push")
        assert auth.gmail_push_permitido(
            "Bearer jwt-google", "", oidc_check=lambda t: t == "jwt-google") is True

    def test_require_auth_sin_oidc_rechaza(self, monkeypatch):
        monkeypatch.setenv("GMAIL_PUSH_REQUIRE_AUTH", "1")
        assert auth.gmail_push_permitido("", "", oidc_check=lambda t: False) is False
        assert auth.gmail_push_permitido(
            "Bearer jwt-google", "", oidc_check=lambda t: t == "jwt-google") is True

    def test_oidc_basura_corta_no_llama_google(self):
        assert auth._oidc_google_ok("corto") is False
        assert auth._oidc_google_ok("") is False


class TestCifradoCrece:
    def test_sin_clave_no_cifra(self):
        assert auth.cifrar_secreto("mipass") is None
        assert auth.descifrar_secreto("gAAAA") is None

    def test_roundtrip_fernet(self, monkeypatch):
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
        monkeypatch.setenv("CRED_CIPHER_KEY", key)
        token = auth.cifrar_secreto("ClaveCrece/2026")
        assert token and token != "ClaveCrece/2026"
        assert auth.descifrar_secreto(token) == "ClaveCrece/2026"
