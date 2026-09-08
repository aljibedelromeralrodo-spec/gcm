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
      className="w-full rounded-xl"
      style={{ background: idx % 2 === 0 ? "#1E2A3A" : "#233145",
        border: `1px solid ${c.hilo_frio ? "rgba(239,68,68,0.75)" : "rgba(212,175,55,0.35)"}`,
        boxShadow: c.hilo_frio ? "0 0 14px rgba(239,68,68,0.22)" : "none",
        padding: "1rem 1.15rem 0.85rem" }}>

      {/* ── ZONA 1 · Cabecera: nombre + tipo a la izquierda · % / barra a la derecha ── */}
      <div data-testid={`tarjeta-encabezado-${c.id}`} onClick={() => setAbierta(a => !a)}
        className="flex items-start justify-between gap-4 cursor-pointer">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <b className="text-white text-[19px] font-semibold break-words">
              <span style={{ color: "#D4AF37" }}>{idx + 1}.</span> {c.cliente}
            </b>
            {c.hilo_frio && (
              <span data-testid={`hilo-frio-${c.id}`}
                title={`Hilo sin movimiento hace más de 7 días${c.hilo_ultimo ? ` (último: ${c.hilo_ultimo})` : ""} — reactivar contacto`}
                className="text-xs font-black tracking-wide"
                style={{ background: "rgba(239,68,68,0.18)", border: "1px solid rgba(239,68,68,0.7)",
                  color: "#f87171", borderRadius: 999, padding: "2px 10px" }}>
                ⚠ HILO FRÍO +7D</span>
            )}
            {notas.length > 0 && (
              <span data-testid={`badge-nota-${c.id}`} title={`${notas.length} nota(s)`}
                className="text-[13px] font-extrabold"
                style={{ background: "rgba(212,175,55,0.2)", border: "1px solid rgba(212,175,55,0.7)",
                  color: "#FFD700", borderRadius: 999, padding: "2px 10px" }}>
                📝 {notas.length}</span>
            )}
          </div>
          <div className="mt-1 flex items-center gap-2 flex-wrap">
            {c.subsidio && (
              <span className="text-xs font-semibold uppercase tracking-wide text-white px-2 py-0.5 rounded-full"
                style={{ background: c.subsidio.toLowerCase().startsWith("con") ? "#2E7D32" : "#37474F" }}>
                {c.subsidio}</span>
            )}
            {c.monto_uf ? (
              <span className="text-sm font-medium" style={{ color: "#D4AF37" }}>
                {Number(c.monto_uf).toLocaleString("es-CL")} UF</span>
            ) : null}
          </div>
        </div>
        <div className="shrink-0 w-[168px] text-right" onClick={(e) => { e.stopPropagation(); setAvanceModal(c); }}
          title="Ver detalle de etapas">
          <div className="flex items-baseline justify-end gap-2">
            <span className="text-xs uppercase tracking-wide text-gray-500">Avance</span>
            <b className="text-sm font-medium"
              style={{ color: (c.avance?.pct || 0) >= 100 ? "#FFD700" : "#f8fafc" }}>{c.avance?.pct ?? 0}%</b>
            <span className="text-slate-500 text-sm">{abierta ? "▲" : "▼"}</span>
          </div>
          <div className="mt-1.5 h-2 rounded-full overflow-hidden" style={{ background: "rgba(0,0,0,0.35)" }}>
            <div style={{ width: `${Math.min(c.avance?.pct || 0, 100)}%`, height: "100%",
              background: colorAvance(c.avance?.pct || 0) }} />
          </div>
        </div>
      </div>

      {/* ── ZONA 2 · Datos estructurales ── */}
      <div className="mt-3 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-x-4 gap-y-3 rounded-lg px-3 py-2.5 bg-black/50">
        {CAMPOS_EDIT.map(([campo, label]) => (
          <div key={campo}>
            <div className="text-xs text-gray-500 uppercase tracking-wide">{label}</div>
            <CampoEditable fid={c.id} campo={campo} label={label} manejar409={manejar409}
              valor={campo === "monto" ? c.monto_uf : c[campo === "broker" ? "broker" : campo]}
              onGuardado={recargar} testid={`campo-${campo}-${c.id}`} />
          </div>
        ))}
        <div>
          <div className="text-xs text-gray-500 uppercase tracking-wide">Fecha Firma</div>
          <div className={`text-sm font-medium ${c.fecha_firma ? "text-white" : "text-gray-500 italic"}`}
            style={c.fecha_firma ? { color: "#FFD700" } : undefined}>
            {c.fecha_firma ? String(c.fecha_firma).slice(0, 10) : "Sin fecha"}</div>
        </div>
      </div>

      {/* ── ZONA 3 · Pipeline de hitos (stepper) ── */}
      <div className="mt-3 overflow-x-auto pb-1" style={{ scrollbarWidth: "thin" }}>
        <div className="flex items-start min-w-min">
          {hitos.map(([h, est], i) => {
            const s = semaforo(est);
            const activo = hitoAbierto === h;
            return (
              <div key={h} className="flex items-start">
                <button type="button" data-testid={`hito-chip-${h}-${c.id}`}
                  onClick={() => setHitoAbierto(activo ? null : h)}
                  title={`${HITO_LABEL[h]}: ${est || "Pendiente"} (${s.nivel})`}
                  className="flex flex-col items-center gap-1 px-1 py-0.5 bg-transparent border-0 cursor-pointer min-w-[72px]">
                  <span className="w-3 h-3 rounded-full shrink-0"
                    style={{ background: s.color, boxShadow: activo ? `0 0 0 3px ${s.color}55` : `0 0 0 2px ${s.color}22` }} />
                  <span className="text-[11px] font-medium text-center leading-tight" style={{ color: s.color }}>
                    {{ tasacion: "Tasación", estudio: "Estudio", serviu: "Serviu", carta_oferta: "Oferta",
                       promesa: "Promesa", set_credito: "Cédula", carpeta_notaria: "Notaría",
                       escritura: "Escritura" }[h] || HITO_LABEL[h]}</span>
                </button>
                {i < hitos.length - 1 && (
                  <div className="w-8 h-px mt-1.5 shrink-0" style={{ background: "rgba(148,163,184,0.35)" }} />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Detalle del hito: mismos handlers, debajo del stepper */}
      {hitoAbierto && (() => {
        const est = (hitos.find(([h]) => h === hitoAbierto) || [])[1] || "Pendiente";
        const notasHito = notas.filter(n => n.hito === hitoAbierto);
        return (
          <div data-testid={`hito-expandido-${hitoAbierto}-${c.id}`}
            className="mt-2.5 rounded-[10px] px-4 py-3"
            style={{ background: "rgba(2,6,23,0.45)", border: "1px solid rgba(212,175,55,0.3)" }}>
            <b className="text-[15px]" style={{ color: "#d4af37" }}>{HITO_LABEL[hitoAbierto]}</b>
            <div className="flex gap-2.5 flex-wrap items-center mt-2">
              <span className="text-sm text-slate-400">Estado:</span>
              <select data-testid={`hito-estado-${hitoAbierto}-${c.id}`} value={est} disabled={guardando}
                onChange={e => guardarEstado(hitoAbierto, e.target.value)}
                style={{ ...inputEdit, width: "auto", fontSize: 15 }}>
                {[...new Set([est, ...(ESTADOS_POR[hitoAbierto] || ["Pendiente"])])].map(x =>
                  <option key={x} value={x} style={{ background: "#0f172a" }}>{x}</option>)}
              </select>
              {c.manual?.[hitoAbierto] && <span className="text-xs" style={{ color: "#eab308" }}>✍️ manual</span>}
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
              <div className="mt-2 grid gap-1">
                {notasHito.map((n, i) => (
                  <div key={n.en || i} className="text-sm text-slate-200">
                    📝 {n.texto} <span className="text-xs text-gray-500">({fFecha(n.en)})</span></div>
                ))}
              </div>
            )}
          </div>
        );
      })()}

      {notas.length > 0 && (
        <div data-testid={`notas-visibles-${c.id}`} className="mt-3 grid gap-1.5">
          {notas.map((n, i) => (
            <div key={n.en || i} className="rounded-lg px-3 py-1.5"
              style={{ background: "rgba(212,175,55,0.08)", borderLeft: "3px solid #d4af37" }}>
              <div className="text-sm text-white break-words">📝 {n.texto}</div>
              <div className="text-xs text-gray-500 mt-0.5">
                {HITO_LABEL[n.hito] || n.hito} · {fFecha(n.en)}{n.por ? ` · ${n.por}` : ""}</div>
            </div>
          ))}
        </div>
      )}

      {notaForm && (
        <div data-testid={`nota-form-${c.id}`} className="mt-2 grid gap-1.5">
          <div className="flex gap-1.5 flex-wrap">
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
      )}

      {/* ── ZONA 4 · Footer: resumen IA + acciones operativas ── */}
      <div className="mt-3 pt-2.5 flex flex-col sm:flex-row sm:items-center sm:justify-end gap-2"
        style={{ borderTop: "1px solid rgba(212,175,55,0.22)" }}>
        {(() => {
          const rh = resumen || c.resumen_hilo;
          return (
            <div data-testid={`resumen-hilo-${c.id}`} className="flex-1 min-w-0 flex gap-2 items-start rounded-lg px-2.5 py-1.5"
              style={{ background: "rgba(96,165,250,0.08)", borderLeft: "3px solid #60a5fa" }}>
              <span className="text-sm">🧠</span>
              <span data-testid={`resumen-hilo-texto-${c.id}`} className="flex-1 text-sm break-words"
                style={{ color: rh?.texto ? "#dbeafe" : "#64748b", fontStyle: rh?.texto ? "normal" : "italic" }}>
                {genResumen ? "Generando resumen IA…" : (rh?.texto || "Sin resumen IA aún — se genera solo al detectar correos nuevos")}
                {rh?.en && !genResumen && <span className="text-[11px] text-gray-500"> · {fFecha(rh.en)}</span>}
              </span>
              <button data-testid={`resumen-hilo-regenerar-${c.id}`} onClick={regenerarResumen} disabled={genResumen}
                title="Regenerar resumen IA del hilo"
                style={{ background: "transparent", border: "1px solid rgba(96,165,250,0.5)", color: "#93c5fd",
                  borderRadius: 6, padding: "2px 8px", fontSize: 12, fontWeight: 700,
                  cursor: genResumen ? "wait" : "pointer" }}>{genResumen ? "…" : "🔄"}</button>
            </div>
          );
        })()}
        <div className="flex items-center justify-end gap-2 flex-wrap shrink-0">
          <div title={c.docs_co_rs?.detalle || ""} className="flex gap-2 flex-wrap">
            {(c.docs_co_rs?.documentos || []).map((d, di) => (
              <span key={d.hito || di} title={`${d.label}: ${d.estado}`} className="text-xs font-extrabold"
                style={{ color: { verde: "#4ade80", azul: "#93c5fd", amarillo: "#facc15", rojo: "#f87171" }[d.color] }}>
                {d.icono} {d.label.split(" / ")[0]}</span>
            ))}
          </div>
          {c.promesa_ia && <span className="text-xs" style={{ color: c.promesa_ia.firmado ? "#4ade80" : "#93c5fd" }}
            title={c.promesa_ia.evidencia}>🤖 {c.promesa_ia.firmado ? "Firma verificada" : "Revisar firma"}</span>}
          {!notaForm && (
            <button data-testid={`nota-agregar-${c.id}`} onClick={() => setNotaForm({ hito: hitos[0]?.[0] || "tasacion", texto: "" })}
              style={{ background: "rgba(212,175,55,0.12)", border: "1px dashed rgba(212,175,55,0.6)",
                color: "#d4af37", borderRadius: 8, padding: "0.3rem 0.8rem", fontSize: 13, fontWeight: 700, cursor: "pointer" }}>
              📝 Agregar nota</button>
          )}
          <button data-testid={`tarjeta-solicitar-${c.id}`} onClick={() => abrirSolicitud(c)}
            style={{ background: "rgba(96,165,250,0.15)", border: "1px solid rgba(96,165,250,0.6)",
              color: "#60a5fa", borderRadius: 8, padding: "0.35rem 0.9rem", fontSize: 13, fontWeight: 800, cursor: "pointer" }}>
            📨 Pedir Documentos</button>
          <button data-testid={`tarjeta-hilo-${c.id}`} onClick={verHilo}
            style={{ background: hilo ? "rgba(212,175,55,0.2)" : "rgba(2,6,23,0.5)",
              border: `1px solid ${hilo ? "#d4af37" : "rgba(148,163,184,0.4)"}`,
              color: hilo ? "#FFD700" : "#cbd5e1", borderRadius: 8, padding: "0.35rem 0.9rem",
              fontSize: 13, fontWeight: 800, cursor: "pointer" }}>
            🧵 Hilo del Cliente{hilo?.total != null ? ` (${hilo.total})` : ""}</button>
        </div>
      </div>

      {abierta && <div data-testid={`tarjeta-cuerpo-${c.id}`} />}

      {hilo && (
        <div data-testid={`hilo-timeline-${c.id}`} className="mt-2.5 rounded-[10px] px-4 py-3"
          style={{ background: "rgba(2,6,23,0.45)", border: "1px solid rgba(212,175,55,0.3)" }}>
          {hilo.loading ? <span className="text-sm text-slate-400">Cargando hilo…</span> : (<>
            <div className="text-[13px] text-slate-400 font-extrabold mb-2">
              {hilo.total} correo{hilo.total !== 1 ? "s" : ""} · 📤 {hilo.enviados} enviado{hilo.enviados !== 1 ? "s" : ""} · 📥 {hilo.recibidos} recibido{hilo.recibidos !== 1 ? "s" : ""}
            </div>
            {hilo.total === 0 && <span className="text-sm text-gray-500 italic">
              Aún no hay correos registrados para este cliente.</span>}
            <div className="grid gap-0 max-h-80 overflow-y-auto">
              {(hilo.eventos || []).map((e, i) => (
                <div key={`${e.en}-${i}`} className="flex gap-2.5 py-1.5 pl-3"
                  style={{ borderLeft: `3px solid ${e.tipo === "enviado" ? "#60a5fa" : "#4ade80"}`,
                    borderBottom: i < hilo.eventos.length - 1 ? "1px solid rgba(148,163,184,0.12)" : "none" }}>
                  <span className="text-[15px]">{e.tipo === "enviado" ? "📤" : "📥"}</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-white break-words">
                      {e.asunto || e.detalle || "(sin asunto)"}
                      {e.estado === "fallido" && <b style={{ color: "#f87171" }}> · 🔴 FALLIDO</b>}
                    </div>
                    <div className="text-xs text-slate-400 mt-px">
                      {e.tipo === "enviado" ? "Para" : "De"}: {e.con || "—"}{e.detalle && e.asunto ? ` · ${e.detalle}` : ""} · {fFecha(e.en)}
                    </div>
                    {(e.adjuntos || []).length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-1">
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
