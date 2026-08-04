import { useState, useEffect } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

export default function IntelligencePanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [calibrating, setCalibrating] = useState(false);
  const [calibResult, setCalibResult] = useState(null);

  useEffect(() => {
    axios.get(`${API_URL}/api/central/intelligence-panel`)
      .then(r => { setData(r.data); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const runCalibration = async () => {
    setCalibrating(true);
    setCalibResult(null);
    try {
      const r = await axios.post(`${API_URL}/api/central/calibrate`);
      setCalibResult(r.data);
      // Refresh panel
      const refreshed = await axios.get(`${API_URL}/api/central/intelligence-panel`);
      setData(refreshed.data);
    } catch {
      setCalibResult({ error: true });
    }
    setCalibrating(false);
  };

  if (loading) return (
    <div style={{ textAlign: "center", padding: "2rem" }}>
      <i className="fa fa-spinner fa-spin" style={{ fontSize: "1.5rem", color: "var(--gold)" }}></i>
      <p style={{ color: "var(--text-secondary)", marginTop: "0.5rem", fontSize: "0.85rem" }}>Cargando inteligencia...</p>
    </div>
  );

  if (!data) return null;

  const { tendencias, calibracion, conocimiento, aprendizaje_reciente } = data;
  const tasaColor = tendencias.tasa_aprobacion >= 70 ? "#10b981" : tendencias.tasa_aprobacion >= 50 ? "#f59e0b" : "#ef4444";
  const precisionColor = calibracion.precision_ia >= 80 ? "#10b981" : calibracion.precision_ia >= 60 ? "#f59e0b" : calibracion.total === 0 ? "var(--text-muted)" : "#ef4444";

  return (
    <div data-testid="intelligence-panel" style={{ marginTop: "1.5rem" }}>
      <div className="dash-section-title">
        <i className="fa fa-lightbulb-o"></i> Inteligencia Central
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "0.75rem", marginBottom: "1rem" }}>
        {/* Gauge: Tasa Aprobacion */}
        <div className="dash-card" style={{ textAlign: "center" }} data-testid="gauge-approval-rate">
          <div style={{ position: "relative", width: "90px", height: "50px", margin: "0 auto 0.4rem", overflow: "hidden" }}>
            <svg viewBox="0 0 100 50" style={{ width: "100%" }}>
              <path d="M5 50 A45 45 0 0 1 95 50" fill="none" stroke="var(--border)" strokeWidth="8" strokeLinecap="round" />
              <path d="M5 50 A45 45 0 0 1 95 50" fill="none" stroke={tasaColor} strokeWidth="8" strokeLinecap="round"
                strokeDasharray={`${tendencias.tasa_aprobacion * 1.41} 141`} />
            </svg>
            <div style={{ position: "absolute", bottom: "0", width: "100%", textAlign: "center", fontSize: "1.1rem", fontWeight: 700, color: tasaColor }}>
              {tendencias.tasa_aprobacion}%
            </div>
          </div>
          <div className="dash-card-label" style={{ fontSize: "0.75rem" }}>Tasa Aprobacion</div>
          <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>{tendencias.aprobadas}/{tendencias.total_simulaciones} sim.</div>
        </div>

        {/* Gauge: Precision IA */}
        <div className="dash-card" style={{ textAlign: "center" }} data-testid="gauge-ai-precision">
          <div style={{ position: "relative", width: "90px", height: "50px", margin: "0 auto 0.4rem", overflow: "hidden" }}>
            <svg viewBox="0 0 100 50" style={{ width: "100%" }}>
              <path d="M5 50 A45 45 0 0 1 95 50" fill="none" stroke="var(--border)" strokeWidth="8" strokeLinecap="round" />
              <path d="M5 50 A45 45 0 0 1 95 50" fill="none" stroke={precisionColor} strokeWidth="8" strokeLinecap="round"
                strokeDasharray={`${(calibracion.total > 0 ? calibracion.precision_ia : 0) * 1.41} 141`} />
            </svg>
            <div style={{ position: "absolute", bottom: "0", width: "100%", textAlign: "center", fontSize: "1.1rem", fontWeight: 700, color: precisionColor }}>
              {calibracion.total > 0 ? `${calibracion.precision_ia}%` : "--"}
            </div>
          </div>
          <div className="dash-card-label" style={{ fontSize: "0.75rem" }}>Precision IA</div>
          <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>{calibracion.aciertos}A / {calibracion.desaciertos}E de {calibracion.total}</div>
        </div>

        {/* Stats: Conocimiento */}
        <div className="dash-card" style={{ textAlign: "center" }} data-testid="stat-knowledge">
          <i className="fa fa-database dash-card-icon" style={{ fontSize: "1.2rem" }}></i>
          <div className="dash-card-value" style={{ fontSize: "1.3rem" }}>{conocimiento.creditos}</div>
          <div className="dash-card-label" style={{ fontSize: "0.75rem" }}>Patrones Credito</div>
          <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>{conocimiento.general} datos + {conocimiento.calibraciones} calib.</div>
        </div>

        {/* Stats: Capacity */}
        <div className="dash-card" style={{ textAlign: "center" }} data-testid="stat-capacity">
          <i className="fa fa-line-chart dash-card-icon" style={{ fontSize: "1.2rem" }}></i>
          <div className="dash-card-value" style={{ fontSize: "1.3rem" }}>{tendencias.capacidad_promedio_uf} UF</div>
          <div className="dash-card-label" style={{ fontSize: "0.75rem" }}>Cap. Promedio</div>
          <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>Renta prom: ${(tendencias.renta_promedio || 0).toLocaleString("es-CL")}</div>
        </div>
      </div>

      {/* Distribution bar */}
      {tendencias.distribucion_uf && (
        <div data-testid="distribution-chart" style={{ background: "var(--bg-card)", borderRadius: "0px", padding: "0.75rem 1rem", marginBottom: "0.75rem", border: "1px solid var(--border)" }}>
          <div style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-primary)", marginBottom: "0.5rem" }}>
            Distribucion por Monto (UF)
          </div>
          <div style={{ display: "flex", gap: "3px", height: "24px", borderRadius: "0px", overflow: "hidden" }}>
            {Object.entries(tendencias.distribucion_uf).map(([range, count]) => {
              const total = Object.values(tendencias.distribucion_uf).reduce((a, b) => a + b, 0);
              const pct = total > 0 ? (count / total * 100) : 0;
              const colors = { "0-1000": "#6366f1", "1000-2000": "#8b5cf6", "2000-3000": "#a78bfa", "3000-5000": "#c4b5fd", "5000+": "#ddd6fe" };
              return pct > 0 ? (
                <div key={range} title={`${range} UF: ${count} (${pct.toFixed(0)}%)`}
                  style={{ flex: pct, background: colors[range] || "#94a3b8", minWidth: pct > 3 ? "auto" : "0", transition: "flex 0.5s" }}
                />
              ) : null;
            })}
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: "0.3rem", fontSize: "0.65rem", color: "var(--text-muted)" }}>
            {Object.entries(tendencias.distribucion_uf).map(([range, count]) => (
              <span key={range}>{range}: {count}</span>
            ))}
          </div>
        </div>
      )}

      {/* Calibration button + Recent learning */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
        <div style={{ background: "var(--bg-card)", borderRadius: "0px", padding: "0.75rem 1rem", border: "1px solid var(--border)" }}>
          <div style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-primary)", marginBottom: "0.5rem" }}>
            <i className="fa fa-refresh"></i> Calibracion IA
          </div>
          <button data-testid="btn-calibrate" onClick={runCalibration} disabled={calibrating}
            style={{
              width: "100%", padding: "0.5rem", borderRadius: "0px", border: "1px solid var(--border-gold)",
              background: calibrating ? "var(--bg-hover)" : "linear-gradient(135deg, rgba(212,175,55,0.1), rgba(212,175,55,0.05))",
              color: "var(--gold)", fontWeight: 600, fontSize: "0.8rem", cursor: calibrating ? "wait" : "pointer",
            }}>
            <i className={`fa fa-${calibrating ? 'spinner fa-spin' : 'cogs'}`}></i>
            {calibrating ? " Calibrando..." : " Calibrar con Correos Reales"}
          </button>
          {calibResult && !calibResult.error && (
            <div data-testid="calibration-result" style={{ marginTop: "0.4rem", fontSize: "0.72rem", color: "var(--text-secondary)" }}>
              {calibResult.calibrations > 0
                ? `${calibResult.calibrations} correos procesados`
                : "Sin correos nuevos para calibrar"}
            </div>
          )}
        </div>

        <div style={{ background: "var(--bg-card)", borderRadius: "0px", padding: "0.75rem 1rem", border: "1px solid var(--border)" }}>
          <div style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-primary)", marginBottom: "0.5rem" }}>
            <i className="fa fa-graduation-cap"></i> Aprendizaje Reciente
          </div>
          {aprendizaje_reciente?.length > 0 ? aprendizaje_reciente.slice(0, 3).map((item, i) => (
            <div key={i} data-testid={`learning-item-${i}`} style={{ fontSize: "0.7rem", color: "var(--text-secondary)", marginBottom: "0.25rem", lineHeight: 1.3 }}>
              <span style={{
                display: "inline-block", padding: "1px 5px", borderRadius: "0px", fontSize: "0.6rem", fontWeight: 600, marginRight: "4px",
                background: item.tipo === "aprobacion" ? "rgba(16,185,129,0.15)" : item.tipo === "rechazo" ? "rgba(239,68,68,0.15)" : "rgba(99,102,241,0.15)",
                color: item.tipo === "aprobacion" ? "#10b981" : item.tipo === "rechazo" ? "#ef4444" : "#6366f1",
              }}>
                {item.tipo}
              </span>
              {(item.contenido || "").slice(0, 80)}
            </div>
          )) : (
            <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>Sin aprendizajes recientes</div>
          )}
        </div>
      </div>
    </div>
  );
}
