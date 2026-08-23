"""📔 REGISTRO EMMY — Historial persistente de cambios, reglas y decisiones de la plataforma.
Visible SOLO para el Administrador. Registro automático (espejo de dashai_eventos) + notas manuales.
Exportable a PDF."""
import io
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from database import db

emmy = APIRouter(prefix="/emmy")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _exigir_admin(request):
    claims = getattr(request.state, "user", {}) or {}
    if claims.get("rol") not in ("admin", "maestro"):
        raise HTTPException(status_code=403, detail="Registro Emmy: exclusivo del Administrador")
    return claims


async def registrar(titulo, descripcion, tipo="auto", estado="implementado", por="sistema"):
    """Registro automático: llamable desde cualquier módulo al implementar algo nuevo.
    Espeja cada entrada en /app/memory/EMMY.md para que los agentes futuros retomen el contexto."""
    await db.registro_emmy.insert_one({
        "id": str(uuid.uuid4()), "fecha": _now(), "tipo": tipo, "titulo": titulo,
        "descripcion": descripcion, "estado": estado, "por": por})
    try:
        with open("/app/memory/EMMY.md", "a") as f:
            f.write(f"\n- [{_now()[:16]}] ({tipo}/{estado}) **{titulo}** — {descripcion} · por {por}")
    except Exception:
        pass


def _evento_a_registro(e):
    tipo = e.get("tipo", "evento")
    detalle = {k: v for k, v in e.items() if k not in ("_id", "tipo", "fecha") and not isinstance(v, (dict, list))}
    return {"id": str(e.get("_id", "")), "fecha": e.get("fecha", ""), "tipo": "auto",
            "titulo": f"Evento del sistema: {tipo}",
            "descripcion": " · ".join(f"{k}: {v}" for k, v in list(detalle.items())[:6]) or tipo,
            "estado": "implementado", "por": "sistema (dashai)"}


async def _todos(limit=800):
    regs = [{k: v for k, v in r.items() if k != "_id"}
            for r in await db.registro_emmy.find({}).sort("fecha", -1).to_list(limit)]
    eventos = await db.dashai_eventos.find({}).sort("fecha", -1).to_list(300)
    regs += [_evento_a_registro(e) for e in eventos]
    regs.sort(key=lambda r: str(r.get("fecha", "")), reverse=True)
    return regs[:limit]


@emmy.get("/registros")
async def listar(request: Request):
    _exigir_admin(request)
    return {"registros": await _todos()}


@emmy.post("/registros")
async def nota_manual(payload: dict, request: Request):
    u = _exigir_admin(request)
    titulo = (payload.get("titulo") or "").strip()
    descripcion = (payload.get("descripcion") or "").strip()
    if not titulo:
        raise HTTPException(status_code=400, detail="El título de la nota es obligatorio")
    await registrar(titulo, descripcion, tipo="manual",
                    estado=(payload.get("estado") or "implementado"), por=u.get("sub", "admin"))
    return {"ok": True, "mensaje": "Nota registrada en el Registro Emmy"}


@emmy.get("/export-pdf")
async def export_pdf(request: Request):
    _exigir_admin(request)
    regs = await _todos(500)
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    oro, negro = HexColor("#d4af37"), HexColor("#0a0a0a")

    def encabezado(pagina):
        c.setFillColor(negro)
        c.rect(0, h - 70, w, 70, fill=1, stroke=0)
        c.setFillColor(oro)
        c.setFont("Helvetica-Bold", 15)
        c.drawString(40, h - 42, "REGISTRO EMMY — Central Mutuos")
        c.setFont("Helvetica", 8)
        c.setFillColor(HexColor("#f4f2ec"))
        c.drawString(40, h - 56, f"Historial de cambios, reglas y decisiones · generado {_now()[:16].replace('T', ' ')} UTC · pág. {pagina}")
        return h - 92

    pagina = 1
    y = encabezado(pagina)
    for r in regs:
        if y < 90:
            c.showPage()
            pagina += 1
            y = encabezado(pagina)
        c.setFillColor(oro)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(40, y, f"{str(r.get('fecha',''))[:16].replace('T',' ')} · [{(r.get('tipo') or '').upper()}] {r.get('titulo','')[:80]}")
        y -= 12
        c.setFillColor(HexColor("#222222"))
        c.setFont("Helvetica", 8)
        desc = str(r.get("descripcion", ""))
        for i in range(0, min(len(desc), 360), 120):
            c.drawString(52, y, desc[i:i + 120])
            y -= 10
        c.setFillColor(HexColor("#666666"))
        c.drawString(52, y, f"Estado: {r.get('estado','')} · Por: {r.get('por','')}")
        y -= 18
    c.save()
    from fastapi.responses import Response
    return Response(content=buf.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="registro_emmy.pdf"'})
