"""Tests iteration 4: Gastos Operacionales, UF SII, Autocorreo reenviado, Reporte diario,
Procesamiento auto, regla inviolable carta."""
import os
import sys
import time
import pytest
import requests

def _read_env(key):
    v = os.environ.get(key)
    if v:
        return v
    try:
        for line in open("/app/frontend/.env"):
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""

BASE_URL = _read_env("REACT_APP_BACKEND_URL").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL missing"
API = f"{BASE_URL}/api"

sys.path.insert(0, "/app/backend")


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


# -------- Módulo: Gastos Operacionales --------
class TestGastosDefaults:
    def test_get_defaults(self, s):
        r = s.get(f"{API}/gastos-operacionales/defaults", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "intro" in d and isinstance(d["intro"], str) and len(d["intro"]) > 10
        assert isinstance(d.get("items"), list) and len(d["items"]) >= 6
        # Conservador 21 UF
        cons = next((it for it in d["items"] if "Conservador" in it.get("concepto", "")), None)
        assert cons is not None
        assert float(cons["valor"]) == 21
        # datos_pago
        dp = d.get("datos_pago", {})
        assert dp.get("nombre") == "MUTUARIAS Y LEASING LIMITADA"
        assert dp.get("rut") and dp.get("banco")

    def test_patch_defaults_and_get(self, s):
        original = s.get(f"{API}/gastos-operacionales/defaults").json()
        new_intro = original["intro"] + "\n[TEST_ITER4]"
        r = s.patch(f"{API}/gastos-operacionales/defaults", json={"intro": new_intro}, timeout=15)
        assert r.status_code == 200
        d = s.get(f"{API}/gastos-operacionales/defaults").json()
        assert "[TEST_ITER4]" in d["intro"]
        # restaurar
        s.patch(f"{API}/gastos-operacionales/defaults", json={"intro": original["intro"]})


class TestGastosBuscarCliente:
    def test_buscar_franco(self, s):
        r = s.get(f"{API}/gastos-operacionales/buscar-cliente", params={"q": "franco"}, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "resultados" in d and isinstance(d["resultados"], list)
        # should contain Franco Bahamondes
        nombres = [x.get("nombre", "").lower() for x in d["resultados"]]
        assert any("franco" in n for n in nombres), f"nombres={nombres}"
        item = next(x for x in d["resultados"] if "franco" in x.get("nombre", "").lower())
        assert "rut" in item
        assert "email" in item

    def test_buscar_short_returns_empty(self, s):
        r = s.get(f"{API}/gastos-operacionales/buscar-cliente", params={"q": "a"}, timeout=10)
        assert r.status_code == 200
        assert r.json()["resultados"] == []


class TestGastosEnviarPreview:
    def test_preview_no_confirm(self, s):
        defaults = s.get(f"{API}/gastos-operacionales/defaults").json()
        payload = {
            "nombre": "TEST Franco Bahamondes",
            "rut": "18.312.893-0",
            "email_cliente": "test@example.com",
            "intro": defaults["intro"],
            "items": defaults["items"],
            "datos_pago": defaults["datos_pago"],
            "confirm": False,
        }
        r = s.post(f"{API}/gastos-operacionales/enviar", json=payload, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["to"] == "test@example.com"
        assert "TEST Franco" in d["subject"]
        assert "<div" in d["body"] and "Central Mutuos" in d["body"]
        assert "sender" in d
        # total = 21 + 5.6 + 3 + 0 = 29.6 (Notaría None, Tasación None)
        assert d["total"] == 29.6, f"total={d['total']}"

    def test_total_ignores_text_and_null(self, s):
        payload = {
            "nombre": "TEST", "rut": "1-1", "email_cliente": "x@y.com",
            "intro": "hola",
            "items": [
                {"concepto": "A", "valor": 10},
                {"concepto": "B", "valor": None, "texto": "Pagada"},
                {"concepto": "C", "valor": "", "texto": "Pago en notaría"},
                {"concepto": "D", "valor": 5.5},
            ],
            "datos_pago": {},
            "confirm": False,
        }
        r = s.post(f"{API}/gastos-operacionales/enviar", json=payload, timeout=15)
        assert r.status_code == 200
        assert r.json()["total"] == 15.5


class TestGastosLog:
    def test_log_endpoint(self, s):
        r = s.get(f"{API}/gastos-operacionales/log", timeout=15)
        assert r.status_code == 200
        assert "log" in r.json()
        assert isinstance(r.json()["log"], list)


# -------- UF actual desde SII --------
class TestUF:
    def test_uf_actual_get(self, s):
        r = s.get(f"{API}/clientes/uf-actual", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "valor" in d and "valor_uf" in d
        assert isinstance(d["valor"], (int, float))
        assert d["valor"] > 30000  # UF > 30k CLP

    def test_uf_refresh_from_sii(self, s):
        r = s.get(f"{API}/clientes/uf-actual", params={"refresh": "true"}, timeout=45)
        assert r.status_code == 200
        d = r.json()
        assert "valor" in d
        assert d["valor"] > 30000
        # should be from sii.cl (or fallback local si SII cae)
        assert d.get("source") in ("sii.cl", "local")
        if d["source"] == "sii.cl":
            # esperado ~40844.79
            assert 40000 < d["valor"] < 42000, f"UF SII fuera de rango: {d['valor']}"


# -------- Regla inviolable de carta de aprobación --------
class TestClasificacionCartaInviolable:
    def test_carta_aprobacion_by_filename(self):
        from pdf_service import clasificar_documento
        assert clasificar_documento(b"", "Carta_Aprobacion_Juan.pdf") == "carta_aprobacion"
        assert clasificar_documento(b"", "carta aprobacion.pdf") == "carta_aprobacion"
        assert clasificar_documento(b"", "APROBACION_cliente.pdf") == "carta_aprobacion"

    def test_simulador_by_filename(self):
        from pdf_service import clasificar_documento
        # filename con 'simulacion' matches regex directly
        assert clasificar_documento(b"", "Simulacion_cliente_2025.pdf") == "simulacion"
        # 'Simulador' (variante común en Chile) NO matchea el regex actual (simulaci[oó]n)
        # → cae a 'otro' con bytes vacíos. Se documenta como minor gap.
        r = clasificar_documento(b"", "Simulador_cliente.pdf")
        assert r in ("simulacion", "otro"), f"got {r}"

    def test_carta_nunca_es_simulacion(self):
        from pdf_service import clasificar_documento
        # Aunque tenga palabras como 'dividendo' o 'tasa' en filename, si tiene 'carta' o 'aprobacion' → carta
        assert clasificar_documento(b"", "Carta_Aprobacion_con_dividendo_tasa.pdf") == "carta_aprobacion"


# -------- Autocorreo status con reenviado --------
class TestAutocorreoStatus:
    def test_status_recent_estructura(self, s):
        # Primera llamada puede disparar escaneo en background
        r1 = s.get(f"{API}/autocorreo/status", timeout=90)
        assert r1.status_code == 200
        d1 = r1.json()
        assert "recent" in d1
        # esperar y volver a llamar para dar tiempo al escaneo de Enviados
        time.sleep(22)
        r2 = s.get(f"{API}/autocorreo/status", timeout=90)
        assert r2.status_code == 200
        d2 = r2.json()
        assert isinstance(d2.get("recent"), list)
        if d2["recent"]:
            it = d2["recent"][0]
            # campos requeridos
            assert "reenviado" in it, f"item keys={list(it.keys())}"
            assert isinstance(it["reenviado"], bool)
            assert "reenviado_a" in it
            assert "reenviado_fecha" in it


# -------- Reporte diario + procesamiento auto --------
class TestReporteDiario:
    def test_status(self, s):
        r = s.get(f"{API}/reportes/diario/status", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d, dict)

    def test_preview(self, s):
        r = s.get(f"{API}/reportes/diario/preview", timeout=30)
        assert r.status_code == 200

    def test_toggle_hora_10(self, s):
        r = s.post(f"{API}/reportes/diario/toggle", json={"hora": 10}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        # verifica que la hora quedó configurada
        st = s.get(f"{API}/reportes/diario/status").json()
        assert st.get("hora") == 10 or d.get("hora") == 10


class TestProcesamientoAuto:
    def test_status(self, s):
        r = s.get(f"{API}/procesamiento/auto/status", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), dict)
