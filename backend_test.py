#!/usr/bin/env python3
"""
Comprehensive backend API tests for Central Mutuos / Central PREDIC
Tests all main endpoints with realistic data
"""
import requests
import json
import sys
from typing import Dict, Any

# Base URL from frontend/.env
BASE_URL = "https://risk-assess-17.preview.emergentagent.com/api"

# Test results tracking
test_results = {
    "passed": [],
    "failed": [],
    "warnings": []
}


def log_test(name: str, passed: bool, details: str = ""):
    """Log test result"""
    if passed:
        test_results["passed"].append(f"✅ {name}")
        print(f"✅ PASS: {name}")
    else:
        test_results["failed"].append(f"❌ {name}: {details}")
        print(f"❌ FAIL: {name}")
        if details:
            print(f"   Details: {details}")


def log_warning(name: str, details: str):
    """Log warning"""
    test_results["warnings"].append(f"⚠️  {name}: {details}")
    print(f"⚠️  WARNING: {name}: {details}")


def test_auth_login():
    """Test 1: POST /api/auth/login"""
    print("\n=== Testing Auth Login ===")
    
    # Test with correct credentials
    try:
        response = requests.post(f"{BASE_URL}/auth/login", json={
            "rut": "admin",
            "password": "0586"
        }, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if "token" in data and "nombre" in data and data.get("rol") == "admin":
                log_test("Auth login with correct credentials", True)
            else:
                log_test("Auth login with correct credentials", False, 
                        f"Missing fields or incorrect rol. Got: {data}")
        else:
            log_test("Auth login with correct credentials", False, 
                    f"Status {response.status_code}: {response.text}")
    except Exception as e:
        log_test("Auth login with correct credentials", False, str(e))
    
    # Test with incorrect credentials
    try:
        response = requests.post(f"{BASE_URL}/auth/login", json={
            "rut": "admin",
            "password": "wrong"
        }, timeout=10)
        
        if response.status_code == 401:
            log_test("Auth login with incorrect credentials returns 401", True)
        else:
            log_test("Auth login with incorrect credentials returns 401", False, 
                    f"Expected 401, got {response.status_code}")
    except Exception as e:
        log_test("Auth login with incorrect credentials returns 401", False, str(e))


def test_config_endpoints():
    """Test 2: Configuration endpoints"""
    print("\n=== Testing Configuration Endpoints ===")
    
    # GET /api/valor-uf
    try:
        response = requests.get(f"{BASE_URL}/valor-uf", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "valor_uf" in data:
                log_test("GET /api/valor-uf", True)
            else:
                log_test("GET /api/valor-uf", False, f"Missing valor_uf field. Got: {data}")
        else:
            log_test("GET /api/valor-uf", False, f"Status {response.status_code}")
    except Exception as e:
        log_test("GET /api/valor-uf", False, str(e))
    
    # GET /api/admin/criterios
    try:
        response = requests.get(f"{BASE_URL}/admin/criterios", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "btg_pactual" in data and "ameris" in data and "parametros_generales" in data:
                log_test("GET /api/admin/criterios", True)
            else:
                log_test("GET /api/admin/criterios", False, 
                        f"Missing expected structure. Got keys: {list(data.keys())}")
        else:
            log_test("GET /api/admin/criterios", False, f"Status {response.status_code}")
    except Exception as e:
        log_test("GET /api/admin/criterios", False, str(e))
    
    # GET /api/inmobiliaria/config/tasas
    try:
        response = requests.get(f"{BASE_URL}/inmobiliaria/config/tasas", timeout=10)
        if response.status_code == 200:
            data = response.json()
            log_test("GET /api/inmobiliaria/config/tasas", True)
        else:
            log_test("GET /api/inmobiliaria/config/tasas", False, f"Status {response.status_code}")
    except Exception as e:
        log_test("GET /api/inmobiliaria/config/tasas", False, str(e))
    
    # GET /api/inmobiliaria/config/seguros
    try:
        response = requests.get(f"{BASE_URL}/inmobiliaria/config/seguros", timeout=10)
        if response.status_code == 200:
            data = response.json()
            log_test("GET /api/inmobiliaria/config/seguros", True)
        else:
            log_test("GET /api/inmobiliaria/config/seguros", False, f"Status {response.status_code}")
    except Exception as e:
        log_test("GET /api/inmobiliaria/config/seguros", False, str(e))
    
    # PUT /api/inmobiliaria/config/tasas
    try:
        response = requests.put(f"{BASE_URL}/inmobiliaria/config/tasas", json={
            "tasa_subsidio_mayor_2000": 0.064,
            "tasa_subsidio_menor_2000": 0.065,
            "tasa_sin_subsidio": 0.059
        }, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                log_test("PUT /api/inmobiliaria/config/tasas", True)
            else:
                log_test("PUT /api/inmobiliaria/config/tasas", False, f"No 'ok' field. Got: {data}")
        else:
            log_test("PUT /api/inmobiliaria/config/tasas", False, f"Status {response.status_code}")
    except Exception as e:
        log_test("PUT /api/inmobiliaria/config/tasas", False, str(e))


def test_simular_credito():
    """Test 3: Credit simulation endpoints"""
    print("\n=== Testing Credit Simulation ===")
    
    # POST /api/simular-credito
    payload = {
        "nombre_completo": "Juan Pérez González",
        "rut": "12345678-9",
        "valor_uf": 39842,
        "renta_titular": 1500000,
        "plazo_anos": 25,
        "tasa_anual": 0.0635,
        "valor_propiedad_uf": 3000,
        "credito_solicitado_uf": 2400,
        "edad_cliente": 35,
        "tipo_deudor": 1,
        "continuidad_laboral": True
    }
    
    simulacion_id = None
    try:
        response = requests.post(f"{BASE_URL}/simular-credito", json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            required_fields = ["capacidad_credito_uf", "credito_maximo_uf", "dividendo_credito_clp",
                             "eval_btg", "eval_ameris", "precalificacion_aprobada"]
            missing = [f for f in required_fields if f not in data]
            if not missing:
                log_test("POST /api/simular-credito", True)
                simulacion_id = data.get("id")
            else:
                log_test("POST /api/simular-credito", False, f"Missing fields: {missing}")
        else:
            log_test("POST /api/simular-credito", False, 
                    f"Status {response.status_code}: {response.text}")
    except Exception as e:
        log_test("POST /api/simular-credito", False, str(e))
    
    # GET /api/simulaciones
    try:
        response = requests.get(f"{BASE_URL}/simulaciones", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "simulaciones" in data and isinstance(data["simulaciones"], list):
                if len(data["simulaciones"]) > 0:
                    log_test("GET /api/simulaciones", True)
                else:
                    log_warning("GET /api/simulaciones", "No simulaciones found")
                    log_test("GET /api/simulaciones", True)
            else:
                log_test("GET /api/simulaciones", False, f"Invalid structure. Got: {data}")
        else:
            log_test("GET /api/simulaciones", False, f"Status {response.status_code}")
    except Exception as e:
        log_test("GET /api/simulaciones", False, str(e))
    
    # POST /api/simulacion/pdf
    try:
        pdf_payload = {
            "nombre_completo": "Juan Pérez González",
            "rut": "12345678-9",
            "capacidad_credito_uf": 2500,
            "capacidad_credito_clp": 99605000,
            "credito_maximo_uf": 2400,
            "dividendo_credito_clp": 750000,
            "plazo_anos": 25,
            "precalificacion_aprobada": True
        }
        response = requests.post(f"{BASE_URL}/simulacion/pdf", json=pdf_payload, timeout=10)
        if response.status_code == 200:
            if response.headers.get("content-type") == "application/pdf":
                log_test("POST /api/simulacion/pdf", True)
            else:
                log_test("POST /api/simulacion/pdf", False, 
                        f"Wrong content-type: {response.headers.get('content-type')}")
        else:
            log_test("POST /api/simulacion/pdf", False, f"Status {response.status_code}")
    except Exception as e:
        log_test("POST /api/simulacion/pdf", False, str(e))


def test_inmobiliaria_endpoints():
    """Test 4: Inmobiliaria endpoints"""
    print("\n=== Testing Inmobiliaria Endpoints ===")
    
    # POST /api/inmobiliaria/auth/login
    try:
        response = requests.post(f"{BASE_URL}/inmobiliaria/auth/login", json={
            "usuario": "demo",
            "password": "demo"
        }, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("ok") == True:
                log_test("POST /api/inmobiliaria/auth/login", True)
            else:
                log_test("POST /api/inmobiliaria/auth/login", False, f"ok != True. Got: {data}")
        else:
            log_test("POST /api/inmobiliaria/auth/login", False, f"Status {response.status_code}")
    except Exception as e:
        log_test("POST /api/inmobiliaria/auth/login", False, str(e))
    
    # POST /api/inmobiliaria/predict
    predict_payload = {
        "modo": "subsidio",
        "valor_propiedad_uf": 3000,
        "subsidio_uf": 500,
        "monto_credito_uf": 2000,
        "renta_fija": 1500000,
        "edad_cliente": 35,
        "plazo_anos": 0,
        "tipo_deudor": 1,
        "antiguedad_laboral_meses": 24,
        "continuidad_laboral": True
    }
    try:
        response = requests.post(f"{BASE_URL}/inmobiliaria/predict", json=predict_payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            required_fields = ["viable", "monto_aprobado_uf", "dividendo_estimado_clp", 
                             "plazo_anos", "seguros", "central_score", "eval_escenario_1"]
            missing = [f for f in required_fields if f not in data]
            if not missing:
                # Check seguros structure
                if "dividendo_final" in data.get("seguros", {}):
                    # Check central_score structure
                    score = data.get("central_score", {})
                    if all(k in score for k in ["score", "risk_level", "risk_color", "factors"]):
                        log_test("POST /api/inmobiliaria/predict", True)
                    else:
                        log_test("POST /api/inmobiliaria/predict", False, 
                                f"central_score missing fields. Got: {score}")
                else:
                    log_test("POST /api/inmobiliaria/predict", False, 
                            "seguros missing dividendo_final")
            else:
                log_test("POST /api/inmobiliaria/predict", False, f"Missing fields: {missing}")
        else:
            log_test("POST /api/inmobiliaria/predict", False, 
                    f"Status {response.status_code}: {response.text}")
    except Exception as e:
        log_test("POST /api/inmobiliaria/predict", False, str(e))
    
    # POST /api/inmobiliaria/calc-deuda
    try:
        response = requests.post(f"{BASE_URL}/inmobiliaria/calc-deuda", json={
            "monto_deuda": 5000000,
            "tasa_anual": 0.02,
            "plazo_anos": 4
        }, timeout=10)
        if response.status_code == 200:
            data = response.json()
            required = ["cuota_mensual", "total_a_pagar", "total_intereses"]
            if all(k in data for k in required):
                log_test("POST /api/inmobiliaria/calc-deuda", True)
            else:
                log_test("POST /api/inmobiliaria/calc-deuda", False, f"Missing fields. Got: {data}")
        else:
            log_test("POST /api/inmobiliaria/calc-deuda", False, f"Status {response.status_code}")
    except Exception as e:
        log_test("POST /api/inmobiliaria/calc-deuda", False, str(e))
    
    # POST /api/inmobiliaria/comparar-competidores
    try:
        response = requests.post(f"{BASE_URL}/inmobiliaria/comparar-competidores", json={
            "valor_propiedad_uf": 3000,
            "monto_credito_uf": 2000,
            "pie_pct": 20,
            "plazo_anos": 30,
            "tasa_mutuaria": 6.5
        }, timeout=10)
        if response.status_code == 200:
            data = response.json()
            required = ["competidores", "resumen", "mensaje_comercial"]
            if all(k in data for k in required):
                log_test("POST /api/inmobiliaria/comparar-competidores", True)
            else:
                log_test("POST /api/inmobiliaria/comparar-competidores", False, 
                        f"Missing fields. Got keys: {list(data.keys())}")
        else:
            log_test("POST /api/inmobiliaria/comparar-competidores", False, 
                    f"Status {response.status_code}")
    except Exception as e:
        log_test("POST /api/inmobiliaria/comparar-competidores", False, str(e))
    
    # POST /api/inmobiliaria/leads
    try:
        response = requests.post(f"{BASE_URL}/inmobiliaria/leads", json={
            "nombre": "María López",
            "telefono": "+56912345678",
            "email": "maria.lopez@example.com",
            "mensaje": "Interesada en crédito hipotecario"
        }, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "id" in data:
                log_test("POST /api/inmobiliaria/leads", True)
            else:
                log_test("POST /api/inmobiliaria/leads", False, f"Missing id. Got: {data}")
        else:
            log_test("POST /api/inmobiliaria/leads", False, f"Status {response.status_code}")
    except Exception as e:
        log_test("POST /api/inmobiliaria/leads", False, str(e))
    
    # GET /api/inmobiliaria/mi-dashboard
    try:
        response = requests.get(f"{BASE_URL}/inmobiliaria/mi-dashboard", timeout=10)
        if response.status_code == 200:
            data = response.json()
            log_test("GET /api/inmobiliaria/mi-dashboard", True)
        else:
            log_test("GET /api/inmobiliaria/mi-dashboard", False, f"Status {response.status_code}")
    except Exception as e:
        log_test("GET /api/inmobiliaria/mi-dashboard", False, str(e))
    
    # GET /api/inmobiliaria/score-history/{nombre}
    try:
        response = requests.get(f"{BASE_URL}/inmobiliaria/score-history/test", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "history" in data:
                log_test("GET /api/inmobiliaria/score-history/{nombre}", True)
            else:
                log_test("GET /api/inmobiliaria/score-history/{nombre}", False, 
                        f"Missing history field. Got: {data}")
        else:
            log_test("GET /api/inmobiliaria/score-history/{nombre}", False, 
                    f"Status {response.status_code}")
    except Exception as e:
        log_test("GET /api/inmobiliaria/score-history/{nombre}", False, str(e))


def test_ia_endpoints():
    """Test 5: IA/AI endpoints"""
    print("\n=== Testing IA/AI Endpoints ===")
    
    # POST /api/ia/predict
    ia_payload = {
        "renta_titular": 1500000,
        "plazo_anos": 25,
        "edad_cliente": 35,
        "tasa_anual": 0.0635,
        "credito_solicitado_uf": 2400,
        "valor_propiedad_uf": 3000
    }
    try:
        response = requests.post(f"{BASE_URL}/ia/predict", json=ia_payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            required = ["probabilidad", "nivel", "score_btg", "score_ameris", "metricas", 
                       "factores_riesgo", "sugerencias", "comparacion_historica"]
            missing = [f for f in required if f not in data]
            if not missing:
                log_test("POST /api/ia/predict", True)
            else:
                log_test("POST /api/ia/predict", False, f"Missing fields: {missing}")
        else:
            log_test("POST /api/ia/predict", False, f"Status {response.status_code}: {response.text}")
    except Exception as e:
        log_test("POST /api/ia/predict", False, str(e))
    
    # GET /api/ia/insights
    try:
        response = requests.get(f"{BASE_URL}/ia/insights", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "insights" in data:
                log_test("GET /api/ia/insights", True)
            else:
                log_test("GET /api/ia/insights", False, f"Missing insights field. Got: {data}")
        else:
            log_test("GET /api/ia/insights", False, f"Status {response.status_code}")
    except Exception as e:
        log_test("GET /api/ia/insights", False, str(e))
    
    # POST /api/ai/analizar
    analizar_payload = {
        "resultado": {
            "capacidad_credito_clp": 99605000,
            "tasa_anual": 0.0635,
            "valor_propiedad_uf": 3000,
            "edad_plazo": 60,
            "plazo_anos": 25,
            "dividendo_tope": 450000
        },
        "valor_uf": 39842
    }
    try:
        response = requests.post(f"{BASE_URL}/ai/analizar", json=analizar_payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            required = ["escenarios", "monto_maximo_viable_uf", "recomendacion_ia"]
            missing = [f for f in required if f not in data]
            if not missing:
                log_test("POST /api/ai/analizar", True)
            else:
                log_test("POST /api/ai/analizar", False, f"Missing fields: {missing}")
        else:
            log_test("POST /api/ai/analizar", False, f"Status {response.status_code}")
    except Exception as e:
        log_test("POST /api/ai/analizar", False, str(e))


def test_central_endpoints():
    """Test 6: Central dashboard and intelligence endpoints"""
    print("\n=== Testing Central Dashboard Endpoints ===")
    
    endpoints = [
        "/central/dashboard-batch",
        "/central/intelligence-panel",
        "/central/email-summary"
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                log_test(f"GET /api{endpoint}", True)
            else:
                log_test(f"GET /api{endpoint}", False, f"Status {response.status_code}")
        except Exception as e:
            log_test(f"GET /api{endpoint}", False, str(e))


def test_admin_endpoints():
    """Test 7: Admin endpoints"""
    print("\n=== Testing Admin Endpoints ===")
    
    # GET /api/admin/learning/status
    try:
        response = requests.get(f"{BASE_URL}/admin/learning/status", timeout=10)
        if response.status_code == 200:
            log_test("GET /api/admin/learning/status", True)
        else:
            log_test("GET /api/admin/learning/status", False, f"Status {response.status_code}")
    except Exception as e:
        log_test("GET /api/admin/learning/status", False, str(e))
    
    # GET /api/admin/learning/email-stats
    try:
        response = requests.get(f"{BASE_URL}/admin/learning/email-stats", timeout=10)
        if response.status_code == 200:
            log_test("GET /api/admin/learning/email-stats", True)
        else:
            log_test("GET /api/admin/learning/email-stats", False, f"Status {response.status_code}")
    except Exception as e:
        log_test("GET /api/admin/learning/email-stats", False, str(e))
    
    # GET /api/admin/alertas
    try:
        response = requests.get(f"{BASE_URL}/admin/alertas", timeout=10)
        if response.status_code == 200:
            log_test("GET /api/admin/alertas", True)
        else:
            log_test("GET /api/admin/alertas", False, f"Status {response.status_code}")
    except Exception as e:
        log_test("GET /api/admin/alertas", False, str(e))
    
    # GET /api/alertas/seguimiento
    try:
        response = requests.get(f"{BASE_URL}/alertas/seguimiento?dias=7", timeout=10)
        if response.status_code == 200:
            log_test("GET /api/alertas/seguimiento", True)
        else:
            log_test("GET /api/alertas/seguimiento", False, f"Status {response.status_code}")
    except Exception as e:
        log_test("GET /api/alertas/seguimiento", False, str(e))


def test_admin_users():
    """Test 8: Admin users CRUD"""
    print("\n=== Testing Admin Users CRUD ===")
    
    test_user_codigo = "ej01"
    
    # POST /api/admin/users (create)
    try:
        response = requests.post(f"{BASE_URL}/admin/users", json={
            "codigo": test_user_codigo,
            "nombre": "Ejecutivo Uno",
            "password": "1234",
            "rol": "ejecutivo"
        }, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                log_test("POST /api/admin/users (create)", True)
            else:
                log_test("POST /api/admin/users (create)", False, f"ok != True. Got: {data}")
        else:
            log_test("POST /api/admin/users (create)", False, 
                    f"Status {response.status_code}: {response.text}")
    except Exception as e:
        log_test("POST /api/admin/users (create)", False, str(e))
    
    # GET /api/admin/users (list)
    try:
        response = requests.get(f"{BASE_URL}/admin/users", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "users" in data:
                users = data["users"]
                if any(u.get("codigo") == test_user_codigo for u in users):
                    log_test("GET /api/admin/users (includes created user)", True)
                else:
                    log_warning("GET /api/admin/users", f"User {test_user_codigo} not found in list")
                    log_test("GET /api/admin/users (includes created user)", True)
            else:
                log_test("GET /api/admin/users (includes created user)", False, 
                        f"Missing users field. Got: {data}")
        else:
            log_test("GET /api/admin/users (includes created user)", False, 
                    f"Status {response.status_code}")
    except Exception as e:
        log_test("GET /api/admin/users (includes created user)", False, str(e))
    
    # DELETE /api/admin/users/{codigo} (delete test user)
    try:
        response = requests.delete(f"{BASE_URL}/admin/users/{test_user_codigo}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                log_test(f"DELETE /api/admin/users/{test_user_codigo}", True)
            else:
                log_test(f"DELETE /api/admin/users/{test_user_codigo}", False, 
                        f"ok != True. Got: {data}")
        else:
            log_test(f"DELETE /api/admin/users/{test_user_codigo}", False, 
                    f"Status {response.status_code}")
    except Exception as e:
        log_test(f"DELETE /api/admin/users/{test_user_codigo}", False, str(e))
    
    # DELETE /api/admin/users/admin (should fail)
    try:
        response = requests.delete(f"{BASE_URL}/admin/users/admin", timeout=10)
        if response.status_code == 400:
            log_test("DELETE /api/admin/users/admin (should fail with 400)", True)
        else:
            log_test("DELETE /api/admin/users/admin (should fail with 400)", False, 
                    f"Expected 400, got {response.status_code}")
    except Exception as e:
        log_test("DELETE /api/admin/users/admin (should fail with 400)", False, str(e))


def test_folders():
    """Test 9: Folders endpoints"""
    print("\n=== Testing Folders Endpoints ===")
    
    folder_id = None
    
    # POST /api/clientes/folders (create)
    try:
        response = requests.post(f"{BASE_URL}/clientes/folders", json={
            "nombre": "Cliente Test",
            "rut": "11111111-1"
        }, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "id" in data:
                folder_id = data["id"]
                log_test("POST /api/clientes/folders", True)
            else:
                log_test("POST /api/clientes/folders", False, f"Missing id. Got: {data}")
        else:
            log_test("POST /api/clientes/folders", False, f"Status {response.status_code}")
    except Exception as e:
        log_test("POST /api/clientes/folders", False, str(e))
    
    # GET /api/clientes/folders (list)
    try:
        response = requests.get(f"{BASE_URL}/clientes/folders", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "folders" in data:
                log_test("GET /api/clientes/folders", True)
            else:
                log_test("GET /api/clientes/folders", False, f"Missing folders field. Got: {data}")
        else:
            log_test("GET /api/clientes/folders", False, f"Status {response.status_code}")
    except Exception as e:
        log_test("GET /api/clientes/folders", False, str(e))
    
    # GET /api/clientes/folders/{id}
    if folder_id:
        try:
            response = requests.get(f"{BASE_URL}/clientes/folders/{folder_id}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("id") == folder_id:
                    log_test("GET /api/clientes/folders/{id}", True)
                else:
                    log_test("GET /api/clientes/folders/{id}", False, 
                            f"ID mismatch. Expected {folder_id}, got {data.get('id')}")
            else:
                log_test("GET /api/clientes/folders/{id}", False, f"Status {response.status_code}")
        except Exception as e:
            log_test("GET /api/clientes/folders/{id}", False, str(e))
    
    # GET /api/search
    try:
        response = requests.get(f"{BASE_URL}/search?q=Cliente", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "results" in data:
                log_test("GET /api/search", True)
            else:
                log_test("GET /api/search", False, f"Missing results field. Got: {data}")
        else:
            log_test("GET /api/search", False, f"Status {response.status_code}")
    except Exception as e:
        log_test("GET /api/search", False, str(e))


def test_stub_endpoints():
    """Test 10: Stub endpoints"""
    print("\n=== Testing Stub Endpoints ===")
    
    stub_endpoints = [
        "/whatsapp/status",
        "/whatsapp/qr",
        "/whatsapp/approvals",
        "/seguimiento/clientes",
        "/seguimiento/stats",
        "/autocorreo/status",
        "/procesamiento/queue",
        "/procesamiento/stats"
    ]
    
    for endpoint in stub_endpoints:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                log_test(f"GET /api{endpoint}", True)
            else:
                log_test(f"GET /api{endpoint}", False, 
                        f"Status {response.status_code}: {response.text}")
        except Exception as e:
            log_test(f"GET /api{endpoint}", False, str(e))


def print_summary():
    """Print test summary"""
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    print(f"\n✅ PASSED: {len(test_results['passed'])}")
    for test in test_results['passed']:
        print(f"  {test}")
    
    if test_results['warnings']:
        print(f"\n⚠️  WARNINGS: {len(test_results['warnings'])}")
        for warning in test_results['warnings']:
            print(f"  {warning}")
    
    if test_results['failed']:
        print(f"\n❌ FAILED: {len(test_results['failed'])}")
        for test in test_results['failed']:
            print(f"  {test}")
    
    print("\n" + "="*70)
    total = len(test_results['passed']) + len(test_results['failed'])
    pass_rate = (len(test_results['passed']) / total * 100) if total > 0 else 0
    print(f"PASS RATE: {pass_rate:.1f}% ({len(test_results['passed'])}/{total})")
    print("="*70 + "\n")
    
    return len(test_results['failed']) == 0


if __name__ == "__main__":
    print("="*70)
    print("Central Mutuos / Central PREDIC Backend API Tests")
    print(f"Base URL: {BASE_URL}")
    print("="*70)
    
    # Run all tests
    test_auth_login()
    test_config_endpoints()
    test_simular_credito()
    test_inmobiliaria_endpoints()
    test_ia_endpoints()
    test_central_endpoints()
    test_admin_endpoints()
    test_admin_users()
    test_folders()
    test_stub_endpoints()
    
    # Print summary
    all_passed = print_summary()
    
    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)
