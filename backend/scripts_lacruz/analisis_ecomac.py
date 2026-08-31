"""Análisis histórico Ecomac: evaluaciones vs escrituraciones (casilla gerardo.ext)."""
import json, re, unicodedata
from email.utils import parsedate_to_datetime
from collections import defaultdict, Counter

D = json.load(open("/app/backend/scripts_lacruz/gerardo_headers.json"))

RX_RUT = re.compile(r"\b(\d{1,2}\.?\d{3}\.?\d{3})\s*-\s*([\dkK])\b")
RX_PREFIX = re.compile(r"^(re|rv|fwd|fw|recuperar|urgente|\*+urgente\*+)[:\s/]*", re.I)
KW_EVAL = re.compile(r"evaluaci|documentaci|documentos|credito hipotecario|crédito hipotecario|gestion bancaria|gestión bancaria|antecedentes|pre-?aprob|carpeta|simulaci|renta|hipotecari", re.I)
KW_APROB = re.compile(r"aprobad|aprobaci|pre-?aprob|carta oferta|resultado", re.I)
EJEC = {
    "yevillanuevad@ecomac.cl": "Yerko Villanueva",
    "aagalleguillosu@ecomac.cl": "Amalia Galleguillos",
    "gmunoz@ecomac.cl": "Gabriela Muñoz",
    "saguilar@ecomac.cl": "Scarlett Aguilar",
    "riarancibia@ecomac.cl": "Rita Arancibia",
}


def norm(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip().lower()


def thread_key(subj):
    s = norm(subj)
    prev = None
    while prev != s:
        prev = s
        s = RX_PREFIX.sub("", s).strip()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()[:80]


def rut_of(subj):
    m = RX_RUT.search(subj or "")
    if not m:
        return None
    return m.group(1).replace(".", "") + "-" + m.group(2).lower()


def parse(x):
    try:
        dt = parsedate_to_datetime(x["date"])
        return dt.strftime("%Y-%m"), dt
    except Exception:
        return None, None


def sender(x):
    m = re.search(r"[\w.+-]+@[\w.-]+", x.get("from", ""))
    return m.group().lower() if m else ""


# ── indexar ────────────────────────────────────────────────
rows = []
for x in D:
    mes, dt = parse(x)
    if not mes:
        continue
    rows.append({**x, "mes": mes, "dt": dt, "tk": thread_key(x["subject"]),
                 "rut": rut_of(x["subject"]), "sender": sender(x)})

inbox = [r for r in rows if r["carpeta"] == "inbox_ecomac"]
sent = [r for r in rows if r["carpeta"] == "sent_ecomac"]

# ── A. solicitudes de evaluación (hilos únicos iniciados por Ecomac) ──
threads = {}
for r in sorted(inbox, key=lambda r: r["dt"]):
    if not KW_EVAL.search(r["subject"]) and not r["rut"]:
        continue
    t = threads.setdefault(r["tk"], {"first": r, "ruts": set(), "n": 0})
    t["n"] += 1
    if r["rut"]:
        t["ruts"].add(r["rut"])

sol_mes = Counter(t["first"]["mes"] for t in threads.values())
ruts_solicitados = set()
for t in threads.values():
    ruts_solicitados |= t["ruts"]

# ── B. respuestas y tiempos ────────────────────────────────
sent_by_tk = defaultdict(list)
for r in sent:
    sent_by_tk[r["tk"]].append(r)
tiempos, respondidos = [], 0
for tk, t in threads.items():
    reps = [s for s in sent_by_tk.get(tk, []) if s["dt"] >= t["first"]["dt"]]
    if reps:
        respondidos += 1
        delta = (min(reps, key=lambda s: s["dt"])["dt"] - t["first"]["dt"]).total_seconds() / 3600
        if 0 <= delta < 24 * 30:
            tiempos.append(delta)

# ── C. señales de aprobación en enviados ───────────────────
aprob_mes = Counter()
aprob_hilos = set()
for r in sent:
    if KW_APROB.search(r["subject"]):
        if r["tk"] not in aprob_hilos:
            aprob_hilos.add(r["tk"])
            aprob_mes[r["mes"]] += 1

# ── D. escrituraciones: cliente + etapa ────────────────────
RX_NOMBRE = [
    re.compile(r"borrador escritura (?:de compraventa )?(?:de )?([a-z\u00f1\u00e1\u00e9\u00ed\u00f3\u00fa ]{6,45}?)\s*(?:op\b|$|//|,)", re.I),
    re.compile(r"borrador cliente \d+ ([a-z\u00f1\u00e1\u00e9\u00ed\u00f3\u00fa ]{6,45}?)\s*(?://|$|,)", re.I),
    re.compile(r"escritura (?:de )?([a-z\u00f1\u00e1\u00e9\u00ed\u00f3\u00fa ]{6,40}?)\s+op\b", re.I),
    re.compile(r"firma (?:de |mandatario de |inmobiliaria op )?([a-z\u00f1\u00e1\u00e9\u00ed\u00f3\u00fa ]{6,40}?)\s+op\b", re.I),
    re.compile(r"titulos? (?:aprobados? )?(?:de |// )?(?:estudio de titulos? (?:de )?)?([a-z\u00f1\u00e1\u00e9\u00ed\u00f3\u00fa ]{6,40}?)\s*(?://|$)", re.I),
]
STOP = {"de", "la", "el", "los", "las", "y", "del", "con", "operacion"}


def cliente_esc(subj):
    s = norm(subj)
    rut = rut_of(subj)
    if rut:
        return "rut:" + rut
    for rx in RX_NOMBRE:
        m = rx.search(s)
        if m:
            toks = [w for w in m.group(1).split() if w not in STOP and len(w) > 2]
            if 2 <= len(toks) <= 5:
                return " ".join(toks)
    return None


esc = defaultdict(lambda: {"etapas": {}, "meses": {}})
ORDEN = {"esc_borrador": 1, "esc_escritura": 2, "esc_firma": 3, "esc_titulos": 3}
for r in sorted([r for r in rows if r["carpeta"].startswith("esc_")], key=lambda r: r["dt"]):
    c = cliente_esc(r["subject"])
    if not c:
        continue
    e = esc[c]
    lvl = ORDEN[r["carpeta"]]
    if lvl not in e["etapas"] or r["dt"] < e["etapas"][lvl]:
        e["etapas"][lvl] = r["dt"]
    # señal firmada explícita
    if re.search(r"firmad|lista para firma|titulos aprobados", norm(r["subject"])):
        e["etapas"][4] = min(e["etapas"].get(4, r["dt"]), r["dt"])

esc_borr_mes = Counter()
esc_firma_mes = Counter()
for c, e in esc.items():
    if 1 in e["etapas"] or 2 in e["etapas"]:
        dt = e["etapas"].get(1) or e["etapas"].get(2)
        esc_borr_mes[dt.strftime("%Y-%m")] += 1
    top = max(e["etapas"])
    if top >= 3:
        esc_firma_mes[e["etapas"][top].strftime("%Y-%m")] += 1

# ── E. ejecutivas ──────────────────────────────────────────
ejec_stats = {}
for mail, nombre in EJEC.items():
    ths = [t for t in threads.values() if t["first"]["sender"] == mail]
    total_mails = sum(1 for r in inbox if r["sender"] == mail)
    ruts = set()
    for t in ths:
        ruts |= t["ruts"]
    aprob = sum(1 for t in ths if any(KW_APROB.search(s["subject"]) for s in sent_by_tk.get(t["first"]["tk"], [])))
    ejec_stats[nombre] = {"correos": total_mails, "solicitudes": len(ths), "ruts": len(ruts), "aprob_señal": aprob}

# ── salida ─────────────────────────────────────────────────
if __name__ == "__main__":
    out = {
        "total_correos": len(rows),
        "solicitudes_por_mes": dict(sorted(sol_mes.items())),
        "total_solicitudes": len(threads),
        "ruts_unicos": len(ruts_solicitados),
        "respondidos": respondidos,
        "tiempo_mediana_h": sorted(tiempos)[len(tiempos) // 2] if tiempos else None,
        "tiempo_promedio_h": sum(tiempos) / len(tiempos) if tiempos else None,
        "aprobaciones_señal_por_mes": dict(sorted(aprob_mes.items())),
        "esc_clientes_unicos": len(esc),
        "esc_borrador_por_mes": dict(sorted(esc_borr_mes.items())),
        "esc_firma_titulos_por_mes": dict(sorted(esc_firma_mes.items())),
        "ejecutivas": ejec_stats,
    }
    json.dump(out, open("/app/backend/scripts_lacruz/informe_stats.json", "w"), ensure_ascii=False, indent=1, default=str)
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
