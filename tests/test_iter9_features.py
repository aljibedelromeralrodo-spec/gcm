"""Iteration 9 tests: Historial, Gastos CLP, actividad-terminada origen, code checks."""
import os
import re
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
# fallback: read frontend/.env
if not BASE_URL:
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass

ERNESTO_FID = "7a510501-b702-4707-bc10-b1b3d4e8868a"


# ---------- Historial ----------
class TestHistorial:
    def test_historial_ernesto(self):
        r = requests.get(f"{BASE_URL}/api/clientes/folders/{ERNESTO_FID}/historial", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "nombre" in data and "eventos" in data
        eventos = data["eventos"]
        assert isinstance(eventos, list) and len(eventos) >= 3
        for e in eventos:
            assert "fecha" in e and "icono" in e and "titulo" in e and "detalle" in e
        # Order desc
        fechas = [e["fecha"] for e in eventos]
        assert fechas == sorted(fechas, reverse=True)
        titulos = [e["titulo"] for e in eventos]
        assert any("Carpeta creada" in t for t in titulos)
        assert any("Datos financieros" in t for t in titulos)
        assert any("Documentos faltantes" in t for t in titulos)


# ---------- Gastos Operacionales preview CLP ----------
class TestGastosCLP:
    def test_preview_incluye_total_clp(self):
        payload = {
            "confirm": False,
            "nombre": "TEST_Cliente",
            "email_cliente": "test@example.com",
            "items": [
                {"concepto": "Conservador", "valor": 21},
                {"concepto": "Estudio", "valor": 3},
            ],
        }
        r = requests.post(f"{BASE_URL}/api/gastos-operacionales/enviar", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json().get("body", "")
        assert "TOTAL EN PESOS" in body
        assert re.search(r"UF del d[ií]a \$[\d\.\,]+", body), body[:1000]
        assert re.search(r"\$[\d\.\,]+\s*CLP", body), body[:1000]


# ---------- actividad-terminada origen ----------
class TestActividadTerminadaOrigen:
    def test_tasacion_terminada_manual_origen(self):
        # set true
        r = requests.patch(
            f"{BASE_URL}/api/clientes/folders/{ERNESTO_FID}/actividad-terminada",
            json={"tipo": "tasacion", "terminado": True}, timeout=30)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("valor") is not None
        # verify historial contains origen manual
        h = requests.get(f"{BASE_URL}/api/clientes/folders/{ERNESTO_FID}/historial", timeout=30).json()
        tas_ev = [e for e in h["eventos"] if e["titulo"] == "Tasación terminada"]
        assert tas_ev, "Se esperaba evento 'Tasación terminada'"
        assert "manual" in tas_ev[0]["detalle"].lower()
        # restore null
        r2 = requests.patch(
            f"{BASE_URL}/api/clientes/folders/{ERNESTO_FID}/actividad-terminada",
            json={"tipo": "tasacion", "terminado": False}, timeout=30)
        assert r2.status_code == 200
        assert r2.json().get("valor") is None


# ---------- Code-level static checks ----------
class TestCodeStatic:
    SRC = "/app/backend/server.py"

    def _read(self):
        with open(self.SRC) as f:
            return f.read()

    def test_actividades_terminadas_loop_registered(self):
        src = self._read()
        # startup task for _actividades_terminadas_loop must be present (uncommented)
        assert re.search(r"^\s*asyncio\.create_task\(_task_blindada\(_actividades_terminadas_loop",
                         src, re.M), "loop actividades terminadas no registrado en startup"

    def test_faltantes_recordatorio_loop_commented(self):
        src = self._read()
        # The recordatorio loop line should be commented out
        # Find non-comment usage
        pat = re.compile(r"^\s*asyncio\.create_task\(_task_blindada\(_faltantes_recordatorio_loop", re.M)
        assert not pat.search(src), "_faltantes_recordatorio_loop NO debe estar activo en startup"

    def test_auto_faltantes_disabled_in_proc_upload_drive(self):
        """Regla del usuario: los faltantes se piden SOLO manualmente."""
        src = self._read()
        # Between proc_upload_drive and the next function def, no create_task(_enviar_faltantes_auto)
        m = re.search(r"async def proc_upload_drive\(.*?\n(.*?)\nasync def ", src, re.S)
        assert m, "no encontró proc_upload_drive"
        body = m.group(1)
        assert "_enviar_faltantes_auto" not in body, \
            "BUG: proc_upload_drive todavía llama a _enviar_faltantes_auto — el auto-envío NO está desactivado"

    def test_buscar_tasacion_terminada_imap_exists(self):
        src = self._read()
        assert "def _buscar_tasacion_terminada_imap" in src
        assert 'tasacion_terminado_origen": "auto"' in src

    def test_procesar_reparos_sets_estudio_terminado(self):
        src = self._read()
        # buscar bloque _procesar_reparos_folder que setea estudio_titulo_terminado_at cuando satisfecho
        m = re.search(r"async def _procesar_reparos_folder\(doc\):(.*?)(?=\nasync def |\ndef )", src, re.S)
        assert m
        body = m.group(1)
        assert "estudio_titulo_terminado_at" in body
        assert "satisfecho" in body
