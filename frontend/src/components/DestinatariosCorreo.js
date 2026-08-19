import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const card = { background: "rgba(30,41,59,0.55)", border: "1px solid rgba(148,163,184,0.2)", borderRadius: 12, padding: "1rem", marginTop: 14 };
const inp = { background: "rgba(255,255,255,0.06)", border: "1px solid rgba(212,175,55,0.3)", color: "#fff", padding: "0.35rem 0.55rem", borderRadius: 8, fontSize: "0.7rem", boxSizing: "border-box" };
const goldBtn = { background: "linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C)", color: "#0a0a0a", border: "none", borderRadius: 8, padding: "0.32rem 0.75rem", fontWeight: 800, cursor: "pointer", fontSize: "0.66rem" };

const CAMPOS = [["to", "Para"], ["cc", "CC"], ["bcc", "CCO"]];

const ListaCorreos = ({ accionId, campo, label, correos, onAdd, onRemove }) => {
  const [nuevo, setNuevo] = useState("");
  const agregar = () => {
    const e = nuevo.trim().toLowerCase();
    if (!e) return;
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e)) { window.alert(`Correo inválido: ${e}`); return; }
    onAdd(campo, e);
    setNuevo("");
  };
  return (
    <div style={{ minWidth: 200, flex: "1 1 200px" }}>
      <div style={{ color: "#94a3b8", fontSize: "0.56rem", fontWeight: 800, letterSpacing: 1 }}>{label.toUpperCase()}</div>
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap", margin: "4px 0" }}>
        {(correos || []).map(e => (
          <span key={e} data-testid={`dest-chip-${accionId}-${campo}-${e}`}
            style={{ background: "rgba(212,175,55,0.12)", border: "1px solid rgba(212,175,55,0.4)", color: "#e2e8f0",
              borderRadius: 999, padding: "2px 8px", fontSize: "0.62rem", fontFamily: "monospace" }}>
            {e}
            <button data-testid={`dest-quitar-${accionId}-${campo}-${e}`} onClick={() => onRemove(campo, e)}
              style={{ background: "none", border: "none", color: "#f87171", cursor: "pointer", fontWeight: 900, marginLeft: 4, padding: 0 }}>×</button>
          </span>
        ))}
        {(correos || []).length === 0 && <span style={{ color: "#64748b", fontSize: "0.6rem", fontStyle: "italic" }}>Sin destinatarios</span>}
      </div>
      <div style={{ display: "flex", gap: 4 }}>
        <input data-testid={`dest-input-${accionId}-${campo}`} type="email" placeholder="correo@dominio.cl" value={nuevo}
          onChange={e => setNuevo(e.target.value)} onKeyDown={e => e.key === "Enter" && agregar()} style={{ ...inp, flex: 1 }} />
        <button data-testid={`dest-agregar-${accionId}-${campo}`} onClick={agregar}
          style={{ ...goldBtn, padding: "0.3rem 0.55rem" }}>+</button>
      </div>
    </div>
  );
};

const FilaAccion = ({ a, puedeEliminar, onGuardar, onProbar, onEliminar, busy }) => {
  const [draft, setDraft] = useState({ to: a.to || [], cc: a.cc || [], bcc: a.bcc || [] });
  const [dirty, setDirty] = useState(false);
  const add = (campo, e) => { if (!draft[campo].includes(e)) { setDraft(d => ({ ...d, [campo]: [...d[campo], e] })); setDirty(true); } };
  const rem = (campo, e) => { setDraft(d => ({ ...d, [campo]: d[campo].filter(x => x !== e) })); setDirty(true); };
  return (
    <div data-testid={`dest-accion-${a.accion_id}`} style={{ borderTop: "1px solid rgba(148,163,184,0.15)", padding: "0.8rem 0" }}>
      <div style={{ display: "flex", gap: 10, alignItems: "baseline", flexWrap: "wrap" }}>
        <b style={{ color: "#f8fafc", fontSize: "0.8rem" }}>{a.nombre}</b>
        {a.permanente && <span data-testid={`dest-permanente-${a.accion_id}`} style={{ fontSize: "0.54rem", fontWeight: 900, letterSpacing: 1, background: "rgba(239,68,68,0.15)", color: "#f87171", border: "1px solid rgba(239,68,68,0.5)", borderRadius: 5, padding: "0.12rem 0.5rem" }}>REGLA PERMANENTE</span>}
        {!a.base && <span style={{ fontSize: "0.54rem", fontWeight: 800, background: "rgba(96,165,250,0.15)", color: "#93c5fd", borderRadius: 5, padding: "0.12rem 0.5rem" }}>PERSONALIZADA</span>}
        <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          {dirty && <button data-testid={`dest-guardar-${a.accion_id}`} onClick={() => { onGuardar(a.accion_id, draft); setDirty(false); }} style={goldBtn}>💾 Guardar</button>}
          <button data-testid={`dest-probar-${a.accion_id}`} onClick={() => onProbar(a.accion_id)} disabled={busy === a.accion_id}
            style={{ background: "rgba(96,165,250,0.15)", color: "#93c5fd", border: "1px solid rgba(96,165,250,0.45)", borderRadius: 8, padding: "0.32rem 0.75rem", fontWeight: 800, cursor: "pointer", fontSize: "0.66rem" }}>
            {busy === a.accion_id ? "Enviando…" : "🧪 Enviar prueba"}</button>
          {puedeEliminar && !a.base && (
            <button data-testid={`dest-eliminar-${a.accion_id}`} onClick={() => onEliminar(a.accion_id)}
              style={{ background: "rgba(239,68,68,0.12)", color: "#f87171", border: "1px solid rgba(239,68,68,0.45)", borderRadius: 8, padding: "0.32rem 0.6rem", fontWeight: 800, cursor: "pointer", fontSize: "0.66rem" }}>🗑</button>
          )}
        </span>
      </div>
      {a.descripcion && <p style={{ color: "#94a3b8", fontSize: "0.62rem", margin: "3px 0 8px", lineHeight: 1.45 }}>{a.descripcion}</p>}
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
        {CAMPOS.map(([campo, label]) => (
          <ListaCorreos key={campo} accionId={a.accion_id} campo={campo} label={label}
            correos={draft[campo]} onAdd={add} onRemove={rem} />
        ))}
      </div>
    </div>
  );
};

export default function DestinatariosCorreo() {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState("");
  const [nueva, setNueva] = useState({ nombre: "", descripcion: "" });
  const [mostrarNueva, setMostrarNueva] = useState(false);

  const recargar = useCallback(() => {
    axios.get(`${API}/api/correo-destinatarios`).then(r => setData(r.data)).catch(() => setData({ error: true }));
  }, []);
  useEffect(() => { recargar(); }, [recargar]);

  const guardar = async (accionId, draft) => {
    try {
      await axios.put(`${API}/api/correo-destinatarios/${accionId}`, draft);
      recargar();
    } catch (e) { window.alert(e.response?.data?.detail || "No fue posible guardar los destinatarios"); }
  };
  const probar = async (accionId) => {
    setBusy(accionId);
    try {
      const r = await axios.post(`${API}/api/correo-destinatarios/${accionId}/prueba`);
      window.alert(`✅ Correo de prueba enviado a: ${(r.data.enviado_a || []).join(", ")}${(r.data.cc || []).length ? ` · CC: ${r.data.cc.join(", ")}` : ""}`);
    } catch (e) { window.alert(e.response?.data?.detail || "No fue posible enviar el correo de prueba"); }
    setBusy("");
  };
  const eliminar = async (accionId) => {
    if (!window.confirm("¿Eliminar esta acción de correo personalizada?")) return;
    try { await axios.delete(`${API}/api/correo-destinatarios/${accionId}`); recargar(); }
    catch (e) { window.alert(e.response?.data?.detail || "No fue posible eliminar la acción"); }
  };
  const crear = async () => {
    if (!nueva.nombre.trim()) { window.alert("Indique un nombre para la nueva acción"); return; }
    try {
      await axios.post(`${API}/api/correo-destinatarios`, nueva);
      setNueva({ nombre: "", descripcion: "" });
      setMostrarNueva(false);
      recargar();
    } catch (e) { window.alert(e.response?.data?.detail || "No fue posible crear la acción"); }
  };

  if (!data) return null;
  if (data.error) return null;
  return (
    <div style={card} data-testid="panel-destinatarios-correo">
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <h4 style={{ margin: 0, color: "#d4af37", fontSize: "0.85rem", letterSpacing: 1 }}>
          📧 DESTINATARIOS DE CORREO POR ACCIÓN</h4>
        <span style={{ color: "#64748b", fontSize: "0.6rem" }}>
          Editable por Admin y Gerencia Comercial · sin tocar código · pruebe antes de activar</span>
        {data.puede_crear && (
          <button data-testid="dest-nueva-accion-btn" onClick={() => setMostrarNueva(v => !v)}
            style={{ ...goldBtn, marginLeft: "auto" }}>+ Nueva acción</button>
        )}
      </div>
      {mostrarNueva && (
        <div data-testid="dest-nueva-accion-form" style={{ display: "flex", gap: 8, flexWrap: "wrap", margin: "10px 0", background: "rgba(2,6,23,0.5)", borderRadius: 10, padding: "0.7rem 0.9rem", border: "1px dashed rgba(212,175,55,0.4)" }}>
          <input data-testid="dest-nueva-nombre" placeholder="Nombre de la acción" value={nueva.nombre}
            onChange={e => setNueva({ ...nueva, nombre: e.target.value })} style={{ ...inp, flex: "1 1 220px" }} />
          <input data-testid="dest-nueva-descripcion" placeholder="Descripción (opcional)" value={nueva.descripcion}
            onChange={e => setNueva({ ...nueva, descripcion: e.target.value })} style={{ ...inp, flex: "2 1 300px" }} />
          <button data-testid="dest-nueva-crear" onClick={crear} style={goldBtn}>Crear</button>
        </div>
      )}
      {(data.acciones || []).map(a => (
        <FilaAccion key={a.accion_id} a={a} puedeEliminar={data.puede_eliminar}
          onGuardar={guardar} onProbar={probar} onEliminar={eliminar} busy={busy} />
      ))}
    </div>
  );
}
