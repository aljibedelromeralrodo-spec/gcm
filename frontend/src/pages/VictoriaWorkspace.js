import { useState } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";
import VictoriaBoveda from "../components/VictoriaBoveda";
import ManualConcreces from "../components/ManualConcreces";

const inp = { width: "100%", background: "rgba(255,255,255,0.06)", border: "1px solid rgba(212,175,55,0.3)", color: "#fff", padding: "0.55rem 0.7rem", borderRadius: 8, fontSize: "0.8rem", boxSizing: "border-box" };
const lbl = { color: "#94a3b8", fontSize: "0.7rem", fontWeight: 700, display: "block", marginBottom: 4 };

function CambiarClave({ onClose, onChanged }) {
  const [f, setF] = useState({ actual: "", nueva: "", conf: "" });
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [loading, setLoading] = useState(false);

  const enviar = async (e) => {
    e.preventDefault();
    setError(""); setOk("");
    setLoading(true);
    try {
      await axios.post(`${API_URL}/api/auth/cambiar-clave`,
        { clave_actual: f.actual, clave_nueva: f.nueva, confirmacion: f.conf });
      setOk("Contraseña actualizada correctamente");
      onChanged();
      setTimeout(onClose, 1500);
    } catch (er) {
      const d = er.response?.data?.detail;
      setError(typeof d === "string" ? d : "No se pudo cambiar la contraseña");
    }
    setLoading(false);
  };

  return (
    <div data-testid="victoria-cambiar-clave-modal" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
      <div style={{ background: "#0f172a", border: "1px solid rgba(212,175,55,0.4)", borderRadius: 14, padding: "1.4rem", width: "100%", maxWidth: 400 }}>
        <h3 style={{ color: "#d4af37", margin: "0 0 4px", fontSize: "1rem" }}>🔐 Cambiar contraseña</h3>
        <p style={{ color: "#94a3b8", fontSize: "0.72rem", margin: "0 0 12px" }}>
          Mínimo 8 caracteres, al menos una mayúscula y un número.</p>
        <form onSubmit={enviar} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div><label style={lbl}>Contraseña actual</label>
            <input type="password" style={inp} value={f.actual} required autoFocus data-testid="vw-clave-actual"
              onChange={e => setF(s => ({ ...s, actual: e.target.value }))} /></div>
          <div><label style={lbl}>Nueva contraseña</label>
            <input type="password" style={inp} value={f.nueva} required data-testid="vw-clave-nueva"
              onChange={e => setF(s => ({ ...s, nueva: e.target.value }))} /></div>
          <div><label style={lbl}>Confirmar nueva contraseña</label>
            <input type="password" style={inp} value={f.conf} required data-testid="vw-clave-conf"
              onChange={e => setF(s => ({ ...s, conf: e.target.value }))} /></div>
          {error && <p data-testid="vw-clave-error" style={{ color: "#ef4444", fontSize: "0.74rem", margin: 0 }}>{error}</p>}
          {ok && <p data-testid="vw-clave-ok" style={{ color: "#22c55e", fontSize: "0.74rem", margin: 0 }}>{ok}</p>}
          <div style={{ display: "flex", gap: 8 }}>
            <button type="submit" disabled={loading} data-testid="vw-clave-submit"
              style={{ flex: 1, background: "linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C)", color: "#0a0a0a", border: "none", borderRadius: 8, padding: "0.55rem", fontWeight: 800, cursor: "pointer" }}>
              {loading ? "Guardando…" : "Guardar nueva contraseña"}</button>
            <button type="button" onClick={onClose} data-testid="vw-clave-cancelar"
              style={{ background: "rgba(255,255,255,0.08)", color: "#e2e8f0", border: "1px solid rgba(148,163,184,0.3)", borderRadius: 8, padding: "0.55rem 0.9rem", cursor: "pointer" }}>
              Cancelar</button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function VictoriaWorkspace({ user, onLogout, onUserUpdate }) {
  const [showClave, setShowClave] = useState(false);

  return (
    <div data-testid="victoria-workspace" style={{ minHeight: "100vh", background: "#0a0f1c", padding: "0 0 3rem" }}>
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10,
        padding: "0.9rem 1.4rem", background: "#0a0a0a", borderBottom: "1px solid rgba(212,175,55,0.35)", position: "sticky", top: 0, zIndex: 50 }}>
        <div>
          <div style={{ fontFamily: "'Playfair Display', serif", fontWeight: 700, fontSize: "1.15rem", letterSpacing: 3,
            background: "linear-gradient(135deg,#BF953F,#FCF6BA,#B38728)", WebkitBackgroundClip: "text",
            backgroundClip: "text", WebkitTextFillColor: "transparent" }}>CENTRAL MUTUOS</div>
          <div style={{ color: "#94a3b8", fontSize: "0.66rem", letterSpacing: 2 }}>MÓDULO VICTORIA · CON CRECES</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span data-testid="victoria-user-nombre" style={{ color: "#e2e8f0", fontSize: "0.78rem", fontWeight: 700 }}>
            👤 {user.nombre}</span>
          <button onClick={() => setShowClave(true)} data-testid="victoria-btn-perfil"
            style={{ background: "rgba(212,175,55,0.12)", color: "#d4af37", border: "1px solid rgba(212,175,55,0.4)",
              borderRadius: 8, padding: "0.4rem 0.8rem", fontSize: "0.72rem", fontWeight: 700, cursor: "pointer" }}>
            <i className="fa fa-key" style={{ marginRight: 5 }}></i>Cambiar contraseña</button>
          <button onClick={onLogout} data-testid="victoria-btn-salir"
            style={{ background: "rgba(239,68,68,0.12)", color: "#f87171", border: "1px solid rgba(239,68,68,0.4)",
              borderRadius: 8, padding: "0.4rem 0.8rem", fontSize: "0.72rem", fontWeight: 700, cursor: "pointer" }}>
            <i className="fa fa-sign-out" style={{ marginRight: 5 }}></i>Salir</button>
        </div>
      </header>

      {user.clave_temporal && (
        <div data-testid="victoria-banner-clave-temporal" style={{ margin: "14px 1.4rem 0", background: "rgba(245,158,11,0.1)",
          border: "1px solid rgba(245,158,11,0.5)", borderRadius: 10, padding: "0.7rem 1rem", color: "#fbbf24",
          fontSize: "0.76rem", fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
          <span>⚠️ Está usando una contraseña temporal. Por seguridad, cámbiela ahora.</span>
          <button onClick={() => setShowClave(true)} data-testid="victoria-banner-btn-cambiar"
            style={{ background: "#f59e0b", color: "#0a0a0a", border: "none", borderRadius: 8,
              padding: "0.35rem 0.9rem", fontWeight: 800, fontSize: "0.72rem", cursor: "pointer" }}>
            Cambiar ahora</button>
        </div>
      )}

      <main style={{ padding: "0 1.4rem" }}>
        <VictoriaBoveda />
        <ManualConcreces />
      </main>

      {showClave && <CambiarClave onClose={() => setShowClave(false)}
        onChanged={() => onUserUpdate({ ...user, clave_temporal: false })} />}
    </div>
  );
}
