import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const ORO = "#d4af37";
const sec = { background: "#101014", border: "1px solid rgba(212,175,55,0.25)", borderRadius: 12, padding: "1rem 1.2rem", marginTop: 12 };
const inp = { background: "#0c0c0e", border: "1px solid rgba(212,175,55,0.35)", color: "#f4f2ec", padding: "0.55rem 0.7rem", borderRadius: 8, fontSize: "0.75rem" };
const goldBtn = { background: ORO, color: "#111", border: 0, borderRadius: 8, padding: "0.6rem 1.2rem", fontWeight: 800, cursor: "pointer", fontSize: "0.75rem" };

const COLOR_TIPO = { manual: "#38bdf8", auto: "#8a8fa3", regla: ORO, correccion: "#f59e0b" };

export default function RegistroEmmyModule() {
  const [regs, setRegs] = useState([]);
  const [nota, setNota] = useState({ titulo: "", descripcion: "", estado: "implementado" });
  const [msg, setMsg] = useState("");
  const [filtro, setFiltro] = useState("");

  const cargar = useCallback(() => {
    axios.get(`${API}/api/emmy/registros`).then(r => setRegs(r.data.registros || []))
      .catch(e => setMsg("❌ " + (e.response?.data?.detail || "Error")));
  }, []);
  useEffect(() => { cargar(); }, [cargar]);

  const agregar = async () => {
    try {
      await axios.post(`${API}/api/emmy/registros`, nota);
      setMsg("✅ Nota registrada");
      setNota({ titulo: "", descripcion: "", estado: "implementado" });
      cargar();
    } catch (e) { setMsg("❌ " + (e.response?.data?.detail || "Error")); }
  };

  const exportar = async () => {
    try {
      const r = await axios.get(`${API}/api/emmy/export-pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url; a.download = "registro_emmy.pdf"; a.click();
      URL.revokeObjectURL(url);
      setMsg("✅ Registro exportado a PDF");
    } catch { setMsg("❌ No se pudo exportar"); }
  };

  const visibles = regs.filter(r => !filtro
    || (r.titulo || "").toLowerCase().includes(filtro.toLowerCase())
    || (r.descripcion || "").toLowerCase().includes(filtro.toLowerCase()));

  return (
    <div data-testid="emmy-module" style={{ padding: "0.5rem", background: "#0a0a0c", minHeight: "100%" }}>
      <h2 style={{ color: ORO, fontFamily: "'Playfair Display', serif", margin: "0 0 2px" }}>📔 Registro Emmy</h2>
      <p style={{ color: "#8a8fa3", fontSize: "0.7rem", margin: 0 }}>Historial persistente de cambios, reglas y decisiones · exclusivo del Administrador</p>
      {msg && <p data-testid="emmy-msg" style={{ color: msg.startsWith("✅") ? "#22c55e" : "#ef4444", fontSize: "0.74rem", fontWeight: 700 }}>{msg}</p>}

      <div style={sec} data-testid="emmy-nota-form">
        <b style={{ color: ORO, fontSize: "0.75rem", letterSpacing: 1 }}>AGREGAR NOTA MANUAL</b>
        <div style={{ display: "grid", gridTemplateColumns: "1.2fr 2fr auto auto", gap: 8, marginTop: 8 }}>
          <input data-testid="emmy-nota-titulo" style={inp} placeholder="Título del cambio o decisión" value={nota.titulo} onChange={e => setNota({ ...nota, titulo: e.target.value })} />
          <input data-testid="emmy-nota-desc" style={inp} placeholder="Descripción" value={nota.descripcion} onChange={e => setNota({ ...nota, descripcion: e.target.value })} />
          <select data-testid="emmy-nota-estado" style={inp} value={nota.estado} onChange={e => setNota({ ...nota, estado: e.target.value })}>
            <option value="implementado">Implementado</option>
            <option value="pendiente">Pendiente</option>
            <option value="regla_activa">Regla activa</option>
          </select>
          <button data-testid="emmy-nota-agregar" style={goldBtn} disabled={!nota.titulo.trim()} onClick={agregar}>＋ Registrar</button>
        </div>
      </div>

      <div style={sec} data-testid="emmy-historial">
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <b style={{ color: ORO, fontSize: "0.75rem", letterSpacing: 1 }}>HISTORIAL ({visibles.length})</b>
          <input data-testid="emmy-filtro" style={{ ...inp, width: 240 }} placeholder="Buscar en el registro…" value={filtro} onChange={e => setFiltro(e.target.value)} />
          <button data-testid="emmy-export-pdf" style={{ ...goldBtn, marginLeft: "auto" }} onClick={exportar}>📄 Exportar a PDF</button>
        </div>
        <div style={{ maxHeight: 520, overflowY: "auto", marginTop: 10 }}>
          {visibles.map((r, i) => (
            <div key={r.id || i} data-testid={`emmy-registro-${i}`} style={{ borderTop: "1px solid rgba(255,255,255,0.06)", padding: "0.5rem 0" }}>
              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <span style={{ color: COLOR_TIPO[r.tipo] || "#8a8fa3", fontSize: "0.6rem", fontWeight: 800, letterSpacing: 1 }}>[{(r.tipo || "auto").toUpperCase()}]</span>
                <b style={{ color: "#fff", fontSize: "0.74rem" }}>{r.titulo}</b>
                <span style={{ color: "#64748b", fontSize: "0.62rem" }}>{String(r.fecha || "").slice(0, 16).replace("T", " ")}</span>
                <span style={{ color: r.estado === "pendiente" ? "#f59e0b" : "#22c55e", fontSize: "0.6rem", fontWeight: 800 }}>{(r.estado || "").toUpperCase()}</span>
              </div>
              {r.descripcion && <p style={{ color: "#b6bac9", fontSize: "0.68rem", margin: "3px 0 0", lineHeight: 1.5 }}>{r.descripcion}</p>}
              <span style={{ color: "#4b5563", fontSize: "0.58rem" }}>por {r.por}</span>
            </div>
          ))}
          {visibles.length === 0 && <p style={{ color: "#64748b", fontSize: "0.7rem" }}>Sin registros aún.</p>}
        </div>
      </div>
    </div>
  );
}
