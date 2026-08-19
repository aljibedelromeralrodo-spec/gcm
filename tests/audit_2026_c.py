import requests

B = "http://localhost:8001/api"
def login(u, p):
    r = requests.post(f"{B}/auth/login", json={"rut": u, "password": p})
    return r.json() if r.status_code == 200 else {}
def H(t): return {"Authorization": f"Bearer {t}"}

A = login("administrador", "141617575")["token"]
T1 = login("broker1", "broker123")["token"]

# broker2 temporal
r = requests.post(f"{B}/admin/users", headers=H(A), json={"nombre": "QA Broker2", "email": "qa.broker2b@test.cl", "rol": "broker"})
d = r.json(); cod, clave = d["codigo"], d["clave_provisoria"]
t = login(cod, clave)["token"]
requests.post(f"{B}/auth/primer-ingreso/clave", headers=H(t), json={"clave_actual": clave, "clave_nueva": "QaBroker2026!", "confirmacion": "QaBroker2026!"})
requests.post(f"{B}/auth/primer-ingreso/imap", headers=H(t), json={"servidor": "imap.gmail.com", "puerto": 993, "email": "qa.broker2b@test.cl", "clave": "x"})
T2 = login(cod, "QaBroker2026!")["token"]

# broker1 crea RUT
r1 = requests.post(f"{B}/broker/carpetas", headers=H(T1), json={"nombre": "QA CLIENTE UNO", "rut": "24.111.222-3"})
print("broker1 crea:", r1.status_code, r1.text[:120])
fid = r1.json().get("id")

# broker2 mismo RUT -> 409
r2 = requests.post(f"{B}/broker/carpetas", headers=H(T2), json={"nombre": "QA DUP", "rut": "24111222-3"})
print("broker2 RUT duplicado →", r2.status_code, r2.text[:150])
assert r2.status_code == 409

# aislamiento: broker2 no ve carpeta de broker1
rb = requests.get(f"{B}/broker/carpetas", headers=H(T2))
nombres = [c["nombre"] for c in rb.json().get("carpetas", [])]
print("broker2 ve:", nombres)
assert "QA CLIENTE UNO" not in nombres, "FALLA aislamiento"
rb1 = requests.get(f"{B}/broker/carpetas", headers=H(T1))
print("broker1 ve:", [c["nombre"] for c in rb1.json().get("carpetas", [])])

# contralor solo lectura sobre broker endpoints
C = login("contralor", "Contralor2026")["token"]
rc = requests.post(f"{B}/broker/carpetas", headers=H(C), json={"nombre": "X", "rut": "12.345.678-5"})
print("contralor intenta crear carpeta broker →", rc.status_code, rc.text[:100])

# limpiar
if fid:
    print("del carpeta:", requests.delete(f"{B}/clientes/folders/{fid}", headers=H(A)).status_code)
print("del usuario:", requests.delete(f"{B}/admin/users/{cod}", headers=H(A)).status_code)
print("\nTODO OK")
