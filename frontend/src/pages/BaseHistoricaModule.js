import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const th = { padding: "0.6rem 0.7rem", textAlign: "left", fontSize: "0.62rem", color: "#94a3b8",
  textTransform: "uppercase", letterSpacing: "0.1em", borderBottom: "1px solid rgba(148,163,184,0.15)" };
const td = { padding: "0.5rem 0.7rem", fontSize: "0.72rem", color: "#e2e8f0" };

export default function BaseHistoricaModule() {
  const [estado, setEstado] = useState(null);
  const [clientes, setClientes] = useState([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);

  const cargar = useCallback((query = "") => {
    axios.get(`${API}/api/historia/estado`).then(r => setEstado(r.data)).catch(() => {});
    axios.get(`${API}/api/historia/clientes?q=${encodeURIComponent(query)}`)
      .then(r => setClientes(r.data.clientes || [])).catch(() => {});
  }, []);
  useEffect(() => { cargar(); const iv = setInterval(() => cargar(q), 15000); return () => clearInterval(iv); }, [cargar, q]);
  useEffect(() => { const t = setTimeout(() => cargar(q), 350); return () => clearTimeout(t); }, [q, cargar]);

  const toggleMotor = async () => {
    setBusy(true);
    const activo = estado?.checkpoint?.activo;
    try { await axios.post(`${API}/api/historia/${activo ? "pausar" : "iniciar"}`); cargar(q); }
    catch (e) { window.alert(e.response?.data?.detail || "Error"); }
    setBusy(false);
  };

  const exportar = async () => {
    const r = await axios.get(`${API}/api/historia/export-xlsx`, { responseType: "blob" });
    const url = URL.createObjectURL(r.data);
    const a = document.createElement("a");
    a.href = url; a.download = "Base_Datos_Historica_CentralMutuos.xlsx"; a.click();
    URL.revokeObjectURL(url);
  };

  const cp = estado?.checkpoint || {};
  const progreso = cp.total_correos ? Math.min(100, Math.round(((cp.indice || 0) / cp.total_correos) * 100)) : 0;

  return (
    <div className="module-content seamless-scope" data-testid="base-historica-module" style={{ padding: "1.2rem", borderRadius: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
        <h3 style={{ margin: 0, color: "#f8fafc", fontSize: "1.05rem" }}>
          <i className="fa fa-university" style={{ color: "#d4af37", marginRight: 8 }} />Base de Datos Histórica — Archivo Nacional
        </h3>
        <span style={{ color: "#94a3b8", fontSize: "0.7rem" }}>
          Minado del buzón gerardo.ext · Reglas #64/#65 · Sin Email el registro NO entra
        </span>
      </div>

      <div style={{ display: "flex", gap: 20, flexWrap: "wrap", alignItems: "stretch", marginTop: 18 }}>
        <div data-testid="contador-rescatados" style={{ flex: "1 1 260px", textAlign: "center", padding: "1.4rem",
          background: "rgba(30,41,59,0.45)", backdropFilter: "blur(14px)", borderRadius: 16 }}>
          <div style={{ fontSize: "0.64rem", color: "#94a3b8", letterSpacing: "0.2em", textTransform: "uppercase" }}>Clientes Rescatados</div>
          <div style={{ fontSize: "3.4rem", fontWeight: 900, lineHeight: 1.1,
            background: "linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C)", WebkitBackgroundClip: "text",
            backgroundClip: "text", color: "transparent" }}>{estado?.rescatados ?? "…"}</div>
          <div style={{ fontSize: "0.62rem", color: "#f59e0b" }}>{estado?.revision_manual ?? 0} en Revisión Manual (Regla #65)</div>
        </div>
        <div style={{ flex: "2 1 380px", padding: "1.2rem", background: "rgba(30,41,59,0.45)",
          backdropFilter: "blur(14px)", borderRadius: 16 }}>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
            <button data-testid="historia-toggle" onClick={toggleMotor} disabled={busy}
              className="maserati-btn" style={{ borderColor: cp.activo ? "#f59e0b" : "#22c55e" }}>
              {cp.activo ? "⏸ Pausar Motor de Rastreo" : "▶️ Iniciar Motor de Rastreo"}
            </button>
            <button data-testid="historia-export" onClick={exportar} className="maserati-btn neon">
              <i className="fa fa-file-excel-o" /> Exportar a Excel (.xlsx)
            </button>
          </div>
          <div style={{ marginTop: 14, fontSize: "0.68rem", color: "#94a3b8" }}>
            Punto de control: correo {cp.indice || 0} de {cp.total_correos || "?"} · Procesados: {cp.procesados || 0}
            {cp.completado && <b style={{ color: "#22c55e" }}> · ✅ MINADO COMPLETO</b>}
            {cp.activo && !cp.completado && <b style={{ color: "#f59e0b" }}> · ⛏️ Minando en bloques de 100…</b>}
          </div>
          <div style={{ marginTop: 8, height: 8, borderRadius: 6, background: "rgba(148,163,184,0.15)", overflow: "hidden" }}>
            <div data-testid="historia-progreso" style={{ width: `${progreso}%`, height: "100%",
              background: "linear-gradient(90deg,#BF953F,#FCF6BA,#AA771C)", transition: "width 0.6s" }} />
          </div>
          <div style={{ marginTop: 4, fontSize: "0.6rem", color: "#64748b" }}>{progreso}% del buzón escaneado · Exportación en streaming (jamás toca el disco)</div>
        </div>
      </div>

      <input data-testid="historia-buscar" placeholder="🔎 Búsqueda instantánea por nombre, RUT, email, inmobiliaria, proyecto, ciudad o teléfono…"
        value={q} onChange={e => setQ(e.target.value)}
        style={{ width: "100%", boxSizing: "border-box", marginTop: 18, background: "rgba(255,255,255,0.05)",
          border: "none", borderBottom: "1px solid rgba(212,175,55,0.35)", color: "#f8fafc",
          padding: "0.7rem 0.9rem", borderRadius: 10, fontSize: "0.8rem", outline: "none" }} />

      <div style={{ marginTop: 12, overflowX: "auto" }}>
        <table data-testid="historia-tabla" style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead><tr>
            {["Nombre", "RUT", "Email", "Teléfono", "Inmobiliaria", "Proyecto", "Ciudad", "Fuente", "Estado"].map(h => <th key={h} style={th}>{h}</th>)}
          </tr></thead>
          <tbody>
            {clientes.map(c => (
              <tr key={c.id || c.email} data-testid={`historia-fila-${c.id}`}
                style={{ background: c.revision_manual ? "rgba(239,68,68,0.10)" : undefined }}>
                <td style={{ ...td, fontWeight: 700, color: "#f8fafc" }}>{c.nombre || "—"}</td>
                <td style={{ ...td, fontFamily: "monospace" }}>{c.rut || "—"}</td>
                <td style={td}>{c.email}</td>
                <td style={td}>{c.telefono || "—"}</td>
                <td style={{ ...td, color: "#d4af37" }}>{c.inmobiliaria || "—"}</td>
                <td style={td}>{c.proyecto || "—"}</td>
                <td style={td}>{c.ciudad || "—"}</td>
                <td style={{ ...td, fontSize: "0.6rem", color: c.fuente === "bodega_dashai" ? "#22c55e" : "#94a3b8" }}>
                  {c.fuente === "bodega_dashai" ? "Verdad DashAI" : "Minado IMAP"}</td>
                <td style={{ ...td, fontSize: "0.6rem" }}>
                  {c.revision_manual
                    ? <span title={(c.motivos_revision || []).join(" · ")} style={{ color: "#ef4444", fontWeight: 800 }}>🔴 Revisión Manual</span>
                    : <span style={{ color: "#22c55e" }}>✅ Certeza 100%</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {clientes.length === 0 && <p style={{ color: "#94a3b8", textAlign: "center", padding: "2rem", fontSize: "0.74rem" }}>
          Sin registros aún. Inicie el Motor de Rastreo para minar el buzón histórico.</p>}
      </div>
    </div>
  );
}
