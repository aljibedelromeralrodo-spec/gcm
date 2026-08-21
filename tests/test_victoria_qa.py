import io
import json
import requests
from reportlab.pdfgen import canvas

BASE = "http://localhost:8001/api"
tok = requests.post(f"{BASE}/auth/login", json={"rut": "administrador", "password": "141617575"}).json()["token"]
H = {"Authorization": f"Bearer {tok}"}


def pdf(lineas):
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 780
    for ln in lineas:
        c.drawString(60, y, ln)
        y -= 22
    c.save()
    return buf.getvalue()


r = requests.post(f"{BASE}/victoria/clientes", headers=H,
                  json={"nombre": "CLIENTE PRUEBA VICTORIA QA", "rut": "12.345.678-5"}).json()
CID = r["cliente"]["id"]
print("cliente:", CID)

docs = {
    "tasacion": ["INFORME DE TASACION - Value Property", "Cliente: CLIENTE PRUEBA VICTORIA QA",
                 "RUT: 12.345.678-5", "Rol de Avaluo Fiscal: 1234-56",
                 "Direccion de la propiedad: Av Las Condes 1234, Santiago",
                 "Fecha de emision: 01/08/2026", "Firmado electronicamente por el tasador"],
    "titulos": ["ESTUDIO DE TITULOS - AMV Abogados", "Comprador: CLIENTE PRUEBA VICTORIA QA",
                "RUT: 12.345.678-5", "Rol de Avaluo: 1234-56",
                "Inmueble ubicado en: Av Providencia 999, Santiago",  # ← DIRECCIÓN DISTINTA (debe bloquear)
                "Fecha: 05/08/2026", "Firmado por el abogado Guillermo Majluf"],
    "carpeta_credito": ["CARPETA DE CREDITO / SET HIPOTECARIO", "Deudor: CLIENTE PRUEBA VICTORIA QA",
                        "RUT: 12.345.678-5", "Codeudor RUT: 9.876.543-3",
                        "Fecha: 10/08/2026", "Firma del deudor"],
    "simulacion": ["SIMULACION DE CREDITO HIPOTECARIO", "Cliente: CLIENTE PRUEBA VICTORIA QA",
                   "RUT: 12.345.678-5", "Monto credito: UF 1800", "Fecha: 12/08/2026"],
}
for tipo, lineas in docs.items():
    rr = requests.post(f"{BASE}/victoria/clientes/{CID}/subir", headers=H,
                       files={"file": (f"{tipo}_qa.pdf", pdf(lineas), "application/pdf")},
                       data={"tipo": tipo}, timeout=120).json()
    print("subido", tipo, "->", rr.get("ok"), "| datos:", {k: v for k, v in (rr.get("doc", {}).get("datos") or {}).items() if k in ("rut_titular", "rol_avaluo", "direccion_propiedad", "fecha_documento", "firmado")})

det = requests.get(f"{BASE}/victoria/clientes/{CID}", headers=H).json()
aud = det["auditoria"]
print("\nBLOQUEADO:", aud["bloqueado"])
for x in aud["coincidencias"]:
    print(" COIN:", x["ok"], "|", x["regla"][:60], "|", x["detalle"][:110])
for a in aud["alertas"][:6]:
    print(" ALERTA:", a["nivel"], "|", a["detalle"][:110])

# despacho debe FALLAR bloqueado
requests.put(f"{BASE}/victoria/clientes/{CID}/formularios", headers=H,
             json={"datos": det["formularios_auto"], "confirmado": True})
r = requests.post(f"{BASE}/victoria/clientes/{CID}/despachar", headers=H, json={"confirmado": True})
print("\ndespacho con mismatch (debe 403):", r.status_code, r.json().get("detail", "")[:140])
