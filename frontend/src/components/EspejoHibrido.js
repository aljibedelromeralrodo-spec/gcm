import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const card = { background: "rgba(30,41,59,0.55)", border: "1px solid rgba(148,163,184,0.2)", borderRadius: 12, padding: "1rem", marginTop: 14 };
const EST_COLOR = { activo: "#4ade80", en_espera: "#facc15", error: "#f87171" };
const EST_LB = { activo: "ACTIVO", en_espera: "EN ESPERA (sin credenciales)", error: "ERROR" };
const PRIO_COLOR = { PRIMARIA: "#d4af37", COMPLEMENTARIA: "#93c5fd", POSTVENTA: "#4ade80" };

const fFecha = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  const p = (n) => String(n).padStart(2, "0");
  return `${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}`;
};

export default function EspejoHibrido() {
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState(false);
  const cargar = useCallback(() => {
    axios.get(`${API}/api/espejo-hibrido/estado`).then(r => setD(r.data)).catch(() => setD({ oculto: true }));
  }, []);
  useEffect(() => {
    cargar();
    const iv = setInterval(cargar, 90000);
    return () => clearInterval(iv);
  }, [cargar]);
  const barrer = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/espejo-hibrido/barrido`);
      const res = (r.data.resultados || []).map(x =>
        `${x.fuente}: ${x.estado}${x.correos_procesados !== undefined ? ` · ${x.correos_procesados} correos · ${x.operaciones_actualizadas} ops` : ""}`).join("\n");
      window.alert(`Barrido ejecutado:\n${res}`);
      cargar();
    } catch (e) { window.alert(e.response?.data?.detail || "No fue posible ejecutar el barrido"); }
    setBusy(false);
  };
  if (!d || d.oculto) return null;
  return (
    <div style={card} data-testid="panel-espejo-hibrido">
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <h4 style={{ margin: 0, color: "#d4af37", fontSize: "0.85rem", letterSpacing: 1 }}>
          🪞 ESPEJO HÍBRIDO — ESTADO DE FUENTES</h4>
        <span style={{ color: "#64748b", fontSize: "0.6rem" }}>
          Capa aprobación + capa administrativa · Claude analiza cada correo · barrido cada {Math.round((d.intervalo_seg || 300) / 60)} min</span>
        {d.puede_barrer && (
          <button data-testid="espejo-barrido-manual" onClick={barrer} disabled={busy}
            style={{ marginLeft: "auto", background: "linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C)",
              color: "#0a0a0a", border: "none", borderRadius: 8, padding: "0.35rem 0.8rem",
              fontWeight: 800, cursor: "pointer", fontSize: "0.66rem" }}>
            {busy ? "Barriendo…" : "🔄 Ejecutar barrido ahora"}</button>
        )}
      </div>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 10 }}>
        {(d.fuentes || []).map(f => (
          <div key={f.fid} data-testid={`espejo-fuente-${f.fid}`} style={{ flex: "1 1 260px", minWidth: 250,
            background: "rgba(2,6,23,0.5)", border: `1px solid ${EST_COLOR[f.estado] || "#64748b"}44`,
            borderRadius: 10, padding: "0.7rem 0.9rem" }}>
            <div style={{ display: "flex", gap: 8, alignItems: "baseline", flexWrap: "wrap" }}>
              <b style={{ color: "#f8fafc", fontSize: "0.78rem" }}>{f.nombre}</b>
              <span style={{ fontSize: "0.52rem", fontWeight: 900, letterSpacing: 1, color: PRIO_COLOR[f.prioridad] || "#94a3b8",
                border: `1px solid ${PRIO_COLOR[f.prioridad] || "#94a3b8"}66`, borderRadius: 5, padding: "0.1rem 0.45rem" }}>
                {f.prioridad}</span>
            </div>
            <div style={{ color: "#94a3b8", fontSize: "0.6rem", fontFamily: "monospace", margin: "3px 0" }}>{f.email}</div>
            <div style={{ color: "#64748b", fontSize: "0.58rem", lineHeight: 1.4 }}>{f.descripcion}</div>
            <div style={{ marginTop: 6, display: "flex", gap: 12, flexWrap: "wrap", alignItems: "baseline" }}>
              <span data-testid={`espejo-estado-${f.fid}`} style={{ color: EST_COLOR[f.estado] || "#94a3b8", fontWeight: 900, fontSize: "0.66rem" }}>
                ● {EST_LB[f.estado] || f.estado}</span>
              <span style={{ color: "#94a3b8", fontSize: "0.58rem" }}>
                credenciales: <b style={{ color: "#e2e8f0" }}>{f.origen_credenciales}</b></span>
            </div>
            <div style={{ marginTop: 5, color: "#94a3b8", fontSize: "0.6rem" }}>
              {f.correos_totales} correos analizados · {f.en_revision} en revisión
              {f.ultimo_barrido && <> · último barrido: {fFecha(f.ultimo_barrido.fecha)} ({f.ultimo_barrido.correos_procesados} correos, {f.ultimo_barrido.operaciones_actualizadas} ops)</>}
            </div>
          </div>
        ))}
      </div>
      {(d.bitacora || []).length > 0 && (
        <details style={{ marginTop: 10 }}>
          <summary style={{ color: "#94a3b8", fontSize: "0.64rem", fontWeight: 800, cursor: "pointer" }}>
            📜 Bitácora de barridos ({d.bitacora.length})</summary>
          <table data-testid="espejo-bitacora" style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.62rem", marginTop: 6 }}>
            <thead><tr style={{ color: "#94a3b8", textAlign: "left" }}>
              <th style={{ padding: "3px 6px" }}>Fecha</th><th>Fuente</th><th>Correos</th><th>Ops actualizadas</th><th>Discrepancias</th><th>Estado</th></tr></thead>
            <tbody>{d.bitacora.map(b => (
              <tr key={b.id} style={{ borderTop: "1px solid rgba(148,163,184,0.12)", color: "#e2e8f0" }}>
                <td style={{ padding: "3px 6px", fontFamily: "monospace" }}>{fFecha(b.fecha)}</td>
                <td>{b.fuente_nombre || b.fuente}</td>
                <td>{b.correos_procesados}</td>
                <td>{b.operaciones_actualizadas}</td>
                <td style={{ color: b.discrepancias > 0 ? "#f87171" : "#94a3b8" }}>{b.discrepancias}</td>
                <td style={{ color: b.estado === "ok" ? "#4ade80" : "#f87171", fontWeight: 800 }}>{b.estado}{b.error ? ` — ${b.error.slice(0, 60)}` : ""}</td>
              </tr>
            ))}</tbody>
          </table>
        </details>
      )}
    </div>
  );
}
