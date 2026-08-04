import { useState, useEffect } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

export default function AlertasPanel() {
  const [alertas, setAlertas] = useState([]);
  const [dias, setDias] = useState(7);
  const [loading, setLoading] = useState(true);

  const fetchAlertas = () => {
    setLoading(true);
    axios.get(`${API_URL}/api/alertas/seguimiento?dias=${dias}`).then(r => {
      setAlertas(r.data.alertas || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => { fetchAlertas(); }, [dias]);

  if (loading && alertas.length === 0) return null;

  return (
    <div data-testid="alertas-panel" style={{ marginBottom: "1.5rem", padding: "1rem", borderRadius: "2px", background: alertas.length > 0 ? "rgba(245,158,11,0.08)" : "var(--bg-card)", border: `1px solid ${alertas.length > 0 ? "rgba(245,158,11,0.3)" : "var(--border)"}` }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.75rem" }}>
        <div style={{ fontWeight: 700, color: alertas.length > 0 ? "#f59e0b" : "var(--text-primary)", fontSize: "0.9rem" }}>
          <i className={`fa ${alertas.length > 0 ? "fa-exclamation-triangle" : "fa-check-circle"}`} style={{ marginRight: "0.4rem" }}></i>
          {alertas.length > 0 ? `${alertas.length} caso${alertas.length > 1 ? "s" : ""} sin movimiento` : "Sin alertas pendientes"}
        </div>
        <select data-testid="alertas-dias-select" value={dias} onChange={e => setDias(parseInt(e.target.value))}
          style={{ padding: "0.3rem 0.6rem", borderRadius: "2px", border: "1px solid var(--border)", background: "var(--bg-hover)", color: "var(--text-primary)", fontSize: "0.8rem" }}>
          <option value={3}>3 dias</option>
          <option value={5}>5 dias</option>
          <option value={7}>7 dias</option>
          <option value={14}>14 dias</option>
          <option value={30}>30 dias</option>
        </select>
      </div>

      {alertas.length > 0 && (
        <div style={{ maxHeight: "200px", overflowY: "auto" }}>
          {alertas.map((a, i) => {
            const diasSin = Math.floor((Date.now() - new Date(a.created_at).getTime()) / 86400000);
            return (
              <div key={i} data-testid={`alerta-row-${i}`} style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.5rem 0", borderBottom: i < alertas.length - 1 ? "1px solid var(--border)" : "none" }}>
                <div style={{ width: "32px", height: "32px", borderRadius: "2px", background: diasSin > 14 ? "rgba(239,68,68,0.15)" : "rgba(245,158,11,0.15)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                  <span style={{ fontSize: "0.75rem", fontWeight: 700, color: diasSin > 14 ? "#ef4444" : "#f59e0b" }}>{diasSin}d</span>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: "0.82rem", fontWeight: 600, color: "var(--text-primary)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{a.cliente_display || "-"}</div>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>{a.proyecto || "Sin proyecto"} - {a.ejecutivo_cm || "Sin ejecutivo"}</div>
                </div>
                <span style={{ padding: "2px 8px", borderRadius: "2px", fontSize: "0.7rem", fontWeight: 600, background: "rgba(99,102,241,0.12)", color: "#6366f1", whiteSpace: "nowrap" }}>{a.estado || "en proceso"}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
