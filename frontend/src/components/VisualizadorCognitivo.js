import { useState, useEffect, useRef } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

const ORO = "212,175,55", MORADO = "139,92,246", VERDE = "16,217,142", ROJO = "225,29,72";

const colorCarpeta = (c) => c.alerta || c.resultado === "reprobado" ? ROJO
  : c.resultado === "aprobado" ? VERDE : MORADO;

const hashStr = (s) => (s || "").split("").reduce((a, ch) => a + ch.charCodeAt(0) * 7, 0);
// disparo neuronal: cada nodo brilla solo, al azar — ataque breve, apagado lento
const disparo = (h, t) => {
  const p = 3.5 + (h % 50) / 10;
  const f = (t + ((h % 97) / 97) * p) % p;
  return f < 0.18 ? f / 0.18 : Math.max(0, 1 - (f - 0.18) / 2.4);
};

// Visualizador Cognitivo en Vivo: el sistema como cerebro con nodos y pulsos reales
export default function VisualizadorCognitivo({ modo = "panel" }) {
  const [datos, setDatos] = useState(null);
  const [expandido, setExpandido] = useState(false);
  const datosRef = useRef(null);
  const fxRef = useRef({ nacimientos: [], vibraciones: {}, conocidos: null, resultados: {} });
  const wrapRef = useRef(null);
  const canvasRef = useRef(null);
  const fullscreen = modo === "pantalla" || expandido;

  useEffect(() => {
    let vivo = true;
    const cargar = async () => {
      try {
        const r = await axios.get(`${API_URL}/api/visualizador/estado`);
        if (!vivo) return;
        const fx = fxRef.current, ahora = performance.now();
        if (fx.conocidos) {
          r.data.correos.forEach(c => { if (!fx.conocidos.has(c.key)) fx.nacimientos.push({ key: c.key, t: ahora }); });
          r.data.carpetas.forEach(c => {
            const prev = fx.resultados[c.id];
            if (prev !== undefined && prev !== c.resultado) fx.vibraciones[c.id] = ahora + 2600;
            else if (c.activo_reciente) fx.vibraciones[c.id] = Math.max(fx.vibraciones[c.id] || 0, ahora + 1600);
          });
        }
        fx.conocidos = new Set(r.data.correos.map(c => c.key));
        fx.resultados = Object.fromEntries(r.data.carpetas.map(c => [c.id, c.resultado]));
        datosRef.current = r.data;
        setDatos(r.data);
      } catch { if (vivo && modo === "panel") setDatos(d => d); }
    };
    cargar();
    const iv = setInterval(cargar, 8000);
    return () => { vivo = false; clearInterval(iv); };
  }, [modo]);

  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv) return;
    const ctx = cv.getContext("2d");
    let raf;
    const start = performance.now();

    const draw = (now) => {
      const wrap = wrapRef.current;
      if (!wrap) return;
      const W = (cv.width = wrap.clientWidth);
      const H = (cv.height = wrap.clientHeight);
      const t = (now - start) / 1000;
      const d = datosRef.current;
      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, W, H);
      if (!d) { raf = requestAnimationFrame(draw); return; }
      const fx = fxRef.current;
      const cx = W / 2, cy = H / 2, base = Math.min(W, H);
      const R1 = base * 0.21, R2 = base * 0.38, R3 = base * 0.47;
      const grande = fullscreen || base > 500;

      const posEj = (i, n) => {
        const a = (i / Math.max(n, 1)) * Math.PI * 2 - Math.PI / 2;
        return { x: cx + Math.cos(a) * R1 + Math.sin(t * 0.22 + i) * 6, y: cy + Math.sin(a) * R1 + Math.cos(t * 0.18 + i * 2) * 6 };
      };
      const posCa = (i, n, id) => {
        const h = hashStr(id);
        const a = (i / Math.max(n, 1)) * Math.PI * 2 + (h % 10) * 0.02;
        const r = R2 + (h % 5) * base * 0.015;
        let x = cx + Math.cos(a) * r + Math.sin(t * 0.25 + h) * 7, y = cy + Math.sin(a) * r + Math.cos(t * 0.2 + h) * 7;
        if ((fx.vibraciones[id] || 0) > now) { x += Math.sin(now * 0.09 + h) * 3.5; y += Math.cos(now * 0.11 + h) * 3.5; }
        return { x, y };
      };
      const posCo = (i, n) => {
        const a = (i / Math.max(n, 1)) * Math.PI * 2 + 0.35 + t * 0.008;
        return { x: cx + Math.cos(a) * R3 + Math.sin(t * 0.2 + i * 3) * 5, y: cy + Math.sin(a) * R3 + Math.cos(t * 0.24 + i * 2) * 5 };
      };

      const linea = (a, b, rgb, alpha, pulso, fase) => {
        ctx.globalAlpha = alpha;
        ctx.strokeStyle = `rgba(${rgb},1)`;
        ctx.lineWidth = pulso ? 1.4 : 0.7;
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
        if (pulso) {                                     // luz dorada viajando por la conexión
          const f = ((t * 0.45 + fase) % 1);
          const x = a.x + (b.x - a.x) * f, y = a.y + (b.y - a.y) * f;
          ctx.globalAlpha = 0.95;
          ctx.shadowColor = `rgb(${ORO})`; ctx.shadowBlur = 12;
          ctx.fillStyle = "#FCF6BA";
          ctx.beginPath(); ctx.arc(x, y, 2.4, 0, Math.PI * 2); ctx.fill();
          ctx.shadowBlur = 0;
        }
      };
      const nodo = (p, r, rgb, glow, label, labelCol, fuego = 0) => {
        if (fuego > 0.02) {                            // halo orgánico del disparo neuronal
          ctx.globalAlpha = 0.16 * fuego;
          ctx.fillStyle = `rgb(${rgb})`;
          ctx.beginPath(); ctx.arc(p.x, p.y, r + 4 + fuego * 13, 0, Math.PI * 2); ctx.fill();
        }
        ctx.globalAlpha = 0.55 + 0.45 * fuego;
        ctx.shadowColor = `rgb(${rgb})`; ctx.shadowBlur = glow + fuego * 22;
        ctx.fillStyle = `rgba(${rgb},0.95)`;
        ctx.beginPath(); ctx.arc(p.x, p.y, r * (1 + 0.3 * fuego), 0, Math.PI * 2); ctx.fill();
        ctx.shadowBlur = 0;
        if (label && grande) {
          ctx.globalAlpha = 1;
          ctx.font = "9px monospace"; ctx.textAlign = "center";
          ctx.fillStyle = labelCol || "rgba(200,190,160,0.75)";
          ctx.fillText(label, p.x, p.y + r + 11);
        }
      };

      const nE = d.ejecutivos.length, nC = d.carpetas.length, nM = d.correos.length;
      // conexiones ejecutivo→cerebro y carpeta→ejecutivo
      d.ejecutivos.forEach((e, i) => linea(posEj(i, nE), { x: cx, y: cy }, ORO, 0.35, true, i * 0.19));
      d.carpetas.forEach((c, i) => {
        const pe = nE ? posEj(i % nE, nE) : { x: cx, y: cy };
        const activo = c.activo_reciente || (fx.vibraciones[c.id] || 0) > now;
        linea(posCa(i, nC, c.id), pe, activo ? ORO : colorCarpeta(c), activo ? 0.5 : 0.14, activo, i * 0.13);
      });
      d.correos.forEach((c, i) => linea(posCo(i, nM), { x: cx, y: cy }, c.fallido ? ROJO : ORO,
        c.reciente ? 0.45 : 0.12, c.reciente, i * 0.23));

      // nodos correo (nacen al llegar)
      d.correos.forEach((c, i) => {
        const p = posCo(i, nM);
        nodo(p, 3.2, c.fallido ? ROJO : ORO, 4, c.cliente, undefined, disparo(hashStr(c.key), t));
        const nac = fx.nacimientos.find(n => n.key === c.key);
        if (nac) {
          const e = (now - nac.t) / 1500;
          if (e < 1) {
            ctx.globalAlpha = 1 - e;
            ctx.strokeStyle = `rgb(${ORO})`; ctx.lineWidth = 1.6;
            ctx.beginPath(); ctx.arc(p.x, p.y, 4 + e * 26, 0, Math.PI * 2); ctx.stroke();
          }
        }
      });
      fx.nacimientos = fx.nacimientos.filter(n => now - n.t < 1600);

      // nodos carpeta: morado espera · verde aprobado · rojo rechazo/alerta
      d.carpetas.forEach((c, i) => {
        const rgb = colorCarpeta(c);
        nodo(posCa(i, nC, c.id), 4.6, rgb, (fx.vibraciones[c.id] || 0) > now ? 16 : 5,
          c.nombre.split(" ")[0], `rgba(${rgb},0.8)`, disparo(hashStr(c.id), t));
      });
      // nodos ejecutivo
      d.ejecutivos.forEach((e, i) => nodo(posEj(i, nE), 6, ORO, 6, e.nombre.split(" ")[0],
        "rgba(231,207,122,0.85)", disparo(hashStr(e.codigo) + 31, t)));

      // CEREBRO NORMATIVO al centro, latiendo
      const rB = 13 + Math.sin(t * 2.2) * 2.5;
      ctx.globalAlpha = 0.25;
      ctx.fillStyle = `rgb(${ORO})`;
      ctx.beginPath(); ctx.arc(cx, cy, rB + 12 + Math.sin(t * 2.2) * 4, 0, Math.PI * 2); ctx.fill();
      nodo({ x: cx, y: cy }, rB, ORO, 26);
      ctx.globalAlpha = 1; ctx.textAlign = "center";
      ctx.font = "bold 10px monospace"; ctx.fillStyle = "#FCF6BA";
      ctx.fillText("CEREBRO NORMATIVO", cx, cy + rB + 18);
      ctx.font = "9px monospace"; ctx.fillStyle = "rgba(200,190,160,0.7)";
      ctx.fillText(`${d.cerebro.normativas} reglas · calibración ${d.cerebro.calibracion}%`, cx, cy + rB + 30);
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [fullscreen]);

  if (modo === "panel" && !datos) return null;

  const cuerpo = (
    <div ref={wrapRef} style={{ position: expandido ? "fixed" : modo === "pantalla" ? "absolute" : "relative",
      inset: fullscreen ? 0 : "auto", zIndex: expandido ? 90000 : "auto",
      height: expandido ? "100vh" : modo === "pantalla" ? "100%" : 360, background: "#000",
      border: fullscreen ? "none" : "1px solid rgba(212,175,55,0.3)" }}>
      <canvas ref={canvasRef} style={{ display: "block", position: "absolute", inset: 0 }} />
      <div style={{ position: "absolute", top: 10, left: 14, pointerEvents: "none" }}>
        <span style={{ color: "#e7cf7a", fontSize: "0.68rem", fontWeight: 800, letterSpacing: 2, fontFamily: "monospace" }}>
          🧠 VISUALIZADOR COGNITIVO EN VIVO</span>
        {datos && <span style={{ color: "#6a6046", fontSize: "0.6rem", fontFamily: "monospace", marginLeft: 10 }}>
          {datos.carpetas.length} carpetas · {datos.correos.length} correos · {datos.ejecutivos.length} ejecutivos</span>}
      </div>
      <div style={{ position: "absolute", bottom: 8, left: 14, display: "flex", gap: 12, pointerEvents: "none" }}>
        {[["ESPERA", MORADO], ["APROBADO", VERDE], ["RECHAZO/ALERTA", ROJO], ["ACTIVIDAD", ORO]].map(([l, c]) => (
          <span key={l} style={{ fontSize: "0.55rem", fontFamily: "monospace", letterSpacing: 1, color: `rgb(${c})` }}>
            ● {l}</span>
        ))}
      </div>
      {modo === "panel" && (
        <button data-testid="visualizador-expandir" onClick={() => setExpandido(!expandido)}
          style={{ position: "absolute", top: 8, right: 10, background: "rgba(14,14,16,0.9)",
            border: "1px solid rgba(212,175,55,0.5)", color: "#e7cf7a", padding: "0.25rem 0.7rem",
            cursor: "pointer", fontSize: "0.65rem", fontWeight: 800, letterSpacing: 1 }}>
          <i className={`fa ${expandido ? "fa-compress" : "fa-expand"}`}></i> {expandido ? "SALIR" : "PANTALLA COMPLETA"}
        </button>
      )}
    </div>
  );

  return modo === "panel"
    ? <div data-testid="visualizador-cognitivo" style={{ marginBottom: "1rem" }}>{cuerpo}</div>
    : cuerpo;
}
