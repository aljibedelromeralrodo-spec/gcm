import { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

const INACTIVIDAD_MS = 5 * 60 * 1000;

function HeliceProtector() {
  const canvasRef = useRef(null);
  const logoRef = useRef(null);
  useEffect(() => {
    const cv = canvasRef.current;
    const ctx = cv.getContext("2d");
    let raf;
    const start = performance.now();
    const W = (cv.width = window.innerWidth);
    const H = (cv.height = window.innerHeight);
    const cy = H / 2;
    const xIzq = W * 0.08, xDer = W * 0.92;
    const N = 60;                       // nodos por hebra (estilo poligonal)
    const amp = Math.min(170, H * 0.21);
    const FILL_MS = 16000, HOLD_MS = 3000;
    const MORADO = ["#7c3aed", "#5b6cf0", "#3b82f6"];
    const ORO = ["#8a6d1a", "#b8860b", "#BF953F", "#d4af37"];

    const draw = (now) => {
      const t = now - start;
      const ciclo = t % (FILL_MS + HOLD_MS);
      const fill = Math.min(1, ciclo / FILL_MS);   // 0→1: el dorado conquista de izquierda a derecha
      const rot = t * 0.0009;
      const xFrontera = xIzq + (xDer - xIzq) * fill;
      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, W, H);

      const nodo = (i, desfase) => {
        const x = xIzq + ((xDer - xIzq) * i) / (N - 1);
        const ph = i * 0.42 + rot + desfase;
        return { x, y: cy + Math.sin(ph) * amp, prof: (Math.cos(ph) + 1) / 2 };
      };
      const colorDe = (x, prof, dorado) => {
        const pal = dorado ? ORO : MORADO;
        const c = pal[Math.floor(prof * (pal.length - 1))];
        const cerca = Math.abs(x - xFrontera) < (xDer - xIzq) * 0.035;
        return { c: cerca && dorado ? "#FCF6BA" : c, a: 0.3 + 0.65 * prof };
      };

      for (const desfase of [0, Math.PI]) {
        // hebra poligonal: segmentos rectos entre nodos
        for (let i = 0; i < N - 1; i++) {
          const a = nodo(i, desfase), b = nodo(i + 1, desfase);
          const dor = a.x <= xFrontera;
          const { c, a: al } = colorDe(a.x, (a.prof + b.prof) / 2, dor);
          ctx.globalAlpha = al * 0.85;
          ctx.strokeStyle = c;
          ctx.lineWidth = 1.6 + 1.8 * a.prof;
          ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
        }
        // vértices: rombos geométricos (low-poly)
        for (let i = 0; i < N; i++) {
          const p = nodo(i, desfase);
          const dor = p.x <= xFrontera;
          const { c, a: al } = colorDe(p.x, p.prof, dor);
          const r = 3 + 4.5 * p.prof;
          ctx.globalAlpha = al;
          ctx.fillStyle = c;
          ctx.beginPath();
          ctx.moveTo(p.x, p.y - r); ctx.lineTo(p.x + r, p.y);
          ctx.lineTo(p.x, p.y + r); ctx.lineTo(p.x - r, p.y);
          ctx.closePath(); ctx.fill();
        }
      }
      // peldaños rectos entre hebras
      for (let i = 0; i < N; i += 3) {
        const a = nodo(i, 0), b = nodo(i, Math.PI);
        const dor = a.x <= xFrontera;
        ctx.globalAlpha = 0.16 + 0.2 * Math.min(a.prof, b.prof);
        ctx.strokeStyle = dor ? "#b8860b" : "#5b6cf0";
        ctx.lineWidth = 1.2;
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      }
      ctx.globalAlpha = 1;
      // el logo emerge en el centro a medida que el dorado conquista la hélice
      if (logoRef.current) {
        logoRef.current.style.opacity = Math.max(0, Math.min(1, (fill - 0.3) / 0.35));
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, []);
  const logoSize = Math.min(Math.floor(window.innerHeight * 0.3), 250);
  return (
    <>
      <style>{`@keyframes cm-logo-giro { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
      <canvas ref={canvasRef} style={{ display: "block", position: "absolute", inset: 0 }} />
      <img ref={logoRef} src="/logo-circular-oficial.png" alt="Central Mutuos" data-testid="protector-logo"
        style={{ position: "absolute", top: "50%", left: "50%", width: logoSize, height: logoSize,
          marginTop: -logoSize / 2, marginLeft: -logoSize / 2, borderRadius: "50%", opacity: 0,
          animation: "cm-logo-giro 26s linear infinite",
          boxShadow: "0 0 60px -12px rgba(212,175,55,0.55)" }} />
    </>
  );
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
