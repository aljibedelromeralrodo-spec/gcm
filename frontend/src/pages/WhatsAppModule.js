import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

/**
 * WhatsAppModule - Centro de control de WhatsApp para Martin
 * - Muestra QR para vincular si no esta conectado
 * - Bandeja de aprobaciones pendientes
 * - Botones de prueba
 */
export default function WhatsAppModule() {
  const [status, setStatus] = useState(null);
  const [qrData, setQrData] = useState(null);
  const [approvals, setApprovals] = useState([]);
  const [loading, setLoading] = useState(false);
  const [testMessage, setTestMessage] = useState("Hola, soy Martin desde Central Mutuos. Test inicial.");

  const refreshAll = useCallback(async () => {
    try {
      const [s, q, a] = await Promise.all([
        axios.get(`${API_URL}/api/whatsapp/status`),
        axios.get(`${API_URL}/api/whatsapp/qr`),
        axios.get(`${API_URL}/api/whatsapp/approvals?status=pending`),
      ]);
      setStatus(s.data);
      setQrData(q.data);
      setApprovals(a.data?.approvals || []);
    } catch (e) { console.error(e); }
  }, []);

  useEffect(() => {
    refreshAll();
    const t = setInterval(refreshAll, 5000); // poll every 5s while QR/approvals
    return () => clearInterval(t);
  }, [refreshAll]);

  const sendTest = async () => {
    setLoading(true);
    try {
      const r = await axios.post(`${API_URL}/api/whatsapp/test-send?message=${encodeURIComponent(testMessage)}`);
      alert(r.data?.success ? "Mensaje enviado a tu WhatsApp" : "Error: " + (r.data?.error || "?"));
    } catch (e) { alert("Error: " + e.message); }
    setLoading(false);
  };

  const resolveApproval = async (id, action, editText = null) => {
    try {
      const url = action === "approve"
        ? `${API_URL}/api/whatsapp/approval/${id}/approve`
        : `${API_URL}/api/whatsapp/approval/${id}/reject`;
      await axios.post(url, action === "approve" && editText ? { edited_text: editText } : {});
      await refreshAll();
    } catch (e) { console.error(e); }
  };

  const isConnected = status?.isReady;
  const hasQR = status?.hasQR && !isConnected;

  return (
    <div className="module-content" data-testid="whatsapp-module">
      {/* Portal ejecutivos: compartir archivos desde el teléfono */}
      <div data-testid="portal-ejecutivos-card" style={{ background: "var(--bg-card)", border: "1px solid rgba(212,175,55,0.4)", borderRadius: 2, padding: "1.25rem", marginBottom: "1.5rem" }}>
        <div style={{ fontSize: "1.05rem", fontWeight: 800, color: "var(--gold, #d4af37)", marginBottom: "0.5rem" }}>
          <i className="fa fa-mobile" style={{ marginRight: "0.5rem" }}></i>App móvil para ejecutivos — compartir archivos desde WhatsApp
        </div>
        <ol style={{ margin: "0.4rem 0 0.8rem 1.2rem", padding: 0, fontSize: "0.87rem", color: "var(--text-secondary, #94a3b8)", lineHeight: 1.8 }}>
          <li>El ejecutivo abre <b style={{ color: "var(--text-primary)" }}>{window.location.origin}</b> en Chrome del teléfono.</li>
          <li>Menú de Chrome (⋮) → <b style={{ color: "var(--text-primary)" }}>"Agregar a pantalla de inicio"</b> / "Instalar app".</li>
          <li>En WhatsApp: mantener presionado el archivo → <b style={{ color: "var(--text-primary)" }}>Compartir</b> → elegir <b style={{ color: "var(--text-primary)" }}>Central Mutuos</b>.</li>
          <li>Elige la carpeta del cliente (o crea una nueva) y los archivos llegan directo al sistema. Puede compartir varios: se van acumulando.</li>
        </ol>
        <button data-testid="btn-copy-portal-link" onClick={() => { navigator.clipboard.writeText(window.location.origin); alert("Link copiado. Envíalo a tus ejecutivos por WhatsApp."); }}
          style={{ background: "var(--gold, #d4af37)", color: "#0a0e17", border: "none", borderRadius: 2, padding: "0.5rem 1rem", fontWeight: 700, cursor: "pointer", marginRight: "0.6rem" }}>
          <i className="fa fa-copy" style={{ marginRight: "0.4rem" }}></i>Copiar link
        </button>
        <a data-testid="btn-share-portal-wa" href={`https://wa.me/?text=${encodeURIComponent("Instala la app de Central Mutuos para enviar los documentos de tus clientes directo al sistema: " + window.location.origin + " — Abrila en Chrome y tocá 'Agregar a pantalla de inicio'.")}`} target="_blank" rel="noreferrer"
          style={{ display: "inline-block", background: "#25d366", color: "#fff", borderRadius: 2, padding: "0.5rem 1rem", fontWeight: 700, textDecoration: "none" }}>
          <i className="fa fa-whatsapp" style={{ marginRight: "0.4rem" }}></i>Enviar por WhatsApp
        </a>
      </div>

      {/* Connection status */}
      <div style={{ background: "var(--bg-card)", border: `1px solid ${isConnected ? "rgba(16,185,129,0.5)" : "rgba(245,158,11,0.4)"}`, borderRadius: 2, padding: "1.25rem", marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.75rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <div style={{ width: 50, height: 50, borderRadius: 2, background: isConnected ? "linear-gradient(135deg, #25d366, #128c7e)" : "rgba(245,158,11,0.18)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1.6rem", color: isConnected ? "#fff" : "#f59e0b" }}>
              <i className="fa fa-whatsapp"></i>
            </div>
            <div>
              <div style={{ fontSize: "1.1rem", fontWeight: 800, color: "var(--text-primary)" }}>
                WhatsApp {isConnected ? <span style={{ color: "#10b981" }}>Conectado</span> : <span style={{ color: "#f59e0b" }}>Esperando vincular</span>}
              </div>
              <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: 2 }} data-testid="wa-status-text">
                {isConnected
                  ? `Martin esta conectado a tu WhatsApp y puede enviar mensajes con tu autorizacion.`
                  : `Escanea el QR con tu celular para vincular tu WhatsApp a Martin.`}
              </div>
            </div>
          </div>
          <button onClick={refreshAll} title="Refrescar" style={{ padding: "0.5rem 0.75rem", background: "rgba(255,255,255,0.04)", border: "1px solid var(--border)", borderRadius: 2, color: "var(--text-secondary)", cursor: "pointer" }}>
            <i className="fa fa-refresh"></i>
          </button>
        </div>

        {/* QR Code */}
        {hasQR && qrData?.qrCode && (
          <div data-testid="wa-qr-container" style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "1.5rem", background: "rgba(255,255,255,0.03)", borderRadius: 2, gap: "0.85rem" }}>
            <div style={{ background: "#fff", padding: "0.75rem", borderRadius: 2 }}>
              <img src={qrData.qrCode} alt="QR Code WhatsApp" style={{ width: 280, height: 280, display: "block" }} />
            </div>
            <div style={{ textAlign: "center", maxWidth: 460 }}>
              <h4 style={{ color: "var(--gold)", marginBottom: 6 }}>Como vincular</h4>
              <ol style={{ textAlign: "left", color: "var(--text-secondary)", fontSize: "0.85rem", lineHeight: 1.6, paddingLeft: "1.25rem" }}>
                <li>Abre WhatsApp en tu celular</li>
                <li>Toca <strong>Configuracion</strong> (o los 3 puntos en Android)</li>
                <li>Toca <strong>Dispositivos vinculados</strong></li>
                <li>Toca <strong>Vincular un dispositivo</strong> y escanea este QR</li>
              </ol>
            </div>
          </div>
        )}

        {/* Test send button */}
        {isConnected && (
          <div style={{ marginTop: "1rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            <input type="text" value={testMessage} onChange={e => setTestMessage(e.target.value)}
              data-testid="wa-test-message"
              style={{ flex: 1, minWidth: 200, padding: "0.55rem 0.85rem", background: "var(--bg-input)", border: "1px solid var(--border)", borderRadius: 2, color: "var(--text-primary)", fontSize: "0.85rem" }} />
            <button onClick={sendTest} disabled={loading} data-testid="wa-test-btn"
              style={{ padding: "0.55rem 1rem", background: "linear-gradient(135deg, #25d366, #128c7e)", color: "#fff", border: "none", borderRadius: 2, fontWeight: 700, cursor: loading ? "wait" : "pointer", fontSize: "0.85rem" }}>
              <i className={`fa ${loading ? 'fa-spinner fa-spin' : 'fa-paper-plane'}`}></i> Enviarme prueba
            </button>
          </div>
        )}
      </div>

      {/* Approval Queue */}
      <div style={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 2, padding: "1.25rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
          <h3 style={{ color: "var(--gold)", fontSize: "1rem", margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
            <i className="fa fa-tasks"></i>
            Bandeja de Aprobaciones
            <span style={{ background: approvals.length > 0 ? "#f59e0b" : "rgba(212,175,55,0.2)", color: approvals.length > 0 ? "#0a0e17" : "var(--text-muted)", borderRadius: 2, padding: "1px 9px", fontSize: "0.7rem", fontWeight: 700 }}>
              {approvals.length}
            </span>
          </h3>
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
            Tambien podes responder OK/NO/EDIT desde tu WhatsApp
          </span>
        </div>

        {approvals.length === 0 ? (
          <div style={{ textAlign: "center", padding: "2rem 1rem", color: "var(--text-muted)" }}>
            <i className="fa fa-check-circle" style={{ fontSize: "2rem", color: "#10b981", opacity: 0.5 }}></i>
            <p style={{ marginTop: "0.5rem", fontSize: "0.85rem" }}>No hay aprobaciones pendientes</p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }} data-testid="wa-approvals-list">
            {approvals.map(a => (
              <div key={a.id} data-testid={`approval-${a.id}`}
                style={{ background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.3)", borderRadius: 2, padding: "0.85rem 1rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <div style={{ fontWeight: 700, color: "var(--text-primary)", fontSize: "0.88rem" }}>
                    <span style={{ color: "#f59e0b", marginRight: 6 }}>#{a.id}</span>
                    {a.action_type}
                  </div>
                  <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                    {a.created_at ? new Date(a.created_at).toLocaleString("es-CL") : ""}
                  </span>
                </div>
                {a.description && <div style={{ fontSize: "0.82rem", color: "var(--text-secondary)", marginBottom: 6 }}>{a.description}</div>}
                {a.suggested_text && (
                  <div style={{ background: "rgba(0,0,0,0.25)", borderRadius: 2, padding: "0.55rem 0.75rem", fontSize: "0.8rem", color: "var(--text-secondary)", fontStyle: "italic", marginBottom: 8 }}>
                    "{a.suggested_text}"
                  </div>
                )}
                <div style={{ display: "flex", gap: 8 }}>
                  <button onClick={() => resolveApproval(a.id, "approve")} data-testid={`btn-approve-${a.id}`}
                    style={{ padding: "0.4rem 0.85rem", background: "rgba(16,185,129,0.18)", border: "1px solid #10b981", color: "#10b981", borderRadius: 2, fontWeight: 700, cursor: "pointer", fontSize: "0.78rem" }}>
                    <i className="fa fa-check"></i> Aprobar
                  </button>
                  <button onClick={() => resolveApproval(a.id, "reject")} data-testid={`btn-reject-${a.id}`}
                    style={{ padding: "0.4rem 0.85rem", background: "rgba(239,68,68,0.18)", border: "1px solid #ef4444", color: "#ef4444", borderRadius: 2, fontWeight: 700, cursor: "pointer", fontSize: "0.78rem" }}>
                    <i className="fa fa-times"></i> Rechazar
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
