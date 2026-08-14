import { useState, useEffect } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const PILL = { validado: "#22c55e", observado: "#f59e0b", pendiente: "#94a3b8", expulsado: "#ef4444" };

export default function AdministracionModule({ user }) {
  const nombreU = (user?.nombre || "").toLowerCase();
  const [panel, setPanel] = useState(nombreU.includes("victoria") || nombreU.includes("vilche") ? "victoria" : "daniela");
  const [cartera, setCartera] = useState(null);
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState("");
  const [excModal, setExcModal] = useState(null);
  const [excForm, setExcForm] = useState({ clave: "", justificacion: "" });

  const autorizarExcepcion = async () => {
    try {
      await axios.post(`${API}/api/excepciones/autorizar`, {
        folder_id: excModal, hito: "envio_bodega", ...excForm });
      setExcModal(null); setExcForm({ clave: "", justificacion: "" });
      await cargar();
    } catch (e) { alert(e.response?.data?.detail || "Error"); }
  };

  const cargar = () => axios.get(`${API}/api/bodega`).then(r => setData(r.data)).catch(() => setData({ registros: [] }));
  useEffect(() => {
    cargar();
    axios.get(`${API}/api/gerencia/cartera`).then(r => setCartera(r.data)).catch(() => setCartera(null));
  }, []);

  const contrastar = async (fid) => {
    setBusy(fid);
    try { await axios.post(`${API}/api/bodega/contrastar/${fid}`); await cargar(); } catch (e) { alert(e.response?.data?.detail || "Error"); }
    setBusy("");
  };

  return (
    <div className="module-content" data-testid="administracion-module">
      <div className="clientes-toolbar">
        <h3 style={{ margin: 0, color: "var(--text-primary)", fontSize: "1.05rem" }}>
          <i className="fa fa-database" style={{ marginRight: 8, color: "var(--gold)" }} />Administración — Bodega de Datos Concreces
        </h3>
        <span style={{ color: "var(--text-secondary)", fontSize: "0.72rem" }}>{data?.total ?? 0} registros · Regla de Oro #24: sin contraste RUT/Rol + respaldo OCR, el envío queda bloqueado</span>
      </div>
      {/* DIVISIÓN OPERATIVA (Regla #32) — esqueletos espejo */}
      <div style={{ display: "flex", gap: 10, marginTop: 14, flexWrap: "wrap" }}>
        {[["daniela", "Panel Daniela Galindo", "Operación A — Fase Revisión"],
          ["victoria", "Panel Victoria Vilche", "Operación B — Fase Carga"]].map(([k, t, s]) => (
          <button key={k} data-testid={`panel-${k}`} onClick={() => setPanel(k)}
            style={{ flex: "1 1 240px", textAlign: "left", cursor: "pointer", borderRadius: 12, padding: "0.8rem 1rem",
              background: panel === k ? "linear-gradient(135deg, rgba(212,175,55,0.18), rgba(15,23,42,0.9))" : "rgba(30,41,59,0.55)",
              border: `1.5px solid ${panel === k ? "#d4af37" : "rgba(148,163,184,0.2)"}` }}>
            <div style={{ color: panel === k ? "#d4af37" : "#e2e8f0", fontWeight: 800, fontSize: "0.85rem" }}>{t}</div>
            <div style={{ color: "#94a3b8", fontSize: "0.66rem", marginTop: 2 }}>{s}</div>
          </button>
        ))}
      </div>
      <div data-testid="esqueleto-banner" style={{ marginTop: 10, background: "rgba(212,175,55,0.08)", border: "1px dashed rgba(212,175,55,0.4)", borderRadius: 8, padding: "0.5rem 0.9rem", color: "#d4af37", fontSize: "0.68rem", fontWeight: 700 }}>
        🏗 Esqueleto operativo ({panel === "daniela" ? "Daniela Galindo" : "Victoria Vilche"}) — herramientas espejo activas. Funciones definitivas BLOQUEADAS hasta la instrucción final de roles de Gerardo (Regla de Oro #32).
      </div>
      {cartera && (
        <div data-testid="carpetas-mes-strip" style={{ marginTop: 10, display: "flex", gap: 16, flexWrap: "wrap", color: "var(--text-secondary)", fontSize: "0.72rem" }}>
          <span>📁 Carpetas del mes: <b style={{ color: "var(--text-primary)" }}>{cartera.total}</b></span>
          <span>🚨 Alertas notaría: <b style={{ color: cartera.alertas_notaria ? "#ef4444" : "#22c55e" }}>{cartera.alertas_notaria}</b></span>
          <span>⚠️ Excepciones: <b>{(cartera.excepciones_recientes || []).length}</b></span>
        </div>
      )}
      <div style={{ marginTop: "1rem", overflowX: "auto" }}>
        <table className="history-table" data-testid="bodega-tabla">
          <thead>
            <tr>
              <th>Cliente</th><th>RUT Titular</th><th>RUT Codeudor</th><th>Renta Prom.</th>
              <th>Rol Prop.</th><th>Dirección</th><th>OCR</th><th>Contraste</th><th>Envío</th><th></th>
            </tr>
          </thead>
          <tbody>
            {(data?.registros || []).map(r => (
              <tr key={r.folder_id} data-testid={`bodega-fila-${r.folder_id}`}>
                <td style={{ fontWeight: 700 }}>{r.cliente}</td>
                <td style={{ fontFamily: "monospace" }}>{r.rut_titular || "—"}</td>
                <td style={{ fontFamily: "monospace" }}>{r.rut_codeudor || "—"}</td>
                <td>{r.renta_promedio ? `$${Number(r.renta_promedio).toLocaleString("es-CL")}` : "—"}</td>
                <td>{r.rol_propiedad || "—"}</td>
                <td style={{ fontSize: "0.72rem" }}>{r.direccion || "—"}</td>
                <td>{r.respaldo_ocr ? "✅" : "❌"}</td>
                <td><span title={r.contraste_detalle} style={{ color: PILL[r.contraste] || "#94a3b8", fontWeight: 800, fontSize: "0.7rem", textTransform: "uppercase" }}>{r.contraste}</span></td>
                <td>{r.envio_bloqueado
                  ? <button data-testid={`btn-excepcion-${r.folder_id}`} onClick={() => setExcModal(r.folder_id)}
                      style={{ background: "rgba(239,68,68,0.12)", border: "1px solid #ef4444", color: "#ef4444", borderRadius: 6, padding: "0.25rem 0.5rem", fontWeight: 800, fontSize: "0.62rem", cursor: "pointer" }}
                      title="Autorización de Excepción (Regla #31)">🔒 BLOQUEADO · Excepción</button>
                  : <span style={{ color: "#22c55e", fontWeight: 800, fontSize: "0.68rem" }}>{r.excepcion_autorizada ? `LISTO · Excep. ${r.excepcion_por}` : "LISTO"}</span>}</td>
                <td>
                  <button className="docs-btn secondary" data-testid={`btn-contrastar-${r.folder_id}`}
                    disabled={busy === r.folder_id} onClick={() => contrastar(r.folder_id)} style={{ fontSize: "0.68rem" }}>
                    {busy === r.folder_id ? "…" : "Contrastar RUT/Rol"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && data.registros.length === 0 && <p style={{ color: "var(--text-muted)", textAlign: "center", padding: "2rem" }}>Bodega vacía.</p>}
      </div>
      <div style={{ marginTop: 14, color: "var(--text-secondary)", fontSize: "0.7rem" }}>
        <b>Mapeo Módulo B (Concreces):</b> {Object.keys(data?.mapeo_concreces || {}).join(" · ") || "…"}
      </div>
      {excModal && (
        <div data-testid="modal-excepcion" onClick={() => setExcModal(null)}
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", zIndex: 600, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div onClick={e => e.stopPropagation()} style={{ background: "#111214", border: "1.5px solid #ef4444", borderRadius: 12, padding: "1.5rem", width: 420, maxWidth: "92vw" }}>
            <h4 style={{ color: "#ef4444", margin: "0 0 6px" }}>⚠️ Autorización de Excepción — Regla #31</h4>
            <p style={{ color: "#94a3b8", fontSize: "0.7rem", margin: "0 0 12px", lineHeight: 1.5 }}>
              Va a saltar un bloqueo de las Reglas de Oro. Quedará un registro INMUTABLE con su identidad, motivo, fecha y hora, y se notificará a Gerencia Comercial.
            </p>
            <input data-testid="excepcion-clave" type="password" placeholder="Re-ingrese su clave (firma digital)" value={excForm.clave}
              onChange={e => setExcForm({ ...excForm, clave: e.target.value })}
              style={{ width: "100%", boxSizing: "border-box", background: "rgba(255,255,255,0.06)", border: "1px solid rgba(239,68,68,0.5)", color: "#fff", padding: "0.55rem 0.7rem", borderRadius: 8, marginBottom: 10 }} />
            <textarea data-testid="excepcion-justificacion" placeholder="Justificación de la Excepción (obligatoria)" rows={3} value={excForm.justificacion}
              onChange={e => setExcForm({ ...excForm, justificacion: e.target.value })}
              style={{ width: "100%", boxSizing: "border-box", background: "rgba(255,255,255,0.06)", border: "1px solid rgba(239,68,68,0.5)", color: "#fff", padding: "0.55rem 0.7rem", borderRadius: 8, marginBottom: 12, fontFamily: "inherit" }} />
            <div style={{ display: "flex", gap: 8 }}>
              <button data-testid="excepcion-confirmar" onClick={autorizarExcepcion}
                style={{ flex: 1, background: "#ef4444", color: "#fff", border: "none", borderRadius: 8, padding: "0.55rem", fontWeight: 800, cursor: "pointer" }}>Firmar y Autorizar</button>
              <button onClick={() => setExcModal(null)} style={{ background: "transparent", color: "#94a3b8", border: "1px solid rgba(255,255,255,0.2)", borderRadius: 8, padding: "0.55rem 1rem", cursor: "pointer" }}>Cancelar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
