import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

const card = { background: "rgba(15,23,42,0.6)", padding: "1.5rem", borderRadius: "14px", border: "1px solid rgba(255,255,255,0.08)", marginBottom: "1.5rem" };
const inp = { background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: "8px", padding: "0.55rem 0.8rem", color: "#fff", fontSize: "0.9rem", width: "100%" };
const btn = (bg, small) => ({ background: bg, color: bg === "var(--gold)" ? "#0a0e17" : "#fff", border: "none", borderRadius: "8px", padding: small ? "0.4rem 0.8rem" : "0.6rem 1.2rem", fontWeight: 700, cursor: "pointer", fontSize: small ? "0.8rem" : "0.9rem" });
const lbl = { display: "block", fontSize: "0.75rem", opacity: 0.6, marginBottom: "0.3rem", textTransform: "uppercase", letterSpacing: "0.5px" };

export default function SetCreditoModule() {
  const [sets, setSets] = useState([]);
  const [docTipos, setDocTipos] = useState({});
  const [current, setCurrent] = useState(null);
  const [migrup, setMigrup] = useState(null);
  const [nuevo, setNuevo] = useState({ nombre: "", rut: "", email: "" });
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");
  const [firmaModal, setFirmaModal] = useState(null);
  const fileRef = useRef();
  const [tipoUpload, setTipoUpload] = useState("solicitud_credito");

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
        ? `✅ Set completo enviado a firmar a ${firmaModal.email} (${r.data.paginas} hojas, ${r.data.documentos_incluidos?.length || 0} documentos)`
        : `✅ Documento enviado a firmar a ${firmaModal.email}`);
      setFirmaModal(null);
      await abrir(current.id);
      loadMigrup();
    } catch (e) { setMsg("Error al enviar a firmar: " + (e.response?.data?.detail || e.message)); }
    setLoading(false);
  };

  return (
    <div style={{ padding: "1.5rem", color: "var(--white)", maxWidth: "1050px" }} data-testid="setcredito-module">
      {msg && <div data-testid="setcred-msg" style={{ padding: "0.7rem 1rem", borderRadius: "8px", marginBottom: "1rem", background: msg.startsWith("✅") ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)", color: msg.startsWith("✅") ? "#22c55e" : "#ef4444", fontWeight: 600 }}>{msg}</div>}

      {/* Estado migrup */}
      <div data-testid="migrup-status" style={{ ...card, display: "flex", alignItems: "center", gap: "1rem", flexWrap: "wrap", marginBottom: "1rem", padding: "0.9rem 1.3rem" }}>
        <i className="fa fa-pencil-square-o" style={{ color: "var(--gold)", fontSize: "1.3rem" }} />
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700 }}>Firma electrónica migrup / eCert{migrup?.user ? ` — ${migrup.user.nombres} ${migrup.user.apellido}` : ""}</div>
          <div style={{ fontSize: "0.82rem", opacity: 0.7 }}>
            {migrup?.connected
              ? `Conectado · ${migrup.firmas_terceros_disponibles ?? "—"} firmas de terceros disponibles`
              : migrup?.configured ? "No se pudo conectar (revisar credenciales)" : "No configurado"}
          </div>
        </div>
        <span style={{ padding: "0.2rem 0.7rem", borderRadius: "999px", fontSize: "0.8rem", fontWeight: 700, background: migrup?.connected ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)", color: migrup?.connected ? "#22c55e" : "#ef4444" }}>
          {migrup?.connected ? "● Conectado" : "○ Desconectado"}
        </span>
      </div>

      {!current ? (
        <>
          {/* Crear set */}
          <div style={card}>
            <h3 style={{ margin: "0 0 1rem", color: "var(--gold)", fontSize: "1.1rem" }}><i className="fa fa-folder-plus" style={{ marginRight: "0.5rem" }} />Nuevo Set de Crédito</h3>
            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 2fr auto", gap: "1rem", alignItems: "end" }}>
              <div><label style={lbl}>Nombre del cliente</label><input data-testid="setcred-nombre" style={inp} value={nuevo.nombre} onChange={e => setNuevo({ ...nuevo, nombre: e.target.value })} /></div>
              <div><label style={lbl}>RUT</label><input data-testid="setcred-rut" style={inp} value={nuevo.rut} onChange={e => setNuevo({ ...nuevo, rut: e.target.value })} /></div>
              <div><label style={lbl}>Correo (para firmar)</label><input data-testid="setcred-email" style={inp} value={nuevo.email} onChange={e => setNuevo({ ...nuevo, email: e.target.value })} placeholder="cliente@correo.cl" /></div>
              <button data-testid="setcred-crear" onClick={crearSet} disabled={loading} style={btn("var(--gold)")}>Crear</button>
            </div>
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
            </div>
            <button data-testid="setcred-eliminar" onClick={() => eliminarSet(current.id)} style={btn("#ef4444", true)}><i className="fa fa-trash" /> Eliminar set</button>
          </div>

          {/* Subir documento */}
          <div style={{ display: "flex", gap: "0.8rem", alignItems: "center", flexWrap: "wrap", marginBottom: "1rem", padding: "0.8rem", background: "rgba(255,255,255,0.03)", borderRadius: "8px" }}>
            <span style={{ fontSize: "0.85rem", opacity: 0.7 }}>Tipo:</span>
            <select data-testid="setcred-tipo" value={tipoUpload} onChange={e => setTipoUpload(e.target.value)} style={{ ...inp, width: "auto" }}>
              {Object.entries(docTipos).map(([k, v]) => <option key={k} value={k} style={{ background: "#1a1f2e" }}>{v}</option>)}
            </select>
            <input ref={fileRef} data-testid="setcred-upload-input" type="file" accept="application/pdf,image/*" onChange={subir} style={{ display: "none" }} />
            <button data-testid="setcred-upload-btn" onClick={() => fileRef.current?.click()} disabled={loading} style={btn("#3b82f6", true)}><i className="fa fa-upload" style={{ marginRight: "0.4rem" }} />Subir documento</button>
          </div>

          {/* Documentos */}
          {current.archivos.length > 0 && (
            <div data-testid="setcred-firmar-todo-bar" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.8rem", flexWrap: "wrap", padding: "0.9rem 1rem", background: "rgba(212,175,55,0.1)", border: "1px solid rgba(212,175,55,0.35)", borderRadius: "10px", marginBottom: "1rem" }}>
              <div style={{ fontSize: "0.88rem" }}>
                <b style={{ color: "var(--gold)" }}>Firmar todo de una vez</b> — combina los {current.archivos.filter(a => !a.nombre.startsWith("COMBINADO_SET")).length} documentos en un solo PDF y el cliente firma todas las hojas con un clic.
              </div>
              <button data-testid="setcred-firmar-todo" onClick={abrirFirmaCompleta} disabled={!migrup?.connected || loading} style={btn("var(--gold)")}><i className="fa fa-check-square-o" style={{ marginRight: "0.4rem" }} />Combinar y enviar a firmar todo</button>
            </div>
          )}
          {current.archivos.filter(a => !a.nombre.startsWith("COMBINADO_SET")).length === 0 ? <div style={{ opacity: 0.5 }}>Sin documentos. Subí los del set (seguros, solicitud de crédito, declaración de salud).</div> :
            current.archivos.filter(a => !a.nombre.startsWith("COMBINADO_SET")).map((a, i) => (
              <div key={i} data-testid={`setcred-file-${i}`} style={{ display: "flex", alignItems: "center", gap: "0.7rem", padding: "0.55rem 0.4rem", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                <i className="fa fa-file-pdf-o" style={{ color: "#ef4444" }} />
                <span style={{ flex: 1 }}>{a.nombre}</span>
                <span style={{ fontSize: "0.72rem", padding: "0.12rem 0.5rem", borderRadius: "999px", background: "rgba(212,175,55,0.15)", color: "var(--gold)" }}>{docTipos[a.tipo] || "Otro"}</span>
                <a href={`${API}/api/set-credito/sets/${current.id}/download/${encodeURIComponent(a.ruta)}?inline=true`} target="_blank" rel="noreferrer" style={{ color: "#3b82f6" }} title="Ver"><i className="fa fa-eye" /></a>
                <button data-testid={`setcred-firmar-${i}`} onClick={() => abrirFirma(a)} disabled={!migrup?.connected} style={btn("var(--gold)", true)} title="Enviar a firmar"><i className="fa fa-pencil" style={{ marginRight: "0.3rem" }} />Firmar</button>
                <button onClick={() => borrarFile(a.ruta)} style={{ background: "none", border: "none", color: "#ef4444", cursor: "pointer" }}><i className="fa fa-trash" /></button>
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
        </div>
      )}

      {/* Modal firma */}
      {firmaModal && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center", padding: "2rem" }} onClick={() => setFirmaModal(null)}>
          <div style={{ background: "#1a1f2e", borderRadius: "12px", maxWidth: "480px", width: "100%", padding: "1.5rem", border: "1px solid rgba(255,255,255,0.15)" }} onClick={e => e.stopPropagation()} data-testid="setcred-firma-modal">
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
    </div>
  );
}
