import requests, json

B = "http://localhost:8001/api"
def login(u, p):
    r = requests.post(f"{B}/auth/login", json={"rut": u, "password": p})
    return (r.json() if r.status_code == 200 else {})
def H(t): return {"Authorization": f"Bearer {t}"}

A = login("administrador", "141617575")["token"]

# --- RUT DUPLICADO entre brokers ---
BK1 = login("broker1", "broker123").get("token")
r = requests.post(f"{B}/admin/users", headers=H(A), json={"nombre": "QA Broker2", "email": "qa.broker2@test.cl", "rol": "broker"})
d = r.json(); print("crear broker2:", r.status_code, "email_enviado:", d.get("email_enviado"), "nota:", d.get("nota", "")[:120])
clave, cod = d["clave_provisoria"], d["codigo"]
j = login(cod, clave); t2 = j["token"]
# completar primer ingreso completo
rc = requests.post(f"{B}/auth/primer-ingreso/clave", headers=H(t2), json={"clave_actual": clave, "clave_nueva": "QaBroker2026!", "confirmacion": "QaBroker2026!"})
print("primer-ingreso clave:", rc.status_code, rc.text[:100])
ri = requests.post(f"{B}/auth/primer-ingreso/imap", headers=H(t2), json={"servidor": "imap.gmail.com", "puerto": 993, "email": "qa.broker2@test.cl", "clave": "fakepass123"})
print("primer-ingreso imap:", ri.status_code, ri.text[:120])
j2 = login(cod, "QaBroker2026!")
print("re-login tras primer ingreso: first_login =", j2.get("first_login"))
t2 = j2["token"]

# broker1 crea carpeta con RUT X
r1 = requests.post(f"{B}/broker/carpetas" if False else f"{B}/clientes/folders", headers=H(login("broker1","broker123")["token"]), json={"nombre": "QA CLIENTE UNO", "rut": "11.111.111-1"})
print("broker1 crea RUT 11.111.111-1:", r1.status_code, r1.text[:100])
# broker2 intenta el mismo RUT
r2 = requests.post(f"{B}/clientes/folders", headers=H(t2), json={"nombre": "QA CLIENTE DUP", "rut": "11111111-1"})
print("broker2 mismo RUT →", r2.status_code, r2.text[:150])
assert r2.status_code == 409, "FALLA: no rechazó RUT duplicado"

# broker2 no ve carpeta de broker1 (aislamiento)
rb = requests.get(f"{B}/broker/carpetas", headers=H(t2))
print("broker/carpetas broker2:", rb.status_code, rb.text[:200])

# limpiar: borrar carpeta QA y usuario
fid = r1.json().get("id") if r1.status_code == 200 else None
if fid:
    rd = requests.delete(f"{B}/clientes/folders/{fid}", headers=H(A))
    print("carpeta QA eliminada:", rd.status_code)
rd = requests.delete(f"{B}/admin/users/{cod}", headers=H(A))
print("usuario QA eliminado:", rd.status_code)
