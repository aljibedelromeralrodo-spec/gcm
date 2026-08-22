"""Auditoría: reclasificación de casos fallidos (todo 'otro') con el pipeline NUEVO."""
import os
import sys
import asyncio
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
load_dotenv("/app/backend/.env")

CASOS = [
    "envío liquidaciones de cliente Juan Moya",
    "LILIAN NAVARRO",
    "Evaluación cliente Pedro González solo",
    "EVALUACION FRANCO BAHAMONDES",
]


async def main():
    from database import db
    import ocr_service
    from pdf_service import _categoria_pagina
    from pathlib import Path
    for patron in CASOS:
        it = await db.proc_queue.find_one({"subject": {"$regex": patron, "$options": "i"}})
        if not it:
            print(f"== {patron}: no encontrado =="); continue
        viejos = {d["filename"]: d.get("tipo") for d in (it.get("classification") or {}).get("documentos", [])}
        print(f"\n== {it['subject'][:70]} | de: {it.get('sender','')[:40]} ==")
        folder = Path(it.get("attachments_bytes_dir") or "")
        for fn in (it.get("attachments") or [])[:9]:
            p = folder / fn
            if not p.exists():
                print(f"  {fn[:48]:50} | archivo no disponible"); continue
            raw = p.read_bytes()
            texto, metodo = await asyncio.to_thread(ocr_service.extraer_texto, raw, fn, False)
            cat = _categoria_pagina(texto)
            viejo = viejos.get(fn, "?")
            ok = "✅" if (cat != "otro" and viejo == "otro") or cat == viejo or (cat != "otro") else "•"
            print(f"  {fn[:48]:50} | ANTES: {viejo:16} | AHORA: {cat:12} ({metodo},{len(texto)}c) {ok}")

asyncio.run(main())
