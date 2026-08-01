import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

const card = { background: "rgba(15,23,42,0.6)", padding: "1.5rem", borderRadius: "14px", border: "1px solid rgba(255,255,255,0.08)", marginBottom: "1.5rem" };
const inp = { background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: "8px", padding: "0.55rem 0.8rem", color: "#fff", fontSize: "0.9rem", width: "100%" };
const btn = (bg, small) => ({ background: bg, color: bg === "var(--gold)" ? "#0a0e17" : "#fff", border: "none", borderRadius: "8px", padding: small ? "0.4rem 0.8rem" : "0.6rem 1.2rem", fontWeight: 700, cursor: "pointer", fontSize: small ? "0.8rem" : "0.9rem" });
const lbl = { display: "block", fontSize: "0.75rem", opacity: 0.6, marginBottom: "0.3rem", textTransform: "uppercase", letterSpacing: "0.5px" };

export default function GastosOperacionalesModule({ onNavigate }) {
  const [q, setQ] = useState("");
  const [resultados, setResultados] = useState([]);
  const [nombre, setNombre] = useState("");
  const [rut, setRut] = useState("");
  const [emailCliente, setEmailCliente] = useState("");
  const [intro, setIntro] = useState("");
  const [items, setItems] = useState([]);
  const [datosPago, setDatosPago] = useState({});
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");
  const [log, setLog] = useState([]);

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

  const elegir = (r) => {
    setNombre(r.nombre); setRut(r.rut); if (r.email) setEmailCliente(r.email);
    setResultados([]); setQ("");
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
    nombre, rut, email_cliente: emailCliente, intro,
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
    if (!window.confirm(`¿Enviar los gastos operacionales a ${emailCliente}?`)) return;
    setLoading(true); setMsg("");
    try {
      const r = await axios.post(`${API}/api/gastos-operacionales/enviar`, { ...payload(), confirm: true });
      setMsg(`✅ Enviado a ${r.data.to} desde ${r.data.sender} (Total ${r.data.total} UF)`);
      setPreview(null);
      loadDefaults();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setLoading(false);
  };

  const guardarPlantilla = async () => {
    await axios.patch(`${API}/api/gastos-operacionales/defaults`, { intro, items: payload().items, datos_pago: datosPago });
    setMsg("✅ Plantilla guardada como predeterminada");
  };

  return (
    <div style={{ padding: "1.5rem", color: "var(--white)", maxWidth: "1000px" }} data-testid="gastos-module">
      {onNavigate && (
        <button data-testid="gastos-volver" onClick={() => onNavigate("clientes")} style={{ marginBottom: "1rem", background: "transparent", border: "1px solid rgba(212,175,55,0.5)", color: "var(--gold)", borderRadius: 8, padding: "0.45rem 1rem", fontWeight: 700, cursor: "pointer" }}>
          <i className="fa fa-arrow-left" /> Volver a Carpeta Clientes
        </button>
      )}
      {msg && <div data-testid="gastos-msg" style={{ padding: "0.7rem 1rem", borderRadius: "8px", marginBottom: "1rem", background: msg.startsWith("✅") ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)", color: msg.startsWith("✅") ? "#22c55e" : "#ef4444", fontWeight: 600 }}>{msg}</div>}

      {/* BUSCADOR */}
      <div style={card}>
        <h3 style={{ margin: "0 0 1rem", color: "var(--gold)", fontSize: "1.1rem" }}><i className="fa fa-search" style={{ marginRight: "0.5rem" }} />Buscar cliente (nombre o RUT)</h3>
        <div style={{ position: "relative" }}>
          <input data-testid="gastos-buscar" style={inp} placeholder="Ej: Franco Bahamondes o 18.312.893-0" value={q} onChange={e => setQ(e.target.value)} />
          {resultados.length > 0 && (
            <div style={{ position: "absolute", top: "110%", left: 0, right: 0, background: "#1a1f2e", border: "1px solid rgba(255,255,255,0.15)", borderRadius: "8px", zIndex: 20, overflow: "hidden" }}>
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
          <div><label style={lbl}>RUT</label><input data-testid="gastos-rut" style={inp} value={rut} onChange={e => setRut(e.target.value)} /></div>
          <div><label style={lbl}>Correo del cliente</label><input data-testid="gastos-email" style={inp} value={emailCliente} onChange={e => setEmailCliente(e.target.value)} placeholder="cliente@correo.cl" /></div>
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
              <td colSpan={2} />
            </tr>
          </tbody>
        </table>
        <button data-testid="gastos-add-item" onClick={addItem} style={{ ...btn("rgba(255,255,255,0.1)", true), marginTop: "0.6rem" }}><i className="fa fa-plus" style={{ marginRight: "0.4rem" }} />Agregar ítem</button>
      </div>

      {/* DATOS DE PAGO */}
      <div style={card}>
        <h3 style={{ margin: "0 0 1rem", color: "var(--gold)", fontSize: "1.1rem" }}><i className="fa fa-university" style={{ marginRight: "0.5rem" }} />Datos para el Pago (editable)</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "1rem" }}>
          {[["nombre", "Nombre"], ["rut", "RUT"], ["banco", "Banco"], ["tipo_cuenta", "Tipo de cuenta"], ["numero_cuenta", "N° de cuenta"]].map(([k, label]) => (
            <div key={k}><label style={lbl}>{label}</label>
              <input data-testid={`gastos-pago-${k}`} style={inp} value={datosPago[k] || ""} onChange={e => setDatosPago(prev => ({ ...prev, [k]: e.target.value }))} />
            </div>
          ))}
        </div>
      </div>

      {/* ACCIONES */}
      <div style={{ display: "flex", gap: "0.8rem", flexWrap: "wrap", marginBottom: "1.5rem" }}>
        <button data-testid="gastos-preview-btn" onClick={verPreview} disabled={loading} style={btn("#3b82f6")}><i className="fa fa-eye" style={{ marginRight: "0.4rem" }} />Vista previa</button>
        <button data-testid="gastos-enviar-btn" onClick={enviar} disabled={loading || !emailCliente} style={btn("var(--gold)")}><i className="fa fa-paper-plane" style={{ marginRight: "0.4rem" }} />Enviar al cliente</button>
        <button data-testid="gastos-guardar-plantilla" onClick={guardarPlantilla} disabled={loading} style={btn("rgba(255,255,255,0.12)")}><i className="fa fa-save" style={{ marginRight: "0.4rem" }} />Guardar como plantilla</button>
      </div>

      {/* HISTORIAL */}
      {log.length > 0 && (
        <div style={card} data-testid="gastos-log">
          <h3 style={{ margin: "0 0 0.8rem", color: "var(--gold)", fontSize: "1rem" }}><i className="fa fa-history" style={{ marginRight: "0.5rem" }} />Últimos envíos</h3>
          {log.map((l, i) => (
            <div key={i} style={{ fontSize: "0.85rem", opacity: 0.85, padding: "0.3rem 0", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
              {String(l.enviado_en || "").slice(0, 16).replace("T", " ")} — <b>{l.nombre}</b> ({l.rut}) → {l.to} · {l.total} UF
            </div>
          ))}
        </div>
      )}

      {/* MODAL PREVIEW */}
      {preview && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center", padding: "2rem" }} onClick={() => setPreview(null)}>
          <div style={{ background: "#fff", borderRadius: "12px", maxWidth: "720px", width: "100%", maxHeight: "88vh", overflow: "auto" }} onClick={e => e.stopPropagation()} data-testid="gastos-preview-modal">
            <div style={{ padding: "0.8rem 1.2rem", background: "#1a1f2e", display: "flex", justifyContent: "space-between", alignItems: "center", position: "sticky", top: 0 }}>
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
