"""Repara archivos INFNOMAT mal clasificados como CMF: los mueve a 99_otros."""
import asyncio, os, shutil
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import pdfplumber

load_dotenv()
CLIENTES = Path(__file__).parent / "storage" / "clientes"


def es_no_matrimonio(path):
    if "INFNOMAT" in path.name.upper():
        return True
    try:
        with pdfplumber.open(path) as pdf:
            txt = (pdf.pages[0].extract_text() or "").lower()
        return "no matrimonio" in txt or "acuerdo de unión civil" in txt
    except Exception:
        return False


async def main():
    client = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = client[os.environ['DB_NAME']]
    movidos = []
    for carpeta in CLIENTES.iterdir():
        cmf_dir = carpeta / "04_cmf"
        if not cmf_dir.is_dir():
            continue
        for f in list(cmf_dir.glob("*.pdf")):
            if es_no_matrimonio(f):
                dest_dir = carpeta / "99_otros"
                dest_dir.mkdir(exist_ok=True)
                dest = dest_dir / f.name
                shutil.move(str(f), str(dest))
                movidos.append((carpeta.name, f.name))
                # borrar combinados obsoletos para que se regeneren
                for m in list(carpeta.glob("COMBINADO*")) + list(carpeta.glob("Carpeta_*")):
                    m.unlink(missing_ok=True)
                # actualizar lista de archivos en Mongo
                doc = await db.folders.find_one({"archivos": {"$regex": f.name.replace('.', r'\.')}})
                if doc:
                    nuevos = []
                    for a in doc.get("archivos", []):
                        if f.name in a:
                            nuevos.append(f"99_otros/{f.name}")
                        elif a.startswith("Carpeta_") or a.startswith("COMBINADO"):
                            continue
                        else:
                            nuevos.append(a)
                    await db.folders.update_one({"id": doc["id"]}, {"$set": {"archivos": nuevos}})
    for c, n in movidos:
        print(f"MOVIDO: {c} :: 04_cmf/{n} -> 99_otros/{n}")
    print(f"Total movidos: {len(movidos)}")

asyncio.run(main())
