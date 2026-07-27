#!/usr/bin/env python3
"""
Backend test for Autocorreo Run Background Fix
Tests the new background processing implementation for POST /api/autocorreo/run
"""
import requests
import time
import sys
from datetime import datetime

# Backend URL from frontend/.env
BASE_URL = "https://risk-assess-17.preview.emergentagent.com/api"

def log(msg):
    """Log with timestamp"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def test_autocorreo_run_background():
    """
    Test the autocorreo/run endpoint with background processing.
    
    Expected behavior:
    1. POST /api/autocorreo/run responds FAST (< 15s) with 200 and {started: true, running: true, message: string}
    2. GET /api/autocorreo/status immediately shows running: true
    3. Calling run again while running returns {started: false, running: true, message: "Ya hay un procesamiento..."}
    4. After 90-120s, running returns to false with last_run and last_run_result
    5. Status structure includes: enabled, periodic_enabled, cutoff_iso, destination, sent, failed, total, recent
    """
    results = {
        "test_1_run_responds_fast": False,
        "test_2_status_shows_running": False,
        "test_3_duplicate_run_blocked": False,
        "test_4_running_completes": False,
        "test_5_status_structure_complete": False,
        "test_6_regression_login": False,
    }
    
    log("=" * 80)
    log("TEST 1: POST /api/autocorreo/run - Should respond FAST (< 15s)")
    log("=" * 80)
    
    try:
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/autocorreo/run", json={}, timeout=20)
        elapsed = time.time() - start_time
        
        log(f"Response time: {elapsed:.2f}s")
        log(f"Status code: {response.status_code}")
        
        if response.status_code != 200:
            log(f"❌ FAILED: Expected 200, got {response.status_code}")
            log(f"Response: {response.text}")
            return results
        
        data = response.json()
        log(f"Response data: {data}")
        
        # Check response structure
        if not isinstance(data.get("started"), bool):
            log(f"❌ FAILED: 'started' field missing or not boolean")
            return results
        
        if not isinstance(data.get("running"), bool):
            log(f"❌ FAILED: 'running' field missing or not boolean")
            return results
        
        if not isinstance(data.get("message"), str):
            log(f"❌ FAILED: 'message' field missing or not string")
            return results
        
        # Check response time
        if elapsed >= 15:
            log(f"❌ FAILED: Response took {elapsed:.2f}s, expected < 15s")
            return results
        
        # Check values
        if data.get("running") is not True:
            log(f"❌ FAILED: 'running' should be True, got {data.get('running')}")
            return results
        
        log(f"✅ PASSED: Run endpoint responded in {elapsed:.2f}s with correct structure")
        log(f"   started={data.get('started')}, running={data.get('running')}")
        log(f"   message='{data.get('message')}'")
        results["test_1_run_responds_fast"] = True
        
    except requests.exceptions.Timeout:
        log(f"❌ FAILED: Request timed out after 20s (expected < 15s)")
        return results
    except Exception as e:
        log(f"❌ FAILED: Exception: {e}")
        return results
    
    log("")
    log("=" * 80)
    log("TEST 2: GET /api/autocorreo/status - Should show running: true immediately")
    log("=" * 80)
    
    try:
        time.sleep(1)  # Brief pause
        response = requests.get(f"{BASE_URL}/autocorreo/status", timeout=10)
        
        if response.status_code != 200:
            log(f"❌ FAILED: Expected 200, got {response.status_code}")
            return results
        
        data = response.json()
        log(f"Status response: running={data.get('running')}, destination={data.get('destination')}")
        
        if data.get("running") is not True:
            log(f"❌ FAILED: 'running' should be True immediately after starting, got {data.get('running')}")
            return results
        
        log(f"✅ PASSED: Status shows running=True")
        results["test_2_status_shows_running"] = True
        
    except Exception as e:
        log(f"❌ FAILED: Exception: {e}")
        return results
    
    log("")
    log("=" * 80)
    log("TEST 3: POST /api/autocorreo/run again - Should block duplicate run")
    log("=" * 80)
    
    try:
        response = requests.post(f"{BASE_URL}/autocorreo/run", json={}, timeout=10)
        
        if response.status_code != 200:
            log(f"❌ FAILED: Expected 200, got {response.status_code}")
            return results
        
        data = response.json()
        log(f"Response: {data}")
        
        if data.get("started") is not False:
            log(f"❌ FAILED: 'started' should be False when already running, got {data.get('started')}")
            return results
        
        if data.get("running") is not True:
            log(f"❌ FAILED: 'running' should be True, got {data.get('running')}")
            return results
        
        if "en curso" not in data.get("message", "").lower():
            log(f"❌ FAILED: Message should indicate process in progress")
            return results
        
        log(f"✅ PASSED: Duplicate run correctly blocked")
        log(f"   started={data.get('started')}, running={data.get('running')}")
        log(f"   message='{data.get('message')}'")
        results["test_3_duplicate_run_blocked"] = True
        
    except Exception as e:
        log(f"❌ FAILED: Exception: {e}")
        return results
    
    log("")
    log("=" * 80)
    log("TEST 4: Poll status every 15s - Wait for running to become false")
    log("=" * 80)
    log("Expected: 90-120 seconds for completion")
    log("Will poll for up to 180 seconds (3 minutes)")
    
    max_wait = 180  # 3 minutes
    poll_interval = 15  # 15 seconds
    start_poll = time.time()
    running_became_false = False
    last_run_result = None
    
    try:
        while time.time() - start_poll < max_wait:
            elapsed_poll = time.time() - start_poll
            log(f"Polling status... (elapsed: {elapsed_poll:.0f}s)")
            
            response = requests.get(f"{BASE_URL}/autocorreo/status", timeout=10)
            if response.status_code != 200:
                log(f"⚠ Warning: Status returned {response.status_code}")
                time.sleep(poll_interval)
                continue
            
            data = response.json()
            running = data.get("running")
            last_run = data.get("last_run")
            last_run_result = data.get("last_run_result")
            
            log(f"  running={running}, last_run={last_run}")
            if last_run_result:
                log(f"  last_run_result={last_run_result}")
            
            if running is False:
                log(f"✅ Process completed after {elapsed_poll:.0f}s")
                running_became_false = True
                break
            
            time.sleep(poll_interval)
        
        if not running_became_false:
            log(f"❌ FAILED: Process still running after {max_wait}s")
            return results
        
        # Verify last_run_result structure
        if not last_run_result:
            log(f"❌ FAILED: last_run_result is missing")
            return results
        
        if "error" in last_run_result:
            log(f"⚠ Warning: Process completed with error: {last_run_result.get('error')}")
        
        # Check for expected fields (processed, sent, errors)
        if "processed" not in last_run_result and "error" not in last_run_result:
            log(f"❌ FAILED: last_run_result missing 'processed' field")
            return results
        
        if "processed" in last_run_result:
            log(f"✅ PASSED: Process completed successfully")
            log(f"   processed={last_run_result.get('processed')}, sent={last_run_result.get('sent')}, errors={last_run_result.get('errors', [])}")
            
            # Note: processed can be 0 if no new emails after cutoff
            if last_run_result.get("processed") == 0:
                log(f"   ℹ Note: processed=0 is valid (no new emails after cutoff line)")
        
        results["test_4_running_completes"] = True
        
    except Exception as e:
        log(f"❌ FAILED: Exception during polling: {e}")
        return results
    
    log("")
    log("=" * 80)
    log("TEST 5: Verify complete status structure")
    log("=" * 80)
    
    try:
        response = requests.get(f"{BASE_URL}/autocorreo/status", timeout=10)
        
        if response.status_code != 200:
            log(f"❌ FAILED: Expected 200, got {response.status_code}")
            return results
        
        data = response.json()
        
        required_fields = [
            "enabled", "periodic_enabled", "cutoff_iso", "destination",
            "sent", "failed", "total", "recent"
        ]
        
        missing_fields = []
        for field in required_fields:
            if field not in data:
                missing_fields.append(field)
        
        if missing_fields:
            log(f"❌ FAILED: Missing required fields: {missing_fields}")
            return results
        
        log(f"✅ PASSED: All required fields present")
        log(f"   enabled={data.get('enabled')}")
        log(f"   periodic_enabled={data.get('periodic_enabled')}")
        log(f"   cutoff_iso={data.get('cutoff_iso')}")
        log(f"   destination={data.get('destination')}")
        log(f"   sent={data.get('sent')}, failed={data.get('failed')}, total={data.get('total')}")
        log(f"   recent entries: {len(data.get('recent', []))}")
        
        results["test_5_status_structure_complete"] = True
        
    except Exception as e:
        log(f"❌ FAILED: Exception: {e}")
        return results
    
    log("")
    log("=" * 80)
    log("TEST 6: Regression - POST /api/auth/login")
    log("=" * 80)
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"codigo": "administrador", "password": "141617575"},
            timeout=10
        )
        
        if response.status_code != 200:
            log(f"❌ FAILED: Expected 200, got {response.status_code}")
            return results
        
        data = response.json()
        
        if "token" not in data or "rol" not in data:
            log(f"❌ FAILED: Missing token or rol in response")
            return results
        
        log(f"✅ PASSED: Login successful")
        log(f"   codigo={data.get('codigo')}, rol={data.get('rol')}")
        
        results["test_6_regression_login"] = True
        
    except Exception as e:
        log(f"❌ FAILED: Exception: {e}")
        return results
    
    return results


def main():
    log("Starting Autocorreo Run Background Tests")
    log(f"Backend URL: {BASE_URL}")
    log("")
    
    results = test_autocorreo_run_background()
    
    log("")
    log("=" * 80)
    log("TEST SUMMARY")
    log("=" * 80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_flag in results.items():
        status = "✅ PASSED" if passed_flag else "❌ FAILED"
        log(f"{status}: {test_name}")
    
    log("")
    log(f"Total: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        log("")
        log("🎉 ALL TESTS PASSED - Autocorreo run background fix is working correctly!")
        return 0
    else:
        log("")
        log("⚠ SOME TESTS FAILED - See details above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
