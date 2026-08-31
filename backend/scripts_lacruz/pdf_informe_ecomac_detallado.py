"""Informe Histórico Ecomac DETALLADO — cliente por cliente + envío a preview."""
# ruff: noqa: F821, F403, F405
import io, re, base64
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
import sys
sys.path.insert(0, "/app/backend")
from xhtml2pdf import pisa
from collections import Counter
from pymongo import MongoClient
import os

from analisis_ecomac import *  # noqa: F403

MESES_ES = {"01": "Ene", "02": "Feb", "03": "Mar", "04": "Abr", "05": "May", "06": "Jun",
            "07": "Jul", "08": "Ago", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dic"}
mes_es = lambda m: f"{MESES_ES[m[5:]]} {m[:4]}"

KW_LIMPIA = re.compile(
    r"\b(rv|re|fwd?|evaluaci[oó]n|hipotecari[oa]s?|documentos?|documentaci[oó]n|para|gesti[oó]n|bancaria|"
    r"cr[eé]dito|solicitud|antecedentes|rut|con|complemento|codeudora?|a nombre de|cliente|sra?|don|do[ñn]a|"
    r"ds-?\d*|subsidio|pre-?aprobaci[oó]n|aprobaci[oó]n|simulaci[oó]n|renta|liquidaciones?|cotizaci[oó]n|"
    r"condominio|proyecto|entrega|inmediata|futura|urgente|adjunto|nueva?|caso|operaci[oó]n|op)\b", re.I)


def nombre_cliente(subj):
    s = re.sub(r"[\r\n]+", " ", subj or "")
    m = RX_RUT.search(s)
    if m:
        tras = s[m.end():]
        tras = re.split(r"[-–/(]|,|\bRUT\b", tras)[0]
        toks = [w for w in re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{3,}", KW_LIMPIA.sub(" ", tras))]
        if len(toks) >= 2:
            return " ".join(toks[:5]).title()
        antes = s[:m.start()]
        toks = [w for w in re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{3,}", KW_LIMPIA.sub(" ", antes))]
        if len(toks) >= 2:
            return " ".join(toks[-5:]).title()
    limpio = KW_LIMPIA.sub(" ", re.sub(r"\d[\d.\-kK]*", " ", s))
    toks = re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{3,}", limpio)
    return " ".join(toks[:5]).title() if len(toks) >= 2 else (subj or "")[:35]


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


# veredictos de Mesa registrados en el sistema
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
verdes_db, rojos_db = [], []
for d in db.mesa_verdad_log.find({}, {"tipo": 1, "subject": 1}):
    toks = name_tokens(d.get("subject", ""))
    if len(toks) >= 2:
        (verdes_db if d.get("tipo") == "aprobacion" else rojos_db if d.get("tipo") == "rechazo" else []).append(toks)
for d in db.aprobacion_log.find({}, {"nombre": 1}):
    toks = {w.lower() for w in re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{3,}", d.get("nombre", ""))}
    if len(toks) >= 2:
        verdes_db.append(toks)


def veredicto_db(toks):
    for v in verdes_db:
        if len(v & toks) >= 2:
            return "APROBADO"
    for r in rojos_db:
        if len(r & toks) >= 2:
            return "RECHAZADO"
    return None


ETIQ = {4: "FIRMADA", 3: "FIRMA/TÍTULOS", 2: "EN ESCRITURA", 1: "BORRADOR"}
casos = []
for tk, t in sorted(threads.items(), key=lambda kv: kv[1]["first"]["dt"]):
    f = t["first"]
    reps = [s for s in sent_by_tk.get(tk, []) if s["dt"] >= f["dt"]]
    horas = min((s["dt"] - f["dt"]).total_seconds() / 3600 for s in reps) if reps else None
    aprob_asunto = any(KW_APROB.search(s["subject"]) for s in reps)
    h = match_esc(t)
    etapa = max(esc[h]["etapas"]) if h else 0
    fecha_esc = esc[h]["etapas"][etapa].strftime("%d/%m/%y") if h else ""
    toks = name_tokens(f["subject"])
    vdb = veredicto_db(toks) if toks else None
    if etapa >= 3:
        estado, css = ETIQ[etapa], "verde2"
    elif etapa >= 1:
        estado, css = ETIQ[etapa], "verde1"
    elif aprob_asunto or vdb == "APROBADO":
        estado, css = "APROBADO ✓", "verde0"
    elif vdb == "RECHAZADO":
        estado, css = "RECHAZADO", "rojo"
    elif reps:
        estado, css = "Respondida", ""
    else:
        estado, css = "Sin respuesta", "gris"
    casos.append({
        "mes": f["mes"], "fecha": f["dt"].strftime("%d/%m/%y"),
        "nombre": nombre_cliente(f["subject"]), "rut": next(iter(t["ruts"]), ""),
        "ejec": EJEC.get(f["sender"], f["sender"].split("@")[0]),
        "horas": horas, "estado": estado, "css": css, "fecha_esc": fecha_esc,
    })

verdes_tot = sum(1 for c in casos if c["css"].startswith("verde"))
m3 = [c for c in casos if c["mes"] >= "2026-06"]
verdes_3m = [c for c in casos if c["mes"] >= "2026-06" and c["css"].startswith("verde")]
esc_3m = [c for c in m3 if c["fecha_esc"]]

hrs_fmt = lambda h: (f"{h:.0f} h" if h is not None and h < 48 else f"{h/24:.0f} d" if h is not None else "—")


def fila(c, con_mes=False):
    return (f"<tr class='{c['css']}'><td>{c['fecha']}</td><td>{c['nombre'][:38]}</td><td>{c['rut']}</td>"
            f"<td>{c['ejec'][:22]}</td><td class='n'>{hrs_fmt(c['horas'])}</td>"
            f"<td>{c['estado']}</td><td>{c['fecha_esc']}</td></tr>")


TH = ("<tr><th>Fecha</th><th>Cliente</th><th>RUT</th><th>Ejecutiva/o</th>"
      "<th>1&ordf; resp.</th><th>Estado</th><th>Escritura</th></tr>")

filas_3m = "".join(fila(c) for c in m3)

# histórico completo agrupado por mes
bloques_hist = ""
for mes in sorted({c["mes"] for c in casos}):
    cs = [c for c in casos if c["mes"] == mes]
    bloques_hist += (f"<tr class='mes'><td colspan='7'>{mes_es(mes)} &mdash; {len(cs)} solicitudes &middot; "
                     f"{sum(1 for c in cs if c['css'].startswith('verde'))} en verde</td></tr>"
                     + "".join(fila(c) for c in cs))

# escriturados históricos (121)
filas_esc = ""
for cli, e in sorted(esc.items(), key=lambda kv: min(kv[1]["etapas"].values())):
    top = max(e["etapas"])
    ini = min(e["etapas"].values()).strftime("%d/%m/%y")
    fin = e["etapas"][top].strftime("%d/%m/%y")
    nom = cli[4:].upper() if cli.startswith("rut:") else cli.title()
    css = "verde2" if top >= 3 else "verde1"
    filas_esc += (f"<tr class='{css}'><td>{nom[:42]}</td><td>{ini}</td><td>{ETIQ[top]}</td><td>{fin}</td></tr>")

resp_mes, tot_mes = Counter(), Counter()
for c in casos:
    tot_mes[c["mes"]] += 1
    if c["horas"] is not None:
        resp_mes[c["mes"]] += 1
esc_ini_mes, esc_fin_mes = Counter(), Counter()
for cli, e in esc.items():
    esc_ini_mes[min(e["etapas"].values()).strftime("%Y-%m")] += 1
    if max(e["etapas"]) >= 3:
        esc_fin_mes[e["etapas"][max(e["etapas"])].strftime("%Y-%m")] += 1
verdes_mes = Counter(c["mes"] for c in casos if c["css"].startswith("verde"))
filas_stats = "".join(
    f"<tr><td>{mes_es(m)}</td><td class='n'>{tot_mes[m]}</td><td class='n'>{resp_mes[m]}</td>"
    f"<td class='n'>{resp_mes[m]/tot_mes[m]*100:.0f}%</td><td class='n'>{verdes_mes.get(m,'')}</td>"
    f"<td class='n'>{esc_ini_mes.get(m,'')}</td><td class='n'>{esc_fin_mes.get(m,'')}</td></tr>"
    for m in sorted(tot_mes))

tiempos_ord = sorted(tiempos)
mediana_h = tiempos_ord[len(tiempos_ord) // 2]
pre = [m for m in tot_mes if m < "2025-11"]
post = [m for m in tot_mes if m >= "2025-11"]
tasa_pre = sum(resp_mes[m] for m in pre) / max(1, sum(tot_mes[m] for m in pre)) * 100
tasa_post = sum(resp_mes[m] for m in post) / max(1, sum(tot_mes[m] for m in post)) * 100

cruce_rows = ""
for mail, nombre in EJEC.items():
    ths = [t for t in threads.values() if t["first"]["sender"] == mail]
    e_n = f_n = 0
    for t in ths:
        h = match_esc(t)
        if h:
            e_n += 1
            if max(esc[h]["etapas"]) >= 3:
                f_n += 1
    cruce_rows += (f"<tr><td>{nombre}</td><td class='n'>{sum(1 for r in inbox if r['sender']==mail)}</td>"
                   f"<td class='n'>{len(ths)}</td><td class='n'>{e_n}</td><td class='n'>{f_n}</td>"
                   f"<td class='n'>{(e_n/len(ths)*100 if ths else 0):.0f}%</td></tr>")

CSS = """@page { size: letter; margin: 1.6cm 1.8cm; }
body { font-family: Helvetica; font-size: 8.5pt; color: #1a1a1a; line-height: 1.4; }
h1 { font-size: 14pt; color: #14213d; text-align: center; margin: 0 0 2px; }
.sub { text-align:center; font-size: 8pt; color: #555; margin: 0 0 12px; }
h2 { font-size: 10pt; color: #14213d; border-bottom: 1.2pt solid #c9a227; padding-bottom: 2px; margin: 13px 0 5px; }
table { width: 100%; border-collapse: collapse; margin: 3px 0 7px; }
td, th { border: 0.4pt solid #b9c0cc; padding: 2px 4px; font-size: 7.3pt; }
th { background-color: #14213d; color: #fff; text-align: left; }
.n { text-align: right; }
.kpi td { background-color: #f0e9d2; font-weight: bold; font-size: 8.5pt; text-align:center; padding:5px; }
.verde2 td { background-color: #c8e6c9; font-weight: bold; }
.verde1 td { background-color: #dcedc8; }
.verde0 td { background-color: #f1f8e9; }
.rojo td { background-color: #fdecea; }
.gris td { color: #888; }
.mes td { background-color: #e8eaf0; font-weight: bold; font-size: 7.8pt; color:#14213d; }
.nota { font-size: 7.2pt; color: #555; margin-top: 8px; }
.leyenda { font-size: 7.4pt; margin: 2px 0 6px; }"""

LEY = ("<p class='leyenda'>Leyenda: <span style='background:#c8e6c9'>&nbsp;FIRMADA/T&Iacute;TULOS&nbsp;</span> "
       "<span style='background:#dcedc8'>&nbsp;EN ESCRITURACI&Oacute;N&nbsp;</span> "
       "<span style='background:#f1f8e9'>&nbsp;APROBADO&nbsp;</span> "
       "<span style='background:#fdecea'>&nbsp;RECHAZADO&nbsp;</span> &middot; gris = sin respuesta detectada</p>")

HTML = f"""
<h1>INFORME HIST&Oacute;RICO ECOMAC &mdash; DETALLE CLIENTE POR CLIENTE</h1>
<p class="sub">Casilla gerardo.ext@centralmutuos.cl &middot; 11.031 correos &middot; Sep 2024 &rarr; Ago 2026 &middot; Regla: Ecomac = vivienda futura (Pe&ntilde;uelas II incluido)</p>

<h2>I. RESUMEN EJECUTIVO</h2>
<table class="kpi"><tr>
<td>{len(casos)}<br/>clientes enviados<br/>(hist&oacute;rico)</td>
<td>{verdes_tot}<br/>en verde<br/>(aprob./escritura)</td>
<td>{len(esc)}<br/>en proceso de<br/>escrituraci&oacute;n</td>
<td>{sum(1 for _,e in esc.items() if max(e['etapas'])>=3)}<br/>llegaron a<br/>firma/t&iacute;tulos</td>
<td>{mediana_h:.1f} h<br/>mediana 1&ordf;<br/>respuesta</td>
</tr></table>

<h2>II. ESTAD&Iacute;STICA MES A MES DESDE EL INICIO</h2>
<table>
<tr><th>Mes</th><th>Enviados</th><th>Respondidos</th><th>% resp.</th><th>En verde</th><th>Escrituras iniciadas</th><th>Firma/t&iacute;tulos</th></tr>
{filas_stats}
</table>
<p>Tasa de respuesta: <b>{tasa_pre:.0f}%</b> antes de Nov 2025 &rarr; <b>{tasa_post:.0f}%</b> con Central Mutuos operando. Mediana 1&ordf; respuesta: <b>{mediana_h:.1f} h</b>.</p>

<h2>III. &Uacute;LTIMOS 3 MESES &mdash; TODOS LOS CLIENTES ENVIADOS ({len(m3)}) &middot; {len(verdes_3m)} en verde &middot; {len(esc_3m)} con escritura</h2>
{LEY}
<table>{TH}{filas_3m}</table>

<h2>IV. ESCRITURACIONES HIST&Oacute;RICAS &mdash; LOS {len(esc)} CLIENTES</h2>
<table><tr><th>Cliente</th><th>Inicio proceso</th><th>Etapa m&aacute;xima</th><th>Fecha etapa</th></tr>{filas_esc}</table>

<h2>V. HIST&Oacute;RICO COMPLETO &mdash; TODOS LOS CLIENTES ENVIADOS DESDE EL INICIO ({len(casos)})</h2>
{LEY}
<table>{TH}{bloques_hist}</table>

<h2>VI. EJECUTIVAS ECOMAC</h2>
<table>
<tr><th>Ejecutiva/o</th><th>Correos</th><th>Clientes enviados</th><th>En escrituraci&oacute;n</th><th>Firmadas</th><th>Conversi&oacute;n</th></tr>
{cruce_rows}
</table>

<p class="nota"><b>Metodolog&iacute;a:</b> an&aacute;lisis de 11.031 encabezados hist&oacute;ricos de gerardo.ext (Ecomac 2.711, enviados 3.597,
borradores 1.463, escrituras 1.361, firmas 115, t&iacute;tulos 59) + veredictos de Mesa registrados en el sistema (30 aprobaciones,
22 rechazos). Cliente = hilo &uacute;nico iniciado por @ecomac.cl; escrituraci&oacute;n detectada por RUT o nombre en hilos de
borrador/escritura/firma/t&iacute;tulos. Las aprobaciones antiguas comunicadas solo dentro del cuerpo del correo se incorporar&aacute;n
autom&aacute;ticamente cuando Google libere la descarga de cuerpos (miner&iacute;a activa cada 30 min). Uso interno &mdash; Central Mutuos.</p>
"""

buf = io.BytesIO()
pisa.CreatePDF(f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{HTML}</body></html>",
               dest=buf, encoding="utf-8")
pdf = buf.getvalue()
open("/app/backend/scripts_lacruz/Informe_Historico_Ecomac_Detallado.pdf", "wb").write(pdf)
print("PDF OK", len(pdf), "| casos:", len(casos), "| verdes:", verdes_tot, "| 3m:", len(m3), "| verdes 3m:", len(verdes_3m))

# descartar preview anterior (versión solo estadística) y encolar la detallada
db.correos_preview.update_one({"id": "05f69bf0-726c-4d4d-86a6-162a69009146", "estado": "esperando_confirmacion"},
                              {"$set": {"estado": "descartado", "motivo": "reemplazado por versión detallada"}})
import email_service as es
cuerpo = f"""<p>Estimado Gerardo,</p>
<p>Adjunto el <b>Informe Hist&oacute;rico Ecomac DETALLADO, cliente por cliente</b> (11.031 correos, Sep 2024 &rarr; Ago 2026):</p>
<ul>
<li><b>{len(casos)} clientes enviados</b> desde el inicio de los tiempos, listados uno por uno con fecha, ejecutiva, tiempo de 1&ordf; respuesta y estado.</li>
<li><b>{verdes_tot} en verde</b> (aprobados o en escrituraci&oacute;n) y <b>{len(esc)} escrituraciones</b> detalladas con sus etapas.</li>
<li><b>&Uacute;ltimos 3 meses minucioso:</b> {len(m3)} clientes enviados, {len(verdes_3m)} en verde, {len(esc_3m)} con escritura.</li>
<li>Estad&iacute;stica mes a mes, tiempos de respuesta (mediana {mediana_h:.1f} h; {tasa_pre:.0f}% &rarr; {tasa_post:.0f}% de respuesta) y detalle por ejecutiva.</li>
</ul>
<p>Saludos,<br/>DashAI &mdash; Central Mutuos</p>"""
r = es.send_mail("gerardo.ext@centralmutuos.cl",
                 "Informe Histórico Ecomac DETALLADO — cliente por cliente (Sep 2024 → Ago 2026)",
                 cuerpo,
                 attachments=[{"filename": "Informe_Historico_Ecomac_Detallado.pdf",
                               "content_b64": base64.b64encode(pdf).decode()}])
print("ENCOLADO:", r)
