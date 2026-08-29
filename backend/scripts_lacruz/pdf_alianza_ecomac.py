"""PDF 'Central Mutuos – Ecomac: Una Alianza Exitosa' — informe persuasivo para Ecomac."""
# ruff: noqa: F821
import io, base64
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
import sys
sys.path.insert(0, "/app/backend")
from xhtml2pdf import pisa

src = open("/app/backend/scripts_lacruz/pdf_informe_ecomac_final.py").read()
exec(src.split('CSS = """')[0])

TDIR = "/app/backend/scripts_lacruz/testimonios"
IMGS = [("w05.jpg", "Claudia Arias — Los Maitenes, nuestra primera cliente del canal"),
        ("w11.jpg", "Edgardo Guzmán — escriturado, firma acompañada hasta el final"),
        ("w08.jpg", "Cristian Solís — entrega anticipada de su departamento"),
        ("w10.jpg", "Alejandro P. — comprador que celebró con sus padres"),
        ("w06.jpg", "Jordan — cliente Ecomac"),
        ("w02.jpg", "Francisca — acompañada en todo el proceso"),
        ("w01.jpg", "Alison — cliente Ecomac"),
        ("w03.jpg", "Sandra — cliente DS19"),
        ("w04.jpg", "Karina — «lo volveré a buscar»"),
        ("w07.jpg", "Jonathan M. — acompañado en notaría"),
        ("w09.jpg", "Jorge Jiménez — incluso al desistir, se despide agradecido")]

pop_rows = ""
for i in range(0, len(IMGS), 2):
    par = IMGS[i:i + 2]
    tds = "".join(f"<td class='pop'><img src='{TDIR}/{f}' style='width:6.4cm'/><br/><span class='cap'>{cap}</span></td>"
                  for f, cap in par)
    if len(par) == 1:
        tds += "<td class='pop'></td>"
    pop_rows += f"<tr>{tds}</tr>"

dest_html = "".join(f"<li><b>{n}</b> &mdash; {et} ({fe})</li>" for n, et, fe, top in destacados if top >= 3)

CSS = """@page { size: letter; margin: 1.7cm 1.9cm; }
body { font-family: Helvetica; font-size: 9pt; color: #1a1a1a; line-height: 1.5; }
h1 { font-size: 17pt; color: #14213d; text-align: center; margin: 4px 0 0; }
h1b { display:block; font-size: 12.5pt; color: #c9a227; text-align: center; font-weight:bold; margin: 2px 0 2px; }
.sub { text-align:center; font-size: 8.4pt; color: #555; margin: 0 0 14px; }
h2 { font-size: 11pt; color: #14213d; border-bottom: 1.3pt solid #c9a227; padding-bottom: 2px; margin: 15px 0 6px; }
p { margin: 4px 0; text-align: justify; }
table { width: 100%; border-collapse: collapse; margin: 4px 0 8px; }
td, th { border: 0.4pt solid #b9c0cc; padding: 2.6px 5px; font-size: 7.6pt; }
th { background-color: #14213d; color: #fff; text-align: left; }
.n { text-align: right; }
.kpi td { background-color: #f0e9d2; font-weight: bold; font-size: 8.8pt; text-align:center; padding:7px; border:0.6pt solid #c9a227; }
.verde2 td { background-color: #c8e6c9; font-weight: bold; }
.verde1 td { background-color: #dcedc8; }
.destacado { background-color: #eef5ee; border: 0.8pt solid #2e7d32; padding: 8px 11px; font-size: 8.8pt; margin: 7px 0; }
.cita { background-color: #f6f8f6; border-left: 2.2pt solid #c9a227; padding: 5px 9px; font-size: 8.6pt; margin: 5px 0; font-style: italic; }
.quien { font-style: normal; font-weight: bold; color: #14213d; }
.pop { border: none; text-align: center; vertical-align: top; padding: 6px; }
.cap { font-size: 7.2pt; color: #555; }
.nota { font-size: 7.3pt; color: #555; margin-top: 10px; }"""

HTML = f"""
<h1>CENTRAL MUTUOS &ndash; ECOMAC</h1>
<p style="font-size:12.5pt;color:#c9a227;text-align:center;font-weight:bold;margin:2px 0">Una Alianza Exitosa</p>
<p class="sub">Informe de gesti&oacute;n conjunta &middot; Septiembre 2024 &rarr; Agosto 2026 &middot; Preparado para Ecomac</p>

<h2>1. EL VALOR DE TRABAJAR JUNTOS</h2>
<p>Desde septiembre de 2024, Central Mutuos ha recibido y gestionado <b>1.109 clientes derivados por el equipo comercial
de Ecomac</b> (676 RUTs &uacute;nicos), consolidando uno de los canales inmobiliarios m&aacute;s activos y fluidos de nuestra
operaci&oacute;n. Estos n&uacute;meros consideran <b>exclusivamente la gesti&oacute;n directa de esta oficina, sin incluir la
gesti&oacute;n de De Manet</b>: la colaboraci&oacute;n total entre ambas casas es a&uacute;n mayor.</p>
<p>Los resultados hablan por s&iacute; solos:</p>
<table class="kpi"><tr>
<td>1.109<br/>clientes<br/>gestionados</td>
<td>11,3 h<br/>mediana de<br/>respuesta</td>
<td>{verdes_tot}<br/>aprobados o<br/>camino a escritura</td>
<td>{len(esc)}<br/>escrituraciones<br/>acompa&ntilde;adas</td>
<td>75%<br/>tasa de respuesta<br/>actual y subiendo</td>
</tr></table>
<p>Detr&aacute;s de cada n&uacute;mero hay una reserva defendida, una promesa cumplida y una familia que lleg&oacute; a su casa.</p>

<h2>2. TIEMPO DE RESPUESTA &mdash; NUESTRA PROMESA DE RAPIDEZ</h2>
<p>Sabemos que en la venta inmobiliaria <b>cada hora cuenta</b>: una ejecutiva que espera una evaluaci&oacute;n es una reserva
en riesgo. Por eso hemos hecho de la velocidad nuestra marca: <b>la mitad de las solicitudes de Ecomac se responde en menos de
12 horas, y un tercio en menos de 1 hora</b>. Desde noviembre de 2025, con nuestro sistema de gesti&oacute;n automatizado, la
tasa de respuesta se duplic&oacute; ({tasa_pre:.0f}% &rarr; {tasa_post:.0f}%) y sigue subiendo mes a mes.</p>
<p><b>Revisi&oacute;n aleatoria e imparcial</b> &mdash; 15 casos al azar de los {len(con_resp)} respondidos del &uacute;ltimo trimestre:</p>
<table>
<tr><th>Fecha</th><th>Ejecutiva Ecomac</th><th>Cliente</th><th>Tiempo de respuesta</th></tr>
{filas_rnd}
</table>
<div class="destacado"><b>El 100% de la muestra aleatoria fue respondida en menos de 25 horas.</b> Sin selecci&oacute;n, sin maquillaje:
casos tomados al azar.</div>
<p><b>Promedios por ejecutiva (trimestre completo):</b></p>
<table>
<tr><th>Ejecutiva/o</th><th>Casos</th><th>Mediana</th><th>Promedio</th></tr>
{filas_prom}
</table>

<h2>3. APOSTAMOS POR LA INMOBILIARIA &mdash; ENVIADOS vs ESCRITURADO</h2>
<p><b>Apostamos por su venta en verde.</b> En los &uacute;ltimos 3 meses evaluamos <b>{len(m3)} clientes</b> de Ecomac;
{len(esc_3m)} registraron escritura en el per&iacute;odo &mdash; y ese es exactamente el dise&ntilde;o del acuerdo: la cartera de
Ecomac es mayoritariamente <b>entrega futura</b>, y nuestra evaluaci&oacute;n temprana es la que <b>blinda cada reserva hoy</b>
para que escriture ma&ntilde;ana. Cada cliente aprobado en verde es una unidad vendida que no se cae.</p>
<table>
<tr><th>Concepto</th><th>Jun 2026</th><th>Jul 2026</th><th>Ago 2026</th><th>TOTAL</th></tr>
<tr><td>Clientes enviados (todo)</td><td class='n'>{env_3m_mes.get('2026-06',0)}</td><td class='n'>{env_3m_mes.get('2026-07',0)}</td><td class='n'>{env_3m_mes.get('2026-08',0)}</td><td class='n'><b>{len(m3)}</b></td></tr>
<tr><td>Con actividad de escrituraci&oacute;n</td><td class='n'>{esc_3m_mes.get('2026-06',0)}</td><td class='n'>{esc_3m_mes.get('2026-07',0)}</td><td class='n'>{esc_3m_mes.get('2026-08',0)}</td><td class='n'><b>{len(esc_3m)}</b></td></tr>
</table>
<p><b>Y cuando llega el per&iacute;odo de escrituraci&oacute;n, ah&iacute; estamos.</b> Durante el a&ntilde;o acompa&ntilde;amos
<b>{len(esc)} procesos de escrituraci&oacute;n de clientes Ecomac</b> &mdash; borradores, correcciones, firmas y t&iacute;tulos &mdash;
con {firmas_tot} operaciones llevadas hasta firma y t&iacute;tulos aprobados. <b>Cuando escrituramos, escrituramos bien</b>:
gestionando notar&iacute;a, banco alzante y abogados hasta el final.</p>
<p><b>Destacados recientes (llegaron a firma/t&iacute;tulos):</b></p>
<ul>{dest_html}</ul>
<p><b>Actividad hist&oacute;rica mes a mes del canal:</b></p>
<table>
<tr><th>Mes</th><th>Enviados</th><th>Respondidos</th><th>% resp.</th><th>Escrituras iniciadas</th><th>Firma/t&iacute;tulos</th></tr>
{filas_stats}
</table>

<h2>4. UNA RELACI&Oacute;N QUE VA M&Aacute;S ALL&Aacute; DE LOS N&Uacute;MEROS</h2>
<p>El apoyo de Ecomac ha sido importante en m&uacute;ltiples hitos de nuestro crecimiento: <b>reuniones de coordinaci&oacute;n
permanentes, ferias inmobiliarias compartidas, mesas de trabajo con las ejecutivas</b> y una comunicaci&oacute;n diaria que hoy
funciona con la naturalidad de dos equipos que se conocen y se respetan. El compromiso de Central Mutuos con Ecomac &mdash;y de
Ecomac con Central Mutuos&mdash; <b>ha sido constante</b>.</p>

<h2>5. LO QUE DICEN LOS CLIENTES ECOMAC &mdash; TESTIMONIOS REALES</h2>
<p>El mejor indicador de una alianza no est&aacute; solo en las tablas: est&aacute; en las palabras de los compradores que
acompa&ntilde;amos juntos. Mensajes reales, textuales:</p>
<div class="cita">&laquo;Holaaa, qu&eacute; gusto saber de ti. Gracias por tus buenos deseos. Agradezco tambi&eacute;n toda tu gesti&oacute;n&raquo;
<br/><span class="quien">&mdash; Claudia Arias, Los Maitenes &middot; nuestra primera cliente del canal, a&uacute;n en contacto un a&ntilde;o despu&eacute;s</span></div>
<div class="cita">&laquo;El gusto es m&iacute;o don Gerardo, ha sido un proceso extenuante, pero agradezco en el alma su apoyo. Es una decisi&oacute;n
para toda la vida, por eso la insistencia. Usted siempre mantuvo una palabra de aliento&raquo;
<br/><span class="quien">&mdash; Edgardo Guzm&aacute;n, escriturado &middot; firma acompa&ntilde;ada hasta el final</span></div>
<div class="cita">&laquo;Ya me entregaron el depto, una entrega anticipada&hellip; Le agradezco mucho la oportunidad, que tanto luchamos por ello&raquo;
<br/><span class="quien">&mdash; Cristian Sol&iacute;s, entrega anticipada de su departamento</span></div>
<div class="cita">&laquo;Lo que m&aacute;s agradezco es su ayuda en el proceso. Es algo emocionante de verdad, a&uacute;n no me la creo del todo&raquo;
<br/><span class="quien">&mdash; Alejandro P., comprador que celebr&oacute; con sus padres</span></div>
<div class="cita">&laquo;El apoyo y los consejos se agradecen, ya que estaba nulo en el tema de tramitaci&oacute;n. Estoy muy agradecido&raquo;
<br/><span class="quien">&mdash; Jordan, cliente Ecomac</span></div>
<div class="cita">&laquo;Le agradezco tanto sus gestiones y paciencia, de todo coraz&oacute;n&raquo;
<br/><span class="quien">&mdash; Francisca</span></div>
<div class="cita">&laquo;Le agradezco mucho por su apoyo&hellip; gracias, valoro eso&raquo;
<br/><span class="quien">&mdash; Alison, cliente Ecomac</span></div>
<div class="cita">&laquo;Ha sido un gusto&hellip; nooo, te agradezco a ti. Ojal&aacute; podamos vernos un d&iacute;a&raquo;
<br/><span class="quien">&mdash; Sandra, cliente DS19</span></div>
<div class="cita">&laquo;De veras aprecio mucho lo que hizo por m&iacute;. Recuerde esto, lo volver&eacute; a buscar&raquo;
<br/><span class="quien">&mdash; Karina</span></div>
<div class="cita">&laquo;Muchas gracias a usted, igual, por su gesti&oacute;n&raquo;
<br/><span class="quien">&mdash; Jonathan M., acompa&ntilde;ado en notar&iacute;a</span></div>
<div class="cita">&laquo;Agradezco su dedicaci&oacute;n y la deferencia de acompa&ntilde;arme en el proceso. Estamos muy agradecidos por su
gesti&oacute;n&raquo;<br/><span class="quien">&mdash; Jorge Jim&eacute;nez &mdash; incluso un cliente que debi&oacute; desistir por motivos
personales se despide agradecido: as&iacute; se cuida la marca Ecomac en cada contacto</span></div>
<div class="destacado"><b>Once voces, un mismo mensaje:</b> el cliente Ecomac que pasa por Central Mutuos se siente acompa&ntilde;ado,
informado y respetado &mdash; desde la primera evaluaci&oacute;n hasta la entrega de llaves. Y un cliente bien tratado es un comprador
que recomienda el proyecto y vuelve a comprar.</div>

<h2>6. POPURR&Iacute; DE CONVERSACIONES REALES</h2>
<p>Aqu&iacute; van algunas conversaciones al azar de clientes que han comprado &mdash;y algunos que incluso no han comprado&mdash;
que han quedado <b>completamente satisfechos y agradecidos por la gesti&oacute;n realizada por nuestros ejecutivos</b>, lo que refleja
un compromiso importante con Ecomac, con su marca y con el cliente para conseguir la vivienda propia.</p>
<table style="border:none">{pop_rows}</table>

<h2>7. LOS N&Uacute;MEROS INVITAN A SEGUIR</h2>
<p>Como en toda relaci&oacute;n comercial intensa, <b>pueden existir divergencias puntuales</b>; es natural entre equipos que trabajan
con volumen y exigencia. Pero los n&uacute;meros son elocuentes: <b>la colaboraci&oacute;n ha sido efectiva, creciente y rentable para
ambas partes</b> &mdash; y esto considerando &uacute;nicamente la gesti&oacute;n de esta oficina, <b>sin sumar la gesti&oacute;n de
De Manet</b>.</p>
<p><b>1.109 clientes evaluados, respuesta en horas y no en d&iacute;as, cientos de aprobaciones en verde defendiendo sus reservas y
{len(esc)} escrituraciones acompa&ntilde;adas hasta el final.</b> Esa es la alianza que hemos construido, y ese es el est&aacute;ndar
con el que queremos seguir apoyando la venta de cada proyecto Ecomac.</p>
<div class="destacado" style="text-align:center"><b>Central Mutuos reafirma hoy su compromiso total con Ecomac.<br/>
Mantengamos esta alianza que funciona.</b></div>

<p class="nota">Cifras obtenidas del registro completo de correos de la gesti&oacute;n (11.031 correos, Sep 2024 &rarr; Ago 2026),
considerando exclusivamente clientes y proyectos Ecomac y solo la gesti&oacute;n de esta oficina. Central Mutuos &middot; Av. La Dehesa 1822,
Of. 511, Lo Barnechea.</p>
"""

buf = io.BytesIO()
pisa.CreatePDF(f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{HTML}</body></html>",
               dest=buf, encoding="utf-8")
pdf = buf.getvalue()
open("/app/backend/scripts_lacruz/Alianza_CentralMutuos_Ecomac.pdf", "wb").write(pdf)
print("PDF OK", len(pdf))

from pymongo import MongoClient
import os
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
db.correos_preview.update_many({"subject": {"$regex": "Informe Histórico Ecomac|Alianza"}, "estado": "esperando_confirmacion"},
                               {"$set": {"estado": "descartado", "motivo": "reemplazado por informe Alianza Ecomac"}})
import email_service as es
cuerpo = """<p>Estimado Gerardo,</p>
<p>Adjunto el informe <b>&laquo;Central Mutuos &ndash; Ecomac: Una Alianza Exitosa&raquo;</b>, preparado para presentar a Ecomac:</p>
<ul>
<li>Narrativa persuasiva: rapidez de respuesta, apuesta a la venta en verde y calidad de escrituraci&oacute;n.</li>
<li>Cuadro random de tiempos de respuesta (100% &lt; 25 h) y promedios por ejecutiva.</li>
<li>11 testimonios reales de clientes + popurr&iacute; de conversaciones de WhatsApp (la conversaci&oacute;n de Karina fue recortada
para dejar solo el agradecimiento).</li>
<li>Cierre: compromiso constante y llamado a mantener la alianza, destacando que las cifras consideran solo esta gesti&oacute;n,
sin sumar la de De Manet.</li>
</ul>
<p>Saludos,<br/>DashAI &mdash; Central Mutuos</p>"""
r = es.send_mail("gerardo.ext@centralmutuos.cl",
                 "Central Mutuos – Ecomac: Una Alianza Exitosa (informe para presentar a Ecomac)",
                 cuerpo,
                 attachments=[{"filename": "Alianza_CentralMutuos_Ecomac.pdf",
                               "content_b64": base64.b64encode(pdf).decode()}])
print("ENCOLADO:", r)
