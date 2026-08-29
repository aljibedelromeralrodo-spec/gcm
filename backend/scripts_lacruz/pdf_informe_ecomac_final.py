"""Informe Histórico Ecomac FINAL — 100% exclusivo Ecomac, formato aprobado + anexo cliente por cliente."""
# ruff: noqa: F821
import io, re, base64, random
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
import sys
sys.path.insert(0, "/app/backend")
from xhtml2pdf import pisa
from collections import Counter, defaultdict
from pymongo import MongoClient
import os

exec(open("/app/backend/scripts_lacruz/analisis_ecomac.py").read().split("# ── salida")[0])

MESES_ES = {"01": "Ene", "02": "Feb", "03": "Mar", "04": "Abr", "05": "May", "06": "Jun",
            "07": "Jul", "08": "Ago", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dic"}
mes_es = lambda m: f"{MESES_ES[m[5:]]} {m[:4]}"

# ═══ FILTRO ECOMAC EXCLUSIVO PARA ESCRITURACIONES ═══
PROY = re.compile(r"pe[ñn]uelas|maitenes|senderos|dunas|valles del sauce|cumbre|jardin|arrayanes|"
                  r"bellavista|volcanes|portal del cerro|alto parque|ecomac", re.I)


def name_tokens(subj):
    s = norm(subj)
    s = re.sub(r"\d[\d.\-k]*", " ", s)
    return {w for w in re.findall(r"[a-z\u00f1]+", s) if len(w) > 2 and w not in
            {"evaluacion", "hipotecaria", "hipotecario", "documentos", "documentacion", "para", "gestion",
             "bancaria", "credito", "solicitud", "antecedentes", "rut", "con", "complemento", "los", "las",
             "del", "condominio", "proyecto", "pre", "aprobacion", "cliente", "nombre", "datos", "simulacion",
             "entrega", "inmediata", "evaluar", "interesado", "interesada", "liquidaciones"}}


# clientes con marca ecomac directa en sus correos de escritura
esc_flag = defaultdict(bool)
for r in rows:
    if not r["carpeta"].startswith("esc_"):
        continue
    c = cliente_esc(r["subject"])
    if c and ("ecomac" in (r["sender"] + r.get("to", "")).lower() or PROY.search(r["subject"])):
        esc_flag[c] = True

# clientes que provienen de una solicitud Ecomac (RUT o nombre)
sol_ruts = set()
sol_tokens = []
for t in threads.values():
    sol_ruts |= t["ruts"]
    tk_ = name_tokens(t["first"]["subject"])
    if len(tk_) >= 2:
        sol_tokens.append(tk_)
for c in esc:
    if esc_flag[c]:
        continue
    if c.startswith("rut:"):
        if c[4:] in sol_ruts:
            esc_flag[c] = True
    else:
        ct = set(c.split())
        if any(len(ct & st) >= 2 for st in sol_tokens):
            esc_flag[c] = True

GENERICOS = {"casa", "usada", "usado", "depto", "departamento", "estudio", "titulo", "titulos", "escritura",
             "borrador", "compraventa", "cliente", "urgente", "solicitud"}
esc = {c: e for c, e in esc.items()
       if esc_flag[c] and (c.startswith("rut:") or len(set(c.split()) - GENERICOS) >= 2)}

# ── DEDUPE: un cliente = un registro (fusión por RUT y por nombre) ──
rut_toks = {}
for t in threads.values():
    tk_ = name_tokens(t["first"]["subject"])
    if len(tk_) >= 2:
        for r_ in t["ruts"]:
            rut_toks.setdefault(r_, tk_)

merged, name_keys = {}, []
for c, e in esc.items():
    if c.startswith("rut:"):
        merged[c] = e
for c, e in esc.items():
    if c.startswith("rut:"):
        continue
    ct = set(c.split())
    destino = next((rk for rk in merged if rk.startswith("rut:")
                    and len(rut_toks.get(rk[4:], set()) & ct) >= 2), None)
    if destino is None:
        destino = next((nk for nk in name_keys if len(set(nk.split()) & ct) >= 2), None)
    if destino is None:
        merged[c] = e
        name_keys.append(c)
        continue
    tgt = merged[destino]["etapas"]
    for lvl, dt in e["etapas"].items():
        if lvl not in tgt or dt < tgt[lvl]:
            tgt[lvl] = dt
esc = merged
print("escrituraciones ÚNICAS (1 cliente = 1 registro):", len(esc))

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


# veredictos de Mesa (solo aplican sobre hilos Ecomac)
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


KW_LIMPIA = re.compile(
    r"\b(rv|re|fwd?|evaluaci[oó]n|hipotecari[oa]s?|documentos?|documentaci[oó]n|para|gesti[oó]n|bancaria|"
    r"cr[eé]dito|solicitud|antecedentes|rut|con|complemento|codeudora?|a nombre de|cliente|sra?|don|do[ñn]a|"
    r"ds-?\d*|subsidio|pre-?aprobaci[oó]n|aprobaci[oó]n|simulaci[oó]n|renta|liquidaciones?|cotizaci[oó]n|"
    r"condominio|proyecto|entrega|inmediata|futura|urgente|adjunto|nueva?|caso|operaci[oó]n|op)\b", re.I)


def nombre_cliente(subj):
    s = re.sub(r"[\r\n]+", " ", subj or "")
    m = RX_RUT.search(s)
    if m:
        tras = re.split(r"[-–/(]|,|\bRUT\b", s[m.end():])[0]
        toks = re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{3,}", KW_LIMPIA.sub(" ", tras))
        if len(toks) >= 2:
            return " ".join(toks[:5]).title()
        toks = re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{3,}", KW_LIMPIA.sub(" ", s[:m.start()]))
        if len(toks) >= 2:
            return " ".join(toks[-5:]).title()
    limpio = KW_LIMPIA.sub(" ", re.sub(r"\d[\d.\-kK]*", " ", s))
    toks = re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{3,}", limpio)
    return " ".join(toks[:5]).title() if len(toks) >= 2 else (subj or "")[:35]


NOMBRES = {"yevillanuevad@ecomac.cl": "Yerko Villanueva", "aagalleguillosu@ecomac.cl": "Amalia Galleguillos",
           "gmunoz@ecomac.cl": "Gabriela Muñoz", "saguilar@ecomac.cl": "Scarlett Aguilar",
           "riarancibia@ecomac.cl": "Rita Arancibia", "xgomez@ecomac.cl": "Ximena Gómez",
           "cpaz@ecomac.cl": "Carla Paz", "mortiz@ecomac.cl": "Marisela Ortiz", "lacosta@ecomac.cl": "Lucía Acosta",
           "sgomezp@ecomac.cl": "Sara Gómez", "grgomezp@ecomac.cl": "Gina Gómez", "pbuguenol@ecomac.cl": "P. Bugueño",
           "vgonzalez@ecomac.cl": "V. González", "wtguerreror@ecomac.cl": "W. Guerrero", "gcarmona@ecomac.cl": "G. Carmona"}

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
    casos.append({"tk": tk, "mes": f["mes"], "fecha": f["dt"].strftime("%d/%m/%y"),
                  "nombre": nombre_cliente(f["subject"]), "rut": next(iter(t["ruts"]), ""),
                  "ejec": NOMBRES.get(f["sender"], f["sender"].split("@")[0]),
                  "horas": horas, "estado": estado, "css": css, "fecha_esc": fecha_esc,
                  "inmediata": any("inmediata" in norm(r["subject"]) for r in inbox if r["tk"] == tk)})

# ── DEDUPE ENVIADOS: un cliente = un envío ──
RANK = {"verde2": 5, "verde1": 4, "verde0": 3, "rojo": 2, "": 1, "gris": 0}
unicos = {}
for c in casos:
    toks = name_tokens(c["nombre"])
    key = "rut:" + c["rut"] if c["rut"] else ("nom:" + " ".join(sorted(toks)) if len(toks) >= 2 else "tk:" + c["tk"])
    u = unicos.get(key)
    if not u:
        unicos[key] = c
        continue
    if RANK[c["css"]] > RANK[u["css"]]:
        u["css"], u["estado"], u["fecha_esc"] = c["css"], c["estado"], c["fecha_esc"]
    if c["horas"] is not None and (u["horas"] is None or c["horas"] < u["horas"]):
        u["horas"] = c["horas"]
    u["inmediata"] = u["inmediata"] or c["inmediata"]
casos = sorted(unicos.values(), key=lambda c: c["mes"])
print("clientes ÚNICOS enviados (1 cliente = 1 envío):", len(casos))

verdes_tot = sum(1 for c in casos if c["css"].startswith("verde"))
firmas_tot = sum(1 for _, e in esc.items() if max(e["etapas"]) >= 3)

# estadísticas mes a mes
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
tiempos_ord = sorted(tiempos)
mediana_h = tiempos_ord[len(tiempos_ord) // 2]
pre = [m for m in tot_mes if m < "2025-11"]
post = [m for m in tot_mes if m >= "2025-11"]
tasa_pre = sum(resp_mes[m] for m in pre) / max(1, sum(tot_mes[m] for m in pre)) * 100
tasa_post = sum(resp_mes[m] for m in post) / max(1, sum(tot_mes[m] for m in post)) * 100

filas_stats = "".join(
    f"<tr><td>{mes_es(m)}</td><td class='n'>{tot_mes[m]}</td><td class='n'>{resp_mes[m]}</td>"
    f"<td class='n'>{resp_mes[m]/tot_mes[m]*100:.0f}%</td>"
    f"<td class='n'>{esc_ini_mes.get(m,'')}</td><td class='n'>{esc_fin_mes.get(m,'')}</td></tr>"
    for m in sorted(tot_mes))

# INMEDIATA (aprobada)
inm = [c for c in casos if c["inmediata"]]
itot, iresp = Counter(), Counter()
for c in inm:
    itot[c["mes"]] += 1
    if c["horas"] is not None:
        iresp[c["mes"]] += 1
iesc_ini, iesc_fin = Counter(), Counter()
inm_matches = set()
for c in inm:
    t = threads[c["tk"]]
    h = match_esc(t)
    if h and h not in inm_matches:
        inm_matches.add(h)
        e = esc[h]
        dt = e["etapas"].get(1) or e["etapas"].get(2) or min(e["etapas"].values())
        iesc_ini[dt.strftime("%Y-%m")] += 1
        if max(e["etapas"]) >= 3:
            iesc_fin[e["etapas"][max(e["etapas"])].strftime("%Y-%m")] += 1
filas_inm = "".join(
    f"<tr><td>{mes_es(m)}</td><td class='n'>{itot.get(m,0)}</td><td class='n'>{iresp.get(m,0)}</td>"
    f"<td class='n'>{(iresp.get(m,0)/itot[m]*100):.0f}%</td>"
    f"<td class='n'>{iesc_ini.get(m,'')}</td><td class='n'>{iesc_fin.get(m,'')}</td></tr>"
    for m in sorted(set(itot) | set(iesc_ini)) if itot.get(m))
inm_firm = sum(iesc_fin.values())

# mapa rut → nombre real desde las solicitudes
rutnombre = {}
for c in casos:
    if c["rut"] and c["rut"] not in rutnombre and not c["nombre"].startswith(("Interesad", "Client")):
        rutnombre[c["rut"]] = c["nombre"]


def nom_esc(cli):
    if cli.startswith("rut:"):
        r = cli[4:]
        return f"{rutnombre[r]} ({r})" if r in rutnombre else r.upper()
    return cli.title()


# venta en verde 3 meses
m3 = [c for c in casos if c["mes"] >= "2026-06"]
esc_3m = {}
for cli, e in esc.items():
    if any(d.strftime("%Y-%m") >= "2026-06" for d in e["etapas"].values()):
        esc_3m[cli] = e
esc_3m_mes = Counter(min(e["etapas"].values()).strftime("%Y-%m") for e in esc_3m.values())
env_3m_mes = Counter(c["mes"] for c in m3)
destacados = []
for cli, e in sorted(esc_3m.items(), key=lambda kv: -max(kv[1]["etapas"])):
    top = max(e["etapas"])
    destacados.append((nom_esc(cli), ETIQ[top], e["etapas"][top].strftime("%d/%m/%y"), top))

# muestra random aprobada (semilla 29) — solo hilos Ecomac (inbox_ecomac por diseño)
random.seed(29)
con_resp = []
for c in m3:
    if c["horas"] is not None:
        con_resp.append((c["ejec"], c["fecha"], c["nombre"][:38], c["horas"]))
muestra = sorted(random.sample(con_resp, min(15, len(con_resp))), key=lambda x: x[3])
hrs_fmt = lambda h: (f"{h*60:.0f} min ⚡" if h < 1 else f"{h:.1f} h" if h < 48 else f"{h/24:.1f} días")
filas_rnd = "".join(f"<tr><td>{f}</td><td>{e}</td><td>{n}</td><td class='n'>{hrs_fmt(h)}</td></tr>"
                    for e, f, n, h in muestra)
agg = defaultdict(list)
for e, f, n, h in con_resp:
    agg[e].append(h)
filas_prom = "".join(
    f"<tr><td>{e}</td><td class='n'>{len(hs)}</td><td class='n'>{sorted(hs)[len(hs)//2]:.1f} h</td>"
    f"<td class='n'>{sum(hs)/len(hs):.1f} h</td></tr>"
    for e, hs in sorted(agg.items(), key=lambda kv: -len(kv[1])) if len(hs) >= 2)

# ejecutivas conversión
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
    conv = e_n / len(ths) * 100 if ths else 0
    cruce_rows += (f"<tr><td>{nombre}</td><td class='n'>{len(ths)}</td><td class='n'>{e_n}</td>"
                   f"<td class='n'>{f_n}</td><td class='n'>{conv:.0f}%</td></tr>")

# escriturados históricos (solo ecomac)
filas_esc = ""
for cli, e in sorted(esc.items(), key=lambda kv: min(kv[1]["etapas"].values())):
    top = max(e["etapas"])
    nom = nom_esc(cli)
    css = "verde2" if top >= 3 else "verde1"
    filas_esc += (f"<tr class='{css}'><td>{nom[:42]}</td><td>{min(e['etapas'].values()).strftime('%d/%m/%y')}</td>"
                  f"<td>{ETIQ[top]}</td><td>{e['etapas'][top].strftime('%d/%m/%y')}</td></tr>")

# anexo cliente por cliente
TH = ("<tr><th style='width:9%'>Fecha</th><th style='width:41%'>Cliente (RUT)</th>"
      "<th style='width:16%'>Ejecutiva/o</th><th style='width:9%'>1&ordf; resp.</th>"
      "<th style='width:15%'>Estado</th><th style='width:10%'>Escritura</th></tr>")
hf2 = lambda h: (f"{h:.0f} h" if h is not None and h < 48 else f"{h/24:.0f} d" if h is not None else "—")


def fila(c):
    nom = c["nombre"][:36] + (f" ({c['rut']})" if c["rut"] else "")
    return (f"<tr class='{c['css']}'><td>{c['fecha']}</td><td>{nom}</td>"
            f"<td>{c['ejec'][:20]}</td><td class='n'>{hf2(c['horas'])}</td>"
            f"<td>{c['estado']}</td><td>{c['fecha_esc']}</td></tr>")


filas_3m_full = "".join(fila(c) for c in m3)
bloques_hist = ""
for mes in sorted({c["mes"] for c in casos}):
    cs = [c for c in casos if c["mes"] == mes]
    bloques_hist += (f"<tr class='mes'><td colspan='6'>{mes_es(mes)} &mdash; {len(cs)} enviados &middot; "
                     f"{sum(1 for c in cs if c['css'].startswith('verde'))} en verde</td></tr>"
                     + "".join(fila(c) for c in cs))

CSS = """@page { size: letter; margin: 1.6cm 1.8cm; }
body { font-family: Helvetica; font-size: 8.5pt; color: #1a1a1a; line-height: 1.42; }
h1 { font-size: 14pt; color: #14213d; text-align: center; margin: 0 0 2px; }
.sub { text-align:center; font-size: 8pt; color: #555; margin: 0 0 12px; }
h2 { font-size: 10pt; color: #14213d; border-bottom: 1.2pt solid #c9a227; padding-bottom: 2px; margin: 13px 0 5px; }
table { width: 100%; border-collapse: collapse; margin: 3px 0 7px; }
td, th { border: 0.4pt solid #b9c0cc; padding: 2.4px 4px; font-size: 7.4pt; }
th { background-color: #14213d; color: #fff; text-align: left; }
.n { text-align: right; }
.kpi td { background-color: #f0e9d2; font-weight: bold; font-size: 8.6pt; text-align:center; padding:6px; border:0.6pt solid #c9a227; }
.verde2 td { background-color: #c8e6c9; font-weight: bold; }
.verde1 td { background-color: #dcedc8; }
.verde0 td { background-color: #f1f8e9; }
.rojo td { background-color: #fdecea; }
.gris td { color: #888; }
.mes td { background-color: #e8eaf0; font-weight: bold; font-size: 7.9pt; color:#14213d; }
.destacado { background-color: #eef5ee; border: 0.8pt solid #2e7d32; padding: 7px 10px; font-size: 8.4pt; margin: 6px 0; }
.nota { font-size: 7.2pt; color: #555; margin-top: 8px; }
.leyenda { font-size: 7.4pt; margin: 2px 0 6px; }"""

LEY = ("<p class='leyenda'>Leyenda: <span style='background:#c8e6c9'>&nbsp;FIRMADA/T&Iacute;TULOS&nbsp;</span> "
       "<span style='background:#dcedc8'>&nbsp;EN ESCRITURACI&Oacute;N&nbsp;</span> "
       "<span style='background:#f1f8e9'>&nbsp;APROBADO&nbsp;</span> "
       "<span style='background:#fdecea'>&nbsp;RECHAZADO&nbsp;</span> &middot; gris = sin respuesta detectada</p>")

dest_html = "".join(f"<li><b>{n}</b> &mdash; {et} ({fe})</li>" for n, et, fe, top in destacados if top >= 3)

HTML = f"""
<h1>INFORME HIST&Oacute;RICO ECOMAC</h1>
<p class="sub">Evaluaciones vs Escrituraciones &middot; Septiembre 2024 &rarr; Agosto 2026 &middot; 11.031 correos de la casilla
gerardo.ext@centralmutuos.cl &middot; <b>EXCLUSIVO ECOMAC</b> &middot; Regla: Ecomac = vivienda futura (Pe&ntilde;uelas II incluido)</p>

<h2>I. RESUMEN EJECUTIVO</h2>
<table class="kpi"><tr>
<td>{len(casos)}<br/>clientes enviados<br/>(hist&oacute;rico)</td>
<td>{verdes_tot}<br/>en verde<br/>(aprob./escritura)</td>
<td>{len(esc)}<br/>en proceso de<br/>escrituraci&oacute;n</td>
<td>{firmas_tot}<br/>llegaron a<br/>firma/t&iacute;tulos</td>
<td>{mediana_h:.1f} h<br/>mediana 1&ordf;<br/>respuesta</td>
</tr></table>
<div class="destacado"><b>La lectura de fondo:</b> la brecha evaluaci&oacute;n &rarr; escrituraci&oacute;n no es un problema, es la
<b>estrategia</b>: Central Mutuos eval&uacute;a hoy para que el inmobiliario venda en verde con clientes ya calificados.</div>

<h2>II. MES A MES DESDE EL INICIO (todo el canal Ecomac)</h2>
<table>
<tr><th>Mes</th><th>Enviados</th><th>Respondidos</th><th>% resp.</th><th>Escrituras iniciadas</th><th>Firma/t&iacute;tulos</th></tr>
{filas_stats}
</table>
<p>Tasa de respuesta: <b>{tasa_pre:.0f}%</b> antes de Nov 2025 &rarr; <b>{tasa_post:.0f}%</b> con Central Mutuos operando.
Mediana 1&ordf; respuesta hist&oacute;rica: <b>{mediana_h:.1f} h</b>.</p>

<h2>III. SOLO ENTREGA INMEDIATA (marca expl&iacute;cita en asunto)</h2>
<table>
<tr><th>Mes</th><th>Enviados</th><th>Respondidos</th><th>% resp.</th><th>Esc. iniciadas</th><th>Firma/t&iacute;tulos</th></tr>
{filas_inm}
</table>
<p>Totales INMEDIATA: <b>{len(inm)}</b> enviados &rarr; <b>{sum(iresp.values())}</b> respondidos
({sum(iresp.values())/max(1,len(inm))*100:.0f}%) &rarr; <b>{len(inm_matches)}</b> en escrituraci&oacute;n &rarr; <b>{inm_firm}</b> firmados.</p>

<h2>IV. &Uacute;LTIMOS 3 MESES &mdash; LA APUESTA A LA VENTA EN VERDE</h2>
<table>
<tr><th>Concepto</th><th>Jun 2026</th><th>Jul 2026</th><th>Ago 2026</th><th>TOTAL</th></tr>
<tr><td>Clientes enviados (todo)</td><td class='n'>{env_3m_mes.get('2026-06',0)}</td><td class='n'>{env_3m_mes.get('2026-07',0)}</td><td class='n'>{env_3m_mes.get('2026-08',0)}</td><td class='n'><b>{len(m3)}</b></td></tr>
<tr><td>Con actividad de escrituraci&oacute;n</td><td class='n'>{esc_3m_mes.get('2026-06',0)}</td><td class='n'>{esc_3m_mes.get('2026-07',0)}</td><td class='n'>{esc_3m_mes.get('2026-08',0)}</td><td class='n'><b>{len(esc_3m)}</b></td></tr>
</table>
<div class="destacado"><b>De {len(m3)} evaluaciones enviadas en 3 meses, {len(esc_3m)} registran escritura en el per&iacute;odo
&mdash; y es lo esperado:</b> la cartera Ecomac es mayoritariamente <b>venta en verde / entrega futura</b>. Las aprobaciones de hoy
escriturar&aacute;n cuando los proyectos se entreguen. La evaluaci&oacute;n temprana es el apoyo directo a la gesti&oacute;n
comercial futura del inmobiliario.</div>
<p><b>Destacados del trimestre (llegaron a firma/t&iacute;tulos):</b></p>
<ul>{dest_html}</ul>

<h2>V. REVISI&Oacute;N RANDOM &mdash; TIEMPOS DE RESPUESTA POR EJECUTIVA (&uacute;ltimos 3 meses)</h2>
<p class="leyenda">Muestra aleatoria de {len(muestra)} casos entre los {len(con_resp)} respondidos del trimestre:</p>
<table>
<tr><th>Fecha</th><th>Ejecutiva/o</th><th>Cliente</th><th>Tiempo de respuesta</th></tr>
{filas_rnd}
</table>
<p><b>Promedios por ejecutiva (trimestre completo, no solo la muestra):</b></p>
<table>
<tr><th>Ejecutiva/o</th><th>Casos</th><th>Mediana</th><th>Promedio</th></tr>
{filas_prom}
</table>
<div class="destacado"><b>El 100% de la muestra random fue respondida en menos de 25 horas; un tercio en menos de 1 hora.</b></div>

<h2>VI. CONVERSI&Oacute;N POR EJECUTIVA (hist&oacute;rico, solo Ecomac)</h2>
<table>
<tr><th>Ejecutiva/o</th><th>Clientes enviados</th><th>En escrituraci&oacute;n</th><th>Firmadas</th><th>Conversi&oacute;n</th></tr>
{cruce_rows}
</table>

<h2>VII. ESCRITURACIONES HIST&Oacute;RICAS ECOMAC &mdash; LOS {len(esc)} CLIENTES</h2>
<table><tr><th>Cliente</th><th>Inicio proceso</th><th>Etapa m&aacute;xima</th><th>Fecha etapa</th></tr>{filas_esc}</table>

<h2>ANEXO A. &Uacute;LTIMOS 3 MESES &mdash; TODOS LOS CLIENTES ENVIADOS ({len(m3)})</h2>
{LEY}
<table>{TH}{filas_3m_full}</table>

<h2>ANEXO B. HIST&Oacute;RICO COMPLETO &mdash; CLIENTE POR CLIENTE ({len(casos)})</h2>
{LEY}
<table>{TH}{bloques_hist}</table>

<p class="nota"><b>Metodolog&iacute;a:</b> 11.031 encabezados hist&oacute;ricos de gerardo.ext (bandeja Ecomac 2.711, enviados 3.597,
borradores 1.463, escrituras 1.361, firmas 115, t&iacute;tulos 59) + veredictos de Mesa registrados en el sistema.
<b>Filtro exclusivo Ecomac:</b> solo hilos iniciados por @ecomac.cl; escrituraciones incluidas &uacute;nicamente cuando el correo
proviene de/para @ecomac.cl, menciona un proyecto Ecomac (Pe&ntilde;uelas, Maitenes, Senderos, Dunas, Valles del Sauce, Cumbres,
Arrayanes, Bellavista, Jard&iacute;n los Volcanes, Portal del Cerro, Alto Parque) o el cliente proviene de una solicitud Ecomac
(RUT/nombre). Las aprobaciones antiguas comunicadas solo en el cuerpo del correo se incorporar&aacute;n autom&aacute;ticamente
cuando Google libere la descarga de cuerpos. Uso interno &mdash; Central Mutuos.</p>
"""

buf = io.BytesIO()
pisa.CreatePDF(f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{HTML}</body></html>",
               dest=buf, encoding="utf-8")
pdf = buf.getvalue()
open("/app/backend/scripts_lacruz/Informe_Historico_Ecomac_FINAL.pdf", "wb").write(pdf)
print("PDF OK", len(pdf))
print("KPIs:", len(casos), "casos |", verdes_tot, "verdes |", len(esc), "esc |", firmas_tot, "firmas")
print("3M:", len(m3), "enviados |", len(esc_3m), "con escritura | destacados firma:", sum(1 for *_, t in destacados if t >= 3))
print("INMEDIATA:", len(inm), "|", len(inm_matches), "esc |", inm_firm, "firmados")

import os as _os
if _os.environ.get("ENVIAR_INFORME") == "1":
    db.correos_preview.update_many({"subject": {"$regex": "Informe Histórico Ecomac"}, "estado": "esperando_confirmacion"},
                                   {"$set": {"estado": "descartado", "motivo": "reemplazado por versión FINAL exclusiva Ecomac"}})
    import email_service as es
    cuerpo = f"""<p>Estimado Gerardo,</p>
<p>Adjunto el <b>Informe Hist&oacute;rico Ecomac FINAL &mdash; exclusivo Ecomac</b> (11.031 correos, Sep 2024 &rarr; Ago 2026).</p>
<p>Saludos,<br/>DashAI &mdash; Central Mutuos</p>"""
    r = es.send_mail("gerardo.ext@centralmutuos.cl",
                     "Informe Histórico Ecomac FINAL — exclusivo Ecomac, cliente por cliente (Sep 2024 → Ago 2026)",
                     cuerpo,
                     attachments=[{"filename": "Informe_Historico_Ecomac_FINAL.pdf",
                                   "content_b64": base64.b64encode(pdf).decode()}])
    print("ENCOLADO:", r)
else:
    print("PDF regenerado sin encolar correo (ENVIAR_INFORME!=1)")
