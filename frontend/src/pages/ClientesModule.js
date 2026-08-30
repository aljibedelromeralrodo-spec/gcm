import React, { useState, useEffect, useRef } from "react";
// Orquestador: lista, ficha, correos, ajustes y modales viven en ./clientes/ (misma UI).
import axios from "axios";
import { secureGet } from "../utils/secureStore";
import { guardarEstado, leerEstado, tomarRegreso } from "../utils/navegacion";
import { API } from "./clientes/clientesShared";
import { ClientesCtx } from "./clientes/clientesCtx";
import ClientesLista from "./clientes/ClientesLista";
import ClientesFicha from "./clientes/ClientesFicha";
import ClientesEmails from "./clientes/ClientesEmails";
import ClientesAjustes from "./clientes/ClientesAjustes";
import ClientesModales from "./clientes/ClientesModales";
import ClientesPreview from "./clientes/ClientesPreview";

export default function ClientesModule({ onNavigate }) {
  const [view, setView] = useState("list"); // list, detail, emails, ajustes
  const [folders, setFolders] = useState([]);
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState("");
  const [currentFolder, setCurrentFolder] = useState(null);
  const [techo, setTecho] = useState(null);
  const [showCompromiso, setShowCompromiso] = useState(false);
  const [compromisoLibre, setCompromisoLibre] = useState(null);
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
  const [moraUp, setMoraUp] = useState(null); // folder_id subiendo comprobante de mora
  const [moraMsg, setMoraMsg] = useState({}); // { folder_id: { ok, texto } }
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
  const [folderTab, setFolderTab] = useState("clientes"); // clientes | escrituracion | calendario
  const [evalNeg, setEvalNeg] = useState({}); // folder_id → última simulación negativa (No Calificó)
  const [notificandoNC, setNotificandoNC] = useState("");
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
  // Deep-link desde el aviso de mora: #cliente-{folderId} abre la ficha directo
  useEffect(() => {
    const h = window.location.hash;
    if (h.startsWith("#cliente-")) {
      const fid = h.slice(9);
      if (fid) openFolder(fid);
      window.history.replaceState(null, "", window.location.pathname);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    axios.get(`${API}/api/clientes/evaluaciones-negativas`)
      .then(r => setEvalNeg(r.data.negativas || {})).catch(() => setEvalNeg({}));
  }, []);

  const notificarNoCalifico = async (f) => {
    if (!window.confirm(`Se enviará un correo al ejecutivo/solicitante asociado informando que ${f.nombre} NO CALIFICÓ en la evaluación. ¿Continuar?`)) return;
    setNotificandoNC(f.id);
    try {
      const r = await axios.post(`${API}/api/clientes/folders/${f.id}/notificar-no-califico`, {});
      window.alert(`✅ Resultado notificado a: ${(r.data.destinatarios || []).join(", ")}`);
      loadFolders();
    } catch (e) {
      window.alert(e.response?.data?.detail || "No fue posible enviar la notificación");
    }
    setNotificandoNC("");
  };

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

  const openTasacion = (f) => {
    const df = f.datos_financieros || {};
    const valorUF0 = df.valor_propiedad || "";
    // FIX LATENCIA: el modal abre AL INSTANTE; los datos lentos (OCR + IA) llegan en segundo plano
    setTasacionModal({
      folder: f, archivos: [], tipo: "Individual",
      destinatarios: "contacto@valueproperty.cl, victoriavilches@centralmutuos.cl",
      modalidad: "inmobiliaria", broker_id: "",
      inmobiliaria: df.inmobiliaria || "",
      inmo_contacto_nombre: "", inmo_contacto_email: "",
      intro: "", voucher_nombre: "", fecha_tasacion: f.tasacion_fecha || "",
      direccion: df.direccion || "", comuna: df.comuna || "", ciudad: df.ciudad || "",
      unidad: "", rol_avaluo: "",
      valor_uf: valorUF0 ? String(valorUF0) : "",
      valor_esperado_uf: valorUF0 ? String(valorUF0) : "",
      vendedor: "", vendedor_email: "",
      contacto_nombre: "", contacto_telefono: "", contacto_email: "",
      observaciones: "", preview: null, loading: false, msg: "", prefillLoading: true,
    });
    const mergeSiActual = (updater) => setTasacionModal(prev =>
      (prev && prev.folder?.id === f.id ? updater(prev) : prev));
    const cargarArchivos = async () => {
      try {
        const r = await axios.get(`${API}/api/clientes/folders/${f.id}`);
        const archivos = (r.data.archivos || []).map(a => ({ ...a, sel: /carta|oferta|aprobaci/i.test(a.nombre) }))
          .sort((a, b) => (b.sel ? 1 : 0) - (a.sel ? 1 : 0));
        mergeSiActual(prev => {
          const selPrev = Object.fromEntries((prev.archivos || []).map(a => [a.nombre, a.sel]));
          return { ...prev, archivos: archivos.map(a => (a.nombre in selPrev ? { ...a, sel: selPrev[a.nombre] } : a)) };
        });
      } catch (_e) { /* sin archivos */ }
    };
    cargarArchivos();
    // REGLA: la carta de aprobación debe estar SIEMPRE descargada antes de tasar (best effort, en background)
    axios.post(`${API}/api/clientes/folders/${f.id}/sync-aprobacion`, {}, { timeout: 90000 })
      .then(cargarArchivos).catch(() => {});
    Promise.all([axios.get(`${API}/api/tasacion/contactos`), axios.get(`${API}/api/brokers`)])
      .then(([c, b]) => { setTasacionContactos(c.data.contactos || []); setBrokers(b.data.brokers || []); })
      .catch(() => setTasacionContactos([]));
    axios.get(`${API}/api/clientes/folders/${f.id}/tasacion-prefill`, { timeout: 120000 })
      .then(pf => {
        const prefill = pf.data.prefill || {};
        mergeSiActual(prev => {
          const v = prev.valor_uf || (prefill.valor_propiedad_uf ? String(prefill.valor_propiedad_uf) : "");
          return { ...prev, prefillLoading: false,
            inmobiliaria: prev.inmobiliaria || prefill.inmobiliaria || "",
            direccion: prev.direccion || prefill.direccion || "",
            comuna: prev.comuna || prefill.comuna || "",
            ciudad: prev.ciudad || prefill.ciudad || "",
            unidad: prev.unidad || prefill.unidad || "",
            rol_avaluo: prev.rol_avaluo || prefill.rol_avaluo || "",
            valor_uf: v, valor_esperado_uf: prev.valor_esperado_uf || v,
            vendedor: prev.vendedor || prefill.vendedor_nombre || "",
            vendedor_email: prev.vendedor_email || prefill.vendedor_email || "",
            contacto_nombre: prev.contacto_nombre || prefill.vendedor_nombre || "",
            contacto_telefono: prev.contacto_telefono || prefill.vendedor_telefono || "",
            contacto_email: prev.contacto_email || prefill.vendedor_email || "" };
        });
      })
      .catch(() => mergeSiActual(prev => ({ ...prev, prefillLoading: false })));
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
    const faltan = (f.alertas_documentales && f.alertas_documentales.length)
      ? f.alertas_documentales
      : (f.criterios || []).filter(c => !c.ok && !["Enviada a mesa", "Datos financieros completos"].includes(c.nombre)).map(c => c.nombre);
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

  const openEstudio = (f) => {
    // FIX LATENCIA: modal instantáneo; prefill OCR/IA y defaults llegan en segundo plano
    setEstudioModal({
      folder: f, archivos: [],
      destinatarios: "contacto@hipotecariogestion.cl, victoriavilches@centralmutuos.cl",
      cc: (f.estudio_titulo_cc || []).join(", "),
      tipo_vivienda: "nueva",
      docs_usada: [], docs_nueva: [],
      inmobiliaria: f.datos_financieros?.inmobiliaria || "",
      inmo_contacto_nombre: "", inmo_contacto_email: "",
      vendedor_nombre: "", vendedor_email: "", vendedor_telefono: "",
      intro: "",
      direccion: f.datos_financieros?.direccion || "", observaciones: "",
      docs_texto: "",
      preview: null, loading: false, msg: "", prefillLoading: true,
    });
    const mergeSiActual = (updater) => setEstudioModal(prev =>
      (prev && prev.folder?.id === f.id ? updater(prev) : prev));
    Promise.all([
      axios.get(`${API}/api/clientes/folders/${f.id}`),
      axios.get(`${API}/api/estudio-titulo/defaults`),
    ]).then(([r, d]) => {
      const archivos = (r.data.archivos || []).map(a => ({ ...a, sel: /carta|oferta|aprobaci/i.test(a.nombre) }))
        .sort((a, b) => (b.sel ? 1 : 0) - (a.sel ? 1 : 0));
      const defaults = d.data || {};
      mergeSiActual(prev => ({ ...prev, archivos,
        destinatarios: (defaults.destinatarios || []).join(", ") || prev.destinatarios,
        docs_usada: defaults.docs_usada || [], docs_nueva: defaults.docs_nueva || [],
        docs_texto: prev.docs_texto || (prev.tipo_vivienda === "usada"
          ? (defaults.docs_usada || []).join("\n") : (defaults.docs_nueva || []).join("\n")) }));
    }).catch(() => {});
    reloadBrokers();
    axios.get(`${API}/api/plantillas?tipo=estudio`)
      .then(p => setEstudioPlantillas(p.data.plantillas || [])).catch(e => console.error(e));
    axios.get(`${API}/api/tasacion/contactos`)
      .then(c => setTasacionContactos(c.data.contactos || [])).catch(e => console.error(e));
    axios.get(`${API}/api/clientes/folders/${f.id}/tasacion-prefill`, { timeout: 120000 })
      .then(pf => {
        const prefill = pf.data.prefill || {};
        mergeSiActual(prev => ({ ...prev, prefillLoading: false,
          inmobiliaria: prev.inmobiliaria || prefill.inmobiliaria || "",
          direccion: prev.direccion || prefill.direccion || "",
          vendedor_nombre: prev.vendedor_nombre || prefill.vendedor_nombre || "",
          vendedor_email: prev.vendedor_email || prefill.vendedor_email || "",
          vendedor_telefono: prev.vendedor_telefono || prefill.vendedor_telefono || "" }));
      })
      .catch(() => mergeSiActual(prev => ({ ...prev, prefillLoading: false })));
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
    sessionStorage.setItem("cm_nav_scroll_clientes", String(window.scrollY));
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
      resolucion_serviu: df.resolucion_serviu ?? false,
      tipo_vivienda: df.tipo_vivienda || "nueva",
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
        resolucion_serviu: ex.resolucion_serviu ?? prev.resolucion_serviu,
        tipo_vivienda: ex.tipo_vivienda || prev.tipo_vivienda,
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


  const subirComprobanteMora = async (f, file, tipo = "comprobante") => {
    if (!file) return;
    setMoraUp(f.id);
    setMoraMsg(s => ({ ...s, [f.id]: null }));
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("tipo", tipo);
      const r = await axios.post(`${API}/api/clientes/folders/${f.id}/aclarar-mora`, fd);
      setMoraMsg(s => ({ ...s, [f.id]: { ok: true, texto: r.data.mensaje } }));
      loadFolders();
    } catch (e) {
      setMoraMsg(s => ({ ...s, [f.id]: { ok: false, texto: e.response?.data?.detail || "Error al subir el documento. Intente nuevamente." } }));
    } finally {
      setMoraUp(null);
    }
  };

  const enviarLinkPagoMora = async (f) => {
    if (!window.confirm(`Se enviará al cliente el monto de la mora y los datos oficiales de pago. ¿Continuar?`)) return;
    setMoraUp(f.id);
    setMoraMsg(s => ({ ...s, [f.id]: null }));
    try {
      const r = await axios.post(`${API}/api/clientes/folders/${f.id}/mora-link-pago`);
      setMoraMsg(s => ({ ...s, [f.id]: { ok: true, texto: r.data.mensaje } }));
      loadFolders();
    } catch (e) {
      setMoraMsg(s => ({ ...s, [f.id]: { ok: false, texto: e.response?.data?.detail || "Error al enviar el link de pago." } }));
    } finally {
      setMoraUp(null);
    }
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
    } catch (err) { alert(err?.response?.data?.detail || "Error creando carpeta"); }
    setLoading(false);
  };

  const openFolder = async (folderId, autoAction) => {
    sessionStorage.setItem("cm_nav_scroll_clientes", String(window.scrollY));
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

  // Apertura instantánea desde la Telepantalla Cognitiva (clic en nodo)
  // + NORMATIVA DE NAVEGACIÓN: al regresar con "Volver" desde otro módulo,
  //   restaurar pestaña, carpeta abierta y scroll exactos.
  useEffect(() => {
    const fid = sessionStorage.getItem("cm_abrir_folder_id");
    if (fid) {
      sessionStorage.removeItem("cm_abrir_folder_id");
      openFolder(fid);
      return;
    }
    if (tomarRegreso("clientes")) {
      const est = leerEstado("clientes");
      if (est) {
        if (est.folderTab) setFolderTab(est.folderTab);
        if (est.view === "detail" && est.folderId) openFolder(est.folderId);
        else {
          const y = parseFloat(sessionStorage.getItem("cm_nav_scroll_clientes") || "0");
          setTimeout(() => window.scrollTo(0, y), 300);
        }
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // NORMATIVA DE NAVEGACIÓN: persistir estado y restaurar scroll al volver a la lista
  useEffect(() => {
    guardarEstado("clientes", { view, folderId: currentFolder?.id || null, folderTab });
  }, [view, currentFolder, folderTab]);
  const prevViewRef = useRef(view);
  useEffect(() => {
    if (view === "list" && prevViewRef.current !== "list") {
      const y = parseFloat(sessionStorage.getItem("cm_nav_scroll_clientes") || "0");
      setTimeout(() => window.scrollTo(0, y), 80);
      setTimeout(() => window.scrollTo(0, y), 350);
    }
    prevViewRef.current = view;
  }, [view]);

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
    sessionStorage.setItem("cm_nav_scroll_clientes", String(window.scrollY));
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
    window.open(`${API}/api/clientes/folders/${folderId}/download/${filePath}?t=${encodeURIComponent(secureGet("token", false) || "")}`, "_blank");
  };

  const openPreview = (folderId, filePath, fileName) => {
    const url = `${API}/api/clientes/folders/${folderId}/download/${encodeURI(filePath)}?inline=true&t=${encodeURIComponent(secureGet("token", false) || "")}`;
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
      ? "Cédula → Impuesto Renta / F22 → Boletas / DAI → CMF → Extras"
      : clientType === "mixto"
      ? "Cédula → Liquidaciones → AFP → Impuesto Renta / F22 → Boletas / DAI → CMF → Extras"
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
    if (em.force_discrepancia) p.force_discrepancia = true;
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
    const disc = em.preview?.viabilidad?.discrepancia;
    if (disc?.nivel === "alerta" && !em.force_discrepancia) {
      alert(`🚫 ENVÍO BLOQUEADO — Discrepancia de riesgo Mutuaria vs Concreces\n\n${disc.mensaje || ""}\n\nPara enviar igual, marcá "Asumo el sesgo interno vs Espejo Concreces" en el preview.`);
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
    window.open(`${API}/api/clientes/folders/${folderId}/download-all?t=${encodeURIComponent(secureGet("token", false) || "")}`, "_blank");
  };

  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
  };

  const filtered = folderTab === "calendario" ? [] : folders.filter(f =>
    (!searchQuery || f.nombre.toLowerCase().includes(searchQuery.toLowerCase())) &&
    (folderTab === "escrituracion" ? !!f.is_escrituracion : !f.is_escrituracion)
  );
  const countEscrituracion = folders.filter(f => !!f.is_escrituracion).length;
  const countClientes = folders.length - countEscrituracion;

  const ctx = {
    view,
    setView,
    folders,
    setFolders,
    syncing,
    setSyncing,
    syncMsg,
    setSyncMsg,
    currentFolder,
    setCurrentFolder,
    techo,
    setTecho,
    showCompromiso,
    setShowCompromiso,
    compromisoLibre,
    setCompromisoLibre,
    techoBusy,
    setTechoBusy,
    emails,
    setEmails,
    loading,
    setLoading,
    showCreate,
    setShowCreate,
    newFolder,
    setNewFolder,
    searchQuery,
    setSearchQuery,
    emailSearch,
    setEmailSearch,
    emailResults,
    setEmailResults,
    savingAttachment,
    setSavingAttachment,
    ajustes,
    setAjustes,
    editingId,
    setEditingId,
    editDraft,
    setEditDraft,
    savingEdit,
    setSavingEdit,
    finOpenId,
    setFinOpenId,
    finDraft,
    setFinDraft,
    finSaving,
    setFinSaving,
    ocrRunning,
    setOcrRunning,
    previewFile,
    setPreviewFile,
    selectedFiles,
    setSelectedFiles,
    uploadingFor,
    setUploadingFor,
    uploadingManual,
    setUploadingManual,
    moraUp,
    setMoraUp,
    moraMsg,
    setMoraMsg,
    merging,
    setMerging,
    mergingProto,
    setMergingProto,
    splittingRel,
    setSplittingRel,
    emailModal,
    setEmailModal,
    tasacionModal,
    setTasacionModal,
    tasacionContactos,
    setTasacionContactos,
    estudioPlantillas,
    setEstudioPlantillas,
    brokers,
    setBrokers,
    estudioModal,
    setEstudioModal,
    reparosModal,
    setReparosModal,
    escrituraModal,
    setEscrituraModal,
    notarias,
    setNotarias,
    pedirModal,
    setPedirModal,
    missingDocsModal,
    setMissingDocsModal,
    historialModal,
    setHistorialModal,
    _respaldoModal,
    setRespaldoModal,
    folderTab,
    setFolderTab,
    evalNeg,
    setEvalNeg,
    notificandoNC,
    setNotificandoNC,
    enriching,
    setEnriching,
    forzarModal,
    setForzarModal,
    _importarRespaldo,
    ufValue,
    setUfValue,
    fileInputRef,
    uploadCtxRef,
    notificarNoCalifico,
    loadUf,
    fmtAct,
    fmtActFull,
    openHistorial,
    marcarTerminado,
    openTasacion,
    subirVoucher,
    detectarFechaTasacion,
    guardarFechaTasacion,
    pickInmoPlantilla,
    reloadBrokers,
    openPedirFaltantes,
    pedirPayload,
    pedirPreview,
    pedirEnviar,
    tasacionPayload,
    tasacionPreview,
    tasacionEnviar,
    openReparos,
    scanReparos,
    toggleReparo,
    declararReparos,
    openEstudio,
    guardarPlantillaEstudio,
    aplicarPlantillaEstudio,
    eliminarPlantillaEstudio,
    estudioPayload,
    estudioPreview,
    estudioEnviar,
    enviarEtapa2,
    _buscarCorreosEstudio,
    openEscritura,
    reloadNotarias,
    escrituraPayload,
    escrituraPreview,
    escrituraEnviar,
    escrituraAddNotaria,
    escrituraSaveNotariaEmail,
    refreshUfFromSii,
    updateUf,
    loadAjustes,
    startEdit,
    cancelEdit,
    saveEdit,
    resetEdit,
    calcularTecho,
    openFinPanel,
    closeFinPanel,
    saveFinPanel,
    runOcrFin,
    subirComprobanteMora,
    enviarLinkPagoMora,
    loadFolders,
    cloudSync,
    toggleEnvioManual,
    createFolder,
    openFolder,
    prevViewRef,
    handleManualUpload,
    regenerateCombined,
    deleteFolder,
    loadEmails,
    searchEmails,
    saveAttachmentToFolder,
    codeudorModal,
    setCodeudorModal,
    codeudorForm,
    setCodeudorForm,
    agregarCodeudor,
    guardarCodeudor,
    saveAllAttachments,
    downloadFile,
    openPreview,
    closePreview,
    toggleSelect,
    isSelected,
    selectionCount,
    clearSelection,
    triggerUpload,
    handleFileSelected,
    deleteClientFile,
    mergeSelected,
    splitBundled,
    mergeByProtocol,
    autocorreoDest,
    setAutocorreoDest,
    openEmailModal,
    closeEmailModal,
    buildEmailPayload,
    previewClientEmail,
    confirmSendClientEmail,
    openMissingDocsModal,
    closeMissingDocsModal,
    refreshMissingDocsPreview,
    confirmSendMissingDocs,
    toggleEscrituracion,
    enriquecerCarpeta,
    ejecutarForzar,
    downloadAll,
    formatSize,
    filtered,
    countEscrituracion,
    countClientes,
    onNavigate,
  };

  return (
    <ClientesCtx.Provider value={ctx}>
    <div className="clientes-module" data-testid="clientes-module">
      {view === "list" && <ClientesLista />}
      {view === "detail" && currentFolder && <ClientesFicha />}
      {view === "emails" && <ClientesEmails />}
      {view === "ajustes" && <ClientesAjustes />}
      <input
        ref={fileInputRef}
        type="file"
        style={{ display: "none" }}
        onChange={handleFileSelected}
        data-testid="hidden-file-input"
      />
      <ClientesModales />
      <ClientesPreview />
    </div>
    </ClientesCtx.Provider>
  );
}
