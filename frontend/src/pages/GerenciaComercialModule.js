import { useState, useEffect, useMemo, useCallback } from "react";
import axios from "axios";
import { PanelComercial } from "./GerenciaCommandCenter";
import GestionEjecutivosModule from "./GestionEjecutivosModule";
import CentroMandoGerencia from "../components/CentroMandoGerencia";

const API = process.env.REACT_APP_BACKEND_URL;

// ═══ PALETA CENTRO DE MANDO: negro profundo + dorado mate ═══
const ORO = "#C9A227";
const ORO_CLARO = "#E8C96A";
const FILA_A = "#0b0b0b";
const FILA_B = "#111111";
const BORDE = "rgba(201,162,39,0.22)";
const panel = { background: "#0c0c0c", border: `1px solid ${BORDE}`, borderRadius: 10 };
const selEstilo = { background: "#080808", border: `1px solid ${BORDE}`,
  color: "#e8e3d3", padding: "0.45rem 0.6rem", borderRadius: 8, fontSize: "0.7rem" };

const EST_LABEL = {
  ok: "✅ Aprobado", proceso: "⏳ En Proceso", pendiente: "Pendiente",
  pendiente_informacion: "Pendiente de Información", bloqueo: "❌ Bloqueado", alerta: "⚠️ Con Observaciones",
};
const estBtnStyle = (estado) => {
  const base = { display: "inline-block", borderRadius: 6, padding: "4px 10px", fontSize: 14,
    fontWeight: 700, boxShadow: "0 1px 3px rgba(0,0,0,0.4)", whiteSpace: "nowrap" };
  if (estado === "ok") return { ...base, background: "#123A1E", color: "#7ee2a0" };
  if (estado === "proceso") return { ...base, background: "#12283A", color: "#7ec3e2" };
  if (estado === "alerta") return { ...base, background: "#3A2A08", color: "#e2c37e" };
  if (estado === "bloqueo") return { ...base, background: "#3A1212", color: "#e27e7e" };
  if (estado === "manual") return { ...base, background: "#1c1c1c", color: "#fff", border: `1px solid ${ORO}` };
  return { ...base, background: "#161616", color: "#8a8a8a", fontStyle: "italic", border: "1px dashed #3a3a3a", fontWeight: 500 };
};
const BotonEstado = ({ estado, label, title, testid }) => (
  <span data-testid={testid} title={title} style={estBtnStyle(estado)}>{label || EST_LABEL[estado] || EST_LABEL.pendiente}</span>
);

const thG = { padding: "13px 16px", textAlign: "left", whiteSpace: "nowrap", fontSize: 12.5,
  letterSpacing: 1.5, textTransform: "uppercase", color: ORO, height: 46,
  position: "sticky", top: 0, zIndex: 25, background: "#0a0a0a",
  boxShadow: "0 2px 0 rgba(201,162,39,0.4), 0 4px 10px rgba(0,0,0,0.6)",
  borderRight: "1px solid rgba(255,255,255,0.08)" };
const tdG = { padding: "8px 14px", fontSize: 14, verticalAlign: "middle",
  borderRight: "1px solid rgba(255,255,255,0.05)" };

const RECLAMOS_UI = [
  ["tasacion", "📩 Reclamar Tasación", f => f.tasacion_estado !== "ok", "mb-azul"],
  ["serviu", "📩 Reclamar SERVIU", f => !!f.subsidio, "mb-verde"],
  ["actualizacion", "📩 Reclamar Actualización", f => f.doc20?.estado !== "ok", "mb-naranja"],
  ["firmas", "📩 Reclamar Firmas", f => f.hito_firmas !== "ok", "mb-azul"],
  ["movimiento", "📩 Reclamar Movimiento", f => !!f.inactivo_96h, "mb-naranja"],
];
const CONSULTAS_UI = [
  ["tasacion", "¿Por qué no está la tasación?", f => f.tasacion_estado !== "ok"],
  ["estudio", "¿En qué estado está el estudio?", f => f.estudio_estado !== "ok"],
  ["serie", "¿En qué estado está la serie firmada?", f => (f.serie_estado || f.firma_set) !== "ok"],
];

const FILTRO0 = { broker: "", inmo: "", proy: "", viv: "", sub: "", serviu: "", periodo: "", estado: "" };

const dentroPeriodo = (f, periodo, mes) => {
  if (!periodo) return true;
  if (periodo === "mes") return (f.creado || "").startsWith(mes) || (f.actualizado || "").startsWith(mes);
  const dias = periodo === "30d" ? 30 : 90;
  const ref = f.actualizado || f.creado || "";
  if (!ref) return false;
  return (Date.now() - new Date(ref).getTime()) <= dias * 86400000;
};
const enEstado = (f, estado) => {
  if (!estado) return true;
  if (estado === "activa") return !f.escritura_firmada;
  if (estado === "escriturada") return !!f.escritura_firmada;
  if (estado === "reparos") return (f.reparos_pendientes || 0) > 0;
  if (estado === "sin_actividad") return !!f.inactivo_96h;
  if (estado === "dicom") return !!f.dicom;
  if (estado === "proyectado") return !!(f.proyeccion_mes);
  if (estado === "cuello") return (f.consultas_abiertas || 0) > 0 || f.tasacion_estado !== "ok" || f.estudio_estado === "alerta";
  return true;
};

export default function GerenciaComercialModule() {
  const [data, setData] = useState(null);
  const [busyRec, setBusyRec] = useState("");
  const [reparosModal, setReparosModal] = useState(null);
  const [hiloModal, setHiloModal] = useState(null);
  const [hiloBusy, setHiloBusy] = useState(false);
  const [busyPdf, setBusyPdf] = useState(false);

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

  const exportarPdf = async () => {
    const pin = window.prompt("Exportación PDF protegida.\nIngrese el PIN maestro:");
    if (!pin) return;
    setBusyPdf(true);
    try {
      const r = await axios.get(`${API}/api/gerencia-comercial/export-pdf`,
        { params: { pin: pin.trim() }, responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url; a.download = `Reporte_Gerencia_${data?.mes || ""}.pdf`; a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      let det = "Error al generar el PDF";
      try { det = JSON.parse(await e.response.data.text()).detail || det; } catch { /* blob sin json */ }
      window.alert(det);
    }
    setBusyPdf(false);
  };

  const consultarHito = async (f, hito) => {
    setHiloBusy(true);
    try {
      await axios.post(`${API}/api/trazabilidad/consulta/${f.folder_id}`, { hito });
      const r = await axios.get(`${API}/api/trazabilidad/comunicaciones/${f.folder_id}`);
      setHiloModal({ cliente: f.cliente, fid: f.folder_id, hilos: r.data.hilos || [] });
      recargar();
    } catch (e) {
      window.alert(e.response?.data?.detail || "No se pudo registrar la consulta");
    }
    setHiloBusy(false);
  };

  const abrirHilo = async (f) => {
    try {
      const r = await axios.get(`${API}/api/trazabilidad/comunicaciones/${f.folder_id}`);
      setHiloModal({ cliente: f.cliente, fid: f.folder_id, hilos: r.data.hilos || [] });
    } catch (e) {
      window.alert(e.response?.data?.detail || "No se pudo cargar el hilo");
    }
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

  // CENTRO DE FILTRADO en memoria: período · ejecutivo/broker · estado · segmento + oficiales
  const cartera = useMemo(() => {
    let fs = data?.cartera || [];
    const mes = data?.mes || "";
    if (filtro.periodo) fs = fs.filter(f => dentroPeriodo(f, filtro.periodo, mes));
    if (filtro.estado === "proyectado") fs = fs.filter(f => (f.proyeccion_mes || "") === mes);
    else if (filtro.estado) fs = fs.filter(f => enEstado(f, filtro.estado));
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

  const res = data?.resumen || {};

  const Tarjeta = ({ k, titulo, val, activo, onClick }) => (
    <button data-testid={`gerencia-card-${k}`} onClick={onClick}
      style={{ ...panel, cursor: "pointer", display: "flex", flexDirection: "column", alignItems: "flex-start",
        gap: 2, minWidth: 160, padding: "0.6rem 0.9rem",
        borderColor: activo ? ORO : BORDE, background: activo ? "rgba(201,162,39,0.1)" : "#0c0c0c" }}>
      <span style={{ fontSize: "0.56rem", color: "#8a8a8a", letterSpacing: "0.14em", fontWeight: 800 }}>{titulo}</span>
      <span style={{ fontSize: "0.9rem", color: ORO_CLARO, fontWeight: 800 }}>{val?.n ?? 0} ops · {Number(val?.uf ?? 0).toLocaleString("es-CL")} UF</span>
    </button>
  );

  const lblF = { color: "#8a8a8a", fontSize: "0.6rem", fontWeight: 700, letterSpacing: 1 };

  return (
    <div className="module-content seamless-scope" data-testid="gerencia-module"
      style={{ minHeight: "100%", padding: "1.2rem", borderRadius: 12, background: "#050505" }}>

      {/* ═══ CABECERA DE MANDO ═══ */}
      <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap", marginBottom: 16,
        borderBottom: `1px solid ${BORDE}`, paddingBottom: 12 }}>
        <h3 style={{ margin: 0, color: ORO, fontSize: "1.1rem", letterSpacing: 2, fontFamily: "Georgia, serif" }}>
          GERENCIA COMERCIAL — CENTRO DE MANDO
        </h3>
        <span style={{ color: "#8a8a8a", fontSize: "0.7rem" }}>
          Mes {data?.mes || "…"} · {cartera.length}/{data?.total ?? 0} operaciones · Auditoría DashAI: {(data?.ultima_auditoria_dashai || "").slice(0, 16) || "pendiente"}</span>
        {data?.cumplimiento_broker?.actualizado && (
          <span data-testid="gerencia-cumplimiento-broker" title="Sincronizado en tiempo real con la Supercarpeta (Meta de Proyección)"
            style={{ background: "rgba(201,162,39,0.1)", border: `1px solid ${BORDE}`, color: ORO,
              borderRadius: 8, padding: "0.35rem 0.7rem", fontWeight: 800, fontSize: "0.7rem" }}>
            📈 Cumplimiento Broker: {data.cumplimiento_broker.pct_global ?? 0}% · UF cerradas {Number(data.cumplimiento_broker.uf_cerradas || 0).toLocaleString("es-CL")} / {Number(data.cumplimiento_broker.meta_uf || 0).toLocaleString("es-CL")}
          </span>
        )}
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button data-testid="btn-export-pdf" onClick={exportarPdf} disabled={busyPdf}
            style={{ background: "transparent", border: `1px solid ${ORO}`, color: ORO, borderRadius: 8,
              padding: "0.45rem 1rem", cursor: "pointer", fontWeight: 800, fontSize: "0.68rem", letterSpacing: 1 }}>
            <i className="fa fa-file-pdf-o" /> {busyPdf ? "GENERANDO…" : "PDF (PIN)"}
          </button>
          <button data-testid="btn-export-gerencia" onClick={exportar}
            style={{ background: ORO, border: "none", color: "#0a0a0a", borderRadius: 8,
              padding: "0.45rem 1rem", cursor: "pointer", fontWeight: 900, fontSize: "0.68rem", letterSpacing: 1 }}>
            <i className="fa fa-file-excel-o" /> EXCEL
          </button>
        </div>
      </div>

      {/* ═══ KPIs + RANKING + ALERTAS + TABLA EJECUTIVOS (fusión Gestión de Ejecutivos) ═══ */}
      <CentroMandoGerencia />

      {/* ═══ ACTIVIDAD EN TIEMPO REAL POR EJECUTIVO (ex módulo Gestión Ejecutivos) ═══ */}
      <div style={{ ...panel, padding: "1rem 1.2rem", marginBottom: 14 }}>
        <GestionEjecutivosModule />
      </div>

      {/* ═══ VISIÓN COMERCIAL (subdivisiones, comparativos) ═══ */}
      <PanelComercial />

      {/* ═══ CABECERA SEGMENTADA: sumatorias con filtrado dinámico ═══ */}
      <div className="gerencia-filtros" data-testid="gerencia-cards" style={{ margin: "14px 0 12px" }}>
        <Tarjeta k="subsidio" titulo="CON SUBSIDIO" val={res.subsidio} activo={filtro.sub === "con"}
          onClick={() => setFiltro({ ...filtro, sub: filtro.sub === "con" ? "" : "con" })} />
        <Tarjeta k="sin_subsidio" titulo="SIN SUBSIDIO" val={res.sin_subsidio} activo={filtro.sub === "sin"}
          onClick={() => setFiltro({ ...filtro, sub: filtro.sub === "sin" ? "" : "sin" })} />
        <div data-testid="gerencia-card-filtrado" style={{ ...panel, display: "flex", flexDirection: "column",
          alignItems: "flex-start", gap: 2, minWidth: 180, padding: "0.6rem 0.9rem", borderColor: ORO }}>
          <span style={{ fontSize: "0.56rem", color: ORO, letterSpacing: "0.14em", fontWeight: 800 }}>Σ RESULTADO FILTRADO</span>
          <span style={{ fontSize: "0.9rem", color: ORO_CLARO, fontWeight: 800 }}>{cartera.length} ops · {Math.round(ufFiltrado).toLocaleString("es-CL")} UF</span>
        </div>
        <button data-testid="gerencia-card-total" onClick={() => setFiltro(FILTRO0)}
          style={{ ...panel, cursor: "pointer", display: "flex", flexDirection: "column", alignItems: "flex-start",
            gap: 2, minWidth: 160, padding: "0.6rem 0.9rem" }}>
          <span style={{ fontSize: "0.56rem", color: "#8a8a8a", letterSpacing: "0.14em", fontWeight: 800 }}>TOTAL (limpiar filtros)</span>
          <span style={{ fontSize: "0.9rem", color: "#f5f0e1", fontWeight: 800 }}>{res.total?.n ?? 0} ops · {Number(res.total?.uf ?? 0).toLocaleString("es-CL")} UF</span>
        </button>
      </div>

      {/* ═══ CENTRO DE FILTRADO: período · ejecutivo · estado · segmento + oficiales ═══ */}
      <div className="gerencia-filtros" data-testid="gerencia-filtros"
        style={{ ...panel, padding: "0.7rem 0.9rem", marginBottom: 12, alignItems: "flex-end" }}>
        <label style={lblF}>Período<br />
          <select data-testid="filtro-periodo" style={selEstilo} value={filtro.periodo} onChange={e => setFiltro({ ...filtro, periodo: e.target.value })}>
            <option value="">Todo</option>
            <option value="mes">Mes actual</option>
            <option value="30d">Últimos 30 días</option>
            <option value="90d">Últimos 90 días</option>
          </select>
        </label>
        <label style={lblF}>Estado de operación<br />
          <select data-testid="filtro-estado" style={selEstilo} value={filtro.estado} onChange={e => setFiltro({ ...filtro, estado: e.target.value })}>
            <option value="">Todos</option>
            <option value="activa">Activas</option>
            <option value="escriturada">Escrituradas</option>
            <option value="reparos">Con reparos</option>
            <option value="sin_actividad">Sin actividad 96h</option>
            <option value="dicom">Con DICOM (mora)</option>
            <option value="proyectado">Proyectados a escriturar</option>
            <option value="cuello">Cuello de botella (hito pendiente)</option>
          </select>
        </label>
        <label style={lblF}>Broker / Ejecutivo<br />
          <select data-testid="filtro-broker" style={selEstilo} value={filtro.broker} onChange={e => setFiltro({ ...filtro, broker: e.target.value })}>
            <option value="">Todos</option>
            {brokersOpc.map(b => <option key={b} value={b}>{b}</option>)}
          </select>
        </label>
        <label style={lblF}>Inmobiliaria<br />
          <select data-testid="filtro-inmobiliaria" style={selEstilo} value={filtro.inmo}
            onChange={e => setFiltro({ ...filtro, inmo: e.target.value, proy: "" })}>
            <option value="">Todas</option>
            {inmosOpc.map(i => <option key={i} value={i}>{i}</option>)}
          </select>
        </label>
        <label style={lblF}>Proyecto<br />
          <select data-testid="filtro-proyecto" style={{ ...selEstilo, opacity: filtro.inmo ? 1 : 0.45 }}
            disabled={!filtro.inmo} value={filtro.proy} onChange={e => setFiltro({ ...filtro, proy: e.target.value })}>
            <option value="">{filtro.inmo ? "Todos" : "Elija inmobiliaria"}</option>
            {proysOpc.map(pr => <option key={pr} value={pr}>{pr}</option>)}
          </select>
        </label>
        <label style={lblF}>Tipo de vivienda<br />
          <select data-testid="filtro-vivienda" style={selEstilo} value={filtro.viv} onChange={e => setFiltro({ ...filtro, viv: e.target.value })}>
            <option value="">Todas</option>
            <option value="nueva">Nueva</option>
            <option value="usada">Usada</option>
          </select>
        </label>
        <label style={lblF}>Subsidio<br />
          <select data-testid="filtro-subsidio" style={selEstilo} value={filtro.sub} onChange={e => setFiltro({ ...filtro, sub: e.target.value })}>
            <option value="">Todos</option>
            <option value="con">Con subsidio</option>
            <option value="sin">Sin subsidio</option>
          </select>
        </label>
        <label style={lblF}>Resolución SERVIU<br />
          <select data-testid="filtro-serviu" style={selEstilo} value={filtro.serviu} onChange={e => setFiltro({ ...filtro, serviu: e.target.value })}>
            <option value="">Todos</option>
            <option value="con">Con resolución</option>
            <option value="sin">Sin resolución</option>
          </select>
        </label>
        <button data-testid="filtro-limpiar" onClick={() => setFiltro(FILTRO0)}
          style={{ background: "rgba(239,68,68,0.1)", color: "#f87171", border: "1px solid rgba(239,68,68,0.45)",
            borderRadius: 8, padding: "0.45rem 0.9rem", fontWeight: 800, cursor: "pointer", fontSize: "0.64rem" }}>
          ✕ Limpiar filtros</button>
        <span data-testid="filtro-sumatoria" style={{ marginLeft: "auto", color: ORO, fontSize: "0.72rem", fontWeight: 900 }}>
          Σ {cartera.length} operaciones · UF {Math.round(ufFiltrado).toLocaleString("es-CL")}</span>
      </div>

      {(data?.alertas_notaria || 0) > 0 && (
        <div data-testid="gerencia-alerta-notaria" style={{ ...panel, borderColor: "#ef4444", color: "#fca5a5", padding: "0.6rem 1rem", marginBottom: 12, fontSize: "0.78rem", fontWeight: 700 }}>
          🚨 {data.alertas_notaria} aviso(s) de notaría sobre firmas faltantes detectados por DashAI
        </div>
      )}
      {(data?.excepciones_recientes || []).length > 0 && (
        <div data-testid="gerencia-excepciones" style={{ ...panel, borderColor: "#f59e0b", color: "#fde68a", padding: "0.6rem 1rem", marginBottom: 12, fontSize: "0.72rem" }}>
          ⚠️ Excepciones autorizadas recientes: {data.excepciones_recientes.map(e => `${e.usuario} (${e.cliente || e.hito})`).join(" · ")}
        </div>
      )}

      {isMobile ? (
        /* 📱 VISTA MÓVIL: tarjetas apiladas (la tabla queda intacta en escritorio) */
        <div data-testid="gerencia-cards-mobile" style={{ display: "grid", gap: 10 }}>
          {cartera.map((f, idx) => (
            <div key={f.folder_id} data-testid={`gerencia-card-${f.folder_id}`}
              style={{ ...panel, padding: "0.8rem", background: f.datos_incompletos ? "rgba(58,18,18,0.6)" : (idx % 2 === 0 ? FILA_A : FILA_B) }}>
              <div style={{ display: "flex", gap: 8, alignItems: "baseline", flexWrap: "wrap" }}>
                <b style={{ color: ORO }}>{idx + 1}</b>
                <b style={{ color: "#fff", fontSize: 15, flex: 1, overflowWrap: "anywhere" }}>{f.cliente}</b>
                <span style={{ color: "#9a9483", fontFamily: "monospace", fontSize: 12 }}>{f.rut || "—"}</span>
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 4, fontSize: 12, color: "#8a8a8a", alignItems: "center" }}>
                <span>{f.inmobiliaria || f.origen || "⚠️ Sin inmobiliaria"}</span>
                {f.tipo_operacion && <span style={{ fontSize: 10, fontWeight: 800, padding: "1px 8px", borderRadius: 6,
                  background: f.tipo_operacion === "USADA" ? "rgba(34,197,94,0.12)" : "rgba(56,189,248,0.12)",
                  color: f.tipo_operacion === "USADA" ? "#22c55e" : "#38bdf8" }}>{f.tipo_operacion}</span>}
                <span style={{ color: f.subsidio ? "#4ade80" : "#8a8a8a", fontSize: 11 }}>{f.subsidio ? "Con Subsidio" : "Sin Subsidio"}</span>
                {f.dicom && <span style={{ color: "#ef4444", fontWeight: 800, fontSize: 11 }}>DICOM</span>}
                <b style={{ marginLeft: "auto", color: ORO_CLARO }}>{f.monto_credito_uf ? `${Number(f.monto_credito_uf).toLocaleString("es-CL")} UF` : "—"}</b>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginTop: 8, fontSize: 11 }}>
                <BotonEstado estado={f.documentacion} label={`Docs: ${f.documentacion === "ok" ? "✅" : f.documentacion === "proceso" ? "⏳" : "❌"}`} />
                <BotonEstado estado={f.tasacion_estado} label={`Tasación: ${f.tasacion_estado === "ok" ? "✅" : f.tasacion_estado === "proceso" ? "⏳" : "Pend."}`} />
                <BotonEstado estado={f.estudio_estado} label={`Estudio: ${f.estudio_estado === "ok" ? "✅" : f.estudio_estado === "proceso" ? "⏳" : "Pend."}`} />
                <BotonEstado estado={f.firma_set} label={`Set: ${f.firma_set === "ok" ? "✅" : f.firma_set === "proceso" ? "⏳" : "Pend."}`} />
                {f.escritura_firmada
                  ? <span style={{ color: ORO_CLARO, fontWeight: 900, fontSize: 12 }}>🏆 ESCRITURA FIRMADA</span>
                  : <BotonEstado estado="pendiente" label="Escritura: Pend." />}
              </div>
              {f.reparos_pendientes > 0 && (
                <button onClick={() => verReparos(f)} style={{ marginTop: 6, cursor: "pointer", border: "none",
                  borderRadius: 6, fontWeight: 800, fontSize: 11, padding: "3px 10px",
                  background: "rgba(239,68,68,0.15)", color: "#ef4444" }}>⚠️ {f.reparos_pendientes} reparo(s)</button>
              )}
              <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8, flexWrap: "wrap" }}>
                <label style={{ fontSize: 11, color: "#8a8a8a" }}>📅 Firma:</label>
                <input type="date" defaultValue={f.fecha_firma || ""} onBlur={e => fecharFirma(f.folder_id, e.target.value)}
                  style={{ background: "#080808", border: `1px solid ${BORDE}`,
                    color: "#e8e3d3", borderRadius: 6, padding: "0.25rem 0.4rem", fontSize: 13, width: 140 }} />
                <span style={{ fontSize: 11, color: "#7a7a7a", marginLeft: "auto" }}>{f.notaria_nombre || "Notaría por asignar"}</span>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 8 }}>
                {CONSULTAS_UI.filter(([, , cond]) => cond(f)).map(([hito, label]) => (
                  <button key={hito} data-testid={`consulta-${hito}-${f.folder_id}`}
                    className="maserati-btn mb-azul" disabled={hiloBusy}
                    style={{ minHeight: 28, padding: "0.25rem 0.5rem", fontSize: "0.58rem", borderRadius: 8 }}
                    title="Queda en el hilo de la operación. No envía correo."
                    onClick={() => consultarHito(f, hito)}>{label}</button>
                ))}
                {(f.consultas_abiertas || 0) > 0 && (
                  <button className="maserati-btn" data-testid={`hilo-${f.folder_id}`}
                    style={{ minHeight: 28, padding: "0.25rem 0.5rem", fontSize: "0.58rem", borderRadius: 8 }}
                    onClick={() => abrirHilo(f)}>Hilo ({f.consultas_abiertas})</button>
                )}
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
          {!data && <p style={{ color: "#8a8a8a", textAlign: "center", padding: "2rem" }}>Cargando cartera…</p>}
          {data && cartera.length === 0 && <p style={{ color: "#8a8a8a", textAlign: "center", padding: "2rem" }}>Sin operaciones con los filtros aplicados.</p>}
        </div>
      ) : (
      <div style={{ ...panel, overflow: "auto", maxHeight: "calc(100vh - 130px)" }}>
        <table data-testid="gerencia-tabla" style={{ width: "100%", borderCollapse: "collapse", fontSize: 14, color: "#e8e3d3", minWidth: 1900 }}>
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
                  height: 52, borderBottom: "1px solid rgba(201,162,39,0.12)",
                  background: f.datos_incompletos ? "rgba(58,18,18,0.55)" : (idx % 2 === 0 ? FILA_A : FILA_B) }}>
                {/* 1. CLIENTE (nombre + RUT) */}
                <td style={{ ...tdG, fontWeight: 700, fontSize: 15, color: "#FFFFFF", whiteSpace: "nowrap" }}>
                  {f.cliente}
                  {f.dicom && <span title="Cliente con morosidad vigente en DICOM" style={{ marginLeft: 6, color: "#ef4444",
                    fontWeight: 900, fontSize: "0.6rem", border: "1px solid rgba(239,68,68,0.5)", borderRadius: 5, padding: "1px 5px" }}>DICOM</span>}
                  <div style={{ fontFamily: "monospace", fontWeight: 400, fontSize: 14, color: "#9a9483" }}>{f.rut || "—"}</div>
                  {f.datos_incompletos && <div data-testid={`broker-no-actualizado-${f.folder_id}`} style={{ color: "#ef4444", fontSize: "0.62rem", fontWeight: 800 }}>🔴 Broker no actualizado</div>}
                  {f.inactivo_96h && !f.datos_incompletos && <div style={{ color: "#8a8a8a", fontSize: "0.6rem" }}>⏸ Sin actividad 96h</div>}
                  {f.alerta_notaria && <div title={f.alerta_notaria} style={{ color: "#fb7185", fontSize: "0.62rem", fontWeight: 600,
                    maxWidth: 230, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.alerta_notaria}</div>}
                </td>
                {/* 2. INMOBILIARIA */}
                <td data-testid={`gerencia-origen-${f.folder_id}`} style={{ ...tdG,
                    color: (!f.inmobiliaria && (f.origen || "").startsWith("⚠️")) ? "#ef4444" : "#b8b2a0", fontWeight: 700 }}
                  title="Regla #58: prohibido 'Directo' — se prioriza la identidad de la Inmobiliaria">
                  {f.inmobiliaria || f.origen || "⚠️ Falta Identidad de Inmobiliaria"}
                  {f.tipo_operacion && <div data-testid={`gerencia-tipo-${f.folder_id}`} style={{ marginTop: 3 }}>
                    <span style={{ fontSize: "0.6rem", fontWeight: 800, padding: "0.15rem 0.5rem", borderRadius: 6,
                      background: f.tipo_operacion === "USADA" ? "rgba(34,197,94,0.12)" : "rgba(56,189,248,0.12)",
                      color: f.tipo_operacion === "USADA" ? "#22c55e" : "#38bdf8" }}>{f.tipo_operacion}</span></div>}
                </td>
                {/* 3. PROYECTO */}
                <td style={{ ...tdG, color: "#9a9483" }}>{f.proyecto || <i style={{ color: "#6a6a6a" }}>Pendiente</i>}</td>
                {/* 4. CIUDAD */}
                <td style={{ ...tdG, color: "#8a8a8a" }}>{f.ciudad || <i style={{ color: "#6a6a6a" }}>Por Confirmar</i>}</td>
                {/* 5. BROKER */}
                <td style={{ ...tdG, color: "#b8b2a0", fontStyle: "italic", whiteSpace: "nowrap" }}>{f.broker_origen || "—"}</td>
                {/* 6. SUBSIDIO */}
                <td style={{ ...tdG, whiteSpace: "nowrap" }}>{f.subsidio
                  ? <span style={{ color: "#4ade80", fontWeight: 700 }}>Con Subsidio</span>
                  : <span style={{ color: "#8a8a8a" }}>Sin Subsidio</span>}</td>
                {/* 7. MONTO UF */}
                <td style={{ ...tdG, textAlign: "right", fontWeight: 800, color: ORO, whiteSpace: "nowrap" }}>
                  {f.monto_credito_uf ? <>{Number(f.monto_credito_uf).toLocaleString("es-CL")} <span style={{ color: "#9a9483", fontWeight: 400 }}>UF</span></> : "—"}</td>
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
                        background: "rgba(239,68,68,0.15)", color: "#ef4444" }}>
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
                    style={{ background: "#080808", border: `1px solid ${BORDE}`,
                      color: "#e8e3d3", borderRadius: 6, padding: "0.25rem 0.4rem", fontSize: 14, width: 140 }} />
                </td>
                {/* 13. NOTARÍA: nombre + estado en dos líneas */}
                <td data-testid={`gerencia-notaria-${f.folder_id}`} style={{ ...tdG }}>
                  <div style={{ fontWeight: 700, color: f.notaria_nombre ? "#b8b2a0" : "#8a8a8a",
                    fontStyle: f.notaria_nombre ? "normal" : "italic" }}>{f.notaria_nombre || "Por Asignar"}</div>
                  <div style={{ marginTop: 3, fontSize: 14,
                    color: f.notaria_estado_escritura === "Escritura Lista Para Firmar" ? "#4ade80"
                      : f.notaria_estado_escritura === "En Preparación" ? "#60a5fa" : "#8a8a8a",
                    fontWeight: f.notaria_estado_escritura === "Pendiente" ? 400 : 700,
                    fontStyle: f.notaria_estado_escritura === "Pendiente" ? "italic" : "normal" }}>
                    {f.notaria_estado_escritura}</div>
                </td>
                {/* 14. FIRMA DE ESCRITURA EN NOTARÍA — HITO FINAL */}
                <td data-testid={`gerencia-firma-escritura-${f.folder_id}`} style={{ ...tdG, textAlign: "center" }}>
                  {f.escritura_firmada
                    ? <span style={{ color: ORO_CLARO, fontWeight: 900, fontSize: 15, textShadow: "0 0 12px rgba(201,162,39,0.4)" }}>🏆 FIRMADA</span>
                    : <span style={estBtnStyle("pendiente")}>Pendiente</span>}
                </td>
                <td style={{ ...tdG, padding: "10px 10px" }}>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 4, maxWidth: 360, alignItems: "center" }}>
                    {CONSULTAS_UI.filter(([, , cond]) => cond(f)).map(([hito, label]) => (
                      <button key={hito} data-testid={`consulta-${hito}-${f.folder_id}`}
                        className="maserati-btn mb-azul" disabled={hiloBusy}
                        style={{ minHeight: 28, padding: "0.25rem 0.5rem", fontSize: "0.58rem", borderRadius: 8 }}
                        title="Queda en el hilo de la operación. No envía correo."
                        onClick={() => consultarHito(f, hito)}>{label}</button>
                    ))}
                    {(f.consultas_abiertas || 0) > 0 && (
                      <button className="maserati-btn" data-testid={`hilo-${f.folder_id}`}
                        style={{ minHeight: 28, padding: "0.25rem 0.5rem", fontSize: "0.58rem", borderRadius: 8 }}
                        onClick={() => abrirHilo(f)}>Hilo ({f.consultas_abiertas})</button>
                    )}
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
        {!data && <p style={{ color: "#8a8a8a", textAlign: "center", padding: "2rem" }}>Cargando cartera…</p>}
        {data && cartera.length === 0 && <p style={{ color: "#8a8a8a", textAlign: "center", padding: "2rem" }}>Sin operaciones con los filtros aplicados.</p>}
      </div>
      )}
      <p data-testid="costo-desarrollo" style={{ color: "#6a6a6a", fontSize: "0.68rem", marginTop: 12 }}>
        ⚡ Costo de Desarrollo del mes: <b style={{ color: ORO }}>{data?.costo_desarrollo_creditos ?? 0} créditos</b> (estimado por consumo real de IA — Ley de Eficiencia #23)
        · Cada clic queda en el Log de Gestión Gerencial (Regla #52)
      </p>
      {reparosModal && (
        <div data-testid="gerencia-reparos-modal" onClick={() => setReparosModal(null)}
          style={{ position: "fixed", inset: 0, zIndex: 200, background: "rgba(0,0,0,0.85)",
            display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem" }}>
          <div onClick={e => e.stopPropagation()} style={{ width: "100%", maxWidth: 560, maxHeight: "80vh", overflowY: "auto",
            background: "#0a0a0a", border: `1px solid ${BORDE}`, borderRadius: 12, padding: "1.4rem 1.6rem", boxShadow: "0 30px 80px rgba(0,0,0,0.7)" }}>
            <h4 style={{ margin: 0, color: "#ef4444", fontSize: "0.9rem" }}>⚠️ Reparos del abogado — {reparosModal.cliente}</h4>
            {reparosModal.loading && <p style={{ color: "#8a8a8a", fontSize: "0.7rem" }}>Cargando texto íntegro…</p>}
            {reparosModal.error && <p style={{ color: "#ef4444", fontSize: "0.7rem" }}>{reparosModal.error}</p>}
            {!reparosModal.loading && (reparosModal.reparos || []).length === 0 && !reparosModal.error &&
              <p style={{ color: "#8a8a8a", fontSize: "0.7rem" }}>Sin texto de reparos registrado en la carpeta.</p>}
            {(reparosModal.reparos || []).map((r, i) => (
              <div key={i} style={{ marginTop: 10, padding: "0.7rem 0.9rem", background: "rgba(239,68,68,0.07)",
                borderLeft: "3px solid #ef4444", borderRadius: 8 }}>
                {(r.texto || r.detalle) && <div style={{ color: "#f5f0e1", fontSize: "0.7rem", whiteSpace: "pre-wrap" }}>{r.texto || r.detalle}</div>}
                {!r.texto && !r.detalle && <div style={{ color: "#f5f0e1", fontSize: "0.7rem", whiteSpace: "pre-wrap" }}>{r.asunto || (typeof r === "string" ? r : JSON.stringify(r).slice(0, 300))}</div>}
                {(r.fecha || r.remitente) && <div style={{ color: "#8a8a8a", fontSize: "0.6rem", marginTop: 4 }}>
                  {(r.fecha || "").slice(0, 16).replace("T", " ")} {r.remitente ? `· ${r.remitente}` : ""}</div>}
              </div>
            ))}
            <button data-testid="gerencia-reparos-cerrar" onClick={() => setReparosModal(null)} className="maserati-btn" style={{ marginTop: 14 }}>Cerrar</button>
          </div>
        </div>
      )}
      {hiloModal && (
        <div data-testid="gerencia-hilo-modal" onClick={() => setHiloModal(null)}
          style={{ position: "fixed", inset: 0, zIndex: 200, background: "rgba(0,0,0,0.85)",
            display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem" }}>
          <div onClick={e => e.stopPropagation()} style={{ width: "100%", maxWidth: 560, maxHeight: "80vh", overflowY: "auto",
            background: "#0a0a0a", border: `1px solid ${BORDE}`, borderRadius: 12, padding: "1.4rem 1.6rem" }}>
            <h4 style={{ margin: 0, color: ORO, fontSize: "0.9rem" }}>Hilo de la operación — {hiloModal.cliente}</h4>
            <p style={{ color: "#8a8a8a", fontSize: "0.62rem", margin: "6px 0 10px" }}>Comunicación interna. No sale correo.</p>
            {(hiloModal.hilos || []).length === 0 && <p style={{ color: "#8a8a8a", fontSize: "0.7rem" }}>Sin consultas aún.</p>}
            {(hiloModal.hilos || []).map(h => (
              <div key={h.id} style={{ marginTop: 10, padding: "0.7rem 0.9rem", background: "rgba(201,162,39,0.07)",
                borderLeft: `3px solid ${ORO}`, borderRadius: 8 }}>
                <div style={{ color: ORO, fontSize: "0.68rem", fontWeight: 800 }}>{h.pregunta} · {h.estado}</div>
                {(h.mensajes || []).map(m => (
                  <div key={m.id} style={{ color: "#f5f0e1", fontSize: "0.7rem", marginTop: 6 }}>
                    <b>{m.autor}</b> ({m.tipo}): {m.texto}
                    <div style={{ color: "#8a8a8a", fontSize: "0.58rem" }}>{String(m.fecha || "").slice(0, 16).replace("T", " ")}</div>
                  </div>
                ))}
              </div>
            ))}
            <button data-testid="gerencia-hilo-cerrar" onClick={() => setHiloModal(null)} className="maserati-btn" style={{ marginTop: 14 }}>Cerrar</button>
          </div>
        </div>
      )}
    </div>
  );
}
