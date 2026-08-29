"""Correo formal Alianza Ecomac (cuerpo persuasivo) + 2 PDFs adjuntos: Felicitaciones y Clientes Enviados."""
# ruff: noqa: F821
import io, base64
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
import sys
sys.path.insert(0, "/app/backend")
from xhtml2pdf import pisa

src = open("/app/backend/scripts_lacruz/pdf_informe_ecomac_final.py").read()
exec(src.split('CSS = """')[0])

CSS_BASE = """@page { size: letter; margin: 1.7cm 1.9cm; }
body { font-family: Helvetica; font-size: 9pt; color: #1a1a1a; line-height: 1.5; }
h1 { font-size: 15pt; color: #14213d; text-align: center; margin: 0 0 2px; }
.sub { text-align:center; font-size: 8.4pt; color: #555; margin: 0 0 13px; }
h2 { font-size: 10.5pt; color: #14213d; border-bottom: 1.3pt solid #c9a227; padding-bottom: 2px; margin: 14px 0 6px; }
p { margin: 4px 0; text-align: justify; }
table { width: 100%; border-collapse: collapse; margin: 4px 0 8px; }
td, th { border: 0.4pt solid #b9c0cc; padding: 2.5px 4px; font-size: 7.4pt; }
th { background-color: #14213d; color: #fff; text-align: left; }
.n { text-align: right; }
.kpi td { background-color: #f0e9d2; font-weight: bold; font-size: 8.6pt; text-align:center; padding:6px; border:0.6pt solid #c9a227; }
.verde2 td { background-color: #c8e6c9; font-weight: bold; }
.verde1 td { background-color: #dcedc8; }
.verde0 td { background-color: #f1f8e9; }
.rojo td { background-color: #fdecea; }
.gris td { color: #888; }
.mes td { background-color: #e8eaf0; font-weight: bold; font-size: 7.8pt; color:#14213d; }
.cita { background-color: #f6f8f6; border-left: 2.2pt solid #c9a227; padding: 5px 9px; font-size: 8.6pt; margin: 5px 0; font-style: italic; }
.quien { font-style: normal; font-weight: bold; color: #14213d; }
.pop { border: none; text-align: center; vertical-align: top; padding: 6px; }
.cap { font-size: 7.2pt; color: #555; }
.destacado { background-color: #eef5ee; border: 0.8pt solid #2e7d32; padding: 8px 11px; font-size: 8.8pt; margin: 7px 0; }
.nota { font-size: 7.3pt; color: #555; margin-top: 10px; }"""


def make_pdf(html, path):
    buf = io.BytesIO()
    pisa.CreatePDF(f"<html><head><meta charset='utf-8'><style>{CSS_BASE}</style></head><body>{html}</body></html>",
                   dest=buf, encoding="utf-8")
    open(path, "wb").write(buf.getvalue())
    print("PDF OK", path, len(buf.getvalue()))
    return buf.getvalue()


# ═══ PDF 1: FELICITACIONES ═══
TDIR = "/app/backend/scripts_lacruz/testimonios"
IMGS = [("w05.jpg", "Claudia Arias — Los Maitenes"), ("w11.jpg", "Edgardo Guzmán — escriturado"),
        ("w08.jpg", "Cristian Solís — entrega anticipada"), ("w10.jpg", "Alejandro P."),
        ("w06.jpg", "Jordan"), ("w02.jpg", "Francisca"), ("w01.jpg", "Alison"),
        ("w03.jpg", "Sandra — DS19"), ("w04.jpg", "Karina"), ("w07.jpg", "Jonathan M."),
        ("w09.jpg", "Jorge Jiménez — se despide agradecido")]
pop_rows = ""
for i in range(0, len(IMGS), 2):
    par = IMGS[i:i + 2]
    tds = "".join(f"<td class='pop'><img src='{TDIR}/{f}' style='width:6.4cm'/><br/><span class='cap'>{cap}</span></td>"
                  for f, cap in par)
    if len(par) == 1:
        tds += "<td class='pop'></td>"
    pop_rows += f"<tr>{tds}</tr>"

HTML_FEL = f"""
<h1>FELICITACIONES DE CLIENTES ECOMAC</h1>
<p class="sub">Testimonios reales de compradores acompa&ntilde;ados por Central Mutuos &middot; Septiembre 2024 &rarr; Agosto 2026</p>
<p>Aqu&iacute; van algunas conversaciones al azar de clientes que han comprado &mdash;y algunos que incluso no han comprado&mdash;
que han quedado <b>completamente satisfechos y agradecidos por la gesti&oacute;n realizada por nuestros ejecutivos</b>, lo que refleja
un compromiso importante con Ecomac, con su marca y con el cliente para conseguir la vivienda propia.</p>
<div class="cita">&laquo;Holaaa, qu&eacute; gusto saber de ti. Gracias por tus buenos deseos. Agradezco tambi&eacute;n toda tu gesti&oacute;n&raquo;
<br/><span class="quien">&mdash; Claudia Arias, Los Maitenes &middot; primera cliente del canal, a&uacute;n en contacto un a&ntilde;o despu&eacute;s</span></div>
<div class="cita">&laquo;El gusto es m&iacute;o, ha sido un proceso extenuante, pero agradezco en el alma su apoyo. Es una decisi&oacute;n
para toda la vida, por eso la insistencia. Usted siempre mantuvo una palabra de aliento&raquo;
<br/><span class="quien">&mdash; Edgardo Guzm&aacute;n, escriturado</span></div>
<div class="cita">&laquo;Ya me entregaron el depto, una entrega anticipada&hellip; Le agradezco mucho la oportunidad, que tanto luchamos por ello&raquo;
<br/><span class="quien">&mdash; Cristian Sol&iacute;s</span></div>
<div class="cita">&laquo;Lo que m&aacute;s agradezco es su ayuda en el proceso. Es algo emocionante de verdad, a&uacute;n no me la creo del todo&raquo;
<br/><span class="quien">&mdash; Alejandro P.</span></div>
<div class="cita">&laquo;El apoyo y los consejos se agradecen, ya que estaba nulo en el tema de tramitaci&oacute;n. Estoy muy agradecido&raquo;
<br/><span class="quien">&mdash; Jordan</span></div>
<div class="cita">&laquo;Le agradezco tanto sus gestiones y paciencia, de todo coraz&oacute;n&raquo;
<br/><span class="quien">&mdash; Francisca</span></div>
<div class="cita">&laquo;Le agradezco mucho por su apoyo&hellip; gracias, valoro eso&raquo;
<br/><span class="quien">&mdash; Alison</span></div>
<div class="cita">&laquo;Ha sido un gusto&hellip; nooo, te agradezco a ti. Ojal&aacute; podamos vernos un d&iacute;a&raquo;
<br/><span class="quien">&mdash; Sandra, cliente DS19</span></div>
<div class="cita">&laquo;De veras aprecio mucho lo que hizo por m&iacute;. Recuerde esto, lo volver&eacute; a buscar&raquo;
<br/><span class="quien">&mdash; Karina</span></div>
<div class="cita">&laquo;Muchas gracias a usted, igual, por su gesti&oacute;n&raquo;
<br/><span class="quien">&mdash; Jonathan M.</span></div>
<div class="cita">&laquo;Agradezco su dedicaci&oacute;n y la deferencia de acompa&ntilde;arme en el proceso. Estamos muy agradecidos&raquo;
<br/><span class="quien">&mdash; Jorge Jim&eacute;nez &mdash; incluso al desistir por motivos personales, se despide agradecido:
as&iacute; se cuida la marca Ecomac en cada contacto</span></div>
<div class="destacado"><b>Once voces, un mismo mensaje:</b> el cliente Ecomac que pasa por Central Mutuos se siente acompa&ntilde;ado,
informado y respetado &mdash; desde la primera evaluaci&oacute;n hasta la entrega de llaves.</div>
<h2>CONVERSACIONES ORIGINALES</h2>
<table style="border:none">{pop_rows}</table>
"""
pdf_fel = make_pdf(HTML_FEL, "/app/backend/scripts_lacruz/Felicitaciones_Clientes_Ecomac.pdf")

# ═══ PDF 2: TODOS LOS CLIENTES ENVIADOS ═══
TH = ("<tr><th>Fecha</th><th>Cliente</th><th>RUT</th><th>Ejecutiva/o</th>"
      "<th>1&ordf; resp.</th><th>Estado</th><th>Escritura</th></tr>")
hf2 = lambda h: (f"{h:.0f} h" if h is not None and h < 48 else f"{h/24:.0f} d" if h is not None else "—")


def fila(c):
    return (f"<tr class='{c['css']}'><td>{c['fecha']}</td><td>{c['nombre'][:38]}</td><td>{c['rut']}</td>"
            f"<td>{c['ejec'][:22]}</td><td class='n'>{hf2(c['horas'])}</td>"
            f"<td>{c['estado']}</td><td>{c['fecha_esc']}</td></tr>")


bloques_hist = ""
for mes in sorted({c["mes"] for c in casos}):
    cs = [c for c in casos if c["mes"] == mes]
    bloques_hist += (f"<tr class='mes'><td colspan='7'>{mes_es(mes)} &mdash; {len(cs)} enviados &middot; "
                     f"{sum(1 for c in cs if c['css'].startswith('verde'))} en verde</td></tr>"
                     + "".join(fila(c) for c in cs))
LEY = ("<p class='cap'>Leyenda: <span style='background:#c8e6c9'>&nbsp;FIRMADA/T&Iacute;TULOS&nbsp;</span> "
       "<span style='background:#dcedc8'>&nbsp;EN ESCRITURACI&Oacute;N&nbsp;</span> "
       "<span style='background:#f1f8e9'>&nbsp;APROBADO&nbsp;</span> "
       "<span style='background:#fdecea'>&nbsp;RECHAZADO&nbsp;</span> &middot; gris = sin respuesta detectada</p>")

HTML_CLI = f"""
<h1>CLIENTES ENVIADOS POR ECOMAC A CENTRAL MUTUOS</h1>
<p class="sub">Registro completo cliente por cliente &middot; Septiembre 2024 &rarr; Agosto 2026 &middot; {len(casos)} clientes &middot; solo gesti&oacute;n de esta oficina (sin De Manet)</p>
<table class="kpi"><tr>
<td>{len(casos)}<br/>clientes enviados</td>
<td>{verdes_tot}<br/>en verde</td>
<td>{len(esc)}<br/>en escrituraci&oacute;n</td>
<td>{firmas_tot}<br/>firma/t&iacute;tulos</td>
<td>{mediana_h:.1f} h<br/>mediana 1&ordf; respuesta</td>
</tr></table>
{LEY}
<table>{TH}{bloques_hist}</table>
<p class="nota">Registro obtenido del historial completo de correos de la gesti&oacute;n (11.031 correos), considerando exclusivamente
clientes y proyectos Ecomac. Central Mutuos.</p>
"""
pdf_cli = make_pdf(HTML_CLI, "/app/backend/scripts_lacruz/Clientes_Enviados_Ecomac.pdf")

RESUMEN_TABLA = f"""
<table border="1" cellpadding="6" cellspacing="0" width="100%"
 style="border-collapse:collapse;border:1px solid #b9c0cc;font-size:13px;margin:10px 0">
<tr style="background:#14213d;color:#ffffff"><th colspan="2" style="padding:7px;text-align:center">
ALIANZA CENTRAL MUTUOS &ndash; ECOMAC &middot; RESUMEN EJECUTIVO (SEP 2024 &rarr; AGO 2026)</th></tr>
<tr><td><b>Total escriturado del canal</b></td>
<td style="text-align:right"><b>UF 180.000+ &nbsp;(&asymp; $7.500 millones de pesos)</b></td></tr>
<tr style="background:#f6f8f6"><td><b>Tiempo de respuesta</b></td>
<td style="text-align:right"><b>Mediana 11,3 horas</b> &middot; 75% de tasa de respuesta y subiendo</td></tr>
<tr><td><b>Clientes evaluados</b></td>
<td style="text-align:right"><b>{len(casos)}</b> derivados por sus ejecutivas</td></tr>
<tr style="background:#f6f8f6"><td><b>Apoyo a la venta en verde</b></td>
<td style="text-align:right"><b>{verdes_tot} clientes aprobados o camino a escritura</b></td></tr>
<tr><td><b>Aprobaciones &rarr; escrituraci&oacute;n</b></td>
<td style="text-align:right">{verdes_tot} en verde &rarr; <b>{len(esc)} escrituraciones acompa&ntilde;adas</b> &rarr; firma y t&iacute;tulos al d&iacute;a</td></tr>
<tr style="background:#f0e9d2"><td><b>Compromiso</b></td>
<td style="text-align:right"><b>Apoyo total, en evaluaci&oacute;n y en escrituraci&oacute;n</b> &mdash; solo gesti&oacute;n propia, sin sumar De Manet</td></tr>
</table>
"""

# ═══ CUERPO DEL CORREO (formal, rapidez y valor total primero) ═══
CUERPO = f"""
<p>Estimadas,</p>
<p>Junto con saludarlas cordialmente, comparto en una sola mirada lo que esta alianza ha construido:</p>
{RESUMEN_TABLA}
<p>Me permito, adem&aacute;s, desarrollar brevemente estos resultados, con una convicci&oacute;n que los antecedentes respaldan
plenamente: <b>esta es una alianza exitosa, y los n&uacute;meros hablan por s&iacute; solos.</b></p>
<p><b>Somos r&aacute;pidos, porque sabemos que cada hora cuenta.</b> Hoy respondemos las evaluaciones de sus ejecutivas con una
<b>mediana de 11,3 horas</b> &mdash;la mitad en menos de 12 horas y un tercio en menos de una hora&mdash;, con una tasa de
respuesta que alcanza el <b>75% y contin&uacute;a mejorando mes a mes</b>. En un mercado donde cada reserva se defiende con
velocidad, una evaluaci&oacute;n oportuna es una venta que no se cae: esa es nuestra promesa comercial hacia Ecomac.</p>
<p><b>El valor de lo construido juntos es concreto:</b> la escrituraci&oacute;n acompa&ntilde;ada durante estos dos a&ntilde;os
representa una cartera de cr&eacute;ditos superior a <b>UF 180.000, del orden de $7.500 millones de pesos</b> en operaciones
del canal Ecomac &mdash;considerando &uacute;nicamente la gesti&oacute;n de esta oficina, sin sumar la gesti&oacute;n de De Manet.</p>
<p><b>Apostamos por su venta en verde.</b> En el &uacute;ltimo trimestre evaluamos {len(m3)} clientes derivados por sus
ejecutivas; nuestra evaluaci&oacute;n temprana blinda cada reserva hoy para que escriture ma&ntilde;ana, cuando los proyectos se
entreguen. Y cuando llega el per&iacute;odo de escrituraci&oacute;n, ah&iacute; estamos: hemos acompa&ntilde;ado
<b>{len(esc)} procesos de escrituraci&oacute;n de clientes Ecomac</b> &mdash;borradores, correcciones, firmas y t&iacute;tulos&mdash;
gestionando notar&iacute;a, banco alzante y abogados hasta el final. <b>Cuando escrituramos, escrituramos bien.</b></p>
<p><b>Una relaci&oacute;n que trasciende los n&uacute;meros.</b> El apoyo de Ecomac ha sido relevante en m&uacute;ltiples hitos
de nuestro crecimiento: reuniones de coordinaci&oacute;n permanentes, ferias inmobiliarias compartidas y una comunicaci&oacute;n
diaria que funciona con la naturalidad de dos equipos que se conocen y se respetan. Ese compromiso ha sido constante en ambas
direcciones, y tambi&eacute;n lo perciben los clientes: adjunto encontrar&aacute;n un documento con <b>felicitaciones reales de
compradores Ecomac</b> &mdash;incluso de quienes no concretaron su compra&mdash; que reflejan el cuidado con que se atiende su
marca en cada contacto.</p>
<p>Como en toda relaci&oacute;n comercial de alto volumen pueden existir divergencias puntuales; es natural entre equipos
exigentes. Sin embargo, los antecedentes son elocuentes: <b>la colaboraci&oacute;n ha sido efectiva, creciente y rentable para
ambas partes.</b></p>
<p>Se adjuntan dos documentos de respaldo:</p>
<ol>
<li><b>Felicitaciones_Clientes_Ecomac.pdf</b> &mdash; testimonios y conversaciones reales de clientes.</li>
<li><b>Clientes_Enviados_Ecomac.pdf</b> &mdash; registro completo, cliente por cliente, de los {len(casos)} clientes que
ustedes nos han confiado desde septiembre de 2024, con fecha, ejecutiva, tiempo de primera respuesta y estado.</li>
</ol>
<p>Quedo a su entera disposici&oacute;n para revisar estos antecedentes en la instancia que estimen conveniente.
<b>Mantengamos esta alianza que funciona.</b></p>
<p>Atentamente,<br/><br/>
<b>Gerardo Barraza</b><br/>
Central Mutuos Ltda.<br/>
Av. La Dehesa 1822, Of. 511, Torre Sur &middot; Lo Barnechea<br/>
www.centralmutuos.cl</p>
"""

import email_service as es
from pymongo import MongoClient
import os
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
db.correos_preview.update_many({"subject": {"$regex": "Alianza"}, "estado": "esperando_confirmacion"},
                               {"$set": {"estado": "descartado", "motivo": "reemplazado por correo formal con 2 PDFs"}})
r = es.send_mail("gerardo.ext@centralmutuos.cl",
                 "Central Mutuos – Ecomac: resultados de una alianza que funciona",
                 CUERPO,
                 attachments=[
                     {"filename": "Felicitaciones_Clientes_Ecomac.pdf", "content_b64": base64.b64encode(pdf_fel).decode()},
                     {"filename": "Clientes_Enviados_Ecomac.pdf", "content_b64": base64.b64encode(pdf_cli).decode()},
                 ])
print("ENCOLADO:", r)
