"""MODO STANDALONE — activa SOLO el Cerebro (Contralor + DashAI) purgando los
datos privados de clientes. Para el receptor del Fork del Job
8f15b608-2c47-4131-9ef1-abcea57ac830.

Uso:  cd /app/backend && python brain_standalone_setup.py --activar
"""
import asyncio
import os
import sys
import json
import shutil
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")
from motor.motor_asyncio import AsyncIOMotorClient

# Colecciones con datos PRIVADOS del dueño original (se eliminan por completo)
PRIVADAS = ["folders", "seguimiento", "simulaciones", "prospectos", "compromisos",
            "perfiles_vuelo", "oportunidades", "capturas_autonomas", "users",
            "notas", "inmobiliarias", "fs.files", "fs.chunks"]


async def main():
    if "--activar" not in sys.argv:
        print(__doc__)
        print("Agregue --activar para ejecutar. Esto ELIMINA los datos de clientes "
              "e importa exports/brain_config_export.json (solo inteligencia).")
        return
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    for c in PRIVADAS:
        try:
            n = await db[c].count_documents({})
            await db[c].drop()
            print(f"— {c}: {n} documento(s) privado(s) eliminado(s)")
        except Exception as e:
            print(f"— {c}: {e}")
    stor = Path(__file__).parent / "storage" / "clientes"
    if stor.exists():
        shutil.rmtree(stor)
        print("— storage/clientes (archivos físicos) eliminado")
    exp = Path(__file__).parent.parent / "exports" / "brain_config_export.json"
    if not exp.exists():
        print("⚠ Falta exports/brain_config_export.json — genérelo con GET /api/brain/export (llave X-Brain-Key)")
        return
    data = json.loads(exp.read_text())
    crit = dict(data.get("boveda_criterios") or {})
    espj = dict(data.get("espejo_mesa_modelo") or {})
    crit["_key"] = "criterios"
    espj["_key"] = "espejo_mesa_modelo"
    await db.config.update_one({"_key": "criterios"}, {"$set": crit}, upsert=True)
    await db.config.update_one({"_key": "espejo_mesa_modelo"}, {"$set": espj}, upsert=True)
    casos = data.get("casos_entrenamiento_anonimizados") or []
    if casos:
        await db.limites_reales_mesa.delete_many({})
        await db.limites_reales_mesa.insert_many([dict(c) for c in casos])
    await db.config.update_one({"_key": "brain_standalone"}, {"$set": {
        "activo": True, "origen": data.get("job_id_origen"),
        "criterios_version": data.get("criterios_version")}}, upsert=True)
    print(f"🧠 Cerebro importado ({data.get('criterios_version')}, {len(casos)} casos anónimos) — MODO STANDALONE ACTIVO")
    print("Login admin: se regenera desde ADMIN_PASSWORD_1/2 de backend/.env (defina las suyas).")

asyncio.run(main())
