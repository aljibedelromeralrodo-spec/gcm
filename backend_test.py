#!/usr/bin/env python3
"""
REGRESIÓN INTEGRAL COMPLETA - Central Mutuos Backend
Tests ALL backend endpoints per review request specifications
"""
import requests
import time
import json

# Backend URL from frontend/.env
BASE_URL = "https://risk-assess-17.preview.emergentagent.com/api"

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
# 1. AUTH
# ============================================================================
def test_auth():
    print_category("1. AUTH")
    
    # Test 1: administrador/141617575
    print("\n1.1 POST /api/auth/login with administrador/141617575")
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", 
                           json={"rut": "administrador", "password": "141617575"}, 
                           timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("rol") == "admin":
                log_result("AUTH", "Login administrador/141617575 → 200 rol=admin", True)
            else:
                log_result("AUTH", "Login administrador/141617575 → 200 rol=admin", False, f"rol={data.get('rol')}")
        else:
            log_result("AUTH", "Login administrador/141617575 → 200 rol=admin", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("AUTH", "Login administrador/141617575 → 200 rol=admin", False, str(e))
    
    # Test 2: admin/0586
    print("\n1.2 POST /api/auth/login with admin/0586")
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", 
                           json={"rut": "admin", "password": "0586"}, 
                           timeout=10)
        if resp.status_code == 200:
            log_result("AUTH", "Login admin/0586 → 200", True)
        else:
            log_result("AUTH", "Login admin/0586 → 200", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("AUTH", "Login admin/0586 → 200", False, str(e))
    
    # Test 3: Bad credentials
    print("\n1.3 POST /api/auth/login with bad credentials")
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", 
                           json={"rut": "admin", "password": "wrongpass"}, 
                           timeout=10)
        if resp.status_code == 401:
            log_result("AUTH", "Login bad credentials → 401", True)
        else:
            log_result("AUTH", "Login bad credentials → 401", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("AUTH", "Login bad credentials → 401", False, str(e))
    
    # Test 4: Inmobiliaria login
    print("\n1.4 POST /api/inmobiliaria/auth/login with demo/demo")
    try:
        resp = requests.post(f"{BASE_URL}/inmobiliaria/auth/login", 
                           json={"usuario": "demo", "password": "demo"}, 
                           timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok") == True:
                log_result("AUTH", "Inmobiliaria login demo/demo → ok:true", True)
            else:
                log_result("AUTH", "Inmobiliaria login demo/demo → ok:true", False, f"ok={data.get('ok')}")
        else:
            log_result("AUTH", "Inmobiliaria login demo/demo → ok:true", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("AUTH", "Inmobiliaria login demo/demo → ok:true", False, str(e))

# ============================================================================
# 2. CONFIG/DATOS
# ============================================================================
def test_config_datos():
    print_category("2. CONFIG/DATOS")
    
    # Test 1: GET /api/valor-uf
    print("\n2.1 GET /api/valor-uf")
    try:
        resp = requests.get(f"{BASE_URL}/valor-uf", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            valor_uf = data.get("valor_uf", 0)
            if valor_uf > 0:
                log_result("CONFIG", "GET /api/valor-uf → valor_uf>0", True, f"valor_uf={valor_uf}")
            else:
                log_result("CONFIG", "GET /api/valor-uf → valor_uf>0", False, f"valor_uf={valor_uf}")
        else:
            log_result("CONFIG", "GET /api/valor-uf → valor_uf>0", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("CONFIG", "GET /api/valor-uf → valor_uf>0", False, str(e))
    
    # Test 2: GET /api/admin/criterios
    print("\n2.2 GET /api/admin/criterios")
    try:
        resp = requests.get(f"{BASE_URL}/admin/criterios", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            has_btg = "btg_pactual" in data
            has_ameris = "ameris" in data
            has_params = "parametros_generales" in data
            if has_btg and has_ameris and has_params:
                btg = data.get("btg_pactual", {})
                has_con_subsidio = "con_subsidio" in btg
                has_sin_subsidio = "sin_subsidio" in btg
                has_castigos = "castigos_renta" in btg
                if has_con_subsidio and has_sin_subsidio and has_castigos:
                    log_result("CONFIG", "GET /api/admin/criterios → estructura completa", True)
                else:
                    log_result("CONFIG", "GET /api/admin/criterios → estructura completa", False, 
                             f"btg_pactual missing fields: con_subsidio={has_con_subsidio}, sin_subsidio={has_sin_subsidio}, castigos_renta={has_castigos}")
            else:
                log_result("CONFIG", "GET /api/admin/criterios → estructura completa", False, 
                         f"Missing: btg_pactual={has_btg}, ameris={has_ameris}, parametros_generales={has_params}")
        else:
            log_result("CONFIG", "GET /api/admin/criterios → estructura completa", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("CONFIG", "GET /api/admin/criterios → estructura completa", False, str(e))
    
    # Test 3: GET /api/inmobiliaria/config/tasas
    print("\n2.3 GET /api/inmobiliaria/config/tasas")
    try:
        resp = requests.get(f"{BASE_URL}/inmobiliaria/config/tasas", timeout=10)
        if resp.status_code == 200:
            log_result("CONFIG", "GET /api/inmobiliaria/config/tasas → 200", True)
        else:
            log_result("CONFIG", "GET /api/inmobiliaria/config/tasas → 200", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("CONFIG", "GET /api/inmobiliaria/config/tasas → 200", False, str(e))
    
    # Test 4: PUT /api/inmobiliaria/config/tasas
    print("\n2.4 PUT /api/inmobiliaria/config/tasas")
    try:
        resp = requests.put(f"{BASE_URL}/inmobiliaria/config/tasas", 
                          json={"tasa_anual": 0.0635}, 
                          timeout=10)
        if resp.status_code == 200:
            log_result("CONFIG", "PUT /api/inmobiliaria/config/tasas → 200", True)
        else:
            log_result("CONFIG", "PUT /api/inmobiliaria/config/tasas → 200", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("CONFIG", "PUT /api/inmobiliaria/config/tasas → 200", False, str(e))
    
    # Test 5: GET /api/inmobiliaria/config/seguros
    print("\n2.5 GET /api/inmobiliaria/config/seguros")
    try:
        resp = requests.get(f"{BASE_URL}/inmobiliaria/config/seguros", timeout=10)
        if resp.status_code == 200:
            log_result("CONFIG", "GET /api/inmobiliaria/config/seguros → 200", True)
        else:
            log_result("CONFIG", "GET /api/inmobiliaria/config/seguros → 200", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("CONFIG", "GET /api/inmobiliaria/config/seguros → 200", False, str(e))

# ============================================================================
# 3. SIMULADOR
# ============================================================================
def test_simulador():
    print_category("3. SIMULADOR")
    
    # Test 1: POST /api/simular-credito
    print("\n3.1 POST /api/simular-credito")
    try:
        payload = {
            "nombre_completo": "Regresion QA",
            "renta_titular": 1500000,
            "plazo_anos": 25,
            "tasa_anual": 0.0635,
            "valor_uf": 39842,
            "valor_propiedad_uf": 3000,
            "credito_solicitado_uf": 2400,
            "edad_cliente": 35,
            "tipo_deudor": 1,
            "continuidad_laboral": True
        }
        resp = requests.post(f"{BASE_URL}/simular-credito", json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            required_fields = ["capacidad_credito_uf", "eval_btg", "eval_ameris"]
            missing = [f for f in required_fields if f not in data]
            if not missing:
                log_result("SIMULADOR", "POST /api/simular-credito → 200 con campos requeridos", True)
            else:
                log_result("SIMULADOR", "POST /api/simular-credito → 200 con campos requeridos", False, 
                         f"Missing fields: {missing}")
        else:
            log_result("SIMULADOR", "POST /api/simular-credito → 200 con campos requeridos", False, 
                     f"Status {resp.status_code}")
    except Exception as e:
        log_result("SIMULADOR", "POST /api/simular-credito → 200 con campos requeridos", False, str(e))
    
    # Test 2: GET /api/simulaciones
    print("\n3.2 GET /api/simulaciones")
    try:
        resp = requests.get(f"{BASE_URL}/simulaciones", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            # Handle both list and {"simulaciones": [...]} formats
            sims = data if isinstance(data, list) else data.get("simulaciones", [])
            # Check if it includes the simulation we just created
            found = any(s.get("nombre_completo") == "Regresion QA" for s in sims)
            if found:
                log_result("SIMULADOR", "GET /api/simulaciones → incluye simulación creada", True)
            else:
                log_result("SIMULADOR", "GET /api/simulaciones → incluye simulación creada", False, 
                         "Simulation 'Regresion QA' not found in list")
        else:
            log_result("SIMULADOR", "GET /api/simulaciones → incluye simulación creada", False, 
                     f"Status {resp.status_code}")
    except Exception as e:
        log_result("SIMULADOR", "GET /api/simulaciones → incluye simulación creada", False, str(e))
    
    # Test 3: POST /api/simulacion/pdf
    print("\n3.3 POST /api/simulacion/pdf")
    try:
        payload = {
            "nombre_completo": "Regresion QA",
            "renta_titular": 1500000,
            "plazo_anos": 25,
            "tasa_anual": 0.0635,
            "valor_uf": 39842,
            "valor_propiedad_uf": 3000,
            "credito_solicitado_uf": 2400,
            "edad_cliente": 35,
            "tipo_deudor": 1,
            "continuidad_laboral": True
        }
        resp = requests.post(f"{BASE_URL}/simulacion/pdf", json=payload, timeout=10)
        if resp.status_code == 200:
            content_type = resp.headers.get("content-type", "")
            if "application/pdf" in content_type:
                log_result("SIMULADOR", "POST /api/simulacion/pdf → PDF", True)
            else:
                log_result("SIMULADOR", "POST /api/simulacion/pdf → PDF", False, 
                         f"content-type={content_type}")
        else:
            log_result("SIMULADOR", "POST /api/simulacion/pdf → PDF", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("SIMULADOR", "POST /api/simulacion/pdf → PDF", False, str(e))

# ============================================================================
# 4. IA
# ============================================================================
def test_ia():
    print_category("4. IA")
    
    # Test 1: POST /api/ia/predict
    print("\n4.1 POST /api/ia/predict")
    try:
        payload = {
            "renta_titular": 1500000,
            "plazo_anos": 25,
            "valor_propiedad_uf": 3000,
            "credito_solicitado_uf": 2400,
            "edad_cliente": 35
        }
        resp = requests.post(f"{BASE_URL}/ia/predict", json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            required_fields = ["probabilidad", "nivel", "score_btg", "score_ameris", "metricas", "sugerencias"]
            missing = [f for f in required_fields if f not in data]
            if not missing:
                log_result("IA", "POST /api/ia/predict → campos requeridos", True)
            else:
                log_result("IA", "POST /api/ia/predict → campos requeridos", False, f"Missing: {missing}")
        else:
            log_result("IA", "POST /api/ia/predict → campos requeridos", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("IA", "POST /api/ia/predict → campos requeridos", False, str(e))
    
    # Test 2: GET /api/ia/insights
    print("\n4.2 GET /api/ia/insights")
    try:
        resp = requests.get(f"{BASE_URL}/ia/insights", timeout=10)
        if resp.status_code == 200:
            log_result("IA", "GET /api/ia/insights → 200", True)
        else:
            log_result("IA", "GET /api/ia/insights → 200", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("IA", "GET /api/ia/insights → 200", False, str(e))
    
    # Test 3: POST /api/ai/analizar
    print("\n4.3 POST /api/ai/analizar")
    try:
        # First get a simulation result
        sim_payload = {
            "nombre_completo": "Regresion QA",
            "renta_titular": 1500000,
            "plazo_anos": 25,
            "tasa_anual": 0.0635,
            "valor_uf": 39842,
            "valor_propiedad_uf": 3000,
            "credito_solicitado_uf": 2400,
            "edad_cliente": 35,
            "tipo_deudor": 1,
            "continuidad_laboral": True
        }
        sim_resp = requests.post(f"{BASE_URL}/simular-credito", json=sim_payload, timeout=10)
        if sim_resp.status_code == 200:
            resultado = sim_resp.json()
            payload = {
                "resultado": resultado,
                "valor_uf": 39842
            }
            resp = requests.post(f"{BASE_URL}/ai/analizar", json=payload, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                required_fields = ["escenarios", "mejor_plazo", "recomendacion_ia"]
                missing = [f for f in required_fields if f not in data]
                if not missing:
                    escenarios = data.get("escenarios", [])
                    if len(escenarios) == 4:
                        log_result("IA", "POST /api/ai/analizar → escenarios(4), mejor_plazo, recomendacion_ia", True)
                    else:
                        log_result("IA", "POST /api/ai/analizar → escenarios(4), mejor_plazo, recomendacion_ia", False, 
                                 f"Expected 4 escenarios, got {len(escenarios)}")
                else:
                    log_result("IA", "POST /api/ai/analizar → escenarios(4), mejor_plazo, recomendacion_ia", False, 
                             f"Missing: {missing}")
            else:
                log_result("IA", "POST /api/ai/analizar → escenarios(4), mejor_plazo, recomendacion_ia", False, 
                         f"Status {resp.status_code}")
        else:
            log_result("IA", "POST /api/ai/analizar → escenarios(4), mejor_plazo, recomendacion_ia", False, 
                     "Failed to get simulation result first")
    except Exception as e:
        log_result("IA", "POST /api/ai/analizar → escenarios(4), mejor_plazo, recomendacion_ia", False, str(e))
    
    # Test 4: POST /api/ia/refresh-knowledge
    print("\n4.4 POST /api/ia/refresh-knowledge")
    try:
        resp = requests.post(f"{BASE_URL}/ia/refresh-knowledge", timeout=10)
        if resp.status_code == 200:
            log_result("IA", "POST /api/ia/refresh-knowledge → 200", True)
        else:
            log_result("IA", "POST /api/ia/refresh-knowledge → 200", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("IA", "POST /api/ia/refresh-knowledge → 200", False, str(e))

# ============================================================================
# 5. PREDIC INMOBILIARIA
# ============================================================================
def test_predic_inmobiliaria():
    print_category("5. PREDIC INMOBILIARIA")
    
    # Test 1: POST /api/inmobiliaria/predict
    print("\n5.1 POST /api/inmobiliaria/predict")
    try:
        payload = {
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
        resp = requests.post(f"{BASE_URL}/inmobiliaria/predict", json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            required_fields = ["viable", "central_score", "seguros", "eval_escenario_1"]
            missing = [f for f in required_fields if f not in data]
            if not missing:
                central_score = data.get("central_score", {})
                seguros = data.get("seguros", {})
                has_score = "score" in central_score
                has_risk_level = "risk_level" in central_score
                has_factors = "factors" in central_score
                has_dividendo_final = "dividendo_final" in seguros
                if has_score and has_risk_level and has_factors and has_dividendo_final:
                    log_result("PREDIC_INMOB", "POST /api/inmobiliaria/predict → estructura completa", True)
                else:
                    log_result("PREDIC_INMOB", "POST /api/inmobiliaria/predict → estructura completa", False, 
                             f"Missing subfields: score={has_score}, risk_level={has_risk_level}, factors={has_factors}, dividendo_final={has_dividendo_final}")
            else:
                log_result("PREDIC_INMOB", "POST /api/inmobiliaria/predict → estructura completa", False, 
                         f"Missing: {missing}")
        else:
            log_result("PREDIC_INMOB", "POST /api/inmobiliaria/predict → estructura completa", False, 
                     f"Status {resp.status_code}")
    except Exception as e:
        log_result("PREDIC_INMOB", "POST /api/inmobiliaria/predict → estructura completa", False, str(e))
    
    # Test 2: POST /api/inmobiliaria/calc-deuda
    print("\n5.2 POST /api/inmobiliaria/calc-deuda")
    try:
        payload = {
            "monto_credito_uf": 2000,
            "tasa_anual": 0.0635,
            "plazo_anos": 25
        }
        resp = requests.post(f"{BASE_URL}/inmobiliaria/calc-deuda", json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if "cuota_mensual" in data:
                log_result("PREDIC_INMOB", "POST /api/inmobiliaria/calc-deuda → cuota_mensual", True)
            else:
                log_result("PREDIC_INMOB", "POST /api/inmobiliaria/calc-deuda → cuota_mensual", False, 
                         "Missing cuota_mensual")
        else:
            log_result("PREDIC_INMOB", "POST /api/inmobiliaria/calc-deuda → cuota_mensual", False, 
                     f"Status {resp.status_code}")
    except Exception as e:
        log_result("PREDIC_INMOB", "POST /api/inmobiliaria/calc-deuda → cuota_mensual", False, str(e))
    
    # Test 3: POST /api/inmobiliaria/comparar-competidores
    print("\n5.3 POST /api/inmobiliaria/comparar-competidores")
    try:
        payload = {
            "monto_credito_uf": 2000,
            "plazo_anos": 25,
            "renta_fija": 1500000,
            "edad_cliente": 35
        }
        resp = requests.post(f"{BASE_URL}/inmobiliaria/comparar-competidores", json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            required_fields = ["competidores", "resumen", "mensaje_comercial"]
            missing = [f for f in required_fields if f not in data]
            if not missing:
                competidores = data.get("competidores", [])
                if len(competidores) == 6:
                    log_result("PREDIC_INMOB", "POST /api/inmobiliaria/comparar-competidores → competidores(6)", True)
                else:
                    log_result("PREDIC_INMOB", "POST /api/inmobiliaria/comparar-competidores → competidores(6)", False, 
                             f"Expected 6 competidores, got {len(competidores)}")
            else:
                log_result("PREDIC_INMOB", "POST /api/inmobiliaria/comparar-competidores → competidores(6)", False, 
                         f"Missing: {missing}")
        else:
            log_result("PREDIC_INMOB", "POST /api/inmobiliaria/comparar-competidores → competidores(6)", False, 
                     f"Status {resp.status_code}")
    except Exception as e:
        log_result("PREDIC_INMOB", "POST /api/inmobiliaria/comparar-competidores → competidores(6)", False, str(e))
    
    # Test 4: POST /api/inmobiliaria/leads
    print("\n5.4 POST /api/inmobiliaria/leads")
    try:
        payload = {
            "nombre": "Regresion QA Lead",
            "email": "qa@test.com",
            "telefono": "+56912345678",
            "mensaje": "Test lead"
        }
        resp = requests.post(f"{BASE_URL}/inmobiliaria/leads", json=payload, timeout=10)
        if resp.status_code == 200:
            log_result("PREDIC_INMOB", "POST /api/inmobiliaria/leads → 200", True)
        else:
            log_result("PREDIC_INMOB", "POST /api/inmobiliaria/leads → 200", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("PREDIC_INMOB", "POST /api/inmobiliaria/leads → 200", False, str(e))
    
    # Test 5: GET /api/inmobiliaria/mi-dashboard
    print("\n5.5 GET /api/inmobiliaria/mi-dashboard")
    try:
        resp = requests.get(f"{BASE_URL}/inmobiliaria/mi-dashboard", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            required_fields = ["total", "recientes", "leads"]
            missing = [f for f in required_fields if f not in data]
            if not missing:
                log_result("PREDIC_INMOB", "GET /api/inmobiliaria/mi-dashboard → total, recientes, leads", True)
            else:
                log_result("PREDIC_INMOB", "GET /api/inmobiliaria/mi-dashboard → total, recientes, leads", False, 
                         f"Missing: {missing}")
        else:
            log_result("PREDIC_INMOB", "GET /api/inmobiliaria/mi-dashboard → total, recientes, leads", False, 
                     f"Status {resp.status_code}")
    except Exception as e:
        log_result("PREDIC_INMOB", "GET /api/inmobiliaria/mi-dashboard → total, recientes, leads", False, str(e))
    
    # Test 6: GET /api/inmobiliaria/score-history/{nombre}
    print("\n5.6 GET /api/inmobiliaria/score-history/Regresion%20QA")
    try:
        resp = requests.get(f"{BASE_URL}/inmobiliaria/score-history/Regresion%20QA", timeout=10)
        if resp.status_code == 200:
            log_result("PREDIC_INMOB", "GET /api/inmobiliaria/score-history/{nombre} → 200", True)
        else:
            log_result("PREDIC_INMOB", "GET /api/inmobiliaria/score-history/{nombre} → 200", False, 
                     f"Status {resp.status_code}")
    except Exception as e:
        log_result("PREDIC_INMOB", "GET /api/inmobiliaria/score-history/{nombre} → 200", False, str(e))
    
    # Test 7: POST /api/inmobiliaria/export-pdf
    print("\n5.7 POST /api/inmobiliaria/export-pdf")
    try:
        payload = {
            "modo": "subsidio",
            "valor_propiedad_uf": 3000,
            "subsidio_uf": 500,
            "monto_credito_uf": 2000,
            "renta_fija": 1500000,
            "edad_cliente": 35,
            "plazo_anos": 25,
            "tipo_deudor": 1,
            "antiguedad_laboral_meses": 24,
            "continuidad_laboral": True
        }
        resp = requests.post(f"{BASE_URL}/inmobiliaria/export-pdf", json=payload, timeout=10)
        if resp.status_code == 200:
            content_type = resp.headers.get("content-type", "")
            if "application/pdf" in content_type:
                log_result("PREDIC_INMOB", "POST /api/inmobiliaria/export-pdf → PDF", True)
            else:
                log_result("PREDIC_INMOB", "POST /api/inmobiliaria/export-pdf → PDF", False, 
                         f"content-type={content_type}")
        else:
            log_result("PREDIC_INMOB", "POST /api/inmobiliaria/export-pdf → PDF", False, 
                     f"Status {resp.status_code}")
    except Exception as e:
        log_result("PREDIC_INMOB", "POST /api/inmobiliaria/export-pdf → PDF", False, str(e))
    
    # Test 8: POST /api/inmobiliaria/comparar-pdf
    print("\n5.8 POST /api/inmobiliaria/comparar-pdf")
    try:
        payload = {
            "monto_credito_uf": 2000,
            "plazo_anos": 25,
            "renta_fija": 1500000,
            "edad_cliente": 35
        }
        resp = requests.post(f"{BASE_URL}/inmobiliaria/comparar-pdf", json=payload, timeout=10)
        if resp.status_code == 200:
            content_type = resp.headers.get("content-type", "")
            if "application/pdf" in content_type:
                log_result("PREDIC_INMOB", "POST /api/inmobiliaria/comparar-pdf → PDF", True)
            else:
                log_result("PREDIC_INMOB", "POST /api/inmobiliaria/comparar-pdf → PDF", False, 
                         f"content-type={content_type}")
        else:
            log_result("PREDIC_INMOB", "POST /api/inmobiliaria/comparar-pdf → PDF", False, 
                     f"Status {resp.status_code}")
    except Exception as e:
        log_result("PREDIC_INMOB", "POST /api/inmobiliaria/comparar-pdf → PDF", False, str(e))
    
    # Test 9: GET /api/inmobiliaria/ia-config
    print("\n5.9 GET /api/inmobiliaria/ia-config")
    try:
        resp = requests.get(f"{BASE_URL}/inmobiliaria/ia-config", timeout=10)
        if resp.status_code == 200:
            log_result("PREDIC_INMOB", "GET /api/inmobiliaria/ia-config → 200", True)
        else:
            log_result("PREDIC_INMOB", "GET /api/inmobiliaria/ia-config → 200", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("PREDIC_INMOB", "GET /api/inmobiliaria/ia-config → 200", False, str(e))

# ============================================================================
# 6. CENTRAL/DASHBOARD
# ============================================================================
def test_central_dashboard():
    print_category("6. CENTRAL/DASHBOARD")
    
    # Test 1: GET /api/central/dashboard-batch
    print("\n6.1 GET /api/central/dashboard-batch")
    try:
        resp = requests.get(f"{BASE_URL}/central/dashboard-batch", timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            if "email_status" in data:
                email_status = data.get("email_status", {})
                if email_status.get("connected") == True:
                    log_result("CENTRAL", "GET /api/central/dashboard-batch → email_status.connected=true", True)
                else:
                    log_result("CENTRAL", "GET /api/central/dashboard-batch → email_status.connected=true", False, 
                             f"connected={email_status.get('connected')}")
            else:
                log_result("CENTRAL", "GET /api/central/dashboard-batch → email_status.connected=true", False, 
                         "Missing email_status")
        else:
            log_result("CENTRAL", "GET /api/central/dashboard-batch → email_status.connected=true", False, 
                     f"Status {resp.status_code}")
    except Exception as e:
        log_result("CENTRAL", "GET /api/central/dashboard-batch → email_status.connected=true", False, str(e))
    
    # Test 2: GET /api/central/intelligence-panel
    print("\n6.2 GET /api/central/intelligence-panel")
    try:
        resp = requests.get(f"{BASE_URL}/central/intelligence-panel", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if "tendencias" in data:
                log_result("CENTRAL", "GET /api/central/intelligence-panel → tendencias", True)
            else:
                log_result("CENTRAL", "GET /api/central/intelligence-panel → tendencias", False, 
                         "Missing tendencias")
        else:
            log_result("CENTRAL", "GET /api/central/intelligence-panel → tendencias", False, 
                     f"Status {resp.status_code}")
    except Exception as e:
        log_result("CENTRAL", "GET /api/central/intelligence-panel → tendencias", False, str(e))
    
    # Test 3: GET /api/central/email-summary?limit=5
    print("\n6.3 GET /api/central/email-summary?limit=5")
    try:
        resp = requests.get(f"{BASE_URL}/central/email-summary?limit=5", timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            # Handle both list and {"emails": [...]} formats
            emails = data if isinstance(data, list) else data.get("emails", [])
            if isinstance(emails, list) and len(emails) > 0:
                # Check first email has required fields
                first_email = emails[0]
                required_fields = ["from", "subject", "date"]
                missing = [f for f in required_fields if f not in first_email]
                if not missing:
                    log_result("CENTRAL", "GET /api/central/email-summary → emails reales", True)
                else:
                    log_result("CENTRAL", "GET /api/central/email-summary → emails reales", False, 
                             f"Missing fields in email: {missing}")
            else:
                log_result("CENTRAL", "GET /api/central/email-summary → emails reales", False, 
                         "Empty list or not a list")
        else:
            log_result("CENTRAL", "GET /api/central/email-summary → emails reales", False, 
                     f"Status {resp.status_code}")
    except Exception as e:
        log_result("CENTRAL", "GET /api/central/email-summary → emails reales", False, str(e))
    
    # Test 4: POST /api/central/chat
    print("\n6.4 POST /api/central/chat")
    try:
        payload = {
            "message": "hola",
            "session_id": "qa1"
        }
        resp = requests.post(f"{BASE_URL}/central/chat", json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            required_fields = ["response", "session_id"]
            missing = [f for f in required_fields if f not in data]
            if not missing:
                log_result("CENTRAL", "POST /api/central/chat → response + session_id", True)
            else:
                log_result("CENTRAL", "POST /api/central/chat → response + session_id", False, 
                         f"Missing: {missing}")
        else:
            log_result("CENTRAL", "POST /api/central/chat → response + session_id", False, 
                     f"Status {resp.status_code}")
    except Exception as e:
        log_result("CENTRAL", "POST /api/central/chat → response + session_id", False, str(e))

# ============================================================================
# 7. ADMIN
# ============================================================================
def test_admin():
    print_category("7. ADMIN")
    
    # Test 1: GET /api/admin/users
    print("\n7.1 GET /api/admin/users")
    try:
        resp = requests.get(f"{BASE_URL}/admin/users", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            # Handle both list and {"users": [...]} formats
            users_list = data if isinstance(data, list) else data.get("users", [])
            # Check if includes administrador and admin
            users = [u.get("codigo") for u in users_list]
            has_administrador = "administrador" in users
            has_admin = "admin" in users
            if has_administrador and has_admin:
                log_result("ADMIN", "GET /api/admin/users → incluye administrador y admin", True)
            else:
                log_result("ADMIN", "GET /api/admin/users → incluye administrador y admin", False, 
                         f"administrador={has_administrador}, admin={has_admin}")
        else:
            log_result("ADMIN", "GET /api/admin/users → incluye administrador y admin", False, 
                     f"Status {resp.status_code}")
    except Exception as e:
        log_result("ADMIN", "GET /api/admin/users → incluye administrador y admin", False, str(e))
    
    # Test 2: POST /api/admin/users (create test user)
    print("\n7.2 POST /api/admin/users (create qa99)")
    try:
        payload = {
            "codigo": "qa99",
            "nombre": "QA Test User",
            "password": "test123",
            "rol": "ejecutivo"
        }
        resp = requests.post(f"{BASE_URL}/admin/users", json=payload, timeout=10)
        if resp.status_code == 200:
            log_result("ADMIN", "POST /api/admin/users → create qa99", True)
        else:
            log_result("ADMIN", "POST /api/admin/users → create qa99", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("ADMIN", "POST /api/admin/users → create qa99", False, str(e))
    
    # Test 3: DELETE /api/admin/users/qa99
    print("\n7.3 DELETE /api/admin/users/qa99")
    try:
        resp = requests.delete(f"{BASE_URL}/admin/users/qa99", timeout=10)
        if resp.status_code == 200:
            log_result("ADMIN", "DELETE /api/admin/users/qa99 → 200", True)
        else:
            log_result("ADMIN", "DELETE /api/admin/users/qa99 → 200", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("ADMIN", "DELETE /api/admin/users/qa99 → 200", False, str(e))
    
    # Test 4: GET /api/admin/alertas
    print("\n7.4 GET /api/admin/alertas")
    try:
        resp = requests.get(f"{BASE_URL}/admin/alertas", timeout=10)
        if resp.status_code == 200:
            log_result("ADMIN", "GET /api/admin/alertas → 200", True)
        else:
            log_result("ADMIN", "GET /api/admin/alertas → 200", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("ADMIN", "GET /api/admin/alertas → 200", False, str(e))
    
    # Test 5: GET /api/admin/learning/status
    print("\n7.5 GET /api/admin/learning/status")
    try:
        resp = requests.get(f"{BASE_URL}/admin/learning/status", timeout=10)
        if resp.status_code == 200:
            log_result("ADMIN", "GET /api/admin/learning/status → 200", True)
        else:
            log_result("ADMIN", "GET /api/admin/learning/status → 200", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("ADMIN", "GET /api/admin/learning/status → 200", False, str(e))
    
    # Test 6: GET /api/admin/learning/email-stats
    print("\n7.6 GET /api/admin/learning/email-stats")
    try:
        resp = requests.get(f"{BASE_URL}/admin/learning/email-stats", timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("imap_status") == "conectado":
                log_result("ADMIN", "GET /api/admin/learning/email-stats → imap_status='conectado'", True)
            else:
                log_result("ADMIN", "GET /api/admin/learning/email-stats → imap_status='conectado'", False, 
                         f"imap_status={data.get('imap_status')}")
        else:
            log_result("ADMIN", "GET /api/admin/learning/email-stats → imap_status='conectado'", False, 
                     f"Status {resp.status_code}")
    except Exception as e:
        log_result("ADMIN", "GET /api/admin/learning/email-stats → imap_status='conectado'", False, str(e))
    
    # Test 7: GET /api/alertas/seguimiento?dias=7
    print("\n7.7 GET /api/alertas/seguimiento?dias=7")
    try:
        resp = requests.get(f"{BASE_URL}/alertas/seguimiento?dias=7", timeout=10)
        if resp.status_code == 200:
            log_result("ADMIN", "GET /api/alertas/seguimiento?dias=7 → 200", True)
        else:
            log_result("ADMIN", "GET /api/alertas/seguimiento?dias=7 → 200", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("ADMIN", "GET /api/alertas/seguimiento?dias=7 → 200", False, str(e))

# ============================================================================
# 8. CLIENTES/BÚSQUEDA
# ============================================================================
def test_clientes_busqueda():
    print_category("8. CLIENTES/BÚSQUEDA")
    
    folder_id = None
    
    # Test 1: POST /api/clientes/folders
    print("\n8.1 POST /api/clientes/folders")
    try:
        payload = {
            "nombre": "Regresion QA",
            "rut": "22.222.222-2"
        }
        resp = requests.post(f"{BASE_URL}/clientes/folders", json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if "id" in data:
                folder_id = data["id"]
                log_result("CLIENTES", "POST /api/clientes/folders → id", True, f"id={folder_id}")
            else:
                log_result("CLIENTES", "POST /api/clientes/folders → id", False, "Missing id")
        else:
            log_result("CLIENTES", "POST /api/clientes/folders → id", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("CLIENTES", "POST /api/clientes/folders → id", False, str(e))
    
    # Test 2: GET /api/clientes/folders (list)
    print("\n8.2 GET /api/clientes/folders")
    try:
        resp = requests.get(f"{BASE_URL}/clientes/folders", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            # Handle both list and {"folders": [...]} formats
            folders = data if isinstance(data, list) else data.get("folders", [])
            # Check if includes the folder we just created
            found = any(f.get("nombre") == "Regresion QA" for f in folders)
            if found:
                log_result("CLIENTES", "GET /api/clientes/folders → lista incluye creado", True)
            else:
                log_result("CLIENTES", "GET /api/clientes/folders → lista incluye creado", False, 
                         "Folder 'Regresion QA' not found")
        else:
            log_result("CLIENTES", "GET /api/clientes/folders → lista incluye creado", False, 
                     f"Status {resp.status_code}")
    except Exception as e:
        log_result("CLIENTES", "GET /api/clientes/folders → lista incluye creado", False, str(e))
    
    # Test 3: GET /api/clientes/folders/{id} (detail)
    if folder_id:
        print(f"\n8.3 GET /api/clientes/folders/{folder_id}")
        try:
            resp = requests.get(f"{BASE_URL}/clientes/folders/{folder_id}", timeout=10)
            if resp.status_code == 200:
                log_result("CLIENTES", "GET /api/clientes/folders/{id} → detalle", True)
            else:
                log_result("CLIENTES", "GET /api/clientes/folders/{id} → detalle", False, 
                         f"Status {resp.status_code}")
        except Exception as e:
            log_result("CLIENTES", "GET /api/clientes/folders/{id} → detalle", False, str(e))
    else:
        log_result("CLIENTES", "GET /api/clientes/folders/{id} → detalle", False, "No folder_id available")
    
    # Test 4: GET /api/search?q=Regresion
    print("\n8.4 GET /api/search?q=Regresion")
    try:
        resp = requests.get(f"{BASE_URL}/search?q=Regresion", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if "results" in data:
                log_result("CLIENTES", "GET /api/search?q=Regresion → results", True)
            else:
                log_result("CLIENTES", "GET /api/search?q=Regresion → results", False, "Missing results")
        else:
            log_result("CLIENTES", "GET /api/search?q=Regresion → results", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("CLIENTES", "GET /api/search?q=Regresion → results", False, str(e))
    
    # Test 5: GET /api/clientes/emails?limit=5
    print("\n8.5 GET /api/clientes/emails?limit=5")
    try:
        resp = requests.get(f"{BASE_URL}/clientes/emails?limit=5", timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            # Handle both list and {"emails": [...]} formats
            emails = data if isinstance(data, list) else data.get("emails", [])
            if isinstance(emails, list) and len(emails) > 0:
                log_result("CLIENTES", "GET /api/clientes/emails?limit=5 → emails reales", True)
            else:
                log_result("CLIENTES", "GET /api/clientes/emails?limit=5 → emails reales", False, 
                         "Empty list or not a list")
        else:
            log_result("CLIENTES", "GET /api/clientes/emails?limit=5 → emails reales", False, 
                     f"Status {resp.status_code}")
    except Exception as e:
        log_result("CLIENTES", "GET /api/clientes/emails?limit=5 → emails reales", False, str(e))
    
    # Test 6: DELETE /api/clientes/folders/{id}
    if folder_id:
        print(f"\n8.6 DELETE /api/clientes/folders/{folder_id}")
        try:
            resp = requests.delete(f"{BASE_URL}/clientes/folders/{folder_id}", timeout=10)
            if resp.status_code == 200:
                log_result("CLIENTES", "DELETE /api/clientes/folders/{id} → 200", True)
            else:
                log_result("CLIENTES", "DELETE /api/clientes/folders/{id} → 200", False, 
                         f"Status {resp.status_code}")
        except Exception as e:
            log_result("CLIENTES", "DELETE /api/clientes/folders/{id} → 200", False, str(e))
    else:
        log_result("CLIENTES", "DELETE /api/clientes/folders/{id} → 200", False, "No folder_id available")

# ============================================================================
# 9. SEGUIMIENTO
# ============================================================================
def test_seguimiento():
    print_category("9. SEGUIMIENTO")
    
    # Test 1: GET /api/seguimiento/clientes
    print("\n9.1 GET /api/seguimiento/clientes")
    try:
        resp = requests.get(f"{BASE_URL}/seguimiento/clientes", timeout=10)
        if resp.status_code == 200:
            log_result("SEGUIMIENTO", "GET /api/seguimiento/clientes → 200", True)
        else:
            log_result("SEGUIMIENTO", "GET /api/seguimiento/clientes → 200", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("SEGUIMIENTO", "GET /api/seguimiento/clientes → 200", False, str(e))
    
    # Test 2: GET /api/seguimiento/stats
    print("\n9.2 GET /api/seguimiento/stats")
    try:
        resp = requests.get(f"{BASE_URL}/seguimiento/stats", timeout=10)
        if resp.status_code == 200:
            log_result("SEGUIMIENTO", "GET /api/seguimiento/stats → 200", True)
        else:
            log_result("SEGUIMIENTO", "GET /api/seguimiento/stats → 200", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("SEGUIMIENTO", "GET /api/seguimiento/stats → 200", False, str(e))

# ============================================================================
# 10. AUTOCORREO
# ============================================================================
def test_autocorreo():
    print_category("10. AUTOCORREO")
    
    # Test 1: GET /api/autocorreo/status
    print("\n10.1 GET /api/autocorreo/status")
    try:
        resp = requests.get(f"{BASE_URL}/autocorreo/status", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            required_fields = ["enabled", "destination", "recent"]
            missing = [f for f in required_fields if f not in data]
            if not missing:
                log_result("AUTOCORREO", "GET /api/autocorreo/status → enabled/destination/recent", True)
            else:
                log_result("AUTOCORREO", "GET /api/autocorreo/status → enabled/destination/recent", False, 
                         f"Missing: {missing}")
        else:
            log_result("AUTOCORREO", "GET /api/autocorreo/status → enabled/destination/recent", False, 
                     f"Status {resp.status_code}")
    except Exception as e:
        log_result("AUTOCORREO", "GET /api/autocorreo/status → enabled/destination/recent", False, str(e))
    
    # Test 2: GET /api/autocorreo/mailboxes?probe=true
    print("\n10.2 GET /api/autocorreo/mailboxes?probe=true")
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
                    log_result("AUTOCORREO", "GET /api/autocorreo/mailboxes?probe=true → 2 cuentas auth_live=true", True)
                else:
                    log_result("AUTOCORREO", "GET /api/autocorreo/mailboxes?probe=true → 2 cuentas auth_live=true", False, 
                             "Not all accounts have auth_live=true")
            else:
                log_result("AUTOCORREO", "GET /api/autocorreo/mailboxes?probe=true → 2 cuentas auth_live=true", False, 
                         f"Expected 2 accounts, got {len(accounts) if isinstance(accounts, list) else 'not a list'}")
        else:
            log_result("AUTOCORREO", "GET /api/autocorreo/mailboxes?probe=true → 2 cuentas auth_live=true", False, 
                     f"Status {resp.status_code}")
    except Exception as e:
        log_result("AUTOCORREO", "GET /api/autocorreo/mailboxes?probe=true → 2 cuentas auth_live=true", False, str(e))
    
    # Test 3: GET /api/autocorreo/archive
    print("\n10.3 GET /api/autocorreo/archive")
    try:
        resp = requests.get(f"{BASE_URL}/autocorreo/archive", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if "folders" in data:
                log_result("AUTOCORREO", "GET /api/autocorreo/archive → folders", True)
            else:
                log_result("AUTOCORREO", "GET /api/autocorreo/archive → folders", False, "Missing folders")
        else:
            log_result("AUTOCORREO", "GET /api/autocorreo/archive → folders", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("AUTOCORREO", "GET /api/autocorreo/archive → folders", False, str(e))
    
    # Test 4: POST /api/autocorreo/toggle (enable)
    print("\n10.4 POST /api/autocorreo/toggle (enable)")
    try:
        resp = requests.post(f"{BASE_URL}/autocorreo/toggle", json={"enabled": True}, timeout=10)
        if resp.status_code == 200:
            log_result("AUTOCORREO", "POST /api/autocorreo/toggle (enable) → 200", True)
        else:
            log_result("AUTOCORREO", "POST /api/autocorreo/toggle (enable) → 200", False, 
                     f"Status {resp.status_code}")
    except Exception as e:
        log_result("AUTOCORREO", "POST /api/autocorreo/toggle (enable) → 200", False, str(e))
    
    # Test 5: POST /api/autocorreo/toggle (disable)
    print("\n10.5 POST /api/autocorreo/toggle (disable)")
    try:
        resp = requests.post(f"{BASE_URL}/autocorreo/toggle", json={"enabled": False}, timeout=10)
        if resp.status_code == 200:
            log_result("AUTOCORREO", "POST /api/autocorreo/toggle (disable) → 200", True)
        else:
            log_result("AUTOCORREO", "POST /api/autocorreo/toggle (disable) → 200", False, 
                     f"Status {resp.status_code}")
    except Exception as e:
        log_result("AUTOCORREO", "POST /api/autocorreo/toggle (disable) → 200", False, str(e))
    
    # Test 6: POST /api/autocorreo/cutoff/now
    print("\n10.6 POST /api/autocorreo/cutoff/now")
    try:
        resp = requests.post(f"{BASE_URL}/autocorreo/cutoff/now", timeout=10)
        if resp.status_code == 200:
            log_result("AUTOCORREO", "POST /api/autocorreo/cutoff/now → 200", True)
        else:
            log_result("AUTOCORREO", "POST /api/autocorreo/cutoff/now → 200", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("AUTOCORREO", "POST /api/autocorreo/cutoff/now → 200", False, str(e))
    
    # Test 7: POST /api/autocorreo/cutoff/clear
    print("\n10.7 POST /api/autocorreo/cutoff/clear")
    try:
        resp = requests.post(f"{BASE_URL}/autocorreo/cutoff/clear", timeout=10)
        if resp.status_code == 200:
            log_result("AUTOCORREO", "POST /api/autocorreo/cutoff/clear → 200", True)
        else:
            log_result("AUTOCORREO", "POST /api/autocorreo/cutoff/clear → 200", False, 
                     f"Status {resp.status_code}")
    except Exception as e:
        log_result("AUTOCORREO", "POST /api/autocorreo/cutoff/clear → 200", False, str(e))

# ============================================================================
# 11. PROCESAMIENTO
# ============================================================================
def test_procesamiento():
    print_category("11. PROCESAMIENTO")
    
    # Test 1: GET /api/procesamiento/stats
    print("\n11.1 GET /api/procesamiento/stats")
    try:
        resp = requests.get(f"{BASE_URL}/procesamiento/stats", timeout=10)
        if resp.status_code == 200:
            log_result("PROCESAMIENTO", "GET /api/procesamiento/stats → 200", True)
        else:
            log_result("PROCESAMIENTO", "GET /api/procesamiento/stats → 200", False, 
                     f"Status {resp.status_code}")
    except Exception as e:
        log_result("PROCESAMIENTO", "GET /api/procesamiento/stats → 200", False, str(e))
    
    # Test 2: GET /api/procesamiento/queue
    print("\n11.2 GET /api/procesamiento/queue")
    try:
        resp = requests.get(f"{BASE_URL}/procesamiento/queue", timeout=10)
        if resp.status_code == 200:
            log_result("PROCESAMIENTO", "GET /api/procesamiento/queue → 200", True)
        else:
            log_result("PROCESAMIENTO", "GET /api/procesamiento/queue → 200", False, 
                     f"Status {resp.status_code}")
    except Exception as e:
        log_result("PROCESAMIENTO", "GET /api/procesamiento/queue → 200", False, str(e))
    
    # Test 3: GET /api/procesamiento/rules
    print("\n11.3 GET /api/procesamiento/rules")
    try:
        resp = requests.get(f"{BASE_URL}/procesamiento/rules", timeout=10)
        if resp.status_code == 200:
            log_result("PROCESAMIENTO", "GET /api/procesamiento/rules → 200", True)
        else:
            log_result("PROCESAMIENTO", "GET /api/procesamiento/rules → 200", False, 
                     f"Status {resp.status_code}")
    except Exception as e:
        log_result("PROCESAMIENTO", "GET /api/procesamiento/rules → 200", False, str(e))
    
    # Test 4: GET /api/procesamiento/checklist
    print("\n11.4 GET /api/procesamiento/checklist")
    try:
        resp = requests.get(f"{BASE_URL}/procesamiento/checklist", timeout=10)
        if resp.status_code == 200:
            log_result("PROCESAMIENTO", "GET /api/procesamiento/checklist → 200", True)
        else:
            log_result("PROCESAMIENTO", "GET /api/procesamiento/checklist → 200", False, 
                     f"Status {resp.status_code}")
    except Exception as e:
        log_result("PROCESAMIENTO", "GET /api/procesamiento/checklist → 200", False, str(e))
    
    # Test 5: GET /api/oauth/drive/status
    print("\n11.5 GET /api/oauth/drive/status")
    try:
        resp = requests.get(f"{BASE_URL}/oauth/drive/status", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("configured") == True:
                log_result("PROCESAMIENTO", "GET /api/oauth/drive/status → configured=true", True)
            else:
                log_result("PROCESAMIENTO", "GET /api/oauth/drive/status → configured=true", False, 
                         f"configured={data.get('configured')}")
        else:
            log_result("PROCESAMIENTO", "GET /api/oauth/drive/status → configured=true", False, 
                     f"Status {resp.status_code}")
    except Exception as e:
        log_result("PROCESAMIENTO", "GET /api/oauth/drive/status → configured=true", False, str(e))
    
    # Test 6: GET /api/procesamiento/queue (get an item ID for next tests)
    print("\n11.6 GET /api/procesamiento/queue (get item for testing)")
    queue_item_id = None
    try:
        resp = requests.get(f"{BASE_URL}/procesamiento/queue", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            # Handle both list and {"rows": [...]} formats
            rows = data if isinstance(data, list) else data.get("rows", [])
            if isinstance(rows, list) and len(rows) > 0:
                queue_item_id = rows[0].get("id")
                print(f"   Found queue item: {queue_item_id}")
            else:
                print("   No queue items available for testing")
        else:
            print(f"   Failed to get queue items: {resp.status_code}")
    except Exception as e:
        print(f"   Error getting queue items: {e}")
    
    # Test 7: GET /api/procesamiento/queue/{id}
    if queue_item_id:
        print(f"\n11.7 GET /api/procesamiento/queue/{queue_item_id}")
        try:
            resp = requests.get(f"{BASE_URL}/procesamiento/queue/{queue_item_id}", timeout=10)
            if resp.status_code == 200:
                log_result("PROCESAMIENTO", "GET /api/procesamiento/queue/{id} → 200", True)
            else:
                log_result("PROCESAMIENTO", "GET /api/procesamiento/queue/{id} → 200", False, 
                         f"Status {resp.status_code}")
        except Exception as e:
            log_result("PROCESAMIENTO", "GET /api/procesamiento/queue/{id} → 200", False, str(e))
    else:
        log_result("PROCESAMIENTO", "GET /api/procesamiento/queue/{id} → 200", False, 
                 "No queue item available")
    
    # Test 8: GET /api/procesamiento/queue/{id}/validate
    if queue_item_id:
        print(f"\n11.8 GET /api/procesamiento/queue/{queue_item_id}/validate")
        try:
            resp = requests.get(f"{BASE_URL}/procesamiento/queue/{queue_item_id}/validate", timeout=10)
            if resp.status_code == 200:
                log_result("PROCESAMIENTO", "GET /api/procesamiento/queue/{id}/validate → 200", True)
            else:
                log_result("PROCESAMIENTO", "GET /api/procesamiento/queue/{id}/validate → 200", False, 
                         f"Status {resp.status_code}")
        except Exception as e:
            log_result("PROCESAMIENTO", "GET /api/procesamiento/queue/{id}/validate → 200", False, str(e))
    else:
        log_result("PROCESAMIENTO", "GET /api/procesamiento/queue/{id}/validate → 200", False, 
                 "No queue item available")

# ============================================================================
# 12. WHATSAPP (stubs)
# ============================================================================
def test_whatsapp():
    print_category("12. WHATSAPP (stubs)")
    
    # Test 1: GET /api/whatsapp/status
    print("\n12.1 GET /api/whatsapp/status")
    try:
        resp = requests.get(f"{BASE_URL}/whatsapp/status", timeout=10)
        if resp.status_code == 200:
            log_result("WHATSAPP", "GET /api/whatsapp/status → 200", True)
        else:
            log_result("WHATSAPP", "GET /api/whatsapp/status → 200", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("WHATSAPP", "GET /api/whatsapp/status → 200", False, str(e))
    
    # Test 2: GET /api/whatsapp/qr
    print("\n12.2 GET /api/whatsapp/qr")
    try:
        resp = requests.get(f"{BASE_URL}/whatsapp/qr", timeout=10)
        if resp.status_code == 200:
            log_result("WHATSAPP", "GET /api/whatsapp/qr → 200", True)
        else:
            log_result("WHATSAPP", "GET /api/whatsapp/qr → 200", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("WHATSAPP", "GET /api/whatsapp/qr → 200", False, str(e))
    
    # Test 3: GET /api/whatsapp/approvals
    print("\n12.3 GET /api/whatsapp/approvals")
    try:
        resp = requests.get(f"{BASE_URL}/whatsapp/approvals", timeout=10)
        if resp.status_code == 200:
            log_result("WHATSAPP", "GET /api/whatsapp/approvals → 200", True)
        else:
            log_result("WHATSAPP", "GET /api/whatsapp/approvals → 200", False, f"Status {resp.status_code}")
    except Exception as e:
        log_result("WHATSAPP", "GET /api/whatsapp/approvals → 200", False, str(e))

# ============================================================================
# MAIN
# ============================================================================
def main():
    print("\n" + "="*80)
    print("REGRESIÓN INTEGRAL COMPLETA - Central Mutuos Backend")
    print("="*80)
    print(f"Backend URL: {BASE_URL}")
    print("="*80)
    
    # Run all tests
    test_auth()
    test_config_datos()
    test_simulador()
    test_ia()
    test_predic_inmobiliaria()
    test_central_dashboard()
    test_admin()
    test_clientes_busqueda()
    test_seguimiento()
    test_autocorreo()
    test_procesamiento()
    test_whatsapp()
    
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
    print(f"Success rate: {total_passed / (total_passed + total_failed) * 100:.1f}%")
    print("="*80)
    
    # Return exit code
    return 0 if total_failed == 0 else 1

if __name__ == "__main__":
    exit(main())
