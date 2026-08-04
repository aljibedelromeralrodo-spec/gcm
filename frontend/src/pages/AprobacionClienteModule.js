import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import ImportarCorreo from "../components/ImportarCorreo";
import ConversorUF from "../components/ConversorUF";
import { EmailAutocomplete } from "../components/EmailAutocomplete";

const API = process.env.REACT_APP_BACKEND_URL;

const card = { background: "rgba(15,23,42,0.6)", padding: "1.5rem", borderRadius: "14px", border: "1px solid rgba(255,255,255,0.08)", marginBottom: "1.5rem" };
const inp = { background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: "8px", padding: "0.55rem 0.8rem", color: "#fff", fontSize: "0.9rem", width: "100%" };
const btn = (bg, small) => ({ background: bg, color: bg === "var(--gold)" ? "#0a0e17" : "#fff", border: "none", borderRadius: "8px", padding: small ? "0.4rem 0.8rem" : "0.6rem 1.2rem", fontWeight: 700, cursor: "pointer", fontSize: small ? "0.8rem" : "0.9rem" });
const lbl = { display: "block", fontSize: "0.75rem", opacity: 0.6, marginBottom: "0.3rem", textTransform: "uppercase", letterSpacing: "0.5px" };

const TIPO_LABEL = { simulacion_ajustada: "Simulación ajustada", carta_aprobacion: "Carta de aprobación", otro: "Otro documento" };

export default function AprobacionClienteModule({ onNavigate }) {
  const [q, setQ] = useState("");
  const [resultados, setResultados] = useState([]);
  const [nombre, setNombre] = useState("");
  const [rut, setRut] = useState("");
  const [emailCliente, setEmailCliente] = useState("");
  const [ejecutivoNombre, setEjecutivoNombre] = useState("");
  const [ejecutivoEmail, setEjecutivoEmail] = useState("");
  const [ejecutivoInterno, setEjecutivoInterno] = useState("");
  const [subject, setSubject] = useState("");
  const [intro, setIntro] = useState("");
  const [botonTexto, setBotonTexto] = useState("");
  const [archivos, setArchivos] = useState([]);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");
  const [log, setLog] = useState([]);
  const [plantillaPropia, setPlantillaPropia] = useState(false);
  const [confianza, setConfianza] = useState({});
  const [extraido, setExtraido] = useState({});

  const bordeConf = (campo) => {
    const c = confianza[campo];
    if (c === "alta") return { border: "2px solid #22c55e", boxShadow: "0 0 6px rgba(34,197,94,0.25)" };
    if (c === "dudosa") return { border: "2px solid #f59e0b", boxShadow: "0 0 6px rgba(245,158,11,0.35)" };
    return {};
  };

  const guardarAprender = async () => {
    const pares = [["email", emailCliente], ["rut", rut], ["ejecutivo_nombre", ejecutivoNombre],
      ["ejecutivo_email", ejecutivoEmail], ["ejecutivo_interno", ejecutivoInterno]];
    let n = 0;
    const nuevas = { ...confianza };
    for (const [campo, val] of pares) {
      const orig = (extraido[campo] || "").trim();
      const v = (val || "").trim();
      if (v && v !== orig) {
        try {
          await axios.post(`${API}/api/aprendizaje/correccion`, {
            cliente: nombre, campo, valor_correcto: v, valor_extraido: orig, remitente: extraido.remitente || "",
          });
          nuevas[campo] = "alta"; n++;
        } catch (_e) { /* siguiente */ }
      } else if (v && confianza[campo] === "dudosa") {
        nuevas[campo] = "alta";
      }
    }
    setConfianza(nuevas);
    setExtraido(prev => ({ ...prev, email: emailCliente, rut, ejecutivo_nombre: ejecutivoNombre, ejecutivo_email: ejecutivoEmail, ejecutivo_interno: ejecutivoInterno }));
    setMsg(n > 0
      ? `🧠 ${n} corrección(es) guardada(s) como Patrón Aprendido: la próxima vez no se repetirá el error.`
      : "✅ Datos validados: no había cambios que aprender.");
  };

  const loadPlantilla = useCallback(async (cliente) => {
    const r = await axios.get(`${API}/api/aprobacion-cliente/plantilla`, { params: { cliente: cliente || "" } });
    setSubject(r.data.subject || "");
    setIntro(r.data.intro || "");
    setBotonTexto(r.data.boton_texto || "");
    setPlantillaPropia(!!r.data.plantilla_propia);
  }, []);

  const loadLog = useCallback(async () => {
    const r = await axios.get(`${API}/api/aprobacion-cliente/log`).catch(() => ({ data: { log: [] } }));
    setLog(r.data.log || []);
  }, []);

  useEffect(() => { loadPlantilla(""); loadLog(); }, [loadPlantilla, loadLog]);

  useEffect(() => {
    if (q.trim().length < 2) { setResultados([]); return; }
    const t = setTimeout(async () => {
      try {
        const r = await axios.get(`${API}/api/aprobacion-cliente/buscar-cliente`, { params: { q } });
        setResultados(r.data.resultados || []);
      } catch (_e) { setResultados([]); }
    }, 400);
    return () => clearTimeout(t);
  }, [q]);

  const autofillDatos = async (cliente, emailActual) => {
    try {
      const d = await axios.get(`${API}/api/aprobacion-cliente/datos-cliente`, { params: { nombre: cliente }, timeout: 120000 });
      if (!emailActual && d.data.email) setEmailCliente(prev => prev || d.data.email);
      if (d.data.rut) setRut(prev => prev || d.data.rut);
      if (d.data.ejecutivo_nombre) setEjecutivoNombre(prev => prev || d.data.ejecutivo_nombre);
      if (d.data.ejecutivo_email) setEjecutivoEmail(prev => prev || d.data.ejecutivo_email);
      if (d.data.ejecutivo_interno) setEjecutivoInterno(prev => prev || d.data.ejecutivo_interno);
      setConfianza(d.data.confianza || {});
      setExtraido({ email: d.data.email || "", rut: d.data.rut || "", ejecutivo_nombre: d.data.ejecutivo_nombre || "", ejecutivo_email: d.data.ejecutivo_email || "", ejecutivo_interno: d.data.ejecutivo_interno || "" });
      if (d.data.email && !emailActual) setMsg(`ℹ️ Datos rellenados (fuentes: ${d.data.fuente})${d.data.telefono ? ` · Teléfono: ${d.data.telefono}` : ""} — 🟢 seguro · 🟠 revisar y validar`);
    } catch (_e) { /* el usuario puede escribirlo a mano */ }
  };

  const elegir = async (r) => {
    setNombre(r.nombre); setRut(r.rut || "");
    setEmailCliente(r.email || "");
    setResultados([]); setQ("");
    setLoading(true);
    try {
      const [a] = await Promise.all([
        axios.get(`${API}/api/aprobacion-cliente/archivos`, { params: { cliente: r.nombre } }),
        loadPlantilla(r.nombre),
      ]);
      setArchivos(a.data.archivos || []);
    } catch (_e) { setArchivos([]); }
    setLoading(false);
    autofillDatos(r.nombre, r.email || "");
  };

  useEffect(() => {
    const raw = sessionStorage.getItem("cm_prefill_cliente");
    if (!raw) return;
    sessionStorage.removeItem("cm_prefill_cliente");
    try {
      const p = JSON.parse(raw);
      axios.get(`${API}/api/aprobacion-cliente/buscar-cliente`, { params: { q: p.nombre } })
        .then(r => {
          const res = (r.data.resultados || [])[0];
          elegir(res || { nombre: p.nombre, rut: p.rut || "", email: "" });
        })
        .catch(() => elegir({ nombre: p.nombre, rut: p.rut || "", email: "" }));
    } catch (_e) { /* prefill inválido */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleArchivo = (i) => setArchivos(prev => prev.map((a, j) => j === i ? { ...a, seleccionado: !a.seleccionado } : a));

  const payload = () => ({
    nombre, rut, email_cliente: emailCliente, subject, intro, boton_texto: botonTexto,
    ejecutivo_nombre: ejecutivoNombre, ejecutivo_email: ejecutivoEmail, ejecutivo_interno: ejecutivoInterno,
    adjuntos: archivos.filter(a => a.seleccionado).map(a => ({ origen: a.origen, ruta: a.ruta })),
  });

  const verPreview = async () => {
    setLoading(true); setMsg("");
    try {
      const r = await axios.post(`${API}/api/aprobacion-cliente/enviar`, { ...payload(), confirm: false });
      setPreview(r.data);
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setLoading(false);
  };

  const enviar = async () => {
    if (!window.confirm(`¿Enviar la aprobación con felicitaciones a ${emailCliente}?`)) return;
    setLoading(true); setMsg("");
    try {
      const r = await axios.post(`${API}/api/aprobacion-cliente/enviar`, { ...payload(), confirm: true });
      setMsg(`✅ Enviado a ${r.data.to} desde ${r.data.sender} con ${r.data.attachments.length} adjunto(s). Plantilla del cliente guardada.`);
      setPreview(null); setPlantillaPropia(true);
      loadLog();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setLoading(false);
  };

  const guardarPlantilla = async (comoDefault) => {
    await axios.patch(`${API}/api/aprobacion-cliente/plantilla`, {
      cliente: nombre, subject, intro, boton_texto: botonTexto, como_default: comoDefault,
    });
    if (nombre) setPlantillaPropia(true);
    setMsg(comoDefault ? "✅ Guardado como plantilla por defecto" : `✅ Plantilla guardada para ${nombre || "el cliente"}`);
  };

  const seleccionados = archivos.filter(a => a.seleccionado).length;

  return (
    <div style={{ padding: "1.5rem", color: "var(--white)", maxWidth: "1000px" }} data-testid="aprobacion-module">
      {onNavigate && (
        <button data-testid="aprobacion-volver" onClick={() => onNavigate("clientes")} style={{ marginBottom: "1rem", background: "transparent", border: "1px solid rgba(212,175,55,0.5)", color: "var(--gold)", borderRadius: 8, padding: "0.45rem 1rem", fontWeight: 700, cursor: "pointer" }}>
          <i className="fa fa-arrow-left" /> Volver a Carpeta Clientes
        </button>
      )}
      {msg && <div data-testid="aprobacion-msg" style={{ padding: "0.7rem 1rem", borderRadius: "8px", marginBottom: "1rem", background: msg.startsWith("✅") ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)", color: msg.startsWith("✅") ? "#22c55e" : "#ef4444", fontWeight: 600 }}>{msg}</div>}

      {/* BUSCADOR */}
      <div style={card}>
        <h3 style={{ margin: "0 0 1rem", color: "var(--gold)", fontSize: "1.1rem" }}><i className="fa fa-trophy" style={{ marginRight: "0.5rem" }} />Cliente aprobado (nombre o RUT)</h3>
        <div style={{ position: "relative" }}>
          <input data-testid="aprobacion-buscar" style={inp} placeholder="Buscar cliente… detecta automáticamente su correo" value={q} onChange={e => setQ(e.target.value)} />
          {resultados.length > 0 && (
            <div style={{ position: "absolute", top: "110%", left: 0, right: 0, background: "#1a1f2e", border: "1px solid rgba(255,255,255,0.15)", borderRadius: "8px", zIndex: 20, overflow: "hidden" }}>
              {resultados.map((r, i) => (
                <div key={i} data-testid={`aprobacion-resultado-${i}`} onClick={() => elegir(r)} style={{ padding: "0.6rem 1rem", cursor: "pointer", borderBottom: "1px solid rgba(255,255,255,0.05)" }}
                     onMouseEnter={e => e.currentTarget.style.background = "rgba(212,175,55,0.1)"} onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                  <b>{r.nombre}</b> <span style={{ opacity: 0.6 }}>{r.rut}</span> {r.email && <span style={{ color: "#22c55e", fontSize: "0.8rem" }}> · {r.email}</span>}
                </div>
              ))}
            </div>
          )}
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 2fr", gap: "1rem", marginTop: "1rem" }}>
          <div><label style={lbl}>Nombre del cliente</label><input data-testid="aprobacion-nombre" style={inp} value={nombre} onChange={e => setNombre(e.target.value)} /></div>
          <div><label style={lbl}>RUT</label><input data-testid="aprobacion-rut" style={{ ...inp, ...bordeConf("rut") }} value={rut} onChange={e => setRut(e.target.value)} /></div>
          <div><label style={lbl}>Correo del cliente (auto o manual)</label><EmailAutocomplete dataTestId="aprobacion-email" style={{ ...inp, ...bordeConf("email") }} value={emailCliente} onChange={setEmailCliente} placeholder="cliente@correo.cl" /></div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "2fr 2fr 2fr", gap: "1rem", marginTop: "1rem" }}>
          <div><label style={lbl}>Ejecutivo que envió la solicitud</label><input data-testid="aprobacion-ejecutivo-nombre" style={{ ...inp, ...bordeConf("ejecutivo_nombre") }} value={ejecutivoNombre} onChange={e => setEjecutivoNombre(e.target.value)} placeholder="Nombre del ejecutivo externo" /></div>
          <div><label style={lbl}>Correo del ejecutivo</label><input data-testid="aprobacion-ejecutivo-email" style={{ ...inp, ...bordeConf("ejecutivo_email") }} value={ejecutivoEmail} onChange={e => setEjecutivoEmail(e.target.value)} placeholder="ejecutivo@inmobiliaria.cl" /></div>
          <div><label style={lbl}>Ejecutivo interno (Central Mutuos)</label><input data-testid="aprobacion-ejecutivo-interno" style={{ ...inp, ...bordeConf("ejecutivo_interno") }} value={ejecutivoInterno} onChange={e => setEjecutivoInterno(e.target.value)} placeholder="Nombre del ejecutivo interno" /></div>
        </div>
        {Object.values(confianza).some(Boolean) && (
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: "0.7rem", flexWrap: "wrap" }}>
            <span style={{ fontSize: "0.75rem", opacity: 0.8 }}>🟢 dato seguro (2+ fuentes) · 🟠 revisa y valida antes de enviar</span>
            <button data-testid="aprobacion-guardar-aprender" onClick={guardarAprender}
              style={{ background: "rgba(168,85,247,0.2)", border: "1px solid #a855f7", color: "#d8b4fe", borderRadius: 8, padding: "0.4rem 1rem", cursor: "pointer", fontWeight: 700, fontSize: "0.8rem" }}>
              <i className="fa fa-graduation-cap" style={{ marginRight: 6 }} />Guardar y Aprender
            </button>
          </div>
        )}
        <div style={{ marginTop: "1rem" }}>
          <ConversorUF />
        </div>
        <div style={{ marginTop: "0.8rem" }}>
          <ImportarCorreo destino="carpeta" nombre={nombre}
            label="Importar documentos desde correo"
            onDone={async () => {
              if (!nombre) return;
              try {
                const a = await axios.get(`${API}/api/aprobacion-cliente/archivos`, { params: { cliente: nombre } });
                setArchivos(a.data.archivos || []);
              } catch (_e) { /* noop */ }
            }} />
        </div>
        {plantillaPropia && <div style={{ marginTop: "0.6rem", fontSize: "0.8rem", color: "#22c55e" }}><i className="fa fa-bookmark" style={{ marginRight: "0.35rem" }} />Este cliente tiene plantilla propia guardada</div>}
      </div>

      {/* CONTENIDO DEL CORREO */}
      <div style={card}>
        <h3 style={{ margin: "0 0 1rem", color: "var(--gold)", fontSize: "1.1rem" }}><i className="fa fa-envelope" style={{ marginRight: "0.5rem" }} />Correo de felicitaciones (editable)</h3>
        <label style={lbl}>Asunto</label>
        <input data-testid="aprobacion-subject" style={{ ...inp, marginBottom: "1rem" }} value={subject} onChange={e => setSubject(e.target.value)} />
        <label style={lbl}>Texto comercial</label>
        <textarea data-testid="aprobacion-intro" style={{ ...inp, minHeight: "130px", resize: "vertical", marginBottom: "1rem" }} value={intro} onChange={e => setIntro(e.target.value)} />
        <label style={lbl}>Texto del botón grande</label>
        <input data-testid="aprobacion-boton" style={inp} value={botonTexto} onChange={e => setBotonTexto(e.target.value)} />
      </div>

      {/* ADJUNTOS DETECTADOS */}
      <div style={card}>
        <h3 style={{ margin: "0 0 0.4rem", color: "var(--gold)", fontSize: "1.1rem" }}><i className="fa fa-paperclip" style={{ marginRight: "0.5rem" }} />PDFs del cliente ({seleccionados} seleccionados)</h3>
        <p style={{ fontSize: "0.8rem", opacity: 0.6, margin: "0 0 0.8rem" }}>Al cliente se envían <b>SOLO 2 archivos</b>: la carta de aprobación y la simulación (los mismos del autocorreo). El cliente no verá la palabra "ajustada". Usa "Ver PDF" para confirmar cada archivo antes de enviar.</p>
        {archivos.length === 0 ? (
          <div style={{ opacity: 0.5, fontSize: "0.9rem", padding: "0.5rem 0" }} data-testid="aprobacion-sin-archivos">Seleccioná un cliente para ver su carta de aprobación y simulación.</div>
        ) : archivos.map((a, i) => (
          <label key={i} data-testid={`aprobacion-archivo-${i}`} style={{ display: "flex", alignItems: "center", gap: "0.7rem", padding: "0.45rem 0.4rem", borderBottom: "1px solid rgba(255,255,255,0.05)", cursor: "pointer" }}>
            <input type="checkbox" checked={!!a.seleccionado} onChange={() => toggleArchivo(i)} />
            <span style={{ flex: 1, fontSize: "0.88rem" }}>
              {a.nombre_cliente || a.nombre}
              {a.nombre_cliente && a.nombre_cliente !== a.nombre && (
                <span style={{ display: "block", fontSize: "0.7rem", opacity: 0.45 }}>archivo interno: {a.nombre}</span>
              )}
            </span>
            <a data-testid={`aprobacion-ver-pdf-${i}`} href={`${API}/api/aprobacion-cliente/preview-pdf?ruta=${encodeURIComponent(a.ruta)}&origen=${a.origen}&cliente=${encodeURIComponent(nombre)}`}
              target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()}
              style={{ fontSize: "0.75rem", color: "#3b82f6", fontWeight: 700, textDecoration: "none", border: "1px solid #3b82f6", borderRadius: 6, padding: "0.15rem 0.55rem" }}>
              <i className="fa fa-eye" style={{ marginRight: "0.3rem" }} />Ver PDF
            </a>
            <span style={{ fontSize: "0.72rem", padding: "0.12rem 0.5rem", borderRadius: "999px", background: a.tipo === "carta_aprobacion" ? "rgba(34,197,94,0.15)" : a.tipo === "simulacion_ajustada" ? "rgba(212,175,55,0.15)" : "rgba(255,255,255,0.08)", color: a.tipo === "carta_aprobacion" ? "#22c55e" : a.tipo === "simulacion_ajustada" ? "var(--gold)" : "#9aa3b5" }}>{a.tipo === "simulacion_ajustada" ? "Simulación" : TIPO_LABEL[a.tipo]}</span>
            <span style={{ fontSize: "0.72rem", opacity: 0.45 }}>{a.origen === "autocorreo" ? "Archivo Autocorreo" : "Carpeta Cliente"}</span>
          </label>
        ))}
      </div>

      {/* ACCIONES */}
      <div style={{ display: "flex", gap: "0.8rem", flexWrap: "wrap", marginBottom: "1.5rem" }}>
        <button data-testid="aprobacion-preview-btn" onClick={verPreview} disabled={loading} style={btn("#3b82f6")}><i className="fa fa-eye" style={{ marginRight: "0.4rem" }} />Vista previa</button>
        <button data-testid="aprobacion-enviar-btn" onClick={enviar} disabled={loading || !emailCliente} style={btn("var(--gold)")}><i className="fa fa-paper-plane" style={{ marginRight: "0.4rem" }} />Enviar al cliente</button>
        <button data-testid="aprobacion-guardar-cliente" onClick={() => guardarPlantilla(false)} disabled={loading || !nombre} style={btn("rgba(255,255,255,0.12)")}><i className="fa fa-bookmark" style={{ marginRight: "0.4rem" }} />Guardar plantilla del cliente</button>
        <button data-testid="aprobacion-guardar-default" onClick={() => guardarPlantilla(true)} disabled={loading} style={btn("rgba(255,255,255,0.12)")}><i className="fa fa-save" style={{ marginRight: "0.4rem" }} />Usar como plantilla por defecto</button>
      </div>

      {/* HISTORIAL */}
      {log.length > 0 && (
        <div style={card} data-testid="aprobacion-log">
          <h3 style={{ margin: "0 0 0.8rem", color: "var(--gold)", fontSize: "1rem" }}><i className="fa fa-history" style={{ marginRight: "0.5rem" }} />Últimos envíos</h3>
          {log.map((l, i) => (
            <div key={i} style={{ fontSize: "0.85rem", opacity: 0.85, padding: "0.3rem 0", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
              {String(l.enviado_en || "").slice(0, 16).replace("T", " ")} — <b>{l.nombre}</b> → {l.to} · {(l.adjuntos || []).length} adjunto(s)
            </div>
          ))}
        </div>
      )}

      {/* MODAL PREVIEW */}
      {preview && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center", padding: "2rem" }} onClick={() => setPreview(null)}>
          <div style={{ background: "#fff", borderRadius: "12px", maxWidth: "720px", width: "100%", maxHeight: "88vh", overflow: "auto" }} onClick={e => e.stopPropagation()} data-testid="aprobacion-preview-modal">
            <div style={{ padding: "0.8rem 1.2rem", background: "#1a1f2e", display: "flex", justifyContent: "space-between", alignItems: "center", position: "sticky", top: 0, zIndex: 5 }}>
              <span style={{ color: "var(--gold)", fontWeight: 700 }}>Vista previa — {preview.subject}</span>
              <div>
                <button data-testid="aprobacion-preview-enviar" onClick={enviar} disabled={loading || !emailCliente} style={{ ...btn("var(--gold)", true), marginRight: "0.6rem" }}>Enviar</button>
                <button onClick={() => setPreview(null)} style={btn("rgba(255,255,255,0.15)", true)}>Cerrar</button>
              </div>
            </div>
            {preview.attachments?.length > 0 && (
              <div style={{ padding: "0.5rem 1.2rem", background: "#f8f9fc", fontSize: "0.8rem", color: "#1a1f2e" }}>
                <b>Adjuntos:</b> {preview.attachments.join(" · ")}
              </div>
            )}
            <div dangerouslySetInnerHTML={{ __html: preview.body }} />
          </div>
        </div>
      )}
    </div>
  );
}
