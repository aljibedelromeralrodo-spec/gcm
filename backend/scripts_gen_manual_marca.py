import sys
sys.path.insert(0, '/app/backend')
from datetime import datetime, timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

ORO = (0.788, 0.635, 0.153)
NEGRO = (0.039, 0.039, 0.039)
GRIS = (0.35, 0.35, 0.35)
CARGO = "Jefe Externo, Asesor Business Development | Canal Inmobiliarias y Brokers | Central Mutuos"
HOY = datetime.now(timezone.utc).strftime("%d/%m/%Y")
OUT = "/app/frontend/public/manual-marca-central-mutuos.pdf"

c = canvas.Canvas(OUT, pagesize=A4)
w, h = A4


def header(sub):
    c.setFillColorRGB(*NEGRO)
    c.rect(0, h - 2.6 * cm, w, 2.6 * cm, fill=1, stroke=0)
    c.setFillColorRGB(*ORO)
    c.setFont("Times-Bold", 20)
    c.drawCentredString(w / 2, h - 1.15 * cm, "C E N T R A L   M U T U O S")
    c.setStrokeColorRGB(*ORO)
    c.setLineWidth(1)
    c.line(w * 0.3, h - 1.45 * cm, w * 0.7, h - 1.45 * cm)
    c.setFont("Times-Bold", 9)
    c.drawCentredString(w / 2, h - 1.83 * cm, "C O N   C R E C E S")
    c.setFillColorRGB(0.62, 0.62, 0.62)
    c.setFont("Helvetica", 9)
    c.drawCentredString(w / 2, h - 2.32 * cm, sub)


def footer(pag):
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(2 * cm, 1.9 * cm, f"Emitido por el Administrador: {CARGO}")
    c.drawString(2 * cm, 1.5 * cm, f"Manual de Identidad Visual v1.0 · Generado el {HOY} · Documento oficial — Central Mutuos")
    c.drawRightString(w - 2 * cm, 1.5 * cm, f"Página {pag}")


def titulo(t, y):
    c.setFillColorRGB(*ORO)
    c.setFont("Times-Bold", 15)
    c.drawString(2 * cm, y, t)
    c.setStrokeColorRGB(*ORO)
    c.setLineWidth(0.7)
    c.line(2 * cm, y - 0.18 * cm, w - 2 * cm, y - 0.18 * cm)
    return y - 0.95 * cm


def parrafo(lineas, y, size=10):
    c.setFillColorRGB(0.12, 0.12, 0.12)
    c.setFont("Helvetica", size)
    for ln in lineas:
        c.drawString(2 * cm, y, ln)
        y -= 0.52 * cm
    return y


# ══ PÁGINA 1 — Portada + Formato 1 ══
header("Manual de Identidad Visual — Versión 1.0")
y = h - 3.6 * cm
c.setFillColorRGB(*NEGRO)
c.setFont("Times-Bold", 22)
c.drawCentredString(w / 2, y, "MANUAL DE MARCA")
c.setFont("Helvetica", 10)
c.setFillColorRGB(*GRIS)
c.drawCentredString(w / 2, y - 0.7 * cm, f"Identidad visual oficial e inamovible · Fecha de generación: {HOY} · Período: vigencia permanente")
y -= 1.9 * cm

y = titulo("1. FORMATO OFICIAL 1 — LOGO HORIZONTAL EJECUTIVO", y)
img1 = ImageReader("/app/frontend/public/logo-horizontal.png")
iw, ih = 11.5 * cm, 5.03 * cm
c.drawImage(img1, (w - iw) / 2, y - ih, iw, ih)
y -= ih + 0.7 * cm
y = parrafo([
    "Estructura obligatoria e inalterable: CENTRAL MUTUOS (arriba) · línea dorada horizontal (medio)",
    "· CON CRECES (abajo, agrandado +10%). Sin subtítulos ni texto adicional.",
    "Tipografía: Playfair Display (serif), peso 700 en el nombre y 400 en el lema. Fondo: negro absoluto #0A0A0A.",
    "Usos permitidos: barra lateral y login del sistema, encabezados de TODOS los correos automáticos,",
    "encabezados de reportes PDF y documentos exportables. En correos se reproduce en HTML/CSS puro,",
    "sin imágenes externas (Normativa Bloque 6).",
], y)

footer(1)
c.showPage()

# ══ PÁGINA 2 — Formato 2 + Paleta ══
header("Manual de Identidad Visual — Versión 1.0")
y = h - 3.6 * cm
y = titulo("2. FORMATO OFICIAL 2 — SELLO CIRCULAR \"DOBLE ARCO\"", y)
img2 = ImageReader("/app/frontend/public/app-icon-1024.png")
s = 5.6 * cm
c.drawImage(img2, (w - s) / 2, y - s, s, s)
y -= s + 0.7 * cm
y = parrafo([
    "Composición: \"CENTRAL MUTUOS\" curvado en el arco superior, \"CON CRECES\" curvado en el arco inferior",
    "y monograma CM al centro en degradado dorado. Fondo: negro absoluto #0A0A0A.",
    "Usos permitidos: foto de perfil de WhatsApp institucional, ícono de la aplicación móvil (iOS y Android),",
    "favicon del navegador e ícono de instalación (PWA). Exportado en: 1024/512/192/180/167/152/144/120/96/72/48 px.",
], y)
y -= 0.5 * cm

y = titulo("3. PALETA DE COLORES CORPORATIVA", y)
paleta = [("#0A0A0A", "Negro absoluto — fondo del logo", (0.039, 0.039, 0.039)),
          ("#141925", "Azul marino — fondos de interfaz", (0.078, 0.098, 0.145)),
          ("#C9A227", "Dorado mate — líneas y lema", (0.788, 0.635, 0.153)),
          ("#BF953F", "Dorado base del degradado", (0.749, 0.584, 0.247)),
          ("#FCF6BA", "Dorado claro del degradado", (0.988, 0.965, 0.729)),
          ("#AA771C", "Dorado profundo del degradado", (0.667, 0.467, 0.110)),
          ("#F8FAFC", "Blanco humo — tipografía sobre oscuro", (0.973, 0.980, 0.988))]
for hexc, desc, rgb in paleta:
    c.setFillColorRGB(*rgb)
    c.rect(2 * cm, y - 0.42 * cm, 1.1 * cm, 0.5 * cm, fill=1, stroke=1)
    c.setFillColorRGB(0.12, 0.12, 0.12)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(3.4 * cm, y - 0.3 * cm, hexc)
    c.setFont("Helvetica", 10)
    c.drawString(5.4 * cm, y - 0.3 * cm, desc)
    y -= 0.75 * cm

footer(2)
c.showPage()

# ══ PÁGINA 3 — Usos y regla de inmutabilidad ══
header("Manual de Identidad Visual — Versión 1.0")
y = h - 3.6 * cm
y = titulo("4. USOS PERMITIDOS Y PROHIBICIONES", y)
y = parrafo([
    "PERMITIDO:",
    "  •  Reproducir los formatos oficiales sin alteración de proporciones, colores ni tipografía.",
    "  •  Escalar los formatos manteniendo la relación de aspecto original.",
    "  •  Usar el logo horizontal sobre fondos oscuros (#0A0A0A a #141925).",
    "",
    "PROHIBIDO:",
    "  •  Cambiar el orden de los elementos (CENTRAL MUTUOS arriba, línea dorada, CON CRECES abajo).",
    "  •  Sustituir la tipografía Playfair Display o alterar los pesos aprobados.",
    "  •  Aplicar el logo sobre fondos claros sin autorización del Administrador.",
    "  •  Agregar subtítulos, descriptores o cualquier texto adicional al logo.",
    "  •  Usar imágenes del logo dentro de correos (deben reproducirse en HTML/CSS puro — Normativa Bloque 6).",
], y)
y -= 0.5 * cm

y = titulo("5. REGLA DE INMUTABILIDAD", y)
y = parrafo([
    "Esta identidad visual está registrada como normativa inamovible \"IDENTIDAD VISUAL OFICIAL\" en el",
    "Cerebro DashAI del sistema, con registro de auditoría. Ninguno de los dos formatos oficiales puede ser",
    "alterado, sustituido ni desactivado por ningún usuario, módulo o proceso automático sin la confirmación",
    "explícita del Administrador (Ethan), único rol autorizado para modificar las normativas del sistema.",
], y)

footer(3)
c.save()
print("PDF generado:", OUT)
