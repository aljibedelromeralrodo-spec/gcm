import { useState, useEffect, useMemo, useCallback } from "react";
import axios from "axios";
import { PanelComercial } from "./GerenciaCommandCenter";

const API = process.env.REACT_APP_BACKEND_URL;
const selEstilo = { background: "rgba(255,255,255,0.06)", border: "1px solid rgba(148,163,184,0.3)",
  color: "#e2e8f0", padding: "0.45rem 0.6rem", borderRadius: 10, fontSize: "0.7rem" };

// PROBLEMA 5: botones de estado diferenciados con color propio
const EST_LABEL = {
  ok: "✅ Aprobado", proceso: "⏳ En Proceso", pendiente: "Pendiente",
  pendiente_informacion: "Pendiente de Información", bloqueo: "❌ Bloqueado", alerta: "⚠️ Con Observaciones",
};
const estBtnStyle = (estado) => {
  const base = { display: "inline-block", borderRadius: 6, padding: "4px 10px", fontSize: 14,
    fontWeight: 700, boxShadow: "0 1px 3px rgba(0,0,0,0.4)", whiteSpace: "nowrap" };
  if (estado === "ok") return { ...base, background: "#1A5C2A", color: "#fff" };
  if (estado === "proceso") return { ...base, background: "#1A3A5C", color: "#fff" };
  if (estado === "alerta") return { ...base, background: "#7A4A00", color: "#fff" };
  if (estado === "bloqueo") return { ...base, background: "#5C1A1A", color: "#fff" };
  if (estado === "manual") return { ...base, background: "#3A3A3A", color: "#fff", border: "1px solid #eab308" };
  return { ...base, background: "#2A2A2A", color: "#9aa4b2", fontStyle: "italic", border: "1px dashed #555", fontWeight: 500 };
};
const BotonEstado = ({ estado, label, title, testid }) => (
  <span data-testid={testid} title={title} style={estBtnStyle(estado)}>{label || EST_LABEL[estado] || EST_LABEL.pendiente}</span>
);

// PROBLEMA 2/4: encabezados 13px dorados, sticky con fondo dorado 20% y sombra inferior
const thG = { padding: "14px 16px", textAlign: "left", whiteSpace: "nowrap", fontSize: 13,
  letterSpacing: 1, textTransform: "uppercase", color: "#D4AF37", height: 48,
  position: "sticky", top: 0, zIndex: 25,
  background: "linear-gradient(rgba(212,175,55,0.20), rgba(212,175,55,0.20)), #0f172a",
  boxShadow: "0 4px 10px rgba(0,0,0,0.45)", borderRight: "1px solid rgba(255,255,255,0.25)" };
const tdG = { padding: "8px 14px", fontSize: 14, verticalAlign: "middle",
  borderRight: "1px solid rgba(255,255,255,0.12)" };

const RECLAMOS_UI = [
  ["tasacion", "📩 Reclamar Tasación", f => f.tasacion_estado !== "ok", "mb-azul"],
  ["serviu", "📩 Reclamar SERVIU", f => !!f.subsidio, "mb-verde"],
  ["actualizacion", "📩 Reclamar Actualización", f => f.doc20?.estado !== "ok", "mb-naranja"],
  ["firmas", "📩 Reclamar Firmas", f => f.hito_firmas !== "ok", "mb-azul"],
  ["movimiento", "📩 Reclamar Movimiento", f => !!f.inactivo_96h, "mb-naranja"],
];

const FILTRO0 = { broker: "", inmo: "", proy: "", viv: "", sub: "", serviu: "" };

export default function GerenciaComercialModule() {
  const [data, setData] = useState(null);
  const [busyRec, setBusyRec] = useState("");
  const [reparosModal, setReparosModal] = useState(null);

  const verReparos = async (f) => {
    setReparosModal({ cliente: f.cliente, loading: true, reparos: [] });
    try {
      const r = await axios.get(`${API}/api/estudio-titulo/reparos/${f.folder_id}`);
      const rep = r.data?.reparos;
      const items = Array.isArray(rep) ? rep : (rep?.items || []);
      const alertas = Array.isArray(r.data?.alertas) ? r.data.alertas : [];
      setReparosModal({ cliente: f.cliente, loading: false, reparos: [...items, ...alertas] });
    } catch (e) {
      setReparosModal({ cliente: f.cliente, loading: false, reparos: [], error: e.response?.data?.detail || "Error" });
    }
  };
  const [filtro, setFiltro] = useState(FILTRO0);
  const [isMobile, setIsMobile] = useState(window.matchMedia("(max-width: 768px)").matches);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 768px)");
    const fn = e => setIsMobile(e.matches);
    mq.addEventListener("change", fn);
    return () => mq.removeEventListener("change", fn);
  }, []);

  const recargar = useCallback(() => {
    axios.get(`${API}/api/gerencia/cartera`).then(r => setData(r.data)).catch(() => setData({ cartera: [] }));
  }, []);
  useEffect(() => { recargar(); }, [recargar]);

  const exportar = async () => {
    const r = await axios.get(`${API}/api/gerencia/export-xlsx`, { responseType: "blob" });
    const url = URL.createObjectURL(r.data);
    const a = document.createElement("a");
    a.href = url; a.download = `Reporte_Gerencia_${data?.mes || ""}.xlsx`; a.click();
    URL.revokeObjectURL(url);
  };

  const fecharFirma = async (fid, fecha) => {
    try { await axios.post(`${API}/api/flujos/fecha-firma/${fid}`, { fecha }); recargar(); }
    catch (e) { console.error(e); }
  };

  // ACCIÓN ÚNICA (Regla #49) + HUELLA Y BLOQUEO 12H (Regla #57)
  const reclamar = async (fid, tipo, ultimaFecha, destinatario) => {
    if (ultimaFecha && (Date.now() - new Date(ultimaFecha).getTime()) < 12 * 3600 * 1000) {
      if (!window.confirm("¿Estás seguro de enviar un nuevo reclamo tan pronto? (último hace menos de 12 horas)")) return;
    }
    setBusyRec(`${fid}-${tipo}`);
    try {
      await axios.post(`${API}/api/gerencia/reclamo/${fid}`, { tipo, destinatario });
      recargar();
    } catch (e) {
      const det = e.response?.data?.detail || "Error de envío";
      if (e.response?.status === 400 && det.includes("correo configurado")) {
        const manual = window.prompt("El Broker no tiene correo configurado.\nIngrese el correo del destinatario:");
        if (manual) { await reclamar(fid, tipo, null, manual); return; }
      } else {
        window.alert(det);
      }
    }
    setBusyRec("");
  };

  // CENTRO DE FILTRADO (instantáneo, en memoria — Regla #54): SOLO los 6 filtros oficiales
  const cartera = useMemo(() => {
    let fs = data?.cartera || [];
    if (filtro.broker) fs = fs.filter(f => (f.broker_origen || "") === filtro.broker);
    if (filtro.inmo) fs = fs.filter(f => (f.inmobiliaria || f.origen || "") === filtro.inmo);
    if (filtro.proy) fs = fs.filter(f => (f.proyecto || "") === filtro.proy);
    if (filtro.viv) fs = fs.filter(f => (f.tipo_vivienda || "nueva") === filtro.viv);
    if (filtro.sub === "con") fs = fs.filter(f => f.subsidio);
    if (filtro.sub === "sin") fs = fs.filter(f => !f.subsidio);
    if (filtro.serviu === "con") fs = fs.filter(f => f.resolucion_serviu);
    if (filtro.serviu === "sin") fs = fs.filter(f => !f.resolucion_serviu);
    return fs;
  }, [data, filtro]);
  const ufFiltrado = useMemo(() => cartera.reduce((s, f) => s + (Number(f.monto_credito_uf) || 0), 0), [cartera]);
  const brokersOpc = useMemo(() => [...new Set((data?.cartera || []).map(f => f.broker_origen).filter(Boolean))].sort(), [data]);
  const inmosOpc = useMemo(() => [...new Set((data?.cartera || []).map(f => f.inmobiliaria || f.origen).filter(Boolean))].sort(), [data]);
  const proysOpc = useMemo(() => filtro.inmo
    ? [...new Set((data?.cartera || []).filter(f => (f.inmobiliaria || f.origen) === filtro.inmo).map(f => f.proyecto).filter(Boolean))].sort()
    : [], [data, filtro.inmo]);

  const glass = { background: "rgba(30,41,59,0.55)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)",
    border: "1px solid rgba(148,163,184,0.18)", borderRadius: 14 };
  const res = data?.resumen || {};

  const Tarjeta = ({ k, titulo, val, activo, onClick }) => (
    <button data-testid={`gerencia-card-${k}`} onClick={onClick}
      className="maserati-btn" style={{ flexDirection: "column", alignItems: "flex-start", gap: 2, minWidth: 160,
        borderColor: activo ? "#d4af37" : undefined, background: activo ? "rgba(212,175,55,0.12)" : undefined }}>
      <span style={{ fontSize: "0.58rem", color: "#94a3b8", letterSpacing: "0.12em" }}>{titulo}</span>
      <span style={{ fontSize: "0.9rem", color: "#FCF6BA" }}>{val?.n ?? 0} ops · {Number(val?.uf ?? 0).toLocaleString("es-CL")} UF</span>
    </button>
  );

  return (
    <div className="module-content seamless-scope" data-testid="gerencia-module" style={{ minHeight: "100%", padding: "1.2rem", borderRadius: 12 }}>
      <PanelComercial />
      <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap", marginBottom: 14 }}>
        <h3 style={{ margin: 0, color: "#f8fafc", fontSize: "1.05rem" }}>
          <i className="fa fa-line-chart" style={{ color: "#d4af37", marginRight: 8 }} />Gerencia Comercial — Centro de Mando Estratégico
        </h3>
        <span style={{ color: "#94a3b8", fontSize: "0.72rem" }}>Mes {data?.mes || "…"} · {cartera.length}/{data?.total ?? 0} operaciones · Auditoría DashAI: {(data?.ultima_auditoria_dashai || "").slice(0, 16) || "pendiente"}</span>
        {data?.cumplimiento_broker?.actualizado && (
          <span data-testid="gerencia-cumplimiento-broker" title="Sincronizado en tiempo real con la Supercarpeta (Meta de Proyección)"
            style={{ background: "rgba(212,175,55,0.12)", border: "1px solid rgba(212,175,55,0.5)", color: "#d4af37",
              borderRadius: 10, padding: "0.35rem 0.7rem", fontWeight: 800, fontSize: "0.72rem" }}>
            📈 Cumplimiento Broker: {data.cumplimiento_broker.pct_global ?? 0}% · UF cerradas {Number(data.cumplimiento_broker.uf_cerradas || 0).toLocaleString("es-CL")} / {Number(data.cumplimiento_broker.meta_uf || 0).toLocaleString("es-CL")}
          </span>
        )}
        <button data-testid="btn-export-gerencia" onClick={exportar} className="maserati-btn" style={{ marginLeft: "auto" }}>
          <i className="fa fa-file-excel-o" /> Exportar Reporte Mensual
        </button>
      </div>

      {/* CABECERA SEGMENTADA: sumatorias con filtrado dinámico */}
      <div className="gerencia-filtros" data-testid="gerencia-cards" style={{ marginBottom: 12 }}>
        <Tarjeta k="subsidio" titulo="CON SUBSIDIO" val={res.subsidio} activo={filtro.sub === "con"}
          onClick={() => setFiltro({ ...filtro, sub: filtro.sub === "con" ? "" : "con" })} />
        <Tarjeta k="sin_subsidio" titulo="SIN SUBSIDIO" val={res.sin_subsidio} activo={filtro.sub === "sin"}
          onClick={() => setFiltro({ ...filtro, sub: filtro.sub === "sin" ? "" : "sin" })} />
        <div data-testid="gerencia-card-filtrado" className="maserati-btn" style={{ flexDirection: "column",
          alignItems: "flex-start", gap: 2, minWidth: 180, cursor: "default", borderColor: "#d4af37" }}>
          <span style={{ fontSize: "0.58rem", color: "#d4af37", letterSpacing: "0.12em" }}>Σ RESULTADO FILTRADO</span>
          <span style={{ fontSize: "0.9rem", color: "#FCF6BA" }}>{cartera.length} ops · {Math.round(ufFiltrado).toLocaleString("es-CL")} UF</span>
        </div>
        <button data-testid="gerencia-card-total" onClick={() => setFiltro(FILTRO0)}
          className="maserati-btn neon" style={{ flexDirection: "column", alignItems: "flex-start", gap: 2, minWidth: 160 }}>
          <span style={{ fontSize: "0.58rem", color: "#94a3b8", letterSpacing: "0.12em" }}>TOTAL (limpiar filtros)</span>
          <span style={{ fontSize: "0.9rem" }}>{res.total?.n ?? 0} ops · {Number(res.total?.uf ?? 0).toLocaleString("es-CL")} UF</span>
        </button>
      </div>

      {/* CENTRO DE FILTRADO — SOLO: Broker · Inmobiliaria · Proyecto · Vivienda · Subsidio · SERVIU */}
      <div className="gerencia-filtros" data-testid="gerencia-filtros" style={{ ...glass, padding: "0.7rem 0.9rem", marginBottom: 12, alignItems: "flex-end" }}>
        <label style={{ color: "#94a3b8", fontSize: "0.62rem" }}>Broker<br />
          <select data-testid="filtro-broker" style={selEstilo} value={filtro.broker} onChange={e => setFiltro({ ...filtro, broker: e.target.value })}>
            <option value="">Todos</option>
            {brokersOpc.map(b => <option key={b} value={b}>{b}</option>)}
          </select>
        </label>
        <label style={{ color: "#94a3b8", fontSize: "0.62rem" }}>Inmobiliaria<br />
          <select data-testid="filtro-inmobiliaria" style={selEstilo} value={filtro.inmo}
            onChange={e => setFiltro({ ...filtro, inmo: e.target.value, proy: "" })}>
            <option value="">Todas</option>
            {inmosOpc.map(i => <option key={i} value={i}>{i}</option>)}
          </select>
        </label>
        <label style={{ color: "#94a3b8", fontSize: "0.62rem" }}>Proyecto<br />
          <select data-testid="filtro-proyecto" style={{ ...selEstilo, opacity: filtro.inmo ? 1 : 0.45 }}
            disabled={!filtro.inmo} value={filtro.proy} onChange={e => setFiltro({ ...filtro, proy: e.target.value })}>
            <option value="">{filtro.inmo ? "Todos" : "Elija inmobiliaria"}</option>
            {proysOpc.map(pr => <option key={pr} value={pr}>{pr}</option>)}
          </select>
        </label>
        <label style={{ color: "#94a3b8", fontSize: "0.62rem" }}>Tipo de vivienda<br />
          <select data-testid="filtro-vivienda" style={selEstilo} value={filtro.viv} onChange={e => setFiltro({ ...filtro, viv: e.target.value })}>
            <option value="">Todas</option>
            <option value="nueva">Nueva</option>
            <option value="usada">Usada</option>
          </select>
        </label>
        <label style={{ color: "#94a3b8", fontSize: "0.62rem" }}>Subsidio<br />
          <select data-testid="filtro-subsidio" style={selEstilo} value={filtro.sub} onChange={e => setFiltro({ ...filtro, sub: e.target.value })}>
            <option value="">Todos</option>
            <option value="con">Con subsidio</option>
            <option value="sin">Sin subsidio</option>
          </select>
        </label>
        <label style={{ color: "#94a3b8", fontSize: "0.62rem" }}>Resolución SERVIU<br />
          <select data-testid="filtro-serviu" style={selEstilo} value={filtro.serviu} onChange={e => setFiltro({ ...filtro, serviu: e.target.value })}>
            <option value="">Todos</option>
            <option value="con">Con resolución</option>
            <option value="sin">Sin resolución</option>
          </select>
        </label>
        <button data-testid="filtro-limpiar" onClick={() => setFiltro(FILTRO0)}
          style={{ background: "rgba(239,68,68,0.12)", color: "#f87171", border: "1px solid rgba(239,68,68,0.5)",
            borderRadius: 10, padding: "0.45rem 0.9rem", fontWeight: 800, cursor: "pointer", fontSize: "0.64rem" }}>
          ✕ Limpiar filtros</button>
        <span data-testid="filtro-sumatoria" style={{ marginLeft: "auto", color: "#d4af37", fontSize: "0.72rem", fontWeight: 900 }}>
          Σ {cartera.length} operaciones · UF {Math.round(ufFiltrado).toLocaleString("es-CL")}</span>
      </div>

      {(data?.alertas_notaria || 0) > 0 && (
        <div data-testid="gerencia-alerta-notaria" style={{ ...glass, borderColor: "#ef4444", color: "#fecaca", padding: "0.6rem 1rem", marginBottom: 12, fontSize: "0.78rem", fontWeight: 700 }}>
          🚨 {data.alertas_notaria} aviso(s) de notaría sobre firmas faltantes detectados por DashAI
        </div>
      )}
      {(data?.excepciones_recientes || []).length > 0 && (
        <div data-testid="gerencia-excepciones" style={{ ...glass, borderColor: "#f59e0b", color: "#fde68a", padding: "0.6rem 1rem", marginBottom: 12, fontSize: "0.72rem" }}>
          ⚠️ Excepciones autorizadas recientes: {data.excepciones_recientes.map(e => `${e.usuario} (${e.cliente || e.hito})`).join(" · ")}
        </div>
      )}

      {isMobile ? (
        /* 📱 VISTA MÓVIL: tarjetas apiladas (la tabla queda intacta en escritorio) */
        <div data-testid="gerencia-cards-mobile" style={{ display: "grid", gap: 10 }}>
          {cartera.map((f, idx) => (
            <div key={f.folder_id} data-testid={`gerencia-card-${f.folder_id}`}
              style={{ ...glass, padding: "0.8rem", background: f.datos_incompletos ? "rgba(94,26,26,0.45)" : (idx % 2 === 0 ? "#1E2A3A" : "#253347") }}>
              <div style={{ display: "flex", gap: 8, alignItems: "baseline", flexWrap: "wrap" }}>
                <b style={{ color: "#D4AF37" }}>{idx + 1}</b>
                <b style={{ color: "#fff", fontSize: 15, flex: 1, overflowWrap: "anywhere" }}>{f.cliente}</b>
                <span style={{ color: "#B0BEC5", fontFamily: "monospace", fontSize: 12 }}>{f.rut || "—"}</span>
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 4, fontSize: 12, color: "#90A4AE", alignItems: "center" }}>
                <span>{f.inmobiliaria || f.origen || "⚠️ Sin inmobiliaria"}</span>
                {f.tipo_operacion && <span style={{ fontSize: 10, fontWeight: 800, padding: "1px 8px", borderRadius: 6,
                  background: f.tipo_operacion === "USADA" ? "rgba(34,197,94,0.15)" : "rgba(56,189,248,0.15)",
                  color: f.tipo_operacion === "USADA" ? "#22c55e" : "#38bdf8" }}>{f.tipo_operacion}</span>}
                <span style={{ color: f.subsidio ? "#4ade80" : "#94a3b8", fontSize: 11 }}>{f.subsidio ? "Con Subsidio" : "Sin Subsidio"}</span>
                <b style={{ marginLeft: "auto", color: "#D4AF37" }}>{f.monto_credito_uf ? `${Number(f.monto_credito_uf).toLocaleString("es-CL")} UF` : "—"}</b>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginTop: 8, fontSize: 11 }}>
                <BotonEstado estado={f.documentacion} label={`Docs: ${f.documentacion === "ok" ? "✅" : f.documentacion === "proceso" ? "⏳" : "❌"}`} />
                <BotonEstado estado={f.tasacion_estado} label={`Tasación: ${f.tasacion_estado === "ok" ? "✅" : f.tasacion_estado === "proceso" ? "⏳" : "Pend."}`} />
                <BotonEstado estado={f.estudio_estado} label={`Estudio: ${f.estudio_estado === "ok" ? "✅" : f.estudio_estado === "proceso" ? "⏳" : "Pend."}`} />
                <BotonEstado estado={f.firma_set} label={`Set: ${f.firma_set === "ok" ? "✅" : f.firma_set === "proceso" ? "⏳" : "Pend."}`} />
                {f.escritura_firmada
                  ? <span style={{ color: "#FFD700", fontWeight: 900, fontSize: 12 }}>🏆 ESCRITURA FIRMADA</span>
                  : <BotonEstado estado="pendiente" label="Escritura: Pend." />}
              </div>
              {f.reparos_pendientes > 0 && (
                <button onClick={() => verReparos(f)} style={{ marginTop: 6, cursor: "pointer", border: "none",
                  borderRadius: 6, fontWeight: 800, fontSize: 11, padding: "3px 10px",
                  background: "rgba(239,68,68,0.18)", color: "#ef4444" }}>⚠️ {f.reparos_pendientes} reparo(s)</button>
              )}
              <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8, flexWrap: "wrap" }}>
                <label style={{ fontSize: 11, color: "#94a3b8" }}>📅 Firma:</label>
                <input type="date" defaultValue={f.fecha_firma || ""} onBlur={e => fecharFirma(f.folder_id, e.target.value)}
                  style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(148,163,184,0.25)",
                    color: "#e2e8f0", borderRadius: 6, padding: "0.25rem 0.4rem", fontSize: 13, width: 140 }} />
                <span style={{ fontSize: 11, color: "#78909C", marginLeft: "auto" }}>{f.notaria_nombre || "Notaría por asignar"}</span>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 8 }}>
                {RECLAMOS_UI.filter(([, , cond]) => cond(f)).map(([tipo, label, , color]) => {
                  const hecho = f.reclamos?.[tipo];
                  return (
                    <button key={tipo} className={`maserati-btn ${hecho ? "mb-hecho" : color}`}
                      disabled={busyRec === `${f.folder_id}-${tipo}`}
                      style={{ minHeight: 28, padding: "0.25rem 0.5rem", fontSize: "0.58rem", borderRadius: 8 }}
                      onClick={() => reclamar(f.folder_id, tipo, hecho?.fecha)}>
                      {busyRec === `${f.folder_id}-${tipo}` ? "Enviando…" : hecho ? `✓ ${label.replace("📩 ", "")}` : label}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
          {!data && <p style={{ color: "#94a3b8", textAlign: "center", padding: "2rem" }}>Cargando cartera…</p>}
          {data && cartera.length === 0 && <p style={{ color: "#94a3b8", textAlign: "center", padding: "2rem" }}>Sin operaciones con los filtros aplicados.</p>}
        </div>
      ) : (
      <div style={{ ...glass, overflow: "auto", maxHeight: "calc(100vh - 130px)" }}>
        <table data-testid="gerencia-tabla" style={{ width: "100%", borderCollapse: "collapse", fontSize: 14, color: "#e2e8f0", minWidth: 1900 }}>
          <thead>
            <tr>
              {["Cliente", "Inmobiliaria", "Proyecto", "Ciudad", "Broker", "Subsidio", "Monto UF",
                "Documentos Comerciales", "Tasación", "Estudio de Títulos", "Firma del Set",
                "Fecha de Firma de Escritura", "Notaría", "Firma de Escritura en Notaría",
                "Acciones de Mando"].map(h =>
                <th key={h} style={thG}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {cartera.map((f, idx) => (
              <tr key={f.folder_id} data-testid={`gerencia-fila-${f.folder_id}`}
                style={{
                  height: 52, borderBottom: "1px solid rgba(255,255,255,0.4)",
                  background: f.datos_incompletos ? "rgba(94,26,26,0.45)" : (idx % 2 === 0 ? "#1E2A3A" : "#253347") }}>
                {/* 1. CLIENTE (nombre + RUT) */}
                <td style={{ ...tdG, fontWeight: 700, fontSize: 15, color: "#FFFFFF", whiteSpace: "nowrap" }}>
                  {f.cliente}
                  <div style={{ fontFamily: "monospace", fontWeight: 400, fontSize: 14, color: "#B0BEC5" }}>{f.rut || "—"}</div>
                  {f.datos_incompletos && <div data-testid={`broker-no-actualizado-${f.folder_id}`} style={{ color: "#ef4444", fontSize: "0.62rem", fontWeight: 800 }}>🔴 Broker no actualizado</div>}
                  {f.inactivo_96h && !f.datos_incompletos && <div style={{ color: "#94a3b8", fontSize: "0.6rem" }}>⏸ Sin actividad 96h</div>}
                  {f.alerta_notaria && <div title={f.alerta_notaria} style={{ color: "#fb7185", fontSize: "0.62rem", fontWeight: 600,
                    maxWidth: 230, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.alerta_notaria}</div>}
                </td>
                {/* 2. INMOBILIARIA */}
                <td data-testid={`gerencia-origen-${f.folder_id}`} style={{ ...tdG,
                    color: (!f.inmobiliaria && (f.origen || "").startsWith("⚠️")) ? "#ef4444" : "#B0BEC5", fontWeight: 700 }}
                  title="Regla #58: prohibido 'Directo' — se prioriza la identidad de la Inmobiliaria">
                  {f.inmobiliaria || f.origen || "⚠️ Falta Identidad de Inmobiliaria"}
                  {f.tipo_operacion && <div data-testid={`gerencia-tipo-${f.folder_id}`} style={{ marginTop: 3 }}>
                    <span style={{ fontSize: "0.6rem", fontWeight: 800, padding: "0.15rem 0.5rem", borderRadius: 6,
                      background: f.tipo_operacion === "USADA" ? "rgba(34,197,94,0.15)" : "rgba(56,189,248,0.15)",
                      color: f.tipo_operacion === "USADA" ? "#22c55e" : "#38bdf8" }}>{f.tipo_operacion}</span></div>}
                </td>
                {/* 3. PROYECTO */}
                <td style={{ ...tdG, color: "#90A4AE" }}>{f.proyecto || <i style={{ color: "#64748b" }}>Pendiente</i>}</td>
                {/* 4. CIUDAD */}
                <td style={{ ...tdG, color: "#78909C" }}>{f.ciudad || <i style={{ color: "#64748b" }}>Por Confirmar</i>}</td>
                {/* 5. BROKER */}
                <td style={{ ...tdG, color: "#B0BEC5", fontStyle: "italic", whiteSpace: "nowrap" }}>{f.broker_origen || "—"}</td>
                {/* 6. SUBSIDIO */}
                <td style={{ ...tdG, whiteSpace: "nowrap" }}>{f.subsidio
                  ? <span style={{ color: "#4ade80", fontWeight: 700 }}>Con Subsidio</span>
                  : <span style={{ color: "#94a3b8" }}>Sin Subsidio</span>}</td>
                {/* 7. MONTO UF */}
                <td style={{ ...tdG, textAlign: "right", fontWeight: 800, color: "#D4AF37", whiteSpace: "nowrap" }}>
                  {f.monto_credito_uf ? <>{Number(f.monto_credito_uf).toLocaleString("es-CL")} <span style={{ color: "#B0BEC5", fontWeight: 400 }}>UF</span></> : "—"}</td>
                {/* 8. DOCUMENTOS COMERCIALES */}
                <td style={{ ...tdG, textAlign: "center" }}>
                  <BotonEstado testid={`gerencia-docs-${f.folder_id}`} estado={f.documentacion}
                    label={f.documentacion === "ok" ? "✅ Completos" : f.documentacion === "proceso" ? "⏳ En Proceso" : "❌ Incompletos"} /></td>
                {/* 9. TASACIÓN */}
                <td data-testid={`gerencia-tasacion-${f.folder_id}`} style={{ ...tdG, textAlign: "center" }}>
                  <BotonEstado estado={f.tasacion_estado}
                    label={f.tasacion_estado === "ok" ? "✅ Informe Recibido" : f.tasacion_estado === "proceso" ? "⏳ En Proceso" : undefined} /></td>
                {/* 10. ESTUDIO DE TÍTULOS */}
                <td data-testid={`gerencia-estudio-${f.folder_id}`} style={{ ...tdG, textAlign: "center" }}>
                  <BotonEstado estado={f.estudio_estado}
                    label={f.estudio_estado === "ok" ? "✅ Aprobado" : f.estudio_estado === "proceso" ? "⏳ En Proceso" : undefined} />
                  {f.reparos_pendientes > 0 && (
                    <button data-testid={`gerencia-reparos-btn-${f.folder_id}`}
                      onClick={() => verReparos(f)}
                      title="⚠️ Reparo detectado — pinche para leer el texto del abogado"
                      style={{ display: "block", margin: "4px auto 0", cursor: "pointer", border: "none",
                        borderRadius: 6, fontWeight: 800, fontSize: "0.62rem", padding: "2px 8px",
                        background: "rgba(239,68,68,0.18)", color: "#ef4444" }}>
                      ⚠️ {f.reparos_pendientes} reparo(s)
                    </button>
                  )}
                </td>
                {/* 11. FIRMA DEL SET (Cédula de Crédito) */}
                <td style={{ ...tdG, textAlign: "center" }}>
                  <BotonEstado testid={`gerencia-firmaset-${f.folder_id}`} estado={f.firma_set}
                    label={f.firma_set === "ok" ? "✅ Firmado" : f.firma_set === "proceso" ? "⏳ Enviado" : undefined} /></td>
                {/* 12. FECHA DE FIRMA DE ESCRITURA */}
                <td data-testid={`gerencia-fecha-firma-${f.folder_id}`} style={{ ...tdG }}>
                  <input type="date" defaultValue={f.fecha_firma || ""} onBlur={e => fecharFirma(f.folder_id, e.target.value)}
                    style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(148,163,184,0.25)",
                      color: "#e2e8f0", borderRadius: 6, padding: "0.25rem 0.4rem", fontSize: 14, width: 140 }} />
                </td>
                {/* 13. NOTARÍA: nombre + estado en dos líneas */}
                <td data-testid={`gerencia-notaria-${f.folder_id}`} style={{ ...tdG }}>
                  <div style={{ fontWeight: 700, color: f.notaria_nombre ? "#B0BEC5" : "#78909C",
                    fontStyle: f.notaria_nombre ? "normal" : "italic" }}>{f.notaria_nombre || "Por Asignar"}</div>
                  <div style={{ marginTop: 3, fontSize: 14,
                    color: f.notaria_estado_escritura === "Escritura Lista Para Firmar" ? "#4ade80"
                      : f.notaria_estado_escritura === "En Preparación" ? "#60a5fa" : "#9aa4b2",
                    fontWeight: f.notaria_estado_escritura === "Pendiente" ? 400 : 700,
                    fontStyle: f.notaria_estado_escritura === "Pendiente" ? "italic" : "normal" }}>
                    {f.notaria_estado_escritura}</div>
                </td>
                {/* 14. FIRMA DE ESCRITURA EN NOTARÍA — HITO FINAL */}
                <td data-testid={`gerencia-firma-escritura-${f.folder_id}`} style={{ ...tdG, textAlign: "center" }}>
                  {f.escritura_firmada
                    ? <span style={{ color: "#FFD700", fontWeight: 900, fontSize: 15, textShadow: "0 0 12px rgba(255,215,0,0.4)" }}>🏆 FIRMADA</span>
                    : <span style={estBtnStyle("pendiente")}>Pendiente</span>}
                </td>
                <td style={{ ...tdG, padding: "10px 10px" }}>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 4, maxWidth: 360, alignItems: "center" }}>
                    {RECLAMOS_UI.filter(([, , cond]) => cond(f)).map(([tipo, label, , color]) => {
                      const hecho = f.reclamos?.[tipo];
                      return (
                        <div key={tipo}>
                          <button data-testid={`reclamo-${tipo}-${f.folder_id}`}
                            className={`maserati-btn ${hecho ? "mb-hecho" : color}`}
                            disabled={busyRec === `${f.folder_id}-${tipo}`}
                            style={{ minHeight: 28, padding: "0.25rem 0.5rem", fontSize: "0.58rem", borderRadius: 8 }}
                            title={hecho ? `Última gestión: ${hecho.por} → ${hecho.destinatario} · ${(hecho.fecha || "").slice(0, 16).replace("T", " ")} UTC (Regla #57)` : "El envío depende 100% de Gerencia (Regla #49)"}
                            onClick={() => reclamar(f.folder_id, tipo, hecho?.fecha)}>
                            {busyRec === `${f.folder_id}-${tipo}` ? "Enviando…"
                              : hecho ? `✓ ${label.replace("📩 ", "")}` : label}
                          </button>
                        </div>
                      );
                    })}
                    {RECLAMOS_UI.every(([, , cond]) => !cond(f)) && <span style={{ color: "#22c55e", fontSize: "0.62rem" }}>Sin gestiones pendientes</span>}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!data && <p style={{ color: "#94a3b8", textAlign: "center", padding: "2rem" }}>Cargando cartera…</p>}
        {data && cartera.length === 0 && <p style={{ color: "#94a3b8", textAlign: "center", padding: "2rem" }}>Sin operaciones con los filtros aplicados.</p>}
      </div>
      )}
      <p data-testid="costo-desarrollo" style={{ color: "#64748b", fontSize: "0.68rem", marginTop: 12 }}>
        ⚡ Costo de Desarrollo del mes: <b style={{ color: "#d4af37" }}>{data?.costo_desarrollo_creditos ?? 0} créditos</b> (estimado por consumo real de IA — Ley de Eficiencia #23)
        · Cada clic queda en el Log de Gestión Gerencial (Regla #52)
      </p>
      {reparosModal && (
        <div data-testid="gerencia-reparos-modal" onClick={() => setReparosModal(null)}
          style={{ position: "fixed", inset: 0, zIndex: 200, background: "rgba(2,6,23,0.8)",
            backdropFilter: "blur(8px)", display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem" }}>
          <div onClick={e => e.stopPropagation()} style={{ width: "100%", maxWidth: 560, maxHeight: "80vh", overflowY: "auto",
            background: "rgba(15,23,42,0.97)", borderRadius: 16, padding: "1.4rem 1.6rem", boxShadow: "0 30px 80px rgba(0,0,0,0.6)" }}>
            <h4 style={{ margin: 0, color: "#ef4444", fontSize: "0.9rem" }}>⚠️ Reparos del abogado — {reparosModal.cliente}</h4>
            {reparosModal.loading && <p style={{ color: "#94a3b8", fontSize: "0.7rem" }}>Cargando texto íntegro…</p>}
            {reparosModal.error && <p style={{ color: "#ef4444", fontSize: "0.7rem" }}>{reparosModal.error}</p>}
            {!reparosModal.loading && (reparosModal.reparos || []).length === 0 && !reparosModal.error &&
              <p style={{ color: "#94a3b8", fontSize: "0.7rem" }}>Sin texto de reparos registrado en la carpeta.</p>}
            {(reparosModal.reparos || []).map((r, i) => (
              <div key={i} style={{ marginTop: 10, padding: "0.7rem 0.9rem", background: "rgba(239,68,68,0.08)",
                borderLeft: "3px solid #ef4444", borderRadius: 8 }}>
                {(r.texto || r.detalle) && <div style={{ color: "#f8fafc", fontSize: "0.7rem", whiteSpace: "pre-wrap" }}>{r.texto || r.detalle}</div>}
                {!r.texto && !r.detalle && <div style={{ color: "#f8fafc", fontSize: "0.7rem", whiteSpace: "pre-wrap" }}>{r.asunto || (typeof r === "string" ? r : JSON.stringify(r).slice(0, 300))}</div>}
                {(r.fecha || r.remitente) && <div style={{ color: "#94a3b8", fontSize: "0.6rem", marginTop: 4 }}>
                  {(r.fecha || "").slice(0, 16).replace("T", " ")} {r.remitente ? `· ${r.remitente}` : ""}</div>}
              </div>
            ))}
            <button data-testid="gerencia-reparos-cerrar" onClick={() => setReparosModal(null)} className="maserati-btn" style={{ marginTop: 14 }}>Cerrar</button>
          </div>
        </div>
      )}
    </div>
  );
}
