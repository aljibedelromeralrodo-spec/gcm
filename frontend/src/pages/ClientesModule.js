import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import DOMPurify from "dompurify";
import ImportarCorreo from "../components/ImportarCorreo";
import ConversorUF from "../components/ConversorUF";
import CompromisoEditor from "./CompromisoEditor";

const API = process.env.REACT_APP_BACKEND_URL;
const CAT_LABELS = { cedula: "Cédula", liquidacion: "Liquidaciones", afp: "AFP", cmf: "CMF", imp_renta: "Imp. Renta", boletas: "Boletas" };

const BrokersPanel = ({ brokers, dest, setDest, reloadBrokers, soloAdmin }) => {
  const [nuevo, setNuevo] = useState({ nombre: "", contactos: "", emails: "" });
  const [showAdd, setShowAdd] = useState(false);
  const [editId, setEditId] = useState(null);
  const destList = dest.split(",").map(s => s.trim()).filter(Boolean);
  const isOn = (b) => (b.emails || []).length > 0 && b.emails.every(e => destList.some(d => d.toLowerCase() === e.toLowerCase()));
  const toggle = (b) => {
    if (isOn(b)) setDest(destList.filter(d => !b.emails.some(e => e.toLowerCase() === d.toLowerCase())).join(", "));
    else setDest([...destList, ...b.emails.filter(e => !destList.some(d => d.toLowerCase() === e.toLowerCase()))].join(", "));
  };
  const guardar = async () => {
    if (!nuevo.nombre.trim() || !nuevo.emails.trim()) return;
    try {
      if (editId) await axios.put(`${API}/api/brokers/${editId}`, nuevo);
      else await axios.post(`${API}/api/brokers`, nuevo);
      setNuevo({ nombre: "", contactos: "", emails: "" }); setShowAdd(false); setEditId(null);
      reloadBrokers();
    } catch (e) { console.error(e); }
  };
  const editar = (b) => {
    setEditId(b.id); setShowAdd(true);
    setNuevo({ nombre: b.nombre, contactos: b.contactos || "", emails: (b.emails || []).join(", ") });
  };
  const quitar = async (b) => {
    if (!window.confirm(`¿Quitar el broker "${b.nombre}"?`)) return;
    try { await axios.delete(`${API}/api/brokers/${b.id}`); reloadBrokers(); } catch (e) { console.error(e); }
  };
  const inpS = { padding: "0.4rem 0.6rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.3)", background: "#232326", color: "#e2e8f0", fontSize: 12 };
  return (
    <div data-testid="brokers-panel" style={{ background: "rgba(212,175,55,0.06)", border: "1px solid rgba(212,175,55,0.25)", borderRadius: 0, padding: "0.7rem 0.9rem" }}>
      <div style={{ opacity: 0.8, fontSize: 11, textTransform: "uppercase", marginBottom: 6, fontWeight: 700 }}>
        {soloAdmin ? "Plantillas de brokers (editar / agregar / quitar)" : "Brokers — marca para agregarlos al envío"}
      </div>
      <div style={{ display: "grid", gap: 4 }}>
        {brokers.map(b => (
          <div key={b.id} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5 }}>
            {soloAdmin ? (
              <span style={{ flex: 1 }}><b>{b.nombre}</b>{b.contactos ? ` — ${b.contactos}` : ""} <span style={{ opacity: 0.55 }}>({(b.emails || []).join(", ")})</span></span>
            ) : (
              <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", flex: 1 }}>
                <input type="checkbox" checked={isOn(b)} onChange={() => toggle(b)} data-testid={`broker-check-${b.id}`} />
                <span><b>{b.nombre}</b>{b.contactos ? ` — ${b.contactos}` : ""} <span style={{ opacity: 0.55 }}>({(b.emails || []).join(", ")})</span></span>
              </label>
            )}
            <button onClick={() => editar(b)} title="Editar broker" data-testid={`broker-edit-${b.id}`}
              style={{ background: "transparent", border: "none", color: "#d4af37", cursor: "pointer" }}><i className="fa fa-pencil" /></button>
            <button onClick={() => quitar(b)} title="Quitar broker" data-testid={`broker-del-${b.id}`}
              style={{ background: "transparent", border: "none", color: "#fb7185", cursor: "pointer" }}><i className="fa fa-trash" /></button>
          </div>
        ))}
      </div>
      {showAdd ? (
        <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
          <input value={nuevo.nombre} onChange={e => setNuevo({ ...nuevo, nombre: e.target.value })} placeholder="Nombre broker" data-testid="broker-new-nombre" style={{ ...inpS, flex: 1, minWidth: 110 }} />
          <input value={nuevo.contactos} onChange={e => setNuevo({ ...nuevo, contactos: e.target.value })} placeholder="Personas de contacto" data-testid="broker-new-contactos" style={{ ...inpS, flex: 1, minWidth: 130 }} />
          <input value={nuevo.emails} onChange={e => setNuevo({ ...nuevo, emails: e.target.value })} placeholder="correos separados por coma" data-testid="broker-new-emails" style={{ ...inpS, flex: 2, minWidth: 170 }} />
          <button onClick={guardar} data-testid="broker-new-save" style={{ ...inpS, background: "#0f52ba", border: "none", fontWeight: 700, cursor: "pointer" }}>{editId ? "Actualizar" : "Guardar"}</button>
          <button onClick={() => { setShowAdd(false); setEditId(null); setNuevo({ nombre: "", contactos: "", emails: "" }); }} style={{ ...inpS, background: "transparent", cursor: "pointer" }}>Cancelar</button>
        </div>
      ) : (
        <button onClick={() => setShowAdd(true)} data-testid="broker-add-btn" style={{ marginTop: 8, background: "transparent", border: "1px dashed rgba(212,175,55,0.5)", color: "#d4af37", borderRadius: 0, padding: "0.3rem 0.7rem", fontSize: 11.5, cursor: "pointer" }}>
          <i className="fa fa-plus" /> Agregar broker
        </button>
      )}
    </div>
  );
};

// Input inteligente para montos en UF. Si el usuario ingresa un número
// grande (>= 20000) se asume que es CLP y se convierte automáticamente
// dividiendo por el valor de la UF del día (al hacer blur o pegar).
// Muestra siempre un hint del equivalente en CLP debajo.
function UFAmountInput({ value, onChange, uf, testid, dataTestid }) {
  const [raw, setRaw] = React.useState(value == null || value === "" ? "" : String(value));
  React.useEffect(() => {
    // Sync when parent value changes (ej: OCR autofill)
    setRaw(value == null || value === "" ? "" : String(value));
  }, [value]);

  const normalize = (str) => {
    // "1.234,56" (es-CL) o "1234.56" o "$130.694.624" → number
    if (str == null) return NaN;
    let s = String(str).trim().replace(/\$/g, "").replace(/\s+/g, "");
    if (s === "") return NaN;
    if (s.includes(",") && s.includes(".")) {
      // asume "." miles y "," decimal
      s = s.replace(/\./g, "").replace(",", ".");
    } else if (s.includes(",") && !s.includes(".")) {
      s = s.replace(",", ".");
    } else if (s.includes(".")) {
      // Sin coma: si tiene >1 punto o el último grupo no es de 1-2 dígitos, son miles
      const parts = s.split(".");
      const lastLen = parts[parts.length - 1].length;
      if (parts.length > 2 || lastLen === 3) s = parts.join("");
    }
    return Number(s);
  };

  const commit = (str) => {
    const n = normalize(str);
    if (isNaN(n)) { onChange(""); return; }
    if (n >= 20000 && uf > 0) {
      const ufVal = +(n / uf).toFixed(2);
      onChange(ufVal);
      setRaw(String(ufVal));
    } else {
      const ufVal = +Number(n).toFixed(2);
      onChange(ufVal);
      setRaw(String(ufVal));
    }
  };

  const preview = (() => {
    const n = normalize(raw);
    if (isNaN(n) || n === 0) return null;
    if (n >= 20000 && uf > 0) {
      const ufEq = (n / uf);
      return `≈ UF ${ufEq.toLocaleString('es-CL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} (CLP detectado)`;
    }
    const clpEq = Math.round(n * uf);
    return `≈ $ ${clpEq.toLocaleString('es-CL')} CLP`;
  })();

  return (
    <div>
      <input
        type="text"
        inputMode="decimal"
        value={raw}
        onChange={(e) => setRaw(e.target.value)}
        onBlur={(e) => commit(e.target.value)}
        onPaste={(e) => {
          const pasted = (e.clipboardData || window.clipboardData).getData("text");
          if (pasted && pasted.length > 4) {
            e.preventDefault();
            commit(pasted);
          }
        }}
        placeholder="Ingresá UF o CLP…"
        data-testid={dataTestid || testid}
        style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, border: "1px solid #d4d4d8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }}
      />
      {preview && (
        <div style={{ fontSize: 10, color: "#b8942e", marginTop: 2, fontWeight: 500 }}>{preview}</div>
      )}
    </div>
  );
}

export default function ClientesModule({ onNavigate }) {
  const [view, setView] = useState("list"); // list, detail, emails, ajustes
  const [folders, setFolders] = useState([]);
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState("");
  const [currentFolder, setCurrentFolder] = useState(null);
  const [techo, setTecho] = useState(null);
  const [showCompromiso, setShowCompromiso] = useState(false);
  const [techoBusy, setTechoBusy] = useState(false);
  const [emails, setEmails] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [newFolder, setNewFolder] = useState({ nombre: "", rut: "", codeudor_nombre: "", codeudor_rut: "" });
  const [searchQuery, setSearchQuery] = useState("");
  const [emailSearch, setEmailSearch] = useState("");
  const [emailResults, setEmailResults] = useState([]);
  const [savingAttachment, setSavingAttachment] = useState("");
  const [ajustes, setAjustes] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [editDraft, setEditDraft] = useState({});
  const [savingEdit, setSavingEdit] = useState(false);
  const [finOpenId, setFinOpenId] = useState(null);
  const [finDraft, setFinDraft] = useState({});
  const [finSaving, setFinSaving] = useState(false);
  const [ocrRunning, setOcrRunning] = useState(false);
  const [previewFile, setPreviewFile] = useState(null); // { url, name, mime }
  const [selectedFiles, setSelectedFiles] = useState({}); // { folder_id: Set(rel_paths) }
  const [uploadingFor, setUploadingFor] = useState(null); // folder_id currently uploading
  const [uploadingManual, setUploadingManual] = useState(false);
  const [merging, setMerging] = useState(false);
  const [mergingProto, setMergingProto] = useState(null); // folder_id in progress
  const [splittingRel, setSplittingRel] = useState(null); // rel path currently splitting
  const [emailModal, setEmailModal] = useState(null);
  const [tasacionModal, setTasacionModal] = useState(null); // { folder, archivos, campos... }
  const [tasacionContactos, setTasacionContactos] = useState([]); // plantillas inmobiliaria
  const [estudioPlantillas, setEstudioPlantillas] = useState([]); // plantillas estudio de título
  const [brokers, setBrokers] = useState([]);
  const [estudioModal, setEstudioModal] = useState(null); // estudio de título
  const [reparosModal, setReparosModal] = useState(null); // reparos estudio de título
  const [escrituraModal, setEscrituraModal] = useState(null); // firma de escritura
  const [notarias, setNotarias] = useState([]);
  const [pedirModal, setPedirModal] = useState(null); // pedir documentos faltantes
  const [missingDocsModal, setMissingDocsModal] = useState(null); // { folder, to, extra, preview, sending }
  const [historialModal, setHistorialModal] = useState(null); // { folder, eventos, loading }
  const [_respaldoModal, setRespaldoModal] = useState(null); // { subiendo, progreso, resultado }
  const [folderTab, setFolderTab] = useState("clientes"); // clientes | escrituracion
  const [enriching, setEnriching] = useState(null); // `${folderId}${modo}` en progreso
  const [forzarModal, setForzarModal] = useState(null); // {nombre, rut, sug, buscando, forzando, msg}

  const _importarRespaldo = async (file) => {
    if (!file) return;
    const sessionId = `imp-${Date.now()}`;
    const CHUNK = 4 * 1024 * 1024;
    const total = Math.ceil(file.size / CHUNK);
    setRespaldoModal({ subiendo: true, progreso: 0, resultado: null });
    try {
      for (let i = 0; i < total; i++) {
        const fd = new FormData();
        fd.append("session_id", sessionId);
        fd.append("index", String(i));
        fd.append("chunk", file.slice(i * CHUNK, (i + 1) * CHUNK), "chunk.bin");
        await axios.post(`${API}/api/admin/respaldo/import-chunk`, fd, { timeout: 120000 });
        setRespaldoModal((m) => ({ ...m, subiendo: true, progreso: Math.round(((i + 1) / total) * 100) }));
      }
      const r = await axios.post(`${API}/api/admin/respaldo/import-finish`, { session_id: sessionId }, { timeout: 300000 });
      setRespaldoModal({ subiendo: false, progreso: 100, resultado: r.data });
      loadFolders();
    } catch (e) {
      setRespaldoModal({ subiendo: false, progreso: 0, resultado: { error: e.response?.data?.detail || e.message } });
    }
  };
  const [ufValue, setUfValue] = useState(40842);
  const fileInputRef = useRef(null);
  const uploadCtxRef = useRef(null); // { folder_id, subfolder }

  useEffect(() => { loadFolders(); loadUf(); }, []);

  const loadUf = async () => {
    try {
      const r = await axios.get(`${API}/api/clientes/uf-actual`);
      setUfValue(r.data?.valor || 40842);
    } catch { /* keep default */ }
  };

  const fmtAct = (iso) => {
    if (!iso) return "";
    try {
      return new Date(iso).toLocaleString("es-CL", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false });
    } catch { return (iso || "").slice(0, 16).replace("T", " "); }
  };

  const fmtActFull = (iso) => {
    if (!iso) return "";
    try {
      return new Date(iso).toLocaleString("es-CL", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false });
    } catch { return (iso || "").slice(0, 16).replace("T", " "); }
  };

  const openHistorial = async (f) => {
    setHistorialModal({ folder: f, eventos: [], loading: true });
    try {
      const r = await axios.get(`${API}/api/clientes/folders/${f.id}/historial`);
      setHistorialModal({ folder: f, eventos: r.data.eventos || [], loading: false });
    } catch (e) {
      alert("Error cargando historial: " + (e.response?.data?.detail || e.message));
      setHistorialModal(null);
    }
  };

  const marcarTerminado = async (f, tipo, terminado) => {
    try {
      await axios.patch(`${API}/api/clientes/folders/${f.id}/actividad-terminada`, { tipo, terminado });
      loadFolders();
    } catch (e) { alert("Error: " + (e.response?.data?.detail || e.message)); }
  };

  const openTasacion = async (f) => {
    let archivos = [];
    // REGLA: la carta de aprobación debe estar SIEMPRE descargada en la carpeta antes de tasar
    try { await axios.post(`${API}/api/clientes/folders/${f.id}/sync-aprobacion`, {}, { timeout: 90000 }); } catch (_e) { /* best effort */ }
    try {
      const r = await axios.get(`${API}/api/clientes/folders/${f.id}`);
      // Solo la carta de aprobación va preseleccionada — nada más de la carpeta
      archivos = (r.data.archivos || []).map(a => ({ ...a, sel: /carta|oferta|aprobaci/i.test(a.nombre) }))
        .sort((a, b) => (b.sel ? 1 : 0) - (a.sel ? 1 : 0));
    } catch (_e) { /* sin archivos */ }
    let prefill = {};
    try {
      const pf = await axios.get(`${API}/api/clientes/folders/${f.id}/tasacion-prefill`, { timeout: 90000 });
      prefill = pf.data.prefill || {};
    } catch (_e) { /* best effort */ }
    try {
      const [c, b] = await Promise.all([
        axios.get(`${API}/api/tasacion/contactos`),
        axios.get(`${API}/api/brokers`),
      ]);
      setTasacionContactos(c.data.contactos || []);
      setBrokers(b.data.brokers || []);
    } catch (_e) { setTasacionContactos([]); }
    const df = f.datos_financieros || {};
    const valorUF = df.valor_propiedad || prefill.valor_propiedad_uf || "";
    setTasacionModal({
      folder: f, archivos, tipo: "Individual",
      destinatarios: "contacto@valueproperty.cl, victoriavilches@centralmutuos.cl",
      modalidad: "inmobiliaria", broker_id: "",
      inmobiliaria: df.inmobiliaria || prefill.inmobiliaria || "",
      inmo_contacto_nombre: "", inmo_contacto_email: "",
      intro: "", voucher_nombre: "", fecha_tasacion: f.tasacion_fecha || "",
      direccion: df.direccion || prefill.direccion || "", comuna: df.comuna || prefill.comuna || "", ciudad: df.ciudad || prefill.ciudad || "",
      unidad: prefill.unidad || "", rol_avaluo: prefill.rol_avaluo || "",
      valor_uf: valorUF ? String(valorUF) : "",
      valor_esperado_uf: valorUF ? String(valorUF) : "",
      vendedor: prefill.vendedor_nombre || "", vendedor_email: prefill.vendedor_email || "",
      contacto_nombre: prefill.vendedor_nombre || "", contacto_telefono: prefill.vendedor_telefono || "",
      contacto_email: prefill.vendedor_email || "",
      observaciones: "", preview: null, loading: false, msg: "",
    });
  };

  const subirVoucher = async (file) => {
    if (!file) return;
    const m = tasacionModal;
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("subfolder", "99_otros");
      const r = await axios.post(`${API}/api/clientes/folders/${m.folder.id}/upload-file`, fd);
      const ruta = r.data.saved || `99_otros/${file.name}`;
      setTasacionModal(prev => ({
        ...prev, preview: null, voucher_nombre: file.name, voucher_ruta: ruta,
        archivos: [{ nombre: file.name, ruta, subfolder: "99_otros", sel: true },
                   ...prev.archivos.filter(a => a.ruta !== ruta)],
      }));
    } catch (e) {
      setTasacionModal(prev => ({ ...prev, msg: "Error subiendo voucher: " + (e.response?.data?.detail || e.message) }));
    }
  };

  const detectarFechaTasacion = async () => {
    setTasacionModal(prev => ({ ...prev, loading: true }));
    try {
      const r = await axios.post(`${API}/api/tasacion/detectar-fecha/${tasacionModal.folder.id}`);
      if (r.data.ok) {
        setTasacionModal(prev => ({ ...prev, loading: false, fecha_tasacion: r.data.fecha, msg: `✅ Fecha detectada del correo: ${r.data.fecha}` }));
        loadFolders();
      } else {
        setTasacionModal(prev => ({ ...prev, loading: false, msg: r.data.detail || "No se encontró la fecha" }));
      }
    } catch (e) {
      setTasacionModal(prev => ({ ...prev, loading: false, msg: "Error: " + (e.response?.data?.detail || e.message) }));
    }
  };

  const guardarFechaTasacion = async () => {
    try {
      await axios.patch(`${API}/api/tasacion/fecha/${tasacionModal.folder.id}`, { fecha: tasacionModal.fecha_tasacion });
      setTasacionModal(prev => ({ ...prev, msg: "✅ Fecha de tasación guardada" }));
      loadFolders();
    } catch (e) {
      setTasacionModal(prev => ({ ...prev, msg: "Error: " + (e.response?.data?.detail || e.message) }));
    }
  };

  const pickInmoPlantilla = (nombre) => {
    const p = tasacionContactos.find(c => (c.inmobiliaria || "").toLowerCase() === (nombre || "").toLowerCase());
    setTasacionModal(m => ({
      ...m, inmobiliaria: nombre, preview: null,
      inmo_contacto_nombre: p ? (p.contacto_nombre || m.inmo_contacto_nombre) : m.inmo_contacto_nombre,
      inmo_contacto_email: p ? (p.contacto_email || m.inmo_contacto_email) : m.inmo_contacto_email,
    }));
  };

  const reloadBrokers = async () => {
    try {
      const b = await axios.get(`${API}/api/brokers`);
      setBrokers(b.data.brokers || []);
    } catch (e) { console.error(e); }
  };

  const openPedirFaltantes = (f) => {
    const faltan = (f.criterios || []).filter(c => !c.ok && !["Enviada a mesa", "Datos financieros completos"].includes(c.nombre)).map(c => c.nombre);
    setPedirModal({ folder: f, destinatario: f.source_email || "", faltantes: faltan.join("\n"), mensaje: "", preview: null, loading: false, msg: "" });
  };

  const pedirPayload = (m, confirm) => ({
    destinatario: m.destinatario,
    faltantes: m.faltantes.split("\n").map(s => s.trim()).filter(Boolean),
    mensaje: m.mensaje, confirm,
  });

  const pedirPreview = async () => {
    setPedirModal(m => ({ ...m, loading: true, msg: "" }));
    try {
      const r = await axios.post(`${API}/api/clientes/folders/${pedirModal.folder.id}/pedir-faltantes`, pedirPayload(pedirModal, false));
      setPedirModal(m => ({ ...m, preview: r.data, loading: false }));
    } catch (e) {
      setPedirModal(m => ({ ...m, loading: false, msg: "Error: " + (e.response?.data?.detail || e.message) }));
    }
  };

  const pedirEnviar = async () => {
    if (!window.confirm(`¿Pedir los documentos faltantes de ${pedirModal.folder.nombre} a ${pedirModal.destinatario}?`)) return;
    setPedirModal(m => ({ ...m, loading: true, msg: "" }));
    try {
      const r = await axios.post(`${API}/api/clientes/folders/${pedirModal.folder.id}/pedir-faltantes`, pedirPayload(pedirModal, true));
      setPedirModal(m => ({ ...m, loading: false, msg: `✅ Correo enviado a ${r.data.to}` }));
      loadFolders();
    } catch (e) {
      setPedirModal(m => ({ ...m, loading: false, msg: "Error: " + (e.response?.data?.detail || e.message) }));
    }
  };

  const tasacionPayload = (m, confirm) => ({
    folder_id: m.folder.id, nombre: m.folder.nombre, rut: m.folder.rut || "",
    destinatarios: m.destinatarios, modalidad: m.modalidad,
    inmobiliaria: m.inmobiliaria, inmo_contacto_nombre: m.inmo_contacto_nombre,
    inmo_contacto_email: m.inmo_contacto_email,
    intro: m.intro, voucher: !!m.voucher_nombre,
    tipo: m.tipo, direccion: m.direccion, comuna: m.comuna, ciudad: m.ciudad, unidad: m.unidad, rol_avaluo: m.rol_avaluo,
    valor_uf: m.valor_uf, valor_esperado_uf: m.valor_esperado_uf,
    carta_adjunta: m.archivos.some(a => a.sel && /carta|oferta|aprobaci/i.test(a.nombre)),
    vendedor: m.vendedor, vendedor_email: m.vendedor_email,
    contacto_nombre: m.contacto_nombre, contacto_telefono: m.contacto_telefono,
    contacto_email: m.contacto_email,
    observaciones: m.observaciones,
    attach_files: m.archivos.filter(a => a.sel).map(a => a.ruta),
    confirm,
  });

  const tasacionPreview = async () => {
    setTasacionModal(m => ({ ...m, loading: true, msg: "" }));
    try {
      const r = await axios.post(`${API}/api/tasacion/enviar`, tasacionPayload(tasacionModal, false));
      setTasacionModal(m => ({ ...m, preview: r.data, loading: false }));
    } catch (e) {
      setTasacionModal(m => ({ ...m, loading: false, msg: "Error: " + (e.response?.data?.detail || e.message) }));
    }
  };

  const tasacionEnviar = async () => {
    if (!window.confirm(`¿Enviar la solicitud de tasación de ${tasacionModal.folder.nombre} a: ${tasacionModal.destinatarios}?`)) return;
    setTasacionModal(m => ({ ...m, loading: true, msg: "" }));
    try {
      const r = await axios.post(`${API}/api/tasacion/enviar`, tasacionPayload(tasacionModal, true));
      setTasacionModal(m => ({ ...m, loading: false, msg: `✅ Solicitud enviada a ${r.data.to.join(", ")}` }));
      loadFolders();
    } catch (e) {
      setTasacionModal(m => ({ ...m, loading: false, msg: "Error: " + (e.response?.data?.detail || e.message) }));
    }
  };

  const openReparos = async (f) => {
    setReparosModal({ folder: f, loading: true, data: null, msg: "" });
    try {
      const r = await axios.get(`${API}/api/estudio-titulo/reparos/${f.id}`);
      setReparosModal(prev => prev && ({ ...prev, loading: false, data: r.data }));
    } catch (e) {
      setReparosModal(prev => prev && ({ ...prev, loading: false, msg: "Error: " + (e.response?.data?.detail || e.message) }));
    }
  };

  const scanReparos = async () => {
    const m = reparosModal;
    setReparosModal(prev => ({ ...prev, scanning: true, msg: "" }));
    try {
      const r = await axios.post(`${API}/api/estudio-titulo/reparos/${m.folder.id}/scan`);
      const items = r.data.reparos?.items || [];
      setReparosModal(prev => ({ ...prev, scanning: false, data: { ...prev.data, reparos: r.data.reparos },
        msg: items.length ? `🔍 Hilo revisado: ${items.length} reparo(s) registrados.` : "🔍 Hilo revisado: no se detectaron reparos del abogado todavía." }));
      loadFolders();
    } catch (e) {
      setReparosModal(prev => ({ ...prev, scanning: false, msg: "Error: " + (e.response?.data?.detail || e.message) }));
    }
  };

  const toggleReparo = async (n, satisfecho) => {
    const m = reparosModal;
    try {
      const r = await axios.patch(`${API}/api/estudio-titulo/reparos/${m.folder.id}/item/${n}`, { satisfecho });
      setReparosModal(prev => ({ ...prev, data: { ...prev.data, reparos: r.data.reparos } }));
    } catch (e) { alert("Error: " + (e.response?.data?.detail || e.message)); }
  };

  const declararReparos = async () => {
    const m = reparosModal;
    if (!window.confirm("¿Declarás que TODOS los reparos han sido recibidos satisfactoriamente y podemos continuar con el estudio de título?\n\nSe enviará un correo de aviso (en el mismo hilo) a ti, al vendedor y a Victoria Vilches.")) return;
    setReparosModal(prev => ({ ...prev, declarando: true, msg: "" }));
    try {
      const r = await axios.post(`${API}/api/estudio-titulo/reparos/${m.folder.id}/declarar`);
      setReparosModal(prev => ({ ...prev, declarando: false, data: { ...prev.data, reparos: r.data.reparos }, msg: "✅ Reparos declarados satisfechos. Aviso enviado por correo (tú + vendedor + Victoria)." }));
      loadFolders();
    } catch (e) {
      setReparosModal(prev => ({ ...prev, declarando: false, msg: "Error: " + (e.response?.data?.detail || e.message) }));
    }
  };

  const openEstudio = async (f) => {
    let archivos = [];
    let defaults = { destinatarios: ["contacto@hipotecariogestion.cl", "victoriavilches@centralmutuos.cl"], docs_usada: [] };
    let prefill = {};
    try {
      const pf = await axios.get(`${API}/api/clientes/folders/${f.id}/tasacion-prefill`, { timeout: 90000 });
      prefill = pf.data.prefill || {};
    } catch (_e) { /* best effort */ }
    try {
      const [r, d] = await Promise.all([
        axios.get(`${API}/api/clientes/folders/${f.id}`),
        axios.get(`${API}/api/estudio-titulo/defaults`),
      ]);
      archivos = (r.data.archivos || []).map(a => ({ ...a, sel: /carta|oferta|aprobaci/i.test(a.nombre) }))
        .sort((a, b) => (b.sel ? 1 : 0) - (a.sel ? 1 : 0));
      defaults = d.data;
    } catch (_e) { /* defaults */ }
    reloadBrokers();
    try {
      const p = await axios.get(`${API}/api/plantillas?tipo=estudio`);
      setEstudioPlantillas(p.data.plantillas || []);
    } catch (e) { console.error(e); }
    try {
      const c = await axios.get(`${API}/api/tasacion/contactos`);
      setTasacionContactos(c.data.contactos || []);
    } catch (e) { console.error(e); }
    setEstudioModal({
      folder: f, archivos,
      destinatarios: defaults.destinatarios.join(", "),
      cc: (f.estudio_titulo_cc || []).join(", "),
      tipo_vivienda: "nueva",
      docs_usada: defaults.docs_usada || [],
      docs_nueva: defaults.docs_nueva || [],
      inmobiliaria: f.datos_financieros?.inmobiliaria || prefill.inmobiliaria || "",
      inmo_contacto_nombre: "", inmo_contacto_email: "",
      vendedor_nombre: prefill.vendedor_nombre || "", vendedor_email: prefill.vendedor_email || "", vendedor_telefono: prefill.vendedor_telefono || "",
      intro: "",
      direccion: f.datos_financieros?.direccion || prefill.direccion || "", observaciones: "",
      docs_texto: (defaults.docs_nueva || []).join("\n"),
      preview: null, loading: false, msg: "",
    });
  };

  const guardarPlantillaEstudio = async () => {
    const m = estudioModal;
    const nombre = window.prompt("Nombre de la plantilla (ej: Vivienda usada — World Consultores):");
    if (!nombre) return;
    try {
      await axios.post(`${API}/api/plantillas`, { tipo: "estudio", nombre, data: {
        destinatarios: m.destinatarios, cc: m.cc || "", tipo_vivienda: m.tipo_vivienda,
        intro: m.intro, docs_texto: m.docs_texto, observaciones: m.observaciones } });
      const p = await axios.get(`${API}/api/plantillas?tipo=estudio`);
      setEstudioPlantillas(p.data.plantillas || []);
      setEstudioModal(prev => ({ ...prev, msg: `✅ Plantilla "${nombre}" guardada.` }));
    } catch (e) { setEstudioModal(prev => ({ ...prev, msg: "Error: " + (e.response?.data?.detail || e.message) })); }
  };

  const aplicarPlantillaEstudio = (pid) => {
    const p = estudioPlantillas.find(x => x.id === pid);
    if (!p) return;
    setEstudioModal(prev => ({ ...prev, ...p.data, preview: null, msg: `📋 Plantilla "${p.nombre}" aplicada.` }));
  };

  const eliminarPlantillaEstudio = async (pid) => {
    const p = estudioPlantillas.find(x => x.id === pid);
    if (!p || !window.confirm(`¿Eliminar la plantilla "${p.nombre}"?`)) return;
    try {
      await axios.delete(`${API}/api/plantillas/${pid}`);
      setEstudioPlantillas(prev => prev.filter(x => x.id !== pid));
    } catch (e) { alert("Error: " + (e.response?.data?.detail || e.message)); }
  };

  const estudioPayload = (m, confirm) => ({
    folder_id: m.folder.id, nombre: m.folder.nombre, rut: m.folder.rut || "",
    destinatarios: m.destinatarios, cc: m.cc || "", tipo_vivienda: m.tipo_vivienda,
    inmobiliaria: m.inmobiliaria,
    inmo_contacto_nombre: m.inmo_contacto_nombre, inmo_contacto_email: m.inmo_contacto_email,
    vendedor_nombre: m.vendedor_nombre, vendedor_email: m.vendedor_email,
    vendedor_telefono: m.vendedor_telefono, intro: m.intro,
    direccion: m.direccion,
    observaciones: m.observaciones,
    docs_lista: m.docs_texto.split("\n").map(s => s.trim()).filter(Boolean),
    attach_files: m.archivos.filter(a => a.sel).map(a => a.ruta),
    confirm,
  });

  const estudioPreview = async () => {
    setEstudioModal(m => ({ ...m, loading: true, msg: "" }));
    try {
      const r = await axios.post(`${API}/api/estudio-titulo/enviar`, estudioPayload(estudioModal, false));
      setEstudioModal(m => ({ ...m, preview: r.data, loading: false }));
    } catch (e) {
      setEstudioModal(m => ({ ...m, loading: false, msg: "Error: " + (e.response?.data?.detail || e.message) }));
    }
  };

  const estudioEnviar = async () => {
    if (!window.confirm(`¿Enviar la solicitud de estudio de títulos de ${estudioModal.folder.nombre} a: ${estudioModal.destinatarios}?`)) return;
    setEstudioModal(m => ({ ...m, loading: true, msg: "" }));
    try {
      const r = await axios.post(`${API}/api/estudio-titulo/enviar`, estudioPayload(estudioModal, true));
      setEstudioModal(m => ({ ...m, loading: false, msg: `✅ Solicitud enviada a ${r.data.to.join(", ")}` }));
      loadFolders();
    } catch (e) {
      setEstudioModal(m => ({ ...m, loading: false, msg: "Error: " + (e.response?.data?.detail || e.message) }));
    }
  };

  const enviarEtapa2 = async (m) => {
    setEstudioModal(prev => ({ ...prev, loading: true, msg: "" }));
    try {
      const pre = await axios.post(`${API}/api/estudio-titulo/etapa2/${m.folder.id}`, { confirm: false });
      const p = pre.data;
      setEstudioModal(prev => ({ ...prev, loading: false }));
      const to = window.prompt(
        `ETAPA 2 — Enviar los documentos recibidos al abogado (CC: ${(p.cc || []).join(", ")})\n\n` +
        `Asunto (mismo hilo): ${p.subject}\n\nAdjuntos (${p.attachments.length}):\n${p.attachments.map(a => `• ${a}`).join("\n")}\n\n` +
        `Confirmá o corregí el correo del abogado:`, p.to);
      if (!to) return;
      setEstudioModal(prev => ({ ...prev, loading: true }));
      const r = await axios.post(`${API}/api/estudio-titulo/etapa2/${m.folder.id}`, { confirm: true, to_addr: to.trim() });
      setEstudioModal(prev => ({ ...prev, loading: false, msg: `✅ Etapa 2: ${r.data.attachments.length} documento(s) del estudio enviados a ${r.data.to} (CC ${(r.data.cc || []).join(", ")}) — mismo hilo` }));
      loadFolders();
    } catch (e) {
      setEstudioModal(prev => ({ ...prev, loading: false, msg: "Error: " + (e.response?.data?.detail || e.message) }));
    }
  };

  const _buscarCorreosEstudio = async (m) => {
    setEstudioModal(prev => ({ ...prev, buscandoCorreos: true }));
    try {
      const r = await axios.get(`${API}/api/clientes/forzar/sugerencias`, { params: { q: m.folder.nombre }, timeout: 60000 });
      setEstudioModal(prev => ({ ...prev, buscandoCorreos: false, correosSug: (r.data.correos || []).map(c => ({ ...c, sel: false })) }));
    } catch (e) {
      setEstudioModal(prev => ({ ...prev, buscandoCorreos: false, msg: "Error buscando correos: " + (e.response?.data?.detail || e.message) }));
    }
  };

  const openEscritura = async (f) => {
    try {
      const n = await axios.get(`${API}/api/escritura/notarias`);
      setNotarias(n.data.notarias || []);
    } catch (_e) { setNotarias([]); }
    setEscrituraModal({
      folder: f, email_cliente: f.credit_request?.email_cliente || "",
      notaria_id: "", fecha: "", hora: "10:00",
      addNotaria: false, nn: { ciudad: "", nombre: "", direccion: "", email: "" },
      notaria_email_edit: "", preview: null, loading: false, msg: "",
    });
  };

  const reloadNotarias = async () => {
    try {
      const n = await axios.get(`${API}/api/escritura/notarias`);
      setNotarias(n.data.notarias || []);
      return n.data.notarias || [];
    } catch (_e) { return []; }
  };

  const escrituraPayload = (m, confirm) => ({
    folder_id: m.folder.id, nombre: m.folder.nombre, rut: m.folder.rut || "",
    email_cliente: m.email_cliente, notaria_id: m.notaria_id,
    fecha: m.fecha, hora: m.hora, base_url: window.location.origin, confirm,
  });

  const escrituraPreview = async () => {
    setEscrituraModal(m => ({ ...m, loading: true, msg: "" }));
    try {
      const r = await axios.post(`${API}/api/escritura/enviar`, escrituraPayload(escrituraModal, false));
      setEscrituraModal(m => ({ ...m, preview: r.data, loading: false }));
    } catch (e) {
      setEscrituraModal(m => ({ ...m, loading: false, msg: "Error: " + (e.response?.data?.detail || e.message) }));
    }
  };

  const escrituraEnviar = async () => {
    if (!window.confirm(`¿Enviar el aviso de firma de escritura a ${escrituraModal.email_cliente}?`)) return;
    setEscrituraModal(m => ({ ...m, loading: true, msg: "" }));
    try {
      const r = await axios.post(`${API}/api/escritura/enviar`, escrituraPayload(escrituraModal, true));
      setEscrituraModal(m => ({ ...m, loading: false, msg: `✅ Aviso enviado a ${r.data.to}. Cuando el cliente confirme, se avisará a la notaría y a Victoria, Daniela y Rodrigo.` }));
      loadFolders();
    } catch (e) {
      setEscrituraModal(m => ({ ...m, loading: false, msg: "Error: " + (e.response?.data?.detail || e.message) }));
    }
  };

  const escrituraAddNotaria = async () => {
    const m = escrituraModal;
    if (!m.nn.ciudad.trim() || !m.nn.direccion.trim()) return;
    try {
      const r = await axios.post(`${API}/api/escritura/notarias`, m.nn);
      await reloadNotarias();
      setEscrituraModal(prev => ({ ...prev, addNotaria: false, notaria_id: r.data.notaria.id, nn: { ciudad: "", nombre: "", direccion: "", email: "" } }));
    } catch (e) { console.error(e); }
  };

  const escrituraSaveNotariaEmail = async () => {
    const m = escrituraModal;
    if (!m.notaria_id || !m.notaria_email_edit.includes("@")) return;
    try {
      await axios.patch(`${API}/api/escritura/notarias/${m.notaria_id}`, { email: m.notaria_email_edit });
      await reloadNotarias();
      setEscrituraModal(prev => ({ ...prev, notaria_email_edit: "", msg: "✅ Correo de la notaría guardado" }));
    } catch (e) { console.error(e); }
  };
  const refreshUfFromSii = async () => {
    try {
      const r = await axios.get(`${API}/api/clientes/uf-actual?refresh=true`);
      setUfValue(r.data?.valor || 40842);
      alert(`UF actualizada desde ${r.data.source}: $${Number(r.data.valor).toLocaleString('es-CL')}` +
            (r.data.sii_day ? ` (día ${r.data.sii_day})` : "") +
            (r.data.error ? `\n\n⚠️ ${r.data.error}` : ""));
    } catch (e) { alert("Error: " + (e.response?.data?.detail || e.message)); }
  };
  const updateUf = async () => {
    const opt = window.confirm(
      `Valor actual UF: $${ufValue.toLocaleString('es-CL')}\n\n` +
      `Aceptar = Auto-actualizar desde SII.cl\nCancelar = Ingresar manualmente`
    );
    if (opt) return refreshUfFromSii();
    const v = prompt(`Ingresá el valor de la UF manualmente:`, String(ufValue));
    if (!v) return;
    const num = Number(v.replace(/\./g, "").replace(",", "."));
    if (isNaN(num) || num <= 0) return alert("Valor inválido");
    try {
      await axios.patch(`${API}/api/clientes/uf-actual`, { valor: num });
      setUfValue(num);
      alert(`UF actualizada manualmente a $${num.toLocaleString('es-CL')}`);
    } catch (e) { alert("Error: " + (e.response?.data?.detail || e.message)); }
  };

  const loadAjustes = async () => {
    try {
      const r = await axios.get(`${API}/api/clientes/ajustes`);
      setAjustes(r.data.folders || []);
      setView("ajustes");
    } catch (e) { alert("Error cargando Ajustes: " + (e.response?.data?.detail || e.message)); }
  };

  const startEdit = (folder) => {
    const cr = folder.credit_request || {};
    setEditingId(folder.id);
    setEditDraft({
      client_type: cr.client_type || "desconocido",
      subsidy_tipo: cr.subsidy?.tipo || "sin_subsidio",
      codeudor_has: !!cr.codeudor?.has_codeudor,
      codeudor_name: cr.codeudor?.name || "",
      is_request: !!cr.is_request,
    });
  };

  const cancelEdit = () => { setEditingId(null); setEditDraft({}); };

  const saveEdit = async (folderId) => {
    setSavingEdit(true);
    try {
      await axios.patch(`${API}/api/clientes/folders/${folderId}/clasificacion`, editDraft);
      await loadAjustes();
      cancelEdit();
    } catch (e) {
      alert("Error guardando: " + (e.response?.data?.detail || e.message));
    }
    setSavingEdit(false);
  };

  const resetEdit = async (folderId) => {
    if (!window.confirm("¿Volver a la clasificación automática y descartar los cambios manuales?")) return;
    try {
      await axios.patch(`${API}/api/clientes/folders/${folderId}/clasificacion`, { reset: true });
      await loadAjustes();
    } catch (e) {
      alert("Error reseteando: " + (e.response?.data?.detail || e.message));
    }
  };

  const calcularTecho = async (folder) => {
    setTechoBusy(true);
    try {
      const r = await axios.post(`${API}/api/clientes/folders/${folder.id}/techo-hipotecario`,
        { plazo_anos: 25 }, { timeout: 60000 });
      setTecho(r.data);
    } catch (e) {
      alert("❌ " + (e?.response?.data?.detail || e.message));
    }
    setTechoBusy(false);
  };

  const openFinPanel = async (folder) => {
    // Toggle: if the panel is already open for THIS folder, close it
    if (finOpenId === folder.id) {
      setFinOpenId(null);
      setFinDraft({});
      return;
    }
    // Fetch FIRST so the panel opens with data already populated (avoids empty flash)
    let df = {};
    try {
      const r = await axios.get(`${API}/api/clientes/folders/${folder.id}/datos-financieros`);
      df = r.data?.datos_financieros || {};
    } catch (e) {
      console.error("Error cargando datos financieros:", e);
    }
    setFinDraft({
      proyecto: df.proyecto || "",
      inmobiliaria: df.inmobiliaria || "",
      con_subsidio: df.con_subsidio ?? (folder.credit_request?.subsidy?.tipo === "con_subsidio"),
      tipo_propiedad: df.tipo_propiedad || "",
      valor_propiedad: df.valor_propiedad ?? "",
      monto_subsidio: df.monto_subsidio ?? "",
      ahorro: df.ahorro ?? "",
      monto_reserva: df.monto_reserva ?? "",
      monto_pie: df.monto_pie ?? "",
      monto_credito: df.monto_credito ?? "",
      fecha_entrega: df.fecha_entrega || "",
      notas: df.notas || "",
    });
    setFinOpenId(folder.id);
  };

  const closeFinPanel = () => { setFinOpenId(null); setFinDraft({}); };

  const saveFinPanel = async (folderId) => {
    setFinSaving(true);
    try {
      const payload = {};
      Object.keys(finDraft).forEach(k => {
        const v = finDraft[k];
        if (v !== "" && v !== null && v !== undefined) {
          if (["valor_propiedad","monto_subsidio","ahorro","monto_reserva","monto_pie","monto_credito"].includes(k)) {
            const n = Number(v);
            if (!Number.isNaN(n)) payload[k] = n;
          } else payload[k] = v;
        }
      });
      await axios.patch(`${API}/api/clientes/folders/${folderId}/datos-financieros`, payload);
      alert("Datos financieros guardados.");
      closeFinPanel();
      await loadAjustes();
    } catch (e) {
      alert("Error guardando: " + (e.response?.data?.detail || e.message));
    }
    setFinSaving(false);
  };

  const runOcrFin = async (folderId) => {
    setOcrRunning(true);
    try {
      const r = await axios.post(`${API}/api/clientes/folders/${folderId}/ocr-datos-financieros`);
      const ex = r.data?.extracted || {};
      setFinDraft(prev => ({
        ...prev,
        proyecto: ex.proyecto || prev.proyecto,
        inmobiliaria: ex.inmobiliaria || prev.inmobiliaria,
        con_subsidio: ex.con_subsidio ?? prev.con_subsidio,
        tipo_propiedad: ex.tipo_propiedad || prev.tipo_propiedad,
        valor_propiedad: ex.valor_propiedad ?? prev.valor_propiedad,
        monto_subsidio: ex.monto_subsidio ?? prev.monto_subsidio,
        ahorro: ex.ahorro ?? prev.ahorro,
        monto_reserva: ex.monto_reserva ?? prev.monto_reserva,
        monto_pie: ex.monto_pie ?? prev.monto_pie,
        monto_credito: ex.monto_credito ?? prev.monto_credito,
      }));
      alert(`OCR listo. Analizados ${r.data?.pdfs_analyzed?.length || 0} PDFs. Revisá los campos y guardá si están OK.`);
    } catch (e) {
      alert("Error en OCR: " + (e.response?.data?.detail || e.message));
    }
    setOcrRunning(false);
  };


  const loadFolders = async () => {
    try {
      const r = await axios.get(`${API}/api/clientes/folders`);
      setFolders(r.data.folders || []);
    } catch (err) { console.error("Load folders error:", err); }
  };

  const cloudSync = async () => {
    setSyncing(true);
    try {
      const r = await axios.post(`${API}/api/clientes/cloud-sync`, {}, { timeout: 120000 });
      const d = r.data;
      await loadFolders();
      setSyncMsg(`💎 Sync OK (${d.duracion_seg}s) · Mongo: ${d.mongo} · ${d.archivos_nuevos_descargados} archivo(s) nuevos del Cloud · respaldo ${d.respaldo} · ${d.total_en_bunker} protegidos · ${d.carpetas} carpetas`);
    } catch (e) {
      setSyncMsg("⚠ Error de sincronización: " + (e.response?.data?.detail || e.message));
    }
    setSyncing(false);
    setTimeout(() => setSyncMsg(""), 12000);
  };

  const toggleEnvioManual = async (folder) => {
    try {
      await axios.patch(`${API}/api/clientes/folders/${folder.id}/envio-manual`, { enviado: !(folder.envio_manual === true) });
      setFolders(prev => prev.map(x => x.id === folder.id ? { ...x, envio_manual: !(folder.envio_manual === true) } : x));
    } catch (err) { console.error("toggle envio manual error:", err); }
  };


  const createFolder = async () => {
    if (!newFolder.nombre.trim()) return;
    setLoading(true);
    try {
      await axios.post(`${API}/api/clientes/folders`, newFolder);
      setNewFolder({ nombre: "", rut: "", codeudor_nombre: "", codeudor_rut: "" });
      setShowCreate(false);
      await loadFolders();
    } catch (err) { alert("Error creando carpeta"); }
    setLoading(false);
  };

  const openFolder = async (folderId, autoAction) => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/clientes/folders/${folderId}`);
      setCurrentFolder(r.data);
      setView("detail");
      // Acción automática al abrir (usado por "🚀 Enviar Ya" desde la tarjeta)
      if (autoAction === "email") {
        setTimeout(() => openEmailModal(r.data), 500);
      }
    } catch (err) { alert("Error abriendo carpeta"); }
    setLoading(false);
  };

  const handleManualUpload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length || !currentFolder) return;
    setUploadingManual(true);
    let okCount = 0;
    const errors = [];
    for (const file of files) {
      try {
        const fd = new FormData();
        fd.append("file", file);
        // subfolder queda vacío → el clasificador lo pondrá en la subcarpeta correcta
        // en un pipeline futuro. Por ahora va a la raíz de la carpeta.
        await axios.post(`${API}/api/clientes/folders/${currentFolder.id}/upload-file`, fd, {
          headers: { "Content-Type": "multipart/form-data" },
          timeout: 120000,
        });
        okCount += 1;
      } catch (err) {
        errors.push(`${file.name}: ${err.response?.data?.detail || err.message}`);
      }
    }
    setUploadingManual(false);
    e.target.value = ""; // reset input
    // Reload folder detail (background merge se dispara automáticamente en backend)
    try {
      const r = await axios.get(`${API}/api/clientes/folders/${currentFolder.id}`);
      setCurrentFolder(r.data);
      await loadFolders();
    } catch (e) { console.error(e); }
    if (errors.length) {
      alert(`✅ Subidos: ${okCount}\n\n❌ Errores:\n${errors.join("\n")}\n\n🔄 El COMBINADO_PROTOCOLO se está regenerando en background (aparecerá en unos segundos).`);
    } else {
      alert(`✅ Se subieron ${okCount} archivo(s) a la carpeta de ${currentFolder.nombre}.\n\n🔄 El COMBINADO_PROTOCOLO se está regenerando automáticamente en background. Refrescá en unos segundos para verlo.`);
    }
  };

  const regenerateCombined = async () => {
    if (!currentFolder) return;
    if (!window.confirm("Regenerar el archivo combinado con el orden protocolo?\n\nEsto reemplazará cualquier COMBINADO_PROTOCOLO existente.")) return;
    setMergingProto(currentFolder.id);
    try {
      const r = await axios.post(`${API}/api/clientes/folders/${currentFolder.id}/merge-protocol`, { include_extras: true }, { timeout: 180000 });
      const detail = await axios.get(`${API}/api/clientes/folders/${currentFolder.id}`);
      setCurrentFolder(detail.data);
      alert(`✅ Combinado regenerado.\n\nArchivo: ${r.data.merged_file}\nArchivos incluidos: ${(r.data.files_used || []).length}\nOrden: ${(r.data.protocol_order || []).join(" → ")}`);
    } catch (err) {
      alert("❌ Error regenerando combinado: " + (err.response?.data?.detail || err.message));
    }
    setMergingProto(null);
  };

  const deleteFolder = async (folderId) => {
    if (!window.confirm("¿Eliminar esta carpeta y todos sus archivos?")) return;
    try {
      await axios.delete(`${API}/api/clientes/folders/${folderId}`);
      await loadFolders();
    } catch (err) { alert("Error eliminando carpeta"); }
  };

  const loadEmails = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/clientes/emails?max_results=30`);
      setEmails(r.data.emails || []);
      setView("emails");
      if (r.data.busy && (r.data.emails || []).length === 0) {
        alert("Gmail está ocupado leyendo correos en segundo plano. Intenta de nuevo en 1-2 minutos.");
      }
    } catch (err) { alert("Error cargando correos. Verifique las credenciales."); }
    setLoading(false);
  };

  const searchEmails = async () => {
    if (!emailSearch.trim()) return;
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/clientes/emails/search?q=${encodeURIComponent(emailSearch)}`);
      setEmailResults(r.data.results || []);
    } catch (err) { alert("Error buscando correos"); }
    setLoading(false);
  };

  const saveAttachmentToFolder = async (emailId, filename) => {
    if (!currentFolder) return alert("Primero abra una carpeta de cliente");
    setSavingAttachment(`${emailId}-${filename}`);
    try {
      await axios.post(`${API}/api/clientes/save-attachment`, {
        email_id: emailId, filename, folder_id: currentFolder.id,
      });
      alert(`Adjunto "${filename}" guardado en carpeta ${currentFolder.nombre}`);
      // Reload folder
      const r = await axios.get(`${API}/api/clientes/folders/${currentFolder.id}`);
      setCurrentFolder(r.data);
    } catch (err) { alert("Error guardando adjunto"); }
    setSavingAttachment("");
  };

  const [codeudorModal, setCodeudorModal] = useState(null);
  const [codeudorForm, setCodeudorForm] = useState({ nombre: "", rut: "" });

  const agregarCodeudor = (f) => {
    setCodeudorForm({ nombre: f?.codeudor_nombre || "", rut: f?.codeudor_rut || "" });
    setCodeudorModal(f);
  };

  const guardarCodeudor = async () => {
    const nombre = codeudorForm.nombre.trim();
    const rut = codeudorForm.rut.trim();
    if (nombre.length < 3) { alert("Indica el nombre del codeudor"); return; }
    if (rut.replace(/[^0-9kK]/g, "").length < 7) { alert("El RUT del codeudor es obligatorio (ej: 12.345.678-9)"); return; }
    try {
      await axios.post(`${API}/api/clientes/folders/${codeudorModal.id}/codeudor`, { nombre, rut });
      setCodeudorModal(null);
      loadFolders();
      if (currentFolder?.id === codeudorModal.id) {
        setCurrentFolder({ ...currentFolder, codeudor_nombre: nombre, codeudor_rut: rut });
      }
      alert(`Codeudor vinculado: ${nombre} (${rut}).\nLos documentos que lleguen con este RUT irán directo a la subcarpeta 05_Codeudor.`);
    } catch (e) {
      alert(e?.response?.data?.detail || "No se pudo guardar el codeudor");
    }
  };

  const saveAllAttachments = async () => {
    if (!currentFolder) return;
    const name = prompt("Nombre de la persona para buscar adjuntos:");
    if (!name) return;
    setLoading(true);
    try {
      const start = await axios.post(`${API}/api/clientes/save-all-attachments`, {
        person_name: name, folder_id: currentFolder.id,
      });
      const jobId = start.data.job_id;
      // Poll hasta que el trabajo en background termine (máx ~3 min)
      let job = { status: "running" };
      for (let i = 0; i < 60 && job.status === "running"; i++) {
        await new Promise(res => setTimeout(res, 3000));
        const st = await axios.get(`${API}/api/clientes/save-all-attachments/${jobId}`);
        job = st.data;
      }
      if (job.status === "error") {
        alert("Error buscando adjuntos: " + (job.error || "desconocido"));
      } else if (job.status === "running") {
        alert("La búsqueda sigue en segundo plano. Refrescá la carpeta en unos minutos.");
      } else {
        alert(`Se encontraron ${job.total_found} adjuntos. Se guardaron ${job.total_saved}.`);
      }
      const reload = await axios.get(`${API}/api/clientes/folders/${currentFolder.id}`);
      setCurrentFolder(reload.data);
    } catch (err) { alert("Error buscando/guardando adjuntos"); }
    setLoading(false);
  };

  const downloadFile = (folderId, filePath) => {
    window.open(`${API}/api/clientes/folders/${folderId}/download/${filePath}`, "_blank");
  };

  const openPreview = (folderId, filePath, fileName) => {
    const url = `${API}/api/clientes/folders/${folderId}/download/${encodeURI(filePath)}?inline=true`;
    const ext = (fileName || "").toLowerCase().split(".").pop();
    const mime = ext === "pdf" ? "pdf" :
                 ["png","jpg","jpeg","gif","webp"].includes(ext) ? "image" :
                 ["txt"].includes(ext) ? "text" : "other";
    setPreviewFile({ url, name: fileName, mime });
  };

  const closePreview = () => setPreviewFile(null);

  // ---------- File Selection ----------
  const toggleSelect = (folderId, relPath) => {
    setSelectedFiles(prev => {
      const cur = new Set(prev[folderId] || []);
      if (cur.has(relPath)) cur.delete(relPath); else cur.add(relPath);
      return { ...prev, [folderId]: cur };
    });
  };
  const isSelected = (folderId, relPath) => (selectedFiles[folderId] || new Set()).has(relPath);
  const selectionCount = (folderId) => (selectedFiles[folderId] || new Set()).size;
  const clearSelection = (folderId) => setSelectedFiles(prev => ({ ...prev, [folderId]: new Set() }));

  // ---------- Manual Upload ----------
  const triggerUpload = (folderId, subfolder = "") => {
    uploadCtxRef.current = { folderId, subfolder };
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
      fileInputRef.current.click();
    }
  };

  const handleFileSelected = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !uploadCtxRef.current) return;
    const { folderId, subfolder } = uploadCtxRef.current;
    setUploadingFor(folderId);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("subfolder", subfolder || "");
      await axios.post(`${API}/api/clientes/folders/${folderId}/upload-file`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      await loadAjustes();
    } catch (err) {
      alert("Error subiendo archivo: " + (err.response?.data?.detail || err.message));
    }
    setUploadingFor(null);
    uploadCtxRef.current = null;
  };

  // ---------- Delete File ----------
  const deleteClientFile = async (folderId, relPath) => {
    if (!window.confirm(`¿Eliminar el archivo "${relPath}"? Esta acción no se puede deshacer.`)) return;
    try {
      await axios.post(`${API}/api/clientes/folders/${folderId}/delete-file`, { file_path: relPath });
      // Remove from selection if selected
      setSelectedFiles(prev => {
        const cur = new Set(prev[folderId] || []); cur.delete(relPath);
        return { ...prev, [folderId]: cur };
      });
      await loadAjustes();
    } catch (err) {
      alert("Error eliminando archivo: " + (err.response?.data?.detail || err.message));
    }
  };

  // ---------- Merge PDFs ----------
  const mergeSelected = async (folderId) => {
    const files = Array.from(selectedFiles[folderId] || []);
    if (files.length < 1) { alert("Seleccioná al menos un archivo PDF."); return; }
    const nonPdf = files.filter(f => !f.toLowerCase().endsWith(".pdf"));
    if (nonPdf.length > 0) {
      if (!window.confirm(`Los siguientes archivos NO son PDF y serán ignorados:\n${nonPdf.join("\n")}\n\n¿Continuar?`)) return;
    }
    setMerging(true);
    try {
      const r = await axios.post(`${API}/api/clientes/folders/${folderId}/merge-pdfs`, { files });
      alert(`✅ PDFs combinados: ${r.data.merged_file}\nGuardado en 00_combinados/\nArchivos usados: ${r.data.files_used.length}` + (r.data.errors?.length ? `\nErrores: ${r.data.errors.length}` : ""));
      clearSelection(folderId);
      await loadAjustes();
    } catch (err) {
      alert("Error combinando PDFs: " + (err.response?.data?.detail || err.message));
    }
    setMerging(false);
  };

  // ---------- Split Bundled PDF ----------
  const splitBundled = async (folderId, relPath, fileName) => {
    const looksCodeudor = /codeudor|co-?deudor|aval/i.test(fileName + relPath);
    const routeCodeudor = looksCodeudor
      ? true
      : window.confirm(`¿"${fileName}" pertenece al CODEUDOR?\n\n(Aceptar = codeudor, Cancelar = titular)`);
    const delOriginal = window.confirm(
      `Se va a dividir "${fileName}" en archivos individuales por categoría usando IA.\n\n` +
      `¿Eliminar el PDF empaquetado ORIGINAL después de dividirlo?\n\n` +
      `Aceptar = eliminar original\nCancelar = conservar original (aparecerá junto a los individuales)`
    );
    setSplittingRel(relPath);
    try {
      const r = await axios.post(`${API}/api/clientes/folders/${folderId}/split-bundled`, {
        file_path: relPath,
        route_to_codeudor: routeCodeudor,
        delete_original: delOriginal,
      });
      const w = r.data.written || [];
      alert(
        `✅ PDF dividido en ${r.data.n_groups} archivos (${r.data.n_pages} páginas totales).\n\n` +
        w.map(f => `  · [${f.category}] ${f.rel} (pág ${f.pages.join(", ")})`).join("\n") +
        (r.data.deleted_original ? "\n\n✂️ Original eliminado." : "")
      );
      await loadAjustes();
    } catch (err) {
      alert("Error dividiendo: " + (err.response?.data?.detail || err.message));
    }
    setSplittingRel(null);
  };

  // ---------- Merge PDFs by Protocol ----------
  const mergeByProtocol = async (folder) => {
    const cr = folder.credit_request || {};
    const clientType = cr.client_type || "dependiente";
    const protoOrder = clientType === "independiente"
      ? "Cédula → Impuesto Renta → Boletas Año Anterior → Boletas Año Actual → CMF → Extras"
      : "Cédula → Liquidaciones → AFP → CMF → Extras";
    if (!window.confirm(
      `Combinar TODOS los PDFs del cliente siguiendo el protocolo (${clientType}):\n\n${protoOrder}\n\n` +
      `Se ignoran los PDFs combinados anteriores. ¿Continuar?`
    )) return;
    setMergingProto(folder.id);
    try {
      const r = await axios.post(`${API}/api/clientes/folders/${folder.id}/merge-protocol`, {
        include_extras: true,
      });
      const used = r.data.files_used || [];
      const errs = r.data.errors || [];
      alert(
        `✅ Combinado por protocolo (${r.data.client_type}):\n${r.data.merged_file}\n\n` +
        `Archivos incluidos: ${used.length}\n` +
        used.map(u => `  · [${u.cat}] ${u.rel}`).join("\n") +
        (errs.length ? `\n\nErrores: ${errs.length}` : "")
      );
      await loadAjustes();
    } catch (err) {
      alert("Error combinando por protocolo: " + (err.response?.data?.detail || err.message));
    }
    setMergingProto(null);
  };

  // ---------- Send Email ----------
  const [autocorreoDest, setAutocorreoDest] = useState("");
  useEffect(() => {
    axios.get(`${API}/api/clientes/autocorreo-dest`)
      .then(r => setAutocorreoDest(r.data?.destination || ""))
      .catch((e) => console.error(e));
  }, []);

  const openEmailModal = (folder) => {
    // REGLA INVIOLABLE: destinatario siempre = AUTOCORREO_DEST del backend.
    // Ignoramos source_email para prevenir envíos accidentales a bancos.
    const defaultTo = autocorreoDest || "";
    setEmailModal({
      folder,
      to: defaultTo,
      subject: "",
      subject_extra: "",
      ejecutivo_externo: folder.ejecutivo_externo || "",
      extra: "",
      ejecutivo: folder.ejecutivo_interno || "",
      sending: false,
      include_merged: true,
      include_codeudor_merged: !!folder.codeudor_nombre,
      attach_selected: selectionCount(folder.id) > 0,
    });
    // Auto-generate preview inmediatamente
    if (defaultTo && defaultTo.includes("@")) {
      setTimeout(() => {
        (async () => {
          try {
            const r = await axios.post(`${API}/api/clientes/folders/${folder.id}/send-email`,
              { to_addr: defaultTo, include_merged: true, include_codeudor_merged: !!folder.codeudor_nombre, confirm: false });
            setEmailModal(prev => prev && prev.folder.id === folder.id
              ? { ...prev, preview: r.data }
              : prev);
          } catch (err) {
            console.error("Auto-preview fallo:", err);
          }
        })();
      }, 300);
    }
  };
  const closeEmailModal = () => setEmailModal(null);
  const buildEmailPayload = (em) => {
    const p = {
      to_addr: em.to,
      subject_extra: em.subject_extra || "",
      body_extra: em.extra || "",
      include_merged: !!em.include_merged,
      include_codeudor_merged: !!em.include_codeudor_merged,
    };
    if (em.attach_selected) {
      p.attach_files = Array.from(selectedFiles[em.folder.id] || []);
    }
    if (em.editBody != null) p.body_html = em.editBody;
    if (em.ejecutivo) p.ejecutivo_interno = em.ejecutivo;
    if (em.ejecutivo_externo) p.ejecutivo_externo = em.ejecutivo_externo;
    if (em.force_incompleto) p.force_incompleto = true;
    return p;
  };

  const previewClientEmail = async () => {
    if (!emailModal) return;
    const em = emailModal;
    if (!em.to || !em.to.includes("@")) {
      alert("⚠️ Falta el destinatario.\n\nCompletá el campo 'Destinatario' con un correo válido (ej: banco@ejemplo.cl) antes de generar el preview.");
      return;
    }
    setEmailModal({ ...em, sending: true, preview: null });
    try {
      const r = await axios.post(`${API}/api/clientes/folders/${em.folder.id}/send-email`,
        { ...buildEmailPayload(em), confirm: false });
      setEmailModal({ ...em, sending: false, preview: r.data });
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || "Error desconocido";
      alert("❌ No se pudo generar el preview:\n\n" + detail + "\n\nRevisá tu conexión y volvé a intentar.");
      setEmailModal({ ...em, sending: false });
    }
  };

  const confirmSendClientEmail = async () => {
    if (!emailModal || !emailModal.preview) return;
    const em = emailModal;
    // HARD GUARD: documentación incompleta requiere asunción manual
    const md = em.preview?.missing_docs || [];
    if (md.length > 0 && !em.force_incompleto) {
      alert(`🚫 ENVÍO BLOQUEADO — Documentación incompleta\n\nFaltan: ${md.join(", ")}\n\nPara enviar igual, marcá "Asumo el envío manual con documentación incompleta" en el preview.`);
      return;
    }
    // HARD GUARD: SIN subsidio → crédito no puede superar el 80% del valor propiedad
    const df = em.folder.datos_financieros || {};
    const conSub = df.con_subsidio ?? (em.folder.credit_request?.subsidy?.tipo === "con_subsidio");
    const vp = Number(df.valor_propiedad || 0);
    const mc = Number(df.monto_credito || 0);
    if (!conSub && vp > 0 && mc > 0) {
      const max80 = vp * 0.8;
      if (mc > max80 + 0.01) {
        const pct = (mc / vp) * 100;
        alert(
          `🚫 ENVÍO BLOQUEADO\n\n` +
          `El crédito ${mc.toFixed(2)} UF supera el 80% máximo permitido para operaciones SIN subsidio.\n\n` +
          `Máximo permitido: ${max80.toFixed(2)} UF (80% de ${vp.toFixed(2)} UF)\n` +
          `Actual: ${pct.toFixed(1)}% del valor propiedad\n\n` +
          `Ajustá el crédito o cambiá a CON subsidio antes de enviar.`
        );
        return;
      }
    }
    // AVISO auto-envío: Gmail no muestra los correos en Bandeja de Entrada
    // cuando remitente = destinatario. Sólo aparecen en "Enviados".
    const senderEmail = (em.preview?.sender || "").toLowerCase().trim();
    const toEmail = (em.to || "").toLowerCase().trim();
    if (senderEmail && toEmail && senderEmail === toEmail) {
      const cont = window.confirm(
        `⚠️ Estás enviándote un correo A VOS MISMO\n\n` +
        `Remitente: ${senderEmail}\n` +
        `Destinatario: ${toEmail}\n\n` +
        `Gmail y Google Workspace NO muestran los auto-envíos en tu Bandeja de Entrada — ` +
        `solamente aparecen en la carpeta "Enviados". Por eso pensás que no llegan.\n\n` +
        `¿Continuar de todas formas? (revisá "Enviados" luego para verlo)`
      );
      if (!cont) return;
    }
    if (!window.confirm(`¿Enviar correo a ${em.to}?\n\nEsta acción no se puede deshacer.`)) return;
    setEmailModal({ ...em, sending: true });
    try {
      const r = await axios.post(`${API}/api/clientes/folders/${em.folder.id}/send-email`,
        { ...buildEmailPayload(em), confirm: true });
      const isSelfSend = (r.data.sender || "").toLowerCase().trim() === (r.data.to || "").toLowerCase().trim();
      const suffix = isSelfSend
        ? `\n\n📥 AUTO-ENVÍO: revisá la carpeta "Enviados" de Gmail (no aparece en Bandeja de Entrada porque enviaste a tu propia dirección).`
        : "";
      alert(`✅ Correo enviado a ${r.data.to}\nAdjuntos: ${r.data.attachments.length}\nDesde: ${r.data.sender}${suffix}`);
      closeEmailModal();
    } catch (err) {
      const det = err.response?.data?.detail || err.message;
      if (err.response?.status === 403 && String(det).toLowerCase().includes("clave")) {
        const clave = window.prompt(det + "\n\nIngresa la CLAVE de administrador para autorizar el REENVÍO:");
        if (clave) {
          try {
            const r2 = await axios.post(`${API}/api/clientes/folders/${em.folder.id}/send-email`,
              { ...buildEmailPayload(em), confirm: true, clave });
            alert(`✅ Correo REENVIADO a ${r2.data.to} (autorizado con clave)\nAdjuntos: ${r2.data.attachments.length}`);
            closeEmailModal();
            return;
          } catch (e2) {
            alert("Error: " + (e2.response?.data?.detail || e2.message));
          }
        }
        setEmailModal({ ...em, sending: false });
        return;
      }
      alert("Error enviando correo: " + det);
      setEmailModal({ ...em, sending: false });
    }
  };

  // ---------- Missing Docs Modal ----------
  const openMissingDocsModal = async (folder) => {
    setMissingDocsModal({ folder, to: "", extra: "", preview: null, sending: true });
    try {
      const r = await axios.post(`${API}/api/clientes/folders/${folder.id}/send-missing-docs`,
        { confirm: false });
      setMissingDocsModal({ folder, to: r.data.to, extra: "", preview: r.data, sending: false });
    } catch (err) {
      alert("Error generando preview: " + (err.response?.data?.detail || err.message));
      setMissingDocsModal(null);
    }
  };
  const closeMissingDocsModal = () => setMissingDocsModal(null);
  const refreshMissingDocsPreview = async () => {
    if (!missingDocsModal) return;
    setMissingDocsModal({ ...missingDocsModal, sending: true });
    try {
      const r = await axios.post(`${API}/api/clientes/folders/${missingDocsModal.folder.id}/send-missing-docs`,
        { confirm: false, to_addr: missingDocsModal.to, body_extra: missingDocsModal.extra });
      setMissingDocsModal({ ...missingDocsModal, preview: r.data, sending: false });
    } catch (err) {
      alert("Error: " + (err.response?.data?.detail || err.message));
      setMissingDocsModal({ ...missingDocsModal, sending: false });
    }
  };
  const confirmSendMissingDocs = async () => {
    if (!missingDocsModal || !missingDocsModal.preview) return;
    const m = missingDocsModal;
    if (!m.to || !m.to.includes("@")) { alert("Destinatario inválido"); return; }
    if (!window.confirm(`¿Enviar correo de documentos faltantes a ${m.to}?`)) return;
    setMissingDocsModal({ ...m, sending: true });
    try {
      const r = await axios.post(`${API}/api/clientes/folders/${m.folder.id}/send-missing-docs`,
        { confirm: true, to_addr: m.to, body_extra: m.extra });
      alert(`✅ Correo enviado a ${r.data.to}\nAsunto: ${r.data.subject}\nDocs faltantes: ${r.data.missing.length}`);
      closeMissingDocsModal();
    } catch (err) {
      alert("Error enviando: " + (err.response?.data?.detail || err.message));
      setMissingDocsModal({ ...m, sending: false });
    }
  };

  const toggleEscrituracion = async (f) => {
    const activar = !f.is_escrituracion;
    if (!window.confirm(activar
      ? `⚖️ ENVIAR A ESCRITURACIÓN\n\n¿Enviar la ficha de ${f.nombre} a Escrituración?\n\nSe activará también en los módulos Set de Crédito y Títulos, con las reglas de firma vigentes.`
      : `¿Devolver la carpeta de ${f.nombre} a Solicitudes de Crédito?`)) return;
    try {
      if (activar) {
        const r = await axios.post(`${API}/api/clientes/folders/${f.id}/enviar-escrituracion`, {});
        alert(r.data.mensaje || "⚖️ Ficha enviada a Escrituración");
      } else {
        await axios.post(`${API}/api/clientes/folders/${f.id}/escrituracion`, { activar });
      }
      loadFolders();
    } catch (e) { alert("Error: " + (e.response?.data?.detail || e.message)); }
  };

  const enriquecerCarpeta = async (f, modo, messageIds) => {
    setEnriching(f.id + modo);
    try {
      const r = await axios.post(`${API}/api/clientes/folders/${f.id}/enriquecer`, { modo, message_ids: messageIds || [] }, { timeout: 180000 });
      const nuevos = r.data.archivos_nuevos || [];
      const lista = nuevos.map(a => `• ${a.archivo}`).join("\n");
      alert(`🔎 Enriquecer archivos — ${modo === "estudio" ? "Estudio de Título" : "Solicitud de Crédito"}\n\nCorreos revisados: ${r.data.correos_revisados}\nArchivos nuevos: ${nuevos.length}${lista ? "\n\n" + lista : "\n\n(No se encontraron documentos nuevos en el correo)"}`);
      loadFolders();
    } catch (e) { alert("Error: " + (e.response?.data?.detail || e.message)); }
    setEnriching(null);
  };

  // Sugerencias en vivo al escribir el nombre en Forzar Carpeta
  useEffect(() => {
    if (!forzarModal || (forzarModal.nombre || "").trim().length < 3) return;
    const q = forzarModal.nombre.trim();
    const t = setTimeout(async () => {
      setForzarModal(prev => prev ? { ...prev, buscando: true } : prev);
      try {
        const r = await axios.get(`${API}/api/clientes/forzar/sugerencias`, { params: { q }, timeout: 60000 });
        setForzarModal(prev => (prev && prev.nombre.trim() === q) ? { ...prev, sug: r.data, buscando: false } : prev);
      } catch {
        setForzarModal(prev => prev ? { ...prev, buscando: false } : prev);
      }
    }, 700);
    return () => clearTimeout(t);
  }, [forzarModal?.nombre]); // eslint-disable-line react-hooks/exhaustive-deps

  const ejecutarForzar = async () => {
    const m = forzarModal;
    if (!m || (!m.nombre.trim() && !m.rut.trim())) return;
    const clave = window.prompt("Ingresa la CLAVE de administrador:");
    if (!clave) return;
    setForzarModal(prev => ({ ...prev, forzando: true, msg: "" }));
    const mids = ((m.sug || {}).correos || []).filter(c => c.sel && c.message_id).map(c => c.message_id);
    try {
      const r = await axios.post(`${API}/api/clientes/folders/forzar`, { nombre: m.nombre.trim(), rut: m.rut.trim(), clave, message_ids: mids }, { timeout: 55000 });
      const jobId = r.data.job_id;
      setForzarModal(prev => ({ ...prev, msg: "⏳ Buscando en el correo y descargando adjuntos… (puede tardar 1-2 minutos, no cierres esta ventana)" }));
      let res = null;
      for (let i = 0; i < 120; i++) {
        await new Promise(s => setTimeout(s, 3000));
        const j = await axios.get(`${API}/api/jobs/${jobId}`, { timeout: 30000 });
        if (j.data.estado === "listo") { res = j.data.resultado; break; }
        if (j.data.estado === "error") throw new Error(j.data.error || "Error en la búsqueda");
      }
      if (!res) throw new Error("La búsqueda sigue en curso — revisá la carpeta en unos minutos");
      const imap = res.archivos_imap || [];
      const ver = res.verificacion_cedula;
      setForzarModal(prev => ({ ...prev, forzando: false,
        msg: `✅ Carpeta: ${res.carpeta} · Correos: ${res.correos_encontrados} · Adjuntos descargados: ${imap.length}${ver && Object.keys(ver.cambios || {}).length ? ` · 🪪 Corregido con cédula: ${Object.entries(ver.cambios).map(([k, v]) => `${k}→${v}`).join(", ")}` : ""}` }));
      loadFolders();
    } catch (e) {
      setForzarModal(prev => ({ ...prev, forzando: false, msg: "Error: " + (e.response?.data?.detail || e.message) }));
    }
  };

  const downloadAll = (folderId) => {
    window.open(`${API}/api/clientes/folders/${folderId}/download-all`, "_blank");
  };

  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
  };

  const filtered = folders.filter(f =>
    (!searchQuery || f.nombre.toLowerCase().includes(searchQuery.toLowerCase())) &&
    (folderTab === "escrituracion" ? !!f.is_escrituracion : !f.is_escrituracion)
  );
  const countEscrituracion = folders.filter(f => !!f.is_escrituracion).length;
  const countClientes = folders.length - countEscrituracion;

  return (
    <div className="clientes-module" data-testid="clientes-module">

      {/* LIST VIEW */}
      {view === "list" && (
        <div data-testid="clientes-list">
          <div className="clientes-toolbar">
            <div className="clientes-search">
              <i className="fa fa-search"></i>
              <input type="text" placeholder="Buscar cliente..." value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)} data-testid="clientes-search" />
            </div>
            <div className="clientes-toolbar-actions">
              <button className="docs-btn" data-testid="btn-cloud-sync" onClick={cloudSync} disabled={syncing}
                title="Para sincronizar cambios de diseño o nuevas funciones, use el botón Re-publish de la plataforma"
                style={{ background: "linear-gradient(135deg, #BF953F, #FCF6BA, #B38728)", color: "#0a0a0a", fontWeight: 800, border: "none", borderRadius: 0, opacity: syncing ? 0.6 : 1 }}>
                <i className={`fa ${syncing ? "fa-spinner fa-spin" : "fa-gem"}`}></i> {syncing ? "Sincronizando…" : "💎 Sincronizar Datos (Cloud Sync)"}
              </button>
              <span data-testid="cloud-sync-status"
                title="Para sincronizar cambios de diseño o nuevas funciones, use el botón Re-publish de la plataforma"
                style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: "0.72rem", fontWeight: 700, letterSpacing: "0.5px", color: "#10d98e", border: "1px solid rgba(16,217,142,0.35)", padding: "0.35rem 0.7rem", cursor: "help" }}>
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#10d98e", boxShadow: "0 0 6px #10d98e" }}></span>
                Sincronización: {window.location.hostname.includes("preview") ? "Preview" : "Live"} · Conexión Protegida
              </span>
              <button className="docs-btn secondary" onClick={loadEmails} data-testid="btn-view-emails">
                <i className="fa fa-envelope"></i> Ver Correos
              </button>
              <button className="docs-btn secondary" onClick={loadAjustes} data-testid="btn-ajustes">
                <i className="fa fa-sliders"></i> Ajustes
              </button>
              <button className="docs-btn primary" onClick={() => setShowCreate(true)} data-testid="btn-new-folder">
                <i className="fa fa-plus"></i> Nueva Carpeta
              </button>
              <button className="docs-btn secondary" data-testid="btn-forzar-folder"
                onClick={() => setForzarModal({ nombre: "", rut: "", sug: null, buscando: false, forzando: false, msg: "" })}
                style={{ borderColor: "#f59e0b", color: "#f59e0b" }}>
                <i className="fa fa-bolt"></i> Forzar Carpeta
              </button>
            </div>
          </div>

          {syncMsg && (
            <div data-testid="cloud-sync-msg" style={{ margin: "0.6rem 0 0", padding: "0.55rem 0.9rem", fontSize: "0.8rem", fontWeight: 600, background: syncMsg.startsWith("💎") ? "rgba(212,175,55,0.12)" : "rgba(225,29,72,0.12)", border: `1px solid ${syncMsg.startsWith("💎") ? "rgba(212,175,55,0.4)" : "rgba(225,29,72,0.4)"}`, color: syncMsg.startsWith("💎") ? "#d4af37" : "#ff6b8a" }}>
              {syncMsg}
            </div>
          )}

          <div data-testid="folder-tabs" style={{ display: "flex", gap: 8, margin: "0.9rem 0" }}>
            <button data-testid="tab-clientes" onClick={() => setFolderTab("clientes")}
              style={{ padding: "0.55rem 1.2rem", borderRadius: 0, fontWeight: 800, fontSize: 13, cursor: "pointer",
                background: folderTab === "clientes" ? "rgba(212,175,55,0.18)" : "rgba(148,163,184,0.08)",
                border: folderTab === "clientes" ? "2px solid var(--gold, #d4af37)" : "1.5px solid rgba(148,163,184,0.3)",
                color: folderTab === "clientes" ? "var(--gold, #d4af37)" : "#94a3b8" }}>
              <i className="fa fa-folder"></i> Solicitudes de Crédito ({countClientes})
            </button>
            <button data-testid="tab-escrituracion" onClick={() => setFolderTab("escrituracion")}
              style={{ padding: "0.55rem 1.2rem", borderRadius: 0, fontWeight: 800, fontSize: 13, cursor: "pointer",
                background: folderTab === "escrituracion" ? "rgba(46,92,230,0.18)" : "rgba(148,163,184,0.08)",
                border: folderTab === "escrituracion" ? "2px solid #2e5ce6" : "1.5px solid rgba(148,163,184,0.3)",
                color: folderTab === "escrituracion" ? "#2e5ce6" : "#94a3b8" }}>
              <i className="fa fa-pencil-square"></i> Escrituración ({countEscrituracion})
            </button>
          </div>

          {showCreate && (
            <div className="clientes-create-form" data-testid="create-folder-form">
              <h4>Nueva Carpeta de Cliente</h4>
              <div className="clientes-form-grid">
                <div className="clientes-field">
                  <label>Nombre del Cliente *</label>
                  <input type="text" value={newFolder.nombre} onChange={e => setNewFolder({ ...newFolder, nombre: e.target.value })}
                    placeholder="Ej: Juan Pérez" data-testid="input-folder-nombre" />
                </div>
                <div className="clientes-field">
                  <label>RUT</label>
                  <input type="text" value={newFolder.rut} onChange={e => setNewFolder({ ...newFolder, rut: e.target.value })}
                    placeholder="12.345.678-9" data-testid="input-folder-rut" />
                </div>
                <div className="clientes-field">
                  <label>Codeudor (nombre)</label>
                  <input type="text" value={newFolder.codeudor_nombre} onChange={e => setNewFolder({ ...newFolder, codeudor_nombre: e.target.value })}
                    placeholder="Opcional" data-testid="input-folder-codeudor" />
                </div>
                <div className="clientes-field">
                  <label>RUT Codeudor</label>
                  <input type="text" value={newFolder.codeudor_rut} onChange={e => setNewFolder({ ...newFolder, codeudor_rut: e.target.value })}
                    placeholder="Opcional" />
                </div>
              </div>
              <div className="clientes-form-actions">
                <button className="docs-btn secondary" onClick={() => setShowCreate(false)}>Cancelar</button>
                <button className="docs-btn primary" onClick={createFolder} disabled={loading} data-testid="btn-confirm-create">
                  {loading ? "Creando..." : "Crear Carpeta"}
                </button>
              </div>
            </div>
          )}

          <div className="clientes-grid">
            {filtered.length === 0 && (
              <div className="clientes-empty">
                <i className="fa fa-folder-open-o"></i>
                <p>No hay carpetas de clientes{searchQuery ? " que coincidan" : ""}.</p>
              </div>
            )}
            {filtered.map(f => {
              // Detect missing docs (basic heuristic: dependents need cedula+liquidacion+afp+cmf)
              const ct = f.credit_request?.client_type || "";
              const cats = f.credit_request?.doc_categories || [];
              // Regla: dependientes con liquidaciones NO necesitan boletas
              const required = ct === "independiente"
                ? ["cedula", "imp_renta", "boletas", "cmf"]
                : ["cedula", "liquidacion", "afp", "cmf"];
              const missing = required.filter(r => !cats.includes(r));
              // Si es dependiente y tiene liquidaciones, no marques boletas como faltante
              if (ct !== "independiente" && cats.includes("liquidacion")) {
                const idx = missing.indexOf("boletas"); if (idx >= 0) missing.splice(idx, 1);
              }
              const hasFin = f.datos_financieros && f.datos_financieros.valor_propiedad;
              const enviadoManual = f.envio_manual === true;
              const cardStyle = enviadoManual
                ? { position: "relative", background: "#be123c", borderLeft: "5px solid #7f1d1d", color: "#fff", flexWrap: "wrap" }
                : { position: "relative", flexWrap: "wrap", borderLeft: (f.emails_sent_count > 0) ? "5px solid #d4af37" : (f.is_ready_to_send ? "5px solid #10d98e" : (f.codeudor_nombre ? "5px solid #2e5ce6" : "")), background: (f.emails_sent_count > 0) ? "rgba(212,175,55,0.06)" : (f.is_ready_to_send ? "rgba(16,217,142,0.06)" : undefined) };
              const irAModulo = (mod) => {
                sessionStorage.setItem("cm_prefill_cliente", JSON.stringify({ nombre: f.nombre, rut: f.rut || "" }));
                onNavigate && onNavigate(mod);
              };
              const modBtn = (bg, border, color, big) => ({
                display: "flex", alignItems: "center", gap: 6, padding: big ? "0.55rem 1rem" : "0.45rem 0.8rem",
                borderRadius: 0, border: `1.5px solid ${border}`, background: bg, color,
                fontWeight: 800, fontSize: big ? 13 : 11.5, cursor: "pointer", whiteSpace: "nowrap",
              });
              return (
                <div key={f.id} className="clientes-card" data-testid={`folder-${f.id}`} style={cardStyle}>
                  {enviadoManual && (
                    <div style={{ position: "absolute", top: 8, left: 8, background: "#fff", color: "#be123c", borderRadius: 0, padding: "2px 8px", fontSize: 10, fontWeight: 800 }} data-testid={`badge-enviado-${f.id}`}>
                      ✅ ENVIADO (manual)
                    </div>
                  )}
                  {missing.length > 0 && (
                    <div title={`Faltan: ${missing.join(", ")}`} style={{ position: "absolute", top: 8, right: 8, background: "#be123c", color: "#fff", borderRadius: "50%", width: 22, height: 22, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, boxShadow: "0 2px 8px rgba(190,18,60,0.5)" }}>
                      {missing.length}
                    </div>
                  )}
                  <div className="clientes-card-icon"><i className="fa fa-folder"></i></div>
                  <div className="clientes-card-info">
                    <h4>{f.nombre}</h4>
                    {f.rut && <span className="clientes-rut">{f.rut}</span>}
                    {f.codeudor_nombre && <span className="clientes-codeudor"><i className="fa fa-user-plus"></i> {f.codeudor_nombre}</span>}
                    <span className="clientes-file-count">{f.total_archivos || 0} archivos</span>
                    <div style={{ display: "flex", gap: 6, marginTop: 4, flexWrap: "wrap" }}>
                      {f.is_ready_to_send && (
                        <span style={{ fontSize: 10, background: "rgba(16,217,142,0.25)", color: "#0e9f6e", padding: "2px 6px", borderRadius: 0, fontWeight: 700 }}>🎯 Lista para enviar</span>
                      )}
                      {f.emails_sent_count > 0 && (
                        <span title={`Último envío: ${(f.last_email_sent_at || "").slice(0,19).replace('T',' ')}`} style={{ fontSize: 10, background: "rgba(212,175,55,0.2)", color: "#0a3d91", padding: "2px 6px", borderRadius: 0, fontWeight: 700 }}>📧 Enviado a mesa × {f.emails_sent_count}{f.last_email_sent_at ? ` · ${fmtAct(f.last_email_sent_at)}` : ""}</span>
                      )}
                      {hasFin ? (
                        <span style={{ fontSize: 10, background: "rgba(16,217,142,0.15)", color: "#10c98a", padding: "2px 6px", borderRadius: 0 }}>💰 Datos OK</span>
                      ) : (
                        <span style={{ fontSize: 10, background: "rgba(250,204,21,0.15)", color: "#a16207", padding: "2px 6px", borderRadius: 0 }}>💰 Sin datos financieros</span>
                      )}
                      {f.datos_financieros?.fecha_entrega && (
                        <span data-testid={`badge-entrega-${f.id}`} style={{ fontSize: 10, background: "rgba(46,92,230,0.15)", color: "#1e46c0", padding: "2px 6px", borderRadius: 0, fontWeight: 700 }}>🏠 Entrega {f.datos_financieros.fecha_entrega}</span>
                      )}
                    </div>
                    {missing.length > 0 && (
                      <div data-testid={`missing-docs-${f.id}`} style={{ display: "flex", gap: 4, marginTop: 5, flexWrap: "wrap", alignItems: "center" }}>
                        <span style={{ fontSize: 10, fontWeight: 800, color: enviadoManual ? "#fff" : "#be123c" }}>⚠️ FALTA:</span>
                        {missing.map(m => (
                          <span key={m} style={{ fontSize: 10, fontWeight: 700, background: enviadoManual ? "rgba(255,255,255,0.25)" : "rgba(190,18,60,0.15)", color: enviadoManual ? "#fff" : "#be123c", padding: "2px 7px", borderRadius: 0, border: enviadoManual ? "1px solid rgba(255,255,255,0.4)" : "1px solid rgba(190,18,60,0.35)" }}>
                            {CAT_LABELS[m] || m}
                          </span>
                        ))}
                      </div>
                    )}
                    {(f.criterios || []).length > 0 && (
                      <div data-testid={`criterios-list-${f.id}`} style={{ display: "flex", gap: 4, marginTop: 5, flexWrap: "wrap", alignItems: "center" }}>
                        {f.criterios.map(c => (
                          <span key={c.nombre} title={c.nombre} style={{ fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 0,
                            background: enviadoManual ? "rgba(255,255,255,0.2)" : (c.ok ? "rgba(16,217,142,0.12)" : "rgba(148,163,184,0.12)"),
                            color: enviadoManual ? "#fff" : (c.ok ? "#10c98a" : "#94a3b8"),
                            border: `1px solid ${c.ok ? "rgba(16,217,142,0.4)" : "rgba(148,163,184,0.3)"}` }}>
                            {c.ok ? "✓" : "✗"} {c.nombre}
                          </span>
                        ))}
                      </div>
                    )}
                    <div style={{ display: "flex", gap: 8, marginTop: 5, alignItems: "center", flexWrap: "wrap" }}>
                      {f.source_email && (
                        <span data-testid={`recibido-de-${f.id}`} style={{ fontSize: 10.5, opacity: 0.75, color: enviadoManual ? "#fff" : undefined }}>
                          📥 Solicitud recibida de: <b>{f.source_email}</b>
                        </span>
                      )}
                      {missing.length > 0 && f.source_email && (
                        <button data-testid={`btn-pedir-faltantes-${f.id}`} onClick={() => openPedirFaltantes(f)}
                          style={{ fontSize: 10.5, fontWeight: 800, padding: "3px 10px", borderRadius: 0, cursor: "pointer",
                            background: "rgba(190,18,60,0.12)", color: enviadoManual ? "#fff" : "#be123c", border: "1.5px solid rgba(190,18,60,0.5)" }}>
                          📩 Pedir faltantes al remitente{f.faltantes_pedidos_at ? ` ✓ Solicitado ${fmtAct(f.faltantes_pedidos_at)}` : ""}
                        </button>
                      )}
                    </div>

                  </div>
                  {f.prob_aprobacion && f.prob_aprobacion.porcentaje != null && (
                    <div style={{ display: "flex", gap: 8, alignItems: "stretch", flexShrink: 0 }}>
                      <div data-testid={`prob-aprobacion-${f.id}`}
                        title={`Posibilidades de aprobación\n${(f.prob_aprobacion.factores || []).join("\n")}`}
                        style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minWidth: 88, padding: "6px 10px", borderRadius: 0,
                          background: enviadoManual ? "rgba(255,255,255,0.15)" : (f.prob_aprobacion.porcentaje >= 75 ? "rgba(16,217,142,0.12)" : f.prob_aprobacion.porcentaje >= 50 ? "rgba(250,204,21,0.18)" : "rgba(190,18,60,0.12)") }}>
                        <span style={{ fontSize: 36, fontWeight: 900, lineHeight: 1,
                          color: enviadoManual ? "#fff" : (f.prob_aprobacion.porcentaje >= 75 ? "#10c98a" : f.prob_aprobacion.porcentaje >= 50 ? "#a16207" : "#be123c") }}>
                          {f.prob_aprobacion.porcentaje}%
                        </span>
                        <span style={{ fontSize: 9, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.5, opacity: 0.85, color: enviadoManual ? "#fff" : undefined }}>aprobación</span>
                        {f.techo_uf != null && (
                          <span data-testid={`techo-max-${f.id}`}
                            title={`Techo Hipotecario (máximo crédito posible) — mejor escenario: ${f.techo_banco || ""}`}
                            style={{ fontSize: 10, fontWeight: 900, marginTop: 3, whiteSpace: "nowrap", color: enviadoManual ? "#fff" : "#d4af37" }}>
                            ▲ Techo {Math.round(f.techo_uf).toLocaleString("es-CL")} UF
                          </span>
                        )}
                      </div>
                      <div data-testid={`mesa-criterios-${f.id}`}
                        style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minWidth: 92, padding: "6px 10px", borderRadius: 0,
                          background: f.mesa_respuesta === "aprobada" ? "rgba(16,217,142,0.15)" : (f.mesa_respuesta === "rechazada" ? "rgba(190,18,60,0.15)" : "rgba(148,163,184,0.1)"),
                          border: f.mesa_respuesta ? "1.5px solid " + (f.mesa_respuesta === "aprobada" ? "#10d98e" : "#be123c") : "1px dashed rgba(148,163,184,0.4)" }}>
                        <span style={{ fontSize: 9, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.5, opacity: 0.8, color: enviadoManual ? "#fff" : undefined }}>Mesa</span>
                        {f.mesa_respuesta === "aprobada" && <span style={{ fontSize: 13, fontWeight: 900, color: "#10c98a" }}>✅ APROBADA</span>}
                        {f.mesa_respuesta === "rechazada" && <span style={{ fontSize: 13, fontWeight: 900, color: "#be123c" }}>❌ RECHAZADA</span>}
                        {!f.mesa_respuesta && <span style={{ fontSize: 11, fontWeight: 700, opacity: 0.6, color: enviadoManual ? "#fff" : undefined }}>Sin respuesta</span>}
                        {(f.criterios || []).length > 0 && (
                          <span style={{ fontSize: 10, fontWeight: 700, marginTop: 2, color: enviadoManual ? "#fff" : ((f.criterios.filter(c => c.ok).length === f.criterios.length) ? "#10c98a" : "#a16207") }}>
                            criterios {f.criterios.filter(c => c.ok).length}/{f.criterios.length}
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                  <div className="clientes-card-actions">
                    <button
                      className="docs-btn"
                      data-testid={`btn-envio-manual-${f.id}`}
                      onClick={() => toggleEnvioManual(f)}
                      title={enviadoManual ? "Marcar como NO enviado" : "Marcar como ENVIADO (pinta la carpeta roja)"}
                      style={enviadoManual
                        ? { background: "#fff", color: "#be123c", border: "1px solid #fff", fontWeight: 800 }
                        : { background: "rgba(190,18,60,0.1)", color: "#be123c", border: "1px solid #be123c", fontWeight: 700 }}>
                      <i className={`fa ${enviadoManual ? "fa-check-square" : "fa-square-o"}`}></i> {enviadoManual ? "Enviado" : "No enviado"}
                    </button>
                    {f.is_ready_to_send && (
                      <button className="docs-btn" onClick={() => openFolder(f.id, "email")} data-testid={`btn-enviar-ya-${f.id}`}
                        title="Lista para enviar: abre la carpeta y prepara el autocorreo con preview automático"
                        style={{ background: "#10d98e", color: "#fff", border: "1px solid #0e9f6e", fontWeight: 700, boxShadow: "0 2px 8px rgba(16,217,142,0.4)" }}>
                        <i className="fa fa-paper-plane"></i> 🚀 Enviar Ya
                      </button>
                    )}
                    <button className="docs-btn primary" onClick={() => openFolder(f.id)} data-testid={`btn-open-${f.id}`}>
                      <i className="fa fa-folder-open"></i> Abrir
                    </button>
                    <button className="clientes-delete-btn" onClick={() => deleteFolder(f.id)}>
                      <i className="fa fa-trash"></i>
                    </button>
                  </div>
                  <div data-testid={`modulos-carpeta-${f.id}`} style={{ width: "100%", display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10, paddingTop: 10, borderTop: enviadoManual ? "1px solid rgba(255,255,255,0.3)" : "1px solid rgba(46,92,230,0.25)" }}>
                    <button data-testid={`btn-aprobacion-${f.id}`} onClick={() => irAModulo("aprobacion")}
                      title={`Enviar aprobación al cliente ${f.nombre}`}
                      style={modBtn("rgba(16,217,142,0.12)", "#10d98e", enviadoManual ? "#fff" : "#10c98a")}>
                      <i className="fa fa-trophy"></i> Enviar Aprobación Cliente
                    </button>
                    <button data-testid={`btn-gastos-${f.id}`} onClick={() => irAModulo("gastos")}
                      title={`Gasto operacional para ${f.nombre}`}
                      style={modBtn("var(--gold, #d4af37)", "var(--gold, #d4af37)", "#0a0e17", true)}>
                      <i className="fa fa-money"></i> GASTO OPERACIONAL
                    </button>
                    <button data-testid={`btn-setcredito-${f.id}`} onClick={() => irAModulo("setcredito")}
                      title={`Firma set de crédito de ${f.nombre}`}
                      style={modBtn("rgba(212,175,55,0.12)", "#d4af37", enviadoManual ? "#fff" : "#0f52ba")}>
                      <i className="fa fa-pencil-square-o"></i> Firma Set de Crédito
                    </button>
                    <button data-testid={`btn-tasacion-${f.id}`} onClick={() => openTasacion(f)}
                      title={`Solicitar tasación de la propiedad de ${f.nombre} (Value Property + Victoria Vilches)`}
                      style={modBtn("rgba(234,88,12,0.12)", "#ea580c", enviadoManual ? "#fff" : "#ea580c")}>
                      <i className="fa fa-home"></i> Solicitud de Tasación{f.tasacion_terminado_at ? ` ✅ Terminada ${fmtAct(f.tasacion_terminado_at)}` : (f.tasacion_solicitada_at ? ` ✓ Solicitada ${fmtAct(f.tasacion_solicitada_at)}` : "")}{f.tasacion_fecha ? ` · 📅 ${f.tasacion_fecha}` : ""}
                    </button>
                    {f.tasacion_solicitada_at && (
                      <button data-testid={`btn-tasacion-terminada-${f.id}`} onClick={() => marcarTerminado(f, "tasacion", !f.tasacion_terminado_at)}
                        title={f.tasacion_terminado_at ? "Desmarcar: la tasación vuelve a estado solicitada" : "Marcar la tasación como TERMINADA (queda registrado con fecha y hora)"}
                        style={modBtn(f.tasacion_terminado_at ? "rgba(16,217,142,0.15)" : "rgba(148,163,184,0.1)", f.tasacion_terminado_at ? "#10d98e" : "#94a3b8", f.tasacion_terminado_at ? "#34eab9" : (enviadoManual ? "#fff" : "#94a3b8"))}>
                        <i className="fa fa-check-circle"></i> {f.tasacion_terminado_at ? "Tasación terminada" : "¿Tasación terminada?"}
                      </button>
                    )}
                    <button data-testid={`btn-estudio-titulo-${f.id}`} onClick={() => openEstudio(f)}
                      title={`Solicitar estudio de títulos de ${f.nombre} (siempre con copia a Victoria Vilches)`}
                      style={modBtn("rgba(20,184,166,0.12)", "#14b8a6", enviadoManual ? "#fff" : "#0d9488")}>
                      <i className="fa fa-balance-scale"></i> Solicitud de Estudio de Título{f.estudio_titulo_terminado_at ? ` ✅ Terminado ${fmtAct(f.estudio_titulo_terminado_at)}` : (f.estudio_titulo_solicitado_at ? ` ✓ Solicitado ${fmtAct(f.estudio_titulo_solicitado_at)}` : "")}
                    </button>
                    {f.estudio_titulo_solicitado_at && (
                      <button data-testid={`btn-estudio-terminado-${f.id}`} onClick={() => marcarTerminado(f, "estudio_titulo", !f.estudio_titulo_terminado_at)}
                        title={f.estudio_titulo_terminado_at ? "Desmarcar: el estudio vuelve a estado solicitado" : "Marcar el estudio de título como TERMINADO (queda registrado con fecha y hora)"}
                        style={modBtn(f.estudio_titulo_terminado_at ? "rgba(16,217,142,0.15)" : "rgba(148,163,184,0.1)", f.estudio_titulo_terminado_at ? "#10d98e" : "#94a3b8", f.estudio_titulo_terminado_at ? "#34eab9" : (enviadoManual ? "#fff" : "#94a3b8"))}>
                        <i className="fa fa-check-circle"></i> {f.estudio_titulo_terminado_at ? "E. Título terminado" : "¿E. Título terminado?"}
                      </button>
                    )}
                    {f.estudio_titulo_solicitado_at && (() => {
                      const rep = f.estudio_reparos || {};
                      const items = rep.items || [];
                      const pendientes = items.filter(i => !i.satisfecho).length;
                      const satisfecho = rep.estado === "satisfecho";
                      return (
                        <button data-testid={`btn-reparos-${f.id}`} onClick={() => openReparos(f)}
                          title={`Reparos del estudio de título de ${f.nombre} (detección automática en el hilo del abogado)`}
                          style={modBtn(satisfecho ? "rgba(16,217,142,0.12)" : (pendientes ? "rgba(225,29,72,0.14)" : "rgba(148,163,184,0.1)"),
                            satisfecho ? "#10d98e" : (pendientes ? "#e11d48" : "#94a3b8"),
                            satisfecho ? "#34eab9" : (pendientes ? "#fb7185" : (enviadoManual ? "#fff" : "#94a3b8")))}>
                          <i className="fa fa-gavel"></i> Reparos E. Título{satisfecho ? " ✅ resueltos" : (items.length ? ` (${pendientes} pendiente${pendientes === 1 ? "" : "s"})` : "")}
                        </button>
                      );
                    })()}
                    <button data-testid={`btn-escritura-${f.id}`} onClick={() => openEscritura(f)}
                      title={`Avisar a ${f.nombre} la fecha de firma de su escritura (con confirmación de asistencia)`}
                      style={modBtn("rgba(236,72,153,0.12)", "#ec4899", enviadoManual ? "#fff" : "#db2777")}>
                      <i className="fa fa-pencil"></i> Firma de Escritura{f.escritura_confirmada_at ? ` ✅ Confirmada ${fmtAct(f.escritura_confirmada_at)}` : (f.escritura_solicitada_at ? ` ✓ Solicitada ${fmtAct(f.escritura_solicitada_at)}` : "")}
                    </button>
                    <button data-testid={`btn-enriquecer-${f.id}`} onClick={() => enriquecerCarpeta(f, "credito")}
                      disabled={enriching === f.id + "credito"}
                      title={`Buscar de nuevo en el correo (asunto, cuerpo y adjuntos) los documentos faltantes de ${f.nombre}`}
                      style={modBtn("rgba(212,175,55,0.12)", "#d4af37", enviadoManual ? "#fff" : "#b8942e")}>
                      <i className={`fa ${enriching === f.id + "credito" ? "fa-spinner fa-spin" : "fa-magic"}`}></i> Enriquecer archivos
                    </button>
                    <button data-testid={`btn-escrituracion-toggle-${f.id}`} onClick={() => toggleEscrituracion(f)}
                      title={f.is_escrituracion ? "Devolver esta carpeta a Solicitudes de Crédito" : "Enviar la ficha a Escrituración y activarla en Set de Crédito y Títulos"}
                      style={modBtn(f.is_escrituracion ? "rgba(148,163,184,0.12)" : "rgba(46,92,230,0.12)", f.is_escrituracion ? "#94a3b8" : "#2e5ce6", enviadoManual ? "#fff" : (f.is_escrituracion ? "#94a3b8" : "#9333ea"))}>
                      <i className="fa fa-exchange"></i> {f.is_escrituracion ? "Devolver a Clientes" : "⚖️ Enviar a Escrituración"}
                    </button>
                    <button data-testid={`btn-historial-${f.id}`} onClick={() => openHistorial(f)}
                      title={`Historial completo de actividades de ${f.nombre}`}
                      style={modBtn("rgba(212,175,55,0.10)", "#d4af37", enviadoManual ? "#fff" : "#b8912e")}>
                      <i className="fa fa-history"></i> Historial
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* DETAIL VIEW */}
      {view === "detail" && currentFolder && (
        <div data-testid="clientes-detail">
          <div className="clientes-detail-header">
            <button className="docs-btn secondary" onClick={() => { setView("list"); setCurrentFolder(null); }} data-testid="btn-back-clientes">
              <i className="fa fa-arrow-left"></i> Volver
            </button>
            <h3><i className="fa fa-folder-open"></i> {currentFolder.nombre}</h3>
            <div className="clientes-detail-actions">
              <button className="docs-btn secondary" onClick={saveAllAttachments} disabled={loading} data-testid="btn-fetch-attachments">
                <i className={`fa ${loading ? "fa-spinner fa-spin" : "fa-envelope"}`}></i> Buscar Adjuntos
              </button>
              <button className="docs-btn secondary" onClick={() => document.getElementById('manual-upload-input').click()} disabled={uploadingManual} data-testid="btn-upload-manual"
                style={{ background: "rgba(46,92,230,0.15)", border: "1px solid #2e5ce6", color: "#a78bfa" }}>
                <i className={`fa ${uploadingManual ? "fa-spinner fa-spin" : "fa-upload"}`}></i> {uploadingManual ? "Subiendo…" : "Subir Archivo"}
              </button>
              <input id="manual-upload-input" type="file" multiple style={{ display: "none" }} onChange={handleManualUpload}
                accept=".pdf,.jpg,.jpeg,.png,.heic,.heif,.docx,.doc,.xlsx" data-testid="manual-upload-input" />
              <ImportarCorreo destino="carpeta" destinoId={currentFolder.id} nombre={currentFolder.nombre}
                label="Importar desde correo"
                onDone={async () => { const r = await axios.get(`${API}/api/clientes/folders/${currentFolder.id}`); setCurrentFolder(r.data); }} />
              <ImportarCorreo destino="estudio_titulo" destinoId={currentFolder.id} nombre={currentFolder.nombre}
                label="Importar a Estudio de Título" style={{ background: "rgba(13,148,136,0.25)" }}
                onDone={async () => { const r = await axios.get(`${API}/api/clientes/folders/${currentFolder.id}`); setCurrentFolder(r.data); }} />
              <button className="docs-btn secondary" onClick={regenerateCombined} disabled={mergingProto === currentFolder.id} data-testid="btn-regen-combined"
                style={{ background: "rgba(234,88,12,0.15)", border: "1px solid #ea580c", color: "#fb923c" }}>
                <i className={`fa ${mergingProto === currentFolder.id ? "fa-spinner fa-spin" : "fa-file-pdf-o"}`}></i> {mergingProto === currentFolder.id ? "Combinando…" : "Regenerar Combinado"}
              </button>
              <button className="docs-btn secondary" onClick={() => openFinPanel(currentFolder)} data-testid="btn-fin-detail"
                style={{ background: "rgba(212,175,55,0.15)", border: "1px solid #d4af37", color: "#b8942e" }}>
                <i className="fa fa-dollar"></i> Datos Financieros
              </button>
              <button className="docs-btn secondary shimmer-oro" onClick={() => calcularTecho(currentFolder)} disabled={techoBusy} data-testid="btn-techo-hipotecario"
                style={{ backgroundImage: "linear-gradient(135deg, #BF953F, #FCF6BA 45%, #B38728, #FBF5B7 80%, #AA771C)", border: "none", color: "#0a0a0a", fontWeight: 800 }}>
                <i className={`fa ${techoBusy ? "fa-spinner fa-spin" : "fa-bar-chart"}`}></i> {techoBusy ? "Calculando…" : "Calcular Alcance Máximo"}
              </button>
              <button className="docs-btn secondary shimmer-oro" onClick={() => openEmailModal(currentFolder)} data-testid="btn-send-autocorreo-detail"
                style={{ background: "#10c98a", border: "1px solid #0e9f6e", color: "#fff", fontWeight: 600 }}>
                <i className="fa fa-paper-plane"></i> Enviar a Mesa
              </button>
              <button className="docs-btn secondary" data-testid="btn-reenviar-notificacion"
                onClick={async () => {
                  if (!window.confirm(`📧 ¿Re-enviar la notificación de aprobación a ${currentFolder.nombre}?\nSe saltará el bloqueo de duplicados (para cuando el cliente dice que no le llegó).`)) return;
                  try {
                    const r = await axios.post(`${API}/api/clientes/folders/${currentFolder.id}/reenviar-notificacion`);
                    window.alert(`✅ Notificación re-enviada a ${r.data.to}${(r.data.adjuntos || []).length ? ` con ${r.data.adjuntos.length} adjunto(s)` : r.data.con_links ? " con links de descarga segura" : ""} (BCC cuenta comercial)`);
                  } catch (e) { window.alert(`🚨 ${e.response?.data?.detail || "Error al re-enviar la notificación"}`); }
                }}
                style={{ background: "rgba(59,130,246,0.15)", border: "1px solid #3b82f6", color: "#93c5fd" }}>
                <i className="fa fa-bell"></i> Re-enviar Notificación
              </button>
              <button className="docs-btn secondary shimmer-oro" data-testid="btn-compromiso"
                onClick={() => setShowCompromiso(true)}
                style={{ background: "rgba(212,175,55,0.18)", border: "1px solid #d4af37", color: "#d4af37", fontWeight: 700 }}>
                <i className="fa fa-file-text-o"></i> Ver/Editar Compromiso de Compraventa
              </button>
              <button className="docs-btn secondary" onClick={() => openMissingDocsModal(currentFolder)} data-testid="btn-missing-docs-detail"
                style={{ background: "rgba(225,29,72,0.15)", border: "1px solid rgba(225,29,72,0.5)", color: "#fb7185" }}>
                <i className="fa fa-exclamation-triangle"></i> Documento Faltante
              </button>
              <button className="docs-btn secondary" onClick={() => agregarCodeudor(currentFolder)} data-testid={`btn-agregar-codeudor-${currentFolder.id}`}
                style={{ background: "rgba(251,146,60,0.15)", border: "1px solid rgba(251,146,60,0.5)", color: "#fdba74" }}>
                <i className="fa fa-user-plus"></i> Agregar Codeudor
              </button>
              <button className="docs-btn secondary" onClick={() => window.open(`${API}/api/informes/vip/${currentFolder.id}/pdf`, "_blank")} data-testid={`btn-informe-vip-${currentFolder.id}`}
                style={{ background: "rgba(212,175,55,0.12)", border: "1px solid rgba(212,175,55,0.5)", color: "#d4af37" }}>
                <i className="fa fa-file-pdf-o"></i> Informe VIP
              </button>
              <button className="docs-btn primary" onClick={() => downloadAll(currentFolder.id)} data-testid="btn-download-all">
                <i className="fa fa-download"></i> Descargar Todo
              </button>
            </div>
          </div>

          {showCompromiso && currentFolder && (
            <CompromisoEditor folder={currentFolder} onClose={() => setShowCompromiso(false)} />
          )}


          {techo && (
            <div data-testid="techo-modal" onClick={() => setTecho(null)}
              style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.82)", zIndex: 300, display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem" }}>
              <div onClick={e => e.stopPropagation()} style={{ background: "#0a0a0a", border: "1px solid rgba(212,175,55,0.4)", width: "min(680px, 96vw)", maxHeight: "90vh", overflow: "auto", padding: "1.6rem 1.8rem" }}>
                <div style={{ display: "flex", alignItems: "center", marginBottom: 6 }}>
                  <b style={{ color: "#d4af37", fontSize: "1.05rem", letterSpacing: "0.04em" }}>📊 Techo Hipotecario — {techo.cliente}</b>
                  <button data-testid="techo-cerrar" onClick={() => setTecho(null)} style={{ marginLeft: "auto", background: "transparent", border: "none", color: "#94a3b8", fontSize: "1.3rem", cursor: "pointer" }}>✕</button>
                </div>
                {!techo.datos_suficientes ? (
                  <div style={{ color: "#fb7185", fontSize: "0.85rem", padding: "1rem 0", lineHeight: 1.6 }}>
                    ⚠️ No hay renta líquida cargada en los Datos Financieros de esta carpeta. Ejecute la extracción OCR de las liquidaciones o ingrese la renta manualmente para calcular el alcance máximo.
                  </div>
                ) : (
                  <>
                    <div style={{ color: "#9a8c52", fontSize: "0.72rem", marginBottom: 14, lineHeight: 1.6 }}>
                      Renta líquida depurada: <b style={{ color: "#e7cf7a" }}>${techo.renta_liquida_depurada_clp.toLocaleString("es-CL")}</b> ·
                      castigos: variable −{techo.componentes_renta.castigo_variable_pct}%, honorarios −{techo.componentes_renta.castigo_honorarios_pct}% ·
                      tasa {techo.tasa_anual_pct}% · plazo {techo.plazo_anos} años
                    </div>
                    {techo.endeudamiento && (
                      <div style={{ border: "1px solid rgba(255,255,255,0.12)", padding: "0.7rem 0.9rem", marginBottom: 14, fontSize: "0.72rem", color: "#94a3b8", lineHeight: 1.7 }}>
                        <b style={{ color: "#cbd5e1" }}>Endeudamiento teórico (fórmula 2% mensual · 48 meses)</b><br />
                        Deuda CMF ${techo.endeudamiento.deuda_cmf_total_clp.toLocaleString("es-CL")} → cuota ${techo.endeudamiento.cuota_teorica_cmf_clp.toLocaleString("es-CL")}/mes ·
                        Crédito interno PAV ${techo.endeudamiento.pav_saldo_clp.toLocaleString("es-CL")} → cuota ${techo.endeudamiento.cuota_teorica_pav_clp.toLocaleString("es-CL")}/mes<br />
                        <b style={{ color: "#e7cf7a" }}>Endeudamiento mensual total: ${techo.endeudamiento.endeudamiento_mensual_clp.toLocaleString("es-CL")}</b> ({techo.carga_actual_pct}% de la renta)
                      </div>
                    )}
                    {techo.alerta_carga_excedida && (
                      <div data-testid="techo-alerta-carga" style={{ background: "rgba(225,29,72,0.12)", border: "1px solid rgba(225,29,72,0.5)", color: "#fb7185", padding: "0.6rem 0.9rem", marginBottom: 14, fontSize: "0.74rem", fontWeight: 700 }}>
                        🚨 Las deudas actuales ya superan el 40% de la renta líquida depurada — sin margen para un nuevo dividendo.
                      </div>
                    )}
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 14 }} data-testid="techo-doble-panel">
                      <div style={{ border: "1px solid rgba(255,255,255,0.15)", padding: "0.9rem 1rem" }}>
                        <div style={{ color: "#94a3b8", fontSize: "0.68rem", letterSpacing: "0.12em", textTransform: "uppercase" }}>Criterio Teórico (Bodega)</div>
                        <div style={{ color: "#e7cf7a", fontWeight: 900, fontSize: "1.2rem", marginTop: 6 }}>
                          {(techo.teorico_uf || 0).toLocaleString("es-CL")} UF
                        </div>
                        <div style={{ color: "#6b6b6b", fontSize: "0.68rem", marginTop: 4 }}>Reglas BTG/Ameris de la Constitución</div>
                      </div>
                      <div data-testid="techo-espejo-mesa" style={{ border: "1px solid rgba(14,165,233,0.45)", padding: "0.9rem 1rem", background: "rgba(14,165,233,0.05)" }}>
                        <div style={{ color: "#a5f3fc", fontSize: "0.68rem", letterSpacing: "0.12em", textTransform: "uppercase" }}>Veredicto Algoritmo Espejo MESA</div>
                        {techo.espejo_mesa?.disponible ? (
                          <>
                            <div style={{ color: "#a5f3fc", fontWeight: 900, fontSize: "1.2rem", marginTop: 6 }}>
                              {techo.espejo_mesa.monto_uf.toLocaleString("es-CL")} UF
                            </div>
                            <div style={{ color: "#6b6b6b", fontSize: "0.68rem", marginTop: 4 }}>
                              Precisión estimada: {techo.espejo_mesa.precision_pct}% · {techo.espejo_mesa.n} casos del segmento
                              {techo.espejo_mesa.segmento ? ` «${techo.espejo_mesa.segmento}»` : ""} · ventana 280 días
                            </div>
                          </>
                        ) : (
                          <div style={{ color: "#94a3b8", fontSize: "0.72rem", marginTop: 8, lineHeight: 1.5 }}>
                            🧠 {techo.espejo_mesa?.nota || "Espejo en calibración — se entrena cada 24h con las aprobaciones reales."}
                          </div>
                        )}
                        {techo.espejo_mesa?.sugerir_codeudor && (
                          <div data-testid="techo-sugerir-codeudor" style={{ color: "#e7cf7a", fontSize: "0.7rem", marginTop: 6, fontWeight: 700 }}>
                            💡 DashAI: para esta renta la MESA suele exigir <u>Incorporar Codeudor</u>
                          </div>
                        )}
                      </div>
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                      {techo.escenarios.map((e, i) => {
                        const esMejor = techo.mejor_escenario && e.banco === techo.mejor_escenario.banco && e.credito_maximo_uf === techo.mejor_escenario.credito_maximo_uf;
                        return (
                          <div key={i} data-testid={`techo-escenario-${e.banco.split(" ")[0].toLowerCase()}`}
                            style={{ border: `1px solid ${esMejor ? "rgba(212,175,55,0.6)" : "rgba(255,255,255,0.12)"}`, padding: "1rem 1.1rem", background: esMejor ? "rgba(212,175,55,0.05)" : "transparent" }}>
                            <div style={{ color: "#cbd5e1", fontSize: "0.72rem", letterSpacing: "0.1em", textTransform: "uppercase" }}>{e.banco}</div>
                            <div className={esMejor ? "shimmer-oro" : ""} style={{ marginTop: 8, padding: "0.5rem 0.7rem", display: "inline-block",
                              backgroundImage: "linear-gradient(135deg, #BF953F, #FCF6BA 45%, #B38728, #FBF5B7 80%, #AA771C)",
                              color: "#0a0a0a", fontWeight: 900, fontSize: "1.35rem", letterSpacing: "-0.01em" }}>
                              {e.credito_maximo_uf.toLocaleString("es-CL")} UF
                            </div>
                            <div style={{ color: "#94a3b8", fontSize: "0.72rem", marginTop: 8, lineHeight: 1.7 }}>
                              Dividendo máx: ${e.dividendo_maximo_clp.toLocaleString("es-CL")}<br />
                              Carga máx {e.carga_max_pct}% · Div/Renta {e.div_renta_max_pct}%<br />
                              <span style={{ color: "#e7cf7a" }}>Tope activo: {e.restriccion_activa}</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    <div style={{ color: "#6b6b6b", fontSize: "0.68rem", marginTop: 14, lineHeight: 1.6 }}>
                      Simulación inversa DashAI sobre los documentos reales, según los topes vigentes de la Constitución. Referencial: la MESA confirma el monto final.
                    </div>
                  </>
                )}
              </div>
            </div>
          )}
          {finOpenId === currentFolder.id && (
            <div data-testid={`fin-detail-panel`} style={{ background: "rgba(212,175,55,0.08)", border: "1px solid #d4af37", borderRadius: 0, padding: "0.9rem", marginBottom: "0.8rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
                <h5 style={{ margin: 0, color: "#b8942e" }}>
                  <i className="fa fa-dollar" /> Datos financieros del cliente
                  <span style={{ marginLeft: 10, fontSize: 11, fontWeight: 400, opacity: 0.7 }}>
                    UF: ${ufValue.toLocaleString('es-CL')}
                  </span>
                </h5>
                <div style={{ display: "flex", gap: 6 }}>
                  <button className="docs-btn secondary" onClick={() => runOcrFin(currentFolder.id)} disabled={ocrRunning || finSaving} style={{ background: "#1e46c0", color: "#fff", border: "none", padding: "0.35rem 0.7rem", fontSize: 12 }}>
                    <i className="fa fa-magic" /> {ocrRunning ? "Leyendo PDFs..." : "Autodetectar con IA"}
                  </button>
                  <button className="docs-btn primary" onClick={() => saveFinPanel(currentFolder.id)} disabled={finSaving} style={{ padding: "0.35rem 0.7rem", fontSize: 12 }}>
                    <i className={`fa ${finSaving ? "fa-spinner fa-spin" : "fa-save"}`} /> Guardar
                  </button>
                </div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "0.5rem" }}>
                {currentFolder.source_email && (() => {
                  const m = currentFolder.source_email.match(/^\s*(.*?)\s*<([^>]+)>\s*$/);
                  const nm = m ? m[1].replace(/"/g, "").trim() : "";
                  const ad = m ? m[2].trim() : (currentFolder.source_email.includes("@") ? currentFolder.source_email.trim() : "");
                  const disp = nm ? `${nm} <${ad}>` : ad;
                  return (
                    <div data-testid="fin-origen" style={{ gridColumn: "1 / -1", background: "#dbeafe", border: "1px solid #d4af37", borderRadius: 0, padding: "0.5rem 0.7rem", fontSize: 12 }}>
                      <b style={{ color: "#1e3a8a" }}>📧 Origen de la solicitud:</b> <span style={{ color: "#b8942e", fontFamily: "monospace" }}>{disp}</span>
                    </div>
                  );
                })()}
                <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}><b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Inmobiliaria</b>
                  <input type="text" value={finDraft.inmobiliaria || ""} onChange={(e) => setFinDraft({ ...finDraft, inmobiliaria: e.target.value })} style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, border: "1px solid #94a3b8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }} />
                </label>
                <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}><b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Proyecto</b>
                  <input type="text" value={finDraft.proyecto || ""} onChange={(e) => setFinDraft({ ...finDraft, proyecto: e.target.value })} style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, border: "1px solid #94a3b8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }} />
                </label>
                <label style={{ fontSize: 12, gridColumn: "1 / -1", color: "#be123c", fontWeight: 700 }}><b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Tipo de operación</b>
                  <select value={finDraft.con_subsidio ? "con" : "sin"} onChange={(e) => setFinDraft({ ...finDraft, con_subsidio: e.target.value === "con" })} style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, border: "1px solid #94a3b8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }}>
                    <option value="con">CON subsidio (DS1 / DS19)</option>
                    <option value="sin">SIN subsidio</option>
                  </select>
                </label>
                <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}><b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Tipo propiedad</b>
                  <select value={finDraft.tipo_propiedad || ""} onChange={(e) => setFinDraft({ ...finDraft, tipo_propiedad: e.target.value })} style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, border: "1px solid #94a3b8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }}>
                    <option value="">— seleccionar —</option>
                    <option value="Departamento">Departamento</option>
                    <option value="Casa">Casa</option>
                    <option value="Terreno">Terreno</option>
                    <option value="Oficina">Oficina</option>
                    <option value="Estacionamiento">Estacionamiento</option>
                    <option value="Bodega">Bodega</option>
                  </select>
                </label>
                <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}><b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Fecha de entrega</b>
                  <select value={finDraft.fecha_entrega || ""} onChange={(e) => setFinDraft({ ...finDraft, fecha_entrega: e.target.value })} data-testid="fin-fecha-entrega-detail" style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, border: "1px solid #94a3b8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }}>
                    <option value="">— seleccionar —</option>
                    <option value="inmediata">Inmediata</option>
                    <option value="futura">Futura</option>
                  </select>
                </label>
                <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}><b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Valor propiedad (UF)</b>
                  <input type="number" step="0.01" value={finDraft.valor_propiedad || ""} onChange={(e) => setFinDraft({ ...finDraft, valor_propiedad: e.target.value })} style={{ width: "100%", padding: "0.35rem", borderRadius: 0, border: "1px solid #d4d4d8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }} />
                </label>
                {finDraft.con_subsidio && (
                  <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}><b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Subsidio (UF)</b>
                    <input type="number" step="0.01" value={finDraft.monto_subsidio || ""} onChange={(e) => setFinDraft({ ...finDraft, monto_subsidio: e.target.value })} style={{ width: "100%", padding: "0.35rem", borderRadius: 0, border: "1px solid #d4d4d8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }} />
                  </label>
                )}
                {finDraft.con_subsidio && (
                  <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}><b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Ahorro (UF)</b>
                    <input type="number" step="0.01" value={finDraft.ahorro || ""} onChange={(e) => setFinDraft({ ...finDraft, ahorro: e.target.value })} style={{ width: "100%", padding: "0.35rem", borderRadius: 0, border: "1px solid #d4d4d8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }} />
                  </label>
                )}
                {!finDraft.con_subsidio && (
                  <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}><b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Pie (UF)</b>
                    <input type="number" step="0.01" value={finDraft.monto_pie || ""} onChange={(e) => setFinDraft({ ...finDraft, monto_pie: e.target.value })} style={{ width: "100%", padding: "0.35rem", borderRadius: 0, border: "1px solid #d4d4d8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }} />
                  </label>
                )}
                <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}><b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Monto crédito (UF)</b>
                  <input type="number" step="0.01" value={finDraft.monto_credito || ""} onChange={(e) => setFinDraft({ ...finDraft, monto_credito: e.target.value })} style={{ width: "100%", padding: "0.35rem", borderRadius: 0, border: "1px solid #d4d4d8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }} />
                </label>
                <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}><b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Reserva (UF)</b>
                  <input type="number" step="0.01" value={finDraft.monto_reserva || ""} onChange={(e) => setFinDraft({ ...finDraft, monto_reserva: e.target.value })} style={{ width: "100%", padding: "0.35rem", borderRadius: 0, border: "1px solid #d4d4d8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }} />
                </label>
              </div>
              <div style={{ marginTop: 10 }}>
                <ConversorUF style={{ background: "#fefce8", border: "1px solid #d4af37", color: "#1a1f2e" }} />
              </div>
              {(() => {
                const vp = Number(finDraft.valor_propiedad || 0);
                const ms = Number(finDraft.monto_subsidio || 0);
                const ah = Number(finDraft.ahorro || 0);
                const rs = Number(finDraft.monto_reserva || 0);
                const mp = Number(finDraft.monto_pie || 0);
                const mc = Number(finDraft.monto_credito || 0);
                const suma = finDraft.con_subsidio ? (ms + ah + rs + mc) : (mp + rs + mc);
                const diff = vp - suma;
                if (vp === 0 || suma === 0) return null;
                const ok = Math.abs(diff) < 1;
                // Regla 80% SIN subsidio: crédito no puede exceder 80% del valor propiedad
                const max80 = vp * 0.8;
                const excedeMax = !finDraft.con_subsidio && mc > 0 && mc > max80 + 0.01;
                const pctCredito = vp > 0 ? (mc / vp) * 100 : 0;
                return (
                  <div style={{ marginTop: 8, display: "grid", gap: 6 }}>
                    <div style={{ padding: "0.7rem 0.9rem", borderRadius: 0, background: ok ? "#dcfce7" : "#fee2e2", color: ok ? "#166534" : "#991b1b", fontSize: 14.5, fontWeight: 700, lineHeight: 1.45 }}>
                      {ok
                        ? `✅ Suma cuadra: ${suma.toFixed(2)} UF = ${vp.toFixed(2)} UF`
                        : `⚠️ Diferencia: ${diff.toFixed(2)} UF (suma actual: ${suma.toFixed(2)} vs valor propiedad: ${vp.toFixed(2)}). ${finDraft.con_subsidio ? 'Subsidio + Ahorro + Reserva + Crédito' : 'Pie + Reserva + Crédito'} debe = Valor propiedad.`}
                    </div>
                    {!finDraft.con_subsidio && mc > 0 && (
                      <div style={{ padding: "0.6rem 0.8rem", borderRadius: 0, background: excedeMax ? "#fee2e2" : "#e0f2fe", color: excedeMax ? "#991b1b" : "#075985", fontSize: 13.5, fontWeight: 600, lineHeight: 1.45 }}>
                        {excedeMax
                          ? `🚫 Crédito ${mc.toFixed(2)} UF supera el 80% máximo (${max80.toFixed(2)} UF) — SIN subsidio no permite más del 80% del valor propiedad. Actual: ${pctCredito.toFixed(1)}%.`
                          : `📊 Crédito representa ${pctCredito.toFixed(1)}% del valor propiedad (máximo permitido SIN subsidio: 80% = ${max80.toFixed(2)} UF).`}
                      </div>
                    )}
                  </div>
                );
              })()}
              <div style={{ marginTop: 8, fontSize: 11, opacity: 0.75 }}>
                💡 Si dejaste campos vacíos, hacé click en "Autodetectar con IA" para que Claude lea los PDFs adjuntos y complete lo que pueda.
              </div>
            </div>
          )}

          {currentFolder.codeudor_nombre && (
            <div className="clientes-codeudor-badge">
              <i className="fa fa-user-plus"></i> Codeudor: {currentFolder.codeudor_nombre} {currentFolder.codeudor_rut && `(${currentFolder.codeudor_rut})`}
            </div>
          )}

          <div className="clientes-files-list">
            {(!currentFolder.archivos || currentFolder.archivos.length === 0) && (
              <div className="clientes-empty">
                <i className="fa fa-file-o"></i>
                <p>Carpeta vacía. Use "Buscar Adjuntos" para traer archivos del correo.</p>
              </div>
            )}
            {(() => {
              const esCod = (a) => a.subfolder === "05_codeudor" || /^CODEUDOR_/i.test(a.nombre || "");
              const esEstudio = (a) => (a.subfolder || "").startsWith("07_estudio_titulo");
              const titularFiles = (currentFolder.archivos || []).filter(a => !esCod(a) && !esEstudio(a));
              const codFiles = (currentFolder.archivos || []).filter(esCod);
              const estudioFiles = (currentFolder.archivos || []).filter(a => esEstudio(a) && !esCod(a));
              const renderFile = (file, i) => (
              <div key={file.ruta || i} className="clientes-file-item" data-testid={`file-${i}`}>
                <i className={`fa ${file.nombre.endsWith('.pdf') ? 'fa-file-pdf-o' : file.nombre.match(/\.(jpg|png|jpeg)$/i) ? 'fa-file-image-o' : file.nombre.match(/\.(doc|docx)$/i) ? 'fa-file-word-o' : 'fa-file-o'}`}></i>
                <div className="clientes-file-info">
                  <span className="clientes-file-name">{file.nombre}</span>
                  {file.subfolder && <span className="clientes-file-subfolder">{file.subfolder}/</span>}
                  <span className="clientes-file-size">{formatSize(file.tamano)}</span>
                </div>
                <button
                  className="docs-btn secondary"
                  title="Ver / Preview"
                  onClick={() => openPreview(currentFolder.id, file.ruta, file.nombre)}
                  data-testid={`btn-preview-${i}`}
                  style={{ marginRight: 6 }}
                >
                  <i className="fa fa-eye"></i>
                </button>
                <button className="docs-btn secondary" title="Descargar" onClick={() => downloadFile(currentFolder.id, file.ruta)} data-testid={`btn-download-${i}`}>
                  <i className="fa fa-download"></i>
                </button>
                <button
                  className="docs-btn secondary"
                  title="Eliminar archivo"
                  data-testid={`btn-delete-file-${i}`}
                  onClick={async () => {
                    await deleteClientFile(currentFolder.id, file.ruta);
                    const r = await axios.get(`${API}/api/clientes/folders/${currentFolder.id}`);
                    setCurrentFolder(r.data);
                  }}
                  style={{ marginLeft: 6, color: "#be123c", borderColor: "#be123c" }}
                >
                  <i className="fa fa-trash"></i>
                </button>
              </div>
              );
              return (
                <>
                  {titularFiles.map(renderFile)}
                  {codFiles.length > 0 && (
                    <div data-testid="codeudor-subfolder" style={{ marginTop: 14, border: "1.5px dashed #2e5ce6", borderRadius: 0, padding: "10px 12px", background: "rgba(46,92,230,0.06)" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, color: "#1e46c0", fontWeight: 800, fontSize: 13 }}>
                        <i className="fa fa-folder"></i> Subcarpeta Codeudor{currentFolder.codeudor_nombre ? `: ${currentFolder.codeudor_nombre}` : ""}
                        <span style={{ fontWeight: 600, opacity: 0.7 }}>({codFiles.length} archivo{codFiles.length !== 1 ? "s" : ""})</span>
                      </div>
                      {codFiles.map((f2, j) => renderFile(f2, titularFiles.length + j))}
                    </div>
                  )}
                  {estudioFiles.length > 0 && (
                    <div data-testid="estudio-subfolder" style={{ marginTop: 14, border: "1.5px dashed #14b8a6", borderRadius: 0, padding: "10px 12px", background: "rgba(20,184,166,0.06)" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4, color: "#0d9488", fontWeight: 800, fontSize: 13 }}>
                        <i className="fa fa-balance-scale"></i> Carpeta Estudio de Título (separada)
                        <span style={{ fontWeight: 600, opacity: 0.7 }}>({estudioFiles.length} archivo{estudioFiles.length !== 1 ? "s" : ""})</span>
                      </div>
                      <div style={{ fontSize: 11, color: "#5eead4", marginBottom: 8 }}>
                        🔒 Regla inviolable: estos documentos pertenecen al Estudio de Título de la propiedad y NUNCA se combinan ni se envían con la solicitud de crédito.
                      </div>
                      {estudioFiles.map((f2, j) => renderFile(f2, titularFiles.length + codFiles.length + j))}
                    </div>
                  )}
                </>
              );
            })()}
          </div>
        </div>
      )}

      {/* EMAILS VIEW */}
      {view === "emails" && (
        <div data-testid="clientes-emails">
          <div className="clientes-detail-header">
            <button className="docs-btn secondary" onClick={() => setView("list")} data-testid="btn-back-emails">
              <i className="fa fa-arrow-left"></i> Volver
            </button>
            <h3><i className="fa fa-envelope"></i> Correos - aprobaciones@centralmutuos.cl</h3>
          </div>

          <div className="clientes-email-search">
            <input type="text" placeholder="Buscar en correos..." value={emailSearch}
              onChange={e => setEmailSearch(e.target.value)}
              onKeyDown={e => e.key === "Enter" && searchEmails()}
              data-testid="email-search-input" />
            <button className="docs-btn primary" onClick={searchEmails} disabled={loading} data-testid="btn-search-emails">
              <i className={`fa ${loading ? "fa-spinner fa-spin" : "fa-search"}`}></i> Buscar
            </button>
          </div>

          <div className="clientes-email-list">
            {(emailResults.length > 0 ? emailResults : emails).map((em, i) => (
              <div key={i} className="clientes-email-item" data-testid={`email-${i}`}>
                <div className="clientes-email-header">
                  <span className="clientes-email-from">{em.from}</span>
                  <span className="clientes-email-date">{em.date}</span>
                </div>
                <div className="clientes-email-subject">{em.subject || "(Sin asunto)"}</div>
                <div className="clientes-email-body">{(em.body || em.body_preview || "").slice(0, 200)}</div>
                {em.attachments?.length > 0 && (
                  <div className="clientes-email-attachments">
                    {em.attachments.map((att, j) => (
                      <span key={j} className="clientes-attachment-badge">
                        <i className="fa fa-paperclip"></i> {att.filename || att}
                        {currentFolder && att.filename && (
                          <button className="clientes-save-att" onClick={() => saveAttachmentToFolder(em.id, att.filename)}
                            disabled={savingAttachment === `${em.id}-${att.filename}`}>
                            <i className={`fa ${savingAttachment === `${em.id}-${att.filename}` ? "fa-spinner fa-spin" : "fa-save"}`}></i>
                          </button>
                        )}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {emails.length === 0 && emailResults.length === 0 && !loading && (
              <div className="clientes-empty"><i className="fa fa-envelope-o"></i><p>No se encontraron correos.</p></div>
            )}
          </div>
        </div>
      )}

      {/* AJUSTES VIEW - clasificación de solicitudes de crédito */}
      {view === "ajustes" && (
        <div data-testid="clientes-ajustes">
          <div className="clientes-detail-header">
            <button className="docs-btn secondary" onClick={() => setView("list")}>
              <i className="fa fa-arrow-left"></i> Volver
            </button>
            <h3><i className="fa fa-sliders"></i> Ajustes — Clasificación de Solicitudes de Crédito</h3>
            <button className="docs-btn secondary" onClick={updateUf} data-testid="btn-uf-update" title="Valor actual de la UF"
              style={{ background: "rgba(250,204,21,0.15)", border: "1px solid rgba(250,204,21,0.5)", color: "#facc15" }}>
              <i className="fa fa-line-chart"></i> UF: ${ufValue.toLocaleString('es-CL')}
            </button>
            <button className="docs-btn secondary" onClick={loadAjustes}>
              <i className="fa fa-refresh"></i> Refrescar
            </button>
          </div>
          <div style={{ padding: "1rem", background: "rgba(212,175,55,0.08)", border: "1px solid #d4af37", borderRadius: 0, marginBottom: "1rem", fontSize: "0.88rem", lineHeight: 1.6 }}>
            <b>Reglas activas:</b><br/>
            Un correo se clasifica como <b>solicitud de crédito</b> si menciona «solicitud de crédito/financiamiento» O trae ≥3 documentos típicos (cédula, liquidaciones, AFP, CMF, impuesto renta, boletas honorarios).<br/>
            <b>Tipo cliente</b>: dependiente (liquidación+AFP) · independiente (impuesto renta+boletas).<br/>
            <b>Subsidio</b>: si no dice nada → sin subsidio, LTV 80% del valor propiedad.<br/>
            <b>Codeudor</b>: detectado por keyword "codeudor/aval" en asunto o cuerpo → subcarpeta con su nombre.<br/>
            <b>Estructura</b>: cada carpeta cliente tiene subcarpetas ordenadas (01_cedula, 02_liquidaciones o 02_impuesto_renta, 03_afp o 03_boletas..., 04_cmf, 99_otros).
          </div>
          {ajustes.length === 0 ? (
            <div className="clientes-empty">
              <i className="fa fa-inbox"></i>
              <p>Todavía no hay solicitudes clasificadas. Cuando el módulo <b>Procesamiento Correo</b> archive un correo con «Guardar en Carpeta Cliente», aparecerá acá.</p>
            </div>
          ) : (
            <div style={{ display: "grid", gap: "0.8rem" }}>
              {ajustes.map(f => {
                const cr = f.credit_request || {};
                const sub = cr.subsidy || {};
                const cod = cr.codeudor || {};
                const isEditing = editingId === f.id;
                return (
                  <div key={f.id} className="clientes-card" style={{ padding: "1rem", flexDirection: "column", alignItems: "stretch", borderLeft: cr.manual_override ? "3px solid #2e5ce6" : "" }} data-testid={`ajuste-${f.id}`}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem", gap: "0.5rem", flexWrap: "wrap" }}>
                      <h4 style={{ margin: 0 }}>
                        <i className="fa fa-user"></i> {f.nombre}
                        {f.rut && <small style={{ opacity: 0.6 }}> ({f.rut})</small>}
                        {cr.manual_override && (
                          <span data-testid={`manual-badge-${f.id}`} style={{ background: "#ede9fe", color: "#6d28d9", padding: "2px 8px", borderRadius: 0, fontSize: 11, fontWeight: 700, marginLeft: 8 }}>
                            <i className="fa fa-pencil" style={{ marginRight: 4 }} />editado manualmente
                          </span>
                        )}
                      </h4>
                      {!isEditing && (
                        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                          <span style={{ background: cr.is_request ? "#dcfce7" : "#fee2e2", color: cr.is_request ? "#166534" : "#991b1b", padding: "2px 8px", borderRadius: 0, fontSize: 12, fontWeight: 700 }}>
                            {cr.is_request ? "✓ Solicitud" : "✗ No"}
                          </span>
                          <span style={{ background: "#fef3c7", color: "#92400e", padding: "2px 8px", borderRadius: 0, fontSize: 12 }}>{cr.client_type || "?"}</span>
                          <span style={{ background: "#e0e7ff", color: "#3730a3", padding: "2px 8px", borderRadius: 0, fontSize: 12 }}>{sub.tipo || "?"}</span>
                          {cod.has_codeudor && <span style={{ background: "#fce7f3", color: "#9d174d", padding: "2px 8px", borderRadius: 0, fontSize: 12 }}>+ codeudor {cod.name || "s/n"}</span>}
                          <button className="docs-btn secondary" style={{ padding: "0.3rem 0.6rem", fontSize: 12 }} onClick={() => startEdit(f)} data-testid={`btn-edit-${f.id}`}>
                            <i className="fa fa-pencil" /> Editar
                          </button>
                          <button className="docs-btn secondary" style={{ padding: "0.3rem 0.6rem", fontSize: 12, background: "#d4af37", color: "#fff", border: "none" }} onClick={() => openFinPanel(f)} data-testid={`btn-fin-${f.id}`}>
                            <i className="fa fa-dollar" /> Datos financieros
                          </button>
                          {cr.manual_override && (
                            <button className="docs-btn secondary" style={{ padding: "0.3rem 0.6rem", fontSize: 12, color: "#e11d48" }} onClick={() => resetEdit(f.id)} data-testid={`btn-reset-${f.id}`}>
                              <i className="fa fa-undo" /> Volver a auto
                            </button>
                          )}
                        </div>
                      )}
                    </div>

                    {isEditing && (
                      <div data-testid={`edit-form-${f.id}`} style={{ background: "rgba(46,92,230,0.08)", border: "1px solid #2e5ce6", borderRadius: 0, padding: "0.9rem", marginBottom: "0.6rem", display: "grid", gap: "0.7rem", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
                        <label style={{ fontSize: 12 }}>
                          <b style={{ display: "block", marginBottom: 4 }}>¿Es solicitud?</b>
                          <select value={editDraft.is_request ? "si" : "no"} onChange={(e) => setEditDraft({ ...editDraft, is_request: e.target.value === "si" })} data-testid={`edit-is-request-${f.id}`} style={{ width: "100%", padding: "0.35rem", borderRadius: 0, border: "1px solid #d4d4d8" }}>
                            <option value="si">Sí, es solicitud</option>
                            <option value="no">No es solicitud</option>
                          </select>
                        </label>
                        <label style={{ fontSize: 12 }}>
                          <b style={{ display: "block", marginBottom: 4 }}>Tipo de cliente</b>
                          <select value={editDraft.client_type} onChange={(e) => setEditDraft({ ...editDraft, client_type: e.target.value })} data-testid={`edit-client-type-${f.id}`} style={{ width: "100%", padding: "0.35rem", borderRadius: 0, border: "1px solid #d4d4d8" }}>
                            <option value="dependiente">Dependiente (liquidación + AFP)</option>
                            <option value="independiente">Independiente (impuesto renta + boletas)</option>
                            <option value="desconocido">Desconocido / Por revisar</option>
                          </select>
                        </label>
                        <label style={{ fontSize: 12 }}>
                          <b style={{ display: "block", marginBottom: 4 }}>Subsidio</b>
                          <select value={editDraft.subsidy_tipo} onChange={(e) => setEditDraft({ ...editDraft, subsidy_tipo: e.target.value })} data-testid={`edit-subsidy-${f.id}`} style={{ width: "100%", padding: "0.35rem", borderRadius: 0, border: "1px solid #d4d4d8" }}>
                            <option value="con_subsidio">Con subsidio (DS1 / DS19)</option>
                            <option value="sin_subsidio">Sin subsidio</option>
                          </select>
                        </label>
                        <label style={{ fontSize: 12 }}>
                          <b style={{ display: "block", marginBottom: 4 }}>Codeudor</b>
                          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                            <input type="checkbox" checked={!!editDraft.codeudor_has} onChange={(e) => setEditDraft({ ...editDraft, codeudor_has: e.target.checked })} data-testid={`edit-codeudor-has-${f.id}`} />
                            <input type="text" placeholder="Nombre codeudor" value={editDraft.codeudor_name || ""} onChange={(e) => setEditDraft({ ...editDraft, codeudor_name: e.target.value, codeudor_has: true })} data-testid={`edit-codeudor-name-${f.id}`} style={{ flex: 1, padding: "0.35rem", borderRadius: 0, border: "1px solid #d4d4d8", fontSize: 12 }} />
                          </div>
                        </label>
                        <div style={{ gridColumn: "1 / -1", display: "flex", gap: 8, justifyContent: "flex-end" }}>
                          <button className="docs-btn secondary" onClick={cancelEdit} data-testid={`btn-cancel-${f.id}`} disabled={savingEdit}>
                            <i className="fa fa-times" /> Cancelar
                          </button>
                          <button className="docs-btn" style={{ background: "#2e5ce6", color: "#fff" }} onClick={() => saveEdit(f.id)} data-testid={`btn-save-${f.id}`} disabled={savingEdit}>
                            <i className="fa fa-check" /> {savingEdit ? "Guardando..." : "Guardar"}
                          </button>
                        </div>
                      </div>
                    )}

                    <div style={{ fontSize: 12, opacity: 0.75, marginBottom: "0.5rem" }}>
                      docs detectados: {(cr.doc_categories || []).join(", ") || "ninguno"} · matched: {cr.matched_keyword || "—"}
                    </div>

                    {/* ARCHIVOS TOOLBAR */}
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 6, padding: "0.4rem 0.6rem", background: "rgba(14,14,16,0.4)", borderRadius: 0, border: "1px solid rgba(148,163,184,0.15)" }}>
                      <span style={{ fontSize: 12, opacity: 0.85, marginRight: "auto", alignSelf: "center" }}>
                        <i className="fa fa-files-o" /> Archivos {selectionCount(f.id) > 0 && <span style={{ color: "#facc15" }}>· {selectionCount(f.id)} seleccionados</span>}
                      </span>
                      <button
                        onClick={() => triggerUpload(f.id, "")}
                        data-testid={`btn-upload-file-${f.id}`}
                        disabled={uploadingFor === f.id}
                        style={{ background: "rgba(16,217,142,0.15)", border: "1px solid rgba(16,217,142,0.5)", color: "#34eab9", borderRadius: 0, padding: "4px 10px", cursor: "pointer", fontSize: 12 }}
                        title="Subir archivo manualmente"
                      >
                        <i className={`fa ${uploadingFor === f.id ? "fa-spinner fa-spin" : "fa-plus"}`} /> Agregar archivo
                      </button>
                      <button
                        onClick={() => agregarCodeudor(f)}
                        data-testid={`btn-agregar-codeudor-${f.id}`}
                        style={{ background: "rgba(251,146,60,0.15)", border: "1px solid rgba(251,146,60,0.5)", color: "#fdba74", borderRadius: 0, padding: "4px 10px", cursor: "pointer", fontSize: 12 }}
                        title="Crear subcarpeta del codeudor y subir sus archivos"
                      >
                        <i className="fa fa-user-plus" /> Agregar Codeudor
                      </button>
                      <button
                        onClick={() => mergeByProtocol(f)}
                        data-testid={`btn-merge-proto-${f.id}`}
                        disabled={mergingProto === f.id}
                        style={{ background: "rgba(250,204,21,0.15)", border: "1px solid rgba(250,204,21,0.5)", color: "#facc15", borderRadius: 0, padding: "4px 10px", cursor: "pointer", fontSize: 12, fontWeight: 600 }}
                        title="Combinar TODOS los archivos siguiendo el orden del protocolo"
                      >
                        <i className={`fa ${mergingProto === f.id ? "fa-spinner fa-spin" : "fa-list-ol"}`} /> Combinar por Protocolo
                      </button>
                      <button
                        onClick={() => mergeSelected(f.id)}
                        data-testid={`btn-merge-${f.id}`}
                        disabled={merging || selectionCount(f.id) < 1}
                        style={{ background: "rgba(46,92,230,0.15)", border: "1px solid rgba(46,92,230,0.5)", color: "#c084fc", borderRadius: 0, padding: "4px 10px", cursor: selectionCount(f.id) < 1 ? "not-allowed" : "pointer", opacity: selectionCount(f.id) < 1 ? 0.5 : 1, fontSize: 12 }}
                        title="Combinar PDFs seleccionados en un único archivo"
                      >
                        <i className={`fa ${merging ? "fa-spinner fa-spin" : "fa-object-group"}`} /> Combinar PDFs
                      </button>
                      <button
                        onClick={() => openEmailModal(f)}
                        data-testid={`btn-send-email-${f.id}`}
                        style={{ background: "rgba(212,175,55,0.18)", border: "1px solid rgba(212,175,55,0.5)", color: "#d4af37", borderRadius: 0, padding: "4px 10px", cursor: "pointer", fontSize: 12 }}
                        title="Generar y enviar correo con antecedentes"
                      >
                        <i className="fa fa-paper-plane" /> Enviar correo
                      </button>
                      {selectionCount(f.id) > 0 && (
                        <button
                          onClick={() => clearSelection(f.id)}
                          style={{ background: "transparent", border: "1px solid rgba(148,163,184,0.3)", color: "#94a3b8", borderRadius: 0, padding: "4px 10px", cursor: "pointer", fontSize: 11 }}
                          title="Limpiar selección"
                        >
                          <i className="fa fa-times" /> Limpiar
                        </button>
                      )}
                    </div>

                    {finOpenId === f.id && (
                      <div data-testid={`fin-panel-${f.id}`} style={{ background: "rgba(212,175,55,0.08)", border: "1px solid #d4af37", borderRadius: 0, padding: "0.9rem", marginBottom: "0.6rem" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
                          <h5 style={{ margin: 0, color: "#b8942e" }}><i className="fa fa-dollar" /> Datos financieros del cliente</h5>
                          <div style={{ display: "flex", gap: 6 }}>
                            <button className="docs-btn secondary" onClick={() => runOcrFin(f.id)} data-testid={`btn-ocr-${f.id}`} disabled={ocrRunning || finSaving} style={{ background: "#1e46c0", color: "#fff", border: "none", padding: "0.35rem 0.7rem", fontSize: 12 }}>
                              <i className="fa fa-magic" /> {ocrRunning ? "Leyendo PDFs..." : "Leer con OCR"}
                            </button>
                            <button className="docs-btn secondary" onClick={closeFinPanel} disabled={ocrRunning || finSaving} style={{ padding: "0.35rem 0.7rem", fontSize: 12 }}>Cerrar</button>
                          </div>
                        </div>
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "0.5rem" }}>
                          <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}>
                            <b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Cliente</b>
                            <input type="text" value={f.nombre} readOnly style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, background: "#f1f5f9", border: "1px solid #94a3b8", fontSize: 13, color: "#000", fontWeight: 600 }} />
                          </label>
                          <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}>
                            <b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>RUT</b>
                            <input type="text" value={f.rut || ""} readOnly style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, background: "#f1f5f9", border: "1px solid #94a3b8", fontSize: 13, color: "#000", fontWeight: 600 }} />
                          </label>
                          <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}>
                            <b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Proyecto</b>
                            <input type="text" value={finDraft.proyecto || ""} onChange={(e) => setFinDraft({ ...finDraft, proyecto: e.target.value })} data-testid={`fin-proyecto-${f.id}`} style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, border: "1px solid #94a3b8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }} />
                          </label>
                          <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}>
                            <b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Inmobiliaria</b>
                            <input type="text" value={finDraft.inmobiliaria || ""} onChange={(e) => setFinDraft({ ...finDraft, inmobiliaria: e.target.value })} data-testid={`fin-inmobiliaria-${f.id}`} style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, border: "1px solid #94a3b8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }} />
                          </label>
                          <label style={{ fontSize: 12, gridColumn: "1 / -1", color: "#be123c", fontWeight: 700 }}>
                            <b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Tipo de operación</b>
                            <select value={finDraft.con_subsidio ? "con" : "sin"} onChange={(e) => setFinDraft({ ...finDraft, con_subsidio: e.target.value === "con" })} data-testid={`fin-subsidy-${f.id}`} style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, border: "1px solid #94a3b8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }}>
                              <option value="con">CON subsidio (DS1 / DS19)</option>
                              <option value="sin">SIN subsidio</option>
                            </select>
                          </label>
                          <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}>
                            <b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Tipo propiedad</b>
                            <select value={finDraft.tipo_propiedad || ""} onChange={(e) => setFinDraft({ ...finDraft, tipo_propiedad: e.target.value })} data-testid={`fin-tipo-prop-${f.id}`} style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, border: "1px solid #94a3b8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }}>
                              <option value="">— seleccioná —</option>
                              <option value="Departamento">Departamento</option>
                              <option value="Casa">Casa</option>
                              <option value="Terreno">Terreno</option>
                              <option value="Oficina">Oficina</option>
                              <option value="Estacionamiento">Estacionamiento</option>
                              <option value="Bodega">Bodega</option>
                            </select>
                          </label>
                          <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}>
                            <b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Fecha de entrega</b>
                            <select value={finDraft.fecha_entrega || ""} onChange={(e) => setFinDraft({ ...finDraft, fecha_entrega: e.target.value })} data-testid={`fin-fecha-entrega-${f.id}`} style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, border: "1px solid #94a3b8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }}>
                              <option value="">— seleccioná —</option>
                              <option value="inmediata">Inmediata</option>
                              <option value="futura">Futura</option>
                            </select>
                          </label>
                          <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}>
                            <b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Valor propiedad (UF)</b>
                            <UFAmountInput value={finDraft.valor_propiedad} onChange={(v) => setFinDraft({ ...finDraft, valor_propiedad: v })} uf={ufValue} dataTestid={`fin-valor-${f.id}`} />
                          </label>
                          {finDraft.con_subsidio && (
                            <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}>
                              <b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Monto subsidio (UF)</b>
                              <UFAmountInput value={finDraft.monto_subsidio} onChange={(v) => setFinDraft({ ...finDraft, monto_subsidio: v })} uf={ufValue} dataTestid={`fin-subsidio-${f.id}`} />
                            </label>
                          )}
                          {finDraft.con_subsidio && (
                            <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}>
                              <b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Ahorro (UF)</b>
                              <UFAmountInput value={finDraft.ahorro} onChange={(v) => setFinDraft({ ...finDraft, ahorro: v })} uf={ufValue} dataTestid={`fin-ahorro-${f.id}`} />
                            </label>
                          )}
                          {!finDraft.con_subsidio && (
                            <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}>
                              <b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Pie (UF)</b>
                              <UFAmountInput value={finDraft.monto_pie} onChange={(v) => setFinDraft({ ...finDraft, monto_pie: v })} uf={ufValue} dataTestid={`fin-pie-${f.id}`} />
                            </label>
                          )}
                          <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}>
                            <b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Monto del crédito (UF)</b>
                            <UFAmountInput value={finDraft.monto_credito} onChange={(v) => setFinDraft({ ...finDraft, monto_credito: v })} uf={ufValue} dataTestid={`fin-credito-${f.id}`} />
                          </label>
                          <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}>
                            <b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Reserva (UF)</b>
                            <UFAmountInput value={finDraft.monto_reserva} onChange={(v) => setFinDraft({ ...finDraft, monto_reserva: v })} uf={ufValue} dataTestid={`fin-reserva-${f.id}`} />
                          </label>
                        </div>
                        <div style={{ marginTop: 10 }}>
                          <ConversorUF style={{ background: "#fefce8", border: "1px solid #d4af37", color: "#1a1f2e" }} />
                        </div>
                        {(() => {
                          const vp = Number(finDraft.valor_propiedad || 0);
                          const ms = Number(finDraft.monto_subsidio || 0);
                          const ah = Number(finDraft.ahorro || 0);
                          const rs = Number(finDraft.monto_reserva || 0);
                          const mp = Number(finDraft.monto_pie || 0);
                          const mc = Number(finDraft.monto_credito || 0);
                          const suma = finDraft.con_subsidio ? (ms + ah + rs + mc) : (mp + rs + mc);
                          const diff = vp - suma;
                          if (vp === 0 || suma === 0) return null;
                          const ok = Math.abs(diff) < 1;
                          const max80 = vp * 0.8;
                          const excedeMax = !finDraft.con_subsidio && mc > 0 && mc > max80 + 0.01;
                          const pctCredito = vp > 0 ? (mc / vp) * 100 : 0;
                          return (
                            <div style={{ marginTop: 8, display: "grid", gap: 6 }}>
                              <div data-testid={`fin-sum-${f.id}`} style={{ padding: "0.7rem 0.9rem", borderRadius: 0, background: ok ? "#dcfce7" : "#fee2e2", color: ok ? "#166534" : "#991b1b", fontSize: 14.5, fontWeight: 700, lineHeight: 1.45 }}>
                                {ok
                                  ? `✅ Suma cuadra: ${suma.toFixed(2)} UF = ${vp.toFixed(2)} UF`
                                  : `⚠️ Diferencia: ${diff.toFixed(2)} UF (suma actual: ${suma.toFixed(2)} vs valor propiedad: ${vp.toFixed(2)}). ${finDraft.con_subsidio ? 'Subsidio + Ahorro + Reserva + Crédito' : 'Pie + Reserva + Crédito'} debe = Valor propiedad.`}
                              </div>
                              {!finDraft.con_subsidio && mc > 0 && (
                                <div data-testid={`fin-80pct-${f.id}`} style={{ padding: "0.6rem 0.8rem", borderRadius: 0, background: excedeMax ? "#fee2e2" : "#e0f2fe", color: excedeMax ? "#991b1b" : "#075985", fontSize: 13.5, fontWeight: 600, lineHeight: 1.45 }}>
                                  {excedeMax
                                    ? `🚫 Crédito ${mc.toFixed(2)} UF supera el 80% máximo (${max80.toFixed(2)} UF) — SIN subsidio no permite más del 80% del valor propiedad. Actual: ${pctCredito.toFixed(1)}%.`
                                    : `📊 Crédito representa ${pctCredito.toFixed(1)}% del valor propiedad (máximo permitido SIN subsidio: 80% = ${max80.toFixed(2)} UF).`}
                                </div>
                              )}
                            </div>
                          );
                        })()}
                        <div style={{ marginTop: "0.6rem", textAlign: "right" }}>
                          <button className="docs-btn" style={{ background: "#d4af37", color: "#fff", border: "none" }} onClick={() => saveFinPanel(f.id)} data-testid={`btn-fin-save-${f.id}`} disabled={finSaving || ocrRunning}>
                            <i className="fa fa-check" /> {finSaving ? "Guardando..." : "Guardar datos"}
                          </button>
                        </div>
                      </div>
                    )}
                    {(f.subfolders || []).map(s => (
                      <details key={s.name} style={{ background: "rgba(255,255,255,0.03)", borderRadius: 0, padding: "0.4rem 0.7rem", marginTop: 4 }}>
                        <summary style={{ cursor: "pointer", fontWeight: 600, fontSize: 13, display: "flex", alignItems: "center", gap: 6 }}>
                          <span><i className="fa fa-folder"></i> {s.name} ({s.files.length})</span>
                          <button
                            onClick={(e) => { e.preventDefault(); e.stopPropagation(); triggerUpload(f.id, s.name); }}
                            data-testid={`btn-upload-sub-${f.id}-${s.name}`}
                            style={{ marginLeft: "auto", background: "rgba(16,217,142,0.12)", border: "1px solid rgba(16,217,142,0.35)", color: "#34eab9", borderRadius: 0, padding: "1px 8px", cursor: "pointer", fontSize: 11 }}
                            title={`Subir archivo a ${s.name}`}
                          >
                            <i className="fa fa-plus" /> Aquí
                          </button>
                        </summary>
                        <ul style={{ margin: "0.4rem 0 0", paddingLeft: 8, fontSize: 12, listStyle: "none" }}>
                          {s.files.map(ff => {
                            const rel = `${s.name}/${ff.name}`;
                            const sel = isSelected(f.id, rel);
                            return (
                              <li key={ff.name} style={{ opacity: 0.9, display: "flex", alignItems: "center", gap: 6, padding: "3px 4px", background: sel ? "rgba(250,204,21,0.08)" : "transparent", borderRadius: 0 }}>
                                <input
                                  type="checkbox"
                                  checked={sel}
                                  onChange={() => toggleSelect(f.id, rel)}
                                  data-testid={`sel-${f.id}-${ff.name}`}
                                  style={{ cursor: "pointer", accentColor: "#facc15" }}
                                  title="Seleccionar para combinar / adjuntar"
                                />
                                <i className={`fa ${ff.name.toLowerCase().endsWith('.pdf') ? 'fa-file-pdf-o' : ff.name.match(/\.(jpg|png|jpeg|gif|webp)$/i) ? 'fa-file-image-o' : 'fa-file-o'}`} style={{ opacity: 0.7 }}></i>
                                <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{ff.name}</span>
                                <span style={{ opacity: 0.5, fontSize: 11 }}>{Math.round(ff.size / 1024)} KB</span>
                                <button
                                  title="Ver / Preview"
                                  onClick={() => openPreview(f.id, rel, ff.name)}
                                  data-testid={`aj-preview-${f.id}-${ff.name}`}
                                  style={{ background: "rgba(212,175,55,0.15)", border: "1px solid rgba(212,175,55,0.4)", color: "#d4af37", borderRadius: 0, padding: "2px 8px", cursor: "pointer", fontSize: 11 }}
                                >
                                  <i className="fa fa-eye"></i>
                                </button>
                                {ff.name.toLowerCase().endsWith(".pdf") && ff.size > 100000 && (
                                  <button
                                    title="Dividir PDF empaquetado por categoría (IA)"
                                    onClick={() => splitBundled(f.id, rel, ff.name)}
                                    disabled={splittingRel === rel}
                                    data-testid={`aj-split-${f.id}-${ff.name}`}
                                    style={{ background: "rgba(46,92,230,0.15)", border: "1px solid rgba(46,92,230,0.4)", color: "#c084fc", borderRadius: 0, padding: "2px 8px", cursor: "pointer", fontSize: 11 }}
                                  >
                                    <i className={`fa ${splittingRel === rel ? "fa-spinner fa-spin" : "fa-cut"}`}></i>
                                  </button>
                                )}
                                <button
                                  title="Descargar"
                                  onClick={() => downloadFile(f.id, rel)}
                                  data-testid={`aj-download-${f.id}-${ff.name}`}
                                  style={{ background: "rgba(148,163,184,0.15)", border: "1px solid rgba(148,163,184,0.4)", color: "#94a3b8", borderRadius: 0, padding: "2px 8px", cursor: "pointer", fontSize: 11 }}
                                >
                                  <i className="fa fa-download"></i>
                                </button>
                                <button
                                  title="Eliminar"
                                  onClick={() => deleteClientFile(f.id, rel)}
                                  data-testid={`aj-delete-${f.id}-${ff.name}`}
                                  style={{ background: "rgba(225,29,72,0.15)", border: "1px solid rgba(225,29,72,0.4)", color: "#fb7185", borderRadius: 0, padding: "2px 8px", cursor: "pointer", fontSize: 11 }}
                                >
                                  <i className="fa fa-trash"></i>
                                </button>
                              </li>
                            );
                          })}
                        </ul>
                      </details>
                    ))}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* PREVIEW MODAL */}
      {previewFile && (
        <div
          data-testid="preview-modal"
          onClick={closePreview}
          style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)",
            display: "flex", alignItems: "center", justifyContent: "center",
            zIndex: 9999, padding: "2vh 2vw",
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", color: "#e2e8f0",
              borderRadius: 0, boxShadow: "0 20px 60px rgba(0,0,0,0.6)",
              width: "min(1200px, 96vw)", height: "min(900px, 92vh)",
              display: "flex", flexDirection: "column", overflow: "hidden",
              border: "1px solid rgba(148,163,184,0.25)",
            }}
          >
            <div style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "0.6rem 0.9rem", borderBottom: "1px solid rgba(148,163,184,0.2)",
              background: "rgba(14,14,16,0.9)",
            }}>
              <i className={`fa ${previewFile.mime === "pdf" ? "fa-file-pdf-o" : previewFile.mime === "image" ? "fa-file-image-o" : "fa-file-o"}`} style={{ color: "#facc15" }} />
              <span style={{ flex: 1, fontWeight: 600, fontSize: 14, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{previewFile.name}</span>
              <a
                href={previewFile.url.replace("?inline=true", "")}
                target="_blank" rel="noreferrer"
                data-testid="preview-download-link"
                style={{ background: "rgba(148,163,184,0.15)", color: "#e2e8f0", padding: "5px 12px", borderRadius: 0, textDecoration: "none", fontSize: 12 }}
              >
                <i className="fa fa-download" /> Descargar
              </a>
              <button
                onClick={closePreview}
                data-testid="btn-preview-close"
                style={{ background: "rgba(225,29,72,0.2)", color: "#fda4af", border: "1px solid rgba(225,29,72,0.4)", borderRadius: 0, padding: "5px 12px", cursor: "pointer", fontSize: 12 }}
              >
                <i className="fa fa-times" /> Cerrar
              </button>
            </div>
            <div style={{ flex: 1, background: "#232326", overflow: "hidden" }}>
              {previewFile.mime === "pdf" && (
                <iframe title={previewFile.name} src={previewFile.url} style={{ width: "100%", height: "100%", border: "none", background: "#fff" }} />
              )}
              {previewFile.mime === "image" && (
                <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", overflow: "auto", background: "#0b1220" }}>
                  <img src={previewFile.url} alt={previewFile.name} style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }} />
                </div>
              )}
              {previewFile.mime === "text" && (
                <iframe title={previewFile.name} src={previewFile.url} style={{ width: "100%", height: "100%", border: "none", background: "#fff" }} />
              )}
              {previewFile.mime === "other" && (
                <div style={{ padding: "2rem", textAlign: "center", color: "#94a3b8" }}>
                  <i className="fa fa-file-o" style={{ fontSize: 48, opacity: 0.5, display: "block", marginBottom: 12 }} />
                  <p>Vista previa no disponible para este formato.</p>
                  <a href={previewFile.url.replace("?inline=true", "")} target="_blank" rel="noreferrer" style={{ color: "#d4af37", textDecoration: "underline" }}>
                    Descargar archivo
                  </a>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
      {/* HIDDEN FILE INPUT for manual upload */}
      <input
        ref={fileInputRef}
        type="file"
        style={{ display: "none" }}
        onChange={handleFileSelected}
        data-testid="hidden-file-input"
      />

      {/* EMAIL MODAL */}
      {tasacionModal && (() => {
        const m = tasacionModal;
        const set = (k, v) => setTasacionModal(prev => ({ ...prev, [k]: v, preview: null }));
        const inpS = { width: "100%", padding: "0.5rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.3)", background: "#232326", color: "#e2e8f0", fontSize: 13 };
        const lblS = { fontSize: 12 };
        return (
          <div data-testid="tasacion-modal" onClick={() => setTasacionModal(null)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9998, padding: "3vh 3vw" }}>
            <div onClick={(e) => e.stopPropagation()} style={{ background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", color: "#e2e8f0", borderRadius: 0, width: "min(760px, 96vw)", maxHeight: "94vh", overflow: "auto", border: "1px solid rgba(148,163,184,0.25)", boxShadow: "0 20px 60px rgba(0,0,0,0.6)" }}>
              <div style={{ padding: "0.9rem 1.1rem", borderBottom: "1px solid rgba(148,163,184,0.2)", display: "flex", alignItems: "center", gap: 10 }}>
                <i className="fa fa-home" style={{ color: "#fb923c" }} />
                <h4 style={{ margin: 0, flex: 1 }}>Solicitud de Tasación — {m.folder.nombre}</h4>
                <button onClick={() => setTasacionModal(null)} data-testid="btn-tasacion-close" style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: 18 }}><i className="fa fa-times" /></button>
              </div>
              <div style={{ padding: "1rem 1.1rem", display: "grid", gap: "0.75rem" }}>
                {m.msg && (
                  <div data-testid="tasacion-msg" style={{ padding: "0.6rem 0.9rem", borderRadius: 0, background: m.msg.startsWith("✅") ? "rgba(16,217,142,0.15)" : "rgba(225,29,72,0.15)", color: m.msg.startsWith("✅") ? "#34eab9" : "#fb7185", fontWeight: 600, fontSize: 13 }}>{m.msg}</div>
                )}
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Destinatarios <span style={{ color: "#34eab9" }}>· la tasación SIEMPRE va a Value Property y Victoria Vilches</span></b>
                  <input value={m.destinatarios} onChange={e => set("destinatarios", e.target.value)} data-testid="tasacion-destinatarios" style={inpS} />
                </label>
                <div style={{ background: "rgba(28,28,30,0.7)", borderRadius: 0, padding: "0.5rem 0.9rem", fontSize: 12, opacity: 0.85 }}>
                  Asunto: SOLICITUD TASACION // {m.folder.nombre}{m.folder.rut ? ` Rut: ${m.folder.rut}` : ""}
                </div>
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Texto inicial del correo (editable)</b>
                  <textarea value={m.intro} onChange={e => set("intro", e.target.value)} rows={2} placeholder={`Estimados, se envía solicitud de tasación para ${m.folder.nombre}...`} data-testid="tasacion-intro" style={{ ...inpS, resize: "vertical" }} />
                </label>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Canal / Tipo</b>
                    <select value={m.modalidad} onChange={e => set("modalidad", e.target.value)} data-testid="tasacion-modalidad" style={inpS}>
                      <option value="inmobiliaria">Vivienda nueva (inmobiliaria)</option>
                      <option value="broker">Broker</option>
                      <option value="usada">Vivienda usada (vendedor libre)</option>
                    </select>
                  </label>
                  <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Tipo de tasación</b>
                    <select value={m.tipo} onChange={e => set("tipo", e.target.value)} data-testid="tasacion-tipo" style={inpS}>
                      <option>Individual</option>
                      <option>Propiedad usada</option>
                      <option>Individual (proyecto con tasaciones previas)</option>
                    </select>
                  </label>
                </div>
                {m.modalidad === "inmobiliaria" && (
                  <div style={{ background: "rgba(46,92,230,0.08)", border: "1px solid rgba(46,92,230,0.3)", borderRadius: 0, padding: "0.7rem 0.9rem", display: "grid", gap: "0.6rem" }}>
                    <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Inmobiliaria <span style={{ opacity: 0.6 }}>(si ya tiene plantilla guardada, autocompleta el contacto)</span></b>
                      <input value={m.inmobiliaria} onChange={e => pickInmoPlantilla(e.target.value)} list="inmo-plantillas" placeholder="Ej: Ecomac" data-testid="tasacion-inmobiliaria" style={inpS} />
                      <datalist id="inmo-plantillas">
                        {tasacionContactos.map(c => <option key={c.inmobiliaria_key} value={c.inmobiliaria} />)}
                      </datalist>
                    </label>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.6rem" }}>
                      <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Contacto inmobiliaria (nombre)</b>
                        <input value={m.inmo_contacto_nombre} onChange={e => set("inmo_contacto_nombre", e.target.value)} placeholder="A quién se le solicita" data-testid="tasacion-inmo-nombre" style={inpS} />
                      </label>
                      <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Mail contacto inmobiliaria <span style={{ opacity: 0.6 }}>(se agrega al envío)</span></b>
                        <input value={m.inmo_contacto_email} onChange={e => set("inmo_contacto_email", e.target.value)} placeholder="contacto@inmobiliaria.cl" data-testid="tasacion-inmo-email" style={inpS} />
                      </label>
                    </div>
                    <div style={{ fontSize: 11, opacity: 0.7 }}>💾 Al enviar, el contacto queda guardado como plantilla para esta inmobiliaria (no se agrega a los destinatarios, va como contacto en el correo).</div>
                  </div>
                )}
                {m.modalidad === "broker" && (
                  <div style={{ background: "rgba(212,175,55,0.06)", border: "1px solid rgba(212,175,55,0.3)", borderRadius: 0, padding: "0.7rem 0.9rem", display: "grid", gap: "0.6rem" }}>
                    <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Broker <span style={{ opacity: 0.6 }}>(su contacto va en el correo, se puede editar abajo)</span></b>
                      <select value={m.broker_id} data-testid="tasacion-broker" style={inpS}
                        onChange={e => {
                          const b = brokers.find(x => x.id === e.target.value);
                          setTasacionModal(prev => ({ ...prev, preview: null, broker_id: e.target.value,
                            contacto_nombre: b ? (b.contactos || b.nombre) : prev.contacto_nombre,
                            contacto_email: b ? (b.emails || [])[0] || "" : prev.contacto_email }));
                        }}>
                        <option value="">— Seleccionar broker —</option>
                        {brokers.map(b => <option key={b.id} value={b.id}>{b.nombre}{b.contactos ? ` — ${b.contactos}` : ""}</option>)}
                      </select>
                    </label>
                    <BrokersPanel brokers={brokers} dest={""} setDest={() => {}} reloadBrokers={reloadBrokers} soloAdmin />
                  </div>
                )}
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Dirección de la propiedad <span style={{ color: "#fb7185" }}>*</span></b>
                  <input value={m.direccion} onChange={e => set("direccion", e.target.value)} placeholder="Ej: ELISA CORREA 527, LOS SAUCES, LA FLORIDA" data-testid="tasacion-direccion" style={inpS} />
                </label>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.75rem" }}>
                  <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>N° unidad / depto</b>
                    <input value={m.unidad} onChange={e => set("unidad", e.target.value)} placeholder="Ej: Depto 1204" data-testid="tasacion-unidad" style={inpS} />
                  </label>
                  <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Comuna</b>
                    <input value={m.comuna} onChange={e => set("comuna", e.target.value)} placeholder="Ej: La Florida" data-testid="tasacion-comuna" style={inpS} />
                  </label>
                  <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Ciudad</b>
                    <input value={m.ciudad} onChange={e => set("ciudad", e.target.value)} placeholder="Ej: Santiago" data-testid="tasacion-ciudad" style={inpS} />
                  </label>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.75rem" }}>
                  <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Rol de Avalúo Fiscal</b>
                    <input value={m.rol_avaluo} onChange={e => set("rol_avaluo", e.target.value)} placeholder="Ej: 12324-00005" data-testid="tasacion-rol" style={inpS} />
                  </label>
                  <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Valor aproximado (UF)</b>
                    <input value={m.valor_uf} onChange={e => set("valor_uf", e.target.value)} placeholder="Ej: 3.200" data-testid="tasacion-valor" style={inpS} />
                  </label>
                  <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Valor esperado tasación (UF)</b>
                    <input value={m.valor_esperado_uf} onChange={e => set("valor_esperado_uf", e.target.value)} placeholder="Ej: 3.200" data-testid="tasacion-valor-esperado" style={inpS} />
                  </label>
                </div>
                {!m.archivos.some(a => a.sel && /carta|oferta|aprobaci/i.test(a.nombre)) && (
                  <div data-testid="tasacion-sin-carta" style={{ fontSize: 12, color: "#facc15", background: "rgba(250,204,21,0.08)", border: "1px solid rgba(250,204,21,0.35)", borderRadius: 0, padding: "6px 10px" }}>
                    ⚠️ No hay <b>carta de aprobación</b> seleccionada en los adjuntos — la solicitud debe incluirla.
                  </div>
                )}
                <div style={{ background: "rgba(28,28,30,0.7)", borderRadius: 0, padding: "0.7rem 0.9rem", display: "grid", gap: "0.6rem" }}>
                  <div style={{ opacity: 0.8, fontSize: 11, textTransform: "uppercase", fontWeight: 700 }}>
                    {m.modalidad === "usada" ? "Contacto del vendedor (para que el tasador coordine)" : "Contacto para coordinar la visita del tasador"}
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.6rem" }}>
                    <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Nombre</b>
                      <input value={m.contacto_nombre} onChange={e => set("contacto_nombre", e.target.value)} placeholder={m.modalidad === "usada" ? "Nombre del vendedor" : "Quién recibe al tasador"} data-testid="tasacion-contacto-nombre" style={inpS} />
                    </label>
                    <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Teléfono</b>
                      <input value={m.contacto_telefono} onChange={e => set("contacto_telefono", e.target.value)} placeholder="+56 9 …" data-testid="tasacion-contacto-fono" style={inpS} />
                    </label>
                    <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Mail <span style={{ opacity: 0.6 }}>(opcional)</span></b>
                      <input value={m.contacto_email} onChange={e => set("contacto_email", e.target.value)} placeholder="contacto@correo.cl" data-testid="tasacion-contacto-email" style={inpS} />
                    </label>
                  </div>
                </div>
                <div style={{ background: "rgba(212,175,55,0.08)", border: "1px solid rgba(212,175,55,0.35)", borderRadius: 0, padding: "0.7rem 0.9rem", display: "grid", gap: "0.4rem" }}>
                  <div style={{ opacity: 0.85, fontSize: 11, textTransform: "uppercase", fontWeight: 700, color: "#d4af37" }}>Voucher de pago de la tasación</div>
                  <input type="file" accept=".pdf,.jpg,.jpeg,.png" data-testid="tasacion-voucher-input"
                    onChange={e => subirVoucher(e.target.files[0])} style={{ fontSize: 12 }} />
                  {m.voucher_nombre && <div style={{ fontSize: 12, color: "#34eab9" }}>✅ {m.voucher_nombre} — se adjunta y el correo dirá "Adjunto voucher de pago tasación"</div>}
                </div>
                <div style={{ background: "rgba(234,88,12,0.08)", border: "1px solid rgba(234,88,12,0.3)", borderRadius: 0, padding: "0.7rem 0.9rem", display: "flex", gap: 8, alignItems: "end", flexWrap: "wrap" }}>
                  <label style={{ ...lblS, flex: 1, minWidth: 200 }}><b style={{ display: "block", marginBottom: 4 }}>📅 Fecha de tasación informada por Value Property</b>
                    <input value={m.fecha_tasacion} onChange={e => setTasacionModal(prev => ({ ...prev, fecha_tasacion: e.target.value }))} placeholder="Aún sin fecha" data-testid="tasacion-fecha-vp" style={inpS} />
                  </label>
                  <button onClick={detectarFechaTasacion} disabled={m.loading} data-testid="btn-detectar-fecha" style={{ ...inpS, width: "auto", background: "#ea580c", border: "none", fontWeight: 700, cursor: "pointer" }}>
                    <i className="fa fa-magic" /> Detectar del correo
                  </button>
                  <button onClick={guardarFechaTasacion} disabled={m.loading} data-testid="btn-guardar-fecha" style={{ ...inpS, width: "auto", background: "#334155", border: "none", fontWeight: 700, cursor: "pointer" }}>
                    Guardar
                  </button>
                </div>
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Observaciones / antecedentes adicionales</b>
                  <textarea value={m.observaciones} onChange={e => set("observaciones", e.target.value)} rows={2} placeholder="Ej: Se adjunta carta oferta. Ya contamos con tasaciones de este proyecto." data-testid="tasacion-observaciones" style={{ ...inpS, resize: "vertical" }} />
                </label>
                {m.archivos.length > 0 && (
                  <div style={{ background: "rgba(28,28,30,0.7)", borderRadius: 0, padding: "0.7rem 0.9rem" }}>
                    <div style={{ opacity: 0.7, fontSize: 11, textTransform: "uppercase", marginBottom: 6 }}>Adjuntos — SOLO la carta de aprobación y el voucher pueden enviarse; el resto está bloqueado</div>
                    <div style={{ display: "grid", gap: 4, maxHeight: 140, overflow: "auto" }}>
                      {m.archivos.map((a, i) => {
                        const permitido = /carta|oferta|aprobaci|voucher/i.test(a.nombre) || a.ruta === m.voucher_ruta;
                        return (
                        <label key={a.ruta} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5, cursor: permitido ? "pointer" : "not-allowed", opacity: permitido ? 1 : 0.45 }}>
                          <input type="checkbox" checked={!!a.sel} disabled={!permitido} data-testid={`tasacion-adj-${i}`}
                            onChange={() => permitido && setTasacionModal(prev => ({ ...prev, preview: null, archivos: prev.archivos.map(x => x.ruta === a.ruta ? { ...x, sel: !x.sel } : x) }))} />
                          <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{a.nombre} <span style={{ opacity: 0.5 }}>{a.subfolder ? `(${a.subfolder})` : ""}</span>{!permitido && <span style={{ fontSize: 10, color: "#94a3b8" }}> 🔒</span>}</span>
                          <button type="button" data-testid={`tasacion-adj-ver-${i}`}
                            title={`Ver ${a.nombre}`}
                            onClick={(e) => { e.preventDefault(); e.stopPropagation(); openPreview(m.folder.id, a.ruta, a.nombre); }}
                            style={{ background: "rgba(212,175,55,0.15)", border: "1px solid #d4af37", color: "#d4af37", borderRadius: 0, padding: "2px 10px", fontSize: 11, fontWeight: 700, cursor: "pointer", flexShrink: 0, opacity: 1 }}>
                            <i className="fa fa-eye" /> Ver
                          </button>
                        </label>
                        );
                      })}
                    </div>
                  </div>
                )}
                {m.preview && (
                  <div style={{ background: "#fff", borderRadius: 0, padding: "0.9rem", maxHeight: 260, overflow: "auto" }}>
                    <div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(m.preview.body) }} />
                    {m.preview.attachments.length > 0 && (
                      <div style={{ marginTop: 8, fontSize: 12, color: "#334155" }}>📎 Adjuntos: {m.preview.attachments.join(", ")}</div>
                    )}
                  </div>
                )}
                <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
                  <button onClick={tasacionPreview} disabled={m.loading} data-testid="btn-tasacion-preview"
                    style={{ padding: "0.55rem 1.1rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.4)", background: "transparent", color: "#e2e8f0", fontWeight: 700, cursor: "pointer" }}>
                    <i className={`fa ${m.loading ? "fa-spinner fa-spin" : "fa-eye"}`} /> Ver preview
                  </button>
                  <button onClick={tasacionEnviar} disabled={m.loading || !m.direccion.trim()} data-testid="btn-tasacion-enviar"
                    title={!m.direccion.trim() ? "Falta la dirección de la propiedad" : ""}
                    style={{ padding: "0.55rem 1.1rem", borderRadius: 0, border: "none", background: "#ea580c", color: "#fff", fontWeight: 800, cursor: "pointer", opacity: (m.loading || !m.direccion.trim()) ? 0.6 : 1 }}>
                    <i className={`fa ${m.loading ? "fa-spinner fa-spin" : "fa-paper-plane"}`} /> Enviar solicitud
                  </button>
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {estudioModal && (() => {
        const m = estudioModal;
        const set = (k, v) => setEstudioModal(prev => ({ ...prev, [k]: v, preview: null }));
        const inpS = { width: "100%", padding: "0.5rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.3)", background: "#232326", color: "#e2e8f0", fontSize: 13 };
        const lblS = { fontSize: 12 };
        return (
          <div data-testid="estudio-modal" onClick={() => setEstudioModal(null)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9998, padding: "3vh 3vw" }}>
            <div onClick={(e) => e.stopPropagation()} style={{ background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", color: "#e2e8f0", borderRadius: 0, width: "min(760px, 96vw)", maxHeight: "94vh", overflow: "auto", border: "1px solid rgba(148,163,184,0.25)", boxShadow: "0 20px 60px rgba(0,0,0,0.6)" }}>
              <div style={{ padding: "0.9rem 1.1rem", borderBottom: "1px solid rgba(148,163,184,0.2)", display: "flex", alignItems: "center", gap: 10 }}>
                <i className="fa fa-balance-scale" style={{ color: "#2dd4bf" }} />
                <h4 style={{ margin: 0, flex: 1 }}>Solicitud de Estudio de Título — {m.folder.nombre}</h4>
                <button onClick={() => setEstudioModal(null)} data-testid="btn-estudio-close" style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: 18 }}><i className="fa fa-times" /></button>
              </div>
              <div style={{ padding: "1rem 1.1rem", display: "grid", gap: "0.75rem" }}>
                {m.msg && (
                  <div data-testid="estudio-msg" style={{ padding: "0.6rem 0.9rem", borderRadius: 0, background: m.msg.startsWith("✅") ? "rgba(16,217,142,0.15)" : "rgba(225,29,72,0.15)", color: m.msg.startsWith("✅") ? "#34eab9" : "#fb7185", fontWeight: 600, fontSize: 13 }}>{m.msg}</div>
                )}
                <div style={{ display: "flex", gap: 8, alignItems: "center", background: "rgba(212,175,55,0.06)", border: "1px solid rgba(212,175,55,0.25)", borderRadius: 0, padding: "0.5rem 0.9rem", flexWrap: "wrap" }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: "var(--gold, #d4af37)" }}>📋 Plantillas</span>
                  <select data-testid="estudio-plantilla-select" onChange={e => { if (e.target.value) aplicarPlantillaEstudio(e.target.value); e.target.value = ""; }}
                    style={{ ...inpS, width: "auto", flex: 1, minWidth: 180, padding: "5px 8px", fontSize: 12 }} defaultValue="">
                    <option value="">Aplicar plantilla guardada…</option>
                    {estudioPlantillas.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                  </select>
                  <button data-testid="estudio-plantilla-guardar" onClick={guardarPlantillaEstudio}
                    style={{ background: "rgba(212,175,55,0.15)", border: "1px solid rgba(212,175,55,0.5)", color: "#d4af37", borderRadius: 0, padding: "5px 12px", fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
                    💾 Guardar plantilla
                  </button>
                  {estudioPlantillas.length > 0 && (
                    <select data-testid="estudio-plantilla-eliminar" onChange={e => { if (e.target.value) eliminarPlantillaEstudio(e.target.value); e.target.value = ""; }}
                      style={{ ...inpS, width: "auto", padding: "5px 8px", fontSize: 12 }} defaultValue="">
                      <option value="">🗑 Eliminar…</option>
                      {estudioPlantillas.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                    </select>
                  )}
                </div>
                <button data-testid="estudio-enriquecer" onClick={() => enriquecerCarpeta(m.folder, "estudio")}
                  disabled={enriching === m.folder.id + "estudio"}
                  title="Busca en el correo (asunto, cuerpo y adjuntos) documentos del estudio de título y los guarda en 07_estudio_titulo. NUNCA se mezclan con los documentos de la solicitud de crédito."
                  style={{ background: "rgba(212,175,55,0.12)", border: "1.5px solid #d4af37", color: "#d4af37", borderRadius: 0, padding: "0.55rem 1rem", fontSize: 12.5, fontWeight: 800, cursor: "pointer", textAlign: "left" }}>
                  <i className={`fa ${enriching === m.folder.id + "estudio" ? "fa-spinner fa-spin" : "fa-magic"}`}></i> 🔎 Enriquecer archivos del Estudio de Título (busca en el correo · se guardan separados de la solicitud de crédito)
                </button>
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Destinatarios <span style={{ color: "#34eab9" }}>· broker seleccionado + Victoria Vilches siempre en copia</span></b>
                  <input value={m.destinatarios} onChange={e => set("destinatarios", e.target.value)} data-testid="estudio-destinatarios" style={inpS} />
                </label>
                <BrokersPanel brokers={brokers} dest={m.destinatarios} setDest={(v) => set("destinatarios", v)} reloadBrokers={reloadBrokers} />
                <div style={{ background: "rgba(28,28,30,0.5)", border: "1px solid rgba(148,163,184,0.2)", borderRadius: 0, padding: "0.6rem 0.9rem" }}>
                  <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Con copia (CC) <span style={{ color: "#d4af37" }}>· opcional — se mantienen informados en TODO el hilo del estudio (reparos, recordatorios y resolución)</span></b>
                    <input value={m.cc || ""} onChange={e => set("cc", e.target.value)} data-testid="estudio-cc" placeholder="correo1@ejemplo.cl, correo2@ejemplo.cl" style={inpS} />
                  </label>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                    {m.folder.source_email && !String(m.cc || "").toLowerCase().includes(String(m.folder.source_email).toLowerCase()) && (
                      <button data-testid="cc-add-cliente" onClick={() => set("cc", [m.cc, m.folder.source_email].filter(Boolean).join(", "))}
                        style={{ background: "rgba(16,217,142,0.12)", border: "1px solid rgba(16,217,142,0.4)", color: "#34eab9", borderRadius: 0, padding: "3px 10px", fontSize: 11.5, cursor: "pointer" }}>
                        + Cliente/Solicitante ({m.folder.source_email})
                      </button>
                    )}
                    {brokers.flatMap(b => (b.emails || []).map(em => ({ nombre: b.nombre, em })))
                      .filter(x => !String(m.cc || "").toLowerCase().includes(x.em.toLowerCase()))
                      .map((x, i) => (
                        <button key={i} data-testid={`cc-add-broker-${i}`} onClick={() => set("cc", [m.cc, x.em].filter(Boolean).join(", "))}
                          style={{ background: "rgba(212,175,55,0.12)", border: "1px solid rgba(212,175,55,0.4)", color: "#d4af37", borderRadius: 0, padding: "3px 10px", fontSize: 11.5, cursor: "pointer" }}>
                          + {x.nombre} ({x.em})
                        </button>
                      ))}
                  </div>
                </div>
                <div style={{ background: "rgba(28,28,30,0.7)", borderRadius: 0, padding: "0.5rem 0.9rem", fontSize: 12, opacity: 0.85 }}>
                  Asunto: SOLICITUD ESTUDIO DE TITULOS // {m.folder.nombre}{m.folder.rut ? ` ${m.folder.rut}` : ""}
                </div>
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Texto inicial del correo (editable)</b>
                  <textarea value={m.intro} onChange={e => set("intro", e.target.value)} rows={2} placeholder="Solicitamos dar inicio al estudio de títulos del cliente en referencia..." data-testid="estudio-intro" style={{ ...inpS, resize: "vertical" }} />
                </label>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Tipo de vivienda</b>
                    <select value={m.tipo_vivienda} data-testid="estudio-tipo" style={inpS}
                      onChange={e => {
                        const t = e.target.value;
                        setEstudioModal(prev => ({ ...prev, preview: null, tipo_vivienda: t,
                          docs_texto: ((t === "usada" ? prev.docs_usada : prev.docs_nueva) || []).join("\n") }));
                      }}>
                      <option value="nueva">Vivienda nueva (inmobiliaria)</option>
                      <option value="usada">Vivienda usada</option>
                    </select>
                  </label>
                  {m.tipo_vivienda === "nueva" ? (
                    <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Inmobiliaria / Proyecto <span style={{ opacity: 0.6 }}>(plantilla)</span></b>
                      <input value={m.inmobiliaria} list="inmo-plantillas-estudio" placeholder="Ej: Ecomac" data-testid="estudio-inmobiliaria" style={inpS}
                        onChange={e => {
                          const v = e.target.value;
                          const p = tasacionContactos.find(c => (c.inmobiliaria || "").toLowerCase() === v.toLowerCase());
                          setEstudioModal(prev => ({ ...prev, preview: null, inmobiliaria: v,
                            inmo_contacto_nombre: p ? (p.contacto_nombre || prev.inmo_contacto_nombre) : prev.inmo_contacto_nombre,
                            inmo_contacto_email: p ? (p.contacto_email || prev.inmo_contacto_email) : prev.inmo_contacto_email }));
                        }} />
                      <datalist id="inmo-plantillas-estudio">
                        {tasacionContactos.map(c => <option key={c.inmobiliaria_key} value={c.inmobiliaria} />)}
                      </datalist>
                    </label>
                  ) : <div />}
                </div>
                {m.tipo_vivienda === "nueva" && (
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.6rem" }}>
                    <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Contacto inmobiliaria (nombre)</b>
                      <input value={m.inmo_contacto_nombre} onChange={e => set("inmo_contacto_nombre", e.target.value)} placeholder="A quién se le solicita" data-testid="estudio-inmo-nombre" style={inpS} />
                    </label>
                    <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Mail contacto inmobiliaria <span style={{ opacity: 0.6 }}>(💾 se guarda como plantilla al enviar)</span></b>
                      <input value={m.inmo_contacto_email} onChange={e => set("inmo_contacto_email", e.target.value)} placeholder="contacto@inmobiliaria.cl" data-testid="estudio-inmo-email" style={inpS} />
                    </label>
                  </div>
                )}
                {m.tipo_vivienda === "usada" && (
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.6rem" }}>
                    <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Vendedor (nombre)</b>
                      <input value={m.vendedor_nombre} onChange={e => set("vendedor_nombre", e.target.value)} placeholder="Vendedor libre" data-testid="estudio-vendedor-nombre" style={inpS} />
                    </label>
                    <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Mail del vendedor</b>
                      <input value={m.vendedor_email} onChange={e => set("vendedor_email", e.target.value)} placeholder="vendedor@correo.cl" data-testid="estudio-vendedor-email" style={inpS} />
                    </label>
                    <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Teléfono <span style={{ opacity: 0.6 }}>(opcional)</span></b>
                      <input value={m.vendedor_telefono} onChange={e => set("vendedor_telefono", e.target.value)} placeholder="+56 9 …" data-testid="estudio-vendedor-fono" style={inpS} />
                    </label>
                  </div>
                )}
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Dirección de la propiedad</b>
                  <input value={m.direccion} onChange={e => set("direccion", e.target.value)} placeholder="Dirección completa" data-testid="estudio-direccion" style={inpS} />
                </label>
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>{m.tipo_vivienda === "usada" ? "Documentos solicitados para vivienda usada" : "Documentos obligatorios solicitados a la inmobiliaria (vivienda nueva)"} <span style={{ opacity: 0.6 }}>(uno por línea — se listan en el correo junto a la frase de reserva de antecedentes)</span></b>
                  <textarea value={m.docs_texto} onChange={e => set("docs_texto", e.target.value)} rows={8} data-testid="estudio-docs" style={{ ...inpS, resize: "vertical", fontSize: 12 }} />
                </label>
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Observaciones</b>
                  <textarea value={m.observaciones} onChange={e => set("observaciones", e.target.value)} rows={2} data-testid="estudio-observaciones" style={{ ...inpS, resize: "vertical" }} />
                </label>
                {m.archivos.length > 0 && (() => {
                  const esEst = (a) => (a.subfolder || "").startsWith("07_estudio_titulo");
                  const adjCredito = m.archivos.filter(a => !esEst(a));
                  const docsEstudio = m.archivos.filter(esEst);
                  return (
                  <>
                  {docsEstudio.length > 0 && (
                    <div data-testid="estudio-docs-recibidos" style={{ background: "rgba(20,184,166,0.08)", border: "1.5px dashed #14b8a6", borderRadius: 0, padding: "0.7rem 0.9rem" }}>
                      <div style={{ color: "#2dd4bf", fontSize: 11, textTransform: "uppercase", fontWeight: 800, marginBottom: 4 }}>
                        ⚖ Documentos del Estudio de Título recibidos ({docsEstudio.length})
                      </div>
                      <div style={{ fontSize: 11, color: "#5eead4", marginBottom: 6 }}>
                        Carpeta separada de la propiedad — NUNCA se mezclan con la solicitud de crédito. Usá "Enriquecer archivos" para seguir sumando los que lleguen por correo.
                      </div>
                      <button data-testid="btn-estudio-etapa2" onClick={() => enviarEtapa2(m)} disabled={m.loading}
                        title="Etapa 2: enviar al abogado los documentos del estudio recibidos, con copia a Victoria Vilches, en el mismo hilo del correo"
                        style={{ background: "#0d9488", border: "none", color: "#fff", borderRadius: 0, padding: "0.5rem 1rem", fontSize: 12.5, fontWeight: 800, cursor: "pointer", marginBottom: 8 }}>
                        <i className={`fa ${m.loading ? "fa-spinner fa-spin" : "fa-paper-plane"}`} /> 📤 Etapa 2: Enviar documentos recibidos a Guillermo Marluf (CC Victoria Vilches)
                      </button>
                      {m.folder.estudio_docs_enviados_abogado_at && (
                        <div data-testid="estudio-etapa2-badge" style={{ fontSize: 11, color: "#34eab9", fontWeight: 700, marginBottom: 6 }}>
                          ✅ Etapa 2 realizada: {(m.folder.estudio_docs_enviados_abogado || []).length} documento(s) enviados el {new Date(m.folder.estudio_docs_enviados_abogado_at).toLocaleString("es-CL")}
                        </div>
                      )}
                      <div style={{ display: "grid", gap: 4, maxHeight: 130, overflow: "auto" }}>
                        {docsEstudio.map((a, i) => (
                          <div key={a.ruta} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5 }}>
                            <i className="fa fa-file-pdf-o" style={{ color: "#2dd4bf" }} />
                            <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{a.nombre}</span>
                            <button type="button" data-testid={`estudio-doc-ver-${i}`}
                              onClick={() => openPreview(m.folder.id, a.ruta, a.nombre)}
                              style={{ background: "rgba(212,175,55,0.15)", border: "1px solid #d4af37", color: "#d4af37", borderRadius: 0, padding: "2px 10px", fontSize: 11, fontWeight: 700, cursor: "pointer", flexShrink: 0 }}>
                              <i className="fa fa-eye" /> Ver
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  <div style={{ background: "rgba(28,28,30,0.7)", borderRadius: 0, padding: "0.7rem 0.9rem" }}>
                    <div style={{ opacity: 0.7, fontSize: 11, textTransform: "uppercase", marginBottom: 6 }}>Adjuntos de la solicitud — la carta de aprobación va preseleccionada</div>
                    <div style={{ display: "grid", gap: 4, maxHeight: 140, overflow: "auto" }}>
                      {adjCredito.map((a, i) => (
                        <label key={a.ruta} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5, cursor: "pointer" }}>
                          <input type="checkbox" checked={!!a.sel} data-testid={`estudio-adj-${i}`}
                            onChange={() => setEstudioModal(prev => ({ ...prev, preview: null, archivos: prev.archivos.map(x => x.ruta === a.ruta ? { ...x, sel: !x.sel } : x) }))} />
                          <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{a.nombre} <span style={{ opacity: 0.5 }}>{a.subfolder ? `(${a.subfolder})` : ""}</span></span>
                          <button type="button" data-testid={`estudio-adj-ver-${i}`}
                            title={`Ver ${a.nombre} antes de enviarlo`}
                            onClick={(e) => { e.preventDefault(); e.stopPropagation(); openPreview(m.folder.id, a.ruta, a.nombre); }}
                            style={{ background: "rgba(212,175,55,0.15)", border: "1px solid #d4af37", color: "#d4af37", borderRadius: 0, padding: "2px 10px", fontSize: 11, fontWeight: 700, cursor: "pointer", flexShrink: 0 }}>
                            <i className="fa fa-eye" /> Ver
                          </button>
                        </label>
                      ))}
                    </div>
                  </div>
                  </>
                  );
                })()}
                {m.preview && (
                  <div style={{ background: "#fff", borderRadius: 0, padding: "0.9rem", maxHeight: 260, overflow: "auto" }}>
                    <div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(m.preview.body) }} />
                    {m.preview.attachments.length > 0 && (
                      <div style={{ marginTop: 8, fontSize: 12, color: "#334155" }}>📎 Adjuntos: {m.preview.attachments.join(", ")}</div>
                    )}
                  </div>
                )}
                <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
                  <button onClick={estudioPreview} disabled={m.loading} data-testid="btn-estudio-preview"
                    style={{ padding: "0.55rem 1.1rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.4)", background: "transparent", color: "#e2e8f0", fontWeight: 700, cursor: "pointer" }}>
                    <i className={`fa ${m.loading ? "fa-spinner fa-spin" : "fa-eye"}`} /> Ver preview
                  </button>
                  <button onClick={estudioEnviar} disabled={m.loading} data-testid="btn-estudio-enviar"
                    style={{ padding: "0.55rem 1.1rem", borderRadius: 0, border: "none", background: "#0d9488", color: "#fff", fontWeight: 800, cursor: "pointer", opacity: m.loading ? 0.6 : 1 }}>
                    <i className={`fa ${m.loading ? "fa-spinner fa-spin" : "fa-paper-plane"}`} /> Enviar solicitud
                  </button>
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {pedirModal && (() => {
        const m = pedirModal;
        const set = (k, v) => setPedirModal(prev => ({ ...prev, [k]: v, preview: null }));
        const inpS = { width: "100%", padding: "0.5rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.3)", background: "#232326", color: "#e2e8f0", fontSize: 13 };
        const lblS = { fontSize: 12 };
        return (
          <div data-testid="pedir-modal" onClick={() => setPedirModal(null)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9998, padding: "3vh 3vw" }}>
            <div onClick={(e) => e.stopPropagation()} style={{ background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", color: "#e2e8f0", borderRadius: 0, width: "min(680px, 96vw)", maxHeight: "94vh", overflow: "auto", border: "1px solid rgba(148,163,184,0.25)", boxShadow: "0 20px 60px rgba(0,0,0,0.6)" }}>
              <div style={{ padding: "0.9rem 1.1rem", borderBottom: "1px solid rgba(148,163,184,0.2)", display: "flex", alignItems: "center", gap: 10 }}>
                <i className="fa fa-envelope" style={{ color: "#fb7185" }} />
                <h4 style={{ margin: 0, flex: 1 }}>Pedir documentos faltantes — {m.folder.nombre}</h4>
                <button onClick={() => setPedirModal(null)} data-testid="btn-pedir-close" style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: 18 }}><i className="fa fa-times" /></button>
              </div>
              <div style={{ padding: "1rem 1.1rem", display: "grid", gap: "0.75rem" }}>
                {m.msg && (
                  <div data-testid="pedir-msg" style={{ padding: "0.6rem 0.9rem", borderRadius: 0, background: m.msg.startsWith("✅") ? "rgba(16,217,142,0.15)" : "rgba(225,29,72,0.15)", color: m.msg.startsWith("✅") ? "#34eab9" : "#fb7185", fontWeight: 600, fontSize: 13 }}>{m.msg}</div>
                )}
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Destinatario (quien nos envió la solicitud de crédito)</b>
                  <input value={m.destinatario} onChange={e => set("destinatario", e.target.value)} data-testid="pedir-destinatario" style={inpS} />
                </label>
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Documentos faltantes (uno por línea)</b>
                  <textarea value={m.faltantes} onChange={e => set("faltantes", e.target.value)} rows={4} data-testid="pedir-faltantes-lista" style={{ ...inpS, resize: "vertical" }} />
                </label>
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Mensaje adicional (opcional)</b>
                  <textarea value={m.mensaje} onChange={e => set("mensaje", e.target.value)} rows={2} data-testid="pedir-mensaje" style={{ ...inpS, resize: "vertical" }} />
                </label>
                {m.preview && (
                  <div style={{ background: "#fff", borderRadius: 0, padding: "0.9rem", maxHeight: 240, overflow: "auto" }}>
                    <div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(m.preview.body) }} />
                  </div>
                )}
                <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
                  <button onClick={pedirPreview} disabled={m.loading} data-testid="btn-pedir-preview"
                    style={{ padding: "0.55rem 1.1rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.4)", background: "transparent", color: "#e2e8f0", fontWeight: 700, cursor: "pointer" }}>
                    <i className={`fa ${m.loading ? "fa-spinner fa-spin" : "fa-eye"}`} /> Ver preview
                  </button>
                  <button onClick={pedirEnviar} disabled={m.loading || !m.destinatario.includes("@")} data-testid="btn-pedir-enviar"
                    style={{ padding: "0.55rem 1.1rem", borderRadius: 0, border: "none", background: "#be123c", color: "#fff", fontWeight: 800, cursor: "pointer", opacity: (m.loading || !m.destinatario.includes("@")) ? 0.6 : 1 }}>
                    <i className={`fa ${m.loading ? "fa-spinner fa-spin" : "fa-paper-plane"}`} /> Enviar solicitud de faltantes
                  </button>
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {escrituraModal && (() => {
        const m = escrituraModal;
        const set = (k, v) => setEscrituraModal(prev => ({ ...prev, [k]: v, preview: null }));
        const inpS = { width: "100%", padding: "0.5rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.3)", background: "#232326", color: "#e2e8f0", fontSize: 13 };
        const lblS = { fontSize: 12 };
        const notariaSel = notarias.find(n => n.id === m.notaria_id);
        return (
          <div data-testid="escritura-modal" onClick={() => setEscrituraModal(null)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9998, padding: "3vh 3vw" }}>
            <div onClick={(e) => e.stopPropagation()} style={{ background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", color: "#e2e8f0", borderRadius: 0, width: "min(760px, 96vw)", maxHeight: "94vh", overflow: "auto", border: "1px solid rgba(148,163,184,0.25)", boxShadow: "0 20px 60px rgba(0,0,0,0.6)" }}>
              <div style={{ padding: "0.9rem 1.1rem", borderBottom: "1px solid rgba(148,163,184,0.2)", display: "flex", alignItems: "center", gap: 10 }}>
                <i className="fa fa-pencil" style={{ color: "#f472b6" }} />
                <h4 style={{ margin: 0, flex: 1 }}>Firma de Escritura — {m.folder.nombre}</h4>
                <button onClick={() => setEscrituraModal(null)} data-testid="btn-escritura-close" style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: 18 }}><i className="fa fa-times" /></button>
              </div>
              <div style={{ padding: "1rem 1.1rem", display: "grid", gap: "0.75rem" }}>
                {m.msg && (
                  <div data-testid="escritura-msg" style={{ padding: "0.6rem 0.9rem", borderRadius: 0, background: m.msg.startsWith("✅") ? "rgba(16,217,142,0.15)" : "rgba(225,29,72,0.15)", color: m.msg.startsWith("✅") ? "#34eab9" : "#fb7185", fontWeight: 600, fontSize: 13 }}>{m.msg}</div>
                )}
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Correo del cliente <span style={{ color: "#fb7185" }}>*</span></b>
                  <input value={m.email_cliente} onChange={e => set("email_cliente", e.target.value)} placeholder="cliente@correo.cl" data-testid="escritura-email" style={inpS} />
                </label>
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Notaría (por ciudad) <span style={{ color: "#fb7185" }}>*</span></b>
                  <select value={m.notaria_id} onChange={e => set("notaria_id", e.target.value)} data-testid="escritura-notaria" style={inpS}>
                    <option value="">— Seleccionar notaría —</option>
                    {notarias.map(n => <option key={n.id} value={n.id}>{n.ciudad} — {n.nombre} · {n.direccion}</option>)}
                  </select>
                </label>
                {notariaSel && !notariaSel.email && (
                  <div style={{ display: "flex", gap: 6, alignItems: "center", background: "rgba(250,204,21,0.08)", border: "1px solid rgba(250,204,21,0.3)", borderRadius: 0, padding: "0.5rem 0.8rem", fontSize: 12 }}>
                    <span style={{ color: "#facc15" }}>⚠️ Esta notaría no tiene correo: no recibirá el aviso de confirmación.</span>
                    <input value={m.notaria_email_edit} onChange={e => setEscrituraModal(prev => ({ ...prev, notaria_email_edit: e.target.value }))} placeholder="correo@notaria.cl" data-testid="escritura-notaria-email" style={{ ...inpS, flex: 1, width: "auto" }} />
                    <button onClick={escrituraSaveNotariaEmail} data-testid="escritura-notaria-email-save" style={{ ...inpS, width: "auto", background: "#a16207", border: "none", fontWeight: 700, cursor: "pointer" }}>Guardar</button>
                  </div>
                )}
                {m.addNotaria ? (
                  <div style={{ background: "rgba(236,72,153,0.06)", border: "1px dashed rgba(236,72,153,0.4)", borderRadius: 0, padding: "0.7rem 0.9rem", display: "grid", gap: "0.5rem" }}>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1.5fr", gap: "0.5rem" }}>
                      <input value={m.nn.ciudad} onChange={e => setEscrituraModal(prev => ({ ...prev, nn: { ...prev.nn, ciudad: e.target.value } }))} placeholder="Ciudad *" data-testid="notaria-new-ciudad" style={inpS} />
                      <input value={m.nn.nombre} onChange={e => setEscrituraModal(prev => ({ ...prev, nn: { ...prev.nn, nombre: e.target.value } }))} placeholder="Nombre notaría" data-testid="notaria-new-nombre" style={inpS} />
                    </div>
                    <input value={m.nn.direccion} onChange={e => setEscrituraModal(prev => ({ ...prev, nn: { ...prev.nn, direccion: e.target.value } }))} placeholder="Dirección completa *" data-testid="notaria-new-direccion" style={inpS} />
                    <div style={{ display: "flex", gap: 6 }}>
                      <input value={m.nn.email} onChange={e => setEscrituraModal(prev => ({ ...prev, nn: { ...prev.nn, email: e.target.value } }))} placeholder="Correo notaría (para avisarle la confirmación)" data-testid="notaria-new-email" style={{ ...inpS, flex: 1 }} />
                      <button onClick={escrituraAddNotaria} data-testid="notaria-new-save" style={{ ...inpS, width: "auto", background: "#db2777", border: "none", fontWeight: 700, cursor: "pointer" }}>Guardar notaría</button>
                    </div>
                  </div>
                ) : (
                  <button onClick={() => setEscrituraModal(prev => ({ ...prev, addNotaria: true }))} data-testid="btn-add-notaria" style={{ justifySelf: "start", background: "transparent", border: "1px dashed rgba(236,72,153,0.5)", color: "#f9a8d4", borderRadius: 0, padding: "0.3rem 0.7rem", fontSize: 11.5, cursor: "pointer" }}>
                    <i className="fa fa-plus" /> Agregar notaría nueva
                  </button>
                )}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Día de la firma <span style={{ color: "#fb7185" }}>*</span></b>
                    <input type="date" value={m.fecha} onChange={e => set("fecha", e.target.value)} data-testid="escritura-fecha" style={inpS} />
                  </label>
                  <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Horario <span style={{ opacity: 0.6 }}>(10:00 por defecto — horario a sugerir si es distinto)</span></b>
                    <input type="time" value={m.hora} onChange={e => set("hora", e.target.value)} data-testid="escritura-hora" style={inpS} />
                  </label>
                </div>
                <div style={{ fontSize: 11.5, opacity: 0.75, background: "rgba(16,217,142,0.06)", border: "1px solid rgba(16,217,142,0.25)", borderRadius: 0, padding: "0.5rem 0.8rem", lineHeight: 1.6 }}>
                  El cliente recibe el correo con el botón <b>"CONFIRMO QUE ASISTIRÉ"</b>. Al confirmar, indica si va solo, con mandatario y/o codeudor,
                  y se avisa automáticamente a la <b>notaría</b> (si tiene correo) y a <b>Victoria Vilches, Daniela Galindo y Rodrigo Ibáñez</b> con el día, horario y acompañantes.
                </div>
                {m.preview && (
                  <div style={{ background: "#fff", borderRadius: 0, padding: "0.9rem", maxHeight: 280, overflow: "auto" }}>
                    <div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(m.preview.body) }} />
                  </div>
                )}
                <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
                  <button onClick={escrituraPreview} disabled={m.loading} data-testid="btn-escritura-preview"
                    style={{ padding: "0.55rem 1.1rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.4)", background: "transparent", color: "#e2e8f0", fontWeight: 700, cursor: "pointer" }}>
                    <i className={`fa ${m.loading ? "fa-spinner fa-spin" : "fa-eye"}`} /> Ver preview
                  </button>
                  <button onClick={escrituraEnviar} disabled={m.loading || !m.email_cliente.includes("@") || !m.fecha || !m.notaria_id} data-testid="btn-escritura-enviar"
                    title={!m.email_cliente.includes("@") ? "Falta el correo del cliente" : (!m.fecha ? "Falta la fecha" : (!m.notaria_id ? "Falta la notaría" : ""))}
                    style={{ padding: "0.55rem 1.1rem", borderRadius: 0, border: "none", background: "#db2777", color: "#fff", fontWeight: 800, cursor: "pointer", opacity: (m.loading || !m.email_cliente.includes("@") || !m.fecha || !m.notaria_id) ? 0.6 : 1 }}>
                    <i className={`fa ${m.loading ? "fa-spinner fa-spin" : "fa-paper-plane"}`} /> Enviar aviso al cliente
                  </button>
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {emailModal && (() => {
        const f = emailModal.folder;
        const df = f.datos_financieros || {};
        const cr = f.credit_request || {};
        const conSub = df.con_subsidio ?? (cr.subsidy?.tipo === "con_subsidio");
        // Formato UF con prefijo "UF" antes del número. Ej: "UF 3.200,00"
        // Valores < 20000 se consideran UF nativos, >= 20000 se convierten desde CLP.
        const fmt = (n) => {
          if (n == null || n === "") return "—";
          const v = Number(n);
          if (Number.isNaN(v)) return String(n);
          const uf = v < 20000 ? v : v / (Number(ufValue) || 40842);
          return `UF ${uf.toLocaleString('es-CL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        };
        const prefijoAsunto = `Antecedentes crédito hipotecario — ${f.nombre}${f.rut ? ` (${f.rut})` : ""}${df.fecha_entrega ? ` — Entrega: ${df.fecha_entrega.charAt(0).toUpperCase() + df.fecha_entrega.slice(1)}` : ""}`;
        const previewSubject = prefijoAsunto
          + (emailModal.subject_extra ? ` — ${emailModal.subject_extra}` : "")
          + (emailModal.ejecutivo_externo ? ` — Ejecutivo: ${emailModal.ejecutivo_externo}` : "");
        return (
          <div data-testid="email-modal" onClick={closeEmailModal} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9998, padding: "3vh 3vw" }}>
            <div onClick={(e) => e.stopPropagation()} style={{ background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", color: "#e2e8f0", borderRadius: 0, width: "min(760px, 96vw)", maxHeight: "94vh", overflow: "auto", border: "1px solid rgba(148,163,184,0.25)", boxShadow: "0 20px 60px rgba(0,0,0,0.6)" }}>
              <div style={{ padding: "0.9rem 1.1rem", borderBottom: "1px solid rgba(148,163,184,0.2)", display: "flex", alignItems: "center", gap: 10 }}>
                <i className="fa fa-paper-plane" style={{ color: "#d4af37" }} />
                <h4 style={{ margin: 0, flex: 1 }}>Enviar correo con antecedentes</h4>
                <button onClick={closeEmailModal} data-testid="btn-email-close" style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: 18 }}><i className="fa fa-times" /></button>
              </div>
              <div style={{ padding: "1rem 1.1rem", display: "grid", gap: "0.75rem" }}>
                <div style={{ background: "rgba(28,28,30,0.7)", borderRadius: 0, padding: "0.7rem 0.9rem", fontSize: 13, lineHeight: 1.5 }}>
                  <div style={{ opacity: 0.7, fontSize: 11, textTransform: "uppercase", marginBottom: 4 }}>Datos que se incluirán en el correo</div>
                  <div><b>Cliente:</b> {f.nombre}</div>
                  <div><b>RUT:</b> {f.rut || <span style={{ color: "#fb7185" }}>— falta</span>}</div>
                  <div><b>Tipo:</b> {conSub ? "CON subsidio (DS1 / DS19)" : "SIN subsidio"}</div>
                  <div><b>Inmobiliaria:</b> {df.inmobiliaria || <span style={{ color: "#facc15" }}>— falta (completar en Ver datos financieros)</span>}</div>
                  {df.proyecto && <div><b>Proyecto:</b> {df.proyecto}</div>}
                  <div><b>Valor propiedad:</b> {fmt(df.valor_propiedad)}</div>
                  {conSub && <div><b>Monto subsidio:</b> {fmt(df.monto_subsidio)}</div>}
                  {conSub && <div><b>Ahorro:</b> {fmt(df.ahorro)}</div>}
                  {!conSub && <div><b>Pie:</b> {fmt(df.monto_pie)}</div>}
                  <div><b>Reserva:</b> {fmt(df.monto_reserva)}</div>
                  <div><b>Monto crédito:</b> {fmt(df.monto_credito)}</div>
                </div>

                <label style={{ fontSize: 12 }}>
                  <b style={{ display: "block", marginBottom: 4 }}>Destinatario <span style={{ color: "#fb7185" }}>🔒 fijo</span></b>
                  <input
                    type="email"
                    value={emailModal.to}
                    readOnly
                    data-testid="email-to-input"
                    style={{ width: "100%", padding: "0.5rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.3)", background: "#232326", color: "#e2e8f0", fontSize: 13, cursor: "not-allowed", opacity: 0.85 }}
                  />
                  <div style={{ marginTop: 6, padding: "6px 10px", borderRadius: 0, background: "rgba(225,29,72,0.12)", border: "1px solid rgba(225,29,72,0.4)", color: "#fda4af", fontSize: 11, fontWeight: 500 }}>
                    🔒 <b>Regla inviolable</b>: todos los correos a mesa se envían solo a la cuenta Central Mutuos. No se puede modificar el destinatario.
                  </div>
                </label>

                <label style={{ fontSize: 12 }}>
                  <b style={{ display: "block", marginBottom: 4 }}>Ejecutivo interno * <span style={{ color: "#facc15" }}>se incluye en el correo a mesa junto al correo de origen</span></b>
                  <select
                    value={emailModal.ejecutivo || ""}
                    onChange={(e) => setEmailModal({ ...emailModal, ejecutivo: e.target.value })}
                    data-testid="email-ejecutivo-select"
                    style={{ width: "100%", padding: "0.5rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.3)", background: "#232326", color: "#e2e8f0", fontSize: 13 }}>
                    <option value="">— Seleccionar ejecutivo —</option>
                    <option value="Deisy Salazar">Deisy Salazar</option>
                    <option value="Yerile Barrera">Yerile Barrera</option>
                    <option value="Gerardo Barrera">Gerardo Barrera</option>
                  </select>
                </label>

                <label style={{ fontSize: 12 }}>
                  <b style={{ display: "block", marginBottom: 4 }}>Ejecutivo externo (de dónde viene la solicitud) <span style={{ color: "#facc15" }}>se agrega al asunto y al correo</span></b>
                  <input
                    type="text"
                    value={emailModal.ejecutivo_externo || ""}
                    onChange={(e) => setEmailModal({ ...emailModal, ejecutivo_externo: e.target.value })}
                    placeholder="Ej: Javiera Garrido — World Consultores"
                    data-testid="email-ejecutivo-externo-input"
                    style={{ width: "100%", padding: "0.5rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.3)", background: "#232326", color: "#e2e8f0", fontSize: 13 }}
                  />
                </label>

                <label style={{ fontSize: 12 }}>
                  <b style={{ display: "block", marginBottom: 4 }}>Asunto <span style={{ color: "#fb7185" }}>🔒 prefijo fijo</span> + texto adicional (opcional)</b>
                  <div style={{ padding: "0.45rem 0.6rem", borderRadius: 0, background: "rgba(225,29,72,0.08)", border: "1px dashed rgba(225,29,72,0.4)", fontSize: 12, color: "#fda4af", marginBottom: 6 }} data-testid="email-subject-prefijo">
                    🔒 {prefijoAsunto}
                  </div>
                  <input
                    type="text"
                    value={emailModal.subject_extra || ""}
                    onChange={(e) => setEmailModal({ ...emailModal, subject_extra: e.target.value })}
                    placeholder="Agregar al asunto (ej: URGENTE, con codeudor…) — el prefijo nunca se borra"
                    data-testid="email-subject-input"
                    style={{ width: "100%", padding: "0.5rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.3)", background: "#232326", color: "#e2e8f0", fontSize: 13 }}
                  />
                  <div style={{ marginTop: 5, fontSize: 11, opacity: 0.75 }} data-testid="email-subject-final">
                    Asunto final: <span style={{ color: "#facc15" }}>{previewSubject}</span>
                  </div>
                </label>

                <label style={{ fontSize: 12 }}>
                  <b style={{ display: "block", marginBottom: 4 }}>Mensaje adicional (opcional)</b>
                  <textarea
                    value={emailModal.extra}
                    onChange={(e) => setEmailModal({ ...emailModal, extra: e.target.value })}
                    rows={3}
                    placeholder="Comentarios extra para el destinatario…"
                    data-testid="email-extra-input"
                    style={{ width: "100%", padding: "0.5rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.3)", background: "#232326", color: "#e2e8f0", fontSize: 13, resize: "vertical" }}
                  />
                </label>

                <div style={{ background: "rgba(28,28,30,0.5)", borderRadius: 0, padding: "0.6rem 0.9rem", fontSize: 12, display: "grid", gap: 6 }}>
                  <div style={{ opacity: 0.7, fontSize: 11, textTransform: "uppercase" }}>Adjuntos</div>
                  <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={!!emailModal.include_merged}
                      onChange={(e) => setEmailModal({ ...emailModal, include_merged: e.target.checked })}
                      data-testid="email-include-merged"
                      style={{ accentColor: "#facc15" }}
                    />
                    Adjuntar combinado del <b>titular</b> (COMBINADO_PROTOCOLO_*.pdf)
                  </label>
                  {(f.codeudor_nombre || f.credit_request?.codeudor?.has_codeudor) && (
                    <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                      <input
                        type="checkbox"
                        checked={!!emailModal.include_codeudor_merged}
                        onChange={(e) => setEmailModal({ ...emailModal, include_codeudor_merged: e.target.checked })}
                        data-testid="email-include-codeudor"
                        style={{ accentColor: "#facc15" }}
                      />
                      Adjuntar combinado del <b>codeudor</b> {f.codeudor_nombre ? `(${f.codeudor_nombre})` : ""} — se genera automáticamente si no existe
                    </label>
                  )}
                  <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: selectionCount(f.id) > 0 ? "pointer" : "not-allowed", opacity: selectionCount(f.id) > 0 ? 1 : 0.5 }}>
                    <input
                      type="checkbox"
                      checked={!!emailModal.attach_selected}
                      onChange={(e) => setEmailModal({ ...emailModal, attach_selected: e.target.checked })}
                      disabled={selectionCount(f.id) < 1}
                      data-testid="email-attach-selected"
                      style={{ accentColor: "#facc15" }}
                    />
                    Adjuntar archivos seleccionados ({selectionCount(f.id)})
                  </label>
                </div>
              </div>
              {emailModal.preview && (
                <div style={{ padding: "0.8rem 1.1rem", borderTop: "1px solid rgba(148,163,184,0.2)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                    <i className="fa fa-eye" style={{ color: "#facc15" }} />
                    <b style={{ fontSize: 13 }}>Preview del correo (autorizá con "Enviar a Mesa")</b>
                    <span style={{ marginLeft: "auto", fontSize: 11, opacity: 0.7 }}>
                      UF día: <b>{Number(emailModal.preview.uf_valor || ufValue).toLocaleString('es-CL')}</b>
                    </span>
                  </div>
                  {(emailModal.preview.missing_docs || []).length > 0 && (
                    <div data-testid="email-missing-docs-warning" style={{ marginBottom: 8, padding: "8px 12px", borderRadius: 0, background: "rgba(225,29,72,0.12)", border: "1px solid rgba(225,29,72,0.5)", color: "#fda4af", fontSize: 12 }}>
                      <b>🚫 Documentación incompleta — faltan:</b> {emailModal.preview.missing_docs.join(" · ")}
                      <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8, cursor: "pointer", color: "#fecaca", fontWeight: 600 }}>
                        <input type="checkbox" checked={!!emailModal.force_incompleto}
                          onChange={(e) => setEmailModal({ ...emailModal, force_incompleto: e.target.checked })}
                          data-testid="email-force-incompleto" style={{ accentColor: "#e11d48" }} />
                        Asumo el envío manual con documentación incompleta
                      </label>
                    </div>
                  )}
                  {emailModal.editBody != null ? (
                    <div>
                      <textarea value={emailModal.editBody} data-testid="email-body-editor"
                        onChange={(e) => setEmailModal({ ...emailModal, editBody: e.target.value })}
                        rows={12}
                        style={{ width: "100%", padding: "0.6rem 0.8rem", borderRadius: 0, border: "1px solid rgba(250,204,21,0.5)", background: "#232326", color: "#e2e8f0", fontSize: 12, fontFamily: "monospace", resize: "vertical" }} />
                      <div style={{ marginTop: 6, background: "#fff", color: "#111", borderRadius: 0, padding: "0.6rem 0.8rem", maxHeight: 200, overflow: "auto", border: "1px solid rgba(148,163,184,0.3)" }}
                           dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(emailModal.editBody) }} />
                      <button onClick={() => setEmailModal({ ...emailModal, editBody: null })} data-testid="email-body-reset"
                        style={{ marginTop: 6, background: "transparent", border: "1px solid rgba(148,163,184,0.3)", color: "#94a3b8", borderRadius: 0, padding: "4px 10px", cursor: "pointer", fontSize: 12 }}>
                        <i className="fa fa-undo" /> Volver al cuerpo automático
                      </button>
                    </div>
                  ) : (
                    <div>
                      <div style={{ background: "#fff", color: "#111", borderRadius: 0, padding: "0.6rem 0.8rem", maxHeight: 320, overflow: "auto", border: "1px solid rgba(148,163,184,0.3)" }}
                           dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(emailModal.preview.body_html || emailModal.preview.body) }} />
                      <button onClick={() => setEmailModal({ ...emailModal, editBody: emailModal.preview.body_html || emailModal.preview.body || "" })} data-testid="email-body-edit-btn"
                        style={{ marginTop: 6, background: "rgba(250,204,21,0.15)", border: "1px solid rgba(250,204,21,0.5)", color: "#facc15", borderRadius: 0, padding: "4px 10px", cursor: "pointer", fontSize: 12, fontWeight: 600 }}>
                        <i className="fa fa-pencil" /> Editar cuerpo manualmente
                      </button>
                    </div>
                  )}
                  {emailModal.preview.attachments?.length > 0 && (
                    <div style={{ marginTop: 8, fontSize: 12, color: "#d4af37" }}>
                      <b>Adjuntos:</b> {emailModal.preview.attachments.map(a => `📎 ${a}`).join("  ·  ")}
                    </div>
                  )}
                </div>
              )}
              <div style={{ padding: "0.8rem 1.1rem", borderTop: "1px solid rgba(148,163,184,0.2)", display: "flex", gap: 8, justifyContent: "flex-end" }}>
                <button onClick={closeEmailModal} disabled={emailModal.sending} style={{ background: "transparent", border: "1px solid rgba(148,163,184,0.3)", color: "#94a3b8", borderRadius: 0, padding: "6px 14px", cursor: "pointer", fontSize: 13 }}>Cancelar</button>
                {!emailModal.preview ? (
                  <button onClick={previewClientEmail} disabled={emailModal.sending || !emailModal.to} data-testid="btn-email-preview"
                    style={{ background: !emailModal.to ? "rgba(148,163,184,0.15)" : "rgba(250,204,21,0.2)", border: `1px solid ${!emailModal.to ? "rgba(148,163,184,0.3)" : "rgba(250,204,21,0.6)"}`, color: !emailModal.to ? "#94a3b8" : "#facc15", borderRadius: 0, padding: "6px 14px", cursor: (emailModal.sending || !emailModal.to) ? "not-allowed" : "pointer", fontSize: 13, fontWeight: 600 }}
                    title={!emailModal.to ? "Completá el destinatario primero" : "Generar preview"}>
                    <i className={`fa ${emailModal.sending ? "fa-spinner fa-spin" : "fa-eye"}`} /> {emailModal.sending ? "Generando…" : (!emailModal.to ? "Completá destinatario" : "Ver Preview")}
                  </button>
                ) : (
                  <>
                    <button onClick={() => setEmailModal({ ...emailModal, preview: null })} disabled={emailModal.sending}
                      style={{ background: "transparent", border: "1px solid rgba(148,163,184,0.3)", color: "#94a3b8", borderRadius: 0, padding: "6px 14px", cursor: "pointer", fontSize: 13 }}>
                      <i className="fa fa-pencil" /> Editar
                    </button>
                    <button onClick={async () => {
                        await toggleEnvioManual({ ...emailModal.folder, envio_manual: false });
                        closeEmailModal();
                      }} disabled={emailModal.sending} data-testid="btn-marcar-enviado"
                      title="Marca la carpeta como ENVIADA manualmente (la pinta roja) sin enviar el correo"
                      style={{ background: "#ec4899", border: "1px solid #be185d", color: "#fff", borderRadius: 0, padding: "6px 14px", cursor: "pointer", fontSize: 13, fontWeight: 700 }}>
                      <i className="fa fa-check" /> Marcar como enviado
                    </button>
                    {(() => {
                      const df = emailModal.folder.datos_financieros || {};
                      const conSub = df.con_subsidio ?? (emailModal.folder.credit_request?.subsidy?.tipo === "con_subsidio");
                      const vp = Number(df.valor_propiedad || 0);
                      const mc = Number(df.monto_credito || 0);
                      const bloq80 = !conSub && vp > 0 && mc > 0 && mc > vp * 0.8 + 0.01;
                      const md = emailModal.preview?.missing_docs || [];
                      const bloqDocs = md.length > 0 && !emailModal.force_incompleto;
                      const bloqueado = bloq80 || bloqDocs;
                      const label = emailModal.sending ? "Enviando…"
                        : bloq80 ? "🚫 Bloqueado por regla 80%"
                        : bloqDocs ? "🚫 Faltan documentos"
                        : "Enviar a Mesa";
                      const title = bloq80
                        ? `🚫 BLOQUEADO: crédito ${mc.toFixed(2)} UF supera el 80% (${(vp * 0.8).toFixed(2)} UF) — SIN subsidio no permite más del 80%`
                        : bloqDocs
                        ? `🚫 BLOQUEADO: faltan ${md.join(", ")}. Marcá "Asumo el envío manual" para enviar igual.`
                        : "Enviar correo revisado directo a mesa";
                      return (
                        <button onClick={confirmSendClientEmail} disabled={emailModal.sending || bloqueado} data-testid="btn-email-send" title={title}
                          style={{
                            background: bloqueado ? "#7f1d1d" : "#10c98a",
                            border: `1px solid ${bloqueado ? "#450a0a" : "#0e9f6e"}`,
                            color: "#fff", borderRadius: 0, padding: "6px 18px",
                            cursor: (emailModal.sending || bloqueado) ? "not-allowed" : "pointer",
                            fontSize: 13, fontWeight: 700,
                            boxShadow: bloqueado ? "none" : "0 2px 8px rgba(22,163,74,0.4)",
                            opacity: bloqueado ? 0.6 : 1,
                          }}>
                          <i className={`fa ${emailModal.sending ? "fa-spinner fa-spin" : "fa-paper-plane"}`} /> {label}
                        </button>
                      );
                    })()}
                  </>
                )}
              </div>
            </div>
          </div>
        );
      })()}
      {/* HISTORIAL MODAL */}
      {historialModal && (
        <div data-testid="historial-modal" onClick={() => setHistorialModal(null)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9998, padding: "3vh 3vw" }}>
          <div onClick={(e) => e.stopPropagation()} style={{ background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", color: "#e2e8f0", borderRadius: 0, width: "min(640px, 96vw)", maxHeight: "90vh", overflow: "auto", border: "1px solid rgba(212,175,55,0.4)", boxShadow: "0 20px 60px rgba(0,0,0,0.6)" }}>
            <div style={{ padding: "0.9rem 1.1rem", borderBottom: "1px solid rgba(148,163,184,0.2)", display: "flex", alignItems: "center", gap: 10, position: "sticky", top: 0, background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)" }}>
              <i className="fa fa-history" style={{ color: "#d4af37" }} />
              <h4 style={{ margin: 0, flex: 1 }}>Historial — {historialModal.folder.nombre}</h4>
              <button onClick={() => setHistorialModal(null)} data-testid="btn-historial-close" style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: 18 }}><i className="fa fa-times" /></button>
            </div>
            <div style={{ padding: "1rem 1.1rem" }}>
              {historialModal.loading ? (
                <div style={{ opacity: 0.7 }}><i className="fa fa-spinner fa-spin" /> Cargando historial…</div>
              ) : historialModal.eventos.length === 0 ? (
                <div style={{ opacity: 0.7 }} data-testid="historial-vacio">Sin actividades registradas todavía.</div>
              ) : (
                <div>
                  {historialModal.eventos.map((ev, i) => (
                    <div key={i} data-testid={`historial-evento-${i}`} style={{ display: "flex", gap: 12, padding: "0.55rem 0", borderBottom: i < historialModal.eventos.length - 1 ? "1px solid rgba(148,163,184,0.12)" : "none" }}>
                      <div style={{ fontSize: 17, width: 26, textAlign: "center" }}>{ev.icono}</div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 700, fontSize: 13 }}>{ev.titulo}</div>
                        {ev.detalle && <div style={{ fontSize: 11.5, opacity: 0.7 }}>{ev.detalle}</div>}
                      </div>
                      <div style={{ fontSize: 11.5, color: "#d4af37", fontWeight: 700, whiteSpace: "nowrap" }}>{fmtActFull(ev.fecha)}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
      {/* MISSING DOCS MODAL */}
      {missingDocsModal && (() => {
        const p = missingDocsModal.preview;
        return (
          <div data-testid="missing-docs-modal" onClick={closeMissingDocsModal} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9998, padding: "3vh 3vw" }}>
            <div onClick={(e) => e.stopPropagation()} style={{ background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", color: "#e2e8f0", borderRadius: 0, width: "min(760px, 96vw)", maxHeight: "94vh", overflow: "auto", border: "1px solid rgba(225,29,72,0.5)", boxShadow: "0 20px 60px rgba(0,0,0,0.6)" }}>
              <div style={{ padding: "0.9rem 1.1rem", borderBottom: "1px solid rgba(148,163,184,0.2)", display: "flex", alignItems: "center", gap: 10 }}>
                <i className="fa fa-exclamation-triangle" style={{ color: "#fb7185" }} />
                <h4 style={{ margin: 0, flex: 1 }}>Correo de documento faltante — {missingDocsModal.folder.nombre}</h4>
                <button onClick={closeMissingDocsModal} style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: 18 }}><i className="fa fa-times" /></button>
              </div>
              <div style={{ padding: "1rem 1.1rem", display: "grid", gap: "0.75rem" }}>
                {p && (
                  <>
                    <div style={{ background: "rgba(225,29,72,0.1)", borderRadius: 0, padding: "0.7rem 0.9rem", fontSize: 13 }}>
                      <div style={{ opacity: 0.7, fontSize: 11, textTransform: "uppercase", marginBottom: 4 }}>Detección automática</div>
                      <div><b>Cliente tipo:</b> {p.client_type}</div>
                      <div><b>Documentos presentes:</b> {p.present.join(", ") || "ninguno"}</div>
                      <div style={{ color: "#fb7185" }}><b>Documentos faltantes:</b> {p.missing.length > 0 ? p.missing.join(", ") : "ninguno detectado"}</div>
                      {p.source_email && <div style={{ opacity: 0.75, fontSize: 12, marginTop: 4 }}><b>Origen:</b> {p.source_email}</div>}
                    </div>
                    <label style={{ fontSize: 12 }}><b style={{ display: "block", marginBottom: 4 }}>Destinatario *</b>
                      <input type="email" value={missingDocsModal.to} onChange={(e) => setMissingDocsModal({ ...missingDocsModal, to: e.target.value })} onBlur={refreshMissingDocsPreview} data-testid="missing-to" style={{ width: "100%", padding: "0.5rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.3)", background: "#232326", color: "#e2e8f0", fontSize: 13 }} />
                    </label>
                    <label style={{ fontSize: 12 }}><b style={{ display: "block", marginBottom: 4 }}>Mensaje adicional (opcional)</b>
                      <textarea value={missingDocsModal.extra} onChange={(e) => setMissingDocsModal({ ...missingDocsModal, extra: e.target.value })} onBlur={refreshMissingDocsPreview} rows={2} data-testid="missing-extra" style={{ width: "100%", padding: "0.5rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.3)", background: "#232326", color: "#e2e8f0", fontSize: 13 }} />
                    </label>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                        <i className="fa fa-eye" style={{ color: "#facc15" }} />
                        <b style={{ fontSize: 12 }}>Preview (Asunto: <span style={{ color: "#facc15" }}>{p.subject}</span>)</b>
                      </div>
                      <div style={{ background: "#fff", color: "#111", borderRadius: 0, padding: "0.6rem 0.8rem", maxHeight: 280, overflow: "auto", border: "1px solid rgba(148,163,184,0.3)" }}
                           dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(p.body_html) }} />
                    </div>
                  </>
                )}
              </div>
              <div style={{ padding: "0.8rem 1.1rem", borderTop: "1px solid rgba(148,163,184,0.2)", display: "flex", gap: 8, justifyContent: "flex-end" }}>
                <button onClick={closeMissingDocsModal} disabled={missingDocsModal.sending} style={{ background: "transparent", border: "1px solid rgba(148,163,184,0.3)", color: "#94a3b8", borderRadius: 0, padding: "6px 14px", cursor: "pointer", fontSize: 13 }}>Cancelar</button>
                <button onClick={confirmSendMissingDocs} disabled={missingDocsModal.sending || !p} data-testid="btn-missing-send"
                  style={{ background: "#10c98a", border: "1px solid #0e9f6e", color: "#fff", borderRadius: 0, padding: "6px 18px", cursor: "pointer", fontSize: 13, fontWeight: 700, boxShadow: "0 2px 8px rgba(22,163,74,0.4)" }}>
                  <i className={`fa ${missingDocsModal.sending ? "fa-spinner fa-spin" : "fa-paper-plane"}`} /> {missingDocsModal.sending ? "Procesando…" : "Enviar correo"}
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {forzarModal && (() => {
        const m = forzarModal;
        const inpF = { width: "100%", padding: "0.55rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.3)", background: "#232326", color: "#e2e8f0", fontSize: 13 };
        return (
          <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.65)", zIndex: 9998, display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }} onClick={() => !m.forzando && setForzarModal(null)}>
            <div data-testid="forzar-modal" onClick={e => e.stopPropagation()} style={{ background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", border: "1px solid rgba(148,163,184,0.25)", borderRadius: 0, padding: "1.4rem", width: "min(640px, 96vw)", maxHeight: "90vh", overflow: "auto", display: "grid", gap: 10 }}>
              <h3 style={{ margin: 0, fontSize: 15, color: "#f59e0b" }}><i className="fa fa-bolt" /> Forzar Carpeta — buscá por nombre y/o RUT</h3>
              <label style={{ fontSize: 12 }}>Nombre del cliente <span style={{ opacity: 0.6 }}>(al escribir aparecen sugerencias de correos, archivos y carpetas)</span>
                <input data-testid="forzar-nombre" autoFocus style={inpF} value={m.nombre}
                  onChange={e => setForzarModal({ ...m, nombre: e.target.value, msg: "" })} placeholder="Ej: Pedro González" />
              </label>
              <label style={{ fontSize: 12 }}>RUT <span style={{ opacity: 0.6 }}>(opcional — con o sin puntos)</span>
                <input data-testid="forzar-rut" style={inpF} value={m.rut}
                  onChange={e => setForzarModal({ ...m, rut: e.target.value })} placeholder="Ej: 12.345.678-9" />
              </label>
              {m.buscando && <div style={{ fontSize: 12, color: "#94a3b8" }}><i className="fa fa-spinner fa-spin" /> Buscando coincidencias en carpetas, cola y buzón…</div>}
              {m.sug && !m.buscando && (
                <div data-testid="forzar-sugerencias" style={{ display: "grid", gap: 8 }}>
                  {(m.sug.carpetas || []).length > 0 && (
                    <div style={{ background: "rgba(212,175,55,0.06)", border: "1px dashed rgba(212,175,55,0.4)", borderRadius: 0, padding: "0.6rem 0.8rem" }}>
                      <div style={{ fontSize: 11, fontWeight: 800, color: "#d4af37", marginBottom: 4 }}>📁 CARPETAS EXISTENTES ({m.sug.carpetas.length})</div>
                      {m.sug.carpetas.map(c => <div key={c.id} style={{ fontSize: 12.5 }}>• {c.nombre} {c.rut && <span style={{ opacity: 0.6 }}>· {c.rut}</span>} — {c.archivos} archivo(s)</div>)}
                    </div>
                  )}
                  {(m.sug.correos || []).length > 0 && (
                    <div style={{ background: "rgba(212,175,55,0.06)", border: "1px dashed rgba(212,175,55,0.4)", borderRadius: 0, padding: "0.6rem 0.8rem" }}>
                      <div style={{ fontSize: 11, fontWeight: 800, color: "#d4af37", marginBottom: 4 }}>📧 CORREOS EN EL BUZÓN ({m.sug.correos.length}) — marcá uno o varios para descargar exactamente esos</div>
                      {m.sug.correos.map((c, i) => (
                        <label key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: 12, marginBottom: 4, cursor: c.message_id ? "pointer" : "default" }}>
                          {c.message_id && <input type="checkbox" data-testid={`forzar-correo-sel-${i}`} checked={!!c.sel}
                            onChange={() => setForzarModal(prev => ({ ...prev, sug: { ...prev.sug, correos: prev.sug.correos.map((x, j) => j === i ? { ...x, sel: !x.sel } : x) } }))} />}
                          <span>• <b>{(c.subject || "").slice(0, 60)}</b><br /><span style={{ opacity: 0.6, fontSize: 11 }}>{(c.from || "").slice(0, 50)} · {(c.date || "").slice(0, 22)}</span></span>
                        </label>
                      ))}
                    </div>
                  )}
                  {(m.sug.cola || []).length > 0 && (
                    <div style={{ background: "rgba(46,92,230,0.06)", border: "1px dashed rgba(46,92,230,0.4)", borderRadius: 0, padding: "0.6rem 0.8rem" }}>
                      <div style={{ fontSize: 11, fontWeight: 800, color: "#a78bfa", marginBottom: 4 }}>📥 EN LA COLA DE PROCESAMIENTO ({m.sug.cola.length})</div>
                      {m.sug.cola.map((c, i) => <div key={i} style={{ fontSize: 12 }}>• {(c.subject || "").slice(0, 55)} — {c.adjuntos} adjunto(s)</div>)}
                    </div>
                  )}
                  {!(m.sug.carpetas || []).length && !(m.sug.correos || []).length && !(m.sug.cola || []).length && (
                    <div style={{ fontSize: 12, color: "#fb7185" }}>Sin coincidencias por ahora — podés forzar igual y el sistema hará la búsqueda profunda (cuerpo de correos incluido).</div>
                  )}
                </div>
              )}
              {m.msg && <div data-testid="forzar-msg" style={{ fontSize: 12.5, fontWeight: 700, color: m.msg.startsWith("✅") ? "#34eab9" : "#fb7185" }}>{m.msg}</div>}
              <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                <button onClick={() => setForzarModal(null)} disabled={m.forzando} style={{ background: "transparent", border: "1px solid rgba(148,163,184,0.3)", color: "#94a3b8", borderRadius: 0, padding: "0.55rem 1rem", fontSize: 12.5, cursor: "pointer" }}>Cerrar</button>
                <button data-testid="forzar-ejecutar" onClick={ejecutarForzar} disabled={m.forzando || (!m.nombre.trim() && !m.rut.trim())}
                  style={{ background: "#f59e0b", border: "none", color: "#101012", borderRadius: 0, padding: "0.55rem 1.3rem", fontSize: 12.5, fontWeight: 800, cursor: "pointer" }}>
                  <i className={`fa ${m.forzando ? "fa-spinner fa-spin" : "fa-bolt"}`} /> {m.forzando ? "Forzando (busca y descarga adjuntos)…" : "Forzar Carpeta"}
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {reparosModal && (() => {
        const m = reparosModal;
        const rep = m.data?.reparos || {};
        const items = rep.items || [];
        const vendedor = m.data?.vendedor || {};
        const satisfecho = rep.estado === "satisfecho";
        const pendientes = items.filter(i => !i.satisfecho).length;
        const fmtF = (iso) => iso ? new Date(iso).toLocaleString("es-CL", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "";
        return (
          <div data-testid="reparos-modal" onClick={() => setReparosModal(null)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9998, padding: "3vh 3vw" }}>
            <div onClick={(e) => e.stopPropagation()} style={{ background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", color: "#e2e8f0", borderRadius: 0, width: "min(720px, 96vw)", maxHeight: "94vh", overflow: "auto", border: "1px solid rgba(148,163,184,0.25)", boxShadow: "0 20px 60px rgba(0,0,0,0.6)" }}>
              <div style={{ padding: "0.9rem 1.1rem", borderBottom: "1px solid rgba(148,163,184,0.2)", display: "flex", alignItems: "center", gap: 10 }}>
                <i className="fa fa-gavel" style={{ color: satisfecho ? "#34eab9" : "#fb7185" }} />
                <h4 style={{ margin: 0, flex: 1 }}>Reparos Estudio de Título — {m.folder.nombre}</h4>
                <button onClick={() => setReparosModal(null)} data-testid="btn-reparos-close" style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: 18 }}><i className="fa fa-times" /></button>
              </div>
              <div style={{ padding: "1rem 1.1rem", display: "grid", gap: "0.75rem" }}>
                {m.msg && (
                  <div data-testid="reparos-msg" style={{ padding: "0.6rem 0.9rem", borderRadius: 0, background: m.msg.startsWith("Error") ? "rgba(225,29,72,0.15)" : "rgba(16,217,142,0.15)", color: m.msg.startsWith("Error") ? "#fb7185" : "#34eab9", fontWeight: 600, fontSize: 13 }}>{m.msg}</div>
                )}
                {m.loading ? (
                  <div style={{ textAlign: "center", padding: "1.5rem" }}><i className="fa fa-spinner fa-spin" /> Cargando reparos…</div>
                ) : (
                  <>
                    <div style={{ fontSize: 12, color: "#94a3b8", background: "rgba(148,163,184,0.07)", border: "1px solid rgba(148,163,184,0.15)", borderRadius: 0, padding: "0.6rem 0.9rem", display: "grid", gap: 3 }}>
                      <div>🤖 El sistema revisa automáticamente el <b>hilo del correo</b> del estudio de título. Cuando el abogado envía reparos, se reenvían de inmediato al vendedor (CC Victoria Vilches).</div>
                      {rep.abogado_email && <div>⚖ Abogado detectado en el hilo: <b style={{ color: "#e2e8f0" }}>{rep.abogado_email}</b></div>}
                      {vendedor.email && <div>🏠 Vendedor: <b style={{ color: "#e2e8f0" }}>{vendedor.nombre || "—"}</b> · {vendedor.email}{vendedor.telefono ? ` · ${vendedor.telefono}` : ""}</div>}
                      {!vendedor.email && <div style={{ color: "#facc15" }}>⚠️ No hay correo del vendedor registrado — el reenvío automático de reparos no podrá enviarse.</div>}
                      {rep.detectado_en && <div>📥 Primeros reparos detectados: {fmtF(rep.detectado_en)}</div>}
                      {rep.reenviado_vendedor_at && <div>📤 Reparos reenviados al vendedor: {fmtF(rep.reenviado_vendedor_at)}</div>}
                      {rep.reenvio_vendedor_error && <div style={{ color: "#fb7185" }}>⚠️ Reenvío al vendedor: {rep.reenvio_vendedor_error}</div>}
                      {rep.recordatorio_enviado_at && <div>⏰ Recordatorio de estado enviado al abogado: {fmtF(rep.recordatorio_enviado_at)}</div>}
                      {m.data?.tipo_vivienda === "usada" && !rep.recordatorio_enviado_at && !satisfecho && items.length > 0 && (
                        <div>⏰ Vivienda usada: si a los 5 días no hay avance, se consultará el estado en el mismo hilo (una vez).</div>
                      )}
                    </div>

                    {items.length === 0 ? (
                      <div style={{ textAlign: "center", padding: "1rem", color: "#94a3b8", fontSize: 13 }} data-testid="reparos-vacio">
                        Aún no se han detectado reparos del abogado en el hilo de este estudio de título.
                      </div>
                    ) : (
                      <div style={{ display: "grid", gap: 6 }}>
                        {items.map((it) => (
                          <label key={it.n} data-testid={`reparo-item-${it.n}`} style={{ display: "flex", alignItems: "flex-start", gap: 10, background: it.satisfecho ? "rgba(16,217,142,0.08)" : "rgba(225,29,72,0.06)", border: `1px solid ${it.satisfecho ? "rgba(16,217,142,0.35)" : "rgba(225,29,72,0.25)"}`, borderRadius: 0, padding: "0.6rem 0.9rem", cursor: "pointer" }}>
                            <input type="checkbox" checked={!!it.satisfecho} onChange={(e) => toggleReparo(it.n, e.target.checked)} data-testid={`reparo-check-${it.n}`} style={{ marginTop: 3, width: 16, height: 16, accentColor: "#10d98e", cursor: "pointer" }} />
                            <div style={{ flex: 1 }}>
                              <div style={{ fontSize: 13, color: it.satisfecho ? "#6ee7c7" : "#e2e8f0", textDecoration: it.satisfecho ? "line-through" : "none" }}>{it.n}. {it.texto}</div>
                              <div style={{ fontSize: 11, color: it.satisfecho ? "#34eab9" : "#fb7185", fontWeight: 700, marginTop: 2 }}>
                                {it.satisfecho ? `✅ Reparo aceptado${it.satisfecho_en ? ` · ${fmtF(it.satisfecho_en)}` : ""}` : "Pendiente — marcar la casilla \"Reparo aceptado\" cuando quede resuelto"}
                              </div>
                            </div>
                          </label>
                        ))}
                      </div>
                    )}

                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end", borderTop: "1px solid rgba(148,163,184,0.15)", paddingTop: "0.8rem" }}>
                      <button onClick={scanReparos} disabled={m.scanning} data-testid="btn-reparos-scan"
                        style={{ background: "rgba(212,175,55,0.15)", border: "1px solid #d4af37", color: "#d4af37", borderRadius: 0, padding: "8px 14px", cursor: "pointer", fontSize: 13, fontWeight: 700 }}>
                        <i className={`fa ${m.scanning ? "fa-spinner fa-spin" : "fa-refresh"}`} /> {m.scanning ? "Revisando hilo…" : "Buscar reparos ahora"}
                      </button>
                      {satisfecho ? (
                        <div data-testid="reparos-satisfecho-badge" style={{ background: "rgba(16,217,142,0.15)", border: "1px solid #10d98e", color: "#34eab9", borderRadius: 0, padding: "8px 14px", fontSize: 13, fontWeight: 700 }}>
                          ✅ Todos los reparos satisfechos {rep.declarado_satisfecho_at ? `· ${fmtF(rep.declarado_satisfecho_at)}` : ""} {rep.declarado_por === "abogado" ? "(confirmado por el abogado)" : ""}
                        </div>
                      ) : (
                        <button onClick={declararReparos} disabled={m.declarando || items.length === 0 || pendientes > 0} data-testid="btn-reparos-declarar"
                          title={pendientes > 0 ? `Faltan ${pendientes} reparo(s) por marcar como satisfechos` : ""}
                          style={{ background: (m.declarando || items.length === 0 || pendientes > 0) ? "#475569" : "#10c98a", border: "none", color: "#fff", borderRadius: 0, padding: "8px 16px", cursor: (items.length === 0 || pendientes > 0) ? "not-allowed" : "pointer", fontSize: 13, fontWeight: 700 }}>
                          <i className={`fa ${m.declarando ? "fa-spinner fa-spin" : "fa-check-circle"}`} /> {m.declarando ? "Enviando aviso…" : "Declaro que todos los reparos han sido recibidos satisfactoriamente y podemos continuar con el estudio de título"}
                        </button>
                      )}
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        );
      })()}
      {codeudorModal && (
        <div data-testid="codeudor-modal" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.82)", zIndex: 3000, display: "flex", alignItems: "center", justifyContent: "center", backdropFilter: "blur(6px)" }}
          onClick={() => setCodeudorModal(null)}>
          <div onClick={e => e.stopPropagation()} style={{ width: 420, maxWidth: "92vw", background: "linear-gradient(160deg, rgba(22,22,24,0.98), rgba(8,8,9,0.99))", border: "1px solid rgba(212,175,55,0.45)", borderRadius: 0, padding: "1.6rem 1.7rem", boxShadow: "0 40px 90px -20px rgba(0,0,0,0.95), 0 0 44px -14px rgba(191,149,63,0.4)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: "1.1rem" }}>
              <i className="fa fa-user-plus" style={{ color: "var(--gold)" }} />
              <span style={{ fontSize: "0.95rem", fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "#fff" }}>Agregar Codeudor</span>
            </div>
            <div style={{ fontSize: "0.75rem", opacity: 0.65, marginBottom: "1rem" }}>Carpeta titular: <b style={{ color: "var(--gold)" }}>{codeudorModal.nombre}</b></div>
            <label style={{ fontSize: "0.7rem", letterSpacing: "0.1em", textTransform: "uppercase", opacity: 0.7 }}>Nombre del codeudor</label>
            <input data-testid="codeudor-nombre-input" value={codeudorForm.nombre} onChange={e => setCodeudorForm(p => ({ ...p, nombre: e.target.value }))}
              placeholder="Ej: Ángel Mayorga Soto" style={{ width: "100%", margin: "6px 0 14px", background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 0, color: "#fff", padding: "10px 12px", fontSize: "0.9rem" }} />
            <label style={{ fontSize: "0.7rem", letterSpacing: "0.1em", textTransform: "uppercase", color: "#e8cf7f", fontWeight: 700 }}>RUT del codeudor (obligatorio)</label>
            <input data-testid="codeudor-rut-input" value={codeudorForm.rut} onChange={e => setCodeudorForm(p => ({ ...p, rut: e.target.value }))}
              placeholder="12.345.678-9" style={{ width: "100%", margin: "6px 0 6px", background: "rgba(212,175,55,0.08)", border: "1px solid rgba(212,175,55,0.55)", borderRadius: 0, color: "#f4dc82", fontWeight: 700, letterSpacing: "0.06em", padding: "10px 12px", fontSize: "0.95rem", fontFamily: "'JetBrains Mono', monospace" }} />
            <div style={{ fontSize: "0.68rem", color: "rgba(232,207,127,0.75)", marginBottom: "1.2rem" }}>
              <i className="fa fa-link" style={{ marginRight: 5 }} />Todo documento entrante con este RUT irá directo a la subcarpeta 05_Codeudor del titular — sin crear carpetas nuevas.
            </div>
            <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
              <button data-testid="codeudor-cancelar-btn" onClick={() => setCodeudorModal(null)} style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.25)", color: "#cbd5e1", borderRadius: 0, padding: "9px 16px", cursor: "pointer", fontSize: "0.8rem" }}>Cancelar</button>
              <button data-testid="codeudor-guardar-btn" onClick={guardarCodeudor} style={{ background: "linear-gradient(135deg, #BF953F, #FCF6BA 45%, #B38728)", border: "none", color: "#141414", fontWeight: 800, borderRadius: 0, padding: "9px 20px", cursor: "pointer", fontSize: "0.8rem", letterSpacing: "0.05em" }}>
                <i className="fa fa-check" style={{ marginRight: 6 }} />Vincular Codeudor
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
