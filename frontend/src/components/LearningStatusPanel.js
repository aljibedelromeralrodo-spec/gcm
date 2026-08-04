import { useState, useEffect } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

const SOURCE_LABELS = {
  mesa_outcome_patterns: { label: "Resultados de Mesa (aprobaciones@centralmutuos.cl)", icon: "fa-envelope" },
  simulation_patterns: { label: "Simulaciones PREDIC", icon: "fa-chart-bar" },
  admin_chat_insights: { label: "Conversaciones Admin", icon: "fa-comments" },
};

export default function LearningStatusPanel() {
  const [status, setStatus] = useState(null);
  const [emailStats, setEmailStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [training, setTraining] = useState(false);

  const fetchStatus = () => {
    setLoading(true);
    Promise.all([
      axios.get(`${API_URL}/api/admin/learning/status`),
      axios.get(`${API_URL}/api/admin/learning/email-stats`).catch(() => ({ data: null })),
    ]).then(([statusRes, emailRes]) => {
      setStatus(statusRes.data);
      setEmailStats(emailRes.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => { fetchStatus(); }, []);

  const triggerLearning = async () => {
    setTraining(true);
    try {
      await axios.post(`${API_URL}/api/admin/learning/trigger`);
      fetchStatus();
    } catch {}
    setTraining(false);
  };

  if (loading && !status) return null;

  const sources = status?.data_sources || {};
  const patterns = status || {};
  const patternKeys = Object.keys(patterns).filter(k => k !== "data_sources" && k !== "error");

  return (
    <div data-testid="learning-status-panel" style={{ marginBottom: "1.5rem" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.5rem" }}>
        <div style={{ fontWeight: 700, color: "var(--accent-primary)", fontSize: "0.9rem" }}>
          <i className="fa fa-brain" style={{ marginRight: "0.4rem" }}></i>
          Aprendizaje Intuitivo IA
          <span style={{ fontSize: "0.7rem", fontWeight: 400, color: "var(--text-secondary)", marginLeft: "0.5rem" }}>
            Fuente: aprobaciones@centralmutuos.cl
          </span>
        </div>
        <button data-testid="trigger-learning-btn" onClick={triggerLearning} disabled={training}
          style={{ padding: "0.3rem 0.8rem", borderRadius: "4px", border: "1px solid var(--border)", background: "var(--bg-hover)", color: "var(--text-primary)", fontSize: "0.75rem", cursor: "pointer" }}>
          <i className={`fa ${training ? "fa-spinner fa-spin" : "fa-graduation-cap"}`} style={{ marginRight: "0.3rem" }}></i>
          {training ? "Aprendiendo..." : "Entrenar Ahora"}
        </button>
      </div>

      {/* IMAP Status + Email Classification */}
      {emailStats && (
        <div style={{ display: "flex", gap: "0.4rem", marginBottom: "0.5rem", flexWrap: "wrap" }}>
          <div data-testid="imap-status" style={{
            padding: "0.35rem 0.6rem", borderRadius: "4px", fontSize: "0.7rem", fontWeight: 600,
            background: emailStats.imap_status === "disponible" ? "rgba(0,184,148,0.1)" : "rgba(253,203,110,0.2)",
            color: emailStats.imap_status === "disponible" ? "#00b894" : "#e17055",
            border: `1px solid ${emailStats.imap_status === "disponible" ? "rgba(0,184,148,0.3)" : "rgba(253,203,110,0.4)"}`,
          }}>
            <i className={`fa ${emailStats.imap_status === "disponible" ? "fa-check-circle" : "fa-clock-o"}`} style={{ marginRight: "0.3rem" }}></i>
            IMAP {emailStats.imap_status === "disponible" ? "Conectado" : `Recuperando (${emailStats.imap_backoff_restante_seg}s)`}
          </div>
          {emailStats.aprobaciones > 0 && (
            <div style={{ padding: "0.35rem 0.6rem", borderRadius: "4px", fontSize: "0.7rem", background: "rgba(0,184,148,0.08)", border: "1px solid rgba(0,184,148,0.2)", color: "#00b894", fontWeight: 600 }}>
              <i className="fa fa-check" style={{ marginRight: "0.2rem" }}></i>{emailStats.aprobaciones} Aprobaciones
            </div>
          )}
          {emailStats.rechazos > 0 && (
            <div style={{ padding: "0.35rem 0.6rem", borderRadius: "4px", fontSize: "0.7rem", background: "rgba(214,48,49,0.08)", border: "1px solid rgba(214,48,49,0.2)", color: "#d63031", fontWeight: 600 }}>
              <i className="fa fa-times" style={{ marginRight: "0.2rem" }}></i>{emailStats.rechazos} Rechazos
            </div>
          )}
          {emailStats.observaciones > 0 && (
            <div style={{ padding: "0.35rem 0.6rem", borderRadius: "4px", fontSize: "0.7rem", background: "rgba(253,203,110,0.1)", border: "1px solid rgba(253,203,110,0.3)", color: "#e17055", fontWeight: 600 }}>
              <i className="fa fa-eye" style={{ marginRight: "0.2rem" }}></i>{emailStats.observaciones} Observaciones
            </div>
          )}
        </div>
      )}

      {/* Data sources */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.4rem", marginBottom: "0.5rem" }}>
        {[
          { key: "credit_learning", label: "Emails Procesados", icon: "fa-envelope-open" },
          { key: "predic_history", label: "Predicciones", icon: "fa-chart-line" },
          { key: "score_history", label: "Scores Generados", icon: "fa-star" },
        ].map(s => (
          <div key={s.key} style={{ padding: "0.5rem", borderRadius: "4px", background: "var(--bg-tertiary)", textAlign: "center" }}>
            <i className={`fa ${s.icon}`} style={{ fontSize: "1rem", color: "var(--accent-primary)", display: "block", marginBottom: "0.2rem" }}></i>
            <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--text-primary)" }}>{sources[s.key] || 0}</div>
            <div style={{ fontSize: "0.65rem", color: "var(--text-secondary)" }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Learned patterns */}
      {patternKeys.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
          {patternKeys.map(key => {
            const pat = patterns[key];
            const meta = SOURCE_LABELS[key] || { label: key, icon: "fa-database" };
            return (
              <div key={key} data-testid={`pattern-${key}`}
                style={{ padding: "0.5rem 0.7rem", borderRadius: "4px", background: "rgba(99,110,114,0.06)", border: "1px solid var(--border)", fontSize: "0.78rem" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
                  <i className={`fa ${meta.icon}`} style={{ color: "var(--accent-primary)", fontSize: "0.75rem" }}></i>
                  <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>{meta.label}</span>
                  {pat.updated_at && (
                    <span style={{ marginLeft: "auto", fontSize: "0.65rem", color: "var(--text-tertiary)" }}>
                      {new Date(pat.updated_at).toLocaleDateString("es-CL")}
                    </span>
                  )}
                </div>
                <div style={{ color: "var(--text-secondary)", marginTop: "0.15rem" }}>{pat.summary}</div>
              </div>
            );
          })}
        </div>
      )}

      {patternKeys.length === 0 && !loading && (
        <div style={{ padding: "0.6rem", borderRadius: "4px", background: "rgba(108,92,231,0.06)", border: "1px solid rgba(108,92,231,0.15)", fontSize: "0.78rem", color: "var(--text-secondary)" }}>
          <i className="fa fa-lightbulb-o" style={{ marginRight: "0.3rem", color: "#6c5ce7" }}></i>
          La IA aun no ha generado patrones. Presione "Entrenar Ahora" o espere al ciclo automatico.
        </div>
      )}
    </div>
  );
}
