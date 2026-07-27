#!/usr/bin/env python3
"""
Backend testing for Central Mutuos - Nuevas credenciales y campos indispensables
Tests per review request specifications
"""
import requests
import time
import io
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# Backend URL from frontend/.env
BASE_URL = "https://risk-assess-17.preview.emergentagent.com/api"

def test_nuevas_credenciales():
    """A) NUEVAS CREDENCIALES (crítico)"""
    print("\n" + "="*80)
    print("A) TESTING NUEVAS CREDENCIALES")
    print("="*80)
    
    results = []
    
    # Test 1: Login with administrador/141617575
    print("\n1. POST /api/auth/login with administrador/141617575")
    resp = requests.post(f"{BASE_URL}/auth/login", json={"rut": "administrador", "password": "141617575"}, timeout=10)
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   Response: {data}")
        if data.get("rol") == "admin":
            print("   ✅ PASS: Returns 200 with rol=admin")
            results.append(("Login administrador/141617575", True, ""))
        else:
            print(f"   ❌ FAIL: rol={data.get('rol')}, expected 'admin'")
            results.append(("Login administrador/141617575", False, f"rol={data.get('rol')}"))
    else:
        print(f"   ❌ FAIL: Expected 200, got {resp.status_code}")
        results.append(("Login administrador/141617575", False, f"Status {resp.status_code}"))
    
    # Test 2: Case-insensitive login ADMINISTRADOR/141617575
    print("\n2. POST /api/auth/login with ADMINISTRADOR/141617575 (case-insensitive)")
    resp = requests.post(f"{BASE_URL}/auth/login", json={"rut": "ADMINISTRADOR", "password": "141617575"}, timeout=10)
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   ✅ PASS: Case-insensitive login works, rol={data.get('rol')}")
        results.append(("Login ADMINISTRADOR (uppercase)", True, ""))
    else:
        print(f"   ❌ FAIL: Expected 200, got {resp.status_code}")
        results.append(("Login ADMINISTRADOR (uppercase)", False, f"Status {resp.status_code}"))
    
    # Test 3: Backup credential admin/0586 still active
    print("\n3. POST /api/auth/login with admin/0586 (backup credential)")
    resp = requests.post(f"{BASE_URL}/auth/login", json={"rut": "admin", "password": "0586"}, timeout=10)
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   ✅ PASS: Backup credential still active, rol={data.get('rol')}")
        results.append(("Login admin/0586 (backup)", True, ""))
    else:
        print(f"   ❌ FAIL: Expected 200, got {resp.status_code}")
        results.append(("Login admin/0586 (backup)", False, f"Status {resp.status_code}"))
    
    # Test 4: Wrong password should return 401
    print("\n4. POST /api/auth/login with administrador/mala (wrong password)")
    resp = requests.post(f"{BASE_URL}/auth/login", json={"rut": "administrador", "password": "mala"}, timeout=10)
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 401:
        print("   ✅ PASS: Returns 401 for wrong password")
        results.append(("Login wrong password", True, ""))
    else:
        print(f"   ❌ FAIL: Expected 401, got {resp.status_code}")
        results.append(("Login wrong password", False, f"Status {resp.status_code}"))
    
    # Test 5: DELETE /api/admin/users/administrador should fail with 400
    print("\n5. DELETE /api/admin/users/administrador (should be protected)")
    resp = requests.delete(f"{BASE_URL}/admin/users/administrador", timeout=10)
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 400:
        data = resp.json()
        print(f"   Response: {data}")
        print("   ✅ PASS: Protected user cannot be deleted (400)")
        results.append(("Delete administrador user", True, ""))
    elif resp.status_code == 200:
        print(f"   ❌ ISSUE: Returns 200 - admin user should be protected from deletion!")
        results.append(("Delete administrador user", False, "User not protected - returns 200"))
    else:
        print(f"   ⚠️  Got {resp.status_code}, expected 400")
        results.append(("Delete administrador user", False, f"Status {resp.status_code}"))
    
    return results


def get_or_create_queue_item():
    """Get a queue item with status 'clasificado', or create one if needed"""
    print("\n" + "="*80)
    print("GETTING QUEUE ITEM FOR TESTING")
    print("="*80)
    
    # First, check if queue has items
    print("\nGET /api/procesamiento/queue")
    resp = requests.get(f"{BASE_URL}/procesamiento/queue", timeout=10)
    print(f"Status: {resp.status_code}")
    
    if resp.status_code != 200:
        print(f"❌ Failed to get queue: {resp.status_code}")
        return None
    
    data = resp.json()
    items = data.get("rows", []) if isinstance(data, dict) else data
    print(f"Found {len(items)} items in queue")
    
    # If queue is empty, ingest emails
    if len(items) == 0:
        print("\nQueue is empty, ingesting emails...")
        print("POST /api/procesamiento/ingest-from-inbox?max_emails=6 (timeout 120s)")
        try:
            resp = requests.post(f"{BASE_URL}/procesamiento/ingest-from-inbox?max_emails=6", timeout=120)
            print(f"Status: {resp.status_code}")
            if resp.status_code in [200, 502]:
                print("Waiting 30s for processing...")
                time.sleep(30)
                # Retry getting queue
                resp = requests.get(f"{BASE_URL}/procesamiento/queue", timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("rows", []) if isinstance(data, dict) else data
                    print(f"After ingest: {len(items)} items in queue")
        except requests.exceptions.Timeout:
            print("⚠️  Ingest timed out (expected for IMAP operations), waiting 30s...")
            time.sleep(30)
            resp = requests.get(f"{BASE_URL}/procesamiento/queue", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("rows", []) if isinstance(data, dict) else data
                print(f"After ingest: {len(items)} items in queue")
    
    if len(items) == 0:
        print("❌ No items in queue after ingest")
        return None
    
    # Find a 'clasificado' item, or process a 'pendiente' one
    clasificado = [i for i in items if i.get("status") == "clasificado"]
    if clasificado:
        item = clasificado[0]
        print(f"\n✅ Found clasificado item: {item['id']}")
        return item
    
    # If no clasificado, find pendiente and process it
    pendiente = [i for i in items if i.get("status") == "pendiente"]
    if pendiente:
        print("\nNo clasificado items, processing pendiente...")
        print("POST /api/procesamiento/process-pending?limit=1 (timeout 120s)")
        try:
            resp = requests.post(f"{BASE_URL}/procesamiento/process-pending?limit=1", timeout=120)
            print(f"Status: {resp.status_code}")
            if resp.status_code in [200, 502]:
                time.sleep(10)
                # Get the processed item
                item_id = pendiente[0]["id"]
                resp = requests.get(f"{BASE_URL}/procesamiento/queue/{item_id}", timeout=10)
                if resp.status_code == 200:
                    item = resp.json()
                    print(f"✅ Processed item: {item['id']}, status={item.get('status')}")
                    return item
        except requests.exceptions.Timeout:
            print("⚠️  Process-pending timed out (expected for OCR+AI), waiting 10s...")
            time.sleep(10)
            item_id = pendiente[0]["id"]
            resp = requests.get(f"{BASE_URL}/procesamiento/queue/{item_id}", timeout=10)
            if resp.status_code == 200:
                item = resp.json()
                print(f"✅ Processed item: {item['id']}, status={item.get('status')}")
                return item
    
    # Just return the first item
    print(f"\n⚠️  Using first available item: {items[0]['id']}, status={items[0].get('status')}")
    return items[0]


def test_validacion_campos_indispensables(item_id):
    """B) VALIDACIÓN DE CAMPOS INDISPENSABLES + AVISO DE FALTANTES"""
    print("\n" + "="*80)
    print("B) TESTING VALIDACIÓN DE CAMPOS INDISPENSABLES")
    print("="*80)
    
    results = []
    
    # Test 1: GET /api/procesamiento/queue/{id}/validate
    print(f"\n1. GET /api/procesamiento/queue/{item_id}/validate")
    resp = requests.get(f"{BASE_URL}/procesamiento/queue/{item_id}/validate", timeout=10)
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   Response: {data}")
        if "listo" in data and "campos_faltantes" in data and "docs_faltantes" in data:
            print(f"   ✅ PASS: Returns correct structure")
            print(f"      listo={data['listo']}, campos_faltantes={data['campos_faltantes']}")
            results.append(("Validate endpoint structure", True, ""))
            if not data["listo"] and len(data["campos_faltantes"]) > 0:
                print(f"   ✅ Expected: listo=false with faltantes (normal state)")
        else:
            print(f"   ❌ FAIL: Missing required fields in response")
            results.append(("Validate endpoint structure", False, "Missing fields"))
    else:
        print(f"   ❌ FAIL: Expected 200, got {resp.status_code}")
        results.append(("Validate endpoint structure", False, f"Status {resp.status_code}"))
    
    # Test 2: POST /api/procesamiento/queue/{id}/enviar-autocorreo with empty payload (should send AVISO)
    print(f"\n2. POST /api/procesamiento/queue/{item_id}/enviar-autocorreo with empty payload")
    print("   (Should send AVISO email if data is missing, NOT send gestión)")
    resp = requests.post(f"{BASE_URL}/procesamiento/queue/{item_id}/enviar-autocorreo", json={}, timeout=15)
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   Response: {data}")
        if data.get("success") is False and data.get("aviso_enviado") is True:
            print(f"   ✅ PASS: Returns success=false, aviso_enviado=true")
            print(f"      campos_faltantes={data.get('campos_faltantes')}")
            print(f"      docs_faltantes={data.get('docs_faltantes')}")
            results.append(("Enviar-autocorreo AVISO", True, ""))
        elif data.get("success") is True:
            print(f"   ⚠️  WARNING: success=true - gestión was sent (should only send AVISO if data missing)")
            results.append(("Enviar-autocorreo AVISO", False, "Sent gestión instead of AVISO"))
        else:
            print(f"   ❌ FAIL: Unexpected response structure")
            results.append(("Enviar-autocorreo AVISO", False, "Unexpected structure"))
    else:
        print(f"   ❌ FAIL: Expected 200, got {resp.status_code}")
        results.append(("Enviar-autocorreo AVISO", False, f"Status {resp.status_code}"))
    
    # Test 3: POST /api/procesamiento/queue/{id}/correct with complete data
    print(f"\n3. POST /api/procesamiento/queue/{item_id}/correct with complete campos data")
    correct_payload = {
        "cliente": "María González Pérez",
        "rut": "11.111.111-1",
        "con_subsidio": True,
        "proyecto_inmobiliario": "Edificio Vista Hermosa",
        "fecha_entrega": "inmediata",
        "monto_credito_uf": 2000,
        "monto_subsidio_uf": 500,
        "pie_uf": 100,
        "ahorro_uf": 50,
        "monto_credito_solicitar_uf": 2000
    }
    resp = requests.post(f"{BASE_URL}/procesamiento/queue/{item_id}/correct", json=correct_payload, timeout=10)
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   Response: {data}")
        if data.get("ok") is True:
            print(f"   ✅ PASS: Correction applied successfully")
            print(f"      listo={data.get('listo')}, campos_faltantes={data.get('campos_faltantes')}")
            if len(data.get("campos_faltantes", [])) == 0:
                print(f"   ✅ campos_faltantes is empty (as expected)")
            results.append(("Correct with complete data", True, ""))
        else:
            print(f"   ❌ FAIL: ok is not True")
            results.append(("Correct with complete data", False, "ok != True"))
    else:
        print(f"   ❌ FAIL: Expected 200, got {resp.status_code}")
        results.append(("Correct with complete data", False, f"Status {resp.status_code}"))
    
    # Test 4: GET /api/procesamiento/queue/{id} to verify campos were saved
    print(f"\n4. GET /api/procesamiento/queue/{item_id} to verify campos")
    resp = requests.get(f"{BASE_URL}/procesamiento/queue/{item_id}", timeout=10)
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        campos = data.get("campos", {})
        print(f"   campos: {campos}")
        checks = [
            ("fecha_entrega", "inmediata"),
            ("pie_uf", 100),
            ("ahorro_uf", 50),
            ("monto_credito_uf", 2000),
            ("monto_subsidio_uf", 500),
        ]
        all_match = True
        for key, expected in checks:
            actual = campos.get(key)
            if actual == expected:
                print(f"   ✅ {key}={actual}")
            else:
                print(f"   ❌ {key}={actual}, expected {expected}")
                all_match = False
        if all_match:
            print(f"   ✅ PASS: All campos saved correctly")
            results.append(("Verify campos saved", True, ""))
        else:
            print(f"   ❌ FAIL: Some campos not saved correctly")
            results.append(("Verify campos saved", False, "Values mismatch"))
    else:
        print(f"   ❌ FAIL: Expected 200, got {resp.status_code}")
        results.append(("Verify campos saved", False, f"Status {resp.status_code}"))
    
    return results


def test_adjunto_manual_conversion(item_id):
    """C) ADJUNTO MANUAL CON CONVERSIÓN A PDF"""
    print("\n" + "="*80)
    print("C) TESTING ADJUNTO MANUAL CON CONVERSIÓN A PDF")
    print("="*80)
    
    results = []
    
    # Create a small PNG image
    print("\n1. Creating PNG image and uploading to attach-manual")
    img = Image.new('RGB', (200, 100), color='lightblue')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    files = [('files', ('test_image.png', img_bytes, 'image/png'))]
    resp = requests.post(f"{BASE_URL}/procesamiento/queue/{item_id}/attach-manual", files=files, timeout=15)
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   Response: {data}")
        added = data.get("added", [])
        convertidos = data.get("convertidos", [])
        errors = data.get("errors", [])
        
        if len(added) > 0 and any(f.endswith('.pdf') for f in added):
            print(f"   ✅ PASS: Image uploaded and converted to PDF")
            print(f"      added={added}")
            print(f"      convertidos={convertidos}")
            if len(convertidos) > 0:
                print(f"   ✅ convertidos list includes the converted file")
            results.append(("Upload PNG and convert to PDF", True, ""))
        else:
            print(f"   ❌ FAIL: No PDF in added list")
            results.append(("Upload PNG and convert to PDF", False, "No PDF conversion"))
    else:
        print(f"   ❌ FAIL: Expected 200, got {resp.status_code}")
        results.append(("Upload PNG and convert to PDF", False, f"Status {resp.status_code}"))
    
    # Create a PDF with reportlab
    print("\n2. Creating PDF with reportlab and uploading")
    pdf_bytes = io.BytesIO()
    c = canvas.Canvas(pdf_bytes, pagesize=letter)
    c.drawString(100, 750, "Test PDF Document")
    c.drawString(100, 730, "This is a test PDF for Central Mutuos")
    c.showPage()
    c.save()
    pdf_bytes.seek(0)
    
    files = [('files', ('test_document.pdf', pdf_bytes, 'application/pdf'))]
    resp = requests.post(f"{BASE_URL}/procesamiento/queue/{item_id}/attach-manual", files=files, timeout=15)
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   Response: {data}")
        added = data.get("added", [])
        convertidos = data.get("convertidos", [])
        
        if len(added) > 0 and any('test_document' in f for f in added):
            print(f"   ✅ PASS: PDF uploaded successfully")
            print(f"      added={added}")
            if len(convertidos) == 0 or not any('test_document' in f for f in convertidos):
                print(f"   ✅ convertidos does NOT include PDF (already was PDF)")
                results.append(("Upload PDF (no conversion)", True, ""))
            else:
                print(f"   ⚠️  WARNING: PDF appears in convertidos (should not convert already-PDF)")
                results.append(("Upload PDF (no conversion)", False, "PDF in convertidos"))
        else:
            print(f"   ❌ FAIL: PDF not in added list")
            results.append(("Upload PDF (no conversion)", False, "PDF not added"))
    else:
        print(f"   ❌ FAIL: Expected 200, got {resp.status_code}")
        results.append(("Upload PDF (no conversion)", False, f"Status {resp.status_code}"))
    
    # Test 3: Verify attachments in queue item
    print(f"\n3. GET /api/procesamiento/queue/{item_id} to verify attachments")
    resp = requests.get(f"{BASE_URL}/procesamiento/queue/{item_id}", timeout=10)
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        attachments = data.get("attachments", [])
        print(f"   attachments: {attachments}")
        if len(attachments) >= 2:
            print(f"   ✅ PASS: Attachments include uploaded files ({len(attachments)} total)")
            results.append(("Verify attachments in queue", True, ""))
        else:
            print(f"   ⚠️  Only {len(attachments)} attachments found")
            results.append(("Verify attachments in queue", False, f"Only {len(attachments)} attachments"))
    else:
        print(f"   ❌ FAIL: Expected 200, got {resp.status_code}")
        results.append(("Verify attachments in queue", False, f"Status {resp.status_code}"))
    
    return results


def test_regression():
    """D) Regression tests"""
    print("\n" + "="*80)
    print("D) REGRESSION TESTS")
    print("="*80)
    
    results = []
    
    # Test 1: POST /api/simular-credito
    print("\n1. POST /api/simular-credito with minimal payload")
    payload = {
        "renta_titular": 1500000,
        "plazo_anos": 25,
        "tasa_anual": 0.0635,
        "valor_uf": 39842,
        "edad_cliente": 35
    }
    resp = requests.post(f"{BASE_URL}/simular-credito", json=payload, timeout=10)
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   ✅ PASS: Simular-credito returns 200")
        print(f"      capacidad_credito_uf={data.get('capacidad_credito_uf')}")
        results.append(("Simular-credito regression", True, ""))
    else:
        print(f"   ❌ FAIL: Expected 200, got {resp.status_code}")
        results.append(("Simular-credito regression", False, f"Status {resp.status_code}"))
    
    # Test 2: GET /api/autocorreo/status
    print("\n2. GET /api/autocorreo/status")
    resp = requests.get(f"{BASE_URL}/autocorreo/status", timeout=10)
    print(f"   Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"   ✅ PASS: Autocorreo status returns 200")
        print(f"      enabled={data.get('enabled')}, connected={data.get('connected')}")
        results.append(("Autocorreo status regression", True, ""))
    else:
        print(f"   ❌ FAIL: Expected 200, got {resp.status_code}")
        results.append(("Autocorreo status regression", False, f"Status {resp.status_code}"))
    
    return results


def print_summary(all_results):
    """Print test summary"""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    total = len(all_results)
    passed = sum(1 for _, success, _ in all_results if success)
    failed = total - passed
    
    print(f"\nTotal tests: {total}")
    print(f"Passed: {passed} ({100*passed//total}%)")
    print(f"Failed: {failed}")
    
    if failed > 0:
        print("\n❌ FAILED TESTS:")
        for name, success, error in all_results:
            if not success:
                print(f"   - {name}: {error}")
    
    print("\n✅ PASSED TESTS:")
    for name, success, _ in all_results:
        if success:
            print(f"   - {name}")
    
    return passed, failed


def main():
    print("="*80)
    print("CENTRAL MUTUOS BACKEND TESTING")
    print("Testing: Nuevas credenciales + Campos indispensables + Adjunto manual")
    print("="*80)
    
    all_results = []
    
    # A) Test nuevas credenciales
    try:
        results = test_nuevas_credenciales()
        all_results.extend(results)
    except Exception as e:
        print(f"\n❌ ERROR in nuevas credenciales tests: {e}")
        all_results.append(("Nuevas credenciales", False, str(e)))
    
    # Get or create a queue item for B and C tests
    try:
        item = get_or_create_queue_item()
        if item:
            item_id = item["id"]
            
            # B) Test validacion campos indispensables
            try:
                results = test_validacion_campos_indispensables(item_id)
                all_results.extend(results)
            except Exception as e:
                print(f"\n❌ ERROR in validacion campos tests: {e}")
                all_results.append(("Validacion campos", False, str(e)))
            
            # C) Test adjunto manual conversion
            try:
                results = test_adjunto_manual_conversion(item_id)
                all_results.extend(results)
            except Exception as e:
                print(f"\n❌ ERROR in adjunto manual tests: {e}")
                all_results.append(("Adjunto manual", False, str(e)))
        else:
            print("\n⚠️  WARNING: Could not get queue item, skipping B and C tests")
            all_results.append(("Get queue item", False, "No items available"))
    except Exception as e:
        print(f"\n❌ ERROR getting queue item: {e}")
        all_results.append(("Get queue item", False, str(e)))
    
    # D) Regression tests
    try:
        results = test_regression()
        all_results.extend(results)
    except Exception as e:
        print(f"\n❌ ERROR in regression tests: {e}")
        all_results.append(("Regression", False, str(e)))
    
    # Print summary
    passed, failed = print_summary(all_results)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(main())
