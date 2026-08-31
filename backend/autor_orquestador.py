"""AUTOR ORQUESTADOR — ejecuta los bloques en automático: termina uno, espera, sigue solo.
Registra en autor_orquestador_log (NO en sistema_reparaciones_log, para no contaminar
la memoria viva de Martín con falsas líneas de oro). Retoma desde donde quedó."""
import os
import time
import subprocess
from datetime import datetime, timezone
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
client = MongoClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

BLOQUES = [
    {"id": 1, "nombre": "BLINDAJE - Tests E2E Playwright",
     "comando": "cd /app/frontend && PLAYWRIGHT_BROWSERS_PATH=/app/pw-browsers npx playwright test --reporter=list",
     "timeout": 600, "espera": 15},
    {"id": 2, "nombre": "CORTE - Lint split clientes",
     "comando": "cd /app/frontend && npx eslint src/pages/ClientesModule.js src/pages/clientes --max-warnings=50",
     "timeout": 180, "espera": 15},
    {"id": 3, "nombre": "MEMORIA VIVA - compile backend",
     "comando": "cd /app/backend && python3 -m py_compile martin_taller.py server.py",
     "timeout": 120, "espera": 10},
    {"id": 4, "nombre": "FRONTEND VIVO - dev server responde",
     "comando": "curl -s -o /dev/null -w '%{http_code}' http://localhost:3000 | grep -q 200",
     "timeout": 60, "espera": 10},
    {"id": 5, "nombre": "GUARDIAN - revision-vivo API",
     "comando": ("python3 -c \"import json,urllib.request as u; "
                 "req=u.Request('http://localhost:8001/api/auth/login',data=json.dumps({'rut':'administrador','password':'141617575'}).encode(),headers={'Content-Type':'application/json'}); "
                 "t=json.load(u.urlopen(req))['token']; "
                 "r=json.load(u.urlopen(u.Request('http://localhost:8001/api/martin/revision-vivo',headers={'Authorization':'Bearer '+t}))); "
                 "print(r); assert r['vivo'] and r['martin_taller'] and r['logica_humana']\""),
     "timeout": 90, "espera": 5},
    {"id": 6, "nombre": "CORTE ROWACTIONS - anti-polling",
     "comando": "cd /app/frontend && PLAYWRIGHT_BROWSERS_PATH=/app/pw-browsers npx playwright test e2e/ficha-cliente.spec.js --reporter=list",
     "timeout": 300, "espera": 5},
    {"id": 7, "nombre": "CORTE 9 - CardContent tarjeta renderiza",
     "comando": "cd /app/frontend && PLAYWRIGHT_BROWSERS_PATH=/app/pw-browsers npx playwright test e2e/login-clientes.spec.js --reporter=list",
     "timeout": 200, "espera": 5},
    {"id": 8, "nombre": "CORTE 10 - ReparosAbogado modal",
     "comando": "cd /app/frontend && PLAYWRIGHT_BROWSERS_PATH=/app/pw-browsers npx playwright test e2e/login-clientes.spec.js --grep 'TEST REPAROS' --reporter=list",
     "timeout": 200, "espera": 5},
    {"id": 9, "nombre": "CIERRE - Docs", "comando": "echo ok", "timeout": 30, "espera": 0},
]


def _autopiloto_falla(corte, motivo):
    import uuid as _uuid
    db.autor_config.update_one({"_id": "cortes"}, {"$set": {"autopiloto_activo": False, "corridas_verdes": 0}})
    db.autor_orquestador_log.insert_one({"bloque_id": 100 + corte["id"], "nombre": f"AUTOPILOTO corte {corte['nombre']}",
        "ok": False, "fecha": datetime.now(timezone.utc).isoformat(), "salida": motivo[-500:]})
    db.martin_fallas.update_one({"huella": f"autopiloto_c{corte['id']}"}, {"$set": {
        "id": str(_uuid.uuid4()), "tipo_falla": "autopiloto_corte_fallido", "huella": f"autopiloto_c{corte['id']}",
        "descripcion": f"Autopiloto corte {corte['nombre']}: {motivo[:300]}",
        "herramienta_recomendada": "reiniciar_parser_cron", "params": {},
        "estado": "pendiente", "created_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
    print(f"AUTOPILOTO: FALLA en corte {corte['nombre']} — autopiloto DETENIDO. {motivo[:200]}", flush=True)


def _autopiloto():
    """Si hay 3 corridas verdes seguidas y cortes en cola: corta, valida y revierte si sale rojo."""
    import sys
    import shutil
    cfg = db.autor_config.find_one({"_id": "cortes"}) or {}
    if not cfg.get("autopiloto_activo"):
        return
    verdes = cfg.get("corridas_verdes", 0) + 1
    db.autor_config.update_one({"_id": "cortes"}, {"$set": {"corridas_verdes": verdes}}, upsert=True)
    cola = cfg.get("cortes_pendientes") or []
    if not cola:
        print("AUTOPILOTO: cola vacía, nada que cortar", flush=True)
        return
    if verdes < 3:
        print(f"AUTOPILOTO: {verdes}/3 corridas verdes, esperando", flush=True)
        return
    corte = cola[0]
    if corte.get("riesgo") != "bajo":
        print(f"AUTOPILOTO: corte {corte['nombre']} es riesgo {corte.get('riesgo')} — requiere aprobación manual, en pausa", flush=True)
        return
    print(f"AUTOPILOTO: 3 verdes -> aplicando corte {corte['id']} {corte['nombre']}", flush=True)
    r = subprocess.run([sys.executable, f"/app/backend/autor_cortes/corte_{corte['id']}.py"],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        _autopiloto_falla(corte, "el script de corte no aplicó: " + (r.stdout + r.stderr)[-250:])
        return
    time.sleep(30)  # webpack recompila el corte
    val = subprocess.run(
        "cd /app/frontend && npx eslint src/pages/ClientesModule.js src/pages/clientes --max-warnings=50 "
        "&& PLAYWRIGHT_BROWSERS_PATH=/app/pw-browsers npx playwright test --reporter=list",
        shell=True, capture_output=True, text=True, timeout=700)
    lineas = sum(1 for _ in open("/app/frontend/src/pages/ClientesModule.js"))
    if val.returncode == 0:
        db.autor_config.update_one({"_id": "cortes"}, {"$set": {"corridas_verdes": 0},
                                                       "$pop": {"cortes_pendientes": -1}})
        db.autor_orquestador_log.insert_one({"bloque_id": 100 + corte["id"],
            "nombre": f"AUTOPILOTO corte {corte['nombre']}", "ok": True,
            "fecha": datetime.now(timezone.utc).isoformat(),
            "salida": f"corte aplicado y validado — ClientesModule {lineas} líneas"})
        print(f"AUTOPILOTO: corte {corte['nombre']} VERDE — ClientesModule {lineas} líneas", flush=True)
    else:
        shutil.copy("/tmp/autopiloto_bak/ClientesModule.js", "/app/frontend/src/pages/ClientesModule.js")
        shutil.copy("/tmp/autopiloto_bak/index.js", "/app/frontend/src/pages/clientes/index.js")
        _autopiloto_falla(corte, "tests fallaron tras el corte — REVERTIDO del backup: " + (val.stdout + val.stderr)[-250:])


def _esperar_frontend_listo(max_seg=300):
    """Tras despertar el pod, webpack tarda en compilar: espera a que el frontend responda antes de testear."""
    import urllib.request
    t0 = time.time()
    while time.time() - t0 < max_seg:
        try:
            if urllib.request.urlopen("http://localhost:3000", timeout=30).status == 200:
                print("frontend listo, arrancando bloques", flush=True)
                return True
        except Exception:
            pass
        time.sleep(10)
    print("frontend no respondió tras el calentamiento", flush=True)
    return False


def ejecutar_todo_automatico():
    _esperar_frontend_listo()
    estado = db.autor_estado.find_one({"_id": "progreso"}) or {"bloque_actual": 1}
    inicio = max(1, min(estado.get("bloque_actual", 1), len(BLOQUES)))
    db.autor_estado.update_one({"_id": "progreso"}, {"$set": {"corriendo": True,
        "inicio": datetime.now(timezone.utc).isoformat()}}, upsert=True)
    for bloque in BLOQUES[inicio - 1:]:
        print(f"--- BLOQUE {bloque['id']}: {bloque['nombre']} --- INICIANDO", flush=True)
        try:
            result = subprocess.run(bloque["comando"], shell=True, capture_output=True,
                                    text=True, timeout=bloque["timeout"])
            ok, salida = result.returncode == 0, (result.stdout + result.stderr)[-600:]
        except subprocess.TimeoutExpired:
            ok, salida = False, f"TIMEOUT tras {bloque['timeout']}s"
        db.autor_orquestador_log.insert_one({
            "bloque_id": bloque["id"], "nombre": bloque["nombre"], "ok": ok,
            "fecha": datetime.now(timezone.utc).isoformat(), "salida": salida})
        db.autor_estado.update_one({"_id": "progreso"}, {"$set": {
            "bloque_actual": bloque["id"] + 1 if ok else bloque["id"],
            "ultimo_ok": ok, "ultimo_nombre": bloque["nombre"]}}, upsert=True)
        if not ok:
            print(f"BLOQUE {bloque['id']} FALLÓ, se detiene\n{salida}", flush=True)
            db.autor_estado.update_one({"_id": "progreso"}, {"$set": {"corriendo": False}})
            try:
                import uuid as _uuid
                db.martin_fallas.update_one({"huella": f"autor_b{bloque['id']}"}, {"$set": {
                    "id": str(_uuid.uuid4()), "tipo_falla": "autor_fallo_nocturno",
                    "huella": f"autor_b{bloque['id']}",
                    "descripcion": f"AUTOR bloque {bloque['id']} ({bloque['nombre']}) falló: {salida[-300:]}",
                    "herramienta_recomendada": "reiniciar_parser_cron", "params": {},
                    "estado": "pendiente", "created_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
            except Exception:
                pass
            return
        print(f"BLOQUE {bloque['id']} OK -> espera {bloque['espera']}s y sigue solo...", flush=True)
        time.sleep(bloque["espera"])
    db.autor_estado.update_one({"_id": "progreso"}, {"$set": {"corriendo": False, "bloque_actual": 1,
        "completado_en": datetime.now(timezone.utc).isoformat()}})
    print("AUTOR: TODO TERMINADO AUTOMÁTICO", flush=True)
    _autopiloto()


if __name__ == "__main__":
    ejecutar_todo_automatico()
