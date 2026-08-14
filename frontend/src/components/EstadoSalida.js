import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

export const EstadoSalida = () => {
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  const cargar = useCallback(() => {
    axios.get(`${API}/api/correos/fallidos?horas=24`).then(r => setData(r.data)).catch(() => {});
  }, []);
  useEffect(() => { cargar(); const iv = setInterval(cargar, 60000); return () => clearInterval(iv); }, [cargar]);

  const reenviar = async (id) => {
    setBusy(id); setMsg("");
    try {
      await axios.post(`${API}/api/correos/fallidos/${id}/reintentar`);
      setMsg("✅ Re-enviado — salida confirmada por SMTP (Regla #62)");
      cargar();
    } catch (e) { setMsg(e.response?.data?.detail || "⛔ El servidor volvió a rechazar el envío"); }
    setBusy("");
  };

  const n = data?.total ?? 0;
  return (
    <div data-testid="estado-salida" style={{ position: "relative" }}>
      <button data-testid="estado-salida-btn" onClick={() => setOpen(!open)}
        style={{ cursor: "pointer", border: "none", borderRadius: 999, padding: "0.35rem 0.9rem",
          fontSize: "0.66rem", fontWeight: 800, letterSpacing: "0.06em",
          background: n > 0 ? "rgba(239,68,68,0.18)" : "rgba(34,197,94,0.14)",
          color: n > 0 ? "#ef4444" : "#22c55e" }}>
        {n > 0 ? `🔴 Estado de Salida: ${n} correo(s) FALLIDO(S) 24h` : "📮 Estado de Salida: OK"}
      </button>
      {open && (
        <div data-testid="estado-salida-lista" style={{ position: "absolute", zIndex: 60, top: "2.2rem", right: 0,
          minWidth: 340, maxWidth: 460, maxHeight: 320, overflowY: "auto",
          background: "rgba(15,23,42,0.97)", backdropFilter: "blur(16px)", borderRadius: 14,
          boxShadow: "0 18px 50px rgba(0,0,0,0.55)", padding: "0.8rem 1rem" }}>
          <b style={{ color: "#d4af37", fontSize: "0.7rem" }}>Regla de Oro #62 — Envíos fallidos últimas 24h</b>
          {msg && <div data-testid="estado-salida-msg" style={{ color: msg.startsWith("✅") ? "#22c55e" : "#ef4444", fontSize: "0.64rem", margin: "6px 0" }}>{msg}</div>}
          {n === 0 && <p style={{ color: "#94a3b8", fontSize: "0.66rem" }}>Sin fallos de envío. Todos los hitos confirmados por SMTP.</p>}
          {(data?.fallidos || []).map(f => (
            <div key={f.id} data-testid={`fallido-${f.id}`} style={{ padding: "0.5rem 0", borderBottom: "1px solid rgba(148,163,184,0.1)" }}>
              <div style={{ color: "#f8fafc", fontSize: "0.66rem", fontWeight: 700 }}>{f.subject}</div>
              <div style={{ color: "#94a3b8", fontSize: "0.6rem" }}>→ {f.to} · {(f.fecha || "").slice(0, 16).replace("T", " ")} · {(f.error || "").slice(0, 70)}</div>
              <button data-testid={`reenviar-${f.id}`} disabled={busy === f.id} onClick={() => reenviar(f.id)}
                style={{ marginTop: 4, cursor: "pointer", borderRadius: 8, border: "none", fontWeight: 800,
                  fontSize: "0.62rem", padding: "0.25rem 0.7rem",
                  background: "linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C)", color: "#0a0a0a" }}>
                {busy === f.id ? "Enviando…" : "♻️ Re-enviar"}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default EstadoSalida;
