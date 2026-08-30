import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const ORO = "#d4af37";

export default function PanelEstadoCarpeta({ folder }) {
  const [est, setEst] = useState(null);
  const [detalle, setDetalle] = useState(null); // 'sistema' | 'correo' | null
  const [enviando, setEnviando] = useState(false);
  const [msg, setMsg] = useState("");

  const cargar = useCallback(() => {
    if (!folder?.id) return;
    axios.get(`${API}/api/clientes/folders/${folder.id}/panel-estado`)
      .then(r => setEst(r.data)).catch(() => setEst(null));
  }, [folder?.id]);
  useEffect(() => { setDetalle(null); setMsg(""); cargar(); }, [cargar]);

  if (!est) return null;
  const faltantes = (est.documentos_faltantes && est.documentos_faltantes.length)
    ? est.documentos_faltantes
    : (folder.alertas_documentales || []);
  const recomendados = folder.alertas_recomendadas || [];
  const formatos = folder.alertas_formato || [];

  const solicitarDocs = async () => {
    if (!window.confirm(`¿Enviar correo automático a ${est.destinatario_solicitud || "el remitente"} solicitando los ${faltantes.length} documento(s) faltante(s)?`)) return;
    setEnviando(true); setMsg("");
    try {
      const r = await axios.post(`${API}/api/clientes/folders/${folder.id}/pedir-faltantes`,
        { confirm: true, destinatario: est.destinatario_solicitud, faltantes, mensaje: "" });
      setMsg(`✅ Solicitud enviada a ${r.data.to || est.destinatario_solicitud}`);
    } catch (e) { setMsg(`🚨 ${e.response?.data?.detail || "Error al enviar la solicitud"}`); }
    setEnviando(false);
  };

  const Indicador = ({ activo, labelOn, labelOff, tipo }) => (
    <button data-testid={`indicador-${tipo}`} onClick={() => setDetalle(detalle === tipo ? null : tipo)}
      style={{ padding: "0.35rem 0.9rem", fontWeight: 800, fontSize: 11.5, letterSpacing: 0.5, cursor: "pointer",
        background: activo ? "rgba(16,217,142,0.12)" : "rgba(225,29,72,0.1)",
        border: activo ? "1px solid rgba(16,217,142,0.5)" : "1px solid rgba(225,29,72,0.45)",
        color: activo ? "#10d98e" : "#fb7185" }}>
      <i className={`fa ${activo ? "fa-check-circle" : "fa-times-circle"}`}></i> {activo ? labelOn : labelOff}
      <i className={`fa fa-caret-${detalle === tipo ? "up" : "down"}`} style={{ marginLeft: 6, opacity: 0.7 }}></i>
    </button>
  );

  const det = detalle === "sistema" ? est.detalle_sistema : detalle === "correo" ? est.detalle_correo : null;

  return (
    <div data-testid="panel-estado-carpeta" style={{ margin: "0.6rem 0 0.9rem", padding: "0.8rem 1rem",
      background: "rgba(14,14,16,0.9)", border: "1px solid rgba(212,175,55,0.3)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
        {est.resultado === "aprobado" && (
          <span data-testid="estado-aprobado" style={{ fontSize: "1.5rem", fontWeight: 900, letterSpacing: 2,
            color: "#22c55e", textShadow: "0 0 18px rgba(34,197,94,0.5)" }}>✓ APROBADO</span>
        )}
        {est.resultado === "reprobado" && (
          <span data-testid="estado-rechazado" style={{ fontSize: "1.5rem", fontWeight: 900, letterSpacing: 2,
            color: "#ef4444", textShadow: "0 0 18px rgba(239,68,68,0.5)" }}>✕ RECHAZADO</span>
        )}
        {!est.resultado && (
          <span data-testid="estado-sin-resultado" style={{ fontSize: "0.85rem", fontWeight: 800, color: "#94a3b8" }}>
            SIN RESULTADO REGISTRADO</span>
        )}
        {est.fecha_resultado && <span style={{ fontSize: 11, color: "#8a8a8a" }}>({est.fecha_resultado})</span>}
        <Indicador tipo="correo" activo={est.enviado_correo} labelOn="ENVIADO POR CORREO" labelOff="NO ENVIADO POR CORREO" />
        <Indicador tipo="sistema" activo={est.enviado_sistema} labelOn="ENVIADO POR SISTEMA" labelOff="NO ENVIADO POR SISTEMA" />
        {est.alerta_inactividad && (
          <span data-testid="alerta-inactividad" style={{ padding: "0.35rem 0.9rem", fontWeight: 800, fontSize: 11.5,
            background: "rgba(225,29,72,0.14)", border: "1.5px solid #e11d48", color: "#fb7185" }}>
            ⏸ {est.dias_sin_movimiento} día(s) hábiles SIN MOVIMIENTO</span>
        )}
        {est.simulacion_desactualizada && (
          <span data-testid="alerta-sim-desactualizada" title={est.simulacion_desactualizada_motivo}
            style={{ padding: "0.35rem 0.9rem", fontWeight: 800, fontSize: 11.5,
              background: "rgba(234,88,12,0.14)", border: "1.5px solid #ea580c", color: "#fb923c" }}>
            ⚠ SIMULACIÓN DESACTUALIZADA</span>
        )}
      </div>
      {detalle && (
        <div data-testid={`detalle-envio-${detalle}`} style={{ marginTop: 8, padding: "0.6rem 0.9rem", fontSize: 12,
          background: "rgba(212,175,55,0.05)", border: "1px solid rgba(212,175,55,0.25)", color: "#c9c4b4", lineHeight: 1.7 }}>
          {det ? (
            <>
              <b style={{ color: ORO }}>Detalle del envío ({detalle === "sistema" ? "por sistema" : "por correo directo"})</b><br />
              📅 Fecha y hora: <b>{det.fecha || "—"}</b> · 📨 Destinatario: <b>{det.destinatario}</b><br />
              {det.contenido && <>📝 Contenido: {det.contenido}<br /></>}
              {det.adjuntos && <>📎 Adjuntos: {det.adjuntos}</>}
            </>
          ) : (
            <span style={{ color: "#fb7185" }}>Esta carpeta aún no registra envío por {detalle === "sistema" ? "el sistema" : "correo directo"}.</span>
          )}
        </div>
      )}
      {faltantes.length > 0 && (
        <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <span style={{ fontSize: 11, fontWeight: 800, color: "#fb7185", letterSpacing: 1 }}>DOCUMENTOS FALTANTES:</span>
          {faltantes.map((d, i) => (
            <span key={i} data-testid={`doc-faltante-${i}`} style={{ fontSize: 10.5, fontWeight: 700, padding: "2px 8px",
              background: "rgba(225,29,72,0.1)", border: "1px solid rgba(225,29,72,0.4)", color: "#fda4af" }}>{d}</span>
          ))}
          <button data-testid="btn-solicitar-documentos" onClick={solicitarDocs} disabled={enviando || !est.destinatario_solicitud}
            title={est.destinatario_solicitud ? `Enviar solicitud a ${est.destinatario_solicitud}` : "La carpeta no tiene remitente asociado"}
            style={{ padding: "0.35rem 1rem", fontWeight: 800, fontSize: 11.5, cursor: "pointer",
              background: "rgba(212,175,55,0.15)", border: "1px solid var(--gold, #d4af37)", color: ORO,
              opacity: (enviando || !est.destinatario_solicitud) ? 0.5 : 1 }}>
            <i className={`fa ${enviando ? "fa-spinner fa-spin" : "fa-paper-plane"}`}></i> Solicitar Documentos
          </button>
        </div>
      )}
      {recomendados.length > 0 && (
        <div data-testid="docs-recomendados" style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <span style={{ fontSize: 11, fontWeight: 800, color: "#e7cf7a", letterSpacing: 1 }}>RECOMENDADOS:</span>
          {recomendados.map((d, i) => (
            <span key={i} data-testid={`doc-recomendado-${i}`} style={{ fontSize: 10.5, fontWeight: 700, padding: "2px 8px",
              background: "rgba(212,175,55,0.1)", border: "1px solid rgba(212,175,55,0.4)", color: "#e7cf7a" }}>{d}</span>
          ))}
        </div>
      )}
      {formatos.length > 0 && (
        <div data-testid="docs-formato" style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <span style={{ fontSize: 11, fontWeight: 800, color: "#fb923c", letterSpacing: 1 }}>FORMATO:</span>
          {formatos.map((d, i) => (
            <span key={i} data-testid={`doc-formato-${i}`} style={{ fontSize: 10.5, fontWeight: 700, padding: "2px 8px",
              background: "rgba(234,88,12,0.1)", border: "1px solid rgba(234,88,12,0.4)", color: "#fb923c" }}>{d}</span>
          ))}
        </div>
      )}
      {msg && <div data-testid="panel-estado-msg" style={{ marginTop: 6, fontSize: 12, fontWeight: 700,
        color: msg.startsWith("✅") ? "#10d98e" : "#fb7185" }}>{msg}</div>}
    </div>
  );
}
