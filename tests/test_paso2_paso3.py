import os, requests
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
PIN = os.environ["MASTER_PIN"]
B = "http://localhost:8001/api"
R = []
def chk(paso, nombre, ok, det=""):
    R.append((paso, nombre, ok))
    print(("✅" if ok else "⛔"), f"[{paso}]", nombre, ("- " + str(det)[:80]) if det and not ok else "")
def login(u, p):
    r = requests.post(f"{B}/auth/login", json={"rut": u, "password": p})
    return r.json().get("token")
def H(t): return {"Authorization": f"Bearer {t}"}

T = {r: login(u, p) for r, (u, p) in {
    "admin": ("administrador", "141617575"), "gerencia": ("gerencia", "Gerencia2026"),
    "administracion": ("victoria", "Victoria2026"), "postventa": ("postventa", "Postventa2026"),
    "contralor": ("contralor", "Contralor2026"), "broker": ("broker1", "broker123")}.items()}
A = T["admin"]

print("═══ PASO 2 — SEGURIDAD ═══")
for rol in ("gerencia", "contralor", "broker", "administracion", "postventa"):
    r = requests.post(f"{B}/dashai/normativas", headers=H(T[rol]), json={"clave": "X", "patron": "x"})
    chk("P2", f"{rol} NO modifica normativas (403)", r.status_code == 403, r.status_code)
    r = requests.get(f"{B}/dashai/normativas", headers=H(T[rol]))
    chk("P2", f"{rol} NO ve normativas (403)", r.status_code == 403, r.status_code)
    r = requests.get(f"{B}/dashai/catalogo-maestro", headers=H(T[rol]))
    chk("P2", f"{rol} NO ve catálogo (403)", r.status_code == 403, r.status_code)
    r = requests.get(f"{B}/cerebro-export/estado", headers=H(T[rol]))
    chk("P2", f"{rol} NO accede a exportación (403)", r.status_code == 403, r.status_code)
    r = requests.get(f"{B}/auditoria-eficiencia", headers=H(T[rol]))
    chk("P2", f"{rol} NO ve auditoría eficiencia (403)", r.status_code == 403, r.status_code)
r = requests.get(f"{B}/dashai/normativas")
chk("P2", "sin sesión bloqueado (401)", r.status_code == 401, r.status_code)
import subprocess
out = subprocess.run(["grep", "-rc", "0586", "/app/backend/constitucion.py", "/app/backend/email_service.py",
                      "/app/backend/server.py", "/app/backend/mesa_brain.py"], capture_output=True, text=True)
chk("P2", "PIN NO está en el código (solo env)", all(l.endswith(":0") for l in out.stdout.strip().split("\n")), out.stdout)
r = requests.get(f"{B}/dashai/normativas/auditoria", headers=H(A))
regs = r.json().get("auditoria") or r.json().get("registros") or []
chk("P2", "log de auditoría activo y registrando", len(regs) > 0, len(regs))

print("═══ PASO 3 — FUNCIONAL ═══")
r = requests.get(f"{B}/contralor/espejo", headers=H(T["contralor"]))
chk("P3", "Algoritmo Espejo: estado", r.status_code == 200, r.status_code)
r = requests.get(f"{B}/contralor/espejo/operaciones", headers=H(T["contralor"]))
chk("P3", "Algoritmo Espejo: operaciones + IA", r.status_code == 200 and "ia_resumen" in r.text, r.status_code)
r = requests.get(f"{B}/dashai/estado-cerebro", headers=H(A))
d = r.json()
chk("P3", "Cerebro: estado + autoridad suprema", r.status_code == 200 and d.get("autoridad_suprema"), r.status_code)
chk("P3", "Cerebro: constitución 83 inamovible/inviolable",
    d.get("constitucion_oficial", {}).get("total_archivadas") == 83 and
    d["constitucion_oficial"]["estado"] == "inamovible e inviolable", d.get("constitucion_oficial"))
r = requests.get(f"{B}/dashai/catalogo-maestro", headers=H(A))
chk("P3", "Cerebro: catálogo 83 reglas numeradas", r.json().get("total_reglas") == 83, r.json().get("total_reglas"))
r = requests.get(f"{B}/gerencia-panel/command-center", headers=H(T["gerencia"]))
chk("P3", "Gestión operaciones: Command Center", r.status_code == 200, r.status_code)
r = requests.get(f"{B}/postventa/panel", headers=H(T["postventa"]))
chk("P3", "Gestión operaciones: Postventa", r.status_code == 200, r.status_code)
r = requests.get(f"{B}/broker/carpetas", headers=H(T["broker"]))
chk("P3", "Carpetas por operación (broker)", r.status_code == 200, r.status_code)
r = requests.get(f"{B}/storage/docs", headers=H(T["broker"]))
chk("P3", "Storage documental por rol", r.status_code == 200, r.status_code)
r = requests.get(f"{B}/admin/docs-sin-clasificar", headers=H(T["administracion"]))
chk("P3", "Bandeja sin clasificar (administración)", r.status_code == 200, r.status_code)
chk("P3", "Dashboards por rol: 6/6 logins", all(T.values()), {k: bool(v) for k, v in T.items()})
r = requests.post(f"{B}/cerebro-export/verificar-pin", headers=H(A), json={"pin": PIN})
chk("P3", "Flujo exportación con PIN maestro", r.status_code == 200, r.status_code)
r = requests.post(f"{B}/auditoria-eficiencia/ejecutar", headers=H(A))
chk("P3", "Auditoría eficiencia: ejecuta y aprueba", r.json().get("auditoria", {}).get("resultado") == "aprobada",
    r.json().get("auditoria", {}).get("fallas"))

fallas = [x for x in R if not x[2]]
print(f"\n═══ RESULTADO: {len(R)-len(fallas)}/{len(R)} OK — {'SIN BRECHAS ✅' if not fallas else f'{len(fallas)} BRECHAS ⛔'} ═══")
for f in fallas: print("  ⛔", f[0], f[1])
