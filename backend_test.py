#!/usr/bin/env python3
"""
Backend test suite for Central Mutuos - Autocorreo flow
Tests the new Autocorreo module that handles PDF processing:
- Receives simulations, keeps ONLY page 1 (removes page 2+), archives by client
"""
import requests
import io
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from pypdf import PdfReader

# Backend URL from environment
BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://risk-assess-17.preview.emergentagent.com")
API_BASE = f"{BACKEND_URL}/api"

# Test results tracking
tests_passed = 0
tests_failed = 0
test_results = []


def log_test(name, passed, details=""):
    global tests_passed, tests_failed
    if passed:
        tests_passed += 1
        status = "✅ PASS"
    else:
        tests_failed += 1
        status = "❌ FAIL"
    result = f"{status}: {name}"
    if details:
        result += f" - {details}"
    test_results.append(result)
    print(result)


def generate_2page_pdf():
    """Generate a 2-page PDF for testing.
    Page 1: SIMULACION DE CREDITO - Dividendo estimado
    Page 2: Gastos operacionales y plazos
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    
    # Page 1 - Simulation
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, h - 3 * cm, "SIMULACION DE CREDITO")
    c.setFont("Helvetica", 12)
    c.drawString(2 * cm, h - 4 * cm, "Dividendo estimado: $450.000")
    c.drawString(2 * cm, h - 5 * cm, "Monto credito: 3000 UF")
    c.drawString(2 * cm, h - 6 * cm, "Plazo: 20 años")
    c.showPage()
    
    # Page 2 - Operational costs (should be removed)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(2 * cm, h - 3 * cm, "Gastos operacionales y plazos")
    c.setFont("Helvetica", 11)
    c.drawString(2 * cm, h - 4 * cm, "Gastos notariales: $150.000")
    c.drawString(2 * cm, h - 5 * cm, "Gastos de tasacion: $80.000")
    c.drawString(2 * cm, h - 6 * cm, "Otros gastos: $50.000")
    c.showPage()
    
    c.save()
    buf.seek(0)
    return buf.getvalue()


def count_pdf_pages(pdf_bytes):
    """Count pages in a PDF"""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        return len(reader.pages)
    except Exception as e:
        print(f"Error counting PDF pages: {e}")
        return -1


def test_autocorreo_status():
    """Test 1: GET /api/autocorreo/status"""
    try:
        resp = requests.get(f"{API_BASE}/autocorreo/status", timeout=10)
        if resp.status_code != 200:
            log_test("GET /api/autocorreo/status", False, f"Status {resp.status_code}")
            return False
        
        data = resp.json()
        required_fields = ["enabled", "periodic_enabled", "cutoff_iso", "destination", 
                          "sent", "failed", "total", "recent"]
        missing = [f for f in required_fields if f not in data]
        if missing:
            log_test("GET /api/autocorreo/status", False, f"Missing fields: {missing}")
            return False
        
        # Destination must be an email, not empty
        if not data.get("destination") or "@" not in data.get("destination", ""):
            log_test("GET /api/autocorreo/status", False, 
                    f"destination must be a valid email, got: {data.get('destination')}")
            return False
        
        log_test("GET /api/autocorreo/status", True, 
                f"enabled={data['enabled']}, destination={data['destination']}")
        return True
    except Exception as e:
        log_test("GET /api/autocorreo/status", False, str(e))
        return False


def test_autocorreo_toggle():
    """Test 2: POST /api/autocorreo/toggle"""
    try:
        # Enable
        resp = requests.post(f"{API_BASE}/autocorreo/toggle", 
                           json={"enabled": True}, timeout=10)
        if resp.status_code != 200:
            log_test("POST /api/autocorreo/toggle (enable)", False, f"Status {resp.status_code}")
            return False
        
        data = resp.json()
        if not data.get("enabled"):
            log_test("POST /api/autocorreo/toggle (enable)", False, "enabled should be true")
            return False
        
        # Verify status shows enabled=true
        status_resp = requests.get(f"{API_BASE}/autocorreo/status", timeout=10)
        if status_resp.status_code != 200 or not status_resp.json().get("enabled"):
            log_test("POST /api/autocorreo/toggle (verify)", False, "Status doesn't show enabled=true")
            return False
        
        # Disable
        resp = requests.post(f"{API_BASE}/autocorreo/toggle", 
                           json={"enabled": False}, timeout=10)
        if resp.status_code != 200:
            log_test("POST /api/autocorreo/toggle (disable)", False, f"Status {resp.status_code}")
            return False
        
        data = resp.json()
        if data.get("enabled"):
            log_test("POST /api/autocorreo/toggle (disable)", False, "enabled should be false")
            return False
        
        log_test("POST /api/autocorreo/toggle", True, "Enable/disable works correctly")
        return True
    except Exception as e:
        log_test("POST /api/autocorreo/toggle", False, str(e))
        return False


def test_autocorreo_periodic():
    """Test 3: POST /api/autocorreo/periodic"""
    try:
        # Enable periodic
        resp = requests.post(f"{API_BASE}/autocorreo/periodic", 
                           json={"enabled": True}, timeout=10)
        if resp.status_code != 200:
            log_test("POST /api/autocorreo/periodic (enable)", False, f"Status {resp.status_code}")
            return False
        
        data = resp.json()
        if not data.get("periodic_enabled"):
            log_test("POST /api/autocorreo/periodic (enable)", False, "periodic_enabled should be true")
            return False
        
        # Disable periodic
        resp = requests.post(f"{API_BASE}/autocorreo/periodic", 
                           json={"enabled": False}, timeout=10)
        if resp.status_code != 200:
            log_test("POST /api/autocorreo/periodic (disable)", False, f"Status {resp.status_code}")
            return False
        
        data = resp.json()
        if data.get("periodic_enabled"):
            log_test("POST /api/autocorreo/periodic (disable)", False, "periodic_enabled should be false")
            return False
        
        log_test("POST /api/autocorreo/periodic", True, "Periodic enable/disable works")
        return True
    except Exception as e:
        log_test("POST /api/autocorreo/periodic", False, str(e))
        return False


def test_autocorreo_cutoff():
    """Test 4: POST /api/autocorreo/cutoff/now and /api/autocorreo/cutoff/clear"""
    try:
        # Set cutoff to now
        resp = requests.post(f"{API_BASE}/autocorreo/cutoff/now", timeout=10)
        if resp.status_code != 200:
            log_test("POST /api/autocorreo/cutoff/now", False, f"Status {resp.status_code}")
            return False
        
        data = resp.json()
        if not data.get("cutoff_iso"):
            log_test("POST /api/autocorreo/cutoff/now", False, "cutoff_iso should not be null")
            return False
        
        # Verify status shows cutoff_iso
        status_resp = requests.get(f"{API_BASE}/autocorreo/status", timeout=10)
        if status_resp.status_code != 200 or not status_resp.json().get("cutoff_iso"):
            log_test("POST /api/autocorreo/cutoff/now (verify)", False, 
                    "Status doesn't show cutoff_iso")
            return False
        
        # Clear cutoff
        resp = requests.post(f"{API_BASE}/autocorreo/cutoff/clear", timeout=10)
        if resp.status_code != 200:
            log_test("POST /api/autocorreo/cutoff/clear", False, f"Status {resp.status_code}")
            return False
        
        data = resp.json()
        if data.get("cutoff_iso") is not None:
            log_test("POST /api/autocorreo/cutoff/clear", False, "cutoff_iso should be null")
            return False
        
        log_test("POST /api/autocorreo/cutoff", True, "Cutoff set/clear works correctly")
        return True
    except Exception as e:
        log_test("POST /api/autocorreo/cutoff", False, str(e))
        return False


def test_autocorreo_mailboxes():
    """Test 5: GET /api/autocorreo/mailboxes?probe=true"""
    try:
        resp = requests.get(f"{API_BASE}/autocorreo/mailboxes?probe=true", timeout=30)
        if resp.status_code != 200:
            log_test("GET /api/autocorreo/mailboxes?probe=true", False, f"Status {resp.status_code}")
            return False
        
        data = resp.json()
        if "accounts" not in data:
            log_test("GET /api/autocorreo/mailboxes?probe=true", False, "Missing 'accounts' field")
            return False
        
        accounts = data["accounts"]
        if not accounts or len(accounts) < 1:
            log_test("GET /api/autocorreo/mailboxes?probe=true", False, 
                    "Should have at least 1 account")
            return False
        
        # Check each account has required fields
        for acc in accounts:
            required = ["email", "role", "slot", "auth_method", "auth_live"]
            missing = [f for f in required if f not in acc]
            if missing:
                log_test("GET /api/autocorreo/mailboxes?probe=true", False, 
                        f"Account missing fields: {missing}")
                return False
        
        log_test("GET /api/autocorreo/mailboxes?probe=true", True, 
                f"Found {len(accounts)} account(s)")
        return True
    except Exception as e:
        log_test("GET /api/autocorreo/mailboxes?probe=true", False, str(e))
        return False


def test_autocorreo_manual_archive():
    """Test 6: POST /api/autocorreo/manual-archive - KEY TEST for PDF adjustment"""
    try:
        # Generate 2-page PDF
        pdf_bytes = generate_2page_pdf()
        original_pages = count_pdf_pages(pdf_bytes)
        
        if original_pages != 2:
            log_test("POST /api/autocorreo/manual-archive (PDF generation)", False, 
                    f"Generated PDF should have 2 pages, got {original_pages}")
            return False
        
        # Upload via multipart/form-data
        files = {
            'files': ('simulacion_test.pdf', pdf_bytes, 'application/pdf')
        }
        data = {
            'cliente': 'Cliente Prueba QA'
        }
        
        resp = requests.post(f"{API_BASE}/autocorreo/manual-archive", 
                           files=files, data=data, timeout=15)
        
        if resp.status_code != 200:
            log_test("POST /api/autocorreo/manual-archive", False, 
                    f"Status {resp.status_code}, response: {resp.text}")
            return False
        
        result = resp.json()
        
        # Verify response structure
        required_fields = ["folder", "cliente", "saved", "errors"]
        missing = [f for f in required_fields if f not in result]
        if missing:
            log_test("POST /api/autocorreo/manual-archive", False, 
                    f"Missing fields: {missing}")
            return False
        
        # Verify saved array has the adjusted PDF
        saved = result.get("saved", [])
        if not saved:
            log_test("POST /api/autocorreo/manual-archive", False, 
                    "No files in 'saved' array")
            return False
        
        # Find the simulacion_ajustada entry
        adjusted = None
        for s in saved:
            if s.get("type") == "simulacion_ajustada":
                adjusted = s
                break
        
        if not adjusted:
            log_test("POST /api/autocorreo/manual-archive", False, 
                    f"No simulacion_ajustada found in saved: {saved}")
            return False
        
        # Verify PDF adjustment metadata
        if adjusted.get("pages_original") != 2:
            log_test("POST /api/autocorreo/manual-archive", False, 
                    f"pages_original should be 2, got {adjusted.get('pages_original')}")
            return False
        
        if adjusted.get("pages_removed") != 1:
            log_test("POST /api/autocorreo/manual-archive", False, 
                    f"pages_removed should be 1, got {adjusted.get('pages_removed')}")
            return False
        
        # Verify errors is empty
        if result.get("errors"):
            log_test("POST /api/autocorreo/manual-archive", False, 
                    f"Unexpected errors: {result.get('errors')}")
            return False
        
        log_test("POST /api/autocorreo/manual-archive", True, 
                f"PDF adjusted correctly: {adjusted['name']}, original=2 pages, removed=1")
        
        # Store for next test
        global test_cliente, test_filename
        test_cliente = result["folder"]
        test_filename = adjusted["name"]
        
        return True
    except Exception as e:
        log_test("POST /api/autocorreo/manual-archive", False, str(e))
        return False


def test_autocorreo_archive_list():
    """Test 7: GET /api/autocorreo/archive"""
    try:
        resp = requests.get(f"{API_BASE}/autocorreo/archive", timeout=10)
        if resp.status_code != 200:
            log_test("GET /api/autocorreo/archive", False, f"Status {resp.status_code}")
            return False
        
        data = resp.json()
        if "folders" not in data:
            log_test("GET /api/autocorreo/archive", False, "Missing 'folders' field")
            return False
        
        folders = data["folders"]
        
        # Find our test folder
        test_folder = None
        for f in folders:
            if "Cliente_Prueba_QA" in f.get("cliente", ""):
                test_folder = f
                break
        
        if not test_folder:
            log_test("GET /api/autocorreo/archive", False, 
                    "Test folder 'Cliente_Prueba_QA' not found in archive")
            return False
        
        # Check for _ajustada.pdf file
        files = test_folder.get("files", [])
        adjusted_file = None
        for file in files:
            if "_ajustada.pdf" in file.get("name", ""):
                adjusted_file = file
                break
        
        if not adjusted_file:
            log_test("GET /api/autocorreo/archive", False, 
                    "No _ajustada.pdf file found in test folder")
            return False
        
        log_test("GET /api/autocorreo/archive", True, 
                f"Found test folder with {len(files)} file(s)")
        return True
    except Exception as e:
        log_test("GET /api/autocorreo/archive", False, str(e))
        return False


def test_autocorreo_archive_download():
    """Test 8: GET /api/autocorreo/archive/{cliente}/{filename}"""
    try:
        # Use the cliente and filename from manual-archive test
        if not test_cliente or not test_filename:
            log_test("GET /api/autocorreo/archive/{cliente}/{filename}", False, 
                    "No test file available from previous test")
            return False
        
        url = f"{API_BASE}/autocorreo/archive/{test_cliente}/{test_filename}"
        resp = requests.get(url, timeout=10)
        
        if resp.status_code != 200:
            log_test("GET /api/autocorreo/archive/{cliente}/{filename}", False, 
                    f"Status {resp.status_code}")
            return False
        
        # Verify content-type
        content_type = resp.headers.get("content-type", "")
        if "application/pdf" not in content_type:
            log_test("GET /api/autocorreo/archive/{cliente}/{filename}", False, 
                    f"Wrong content-type: {content_type}")
            return False
        
        # Verify PDF has only 1 page
        pdf_bytes = resp.content
        page_count = count_pdf_pages(pdf_bytes)
        
        if page_count != 1:
            log_test("GET /api/autocorreo/archive/{cliente}/{filename}", False, 
                    f"Downloaded PDF should have 1 page, got {page_count}")
            return False
        
        log_test("GET /api/autocorreo/archive/{cliente}/{filename}", True, 
                f"Downloaded PDF has 1 page (correctly adjusted)")
        return True
    except Exception as e:
        log_test("GET /api/autocorreo/archive/{cliente}/{filename}", False, str(e))
        return False


def test_autocorreo_run():
    """Test 9: POST /api/autocorreo/run - may take time (90s timeout)"""
    try:
        resp = requests.post(f"{API_BASE}/autocorreo/run", timeout=90)
        
        if resp.status_code != 200:
            log_test("POST /api/autocorreo/run", False, 
                    f"Status {resp.status_code}, response: {resp.text}")
            return False
        
        data = resp.json()
        
        # Verify response structure
        required_fields = ["processed", "sent", "errors"]
        missing = [f for f in required_fields if f not in data]
        if missing:
            log_test("POST /api/autocorreo/run", False, f"Missing fields: {missing}")
            return False
        
        # processed=0 is valid if no emails from mesa
        processed = data.get("processed", 0)
        sent = data.get("sent", 0)
        errors = data.get("errors", [])
        
        log_test("POST /api/autocorreo/run", True, 
                f"processed={processed}, sent={sent}, errors={len(errors)}")
        return True
    except Exception as e:
        log_test("POST /api/autocorreo/run", False, str(e))
        return False


def test_regression_email_status():
    """Regression test: GET /api/central/email-status should still work"""
    try:
        resp = requests.get(f"{API_BASE}/central/email-status", timeout=10)
        if resp.status_code != 200:
            log_test("Regression: GET /api/central/email-status", False, 
                    f"Status {resp.status_code}")
            return False
        
        data = resp.json()
        if not data.get("connected"):
            log_test("Regression: GET /api/central/email-status", False, 
                    "connected should be true")
            return False
        
        log_test("Regression: GET /api/central/email-status", True, 
                f"connected={data['connected']}")
        return True
    except Exception as e:
        log_test("Regression: GET /api/central/email-status", False, str(e))
        return False


# Global variables for test data sharing
test_cliente = None
test_filename = None


def main():
    print("=" * 80)
    print("BACKEND TEST SUITE - Central Mutuos Autocorreo Flow")
    print("=" * 80)
    print(f"Backend URL: {API_BASE}")
    print()
    
    # Run all tests in order
    test_autocorreo_status()
    test_autocorreo_toggle()
    test_autocorreo_periodic()
    test_autocorreo_cutoff()
    test_autocorreo_mailboxes()
    test_autocorreo_manual_archive()  # KEY TEST
    test_autocorreo_archive_list()
    test_autocorreo_archive_download()
    test_autocorreo_run()
    test_regression_email_status()
    
    # Summary
    print()
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    total = tests_passed + tests_failed
    print(f"Total tests: {total}")
    print(f"Passed: {tests_passed}")
    print(f"Failed: {tests_failed}")
    print(f"Success rate: {tests_passed/total*100:.1f}%")
    print()
    
    if tests_failed > 0:
        print("FAILED TESTS:")
        for result in test_results:
            if "❌" in result:
                print(f"  {result}")
        print()
    
    return tests_failed == 0


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
