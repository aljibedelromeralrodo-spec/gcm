import { useState, useEffect } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

const fFecha = (iso) => (iso || "").slice(0, 16).replace("T", " ");

// 🪞 Evolución del criterio de mesa: cada aprendizaje del Espejo, con fecha
export default function PanelEspejo() {
  const [evo, setEvo] = useState(null);
  const [modelo, setModelo] = useState(null);
  const [abierto, setAbierto] = useState(false);
  const [entrenando, setEntrenando] = useState(false);

  const cargar = async () => {
    try {
      const [e, m] = await Promise.all([
        axios.get(`${API_URL}/api/espejo-ia/evolucion`),
        axios.get(`${API_URL}/api/espejo-ia/modelo`)]);
      setEvo(e.data); setModelo(m.data);
    } catch { /* rol sin acceso */ }
  };
  useEffect(() => { cargar(); }, []);

  const entrenar = async () => {
    setEntrenando(true);
    try { await axios.post(`${API_URL}/api/espejo-ia/entrenar`); await cargar(); }
    catch { /* sin permiso */ }
    setEntrenando(false);
  };

  if (!evo || !modelo) return null;
  const versiones = evo.versiones || [];
  const visibles = abierto ? versiones : versiones.slice(0, 2);

  return (
    <div data-testid="panel-espejo" style={{ background: "#0b0b0d", border: "1px solid rgba(212,175,55,0.3)",
      borderRadius: 12, padding: "0.9rem 1.2rem", marginBottom: "1rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <span style={{ color: "#e7cf7a", fontSize: "0.7rem", fontWeight: 800, letterSpacing: 2, fontFamily: "monospace" }}>
          🪞 ALGORITMO ESPEJO — EVOLUCIÓN DEL CRITERIO DE MESA</span>
        <span style={{ color: "#6a6046", fontSize: "0.6rem", fontFamily: "monospace" }}>
          modelo v{modelo.version} · {modelo.n_casos} casos · <span style={{ color: "#10d98e" }}>{modelo.n_aprobados} aprobados</span> · <span style={{ color: "#e11d48" }}>{modelo.n_reprobados ?? (modelo.n_casos - modelo.n_aprobados)} rechazados</span> · tasa base {(modelo.tasa_base * 100 || 0).toFixed(1)}%
          {modelo.periodo && <> · ventana móvil 3 meses (desde {fFecha(modelo.periodo.desde).slice(0, 10)})</>}</span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button data-testid="panel-espejo-entrenar" onClick={entrenar} disabled={entrenando}
            style={{ background: "rgba(14,14,16,0.9)", border: "1px solid rgba(212,175,55,0.5)", color: "#e7cf7a",
              padding: "0.25rem 0.7rem", cursor: "pointer", fontSize: "0.6rem", fontWeight: 800, borderRadius: 6 }}>
            {entrenando ? "APRENDIENDO…" : "⟳ RE-ENTRENAR AHORA"}</button>
          <button data-testid="panel-espejo-expandir" onClick={() => setAbierto(!abierto)}
            style={{ background: "rgba(14,14,16,0.9)", border: "1px solid rgba(212,175,55,0.5)", color: "#e7cf7a",
              padding: "0.25rem 0.7rem", cursor: "pointer", fontSize: "0.6rem", fontWeight: 800, borderRadius: 6 }}>
            {abierto ? "▲ CONTRAER" : `▼ VER TODA LA EVOLUCIÓN (${versiones.length})`}</button>
        </div>
      </div>

      {(modelo.razones_top || []).length > 0 && (
        <div style={{ marginTop: 10 }}>
          <div style={{ color: "#8a7a5a", fontSize: "0.58rem", fontFamily: "monospace", letterSpacing: 1, marginBottom: 4 }}>
            CRITERIOS DE RECHAZO MÁS FRECUENTES DE MESA</div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {modelo.razones_top.slice(0, 5).map((r, i) => (
              <span key={i} style={{ fontSize: "0.62rem", color: "#f4b1b8", background: "rgba(225,29,72,0.1)",
                border: "1px solid rgba(225,29,72,0.35)", borderRadius: 6, padding: "0.15rem 0.5rem" }}>
                {r.razon} <b>×{r.casos}</b></span>
            ))}
          </div>
        </div>
      )}

      {/* Línea de tiempo de aprendizajes fechados */}
      <div data-testid="panel-espejo-timeline" style={{ marginTop: 12, borderLeft: "2px solid rgba(212,175,55,0.35)",
        paddingLeft: 14, display: "flex", flexDirection: "column", gap: 10 }}>
        {visibles.map((v) => (
          <div key={v.version} style={{ position: "relative" }}>
            <span style={{ position: "absolute", left: -20, top: 3, width: 9, height: 9, borderRadius: "50%",
              background: "#d4af37", boxShadow: "0 0 8px rgba(212,175,55,0.7)" }} />
            <div style={{ color: "#FCF6BA", fontSize: "0.65rem", fontFamily: "monospace", fontWeight: 800 }}>
              v{v.version} · {fFecha(v.fecha)} · {v.n_casos} casos
              {v.origenes && Object.keys(v.origenes).some(o => o.startsWith("capa2")) &&
                <span style={{ color: "#10d98e" }}> · CAPA 2 ACTIVA</span>}
            </div>
            <ul style={{ margin: "3px 0 0", paddingLeft: 16 }}>
              {(v.aprendizajes || []).slice(0, abierto ? 20 : 4).map((a, i) => (
                <li key={i} style={{ color: "#e8e2cf", fontSize: "0.66rem", margin: "2px 0" }}>{a}</li>
              ))}
              {(v.aprendizajes || []).length === 0 &&
                <li style={{ color: "#6a6046", fontSize: "0.62rem" }}>Sin cambios de criterio en esta versión.</li>}
            </ul>
          </div>
        ))}
        {versiones.length === 0 && (
          <span style={{ color: "#8a7a5a", fontSize: "0.65rem" }}>El espejo aún no registra aprendizajes.</span>
        )}
      </div>
    </div>
  );
}
