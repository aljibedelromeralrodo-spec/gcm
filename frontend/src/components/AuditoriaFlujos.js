import { useState, useEffect } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

const COLOR = { correcto: "#10d98e", incorrecto: "#e11d48", alerta: "#d4af37" };

// 🕵️ Auditoría automatizada: recorre los flujos como un usuario real
export default function AuditoriaFlujos() {
  const [run, setRun] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [abierto, setAbierto] = useState(false);

  useEffect(() => {
    axios.get(`${API_URL}/api/auditoria-flujos/ultima`).then(r => setRun(r.data)).catch(() => {});
  }, []);

  const ejecutar = async () => {
    setCargando(true);
    try { const r = await axios.post(`${API_URL}/api/auditoria-flujos/ejecutar`); setRun(r.data); setAbierto(true); }
    catch { /* sin permiso */ }
    setCargando(false);
  };

  const exportarPdf = async () => {
    try {
      const r = await axios.get(`${API_URL}/api/auditoria-flujos/pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url; a.download = "auditoria_flujos.pdf"; a.click();
      URL.revokeObjectURL(url);
    } catch { /* sin auditorías */ }
  };

  if (run === null) return null;
  const res = run.resumen || {};

  return (
    <div data-testid="auditoria-flujos" style={{ background: "#0b0b0d", border: "1px solid rgba(212,175,55,0.3)",
      borderRadius: 12, padding: "0.9rem 1.2rem", marginBottom: "1rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <span style={{ color: "#e7cf7a", fontSize: "0.7rem", fontWeight: 800, letterSpacing: 2, fontFamily: "monospace" }}>
          🕵️ AUDITORÍA AUTOMATIZADA DE FLUJOS</span>
        {run.fecha && <span style={{ color: "#6a6046", fontSize: "0.6rem", fontFamily: "monospace" }}>
          última: {(run.fecha || "").slice(0, 16).replace("T", " ")} ·
          <span style={{ color: COLOR.correcto }}> {res.correcto || 0} correctos</span> ·
          <span style={{ color: COLOR.incorrecto }}> {res.incorrecto || 0} incorrectos</span> ·
          <span style={{ color: COLOR.alerta }}> {res.alerta || 0} alertas</span></span>}
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button data-testid="auditoria-ejecutar" onClick={ejecutar} disabled={cargando}
            style={{ background: "rgba(14,14,16,0.9)", border: "1px solid rgba(212,175,55,0.5)", color: "#e7cf7a",
              padding: "0.25rem 0.7rem", cursor: "pointer", fontSize: "0.6rem", fontWeight: 800, borderRadius: 6 }}>
            {cargando ? "RECORRIENDO FLUJOS…" : "▶ EJECUTAR AUDITORÍA"}</button>
          <button data-testid="auditoria-pdf" onClick={exportarPdf}
            style={{ background: "rgba(14,14,16,0.9)", border: "1px solid rgba(212,175,55,0.5)", color: "#e7cf7a",
              padding: "0.25rem 0.7rem", cursor: "pointer", fontSize: "0.6rem", fontWeight: 800, borderRadius: 6 }}>
            ⬇ EXPORTAR PDF</button>
          <button data-testid="auditoria-expandir" onClick={() => setAbierto(!abierto)}
            style={{ background: "rgba(14,14,16,0.9)", border: "1px solid rgba(212,175,55,0.5)", color: "#e7cf7a",
              padding: "0.25rem 0.7rem", cursor: "pointer", fontSize: "0.6rem", fontWeight: 800, borderRadius: 6 }}>
            {abierto ? "▲" : `▼ VER DETALLE (${(run.items || []).length})`}</button>
        </div>
      </div>
      {abierto && (
        <div data-testid="auditoria-detalle" style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 4,
          maxHeight: 420, overflowY: "auto" }}>
          {(run.items || []).map((it, i) => (
            <div key={i} style={{ display: "flex", gap: 8, alignItems: "baseline", fontSize: "0.66rem",
              borderLeft: `3px solid ${COLOR[it.resultado]}`, paddingLeft: 8 }}>
              <span style={{ color: COLOR[it.resultado], fontWeight: 800, fontFamily: "monospace", minWidth: 78 }}>
                {it.resultado.toUpperCase()}</span>
              <span style={{ color: "#8a7a5a", minWidth: 150 }}>{it.flujo}</span>
              <span style={{ color: "#e8e2cf" }}>{it.paso}{it.descripcion ? ` — ${it.descripcion}` : ""}</span>
            </div>
          ))}
          {(run.items || []).length === 0 && <span style={{ color: "#8a7a5a", fontSize: "0.65rem" }}>
            Aún no se ha ejecutado ninguna auditoría.</span>}
        </div>
      )}
    </div>
  );
}
