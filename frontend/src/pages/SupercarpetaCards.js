import { useState, useRef } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const HITO_LABEL = { tasacion: "Tasación", estudio: "Estudio de Títulos", cesion: "Cesión",
  set_credito: "Cédula de Crédito (SET)", cert_subsidio: "Certificado de Subsidio", carta_pie: "Carta Pie",
  serviu: "Resolución Serviu", promesa: "Promesa de Compraventa", carpeta_notaria: "Carpeta en Notaría",
  escritura: "Escritura en Notaría", notaria: "Notaría", carta_oferta: "Carta Oferta" };
const ESTADOS_POR = {
  tasacion: ["Pendiente", "Solicitada", "Tasación Piloto", "En Proceso", "Recibida", "Con Observaciones", "Aprobada"],
  estudio: ["Pendiente", "Solicitado", "En Proceso", "Recibido", "Con Reparos", "Aprobado"],
  serviu: ["Pendiente", "Solicitada", "Recibida", "Aprobada", "Rechazada", "Pendiente verificación manual"],
  carta_oferta: ["Pendiente", "Solicitada", "Recibida", "Aprobada", "Rechazada", "Pendiente verificación manual"],
  promesa: ["Pendiente", "Redactada", "Firmada", "Firmada (verificada IA)", "Enviada a Notaría", "Pendiente verificación manual"],
  set_credito: ["Pendiente", "Set Para la Firma", "Verificación Pendiente", "Firmado y Verificado"],
  carpeta_notaria: ["Pendiente", "Preparando Carpeta", "Enviada", "Recibida por Notaría", "En Revisión", "Aprobada"],
  escritura: ["Pendiente", "Agendada", "Firmada", "Inscrita en CBR"],
  cesion: ["Pendiente", "Confirmada"],
};
const SET_LABEL = { firmado: "✅ Set Firmado", verificacion_pendiente: "⚠️ Verificación Pendiente",
  esperando_firma: "⏳ Esperando Firma del Cliente" };
const CAMPOS_EDIT = [["rut", "RUT"], ["inmobiliaria", "Inmobiliaria"], ["proyecto", "Proyecto"],
  ["ciudad", "Ciudad"], ["notaria", "Notaría"], ["broker", "Broker"], ["monto", "Monto UF"]];
const colorAvance = (p) => p >= 100 ? "linear-gradient(90deg,#d4af37,#FFD700)"
  : p >= 90 ? "#22c55e" : p >= 61 ? "#eab308" : p >= 31 ? "#f97316" : "#ef4444";

// Semáforo del hito: ✅ verde completado · 🟡 amarillo en proceso · 🔴 rojo pendiente
const semaforo = (estado) => {
  const e = (estado || "").toLowerCase();
  if (/(aprobad|firmado y verificado|firmada|verificada ia|recibida por notaría|inscrita|confirmada|recibid)/.test(e))
    return { icono: "✅", color: "#4ade80", nivel: "completado" };
  if (!e || /^pendiente$/.test(e)) return { icono: "🔴", color: "#f87171", nivel: "pendiente" };
  return { icono: "🟡", color: "#facc15", nivel: "en proceso" };
};

const fFecha = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  return isNaN(d) ? String(iso).slice(0, 16) : d.toLocaleString("es-CL", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
};

const inputEdit = { background: "rgba(2,6,23,0.85)", border: "1px solid rgba(212,175,55,0.6)",
  borderRadius: 8, color: "#f8fafc", padding: "0.35rem 0.6rem", fontSize: 15, width: "100%" };

// ─── Campo editable: doble clic para editar · "Agregar..." si está vacío ───
const CampoEditable = ({ fid, campo, label, valor, onGuardado, manejar409, testid }) => {
  const [edit, setEdit] = useState(false);
  const [v, setV] = useState("");
  const cancelado = useRef(false);
  const guardar = async () => {
    setEdit(false);
    if (cancelado.current) { cancelado.current = false; return; }
    const val = v.trim();
    if (!val || val === String(valor || "")) return;
    try {
      await axios.post(`${API}/api/supercarpeta/manual/${fid}`, { campo, valor: val });
      onGuardado();
    } catch (e) {
      if (!(manejar409 && manejar409(e)))
        window.alert(e.response?.data?.detail?.mensaje || e.response?.data?.detail || "Error al guardar el campo");
    }
  };
  if (edit) return (
    <input autoFocus data-testid={`${testid}-input`} defaultValue={valor || ""} style={inputEdit}
      onChange={e => setV(e.target.value)} onBlur={guardar}
      onKeyDown={e => { if (e.key === "Enter") guardar(); if (e.key === "Escape") { cancelado.current = true; setEdit(false); } }} />
  );
  const vacio = valor === "" || valor == null || valor === "Por Confirmar";
  return (
    <div data-testid={testid} onDoubleClick={() => { setV(String(valor || "")); setEdit(true); }}
      onClick={() => { if (vacio) { setV(""); setEdit(true); } }}
      title={vacio ? "Toca para agregar" : "Doble clic para editar"}
      style={{ fontSize: 15, color: vacio ? "#64748b" : "#f8fafc", cursor: "pointer", minHeight: 22,
        fontStyle: vacio ? "italic" : "normal", overflowWrap: "anywhere" }}>
      {vacio ? "Agregar..." : (campo === "monto" ? `${Number(valor).toLocaleString("es-CL")} UF` : String(valor))}
    </div>
  );
};

// ─── Tarjeta de un cliente ───
const TarjetaCliente = ({ c, idx, recargar, abrirPanel, abrirSolicitud, abrirEstudio, setAvanceModal, manejar409 }) => {
  const [abierta, setAbierta] = useState(false);
  const [hitoAbierto, setHitoAbierto] = useState(null);
  const [notaForm, setNotaForm] = useState(null);
  const [hilo, setHilo] = useState(null);
  const [resumen, setResumen] = useState(null);
  const [genResumen, setGenResumen] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const regenerarResumen = async (e) => {
    e.stopPropagation();
    if (genResumen) return;
    setGenResumen(true);
    try {
      const r = await axios.post(`${API}/api/supercarpeta/resumen-hilo/${c.id}`);
      if (r.data?.texto) setResumen(r.data);
      else window.alert(r.data?.nota || "Sin correos registrados que resumir");
    } catch (err) { window.alert(err.response?.data?.detail || "Error al generar el resumen IA"); }
    setGenResumen(false);
  };
  const abrirAdjunto = async (ruta) => {
    try {
      const r = await axios.get(`${API}/api/supercarpeta/archivo/${c.id}`,
        { params: { ruta }, responseType: "blob" });
      window.open(URL.createObjectURL(new Blob([r.data], { type: "application/pdf" })), "_blank");
    } catch { window.alert("PDF no disponible"); }
  };
  const verHilo = async () => {
    if (hilo) { setHilo(null); return; }
    setHilo({ loading: true });
    try {
      const r = await axios.get(`${API}/api/supercarpeta/hilo/${c.id}`);
      setHilo(r.data);
    } catch { setHilo(null); window.alert("Error al cargar el hilo del cliente"); }
  };
  const notas = c.notas || [];
  const hitos = [["tasacion", c.estado_tasacion], ["estudio", c.estudio_titulos],
    ["serviu", c.con_subsidio ? c.serviu : null], ["carta_oferta", c.carta_oferta],
    ["promesa", c.promesa], ["set_credito", SET_LABEL[c.set_credito?.estado] || c.set_credito?.estado || "Pendiente"],
    ["carpeta_notaria", c.carpeta_notaria], ["escritura", c.escritura]].filter(([, e]) => e !== null);

  const guardarEstado = async (hito, estado) => {
    if (!estado) return;
    setGuardando(true);
    try {
      await axios.post(`${API}/api/supercarpeta/estado/${c.id}`, { hito, estado });
      recargar();
    } catch (e) { window.alert(e.response?.data?.detail || "Error al guardar estado"); }
    setGuardando(false);
  };
  const guardarNota = async () => {
    if (!notaForm?.texto?.trim()) return;
    setGuardando(true);
    try {
      await axios.post(`${API}/api/supercarpeta/nota/${c.id}`, { hito: notaForm.hito, texto: notaForm.texto.trim() });
      setNotaForm(null);
      recargar();
    } catch (e) { window.alert(e.response?.data?.detail || "Error al guardar la nota"); }
    setGuardando(false);
  };

  return (
    <div data-testid={`tarjeta-cliente-${c.id}`}
      style={{ background: idx % 2 === 0 ? "#1E2A3A" : "#233145", width: "100%",
        border: "1px solid rgba(212,175,55,0.35)", borderRadius: 14, padding: "1rem 1.1rem" }}>
      {/* ── ENCABEZADO (siempre visible) ── */}
      <div data-testid={`tarjeta-encabezado-${c.id}`} onClick={() => setAbierta(a => !a)}
        style={{ cursor: "pointer" }}>
        <div style={{ display: "flex", gap: 10, alignItems: "baseline", flexWrap: "wrap" }}>
          <b style={{ color: "#fff", fontSize: 19, overflowWrap: "anywhere", flex: 1 }}>
            <span style={{ color: "#D4AF37" }}>{idx + 1}.</span> {c.cliente}
          </b>
          {notas.length > 0 && (
            <span data-testid={`badge-nota-${c.id}`} title={`${notas.length} nota(s)`}
              style={{ background: "rgba(212,175,55,0.2)", border: "1px solid rgba(212,175,55,0.7)",
                color: "#FFD700", borderRadius: 999, padding: "2px 10px", fontSize: 13, fontWeight: 800 }}>
              📝 {notas.length}</span>
          )}
          <span style={{ color: "#94a3b8", fontSize: 15 }}>{abierta ? "▲" : "▼"}</span>
        </div>
        <div style={{ marginTop: 4, fontSize: 15, color: "#90A4AE", display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <span>{c.inmobiliaria || "—"}</span>
          {c.proyecto && <span>· {c.proyecto}</span>}
          {c.subsidio && <span style={{ background: c.subsidio.toLowerCase().startsWith("con") ? "#2E7D32" : "#37474F",
            color: "#fff", borderRadius: 999, padding: "1px 10px", fontSize: 12 }}>{c.subsidio}</span>}
          <b style={{ marginLeft: "auto", color: "#D4AF37", fontSize: 15 }}>
            {c.monto_uf ? `${Number(c.monto_uf).toLocaleString("es-CL")} UF` : ""}</b>
        </div>
        <div style={{ marginTop: 8 }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, color: "#cbd5e1" }}>
            <span>Avance general</span>
            <b style={{ color: (c.avance?.pct || 0) >= 100 ? "#FFD700" : "#f8fafc", fontSize: 15 }}>{c.avance?.pct ?? 0}%</b>
          </div>
          <div style={{ marginTop: 3, height: 9, background: "rgba(0,0,0,0.35)", borderRadius: 99, overflow: "hidden" }}
            onClick={(e) => { e.stopPropagation(); setAvanceModal(c); }} title="Ver detalle de etapas">
            <div style={{ width: `${Math.min(c.avance?.pct || 0, 100)}%`, height: "100%", borderRadius: 99,
              background: colorAvance(c.avance?.pct || 0) }} />
          </div>
        </div>
      </div>

      {/* ── 🧠 RESUMEN DEL HILO IA: en qué quedó la conversación (siempre visible) ── */}
      {(() => {
        const rh = resumen || c.resumen_hilo;
        return (
          <div data-testid={`resumen-hilo-${c.id}`} style={{ marginTop: 8, display: "flex", gap: 8,
            alignItems: "flex-start", background: "rgba(96,165,250,0.08)", borderLeft: "3px solid #60a5fa",
            borderRadius: 8, padding: "0.4rem 0.7rem" }}>
            <span style={{ fontSize: 14 }}>🧠</span>
            <span data-testid={`resumen-hilo-texto-${c.id}`} style={{ flex: 1, fontSize: 14,
              color: rh?.texto ? "#dbeafe" : "#64748b", fontStyle: rh?.texto ? "normal" : "italic",
              overflowWrap: "anywhere" }}>
              {genResumen ? "Generando resumen IA…" : (rh?.texto || "Sin resumen IA aún — se genera solo al detectar correos nuevos")}
              {rh?.en && !genResumen && <span style={{ color: "#64748b", fontSize: 11 }}> · {fFecha(rh.en)}</span>}
            </span>
            <button data-testid={`resumen-hilo-regenerar-${c.id}`} onClick={regenerarResumen} disabled={genResumen}
              title="Regenerar resumen IA del hilo"
              style={{ background: "transparent", border: "1px solid rgba(96,165,250,0.5)", color: "#93c5fd",
                borderRadius: 6, padding: "2px 8px", fontSize: 12, fontWeight: 700,
                cursor: genResumen ? "wait" : "pointer" }}>{genResumen ? "…" : "🔄"}</button>
          </div>
        );
      })()}

      {/* ── NOTAS: siempre visibles, nunca ocultas ── */}
      {notas.length > 0 && (
        <div data-testid={`notas-visibles-${c.id}`} style={{ marginTop: 10, display: "grid", gap: 6 }}>
          {notas.map((n, i) => (
            <div key={n.en || i} style={{ background: "rgba(212,175,55,0.08)", borderLeft: "3px solid #d4af37",
              borderRadius: 8, padding: "0.45rem 0.7rem" }}>
              <div style={{ fontSize: 15, color: "#f8fafc", overflowWrap: "anywhere" }}>📝 {n.texto}</div>
              <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 2 }}>
                {HITO_LABEL[n.hito] || n.hito} · {fFecha(n.en)}{n.por ? ` · ${n.por}` : ""}</div>
            </div>
          ))}
        </div>
      )}

      {/* ── AGREGAR NOTA: disponible desde cualquier estado ── */}
      {notaForm ? (
        <div data-testid={`nota-form-${c.id}`} style={{ marginTop: 8, display: "grid", gap: 6 }}>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            <select data-testid={`nota-hito-${c.id}`} value={notaForm.hito}
              onChange={e => setNotaForm(f => ({ ...f, hito: e.target.value }))}
              style={{ ...inputEdit, width: "auto", fontSize: 14 }}>
              {hitos.map(([h]) => <option key={h} value={h} style={{ background: "#0f172a" }}>{HITO_LABEL[h]}</option>)}
            </select>
            <button data-testid={`nota-guardar-${c.id}`} onClick={guardarNota} disabled={guardando}
              style={{ background: "#1A5C2A", color: "#fff", border: "none", borderRadius: 8,
                padding: "0.35rem 0.9rem", fontSize: 14, fontWeight: 800, cursor: "pointer" }}>Guardar</button>
            <button onClick={() => setNotaForm(null)} style={{ background: "transparent", color: "#94a3b8",
              border: "1px solid rgba(148,163,184,0.4)", borderRadius: 8, padding: "0.35rem 0.9rem",
              fontSize: 14, cursor: "pointer" }}>Cancelar</button>
          </div>
          <textarea autoFocus data-testid={`nota-texto-${c.id}`} value={notaForm.texto} maxLength={600}
            placeholder="Escribe la nota…" rows={2}
            onChange={e => setNotaForm(f => ({ ...f, texto: e.target.value }))}
            style={{ ...inputEdit, fontSize: 15, resize: "vertical" }} />
        </div>
      ) : (
        <button data-testid={`nota-agregar-${c.id}`} onClick={() => setNotaForm({ hito: hitos[0]?.[0] || "tasacion", texto: "" })}
          style={{ marginTop: 8, background: "rgba(212,175,55,0.12)", border: "1px dashed rgba(212,175,55,0.6)",
            color: "#d4af37", borderRadius: 8, padding: "0.3rem 0.8rem", fontSize: 14, fontWeight: 700, cursor: "pointer" }}>
          📝 Agregar nota</button>
      )}

      {/* ── CUERPO EXPANDIBLE ── */}
      {abierta && (
        <div data-testid={`tarjeta-cuerpo-${c.id}`} style={{ marginTop: 12, borderTop: "1px solid rgba(212,175,55,0.25)", paddingTop: 10 }}>
          {/* Campos de identidad: doble clic para editar · "Agregar..." si vacío */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: "8px 14px" }}>
            {CAMPOS_EDIT.map(([campo, label]) => (
              <div key={campo}>
                <div style={{ fontSize: 12, color: "#94a3b8", fontWeight: 800, textTransform: "uppercase", letterSpacing: 0.5 }}>{label}</div>
                <CampoEditable fid={c.id} campo={campo} label={label} manejar409={manejar409}
                  valor={campo === "monto" ? c.monto_uf : c[campo === "broker" ? "broker" : campo]}
                  onGuardado={recargar} testid={`campo-${campo}-${c.id}`} />
              </div>
            ))}
            <div>
              <div style={{ fontSize: 12, color: "#94a3b8", fontWeight: 800, textTransform: "uppercase", letterSpacing: 0.5 }}>📅 Fecha Firma</div>
              <div style={{ fontSize: 15, color: c.fecha_firma ? "#FFD700" : "#64748b", fontStyle: c.fecha_firma ? "normal" : "italic" }}>
                {c.fecha_firma ? String(c.fecha_firma).slice(0, 10) : "Sin fecha"}</div>
            </div>
          </div>

          {/* Hitos operativos: fila de íconos semáforo — tocar expande el hito */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 14 }}>
            {hitos.map(([h, est]) => {
              const s = semaforo(est);
              const activo = hitoAbierto === h;
              return (
                <button key={h} data-testid={`hito-chip-${h}-${c.id}`}
                  onClick={() => setHitoAbierto(activo ? null : h)}
                  title={`${HITO_LABEL[h]}: ${est || "Pendiente"} (${s.nivel})`}
                  style={{ background: activo ? "rgba(212,175,55,0.2)" : "rgba(2,6,23,0.5)",
                    border: `1px solid ${activo ? "#d4af37" : "rgba(148,163,184,0.3)"}`,
                    color: s.color, borderRadius: 999, padding: "6px 12px", fontSize: 14,
                    fontWeight: 800, cursor: "pointer" }}>
                  {s.icono} {HITO_LABEL[h]}
                </button>
              );
            })}
          </div>

          {/* Hito expandido: estado editable + notas del hito + panel completo */}
          {hitoAbierto && (() => {
            const est = (hitos.find(([h]) => h === hitoAbierto) || [])[1] || "Pendiente";
            const notasHito = notas.filter(n => n.hito === hitoAbierto);
            return (
              <div data-testid={`hito-expandido-${hitoAbierto}-${c.id}`}
                style={{ marginTop: 10, background: "rgba(2,6,23,0.45)", border: "1px solid rgba(212,175,55,0.3)",
                  borderRadius: 10, padding: "0.8rem 1rem" }}>
                <b style={{ color: "#d4af37", fontSize: 15 }}>{HITO_LABEL[hitoAbierto]}</b>
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center", marginTop: 8 }}>
                  <span style={{ fontSize: 14, color: "#94a3b8" }}>Estado:</span>
                  <select data-testid={`hito-estado-${hitoAbierto}-${c.id}`} value={est} disabled={guardando}
                    onChange={e => guardarEstado(hitoAbierto, e.target.value)}
                    style={{ ...inputEdit, width: "auto", fontSize: 15 }}>
                    {[...new Set([est, ...(ESTADOS_POR[hitoAbierto] || ["Pendiente"])])].map(x =>
                      <option key={x} value={x} style={{ background: "#0f172a" }}>{x}</option>)}
                  </select>
                  {c.manual?.[hitoAbierto] && <span style={{ fontSize: 12, color: "#eab308" }}>✍️ manual</span>}
                  {hitoAbierto === "estudio" && (
                    <button data-testid={`hito-solicitar-estudio-${c.id}`} onClick={() => abrirEstudio(c)}
                      style={{ background: "rgba(96,165,250,0.15)", border: "1px solid rgba(96,165,250,0.6)",
                        color: "#93c5fd", borderRadius: 8, padding: "0.3rem 0.8rem", fontSize: 13,
                        fontWeight: 800, cursor: "pointer" }}>📨 Solicitar Estudio</button>
                  )}
                  <button data-testid={`hito-panel-${hitoAbierto}-${c.id}`}
                    onClick={() => abrirPanel(c, hitoAbierto)}
                    style={{ marginLeft: "auto", background: "rgba(96,165,250,0.15)", border: "1px solid rgba(96,165,250,0.6)",
                      color: "#60a5fa", borderRadius: 8, padding: "0.3rem 0.8rem", fontSize: 13, fontWeight: 800, cursor: "pointer" }}>
                    🔎 Panel completo</button>
                </div>
                {notasHito.length > 0 && (
                  <div style={{ marginTop: 8, display: "grid", gap: 4 }}>
                    {notasHito.map((n, i) => (
                      <div key={n.en || i} style={{ fontSize: 14, color: "#e2e8f0" }}>
                        📝 {n.texto} <span style={{ color: "#64748b", fontSize: 12 }}>({fFecha(n.en)})</span></div>
                    ))}
                  </div>
                )}
              </div>
            );
          })()}

          {/* Documentos comerciales + acciones */}
          <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 12, flexWrap: "wrap" }}>
            <div title={c.docs_co_rs?.detalle || ""} style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {(c.docs_co_rs?.documentos || []).map((d, di) => (
                <span key={d.hito || di} title={`${d.label}: ${d.estado}`} style={{ fontSize: 13, fontWeight: 800,
                  color: { verde: "#4ade80", azul: "#93c5fd", amarillo: "#facc15", rojo: "#f87171" }[d.color] }}>
                  {d.icono} {d.label.split(" / ")[0]}</span>
              ))}
            </div>
            <button data-testid={`tarjeta-solicitar-${c.id}`} onClick={() => abrirSolicitud(c)}
              style={{ background: "rgba(96,165,250,0.15)", border: "1px solid rgba(96,165,250,0.6)",
                color: "#60a5fa", borderRadius: 8, padding: "0.35rem 0.9rem", fontSize: 14, fontWeight: 800, cursor: "pointer" }}>
              📨 Pedir Documentos</button>
            <button data-testid={`tarjeta-hilo-${c.id}`} onClick={verHilo}
              style={{ background: hilo ? "rgba(212,175,55,0.2)" : "rgba(2,6,23,0.5)",
                border: `1px solid ${hilo ? "#d4af37" : "rgba(148,163,184,0.4)"}`,
                color: hilo ? "#FFD700" : "#cbd5e1", borderRadius: 8, padding: "0.35rem 0.9rem",
                fontSize: 14, fontWeight: 800, cursor: "pointer" }}>
              🧵 Hilo del Cliente{hilo?.total != null ? ` (${hilo.total})` : ""}</button>
            {c.promesa_ia && <span style={{ fontSize: 13, color: c.promesa_ia.firmado ? "#4ade80" : "#93c5fd" }}
              title={c.promesa_ia.evidencia}>🤖 {c.promesa_ia.firmado ? "Firma verificada" : "Revisar firma"}</span>}
          </div>

          {/* 🧵 HILO DEL CLIENTE: línea de tiempo de correos enviados y recibidos */}
          {hilo && (
            <div data-testid={`hilo-timeline-${c.id}`} style={{ marginTop: 10, background: "rgba(2,6,23,0.45)",
              border: "1px solid rgba(212,175,55,0.3)", borderRadius: 10, padding: "0.8rem 1rem" }}>
              {hilo.loading ? <span style={{ color: "#94a3b8", fontSize: 14 }}>Cargando hilo…</span> : (<>
                <div style={{ fontSize: 13, color: "#94a3b8", fontWeight: 800, marginBottom: 8 }}>
                  {hilo.total} correo{hilo.total !== 1 ? "s" : ""} · 📤 {hilo.enviados} enviado{hilo.enviados !== 1 ? "s" : ""} · 📥 {hilo.recibidos} recibido{hilo.recibidos !== 1 ? "s" : ""}
                </div>
                {hilo.total === 0 && <span style={{ color: "#64748b", fontSize: 14, fontStyle: "italic" }}>
                  Aún no hay correos registrados para este cliente.</span>}
                <div style={{ display: "grid", gap: 0, maxHeight: 320, overflowY: "auto" }}>
                  {(hilo.eventos || []).map((e, i) => (
                    <div key={`${e.en}-${i}`} style={{ display: "flex", gap: 10, padding: "7px 0",
                      borderLeft: `3px solid ${e.tipo === "enviado" ? "#60a5fa" : "#4ade80"}`,
                      paddingLeft: 12, borderBottom: i < hilo.eventos.length - 1 ? "1px solid rgba(148,163,184,0.12)" : "none" }}>
                      <span style={{ fontSize: 15 }}>{e.tipo === "enviado" ? "📤" : "📥"}</span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 14, color: "#f8fafc", overflowWrap: "anywhere" }}>
                          {e.asunto || e.detalle || "(sin asunto)"}
                          {e.estado === "fallido" && <b style={{ color: "#f87171" }}> · 🔴 FALLIDO</b>}
                        </div>
                        <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 1 }}>
                          {e.tipo === "enviado" ? "Para" : "De"}: {e.con || "—"}{e.detalle && e.asunto ? ` · ${e.detalle}` : ""} · {fFecha(e.en)}
                        </div>
                        {(e.adjuntos || []).length > 0 && (
                          <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginTop: 4 }}>
                            {e.adjuntos.map((a) => (
                              <button key={a} data-testid={`hilo-adjunto-${c.id}`}
                                onClick={() => abrirAdjunto(a)} title={a}
                                style={{ background: "rgba(212,175,55,0.12)", border: "1px solid rgba(212,175,55,0.5)",
                                  color: "#d4af37", borderRadius: 6, padding: "2px 8px", fontSize: 12,
                                  fontWeight: 700, cursor: "pointer", maxWidth: 260, overflow: "hidden",
                                  textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                📄 {a.split("/").pop()}</button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </>)}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ─── Vista de tarjetas con barra superior fija ───
export const SupercarpetaCards = ({ clientes, recargar, abrirPanel, abrirSolicitud, abrirEstudio, setAvanceModal, manejar409 }) => {
  const [busqueda, setBusqueda] = useState("");
  const [filtro, setFiltro] = useState("todos");
  const conNotas = clientes.filter(c => (c.notas || []).length > 0).length;
  const pendientes = clientes.filter(c => (c.avance?.pct || 0) < 100).length;
  const completados = clientes.length - pendientes;
  const visibles = clientes.filter(c => {
    if (busqueda && !(c.cliente || "").toLowerCase().includes(busqueda.toLowerCase())) return false;
    if (filtro === "con_notas") return (c.notas || []).length > 0;
    if (filtro === "pendientes") return (c.avance?.pct || 0) < 100;
    if (filtro === "completados") return (c.avance?.pct || 0) >= 100;
    return true;
  });
  const btnFiltro = (id, label) => (
    <button key={id} data-testid={`filtro-${id}`} onClick={() => setFiltro(id)}
      style={{ background: filtro === id ? "rgba(212,175,55,0.25)" : "rgba(2,6,23,0.5)",
        border: `1px solid ${filtro === id ? "#d4af37" : "rgba(148,163,184,0.3)"}`,
        color: filtro === id ? "#FFD700" : "#cbd5e1", borderRadius: 999, padding: "5px 14px",
        fontSize: 14, fontWeight: 800, cursor: "pointer", whiteSpace: "nowrap" }}>{label}</button>
  );
  return (
    <div data-testid="vista-tarjetas">
      {/* Barra superior fija */}
      <div data-testid="tarjetas-barra" style={{ position: "sticky", top: 0, zIndex: 80,
        background: "rgba(15,23,42,0.97)", border: "1px solid rgba(212,175,55,0.35)", borderRadius: 12,
        padding: "0.7rem 0.9rem", marginBottom: 12, boxShadow: "0 8px 20px rgba(0,0,0,0.5)" }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <input data-testid="tarjetas-buscador" value={busqueda} onChange={e => setBusqueda(e.target.value)}
            placeholder="🔍 Buscar cliente por nombre…"
            style={{ ...inputEdit, maxWidth: 300, fontSize: 15 }} />
          {btnFiltro("todos", "Todos")}
          {btnFiltro("con_notas", "📝 Con notas")}
          {btnFiltro("pendientes", "Pendientes")}
          {btnFiltro("completados", "Completados")}
        </div>
        <div data-testid="tarjetas-contador" style={{ marginTop: 6, fontSize: 14, color: "#94a3b8", fontWeight: 700 }}>
          {clientes.length} cliente{clientes.length !== 1 ? "s" : ""} · {conNotas} con nota{conNotas !== 1 ? "s" : ""} · {pendientes} pendiente{pendientes !== 1 ? "s" : ""}{completados > 0 ? ` · ${completados} completado${completados !== 1 ? "s" : ""}` : ""}
        </div>
      </div>
      {/* Tarjetas apiladas verticalmente, ancho completo */}
      <div style={{ display: "grid", gap: 12 }}>
        {visibles.map((c, idx) => (
          <TarjetaCliente key={c.id} c={c} idx={clientes.indexOf(c)} recargar={recargar}
            abrirPanel={abrirPanel} abrirSolicitud={abrirSolicitud} abrirEstudio={abrirEstudio}
            setAvanceModal={setAvanceModal} manejar409={manejar409} />
        ))}
        {visibles.length === 0 && (
          <p style={{ color: "#94a3b8", textAlign: "center", padding: "1.5rem", fontSize: 15 }}>
            Sin clientes que coincidan con la búsqueda o el filtro.</p>
        )}
      </div>
    </div>
  );
};
