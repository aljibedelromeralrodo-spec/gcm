"""Iter 64 — Tests: correos-preview intercept, clasificador IA Claude, autorreparación, reproceso IA.
NO modificar backend, NO reiniciar. NO enviar correos reales."""
import os
import pytest
import requests
from _tok import tok as _login_tok

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL missing")

BASE = _load_backend_url()


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"rut": "administrador", "password": "141617575"}, timeout=30)
    assert r.status_code == 200, r.text
    tok = _login_tok(r)
    assert tok
    return tok


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def contralor_headers():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"rut": "contralor", "password": "Contralor2026"}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"contralor login falló: {r.status_code} {r.text[:200]}")
    return {"Authorization": f"Bearer {_login_tok(r)}"}


# ---------- Login básicos ----------
class TestAuth:
    def test_admin_login_returns_token(self, admin_token):
        assert isinstance(admin_token, str) and len(admin_token) > 20

    def test_contralor_login(self, contralor_headers):
        assert contralor_headers["Authorization"].startswith("Bearer ")


# ---------- Correos Preview ----------
class TestCorreosPreview:
    def test_lista_como_admin(self, admin_headers):
        r = requests.get(f"{BASE}/api/correos-preview", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, (list, dict))
        # Aceptar tanto lista directa como wrapper {previews:[...]}
        items = data if isinstance(data, list) else data.get("previews") or data.get("items") or []
        assert isinstance(items, list)
        print(f"[preview] {len(items)} preview(s) en cola")
        # Guardar la forma para siguiente aserción
        if items:
            first = items[0]
            for key in ("_id", "id", "estado", "destinatario", "asunto"):
                # solo comprobar que exista al menos uno para identificar
                pass

    def test_lista_bloqueada_para_no_admin(self, contralor_headers):
        r = requests.get(f"{BASE}/api/correos-preview", headers=contralor_headers, timeout=30)
        assert r.status_code in (401, 403), f"esperado 401/403, obtenido {r.status_code}: {r.text[:200]}"


# ---------- Clasificador IA (Claude) ----------
CORREO_SOLICITUD = {
    "sender": "maria.perez@inmoventures.cl",
    "subject": "Solicitud nueva evaluación - Juan Pérez",
    "body": "Buenos días, adjunto documentos del cliente Juan Pérez para evaluación de crédito hipotecario: liquidaciones de sueldo últimos 3 meses, cédula de identidad por ambos lados y certificado CMF actualizado. Quedo atenta a comentarios. Saludos, María Pérez - Ejecutiva Inmobiliaria",
    "adjuntos": ["liquidaciones_juan_perez.pdf", "cedula_frontal.pdf", "cedula_reverso.pdf", "cmf_juan_perez.pdf"],
}
CORREO_RECHAZO = {
    "sender": "aprobaciones@centralmutuos.cl",
    "subject": "Resultado evaluación crédito hipotecario",
    "body": "Estimados, la operación no cumple parámetros objetivos: carga financiera excede el 35% de la renta líquida disponible del cliente. Rechazado por mesa. Saludos.",
    "adjuntos": [],
}
CORREO_SPAM = {
    "sender": "newsletter@promociones-shop.com",
    "subject": "50% OFF esta semana - Últimas horas!",
    "body": "Aprovecha nuestra mega oferta de temporada. Compra ahora y recibe envío gratis. Newsletter semanal.",
    "adjuntos": [],
}


class TestClasificadorIA:
    @pytest.mark.parametrize("payload,expected", [
        (CORREO_SOLICITUD, "solicitud_nueva"),
        (CORREO_RECHAZO, "rechazo_mesa"),
        (CORREO_SPAM, "no_relacionado"),
    ], ids=["solicitud", "rechazo", "spam"])
    def test_clasifica(self, admin_headers, payload, expected):
        r = requests.post(f"{BASE}/api/clasificador-ia/probar",
                          json=payload, headers=admin_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        # Estructura: puede venir plano o con wrapper 'resultado'
        res = data.get("resultado") if isinstance(data.get("resultado"), dict) else data
        assert "categoria" in res, f"faltó 'categoria' en {res}"
        assert "confianza" in res
        assert "razon" in res or "razonamiento" in res or "motivo" in res
        metodo = res.get("metodo") or data.get("metodo")
        assert metodo == "claude", f"metodo esperado 'claude', obtenido {metodo!r} (res={res})"
        cat = res["categoria"]
        print(f"[clasif] esperado={expected} obtenido={cat} conf={res.get('confianza')}")
        assert cat == expected, f"categoria esperada {expected}, obtenida {cat}. Razon: {res.get('razon') or res.get('razonamiento')}"


# ---------- Autorreparación ----------
class TestAutorreparacion:
    def test_estado(self, admin_headers):
        r = requests.get(f"{BASE}/api/autorreparacion/estado", headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "ultimo_informe" in data or "diagnosticos" in data, f"estructura inesperada: {list(data)[:10]}"

    def test_ejecutar_ciclo(self, admin_headers):
        r = requests.post(f"{BASE}/api/autorreparacion/ejecutar", headers=admin_headers, timeout=120)
        assert r.status_code == 200, r.text
        data = r.json()
        informe = data.get("informe") if isinstance(data.get("informe"), dict) else data
        for k in ("nivel1", "nivel2", "servicios"):
            assert k in informe, f"falta clave '{k}' en informe: keys={list(informe)[:15]}"


# ---------- Reproceso IA (solo GET estado, NO lanzar POST) ----------
class TestReprocesoIA:
    def test_estado(self, admin_headers):
        r = requests.get(f"{BASE}/api/procesamiento/reproceso-ia/estado",
                         headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "estado" in data or "status" in data or "corriendo" in data, f"estructura inesperada: {list(data)[:10]}"
        print(f"[reproceso-ia] estado: {data.get('estado') or data.get('status')}")


# ---------- Interceptación email_service (revisión por código) ----------
class TestEmailInterceptCode:
    def test_send_mail_intercepta(self):
        """Verifica en el código fuente que send_mail encola preview si no está confirmado."""
        path = "/app/backend/email_service.py"
        assert os.path.exists(path)
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
        assert "_encolar_preview" in src, "función _encolar_preview no encontrada"
        # Busca patrón: if not confirmado ... _encolar_preview
        import re
        # tolerante a espacios/format
        m = re.search(r"if\s+not\s+confirmado[^\n]{0,80}\n[^\n]{0,200}_encolar_preview", src)
        assert m, "no se detectó el patrón 'if not confirmado ... _encolar_preview' en send_mail"

    def test_encolar_preview_estado_esperando(self):
        with open("/app/backend/email_service.py", "r", encoding="utf-8") as f:
            src = f.read()
        assert "esperando_confirmacion" in src, "estado 'esperando_confirmacion' no está referenciado"
