import { useState, useEffect } from "react";
import axios from "axios";
import { secureGet } from "../utils/secureStore";

const API = process.env.REACT_APP_BACKEND_URL;
const ROLES = [
  ["admin", "Administrador"], ["gerencia", "Gerencia Comercial"], ["administracion", "Administración"],
  ["postventa", "Postventa"], ["broker", "Broker"], ["contralor", "Contralor"],
];
const ROLES_TIPO_C = ["broker", "administracion"];

export default function UsuariosModule() {
  const yo = secureGet("user") || {};
  const esVictoria = yo.rol === "administracion";
  const rolesDisponibles = ROLES.filter(([r]) => (esVictoria ? ROLES_TIPO_C.includes(r) : true));
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ codigo: "", nombre: "", email: "", rol: esVictoria ? "broker" : "broker", clave: "" });
  const [error, setError] = useState("");
  const [resultado, setResultado] = useState(null);

  useEffect(() => { loadUsers(); }, []); // eslint-disable-line

  const loadUsers = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/admin/users`);
      setUsers(r.data.users || []);
    } catch { setUsers([]); }
    setLoading(false);
  };

  const createUser = async () => {
    if (!form.nombre.trim() || !form.email.trim() || !form.rol) {
      setError("Nombre, correo y rol son obligatorios"); return;
    }
    setError(""); setLoading(true);
    try {
      const r = await axios.post(`${API}/api/admin/users`, form);
      setResultado(r.data);
      setForm({ codigo: "", nombre: "", email: "", rol: "broker", clave: "" });
      setShowCreate(false);
      await loadUsers();
    } catch (err) { setError(err.response?.data?.detail || "Error al crear usuario"); }
    setLoading(false);
  };

  const toggleActivo = async (u) => {
    try {
      await axios.post(`${API}/api/admin/users/${u.codigo}/activo`, { activo: u.activo === false });
      await loadUsers();
    } catch (err) { alert(err.response?.data?.detail || "Error"); }
  };

  const resetClave = async (u) => {
    const clave = window.prompt(
      `Reseteo de contraseña de "${u.nombre}".\nEscriba la clave inicial que desea asignar (mínimo 6 caracteres) o deje vacío para generar una automática.\nSe enviará por correo y el usuario deberá cambiarla en su primer ingreso.`);
    if (clave === null) return;
    try {
      const r = await axios.post(`${API}/api/admin/users/${u.codigo}/reset-clave`, { clave: clave.trim() });
      setResultado(r.data);
      await loadUsers();
    } catch (err) { alert(err.response?.data?.detail || "Error al resetear"); }
  };

  const deleteUser = async (codigo) => {
    if (!window.confirm(`¿Eliminar usuario "${codigo}"? Esta acción es permanente.`)) return;
    try {
      await axios.delete(`${API}/api/admin/users/${codigo}`);
      await loadUsers();
    } catch (err) { alert(err.response?.data?.detail || "Error al eliminar"); }
  };

  const rolLabel = (r, perfil) => {
    const f = ROLES.find(([k]) => k === r);
    if (f) return f[1];
    if (r === "ejecutivo") return perfil === "D" ? "Broker" : "Administración";
    return r ? r.charAt(0).toUpperCase() + r.slice(1) : "No disponible";
  };
  const fdd = (iso) => (iso ? `${String(iso).slice(8, 10)}/${String(iso).slice(5, 7)}/${String(iso).slice(0, 4)}` : "—");
  const fddHora = (iso) => (iso ? `${fdd(iso)} ${String(iso).slice(11, 16)}` : "—");

  return (
    <div className="module-content" data-testid="usuarios-module">
      <div className="clientes-toolbar">
        <h3 style={{ margin: 0, color: "var(--text-primary)", fontSize: "1.1rem" }}>
          <i className="fa fa-users" style={{ marginRight: 8, color: "var(--gold)" }}></i>
          Gestión de Usuarios
        </h3>
        <span style={{ color: "var(--text-secondary)", fontSize: "0.7rem" }}>
          {esVictoria ? "Puede crear usuarios tipo C: brokers y personal administrativo"
            : "Administrador: puede crear usuarios de cualquier rol"}
        </span>
        <button className="docs-btn primary" onClick={() => setShowCreate(!showCreate)} data-testid="btn-new-user">
          <i className={`fa fa-${showCreate ? "times" : "plus"}`}></i> {showCreate ? "Cancelar" : "Nuevo Usuario"}
        </button>
      </div>

      {resultado && (
        <div data-testid="resultado-creacion" style={{ marginTop: 12, background: "rgba(74,222,128,0.08)",
          border: "1px solid rgba(74,222,128,0.5)", borderRadius: 10, padding: "0.9rem 1.1rem" }}>
          <b style={{ color: "#4ade80", fontSize: "0.82rem" }}>
            {resultado.email_enviado ? "✅ Credenciales enviadas por correo al nuevo usuario"
              : "⚠️ No se pudo enviar el correo — entregue la clave provisoria manualmente"}</b>
          <div style={{ color: "#e2e8f0", fontSize: "0.8rem", marginTop: 6 }}>
            Usuario: <b>{resultado.codigo}</b> · Clave provisoria:{" "}
            <b data-testid="clave-provisoria" style={{ fontFamily: "monospace", color: "#FCF6BA" }}>{resultado.clave_provisoria}</b>
          </div>
          <p style={{ color: "#94a3b8", fontSize: "0.7rem", margin: "6px 0 0" }}>
            En su primer inicio de sesión deberá cambiar la contraseña y configurar su cuenta de correo (obligatorio).</p>
          <button className="docs-btn secondary" style={{ marginTop: 8, fontSize: "0.68rem" }}
            onClick={() => setResultado(null)} data-testid="cerrar-resultado">Cerrar</button>
        </div>
      )}

      {showCreate && (
        <div data-testid="create-user-overlay"
          onClick={(e) => { if (e.target === e.currentTarget) { setShowCreate(false); setError(""); } }}
          style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(2,6,23,0.75)",
            backdropFilter: "blur(4px)", display: "flex", alignItems: "center",
            justifyContent: "center", padding: "1rem" }}>
          <div className="clientes-create-form" data-testid="create-user-form"
            style={{ width: "min(680px, 96vw)", maxHeight: "88vh", overflowY: "auto", margin: 0,
              boxShadow: "0 24px 60px rgba(0,0,0,0.55)" }}>
            <h4>Crear Nuevo Usuario</h4>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.72rem", margin: "0 0 8px" }}>
            El sistema envía la clave inicial y el enlace de acceso al correo del usuario. Puede definir la clave o dejar que se genere automáticamente. El usuario deberá cambiarla en su primer ingreso.</p>
          <div className="clientes-form-grid">
            <div className="clientes-field">
              <label>Nombre Completo *</label>
              <input type="text" value={form.nombre} onChange={e => setForm({ ...form, nombre: e.target.value })}
                placeholder="Ej: Juan Pérez" data-testid="input-user-nombre" />
            </div>
            <div className="clientes-field">
              <label>Correo Electrónico *</label>
              <input type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })}
                placeholder="usuario@centralmutuos.cl" data-testid="input-user-email" />
            </div>
            <div className="clientes-field">
              <label>Código de Acceso (opcional — si se omite, será el correo)</label>
              <input type="text" value={form.codigo} onChange={e => setForm({ ...form, codigo: e.target.value })}
                placeholder="Ej: jperez" data-testid="input-user-codigo" />
            </div>
            <div className="clientes-field">
              <label>Rol *</label>
              <select value={form.rol} onChange={e => setForm({ ...form, rol: e.target.value })} data-testid="select-user-rol">
                {rolesDisponibles.map(([k, lb]) => <option key={k} value={k}>{lb}</option>)}
              </select>
            </div>
            <div className="clientes-field">
              <label>Clave inicial (opcional — si se omite, se genera automática)</label>
              <input type="text" value={form.clave} onChange={e => setForm({ ...form, clave: e.target.value })}
                placeholder="Mínimo 6 caracteres" data-testid="input-user-clave" />
            </div>
          </div>
          {error && <p style={{ color: "#e11d48", fontSize: "0.85rem", margin: "0.5rem 0" }} data-testid="user-error">{error}</p>}
          <div className="clientes-form-actions">
            <button className="docs-btn secondary" onClick={() => { setShowCreate(false); setError(""); }}>Cancelar</button>
            <button className="docs-btn primary" onClick={createUser} disabled={loading} data-testid="btn-confirm-create-user">
              {loading ? "Creando..." : "Crear Usuario y Enviar Credenciales"}
            </button>
          </div>
          </div>
        </div>
      )}

      <div style={{ marginTop: "1.5rem", overflowX: "auto" }}>
        {loading && users.length === 0 ? (
          <p style={{ color: "var(--text-secondary)", textAlign: "center", padding: "2rem" }}>Cargando usuarios...</p>
        ) : (
          <table className="history-table" data-testid="users-table">
            <style>{`
              [data-testid="users-table"] th { padding: 12px 14px; font-size: 0.74rem; letter-spacing: 0.5px; }
              [data-testid="users-table"] td { padding: 16px 14px; font-size: 0.9rem; vertical-align: middle; }
            `}</style>
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Rol</th>
                <th>Correo</th>
                <th>Estado</th>
                <th>Creación</th>
                <th>Último acceso</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.codigo} data-testid={`user-row-${u.codigo}`}>
                  <td><b style={{ fontSize: "0.92rem" }}>{u.nombre}</b><div style={{ fontFamily: "monospace", fontSize: "0.7rem", color: "var(--text-secondary)", marginTop: 3 }}>{u.codigo}</div></td>
                  <td>
                    <span className="status-pill" style={{ fontSize: "0.74rem", padding: "4px 10px", background: "rgba(212,175,55,0.12)", color: "var(--gold)", border: "1px solid rgba(212,175,55,0.4)" }}>
                      {rolLabel(u.rol, u.perfil)}</span>
                    {u.first_login && <div style={{ color: "#fbbf24", fontSize: "0.62rem", fontWeight: 800, marginTop: 4 }}>⏳ CONFIG. INICIAL PENDIENTE</div>}
                  </td>
                  <td style={{ fontSize: "0.84rem" }}>{u.email || <span style={{ color: "var(--text-muted)", fontStyle: "italic" }}>No disponible</span>}</td>
                  <td>
                    <span style={{ color: u.activo ? "#22c55e" : "#ef4444", fontWeight: 800, fontSize: "0.78rem" }}
                      data-testid={`estado-user-${u.codigo}`}>{u.activo ? "● Activo" : "● Inactivo"}</span>
                  </td>
                  <td style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>{fdd(u.created)}</td>
                  <td style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>{fddHora(u.ultimo_acceso)}</td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    {u.codigo !== "administrador" && !esVictoria && (
                      <>
                        <button className="docs-btn secondary" onClick={() => toggleActivo(u)}
                          data-testid={`btn-toggle-user-${u.codigo}`} style={{ fontSize: "0.62rem", marginRight: 4 }}
                          title={u.activo ? "Desactivar acceso" : "Reactivar acceso"}>
                          <i className={`fa fa-${u.activo ? "lock" : "unlock"}`}></i> {u.activo ? "Desactivar" : "Reactivar"}
                        </button>
                        <button className="docs-btn secondary" onClick={() => resetClave(u)}
                          data-testid={`btn-reset-user-${u.codigo}`} style={{ fontSize: "0.62rem", marginRight: 4 }}
                          title="Forzar reseteo de contraseña (nueva clave provisoria por correo)">
                          <i className="fa fa-key"></i> Resetear clave
                        </button>
                        <button className="clientes-delete-btn" onClick={() => deleteUser(u.codigo)}
                          data-testid={`btn-delete-user-${u.codigo}`} title="Eliminar usuario">
                          <i className="fa fa-trash"></i>
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {users.length === 0 && !loading && (
          <p style={{ color: "var(--text-muted)", textAlign: "center", padding: "2rem" }}>No hay usuarios registrados.</p>
        )}
      </div>
    </div>
  );
}
