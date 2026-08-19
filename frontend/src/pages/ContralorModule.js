import { useEffect, useState } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const inp = { background: "rgba(2,6,23,0.7)", border: "1px solid rgba(203,213,225,0.35)", color: "#f8fafc",
  borderRadius: 8, padding: "0.5rem 0.7rem", fontSize: "0.85rem", width: "100%", boxSizing: "border-box" };

export default function ContralorModule() {
  const [espejo, setEspejo] = useState(null);
  const [criterios, setCriterios] = useState(null);
  const [nuevoCriterio, setNuevoCriterio] = useState("");
  const [form, setForm] = useState({ email: "", clave: "", servidor: "imap.gmail.com" });
  const [guardando, setGuardando] = useState(false);
  const [ops, setOps] = useState(null);
  const [noClas, setNoClas] = useState([]);

  const cargar = () => {
    axios.get(`${API}/api/contralor/espejo`)
      .then(r => { setEspejo(r.data); setForm(f => ({ ...f, email: r.data.email || f.email, servidor: r.data.servidor || "imap.gmail.com" })); })
      .catch(() => setEspejo({ error: true }));
    axios.get(`${API}/api/contralor/espejo/criterios`).then(r => setCriterios(r.data)).catch(() => {});
    axios.get(`${API}/api/contralor/espejo/operaciones`).then(r => setOps(r.data)).catch(() => {});
    axios.get(`${API}/api/contralor/espejo/no-clasificados`).then(r => setNoClas(r.data.correos || [])).catch(() => {});
  };
  useEffect(() => { cargar(); }, []);

  const sincronizar = async () => {
    setGuardando(true);
    try {
      const r = await axios.post(`${API}/api/contralor/espejo/sincronizar`, {});
      window.alert(`🔄 Sincronización Concreces: ${r.data.correos_leidos} correo(s) leídos · ` +
        `${r.data.operaciones_actualizadas} operación(es) actualizada(s)` +
        (r.data.no_clasificados_nuevos ? ` · ${r.data.no_clasificados_nuevos} sin clasificar` : ""));
      cargar();
    } catch (e) { window.alert(e.response?.data?.detail || "Error al sincronizar con Concreces"); }
    setGuardando(false);
  };

  const escanear = async () => {
    setGuardando(true);
    try {
      const r = await axios.post(`${API}/api/contralor/espejo/escanear`, {});
      window.alert(`🪞 CAPA A: ${r.data.correos_leidos} correo(s) leídos · ${r.data.patrones_nuevos} patrón(es) nuevo(s)` +
        (r.data.conflictos_pendientes ? ` · ⚠️ ${r.data.conflictos_pendientes} conflicto(s) esperan confirmación del admin` : "") +
        ` · Calibración: ${r.data.calibracion_pct}%`);
      cargar();
    } catch (e) { window.alert(e.response?.data?.detail || "Error al escanear el buzón"); }
    setGuardando(false);
  };
  const agregarCriterio = async () => {
    if (!nuevoCriterio.trim()) return;
    try {
      await axios.post(`${API}/api/contralor/espejo/criterios`, { criterio: nuevoCriterio.trim() });
      setNuevoCriterio(""); cargar();
    } catch (e) { window.alert(e.response?.data?.detail || "Solo el Administrador puede agregar criterios manuales"); }
  };
  const resolverCriterio = async (cid, accion) => {
    try {
      const r = await axios.post(`${API}/api/contralor/espejo/criterios/${cid}/resolver`, { accion });
      window.alert(`✅ ${r.data.nota}`); cargar();
    } catch (e) { window.alert(e.response?.data?.detail || "Solo el Administrador puede resolver conflictos"); }
  };

  const guardar = async () => {
    const confirmacion = window.prompt("Confirmación de identidad: reingrese su contraseña para guardar la configuración avanzada");
    if (!confirmacion) return;
    setGuardando(true);
    try {
      const r = await axios.post(`${API}/api/contralor/espejo`, { ...form, confirmacion_clave: confirmacion });
      window.alert(`✅ ${r.data.nota || "Configuración guardada (cifrada)"}`);
      setForm(f => ({ ...f, clave: "" }));
      cargar();
    } catch (e) { window.alert(e.response?.data?.detail || "No fue posible guardar la configuración. Verifique su contraseña e intente nuevamente."); }
    setGuardando(false);
  };

  if (!espejo) return <p style={{ color: "#94a3b8" }}>Cargando Módulo Contralor…</p>;
  if (espejo.error) return <p style={{ color: "#f87171" }}>No fue posible cargar el módulo. Verifique su rol.</p>;

  return (
    <div data-testid="modulo-contralor" style={{ display: "grid", gap: 16, maxWidth: 900 }}>
      <div style={{ background: "linear-gradient(135deg,#1a1d24,#252a35)", border: "1px solid rgba(203,213,225,0.3)",
        borderLeft: "5px solid #cbd5e1", borderRadius: 14, padding: "1.4rem 1.6rem" }}>
        <h2 style={{ color: "#f8fafc", fontSize: "1.2rem", margin: 0 }}><i className="fa fa-eye" /> Módulo Contralor</h2>
        <p style={{ color: "#94a3b8", fontSize: "0.85rem", marginTop: 6 }}>
          Auditoría absoluta del sistema · configuración exclusiva del Algoritmo Espejo.</p>
      </div>

      {/* ── ALGORITMO ESPEJO ── */}
      <div data-testid="algoritmo-espejo" style={{ background: "rgba(15,23,42,0.6)",
        border: "1px solid rgba(203,213,225,0.25)", borderRadius: 14, padding: "1.4rem 1.6rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <h3 style={{ color: "#e2e8f0", fontSize: "1rem", margin: 0 }}>🪞 Algoritmo Espejo</h3>
          <span data-testid="espejo-estado" style={{ marginLeft: "auto", fontSize: "0.75rem", fontWeight: 800,
            color: espejo.estado === "conectado" ? "#4ade80" : "#f87171",
            border: `1px solid ${espejo.estado === "conectado" ? "#4ade80" : "#f87171"}55`,
            borderRadius: 999, padding: "3px 12px" }}>
            {espejo.estado === "conectado" ? "🟢 CONECTADO" : "🔴 DESCONECTADO"}</span>
        </div>
        <p style={{ color: "#94a3b8", fontSize: "0.8rem", marginTop: 8 }}>
          Buzón IMAP de lectura para capturar las resoluciones reales. Complete las credenciales cuando estén autorizadas —
          el sistema no se conectará hasta que el algoritmo esté construido.</p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10, marginTop: 12 }}>
          <div>
            <label style={{ color: "#cbd5e1", fontSize: "0.72rem", fontWeight: 800 }}>CORREO DEL BUZÓN</label>
            <input data-testid="espejo-email" style={inp} value={form.email} placeholder="correo@dominio.cl"
              onChange={e => setForm(f => ({ ...f, email: e.target.value }))} />
          </div>
          <div>
            <label style={{ color: "#cbd5e1", fontSize: "0.72rem", fontWeight: 800 }}>CLAVE DE APLICACIÓN
              {espejo.tiene_clave && <span style={{ color: "#4ade80" }}> · guardada 🔐</span>}</label>
            <input data-testid="espejo-clave" style={inp} type="password" value={form.clave}
              placeholder={espejo.tiene_clave ? "•••••••• (dejar vacío para mantener)" : "Clave de aplicación IMAP"}
              onChange={e => setForm(f => ({ ...f, clave: e.target.value }))} />
          </div>
          <div>
            <label style={{ color: "#cbd5e1", fontSize: "0.72rem", fontWeight: 800 }}>SERVIDOR IMAP</label>
            <input data-testid="espejo-servidor" style={inp} value={form.servidor}
              onChange={e => setForm(f => ({ ...f, servidor: e.target.value }))} />
          </div>
        </div>
        <button data-testid="espejo-guardar" onClick={guardar} disabled={guardando}
          style={{ marginTop: 14, background: "linear-gradient(135deg,#94a3b8,#e2e8f0)", color: "#0a0a0a",
            border: "none", borderRadius: 8, padding: "0.55rem 1.4rem", fontWeight: 800, cursor: "pointer", fontSize: "0.82rem" }}>
          {guardando ? "Guardando…" : "💾 Guardar configuración (cifrada)"}</button>
        <button data-testid="espejo-escanear" onClick={escanear} disabled={guardando}
          style={{ marginTop: 14, marginLeft: 10, background: "rgba(96,165,250,0.2)", color: "#93c5fd",
            border: "1px solid rgba(96,165,250,0.5)", borderRadius: 8, padding: "0.55rem 1.4rem",
            fontWeight: 800, cursor: "pointer", fontSize: "0.82rem" }}>
          {guardando ? "…" : "🔍 CAPA A — Escanear buzón ahora"}</button>
      </div>

      {/* ── SINCRONIZACIÓN CONCRECES: operaciones + correos no clasificados ── */}
      <div data-testid="espejo-sync" style={{ background: "rgba(15,23,42,0.6)",
        border: "1px solid rgba(203,213,225,0.25)", borderRadius: 14, padding: "1.2rem 1.6rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <h3 style={{ color: "#e2e8f0", fontSize: "0.95rem", margin: 0 }}>🔄 Sincronización Concreces (cada 30 min)</h3>
          <span data-testid="espejo-ultima-sync" style={{ color: "#94a3b8", fontSize: "0.72rem" }}>
            Última lectura: {ops?.ultima_sync ? String(ops.ultima_sync).slice(0, 16).replace("T", " ") : "— sin sincronizar aún"}</span>
          <button data-testid="espejo-sincronizar" onClick={sincronizar} disabled={guardando}
            style={{ marginLeft: "auto", background: "rgba(74,222,128,0.15)", color: "#4ade80",
              border: "1px solid rgba(74,222,128,0.5)", borderRadius: 8, padding: "0.5rem 1.3rem",
              fontWeight: 800, cursor: "pointer", fontSize: "0.8rem" }}>
            {guardando ? "…" : "🔄 Sincronizar ahora"}</button>
        </div>
        <p style={{ color: "#94a3b8", fontSize: "0.74rem", marginTop: 8 }}>
          Lee el buzón institucional de Concreces (credenciales en los secrets de la aplicación),
          extrae nº de operación, estado, monto y observaciones, y actualiza cada operación.</p>
        {(ops?.operaciones || []).length > 0 ? (
          <div style={{ overflowX: "auto", marginTop: 10 }}>
            <table data-testid="espejo-operaciones-tabla" style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.76rem" }}>
              <thead><tr style={{ color: "#94a3b8", textAlign: "left" }}>
                <th style={{ padding: "4px 8px" }}>Cliente</th><th>Nº Operación</th><th>Estado Concreces</th>
                <th>Monto</th><th>Observaciones</th><th>Última lectura</th></tr></thead>
              <tbody>
                {(ops.operaciones || []).map(o => (
                  <tr key={o.fid} data-testid={`espejo-op-${o.fid}`} style={{ borderTop: "1px solid rgba(148,163,184,0.15)", color: "#e2e8f0" }}>
                    <td style={{ padding: "5px 8px" }}><b>{o.cliente}</b><div style={{ color: "#64748b", fontSize: "0.66rem" }}>{o.rut}</div></td>
                    <td style={{ fontFamily: "monospace" }}>{o.nro_operacion || "—"}</td>
                    <td><span style={{ fontWeight: 800,
                      color: /aprobad|cursad|escriturad/i.test(o.estado) ? "#4ade80" : /rechazad/i.test(o.estado) ? "#f87171" : "#facc15" }}>
                      {o.estado || "—"}</span></td>
                    <td>{o.monto || "—"}</td>
                    <td style={{ color: "#94a3b8", maxWidth: 220, overflowWrap: "anywhere" }}>{o.observaciones || "—"}</td>
                    <td style={{ color: "#64748b", fontFamily: "monospace", fontSize: "0.66rem" }}>{String(o.sync_at || "").slice(0, 16).replace("T", " ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p style={{ color: "#64748b", fontSize: "0.76rem", fontStyle: "italic", marginTop: 10 }}>
            Sin operaciones sincronizadas aún — configure las credenciales del buzón Concreces y ejecute la sincronización.</p>
        )}
        <div data-testid="espejo-no-clasificados" style={{ marginTop: 14, borderTop: "1px dashed rgba(148,163,184,0.3)", paddingTop: 10 }}>
          <b style={{ color: "#facc15", fontSize: "0.8rem" }}>📥 Correos no clasificados ({noClas.length}) — visibles solo para Admin y Contralor</b>
          {noClas.length === 0 ? (
            <p style={{ color: "#64748b", fontSize: "0.72rem", fontStyle: "italic", margin: "6px 0 0" }}>
              Todos los correos de Concreces fueron asociados a una operación.</p>
          ) : noClas.map(nc => (
            <div key={nc.id} data-testid={`espejo-nc-${nc.id}`} style={{ borderTop: "1px solid rgba(148,163,184,0.12)",
              padding: "5px 0", fontSize: "0.74rem", color: "#cbd5e1" }}>
              <b style={{ color: "#f8fafc" }}>{nc.asunto || "(sin asunto)"}</b>
              <span style={{ color: "#64748b" }}> · {nc.fecha_correo || nc.recibido}</span>
              {nc.estado && <span style={{ color: "#facc15" }}> · {nc.estado}</span>}
            </div>
          ))}
        </div>
      </div>

      {/* ── CAPA B: CRITERIOS MANUALES DEL ADMINISTRADOR ── */}
      <div data-testid="espejo-capa-b" style={{ background: "rgba(15,23,42,0.6)",
        border: "1px solid rgba(203,213,225,0.25)", borderRadius: 14, padding: "1.2rem 1.6rem" }}>
        <h3 style={{ color: "#e2e8f0", fontSize: "0.95rem", margin: 0 }}>✍️ Capa B — Criterios Manuales
          {criterios?.pendientes > 0 && <span style={{ color: "#facc15", fontSize: "0.75rem" }}> · ⚠️ {criterios.pendientes} conflicto(s) por confirmar</span>}</h3>
        <p style={{ color: "#94a3b8", fontSize: "0.75rem", marginTop: 6 }}>
          Criterios humanos que el correo no captura. Una regla manual JAMÁS se sobreescribe con una automática
          sin confirmación del administrador.</p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
          <input data-testid="criterio-texto" style={{ ...inp, flex: 1, minWidth: 220 }} placeholder="Nuevo criterio (ej: renta mínima 25 UF para DS19)"
            value={nuevoCriterio} onChange={e => setNuevoCriterio(e.target.value)} />
          <button data-testid="criterio-agregar" onClick={agregarCriterio}
            style={{ background: "linear-gradient(135deg,#BF953F,#FCF6BA)", color: "#0a0a0a", border: "none",
              borderRadius: 8, padding: "0.5rem 1.1rem", fontWeight: 800, cursor: "pointer", fontSize: "0.78rem" }}>➕ Agregar (admin)</button>
        </div>
        {(criterios?.criterios || []).length === 0 && <p style={{ color: "#64748b", fontSize: "0.78rem", fontStyle: "italic", marginTop: 10 }}>
          Sin criterios registrados aún.</p>}
        {(criterios?.criterios || []).map(cr => (
          <div key={cr.id} data-testid={`criterio-${cr.id}`} style={{ borderTop: "1px solid rgba(148,163,184,0.15)",
            padding: "0.55rem 0", display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <span style={{ fontSize: "0.68rem", fontWeight: 800, borderRadius: 999, padding: "2px 9px",
              color: cr.origen === "manual" ? "#FCF6BA" : "#93c5fd",
              border: `1px solid ${cr.origen === "manual" ? "#FCF6BA55" : "#93c5fd55"}` }}>
              {cr.origen === "manual" ? "MANUAL" : "AUTO"}</span>
            <span style={{ color: "#e2e8f0", fontSize: "0.8rem", flex: 1 }}>{cr.criterio}
              {cr.detalle ? <span style={{ color: "#94a3b8" }}> — {cr.detalle}</span> : null}</span>
            <span style={{ fontSize: "0.68rem", fontWeight: 800,
              color: cr.estado === "activo" ? "#4ade80" : cr.estado === "pendiente_confirmacion" ? "#facc15" : "#64748b" }}>
              {cr.estado === "pendiente_confirmacion" ? "⚠️ pendiente" : cr.estado}</span>
            {cr.estado === "pendiente_confirmacion" && (
              <span style={{ display: "flex", gap: 6 }}>
                <button data-testid={`criterio-confirmar-${cr.id}`} onClick={() => resolverCriterio(cr.id, "confirmar")}
                  style={{ background: "rgba(74,222,128,0.15)", color: "#4ade80", border: "1px solid #4ade8055",
                    borderRadius: 6, padding: "2px 10px", fontSize: "0.7rem", fontWeight: 800, cursor: "pointer" }}>✔ Confirmar</button>
                <button data-testid={`criterio-rechazar-${cr.id}`} onClick={() => resolverCriterio(cr.id, "rechazar")}
                  style={{ background: "rgba(248,113,113,0.15)", color: "#f87171", border: "1px solid #f8717155",
                    borderRadius: 6, padding: "2px 10px", fontSize: "0.7rem", fontWeight: 800, cursor: "pointer" }}>✖ Mantener manual</button>
              </span>
            )}
          </div>
        ))}
      </div>

      {/* ── INDICADOR DE CALIBRACIÓN ── */}
      <div data-testid="espejo-calibracion" style={{ background: "rgba(15,23,42,0.6)",
        border: "1px solid rgba(203,213,225,0.25)", borderRadius: 14, padding: "1.2rem 1.6rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <h3 style={{ color: "#e2e8f0", fontSize: "0.95rem", margin: 0 }}>📐 Nivel de Calibración del Espejo</h3>
          <b style={{ color: "#f8fafc", fontSize: "1.3rem" }}>{espejo.calibracion_pct || 0}%</b>
        </div>
        <div style={{ marginTop: 8, height: 10, background: "rgba(0,0,0,0.4)", borderRadius: 99, overflow: "hidden" }}>
          <div style={{ width: `${espejo.calibracion_pct || 0}%`, height: "100%", background: "linear-gradient(90deg,#94a3b8,#e2e8f0)" }} />
        </div>
        <p style={{ color: "#64748b", fontSize: "0.75rem", marginTop: 8, fontStyle: "italic" }}>
          Se mantendrá en 0% hasta conectar el buzón y procesar resoluciones reales de Concreces.</p>
      </div>

      {/* ── BITÁCORA DE CALIBRACIÓN ── */}
      <div data-testid="espejo-bitacora" style={{ background: "rgba(15,23,42,0.6)",
        border: "1px solid rgba(203,213,225,0.25)", borderRadius: 14, padding: "1.2rem 1.6rem" }}>
        <h3 style={{ color: "#e2e8f0", fontSize: "0.95rem", margin: 0 }}>📒 Bitácora de Calibración</h3>
        {(espejo.bitacora || []).length === 0 ? (
          <p style={{ color: "#64748b", fontSize: "0.8rem", marginTop: 10, fontStyle: "italic" }}>
            Sin patrones registrados aún — aquí se recibirán los patrones de aprobación de Concreces
            cuando el buzón esté conectado.</p>
        ) : (espejo.bitacora || []).map((b, i) => (
          <div key={i} style={{ borderTop: "1px solid rgba(148,163,184,0.15)", padding: "0.5rem 0",
            color: "#cbd5e1", fontSize: "0.8rem" }}>
            <span style={{ color: "#64748b", fontFamily: "monospace" }}>{String(b.fecha || "").slice(0, 16)}</span> · {b.patron || b.detalle || ""}
          </div>
        ))}
      </div>
    </div>
  );
}
