from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
import sys
sys.path.insert(0, "/app/backend")
from pathlib import Path
from pymongo import MongoClient
import os
import bunker
import folders_service as fsvc

db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
root = Path("/app/backend/storage/clientes")
info = {}
for f in db.folders.find({}, {"nombre": 1, "created_at": 1, "origen": 1}):
    info[fsvc.safe_name(f["nombre"])] = f

CORTE = "2026-08-22"
tot = 0
n_ok = n_skip = n_err = 0
for d in sorted(root.iterdir()):
    if not d.is_dir():
        continue
    f = info.get(d.name, {})
    creado = (f.get("created_at") or "")[:10]
    if f.get("origen") == "lacruz_auto" or (creado and creado >= CORTE):
        n_skip += 1
        continue
    r = bunker.archivar_prefijo(f"clientes/{d.name}")
    if r.get("ok"):
        tot += r["liberado"]
        n_ok += 1
        print(f"ARCHIVADA {d.name[:45]} | {r['liberado']/1048576:.1f}MB | subidos:{r['subidos']}", flush=True)
    else:
        n_err += 1
        print(f"OMITIDA {d.name[:45]} | {r.get('motivo')}", flush=True)
print(f"\nRESUMEN: archivadas {n_ok} | activas conservadas {n_skip} | errores {n_err} | LIBERADO {tot/1048576:.0f} MB")
