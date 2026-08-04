import { useState, useEffect } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

const GEMAS = [
  { lbl: "0–25% · Riesgo Alto", grad: "linear-gradient(180deg, #fb7185, #e11d48 50%, #7f1d1d)", glow: "rgba(225,29,72,0.5)" },
  { lbl: "25–50% · En Ajuste", grad: "linear-gradient(180deg, #fcd34d, #d97706 50%, #78350f)", glow: "rgba(217,119,6,0.5)" },
  { lbl: "50–75% · Encaminado", grad: "linear-gradient(180deg, #93b4f5, #0f52ba 50%, #0a3d91)", glow: "rgba(15,82,186,0.5)" },
  { lbl: "75–100% · Listo p/ Mesa", grad: "linear-gradient(180deg, #6ee7c7, #10d98e 50%, #065f46)", glow: "rgba(16,217,142,0.55)" },
];

export const GraficosRiesgo = () => {
  const [datos, setDatos] = useState(null);
  useEffect(() => {
    axios.get(`${API_URL}/api/clientes/folders`).then(r => {
      const fs = (r.data.folders || []).filter(f => f.prob_aprobacion && f.prob_aprobacion.porcentaje != null);
      if (!fs.length) return;
      const buckets = [0, 0, 0, 0];
      fs.forEach(f => { const p = f.prob_aprobacion.porcentaje; buckets[p >= 75 ? 3 : p >= 50 ? 2 : p >= 25 ? 1 : 0] += 1; });
      const prom = Math.round(fs.reduce((a, f) => a + f.prob_aprobacion.porcentaje, 0) / fs.length);
      const top = [...fs].sort((a, b) => b.prob_aprobacion.porcentaje - a.prob_aprobacion.porcentaje).slice(0, 5);
      setDatos({ buckets, prom, total: fs.length, top });
    }).catch((e) => console.error(e));
  }, []);
  if (!datos) return null;
  const max = Math.max(...datos.buckets, 1);
  return (
    <div data-testid="graficos-riesgo" style={{
      border: "1px solid transparent", borderRadius: 0, padding: "1.2rem 1.4rem", margin: "1.3rem 0",
      backgroundImage: "linear-gradient(115deg, rgba(255,255,255,0.09) 0%, rgba(255,255,255,0.02) 18%, transparent 32%), linear-gradient(160deg, rgba(30,30,30,0.95), rgba(10,10,10,0.98)), linear-gradient(135deg, #BF953F, #FCF6BA, #B38728, #FBF5B7, #AA771C)",
      backgroundOrigin: "border-box", backgroundClip: "padding-box, padding-box, border-box",
      boxShadow: "0 35px 70px -20px rgba(0,0,0,0.95), 0 0 38px -16px rgba(191,149,63,0.45)",
    }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap", marginBottom: "1rem" }}>
        <span style={{ fontSize: "0.7rem", letterSpacing: "0.16em", textTransform: "uppercase", color: "#94a3b8", fontWeight: 700 }}>
          <i className="fa fa-area-chart" style={{ marginRight: 7 }} />Radar de Riesgo de la Cartera
        </span>
        <span style={{ marginLeft: "auto", fontFamily: "'JetBrains Mono', monospace", color: "var(--gold)", fontSize: "1.1rem", fontWeight: 700, textShadow: "0 0 12px rgba(212,175,55,0.45)" }}>
          {datos.prom}% promedio · {datos.total} carpetas
        </span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.6rem", alignItems: "end" }}>
        <div style={{ display: "flex", gap: "1rem", alignItems: "flex-end", height: 150 }}>
          {datos.buckets.map((n, i) => (
            <div key={i} data-testid={`riesgo-barra-${i}`} style={{ flex: 1, textAlign: "center" }}>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: "#f8fafc", fontSize: "0.95rem", marginBottom: 4 }}>{n}</div>
              <div style={{
                height: Math.max(8, 105 * n / max), background: GEMAS[i].grad,
                boxShadow: `0 14px 34px -10px ${GEMAS[i].glow}, inset 0 1px 0 rgba(255,255,255,0.35)`,
                transition: "height 0.8s cubic-bezier(0.4,0,0.2,1)",
              }} />
              <div style={{ fontSize: "0.6rem", color: "#94a3b8", marginTop: 6, letterSpacing: "0.04em", textTransform: "uppercase" }}>{GEMAS[i].lbl}</div>
            </div>
          ))}
        </div>
        <div>
          {datos.top.map((f, i) => {
            const p = f.prob_aprobacion.porcentaje;
            const g = GEMAS[p >= 75 ? 3 : p >= 50 ? 2 : p >= 25 ? 1 : 0];
            return (
              <div key={i} data-testid={`riesgo-top-${i}`} style={{ marginBottom: 9 }}>
                <div style={{ display: "flex", fontSize: "0.72rem", marginBottom: 3 }}>
                  <span style={{ color: "#e2e8f0", fontWeight: 600 }}>{f.nombre}</span>
                  <span style={{ marginLeft: "auto", fontFamily: "'JetBrains Mono', monospace", color: "var(--gold)" }}>{p}%</span>
                </div>
                <div style={{ height: 7, background: "rgba(255,255,255,0.06)" }}>
                  <div style={{ height: "100%", width: `${p}%`, background: g.grad.replace("180deg", "90deg"), boxShadow: `0 0 14px ${g.glow}` }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default GraficosRiesgo;
