import { useState, useEffect } from "react";
import axios from "axios";
import { API_URL, formatCurrency } from "../utils/formatters";
import IntelligencePanel from "../components/IntelligencePanel";
import AlertasPanel from "../components/AlertasPanel";
import ProactiveAlertsPanel from "../components/ProactiveAlertsPanel";
import LearningStatusPanel from "../components/LearningStatusPanel";

export default function DashboardModule({ valorUF, userName, onNavigate }) {
  const [data, setData] = useState(null);
  const [cobrosResumen, setCobrosResumen] = useState(null);
  const [emailStatus, setEmailStatus] = useState(null);
  const [emailSummary, setEmailSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshResult, setRefreshResult] = useState(null);

  useEffect(() => {
    // Single batch call for dashboard + email status
    axios.get(`${API_URL}/api/central/dashboard-batch`).then(r => {
      setData(r.data.dashboard);
      setEmailStatus(r.data.email_status);
      setLoading(false);
    }).catch(() => {
      // Fallback to individual calls
      axios.get(`${API_URL}/api/central/dashboard`).then(r => { setData(r.data); setLoading(false); }).catch(() => setLoading(false));
      axios.get(`${API_URL}/api/central/email-status`).then(r => setEmailStatus(r.data)).catch(() => {});
    });
    // Email summary loaded separately (slower, cached 5min)
    axios.get(`${API_URL}/api/central/email-summary`).then(r => setEmailSummary(r.data)).catch(() => {});
    axios.get(`${API_URL}/api/gastos-operacionales/cobros-tasacion`).then(r => setCobrosResumen(r.data)).catch(() => {});
  }, []);

  const refreshKnowledge = async () => {
    setRefreshing(true);
    setRefreshResult(null);
    try {
      const r = await axios.post(`${API_URL}/api/ia/refresh-knowledge`);
      setRefreshResult(r.data);
    } catch {
      setRefreshResult({ status: "error", message: "Error al actualizar" });
    }
    setRefreshing(false);
  };

  if (loading) return (
    <div className="module-content" style={{ textAlign: "center", padding: "4rem" }}>
      <i className="fa fa-spinner fa-spin" style={{ fontSize: "2rem", color: "var(--gold)" }}></i>
      <p style={{ color: "var(--text-secondary)", marginTop: "1rem" }}>Cargando dashboard...</p>
    </div>
  );

  return (
    <div className="module-content" data-testid="dashboard-module">
      <ProactiveAlertsPanel />
      <LearningStatusPanel />
      <AlertasPanel />
      {cobrosResumen?.resumen && (
        <div data-testid="panel-cobros-tasacion" style={{ background: "rgba(14,14,16,0.9)", border: "1px solid rgba(212,175,55,0.25)", borderRadius: 0, padding: "1rem 1.3rem", marginBottom: "1rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: "0.7rem" }}>
            <i className="fa fa-home" style={{ color: "var(--gold)" }} />
            <b style={{ color: "var(--gold)" }}>Cobros de Tasación — Vivienda Usada ({cobrosResumen.resumen.mes})</b>
            <span style={{ fontSize: 12, opacity: 0.6 }}>· {cobrosResumen.monto_uf} UF ≈ {cobrosResumen.monto_clp} c/u</span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: "0.7rem" }}>
            {[
              { lbl: "Cobros enviados", val: cobrosResumen.resumen.enviadas, color: "#d4af37", extra: "" },
              { lbl: "Pagadas", val: cobrosResumen.resumen.pagadas, color: "#4ade80", extra: cobrosResumen.resumen.monto_pagado_clp },
              { lbl: "Pendientes de pago", val: cobrosResumen.resumen.pendientes, color: "#f87171", extra: cobrosResumen.resumen.monto_pendiente_clp },
            ].map((s, i) => (
              <div key={i} data-testid={`cobros-stat-${i}`} style={{ background: "rgba(255,255,255,0.04)", border: "1px solid transparent", backgroundImage: "linear-gradient(160deg, rgba(30,30,30,0.95), rgba(10,10,10,0.98)), linear-gradient(135deg, #BF953F, #FCF6BA, #B38728, #FBF5B7, #AA771C)", boxShadow: "0 35px 70px -20px rgba(0,0,0,0.95), 0 0 38px -16px rgba(191,149,63,0.45)", backgroundOrigin: "border-box", backgroundClip: "padding-box, border-box", borderRadius: 0, padding: "0.7rem 1rem", textAlign: "center" }}>
                <div style={{ fontSize: "1.6rem", fontWeight: 800, color: s.color }}>{s.val}</div>
                <div style={{ fontSize: "0.72rem", opacity: 0.7, textTransform: "uppercase", letterSpacing: 0.5 }}>{s.lbl}</div>
                {s.extra && <div style={{ fontSize: "0.8rem", color: s.color, fontWeight: 700, marginTop: 2 }}>{s.extra}</div>}
              </div>
            ))}
          </div>
        </div>
      )}
      {emailStatus && (
        <div className="dash-email-status" data-testid="email-status-bar">
          <span className="dash-email-dot" style={{
            background: emailStatus.connected ? "#10b981" : "#ef4444",
            boxShadow: emailStatus.connected ? "0 0 8px #10b981" : "0 0 8px #ef4444"
          }}></span>
          <div className="dash-email-info">
            <div className="dash-email-label">
              {emailStatus.connected ? "Email conectado" : "Email desconectado"}
            </div>
            <div className="dash-email-account">
              {emailStatus.account} {emailStatus.total_emails ? `(${emailStatus.total_emails} correos)` : ""}
            </div>
          </div>
        </div>
      )}

      <div className="dash-refresh-bar" data-testid="knowledge-refresh">
        <button className="dash-refresh-btn" onClick={refreshKnowledge} disabled={refreshing} data-testid="btn-refresh-knowledge">
          <i className={`fa fa-${refreshing ? 'spinner fa-spin' : 'refresh'}`}></i>
          {refreshing ? "Actualizando..." : "Actualizar Conocimiento IA"}
        </button>
        {refreshResult && (
          <div className={`dash-refresh-result ${refreshResult.status === "ok" ? "success" : "error"}`} data-testid="refresh-result">
            <i className={`fa fa-${refreshResult.status === "ok" ? "check-circle" : "exclamation-circle"}`}></i>
            <span>{refreshResult.message}</span>
            {refreshResult.results?.patterns?.total_simulaciones && (
              <span className="dash-refresh-detail">Patrones: {refreshResult.results.patterns.total_simulaciones} simulaciones</span>
            )}
            {refreshResult.results?.emails?.nuevas_operaciones > 0 && (
              <span className="dash-refresh-detail">+{refreshResult.results.emails.nuevas_operaciones} operaciones</span>
            )}
          </div>
        )}
      </div>

      <div className="dashboard-grid" data-testid="dashboard-metrics">
        <div className="dash-card" onClick={() => onNavigate("historial")} style={{ cursor: "pointer" }}>
          <i className="fa fa-bar-chart dash-card-icon"></i>
          <div className="dash-card-label">Simulaciones</div>
          <div className="dash-card-value" data-testid="metric-simulaciones">{data?.simulaciones || 0}</div>
        </div>
        <div className="dash-card" onClick={() => onNavigate("clientes")} style={{ cursor: "pointer" }}>
          <i className="fa fa-users dash-card-icon"></i>
          <div className="dash-card-label">Clientes</div>
          <div className="dash-card-value" data-testid="metric-clientes">{data?.clientes || 0}</div>
        </div>
        <div className="dash-card">
          <i className="fa fa-comments dash-card-icon"></i>
          <div className="dash-card-label">Conversaciones IA</div>
          <div className="dash-card-value" data-testid="metric-conversaciones">{data?.conversaciones || 0}</div>
        </div>
        <div className="dash-card">
          <i className="fa fa-envelope dash-card-icon"></i>
          <div className="dash-card-label">Correos Aprendidos</div>
          <div className="dash-card-value" data-testid="metric-correos">{data?.correos_aprendidos || 0}</div>
        </div>
      </div>

      <div className="dash-section-title"><i className="fa fa-clock-o"></i> Actividad Reciente</div>
      <div className="dash-recent-grid">
        <div className="dash-recent-card">
          <h4><i className="fa fa-line-chart"></i> Ultimas Simulaciones</h4>
          {data?.recientes_simulaciones?.length > 0 ? data.recientes_simulaciones.map((s, i) => (
            <div key={i} className="dash-recent-item" data-testid={`recent-sim-${i}`}>
              <span className="dash-recent-name">{s.nombre_completo || "Sin nombre"}</span>
              <span className={`dash-recent-status ${s.precalificacion_aprobada ? 'dash-status-ok' : 'dash-status-fail'}`}>
                {s.precalificacion_aprobada ? "Aprobado" : "Rechazado"}
              </span>
              <span className="dash-recent-date">{s.timestamp ? new Date(s.timestamp).toLocaleDateString("es-CL") : ""}</span>
            </div>
          )) : <p style={{ color: "var(--text-muted)", fontSize: "0.82rem" }}>Sin simulaciones recientes</p>}
        </div>
        <div className="dash-recent-card">
          <h4><i className="fa fa-comment"></i> Ultimas Conversaciones</h4>
          {data?.recientes_conversaciones?.length > 0 ? data.recientes_conversaciones.map((c, i) => (
            <div key={i} className="dash-recent-item" data-testid={`recent-conv-${i}`}>
              <span className="dash-recent-name">{c.user_name || "Usuario"}</span>
              <span className="dash-recent-date" style={{ flex: 1, textAlign: "left", marginLeft: "8px", color: "var(--text-secondary)" }}>
                {(c.user_msg || "").slice(0, 40)}...
              </span>
            </div>
          )) : <p style={{ color: "var(--text-muted)", fontSize: "0.82rem" }}>Sin conversaciones recientes</p>}
        </div>
      </div>

      {emailSummary?.emails?.length > 0 && (
        <>
          <div className="dash-section-title" style={{ marginTop: "1.5rem" }}>
            <i className="fa fa-envelope-open"></i> Correos Recientes
            <span style={{ marginLeft: "auto", fontSize: "0.72rem", color: "var(--text-muted)", fontWeight: 400 }}>
              {emailSummary.total} correos recientes
            </span>
          </div>
          <div className="dash-email-list" data-testid="dashboard-email-summary">
            {emailSummary.emails.slice(0, 5).map((em, i) => (
              <div key={i} className="dash-email-item" data-testid={`email-summary-${i}`}>
                <div className="dash-email-item-header">
                  <span className="dash-email-item-from">{em.from?.split("<")[0]?.trim() || em.from}</span>
                  <span className="dash-email-item-date">{em.date}</span>
                </div>
                <div className="dash-email-item-subject">{em.subject || "(Sin asunto)"}</div>
                <div className="dash-email-item-preview">{em.preview}</div>
                {em.has_attachments && (
                  <span className="dash-email-att-badge"><i className="fa fa-paperclip"></i> Adjuntos</span>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      <IntelligencePanel />
    </div>
  );
}

