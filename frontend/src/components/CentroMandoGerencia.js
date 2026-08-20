import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
export const ORO = "#C9A227";
export const ORO_CLARO = "#E8C96A";
export const PANEL = { background: "#0c0c0c", border: "1px solid rgba(201,162,39,0.22)", borderRadius: 10 };
const LBL = { color: "#8a8a8a", fontSize: "0.58rem", fontWeight: 800, letterSpacing: 2, textTransform: "uppercase" };
const IMAP_UI = {
  activo: { c: "#4ade80", t: "ACTIVO" },
  error: { c: "#ef4444", t: "ERROR" },
  en_espera: { c: "#eab308", t: "EN ESPERA" },
};
const fmt = (n) => Number(n || 0).toLocaleString("es-CL");

const Kpi = ({ id, titulo, valor, sub, alerta }) => (
  <div data-testid={`kpi-${id}`} style={{ ...PANEL, padding: "1.1rem 1.3rem", flex: "1 1 170px",
    borderColor: alerta ? "rgba(239,68,68,0.55)" : "rgba(201,162,39,0.22)" }}>
    <div style={LBL}>{titulo}</div>
    <div style={{ color: alerta ? "#ef4444" : "#f5f0e1", fontWeight: 900, fontSize: "1.9rem",
      lineHeight: 1.15, marginTop: 4, fontVariantNumeric: "tabular-nums" }}>{valor}</div>
    {sub && <div style={{ color: "#7a7a7a", fontSize: "0.62rem", marginTop: 3 }}>{sub}</div>}
  </div>
);

const EstadoImap = ({ imap }) => {
  const ui = IMAP_UI[imap?.estado] || IMAP_UI.en_espera;
  return (
    <span title={imap?.email ? `${imap.email} · ${imap.correos_totales || 0} correo(s) procesados` : ""}
      style={{ color: ui.c, fontWeight: 800, fontSize: "0.62rem", letterSpacing: 1,
        border: `1px solid ${ui.c}44`, borderRadius: 6, padding: "0.18rem 0.5rem", whiteSpace: "nowrap" }}>
      ● {ui.t}
    </span>
  );
};

const FichaEjecutivo = ({ codigo, onClose }) => {
  const [f, setF] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    axios.get(`${API}/api/gerencia-comercial/ejecutivo/${codigo}/ficha`)
      .then(r => setF(r.data)).catch(e => setError(e.response?.data?.detail || "Error al cargar la ficha"));
  }, [codigo]);
  const m = f?.metricas || {};
  const th = { color: ORO, fontSize: "0.6rem", letterSpacing: 1, textTransform: "uppercase",
    textAlign: "left", padding: "6px 10px", borderBottom: "1px solid rgba(201,162,39,0.3)" };
  const td = { color: "#d9d4c5", fontSize: "0.7rem", padding: "5px 10px",
    borderBottom: "1px solid rgba(255,255,255,0.06)" };
  return (
    <div data-testid="ficha-ejecutivo-modal" onClick={onClose}
      style={{ position: "fixed", inset: 0, zIndex: 300, background: "rgba(0,0,0,0.85)",
        display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem" }}>
      <div onClick={e => e.stopPropagation()} style={{ ...PANEL, background: "#080808", width: "min(880px, 96vw)",
        maxHeight: "88vh", overflowY: "auto", padding: "1.4rem 1.6rem" }}>
        {!f && !error && <p style={{ color: "#8a8a8a" }}>Cargando ficha…</p>}
        {error && <p style={{ color: "#ef4444" }}>{error}</p>}
        {f && (
          <>
            <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
              <h3 style={{ margin: 0, color: ORO, letterSpacing: 1, fontSize: "1.05rem" }}>{f.ejecutivo.nombre}</h3>
              <span style={{ color: "#8a8a8a", fontSize: "0.68rem", textTransform: "capitalize" }}>
                Módulo {f.ejecutivo.modulo} {f.ejecutivo.email ? `· ${f.ejecutivo.email}` : ""}</span>
              <button data-testid="ficha-cerrar" onClick={onClose} style={{ marginLeft: "auto", background: "transparent",
                border: `1px solid ${ORO}55`, color: ORO, borderRadius: 8, padding: "0.25rem 0.8rem",
                cursor: "pointer", fontSize: "0.68rem", fontWeight: 800 }}>CERRAR ✕</button>
            </div>
            {(f.ejecutivo.tareas || []).length > 0 && (
              <p style={{ color: "#9a9483", fontSize: "0.66rem", margin: "6px 0 0" }}>
                {f.ejecutivo.tareas.join(" · ")}</p>
            )}
            <div style={{ display: "flex", gap: 20, flexWrap: "wrap", marginTop: 14 }}>
              {[["Tareas pendientes", m.tareas_pendientes ?? "—"],
                ["Tareas vencidas", m.tareas_vencidas ?? "—", (m.tareas_vencidas || 0) > 0],
                ["Completadas", m.completadas_total ?? "—"],
                ["Cumplimiento de plazos", m.ratio_cumplimiento != null ? `${m.ratio_cumplimiento}%` : "s/d"],
                ["Ops activas", m.ops_activas ?? "—"]].map(([k, v, rojo]) => (
                <div key={k}>
                  <div style={LBL}>{k}</div>
                  <div style={{ color: rojo ? "#ef4444" : "#f5f0e1", fontWeight: 900, fontSize: "1.2rem" }}>{v}</div>
                </div>
              ))}
            </div>
            {(m.historial_mensual || []).length > 0 && (
              <div style={{ marginTop: 12 }}>
                <div style={LBL}>Historial mensual</div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 4 }}>
                  {m.historial_mensual.map(h => (
                    <span key={h.mes} style={{ fontSize: "0.62rem", color: "#d9d4c5",
                      border: "1px solid rgba(201,162,39,0.2)", borderRadius: 6, padding: "0.2rem 0.5rem" }}>
                      {h.mes}: {h.completadas} comp. · {h.a_tiempo} a tiempo · {h.atrasadas} atrasadas</span>
                  ))}
                </div>
              </div>
            )}
            <h4 style={{ color: ORO, fontSize: "0.78rem", letterSpacing: 1, margin: "18px 0 6px" }}>
              HISTORIAL DE OPERACIONES ({f.historial_operaciones.length})</h4>
            <div style={{ overflowX: "auto" }}>
              <table data-testid="ficha-historial" style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead><tr>{["Cliente", "RUT", "Etapa", "Monto UF", "DICOM", "Sin mov. (días)", "Actualizado"].map(h =>
                  <th key={h} style={th}>{h}</th>)}</tr></thead>
                <tbody>
                  {f.historial_operaciones.map((o, i) => (
                    <tr key={i}>
                      <td style={{ ...td, color: "#fff", fontWeight: 600 }}>{o.cliente}</td>
                      <td style={{ ...td, fontFamily: "monospace" }}>{o.rut || "—"}</td>
                      <td style={td}>{o.etapa}</td>
                      <td style={{ ...td, textAlign: "right", color: ORO_CLARO }}>{o.monto_uf ? fmt(o.monto_uf) : "—"}</td>
                      <td style={{ ...td, color: o.dicom ? "#ef4444" : "#4ade80", fontWeight: 800 }}>{o.dicom ? "SÍ" : "No"}</td>
                      <td style={{ ...td, color: o.dias_sin_movimiento >= 7 ? "#eab308" : "#d9d4c5" }}>{o.dias_sin_movimiento}</td>
                      <td style={td}>{o.actualizado || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <h4 style={{ color: ORO, fontSize: "0.78rem", letterSpacing: 1, margin: "18px 0 6px" }}>COMUNICACIONES</h4>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              <div>
                <div style={LBL}>Correos del sistema al ejecutivo</div>
                {(f.comunicaciones.enviadas || []).length === 0 &&
                  <p style={{ color: "#7a7a7a", fontSize: "0.64rem" }}>Sin registros.</p>}
                {(f.comunicaciones.enviadas || []).map((c, i) => (
                  <div key={i} style={{ fontSize: "0.64rem", color: "#d9d4c5", padding: "4px 0",
                    borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                    <span style={{ color: c.success ? "#4ade80" : "#ef4444" }}>●</span>{" "}
                    {(c.fecha || "").slice(0, 16).replace("T", " ")} — {c.subject}
                  </div>
                ))}
              </div>
              <div>
                <div style={LBL}>Correos analizados por el Espejo (IA)</div>
                {(f.comunicaciones.espejo || []).length === 0 &&
                  <p style={{ color: "#7a7a7a", fontSize: "0.64rem" }}>Sin correos procesados aún.</p>}
                {(f.comunicaciones.espejo || []).map((c, i) => (
                  <div key={i} style={{ fontSize: "0.64rem", color: "#d9d4c5", padding: "4px 0",
                    borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                    <b style={{ color: ORO_CLARO }}>{c.tipo_comunicacion || "correo"}</b> · {c.asunto || c.resumen}
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default function CentroMandoGerencia() {
  const [d, setD] = useState(null);
  const [ficha, setFicha] = useState("");

  const recargar = useCallback(() => {
    axios.get(`${API}/api/gerencia-comercial/centro-mando`).then(r => setD(r.data)).catch(() => setD({ error: true }));
  }, []);
  useEffect(() => { recargar(); const iv = setInterval(recargar, 300000); return () => clearInterval(iv); }, [recargar]);

  if (!d) return <p style={{ color: "#8a8a8a", padding: "1rem" }}>Cargando Centro de Mando…</p>;
  if (d.error) return <p style={{ color: "#ef4444", padding: "1rem" }}>No fue posible cargar el Centro de Mando.</p>;
  const k = d.kpis;
  const al = d.alertas;
  const thE = { color: ORO, fontSize: "0.62rem", letterSpacing: 1.5, textTransform: "uppercase",
    textAlign: "left", padding: "10px 14px", borderBottom: "2px solid rgba(201,162,39,0.4)",
    background: "#0a0a0a", whiteSpace: "nowrap" };
  const tdE = { color: "#e8e3d3", fontSize: "0.78rem", padding: "10px 14px",
    borderBottom: "1px solid rgba(255,255,255,0.06)", verticalAlign: "middle" };

  return (
    <div data-testid="centro-mando-gerencia">
      {/* ═══ KPIs PRINCIPALES ═══ */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 14 }}>
        <Kpi id="cartera-total" titulo="Cartera Total" valor={`${fmt(Math.round(k.cartera_total_uf))} UF`}
          sub={`${k.cartera_total_ops} operaciones en cartera`} />
        <Kpi id="ops-activas" titulo="Operaciones Activas" valor={k.operaciones_activas}
          sub={`${k.escrituradas} escrituradas`} />
        <Kpi id="mora-vigente" titulo="Mora Vigente · DICOM" valor={k.mora_vigente.n}
          sub={k.mora_vigente.n ? `${fmt(Math.round(k.mora_vigente.uf))} UF comprometidas` : "Sin clientes con DICOM vigente"}
          alerta={k.mora_vigente.n > 0} />
        <Kpi id="nuevas-mes" titulo={`Nuevas del Mes ${d.mes}`} valor={k.nuevas_mes} sub="ingresos del período" />
        <div data-testid="ranking-ejecutivos" style={{ ...PANEL, padding: "0.9rem 1.2rem", flex: "1.3 1 240px" }}>
          <div style={LBL}>Ranking de Ejecutivos</div>
          {d.ranking.map((e, i) => (
            <div key={e.codigo} style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
              <b style={{ color: i === 0 ? ORO : "#8a8a8a", fontSize: "0.78rem", width: 16 }}>{i + 1}</b>
              <span style={{ color: "#f5f0e1", fontSize: "0.74rem", fontWeight: 700, flex: 1 }}>{e.nombre}</span>
              <span style={{ color: "#9a9483", fontSize: "0.62rem" }}>
                {e.ratio_cumplimiento != null ? `${e.ratio_cumplimiento}% plazos` : "s/d"} · cierre {e.tasa_cierre}%</span>
            </div>
          ))}
        </div>
      </div>

      {/* ═══ ALERTAS INTELIGENTES ═══ */}
      <div data-testid="alertas-inteligentes" style={{ display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 12, marginBottom: 14 }}>
        <div style={{ ...PANEL, padding: "0.9rem 1.1rem",
          borderColor: al.ejecutivos_mora_alta.length ? "rgba(239,68,68,0.5)" : undefined }}>
          <div style={LBL}>Ejecutivos con mora alta</div>
          {al.ejecutivos_mora_alta.length === 0
            ? <p style={{ color: "#4ade80", fontSize: "0.68rem", margin: "6px 0 0" }}>Sin ejecutivos con clientes DICOM en su cartera.</p>
            : al.ejecutivos_mora_alta.map(e => (
              <div key={e.nombre} style={{ color: "#fca5a5", fontSize: "0.7rem", marginTop: 5, fontWeight: 700 }}>
                ⚠ {e.nombre} — {e.mora} cliente(s) con DICOM</div>))}
        </div>
        <div style={{ ...PANEL, padding: "0.9rem 1.1rem",
          borderColor: (al.operaciones_vencidas.tareas_vencidas || al.operaciones_vencidas.firmas_proximas.length) ? "rgba(234,179,8,0.5)" : undefined }}>
          <div style={LBL}>Operaciones vencidas y próximas</div>
          <div style={{ color: al.operaciones_vencidas.tareas_vencidas ? "#eab308" : "#4ade80", fontSize: "0.7rem", marginTop: 5, fontWeight: 700 }}>
            {al.operaciones_vencidas.tareas_vencidas} tarea(s) fuera de plazo en trackers</div>
          {al.operaciones_vencidas.firmas_proximas.map((p, i) => (
            <div key={i} style={{ color: "#e8e3d3", fontSize: "0.66rem", marginTop: 4 }}>
              📅 {p.cliente} — firma {p.fecha_firma} ({p.dias_restantes} día(s))</div>))}
        </div>
        <div style={{ ...PANEL, padding: "0.9rem 1.1rem",
          borderColor: al.clientes_sin_actividad.length ? "rgba(234,179,8,0.4)" : undefined }}>
          <div style={LBL}>Clientes sin actividad reciente (7+ días)</div>
          {al.clientes_sin_actividad.length === 0
            ? <p style={{ color: "#4ade80", fontSize: "0.68rem", margin: "6px 0 0" }}>Toda la cartera con movimiento reciente.</p>
            : al.clientes_sin_actividad.slice(0, 8).map((c, i) => (
              <div key={i} style={{ color: "#d9d4c5", fontSize: "0.66rem", marginTop: 4 }}>
                ⏸ {c.cliente} — {c.dias} días sin movimiento</div>))}
          {al.clientes_sin_actividad.length > 8 &&
            <div style={{ color: "#7a7a7a", fontSize: "0.6rem", marginTop: 4 }}>
              +{al.clientes_sin_actividad.length - 8} más…</div>}
        </div>
      </div>

      {/* ═══ TABLA DE EJECUTIVOS EXPANDIDA ═══ */}
      <div style={{ ...PANEL, overflow: "auto", marginBottom: 14 }}>
        <table data-testid="tabla-ejecutivos" style={{ width: "100%", borderCollapse: "collapse", minWidth: 860 }}>
          <thead><tr>{["Ejecutivo", "Cartera asignada", "Ops activas", "Tasa de cierre", "Mora generada",
            "Cumplimiento plazos", "Correo IMAP", "Ficha"].map(h => <th key={h} style={thE}>{h}</th>)}</tr></thead>
          <tbody>
            {d.ejecutivos.map(e => (
              <tr key={e.codigo} data-testid={`ejecutivo-fila-${e.codigo}`}
                style={{ background: "#0c0c0c", cursor: "pointer" }} onClick={() => setFicha(e.codigo)}>
                <td style={tdE}>
                  <b style={{ color: "#fff" }}>{e.nombre}</b>
                  <div style={{ color: "#8a8a8a", fontSize: "0.6rem", textTransform: "capitalize" }}>Módulo {e.modulo}</div>
                </td>
                <td style={{ ...tdE, color: ORO_CLARO, fontWeight: 800 }}>
                  {fmt(Math.round(e.cartera_uf))} UF <span style={{ color: "#8a8a8a", fontWeight: 400 }}>· {e.cartera_ops} ops</span></td>
                <td style={tdE}>{e.ops_activas}</td>
                <td style={{ ...tdE, fontWeight: 800, color: e.tasa_cierre >= 50 ? "#4ade80" : "#e8e3d3" }}>{e.tasa_cierre}%</td>
                <td style={{ ...tdE, fontWeight: 800, color: e.mora_generada ? "#ef4444" : "#4ade80" }}>
                  {e.mora_generada || "0"}</td>
                <td style={tdE}>
                  {e.ratio_cumplimiento != null ? `${e.ratio_cumplimiento}%` : "s/d"}
                  {e.tareas_vencidas > 0 && <span style={{ color: "#ef4444", fontSize: "0.6rem", marginLeft: 6 }}>
                    {e.tareas_vencidas} vencida(s)</span>}
                </td>
                <td style={tdE}><EstadoImap imap={e.imap} /></td>
                <td style={tdE}>
                  <button data-testid={`btn-ficha-${e.codigo}`} onClick={ev => { ev.stopPropagation(); setFicha(e.codigo); }}
                    style={{ background: "transparent", border: `1px solid ${ORO}66`, color: ORO, borderRadius: 8,
                      padding: "0.3rem 0.8rem", cursor: "pointer", fontSize: "0.62rem", fontWeight: 800, letterSpacing: 1 }}>
                    VER FICHA</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {ficha && <FichaEjecutivo codigo={ficha} onClose={() => setFicha("")} />}
    </div>
  );
}
