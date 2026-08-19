import { useState } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

const err2txt = (e, def) => {
  const d = e.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map(x => x?.msg || "").join(" ") || def;
  return def;
};

export default function PrimerIngreso({ data, onDone }) {
  const [paso, setPaso] = useState(1);
  const [f, setF] = useState({ actual: "", nueva: "", conf: "" });
  const [imap, setImap] = useState({ servidor: "imap.gmail.com", puerto: "993", email: data?.email || "", clave: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const paso1 = async (e) => {
    e.preventDefault();
    setError("");
    if (f.nueva !== f.conf) { setError("La nueva contraseña y su confirmación no coinciden"); return; }
    setLoading(true);
    try {
      await axios.post(`${API_URL}/api/auth/primer-ingreso/clave`,
        { clave_actual: f.actual, clave_nueva: f.nueva, confirmacion: f.conf });
      setPaso(2);
    } catch (er) { setError(err2txt(er, "No se pudo cambiar la contraseña")); }
    setLoading(false);
  };

  const paso2 = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const r = await axios.post(`${API_URL}/api/auth/primer-ingreso/imap`, imap);
      onDone(r.data);
    } catch (er) { setError(err2txt(er, "No se pudo guardar la configuración de correo")); }
    setLoading(false);
  };

  return (
    <div className="login-bg" data-testid="primer-ingreso-page">
      <div className="login-card" style={{ maxWidth: 460 }}>
        <div className="login-header">
          <h1 className="login-title">Central Mutuos</h1>
          <p className="login-subtitle">Configuración inicial obligatoria — {data?.nombre}</p>
        </div>
        <div style={{ display: "flex", gap: 8, margin: "0 0 14px" }}>
          {[1, 2].map(n => (
            <div key={n} data-testid={`primer-ingreso-paso-${n}`} style={{ flex: 1, textAlign: "center",
              borderRadius: 8, padding: "0.45rem", fontSize: "0.72rem", fontWeight: 800,
              background: paso === n ? "rgba(212,175,55,0.2)" : "rgba(255,255,255,0.05)",
              border: `1px solid ${paso >= n ? "#d4af37" : "rgba(255,255,255,0.15)"}`,
              color: paso >= n ? "#d4af37" : "#94a3b8" }}>
              {n === 1 ? "1 · Cambio de contraseña" : "2 · Cuenta de correo IMAP"}{paso > n ? " ✓" : ""}
            </div>
          ))}
        </div>
        {paso === 1 ? (
          <form onSubmit={paso1} className="login-form" data-testid="primer-ingreso-form-clave">
            <p style={{ fontSize: "0.76rem", color: "#94a3b8", margin: 0 }}>
              Debe cambiar su contraseña provisoria. La nueva debe tener mínimo 8 caracteres,
              al menos una mayúscula y un número. Este paso no se puede omitir.</p>
            <div>
              <label className="login-label">Contraseña provisoria</label>
              <input type="password" className="login-input" value={f.actual} required autoFocus
                data-testid="pi-clave-actual" onChange={e => setF(s => ({ ...s, actual: e.target.value }))} />
            </div>
            <div>
              <label className="login-label">Nueva contraseña</label>
              <input type="password" className="login-input" value={f.nueva} required
                data-testid="pi-clave-nueva" onChange={e => setF(s => ({ ...s, nueva: e.target.value }))} />
            </div>
            <div>
              <label className="login-label">Confirmar nueva contraseña</label>
              <input type="password" className="login-input" value={f.conf} required
                data-testid="pi-clave-conf" onChange={e => setF(s => ({ ...s, conf: e.target.value }))} />
            </div>
            {error && <p className="login-error" data-testid="pi-error">{error}</p>}
            <button type="submit" className="login-btn" disabled={loading} data-testid="pi-clave-submit">
              {loading ? "Guardando…" : "Cambiar contraseña →"}
            </button>
          </form>
        ) : (
          <form onSubmit={paso2} className="login-form" data-testid="primer-ingreso-form-imap">
            <p style={{ fontSize: "0.76rem", color: "#94a3b8", margin: 0 }}>
              Configure su cuenta de correo. El sistema la usará para leer su bandeja de entrada
              en los módulos que lo requieran. Se guarda de forma cifrada.</p>
            <div>
              <label className="login-label">Servidor IMAP</label>
              <input type="text" className="login-input" value={imap.servidor} required
                data-testid="pi-imap-servidor" onChange={e => setImap(s => ({ ...s, servidor: e.target.value }))} />
            </div>
            <div>
              <label className="login-label">Puerto</label>
              <input type="number" className="login-input" value={imap.puerto} required
                data-testid="pi-imap-puerto" onChange={e => setImap(s => ({ ...s, puerto: e.target.value }))} />
            </div>
            <div>
              <label className="login-label">Dirección de correo</label>
              <input type="email" className="login-input" value={imap.email} required
                data-testid="pi-imap-email" onChange={e => setImap(s => ({ ...s, email: e.target.value }))} />
            </div>
            <div>
              <label className="login-label">Contraseña de correo (clave de aplicación)</label>
              <input type="password" className="login-input" value={imap.clave} required
                data-testid="pi-imap-clave" onChange={e => setImap(s => ({ ...s, clave: e.target.value }))} />
            </div>
            {error && <p className="login-error" data-testid="pi-error">{error}</p>}
            <button type="submit" className="login-btn" disabled={loading} data-testid="pi-imap-submit">
              {loading ? "Guardando…" : "Finalizar configuración e ingresar"}
            </button>
          </form>
        )}
        <p className="login-footer">Central Mutuos · Con Creces</p>
      </div>
    </div>
  );
}
