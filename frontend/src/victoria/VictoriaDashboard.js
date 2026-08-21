import { useState, useEffect, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import { API_URL } from "../utils/formatters";
import { S, GOLD, PLAYFAIR, ESTADO_PILL, estadoCliente } from "./theme";

let _cache = null;

const KPI = ({ testid, label, value, sub, color }) => (
  <div data-testid={testid} style={{ ...S.card, padding: "1.6rem 1.8rem" }}>
    <div style={S.label}>{label}</div>
    <div style={{ ...S.kpiValue, color: color || "#fff" }}>{value}</div>
    {sub && <div style={{ fontSize: "0.9rem", color: "#a1a1aa", marginTop: 4 }}>{sub}</div>}
  </div>
);

export default function VictoriaDashboard({ onAbrirCliente, filtro, busqueda, onFiltro, onBusqueda }) {
  const [data, setData] = useState(_cache);
  const [nuevo, setNuevo] = useState({ nombre: "", rut: "" });
  const [creando, setCreando] = useState(false);
  const pollRef = useRef(null);

  const cargar = () => axios.get(`${API_URL}/api/victoria/dashboard`)
    .then(r => { _cache = r.data; setData(r.data); })
    .catch(e => toast.error(e.response?.data?.detail || "No se pudo cargar el panel"));

  useEffect(() => {
    cargar();
    pollRef.current = setInterval(cargar, 30000);
    return () => clearInterval(pollRef.current);
  }, []);

  const crearCliente = async (e) => {
    e.preventDefault();
    setCreando(true);
    try {
      const r = await axios.post(`${API_URL}/api/victoria/clientes`, nuevo);
      toast.success(`Ficha de ${r.data.cliente.nombre} creada en la bóveda`);
      setNuevo({ nombre: "", rut: "" });
      cargar();
    } catch (er) { toast.error(er.response?.data?.detail || "No se pudo crear la ficha"); }
    setCreando(false);
  };

  const revisarCorreo = async () => {
    try {
      const r = await axios.post(`${API_URL}/api/victoria/procesar-correo`, {});
      toast.success(r.data.mensaje || "Revisión del correo iniciada");
    } catch (e) { toast.error(e.response?.data?.detail || "Error al revisar el correo"); }
  };

  const resolverAviso = async (aid) => {
    try {
      await axios.post(`${API_URL}/api/victoria/avisos/${aid}/leido`, {});
      toast.success("Aviso marcado como resuelto");
      cargar();
    } catch { toast.error("No se pudo resolver el aviso"); }
  };

  const asignarDoc = async (did, cid) => {
    if (!cid) return;
    try {
      await axios.post(`${API_URL}/api/victoria/sin-clasificar/${did}/asignar`, { cliente_id: cid });
      toast.success("Documento asignado al cliente y re-auditado");
      cargar();
    } catch (e) { toast.error(e.response?.data?.detail || "No se pudo asignar"); }
  };

  if (!data) return <div style={{ padding: "4rem", color: "#a1a1aa", fontSize: "1.1rem" }}>Cargando panel de Victoria…</div>;

  const k = data.kpis;
  const clientes = (data.clientes || []).filter(c => {
    if (filtro === "pendientes" && c.despachado) return false;
    if (filtro === "listos" && !c.listo_envio) return false;
    if (filtro === "despachados" && !c.despachado) return false;
    const q = (busqueda || "").toLowerCase();
    return !q || c.nombre.toLowerCase().includes(q) || (c.rut || "").toLowerCase().includes(q);
  });
  const faltantesLista = (data.clientes || []).filter(c => !c.despachado && c.faltantes.length > 0);

  return (
    <div data-testid="victoria-dashboard" style={{ padding: "2.5rem 3rem", maxWidth: 1600, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: 16, marginBottom: "2rem" }}>
        <div>
          <div style={S.label}>Panel de operación · Bóveda ConCreces</div>
          <h1 style={{ ...S.h1, marginTop: 6 }}>Estado general del flujo</h1>
          {data.correo_monitoreado && <div style={{ color: "#a1a1aa", fontSize: "0.95rem", marginTop: 6 }}>
            Correo monitoreado automáticamente: <b style={{ color: "#FCF6BA" }}>{data.correo_monitoreado}</b></div>}
        </div>
        <button data-testid="dash-btn-revisar-correo" onClick={revisarCorreo} style={S.btnLine}>
          <i className="fa fa-envelope" style={{ marginRight: 8 }}></i>Revisar correo de Victoria ahora</button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))", gap: 20 }}>
        <KPI testid="kpi-clientes-pendientes" label="Clientes pendientes" value={k.clientes_pendientes}
          sub={`${k.listos_envio} listos para envío`} />
        <KPI testid="kpi-docs-faltantes" label="Documentos faltantes" value={k.docs_faltantes}
          sub="en clientes aún no enviados" color={k.docs_faltantes > 0 ? "#f59e0b" : "#4ade80"} />
        <KPI testid="kpi-validaciones" label="Validaciones aprobadas" value={k.validaciones_aprobadas}
          sub="Reglas de Oro 11-14 que coinciden" color="#4ade80" />
        <KPI testid="kpi-alertas" label="Alertas activas" value={k.alertas_activas}
          sub="avisos + alertas críticas" color={k.alertas_activas > 0 ? "#f87171" : "#4ade80"} />
        <KPI testid="kpi-estado-general" label="Estado general" value={`${k.estado_general_pct}%`}
          sub={`${k.despachados} enviados a ConCreces`} color="#FCF6BA" />
      </div>

      {(data.avisos || []).length > 0 && (
        <div data-testid="dash-avisos" style={{ ...S.card, marginTop: 24, borderColor: "rgba(239,68,68,0.35)" }}>
          <h2 style={{ ...S.h2, color: "#f87171", marginBottom: 14 }}>Alertas activas que requieren su acción ({data.avisos.length})</h2>
          {data.avisos.map(a => (
            <div key={a.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 14, padding: "0.8rem 0", borderTop: "1px solid rgba(255,255,255,0.07)" }}>
              <span style={{ ...S.body, fontSize: "0.98rem" }}>{a.detalle}</span>
              <button data-testid={`aviso-resolver-${a.id}`} onClick={() => resolverAviso(a.id)}
                style={{ ...S.btnLine, ...S.btnSmall, whiteSpace: "nowrap" }}>Marcar aviso como resuelto</button>
            </div>
          ))}
        </div>
      )}

      {(data.sin_clasificar || []).length > 0 && (
        <div data-testid="dash-sin-clasificar" style={{ ...S.card, marginTop: 24, borderColor: "rgba(245,158,11,0.35)" }}>
          <h2 style={{ ...S.h2, color: "#f59e0b", marginBottom: 6 }}>Documentos recibidos sin cliente identificado ({data.sin_clasificar.length})</h2>
          <p style={{ ...S.body, fontSize: "0.92rem", color: "#a1a1aa" }}>Asigne cada documento al cliente que corresponde: quedará en su bóveda y se re-auditará al instante.</p>
          {data.sin_clasificar.slice(0, 8).map(d => (
            <div key={d.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 14, padding: "0.7rem 0", borderTop: "1px solid rgba(255,255,255,0.07)", flexWrap: "wrap" }}>
              <span style={{ fontSize: "0.95rem", color: "#e4e4e7" }}>{d.archivo} <span style={{ color: "#71717a" }}>· {data.tipos?.[d.tipo] || d.tipo}</span></span>
              <select data-testid={`sinclasificar-select-${d.id}`} defaultValue="" style={{ ...S.input, width: 320 }}
                onChange={e => asignarDoc(d.id, e.target.value)}>
                <option value="">Asignar este documento al cliente…</option>
                {(data.clientes || []).map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
              </select>
            </div>
          ))}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 24, marginTop: 24, alignItems: "start" }}>
        <div style={{ ...S.card, padding: "1.8rem 2rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12, marginBottom: 16 }}>
            <h2 style={S.h2}>Clientes en la bóveda ({clientes.length})</h2>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <input data-testid="dash-buscador" style={{ ...S.input, width: 230, padding: "0.6rem 0.9rem" }} placeholder="Buscar por nombre o RUT…"
                value={busqueda || ""} onChange={e => onBusqueda(e.target.value)} />
              <select data-testid="dash-filtro-estado" style={{ ...S.input, width: 190, padding: "0.6rem 0.9rem" }}
                value={filtro || "todos"} onChange={e => onFiltro(e.target.value)}>
                <option value="todos">Todos los estados</option>
                <option value="pendientes">Solo pendientes</option>
                <option value="listos">Listos para envío</option>
                <option value="despachados">Enviados a ConCreces</option>
              </select>
            </div>
          </div>
          {clientes.length === 0 && <p style={{ ...S.body, color: "#71717a" }}>No hay clientes que coincidan con el filtro.</p>}
          {clientes.map(c => {
            const est = estadoCliente(c);
            const [bg, fg, txt] = ESTADO_PILL[est];
            return (
              <div key={c.id} data-testid={`cliente-fila-${c.id}`}
                style={{ borderTop: "1px solid rgba(255,255,255,0.08)", padding: "1.1rem 0", display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
                <div style={{ flex: "1 1 300px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                    <span style={{ fontFamily: PLAYFAIR, fontSize: "1.25rem", fontWeight: 700, color: "#fff" }}>{c.nombre}</span>
                    <span style={S.pill(bg, fg)}>{txt}</span>
                  </div>
                  <div style={{ color: "#a1a1aa", fontSize: "0.92rem", marginTop: 5 }}>
                    RUT {c.rut || "—"} · {c.n_docs} documento(s) · validaciones {c.validaciones_ok}/{c.validaciones_total || 4}
                    {c.alertas_criticas > 0 && <span style={{ color: "#f87171", fontWeight: 700 }}> · {c.alertas_criticas} alerta(s) crítica(s)</span>}
                  </div>
                  {c.faltantes.length > 0 && !c.despachado &&
                    <div style={{ color: "#f59e0b", fontSize: "0.92rem", marginTop: 4 }}>Faltan: {c.faltantes.join(", ")}</div>}
                  {c.siguiente && <div style={{ color: "#FCF6BA", fontSize: "0.9rem", marginTop: 4 }}>
                    Siguiente acción: {c.siguiente.titulo}</div>}
                </div>
                <button data-testid={`cliente-abrir-${c.id}`} onClick={() => onAbrirCliente(c)}
                  style={{ ...S.btnGold, ...S.btnSmall, padding: "0.75rem 1.4rem" }}>
                  Abrir ficha y flujo del cliente →</button>
              </div>
            );
          })}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div style={{ ...S.card, padding: "1.8rem 2rem" }}>
            <h2 style={{ ...S.h2, marginBottom: 8 }}>Crear ficha de cliente</h2>
            <p style={{ ...S.body, fontSize: "0.9rem", color: "#a1a1aa", margin: "0 0 14px" }}>
              Para operaciones que llegan por fuera del correo monitoreado.</p>
            <form onSubmit={crearCliente} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <input data-testid="nuevo-cliente-nombre" style={S.input} placeholder="Nombre completo del cliente" required
                value={nuevo.nombre} onChange={e => setNuevo(s => ({ ...s, nombre: e.target.value }))} />
              <input data-testid="nuevo-cliente-rut" style={S.input} placeholder="RUT del cliente (ej: 12.345.678-9)"
                value={nuevo.rut} onChange={e => setNuevo(s => ({ ...s, rut: e.target.value }))} />
              <button type="submit" data-testid="nuevo-cliente-crear" disabled={creando} style={S.btnGold}>
                {creando ? "Creando…" : "Crear ficha de cliente en la bóveda"}</button>
            </form>
          </div>

          <div style={{ ...S.card, padding: "1.8rem 2rem" }}>
            <h2 style={{ ...S.h2, marginBottom: 8 }}>Documentos faltantes por cliente</h2>
            {faltantesLista.length === 0
              ? <p style={{ ...S.body, color: "#4ade80" }}>Ningún cliente pendiente tiene documentos faltantes.</p>
              : faltantesLista.map(c => (
                <div key={c.id} style={{ padding: "0.7rem 0", borderTop: "1px solid rgba(255,255,255,0.07)" }}>
                  <div style={{ fontWeight: 700, color: "#fff", fontSize: "0.98rem" }}>{c.nombre}</div>
                  <div style={{ color: "#f59e0b", fontSize: "0.9rem", marginTop: 3 }}>{c.faltantes.join(" · ")}</div>
                </div>
              ))}
          </div>
        </div>
      </div>
    </div>
  );
}
