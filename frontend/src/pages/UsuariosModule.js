import { useState, useEffect } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

export default function UsuariosModule() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ codigo: "", nombre: "", password: "", rol: "ejecutivo" });
  const [error, setError] = useState("");

  useEffect(() => { loadUsers(); }, []);

  const loadUsers = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/admin/users`);
      setUsers(r.data.users || []);
    } catch { setUsers([]); }
    setLoading(false);
  };

  const createUser = async () => {
    if (!form.codigo.trim() || !form.nombre.trim() || !form.password.trim()) {
      setError("Todos los campos son obligatorios");
      return;
    }
    setError("");
    setLoading(true);
    try {
      await axios.post(`${API}/api/admin/users`, form);
      setForm({ codigo: "", nombre: "", password: "", rol: "ejecutivo" });
      setShowCreate(false);
      await loadUsers();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al crear usuario");
    }
    setLoading(false);
  };

  const deleteUser = async (codigo) => {
    if (!window.confirm(`¿Eliminar usuario "${codigo}"?`)) return;
    try {
      await axios.delete(`${API}/api/admin/users/${codigo}`);
      await loadUsers();
    } catch (err) {
      alert(err.response?.data?.detail || "Error al eliminar");
    }
  };

  return (
    <div className="module-content" data-testid="usuarios-module">
      <div className="clientes-toolbar">
        <h3 style={{ margin: 0, color: "var(--text-primary)", fontSize: "1.1rem" }}>
          <i className="fa fa-users" style={{ marginRight: 8, color: "var(--gold)" }}></i>
          Gestion de Usuarios
        </h3>
        <button className="docs-btn primary" onClick={() => setShowCreate(!showCreate)} data-testid="btn-new-user">
          <i className={`fa fa-${showCreate ? 'times' : 'plus'}`}></i> {showCreate ? "Cancelar" : "Nuevo Usuario"}
        </button>
      </div>

      {showCreate && (
        <div className="clientes-create-form" data-testid="create-user-form" style={{ marginTop: "1rem" }}>
          <h4>Crear Nuevo Usuario</h4>
          <div className="clientes-form-grid">
            <div className="clientes-field">
              <label>Codigo de Acceso *</label>
              <input type="text" value={form.codigo} onChange={e => setForm({ ...form, codigo: e.target.value })}
                placeholder="Ej: 12345678" data-testid="input-user-codigo" />
            </div>
            <div className="clientes-field">
              <label>Nombre Completo *</label>
              <input type="text" value={form.nombre} onChange={e => setForm({ ...form, nombre: e.target.value })}
                placeholder="Ej: Juan Perez" data-testid="input-user-nombre" />
            </div>
            <div className="clientes-field">
              <label>Contrasena *</label>
              <input type="text" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })}
                placeholder="Clave de acceso" data-testid="input-user-password" />
            </div>
            <div className="clientes-field">
              <label>Rol</label>
              <select value={form.rol} onChange={e => setForm({ ...form, rol: e.target.value })} data-testid="select-user-rol">
                <option value="ejecutivo">Ejecutivo</option>
                <option value="admin">Administrador</option>
              </select>
            </div>
          </div>
          {error && <p style={{ color: "#ef4444", fontSize: "0.85rem", margin: "0.5rem 0" }} data-testid="user-error">{error}</p>}
          <div className="clientes-form-actions">
            <button className="docs-btn secondary" onClick={() => { setShowCreate(false); setError(""); }}>Cancelar</button>
            <button className="docs-btn primary" onClick={createUser} disabled={loading} data-testid="btn-confirm-create-user">
              {loading ? "Creando..." : "Crear Usuario"}
            </button>
          </div>
        </div>
      )}

      <div style={{ marginTop: "1.5rem" }}>
        {loading && users.length === 0 ? (
          <p style={{ color: "var(--text-secondary)", textAlign: "center", padding: "2rem" }}>Cargando usuarios...</p>
        ) : (
          <table className="history-table" data-testid="users-table">
            <thead>
              <tr>
                <th>Codigo de Acceso</th>
                <th>Nombre</th>
                <th>Rol</th>
                <th>Fecha Creacion</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.codigo} data-testid={`user-row-${u.codigo}`}>
                  <td style={{ fontFamily: "monospace", fontWeight: 600 }}>{u.codigo}</td>
                  <td>{u.nombre}</td>
                  <td>
                    <span className={`status-pill ${u.rol === 'admin' ? 'pill-approved' : 'pill-rejected'}`}
                      style={{ fontSize: "0.75rem" }}>
                      {u.rol === 'admin' ? 'Admin' : 'Ejecutivo'}
                    </span>
                  </td>
                  <td style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                    {u.created ? new Date(u.created).toLocaleDateString("es-CL") : "-"}
                  </td>
                  <td>
                    {u.codigo !== "administrador" && (
                      <button className="clientes-delete-btn" onClick={() => deleteUser(u.codigo)}
                        data-testid={`btn-delete-user-${u.codigo}`} title="Eliminar usuario">
                        <i className="fa fa-trash"></i>
                      </button>
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
