"""Corte 11 autopiloto: MoraCMF.js — banner de morosidad CMF con link de pago y comprobantes."""
import os
import shutil
import sys

MOD = "/app/frontend/src/pages/ClientesModule.js"
IDX = "/app/frontend/src/pages/clientes/index.js"
BAK = "/tmp/autopiloto_bak"

s = open(MOD).read()
START = "                    {(f.cmf_morosidad?.morosidad_clp > 0) && ("
END = "\n                    )}\n"
if START not in s or "MoraCMF" in s:
    print("corte 11 no aplicable (marcador ausente o ya aplicado)")
    sys.exit(2)
ini = s.index(START)
fin = s.index(END, ini) + len(END)
bloque = s[ini:fin]
assert "mora-banner" in bloque and "subirComprobanteMora" in bloque

os.makedirs(BAK, exist_ok=True)
shutil.copy(MOD, f"{BAK}/ClientesModule.js")
shutil.copy(IDX, f"{BAK}/index.js")

uso = "                    <MoraCMF f={f} moraUp={moraUp} enviarLinkPagoMora={enviarLinkPagoMora} subirComprobanteMora={subirComprobanteMora} />\n"
s = s[:ini] + uso + s[fin:]
s = s.replace(' } from "./clientes";', ', MoraCMF } from "./clientes";')
open(MOD, "w").write(s)

lineas = [l[18:] if l.startswith(" " * 18) else l for l in bloque.rstrip("\n").split("\n")]
comp = ("// Corte 11 (autopiloto): banner de mora CMF con link de pago, comprobante y formulario\n"
        "const MoraCMF = ({ f, moraUp, enviarLinkPagoMora, subirComprobanteMora }) => (\n"
        "  <>\n" + "\n".join(lineas) + "\n  </>\n);\n\nexport default MoraCMF;\n")
open("/app/frontend/src/pages/clientes/MoraCMF.js", "w").write(comp)
open(IDX, "a").write('export { default as MoraCMF } from "./MoraCMF";\n')
print(f"corte 11 MoraCMF aplicado: {bloque.count(chr(10))} líneas movidas")
