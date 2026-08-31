"""Corte 12 autopiloto: NotificarNoCalifico.js — badge ⛔ NO CALIFICÓ + botón notificar al ejecutivo."""
import os
import shutil
import sys

MOD = "/app/frontend/src/pages/ClientesModule.js"
IDX = "/app/frontend/src/pages/clientes/index.js"
BAK = "/tmp/autopiloto_bak"

s = open(MOD).read()
START = "                      {evalNeg[f.id] && ("
END = "\n                      )}\n"
if START not in s or "NotificarNoCalifico" in s:
    print("corte 12 no aplicable (marcador ausente o ya aplicado)")
    sys.exit(2)
ini = s.index(START)
fin = s.index(END, ini) + len(END)
bloque = s[ini:fin]
assert "no-califico" in bloque and "notificarNoCalifico(f)" in bloque

os.makedirs(BAK, exist_ok=True)
shutil.copy(MOD, f"{BAK}/ClientesModule.js")
shutil.copy(IDX, f"{BAK}/index.js")

uso = "                      <NotificarNoCalifico f={f} evalNeg={evalNeg} notificandoNC={notificandoNC} notificarNoCalifico={notificarNoCalifico} />\n"
s = s[:ini] + uso + s[fin:]
s = s.replace(' } from "./clientes";', ', NotificarNoCalifico } from "./clientes";')
open(MOD, "w").write(s)

lineas = [l[20:] if l.startswith(" " * 20) else l for l in bloque.rstrip("\n").split("\n")]
comp = ("// Corte 12 (autopiloto): badge NO CALIFICÓ + notificación al ejecutivo\n"
        "const NotificarNoCalifico = ({ f, evalNeg, notificandoNC, notificarNoCalifico }) => (\n"
        "  <>\n" + "\n".join(lineas) + "\n  </>\n);\n\nexport default NotificarNoCalifico;\n")
open("/app/frontend/src/pages/clientes/NotificarNoCalifico.js", "w").write(comp)
open(IDX, "a").write('export { default as NotificarNoCalifico } from "./NotificarNoCalifico";\n')
print(f"corte 12 NotificarNoCalifico aplicado: {bloque.count(chr(10))} líneas movidas")
