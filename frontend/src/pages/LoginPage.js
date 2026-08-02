import { useState } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

export default function LoginPage({ onLogin }) {
  const [rut, setRut] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await axios.post(`${API_URL}/api/auth/login`, { rut, password });
      localStorage.setItem("token", res.data.token);
      localStorage.setItem("user", JSON.stringify(res.data));
      onLogin(res.data);
    } catch {
      setError("Credenciales inválidas");
    }
    setLoading(false);
  };

  return (
    <div className="login-bg" data-testid="login-page">
      <div className="login-card">
        <div className="login-header">
          <h1 className="login-title">Central Mutuos</h1>
          <p className="login-subtitle">Plataforma de Gestión Crediticia</p>
        </div>
        <form onSubmit={handleSubmit} className="login-form">
          <div>
            <label className="login-label">Código de Acceso</label>
            <input type="text" value={rut} onChange={(e) => setRut(e.target.value)} className="login-input" placeholder="Ingrese su código" data-testid="login-rut" required />
          </div>
          <div>
            <label className="login-label">Contraseña</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="login-input" placeholder="Ingrese su contraseña" data-testid="login-password" required />
          </div>
          {error && <p className="login-error" data-testid="login-error">{error}</p>}
          <button type="submit" className="login-btn" disabled={loading} data-testid="login-submit">
            {loading ? "Verificando..." : "Ingresar"}
          </button>
        </form>
        <p className="login-footer">Con Creces</p>
      </div>
    </div>
  );
}
