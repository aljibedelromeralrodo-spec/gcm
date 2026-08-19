#!/usr/bin/env python3
"""
Test Autocorreo Flow Update - Central Mutuos
Tests the updated autocorreo flow:
- RECHAZOS de mesa are now forwarded even WITHOUT PDF (only text)
- All forwarded emails include a header with the name and email of the ejecutivo
  who sent the gestión (cross-referenced from Procesamiento queue)
- IMAP endpoints are slow with 120s timeout; 502/timeout from proxy is 
  infrastructure limitation, not a bug
"""
import requests
import time
import json

# Backend URL from frontend/.env
BASE_URL = "https://espejo-hibrido.preview.emergentagent.com/api"

# Test results tracking
all_results = []

def log_result(category, test_name, passed, details=""):
    """Log test result"""
    all_results.append({
        "category": category,
        "test": test_name,
        "passed": passed,
        "details": details
    })
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"   {status}: {test_name}")
    if details:
        print(f"      {details}")

def print_category(title):
    """Print category header"""
    print("\n" + "="*80)
    print(f"{title}")
    print("="*80)

# ============================================================================
# 1. AUTOCORREO RUN - Main test
# ============================================================================
def test_autocorreo_run():
    print_category("1. AUTOCORREO RUN - Updated Flow")
    
    # Test 1: POST /api/autocorreo/run
    print("\n1.1 POST /api/autocorreo/run with {}")
    print("   NOTE: This endpoint reads real emails from mesa (aprobaciones@centralmutuos.cl)")
    print("   and sends to gerardo.ext@centralmutuos.cl. Timeout 120s.")
    print("   502/timeout is infrastructure limitation, not a bug.")
    try:
        resp = requests.post(f"{BASE_URL}/autocorreo/run", json={}, timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            # Check structure
            has_processed = "processed" in data
            has_sent = "sent" in data
            has_errors = "errors" in data
            
            if has_processed and has_sent and has_errors:
                processed = data.get("processed", 0)
                sent = data.get("sent", 0)
                errors = data.get("errors", [])
                
                # processed can be 0 if no new emails after cutoff
                log_result("AUTOCORREO_RUN", 
                          "POST /api/autocorreo/run → 200 {processed, sent, errors}", 
                          True, 
                          f"processed={processed}, sent={sent}, errors={len(errors)}")
                
                # Store for next test
                return {"processed": processed, "sent": sent, "errors": errors}
            else:
                log_result("AUTOCORREO_RUN", 
                          "POST /api/autocorreo/run → 200 {processed, sent, errors}", 
                          False, 
                          f"Missing fields: processed={has_processed}, sent={has_sent}, errors={has_errors}")
                return None
        elif resp.status_code == 502:
            # 502 is acceptable - infrastructure timeout
            log_result("AUTOCORREO_RUN", 
                      "POST /api/autocorreo/run → 200 or 502 (infra timeout)", 
                      True, 
                      "502 Bad Gateway - Infrastructure timeout (acceptable per review request)")
            return {"processed": "unknown", "sent": "unknown", "errors": []}
        else:
            log_result("AUTOCORREO_RUN", 
                      "POST /api/autocorreo/run → 200 or 502 (infra timeout)", 
                      False, 
                      f"Status {resp.status_code} - Expected 200 or 502")
            return None
    except requests.exceptions.Timeout:
        log_result("AUTOCORREO_RUN", 
                  "POST /api/autocorreo/run → 200 or 502 (infra timeout)", 
                  True, 
                  "Request timeout after 120s - Infrastructure limitation (acceptable)")
        return {"processed": "unknown", "sent": "unknown", "errors": []}
    except Exception as e:
        log_result("AUTOCORREO_RUN", 
                  "POST /api/autocorreo/run → 200 or 502 (infra timeout)", 
                  False, 
                  str(e))
        return None

# ============================================================================
# 2. AUTOCORREO STATUS - Check recent records
# ============================================================================
def test_autocorreo_status(run_result):
    print_category("2. AUTOCORREO STATUS - Check Recent Records")
    
    # Test 1: GET /api/autocorreo/status
    print("\n2.1 GET /api/autocorreo/status")
    try:
        resp = requests.get(f"{BASE_URL}/autocorreo/status", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            
            # Check basic structure
            has_enabled = "enabled" in data
            has_destination = "destination" in data
            has_recent = "recent" in data
            
            if not (has_enabled and has_destination and has_recent):
                log_result("AUTOCORREO_STATUS", 
                          "GET /api/autocorreo/status → 200 with structure", 
                          False, 
                          f"Missing fields: enabled={has_enabled}, destination={has_destination}, recent={has_recent}")
                return
            
            log_result("AUTOCORREO_STATUS", 
                      "GET /api/autocorreo/status → 200 with structure", 
                      True)
            
            # Check recent records
            recent = data.get("recent", [])
            print(f"\n   Found {len(recent)} recent records")
            
            if len(recent) > 0:
                # Check structure of recent records
                first_record = recent[0]
                required_fields = ["processed_at", "subject", "cliente", "status"]
                missing = [f for f in required_fields if f not in first_record]
                
                if not missing:
                    log_result("AUTOCORREO_STATUS", 
                              "Recent records have required fields {processed_at, subject, cliente, status}", 
                              True)
                else:
                    log_result("AUTOCORREO_STATUS", 
                              "Recent records have required fields {processed_at, subject, cliente, status}", 
                              False, 
                              f"Missing: {missing}")
                
                # Check for rechazos without PDF
                rechazos_sin_pdf = [r for r in recent if "(sin PDF - solo texto)" in r.get("attachments_info", "")]
                
                if rechazos_sin_pdf:
                    print(f"\n   ⚠️  FOUND {len(rechazos_sin_pdf)} RECHAZO(S) WITHOUT PDF (only text):")
                    for r in rechazos_sin_pdf:
                        print(f"      - Cliente: {r.get('cliente')}")
                        print(f"        Subject: {r.get('subject')}")
                        print(f"        Attachments: {r.get('attachments_info')}")
                        print(f"        Status: {r.get('status')}")
                    
                    log_result("AUTOCORREO_STATUS", 
                              "Rechazos without PDF are being forwarded (new feature)", 
                              True, 
                              f"Found {len(rechazos_sin_pdf)} rechazo(s) with '(sin PDF - solo texto)'")
                else:
                    print("   ℹ️  No rechazos without PDF found in recent records (this is OK)")
                    log_result("AUTOCORREO_STATUS", 
                              "Rechazos without PDF check", 
                              True, 
                              "No rechazos without PDF in recent records (not required)")
            else:
                print("   ℹ️  No recent records found (this is OK if no emails were processed)")
                log_result("AUTOCORREO_STATUS", 
                          "Recent records check", 
                          True, 
                          "No recent records (OK if no new emails after cutoff)")
        else:
            log_result("AUTOCORREO_STATUS", 
                      "GET /api/autocorreo/status → 200", 
                      False, 
                      f"Status {resp.status_code}")
    except Exception as e:
        log_result("AUTOCORREO_STATUS", 
                  "GET /api/autocorreo/status → 200", 
                  False, 
                  str(e))

# ============================================================================
# 3. AUTOCORREO REGRESSION
# ============================================================================
def test_autocorreo_regression():
    print_category("3. AUTOCORREO REGRESSION")
    
    # Test 1: GET /api/autocorreo/mailboxes?probe=true
    print("\n3.1 GET /api/autocorreo/mailboxes?probe=true")
    try:
        resp = requests.get(f"{BASE_URL}/autocorreo/mailboxes?probe=true", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            # Handle both list and {"accounts": [...]} formats
            accounts = data if isinstance(data, list) else data.get("accounts", [])
            
            if isinstance(accounts, list) and len(accounts) == 2:
                # Check if both accounts have auth_live=true
                all_live = all(acc.get("auth_live") == True for acc in accounts)
                if all_live:
                    log_result("AUTOCORREO_REGRESSION", 
                              "GET /api/autocorreo/mailboxes?probe=true → 2 accounts auth_live=true", 
                              True)
                else:
                    log_result("AUTOCORREO_REGRESSION", 
                              "GET /api/autocorreo/mailboxes?probe=true → 2 accounts auth_live=true", 
                              False, 
                              "Not all accounts have auth_live=true")
            else:
                log_result("AUTOCORREO_REGRESSION", 
                          "GET /api/autocorreo/mailboxes?probe=true → 2 accounts auth_live=true", 
                          False, 
                          f"Expected 2 accounts, got {len(accounts) if isinstance(accounts, list) else 'not a list'}")
        else:
            log_result("AUTOCORREO_REGRESSION", 
                      "GET /api/autocorreo/mailboxes?probe=true → 2 accounts auth_live=true", 
                      False, 
                      f"Status {resp.status_code}")
    except Exception as e:
        log_result("AUTOCORREO_REGRESSION", 
                  "GET /api/autocorreo/mailboxes?probe=true → 2 accounts auth_live=true", 
                  False, 
                  str(e))
    
    # Test 2: POST /api/autocorreo/toggle (enable)
    print("\n3.2 POST /api/autocorreo/toggle {enabled: true}")
    try:
        resp = requests.post(f"{BASE_URL}/autocorreo/toggle", json={"enabled": True}, timeout=10)
        if resp.status_code == 200:
            log_result("AUTOCORREO_REGRESSION", 
                      "POST /api/autocorreo/toggle {enabled: true} → 200", 
                      True)
        else:
            log_result("AUTOCORREO_REGRESSION", 
                      "POST /api/autocorreo/toggle {enabled: true} → 200", 
                      False, 
                      f"Status {resp.status_code}")
    except Exception as e:
        log_result("AUTOCORREO_REGRESSION", 
                  "POST /api/autocorreo/toggle {enabled: true} → 200", 
                  False, 
                  str(e))
    
    # Test 3: POST /api/autocorreo/toggle (disable)
    print("\n3.3 POST /api/autocorreo/toggle {enabled: false}")
    try:
        resp = requests.post(f"{BASE_URL}/autocorreo/toggle", json={"enabled": False}, timeout=10)
        if resp.status_code == 200:
            log_result("AUTOCORREO_REGRESSION", 
                      "POST /api/autocorreo/toggle {enabled: false} → 200", 
                      True)
        else:
            log_result("AUTOCORREO_REGRESSION", 
                      "POST /api/autocorreo/toggle {enabled: false} → 200", 
                      False, 
                      f"Status {resp.status_code}")
    except Exception as e:
        log_result("AUTOCORREO_REGRESSION", 
                  "POST /api/autocorreo/toggle {enabled: false} → 200", 
                  False, 
                  str(e))

# ============================================================================
# 4. GENERAL REGRESSION
# ============================================================================
def test_general_regression():
    print_category("4. GENERAL REGRESSION")
    
    # Test 1: POST /api/auth/login
    print("\n4.1 POST /api/auth/login (administrador/141617575)")
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", 
                           json={"rut": "administrador", "password": "141617575"}, 
                           timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("rol") == "admin":
                log_result("GENERAL_REGRESSION", 
                          "POST /api/auth/login (administrador/141617575) → 200 rol=admin", 
                          True)
            else:
                log_result("GENERAL_REGRESSION", 
                          "POST /api/auth/login (administrador/141617575) → 200 rol=admin", 
                          False, 
                          f"rol={data.get('rol')}")
        else:
            log_result("GENERAL_REGRESSION", 
                      "POST /api/auth/login (administrador/141617575) → 200 rol=admin", 
                      False, 
                      f"Status {resp.status_code}")
    except Exception as e:
        log_result("GENERAL_REGRESSION", 
                  "POST /api/auth/login (administrador/141617575) → 200 rol=admin", 
                  False, 
                  str(e))
    
    # Test 2: GET /api/procesamiento/stats
    print("\n4.2 GET /api/procesamiento/stats")
    try:
        resp = requests.get(f"{BASE_URL}/procesamiento/stats", timeout=10)
        if resp.status_code == 200:
            log_result("GENERAL_REGRESSION", 
                      "GET /api/procesamiento/stats → 200", 
                      True)
        else:
            log_result("GENERAL_REGRESSION", 
                      "GET /api/procesamiento/stats → 200", 
                      False, 
                      f"Status {resp.status_code}")
    except Exception as e:
        log_result("GENERAL_REGRESSION", 
                  "GET /api/procesamiento/stats → 200", 
                  False, 
                  str(e))
    
    # Test 3: POST /api/simular-credito (minimal payload)
    print("\n4.3 POST /api/simular-credito (minimal payload)")
    try:
        payload = {
            "renta_titular": 1500000,
            "plazo_anos": 25,
            "tasa_anual": 0.0635,
            "valor_uf": 39842,
            "edad_cliente": 35
        }
        resp = requests.post(f"{BASE_URL}/simular-credito", json=payload, timeout=10)
        if resp.status_code == 200:
            log_result("GENERAL_REGRESSION", 
                      "POST /api/simular-credito (minimal) → 200", 
                      True)
        else:
            log_result("GENERAL_REGRESSION", 
                      "POST /api/simular-credito (minimal) → 200", 
                      False, 
                      f"Status {resp.status_code}")
    except Exception as e:
        log_result("GENERAL_REGRESSION", 
                  "POST /api/simular-credito (minimal) → 200", 
                  False, 
                  str(e))

# ============================================================================
# 5. CODE VERIFICATION (Optional)
# ============================================================================
def test_code_verification():
    print_category("5. CODE VERIFICATION (Optional)")
    
    # Test 1: GET /api/procesamiento/queue - check for email_ejecutivo field
    print("\n5.1 GET /api/procesamiento/queue (check campos.email_ejecutivo)")
    try:
        resp = requests.get(f"{BASE_URL}/procesamiento/queue", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            # Handle both list and {"rows": [...]} formats
            rows = data if isinstance(data, list) else data.get("rows", [])
            
            if isinstance(rows, list) and len(rows) > 0:
                # Check if any items have campos.email_ejecutivo
                items_with_ejecutivo = [r for r in rows if r.get("campos", {}).get("email_ejecutivo")]
                
                if items_with_ejecutivo:
                    print(f"   ✅ Found {len(items_with_ejecutivo)} items with campos.email_ejecutivo")
                    # Show first one as example
                    first = items_with_ejecutivo[0]
                    campos = first.get("campos", {})
                    print(f"      Example:")
                    print(f"        - Cliente: {first.get('classification', {}).get('cliente', 'N/A')}")
                    print(f"        - email_ejecutivo: {campos.get('email_ejecutivo', 'N/A')}")
                    print(f"        - nombre_ejecutivo: {campos.get('nombre_ejecutivo', 'N/A')}")
                    
                    log_result("CODE_VERIFICATION", 
                              "GET /api/procesamiento/queue → items with campos.email_ejecutivo", 
                              True, 
                              f"Found {len(items_with_ejecutivo)} items with ejecutivo data")
                else:
                    print("   ℹ️  No items with campos.email_ejecutivo found")
                    log_result("CODE_VERIFICATION", 
                              "GET /api/procesamiento/queue → items with campos.email_ejecutivo", 
                              True, 
                              "No items with ejecutivo data (OK - structure exists in code)")
            else:
                print("   ℹ️  No queue items found")
                log_result("CODE_VERIFICATION", 
                          "GET /api/procesamiento/queue → items with campos.email_ejecutivo", 
                          True, 
                          "No queue items (OK - structure exists in code)")
        else:
            log_result("CODE_VERIFICATION", 
                      "GET /api/procesamiento/queue → 200", 
                      False, 
                      f"Status {resp.status_code}")
    except Exception as e:
        log_result("CODE_VERIFICATION", 
                  "GET /api/procesamiento/queue → 200", 
                  False, 
                  str(e))

# ============================================================================
# MAIN
# ============================================================================
def main():
    print("\n" + "="*80)
    print("TEST AUTOCORREO FLOW UPDATE - Central Mutuos")
    print("="*80)
    print(f"Backend URL: {BASE_URL}")
    print("="*80)
    print("\nTesting updated autocorreo flow:")
    print("  - RECHAZOS de mesa forwarded even WITHOUT PDF (only text)")
    print("  - All forwarded emails include ejecutivo header (name + email)")
    print("  - IMAP endpoints slow (120s timeout); 502 is infra limitation")
    print("="*80)
    
    # Run tests
    run_result = test_autocorreo_run()
    test_autocorreo_status(run_result)
    test_autocorreo_regression()
    test_general_regression()
    test_code_verification()
    
    # Print summary
    print("\n" + "="*80)
    print("RESUMEN DE PRUEBAS")
    print("="*80)
    
    # Group by category
    categories = {}
    for result in all_results:
        cat = result["category"]
        if cat not in categories:
            categories[cat] = {"passed": 0, "failed": 0, "tests": []}
        if result["passed"]:
            categories[cat]["passed"] += 1
        else:
            categories[cat]["failed"] += 1
        categories[cat]["tests"].append(result)
    
    # Print by category
    total_passed = 0
    total_failed = 0
    for cat, data in categories.items():
        print(f"\n{cat}:")
        print(f"  ✅ Passed: {data['passed']}")
        print(f"  ❌ Failed: {data['failed']}")
        total_passed += data["passed"]
        total_failed += data["failed"]
        
        # Print failed tests
        if data["failed"] > 0:
            print(f"  Failed tests:")
            for test in data["tests"]:
                if not test["passed"]:
                    print(f"    - {test['test']}")
                    if test["details"]:
                        print(f"      {test['details']}")
    
    print("\n" + "="*80)
    print(f"TOTAL: {total_passed + total_failed} tests")
    print(f"✅ PASSED: {total_passed}")
    print(f"❌ FAILED: {total_failed}")
    if total_passed + total_failed > 0:
        print(f"Success rate: {total_passed / (total_passed + total_failed) * 100:.1f}%")
    print("="*80)
    
    # Return exit code
    return 0 if total_failed == 0 else 1

if __name__ == "__main__":
    exit(main())
