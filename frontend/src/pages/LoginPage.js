import { useState } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";
import { secureSet } from "../utils/secureStore";
import PrimerIngreso from "./PrimerIngreso";

export default function LoginPage({ onLogin }) {
  const [rut, setRut] = useState("");
  const [password, setPassword] = useState("");
  const [clave2, setClave2] = useState("");
  const [crearClave, setCrearClave] = useState(null); // {codigo, nombre}
  const [primerIngreso, setPrimerIngreso] = useState(null); // flujo obligatorio first_login
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const entrar = (data) => {
    secureSet("token", data.token);
    secureSet("user", data);
    onLogin(data);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await axios.post(`${API_URL}/api/auth/login`, { rut, password });
      if (res.data.requiere_crear_clave) {
        setCrearClave({ codigo: res.data.codigo, nombre: res.data.nombre });
        setPassword(""); setClave2("");
      } else if (res.data.first_login) {
        // PRIMER INGRESO OBLIGATORIO: no se permite acceso hasta completar la configuración
        secureSet("token", res.data.token);
        setPrimerIngreso(res.data);
      } else {
        entrar(res.data);
      }
    } catch {
      setError("Credenciales inválidas");
    }
    setLoading(false);
  };

  const handleCrearClave = async (e) => {
    e.preventDefault();
    setError("");
    if (password.length < 8) { setError("La clave debe tener al menos 8 caracteres"); return; }
    if (password !== clave2) { setError("Las claves no coinciden"); return; }
    setLoading(true);
    try {
      const res = await axios.post(`${API_URL}/api/auth/crear-clave`, { codigo: crearClave.codigo, clave: password });
      entrar(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "No se pudo crear la clave");
    }
    setLoading(false);
  };

  if (primerIngreso) return <PrimerIngreso data={primerIngreso} onDone={entrar} />;

  return (
    <div className="login-bg" data-testid="login-page">
      <div className="login-card">
        <div className="login-header">
          <div data-testid="login-logo" style={{ background: "#0a0a0a", borderRadius: 12,
            padding: "1.4rem 1rem 1.2rem", margin: "0 0 12px",
            border: "1px solid rgba(212,175,55,0.25)", textAlign: "center" }}>
            <div style={{ fontFamily: "'Playfair Display', serif", fontWeight: 700, fontSize: "2rem",
              letterSpacing: 4, whiteSpace: "nowrap",
              background: "linear-gradient(135deg,#BF953F,#FCF6BA,#B38728,#FBF5B7,#AA771C)",
              WebkitBackgroundClip: "text", backgroundClip: "text", WebkitTextFillColor: "transparent",
              filter: "drop-shadow(0 1px 12px rgba(191,149,63,0.55))" }}>CENTRAL MUTUOS</div>
            <div style={{ height: 1.5, margin: "12px auto 9px", width: "88%",
              background: "linear-gradient(90deg,transparent,#d4af37 20%,#d4af37 80%,transparent)" }} />
            <div style={{ fontFamily: "'Playfair Display', serif", color: "#d4af37",
              fontSize: "0.81rem", letterSpacing: 10, fontWeight: 400 }}>CON CRECES</div>
          </div>
        </div>
        {!crearClave ? (
          <form onSubmit={handleSubmit} className="login-form">
            <div>
              <label className="login-label">Código de Acceso</label>
              <input type="text" value={rut} onChange={(e) => setRut(e.target.value)} className="login-input" placeholder="Ingrese su código" data-testid="login-rut" required />
            </div>
            <div>
              <label className="login-label">Contraseña</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="login-input" placeholder="Ingrese su contraseña" data-testid="login-password" />
            </div>
            {error && <p className="login-error" data-testid="login-error">{error}</p>}
            <button type="submit" className="login-btn" disabled={loading} data-testid="login-submit">
              {loading ? "Verificando..." : "Ingresar"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleCrearClave} className="login-form" data-testid="crear-clave-form">
            <p style={{ fontSize: "0.8rem", color: "#d4af37", fontWeight: 700, margin: "0 0 0.6rem" }}>
              🔐 Primer ingreso de {crearClave.nombre}: cree su clave maestra personal. Nadie más la conocerá.
            </p>
            <div>
              <label className="login-label">Nueva clave (mín. 8 caracteres)</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="login-input" placeholder="Cree su clave" data-testid="crear-clave-1" autoFocus required />
            </div>
            <div>
              <label className="login-label">Repita la clave</label>
              <input type="password" value={clave2} onChange={(e) => setClave2(e.target.value)} className="login-input" placeholder="Confirme su clave" data-testid="crear-clave-2" required />
            </div>
            {error && <p className="login-error" data-testid="login-error">{error}</p>}
            <button type="submit" className="login-btn" disabled={loading} data-testid="crear-clave-submit">
              {loading ? "Creando..." : "Crear clave y entrar"}
            </button>
          </form>
        )}
        <p className="login-footer">Central Mutuos · Con Creces</p>
      </div>
    </div>
  );
}
