import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

export default function CierresModule() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [soloEntrega, setSoloEntrega] = useState(true);
  const [verTodos, setVerTodos] = useState(false);
  const [ventana, setVentana] = useState(null);
  const [recientes, setRecientes] = useState([]);
  const [msg, setMsg] = useState("");
  const [sending, setSending] = useState(null);
  const [edit, setEdit] = useState(null); // {id, ejecutivo_nombre, ejecutivo_email, proyecto, entrega_inmediata}

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/cierres`, { params: { solo_entrega_inmediata: soloEntrega } });
      setRows(r.data.cierres || []);
    } catch (e) {
      setMsg("Error cargando cierres: " + (e.response?.data?.detail || e.message));
    }
    setLoading(false);
  }, [soloEntrega]);

  useEffect(() => { load(); }, [load]);

  const guardarEdit = async () => {
    try {
      await axios.patch(`${API}/api/cierres/${edit.id}`, {
        ejecutivo_nombre: edit.ejecutivo_nombre, ejecutivo_email: edit.ejecutivo_email,
        proyecto: edit.proyecto, inmobiliaria: edit.inmobiliaria,
        entrega_inmediata: !!edit.entrega_inmediata,
      });
      setEdit(null);
      load();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
  };

  const consultar = async (r) => {
    setSending(r.id); setMsg("");
    try {
      const pre = await axios.post(`${API}/api/cierres/${r.id}/consultar`, { confirm: false });
      const ok = window.confirm(
        `📨 Preguntar al ejecutivo por ${r.nombre}\n\nPara: ${pre.data.to}\nAsunto: ${pre.data.subject}\n\n` +
        `El correo incluye dos botones de un clic:\n` +
        `✅ "Sí, el cliente continúa con ustedes — contáctenme para formalizar el crédito"\n` +
        `❌ "No, el cliente no continuará el crédito con ustedes" (al marcarlo, la carpeta se BORRA automáticamente de nuestro archivo)\n\n¿Enviar ahora?`);
      if (!ok) { setSending(null); return; }
      await axios.post(`${API}/api/cierres/${r.id}/consultar`, { confirm: true });
      setMsg(`✅ Consulta enviada a ${pre.data.to} por ${r.nombre}. Se volverá a avisar en 3 días.`);
      load();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setSending(null);
  };

  const marcarNoContinua = async (r) => {
    if (!window.confirm(`❌ ¿El ejecutivo confirmó que ${r.nombre} NO continuará el crédito con nosotros?`)) return;
    try {
      await axios.patch(`${API}/api/cierres/${r.id}`, { respuesta_final: "no_continua" });
      if (window.confirm(`¿Borrar la carpeta de ${r.nombre} de la base de datos?\n\n⚠️ Se elimina la carpeta con TODOS sus archivos y datos. Esta acción no se puede deshacer.`)) {
        await axios.delete(`${API}/api/clientes/folders/${r.id}`);
        setMsg(`🗑️ ${r.nombre}: marcado como NO continúa y carpeta eliminada de la base de datos.`);
      } else {
        setMsg(`❌ ${r.nombre}: marcado como NO continúa (la carpeta se conservó).`);
      }
      load();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
  };

  const fmtF = (iso) => { try { return new Date(iso).toLocaleDateString("es-CL"); } catch { return "—"; } };

  const grupos = rows.reduce((acc, r) => {
    const k = r.ejecutivo_nombre ? `${r.ejecutivo_nombre}${r.inmobiliaria ? ` — ${r.inmobiliaria}` : ""}` : "Sin ejecutivo asignado";
    (acc[k] = acc[k] || []).push(r);
    return acc;
  }, {});
  const pendientes = rows.filter(r => r.toca_preguntar).length;

  const inp = { width: "100%", padding: "0.45rem", borderRadius: 4, border: "1px solid rgba(148,163,184,0.3)", background: "#1e293b", color: "#e2e8f0", fontSize: 13 };

  return (
    <div data-testid="cierres-module" style={{ display: "grid", gap: "1rem" }}>
      <div style={{ background: "rgba(15,23,42,0.85)", border: "1px solid rgba(148,163,184,0.15)", borderRadius: 4, padding: "1.2rem 1.4rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <h2 style={{ margin: 0, fontSize: "1.15rem", color: "var(--gold, #d4af37)" }}>
            <i className="fa fa-handshake-o" /> Cierres — Seguimiento de aprobaciones enviadas
          </h2>
          {pendientes > 0 && (
            <span data-testid="cierres-pendientes-badge" style={{ background: "rgba(245,158,11,0.15)", border: "1.5px solid #f59e0b", color: "#fbbf24", borderRadius: 999, padding: "0.25rem 0.9rem", fontSize: 12.5, fontWeight: 800 }}>
              ⏰ {pendientes} cliente{pendientes !== 1 ? "s" : ""} por preguntar (regla: cada 3 días)
            </span>
          )}
          <label style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6, fontSize: 12.5, cursor: "pointer", color: "#94a3b8" }}>
            <input type="checkbox" checked={soloEntrega} data-testid="cierres-filtro-entrega"
              onChange={e => setSoloEntrega(e.target.checked)} /> Solo entrega inmediata
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12.5, cursor: "pointer", color: "#94a3b8" }}>
            <input type="checkbox" checked={verTodos} data-testid="cierres-filtro-todos"
              onChange={e => setVerTodos(e.target.checked)} /> Ver todos (sin ventana mensual)
          </label>
          <button onClick={load} data-testid="cierres-refresh" style={{ background: "rgba(148,163,184,0.1)", border: "1px solid rgba(148,163,184,0.3)", color: "#94a3b8", borderRadius: 4, padding: "0.4rem 0.9rem", fontSize: 12.5, cursor: "pointer" }}>
            <i className="fa fa-refresh" /> Actualizar
          </button>
        </div>
        <p style={{ margin: "0.6rem 0 0", fontSize: 12.5, color: "#94a3b8" }}>
          Barrido inicial: desde el último domingo, un mes hacia atrás{ventana ? ` (${fmtF(ventana.desde)} → ${fmtF(ventana.hasta_domingo)})` : ""} — por única vez mensual.
          Luego, con el botón preguntás (clic por clic, envío manual) si el cliente va a continuar el crédito con nosotros,
          y a los 3 días de cada consulta el aviso se reactiva para volver a preguntar.
        </p>
        {msg && <div data-testid="cierres-msg" style={{ marginTop: 8, fontSize: 12.5, color: msg.startsWith("✅") ? "#4ade80" : "#f87171", fontWeight: 700 }}>{msg}</div>}
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: "2rem", color: "#94a3b8" }}><i className="fa fa-spinner fa-spin" /> Cargando aprobaciones…</div>
      ) : rows.length === 0 ? (
        <div data-testid="cierres-empty" style={{ textAlign: "center", padding: "2rem", color: "#94a3b8" }}>No hay aprobaciones enviadas{soloEntrega ? " con entrega inmediata" : ""}.</div>
      ) : Object.entries(grupos).map(([grupo, lista]) => (
        <div key={grupo} data-testid="cierres-grupo" style={{ background: "rgba(15,23,42,0.85)", border: "1px solid rgba(148,163,184,0.15)", borderRadius: 4, padding: "1rem 1.2rem" }}>
          <div style={{ fontWeight: 800, fontSize: 14, color: "#e2e8f0", marginBottom: 10 }}>
            <i className="fa fa-user-circle-o" style={{ color: "var(--gold, #d4af37)" }} /> {grupo} <span style={{ opacity: 0.6, fontWeight: 600 }}>({lista.length})</span>
          </div>
          <div style={{ display: "grid", gap: 8 }}>
            {lista.map(r => (
              <div key={r.id} data-testid={`cierre-row-${r.id}`} style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", background: r.toca_preguntar ? "rgba(245,158,11,0.06)" : "rgba(30,41,59,0.6)", border: r.toca_preguntar ? "1.5px solid rgba(245,158,11,0.4)" : "1px solid rgba(148,163,184,0.12)", borderRadius: 4, padding: "0.7rem 1rem" }}>
                <div style={{ flex: "1 1 220px", minWidth: 200 }}>
                  <div style={{ fontWeight: 800, fontSize: 13.5 }}>{r.nombre} {r.rut && <span style={{ opacity: 0.6, fontWeight: 600 }}>· {r.rut}</span>}
                    {r.respuesta_final === "continua" && <span data-testid={`cierre-continua-${r.id}`} style={{ marginLeft: 8, background: "rgba(13,148,136,0.2)", color: "#2dd4bf", borderRadius: 999, padding: "2px 10px", fontSize: 11, fontWeight: 800 }}>✅ Confirmó que continúa</span>}
                  </div>
                  <div style={{ fontSize: 12, color: "#94a3b8" }}>
                    {r.proyecto ? <>Proyecto: <b>{r.proyecto}</b> · </> : ""}Aprobación: {fmtF(r.fecha_aprobacion)}
                    {r.entrega_inmediata && <span style={{ color: "#2dd4bf", fontWeight: 700 }}> · Entrega inmediata</span>}
                  </div>
                  <div style={{ fontSize: 11.5, color: r.toca_preguntar ? "#fbbf24" : "#64748b", fontWeight: 700 }}>
                    {r.ultima_consulta_at
                      ? `Última consulta: ${fmtF(r.ultima_consulta_at)} (hace ${r.dias_desde_consulta} día${r.dias_desde_consulta !== 1 ? "s" : ""}) · ${r.consultas} enviada${r.consultas !== 1 ? "s" : ""}${r.toca_preguntar ? " · ⏰ toca volver a preguntar" : ""}`
                      : "⏰ Nunca consultado — toca preguntar"}
                  </div>
                </div>
                <div style={{ fontSize: 12, color: "#94a3b8", flex: "0 1 240px" }}>
                  {r.ejecutivo_email
                    ? <><i className="fa fa-envelope-o" /> {r.ejecutivo_email}
                        {r.ejecutivo_desde_origen && <div style={{ fontSize: 10.5, color: "#d4af37", fontWeight: 700 }}>↩ tomado de la solicitud de crédito original</div>}
                      </>
                    : <span style={{ color: "#f87171" }}>Sin correo del ejecutivo</span>}
                </div>
                <div style={{ display: "flex", gap: 8, marginLeft: "auto" }}>
                  <button data-testid={`cierre-edit-${r.id}`} onClick={() => setEdit({ ...r })}
                    style={{ background: "rgba(148,163,184,0.1)", border: "1px solid rgba(148,163,184,0.3)", color: "#94a3b8", borderRadius: 4, padding: "0.45rem 0.9rem", fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
                    <i className="fa fa-pencil" /> Editar
                  </button>
                  <button data-testid={`cierre-consultar-${r.id}`} onClick={() => consultar(r)} disabled={sending === r.id}
                    title="Enviar correo al ejecutivo preguntando si el cliente continúa el crédito con nosotros"
                    style={{ background: r.toca_preguntar ? "#0d9488" : "rgba(13,148,136,0.25)", border: "none", color: "#fff", borderRadius: 4, padding: "0.45rem 1rem", fontSize: 12, fontWeight: 800, cursor: "pointer" }}>
                    <i className={`fa ${sending === r.id ? "fa-spinner fa-spin" : "fa-paper-plane"}`} /> Preguntar al ejecutivo
                  </button>
                  <button data-testid={`cierre-no-continua-${r.id}`} onClick={() => marcarNoContinua(r)}
                    title="El ejecutivo respondió que el cliente NO continuará el crédito — permite borrar la carpeta de la base de datos"
                    style={{ background: "rgba(185,28,28,0.15)", border: "1.5px solid #b91c1c", color: "#f87171", borderRadius: 4, padding: "0.45rem 0.9rem", fontSize: 12, fontWeight: 800, cursor: "pointer" }}>
                    <i className="fa fa-times-circle" /> No continúa
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}

      {edit && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.65)", zIndex: 9998, display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }} onClick={() => setEdit(null)}>
          <div data-testid="cierre-edit-modal" onClick={e => e.stopPropagation()} style={{ background: "#0f172a", border: "1px solid rgba(148,163,184,0.25)", borderRadius: 4, padding: "1.4rem", width: "min(480px, 96vw)", display: "grid", gap: 10 }}>
            <h3 style={{ margin: 0, fontSize: 15, color: "var(--gold, #d4af37)" }}>Editar cierre — {edit.nombre}</h3>
            <label style={{ fontSize: 12 }}>Nombre del ejecutivo
              <input style={inp} data-testid="cierre-edit-ejecutivo" value={edit.ejecutivo_nombre || ""} onChange={e => setEdit({ ...edit, ejecutivo_nombre: e.target.value })} placeholder="Ej: Carla" />
            </label>
            <label style={{ fontSize: 12 }}>Correo del ejecutivo *
              <input style={inp} data-testid="cierre-edit-email" value={edit.ejecutivo_email || ""} onChange={e => setEdit({ ...edit, ejecutivo_email: e.target.value })} placeholder="ejecutivo@inmobiliaria.cl" />
            </label>
            <label style={{ fontSize: 12 }}>Inmobiliaria
              <input style={inp} data-testid="cierre-edit-inmobiliaria" value={edit.inmobiliaria || ""} onChange={e => setEdit({ ...edit, inmobiliaria: e.target.value })} placeholder="Ej: Ecomac" />
            </label>
            <label style={{ fontSize: 12 }}>Proyecto
              <input style={inp} data-testid="cierre-edit-proyecto" value={edit.proyecto || ""} onChange={e => setEdit({ ...edit, proyecto: e.target.value })} placeholder="Ej: Condominio Portal Cerro Grande" />
            </label>
            <label style={{ fontSize: 12.5, display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
              <input type="checkbox" checked={!!edit.entrega_inmediata} data-testid="cierre-edit-entrega" onChange={e => setEdit({ ...edit, entrega_inmediata: e.target.checked })} /> Entrega inmediata
            </label>
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button onClick={() => setEdit(null)} style={{ background: "transparent", border: "1px solid rgba(148,163,184,0.3)", color: "#94a3b8", borderRadius: 4, padding: "0.5rem 1rem", fontSize: 12.5, cursor: "pointer" }}>Cancelar</button>
              <button data-testid="cierre-edit-guardar" onClick={guardarEdit} style={{ background: "var(--gold, #d4af37)", border: "none", color: "#0f172a", borderRadius: 4, padding: "0.5rem 1.2rem", fontSize: 12.5, fontWeight: 800, cursor: "pointer" }}>Guardar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
