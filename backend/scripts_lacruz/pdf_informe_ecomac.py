"""PDF Informe Histórico Ecomac completo (casilla gerardo.ext) + envío a preview."""
# ruff: noqa: F821, F403, F405
import io, json, re, base64
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
import sys
sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app/backend/scripts_lacruz")
from xhtml2pdf import pisa
from collections import Counter

from analisis_ecomac import *  # noqa: F403

MESES_ES = {"01": "Ene", "02": "Feb", "03": "Mar", "04": "Abr", "05": "May", "06": "Jun",
            "07": "Jul", "08": "Ago", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dic"}


def mes_es(m):
    return f"{MESES_ES[m[5:]]} {m[:4]}"


resp_mes, tot_mes = Counter(), Counter()
for tk, t in threads.items():
    tot_mes[t["first"]["mes"]] += 1
    if any(s["dt"] >= t["first"]["dt"] for s in sent_by_tk.get(tk, [])):
        resp_mes[t["first"]["mes"]] += 1

esc_borr_mes, esc_firma_mes = Counter(), Counter()
for c, e in esc.items():
    dt = e["etapas"].get(1) or e["etapas"].get(2)
    if dt:
        esc_borr_mes[dt.strftime("%Y-%m")] += 1
    top = max(e["etapas"])
    if top >= 3:
        esc_firma_mes[e["etapas"][top].strftime("%Y-%m")] += 1

aprob_mes = Counter()
vistos = set()
for r in sent:
    if KW_APROB.search(r["subject"]) and r["tk"] not in vistos:
        vistos.add(r["tk"])
        aprob_mes[r["mes"]] += 1


def name_tokens(subj):
    s = norm(subj)
    s = re.sub(r"\d[\d.\-k]*", " ", s)
    return {w for w in re.findall(r"[a-z\u00f1]+", s) if len(w) > 2 and w not in
            {"evaluacion", "hipotecaria", "hipotecario", "documentos", "documentacion", "para", "gestion",
             "bancaria", "credito", "solicitud", "antecedentes", "rut", "con", "complemento", "los", "las",
             "del", "condominio", "proyecto", "pre", "aprobacion", "cliente", "nombre", "datos", "simulacion"}}


esc_names = {c: set(c.split()) for c in esc if not c.startswith("rut:")}
esc_ruts = {c[4:] for c in esc if c.startswith("rut:")}


def match_esc(t):
    if t["ruts"] & esc_ruts:
        return "rut:" + next(iter(t["ruts"] & esc_ruts))
    toks = name_tokens(t["first"]["subject"])
    for c, ct in esc_names.items():
        if len(ct & toks) >= 2:
            return c
    return None


cruce = {}
for mail, nombre in EJEC.items():
    ths = [t for t in threads.values() if t["first"]["sender"] == mail]
    e_n = f_n = 0
    for t in ths:
        h = match_esc(t)
        if h:
            e_n += 1
            if max(esc[h]["etapas"]) >= 3:
                f_n += 1
    correos = sum(1 for r in inbox if r["sender"] == mail)
    cruce[nombre] = (correos, len(ths), e_n, f_n)

tot_match = sum(1 for t in threads.values() if match_esc(t))
tot_firm_match = sum(1 for t in threads.values() if (h := match_esc(t)) and max(esc[h]["etapas"]) >= 3)

meses_all = sorted(set(tot_mes) | set(esc_borr_mes) | set(esc_firma_mes))
pre = [m for m in meses_all if m < "2025-11"]
post = [m for m in meses_all if m >= "2025-11"]
tasa_pre = sum(resp_mes[m] for m in pre) / max(1, sum(tot_mes[m] for m in pre)) * 100
tasa_post = sum(resp_mes[m] for m in post) / max(1, sum(tot_mes[m] for m in post)) * 100
tiempos_ord = sorted(tiempos)
mediana_h = tiempos_ord[len(tiempos_ord) // 2]

filas_mes = "".join(
    f"<tr><td>{mes_es(m)}</td><td class='n'>{tot_mes.get(m,0)}</td>"
    f"<td class='n'>{resp_mes.get(m,0)}</td>"
    f"<td class='n'>{(resp_mes.get(m,0)/tot_mes[m]*100):.0f}%</td>"
    f"<td class='n'>{aprob_mes.get(m,'')}</td>"
    f"<td class='n'>{esc_borr_mes.get(m,'')}</td>"
    f"<td class='n'>{esc_firma_mes.get(m,'')}</td></tr>"
    for m in meses_all if m in tot_mes or m in esc_borr_mes)

m3 = [m for m in meses_all if m >= "2026-06"]
filas_3m = "".join(
    f"<tr><td>{mes_es(m)}</td><td class='n'>{tot_mes.get(m,0)}</td>"
    f"<td class='n'>{esc_borr_mes.get(m,0)}</td><td class='n'>{esc_firma_mes.get(m,0)}</td></tr>" for m in m3)

filas_ejec = "".join(
    f"<tr><td>{n}</td><td class='n'>{c}</td><td class='n'>{s}</td><td class='n'>{e}</td><td class='n'>{f}</td>"
    f"<td class='n'>{(e/s*100 if s else 0):.0f}%</td></tr>"
    for n, (c, s, e, f) in cruce.items())

CSS = """@page { size: letter; margin: 1.8cm 2cm; }
body { font-family: Helvetica; font-size: 9pt; color: #1a1a1a; line-height: 1.45; }
h1 { font-size: 15pt; color: #14213d; text-align: center; margin: 0 0 2px; }
.sub { text-align:center; font-size: 8.5pt; color: #555; margin: 0 0 14px; }
h2 { font-size: 10.5pt; color: #14213d; border-bottom: 1.3pt solid #c9a227; padding-bottom: 2px; margin: 14px 0 6px; }
table { width: 100%; border-collapse: collapse; margin: 4px 0 8px; }
td, th { border: 0.5pt solid #b9c0cc; padding: 3px 6px; font-size: 8pt; }
th { background-color: #14213d; color: #fff; text-align: left; }
.n { text-align: right; }
.kpi td { background-color: #f0e9d2; font-weight: bold; font-size: 9pt; text-align:center; }
.nota { font-size: 7.6pt; color: #555; margin-top: 10px; }
.alerta { background-color: #eef5ee; border: 0.8pt solid #2e7d32; padding: 6px 10px; font-size: 8.5pt; margin: 6px 0; }"""

HTML = f"""
<h1>INFORME HIST&Oacute;RICO ECOMAC &mdash; EVALUACIONES vs ESCRITURACIONES</h1>
<p class="sub">Casilla gerardo.ext@centralmutuos.cl &middot; 11.031 correos analizados &middot; Sep 2024 &rarr; Ago 2026 &middot; Regla: Ecomac = vivienda futura (Pe&ntilde;uelas II incluido)</p>

<h2>I. RESUMEN EJECUTIVO</h2>
<table class="kpi"><tr>
<td>1.109<br/>solicitudes de evaluaci&oacute;n</td>
<td>676<br/>RUTs &uacute;nicos</td>
<td>121<br/>clientes en escrituraci&oacute;n</td>
<td>{sum(esc_firma_mes.values())}<br/>llegaron a firma/t&iacute;tulos</td>
<td>{mediana_h:.1f} h<br/>mediana de respuesta</td>
</tr></table>
<p>Del total de solicitudes hist&oacute;ricas, <b>{tot_match} hilos ({tot_match/len(threads)*100:.0f}%)</b> registran actividad
posterior de escrituraci&oacute;n identificable y <b>{tot_firm_match}</b> alcanzaron firma o t&iacute;tulos aprobados.
La brecha evaluaci&oacute;n &rarr; escrituraci&oacute;n sigue siendo el punto cr&iacute;tico del canal.</p>

<h2>II. MES POR MES DESDE EL INICIO REAL (SEP 2024)</h2>
<table>
<tr><th>Mes</th><th>Solicitudes evaluaci&oacute;n</th><th>Respondidas</th><th>% resp.</th><th>Se&ntilde;al aprobaci&oacute;n (asunto)</th><th>Escrituras iniciadas</th><th>Firma / t&iacute;tulos</th></tr>
{filas_mes}
</table>

<h2>III. CUADRO 3 MESES &mdash; FUTURA vs ESCRITURADAS</h2>
<table>
<tr><th>Mes</th><th>Solicitudes FUTURA (Ecomac)</th><th>Escrituras iniciadas</th><th>Firmadas / t&iacute;tulos</th></tr>
{filas_3m}
</table>

<h2>IV. TIEMPOS DE RESPUESTA SOLICITUD &rarr; EJECUTIVO</h2>
<table>
<tr><th>Indicador</th><th>Valor</th></tr>
<tr><td>Mediana primera respuesta</td><td class="n">{mediana_h:.1f} horas</td></tr>
<tr><td>Promedio primera respuesta</td><td class="n">{sum(tiempos)/len(tiempos):.1f} horas</td></tr>
<tr><td>Tasa de respuesta ANTES de Nov 2025</td><td class="n">{tasa_pre:.0f}%</td></tr>
<tr><td>Tasa de respuesta DESDE Nov 2025 (sistema Central Mutuos)</td><td class="n">{tasa_post:.0f}%</td></tr>
</table>
<div class="alerta"><b>Mejora estructural:</b> desde noviembre 2025 la tasa de respuesta a las ejecutivas Ecomac
subi&oacute; de {tasa_pre:.0f}% a {tasa_post:.0f}%, con mediana de primera respuesta de {mediana_h:.1f} horas.</div>

<h2>V. EJECUTIVAS ECOMAC &mdash; SOLICITUDES / ESCRITURACI&Oacute;N</h2>
<table>
<tr><th>Ejecutiva</th><th>Correos totales</th><th>Solicitudes iniciadas</th><th>En escrituraci&oacute;n</th><th>Firmadas</th><th>Conversi&oacute;n</th></tr>
{filas_ejec}
</table>

<p class="nota"><b>Metodolog&iacute;a:</b> an&aacute;lisis de los 11.031 encabezados hist&oacute;ricos de la casilla gerardo.ext
(bandeja Ecomac 2.711, enviados 3.597, borradores 1.463, escrituras 1.361, firmas 115, t&iacute;tulos 59).
Solicitud = hilo &uacute;nico iniciado por @ecomac.cl con se&ntilde;al de evaluaci&oacute;n/documentaci&oacute;n. Escrituraci&oacute;n = cliente
detectado por RUT o nombre en los hilos de borrador/escritura/firma/t&iacute;tulos. La columna &laquo;se&ntilde;al aprobaci&oacute;n&raquo;
solo cuenta aprobaciones expl&iacute;citas en el asunto: las aprobaciones comunicadas en el cuerpo del correo se
incorporar&aacute;n en cuanto Google libere la descarga de cuerpos (miner&iacute;a autom&aacute;tica ya activa).
Documento de uso interno &mdash; Central Mutuos.</p>
"""

buf = io.BytesIO()
pisa.CreatePDF(f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{HTML}</body></html>",
               dest=buf, encoding="utf-8")
pdf = buf.getvalue()
open("/app/backend/scripts_lacruz/Informe_Historico_Ecomac.pdf", "wb").write(pdf)
print("PDF OK", len(pdf))

import email_service as es
cuerpo = f"""<p>Estimado Gerardo,</p>
<p>Adjunto el <b>Informe Hist&oacute;rico Ecomac completo</b> generado desde la casilla gerardo.ext reci&eacute;n liberada
(11.031 correos, septiembre 2024 &rarr; agosto 2026):</p>
<ul>
<li><b>1.109 solicitudes de evaluaci&oacute;n</b> (676 RUTs &uacute;nicos) mes por mes desde el inicio real.</li>
<li><b>121 clientes en proceso de escrituraci&oacute;n</b>; {sum(esc_firma_mes.values())} llegaron a firma/t&iacute;tulos.</li>
<li>Cuadro 3 meses FUTURA vs escrituradas (regla: Ecomac = vivienda futura, Pe&ntilde;uelas II incluido).</li>
<li>Tiempos de respuesta: mediana {mediana_h:.1f} h; la tasa de respuesta subi&oacute; de {tasa_pre:.0f}% a {tasa_post:.0f}% desde Nov 2025.</li>
<li>Detalle por ejecutiva: Yerko, Amalia, Gabriela, Scarlett y Rita.</li>
</ul>
<p>Saludos,<br/>DashAI &mdash; Central Mutuos</p>"""
r = es.send_mail("gerardo.ext@centralmutuos.cl",
                 "Informe Histórico Ecomac — Evaluaciones vs Escrituraciones (Sep 2024 → Ago 2026)",
                 cuerpo,
                 attachments=[{"filename": "Informe_Historico_Ecomac.pdf",
                               "content_b64": base64.b64encode(pdf).decode()}])
print("ENCOLADO:", r)
