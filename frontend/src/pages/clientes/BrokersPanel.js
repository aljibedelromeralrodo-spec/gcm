import { useState } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

const BrokersPanel = ({ brokers, dest, setDest, reloadBrokers, soloAdmin }) => {
  const [nuevo, setNuevo] = useState({ nombre: "", contactos: "", emails: "" });
  const [showAdd, setShowAdd] = useState(false);
  const [editId, setEditId] = useState(null);
  const destList = dest.split(",").map(s => s.trim()).filter(Boolean);
  const isOn = (b) => (b.emails || []).length > 0 && b.emails.every(e => destList.some(d => d.toLowerCase() === e.toLowerCase()));
  const toggle = (b) => {
    if (isOn(b)) setDest(destList.filter(d => !b.emails.some(e => e.toLowerCase() === d.toLowerCase())).join(", "));
    else setDest([...destList, ...b.emails.filter(e => !destList.some(d => d.toLowerCase() === e.toLowerCase()))].join(", "));
  };
  const guardar = async () => {
    if (!nuevo.nombre.trim() || !nuevo.emails.trim()) return;
    try {
      if (editId) await axios.put(`${API}/api/brokers/${editId}`, nuevo);
      else await axios.post(`${API}/api/brokers`, nuevo);
      setNuevo({ nombre: "", contactos: "", emails: "" }); setShowAdd(false); setEditId(null);
      reloadBrokers();
    } catch (e) { console.error(e); }
  };
  const editar = (b) => {
    setEditId(b.id); setShowAdd(true);
    setNuevo({ nombre: b.nombre, contactos: b.contactos || "", emails: (b.emails || []).join(", ") });
  };
  const quitar = async (b) => {
    if (!window.confirm(`¿Quitar el broker "${b.nombre}"?`)) return;
    try { await axios.delete(`${API}/api/brokers/${b.id}`); reloadBrokers(); } catch (e) { console.error(e); }
  };
  const inpS = { padding: "0.4rem 0.6rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.3)", background: "#232326", color: "#e2e8f0", fontSize: 12 };
  return (
    <div data-testid="brokers-panel" style={{ background: "rgba(212,175,55,0.06)", border: "1px solid rgba(212,175,55,0.25)", borderRadius: 0, padding: "0.7rem 0.9rem" }}>
      <div style={{ opacity: 0.8, fontSize: 11, textTransform: "uppercase", marginBottom: 6, fontWeight: 700 }}>
        {soloAdmin ? "Plantillas de brokers (editar / agregar / quitar)" : "Brokers — marca para agregarlos al envío"}
      </div>
      <div style={{ display: "grid", gap: 4 }}>
        {brokers.map(b => (
          <div key={b.id} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5 }}>
            {soloAdmin ? (
              <span style={{ flex: 1 }}><b>{b.nombre}</b>{b.contactos ? ` — ${b.contactos}` : ""} <span style={{ opacity: 0.55 }}>({(b.emails || []).join(", ")})</span></span>
            ) : (
              <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", flex: 1 }}>
                <input type="checkbox" checked={isOn(b)} onChange={() => toggle(b)} data-testid={`broker-check-${b.id}`} />
                <span><b>{b.nombre}</b>{b.contactos ? ` — ${b.contactos}` : ""} <span style={{ opacity: 0.55 }}>({(b.emails || []).join(", ")})</span></span>
              </label>
            )}
            <button onClick={() => editar(b)} title="Editar broker" data-testid={`broker-edit-${b.id}`}
              style={{ background: "transparent", border: "none", color: "#d4af37", cursor: "pointer" }}><i className="fa fa-pencil" /></button>
            <button onClick={() => quitar(b)} title="Quitar broker" data-testid={`broker-del-${b.id}`}
              style={{ background: "transparent", border: "none", color: "#fb7185", cursor: "pointer" }}><i className="fa fa-trash" /></button>
          </div>
        ))}
      </div>
      {showAdd ? (
        <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
          <input value={nuevo.nombre} onChange={e => setNuevo({ ...nuevo, nombre: e.target.value })} placeholder="Nombre broker" data-testid="broker-new-nombre" style={{ ...inpS, flex: 1, minWidth: 110 }} />
          <input value={nuevo.contactos} onChange={e => setNuevo({ ...nuevo, contactos: e.target.value })} placeholder="Personas de contacto" data-testid="broker-new-contactos" style={{ ...inpS, flex: 1, minWidth: 130 }} />
          <input value={nuevo.emails} onChange={e => setNuevo({ ...nuevo, emails: e.target.value })} placeholder="correos separados por coma" data-testid="broker-new-emails" style={{ ...inpS, flex: 2, minWidth: 170 }} />
          <button onClick={guardar} data-testid="broker-new-save" style={{ ...inpS, background: "#0f52ba", border: "none", fontWeight: 700, cursor: "pointer" }}>{editId ? "Actualizar" : "Guardar"}</button>
          <button onClick={() => { setShowAdd(false); setEditId(null); setNuevo({ nombre: "", contactos: "", emails: "" }); }} style={{ ...inpS, background: "transparent", cursor: "pointer" }}>Cancelar</button>
        </div>
      ) : (
        <button onClick={() => setShowAdd(true)} data-testid="broker-add-btn" style={{ marginTop: 8, background: "transparent", border: "1px dashed rgba(212,175,55,0.5)", color: "#d4af37", borderRadius: 0, padding: "0.3rem 0.7rem", fontSize: 11.5, cursor: "pointer" }}>
          <i className="fa fa-plus" /> Agregar broker
        </button>
      )}
    </div>
  );
};

export default BrokersPanel;
