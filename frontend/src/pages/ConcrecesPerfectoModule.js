import { useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import { pdfjs } from "react-pdf";
import { API_URL, formatCurrency } from "../utils/formatters";

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

const UF_RESPALDO = 40871.14;
const COLOR = {
  APROBADO: "#7ee787",
  OBSERVADO: "#fbbf24",
  "COMITE EXCEPCION": "#c4b5fd",
  RECHAZO: "#ff7b72",
  RECHAZADO: "#ff7b72",
  BLOQUEADO: "#ff7b72",
  "BLOQUEO 412": "#ff7b72",
};
const MADRE_DEF = {
  con_subsidio: {
    valor_min_uf: 1000, valor_max_uf: 4000, monto_min_uf: 800, monto_max_uf: 3200,
    pie_min: 0.20, plazo_min: 20, plazo_max: 40, div_renta_max: 0.40, carga_max: 0.55, ltv_duro: 0.795,
    tasa_hasta_2000: 6.5, tasa_mas_2000: 6.35, renta_min_titular_uf: 15,
  },
  sin_subsidio: {
    valor_min_uf: 1250, valor_max_uf: 5000, monto_min_uf: 1000, monto_max_uf: 4000,
    pie_min: 0.20, plazo_min: 20, plazo_max: 30, div_renta_max: 0.35, carga_max: 0.50, ltv_duro: 0.795,
    tasa: 5.9, renta_min_titular_uf: 25,
  },
};
const MADRE_FILAS = [
  ["valor_min_uf", "valorMinUF"],
  ["valor_max_uf", "valorMaxUF"],
  ["monto_min_uf", "montoMinUF"],
  ["monto_max_uf", "montoMaxUF"],
  ["pie_min", "pieMin"],
  ["plazo_min", "plazoMin"],
  ["plazo_max", "plazoMax"],
  ["div_renta_max", "divRentaMax"],
  ["carga_max", "cargaMax"],
  ["ltv_duro", "LTVduro"],
  ["tasa_hasta_2000", "tasaHasta2000"],
  ["tasa_mas_2000", "tasaMas2000"],
  ["tasa", "tasa"],
  ["renta_min_titular_uf", "rentaMinTitular"],
];
const BLOQUEOS = [
  "Deuda Directa Morosa NO",
  "Deuda Vencida NO",
  "Castigada NO",
  "Indirecta morosa/vencida/castigada NO",
  "Mora Comercial NO",
  "Protestos vigentes NO",
  "Pagares Impagos NO",
  "SAR NO",
];
const INI = {
  vNueva: true, vCasa: true, vHab: true, nacOk: true,
  l1: "", l2: "", l3: "", l4: "", l5: "", l6: "",
  afp: "", edad: "35", valor: "2500", monto: "2000",
  pie: "", plazo: "30", div: "", deudas: "150000",
  hab: "", viat: "", antig: "", cont: "",
  actividad: "dependiente", contrato: "indefinido",
  sub: true, tipo: "sin", rentaCod: "0", deudasCod: "0",
  tasa: "", desg: "", inc: "",
  renta: "1200000", client_type: "DEPENDIENTE",
  exento_afp: false, licencia_medica: false,
  fecha_entrega: "Inmediata", ejec_interno: "Deisy Salazar",
  rut_titular: "", force_incompleto: false,
  docs: { cedula: false, liquidacion: false, afp: false, cmf: false,
    imp_renta: false, boletas: false, renta_vitalicia: false },
};

const FILAS_POL = [
  ["valor_min_uf", "Valor min UF"],
  ["valor_max_uf", "Valor max UF"],
  ["monto_min_uf", "Monto min UF"],
  ["monto_max_uf", "Monto max UF"],
  ["pie_min", "Pie min"],
  ["financ_max", "Financ max"],
  ["plazo_min", "Plazo min"],
  ["plazo_max", "Plazo max"],
  ["div_renta_max", "Div/Renta max"],
  ["carga_max", "Carga max"],
  ["ltv_duro", "LTV duro"],
  ["renta_min_titular_uf", "Renta min titular UF"],
  ["edad_max_termino", "Edad máx término"],
];

function pct(v) {
  if (v == null || v === "") return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return String(v);
  return n <= 1.5 ? `${(n * 100).toFixed(1)}%` : String(n);
}

function Spark({ data, color = "#d4af37", testId = "cp-spark" }) {
  const nums = (data || []).map(Number).filter((n) => Number.isFinite(n));
  if (nums.length < 2) return null;
  const w = 520, h = 110, pad = 12;
  const min = Math.min(...nums), max = Math.max(...nums);
  const span = max - min || 1;
  const pts = nums.map((n, i) => {
    const x = pad + (i * (w - pad * 2)) / (nums.length - 1);
    const y = h - pad - ((n - min) / span) * (h - pad * 2);
    return `${x},${y}`;
  }).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" height="110" data-testid={testId}>
      <polyline fill="none" stroke={color} strokeWidth="2.5" points={pts} />
    </svg>
  );
}

async function textoPdf(file) {
  const buf = await file.arrayBuffer();
  const pdf = await pdfjs.getDocument({ data: buf }).promise;
  let t = "";
  for (let i = 1; i <= Math.min(pdf.numPages, 4); i += 1) {
    const page = await pdf.getPage(i);
    const content = await page.getTextContent();
    t += content.items.map((it) => it.str).join(" ") + "\n";
  }
  return t;
}

function liquidoDeTexto(t) {
  const m = /l[ií]quido\s*a\s*pagar[^\d]{0,40}(\d{1,3}(?:\.\d{3})+|\d{5,})/i.exec(t || "");
  if (!m) return 0;
  return Number(String(m[1]).replace(/\./g, "")) || 0;
}

const cell = {
  padding: "6px 8px", borderBottom: "1px solid #1f1f2e", fontSize: "0.78rem",
  fontFamily: "JetBrains Mono, ui-monospace, monospace",
};
const th = { ...cell, color: "#d4af37", fontSize: "0.68rem", letterSpacing: "0.08em", textTransform: "uppercase" };

export default function ConcrecesPerfectoModule({ valorUF, ufMeta, onUfChange }) {
  const [f, setF] = useState(INI);
  const [uf, setUf] = useState(Number(valorUF) > 0 ? Number(valorUF) : UF_RESPALDO);
  const [meta, setMeta] = useState(ufMeta || { fuente: "respaldo 29-08-2026", respaldo: true });
  const [res, setRes] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [ufLoading, setUfLoading] = useState(false);
  const [bloqueos, setBloqueos] = useState({});
  const [base, setBase] = useState(null);
  const [real, setReal] = useState(null);
  const [alertas, setAlertas] = useState([]);
  const [evo, setEvo] = useState([]);
  const [nCartas, setNCartas] = useState(0);
  const [overlay, setOverlay] = useState({});
  const [msg, setMsg] = useState("");
  const arranque = useRef(false);

  useEffect(() => { if (Number(valorUF) > 0) setUf(Number(valorUF)); }, [valorUF]);
  useEffect(() => { if (ufMeta) setMeta(ufMeta); }, [ufMeta]);

  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const chk = (k) => setF((p) => ({ ...p, [k]: !p[k] }));

  const payload = () => ({
    l1: f.l1, l2: f.l2, l3: f.l3, l4: f.l4, l5: f.l5, l6: f.l6,
    afp: f.afp, edad: f.edad, valor_propiedad_uf: f.valor, monto_credito_uf: f.monto,
    pie: f.pie, plazo: f.plazo, dividendo: f.div, deudas_titular: f.deudas,
    haberes: f.hab, viaticos: f.viat, antiguedad: f.antig, continuidad: f.cont,
    actividad: f.actividad, contrato: f.contrato, con_subsidio: f.sub,
    tipo_codeudor: f.tipo, renta_codeudor: f.rentaCod, deudas_codeudor: f.deudasCod,
    vivienda_nueva_usada: f.vNueva, casa_depto: f.vCasa, habitacional: f.vHab,
    nacionalidad_ok: f.nacOk, valor_uf: uf, tasa: f.tasa,
    seguro_desgravamen: f.desg, seguro_incendio: f.inc,
    deuda_prohibida: Object.values(bloqueos).some(Boolean),
    bloqueos, renta: f.renta, client_type: f.client_type,
    exento_afp: f.exento_afp, licencia_medica: f.licencia_medica,
    fecha_entrega: f.fecha_entrega, ejec_interno: f.ejec_interno,
    rut_titular: f.rut_titular, force_incompleto: f.force_incompleto,
    docs: Object.entries(f.docs || {}).filter(([, v]) => v).map(([k]) => k),
  });

  const cargarPolitica = async () => {
    try {
      const r = await axios.get(`${API_URL}/api/concreces-perfecto/politica`);
      setBase(r.data.base);
      setReal(r.data.real);
      setAlertas(r.data.alertas || []);
      setEvo(r.data.evolucion || []);
      setNCartas(r.data.n_cartas || 0);
      setOverlay(r.data.overlay || {});
    } catch { /* sin servidor: se evalúa igual con la constante */ }
  };

  const run = async (extra = {}) => {
    setCargando(true);
    try {
      const r = await axios.post(`${API_URL}/api/concreces-perfecto`, { ...payload(), ...extra });
      setRes(r.data);
      if (r.data?.uf_usada > 0) {
        setUf(r.data.uf_usada);
        if (onUfChange) onUfChange(r.data.uf_usada, r.data.uf);
      }
      if (r.data?.uf) setMeta(r.data.uf);
      if (r.data?.politica_base) setBase(r.data.politica_base);
      if (r.data?.politica_real_full) setReal(r.data.politica_real_full);
      if (r.data?.alertas_vigia) setAlertas(r.data.alertas_vigia);
    } catch {
      setMeta({ fuente: "respaldo 29-08-2026", dia_uf: "2026-08-29", en_vivo: false, respaldo: true });
      setRes({ semaforo: "OBSERVADO", motivos: ["Sin señal — UF de respaldo"],
        checks: [], uf_usada: uf || UF_RESPALDO, renta_titular: 0, renta_total: 0,
        div_renta: 0, carga: 0 });
    }
    setCargando(false);
  };

  useEffect(() => {
    if (arranque.current) return;
    arranque.current = true;
    cargarPolitica().then(() => run());
  }, []);

  const actualizarUF = async () => {
    setUfLoading(true);
    try {
      const r = await axios.get(`${API_URL}/api/valor-uf`, { params: { refresh: true } });
      const v = Number(r.data?.valor_uf) || 0;
      if (v > 0) {
        setUf(v);
        setMeta({ fuente: r.data.fuente, dia_uf: r.data.dia_uf, en_vivo: r.data.en_vivo, respaldo: false });
        if (onUfChange) onUfChange(v, r.data);
        await run({ valor_uf: v });
      } else await run({ refresh_uf: true });
    } catch {
      setMeta({ fuente: "respaldo 29-08-2026", dia_uf: "2026-08-29", en_vivo: false, respaldo: true });
      await run({ valor_uf: uf || UF_RESPALDO });
    }
    setUfLoading(false);
  };

  const subirLiqs = async (lista) => {
    const files = Array.from(lista || []).slice(0, 6);
    const locales = [];
    for (const file of files) {
      try {
        const t = await textoPdf(file);
        locales.push(liquidoDeTexto(t));
      } catch { locales.push(0); }
    }
    if (locales.some((n) => n > 0)) {
      const keys = ["l1", "l2", "l3", "l4", "l5", "l6"];
      setF((p) => {
        const n = { ...p };
        locales.forEach((v, i) => { if (v > 0) n[keys[i]] = String(v); });
        return n;
      });
      setMsg(`Liquidaciones leídas con pdf.js (${locales.filter((n) => n > 0).length}/6).`);
      return;
    }
    const fd = new FormData();
    files.forEach((file) => fd.append("files", file));
    const r = await axios.post(`${API_URL}/api/concreces-perfecto/liquidaciones`, fd);
    const keys = ["l1", "l2", "l3", "l4", "l5", "l6"];
    setF((p) => {
      const n = { ...p };
      (r.data.liquidaciones || []).forEach((row, i) => {
        if (row.liquido > 0) n[keys[i]] = String(row.liquido);
        if (row.haberes > 0) n.hab = String(row.haberes);
        if (row.viaticos > 0) n.viat = String(row.viaticos);
      });
      return n;
    });
    setMsg("Liquidaciones leídas por OCR de respaldo.");
  };

  const subirCartas = async (lista) => {
    const fd = new FormData();
    Array.from(lista || []).forEach((file) => fd.append("files", file));
    setMsg("Vigía leyendo cartas…");
    const r = await axios.post(`${API_URL}/api/concreces-perfecto/vigia`, fd);
    setReal(r.data.real);
    setAlertas(r.data.alertas || []);
    setEvo(r.data.evolucion || []);
    setNCartas(r.data.n_cartas || 0);
    setMsg(`${(r.data.ingestadas || []).length} carta(s) ingestadas. Vigía reentrenado.`);
    await run();
  };

  const subirCombinado = async (lista) => {
    if (!f.rut_titular) { setMsg("REGLA IVANA: indique RUT titular antes de armar el combinado."); return; }
    const fd = new FormData();
    Array.from(lista || []).forEach((file) => fd.append("files", file));
    fd.append("nombre", "Cliente V7");
    fd.append("rut_titular", f.rut_titular);
    fd.append("client_type", (f.client_type || "dependiente").toLowerCase());
    setMsg("Armando COMBINADO_PROTOCOLO…");
    try {
      const r = await axios.post(`${API_URL}/api/concreces-perfecto/combinado`, fd);
      const excl = (r.data.excluidos_rut || []).length;
      setMsg(`Combinado ${r.data.combinado || "—"} · ${excl} excluido(s) Ivana`
        + (r.data.combinado_codeudor ? ` · dual ${r.data.combinado_codeudor}` : "")
        + " · destino aprobaciones@centralmutuos.cl");
    } catch (e) {
      setMsg(e.response?.data?.detail || "Combinado bloqueado");
    }
  };

  const guardarOverlay = async () => {
    await axios.patch(`${API_URL}/api/concreces-perfecto/politica`, { overlay });
    setMsg("Overlay guardado. La constante POLITICA_BASE no se pisa.");
    await run();
  };

  const liqs = useMemo(() => [f.l1, f.l2, f.l3, f.l4, f.l5, f.l6].map(Number), [f]);
  const sema = res?.semaforo || res?.estado || "";
  const color = COLOR[sema] || "#d4af37";
  const fuenteTxt = meta?.respaldo
    ? "respaldo 29-08-2026 — sin internet"
    : (meta?.fuente === "sii.cl" ? "SII / Banco Central"
      : meta?.fuente === "mindicador.cl" ? "mindicador.cl"
      : (meta?.fuente || "sesión"));
  const lado = f.sub ? "con_subsidio" : "sin_subsidio";
  const baseLado = (overlay[lado] && Object.keys(overlay[lado]).length
    ? { ...(base || {})[lado], ...overlay[lado] }
    : (base || {})[lado]) || {};
  const realLado = (real || {})[lado] || {};

  const inp = (id, ph) => (
    <input data-testid={`cp-${id}`} value={f[id]} onChange={(e) => set(id, e.target.value)} placeholder={ph} />
  );
  const box = (id, label) => (
    <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.78rem", color: "#cbd5e1" }}>
      <input type="checkbox" data-testid={`cp-${id}`} checked={!!f[id]} onChange={() => chk(id)}
        style={{ width: 16, height: 16, accentColor: "#d4af37" }} />{label}
    </label>
  );

  const setPol = (campo, val) => {
    setOverlay((prev) => ({
      ...prev,
      [lado]: { ...(prev[lado] || {}), [campo]: val === "" ? "" : Number(val) },
    }));
  };

  return (
    <div className="module-content" data-testid="concreces-perfecto" style={{ padding: "1.2rem 1.5rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12,
        background: "#0e0e14", border: "1px solid #2a2a44", padding: "10px 14px", marginBottom: 12 }}>
        <div>
          <div style={{ fontSize: "0.62rem", letterSpacing: "0.14em", color: "#d4af37", fontWeight: 800 }}>
            CONCRECES MOTOR V7 · POLÍTICA MADRE REAL
          </div>
          <b data-testid="cp-uf-val" style={{ fontSize: "1.25rem", color: "#FCF6BA" }}>{formatCurrency(uf)}</b>
          <div data-testid="cp-uf-fecha" style={{ fontSize: "0.68rem", color: "#94a3b8" }}>
            UF usada: {fuenteTxt}{meta?.dia_uf ? ` · ${String(meta.dia_uf).slice(0, 10)}` : ""}
          </div>
        </div>
        <button type="button" data-testid="cp-actualizar-uf" onClick={actualizarUF} disabled={ufLoading}
          className="config-btn">{ufLoading ? "Actualizando…" : "Actualizar UF"}</button>
      </div>

      <div style={{ background: "#151b23", border: "1px solid #212a36", padding: 12, marginBottom: 12 }}>
        <div style={{ color: "#79c0ff", fontSize: "0.72rem", letterSpacing: "0.1em", marginBottom: 8 }}>POLITICA_BASE · CON vs SIN</div>
        <table data-testid="cp-tabla-madre" style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th style={th}>Var</th>
              <th style={th}>CON subsidio</th>
              <th style={th}>SIN subsidio</th>
            </tr>
          </thead>
          <tbody>
            {MADRE_FILAS.map(([k, label]) => {
              const con = (base?.con_subsidio || MADRE_DEF.con_subsidio)[k];
              const sin = (base?.sin_subsidio || MADRE_DEF.sin_subsidio)[k];
              const fmt = (v) => (k === "ltv_duro" || k === "pie_min" || k === "div_renta_max" || k === "carga_max"
                ? (v == null ? "—" : (Number(v) <= 1.5 ? `${(Number(v) * 100).toFixed(1)}` : v))
                : (v == null ? "—" : v));
              return (
                <tr key={k}>
                  <td style={{ ...cell, color: "#8b949e" }}>{label}</td>
                  <td style={{ ...cell, color: "#7ee787" }}>{fmt(con)}</td>
                  <td style={cell}>{fmt(sin)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {msg && <div data-testid="cp-msg" style={{ marginBottom: 10, color: "#FCF6BA", fontSize: "0.78rem" }}>{msg}</div>}

      <div className="cp-v5-grid">
        <div className="sim-form">
          <fieldset className="form-fieldset">
            <legend>Clasificación</legend>
            <div className="field-grid-2" style={{ marginBottom: 8 }}>
              <div>
                <label>Tipo de cliente</label>
                <select data-testid="cp-client-type" value={f.client_type}
                  onChange={(e) => set("client_type", e.target.value)}>
                  <option>DEPENDIENTE</option>
                  <option>INDEPENDIENTE</option>
                  <option>MIXTO</option>
                  <option>SIN_EVIDENCIA</option>
                  <option>JUBILADO</option>
                </select>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6, justifyContent: "center" }}>
                {box("sub", "con_subsidio")}
                {box("exento_afp", "exento_afp (FFAA/Carab)")}
                {box("licencia_medica", "licencia_medica")}
              </div>
            </div>
            <div className="field-grid-2" style={{ marginBottom: 8 }}>
              {box("vNueva", "Nueva/Usada")}{box("vCasa", "Casa/Depto")}
              {box("vHab", "Habitacional")}{box("nacOk", "Chilena / Perm. Def.")}
            </div>
            <div className="field-grid-2" style={{ marginBottom: 8 }}>
              <div>
                <label>Fecha entrega *</label>
                <select data-testid="cp-fecha" value={f.fecha_entrega} onChange={(e) => set("fecha_entrega", e.target.value)}>
                  <option value="">—</option>
                  <option>Inmediata</option>
                  <option>Futura</option>
                </select>
              </div>
              <div>
                <label>Ejecutivo interno *</label>
                <select data-testid="cp-ejec" value={f.ejec_interno} onChange={(e) => set("ejec_interno", e.target.value)}>
                  <option value="">—</option>
                  <option>Deisy Salazar</option>
                  <option>Yerile Barrera</option>
                  <option>Gerardo Barrera</option>
                </select>
              </div>
              <div><label>RUT titular (Ivana) *</label>{inp("rut_titular", "12.345.678-9")}</div>
              <div>{box("force_incompleto", "force_incompleto (envío manual)")}</div>
            </div>
            <div style={{ fontSize: "0.7rem", color: "#8b949e", marginBottom: 6 }}>Checklist 412 — marcar docs presentes</div>
            <div className="field-grid-2" style={{ marginBottom: 8 }}>
              {Object.keys(f.docs || {}).map((k) => (
                <label key={k} style={{ fontSize: "0.75rem", color: "#cbd5e1", display: "flex", gap: 6 }}>
                  <input type="checkbox" checked={!!f.docs[k]} data-testid={`cp-doc-${k}`}
                    onChange={() => setF((p) => ({ ...p, docs: { ...p.docs, [k]: !p.docs[k] } }))} />
                  {k}
                </label>
              ))}
            </div>
            <div style={{ fontSize: "0.7rem", color: "#94a3b8", margin: "4px 0 8px" }}>
              6 liquidaciones (PDF via pdf.js) — promedio × 0,85 vs AFP × 0,90
            </div>
            <label className="config-btn" style={{ display: "inline-block", marginBottom: 8, cursor: "pointer" }}>
              Subir liquidaciones PDF
              <input type="file" accept="application/pdf" multiple hidden data-testid="cp-liq-pdf"
                onChange={(e) => { subirLiqs(e.target.files); e.target.value = ""; }} />
            </label>
            <div className="field-grid-3">
              {inp("l1", "Liq 1")}{inp("l2", "Liq 2")}{inp("l3", "Liq 3")}
              {inp("l4", "Liq 4")}{inp("l5", "Liq 5")}{inp("l6", "Liq 6")}
            </div>
            <div className="field-grid-2" style={{ marginTop: 10 }}>
              <div><label>Renta CLP (madre)</label>{inp("renta", "1200000")}</div>
              <div><label>AFP promedio</label>{inp("afp")}</div>
              <div><label>Edad</label>{inp("edad")}</div>
              <div><label>Valor vivienda UF</label>{inp("valor")}</div>
              <div><label>Monto crédito UF</label>{inp("monto")}</div>
              <div><label>Pie %</label>{inp("pie")}</div>
              <div><label>Plazo años</label>{inp("plazo")}</div>
              <div><label>Tasa anual %</label>{inp("tasa")}</div>
              <div><label>Dividendo CLP (vacío = PMT+seguros)</label>{inp("div", "auto")}</div>
              <div><label>Deudas titular</label>{inp("deudas")}</div>
              <div><label>Seg. desgravamen</label>{inp("desg", "aprendido")}</div>
              <div><label>Seg. incendio</label>{inp("inc", "aprendido")}</div>
              <div><label>Haberes no imp.</label>{inp("hab")}</div>
              <div><label>Viáticos</label>{inp("viat")}</div>
              <div><label>Antigüedad meses</label>{inp("antig")}</div>
              <div><label>Continuidad meses</label>{inp("cont")}</div>
              <div>
                <label>Actividad</label>
                <select data-testid="cp-actividad" value={f.actividad} onChange={(e) => set("actividad", e.target.value)}>
                  <option value="dependiente">Dependiente</option>
                  <option value="independiente">Independiente 3a</option>
                  <option value="jubilado">Jubilado</option>
                </select>
              </div>
              <div>
                <label>Contrato</label>
                <select data-testid="cp-contrato" value={f.contrato} onChange={(e) => set("contrato", e.target.value)}>
                  <option value="indefinido">Indefinido</option>
                  <option value="plazo_fijo">Plazo fijo</option>
                  <option value="obra">Obra / faena</option>
                </select>
              </div>
            </div>
            <div style={{ marginTop: 10 }}>
              <label>Complemento</label>
              <select data-testid="cp-tipo" value={f.tipo} onChange={(e) => set("tipo", e.target.value)}>
                <option value="sin">Sin complemento</option>
                <option value="conyuge">Cónyuge CON hijo (familiar)</option>
                <option value="directo">Directo padres/hijos/hnos CF tit 70%</option>
                <option value="tercero">Tercero CF tit 60% + 50% div/renta</option>
              </select>
              <div className="field-grid-2" style={{ marginTop: 8 }}>
                <div><label>Renta codeudor</label>{inp("rentaCod")}</div>
                <div><label>Deudas codeudor</label>{inp("deudasCod")}</div>
              </div>
            </div>
            <div style={{ marginTop: 10, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
              {BLOQUEOS.map((b) => (
                <label key={b} style={{ fontSize: "0.72rem", color: "#fda4af", display: "flex", gap: 6 }}>
                  <input type="checkbox" checked={!!bloqueos[b]}
                    onChange={() => setBloqueos((p) => ({ ...p, [b]: !p[b] }))} />
                  {b}
                </label>
              ))}
            </div>
          </fieldset>
          <button type="button" className="submit-btn" data-testid="cp-ejecutar" onClick={() => run()} disabled={cargando}>
            {cargando ? "Evaluando…" : "EVALUAR POLÍTICA MADRE"}
          </button>
        </div>

        <div>
          <div style={{ background: "#0e0e14", border: "1px solid #2a2a44", marginBottom: 12 }}>
            <div style={{ padding: "8px 12px", color: "#d4af37", fontSize: "0.72rem", letterSpacing: "0.1em",
              borderBottom: "1px solid #2a2a44" }}>
              POLÍTICA · {f.sub ? "CON SUBSIDIO" : "SIN SUBSIDIO"} · BASE vs REAL
            </div>
            <table data-testid="cp-tabla-politica" style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <th style={th}>Campo</th>
                  <th style={th}>Base oficial</th>
                  <th style={th}>Real aprendida</th>
                </tr>
              </thead>
              <tbody>
                {FILAS_POL.map(([k, label]) => {
                  const bv = baseLado[k];
                  const mapaReal = {
                    div_renta_max: realLado.div_max_real,
                    carga_max: realLado.carga_max_real,
                    valor_min_uf: realLado.valor_min_real,
                    valor_max_uf: realLado.valor_max_real,
                    pie_min: realLado.pie_min_real,
                    monto_max_uf: realLado.monto_max_real,
                  };
                  const rv = mapaReal[k];
                  const esPct = k.includes("max") && (k.startsWith("div") || k.startsWith("carga") || k.startsWith("pie") || k.startsWith("financ"));
                  return (
                    <tr key={k}>
                      <td style={{ ...cell, color: "#94a3b8" }}>{label}</td>
                      <td style={cell}>
                        <input data-testid={`cp-pol-${k}`} value={bv == null ? "" : bv}
                          onChange={(e) => setPol(k, e.target.value)}
                          style={{ width: "100%", background: "transparent", border: 0, color: "#FCF6BA",
                            fontFamily: "inherit", fontSize: "0.78rem" }} />
                      </td>
                      <td style={{ ...cell, color: rv != null && bv != null && Number(rv) < Number(bv) ? "#fbbf24" : "#e2e8f0" }}>
                        {rv == null ? "—" : (esPct ? pct(rv) : rv)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <div style={{ padding: 8, textAlign: "right" }}>
              <button type="button" className="config-btn" data-testid="cp-guardar-pol" onClick={guardarOverlay}>
                Guardar overlay
              </button>
            </div>
          </div>

          <div style={{ background: "#0e0e14", border: "1px solid #2a2a44", padding: 12, marginBottom: 12 }}>
            <div style={{ fontSize: "0.72rem", color: "#d4af37", letterSpacing: "0.1em", marginBottom: 8 }}>
              FASE3 COMBINADO 01-06 · dual codeudor · Ivana
            </div>
            <label className="config-btn" style={{ display: "inline-block", cursor: "pointer" }}>
              Subir PDFs para combinado
              <input type="file" accept="application/pdf" multiple hidden data-testid="cp-combinado-pdf"
                onChange={(e) => { subirCombinado(e.target.files); e.target.value = ""; }} />
            </label>
            <div style={{ marginTop: 8, color: "#64748b", fontSize: "0.72rem" }}>
              Prefijos 01_cedula → 02_liq/impuesto → 03_afp/boletas → 04_cmf → 05_codeudor → 99_otros.
              Correo Mesa: aprobaciones@centralmutuos.cl desde gerardo.ext@centralmutuos.cl
            </div>
          </div>

          <div style={{ background: "#0e0e14", border: "1px solid #2a2a44", padding: 12, marginBottom: 12 }}>
            <div style={{ fontSize: "0.72rem", color: "#d4af37", letterSpacing: "0.1em", marginBottom: 8 }}>
              VIGÍA aprobaciones@ · {nCartas} cartas
            </div>
            <label className="config-btn" style={{ display: "inline-block", cursor: "pointer" }}>
              Subir cartas PDF
              <input type="file" accept="application/pdf" multiple hidden data-testid="cp-cartas-pdf"
                onChange={(e) => { subirCartas(e.target.files); e.target.value = ""; }} />
            </label>
            {(alertas || []).map((a, i) => (
              <div key={i} data-testid={`cp-alerta-${i}`}
                style={{ marginTop: 8, color: "#fbbf24", fontSize: "0.78rem", lineHeight: 1.4 }}>{a.txt}</div>
            ))}
            {!(alertas || []).length && (
              <div style={{ marginTop: 8, color: "#64748b", fontSize: "0.75rem" }}>
                Sin cortes empíricos aún. Suba cartas de aprobación/rechazo.
              </div>
            )}
            <div style={{ marginTop: 8 }}>
              <Spark data={evo.map((e) => (e.div_renta || 0) * 100)} color="#8b5cf6" testId="cp-evo" />
            </div>
          </div>
        </div>
      </div>

      <div className="result-card" style={{ marginTop: 12 }}>
        <div style={{ padding: "10px 14px" }}>
          <div style={{ fontSize: "0.68rem", color: "#94a3b8" }}>Liquidaciones</div>
          <Spark data={liqs} />
        </div>
      </div>

      {res && (
        <div className="result-card" data-testid="cp-resultado" style={{ marginTop: 12, borderColor: color }}>
          <div className="result-header" style={{ background: `${color}22` }}>
            <h3 data-testid="cp-estado" style={{ color, margin: 0, letterSpacing: "0.1em" }}>{sema}</h3>
            <div data-testid="cp-kpi" style={{ fontSize: "0.9rem", color: "#e6edf3", marginTop: 8, fontWeight: 700 }}>
              {res.kpi || `LTV ${((res.ltv || 0) * 100).toFixed(2)}% · Div/R ${((res.div_renta || 0) * 100).toFixed(2)}% · Carga ${((res.carga || 0) * 100).toFixed(2)}%`}
            </div>
            <div style={{ fontSize: "0.78rem", color: "#cbd5e1", marginTop: 6 }}>
              UF {formatCurrency(res.uf_usada)} · Renta {formatCurrency(res.renta_total)} ·
              Div {formatCurrency(res.dividendo)}
              {res.seguros_fuente ? ` · seguros ${res.seguros_fuente}` : ""}
            </div>
            {(res.motivos || []).length > 0 && (
              <div data-testid="cp-motivos" style={{ marginTop: 8 }}>
                {(res.motivos || []).map((m, i) => (
                  <div key={i} style={{ color: "#fb7185", fontSize: "0.8rem", fontWeight: 700 }}>{m}</div>
                ))}
              </div>
            )}
          </div>
          <div style={{ padding: "10px 16px 16px" }}>
            {(res.checks || []).map((c, i) => (
              <div key={i} data-testid={`cp-check-${i}`}
                style={{ color: c.ok ? "#10d98e" : "#fb7185", fontSize: "0.82rem", padding: "3px 0" }}>
                {c.ok ? "✓" : "✗"} {c.txt}
                {c.motivo && !c.ok ? <span style={{ color: "#fbbf24" }}> · {c.motivo}</span> : null}
              </div>
            ))}
            {(res.checks_real || []).map((c, i) => (
              <div key={`r${i}`} style={{ color: "#fbbf24", fontSize: "0.82rem", padding: "3px 0" }}>
                ⚠ {c.txt}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
