"""Iteración 42 — Verificación cambio de remitente predeterminado a gerardo.ext@centralmutuos.cl

- Backend only. Envía MÁXIMO 1 correo real (throttling 10s + reintento 60s).
- Verifica que send_mail(desde='principal') termina saliendo desde la cuenta corporativa.
- Verifica en Mongo (correos_smtp_log) que últimos envíos tienen desde=gerardo.ext@...
- Inspección de código: excepción anti auto-envío para el propio corporativo.
- Regresión rápida (curl) sobre POST /api/admin/users + login + delete (email dominio inválido OK).
"""
import os
import re
import sys
import time
import uuid
import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv

# Carga /app/backend/.env para que email_service tenga MONGO_URL/DB_NAME/MAIL2_*
BACKEND_DIR = Path("/app/backend")
load_dotenv(BACKEND_DIR / ".env")
sys.path.insert(0, str(BACKEND_DIR))

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001"
# Si la URL pública devuelve HTML (WAF), caemos a localhost
try:
    _probe = requests.get(f"{BASE_URL}/api/", timeout=5)
    if "text/html" in _probe.headers.get("content-type", "") or _probe.status_code >= 500:
        BASE_URL = "http://localhost:8001"
except Exception:
    BASE_URL = "http://localhost:8001"

CORP = "gerardo.ext@centralmutuos.cl"
BACKUP = "ethangerardobarr@gmail.com"


# ---------------------------------------------------------------------------
# Módulo email_service — verificación directa
# ---------------------------------------------------------------------------
class TestRemitentePorDefecto:
    def test_accounts_configurados(self):
        import email_service as mail
        roles = {a["rol"]: a["user"].lower() for a in mail.ACCOUNTS}
        assert roles.get("principal") == BACKUP.lower(), f"principal debe ser gmail, es {roles.get('principal')}"
        assert roles.get("secundaria") == CORP.lower(), f"secundaria debe ser corporativo, es {roles.get('secundaria')}"

    def test_bloque_remapeo_principal_a_secundaria(self):
        """Inspección de código: send_mail debe remapear desde='principal' → 'secundaria'."""
        src = (BACKEND_DIR / "email_service.py").read_text()
        # Debe existir el bloque REMITENTE PREDETERMINADO
        assert "REMITENTE PREDETERMINADO" in src, "Falta bloque REMITENTE PREDETERMINADO"
        m = re.search(r'if desde == "principal":\s*\n\s*desde = "secundaria"', src)
        assert m, "Falta el remapeo explícito desde='principal' → 'secundaria'"

    def test_excepcion_anti_autoenvio_corporativo(self):
        """Si destino == cuenta corporativa (secundaria), la 2ª capa debe cambiar emisor."""
        src = (BACKEND_DIR / "email_service.py").read_text()
        # 2ª capa: cambia emisor cuando destino coincide con acc.user
        assert "ANTI AUTO-ENVÍO (2ª capa)" in src or "2ª capa" in src, "Falta 2ª capa anti auto-envío"
        # _anti_autoenvio existe (1ª capa)
        assert "_anti_autoenvio" in src


# ---------------------------------------------------------------------------
# Envío real (1 correo) — a destinatario corporativo interno seguro
# ---------------------------------------------------------------------------
class TestEnvioReal:
    def test_send_mail_principal_termina_en_corporativa(self):
        """Envía 1 correo real con desde='principal'. Debe salir desde gerardo.ext@centralmutuos.cl,
        success=true, smtp_code=250."""
        import email_service as mail
        assert mail.configured(), "SMTP no configurado (MAIL_USER/MAIL2_USER faltan)"

        # Destinatario externo/interno seguro pedido por el usuario
        destino = "javierurrutia@centralmutuos.cl"
        subject = f"Prueba QA remitente — favor ignorar [{uuid.uuid4().hex[:6]}]"
        body = "<p>Prueba automática iteración 42 — verificación de remitente predeterminado.</p>"

        t0 = time.time()
        res = mail.send_mail(destino, subject, body, [], "principal")
        elapsed = time.time() - t0
        print(f"send_mail duración={elapsed:.1f}s res={res}")

        assert res.get("success") is True, f"Envío falló: {res}"
        assert res.get("smtp_code") == 250, f"smtp_code esperado 250, obtuvo {res.get('smtp_code')}"

        # Verificar en Mongo que el log dice desde=corporativa
        from pymongo import MongoClient
        cli = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=5000)
        db = cli[os.environ["DB_NAME"]]
        doc = db["correos_smtp_log"].find_one(
            {"subject": subject}, sort=[("fecha", -1)])
        assert doc is not None, f"No se encontró log para subject={subject}"
        assert doc.get("success") is True
        assert (doc.get("desde") or "").lower() == CORP.lower(), \
            f"desde en log debe ser {CORP}, obtuvo {doc.get('desde')}"
        print(f"Log OK: desde={doc.get('desde')} success={doc.get('success')} smtp_code={doc.get('smtp_code')}")

    def test_ultimos_logs_smtp_desde_corporativa(self):
        """Últimos 5 envíos success=true deberían tener desde=corporativa (excepto autoenvíos)."""
        from pymongo import MongoClient
        cli = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=5000)
        db = cli[os.environ["DB_NAME"]]
        ultimos = list(db["correos_smtp_log"].find(
            {"success": True}, sort=[("fecha", -1)]).limit(5))
        assert len(ultimos) > 0, "No hay logs de envíos exitosos"
        corp_count = sum(1 for d in ultimos if (d.get("desde") or "").lower() == CORP.lower())
        # Al menos 1 debe ser corporativa; los demás pueden ser autoenvíos legítimos
        print(f"Últimos 5 logs desde: {[d.get('desde') for d in ultimos]}")
        assert corp_count >= 1, f"Ningún log reciente sale desde {CORP}"


# ---------------------------------------------------------------------------
# Regresión POST /api/admin/users + login + delete
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"rut": "administrador", "password": "141617575"}, timeout=15)
    assert r.status_code == 200, f"Login admin falló: {r.status_code} {r.text[:200]}"
    tok = r.json().get("token")
    assert tok, "Token vacío"
    return tok


class TestRegresionCreateUser:
    def test_flujo_create_login_delete(self, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        codigo = "tempqa"
        clave = "PruebaQA123"

        # Limpieza previa por si quedó de un run anterior
        requests.delete(f"{BASE_URL}/api/admin/users/{codigo}", headers=headers, timeout=15)

        # CREATE
        payload = {"codigo": codigo, "nombre": "Temp QA", "email": "tempqa@x.cl",
                   "rol": "administracion", "clave": clave}
        r = requests.post(f"{BASE_URL}/api/admin/users", headers=headers, json=payload, timeout=90)
        assert r.status_code == 200, f"create_user devolvió {r.status_code}: {r.text[:300]}"
        data = r.json()
        assert data.get("ok") is True
        assert data.get("codigo") == codigo
        assert data.get("clave_provisoria") == clave, f"clave_provisoria esperada={clave} obtenida={data.get('clave_provisoria')}"
        # email_enviado puede ser true o false (dominio x.cl inexistente) — solo debe existir la key
        assert "email_enviado" in data

        # LOGIN con la clave provista
        r2 = requests.post(f"{BASE_URL}/api/auth/login",
                           json={"rut": codigo, "password": clave}, timeout=15)
        assert r2.status_code == 200, f"login tempqa falló: {r2.status_code} {r2.text[:200]}"
        d2 = r2.json()
        assert d2.get("token"), "Login no devolvió token"
        assert d2.get("first_login") is True, f"first_login debe ser true, obtuvo {d2.get('first_login')}"

        # DELETE
        r3 = requests.delete(f"{BASE_URL}/api/admin/users/{codigo}", headers=headers, timeout=15)
        assert r3.status_code in (200, 204), f"delete devolvió {r3.status_code}: {r3.text[:200]}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))
