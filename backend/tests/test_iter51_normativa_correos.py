"""Iteración 51 — Verificación de:
1) Normativas FLUJO APROBACION MESA + CORREOS DEL SISTEMA registradas (24).
2) Bloqueo test.cl/qa.audit en email_service.send_mail.
3) Clasificación _clasificar ampliada (rechazo/aprobacion).
4) _parse_full_message extrae texto desde HTML.
5) Flujo constitucional _procesar_correo reenvía a gerardo.ext.
6) Interruptor maestro envios_automaticos=False.
7) Regresión endpoints: resumen-diario/estado, espejo-ia/modelo, visualizador/estado.
8) db.folders sin 'test.cl' ni 'qa.audit'.
"""
import os
import sys
import json
import uuid
import asyncio
import pytest
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
from _tok import tok as _login_tok

# Cargar .env del backend antes de importar módulos
BACKEND_DIR = "/app/backend"
sys.path.insert(0, BACKEND_DIR)
load_dotenv(os.path.join(BACKEND_DIR, ".env"))


# Un único event loop para todo el módulo (motor bind estable)
_LOOP = asyncio.new_event_loop()


def _run(coro):
    return _LOOP.run_until_complete(coro)


def _fresh_db():
    """Cliente motor nuevo ligado al loop del módulo (evita 'Event loop is closed')."""
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"], io_loop=_LOOP)
    return client[os.environ["DB_NAME"]], client

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://espejo-hibrido.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_CODIGO = "administrador"
ADMIN_PASS = "141617575"


@pytest.fixture(scope="module")
def admin_token():
    last_err = None
    for _ in range(3):
        try:
            r = requests.post(f"{API}/auth/login",
                              json={"rut": ADMIN_CODIGO, "password": ADMIN_PASS}, timeout=90)
            if r.status_code == 200:
                tok = _login_tok(r)
                assert tok
                return tok
            last_err = f"{r.status_code} {r.text[:200]}"
        except Exception as e:
            last_err = str(e)
    pytest.fail(f"login admin fallo: {last_err}")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ── Test 1: Normativas registradas ──
def test_1_normativas_flujo_aprobacion_y_correos(admin_headers):
    r = requests.get(f"{API}/dashai/normativas", headers=admin_headers, timeout=90)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    claves = {(n.get("clave") or "").upper() for n in data.get("normativas", [])}
    assert "FLUJO APROBACION MESA" in claves, f"Falta FLUJO APROBACION MESA. Claves: {sorted(claves)}"
    assert "CORREOS DEL SISTEMA" in claves, f"Falta CORREOS DEL SISTEMA. Claves: {sorted(claves)}"
    assert data.get("total") == 24, f"Total esperado 24, obtenido {data.get('total')}"


# ── Test 2: Bloqueo destinos de prueba ──
def test_2_bloqueo_destino_test_cl():
    import email_service
    # destino único test.cl
    res = email_service.send_mail("qa.audit.2026@test.cl", "x", "<p>x</p>")
    assert res.get("success") is False
    assert "prueba" in (res.get("error") or "").lower() or "test" in (res.get("error") or "").lower(), res

    # lista solo con test → bloqueado
    res2 = email_service.send_mail(["qa.audit.2026@test.cl"], "x", "<p>x</p>")
    assert res2.get("success") is False


# ── Test 3: Clasificación ampliada ──
def test_3_clasificar_rechazo_y_aprobacion():
    import mesa_verdad as mv
    rech = [
        "Estimados, el cliente no cumple requisitos",
        "Está muy pasado en carga financiera",
        "Cliente sobreendeudado",
        "Excede la carga permitida",
        "Renta insuficiente para el dividendo",
        "declinado por mesa",
    ]
    for t in rech:
        assert mv._clasificar(t) == "rechazo", f"esperaba rechazo para: {t!r} → {mv._clasificar(t)}"
    aprob = ["Cliente aprobado, favor continuar", "Pre-aprobado por mesa"]
    for t in aprob:
        assert mv._clasificar(t) == "aprobacion", f"esperaba aprobacion para: {t!r} → {mv._clasificar(t)}"


# ── Test 4: HTML → texto ──
def test_4_parse_full_message_html():
    import email_service as es
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Prueba HTML"
    msg["From"] = "x@y.cl"
    msg["Date"] = "Mon, 21 Aug 2026 10:00:00 -0400"
    html = "<html><body><p>Hola <b>mundo</b>, cliente <i>aprobado</i>.</p></body></html>"
    msg.attach(MIMEText(html, "html", "utf-8"))
    parsed = es._parse_full_message(msg)
    assert parsed.get("body"), f"body vacio: {parsed}"
    assert "<" not in parsed["body"], f"tags no removidos: {parsed['body']!r}"
    assert "aprobado" in parsed["body"].lower()
    assert parsed.get("body_html_text"), "body_html_text vacio"
    assert "aprobado" in parsed["body_html_text"].lower()


# ── Test 5: Flujo constitucional aprobación (monkeypatch) ──
def test_5_flujo_constitucional_aprobacion(monkeypatch):
    import email_service
    import mesa_verdad as mv

    captured = {}

    def mock_send(to, subject, body, attachments=None, desde="secundaria", cc=None,
                  headers=None, clave_sin_ajuste="", bcc=None, registro_fallo=True):
        captured["to"] = to
        captured["subject"] = subject
        captured["body"] = body
        captured["attachments"] = attachments
        return {"success": True}

    monkeypatch.setattr(email_service, "send_mail", mock_send)

    correo_id = "TEST-APROB-" + uuid.uuid4().hex[:8]
    msg = {
        "id": correo_id,
        "subject": "Re: Cliente Prueba Constitucional",
        "body": "Estimados, cliente aprobado por mesa. Saludos",
        "from": "aprobaciones@centralmutuos.cl",
        "date": "2026-08-21",
    }

    # Parchear también el 'db' que usa mesa_verdad y server con uno ligado a _LOOP
    fresh_db, client = _fresh_db()
    import database as _database
    monkeypatch.setattr(_database, "db", fresh_db)
    monkeypatch.setattr(mv, "db", fresh_db)
    try:
        _run(mv._procesar_correo(msg))
        reg = _run(fresh_db.mesa_verdad_log.find_one({"correo_id": correo_id}))
        assert reg, "No quedo registro en mesa_verdad_log"
        assert reg.get("tipo") == "aprobacion", f"tipo={reg.get('tipo')}"

        assert captured, "send_mail no fue invocado"
        assert captured["to"] == "gerardo.ext@centralmutuos.cl", captured["to"]
        assert "cliente aprobado por mesa" in (captured["body"] or "").lower(), \
            f"body reenviado no contiene texto original: {captured['body'][:300]}"

        assert reg.get("reenvio_gerardo", {}).get("ok") is True, reg.get("reenvio_gerardo")
    finally:
        _run(fresh_db.mesa_verdad_log.delete_many({"correo_id": {"$regex": "^TEST-APROB-"}}))
        client.close()


# ── Test 6: Interruptor maestro ──
def test_6_interruptor_maestro_envios_automaticos_false():
    import resumen_diario as rd
    fresh_db, client = _fresh_db()
    import database as _database
    _database.db = fresh_db
    rd.db = fresh_db
    try:
        st = _run(fresh_db.config.find_one({"_key": "resumen_diario_8am"}))
        if st is None:
            _run(rd._estado())
            st = _run(fresh_db.config.find_one({"_key": "resumen_diario_8am"}))
        assert st is not None
        assert st.get("envios_automaticos", False) is False, \
            f"envios_automaticos debe ser False, obtenido={st.get('envios_automaticos')}"
        permitido = _run(rd.envios_automaticos_permitidos())
        assert permitido is False
    finally:
        client.close()


# ── Test 7: Regresión endpoints ──
def test_7a_resumen_diario_estado(admin_headers):
    r = requests.get(f"{API}/resumen-diario/estado", headers=admin_headers, timeout=90)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert d.get("hora") == 8, f"hora={d.get('hora')}"
    assert d.get("destino") == "gerardo.ext@centralmutuos.cl", d.get("destino")


def test_7b_espejo_ia_modelo(admin_headers):
    r = requests.get(f"{API}/espejo-ia/modelo", headers=admin_headers, timeout=60)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert "n_reprobados" in d, f"n_reprobados ausente. Keys: {list(d.keys())}"


def test_7c_visualizador_estado(admin_headers):
    r = requests.get(f"{API}/visualizador/estado", headers=admin_headers, timeout=60)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert "carpetas" in d, f"carpetas ausente. Keys: {list(d.keys())}"


# ── Test 8: Datos limpios en folders ──
def test_8_folders_sin_dominios_prueba():
    fresh_db, client = _fresh_db()
    try:
        async def _scan():
            problematicos = []
            async for f in fresh_db.folders.find({}, {"_id": 0}):
                blob = json.dumps(f, default=str, ensure_ascii=False).lower()
                if "test.cl" in blob or "qa.audit" in blob:
                    problematicos.append(f.get("id") or f.get("nombre") or "?")
            return problematicos
        problematicos = _run(_scan())
        assert not problematicos, f"Folders con dominios de prueba: {problematicos[:10]}"
    finally:
        client.close()
