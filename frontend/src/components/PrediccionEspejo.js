import { useState, useEffect } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

const COLORES = { alta: "#10d98e", media: "#d4af37", baja: "#e11d48" };

// 🪞 Algoritmo Espejo Capa 1: probabilidad de aprobación aprendida de mesa
export default function PrediccionEspejo({ folderId }) {
  const [p, setP] = useState(null);
  const [abierto, setAbierto] = useState(false);

  useEffect(() => {
    let vivo = true;
    axios.get(`${API_URL}/api/espejo-ia/prediccion/${folderId}`)
      .then(r => { if (vivo) setP(r.data); }).catch(() => {});
    return () => { vivo = false; };
  }, [folderId]);

  if (!p) return null;
  const c = COLORES[p.nivel] || "#d4af37";

  return (
    <div data-testid="prediccion-espejo" style={{ background: "#0b0b0d", border: `1px solid ${c}55`,
      borderRadius: 10, padding: "0.7rem 1rem", marginBottom: "0.9rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", cursor: "pointer" }}
        onClick={() => setAbierto(!abierto)} data-testid="prediccion-espejo-toggle">
        <span style={{ fontSize: "0.62rem", fontFamily: "monospace", letterSpacing: 2, color: "#8a7a5a", fontWeight: 800 }}>
          🪞 ALGORITMO ESPEJO — PROBABILIDAD DE APROBACIÓN</span>
        <span data-testid="prediccion-espejo-nivel" style={{ color: c, fontWeight: 900, fontSize: "1rem", letterSpacing: 1 }}>
          {p.nivel.toUpperCase()} · {p.probabilidad}%</span>
        {p.resultado_real && (
          <span style={{ fontSize: "0.6rem", fontFamily: "monospace",
            color: p.resultado_real === "aprobado" ? "#10d98e" : "#e11d48" }}>
            (resultado real de mesa: {p.resultado_real.toUpperCase()})</span>
        )}
        <span style={{ marginLeft: "auto", fontSize: "0.58rem", color: "#6a6046", fontFamily: "monospace" }}>
          modelo v{p.modelo_version} · {p.casos_aprendidos} casos aprendidos de mesa · {abierto ? "▲" : "▼ ver factores"}</span>
      </div>
      {abierto && (
        <div data-testid="prediccion-espejo-factores" style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 4 }}>
          {(p.factores || []).length === 0 && (
            <span style={{ fontSize: "0.65rem", color: "#8a7a5a" }}>Aún sin factores con peso: el espejo aprende con cada resultado de mesa.</span>
          )}
          {(p.factores || []).map((f, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.68rem" }}>
              <span style={{ color: f.peso > 0 ? "#10d98e" : "#e11d48", width: 58, fontFamily: "monospace" }}>
                {f.peso > 0 ? "+" : ""}{f.peso.toFixed(2)}</span>
              <span style={{ color: "#e8e2cf" }}>{f.factor}</span>
              <span style={{ color: "#6a6046", fontSize: "0.58rem" }}>({f.direccion})</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
