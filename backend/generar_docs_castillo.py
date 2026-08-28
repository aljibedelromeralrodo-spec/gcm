"""Genera versiones pulidas y profesionales de la Carta Oferta y el Compromiso de
Compraventa (caso Castillo/Quilicura), sin logotipo ni mención de Central Mutuos."""
import asyncio
import io
import os
import uuid
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
from xhtml2pdf import pisa
from database import db

OUT = Path("/app/backend/storage/exports/pulidos")
OUT.mkdir(parents=True, exist_ok=True)

BASE_CSS = """
@page { size: letter; margin-top: 2.6cm; margin-bottom: 2.6cm; margin-left: 3cm; margin-right: 3cm; }
body { font-family: 'Times New Roman', Times, serif; font-size: 11pt; color: #000; line-height: 1.65; }
h1 { font-size: 17pt; text-align: center; letter-spacing: 2px; font-weight: 700; margin: 0 0 4px; }
.sub { text-align: center; font-size: 9.5pt; color: #000; margin: 0 0 22px; }
h2 { font-size: 11.5pt; font-weight: 700; margin: 16px 0 6px; letter-spacing: 0.5px; }
p { margin: 0 0 11px; text-align: justify; }
table { width: 100%; border-collapse: collapse; margin: 6px 0 14px; }
td, th { border: 0.8pt solid #000; padding: 5px 8px; font-size: 10.5pt; }
th { background-color: #f2f2f2; text-align: left; font-weight: 700; }
.num { text-align: right; }
.total td { font-weight: 700; background-color: #f2f2f2; }
.firma { text-align: center; padding-top: 46px; border: none; }
.hr { border-bottom: 1.2pt solid #000; margin: 14px 0 18px; }
"""

COMPROMISO = """
<h1>COMPROMISO DE COMPRAVENTA</h1>
<p class="sub">Documento preparatorio de escritura p&uacute;blica &middot; Valor UF de referencia: $40.868,50 al 27 de agosto de 2026</p>
<div class="hr"></div>
<p>En <b>Quilicura</b>, a 27 de agosto de 2026, comparecen: por una parte, don <b>JORGE ALEJANDRO GALLEGOS ASCENCIO</b>, chileno, empleado, c&eacute;dula nacional de identidad N&deg; <b>10.800.689-7</b>, con domicilio en Pasaje Cuba N&deg; 700, comuna de Quilicura, en adelante &ldquo;el Vendedor&rdquo;; y por la otra, do&ntilde;a <b>CATALINA ANDREA CASTILLO PAUVIE</b>, chilena, educadora de p&aacute;rvulos, soltera, c&eacute;dula nacional de identidad N&deg; <b>20.064.076-4</b>, con domicilio en Los L&iacute;quenes N&deg; 5513, en adelante &ldquo;el Comprador&rdquo;; quienes acuerdan el siguiente compromiso de compraventa:</p>
<h2>PRIMERO &mdash; Objeto.</h2>
<p>El Vendedor se obliga a vender, ceder y transferir al Comprador, quien se obliga a comprar, aceptar y adquirir para s&iacute;, el inmueble consistente en casa habitaci&oacute;n ubicada en <b>Pasaje Cuba N&deg; 700, Conjunto Jard&iacute;n del Norte</b>, comuna de <b>Quilicura</b>, Rol de Aval&uacute;o N&deg; <b>01200-00018</b>. El dominio se encuentra inscrito a fojas <b>45.231</b>, n&uacute;mero <b>43.651</b>, del a&ntilde;o <b>2001</b>, en el Registro de Propiedad del Conservador de Bienes Ra&iacute;ces de <b>Santiago</b>.</p>
<h2>SEGUNDO &mdash; Precio y forma de pago.</h2>
<p>El precio de la venta es la suma de <b>UF 1.925,00</b> (mil novecientas veinticinco Unidades de Fomento), equivalente a <b>$78.671.863</b> al valor UF de referencia. De este monto, el Comprador ha pagado por concepto de pie la suma de <b>UF 39,79</b>, equivalente a <b>$1.626.158</b>, en efectivo, seg&uacute;n se declara en la cl&aacute;usula S&Eacute;PTIMA del presente instrumento.</p>
<p>El saldo de precio, ascendente a <b>UF 1.885,21</b>, equivalente a <b>$77.045.705</b> al valor UF de referencia, se enterar&aacute; al momento de la firma de la escritura definitiva de compraventa conforme a la siguiente estructura de financiamiento:</p>
<table>
<tr><th>Componente</th><th class="num">Monto (UF)</th><th class="num">Equivalencia ($)</th></tr>
<tr><td>Cr&eacute;dito hipotecario, otorgado por la instituci&oacute;n financiera que apruebe la operaci&oacute;n</td><td class="num">1.540,00</td><td class="num">62.937.490</td></tr>
<tr><td>Subsidio habitacional D.S. N&deg; 1</td><td class="num">250,00</td><td class="num">10.217.125</td></tr>
<tr><td>Ahorro del Comprador</td><td class="num">95,21</td><td class="num">3.891.090</td></tr>
<tr><td>Pie pagado en este acto (cl&aacute;usula S&Eacute;PTIMA)</td><td class="num">39,79</td><td class="num">1.626.158</td></tr>
<tr class="total"><td>PRECIO TOTAL DE LA COMPRAVENTA</td><td class="num">1.925,00</td><td class="num">78.671.863</td></tr>
</table>
<p><b>Garant&iacute;a del saldo:</b> el pago del saldo de precio quedar&aacute; garantizado mediante instrucciones notariales irrevocables o vale vista bancario, a elecci&oacute;n de las partes, entregadas en la notar&iacute;a al momento de la firma de la escritura definitiva.</p>
<h2>TERCERO &mdash; Condici&oacute;n suspensiva.</h2>
<p>La celebraci&oacute;n de la compraventa definitiva queda expresamente supeditada a la aprobaci&oacute;n del cr&eacute;dito hipotecario del Comprador. Las partes se obligan a suscribir la escritura p&uacute;blica de compraventa dentro del plazo de <b>60 d&iacute;as corridos</b> contados desde la comunicaci&oacute;n formal de dicha aprobaci&oacute;n. Si el cr&eacute;dito no fuere aprobado dentro del plazo se&ntilde;alado, este instrumento quedar&aacute; sin efecto de pleno derecho, restituy&eacute;ndose a las partes lo que hubieren entregado, sin ulterior responsabilidad.</p>
<h2>CUARTO &mdash; Cl&aacute;usula penal.</h2>
<p>Si cualquiera de las partes se negare injustificadamente a suscribir la escritura definitiva o se arrepintiere de la presente convenci&oacute;n, deber&aacute; pagar a la otra, a t&iacute;tulo de avaluaci&oacute;n anticipada de perjuicios, una multa de <b>UF 10,00</b> (diez Unidades de Fomento), equivalente a <b>$408.685</b> al valor UF de referencia, sin perjuicio del derecho de la parte diligente de exigir adem&aacute;s el cumplimiento forzado del contrato.</p>
<h2>QUINTO &mdash; Gastos.</h2>
<p>Los gastos notariales, impuestos y derechos que irrogue la celebraci&oacute;n de la compraventa definitiva ser&aacute;n solventados por ambas partes en proporciones iguales. Los gastos de inscripci&oacute;n en el Conservador de Bienes Ra&iacute;ces ser&aacute;n de cargo del Comprador.</p>
<h2>SEXTO &mdash; Domicilio y ejemplares.</h2>
<p>Para todos los efectos legales derivados del presente instrumento, las partes fijan su domicilio en la comuna de <b>Quilicura</b> y se someten a la competencia de sus Tribunales Ordinarios de Justicia. El presente compromiso se firma en dos ejemplares del mismo tenor, quedando uno en poder de cada parte.</p>
<h2>S&Eacute;PTIMO &mdash; Declaraci&oacute;n de pago y finiquito del pie.</h2>
<p>El Vendedor declara haber recibido del Comprador, de manera &iacute;ntegra, total y oportuna, la suma de <b>UF 39,79</b>, equivalente a <b>$1.626.158</b> al valor UF de referencia ($40.868,50 al 27/08/2026), pagada en efectivo, por concepto de pie del precio de la compraventa. En consecuencia, el Vendedor otorga al Comprador el m&aacute;s amplio, completo y total finiquito respecto de dicha suma, declar&aacute;ndola &iacute;ntegramente pagada y renunciando expresamente a toda acci&oacute;n, cobro o reclamaci&oacute;n posterior derivada de su pago.</p>
<br/><br/>
<table style="margin-top:40px"><tr>
<td class="firma" style="border:none;width:50%">____________________________________<br/><b>JORGE ALEJANDRO GALLEGOS ASCENCIO</b><br/>RUT 10.800.689-7<br/>VENDEDOR</td>
<td class="firma" style="border:none;width:50%">____________________________________<br/><b>CATALINA ANDREA CASTILLO PAUVIE</b><br/>RUT 20.064.076-4<br/>COMPRADOR</td>
</tr></table>
"""

CARTA = """
<h1>CARTA DE OFERTA DE COMPRA</h1>
<p class="sub">Santiago de Chile &middot; 27 de agosto de 2026 &middot; Valor UF de referencia: $40.868,50</p>
<div class="hr"></div>
<h2>I. ANTECEDENTES DEL CLIENTE</h2>
<table>
<tr><th style="width:38%">Nombre del cliente</th><td><b>CATALINA ANDREA CASTILLO PAUVIE</b></td></tr>
<tr><th>RUT</th><td>20.064.076-4</td></tr>
</table>
<h2>II. ANTECEDENTES DEL VENDEDOR</h2>
<table>
<tr><th style="width:38%">Nombre del vendedor</th><td><b>JORGE ALEJANDRO GALLEGOS ASCENCIO</b></td></tr>
<tr><th>RUT</th><td>10.800.689-7</td></tr>
</table>
<h2>III. INDIVIDUALIZACI&Oacute;N DE LA PROPIEDAD</h2>
<table>
<tr><th style="width:38%">Tipo de propiedad</th><td>Casa &mdash; Vivienda</td></tr>
<tr><th>Proyecto / Conjunto</th><td>Jard&iacute;n del Norte</td></tr>
<tr><th>Direcci&oacute;n</th><td>Pasaje Cuba N&deg; 700</td></tr>
<tr><th>Comuna / Ciudad</th><td>Quilicura, Santiago &mdash; Regi&oacute;n Metropolitana</td></tr>
<tr><th>Rol de aval&uacute;o</th><td>01200-00018</td></tr>
</table>
<h2>IV. ESTRUCTURA DE FINANCIAMIENTO</h2>
<table>
<tr><th>Componente</th><th class="num" style="width:22%">Monto (UF)</th></tr>
<tr><td>Precio de venta de la propiedad</td><td class="num"><b>1.925,00</b></td></tr>
<tr><td>Subsidio habitacional (D.S. N&deg; 1 &mdash; Subsidio Base)</td><td class="num">250,00</td></tr>
<tr><td>Ahorro del cliente</td><td class="num">95,21</td></tr>
<tr><td>Pie</td><td class="num">39,79</td></tr>
<tr><td>Cr&eacute;dito hipotecario</td><td class="num">1.540,00</td></tr>
<tr class="total"><td>TOTAL FINANCIAMIENTO (Subsidio + Ahorro + Pie + Cr&eacute;dito)</td><td class="num">1.925,00</td></tr>
</table>
<p style="margin-top:18px">La presente carta de oferta resume las condiciones comerciales de la operaci&oacute;n de compraventa y financiamiento de la propiedad individualizada, y constituye un documento informativo preparatorio, sujeto a la aprobaci&oacute;n final del cr&eacute;dito hipotecario por parte de la instituci&oacute;n financiera.</p>
<br/><br/>
<table style="margin-top:46px"><tr>
<td class="firma" style="border:none">____________________________________<br/><b>CATALINA ANDREA CASTILLO PAUVIE</b><br/>RUT 20.064.076-4<br/>CLIENTE</td>
</tr></table>
"""


def render(html, path):
    full = f"<html><head><meta charset='utf-8'><style>{BASE_CSS}</style></head><body>{html}</body></html>"
    buf = io.BytesIO()
    err = pisa.CreatePDF(full, dest=buf, encoding="utf-8").err
    if err:
        raise RuntimeError(f"pisa err {path}")
    Path(path).write_bytes(buf.getvalue())


async def main():
    p1 = OUT / "Compromiso_Compraventa_Castillo_Quilicura.pdf"
    p2 = OUT / "Carta_Oferta_Castillo.pdf"
    render(COMPROMISO, p1)
    render(CARTA, p2)
    urls = []
    for p in (p1, p2):
        token = uuid.uuid4().hex
        await db.descargas_seguras.insert_one({"token": token, "path": str(p), "filename": p.name})
        urls.append(f"/api/descarga-segura/{token}")
    print("\n".join(urls))

asyncio.run(main())
