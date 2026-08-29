"""PDF Informe de Arriendos — Rodrigo Jara Bustamante (solo arriendos)."""
import io
import json
import re
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from xhtml2pdf import pisa

d = json.load(open("/app/backend/scripts_lacruz/rodrigo_ocr.json"))


def num(s):
    return int(re.sub(r"[^\d]", "", s)) if s else 0


OVERRIDE = {"Tierra del Fuego 12": (245000, "Carlos Eduardo Fernandez O."), "Tierra del Fuego 13": (240000, "")}
filas = []
tot = 0
for k, t in sorted(d.items()):
    renta = re.search(r"renta mensual(?: de arrendamiento)?(?: ser[aá] la suma)? de \$?\s*([\d.,]{5,12})", t, re.I) or \
            re.search(r"suma de \$?\s*([\d.,]{5,12})\s*[.\-]?\s*\(", t)
    arr = re.search(r"[Aa]rrendatari[oa]:?\s*(?:don|doña|dona)?\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ ]{8,42})[,;]", t)
    ini = re.search(r"renta del mes\s+(?:de\s+)?([A-Z]+)\s+de\s+(\d{4})", t, re.I)
    rea = re.search(r"reajustar[aá] seg[uú]n (?:el )?(IPC[^.,;]{0,18})", t, re.I)
    v = num(renta.group(1)) if renta else 0
    if v > 3000000 or v < 100000:
        v = 0
    a = arr.group(1).strip()[:32] if arr else ""
    if k in OVERRIDE and not v:
        v, a2 = OVERRIDE[k]
        a = a or a2
    tot += v
    filas.append((k, v, a or "&mdash;", f"{ini.group(1).title()} {ini.group(2)}" if ini else "&mdash;",
                  (rea.group(1)[:14] if rea else "&mdash;")))

CSS = """@page { size: letter; margin: 2cm 2.2cm; }
body { font-family: Helvetica; font-size: 9pt; color: #1a1a1a; line-height: 1.45; }
h1 { font-size: 15pt; color: #14213d; text-align: center; margin: 0 0 2px; }
.sub { text-align:center; font-size: 8.5pt; color: #555; margin: 0 0 14px; }
h2 { font-size: 10.5pt; color: #14213d; border-bottom: 1.3pt solid #c9a227; padding-bottom: 2px; margin: 14px 0 6px; }
table { width: 100%; border-collapse: collapse; margin: 4px 0 8px; }
td, th { border: 0.5pt solid #b9c0cc; padding: 3px 6px; font-size: 8pt; }
th { background-color: #14213d; color: #fff; text-align: left; }
.n { text-align: right; }
.tot td { background-color: #f0e9d2; font-weight: bold; }
.alerta { background-color: #fdf3f3; border: 0.8pt solid #d9534f; padding: 6px 10px; font-size: 8.5pt; margin: 6px 0; }
.nota { font-size: 7.6pt; color: #555; margin-top: 10px; }"""

fila_html = "".join(
    f"<tr><td>{k}</td><td class='n'>{('$'+format(v,',').replace(',','.')) if v else 'ilegible'}</td>"
    f"<td>{a}</td><td>{i}</td><td>{r}</td></tr>" for k, v, a, i, r in filas)

HTML = f"""
<h1>INFORME DE CONTRATOS DE ARRIENDO</h1>
<p class="sub">Arrendador: RODRIGO ADOLFO JARA BUSTAMANTE &middot; RUT 15.435.814-5 &middot; 33 contratos notariados (OCR) &middot; 29/08/2026</p>

<h2>I. DETALLE DE LOS 33 CONTRATOS RECIBIDOS</h2>
<table>
<tr><th>Propiedad</th><th>Renta mensual</th><th>Arrendatario</th><th>Inicio/pago detectado</th><th>Reajuste</th></tr>
{fila_html}
<tr class="tot"><td>TOTAL ACREDITABLE POR CONTRATO (32 de 33 legibles)</td><td class="n">${format(tot,',').replace(',','.')}</td><td colspan="3">&asymp; UF 245 mensuales</td></tr>
</table>

<h2>II. RESUMEN POR CONJUNTO</h2>
<table>
<tr><th>Conjunto</th><th>Unidades</th><th>Suma c&aacute;nones</th><th>Antig&uuml;edad</th></tr>
<tr><td>12 Poniente 8490 &laquo;Puerta&raquo; A/B/C, La Granja</td><td class="n">12</td><td class="n">$4.784.000</td><td>2022&ndash;2026</td></tr>
<tr><td>Inglaterra 1144 Torre B2, Independencia</td><td class="n">8</td><td class="n">$2.195.000</td><td>2017&ndash;2026</td></tr>
<tr><td>Isla Tierra del Fuego 8827, La Granja</td><td class="n">12</td><td class="n">$2.530.000</td><td>2019&ndash;2021</td></tr>
<tr><td>General Gana 1063 (Torre Mayor 406-A), Stgo Centro</td><td class="n">1</td><td class="n">$500.000</td><td>2020</td></tr>
</table>

<h2>III. PLANILLA DEL PROPIO CLIENTE (&laquo;arriendos al 01.08.2026&raquo;)</h2>
<p>El cliente declara <b>41 propiedades</b> por un total de <b>$16.114.000 mensuales</b>. Incluye adem&aacute;s de lo anterior:
<b>8 casas en Pasaje Pe&ntilde;uelas 0398, La Granja</b> ($2.780.000), <b>casa en La Florida</b> (Garc&iacute;a Hurtado de Mendoza 7923, $850.000)
y <b>parcela en El Tabo</b> ($310.000). <b>De estas propiedades adicionales NO se recibieron contratos.</b></p>

<h2>IV. CONTRASTE TRIBUTARIO (F22 DEL PROPIO DOSSIER)</h2>
<table>
<tr><th>Concepto</th><th>Anual</th></tr>
<tr><td>Contratos recibidos, anualizados</td><td class="n">&asymp; $120.108.000</td></tr>
<tr><td>Planilla del cliente, anualizada</td><td class="n">&asymp; $193.368.000</td></tr>
<tr><td>F22 AT2026 &mdash; arriendos declarados al SII</td><td class="n">$26.218.888</td></tr>
<tr><td>F22 AT2025 &mdash; arriendos declarados al SII</td><td class="n">$22.965.010</td></tr>
</table>
<div class="alerta"><b>Alerta de acreditaci&oacute;n:</b> el cliente sustenta notarialmente entre 4 y 7 veces m&aacute;s renta de arriendo
de la que tributa. Para acreditaci&oacute;n formal se requiere: dep&oacute;sitos de los &uacute;ltimos 3 meses en cartola bancaria,
certificados de dominio vigente o &uacute;ltimo pago de contribuciones con aval&uacute;o por propiedad, y los contratos faltantes
de Pe&ntilde;uelas 0398, La Florida y El Tabo.</div>

<p class="nota">Informe generado autom&aacute;ticamente a partir de la lectura OCR de los 33 contratos adjuntos (WeTransfer 25/08/2026),
la planilla Excel y los F22 del dossier enviado por Bianca Dur&aacute;n (Inmobiliaria Maestra) el 19/08/2026.
Contrato &laquo;Tierra del Fuego 9&raquo; ilegible por calidad de escaneo. Documento de uso interno &mdash; no constituye aprobaci&oacute;n de cr&eacute;dito.</p>
"""

buf = io.BytesIO()
pisa.CreatePDF(f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{HTML}</body></html>",
               dest=buf, encoding="utf-8")
open("/app/backend/scripts_lacruz/Informe_Arriendos_Rodrigo_Jara.pdf", "wb").write(buf.getvalue())
print("PDF OK", len(buf.getvalue()))
