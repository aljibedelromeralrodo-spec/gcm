"""Crea carpetas para los clientes con solicitud de escrituración del último mes."""
import asyncio, os, re, sys
import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()
API = "http://localhost:8001/api"
CLAVE = "0586"

CLIENTES = [
    ("13.745.447-5", "01-01-02489-1", "Jose Nibaldo Collao Rojas", "Portal de Peñuelas Coquimbo", "Ecomac"),
    ("13.935.126-6", "01-01-02260-1", "Irma Peralta Perez", "casa usada 2742", ""),
    ("15.767.636-9", "01-01-02408-1", "Jocelyn Del Carmen Bello Campos", "Jardin los Volcanes Osorno", "Ecomac"),
    ("15.952.734-4", "01-01-02501-1", "Jorge Andres Bravo Gonzalez", "Fuschloker Los Arrayanes Osorno", "Boetsch"),
    ("16.338.109-5", "01-01-02508-1", "Javier Andres Perez Solis", "Fuschloker Los Arrayanes Osorno", "Boetsch"),
    ("16.338.126-5", "01-01-02505-1", "Luis Miguel Jara Gonzalez", "Fuschloker Los Arrayanes Osorno", "Boetsch"),
    ("16.551.775-K", "01-01-02447-1", "Arlett Viola Nannig Hitschfeld", "Los Arrayanes Fuchlocher Osorno", "Boetsch"),
    ("17.311.046-4", "01-01-02449-1", "Marianne Andrea Cabañas Matzner", "Fuchlocher Osorno", "Boetsch"),
    ("19.862.353-2", "01-01-02484-1", "Javiera Paz Hernandez Lynch", "Fuschloker Los Arrayanes Osorno", "Boetsch"),
    ("20.401.884-7", "01-01-02440-1", "Jhon Alejandro Ponce Vallejos", "Alto Parque Cerrillos", "Boetsch"),
    ("21.359.890-2", "01-01-02452-1", "Rodrigo Nicolas Valencia Huerta", "Portal De Peñuelas Coquimbo", "Ecomac"),
    ("22.345.359-7", "01-01-02507-1", "Sebastian Ignacio Herrera Moroso", "Paseo San Carlos VII Coquimbo", "Ecomac"),
    ("24.558.787-2", "01-01-02480-1", "Johnson Vargas Peña", "Altos del Sendero VIII La Serena", "Ecomac"),
    ("26.264.807-9", "01-01-02504-1", "Yucely Virginia Andrade Natera", "Las Uvas y Viento La Granja", "Boetsch"),
    ("26.825.767-5", "01-01-02509-1", "Aleidys Noemi Aponte Bandres", "Las Uvas y Viento La Granja", "Boetsch"),
]


async def main():
    client = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = client[os.environ['DB_NAME']]
    creadas, existentes, errores = [], [], []
    async with httpx.AsyncClient(timeout=300) as http:
        for rut, op, nombre, proyecto, inmobiliaria in CLIENTES:
            toks = [t for t in nombre.split() if len(t) > 2]
            rx = ".*".join(re.escape(t) for t in (toks[0], toks[-2] if len(toks) > 2 else toks[-1]))
            folder = await db.folders.find_one({"nombre": {"$regex": rx, "$options": "i"}})
            if not folder:
                folder = await db.folders.find_one({"rut": rut})
            nueva = False
            if not folder:
                try:
                    r = await http.post(f"{API}/clientes/folders/forzar",
                                        json={"nombre": nombre, "rut": rut, "clave": CLAVE})
                    r.raise_for_status()
                    data = r.json()
                    folder = await db.folders.find_one({"nombre": data.get("carpeta", nombre.upper())})
                    nueva = True
                    print(f"CREADA: {nombre} — correos:{data.get('correos_encontrados')} docs_aprob:{len(data.get('docs_aprobacion_descargados') or [])}", flush=True)
                except Exception as e:
                    errores.append(f"{nombre}: {str(e)[:100]}")
                    print(f"ERROR: {nombre}: {e}", flush=True)
                    continue
            if folder:
                upd = {"escritura_op": op, "escritura_solicitada_at": folder.get("escritura_solicitada_at") or None}
                if not folder.get("rut"):
                    upd["rut"] = rut
                df = folder.get("datos_financieros") or {}
                if not df.get("proyecto"):
                    df["proyecto"] = proyecto
                if not df.get("inmobiliaria") and inmobiliaria:
                    df["inmobiliaria"] = inmobiliaria
                if not df.get("con_subsidio") and "usada" not in proyecto.lower():
                    df["con_subsidio"] = True
                upd["datos_financieros"] = df
                upd = {k: v for k, v in upd.items() if v is not None}
                await db.folders.update_one({"id": folder["id"]}, {"$set": upd})
                (creadas if nueva else existentes).append(f"{nombre} ({rut}) op {op}")
    print("\n===== RESUMEN =====", flush=True)
    print(f"Creadas nuevas ({len(creadas)}):", *creadas, sep="\n  - ")
    print(f"Ya existían, actualizadas ({len(existentes)}):", *existentes, sep="\n  - ")
    if errores:
        print(f"Errores ({len(errores)}):", *errores, sep="\n  - ")

asyncio.run(main())
