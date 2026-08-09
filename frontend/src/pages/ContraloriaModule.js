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
  const v60 = m.ventana_60 || {};
  const casos = data?.casos || [];
  const inconsistencias = casos.filter(c => c.estado_auditoria === "BAJO AUDITORÍA").length;
  const recibidos = casos.filter(c => c.estado_auditoria === "RECIBIDO DE MESA").length;

  return (
    <div className="module-content" data-testid="contraloria-module">
      <div style={{ display: "flex", alignItems: "baseline", gap: 14, marginBottom: "0.4rem" }}>
        <h2 style={{ color: ORO, letterSpacing: "0.1em", margin: 0 }}>🔍 CONTRALORÍA</h2>
        <span style={{ fontSize: "0.72rem", opacity: 0.55, textTransform: "uppercase", letterSpacing: "0.14em" }}>
          Auditoría Independiente DashAI · Aprobaciones vs. Realidad
        </span>
      </div>
      <div style={{ fontSize: "0.75rem", opacity: 0.6, marginBottom: "1.2rem" }}>
        Modo Espejo: solo se auditan expedientes con documentación COMPLETA (Cédula, Liquidaciones, AFP y CMF).
        Los incompletos quedan como "Recibido de MESA" — sin análisis, sin falsos positivos.
      </div>

      <div data-testid="contraloria-modelo" style={{ display: "flex", flexWrap: "wrap", gap: "0.8rem", marginBottom: "1.2rem" }}>
        {[
          { lbl: "Regla de Oro (60d)", val: v60.base != null ? `${Math.round(v60.base * 100)}%` : "—", color: ORO },
          { lbl: "Base histórica (180d)", val: m.base != null ? `${Math.round(m.base * 100)}%` : "—", color: ORO },
          { lbl: "Aprobadas 60d", val: v60.aprobadas ?? m.aprobadas ?? "—", color: ORO },
          { lbl: "Rechazadas 60d", val: v60.rechazadas ?? m.rechazadas ?? "—", color: RUBI },
          { lbl: "Bajo Auditoría", val: inconsistencias, color: inconsistencias ? RUBI : ORO },
          { lbl: "Recibido de MESA", val: recibidos, color: "#9ca3af" },
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

      {m.tendencia && (
        <div data-testid="contraloria-tendencia" style={{ marginBottom: "1rem", padding: "0.7rem 1.1rem",
          border: "1px solid rgba(212,175,55,0.4)", background: "rgba(30,26,12,0.7)", color: "#F5E7B8", fontSize: "0.8rem" }}>
          <i className="fa fa-line-chart" style={{ marginRight: 8, color: ORO }} />{m.tendencia}
        </div>
      )}
      {(m.ajustes_mercado || []).length > 0 && (
        <div data-testid="contraloria-ajustes" style={{ marginBottom: "1.2rem", border: "1px solid rgba(212,175,55,0.35)",
          background: "rgba(18,18,20,0.9)", padding: "0.8rem 1.1rem" }}>
          <b style={{ color: ORO, fontSize: "0.78rem", letterSpacing: "0.08em" }}>⚡ AJUSTES DE MERCADO SUGERIDOS (60 días)</b>
          {m.ajustes_mercado.map((a, i) => (
            <div key={i} style={{ fontSize: "0.75rem", color: "#F5E7B8", marginTop: 6, opacity: 0.85 }}>• {a}</div>
          ))}
        </div>
      )}
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
              const recibido = c.estado_auditoria === "RECIBIDO DE MESA";
              return (
                <tr key={i} data-testid={`contraloria-fila-${i}`} style={{ borderBottom: "1px solid rgba(255,255,255,0.05)",
                  background: audit ? "rgba(225,29,72,0.07)" : "transparent",
                  opacity: recibido ? 0.65 : 1 }}>
                  <td style={{ padding: "0.6rem 0.9rem", opacity: 0.7, whiteSpace: "nowrap" }}>{(c.fecha || "").slice(0, 10)}</td>
                  <td style={{ padding: "0.6rem 0.9rem", fontWeight: 600 }}>{c.cliente}</td>
                  <td style={{ padding: "0.6rem 0.9rem" }}>
                    <span style={{ color: c.respuesta_mesa === "aprobacion" ? "#10d98e" : RUBI, fontWeight: 700, textTransform: "uppercase", fontSize: "0.7rem" }}>
                      {c.respuesta_mesa === "aprobacion" ? "Aprobada" : "Rechazada"}
                    </span>
                  </td>
                  <td style={{ padding: "0.6rem 0.9rem" }} title={(c.factores || []).join("\n")}>
                    {recibido
                      ? <span style={{ fontStyle: "italic", opacity: 0.8 }}>Documentación incompleta — auditoría no aplicada</span>
                      : (c.prob_dashai != null ? `Probabilidad de Aprobación MESA: ${c.prob_dashai}%` : "sin carpeta")}
                  </td>
                  <td style={{ padding: "0.6rem 0.9rem", color: recibido ? "#9ca3af" : "#fda4af", fontSize: "0.72rem" }}>
                    {recibido
                      ? ((c.docs_faltantes || []).length ? `Faltan: ${c.docs_faltantes.join(" · ")}` : "—")
                      : ((c.criterios_fallidos || []).join(" · ") || "—")}
                  </td>
                  <td style={{ padding: "0.6rem 0.9rem" }}>
                    <span data-testid={`contraloria-estado-${i}`} style={{ fontWeight: 800, fontSize: "0.68rem", letterSpacing: "0.08em",
                      padding: "0.2rem 0.7rem",
                      color: audit ? "#fff" : recibido ? "#d1d5db" : "#0a0a0a",
                      background: audit ? "linear-gradient(135deg, #9f1239, #e11d48)"
                        : recibido ? "rgba(255,255,255,0.08)"
                        : "linear-gradient(135deg, #BF953F, #FCF6BA, #AA771C)",
                      border: recibido ? "1px solid rgba(255,255,255,0.2)" : "none",
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
