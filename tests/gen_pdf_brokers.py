from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader

W, H = A4
ORO = HexColor("#d4af37")
ORO_SUAVE = HexColor("#b8963a")
BLANCO = HexColor("#f2f2f2")
GRIS = HexColor("#9a9a9a")

c = canvas.Canvas("/app/frontend/public/presentacion-brokers-concreces.pdf", pagesize=A4)
c.setTitle("Central Mutuos ConCreces — Financiamiento hipotecario directo")

# Fondo negro
c.setFillColor(HexColor("#050505"))
c.rect(0, 0, W, H, stroke=0, fill=1)

# Marco dorado fino
c.setStrokeColor(ORO_SUAVE)
c.setLineWidth(0.8)
c.rect(28, 28, W - 56, H - 56, stroke=1, fill=0)

# Logo
logo = ImageReader("/app/frontend/public/logo-circular-oficial.png")
LW = 110
c.drawImage(logo, (W - LW) / 2, H - 165, LW, LW, mask="auto")

# Título
c.setFillColor(ORO)
c.setFont("Times-Bold", 26)
c.drawCentredString(W / 2, H - 205, "CENTRAL MUTUOS · CONCRECES")
c.setFillColor(BLANCO)
c.setFont("Times-Italic", 15)
c.drawCentredString(W / 2, H - 230, "Financiamiento hipotecario directo, sin intermediarios.")

# Línea separadora
c.setStrokeColor(ORO)
c.setLineWidth(1.2)
c.line(W / 2 - 90, H - 248, W / 2 + 90, H - 248)

# Beneficios
items = [
    ("Créditos desde 2.000 UF hasta 12.000 UF", "vivienda nueva y usada"),
    ("Con subsidio DS19 y DS01, tramo 2 y tramo 3", "sin monto mínimo"),
    ("Respuesta en 24 horas", "con o sin subsidio"),
    ("Sin cobros de gestión ni honorarios", ""),
    ("Deudor individual o con codeudor", ""),
    ("Exclusivo para escrituración inmediata", ""),
]
y = H - 300
for titulo, sub in items:
    c.setFillColor(ORO)
    c.setFont("Times-Bold", 13)
    c.drawString(95, y, "—")
    c.setFillColor(BLANCO)
    c.setFont("Times-Bold", 14.5)
    c.drawString(120, y, titulo)
    if sub:
        c.setFillColor(GRIS)
        c.setFont("Times-Roman", 12)
        c.drawString(120, y - 16, sub)
        y -= 52
    else:
        y -= 40

# Bloque destaque
c.setStrokeColor(ORO_SUAVE)
c.setLineWidth(0.8)
c.rect(70, y - 46, W - 140, 52, stroke=1, fill=0)
c.setFillColor(ORO)
c.setFont("Times-Bold", 13)
c.drawCentredString(W / 2, y - 14, "Canal exclusivo para brokers")
c.setFillColor(BLANCO)
c.setFont("Times-Roman", 11.5)
c.drawCentredString(W / 2, y - 32, "Evaluación directa con nuestra mesa · acompañamiento en todo el proceso de escrituración")

# Pie legal
c.setStrokeColor(ORO_SUAVE)
c.setLineWidth(0.6)
c.line(70, 92, W - 70, 92)
c.setFillColor(GRIS)
c.setFont("Times-Roman", 9.5)
c.drawCentredString(W / 2, 74, "ConCreces Leasing S.A., inscrita conforme a la Ley 20.382, supervisada por la CMF.")
c.setFillColor(ORO_SUAVE)
c.setFont("Times-Roman", 9.5)
c.drawCentredString(W / 2, 58, "Central Mutuos · mutuariasyleasing.cl")

c.save()
print("PDF generado")
