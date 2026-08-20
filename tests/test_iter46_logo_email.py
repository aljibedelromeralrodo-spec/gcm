"""Iteration 46: Verificar logo en plantilla _email_institucional + envío real (1 correo).
Ejecutar con: cd /app/backend && pytest ../tests/test_iter46_logo_email.py -v -s
"""
import os
import re
import sys
import time
import pytest
import requests

sys.path.insert(0, "/app/backend")

PUBLIC_BASE_URL = "https://risk-assess-17.emergent.host"
LOGO_URL_A = "https://risk-assess-17.emergent.host/logo-cm.png"
LOGO_URL_B = "https://espejo-hibrido.preview.emergentagent.com/logo-cm.png"


# ------------------------ Plantilla: contenido HTML ------------------------
def test_email_institucional_contains_logo_and_spanish():
    from server import _email_institucional
    html = _email_institucional("Prueba QA", "<p>Verificación de logo en plantilla — favor ignorar.</p>")

    # (a) img src con PUBLIC_BASE_URL + /logo-cm.png
    assert f'src="{PUBLIC_BASE_URL}/logo-cm.png"' in html, "Falta img con PUBLIC_BASE_URL/logo-cm.png"
    assert 'alt="Central Mutuos"' in html

    # (b) header "CENTRAL MUTUOS" y "CON CRECES" intactos
    assert "CENTRAL MUTUOS" in html
    assert "CON CRECES" in html

    # (c) textos en español (saludo + pie confidencialidad)
    assert "Estimado/a" in html
    assert "Prueba QA" in html
    assert "confidencial" in html.lower()
    assert "elimínelo" in html or "elimínelo de inmediato" in html
    assert "Atentamente" in html

    # no inglés visible
    forbidden = ["Dear ", "Hello", "Regards", "Welcome", "Password", "Sincerely", "Best regards"]
    for w in forbidden:
        assert w not in html, f"Texto en inglés detectado: {w}"


# ------------------------ URLs del logo responden 200 image/png ------------------------
@pytest.mark.parametrize("url", [LOGO_URL_A, LOGO_URL_B])
def test_logo_url_serves_png(url):
    r = requests.get(url, timeout=15)
    assert r.status_code == 200, f"{url} devolvió {r.status_code}"
    ct = r.headers.get("content-type", "")
    assert "image/png" in ct.lower(), f"{url} content-type={ct}"
    assert len(r.content) > 500


# ------------------------ Regresión: correo_destinatarios y _enviar_credenciales en español + logo ------------------------
def test_correo_destinatarios_compiles_and_has_logo():
    import correo_destinatarios  # noqa: F401 -- confirma import os y compilación
    src = open("/app/backend/correo_destinatarios.py", encoding="utf-8").read()
    assert "import os" in src
    assert "/logo-cm.png" in src
    assert "PUBLIC_BASE_URL" in src


def test_enviar_credenciales_spanish():
    src = open("/app/backend/server.py", encoding="utf-8").read()
    # Buscar función _enviar_credenciales
    m = re.search(r"def _enviar_credenciales\(.*?\)\:(.*?)(?=\n@|\ndef )", src, re.S)
    assert m, "No se encontró _enviar_credenciales"
    body = m.group(1)
    for w in ["Welcome", "Password", "Username", "Dear ", "Regards"]:
        assert w not in body, f"Texto en inglés en _enviar_credenciales: {w}"
    assert "bienvenida" in body.lower() or "Bienvenido" in body
    assert "Contraseña" in body
    assert "INGRESAR A LA PLATAFORMA" in body


# ------------------------ ENVÍO REAL (1 solo correo) ------------------------
def test_envio_real_prueba_qa():
    from server import _email_institucional
    import email_service as mail

    html = _email_institucional(
        "Prueba QA",
        "<p>Verificación de logo en plantilla — favor ignorar.</p>",
    )
    # Un pequeño delay defensivo por throttling
    time.sleep(2)
    res = mail.send_mail(
        "javierurrutia@centralmutuos.cl",
        "Prueba QA logo plantilla — favor ignorar",
        html,
        [],
        "secundaria",
    )
    print("RESULT send_mail:", res)
    assert isinstance(res, dict), f"Respuesta inesperada: {res!r}"
    assert res.get("success") is True, f"success=False → {res}"
    assert res.get("smtp_code") == 250, f"smtp_code={res.get('smtp_code')} → {res}"
    desde = res.get("desde") or res.get("from") or ""
    assert "gerardo.ext@centralmutuos.cl" in desde, f"desde inesperado: {desde}"
