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
  const [camp, setCamp] = useState({ listado_id: "", template: "", asunto: "" });
  const [wa, setWa] = useState({ listado_id: "", mensaje: "" });
  const [waLinks, setWaLinks] = useState([]);
  const [twilio, setTwilio] = useState({ sid: "", token: "", numero: "" });
  const [showTwilio, setShowTwilio] = useState(false);
  const fileCorreo = useRef(null);
  const fileWa = useRef(null);
  const fileDs19 = useRef(null);

  const cargar = useCallback(() => {
    axios.get(`${API}/api/publicidad/listados`).then(r => setData(r.data)).catch(e => setMsg("❌ " + (e.response?.data?.detail || "Error")));
    axios.get(`${API}/api/publicidad/envios`).then(r => setEnvios(r.data.envios || [])).catch(() => {});
    axios.get(`${API}/api/publicidad/captacion`).then(r => setCapta(r.data)).catch(() => {});
    axios.get(`${API}/api/publicidad/pendientes`).then(r => setPend(r.data)).catch(() => {});
  }, []);
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

  const importar = (file, nombre) => accion(async () => {
    const fd = new FormData();
    fd.append("archivo", file);
    if (nombre) fd.append("nombre", nombre);
    return axios.post(`${API}/api/publicidad/listados/importar`, fd);
  });

  const enviarCampana = (prueba) => accion(async () => {
    if (!prueba && !window.confirm("¿Confirmas el envío REAL de la campaña al listado seleccionado?")) return { data: { mensaje: "Envío cancelado" } };
    return axios.post(`${API}/api/publicidad/enviar`, { ...camp, prueba, confirmado: !prueba });
  });

  const generarWa = () => accion(async () => {
    const r = await axios.post(`${API}/api/publicidad/whatsapp-links`, wa);
    setWaLinks(r.data.links || []);
    r.data.mensaje = `${(r.data.links || []).length} enlace(s) de WhatsApp generados`;
    return r;
  });

  const guardarTwilio = () => accion(async () => {
    const r = await axios.post(`${API}/api/whatsapp-twilio/credenciales`, twilio);
    setShowTwilio(false);
    return r;
  });

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
      <div style={sec} data-testid="campanas-correo">
        <Encabezado n="2" titulo="Campañas de Correo" sub="Templates corporativos · envío pausado (6 s) para proteger la reputación del dominio" />
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
          {data.templates.map(t => (
            <div key={t.archivo} data-testid={`template-${t.archivo}`} onClick={() => setCamp({ ...camp, template: t.archivo })}
              style={{ cursor: "pointer", border: `1.5px solid ${camp.template === t.archivo ? ORO : "rgba(148,163,184,0.25)"}`, borderRadius: 10, padding: "0.6rem 0.9rem", background: camp.template === t.archivo ? "rgba(212,175,55,0.08)" : "rgba(255,255,255,0.03)" }}>
              <div style={{ color: "#fff", fontWeight: 800, fontSize: "0.72rem" }}>✉ {t.nombre}</div>
              <a href={`/${t.archivo}`} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()} style={{ color: "#38bdf8", fontSize: "0.62rem" }}>👁 Ver template</a>
            </div>
          ))}
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 8 }}>
          <select data-testid="pub-camp-listado" style={inp} value={camp.listado_id} onChange={e => setCamp({ ...camp, listado_id: e.target.value })}>
            <option value="">— Listado de contactos —</option>
            {listadosCorreo.map(l => <option key={l.id} value={l.id}>{`${l.nombre} (${(l.contactos || []).filter(c => c.tipo === "correo").length} correos)`}</option>)}
          </select>
          <input data-testid="pub-camp-asunto" style={inp} placeholder="Asunto del correo" value={camp.asunto} onChange={e => setCamp({ ...camp, asunto: e.target.value })} />
          <div>
            <input ref={fileCorreo} type="file" accept=".xlsx,.csv,.txt" style={{ display: "none" }}
              onChange={e => { if (e.target.files[0]) { importar(e.target.files[0]); e.target.value = ""; } }} />
            <button data-testid="pub-importar-correo" disabled={busy} style={{ ...ghostBtn, width: "100%" }} onClick={() => fileCorreo.current?.click()}>📂 Cargar listado (Excel / CSV)</button>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
          <button data-testid="pub-enviar-prueba" disabled={busy || !camp.template || !camp.asunto} style={{ ...ghostBtn, color: "#38bdf8", borderColor: "#38bdf8", background: "rgba(56,189,248,0.08)" }} onClick={() => enviarCampana(true)}>📧 Enviar PRUEBA a mí</button>
          <button data-testid="pub-enviar-campana" disabled={busy || !camp.listado_id || !camp.template || !camp.asunto} style={goldBtn} onClick={() => enviarCampana(false)}>🚀 ENVIAR CAMPAÑA</button>
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
          <select data-testid="pub-wa-listado" style={inp} value={wa.listado_id} onChange={e => setWa({ ...wa, listado_id: e.target.value })}>
            <option value="">— Listado con teléfonos —</option>
            {listadosTel.map(l => <option key={l.id} value={l.id}>{`${l.nombre} (${(l.contactos || []).filter(c => c.tipo === "telefono").length} teléfonos)`}</option>)}
          </select>
          <div>
            <input ref={fileWa} type="file" accept=".xlsx,.csv,.txt" style={{ display: "none" }}
              onChange={e => { if (e.target.files[0]) { importar(e.target.files[0]); e.target.value = ""; } }} />
            <button data-testid="pub-importar-wa" disabled={busy} style={{ ...ghostBtn, width: "100%" }} onClick={() => fileWa.current?.click()}>📂 Cargar Excel de teléfonos</button>
          </div>
        </div>
        <textarea data-testid="pub-wa-mensaje" style={{ ...inp, width: "100%", minHeight: 70, marginTop: 8 }} placeholder="Mensaje editable de la campaña de WhatsApp…" value={wa.mensaje} onChange={e => setWa({ ...wa, mensaje: e.target.value })} />
        <button data-testid="pub-wa-generar" disabled={busy || !wa.listado_id || !wa.mensaje} style={{ ...goldBtn, marginTop: 8 }} onClick={generarWa}>💬 Generar enlaces de envío</button>
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
    </div>
  );
}
