import { useState } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

const C = { bg: "#0f172a", card: "#1e293b", accent: "#d4af37", green: "#10b981", red: "#ef4444", text: "#e2e8f0", muted: "#94a3b8", border: "rgba(212,175,55,0.2)" };

const ESTADOS = {
  "en proceso": { color: "#f59e0b", icon: "fa-clock", label: "En Proceso" },
  "pre-aprobado": { color: "#10b981", icon: "fa-check-circle", label: "Pre-Aprobado" },
  "aprobado": { color: "#10b981", icon: "fa-check-double", label: "Aprobado" },
  "rechazado": { color: "#ef4444", icon: "fa-times-circle", label: "Rechazado" },
  "documentacion": { color: "#6366f1", icon: "fa-file-alt", label: "En Documentacion" },
  "escritura": { color: "#8b5cf6", icon: "fa-pen-fancy", label: "Escritura" },
  "tasacion": { color: "#f59e0b", icon: "fa-home", label: "Tasacion" },
  "cierre": { color: "#10b981", icon: "fa-flag-checkered", label: "Cierre" },
};

export default function PortalCliente() {
  const [rut, setRut] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const consultar = async () => {
    if (!rut || rut.length < 5) { setError("Ingrese un RUT valido"); return; }
    setLoading(true); setError(""); setData(null);
    try {
      const r = await axios.get(`${API_URL}/api/portal/consulta?rut=${encodeURIComponent(rut)}`);
      setData(r.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Error de conexion");
    }
    setLoading(false);
  };

  return (
    <div style={{ minHeight: "100vh", background: C.bg, fontFamily: "'Segoe UI', sans-serif", display: "flex", flexDirection: "column", alignItems: "center" }}>
      {/* Header */}
      <div style={{ width: "100%", padding: "1.5rem 2rem", borderBottom: `1px solid ${C.border}`, textAlign: "center" }}>
        <div style={{ fontSize: "1.8rem", fontWeight: 800, color: C.accent }}>Central Mutuos</div>
        <div style={{ fontSize: "0.9rem", color: C.muted, marginTop: "0.2rem" }}>Portal de Consulta - Estado de su Operacion</div>
      </div>

      {/* Search */}
      <div style={{ maxWidth: "520px", width: "90%", marginTop: "3rem" }}>
        <div style={{ padding: "2rem", borderRadius: "16px", background: C.card, border: `1px solid ${C.border}` }}>
          <div style={{ fontSize: "1rem", fontWeight: 600, color: C.text, marginBottom: "1rem" }}>
            <i className="fa fa-search" style={{ color: C.accent, marginRight: "0.5rem" }}></i>
            Consulte el estado de su credito
          </div>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <input data-testid="portal-rut-input" value={rut} onChange={e => setRut(e.target.value)} onKeyDown={e => e.key === "Enter" && consultar()}
              placeholder="Ingrese su RUT (ej: 12.345.678-9)"
              style={{ flex: 1, padding: "0.8rem 1rem", borderRadius: "10px", border: `1px solid ${C.border}`, background: "rgba(255,255,255,0.05)", color: C.text, fontSize: "1rem", outline: "none" }} />
            <button data-testid="portal-search-btn" onClick={consultar} disabled={loading}
              style={{ padding: "0.8rem 1.5rem", borderRadius: "10px", background: `linear-gradient(135deg, ${C.accent}, #b8860b)`, color: "#000", fontWeight: 700, fontSize: "0.9rem", border: "none", cursor: "pointer" }}>
              {loading ? <i className="fa fa-spinner fa-spin"></i> : "Consultar"}
            </button>
          </div>
          {error && <div data-testid="portal-error" style={{ color: C.red, fontSize: "0.85rem", marginTop: "0.5rem" }}>{error}</div>}
        </div>

        {/* No results */}
        {data && !data.found && (
          <div data-testid="portal-not-found" style={{ marginTop: "1.5rem", padding: "2rem", borderRadius: "16px", background: C.card, border: `1px solid ${C.border}`, textAlign: "center" }}>
            <i className="fa fa-info-circle" style={{ fontSize: "2rem", color: C.muted, marginBottom: "0.5rem", display: "block" }}></i>
            <div style={{ color: C.text, fontWeight: 600 }}>No se encontraron operaciones</div>
            <div style={{ color: C.muted, fontSize: "0.85rem", marginTop: "0.3rem" }}>para el RUT {data.rut}</div>
          </div>
        )}

        {/* Results */}
        {data && data.found && (
          <div data-testid="portal-results" style={{ marginTop: "1.5rem" }}>
            {/* Operations */}
            {data.operaciones?.length > 0 && data.operaciones.map((op, i) => {
              const est = ESTADOS[op.estado?.toLowerCase()] || ESTADOS["en proceso"];
              return (
                <div key={i} data-testid={`portal-op-${i}`} style={{ marginBottom: "1rem", padding: "1.25rem", borderRadius: "14px", background: C.card, border: `1px solid ${C.border}` }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.75rem" }}>
                    <div style={{ fontWeight: 700, color: C.text, fontSize: "1rem" }}>{op.cliente_display || op.id}</div>
                    <span style={{ padding: "0.3rem 0.8rem", borderRadius: "8px", background: `${est.color}20`, color: est.color, fontWeight: 700, fontSize: "0.8rem" }}>
                      <i className={`fa ${est.icon}`} style={{ marginRight: "0.3rem" }}></i>{est.label}
                    </span>
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
                    <InfoRow label="Proyecto" value={op.proyecto || "-"} />
                    <InfoRow label="Ejecutivo" value={op.ejecutivo_cm || "-"} />
                    <InfoRow label="Correos procesados" value={op.total_correos || 0} />
                    <InfoRow label="Ultima actualizacion" value={op.ultimo_correo ? new Date(op.ultimo_correo).toLocaleDateString("es-CL") : "-"} />
                  </div>
                  {op.resumen && (
                    <div style={{ marginTop: "0.75rem", padding: "0.6rem", borderRadius: "8px", background: "rgba(255,255,255,0.03)", fontSize: "0.8rem", color: C.muted, lineHeight: 1.5 }}>
                      <i className="fa fa-comment" style={{ marginRight: "0.3rem", color: C.accent }}></i>{op.resumen}
                    </div>
                  )}

                  {/* Progress bar */}
                  <div style={{ marginTop: "0.75rem" }}>
                    <ProgressSteps estado={op.estado?.toLowerCase()} />
                  </div>
                </div>
              );
            })}

            {/* Simulations */}
            {data.simulaciones?.length > 0 && (
              <div style={{ marginTop: "0.5rem", padding: "1rem", borderRadius: "14px", background: C.card, border: `1px solid ${C.border}` }}>
                <div style={{ fontWeight: 600, color: C.text, fontSize: "0.9rem", marginBottom: "0.75rem" }}>
                  <i className="fa fa-calculator" style={{ color: C.accent, marginRight: "0.4rem" }}></i>Simulaciones
                </div>
                {data.simulaciones.map((s, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.5rem 0", borderBottom: i < data.simulaciones.length - 1 ? `1px solid ${C.border}` : "none" }}>
                    <span style={{ padding: "2px 8px", borderRadius: "6px", fontSize: "0.75rem", fontWeight: 700, background: s.precalificacion_aprobada ? `${C.green}20` : `${C.red}20`, color: s.precalificacion_aprobada ? C.green : C.red }}>
                      {s.precalificacion_aprobada ? "APROBADO" : "RECHAZADO"}
                    </span>
                    <div style={{ flex: 1, fontSize: "0.82rem", color: C.text }}>{s.nombre_completo}</div>
                    <div style={{ fontSize: "0.78rem", color: C.accent, fontWeight: 600 }}>{(s.capacidad_credito_uf || 0).toFixed(0)} UF</div>
                    <div style={{ fontSize: "0.72rem", color: C.muted }}>{s.timestamp ? new Date(s.timestamp).toLocaleDateString("es-CL") : ""}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <div style={{ marginTop: "auto", padding: "1.5rem", textAlign: "center", color: C.muted, fontSize: "0.75rem" }}>
        Central Mutuos - Informacion confidencial
      </div>
    </div>
  );
}

function InfoRow({ label, value }) {
  return (
    <div>
      <div style={{ fontSize: "0.7rem", color: C.muted }}>{label}</div>
      <div style={{ fontSize: "0.85rem", color: C.text, fontWeight: 500 }}>{value}</div>
    </div>
  );
}

function ProgressSteps({ estado }) {
  const steps = ["en proceso", "documentacion", "tasacion", "escritura", "aprobado"];
  const labels = ["Inicio", "Docs", "Tasacion", "Escritura", "Aprobado"];
  const current = steps.indexOf(estado || "en proceso");
  const rejected = estado === "rechazado";

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "0" }}>
      {steps.map((s, i) => {
        const done = !rejected && i <= current;
        const clr = rejected ? C.red : (done ? C.green : "rgba(255,255,255,0.1)");
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", flex: 1 }}>
            <div style={{ width: "22px", height: "22px", borderRadius: "50%", background: clr, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.6rem", color: done ? "#fff" : C.muted, fontWeight: 700, flexShrink: 0 }}>
              {rejected && i === 0 ? <i className="fa fa-times"></i> : (done ? <i className="fa fa-check"></i> : (i + 1))}
            </div>
            {i < steps.length - 1 && <div style={{ flex: 1, height: "2px", background: done && i < current ? C.green : "rgba(255,255,255,0.1)" }}></div>}
          </div>
        );
      })}
      <div style={{ display: "flex", justifyContent: "space-between", position: "absolute", left: 0, right: 0, bottom: "-14px" }}>
      </div>
    </div>
  );
}
