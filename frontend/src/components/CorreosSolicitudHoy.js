import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const ORO = "#d4af37";

export default function CorreosSolicitudHoy() {
  const [data, setData] = useState(null);
  const [oculto, setOculto] = useState(false);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");

  const cargar = useCallback(() => {
    axios.get(`${API}/api/dashboard/correos-solicitud-hoy`)
      .then(r => setData(r.data))
      .catch(e => { if (e.response?.status === 403) setOculto(true); });
  }, []);

  useEffect(() => {
    cargar();
    const t = setInterval(cargar, 30000);
    return () => clearInterval(t);
  }, [cargar]);

  if (oculto || !data) return null;

  const accion = async (qid, tipo) => {
    if (tipo === "no-tomar" && !window.confirm("¿Marcar este correo como 'No Tomar en Cuenta'?")) return;
    setBusy(qid + tipo); setMsg("");
    try {
      const r = await axios.post(`${API}/api/dashboard/correos-solicitud-hoy/${qid}/${tipo}`);
      setMsg(tipo === "crear-carpeta"
        ? `✅ Carpeta creada: ${r.data.carpeta} (${r.data.archivos} archivo(s))`
        : "🚫 Correo marcado como no tomado en cuenta");
      cargar();
    } catch (e) { setMsg(`🚨 ${e.response?.data?.detail || "Error"}`); }
    setBusy("");
  };

  return (
    <div data-testid="widget-correos-solicitud-hoy" style={{ border: "1px solid rgba(212,175,55,0.35)",
      background: "linear-gradient(160deg, rgba(18,18,20,0.97), rgba(6,6,8,0.99))", padding: "1rem 1.3rem", marginBottom: "1rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: "0.7rem", flexWrap: "wrap" }}>
        <i className="fa fa-inbox" style={{ color: ORO }} />
        <b style={{ color: ORO, letterSpacing: "0.06em" }}>📨 Correos de Solicitud — Hoy ({data.fecha})</b>
        <span style={{ fontSize: "0.7rem", color: "#10d98e", fontWeight: 700 }}>
          <span style={{ display: "inline-block", width: 7, height: 7, borderRadius: "50%", background: "#10d98e",
            boxShadow: "0 0 8px rgba(16,217,142,0.8)", marginRight: 5 }} />EN VIVO · 30s
        </span>
        <span style={{ marginLeft: "auto", fontSize: "0.72rem", opacity: 0.6 }}>{data.total} correo(s) del día</span>
      </div>
      {msg && <div data-testid="widget-correos-msg" style={{ fontSize: "0.78rem", fontWeight: 700, marginBottom: 8,
        color: msg.startsWith("✅") ? "#10d98e" : msg.startsWith("🚫") ? "#e7cf7a" : "#fb7185" }}>{msg}</div>}
      {data.correos.length === 0 && (
        <p style={{ color: "#7a7a7a", fontSize: "0.78rem", margin: 0 }}>Sin correos entrantes con posibles solicitudes hoy.</p>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 340, overflow: "auto" }}>
        {data.correos.map(c => (
          <div key={c.id} data-testid={`correo-hoy-${c.id}`} style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap",
            padding: "0.55rem 0.8rem", background: c.estado === "descartado" ? "rgba(100,100,100,0.08)" : "rgba(212,175,55,0.05)",
            border: "1px solid rgba(212,175,55,0.2)", opacity: c.estado === "descartado" ? 0.5 : 1 }}>
            <span style={{ fontFamily: "monospace", fontSize: 11, color: ORO, fontWeight: 800 }}>{c.hora}</span>
            <div style={{ flex: 1, minWidth: 220 }}>
              <div style={{ color: "#e8e3d3", fontSize: 12.5, fontWeight: 700 }}>{c.asunto}</div>
              <div style={{ color: "#94a3b8", fontSize: 11 }}>{c.remitente}
                {c.adjuntos.length > 0 && <span style={{ marginLeft: 8 }}><i className="fa fa-paperclip" /> {c.adjuntos.length} adjunto(s)</span>}
              </div>
              {c.documentos_detectados.length > 0 && (
                <div style={{ marginTop: 3, display: "flex", gap: 4, flexWrap: "wrap" }}>
                  {c.documentos_detectados.map((d, i) => (
                    <span key={i} style={{ fontSize: 9.5, fontWeight: 700, padding: "1px 6px",
                      background: "rgba(16,217,142,0.12)", border: "1px solid rgba(16,217,142,0.35)", color: "#10d98e" }}>{d}</span>
                  ))}
                </div>
              )}
            </div>
            {c.estado === "carpeta_creada" ? (
              <span style={{ fontSize: 10.5, fontWeight: 800, color: "#10d98e", border: "1px solid rgba(16,217,142,0.4)", padding: "2px 8px" }}>✓ CARPETA CREADA</span>
            ) : c.estado === "descartado" ? (
              <span style={{ fontSize: 10.5, fontWeight: 800, color: "#94a3b8", border: "1px solid #64748b", padding: "2px 8px" }}>NO TOMADO EN CUENTA</span>
            ) : (
              <span style={{ display: "inline-flex", gap: 6 }}>
                <button data-testid={`btn-crear-carpeta-${c.id}`} disabled={!c.puede_crear || busy === c.id + "crear-carpeta"}
                  onClick={() => accion(c.id, "crear-carpeta")}
                  title={c.puede_crear ? "Crear la carpeta del cliente (Regla #67 verificada)" : "Documentación insuficiente"}
                  style={{ padding: "0.35rem 0.8rem", fontWeight: 800, fontSize: 11, cursor: c.puede_crear ? "pointer" : "not-allowed",
                    background: c.puede_crear ? "rgba(16,217,142,0.15)" : "rgba(100,100,100,0.1)",
                    border: c.puede_crear ? "1px solid #10d98e" : "1px solid #4a4a4a",
                    color: c.puede_crear ? "#10d98e" : "#6a6a6a" }}>
                  {busy === c.id + "crear-carpeta" ? <i className="fa fa-spinner fa-spin" /> : <i className="fa fa-folder-open" />}{" "}
                  {c.puede_crear ? "Crear Carpeta" : "Documentación insuficiente"}
                </button>
                <button data-testid={`btn-no-tomar-${c.id}`} disabled={busy === c.id + "no-tomar"}
                  onClick={() => accion(c.id, "no-tomar")}
                  style={{ padding: "0.35rem 0.8rem", fontWeight: 800, fontSize: 11, cursor: "pointer",
                    background: "rgba(225,29,72,0.1)", border: "1px solid rgba(225,29,72,0.4)", color: "#fb7185" }}>
                  <i className="fa fa-ban" /> No Tomar en Cuenta
                </button>
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
