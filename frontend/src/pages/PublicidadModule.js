import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const ORO = "#d4af37";
const inp = { background: "rgba(255,255,255,0.05)", border: "1px solid rgba(212,175,55,0.3)", color: "#fff", padding: "0.5rem 0.7rem", borderRadius: 8, fontSize: "0.74rem", boxSizing: "border-box" };
const goldBtn = { background: "linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C)", color: "#0a0a0a", border: "none", borderRadius: 8, padding: "0.45rem 1rem", fontWeight: 800, cursor: "pointer", fontSize: "0.72rem" };
const ghostBtn = { background: "rgba(212,175,55,0.1)", color: ORO, border: "1px solid rgba(212,175,55,0.45)", borderRadius: 8, padding: "0.4rem 0.85rem", fontWeight: 700, cursor: "pointer", fontSize: "0.7rem" };
const sec = { background: "#101013", border: "1px solid rgba(212,175,55,0.25)", borderRadius: 14, padding: "1.15rem 1.25rem", marginTop: 16 };
const secTitle = { color: ORO, fontFamily: "'Playfair Display', serif", fontSize: "1.02rem", margin: 0, letterSpacing: "0.04em" };
const secSub = { color: "#8a8fa3", fontSize: "0.66rem", margin: "2px 0 0" };
const chip = (bg, fg) => ({ background: bg, color: fg, borderRadius: 20, padding: "0.14rem 0.6rem", fontSize: "0.6rem", fontWeight: 800, whiteSpace: "nowrap" });

const TIPO_DEST = {
  broker_inmobiliario: "Broker Inmobiliario",
  cliente_directo: "Cliente Directo",
  cliente_individual: "Cliente Individual",
  inmobiliaria: "Inmobiliaria",
};
const etiquetaTipo = (l) => TIPO_DEST[l.tipo_destinatario] || "Broker Inmobiliario";

const Encabezado = ({ n, titulo, sub }) => (
  <div style={{ display: "flex", alignItems: "baseline", gap: 10, borderBottom: "1px solid rgba(212,175,55,0.2)", paddingBottom: 8, marginBottom: 12 }}>
    <span style={{ color: "#0a0a0a", background: `linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C)`, borderRadius: 8, width: 26, height: 26, display: "inline-flex", alignItems: "center", justifyContent: "center", fontWeight: 900, fontSize: "0.8rem" }}>{n}</span>
    <div><h3 style={secTitle}>{titulo}</h3><p style={secSub}>{sub}</p></div>
  </div>
);

export default function PublicidadModule() {
  const [data, setData] = useState({ listados: [], templates: [] });
  const [envios, setEnvios] = useState([]);
  const [capta, setCapta] = useState({ prospectos: [], llamadas: [] });
  const [pend, setPend] = useState(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [camp, setCamp] = useState({ listado_id: "", template: "", asunto: "", limite: "" });
  const [tipoDest, setTipoDest] = useState("broker_inmobiliario");
  const [wa, setWa] = useState({ listado_id: "", mensaje: "", limite: "" });
  const [waLinks, setWaLinks] = useState([]);
  const [bases, setBases] = useState([]);
  const [cantEnvio, setCantEnvio] = useState("");
  const [hist, setHist] = useState([]);
  const [histTipo, setHistTipo] = useState("");
  const [twilio, setTwilio] = useState({ sid: "", token: "", numero: "" });
  const [showTwilio, setShowTwilio] = useState(false);
  const [preview, setPreview] = useState(null);
  const fileCorreo = useRef(null);
  const fileWa = useRef(null);
  const fileDs19 = useRef(null);

  const cargar = useCallback(() => {
    axios.get(`${API}/api/publicidad/listados`).then(r => setData(r.data)).catch(e => setMsg("❌ " + (e.response?.data?.detail || "Error")));
    axios.get(`${API}/api/publicidad/envios`).then(r => setEnvios(r.data.envios || [])).catch(() => {});
    axios.get(`${API}/api/publicidad/captacion`).then(r => setCapta(r.data)).catch(() => {});
    axios.get(`${API}/api/publicidad/pendientes`).then(r => setPend(r.data)).catch(() => {});
    axios.get(`${API}/api/publicidad/estado-bases`).then(r => setBases(r.data.bases || [])).catch(() => {});
  }, []);
  useEffect(() => {
    axios.get(`${API}/api/publicidad/historial-contactados`, { params: { tipo: histTipo } })
      .then(r => setHist(r.data.contactados || [])).catch(() => {});
  }, [histTipo, envios]);
  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => {
    if (!envios.some(e => e.estado === "enviando")) return;
    const t = setInterval(cargar, 8000);
    return () => clearInterval(t);
  }, [envios, cargar]);

  const accion = async (fn) => {
    setBusy(true);
    try { const r = await fn(); setMsg("✅ " + (r?.data?.mensaje || "Listo")); cargar(); return r; }
    catch (e) { setMsg("❌ " + (e.response?.data?.detail || "Error")); }
    finally { setBusy(false); }
  };

  const copiar = async (texto, etiqueta) => {
    try { await navigator.clipboard.writeText(texto); setMsg(`✅ ${etiqueta} copiado al portapapeles`); }
    catch { setMsg("❌ No se pudo copiar (permiso del navegador)"); }
  };

  const generarLink = (oid) => accion(async () => {
    const r = await axios.post(`${API}/api/oportunidades/${oid}/link-calificar`);
    r.data.mensaje = "Link del portal generado y guardado en el prospecto";
    return r;
  });

  const importar = (file, nombre, tipo) => accion(async () => {
    const fd = new FormData();
    fd.append("archivo", file);
    if (nombre) fd.append("nombre", nombre);
    fd.append("tipo_destinatario", tipo || tipoDest);
    return axios.post(`${API}/api/publicidad/listados/importar`, fd);
  });

  const enviarCampana = async (prueba) => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/publicidad/preview-campana`, {
        canal: "correo", template: camp.template, asunto: camp.asunto,
        listado_id: prueba ? "" : camp.listado_id, limite: Number(camp.limite) || 0 });
      setPreview({ ...r.data, prueba });
    } catch (e) { setMsg("❌ " + (e.response?.data?.detail || "Error")); }
    finally { setBusy(false); }
  };

  const generarWa = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/publicidad/preview-campana`, {
        canal: "whatsapp", mensaje: wa.mensaje, listado_id: wa.listado_id, limite: Number(wa.limite) || 0 });
      setPreview({ ...r.data, prueba: false });
    } catch (e) { setMsg("❌ " + (e.response?.data?.detail || "Error")); }
    finally { setBusy(false); }
  };

  const aprobarPreview = async () => {
    const p = preview;
    setPreview(null);
    if (p.canal === "correo" && p.prueba) {
      return accion(async () => axios.post(`${API}/api/publicidad/enviar`,
        { ...camp, limite: Number(camp.limite) || 0, prueba: true, confirmado: false, master_pin: "" }));
    }
    const master_pin = window.prompt("🏛 REGLA ORO-75 — Diseño aprobado visualmente. Ingresa el PIN maestro para confirmar el envío:") || "";
    if (!master_pin.trim()) { setMsg("❌ Envío cancelado: sin PIN maestro no se ejecuta ningún envío (ORO-75)"); return; }
    if (p.canal === "correo") {
      return accion(async () => axios.post(`${API}/api/publicidad/enviar`,
        { ...camp, limite: Number(camp.limite) || 0, prueba: false, confirmado: true, master_pin }));
    }
    return accion(async () => {
      const r = await axios.post(`${API}/api/publicidad/whatsapp-links`, { ...wa, limite: Number(wa.limite) || 0, master_pin });
      setWaLinks(r.data.links || []);
      r.data.mensaje = `${(r.data.links || []).length} enlace(s) de WhatsApp generados`
        + (r.data.excluidos_3m ? ` · ${r.data.excluidos_3m} excluido(s) por regla de 3 meses` : "");
      return r;
    });
  };

  const guardarTwilio = () => accion(async () => {
    const r = await axios.post(`${API}/api/whatsapp-twilio/credenciales`, twilio);
    setShowTwilio(false);
    return r;
  });

  const exportarHistorial = async () => {
    try {
      const r = await axios.get(`${API}/api/publicidad/historial-contactados/excel`, { params: { tipo: histTipo }, responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url; a.download = `historial_contactados${histTipo ? "_" + histTipo : ""}.xlsx`; a.click();
      URL.revokeObjectURL(url);
      setMsg("✅ Historial exportado a Excel");
    } catch { setMsg("❌ No se pudo exportar el historial"); }
  };

  const listadosCorreo = data.listados.filter(l => (l.contactos || []).some(c => c.tipo === "correo"));
  const listadosTel = data.listados.filter(l => (l.contactos || []).some(c => c.tipo === "telefono"));

  return (
    <div data-testid="publicidad-module" style={{ padding: "0.5rem", background: "#0a0a0c", minHeight: "100%" }}>
      <h2 style={{ color: ORO, fontFamily: "'Playfair Display', serif", margin: "0 0 2px", letterSpacing: "0.05em" }}>📣 Publicidad y Captación</h2>
      <p style={{ color: "#8a8fa3", fontSize: "0.7rem", margin: 0 }}>Centro de comando comercial · exclusivo del Administrador</p>
      {msg && <p data-testid="publicidad-msg" style={{ color: msg.startsWith("✅") ? "#22c55e" : "#ef4444", fontSize: "0.74rem", fontWeight: 700 }}>{msg}</p>}

      {/* ══ 1 · CAPTACIÓN INDIVIDUAL ══ */}
      <div style={sec} data-testid="captacion-individual">
        <Encabezado n="1" titulo="Captación Individual" sub={`Portales privados de precalificación · ${capta.capturas_total || 0} carga(s) de documentos recibidas`} />
        {(capta.prospectos || []).length === 0 && <p style={{ color: "#64748b", fontSize: "0.7rem" }}>Sin prospectos aún — créalos desde el Centro de Ventas VIP.</p>}
        {(capta.prospectos || []).map(p => (
          <div key={p.id} data-testid={`captacion-prospecto-${p.id}`} style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10, padding: "0.55rem 0", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
            <div style={{ minWidth: 190 }}>
              <div style={{ color: "#fff", fontWeight: 800, fontSize: "0.78rem" }}>{p.nombre}</div>
              <div style={{ color: "#8a8fa3", fontSize: "0.62rem" }}>{p.proyecto || "Sin proyecto"}{p.telefono ? ` · ${p.telefono}` : ""}</div>
            </div>
            <span style={chip(p.link ? "rgba(34,197,94,0.15)" : "rgba(148,163,184,0.15)", p.link ? "#22c55e" : "#94a3b8")}>{p.link ? "🟢 PORTAL ACTIVO" : "⚪ SIN LINK"}</span>
            <span style={chip(p.docs_subidos ? "rgba(212,175,55,0.15)" : "rgba(148,163,184,0.12)", p.docs_subidos ? ORO : "#94a3b8")}>📄 {p.docs_subidos} doc(s) subidos</span>
            <div style={{ marginLeft: "auto", display: "flex", gap: 6, flexWrap: "wrap" }}>
              <button data-testid={`captacion-generar-link-${p.id}`} disabled={busy} style={ghostBtn} onClick={() => generarLink(p.id)}>🔗 {p.link ? "Regenerar link" : "Generar link"}</button>
              {p.link && <button data-testid={`captacion-copiar-link-${p.id}`} style={ghostBtn} onClick={() => copiar(p.link, "Link del portal")}>📋 Copiar link</button>}
              {p.mensaje_whatsapp && <button data-testid={`captacion-copiar-wa-${p.id}`} style={{ ...ghostBtn, color: "#25d366", borderColor: "rgba(37,211,102,0.5)", background: "rgba(37,211,102,0.08)" }} onClick={() => copiar(p.mensaje_whatsapp, "Mensaje de WhatsApp")}>💬 Copiar WhatsApp</button>}
            </div>
          </div>
        ))}
        <div style={{ marginTop: 14 }} data-testid="captacion-llamadas">
          <b style={{ color: "#fff", fontSize: "0.72rem" }}>📞 Solicitudes de llamada ({(capta.llamadas || []).length})</b>
          {(capta.llamadas || []).map(l => (
            <div key={l.id} style={{ color: "#e2e8f0", fontSize: "0.68rem", padding: "0.3rem 0", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
              ☎ <b>{l.cliente}</b> · {l.telefono} · horario: <span style={{ color: ORO }}>{l.horario}</span>
              <span style={{ color: "#64748b" }}> · {String(l.creado_en).slice(0, 16).replace("T", " ")}</span>
            </div>
          ))}
          {(capta.llamadas || []).length === 0 && <p style={{ color: "#64748b", fontSize: "0.66rem", margin: "4px 0 0" }}>Sin solicitudes pendientes.</p>}
        </div>
      </div>

      {/* ══ 2 · CAMPAÑAS DE CORREO ══ */}
      <div style={sec} data-testid="estado-bases">
        <Encabezado n="📊" titulo="Estado de Bases de Datos" sub="Revisa registros y disponibles antes de confirmar cualquier campaña · la regla de 3 meses descuenta a los ya contactados" />
        {bases.length === 0 && <p style={{ color: "#8a8fa3", fontSize: "0.72rem" }}>Aún no hay bases cargadas.</p>}
        {bases.length > 0 && (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.72rem" }}>
              <thead><tr style={{ color: ORO, textAlign: "left", letterSpacing: 1 }}>
                <th style={{ padding: "6px 10px" }}>BASE</th><th style={{ padding: "6px 10px" }}>TIPO</th>
                <th style={{ padding: "6px 10px" }}>REGISTROS</th>
                <th style={{ padding: "6px 10px" }}>✉ CORREOS (disp./cargados)</th>
                <th style={{ padding: "6px 10px" }}>💬 WHATSAPP (disp./cargados)</th>
                <th style={{ padding: "6px 10px" }}>⛔ BLOQUEADOS 3M</th><th></th>
              </tr></thead>
              <tbody>
                {bases.map(b => (
                  <tr key={b.id} data-testid={`base-fila-${b.id}`} style={{ borderTop: "1px solid rgba(148,163,184,0.12)", color: "#e2e8f0" }}>
                    <td style={{ padding: "8px 10px", fontWeight: 800 }}>{b.nombre}</td>
                    <td style={{ padding: "8px 10px", color: "#8a8fa3" }}>{TIPO_DEST[b.tipo_destinatario] || b.tipo_destinatario}</td>
                    <td style={{ padding: "8px 10px" }}>{b.registros}</td>
                    <td style={{ padding: "8px 10px" }}><b style={{ color: b.correos_disponibles > 0 ? "#34eab9" : "#fb7185" }}>{b.correos_disponibles}</b> / {b.correos_total}</td>
                    <td style={{ padding: "8px 10px" }}><b style={{ color: b.tels_disponibles > 0 ? "#34eab9" : "#fb7185" }}>{b.tels_disponibles}</b> / {b.tels_total}</td>
                    <td style={{ padding: "8px 10px", color: b.bloqueados_3m ? "#fbbf24" : "#8a8fa3" }}>{b.bloqueados_3m}</td>
                    <td style={{ padding: "8px 10px" }}>
                      <button data-testid={`base-usar-${b.id}`} disabled={busy}
                        style={{ background: "rgba(212,175,55,0.1)", color: ORO, border: "1px solid rgba(212,175,55,0.45)", padding: "0.35rem 0.9rem", fontSize: "0.68rem", fontWeight: 800, cursor: "pointer" }}
                        onClick={() => { setCamp({ ...camp, listado_id: b.id, limite: cantEnvio }); setWa({ ...wa, listado_id: b.id, limite: cantEnvio }); setMsg(`✅ Base «${b.nombre}» seleccionada en Campañas de Correo y WhatsApp${cantEnvio ? ` · cantidad: primeros ${cantEnvio}` : ""}`); }}>
                        Usar esta base</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 14, flexWrap: "wrap" }}>
          <label style={{ color: ORO, fontSize: "0.68rem", fontWeight: 800, letterSpacing: 1 }}>CANTIDAD DE DESTINATARIOS PARA EL ENVÍO ACTUAL:</label>
          <input data-testid="bases-cantidad-envio" type="number" min="1" value={cantEnvio} placeholder="ej: 50 (vacío = todos los disponibles)"
            style={{ ...inp, width: 250 }}
            onChange={e => { setCantEnvio(e.target.value); setCamp(c => ({ ...c, limite: e.target.value })); setWa(w => ({ ...w, limite: e.target.value })); }} />
          <span style={{ color: "#8a8fa3", fontSize: "0.62rem" }}>Se aplica a la campaña de correo y de WhatsApp (ej: enviar solo a los primeros 50 disponibles)</span>
        </div>
      </div>

      {/* ══ HISTORIAL DE CONTACTADOS ══ */}
      <div style={sec} data-testid="historial-contactados">
        <Encabezado n="🕓" titulo="Historial de Contactados" sub="Quién recibió publicidad, por qué canal y cuándo se desbloquea (regla de 3 meses)" />
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 10 }}>
          <label style={{ color: ORO, fontSize: "0.68rem", fontWeight: 800, letterSpacing: 1 }}>FILTRAR POR BASE:</label>
          <select data-testid="historial-filtro-base" style={{ ...inp, width: 210 }} value={histTipo} onChange={e => setHistTipo(e.target.value)}>
            <option value="">Todas las bases</option>
            <option value="inmobiliaria">Inmobiliaria</option>
            <option value="broker_inmobiliario">Brokers</option>
            <option value="cliente_directo">Clientes Directos</option>
            <option value="cliente_individual">Cliente Individual</option>
          </select>
          <button data-testid="historial-exportar-excel" style={ghostBtn} onClick={exportarHistorial}>📥 Exportar a Excel</button>
          <span style={{ color: "#8a8fa3", fontSize: "0.64rem" }}>{hist.length} contacto(s) en el historial</span>
        </div>
        {hist.length === 0 && <p style={{ color: "#64748b", fontSize: "0.7rem" }}>Aún no hay contactados registrados{histTipo ? " para esta base" : ""} — se registran automáticamente con cada campaña real.</p>}
        {hist.length > 0 && (
          <div style={{ overflowX: "auto", maxHeight: 340, overflowY: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.7rem" }}>
              <thead><tr style={{ color: ORO, textAlign: "left", letterSpacing: 1 }}>
                <th style={{ padding: "6px 8px" }}>NOMBRE</th><th style={{ padding: "6px 8px" }}>CORREO</th>
                <th style={{ padding: "6px 8px" }}>TELÉFONO</th><th style={{ padding: "6px 8px" }}>CANAL</th>
                <th style={{ padding: "6px 8px" }}>BASE</th><th style={{ padding: "6px 8px" }}>CONTACTADO</th>
                <th style={{ padding: "6px 8px" }}>DESBLOQUEO (3M)</th><th style={{ padding: "6px 8px" }}>ESTADO</th>
              </tr></thead>
              <tbody>
                {hist.map((h, i) => (
                  <tr key={i} data-testid={`historial-fila-${i}`} style={{ borderTop: "1px solid rgba(148,163,184,0.12)", color: "#e2e8f0" }}>
                    <td style={{ padding: "7px 8px", fontWeight: 700 }}>{h.nombre}</td>
                    <td style={{ padding: "7px 8px", color: "#93c5fd" }}>{h.correo || "—"}</td>
                    <td style={{ padding: "7px 8px" }}>{h.telefono || "—"}</td>
                    <td style={{ padding: "7px 8px" }}>{h.canal === "WhatsApp" ? "💬 WhatsApp" : "✉ Correo"}</td>
                    <td style={{ padding: "7px 8px", color: "#8a8fa3" }}>{h.base}</td>
                    <td style={{ padding: "7px 8px" }}>{String(h.fecha_contactado || "").slice(0, 16).replace("T", " ")}</td>
                    <td style={{ padding: "7px 8px", color: ORO, fontWeight: 700 }}>{String(h.fecha_desbloqueo || "").slice(0, 16).replace("T", " ")}</td>
                    <td style={{ padding: "7px 8px" }}>
                      <span style={chip(h.bloqueado ? "rgba(251,113,133,0.15)" : "rgba(52,234,185,0.12)", h.bloqueado ? "#fb7185" : "#34eab9")}>
                        {h.bloqueado ? "⛔ BLOQUEADO 3M" : "✅ DESBLOQUEADO"}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div style={sec} data-testid="campanas-correo">
        <Encabezado n="2" titulo="Campañas de Correo" sub="Templates corporativos · envío pausado (6 s) para proteger la reputación del dominio" />
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
          {data.templates.map(t => (
            <div key={t.archivo} data-testid={`template-${t.archivo}`} onClick={() => setCamp({ ...camp, template: t.archivo, asunto: camp.asunto || t.asunto || "" })}
              style={{ cursor: "pointer", border: `1.5px solid ${camp.template === t.archivo ? ORO : "rgba(148,163,184,0.25)"}`, borderRadius: 10, padding: "0.6rem 0.9rem", background: camp.template === t.archivo ? "rgba(212,175,55,0.08)" : "rgba(255,255,255,0.03)" }}>
              <div style={{ color: "#fff", fontWeight: 800, fontSize: "0.72rem" }}>✉ {t.nombre}</div>
              <a href={`/${t.archivo}`} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()} style={{ color: "#38bdf8", fontSize: "0.62rem" }}>👁 Ver template</a>
            </div>
          ))}
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 8 }}>
          <select data-testid="pub-tipo-destinatario" style={inp} value={tipoDest} onChange={e => setTipoDest(e.target.value)}>
            <option value="broker_inmobiliario">👔 Broker Inmobiliario</option>
            <option value="cliente_directo">🏠 Cliente Directo</option>
            <option value="cliente_individual">👤 Cliente Individual</option>
            <option value="inmobiliaria">🏢 Inmobiliaria</option>
          </select>
          <select data-testid="pub-camp-listado" style={inp} value={camp.listado_id} onChange={e => setCamp({ ...camp, listado_id: e.target.value })}>
            <option value="">— Listado de contactos —</option>
            {listadosCorreo.map(l => <option key={l.id} value={l.id}>{`${l.nombre} · ${etiquetaTipo(l)} (${(l.contactos || []).filter(c => c.tipo === "correo").length} correos)`}</option>)}
          </select>
          <input data-testid="pub-camp-asunto" style={inp} placeholder="Asunto del correo" value={camp.asunto} onChange={e => setCamp({ ...camp, asunto: e.target.value })} />
          <div>
            <input ref={fileCorreo} type="file" accept=".xlsx,.csv,.txt" style={{ display: "none" }}
              onChange={e => { if (e.target.files[0]) { importar(e.target.files[0]); e.target.value = ""; } }} />
            <button data-testid="pub-importar-correo" disabled={busy} style={{ ...ghostBtn, width: "100%" }} onClick={() => fileCorreo.current?.click()}>📂 Cargar base (Excel / CSV)</button>
          </div>
        </div>
        <p style={{ color: "#8a8fa3", fontSize: "0.62rem", margin: "8px 0 0" }} data-testid="pub-distribucion-nota">
          💡 Una sola subida basta: si el Excel trae columnas de <b style={{ color: ORO }}>correo</b> y <b style={{ color: "#25d366" }}>WhatsApp</b>,
          el sistema distribuye automáticamente los correos a esta campaña y los teléfonos a Campañas WhatsApp, con el tipo de destinatario elegido.
        </p>
        <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap", alignItems: "center" }}>
          <input data-testid="pub-camp-limite" type="number" min="1" style={{ ...inp, width: 190 }}
            placeholder="Cantidad a enviar (vacío = todos)" value={camp.limite}
            onChange={e => setCamp({ ...camp, limite: e.target.value })} />
          <button data-testid="pub-enviar-prueba" disabled={busy || !camp.template || !camp.asunto} style={{ ...ghostBtn, color: "#38bdf8", borderColor: "#38bdf8", background: "rgba(56,189,248,0.08)" }} onClick={() => enviarCampana(true)}>📧 Enviar PRUEBA a mí</button>
          <button data-testid="pub-enviar-campana" disabled={busy || !camp.listado_id || !camp.template || !camp.asunto} style={goldBtn} onClick={() => enviarCampana(false)}>🚀 ENVIAR CAMPAÑA</button>
          <span style={{ color: "#8a8fa3", fontSize: "0.6rem" }}>🛡 Regla anti-fatiga: quien recibió publicidad hace menos de 3 meses queda excluido automáticamente</span>
        </div>
        <div style={{ marginTop: 14 }} data-testid="pub-historial">
          <b style={{ color: "#fff", fontSize: "0.72rem" }}>Estado de campañas enviadas</b>
          {envios.map(e => (
            <div key={e.id} data-testid={`pub-envio-${e.id}`} style={{ padding: "0.35rem 0", borderBottom: "1px solid rgba(255,255,255,0.05)", fontSize: "0.68rem", color: "#e2e8f0" }}>
              {e.canal === "whatsapp" ? "💬" : "✉️"} <b>{e.listado}</b> · {e.asunto}
              <span style={{ marginLeft: 8, fontWeight: 800, color: e.estado === "terminado" ? "#22c55e" : e.estado === "enviando" ? "#f59e0b" : "#94a3b8" }}>
                {e.estado === "enviando" ? `ENVIANDO ${e.progreso || 0}/${e.total}` : (e.estado || "").toUpperCase()}</span>
              <span style={{ color: "#64748b" }}> · {e.enviados}/{e.total} ok{(e.fallidos || []).length ? ` · ${e.fallidos.length} fallidos` : ""}</span>
            </div>
          ))}
          {envios.length === 0 && <p style={{ color: "#64748b", fontSize: "0.66rem", margin: "4px 0 0" }}>Sin campañas aún.</p>}
        </div>
      </div>

      {/* ══ 3 · CAMPAÑAS WHATSAPP ══ */}
      <div style={sec} data-testid="campanas-whatsapp">
        <Encabezado n="3" titulo="Campañas WhatsApp" sub="Generador de links masivos por listado · un clic por contacto" />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 8 }}>
          <select data-testid="pub-wa-tipo-destinatario" style={inp} value={tipoDest} onChange={e => setTipoDest(e.target.value)}>
            <option value="broker_inmobiliario">👔 Broker Inmobiliario</option>
            <option value="cliente_directo">🏠 Cliente Directo</option>
            <option value="cliente_individual">👤 Cliente Individual</option>
            <option value="inmobiliaria">🏢 Inmobiliaria</option>
          </select>
          <select data-testid="pub-wa-listado" style={inp} value={wa.listado_id} onChange={e => setWa({ ...wa, listado_id: e.target.value })}>
            <option value="">— Listado con teléfonos —</option>
            {listadosTel.map(l => <option key={l.id} value={l.id}>{`${l.nombre} · ${etiquetaTipo(l)} (${(l.contactos || []).filter(c => c.tipo === "telefono").length} teléfonos)`}</option>)}
          </select>
          <div>
            <input ref={fileWa} type="file" accept=".xlsx,.csv,.txt" style={{ display: "none" }}
              onChange={e => { if (e.target.files[0]) { importar(e.target.files[0]); e.target.value = ""; } }} />
            <button data-testid="pub-importar-wa" disabled={busy} style={{ ...ghostBtn, width: "100%" }} onClick={() => fileWa.current?.click()}>📂 Cargar base (Excel / CSV)</button>
          </div>
        </div>
        <textarea data-testid="pub-wa-mensaje" style={{ ...inp, width: "100%", minHeight: 70, marginTop: 8 }} placeholder="Mensaje editable de la campaña de WhatsApp…" value={wa.mensaje} onChange={e => setWa({ ...wa, mensaje: e.target.value })} />
        <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap", alignItems: "center" }}>
          <button data-testid="pub-wa-plantilla-clientes" disabled={busy || !data.plantilla_wa_clientes}
            style={{ ...ghostBtn, color: "#25d366", borderColor: "rgba(37,211,102,0.5)", background: "rgba(37,211,102,0.08)" }}
            onClick={() => setWa({ ...wa, mensaje: data.plantilla_wa_clientes })}>📋 Plantilla Clientes Directos</button>
          <input data-testid="pub-wa-limite" type="number" min="1" style={{ ...inp, width: 190 }}
            placeholder="Cantidad a enviar (vacío = todos)" value={wa.limite}
            onChange={e => setWa({ ...wa, limite: e.target.value })} />
          <button data-testid="pub-wa-generar" disabled={busy || !wa.listado_id || !wa.mensaje} style={goldBtn} onClick={generarWa}>💬 Generar enlaces de envío</button>
          <span style={{ color: "#8a8fa3", fontSize: "0.6rem" }}>🛡 Regla anti-fatiga: 3 meses de pausa por contacto</span>
        </div>
        {waLinks.length > 0 && (
          <div style={{ marginTop: 10, display: "flex", gap: 8, flexWrap: "wrap" }} data-testid="pub-wa-links">
            {waLinks.map(l => (
              <a key={l.telefono} href={l.link} target="_blank" rel="noreferrer" data-testid={`pub-wa-link-${l.telefono}`}
                style={{ ...ghostBtn, color: "#25d366", borderColor: "#25d366", background: "rgba(37,211,102,0.08)", textDecoration: "none" }}>📱 {l.telefono}</a>
            ))}
          </div>
        )}
      </div>

      {/* ══ 4 · PENDIENTES ══ */}
      <div style={{ ...sec, border: "1px solid rgba(239,68,68,0.35)" }} data-testid="captacion-pendientes">
        <Encabezado n="4" titulo="Pendientes por Resolver" sub="Bloqueos activos del sistema de captación — resuélvelos aquí mismo" />
        {pend && (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "0.5rem 0", flexWrap: "wrap" }} data-testid="pendiente-ds19">
              <span style={chip(pend.ds19.resuelto ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)", pend.ds19.resuelto ? "#22c55e" : "#ef4444")}>
                {pend.ds19.resuelto ? "✅ RESUELTO" : "🔴 BLOQUEADO"}</span>
              <span style={{ color: "#e2e8f0", fontSize: "0.7rem", flex: 1, minWidth: 220 }}>
                <b style={{ color: ORO }}>Listado ds19 inmobiliarias</b> — {pend.ds19.resuelto ? `«${pend.ds19.nombre}» cargado con ${pend.ds19.contactos} contactos` : pend.ds19.detalle}</span>
              {!pend.ds19.resuelto && (
                <>
                  <input ref={fileDs19} type="file" accept=".xlsx,.csv,.txt" style={{ display: "none" }}
                    onChange={e => { if (e.target.files[0]) { importar(e.target.files[0], "ds19 01 inmobiliarias"); e.target.value = ""; } }} />
                  <button data-testid="pendiente-ds19-cargar" disabled={busy} style={goldBtn} onClick={() => fileDs19.current?.click()}>📂 Cargar Excel/CSV ds19</button>
                </>
              )}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "0.5rem 0", flexWrap: "wrap", borderTop: "1px solid rgba(255,255,255,0.05)" }} data-testid="pendiente-twilio">
              <span style={chip(pend.twilio.resuelto ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)", pend.twilio.resuelto ? "#22c55e" : "#ef4444")}>
                {pend.twilio.resuelto ? "✅ RESUELTO" : "🔴 BLOQUEADO"}</span>
              <span style={{ color: "#e2e8f0", fontSize: "0.7rem", flex: 1, minWidth: 220 }}>
                <b style={{ color: ORO }}>WhatsApp automático (Twilio)</b> — {pend.twilio.resuelto ? "Motor operativo con número exclusivo" : pend.twilio.detalle}</span>
              {!pend.twilio.resuelto && <button data-testid="pendiente-twilio-btn" style={goldBtn} onClick={() => setShowTwilio(!showTwilio)}>🔑 Ingresar credenciales</button>}
            </div>
            {showTwilio && (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(200px,1fr))", gap: 8, marginTop: 8, padding: "0.8rem", background: "rgba(212,175,55,0.05)", borderRadius: 10 }} data-testid="twilio-form">
                <input data-testid="twilio-sid" style={inp} placeholder="Account SID (AC…)" value={twilio.sid} onChange={e => setTwilio({ ...twilio, sid: e.target.value })} />
                <input data-testid="twilio-token" type="password" style={inp} placeholder="Auth Token" value={twilio.token} onChange={e => setTwilio({ ...twilio, token: e.target.value })} />
                <input data-testid="twilio-numero" style={inp} placeholder="Número exclusivo (+569…)" value={twilio.numero} onChange={e => setTwilio({ ...twilio, numero: e.target.value })} />
                <button data-testid="twilio-guardar" disabled={busy || !twilio.sid || !twilio.token || !twilio.numero} style={goldBtn} onClick={guardarTwilio}>💾 Activar Twilio</button>
              </div>
            )}
          </>
        )}
      </div>
      {/* ══ PREVIEW A PANTALLA COMPLETA (aprobación visual + ORO-75) ══ */}
      {preview && (
        <div data-testid="preview-fullscreen" style={{ position: "fixed", inset: 0, zIndex: 2000, background: "rgba(4,4,7,0.98)", display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "0.9rem 1.4rem", borderBottom: `1px solid ${ORO}`, flexWrap: "wrap" }}>
            <b style={{ color: ORO, fontSize: "0.95rem", letterSpacing: 1 }}>
              👁 PREVIEW {preview.canal === "whatsapp" ? "WHATSAPP" : "CORREO"} {preview.prueba ? "· ENVÍO DE PRUEBA" : "· CAMPAÑA REAL"}</b>
            {preview.canal === "correo" && <span style={{ color: "#e2e8f0", fontSize: "0.72rem" }}>Asunto: <b>{preview.asunto || "(sin asunto)"}</b> · De: {preview.remitente}</span>}
            {preview.resumen?.listado && (
              <span style={{ color: "#8a8fa3", fontSize: "0.7rem" }}>
                Base: <b style={{ color: "#fff" }}>{preview.resumen.listado}</b> · se enviará a <b style={{ color: ORO }}>{preview.resumen.destinatarios}</b> destinatario(s)
                {preview.resumen.excluidos_3m ? ` · ${preview.resumen.excluidos_3m} excluido(s) por regla 3 meses` : ""}</span>
            )}
            <div style={{ marginLeft: "auto", display: "flex", gap: 10 }}>
              <button data-testid="preview-cancelar" style={{ ...ghostBtn, color: "#ef4444", borderColor: "#ef4444" }} onClick={() => setPreview(null)}>✖ Cancelar</button>
              <button data-testid="preview-aprobar" style={goldBtn} onClick={aprobarPreview}>
                ✅ Apruebo el diseño {preview.prueba ? "→ enviar prueba" : "→ pedir MASTER_PIN"}</button>
            </div>
          </div>
          <div style={{ flex: 1, overflow: "auto", display: "flex", justifyContent: "center", padding: "1.2rem" }}>
            {preview.canal === "correo" ? (
              <iframe title="preview-correo" data-testid="preview-iframe-correo" srcDoc={preview.html}
                style={{ width: "min(780px, 100%)", height: "100%", minHeight: 600, border: `1px solid ${ORO}`, borderRadius: 8, background: "#fff" }} />
            ) : (
              <div data-testid="preview-wa-chat" style={{ width: "min(430px, 100%)", background: "#0b141a", borderRadius: 14, border: "1px solid rgba(37,211,102,0.4)", alignSelf: "flex-start" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, background: "#202c33", padding: "0.7rem 1rem", borderRadius: "14px 14px 0 0" }}>
                  <div style={{ width: 38, height: 38, borderRadius: "50%", background: ORO, color: "#111", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 900 }}>CM</div>
                  <div><div style={{ color: "#fff", fontWeight: 700, fontSize: "0.82rem" }}>Central Mutuos · Con Creces</div>
                    <div style={{ color: "#8696a0", fontSize: "0.62rem" }}>en línea</div></div>
                </div>
                <div style={{ padding: "1.2rem 0.9rem 1.4rem", backgroundImage: "radial-gradient(rgba(255,255,255,0.03) 1px, transparent 1px)", backgroundSize: "18px 18px", minHeight: 260 }}>
                  <div style={{ background: "#202c33", color: "#e9edef", borderRadius: "0 10px 10px 10px", padding: "0.65rem 0.8rem", maxWidth: "88%", fontSize: "0.82rem", lineHeight: 1.55, whiteSpace: "pre-wrap", boxShadow: "0 1px 2px rgba(0,0,0,0.4)" }}>
                    {preview.mensaje}
                    <div style={{ textAlign: "right", color: "#8696a0", fontSize: "0.6rem", marginTop: 5 }}>
                      {new Date().toLocaleTimeString("es-CL", { hour: "2-digit", minute: "2-digit" })} ✓✓</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
