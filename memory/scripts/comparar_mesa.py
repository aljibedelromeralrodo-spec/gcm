import os, sys, asyncio, json, re
sys.path.insert(0, "/app/backend")
os.chdir("/app/backend")
from dotenv import load_dotenv; load_dotenv("/app/backend/.env")
import httpx
import folders_service as fsvc
import ocr_service
import ai_extract

API = "http://localhost:8001/api"
CLAVE = os.environ["CALC_MAX_CLAVE"]

CASOS = [
    ("Cristian Pavez", "aprobacion", 1800, False, 0),
    ("Franco Bahamondes", "aprobacion", 2150, True, 0),
    ("KEVIN MACAYA", "aprobacion", 1522.08, True, 0),
    ("NICOLAS SAAVEDRA", "aprobacion", 2856, False, 3571),
    ("ROLANDO RIVERA", "aprobacion", 1995.19, True, 0),
    ("Francisca Hernandez", "aprobacion", 2150, True, 0),
    ("JOHN DIAZ", "observacion", 1890, True, 2700),
    ("Yarelly Sandoval", "observacion", 2151, True, 0),
    ("GABRIELA ALEJANDRA BERRÍOS ROMERO", "observacion", 2330, True, 0),
    ("FABIÁN ESCALANTE", "observacion", 2000, True, 0),
]

def leer(nombre, pref, maxdocs):
    base = fsvc.folder_dir(nombre)
    out = []
    try:
        arch = [a for a in fsvc.scan_archivos(nombre) if a["subfolder"].startswith(pref)]
    except Exception:
        return out
    for a in sorted(arch, key=lambda x: x["nombre"], reverse=True)[:maxdocs]:
        try:
            raw = (base / a["ruta"]).read_bytes()
            t, _m = ocr_service.extraer_texto(raw, a["nombre"])
            if t and t.strip():
                out.append(t)
        except Exception:
            pass
    return out

async def caso(nombre, real, monto, subsidio, vprop):
    rentas, deudas, edades, rentas_cod = [], [], [], []
    for t in leer(nombre, "02_liq", 2):
        d = await ai_extract.extraer_datos_financieros(t, cliente=nombre)
        if d.get("renta_liquida"): rentas.append(float(d["renta_liquida"]))
        if d.get("edad"): edades.append(float(d["edad"]))
    for t in leer(nombre, "04_cmf", 1):
        d = await ai_extract.extraer_datos_financieros(t, cliente=nombre)
        v = float(d.get("deuda_cmf_total") or 0)
        if 0 < v < 500_000_000: deudas.append(v)
    for t in leer(nombre, "05_codeudor", 2):
        d = await ai_extract.extraer_datos_financieros(t, cliente=nombre)
        if d.get("renta_liquida"): rentas_cod.append(float(d["renta_liquida"]))
    renta = round(sum(rentas) / len(rentas)) if rentas else 0
    renta_cod = round(max(rentas_cod)) if rentas_cod else 0
    # (renta codeudor solo si distinta de la del titular)
    renta_cod = 0 if abs(renta_cod - renta) < 1000 else renta_cod
    deuda = max(deudas) if deudas else 0
    edad = int(edades[0]) if edades else 38
    if not renta:
        return {"cliente": nombre, "real": real, "error": "no se pudo leer renta de las liquidaciones"}
    payload = {"clave": CLAVE, "renta_titular": renta, "renta_codeudor": renta_cod,
               "edad_cliente": edad, "edad_codeudor": 38 if renta_cod else 0,
               "deuda_cmf_total": deuda, "plazo_anos": 25, "tipo_deudor": 1,
               "continuidad_laboral": True, "con_subsidio": subsidio,
               "credito_solicitado_uf": monto, "valor_propiedad_uf": vprop}
    async with httpx.AsyncClient(timeout=60) as cx:
        r = (await cx.post(f"{API}/calcmax/calcular", json=payload)).json()
    calc_viable = bool(r.get("credito_viable"))
    coincide = (real == "aprobacion" and calc_viable) or (real != "aprobacion" and True)
    return {"cliente": nombre, "real": real, "renta_leida": renta, "deuda_cmf_leida": deuda,
            "edad": edad, "solicitado_uf": monto,
            "max_uf_calculadora": r.get("credito_maximo_uf"),
            "viable_calculadora": calc_viable,
            "dividendo_final_clp": r.get("dividendo_final_clp"),
            "tasa": r.get("tasa_origen"),
            "observaciones": r.get("razones_rechazo") or [],
            "coincide_con_mesa": (real == "aprobacion") == calc_viable}

async def main():
    res = []
    for c in CASOS:
        print("procesando:", c[0], flush=True)
        try:
            res.append(await caso(*c))
        except Exception as e:
            res.append({"cliente": c[0], "real": c[1], "error": str(e)[:120]})
    json.dump(res, open("/app/memory/scripts/comparacion_mesa.json", "w"), ensure_ascii=False, indent=1)
    ok = sum(1 for r in res if r.get("coincide_con_mesa"))
    print(f"LISTO — coinciden {ok}/{len([r for r in res if 'error' not in r])}")

asyncio.run(main())
