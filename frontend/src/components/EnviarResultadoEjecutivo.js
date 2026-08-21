import { useState, useEffect } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const ORO = "#d4af37";

export default function EnviarResultadoEjecutivo({ folder }) {
  const [info, setInfo] = useState(null);
  const [show, setShow] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    setInfo(null); setMsg(""); setShow(false);
    if (!folder?.id) return;
    axios.get(`${API}/api/clientes/folders/${folder.id}/resultado-ejecutivo`)
      .then(r => setInfo(r.data)).catch(() => setInfo(null));
  }, [folder?.id]);

  if (!info?.resultado) return null;
  const aprobado = info.resultado === "aprobado";

  const enviar = async () => {
    setEnviando(true); setMsg("");
    try {
      const r = await axios.post(`${API}/api/clientes/folders/${folder.id}/enviar-resultado-ejecutivo`);
      setMsg(`✅ ${aprobado ? "Aprobación" : "Rechazo"} enviado a ${r.data.destinatarios.join(", ")}${r.data.adjuntos ? ` con ${r.data.adjuntos} adjunto(s)` : ""}`);
      setInfo(prev => ({ ...prev, ya_enviado_at: new Date().toISOString() }));
      setTimeout(() => setShow(false), 2500);
    } catch (e) { setMsg(`🚨 ${e.response?.data?.detail || "Error al enviar"}`); }
    setEnviando(false);
  };

  const pdfUrl = (a) => `${API}/api/aprobacion-cliente/preview-pdf?ruta=${encodeURIComponent(a.ruta)}&origen=${a.origen}&cliente=${encodeURIComponent(folder.nombre)}`;

  return (
    <>
      <button className="docs-btn secondary" data-testid={aprobado ? "btn-enviar-aprobacion-ejecutivo" : "btn-enviar-rechazo-ejecutivo"}
        onClick={() => { setMsg(""); setShow(true); }}
        title={info.ya_enviado_at ? `Ya enviado el ${String(info.ya_enviado_at).slice(0, 16).replace("T", " ")}` : ""}
        style={aprobado
          ? { background: "rgba(16,217,142,0.15)", border: "1px solid #10d98e", color: "#10d98e", fontWeight: 700 }
          : { background: "rgba(225,29,72,0.15)", border: "1px solid #e11d48", color: "#fb7185", fontWeight: 700 }}>
        <i className={`fa ${aprobado ? "fa-check-circle" : "fa-times-circle"}`}></i>{" "}
        {aprobado ? "Enviar Aprobación al Ejecutivo" : "Enviar Rechazo al Ejecutivo"}
        {info.ya_enviado_at ? " ✓" : ""}
      </button>

      {show && (
        <div data-testid="preview-resultado-ejecutivo" style={{ position: "fixed", inset: 0, zIndex: 500,
          background: "#050505", display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "0.9rem 1.4rem",
            borderBottom: `1px solid ${aprobado ? "rgba(16,217,142,0.4)" : "rgba(225,29,72,0.4)"}`, flexWrap: "wrap" }}>
            <b style={{ color: aprobado ? "#10d98e" : "#fb7185", fontSize: "1rem", letterSpacing: "0.05em" }}>
              {aprobado ? "📗 PREVIEW — APROBACIÓN AL EJECUTIVO" : "📕 PREVIEW — RECHAZO AL EJECUTIVO"}
            </b>
            <span style={{ color: "#94a3b8", fontSize: "0.78rem" }}>
              Para: <b style={{ color: ORO }}>{(info.destinatarios || []).join(", ") || "—"}</b> · Asunto: {info.asunto}
            </span>
            <button data-testid="preview-resultado-cerrar" onClick={() => setShow(false)}
              style={{ marginLeft: "auto", background: "transparent", border: "1px solid #64748b", color: "#94a3b8",
                padding: "0.3rem 0.9rem", cursor: "pointer", fontWeight: 700 }}>✕ Cerrar</button>
          </div>

          <div style={{ flex: 1, overflow: "auto", display: "grid", gap: 12, padding: "1rem 1.4rem",
            gridTemplateColumns: aprobado && (info.archivos || []).length ? `1fr ${Math.min((info.archivos || []).length, 2)}fr` : "1fr" }}>
            <div style={{ display: "flex", flexDirection: "column", minWidth: 320 }}>
              <div style={{ color: ORO, fontSize: "0.65rem", fontWeight: 800, letterSpacing: 2, marginBottom: 6 }}>1 · TEXTO DEL CORREO</div>
              <iframe title="correo" srcDoc={info.cuerpo_html} data-testid="preview-correo-iframe"
                style={{ flex: 1, minHeight: 420, border: "1px solid rgba(212,175,55,0.3)", background: "#fff", width: "100%" }} />
            </div>
            {aprobado && (info.archivos || []).map((a, i) => (
              <div key={i} style={{ display: "flex", flexDirection: "column", minWidth: 320 }}>
                <div style={{ color: ORO, fontSize: "0.65rem", fontWeight: 800, letterSpacing: 2, marginBottom: 6 }}>
                  {i + 2} · {a.tipo === "carta_aprobacion" ? "CARTA DE APROBACIÓN (PDF)" : "SIMULACIÓN SIN GASTOS OPERACIONALES (PDF)"}
                </div>
                <iframe title={a.nombre} src={pdfUrl(a)} data-testid={`preview-pdf-${a.tipo}`}
                  style={{ flex: 1, minHeight: 420, border: "1px solid rgba(212,175,55,0.3)", background: "#1a1a1a", width: "100%" }} />
              </div>
            ))}
            {aprobado && (info.archivos || []).length === 0 && (
              <div style={{ color: "#fb7185", fontSize: "0.85rem", padding: "1rem", border: "1px solid rgba(225,29,72,0.4)" }}>
                ⚠️ No se encontraron los PDF de aprobación guardados en la carpeta del cliente. Suba la carta de aprobación y la simulación antes de enviar.
              </div>
            )}
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "0.9rem 1.4rem",
            borderTop: "1px solid rgba(255,255,255,0.1)" }}>
            {msg && <span data-testid="resultado-envio-msg" style={{ fontSize: "0.82rem", fontWeight: 700,
              color: msg.startsWith("✅") ? "#10d98e" : "#fb7185" }}>{msg}</span>}
            <button data-testid="preview-resultado-cancelar" onClick={() => setShow(false)}
              style={{ marginLeft: "auto", background: "transparent", border: "1px solid #64748b", color: "#94a3b8",
                padding: "0.55rem 1.4rem", cursor: "pointer", fontWeight: 700 }}>Cancelar</button>
            <button data-testid="preview-resultado-confirmar" onClick={enviar}
              disabled={enviando || (aprobado && (info.archivos || []).length === 0)}
              style={{ background: aprobado ? "#10c98a" : "#e11d48", border: "none", color: "#fff",
                padding: "0.55rem 1.8rem", cursor: "pointer", fontWeight: 800,
                opacity: (enviando || (aprobado && (info.archivos || []).length === 0)) ? 0.5 : 1 }}>
              <i className={`fa ${enviando ? "fa-spinner fa-spin" : "fa-paper-plane"}`}></i>{" "}
              {enviando ? "Enviando…" : "Confirmar y Enviar"}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
