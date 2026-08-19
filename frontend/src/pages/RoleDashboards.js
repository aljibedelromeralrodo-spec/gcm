import { useEffect, useState } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

const TEMAS = {
  gerencia: { color: "#60a5fa", fondo: "linear-gradient(135deg,#0c1a30,#12233f)", icono: "fa-line-chart",
    titulo: "Panel de Gerencia Comercial", sub: "Visión comercial · Supercarpeta · Postventa · Administración en modo lectura",
    atajos: [["gerencia", "Gerencia Comercial", "fa-line-chart"], ["supercarpeta", "Supercarpeta", "fa-folder-open"],
      ["gestion-ejecutivos", "Gestión Ejecutivos", "fa-users"], ["postventa", "Postventa", "fa-heart"]] },
  administracion: { color: "#34d399", fondo: "linear-gradient(135deg,#07261c,#0b3327)", icono: "fa-database",
    titulo: "Panel de Administración", sub: "Módulos administrativos operativos: carpetas, documentos, correo y configuración",
    atajos: [["administracion", "Administración", "fa-database"], ["clientes", "Carpeta Clientes", "fa-folder-open"],
      ["procesamiento", "Procesamiento Correo", "fa-inbox"], ["basehistorica", "Base Histórica", "fa-university"]] },
  postventa: { color: "#f0abfc", fondo: "linear-gradient(135deg,#2a0f2e,#3b1740)", icono: "fa-heart",
    titulo: "Panel de Postventa", sub: "Seguimiento posterior a la entrega — atención y fidelización de clientes",
    atajos: [["postventa", "Módulo Postventa", "fa-heart"], ["micorreo", "Mi Correo", "fa-envelope"]] },
  contralor: { color: "#cbd5e1", fondo: "linear-gradient(135deg,#1a1d24,#252a35)", icono: "fa-eye",
    titulo: "Panel del Contralor", sub: "Auditoría absoluta — visibilidad total del sistema en modo solo lectura",
    atajos: [["contralor", "Módulo Contralor · Algoritmo Espejo", "fa-eye"], ["contraloria", "Módulo Control", "fa-search"],
      ["supercarpeta", "Supercarpeta (lectura)", "fa-folder-open"], ["dashai", "Cerebro DashAI (lectura)", "fa-lightbulb-o"]] },
  broker: { color: "#fbbf24", fondo: "linear-gradient(135deg,#2b1c05,#3d2a08)", icono: "fa-briefcase",
    titulo: "Panel Broker", sub: "Sus operaciones, proyecciones y carpetas asociadas",
    atajos: [["brokers", "Panel Broker", "fa-briefcase"], ["micorreo", "Mi Correo", "fa-envelope"]] },
};

export default function RoleDashboard({ rol, nombre, onNavigate }) {
  const t = TEMAS[rol] || TEMAS.contralor;
  return (
    <div data-testid={`dashboard-rol-${rol}`} style={{ display: "grid", gap: 16 }}>
      <div style={{ background: t.fondo, border: `1px solid ${t.color}44`, borderLeft: `5px solid ${t.color}`,
        borderRadius: 14, padding: "1.6rem 1.8rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
          <i className={`fa ${t.icono}`} style={{ fontSize: 30, color: t.color }}></i>
          <div>
            <h2 style={{ color: "#fff", fontSize: "1.35rem", margin: 0 }}>{t.titulo}</h2>
            <p style={{ color: "#94a3b8", fontSize: "0.85rem", margin: "4px 0 0" }}>{t.sub}</p>
          </div>
          <span style={{ marginLeft: "auto", color: t.color, fontSize: "0.75rem", fontWeight: 800,
            border: `1px solid ${t.color}66`, borderRadius: 999, padding: "4px 14px", letterSpacing: 1,
            textTransform: "uppercase" }}>{rol}</span>
        </div>
        <p style={{ color: "#e2e8f0", fontSize: "0.9rem", marginTop: 14 }}>
          Bienvenido(a), <b>{nombre}</b>. Este es su panel exclusivo según su rol.</p>
        {rol === "contralor" && (
          <p data-testid="sello-solo-lectura" style={{ color: "#f8fafc", background: "rgba(203,213,225,0.12)",
            border: "1px dashed #cbd5e1", borderRadius: 8, padding: "0.5rem 0.9rem", fontSize: "0.8rem", marginTop: 10 }}>
            🔒 SOLO LECTURA Y AUDITORÍA ABSOLUTA — puede ver todos los módulos, sin ejercer ningún cambio.</p>
        )}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))", gap: 12 }}>
        {t.atajos.map(([key, label, icon]) => (
          <button key={key} data-testid={`atajo-${key}`} onClick={() => onNavigate(key)}
            style={{ background: "rgba(15,23,42,0.6)", border: `1px solid ${t.color}33`, borderRadius: 12,
              padding: "1.1rem 1rem", cursor: "pointer", textAlign: "left", color: "#f1f5f9",
              display: "flex", alignItems: "center", gap: 12, fontSize: "0.9rem", fontWeight: 700 }}>
            <i className={`fa ${icon}`} style={{ color: t.color, fontSize: 18 }}></i>{label}
          </button>
        ))}
      </div>
      {rol === "gerencia" && <GerenciaPanel />}
    </div>
  );
}

// ── DASHBOARD GERENCIA: indicadores por inmobiliaria/proyecto/broker + equipo ──
const Barra = ({ label, valor, max, color }) => (
  <div style={{ marginTop: 6 }}>
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "#cbd5e1" }}>
      <span style={{ overflowWrap: "anywhere" }}>{label}</span><b style={{ color: "#f8fafc" }}>{valor}</b></div>
    <div style={{ height: 7, background: "rgba(0,0,0,0.4)", borderRadius: 99, overflow: "hidden", marginTop: 2 }}>
      <div style={{ width: `${Math.min(100, valor * 100 / (max || 1))}%`, height: "100%", background: color }} /></div>
  </div>
);

const GerenciaPanel = () => {
  const [d, setD] = useState(null);
  const [intel, setIntel] = useState(null);
  const [fBroker, setFBroker] = useState("");
  const [ccOpts, setCcOpts] = useState([]);
  const [ccSel, setCcSel] = useState([]);
  const cargarIntel = (b) => axios.get(`${API}/api/gerencia-panel/inteligencia`, { params: { broker: b || "" } })
    .then(r => setIntel(r.data)).catch(() => {});
  useEffect(() => {
    axios.get(`${API}/api/gerencia-panel/rol`).then(r => setD(r.data)).catch(() => setD({ error: true }));
    axios.get(`${API}/api/gerencia-panel/cc-opciones`).then(r => setCcOpts(r.data.opciones || [])).catch(() => {});
    cargarIntel("");
  }, []);
  const verPdf = async (fid, ruta, nota) => {
    try {
      const r = await axios.get(`${API}/api/supercarpeta/archivo/${fid}`, { params: { ruta }, responseType: "blob" });
      window.alert(nota);
      window.open(URL.createObjectURL(new Blob([r.data], { type: "application/pdf" })), "_blank");
    } catch { window.alert("PDF no disponible aún"); }
  };
  const accion = async (fid, tipo, label) => {
    const ccTxt = ccSel.length ? `\nCon copia (CC) a: ${ccSel.join(", ")}` : "\nSin copias (CC)";
    if (!window.confirm(`¿Enviar solicitud "${label}"?${ccTxt}`)) return;
    try {
      const r = await axios.post(`${API}/api/gerencia-panel/accion`, { fid, tipo, cc: ccSel });
      window.alert(`✅ ${r.data.accion} → ${r.data.para}\n${r.data.nota}`);
    } catch (e) { window.alert(e.response?.data?.detail || "Error al enviar la solicitud"); }
  };
  const toggleCc = (email) => setCcSel(s => (s.includes(email) ? s.filter(x => x !== email) : [...s, email]));
  if (!d) return <p style={{ color: "#94a3b8", fontSize: "0.8rem" }}>Cargando indicadores…</p>;
  if (d.error) return null;
  const seccion = { background: "rgba(15,23,42,0.6)", border: "1px solid rgba(96,165,250,0.25)", borderRadius: 12, padding: "1rem 1.2rem" };
  const maxDe = arr => Math.max(...(arr || []).map(x => x[1]), 1);
  const comp = d.comparativa || {};
  return (
    <div data-testid="gerencia-panel" style={{ display: "grid", gap: 12 }}>
      {/* Equipo administrativo — volumen operativo destacado */}
      <div data-testid="gerencia-equipo" style={{ ...seccion, borderColor: "rgba(212,175,55,0.4)" }}>
        <b style={{ color: "#FCF6BA", fontSize: "0.85rem" }}>👥 Actividad del Equipo Administrativo (volumen operativo, no cierres)</b>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 10, marginTop: 10 }}>
          {Object.entries(d.equipo || {}).filter(([k]) => k !== "Otros").map(([nom, v]) => (
            <div key={nom} style={{ background: "rgba(212,175,55,0.08)", border: "1px solid rgba(212,175,55,0.35)",
              borderRadius: 10, padding: "0.8rem 1rem", textAlign: "center" }}>
              <div style={{ color: "#e2e8f0", fontSize: "0.8rem", fontWeight: 800 }}>{nom}</div>
              <div style={{ color: "#FFD700", fontSize: "1.6rem", fontWeight: 900 }}>{v.hoy}</div>
              <div style={{ color: "#94a3b8", fontSize: "0.68rem" }}>gestiones HOY · {v.semana} en la semana</div>
            </div>
          ))}
          <div style={{ background: "rgba(96,165,250,0.08)", border: "1px solid rgba(96,165,250,0.35)",
            borderRadius: 10, padding: "0.8rem 1rem", textAlign: "center" }}>
            <div style={{ color: "#e2e8f0", fontSize: "0.8rem", fontWeight: 800 }}>Comparativa Semanal</div>
            <div style={{ color: "#93c5fd", fontSize: "1.6rem", fontWeight: 900 }}>{comp.semana_actual ?? 0}</div>
            <div style={{ color: "#94a3b8", fontSize: "0.68rem" }}>vs {comp.semana_anterior ?? 0} semana anterior
              {comp.variacion_pct != null && <b style={{ color: comp.variacion_pct >= 0 ? "#4ade80" : "#f87171" }}> ({comp.variacion_pct > 0 ? "+" : ""}{comp.variacion_pct}%)</b>}</div>
          </div>
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 12 }}>
        {[["🏢 Operaciones por Inmobiliaria", d.por_inmobiliaria, "#60a5fa"],
          ["📌 Por Proyecto", d.por_proyecto, "#34d399"],
          ["🤝 Por Broker de Origen", d.por_broker, "#fbbf24"]].map(([tt, arr, col]) => (
          <div key={tt} style={seccion}>
            <b style={{ color: "#e2e8f0", fontSize: "0.82rem" }}>{tt}</b>
            {(arr || []).slice(0, 8).map(([k, v]) => <Barra key={k} label={k} valor={v} max={maxDe(arr)} color={col} />)}
          </div>
        ))}
      </div>
      <div data-testid="gerencia-carpetas" style={seccion}>
        <b style={{ color: "#e2e8f0", fontSize: "0.82rem" }}>📁 Carpetas activas — etiqueta de broker de origen siempre visible</b>
        <div style={{ display: "grid", gap: 4, marginTop: 8, maxHeight: 260, overflowY: "auto" }}>
          {(d.carpetas || []).map((c, i) => (
            <div key={i} style={{ display: "flex", gap: 8, alignItems: "center", fontSize: "0.76rem",
              borderTop: "1px solid rgba(148,163,184,0.12)", padding: "4px 0", flexWrap: "wrap" }}>
              <b style={{ color: "#f8fafc", flex: 1, minWidth: 140 }}>{c.cliente}</b>
              <span style={{ color: "#94a3b8" }}>{c.inmobiliaria}{c.proyecto !== "—" ? ` · ${c.proyecto}` : ""}</span>
              <span style={{ color: "#93c5fd" }}>{c.estado}</span>
              <span style={{ background: "rgba(251,191,36,0.15)", border: "1px solid rgba(251,191,36,0.5)",
                color: "#fbbf24", borderRadius: 999, padding: "1px 9px", fontSize: "0.66rem", fontWeight: 800 }}>
                🤝 {c.broker_origen}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ═══ CENTRO DE INTELIGENCIA COMERCIAL ═══ */}
      {intel && (<>
        <div data-testid="gerencia-estadisticas" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 12 }}>
          <div style={seccion}>
            <b style={{ color: "#e2e8f0", fontSize: "0.82rem" }}>📈 Avance y aprobación por Broker</b>
            {(intel.brokers || []).map(b => (
              <div key={b.broker} style={{ marginTop: 8, fontSize: "0.74rem", color: "#cbd5e1" }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <b style={{ color: "#fbbf24" }}>🤝 {b.broker}</b>
                  <span>{b.clientes} cliente(s) · aprob. {b.tasa_aprobacion}%{b.dias_promedio_cierre != null ? ` · cierre ~${b.dias_promedio_cierre}d` : ""}</span>
                </div>
                <div style={{ height: 6, background: "rgba(0,0,0,0.4)", borderRadius: 99, overflow: "hidden", marginTop: 2 }}>
                  <div style={{ width: `${b.avance_pct}%`, height: "100%", background: "#fbbf24" }} /></div>
              </div>
            ))}
          </div>
          <div style={seccion}>
            <b style={{ color: "#e2e8f0", fontSize: "0.82rem" }}>🏷 Subsidios por tipo</b>
            {(intel.subsidios || []).map(([k, v]) => <Barra key={k} label={k} valor={v} max={maxDe(intel.subsidios)} color="#f0abfc" />)}
          </div>
          <div style={seccion} data-testid="gerencia-proyeccion">
            <b style={{ color: "#e2e8f0", fontSize: "0.82rem" }}>🎯 Real vs Proyectado ({intel.proyeccion?.mes})</b>
            <div style={{ color: "#f8fafc", fontSize: "1.3rem", fontWeight: 900, marginTop: 8 }}>
              {intel.proyeccion?.real_uf} UF <span style={{ color: "#94a3b8", fontSize: "0.75rem", fontWeight: 600 }}>/ meta {intel.proyeccion?.meta_uf} UF</span></div>
            <div style={{ height: 8, background: "rgba(0,0,0,0.4)", borderRadius: 99, overflow: "hidden", marginTop: 6 }}>
              <div style={{ width: `${Math.min(100, intel.proyeccion?.cumplimiento_pct || 0)}%`, height: "100%", background: "linear-gradient(90deg,#34d399,#a7f3d0)" }} /></div>
            <div style={{ color: "#34d399", fontSize: "0.75rem", fontWeight: 800, marginTop: 4 }}>{intel.proyeccion?.cumplimiento_pct || 0}% de cumplimiento</div>
          </div>
        </div>
        <div data-testid="gerencia-inteligencia" style={{ ...seccion, borderColor: "rgba(96,165,250,0.45)" }}>
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <b style={{ color: "#93c5fd", fontSize: "0.85rem" }}>🧭 Panel por Cliente — documentos en tiempo real (RUT cliente / RUT propiedad)</b>
            <select data-testid="gerencia-filtro-broker" value={fBroker}
              onChange={e => { setFBroker(e.target.value); cargarIntel(e.target.value); }}
              style={{ marginLeft: "auto", background: "#14263f", color: "#f8fafc", border: "1px solid rgba(96,165,250,0.4)",
                borderRadius: 8, padding: "0.3rem 0.6rem", fontSize: "0.72rem" }}>
              <option value="">Todos los brokers</option>
              {(intel.brokers || []).map(b => <option key={b.broker} value={b.broker}>{b.broker}</option>)}
            </select>
          </div>
          {/* CC LIBRE DE GERENCIA: Daniela, Victoria, ambas u otros — sin restricción */}
          <div data-testid="gerencia-cc-selector" style={{ display: "flex", gap: 6, flexWrap: "wrap",
            alignItems: "center", marginTop: 8, background: "rgba(2,6,23,0.5)",
            border: "1px dashed rgba(96,165,250,0.35)", borderRadius: 8, padding: "0.5rem 0.7rem" }}>
            <span style={{ color: "#93c5fd", fontSize: "0.7rem", fontWeight: 800 }}>📎 Con copia (CC) en las solicitudes:</span>
            {ccOpts.map(o => (
              <button key={o.email} data-testid={`cc-chip-${o.email}`} onClick={() => toggleCc(o.email)}
                title={o.email}
                style={{ fontSize: "0.66rem", fontWeight: 800, borderRadius: 999, padding: "3px 10px", cursor: "pointer",
                  background: ccSel.includes(o.email) ? "rgba(96,165,250,0.25)" : "transparent",
                  color: ccSel.includes(o.email) ? "#dbeafe" : "#94a3b8",
                  border: `1px solid ${ccSel.includes(o.email) ? "#60a5fa" : "rgba(148,163,184,0.35)"}` }}>
                {ccSel.includes(o.email) ? "✓ " : ""}{o.nombre}</button>
            ))}
            {ccSel.length === 0 && <span style={{ color: "#64748b", fontSize: "0.64rem", fontStyle: "italic" }}>sin copias seleccionadas</span>}
          </div>
          <div style={{ display: "grid", gap: 8, marginTop: 10, maxHeight: 420, overflowY: "auto" }}>
            {(intel.clientes || []).map(c => (
              <div key={c.fid} data-testid={`intel-cliente-${c.fid}`} style={{ background: "rgba(2,6,23,0.5)",
                border: "1px solid rgba(96,165,250,0.2)", borderRadius: 10, padding: "0.7rem 0.9rem" }}>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", fontSize: "0.78rem" }}>
                  <b style={{ color: "#f8fafc" }}>{c.cliente}</b>
                  <span style={{ color: "#94a3b8" }}>{c.rut}{c.rut_propiedad ? ` · Prop: ${c.rut_propiedad}` : ""}</span>
                  <span style={{ color: "#93c5fd" }}>{c.inmobiliaria}{c.proyecto ? ` · ${c.proyecto}` : ""}</span>
                  <span style={{ marginLeft: "auto", background: "rgba(251,191,36,0.15)", border: "1px solid rgba(251,191,36,0.5)",
                    color: "#fbbf24", borderRadius: 999, padding: "1px 9px", fontSize: "0.64rem", fontWeight: 800 }}>🤝 {c.broker}</span>
                </div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                  {c.docs.map(dd => (
                    <button key={dd.doc} title={`${dd.doc}: ${dd.estado}${dd.fecha ? ` el ${dd.fecha}` : ""}`}
                      onClick={() => dd.ruta ? verPdf(c.fid, dd.ruta, `${dd.doc} — ${dd.estado}${dd.fecha ? ` el ${dd.fecha}` : ""}`) : null}
                      style={{ fontSize: "0.66rem", fontWeight: 800, borderRadius: 999, padding: "3px 9px",
                        cursor: dd.ruta ? "pointer" : "default", border: "1px solid",
                        color: /recibid|actualizad|aprobad|firmado/i.test(dd.estado) ? "#4ade80" : /observa|solicitada/i.test(dd.estado) ? "#facc15" : "#94a3b8",
                        borderColor: "rgba(148,163,184,0.3)", background: "transparent" }}>
                      {/recibid|actualizad|aprobad|firmado/i.test(dd.estado) ? "✅" : /observa/i.test(dd.estado) ? "⚠️" : "○"} {dd.doc}
                      {dd.fecha ? ` · ${dd.fecha}` : ""}{dd.ruta ? " 📄" : ""}</button>
                  ))}
                </div>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                  {[["tasacion", "📨 Solicitar tasación al broker"], ["estudio", "📨 Consultar estudio de título"],
                    ["docs", "📨 Pedir actualización de documentos"]].map(([t, lb]) => (
                    <button key={t} data-testid={`accion-${t}-${c.fid}`} onClick={() => accion(c.fid, t, lb)}
                      style={{ background: "rgba(96,165,250,0.12)", border: "1px solid rgba(96,165,250,0.45)",
                        color: "#93c5fd", borderRadius: 8, padding: "3px 10px", fontSize: "0.66rem",
                        fontWeight: 800, cursor: "pointer" }}>{lb}</button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </>)}
    </div>
  );
};

export const PostventaModulo = () => (
  <div data-testid="modulo-postventa" style={{ background: "rgba(42,15,46,0.5)", border: "1px solid rgba(240,171,252,0.35)",
    borderRadius: 14, padding: "1.6rem 1.8rem" }}>
    <h2 style={{ color: "#f0abfc", fontSize: "1.2rem", margin: 0 }}><i className="fa fa-heart" /> Módulo Postventa</h2>
    <p style={{ color: "#cbd5e1", fontSize: "0.85rem", marginTop: 8 }}>
      Seguimiento posterior a la entrega: atención de requerimientos, garantías y fidelización.</p>
    <div style={{ marginTop: 14, background: "rgba(2,6,23,0.5)", borderRadius: 10, padding: "1rem",
      color: "#94a3b8", fontSize: "0.85rem", fontStyle: "italic" }}>
      Esqueleto operativo listo — los casos de postventa aparecerán aquí cuando se conecten las fuentes de correo.</div>
  </div>
);

export const NoAutorizado = ({ modulo }) => (
  <div data-testid="no-autorizado" style={{ display: "grid", placeItems: "center", minHeight: "50vh" }}>
    <div style={{ textAlign: "center", background: "rgba(30,41,59,0.6)", border: "1px solid rgba(248,113,113,0.4)",
      borderRadius: 16, padding: "2.5rem 3rem", maxWidth: 480 }}>
      <i className="fa fa-lock" style={{ fontSize: 40, color: "#f87171" }}></i>
      <h2 style={{ color: "#f8fafc", fontSize: "1.15rem", marginTop: 14 }}>No está autorizado el ingreso a este módulo</h2>
      <p style={{ color: "#94a3b8", fontSize: "0.85rem", marginTop: 8 }}>
        Su rol no tiene permisos sobre {modulo ? `el módulo "${modulo}"` : "este módulo"}. Si necesita acceso, contacte al Administrador.</p>
    </div>
  </div>
);
