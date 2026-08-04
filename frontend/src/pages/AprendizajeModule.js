import React, { useState, useEffect } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

const PRIO_COLOR = { alta: "#f87171", media: "#fbbf24", baja: "#4ade80" };

export default function AprendizajeModule() {
  const [analisis, setAnalisis] = useState([]);
  const [notas, setNotas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [analizando, setAnalizando] = useState(false);
  const [nota, setNota] = useState("");
  const [msg, setMsg] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/aprendizaje`);
      setAnalisis(r.data.analisis || []);
      setNotas(r.data.notas || []);
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const analizar = async () => {
    setAnalizando(true); setMsg("");
    try {
      await axios.post(`${API}/api/aprendizaje/analizar`, {}, { timeout: 180000 });
      setMsg("✅ Ciclo de aprendizaje completado con los datos reales del flujo.");
      load();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setAnalizando(false);
  };

  const agregarNota = async () => {
    if (nota.trim().length < 5) return;
    try {
      await axios.post(`${API}/api/aprendizaje/nota`, { texto: nota.trim() });
      setNota(""); setMsg("✅ Nota guardada — la IA la usará en su próximo ciclo de aprendizaje.");
      load();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
  };

  const fmtF = (iso) => { try { return new Date(iso).toLocaleString("es-CL"); } catch { return "—"; } };
  const ultimo = analisis[0];

  const card = { background: "rgba(15,23,42,0.85)", border: "1px solid rgba(148,163,184,0.15)", borderRadius: 12, padding: "1.2rem 1.4rem" };

  return (
    <div data-testid="aprendizaje-module" style={{ display: "grid", gap: "1rem" }}>
      <div style={card}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <h2 style={{ margin: 0, fontSize: "1.15rem", color: "var(--gold, #60a5fa)" }}>
            <i className="fa fa-graduation-cap" /> Aprendizaje IA — Flujo de información comercial
          </h2>
          <button data-testid="aprendizaje-analizar" onClick={analizar} disabled={analizando}
            style={{ marginLeft: "auto", background: "#7c3aed", border: "none", color: "#fff", borderRadius: 8, padding: "0.55rem 1.2rem", fontSize: 13, fontWeight: 800, cursor: "pointer" }}>
            <i className={`fa ${analizando ? "fa-spinner fa-spin" : "fa-bolt"}`} /> {analizando ? "Aprendiendo del flujo…" : "Analizar flujo ahora"}
          </button>
        </div>
        <p style={{ margin: "0.6rem 0 0", fontSize: 12.5, color: "#94a3b8" }}>
          La IA aprende constantemente (ciclo automático diario + manual) del círculo comercial real:
          solicitud → carpeta → mesa → aprobación → tasación → estudio de título → gastos → escrituración → cierre.
          Regla inviolable: solo aprende de datos reales del sistema, sin inventar métricas.
        </p>
        {msg && <div data-testid="aprendizaje-msg" style={{ marginTop: 8, fontSize: 12.5, color: msg.startsWith("✅") ? "#4ade80" : "#f87171", fontWeight: 700 }}>{msg}</div>}
      </div>

      <div style={card}>
        <div style={{ fontWeight: 800, fontSize: 13.5, color: "#e2e8f0", marginBottom: 8 }}>
          <i className="fa fa-comment-o" style={{ color: "#7c3aed" }} /> Enséñale a la IA (notas del flujo comercial)
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <input data-testid="aprendizaje-nota-input" value={nota} onChange={e => setNota(e.target.value)}
            placeholder="Ej: Los ejecutivos de Ecomac responden más rápido por la mañana…"
            style={{ flex: 1, padding: "0.55rem", borderRadius: 8, border: "1px solid rgba(148,163,184,0.3)", background: "#1e293b", color: "#e2e8f0", fontSize: 13 }} />
          <button data-testid="aprendizaje-nota-guardar" onClick={agregarNota}
            style={{ background: "var(--gold, #60a5fa)", border: "none", color: "#0f172a", borderRadius: 8, padding: "0.55rem 1.1rem", fontSize: 12.5, fontWeight: 800, cursor: "pointer" }}>
            Guardar
          </button>
        </div>
        {notas.length > 0 && (
          <div style={{ marginTop: 10, display: "grid", gap: 4, maxHeight: 120, overflow: "auto" }}>
            {notas.map(n => (
              <div key={n.id} style={{ fontSize: 12, color: "#94a3b8" }}>• {n.texto} <span style={{ opacity: 0.5 }}>({fmtF(n.fecha)})</span></div>
            ))}
          </div>
        )}
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: "2rem", color: "#94a3b8" }}><i className="fa fa-spinner fa-spin" /> Cargando aprendizajes…</div>
      ) : !ultimo ? (
        <div data-testid="aprendizaje-empty" style={{ ...card, textAlign: "center", color: "#94a3b8" }}>
          Aún no hay ciclos de aprendizaje. Pulsá "Analizar flujo ahora" para el primero.
        </div>
      ) : (
        <>
          <div style={card} data-testid="aprendizaje-ultimo">
            <div style={{ fontSize: 11.5, color: "#94a3b8", marginBottom: 6 }}>Último ciclo: {fmtF(ultimo.fecha)} · método: {ultimo.metodo === "ia" ? "IA (GPT)" : "sin IA"}</div>
            <div style={{ fontSize: 14, color: "#e2e8f0", fontWeight: 600, lineHeight: 1.55 }}>{ultimo.resumen || "(sin resumen)"}</div>
            {ultimo.stats && (
              <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginTop: 12 }}>
                {[["Carpetas", ultimo.stats.total_carpetas], ["Aprobadas mesa", ultimo.stats.aprobadas_mesa],
                  ["Escrituración", ultimo.stats.en_escrituracion], ["Tasaciones", ultimo.stats.tasaciones_solicitadas],
                  ["Estudios", ultimo.stats.estudios_solicitados], ["Etapa 2", ultimo.stats.estudios_etapa2_enviados],
                  ["Reparos pend.", ultimo.stats.reparos_pendientes], ["Cierres consultados", ultimo.stats.cierres_consultados]]
                  .map(([l, v]) => (
                    <div key={l} style={{ background: "rgba(124,58,237,0.08)", border: "1px solid rgba(124,58,237,0.25)", borderRadius: 8, padding: "0.4rem 0.8rem", fontSize: 12 }}>
                      <b style={{ color: "#a78bfa", fontSize: 15 }}>{v ?? 0}</b> <span style={{ color: "#94a3b8" }}>{l}</span>
                    </div>
                  ))}
              </div>
            )}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "1rem" }}>
            <div style={card}>
              <div style={{ fontWeight: 800, fontSize: 13, color: "#4ade80", marginBottom: 8 }}><i className="fa fa-lightbulb-o" /> Aprendizajes del flujo</div>
              {(ultimo.aprendizajes || []).length === 0 ? <div style={{ fontSize: 12, color: "#64748b" }}>—</div>
                : (ultimo.aprendizajes || []).map((a, i) => <div key={i} style={{ fontSize: 12.5, color: "#cbd5e1", marginBottom: 6, lineHeight: 1.5 }}>• {a}</div>)}
            </div>
            <div style={card}>
              <div style={{ fontWeight: 800, fontSize: 13, color: "#f87171", marginBottom: 8 }}><i className="fa fa-exclamation-triangle" /> Cuellos de botella</div>
              {(ultimo.cuellos_botella || []).length === 0 ? <div style={{ fontSize: 12, color: "#64748b" }}>—</div>
                : (ultimo.cuellos_botella || []).map((a, i) => <div key={i} style={{ fontSize: 12.5, color: "#cbd5e1", marginBottom: 6, lineHeight: 1.5 }}>• {a}</div>)}
            </div>
          </div>

          <div style={card}>
            <div style={{ fontWeight: 800, fontSize: 13, color: "#a78bfa", marginBottom: 10 }}><i className="fa fa-rocket" /> Mejoras sugeridas al círculo comercial</div>
            {(ultimo.mejoras || []).length === 0 ? <div style={{ fontSize: 12, color: "#64748b" }}>—</div>
              : (ultimo.mejoras || []).map((m, i) => (
                <div key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start", background: "rgba(30,41,59,0.6)", borderRadius: 8, padding: "0.6rem 0.9rem", marginBottom: 6 }}>
                  <span style={{ background: `${PRIO_COLOR[m.prioridad] || "#fbbf24"}22`, color: PRIO_COLOR[m.prioridad] || "#fbbf24", border: `1px solid ${PRIO_COLOR[m.prioridad] || "#fbbf24"}`, borderRadius: 999, padding: "1px 10px", fontSize: 10.5, fontWeight: 800, textTransform: "uppercase", flexShrink: 0 }}>{m.prioridad}</span>
                  <div><b style={{ fontSize: 13 }}>{m.titulo}</b><div style={{ fontSize: 12.5, color: "#94a3b8", lineHeight: 1.5 }}>{m.detalle}</div></div>
                </div>
              ))}
          </div>

          {analisis.length > 1 && (
            <div style={card}>
              <div style={{ fontWeight: 800, fontSize: 13, color: "#94a3b8", marginBottom: 8 }}><i className="fa fa-history" /> Ciclos anteriores</div>
              {analisis.slice(1).map(a => (
                <div key={a.id} style={{ fontSize: 12, color: "#94a3b8", marginBottom: 6, lineHeight: 1.5 }}>
                  <b style={{ color: "#cbd5e1" }}>{fmtF(a.fecha)}:</b> {a.resumen || "(sin resumen)"}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
