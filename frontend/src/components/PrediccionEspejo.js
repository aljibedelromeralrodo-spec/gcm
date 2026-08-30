import { useState, useEffect } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

const COLORES = { alta: "#10d98e", media: "#d4af37", baja: "#e11d48", alerta: "#ea580c" };

/** Un panel: Mutuaria (interno) vs Concreces (tope mesa) + patrones históricos. */
export default function PrediccionEspejo({ folderId, viabilidad }) {
  const [p, setP] = useState(null);
  const [abierto, setAbierto] = useState(false);

  useEffect(() => {
    let vivo = true;
    axios.get(`${API_URL}/api/espejo-ia/prediccion/${folderId}`)
      .then(r => { if (vivo) setP(r.data); }).catch(() => {});
    return () => { vivo = false; };
  }, [folderId]);

  const mut = viabilidad?.mutuaria?.porcentaje ?? viabilidad?.porcentaje;
  const con = viabilidad?.concreces;
  const disc = viabilidad?.discrepancia;
  if (!p && mut == null) return null;

  const borde = disc?.hay ? COLORES.alerta : (COLORES[p?.nivel] || "#d4af37");

  return (
    <div data-testid="prediccion-espejo" style={{ background: "#0b0b0d", border: `1px solid ${borde}55`,
      borderRadius: 10, padding: "0.7rem 1rem", marginBottom: "0.9rem" }}>
      <div style={{ fontSize: "0.62rem", fontFamily: "monospace", letterSpacing: 2, color: "#8a7a5a", fontWeight: 800, marginBottom: 8 }}>
        🪞 VIABILIDAD — MUTUARIA vs CONCRECES</div>
      <div style={{ display: "flex", gap: 18, flexWrap: "wrap", alignItems: "flex-end" }}>
        {mut != null && (
          <div data-testid="viab-mutuaria">
            <div style={{ fontSize: 9, fontWeight: 800, color: "#94a3b8", letterSpacing: 0.8 }}>MUTUARIA (interno)</div>
            <div style={{ fontSize: "1.45rem", fontWeight: 900, color: "#e8e2cf" }}>{mut}%</div>
          </div>
        )}
        <div data-testid="viab-concreces">
          <div style={{ fontSize: 9, fontWeight: 800, color: "#94a3b8", letterSpacing: 0.8 }}>CONCRECES (tope mesa)</div>
          {con?.disponible && con.porcentaje != null
            ? <div style={{ fontSize: "1.45rem", fontWeight: 900, color: disc?.hay ? COLORES.alerta : "#d4af37" }}>{con.porcentaje}%</div>
            : <div style={{ fontSize: 12, fontWeight: 700, color: "#6a6046", marginTop: 6 }}>en calibración</div>}
        </div>
        {p && (
          <div data-testid="viab-patrones" title="Patrones de mesa (histórico 3 meses), no es el tope UF">
            <div style={{ fontSize: 9, fontWeight: 800, color: "#6a6046", letterSpacing: 0.8 }}>PATRONES (histórico)</div>
            <div style={{ fontSize: "1.1rem", fontWeight: 800, color: COLORES[p.nivel] || "#d4af37" }}>{p.probabilidad}%</div>
          </div>
        )}
      </div>
      {disc?.mensaje && (
        <div data-testid="discrepancia-viabilidad" style={{ marginTop: 8, fontSize: 12, fontWeight: 700,
          color: disc.hay ? COLORES.alerta : "#10d98e" }}>
          {disc.mensaje}
        </div>
      )}
      {p && (
        <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", cursor: "pointer" }}
          onClick={() => setAbierto(!abierto)} data-testid="prediccion-espejo-toggle">
          <span data-testid="prediccion-espejo-nivel" style={{ color: "#6a6046", fontSize: "0.62rem", fontFamily: "monospace" }}>
            Patrones de mesa · {(p.nivel || "").toUpperCase()} · modelo v{p.modelo_version} · {p.casos_aprendidos} casos
            {p.resultado_real ? ` · resultado real: ${String(p.resultado_real).toUpperCase()}` : ""} · {abierto ? "▲" : "▼ factores"}
          </span>
        </div>
      )}
      {abierto && p && (
        <div data-testid="prediccion-espejo-factores" style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 4 }}>
          {(p.factores || []).length === 0 && (
            <span style={{ fontSize: "0.65rem", color: "#8a7a5a" }}>Aún sin factores con peso: el espejo de patrones aprende con cada resultado de mesa.</span>
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
