import { useState } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const ORO = "#d4af37";
const S = {
  page: { minHeight: "100vh", background: "#0a0a0a", color: "#fff", padding: "1rem",
    maxWidth: 720, margin: "0 auto", fontFamily: "'Segoe UI', system-ui, sans-serif" },
  input: { width: "100%", boxSizing: "border-box", background: "#161616", color: "#fff",
    border: `1px solid rgba(212,175,55,0.35)`, padding: "0.8rem", fontSize: "1rem", marginBottom: "0.8rem" },
  boton: { background: ORO, color: "#0a0a0a", border: "none", fontWeight: 800, padding: "0.8rem 1.2rem", cursor: "pointer" },
  fila: { display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", padding: "0.5rem 0.7rem",
    borderBottom: "1px solid rgba(255,255,255,0.08)", fontSize: "0.8rem" },
};

export default function CalculadoraAdmin() {
  const [master, setMaster] = useState("");
  const [data, setData] = useState(null);
  const [nueva, setNueva] = useState(null);
  const [msg, setMsg] = useState("");
  const link = `${window.location.origin}/calculadora`;

  const cargar = async (m) => {
    try {
      const r = await axios.post(`${API}/api/calcmax/admin/ejecutivos`, { master: m || master });
      setData(r.data); setMsg("");
    } catch (e) { setMsg(e.response?.data?.detail || "Error"); }
  };
  const generar = async () => {
    try {
      const r = await axios.post(`${API}/api/calcmax/admin/generar`, { master });
      setNueva(r.data.clave); cargar();
    } catch (e) { setMsg(e.response?.data?.detail || "Error"); }
  };
  const toggle = async (id) => {
    await axios.post(`${API}/api/calcmax/admin/toggle`, { master, id });
    cargar();
  };
  const compartir = (clave) => {
    const texto = `Calculadora de Crédito Máximo — Mutuarias y Leasing%0A%0ALink: ${link}%0AClave inicial: ${clave}%0A%0AAl primer ingreso registre su RUT y nombre completo.`;
    window.open(`https://wa.me/?text=${texto}`, "_blank");
  };

  if (!data) return (
    <div style={S.page}>
      <h2 style={{ color: ORO }}>🔑 Claves Calculadora — Admin</h2>
      <input data-testid="admin-master" style={S.input} type="password" placeholder="Clave maestra"
        value={master} onChange={e => setMaster(e.target.value)}
        onKeyDown={e => e.key === "Enter" && cargar()} />
      <button data-testid="admin-entrar" style={S.boton} onClick={() => cargar()}>ENTRAR</button>
      {msg && <div style={{ color: "#e35d6a", marginTop: 10 }}>{msg}</div>}
    </div>
  );

  return (
    <div style={S.page}>
      <h2 style={{ color: ORO }}>🔑 Claves Calculadora de Crédito Máximo</h2>
      <div style={{ fontSize: "0.8rem", opacity: 0.7, marginBottom: 12 }}>
        Link permanente para ejecutivos: <b style={{ color: ORO }}>{link}</b>
      </div>
      <button data-testid="admin-generar" style={S.boton} onClick={generar}>+ GENERAR NUEVA CLAVE</button>
      {nueva && (
        <div data-testid="admin-clave-nueva" style={{ margin: "12px 0", padding: "0.9rem", border: `1.5px solid ${ORO}`, background: "rgba(212,175,55,0.08)" }}>
          Nueva clave: <b style={{ color: ORO, fontSize: "1.4rem", letterSpacing: "0.2em" }}>{nueva}</b>
          <button style={{ ...S.boton, marginLeft: 12, background: "#25D366" }} onClick={() => compartir(nueva)}>
            Enviar por WhatsApp
          </button>
        </div>
      )}
      {msg && <div style={{ color: "#e35d6a", margin: "8px 0" }}>{msg}</div>}
      <h3 style={{ color: ORO, fontSize: "0.9rem", marginTop: 18 }}>EJECUTIVOS ({data.ejecutivos.length})</h3>
      {data.ejecutivos.map(e => (
        <div key={e.id} style={S.fila}>
          <b style={{ color: ORO, letterSpacing: "0.15em", minWidth: 90 }}>{e.clave}</b>
          <span style={{ flex: 1 }}>{e.registrado ? `${e.nombre} · RUT ${e.rut}` : "— sin registrar —"}</span>
          <span style={{ opacity: 0.5 }}>{(e.ultimo_acceso || "").slice(0, 16).replace("T", " ") || "nunca"}</span>
          <button style={{ ...S.boton, padding: "0.3rem 0.7rem", fontSize: "0.7rem",
            background: e.activo ? "#e35d6a" : "#10d98e" }} onClick={() => toggle(e.id)}>
            {e.activo ? "Desactivar" : "Activar"}
          </button>
          <button style={{ ...S.boton, padding: "0.3rem 0.7rem", fontSize: "0.7rem", background: "#25D366" }}
            onClick={() => compartir(e.clave)}>WhatsApp</button>
        </div>
      ))}
      <h3 style={{ color: ORO, fontSize: "0.9rem", marginTop: 18 }}>ÚLTIMOS ACCESOS</h3>
      {(data.ultimos_accesos || []).map((a, i) => (
        <div key={i} style={S.fila}>
          <span style={{ flex: 1 }}>{a.nombre} · {a.rut}</span>
          <span style={{ opacity: 0.5 }}>{(a.fecha || "").slice(0, 16).replace("T", " ")}</span>
        </div>
      ))}
    </div>
  );
}
