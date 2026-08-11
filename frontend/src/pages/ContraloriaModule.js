import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import DOMPurify from "dompurify";
import { API_URL } from "../utils/formatters";

const RUBI = "#e11d48";
const ORO = "var(--gold, #D4AF37)";

export default function ContraloriaModule() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [cert, setCert] = useState(null);
  const [certLoading, setCertLoading] = useState(false);
  const [forense, setForense] = useState(null);
  const [reclamos, setReclamos] = useState(null);
  const [reclamoBusy, setReclamoBusy] = useState(false);
  const [reclamoOpen, setReclamoOpen] = useState(-1);

  const cargarReclamos = useCallback(async () => {
    try {
      const r = await axios.get(`${API_URL}/api/contraloria/forense/reclamaciones`);
      setReclamos(r.data);
    } catch { /* silencioso */ }
  }, []);

  const generarReclamos = async () => {
    setReclamoBusy(true);
    try {
      const r = await axios.post(`${API_URL}/api/contraloria/forense/reclamaciones`);
      setReclamos(r.data);
    } catch (e) { alert(e?.response?.data?.detail || "No se pudieron generar las reclamaciones"); }
    setReclamoBusy(false);
  };

  const enviarReclamo = async (idx, cliente) => {
    if (!window.confirm(`🔐 AUTORIZACIÓN DE GERARDO\n\n¿Enviar la reclamación formal del caso ${cliente} a aprobaciones@centralmutuos.cl?`)) return;
    setReclamoBusy(true);
    try {
      const r = await axios.post(`${API_URL}/api/contraloria/forense/reclamaciones/${idx}/enviar`, {}, { timeout: 120000 });
      alert(r.data.mensaje);
      cargarReclamos();
    } catch (e) { alert("❌ " + (e?.response?.data?.detail || e.message)); }
    setReclamoBusy(false);
  };

  const cargarForense = useCallback(async () => {
    try {
      const r = await axios.get(`${API_URL}/api/contraloria/forense`);
      setForense(r.data);
    } catch { /* silencioso */ }
  }, []);

  const lanzarForense = async () => {
    try {
      await axios.post(`${API_URL}/api/contraloria/forense/iniciar?dias=90`);
      setForense({ estado: "en_proceso", progreso: 0, total: 0 });
      const iv = setInterval(async () => {
        const r = await axios.get(`${API_URL}/api/contraloria/forense`);
        setForense(r.data);
        if (r.data?.estado === "completado") clearInterval(iv);
      }, 4000);
    } catch { /* silencioso */ }
  };

  const cargar = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API_URL}/api/contraloria/casos`);
      setData(r.data);
    } catch { setData({ error: true }); }
    setLoading(false);
  }, []);

  useEffect(() => { cargar(); cargarForense(); cargarReclamos(); }, [cargar, cargarForense, cargarReclamos]);

  const abrirCertificado = async (c) => {
    setCert({ loading: true, cliente: c.cliente });
    setCertLoading(true);
    try {
      const r = await axios.get(`${API_URL}/api/contraloria/certificado`, {
        params: { cliente: c.cliente, rut: c.rut || "" } });
      setCert(r.data);
    } catch (e) {
      setCert({ error: (e?.response?.data?.detail) || "No se pudo generar el certificado" });
    }
    setCertLoading(false);
  };

  const calibrar = async () => {
    setLoading(true);
    try { await axios.post(`${API_URL}/api/mesa-brain/calibrar`); await cargar(); }
    catch { setLoading(false); }
  };

  const m = data?.modelo || {};
  const v60 = m.ventana_60 || {};
  const casos = data?.casos || [];
  const inconsistencias = casos.filter(c => c.estado_auditoria === "BAJO AUDITORÍA").length;
  const falsosPos = casos.filter(c => c.estado_auditoria === "RIESGO DE FALSO POSITIVO").length;
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

      {/* 🔬 PANEL DE MANDO — AUDITORÍA FORENSE 90 DÍAS */}
      <div data-testid="forense-panel" style={{ border: "1px solid rgba(212,175,55,0.35)", background: "linear-gradient(160deg, #0d0b06, #050505)", padding: "1.2rem 1.4rem", marginBottom: "1.6rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <div style={{ flex: 1, minWidth: 240 }}>
            <div style={{ color: ORO, fontSize: "0.72rem", letterSpacing: "0.18em", textTransform: "uppercase" }}>🔬 Auditoría Forense · Ultra-Precisión {forense?.periodo_dias || 60} Días</div>
            <div style={{ color: "#9a8c52", fontSize: "0.72rem", marginTop: 3 }}>
              Minería de aprobaciones@centralmutuos.cl · triangulación contra reglamento de bodega (BTG/Ameris/Subsidio 02) · lotes diarios en segundo plano
            </div>
          </div>
          {forense?.estado === "en_proceso" && (
            <span style={{ color: "#C7B36A", fontSize: "0.78rem" }}><i className="fa fa-cog fa-spin" /> Procesando {forense.progreso || 0}/{forense.total || "…"}</span>
          )}
          {forense?.estado === "completado" && (
            <span style={{ color: "#8fd9b0", fontSize: "0.72rem" }}>✓ Completada {(forense.generado_en || "").slice(0, 16).replace("T", " ")} · {forense.progreso} casos
              {forense.nuevos_ultimo_barrido != null && <b style={{ color: "#FCF6BA", marginLeft: 8 }}>· {forense.nuevos_ultimo_barrido} errores NUEVOS</b>}
            </span>
          )}
          <button data-testid="forense-lanzar-btn" onClick={() => lanzarForense(60)} disabled={forense?.estado === "en_proceso"}
            style={{ background: "linear-gradient(135deg, #BF953F, #FCF6BA, #AA771C)", color: "#0a0a0a", border: "none",
              fontWeight: 800, fontSize: "0.72rem", letterSpacing: "0.08em", padding: "0.55rem 1.2rem", cursor: "pointer",
              opacity: forense?.estado === "en_proceso" ? 0.5 : 1 }}>
            {forense?.estado === "completado" ? "RE-EJECUTAR MINERÍA 60D" : "LANZAR MINERÍA 60 DÍAS"}
          </button>
        </div>
        {forense?.estado === "completado" && (
          <div style={{ marginTop: "1.1rem" }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10, marginBottom: "1rem" }}>
              {[["RIESGO CRÍTICO", "Carga conjunta >40% — el Contralor manda", "#ef4444"],
                ["RIESGO", "Aprobaciones que rompen políticas", RUBI],
                ["PERDIDA", "Rechazos viables — rescatar", "#f59e0b"],
                ["ERROR HUMANO", "Inconsistencias renta/antigüedad", "#93c5fd"]].map(([cat, desc, color]) => (
                <div key={cat} data-testid={`forense-cat-${cat.toLowerCase().replace(" ", "-")}`}
                  style={{ border: `1px solid ${color}44`, padding: "0.7rem 0.9rem" }}>
                  <div style={{ color, fontWeight: 800, fontSize: "1.3rem" }}>{(forense.resumen || {})[cat] ?? 0}</div>
                  <div style={{ color, fontSize: "0.68rem", fontWeight: 700, letterSpacing: "0.08em" }}>{cat}</div>
                  <div style={{ color: "#8a8a8a", fontSize: "0.65rem", marginTop: 2 }}>{desc}</div>
                </div>
              ))}
            </div>
            {(forense.hallazgos || []).length === 0 && (
              <div style={{ color: "#8fd9b0", fontSize: "0.78rem" }}>✓ Sin fallos de control detectados en el período.</div>
            )}
            {(forense.hallazgos || []).length > 0 && (
              <div data-testid="forense-titulo-lista" style={{ color: ORO, fontSize: "0.72rem", letterSpacing: "0.14em", textTransform: "uppercase", fontWeight: 800, marginBottom: 4 }}>
                ⚠ Errores MESA detectados ({(forense.hallazgos || []).length})
              </div>
            )}
            {(forense.hallazgos || []).map((h, k) => (
              <div key={k} data-testid={`forense-hallazgo-${k}`} style={{ display: "flex", gap: 10, alignItems: "baseline",
                padding: "0.5rem 0", borderTop: "1px solid rgba(255,255,255,0.06)", fontSize: "0.78rem", flexWrap: "wrap" }}>
                <span style={{ fontWeight: 800, fontSize: "0.65rem", letterSpacing: "0.06em", padding: "0.15rem 0.55rem", whiteSpace: "nowrap",
                  color: "#0a0a0a",
                  background: h.categoria === "RIESGO CRÍTICO" ? "linear-gradient(135deg,#7f1d1d,#ef4444)"
                    : h.categoria === "RIESGO" ? "linear-gradient(135deg,#e11d48,#fb7185)"
                    : h.categoria === "PERDIDA" ? "linear-gradient(135deg,#d97706,#fbbf24)"
                      : h.categoria === "AUDITADO AL VUELO" ? "linear-gradient(135deg,#0d9488,#5eead4)"
                      : h.categoria === "NO AUDITABLE" ? "linear-gradient(135deg,#64748b,#cbd5e1)" : "linear-gradient(135deg,#60a5fa,#bfdbfe)" }}>
                  {h.categoria}
                </span>
                <b style={{ color: "#f8fafc" }}>{h.cliente}</b>
                <span style={{ color: "#9a8c52", fontFamily: "monospace", fontSize: "0.72rem" }}>{h.rut || "sin RUT"}</span>
                <span style={{ color: "#6b6b6b", fontSize: "0.68rem" }}>{h.fecha_mesa}</span>
                <span style={{ color: "#cbd5e1", flexBasis: "100%", fontSize: "0.74rem" }}>{h.detalle}</span>
                {h.nota_dashai && <span style={{ color: "#9a8c52", flexBasis: "100%", fontSize: "0.7rem", fontStyle: "italic", borderLeft: `2px solid ${ORO}`, paddingLeft: 8 }}>{h.nota_dashai}</span>}
              </div>
            ))}
            {((forense.resumen || {}).PERDIDA || 0) > 0 && (
              <div data-testid="forense-reclamaciones-panel" style={{ marginTop: "1.2rem", border: "1px solid rgba(217,119,6,0.45)", background: "rgba(30,20,6,0.5)", padding: "0.9rem 1.1rem" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                  <b style={{ color: "#fbbf24", fontSize: "0.76rem", letterSpacing: "0.08em" }}>📨 MODO RECLAMACIÓN — Rescate de casos PERDIDA</b>
                  <button data-testid="reclamos-generar-btn" onClick={generarReclamos} disabled={reclamoBusy}
                    style={{ marginLeft: "auto", background: "linear-gradient(135deg,#d97706,#fbbf24)", color: "#0a0a0a", border: "none",
                      fontWeight: 800, fontSize: "0.68rem", letterSpacing: "0.06em", padding: "0.45rem 1rem", cursor: "pointer" }}>
                    {reclamoBusy ? "…" : "PREPARAR BORRADORES (TOP 5)"}
                  </button>
                </div>
                {(reclamos?.borradores || []).map((b, i) => (
                  <div key={i} data-testid={`reclamo-${i}`} style={{ borderTop: "1px solid rgba(255,255,255,0.07)", padding: "0.55rem 0", fontSize: "0.76rem" }}>
                    <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                      <b style={{ color: "#f8fafc" }}>{b.cliente}</b>
                      <span style={{ color: "#9a8c52", fontFamily: "monospace", fontSize: "0.7rem" }}>{b.rut || ""}</span>
                      <span style={{ color: "#6b6b6b", fontSize: "0.68rem" }}>{b.fecha_mesa}</span>
                      {b.enviado && <span style={{ color: "#8fd9b0", fontSize: "0.68rem", fontWeight: 700 }}>✓ Enviada {(b.enviado_en || "").slice(0, 10)}</span>}
                      <button data-testid={`reclamo-ver-${i}`} onClick={() => setReclamoOpen(reclamoOpen === i ? -1 : i)}
                        style={{ marginLeft: "auto", background: "transparent", color: "#C7B36A", border: "1px solid rgba(212,175,55,0.4)", padding: "0.25rem 0.7rem", cursor: "pointer", fontSize: "0.66rem", fontWeight: 700 }}>
                        {reclamoOpen === i ? "OCULTAR" : "VER BORRADOR"}
                      </button>
                      <button data-testid={`reclamo-enviar-${i}`} onClick={() => enviarReclamo(i, b.cliente)} disabled={reclamoBusy || b.enviado}
                        style={{ background: "linear-gradient(135deg, #BF953F, #FCF6BA, #AA771C)", color: "#0a0a0a", border: "none",
                          fontWeight: 800, fontSize: "0.66rem", padding: "0.3rem 0.8rem", cursor: "pointer", opacity: b.enviado ? 0.35 : 1 }}>
                        🔐 ENVIAR A MESA
                      </button>
                    </div>
                    {reclamoOpen === i && (
                      <div style={{ marginTop: 8, background: "#fff", padding: "0.9rem", maxHeight: "40vh", overflow: "auto" }}
                        dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(b.body) }} />
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div data-testid="contraloria-modelo" style={{ display: "flex", flexWrap: "wrap", gap: "0.8rem", marginBottom: "1.2rem" }}>
        {[
          { lbl: "Regla de Oro (60d)", val: v60.base != null ? `${Math.round(v60.base * 100)}%` : "—", color: ORO },
          { lbl: "Base histórica (180d)", val: m.base != null ? `${Math.round(m.base * 100)}%` : "—", color: ORO },
          { lbl: "Aprobadas 60d", val: v60.aprobadas ?? m.aprobadas ?? "—", color: ORO },
          { lbl: "Rechazadas 60d", val: v60.rechazadas ?? m.rechazadas ?? "—", color: RUBI },
          { lbl: "Bajo Auditoría", val: inconsistencias, color: inconsistencias ? RUBI : ORO },
          { lbl: "Riesgo Falso Positivo", val: falsosPos, color: falsosPos ? RUBI : ORO },
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
              const riesgo = c.estado_auditoria === "RIESGO DE FALSO POSITIVO";
              const audit = c.estado_auditoria === "BAJO AUDITORÍA" || riesgo;
              const recibido = c.estado_auditoria === "RECIBIDO DE MESA";
              return (
                <tr key={i} data-testid={`contraloria-fila-${i}`}
                  onClick={() => !recibido && abrirCertificado(c)}
                  style={{ borderBottom: "1px solid rgba(255,255,255,0.05)",
                  cursor: recibido ? "default" : "pointer",
                  background: riesgo ? "rgba(225,29,72,0.13)" : audit ? "rgba(225,29,72,0.07)" : "transparent",
                  opacity: recibido ? 0.65 : 1 }}>
                  <td style={{ padding: "0.6rem 0.9rem", opacity: 0.7, whiteSpace: "nowrap" }}>{(c.fecha || "").slice(0, 10)}</td>
                  <td style={{ padding: "0.6rem 0.9rem", fontWeight: 600 }}>{c.cliente}
                    {!recibido && <i className="fa fa-certificate" style={{ marginLeft: 8, color: ORO, fontSize: "0.7rem", opacity: 0.7 }} title="Ver Certificado de Auditoría Interna" />}
                  </td>
                  <td style={{ padding: "0.6rem 0.9rem" }}>
                    <span style={{ color: c.respuesta_mesa === "aprobacion" ? "#10d98e" : RUBI, fontWeight: 700, textTransform: "uppercase", fontSize: "0.7rem" }}>
                      {c.respuesta_mesa === "aprobacion" ? "Aprobada" : "Rechazada"}
                    </span>
                  </td>
                  <td style={{ padding: "0.6rem 0.9rem" }} title={(c.factores || []).join("\n")}>
                    {recibido
                      ? <span style={{ fontStyle: "italic", opacity: 0.8 }}>Documentación incompleta — auditoría no aplicada</span>
                      : (c.veredicto_dashai || (c.prob_dashai != null ? `Probabilidad de Aprobación MESA: ${c.prob_dashai}%` : "sin carpeta"))}
                  </td>
                  <td style={{ padding: "0.6rem 0.9rem", color: recibido ? "#9ca3af" : "#fda4af", fontSize: "0.72rem" }}>
                    {recibido
                      ? ((c.docs_faltantes || []).length ? `Faltan: ${c.docs_faltantes.join(" · ")}` : "—")
                      : ((c.criterios_fallidos || []).join(" · ") || "—")}
                  </td>
                  <td style={{ padding: "0.6rem 0.9rem" }}>
                    <span data-testid={`contraloria-estado-${i}`} style={{ fontWeight: 800, fontSize: "0.68rem", letterSpacing: "0.08em",
                      padding: "0.2rem 0.7rem", whiteSpace: "nowrap",
                      color: audit ? "#fff" : recibido ? "#d1d5db" : "#0a0a0a",
                      background: audit ? "linear-gradient(135deg, #9f1239, #e11d48)"
                        : recibido ? "rgba(255,255,255,0.08)"
                        : "linear-gradient(135deg, #BF953F, #FCF6BA, #AA771C)",
                      border: recibido ? "1px solid rgba(255,255,255,0.2)" : "none",
                      boxShadow: riesgo ? "0 0 22px -4px rgba(225,29,72,0.95)" : audit ? "0 0 18px -6px rgba(225,29,72,0.8)" : "none" }}>
                      {c.estado_auditoria}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {cert && (
        <div data-testid="contraloria-cert-modal" onClick={() => setCert(null)}
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", zIndex: 999,
            display: "flex", alignItems: "flex-start", justifyContent: "center", padding: "3rem 1rem", overflow: "auto" }}>
          <div onClick={e => e.stopPropagation()} style={{ background: "#0a0a0a", border: `1px solid ${ORO}`,
            maxWidth: 760, width: "100%", boxShadow: "0 30px 80px -20px rgba(0,0,0,0.9)" }}>
            <div style={{ background: "linear-gradient(135deg,#0a0a0a,#1a160c)", borderBottom: `1px solid ${ORO}`, padding: "1.3rem 1.6rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
                <div>
                  <div style={{ color: ORO, fontSize: "0.7rem", letterSpacing: "0.2em", textTransform: "uppercase" }}>Certificado de Auditoría Interna</div>
                  <div style={{ color: "#FCF6BA", fontSize: "1.3rem", fontWeight: 700, fontFamily: "'Playfair Display',serif", marginTop: 4 }}>{cert.cliente}</div>
                  {cert.certificado_id && <div style={{ color: "#9a8c52", fontSize: "0.7rem", fontFamily: "monospace", marginTop: 2 }}>{cert.certificado_id} · {cert.rut}</div>}
                </div>
                <button data-testid="cert-cerrar" onClick={() => setCert(null)} style={{ background: "transparent", border: `1px solid ${ORO}`, color: ORO, padding: "0.3rem 0.7rem", cursor: "pointer" }}>✕</button>
              </div>
            </div>
            <div style={{ padding: "1.4rem 1.6rem" }}>
              {certLoading && <div style={{ color: "#C7B36A", textAlign: "center", padding: "2rem" }}><i className="fa fa-cog fa-spin" /> Ejecutando auditoría 360°…</div>}
              {cert.error && <div style={{ color: "#fda4af", padding: "1rem" }}>{cert.error}</div>}
              {!certLoading && cert.estado_auditoria && (
                <>
                  <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", marginBottom: "1.2rem",
                    padding: "0.9rem 1.1rem",
                    background: cert.estado_auditoria === "RIESGO DE FALSO POSITIVO" ? "rgba(225,29,72,0.15)" : "rgba(212,175,55,0.08)",
                    border: `1px solid ${cert.estado_auditoria === "RIESGO DE FALSO POSITIVO" ? "rgba(225,29,72,0.5)" : "rgba(212,175,55,0.35)"}` }}>
                    <span style={{ fontWeight: 800, letterSpacing: "0.06em",
                      color: cert.estado_auditoria === "RIESGO DE FALSO POSITIVO" ? "#fecaca" : ORO }}>
                      {cert.estado_auditoria === "RIESGO DE FALSO POSITIVO" ? "🚨 " : "🛡 "}{cert.estado_auditoria}
                    </span>
                    <span style={{ color: "#e5e5e5", fontSize: "0.82rem" }}>Veredicto DashAI: <b>{cert.veredicto_dashai}</b></span>
                    <span style={{ color: "#9ca3af", fontSize: "0.75rem" }}>MESA: {cert.respuesta_mesa === "aprobacion" ? "Aprobó" : "Rechazó"} · {cert.monto_uf ? `${cert.monto_uf} UF` : ""} · {cert.con_subsidio ? "con subsidio" : "sin subsidio"}</span>
                  </div>

                  {(cert.politica_saltada || []).length > 0 && (
                    <div style={{ marginBottom: "1.2rem", border: "1px solid rgba(225,29,72,0.4)", background: "rgba(30,6,12,0.6)", padding: "0.9rem 1.1rem" }}>
                      <b style={{ color: "#fda4af", fontSize: "0.78rem", letterSpacing: "0.06em" }}>POLÍTICAS QUE LA MESA SE ESTÁ SALTANDO</b>
                      <ul style={{ margin: "0.6rem 0 0", paddingLeft: 18, color: "#fecaca", fontSize: "0.78rem", lineHeight: 1.7 }}>
                        {cert.politica_saltada.map((p, k) => <li key={k}>{p}</li>)}
                      </ul>
                    </div>
                  )}

                  {(cert.secciones || []).map((sec, si) => (
                    <div key={si} style={{ marginBottom: "1.2rem" }}>
                      <div style={{ color: ORO, fontSize: "0.75rem", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: "0.5rem", borderBottom: "1px solid rgba(212,175,55,0.2)", paddingBottom: 4 }}>{sec.titulo}</div>
                      {(sec.items || []).map((it, ii) => (
                        <div key={ii} style={{ display: "flex", justifyContent: "space-between", gap: 10, padding: "0.35rem 0", borderBottom: "1px solid rgba(255,255,255,0.04)", fontSize: "0.78rem" }}>
                          <span style={{ color: "#d1d5db", flex: 1 }}>
                            {it.ok === false ? "❌ " : it.ok === true ? "✅ " : "• "}{it.regla}
                          </span>
                          <span style={{ color: it.ok === false ? "#fda4af" : "#e5e5e5", fontFamily: "monospace", textAlign: "right" }}>
                            {it.real}{it.esperado && it.ok !== null ? ` (${it.esperado})` : ""}
                          </span>
                        </div>
                      ))}
                      {sec.nota && <div style={{ color: "#9a8c52", fontSize: "0.72rem", marginTop: 6, fontStyle: "italic" }}>{sec.nota}</div>}
                    </div>
                  ))}
                  <div style={{ color: "#6b6b6b", fontSize: "0.68rem", textAlign: "right", marginTop: "1rem" }}>
                    Generado por DashAI · Contraloría Suprema · {(cert.generado_en || "").slice(0, 16).replace("T", " ")}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
