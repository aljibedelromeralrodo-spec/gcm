import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const ORO = "#C9A227";
const ORO_CLARO = "#E8C96A";
const BORDE = "rgba(201,162,39,0.22)";
const panel = { background: "#0c0c0c", border: `1px solid ${BORDE}`, borderRadius: 10 };
const LBL = { color: "#8a8a8a", fontSize: "0.58rem", fontWeight: 800, letterSpacing: 2, textTransform: "uppercase" };
const th = { color: ORO, fontSize: "0.6rem", letterSpacing: 1.2, textTransform: "uppercase", textAlign: "left",
  padding: "9px 12px", borderBottom: "2px solid rgba(201,162,39,0.4)", background: "#0a0a0a", whiteSpace: "nowrap" };
const td = { color: "#e8e3d3", fontSize: "0.74rem", padding: "8px 12px",
  borderBottom: "1px solid rgba(255,255,255,0.06)", verticalAlign: "top" };
const fmt = (n) => Number(n || 0).toLocaleString("es-CL");

export default function AuditoriaCreditos() {
  const [d, setD] = useState(null);
  const [dias, setDias] = useState(3);
  const [busy, setBusy] = useState(false);

  const cargar = useCallback((nd) => {
    axios.get(`${API}/api/autocorreo/auditoria-mesa`, { params: { dias: nd } })
      .then(r => setD(r.data)).catch(() => setD({ error: true }));
  }, []);
  useEffect(() => { cargar(dias); }, [dias, cargar]);

  const exportar = async () => {
    setBusy(true);
    try {
      const r = await axios.get(`${API}/api/autocorreo/auditoria-mesa/export-xlsx`,
        { params: { dias }, responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url; a.download = `Auditoria_Creditos_Mesa_${dias}dias.xlsx`; a.click();
      URL.revokeObjectURL(url);
    } catch { window.alert("No fue posible generar el Excel"); }
    setBusy(false);
  };

  if (!d) return <p style={{ color: "#8a8a8a" }}>Cargando auditoría de créditos…</p>;
  if (d.error) return <p style={{ color: "#ef4444" }}>No fue posible cargar la auditoría.</p>;
  const r = d.resumen;

  const Kpi = ({ id, titulo, valor, sub, color }) => (
    <div data-testid={`audit-kpi-${id}`} style={{ ...panel, padding: "0.9rem 1.2rem", flex: "1 1 150px" }}>
      <div style={LBL}>{titulo}</div>
      <div style={{ color: color || "#f5f0e1", fontWeight: 900, fontSize: "1.7rem", lineHeight: 1.1, marginTop: 3 }}>{valor}</div>
      {sub && <div style={{ color: "#7a7a7a", fontSize: "0.6rem", marginTop: 2 }}>{sub}</div>}
    </div>
  );

  return (
    <div data-testid="auditoria-creditos" style={{ background: "#050505", border: `1px solid ${BORDE}`,
      borderRadius: 12, padding: "1.2rem 1.4rem", marginBottom: "1.5rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
        <h3 style={{ margin: 0, color: ORO, fontSize: "0.95rem", letterSpacing: 2, fontFamily: "Georgia, serif" }}>
          📋 AUDITORÍA DE CRÉDITOS — ENVÍOS A MESA</h3>
        <select data-testid="audit-dias" value={dias} onChange={e => setDias(Number(e.target.value))}
          style={{ background: "#080808", border: `1px solid ${BORDE}`, color: "#e8e3d3",
            padding: "0.35rem 0.5rem", borderRadius: 8, fontSize: "0.68rem" }}>
          <option value={3}>Últimos 3 días</option>
          <option value={7}>Últimos 7 días</option>
          <option value={15}>Últimos 15 días</option>
        </select>
        <button data-testid="audit-export-xlsx" onClick={exportar} disabled={busy}
          style={{ marginLeft: "auto", background: ORO, border: "none", color: "#0a0a0a", borderRadius: 8,
            padding: "0.45rem 1rem", cursor: "pointer", fontWeight: 900, fontSize: "0.66rem", letterSpacing: 1 }}>
          <i className="fa fa-file-excel-o" /> {busy ? "GENERANDO…" : "EXPORTAR EXCEL"}
        </button>
      </div>

      {/* ═══ RESUMEN SUPERIOR ═══ */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 14 }}>
        <Kpi id="recibidas" titulo="Solicitudes recibidas" valor={r.recibidas} sub={`últimos ${d.dias} días`} />
        <Kpi id="enviadas" titulo="Enviadas a mesa" valor={r.enviadas_mesa} color="#4ade80"
          sub={`${r.enviadas_sistema} por sistema · ${r.enviadas_correo_directo} por correo directo`} />
        <Kpi id="pendientes" titulo="Pendientes (no enviadas)" valor={r.pendientes}
          color={r.pendientes > 0 ? "#ef4444" : "#4ade80"} sub={r.pendientes > 0 ? "requieren gestión" : "todo derivado"} />
      </div>

      {/* ═══ SECCIÓN 1: ENVIADOS A MESA ═══ */}
      <div style={{ ...LBL, color: "#4ade80", marginBottom: 6 }}>✅ Enviados a mesa ({d.enviados.length})</div>
      <div style={{ ...panel, overflow: "auto", marginBottom: 16, maxHeight: 340 }}>
        <table data-testid="audit-tabla-enviados" style={{ width: "100%", borderCollapse: "collapse", minWidth: 760 }}>
          <thead><tr>{["Cliente", "RUT", "Monto UF", "Ejecutivo responsable", "Recepción", "Envío a mesa", "Vía"].map(h =>
            <th key={h} style={th}>{h}</th>)}</tr></thead>
          <tbody>
            {d.enviados.map((f, i) => (
              <tr key={f.folder_id || i} style={{ background: i % 2 === 0 ? "#0b0b0b" : "#101010" }}>
                <td style={{ ...td, color: "#fff", fontWeight: 700 }}>{f.cliente}</td>
                <td style={{ ...td, fontFamily: "monospace" }}>{f.rut || "—"}</td>
                <td style={{ ...td, textAlign: "right", color: ORO_CLARO, fontWeight: 700 }}>{f.monto_uf ? fmt(f.monto_uf) : "—"}</td>
                <td style={td}>{f.ejecutivo}</td>
                <td style={{ ...td, whiteSpace: "nowrap" }}>{f.fecha_recepcion}</td>
                <td style={{ ...td, whiteSpace: "nowrap", color: "#4ade80", fontWeight: 700 }}>{f.fecha_envio_mesa || "—"}</td>
                <td style={td}><span style={{ fontSize: "0.6rem", fontWeight: 800, padding: "2px 8px", borderRadius: 6,
                  background: f.via === "Sistema" ? "rgba(56,189,248,0.12)" : "rgba(201,162,39,0.14)",
                  color: f.via === "Sistema" ? "#38bdf8" : ORO_CLARO }}>{f.via}</span></td>
              </tr>
            ))}
            {d.enviados.length === 0 && <tr><td colSpan={7} style={{ ...td, textAlign: "center", color: "#7a7a7a" }}>
              Sin envíos a mesa en el período.</td></tr>}
          </tbody>
        </table>
      </div>

      {/* ═══ SECCIÓN 2: NO ENVIADOS A MESA ═══ */}
      <div style={{ ...LBL, color: "#ef4444", marginBottom: 6 }}>⏳ No enviados a mesa ({d.pendientes.length})</div>
      <div style={{ ...panel, overflow: "auto", maxHeight: 420, borderColor: d.pendientes.length ? "rgba(239,68,68,0.35)" : BORDE }}>
        <table data-testid="audit-tabla-pendientes" style={{ width: "100%", borderCollapse: "collapse", minWidth: 760 }}>
          <thead><tr>{["Cliente", "RUT", "Monto UF", "Ejecutivo responsable", "Recepción", "Motivo de retención"].map(h =>
            <th key={h} style={th}>{h}</th>)}</tr></thead>
          <tbody>
            {d.pendientes.map((f, i) => (
              <tr key={f.folder_id || i} style={{ background: i % 2 === 0 ? "#0b0b0b" : "#101010" }}>
                <td style={{ ...td, color: "#fff", fontWeight: 700 }}>{f.cliente}</td>
                <td style={{ ...td, fontFamily: "monospace" }}>{f.rut || "—"}</td>
                <td style={{ ...td, textAlign: "right", color: ORO_CLARO, fontWeight: 700 }}>{f.monto_uf ? fmt(f.monto_uf) : "—"}</td>
                <td style={td}>{f.ejecutivo}</td>
                <td style={{ ...td, whiteSpace: "nowrap" }}>{f.fecha_recepcion}</td>
                <td style={{ ...td, maxWidth: 380 }}>
                  {(f.motivos_retencion || []).map((m, j) => (
                    <div key={j} style={{ color: "#fca5a5", fontSize: "0.68rem", marginBottom: 2 }}>{m}</div>
                  ))}
                </td>
              </tr>
            ))}
            {d.pendientes.length === 0 && <tr><td colSpan={6} style={{ ...td, textAlign: "center", color: "#4ade80" }}>
              🏆 Todas las solicitudes del período fueron derivadas a mesa.</td></tr>}
          </tbody>
        </table>
      </div>
      <p style={{ color: "#6a6a6a", fontSize: "0.6rem", marginTop: 8, marginBottom: 0 }}>
        Cruce automático: envíos por el sistema + envíos directos por correo detectados en el espejo de la casilla de mesa (match por RUT o nombre).
      </p>
    </div>
  );
}
