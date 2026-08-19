import { useEffect, useState } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const inp = { background: "rgba(2,6,23,0.7)", border: "1px solid rgba(212,175,55,0.35)", color: "#f8fafc",
  borderRadius: 8, padding: "0.45rem 0.65rem", fontSize: "0.8rem", width: "100%", boxSizing: "border-box" };
const ESTADO_COLOR = { "Activo": "#4ade80", "Inactivo": "#facc15", "Sin credenciales": "#94a3b8" };

const FilaEjecutivo = ({ e, recargar }) => {
  const [form, setForm] = useState({ email: e.email || "", clave: "", servidor: e.servidor || "imap.gmail.com", activo: e.activo });
  const [guardando, setGuardando] = useState(false);
  const guardar = async () => {
    const confirmacion = window.prompt("Confirmación de identidad: reingrese su contraseña para guardar la configuración avanzada");
    if (!confirmacion) return;
    setGuardando(true);
    try {
      const r = await axios.post(`${API}/api/config/ejecutivos/${e.eid}`, { ...form, confirmacion_clave: confirmacion });
      window.alert(`✅ ${e.nombre}: configuración guardada (clave cifrada). Estado: ${r.data.estado}`);
      setForm(f => ({ ...f, clave: "" }));
      recargar();
    } catch (er) { window.alert(er.response?.data?.detail || "No fue posible guardar la configuración. Verifique su contraseña e intente nuevamente."); }
    setGuardando(false);
  };
  return (
    <div data-testid={`ejecutivo-${e.eid}`} style={{ background: "rgba(2,6,23,0.45)", border: "1px solid rgba(148,163,184,0.2)",
      borderRadius: 10, padding: "0.9rem 1rem", marginTop: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <b style={{ color: "#f8fafc", fontSize: "0.9rem" }}>👤 {e.nombre}</b>
        <span data-testid={`estado-${e.eid}`} style={{ fontSize: "0.68rem", fontWeight: 800,
          color: ESTADO_COLOR[e.estado] || "#94a3b8", border: `1px solid ${ESTADO_COLOR[e.estado] || "#94a3b8"}55`,
          borderRadius: 999, padding: "2px 10px" }}>{e.estado === "Activo" ? "🟢" : e.estado === "Inactivo" ? "🟡" : "⚪"} {e.estado}</span>
        {e.tiene_clave && <span style={{ color: "#4ade80", fontSize: "0.68rem" }}>🔐 clave guardada (cifrada, no visible)</span>}
        <label style={{ marginLeft: "auto", color: "#cbd5e1", fontSize: "0.75rem", display: "flex", gap: 6, alignItems: "center", cursor: "pointer" }}>
          <input data-testid={`activo-${e.eid}`} type="checkbox" checked={form.activo}
            onChange={ev => setForm(f => ({ ...f, activo: ev.target.checked }))} /> Conexión activa
        </label>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 8, marginTop: 10 }}>
        <div>
          <label style={{ color: "#94a3b8", fontSize: "0.65rem", fontWeight: 800 }}>CORREO ELECTRÓNICO</label>
          <input data-testid={`email-${e.eid}`} style={inp} value={form.email} placeholder="correo@dominio.cl"
            onChange={ev => setForm(f => ({ ...f, email: ev.target.value }))} />
        </div>
        <div>
          <label style={{ color: "#94a3b8", fontSize: "0.65rem", fontWeight: 800 }}>CLAVE DE APLICACIÓN IMAP</label>
          <input data-testid={`clave-${e.eid}`} style={inp} type="password" value={form.clave}
            placeholder={e.tiene_clave ? "•••••••• (vacío = mantener)" : "Pendiente — la ingresa el ejecutivo"}
            onChange={ev => setForm(f => ({ ...f, clave: ev.target.value }))} />
        </div>
        <div>
          <label style={{ color: "#94a3b8", fontSize: "0.65rem", fontWeight: 800 }}>SERVIDOR IMAP</label>
          <input data-testid={`servidor-${e.eid}`} style={inp} value={form.servidor}
            onChange={ev => setForm(f => ({ ...f, servidor: ev.target.value }))} />
        </div>
        <div style={{ display: "flex", alignItems: "flex-end" }}>
          <button data-testid={`guardar-${e.eid}`} onClick={guardar} disabled={guardando}
            style={{ background: "linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C)", color: "#0a0a0a", border: "none",
              borderRadius: 8, padding: "0.45rem 1rem", fontWeight: 800, cursor: "pointer", fontSize: "0.75rem", width: "100%" }}>
            {guardando ? "Guardando…" : "💾 Guardar"}</button>
        </div>
      </div>
    </div>
  );
};

export function ConexionConcreces() {
  const [data, setData] = useState(null);
  const [form, setForm] = useState({ usuario: "", clave: "", url: "" });
  const [busy, setBusy] = useState(false);
  const cargar = () => axios.get(`${API}/api/config/concreces`).then(r => {
    setData(r.data); setForm(f => ({ ...f, usuario: r.data.usuario || "", url: r.data.url || "" }));
  }).catch(() => setData({ error: true }));
  useEffect(() => { cargar(); }, []);
  const guardar = async () => {
    const confirmacion = window.prompt("Confirmación de identidad: reingrese su contraseña para guardar la configuración avanzada");
    if (!confirmacion) return;
    setBusy(true);
    try {
      await axios.post(`${API}/api/config/concreces`, { ...form, confirmacion_clave: confirmacion });
      window.alert("✅ Credenciales Concreces guardadas (cifradas) — sin conexión activa aún");
      setForm(f => ({ ...f, clave: "" })); cargar();
    } catch (e) { window.alert(e.response?.data?.detail || "No fue posible guardar. Verifique su contraseña e intente nuevamente."); }
    setBusy(false);
  };
  return (
    <div data-testid="conexion-concreces" style={{ background: "rgba(30,41,59,0.55)", border: "1px solid rgba(96,165,250,0.35)",
      borderRadius: 12, padding: "1.1rem 1.3rem", marginTop: 14 }}>
      <h3 style={{ color: "#93c5fd", fontSize: "0.95rem", margin: 0 }}>🔗 Conexión Concreces</h3>
      <p style={{ color: "#94a3b8", fontSize: "0.75rem", marginTop: 6 }}>
        Acceso dentro de la normativa de empresas vinculadas legalmente. <b>Sin conexión activa</b> hasta que el
        administrador ingrese y guarde las credenciales. Estado: <b data-testid="concreces-estado"
        style={{ color: data?.tiene_clave ? "#4ade80" : "#facc15" }}>{data?.estado || "Cargando…"}</b></p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 8, marginTop: 10 }}>
        <div>
          <label style={{ color: "#94a3b8", fontSize: "0.65rem", fontWeight: 800 }}>USUARIO</label>
          <input data-testid="concreces-usuario" style={inp} value={form.usuario} placeholder="usuario Concreces"
            onChange={e => setForm(f => ({ ...f, usuario: e.target.value }))} />
        </div>
        <div>
          <label style={{ color: "#94a3b8", fontSize: "0.65rem", fontWeight: 800 }}>CONTRASEÑA</label>
          <input data-testid="concreces-clave" style={inp} type="password" value={form.clave}
            placeholder={data?.tiene_clave ? "•••••••• (vacío = mantener)" : "Contraseña de acceso"}
            onChange={e => setForm(f => ({ ...f, clave: e.target.value }))} />
        </div>
        <div>
          <label style={{ color: "#94a3b8", fontSize: "0.65rem", fontWeight: 800 }}>URL DE ACCESO</label>
          <input data-testid="concreces-url" style={inp} value={form.url} placeholder="https://…"
            onChange={e => setForm(f => ({ ...f, url: e.target.value }))} />
        </div>
        <div style={{ display: "flex", alignItems: "flex-end" }}>
          <button data-testid="concreces-guardar" onClick={guardar} disabled={busy}
            style={{ background: "rgba(96,165,250,0.25)", color: "#93c5fd", border: "1px solid rgba(96,165,250,0.6)",
              borderRadius: 8, padding: "0.45rem 1rem", fontWeight: 800, cursor: "pointer", fontSize: "0.75rem", width: "100%" }}>
            {busy ? "Guardando…" : "💾 Guardar credenciales"}</button>
        </div>
      </div>
    </div>
  );
}

export default function ConfigEjecutivos() {
  const [data, setData] = useState(null);
  const cargar = () => axios.get(`${API}/api/config/ejecutivos`).then(r => setData(r.data)).catch(() => setData({ ejecutivos: [] }));
  useEffect(() => { cargar(); }, []);
  return (
    <div data-testid="config-ejecutivos" style={{ background: "rgba(30,41,59,0.55)", border: "1px solid rgba(212,175,55,0.3)",
      borderRadius: 12, padding: "1.1rem 1.3rem", marginTop: 14 }}>
      <h3 style={{ color: "#FCF6BA", fontSize: "0.95rem", margin: 0 }}>⚙️ Configuración de Ejecutivos — Correos IMAP</h3>
      <p style={{ color: "#94a3b8", fontSize: "0.75rem", marginTop: 6 }}>
        Cada ejecutivo ingresa su correo y clave de aplicación con su propia autorización. Las claves se guardan
        <b> cifradas</b> y no son visibles. El sistema <b>no se conecta a ningún correo</b> hasta que se guarden credenciales
        y se active la conexión.</p>
      {!data ? <p style={{ color: "#94a3b8", fontSize: "0.8rem" }}>Cargando…</p> :
        (data.ejecutivos || []).map(e => <FilaEjecutivo key={e.eid} e={e} recargar={cargar} />)}
    </div>
  );
}
