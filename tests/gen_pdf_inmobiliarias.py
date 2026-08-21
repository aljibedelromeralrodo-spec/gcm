from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader

W, H = A4
ORO = HexColor("#d4af37")
ORO_S = HexColor("#b8963a")
BLANCO = HexColor("#f2f2f2")
GRIS = HexColor("#9a9a9a")
NEGRO = HexColor("#050505")
PANEL = HexColor("#111111")

c = canvas.Canvas("/app/frontend/public/presentacion-inmobiliarias-concreces.pdf", pagesize=A4)
c.setTitle("Central Mutuos ConCreces — Presentación corporativa para inmobiliarias")
LOGO = ImageReader("/app/frontend/public/logo-circular-oficial.png")


def fondo(num, titulo=""):
    c.setFillColor(NEGRO)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setStrokeColor(ORO_S)
    c.setLineWidth(0.8)
    c.rect(24, 24, W - 48, H - 48, stroke=1, fill=0)
    # pie legal en todas las páginas
    c.setFillColor(GRIS)
    c.setFont("Times-Roman", 8.5)
    c.drawCentredString(W / 2, 40, "ConCreces Leasing S.A., inscrita conforme a la Ley 20.382, supervisada por la CMF. República de Chile.")
    c.setFillColor(ORO_S)
    c.drawRightString(W - 36, 40, f"{num}")
    if titulo:
        c.drawImage(LOGO, 40, H - 78, 42, 42, mask="auto")
        c.setFillColor(ORO)
        c.setFont("Times-Bold", 17)
        c.drawString(94, H - 62, titulo)
        c.setStrokeColor(ORO_S)
        c.setLineWidth(1)
        c.line(40, H - 88, W - 40, H - 88)


def parrafo(x, y, lineas, size=11, color=BLANCO, leading=16, font="Times-Roman"):
    c.setFont(font, size)
    c.setFillColor(color)
    for ln in lineas:
        c.drawString(x, y, ln)
        y -= leading
    return y


def caja(x, y, w, h, titulo, lineas, size=10.5):
    c.setStrokeColor(ORO_S)
    c.setFillColor(PANEL)
    c.rect(x, y - h, w, h, stroke=1, fill=1)
    c.setFillColor(ORO)
    c.setFont("Times-Bold", 12.5)
    c.drawString(x + 14, y - 22, titulo)
    yy = y - 40
    c.setFont("Times-Roman", size)
    c.setFillColor(BLANCO)
    for ln in lineas:
        c.drawString(x + 14, yy, ln)
        yy -= 15


# ═══ PÁGINA 1 — PORTADA ═══
fondo(1)
c.drawImage(LOGO, (W - 150) / 2, H - 320, 150, 150, mask="auto")
c.setFillColor(ORO)
c.setFont("Times-Bold", 30)
c.drawCentredString(W / 2, H - 372, "CENTRAL MUTUOS · CONCRECES")
c.setFillColor(BLANCO)
c.setFont("Times-Italic", 16)
c.drawCentredString(W / 2, H - 400, "Financiamiento hipotecario directo, ágil y sin complicaciones.")
c.setStrokeColor(ORO)
c.setLineWidth(1.2)
c.line(W / 2 - 110, H - 420, W / 2 + 110, H - 420)
c.setFillColor(GRIS)
c.setFont("Times-Roman", 13)
c.drawCentredString(W / 2, H - 452, "Presentación corporativa para inmobiliarias")
c.setFillColor(ORO_S)
c.setFont("Times-Bold", 12)
c.drawCentredString(W / 2, 150, "Respuesta en 24 horas  ·  Con y sin subsidio  ·  Trato directo con la mutuaria")
c.setFillColor(GRIS)
c.setFont("Times-Roman", 11)
c.drawCentredString(W / 2, 128, "centralmutuos.cl  ·  concreces.cl")
c.showPage()

# ═══ PÁGINA 2 — QUIÉNES SOMOS + ALIANZA ═══
fondo(2, "Quiénes somos — la alianza")
y = H - 120
c.setFillColor(ORO)
c.setFont("Times-Bold", 13.5)
c.drawString(46, y, "CENTRAL MUTUOS")
y = parrafo(46, y - 20, [
    "Especialistas en el financiamiento de Mutuos Hipotecarios Endosables (MHE) con y sin subsidio.",
    "Asesoramos de manera integral todo el proceso de adquisición de la vivienda, en tiempo récord,",
    "en lo comercial y en lo operativo: desde la captación del prospecto hasta la entrega de la casa,",
    "junto con la escritura de compraventa.",
    "Nuestro equipo está liderado por uno de los fundadores de Mutuaria Central Hipotecaria, que en",
    "solo tres años posicionó a esa compañía como líder en colocaciones de MHE con subsidio en Chile."])
y -= 12
c.setFillColor(ORO)
c.setFont("Times-Bold", 13.5)
c.drawString(46, y, "CONCRECES — GRUPO ECOMAC")
y = parrafo(46, y - 20, [
    "Fundada en 1996 como parte del grupo Ecomac, ConCreces lleva 30 años a la vanguardia del",
    "financiamiento habitacional en Chile, con dos productos: Mutuo Hipotecario y Leasing Habitacional,",
    "ofreciendo alternativas a personas que no calzan con el financiamiento bancario tradicional.",
    "ConCreces Leasing S.A. está inscrita conforme a la Ley 20.382 y es supervisada por la CMF."])
y -= 18
# métricas
mx, mw = 46, (W - 92 - 24) / 3
for i, (n, t) in enumerate([("+12 mil", "familias han conseguido su hogar"),
                            ("+1.300", "viviendas financiadas en 5 años"),
                            ("30 años", "de innovación (desde 1996)")]):
    x0 = mx + i * (mw + 12)
    c.setStrokeColor(ORO_S)
    c.setFillColor(PANEL)
    c.rect(x0, y - 64, mw, 64, stroke=1, fill=1)
    c.setFillColor(ORO)
    c.setFont("Times-Bold", 19)
    c.drawCentredString(x0 + mw / 2, y - 28, n)
    c.setFillColor(BLANCO)
    c.setFont("Times-Roman", 9.5)
    c.drawCentredString(x0 + mw / 2, y - 48, t)
y -= 92
c.setStrokeColor(ORO)
c.setFillColor(HexColor("#1a1503"))
c.rect(46, y - 78, W - 92, 78, stroke=1, fill=1)
c.setFillColor(ORO)
c.setFont("Times-Bold", 13)
c.drawCentredString(W / 2, y - 24, "¿Qué significa la alianza para su inmobiliaria?")
c.setFillColor(BLANCO)
c.setFont("Times-Roman", 10.5)
c.drawCentredString(W / 2, y - 44, "La agilidad comercial de Central Mutuos + el respaldo financiero e institucional de ConCreces:")
c.drawCentredString(W / 2, y - 60, "su stock se escritura más rápido, con más compradores calificados y sin intermediarios.")
c.showPage()

# ═══ PÁGINA 3 — PRODUCTOS + RAPIDEZ ═══
fondo(3, "Productos y plazos")
y = H - 116
cw = (W - 92 - 14) / 2
caja(46, y, cw, 128, "🏠  Con subsidio", [
    "DS19 y DS01 · Tramo 2 y Tramo 3",
    "SIN monto mínimo",
    "Proyectos DS19 con homologación DS01:",
    "relación deuda/garantía de hasta 70%",
    "Seguro de cesantía hasta 6 meses,",
    "prima cubierta por el Estado"])
caja(46 + cw + 14, y, cw, 128, "💰  Sin subsidio", [
    "Desde 2.000 UF hasta 12.000 UF",
    "Vivienda nueva y usada",
    "Deudor individual o con codeudor",
    "Complementación de renta",
    "con terceros permitida",
    "Dividendos más flexibles"])
y -= 150
c.setFillColor(ORO)
c.setFont("Times-Bold", 15)
c.drawString(46, y, "Beneficio adicional: subsidio al buen pagador")
y = parrafo(46, y - 18, ["Abono de entre el 10% y el 20% del dividendo mensual si el cliente paga dentro de los",
                         "primeros 10 días. Un argumento de venta concreto para su equipo comercial."], 11)
y -= 16
c.setFillColor(ORO)
c.setFont("Times-Bold", 15)
c.drawString(46, y, "⚡ Rapidez: nuestros plazos")
y -= 14
mw = (W - 92 - 36) / 4
for i, (n, t1, t2) in enumerate([("24 hrs", "Aprobación", "del crédito"),
                                 ("48 hrs", "Tasación y", "Estudio de Títulos"),
                                 ("48 hrs", "Escritura puesta", "en Notaría"),
                                 ("5 días", "Tiempo total", "desde la aprobación")]):
    x0 = 46 + i * (mw + 12)
    destaca = i == 3
    c.setStrokeColor(ORO if destaca else ORO_S)
    c.setFillColor(HexColor("#1a1503") if destaca else PANEL)
    c.rect(x0, y - 72, mw, 66, stroke=1, fill=1)
    c.setFillColor(ORO)
    c.setFont("Times-Bold", 17)
    c.drawCentredString(x0 + mw / 2, y - 28, n)
    c.setFillColor(BLANCO)
    c.setFont("Times-Roman", 8.5)
    c.drawCentredString(x0 + mw / 2, y - 44, t1)
    c.drawCentredString(x0 + mw / 2, y - 56, t2)
y -= 100
parrafo(46, y, ["Respuesta en 24 horas con o sin subsidio: aprobación o rechazo inmediato, sin tiempos de espera.",
                "Su equipo comercial sabe al día siguiente si la promesa avanza."], 11.5, ORO)
c.showPage()

# ═══ PÁGINA 4 — COMPARATIVO + INMOBILIARIAS ═══
fondo(4, "Ventajas frente al proceso tradicional")
y = H - 112
filas = [
    ("Respuesta en 24 horas", "Semanas de espera"),
    ("Complementación de renta con terceros permitida", "Restricción habitual"),
    ("Dividendos más flexibles", "Cálculo rígido"),
    ("Sin cobros de gestión", "Honorarios de gestor o broker"),
    ("Trato directo con la mutuaria", "Intermediarios"),
]
cw = (W - 92) / 2
c.setFillColor(HexColor("#1a1503"))
c.setStrokeColor(ORO_S)
c.rect(46, y - 26, cw, 26, stroke=1, fill=1)
c.rect(46 + cw, y - 26, cw, 26, stroke=1, fill=1)
c.setFillColor(ORO)
c.setFont("Times-Bold", 11)
c.drawString(56, y - 18, "CENTRAL MUTUOS · CONCRECES")
c.setFillColor(GRIS)
c.drawString(56 + cw, y - 18, "PROCESO TRADICIONAL")
y -= 26
for i, (a, b) in enumerate(filas):
    c.setFillColor(HexColor("#0f0f0f") if i % 2 == 0 else HexColor("#141414"))
    c.setStrokeColor(ORO_S)
    c.rect(46, y - 30, cw, 30, stroke=1, fill=1)
    c.rect(46 + cw, y - 30, cw, 30, stroke=1, fill=1)
    c.setFillColor(BLANCO)
    c.setFont("Times-Bold", 10.5)
    c.drawString(56, y - 19, f"✓  {a}")
    c.setFillColor(GRIS)
    c.setFont("Times-Roman", 10.5)
    c.drawString(56 + cw, y - 19, f"✗  {b}")
    y -= 30
y -= 40
c.setFillColor(ORO)
c.setFont("Times-Bold", 12)
c.drawCentredString(W / 2, y, "YA TRABAJAMOS CON LAS PRINCIPALES INMOBILIARIAS DEL PAÍS")
c.setFillColor(BLANCO)
c.setFont("Times-Bold", 16)
c.drawCentredString(W / 2, y - 26, "BOETSCH   ·   ECOMAC   ·   BESALCO   ·   y otras")
y -= 70
c.setFillColor(ORO)
c.setFont("Times-Bold", 15)
c.drawString(46, y, "¿Cómo opera su inmobiliaria con nosotros? — paso a paso")
y -= 22
pasos = [
    "1. Firma de alianza comercial: definimos proyectos, contactos y flujo de derivación.",
    "2. Su sala de ventas deriva al comprador con sus antecedentes (o lo ingresa por nuestro simulador).",
    "3. En 24 horas entregamos aprobación o rechazo del crédito, con o sin subsidio.",
    "4. En 48 horas coordinamos tasación y estudio de títulos con nuestros equipos.",
    "5. En 48 horas la escritura queda puesta en Notaría; total: 5 días desde la aprobación.",
    "6. Acompañamos al cliente hasta la entrega de la vivienda; su inmobiliaria escritura y cobra antes.",
]
for p in pasos:
    c.setFillColor(ORO)
    c.setFont("Times-Bold", 11)
    c.drawString(50, y, "—")
    c.setFillColor(BLANCO)
    c.setFont("Times-Roman", 11)
    c.drawString(68, y, p)
    y -= 20
c.showPage()

# ═══ PÁGINA 5 — FAQ + CONTACTO + CIERRE ═══
fondo(5, "Preguntas frecuentes y contacto")
y = H - 116
faqs = [
    ("¿Qué necesita el comprador para la evaluación?",
     "Cédula de identidad, liquidaciones o boletas, certificado AFP y antecedentes de la compra. Con eso respondemos en 24 horas."),
    ("¿Trabajan operaciones con y sin subsidio?",
     "Sí. Con subsidio DS19 y DS01 (tramo 2 y 3, sin monto mínimo) y sin subsidio desde 2.000 UF hasta 12.000 UF."),
    ("¿Aceptan complementación de renta?",
     "Sí, permitimos complementación de renta con terceros, ampliando la base de compradores que califican."),
    ("¿Cobran gestión al cliente o a la inmobiliaria?",
     "No. Sin cobros de gestión ni honorarios de gestor o broker: trato directo con la mutuaria."),
    ("¿Para qué tipo de vivienda aplica?",
     "Vivienda nueva y usada, con deudor individual o con codeudor. Exclusivo para escrituración inmediata."),
    ("¿Quién respalda la operación?",
     "ConCreces Leasing S.A. (grupo Ecomac, desde 1996), inscrita conforme a la Ley 20.382 y supervisada por la CMF."),
]
for q, a in faqs:
    c.setFillColor(ORO)
    c.setFont("Times-Bold", 11.5)
    c.drawString(46, y, q)
    y -= 16
    c.setFillColor(BLANCO)
    c.setFont("Times-Roman", 10.5)
    for ln in [a[i:i + 105] for i in range(0, len(a), 105)]:
        c.drawString(58, y, ln)
        y -= 14
    y -= 10
y -= 6
c.setStrokeColor(ORO)
c.setFillColor(HexColor("#1a1503"))
c.rect(46, y - 96, W - 92, 96, stroke=1, fill=1)
c.setFillColor(ORO)
c.setFont("Times-Bold", 15)
c.drawCentredString(W / 2, y - 26, "Conversemos sobre su próximo proyecto")
c.setFillColor(BLANCO)
c.setFont("Times-Roman", 11.5)
c.drawCentredString(W / 2, y - 48, "contacto@centralmutuos.cl   ·   centralmutuos.cl   ·   concreces.cl")
c.setFillColor(GRIS)
c.setFont("Times-Italic", 10.5)
c.drawCentredString(W / 2, y - 70, "Financiamiento hipotecario directo, ágil y sin complicaciones.")
c.save()
print("PDF inmobiliarias generado")
