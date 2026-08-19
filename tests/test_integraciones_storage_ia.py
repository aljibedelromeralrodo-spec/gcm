import requests, json, io

B = "http://localhost:8001/api"
def login(u, p): return requests.post(f"{B}/auth/login", json={"rut": u, "password": p}).json()
def H(t): return {"Authorization": f"Bearer {t}"}

A = login("administrador", "141617575")["token"]
BK = login("broker1", "broker123")["token"]
C = login("contralor", "Contralor2026")["token"]
V = login("victoria", "Victoria2026")["token"]

print("═══ 1. STORAGE: subida broker (dual write) ═══")
r = requests.post(f"{B}/broker/carpetas", headers=H(BK), json={"nombre": "QA STORAGE CLIENTE", "rut": "19.876.543-2"})
fid = r.json().get("id"); print("carpeta:", r.status_code, fid)
pdf = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\nxref\n0 4\ntrailer<</Size 4/Root 1 0 R>>\n%%EOF"
r = requests.post(f"{B}/broker/carpetas/{fid}/upload", headers=H(BK),
                  data={"subcarpeta": "06_solicitud"}, files={"archivo": ("test_qa.pdf", pdf, "application/pdf")})
print("upload broker:", r.status_code, r.text[:120])
import time; time.sleep(4)
r = requests.get(f"{B}/storage/docs", headers=H(BK), params={"fid": fid})
docs = r.json().get("documentos", []); print("storage docs broker:", r.status_code, len(docs))
assert docs, "FALLA: doc no llegó al storage"
did = docs[0]["id"]
r = requests.get(f"{B}/storage/ver/{did}", headers=H(BK))
print("ver inline broker:", r.status_code, r.headers.get("content-type"), r.headers.get("content-disposition", "")[:40], len(r.content), "bytes")
assert r.status_code == 200 and "inline" in r.headers.get("content-disposition", "")
# RBAC: otro broker no ve; contralor sí (lectura); victoria sí
r2 = requests.get(f"{B}/storage/ver/{did}", headers=H(login("broker", "Broker2026")["token"]))
print("otro broker ver →", r2.status_code, "(esperado 403)"); assert r2.status_code == 403
print("contralor ver →", requests.get(f"{B}/storage/ver/{did}", headers=H(C)).status_code, "(esperado 200)")

print("\n═══ 2. STORAGE: bandeja sin clasificar ═══")
r = requests.post(f"{B}/admin/docs-sin-clasificar/upload", headers=H(V),
                  files={"archivo": ("doc_bandeja_qa.pdf", pdf, "application/pdf")})
bid = r.json()["documento"]["id"]; print("upload bandeja:", r.status_code, bid)
time.sleep(3)
r = requests.get(f"{B}/storage/docs", headers=H(V), params={"bandeja": "1"})
bdocs = r.json().get("documentos", []); print("storage bandeja:", len(bdocs), [d["nombre_archivo"] for d in bdocs][:3])
r = requests.get(f"{B}/storage/ver/{bid}", headers=H(V))
print("ver bandeja (por bandeja_id):", r.status_code)
r = requests.get(f"{B}/storage/docs", headers=H(BK), params={"bandeja": "1"})
print("bandeja bloqueada a broker →", r.status_code, "(esperado 403)"); assert r.status_code == 403
# asignar a la carpeta → reclasificación en storage
r = requests.post(f"{B}/admin/docs-sin-clasificar/{bid}/asignar", headers=H(V), json={"fid": fid})
print("asignar:", r.status_code, r.text[:80])
r = requests.get(f"{B}/storage/docs", headers=H(A), params={"fid": fid})
print("docs de la operación tras asignar:", [d["nombre_archivo"] for d in r.json()["documentos"]])

print("\n═══ 3. CLAUDE: correo simulado URGENTE ═══")
r = requests.post(f"{B}/contralor/espejo/probar-ia", headers=H(A), json={
    "asunto": "Operación N° 78412 - Cliente QA STORAGE CLIENTE RUT 19.876.543-2 - OBSERVACIONES",
    "cuerpo": ("Estimados: la operación 78412 del cliente RUT 19.876.543-2 por UF 3.450 presenta "
               "observaciones. El plazo para regularizar el estudio de título VENCIÓ el 05/06/2026 y "
               "según la normativa vigente de la CMF el crédito no puede cursarse sin subsanar. "
               "Se requiere certificado de dominio vigente actualizado y aclaración de gravamen. "
               "De no resolverse esta semana la operación pasa a rechazo definitivo.")})
print("probar-ia:", r.status_code)
ia = r.json().get("analisis", {})
print("  urgente:", ia.get("urgente"), "| motivo:", (ia.get("motivo_urgencia") or "")[:90])
print("  nro:", ia.get("nro_operacion"), "| estado:", ia.get("estado"), "| monto:", ia.get("monto"))
print("  resumen:", (ia.get("resumen_interpretativo") or "")[:140])
print("  asignado_a:", r.json().get("asignado_a"))
assert r.status_code == 200 and ia.get("urgente") and ia.get("nro_operacion") == "78412"
# contralor NO puede probar
rr = requests.post(f"{B}/contralor/espejo/probar-ia", headers=H(C), json={"asunto": "x", "cuerpo": "y"})
print("contralor probar-ia →", rr.status_code, "(esperado 403)"); assert rr.status_code == 403
# operaciones muestran análisis IA
r = requests.get(f"{B}/contralor/espejo/operaciones", headers=H(C))
op = next((o for o in r.json()["operaciones"] if o["fid"] == fid), None)
print("op en dashboard contralor: urgente =", op and op["ia_urgente"], "| resumen presente =", bool(op and op["ia_resumen"]), "| analizado_en =", bool(op and op["ia_analizado_en"]))
assert op and op["ia_urgente"] and op["ia_resumen"]

print("\n═══ 4. CORRECCIÓN MANUAL DEL ADMIN ═══")
r = requests.post(f"{B}/contralor/espejo/operaciones/{fid}/ia-correccion", headers=H(A),
                  json={"estado": "En Estudio", "resumen_interpretativo": "Corregido por Admin: en revisión con abogado.", "urgente": False})
print("correccion admin:", r.status_code, r.text[:120])
rr = requests.post(f"{B}/contralor/espejo/operaciones/{fid}/ia-correccion", headers=H(C), json={"estado": "x"})
print("contralor corrige →", rr.status_code, "(esperado 403)"); assert rr.status_code == 403
r = requests.get(f"{B}/contralor/espejo/operaciones", headers=H(A))
op = next(o for o in r.json()["operaciones"] if o["fid"] == fid)
print("tras corrección: estado =", op["estado"], "| correccion =", op["ia_correccion"])
assert op["estado"] == "En Estudio" and op["ia_correccion"]

print("\n═══ 5. AUDITORÍA SEMANAL DE EFICIENCIA ═══")
r = requests.post(f"{B}/auditoria-eficiencia/ejecutar", headers=H(A))
aud = r.json().get("auditoria", {})
print("ejecutar:", r.status_code, "| resultado:", aud.get("resultado"), "| fallas:", aud.get("fallas"))
for cq in aud.get("checks", []):
    print(f"  {'✓' if cq['ok'] else '✗'} {cq['clave']}: {cq['detalle'][:90]}")
r = requests.get(f"{B}/auditoria-eficiencia", headers=H(A))
print("historial:", r.status_code, "| total:", r.json().get("total"), "| activa:", r.json().get("activa"))
rr = requests.get(f"{B}/auditoria-eficiencia", headers=H(C))
print("contralor historial →", rr.status_code, "(esperado 403)"); assert rr.status_code == 403
rr = requests.post(f"{B}/auditoria-eficiencia/config", headers=H(V), json={"activa": False})
print("victoria desactiva →", rr.status_code, "(esperado 403)"); assert rr.status_code == 403
r = requests.get(f"{B}/dashai/normativas", headers=H(A))
claves = [n["clave"] for n in r.json()["normativas"]]
print("normativa AUDITORÍA EFICIENCIA sembrada:", "AUDITORÍA EFICIENCIA" in claves, f"(total {len(claves)})")

print("\n═══ 6. ALERTA URGENTE creada ═══")
import subprocess
out = subprocess.run(["python3", "-c", """
from pymongo import MongoClient
db = MongoClient('mongodb://localhost:27017')['test_database']
a = db.alertas.find_one({'tipo':'espejo_urgente'}, sort=[('creado',-1)])
print('alerta:', bool(a), '|', (a or {}).get('titulo'), '| dest:', (a or {}).get('destinatarios'))
print('ia_log:', db.espejo_ia_log.count_documents({}))
"""], capture_output=True, text=True)
print(out.stdout, out.stderr[:200])
print("\n✅ TODO OK — limpiando datos QA…")
requests.delete(f"{B}/clientes/folders/{fid}", headers=H(A))
