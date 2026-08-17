import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { secureGet } from "../utils/secureStore";

const API = process.env.REACT_APP_BACKEND_URL;
const ESTADOS = ["Tasación Piloto", "Solicitada", "En Proceso", "Con Observaciones", "Aprobada", "Rechazada"];
const HITO_LABEL = { tasacion: "Tasación", estudio: "Estudio de Títulos", cesion: "Cesión", set_credito: "Cédula de Crédito (SET)",
  cert_subsidio: "Certificado de Subsidio", carta_pie: "Carta Pie",
  serviu: "Resolución Serviu", promesa: "Promesa de Compraventa", carpeta_notaria: "Carpeta en Notaría", escritura: "Escritura en Notaría",
  notaria: "Notaría", carta_oferta: "Carta Oferta" };
const ESTADOS_POR = {
  tasacion: ["Pendiente", "Solicitada", "Tasación Piloto", "En Proceso", "Recibida", "Con Observaciones", "Aprobada"],
  estudio: ["Pendiente", "Solicitado", "En Proceso", "Recibido", "Con Reparos", "Aprobado"],
  serviu: ["Pendiente", "Solicitada", "Recibida", "Aprobada", "Rechazada", "Pendiente verificación manual"],
  carta_oferta: ["Pendiente", "Solicitada", "Recibida", "Aprobada", "Rechazada", "Pendiente verificación manual"],
  promesa: ["Pendiente", "Redactada", "Firmada", "Firmada (verificada IA)", "Enviada a Notaría", "Pendiente verificación manual"],
  cert_subsidio: ["Pendiente", "Solicitada", "Recibida", "Aprobada", "Pendiente verificación manual"],
  carta_pie: ["Pendiente", "Solicitada", "Recibida", "Aprobada", "Pendiente verificación manual"],
  set_credito: ["Pendiente", "Set Para la Firma", "Verificación Pendiente", "Firmado y Verificado"],
  carpeta_notaria: ["Pendiente", "Preparando Carpeta", "Enviada", "Recibida por Notaría", "En Revisión", "Aprobada"],
  escritura: ["Pendiente", "Agendada", "Firmada", "Inscrita en CBR"],
  cesion: ["Pendiente", "Confirmada"],
};
const SET_LABEL = {
  firmado: "✅ Set Firmado",
  verificacion_pendiente: "⚠️ Verificación Pendiente",
  esperando_firma: "⏳ Esperando Firma del Cliente",
};
const CAMPO_LABEL = { rut: "RUT", inmobiliaria: "Inmobiliaria", broker: "Broker", monto: "Monto UF", proyecto: "Proyecto", ciudad: "Ciudad" };

// P12: cada estado es un BOTÓN con color propio (spec de alto contraste)
const estadoBg = (estado, manual) => {
  const e = (estado || "").toLowerCase();
  let st;
  if (/verificaci.*manual/.test(e)) st = { background: "#1A3A8A", color: "#fff" };
  else if (!e || /pendiente/.test(e)) st = { background: "#2A2A2A", color: "#888", fontStyle: "italic", border: "1px dashed #555" };
  else if (/(aprobad|firmado|verificada ia|verificado$|informe recibido|recibida|recibido|confirmada|limpio|inscrita)/.test(e)) st = { background: "#1A5C2A", color: "#fff" };
  else if (/(observacion|reparo|verificaci)/.test(e)) st = { background: "#7A4A00", color: "#fff" };
  else if (/(rechaz|bloquead)/.test(e)) st = { background: "#5C1A1A", color: "#fff" };
  else st = { background: "#1A3A5C", color: "#fff" };
  if (manual) st = { background: "#3A3A3A", color: "#fff", border: "1px solid #eab308" };
  return st;
};

const MESES_ES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
  "Septiembre", "Octubre", "Noviembre", "Diciembre"];
const nombreMes = (m) => m ? `${MESES_ES[parseInt(m.slice(5, 7), 10) - 1]} ${m.slice(0, 4)}` : "";
const mesSiguiente = (m) => {
  const y = parseInt(m.slice(0, 4), 10), mm = parseInt(m.slice(5, 7), 10);
  return mm === 12 ? `${y + 1}-01` : `${y}-${String(mm + 1).padStart(2, "0")}`;
};

const colorAvance = (p) => p >= 100 ? "linear-gradient(90deg,#d4af37,#FFD700)"
  : p >= 90 ? "#22c55e" : p >= 61 ? "#eab308" : p >= 31 ? "#f97316" : "#ef4444";

const celda = { padding: "12px 16px", borderRight: "1px solid rgba(255,255,255,0.5)", fontSize: 14, verticalAlign: "top" };
const celdaId = { ...celda, background: "rgba(0,0,0,0.22)" };
const th = { padding: "14px 16px", textAlign: "left", borderRight: "1px solid rgba(255,255,255,0.35)",
  whiteSpace: "nowrap", fontSize: 13, letterSpacing: 1, height: 48, minHeight: 48,
  position: "sticky", top: 0, zIndex: 30, textTransform: "uppercase", color: "#D4AF37",
  background: "linear-gradient(rgba(212,175,55,0.20), rgba(212,175,55,0.20)), #0f172a",
  boxShadow: "0 4px 10px rgba(0,0,0,0.45)" };
const btnPdf = {
  display: "block", marginTop: 3, cursor: "pointer", background: "rgba(34,197,94,0.15)",
  border: "1px solid rgba(34,197,94,0.6)", color: "#4ade80", borderRadius: 8,
  padding: "0.15rem 0.5rem", fontSize: "0.58rem", fontWeight: 800,
};
const modalBg = {
  position: "fixed", inset: 0, zIndex: 220, background: "rgba(2,6,23,0.8)",
  backdropFilter: "blur(8px)", display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem",
};
const modalBox = {
  width: "100%", maxWidth: 520, background: "rgba(15,23,42,0.97)",
  borderRadius: 16, padding: "1.4rem 1.6rem", boxShadow: "0 30px 80px rgba(0,0,0,0.6)",
};
const inputStyle = {
  width: "100%", background: "rgba(2,6,23,0.7)", border: "1px solid rgba(212,175,55,0.35)",
  borderRadius: 10, color: "#f8fafc", padding: "0.55rem 0.8rem", fontSize: "0.78rem", marginTop: 8,
};

export default function SupercarpetaModule() {
  const [data, setData] = useState(null);
  const [solo24, setSolo24] = useState(false);
  const [preview, setPreview] = useState(null);
  const [reparoModal, setReparoModal] = useState(null);
  const [bitModal, setBitModal] = useState(null);
  const [manualModal, setManualModal] = useState(null);
  const [estadoModal, setEstadoModal] = useState(null);
  const [conflictoModal, setConflictoModal] = useState(null);
  const [fuentesModal, setFuentesModal] = useState(null);
  const [agregarModal, setAgregarModal] = useState(null);
  const [panel, setPanel] = useState(null);
  const [editCell, setEditCell] = useState(null);
  const [auditoria, setAuditoria] = useState(null);
  const [mes, setMes] = useState("2026-08");
  const [avanceModal, setAvanceModal] = useState(null);
  const [remitentesModal, setRemitentesModal] = useState(null);
  const [cbrModal, setCbrModal] = useState(null);
  const [cbrEdit, setCbrEdit] = useState(null);
  const [vbEdit, setVbEdit] = useState(null);
  const [inmoModal, setInmoModal] = useState(null);
  const [solicitudModal, setSolicitudModal] = useState(null);
  // ACCESO EXCLUSIVO: módulo Comisiones/CBR solo para el Administrador General
  const esAdminGeneral = ["admin", "maestro"].includes((secureGet("user") || {}).rol);
  const [guardando, setGuardando] = useState(false);
  const [isMobile, setIsMobile] = useState(window.matchMedia("(max-width: 768px)").matches);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 768px)");
    const fn = e => setIsMobile(e.matches);
    mq.addEventListener("change", fn);
    return () => mq.removeEventListener("change", fn);
  }, []);

  const abrirPanel = async (c, hito) => {
    setPanel({ fid: c.id, cliente: c.cliente, hito, loading: true, nota: "", nuevoEstado: "" });
    try {
      const r = await axios.get(`${API}/api/supercarpeta/panel/${c.id}?hito=${hito}`);
      setPanel(p => ({ ...p, loading: false, data: r.data }));
    } catch { setPanel(p => ({ ...p, loading: false, data: null })); }
  };

  const guardarEstadoPanel = async () => {
    if (!panel?.nuevoEstado) return;
    setGuardando(true);
    try {
      await axios.post(`${API}/api/supercarpeta/estado/${panel.fid}`, { hito: panel.hito, estado: panel.nuevoEstado });
      recargar();
      const r = await axios.get(`${API}/api/supercarpeta/panel/${panel.fid}?hito=${panel.hito}`);
      setPanel(p => ({ ...p, data: r.data, nuevoEstado: "" }));
    } catch (e) { window.alert(e.response?.data?.detail || "Error al guardar estado"); }
    setGuardando(false);
  };

  const guardarNota = async () => {
    if (!panel?.nota?.trim()) return;
    setGuardando(true);
    try {
      await axios.post(`${API}/api/supercarpeta/nota/${panel.fid}`, { hito: panel.hito, texto: panel.nota.trim() });
      const r = await axios.get(`${API}/api/supercarpeta/panel/${panel.fid}?hito=${panel.hito}`);
      setPanel(p => ({ ...p, data: r.data, nota: "" }));
    } catch (e) { window.alert(e.response?.data?.detail || "Error al guardar nota"); }
    setGuardando(false);
  };

  const recargar = useCallback(() => {
    axios.get(`${API}/api/supercarpeta?mes=${mes}`).then(r => setData(r.data)).catch(() => setData({ clientes: [] }));
  }, [mes]);
  useEffect(() => { recargar(); }, [recargar]);

  const verBitacora = async (c, hito) => {
    setBitModal({ cliente: c.cliente, loading: true });
    try {
      const r = await axios.get(`${API}/api/supercarpeta/bitacora/${c.id}?hito=${hito}`);
      setBitModal({ cliente: c.cliente, loading: false, ...r.data });
    } catch (e) {
      setBitModal({ cliente: c.cliente, loading: false, error_seguimiento: true,
        detalle: e.response?.data?.detail || "Error consultando la bitácora" });
    }
  };

  const abrir = async (fid, cliente, inf) => {
    try {
      const r = await axios.get(`${API}/api/supercarpeta/archivo/${fid}`, {
        params: { ruta: inf.archivo }, responseType: "blob" });
      const url = URL.createObjectURL(new Blob([r.data], { type: "application/pdf" }));
      setPreview({ url, cliente, archivo: inf.archivo });
    } catch (e) { window.alert(e.response?.status === 404 ? "Informe no disponible" : "Error al abrir el informe"); }
  };

  const manejar409 = (e) => {
    const d = e.response?.data?.detail;
    if (e.response?.status === 409 && d?.code === "ORIGEN_NO_CONFIGURADO") {
      window.alert(`🚫 GUARDADO BLOQUEADO — ${d.mensaje}\n\nSe abrirá el Panel de Fuentes para registrar "${d.valor}" con todos sus contactos.`);
      setManualModal(null); setEditCell(null);
      abrirInmobiliarias().then(() => setInmoModal(m => (m ? { ...m,
        reg: d.campo === "broker"
          ? { tipo: "broker", nombre: d.valor, tipo_broker: "word_consultor", email: "", tasacion_nombre: "", tasacion_email: "", estudio_nombre: "", estudio_email: "", carta_nombre: "", carta_email: "" }
          : { tipo: "inmobiliaria", nombre: d.valor, email_general: "", tieneProyectos: true, proyectos: [regProyectoVacio()] } } : m)));
      return true;
    }
    return false;
  };

  const guardarManual = async () => {
    if (!manualModal?.valor?.trim()) return;
    setGuardando(true);
    try {
      await axios.post(`${API}/api/supercarpeta/manual/${manualModal.fid}`,
        { campo: manualModal.campo, valor: manualModal.valor.trim() });
      setManualModal(null); recargar();
    } catch (e) { if (!manejar409(e)) window.alert(e.response?.data?.detail?.mensaje || e.response?.data?.detail || "Error al guardar"); }
    setGuardando(false);
  };

  const guardarEstado = async () => {
    if (!estadoModal?.estado?.trim()) return;
    setGuardando(true);
    try {
      await axios.post(`${API}/api/supercarpeta/estado/${estadoModal.fid}`,
        { hito: estadoModal.hito, estado: estadoModal.estado.trim() });
      setEstadoModal(null); recargar();
    } catch (e) { window.alert(e.response?.data?.detail || "Error al guardar estado"); }
    setGuardando(false);
  };

  const resolverConflicto = async (accion) => {
    setGuardando(true);
    try {
      await axios.post(`${API}/api/supercarpeta/estado/${conflictoModal.fid}/resolver`,
        { hito: conflictoModal.hito, accion });
      setConflictoModal(null); recargar();
    } catch (e) { window.alert(e.response?.data?.detail || "Error al resolver"); }
    setGuardando(false);
  };

  const abrirFuentes = async (hito) => {
    setFuentesModal({ hito, loading: true });
    try {
      const [r, rb] = await Promise.all([
        axios.get(`${API}/api/supercarpeta/fuentes-doc`),
        axios.get(`${API}/api/supercarpeta/cuenta-barrido`).catch(() => ({ data: null })),
      ]);
      setFuentesModal({ hito, loading: false, globales: r.data.fuentes?.[hito] || [],
        alternativas: r.data.alternativas_cliente || [], barrido: rb.data,
        gCorreo: "", gNombre: "", cliSel: "", iCorreo: "", iNombre: "" });
    } catch { setFuentesModal({ hito, loading: false, globales: [], alternativas: [], barrido: null, gCorreo: "", gNombre: "", cliSel: "", iCorreo: "", iNombre: "" }); }
  };

  const opBarrido = async (body, barrer = false) => {
    setGuardando(true);
    try {
      const url = `${API}/api/supercarpeta/cuenta-barrido${barrer ? "/barrer" : ""}`;
      await axios.post(url, body || {});
      const rb = await axios.get(`${API}/api/supercarpeta/cuenta-barrido`);
      setFuentesModal(m => (m ? { ...m, barrido: rb.data } : m));
    } catch (e) { window.alert(e.response?.data?.detail || "Error en la cuenta de barrido"); }
    setGuardando(false);
  };

  const guardarEdit = async (valor) => {
    const v = String(valor ?? "").trim();
    if (!editCell || !v) { setEditCell(null); return; }
    setGuardando(true);
    try {
      await axios.post(`${API}/api/supercarpeta/manual/${editCell.fid}`, { campo: editCell.campo, valor: v });
      setEditCell(null); recargar();
    } catch (e) { if (!manejar409(e)) window.alert(e.response?.data?.detail?.mensaje || e.response?.data?.detail || "Error al guardar el campo"); }
    setGuardando(false);
  };

  const abrirRemitentes = async () => {
    setRemitentesModal({ loading: true });
    try {
      const r = await axios.get(`${API}/api/supercarpeta/remitentes-detectados`);
      setRemitentesModal({ loading: false, ...r.data });
    } catch { setRemitentesModal(null); }
  };

  const accionRemitente = async (d, accion, destino) => {
    try {
      await axios.post(`${API}/api/supercarpeta/remitentes-detectados/accion`,
        { folder_id: d.folder_id, hito: d.hito, correo: d.correo, accion, hito_destino: destino || "" });
      abrirRemitentes();
    } catch (e) { window.alert(e.response?.data?.detail || "Error en la acción"); }
  };

  const lanzarAuditoria = async () => {
    setAuditoria({ loading: true });
    try {
      await axios.post(`${API}/api/supercarpeta/auditoria-boveda`);
      let intentos = 0;
      const poll = setInterval(async () => {
        intentos += 1;
        try {
          const r = await axios.get(`${API}/api/supercarpeta/auditoria-boveda`);
          if (r.data.estado !== "en_proceso" || intentos > 80) {
            clearInterval(poll);
            setAuditoria({ loading: false, ...r.data });
            recargar();
          }
        } catch { clearInterval(poll); setAuditoria(null); }
      }, 3000);
    } catch (e) { setAuditoria(null); window.alert(e.response?.data?.detail || "Error al lanzar la auditoría"); }
  };

  const opFuente = async (ambito, accion, correo, nombre) => {
    setGuardando(true);
    try {
      const url = ambito === "global"
        ? `${API}/api/supercarpeta/fuentes-doc`
        : `${API}/api/supercarpeta/fuentes-doc/${fuentesModal.cliSel}`;
      await axios.post(url, { hito: fuentesModal.hito, accion, correo, nombre: nombre || "" });
      const r = await axios.get(`${API}/api/supercarpeta/fuentes-doc`);
      setFuentesModal(m => ({ ...m, globales: r.data.fuentes?.[m.hito] || [],
        alternativas: r.data.alternativas_cliente || [], gCorreo: "", gNombre: "", iCorreo: "", iNombre: "" }));
    } catch (e) { window.alert(e.response?.data?.detail || "Error al actualizar fuente"); }
    setGuardando(false);
  };

  const agregarCliente = async () => {
    if (!agregarModal?.nombre?.trim()) return;
    setGuardando(true);
    try {
      await axios.post(`${API}/api/supercarpeta/cliente`, { ...agregarModal, mes });
      setAgregarModal(null); recargar();
    } catch (e) { window.alert(e.response?.data?.detail || "Error al agregar cliente"); }
    setGuardando(false);
  };

  const eliminarCliente = async (c) => {
    if (!window.confirm(`¿Estás seguro de eliminar a ${c.cliente} de la proyección de ${nombreMes(mes)}?\nEsta acción no elimina su ficha de ADN_CLIENTES_360 (se conserva como registro histórico) y queda en bitácora.`)) return;
    try {
      await axios.post(`${API}/api/supercarpeta/cliente/${c.id}/eliminar`);
      recargar();
    } catch (e) { window.alert(e.response?.data?.detail || "Error al eliminar"); }
  };

  const moverMes = async (c) => {
    const destino = mesSiguiente(mes);
    if (!window.confirm(`¿Deseas mover a ${c.cliente} a la proyección de ${nombreMes(destino)}?\nConserva todos sus datos y estados; queda con etiqueta "Arrastre ${nombreMes(mes)}" y en bitácora. Nunca se borra nada.`)) return;
    try {
      await axios.post(`${API}/api/supercarpeta/mes-siguiente/${c.id}`, { mes_destino: destino });
      recargar();
    } catch (e) { window.alert(e.response?.data?.detail || "Error al trasladar de mes"); }
  };

  const refrescarCbr = async () => {
    const r = await axios.get(`${API}/api/supercarpeta/cbr/estado`);
    setCbrModal(m => (m ? { ...m, ...r.data, loading: false } : m));
    return r.data;
  };
  const abrirCbr = async () => {
    setCbrModal({ loading: true });
    try { await refrescarCbr(); } catch { setCbrModal(m => ({ ...m, loading: false })); }
  };
  const lanzarCbr = async () => {
    try {
      await axios.post(`${API}/api/supercarpeta/cbr/extraer`, {});
      setCbrModal(m => ({ ...m, estado: "en_proceso" }));
      const poll = setInterval(async () => {
        try {
          const d = await refrescarCbr();
          if (d.estado !== "en_proceso") { clearInterval(poll); recargar(); }
        } catch { clearInterval(poll); }
      }, 4000);
    } catch (e) { window.alert(e.response?.data?.detail || "Error al lanzar la extracción CBR"); }
  };
  const descargarCbrExcel = async () => {
    try {
      const r = await axios.get(`${API}/api/supercarpeta/cbr/excel`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `costos_CBR_${new Date().toISOString().slice(0, 10)}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { window.alert("Aún no hay resultados CBR para exportar — ejecute primero la extracción"); }
  };

  const guardarCbrManual = async () => {
    if (!cbrEdit) return;
    const { fila, campo, valor } = cbrEdit;
    setCbrEdit(null);
    try {
      await axios.post(`${API}/api/supercarpeta/cbr/manual`, { cliente: fila.cliente, fid: fila.fid, campo, valor });
      await refrescarCbr();
    } catch (e) { window.alert(e.response?.data?.detail || "Error al guardar el valor manual"); }
  };

  const guardarValorBase = async () => {
    if (!vbEdit) return;
    const { campo, valor } = vbEdit;
    setVbEdit(null);
    try {
      await axios.post(`${API}/api/supercarpeta/valores-base`, { [campo]: valor });
      await refrescarCbr();
    } catch (e) { window.alert(e.response?.data?.detail || "Error al guardar el valor base"); }
  };
  const valorBaseSpan = (campo, etiqueta) => (
    <span data-testid={`vb-${campo}`} title="Doble clic para editar el valor global (no afecta valores manuales)"
      onDoubleClick={() => setVbEdit({ campo, valor: cbrModal?.valores_base?.[campo] ?? "" })}
      style={{ cursor: "cell", fontWeight: 800, color: "#d4af37" }}>
      {vbEdit?.campo === campo ? (
        <input data-testid={`vb-${campo}-input`} autoFocus value={vbEdit.valor}
          onChange={e => setVbEdit({ ...vbEdit, valor: e.target.value })}
          onBlur={guardarValorBase}
          onKeyDown={e => { if (e.key === "Enter") guardarValorBase(); if (e.key === "Escape") setVbEdit(null); }}
          style={{ width: 50, background: "#0f172a", color: "#e2e8f0", border: "1px solid #3b82f6", borderRadius: 4, padding: "1px 4px", fontSize: "0.62rem" }} />
      ) : `${etiqueta}: ${Number(cbrModal?.valores_base?.[campo] ?? 0).toLocaleString("es-CL")} UF`}
    </span>
  );

  const abrirInmobiliarias = async () => {
    setInmoModal({ loading: true });
    try {
      const [rf, rg] = await Promise.all([
        axios.get(`${API}/api/supercarpeta/fuentes-panel`),
        axios.get(`${API}/api/supercarpeta/cc-globales`)]);
      const grupos = rf.data.inmobiliarias || [];
      setInmoModal({ loading: false,
        contactos: grupos.flatMap(g => g.proyectos || []),
        generales: grupos.map(g => ({ inmobiliaria: g.inmobiliaria, email: g.correo_general })),
        brokers: rf.data.brokers || [], vendedores: rf.data.individuales || [],
        lista_maestra: rf.data.lista_maestra || {}, cc: rg.data.lista || [],
        exp: {}, reg: null,
        nuevo: { inmobiliaria: "", proyecto: "", contacto: "", email: "" },
        nuevoCc: { nombre: "", email: "" } });
    } catch (e) { setInmoModal(null); window.alert(e.response?.data?.detail || "Error al cargar el panel de fuentes"); }
  };
  const guardarGeneral = async (g) => {
    try {
      await axios.post(`${API}/api/supercarpeta/inmobiliaria-general`, g);
      await abrirInmobiliarias();
    } catch (e) { window.alert(e.response?.data?.detail || "Error al guardar el correo general"); }
  };
  const guardarBroker = async (b) => {
    try {
      await axios.post(`${API}/api/supercarpeta/brokers-fuentes`, b);
      await abrirInmobiliarias();
    } catch (e) { window.alert(e.response?.data?.detail || "Error al guardar el broker"); }
  };
  const editarBroker = (i, campo, valor) => setInmoModal(m => ({
    ...m, brokers: m.brokers.map((x, j) => j === i ? { ...x, [campo]: valor } : x) }));
  const editarGeneral = (i, valor) => setInmoModal(m => ({
    ...m, generales: m.generales.map((x, j) => j === i ? { ...x, email: valor } : x) }));
  const guardarRegistro = async () => {
    const r = inmoModal.reg;
    if (!r?.nombre?.trim()) { window.alert("El nombre es obligatorio"); return; }
    try {
      if (r.tipo === "broker") {
        await axios.post(`${API}/api/supercarpeta/brokers-fuentes`, r);
      } else {
        await axios.post(`${API}/api/supercarpeta/inmobiliaria-general`, { inmobiliaria: r.nombre, email: r.email_general || "" });
        for (const p of (r.proyectos || [])) {
          if (p.contacto || p.email || p.proyecto || p.tasacion_email || p.estudio_email) {
            await axios.post(`${API}/api/supercarpeta/contactos-carta`, { ...p, inmobiliaria: r.nombre });
          }
        }
      }
      window.alert("✅ Origen registrado con todos sus contactos");
      await abrirInmobiliarias();
    } catch (e) { window.alert(e.response?.data?.detail || "Error al registrar"); }
  };
  const regProyectoVacio = () => ({ proyecto: "", contacto: "", email: "",
    tasacion_nombre: "", tasacion_email: "", estudio_nombre: "", estudio_email: "" });
  const guardarContacto = async (c) => {
    try {
      await axios.post(`${API}/api/supercarpeta/contactos-carta`, c);
      await abrirInmobiliarias();
    } catch (e) { window.alert(e.response?.data?.detail || "Error al guardar el contacto"); }
  };
  const editarContacto = (i, campo, valor) => setInmoModal(m => ({
    ...m, contactos: m.contactos.map((x, j) => j === i ? { ...x, [campo]: valor } : x) }));
  const guardarCc = async (x) => {
    try {
      await axios.post(`${API}/api/supercarpeta/cc-globales`, x);
      await abrirInmobiliarias();
    } catch (e) { window.alert(e.response?.data?.detail || "Error al guardar el destinatario"); }
  };
  const editarCc = (i, campo, valor) => setInmoModal(m => ({
    ...m, cc: m.cc.map((x, j) => j === i ? { ...x, [campo]: valor } : x) }));
  const guardarVendedor = async (v) => {
    try {
      await axios.post(`${API}/api/supercarpeta/vendedores-usada`, v);
      await abrirInmobiliarias();
    } catch (e) { window.alert(e.response?.data?.detail || "Error al guardar el vendedor"); }
  };
  const editarVendedor = (i, campo, valor) => setInmoModal(m => ({
    ...m, vendedores: m.vendedores.map((x, j) => j === i ? { ...x, [campo]: valor } : x) }));

  const abrirSolicitud = async (c, doc = "") => {
    setSolicitudModal({ loading: true, fid: c.id });
    try {
      const r = await axios.get(`${API}/api/supercarpeta/solicitud-doc/${c.id}${doc ? `?doc=${doc}` : ""}`);
      setSolicitudModal({ loading: false, fid: c.id, ...r.data });
    } catch (e) { setSolicitudModal(null); window.alert(e.response?.data?.detail || "Error al preparar la solicitud"); }
  };
  const enviarSolicitud = async () => {
    const m = solicitudModal;
    setSolicitudModal({ ...m, enviando: true });
    try {
      const r = await axios.post(`${API}/api/supercarpeta/solicitud-doc/${m.fid}/enviar`, {
        para: m.para, asunto: m.asunto, cuerpo: m.cuerpo, doc_elegido: m.doc_elegido || "",
        encargado: m.encargado || "",
        rut: m.rut, proyecto: m.proyecto, resolucion_serviu: m.resolucion_serviu });
      setSolicitudModal(null);
      window.alert(`✅ Solicitud enviada a ${m.para} (CC: ${(r.data.cc || []).join(", ") || "—"}) — ${(m.docs_solicitados || []).join(" y ")} queda(n) "Solicitada"`);
      recargar();
    } catch (e) {
      setSolicitudModal({ ...m, enviando: false });
      window.alert(e.response?.data?.detail || "Error al enviar la solicitud");
    }
  };

  const celdaCbrEdit = (r, i, campo, opts = {}) => {
    const editando = cbrEdit && (cbrEdit.fila.fid ? cbrEdit.fila.fid === r.fid : cbrEdit.fila.cliente === r.cliente) && cbrEdit.campo === campo;
    const manual = r[`${campo}_origen`] === "manual";
    const v = r[campo];
    const mostrar = v !== "" && v != null
      ? (opts.texto ? String(v) : `${Number(v).toLocaleString("es-CL")}${opts.sufijo || ""}`)
      : "—";
    return (
      <td key={campo} data-testid={`cbr-${campo}-${i}`}
        title="Doble clic para editar (gris = automático, azul = manual). Se guarda al instante en ADN_CLIENTES_360"
        onDoubleClick={() => setCbrEdit({ fila: r, campo, valor: v ?? "" })}
        style={{ padding: "6px 8px", fontWeight: opts.suave ? 500 : 800, whiteSpace: "nowrap", cursor: "cell",
          color: manual ? "#93c5fd" : (opts.color || "#cbd5e1"),
          background: manual ? "rgba(59,130,246,0.14)" : "rgba(148,163,184,0.08)", ...(opts.estilo || {}) }}>
        {editando ? (
          <input data-testid={`cbr-${campo}-input-${i}`} autoFocus value={cbrEdit.valor}
            onChange={e => setCbrEdit({ ...cbrEdit, valor: e.target.value })}
            onBlur={guardarCbrManual}
            onKeyDown={e => { if (e.key === "Enter") guardarCbrManual(); if (e.key === "Escape") setCbrEdit(null); }}
            style={{ width: opts.texto ? 110 : 64, background: "#0f172a", color: "#e2e8f0", border: "1px solid #3b82f6", borderRadius: 4, padding: "2px 4px", fontSize: "0.64rem" }} />
        ) : mostrar}
      </td>
    );
  };

  const totalPagadoFila = (r) => {
    if (r.total_pagado_origen === "manual" && r.total_pagado !== "" && r.total_pagado != null)
      return { tot: Number(r.total_pagado), hay: true, incompleto: false, manual: true };
    const nums = [r.valor_cbr, r.tasacion, r.est_titulos]
      .filter(x => x !== "" && x != null).map(Number);
    return { tot: Math.round(nums.reduce((a, b) => a + b, 0) * 100) / 100,
             hay: nums.length > 0, incompleto: nums.length < 3, manual: false };
  };

  const clientes = (data?.clientes || []).filter(c => !solo24 || c.recien_24h);
  const proy = data?.proyeccion;

  const lapiz = (c, hito) => (
    <button data-testid={`editar-estado-${hito}-${c.id}`}
      onClick={() => setEstadoModal({ fid: c.id, cliente: c.cliente, hito, estado: "" })}
      title="Editar estado manualmente (Gerencia) — queda en bitácora inmutable"
      style={{ cursor: "pointer", border: "none", background: "transparent", padding: "0 3px",
        fontSize: "0.62rem", opacity: 0.85 }}>✏️</button>
  );
  const marcaManual = (c, hito) => c.manual?.[hito] && (
    <span data-testid={`marca-manual-${hito}-${c.id}`} title="Estado modificado manualmente por Gerencia"
      style={{ marginLeft: 3, fontSize: "0.55rem", color: "#eab308", fontWeight: 800 }}>✏️ manual</span>
  );
  const marcaConflicto = (c, hito) => c.conflicto?.[hito] && (
    <button data-testid={`conflicto-${hito}-${c.id}`}
      onClick={() => setConflictoModal({ fid: c.id, cliente: c.cliente, hito })}
      title="DashAI detectó un dato nuevo por correo: decidir si sobreescribe el estado manual"
      style={{ display: "block", cursor: "pointer", border: "1px solid rgba(239,68,68,0.6)",
        background: "rgba(239,68,68,0.2)", color: "#fca5a5", borderRadius: 8,
        padding: "1px 6px", fontSize: "0.55rem", fontWeight: 800, marginTop: 2 }}>❓ Dato nuevo detectado</button>
  );
  const btnFaltante = (c, campo) => (
    <button data-testid={`manual-btn-${campo}-${c.id}`}
      onClick={() => setManualModal({ fid: c.id, cliente: c.cliente, campo, valor: "" })}
      title="⚠️ FALLO DE COSECHA: este dato no está en la Bóveda ADN — ingreso manual de respaldo"
      style={{ cursor: "pointer", border: "1px solid rgba(239,68,68,0.55)", background: "rgba(239,68,68,0.14)",
        color: "#ef4444", borderRadius: 8, padding: "2px 7px", fontSize: "0.56rem", fontWeight: 800 }}>
      ⚠️ {CAMPO_LABEL[campo]}</button>
  );
  const gear = (hito) => (
    <button data-testid={`fuentes-gear-${hito}`} onClick={() => abrirFuentes(hito)}
      title="Configurar correos fuente de esta columna (Gerencia)"
      style={{ cursor: "pointer", border: "none", background: "transparent", padding: "0 2px",
        fontSize: "0.72rem", opacity: 0.9 }}>⚙️</button>
  );
  const pendiente = <span style={{ fontStyle: "italic", color: "#94a3b8" }}>Pendiente</span>;

  const editable = (c, campo, contenido, valorActual) =>
    editCell && editCell.fid === c.id && editCell.campo === campo ? (
      <input autoFocus data-testid={`edit-inline-${campo}-${c.id}`} defaultValue={editCell.valor}
        onKeyDown={e => { if (e.key === "Enter") guardarEdit(e.target.value); if (e.key === "Escape") setEditCell(null); }}
        onBlur={() => setEditCell(null)}
        style={{ background: "rgba(2,6,23,0.95)", border: "1.5px solid #d4af37", borderRadius: 6,
          color: "#f8fafc", padding: "0.25rem 0.45rem", fontSize: 13, width: "100%", minWidth: 100 }} />
    ) : (
      <span data-testid={`editable-${campo}-${c.id}`}
        onDoubleClick={() => setEditCell({ fid: c.id, campo, valor: valorActual ?? "" })}
        title="Doble clic para editar (Gerencia): Enter guarda en ADN_CLIENTES_360, Escape cancela — queda en bitácora"
        style={{ cursor: "text" }}>
        {contenido}
        {c.manual_identidad?.includes(campo) &&
          <span data-testid={`marca-identidad-${campo}-${c.id}`} title="Editado manualmente por Gerencia"
            style={{ marginLeft: 3, fontSize: 10, color: "#eab308", fontWeight: 800 }}>✏️</span>}
      </span>
    );

  const celdaEstado = (c, hito, estado, opts = {}) => {
    const na = opts.naSinSubsidio && !c.con_subsidio;
    const st = na ? { background: "#2A2A2A", color: "#666", fontStyle: "italic" }
      : estadoBg(estado, c.manual?.[hito]);
    return (
      <td key={hito} data-testid={`super-${hito}-${c.id}`} style={{ ...celda, minWidth: 130 }}>
        {na ? <div style={{ ...st, borderRadius: 6, padding: "6px 12px", textAlign: "center" }}>N/A</div> : (<>
          <button data-testid={`panel-${hito}-${c.id}`} onClick={() => abrirPanel(c, hito)}
            className="estado-btn"
            title={`Abrir panel de ${HITO_LABEL[hito]}: correos detectados, notas y bitácora`}
            style={{ ...st, cursor: "pointer", width: "100%", borderRadius: 6, padding: "6px 12px",
              fontWeight: 800, fontSize: 13, textAlign: "center",
              boxShadow: "0 2px 6px rgba(0,0,0,0.45)",
              border: st.border || "1px solid rgba(255,255,255,0.12)" }}>
            {estado || "Pendiente"}
          </button>
          <div style={{ marginTop: 3, textAlign: "center" }}>
            {lapiz(c, hito)}{marcaManual(c, hito)}{marcaConflicto(c, hito)}
          </div>
          {opts.extra}
        </>)}
      </td>
    );
  };

  return (
    <div className="module-content seamless-scope" data-testid="supercarpeta-module" style={{ minHeight: "100%", padding: "1.1rem", borderRadius: 12 }}>
      <style>{`
        .super-row { transition: background-color .15s ease, box-shadow .15s ease; border-left: 3px solid transparent; }
        .super-row:hover { filter: brightness(1.14); border-left: 3px solid #d4af37; cursor: pointer; }
        .super-row:active { box-shadow: inset 0 0 0 2px #d4af37; }
        .estado-btn { transition: filter .15s ease, box-shadow .15s ease; }
        .estado-btn:hover { filter: brightness(1.2); box-shadow: 0 0 0 1.5px #d4af37, 0 2px 8px rgba(0,0,0,0.5) !important; }
      `}</style>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 10 }}>
        <h3 style={{ margin: 0, color: "#f8fafc", fontSize: "1.02rem" }}>
          <i className="fa fa-folder folder-metal" style={{ marginRight: 8 }} />Supercarpeta de Management — {data?.mes || "…"}
        </h3>
        <span style={{ color: "#94a3b8", fontSize: "0.7rem" }}>
          {clientes.length}/{data?.total ?? 0} clientes · Regla #67: la Bóveda ADN_CLIENTES_360 manda
        </span>
        <select data-testid="selector-mes" value={mes} onChange={e => setMes(e.target.value)}
          title="Navegación entre proyecciones mensuales — todas comparten la misma Bóveda ADN_CLIENTES_360"
          style={{ background: "rgba(212,175,55,0.12)", border: "1px solid rgba(212,175,55,0.5)", color: "#d4af37",
            borderRadius: 10, padding: "0.45rem 0.7rem", fontWeight: 800, fontSize: "0.72rem", cursor: "pointer" }}>
          {(data?.meses || ["2026-08", "2026-09"]).map(m =>
            <option key={m} value={m} style={{ background: "#0f172a" }}>{nombreMes(m)}</option>)}
        </select>
        <button data-testid="auditar-boveda-btn" onClick={lanzarAuditoria} disabled={auditoria?.loading}
          title="Regla de Hierro: audita RUT y campos de identidad en 4 fuentes (ficha ADN, EXPEDIENTE_360, documentos, correos 90 días)"
          className="maserati-btn" style={{ marginLeft: "auto", minHeight: 38 }}>
          {auditoria?.loading ? "🧬 Auditando…" : "🧬 Auditar Bóveda"}</button>
        <button data-testid="remitentes-btn" onClick={abrirRemitentes}
          title="Remitentes capturados automáticamente por DashAI — confirmar, reubicar, eliminar o bloquear"
          className="maserati-btn" style={{ minHeight: 38 }}>📡 Remitentes</button>
        <button data-testid="inmobiliarias-btn" onClick={abrirInmobiliarias}
          title="Inmobiliarias detectadas con su encargado y correo — a quién se le pide Carta Oferta y Resolución Serviu"
          className="maserati-btn" style={{ minHeight: 38 }}>🏢 Inmobiliarias</button>
        {esAdminGeneral && <button data-testid="cbr-btn" onClick={abrirCbr}
          title="Buscar los costos CBR en las simulaciones de aprobaciones@centralmutuos.cl y calcular comisiones — EXCLUSIVO Administrador General"
          className="maserati-btn" style={{ minHeight: 38 }}>💰 CBR Mesa</button>}
        <button data-testid="agregar-cliente-btn" onClick={() => setAgregarModal({
          nombre: "", inmobiliaria: "", proyecto: "", ciudad: "", broker: "Mutuaria y Leasing Limitada",
          tipo_propiedad: "nueva", subsidio: "Sin Subsidio", monto_uf: "" })}
          className="maserati-btn" style={{ minHeight: 38 }}>➕ Agregar Cliente</button>
        <button data-testid="filtro-recien-24h" onClick={() => setSolo24(v => !v)}
          className={`maserati-btn ${solo24 ? "" : "neon"}`} style={{ minHeight: 38 }}>
          🟢 Recién llegados 24h ({data?.recien_llegados ?? 0}) {solo24 ? "· quitar filtro" : ""}
        </button>
      </div>
      {proy && (
        <div data-testid="proyeccion-meta" style={{ position: "sticky", top: 0, zIndex: 60, marginBottom: 10, padding: "0.7rem 1rem",
          background: "linear-gradient(rgba(212,175,55,0.10), rgba(212,175,55,0.10)), #0f172a",
          border: "1px solid rgba(212,175,55,0.35)", borderRadius: 12, boxShadow: "0 6px 18px rgba(0,0,0,0.45)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <b style={{ color: "#d4af37", fontSize: "0.74rem" }}>
              🎯 Proyección {nombreMes(mes)} — {proy.broker}: {proy.suma_uf?.toLocaleString("es-CL")} / {proy.meta_uf?.toLocaleString("es-CL")} UF ({proy.avance_pct}%)
            </b>
            {proy.alerta_diferencia && (
              <span data-testid="proyeccion-alerta" style={{ color: "#ef4444", fontWeight: 800, fontSize: "0.64rem" }}>
                ⚠️ ALERTA GERENCIA: diferencia de {proy.diferencia_uf?.toLocaleString("es-CL")} UF vs la meta
                {proy.pendientes_monto?.length > 0 && ` · Monto pendiente: ${proy.pendientes_monto.join(", ")}`}
              </span>
            )}
          </div>
          <div data-testid="meta-avance-panel" style={{ display: "flex", gap: 16, flexWrap: "wrap", marginTop: 8, alignItems: "center" }}>
            <div style={{ minWidth: 220, flex: 1, maxWidth: 340 }}>
              <div style={{ color: "#94a3b8", fontSize: "0.58rem", fontWeight: 800, letterSpacing: 1 }}>
                META TOTAL (avance promedio): <b style={{ color: "#f8fafc", fontSize: "0.72rem" }}>{proy.avance_promedio ?? 0}%</b></div>
              <div style={{ marginTop: 3, height: 8, background: "rgba(0,0,0,0.35)", borderRadius: 99, overflow: "hidden" }}>
                <div style={{ width: `${Math.min(proy.avance_promedio || 0, 100)}%`, height: "100%", borderRadius: 99,
                  background: colorAvance(proy.avance_promedio || 0) }} />
              </div>
            </div>
            {[["UF PROYECTADAS", (proy.meta_uf || 0).toLocaleString("es-CL"), "#d4af37"],
              ["UF EN AVANCE (>50%)", (proy.uf_en_avance || 0).toLocaleString("es-CL"), "#60a5fa"],
              ["UF CERRADAS (100%)", (proy.uf_cerradas || 0).toLocaleString("es-CL"), "#4ade80"],
              ["CUMPLIMIENTO GLOBAL", `${proy.pct_global ?? 0}%`, (proy.pct_global || 0) >= 100 ? "#FFD700" : "#f8fafc"]].map(([k, v, col]) => (
              <div key={k} data-testid={`meta-${k.split(" ")[0].toLowerCase()}-${k.split(" ")[1]?.toLowerCase() || ""}`}>
                <div style={{ color: "#94a3b8", fontSize: "0.56rem", fontWeight: 800, letterSpacing: 1 }}>{k}</div>
                <div style={{ color: col, fontWeight: 900, fontSize: "0.92rem" }}>{v}</div>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 6, height: 7, background: "rgba(148,163,184,0.15)", borderRadius: 99, overflow: "hidden" }}>
            <div style={{ width: `${Math.min(proy.avance_pct || 0, 100)}%`, height: "100%",
              background: "linear-gradient(90deg,#d4af37,#f5d76e)", borderRadius: 99 }} />
          </div>
        </div>
      )}
      {isMobile ? (
        /* 📱 VISTA MÓVIL: tarjetas apiladas por cliente (la tabla queda intacta en escritorio) */
        <div data-testid="supercarpeta-cards" style={{ display: "grid", gap: 10 }}>
          {clientes.map((c, idx) => (
            <div key={c.id} data-testid={`super-card-${c.id}`}
              style={{ background: idx % 2 === 0 ? "#1E2A3A" : "#253347",
                border: "1px solid rgba(212,175,55,0.35)", borderRadius: 12, padding: "0.8rem" }}>
              <div style={{ display: "flex", gap: 8, alignItems: "baseline", flexWrap: "wrap" }}>
                <b data-testid={`super-card-numero-${c.id}`} style={{ color: "#D4AF37", fontSize: 15 }}>{idx + 1}</b>
                <b style={{ color: "#fff", fontSize: 15, flex: 1, overflowWrap: "anywhere" }}>{c.cliente}</b>
                <span style={{ color: "#B0BEC5", fontFamily: "monospace", fontSize: 12 }}>{c.rut || "—"}</span>
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 4, fontSize: 12, color: "#90A4AE", alignItems: "center" }}>
                <span>{c.inmobiliaria}</span>
                {c.proyecto && <span>· {c.proyecto}</span>}
                {c.subsidio && <span style={{ background: c.subsidio.toLowerCase().startsWith("con") ? "#2E7D32" : "#37474F",
                  color: "#fff", borderRadius: 999, padding: "1px 8px", fontSize: 11 }}>{c.subsidio}</span>}
                <b style={{ marginLeft: "auto", color: "#D4AF37" }}>{c.monto_uf ? `${Number(c.monto_uf).toLocaleString("es-CL")} UF` : "—"}</b>
              </div>
              <div style={{ marginTop: 8 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#cbd5e1" }}>
                  <span>Avance</span><b style={{ color: (c.avance?.pct || 0) >= 100 ? "#FFD700" : "#f8fafc" }}>{c.avance?.pct ?? 0}%</b>
                </div>
                <div style={{ marginTop: 3, height: 7, background: "rgba(0,0,0,0.35)", borderRadius: 99, overflow: "hidden" }}
                  onClick={() => setAvanceModal(c)}>
                  <div style={{ width: `${Math.min(c.avance?.pct || 0, 100)}%`, height: "100%", borderRadius: 99,
                    background: colorAvance(c.avance?.pct || 0) }} />
                </div>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginTop: 8 }}>
                {[["tasacion", c.estado_tasacion], ["estudio", c.estudio_titulos],
                  ["serviu", c.con_subsidio ? c.serviu : null],
                  ["carta_oferta", c.carta_oferta], ["promesa", c.promesa],
                  ["set_credito", SET_LABEL[c.set_credito?.estado] || c.set_credito?.estado || "Pendiente"],
                  ["carpeta_notaria", c.carpeta_notaria], ["escritura", c.escritura]]
                  .filter(([, est]) => est !== null).map(([h, est]) => (
                    <button key={h} data-testid={`card-${h}-${c.id}`} onClick={() => abrirPanel(c, h)}
                      style={{ ...estadoBg(est, c.manual?.[h]), border: "none", borderRadius: 999,
                        padding: "4px 10px", fontSize: 11, fontWeight: 700, cursor: "pointer", maxWidth: "100%" }}>
                      {HITO_LABEL[h]}: {est || "Pendiente"}
                    </button>
                  ))}
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8, flexWrap: "wrap" }}>
                <div title={c.docs_co_rs?.detalle || ""} style={{ display: "flex", gap: 5, flexWrap: "wrap", cursor: "help" }}>
                  {(c.docs_co_rs?.documentos || []).map((d, di) => (
                    <span key={d.hito || di} title={`${d.label}: ${d.estado}`} style={{ fontSize: 10, fontWeight: 800,
                      color: { verde: "#4ade80", azul: "#93c5fd", amarillo: "#facc15", rojo: "#f87171" }[d.color] }}>
                      {d.icono} {d.label.split(" / ")[0]}</span>
                  ))}
                </div>
                <button data-testid={`card-solicitar-${c.id}`} onClick={() => abrirSolicitud(c)}
                  style={{ ...btnPdf, display: "inline-block", marginTop: 0, background: "rgba(96,165,250,0.15)",
                    border: "1px solid rgba(96,165,250,0.6)", color: "#60a5fa" }}>
                  📨 Pedir Documentos</button>
                {c.promesa_ia && <span style={{ fontSize: 11, color: c.promesa_ia.firmado ? "#4ade80" : "#93c5fd" }}
                  title={c.promesa_ia.evidencia}>🤖 {c.promesa_ia.firmado ? "Firma verificada" : "Revisar firma"}</span>}
                <span style={{ marginLeft: "auto", fontSize: 11, color: c.fecha_firma ? "#FFD700" : "#64748b" }}>
                  📅 {c.fecha_firma ? String(c.fecha_firma).slice(0, 10) : "sin fecha"}</span>
              </div>
            </div>
          ))}
          {data && clientes.length === 0 && <p style={{ color: "#94a3b8", textAlign: "center", padding: "1.5rem" }}>Sin clientes en la vista.</p>}
        </div>
      ) : (
      <div style={{ background: "rgba(15,23,42,0.6)", border: "1px solid rgba(212,175,55,0.3)", borderRadius: 14, overflow: "auto", maxHeight: "calc(100vh - 130px)" }}>
        <table data-testid="supercarpeta-tabla" style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.72rem", color: "#e2e8f0", minWidth: 1450 }}>
          <thead>
            <tr style={{ background: "rgba(212,175,55,0.15)", color: "#D4AF37",
              textTransform: "uppercase", borderBottom: "1px solid rgba(212,175,55,0.6)" }}>
              <th style={{ ...th, left: 0, zIndex: 40, width: 46, minWidth: 46, maxWidth: 46, textAlign: "center", boxSizing: "border-box" }}>N°</th>
              <th style={{ ...th, left: 46, zIndex: 40, width: 240, minWidth: 240, maxWidth: 240, boxSizing: "border-box" }}>Cliente</th>
              <th style={{ ...th, left: 286, zIndex: 40 }}>RUT</th>
              <th style={th}>Inmobiliaria</th>
              <th style={th}>Proyecto</th>
              <th style={th}>Ciudad</th>
              <th style={th}>Notaría {gear("notaria")}</th>
              <th style={th}>Broker</th>
              <th style={{ ...th, textAlign: "right" }}>Monto UF</th>
              <th style={th}>Tasación {gear("tasacion")}</th>
              <th style={th}>Estudio de Títulos {gear("estudio")}</th>
              <th style={th}>Resolución Serviu {gear("serviu")}</th>
              <th style={th}>Carta Oferta {gear("carta_oferta")}</th>
              <th style={th}>Promesa CV {gear("promesa")}</th>
              <th style={th}>Cédula Crédito (SET) {gear("set_credito")}</th>
              <th style={th}>Carpeta Notaría {gear("carpeta_notaria")}</th>
              <th style={th}>Escritura {gear("escritura")}</th>
              <th style={{ ...th, color: "#f5d76e" }}>📅 Fecha Firma</th>
              <th style={th}>Avance</th>
              <th style={{ ...th, borderRight: "none" }}>Gestión</th>
            </tr>
          </thead>
          <tbody>
            {clientes.map((c, idx) => (
              <tr key={c.id} data-testid={`super-fila-${c.id}`}
                className={`super-row ${c.recien_24h ? "neon-verde" : ""}`}
                style={{ borderBottom: "1px solid rgba(255,255,255,0.3)", minHeight: 52,
                  background: idx % 2 === 0 ? "#1E2A3A" : "#253347" }}>
                <td data-testid={`super-numero-${c.id}`} title="Numeración correlativa (solo lectura — se recalcula automáticamente)"
                  style={{ ...celdaId, fontWeight: 900, color: "#D4AF37", fontSize: 14, textAlign: "center",
                    position: "sticky", left: 0, zIndex: 20, width: 46, minWidth: 46, maxWidth: 46,
                    boxSizing: "border-box", userSelect: "none",
                    background: idx % 2 === 0 ? "#17222F" : "#1C2839" }}>
                  {idx + 1}
                </td>
                <td style={{ ...celdaId, fontWeight: 800, color: "#FFFFFF", fontSize: 15,
                  position: "sticky", left: 46, zIndex: 20, width: 240, minWidth: 240, maxWidth: 240,
                  boxSizing: "border-box", overflowWrap: "break-word",
                  background: idx % 2 === 0 ? "#17222F" : "#1C2839" }}>
                  <i className="fa fa-folder folder-metal" style={{ marginRight: 6, fontSize: "0.85rem" }} />
                  {editable(c, "nombre", c.cliente, c.cliente)}
                  {(c.avance?.pct || 0) >= 100 && <span data-testid={`avance-100-${c.id}`}
                    title="100% — todas las etapas completadas, listo para escriturar" style={{ marginLeft: 4 }}>✅</span>}
                  {c.reactivacion && <span data-testid={`reactivacion-${c.id}`}
                    style={{ marginLeft: 8, background: "#E65100", color: "#fff", borderRadius: 999,
                      padding: "2px 10px", fontSize: 12, fontWeight: 900 }}>⚡ REACTIVACIÓN</span>}
                  {c.alerta_reparos && <span data-testid={`alerta-reparos-${c.id}`}
                    style={{ marginLeft: 8, background: "#5C1A1A", color: "#fff", borderRadius: 6,
                      padding: "2px 8px", fontSize: 11, fontWeight: 900 }}>🔴 REPAROS DETECTADOS SIN PROCESAR</span>}
                  {c.recien_24h && <span data-testid={`recien-${c.id}`} style={{ marginLeft: 6, color: "#22c55e", fontSize: "0.56rem", fontWeight: 800 }}>● NUEVO 24H</span>}
                  {c.arrastre && <span data-testid={`arrastre-${c.id}`}
                    title={`Cliente trasladado desde la proyección de ${nombreMes(c.arrastre)}`}
                    style={{ marginLeft: 6, background: "rgba(96,165,250,0.18)", border: "1px solid rgba(96,165,250,0.6)",
                      color: "#7DD3FC", borderRadius: 999, padding: "2px 8px", fontSize: 11, fontWeight: 800 }}>
                    ↪ Arrastre {nombreMes(c.arrastre)}</span>}
                  {(c.contacto?.email || c.contacto?.telefono) &&
                    <div style={{ color: "#64748b", fontSize: "0.55rem", fontWeight: 400 }}>
                      {c.contacto.email}{c.contacto.email && c.contacto.telefono ? " · " : ""}{c.contacto.telefono}</div>}
                </td>
                <td data-testid={`super-rut-${c.id}`} style={{ ...celdaId, fontFamily: "monospace", color: "#B0BEC5",
                  position: "sticky", left: 286, zIndex: 20, whiteSpace: "nowrap",
                  background: idx % 2 === 0 ? "#17222F" : "#1C2839" }}>
                  {editable(c, "rut", c.faltantes?.includes("rut")
                    ? <span data-testid={`rut-por-confirmar-${c.id}`}
                        style={{ background: "rgba(239,68,68,0.16)", border: "1px solid rgba(239,68,68,0.65)",
                          color: "#ef4444", borderRadius: 8, padding: "2px 8px", fontWeight: 800, fontSize: 12 }}>
                        🔴 RUT Por Confirmar</span>
                    : (c.rut || pendiente), c.rut)}
                </td>
                <td data-testid={`super-inmobiliaria-${c.id}`} style={{ ...celdaId, fontWeight: 700, color: "#B0BEC5" }}>
                  {editable(c, "inmobiliaria", c.inmobiliaria, c.inmobiliaria)}
                  {c.faltantes?.includes("inmobiliaria") && <div style={{ marginTop: 2 }}>{btnFaltante(c, "inmobiliaria")}</div>}
                </td>
                <td data-testid={`super-proyecto-${c.id}`} style={{ ...celdaId, color: "#90A4AE", maxWidth: 170 }}>
                  {editable(c, "proyecto", c.proyecto || btnFaltante(c, "proyecto"), c.proyecto)}
                </td>
                <td data-testid={`super-ciudad-${c.id}`} style={{ ...celdaId, color: "#78909C",
                  fontStyle: c.ciudad === "Por Confirmar" ? "italic" : "normal" }}>
                  {editable(c, "ciudad", c.ciudad, c.ciudad === "Por Confirmar" ? "" : c.ciudad)}
                  {c.faltantes?.includes("ciudad") && <div style={{ marginTop: 2 }}>{btnFaltante(c, "ciudad")}</div>}
                </td>
                <td data-testid={`super-notaria-${c.id}`} style={{ ...celdaId, color: "#78909C" }}>
                  {editable(c, "notaria", (
                    <button data-testid={`panel-notaria-${c.id}`} onClick={() => abrirPanel(c, "notaria")}
                      title="Panel de notaría: correos detectados de la notaría de este cliente"
                      style={{ cursor: "pointer", border: "none", background: "transparent", padding: 0,
                        color: c.notaria ? "#B0BEC5" : "#78909C", fontStyle: c.notaria ? "normal" : "italic",
                        fontWeight: c.notaria ? 700 : 400, fontSize: 14, textAlign: "left" }}>
                      {c.notaria || "Por Asignar"}
                    </button>
                  ), c.notaria)}
                  {c.alerta_notaria_ciudad && <div data-testid={`alerta-notaria-ciudad-${c.id}`}
                    style={{ color: "#facc15", fontSize: 11, fontWeight: 700, marginTop: 2 }}>
                    ⚠️ Notaría en ciudad distinta a la propiedad. Verificar.</div>}
                  <div style={{ marginTop: 2 }}>
                    <button data-testid={`manual-btn-notaria-${c.id}`}
                      onClick={() => setManualModal({ fid: c.id, cliente: c.cliente, campo: "notaria", valor: "" })}
                      title="Editar notaría manualmente (Gerencia)"
                      style={{ cursor: "pointer", border: "none", background: "transparent", padding: 0, fontSize: 12, opacity: 0.8 }}>✏️</button>
                  </div>
                </td>
                <td data-testid={`super-broker-${c.id}`} style={{ ...celdaId, color: "#B0BEC5", fontStyle: "italic" }}>
                  {editable(c, "broker", c.faltantes?.includes("broker") ? btnFaltante(c, "broker") : (c.broker || pendiente), c.broker)}
                </td>
                <td data-testid={`super-monto-${c.id}`} style={{ ...celdaId, textAlign: "right", fontWeight: 800, color: "#D4AF37",
                  whiteSpace: "nowrap" }}>
                  {editable(c, "monto", c.monto_uf
                    ? <>{Number(c.monto_uf).toLocaleString("es-CL")} <span style={{ color: "#B0BEC5", fontWeight: 400 }}>UF</span></>
                    : btnFaltante(c, "monto"), c.monto_uf)}
                  {c.subsidio && <div data-testid={`subsidio-${c.id}`} style={{ marginTop: 4, display: "inline-block",
                    background: c.subsidio.toLowerCase().startsWith("con") ? "#2E7D32" : "#37474F",
                    color: "#fff", fontWeight: c.subsidio.toLowerCase().startsWith("con") ? 800 : 500,
                    borderRadius: 999, padding: "2px 10px", fontSize: 12 }}>{c.subsidio}</div>}
                </td>
                {celdaEstado(c, "tasacion", c.estado_tasacion === "Pendiente" ? "" : c.estado_tasacion, { extra: <>
                    {c.bitacora?.tasacion?.demora_48h &&
                      <div style={{ color: "#fca5a5", fontWeight: 800, fontSize: "0.56rem" }}>🔴 {c.bitacora.tasacion.fecha_solicitud?.slice(0, 10)} · +48h sin respuesta</div>}
                    {c.informes?.tasacion?.disponible &&
                      <button data-testid={`ver-tasacion-${c.id}`} onClick={() => abrir(c.id, c.cliente, c.informes.tasacion)} style={btnPdf}>📄 Ver PDF</button>}
                  </> })}
                {celdaEstado(c, "estudio", c.estudio_titulos, { extra: <>
                    {c.detalle_reparos &&
                      <button data-testid={`super-legal-btn-${c.id}`} onClick={() => setReparoModal({ cliente: c.cliente, texto: c.detalle_reparos })}
                        style={{ display: "block", marginTop: 2, cursor: "pointer", background: "rgba(249,115,22,0.25)",
                          border: "1px solid rgba(249,115,22,0.6)", color: "#fdba74", borderRadius: 8,
                          padding: "0.15rem 0.5rem", fontSize: "0.56rem", fontWeight: 800 }}>⚠️ Ver Reparos</button>}
                    {c.informes?.estudio?.disponible &&
                      <button data-testid={`ver-estudio-${c.id}`} onClick={() => abrir(c.id, c.cliente, c.informes.estudio)} style={btnPdf}>📄 Ver PDF</button>}
                  </> })}
                {celdaEstado(c, "serviu", c.serviu, { naSinSubsidio: true })}
                {celdaEstado(c, "carta_oferta", c.carta_oferta, { extra: (<>
                  <div data-testid={`docs-co-rs-${c.id}`} title={c.docs_co_rs?.detalle || ""}
                    style={{ display: "flex", flexDirection: "column", gap: 1, marginTop: 2, cursor: "help" }}>
                    {(c.docs_co_rs?.documentos || []).map((d, di) => (
                      <span key={d.hito || di} data-testid={`doc-badge-${d.hito}-${c.id}`}
                        title={`${d.label}: ${d.estado}`}
                        style={{ fontSize: "0.54rem", fontWeight: 800, textAlign: "center",
                          color: { verde: "#4ade80", azul: "#93c5fd", amarillo: "#facc15", rojo: "#f87171" }[d.color] }}>
                        {d.icono} {d.label.length > 24 ? d.label.slice(0, 24) + "…" : d.label}
                      </span>
                    ))}
                    {c.docs_co_rs?.reenviado && <span style={{ fontSize: "0.52rem", color: "#4ade80", textAlign: "center", fontWeight: 800 }}>📤 Reenviado ✓</span>}
                  </div>
                  <button data-testid={`solicitar-co-rs-${c.id}`} onClick={() => abrirSolicitud(c)}
                    title={c.inmobiliaria === "Casa Usada"
                      ? "Pedir al vendedor directo los documentos que aplican (vista previa antes de enviar)"
                      : "Pedir a la inmobiliaria los documentos que aplican (vista previa antes de enviar, CC automática a Victoria y Daniela)"}
                    style={{ ...btnPdf, background: "rgba(96,165,250,0.15)", border: "1px solid rgba(96,165,250,0.6)",
                      color: "#60a5fa", width: "100%" }}>
                    📨 Pedir Documentos</button>
                </>) })}
                {celdaEstado(c, "promesa", c.promesa, { naSinSubsidio: true, extra: c.promesa_ia ? (
                  <div data-testid={`promesa-ia-${c.id}`}
                    title={`Análisis IA (${c.promesa_ia.fecha}): ${c.promesa_ia.evidencia}${c.promesa_ia.archivo ? ` · Archivo: ${c.promesa_ia.archivo}` : ""}`}
                    style={{ marginTop: 2, fontSize: "0.56rem", fontWeight: 800, textAlign: "center",
                      color: c.promesa_ia.firmado ? "#4ade80" : "#93c5fd", cursor: "help" }}>
                    🤖 {c.promesa_ia.firmado ? "Firma verificada por IA" : "IA: revisar firma manualmente"}
                  </div>) : null })}
                {celdaEstado(c, "set_credito", SET_LABEL[c.set_credito?.estado] || c.set_credito?.estado, { extra:
                    c.set_credito?.fecha ? <div style={{ color: "#cbd5e1", fontSize: "0.55rem" }}>{c.set_credito.fecha.slice(0, 10)}</div> : null })}
                {celdaEstado(c, "carpeta_notaria", c.carpeta_notaria, {})}
                {celdaEstado(c, "escritura", c.escritura, { extra:
                    c.informes?.borrador?.disponible ? <button data-testid={`ver-borrador-${c.id}`}
                      onClick={() => abrir(c.id, c.cliente, c.informes.borrador)} style={btnPdf}>📄 Borrador</button> : null })}
                <td data-testid={`super-fecha-firma-${c.id}`} style={{ ...celda, textAlign: "center", whiteSpace: "nowrap" }}>
                  {c.fecha_firma
                    ? <b style={{ color: "#FFD700", fontSize: 15, fontWeight: 900 }}>📅 {String(c.fecha_firma).slice(0, 10)}</b>
                    : pendiente}
                </td>
                <td data-testid={`super-avance-${c.id}`} style={{ ...celda, textAlign: "center", minWidth: 110 }}>
                  <div data-testid={`avance-bar-${c.id}`} onClick={() => setAvanceModal(c)} style={{ cursor: "pointer" }}
                    title="Clic: resumen de etapas completadas y faltantes">
                    <b style={{ fontSize: 15, color: (c.avance?.pct || 0) >= 100 ? "#FFD700" : "#f8fafc" }}>{c.avance?.pct ?? 0}%</b>
                    <div style={{ marginTop: 4, height: 8, background: "rgba(0,0,0,0.35)", borderRadius: 99, overflow: "hidden" }}>
                      <div style={{ width: `${Math.min(c.avance?.pct || 0, 100)}%`, height: "100%", borderRadius: 99,
                        background: colorAvance(c.avance?.pct || 0) }} />
                    </div>
                  </div>
                </td>
                <td data-testid={`super-gestion-${c.id}`} style={{ ...celda, borderRight: "none", whiteSpace: "nowrap", textAlign: "center" }}>
                  <button data-testid={`mover-mes-${c.id}`} onClick={() => moverMes(c)}
                    title={`Pasar a ${nombreMes(mesSiguiente(mes))} conservando todos sus datos y estados (nunca borra nada)`}
                    style={{ display: "block", width: "100%", cursor: "pointer", background: "rgba(96,165,250,0.12)",
                      border: "1px solid rgba(96,165,250,0.45)", color: "#7DD3FC", borderRadius: 8,
                      padding: "0.3rem 0.6rem", fontSize: "0.62rem", fontWeight: 800 }}>
                    ➡ Pasar a {nombreMes(mesSiguiente(mes)).split(" ")[0]}</button>
                  <button data-testid={`eliminar-cliente-${c.id}`} onClick={() => eliminarCliente(c)}
                    title="Eliminar de esta proyección mensual (la ficha ADN_CLIENTES_360 se conserva; queda en bitácora)"
                    style={{ display: "block", width: "100%", marginTop: 4, cursor: "pointer", background: "rgba(239,68,68,0.10)",
                      border: "1px solid rgba(239,68,68,0.4)", color: "#f87171", borderRadius: 8,
                      padding: "0.3rem 0.6rem", fontSize: "0.62rem", fontWeight: 800 }}>
                    🗑 Eliminar</button>
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr data-testid="fila-totales" style={{ background: "#D4AF37", color: "#1A1A1A" }}>
              <td colSpan={7} style={{ padding: "12px 16px", fontWeight: 900, fontSize: 14 }}>
                TOTAL PROYECCIÓN {nombreMes(mes).toUpperCase()} — {clientes.length} clientes
              </td>
              <td style={{ padding: "12px 16px", textAlign: "right", fontWeight: 900, fontSize: 14, whiteSpace: "nowrap" }}>
                {(proy?.suma_uf || 0).toLocaleString("es-CL")} / {(proy?.meta_uf || 0).toLocaleString("es-CL")} UF
              </td>
              <td colSpan={10} style={{ padding: "12px 16px", fontWeight: 900, fontSize: 14 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span>Avance: {proy?.avance_pct ?? 0}%</span>
                  <div style={{ flex: 1, maxWidth: 260, height: 8, background: "rgba(0,0,0,0.25)", borderRadius: 99, overflow: "hidden" }}>
                    <div style={{ width: `${Math.min(proy?.avance_pct || 0, 100)}%`, height: "100%", background: "#1A1A1A" }} />
                  </div>
                  <span>{proy?.alerta_diferencia ? `⚠️ Diferencia: ${proy.diferencia_uf?.toLocaleString("es-CL")} UF` : "✅ Cuadra con la meta"}</span>
                </div>
              </td>
            </tr>
          </tfoot>
        </table>
        {data && clientes.length === 0 && <p style={{ color: "#94a3b8", textAlign: "center", padding: "1.5rem" }}>Sin clientes {solo24 ? "con informes en las últimas 24h" : "en el mes corriente"}.</p>}
      </div>
      )}

      {cbrModal && (
        <div data-testid="cbr-modal" onClick={() => setCbrModal(null)} style={modalBg}>
          {!esAdminGeneral ? (
            <div onClick={e => e.stopPropagation()} style={modalBox}>
              <h4 data-testid="cbr-acceso-denegado" style={{ margin: 0, color: "#ef4444", fontSize: "0.9rem" }}>⛔ Acceso Denegado</h4>
              <p style={{ color: "#94a3b8", fontSize: "0.7rem", marginTop: 8 }}>
                El módulo de Comisiones y CBR es de uso exclusivo del Administrador General.</p>
              <button onClick={() => setCbrModal(null)} className="maserati-btn" style={{ marginTop: 14 }}>Cerrar</button>
            </div>
          ) : (
          <div onClick={e => e.stopPropagation()} style={{ ...modalBox, maxWidth: "min(96vw, 1500px)", maxHeight: "84vh", overflowY: "auto", overflowX: "auto" }}>
            <h4 style={{ margin: 0, color: "#d4af37", fontSize: "0.9rem" }}>💰 Costos CBR — correos de aprobaciones@centralmutuos.cl</h4>
            <p style={{ color: "#94a3b8", fontSize: "0.62rem", margin: "6px 0 0" }}>
              Busca ÚNICAMENTE los correos de aprobación (remitente aprobaciones@centralmutuos.cl), abre la simulación adjunta
              (2ª hoja, Gastos Operacionales) y extrae la fila "CBR (Inscripción Registro Propiedad + Hipoteca)".
              REGLA DE HIERRO: jamás se inventa un valor. El dato se guarda en la Bóveda ADN_CLIENTES_360 como <b>costo_CBR</b>.
              La comisión es de uso exclusivo de Gerencia.
            </p>
            {cbrModal.loading && <p style={{ color: "#94a3b8", fontSize: "0.7rem" }}>Consultando estado…</p>}
            {!cbrModal.loading && (<>
              <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", marginTop: 12 }}>
                <button data-testid="cbr-extraer-btn" onClick={lanzarCbr} disabled={cbrModal.estado === "en_proceso"}
                  className="maserati-btn" style={{ minHeight: 36 }}>
                  {cbrModal.estado === "en_proceso" ? "🔎 Buscando en correos…" : "🔎 Buscar y Extraer CBR"}</button>
                <button data-testid="cbr-excel-btn" onClick={descargarCbrExcel}
                  disabled={!(cbrModal.resultados || []).length}
                  className="maserati-btn" style={{ minHeight: 36, opacity: (cbrModal.resultados || []).length ? 1 : 0.5 }}>
                  📥 Descargar Excel</button>
                <span data-testid="cbr-estado" style={{ fontSize: "0.62rem", fontWeight: 800,
                  color: cbrModal.estado === "completado" ? "#4ade80"
                    : cbrModal.estado === "en_proceso" ? "#facc15"
                    : String(cbrModal.estado || "").startsWith("error") ? "#f87171" : "#94a3b8" }}>
                  Estado: {cbrModal.estado || "nunca ejecutado"}
                  {cbrModal.ultima ? ` · última: ${String(cbrModal.ultima).slice(0, 16).replace("T", " ")}` : ""}
                  {cbrModal.estado === "completado" ? ` · ${cbrModal.encontrados}/${cbrModal.total} encontrados · ${cbrModal.correos_revisados ?? 0} correos revisados` : ""}
                </span>
              </div>
              {cbrModal.valores_base && (
                <div data-testid="valores-base" style={{ marginTop: 8, padding: "0.45rem 0.7rem", borderRadius: 8,
                  background: "rgba(212,175,55,0.08)", border: "1px solid rgba(212,175,55,0.3)",
                  fontSize: "0.62rem", color: "#94a3b8", display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
                  <b style={{ color: "#d4af37" }}>⚙ Valores Base Operacionales</b>
                  {valorBaseSpan("tasacion", "Tasación")}
                  {valorBaseSpan("est_titulos", "Estudio de Títulos")}
                  <span style={{ fontSize: "0.56rem" }}>se precargan en clientes sin dato · los valores manuales no se tocan</span>
                </div>
              )}
              {(cbrModal.resultados || []).length > 0 && (
                <table data-testid="cbr-tabla" style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.64rem", marginTop: 12, color: "#e2e8f0" }}>
                  <thead>
                    <tr style={{ color: "#d4af37", textTransform: "uppercase", fontSize: "0.56rem", letterSpacing: 1 }}>
                      {["N°", "Cliente", "RUT", "Broker", "Proyecto", "Tipo", "Subsidio", "Monto UF", "Valor CBR", "Tasación", "Est. Títulos", "Total Pagado", "Comisión", "% Aplicado", "Moneda", "Fecha correo", "Estado"].map(h =>
                        <th key={h} style={{ textAlign: "left", padding: "6px 8px", borderBottom: "1px solid rgba(212,175,55,0.4)" }}>{h}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {cbrModal.resultados.map((r, i) => {
                      const tp = totalPagadoFila(r);
                      const editandoTP = cbrEdit && (cbrEdit.fila.fid ? cbrEdit.fila.fid === r.fid : cbrEdit.fila.cliente === r.cliente) && cbrEdit.campo === "total_pagado";
                      return (
                        <tr key={r.fid || i} data-testid={`cbr-fila-${i}`} style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
                          <td data-testid={`cbr-numero-${i}`} style={{ padding: "6px 8px", color: "#d4af37", fontWeight: 900, textAlign: "center", userSelect: "none" }}>{i + 1}</td>
                          {celdaCbrEdit(r, i, "cliente", { texto: true, color: "#f8fafc", estilo: { whiteSpace: "normal", minWidth: 130 } })}
                          {celdaCbrEdit(r, i, "rut", { texto: true, suave: true, color: "#94a3b8" })}
                          {celdaCbrEdit(r, i, "broker", { texto: true, suave: true, color: "#94a3b8" })}
                          {celdaCbrEdit(r, i, "proyecto", { texto: true, suave: true, color: "#94a3b8", estilo: { maxWidth: 120, overflow: "hidden", textOverflow: "ellipsis" } })}
                          {celdaCbrEdit(r, i, "tipo_propiedad", { texto: true, suave: true, color: "#94a3b8" })}
                          {celdaCbrEdit(r, i, "subsidio", { texto: true, suave: true, color: "#94a3b8" })}
                          {celdaCbrEdit(r, i, "monto_credito", {})}
                          {celdaCbrEdit(r, i, "valor_cbr", {})}
                          {celdaCbrEdit(r, i, "tasacion", {})}
                          {celdaCbrEdit(r, i, "est_titulos", {})}
                          <td data-testid={`cbr-total_pagado-${i}`}
                            title={tp.manual ? "Sobreescrito manualmente — deja de recalcularse (doble clic para editar)"
                              : tp.incompleto ? "Total incompleto (⚠): falta CBR, Tasación o Estudio. Doble clic para sobreescribir"
                              : "CBR + Tasación + Estudio de Títulos. Doble clic para sobreescribir"}
                            onDoubleClick={() => setCbrEdit({ fila: r, campo: "total_pagado", valor: r.total_pagado ?? (tp.hay ? tp.tot : "") })}
                            style={{ padding: "6px 8px", fontWeight: 900, whiteSpace: "nowrap", cursor: "cell",
                              color: tp.manual ? "#93c5fd" : "#d4af37",
                              background: tp.manual ? "rgba(59,130,246,0.14)" : "rgba(148,163,184,0.08)" }}>
                            {editandoTP ? (
                              <input data-testid={`cbr-total_pagado-input-${i}`} autoFocus value={cbrEdit.valor}
                                onChange={e => setCbrEdit({ ...cbrEdit, valor: e.target.value })}
                                onBlur={guardarCbrManual}
                                onKeyDown={e => { if (e.key === "Enter") guardarCbrManual(); if (e.key === "Escape") setCbrEdit(null); }}
                                style={{ width: 64, background: "#0f172a", color: "#e2e8f0", border: "1px solid #3b82f6", borderRadius: 4, padding: "2px 4px", fontSize: "0.64rem" }} />
                            ) : (<>
                              {tp.hay ? Number(tp.tot).toLocaleString("es-CL") : "—"}
                              {tp.hay && tp.incompleto && <span style={{ color: "#facc15", marginLeft: 4 }}>⚠</span>}
                            </>)}</td>
                          {celdaCbrEdit(r, i, "comision", { sufijo: " UF" })}
                          {celdaCbrEdit(r, i, "pct_aplicado", { texto: true, suave: true,
                            color: String(r.pct_aplicado || "").includes("REVISAR") ? "#facc15" : "#e2e8f0",
                            estilo: { fontSize: "0.58rem" } })}
                          {celdaCbrEdit(r, i, "moneda", { texto: true, suave: true })}
                          <td style={{ padding: "6px 8px", whiteSpace: "nowrap" }}>{r.fecha_correo}</td>
                          {celdaCbrEdit(r, i, "estado", { texto: true,
                            color: r.estado === "ENCONTRADO" ? "#4ade80" : "#f87171" })}
                        </tr>
                      );
                    })}
                    {/* TOTALES DOBLE MONEDA — fijos al final, UF nunca se mezcla con CLP */}
                    <tr data-testid="cbr-totales-uf">
                      {[
                        "TOTAL EN UF", "", "", "", "", "", "",
                        Number(cbrModal.total_cbr_uf || 0).toLocaleString("es-CL"),
                        Number(cbrModal.total_tasacion_uf || 0).toLocaleString("es-CL"),
                        Number(cbrModal.total_titulos_uf || 0).toLocaleString("es-CL"),
                        Number(cbrModal.gran_total_uf || 0).toLocaleString("es-CL"),
                        Number(cbrModal.total_comision_uf || 0).toLocaleString("es-CL"),
                        "", "UF", "", "solo filas con dato",
                      ].map((v, j) => (
                        <td key={j} data-testid={j === 7 ? "cbr-total-cbr-uf" : j === 10 ? "cbr-gran-total-uf" : j === 11 ? "cbr-total-comision-uf" : undefined}
                          style={{ position: "sticky", bottom: 31, background: "#1e3a8a", color: "#ffffff",
                            fontWeight: j === 15 ? 400 : 900, fontSize: j === 15 ? "0.54rem" : undefined,
                            padding: "7px 8px", whiteSpace: "nowrap", zIndex: 2 }}>{v}</td>
                      ))}
                    </tr>
                    <tr data-testid="cbr-totales-clp">
                      {[
                        "TOTAL EN PESOS", "", "", "", "", "", "",
                        Number(cbrModal.total_cbr_clp || 0).toLocaleString("es-CL"),
                        Number(cbrModal.total_tasacion_clp || 0).toLocaleString("es-CL"),
                        Number(cbrModal.total_titulos_clp || 0).toLocaleString("es-CL"),
                        Number(cbrModal.gran_total_clp || 0).toLocaleString("es-CL"),
                        Number(cbrModal.total_comision_clp || 0).toLocaleString("es-CL"),
                        "", "CLP", "", "sin conversión entre monedas",
                      ].map((v, j) => (
                        <td key={j} data-testid={j === 7 ? "cbr-total-cbr-clp" : j === 10 ? "cbr-gran-total-clp" : j === 11 ? "cbr-total-comision-clp" : undefined}
                          style={{ position: "sticky", bottom: 0, background: "#14532d", color: "#ffffff",
                            fontWeight: j === 15 ? 400 : 900, fontSize: j === 15 ? "0.54rem" : undefined,
                            padding: "7px 8px", whiteSpace: "nowrap", zIndex: 2 }}>{v}</td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              )}
            </>)}
            <button data-testid="cbr-cerrar" onClick={() => setCbrModal(null)} className="maserati-btn" style={{ marginTop: 14 }}>Cerrar</button>
          </div>
          )}
        </div>
      )}

      {inmoModal && (
        <div data-testid="inmobiliarias-modal" onClick={() => setInmoModal(null)} style={modalBg}>
          <div onClick={e => e.stopPropagation()} style={{ ...modalBox, maxWidth: 940, maxHeight: "86vh", overflowY: "auto" }}>
            <h4 style={{ margin: 0, color: "#d4af37", fontSize: "0.9rem" }}>🏢 Panel de Fuentes — Inmobiliarias · Brokers · Fuentes Individuales</h4>
            <p style={{ color: "#94a3b8", fontSize: "0.62rem", margin: "6px 0 0" }}>
              Orden de búsqueda del destinatario: <b>1)</b> fuente individual del cliente · <b>2)</b> proyecto dentro de la
              inmobiliaria · <b>3)</b> contacto general de la inmobiliaria · <b>4)</b> broker. Nada se elimina: solo se desactiva.
            </p>
            {inmoModal.loading ? <p style={{ color: "#94a3b8", fontSize: "0.7rem" }}>Cargando…</p> : (<>
              <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
                <button data-testid="reg-nueva-inmobiliaria" className="maserati-btn" style={{ minHeight: 30, fontSize: "0.6rem" }}
                  onClick={() => setInmoModal(m => ({ ...m, reg: { tipo: "inmobiliaria", nombre: "", email_general: "", tieneProyectos: true, proyectos: [regProyectoVacio()] } }))}>
                  ➕ Registrar nueva inmobiliaria</button>
                <button data-testid="reg-nuevo-broker" className="maserati-btn" style={{ minHeight: 30, fontSize: "0.6rem" }}
                  onClick={() => setInmoModal(m => ({ ...m, reg: { tipo: "broker", nombre: "", tipo_broker: "word_consultor", email: "", tasacion_nombre: "", tasacion_email: "", estudio_nombre: "", estudio_email: "", carta_nombre: "", carta_email: "" } }))}>
                  ➕ Registrar nuevo broker</button>
              </div>

              {inmoModal.reg && (
                <div data-testid="registro-fuente" style={{ marginTop: 10, padding: "0.8rem", background: "rgba(212,175,55,0.06)",
                  border: "1px solid rgba(212,175,55,0.4)", borderRadius: 10 }}>
                  <b style={{ color: "#d4af37", fontSize: "0.72rem" }}>
                    📝 Registro completo — {inmoModal.reg.tipo === "broker" ? "Broker" : "Inmobiliaria"} (todos los contactos para operar)</b>
                  <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
                    <input data-testid="reg-nombre" placeholder={inmoModal.reg.tipo === "broker" ? "Nombre del broker" : "Nombre de la inmobiliaria"}
                      value={inmoModal.reg.nombre}
                      onChange={e => setInmoModal(m => ({ ...m, reg: { ...m.reg, nombre: e.target.value } }))}
                      style={{ ...inputStyle, marginTop: 0, flex: 1, minWidth: 180 }} />
                    {inmoModal.reg.tipo === "broker" ? (
                      <select data-testid="reg-tipo-broker" value={inmoModal.reg.tipo_broker}
                        onChange={e => setInmoModal(m => ({ ...m, reg: { ...m.reg, tipo_broker: e.target.value, tipo: "broker" } }))}
                        style={{ ...inputStyle, marginTop: 0, width: 170 }}>
                        <option value="word_consultor">Word Consultor</option>
                        <option value="autocorredor">Autocorredor</option>
                      </select>
                    ) : (
                      <input data-testid="reg-email-general" placeholder="Correo general de la inmobiliaria"
                        value={inmoModal.reg.email_general || ""}
                        onChange={e => setInmoModal(m => ({ ...m, reg: { ...m.reg, email_general: e.target.value } }))}
                        style={{ ...inputStyle, marginTop: 0, flex: 1, minWidth: 200 }} />
                    )}
                  </div>
                  {inmoModal.reg.tipo === "broker" ? (
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 8, marginTop: 8 }}>
                      <input placeholder="Correo del broker" value={inmoModal.reg.email || ""}
                        onChange={e => setInmoModal(m => ({ ...m, reg: { ...m.reg, email: e.target.value } }))} style={{ ...inputStyle, marginTop: 0 }} />
                      {[["tasacion", "Tasación"], ["estudio", "Estudio de Títulos"], ["carta", "Carta Oferta / RS"]].map(([k, lb]) => (
                        <div key={k} style={{ display: "grid", gap: 6 }}>
                          <input placeholder={`Contacto ${lb} — nombre`} value={inmoModal.reg[`${k}_nombre`] || ""}
                            onChange={e => setInmoModal(m => ({ ...m, reg: { ...m.reg, [`${k}_nombre`]: e.target.value } }))} style={{ ...inputStyle, marginTop: 0 }} />
                          <input placeholder={`Contacto ${lb} — correo`} value={inmoModal.reg[`${k}_email`] || ""}
                            onChange={e => setInmoModal(m => ({ ...m, reg: { ...m.reg, [`${k}_email`]: e.target.value } }))} style={{ ...inputStyle, marginTop: 0 }} />
                        </div>
                      ))}
                    </div>
                  ) : (<>
                    <label style={{ color: "#cbd5e1", fontSize: "0.62rem", display: "block", marginTop: 8 }}>
                      ¿Tiene proyectos específicos?{" "}
                      <button data-testid="reg-tiene-proyectos" className="maserati-btn" style={{ minHeight: 24, fontSize: "0.56rem", marginLeft: 6 }}
                        onClick={() => setInmoModal(m => ({ ...m, reg: { ...m.reg, tieneProyectos: !m.reg.tieneProyectos } }))}>
                        {inmoModal.reg.tieneProyectos ? "Sí — por proyecto" : "No — contacto general único"}</button>
                    </label>
                    {(inmoModal.reg.proyectos || []).map((p, pi) => (
                      <div key={pi} style={{ marginTop: 8, padding: "0.6rem", background: "rgba(255,255,255,0.03)", borderRadius: 8, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 6 }}>
                        {inmoModal.reg.tieneProyectos &&
                          <input placeholder="Nombre del proyecto" value={p.proyecto}
                            onChange={e => setInmoModal(m => ({ ...m, reg: { ...m.reg, proyectos: m.reg.proyectos.map((x, j) => j === pi ? { ...x, proyecto: e.target.value } : x) } }))}
                            style={{ ...inputStyle, marginTop: 0, gridColumn: "1 / -1" }} />}
                        {[["contacto", "email", "Carta Oferta / RS"], ["tasacion_nombre", "tasacion_email", "Tasación"], ["estudio_nombre", "estudio_email", "Estudio de Títulos"]].map(([kn, ke, lb]) => (
                          <div key={kn} style={{ display: "grid", gap: 6 }}>
                            <input placeholder={`${lb} — nombre`} value={p[kn] || ""}
                              onChange={e => setInmoModal(m => ({ ...m, reg: { ...m.reg, proyectos: m.reg.proyectos.map((x, j) => j === pi ? { ...x, [kn]: e.target.value } : x) } }))}
                              style={{ ...inputStyle, marginTop: 0 }} />
                            <input placeholder={`${lb} — correo`} value={p[ke] || ""}
                              onChange={e => setInmoModal(m => ({ ...m, reg: { ...m.reg, proyectos: m.reg.proyectos.map((x, j) => j === pi ? { ...x, [ke]: e.target.value } : x) } }))}
                              style={{ ...inputStyle, marginTop: 0 }} />
                          </div>
                        ))}
                      </div>
                    ))}
                    {inmoModal.reg.tieneProyectos &&
                      <button className="maserati-btn" style={{ minHeight: 26, fontSize: "0.56rem", marginTop: 6 }}
                        onClick={() => setInmoModal(m => ({ ...m, reg: { ...m.reg, proyectos: [...m.reg.proyectos, regProyectoVacio()] } }))}>
                        ➕ Agregar otro proyecto</button>}
                  </>)}
                  <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                    <button data-testid="reg-guardar" className="maserati-btn" style={{ minHeight: 30 }} onClick={guardarRegistro}>💾 Registrar origen completo</button>
                    <button className="maserati-btn" style={{ minHeight: 30, opacity: 0.6 }}
                      onClick={() => setInmoModal(m => ({ ...m, reg: null }))}>Cancelar</button>
                  </div>
                </div>
              )}

              <h4 style={{ margin: "16px 0 0", color: "#d4af37", fontSize: "0.78rem" }}>1️⃣ Fuentes por Inmobiliaria (vivienda nueva)</h4>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.62rem", marginTop: 6, color: "#e2e8f0" }}>
                <tbody>
                  {(inmoModal.generales || []).map((g, i) => (
                    <tr key={g.inmobiliaria || i} data-testid={`general-fila-${i}`} style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
                      <td style={{ padding: "3px 6px", fontWeight: 800, color: "#f8fafc", width: 200 }}>{g.inmobiliaria}</td>
                      <td style={{ padding: "3px 6px", color: "#94a3b8" }}>Correo general:</td>
                      <td style={{ padding: "3px 6px" }}>
                        <input data-testid={`general-email-${i}`} value={g.email || ""} placeholder="correo general (opcional)"
                          onChange={e => editarGeneral(i, e.target.value)}
                          style={{ ...inputStyle, marginTop: 0, padding: "0.3rem 0.5rem", fontSize: "0.6rem" }} /></td>
                      <td style={{ padding: "3px 6px" }}>
                        <button data-testid={`general-guardar-${i}`} onClick={() => guardarGeneral(g)}
                          className="maserati-btn" style={{ minHeight: 26, fontSize: "0.56rem" }}>💾</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.64rem", marginTop: 10, color: "#e2e8f0" }}>
                <thead>
                  <tr style={{ color: "#d4af37", textTransform: "uppercase", fontSize: "0.56rem", letterSpacing: 1 }}>
                    {["Inmobiliaria / Corredor", "Proyecto (vacío = general)", "Contacto CO/RS", "Correo CO/RS", "⚙", "Activo", ""].map((h, j) =>
                      <th key={j} style={{ textAlign: "left", padding: "6px 8px", borderBottom: "1px solid rgba(212,175,55,0.4)" }}>{h}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {(inmoModal.contactos || []).map((c, i) => (<React.Fragment key={c.id}>
                    <tr data-testid={`contacto-fila-${i}`} style={{ borderBottom: "1px solid rgba(255,255,255,0.08)", opacity: c.activo === false ? 0.45 : 1 }}>
                      {["inmobiliaria", "proyecto", "contacto", "email"].map(campo => (
                        <td key={campo} style={{ padding: "4px 6px" }}>
                          <input data-testid={`contacto-${campo}-${i}`} value={c[campo] || ""}
                            onChange={e => editarContacto(i, campo, e.target.value)}
                            placeholder={campo === "proyecto" ? "(general)" : campo}
                            style={{ ...inputStyle, marginTop: 0, padding: "0.32rem 0.5rem", fontSize: "0.62rem" }} /></td>
                      ))}
                      <td style={{ padding: "4px 6px", textAlign: "center" }}>
                        <button data-testid={`contacto-exp-${i}`} title="Contactos de Tasación y Estudio de Títulos de este proyecto"
                          onClick={() => setInmoModal(m => ({ ...m, exp: { ...m.exp, [c.id]: !m.exp?.[c.id] } }))}
                          style={{ background: "none", border: "none", cursor: "pointer", fontSize: "0.85rem",
                            color: (c.tasacion_email || c.estudio_email) ? "#4ade80" : "#94a3b8" }}>⚙️</button></td>
                      <td style={{ padding: "4px 6px", textAlign: "center" }}>
                        <button data-testid={`contacto-activo-${i}`}
                          onClick={() => guardarContacto({ ...c, activo: c.activo === false })}
                          title={c.activo === false ? "Reactivar" : "Desactivar (no se elimina)"}
                          style={{ background: "none", border: "none", cursor: "pointer", fontSize: "0.9rem" }}>
                          {c.activo === false ? "🚫" : "🟢"}</button></td>
                      <td style={{ padding: "4px 6px" }}>
                        <button data-testid={`contacto-guardar-${i}`} onClick={() => guardarContacto(c)}
                          className="maserati-btn" style={{ minHeight: 28, fontSize: "0.58rem" }}>💾</button></td>
                    </tr>
                    {inmoModal.exp?.[c.id] && (
                      <tr data-testid={`contacto-exp-fila-${i}`} style={{ background: "rgba(212,175,55,0.04)" }}>
                        <td colSpan={7} style={{ padding: "6px 10px" }}>
                          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 6 }}>
                            {[["tasacion_nombre", "Tasación — nombre"], ["tasacion_email", "Tasación — correo"],
                              ["estudio_nombre", "Est. Títulos — nombre"], ["estudio_email", "Est. Títulos — correo"]].map(([k, ph]) => (
                              <input key={k} data-testid={`contacto-${k}-${i}`} value={c[k] || ""} placeholder={ph}
                                onChange={e => editarContacto(i, k, e.target.value)}
                                style={{ ...inputStyle, marginTop: 0, padding: "0.3rem 0.5rem", fontSize: "0.6rem" }} />
                            ))}
                            <button onClick={() => guardarContacto(c)} className="maserati-btn" style={{ minHeight: 28, fontSize: "0.56rem" }}>💾 Guardar contactos del proyecto</button>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>))}
                  <tr data-testid="contacto-nuevo">
                    {["inmobiliaria", "proyecto", "contacto", "email"].map(campo => (
                      <td key={campo} style={{ padding: "4px 6px" }}>
                        <input data-testid={`contacto-nuevo-${campo}`} value={inmoModal.nuevo?.[campo] || ""}
                          placeholder={campo === "inmobiliaria" ? "Nueva inmobiliaria/corredor" : campo === "proyecto" ? "(general)" : campo}
                          onChange={e => setInmoModal(m => ({ ...m, nuevo: { ...m.nuevo, [campo]: e.target.value } }))}
                          style={{ ...inputStyle, marginTop: 0, padding: "0.32rem 0.5rem", fontSize: "0.62rem" }} /></td>
                    ))}
                    <td colSpan={3} style={{ padding: "4px 6px" }}>
                      <button data-testid="contacto-nuevo-guardar"
                        onClick={() => inmoModal.nuevo?.inmobiliaria && guardarContacto(inmoModal.nuevo)}
                        className="maserati-btn" style={{ minHeight: 28, fontSize: "0.58rem" }}>➕ Agregar proyecto</button></td>
                  </tr>
                </tbody>
              </table>

              <h4 style={{ margin: "18px 0 0", color: "#d4af37", fontSize: "0.78rem" }}>2️⃣ Fuentes por Broker (vivienda nueva vía broker)</h4>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.64rem", marginTop: 8, color: "#e2e8f0" }}>
                <thead>
                  <tr style={{ color: "#d4af37", textTransform: "uppercase", fontSize: "0.56rem", letterSpacing: 1 }}>
                    {["Broker", "Tipo", "Correo", "⚙", "Activo", ""].map((h, j) =>
                      <th key={j} style={{ textAlign: "left", padding: "6px 8px", borderBottom: "1px solid rgba(212,175,55,0.4)" }}>{h}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {(inmoModal.brokers || []).map((b, i) => (<React.Fragment key={b.id}>
                    <tr data-testid={`broker-fila-${i}`} style={{ borderBottom: "1px solid rgba(255,255,255,0.08)", opacity: b.activo === false ? 0.45 : 1 }}>
                      <td style={{ padding: "4px 6px" }}>
                        <input data-testid={`broker-nombre-${i}`} value={b.nombre || ""}
                          onChange={e => editarBroker(i, "nombre", e.target.value)}
                          style={{ ...inputStyle, marginTop: 0, padding: "0.32rem 0.5rem", fontSize: "0.62rem" }} /></td>
                      <td style={{ padding: "4px 6px" }}>
                        <select data-testid={`broker-tipo-${i}`} value={b.tipo || "word_consultor"}
                          onChange={e => editarBroker(i, "tipo", e.target.value)}
                          style={{ ...inputStyle, marginTop: 0, padding: "0.32rem 0.5rem", fontSize: "0.62rem" }}>
                          <option value="word_consultor">Word Consultor</option>
                          <option value="autocorredor">Autocorredor</option>
                        </select></td>
                      <td style={{ padding: "4px 6px" }}>
                        <input data-testid={`broker-email-${i}`} value={b.email || ""} placeholder="correo del broker"
                          onChange={e => editarBroker(i, "email", e.target.value)}
                          style={{ ...inputStyle, marginTop: 0, padding: "0.32rem 0.5rem", fontSize: "0.62rem" }} /></td>
                      <td style={{ padding: "4px 6px", textAlign: "center" }}>
                        <button title="Contactos de Tasación, Estudio y Carta Oferta/RS del broker"
                          onClick={() => setInmoModal(m => ({ ...m, exp: { ...m.exp, [b.id]: !m.exp?.[b.id] } }))}
                          style={{ background: "none", border: "none", cursor: "pointer", fontSize: "0.85rem",
                            color: (b.tasacion_email || b.estudio_email || b.carta_email) ? "#4ade80" : "#94a3b8" }}>⚙️</button></td>
                      <td style={{ padding: "4px 6px", textAlign: "center" }}>
                        <button onClick={() => guardarBroker({ ...b, activo: b.activo === false })}
                          style={{ background: "none", border: "none", cursor: "pointer", fontSize: "0.9rem" }}>
                          {b.activo === false ? "🚫" : "🟢"}</button></td>
                      <td style={{ padding: "4px 6px" }}>
                        <button data-testid={`broker-guardar-${i}`} onClick={() => guardarBroker(b)}
                          className="maserati-btn" style={{ minHeight: 28, fontSize: "0.58rem" }}>💾</button></td>
                    </tr>
                    {inmoModal.exp?.[b.id] && (
                      <tr style={{ background: "rgba(212,175,55,0.04)" }}>
                        <td colSpan={6} style={{ padding: "6px 10px" }}>
                          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 6 }}>
                            {[["tasacion_nombre", "Tasación — nombre"], ["tasacion_email", "Tasación — correo"],
                              ["estudio_nombre", "Est. Títulos — nombre"], ["estudio_email", "Est. Títulos — correo"],
                              ["carta_nombre", "Carta Oferta/RS — nombre"], ["carta_email", "Carta Oferta/RS — correo"]].map(([k, ph]) => (
                              <input key={k} value={b[k] || ""} placeholder={ph}
                                onChange={e => editarBroker(i, k, e.target.value)}
                                style={{ ...inputStyle, marginTop: 0, padding: "0.3rem 0.5rem", fontSize: "0.6rem" }} />
                            ))}
                            <button onClick={() => guardarBroker(b)} className="maserati-btn" style={{ minHeight: 28, fontSize: "0.56rem" }}>💾 Guardar contactos del broker</button>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>))}
                </tbody>
              </table>

              <h4 style={{ margin: "18px 0 0", color: "#d4af37", fontSize: "0.78rem" }}>3️⃣ Fuentes Individuales — Vivienda Usada (vendedor directo por cliente)</h4>
              <p style={{ color: "#94a3b8", fontSize: "0.6rem", margin: "4px 0 0" }}>
                Los documentos que aplican se muestran automáticamente según el tipo:
                usada <b>con</b> subsidio → Compromiso de Compraventa + Certificado de Subsidio ·
                usada <b>sin</b> subsidio → Compromiso de Compraventa <b>O</b> Carta Pie (elige el ejecutivo).</p>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.64rem", marginTop: 8, color: "#e2e8f0" }}>
                <thead>
                  <tr style={{ color: "#d4af37", textTransform: "uppercase", fontSize: "0.56rem", letterSpacing: 1 }}>
                    {["Cliente (usada)", "Tipo / Documentos que aplican", "Vendedor", "Correo del vendedor", "Activo", ""].map((h, j) =>
                      <th key={j} style={{ textAlign: "left", padding: "6px 8px", borderBottom: "1px solid rgba(212,175,55,0.4)" }}>{h}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {(inmoModal.vendedores || []).length === 0 && (
                    <tr><td colSpan={6} style={{ padding: "8px", color: "#94a3b8", fontStyle: "italic" }}>Sin clientes de vivienda usada en la vista.</td></tr>
                  )}
                  {(inmoModal.vendedores || []).map((v, i) => (
                    <tr key={v.fid} data-testid={`vendedor-fila-${i}`} style={{ borderBottom: "1px solid rgba(255,255,255,0.08)", opacity: v.activo === false ? 0.45 : 1 }}>
                      <td style={{ padding: "4px 6px", color: "#f8fafc", fontWeight: 700 }}>
                        {v.cliente}
                        {!v.configurado && <div style={{ color: "#facc15", fontSize: "0.54rem", fontWeight: 800 }}>⚠️ Sin vendedor configurado</div>}
                      </td>
                      <td style={{ padding: "4px 6px" }}>
                        <span style={{ fontSize: "0.54rem", fontWeight: 800, padding: "1px 6px", borderRadius: 6,
                          background: v.tipo_propiedad === "usada_con_subsidio" ? "rgba(74,222,128,0.15)" : "rgba(148,163,184,0.15)",
                          color: v.tipo_propiedad === "usada_con_subsidio" ? "#4ade80" : "#cbd5e1" }}>
                          {v.tipo_propiedad === "usada_con_subsidio" ? "USADA CON SUBSIDIO" : "USADA SIN SUBSIDIO"}</span>
                        <div style={{ color: "#94a3b8", fontSize: "0.54rem", marginTop: 2 }}>{(v.docs || []).join(" + ")}</div>
                      </td>
                      {["vendedor", "email"].map(campo => (
                        <td key={campo} style={{ padding: "4px 6px" }}>
                          <input data-testid={`vendedor-${campo}-${i}`} value={v[campo] || ""}
                            onChange={e => editarVendedor(i, campo, e.target.value)}
                            placeholder={campo === "email" ? "vendedor@correo.cl" : "Nombre del vendedor"}
                            style={{ ...inputStyle, marginTop: 0, padding: "0.32rem 0.5rem", fontSize: "0.62rem" }} /></td>
                      ))}
                      <td style={{ padding: "4px 6px", textAlign: "center" }}>
                        <button data-testid={`vendedor-activo-${i}`}
                          onClick={() => guardarVendedor({ ...v, activo: v.activo === false })}
                          title={v.activo === false ? "Reactivar" : "Desactivar (no se elimina)"}
                          style={{ background: "none", border: "none", cursor: "pointer", fontSize: "0.9rem" }}>
                          {v.activo === false ? "🚫" : "🟢"}</button></td>
                      <td style={{ padding: "4px 6px" }}>
                        <button data-testid={`vendedor-guardar-${i}`} onClick={() => guardarVendedor(v)}
                          className="maserati-btn" style={{ minHeight: 28, fontSize: "0.58rem" }}>💾</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <h4 style={{ margin: "18px 0 0", color: "#d4af37", fontSize: "0.78rem" }}>📋 Destinatarios Globales — CC obligatoria en todos los envíos</h4>
              <p style={{ color: "#94a3b8", fontSize: "0.6rem", margin: "4px 0 0" }}>
                Van con copia en cada correo del sistema. No se eliminan: solo se desactivan.</p>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.64rem", marginTop: 8, color: "#e2e8f0" }}>
                <tbody>
                  {(inmoModal.cc || []).map((x, i) => (
                    <tr key={i} data-testid={`cc-fila-${i}`} style={{ borderBottom: "1px solid rgba(255,255,255,0.08)", opacity: x.activo === false ? 0.45 : 1 }}>
                      <td style={{ padding: "4px 6px" }}>
                        <input data-testid={`cc-nombre-${i}`} value={x.nombre || ""}
                          onChange={e => editarCc(i, "nombre", e.target.value)}
                          style={{ ...inputStyle, marginTop: 0, padding: "0.32rem 0.5rem", fontSize: "0.62rem" }} /></td>
                      <td style={{ padding: "4px 6px" }}>
                        <input data-testid={`cc-email-${i}`} value={x.email || ""}
                          onChange={e => editarCc(i, "email", e.target.value)}
                          style={{ ...inputStyle, marginTop: 0, padding: "0.32rem 0.5rem", fontSize: "0.62rem" }} /></td>
                      <td style={{ padding: "4px 6px", textAlign: "center" }}>
                        <button data-testid={`cc-activo-${i}`}
                          onClick={() => guardarCc({ ...x, activo: x.activo === false })}
                          title={x.activo === false ? "Reactivar" : "Desactivar (no se elimina)"}
                          style={{ background: "none", border: "none", cursor: "pointer", fontSize: "0.9rem" }}>
                          {x.activo === false ? "🚫" : "🟢"}</button></td>
                      <td style={{ padding: "4px 6px" }}>
                        <button data-testid={`cc-guardar-${i}`} onClick={() => guardarCc(x)}
                          className="maserati-btn" style={{ minHeight: 28, fontSize: "0.58rem" }}>💾</button></td>
                    </tr>
                  ))}
                  <tr data-testid="cc-nuevo">
                    <td style={{ padding: "4px 6px" }}>
                      <input data-testid="cc-nuevo-nombre" value={inmoModal.nuevoCc?.nombre || ""} placeholder="Nuevo destinatario"
                        onChange={e => setInmoModal(m => ({ ...m, nuevoCc: { ...m.nuevoCc, nombre: e.target.value } }))}
                        style={{ ...inputStyle, marginTop: 0, padding: "0.32rem 0.5rem", fontSize: "0.62rem" }} /></td>
                    <td style={{ padding: "4px 6px" }}>
                      <input data-testid="cc-nuevo-email" value={inmoModal.nuevoCc?.email || ""} placeholder="correo@…"
                        onChange={e => setInmoModal(m => ({ ...m, nuevoCc: { ...m.nuevoCc, email: e.target.value } }))}
                        style={{ ...inputStyle, marginTop: 0, padding: "0.32rem 0.5rem", fontSize: "0.62rem" }} /></td>
                    <td colSpan={2} style={{ padding: "4px 6px" }}>
                      <button data-testid="cc-nuevo-guardar"
                        onClick={() => inmoModal.nuevoCc?.nombre && guardarCc(inmoModal.nuevoCc)}
                        className="maserati-btn" style={{ minHeight: 28, fontSize: "0.58rem" }}>➕ Agregar</button></td>
                  </tr>
                </tbody>
              </table>
            </>)}
            <button data-testid="inmo-cerrar" onClick={() => setInmoModal(null)} className="maserati-btn" style={{ marginTop: 14 }}>Cerrar</button>
          </div>
        </div>
      )}

      {solicitudModal && (
        <div data-testid="solicitud-modal" style={{ ...modalBg }}>
          <div onClick={e => e.stopPropagation()} style={{ ...modalBox, maxWidth: "min(94vw, 1050px)", width: "min(94vw, 1050px)",
            minHeight: "70vh", maxHeight: "92vh", overflowY: "auto", fontSize: "1rem" }}>
            <h4 data-testid="solicitud-titulo" style={{ margin: 0, color: "#d4af37", fontSize: "1.05rem" }}>
              📨 Confirmar envío de {(solicitudModal.docs_solicitados || []).join(" + ") || "documentos"} para {solicitudModal.cliente || ""}</h4>
            {solicitudModal.loading ? <p style={{ color: "#94a3b8", fontSize: "0.8rem" }}>Preparando vista previa…</p> : (<>
              <p style={{ color: "#94a3b8", fontSize: "0.72rem", margin: "6px 0 0" }}>
                Tipo detectado desde ADN: <b style={{ color: "#f8fafc" }}>
                  {{ nueva_con_subsidio: "Vivienda Nueva con Subsidio", nueva_sin_subsidio: "Vivienda Nueva sin Subsidio",
                     usada_con_subsidio: "Vivienda Usada con Subsidio", usada_sin_subsidio: "Vivienda Usada sin Subsidio" }[solicitudModal.tipo_cliente] || solicitudModal.inmobiliaria}</b>
                {" "}· Se envía desde: <b style={{ color: "#60a5fa" }}>{solicitudModal.desde}</b>
                {" "}· {solicitudModal.editando
                  ? <b style={{ color: "#facc15" }}>✏️ Modo edición — los cambios de destinatario se aprenden para la próxima vez</b>
                  : "Campos bloqueados: use EDITAR para modificar"}
              </p>
              {solicitudModal.alternativas && (
                <div data-testid="solicitud-alternativas" style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                  <span style={{ color: "#facc15", fontSize: "0.62rem", fontWeight: 800 }}>El ejecutivo elige cuál aplica:</span>
                  {solicitudModal.alternativas.map(d => (
                    <button key={d} data-testid={`solicitud-doc-${d}`}
                      onClick={() => abrirSolicitud({ id: solicitudModal.fid }, d)}
                      className="maserati-btn" style={{ minHeight: 28, fontSize: "0.6rem",
                        border: solicitudModal.doc_elegido === d ? "2px solid #d4af37" : undefined,
                        opacity: solicitudModal.doc_elegido === d ? 1 : 0.55 }}>
                      {solicitudModal.doc_elegido === d ? "● " : "○ "}{d === "promesa" ? "Compromiso de Compraventa" : "Carta Pie"}</button>
                  ))}
                </div>
              )}
              {!solicitudModal.configurada && (
                <div data-testid="solicitud-sin-encargado" style={{ marginTop: 8, padding: "0.6rem 0.8rem",
                  background: "rgba(250,204,21,0.10)", borderLeft: "3px solid #facc15", borderRadius: 8 }}>
                  <b style={{ color: "#facc15", fontSize: "0.66rem" }}>
                    ⚠️ {solicitudModal.usada ? "No hay vendedor configurado para este cliente."
                      : "No hay contacto configurado para esta inmobiliaria/proyecto."}</b>
                  <button onClick={() => { setSolicitudModal(null); abrirInmobiliarias(); }}
                    className="maserati-btn" style={{ marginLeft: 8, minHeight: 26, fontSize: "0.58rem" }}>🏢 Configurar ahora</button>
                </div>
              )}
              {(solicitudModal.faltantes || []).length > 0 && (
                <div data-testid="solicitud-faltantes" style={{ marginTop: 8, padding: "0.6rem 0.8rem",
                  background: "rgba(239,68,68,0.10)", borderLeft: "3px solid #ef4444", borderRadius: 8 }}>
                  <b style={{ color: "#f87171", fontSize: "0.66rem" }}>
                    ⛔ Envío bloqueado — falta: {(solicitudModal.faltantes || []).join(", ")}. Complete los campos abajo.</b>
                </div>
              )}
              <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
                <div style={{ flex: 1, minWidth: 180 }}>
                  <label style={{ color: "#94a3b8", fontSize: "0.66rem" }}>DESTINATARIO PRINCIPAL ({solicitudModal.usada ? "vendedor" : "contacto"})</label>
                  <input data-testid="solicitud-encargado" value={solicitudModal.encargado || ""}
                    readOnly={!solicitudModal.editando}
                    onChange={e => setSolicitudModal(m => ({ ...m, encargado: e.target.value }))}
                    placeholder="Nombre del contacto" style={{ ...inputStyle, marginTop: 3, fontSize: "0.85rem", opacity: solicitudModal.editando ? 1 : 0.75 }} />
                </div>
                <div style={{ flex: 1, minWidth: 180 }}>
                  <label style={{ color: "#94a3b8", fontSize: "0.66rem" }}>{solicitudModal.usada ? "VENDEDOR / ORIGEN" : "INMOBILIARIA / BROKER"}</label>
                  <input data-testid="solicitud-inmobiliaria" value={solicitudModal.inmobiliaria || ""}
                    readOnly={!solicitudModal.editando}
                    onChange={e => setSolicitudModal(m => ({ ...m, inmobiliaria: e.target.value }))}
                    style={{ ...inputStyle, marginTop: 3, fontSize: "0.85rem", opacity: solicitudModal.editando ? 1 : 0.75 }} />
                </div>
              </div>
              <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
                <div style={{ flex: 1, minWidth: 160 }}>
                  <label style={{ color: "#94a3b8", fontSize: "0.66rem" }}>RUT DEL CLIENTE *</label>
                  <input data-testid="solicitud-rut" value={solicitudModal.rut || ""}
                    readOnly={!solicitudModal.editando}
                    onChange={e => setSolicitudModal(m => ({ ...m, rut: e.target.value }))}
                    style={{ ...inputStyle, marginTop: 3, fontSize: "0.85rem", opacity: solicitudModal.editando ? 1 : 0.75 }} />
                </div>
                <div style={{ flex: 1, minWidth: 160 }}>
                  <label style={{ color: "#94a3b8", fontSize: "0.66rem" }}>{solicitudModal.usada ? "PROPIEDAD (opcional)" : "PROYECTO *"}</label>
                  <input data-testid="solicitud-proyecto" value={solicitudModal.proyecto || ""}
                    readOnly={!solicitudModal.editando}
                    onChange={e => setSolicitudModal(m => ({ ...m, proyecto: e.target.value }))}
                    style={{ ...inputStyle, marginTop: 3, fontSize: "0.85rem", opacity: solicitudModal.editando ? 1 : 0.75 }} />
                </div>
                {!solicitudModal.usada && solicitudModal.requiere_resolucion && (
                <div style={{ flex: 1, minWidth: 160 }}>
                  <label style={{ color: "#94a3b8", fontSize: "0.66rem" }}>RESOLUCIÓN SERVIU *</label>
                  <input data-testid="solicitud-resolucion" value={solicitudModal.resolucion_serviu || ""}
                    readOnly={!solicitudModal.editando}
                    onChange={e => setSolicitudModal(m => ({ ...m, resolucion_serviu: e.target.value }))}
                    placeholder="N° resolución" style={{ ...inputStyle, marginTop: 3, fontSize: "0.85rem", opacity: solicitudModal.editando ? 1 : 0.75 }} />
                </div>)}
              </div>
              <label style={{ color: "#94a3b8", fontSize: "0.66rem", display: "block", marginTop: 10 }}>
                CORREO DEL {solicitudModal.usada ? "VENDEDOR" : "CONTACTO"} — editable aquí (el sistema lo aprende para la próxima vez)</label>
              <input data-testid="solicitud-para" value={solicitudModal.para || ""}
                readOnly={!solicitudModal.editando}
                onChange={e => setSolicitudModal(m => ({ ...m, para: e.target.value }))}
                placeholder="correo@inmobiliaria.cl" style={{ ...inputStyle, marginTop: 3, fontSize: "0.85rem", opacity: solicitudModal.editando ? 1 : 0.75 }} />
              <div data-testid="solicitud-cc" style={{ marginTop: 8, padding: "0.5rem 0.7rem", background: "rgba(96,165,250,0.08)",
                borderLeft: "3px solid #60a5fa", borderRadius: 8, fontSize: "0.72rem", color: "#cbd5e1" }}>
                🔒 CC automático (fijo, no editable): <b style={{ color: "#60a5fa" }}>{(solicitudModal.cc || []).join(", ") || "—"}</b>
                {" "}· firma "Central Mutuos" incluida al pie
              </div>
              <label style={{ color: "#94a3b8", fontSize: "0.66rem", display: "block", marginTop: 8 }}>ASUNTO</label>
              <input data-testid="solicitud-asunto" value={solicitudModal.asunto || ""}
                readOnly={!solicitudModal.editando}
                onChange={e => setSolicitudModal(m => ({ ...m, asunto: e.target.value }))}
                style={{ ...inputStyle, marginTop: 3, fontSize: "0.85rem", opacity: solicitudModal.editando ? 1 : 0.75 }} />
              <label style={{ color: "#94a3b8", fontSize: "0.66rem", display: "block", marginTop: 8 }}>VISTA PREVIA DEL CORREO COMPLETO</label>
              <textarea data-testid="solicitud-cuerpo" value={solicitudModal.cuerpo || ""} rows={10}
                readOnly={!solicitudModal.editando}
                onChange={e => setSolicitudModal(m => ({ ...m, cuerpo: e.target.value }))}
                style={{ ...inputStyle, marginTop: 3, resize: "vertical", fontFamily: "inherit", fontSize: "0.85rem", opacity: solicitudModal.editando ? 1 : 0.9 }} />
              <div style={{ display: "flex", gap: 10, marginTop: 14, flexWrap: "wrap" }}>
                <button data-testid="solicitud-enviar" onClick={enviarSolicitud}
                  disabled={solicitudModal.enviando || !(solicitudModal.para || "").includes("@")
                    || !solicitudModal.rut
                    || (!solicitudModal.usada && !solicitudModal.proyecto)
                    || (solicitudModal.requiere_resolucion && !solicitudModal.resolucion_serviu)}
                  className="maserati-btn" style={{ minHeight: 42, fontSize: "0.8rem", fontWeight: 900,
                    opacity: ((solicitudModal.para || "").includes("@") && solicitudModal.rut
                      && (solicitudModal.usada || solicitudModal.proyecto)
                      && (!solicitudModal.requiere_resolucion || solicitudModal.resolucion_serviu)) ? 1 : 0.5 }}>
                  {solicitudModal.enviando ? "✉️ Enviando…" : "✅ CONFIRMAR Y ENVIAR"}</button>
                <button data-testid="solicitud-editar" onClick={() => setSolicitudModal(m => ({ ...m, editando: !m.editando }))}
                  className="maserati-btn" style={{ minHeight: 42, fontSize: "0.8rem",
                    border: solicitudModal.editando ? "2px solid #facc15" : undefined }}>
                  ✏️ {solicitudModal.editando ? "BLOQUEAR EDICIÓN" : "EDITAR"}</button>
                <button data-testid="solicitud-cancelar" onClick={() => setSolicitudModal(null)}
                  className="maserati-btn" style={{ minHeight: 42, fontSize: "0.8rem", opacity: 0.7 }}>❌ CANCELAR</button>
              </div>
            </>)}
          </div>
        </div>
      )}

      {bitModal && (
        <div data-testid="bitacora-modal" onClick={() => setBitModal(null)} style={modalBg}>
          <div onClick={e => e.stopPropagation()} style={modalBox}>
            <h4 style={{ margin: 0, color: "#d4af37", fontSize: "0.9rem" }}>
              🕐 Bitácora de Tiempos — {bitModal.cliente} · {bitModal.hito === "estudio" ? "Estudio de Títulos" : "Tasación"}
            </h4>
            {bitModal.loading && <p style={{ color: "#94a3b8", fontSize: "0.7rem" }}>Consultando registros…</p>}
            {!bitModal.loading && bitModal.error_seguimiento && (
              <div style={{ marginTop: 10, padding: "0.8rem 1rem", background: "rgba(239,68,68,0.12)",
                borderLeft: "3px solid #ef4444", borderRadius: 8 }}>
                <b style={{ color: "#ef4444", fontSize: "0.78rem" }}>⛔ ERROR DE SEGUIMIENTO</b>
                <p style={{ color: "#f8fafc", fontSize: "0.68rem", margin: "6px 0 0" }}>
                  {bitModal.detalle || "No hay registro de cuándo se solicitó este hito (Regla de Hierro)."}</p>
              </div>
            )}
            {!bitModal.loading && !bitModal.error_seguimiento && (
              <div style={{ marginTop: 10, fontSize: "0.72rem", color: "#e2e8f0", display: "grid", gap: 8 }}>
                <div>📅 <b>Fecha de solicitud:</b>{" "}
                  <span style={{ color: bitModal.demora_48h ? "#ef4444" : "#22c55e", fontWeight: 800 }}>
                    {(bitModal.fecha_solicitud || "").replace("T", " ")}</span>
                  {bitModal.demora_48h && <b style={{ color: "#ef4444" }}> · 🔴 +48h SIN RESPUESTA (cuello de botella)</b>}
                </div>
                <div>📨 <b>Destinatario:</b> {bitModal.destinatario || "—"} <span style={{ color: "#64748b" }}>({bitModal.fuente})</span></div>
                <div>⏱ <b>Días transcurridos:</b>{" "}
                  <span style={{ fontWeight: 800, color: bitModal.demora_48h ? "#ef4444" : "#f59e0b" }}>
                    {bitModal.dias_transcurridos ?? "?"} día(s) ({bitModal.horas_transcurridas ?? "?"} h)</span></div>
                <div>{bitModal.respondido
                  ? <span style={{ color: "#22c55e", fontWeight: 800 }}>✅ Respondido el {(bitModal.respondido_at || "").replace("T", " ")}</span>
                  : <span style={{ color: "#f59e0b", fontWeight: 800 }}>⏳ Aún sin respuesta</span>}</div>
                <div style={{ padding: "0.6rem 0.8rem", background: "rgba(212,175,55,0.08)",
                  borderLeft: "3px solid #d4af37", borderRadius: 8 }}>
                  <b style={{ color: "#d4af37", fontSize: "0.62rem" }}>QUÉ SE PIDIÓ (extracto del correo):</b>
                  <div style={{ marginTop: 4, whiteSpace: "pre-wrap" }}>{bitModal.resumen || "—"}</div>
                </div>
              </div>
            )}
            <button data-testid="bitacora-cerrar" onClick={() => setBitModal(null)} className="maserati-btn" style={{ marginTop: 14 }}>Cerrar</button>
          </div>
        </div>
      )}

      {reparoModal && (
        <div data-testid="super-reparo-modal" onClick={() => setReparoModal(null)} style={{ ...modalBg, zIndex: 210 }}>
          <div onClick={e => e.stopPropagation()} style={{ ...modalBox, maxWidth: 560, maxHeight: "78vh", overflowY: "auto" }}>
            <h4 style={{ margin: 0, color: "#f97316", fontSize: "0.9rem" }}>⚠️ Reparo extraído del correo — {reparoModal.cliente}</h4>
            <div style={{ marginTop: 10, padding: "0.8rem 1rem", background: "rgba(249,115,22,0.1)",
              borderLeft: "3px solid #f97316", borderRadius: 8, color: "#f8fafc", fontSize: "0.72rem", whiteSpace: "pre-wrap" }}>
              {reparoModal.texto || "Sin texto registrado."}
            </div>
            <button data-testid="super-reparo-cerrar" onClick={() => setReparoModal(null)} className="maserati-btn" style={{ marginTop: 14 }}>Cerrar</button>
          </div>
        </div>
      )}

      {manualModal && (
        <div data-testid="manual-modal" onClick={() => setManualModal(null)} style={modalBg}>
          <div onClick={e => e.stopPropagation()} style={modalBox}>
            <h4 style={{ margin: 0, color: "#ef4444", fontSize: "0.9rem" }}>
              ⚠️ Ingreso Manual de Respaldo — {manualModal.cliente}
            </h4>
            <p style={{ color: "#f8fafc", fontSize: "0.68rem", margin: "8px 0 0" }}>
              La cosecha automática NO encontró el campo <b>{CAMPO_LABEL[manualModal.campo] || manualModal.campo}</b> en la
              Bóveda ADN_CLIENTES_360. Esto es una <b style={{ color: "#ef4444" }}>alerta de fallo del sistema</b>, no un flujo normal.
              Lo que ingreses se guardará de inmediato en la Bóveda (Regla #67).
            </p>
            <input data-testid="manual-input" autoFocus value={manualModal.valor}
              onChange={e => setManualModal(m => ({ ...m, valor: e.target.value }))}
              placeholder={manualModal.campo === "rut" ? "Ej: 12.345.678-9 (se valida dígito verificador)" : `Ingresa ${CAMPO_LABEL[manualModal.campo] || manualModal.campo}`}
              style={inputStyle} onKeyDown={e => e.key === "Enter" && guardarManual()} />
            <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
              <button data-testid="manual-guardar" onClick={guardarManual} disabled={guardando}
                className="maserati-btn">{guardando ? "Guardando…" : "💾 Guardar en la Bóveda"}</button>
              <button data-testid="manual-cancelar" onClick={() => setManualModal(null)}
                style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.25)", color: "#e2e8f0",
                  borderRadius: 8, padding: "0.35rem 0.9rem", cursor: "pointer" }}>Cancelar</button>
            </div>
          </div>
        </div>
      )}

      {estadoModal && (
        <div data-testid="estado-modal" onClick={() => setEstadoModal(null)} style={modalBg}>
          <div onClick={e => e.stopPropagation()} style={modalBox}>
            <h4 style={{ margin: 0, color: "#d4af37", fontSize: "0.9rem" }}>
              ✏️ Editar Estado (Gerencia) — {estadoModal.cliente} · {HITO_LABEL[estadoModal.hito]}
            </h4>
            <p style={{ color: "#94a3b8", fontSize: "0.64rem", margin: "6px 0 0" }}>
              Cada cambio queda en bitácora inmutable (quién, fecha/hora, estado anterior y nuevo) y se guarda en la Bóveda ADN.
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
              {ESTADOS.map(s => (
                <button key={s} data-testid={`estado-opcion-${s.replace(/\s/g, "-")}`}
                  onClick={() => setEstadoModal(m => ({ ...m, estado: s }))}
                  style={{ cursor: "pointer", borderRadius: 999, padding: "4px 12px", fontSize: "0.64rem", fontWeight: 700,
                    border: estadoModal.estado === s ? "1.5px solid #d4af37" : "1px solid rgba(148,163,184,0.35)",
                    background: estadoModal.estado === s ? "rgba(212,175,55,0.18)" : "transparent",
                    color: estadoModal.estado === s ? "#d4af37" : "#e2e8f0" }}>{s}</button>
              ))}
            </div>
            <input data-testid="estado-input" value={estadoModal.estado}
              onChange={e => setEstadoModal(m => ({ ...m, estado: e.target.value }))}
              placeholder="…o escribe un estado especial del negocio" style={inputStyle}
              onKeyDown={e => e.key === "Enter" && guardarEstado()} />
            <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
              <button data-testid="estado-guardar" onClick={guardarEstado} disabled={guardando || !estadoModal.estado?.trim()}
                className="maserati-btn">{guardando ? "Guardando…" : "💾 Guardar con Trazabilidad"}</button>
              <button data-testid="estado-cancelar" onClick={() => setEstadoModal(null)}
                style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.25)", color: "#e2e8f0",
                  borderRadius: 8, padding: "0.35rem 0.9rem", cursor: "pointer" }}>Cancelar</button>
            </div>
          </div>
        </div>
      )}

      {conflictoModal && (
        <div data-testid="conflicto-modal" onClick={() => setConflictoModal(null)} style={modalBg}>
          <div onClick={e => e.stopPropagation()} style={modalBox}>
            <h4 style={{ margin: 0, color: "#ef4444", fontSize: "0.9rem" }}>
              ❓ Conflicto de Estado — {conflictoModal.cliente} · {HITO_LABEL[conflictoModal.hito]}
            </h4>
            <p style={{ color: "#f8fafc", fontSize: "0.7rem", margin: "8px 0 0" }}>
              DashAI detectó un dato NUEVO vía correo, posterior al estado que Gerencia fijó manualmente.
              ¿Deseas mantener el estado manual o sobreescribirlo con lo detectado automáticamente?
            </p>
            <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
              <button data-testid="conflicto-mantener" onClick={() => resolverConflicto("mantener")} disabled={guardando}
                className="maserati-btn">✏️ Mantener manual</button>
              <button data-testid="conflicto-sobreescribir" onClick={() => resolverConflicto("sobreescribir")} disabled={guardando}
                style={{ background: "rgba(239,68,68,0.14)", border: "1px solid rgba(239,68,68,0.5)", color: "#ef4444",
                  borderRadius: 8, padding: "0.35rem 0.9rem", cursor: "pointer", fontWeight: 800 }}>🤖 Sobreescribir con lo detectado</button>
            </div>
          </div>
        </div>
      )}

      {fuentesModal && (
        <div data-testid="fuentes-modal" onClick={() => setFuentesModal(null)} style={modalBg}>
          <div onClick={e => e.stopPropagation()} style={modalBox}>
            <h4 style={{ margin: 0, color: "#d4af37", fontSize: "0.9rem" }}>
              ⚙️ Correos Fuente — {HITO_LABEL[fuentesModal.hito]}
            </h4>
            {fuentesModal.loading ? <p style={{ color: "#94a3b8", fontSize: "0.7rem" }}>Cargando…</p> : (<>
              <div style={{ marginTop: 10, paddingBottom: 10, borderBottom: "1px solid rgba(212,175,55,0.4)" }}>
                <b data-testid="fuentes-bloque-global" style={{ color: "#d4af37", fontSize: "0.7rem" }}>
                  FUENTES GLOBALES — Aplica a todos los clientes</b>
                <div style={{ marginTop: 6, display: "grid", gap: 5 }}>
                  {(fuentesModal.globales || []).length === 0 &&
                    <i style={{ color: "#94a3b8", fontSize: "0.64rem" }}>Sin fuentes globales configuradas</i>}
                  {(fuentesModal.globales || []).map(f => (
                    <div key={f.correo} data-testid={`fuente-global-${f.correo}`}
                      style={{ display: "flex", alignItems: "center", gap: 8, padding: "0.35rem 0.6rem",
                        background: "rgba(30,41,59,0.7)", borderRadius: 8, fontSize: "0.66rem", color: "#e2e8f0" }}>
                      <span style={{ flex: 1 }}><b>{f.correo}</b>{f.nombre ? ` — ${f.nombre}` : ""}
                        <span style={{ color: "#64748b" }}> · Global{f.ultima_deteccion ? ` · último: ${f.ultima_deteccion.slice(0, 10)}` : " · sin detecciones"}</span></span>
                      <button data-testid={`fuente-quitar-${f.correo}`} onClick={() => opFuente("global", "quitar", f.correo, f.nombre)}
                        disabled={guardando} style={{ cursor: "pointer", background: "#5C1A1A", color: "#fff",
                          border: "none", borderRadius: 6, padding: "2px 10px", fontWeight: 800, fontSize: "0.6rem" }}>QUITAR</button>
                    </div>
                  ))}
                </div>
                <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                  <input data-testid="fuentes-input" value={fuentesModal.gCorreo}
                    onChange={e => setFuentesModal(m => ({ ...m, gCorreo: e.target.value }))}
                    placeholder="correo@fuente.cl" style={{ ...inputStyle, marginTop: 0, flex: 1 }} />
                  <input data-testid="fuentes-nombre-input" value={fuentesModal.gNombre}
                    onChange={e => setFuentesModal(m => ({ ...m, gNombre: e.target.value }))}
                    placeholder="Nombre descriptivo" style={{ ...inputStyle, marginTop: 0, flex: 1 }} />
                  <button data-testid="fuentes-agregar-global" disabled={guardando || !fuentesModal.gCorreo?.trim()}
                    onClick={() => opFuente("global", "agregar", fuentesModal.gCorreo.trim(), fuentesModal.gNombre)}
                    className="maserati-btn" style={{ minHeight: 36, whiteSpace: "nowrap" }}>➕ Agregar Fuente Global</button>
                </div>
              </div>
              <div style={{ marginTop: 12 }}>
                <b data-testid="fuentes-bloque-individual" style={{ color: "#d4af37", fontSize: "0.7rem" }}>
                  FUENTES INDIVIDUALES — Solo para este cliente</b>
                <select data-testid="fuentes-cliente-select" value={fuentesModal.cliSel}
                  onChange={e => setFuentesModal(m => ({ ...m, cliSel: e.target.value }))}
                  style={{ ...inputStyle, marginTop: 6 }}>
                  <option value="">— Selecciona el cliente —</option>
                  {(data?.clientes || []).map(c => <option key={c.id} value={c.id}>{c.cliente}</option>)}
                </select>
                {fuentesModal.cliSel && (<>
                  <div style={{ marginTop: 6, display: "grid", gap: 5 }}>
                    {(((fuentesModal.alternativas || []).find(a => a.id === fuentesModal.cliSel)?.fuentes_doc?.[fuentesModal.hito]) || []).map(f => (
                      <div key={f.correo} data-testid={`fuente-individual-${f.correo}`}
                        style={{ display: "flex", alignItems: "center", gap: 8, padding: "0.35rem 0.6rem",
                          background: "rgba(30,41,59,0.7)", borderRadius: 8, fontSize: "0.66rem", color: "#e2e8f0" }}>
                        <span style={{ flex: 1 }}><b>{f.correo}</b>{f.nombre ? ` — ${f.nombre}` : ""}
                          <span style={{ color: "#64748b" }}> · Individual</span></span>
                        <button data-testid={`fuente-ind-quitar-${f.correo}`} onClick={() => opFuente("individual", "quitar", f.correo, f.nombre)}
                          disabled={guardando} style={{ cursor: "pointer", background: "#5C1A1A", color: "#fff",
                            border: "none", borderRadius: 6, padding: "2px 10px", fontWeight: 800, fontSize: "0.6rem" }}>QUITAR</button>
                      </div>
                    ))}
                  </div>
                  <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                    <input data-testid="fuentes-cliente-input" value={fuentesModal.iCorreo}
                      onChange={e => setFuentesModal(m => ({ ...m, iCorreo: e.target.value }))}
                      placeholder="correo@fuente.cl" style={{ ...inputStyle, marginTop: 0, flex: 1 }} />
                    <input data-testid="fuentes-cliente-nombre" value={fuentesModal.iNombre}
                      onChange={e => setFuentesModal(m => ({ ...m, iNombre: e.target.value }))}
                      placeholder="Nombre descriptivo" style={{ ...inputStyle, marginTop: 0, flex: 1 }} />
                    <button data-testid="fuentes-agregar-individual" disabled={guardando || !fuentesModal.iCorreo?.trim()}
                      onClick={() => opFuente("individual", "agregar", fuentesModal.iCorreo.trim(), fuentesModal.iNombre)}
                      className="maserati-btn" style={{ minHeight: 36, whiteSpace: "nowrap" }}>➕ Agregar Fuente Individual</button>
                  </div>
                </>)}
              </div>
              <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid rgba(212,175,55,0.4)" }}>
                <b data-testid="fuentes-bloque-barrido" style={{ color: "#d4af37", fontSize: "0.7rem" }}>
                  📥 CUENTA DE BARRIDO (SOLO LECTURA) — Lee lo que nos envían, jamás envía</b>
                {fuentesModal.barrido ? (<>
                  <div style={{ marginTop: 6, display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                    <select data-testid="barrido-cuenta-select" value={fuentesModal.barrido.rol || ""}
                      onChange={e => e.target.value && opBarrido({ rol: e.target.value })}
                      disabled={guardando} style={{ ...inputStyle, marginTop: 0, flex: 1, minWidth: 200 }}>
                      <option value="">— Designar casilla de barrido —</option>
                      {(fuentesModal.barrido.cuentas_disponibles || []).map(a =>
                        <option key={a.rol} value={a.rol}>{a.correo} ({a.rol})</option>)}
                    </select>
                    {fuentesModal.barrido.configurada && (<>
                      <button data-testid="barrido-barrer-btn" disabled={guardando}
                        onClick={() => opBarrido(null, true)} className="maserati-btn"
                        style={{ minHeight: 36, whiteSpace: "nowrap" }}>🔍 Barrer Ahora (7 días)</button>
                      <button data-testid="barrido-toggle-btn" disabled={guardando}
                        onClick={() => opBarrido({ activo: !fuentesModal.barrido.activo })}
                        style={{ cursor: "pointer", background: fuentesModal.barrido.activo ? "#5C1A1A" : "#1A5C2A",
                          color: "#fff", border: "none", borderRadius: 8, padding: "0.4rem 0.8rem",
                          fontWeight: 800, fontSize: "0.6rem", whiteSpace: "nowrap" }}>
                        {fuentesModal.barrido.activo ? "⏸ Pausar automático" : "▶ Activar automático"}</button>
                    </>)}
                  </div>
                  <div data-testid="barrido-estado" style={{ marginTop: 6, color: "#94a3b8", fontSize: "0.62rem" }}>
                    {fuentesModal.barrido.configurada
                      ? <>Casilla: <b style={{ color: "#e2e8f0" }}>{fuentesModal.barrido.correo}</b>
                          · Automático cada 20 min: <b style={{ color: fuentesModal.barrido.activo ? "#4ade80" : "#ef4444" }}>
                            {fuentesModal.barrido.activo ? "ACTIVO" : "PAUSADO"}</b>
                          {fuentesModal.barrido.ultima_lectura && <> · Última lectura: {fuentesModal.barrido.ultima_lectura.slice(0, 16).replace("T", " ")}</>}
                          {fuentesModal.barrido.barrido_estado && <> · Estado: {fuentesModal.barrido.barrido_estado}</>}
                          {fuentesModal.barrido.ultimo_resultado?.correos_revisados !== undefined &&
                            <div style={{ marginTop: 2 }}>Último barrido: {fuentesModal.barrido.ultimo_resultado.correos_revisados} correos ·
                              {" "}{fuentesModal.barrido.ultimo_resultado.tasaciones_detectadas || 0} tasaciones ·
                              {" "}{fuentesModal.barrido.ultimo_resultado.estudios_detectados || 0} estudios ·
                              {" "}{fuentesModal.barrido.ultimo_resultado.sets_detectados || 0} sets ·
                              {" "}{fuentesModal.barrido.ultimo_resultado.ruts_cosechados || 0} RUTs cosechados</div>}
                        </>
                      : <i style={{ color: "#ef4444" }}>⚠️ Sin casilla designada — selecciona una cuenta IMAP existente del sistema</i>}
                  </div>
                </>) : <i style={{ display: "block", marginTop: 6, color: "#94a3b8", fontSize: "0.62rem" }}>No fue posible consultar la cuenta de barrido</i>}
              </div>
              <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
                <button data-testid="fuentes-cancelar" onClick={() => { setFuentesModal(null); recargar(); }}
                  style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.25)", color: "#e2e8f0",
                    borderRadius: 8, padding: "0.35rem 0.9rem", cursor: "pointer" }}>Cerrar</button>
              </div>
            </>)}
          </div>
        </div>
      )}

      {auditoria && !auditoria.loading && (
        <div data-testid="auditoria-modal" onClick={() => setAuditoria(null)} style={modalBg}>
          <div onClick={e => e.stopPropagation()} style={{ ...modalBox, maxWidth: 640, maxHeight: "82vh", overflowY: "auto" }}>
            <h4 style={{ margin: 0, color: "#d4af37", fontSize: "0.9rem" }}>🧬 Reporte de Auditoría de Bóveda — ADN_CLIENTES_360</h4>
            {auditoria.reporte ? (() => { const r = auditoria.reporte; return (<>
              <p style={{ color: "#94a3b8", fontSize: "0.64rem", margin: "6px 0 10px" }}>
                Ejecutada: {(auditoria.ultima || "").slice(0, 16).replace("T", " ")} · Orden de búsqueda: ficha ADN → EXPEDIENTE_360 → documentos → correos 90 días
              </p>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                {[["Clientes auditados", r.clientes_auditados], ["Con RUT en la bóveda", r.con_rut_boveda],
                  ["Sin RUT al inicio", r.sin_rut_inicial], ["RUTs encontrados y escritos", (r.ruts_encontrados || []).length],
                  ["Campos de identidad vacíos", r.campos_vacios], ["Campos poblados automáticamente", r.campos_poblados],
                  ["Requieren ingreso manual", r.requieren_ingreso_manual]].map(([k, v]) => (
                  <div key={k} style={{ background: "rgba(30,41,59,0.7)", borderRadius: 10, padding: "0.5rem 0.8rem" }}>
                    <div style={{ color: "#94a3b8", fontSize: "0.58rem" }}>{k}</div>
                    <div style={{ color: "#f8fafc", fontWeight: 900, fontSize: "1.05rem" }}>{v ?? 0}</div>
                  </div>
                ))}
              </div>
              {(r.ruts_encontrados || []).length > 0 && (
                <div style={{ marginTop: 10 }}>
                  <b style={{ color: "#4ade80", fontSize: "0.66rem" }}>✅ RUTs encontrados (escritos en la bóveda):</b>
                  {(r.ruts_encontrados || []).map(x => (
                    <div key={x.cliente} data-testid={`auditoria-rut-${x.cliente}`} style={{ color: "#e2e8f0", fontSize: "0.62rem", marginTop: 3 }}>
                      <b>{x.cliente}</b> → <span style={{ fontFamily: "monospace" }}>{x.rut}</span>
                      <span style={{ color: "#64748b" }}> · fuente: {x.fuente}</span></div>
                  ))}
                </div>
              )}
              {(r.ruts_por_confirmar || []).length > 0 && (
                <div style={{ marginTop: 10, background: "rgba(239,68,68,0.12)", border: "1px solid rgba(239,68,68,0.5)",
                  borderRadius: 10, padding: "0.5rem 0.8rem" }}>
                  <b style={{ color: "#ef4444", fontSize: "0.66rem" }}>🔴 RUT Por Confirmar (no está en ninguna de las 4 fuentes — ingreso manual con doble clic):</b>
                  <div style={{ color: "#fca5a5", fontSize: "0.62rem", marginTop: 3 }}>{(r.ruts_por_confirmar || []).join(" · ")}</div>
                </div>
              )}
              {(r.detalle_campos || []).length > 0 && (
                <div style={{ marginTop: 10 }}>
                  <b style={{ color: "#d4af37", fontSize: "0.66rem" }}>Campos poblados desde la bóveda:</b>
                  {(r.detalle_campos || []).slice(0, 30).map((x, i) => (
                    <div key={`${x.cliente}-${x.campo}-${i}`} style={{ color: "#e2e8f0", fontSize: "0.6rem", marginTop: 2 }}>
                      {x.cliente}: <b>{x.campo}</b> → {String(x.valor)}</div>
                  ))}
                </div>
              )}
            </>); })() : <p style={{ color: "#ef4444", fontSize: "0.68rem" }}>La auditoría terminó con estado: {auditoria.estado}</p>}
            <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
              <button data-testid="auditoria-cerrar" onClick={() => setAuditoria(null)}
                style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.25)", color: "#e2e8f0",
                  borderRadius: 8, padding: "0.35rem 0.9rem", cursor: "pointer" }}>Cerrar</button>
            </div>
          </div>
        </div>
      )}

      {remitentesModal && (
        <div data-testid="remitentes-modal" onClick={() => setRemitentesModal(null)} style={modalBg}>
          <div onClick={e => e.stopPropagation()} style={{ ...modalBox, maxWidth: 680, maxHeight: "82vh", overflowY: "auto" }}>
            <h4 style={{ margin: 0, color: "#d4af37", fontSize: "0.9rem" }}>📡 Remitentes Detectados Automáticamente</h4>
            <p style={{ color: "#64748b", fontSize: "0.6rem", margin: "4px 0 10px" }}>
              Regla de Hierro: la captura es automática, la confirmación final es de Gerencia.
              Un remitente no confirmado queda "Pendiente de Confirmación". Dos reubicaciones iguales = criterio permanente.</p>
            {remitentesModal.loading ? <p style={{ color: "#94a3b8" }}>Cargando…</p> : <>
              {(remitentesModal.detectados || []).length === 0 &&
                <p style={{ color: "#94a3b8", fontSize: "0.7rem" }}>Sin remitentes pendientes. DashAI los capturará al detectar correos de clientes + hitos.</p>}
              {(remitentesModal.detectados || []).map((d, i) => (
                <div key={`${d.folder_id}-${d.hito}-${d.correo}`} data-testid={`remitente-${i}`}
                  style={{ background: "rgba(30,41,59,0.7)", borderRadius: 10, padding: "0.55rem 0.8rem", marginTop: 6 }}>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "baseline" }}>
                    <b style={{ color: "#f8fafc", fontSize: "0.72rem" }}>{d.nombre}</b>
                    <span style={{ color: "#7DD3FC", fontSize: "0.66rem" }}>{d.correo}</span>
                    <span style={{ color: "#d4af37", fontSize: "0.62rem", fontWeight: 800 }}>→ {d.hito}</span>
                    <span style={{ color: "#94a3b8", fontSize: "0.6rem" }}>de {d.cliente}</span>
                    <span style={{ marginLeft: "auto", color: "#eab308", fontSize: "0.56rem", fontStyle: "italic" }}>
                      {d.etiqueta} · Pendiente de Confirmación</span>
                  </div>
                  <div style={{ display: "flex", gap: 6, marginTop: 6, flexWrap: "wrap", alignItems: "center" }}>
                    <button data-testid={`remitente-confirmar-${i}`} onClick={() => accionRemitente(d, "confirmar")}
                      style={{ cursor: "pointer", background: "#1A5C2A", color: "#fff", border: "none", borderRadius: 6,
                        padding: "0.25rem 0.6rem", fontSize: "0.6rem", fontWeight: 800 }}>✔ CONFIRMAR</button>
                    <select data-testid={`remitente-destino-${i}`} defaultValue=""
                      onChange={e => e.target.value && accionRemitente(d, "reubicar", e.target.value)}
                      style={{ background: "rgba(2,6,23,0.9)", border: "1px solid rgba(148,163,184,0.3)",
                        color: "#e2e8f0", borderRadius: 6, padding: "0.2rem 0.4rem", fontSize: "0.6rem" }}>
                      <option value="">↪ REUBICAR a…</option>
                      {(remitentesModal.hitos_validos || []).filter(h => h !== d.hito).map(h =>
                        <option key={h} value={h}>{h}</option>)}
                    </select>
                    <button data-testid={`remitente-eliminar-${i}`} onClick={() => accionRemitente(d, "eliminar")}
                      style={{ cursor: "pointer", background: "#5C1A1A", color: "#fff", border: "none", borderRadius: 6,
                        padding: "0.25rem 0.6rem", fontSize: "0.6rem", fontWeight: 800 }}>🗑 ELIMINAR</button>
                    <button data-testid={`remitente-bloquear-${i}`} onClick={() => accionRemitente(d, "bloquear")}
                      style={{ cursor: "pointer", background: "#3A3A3A", color: "#fff", border: "1px solid #eab308",
                        borderRadius: 6, padding: "0.25rem 0.6rem", fontSize: "0.6rem", fontWeight: 800 }}>🚫 BLOQUEAR</button>
                  </div>
                </div>
              ))}
              {(remitentesModal.registro || []).length > 0 && (
                <div style={{ marginTop: 12 }}>
                  <b style={{ color: "#d4af37", fontSize: "0.66rem" }}>🧠 Registro inteligente (por hito y broker):</b>
                  {(remitentesModal.registro || []).slice(0, 12).map(r => (
                    <div key={r.correo} style={{ color: "#94a3b8", fontSize: "0.6rem", marginTop: 3 }}>
                      <b style={{ color: "#e2e8f0" }}>{r.nombre}</b> ({r.correo}) ·
                      hitos: {Object.entries(r.hitos || {}).map(([h, n]) => `${h}×${n}`).join(", ") || "—"} ·
                      brokers: {Object.keys(r.brokers || {}).join(", ") || "—"}
                      {r.hito_forzado && <span style={{ color: "#4ade80" }}> · aprendido: {r.hito_forzado}</span>}
                    </div>
                  ))}
                </div>
              )}
              {(remitentesModal.bloqueados || []).length > 0 && (
                <p style={{ color: "#64748b", fontSize: "0.58rem", marginTop: 8 }}>
                  🚫 Bloqueados: {(remitentesModal.bloqueados || []).join(", ")}</p>
              )}
            </>}
            <button data-testid="remitentes-cerrar" onClick={() => setRemitentesModal(null)}
              style={{ marginTop: 12, background: "transparent", border: "1px solid rgba(255,255,255,0.25)",
                color: "#e2e8f0", borderRadius: 8, padding: "0.35rem 0.9rem", cursor: "pointer" }}>Cerrar</button>
          </div>
        </div>
      )}

      {avanceModal && (
        <div data-testid="avance-modal" onClick={() => setAvanceModal(null)} style={modalBg}>
          <div onClick={e => e.stopPropagation()} style={{ ...modalBox, maxWidth: 520 }}>
            <h4 style={{ margin: 0, color: "#d4af37", fontSize: "0.9rem" }}>
              📊 Avance de {avanceModal.cliente} — {avanceModal.avance?.pct ?? 0}%</h4>
            <div style={{ marginTop: 8, height: 10, background: "rgba(0,0,0,0.35)", borderRadius: 99, overflow: "hidden" }}>
              <div style={{ width: `${Math.min(avanceModal.avance?.pct || 0, 100)}%`, height: "100%",
                borderRadius: 99, background: colorAvance(avanceModal.avance?.pct || 0) }} />
            </div>
            <div style={{ marginTop: 12 }}>
              {(avanceModal.avance?.etapas || []).map(e => (
                <div key={e.clave} data-testid={`avance-etapa-${e.clave}`}
                  style={{ display: "flex", alignItems: "center", gap: 8, padding: "0.45rem 0.6rem",
                    marginTop: 4, borderRadius: 8,
                    background: e.completada ? "rgba(34,197,94,0.10)" : "rgba(148,163,184,0.07)",
                    border: `1px solid ${e.completada ? "rgba(34,197,94,0.45)" : "rgba(148,163,184,0.2)"}` }}>
                  <span style={{ fontSize: "0.85rem" }}>{e.completada ? "✅" : "⬜"}</span>
                  <span style={{ flex: 1, color: e.completada ? "#e2e8f0" : "#94a3b8", fontSize: "0.72rem",
                    fontWeight: e.completada ? 700 : 400 }}>{e.etapa}</span>
                  <b style={{ color: e.completada ? "#4ade80" : "#64748b", fontSize: "0.7rem" }}>{e.peso}%</b>
                </div>
              ))}
            </div>
            <p style={{ color: "#64748b", fontSize: "0.6rem", marginTop: 10 }}>
              Regla de Hierro: cada etapa solo suma con respaldo real (correo o verificación documental). Nunca se infla.</p>
            <button data-testid="avance-cerrar" onClick={() => setAvanceModal(null)}
              style={{ marginTop: 8, background: "transparent", border: "1px solid rgba(255,255,255,0.25)",
                color: "#e2e8f0", borderRadius: 8, padding: "0.35rem 0.9rem", cursor: "pointer" }}>Cerrar</button>
          </div>
        </div>
      )}

      {agregarModal && (
        <div data-testid="agregar-modal" onClick={() => setAgregarModal(null)} style={modalBg}>
          <div onClick={e => e.stopPropagation()} style={modalBox}>
            <h4 style={{ margin: 0, color: "#d4af37", fontSize: "0.9rem" }}>➕ Agregar Cliente (Gerencia)</h4>
            <p style={{ color: "#94a3b8", fontSize: "0.62rem", margin: "6px 0 0" }}>
              Válvula operativa para ajustes puntuales — el flujo normal es la carga automática desde la proyección del broker.
              La ficha se crea en la Bóveda ADN y la acción queda en bitácora.
            </p>
            <input data-testid="agregar-nombre" autoFocus value={agregarModal.nombre}
              onChange={e => setAgregarModal(m => ({ ...m, nombre: e.target.value }))}
              placeholder="Nombre y apellido del cliente" style={inputStyle} />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              <select data-testid="agregar-inmobiliaria" value={agregarModal.inmobiliaria}
                onChange={e => setAgregarModal(m => ({ ...m, inmobiliaria: e.target.value }))} style={inputStyle}>
                <option value="">Inmobiliaria…</option>
                {["Boetsch", "Word", "Urbanizate", "Maestra", "Ecomac"].map(i => <option key={i} value={i}>{i}</option>)}
              </select>
              <select data-testid="agregar-tipo" value={agregarModal.tipo_propiedad}
                onChange={e => setAgregarModal(m => ({ ...m, tipo_propiedad: e.target.value }))} style={inputStyle}>
                <option value="nueva">Propiedad Nueva</option>
                <option value="usada">Casa Usada</option>
              </select>
              <input data-testid="agregar-proyecto" value={agregarModal.proyecto}
                onChange={e => setAgregarModal(m => ({ ...m, proyecto: e.target.value }))}
                placeholder="Proyecto (ej: Fuch Locker)" style={inputStyle} />
              <input data-testid="agregar-ciudad" value={agregarModal.ciudad}
                onChange={e => setAgregarModal(m => ({ ...m, ciudad: e.target.value }))}
                placeholder="Ciudad (ej: Osorno)" style={inputStyle} />
              <select data-testid="agregar-subsidio" value={agregarModal.subsidio}
                onChange={e => setAgregarModal(m => ({ ...m, subsidio: e.target.value }))} style={inputStyle}>
                <option value="Sin Subsidio">Sin Subsidio</option>
                <option value="Con Subsidio">Con Subsidio</option>
                <option value="Con Subsidio DS1 Tramo 2">Con Subsidio DS1 Tramo 2</option>
              </select>
              <input data-testid="agregar-monto" value={agregarModal.monto_uf}
                onChange={e => setAgregarModal(m => ({ ...m, monto_uf: e.target.value }))}
                placeholder="Monto UF (ej: 2.000)" style={inputStyle} />
            </div>
            <input data-testid="agregar-broker" value={agregarModal.broker}
              onChange={e => setAgregarModal(m => ({ ...m, broker: e.target.value }))}
              placeholder="Broker" style={inputStyle} />
            <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
              <button data-testid="agregar-guardar" onClick={agregarCliente} disabled={guardando || !agregarModal.nombre?.trim()}
                className="maserati-btn">{guardando ? "Creando…" : "💾 Crear en la Bóveda"}</button>
              <button data-testid="agregar-cancelar" onClick={() => setAgregarModal(null)}
                style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.25)", color: "#e2e8f0",
                  borderRadius: 8, padding: "0.35rem 0.9rem", cursor: "pointer" }}>Cancelar</button>
            </div>
          </div>
        </div>
      )}

      {panel && (
        <div data-testid="panel-lateral" style={{ position: "fixed", top: 0, right: 0, bottom: 0, width: "min(420px, 92vw)",
          zIndex: 230, background: "rgba(10,15,28,0.98)", borderLeft: "2px solid #d4af37",
          boxShadow: "-20px 0 60px rgba(0,0,0,0.6)", overflowY: "auto", padding: "1.2rem 1.3rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <h4 style={{ margin: 0, color: "#d4af37", fontSize: "0.86rem", flex: 1 }}>
              {panel.cliente} · {HITO_LABEL[panel.hito]}
            </h4>
            <button data-testid="panel-fuentes-gear" onClick={() => abrirFuentes(panel.hito)} title="Configurar correos fuente"
              style={{ cursor: "pointer", border: "none", background: "transparent", fontSize: "0.85rem" }}>⚙️</button>
            <button data-testid="panel-cerrar" onClick={() => setPanel(null)}
              style={{ cursor: "pointer", border: "1px solid rgba(255,255,255,0.25)", background: "transparent",
                color: "#e2e8f0", borderRadius: 8, padding: "0.2rem 0.6rem" }}>✕</button>
          </div>
          {panel.loading ? <p style={{ color: "#94a3b8", fontSize: "0.7rem" }}>Cargando panel…</p> : (<>
            <div style={{ marginTop: 12 }}>
              <b style={{ color: "#f5d76e", fontSize: "0.64rem" }}>✏️ CAMBIO DE ESTADO MANUAL (Gerencia)</b>
              <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
                <select data-testid="panel-estado-select" value={panel.nuevoEstado}
                  onChange={e => setPanel(p => ({ ...p, nuevoEstado: e.target.value }))}
                  style={{ ...inputStyle, marginTop: 0, flex: 1 }}>
                  <option value="">— Selecciona estado —</option>
                  {(ESTADOS_POR[panel.hito] || ESTADOS).map(s => <option key={s} value={s}>{s}</option>)}
                </select>
                <button data-testid="panel-estado-guardar" onClick={guardarEstadoPanel} disabled={guardando || !panel.nuevoEstado}
                  className="maserati-btn" style={{ minHeight: 36 }}>💾</button>
              </div>
              {panel.data?.estado_manual?.estado && (
                <div style={{ color: "#eab308", fontSize: "0.6rem", marginTop: 4 }}>
                  ✏️ Manual vigente: <b>{panel.data.estado_manual.estado}</b> ({panel.data.estado_manual.por} · {(panel.data.estado_manual.en || "").slice(0, 16).replace("T", " ")})</div>
              )}
            </div>
            <div style={{ marginTop: 14 }}>
              <b style={{ color: "#f5d76e", fontSize: "0.64rem" }}>📮 CORREOS FUENTE ACTIVOS</b>
              <div style={{ marginTop: 4, fontSize: "0.64rem", color: "#e2e8f0" }}>
                {(panel.data?.fuentes || []).length
                  ? (panel.data.fuentes || []).map(f => <div key={f}>• {f}</div>)
                  : <i style={{ color: "#ef4444" }}>⚠️ Sin correos fuente configurados — usa el ⚙️</i>}
              </div>
            </div>
            {panel.hito === "estudio" && panel.data?.detalle_reparos && (
              <div style={{ marginTop: 14, padding: "0.6rem 0.8rem", background: "rgba(124,45,18,0.4)",
                borderLeft: "3px solid #f97316", borderRadius: 8, fontSize: "0.64rem", color: "#fdba74", whiteSpace: "pre-wrap" }}>
                <b>⚠️ REPAROS (texto exacto):</b><div style={{ marginTop: 4 }}>{panel.data.detalle_reparos}</div>
              </div>
            )}
            {panel.data?.bitacora_tiempos && !panel.data.bitacora_tiempos.error_seguimiento && (
              <div style={{ marginTop: 14, fontSize: "0.64rem", color: "#e2e8f0" }}>
                <b style={{ color: "#f5d76e", fontSize: "0.64rem" }}>🕐 BITÁCORA DE TIEMPOS</b>
                <div style={{ marginTop: 4 }}>📅 Solicitado: <b style={{ color: panel.data.bitacora_tiempos.demora_48h ? "#ef4444" : "#22c55e" }}>
                  {(panel.data.bitacora_tiempos.fecha_solicitud || "").replace("T", " ")}</b>
                  {panel.data.bitacora_tiempos.demora_48h && <b style={{ color: "#ef4444" }}> · 🔴 +48h</b>}</div>
                <div>📨 Destinatario: {panel.data.bitacora_tiempos.destinatario || "—"}</div>
                <div>⏱ {panel.data.bitacora_tiempos.dias_transcurridos ?? "?"} día(s) transcurrido(s)</div>
              </div>
            )}
            <div style={{ marginTop: 14 }}>
              <b style={{ color: "#f5d76e", fontSize: "0.64rem" }}>📥 CORREOS DETECTADOS DEL CLIENTE</b>
              <div style={{ marginTop: 4, display: "grid", gap: 5 }}>
                {(panel.data?.correos_detectados || []).length === 0 &&
                  <i style={{ color: "#94a3b8", fontSize: "0.62rem" }}>Sin correos detectados aún</i>}
                {(panel.data?.correos_detectados || []).map((m, i) => (
                  <div key={m.id || `${m.hito}-${m.fecha || m.creado}-${i}`} style={{ padding: "0.4rem 0.6rem", background: "rgba(30,41,59,0.7)", borderRadius: 8, fontSize: "0.6rem" }}>
                    <b style={{ color: "#7dd3fc" }}>{m.hito}</b> · <span style={{ color: "#94a3b8" }}>{(m.fecha || m.creado || "").slice(0, 16).replace("T", " ")}</span>
                    <div style={{ color: "#e2e8f0" }}>{m.asunto}</div>
                    <span style={{ color: "#64748b" }}>{m.fuente} · {m.direccion}</span>
                  </div>
                ))}
              </div>
            </div>
            <div style={{ marginTop: 14 }}>
              <b style={{ color: "#f5d76e", fontSize: "0.64rem" }}>📝 NOTAS MANUALES</b>
              {(panel.data?.notas || []).map((n, i) => (
                <div key={n.en || i} style={{ marginTop: 4, fontSize: "0.62rem", color: "#e2e8f0", padding: "0.35rem 0.6rem",
                  background: "rgba(212,175,55,0.08)", borderLeft: "2px solid #d4af37", borderRadius: 6 }}>
                  {n.texto} <span style={{ color: "#64748b" }}>— {n.por} · {(n.en || "").slice(0, 16).replace("T", " ")}</span>
                </div>
              ))}
              <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
                <input data-testid="panel-nota-input" value={panel.nota}
                  onChange={e => setPanel(p => ({ ...p, nota: e.target.value }))}
                  placeholder="Agregar observación…" style={{ ...inputStyle, marginTop: 0, flex: 1 }}
                  onKeyDown={e => e.key === "Enter" && guardarNota()} />
                <button data-testid="panel-nota-guardar" onClick={guardarNota} disabled={guardando || !panel.nota?.trim()}
                  className="maserati-btn" style={{ minHeight: 36 }}>➕</button>
              </div>
            </div>
            <div style={{ marginTop: 14, paddingBottom: 20 }}>
              <b style={{ color: "#f5d76e", fontSize: "0.64rem" }}>📜 BITÁCORA DE CAMBIOS (inmutable)</b>
              {(panel.data?.bitacora_cambios || []).length === 0 &&
                <div><i style={{ color: "#94a3b8", fontSize: "0.62rem" }}>Sin cambios manuales registrados</i></div>}
              {(panel.data?.bitacora_cambios || []).map((l, i) => (
                <div key={`${l.fecha}-${i}`} style={{ marginTop: 4, fontSize: "0.6rem", color: "#cbd5e1" }}>
                  • {(l.fecha || "").slice(0, 16).replace("T", " ")} — <b>{l.por}</b>:{" "}
                  {l.accion_conflicto ? `conflicto → ${l.accion_conflicto}` : `"${l.estado_anterior}" → "${l.estado_nuevo}"`}
                </div>
              ))}
            </div>
          </>)}
        </div>
      )}

      {preview && (
        <div data-testid="super-preview-modal" onClick={() => { URL.revokeObjectURL(preview.url); setPreview(null); }}
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)", zIndex: 800, display: "flex", alignItems: "center", justifyContent: "center", padding: "2vh 2vw" }}>
          <div onClick={e => e.stopPropagation()} style={{ background: "#111214", border: "1.5px solid #d4af37", borderRadius: 12, width: "min(960px,96vw)", height: "92vh", display: "flex", flexDirection: "column" }}>
            <div style={{ display: "flex", alignItems: "center", padding: "0.6rem 1rem", gap: 10 }}>
              <b style={{ color: "#d4af37", fontSize: "0.8rem" }}>📄 {preview.cliente}</b>
              <span style={{ color: "#94a3b8", fontSize: "0.66rem" }}>{preview.archivo}</span>
              <button onClick={() => { URL.revokeObjectURL(preview.url); setPreview(null); }}
                style={{ marginLeft: "auto", background: "transparent", border: "1px solid rgba(255,255,255,0.25)", color: "#e2e8f0", borderRadius: 8, padding: "0.25rem 0.7rem", cursor: "pointer" }}>✕ Cerrar</button>
            </div>
            <iframe title="preview" src={preview.url} style={{ flex: 1, border: "none", borderRadius: "0 0 12px 12px", background: "#fff" }} />
          </div>
        </div>
      )}
    </div>
  );
}
