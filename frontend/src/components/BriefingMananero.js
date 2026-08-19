import { useState, useEffect } from "react";
import axios from "axios";
import { secureGet, secureSet } from "../utils/secureStore";

const API = process.env.REACT_APP_BACKEND_URL;

export default function BriefingMananero({ user }) {
  const [data, setData] = useState(null);
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState("");
  const hoy = new Date().toISOString().slice(0, 10);
  const clave = `briefing_${user?.codigo || user?.nombre || "u"}`;

  useEffect(() => {
    const v = secureGet(clave, false);
    if (v === hoy || v === JSON.stringify(hoy)) return;
    let cancelado = false;
    axios.get(`${API}/api/correos/briefing`).then(r => {
      const v2 = secureGet(clave, false);
      if (!cancelado && v2 !== hoy && v2 !== JSON.stringify(hoy)) { setData(r.data); setVisible(true); }
    }).catch(() => {});
    return () => { cancelado = true; };
  }, [clave, hoy]);

  const cerrar = () => { secureSet(clave, hoy); setVisible(false); };
  const reenviar = async (id) => {
    setBusy(id);
    try {
      await axios.post(`${API}/api/correos/fallidos/${id}/reintentar`);
      const r = await axios.get(`${API}/api/correos/briefing`);
      setData(r.data);
    } catch (e) { window.alert(e.response?.data?.detail || "El servidor volvió a rechazar el envío"); }
    setBusy("");
  };

  if (!visible || !data) return null;
  const pend = data.fallidos_pendientes || [];
  return (
    <div data-testid="briefing-mananero" style={{ position: "fixed", inset: 0, zIndex: 300,
      background: "rgba(2,6,23,0.82)", backdropFilter: "blur(10px)",
      display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem" }}>
      <div style={{ width: "100%", maxWidth: 620, maxHeight: "84vh", overflowY: "auto",
        background: "rgba(15,23,42,0.97)", borderRadius: 18, padding: "1.6rem 1.8rem",
        boxShadow: "0 30px 80px rgba(0,0,0,0.6)" }}>
        <h3 style={{ margin: 0, color: "#d4af37", fontSize: "1rem" }}>☀️ Briefing Mañanero — {data.dia}</h3>
        <p style={{ color: "#94a3b8", fontSize: "0.68rem", marginTop: 4 }}>
          Regla de Oro #62: es obligación de cada ejecutivo limpiar su lista de envíos fallidos al inicio de su jornada.
        </p>
        <div style={{ marginTop: 12 }}>
          <b style={{ color: "#22c55e", fontSize: "0.74rem" }}>✅ Envíos exitosos de ayer ({(data.exitosos || []).length})</b>
          {(data.exitosos || []).length === 0 && <p style={{ color: "#64748b", fontSize: "0.64rem" }}>Sin envíos ayer.</p>}
          {(data.exitosos || []).slice(0, 15).map((e, i) => (
            <div key={i} style={{ fontSize: "0.64rem", color: "#cbd5e1", padding: "0.2rem 0" }}>
              {(e.fecha || "").slice(11, 16)} · {e.subject} <span style={{ color: "#64748b" }}>→ {e.to}</span>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 14 }}>
          <b style={{ color: pend.length ? "#ef4444" : "#22c55e", fontSize: "0.74rem" }}>
            {pend.length ? `🔴 Envíos fallidos pendientes (${pend.length})` : "🟢 Sin envíos fallidos pendientes"}
          </b>
          {pend.map(f => (
            <div key={f.id} data-testid={`briefing-fallido-${f.id}`} style={{ padding: "0.45rem 0", borderBottom: "1px solid rgba(148,163,184,0.1)" }}>
              <div style={{ color: "#f8fafc", fontSize: "0.66rem", fontWeight: 700 }}>{f.subject}</div>
              <div style={{ color: "#94a3b8", fontSize: "0.6rem" }}>→ {f.to} · {(f.fecha || "").slice(0, 16).replace("T", " ")}</div>
              <button data-testid={`briefing-reenviar-${f.id}`} disabled={busy === f.id} onClick={() => reenviar(f.id)}
                style={{ marginTop: 4, cursor: "pointer", borderRadius: 8, border: "none", fontWeight: 800,
                  fontSize: "0.62rem", padding: "0.25rem 0.7rem",
                  background: "linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C)", color: "#0a0a0a" }}>
                {busy === f.id ? "Enviando…" : "♻️ Re-enviar"}
              </button>
            </div>
          ))}
        </div>
        <button data-testid="briefing-comenzar" onClick={cerrar}
          style={{ marginTop: 18, width: "100%", cursor: "pointer", border: "none", borderRadius: 12,
            padding: "0.7rem", fontWeight: 800, fontSize: "0.8rem",
            background: "linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C)", color: "#0a0a0a" }}>
          ✅ Comenzar jornada
        </button>
      </div>
    </div>
  );
}
