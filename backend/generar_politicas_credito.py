"""Versión pulida y profesional de las Políticas de Crédito MHE (con/sin subsidio),
sin mención de la institución de origen ni datos privados."""
import asyncio
import io
import uuid
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
from xhtml2pdf import pisa
from database import db

OUT = Path("/app/backend/storage/exports/pulidos")
OUT.mkdir(parents=True, exist_ok=True)

CSS = """
@page { size: letter; margin: 2.2cm 2.4cm; }
body { font-family: Helvetica, Arial, sans-serif; font-size: 9.5pt; color: #1a1a1a; line-height: 1.5; }
h1 { font-size: 16pt; text-align: center; letter-spacing: 2px; margin: 0 0 2px; color: #14213d; }
.sub { text-align: center; font-size: 9pt; color: #555; margin: 0 0 16px; }
h2 { font-size: 10.5pt; font-weight: 700; margin: 14px 0 5px; color: #14213d;
     border-bottom: 1.4pt solid #c9a227; padding-bottom: 3px; letter-spacing: 0.8px; }
table { width: 100%; border-collapse: collapse; margin: 4px 0 10px; }
td, th { border: 0.6pt solid #b9c0cc; padding: 4px 7px; font-size: 8.8pt; vertical-align: top; }
th { background-color: #14213d; color: #ffffff; font-weight: 700; text-align: left; }
td.c { width: 34%; font-weight: 700; background-color: #f4f6fa; }
td.eq { text-align: center; color: #555; }
.nota { font-size: 8pt; color: #555; margin-top: 12px; text-align: justify; }
.hr { border-bottom: 1.2pt solid #14213d; margin: 8px 0 14px; }
"""


def fila(cat, con, sin=None):
    sin_td = "<td class='eq'>Igual que con subsidio</td>" if sin is None else f"<td>{sin}</td>"
    return f"<tr><td class='c'>{cat}</td><td>{con}</td>{sin_td}</tr>"


HEAD = "<tr><th style='width:34%'>Criterio</th><th>Mutuo CON Subsidio</th><th>Mutuo SIN Subsidio</th></tr>"

HTML = f"""
<h1>POL&Iacute;TICAS DE CR&Eacute;DITO HIPOTECARIO</h1>
<p class="sub">Mutuo Hipotecario Endosable (MHE) &middot; Cuadro comparativo: operaciones con y sin subsidio habitacional</p>
<div class="hr"></div>

<h2>I. PROPIEDAD Y VIVIENDA</h2>
<table>{HEAD}
{fila("Tipo de vivienda", "Nuevas y usadas")}
{fila("Tipo de inmueble", "Casas y departamentos")}
{fila("Destino de la vivienda", "Habitacional")}
{fila("Valor m&iacute;nimo de la propiedad", "UF 1.000", "UF 1.250")}
{fila("Valor m&aacute;ximo de la propiedad", "UF 4.000", "UF 5.000")}
</table>

<h2>II. FINANCIAMIENTO</h2>
<table>{HEAD}
{fila("% m&aacute;ximo a financiar", "80%")}
{fila("Monto m&aacute;ximo del cr&eacute;dito", "UF 3.200", "UF 4.000")}
{fila("Monto m&iacute;nimo a financiar", "UF 800", "UF 1.000")}
{fila("Pie m&iacute;nimo", "20%")}
{fila("Plazo (a&ntilde;os)", "M&iacute;n. 20 &mdash; M&aacute;x. 40 a&ntilde;os (plazos menores se revisan en comit&eacute; de excepci&oacute;n)", "M&iacute;n. 20 &mdash; M&aacute;x. 30 a&ntilde;os")}
{fila("Relaci&oacute;n dividendo / renta", "&le; 40%", "&le; 35%")}
{fila("Carga financiera", "&le; 55%", "&le; 50%")}
{fila("Renta m&iacute;nima", "UF 15 titular &middot; UF 25 renta conjunta", "UF 25")}
</table>

<h2>III. PERFIL DEL SOLICITANTE</h2>
<table>{HEAD}
{fila("Nacionalidad", "Chilena, o extranjero con Permanencia Definitiva")}
{fila("Actividad", "Dependiente &middot; Independiente &middot; Jubilado / pensi&oacute;n de renta vitalicia o fija definitiva")}
{fila("Antig&uuml;edad laboral", "Dependiente: 3 meses (contrato indefinido) &middot; 6 meses (plazo fijo, obra o faena) &middot; Independiente: 3 a&ntilde;os", "6 meses (dependiente) &middot; resto igual")}
{fila("Continuidad laboral", "6 meses (contrato indefinido) &middot; 12 meses (obra o faena)", "12 meses (contrato indefinido) &middot; 24 meses (obra o faena)")}
{fila("Tipo de contrato", "Indefinido &middot; Plazo fijo &middot; A contrata &middot; Por obra o faena")}
{fila("Edad m&iacute;nima de ingreso", "21 a&ntilde;os")}
{fila("Edad m&aacute;xima de ingreso", "65 a&ntilde;os")}
{fila("Edad m&aacute;xima al t&eacute;rmino del cr&eacute;dito", "79 a&ntilde;os y 360 d&iacute;as")}
{fila("Haberes no imponibles", "Hasta $200.000")}
{fila("Vi&aacute;ticos, asignaciones de zona o propinas", "Hasta el 50% del total de la renta")}
</table>

<h2>IV. COMPORTAMIENTO FINANCIERO (REQUISITOS EXCLUYENTES)</h2>
<table>{HEAD}
{fila("Deuda directa morosa", "No admite")}
{fila("Deuda directa vencida", "No admite")}
{fila("Deuda directa castigada", "No admite")}
{fila("Deuda indirecta (morosa, vencida o castigada)", "No admite")}
{fila("Mora comercial", "No admite")}
{fila("Protestos vigentes", "No admite")}
{fila("Pagar&eacute;s impagos", "No admite")}
{fila("Sujeto de alto riesgo (SAR)", "No admite")}
</table>

<h2>V. CODEUDORES Y COMPLEMENTO DE RENTA</h2>
<table>{HEAD}
{fila("Tipos de codeudor admitidos", "C&oacute;nyuge o conviviente con hijo en com&uacute;n &middot; Codeudor directo: padres, hijos o hermanos &middot; Codeudor tercero: conviviente sin hijo en com&uacute;n, compa&ntilde;eros de trabajo o amigos")}
{fila("Complemento de renta", "Seg&uacute;n reglas generales",
      "Padres y hermanos; c&oacute;nyuge y pareja con hijos en com&uacute;n se eval&uacute;an con ratios familiares. Con codeudor directo, el titular no debe exceder una carga financiera de 70%. Con codeudor tercero, el titular no debe exceder una carga financiera de 60% y debe acreditar al menos el 50% de la relaci&oacute;n dividendo/renta")}
</table>

<p class="nota">Documento de referencia interna que resume los criterios de admisibilidad vigentes para operaciones
de Mutuo Hipotecario Endosable, en sus modalidades con y sin subsidio habitacional. Las condiciones indicadas
est&aacute;n sujetas a evaluaci&oacute;n crediticia y a la aprobaci&oacute;n final del comit&eacute; correspondiente.</p>
"""


async def main():
    full = f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{HTML}</body></html>"
    buf = io.BytesIO()
    if pisa.CreatePDF(full, dest=buf, encoding="utf-8").err:
        raise RuntimeError("pisa err")
    p = OUT / "Politicas_Credito_MHE.pdf"
    p.write_bytes(buf.getvalue())
    token = uuid.uuid4().hex
    await db.descargas_seguras.insert_one({"token": token, "path": str(p), "filename": p.name})
    print(f"/api/descarga-segura/{token}")

asyncio.run(main())
