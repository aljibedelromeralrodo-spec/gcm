import { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const ORO_MATE = "#b8860b";
const ORO_CLARO = "#d4af37";

const ESTADO_LB = { procesando: "PROCESANDO", activo: "ACTIVO", en_espera: "EN ESPERA" };

function fFecha(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    const p = (n) => String(n).padStart(2, "0");
    return `${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}`;
  } catch { return iso.slice(0, 16).replace("T", " "); }
}

function OverlayHelice({ est, onSalir }) {
  const canvasRef = useRef(null);
  useEffect(() => {
    const cv = canvasRef.current;
    const ctx = cv.getContext("2d");
    let raf;
    const start = performance.now();
    const W = (cv.width = window.innerWidth);
    const H = (cv.height = window.innerHeight);
    const cx = W / 2, cy = H / 2;
    const progreso = est ? Math.min(1, (est.procesados || 0) / Math.max(1, est.esperados || 1)) : 1;
    const BUILD = 8000;
    const paso = 9;
    const maxSeg = Math.ceil((W / 2 - 30) / paso);
    const amp = Math.min(150, H * 0.19);
    const draw = (now) => {
      const t = now - start;
      const build = Math.min(1, t / BUILD);
      const segVisibles = Math.floor(maxSeg * build * progreso);
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
          if (i % 4 === 0) {
            ctx.strokeStyle = `rgba(184,134,11,${0.14 + 0.14 * Math.min(prof1, prof2)})`;
            ctx.lineWidth = 1.4;
            ctx.beginPath(); ctx.moveTo(x, y1); ctx.lineTo(x, y2); ctx.stroke();
          }
          ctx.shadowColor = ORO_MATE; ctx.shadowBlur = 7;
          ctx.fillStyle = `rgba(200,160,40,${0.35 + 0.6 * prof1})`;
          ctx.beginPath(); ctx.arc(x, y1, 2.4 + 1.6 * prof1, 0, Math.PI * 2); ctx.fill();
          ctx.fillStyle = `rgba(184,134,11,${0.35 + 0.6 * prof2})`;
          ctx.beginPath(); ctx.arc(x, y2, 2.4 + 1.6 * prof2, 0, Math.PI * 2); ctx.fill();
          ctx.shadowBlur = 0;
        }
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    const salir = () => onSalir();
    window.addEventListener("keydown", salir);
    return () => { cancelAnimationFrame(raf); window.removeEventListener("keydown", salir); };
  }, [est, onSalir]);
  return (
    <div data-testid="helice-overlay" onClick={onSalir}
      style={{ position: "fixed", inset: 0, zIndex: 99999, background: "#000", cursor: "pointer" }}>
      <canvas ref={canvasRef} style={{ display: "block" }} />
      <div data-testid="helice-estado-pie" style={{ position: "absolute", bottom: 26, left: 0, right: 0,
        textAlign: "center", color: ORO_MATE, fontFamily: "monospace", fontSize: "0.78rem",
        letterSpacing: 2, opacity: 0.9 }}>
        {est ? (
          <>
            <span style={{ color: ORO_CLARO }}>{est.procesados}</span> BLOQUES DE DATOS PROCESADOS
            {" · "}ÚLTIMO PROCESAMIENTO: <span style={{ color: ORO_CLARO }}>{fFecha(est.ultimo_procesamiento)}</span>
            {" · "}ESTADO: <span style={{ color: est.estado === "procesando" ? "#FCF6BA" : ORO_CLARO }}>
              {ESTADO_LB[est.estado] || est.estado?.toUpperCase()}</span>
            {est.faltantes > 0 && <> · PENDIENTES: <span style={{ color: ORO_CLARO }}>{est.faltantes}</span></>}
          </>
        ) : "CARGANDO ESTADO DEL ALGORITMO…"}
        <div style={{ fontSize: "0.6rem", marginTop: 8, opacity: 0.55, letterSpacing: 3 }}>
          PRESIONE CUALQUIER TECLA O HAGA CLIC PARA VOLVER AL SISTEMA</div>
      </div>
    </div>
  );
}

export default function HeliceADN() {
  const [est, setEst] = useState(null);
  const [playing, setPlaying] = useState(false);
  const cargar = useCallback(() => {
    axios.get(`${API}/api/adn-helice/estado`).then(r => {
      setEst(r.data);
      // ACTIVACIÓN AUTOMÁTICA: cuando el algoritmo inicia procesamiento
      if (r.data.estado === "procesando" &&
        sessionStorage.getItem("helice_auto") !== r.data.ultimo_procesamiento) {
        sessionStorage.setItem("helice_auto", r.data.ultimo_procesamiento);
        setPlaying(true);
      }
    }).catch(() => {});
  }, []);
  useEffect(() => {
    cargar();
    const iv = setInterval(cargar, 60000);
    return () => clearInterval(iv);
  }, [cargar]);
  const salir = useCallback(() => setPlaying(false), []);
  return (
    <>
      <div data-testid="helice-panel" style={{ background: "#050505", border: "1px solid rgba(184,134,11,0.4)",
        borderRadius: 14, padding: "0.9rem 1.2rem", marginBottom: 14, display: "flex",
        alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <span style={{ fontSize: "1.4rem" }}>🧬</span>
        <div>
          <div style={{ color: ORO_CLARO, fontWeight: 900, fontSize: "0.78rem", letterSpacing: 1.5 }}>
            ADN DEL SISTEMA — VISUALIZACIÓN DEL ALGORITMO</div>
          <div style={{ color: "#8a7a3a", fontSize: "0.62rem", fontFamily: "monospace", marginTop: 2 }}>
            {est ? `${est.procesados} bloques procesados · ${est.faltantes} pendientes · último: ${fFecha(est.ultimo_procesamiento)} · estado: ${ESTADO_LB[est.estado] || "—"}` : "cargando estado…"}</div>
        </div>
        <button data-testid="btn-helice-reproducir" onClick={() => setPlaying(true)}
          style={{ marginLeft: "auto", background: "linear-gradient(135deg,#8a6d1a,#b8860b)",
            color: "#000", border: "none", borderRadius: 10, padding: "0.5rem 1.1rem",
            fontWeight: 900, cursor: "pointer", fontSize: "0.72rem", letterSpacing: 0.5 }}>
          ▶ Reproducir visualización</button>
      </div>
      {playing && <OverlayHelice est={est} onSalir={salir} />}
    </>
  );
}
