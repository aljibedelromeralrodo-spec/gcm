"""Iter22 tests:
 - POST /gastos-operacionales/enviar multi-correo (emails_extra dedupe, confirm:false)
 - GET /estudio-titulo/reparos/{fid} for a folder
 - Verify _reparos_cc code includes participantes (source inspection only, no real mail)
"""
import os
import re
import requests
import pytest

def _read_env():
    with open("/app/frontend/.env") as f:
        for ln in f:
            if ln.startswith("REACT_APP_BACKEND_URL="):
                return ln.split("=", 1)[1].strip()
    raise RuntimeError("REACT_APP_BACKEND_URL not found")

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or _read_env()).rstrip("/")
API = f"{BASE}/api"


# === Backend up ===
def test_api_root():
    r = requests.get(f"{API}/", timeout=15)
    assert r.status_code == 200


# === Gastos multi-correo (preview, confirm:false) ===
class TestGastosMultiCorreo:
    def _payload(self, extras):
        return {
            "nombre": "Franco Test",
            "rut": "11.111.111-1",
            "email_cliente": "cliente@example.cl",
            "emails_extra": extras,
            "items": [{"concepto": "Tasación", "valor": 100000}],
            "intro": "",
            "confirm": False,
        }

    def test_preview_dedupe_and_body(self):
        r = requests.post(f"{API}/gastos-operacionales/enviar",
                          json=self._payload("a@b.cl, c@d.cl, a@b.cl, cliente@example.cl"),
                          timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        # dedupe and NOT contain email_cliente
        assert "a@b.cl" in data["emails_extra"]
        assert "c@d.cl" in data["emails_extra"]
        # dedup: a@b.cl appears once
        assert sum(1 for e in data["emails_extra"] if e.lower() == "a@b.cl") == 1
        # cliente not in extras
        assert not any(e.lower() == "cliente@example.cl" for e in data["emails_extra"])
        assert data.get("body") and "<" in data["body"]
        assert data.get("total") == 100000
        assert "confirm" not in data or data.get("ok") is not True  # confirm:false => no send

    def test_preview_empty_extras(self):
        r = requests.post(f"{API}/gastos-operacionales/enviar",
                          json=self._payload(""), timeout=30)
        assert r.status_code == 200
        assert r.json().get("emails_extra") == []

    def test_preview_list_form(self):
        payload = self._payload(["x@y.cl", "z@w.cl", "x@y.cl"])
        r = requests.post(f"{API}/gastos-operacionales/enviar", json=payload, timeout=30)
        assert r.status_code == 200
        extras = r.json()["emails_extra"]
        assert extras == ["x@y.cl", "z@w.cl"]


# === Reparos GET for existing folder ===
class TestReparosGet:
    def test_reparos_endpoint_no_500(self):
        # get any folder
        r = requests.get(f"{API}/clientes/folders-light", timeout=20)
        assert r.status_code == 200
        folders = r.json() if isinstance(r.json(), list) else r.json().get("folders") or []
        assert folders, "No folders available for reparos test"
        # try folder that has estudio solicitado first, else fallback to first
        target = None
        for f in folders:
            if f.get("estudio_titulo_solicitado_at"):
                target = f
                break
        target = target or folders[0]
        fid = target.get("id")
        assert fid
        r2 = requests.get(f"{API}/estudio-titulo/reparos/{fid}", timeout=30)
        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert "reparos" in body
        assert "tipo_vivienda" in body


# === Source inspection: _reparos_cc includes participantes ===
def test_reparos_cc_includes_participantes():
    with open("/app/backend/server.py", "r", encoding="utf-8") as f:
        src = f.read()
    # find the function _reparos_cc block
    m = re.search(r"def _reparos_cc\(.*?\):(.*?)\n\n", src, flags=re.DOTALL)
    assert m, "Could not find _reparos_cc"
    body = m.group(1)
    assert "participantes" in body
    assert "estudio_reparos" in body


# === Source inspection: capture participantes in _procesar_reparos_folder ===
def test_procesar_reparos_captura_participantes():
    with open("/app/backend/server.py", "r", encoding="utf-8") as f:
        src = f.read()
    # look for participantes accumulation via to_cc_emails
    assert "to_cc_emails" in src
    assert "rep[\"participantes\"]" in src or "rep['participantes']" in src


# === email_service returns to_cc_emails in buscar_hilo_por_asunto ===
def test_email_service_to_cc_emails():
    with open("/app/backend/email_service.py", "r", encoding="utf-8") as f:
        src = f.read()
    assert "to_cc_emails" in src


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
