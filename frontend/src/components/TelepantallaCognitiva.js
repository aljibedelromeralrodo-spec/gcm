import { useState, useEffect, useRef } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

const ORO = "212,175,55", MORADO = "139,92,246", VERDE = "16,217,142", ROJO = "225,29,72";

const colorCarpeta = (c) => c.alerta || c.resultado === "reprobado" ? ROJO
  : c.resultado === "aprobado" ? VERDE : MORADO;
const hashStr = (s) => (s || "").split("").reduce((a, ch) => a + ch.charCodeAt(0) * 7, 0);
// disparo neuronal secuencial: cada nodo brilla solo — ataque breve, apagado lento
const disparo = (h, t) => {
  const p = 3.5 + (h % 50) / 10;
  const f = (t + ((h % 97) / 97) * p) % p;
  return f < 0.18 ? f / 0.18 : Math.max(0, 1 - (f - 0.18) / 2.4);
};
const DUR_IMPULSO = 5200;

// TELEPANTALLA COGNITIVA: visualizador + correos entrando como impulsos eléctricos
export default function TelepantallaCognitiva({ onCerrar, onAbrirCarpeta }) {
  const [datos, setDatos] = useState(null);
  const datosRef = useRef(null);
  const impRef = useRef({ vistos: new Set(), vuelo: [], llegados: {} });
  const hitsRef = useRef([]);
  const wrapRef = useRef(null);
  const canvasRef = useRef(null);

  const buscarNodo = (e) => {
    const rect = canvasRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left, y = e.clientY - rect.top;
    return hitsRef.current.find(h => (h.x - x) ** 2 + (h.y - y) ** 2 <= 169);
  };
  const clickCanvas = (e) => {
    const h = buscarNodo(e);
    if (h && onAbrirCarpeta) onAbrirCarpeta(h.id);
  };
  const moverCanvas = (e) => {
    if (canvasRef.current) canvasRef.current.style.cursor = buscarNodo(e) ? "pointer" : "default";
  };

  useEffect(() => {
    let vivo = true;
    const cargar = async () => {
      try {
        const r = await axios.get(`${API_URL}/api/telepantalla/estado`);
        if (!vivo) return;
        const im = impRef.current, ahora = performance.now();
        (r.data.flujo_correos || []).forEach((c, i) => {
          if (!im.vistos.has(c.id)) {
            im.vistos.add(c.id);
            im.vuelo.push({ correo: c, t0: ahora + i * 650 });   // impulsos escalonados
          }
        });
        datosRef.current = r.data;
        setDatos(r.data);
      } catch { /* mantiene el último estado */ }
    };
    cargar();
    const iv = setInterval(cargar, 8000);
    return () => { vivo = false; clearInterval(iv); };
  }, []);

  useEffect(() => {
    const fn = (e) => { if (e.key === "Escape") onCerrar(); };
    window.addEventListener("keydown", fn);
    return () => window.removeEventListener("keydown", fn);
  }, [onCerrar]);

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
      const im = impRef.current;
      const cx = W / 2, cy = H / 2, base = Math.min(W, H);
      const R1 = base * 0.19, R2 = base * 0.35, R3 = base * 0.46;

      const posEj = (i, n) => {
        const a = (i / Math.max(n, 1)) * Math.PI * 2 - Math.PI / 2;
        return { x: cx + Math.cos(a) * R1 + Math.sin(t * 0.22 + i) * 6, y: cy + Math.sin(a) * R1 + Math.cos(t * 0.18 + i * 2) * 6 };
      };
      const posCa = (i, n, id) => {
        const h = hashStr(id);
        const a = (i / Math.max(n, 1)) * Math.PI * 2 + (h % 10) * 0.02;
        const r = R2 + (h % 5) * base * 0.015;
        return { x: cx + Math.cos(a) * r + Math.sin(t * 0.25 + h) * 7, y: cy + Math.sin(a) * r + Math.cos(t * 0.2 + h) * 7 };
      };
      const posCo = (id) => {
        const h = hashStr(id);
        const a = ((h % 360) / 360) * Math.PI * 2;
        return { x: cx + Math.cos(a) * R3 + Math.sin(t * 0.2 + h) * 5, y: cy + Math.sin(a) * R3 + Math.cos(t * 0.24 + h) * 5,
                 borde: { x: cx + Math.cos(a) * Math.max(W, H) * 0.75, y: cy + Math.sin(a) * Math.max(W, H) * 0.75 } };
      };

      const linea = (a, b, rgb, alpha, pulso, fase) => {
        ctx.globalAlpha = alpha;
        ctx.strokeStyle = `rgba(${rgb},1)`;
        ctx.lineWidth = pulso ? 1.4 : 0.7;
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
        if (pulso) {
          const f = ((t * 0.45 + fase) % 1);
          ctx.globalAlpha = 0.95;
          ctx.shadowColor = `rgb(${ORO})`; ctx.shadowBlur = 12;
          ctx.fillStyle = "#FCF6BA";
          ctx.beginPath(); ctx.arc(a.x + (b.x - a.x) * f, a.y + (b.y - a.y) * f, 2.4, 0, Math.PI * 2); ctx.fill();
          ctx.shadowBlur = 0;
        }
      };
      const nodo = (p, r, rgb, glow, label, labelCol, fuego = 0, alphaBase = 0.55) => {
        if (fuego > 0.02) {
          ctx.globalAlpha = 0.16 * fuego;
          ctx.fillStyle = `rgb(${rgb})`;
          ctx.beginPath(); ctx.arc(p.x, p.y, r + 4 + fuego * 13, 0, Math.PI * 2); ctx.fill();
        }
        ctx.globalAlpha = alphaBase + (1 - alphaBase) * fuego;
        ctx.shadowColor = `rgb(${rgb})`; ctx.shadowBlur = glow + fuego * 22;
        ctx.fillStyle = `rgba(${rgb},0.95)`;
        ctx.beginPath(); ctx.arc(p.x, p.y, r * (1 + 0.3 * fuego), 0, Math.PI * 2); ctx.fill();
        ctx.shadowBlur = 0;
        if (label) {
          ctx.globalAlpha = 1;
          ctx.font = "9px monospace"; ctx.textAlign = "center";
          ctx.fillStyle = labelCol || "rgba(200,190,160,0.75)";
          ctx.fillText(label, p.x, p.y + r + 11);
        }
      };

      const nE = d.ejecutivos.length, nC = d.carpetas.length;
      d.ejecutivos.forEach((e, i) => linea(posEj(i, nE), { x: cx, y: cy }, ORO, 0.35, true, i * 0.19));
      d.carpetas.forEach((c, i) => {
        const pe = nE ? posEj(i % nE, nE) : { x: cx, y: cy };
        linea(posCa(i, nC, c.id), pe, c.activo_reciente ? ORO : colorCarpeta(c), c.activo_reciente ? 0.5 : 0.14, c.activo_reciente, i * 0.13);
      });

      // CORREOS ya integrados al sistema (impulso terminado)
      (d.flujo_correos || []).forEach((c) => {
        if (!im.llegados[c.id]) return;
        const p = posCo(c.id);
        if (c.estado === "carpeta") {                    // generó carpeta → dorado mate activo
          linea(p, { x: cx, y: cy }, ORO, 0.3, true, hashStr(c.id) % 10 / 10);
          nodo(p, 4.2, ORO, 6, c.nombre, "rgba(231,207,122,0.85)", disparo(hashStr(c.id), t));
        } else if (c.estado === "espera") {              // en espera → pulsa lentamente
          const lat = (Math.sin(t * 0.9 + hashStr(c.id)) + 1) / 2;
          linea(p, { x: cx, y: cy }, MORADO, 0.12, false, 0);
          nodo(p, 3.4 + lat * 1.4, MORADO, 4 + lat * 10, c.nombre, `rgba(${MORADO},0.8)`, 0, 0.5 + lat * 0.4);
        } else {                                          // no califica → morado tenue apagado
          nodo(p, 3, MORADO, 0, c.nombre, "rgba(139,92,246,0.45)", 0, 0.3);
        }
      });

      // IMPULSOS ELÉCTRICOS en vuelo: desde el borde hacia el centro
      im.vuelo = im.vuelo.filter((v) => {
        if (now < v.t0) return true;
        const c = v.correo;
        const { x, y, borde } = posCo(c.id);
        const destino = c.estado === "carpeta" || c.estado === "espera" ? { x, y } : { x: cx, y: cy };
        const fFin = c.estado === "no_califica" ? 0.62 : 1;   // se apaga a mitad de camino
        const f = Math.min(1, (now - v.t0) / DUR_IMPULSO) * fFin;
        const px = borde.x + (destino.x - borde.x) * f, py = borde.y + (destino.y - borde.y) * f;
        const muriendo = c.estado === "no_califica" && f > fFin * 0.7;
        const rgb = muriendo ? MORADO : ORO;
        // estela del impulso
        for (let k = 0; k < 6; k++) {
          const fk = Math.max(0, f - k * 0.018);
          ctx.globalAlpha = (muriendo ? 0.25 : 0.6) * (1 - k / 6);
          ctx.fillStyle = k === 0 ? "#FCF6BA" : `rgba(${rgb},0.9)`;
          ctx.shadowColor = `rgb(${rgb})`; ctx.shadowBlur = k === 0 ? 16 : 0;
          ctx.beginPath();
          ctx.arc(borde.x + (destino.x - borde.x) * fk, borde.y + (destino.y - borde.y) * fk, k === 0 ? 3.2 : 2.2 - k * 0.25, 0, Math.PI * 2);
          ctx.fill();
          ctx.shadowBlur = 0;
        }
        ctx.globalAlpha = 0.85;
        ctx.font = "9px monospace"; ctx.textAlign = "center";
        ctx.fillStyle = muriendo ? "rgba(139,92,246,0.6)" : "#e7cf7a";
        ctx.fillText(`✉ ${c.nombre}`, px, py - 10);
        if ((now - v.t0) >= DUR_IMPULSO) {
          im.llegados[c.id] = now;
          return false;
        }
        return true;
      });
      // anillo de nacimiento al integrarse
      Object.entries(im.llegados).forEach(([id, tn]) => {
        const e = (now - tn) / 1400;
        if (e < 1) {
          const p = posCo(id);
          ctx.globalAlpha = 1 - e;
          ctx.strokeStyle = `rgb(${ORO})`; ctx.lineWidth = 1.6;
          ctx.beginPath(); ctx.arc(p.x, p.y, 4 + e * 26, 0, Math.PI * 2); ctx.stroke();
        }
      });

      // nodos carpeta con nombres (clickeables → abren la carpeta del cliente)
      const hits = [];
      d.carpetas.forEach((c, i) => {
        const rgb = colorCarpeta(c);
        const p = posCa(i, nC, c.id);
        hits.push({ x: p.x, y: p.y, id: c.id });
        nodo(p, 4.6, rgb, 5, c.nombre.split(" ")[0], `rgba(${rgb},0.8)`, disparo(hashStr(c.id), t));
      });
      hitsRef.current = hits;
      d.ejecutivos.forEach((e, i) => nodo(posEj(i, nE), 6, ORO, 6, e.nombre.split(" ")[0],
        "rgba(231,207,122,0.85)", disparo(hashStr(e.codigo) + 31, t)));

      // CEREBRO NORMATIVO al centro
      const rB = 13 + Math.sin(t * 2.2) * 2.5;
      ctx.globalAlpha = 0.25;
      ctx.fillStyle = `rgb(${ORO})`;
      ctx.beginPath(); ctx.arc(cx, cy, rB + 12 + Math.sin(t * 2.2) * 4, 0, Math.PI * 2); ctx.fill();
      nodo({ x: cx, y: cy }, rB, ORO, 26, null, null, 0, 1);
      ctx.globalAlpha = 1; ctx.textAlign = "center";
      ctx.font = "bold 10px monospace"; ctx.fillStyle = "#FCF6BA";
      ctx.fillText("CEREBRO NORMATIVO", cx, cy + rB + 18);
      ctx.font = "9px monospace"; ctx.fillStyle = "rgba(200,190,160,0.7)";
      ctx.fillText(`${d.cerebro.normativas} reglas · calibración ${d.cerebro.calibracion}%`, cx, cy + rB + 30);
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <div ref={wrapRef} data-testid="telepantalla-cognitiva"
      style={{ position: "fixed", inset: 0, zIndex: 95000, background: "#000" }}>
      <canvas ref={canvasRef} onClick={clickCanvas} onMouseMove={moverCanvas} data-testid="telepantalla-canvas"
        style={{ display: "block", position: "absolute", inset: 0 }} />
      <div style={{ position: "absolute", top: 12, left: 16, pointerEvents: "none" }}>
        <span style={{ color: "#e7cf7a", fontSize: "0.72rem", fontWeight: 800, letterSpacing: 2, fontFamily: "monospace" }}>
          📡 TELEPANTALLA COGNITIVA — CENTRAL MUTUOS</span>
        {datos && <span style={{ color: "#6a6046", fontSize: "0.6rem", fontFamily: "monospace", marginLeft: 10 }}>
          {(datos.flujo_correos || []).length} correos en flujo · {datos.carpetas.length} carpetas · {datos.ejecutivos.length} ejecutivos</span>}
      </div>
      <div style={{ position: "absolute", bottom: 10, left: 16, display: "flex", gap: 12, pointerEvents: "none" }}>
        {[["IMPULSO/ACTIVO", ORO], ["ESPERA (pulsa)", MORADO], ["APROBADO", VERDE], ["RECHAZO/ALERTA", ROJO]].map(([l, c]) => (
          <span key={l} style={{ fontSize: "0.55rem", fontFamily: "monospace", letterSpacing: 1, color: `rgb(${c})` }}>● {l}</span>
        ))}
        <span style={{ fontSize: "0.55rem", fontFamily: "monospace", letterSpacing: 1, color: "#6a6046" }}>
          · CLIC EN UNA CARPETA PARA ABRIRLA</span>
      </div>
      <button data-testid="telepantalla-cerrar" onClick={onCerrar}
        style={{ position: "absolute", top: 10, right: 12, background: "rgba(14,14,16,0.9)",
          border: "1px solid rgba(212,175,55,0.5)", color: "#e7cf7a", padding: "0.3rem 0.9rem",
          cursor: "pointer", fontSize: "0.68rem", fontWeight: 800, letterSpacing: 1 }}>✕ CERRAR (ESC)</button>
    </div>
  );
}
