import { useState, useEffect } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const oro = "#d4af37";
const card = { background: "rgba(15,23,42,0.72)", border: "1px solid rgba(212,175,55,0.22)", borderRadius: 14, padding: "1.1rem 1.3rem" };
const MODULO_LB = { administrativo: "Módulo Administrativo", postventa: "Módulo Postventa" };

const RatioPct = ({ v }) => v === null || v === undefined
  ? <span style={{ color: "#64748b", fontSize: "0.66rem", fontStyle: "italic" }}>Plazos por definir</span>
  : <span style={{ fontWeight: 900, fontSize: "1.3rem", color: v >= 80 ? "#22c55e" : v >= 50 ? "#facc15" : "#ef4444" }}>{v}%</span>;

const Kpi = ({ lb, v, color = "#f8fafc" }) => (
  <div>
    <div style={{ color: "#94a3b8", fontSize: "0.56rem", fontWeight: 800, letterSpacing: 1 }}>{lb}</div>
    <div style={{ color, fontSize: "1.3rem", fontWeight: 900 }}>{v}</div>
  </div>
);

const TarjetaEjecutivo = ({ e, detallado }) => (
  <div data-testid={`ejecutivo-card-${e.codigo}`} style={{ ...card, flex: "1 1 300px", minWidth: 280,
    borderColor: e.tareas_vencidas > 0 ? "rgba(239,68,68,0.55)" : "rgba(212,175,55,0.22)" }}>
    <div style={{ display: "flex", gap: 8, alignItems: "baseline", flexWrap: "wrap" }}>
      <b style={{ color: "#f8fafc", fontSize: "0.9rem" }}>{e.nombre}</b>
      <span style={{ fontSize: "0.56rem", fontWeight: 900, letterSpacing: 1, borderRadius: 5, padding: "0.12rem 0.5rem",
        background: e.modulo === "postventa" ? "rgba(74,222,128,0.15)" : "rgba(96,165,250,0.15)",
        color: e.modulo === "postventa" ? "#4ade80" : "#93c5fd" }}>{MODULO_LB[e.modulo] || e.modulo}</span>
      <span style={{ fontSize: "0.52rem", color: "#64748b", fontWeight: 800 }}>ASIGNACIÓN PERMANENTE</span>
    </div>
    {(e.tareas || []).length > 0 && (
      <div style={{ color: "#94a3b8", fontSize: "0.6rem", margin: "4px 0 2px", lineHeight: 1.5 }}>
        {e.tareas.map(t => <div key={t}>• {t}</div>)}
      </div>
    )}
    <div style={{ display: "flex", gap: 16, marginTop: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
      <Kpi lb="OPS ACTIVAS" v={e.ops_activas} />
      <Kpi lb="TAREAS PENDIENTES" v={e.tareas_pendientes} color="#facc15" />
      <Kpi lb="VENCIDAS" v={e.tareas_vencidas} color={e.tareas_vencidas > 0 ? "#ef4444" : "#22c55e"} />
      <Kpi lb="ALERTAS" v={e.alertas_sin_resolver} color={e.alertas_sin_resolver > 0 ? "#f87171" : "#22c55e"} />
      <div>
        <div style={{ color: "#94a3b8", fontSize: "0.56rem", fontWeight: 800, letterSpacing: 1 }}>CUMPLIMIENTO DE PLAZOS</div>
        <RatioPct v={e.ratio_cumplimiento} />
        {e.con_plazo_evaluadas > 0 && (
          <div style={{ color: "#64748b", fontSize: "0.56rem" }}>{e.a_tiempo} a tiempo / {e.atrasadas} atrasadas</div>
        )}
      </div>
    </div>
    {e.tareas_vencidas > 0 && (
      <div data-testid={`ejecutivo-alerta-${e.codigo}`} style={{ marginTop: 8, background: "rgba(239,68,68,0.1)",
        border: "1px solid rgba(239,68,68,0.4)", borderRadius: 8, padding: "0.4rem 0.7rem",
        color: "#fecaca", fontSize: "0.64rem", fontWeight: 800 }}>
        🚨 {e.tareas_vencidas} tarea(s) vencida(s) sin resolver — alerta enviada a Admin y Gerencia
      </div>
    )}
    {detallado && (
      <div style={{ marginTop: 10 }}>
        <div style={{ color: oro, fontSize: "0.6rem", fontWeight: 900, letterSpacing: 1 }}>HISTORIAL MENSUAL DE CUMPLIMIENTO</div>
        {(e.historial_mensual || []).length === 0 && (
          <p style={{ color: "#64748b", fontSize: "0.62rem", fontStyle: "italic" }}>Sin tareas completadas registradas todavía.</p>
        )}
        {(e.historial_mensual || []).length > 0 && (
          <table data-testid={`ejecutivo-historial-${e.codigo}`} style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.66rem", marginTop: 4 }}>
            <thead><tr style={{ color: "#94a3b8", textAlign: "left" }}>
              <th style={{ padding: "3px 6px" }}>Mes</th><th>Completadas</th><th>A tiempo</th><th>Atrasadas</th><th>%</th></tr></thead>
            <tbody>{e.historial_mensual.map(h => {
              const evalu = h.a_tiempo + h.atrasadas;
              const pct = evalu ? Math.round(h.a_tiempo / evalu * 100) : null;
              return (
                <tr key={h.mes} style={{ borderTop: "1px solid rgba(148,163,184,0.12)", color: "#e2e8f0" }}>
                  <td style={{ padding: "3px 6px", fontFamily: "monospace" }}>{h.mes.slice(5)}/{h.mes.slice(0, 4)}</td>
                  <td>{h.completadas}</td>
                  <td style={{ color: "#4ade80" }}>{h.a_tiempo}</td>
                  <td style={{ color: h.atrasadas > 0 ? "#f87171" : "#94a3b8" }}>{h.atrasadas}</td>
                  <td style={{ fontWeight: 800, color: pct === null ? "#64748b" : pct >= 80 ? "#22c55e" : pct >= 50 ? "#facc15" : "#ef4444" }}>
                    {pct === null ? "—" : `${pct}%`}</td>
                </tr>);
            })}</tbody>
          </table>
        )}
      </div>
    )}
  </div>
);

export default function EjecutivosDesempeno() {
  const [d, setD] = useState(null);
  const [vista, setVista] = useState("consolidada");
  useEffect(() => {
    axios.get(`${API}/api/gerencia-comercial/ejecutivos-desempeno`).then(r => setD(r.data)).catch(() => {});
    const iv = setInterval(() => {
      axios.get(`${API}/api/gerencia-comercial/ejecutivos-desempeno`).then(r => setD(r.data)).catch(() => {});
    }, 120000);
    return () => clearInterval(iv);
  }, []);
  if (!d) return null;
  const sel = vista === "consolidada" ? null : (d.ejecutivos || []).find(e => e.codigo === vista);
  return (
    <div style={card} data-testid="panel-ejecutivos-desempeno">
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", marginBottom: 10 }}>
        <h2 style={{ margin: 0, color: "#e2e8f0", fontSize: "0.82rem", fontWeight: 900, letterSpacing: 1.6, textTransform: "uppercase" }}>
          🧭 Gestión de Ejecutivos por Módulo</h2>
        <span style={{ color: "#64748b", fontSize: "0.6rem" }}>
          Cada ejecutivo gestiona solo su módulo · Admin y Gerencia con visión transversal</span>
        <select data-testid="ejecutivos-vista-selector" value={vista} onChange={e => setVista(e.target.value)}
          style={{ marginLeft: "auto", background: "#0f172a", color: "#f8fafc", border: "1px solid rgba(212,175,55,0.4)",
            borderRadius: 8, padding: "0.3rem 0.6rem", fontSize: "0.7rem", fontWeight: 700 }}>
          <option value="consolidada">Vista consolidada — los 3 ejecutivos</option>
          {(d.ejecutivos || []).map(e => <option key={e.codigo} value={e.codigo}>{e.nombre}</option>)}
        </select>
      </div>
      {!sel && (
        <>
        <div data-testid="ejecutivos-consolidado" style={{ display: "flex", gap: 20, flexWrap: "wrap", marginBottom: 12,
          background: "rgba(2,6,23,0.5)", borderRadius: 10, padding: "0.7rem 1rem" }}>
          <Kpi lb="TAREAS PENDIENTES (EQUIPO)" v={d.consolidado?.tareas_pendientes ?? 0} color="#facc15" />
          <Kpi lb="TAREAS VENCIDAS" v={d.consolidado?.tareas_vencidas ?? 0} color={(d.consolidado?.tareas_vencidas || 0) > 0 ? "#ef4444" : "#22c55e"} />
          <Kpi lb="ALERTAS SIN RESOLVER" v={d.consolidado?.alertas_sin_resolver ?? 0} color={(d.consolidado?.alertas_sin_resolver || 0) > 0 ? "#f87171" : "#22c55e"} />
          <Kpi lb="TAREAS COMPLETADAS" v={d.consolidado?.completadas_total ?? 0} color="#4ade80" />
        </div>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          {(d.ejecutivos || []).map(e => <TarjetaEjecutivo key={e.codigo} e={e} />)}
        </div>
        </>
      )}
      {sel && <TarjetaEjecutivo e={sel} detallado />}
    </div>
  );
}
