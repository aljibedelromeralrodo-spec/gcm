"""
Backend tests for the Carpeta Clientes / correo/adjuntos fix (P0).
Focus: folders CRUD, files scan, upload, download, delete, merge, classification,
datos financieros, envio manual, send-email preview (no real send), send-missing-docs preview,
emails IMAP list, save-attachment, save-all-attachments job, UF actual, ajustes.
"""
import io
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"
TEST_FOLDER_NAME = "Juan Test Proc"  # pre-created folder with files
CREATED_FOLDER_ID = None


@pytest.fixture(scope="session")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


@pytest.fixture(scope="session")
def juan_folder(s):
    r = s.get(f"{API}/clientes/folders", timeout=30)
    assert r.status_code == 200, r.text
    folders = r.json().get("folders", [])
    for f in folders:
        if f.get("nombre") == TEST_FOLDER_NAME:
            return f
    pytest.skip(f"Folder '{TEST_FOLDER_NAME}' no encontrada — no se puede continuar")


# ---------- Basic: UF, list folders ----------
class TestBasics:
    def test_uf_actual_get(self, s):
        r = s.get(f"{API}/clientes/uf-actual", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "valor" in d or "valor_uf" in d

    def test_uf_actual_patch(self, s):
        r = s.patch(f"{API}/clientes/uf-actual", json={"valor": 40000}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        # Must reflect updated value
        v = d.get("valor") or d.get("valor_uf")
        assert float(v) == 40000.0

    def test_uf_actual_refresh(self, s):
        r = s.get(f"{API}/clientes/uf-actual?refresh=true", timeout=45)
        assert r.status_code == 200, r.text
        d = r.json()
        assert ("valor" in d) or ("valor_uf" in d)

    def test_list_folders(self, s):
        r = s.get(f"{API}/clientes/folders", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "folders" in d
        assert isinstance(d["folders"], list)
        # doc fields check
        if d["folders"]:
            f0 = d["folders"][0]
            assert "total_archivos" in f0
            assert "credit_request" in f0
            assert "is_ready_to_send" in f0
            assert "doc_categories" in f0["credit_request"]

    def test_ajustes(self, s):
        r = s.get(f"{API}/clientes/ajustes", timeout=45)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "folders" in d
        # con_archivos=True — each folder should have 'archivos'
        if d["folders"]:
            assert "archivos" in d["folders"][0]


# ---------- Folder CRUD and detail ----------
class TestFolderCRUD:
    def test_create_folder(self, s):
        global CREATED_FOLDER_ID
        name = f"TEST_Carpeta_{uuid.uuid4().hex[:6]}"
        r = s.post(f"{API}/clientes/folders", json={
            "nombre": name, "rut": "11.111.111-1",
            "codeudor_nombre": "Codeudor Test"
        }, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("nombre") == name
        assert "id" in d
        CREATED_FOLDER_ID = d["id"]

    def test_get_folder_detail(self, s, juan_folder):
        r = s.get(f"{API}/clientes/folders/{juan_folder['id']}", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["id"] == juan_folder["id"]
        assert "archivos" in d
        assert isinstance(d["archivos"], list)
        # Must have real files from disk
        assert len(d["archivos"]) >= 2
        a0 = d["archivos"][0]
        for k in ("nombre", "ruta", "subfolder", "tamano"):
            assert k in a0, f"campo {k} falta en archivo: {a0}"
        # Ensure cedula/liquidaciones subfolders present
        subfolders = {a["subfolder"] for a in d["archivos"]}
        assert any("01_cedula" in s or "cedula" in s for s in subfolders) or \
               any("cedula" in (a.get("nombre") or "").lower() for a in d["archivos"])


# ---------- Upload / delete / download ----------
def _tiny_pdf_bytes():
    # Minimal valid-ish PDF header + eof so pdf-tools accept as attempt
    return (b"%PDF-1.4\n1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
            b"2 0 obj<< /Type /Pages /Count 1 /Kids [3 0 R] >>endobj\n"
            b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] >>endobj\n"
            b"xref\n0 4\n0000000000 65535 f \n"
            b"trailer<< /Size 4 /Root 1 0 R >>\nstartxref\n0\n%%EOF\n")


class TestUploadDownloadDelete:
    uploaded_path = None

    def test_upload_file_auto_classify(self, s, juan_folder):
        fid = juan_folder["id"]
        filename = f"cedula_TEST_{uuid.uuid4().hex[:6]}.pdf"
        files = {"file": (filename, _tiny_pdf_bytes(), "application/pdf")}
        data = {"subfolder": ""}
        r = requests.post(f"{API}/clientes/folders/{fid}/upload-file",
                          files=files, data=data, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True
        saved_rel = d.get("saved") or ""
        assert saved_rel, "saved path missing"
        # Should classify to 01_cedula automatically
        assert "01_cedula" in saved_rel or "cedula" in saved_rel.lower()
        TestUploadDownloadDelete.uploaded_path = saved_rel

    def test_download_uploaded(self, s, juan_folder):
        assert TestUploadDownloadDelete.uploaded_path, "uploaded_path not set"
        fid = juan_folder["id"]
        rel = TestUploadDownloadDelete.uploaded_path
        r = requests.get(f"{API}/clientes/folders/{fid}/download/{rel}", timeout=30)
        assert r.status_code == 200, r.text
        assert "pdf" in r.headers.get("Content-Type", "").lower()
        cd = r.headers.get("Content-Disposition", "")
        assert "attachment" in cd

    def test_download_inline(self, s, juan_folder):
        assert TestUploadDownloadDelete.uploaded_path
        fid = juan_folder["id"]
        rel = TestUploadDownloadDelete.uploaded_path
        r = requests.get(f"{API}/clientes/folders/{fid}/download/{rel}?inline=true", timeout=30)
        assert r.status_code == 200
        assert "inline" in r.headers.get("Content-Disposition", "")

    def test_download_path_traversal(self, s, juan_folder):
        fid = juan_folder["id"]
        r = requests.get(f"{API}/clientes/folders/{fid}/download/../../etc/passwd", timeout=30)
        # Should be 400 (invalid). 404 also acceptable but 400 preferred per spec.
        assert r.status_code in (400, 404), r.text

    def test_download_all_zip(self, s, juan_folder):
        fid = juan_folder["id"]
        r = requests.get(f"{API}/clientes/folders/{fid}/download-all", timeout=60)
        assert r.status_code == 200, r.text
        ct = r.headers.get("Content-Type", "").lower()
        assert "zip" in ct or "octet-stream" in ct
        # ZIP magic
        assert r.content[:2] == b"PK", "Contenido no parece un ZIP"

    def test_delete_file(self, s, juan_folder):
        assert TestUploadDownloadDelete.uploaded_path
        fid = juan_folder["id"]
        rel = TestUploadDownloadDelete.uploaded_path
        r = s.post(f"{API}/clientes/folders/{fid}/delete-file",
                   json={"file_path": rel}, timeout=30)
        assert r.status_code == 200, r.text
        # Verify gone
        r2 = requests.get(f"{API}/clientes/folders/{fid}/download/{rel}", timeout=15)
        assert r2.status_code == 404


# ---------- Merges ----------
class TestMerges:
    def test_merge_protocol(self, s, juan_folder):
        fid = juan_folder["id"]
        r = s.post(f"{API}/clientes/folders/{fid}/merge-protocol",
                   json={"include_extras": True}, timeout=90)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("merged_file"), f"merged_file vacío: {d}"
        assert "COMBINADO_PROTOCOLO" in d["merged_file"]
        assert isinstance(d.get("files_used", []), list)

    def test_merge_pdfs_arbitrary(self, s, juan_folder):
        fid = juan_folder["id"]
        # Get list of pdf rutas
        detail = s.get(f"{API}/clientes/folders/{fid}", timeout=30).json()
        rutas = [a["ruta"] for a in detail["archivos"]
                 if a["nombre"].lower().endswith(".pdf") and "COMBINADO" not in a["nombre"]]
        if len(rutas) < 2:
            pytest.skip("no suficientes PDFs para merge")
        r = s.post(f"{API}/clientes/folders/{fid}/merge-pdfs",
                   json={"files": rutas[:3]}, timeout=60)
        assert r.status_code == 200, r.text
        assert r.json().get("merged_file")


# ---------- Clasificacion / datos financieros / envio manual ----------
class TestClasificacion:
    def test_patch_clasificacion(self, s, juan_folder):
        fid = juan_folder["id"]
        r = s.patch(f"{API}/clientes/folders/{fid}/clasificacion", json={
            "client_type": "dependiente",
            "subsidy_tipo": "ds01",
            "is_request": True,
            "codeudor_has": True,
            "codeudor_name": "Codeudor X"
        }, timeout=30)
        assert r.status_code == 200, r.text
        # verify persistence
        det = s.get(f"{API}/clientes/folders/{fid}", timeout=30).json()
        cr = det.get("credit_request", {})
        assert cr.get("client_type") == "dependiente"
        # subsidy is stored nested as subsidy.tipo
        subsidy_tipo = cr.get("subsidy_tipo") or (cr.get("subsidy") or {}).get("tipo")
        assert subsidy_tipo == "ds01", f"subsidy: {cr}"
        assert cr.get("manual_override") is True

    def test_reset_clasificacion(self, s, juan_folder):
        fid = juan_folder["id"]
        r = s.patch(f"{API}/clientes/folders/{fid}/clasificacion",
                    json={"reset": True}, timeout=30)
        assert r.status_code == 200, r.text
        det = s.get(f"{API}/clientes/folders/{fid}", timeout=30).json()
        cr = det.get("credit_request", {})
        assert cr.get("manual_override") in (False, None)


class TestDatosFinancieros:
    def test_get_and_patch(self, s, juan_folder):
        fid = juan_folder["id"]
        r = s.get(f"{API}/clientes/folders/{fid}/datos-financieros", timeout=30)
        assert r.status_code == 200, r.text
        assert "datos_financieros" in r.json() or isinstance(r.json(), dict)
        r2 = s.patch(f"{API}/clientes/folders/{fid}/datos-financieros",
                     json={"renta_liquida": 1500000, "ahorro": 5000000}, timeout=30)
        assert r2.status_code == 200, r2.text
        # verify
        r3 = s.get(f"{API}/clientes/folders/{fid}/datos-financieros", timeout=30)
        df = r3.json().get("datos_financieros") or r3.json()
        assert float(df.get("renta_liquida", 0)) == 1500000.0


class TestEnvioManual:
    def test_envio_manual(self, s, juan_folder):
        fid = juan_folder["id"]
        r = s.patch(f"{API}/clientes/folders/{fid}/envio-manual",
                    json={"enviado": True}, timeout=30)
        assert r.status_code == 200, r.text


# ---------- Send email preview (NO real send) ----------
class TestSendEmailPreview:
    def test_send_email_preview(self, s, juan_folder):
        fid = juan_folder["id"]
        r = s.post(f"{API}/clientes/folders/{fid}/send-email", json={
            "to_addr": "test@example.com",
            "confirm": False,
            "include_merged": True
        }, timeout=90)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("to", "subject", "body", "attachments", "sender"):
            assert k in d, f"campo {k} falta"
        assert d["to"] == "test@example.com"
        assert isinstance(d["attachments"], list)

    def test_send_email_invalid_addr(self, s, juan_folder):
        fid = juan_folder["id"]
        r = s.post(f"{API}/clientes/folders/{fid}/send-email",
                   json={"to_addr": "notanemail", "confirm": False}, timeout=30)
        assert r.status_code == 400

    def test_send_missing_docs_preview(self, s, juan_folder):
        fid = juan_folder["id"]
        r = s.post(f"{API}/clientes/folders/{fid}/send-missing-docs",
                   json={"to_addr": "test@example.com", "confirm": False}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("to", "subject", "missing", "body"):
            assert k in d


# ---------- IMAP: emails list + save-attachment ----------
@pytest.mark.slow
class TestIMAP:
    emails = None

    def test_emails_list(self, s):
        r = s.get(f"{API}/clientes/emails?max_results=10", timeout=90)
        assert r.status_code == 200, r.text[:500]
        d = r.json()
        assert "emails" in d
        emails = d["emails"]
        TestIMAP.emails = emails
        # basic shape (not strict on count due to real inbox)
        if emails:
            e0 = emails[0]
            for k in ("id", "from", "subject", "attachments"):
                assert k in e0, f"campo {k} falta"
            assert "|" in e0["id"], "id should be 'rol|uid'"
            assert isinstance(e0["attachments"], list)

    def test_save_attachment(self, s, juan_folder):
        if not TestIMAP.emails:
            pytest.skip("no emails para probar save-attachment")
        candidates = [e for e in TestIMAP.emails if e.get("attachments")]
        if not candidates:
            pytest.skip("no hay correos con adjuntos")
        e = candidates[0]
        fname = e["attachments"][0].get("filename")
        r = s.post(f"{API}/clientes/save-attachment", json={
            "email_id": e["id"], "filename": fname,
            "folder_id": juan_folder["id"]
        }, timeout=90)
        # 200 OK or 404 if attachment fetch missed (real inbox)
        assert r.status_code in (200, 404), r.text[:500]
        if r.status_code == 200:
            d = r.json()
            assert d.get("ok") is True
            assert isinstance(d.get("saved"), list)


@pytest.mark.slow
class TestSaveAllJob:
    def test_save_all_polling(self, s, juan_folder):
        r = s.post(f"{API}/clientes/save-all-attachments", json={
            "person_name": "Kevin Macaya",
            "folder_id": juan_folder["id"]
        }, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("status") == "running"
        job_id = d["job_id"]
        # Poll up to ~120s
        final = None
        for _ in range(30):
            time.sleep(5)
            r2 = s.get(f"{API}/clientes/save-all-attachments/{job_id}", timeout=30)
            assert r2.status_code == 200
            final = r2.json()
            if final.get("status") in ("done", "error"):
                break
        assert final is not None
        assert final.get("status") in ("done", "error"), f"job no terminó: {final}"
        if final["status"] == "done":
            assert "total_found" in final
            assert "total_saved" in final
