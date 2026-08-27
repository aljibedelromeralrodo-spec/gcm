"""Runner independiente del reproceso masivo IA con WATCHDOG anti-cuelgue.
Se ejecuta fuera de uvicorn: si se congela >8 min, sale con código 3 y el
wrapper bash lo relanza (reanuda gratis desde el caché de clasificaciones)."""
import asyncio
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv()
import server  # noqa: E402
from database import db  # noqa: E402


async def main():
    st0 = await db.config.find_one({"_key": "reproceso_ia"}) or {}
    if st0.get("estado") == "terminado":
        print("ya terminado — nada que hacer", flush=True)
        os._exit(0)
    await db.config.update_one({"_key": "reproceso_stop"}, {"$set": {"stop": False}}, upsert=True)
    tarea = asyncio.create_task(server._reproceso_ia_run(180, 4000))
    while not tarea.done():
        await asyncio.sleep(60)
        try:
            st = await db.config.find_one({"_key": "reproceso_ia"}) or {}
        except Exception:
            continue
        if st.get("estado") in ("detenido_por_admin", "detenido_tope_presupuesto"):
            print("detenido por admin/tope", flush=True)
            os._exit(0)
        act = st.get("actualizado") or ""
        try:
            dt = datetime.fromisoformat(act)
            sin_avance = (datetime.now(timezone.utc) - dt).total_seconds()
            # Fase de barrido IMAP (total==0): tolerar hasta 45 min; luego 8 min por lote
            limite = 2700 if not st.get("total") else 480
            if sin_avance > limite:
                print(f"WATCHDOG: sin avance {int(sin_avance)}s (límite {limite}s) → salgo para reinicio", flush=True)
                os._exit(3)
        except Exception:
            pass
    if tarea.done() and tarea.exception():
        import traceback
        traceback.print_exception(tarea.exception())
    st = await db.config.find_one({"_key": "reproceso_ia"}) or {}
    print(f"fin: {st.get('estado')} revisados={st.get('revisados')}", flush=True)
    os._exit(0 if st.get("estado") in ("terminado", "detenido_por_admin", "detenido_tope_presupuesto") else 3)

asyncio.run(main())
