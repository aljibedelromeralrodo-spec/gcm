#!/usr/bin/env python3
"""
Backend API Testing for Central Mutuos - Login Fix & Autocorreo Enriquecido
FINAL COMPREHENSIVE TEST
"""
import requests
import time
import json

BASE_URL = "https://risk-assess-17.preview.emergentagent.com/api"
ADMIN_USER = "admin"
ADMIN_PASS = "0586"
SLOW_TIMEOUT = 120

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def log_test(name, passed, details=""):
    status = f"{GREEN}✅ PASS{RESET}" if passed else f"{RED}❌ FAIL{RESET}"
    print(f"{status} - {name}")
    if details:
        print(f"  {details}")
    return passed

def main():
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}Central Mutuos - FINAL COMPREHENSIVE TEST{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")
    
    results = []
    
    # A) FIX LOGIN (crítico)
    print(f"\n{BLUE}--- A) FIX LOGIN (crítico) ---{RESET}")
    
    # A1: Basic login
    r = requests.post(f"{BASE_URL}/auth/login", json={"rut": "admin", "password": "0586"}, timeout=10)
    data = r.json()
    results.append(log_test("A1: Login admin/0586", 
                           r.status_code == 200 and data.get("rol") == "admin",
                           f"Status: {r.status_code}, Rol: {data.get('rol')}"))
    
    # A2: Uppercase
    r = requests.post(f"{BASE_URL}/auth/login", json={"rut": "ADMIN", "password": "0586"}, timeout=10)
    results.append(log_test("A2: Login ADMIN/0586 (uppercase)", 
                           r.status_code == 200 and r.json().get("rol") == "admin",
                           f"Status: {r.status_code}"))
    
    # A3: Spaces
    r = requests.post(f"{BASE_URL}/auth/login", json={"rut": "  admin  ", "password": "0586"}, timeout=10)
    results.append(log_test("A3: Login '  admin  '/0586 (spaces)", 
                           r.status_code == 200 and r.json().get("rol") == "admin",
                           f"Status: {r.status_code}"))
    
    # A4: Wrong password
    r = requests.post(f"{BASE_URL}/auth/login", json={"rut": "admin", "password": "9999"}, timeout=10)
    results.append(log_test("A4: Login admin/9999 (wrong password)", 
                           r.status_code == 401,
                           f"Status: {r.status_code} (expected 401)"))
    
    # A5: Using 'codigo' field
    r = requests.post(f"{BASE_URL}/auth/login", json={"codigo": "admin", "password": "0586"}, timeout=10)
    results.append(log_test("A5: Login with 'codigo' field", 
                           r.status_code == 200 and r.json().get("rol") == "admin",
                           f"Status: {r.status_code}"))
    
    # B & C) ENVIAR AUTOCORREO + Verify ejecutivo data
    print(f"\n{BLUE}--- B & C) AUTOCORREO + Ejecutivo Data ---{RESET}")
    
    # Get queue
    r = requests.get(f"{BASE_URL}/procesamiento/queue", timeout=10)
    queue_items = r.json().get("rows", [])
    queue_passed = log_test("B-Prep: Get queue", 
                           r.status_code == 200 and len(queue_items) > 0,
                           f"Status: {r.status_code}, Items: {len(queue_items)}")
    results.append(queue_passed)
    
    if queue_items:
        # Take first item and reprocess to ensure it has ejecutivo data
        item_id = queue_items[0]["id"]
        print(f"{BLUE}ℹ Using item: {item_id}{RESET}")
        
        # Reprocess to apply the fix
        print(f"{YELLOW}⏳ Reprocessing item to apply ejecutivo data fix...{RESET}")
        r = requests.post(f"{BASE_URL}/procesamiento/queue/{item_id}/reprocess", timeout=120)
        results.append(log_test("B-Prep: Reprocess item", 
                               r.status_code == 200,
                               f"Status: {r.status_code}"))
        
        # C) Verify ejecutivo data
        r = requests.get(f"{BASE_URL}/procesamiento/queue/{item_id}", timeout=10)
        data = r.json()
        campos = data.get("campos", {})
        classification = data.get("classification", {})
        
        has_email_ejecutivo = "email_ejecutivo" in campos and bool(campos["email_ejecutivo"])
        has_nombre_ejecutivo = "nombre_ejecutivo" in campos and bool(campos["nombre_ejecutivo"])
        has_email_cliente = "email_cliente" in classification
        
        results.append(log_test("C: Verify email_ejecutivo in campos", 
                               has_email_ejecutivo,
                               f"email_ejecutivo: {campos.get('email_ejecutivo')}"))
        results.append(log_test("C: Verify nombre_ejecutivo in campos", 
                               has_nombre_ejecutivo,
                               f"nombre_ejecutivo: {campos.get('nombre_ejecutivo')}"))
        results.append(log_test("C: Verify email_cliente in classification", 
                               has_email_cliente,
                               f"email_cliente: '{classification.get('email_cliente')}'"))
        
        # Upload to drive (generate PDF)
        r = requests.post(f"{BASE_URL}/procesamiento/queue/{item_id}/upload-drive", timeout=30)
        data = r.json()
        has_merged_pdf = any("Carpeta_" in f for f in data.get("uploaded", []))
        results.append(log_test("B-Prep: Upload to drive (generate PDF)", 
                               r.status_code == 200 and has_merged_pdf,
                               f"Status: {r.status_code}, Merged PDF: {has_merged_pdf}"))
        
        # B) Send autocorreo enriquecido
        r = requests.post(f"{BASE_URL}/procesamiento/queue/{item_id}/enviar-autocorreo", timeout=30)
        data = r.json()
        results.append(log_test("B: Enviar autocorreo enriquecido", 
                               r.status_code == 200 and data.get("success") == True,
                               f"Status: {r.status_code}, Success: {data.get('success')}, Destino: {data.get('destino')}, Adjunto: {data.get('adjunto')}"))
        
        # Verify autocorreo_enviado flag
        r = requests.get(f"{BASE_URL}/procesamiento/queue/{item_id}", timeout=10)
        data = r.json()
        results.append(log_test("B-Verify: autocorreo_enviado flag set", 
                               data.get("autocorreo_enviado") == True,
                               f"autocorreo_enviado: {data.get('autocorreo_enviado')}"))
    
    # Test 404 for non-existent item
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = requests.post(f"{BASE_URL}/procesamiento/queue/{fake_id}/enviar-autocorreo", timeout=10)
    results.append(log_test("B-404: Enviar autocorreo with non-existent ID", 
                           r.status_code == 404,
                           f"Status: {r.status_code} (expected 404)"))
    
    # D) Regression
    print(f"\n{BLUE}--- D) Regression Tests ---{RESET}")
    
    r = requests.get(f"{BASE_URL}/autocorreo/status", timeout=10)
    results.append(log_test("D1: GET /api/autocorreo/status", 
                           r.status_code == 200,
                           f"Status: {r.status_code}"))
    
    r = requests.get(f"{BASE_URL}/central/email-status", timeout=30)
    data = r.json()
    results.append(log_test("D2: GET /api/central/email-status", 
                           r.status_code == 200 and data.get("connected") == True,
                           f"Status: {r.status_code}, Connected: {data.get('connected')}"))
    
    # Summary
    passed = sum(1 for r in results if r)
    total = len(results)
    pass_rate = (passed / total * 100) if total > 0 else 0
    
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}Test Summary{RESET}")
    print(f"{BLUE}{'='*70}{RESET}")
    print(f"Total Tests: {total}")
    print(f"Passed: {GREEN}{passed}{RESET}")
    print(f"Failed: {RED}{total - passed}{RESET}")
    print(f"Pass Rate: {GREEN if pass_rate == 100 else YELLOW}{pass_rate:.1f}%{RESET}\n")
    
    if pass_rate == 100:
        print(f"{GREEN}✅ All tests passed!{RESET}\n")
    else:
        print(f"{YELLOW}⚠ Some tests failed - review details above{RESET}\n")

if __name__ == "__main__":
    main()
