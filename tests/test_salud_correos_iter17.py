"""Tests for iteration 17: Salud (health) module, contactos emails autocomplete,
folder send-email preview with prefix, and regressions on SMTP log and gastos log.
"""
import os
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://risk-assess-17.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# -------- Salud --------
class TestSalud:
    def test_salud_estado_structure(self, client):
        r = client.get(f"{BASE_URL}/api/salud/estado", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        # top-level keys
        for k in ("monitoreo_buzon", "autocorreo_mesa", "cola_correos", "carpetas"):
            assert k in data, f"missing key {k}: {list(data.keys())}"
        mb = data["monitoreo_buzon"]
        assert mb.get("intervalo_min") == 2, mb
        for k in ("activo", "ultima_revision", "hace_min", "alerta"):
            assert k in mb, f"monitoreo_buzon missing {k}"
        cc = data["cola_correos"]
        assert cc.get("goteo_seg") == 10, cc
        assert cc.get("reintento_seg") == 60, cc
        for k in ("enviados_24h", "ultimos_envios", "ultimos_errores"):
            assert k in cc, f"cola_correos missing {k}"
        car = data["carpetas"]
        for k in ("creadas_24h", "ultimas"):
            assert k in car, f"carpetas missing {k}"

    def test_salud_monitoreo_avanza(self, client):
        """Consultar dos veces con ~150s de diferencia y verificar ultima_revision avanza."""
        r1 = client.get(f"{BASE_URL}/api/salud/estado", timeout=30).json()
        t1 = r1["monitoreo_buzon"].get("ultima_revision")
        print(f"first ultima_revision={t1}, hace_min={r1['monitoreo_buzon'].get('hace_min')}")
        # Sleep ~150s to give the 2-min background loop time to run
        time.sleep(150)
        r2 = client.get(f"{BASE_URL}/api/salud/estado", timeout=30).json()
        t2 = r2["monitoreo_buzon"].get("ultima_revision")
        hace = r2["monitoreo_buzon"].get("hace_min")
        print(f"second ultima_revision={t2}, hace_min={hace}")
        # Accept either: timestamp advanced, or hace_min small enough (loop ran)
        assert (t2 and t1 and t2 != t1) or (hace is not None and hace <= 3), (
            f"monitoreo did not advance: t1={t1} t2={t2} hace_min={hace}"
        )


# -------- Contactos emails --------
class TestContactosEmails:
    def test_emails_with_query(self, client):
        r = client.get(f"{BASE_URL}/api/contactos/emails", params={"q": "gmail"}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "contactos" in data, data
        lst = data["contactos"]
        assert isinstance(lst, list)
        assert len(lst) <= 15
        if lst:
            item = lst[0]
            for k in ("email", "nombre", "origen"):
                assert k in item, f"contacto item missing {k}: {item}"

    def test_emails_empty_query(self, client):
        r = client.get(f"{BASE_URL}/api/contactos/emails", params={"q": ""}, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "contactos" in data
        assert isinstance(data["contactos"], list)
        assert len(data["contactos"]) <= 15


# -------- Folder send-email preview with prefix --------
class TestFolderSendEmailPreview:
    def test_preview_subject_prefix(self, client):
        # Get a real folder id
        r = client.get(f"{BASE_URL}/api/clientes/folders-light", timeout=30)
        assert r.status_code == 200, r.text
        payload = r.json()
        folders = payload.get("folders") or payload.get("carpetas") or payload
        if isinstance(folders, dict):
            folders = folders.get("items") or []
        assert isinstance(folders, list) and folders, f"no folders: {payload}"
        # Try several folders to find one that can preview
        preview_data = None
        last_err = None
        for f in folders[:15]:
            fid = f.get("id") or f.get("_id") or f.get("folder_id")
            if not fid:
                continue
            body = {
                "to_addr": "test@test.cl",
                "subject_extra": "URGENTE",
                "ejecutivo_externo": "Javiera Garrido",
                "confirm": False,
                "force_incompleto": True,
            }
            rp = client.post(
                f"{BASE_URL}/api/clientes/folders/{fid}/send-email",
                json=body,
                timeout=45,
            )
            if rp.status_code == 200:
                preview_data = rp.json()
                print(f"used folder {fid} ({f.get('nombre') or f.get('cliente')})")
                break
            last_err = (rp.status_code, rp.text[:200])
        assert preview_data is not None, f"could not get preview from any folder; last={last_err}"
        # locate subject
        subj = (
            preview_data.get("subject")
            or preview_data.get("asunto")
            or (preview_data.get("preview") or {}).get("subject")
            or (preview_data.get("preview") or {}).get("asunto")
        )
        assert subj, f"no subject in preview: {preview_data}"
        print(f"subject={subj}")
        assert subj.startswith("Antecedentes crédito hipotecario — "), subj
        assert "— URGENTE" in subj, subj
        assert "— Ejecutivo: Javiera Garrido" in subj, subj


# -------- Regressions --------
class TestRegressions:
    def test_smtp_log(self, client):
        r = client.get(f"{BASE_URL}/api/correos/smtp-log", params={"limit": 5}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        # Expect a list or wrapper with items
        items = data if isinstance(data, list) else (data.get("items") or data.get("log") or data.get("envios") or [])
        assert isinstance(items, list)
        if items:
            # at least one has smtp_code field
            assert any("smtp_code" in it for it in items), items[0]

    def test_gastos_log(self, client):
        r = client.get(f"{BASE_URL}/api/gastos-operacionales/log", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        items = data if isinstance(data, list) else (data.get("items") or data.get("log") or data.get("gastos") or [])
        assert isinstance(items, list)
        if items:
            it = items[0]
            for k in ("pagado", "saldo", "estado_pago"):
                assert k in it, f"gasto item missing {k}: {list(it.keys())}"
