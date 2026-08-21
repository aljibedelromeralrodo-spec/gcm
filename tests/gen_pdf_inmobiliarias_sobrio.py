from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader

W, H = A4
PETROL = HexColor("#2e4a5a")
TURQ = HexColor("#43b5c3")
NAVY = HexColor("#0e1c30")
AZUL = HexColor("#2f80ed")
GRIS = HexColor("#5a6b76")
GRIS_C = HexColor("#8a97a1")
BORDE = HexColor("#d8dee4")
FONDO_S = HexColor("#f5f8fa")
BLANCO = HexColor("#ffffff")

c = canvas.Canvas("/app/frontend/public/presentacion-inmobiliarias-corporativa.pdf", pagesize=A4)
c.setTitle("Central Mutuos + ConCreces — Presentación corporativa para inmobiliarias")
LOGO_CM = ImageReader("/app/frontend/public/logo-centralmutuos-horizontal.png")
LOGO_CC = ImageReader("/app/frontend/public/logo-concreces.png")


def logos_header(y=H - 74):
    c.drawImage(LOGO_CM, 40, y, 150, 150 * 0.22, mask="auto", preserveAspectRatio=True, anchor="w")
    c.setFillColor(NAVY)
    c.roundRect(W - 178, y - 6, 138, 44, 4, stroke=0, fill=1)
    c.drawImage(LOGO_CC, W - 168, y + 4, 118, 118 * 0.2, mask="auto", preserveAspectRatio=True, anchor="w")


def fondo(num, titulo=""):
    c.setFillColor(BLANCO)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    # pie legal en todas las páginas
    c.setFillColor(NAVY)
    c.rect(0, 0, W, 54, stroke=0, fill=1)
    c.setFillColor(HexColor("#8fa3ba"))
    c.setFont("Helvetica", 8.5)
    c.drawCentredString(W / 2, 32, "ConCreces Leasing S.A., inscrita conforme a la Ley 20.382, supervisada por la CMF. República de Chile.")
    c.setFont("Helvetica", 8.5)
    c.drawRightString(W - 36, 18, f"{num}")
    if titulo:
        logos_header()
        c.setFillColor(PETROL)
        c.setFont("Helvetica-Bold", 17)
        c.drawString(40, H - 112, titulo)
        c.setStrokeColor(PETROL)
        c.setLineWidth(1.6)
        c.line(40, H - 122, W - 40, H - 122)


def parrafo(x, y, lineas, size=10.5, color=GRIS, leading=16, font="Helvetica"):
    c.setFont(font, size)
    c.setFillColor(color)
    for ln in lineas:
        c.drawString(x, y, ln)
        y -= leading
    return y


def caja(x, y, w, h, titulo, lineas, acento=TURQ, size=10):
    c.setStrokeColor(BORDE)
    c.setFillColor(BLANCO)
    c.rect(x, y - h, w, h, stroke=1, fill=1)
    c.setFillColor(acento)
    c.rect(x, y, w, 3, stroke=0, fill=1)
    c.setFillColor(PETROL)
    c.setFont("Helvetica-Bold", 12.5)
    c.drawString(x + 14, y - 24, titulo)
    yy = y - 42
    c.setFont("Helvetica", size)
    c.setFillColor(GRIS)
    for ln in lineas:
        c.drawString(x + 14, yy, ln)
        yy -= 15


# ═══ PÁGINA 1 — PORTADA ═══
fondo(1)
c.drawImage(LOGO_CM, (W - 260) / 2, H - 300, 260, 260 * 0.22, mask="auto", preserveAspectRatio=True)
c.setFillColor(NAVY)
c.roundRect((W - 230) / 2, H - 390, 230, 66, 5, stroke=0, fill=1)
c.drawImage(LOGO_CC, (W - 190) / 2, H - 374, 190, 190 * 0.2, mask="auto", preserveAspectRatio=True)
c.setFillColor(PETROL)
c.setFont("Helvetica-Bold", 26)
c.drawCentredString(W / 2, H - 448, "Alianza Central Mutuos + ConCreces")
c.setFillColor(GRIS)
c.setFont("Helvetica-Oblique", 14)
c.drawCentredString(W / 2, H - 474, "Financiamiento hipotecario directo, ágil y sin complicaciones.")
c.setStrokeColor(TURQ)
c.setLineWidth(2)
c.line(W / 2 - 100, H - 492, W / 2 + 100, H - 492)
c.setFillColor(GRIS_C)
c.setFont("Helvetica", 12.5)
c.drawCentredString(W / 2, H - 520, "Presentación corporativa para inmobiliarias")
c.setFillColor(AZUL)
c.setFont("Helvetica-Bold", 11.5)
c.drawCentredString(W / 2, 130, "Respuesta en 24 horas  ·  Con y sin subsidio  ·  Trato directo con la mutuaria")
c.setFillColor(GRIS_C)
c.setFont("Helvetica", 10.5)
c.drawCentredString(W / 2, 108, "centralmutuos.cl  ·  concreces.cl")
c.showPage()

# ═══ PÁGINA 2 — QUIÉNES SOMOS + ALIANZA ═══
fondo(2, "Quiénes somos — la alianza")
y = H - 152
c.setFillColor(PETROL)
c.setFont("Helvetica-Bold", 13)
c.drawString(40, y, "CENTRAL MUTUOS")
y = parrafo(40, y - 18, [
    "Especialistas en el financiamiento de Mutuos Hipotecarios Endosables (MHE) con y sin subsidio.",
    "Asesoramos de manera integral todo el proceso de adquisición de la vivienda, en tiempo récord,",
    "en lo comercial y en lo operativo: desde la captación del prospecto hasta la entrega de la casa,",
    "junto con la escritura de compraventa.",
    "Nuestro equipo está liderado por uno de los fundadores de Mutuaria Central Hipotecaria, que en",
    "solo tres años posicionó a esa compañía como líder en colocaciones de MHE con subsidio en Chile."])
y -= 12
c.setFillColor(AZUL)
c.setFont("Helvetica-Bold", 13)
c.drawString(40, y, "CONCRECES — GRUPO ECOMAC")
y = parrafo(40, y - 18, [
    "Fundada en 1996 como parte del grupo Ecomac, ConCreces lleva 30 años a la vanguardia del",
    "financiamiento habitacional en Chile, con dos productos: Mutuo Hipotecario y Leasing Habitacional,",
    "ofreciendo alternativas a personas que no calzan con el financiamiento bancario tradicional.",
    "ConCreces Leasing S.A. está inscrita conforme a la Ley 20.382 y es supervisada por la CMF."])
y -= 18
mx, mw = 40, (W - 80 - 24) / 3
for i, (n, t) in enumerate([("+12 mil", "familias han conseguido su hogar"),
                            ("+1.300", "viviendas financiadas en 5 años"),
                            ("30 años", "de trayectoria (desde 1996)")]):
    x0 = mx + i * (mw + 12)
    c.setStrokeColor(BORDE)
    c.setFillColor(BLANCO)
    c.rect(x0, y - 60, mw, 60, stroke=1, fill=1)
    c.setFillColor(AZUL)
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(x0 + mw / 2, y - 26, n)
    c.setFillColor(GRIS)
    c.setFont("Helvetica", 9)
    c.drawCentredString(x0 + mw / 2, y - 44, t)
y -= 88
c.setStrokeColor(BORDE)
c.setFillColor(FONDO_S)
c.rect(40, y - 78, W - 80, 78, stroke=1, fill=1)
c.setFillColor(TURQ)
c.rect(40, y - 78, 4, 78, stroke=0, fill=1)
c.setFillColor(PETROL)
c.setFont("Helvetica-Bold", 12.5)
c.drawString(58, y - 24, "¿Qué significa la alianza para su inmobiliaria?")
c.setFillColor(GRIS)
c.setFont("Helvetica", 10.5)
c.drawString(58, y - 44, "La agilidad comercial de Central Mutuos + el respaldo financiero e institucional de ConCreces:")
c.drawString(58, y - 60, "su stock se escritura más rápido, con más compradores calificados y sin intermediarios.")
c.showPage()

# ═══ PÁGINA 3 — PRODUCTOS + RAPIDEZ ═══
fondo(3, "Productos y plazos")
y = H - 148
cw = (W - 80 - 14) / 2
caja(40, y, cw, 122, "Con subsidio", [
    "DS19 y DS01 · Tramo 2 y Tramo 3",
    "SIN monto mínimo",
    "Proyectos DS19 con homologación DS01:",
    "relación deuda/garantía de hasta 70%",
    "Seguro de cesantía hasta 6 meses,",
    "prima cubierta por el Estado"], TURQ)
caja(40 + cw + 14, y, cw, 122, "Sin subsidio", [
    "Desde 2.000 UF hasta 12.000 UF",
    "Vivienda nueva y usada",
    "Deudor individual o con codeudor",
    "Complementación de renta",
    "con terceros permitida",
    "Dividendos más flexibles"], AZUL)
y -= 152
c.setFillColor(PETROL)
c.setFont("Helvetica-Bold", 14)
c.drawString(40, y, "Beneficio adicional: subsidio al buen pagador")
y = parrafo(40, y - 18, ["Abono de entre el 10% y el 20% del dividendo mensual si el cliente paga dentro de los",
                         "primeros 10 días. Un argumento de venta concreto para su equipo comercial."], 10.5)
y -= 18
c.setFillColor(PETROL)
c.setFont("Helvetica-Bold", 14)
c.drawString(40, y, "Rapidez: nuestros plazos")
y -= 14
mw = (W - 80 - 36) / 4
for i, (n, t1, t2) in enumerate([("24 hrs", "Aprobación", "del crédito"),
                                 ("48 hrs", "Tasación y", "Estudio de Títulos"),
                                 ("48 hrs", "Escritura puesta", "en Notaría"),
                                 ("5 días", "Tiempo total", "desde la aprobación")]):
    x0 = 40 + i * (mw + 12)
    destaca = i == 3
    c.setStrokeColor(NAVY if destaca else BORDE)
    c.setFillColor(NAVY if destaca else BLANCO)
    c.rect(x0, y - 66, mw, 62, stroke=1, fill=1)
    c.setFillColor(HexColor("#ffffff") if destaca else PETROL)
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(x0 + mw / 2, y - 26, n)
    c.setFillColor(HexColor("#cfe0f5") if destaca else GRIS)
    c.setFont("Helvetica", 8)
    c.drawCentredString(x0 + mw / 2, y - 42, t1)
    c.drawCentredString(x0 + mw / 2, y - 53, t2)
y -= 94
parrafo(40, y, ["Respuesta en 24 horas con o sin subsidio: aprobación o rechazo inmediato, sin tiempos de espera.",
                "Su equipo comercial sabe al día siguiente si la promesa avanza."], 11, AZUL, font="Helvetica-Bold")
c.showPage()

# ═══ PÁGINA 4 — COMPARATIVO + PROCESO ═══
fondo(4, "Ventajas frente al proceso tradicional")
y = H - 144
filas = [
    ("Respuesta en 24 horas", "Semanas de espera"),
    ("Complementación de renta con terceros permitida", "Restricción habitual"),
    ("Dividendos más flexibles", "Cálculo rígido"),
    ("Sin cobros de gestión", "Honorarios de gestor o broker"),
    ("Trato directo con la mutuaria", "Intermediarios"),
]
cw = (W - 80) / 2
c.setFillColor(PETROL)
c.setStrokeColor(BORDE)
c.rect(40, y - 26, cw, 26, stroke=1, fill=1)
c.setFillColor(FONDO_S)
c.rect(40 + cw, y - 26, cw, 26, stroke=1, fill=1)
c.setFillColor(BLANCO)
c.setFont("Helvetica-Bold", 10.5)
c.drawString(50, y - 18, "CENTRAL MUTUOS · CONCRECES")
c.setFillColor(GRIS_C)
c.drawString(50 + cw, y - 18, "PROCESO TRADICIONAL")
y -= 26
for i, (a, b) in enumerate(filas):
    c.setFillColor(BLANCO if i % 2 == 0 else FONDO_S)
    c.setStrokeColor(BORDE)
    c.rect(40, y - 30, cw, 30, stroke=1, fill=1)
    c.rect(40 + cw, y - 30, cw, 30, stroke=1, fill=1)
    c.setFillColor(AZUL)
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(50, y - 19, "✓")
    c.setFillColor(PETROL)
    c.drawString(64, y - 19, a)
    c.setFillColor(GRIS_C)
    c.setFont("Helvetica", 10.5)
    c.drawString(50 + cw, y - 19, f"—  {b}")
    y -= 30
y -= 38
c.setFillColor(GRIS_C)
c.setFont("Helvetica-Bold", 10.5)
c.drawCentredString(W / 2, y, "YA TRABAJAMOS CON LAS PRINCIPALES INMOBILIARIAS DEL PAÍS")
c.setFillColor(PETROL)
c.setFont("Helvetica-Bold", 15)
c.drawCentredString(W / 2, y - 24, "BOETSCH   ·   ECOMAC   ·   BESALCO   ·   y otras")
y -= 66
c.setFillColor(PETROL)
c.setFont("Helvetica-Bold", 14)
c.drawString(40, y, "¿Cómo opera su inmobiliaria con nosotros? — paso a paso")
y -= 24
pasos = [
    "Firma de alianza comercial: definimos proyectos, contactos y flujo de derivación.",
    "Su sala de ventas deriva al comprador con sus antecedentes (o lo ingresa por nuestro simulador).",
    "En 24 horas entregamos aprobación o rechazo del crédito, con o sin subsidio.",
    "En 48 horas coordinamos tasación y estudio de títulos con nuestros equipos.",
    "En 48 horas la escritura queda puesta en Notaría; total: 5 días desde la aprobación.",
    "Acompañamos al cliente hasta la entrega de la vivienda; su inmobiliaria escritura y cobra antes.",
]
for i, p in enumerate(pasos, 1):
    c.setFillColor(AZUL)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(46, y, f"{i}.")
    c.setFillColor(GRIS)
    c.setFont("Helvetica", 10.5)
    c.drawString(64, y, p)
    y -= 20
c.showPage()

# ═══ PÁGINA 5 — FAQ + CONTACTO ═══
fondo(5, "Preguntas frecuentes y contacto")
y = H - 148
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
    c.setFillColor(PETROL)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, q)
    y -= 15
    c.setFillColor(GRIS)
    c.setFont("Helvetica", 10)
    for ln in [a[i:i + 108] for i in range(0, len(a), 108)]:
        c.drawString(52, y, ln)
        y -= 13.5
    y -= 11
y -= 4
c.setStrokeColor(BORDE)
c.setFillColor(FONDO_S)
c.rect(40, y - 92, W - 80, 92, stroke=1, fill=1)
c.setFillColor(AZUL)
c.rect(40, y - 92, 4, 92, stroke=0, fill=1)
c.setFillColor(PETROL)
c.setFont("Helvetica-Bold", 14)
c.drawCentredString(W / 2, y - 26, "Conversemos sobre su próximo proyecto")
c.setFillColor(GRIS)
c.setFont("Helvetica", 11)
c.drawCentredString(W / 2, y - 48, "contacto@centralmutuos.cl   ·   centralmutuos.cl   ·   concreces.cl")
c.setFillColor(GRIS_C)
c.setFont("Helvetica-Oblique", 10)
c.drawCentredString(W / 2, y - 68, "Financiamiento hipotecario directo, ágil y sin complicaciones.")
c.save()
print("PDF sobrio generado")
