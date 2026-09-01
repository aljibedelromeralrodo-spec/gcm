import { useState, useRef } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const ORO = "#d4af37";
const S = {
  page: { minHeight: "100vh", background: "#0a0a0a", color: "#fff",
    fontFamily: "'Segoe UI', system-ui, sans-serif", padding: "1rem", maxWidth: 560, margin: "0 auto" },
  titulo: { color: ORO, fontSize: "1.35rem", fontWeight: 800, letterSpacing: "0.06em", margin: "0.4rem 0" },
  sub: { color: "rgba(255,255,255,0.55)", fontSize: "0.8rem", marginBottom: "1rem" },
  label: { color: ORO, fontSize: "0.72rem", fontWeight: 700, letterSpacing: "0.05em",
    textTransform: "uppercase", display: "block", marginBottom: 4 },
  input: { width: "100%", boxSizing: "border-box", background: "#161616", color: "#fff",
    border: `1px solid rgba(212,175,55,0.35)`, padding: "0.85rem", fontSize: "1rem",
    borderRadius: 4, outline: "none", marginBottom: "0.9rem" },
  boton: { width: "100%", background: ORO, color: "#0a0a0a", border: "none", fontWeight: 800,
    fontSize: "1.05rem", padding: "1rem", borderRadius: 4, cursor: "pointer", letterSpacing: "0.05em" },
  botonSec: { background: "transparent", color: ORO, border: `1px solid ${ORO}`, fontWeight: 700,
    fontSize: "0.8rem", padding: "0.7rem 0.5rem", borderRadius: 4, cursor: "pointer", width: "100%" },
  card: { background: "#121212", border: "1px solid rgba(212,175,55,0.25)", borderRadius: 6,
    padding: "1rem", marginBottom: "1rem" },
  fila: { display: "flex", justifyContent: "space-between", padding: "0.4rem 0",
    borderBottom: "1px solid rgba(255,255,255,0.07)", fontSize: "0.85rem" },
};
const CAMPOS = [
  ["renta_titular", "Renta líquida titular ($ CLP)", "numeric"],
  ["renta_codeudor", "Renta líquida codeudor ($ CLP)", "numeric"],
  ["edad_cliente", "Edad titular", "numeric"],
  ["edad_codeudor", "Edad codeudor", "numeric"],
  ["deuda_cmf_total", "Deuda CMF titular ($ CLP)", "numeric"],
  ["deuda_cmf_codeudor", "Deuda CMF codeudor ($ CLP)", "numeric"],
  ["credito_interno_pav", "Créditos consumo / PAV ($ CLP)", "numeric"],
  ["valor_propiedad_uf", "Valor propiedad (UF)", "decimal"],
  ["credito_solicitado_uf", "Crédito solicitado (UF, opcional)", "decimal"],
  ["ahorro_uf", "Ahorro / pie (UF)", "decimal"],
  ["subsidio_uf", "Subsidio (UF)", "decimal"],
];
const DOCS = [
  ["liquidacion", "📄 Liquidación"], ["cedula", "🪪 Cédula"],
  ["afp", "🏦 Cert. AFP"], ["cmf", "📊 Informe CMF"],
];
const fmt = (n, d = 0) => Number(n || 0).toLocaleString("es-CL", { maximumFractionDigits: d });
const pct = (n) => `${(Number(n || 0) * 100).toFixed(1)}%`;

export default function CalculadoraMax() {
  const [clave, setClave] = useState("");
  const [auth, setAuth] = useState(false);
  const [uf, setUf] = useState(0);
  const [f, setF] = useState({ plazo_anos: 25, tasa_pct: "", tasa_manual: false, tipo_deudor: 1, continuidad_laboral: true });
  const [res, setRes] = useState(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState("");
  const fileRefs = useRef({});

  const set = (k, v) => setF(prev => ({ ...prev, [k]: v }));

  const login = async () => {
    setBusy("login"); setMsg("");
    try {
      const r = await axios.post(`${API}/api/calcmax/login`, { clave });
      setUf(r.data.valor_uf); setAuth(true);
    } catch (e) { setMsg(e.response?.data?.detail || "Error de conexión"); }
    setBusy("");
  };

  const subirFoto = async (tipo, file) => {
    if (!file) return;
    setBusy(tipo); setMsg("");
    try {
      const fd = new FormData();
      fd.append("clave", clave); fd.append("tipo", tipo); fd.append("foto", file);
      const r = await axios.post(`${API}/api/calcmax/ocr`, fd, { timeout: 120000 });
      const c = r.data.campos || {};
      setF(prev => ({ ...prev, ...c }));
      const n = Object.keys(c).length;
      setMsg(n ? `✅ ${r.data.tipo_detectado}: ${n} dato(s) extraído(s) — ${Object.keys(c).join(", ")}`
               : `⚠️ Documento leído (${r.data.tipo_detectado}) pero sin datos financieros claros`);
    } catch (e) { setMsg(`🚨 ${e.response?.data?.detail || "Error al procesar la foto"}`); }
    setBusy("");
  };

  const calcular = async () => {
    setBusy("calc"); setMsg(""); setRes(null);
    try {
      const payload = { clave, ...f };
      delete payload.tasa_pct; delete payload.tasa_manual;
      if (f.tasa_manual && Number(f.tasa_pct) > 0) payload.tasa_anual = Number(f.tasa_pct) / 100;
      const r = await axios.post(`${API}/api/calcmax/calcular`, payload);
      setRes(r.data); setUf(r.data.valor_uf);
      setTimeout(() => document.getElementById("resultado-calcmax")?.scrollIntoView({ behavior: "smooth" }), 150);
    } catch (e) { setMsg(`🚨 ${e.response?.data?.detail || "Error al calcular"}`); }
    setBusy("");
  };

  if (!auth) return (
    <div style={S.page}>
      <div style={{ textAlign: "center", marginTop: "18vh" }}>
        <div style={{ ...S.titulo, fontSize: "1.6rem" }}>CENTRAL MUTUOS</div>
        <div style={S.sub}>Calculadora de Crédito Máximo — Ejecutivos</div>
        <input data-testid="calcmax-clave" style={{ ...S.input, textAlign: "center", letterSpacing: "0.3em" }}
          type="password" placeholder="Clave de acceso" value={clave} autoFocus
          onChange={e => setClave(e.target.value)} onKeyDown={e => e.key === "Enter" && login()} />
        <button data-testid="calcmax-entrar" style={S.boton} disabled={!!busy} onClick={login}>
          {busy ? "Verificando…" : "ENTRAR"}
        </button>
        {msg && <div data-testid="calcmax-login-msg" style={{ color: "#e35d6a", marginTop: 12, fontSize: "0.85rem" }}>{msg}</div>}
      </div>
    </div>
  );

  return (
    <div style={S.page}>
      <div style={S.titulo}>💰 CRÉDITO MÁXIMO</div>
      <div style={S.sub}>Algoritmo Espejo · UF del día: <b style={{ color: ORO }}>${fmt(uf, 2)}</b></div>

      <div style={S.card}>
        <span style={S.label}>📸 Capturar documentos con la cámara</span>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 6 }}>
          {DOCS.map(([t, lbl]) => (
            <span key={t}>
              <input ref={el => (fileRefs.current[t] = el)} type="file" accept="image/*,application/pdf"
                capture="environment" style={{ display: "none" }}
                onChange={e => { subirFoto(t, e.target.files[0]); e.target.value = ""; }} />
              <button data-testid={`calcmax-foto-${t}`} style={S.botonSec} disabled={!!busy}
                onClick={() => fileRefs.current[t]?.click()}>
                {busy === t ? "⏳ Leyendo…" : lbl}
              </button>
            </span>
          ))}
        </div>
        <div style={{ fontSize: "0.68rem", opacity: 0.5, marginTop: 8 }}>
          El sistema extrae automáticamente renta, deudas CMF, edad y RUT con OCR + IA y rellena los campos.
        </div>
      </div>

      {msg && <div data-testid="calcmax-msg" style={{ fontSize: "0.8rem", margin: "0 0 0.8rem", color: "#F5E7B8" }}>{msg}</div>}

      <div style={S.card}>
        <span style={S.label}>Datos del cliente {f.rut ? `· RUT ${f.rut}` : ""}</span>
        {CAMPOS.map(([k, lbl, mode]) => (
          <div key={k}>
            <span style={{ ...S.label, color: "rgba(255,255,255,0.6)", textTransform: "none" }}>{lbl}</span>
            <input data-testid={`calcmax-${k}`} style={S.input} inputMode={mode} type="number"
              value={f[k] ?? ""} placeholder="0"
              onChange={e => set(k, e.target.value === "" ? "" : Number(e.target.value))} />
          </div>
        ))}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          <div>
            <span style={{ ...S.label, color: "rgba(255,255,255,0.6)", textTransform: "none" }}>Plazo (años)</span>
            <select data-testid="calcmax-plazo" style={S.input} value={f.plazo_anos}
              onChange={e => set("plazo_anos", Number(e.target.value))}>
              {[10, 15, 20, 25, 30].map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <div>
            <span style={{ ...S.label, color: "rgba(255,255,255,0.6)", textTransform: "none" }}>Tasa anual</span>
            <select data-testid="calcmax-tasa-modo" style={S.input} value={f.tasa_manual ? "manual" : "auto"}
              onChange={e => set("tasa_manual", e.target.value === "manual")}>
              <option value="auto">Automática (subsidio y tramo 2.000 UF)</option>
              <option value="manual">Manual</option>
            </select>
            {f.tasa_manual && (
              <input data-testid="calcmax-tasa" style={S.input} inputMode="decimal" type="number" step="0.01"
                placeholder="% anual" value={f.tasa_pct} onChange={e => set("tasa_pct", e.target.value)} />
            )}
          </div>
        </div>
        <span style={{ ...S.label, color: "rgba(255,255,255,0.6)", textTransform: "none" }}>Tipo de deudor</span>
        <select data-testid="calcmax-tipo-deudor" style={S.input} value={f.tipo_deudor}
          onChange={e => set("tipo_deudor", Number(e.target.value))}>
          <option value={1}>Tipo 1 — Dependiente renta fija</option>
          <option value={2}>Tipo 2 — Dependiente renta variable (−15%)</option>
          <option value={3}>Tipo 3 — Independiente / honorarios (−20%)</option>
        </select>
        {[["con_subsidio", "Cliente CON subsidio habitacional"],
          ["morosidad_dicom", "Morosidad vigente en DICOM"],
          ["protestos_vigentes", "Protestos vigentes"],
          ["continuidad_laboral", "Continuidad laboral"]].map(([k, lbl]) => (
          <label key={k} style={{ display: "flex", alignItems: "center", gap: 10, padding: "0.5rem 0",
            fontSize: "0.9rem", cursor: "pointer" }}>
            <input data-testid={`calcmax-${k}`} type="checkbox" checked={!!f[k]}
              onChange={e => set(k, e.target.checked)} style={{ width: 20, height: 20, accentColor: ORO }} />
            {lbl}
          </label>
        ))}
      </div>

      <button data-testid="calcmax-calcular" style={{ ...S.boton, marginBottom: "1.2rem" }}
        disabled={!!busy} onClick={calcular}>
        {busy === "calc" ? "Calculando…" : "CALCULAR CRÉDITO MÁXIMO"}
      </button>

      {res && (
        <div id="resultado-calcmax" style={{ ...S.card, border: `1.5px solid ${ORO}` }}>
          <div style={{ textAlign: "center", padding: "0.5rem 0 1rem" }}>
            <div style={S.label}>CRÉDITO MÁXIMO POSIBLE</div>
            <div data-testid="calcmax-resultado-uf" style={{ color: ORO, fontSize: "2.6rem", fontWeight: 900 }}>
              UF {fmt(res.credito_maximo_uf, 2)}
            </div>
            <div style={{ fontSize: "0.95rem", opacity: 0.8 }}>≈ ${fmt(res.credito_maximo_uf * res.valor_uf)}</div>
            <div style={{ marginTop: 8, fontSize: "0.85rem",
              color: res.precalificacion_aprobada ? "#10d98e" : "#e35d6a", fontWeight: 700 }}>
              {res.precalificacion_aprobada ? "✅ VIABILIDAD POSITIVA" : "⚠️ SIN VIABILIDAD POR AHORA"}
            </div>
          </div>
          <div style={S.label}>Desglose del cálculo</div>
          {[["UF del día (SII)", `$${fmt(res.valor_uf, 2)}`],
            ["Ingreso considerado (líquido)", `$${fmt((Number(f.renta_titular) || 0) + (Number(f.renta_codeudor) || 0))}`],
            ["Tipo de deudor", res.tipo_deudor_texto],
            ["Deuda CMF + PAV considerada", `$${fmt(res.deuda_cmf_considerada_clp)}`],
            ["Cuota CMF (36 meses al 2% anual) — carga presente", `$${fmt(res.cuota_cmf_36m_clp)}`],
            ["Carga futura (dividendo nuevo crédito)", `$${fmt(res.carga_futura_clp)}`],
            ["Carga financiera TOTAL (presente + futura)", `$${fmt(res.carga_total_clp)}`],
            ["Dividendo tope mensual", `$${fmt(res.dividendo_tope)}`],
            ["Capacidad por renta", `UF ${fmt(res.capacidad_credito_uf, 2)}`],
            ["Dividendo del crédito máximo", `UF ${fmt(res.dividendo_credito_uf, 2)} ≈ $${fmt(res.dividendo_credito_clp)}`],
            ["Dividendo / Renta conjunta", pct(res.div_renta_conjunta)],
            ["Carga financiera conjunta", pct(res.carga_fin_conjunta)],
            ["LTV (crédito/propiedad)", res.valor_propiedad_uf > 0 ? pct(res.ltv) : "sin valor propiedad"],
            ["Edad + plazo", res.edad_plazo],
            ["Valor máximo de compra", `UF ${fmt(res.valor_maximo_compra_uf, 2)}`],
            ["Tasa aplicada", `${(Number(res.tasa_anual || 0) * 100).toFixed(2)}% (${res.tasa_origen || "manual"})`]].map(([k, v], i) => (
            <div key={i} style={S.fila}><span style={{ opacity: 0.65 }}>{k}</span><b>{v}</b></div>
          ))}
          {res.razones_rechazo?.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ ...S.label, color: "#e35d6a" }}>Observaciones de viabilidad</div>
              {res.razones_rechazo.map((r, i) => (
                <div key={i} style={{ fontSize: "0.8rem", color: "#e35d6a", padding: "2px 0" }}>• {r}</div>
              ))}
            </div>
          )}
          {res.credito_solicitado_uf > 0 && (
            <div style={{ marginTop: 10, fontSize: "0.85rem" }}>
              Crédito solicitado UF {fmt(res.credito_solicitado_uf, 2)}: {res.credito_viable
                ? <b style={{ color: "#10d98e" }}>POSIBLE VIABILIDAD</b> : <b style={{ color: "#e35d6a" }}>SIN VIABILIDAD</b>}
              {res.pie_requerido_uf > 0 && ` · Pie requerido: UF ${fmt(res.pie_requerido_uf, 2)}`}
            </div>
          )}
          <div data-testid="calcmax-nota-legal" style={{ marginTop: 14, padding: "0.7rem",
            background: "rgba(212,175,55,0.07)", border: "1px solid rgba(212,175,55,0.25)",
            fontSize: "0.68rem", lineHeight: 1.5, color: "rgba(255,255,255,0.65)" }}>
            <b style={{ color: ORO }}>NOTA LEGAL:</b> Esta información es solo referencial y NO constituye
            ningún tipo de aprobación ni preaprobación. La aprobación debe realizarse en forma directa y
            ser enviada con la documentación correspondiente, según la normativa vigente.
          </div>
        </div>
      )}
      <div style={{ textAlign: "center", fontSize: "0.65rem", opacity: 0.35, padding: "1rem 0 2rem" }}>
        Central Mutuos · Algoritmo Espejo · Uso exclusivo de ejecutivos
      </div>
    </div>
  );
}
