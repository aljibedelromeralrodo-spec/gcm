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
     "comando": "cd /app/frontend && PLAYWRIGHT_BROWSERS_PATH=/pw-browsers npx playwright test --reporter=list",
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
     "comando": "cd /app/frontend && PLAYWRIGHT_BROWSERS_PATH=/pw-browsers npx playwright test e2e/ficha-cliente.spec.js --reporter=list",
     "timeout": 300, "espera": 5},
    {"id": 7, "nombre": "CORTE 9 - CardContent tarjeta renderiza",
     "comando": "cd /app/frontend && PLAYWRIGHT_BROWSERS_PATH=/pw-browsers npx playwright test e2e/login-clientes.spec.js --reporter=list",
     "timeout": 200, "espera": 5},
    {"id": 8, "nombre": "CORTE 10 - ReparosAbogado modal",
     "comando": "cd /app/frontend && PLAYWRIGHT_BROWSERS_PATH=/pw-browsers npx playwright test e2e/login-clientes.spec.js --grep 'TEST REPAROS' --reporter=list",
     "timeout": 200, "espera": 5},
    {"id": 9, "nombre": "CIERRE - Docs", "comando": "echo ok", "timeout": 30, "espera": 0},
]


def ejecutar_todo_automatico():
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


if __name__ == "__main__":
    ejecutar_todo_automatico()
