import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

const ORO = "var(--gold, #D4AF37)";
const panel = {
  border: "1px solid rgba(212,175,55,0.35)",
  background: "linear-gradient(160deg, #0d0b06, #050505)",
  padding: "1.2rem 1.4rem", marginBottom: "1.2rem",
};
const btnOro = {
  background: "linear-gradient(135deg, #BF953F, #FCF6BA 45%, #B38728)", color: "#0a0a0a",
  border: "none", fontWeight: 800, fontSize: "0.72rem", letterSpacing: "0.08em",
  padding: "0.6rem 1.2rem", cursor: "pointer",
};

const Badge = ({ cat }) => (
  <span style={{ fontWeight: 800, fontSize: "0.63rem", letterSpacing: "0.06em", padding: "0.15rem 0.55rem",
    whiteSpace: "nowrap", color: "#0a0a0a",
    background: cat === "RIESGO" ? "linear-gradient(135deg,#e11d48,#fb7185)"
      : cat === "PERDIDA" ? "linear-gradient(135deg,#d97706,#fbbf24)"
        : cat === "NO AUDITABLE" ? "linear-gradient(135deg,#64748b,#cbd5e1)" : "linear-gradient(135deg,#60a5fa,#bfdbfe)" }}>
    {cat}
  </span>
);

export default function AuditoriaForenseModule() {
  const [forense, setForense] = useState(null);
  const [q, setQ] = useState("");
  const [busqueda, setBusqueda] = useState(null);
  const [buscando, setBuscando] = useState(false);

  const cargar = useCallback(async () => {
    try {
      const r = await axios.get(`${API_URL}/api/contraloria/forense`);
      setForense(r.data);
    } catch { /* silencioso */ }
  }, []);
  useEffect(() => { cargar(); }, [cargar]);

  const lanzar = async () => {
    try {
      await axios.post(`${API_URL}/api/contraloria/forense/iniciar?dias=280`);
      setForense({ estado: "en_proceso", progreso: 0, total: 0 });
      const iv = setInterval(async () => {
        const r = await axios.get(`${API_URL}/api/contraloria/forense`);
        setForense(r.data);
        if (r.data?.estado === "completado") clearInterval(iv);
      }, 4000);
    } catch { /* silencioso */ }
  };

  const buscar = async () => {
    if (q.trim().length < 3) return;
    setBuscando(true);
    setBusqueda(null);
    try {
      const r = await axios.get(`${API_URL}/api/contraloria/forense/buscar`, { params: { q }, timeout: 120000 });
      setBusqueda(r.data);
    } catch (e) { setBusqueda({ error: e?.response?.data?.detail || e.message }); }
    setBuscando(false);
  };

  const hallazgos = forense?.hallazgos || [];
  const listaA = hallazgos.filter(h => h.categoria === "RIESGO" || h.categoria === "ERROR HUMANO");
  const listaB = hallazgos.filter(h => h.categoria === "PERDIDA");
  const noAuditables = hallazgos.filter(h => h.categoria === "NO AUDITABLE");

  const rellenar = async () => {
    if (!window.confirm("🤖 RELLENADO DE DATOS (280 días)\n\n¿Extraer monto, renta y subsidio de los PDFs de aprobación y guardarlos en las fichas?\n\nSe ejecuta por lotes suaves, sin gasto de créditos LLM.")) return;
    try {
      const r = await axios.post(`${API_URL}/api/contraloria/forense/backfill?dias=280`);
      alert(r.data.mensaje);
    } catch (e) { alert("❌ " + (e?.response?.data?.detail || e.message)); }
  };

  const FilaHallazgo = ({ h, k }) => (
    <div key={k} style={{ display: "flex", gap: 10, alignItems: "baseline", padding: "0.5rem 0",
      borderTop: "1px solid rgba(255,255,255,0.06)", fontSize: "0.78rem", flexWrap: "wrap" }}>
      <Badge cat={h.categoria} />
      <b style={{ color: "#f8fafc" }}>{h.cliente}</b>
      <span style={{ color: "#9a8c52", fontFamily: "monospace", fontSize: "0.72rem" }}>{h.rut || "sin RUT"}</span>
      <span style={{ color: "#6b6b6b", fontSize: "0.68rem" }}>{h.fecha_mesa}</span>
      <span style={{ color: "#cbd5e1", flexBasis: "100%", fontSize: "0.74rem" }}>{h.detalle}</span>
      {h.nota_dashai && <span style={{ color: "#9a8c52", flexBasis: "100%", fontSize: "0.7rem", fontStyle: "italic", borderLeft: `2px solid ${ORO}`, paddingLeft: 8 }}>{h.nota_dashai}</span>}
    </div>
  );

  return (
    <div className="module-content" data-testid="auditoria-forense-module">
      <div style={{ display: "flex", alignItems: "baseline", gap: 14, marginBottom: "1.2rem" }}>
        <h2 style={{ color: ORO, letterSpacing: "0.1em", margin: 0 }}>📋 AUDITORÍA FORENSE</h2>
        <span style={{ fontSize: "0.72rem", opacity: 0.55, textTransform: "uppercase", letterSpacing: "0.14em" }}>
          Barrido histórico 280 días · Bóveda de Criterios DashAI como único juez · lotes anti-estrés
        </span>
      </div>

      {forense?.nota_trazabilidad && (
        <div data-testid="af-trazabilidad" style={{ color: "#9a8c52", fontSize: "0.72rem", fontStyle: "italic", marginBottom: "0.9rem", borderLeft: `2px solid ${ORO}`, paddingLeft: 10 }}>
          🔏 {forense.nota_trazabilidad}
        </div>
      )}

      <div style={panel} data-testid="af-panel-control">
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 240 }}>
            <div style={{ color: ORO, fontSize: "0.72rem", letterSpacing: "0.18em", textTransform: "uppercase" }}>Motor de Análisis Histórico</div>
            <div style={{ color: "#9a8c52", fontSize: "0.72rem", marginTop: 3 }}>
              Contrasta cada decisión de MESA contra: mínimo 2.000 UF sin subsidio · Edad+Plazo &lt; 80 años · Carga financiera &lt; 40% · antigüedad 12 meses
            </div>
          </div>
          {forense?.estado === "en_proceso" && (
            <span style={{ color: "#C7B36A", fontSize: "0.78rem" }}><i className="fa fa-cog fa-spin" /> Procesando {forense.progreso || 0}/{forense.total || "…"}</span>
          )}
          {forense?.estado === "completado" && (
            <span style={{ color: "#8fd9b0", fontSize: "0.72rem" }}>✓ {(forense.generado_en || "").slice(0, 16).replace("T", " ")} · {forense.progreso} casos · período {forense.periodo_dias}d</span>
          )}
          <button data-testid="af-backfill-btn" onClick={rellenar}
            style={{ ...btnOro, background: "rgba(212,175,55,0.15)", color: "#e7cf7a", border: "1px solid rgba(212,175,55,0.4)" }}>
            🤖 RELLENADO DE DATOS
          </button>
          <button data-testid="af-lanzar-btn" onClick={lanzar} disabled={forense?.estado === "en_proceso"}
            style={{ ...btnOro, opacity: forense?.estado === "en_proceso" ? 0.5 : 1 }}>
            LANZAR BARRIDO 280 DÍAS
          </button>
        </div>
      </div>

      <div style={panel} data-testid="af-panel-busqueda">
        <div style={{ color: ORO, fontSize: "0.72rem", letterSpacing: "0.18em", textTransform: "uppercase", marginBottom: 10 }}>🔎 Búsqueda Rápida por RUT o Nombre</div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <input data-testid="af-buscar-input" value={q} onChange={e => setQ(e.target.value)}
            onKeyDown={e => e.key === "Enter" && buscar()}
            placeholder="Ej: 16.845.321-0 o Christian Pasten"
            style={{ flex: 1, minWidth: 220, background: "#050505", border: "1px solid #7a6a2f", color: "#FCF6BA",
              padding: "0.65rem 0.9rem", fontSize: "0.9rem", outline: "none" }} />
          <button data-testid="af-buscar-btn" onClick={buscar} disabled={buscando} style={btnOro}>
            {buscando ? "AUDITANDO…" : "AUDITAR AL INSTANTE"}
          </button>
        </div>
        {busqueda?.error && <div style={{ color: "#fda4af", fontSize: "0.78rem", marginTop: 10 }}>⚠ {busqueda.error}</div>}
        {busqueda?.mensaje && <div style={{ color: "#9a8c52", fontSize: "0.78rem", marginTop: 10 }}>{busqueda.mensaje}</div>}
        {(busqueda?.casos || []).map((c, i) => (
          <div key={i} data-testid={`af-caso-${i}`} style={{ borderTop: "1px solid rgba(255,255,255,0.07)", padding: "0.6rem 0", marginTop: 8 }}>
            <div style={{ display: "flex", gap: 10, alignItems: "baseline", flexWrap: "wrap", fontSize: "0.8rem" }}>
              <b style={{ color: "#f8fafc" }}>{c.cliente}</b>
              <span style={{ color: "#6b6b6b", fontSize: "0.7rem" }}>{c.fecha}</span>
              <span style={{ color: c.respuesta_mesa === "Aprobada" ? "#10d98e" : "#fb7185", fontWeight: 700, fontSize: "0.72rem" }}>MESA: {c.respuesta_mesa}</span>
              <span style={{ fontWeight: 800, fontSize: "0.72rem", color: (c.hallazgos || []).length ? "#fbbf24" : "#8fd9b0" }}>{c.veredicto}</span>
            </div>
            {(c.hallazgos || []).map((h, k) => <FilaHallazgo h={h} k={k} key={k} />)}
          </div>
        ))}
      </div>

      {forense?.estado === "completado" && (
        <>
          <div style={panel} data-testid="af-lista-a">
            <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 8 }}>
              <b style={{ color: "#fb7185", fontSize: "0.78rem", letterSpacing: "0.08em" }}>LISTA A — APROBACIONES CUESTIONABLES ({listaA.length})</b>
              <button data-testid="af-descargar-a" onClick={() => window.open(`${API_URL}/api/contraloria/forense/descargar?lista=A`, "_blank")}
                style={{ ...btnOro, marginLeft: "auto", fontSize: "0.66rem", padding: "0.45rem 1rem" }}>
                <i className="fa fa-download" style={{ marginRight: 6 }} />DESCARGAR CSV
              </button>
            </div>
            {listaA.length === 0 && <div style={{ color: "#8fd9b0", fontSize: "0.78rem" }}>✓ Sin aprobaciones fuera de regla en el período.</div>}
            {listaA.map((h, k) => <FilaHallazgo h={h} k={k} key={k} />)}
          </div>

          <div style={panel} data-testid="af-lista-b">
            <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 8 }}>
              <b style={{ color: "#fbbf24", fontSize: "0.78rem", letterSpacing: "0.08em" }}>LISTA B — OPORTUNIDADES RESCATABLES ({listaB.length})</b>
              <button data-testid="af-descargar-b" onClick={() => window.open(`${API_URL}/api/contraloria/forense/descargar?lista=B`, "_blank")}
                style={{ ...btnOro, marginLeft: "auto", fontSize: "0.66rem", padding: "0.45rem 1rem" }}>
                <i className="fa fa-download" style={{ marginRight: 6 }} />DESCARGAR CSV
              </button>
            </div>
            {listaB.length === 0 && <div style={{ color: "#9a8c52", fontSize: "0.78rem" }}>Sin rechazos rescatables detectados en el período.</div>}
            {listaB.map((h, k) => <FilaHallazgo h={h} k={k} key={k} />)}
          </div>
          <div style={panel} data-testid="af-no-auditables">
            <b style={{ color: "#cbd5e1", fontSize: "0.78rem", letterSpacing: "0.08em" }}>⚠️ NO AUDITABLES — SIN EXPEDIENTE DIGITAL ({noAuditables.length})</b>
            {noAuditables.length === 0 && <div style={{ color: "#8fd9b0", fontSize: "0.78rem", marginTop: 6 }}>✓ Todos los casos del período tienen expediente digital.</div>}
            {noAuditables.map((h, k) => <FilaHallazgo h={h} k={k} key={k} />)}
          </div>
        </>
      )}
    </div>
  );
}
