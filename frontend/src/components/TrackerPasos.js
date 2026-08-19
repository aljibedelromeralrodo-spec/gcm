import { useEffect, useState, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const ORO = "#d4af37";

export const TrackerPasos = ({ tipo, refId, titulo, readOnly = false, condicionalActivo = true }) => {
  const [t, setT] = useState(null);
  const [busy, setBusy] = useState("");
  const cargar = useCallback(() => {
    axios.get(`${API}/api/gerencia-comercial/tracker/${tipo}/${refId}`)
      .then(r => setT(r.data)).catch(() => setT({ error: true }));
  }, [tipo, refId]);
  useEffect(() => { cargar(); }, [cargar]);
  if (!t) return <div style={{ color: "#64748b", fontSize: "0.7rem" }}>Cargando tracker…</div>;
  if (t.error) return <div style={{ color: "#f87171", fontSize: "0.7rem" }}>Sin acceso al tracker</div>;
  const pasos = t.pasos.filter(p => !p.condicional || condicionalActivo);
  const toggle = async (p) => {
    if (readOnly) return;
    setBusy(p.id);
    try {
      await axios.post(`${API}/api/gerencia-comercial/tracker/${tipo}/${refId}/toggle`,
        { paso_id: p.id, completado: !p.completado });
      cargar();
    } catch (e) { alert(e.response?.data?.detail || "No autorizado"); }
    setBusy("");
  };
  return (
    <div data-testid={`tracker-${tipo}-${refId}`} style={{ background: "rgba(2,6,23,0.55)",
      border: `1px solid rgba(212,175,55,0.25)`, borderRadius: 12, padding: "0.9rem 1.1rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
        <b style={{ color: ORO, fontSize: "0.72rem", letterSpacing: 1.2, textTransform: "uppercase" }}>
          {titulo || (tipo === "escritura" ? "📜 Tracker de Escritura" : "🗂 Tracker Administrativo")}</b>
        <div style={{ flex: 1, height: 7, background: "rgba(148,163,184,0.15)", borderRadius: 6 }}>
          <div style={{ width: `${t.avance_pct}%`, height: "100%", borderRadius: 6,
            background: `linear-gradient(90deg, #8a6d1a, ${ORO})`, transition: "width .4s" }} />
        </div>
        <b data-testid={`tracker-avance-${refId}`} style={{ color: "#f8fafc", fontSize: "0.85rem" }}>{t.avance_pct}%</b>
      </div>
      {pasos.map((p, i) => {
        const col = p.estado === "vencido" ? "#ef4444"
          : p.estado === "en_curso" ? (p.dias_restantes !== null && p.dias_restantes <= 1 ? "#facc15" : "#22c55e")
          : p.completado ? ORO : "#475569";
        return (
        <div key={p.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "0.32rem 0",
          borderTop: i ? "1px solid rgba(148,163,184,0.08)" : "none" }}>
          <button data-testid={`tracker-paso-${p.id}`} onClick={() => toggle(p)} disabled={readOnly || busy === p.id}
            title={readOnly ? "Solo lectura" : (p.completado ? "Desmarcar" : "Marcar completado")}
            style={{ width: 24, height: 24, borderRadius: "50%", cursor: readOnly ? "default" : "pointer",
              border: `1px solid ${p.completado ? ORO : col}`,
              background: p.completado ? "rgba(212,175,55,0.25)" : "transparent",
              color: p.completado ? ORO : col, fontWeight: 900, fontSize: "0.72rem", flexShrink: 0 }}>
            {p.completado ? "✓" : i + 1}</button>
          <span style={{ color: p.completado ? "#f8fafc" : "#94a3b8", fontSize: "0.76rem",
            fontWeight: p.completado ? 800 : 500 }}>
            {p.label}{p.condicional ? " (si aplica)" : ""}
            {p.plazo_habiles ? <span style={{ color: "#64748b", fontSize: "0.6rem" }}> · plazo {p.plazo_habiles}d hábiles</span> : null}</span>
          {p.completado ? (
            <span style={{ marginLeft: "auto", color: "#64748b", fontSize: "0.62rem" }}>
              {p.fecha ? `${p.fecha.slice(8, 10)}/${p.fecha.slice(5, 7)}/${p.fecha.slice(0, 4)}` : ""} · {p.responsable}</span>
          ) : p.estado === "vencido" ? (
            <span data-testid={`tracker-vencido-${p.id}`} style={{ marginLeft: "auto", color: "#ef4444",
              fontSize: "0.62rem", fontWeight: 900 }}>🚨 VENCIDO +{p.dias_vencidos}d</span>
          ) : p.estado === "en_curso" ? (
            <span style={{ marginLeft: "auto", color: col, fontSize: "0.62rem", fontWeight: 900 }}>
              ⏳ EN CURSO{p.dias_restantes !== null && p.dias_restantes !== undefined ? ` · ${p.dias_restantes}d restantes` : ""}</span>
          ) : (
            <span style={{ marginLeft: "auto", color: "#64748b", fontSize: "0.6rem",
              fontWeight: 800, letterSpacing: 0.8 }}>PENDIENTE</span>
          )}
        </div>
      ); })}
    </div>
  );
};

export default TrackerPasos;
