import { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";
import VisualizadorCognitivo from "./VisualizadorCognitivo";

const INACTIVIDAD_MS = 5 * 60 * 1000;

export default function ProtectorPantalla({ user }) {
  const [activo, setActivo] = useState(false);
  const [showPin, setShowPin] = useState(false);
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [verificando, setVerificando] = useState(false);
  const timerRef = useRef(null);
  const activoRef = useRef(false);
  const esAdmin = user && ["admin", "maestro"].includes(user.rol);

  const armar = useCallback(() => {
    if (activoRef.current) return;
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      activoRef.current = true;
      setActivo(true);
      setShowPin(false); setPin(""); setError("");
    }, INACTIVIDAD_MS);
  }, []);

  useEffect(() => {
    if (!esAdmin) return;
    const evs = ["mousemove", "mousedown", "keydown", "scroll", "touchstart", "wheel"];
    evs.forEach(e => window.addEventListener(e, armar, { passive: true }));
    armar();
    return () => {
      evs.forEach(e => window.removeEventListener(e, armar));
      clearTimeout(timerRef.current);
    };
  }, [esAdmin, armar]);

  useEffect(() => {
    if (!esAdmin) return;
    const forzar = () => { activoRef.current = true; setActivo(true); setShowPin(false); setPin(""); setError(""); };
    window.addEventListener("protector-forzar", forzar);
    return () => window.removeEventListener("protector-forzar", forzar);
  }, [esAdmin]);

  // El campo de PIN aparece SOLO al presionar cualquier tecla
  useEffect(() => {
    if (!activo) return;
    const fn = () => setShowPin(true);
    window.addEventListener("keydown", fn);
    return () => window.removeEventListener("keydown", fn);
  }, [activo]);

  if (!esAdmin || !activo) return null;

  const desbloquear = async (e) => {
    e.preventDefault();
    if (!pin.trim() || verificando) return;
    setVerificando(true); setError("");
    try {
      await axios.post(`${API_URL}/api/seguridad/verificar-pin-maestro`, { pin: pin.trim() });
      activoRef.current = false;
      setActivo(false);
      setPin("");
      armar();
    } catch (err) {
      setError(err.response?.data?.detail || "PIN maestro incorrecto");
      setPin("");
    }
    setVerificando(false);
  };

  return (
    <div data-testid="protector-pantalla" style={{ position: "fixed", inset: 0, zIndex: 100000, background: "#000" }}>
      <VisualizadorCognitivo modo="pantalla" />
      <div style={{ position: "absolute", top: "4%", left: 0, right: 0, textAlign: "center", pointerEvents: "none" }}>
        <div style={{ color: "#8a7a3a", fontSize: "0.6rem", fontFamily: "monospace", letterSpacing: 4 }}>
          SISTEMA PROTEGIDO · VISUALIZADOR COGNITIVO EN VIVO · SESIÓN DE ADMINISTRADOR EN PAUSA</div>
      </div>
      {!showPin && (
        <div data-testid="protector-hint" style={{ position: "absolute", bottom: "5%", left: 0, right: 0,
          textAlign: "center", color: "#6a6046", fontSize: "0.62rem", fontFamily: "monospace",
          letterSpacing: 3, pointerEvents: "none" }}>
          PRESIONE CUALQUIER TECLA PARA DESBLOQUEAR
        </div>
      )}
      {showPin && (
        <form onSubmit={desbloquear} style={{ position: "absolute", bottom: "8%", left: 0, right: 0,
          display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
          <label style={{ color: "#b8860b", fontSize: "0.66rem", fontFamily: "monospace", letterSpacing: 3 }}>
            <i className="fa fa-lock" style={{ marginRight: 6 }} />INGRESE SU PIN MAESTRO PARA VOLVER AL SISTEMA
          </label>
          <div style={{ display: "flex", gap: 8 }}>
            <input data-testid="protector-pin-input" type="password" value={pin} autoFocus
              onChange={e => setPin(e.target.value)} maxLength={12} placeholder="PIN Maestro"
              style={{ background: "rgba(14,14,16,0.9)", border: "1px solid rgba(212,175,55,0.5)",
                color: "#FCF6BA", padding: "0.6rem 1rem", fontSize: "1rem", letterSpacing: 6,
                textAlign: "center", width: 190, outline: "none", fontFamily: "monospace" }} />
            <button data-testid="protector-pin-submit" type="submit" disabled={verificando}
              style={{ background: "linear-gradient(135deg,#8a6d1a,#b8860b)", color: "#000", border: "none",
                padding: "0.6rem 1.3rem", fontWeight: 900, cursor: "pointer", letterSpacing: 1 }}>
              {verificando ? <i className="fa fa-spinner fa-spin" /> : "DESBLOQUEAR"}
            </button>
          </div>
          {error && <div data-testid="protector-pin-error" style={{ color: "#fb7185", fontSize: "0.72rem",
            fontFamily: "monospace", letterSpacing: 1 }}>🚨 {error}</div>}
        </form>
      )}
    </div>
  );
}
