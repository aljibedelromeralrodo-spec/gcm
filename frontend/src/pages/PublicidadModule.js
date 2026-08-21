import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const inp = { background: "rgba(255,255,255,0.06)", border: "1px solid rgba(212,175,55,0.3)", color: "#fff", padding: "0.45rem 0.65rem", borderRadius: 8, fontSize: "0.74rem", boxSizing: "border-box" };
const goldBtn = { background: "linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C)", color: "#0a0a0a", border: "none", borderRadius: 8, padding: "0.45rem 1rem", fontWeight: 800, cursor: "pointer", fontSize: "0.72rem" };
const sec = { background: "rgba(30,41,59,0.55)", border: "1px solid rgba(212,175,55,0.35)", borderRadius: 12, padding: "1rem", marginTop: 14 };

export default function PublicidadModule() {
  const [data, setData] = useState({ listados: [], templates: [] });
  const [envios, setEnvios] = useState([]);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [nuevo, setNuevo] = useState({ nombre: "Para Inmobiliarias", tipo_contacto: "Inmobiliaria / Empresa", contactos_texto: "", excluir_txt: "ecomac.cl" });
  const [verListado, setVerListado] = useState("");
  const [camp, setCamp] = useState({ listado_id: "", template: "", asunto: "" });
  const [wa, setWa] = useState({ listado_id: "", mensaje: "" });
  const [waLinks, setWaLinks] = useState([]);

  const cargar = useCallback(() => {
    axios.get(`${API}/api/publicidad/listados`).then(r => setData(r.data)).catch(e => setMsg("❌ " + (e.response?.data?.detail || "Error")));
    axios.get(`${API}/api/publicidad/envios`).then(r => setEnvios(r.data.envios || [])).catch(() => {});
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

  const crearListado = () => accion(async () => {
    const excluir = nuevo.excluir_txt.split(",").map(s => s.trim()).filter(Boolean);
    const r = await axios.post(`${API}/api/publicidad/listados`, { ...nuevo, excluir });
    const s = r.data.resumen;
    r.data.mensaje = `Listado «${r.data.listado.nombre}»: ${s.agregados} agregados · ${s.duplicados_eliminados} duplicados eliminados · ${s.excluidos.length} excluidos · ${s.invalidos.length} inválidos`;
    setNuevo({ ...nuevo, contactos_texto: "" });
    return r;
  });

  const enviarCampana = (prueba) => accion(async () => {
    if (!prueba && !window.confirm(`¿Confirmas el envío REAL de la campaña al listado seleccionado?`)) return { data: { mensaje: "Envío cancelado" } };
    return axios.post(`${API}/api/publicidad/enviar`, { ...camp, prueba, confirmado: !prueba });
  });

  const generarWa = () => accion(async () => {
    const r = await axios.post(`${API}/api/publicidad/whatsapp-links`, wa);
    setWaLinks(r.data.links || []);
    r.data.mensaje = `${r.data.links.length} enlace(s) de WhatsApp generados: haz clic en cada uno para enviar`;
    return r;
  });

  const lst = data.listados.find(l => l.id === verListado);

  return (
    <div data-testid="publicidad-module" style={{ padding: "0.5rem" }}>
      <h2 style={{ color: "#d4af37", fontFamily: "'Playfair Display', serif", margin: "0 0 4px" }}>📣 Publicidad</h2>
      <p style={{ color: "#94a3b8", fontSize: "0.72rem", margin: 0 }}>Campañas por correo y WhatsApp · exclusivo del Administrador</p>
      {msg && <p data-testid="publicidad-msg" style={{ color: msg.startsWith("✅") ? "#22c55e" : "#ef4444", fontSize: "0.74rem", fontWeight: 700 }}>{msg}</p>}

      {/* LISTADOS */}
      <div style={sec} data-testid="publicidad-listados">
        <b style={{ color: "#e2e8f0", fontSize: "0.8rem" }}>1 · Listados de campaña</b>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 8, marginTop: 10 }}>
          <input data-testid="pub-nombre" style={inp} placeholder="Nombre del listado" value={nuevo.nombre} onChange={e => setNuevo({ ...nuevo, nombre: e.target.value })} />
          <input data-testid="pub-tipo" style={inp} placeholder="Tipo de contacto" value={nuevo.tipo_contacto} onChange={e => setNuevo({ ...nuevo, tipo_contacto: e.target.value })} />
          <input data-testid="pub-excluir" style={inp} placeholder="Excluir (dominios/correos, coma)" value={nuevo.excluir_txt} onChange={e => setNuevo({ ...nuevo, excluir_txt: e.target.value })} />
        </div>
        <textarea data-testid="pub-contactos" style={{ ...inp, width: "100%", minHeight: 110, marginTop: 8, fontFamily: "monospace" }}
          placeholder={"Pega aquí correos y/o teléfonos (separados por comas, espacios o líneas).\nDuplicados e inválidos se eliminan solos."}
          value={nuevo.contactos_texto} onChange={e => setNuevo({ ...nuevo, contactos_texto: e.target.value })} />
        <button data-testid="pub-crear-listado" disabled={busy} style={{ ...goldBtn, marginTop: 8 }} onClick={crearListado}>💾 Guardar en listado</button>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
          {data.listados.map(l => (
            <div key={l.id} data-testid={`pub-listado-${l.id}`} style={{ border: `1.5px solid ${verListado === l.id ? "#d4af37" : "rgba(148,163,184,0.3)"}`, borderRadius: 10, padding: "0.55rem 0.8rem", background: "rgba(255,255,255,0.04)" }}>
              <div style={{ color: "#e2e8f0", fontWeight: 800, fontSize: "0.74rem", cursor: "pointer" }} onClick={() => setVerListado(verListado === l.id ? "" : l.id)}>
                📋 {l.nombre} <span style={{ color: "#d4af37" }}>({(l.contactos || []).length})</span></div>
              <div style={{ color: "#64748b", fontSize: "0.6rem" }}>{l.tipo_contacto} · {(l.contactos || []).filter(c => c.tipo === "correo").length} correos · {(l.contactos || []).filter(c => c.tipo === "telefono").length} teléfonos</div>
            </div>
          ))}
          {data.listados.length === 0 && <span style={{ color: "#64748b", fontSize: "0.7rem" }}>Sin listados aún: pega los contactos arriba y guarda.</span>}
        </div>
        {lst && (
          <div style={{ marginTop: 10, maxHeight: 180, overflowY: "auto", border: "1px solid rgba(148,163,184,0.2)", borderRadius: 8, padding: "0.5rem" }} data-testid="pub-detalle-listado">
            {(lst.contactos || []).map(c => (
              <div key={c.valor} style={{ display: "flex", gap: 8, alignItems: "center", fontSize: "0.66rem", color: "#cbd5e1", padding: "0.15rem 0" }}>
                {c.tipo === "correo" ? "✉️" : "📱"} {c.valor}
                <button style={{ marginLeft: "auto", background: "transparent", border: "none", color: "#ef4444", cursor: "pointer", fontSize: "0.66rem" }}
                  onClick={() => accion(() => axios.post(`${API}/api/publicidad/listados/${lst.id}/quitar`, { valor: c.valor }))}>✕</button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* CAMPAÑA CORREO */}
      <div style={sec} data-testid="publicidad-correo">
        <b style={{ color: "#e2e8f0", fontSize: "0.8rem" }}>2 · Campaña por correo</b>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 8, marginTop: 10 }}>
          <select data-testid="pub-camp-listado" style={inp} value={camp.listado_id} onChange={e => setCamp({ ...camp, listado_id: e.target.value })}>
            <option value="">— Listado —</option>
            {data.listados.map(l => <option key={l.id} value={l.id}>{`${l.nombre} (${(l.contactos || []).filter(c => c.tipo === "correo").length} correos)`}</option>)}
          </select>
          <select data-testid="pub-camp-template" style={inp} value={camp.template} onChange={e => setCamp({ ...camp, template: e.target.value })}>
            <option value="">— Template —</option>
            {data.templates.map(t => <option key={t.archivo} value={t.archivo}>{t.nombre}</option>)}
          </select>
          <input data-testid="pub-camp-asunto" style={inp} placeholder="Asunto del correo" value={camp.asunto} onChange={e => setCamp({ ...camp, asunto: e.target.value })} />
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap", alignItems: "center" }}>
          {camp.template && <a href={`/${camp.template}`} target="_blank" rel="noreferrer" style={{ color: "#38bdf8", fontSize: "0.68rem" }} data-testid="pub-ver-template">👁 Ver template</a>}
          <button data-testid="pub-enviar-prueba" disabled={busy || !camp.template || !camp.asunto} style={{ ...goldBtn, background: "rgba(56,189,248,0.15)", color: "#38bdf8", border: "1px solid #38bdf8" }} onClick={() => enviarCampana(true)}>📧 Enviar PRUEBA a mí</button>
          <button data-testid="pub-enviar-campana" disabled={busy || !camp.listado_id || !camp.template || !camp.asunto} style={goldBtn} onClick={() => enviarCampana(false)}>🚀 ENVIAR CAMPAÑA</button>
          <span style={{ color: "#64748b", fontSize: "0.62rem" }}>Se envía en segundo plano con pausa de 6 s entre correos (protege la reputación del dominio)</span>
        </div>
      </div>

      {/* CAMPAÑA WHATSAPP */}
      <div style={sec} data-testid="publicidad-whatsapp">
        <b style={{ color: "#e2e8f0", fontSize: "0.8rem" }}>3 · Campaña por WhatsApp</b>
        <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", gap: 8, marginTop: 10 }}>
          <select data-testid="pub-wa-listado" style={inp} value={wa.listado_id} onChange={e => setWa({ ...wa, listado_id: e.target.value })}>
            <option value="">— Listado —</option>
            {data.listados.map(l => <option key={l.id} value={l.id}>{`${l.nombre} (${(l.contactos || []).filter(c => c.tipo === "telefono").length} teléfonos)`}</option>)}
          </select>
          <textarea data-testid="pub-wa-mensaje" style={{ ...inp, minHeight: 64 }} placeholder="Mensaje de WhatsApp para la campaña…" value={wa.mensaje} onChange={e => setWa({ ...wa, mensaje: e.target.value })} />
        </div>
        <button data-testid="pub-wa-generar" disabled={busy || !wa.listado_id || !wa.mensaje} style={{ ...goldBtn, marginTop: 8 }} onClick={generarWa}>💬 Generar enlaces de envío</button>
        {waLinks.length > 0 && (
          <div style={{ marginTop: 10, display: "flex", gap: 8, flexWrap: "wrap" }} data-testid="pub-wa-links">
            {waLinks.map(l => (
              <a key={l.telefono} href={l.link} target="_blank" rel="noreferrer" data-testid={`pub-wa-link-${l.telefono}`}
                style={{ ...goldBtn, background: "rgba(37,211,102,0.15)", color: "#25d366", border: "1px solid #25d366", textDecoration: "none" }}>
                📱 {l.telefono}</a>
            ))}
          </div>
        )}
      </div>

      {/* HISTORIAL */}
      <div style={sec} data-testid="publicidad-historial">
        <b style={{ color: "#e2e8f0", fontSize: "0.8rem" }}>4 · Historial de campañas</b>
        {envios.map(e => (
          <div key={e.id} data-testid={`pub-envio-${e.id}`} style={{ padding: "0.45rem 0", borderBottom: "1px solid rgba(255,255,255,0.06)", fontSize: "0.7rem", color: "#e2e8f0" }}>
            {e.canal === "whatsapp" ? "💬" : "✉️"} <b>{e.listado}</b> · {e.asunto}
            <span style={{ marginLeft: 8, fontWeight: 800, color: e.estado === "terminado" ? "#22c55e" : e.estado === "enviando" ? "#f59e0b" : "#94a3b8" }}>
              {e.estado === "enviando" ? `ENVIANDO ${e.progreso || 0}/${e.total}` : e.estado.toUpperCase()}</span>
            <span style={{ color: "#64748b" }}> · {e.enviados}/{e.total} ok{(e.fallidos || []).length ? ` · ${e.fallidos.length} fallidos` : ""} · {String(e.iniciado).slice(0, 16).replace("T", " ")}</span>
          </div>
        ))}
        {envios.length === 0 && <p style={{ color: "#64748b", fontSize: "0.7rem" }}>Sin campañas aún.</p>}
      </div>
    </div>
  );
}
