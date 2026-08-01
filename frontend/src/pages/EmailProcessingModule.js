import React, { useEffect, useState, useRef } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

const STATUS_META = {
  pendiente:   { label: "Pendiente",   color: "#eab308", emoji: "🟡" },
  procesando:  { label: "Procesando",  color: "#3b82f6", emoji: "🔵" },
  clasificado: { label: "Clasificado", color: "#22c55e", emoji: "🟢" },
  revisar:     { label: "Revisar",     color: "#f97316", emoji: "🟠" },
  error:       { label: "Error",       color: "#ef4444", emoji: "🔴" },
  descartado:  { label: "Descartado",  color: "#6b7280", emoji: "⚫" },
};

const TIPOS_DOC = ["liquidacion","cotizacion","cedula","dicom","carta_aprobacion","simulacion","solicitud","otro"];

export default function EmailProcessingModule() {
  const [stats, setStats] = useState({});
  const [rows, setRows] = useState([]);
  const [filter, setFilter] = useState("");
  const [selected, setSelected] = useState(null);
  const [busy, setBusy] = useState(false);
  const [rules, setRules] = useState([]);
  const [showRules, setShowRules] = useState(false);
  const [driveConfigured, setDriveConfigured] = useState(false);
  const [auto, setAuto] = useState(null);
  const [alertas, setAlertas] = useState([]);

  const loadAuto = async () => {
    try {
      const [a, al] = await Promise.all([
        axios.get(`${API}/api/procesamiento/auto/status`),
        axios.get(`${API}/api/admin/alertas`),
      ]);
      setAuto(a.data);
      setAlertas((al.data.alertas || []).filter(x => !x.leida));
    } catch (_e) { /* noop */ }
  };

  useEffect(() => {
    loadAuto();
    const t = setInterval(loadAuto, 30000);
    return () => clearInterval(t);
  }, []);

  const toggleAuto = async () => {
    const r = await axios.post(`${API}/api/procesamiento/auto/toggle`, { enabled: !(auto?.enabled) });
    setAuto(prev => ({ ...prev, ...r.data }));
  };

  const changeInterval = async () => {
    const v = prompt("¿Cada cuántos minutos revisar el correo? (2 a 120)", String(auto?.interval_min || 10));
    if (!v) return;
    const n = parseInt(v, 10);
    if (isNaN(n) || n < 2 || n > 120) return alert("Valor inválido (debe ser entre 2 y 120 minutos)");
    const r = await axios.post(`${API}/api/procesamiento/auto/toggle`, { interval_min: n });
    setAuto(prev => ({ ...prev, ...r.data }));
  };

  const runAutoNow = async () => {
    const r = await axios.post(`${API}/api/procesamiento/auto/run-now`);
    alert(r.data.message);
    setTimeout(() => { loadAuto(); load(); }, 5000);
  };

  const markAlertRead = async (aid) => {
    await axios.post(`${API}/api/admin/alertas/${aid}/leida`);
    setAlertas(prev => prev.filter(a => a.id !== aid));
  };

  const load = async () => {
    const [s, q, r, d] = await Promise.all([
      axios.get(`${API}/api/procesamiento/stats`),
      axios.get(`${API}/api/procesamiento/queue${filter ? `?status=${filter}` : ""}`),
      axios.get(`${API}/api/procesamiento/rules`),
      axios.get(`${API}/api/oauth/drive/status`).catch(() => ({ data: { configured: false } })),
    ]);
    setStats(s.data);
    setRows(q.data.rows || []);
    setRules(r.data.rules || []);
    setDriveConfigured(!!d.data?.configured);
  };

  const connectDrive = () => {
    // Drive uses a DIFFERENT account (personal @gmail) than Gmail (Workspace)
    // because Workspace admin blocks Drive API access. Ensure you're logged in
    // with the personal Gmail before clicking.
    window.open(`${API}/api/oauth/drive/start`, "_blank", "width=560,height=720");
  };

  const purgeDrive = async () => {
    if (!window.confirm("⚠️ Esto elimina TODAS las carpetas creadas por Procesamiento de Correo y limpia el cache de hashes. Las carpetas creadas manualmente NO se tocan. ¿Continuar?")) return;
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/procesamiento/drive/purge-all`);
      alert(`✅ Purga completada.\nCarpetas eliminadas: ${r.data.deleted}\nErrores: ${r.data.errors?.length || 0}`);
      load();
    } catch (e) {
      alert("Error: " + (e.response?.data?.detail || e.message));
    } finally { setBusy(false); }
  };

  useEffect(() => { load(); }, [filter]);

  const ingest = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/procesamiento/ingest-from-inbox?max_emails=30`);
      alert(`Ingest OK: ${r.data.fetched} correos, ${r.data.enqueued} nuevos en cola`);
      load();
    } catch (e) { alert("Error: " + e.message); } finally { setBusy(false); }
  };

  const processPending = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/procesamiento/process-pending?limit=20`);
      alert(`Procesados ${r.data.processed}`);
      load();
    } catch (e) { alert("Error: " + e.message); } finally { setBusy(false); }
  };

  const reprocess = async (id) => {
    setBusy(true);
    try {
      await axios.post(`${API}/api/procesamiento/queue/${id}/reprocess`);
      load(); if (selected?.id === id) openDetail(id);
    } finally { setBusy(false); }
  };

  const saveCorrection = async (id, corrected) => {
    setBusy(true);
    try {
      await axios.post(`${API}/api/procesamiento/queue/${id}/correct`, corrected);
      load(); setSelected(null);
    } finally { setBusy(false); }
  };

  const openDetail = async (id) => {
    const r = await axios.get(`${API}/api/procesamiento/queue/${id}`);
    setSelected(r.data);
  };

  const uploadToDrive = async (id) => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/procesamiento/queue/${id}/upload-drive`);
      const upl = r.data.uploaded || [];
      const dupes = r.data.skipped_duplicates || [];
      const dropped = r.data.dropped_originals || [];
      let msg = `✅ Carpeta local: ${r.data.folder_name}\n${upl.length} archivo(s) guardado(s)`;
      if (dupes.length) msg += `\n${dupes.length} duplicado(s) omitidos por OCR`;
      if (dropped.length) msg += `\n${dropped.length} original(es) no-PDF descartado(s)`;
      msg += `\n\nVer en: Carpeta Clientes → ${r.data.folder_name}`;
      alert(msg);
      load(); if (selected?.id === id) openDetail(id);
    } catch (e) {
      alert("Error: " + (e.response?.data?.detail || e.message));
    } finally { setBusy(false); }
  };

  const enviarAutocorreo = async (id) => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/procesamiento/queue/${id}/enviar-autocorreo`, {});
      if (r.data.success) {
        alert(`✅ Autocorreo enviado a ${r.data.destino}\n${r.data.adjunto ? "Con PDF agrupado adjunto" : "Sin PDF agrupado (arma la carpeta primero)"}\n\nRevisa tu bandeja y reenvíalo a mesa.`);
      } else {
        const campos = (r.data.campos_faltantes || []).map(f => `  • ${f}`).join("\n");
        const docs = Object.entries(r.data.docs_faltantes || {}).map(([t, n]) => `  • ${t}: faltan ${n}`).join("\n");
        alert(`⚠️ NO se envió: falta información.\n${r.data.aviso_enviado ? "Se envió un AVISO por correo con el detalle." : ""}\n\n${campos ? "Campos por completar:\n" + campos : ""}${docs ? "\n\nDocumentos faltantes:\n" + docs : ""}\n\nComplétalo a mano (Guardar corrección / Adjuntar documento) y vuelve a enviar.`);
      }
      load(); if (selected?.id === id) openDetail(id);
    } catch (e) {
      alert("Error: " + (e.response?.data?.detail || e.message));
    } finally { setBusy(false); }
  };

  const attachManual = async (id, fileList) => {
    setBusy(true);
    try {
      const fd = new FormData();
      Array.from(fileList).forEach(f => fd.append("files", f));
      const r = await axios.post(`${API}/api/procesamiento/queue/${id}/attach-manual`, fd);
      let msg = `✅ ${r.data.added.length} documento(s) adjuntado(s)`;
      if (r.data.convertidos?.length) msg += `\n${r.data.convertidos.length} convertido(s) a PDF: ${r.data.convertidos.join(", ")}`;
      if (r.data.errors?.length) msg += `\n⚠️ Errores: ${r.data.errors.map(x => x.file).join(", ")}`;
      msg += "\n\nUsa ♻ Reprocesar con IA para clasificarlos.";
      alert(msg);
      load(); if (selected?.id === id) openDetail(id);
    } catch (e) {
      alert("Error: " + (e.response?.data?.detail || e.message));
    } finally { setBusy(false); }
  };


  const extractText = async (id) => {
    setBusy(true);
    try {
      const r = await axios.get(`${API}/api/procesamiento/queue/${id}/extract-text?allow_vision=true`);
      const lines = (r.data.results || []).map(x =>
        `• ${x.filename} [${x.method || "?"}, ${x.chars || 0} chars]` +
        (x.converted_from ? ` (conv de .${x.converted_from})` : "") +
        (x.reason ? ` — ${x.reason}` : "")
      );
      alert(`Extracción OCR:\n\n${lines.join("\n")}`);
    } catch (e) {
      alert("Error: " + (e.response?.data?.detail || e.message));
    } finally { setBusy(false); }
  };

  const addRule = async () => {
    const name = prompt("Nombre de la regla:"); if (!name) return;
    const pattern = prompt("Patrón (contains) — ej: 'Ecomac':"); if (!pattern) return;
    const inmobiliaria = prompt("Inmobiliaria a asignar (o vacío):") || "";
    const tipo = prompt("Tipo doc (liquidacion/cotizacion/simulacion/solicitud/otro):") || "otro";
    await axios.post(`${API}/api/procesamiento/rules`, {
      name, pattern, kind: "contains", priority: 10, active: true,
      classify_as: { inmobiliaria, tipo_documento: tipo },
    });
    load();
  };

  const deleteRule = async (id) => {
    if (!window.confirm("¿Eliminar regla?")) return;
    await axios.delete(`${API}/api/procesamiento/rules/${id}`);
    load();
  };

  return (
    <div style={{ padding: 24 }} data-testid="email-processing-module">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 26, color: "#1a1f2e" }}>📥 Procesamiento de Correo</h2>
          <p style={{ margin: "4px 0 0", color: "#64748b", fontSize: 13 }}>
            Monitoreo, clasificación IA y corrección manual de correos entrantes
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button data-testid="btn-ingest" onClick={ingest} disabled={busy}
                  style={btnStyle("#3b82f6")}>📨 Ingestar Inbox</button>
          <button data-testid="btn-process" onClick={processPending} disabled={busy}
                  style={btnStyle("#22c55e")}>⚡ Procesar pendientes</button>
          <button data-testid="btn-rules" onClick={() => setShowRules(!showRules)}
                  style={btnStyle("#8b5cf6")}>⚙️ Reglas ({rules.length})</button>
          {driveConfigured ? (
            <>
              <span data-testid="drive-badge"
                    style={{ padding: "6px 12px", borderRadius: 6, background: "#dcfce7", color: "#166534", fontWeight: 700, fontSize: 12, alignSelf: "center" }}>
                📂 Almacenamiento local activo
              </span>
              <button data-testid="btn-purge" onClick={purgeDrive} disabled={busy}
                      style={btnStyle("#dc2626")}>🗑️ Purga carpetas Procesamiento</button>
            </>
          ) : (
            <span style={{ padding: "6px 12px", borderRadius: 6, background: "#fef3c7", color: "#92400e", fontWeight: 700, fontSize: 12, alignSelf: "center" }}>
              ⚠️ Almacenamiento inactivo
            </span>
          )}
        </div>
      </div>

      {/* PANEL AUTOMÁTICO 24/7 */}
      <div data-testid="auto-panel" style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", padding: "10px 14px", borderRadius: 10, marginBottom: 16, background: auto?.enabled ? "#dcfce7" : "#f1f5f9", border: `1px solid ${auto?.enabled ? "#22c55e" : "#cbd5e1"}` }}>
        <span style={{ fontSize: 14, fontWeight: 700, color: auto?.enabled ? "#166534" : "#475569" }}>
          🤖 Procesamiento automático {auto?.enabled ? "ACTIVADO" : "desactivado"}
        </span>
        <button data-testid="btn-auto-toggle" onClick={toggleAuto} disabled={!auto}
                style={btnStyle(auto?.enabled ? "#dc2626" : "#22c55e", true)}>
          {auto?.enabled ? "Desactivar" : "Activar"}
        </button>
        {auto?.enabled && (
          <>
            <button data-testid="btn-auto-interval" onClick={changeInterval} style={btnStyle("#3b82f6", true)}
                    title="Cambiar frecuencia de revisión">
              ⏱ cada {auto?.interval_min || 10} min
            </button>
            <button data-testid="btn-auto-run-now" onClick={runAutoNow} disabled={auto?.running} style={btnStyle("#8b5cf6", true)}>
              {auto?.running ? "⏳ Corriendo…" : "▶ Ejecutar ahora"}
            </button>
            <span style={{ fontSize: 12, color: "#64748b" }}>
              {auto?.last_run
                ? `Última revisión: ${String(auto.last_run).slice(0, 16).replace("T", " ")} — ${auto.last_result?.enqueued || 0} nuevos, ${auto.last_result?.carpetas || 0} carpetas armadas, ${auto.last_result?.alertas || 0} alertas`
                : "Todavía no corrió ningún ciclo."}
            </span>
          </>
        )}
      </div>

      {alertas.length > 0 && (
        <div data-testid="alertas-panel" style={{ padding: "10px 14px", borderRadius: 10, marginBottom: 16, background: "#fefce8", border: "1px solid #facc15" }}>
          <div style={{ fontWeight: 700, color: "#854d0e", marginBottom: 6 }}>🔔 Carpetas listas para enviar a mesa</div>
          {alertas.map(a => (
            <div key={a.id} data-testid={`alerta-${a.id}`} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "4px 0", fontSize: 13, color: "#713f12" }}>
              <span>✅ {a.mensaje} <small style={{ opacity: 0.6 }}>({String(a.fecha || "").slice(0, 16).replace("T", " ")})</small></span>
              <button onClick={() => markAlertRead(a.id)} style={btnStyle("#64748b", true)} title="Marcar como vista">✔ Vista</button>
            </div>
          ))}
          <div style={{ fontSize: 11, color: "#a16207", marginTop: 4 }}>Andá a <b>Carpeta Clientes</b> para revisar y enviar el autocorreo.</div>
        </div>
      )}

      {/* KPI cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 12, marginBottom: 20 }}>
        {["total","pendiente","clasificado","revisar","error","descartado"].map(k => {
          const meta = STATUS_META[k] || { label: "Total", emoji: "📊", color: "#1a1f2e" };
          return (
            <div key={k} data-testid={`kpi-${k}`}
                 onClick={() => setFilter(k === "total" ? "" : k)}
                 style={{ cursor: "pointer", padding: 14, borderRadius: 10,
                          background: filter===k ? "#fef3c7" : "#ffffff",
                          border: `2px solid ${filter===k ? meta.color : "#e2e8f0"}` }}>
              <div style={{ fontSize: 11, color: "#64748b", textTransform: "uppercase" }}>
                {meta.emoji} {meta.label}
              </div>
              <div style={{ fontSize: 26, fontWeight: 700, color: meta.color }}>
                {stats[k] || 0}
              </div>
            </div>
          );
        })}
      </div>

      {showRules && (
        <div style={{ background: "#f8fafc", padding: 16, borderRadius: 10, marginBottom: 20, border: "1px solid #e2e8f0" }}>
          <div style={{ display:"flex", justifyContent:"space-between", marginBottom: 10 }}>
            <h3 style={{ margin: 0 }}>⚙️ Reglas de clasificación</h3>
            <button onClick={addRule} style={btnStyle("#3b82f6")}>+ Nueva regla</button>
          </div>
          {rules.length === 0 && <div style={{ color: "#64748b" }}>Sin reglas configuradas — la IA clasifica todo.</div>}
          {rules.map(r => (
            <div key={r.id} data-testid={`rule-${r.id}`}
                 style={{ display:"flex", justifyContent:"space-between", padding:"8px 12px", borderBottom:"1px solid #e2e8f0" }}>
              <div>
                <strong>{r.name}</strong> — si contiene <code>{r.pattern}</code> →
                {" "}{JSON.stringify(r.classify_as || {})}
              </div>
              <button onClick={() => deleteRule(r.id)} style={btnStyle("#ef4444")}>Eliminar</button>
            </div>
          ))}
        </div>
      )}

      {/* Table */}
      <div style={{ background: "#ffffff", borderRadius: 10, overflow: "hidden", border: "1px solid #e2e8f0" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "#1a1f2e", color: "#fff" }}>
              <th style={th}>Estado</th>
              <th style={th}>Fecha</th>
              <th style={th}>Asunto</th>
              <th style={th}>Cliente detectado</th>
              <th style={th}>Tipo doc</th>
              <th style={th}>Confianza</th>
              <th style={th}>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(r => {
              const meta = STATUS_META[r.status] || { emoji: "❓", color: "#64748b", label: r.status };
              const cl = r.classification || {};
              return (
                <tr key={r.id} data-testid={`row-${r.id}`}
                    style={{ borderBottom: "1px solid #f1f5f9", cursor: "pointer" }}
                    onClick={() => openDetail(r.id)}>
                  <td style={td}><span style={{ color: meta.color, fontWeight: 700 }}>{meta.emoji} {meta.label}</span></td>
                  <td style={td}>{(r.date_iso || "").slice(0,10)}</td>
                  <td style={td} title={r.subject}>{(r.subject || "").slice(0,60)}</td>
                  <td style={td}>{cl.cliente || "—"}</td>
                  <td style={td}>{cl.tipo_documento || "—"}</td>
                  <td style={td}>{cl.confianza != null ? `${Math.round(cl.confianza*100)}%` : "—"}</td>
                  <td style={td} onClick={(e) => e.stopPropagation()}>
                    <button onClick={() => reprocess(r.id)} disabled={busy} style={btnStyle("#3b82f6", true)}>♻</button>
                  </td>
                </tr>
              );
            })}
            {rows.length === 0 && (
              <tr><td colSpan={7} style={{ ...td, textAlign:"center", color:"#94a3b8", padding: 30 }}>
                Sin resultados. Hacé clic en <b>Ingestar Inbox</b> para traer correos.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {selected && (
        <DetailModal item={selected} onClose={() => setSelected(null)}
                     onReprocess={reprocess} onSave={saveCorrection}
                     onUploadDrive={uploadToDrive} onExtractText={extractText}
                     onEnviarAutocorreo={enviarAutocorreo} onAttachManual={attachManual}
                     driveConfigured={driveConfigured} busy={busy} />
      )}
    </div>
  );
}

function DetailModal({ item, onClose, onReprocess, onSave, onUploadDrive, onExtractText, onEnviarAutocorreo, onAttachManual, driveConfigured, busy }) {
  const cl = item.classification || {};
  const campos = item.campos || {};
  const fileRef = useRef(null);
  const [docs, setDocs] = useState(cl.documentos || []);
  const [ordenando, setOrdenando] = useState(false);
  const moverDoc = async (i, dir) => {
    const j = i + dir;
    if (j < 0 || j >= docs.length) return;
    const nuevos = [...docs];
    [nuevos[i], nuevos[j]] = [nuevos[j], nuevos[i]];
    setDocs(nuevos);
    setOrdenando(true);
    try {
      await axios.post(`${API}/api/procesamiento/queue/${item.id}/ordenar-docs`,
        { filenames: nuevos.map(d => d.filename) });
    } catch (e) { alert("Error guardando orden: " + (e.response?.data?.detail || e.message)); }
    setOrdenando(false);
  };
  const [c, setC] = useState({
    cliente: cl.cliente || "",
    rut: cl.rut || "",
    tipo_documento: cl.tipo_documento || "otro",
    inmobiliaria: cl.inmobiliaria || "",
    tipo_cliente: cl.tipo_cliente || "dependiente",
    email_cliente: cl.email_cliente || campos.email_cliente || "",
    proyecto_inmobiliario: campos.proyecto_inmobiliario || "",
    fecha_entrega: campos.fecha_entrega || "",
    con_subsidio: campos.con_subsidio === true ? "si" : campos.con_subsidio === false ? "no" : "",
    monto_credito_uf: campos.monto_credito_uf ?? "",
    monto_subsidio_uf: campos.monto_subsidio_uf ?? "",
    pie_uf: campos.pie_uf ?? "",
    ahorro_uf: campos.ahorro_uf ?? "",
    monto_credito_solicitar_uf: campos.monto_credito_solicitar_uf ?? "",
  });
  const guardar = () => {
    const payload = { ...c };
    payload.con_subsidio = c.con_subsidio === "si" ? true : c.con_subsidio === "no" ? false : null;
    ["monto_credito_uf","monto_subsidio_uf","pie_uf","ahorro_uf","monto_credito_solicitar_uf"].forEach(k => {
      payload[k] = c[k] === "" ? null : Number(c[k]);
    });
    onSave(item.id, payload);
  };
  return (
    <div style={{ position:"fixed", inset:0, background:"rgba(0,0,0,0.55)", zIndex:100,
                  display:"flex", alignItems:"center", justifyContent:"center" }}
         onClick={onClose}>
      <div style={{ background:"#fff", borderRadius:14, width:720, maxHeight:"85vh", overflow:"auto", padding:24 }}
           onClick={(e) => e.stopPropagation()} data-testid="detail-modal">
        <h3 style={{ marginTop:0 }}>{item.subject}</h3>
        <div style={{ color:"#64748b", fontSize:12, marginBottom:12 }}>
          {item.sender} · {(item.date_iso || "").slice(0,16).replace("T"," ")} · Status: <b>{item.status}</b>
        </div>
        <div style={{ background:"#f8fafc", padding:12, borderRadius:8, marginBottom:16,
                      maxHeight:180, overflow:"auto", whiteSpace:"pre-wrap", fontSize:13 }}>
          {item.body_preview || "(sin cuerpo)"}
        </div>
        <div style={{ marginBottom:8, fontSize:12, color:"#64748b" }}>
          Adjuntos: {(item.attachments || []).join(", ") || "(sin adjuntos)"}
        </div>
        {docs.length > 0 && (
          <div style={{ background:"#fffbeb", border:"1px solid #fcd34d", borderRadius:8, padding:10, marginBottom:12 }} data-testid="docs-orden-section">
            <div style={{ fontWeight:700, fontSize:13, marginBottom:4 }}>📑 Orden de los documentos (carpeta → mesa)</div>
            <div style={{ fontSize:11, color:"#92400e", marginBottom:8 }}>
              Protocolo: dependiente = cédula → liquidaciones → AFP → CMF · honorarios = cédula → imp. renta → boletas → CMF. Usa las flechas para ajustar el orden a mano (se regenera la Carpeta).
            </div>
            {docs.map((d, i) => (
              <div key={d.filename + i} style={{ display:"flex", alignItems:"center", gap:8, padding:"3px 0", fontSize:12, borderTop: i ? "1px solid #fde68a" : "none" }} data-testid={`doc-orden-row-${i}`}>
                <span style={{ width:18, textAlign:"right", color:"#92400e", fontWeight:700 }}>{i + 1}.</span>
                <span style={{ flex:1, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{d.filename}</span>
                <span style={{ color:"#64748b" }}>{d.tipo || "otro"}</span>
                <button data-testid={`doc-subir-${i}`} onClick={() => moverDoc(i, -1)} disabled={ordenando || i === 0}
                        style={{ border:"1px solid #d1d5db", background:"#fff", borderRadius:4, cursor:"pointer", padding:"1px 7px" }}>↑</button>
                <button data-testid={`doc-bajar-${i}`} onClick={() => moverDoc(i, 1)} disabled={ordenando || i === docs.length - 1}
                        style={{ border:"1px solid #d1d5db", background:"#fff", borderRadius:4, cursor:"pointer", padding:"1px 7px" }}>↓</button>
              </div>
            ))}
          </div>
        )}
        {cl.razonamiento && (
          <div style={{ background:"#eff6ff", padding:8, borderRadius:6, fontSize:12, marginBottom:12 }}>
            🤖 IA dice: {cl.razonamiento} (confianza: {Math.round((cl.confianza||0)*100)}%)
          </div>
        )}
        <h4>Corregir clasificación</h4>
        <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap: 10, marginBottom: 12 }}>
          <label>Cliente <input data-testid="edit-cliente" value={c.cliente}
            onChange={e => setC({...c, cliente:e.target.value})} style={inp}/></label>
          <label>RUT <input data-testid="edit-rut" value={c.rut}
            onChange={e => setC({...c, rut:e.target.value})} style={inp}/></label>
          <label>Tipo documento
            <select data-testid="edit-tipo" value={c.tipo_documento}
                    onChange={e => setC({...c, tipo_documento:e.target.value})} style={inp}>
              {TIPOS_DOC.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
          <label>Inmobiliaria <input data-testid="edit-inmob" value={c.inmobiliaria}
            onChange={e => setC({...c, inmobiliaria:e.target.value})} style={inp}/></label>
        </div>
        <h4 style={{ marginBottom: 6 }}>Campos indispensables para enviar a mesa</h4>
        <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap: 10, marginBottom: 12 }}>
          <label>Tipo cliente
            <select value={c.tipo_cliente} onChange={e => setC({...c, tipo_cliente:e.target.value})} style={inp}>
              <option value="dependiente">Dependiente</option>
              <option value="independiente">Independiente</option>
            </select>
          </label>
          <label>Correo cliente <input value={c.email_cliente}
            onChange={e => setC({...c, email_cliente:e.target.value})} style={inp}/></label>
          <label>Proyecto / Inmobiliaria <input data-testid="edit-proyecto" value={c.proyecto_inmobiliario}
            onChange={e => setC({...c, proyecto_inmobiliario:e.target.value})} style={inp}/></label>
          <label>Fecha de entrega
            <select data-testid="edit-entrega" value={c.fecha_entrega}
                    onChange={e => setC({...c, fecha_entrega:e.target.value})} style={inp}>
              <option value="">—</option>
              <option value="inmediata">Inmediata</option>
              <option value="futura">Futura</option>
            </select>
          </label>
          <label>Con / Sin subsidio
            <select data-testid="edit-subsidio" value={c.con_subsidio}
                    onChange={e => setC({...c, con_subsidio:e.target.value})} style={inp}>
              <option value="">—</option>
              <option value="si">Con subsidio</option>
              <option value="no">Sin subsidio</option>
            </select>
          </label>
          <label>Monto crédito (UF) <input type="number" value={c.monto_credito_uf}
            onChange={e => setC({...c, monto_credito_uf:e.target.value})} style={inp}/></label>
          <label>Monto subsidio (UF) <input type="number" value={c.monto_subsidio_uf}
            onChange={e => setC({...c, monto_subsidio_uf:e.target.value})} style={inp}/></label>
          <label>Pie (UF) <input type="number" value={c.pie_uf}
            onChange={e => setC({...c, pie_uf:e.target.value})} style={inp}/></label>
          <label>Ahorro (UF) <input type="number" value={c.ahorro_uf}
            onChange={e => setC({...c, ahorro_uf:e.target.value})} style={inp}/></label>
          <label>Crédito a solicitar (UF) <input type="number" value={c.monto_credito_solicitar_uf}
            onChange={e => setC({...c, monto_credito_solicitar_uf:e.target.value})} style={inp}/></label>
        </div>
        <div style={{ marginBottom: 12 }}>
          <input ref={fileRef} type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.tif,.tiff,.webp,.bmp"
                 style={{ display:"none" }}
                 onChange={e => { if (e.target.files?.length) { onAttachManual(item.id, e.target.files); e.target.value = ""; } }} />
          <button data-testid="btn-attach-manual" onClick={() => fileRef.current?.click()} disabled={busy}
                  style={btnStyle("#f59e0b")}>📎 Adjuntar documento a mano (auto-convierte a PDF)</button>
        </div>
        {item.drive_folder_id && (
          <div style={{ background:"#ecfdf5", border:"1px solid #86efac", padding:8, borderRadius:6,
                        fontSize:12, marginBottom:12, color:"#065f46" }}>
            📁 Ya subido a Drive (mock): <code>{item.drive_folder_id}</code>
          </div>
        )}
        {item.drive_folder_id && (
          <div style={{ background:"#ecfdf5", border:"1px solid #86efac", padding:8, borderRadius:6,
                        fontSize:12, marginBottom:12, color:"#065f46" }}>
            📂 Guardado en carpeta local: <b>{item.drive_folder_id}</b>
          </div>
        )}
        <div style={{ display:"flex", justifyContent:"space-between", gap: 8, flexWrap:"wrap" }}>
          <div style={{ display:"flex", gap: 8, flexWrap:"wrap" }}>
            <button onClick={() => onReprocess(item.id)} disabled={busy} style={btnStyle("#3b82f6")}>
              ♻ Reprocesar con IA
            </button>
            <button data-testid="btn-extract-text" onClick={() => onExtractText(item.id)} disabled={busy}
                    style={btnStyle("#0891b2")}>🔍 Leer con OCR</button>
            {item.status === "clasificado" && (
              <button data-testid="btn-upload-drive" onClick={() => onUploadDrive(item.id)} disabled={busy}
                      style={btnStyle("#22c55e")}>📂 Guardar en Carpeta Cliente</button>
            )}
            {item.status === "clasificado" && (
              <button data-testid="btn-enviar-autocorreo" onClick={() => onEnviarAutocorreo(item.id)} disabled={busy}
                      style={btnStyle("#6c5ce7")}>✉️ Enviar autocorreo (→ mí → mesa)</button>
            )}
          </div>
          <div style={{ display:"flex", gap: 8 }}>
            <button onClick={onClose} style={btnStyle("#64748b")}>Cerrar</button>
            <button data-testid="btn-save-correction" onClick={guardar} disabled={busy}
                    style={btnStyle("#22c55e")}>Guardar corrección</button>
          </div>
        </div>
      </div>
    </div>
  );
}

const btnStyle = (bg, small=false) => ({
  background: bg, color: "#fff", padding: small ? "4px 10px" : "8px 14px",
  border: "none", borderRadius: 6, cursor: "pointer", fontWeight: 600, fontSize: small ? 12 : 13,
});
const th = { padding: "10px 12px", textAlign: "left", fontSize: 12, textTransform: "uppercase" };
const td = { padding: "10px 12px", fontSize: 13, color: "#1a1f2e" };
const inp = { width: "100%", padding: "6px 10px", border: "1px solid #cbd5e1", borderRadius: 6, marginTop: 4 };
