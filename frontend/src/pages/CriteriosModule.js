import { useState, useEffect } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

const ORO = "var(--gold, #D4AF37)";
const LABELS = {
  btg_pactual: "BTG Pactual", ameris: "Ameris (Packard)", parametros_generales: "Parámetros Generales",
  con_subsidio: "Con Subsidio", sin_subsidio: "Sin Subsidio", castigos_renta: "Castigos de Renta",
};
const OCULTOS = ["version", "updated_at", "manual_override", "prioridad", "_key", "_id"];

function nombreCampo(k) {
  return LABELS[k] || k.replace(/_/g, " ").replace(/\buf\b/gi, "UF").replace(/\bltv\b/gi, "LTV")
    .replace(/^./, c => c.toUpperCase());
}

const filaStyle = {
  display: "flex", justifyContent: "space-between", alignItems: "center",
  padding: "0.3rem 0", borderBottom: "1px solid rgba(255,255,255,0.05)", gap: 10,
};
const inputStyle = {
  width: 110, background: "rgba(255,255,255,0.05)", color: ORO, fontWeight: 700,
  border: "1px solid rgba(212,175,55,0.35)", padding: "0.25rem 0.5rem", textAlign: "right",
  fontFamily: "'JetBrains Mono', monospace", fontSize: "0.78rem",
};

function renderCampos(nodo, path, onChange) {
  const items = [];
  for (const [k, v] of Object.entries(nodo)) {
    if (k.startsWith("_") || OCULTOS.includes(k)) continue;
    const p = [...path, k];
    const pid = p.join(".");
    if (typeof v === "number") {
      items.push(
        <div key={pid} style={filaStyle}>
          <span style={{ fontSize: "0.75rem", opacity: 0.75 }}>{nombreCampo(k)}</span>
          <input data-testid={`criterio-${pid}`} type="number" step="any" value={v}
            onChange={e => onChange(p, e.target.value === "" ? 0 : Number(e.target.value))}
            style={inputStyle} />
        </div>
      );
    } else if (typeof v === "string" && ["Si", "No", "Sí"].includes(v)) {
      items.push(
        <div key={pid} style={filaStyle}>
          <span style={{ fontSize: "0.75rem", opacity: 0.75 }}>{nombreCampo(k)}</span>
          <select data-testid={`criterio-${pid}`} value={v} onChange={e => onChange(p, e.target.value)}
            style={{ background: "rgba(255,255,255,0.05)", color: ORO, fontWeight: 700,
              border: "1px solid rgba(212,175,55,0.35)", padding: "0.25rem 0.5rem" }}>
            <option value="Si">Sí</option>
            <option value="No">No</option>
          </select>
        </div>
      );
    } else if (v && typeof v === "object" && !Array.isArray(v)) {
      items.push(
        <div key={`${pid}-h`} style={{ fontSize: "0.7rem", fontWeight: 800, color: ORO,
          textTransform: "uppercase", letterSpacing: "0.1em", margin: "0.7rem 0 0.2rem" }}>
          {nombreCampo(k)}
        </div>
      );
      items.push(...renderCampos(v, p, onChange));
    }
  }
  return items;
}

export default function CriteriosModule() {
  const [criteria, setCriteria] = useState(null);
  const [modal, setModal] = useState(false);
  const [clave, setClave] = useState("");
  const [msg, setMsg] = useState("");
  const [dirty, setDirty] = useState(false);

  const cargar = () => axios.get(`${API_URL}/api/admin/criterios`)
    .then(r => { setCriteria(r.data); setDirty(false); }).catch(() => {});
  useEffect(() => { cargar(); }, []);

  const onChange = (path, val) => {
    setCriteria(prev => {
      const next = JSON.parse(JSON.stringify(prev));
      let n = next;
      for (const k of path.slice(0, -1)) n = n[k];
      n[path[path.length - 1]] = val;
      return next;
    });
    setDirty(true);
  };

  const guardar = async () => {
    try {
      const r = await axios.post(`${API_URL}/api/admin/criterios`, { clave, criterios: criteria });
      setMsg(`✅ ${r.data.nota}`);
      setModal(false); setClave(""); setDirty(false);
      cargar();
    } catch (e) {
      setMsg(`🚨 ${e.response?.data?.detail || "Error al guardar"}`);
      setModal(false); setClave("");
      cargar();
    }
  };

  if (!criteria) return <div className="module-content">Cargando bóveda de reglas…</div>;

  return (
    <div className="module-content" data-testid="criterios-module">
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: "0.3rem" }}>
        <h2 style={{ color: ORO, letterSpacing: "0.08em", margin: 0 }}>⚙ CONFIGURACIÓN DE ESCENARIOS</h2>
        <span style={{ fontSize: "0.7rem", opacity: 0.55, textTransform: "uppercase", letterSpacing: "0.12em" }}>
          Ajuste de Algoritmo · Bóveda de Reglas MESA
        </span>
      </div>
      <div style={{ fontSize: "0.74rem", opacity: 0.6, marginBottom: "1rem" }}>
        {criteria.manual_override
          ? "🔐 Reglas manuales ACTIVAS — prioridad suprema sobre los patrones aprendidos del historial."
          : "Criterios por defecto. Al guardar con la clave maestra, tus reglas toman prioridad absoluta."}
      </div>
      {msg && (
        <div data-testid="criterios-msg" style={{ marginBottom: "1rem", padding: "0.7rem 1rem",
          border: `1px solid ${msg.startsWith("✅") ? "rgba(212,175,55,0.5)" : "rgba(225,29,72,0.5)"}`,
          color: msg.startsWith("✅") ? "#F5E7B8" : "#fda4af",
          background: msg.startsWith("✅") ? "rgba(30,26,12,0.9)" : "rgba(40,6,14,0.9)" }}>{msg}</div>
      )}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: "1rem" }}>
        {["btg_pactual", "ameris", "parametros_generales"].map(sec => criteria[sec] && (
          <div key={sec} style={{ background: "linear-gradient(160deg, rgba(18,18,20,0.97), rgba(6,6,8,0.99))",
            border: "1px solid rgba(212,175,55,0.3)", padding: "1rem 1.2rem" }}>
            <div style={{ fontWeight: 800, color: ORO, letterSpacing: "0.08em", marginBottom: "0.5rem" }}>
              <i className="fa fa-bank" style={{ marginRight: 8 }} />{nombreCampo(sec)}
            </div>
            {renderCampos(criteria[sec], [sec], onChange)}
          </div>
        ))}
      </div>
      <div style={{ position: "sticky", bottom: 0, marginTop: "1.2rem", textAlign: "right" }}>
        <button data-testid="criterios-guardar-btn" className="shimmer-oro" disabled={!dirty} onClick={() => { setMsg(""); setModal(true); }}
          style={{ padding: "0.7rem 2rem", fontWeight: 800, fontSize: "0.85rem", letterSpacing: "0.08em",
            cursor: dirty ? "pointer" : "not-allowed", border: "none", color: "#0a0a0a",
            backgroundImage: "linear-gradient(135deg, #BF953F, #FCF6BA 45%, #B38728, #FBF5B7 80%, #AA771C)",
            boxShadow: dirty ? "0 0 30px -8px rgba(212,175,55,0.8)" : "none", opacity: dirty ? 1 : 0.45 }}>
          <i className="fa fa-diamond" style={{ marginRight: 8 }} />Guardar Cambios
        </button>
      </div>

      {modal && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)", zIndex: 1000,
          display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div data-testid="criterios-modal-clave" style={{ width: 360, background: "linear-gradient(160deg, #141416, #060608)",
            border: "1px solid rgba(212,175,55,0.5)", padding: "1.5rem", boxShadow: "0 0 60px -15px rgba(212,175,55,0.5)" }}>
            <div style={{ color: ORO, fontWeight: 800, letterSpacing: "0.1em", marginBottom: 6 }}>
              🔐 BLOQUEO DE SEGURIDAD
            </div>
            <div style={{ fontSize: "0.75rem", opacity: 0.7, marginBottom: 12 }}>
              Ingrese la clave maestra para aplicar los cambios al algoritmo de la MESA. Clave incorrecta = cambios descartados + alerta.
            </div>
            <input data-testid="criterios-clave-input" type="password" value={clave} autoFocus
              onChange={e => setClave(e.target.value)} placeholder="Clave maestra"
              onKeyDown={e => e.key === "Enter" && guardar()}
              style={{ width: "100%", background: "rgba(255,255,255,0.06)", color: ORO, fontWeight: 800,
                border: "1px solid rgba(212,175,55,0.4)", padding: "0.6rem 0.8rem", letterSpacing: "0.4em",
                textAlign: "center", fontSize: "1.1rem", marginBottom: 14, boxSizing: "border-box" }} />
            <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
              <button data-testid="criterios-modal-cancelar" onClick={() => { setModal(false); setClave(""); }}
                style={{ background: "transparent", color: "#94a3b8", border: "1px solid rgba(255,255,255,0.15)",
                  padding: "0.5rem 1.1rem", cursor: "pointer", fontSize: "0.78rem" }}>Cancelar</button>
              <button data-testid="criterios-modal-confirmar" onClick={guardar}
                style={{ border: "none", color: "#0a0a0a", fontWeight: 800, padding: "0.5rem 1.4rem", cursor: "pointer",
                  backgroundImage: "linear-gradient(135deg, #BF953F, #FCF6BA 50%, #AA771C)", fontSize: "0.78rem" }}>
                Validar y Guardar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
