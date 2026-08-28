import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import ImportarCorreo from "../components/ImportarCorreo";
import { estiloConfianza, PanelAprendizaje, useAprendizaje } from "../components/CampoAprendizaje";
import { secureGet } from "../utils/secureStore";
import { marcarRegreso } from "../utils/navegacion";
import { marcarRegreso } from "../utils/navegacion";

const API = process.env.REACT_APP_BACKEND_URL;
const tkParam = () => `&t=${encodeURIComponent(secureGet("token", false) || "")}`;

const card = { background: "rgba(14,14,16,0.9)", padding: "1.5rem", borderRadius: "0px", border: "1px solid transparent", backgroundImage: "linear-gradient(115deg, rgba(255,255,255,0.09) 0%, rgba(255,255,255,0.02) 18%, transparent 32%), linear-gradient(160deg, rgba(30,30,30,0.95), rgba(10,10,10,0.98)), linear-gradient(135deg, #BF953F, #FCF6BA, #B38728, #FBF5B7, #AA771C)", boxShadow: "0 35px 70px -20px rgba(0,0,0,0.95), 0 0 38px -16px rgba(191,149,63,0.45)", backgroundOrigin: "border-box", backgroundClip: "padding-box, padding-box, border-box", marginBottom: "1.5rem" };
const inp = { background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: "0px", padding: "0.55rem 0.8rem", color: "#fff", fontSize: "0.9rem", width: "100%" };
const btn = (bg, small) => ({ background: bg, color: bg === "var(--gold)" ? "#0a0e17" : "#fff", border: "none", borderRadius: "0px", padding: small ? "0.4rem 0.8rem" : "0.6rem 1.2rem", fontWeight: 700, cursor: "pointer", fontSize: small ? "0.8rem" : "0.9rem" });
const lbl = { display: "block", fontSize: "0.75rem", opacity: 0.6, marginBottom: "0.3rem", textTransform: "uppercase", letterSpacing: "0.5px" };

export default function SetCreditoModule({ onNavigate }) {
  const [sets, setSets] = useState([]);
  const [docTipos, setDocTipos] = useState({});
  const [current, setCurrent] = useState(null);
  const [migrup, setMigrup] = useState(null);
  const [nuevo, setNuevo] = useState({ nombre: "", rut: "", email: "" });
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");
  const [firmaModal, setFirmaModal] = useState(null);
  const [previewCombinado, setPreviewCombinado] = useState(null);
  const [contactoModal, setContactoModal] = useState(null);
  const [ocrLoading, setOcrLoading] = useState(false);
  const [correosEnvio, setCorreosEnvio] = useState("danielagalindo@centralmutuos.cl, victoriavilches@centralmutuos.cl");
  const fileRef = useRef();
  const cedulaRef = useRef();
  const [tipoUpload, setTipoUpload] = useState("solicitud_credito");
  const { confianza, autofill, guardarAprender } = useAprendizaje();

  const autofillNuevo = async (nombreParam) => {
    const n = (nombreParam || nuevo.nombre || "").trim();
    if (n.length < 3) return;
    try {
      const d = await autofill(n);
      setNuevo(prev => ({ ...prev, rut: prev.rut || d.rut || "", email: prev.email || d.email || "" }));
    } catch (_e) { /* el usuario puede escribirlo a mano */ }
  };

  const aprenderNuevo = async () => {
    const n = await guardarAprender(nuevo.nombre, [["email", nuevo.email], ["rut", nuevo.rut]]);
    setMsg(n > 0
      ? `🧠 ${n} corrección(es) guardada(s) como Patrón Aprendido: la próxima vez no se repetirá el error.`
      : "✅ Datos validados: no había cambios que aprender.");
  };

  const loadSets = useCallback(async () => {
    const r = await axios.get(`${API}/api/set-credito/sets`);
    setSets(r.data.sets || []);
    setDocTipos(r.data.doc_tipos || {});
  }, []);

  const loadMigrup = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/migrup/status`, { timeout: 40000 });
      setMigrup(r.data);
    } catch (_e) { setMigrup({ configured: true, connected: false }); }
  }, []);

  useEffect(() => { loadSets(); loadMigrup(); }, [loadSets, loadMigrup]);

  useEffect(() => {
    const raw = sessionStorage.getItem("cm_prefill_cliente");
    if (!raw) return;
    sessionStorage.removeItem("cm_prefill_cliente");
    try {
      const p = JSON.parse(raw);
      (async () => {
        const r = await axios.get(`${API}/api/set-credito/sets`);
        const lista = r.data.sets || [];
        const norm = (s) => (s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim();
        const ex = lista.find(s => norm(s.nombre) === norm(p.nombre));
        if (ex) {
          const d = await axios.get(`${API}/api/set-credito/sets/${ex.id}`);
          setCurrent(d.data);
        } else {
          setNuevo({ nombre: p.nombre, rut: p.rut || "", email: "" });
          setMsg(`✅ Cliente "${p.nombre}" precargado desde su carpeta — crea su set de crédito`);
          autofillNuevo(p.nombre);
        }
      })();
    } catch (_e) { /* prefill inválido */ }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps -- intencional: prefill solo al montar

  const crearSet = async () => {
    if (!nuevo.nombre.trim()) return setMsg("Falta el nombre del cliente");
    setLoading(true);
    try {
      await axios.post(`${API}/api/set-credito/sets`, nuevo);
      setNuevo({ nombre: "", rut: "", email: "" });
      setMsg("✅ Set de crédito creado");
      await loadSets();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setLoading(false);
  };

  const abrir = async (id) => {
    const r = await axios.get(`${API}/api/set-credito/sets/${id}`);
    setCurrent(r.data);
  };

  const eliminarSet = async (id) => {
    if (!window.confirm("¿Eliminar este set de crédito y sus documentos?")) return;
    await axios.delete(`${API}/api/set-credito/sets/${id}`);
    setCurrent(null); loadSets();
  };

  const subir = async (e) => {
    const file = e.target.files[0];
    if (!file || !current) return;
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("tipo", tipoUpload);
      await axios.post(`${API}/api/set-credito/sets/${current.id}/upload`, fd);
      setMsg(`✅ Documento subido (${docTipos[tipoUpload] || tipoUpload})`);
      await abrir(current.id);
    } catch (err) { setMsg("Error subiendo documento"); }
    setLoading(false);
    if (fileRef.current) fileRef.current.value = "";
  };

  const borrarFile = async (ruta) => {
    if (!window.confirm("¿Eliminar este documento?")) return;
    await axios.post(`${API}/api/set-credito/sets/${current.id}/delete-file`, { file_path: ruta });
    await abrir(current.id);
  };

  const abrirFirma = (archivo) => setFirmaModal({
    file_path: archivo.ruta, doc_nombre: archivo.nombre, completo: false,
    nombres: current.nombre, aPaterno: "", aMaterno: "",
    rut: current.rut || "", email: current.email || "", comentario: "",
  });

  const previsualizarCombinado = async () => {
    if (!current) return;
    setLoading(true); setMsg("");
    try {
      const r = await axios.post(`${API}/api/set-credito/sets/${current.id}/combinar`, {}, { timeout: 120000 });
      setPreviewCombinado({
        nombre: r.data.combinado,
        usados: r.data.usados || [],
        excluidos: r.data.excluidos_rut || [],
        url: `${API}/api/set-credito/sets/${current.id}/download/${encodeURIComponent(r.data.combinado)}?inline=true${tkParam()}`,
      });
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setLoading(false);
  };

  const abrirFirmaCompleta = () => setFirmaModal({
    completo: true, doc_nombre: `Set completo de ${current.nombre} (todas las hojas)`,
    nombres: current.nombre, aPaterno: "", aMaterno: "",
    rut: current.rut || "", email: current.email || "", comentario: "",
  });

  const enviarFirma = async () => {
    const destino = firmaModal.completo
      ? `TODO el set (todas las hojas) a ${firmaModal.email}`
      : `"${firmaModal.doc_nombre}" a ${firmaModal.email}`;
    if (!window.confirm(`¿Enviar ${destino}? Se firmará con tu certificado y el cliente recibirá el correo de eCert para firmar todo de una vez.`)) return;
    setLoading(true);
    try {
      const url = firmaModal.completo
        ? `${API}/api/set-credito/sets/${current.id}/enviar-firma-completo`
        : `${API}/api/set-credito/sets/${current.id}/enviar-firma`;
      const r = await axios.post(url, firmaModal, { timeout: 90000 });
      setMsg(firmaModal.completo
        ? `✅ Set completo enviado a firmar a ${firmaModal.email} (${r.data.paginas} hojas, firma en ${r.data.estampas || 1} lugares, solo 1 firma del plan consumida)`
        : `✅ Documento enviado a firmar a ${firmaModal.email} (firma en ${r.data.estampas || 1} lugar(es))`);
      setFirmaModal(null);
      await abrir(current.id);
      loadMigrup();
    } catch (e) { setMsg("Error al enviar a firmar: " + (e.response?.data?.detail || e.message)); }
    setLoading(false);
  };

  const abrirContacto = () => {
    const base = { nombres: "", aPaterno: "", aMaterno: "", rut: "", email: "", email2: "" };
    if (current) {
      const partes = (current.nombre || "").trim().split(/\s+/);
      base.nombres = partes.slice(0, Math.max(1, partes.length - 2)).join(" ");
      base.aPaterno = partes.length >= 3 ? partes[partes.length - 2] : (partes[1] || "");
      base.aMaterno = partes.length >= 3 ? partes[partes.length - 1] : "";
      base.rut = current.rut || "";
      base.email = current.email || "";
      base.email2 = current.email || "";
    }
    setContactoModal(base);
  };

  const ocrCedula = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setOcrLoading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await axios.post(`${API}/api/migrup/ocr-cedula`, fd, { timeout: 120000 });
      setContactoModal(c => ({
        ...c,
        nombres: r.data.nombres || c.nombres,
        aPaterno: r.data.aPaterno || c.aPaterno,
        aMaterno: r.data.aMaterno || c.aMaterno,
        rut: r.data.rut || c.rut,
      }));
      setMsg("✅ Datos capturados desde la cédula. Revisá y completá el correo.");
    } catch (err) { setMsg("Error leyendo la cédula: " + (err.response?.data?.detail || err.message)); }
    setOcrLoading(false);
    if (cedulaRef.current) cedulaRef.current.value = "";
  };

  const crearContacto = async () => {
    setLoading(true);
    try {
      const r = await axios.post(`${API}/api/migrup/contactos`, contactoModal, { timeout: 60000 });
      setMsg(`✅ ${r.data.mensaje}`);
      setContactoModal(null);
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setLoading(false);
  };

  const traerFirmado = async () => {
    setLoading(true);
    try {
      const r = await axios.post(`${API}/api/set-credito/sets/${current.id}/traer-firmado`, {}, { timeout: 120000 });
      setMsg(`✅ Set firmado descargado desde eCert y separado en ${r.data.total} archivos`);
      await abrir(current.id);
    } catch (e) { setMsg("⚠️ " + (e.response?.data?.detail || e.message)); }
    setLoading(false);
  };

  const enviarFirmados = async () => {
    setLoading(true);
    try {
      const r = await axios.post(`${API}/api/set-credito/sets/${current.id}/enviar-firmados`,
        { correos: correosEnvio }, { timeout: 120000 });
      setMsg(`✅ Set firmado (${r.data.archivos} archivos) enviado a: ${r.data.enviados.join(", ")}`);
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setLoading(false);
  };

  return (
    <div style={{ padding: "1.5rem", color: "var(--white)", maxWidth: "1050px" }} data-testid="setcredito-module">
      {onNavigate && (
        <button data-testid="setcred-volver" onClick={() => { marcarRegreso("clientes"); onNavigate("clientes"); }} style={{ marginBottom: "1rem", background: "transparent", border: "1px solid rgba(212,175,55,0.5)", color: "var(--gold)", borderRadius: 0, padding: "0.45rem 1rem", fontWeight: 700, cursor: "pointer" }}>
          <i className="fa fa-arrow-left" /> Volver a Carpeta Clientes
        </button>
      )}
      {msg && <div data-testid="setcred-msg" style={{ padding: "0.7rem 1rem", borderRadius: "0px", marginBottom: "1rem", background: msg.startsWith("✅") ? "rgba(16,217,142,0.15)" : "rgba(225,29,72,0.15)", color: msg.startsWith("✅") ? "#10d98e" : "#e11d48", fontWeight: 600 }}>{msg}</div>}

      {/* Estado migrup */}
      <div data-testid="migrup-status" style={{ ...card, display: "flex", alignItems: "center", gap: "1rem", flexWrap: "wrap", marginBottom: "1rem", padding: "0.9rem 1.3rem" }}>
        <i className="fa fa-pencil-square-o" style={{ color: "var(--gold)", fontSize: "1.3rem" }} />
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700 }}>Firma electrónica migrup / eCert{migrup?.user ? ` — ${migrup.user.alias || `${migrup.user.nombres} ${migrup.user.apellido}`}` : ""}</div>
          <div style={{ fontSize: "0.82rem", opacity: 0.7 }}>
            {migrup?.connected
              ? `Conectado · ${migrup.firmas_terceros_disponibles ?? "—"} firmas de terceros disponibles`
              : migrup?.configured ? "No se pudo conectar (revisar credenciales)" : "No configurado"}
          </div>
        </div>
        <button data-testid="setcred-nuevo-contacto" onClick={abrirContacto} disabled={!migrup?.connected} style={btn("#d4af37", true)}><i className="fa fa-user-plus" style={{ marginRight: "0.4rem" }} />Nuevo contacto eCert</button>
        <span style={{ padding: "0.2rem 0.7rem", borderRadius: "999px", fontSize: "0.8rem", fontWeight: 700, background: migrup?.connected ? "rgba(16,217,142,0.15)" : "rgba(225,29,72,0.15)", color: migrup?.connected ? "#10d98e" : "#e11d48" }}>
          {migrup?.connected ? "● Conectado" : "○ Desconectado"}
        </span>
      </div>

      {!current ? (
        <>
          {/* Crear set */}
          <div style={card}>
            <h3 style={{ margin: "0 0 1rem", color: "var(--gold)", fontSize: "1.1rem" }}><i className="fa fa-folder-plus" style={{ marginRight: "0.5rem" }} />Nuevo Set de Crédito</h3>
            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 2fr auto", gap: "1rem", alignItems: "end" }}>
              <div><label style={lbl}>Nombre del cliente</label><input data-testid="setcred-nombre" style={inp} value={nuevo.nombre} onChange={e => setNuevo({ ...nuevo, nombre: e.target.value })} onBlur={() => autofillNuevo()} /></div>
              <div><label style={lbl}>RUT</label><input data-testid="setcred-rut" style={{ ...inp, ...estiloConfianza(confianza, "rut") }} value={nuevo.rut} onChange={e => setNuevo({ ...nuevo, rut: e.target.value })} /></div>
              <div><label style={lbl}>Correo (para firmar)</label><input data-testid="setcred-email" style={{ ...inp, ...estiloConfianza(confianza, "email") }} value={nuevo.email} onChange={e => setNuevo({ ...nuevo, email: e.target.value })} placeholder="cliente@correo.cl" /></div>
              <button data-testid="setcred-crear" onClick={crearSet} disabled={loading} style={btn("var(--gold)")}>Crear</button>
            </div>
            <PanelAprendizaje confianza={confianza} onGuardar={aprenderNuevo} testId="setcred-guardar-aprender" />
          </div>

          {/* Lista de sets */}
          <div style={card}>
            <h3 style={{ margin: "0 0 1rem", color: "var(--gold)", fontSize: "1.1rem" }}><i className="fa fa-list" style={{ marginRight: "0.5rem" }} />Sets de Crédito ({sets.length})</h3>
            {sets.length === 0 ? <div style={{ opacity: 0.5 }}>Aún no hay sets. Creá el primero arriba.</div> : sets.map(s => (
              <div key={s.id} data-testid={`setcred-item-${s.id}`} onClick={() => abrir(s.id)} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.7rem 0.4rem", borderBottom: "1px solid rgba(255,255,255,0.05)", cursor: "pointer" }}>
                <div><b>{s.nombre}</b> <span style={{ opacity: 0.6, fontSize: "0.85rem" }}>{s.rut} · {s.email || "sin correo"}</span></div>
                <span style={{ fontSize: "0.82rem", opacity: 0.7 }}>{s.total_archivos} doc(s) <i className="fa fa-chevron-right" style={{ marginLeft: "0.5rem" }} /></span>
              </div>
            ))}
          </div>
        </>
      ) : (
        /* Detalle */
        <div style={card}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <div>
              <button data-testid="setcred-volver" onClick={() => setCurrent(null)} style={{ ...btn("rgba(255,255,255,0.1)", true), marginRight: "0.8rem" }}><i className="fa fa-arrow-left" /> Volver</button>
              <b style={{ fontSize: "1.15rem", color: "var(--gold)" }}>{current.nombre}</b> <span style={{ opacity: 0.6 }}>{current.rut} · {current.email || "sin correo"}</span>
              {current.num_documento && (
                <span data-testid="setcred-num-doc" style={{ marginLeft: 10, fontSize: "0.75rem", fontWeight: 800, padding: "0.25rem 0.6rem", background: "rgba(16,217,142,0.12)", border: "1px solid rgba(16,217,142,0.4)", color: "#10d98e" }}>
                  🪪 Nº Documento: {current.num_documento}
                </span>
              )}
            </div>
            <button data-testid="setcred-eliminar" onClick={() => eliminarSet(current.id)} style={btn("#e11d48", true)}><i className="fa fa-trash" /> Eliminar set</button>
            <button data-testid="setcred-link-vip" onClick={async () => {
              if (!(current.archivos || []).length) {
                setMsg("⚠ REGLA DEL SET: la Firma VIP exige archivos PDF dentro del Set de Crédito. Este set está en 0 — suba o sincronice los documentos primero.");
                return;
              }
              try {
                const r = await axios.post(`${API}/api/firma/generar-link`, { cliente: current.nombre, rut: current.rut || "", email: current.email || "" });
                try { await navigator.clipboard.writeText(r.data.url); } catch (_e) { /* clipboard opcional */ }
                setMsg(`✨ Portal de Firma VIP listo y copiado al portapapeles: ${r.data.url}`);
                window.open(r.data.whatsapp, "_blank");
              } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
            }} style={{ ...btn("#14213D"), marginLeft: "0.6rem", border: "1px solid #E8C567", color: "#E8C567" }} title="Genera el link de lujo con tarjeta VIP para WhatsApp">
              <i className="fa fa-diamond" style={{ marginRight: "0.4rem" }} />Link de Firma VIP (WhatsApp)
            </button>
            <button data-testid="setcred-simulador-vip" onClick={async () => {
              try {
                const r = await axios.get(`${API}/api/martin/link`);
                try { await navigator.clipboard.writeText(r.data.url); } catch (_e) { /* clipboard opcional */ }
                setMsg(`✦ Link del Simulador Inmobiliario VIP copiado: ${r.data.url}`);
                const texto = `Hola ${current.nombre.split(" ")[0]} 👋, soy Martín de Central Mutuos. Simula tu crédito hipotecario en 1 minuto con mi asesor VIP: ${r.data.url}`;
                window.open(`https://wa.me/?text=${encodeURIComponent(texto)}`, "_blank");
              } catch (e) { console.error(e); setMsg("Error: " + (e.response?.data?.detail || e.message)); }
            }} style={{ ...btn("transparent"), marginLeft: "0.6rem", border: "1px solid transparent", color: "#0a0a0a", fontWeight: 800,
              backgroundImage: "linear-gradient(135deg, #BF953F, #FCF6BA 45%, #B38728, #FBF5B7 80%, #AA771C), linear-gradient(135deg, #BF953F, #FCF6BA, #B38728, #FBF5B7, #AA771C)",
              backgroundOrigin: "border-box", backgroundClip: "padding-box, border-box",
              boxShadow: "0 0 22px -6px rgba(191,149,63,0.6)" }} title="Envía el Simulador Inmobiliario Martín por WhatsApp">
              <i className="fa fa-diamond" style={{ marginRight: "0.4rem" }} />Generar Link VIP (WhatsApp)
            </button>
          </div>

          {/* Subir documento */}
          <div style={{ display: "flex", gap: "0.8rem", alignItems: "center", flexWrap: "wrap", marginBottom: "1rem", padding: "0.8rem", background: "rgba(255,255,255,0.03)", borderRadius: "0px" }}>
            <span style={{ fontSize: "0.85rem", opacity: 0.7 }}>Tipo:</span>
            <select data-testid="setcred-tipo" value={tipoUpload} onChange={e => setTipoUpload(e.target.value)} style={{ ...inp, width: "auto" }}>
              {Object.entries(docTipos).map(([k, v]) => <option key={k} value={k} style={{ background: "rgba(14,14,16,0.9)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)" }}>{v}</option>)}
            </select>
            <input ref={fileRef} data-testid="setcred-upload-input" type="file" accept="application/pdf,image/*" onChange={subir} style={{ display: "none" }} />
            <button data-testid="setcred-upload-btn" onClick={() => fileRef.current?.click()} disabled={loading} style={btn("#d4af37", true)}><i className="fa fa-upload" style={{ marginRight: "0.4rem" }} />Subir documento</button>
            <ImportarCorreo destino="set_credito" destinoId={current.id} nombre={current.nombre}
              label="Importar desde correo" onDone={() => abrir(current.id)} />
          </div>

          {/* Documentos */}
          {current.archivos.length > 0 && (
            <div data-testid="setcred-firmar-todo-bar" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.8rem", flexWrap: "wrap", padding: "0.9rem 1rem", background: "rgba(212,175,55,0.1)", border: "1px solid rgba(212,175,55,0.35)", borderRadius: "0px", marginBottom: "1rem" }}>
              <div style={{ fontSize: "0.88rem" }}>
                <b style={{ color: "var(--gold)" }}>Firmar todo de una vez</b> — combina los {current.archivos.filter(a => !a.nombre.startsWith("COMBINADO_SET")).length} documentos en un solo PDF. La firma eCert va en la primera etiqueta "Firma cliente" y en las demás queda la marca de Firma Electrónica Avanzada. <span style={{ opacity: 0.7 }}>(consume solo 1 firma de terceros)</span>
              </div>
              <button data-testid="setcred-preview-combinado" onClick={previsualizarCombinado} disabled={loading}
                style={{ ...btn("transparent"), border: "1px solid rgba(212,175,55,0.6)", color: "#d4af37", fontWeight: 800 }}>
                <i className="fa fa-search" style={{ marginRight: "0.4rem" }} />🔍 Previsualizar Combinado
              </button>
              <button data-testid="setcred-firmar-todo" onClick={abrirFirmaCompleta} disabled={!migrup?.connected || loading} style={btn("var(--gold)")}><i className="fa fa-check-square-o" style={{ marginRight: "0.4rem" }} />Combinar y enviar a firmar todo</button>
            </div>
          )}
          {current.archivos.filter(a => !a.nombre.startsWith("COMBINADO_SET")).length === 0 ? <div style={{ opacity: 0.5 }}>Sin documentos. Subí los del set (seguros, solicitud de crédito, declaración de salud).</div> :
            current.archivos.filter(a => !a.nombre.startsWith("COMBINADO_SET")).map((a, i) => (
              <div key={i} data-testid={`setcred-file-${i}`} style={{ display: "flex", alignItems: "center", gap: "0.7rem", padding: "0.55rem 0.4rem", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                <i className="fa fa-file-pdf-o" style={{ color: "#e11d48" }} />
                <span style={{ flex: 1 }}>{a.nombre}</span>
                <span style={{ fontSize: "0.72rem", padding: "0.12rem 0.5rem", borderRadius: "999px", background: "rgba(212,175,55,0.15)", color: "var(--gold)" }}>{docTipos[a.tipo] || "Otro"}</span>
                <a href={`${API}/api/set-credito/sets/${current.id}/download/${encodeURIComponent(a.ruta)}?inline=true${tkParam()}`} target="_blank" rel="noreferrer" style={{ color: "#d4af37" }} title="Ver"><i className="fa fa-eye" /></a>
                <button data-testid={`setcred-firmar-${i}`} onClick={() => abrirFirma(a)} disabled={!migrup?.connected} style={btn("var(--gold)", true)} title="Enviar a firmar"><i className="fa fa-pencil" style={{ marginRight: "0.3rem" }} />Firmar</button>
                <button onClick={() => borrarFile(a.ruta)} style={{ background: "none", border: "none", color: "#e11d48", cursor: "pointer" }}><i className="fa fa-trash" /></button>
              </div>
            ))}

          {(current.firmas || []).length > 0 && (
            <div style={{ marginTop: "1.2rem" }}>
              <h4 style={{ color: "var(--gold)", fontSize: "0.95rem" }}>Enviados a firmar</h4>
              {current.firmas.map((f, i) => (
                <div key={i} style={{ fontSize: "0.83rem", opacity: 0.8, padding: "0.25rem 0" }}>
                  {String(f.enviado_en).slice(0, 16).replace("T", " ")} — {f.documento} → {f.firmante}
                </div>
              ))}
            </div>
          )}

          {/* Set firmado: traer desde eCert, separar y enviar por correo */}
          <div data-testid="setcred-firmados-section" style={{ marginTop: "1.4rem", padding: "1rem", background: "rgba(16,217,142,0.07)", border: "1px solid rgba(16,217,142,0.3)", borderRadius: "0px" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.8rem", flexWrap: "wrap" }}>
              <h4 style={{ color: "#10d98e", fontSize: "0.95rem", margin: 0 }}><i className="fa fa-check-circle" style={{ marginRight: "0.4rem" }} />Set firmado por el cliente</h4>
              <button data-testid="setcred-traer-firmado" onClick={traerFirmado} disabled={loading || !migrup?.connected} style={btn("#10d98e", true)}>
                <i className="fa fa-cloud-download" style={{ marginRight: "0.4rem" }} />Traer firmado desde eCert y separar
              </button>
            </div>
            {(current.firmados || []).length === 0 ? (
              <div style={{ fontSize: "0.8rem", opacity: 0.6, marginTop: "0.5rem" }}>Cuando el cliente firme, trae el PDF firmado: se separa automáticamente archivo por archivo (cobranza, cesantía, origen de fondos, etc.).</div>
            ) : (
              <>
                {(current.firmados || []).map((f, i) => (
                  <div key={i} data-testid={`setcred-firmado-${i}`} style={{ display: "flex", alignItems: "center", gap: "0.7rem", padding: "0.4rem 0.2rem", borderBottom: "1px solid rgba(255,255,255,0.05)", fontSize: "0.85rem" }}>
                    <i className="fa fa-file-pdf-o" style={{ color: "#10d98e" }} />
                    <span style={{ flex: 1 }}>{f.nombre}</span>
                    <a href={`${API}/api/set-credito/sets/${current.id}/download/${encodeURIComponent(f.ruta)}?inline=true${tkParam()}`} target="_blank" rel="noreferrer" style={{ color: "#d4af37" }} title="Ver"><i className="fa fa-eye" /></a>
                  </div>
                ))}
                <div style={{ display: "flex", gap: "0.6rem", marginTop: "0.9rem", flexWrap: "wrap", alignItems: "center" }}>
                  <input data-testid="setcred-correos-envio" value={correosEnvio} onChange={e => setCorreosEnvio(e.target.value)}
                         placeholder="correo1@..., correo2@..." style={{ ...inp, flex: 1, minWidth: "280px" }} />
                  <button data-testid="setcred-enviar-firmados" onClick={enviarFirmados} disabled={loading} style={btn("#10d98e")}>
                    <i className="fa fa-paper-plane" style={{ marginRight: "0.4rem" }} />Enviar set firmado por correo
                  </button>
                </div>
                <div style={{ fontSize: "0.72rem", opacity: 0.55, marginTop: "0.3rem" }}>Se envía separado archivo por archivo. Puedes cambiar los destinatarios (separados por coma).</div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Modal nuevo contacto eCert */}
      {contactoModal && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center", padding: "2rem" }} onClick={() => setContactoModal(null)}>
          <div style={{ background: "rgba(14,14,16,0.9)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", borderRadius: "0px", maxWidth: "500px", width: "100%", padding: "1.5rem", border: "1px solid rgba(255,255,255,0.15)" }} onClick={e => e.stopPropagation()} data-testid="setcred-contacto-modal">
            <h3 style={{ margin: "0 0 0.3rem", color: "var(--gold)" }}>Añade un nuevo contacto para firmar</h3>
            <p style={{ fontSize: "0.83rem", opacity: 0.7, margin: "0 0 1rem" }}>El contacto se crea en eCert Chile (migrup). Podés capturar los datos con el lector de cédula o llenarlos a mano.</p>
            <div style={{ display: "flex", gap: "0.6rem", marginBottom: "1rem", flexWrap: "wrap" }}>
              <input ref={cedulaRef} type="file" accept="application/pdf,image/*" onChange={ocrCedula} style={{ display: "none" }} data-testid="contacto-cedula-input" />
              <button data-testid="contacto-ocr-btn" onClick={() => cedulaRef.current?.click()} disabled={ocrLoading} style={btn("#2e5ce6", true)}>
                <i className={`fa ${ocrLoading ? "fa-spinner fa-spin" : "fa-id-card-o"}`} style={{ marginRight: "0.4rem" }} />{ocrLoading ? "Leyendo cédula..." : "Capturar desde cédula (OCR)"}
              </button>
            </div>
            <div style={{ display: "grid", gap: "0.8rem" }}>
              <div><label style={lbl}>Nombres *</label><input data-testid="contacto-nombres" style={inp} value={contactoModal.nombres} onChange={e => setContactoModal({ ...contactoModal, nombres: e.target.value })} placeholder="Por favor ingrese nombre(s)" /></div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.8rem" }}>
                <div><label style={lbl}>Apellido Paterno *</label><input data-testid="contacto-apaterno" style={inp} value={contactoModal.aPaterno} onChange={e => setContactoModal({ ...contactoModal, aPaterno: e.target.value })} /></div>
                <div><label style={lbl}>Apellido Materno</label><input data-testid="contacto-amaterno" style={inp} value={contactoModal.aMaterno} onChange={e => setContactoModal({ ...contactoModal, aMaterno: e.target.value })} /></div>
              </div>
              <div><label style={lbl}>RUN *</label><input data-testid="contacto-rut" style={inp} value={contactoModal.rut} onChange={e => setContactoModal({ ...contactoModal, rut: e.target.value })} placeholder="12.345.678-9" /></div>
              <div><label style={lbl}>Correo electrónico *</label><input data-testid="contacto-email" style={inp} value={contactoModal.email} onChange={e => setContactoModal({ ...contactoModal, email: e.target.value })} /></div>
              <div><label style={lbl}>Confirmar correo electrónico *</label><input data-testid="contacto-email2" style={inp} value={contactoModal.email2} onChange={e => setContactoModal({ ...contactoModal, email2: e.target.value })} /></div>
              {contactoModal.email && contactoModal.email2 && contactoModal.email !== contactoModal.email2 && (
                <div style={{ color: "#e11d48", fontSize: "0.8rem" }} data-testid="contacto-email-error">Los correos no coinciden</div>
              )}
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.6rem", marginTop: "1.2rem" }}>
              <button onClick={() => setContactoModal(null)} style={btn("rgba(255,255,255,0.15)", true)}>Cancelar</button>
              <button data-testid="contacto-crear" onClick={crearContacto} disabled={loading || !contactoModal.nombres || !contactoModal.aPaterno || !contactoModal.rut || !contactoModal.email || contactoModal.email !== contactoModal.email2} style={btn("var(--gold)", true)}><i className="fa fa-user-plus" style={{ marginRight: "0.4rem" }} />Crear contacto</button>
            </div>
          </div>
        </div>
      )}

      {/* Modal firma */}
      {firmaModal && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center", padding: "2rem" }} onClick={() => setFirmaModal(null)}>
          <div style={{ background: "rgba(14,14,16,0.9)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", borderRadius: "0px", maxWidth: "480px", width: "100%", padding: "1.5rem", border: "1px solid rgba(255,255,255,0.15)" }} onClick={e => e.stopPropagation()} data-testid="setcred-firma-modal">
            <h3 style={{ margin: "0 0 0.3rem", color: "var(--gold)" }}>Enviar a firmar</h3>
            <p style={{ fontSize: "0.85rem", opacity: 0.7, margin: "0 0 1rem" }}>{firmaModal.doc_nombre}</p>
            <div style={{ display: "grid", gap: "0.8rem" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.8rem" }}>
                <div><label style={lbl}>Nombres</label><input data-testid="firma-nombres" style={inp} value={firmaModal.nombres} onChange={e => setFirmaModal({ ...firmaModal, nombres: e.target.value })} /></div>
                <div><label style={lbl}>Apellido paterno</label><input data-testid="firma-apaterno" style={inp} value={firmaModal.aPaterno} onChange={e => setFirmaModal({ ...firmaModal, aPaterno: e.target.value })} /></div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.8rem" }}>
                <div><label style={lbl}>Apellido materno</label><input data-testid="firma-amaterno" style={inp} value={firmaModal.aMaterno} onChange={e => setFirmaModal({ ...firmaModal, aMaterno: e.target.value })} /></div>
                <div><label style={lbl}>RUT</label><input data-testid="firma-rut" style={inp} value={firmaModal.rut} onChange={e => setFirmaModal({ ...firmaModal, rut: e.target.value })} /></div>
              </div>
              <div><label style={lbl}>Correo del firmante</label><input data-testid="firma-email" style={inp} value={firmaModal.email} onChange={e => setFirmaModal({ ...firmaModal, email: e.target.value })} /></div>
              <div><label style={lbl}>Comentario (opcional)</label><input data-testid="firma-comentario" style={inp} value={firmaModal.comentario} onChange={e => setFirmaModal({ ...firmaModal, comentario: e.target.value })} /></div>
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.6rem", marginTop: "1.2rem" }}>
              <button onClick={() => setFirmaModal(null)} style={btn("rgba(255,255,255,0.15)", true)}>Cancelar</button>
              <button data-testid="firma-enviar" onClick={enviarFirma} disabled={loading} style={btn("var(--gold)", true)}><i className="fa fa-paper-plane" style={{ marginRight: "0.4rem" }} />Enviar a firmar</button>
            </div>
          </div>
        </div>
      )}

      {previewCombinado && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)", backdropFilter: "blur(10px)", WebkitBackdropFilter: "blur(10px)", zIndex: 150, display: "flex", alignItems: "center", justifyContent: "center", padding: "1.5rem" }} onClick={() => setPreviewCombinado(null)}>
          <div data-testid="setcred-visor-maserati" onClick={e => e.stopPropagation()}
            style={{ width: "min(1000px, 96vw)", height: "90vh", display: "flex", flexDirection: "column", background: "#0a0a0c", border: "1px solid rgba(212,175,55,0.55)", borderRadius: 0, boxShadow: "0 0 60px -10px rgba(212,175,55,0.35), 0 40px 80px -20px rgba(0,0,0,0.95)" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0.9rem 1.2rem", borderBottom: "1px solid rgba(212,175,55,0.3)" }}>
              <div>
                <div style={{ color: "#d4af37", fontWeight: 800, fontSize: "1.05rem" }}>🔍 Visor Maserati — {previewCombinado.nombre}</div>
                <div style={{ color: "#fff", opacity: 0.55, fontSize: "0.75rem", marginTop: 3 }}>
                  {previewCombinado.usados.length} documento(s) del expediente, en este orden: {previewCombinado.usados.join(" → ")}
                  {previewCombinado.excluidos.length > 0 && <span style={{ color: "#f59e0b" }}> · ⚠ {previewCombinado.excluidos.length} excluido(s) por RUT ajeno</span>}
                </div>
              </div>
              <button data-testid="setcred-visor-cerrar" onClick={() => setPreviewCombinado(null)}
                style={{ background: "transparent", border: "1px solid rgba(212,175,55,0.6)", color: "#d4af37", borderRadius: 0, padding: "0.4rem 1rem", cursor: "pointer", fontWeight: 800 }}>
                Cerrar ✕
              </button>
            </div>
            <iframe title="Previsualización combinado" src={previewCombinado.url}
              style={{ flex: 1, width: "100%", border: "none", background: "#161618" }} />
          </div>
        </div>
      )}
    </div>
  );
}
