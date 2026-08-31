import { useState, useEffect } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

export const vipCard = {
  background: "rgba(12,12,14,0.92)", backdropFilter: "blur(18px)", WebkitBackdropFilter: "blur(18px)",
  padding: "1.6rem", borderRadius: 0, border: "1px solid transparent",
  backgroundImage: "linear-gradient(115deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.02) 18%, transparent 32%), linear-gradient(160deg, rgba(24,24,26,0.96), rgba(8,8,9,0.99)), linear-gradient(135deg, #BF953F, #FCF6BA, #B38728, #FBF5B7, #AA771C)",
  backgroundOrigin: "border-box", backgroundClip: "padding-box, padding-box, border-box",
  boxShadow: "0 35px 70px -20px rgba(0,0,0,0.95), 0 0 38px -16px rgba(191,149,63,0.45)",
  fontFamily: "'Inter', sans-serif",
};

export const vipTitle = { fontFamily: "'Inter', sans-serif", fontWeight: 800, fontSize: "1.35rem", letterSpacing: "0.5px", color: "#fff", margin: 0 };
export const vipGoldBtn = {
  background: "linear-gradient(135deg, #BF953F 0%, #FCF6BA 30%, #B38728 55%, #FBF5B7 80%, #AA771C 100%)",
  color: "#0a0a0a", fontWeight: 800, border: "none", borderRadius: 0, padding: "0.7rem 1.4rem",
  cursor: "pointer", fontSize: "0.95rem", letterSpacing: "0.5px", fontFamily: "'Inter', sans-serif",
  boxShadow: "0 8px 24px -8px rgba(191,149,63,0.7)",
};

export const Semaforo = ({ ok, label, testId }) => (
  <span data-testid={testId} title={ok ? "Dato verificado" : "Falta revisar"} style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: "0.78rem", fontWeight: 600, color: ok ? "#10d98e" : "#f59e0b", marginRight: "1rem" }}>
    <span style={{ width: 9, height: 9, borderRadius: "50%", background: ok ? "#10d98e" : "#f59e0b", boxShadow: `0 0 8px ${ok ? "#10d98e" : "#f59e0b"}` }} />
    {label}
  </span>
);

export const FechaFmt = (iso) => (iso ? String(iso).slice(0, 16).replace("T", " ") : "—");

export function useCarpetasVIP(endpoint) {
  const [carpetas, setCarpetas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/${endpoint}`);
      setCarpetas(r.data.carpetas || []);
      setError("");
    } catch (e) { setError(e.response?.data?.detail || e.message); }
    setLoading(false);
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, []);
  return { carpetas, loading, error, reload: load };
}

export const VipHeader = ({ icon, titulo, sub, total, testId }) => (
  <div data-testid={testId} style={{ marginBottom: "2rem" }}>
    <h2 style={{ ...vipTitle, fontSize: "1.8rem", color: "#d4af37" }}>
      <i className={`fa ${icon}`} style={{ marginRight: "0.7rem" }} />{titulo}
      {total !== undefined && <span style={{ fontSize: "1rem", opacity: 0.55, marginLeft: "0.8rem", color: "#fff" }}>{total} ficha(s)</span>}
    </h2>
    <p style={{ fontFamily: "'Inter', sans-serif", fontSize: "0.9rem", opacity: 0.55, color: "#fff", margin: "0.4rem 0 0" }}>{sub}</p>
  </div>
);

export const VipVacio = ({ texto, testId }) => (
  <div data-testid={testId} style={{ ...vipCard, textAlign: "center", padding: "3rem", color: "#fff", opacity: 0.6, fontSize: "1rem" }}>{texto}</div>
);

export default function TasacionModule() {
  const { carpetas, loading, error, reload } = useCarpetasVIP("tasacion/carpetas");
  const [visitas, setVisitas] = useState({});
  const [prefill, setPrefill] = useState(null);
  useEffect(() => {
    axios.get(`${API}/api/flujos/contactos-visita`).then(r => setVisitas(r.data.contactos || {})).catch(() => {});
  }, []);
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem("cm_prefill_cliente");
      if (!raw) return;
      sessionStorage.removeItem("cm_prefill_cliente");
      setPrefill(JSON.parse(raw));
    } catch { /* */ }
  }, []);
  return (
    <div style={{ padding: "2rem", maxWidth: "1100px" }} data-testid="tasacion-module">
      <VipHeader icon="fa-home" titulo="Tasación" sub="Fichas leídas directo desde MongoDB · carga instantánea, sin dependencia del disco" total={carpetas.length} testId="tasacion-header" />
      <button onClick={reload} data-testid="tasacion-reload" style={{ ...vipGoldBtn, marginBottom: "1.5rem", padding: "0.5rem 1rem", fontSize: "0.82rem" }}>
        <i className="fa fa-refresh" style={{ marginRight: 6 }} />Actualizar
      </button>
      {prefill?.nombre && (
        <div style={{ ...vipCard, marginBottom: "1rem", color: "#fff" }}>
          Pro Flujo: {prefill.nombre}. Si aún no hay tasación, volvé al tablero y usá «Solicitar tasación».
        </div>
      )}
      {error && <div style={{ color: "#ff6b8a", marginBottom: "1rem", fontWeight: 600 }}>⚠ {error}</div>}
      {loading ? <VipVacio texto="Cargando fichas…" testId="tasacion-loading" /> :
        carpetas.length === 0 ? <VipVacio texto="No hay tasaciones solicitadas todavía." testId="tasacion-vacio" /> :
        carpetas.map((c, i) => (
          <div key={c.id} data-testid={`tasacion-ficha-${i}`} style={{ ...vipCard, marginBottom: "1.4rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem" }}>
              <div>
                <h3 style={vipTitle}>{c.nombre}</h3>
                <div style={{ color: "#d4af37", fontWeight: 700, fontSize: "1rem", marginTop: 4, letterSpacing: "1px" }}>{c.rut || "RUT pendiente"}</div>
              </div>
              <span style={{ fontSize: "0.75rem", fontWeight: 700, padding: "0.35rem 0.8rem", letterSpacing: "1px", background: c.terminado_at ? "rgba(16,217,142,0.15)" : "rgba(212,175,55,0.15)", color: c.terminado_at ? "#10d98e" : "#d4af37", border: `1px solid ${c.terminado_at ? "rgba(16,217,142,0.4)" : "rgba(212,175,55,0.4)"}` }}>
                {c.terminado_at ? "✓ TERMINADA" : "EN CURSO"}
              </span>
            </div>
            <div style={{ marginTop: "1.1rem", paddingTop: "1rem", borderTop: "1px solid rgba(212,175,55,0.15)" }}>
              <div style={{ fontSize: "0.72rem", letterSpacing: "1.5px", opacity: 0.5, color: "#fff", marginBottom: "0.6rem" }}>SEMÁFORO DE CONFIANZA (DATOS IA)</div>
              <Semaforo ok={!!c.rut} label="RUT verificado" testId={`tasacion-sem-rut-${i}`} />
              <Semaforo ok={!!c.solicitada_at} label={`Solicitada ${FechaFmt(c.solicitada_at)}`} testId={`tasacion-sem-sol-${i}`} />
              <Semaforo ok={!!c.terminado_at} label={c.terminado_at ? `Terminada ${FechaFmt(c.terminado_at)}` : "Sin respuesta aún"} testId={`tasacion-sem-fin-${i}`} />
              <Semaforo ok={!!c.pdf_disponible} label={c.pdf_disponible ? "PDF disponible" : "PDF no disponible (solo alerta)"} testId={`tasacion-sem-pdf-${i}`} />
            </div>
            {visitas[c.id] && (
              <div data-testid={`tasacion-contacto-visita-${i}`} style={{ marginTop: "0.9rem", padding: "0.7rem 0.9rem", border: "1px solid rgba(212,175,55,0.35)", background: "rgba(212,175,55,0.06)" }}>
                <div style={{ fontSize: "0.68rem", letterSpacing: "1.5px", color: "#d4af37", fontWeight: 800, marginBottom: 4 }}>
                  CONTACTO DE VISITA · {visitas[c.id].tipo} ({visitas[c.id].origen})
                </div>
                <div style={{ color: "#fff", fontSize: "0.8rem" }}>
                  {visitas[c.id].nombre || "Sin nombre"} · {visitas[c.id].email || "sin correo"} · {visitas[c.id].telefono || "sin teléfono"}
                </div>
                <div style={{ color: "#94a3b8", fontSize: "0.62rem", marginTop: 3 }}>
                  {visitas[c.id].tipo === "USADA" ? "Auto-completado con el Vendedor de la usada (Regla #37)" : "Encargado del proyecto para coordinar con Value Property"}
                </div>
              </div>
            )}
          </div>
        ))}
    </div>
  );
}
