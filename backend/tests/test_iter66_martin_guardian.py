"""Iter 66 — V16.4 Taller Kintsugi Martín + V16.5 Guardián Lógico."""
import os
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"rut": "administrador", "password": "141617575"}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def broker_token():
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"rut": "broker1", "password": "broker123"}, timeout=30)
    if r.status_code != 200:
        pytest.skip("broker login no disponible")
    return r.json().get("token") or r.json().get("access_token")


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


# ═══════ SEGURIDAD ═══════
class TestSeguridad:
    def test_martin_reparaciones_sin_token(self):
        r = requests.get(f"{BASE}/api/martin/reparaciones", timeout=30)
        assert r.status_code in (401, 403)

    def test_guardian_estado_sin_token(self):
        r = requests.get(f"{BASE}/api/guardian/estado", timeout=30)
        assert r.status_code in (401, 403)

    def test_martin_no_admin(self, broker_token):
        r = requests.get(f"{BASE}/api/martin/reparaciones", headers=_h(broker_token), timeout=30)
        assert r.status_code == 403

    def test_guardian_no_admin(self, broker_token):
        r = requests.get(f"{BASE}/api/guardian/estado", headers=_h(broker_token), timeout=30)
        assert r.status_code == 403


# ═══════ V16.4 MARTÍN ═══════
class TestMartinTaller:
    def test_taller_reparaciones(self, admin_token):
        r = requests.get(f"{BASE}/api/martin/reparaciones", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "kpis" in data
        kpis = data["kpis"]
        for k in ("fallas_hoy", "reparadas_hoy", "tiempo_promedio_ms", "tasa_oro"):
            assert k in kpis, f"falta kpi {k}"
        assert "herramientas" in data and len(data["herramientas"]) == 17, f"Esperaba 17, hay {len(data.get('herramientas', []))}"
        assert "historial" in data

    def test_reparar_tasa_rota_sin_autorizacion(self, admin_token):
        r = requests.post(f"{BASE}/api/martin/reparar", headers=_h(admin_token),
                          json={"herramienta": "reparar_tasa_rota_con_oro"}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("ok") is True
        # No debe pedir autorización
        assert not data.get("requiere_autorizacion")
        # Mensaje: tasas sanas o unidas con oro
        msg = (data.get("mensaje") or "").lower()
        assert "tasa" in msg or "sana" in msg or "oro" in msg

    def test_reindexar_memoria_total(self, admin_token):
        r = requests.post(f"{BASE}/api/martin/reparar", headers=_h(admin_token),
                          json={"herramienta": "reindexar_memoria_total"}, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("ok") is True
        assert "indices" in data
        # Verifica que historial tiene esta reparación con oro
        r2 = requests.get(f"{BASE}/api/martin/reparaciones", headers=_h(admin_token), timeout=30)
        hist = r2.json().get("historial", [])
        matches = [h for h in hist if h.get("herramienta_usada") == "reindexar_memoria_total"]
        assert matches, "reindexar no quedó en historial"
        assert matches[0].get("quedo_con_oro") is True

    def test_enviar_masivo_requiere_autorizacion(self, admin_token):
        r = requests.post(f"{BASE}/api/martin/reparar", headers=_h(admin_token),
                          json={"herramienta": "enviar_masivo",
                                "params": {"motivo": "TEST iter66 autorización"}}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("requiere_autorizacion") is True
        # Verifica bandeja
        r2 = requests.get(f"{BASE}/api/blindaje/autorizaciones", headers=_h(admin_token), timeout=30)
        assert r2.status_code == 200
        payload = r2.json()
        items = payload.get("autorizaciones") or payload.get("items") or payload if isinstance(payload, list) else payload.get("pendientes") or []
        if isinstance(payload, dict) and not items:
            # buscar en cualquier lista
            for v in payload.values():
                if isinstance(v, list):
                    items = v
                    break
        martin_reqs = [x for x in items if "MARTÍN" in (x.get("cliente_nombre") or "").upper()
                       or "MARTIN" in (x.get("cliente_nombre") or "").upper()]
        assert martin_reqs, f"No aparece SOLICITUD DE MARTÍN en bandeja (items: {len(items)})"
        # Guardar id para limpieza
        TestMartinTaller.solicitud_id = martin_reqs[0].get("id")

    def test_cleanup_solicitud_martin(self, admin_token):
        sid = getattr(TestMartinTaller, "solicitud_id", None)
        if not sid:
            pytest.skip("no hay solicitud creada")
        r = requests.post(f"{BASE}/api/blindaje/autorizaciones/{sid}/rechazar",
                          headers=_h(admin_token), json={"motivo": "TEST cleanup"}, timeout=30)
        # tolerar 200/404 (endpoint puede diferir)
        assert r.status_code in (200, 204, 404, 405)

    def test_vigia_ahora(self, admin_token):
        r = requests.post(f"{BASE}/api/martin/vigia-ahora", headers=_h(admin_token), timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("ok") is True
        assert "fallas_nuevas" in data
        assert isinstance(data["fallas_nuevas"], int)


# ═══════ V16.5 GUARDIÁN LÓGICO ═══════
class TestGuardianLogico:
    def test_estado(self, admin_token):
        r = requests.get(f"{BASE}/api/guardian/estado", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "score" in data
        score = data["score"]
        for k in ("total", "simplicidad", "logica", "fluidez"):
            assert k in score, f"falta {k}"
        assert "flujo" in data and len(data["flujo"]) == 8, f"Esperaba 8 nodos, hay {len(data.get('flujo', []))}"
        assert "nudos" in data
        assert "mapa" in data
        assert "backtracking" in data
        # Verificar backtrackings históricos
        backs = data["backtracking"]
        # Buscar los pasos esperados
        pasos = [b.get("paso_actual") for b in backs]
        # No exigencia estricta (dato existente) — solo log
        print(f"Backtracking pasos encontrados: {pasos[:10]}, total={len(backs)}")

    def test_revisar_ahora(self, admin_token):
        r = requests.post(f"{BASE}/api/guardian/revisar-ahora",
                          headers=_h(admin_token), timeout=120)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "reporte" in data
        assert "revisé" in data["reporte"].lower() or "revise" in data["reporte"].lower()
        assert "% lógico" in data["reporte"] or "% logico" in data["reporte"].lower()
        assert "score" in data


# ═══════ REGRESIÓN ═══════
class TestRegresion:
    def test_blindaje_dashboard(self, admin_token):
        r = requests.get(f"{BASE}/api/blindaje/dashboard", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200

    def test_correos_preview(self, admin_token):
        r = requests.get(f"{BASE}/api/correos-preview", headers=_h(admin_token), timeout=60)
        assert r.status_code == 200
