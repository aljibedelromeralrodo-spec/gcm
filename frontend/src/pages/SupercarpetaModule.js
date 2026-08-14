import { useState, useEffect } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const INFORMES = [["tasacion", "Tasación"], ["estudio", "Estudio Títulos"], ["borrador", "Borrador Escritura"]];

export default function SupercarpetaModule() {
  const [data, setData] = useState(null);
  const [solo24, setSolo24] = useState(false);
  const [preview, setPreview] = useState(null);
  const [reparoModal, setReparoModal] = useState(null);
  const [bitModal, setBitModal] = useState(null);

  const verBitacora = async (c, hito) => {
    setBitModal({ cliente: c.cliente, loading: true });
    try {
      const r = await axios.get(`${API}/api/supercarpeta/bitacora/${c.id}?hito=${hito}`);
      setBitModal({ cliente: c.cliente, loading: false, ...r.data });
    } catch (e) {
      setBitModal({ cliente: c.cliente, loading: false, error_seguimiento: true,
        detalle: e.response?.data?.detail || "Error consultando la bitácora" });
    }
  };

  useEffect(() => {
    axios.get(`${API}/api/supercarpeta`).then(r => setData(r.data)).catch(() => setData({ clientes: [] }));
  }, []);

  const abrir = async (fid, cliente, inf) => {
    try {
      const r = await axios.get(`${API}/api/supercarpeta/archivo/${fid}`, {
        params: { ruta: inf.archivo }, responseType: "blob" });
      const url = URL.createObjectURL(new Blob([r.data], { type: "application/pdf" }));
      setPreview({ url, cliente, archivo: inf.archivo });
    } catch (e) { window.alert(e.response?.status === 404 ? "Informe no disponible" : "Error al abrir el informe"); }
  };

  const clientes = (data?.clientes || []).filter(c => !solo24 || c.recien_24h);

  return (
    <div className="module-content seamless-scope" data-testid="supercarpeta-module" style={{ minHeight: "100%", padding: "1.1rem", borderRadius: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 10 }}>
        <h3 style={{ margin: 0, color: "#f8fafc", fontSize: "1.02rem" }}>
          <i className="fa fa-folder folder-metal" style={{ marginRight: 8 }} />Supercarpeta de Management — {data?.mes || "…"}
        </h3>
        <span style={{ color: "#94a3b8", fontSize: "0.7rem" }}>
          {clientes.length}/{data?.total ?? 0} clientes · Regla #55: disponibilidad física de informes del mes corriente
        </span>
        <button data-testid="filtro-recien-24h" onClick={() => setSolo24(v => !v)}
          className={`maserati-btn ${solo24 ? "" : "neon"}`} style={{ marginLeft: "auto", minHeight: 38 }}>
          🟢 Recién llegados 24h ({data?.recien_llegados ?? 0}) {solo24 ? "· quitar filtro" : ""}
        </button>
      </div>
      <div style={{ background: "rgba(30,41,59,0.5)", border: "1px solid rgba(148,163,184,0.18)", borderRadius: 14, overflowX: "auto" }}>
        <table data-testid="supercarpeta-tabla" style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.72rem", color: "#e2e8f0" }}>
          <thead>
            <tr style={{ color: "#94a3b8", fontSize: "0.6rem", textTransform: "uppercase", letterSpacing: "0.1em" }}>
              {["Cliente", "RUT", "Inmobiliaria / Broker", "Estado Tasación", "Estudio de Títulos", "Estado Legal", "Detalle de Reparos", "Cesión / Transacción"].map(h =>
                <th key={h} style={{ padding: "0.5rem 0.7rem", textAlign: "left", borderBottom: "1px solid rgba(148,163,184,0.15)" }}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {clientes.map(c => (
              <tr key={c.id} data-testid={`super-fila-${c.id}`}
                className={c.recien_24h ? "neon-verde" : ""}
                style={{ borderBottom: "1px solid rgba(148,163,184,0.07)", height: 34 }}>
                <td style={{ padding: "0.3rem 0.7rem", fontWeight: 700, color: "#f8fafc", whiteSpace: "nowrap" }}>
                  <i className="fa fa-folder folder-metal" style={{ marginRight: 6, fontSize: "0.85rem" }} />{c.cliente}
                  {c.recien_24h && <span data-testid={`recien-${c.id}`} style={{ marginLeft: 6, color: "#22c55e", fontSize: "0.56rem", fontWeight: 800 }}>● NUEVO 24H</span>}
                </td>
                <td style={{ padding: "0.3rem 0.7rem", fontFamily: "monospace", fontSize: "0.66rem" }}>{c.rut || "—"}</td>
                <td style={{ padding: "0.3rem 0.7rem", color: (c.broker_origen || "").startsWith("⚠️") ? "#ef4444" : "#38bdf8", fontSize: "0.62rem" }}>{c.broker_origen}</td>
                <td data-testid={`super-tasacion-${c.id}`} style={{ padding: "0.3rem 0.7rem", fontSize: "0.62rem" }}>
                  <button data-testid={`bitacora-tasacion-${c.id}`} onClick={() => verBitacora(c, "tasacion")}
                    title="Bitácora de tiempos: cuándo se solicitó, a quién y días transcurridos"
                    style={{ cursor: "pointer", border: "none", background: "transparent", padding: 0, fontWeight: 800,
                      color: c.estado_tasacion === "Informe Recibido" ? "#22c55e"
                        : c.estado_tasacion === "Visita" ? "#38bdf8" : c.estado_tasacion === "Solicitada" ? "#f59e0b" : "#ef4444" }}>
                    {c.estado_tasacion === "Informe Recibido" ? "✅ " : c.estado_tasacion === "Pendiente" ? "🔴 " : ""}{c.estado_tasacion === "Pendiente" ? "PENDIENTE" : c.estado_tasacion}
                  </button>
                  {c.bitacora?.tasacion?.demora_48h &&
                    <div style={{ color: "#ef4444", fontWeight: 800, fontSize: "0.56rem" }}>
                      🔴 {c.bitacora.tasacion.fecha_solicitud?.slice(0, 10)} · +48h sin respuesta</div>}
                  {c.bitacora?.tasacion?.error_seguimiento && c.estado_tasacion !== "Informe Recibido" &&
                    <div style={{ color: "#ef4444", fontWeight: 800, fontSize: "0.56rem" }}>ERROR DE SEGUIMIENTO</div>}
                  {c.informes?.tasacion?.disponible && (
                    <button data-testid={`ver-tasacion-${c.id}`} onClick={() => abrir(c.id, c.cliente, c.informes.tasacion)}
                      title={`${c.informes.tasacion.archivo} · ${(c.informes.tasacion.fecha || "").slice(0, 16).replace("T", " ")}`}
                      style={{ display: "block", marginTop: 2, cursor: "pointer", background: "rgba(34,197,94,0.12)",
                        border: "1px solid rgba(34,197,94,0.5)", color: "#22c55e", borderRadius: 8,
                        padding: "0.15rem 0.5rem", fontSize: "0.58rem", fontWeight: 800 }}>📄 Ver PDF</button>
                  )}
                </td>
                <td data-testid={`super-estudio-${c.id}`} style={{ padding: "0.3rem 0.7rem", fontSize: "0.62rem" }}>
                  <span style={{ fontWeight: 800, color: c.estudio_titulos === "Aprobado" ? "#22c55e"
                    : c.estudio_titulos === "Con Reparos" ? "#f97316" : "#94a3b8" }}>
                    {c.estudio_titulos === "Aprobado" ? "✅ " : c.estudio_titulos === "Con Reparos" ? "⚠️ " : "⏳ "}{c.estudio_titulos}
                  </span>
                  {c.informes?.estudio?.disponible && (
                    <button data-testid={`ver-estudio-${c.id}`} onClick={() => abrir(c.id, c.cliente, c.informes.estudio)}
                      title={`${c.informes.estudio.archivo} · ${(c.informes.estudio.fecha || "").slice(0, 16).replace("T", " ")}`}
                      style={{ display: "block", marginTop: 2, cursor: "pointer", background: "rgba(34,197,94,0.12)",
                        border: "1px solid rgba(34,197,94,0.5)", color: "#22c55e", borderRadius: 8,
                        padding: "0.15rem 0.5rem", fontSize: "0.58rem", fontWeight: 800 }}>📄 Ver PDF</button>
                  )}
                </td>
                <td data-testid={`super-legal-${c.id}`} style={{ padding: "0.3rem 0.7rem", fontSize: "0.62rem" }}>
                  {c.estado_legal === "⚠️ Con Reparos"
                    ? <button data-testid={`super-legal-btn-${c.id}`} onClick={() => setReparoModal({ cliente: c.cliente, texto: c.detalle_reparos })}
                        title="Pinche para leer el texto íntegro del reparo extraído del correo"
                        style={{ cursor: "pointer", border: "none", borderRadius: 8, fontWeight: 800,
                          fontSize: "0.6rem", padding: "2px 8px", background: "rgba(249,115,22,0.18)", color: "#f97316" }}>
                        ⚠️ Con Reparos</button>
                    : <button data-testid={`bitacora-legal-${c.id}`} onClick={() => verBitacora(c, "estudio")}
                        title="Bitácora de tiempos del estudio de títulos"
                        style={{ cursor: "pointer", border: "none", background: "transparent", padding: 0,
                          fontWeight: 800, color: c.estado_legal === "✅ Limpio" ? "#22c55e" : "#f59e0b" }}>
                        {c.estado_legal}
                        {c.bitacora?.estudio?.demora_48h &&
                          <span style={{ display: "block", color: "#ef4444", fontSize: "0.56rem" }}>
                            🔴 {c.bitacora.estudio.fecha_solicitud?.slice(0, 10)} · +48h</span>}
                        {c.bitacora?.estudio?.error_seguimiento && c.estado_legal === "⏳ En Proceso" &&
                          <span style={{ display: "block", color: "#ef4444", fontSize: "0.56rem" }}>ERROR DE SEGUIMIENTO</span>}
                      </button>}
                </td>
                <td data-testid={`super-reparos-${c.id}`} style={{ padding: "0.3rem 0.7rem", fontSize: "0.6rem", maxWidth: 260,
                  background: c.detalle_reparos ? "rgba(249,115,22,0.14)" : undefined,
                  color: c.detalle_reparos ? "#f97316" : "#64748b" }}
                  title={c.detalle_reparos || "Sin reparos detectados"}>
                  {c.detalle_reparos
                    ? <span style={{ fontWeight: 700, display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>{c.detalle_reparos}</span>
                    : "—"}
                </td>
                <td data-testid={`super-cesion-${c.id}`} style={{ padding: "0.3rem 0.7rem", fontSize: "0.62rem" }}>
                  <span style={{ fontWeight: 800, color: c.cesion === "Confirmada" ? "#22c55e" : "#94a3b8" }}>
                    {c.cesion === "Confirmada" ? "✅ Confirmada" : "⏳ Pendiente"}
                  </span>
                  {c.informes?.borrador?.disponible && (
                    <button data-testid={`ver-borrador-${c.id}`} onClick={() => abrir(c.id, c.cliente, c.informes.borrador)}
                      title={`${c.informes.borrador.archivo}`}
                      style={{ display: "block", marginTop: 2, cursor: "pointer", background: "rgba(34,197,94,0.12)",
                        border: "1px solid rgba(34,197,94,0.5)", color: "#22c55e", borderRadius: 8,
                        padding: "0.15rem 0.5rem", fontSize: "0.58rem", fontWeight: 800 }}>📄 Borrador</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && clientes.length === 0 && <p style={{ color: "#94a3b8", textAlign: "center", padding: "1.5rem" }}>Sin clientes {solo24 ? "con informes en las últimas 24h" : "en el mes corriente"}.</p>}
        {bitModal && (
          <div data-testid="bitacora-modal" onClick={() => setBitModal(null)}
            style={{ position: "fixed", inset: 0, zIndex: 220, background: "rgba(2,6,23,0.8)",
              backdropFilter: "blur(8px)", display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem" }}>
            <div onClick={e => e.stopPropagation()} style={{ width: "100%", maxWidth: 520, background: "rgba(15,23,42,0.97)",
              borderRadius: 16, padding: "1.4rem 1.6rem", boxShadow: "0 30px 80px rgba(0,0,0,0.6)" }}>
              <h4 style={{ margin: 0, color: "#d4af37", fontSize: "0.9rem" }}>
                🕐 Bitácora de Tiempos — {bitModal.cliente} · {bitModal.hito === "estudio" ? "Estudio de Títulos" : "Tasación"}
              </h4>
              {bitModal.loading && <p style={{ color: "#94a3b8", fontSize: "0.7rem" }}>Consultando registros…</p>}
              {!bitModal.loading && bitModal.error_seguimiento && (
                <div style={{ marginTop: 10, padding: "0.8rem 1rem", background: "rgba(239,68,68,0.12)",
                  borderLeft: "3px solid #ef4444", borderRadius: 8 }}>
                  <b style={{ color: "#ef4444", fontSize: "0.78rem" }}>⛔ ERROR DE SEGUIMIENTO</b>
                  <p style={{ color: "#f8fafc", fontSize: "0.68rem", margin: "6px 0 0" }}>
                    {bitModal.detalle || "No hay registro de cuándo se solicitó este hito (Regla de Hierro)."}</p>
                </div>
              )}
              {!bitModal.loading && !bitModal.error_seguimiento && (
                <div style={{ marginTop: 10, fontSize: "0.72rem", color: "#e2e8f0", display: "grid", gap: 8 }}>
                  <div>📅 <b>Fecha de solicitud:</b>{" "}
                    <span style={{ color: bitModal.demora_48h ? "#ef4444" : "#22c55e", fontWeight: 800 }}>
                      {(bitModal.fecha_solicitud || "").replace("T", " ")}</span>
                    {bitModal.demora_48h && <b style={{ color: "#ef4444" }}> · 🔴 +48h SIN RESPUESTA (cuello de botella)</b>}
                  </div>
                  <div>📨 <b>Destinatario:</b> {bitModal.destinatario || "—"} <span style={{ color: "#64748b" }}>({bitModal.fuente})</span></div>
                  <div>⏱ <b>Días transcurridos:</b>{" "}
                    <span style={{ fontWeight: 800, color: bitModal.demora_48h ? "#ef4444" : "#f59e0b" }}>
                      {bitModal.dias_transcurridos ?? "?"} día(s) ({bitModal.horas_transcurridas ?? "?"} h)</span></div>
                  <div>{bitModal.respondido
                    ? <span style={{ color: "#22c55e", fontWeight: 800 }}>✅ Respondido el {(bitModal.respondido_at || "").replace("T", " ")}</span>
                    : <span style={{ color: "#f59e0b", fontWeight: 800 }}>⏳ Aún sin respuesta</span>}</div>
                  <div style={{ padding: "0.6rem 0.8rem", background: "rgba(212,175,55,0.08)",
                    borderLeft: "3px solid #d4af37", borderRadius: 8 }}>
                    <b style={{ color: "#d4af37", fontSize: "0.62rem" }}>QUÉ SE PIDIÓ (extracto del correo):</b>
                    <div style={{ marginTop: 4, whiteSpace: "pre-wrap" }}>{bitModal.resumen || "—"}</div>
                  </div>
                </div>
              )}
              <button data-testid="bitacora-cerrar" onClick={() => setBitModal(null)} className="maserati-btn" style={{ marginTop: 14 }}>Cerrar</button>
            </div>
          </div>
        )}
        {reparoModal && (
          <div data-testid="super-reparo-modal" onClick={() => setReparoModal(null)}
            style={{ position: "fixed", inset: 0, zIndex: 210, background: "rgba(2,6,23,0.8)",
              backdropFilter: "blur(8px)", display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem" }}>
            <div onClick={e => e.stopPropagation()} style={{ width: "100%", maxWidth: 560, maxHeight: "78vh", overflowY: "auto",
              background: "rgba(15,23,42,0.97)", borderRadius: 16, padding: "1.4rem 1.6rem", boxShadow: "0 30px 80px rgba(0,0,0,0.6)" }}>
              <h4 style={{ margin: 0, color: "#f97316", fontSize: "0.9rem" }}>⚠️ Reparo extraído del correo — {reparoModal.cliente}</h4>
              <div style={{ marginTop: 10, padding: "0.8rem 1rem", background: "rgba(249,115,22,0.1)",
                borderLeft: "3px solid #f97316", borderRadius: 8, color: "#f8fafc", fontSize: "0.72rem", whiteSpace: "pre-wrap" }}>
                {reparoModal.texto || "Sin texto registrado."}
              </div>
              <button data-testid="super-reparo-cerrar" onClick={() => setReparoModal(null)} className="maserati-btn" style={{ marginTop: 14 }}>Cerrar</button>
            </div>
          </div>
        )}
      </div>
      {preview && (
        <div data-testid="super-preview-modal" onClick={() => { URL.revokeObjectURL(preview.url); setPreview(null); }}
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)", zIndex: 800, display: "flex", alignItems: "center", justifyContent: "center", padding: "2vh 2vw" }}>
          <div onClick={e => e.stopPropagation()} style={{ background: "#111214", border: "1.5px solid #d4af37", borderRadius: 12, width: "min(960px,96vw)", height: "92vh", display: "flex", flexDirection: "column" }}>
            <div style={{ display: "flex", alignItems: "center", padding: "0.6rem 1rem", gap: 10 }}>
              <b style={{ color: "#d4af37", fontSize: "0.8rem" }}>📄 {preview.cliente}</b>
              <span style={{ color: "#94a3b8", fontSize: "0.66rem" }}>{preview.archivo}</span>
              <button onClick={() => { URL.revokeObjectURL(preview.url); setPreview(null); }}
                style={{ marginLeft: "auto", background: "transparent", border: "1px solid rgba(255,255,255,0.25)", color: "#e2e8f0", borderRadius: 8, padding: "0.25rem 0.7rem", cursor: "pointer" }}>✕ Cerrar</button>
            </div>
            <iframe title="preview" src={preview.url} style={{ flex: 1, border: "none", borderRadius: "0 0 12px 12px", background: "#fff" }} />
          </div>
        </div>
      )}
    </div>
  );
}
