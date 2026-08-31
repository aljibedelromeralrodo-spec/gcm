"""Extrae valor de crédito de cada escriturado Ecomac y suma total. Salida: montos_escriturados.json"""
# ruff: noqa: F821, F403, F405
import json, re
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
import sys
sys.path.insert(0, "/app/backend")

from ecomac_datos_final import *  # noqa: F403

bodies = json.load(open("/app/backend/scripts_lacruz/esc_bodies.json")) + \
         json.load(open("/app/backend/scripts_lacruz/gerardo_bodies.json"))
for b in bodies:
    b["_blob"] = norm((b.get("subject", "") or "") + " " + (b.get("body", "") or ""))
    b["_blob_digits"] = re.sub(r"[.\-\s]", "", b["_blob"])

RX_UF = re.compile(r"(\d{1,2}(?:[.,]\d{3})+|\d{3,5})(?:[.,]\d{1,2})?\s*(?:uf|u\.f\.)|(?:uf|u\.f\.)\s*\$?\s*(\d{1,2}(?:[.,]\d{3})+|\d{3,5})", re.I)


def uf_val(s):
    try:
        return float(s.replace(".", "").replace(",", "."))
    except Exception:
        return None


def analizar(texto):
    t = norm(texto)
    vals = {"credito": [], "valor": [], "subsidio": [], "ahorro": [], "pie": [], "otros": []}
    for m in RX_UF.finditer(t):
        v = uf_val(m.group(1) or m.group(2))
        if not v:
            continue
        ctx = t[max(0, m.start() - 90):m.start()]
        if re.search(r"cr[e]dito|mutuo|hipotecari|monto a financiar|financiamiento", ctx) and 200 <= v <= 15000:
            vals["credito"].append(v)
        elif re.search(r"subsidio", ctx) and v <= 800:
            vals["subsidio"].append(v)
        elif re.search(r"ahorro", ctx) and v <= 800:
            vals["ahorro"].append(v)
        elif re.search(r"\bpie\b", ctx) and v <= 1500:
            vals["pie"].append(v)
        elif re.search(r"valor|precio|inmueble|departamento de|casa de|dpto de|propiedad", ctx) and 800 <= v <= 15000:
            vals["valor"].append(v)
        elif 800 <= v <= 15000:
            vals["otros"].append(v)
    return vals


def credito_de(vals):
    if vals["credito"]:
        return max(set(vals["credito"]), key=vals["credito"].count), "crédito explícito"
    if vals["valor"]:
        val = max(set(vals["valor"]), key=vals["valor"].count)
        desc = (vals["subsidio"][0] if vals["subsidio"] else 0) + \
               (vals["ahorro"][0] if vals["ahorro"] else 0) + (vals["pie"][0] if vals["pie"] else 0)
        if desc:
            return val - desc, f"valor {val:.0f} − pie/sub/ahorro {desc:.0f}"
        return val * 0.8, f"estimado 80% del valor {val:.0f}"
    if vals["otros"]:
        return max(set(vals["otros"]), key=vals["otros"].count) * 0.8, "estimado 80% de monto detectado"
    return None, ""


resultado = []
for cli, e in esc.items():
    rut = cli[4:] if cli.startswith("rut:") else None
    ct = set(cli.split()) if not rut else None
    agg = {"credito": [], "valor": [], "subsidio": [], "ahorro": [], "pie": [], "otros": []}
    for b in bodies:
        hit = False
        if rut and rut.split("-")[0] in b["_blob_digits"]:
            hit = True
        elif ct and len(ct & set(re.findall(r"[a-z\u00f1]+", b["_blob"][:300]))) >= 2:
            hit = True
        if not hit:
            continue
        v = analizar(b.get("body", "") or "")
        for k in agg:
            agg[k] += v[k]
    cred, fuente = credito_de(agg)
    top = max(e["etapas"])
    resultado.append({"cliente": nom_esc(cli), "etapa": ETIQ[top],
                      "fecha": e["etapas"][top].strftime("%d/%m/%y"),
                      "credito_uf": round(cred) if cred else None, "fuente": fuente})

con = [r for r in resultado if r["credito_uf"]]
sin = [r for r in resultado if not r["credito_uf"]]
tot = sum(r["credito_uf"] for r in con)
prom = tot / len(con)
est_total = tot + prom * len(sin)
UF = 40868.50
out = {"con_monto": sorted(con, key=lambda r: -r["credito_uf"]), "sin_monto": sin,
       "suma_uf_detectada": tot, "promedio_uf": prom, "estimado_total_uf": est_total,
       "uf_pesos": UF, "suma_pesos": tot * UF, "estimado_pesos": est_total * UF}
json.dump(out, open("/app/backend/scripts_lacruz/montos_escriturados.json", "w"), ensure_ascii=False, indent=1)

print(f"ESCRITURADOS: {len(resultado)} | con monto: {len(con)} | sin monto: {len(sin)}")
print(f"SUMA DETECTADA: UF {tot:,.0f}  (≈ ${tot*UF/1e9:,.2f} mil millones CLP a UF $40.868,50)")
print(f"PROMEDIO: UF {prom:,.0f} | ESTIMADO TOTAL (incl. sin monto a promedio): UF {est_total:,.0f} ≈ ${est_total*UF/1e9:,.2f} MM CLP")
print()
for r in out["con_monto"]:
    print(f"  UF {r['credito_uf']:>6,} | {r['etapa']:14s} | {r['fecha']} | {r['cliente'][:48]} | {r['fuente'][:40]}")
print()
print("SIN MONTO:")
for r in sin:
    print(f"      —   | {r['etapa']:14s} | {r['fecha']} | {r['cliente'][:52]}")
