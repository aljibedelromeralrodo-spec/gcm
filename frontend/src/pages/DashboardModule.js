import { useState, useEffect } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";
import IntelligencePanel from "../components/IntelligencePanel";
import AlertasPanel from "../components/AlertasPanel";
import ProactiveAlertsPanel from "../components/ProactiveAlertsPanel";
import LearningStatusPanel from "../components/LearningStatusPanel";
import GraficosRiesgo from "../components/GraficosRiesgo";
import CorreosSolicitudHoy from "../components/CorreosSolicitudHoy";
import RetenidosModoPrueba from "../components/RetenidosModoPrueba";
import CarpetasFaltantes from "../components/CarpetasFaltantes";
import VisualizadorCognitivo from "../components/VisualizadorCognitivo";
import PanelEspejo from "../components/PanelEspejo";
import AuditoriaFlujos from "../components/AuditoriaFlujos";
import TelepantallaCognitiva from "../components/TelepantallaCognitiva";

export default function DashboardModule({ valorUF: _valorUF, userName: _userName, onNavigate }) {
  const [data, setData] = useState(null);
  const [cobrosResumen, setCobrosResumen] = useState(null);
  const [emailStatus, setEmailStatus] = useState(null);
  const [emailSummary, setEmailSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshResult, setRefreshResult] = useState(null);
  const [motor, setMotor] = useState(null);
  const [semaforo, setSemaforo] = useState(null);
  const [docsJob, setDocsJob] = useState(null);
  const [tendencia, setTendencia] = useState("");
  const [hallazgos, setHallazgos] = useState(null);
  const [capturas, setCapturas] = useState([]);
  const [seguridad, setSeguridad] = useState(null);
  const [telepantalla, setTelepantalla] = useState(false);

  useEffect(() => {
    const abrir = () => setTelepantalla(true);
    window.addEventListener("abrir-telepantalla", abrir);
    return () => window.removeEventListener("abrir-telepantalla", abrir);
  }, []);

  const generarDocsDataset = async () => {
    try {
      await axios.post(`${API_URL}/api/dashai/dataset-documentos/generar`);
      const poll = setInterval(async () => {
        try {
          const r = await axios.get(`${API_URL}/api/dashai/dataset-documentos/estado`);
          setDocsJob(r.data);
          if (r.data.status !== "corriendo") clearInterval(poll);
        } catch { clearInterval(poll); }
      }, 3000);
      setDocsJob({ status: "corriendo", progreso: 0 });
    } catch { /* silencioso */ }
  };

  useEffect(() => {
    // Single batch call for dashboard + email status
    axios.get(`${API_URL}/api/central/dashboard-batch`).then(r => {
      setData(r.data.dashboard);
      setEmailStatus(r.data.email_status);
      setLoading(false);
    }).catch(() => {
      // Fallback to individual calls
      axios.get(`${API_URL}/api/central/dashboard`).then(r => { setData(r.data); setLoading(false); }).catch(() => setLoading(false));
      axios.get(`${API_URL}/api/central/email-status`).then(r => setEmailStatus(r.data)).catch((e) => console.error(e));
    });
    // Email summary loaded separately (slower, cached 5min)
    axios.get(`${API_URL}/api/central/email-summary`).then(r => setEmailSummary(r.data)).catch((e) => console.error(e));
    axios.get(`${API_URL}/api/gastos-operacionales/cobros-tasacion`).then(r => setCobrosResumen(r.data)).catch((e) => console.error(e));
    axios.get(`${API_URL}/api/motor/status`).then(r => setMotor(r.data)).catch(() => {});
    axios.get(`${API_URL}/api/firma/semaforo`).then(r => setSemaforo(r.data)).catch(() => setSemaforo({ error: true }));
    axios.get(`${API_URL}/api/dashai/dataset-documentos/estado`).then(r => setDocsJob(r.data)).catch(() => {});
    axios.get(`${API_URL}/api/mesa-brain/modelo`).then(r => setTendencia(r.data?.tendencia || "")).catch(() => {});
    axios.get(`${API_URL}/api/contraloria/casos`).then(r => setHallazgos(r.data)).catch(() => {});
    axios.get(`${API_URL}/api/capturas/recientes`).then(r => setCapturas(r.data?.capturas || [])).catch(() => {});
    axios.get(`${API_URL}/api/seguridad/respaldo`).then(r => setSeguridad(r.data)).catch(() => {});
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
      {capturas.length > 0 && (
        <div data-testid="alerta-captura-autonoma" style={{ background: "linear-gradient(160deg, rgba(45,35,8,0.95), rgba(12,9,2,0.98))",
          border: "1px solid rgba(212,175,55,0.7)", borderRadius: 0, padding: "0.9rem 1.2rem", marginBottom: "1rem",
          display: "flex", alignItems: "center", gap: 10, boxShadow: "0 0 35px -10px rgba(212,175,55,0.6)" }}>
          <i className="fa fa-rocket" style={{ color: "var(--gold)", fontSize: "1.1rem" }} />
          <div>
            <b style={{ color: "#FCF6BA", letterSpacing: "0.06em" }}>🚀 NUEVA CARPETA AUTÓNOMA CREADA: {capturas[0].cliente}</b>
            <div style={{ opacity: 0.8, fontSize: "0.78rem", color: "#C7B36A", marginTop: 2 }}>
              {capturas.length > 1 && `+${capturas.length - 1} captura(s) más · `}
              El prospecto subió su Cédula y Liquidación desde el link de WhatsApp — carpeta lista en Carpeta Clientes
              {capturas[0].proyecto ? ` · Proyecto ${capturas[0].proyecto}` : ""}
            </div>
          </div>
        </div>
      )}
      {hallazgos && ((hallazgos.riesgo_falso_positivo || 0) + (hallazgos.bajo_auditoria || 0)) > 0 && (
        <div data-testid="alerta-hallazgo-contraloria" style={{ background: "linear-gradient(160deg, rgba(70,10,20,0.97), rgba(20,2,6,0.99))",
          border: "1px solid rgba(225,29,72,0.75)", borderRadius: 0, padding: "0.9rem 1.2rem", marginBottom: "1rem",
          display: "flex", alignItems: "center", gap: 10, boxShadow: "0 0 40px -8px rgba(225,29,72,0.7)" }}>
          <i className="fa fa-gavel" style={{ color: "#fb7185", fontSize: "1.2rem" }} />
          <div>
            <b style={{ color: "#fecaca", letterSpacing: "0.06em" }}>🚨 HALLAZGO DE CONTRALORÍA — DashAI detectó inconsistencias de la MESA</b>
            <div style={{ opacity: 0.85, fontSize: "0.8rem", color: "#fda4af", marginTop: 2 }}>
              {(hallazgos.riesgo_falso_positivo || 0) > 0 && <span>{hallazgos.riesgo_falso_positivo} caso(s) con RIESGO DE FALSO POSITIVO · </span>}
              {(hallazgos.bajo_auditoria || 0) > 0 && <span>{hallazgos.bajo_auditoria} bajo auditoría · </span>}
              {(hallazgos.casos || []).filter(c => c.estado_auditoria === "RIESGO DE FALSO POSITIVO").slice(0, 3).map(c => c.cliente).join(", ")}
            </div>
          </div>
          <span style={{ marginLeft: "auto", color: "var(--gold)", fontWeight: 700, fontSize: "0.78rem",
            border: "1px solid rgba(212,175,55,0.5)", padding: "0.3rem 0.8rem", whiteSpace: "nowrap" }}>
            Revisar en Contraloría →
          </span>
        </div>
      )}
      {semaforo?.alerta && (
        <div data-testid="alerta-saldo-firmas" style={{ background: "linear-gradient(160deg, rgba(70,10,20,0.95), rgba(20,2,6,0.98))",
          border: "1px solid rgba(225,29,72,0.6)", borderRadius: 0, padding: "0.8rem 1.2rem", marginBottom: "1rem",
          display: "flex", alignItems: "center", gap: 10, boxShadow: "0 0 30px -10px rgba(225,29,72,0.55)" }}>
          <i className="fa fa-exclamation-triangle" style={{ color: "#fb7185", fontSize: "1.1rem" }} />
          <b style={{ color: "#fb7185", letterSpacing: "0.06em" }}>⚠ ATENCIÓN: Saldo de firmas próximo a agotarse</b>
          <span style={{ opacity: 0.75, fontSize: "0.82rem" }}>
            (Propias: {semaforo.propias} · Terceros: {semaforo.terceros})
          </span>
          <a href="https://www.migrup.cl" target="_blank" rel="noreferrer" data-testid="alerta-recarga-link"
             style={{ marginLeft: "auto", color: "var(--gold)", fontWeight: 700, fontSize: "0.8rem", textDecoration: "none",
               border: "1px solid rgba(212,175,55,0.5)", padding: "0.3rem 0.8rem" }}>
            <i className="fa fa-bolt" style={{ marginRight: 6 }} />Recargar ahora
          </a>
        </div>
      )}
      {motor && (
        <div data-testid="motor-247-badge" style={{ display: "inline-flex", alignItems: "center", gap: 8,
          background: "rgba(14,14,16,0.9)", border: `1px solid ${motor.operativo ? "rgba(16,217,142,0.4)" : "rgba(225,29,72,0.4)"}`,
          borderRadius: 0, padding: "0.35rem 0.9rem", marginBottom: "0.8rem",
          fontSize: "0.72rem", letterSpacing: "0.12em", textTransform: "uppercase",
          color: motor.operativo ? "#10d98e" : "#e11d48", fontWeight: 700 }}>
          <span style={{ width: 7, height: 7, borderRadius: "50%", background: motor.operativo ? "#10d98e" : "#e11d48",
            boxShadow: motor.operativo ? "0 0 8px rgba(16,217,142,0.8)" : "0 0 8px rgba(225,29,72,0.8)" }} />
          Motor 24/7: {motor.operativo ? "OPERATIVO" : "DETENIDO"}
        </div>
      )}
      <ProactiveAlertsPanel />
      {telepantalla && <TelepantallaCognitiva onCerrar={() => setTelepantalla(false)}
        onAbrirCarpeta={(fid) => { sessionStorage.setItem("cm_abrir_folder_id", fid); setTelepantalla(false); onNavigate && onNavigate("clientes"); }} />}
      <VisualizadorCognitivo modo="panel" />
      <PanelEspejo />
      <AuditoriaFlujos />
      <RetenidosModoPrueba />
      <CarpetasFaltantes />
      <CorreosSolicitudHoy />
      {seguridad && (
        <div data-testid="seguridad-datos-card" style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap",
          background: "rgba(14,14,16,0.9)", border: `1px solid ${seguridad.estado === "SINCRONIZADO" ? "rgba(16,217,142,0.35)" : "rgba(212,175,55,0.35)"}`,
          borderRadius: 0, padding: "0.7rem 1.1rem", marginBottom: "1rem" }}>
          <b style={{ color: "var(--gold)", fontSize: "0.82rem", letterSpacing: "0.08em" }}>🛡️ Seguridad de Datos</b>
          <span data-testid="seguridad-estado" style={{ fontSize: "0.74rem", fontWeight: 800, letterSpacing: "0.08em",
            color: seguridad.estado === "SINCRONIZADO" ? "#10d98e" : "#e7cf7a" }}>
            Estado del Respaldo: {seguridad.estado || "INICIANDO"}
          </span>
          <span data-testid="seguridad-ultima-copia" style={{ fontSize: "0.72rem", opacity: 0.7 }}>
            Última copia en nube: {seguridad.ultima_copia ? seguridad.ultima_copia.slice(0, 16).replace("T", " ") : "pendiente"}
          </span>
          <span style={{ fontSize: "0.68rem", opacity: 0.5, marginLeft: "auto", textTransform: "uppercase", letterSpacing: "0.1em" }}>
            {seguridad.objetos || 0} archivos espejados · Búnker Cloud pasivo
          </span>
        </div>
      )}
      {semaforo && !semaforo.error && (
        <div data-testid="boveda-firmas-card" style={{ border: "1px solid transparent", borderRadius: 0, marginBottom: "1rem",
          backgroundImage: "linear-gradient(115deg, rgba(255,255,255,0.07) 0%, rgba(255,255,255,0.02) 18%, transparent 32%), linear-gradient(160deg, rgba(22,22,24,0.97), rgba(6,6,8,0.99)), linear-gradient(135deg, #BF953F, #FCF6BA, #B38728, #FBF5B7, #AA771C)",
          backgroundOrigin: "border-box", backgroundClip: "padding-box, padding-box, border-box",
          boxShadow: "0 35px 70px -20px rgba(0,0,0,0.95), 0 0 45px -14px rgba(191,149,63,0.5)", padding: "1.2rem 1.5rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: "1rem" }}>
            <b style={{ color: "var(--gold)", fontSize: "1.05rem", letterSpacing: "0.08em" }}>💰 Bóveda de Firmas eCert</b>
            <span style={{ fontSize: "0.7rem", opacity: 0.55, textTransform: "uppercase", letterSpacing: "0.12em" }}>Saldo en vivo · migrup.cl</span>
            <a href="https://www.migrup.cl" target="_blank" rel="noreferrer" data-testid="boveda-recarga-link"
               style={{ marginLeft: "auto", color: "#0a0a0a", fontWeight: 800, fontSize: "0.78rem", textDecoration: "none", padding: "0.4rem 1rem",
                 backgroundImage: "linear-gradient(135deg, #BF953F, #FCF6BA 45%, #B38728, #FBF5B7 80%, #AA771C)",
                 boxShadow: "0 0 20px -6px rgba(191,149,63,0.7)" }}>
              <i className="fa fa-diamond" style={{ marginRight: 6 }} />Recarga Rápida
            </a>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "0.8rem" }}>
            <div data-testid="boveda-propias" style={{ background: "rgba(255,255,255,0.03)", padding: "0.9rem 1rem", textAlign: "center",
              border: semaforo.propias === 0 ? "1px solid rgba(225,29,72,0.7)" : "1px solid rgba(212,175,55,0.25)",
              boxShadow: semaforo.propias === 0 ? "0 0 25px -8px rgba(225,29,72,0.8)" : "none" }}>
              <div style={{ fontSize: "2rem", fontWeight: 800, color: semaforo.propias === 0 ? "#e11d48" : (semaforo.propias < 5 ? "#fb7185" : "var(--gold)"),
                textShadow: semaforo.propias === 0 ? "0 0 14px rgba(225,29,72,0.9)" : "none" }}>{semaforo.propias}</div>
              <div style={{ fontSize: "0.72rem", opacity: 0.75, textTransform: "uppercase", letterSpacing: "0.1em" }}>Firmas Propias</div>
            </div>
            <div data-testid="boveda-terceros" style={{ background: "rgba(255,255,255,0.03)", padding: "0.9rem 1rem", textAlign: "center", border: "1px solid rgba(16,217,142,0.35)" }}>
              <div style={{ fontSize: "2rem", fontWeight: 800, color: "#10d98e", textShadow: "0 0 12px rgba(16,217,142,0.5)" }}>{semaforo.terceros}</div>
              <div style={{ fontSize: "0.72rem", opacity: 0.75, textTransform: "uppercase", letterSpacing: "0.1em" }}>Firmas de Terceros</div>
            </div>
            <div data-testid="boveda-documentos" style={{ background: "rgba(255,255,255,0.03)", padding: "0.9rem 1rem", textAlign: "center", border: "1px solid rgba(212,175,55,0.25)" }}>
              <div style={{ fontSize: "2rem", fontWeight: 800, color: "#FCF6BA" }}>{semaforo.documentos}</div>
              <div style={{ fontSize: "0.72rem", opacity: 0.75, textTransform: "uppercase", letterSpacing: "0.1em" }}>Documentos Disponibles</div>
            </div>
          </div>
        </div>
      )}
      <LearningStatusPanel />
      {semaforo && !semaforo.error && (
        <div data-testid="dashai-export-card" style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: "1rem",
          border: "1px solid rgba(212,175,55,0.35)", background: "linear-gradient(160deg, rgba(18,18,20,0.97), rgba(6,6,8,0.99))",
          padding: "0.7rem 1.2rem" }}>
          <i className="fa fa-flask" style={{ color: "var(--gold)" }} />
          <div style={{ flex: 1 }}>
            <b style={{ color: "var(--gold)", fontSize: "0.85rem", letterSpacing: "0.06em" }}>📊 Dataset para DashAI</b>
            <div style={{ fontSize: "0.72rem", opacity: 0.65 }}>
              Exporta tu cartera en CSV para entrenar tu modelo de aprobación en tu computador — sin gasto de nube
            </div>
          </div>
          <button data-testid="dashai-export-btn"
            onClick={() => window.open(`${API_URL}/api/dashai/dataset`, "_blank")}
            style={{ background: "transparent", color: "var(--gold)", border: "1px solid rgba(212,175,55,0.55)",
              padding: "0.45rem 1.1rem", cursor: "pointer", fontWeight: 700, fontSize: "0.78rem", letterSpacing: "0.06em" }}>
            <i className="fa fa-download" style={{ marginRight: 6 }} />Cartera CSV
          </button>
          <button data-testid="dashai-mesa-btn"
            onClick={() => window.open(`${API_URL}/api/dashai/dataset-mesa`, "_blank")}
            style={{ background: "transparent", color: "var(--gold)", border: "1px solid rgba(212,175,55,0.55)",
              padding: "0.45rem 1.1rem", cursor: "pointer", fontWeight: 700, fontSize: "0.78rem", letterSpacing: "0.06em" }}>
            <i className="fa fa-balance-scale" style={{ marginRight: 6 }} />Historial MESA
          </button>
          {docsJob?.status === "corriendo" ? (
            <span data-testid="dashai-docs-progreso" style={{ color: "var(--gold)", fontSize: "0.75rem", fontWeight: 700 }}>
              <i className="fa fa-cog fa-spin" style={{ marginRight: 6 }} />
              Extrayendo {docsJob.progreso || 0}/{docsJob.total || "…"}
            </span>
          ) : docsJob?.status === "listo" || docsJob?.descargable ? (
            <button data-testid="dashai-docs-descargar-btn"
              onClick={() => window.open(`${API_URL}/api/dashai/dataset-documentos`, "_blank")}
              style={{ background: "linear-gradient(135deg, #BF953F, #FCF6BA 50%, #AA771C)", color: "#0a0a0a",
                border: "none", padding: "0.45rem 1.1rem", cursor: "pointer", fontWeight: 800, fontSize: "0.78rem" }}>
              <i className="fa fa-file-text" style={{ marginRight: 6 }} />Docs Entrenamiento
            </button>
          ) : (
            <button data-testid="dashai-docs-generar-btn" onClick={generarDocsDataset}
              style={{ background: "transparent", color: "var(--gold)", border: "1px solid rgba(212,175,55,0.55)",
                padding: "0.45rem 1.1rem", cursor: "pointer", fontWeight: 700, fontSize: "0.78rem", letterSpacing: "0.06em" }}>
              <i className="fa fa-cogs" style={{ marginRight: 6 }} />Generar Docs
            </button>
          )}
        </div>
      )}
      {tendencia && (
        <div data-testid="dashai-tendencia" style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: "1rem",
          border: "1px solid rgba(212,175,55,0.3)", background: "rgba(30,26,12,0.6)",
          padding: "0.55rem 1.2rem", color: "#F5E7B8", fontSize: "0.78rem" }}>
          <i className="fa fa-line-chart" style={{ color: "var(--gold)" }} />
          <span><b style={{ color: "var(--gold)" }}>DashAI:</b> {tendencia}</span>
        </div>
      )}
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
              { lbl: "Pagadas", val: cobrosResumen.resumen.pagadas, color: "#34eab9", extra: cobrosResumen.resumen.monto_pagado_clp },
              { lbl: "Pendientes de pago", val: cobrosResumen.resumen.pendientes, color: "#fb7185", extra: cobrosResumen.resumen.monto_pendiente_clp },
            ].map((s, i) => (
              <div key={i} data-testid={`cobros-stat-${i}`} style={{ background: "rgba(255,255,255,0.04)", border: "1px solid transparent", backgroundImage: "linear-gradient(115deg, rgba(255,255,255,0.09) 0%, rgba(255,255,255,0.02) 18%, transparent 32%), linear-gradient(160deg, rgba(30,30,30,0.95), rgba(10,10,10,0.98)), linear-gradient(135deg, #BF953F, #FCF6BA, #B38728, #FBF5B7, #AA771C)", boxShadow: "0 35px 70px -20px rgba(0,0,0,0.95), 0 0 38px -16px rgba(191,149,63,0.45)", backgroundOrigin: "border-box", backgroundClip: "padding-box, padding-box, border-box", borderRadius: 0, padding: "0.7rem 1rem", textAlign: "center" }}>
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
            background: emailStatus.connected ? "#10d98e" : "#e11d48",
            boxShadow: emailStatus.connected ? "0 0 8px #10d98e" : "0 0 8px #e11d48"
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
              <span className="dash-recent-date">{s.timestamp ? new Date(s.timestamp).toLocaleDateString("es-CL").replace(/-/g, "/") : ""}</span>
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

      <GraficosRiesgo />
      <IntelligencePanel />
    </div>
  );
}

