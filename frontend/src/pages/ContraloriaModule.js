import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

const RUBI = "#e11d48";
const ORO = "var(--gold, #D4AF37)";

export default function ContraloriaModule() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const cargar = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API_URL}/api/contraloria/casos`);
      setData(r.data);
    } catch { setData({ error: true }); }
    setLoading(false);
  }, []);

  useEffect(() => { cargar(); }, [cargar]);

  const calibrar = async () => {
    setLoading(true);
    try { await axios.post(`${API_URL}/api/mesa-brain/calibrar`); await cargar(); }
    catch { setLoading(false); }
  };

  const m = data?.modelo || {};
  const casos = data?.casos || [];
  const inconsistencias = casos.filter(c => c.estado_auditoria === "BAJO AUDITORÍA").length;

  return (
    <div className="module-content" data-testid="contraloria-module">
      <div style={{ display: "flex", alignItems: "baseline", gap: 14, marginBottom: "0.4rem" }}>
        <h2 style={{ color: ORO, letterSpacing: "0.1em", margin: 0 }}>🔍 CONTRALORÍA</h2>
        <span style={{ fontSize: "0.72rem", opacity: 0.55, textTransform: "uppercase", letterSpacing: "0.14em" }}>
          Auditoría Independiente DashAI · Aprobaciones vs. Realidad
        </span>
      </div>
      <div style={{ fontSize: "0.75rem", opacity: 0.6, marginBottom: "1.2rem" }}>
        Cada respuesta de la MESA se valida contra el Modelo Predictivo local (calibración {m.ventana_dias || 180} días, sin costo de nube).
      </div>

      <div data-testid="contraloria-modelo" style={{ display: "flex", flexWrap: "wrap", gap: "0.8rem", marginBottom: "1.2rem" }}>
        {[
          { lbl: "Base MESA (180d)", val: m.base != null ? `${Math.round(m.base * 100)}%` : "—", color: ORO },
          { lbl: "Aprobadas", val: m.aprobadas ?? "—", color: ORO },
          { lbl: "Rechazadas", val: m.rechazadas ?? "—", color: RUBI },
          { lbl: "Bajo Auditoría", val: inconsistencias, color: inconsistencias ? RUBI : ORO },
        ].map((s, i) => (
          <div key={i} style={{ minWidth: 150, background: "rgba(255,255,255,0.03)", padding: "0.7rem 1rem",
            border: `1px solid ${s.color === RUBI && s.val !== 0 && s.val !== "—" ? "rgba(225,29,72,0.45)" : "rgba(212,175,55,0.3)"}`, textAlign: "center" }}>
            <div style={{ fontSize: "1.4rem", fontWeight: 800, color: s.color, fontFamily: "'JetBrains Mono', monospace" }}>{s.val}</div>
            <div style={{ fontSize: "0.65rem", opacity: 0.7, textTransform: "uppercase", letterSpacing: "0.1em" }}>{s.lbl}</div>
          </div>
        ))}
        <button data-testid="contraloria-calibrar-btn" onClick={calibrar} disabled={loading}
          style={{ marginLeft: "auto", alignSelf: "center", background: "transparent", color: ORO,
            border: "1px solid rgba(212,175,55,0.5)", padding: "0.5rem 1.2rem", cursor: "pointer",
            fontWeight: 700, fontSize: "0.75rem", letterSpacing: "0.08em" }}>
          <i className={`fa ${loading ? "fa-cog fa-spin" : "fa-refresh"}`} style={{ marginRight: 6 }} />
          Recalibrar Modelo
        </button>
      </div>

      {(m.motivos_rechazo || []).length > 0 && (
        <div style={{ marginBottom: "1.2rem", border: "1px solid rgba(225,29,72,0.3)", background: "rgba(30,6,12,0.5)", padding: "0.8rem 1.1rem" }}>
          <b style={{ color: RUBI, fontSize: "0.78rem", letterSpacing: "0.08em" }}>MOTIVOS DE RECHAZO DETECTADOS (minería local)</b>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
            {m.motivos_rechazo.map((mo, i) => (
              <span key={i} style={{ fontSize: "0.7rem", color: "#fda4af", border: "1px solid rgba(225,29,72,0.35)", padding: "0.15rem 0.6rem" }}>
                {mo.motivo} · {mo.casos}
              </span>
            ))}
          </div>
        </div>
      )}

      <div style={{ border: "1px solid rgba(212,175,55,0.25)", background: "rgba(10,10,12,0.9)" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.78rem" }} data-testid="contraloria-tabla">
          <thead>
            <tr style={{ borderBottom: "1px solid rgba(212,175,55,0.3)" }}>
              {["Fecha", "Cliente", "Respuesta MESA", "Veredicto DashAI", "Criterios Incumplidos", "Estado"].map(h => (
                <th key={h} style={{ padding: "0.7rem 0.9rem", textAlign: "left", color: ORO,
                  fontSize: "0.65rem", textTransform: "uppercase", letterSpacing: "0.12em" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={6} style={{ padding: "1.5rem", textAlign: "center", opacity: 0.6 }}>
              <i className="fa fa-cog fa-spin" /> Auditando respuestas de la MESA…</td></tr>}
            {!loading && casos.length === 0 && <tr><td colSpan={6} style={{ padding: "1.5rem", textAlign: "center", opacity: 0.6 }}>
              Sin respuestas de MESA en la ventana de auditoría.</td></tr>}
            {!loading && casos.map((c, i) => {
              const audit = c.estado_auditoria === "BAJO AUDITORÍA";
              return (
                <tr key={i} data-testid={`contraloria-fila-${i}`} style={{ borderBottom: "1px solid rgba(255,255,255,0.05)",
                  background: audit ? "rgba(225,29,72,0.07)" : "transparent" }}>
                  <td style={{ padding: "0.6rem 0.9rem", opacity: 0.7, whiteSpace: "nowrap" }}>{(c.fecha || "").slice(0, 10)}</td>
                  <td style={{ padding: "0.6rem 0.9rem", fontWeight: 600 }}>{c.cliente}</td>
                  <td style={{ padding: "0.6rem 0.9rem" }}>
                    <span style={{ color: c.respuesta_mesa === "aprobacion" ? "#10d98e" : RUBI, fontWeight: 700, textTransform: "uppercase", fontSize: "0.7rem" }}>
                      {c.respuesta_mesa === "aprobacion" ? "Aprobada" : "Rechazada"}
                    </span>
                  </td>
                  <td style={{ padding: "0.6rem 0.9rem" }} title={(c.factores || []).join("\n")}>
                    {c.prob_dashai != null ? `Probabilidad de Aprobación MESA: ${c.prob_dashai}%` : "sin carpeta"}
                  </td>
                  <td style={{ padding: "0.6rem 0.9rem", color: "#fda4af", fontSize: "0.72rem" }}>
                    {(c.criterios_fallidos || []).join(" · ") || "—"}
                  </td>
                  <td style={{ padding: "0.6rem 0.9rem" }}>
                    <span data-testid={`contraloria-estado-${i}`} style={{ fontWeight: 800, fontSize: "0.68rem", letterSpacing: "0.08em",
                      padding: "0.2rem 0.7rem",
                      color: audit ? "#fff" : "#0a0a0a",
                      background: audit ? "linear-gradient(135deg, #9f1239, #e11d48)" : "linear-gradient(135deg, #BF953F, #FCF6BA, #AA771C)",
                      boxShadow: audit ? "0 0 18px -6px rgba(225,29,72,0.8)" : "none" }}>
                      {c.estado_auditoria}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
