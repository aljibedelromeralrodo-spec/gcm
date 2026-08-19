import requests

B = "http://localhost:8001/api"
def login(u, p): return requests.post(f"{B}/auth/login", json={"rut": u, "password": p}).json()
def H(t): return {"Authorization": f"Bearer {t}"}

A = login("administrador", "141617575")["token"]
G = login("gerencia", "Gerencia2026")["token"]
C = login("contralor", "Contralor2026")["token"]

# validador: postventa avanzar con texto normal debe pasar (no hay casos, prueba de import)
r = requests.get(f"{B}/postventa/panel", headers=H(login("postventa", "Postventa2026")["token"]))
print("postventa panel:", r.status_code)

# espejo sincronizar sin credenciales -> mensaje claro
r = requests.post(f"{B}/contralor/espejo/sincronizar", headers=H(C))
print("espejo sincronizar:", r.status_code, r.text[:200])
r = requests.get(f"{B}/contralor/espejo/operaciones", headers=H(C))
print("espejo operaciones (ultima_sync):", r.status_code, r.text[:200])

# gerencia accion con CC (debe pasar el validador — rol gerencia autorizado)
fid = None
rf = requests.get(f"{B}/gerencia-panel/command-center", headers=H(G))
ops = (rf.json().get("bandeja") or rf.json().get("operaciones") or []) if rf.status_code == 200 else []
print("command-center zonas:", list(rf.json().keys())[:10] if rf.status_code == 200 else rf.status_code)

# normativas list + fechas formato
r = requests.get(f"{B}/dashai/normativas", headers=H(A))
print("normativas total:", r.json().get("total"))
r = requests.get(f"{B}/broker/ventana-proyeccion", headers=H(login("broker1", "broker123")["token"]))
print("ventana (fecha con /):", r.json())
