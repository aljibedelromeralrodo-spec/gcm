import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import GestorFuentesIMAP from "../components/GestorFuentesIMAP";

const API = process.env.REACT_APP_BACKEND_URL;
const PILL = { validado: "#22c55e", observado: "#f59e0b", pendiente: "#94a3b8", expulsado: "#ef4444" };
const inp = { background: "rgba(255,255,255,0.06)", border: "1px solid rgba(212,175,55,0.3)", color: "#fff", padding: "0.4rem 0.6rem", borderRadius: 8, fontSize: "0.72rem", boxSizing: "border-box" };
const goldBtn = { background: "linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C)", color: "#0a0a0a", border: "none", borderRadius: 8, padding: "0.35rem 0.8rem", fontWeight: 800, cursor: "pointer", fontSize: "0.68rem" };
const card = { background: "rgba(30,41,59,0.55)", border: "1px solid rgba(148,163,184,0.2)", borderRadius: 12, padding: "1rem", marginTop: 14 };

const PANELES = [
  ["daniela", "Panel Daniela Galindo", "Operación A — Fase Revisión"],
  ["victoria", "Panel Victoria Vilche", "Operación B — Fase Carga · Estudio de Títulos"],
  ["postventa", "Panel Postventa", "Seguimiento posterior a la entrega"],
];

// ── FLUJOS VICTORIA: [🏠 Vivienda Usada] vs [🏢 Vivienda Inmobiliaria] (Regla #37)
const FlujosVictoria = () => {
  const [tab, setTab] = useState("usada");
  const [carpetas, setCarpetas] = useState([]);
  const [inmos, setInmos] = useState([]);
  const [vend, setVend] = useState({});
  const [inmoForm, setInmoForm] = useState({ inmobiliaria: "", encargado: "", email: "", telefono: "" });
  const [msg, setMsg] = useState("");

  const cargar = useCallback(() => {
    axios.get(`${API}/api/flujos/carpetas`).then(r => setCarpetas(r.data.carpetas || [])).catch(() => {});
    axios.get(`${API}/api/flujos/inmobiliarias`).then(r => setInmos(r.data.contactos || [])).catch(() => {});
  }, []);
  useEffect(() => { cargar(); }, [cargar]);

  const guardarVendedor = async (fid) => {
    try {
      await axios.post(`${API}/api/flujos/vendedor/${fid}`, vend[fid] || {});
      setMsg("✅ Vendedor guardado — DashAI archiva sus documentos bajo el RUT del cliente (Regla #37)");
      cargar();
    } catch (e) { setMsg(`⛔ ${e.response?.data?.detail || "Error"}`); }
  };

  const asignarInmo = async (fid, contacto_id) => {
    if (!contacto_id) return;
    try {
      await axios.post(`${API}/api/flujos/inmobiliaria/${fid}`, { contacto_id });
      setMsg("✅ Contacto inmobiliario permanente asignado");
      cargar();
    } catch (e) { setMsg(`⛔ ${e.response?.data?.detail || "Error"}`); }
  };

  const guardarInmo = async () => {
    try {
      await axios.post(`${API}/api/flujos/inmobiliarias`, inmoForm);
      setInmoForm({ inmobiliaria: "", encargado: "", email: "", telefono: "" });
      setMsg("✅ Contacto inmobiliario guardado");
      cargar();
    } catch (e) { setMsg(`⛔ ${e.response?.data?.detail || "Error"}`); }
  };

  const setV = (fid, k, v) => setVend(s => ({ ...s, [fid]: { ...(s[fid] || {}), [k]: v } }));

  return (
    <div style={card} data-testid="flujos-victoria">
      <div style={{ color: "#d4af37", fontWeight: 800, fontSize: "0.8rem", marginBottom: 6 }}>
        ⚖️ División de Estudio de Títulos — Fuentes Transitorias vs Permanentes (Regla #37)
      </div>
      <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
        {[["usada", "🏠 Vivienda Usada"], ["inmobiliaria", "🏢 Vivienda Inmobiliaria"]].map(([k, t]) => (
          <button key={k} data-testid={`flujos-tab-${k}`} onClick={() => setTab(k)}
            style={{ ...goldBtn, background: tab === k ? goldBtn.background : "rgba(255,255,255,0.08)", color: tab === k ? "#0a0a0a" : "#e2e8f0" }}>{t}</button>
        ))}
      </div>
      {msg && <p data-testid="flujos-msg" style={{ color: msg.startsWith("✅") ? "#22c55e" : "#ef4444", fontSize: "0.68rem" }}>{msg}</p>}
      {tab === "usada" && (
        <div data-testid="flujos-usada">
          <p style={{ color: "#94a3b8", fontSize: "0.66rem", margin: "0 0 8px" }}>
            Fuente TRANSITORIA: ingrese el correo del Vendedor por carpeta. DashAI rastrea y archiva sus documentos
            bajo el RUT del cliente. REGLA DE HIERRO: el RUT es el único eje que une vendedor y estudio del abogado.
          </p>
          {carpetas.map(c => (
            <div key={c.id} data-testid={`flujos-usada-${c.id}`} style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center", padding: "0.45rem 0", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
              <span style={{ color: "#f8fafc", fontWeight: 700, fontSize: "0.72rem", flex: "1 1 160px" }}>
                {c.nombre} <span style={{ color: "#64748b", fontFamily: "monospace", fontSize: "0.62rem" }}>{c.rut}</span>
                {c.tipo_operacion === "usada" && <span style={{ color: "#22c55e", fontSize: "0.6rem", marginLeft: 6 }}>USADA ✓</span>}
                {(c.reparos || []).length > 0 && <span data-testid={`flujos-reparo-${c.id}`} style={{ color: "#ef4444", fontSize: "0.6rem", marginLeft: 6, fontWeight: 800 }}>⚠️ {c.reparos.length} REPARO(S)</span>}
              </span>
              <input style={{ ...inp, flex: "0 1 130px" }} placeholder="Vendedor" value={(vend[c.id]?.nombre) ?? (c.vendedor_usada?.nombre || "")} onChange={e => setV(c.id, "nombre", e.target.value)} />
              <input data-testid={`flujos-vendedor-email-${c.id}`} style={{ ...inp, flex: "0 1 180px" }} placeholder="correo@vendedor.cl" value={(vend[c.id]?.email) ?? (c.vendedor_usada?.email || "")} onChange={e => setV(c.id, "email", e.target.value)} />
              <input style={{ ...inp, flex: "0 1 110px" }} placeholder="Teléfono" value={(vend[c.id]?.telefono) ?? (c.vendedor_usada?.telefono || "")} onChange={e => setV(c.id, "telefono", e.target.value)} />
              <button data-testid={`flujos-vendedor-guardar-${c.id}`} style={goldBtn} onClick={() => guardarVendedor(c.id)}>Guardar</button>
            </div>
          ))}
        </div>
      )}
      {tab === "inmobiliaria" && (
        <div data-testid="flujos-inmobiliaria">
          <p style={{ color: "#94a3b8", fontSize: "0.66rem", margin: "0 0 8px" }}>
            Fuente PERMANENTE: contactos inmobiliarios reutilizables (Maestra, Comac, Bestal…). El encargado del
            proyecto es el Contacto de Visita para coordinar con Value Property.
          </p>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
            <input data-testid="inmo-nombre" style={{ ...inp, flex: "0 1 140px" }} placeholder="Inmobiliaria" value={inmoForm.inmobiliaria} onChange={e => setInmoForm({ ...inmoForm, inmobiliaria: e.target.value })} />
            <input data-testid="inmo-encargado" style={{ ...inp, flex: "0 1 140px" }} placeholder="Encargado" value={inmoForm.encargado} onChange={e => setInmoForm({ ...inmoForm, encargado: e.target.value })} />
            <input data-testid="inmo-email" style={{ ...inp, flex: "0 1 180px" }} placeholder="correo@inmobiliaria.cl" value={inmoForm.email} onChange={e => setInmoForm({ ...inmoForm, email: e.target.value })} />
            <input data-testid="inmo-telefono" style={{ ...inp, flex: "0 1 110px" }} placeholder="Teléfono" value={inmoForm.telefono} onChange={e => setInmoForm({ ...inmoForm, telefono: e.target.value })} />
            <button data-testid="inmo-guardar" style={goldBtn} onClick={guardarInmo}>+ Guardar contacto</button>
          </div>
          {carpetas.map(c => (
            <div key={c.id} data-testid={`flujos-inmo-${c.id}`} style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", padding: "0.45rem 0", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
              <span style={{ color: "#f8fafc", fontWeight: 700, fontSize: "0.72rem", flex: "1 1 180px" }}>
                {c.nombre}
                {c.tipo_operacion === "inmobiliaria" && <span style={{ color: "#38bdf8", fontSize: "0.6rem", marginLeft: 6 }}>INMOBILIARIA · {c.contacto_inmobiliario?.inmobiliaria} ✓</span>}
              </span>
              <select data-testid={`flujos-inmo-select-${c.id}`} style={{ ...inp, flex: "0 1 220px" }} defaultValue=""
                onChange={e => asignarInmo(c.id, e.target.value)}>
                <option value="">Contacto Inmobiliario permanente…</option>
                {inmos.map(m => <option key={m.id} value={m.id}>{m.inmobiliaria}{m.encargado ? ` — ${m.encargado}` : ""}</option>)}
              </select>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ── MÓDULO CONTROL: AUDITOR INFORMATIVO (Regla #35) — no interfiere el flujo
const ControlAuditor = () => {
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  const cargar = () => axios.get(`${API}/api/control/discrepancias`).then(r => setD(r.data)).catch(() => setD({ discrepancias: [] }));
  useEffect(() => { cargar(); }, []);

  const enviarAlerta = async (fid) => {
    setBusy(fid); setMsg("");
    try {
      const r = await axios.post(`${API}/api/control/alerta/${fid}`, {});
      setMsg(`✅ Informe de inconsistencia enviado (${r.data.diferencias} diferencia(s)) — la operación NO se bloquea (Regla #35)`);
      cargar();
    } catch (e) { setMsg(`⛔ ${e.response?.data?.detail || "Error"}`); }
    setBusy("");
  };

  return (
    <div style={{ ...card, borderColor: "rgba(245,158,11,0.4)" }} data-testid="control-auditor">
      <div style={{ color: "#f59e0b", fontWeight: 800, fontSize: "0.8rem", marginBottom: 4 }}>
        🔎 Módulo Control — Auditor Informativo (Regla de Oro #35)
      </div>
      <p style={{ color: "#94a3b8", fontSize: "0.66rem", margin: "0 0 8px", lineHeight: 1.5 }}>
        Detecta discrepancias entre la Bodega y el Ingreso de Concreces. NO-INTERFERENCIA: el hallazgo jamás bloquea
        la operación. Destinatario Maestro: <b style={{ color: "#e2e8f0" }}>{d?.destinatario_maestro || "sin configurar (defínalo en DashAI)"}</b>
      </p>
      {msg && <p data-testid="control-msg" style={{ color: msg.startsWith("✅") ? "#22c55e" : "#ef4444", fontSize: "0.68rem" }}>{msg}</p>}
      {(d?.discrepancias || []).length === 0 && <p style={{ color: "#22c55e", fontSize: "0.7rem" }}>✅ Sin discrepancias entre Bodega e Ingreso de Concreces.</p>}
      {(d?.discrepancias || []).map(x => (
        <div key={x.folder_id} data-testid={`control-disc-${x.folder_id}`} style={{ padding: "0.5rem 0", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            <span style={{ color: "#f59e0b", fontWeight: 800, fontSize: "0.7rem" }}>⚠️ Discrepancia Detectada</span>
            <b style={{ color: "#f8fafc", fontSize: "0.74rem" }}>{x.cliente}</b>
            <span style={{ color: "#94a3b8", fontFamily: "monospace", fontSize: "0.66rem" }}>{x.rut}</span>
            {x.alerta_enviada && <span style={{ color: "#22c55e", fontSize: "0.62rem" }}>✉ Informe enviado {(x.alerta_fecha || "").slice(0, 16).replace("T", " ")}</span>}
            <button data-testid={`control-alerta-${x.folder_id}`} style={{ ...goldBtn, marginLeft: "auto" }}
              disabled={busy === x.folder_id} onClick={() => enviarAlerta(x.folder_id)}>
              {busy === x.folder_id ? "Enviando…" : "Enviar Alerta de Inconsistencia"}
            </button>
          </div>
          {x.diferencias.map((df, i) => (
            <div key={i} style={{ color: "#e2e8f0", fontSize: "0.64rem", marginTop: 3 }}>
              · <b>{df.campo}</b>: Bodega = {String(df.valor_bodega ?? "—")} vs Ingreso = {String(df.valor_ingreso ?? "—")}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
};

const GridEstado = () => {
  const [g, setG] = useState(null);
  useEffect(() => {
    const load = () => axios.get(`${API}/api/grid/estado`).then(r => setG(r.data)).catch(() => {});
    load(); const iv = setInterval(load, 15000); return () => clearInterval(iv);
  }, []);
  if (!g) return null;
  return (
    <div data-testid="grid-estado" style={{ marginTop: 10, display: "flex", gap: 14, flexWrap: "wrap", alignItems: "center",
      background: "rgba(56,189,248,0.06)", border: "1px solid rgba(56,189,248,0.35)", borderRadius: 8, padding: "0.5rem 0.9rem", fontSize: "0.66rem", color: "#94a3b8" }}>
      <b style={{ color: "#38bdf8" }}>🛰 GRID-DASHAI · Espejo Concreces Cloud (Regla #41)</b>
      <span>Archivos en espejo: <b style={{ color: "#e2e8f0" }}>{g.archivos_espejo ?? 0}</b></span>
      <span>Última resync MD5: <b style={{ color: "#e2e8f0" }}>{(g.ultima_resync || "—").slice(0, 16).replace("T", " ")}</b></span>
      <span>Eventos empujados: <b style={{ color: "#e2e8f0" }}>{g.eventos_emitidos ?? 0}</b></span>
      <span style={{ color: "#f59e0b", fontWeight: 800 }}>🔒 Sincronización obligatoria y permanente — sin interruptor</span>
    </div>
  );
};

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

  const panelActual = PANELES.find(p => p[0] === panel) || PANELES[0];

  return (
    <div className="module-content seamless-scope" data-testid="administracion-module" style={{ padding: "1.2rem", borderRadius: 12 }}>
      <div className="clientes-toolbar">
        <h3 style={{ margin: 0, color: "var(--text-primary)", fontSize: "1.05rem" }}>
          <i className="fa fa-database" style={{ marginRight: 8, color: "var(--gold)" }} />Administración — Bodega de Datos Concreces
        </h3>
        <span style={{ color: "var(--text-secondary)", fontSize: "0.72rem" }}>{data?.total ?? 0} registros · Regla de Oro #24: sin contraste RUT/Rol + respaldo OCR, el envío queda bloqueado</span>
      </div>
      {/* DIVISIÓN OPERATIVA (Regla #32) + Postventa */}
      <div style={{ display: "flex", gap: 10, marginTop: 14, flexWrap: "wrap" }}>
        {PANELES.map(([k, t, s]) => (
          <button key={k} data-testid={`panel-${k}`} onClick={() => setPanel(k)}
            style={{ flex: "1 1 200px", textAlign: "left", cursor: "pointer", borderRadius: 12, padding: "0.8rem 1rem",
              background: panel === k ? "linear-gradient(135deg, rgba(212,175,55,0.18), rgba(15,23,42,0.9))" : "rgba(30,41,59,0.55)",
              border: `1.5px solid ${panel === k ? "#d4af37" : "rgba(148,163,184,0.2)"}` }}>
            <div style={{ color: panel === k ? "#d4af37" : "#e2e8f0", fontWeight: 800, fontSize: "0.85rem" }}>{t}</div>
            <div style={{ color: "#94a3b8", fontSize: "0.66rem", marginTop: 2 }}>{s}</div>
          </button>
        ))}
      </div>
      <div data-testid="esqueleto-banner" style={{ marginTop: 10, background: "rgba(212,175,55,0.08)", border: "1px dashed rgba(212,175,55,0.4)", borderRadius: 8, padding: "0.5rem 0.9rem", color: "#d4af37", fontSize: "0.68rem", fontWeight: 700 }}>
        🏗 {panelActual[1]} — {panelActual[2]}. Funciones definitivas por instrucción final de Gerardo (Regla de Oro #32).
      </div>

      {/* GRID-DASHAI: sincronización forzada (Regla #41) */}
      <GridEstado />

      {/* CONFIGURACIÓN DE FUENTES IMAP del panel activo (Reglas #34 y #36) */}
      <GestorFuentesIMAP panel={panel} titulo={panelActual[1]} />

      {/* FLUJOS USADA/INMOBILIARIA solo en el panel de Victoria (Regla #37) */}
      {panel === "victoria" && <FlujosVictoria />}

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
                <td style={{ fontWeight: 700 }}>{r.cliente}
                  {r.broker_origen && r.broker_origen !== "DIRECTO" && <div style={{ color: "#38bdf8", fontSize: "0.6rem" }}>Broker: {r.broker_origen}</div>}
                </td>
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

      {/* CANAL DE INFORMACIÓN — MÓDULO CONTROL (Regla #35) */}
      <ControlAuditor />

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
