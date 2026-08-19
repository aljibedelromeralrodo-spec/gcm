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

const CatalogoMaestro = () => {
  const [cat, setCat] = useState(null);
  const [abierto, setAbierto] = useState({});
  useEffect(() => {
    axios.get(`${API_URL}/api/dashai/catalogo-maestro`).then(r => setCat(r.data)).catch(() => {});
  }, []);
  if (!cat) return null;
  return (
    <div data-testid="catalogo-maestro" style={{ background: "rgba(15,23,42,0.6)",
      border: "1px solid rgba(212,175,55,0.4)", borderRadius: 14, padding: "1.2rem 1.6rem", marginBottom: "1.1rem" }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
        <h3 style={{ color: "#d4af37", fontSize: "1rem", margin: 0, letterSpacing: 1 }}>
          📜 CONSTITUCIÓN OFICIAL DEL SISTEMA — {cat.total_reglas} REGLAS ARCHIVADAS</h3>
        <span style={{ color: "#4ade80", fontSize: "0.62rem", fontWeight: 800 }}>● INAMOVIBLE E INVIOLABLE</span>
        <span style={{ color: "#64748b", fontSize: "0.64rem" }}>
          Constitución v{cat.version_constitucion} · {cat.resumen.reglas_oro} Reglas de Oro ·
          {" "}{cat.resumen.reglas_eficiencia} Eficiencia · {cat.resumen.normativas_maestras} Normativas ·
          {" "}{cat.resumen.reglas_operativas} Operativas · {cat.resumen.reglas_inviolables} Inviolables</span>
      </div>
      {cat.categorias.map(g => (
        <div key={g.clave} style={{ marginTop: 10 }}>
          <button data-testid={`catalogo-cat-${g.clave}`} onClick={() => setAbierto(a => ({ ...a, [g.clave]: !a[g.clave] }))}
            style={{ width: "100%", textAlign: "left", background: "rgba(2,6,23,0.5)", color: "#FCF6BA",
              border: "1px solid rgba(212,175,55,0.25)", borderRadius: 9, padding: "0.55rem 0.9rem",
              cursor: "pointer", fontWeight: 800, fontSize: "0.76rem", letterSpacing: 0.6 }}>
            {abierto[g.clave] ? "▾" : "▸"} {g.nombre} — {g.total} reglas</button>
          {abierto[g.clave] && g.reglas.map(r => (
            <div key={r.num} style={{ borderLeft: "2px solid rgba(212,175,55,0.35)", margin: "6px 0 6px 10px",
              padding: "4px 10px", fontSize: "0.7rem" }}>
              <b style={{ color: "#d4af37" }}>{r.num}</b>
              <b style={{ color: "#f8fafc" }}> · {r.titulo}</b>
              <span style={{ color: "#4ade80", fontSize: "0.6rem", marginLeft: 6 }}>● {r.estado}</span>
              <div style={{ color: "#94a3b8", marginTop: 2 }}>{r.descripcion}</div>
              <div style={{ color: "#475569", fontSize: "0.6rem", marginTop: 2 }}>
                Módulo: {r.modulo} · Fuente: {r.fuente}</div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
};

const EstadoCerebro = () => {
  const [ec, setEc] = useState(null);
  const [aud, setAud] = useState(null);
  const [audAbierta, setAudAbierta] = useState(false);
  const [audBusy, setAudBusy] = useState(false);
  const cargarAud = () => axios.get(`${API_URL}/api/auditoria-eficiencia`).then(r => setAud(r.data)).catch(() => {});
  useEffect(() => {
    axios.get(`${API_URL}/api/dashai/estado-cerebro`).then(r => setEc(r.data)).catch(() => {});
    cargarAud();
  }, []);
  if (!ec) return null;
  const fdd = (iso) => (iso ? `${String(iso).slice(8, 10)}/${String(iso).slice(5, 7)}/${String(iso).slice(0, 4)} ${String(iso).slice(11, 16)}` : "—");
  const celda = { background: "rgba(15,23,42,0.6)", border: "1px solid rgba(212,175,55,0.3)", borderRadius: 10, padding: "0.8rem 1rem", flex: "1 1 200px" };
  return (
    <div data-testid="estado-cerebro" style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: "1.1rem" }}>
      <div style={celda}>
        <div style={{ color: "#94a3b8", fontSize: "0.64rem", fontWeight: 800, letterSpacing: 1 }}>NORMATIVAS ACTIVAS</div>
        <div data-testid="ec-normativas" style={{ color: "#d4af37", fontSize: "1.6rem", fontWeight: 900 }}>{ec.normativas_activas}</div>
      </div>
      <div style={celda}>
        <div style={{ color: "#94a3b8", fontSize: "0.64rem", fontWeight: 800, letterSpacing: 1 }}>ÚLTIMA MODIFICACIÓN</div>
        <div style={{ color: "#f8fafc", fontSize: "0.82rem", fontWeight: 700, marginTop: 6 }}>
          {ec.ultima_modificacion ? `${fdd(ec.ultima_modificacion)} · ${ec.modificada_por}` : "Sin modificaciones desde la siembra"}</div>
      </div>
      <div style={celda}>
        <div style={{ color: "#94a3b8", fontSize: "0.64rem", fontWeight: 800, letterSpacing: 1 }}>ÚLTIMA VALIDACIÓN</div>
        <div style={{ color: "#f8fafc", fontSize: "0.82rem", fontWeight: 700, marginTop: 6 }}>{fdd(ec.ultima_validacion)}</div>
        <div style={{ color: "#8fd9b0", fontSize: "0.7rem", marginTop: 2 }}>{ec.resultado_validacion}</div>
      </div>
      <a href="/manual-marca-central-mutuos.pdf" target="_blank" rel="noreferrer" data-testid="btn-manual-marca"
        style={{ ...celda, flex: "0 1 190px", textDecoration: "none", display: "flex", flexDirection: "column",
          justifyContent: "center", cursor: "pointer" }}>
        <div style={{ color: "#d4af37", fontSize: "1.3rem" }}>📘</div>
        <div style={{ color: "#d4af37", fontSize: "0.72rem", fontWeight: 900, letterSpacing: 0.8 }}>MANUAL DE MARCA</div>
        <div style={{ color: "#94a3b8", fontSize: "0.6rem" }}>Descargar PDF oficial v1.0</div>
      </a>
      {aud && (
        <div data-testid="panel-auditoria-eficiencia" style={{ ...celda, flex: "1 1 100%" }}>
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <div style={{ color: "#94a3b8", fontSize: "0.64rem", fontWeight: 800, letterSpacing: 1 }}>
              🔍 AUDITORÍA SEMANAL DE EFICIENCIA — regla permanente (lunes, primer ingreso del Admin)</div>
            <span style={{ color: aud.activa ? "#4ade80" : "#f87171", fontSize: "0.66rem", fontWeight: 800 }}>
              {aud.activa ? "● ACTIVA" : "● DESACTIVADA"}</span>
            <button data-testid="auditoria-ejecutar" disabled={audBusy} onClick={async () => {
              setAudBusy(true);
              try { await axios.post(`${API_URL}/api/auditoria-eficiencia/ejecutar`, {}); cargarAud(); } catch { /* noop */ }
              setAudBusy(false);
            }} style={{ marginLeft: "auto", background: "rgba(212,175,55,0.12)", color: "#d4af37",
              border: "1px solid rgba(212,175,55,0.5)", borderRadius: 7, padding: "0.3rem 0.8rem",
              cursor: "pointer", fontSize: "0.64rem", fontWeight: 800 }}>
              {audBusy ? "Auditando…" : "▶ Ejecutar ahora"}</button>
            <button data-testid="auditoria-historial-toggle" onClick={() => setAudAbierta(a => !a)}
              style={{ background: "none", color: "#94a3b8", border: "1px solid rgba(148,163,184,0.4)",
                borderRadius: 7, padding: "0.3rem 0.8rem", cursor: "pointer", fontSize: "0.64rem", fontWeight: 800 }}>
              {audAbierta ? "Ocultar historial" : `Historial (${aud.total})`}</button>
          </div>
          {(aud.historial || [])[0] && (
            <div style={{ color: "#e2e8f0", fontSize: "0.7rem", marginTop: 6 }}>
              Última: <b style={{ color: aud.historial[0].resultado === "aprobada" ? "#4ade80" : "#facc15" }}>
                {aud.historial[0].resultado === "aprobada" ? "✅ APROBADA" : `⚠️ ${aud.historial[0].fallas} hallazgo(s)`}</b>
              {" · "}{fdd(aud.historial[0].fecha)} · semana {aud.historial[0].semana} · {aud.historial[0].trigger}
            </div>
          )}
          {audAbierta && (aud.historial || []).map(h => (
            <div key={h.id} data-testid={`auditoria-reg-${h.id}`} style={{ borderTop: "1px solid rgba(148,163,184,0.15)",
              marginTop: 6, paddingTop: 6, fontSize: "0.66rem", color: "#cbd5e1" }}>
              <b style={{ color: h.resultado === "aprobada" ? "#4ade80" : "#facc15" }}>
                {h.resultado === "aprobada" ? "✅" : "⚠️"} {h.semana}</b> · {fdd(h.fecha)} · {h.trigger}
              <div style={{ marginTop: 3, display: "flex", flexWrap: "wrap", gap: 4 }}>
                {(h.checks || []).map(cq => (
                  <span key={cq.clave} title={cq.detalle} style={{ background: cq.ok ? "rgba(74,222,128,0.1)" : "rgba(248,113,113,0.12)",
                    color: cq.ok ? "#4ade80" : "#f87171", borderRadius: 6, padding: "0.05rem 0.4rem", fontSize: "0.58rem" }}>
                    {cq.ok ? "✓" : "✗"} {cq.clave}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default function CerebroDashAIModule() {
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [dataset, setDataset] = useState(null);
  const [busyDs, setBusyDs] = useState(false);
  const [destMaestro, setDestMaestro] = useState("");
  const [destMsg, setDestMsg] = useState("");
  const [buzon, setBuzon] = useState(null);
  const [buzonForm, setBuzonForm] = useState({ email: "", app_password: "", imap_host: "imap.gmail.com" });
  const [buzonMsg, setBuzonMsg] = useState("");

  useEffect(() => {
    axios.get(`${API_URL}/api/buzon-aprendizaje`).then(r => setBuzon(r.data)).catch(() => {});
  }, []);

  const guardarBuzon = async () => {
    setBuzonMsg("");
    try {
      const r = await axios.post(`${API_URL}/api/buzon-aprendizaje/configurar`, buzonForm);
      setBuzonMsg(`✅ ${r.data.nota}`);
      setBuzonForm({ ...buzonForm, app_password: "" });
      axios.get(`${API_URL}/api/buzon-aprendizaje`).then(x => setBuzon(x.data)).catch(() => {});
    } catch (e) { setBuzonMsg(`${e.response?.data?.detail || "⛔ Error"}`); }
  };

  useEffect(() => {
    axios.get(`${API_URL}/api/control/config`).then(r => setDestMaestro(r.data.destinatario_maestro || "")).catch(() => {});
  }, []);

  const guardarDestMaestro = async () => {
    setDestMsg("");
    try {
      await axios.post(`${API_URL}/api/control/config`, { destinatario_maestro: destMaestro });
      setDestMsg("✅ Destinatario Maestro guardado — los informes de inconsistencia irán a esa dirección");
    } catch (e) { setDestMsg(`⛔ ${e.response?.data?.detail || "Error"}`); }
  };

  useEffect(() => {
    axios.get(`${API_URL}/api/dashai/dataset/status`).then(r => setDataset(r.data)).catch(() => {});
  }, []);

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

      <EstadoCerebro />
      <CatalogoMaestro />

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

      {(d?.reglas_estilo || []).length > 0 && (
        <div style={{ ...panel, marginBottom: "1.2rem", borderColor: "rgba(212,175,55,0.55)" }} data-testid="dashai-reglas-estilo">
          <div style={{ color: ORO, fontSize: "0.7rem", letterSpacing: "0.18em", textTransform: "uppercase", marginBottom: 10 }}>⚖️ Constitución DashAI · Ley de Jerarquía Suprema</div>
          <div data-testid="dashai-constitucion" style={{ display: "flex", gap: 12, alignItems: "baseline", fontSize: "0.8rem", padding: "0.4rem 0", borderBottom: "1px solid rgba(255,255,255,0.06)", marginBottom: 6 }}>
            <span style={{ fontWeight: 800, color: "#0a0a0a", background: "linear-gradient(135deg,#e11d48,#fb7185)", padding: "0.15rem 0.6rem", fontSize: "0.66rem", whiteSpace: "nowrap" }}>LEY MADRE · CLAVE 0586</span>
            <span style={{ color: "#e2e8f0", lineHeight: 1.65 }}>DashAI (Bóveda de Criterios) es la ÚNICA fuente de verdad: viabilidad, forense, Set de Crédito y Simulador consultan sus parámetros antes de cada decisión. Sin conexión a la Constitución, las decisiones se bloquean.</span>
          </div>
          <div style={{ color: ORO, fontSize: "0.68rem", letterSpacing: "0.14em", textTransform: "uppercase", margin: "8px 0 4px" }}>📐 Reglas de Estilo Inamovibles</div>
          {d.reglas_estilo.map((r, i) => (
            <div key={i} data-testid={`dashai-regla-${r.n}`} style={{ display: "flex", gap: 12, alignItems: "baseline", fontSize: "0.8rem", padding: "0.4rem 0" }}>
              <span style={{ fontWeight: 800, color: "#0a0a0a", background: "linear-gradient(135deg,#BF953F,#FCF6BA)", padding: "0.15rem 0.6rem", fontSize: "0.66rem", whiteSpace: "nowrap" }}>REGLA #{r.n}{r.inamovible ? " · INAMOVIBLE" : ""}</span>
              <span style={{ color: "#e2e8f0", lineHeight: 1.65 }}>{r.regla}</span>
            </div>
          ))}
        </div>
      )}

      <div style={{ ...panel, marginBottom: "1.2rem", borderColor: "rgba(245,158,11,0.5)" }} data-testid="dashai-control-config">
        <div style={{ color: ORO, fontSize: "0.7rem", letterSpacing: "0.18em", textTransform: "uppercase", marginBottom: 10 }}>
          🔎 Módulo Control — Destinatario Maestro de Inconsistencias (Regla #35)
        </div>
        <p style={{ color: "#94a3b8", fontSize: "0.72rem", margin: "0 0 10px", lineHeight: 1.6 }}>
          Correo que recibe los informes de discrepancia entre la Bodega y el Ingreso de Concreces (ej. Riesgo Concreces).
          El hallazgo NUNCA bloquea la operación: el Módulo Control solo audita e informa.
        </p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input data-testid="dashai-dest-maestro" placeholder="riesgo@concreces.cl" value={destMaestro}
            onChange={e => setDestMaestro(e.target.value)}
            style={{ flex: "1 1 260px", background: "rgba(255,255,255,0.06)", border: "1px solid rgba(245,158,11,0.4)", color: "#fff", padding: "0.5rem 0.7rem", borderRadius: 8, fontSize: "0.78rem", boxSizing: "border-box" }} />
          <button data-testid="dashai-dest-guardar" onClick={guardarDestMaestro}
            style={{ background: "linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C)", color: "#0a0a0a", border: "none", borderRadius: 8, padding: "0.5rem 1rem", fontWeight: 800, cursor: "pointer", fontSize: "0.74rem" }}>
            Guardar Destinatario
          </button>
        </div>
        {destMsg && <p data-testid="dashai-dest-msg" style={{ color: destMsg.startsWith("✅") ? "#22c55e" : "#ef4444", fontSize: "0.7rem", marginTop: 8 }}>{destMsg}</p>}
      </div>

      <div style={{ ...panel, marginBottom: "1.2rem", borderColor: "rgba(56,189,248,0.5)" }} data-testid="dashai-buzon-aprendizaje">
        <div style={{ color: ORO, fontSize: "0.7rem", letterSpacing: "0.18em", textTransform: "uppercase", marginBottom: 10 }}>
          📚 Buzón de Aprendizaje — 2º IMAP solo lectura
        </div>
        <p style={{ color: "#94a3b8", fontSize: "0.72rem", margin: "0 0 10px", lineHeight: 1.6 }}>
          DashAI lee este buzón SIN marcar ni mover correos y aprende de asuntos reales (tasaciones, estudios, reparos, notarías).
          {buzon?.configurado && <> · <b style={{ color: buzon.estado === "ok" ? "#22c55e" : "#f59e0b" }}>{buzon.email}</b> — {buzon.ingeridos} correo(s) ingeridos · última lectura {(buzon.ultima_lectura || "—").slice(0, 16).replace("T", " ")}</>}
        </p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input data-testid="buzon-email" placeholder="segundo.buzon@gmail.com" value={buzonForm.email}
            onChange={e => setBuzonForm({ ...buzonForm, email: e.target.value })}
            style={{ flex: "1 1 200px", background: "rgba(255,255,255,0.06)", border: "1px solid rgba(56,189,248,0.4)", color: "#fff", padding: "0.5rem 0.7rem", borderRadius: 8, fontSize: "0.76rem", boxSizing: "border-box" }} />
          <input data-testid="buzon-password" type="password" placeholder="Clave de aplicación" value={buzonForm.app_password}
            onChange={e => setBuzonForm({ ...buzonForm, app_password: e.target.value })}
            style={{ flex: "1 1 170px", background: "rgba(255,255,255,0.06)", border: "1px solid rgba(56,189,248,0.4)", color: "#fff", padding: "0.5rem 0.7rem", borderRadius: 8, fontSize: "0.76rem", boxSizing: "border-box" }} />
          <input data-testid="buzon-imap" value={buzonForm.imap_host}
            onChange={e => setBuzonForm({ ...buzonForm, imap_host: e.target.value })}
            style={{ flex: "0 1 150px", background: "rgba(255,255,255,0.06)", border: "1px solid rgba(56,189,248,0.4)", color: "#fff", padding: "0.5rem 0.7rem", borderRadius: 8, fontSize: "0.76rem", boxSizing: "border-box" }} />
          <button data-testid="buzon-guardar" onClick={guardarBuzon} disabled={!buzonForm.email || !buzonForm.app_password}
            style={{ background: "linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C)", color: "#0a0a0a", border: "none", borderRadius: 8, padding: "0.5rem 1rem", fontWeight: 800, cursor: "pointer", fontSize: "0.74rem" }}>
            Conectar (solo lectura)
          </button>
        </div>
        {buzonMsg && <p data-testid="buzon-msg" style={{ color: buzonMsg.startsWith("✅") ? "#22c55e" : "#f59e0b", fontSize: "0.7rem", marginTop: 8 }}>{buzonMsg}</p>}
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

      <div style={{ ...panel, marginBottom: "1.2rem", borderColor: "rgba(14,165,233,0.4)" }} data-testid="dashai-boveda-dataset">
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 240 }}>
            <div style={{ color: "#a5f3fc", fontSize: "0.7rem", letterSpacing: "0.18em", textTransform: "uppercase" }}>📊 Bóveda de DashAI · Dataset Comercial</div>
            <div style={{ color: "#9a8c52", fontSize: "0.72rem", marginTop: 4 }}>
              Auto-exportación diaria 23:59 · RUT hasheado como llave única · 100% anonimizado · MESA + finanzas + forense
            </div>
            <div data-testid="dashai-dataset-status" style={{ color: "#cbd5e1", fontSize: "0.74rem", marginTop: 6 }}>
              {dataset?.generado_en
                ? <>✓ Última exportación: {(dataset.generado_en || "").slice(0, 16).replace("T", " ")} · {dataset.total} casos · {dataset.nuevos_ultimo} nuevos</>
                : "Aún sin exportaciones — la primera se genera hoy a las 23:59 o al presionar EXPORTAR AHORA."}
            </div>
          </div>
          <button data-testid="dashai-dataset-exportar-btn" disabled={busyDs}
            onClick={async () => {
              setBusyDs(true);
              try {
                const r = await axios.post(`${API_URL}/api/dashai/dataset/exportar-ahora`, {}, { timeout: 180000 });
                setDataset(d0 => ({ ...(d0 || {}), ...r.data, nuevos_ultimo: r.data.nuevos }));
                setMsg(`📊 Dataset DashAI actualizado con ${r.data.nuevos} nuevos casos (${r.data.total} totales)`);
              } catch (e) { setMsg("❌ " + (e?.response?.data?.detail || e.message)); }
              setBusyDs(false);
            }}
            style={{ background: "rgba(14,165,233,0.15)", color: "#a5f3fc", border: "1px solid rgba(14,165,233,0.45)",
              fontWeight: 800, fontSize: "0.7rem", letterSpacing: "0.08em", padding: "0.6rem 1.1rem", cursor: "pointer" }}>
            {busyDs ? "EXPORTANDO…" : "⚡ EXPORTAR AHORA"}
          </button>
          <button data-testid="dashai-dataset-descargar-btn"
            onClick={() => window.open(`${API_URL}/api/dashai/dataset/descargar`, "_blank")}
            style={{ background: "linear-gradient(135deg, #BF953F, #FCF6BA 45%, #B38728)", color: "#0a0a0a",
              border: "none", fontWeight: 800, fontSize: "0.7rem", letterSpacing: "0.08em", padding: "0.6rem 1.1rem", cursor: "pointer" }}>
            <i className="fa fa-download" style={{ marginRight: 6 }} />CSV
          </button>
        </div>
      </div>

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
              {e.motivo === "normativa" ? "📜 NORMATIVA" : e.motivo?.startsWith("disparo") ? "⚡ DISPARO" : e.motivo === "manual" ? "MANUAL" : "60 MIN"}
            </span>
            <span style={{ color: "#cbd5e1" }}>Calibración {e.nivel_calibracion}% · {e.prospectos_sync} prospectos · {e.folders_sync} carpetas</span>
            {e.patron && <span style={{ color: "#9a8c52", flexBasis: "100%", fontSize: "0.7rem", fontStyle: "italic" }}>{e.patron}</span>}
          </div>
        ))}
      </div>
    </div>
  );
}
