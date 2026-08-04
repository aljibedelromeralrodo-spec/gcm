import { useState, useEffect } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

const SEVERITY_COLORS = {
  alta: { bg: "rgba(225,112,85,0.1)", border: "rgba(225,112,85,0.3)", text: "#e17055", icon: "fa-exclamation-circle" },
  media: { bg: "rgba(243,156,18,0.1)", border: "rgba(243,156,18,0.3)", text: "#f39c12", icon: "fa-exclamation-triangle" },
  baja: { bg: "rgba(0,184,148,0.08)", border: "rgba(0,184,148,0.2)", text: "#00b894", icon: "fa-info-circle" },
};

const TIPO_LABELS = {
  tendencia_aprobacion: "Tendencia de Aprobacion",
  patron_rechazo: "Patron de Rechazo",
  tendencia_score: "Tendencia de Score",
  cambio_tasa: "Cambio de Tasa",
  perfil_baja_aprobacion: "Perfil con Baja Aprobacion",
  perfil_alta_aprobacion: "Segmento Fuerte",
  modo_baja_viabilidad: "Modo con Baja Viabilidad",
  ltv_alto_promedio: "LTV Promedio Alto",
};

export default function ProactiveAlertsPanel() {
  const [alertas, setAlertas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchAlertas = () => {
    setLoading(true);
    axios.get(`${API_URL}/api/admin/alertas`).then(r => {
      setAlertas(r.data.alertas || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => { fetchAlertas(); }, []);

  const refresh = async () => {
    setRefreshing(true);
    try {
      await axios.post(`${API_URL}/api/admin/alertas/refresh`);
      fetchAlertas();
    } catch {}
    setRefreshing(false);
  };

  if (loading && alertas.length === 0) return null;

  return (
    <div data-testid="proactive-alerts-panel" style={{ marginBottom: "1.5rem" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
        <div style={{ fontWeight: 700, color: alertas.length > 0 ? "#f39c12" : "var(--text-secondary)", fontSize: "0.9rem" }}>
          <i className={`fa ${alertas.length > 0 ? "fa-bolt" : "fa-shield"}`} style={{ marginRight: "0.4rem" }}></i>
          Alertas Inteligentes {alertas.length > 0 ? `(${alertas.length})` : ""}
        </div>
        <button data-testid="refresh-alerts-btn" onClick={refresh} disabled={refreshing}
          style={{ padding: "0.3rem 0.8rem", borderRadius: "0px", border: "1px solid var(--border)", background: "var(--bg-hover)", color: "var(--text-primary)", fontSize: "0.75rem", cursor: "pointer" }}>
          <i className={`fa ${refreshing ? "fa-spinner fa-spin" : "fa-refresh"}`} style={{ marginRight: "0.3rem" }}></i>
          {refreshing ? "Analizando..." : "Analizar"}
        </button>
      </div>

      {alertas.length === 0 ? (
        <div style={{ padding: "0.75rem", borderRadius: "0px", background: "rgba(0,184,148,0.06)", border: "1px solid rgba(0,184,148,0.15)", fontSize: "0.78rem", color: "var(--text-secondary)" }}>
          <i className="fa fa-check-circle" style={{ marginRight: "0.3rem", color: "#00b894" }}></i>
          Sin alertas. Los patrones estan estables.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
          {alertas.slice(0, 8).map((a, i) => {
            const sev = SEVERITY_COLORS[a.severidad] || SEVERITY_COLORS.baja;
            return (
              <div key={i} data-testid={`alert-${i}`} style={{ padding: "0.6rem 0.8rem", borderRadius: "0px", background: sev.bg, border: `1px solid ${sev.border}`, fontSize: "0.78rem" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.15rem" }}>
                  <i className={`fa ${sev.icon}`} style={{ color: sev.text, fontSize: "0.8rem" }}></i>
                  <span style={{ fontWeight: 700, color: sev.text, fontSize: "0.7rem", textTransform: "uppercase" }}>
                    {TIPO_LABELS[a.tipo] || a.tipo}
                  </span>
                </div>
                <div style={{ color: "var(--text-primary)" }}>{a.mensaje}</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
