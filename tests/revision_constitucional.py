"""Revisión constitucional pre-redespliegue: verifica/corrige las 7 reglas y resume estado."""
import os, re, sys, uuid, asyncio
from datetime import datetime, timezone
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient

REGLAS = [
    ("REDESPLIEGUE-1", "Lectura completa de correos",
     "REGLA DE ORO: lectura obligatoria del cuerpo completo y de TODOS los archivos adjuntos de cada correo recibido, sin excepción. Ningún correo se procesa parcialmente.",
     ["cuerpo completo", "adjuntos", "lectura"]),
    ("REDESPLIEGUE-2", "Validación ConCreces 4 contrastes",
     "REGLA DE ORO CONCRECES: validación obligatoria de RUT con RUT, RUT codeudor con RUT codeudor, rol de avalúo fiscal contra tasación y estudio de títulos, y dirección con dirección. Sin estas CUATRO validaciones aprobadas no se puede avanzar ni enviar a ConCreces.",
     ["ORO_CONCRECES_11", "ORO_CONCRECES_15"]),
    ("REDESPLIEGUE-3", "Único correo diario 8:00 AM",
     "REGLA DE NOTIFICACIONES: un ÚNICO correo diario a las 8:00 AM a gerardo.ext@centralmutuos.cl con el resumen consolidado. Los loops _reporte_correos_loop y _daily_report_loop permanecen DESACTIVADOS. Ninguna otra notificación automática durante el día.",
     ["8:00", "único correo", "resumen"]),
    ("REDESPLIEGUE-4", "Aprobación MESA automática",
     "REGLA DE APROBACIÓN MESA: flujo automático activo. Toda aprobación de MESA se reenvía de inmediato a gerardo.ext@centralmutuos.cl con el cuerpo ORIGINAL de MESA y el PDF SIN gastos operacionales. Excepción única a la regla del correo diario.",
     ["MESA", "reenvío", "gastos operacionales"]),
    ("REDESPLIEGUE-5", "Módulo Victoria independiente",
     "REGLA DEL MÓDULO DE VICTORIA: completamente independiente del módulo de administrador. El acceso victoria.vilches@centralmutuos.cl entra SOLO a su módulo de trabajo (solo_modulo='victoria'), sin sidebar ni paneles de administración.",
     ["Victoria", "independiente"]),
    ("REDESPLIEGUE-6", "Visualizador Cognitivo perpetuo",
     "REGLA DEL VISUALIZADOR COGNITIVO: nunca se detiene, funciona en ciclo perpetuo, SIN etiqueta 'Central Mutuos' visible en el lienzo, y archiva sus registros en segundo plano.",
     ["Visualizador", "nunca se detiene"]),
    ("REDESPLIEGUE-7", "Martín con autorización",
     "REGLA DE MARTÍN: el asistente de voz Martín NO envía correos sin autorización expresa del administrador. Se detiene inmediatamente al escuchar la palabra 'para'.",
     ["Martín", "autorización", "para"]),
]


def ahora():
    return datetime.now(timezone.utc).isoformat()


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    regs = await db.dashai_eventos.find({}, {"_id": 0}).to_list(500)
    corpus = {id(r): " ".join(str(v) for v in r.values()).lower() for r in regs}
    resumen = []
    for codigo, titulo, detalle, claves in REGLAS:
        ya = await db.dashai_eventos.find_one({"codigo": codigo})
        if ya:
            estado = "OK (ya escrita)"
            if (ya.get("detalle") or "") != detalle or ya.get("activa") is not True:
                await db.dashai_eventos.update_one({"codigo": codigo}, {"$set": {
                    "detalle": detalle, "activa": True, "actualizado": ahora()}})
                estado = "CORREGIDA (texto/estado actualizado)"
        else:
            similares = sum(1 for c in corpus.values() if all(k.lower() in c for k in claves[:2]))
            await db.dashai_eventos.insert_one({
                "id": str(uuid.uuid4()), "tipo": "regla_oro", "codigo": codigo,
                "titulo": titulo, "detalle": detalle, "activa": True,
                "categoria": "redespliegue_2026", "inviolable": True, "fecha": ahora()})
            estado = f"ESCRITA AHORA (había {similares} regla(s) parcial(es) relacionadas)"
        resumen.append((codigo, titulo, estado))

    print("=" * 70)
    print("RESUMEN CONSTITUCIONAL PRE-REDESPLIEGUE")
    print("=" * 70)
    for c, t, e in resumen:
        print(f"{c} · {t}\n    → {e}")
    # Verificaciones operativas
    src = open("/app/backend/server.py").read()
    l1 = "# asyncio.create_task(_task_blindada(_daily_report_loop" in src
    l2 = "# asyncio.create_task(_task_blindada(_reporte_correos_loop" in src
    print(f"_daily_report_loop DESACTIVADO en código: {'SÍ' if l1 else 'NO ⚠'}")
    print(f"_reporte_correos_loop DESACTIVADO en código: {'SÍ' if l2 else 'NO ⚠'}")
    oro = await db.dashai_eventos.count_documents({"norma_clave": {"$regex": "^ORO_CONCRECES_1[1-5]$"}})
    print(f"Reglas de Oro ConCreces 11-15 sembradas: {oro}/5")
    v = await db.users.find_one({"codigo": "victoria.vilches@centralmutuos.cl"})
    print(f"Acceso exclusivo Victoria (solo_modulo): {'SÍ' if v and v.get('solo_modulo') == 'victoria' else 'NO ⚠'}")
    total = await db.dashai_eventos.count_documents({"codigo": {"$regex": "^REDESPLIEGUE-"}})
    print(f"Reglas de redespliegue activas en Constitución: {total}/7")

asyncio.run(main())
