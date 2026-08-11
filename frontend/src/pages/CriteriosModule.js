import { useState, useEffect } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";
import { secureGet } from "../utils/secureStore";

const ORO = "var(--gold, #D4AF37)";
const LABELS = {
  btg_pactual: "BTG Pactual", ameris: "Ameris (Packard)", parametros_generales: "Parámetros Generales",
  con_subsidio: "Con Subsidio", sin_subsidio: "Sin Subsidio", castigos_renta: "Castigos de Renta",
};
const OCULTOS = ["version", "updated_at", "manual_override", "prioridad", "_key", "_id", "reglas_supervisadas"];

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

function renderCampos(nodo, path, onChange, soloLectura) {
  const items = [];
  for (const [k, v] of Object.entries(nodo)) {
    if (k.startsWith("_") || OCULTOS.includes(k)) continue;
    const p = [...path, k];
    const pid = p.join(".");
    if (typeof v === "number") {
      items.push(
        <div key={pid} style={filaStyle}>
          <span style={{ fontSize: "0.75rem", opacity: 0.75 }}>{nombreCampo(k)}</span>
          <input data-testid={`criterio-${pid}`} type="number" step="any" value={v} disabled={soloLectura}
            onChange={e => onChange(p, e.target.value === "" ? 0 : Number(e.target.value))}
            style={{ ...inputStyle, opacity: soloLectura ? 0.55 : 1, cursor: soloLectura ? "not-allowed" : "text" }} />
        </div>
      );
    } else if (typeof v === "string" && ["Si", "No", "Sí"].includes(v)) {
      items.push(
        <div key={pid} style={filaStyle}>
          <span style={{ fontSize: "0.75rem", opacity: 0.75 }}>{nombreCampo(k)}</span>
          <select data-testid={`criterio-${pid}`} value={v} disabled={soloLectura} onChange={e => onChange(p, e.target.value)}
            style={{ background: "rgba(255,255,255,0.05)", color: ORO, fontWeight: 700,
              border: "1px solid rgba(212,175,55,0.35)", padding: "0.25rem 0.5rem", opacity: soloLectura ? 0.55 : 1 }}>
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
      items.push(...renderCampos(v, p, onChange, soloLectura));
    }
  }
  return items;
}

export default function CriteriosModule() {
  const user = secureGet("user") || {};
  const esMaestro = user.rol === "maestro";
  const [criteria, setCriteria] = useState(null);
  const [modal, setModal] = useState(false);
  const [clave, setClave] = useState("");
  const [msg, setMsg] = useState("");
  const [dirty, setDirty] = useState(false);
  const [historial, setHistorial] = useState([]);
  const [supervision, setSupervision] = useState({ pendientes: [], resueltos: [] });
  const [claveSup, setClaveSup] = useState("");

  const cargar = () => {
    axios.get(`${API_URL}/api/admin/criterios`).then(r => { setCriteria(r.data); setDirty(false); }).catch(() => {});
    axios.get(`${API_URL}/api/admin/criterios/auditoria`).then(r => setHistorial(r.data.historial || [])).catch(() => {});
    axios.get(`${API_URL}/api/admin/supervision`).then(r => setSupervision(r.data)).catch(() => {});
  };
  useEffect(() => { cargar(); }, []);

  const onChange = (path, val) => {
    if (!esMaestro) return;
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

  const resolver = async (pid, accion) => {
    if (!claveSup) { setMsg("🚨 Ingrese su clave (René Osa) para aprobar o rechazar patrones."); return; }
    try {
      await axios.post(`${API_URL}/api/admin/supervision/${pid}/resolver`, { accion, clave: claveSup });
      setMsg(`✅ Patrón ${accion === "aprobar" ? "aprobado como regla oficial" : "rechazado"} por René Osa.`);
      cargar();
    } catch (e) {
      setMsg(`🚨 ${e.response?.data?.detail || "Error"}`);
    }
  };

  if (!criteria) return <div className="module-content">Cargando bóveda de reglas…</div>;

  return (
    <div className="module-content" data-testid="criterios-module">
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: "0.3rem" }}>
        <h2 style={{ color: ORO, letterSpacing: "0.08em", margin: 0 }}>⚙ BÓVEDA DE CRITERIOS MAESTROS</h2>
        <span style={{ fontSize: "0.7rem", opacity: 0.55, textTransform: "uppercase", letterSpacing: "0.12em" }}>
          Propiedad de René Osa · Administrador Maestro (Nivel 1)
        </span>
      </div>
      <div data-testid="criterios-banner-mando" style={{ fontSize: "0.74rem", marginBottom: "1rem",
        padding: "0.55rem 0.9rem", border: `1px solid ${esMaestro ? "rgba(212,175,55,0.5)" : "rgba(148,163,184,0.35)"}`,
        color: esMaestro ? "#F5E7B8" : "#94a3b8", background: esMaestro ? "rgba(30,26,12,0.9)" : "rgba(20,20,24,0.9)" }}>
        {esMaestro
          ? "👑 Mando Supremo activo: usted (René Osa) es el único autorizado para modificar BTG Pactual, Ameris, políticas internas, umbrales y el Espejo MESA. Cada cambio exige su clave y queda auditado."
          : "🔒 Bóveda en MODO SOLO LECTURA — la gestión del Cerebro es responsabilidad exclusiva de René Osa. Este Maserati técnico obedece únicamente a su Constitución de riesgos."}
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
            {renderCampos(criteria[sec], [sec], onChange, !esMaestro)}
          </div>
        ))}
      </div>
      {esMaestro && (
        <div style={{ position: "sticky", bottom: 0, marginTop: "1.2rem", textAlign: "right" }}>
          <button data-testid="criterios-guardar-btn" className="shimmer-oro" disabled={!dirty} onClick={() => { setMsg(""); setModal(true); }}
            style={{ padding: "0.7rem 2rem", fontWeight: 800, fontSize: "0.85rem", letterSpacing: "0.08em",
              cursor: dirty ? "pointer" : "not-allowed", border: "none", color: "#0a0a0a",
              backgroundImage: "linear-gradient(135deg, #BF953F, #FCF6BA 45%, #B38728, #FBF5B7 80%, #AA771C)",
              boxShadow: dirty ? "0 0 30px -8px rgba(212,175,55,0.8)" : "none", opacity: dirty ? 1 : 0.45 }}>
            <i className="fa fa-diamond" style={{ marginRight: 8 }} />Guardar Cambios
          </button>
        </div>
      )}

      {/* ══ COLA DE SUPERVISIÓN DE RENÉ ══ */}
      <div style={{ marginTop: "1.6rem", background: "linear-gradient(160deg, rgba(18,18,20,0.97), rgba(6,6,8,0.99))",
        border: "1px solid rgba(212,175,55,0.3)", padding: "1rem 1.2rem" }} data-testid="supervision-panel">
        <div style={{ fontWeight: 800, color: ORO, letterSpacing: "0.08em", marginBottom: "0.4rem" }}>
          🧠 COLA DE SUPERVISIÓN DE RENÉ <span style={{ fontSize: "0.68rem", opacity: 0.6, fontWeight: 600 }}>
            — ningún patrón detectado por DashAI se vuelve regla oficial sin su aprobación</span>
        </div>
        {esMaestro && (supervision.pendientes || []).length > 0 && (
          <input data-testid="supervision-clave" type="password" value={claveSup} onChange={e => setClaveSup(e.target.value)}
            placeholder="Su clave (validación digital)" style={{ ...inputStyle, width: 220, textAlign: "left", marginBottom: 10 }} />
        )}
        {(supervision.pendientes || []).length === 0 && (
          <div style={{ fontSize: "0.75rem", opacity: 0.55 }}>Sin patrones pendientes de supervisión.</div>
        )}
        {(supervision.pendientes || []).map(p => (
          <div key={p.id} data-testid={`supervision-item-${p.id}`} style={{ ...filaStyle, alignItems: "flex-start" }}>
            <span style={{ fontSize: "0.75rem", opacity: 0.85, flex: 1 }}>
              <b style={{ color: ORO, textTransform: "uppercase", fontSize: "0.62rem" }}>{p.tipo}</b> · {p.texto}
              <span style={{ opacity: 0.45 }}> ({(p.detectado_en || "").slice(0, 10)})</span>
            </span>
            {esMaestro && (
              <span style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                <button data-testid={`supervision-aprobar-${p.id}`} onClick={() => resolver(p.id, "aprobar")}
                  style={{ background: "rgba(16,217,142,0.15)", color: "#10c98a", border: "1px solid rgba(16,217,142,0.5)",
                    padding: "0.2rem 0.7rem", cursor: "pointer", fontSize: "0.7rem", fontWeight: 800 }}>✓ Aprobar</button>
                <button data-testid={`supervision-rechazar-${p.id}`} onClick={() => resolver(p.id, "rechazar")}
                  style={{ background: "rgba(190,18,60,0.12)", color: "#fb7185", border: "1px solid rgba(190,18,60,0.5)",
                    padding: "0.2rem 0.7rem", cursor: "pointer", fontSize: "0.7rem", fontWeight: 800 }}>✕ Rechazar</button>
              </span>
            )}
          </div>
        ))}
        {esMaestro && (
          <button data-testid="descargar-cerebro-btn" onClick={() => window.open(`${API_URL}/api/dashai/dataset`, "_blank")}
            style={{ marginTop: 12, background: "transparent", color: ORO, border: "1px solid rgba(212,175,55,0.5)",
              padding: "0.4rem 1rem", cursor: "pointer", fontSize: "0.72rem", fontWeight: 800 }}>
            <i className="fa fa-download" style={{ marginRight: 6 }} />Descargar Cerebro a mi PC (dataset completo)
          </button>
        )}
      </div>

      {/* ══ HISTORIAL DE AUDITORÍA ══ */}
      <div style={{ marginTop: "1rem", background: "linear-gradient(160deg, rgba(18,18,20,0.97), rgba(6,6,8,0.99))",
        border: "1px solid rgba(212,175,55,0.3)", padding: "1rem 1.2rem" }} data-testid="auditoria-panel">
        <div style={{ fontWeight: 800, color: ORO, letterSpacing: "0.08em", marginBottom: "0.4rem" }}>
          📜 HISTORIAL DE AUDITORÍA DE LA BÓVEDA
        </div>
        {historial.length === 0 && <div style={{ fontSize: "0.75rem", opacity: 0.55 }}>Sin modificaciones registradas aún.</div>}
        {historial.map(h => (
          <div key={h.id} style={{ fontSize: "0.74rem", padding: "0.35rem 0", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
            <b style={{ color: "#F5E7B8" }}>{h.detalle}</b>
            {h.version ? <span style={{ opacity: 0.5 }}> · v1.{h.version}</span> : null}
            {(h.cambios || []).length > 0 && (
              <span style={{ opacity: 0.55 }}> · {h.cambios.slice(0, 3).map(c =>
                c.campo ? `${c.campo}: ${c.antes ?? "—"} → ${c.despues}` : String(c)).join(" · ")}
                {h.cambios.length > 3 ? ` (+${h.cambios.length - 3} más)` : ""}</span>
            )}
          </div>
        ))}
      </div>

      {modal && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)", zIndex: 1000,
          display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div data-testid="criterios-modal-clave" style={{ width: 380, background: "linear-gradient(160deg, #141416, #060608)",
            border: "1px solid rgba(212,175,55,0.5)", padding: "1.5rem", boxShadow: "0 0 60px -15px rgba(212,175,55,0.5)" }}>
            <div style={{ color: ORO, fontWeight: 800, letterSpacing: "0.1em", marginBottom: 6 }}>
              🔐 VALIDACIÓN DIGITAL — RENÉ OSA
            </div>
            <div style={{ fontSize: "0.75rem", opacity: 0.7, marginBottom: 12 }}>
              Ingrese su clave maestra para firmar el cambio. Quedará registrado: "Política modificada por René Osa el [fecha]". Clave incorrecta = cambios descartados + alerta.
            </div>
            <input data-testid="criterios-clave-input" type="password" value={clave} autoFocus
              onChange={e => setClave(e.target.value)} placeholder="Clave de René Osa"
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
