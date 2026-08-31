"""Corte 13 autopiloto: DocumentosContador.js — badge contador de documentos faltantes de la tarjeta."""
import os
import shutil
import sys

MOD = "/app/frontend/src/pages/ClientesModule.js"
IDX = "/app/frontend/src/pages/clientes/index.js"
BAK = "/tmp/autopiloto_bak"

s = open(MOD).read()
START = "                  {missing.length > 0 && ("
END = "\n                  )}\n"
if START not in s or "DocumentosContador" in s:
    print("corte 13 no aplicable (marcador ausente o ya aplicado)")
    sys.exit(2)
ini = s.index(START)
fin = s.index(END, ini) + len(END)
bloque = s[ini:fin]
assert "Faltan:" in bloque

os.makedirs(BAK, exist_ok=True)
shutil.copy(MOD, f"{BAK}/ClientesModule.js")
shutil.copy(IDX, f"{BAK}/index.js")

uso = "                  <DocumentosContador missing={missing} />\n"
s = s[:ini] + uso + s[fin:]
s = s.replace(' } from "./clientes";', ', DocumentosContador } from "./clientes";')
open(MOD, "w").write(s)

lineas = [l[16:] if l.startswith(" " * 16) else l for l in bloque.rstrip("\n").split("\n")]
comp = ("// Corte 13 (autopiloto): contador rojo de documentos faltantes en la tarjeta\n"
        "const DocumentosContador = ({ missing }) => (\n"
        "  <>\n" + "\n".join(lineas) + "\n  </>\n);\n\nexport default DocumentosContador;\n")
open("/app/frontend/src/pages/clientes/DocumentosContador.js", "w").write(comp)
open(IDX, "a").write('export { default as DocumentosContador } from "./DocumentosContador";\n')
print(f"corte 13 DocumentosContador aplicado: {bloque.count(chr(10))} líneas movidas")
