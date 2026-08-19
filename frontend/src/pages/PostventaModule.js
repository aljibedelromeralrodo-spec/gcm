import { useEffect, useState } from "react";
import axios from "axios";
import TrackerPasos from "../components/TrackerPasos";

const API = process.env.REACT_APP_BACKEND_URL;
const inp = { background: "rgba(2,6,23,0.7)", border: "1px solid rgba(240,171,252,0.35)", color: "#f8fafc",
  borderRadius: 8, padding: "0.45rem 0.65rem", fontSize: "0.85rem", boxSizing: "border-box" };
const btn = { background: "linear-gradient(135deg,#c084fc,#f0abfc)", color: "#1a0b1e", border: "none",
  borderRadius: 8, padding: "0.45rem 1rem", fontWeight: 800, cursor: "pointer", fontSize: "0.78rem" };

export default function PostventaModule({ user }) {
  const [data, setData] = useState(null);
  const [nuevo, setNuevo] = useState({ cliente: "", email: "" });
  const [plazosForm, setPlazosForm] = useState(null);
  const [busy, setBusy] = useState("");
  const [trackerOpen, setTrackerOpen] = useState({});
  const esAdmin = ["admin", "maestro"].includes(user?.rol);

  const cargar = () => axios.get(`${API}/api/postventa/panel`).then(r => {
    setData(r.data); setPlazosForm(p => p || { ...r.data.plazos });
  }).catch(() => setData({ casos: [], error: true }));
  useEffect(() => { cargar(); }, []);

  const crear = async () => {
    if (!nuevo.cliente.trim()) { window.alert("Ingrese el nombre del cliente"); return; }
    setBusy("crear");
    try {
      await axios.post(`${API}/api/postventa/casos`, nuevo);
      setNuevo({ cliente: "", email: "" }); cargar();
    } catch (e) { window.alert(e.response?.data?.detail || "Error al crear el caso"); }
    setBusy("");
  };
  const avanzar = async (c) => {
    if (!window.confirm(`¿Confirmar que la etapa "${c.etapa_label}" de ${c.cliente} fue completada?`)) return;
    setBusy(c.id);
    try {
      const r = await axios.post(`${API}/api/postventa/casos/${c.id}/avanzar`);
      window.alert(`✅ ${r.data.etapa_completada} completada en ${r.data.dias_reales} día(s) (${r.data.en_plazo ? "en plazo" : "FUERA de plazo"}).\n\n📩 Comunicación generada al cliente:\n"${r.data.comunicacion_cliente}"`);
      cargar();
    } catch (e) { window.alert(e.response?.data?.detail || "Error al avanzar etapa"); }
    setBusy("");
  };
  const guardarPlazos = async () => {
    setBusy("plazos");
    try {
      await axios.post(`${API}/api/postventa/plazos`, plazosForm);
      window.alert("✅ Plazos actualizados"); cargar();
    } catch (e) { window.alert(e.response?.data?.detail || "Error al guardar plazos"); }
    setBusy("");
  };

  if (!data) return <p style={{ color: "#94a3b8" }}>Cargando Postventa…</p>;
  return (
    <div data-testid="modulo-postventa" style={{ display: "grid", gap: 14 }}>
      <div style={{ background: "linear-gradient(135deg,#2a0f2e,#3b1740)", border: "1px solid rgba(240,171,252,0.35)",
        borderLeft: "5px solid #f0abfc", borderRadius: 14, padding: "1.2rem 1.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <h2 style={{ color: "#f0abfc", fontSize: "1.15rem", margin: 0 }}><i className="fa fa-heart" /> Postventa — Seguimiento de Escritura</h2>
          <span style={{ marginLeft: "auto", color: "#cbd5e1", fontSize: "0.75rem" }}>Responsable: <b>{data.responsable}</b></span>
        </div>
        <div style={{ display: "flex", gap: 16, marginTop: 10, flexWrap: "wrap", fontSize: "0.8rem" }}>
          <span style={{ color: "#e2e8f0" }}>📁 {data.total} caso{data.total !== 1 ? "s" : ""}</span>
          <span data-testid="pv-alertas" style={{ color: data.alertas_atraso ? "#f87171" : "#4ade80", fontWeight: 800 }}>
            {data.alertas_atraso ? `🚨 ${data.alertas_atraso} etapa(s) atrasada(s)` : "✅ Sin atrasos"}</span>
          <span style={{ color: "#94a3b8" }}>🎓 {data.escrituras_completadas} escritura(s) alimentando el aprendizaje</span>
        </div>
      </div>

      {/* Crear caso */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <input data-testid="pv-nuevo-cliente" style={{ ...inp, width: 240 }} placeholder="Nombre del cliente"
          value={nuevo.cliente} onChange={e => setNuevo(f => ({ ...f, cliente: e.target.value }))} />
        <input data-testid="pv-nuevo-email" style={{ ...inp, width: 240 }} placeholder="Correo del cliente (opcional)"
          value={nuevo.email} onChange={e => setNuevo(f => ({ ...f, email: e.target.value }))} />
        <button data-testid="pv-crear" style={btn} onClick={crear} disabled={busy === "crear"}>➕ Iniciar seguimiento</button>
      </div>

      {/* Plazos configurables (solo admin) */}
      {esAdmin && plazosForm && (
        <div data-testid="pv-plazos" style={{ background: "rgba(15,23,42,0.6)", border: "1px solid rgba(240,171,252,0.25)",
          borderRadius: 12, padding: "0.9rem 1.1rem" }}>
          <b style={{ color: "#f0abfc", fontSize: "0.85rem" }}>⏱ Plazos por etapa (días) — configurable por el Administrador</b>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 8, alignItems: "flex-end" }}>
            {(data.etapas || []).map(e => (
              <div key={e.clave}>
                <label style={{ color: "#94a3b8", fontSize: "0.65rem", fontWeight: 800, display: "block" }}>{e.label.toUpperCase()}
                  {data.plazos_aprendidos?.[e.clave] != null &&
                    <span style={{ color: "#4ade80" }}> · aprendido: {data.plazos_aprendidos[e.clave]}d</span>}</label>
                <input data-testid={`pv-plazo-${e.clave}`} type="number" min="1" max="365" style={{ ...inp, width: 90 }}
                  value={plazosForm[e.clave] ?? ""} onChange={ev => setPlazosForm(f => ({ ...f, [e.clave]: ev.target.value }))} />
              </div>
            ))}
            <button data-testid="pv-guardar-plazos" style={btn} onClick={guardarPlazos} disabled={busy === "plazos"}>💾 Guardar plazos</button>
          </div>
        </div>
      )}

      {/* Casos */}
      {(data.casos || []).length === 0 && <p style={{ color: "#64748b", fontStyle: "italic", fontSize: "0.85rem" }}>
        Sin casos de postventa aún — inicie el primer seguimiento arriba.</p>}
      {(data.casos || []).map(c => (
        <div key={c.id} data-testid={`pv-caso-${c.id}`} style={{ background: "rgba(15,23,42,0.6)",
          border: `1px solid ${c.atrasada ? "rgba(248,113,113,0.6)" : "rgba(240,171,252,0.25)"}`, borderRadius: 12, padding: "1rem 1.2rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <b style={{ color: "#f8fafc", fontSize: "0.95rem" }}>{c.cliente}</b>
            <span style={{ color: "#c084fc", fontSize: "0.75rem", fontWeight: 800 }}>Etapa: {c.etapa_label}</span>
            {c.atrasada && <span data-testid={`pv-alerta-${c.id}`} style={{ color: "#f87171", fontSize: "0.72rem", fontWeight: 800 }}>
              🚨 ATRASADA — {c.dias_en_etapa} días (plazo excedido)</span>}
            {c.etapa_actual !== "completado" ? (
              <button data-testid={`pv-avanzar-${c.id}`} style={{ ...btn, marginLeft: "auto" }} onClick={() => avanzar(c)}
                disabled={busy === c.id}>✔ Completar etapa</button>
            ) : <span style={{ marginLeft: "auto", color: "#4ade80", fontWeight: 800, fontSize: "0.8rem" }}>✅ Proceso completado</span>}
          </div>
          {/* Línea de etapas */}
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 10 }}>
            {c.etapas.map(e => (
              <span key={e.clave} title={`Plazo: ${e.plazo_dias}d${e.dias_reales != null ? ` · real: ${e.dias_reales}d` : ""}${e.en_tiempo_y_forma === false ? " · FUERA DE PLAZO" : ""}`}
                style={{ fontSize: "0.72rem", fontWeight: 800, borderRadius: 999, padding: "3px 10px",
                  border: "1px solid", whiteSpace: "nowrap",
                  color: e.completada ? (e.en_tiempo_y_forma ? "#4ade80" : "#facc15") : e.en_curso ? (e.atrasada ? "#f87171" : "#c084fc") : "#64748b",
                  borderColor: e.completada ? (e.en_tiempo_y_forma ? "#4ade8055" : "#facc1555") : e.en_curso ? "#c084fc66" : "#47556955" }}>
                {e.completada ? (e.en_tiempo_y_forma ? "✅" : "⚠️") : e.en_curso ? "⏳" : "○"} {e.etapa}
                {e.completada && e.dias_reales != null ? ` (${e.dias_reales}d)` : e.en_curso && e.dias_en_curso != null ? ` (${e.dias_en_curso}d/${e.plazo_dias}d)` : ""}
              </span>
            ))}
          </div>
          {(c.comunicaciones || []).length > 0 && (
            <div style={{ marginTop: 8, borderLeft: "3px solid #c084fc", paddingLeft: 10 }}>
              {c.comunicaciones.map((m, i) => (
                <p key={i} style={{ color: "#cbd5e1", fontSize: "0.72rem", margin: "4px 0" }}>
                  📩 <i>{m.texto}</i> <span style={{ color: "#64748b" }}>({String(m.generada).slice(0, 10)})</span></p>
              ))}
            </div>
          )}
          <div style={{ marginTop: 10 }}>
            <button data-testid={`pv-tracker-toggle-${c.id}`} onClick={() => setTrackerOpen(t => ({ ...t, [c.id]: !t[c.id] }))}
              style={{ background: "rgba(212,175,55,0.1)", color: "#d4af37", border: "1px solid rgba(212,175,55,0.4)",
                borderRadius: 8, padding: "0.32rem 0.85rem", cursor: "pointer", fontWeight: 800, fontSize: "0.68rem" }}>
              📜 {trackerOpen[c.id] ? "Ocultar" : "Tracker de Escritura"}</button>
            {trackerOpen[c.id] && (
              <div style={{ marginTop: 8 }}>
                <TrackerPasos tipo="escritura" refId={c.id} readOnly={user?.rol === "contralor"} />
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
