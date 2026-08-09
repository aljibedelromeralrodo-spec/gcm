import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

const ORO = "#D4AF37";
const ZAFIRO = "#2e5ce6";

const panel = {
  border: "1px solid rgba(212,175,55,0.35)",
  background: "linear-gradient(160deg, #0d0b06, #050505)",
  padding: "1.3rem 1.5rem",
  boxShadow: "0 0 36px -14px rgba(212,175,55,0.45), 0 0 60px -30px rgba(46,92,230,0.5)",
};

const Gauge = ({ pct }) => {
  const r = 70, c = 2 * Math.PI * r, off = c - (c * (pct || 0)) / 100;
  return (
    <div style={{ position: "relative", width: 180, height: 180 }} data-testid="dashai-gauge">
      <svg width="180" height="180" viewBox="0 0 180 180">
        <defs>
          <linearGradient id="gaugeGold" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#BF953F" /><stop offset="50%" stopColor="#FCF6BA" /><stop offset="100%" stopColor="#2e5ce6" />
          </linearGradient>
        </defs>
        <circle cx="90" cy="90" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="12" />
        <circle cx="90" cy="90" r={r} fill="none" stroke="url(#gaugeGold)" strokeWidth="12"
          strokeDasharray={c} strokeDashoffset={off} strokeLinecap="round"
          transform="rotate(-90 90 90)" style={{ filter: "drop-shadow(0 0 8px rgba(212,175,55,0.8))", transition: "stroke-dashoffset 1s ease" }} />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
        <div data-testid="dashai-gauge-valor" style={{ color: "#FCF6BA", fontSize: "2rem", fontWeight: 800, fontFamily: "'JetBrains Mono', monospace", textShadow: "0 0 14px rgba(212,175,55,0.6)" }}>{pct ?? "—"}%</div>
        <div style={{ color: "#9a8c52", fontSize: "0.55rem", letterSpacing: "0.22em", marginTop: 2 }}>CALIBRACIÓN</div>
      </div>
    </div>
  );
};

export default function CerebroDashAIModule() {
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const cargar = useCallback(async () => {
    try {
      const r = await axios.get(`${API_URL}/api/dashai/estado`);
      setD(r.data);
    } catch { setMsg("Error cargando el Cerebro DashAI"); }
  }, []);
  useEffect(() => { cargar(); const iv = setInterval(cargar, 60000); return () => clearInterval(iv); }, [cargar]);

  const sincronizar = async () => {
    setBusy(true);
    setMsg("🧠 Recalibrando criterios y sincronizando scores…");
    try {
      const r = await axios.post(`${API_URL}/api/dashai/sync`, {}, { timeout: 180000 });
      setMsg(`${r.data.mensaje} — ${r.data.prospectos_sync} prospectos y ${r.data.folders_sync} carpetas actualizados`);
      cargar();
    } catch (e) { setMsg("❌ " + (e?.response?.data?.detail || e.message)); }
    setBusy(false);
  };

  const fmt = (iso) => (iso || "").slice(0, 16).replace("T", " ");

  return (
    <div className="module-content" data-testid="dashai-module">
      <div style={{ display: "flex", alignItems: "baseline", gap: 14, marginBottom: "1.2rem", flexWrap: "wrap" }}>
        <h2 style={{ color: ORO, letterSpacing: "0.1em", margin: 0, textShadow: "0 0 18px rgba(212,175,55,0.55)" }}>🧠 CEREBRO DASHAI</h2>
        <span style={{ fontSize: "0.72rem", opacity: 0.55, textTransform: "uppercase", letterSpacing: "0.14em" }}>
          Aprendizaje Perpetuo · Sincronización Autónoma cada 60 minutos
        </span>
        <span data-testid="dashai-perpetuo-badge" style={{ marginLeft: "auto", fontSize: "0.68rem", fontWeight: 800, letterSpacing: "0.08em",
          color: "#8fd9b0", border: "1px solid rgba(16,217,142,0.4)", padding: "0.25rem 0.8rem",
          boxShadow: "0 0 14px -4px rgba(16,217,142,0.7)" }}>
          ● PERPETUO ACTIVO
        </span>
      </div>

      {msg && <div data-testid="dashai-msg" style={{ ...panel, padding: "0.7rem 1rem", fontSize: "0.82rem", color: "#F5E7B8", marginBottom: "1.1rem" }}>{msg}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "1.2rem", marginBottom: "1.2rem", alignItems: "stretch" }}>
        <div style={{ ...panel, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }} data-testid="dashai-panel-calibracion">
          <div style={{ color: ORO, fontSize: "0.7rem", letterSpacing: "0.2em", textTransform: "uppercase", marginBottom: 8 }}>Nivel de Calibración Actual</div>
          <Gauge pct={d?.nivel_calibracion} />
          <div style={{ color: "#6b6b6b", fontSize: "0.66rem", marginTop: 6 }}>Modelo calibrado: {fmt(d?.calibrado_en) || "—"}</div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "1.2rem" }}>
          <div style={{ ...panel, borderColor: "rgba(46,92,230,0.45)", boxShadow: "0 0 36px -14px rgba(46,92,230,0.6)" }} data-testid="dashai-panel-patron">
            <div style={{ color: "#7da2e8", fontSize: "0.7rem", letterSpacing: "0.18em", textTransform: "uppercase", marginBottom: 8 }}>💡 Último Patrón Aprendido</div>
            <div style={{ color: "#f8fafc", fontSize: "1rem", fontWeight: 700, lineHeight: 1.6 }}>
              {d?.ultimo_patron || "Aún sin patrones nuevos — el cerebro está vigilando cada correo de MESA y cada documento entrante."}
            </div>
            {d?.tendencia && <div style={{ color: "#9a8c52", fontSize: "0.76rem", marginTop: 8, fontStyle: "italic" }}>{d.tendencia}</div>}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "0.8rem" }}>
            {[
              { lbl: "Regla de Oro (60d)", val: d?.ventana_60?.base != null ? `${Math.round(d.ventana_60.base * 100)}%` : "—", color: ORO },
              { lbl: "Aprobadas 60d", val: d?.ventana_60?.aprobadas ?? "—", color: "#8fd9b0" },
              { lbl: "Rechazadas 60d", val: d?.ventana_60?.rechazadas ?? "—", color: "#fb7185" },
              { lbl: "Prospectos Sync", val: d?.prospectos_sync ?? 0, color: "#7da2e8" },
              { lbl: "Carpetas Sync", val: d?.folders_sync ?? 0, color: "#7da2e8" },
            ].map((s, i) => (
              <div key={i} data-testid={`dashai-stat-${i}`} style={{ background: "rgba(255,255,255,0.03)", border: `1px solid ${s.color}33`,
                padding: "0.7rem 0.9rem", textAlign: "center", boxShadow: `0 0 18px -10px ${s.color}` }}>
                <div style={{ fontSize: "1.4rem", fontWeight: 800, color: s.color, fontFamily: "'JetBrains Mono', monospace" }}>{s.val}</div>
                <div style={{ fontSize: "0.62rem", opacity: 0.7, textTransform: "uppercase", letterSpacing: "0.1em" }}>{s.lbl}</div>
              </div>
            ))}
          </div>

          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button data-testid="dashai-sync-btn" onClick={sincronizar} disabled={busy}
              style={{ background: "linear-gradient(135deg, #BF953F, #FCF6BA 45%, #B38728)", color: "#0a0a0a", border: "none",
                fontWeight: 800, fontSize: "0.76rem", letterSpacing: "0.08em", padding: "0.7rem 1.4rem", cursor: "pointer",
                opacity: busy ? 0.5 : 1, boxShadow: "0 0 22px -6px rgba(212,175,55,0.8)" }}>
              <i className={`fa ${busy ? "fa-cog fa-spin" : "fa-bolt"}`} style={{ marginRight: 6 }} />
              {busy ? "SINCRONIZANDO…" : "RECALIBRAR Y SINCRONIZAR AHORA"}
            </button>
            <div style={{ alignSelf: "center", color: "#6b6b6b", fontSize: "0.7rem" }}>
              Última sync: {fmt(d?.ultima_sync) || "pendiente"} {d?.ultimo_motivo ? `· ${d.ultimo_motivo}` : ""}
            </div>
          </div>
        </div>
      </div>

      {(d?.motivos_rechazo || []).length > 0 && (
        <div style={{ ...panel, marginBottom: "1.2rem" }} data-testid="dashai-motivos">
          <div style={{ color: ORO, fontSize: "0.7rem", letterSpacing: "0.18em", textTransform: "uppercase", marginBottom: 10 }}>Patrones de Rechazo Detectados (minería local)</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {d.motivos_rechazo.map((m, i) => (
              <span key={i} style={{ fontSize: "0.72rem", color: "#fda4af", border: "1px solid rgba(225,29,72,0.35)", padding: "0.25rem 0.7rem" }}>
                {m.motivo} · {m.casos} caso(s)
              </span>
            ))}
          </div>
          {(d.ajustes_mercado || []).map((a, i) => (
            <div key={i} style={{ fontSize: "0.75rem", color: "#F5E7B8", marginTop: 8, opacity: 0.85 }}>⚡ {a}</div>
          ))}
        </div>
      )}

      <div style={panel} data-testid="dashai-eventos">
        <div style={{ color: "#7da2e8", fontSize: "0.7rem", letterSpacing: "0.18em", textTransform: "uppercase", marginBottom: 10 }}>Bitácora de Aprendizaje Perpetuo</div>
        {(d?.eventos || []).length === 0 && (
          <div style={{ color: "#8a8a8a", fontSize: "0.78rem" }}>Sin eventos aún — la primera sincronización automática ocurre a los pocos minutos de encender el sistema.</div>
        )}
        {(d?.eventos || []).map((e, i) => (
          <div key={i} data-testid={`dashai-evento-${i}`} style={{ display: "flex", gap: 12, alignItems: "baseline", padding: "0.45rem 0",
            borderTop: "1px solid rgba(255,255,255,0.05)", fontSize: "0.76rem", flexWrap: "wrap" }}>
            <span style={{ color: "#6b6b6b", fontFamily: "monospace", fontSize: "0.68rem", whiteSpace: "nowrap" }}>{fmt(e.fecha)}</span>
            <span style={{ fontWeight: 800, fontSize: "0.62rem", letterSpacing: "0.06em", padding: "0.12rem 0.5rem", color: "#0a0a0a",
              background: e.motivo?.startsWith("disparo") ? "linear-gradient(135deg,#2e5ce6,#7da2e8)" : "linear-gradient(135deg,#BF953F,#FCF6BA)" }}>
              {e.motivo?.startsWith("disparo") ? "⚡ DISPARO" : e.motivo === "manual" ? "MANUAL" : "60 MIN"}
            </span>
            <span style={{ color: "#cbd5e1" }}>Calibración {e.nivel_calibracion}% · {e.prospectos_sync} prospectos · {e.folders_sync} carpetas</span>
            {e.patron && <span style={{ color: "#9a8c52", flexBasis: "100%", fontSize: "0.7rem", fontStyle: "italic" }}>{e.patron}</span>}
          </div>
        ))}
      </div>
    </div>
  );
}
