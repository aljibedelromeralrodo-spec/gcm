import { useEffect, useState } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const VACIA = { id: "", etiqueta: "", usuario: "", clave: "", url: "https://crece.cl", notas: "" };

export default function CreceModule({ user }) {
  const [data, setData] = useState({ credenciales: [], editable: false });
  const [form, setForm] = useState(null);
  const [verClave, setVerClave] = useState({});
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const cargar = () => axios.get(`${API}/api/crece/credenciales`).then(r => setData(r.data)).catch(() => {});
  useEffect(() => { cargar(); }, []);

  const guardar = async () => {
    setBusy(true); setMsg("");
    try {
      await axios.post(`${API}/api/crece/credenciales`, form);
      setForm(null); cargar();
      setMsg("✅ Credencial guardada");
    } catch (e) {
      setMsg("❌ " + (e.response?.data?.detail || e.message));
    } finally { setBusy(false); }
  };

  const eliminar = async (c) => {
    if (!window.confirm(`¿Eliminar la credencial "${c.etiqueta}"?`)) return;
    try { await axios.delete(`${API}/api/crece/credenciales/${c.id}`); cargar(); }
    catch (e) { setMsg("❌ " + (e.response?.data?.detail || e.message)); }
  };

  const inp = { width: "100%", background: "#0a0e17", border: "1px solid rgba(212,175,55,0.35)",
    color: "#f8fafc", padding: "0.55rem 0.8rem", fontSize: 13, marginTop: 4 };
  const th = { textAlign: "left", padding: "0.55rem 0.8rem", color: "#d4af37", fontSize: 11,
    letterSpacing: "0.12em", textTransform: "uppercase", borderBottom: "1px solid rgba(212,175,55,0.35)" };
  const td = { padding: "0.55rem 0.8rem", color: "#f8fafc", fontSize: 13,
    borderBottom: "1px solid rgba(148,163,184,0.12)" };

  return (
    <div data-testid="crece-module" style={{ padding: "1.4rem", color: "#f8fafc" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h2 style={{ color: "#d4af37", margin: 0, fontSize: "1.1rem", letterSpacing: "0.08em" }}>
          🔑 CREDENCIALES PLATAFORMA CRECE</h2>
        <span data-testid="crece-modo" style={{ fontSize: 10, fontWeight: 800, padding: "3px 10px",
          background: data.editable ? "rgba(212,175,55,0.15)" : "rgba(148,163,184,0.15)",
          color: data.editable ? "#d4af37" : "#94a3b8", border: "1px solid rgba(212,175,55,0.3)" }}>
          {data.editable ? "MODO ADMINISTRADOR — edición habilitada" : "SOLO LECTURA — edición exclusiva del Administrador"}
        </span>
        {data.editable && !form && (
          <button data-testid="crece-nueva-btn" onClick={() => setForm({ ...VACIA })}
            style={{ marginLeft: "auto", cursor: "pointer", background: "#d4af37", color: "#0a0e17",
              border: "none", fontWeight: 800, fontSize: 12, padding: "0.5rem 1rem" }}>
            + Nueva credencial</button>
        )}
      </div>
      <p style={{ color: "#94a3b8", fontSize: 12, marginTop: 6 }}>
        Accesos de los ejecutivos a la plataforma Crece (Regla de Oro #74). Los cambios quedan registrados.</p>
      {msg && <div data-testid="crece-msg" style={{ margin: "8px 0", fontSize: 12, fontWeight: 700,
        color: msg.startsWith("✅") ? "#10d98e" : "#f87171" }}>{msg}</div>}

      {form && (
        <div data-testid="crece-form" style={{ margin: "12px 0", padding: "1rem 1.2rem",
          background: "rgba(15,23,42,0.7)", border: "1px solid rgba(212,175,55,0.4)", maxWidth: 560 }}>
          <b style={{ color: "#d4af37", fontSize: 12 }}>{form.id ? "EDITAR" : "NUEVA"} CREDENCIAL</b>
          <input data-testid="crece-etiqueta" style={inp} placeholder="Etiqueta (ej: Ejecutiva Yerile — Crece)"
            value={form.etiqueta} onChange={e => setForm({ ...form, etiqueta: e.target.value })} />
          <input data-testid="crece-usuario" style={inp} placeholder="Usuario / correo"
            value={form.usuario} onChange={e => setForm({ ...form, usuario: e.target.value })} />
          <input data-testid="crece-clave" style={inp} placeholder="Clave"
            value={form.clave} onChange={e => setForm({ ...form, clave: e.target.value })} />
          <input style={inp} placeholder="URL" value={form.url}
            onChange={e => setForm({ ...form, url: e.target.value })} />
          <input style={inp} placeholder="Notas (opcional)" value={form.notas}
            onChange={e => setForm({ ...form, notas: e.target.value })} />
          <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
            <button data-testid="crece-guardar-btn" disabled={busy} onClick={guardar}
              style={{ cursor: "pointer", background: "#d4af37", color: "#0a0e17", border: "none",
                fontWeight: 800, fontSize: 12, padding: "0.5rem 1.2rem" }}>
              {busy ? "Guardando…" : "Guardar"}</button>
            <button onClick={() => setForm(null)} style={{ cursor: "pointer", background: "transparent",
              color: "#94a3b8", border: "1px solid rgba(148,163,184,0.4)", fontSize: 12, padding: "0.5rem 1rem" }}>
              Cancelar</button>
          </div>
        </div>
      )}

      <div style={{ marginTop: 14, background: "rgba(15,23,42,0.6)", border: "1px solid rgba(212,175,55,0.25)" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead><tr>
            <th style={th}>Etiqueta</th><th style={th}>Usuario</th><th style={th}>Clave</th>
            <th style={th}>URL</th><th style={th}>Notas</th><th style={th}>Actualizado</th>
            {data.editable && <th style={th}>Acciones</th>}
          </tr></thead>
          <tbody>
            {data.credenciales.length === 0 && (
              <tr><td style={{ ...td, color: "#64748b", fontStyle: "italic" }} colSpan={7}>
                Sin credenciales registradas{data.editable ? " — use “+ Nueva credencial”" : ""}.</td></tr>
            )}
            {data.credenciales.map(c => (
              <tr key={c.id} data-testid={`crece-fila-${c.id}`}>
                <td style={{ ...td, fontWeight: 700 }}>{c.etiqueta}</td>
                <td style={td}>{c.usuario}</td>
                <td style={td}>
                  <span style={{ fontFamily: "monospace" }}>{verClave[c.id] ? c.clave : "••••••••"}</span>
                  <button data-testid={`crece-ver-${c.id}`} title="Mostrar/ocultar"
                    onClick={() => setVerClave(s => ({ ...s, [c.id]: !s[c.id] }))}
                    style={{ marginLeft: 8, cursor: "pointer", background: "transparent", border: "none",
                      color: "#d4af37", fontSize: 12 }}>
                    <i className={`fa fa-eye${verClave[c.id] ? "-slash" : ""}`}></i></button>
                </td>
                <td style={td}><a href={c.url} target="_blank" rel="noreferrer"
                  style={{ color: "#d4af37" }}>{c.url}</a></td>
                <td style={{ ...td, color: "#94a3b8" }}>{c.notas || "—"}</td>
                <td style={{ ...td, color: "#94a3b8", fontSize: 11 }}>
                  {String(c.actualizado || "").slice(0, 16).replace("T", " ")}<br />{c.por}</td>
                {data.editable && (
                  <td style={td}>
                    <button data-testid={`crece-editar-${c.id}`} onClick={() => setForm({ ...VACIA, ...c })}
                      style={{ cursor: "pointer", background: "transparent", border: "1px solid rgba(212,175,55,0.5)",
                        color: "#d4af37", fontSize: 11, padding: "3px 10px", marginRight: 6 }}>Editar</button>
                    <button data-testid={`crece-eliminar-${c.id}`} onClick={() => eliminar(c)}
                      style={{ cursor: "pointer", background: "transparent", border: "1px solid rgba(239,68,68,0.5)",
                        color: "#f87171", fontSize: 11, padding: "3px 10px" }}>Eliminar</button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
