"""MIGRACIÓN ÚNICA — Regla de Oro #68 (Escudo Anti-Duplicados).
1) Marca el backlog de notif_cola como omitido (no saldrá en ráfaga).
2) Reserva (huella) todos los correos actuales de la casilla MESA para que NADA antiguo se reenvíe.
3) Deduplica huellas y crea índice único en mesa_verdad_log.
4) Re-siembra la Constitución v29 (Regla #68) en config + dashai_eventos.
"""
import asyncio
import uuid
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)


async def main():
    from database import db
    import email_service as mail
    import mesa_verdad as mv
    now = datetime.now(timezone.utc).isoformat()

    r1 = await db.notif_cola.update_many(
        {"estado_cola": "pendiente"},
        {"$set": {"estado_cola": "omitido_backlog", "despachado_en": now,
                  "motivo": "Limpieza de backlog — Regla de Oro #68 anti-duplicados"}})
    print(f"1) notif_cola backlog marcado: {r1.modified_count}")

    msgs = await asyncio.to_thread(mail.fetch_since_by_senders, 7, [mv.MESA_EMAIL], 120)
    reservados, ya = 0, 0
    for m in msgs:
        mid = m.get("id") or ""
        subject = m.get("subject") or ""
        body = f"{m.get('body') or m.get('body_full') or m.get('preview') or ''}\n{m.get('body_html_text') or ''}"[:8000]
        huella = mv._huella_msg(m, subject, body)
        ex = await db.mesa_verdad_log.find_one({"$or": [{"correo_id": mid}, {"huella": huella}]})
        if ex:
            if not ex.get("huella"):
                await db.mesa_verdad_log.update_one({"_id": ex["_id"]}, {"$set": {"huella": huella}})
            ya += 1
            continue
        await db.mesa_verdad_log.insert_one({
            "id": str(uuid.uuid4()), "correo_id": mid, "huella": huella,
            "tipo": "backlog_marcado", "subject": subject[:200], "procesado_en": now,
            "accion": "Marcado como ya gestionado (migración Regla #68) — sin reenvío"})
        reservados += 1
    print(f"2) MESA inbox: {len(msgs)} correos · {reservados} reservados nuevos · {ya} ya registrados")

    vistos = set()
    async for d in db.mesa_verdad_log.find({"huella": {"$exists": True}}).sort("procesado_en", 1):
        h = d["huella"]
        if h in vistos:
            await db.mesa_verdad_log.delete_one({"_id": d["_id"]})
        else:
            vistos.add(h)
    await db.mesa_verdad_log.create_index("huella", unique=True, sparse=True)
    print(f"3) índice único de huella creado ({len(vistos)} huellas)")

    import constitucion as _const
    import catalogo_maestro as _cat
    await _const.seed_constitucion(db)
    await _cat.archivar_constitucion_completa()
    n68 = await db.dashai_eventos.find_one({"norma_clave": "ORO-68"}, {"_id": 0, "titulo": 1, "estado": 1})
    print(f"4) Constitución v29 sembrada · ORO-68: {n68}")


if __name__ == "__main__":
    asyncio.run(main())
