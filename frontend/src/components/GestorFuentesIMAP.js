import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const ETIQUETAS = ["Tasador", "Abogado", "Notaría", "Inmobiliaria", "Banco", "Otro"];
const inp = { background: "rgba(255,255,255,0.06)", border: "1px solid rgba(212,175,55,0.3)",
  color: "#fff", padding: "0.45rem 0.6rem", borderRadius: 8, fontSize: "0.74rem", boxSizing: "border-box" };

export const GestorFuentesIMAP = ({ panel, titulo }) => {
  const [correo, setCorreo] = useState("");
  const [aliados, setAliados] = useState([]);
  const [claveModal, setClaveModal] = useState(false);
  const [clave, setClave] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const cargar = useCallback(() => {
    axios.get(`${API}/api/fuentes/${panel}`).then(r => {
      setCorreo(r.data.correo_principal || "");
      setAliados(r.data.aliados || []);
    }).catch(() => {});
  }, [panel]);
  useEffect(() => { cargar(); setMsg(""); }, [cargar]);

  const setAl = (i, k, v) => setAliados(a => a.map((x, j) => (j === i ? { ...x, [k]: v } : x)));

  const guardar = async () => {
    setBusy(true); setMsg("");
    try {
      const r = await axios.post(`${API}/api/fuentes/${panel}`, {
        correo_principal: correo, aliados, clave });
      setMsg(`✅ Fuentes guardadas y firmadas — ${r.data.cambios_auditados} cambio(s) auditados por DashAI (Regla #36)`);
      setClaveModal(false); setClave("");
      cargar();
    } catch (e) { setMsg(`⛔ ${e.response?.data?.detail || "Error al guardar"}`); }
    setBusy(false);
  };

  return (
    <div data-testid={`fuentes-imap-${panel}`} style={{ marginTop: 14, background: "rgba(30,41,59,0.55)",
      border: "1px solid rgba(212,175,55,0.35)", borderRadius: 12, padding: "1rem" }}>
      <div style={{ color: "#d4af37", fontWeight: 800, fontSize: "0.8rem", marginBottom: 4 }}>
        <i className="fa fa-plug" style={{ marginRight: 6 }} />Configuración de Fuentes IMAP — {titulo || panel}
      </div>
      <p style={{ color: "#94a3b8", fontSize: "0.66rem", margin: "0 0 10px", lineHeight: 1.5 }}>
        Correo principal + hasta 3 aliados externos con etiqueta obligatoria. DashAI solo escucha las fuentes activas;
        si borra un correo, el sistema deja de escucharlo de inmediato (Regla de Oro #36).
      </p>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 10 }}>
        <label style={{ color: "#e2e8f0", fontSize: "0.7rem", fontWeight: 700 }}>Correo principal:</label>
        <input data-testid={`fuentes-correo-principal-${panel}`} style={{ ...inp, flex: "1 1 240px" }}
          placeholder="usuario@centralmutuos.cl" value={correo} onChange={e => setCorreo(e.target.value)} />
      </div>
      {aliados.map((a, i) => (
        <div key={i} style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 6, alignItems: "center" }}>
          <input data-testid={`fuentes-aliado-nombre-${panel}-${i}`} style={{ ...inp, flex: "1 1 150px" }}
            placeholder="Nombre aliado (ej. Value Property)" value={a.nombre || ""} onChange={e => setAl(i, "nombre", e.target.value)} />
          <input data-testid={`fuentes-aliado-email-${panel}-${i}`} style={{ ...inp, flex: "1 1 200px" }}
            placeholder="correo@aliado.cl" value={a.email || ""} onChange={e => setAl(i, "email", e.target.value)} />
          <select data-testid={`fuentes-aliado-etiqueta-${panel}-${i}`} style={{ ...inp, flex: "0 1 130px" }}
            value={a.etiqueta || ""} onChange={e => setAl(i, "etiqueta", e.target.value)}>
            <option value="">Etiqueta *</option>
            {ETIQUETAS.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <button data-testid={`fuentes-aliado-borrar-${panel}-${i}`} onClick={() => setAliados(al => al.filter((_, j) => j !== i))}
            title="Eliminar fuente (deja de escucharse al guardar)"
            style={{ background: "rgba(239,68,68,0.12)", border: "1px solid #ef4444", color: "#ef4444",
              borderRadius: 8, padding: "0.4rem 0.6rem", cursor: "pointer", fontSize: "0.7rem" }}>✕</button>
        </div>
      ))}
      <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
        {aliados.length < 3 && (
          <button data-testid={`fuentes-agregar-aliado-${panel}`} onClick={() => setAliados(a => [...a, { nombre: "", email: "", etiqueta: "" }])}
            style={{ background: "transparent", border: "1px dashed rgba(212,175,55,0.5)", color: "#d4af37",
              borderRadius: 8, padding: "0.4rem 0.8rem", cursor: "pointer", fontSize: "0.7rem", fontWeight: 700 }}>
            + Agregar aliado ({aliados.length}/3)
          </button>
        )}
        <button data-testid={`fuentes-guardar-${panel}`} onClick={() => setClaveModal(true)}
          style={{ background: "linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C)", color: "#0a0a0a",
            border: "none", borderRadius: 8, padding: "0.4rem 1rem", fontWeight: 800, cursor: "pointer", fontSize: "0.72rem" }}>
          <i className="fa fa-lock" /> Guardar cambios (firma digital)
        </button>
      </div>
      {msg && <p data-testid={`fuentes-msg-${panel}`} style={{ color: msg.startsWith("✅") ? "#22c55e" : "#ef4444", fontSize: "0.68rem", marginTop: 8 }}>{msg}</p>}
      {claveModal && (
        <div data-testid={`fuentes-clave-modal-${panel}`} onClick={() => setClaveModal(false)}
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", zIndex: 700, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div onClick={e => e.stopPropagation()} style={{ background: "#111214", border: "1.5px solid #d4af37", borderRadius: 12, padding: "1.4rem", width: 380, maxWidth: "92vw" }}>
            <h4 style={{ color: "#d4af37", margin: "0 0 6px", fontSize: "0.9rem" }}>🔐 Firma Digital — Regla de Oro #36</h4>
            <p style={{ color: "#94a3b8", fontSize: "0.68rem", margin: "0 0 12px", lineHeight: 1.5 }}>
              Todo cambio en la red de escucha queda registrado en el Log de Auditoría de Red de DashAI con su identidad.
            </p>
            <input data-testid={`fuentes-clave-input-${panel}`} type="password" placeholder="Su clave personal"
              value={clave} onChange={e => setClave(e.target.value)}
              style={{ ...inp, width: "100%", marginBottom: 12 }} />
            <div style={{ display: "flex", gap: 8 }}>
              <button data-testid={`fuentes-clave-confirmar-${panel}`} onClick={guardar} disabled={busy || !clave}
                style={{ flex: 1, background: "#d4af37", color: "#0a0a0a", border: "none", borderRadius: 8, padding: "0.55rem", fontWeight: 800, cursor: "pointer" }}>
                {busy ? "Firmando…" : "Firmar y Guardar"}
              </button>
              <button onClick={() => setClaveModal(false)} style={{ background: "transparent", color: "#94a3b8", border: "1px solid rgba(255,255,255,0.2)", borderRadius: 8, padding: "0.55rem 1rem", cursor: "pointer" }}>Cancelar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default GestorFuentesIMAP;
