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
    const cx = W / 2;
    const yTop = H * 0.1, yBot = H * 0.6;
    const N = 40;
    const amp = Math.min(110, W * 0.07);
    const FILL_MS = 16000, HOLD_MS = 3000;
    const AZUL = ["#3b6cf6", "#5b8cff", "#7dd3fc"];
    const ORO = ["#8a6d1a", "#b8860b", "#d4af37", "#FCF6BA"];
    // destellos fijos alrededor de la hélice (como en la referencia)
    const chispas = Array.from({ length: 46 }, () => ({
      x: cx + (Math.random() - 0.5) * amp * 6,
      y: yTop - 30 + Math.random() * (yBot - yTop + 80),
      r: 0.6 + Math.random() * 1.8, f: 1 + Math.random() * 3, d: Math.random() * 10,
    }));

    const draw = (now) => {
      const t = now - start;
      const ciclo = t % (FILL_MS + HOLD_MS);
      const fill = Math.min(1, ciclo / FILL_MS);   // el dorado conquista de abajo hacia arriba
      const rot = t * 0.0011;
      const yFrontera = yBot - (yBot - yTop) * fill;
      // fondo azul profundo con luz superior (como la foto)
      const g = ctx.createLinearGradient(0, 0, W * 0.2, H);
      g.addColorStop(0, "#101d52");
      g.addColorStop(0.45, "#0a1238");
      g.addColorStop(1, "#04081d");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, W, H);
      const luz = ctx.createRadialGradient(cx, yTop - 40, 0, cx, yTop - 40, H * 0.5);
      luz.addColorStop(0, "rgba(120,160,255,0.14)");
      luz.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = luz;
      ctx.fillRect(0, 0, W, H);

      const nodo = (i, desfase) => {
        const y = yTop + ((yBot - yTop) * i) / (N - 1);
        const ph = i * 0.5 + rot + desfase;
        return { x: cx + Math.sin(ph) * amp, y, prof: (Math.cos(ph) + 1) / 2 };
      };
      const colorDe = (y, prof, dorado) => {
        const pal = dorado ? ORO : AZUL;
        const c = pal[Math.floor(prof * (pal.length - 1))];
        const cerca = Math.abs(y - yFrontera) < (yBot - yTop) * 0.05;
        return { c: cerca && dorado ? "#FCF6BA" : c, a: 0.35 + 0.6 * prof };
      };

      for (const desfase of [0, Math.PI]) {
        for (let i = 0; i < N - 1; i++) {
          const a = nodo(i, desfase), b = nodo(i + 1, desfase);
          const dor = a.y >= yFrontera;
          const { c, a: al } = colorDe(a.y, (a.prof + b.prof) / 2, dor);
          ctx.globalAlpha = al * 0.9;
          ctx.strokeStyle = c;
          ctx.lineWidth = 1.2 + 1.6 * a.prof;
          ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
        }
        for (let i = 0; i < N; i++) {
          const p = nodo(i, desfase);
          const dor = p.y >= yFrontera;
          const { c, a: al } = colorDe(p.y, p.prof, dor);
          ctx.globalAlpha = al;
          ctx.shadowColor = c; ctx.shadowBlur = 9;
          ctx.fillStyle = c;
          const r = 2 + 3.4 * p.prof;
          ctx.beginPath();
          ctx.moveTo(p.x, p.y - r); ctx.lineTo(p.x + r, p.y);
          ctx.lineTo(p.x, p.y + r); ctx.lineTo(p.x - r, p.y);
          ctx.closePath(); ctx.fill();
          ctx.shadowBlur = 0;
        }
      }
      // peldaños entre hebras
      for (let i = 0; i < N; i += 2) {
        const a = nodo(i, 0), b = nodo(i, Math.PI);
        const dor = a.y >= yFrontera;
        ctx.globalAlpha = 0.18 + 0.22 * Math.min(a.prof, b.prof);
        ctx.strokeStyle = dor ? "#d4af37" : "#5b8cff";
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      }
      // destellos titilantes
      for (const s of chispas) {
        const tw = (Math.sin(t * 0.001 * s.f + s.d) + 1) / 2;
        const dor = s.y >= yFrontera;
        ctx.globalAlpha = 0.15 + 0.6 * tw;
        ctx.fillStyle = dor ? "#FCF6BA" : "#bfd7ff";
        ctx.beginPath(); ctx.arc(s.x, s.y, s.r * (0.7 + tw * 0.6), 0, Math.PI * 2); ctx.fill();
      }
      ctx.globalAlpha = 1;
      if (logoRef.current) {
        logoRef.current.style.opacity = Math.max(0, Math.min(1, (fill - 0.25) / 0.35));
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, []);
  const logoSize = Math.min(Math.floor(window.innerHeight * 0.22), 190);
  return (
    <>
      <style>{`@keyframes cm-logo-levita { 0% { transform: translateY(0); } 50% { transform: translateY(-16px); } 100% { transform: translateY(0); } }`}</style>
      <canvas ref={canvasRef} style={{ display: "block", position: "absolute", inset: 0 }} />
      <img ref={logoRef} src="/logo-circular-oficial.png" alt="Central Mutuos" data-testid="protector-logo"
        style={{ position: "absolute", top: "60%", left: "50%", width: logoSize, height: logoSize,
          marginLeft: -logoSize / 2, borderRadius: "50%", opacity: 0,
          animation: "cm-logo-levita 5s ease-in-out infinite",
          boxShadow: "0 0 70px -10px rgba(212,175,55,0.6)" }} />
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
