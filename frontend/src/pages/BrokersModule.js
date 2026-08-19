import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import GestorFuentesIMAP from "../components/GestorFuentesIMAP";
import EstadoSalida from "../components/EstadoSalida";
import DocumentoViewer from "../components/DocumentoViewer";

const API = process.env.REACT_APP_BACKEND_URL;
const fdd = (iso) => (iso ? `${String(iso).slice(8, 10)}/${String(iso).slice(5, 7)}/${String(iso).slice(0, 4)} ${String(iso).slice(11, 16)}`.trim() : "");
const card = { background: "rgba(30,41,59,0.55)", border: "1px solid rgba(212,175,55,0.3)", borderRadius: 12, padding: "1.1rem", marginTop: 14 };
const inp = { background: "rgba(255,255,255,0.06)", border: "1px solid rgba(212,175,55,0.3)", color: "#fff", padding: "0.5rem 0.7rem", borderRadius: 8, fontSize: "0.78rem", boxSizing: "border-box" };
const goldBtn = { background: "linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C)", color: "#0a0a0a", border: "none", borderRadius: 8, padding: "0.5rem 1rem", fontWeight: 800, cursor: "pointer", fontSize: "0.75rem" };

// ── DOCUMENTOS EN LA NUBE (storage integrado) — visualización sin descarga ──
const NubeCarpeta = ({ fid }) => {
  const [abierto, setAbierto] = useState(false);
  const [docs, setDocs] = useState(null);
  const [visor, setVisor] = useState(null);
  const abrir = async () => {
    if (!abierto && docs === null) {
      try {
        const r = await axios.get(`${API}/api/storage/docs`, { params: { fid } });
        setDocs(r.data.documentos || []);
      } catch { setDocs([]); }
    }
    setAbierto(a => !a);
  };
  return (
    <div style={{ marginTop: 8 }}>
      <button data-testid={`nube-toggle-${fid}`} onClick={abrir}
        style={{ background: "rgba(96,165,250,0.12)", color: "#93c5fd", border: "1px solid rgba(96,165,250,0.4)",
          borderRadius: 7, padding: "0.25rem 0.7rem", cursor: "pointer", fontSize: "0.64rem", fontWeight: 800 }}>
        ☁️ {abierto ? "Ocultar documentos en la nube" : "Documentos en la nube"}</button>
      {abierto && (
        <div data-testid={`nube-docs-${fid}`} style={{ marginTop: 6, background: "rgba(15,23,42,0.6)", borderRadius: 8, padding: "0.5rem 0.7rem" }}>
          {(docs || []).length === 0 && <span style={{ color: "#64748b", fontSize: "0.62rem" }}>
            Sin documentos en el storage aún — los próximos archivos que suba quedarán respaldados aquí automáticamente.</span>}
          {(docs || []).map(d => (
            <div key={d.id} style={{ display: "flex", gap: 8, alignItems: "center", padding: "0.2rem 0", fontSize: "0.64rem" }}>
              <span style={{ color: "#e2e8f0" }}>📄 {d.nombre_archivo}</span>
              <span style={{ color: "#64748b" }}>{fdd(d.subido_en)}</span>
              <button data-testid={`nube-ver-${d.id}`} onClick={() => setVisor(d)}
                style={{ marginLeft: "auto", background: "none", border: "1px solid rgba(212,175,55,0.5)",
                  color: "#d4af37", borderRadius: 6, padding: "0.1rem 0.55rem", cursor: "pointer",
                  fontSize: "0.62rem", fontWeight: 800 }}>👁 Ver</button>
            </div>
          ))}
        </div>
      )}
      {visor && <DocumentoViewer doc={visor} onClose={() => setVisor(null)} />}
    </div>
  );
};

const CATEGORIAS = [
  ["set_credito", "Set de Crédito (PDF)"],
  ["carta_enmienda", "Carta Enmienda"],
  ["actualizacion", "Documento de Actualización"],
  ["otros", "Otros Documentos (descripción libre)"],
];

export default function BrokersModule({ user }) {
  const [data, setData] = useState(null);
  const [proys, setProys] = useState([]);
  const [situacion, setSituacion] = useState([]);
  const [actividad, setActividad] = useState([]);
  const [form, setForm] = useState({ nombre: "", rut: "" });
  const [files, setFiles] = useState([]);
  const [mes, setMes] = useState("");
  const [proyFile, setProyFile] = useState(null);
  const [carga, setCarga] = useState({ fid: "", categoria: "set_credito", descripcion: "", files: [] });
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const cargar = useCallback(() => {
    axios.get(`${API}/api/broker/carpetas`).then(r => setData(r.data)).catch(() => setData({ carpetas: [] }));
    axios.get(`${API}/api/broker/proyecciones`).then(r => setProys(r.data.proyecciones || [])).catch(() => {});
    axios.get(`${API}/api/broker/estado-situacion`).then(r => setSituacion(r.data.situacion || [])).catch(() => {});
    axios.get(`${API}/api/broker/actividad`).then(r => setActividad(r.data.actividad || [])).catch(() => {});
  }, []);
  useEffect(() => { cargar(); }, [cargar]);

  const cargaMasiva = async () => {
    if (!carga.fid || !carga.files.length) { setMsg("⛔ Elija la carpeta y los archivos a cargar"); return; }
    setBusy(true); setMsg("");
    let ok = 0, rech = 0;
    for (const f of carga.files) {
      const fd = new FormData();
      fd.append("categoria", carga.categoria);
      fd.append("descripcion", carga.descripcion);
      fd.append("archivo", f);
      try { await axios.post(`${API}/api/broker/carpetas/${carga.fid}/upload`, fd); ok++; }
      catch (e) { rech++; setMsg(`${e.response?.data?.detail || "⛔ Error"}`); }
    }
    if (!rech) setMsg(`✅ ${ok} archivo(s) cargados y auditados por DashAI (RUT verificado)`);
    else setMsg(m => `${m} · ${ok} aceptados, ${rech} rechazados por auditoría de RUT`);
    setCarga({ ...carga, files: [], descripcion: "" });
    setBusy(false);
    cargar();
  };

  const [ventana, setVentana] = useState(null);
  useEffect(() => {
    axios.get(`${API}/api/broker/ventana-proyeccion`).then(r => setVentana(r.data)).catch(() => {});
  }, []);

  const subirArchivo = async (fid, subcarpeta, archivo) => {
    const fd = new FormData();
    fd.append("subcarpeta", subcarpeta);
    fd.append("archivo", archivo);
    await axios.post(`${API}/api/broker/carpetas/${fid}/upload`, fd);
  };

  const crearCarpeta = async () => {
    setBusy(true); setMsg("");
    try {
      const r = await axios.post(`${API}/api/broker/carpetas`, form);
      for (const f of files) await subirArchivo(r.data.id, "08_set_credito", f);
      setMsg(`✅ Carpeta de ${form.nombre} creada con subcarpetas Solicitud, Set Crédito y Estudio Título (${files.length} archivo(s) en Set Crédito)`);
      setForm({ nombre: "", rut: "" }); setFiles([]);
      cargar();
    } catch (e) { setMsg(`⛔ ${e.response?.data?.detail || "Error"}`); }
    setBusy(false);
  };

  const subirProyeccion = async () => {
    if (!mes || !proyFile) { setMsg("⛔ Indique el mes y el archivo de su Proyección Mensual"); return; }
    setBusy(true); setMsg("");
    try {
      const fd = new FormData();
      fd.append("mes", mes); fd.append("archivo", proyFile);
      await axios.post(`${API}/api/broker/proyeccion`, fd);
      setMsg("✅ Proyección Mensual cargada"); setMes(""); setProyFile(null);
      cargar();
    } catch (e) { setMsg(`⛔ ${e.response?.data?.detail || "Error"}`); }
    setBusy(false);
  };

  const subirEnCarpeta = async (fid, subcarpeta, e) => {
    const fs = Array.from(e.target.files || []);
    if (!fs.length) return;
    try {
      for (const f of fs) await subirArchivo(fid, subcarpeta, f);
      setMsg(`✅ ${fs.length} archivo(s) subidos`);
      cargar();
    } catch (err) { setMsg(`⛔ ${err.response?.data?.detail || "Error al subir"}`); }
  };

  return (
    <div className="module-content seamless-scope" data-testid="brokers-module" style={{ padding: "1.2rem", borderRadius: 12 }}>
      <div className="clientes-toolbar">
        <h3 style={{ margin: 0, color: "var(--text-primary)", fontSize: "1.05rem" }}>
          <i className="fa fa-briefcase" style={{ marginRight: 8, color: "var(--gold)" }} />Panel Broker — {user?.nombre}
        </h3>
        <span style={{ color: "var(--text-secondary)", fontSize: "0.72rem" }}>
          Usuario D · Sello de origen en cada carpeta (Regla #38) · Solo ve sus propias carpetas
        </span>
        <EstadoSalida />
      </div>
      {/* 📊 PROYECCIÓN MENSUAL: formato Excel oficial (ventana días 1 a 5 hábiles) */}
      <div data-testid="broker-excel" style={{ background: "rgba(30,41,59,0.55)", border: "1px solid rgba(251,191,36,0.4)",
        borderRadius: 12, padding: "0.9rem 1.1rem", marginTop: 12, display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
        <b style={{ color: "#fbbf24", fontSize: "0.8rem" }}>📊 Proyección Mensual (Excel oficial · ventana: día 1 al 5° hábil)</b>
        <button data-testid="broker-descargar-formato" onClick={async () => {
          try {
            const r = await axios.get(`${API}/api/broker/formato-excel`, { responseType: "blob" });
            const a = document.createElement("a");
            a.href = URL.createObjectURL(new Blob([r.data]));
            a.download = "FORMATO_PROYECCION_SUPERCARPETA.xlsx"; a.click();
          } catch { window.alert("Error al descargar el formato"); }
        }} style={{ background: "rgba(251,191,36,0.15)", border: "1px solid rgba(251,191,36,0.5)", color: "#fbbf24",
          borderRadius: 8, padding: "0.4rem 1rem", fontWeight: 800, cursor: "pointer", fontSize: "0.72rem" }}>
          ⬇ Descargar formato oficial</button>
        {ventana && !ventana.abierta ? (
          <button data-testid="broker-subir-excel-cerrado" disabled
            style={{ background: "rgba(148,163,184,0.12)", border: "1px solid rgba(148,163,184,0.4)", color: "#64748b",
              borderRadius: 8, padding: "0.4rem 1rem", fontWeight: 800, cursor: "not-allowed", fontSize: "0.72rem" }}>
            🔒 Subir Excel (ventana cerrada)</button>
        ) : (
          <label style={{ background: "rgba(74,222,128,0.12)", border: "1px solid rgba(74,222,128,0.5)", color: "#4ade80",
            borderRadius: 8, padding: "0.4rem 1rem", fontWeight: 800, cursor: "pointer", fontSize: "0.72rem" }}>
            ⬆ Subir Excel completado
            <input data-testid="broker-subir-excel" type="file" accept=".xlsx" style={{ display: "none" }}
              onChange={async (e) => {
                const f = e.target.files?.[0]; if (!f) return;
                const fd = new FormData(); fd.append("archivo", f);
                try {
                  const r = await axios.post(`${API}/api/broker/cargar-excel`, fd);
                  const errs = (r.data.errores || []).length ? `\n⚠️ ${r.data.errores.join("\n")}` : "";
                  window.alert(`✅ Supercarpeta alimentada sin ingreso manual: ${r.data.creados} carpeta(s) nueva(s), ${r.data.actualizados} actualizada(s)${errs}`);
                } catch (er) { window.alert(er.response?.data?.detail || "Error al cargar el Excel"); }
                e.target.value = "";
              }} />
          </label>
        )}
        {ventana && !ventana.abierta && (
          <span data-testid="broker-ventana-mensaje" style={{ flexBasis: "100%", color: "#f87171",
            fontSize: "0.7rem", fontWeight: 700 }}>{ventana.mensaje}</span>
        )}
      </div>
      {msg && <div data-testid="broker-msg" style={{ marginTop: 10, color: msg.startsWith("✅") ? "#22c55e" : "#ef4444", fontSize: "0.74rem", fontWeight: 700 }}>{msg}</div>}

      <div style={card} data-testid="broker-nuevo-cliente">
        <div style={{ color: "#d4af37", fontWeight: 800, fontSize: "0.82rem", marginBottom: 8 }}>📁 Cargar Set de Crédito — Nuevo Cliente</div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input data-testid="broker-nombre" style={{ ...inp, flex: "1 1 220px" }} placeholder="Nombre completo del cliente"
            value={form.nombre} onChange={e => setForm({ ...form, nombre: e.target.value })} />
          <input data-testid="broker-rut" style={{ ...inp, flex: "1 1 140px" }} placeholder="RUT (ej. 12.345.678-9)"
            value={form.rut} onChange={e => setForm({ ...form, rut: e.target.value })} />
          <input data-testid="broker-set-files" type="file" multiple accept=".pdf,.jpg,.png,.jpeg"
            onChange={e => setFiles(Array.from(e.target.files || []))} style={{ ...inp, flex: "1 1 220px", padding: "0.35rem" }} />
          <button data-testid="broker-crear-carpeta" style={goldBtn} disabled={busy || !form.nombre || !form.rut} onClick={crearCarpeta}>
            {busy ? "Creando…" : "Crear carpeta y cargar Set"}
          </button>
        </div>
        <p style={{ color: "#94a3b8", fontSize: "0.64rem", margin: "8px 0 0" }}>
          Se crean automáticamente las subcarpetas: <b>Solicitud</b> · <b>Set Crédito</b> · <b>Estudio Título</b>. El RUT es obligatorio (Regla #34).
        </p>
      </div>

      <div style={card} data-testid="broker-proyeccion">
        <div style={{ color: "#d4af37", fontWeight: 800, fontSize: "0.82rem", marginBottom: 8 }}>📊 Proyección Mensual</div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <input data-testid="broker-proyeccion-mes" type="month" style={inp} value={mes} onChange={e => setMes(e.target.value)} />
          <input data-testid="broker-proyeccion-file" type="file" accept=".pdf,.xlsx,.xls,.csv"
            onChange={e => setProyFile(e.target.files?.[0] || null)} style={{ ...inp, padding: "0.35rem", flex: "1 1 220px" }} />
          <button data-testid="broker-proyeccion-subir" style={goldBtn} disabled={busy} onClick={subirProyeccion}>Subir Proyección</button>
        </div>
        {proys.length > 0 && (
          <div style={{ marginTop: 10, fontSize: "0.7rem", color: "#e2e8f0" }}>
            {proys.map(p => <div key={p.id} data-testid={`broker-proy-${p.id}`} style={{ padding: "0.25rem 0", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
              📄 {p.archivo} · <span style={{ color: "#d4af37" }}>{p.mes}</span> · {fdd(p.subido_en)}</div>)}
          </div>
        )}
      </div>

      <div style={card} data-testid="broker-carga-masiva">
        <div style={{ color: "#d4af37", fontWeight: 800, fontSize: "0.82rem", marginBottom: 8 }}>📦 Centro de Carga Masiva</div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <select data-testid="carga-carpeta" style={{ ...inp, flex: "0 1 220px" }} value={carga.fid}
            onChange={e => setCarga({ ...carga, fid: e.target.value })}>
            <option value="">Carpeta del cliente…</option>
            {(data?.carpetas || []).map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select>
          <select data-testid="carga-categoria" style={{ ...inp, flex: "0 1 220px" }} value={carga.categoria}
            onChange={e => setCarga({ ...carga, categoria: e.target.value })}>
            {CATEGORIAS.map(([k, t]) => <option key={k} value={k}>{t}</option>)}
          </select>
          {carga.categoria === "otros" && (
            <input data-testid="carga-descripcion" style={{ ...inp, flex: "1 1 200px" }} placeholder="Descripción libre del documento"
              value={carga.descripcion} onChange={e => setCarga({ ...carga, descripcion: e.target.value })} />
          )}
          <input data-testid="carga-files" type="file" multiple accept=".pdf,.jpg,.png,.jpeg"
            onChange={e => setCarga({ ...carga, files: Array.from(e.target.files || []) })} style={{ ...inp, flex: "1 1 200px", padding: "0.35rem" }} />
          <button data-testid="carga-subir" style={goldBtn} disabled={busy} onClick={cargaMasiva}>
            {busy ? "Auditando…" : "Cargar (auditoría DashAI)"}
          </button>
        </div>
        <p style={{ color: "#94a3b8", fontSize: "0.62rem", margin: "8px 0 0" }}>
          REGLA DE HIERRO: DashAI audita cada archivo — si el RUT del documento no coincide con el cliente, se rechaza.
          Todo lo cargado aparece al instante en la Bodega de Datos Concreces y en Gerencia Comercial.
        </p>
      </div>

      <div style={card} data-testid="broker-estado-situacion">
        <div style={{ color: "#d4af37", fontWeight: 800, fontSize: "0.82rem", marginBottom: 8 }}>📡 Estado de Situación — mis clientes</div>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.7rem", color: "#e2e8f0" }}>
            <thead><tr style={{ color: "#94a3b8", fontSize: "0.6rem", textTransform: "uppercase" }}>
              {["Cliente", "RUT", "Tipo", "Docs", "Tasación", "Estudio Títulos", "Escrituración", "Último hito"].map(h =>
                <th key={h} style={{ textAlign: "left", padding: "0.4rem 0.6rem", borderBottom: "1px solid rgba(148,163,184,0.15)" }}>{h}</th>)}
            </tr></thead>
            <tbody>
              {situacion.map(s => (
                <tr key={s.id} data-testid={`situacion-${s.id}`} style={{ borderBottom: "1px solid rgba(148,163,184,0.08)" }}>
                  <td style={{ padding: "0.4rem 0.6rem", fontWeight: 700, color: "#f8fafc" }}>{s.cliente}</td>
                  <td style={{ padding: "0.4rem 0.6rem", fontFamily: "monospace" }}>{s.rut || "—"}</td>
                  <td style={{ padding: "0.4rem 0.6rem" }}>{s.tipo_operacion}</td>
                  <td style={{ padding: "0.4rem 0.6rem" }}>{s.documentos}</td>
                  <td style={{ padding: "0.4rem 0.6rem", color: s.tasacion === "Recibida" ? "#22c55e" : "#94a3b8" }}>{s.tasacion}</td>
                  <td style={{ padding: "0.4rem 0.6rem", color: s.reparos ? "#ef4444" : (s.estudio === "Recibido" ? "#22c55e" : "#94a3b8") }}>
                    {s.estudio}{s.reparos ? ` (${s.reparos})` : ""}</td>
                  <td style={{ padding: "0.4rem 0.6rem" }}>{s.escrituracion ? "✅ En Escrituración" : "—"}</td>
                  <td style={{ padding: "0.4rem 0.6rem", color: "#94a3b8" }}>{s.hitos_recientes?.[0]?.hito || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {situacion.length === 0 && <p style={{ color: "var(--text-muted)", fontSize: "0.7rem" }}>Sin clientes asociados todavía.</p>}
        </div>
      </div>

      <div style={card} data-testid="broker-carpetas">
        <div style={{ color: "#d4af37", fontWeight: 800, fontSize: "0.82rem", marginBottom: 8 }}>
          🗂 Mis Carpetas ({data?.total ?? 0})
        </div>
        {(data?.carpetas || []).length === 0 && <p style={{ color: "var(--text-muted)", fontSize: "0.74rem" }}>Aún no tiene carpetas. Cree la primera cargando un Set de Crédito.</p>}
        {(data?.carpetas || []).map(c => (
          <div key={c.id} data-testid={`broker-carpeta-${c.id}`} style={{ border: "1px solid rgba(148,163,184,0.2)", borderRadius: 10, padding: "0.8rem", marginBottom: 10 }}>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "baseline" }}>
              <b style={{ color: "#f8fafc", fontSize: "0.85rem" }}>{c.nombre}</b>
              <span style={{ color: "#d4af37", fontFamily: "monospace", fontSize: "0.72rem" }}>{c.rut}</span>
              <span style={{ color: "#64748b", fontSize: "0.64rem", marginLeft: "auto" }}>{(c.created_at || "").slice(0, 10)}</span>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
              {(data?.subcarpetas || []).map(s => (
                <div key={s.key} style={{ flex: "1 1 200px", background: "rgba(15,23,42,0.6)", borderRadius: 8, padding: "0.6rem" }}>
                  <div style={{ color: "#d4af37", fontSize: "0.68rem", fontWeight: 800, marginBottom: 4 }}>{s.label}</div>
                  {(c.subcarpetas?.[s.key] || []).map(f => <div key={f} style={{ color: "#e2e8f0", fontSize: "0.64rem", padding: "0.1rem 0" }}>📄 {f}</div>)}
                  {(c.subcarpetas?.[s.key] || []).length === 0 && <div style={{ color: "#64748b", fontSize: "0.62rem" }}>Vacía</div>}
                  <label style={{ display: "inline-block", marginTop: 6, cursor: "pointer", color: "#d4af37", fontSize: "0.62rem", fontWeight: 700, border: "1px dashed rgba(212,175,55,0.5)", borderRadius: 6, padding: "0.2rem 0.5rem" }}>
                    + Subir archivo
                    <input data-testid={`broker-upload-${c.id}-${s.key}`} type="file" multiple style={{ display: "none" }}
                      onChange={e => subirEnCarpeta(c.id, s.key, e)} />
                  </label>
                </div>
              ))}
            </div>
            <NubeCarpeta fid={c.id} />
          </div>
        ))}
      </div>

      <div style={card} data-testid="broker-actividad">
        <div style={{ color: "#d4af37", fontWeight: 800, fontSize: "0.82rem", marginBottom: 8 }}>🖐 Huella Digital — registro DashAI</div>
        {actividad.slice(0, 10).map(a => (
          <div key={a.id} style={{ fontSize: "0.64rem", color: "#94a3b8", padding: "0.2rem 0", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
            <b style={{ color: a.accion === "archivo_rechazado" ? "#ef4444" : "#e2e8f0" }}>{a.accion}</b>
            {" · "}{a.detalle?.archivo || a.detalle?.cliente || ""}{a.detalle?.carpeta ? ` → ${a.detalle.carpeta}` : ""}
            {" · "}{fdd(a.fecha)}
          </div>
        ))}
        {actividad.length === 0 && <p style={{ color: "var(--text-muted)", fontSize: "0.7rem" }}>Sin actividad registrada.</p>}
      </div>

      <GestorFuentesIMAP panel={`broker_${user?.codigo || "brokers"}`} titulo={`Fuentes de ${user?.nombre || "Broker"}`} />
    </div>
  );
}
