"""🧠 VISUALIZADOR COGNITIVO EN VIVO (solo agregar, sin tocar módulos existentes):
Flujo de información del sistema como cerebro vivo: carpetas, correos,
ejecutivos y cerebro normativo como nodos; actividad real = pulsos dorados."""
import re
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Request
from database import db

visual = APIRouter()
ROLES = ("admin", "maestro")


def _exigir(request):
    c = getattr(request.state, "user", {}) or {}
    if c.get("rol") not in ROLES:
        raise HTTPException(status_code=403, detail="Solo el administrador puede ver el Visualizador Cognitivo")
    return c


def _rut8(r):
    return re.sub(r"[^0-9kK]", "", r or "").lower()[:8]


def _dtp(ts):
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


HITOS = ("updated_at", "mesa_enviado_at", "estudio_titulo_solicitado_at", "tasacion_solicitada_at",
         "faltantes_pedidos_at", "escrituracion_confirmada_at", "created_at")


@visual.get("/visualizador/estado")
async def visualizador_estado(request: Request):
    _exigir(request)
    ahora = datetime.now(timezone.utc)
    hace_15m = (ahora - timedelta(minutes=15)).isoformat()

    # mapa rut → resultado desde las últimas simulaciones (una sola pasada)
    sim_map = {}
    async for s in db.simulaciones.find({}, {"_id": 0, "rut": 1, "precalificacion_aprobada": 1}).sort("timestamp", -1).limit(400):
        rn = _rut8(s.get("rut"))
        if not rn or rn in sim_map:
            continue
        v = s.get("precalificacion_aprobada")
        if isinstance(v, str):
            v = v.strip().lower() in ("true", "1", "si", "sí")
        if v is not None:
            sim_map[rn] = "aprobado" if v else "reprobado"

    carpetas = []
    q = {"descartada": {"$ne": True}, "archivada": {"$ne": True}}
    async for f in db.folders.find(q, {"_id": 0, "id": 1, "nombre": 1, "rut": 1, "resultado_mesa": 1,
                                       **{h: 1 for h in HITOS}}).sort("updated_at", -1).limit(36):
        resultado = f.get("resultado_mesa") if f.get("resultado_mesa") in ("aprobado", "reprobado") \
            else sim_map.get(_rut8(f.get("rut")))
        ult = max((_dtp(f.get(h)) for h in HITOS if _dtp(f.get(h))), default=None)
        dias = (ahora - ult).days if ult else 0
        carpetas.append({"id": f.get("id"), "nombre": (f.get("nombre") or "")[:22],
                         "resultado": resultado, "alerta": dias > 3,
                         "activo_reciente": bool(ult and ult.isoformat() >= hace_15m)})

    correos = []
    async for c in db.autocorreo_log.find({}, {"_id": 0, "cliente": 1, "subject": 1,
                                               "processed_at": 1, "status": 1}).sort("processed_at", -1).limit(14):
        correos.append({"key": f"{c.get('processed_at')}|{(c.get('cliente') or '')[:18]}",
                        "cliente": (c.get("cliente") or c.get("subject") or "correo")[:20],
                        "fallido": c.get("status") not in (None, "sent"),
                        "reciente": str(c.get("processed_at") or "") >= hace_15m})

    ejecutivos = []
    async for u in db.users.find({"rol": {"$in": ["broker", "gerencia", "administracion", "postventa"]}},
                                 {"_id": 0, "codigo": 1, "nombre": 1, "rol": 1}).limit(10):
        ejecutivos.append({"codigo": u.get("codigo"), "nombre": (u.get("nombre") or u.get("codigo") or "")[:18],
                           "rol": u.get("rol")})

    normativas = await db.dashai_eventos.count_documents({"motivo": "normativa"})
    perp = await db.config.find_one({"_key": "dashai_perpetuo"}) or {}
    return {"generado": ahora.isoformat(),
            "cerebro": {"normativas": normativas, "calibracion": perp.get("nivel_calibracion") or 85},
            "carpetas": carpetas, "correos": correos, "ejecutivos": ejecutivos}
