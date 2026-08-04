import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

const card = {
  border: "1px solid transparent", borderRadius: 0, padding: "1.2rem 1.4rem", marginBottom: "1.1rem",
  backgroundImage: "linear-gradient(115deg, rgba(255,255,255,0.09) 0%, rgba(255,255,255,0.02) 18%, transparent 32%), linear-gradient(160deg, rgba(30,30,30,0.95), rgba(10,10,10,0.98)), linear-gradient(135deg, #BF953F, #FCF6BA, #B38728, #FBF5B7, #AA771C)",
  backgroundOrigin: "border-box", backgroundClip: "padding-box, padding-box, border-box",
  boxShadow: "0 35px 70px -20px rgba(0,0,0,0.95), 0 0 38px -16px rgba(191,149,63,0.45)",
};
const btn = (bg, color = "#0a0a0a") => ({
  background: bg, color, border: "none", borderRadius: 0, padding: "0.5rem 1rem",
  cursor: "pointer", fontWeight: 700, fontSize: "0.78rem", letterSpacing: "0.05em",
});

const INTERES = {
  nuevo: { lbl: "Nuevo", color: "#94a3b8", bg: "rgba(148,163,184,0.12)" },
  abrio_correo: { lbl: "👀 Abrió el correo", color: "#7da2e8", bg: "rgba(46,92,230,0.15)" },
  hizo_clic: { lbl: "⚡ Hizo clic", color: "#e7cf7a", bg: "rgba(212,175,55,0.15)" },
  uso_simulador: { lbl: "🔥 Usó el simulador", color: "#34eab9", bg: "rgba(16,217,142,0.14)" },
};

export default function OportunidadesModule() {
  const [ops, setOps] = useState([]);
  const [resumen, setResumen] = useState(null);
  const [msg, setMsg] = useState("");
  const [preview, setPreview] = useState(null);
  const [busyId, setBusyId] = useState("");
  const fileRef = useRef(null);

  const cargar = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/oportunidades`);
      setOps(r.data.oportunidades || []);
      setResumen(r.data.resumen || null);
    } catch (_e) { setMsg("Error cargando oportunidades"); }
  }, []);
  useEffect(() => { cargar(); }, [cargar]);

  const subirExcel = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const fd = new FormData();
    fd.append("file", f);
    setMsg("Leyendo listado…");
    try {
      const r = await axios.post(`${API}/api/oportunidades/upload-excel`, fd, { timeout: 120000 });
      setMsg(`✅ ${r.data.nuevos} prospectos nuevos cargados (${r.data.duplicados} ya existían). José Martín ya los tiene en la mira.`);
      cargar();
    } catch (err) { setMsg("❌ " + (err.response?.data?.detail || err.message)); }
    e.target.value = "";
  };

  const preparar = async (op) => {
    setBusyId(op.id);
    try {
      const r = await axios.post(`${API}/api/oportunidades/${op.id}/preparar`, {}, { timeout: 60000 });
      setPreview({ ...r.data, id: op.id, bloqueado: bloqueado(op) });
      cargar();
    } catch (err) { setMsg("❌ " + (err.response?.data?.detail || err.message)); }
    setBusyId("");
  };

  const autorizar = async (op) => {
    if (!window.confirm(`🔐 AUTORIZACIÓN DE GERARDO\n\n¿Autorizar el envío del correo de José Martín a ${op.nombre} (${op.email})?\n\nTras el envío se activa el bloqueo de seguimiento de 14 días.`)) return;
    setBusyId(op.id);
    try {
      const r = await axios.post(`${API}/api/oportunidades/${op.id}/autorizar`, { confirm: true }, { timeout: 120000 });
      setMsg(`📨 Enviado a ${r.data.to}. Seguimiento bloqueado hasta ${(r.data.bloqueado_hasta || "").slice(0, 10)}.`);
      setPreview(null);
      cargar();
    } catch (err) { setMsg("❌ " + (err.response?.data?.detail || err.message)); }
    setBusyId("");
  };

  const borrar = async (op) => {
    if (!window.confirm(`¿Eliminar la oportunidad de ${op.nombre}?`)) return;
    await axios.delete(`${API}/api/oportunidades/${op.id}`).catch(() => {});
    cargar();
  };

  const bloqueado = (op) => op.bloqueado_hasta && op.bloqueado_hasta > new Date().toISOString();

  return (
    <div className="module-content" data-testid="oportunidades-module">
      <div style={card}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <i className="fa fa-diamond" style={{ color: "var(--gold)", fontSize: "1.3rem" }} />
          <div>
            <h3 style={{ margin: 0, fontSize: "1.05rem" }}>Centro de Ventas VIP — José Martín Benavente</h3>
            <div style={{ fontSize: "0.78rem", color: "#94a3b8", marginTop: 4 }}>
              🔐 Modo supervisión: ningún correo sale sin tu "Autorizar Envío" · bloqueo de seguimiento de 14 días tras cada envío
            </div>
          </div>
          <div style={{ marginLeft: "auto", display: "flex", gap: 10 }}>
            <input ref={fileRef} type="file" accept=".xlsx,.xls" style={{ display: "none" }} onChange={subirExcel} data-testid="op-upload-input" />
            <button data-testid="op-upload-btn" onClick={() => fileRef.current?.click()} style={btn("linear-gradient(135deg, #BF953F, #FCF6BA 45%, #B38728)")}>
              <i className="fa fa-file-excel-o" style={{ marginRight: 6 }} />Subir listado Excel
            </button>
          </div>
        </div>
        {resumen && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "0.7rem", marginTop: "1rem" }}>
            {[
              { lbl: "En cartera", val: resumen.total, color: "#e7cf7a" },
              { lbl: "Abrieron correo", val: resumen.abrieron, color: "#7da2e8" },
              { lbl: "🔥 Calientes", val: resumen.calientes, color: "#34eab9" },
              { lbl: "Esperando autorización", val: resumen.pendientes, color: "#fb7185" },
            ].map((s, i) => (
              <div key={i} data-testid={`op-stat-${i}`} style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(212,175,55,0.2)", padding: "0.6rem 0.9rem", textAlign: "center" }}>
                <div style={{ fontSize: "1.5rem", fontWeight: 800, color: s.color, fontFamily: "'JetBrains Mono', monospace" }}>{s.val}</div>
                <div style={{ fontSize: "0.68rem", opacity: 0.7, textTransform: "uppercase", letterSpacing: "0.08em" }}>{s.lbl}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {resumen?.nota && (
        <div style={{ ...card, borderLeft: "3px solid var(--gold)" }} data-testid="op-nota-diaria">
          <div style={{ fontSize: "0.68rem", letterSpacing: "0.16em", textTransform: "uppercase", color: "#94a3b8", fontWeight: 700, marginBottom: 8 }}>
            <i className="fa fa-commenting-o" style={{ marginRight: 6 }} />Nota diaria de José Martín
          </div>
          <div style={{ whiteSpace: "pre-wrap", fontSize: "0.9rem", lineHeight: 1.7, color: "#e2e8f0" }}>{resumen.nota}</div>
        </div>
      )}

      {msg && <div data-testid="op-msg" style={{ ...card, padding: "0.7rem 1rem", fontSize: "0.85rem" }}>{msg}</div>}

      <div style={card}>
        <table style={{ width: "100%", fontSize: "0.85rem" }} data-testid="op-tabla">
          <thead><tr>
            <th style={{ textAlign: "left", padding: "0.5rem" }}>Prospecto</th>
            <th style={{ textAlign: "left", padding: "0.5rem" }}>Contacto</th>
            <th style={{ textAlign: "left", padding: "0.5rem" }}>Interés</th>
            <th style={{ textAlign: "left", padding: "0.5rem" }}>Estado</th>
            <th style={{ textAlign: "right", padding: "0.5rem" }}>Acciones</th>
          </tr></thead>
          <tbody>
            {ops.map((op, i) => {
              const it = INTERES[op.estado_interes] || INTERES.nuevo;
              return (
                <tr key={op.id} data-testid={`op-row-${i}`}>
                  <td style={{ padding: "0.6rem 0.5rem" }}>
                    <b style={{ color: "#f8fafc" }}>{op.nombre}</b>
                    {op.expediente_vip && <span style={{ marginLeft: 8, color: "var(--gold)", fontSize: "0.72rem", fontWeight: 700 }}>✦ EXPEDIENTE VIP</span>}
                    {op.proyecto && <div style={{ fontSize: "0.72rem", color: "#94a3b8" }}>{op.proyecto}</div>}
                  </td>
                  <td style={{ padding: "0.6rem 0.5rem", fontSize: "0.78rem", color: "#cbd5e1" }}>
                    {op.email || "—"}{op.telefono ? <div style={{ color: "#94a3b8" }}>{op.telefono}</div> : null}
                  </td>
                  <td style={{ padding: "0.6rem 0.5rem" }}>
                    <span style={{ background: it.bg, color: it.color, padding: "3px 9px", fontSize: "0.72rem", fontWeight: 700 }}>{it.lbl}</span>
                    {(op.aperturas > 0 || op.clics > 0) && <div style={{ fontSize: "0.68rem", color: "#94a3b8", marginTop: 3 }}>{op.aperturas} aperturas · {op.clics} clics</div>}
                  </td>
                  <td style={{ padding: "0.6rem 0.5rem", fontSize: "0.75rem" }}>
                    {op.status === "enviado"
                      ? <span style={{ color: "#34eab9", fontWeight: 700 }}>📨 Enviado{bloqueado(op) ? <div style={{ color: "#94a3b8", fontWeight: 400 }}>🔒 hasta {(op.bloqueado_hasta || "").slice(0, 10)}</div> : null}</span>
                      : op.status === "expediente_vip"
                        ? <span style={{ color: "var(--gold)", fontWeight: 700 }}>✦ Desde simulador</span>
                        : <span style={{ color: "#fb7185", fontWeight: 700 }}>Esperando autorización</span>}
                  </td>
                  <td style={{ padding: "0.6rem 0.5rem", textAlign: "right", whiteSpace: "nowrap" }}>
                    <button data-testid={`op-preparar-${i}`} onClick={() => preparar(op)} disabled={busyId === op.id}
                      style={{ ...btn("rgba(212,175,55,0.15)", "#e7cf7a"), border: "1px solid rgba(212,175,55,0.4)", marginRight: 6 }}>
                      {busyId === op.id ? "…" : (op.borrador ? "Ver borrador" : "Preparar borrador")}
                    </button>
                    <button data-testid={`op-autorizar-${i}`} onClick={() => autorizar(op)}
                      disabled={busyId === op.id || !op.borrador || !op.email || bloqueado(op)}
                      title={bloqueado(op) ? `Bloqueado hasta ${(op.bloqueado_hasta || "").slice(0, 10)}` : ""}
                      style={{ ...btn("linear-gradient(135deg, #BF953F, #FCF6BA 45%, #B38728)"), marginRight: 6, opacity: (!op.borrador || !op.email || bloqueado(op)) ? 0.35 : 1 }}>
                      🔐 Autorizar Envío
                    </button>
                    <button data-testid={`op-borrar-${i}`} onClick={() => borrar(op)} style={{ ...btn("transparent", "#fb7185"), border: "1px solid rgba(225,29,72,0.4)" }}>
                      <i className="fa fa-trash-o" />
                    </button>
                  </td>
                </tr>
              );
            })}
            {ops.length === 0 && <tr><td colSpan={5} style={{ padding: "1.5rem", textAlign: "center", color: "#94a3b8" }}>Sube un listado Excel y José Martín prepara las propuestas — tú solo autorizas.</td></tr>}
          </tbody>
        </table>
      </div>

      {preview && (
        <div data-testid="op-preview-modal" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.8)", zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem" }}>
          <div style={{ ...card, width: "min(680px, 96vw)", maxHeight: "88vh", overflow: "auto", marginBottom: 0 }}>
            <div style={{ display: "flex", alignItems: "center", marginBottom: 10 }}>
              <b style={{ color: "var(--gold)" }}>Borrador de José Martín — {preview.nombre}</b>
              <button data-testid="op-preview-cerrar" onClick={() => setPreview(null)} style={{ ...btn("transparent", "#94a3b8"), marginLeft: "auto", fontSize: "1rem" }}>✕</button>
            </div>
            <div style={{ fontSize: "0.8rem", color: "#cbd5e1", marginBottom: 8 }}>Para: <b>{preview.to || "⚠️ sin correo"}</b> · Asunto: {preview.subject}</div>
            <div style={{ background: "#fff", padding: "1rem", maxHeight: "50vh", overflow: "auto" }} dangerouslySetInnerHTML={{ __html: preview.body }} />
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 12 }}>
              <button onClick={() => setPreview(null)} style={{ ...btn("transparent", "#94a3b8"), border: "1px solid #444" }}>Cerrar</button>
              <button data-testid="op-preview-autorizar" onClick={() => autorizar({ id: preview.id, nombre: preview.nombre, email: preview.to })}
                disabled={!preview.to || preview.bloqueado} style={{ ...btn("linear-gradient(135deg, #BF953F, #FCF6BA 45%, #B38728)"), opacity: (!preview.to || preview.bloqueado) ? 0.35 : 1 }}>
                🔐 Autorizar Envío
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
