"""Iteration 50 tests — Panel de Estado + normativas + regresión rápida."""
import os
import pytest
import requests
from _tok import tok as _login_tok

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
FID_EDUAR = "c65e1cce-2407-42a8-8ee4-c16b874a2b24"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE}/api/auth/login", json={"rut": "administrador", "password": "141617575"}, timeout=20)
    assert r.status_code == 200, r.text
    return _login_tok(r)


@pytest.fixture(scope="module")
def broker_token():
    r = requests.post(f"{BASE}/api/auth/login", json={"rut": "broker", "password": "Broker2026"}, timeout=20)
    assert r.status_code == 200, r.text
    return _login_tok(r)


@pytest.fixture(scope="module")
def ah(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def bh(broker_token):
    return {"Authorization": f"Bearer {broker_token}"}


# ── Panel Estado ──
def test_panel_estado_eduar(ah):
    r = requests.get(f"{BASE}/api/clientes/folders/{FID_EDUAR}/panel-estado", headers=ah, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("resultado", "enviado_sistema", "detalle_sistema", "enviado_correo", "detalle_correo",
             "dias_sin_movimiento", "alerta_inactividad", "documentos_faltantes", "destinatario_solicitud"):
        assert k in d, f"missing key {k}"
    assert d["enviado_correo"] is True, d
    assert d["detalle_correo"] is not None
    for k in ("fecha", "destinatario", "contenido"):
        assert k in d["detalle_correo"]
    assert isinstance(d["dias_sin_movimiento"], int)


def test_panel_estado_404(ah):
    r = requests.get(f"{BASE}/api/clientes/folders/no-existe-xxx/panel-estado", headers=ah, timeout=20)
    assert r.status_code == 404


# ── Normativas nuevas ──
def test_normativas_nuevas_en_dashai():
    import asyncio, sys
    sys.path.insert(0, "/app/backend")
    from database import db

    async def _q():
        claves = ["REGLA 3 DOCUMENTOS", "MODULOS PROTEGIDOS", "PALETA OFICIAL",
                  "GASTOS OPERACIONALES", "PREVIEW OBLIGATORIO"]
        found = {}
        for c in claves:
            doc = await db.dashai_eventos.find_one({"motivo": "normativa", "norma_clave": c})
            found[c] = doc is not None
        return found

    found = asyncio.get_event_loop().run_until_complete(_q())
    missing = [k for k, v in found.items() if not v]
    assert not missing, f"Normativas faltantes en db.dashai_eventos: {missing}"


# ── Regresión ──
def test_calendario_mes(ah):
    r = requests.get(f"{BASE}/api/clientes/calendario?mes=2026-08", headers=ah, timeout=20)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, (list, dict))


def test_calendario_dia(ah):
    r = requests.get(f"{BASE}/api/clientes/calendario/dia?fecha=2026-08-19", headers=ah, timeout=20)
    assert r.status_code == 200
    d = r.json()
    assert "del_dia" in d and "pendientes_anteriores" in d
    # cada folder debe tener campo descartada
    for fol in (d.get("del_dia") or []) + (d.get("pendientes_anteriores") or []):
        assert "descartada" in fol, f"missing descartada in {fol.get('id')}"


def test_widget_correos_hoy_admin(ah):
    r = requests.get(f"{BASE}/api/dashboard/correos-solicitud-hoy", headers=ah, timeout=20)
    assert r.status_code == 200


def test_widget_correos_hoy_broker_403(bh):
    r = requests.get(f"{BASE}/api/dashboard/correos-solicitud-hoy", headers=bh, timeout=20)
    assert r.status_code == 403


def test_escrituracion_token_invalido_publico():
    r = requests.get(f"{BASE}/api/escrituracion/confirmar/tokeninvalidoxxx", timeout=20, allow_redirects=False)
    assert r.status_code == 404
    # debe retornar HTML (ruta pública)
    assert "text/html" in r.headers.get("content-type", "").lower()


def test_verificar_pin_maestro_ok(ah):
    r = requests.post(f"{BASE}/api/seguridad/verificar-pin-maestro",
                      headers=ah, json={"pin": "0586"}, timeout=20)
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True
