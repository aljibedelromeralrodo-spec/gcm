import { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

const PALETA = ["#8a6d1a", "#b8860b", "#BF953F", "#d4af37", "#B38728", "#FCF6BA"];
const INACTIVIDAD_MS = 5 * 60 * 1000;

function HeliceProtector() {
  const canvasRef = useRef(null);
  useEffect(() => {
    const cv = canvasRef.current;
    const ctx = cv.getContext("2d");
    let raf;
    const start = performance.now();
    const W = (cv.width = window.innerWidth);
    const H = (cv.height = window.innerHeight);
    const cx = W / 2, cy = H / 2;
    const BUILD = 14000;
    const paso = 9;
    const maxSeg = Math.ceil((W / 2 - 30) / paso);
    const amp = Math.min(160, H * 0.2);
    const draw = (now) => {
      const t = now - start;
      const build = Math.min(1, (t % (BUILD + 4000)) / BUILD); // llenado progresivo en loop
      const segVisibles = Math.floor(maxSeg * build);
      const rot = t * 0.0011;
      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, W, H);
      for (let i = 0; i <= segVisibles; i++) {
        for (const lado of [-1, 1]) {
          if (i === 0 && lado === 1) continue;
          const x = cx + lado * i * paso;
          const ph = (x - cx) * 0.028 + rot;
          const y1 = cy + Math.sin(ph) * amp;
          const y2 = cy + Math.sin(ph + Math.PI) * amp;
          const prof1 = (Math.cos(ph) + 1) / 2;
          const prof2 = (Math.cos(ph + Math.PI) + 1) / 2;
          const c1 = PALETA[i % PALETA.length];
          const c2 = PALETA[(i + 3) % PALETA.length];
          if (i % 4 === 0) {
            ctx.strokeStyle = `rgba(184,134,11,${0.12 + 0.16 * Math.min(prof1, prof2)})`;
            ctx.lineWidth = 1.4;
            ctx.beginPath(); ctx.moveTo(x, y1); ctx.lineTo(x, y2); ctx.stroke();
          }
          ctx.shadowColor = "#b8860b"; ctx.shadowBlur = 7;
          ctx.globalAlpha = 0.35 + 0.6 * prof1;
          ctx.fillStyle = c1;
          ctx.beginPath(); ctx.arc(x, y1, 2.4 + 1.6 * prof1, 0, Math.PI * 2); ctx.fill();
          ctx.globalAlpha = 0.35 + 0.6 * prof2;
          ctx.fillStyle = c2;
          ctx.beginPath(); ctx.arc(x, y2, 2.4 + 1.6 * prof2, 0, Math.PI * 2); ctx.fill();
          ctx.globalAlpha = 1;
          ctx.shadowBlur = 0;
        }
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, []);
  return <canvas ref={canvasRef} style={{ display: "block", position: "absolute", inset: 0 }} />;
}

export default function ProtectorPantalla({ user }) {
  const [activo, setActivo] = useState(false);
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
      setPin(""); setError("");
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
    const forzar = () => { activoRef.current = true; setActivo(true); setPin(""); setError(""); };
    window.addEventListener("protector-forzar", forzar);
    return () => window.removeEventListener("protector-forzar", forzar);
  }, [esAdmin]);

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
      <HeliceProtector />
      <div style={{ position: "absolute", top: "8%", left: 0, right: 0, textAlign: "center" }}>
        <div style={{ fontFamily: "'Playfair Display', serif", fontSize: "1.3rem", letterSpacing: 6,
          background: "linear-gradient(135deg,#BF953F,#FCF6BA,#B38728,#FBF5B7,#AA771C)",
          WebkitBackgroundClip: "text", backgroundClip: "text", WebkitTextFillColor: "transparent" }}>
          Central Mutuos</div>
        <div style={{ color: "#8a7a3a", fontSize: "0.6rem", fontFamily: "monospace", letterSpacing: 4, marginTop: 6 }}>
          SISTEMA PROTEGIDO · SESIÓN DE ADMINISTRADOR EN PAUSA</div>
      </div>
      <form onSubmit={desbloquear} style={{ position: "absolute", bottom: "10%", left: 0, right: 0,
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
    </div>
  );
}
