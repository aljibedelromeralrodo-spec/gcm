import os, requests
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
PIN = os.environ["MASTER_PIN"]
B = "http://localhost:8001/api"
def login(u, p): return requests.post(f"{B}/auth/login", json={"rut": u, "password": p}).json()["token"]
def H(t): return {"Authorization": f"Bearer {t}"}
A = login("administrador", "141617575")
C = login("contralor", "Contralor2026")

print("── FLUJO EXPORTACIÓN ──")
r = requests.post(f"{B}/cerebro-export/verificar-pin", headers=H(A), json={"pin": "0000"})
print("PIN incorrecto →", r.status_code, r.json().get("detail", "")[:80])
assert r.status_code == 403
r = requests.post(f"{B}/cerebro-export/verificar-pin", headers=H(A), json={"pin": PIN})
print("PIN correcto →", r.status_code, r.json().get("mensaje", "")[:60]); assert r.status_code == 200
r = requests.post(f"{B}/cerebro-export/verificar-pin", headers=H(C), json={"pin": PIN})
print("contralor con PIN correcto →", r.status_code, "(esperado 403)"); assert r.status_code == 403

# pendiente: crear + eliminar normativa de prueba (ejercita hooks)
r = requests.post(f"{B}/dashai/normativas", headers=H(A), json={"clave": "TEST-EXPORT", "patron": "Normativa temporal de prueba del flujo de exportación."})
print("crear normativa test →", r.status_code, "| export_pendiente:", r.json().get("export_pendiente"))
r = requests.get(f"{B}/cerebro-export/estado", headers=H(A))
print("estado pendiente →", r.json().get("pendiente"), "| motivo:", r.json().get("motivo"))
assert r.json().get("pendiente") is True

# export JSON con PIN → limpia pendiente + archivo oficial
r = requests.get(f"{B}/cerebro-export/json", headers=H(A), params={"pin": PIN})
print("export JSON →", r.status_code, "| reglas:", r.json().get("total_reglas"), "| bytes:", len(r.content))
os.makedirs("/app/backend/exports", exist_ok=True)
open("/app/backend/exports/constitucion-oficial.json", "wb").write(r.content)
r2 = requests.get(f"{B}/cerebro-export/pdf", headers=H(A), params={"pin": PIN})
print("export PDF →", r2.status_code, "| bytes:", len(r2.content), "| tipo:", r2.headers.get("content-type"))
open("/app/backend/exports/constitucion-oficial.pdf", "wb").write(r2.content)
r = requests.get(f"{B}/cerebro-export/estado", headers=H(A))
print("pendiente tras exportar →", r.json().get("pendiente"), "| última:", r.json().get("ultima_export")[:16])
assert r.json().get("pendiente") is False

# limpiar normativa test (vuelve a marcar pendiente → re-exporto para dejar limpio)
r = requests.delete(f"{B}/dashai/normativas/TEST-EXPORT", headers=H(A))
print("eliminar normativa test →", r.status_code)
r = requests.get(f"{B}/cerebro-export/json", headers=H(A), params={"pin": PIN})
open("/app/backend/exports/constitucion-oficial.json", "wb").write(r.content)
print("re-export oficial →", r.status_code, "| reglas:", r.json().get("total_reglas"))

# auditoría registró intentos
r = requests.get(f"{B}/dashai/normativas/auditoria", headers=H(A))
regs = r.json().get("auditoria") or r.json().get("registros") or []
exp = [x for x in regs if x.get("accion") == "exportacion_constitucion"][:4]
print("── LOG AUDITORÍA (exportaciones) ──")
for x in exp:
    print(" ", x.get("fecha", "")[:16], x.get("resultado"), "-", (x.get("detalle") or "")[:60])
assert any(x.get("resultado") == "PIN_INCORRECTO" for x in exp), "falta registro de PIN incorrecto"
print("\n✅ PASO 1 + flujo exportación: TODO OK")
