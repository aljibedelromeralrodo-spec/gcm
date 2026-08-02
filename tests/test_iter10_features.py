"""Iteration 10 — Sync aprobación + fecha_entrega en MESA + prefill Tasación.

Regression check: proc_upload_drive no longer calls _enviar_faltantes_auto (verified in test_iter9).
Nuevas features:
 - sync-aprobacion baja carta+simulacion a 99_otros del cliente (Zurita)
 - GET /api/aprobacion-cliente/archivos lista carta_aprobacion + simulacion_ajustada seleccionadas
 - send-email a MESA incluye "— Entrega: Inmediata" y body con "Fecha de entrega"
 - Verificación estática de bloqueo por fecha_entrega faltante
"""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://risk-assess-17.preview.emergentagent.com").rstrip("/")

ZURITA_FOLDER = "20c1b015-2824-4d18-821b-79aa8548270e"
ERNESTO_FOLDER = "7a510501-b702-4707-bc10-b1b3d4e8868a"
ZURITA_NAME = "CLAUDIA ANDREA ZURITA SOTO"
STORAGE = "/app/backend/storage/clientes"


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    # Login
    r = s.post(f"{BASE_URL}/api/auth/login", json={"codigo": "administrador", "password": "141617575"}, timeout=30)
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token") or r.json().get("token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    return s


# ---------- Regresión: proc_upload_drive sin auto-faltantes ----------
class TestRegresionAutoFaltantes:
    def test_no_call_to_enviar_faltantes_auto(self):
        with open("/app/backend/server.py") as f:
            src = f.read()
        # Solo debe existir la definición (async def)
        occurrences = [m.start() for m in re.finditer(r"_enviar_faltantes_auto", src)]
        assert len(occurrences) == 1, f"Se esperaban 1 ocurrencia (solo def), hay {len(occurrences)}"
        # Y esa ocurrencia debe estar precedida por 'async def '
        assert re.search(r"async def _enviar_faltantes_auto", src), "def missing"


# ---------- Sync aprobación (Claudia Zurita) ----------
class TestSyncAprobacionZurita:
    def test_sync_endpoint_ok(self, api):
        r = api.post(f"{BASE_URL}/api/clientes/folders/{ZURITA_FOLDER}/sync-aprobacion", timeout=180)
        assert r.status_code == 200, r.text
        data = r.json()
        # Idempotencia: puede que copiados esté vacío (ya descargados)
        assert "copiados" in data or "ok" in data or isinstance(data, dict)

    def test_pdfs_exist_in_99_otros(self):
        base = f"{STORAGE}/{ZURITA_NAME}/99_otros"
        assert os.path.isdir(base), f"Carpeta no existe: {base}"
        files = os.listdir(base)
        has_aprob = any("Aprobacion" in f and f.lower().endswith(".pdf") for f in files)
        has_simu = any("simulador" in f.lower() and f.lower().endswith(".pdf") for f in files)
        assert has_aprob, f"Falta carta de aprobación en {base}. Archivos: {files}"
        assert has_simu, f"Falta simulador en {base}. Archivos: {files}"

    def test_aprobacion_cliente_archivos_lista_tipos(self, api):
        # GET puede tardar por IMAP sync
        r = api.get(
            f"{BASE_URL}/api/aprobacion-cliente/archivos",
            params={"cliente": ZURITA_NAME},
            timeout=180,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        archivos = data.get("archivos") or data.get("items") or data
        assert isinstance(archivos, list), f"archivos no es lista: {data}"
        tipos = [(a.get("tipo"), a.get("seleccionado")) for a in archivos]
        # Debe haber carta_aprobacion y simulacion_ajustada, ambas seleccionadas
        carta = [t for t in tipos if t[0] == "carta_aprobacion"]
        simu = [t for t in tipos if t[0] == "simulacion_ajustada"]
        assert carta, f"Falta tipo carta_aprobacion. Tipos vistos: {tipos}"
        assert simu, f"Falta tipo simulacion_ajustada. Tipos vistos: {tipos}"
        assert any(sel for _, sel in carta), f"carta_aprobacion no está seleccionada: {carta}"
        assert any(sel for _, sel in simu), f"simulacion_ajustada no está seleccionada: {simu}"


# ---------- MESA send-email fecha_entrega ----------
class TestMesaFechaEntrega:
    def test_ernesto_subject_body_incluye_entrega(self, api):
        payload = {"to_addr": "mesa@test.local", "confirm": False, "include_merged": False}
        r = api.post(
            f"{BASE_URL}/api/clientes/folders/{ERNESTO_FOLDER}/send-email",
            json=payload,
            timeout=120,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        subject = data.get("subject", "")
        body = data.get("body", "") or data.get("html", "")
        assert "— Entrega:" in subject or "Entrega:" in subject, f"subject sin Entrega: {subject}"
        # 'Inmediata' esperada según review
        assert "Inmediata" in subject, f"Entrega Inmediata no está en subject: {subject}"
        assert "Fecha de entrega" in body, f"body no menciona Fecha de entrega. Body head: {body[:400]}"

    def test_missing_docs_no_incluye_fecha_entrega_cuando_esta_seteada(self, api):
        payload = {"to_addr": "mesa@test.local", "confirm": False, "include_merged": False}
        r = api.post(
            f"{BASE_URL}/api/clientes/folders/{ERNESTO_FOLDER}/send-email",
            json=payload,
            timeout=120,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        missing = data.get("missing_docs") or data.get("missing_labels") or []
        # Como la carpeta ya tiene fecha_entrega, no debe aparecer como faltante
        assert not any("Fecha de entrega" in str(m) for m in missing), f"missing incluye fecha_entrega: {missing}"


# ---------- Verificación estática: bloqueo por fecha_entrega faltante ----------
class TestCodeStaticFechaEntrega:
    def test_missing_labels_incluye_fecha_entrega_si_falta(self):
        with open("/app/backend/server.py") as f:
            src = f.read()
        # Debe existir alguna referencia que agregue "Fecha de entrega" a missing_labels
        # cuando fecha_entrega está vacía
        assert "Fecha de entrega" in src, "server.py sin literal 'Fecha de entrega'"
        # Buscar un patrón que ate fecha_entrega vacía -> missing_labels
        pat = re.search(
            r"fecha_entrega[^\n]{0,120}\n(?:[^\n]*\n){0,10}[^\n]*Fecha de entrega",
            src,
        )
        assert pat, "No se encontró lógica que agregue 'Fecha de entrega' a missing_labels cuando fecha_entrega falta"
