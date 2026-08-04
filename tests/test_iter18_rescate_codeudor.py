"""Iteration 18 — rescate/codeudor/seguimiento + regression."""
import os
import io
import time
import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path("/app/frontend/.env"))
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

MELISA_FID = "ed93f803-9dee-4da6-9e7f-fef3f5e6f6b9"  # Melisa Rivera


# ---------- Regression (after database.py modularization) ----------
class TestRegression:
    def test_salud(self):
        r = requests.get(f"{BASE}/api/salud/estado", timeout=15)
        assert r.status_code == 200
        assert "monitoreo" in r.json() or isinstance(r.json(), dict)

    def test_gastos_log(self):
        r = requests.get(f"{BASE}/api/gastos-operacionales/log", timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert "log" in j and isinstance(j["log"], list)

    def test_smtp_log(self):
        r = requests.get(f"{BASE}/api/correos/smtp-log", timeout=15)
        assert r.status_code == 200

    def test_seguimiento_clientes(self):
        r = requests.get(f"{BASE}/api/seguimiento/clientes", timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert "clientes" in j or isinstance(j, list)


# ---------- Rescate ----------
class TestRescate:
    def test_pendientes_list(self):
        r = requests.get(f"{BASE}/api/rescate/pendientes", timeout=15)
        assert r.status_code == 200
        pend = r.json()["pendientes"]
        assert len(pend) >= 1
        for p in pend:
            assert "id" in p and "subject" in p and "sender" in p
            assert "motivo" in p and "adjuntos" in p and "cliente_sugerido" in p

    def test_asignar_una_palabra_400(self):
        # Any random id — validation should fail before lookup, but even with fake id we expect 400
        r = requests.post(
            f"{BASE}/api/rescate/00000000-0000-0000-0000-000000000000/asignar",
            json={"cliente": "Solo", "tipo_documento": ""},
            timeout=15,
        )
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text[:300]}"

    def test_asignar_luis_fonseca(self):
        # find Luis Fonseca pendiente
        r = requests.get(f"{BASE}/api/rescate/pendientes", timeout=15)
        pend = r.json()["pendientes"]
        luis = next((p for p in pend if "Luis Fonseca" in p["subject"]), None)
        if luis is None:
            pytest.skip("Luis Fonseca pendiente already resolved")
        pid = luis["id"]
        r = requests.post(
            f"{BASE}/api/rescate/{pid}/asignar",
            json={"cliente": "Luis Fonseca", "tipo_documento": ""},
            timeout=60,
        )
        assert r.status_code == 200, f"asignar failed {r.status_code}: {r.text[:500]}"
        j = r.json()
        assert j.get("ok") is True, j

        # verify LUIS FONSECA folder exists
        r2 = requests.get(f"{BASE}/api/clientes/folders-light", timeout=15)
        folders = r2.json().get("folders", [])
        names = [f["nombre"].upper() for f in folders]
        assert any("LUIS FONSECA" in n or "FONSECA" in n for n in names), names

        # verify pendiente no longer in list
        r3 = requests.get(f"{BASE}/api/rescate/pendientes", timeout=15)
        ids_now = [p["id"] for p in r3.json()["pendientes"]]
        assert pid not in ids_now, f"pendiente {pid} still present"


# ---------- Codeudor ----------
class TestCodeudor:
    def test_add_codeudor_and_upload_delete(self):
        # add codeudor Maria Prueba to Melisa Rivera folder
        r = requests.post(
            f"{BASE}/api/clientes/folders/{MELISA_FID}/codeudor",
            json={"nombre": "Maria Prueba"},
            timeout=30,
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        j = r.json()
        assert j.get("ok") is True, j

        # upload a tiny PDF as codeudor file
        pdf_bytes = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
        files = {"file": ("prueba_codeudor.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        data = {"codeudor_nombre": "Maria Prueba"}
        ru = requests.post(
            f"{BASE}/api/clientes/folders/{MELISA_FID}/upload-file",
            files=files, data=data, timeout=60,
        )
        assert ru.status_code == 200, f"upload {ru.status_code}: {ru.text[:400]}"

        # fetch folder detail — look for 05_codeudor/Maria Prueba/CODEUDOR_*
        rd = requests.get(f"{BASE}/api/clientes/folders/{MELISA_FID}", timeout=30)
        assert rd.status_code == 200
        detail = rd.json()
        # walk any structure looking for a filename that has 05_codeudor and Maria and CODEUDOR
        blob = str(detail)
        assert "05_codeudor" in blob, "05_codeudor not found in folder detail"
        assert "Maria Prueba" in blob, "Maria Prueba subfolder not in detail"
        assert "CODEUDOR_" in blob, "CODEUDOR_ prefixed file not present"

        # find the exact path/name to delete — search archivos recursively
        target = None

        def walk(node):
            nonlocal target
            if isinstance(node, dict):
                # candidates
                nm = node.get("nombre") or node.get("name") or ""
                path = node.get("path") or node.get("ruta") or ""
                if "CODEUDOR_" in nm and "Maria Prueba" in (path + nm + str(node)):
                    target = node
                    return
                for v in node.values():
                    walk(v)
                    if target: return
            elif isinstance(node, list):
                for v in node:
                    walk(v)
                    if target: return

        walk(detail)
        # try delete — even without target metadata, we know it should exist
        # attempt delete using file name pattern
        # Try with node info first
        del_payload = None
        if target:
            del_payload = {
                "nombre": target.get("nombre") or target.get("name"),
                "path": target.get("path") or target.get("ruta") or "",
            }
        # fallback: minimal payload
        for payload in ([del_payload] if del_payload else []) + [
            {"nombre": "CODEUDOR_prueba_codeudor.pdf", "subcarpeta": "05_codeudor/Maria Prueba"},
            {"archivo": "05_codeudor/Maria Prueba/CODEUDOR_prueba_codeudor.pdf"},
        ]:
            rdel = requests.post(
                f"{BASE}/api/clientes/folders/{MELISA_FID}/delete-file",
                json=payload, timeout=30,
            )
            if rdel.status_code == 200 and rdel.json().get("ok"):
                print("deleted with payload:", payload)
                return
        # If not deleted, just print but don't fail — cleanup best-effort
        print("WARN: could not delete test file via delete-file endpoint; manual cleanup needed")


# ---------- Seguimiento estado PATCH ----------
class TestSeguimientoEstado:
    def test_patch_luis_fonseca_rechazo(self):
        r = requests.patch(
            f"{BASE}/api/seguimiento/estado",
            json={"cliente": "Luis Fonseca", "estado": "rechazo"},
            timeout=30,
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        assert r.json().get("ok") is True

        rg = requests.get(f"{BASE}/api/seguimiento/clientes", timeout=15)
        j = rg.json()
        clientes = j.get("clientes", j) if isinstance(j, dict) else j
        luis = next(
            (c for c in clientes if "fonseca" in (c.get("cliente", "") + c.get("nombre", "")).lower()),
            None,
        )
        assert luis is not None, "Luis Fonseca not in seguimiento list"
        assert luis.get("estado") == "rechazo", luis


# ---------- Nomenclatura ----------
class TestNomenclatura:
    def test_melisa_prefijos(self):
        r = requests.get(f"{BASE}/api/clientes/folders/{MELISA_FID}", timeout=30)
        assert r.status_code == 200
        blob = str(r.json())
        # Ensure at least a couple prefixed files exist
        found = sum(1 for pref in ("02_Liquidaciones", "03_Certificado_AFP", "04_CMF", "01_Cedula") if pref in blob)
        assert found >= 2, f"only {found} prefijos found in Melisa Rivera detail"
