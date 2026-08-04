import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import ImportarCorreo from "../components/ImportarCorreo";
import { EmailAutocomplete } from "../components/EmailAutocomplete";
import { estiloConfianza, PanelAprendizaje, useAprendizaje } from "../components/CampoAprendizaje";

const API = process.env.REACT_APP_BACKEND_URL;

const card = { background: "rgba(15,23,42,0.6)", padding: "1.5rem", borderRadius: "4px", border: "1px solid rgba(212,175,55,0.2)", marginBottom: "1.5rem" };
const inp = { background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: "4px", padding: "0.55rem 0.8rem", color: "#fff", fontSize: "0.9rem", width: "100%" };
const btn = (bg, small) => ({ background: bg, color: bg === "var(--gold)" ? "#0a0e17" : "#fff", border: "none", borderRadius: "4px", padding: small ? "0.4rem 0.8rem" : "0.6rem 1.2rem", fontWeight: 700, cursor: "pointer", fontSize: small ? "0.8rem" : "0.9rem" });
const lbl = { display: "block", fontSize: "0.75rem", opacity: 0.6, marginBottom: "0.3rem", textTransform: "uppercase", letterSpacing: "0.5px" };

export default function GastosOperacionalesModule({ onNavigate }) {
  const [q, setQ] = useState("");
  const [resultados, setResultados] = useState([]);
  const [nombre, setNombre] = useState("");
  const [rut, setRut] = useState("");
  const [emailCliente, setEmailCliente] = useState("");
  const [emailsExtra, setEmailsExtra] = useState("");
  const [intro, setIntro] = useState("");
  const [items, setItems] = useState([]);
  const [datosPago, setDatosPago] = useState({});
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");
  const [log, setLog] = useState([]);
  const [cobros, setCobros] = useState({ cobros: [], monto_uf: 4.5, valor_uf: 0, monto_clp: "" });
  const [cobroEmail, setCobroEmail] = useState("");
  const [cobroCliente, setCobroCliente] = useState("");
  const [cobroLoading, setCobroLoading] = useState(false);
  const [historial, setHistorial] = useState([]);
  const [plantillas, setPlantillas] = useState([]);
  const [iaLoading, setIaLoading] = useState(false);

  const [pagoInputs, setPagoInputs] = useState({});
  const [pagoLoading, setPagoLoading] = useState(false);

  const setPagoInput = (id, campo, valor) => setPagoInputs(prev => ({ ...prev, [id]: { ...(prev[id] || {}), [campo]: valor } }));

  const registrarPago = async (l) => {
    const pi = pagoInputs[l.id] || {};
    if (!pi.monto || parseFloat(pi.monto) <= 0) { setMsg("Ingresá el monto pagado (UF)."); return; }
    setPagoLoading(true);
    try {
      const r = await axios.post(`${API}/api/gastos-operacionales/log/${l.id}/pago`, {
        monto: parseFloat(pi.monto), fecha: pi.fecha || undefined, origen: "manual",
      });
      setMsg(`✅ Pago registrado a ${l.nombre}: ${pi.monto} UF — Saldo pendiente: ${r.data.saldo} UF`);
      setPagoInputs(prev => ({ ...prev, [l.id]: {} }));
      loadDefaults();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setPagoLoading(false);
  };

  const eliminarPago = async (l, idx) => {
    if (!window.confirm("¿Eliminar este pago registrado?")) return;
    try {
      await axios.delete(`${API}/api/gastos-operacionales/log/${l.id}/pago/${idx}`);
      loadDefaults();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
  };

  const scanPagos = async () => {
    setPagoLoading(true); setMsg("");
    try {
      const r = await axios.post(`${API}/api/gastos-operacionales/pagos/scan`, {}, { timeout: 120000 });
      setMsg(r.data.detectados > 0
        ? `✅ ${r.data.detectados} transferencia(s) detectada(s) y registrada(s): ${r.data.detalle.map(d => d.cliente).join(", ")}`
        : `✅ Correo revisado: sin transferencias nuevas que coincidan con clientes con saldo pendiente. ${r.data.mensaje || ""}`);
      loadDefaults();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setPagoLoading(false);
  };

  const leerConIA = async () => {
    if (!nombre || nombre.trim().length < 3) { setMsg("Primero seleccioná o escribí el nombre del cliente."); return; }
    setIaLoading(true); setMsg("");
    try {
      const r = await axios.get(`${API}/api/gastos-operacionales/prefill`, { params: { nombre }, timeout: 180000 });
      const p = r.data.prefill || {};
      if (p.email_cliente && !emailCliente) setEmailCliente(p.email_cliente);
      if (p.rut && !rut) setRut(p.rut);
      if (Array.isArray(p.items) && p.items.length > 0 &&
          window.confirm(`La IA encontró ${p.items.length} gasto(s) detallados en los documentos del cliente. ¿Reemplazar los ítems actuales con esos valores?`)) {
        setItems(p.items.map(i => ({ concepto: i.concepto, valor: i.valor ?? "", texto: "" })));
      }
      const hallazgos = [p.email_cliente ? "correo ✓" : "", p.rut ? "RUT ✓" : "", (p.items || []).length ? `${p.items.length} gastos ✓` : ""].filter(Boolean).join(" · ");
      setMsg(`✅ Lectura IA (${r.data.fuentes} fuente(s)): ${hallazgos || "no se encontraron datos nuevos — no se inventa nada"}`);
    } catch (e) { setMsg("Error IA: " + (e.response?.data?.detail || e.message)); }
    setIaLoading(false);
  };

  const loadPlantillas = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/plantillas?tipo=gastos`);
      setPlantillas(r.data.plantillas || []);
    } catch (_e) { /* noop */ }
  }, []);

  useEffect(() => { loadPlantillas(); }, [loadPlantillas]);

  const guardarPlantilla = async () => {
    const nombre = window.prompt("Nombre de la plantilla (ej: Gastos estándar vivienda usada):");
    if (!nombre) return;
    try {
      await axios.post(`${API}/api/plantillas`, { tipo: "gastos", nombre, data: { intro, items, datos_pago: datosPago } });
      setMsg(`✅ Plantilla "${nombre}" guardada.`);
      loadPlantillas();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
  };

  const aplicarPlantilla = (pid) => {
    const p = plantillas.find(x => x.id === pid);
    if (!p) return;
    if (p.data.intro !== undefined) setIntro(p.data.intro);
    if (p.data.items) setItems(p.data.items);
    if (p.data.datos_pago) setDatosPago(p.data.datos_pago);
    setMsg(`📋 Plantilla "${p.nombre}" aplicada.`);
  };

  const eliminarPlantilla = async (pid) => {
    const p = plantillas.find(x => x.id === pid);
    if (!p || !window.confirm(`¿Eliminar la plantilla "${p.nombre}"?`)) return;
    try {
      await axios.delete(`${API}/api/plantillas/${pid}`);
      loadPlantillas();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
  };

  const loadHistorial = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/gastos-operacionales/cobros-tasacion/historial`);
      setHistorial(r.data.historial || []);
    } catch (_e) { /* noop */ }
  }, []);

  useEffect(() => { loadHistorial(); }, [loadHistorial]);

  const loadCobros = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/gastos-operacionales/cobros-tasacion`);
      setCobros(r.data);
    } catch (_e) { /* noop */ }
  }, []);

  useEffect(() => { loadCobros(); }, [loadCobros]);

  const enviarCobroManual = async () => {
    if (!window.confirm(`¿Enviar la solicitud de datos + cobro de tasación (${cobros.monto_uf} UF ≈ ${cobros.monto_clp}) a ${cobroEmail}? (sin copia a nadie)`)) return;
    setCobroLoading(true);
    try {
      await axios.post(`${API}/api/gastos-operacionales/cobros-tasacion/manual`, { email: cobroEmail, cliente: cobroCliente, confirm: true });
      setMsg(`✅ Solicitud de datos y cobro de tasación enviada a ${cobroEmail}`);
      setCobroEmail(""); setCobroCliente("");
      loadCobros();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setCobroLoading(false);
  };

  const scanCobros = async () => {
    setCobroLoading(true);
    try {
      const r = await axios.post(`${API}/api/gastos-operacionales/cobros-tasacion/scan`);
      setMsg(r.data.nuevos ? `✅ ${r.data.nuevos} solicitud(es) de tasación detectadas y respondidas con el cobro.` : "✅ Correo revisado: sin solicitudes de tasación nuevas.");
      loadCobros();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setCobroLoading(false);
  };

  const marcarPagado = async (c) => {
    try {
      await axios.post(`${API}/api/gastos-operacionales/cobros-tasacion/${c.id}/pagado`, { pagado: !c.pagado });
      loadCobros();
      loadHistorial();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
  };

  const loadDefaults = useCallback(async () => {
    const [d, l] = await Promise.all([
      axios.get(`${API}/api/gastos-operacionales/defaults`),
      axios.get(`${API}/api/gastos-operacionales/log`).catch(() => ({ data: { log: [] } })),
    ]);
    setIntro(d.data.intro || "");
    setItems(d.data.items || []);
    setDatosPago(d.data.datos_pago || {});
    setLog(l.data.log || []);
  }, []);

  useEffect(() => { loadDefaults(); }, [loadDefaults]);

  useEffect(() => {
    if (q.trim().length < 2) { setResultados([]); return; }
    const t = setTimeout(async () => {
      try {
        const r = await axios.get(`${API}/api/gastos-operacionales/buscar-cliente`, { params: { q } });
        setResultados(r.data.resultados || []);
      } catch (_e) { setResultados([]); }
    }, 400);
    return () => clearTimeout(t);
  }, [q]);

  const { confianza, autofill, guardarAprender } = useAprendizaje();

  const autofillDatos = async (cliente, emailActual) => {
    try {
      const d = await autofill(cliente);
      if (!emailActual && d.email) setEmailCliente(prev => prev || d.email);
      if (d.rut) setRut(prev => prev || d.rut);
    } catch (_e) { /* el usuario puede escribirlo a mano */ }
  };

  const aprender = async () => {
    const n = await guardarAprender(nombre, [["email", emailCliente], ["rut", rut]]);
    setMsg(n > 0
      ? `🧠 ${n} corrección(es) guardada(s) como Patrón Aprendido: la próxima vez no se repetirá el error.`
      : "✅ Datos validados: no había cambios que aprender.");
  };

  const elegir = (r) => {
    setNombre(r.nombre); setRut(r.rut); if (r.email) setEmailCliente(r.email);
    setResultados([]); setQ("");
    autofillDatos(r.nombre, r.email || "");
  };

  useEffect(() => {
    const raw = sessionStorage.getItem("cm_prefill_cliente");
    if (!raw) return;
    sessionStorage.removeItem("cm_prefill_cliente");
    try {
      const p = JSON.parse(raw);
      axios.get(`${API}/api/gastos-operacionales/buscar-cliente`, { params: { q: p.nombre } })
        .then(r => {
          const res = (r.data.resultados || [])[0];
          const el = res || { nombre: p.nombre, rut: p.rut || "", email: "" };
          setNombre(el.nombre); setRut(el.rut || ""); if (el.email) setEmailCliente(el.email);
          autofillDatos(el.nombre, el.email || "");
        })
        .catch(() => { setNombre(p.nombre); setRut(p.rut || ""); });
    } catch (_e) { /* prefill inválido */ }
  }, []);

  const total = items.reduce((s, it) => {
    const v = parseFloat(it.valor);
    return s + (isNaN(v) ? 0 : v);
  }, 0);

  const setItem = (i, campo, valor) => setItems(prev => prev.map((it, j) => j === i ? { ...it, [campo]: valor } : it));
  const delItem = (i) => setItems(prev => prev.filter((_, j) => j !== i));
  const addItem = () => setItems(prev => [...prev, { concepto: "", valor: 0, texto: "" }]);

  const payload = () => ({
    nombre, rut, email_cliente: emailCliente, emails_extra: emailsExtra, intro,
    items: items.map(it => ({ ...it, valor: it.valor === "" || it.valor === null ? null : parseFloat(it.valor) })),
    datos_pago: datosPago,
  });

  const verPreview = async () => {
    setLoading(true); setMsg("");
    try {
      const r = await axios.post(`${API}/api/gastos-operacionales/enviar`, { ...payload(), confirm: false });
      setPreview(r.data);
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setLoading(false);
  };

  const enviar = async () => {
    const extrasTxt = emailsExtra.trim() ? ` (+ copias: ${emailsExtra.trim()})` : "";
    if (!window.confirm(`¿Enviar los gastos operacionales a ${emailCliente}${extrasTxt}?`)) return;
    setLoading(true); setMsg("");
    try {
      const r = await axios.post(`${API}/api/gastos-operacionales/enviar`, { ...payload(), confirm: true });
      setMsg(`✅ Enviado a ${r.data.to} desde ${r.data.sender} (Total ${r.data.total} UF)`);
      setPreview(null);
      loadDefaults();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setLoading(false);
  };

  const guardarPredeterminada = async () => {
    await axios.patch(`${API}/api/gastos-operacionales/defaults`, { intro, items: payload().items, datos_pago: datosPago });
    setMsg("✅ Plantilla guardada como predeterminada");
  };

  return (
    <div style={{ padding: "1.5rem", color: "var(--white)", maxWidth: "1000px" }} data-testid="gastos-module">
      {onNavigate && (
        <button data-testid="gastos-volver" onClick={() => onNavigate("clientes")} style={{ marginBottom: "1rem", background: "transparent", border: "1px solid rgba(212,175,55,0.5)", color: "var(--gold)", borderRadius: 4, padding: "0.45rem 1rem", fontWeight: 700, cursor: "pointer" }}>
          <i className="fa fa-arrow-left" /> Volver a Carpeta Clientes
        </button>
      )}
      {msg && <div data-testid="gastos-msg" style={{ padding: "0.7rem 1rem", borderRadius: "4px", marginBottom: "1rem", background: msg.startsWith("✅") ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)", color: msg.startsWith("✅") ? "#22c55e" : "#ef4444", fontWeight: 600 }}>{msg}</div>}

      {/* BUSCADOR */}
      <div style={card}>
        <h3 style={{ margin: "0 0 1rem", color: "var(--gold)", fontSize: "1.1rem" }}><i className="fa fa-search" style={{ marginRight: "0.5rem" }} />Buscar cliente (nombre o RUT)</h3>
        <div style={{ position: "relative" }}>
          <input data-testid="gastos-buscar" style={inp} placeholder="Ej: Franco Bahamondes o 18.312.893-0" value={q} onChange={e => setQ(e.target.value)} />
          {resultados.length > 0 && (
            <div style={{ position: "absolute", top: "110%", left: 0, right: 0, background: "rgba(15,23,42,0.9)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: "4px", zIndex: 20, overflow: "hidden" }}>
              {resultados.map((r, i) => (
                <div key={i} data-testid={`gastos-resultado-${i}`} onClick={() => elegir(r)} style={{ padding: "0.6rem 1rem", cursor: "pointer", borderBottom: "1px solid rgba(255,255,255,0.05)" }}
                     onMouseEnter={e => e.currentTarget.style.background = "rgba(212,175,55,0.1)"} onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                  <b>{r.nombre}</b> <span style={{ opacity: 0.6 }}>{r.rut}</span> {r.email && <span style={{ color: "#22c55e", fontSize: "0.8rem" }}> · {r.email}</span>}
                </div>
              ))}
            </div>
          )}
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 2fr", gap: "1rem", marginTop: "1rem" }}>
          <div><label style={lbl}>Nombre del cliente</label><input data-testid="gastos-nombre" style={inp} value={nombre} onChange={e => setNombre(e.target.value)} /></div>
          <div><label style={lbl}>RUT</label><input data-testid="gastos-rut" style={{ ...inp, ...estiloConfianza(confianza, "rut") }} value={rut} onChange={e => setRut(e.target.value)} /></div>
          <div><label style={lbl}>Correo del cliente</label><EmailAutocomplete dataTestId="gastos-email" style={{ ...inp, ...estiloConfianza(confianza, "email") }} value={emailCliente} onChange={setEmailCliente} placeholder="cliente@correo.cl" /></div>
        </div>
        <PanelAprendizaje confianza={confianza} onGuardar={aprender} testId="gastos-guardar-aprender" />
        <div style={{ marginTop: "0.9rem" }}>
          <label style={lbl}>Destinatarios adicionales (opcional, separados por coma)</label>
          <input data-testid="gastos-emails-extra" style={inp} value={emailsExtra} onChange={e => setEmailsExtra(e.target.value)} placeholder="ejecutivo@inmobiliaria.cl, broker@correo.cl" />
        </div>
        <div style={{ display: "flex", gap: "0.7rem", flexWrap: "wrap", marginTop: "0.8rem", alignItems: "center" }}>
          <button data-testid="gastos-leer-ia" onClick={leerConIA} disabled={iaLoading || !nombre}
            title="Lee con IA los correos (asunto y cuerpo) y documentos del cliente para completar correo, RUT y gastos. Prohibido inventar: solo llena lo que aparece."
            style={btn("#8b5cf6", true)}>
            <i className={`fa ${iaLoading ? "fa-spinner fa-spin" : "fa-magic"}`} style={{ marginRight: "0.4rem" }} />
            {iaLoading ? "Leyendo correos y documentos…" : "🤖 Leer datos con IA (correos + documentos)"}
          </button>
          <ImportarCorreo destino="carpeta" nombre={nombre}
            label="Importar tasación / docs desde correo"
            onDone={() => setMsg("✅ Archivos importados a la carpeta del cliente — usá 🤖 Leer datos con IA para releerlos")} />
        </div>
      </div>

      {/* TEXTO + CUADRO */}
      <div style={card}>
        <h3 style={{ margin: "0 0 1rem", color: "var(--gold)", fontSize: "1.1rem" }}><i className="fa fa-table" style={{ marginRight: "0.5rem" }} />Detalle de Gastos Operacionales</h3>
        <label style={lbl}>Texto de introducción (editable)</label>
        <textarea data-testid="gastos-intro" style={{ ...inp, minHeight: "90px", resize: "vertical", marginBottom: "1rem" }} value={intro} onChange={e => setIntro(e.target.value)} />
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }} data-testid="gastos-tabla">
          <thead>
            <tr style={{ color: "var(--gold)", borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
              <th style={{ textAlign: "left", padding: "0.5rem" }}>Concepto</th>
              <th style={{ textAlign: "right", padding: "0.5rem", width: "130px" }}>Valor UF</th>
              <th style={{ textAlign: "left", padding: "0.5rem", width: "230px" }}>Texto alternativo (sin monto)</th>
              <th style={{ width: "40px" }} />
            </tr>
          </thead>
          <tbody>
            {items.map((it, i) => (
              <tr key={i} style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                <td style={{ padding: "0.35rem" }}><input data-testid={`gastos-concepto-${i}`} style={inp} value={it.concepto} onChange={e => setItem(i, "concepto", e.target.value)} /></td>
                <td style={{ padding: "0.35rem" }}><input data-testid={`gastos-valor-${i}`} type="number" step="0.1" style={{ ...inp, textAlign: "right" }} value={it.valor ?? ""} onChange={e => setItem(i, "valor", e.target.value)} placeholder="—" /></td>
                <td style={{ padding: "0.35rem" }}><input data-testid={`gastos-texto-${i}`} style={inp} value={it.texto || ""} onChange={e => setItem(i, "texto", e.target.value)} placeholder="Ej: Pagada" /></td>
                <td style={{ textAlign: "center" }}><button data-testid={`gastos-del-${i}`} onClick={() => delItem(i)} style={{ background: "none", border: "none", color: "#ef4444", cursor: "pointer" }}><i className="fa fa-trash" /></button></td>
              </tr>
            ))}
            <tr style={{ background: "rgba(212,175,55,0.08)" }}>
              <td style={{ padding: "0.7rem", fontWeight: 700, color: "var(--gold)" }}>TOTAL (autosuma)</td>
              <td data-testid="gastos-total" style={{ padding: "0.7rem", textAlign: "right", fontWeight: 700, color: "var(--gold)", fontSize: "1.05rem" }}>{total.toLocaleString("es-CL", { maximumFractionDigits: 2 })} UF</td>
              <td colSpan={2} style={{ padding: "0.7rem", fontSize: "0.85rem", color: "#4ade80", fontWeight: 700, whiteSpace: "nowrap" }} data-testid="gastos-total-clp">
                {Number(cobros.valor_uf || 0) > 0
                  ? `≈ $${Math.round(total * Number(cobros.valor_uf)).toLocaleString("es-CL")} CLP (UF hoy $${Number(cobros.valor_uf).toLocaleString("es-CL")})`
                  : ""}
              </td>
            </tr>
          </tbody>
        </table>
        <button data-testid="gastos-add-item" onClick={addItem} style={{ ...btn("rgba(255,255,255,0.1)", true), marginTop: "0.6rem" }}><i className="fa fa-plus" style={{ marginRight: "0.4rem" }} />Agregar ítem</button>
      </div>

      {/* DATOS DE PAGO */}
      <div style={card}>
        <h3 style={{ margin: "0 0 1rem", color: "var(--gold)", fontSize: "1.1rem" }}><i className="fa fa-university" style={{ marginRight: "0.5rem" }} />Cuenta Recaudadora (editable)</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "1rem" }}>
          {[["nombre", "Nombre"], ["rut", "RUT"], ["banco", "Banco"], ["tipo_cuenta", "Tipo de cuenta"], ["numero_cuenta", "N° de cuenta"], ["email", "Correo"]].map(([k, label]) => (
            <div key={k}><label style={lbl}>{label}</label>
              <input data-testid={`gastos-pago-${k}`} style={inp} value={datosPago[k] || ""} onChange={e => setDatosPago(prev => ({ ...prev, [k]: e.target.value }))} />
            </div>
          ))}
        </div>
      </div>

      {/* ACCIONES */}
      <div style={{ display: "flex", gap: "0.8rem", flexWrap: "wrap", marginBottom: "1.5rem", alignItems: "center" }}>
        <button data-testid="gastos-preview-btn" onClick={verPreview} disabled={loading} style={btn("#d4af37")}><i className="fa fa-eye" style={{ marginRight: "0.4rem" }} />Vista previa</button>
        <button data-testid="gastos-enviar-btn" onClick={enviar} disabled={loading || !emailCliente} style={btn("var(--gold)")}><i className="fa fa-paper-plane" style={{ marginRight: "0.4rem" }} />Enviar al cliente</button>
        <button data-testid="gastos-guardar-plantilla" onClick={guardarPlantilla} disabled={loading} style={btn("rgba(255,255,255,0.12)")}><i className="fa fa-save" style={{ marginRight: "0.4rem" }} />Guardar como plantilla</button>
        <button data-testid="gastos-guardar-predeterminada" onClick={guardarPredeterminada} disabled={loading} style={btn("rgba(212,175,55,0.2)")}><i className="fa fa-star" style={{ marginRight: "0.4rem" }} />Guardar como predeterminada</button>
        {plantillas.length > 0 && (
          <>
            <select data-testid="gastos-plantilla-select" onChange={e => { if (e.target.value) aplicarPlantilla(e.target.value); e.target.value = ""; }} defaultValue=""
              style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(212,175,55,0.4)", color: "#e2e8f0", borderRadius: 4, padding: "0.55rem 0.8rem", fontSize: "0.85rem" }}>
              <option value="">📋 Aplicar plantilla…</option>
              {plantillas.map(p => <option key={p.id} value={p.id} style={{ color: "#111" }}>{p.nombre}</option>)}
            </select>
            <select data-testid="gastos-plantilla-eliminar" onChange={e => { if (e.target.value) eliminarPlantilla(e.target.value); e.target.value = ""; }} defaultValue=""
              style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(239,68,68,0.35)", color: "#f87171", borderRadius: 4, padding: "0.55rem 0.8rem", fontSize: "0.85rem" }}>
              <option value="">🗑 Eliminar plantilla…</option>
              {plantillas.map(p => <option key={p.id} value={p.id} style={{ color: "#111" }}>{p.nombre}</option>)}
            </select>
          </>
        )}
      </div>

      {/* COBRO DE TASACIÓN — VIVIENDA USADA */}
      <div style={card} data-testid="cobro-tasacion-card">
        <h3 style={{ margin: "0 0 0.4rem", color: "var(--gold)", fontSize: "1.1rem" }}>
          <i className="fa fa-home" style={{ marginRight: "0.5rem" }} />Cobro de Tasación — Vivienda Usada
        </h3>
        <div style={{ fontSize: "0.85rem", opacity: 0.8, marginBottom: "1rem" }}>
          <b style={{ color: "var(--gold)" }}>{cobros.monto_uf} UF ≈ {cobros.monto_clp}</b> (UF hoy: ${Number(cobros.valor_uf || 0).toLocaleString("es-CL")}).
          🤖 Detección automática activa: cuando llega una solicitud de tasación de vivienda usada (brokers, vendedores — no inmobiliarias),
          se responde de inmediato en el mismo hilo pidiendo los datos + voucher de pago a la Cuenta Recaudadora. <b>Se envía solo al solicitante, sin copia a nadie.</b>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "2fr 2fr auto auto", gap: "0.7rem", alignItems: "end", marginBottom: "1rem" }}>
          <div><label style={lbl}>Correo del solicitante (broker/vendedor)</label>
            <input data-testid="cobro-email" style={inp} value={cobroEmail} onChange={e => setCobroEmail(e.target.value)} placeholder="broker@correo.cl" /></div>
          <div><label style={lbl}>Cliente (opcional)</label>
            <input data-testid="cobro-cliente" style={inp} value={cobroCliente} onChange={e => setCobroCliente(e.target.value)} placeholder="Nombre del comprador" /></div>
          <button data-testid="cobro-enviar-manual" onClick={enviarCobroManual} disabled={cobroLoading || !cobroEmail.includes("@")} style={btn("var(--gold)")}>
            <i className={`fa ${cobroLoading ? "fa-spinner fa-spin" : "fa-paper-plane"}`} style={{ marginRight: "0.4rem" }} />Solicitar datos + cobro
          </button>
          <button data-testid="cobro-scan" onClick={scanCobros} disabled={cobroLoading} style={btn("rgba(212,175,55,0.8)")}>
            <i className={`fa ${cobroLoading ? "fa-spinner fa-spin" : "fa-refresh"}`} style={{ marginRight: "0.4rem" }} />Buscar solicitudes
          </button>
        </div>
        {cobros.cobros.length === 0 ? (
          <div style={{ fontSize: "0.85rem", opacity: 0.6, textAlign: "center", padding: "0.6rem" }} data-testid="cobros-vacio">
            Aún no hay cobros de tasación registrados.
          </div>
        ) : (
          <div style={{ display: "grid", gap: 6 }} data-testid="cobros-lista">
            {cobros.cobros.map((c) => (
              <div key={c.id} style={{ display: "flex", alignItems: "center", gap: 10, background: c.pagado ? "rgba(34,197,94,0.08)" : "rgba(255,255,255,0.04)", border: `1px solid ${c.pagado ? "rgba(34,197,94,0.35)" : "rgba(255,255,255,0.1)"}`, borderRadius: 4, padding: "0.55rem 0.9rem", fontSize: "0.85rem" }}>
                <div style={{ flex: 1 }}>
                  <b>{c.cliente || c.subject || c.from_email}</b>
                  <span style={{ opacity: 0.6 }}> · {c.from_email}</span>
                  <div style={{ fontSize: "0.75rem", opacity: 0.6 }}>
                    {String(c.detectado_en || "").slice(0, 16).replace("T", " ")} · {c.origen === "manual" ? "envío manual" : "detectado automático"}
                    {c.respondido_at ? " · solicitud de datos + cobro enviada ✓" : (c.envio_error ? ` · ⚠️ ${c.envio_error}` : "")}
                    {c.monto_clp ? ` · ${c.monto_uf} UF ≈ ${c.monto_clp}` : ""}
                  </div>
                </div>
                <button data-testid={`cobro-pagado-${c.id}`} onClick={() => marcarPagado(c)}
                  style={{ ...btn(c.pagado ? "rgba(34,197,94,0.85)" : "rgba(255,255,255,0.12)", true), whiteSpace: "nowrap" }}>
                  <i className={`fa ${c.pagado ? "fa-check-circle" : "fa-money"}`} style={{ marginRight: "0.3rem" }} />
                  {c.pagado ? `Tasación pagada ✓ ${String(c.pagado_at || "").slice(0, 10)}` : "Tasación pagada"}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* HISTORIAL MENSUAL DE TASACIONES PAGADAS */}
      {historial.length > 0 && (
        <div style={card} data-testid="historial-pagos-card">
          <h3 style={{ margin: "0 0 0.8rem", color: "var(--gold)", fontSize: "1.05rem" }}>
            <i className="fa fa-calendar-check-o" style={{ marginRight: "0.5rem" }} />Historial Mensual — Tasaciones Pagadas
          </h3>
          {historial.map((h) => (
            <div key={h.mes} data-testid={`historial-mes-${h.mes}`} style={{ marginBottom: "0.9rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "0.5rem 0.9rem", background: "rgba(212,175,55,0.08)", border: "1px solid rgba(212,175,55,0.25)", borderRadius: 4, fontSize: "0.9rem" }}>
                <b style={{ color: "var(--gold)" }}>{h.mes}</b>
                <span style={{ opacity: 0.8 }}>{h.cantidad} tasación(es) pagada(s)</span>
                <span style={{ marginLeft: "auto", fontWeight: 700, color: "#4ade80" }}>{h.total_uf.toLocaleString("es-CL")} UF · {h.total_clp}</span>
              </div>
              <div style={{ padding: "0.3rem 0.5rem" }}>
                {h.detalle.map((d, i) => (
                  <div key={i} style={{ display: "flex", gap: 8, fontSize: "0.8rem", opacity: 0.85, padding: "0.25rem 0.4rem", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                    <span style={{ flex: 1 }}><b>{d.cliente}</b> <span style={{ opacity: 0.6 }}>· {d.from_email}</span></span>
                    <span style={{ opacity: 0.7 }}>{String(d.pagado_at || "").slice(0, 10)}</span>
                    <span style={{ color: "#4ade80", fontWeight: 600 }}>{d.monto_clp}</span>
                    <span style={{ opacity: 0.5, fontSize: "0.72rem" }}>{d.origen_pago === "auto" ? "🤖 auto" : "manual"}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* HISTORIAL DE ENVÍOS + SEGUIMIENTO DE PAGOS */}
      {log.length > 0 && (
        <div style={card} data-testid="gastos-log">
          <div style={{ display: "flex", alignItems: "center", gap: "0.8rem", marginBottom: "0.8rem", flexWrap: "wrap" }}>
            <h3 style={{ margin: 0, color: "var(--gold)", fontSize: "1rem" }}><i className="fa fa-history" style={{ marginRight: "0.5rem" }} />Envíos y Seguimiento de Pagos</h3>
            <button data-testid="gastos-scan-pagos" onClick={scanPagos} disabled={pagoLoading} style={{ ...btn("rgba(212,175,55,0.8)", true), marginLeft: "auto" }}>
              <i className={`fa ${pagoLoading ? "fa-spinner fa-spin" : "fa-search-dollar fa-refresh"}`} style={{ marginRight: "0.4rem" }} />🤖 Buscar transferencias en el correo
            </button>
          </div>
          {log.map((l, i) => {
            const estado = l.estado_pago || "pendiente";
            const estadoColor = estado === "pagado" ? "#22c55e" : estado === "parcial" ? "#f59e0b" : "#ef4444";
            const pi = pagoInputs[l.id] || {};
            return (
              <div key={l.id || i} data-testid={`gastos-log-${i}`} style={{ border: "1px solid rgba(212,175,55,0.2)", borderRadius: 4, padding: "0.7rem 0.9rem", marginBottom: "0.6rem", background: estado === "pagado" ? "rgba(34,197,94,0.05)" : "rgba(255,255,255,0.02)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", fontSize: "0.87rem" }}>
                  <b>{l.nombre}</b>
                  <span style={{ opacity: 0.55 }}>{l.rut}</span>
                  <span style={{ opacity: 0.55 }}>{String(l.enviado_en || "").slice(0, 10)}</span>
                  <span data-testid={`gastos-log-estado-${i}`} style={{ marginLeft: "auto", color: estadoColor, border: `1px solid ${estadoColor}`, borderRadius: 20, padding: "0.1rem 0.7rem", fontSize: "0.72rem", fontWeight: 800, textTransform: "uppercase" }}>{estado}</span>
                </div>
                <div style={{ display: "flex", gap: "1.4rem", marginTop: "0.45rem", fontSize: "0.85rem", flexWrap: "wrap" }}>
                  <span>Total: <b style={{ color: "var(--gold)" }}>{Number(l.total || 0).toLocaleString("es-CL")} UF</b></span>
                  <span>Pagado: <b style={{ color: "#22c55e" }} data-testid={`gastos-log-pagado-${i}`}>{Number(l.pagado || 0).toLocaleString("es-CL")} UF</b></span>
                  <span>Saldo: <b style={{ color: Number(l.saldo) <= 0.01 ? "#22c55e" : "#ef4444" }} data-testid={`gastos-log-saldo-${i}`}>{Number(l.saldo ?? l.total ?? 0).toLocaleString("es-CL")} UF</b></span>
                </div>
                {(l.pagos || []).length > 0 && (
                  <div style={{ marginTop: "0.4rem" }}>
                    {l.pagos.map((p, j) => (
                      <div key={j} style={{ display: "flex", gap: 8, alignItems: "center", fontSize: "0.78rem", opacity: 0.85, padding: "0.15rem 0" }}>
                        <i className={`fa ${p.origen === "auto" ? "fa-magic" : "fa-money"}`} style={{ color: "#22c55e" }} />
                        <span>{p.fecha}</span>
                        <b>{Number(p.monto).toLocaleString("es-CL")} UF</b>
                        <span style={{ opacity: 0.6 }}>{p.origen === "auto" ? "🤖 transferencia detectada" : "manual"}{p.detalle ? ` · ${p.detalle.slice(0, 70)}` : ""}</span>
                        <button data-testid={`gastos-del-pago-${i}-${j}`} onClick={() => eliminarPago(l, j)} style={{ background: "none", border: "none", color: "#ef4444", cursor: "pointer", marginLeft: "auto" }}><i className="fa fa-trash" /></button>
                      </div>
                    ))}
                  </div>
                )}
                {Number(l.saldo ?? l.total ?? 0) > 0.01 && (
                  <div style={{ display: "flex", gap: "0.6rem", marginTop: "0.55rem", alignItems: "end", flexWrap: "wrap" }}>
                    <div><label style={{ ...lbl, marginBottom: "0.15rem" }}>Fecha de pago</label>
                      <input data-testid={`gastos-pago-fecha-${i}`} type="date" style={{ ...inp, width: 150, padding: "0.35rem 0.5rem" }} value={pi.fecha || ""} onChange={e => setPagoInput(l.id, "fecha", e.target.value)} /></div>
                    <div><label style={{ ...lbl, marginBottom: "0.15rem" }}>Monto pagado (UF)</label>
                      <input data-testid={`gastos-pago-monto-${i}`} type="number" step="0.1" style={{ ...inp, width: 130, padding: "0.35rem 0.5rem" }} placeholder="Ej: 10" value={pi.monto || ""} onChange={e => setPagoInput(l.id, "monto", e.target.value)} /></div>
                    <button data-testid={`gastos-registrar-pago-${i}`} onClick={() => registrarPago(l)} disabled={pagoLoading} style={btn("#22c55e", true)}>
                      <i className="fa fa-check" style={{ marginRight: "0.3rem" }} />Registrar pago
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* MODAL PREVIEW */}
      {preview && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center", padding: "2rem" }} onClick={() => setPreview(null)}>
          <div style={{ background: "#fff", borderRadius: "4px", maxWidth: "720px", width: "100%", maxHeight: "88vh", overflow: "auto" }} onClick={e => e.stopPropagation()} data-testid="gastos-preview-modal">
            <div style={{ padding: "0.8rem 1.2rem", background: "rgba(15,23,42,0.9)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", display: "flex", justifyContent: "space-between", alignItems: "center", position: "sticky", top: 0 }}>
              <span style={{ color: "var(--gold)", fontWeight: 700 }}>Vista previa — {preview.subject}</span>
              <div>
                <button data-testid="gastos-preview-enviar" onClick={enviar} disabled={loading || !emailCliente} style={{ ...btn("var(--gold)", true), marginRight: "0.6rem" }}>Enviar</button>
                <button onClick={() => setPreview(null)} style={btn("rgba(255,255,255,0.15)", true)}>Cerrar</button>
              </div>
            </div>
            <div dangerouslySetInnerHTML={{ __html: preview.body }} />
          </div>
        </div>
      )}
    </div>
  );
}
