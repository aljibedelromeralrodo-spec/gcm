import { useState, useEffect } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const card = { background: "rgba(30,41,59,0.55)", border: "1px solid rgba(212,175,55,0.3)", borderRadius: 12, padding: "1.2rem", maxWidth: 560 };
const inp = { width: "100%", background: "rgba(255,255,255,0.06)", border: "1px solid rgba(212,175,55,0.3)", color: "#fff", padding: "0.55rem 0.7rem", borderRadius: 8, fontSize: "0.8rem", boxSizing: "border-box", marginBottom: 10 };

export default function MiCorreoModule() {
  const [estado, setEstado] = useState(null);
  const [form, setForm] = useState({ email: "", app_password: "", imap_host: "imap.gmail.com", smtp_host: "smtp.gmail.com" });
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const cargar = () => axios.get(`${API}/api/mi-correo`).then(r => setEstado(r.data)).catch(() => setEstado({ configurado: false }));
  useEffect(() => { cargar(); }, []);

  const guardar = async () => {
    setBusy(true); setMsg("");
    try {
      const r = await axios.post(`${API}/api/mi-correo/configurar`, form);
      setMsg(`✅ ${r.data.nota}`);
      setForm({ ...form, app_password: "" });
      cargar();
    } catch (e) { setMsg(`${e.response?.data?.detail || "⛔ Error de conexión"}`); }
    setBusy(false);
  };

  return (
    <div className="module-content" data-testid="micorreo-module">
      <h3 style={{ margin: "0 0 4px", color: "var(--text-primary)", fontSize: "1.05rem" }}>
        <i className="fa fa-envelope" style={{ marginRight: 8, color: "var(--gold)" }} />Configuración Inicial de Correo
      </h3>
      <p style={{ color: "var(--text-secondary)", fontSize: "0.72rem", margin: "0 0 14px", lineHeight: 1.6 }}>
        Regla de Oro #38 — Cada ejecutivo es responsable de la salud técnica de su buzón. Su clave de aplicación
        se valida en vivo y se guarda con cifrado <b>AES-256</b>. Solo usted y Gerardo (PIN maestro) pueden acceder a ella.
      </p>
      {estado?.configurado && (
        <div data-testid="micorreo-estado" style={{ ...card, marginBottom: 14, borderColor: estado.estado === "ok" ? "#22c55e" : "#f59e0b" }}>
          <b style={{ color: estado.estado === "ok" ? "#22c55e" : "#f59e0b", fontSize: "0.8rem" }}>
            {estado.estado === "ok" ? "✅ Conexión de correo saludable" : "⚠️ Su conexión de correo necesita actualización"}
          </b>
          <div style={{ color: "#94a3b8", fontSize: "0.7rem", marginTop: 6 }}>
            {estado.email} · IMAP {estado.imap_host} · Última lectura: {(estado.ultima_lectura || "—").slice(0, 16).replace("T", " ")}
          </div>
        </div>
      )}
      <div style={card} data-testid="micorreo-form">
        <label style={{ color: "#e2e8f0", fontSize: "0.7rem", fontWeight: 700 }}>Correo electrónico</label>
        <input data-testid="micorreo-email" style={inp} placeholder="su.correo@gmail.com" value={form.email}
          onChange={e => setForm({ ...form, email: e.target.value })} />
        <label style={{ color: "#e2e8f0", fontSize: "0.7rem", fontWeight: 700 }}>Clave de aplicación</label>
        <input data-testid="micorreo-password" type="password" style={inp} placeholder="Clave de aplicación (no su clave normal)"
          value={form.app_password} onChange={e => setForm({ ...form, app_password: e.target.value })} />
        <div style={{ display: "flex", gap: 8 }}>
          <div style={{ flex: 1 }}>
            <label style={{ color: "#e2e8f0", fontSize: "0.7rem", fontWeight: 700 }}>Servidor IMAP</label>
            <input data-testid="micorreo-imap" style={inp} value={form.imap_host} onChange={e => setForm({ ...form, imap_host: e.target.value })} />
          </div>
          <div style={{ flex: 1 }}>
            <label style={{ color: "#e2e8f0", fontSize: "0.7rem", fontWeight: 700 }}>Servidor SMTP</label>
            <input data-testid="micorreo-smtp" style={inp} value={form.smtp_host} onChange={e => setForm({ ...form, smtp_host: e.target.value })} />
          </div>
        </div>
        <button data-testid="micorreo-guardar" onClick={guardar} disabled={busy || !form.email || !form.app_password}
          style={{ background: "linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C)", color: "#0a0a0a", border: "none", borderRadius: 8, padding: "0.6rem 1.2rem", fontWeight: 800, cursor: "pointer", fontSize: "0.78rem" }}>
          {busy ? "Validando conexión…" : "Validar y guardar (AES-256)"}
        </button>
        {msg && <p data-testid="micorreo-msg" style={{ color: msg.startsWith("✅") ? "#22c55e" : "#f59e0b", fontSize: "0.72rem", marginTop: 10 }}>{msg}</p>}
      </div>
    </div>
  );
}
