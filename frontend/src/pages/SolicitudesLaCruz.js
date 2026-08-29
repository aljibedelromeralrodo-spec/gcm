import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const card = { background: "rgba(20,20,24,0.85)", border: "1px solid rgba(212,175,55,0.25)", padding: "1.2rem 1.4rem", marginBottom: "1.2rem" };
const fmt = n => (n || n === 0) ? Number(n).toLocaleString("es-CL") : "—";
const SEM = { ALTA: { bg: "rgba(16,217,142,0.15)", c: "#10d98e", t: "ALTA" },
              MEDIA: { bg: "rgba(250,204,21,0.15)", c: "#facc15", t: "MEDIA" },
              BAJA: { bg: "rgba(225,29,72,0.15)", c: "#fb7185", t: "BAJA" } };

const Chip = ({ color, bg, children }) => (
  <span style={{ background: bg, color, padding: "0.15rem 0.55rem", fontSize: "0.72rem", fontWeight: 700, borderRadius: 0, marginRight: "0.35rem", display: "inline-block", marginBottom: "0.25rem" }}>{children}</span>
);

const FilaDetalle = ({ s }) => {
  const a = s.analisis || {};
  return (
    <div data-testid={`lacruz-detalle-${s.rut}`} style={{ padding: "0.9rem 1.2rem", background: "rgba(0,0,0,0.35)", borderTop: "1px dashed rgba(212,175,55,0.25)", fontSize: "0.82rem", lineHeight: 1.8 }}>
      {s.codeudor?.nombre && <div><b style={{ color: "var(--gold)" }}>Codeudor:</b> {s.codeudor.nombre} · {s.codeudor.rut}</div>}
      <div><b style={{ color: "var(--gold)" }}>Rentas líquidas prom.:</b> titular ${fmt(a.renta_titular_clp)}{a.renta_codeudor_clp > 0 && <> · codeudor ${fmt(a.renta_codeudor_clp)}</>} · total ${fmt(a.renta_total_clp)} — <b>Deuda CMF:</b> ${fmt(a.deuda_cmf_clp)}</div>
      <div><b style={{ color: "var(--gold)" }}>Ratios (tasa {a.tasa_pct?.toFixed(2)}%, {a.plazo_anos} años):</b> dividendo est. ${fmt(a.dividendo_estimado_clp)} · div/renta {a.div_renta_pct ?? "—"}% (máx 40%) · carga {a.carga_financiera_pct ?? "—"}% (máx 55%) · LTV {a.ltv_pct ?? "—"}% (máx 80%)</div>
      {(a.razones || []).length > 0 && <div style={{ color: "#fb7185" }}><b>⛔ Ratios:</b> {a.razones.join(" · ")}</div>}
      {(a.faltantes || []).length > 0 && <div><b style={{ color: "#facc15" }}>📄 Faltantes:</b> {a.faltantes.join(" · ")}</div>}
      {(a.vencidos || []).length > 0 && <div><b style={{ color: "#fb7185" }}>⏰ Vencidos / ilegibles:</b> {a.vencidos.join(" · ")}</div>}
      {s.observaciones_ia && <div style={{ opacity: 0.7 }}><b>IA:</b> {s.observaciones_ia}</div>}
    </div>
  );
};

export default function SolicitudesLaCruz() {
  const [data, setData] = useState([]);
  const [abierto, setAbierto] = useState(null);
  const [msg, setMsg] = useState("");
  const [proc, setProc] = useState(false);

  const cargar = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/lacruz/solicitudes`);
      setData(r.data.solicitudes || []);
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
  }, []);
  useEffect(() => { cargar(); }, [cargar]);

  const reprocesar = async () => {
    setProc(true); setMsg("");
    try {
      const r = await axios.post(`${API}/api/lacruz/procesar`);
      setMsg(`✅ ${r.data.casos} caso(s) reprocesados desde ${r.data.correos_leidos} correo(s)`);
      cargar();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setProc(false);
  };

  return (
    <div data-testid="lacruz-module" style={{ padding: "1.5rem", color: "var(--white)", maxWidth: "1180px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <div>
          <h2 style={{ margin: 0, color: "var(--gold)", fontSize: "1.15rem" }}><i className="fa fa-building-o" style={{ marginRight: "0.5rem" }} />Solicitudes La Cruz Inmobiliaria</h2>
          <p style={{ margin: "0.3rem 0 0", fontSize: "0.78rem", opacity: 0.65 }}>Casilla daniela.rodriguez@lacruzinmobiliaria.cl · Vigencia CMF/AFP máx. 15 días · Liquidaciones exigidas: febrero a julio 2026</p>
        </div>
        <button data-testid="lacruz-reprocesar" onClick={reprocesar} disabled={proc}
          style={{ background: "transparent", border: "1px solid rgba(212,175,55,0.5)", color: "var(--gold)", padding: "0.5rem 1.1rem", fontWeight: 700, cursor: "pointer", borderRadius: 0 }}>
          <i className={`fa ${proc ? "fa-spinner fa-spin" : "fa-refresh"}`} /> {proc ? "Procesando…" : "Reprocesar correos"}
        </button>
      </div>
      {msg && <div data-testid="lacruz-msg" style={{ padding: "0.6rem 1rem", marginBottom: "1rem", background: msg.startsWith("✅") ? "rgba(16,217,142,0.15)" : "rgba(225,29,72,0.15)", color: msg.startsWith("✅") ? "#10d98e" : "#fb7185", fontWeight: 600 }}>{msg}</div>}

      <div style={card}>
        <table data-testid="lacruz-tabla" style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.84rem" }}>
          <thead>
            <tr style={{ color: "var(--gold)", textAlign: "left", borderBottom: "1px solid rgba(212,175,55,0.35)" }}>
              {["#", "Cliente", "RUT", "Teléfono", "Proyecto", "Crédito solicitado", "Máx. crédito posible", "Posibilidad", "Documentos", ""].map(h =>
                <th key={h} style={{ padding: "0.5rem 0.6rem", fontWeight: 700, fontSize: "0.75rem", letterSpacing: "0.5px" }}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {data.map((s, i) => {
              const a = s.analisis || {};
              const sem = SEM[a.semaforo] || SEM.MEDIA;
              const nFalt = (a.faltantes || []).length, nVenc = (a.vencidos || []).length;
              return [
                <tr key={s.rut} data-testid={`lacruz-fila-${i}`} onClick={() => setAbierto(abierto === s.rut ? null : s.rut)}
                    style={{ borderBottom: "1px solid rgba(255,255,255,0.06)", cursor: "pointer" }}>
                  <td style={{ padding: "0.55rem 0.6rem", fontWeight: 800, color: "var(--gold)" }}>{s.prioridad}</td>
                  <td style={{ padding: "0.55rem 0.6rem", fontWeight: 700 }}>{s.nombre}{s.codeudor?.nombre && <span style={{ opacity: 0.55, fontWeight: 400 }}> + codeudor</span>}</td>
                  <td style={{ padding: "0.55rem 0.6rem" }}>{s.rut}</td>
                  <td data-testid={`lacruz-tel-${i}`} style={{ padding: "0.55rem 0.6rem", whiteSpace: "nowrap" }}>{s.telefono || "—"}</td>
                  <td style={{ padding: "0.55rem 0.6rem" }}>{s.proyecto}</td>
                  <td data-testid={`lacruz-monto-${i}`} style={{ padding: "0.55rem 0.6rem", fontWeight: 700 }}>UF {fmt(s.monto_credito_uf)}</td>
                  <td style={{ padding: "0.55rem 0.6rem", color: (a.max_credito_posible_uf || 0) >= (s.monto_credito_uf || 0) ? "#10d98e" : "#fb7185", fontWeight: 700 }}>UF {fmt(a.max_credito_posible_uf)}</td>
                  <td style={{ padding: "0.55rem 0.6rem" }}><Chip bg={sem.bg} color={sem.c}>{sem.t}</Chip></td>
                  <td style={{ padding: "0.55rem 0.6rem" }}>
                    {nFalt === 0 && nVenc === 0 ? <Chip bg="rgba(16,217,142,0.15)" color="#10d98e">COMPLETOS</Chip> : <>
                      {nFalt > 0 && <Chip bg="rgba(250,204,21,0.15)" color="#facc15">{nFalt} faltante(s)</Chip>}
                      {nVenc > 0 && <Chip bg="rgba(225,29,72,0.15)" color="#fb7185">{nVenc} vencido(s)</Chip>}
                    </>}
                  </td>
                  <td style={{ padding: "0.55rem 0.6rem", color: "var(--gold)" }}><i className={`fa fa-chevron-${abierto === s.rut ? "up" : "down"}`} /></td>
                </tr>,
                abierto === s.rut && <tr key={s.rut + "_d"}><td colSpan={10} style={{ padding: 0 }}><FilaDetalle s={s} /></td></tr>,
              ];
            })}
            {data.length === 0 && <tr><td colSpan={10} style={{ padding: "1.2rem", opacity: 0.6 }}>Sin solicitudes procesadas — usa «Reprocesar correos»</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
