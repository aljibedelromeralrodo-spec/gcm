import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const COLORES = { daniela: "#38bdf8", victoria: "#a78bfa", postventa: "#4ade80" };
const glass = { background: "rgba(30,41,59,0.55)", border: "1px solid rgba(148,163,184,0.18)",
  borderRadius: 14, padding: "0.9rem 1.1rem" };

const Barras = ({ datos, color }) => {
  const max = Math.max(...datos, 1);
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 46 }}>
      {datos.map((v, h) => (
        <div key={h} title={`${String(h).padStart(2, "0")}:00 — ${v} gestión(es)`}
          style={{ flex: 1, height: `${Math.max((v / max) * 100, v ? 12 : 4)}%`,
            background: v ? color : "rgba(148,163,184,0.15)", borderRadius: 2 }} />
      ))}
    </div>
  );
};

const LineasSemana = ({ serie }) => {
  const claves = ["daniela", "victoria", "postventa"];
  const max = Math.max(...serie.flatMap(d => claves.map(k => d[k] || 0)), 1);
  const W = 560, H = 110;
  const x = i => 20 + (i * (W - 40)) / Math.max(serie.length - 1, 1);
  const y = v => H - 15 - (v / max) * (H - 30);
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} data-testid="comparativa-semanal">
      {claves.map(k => (
        <polyline key={k} fill="none" stroke={COLORES[k]} strokeWidth="2.5"
          points={serie.map((d, i) => `${x(i)},${y(d[k] || 0)}`).join(" ")} />
      ))}
      {serie.map((d, i) => (
        <text key={d.dia} x={x(i)} y={H - 2} textAnchor="middle" fontSize="9" fill="#64748b">
          {d.dia.slice(5)}</text>
      ))}
    </svg>
  );
};

export default function GestionEjecutivosModule() {
  const [data, setData] = useState(null);
  const [fuentesModal, setFuentesModal] = useState(null);
  const [nuevoCorreo, setNuevoCorreo] = useState("");
  const [ahora, setAhora] = useState(Date.now());

  const recargar = useCallback(() => {
    axios.get(`${API}/api/gestion-ejecutivos`).then(r => setData(r.data)).catch(() => {});
  }, []);
  useEffect(() => {
    recargar();
    const iv = setInterval(recargar, 300000);
    const reloj = setInterval(() => setAhora(Date.now()), 60000);
    return () => { clearInterval(iv); clearInterval(reloj); };
  }, [recargar]);

  const opFuente = async (ejecutivo, accion, correo) => {
    try {
      await axios.post(`${API}/api/gestion-ejecutivos/fuentes`, { ejecutivo, accion, correo });
      setNuevoCorreo("");
      recargar();
      const r = await axios.get(`${API}/api/gestion-ejecutivos/fuentes`);
      setFuentesModal(m => (m ? { ...m, fuentes: r.data.fuentes[m.ejecutivo] || [] } : m));
    } catch (e) { window.alert(e.response?.data?.detail || "Error al guardar la fuente"); }
  };

  const minDesde = data?.ultima_actualizacion
    ? Math.round((ahora - new Date(data.ultima_actualizacion).getTime()) / 60000) : null;
  const cons = data?.consolidado;

  return (
    <div data-testid="gestion-ejecutivos-modulo">
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
        <h3 style={{ margin: 0, color: "#d4af37", letterSpacing: 2, fontSize: "1rem" }}>
          👥 GESTIÓN POR EJECUTIVO — TIEMPO REAL</h3>
        <span style={{ color: "#64748b", fontSize: "0.62rem" }}>
          Medidor de actividad, no espía de contenido · actualiza cada 5 min</span>
        <span data-testid="gestion-ultima-actualizacion" style={{ marginLeft: "auto", fontSize: "0.62rem",
          color: minDesde !== null && minDesde > 10 ? "#eab308" : "#94a3b8",
          background: minDesde !== null && minDesde > 10 ? "rgba(234,179,8,0.12)" : "transparent",
          border: minDesde !== null && minDesde > 10 ? "1px solid rgba(234,179,8,0.5)" : "none",
          borderRadius: 8, padding: "0.25rem 0.6rem" }}>
          {data?.ultima_actualizacion
            ? `${minDesde > 10 ? "⚠️ " : "🕐 "}Última actualización: ${data.ultima_actualizacion.slice(11, 16)} UTC (hace ${minDesde} min)`
            : "🕐 Esperando primer barrido…"}
        </span>
      </div>

      {cons && (
        <div data-testid="gestion-consolidado" style={{ ...glass, borderColor: "rgba(212,175,55,0.4)", marginBottom: 12 }}>
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap", alignItems: "center" }}>
            <div>
              <div style={{ color: "#94a3b8", fontSize: "0.58rem", fontWeight: 800, letterSpacing: 1 }}>TOTAL DE GESTIONES DEL EQUIPO HOY</div>
              <div data-testid="gestion-total-hoy" style={{ color: "#f8fafc", fontWeight: 900, fontSize: "1.5rem" }}>{cons.total_hoy}</div>
            </div>
            <div>
              <div style={{ color: "#94a3b8", fontSize: "0.58rem", fontWeight: 800, letterSpacing: 1 }}>EJECUTIVO MÁS ACTIVO DEL DÍA</div>
              <div data-testid="gestion-mas-activo" style={{ color: "#d4af37", fontWeight: 900, fontSize: "1rem" }}>{cons.mas_activo || "—"}</div>
            </div>
            <div style={{ flex: 1, minWidth: 320 }}>
              <div style={{ color: "#94a3b8", fontSize: "0.58rem", fontWeight: 800, letterSpacing: 1 }}>
                COMPARATIVA SEMANAL
                {Object.entries(COLORES).map(([k, c]) =>
                  <span key={k} style={{ marginLeft: 10, color: c }}>■ {data.modulos[k]?.nombre?.split(" ")[0] || k}</span>)}
              </div>
              <LineasSemana serie={cons.comparativa_semanal || []} />
            </div>
          </div>
          {(cons.alertas_baja_actividad || []).length > 0 && (
            <div data-testid="gestion-alerta-baja" style={{ marginTop: 8, color: "#eab308", fontSize: "0.64rem" }}>
              🔔 {cons.alertas_baja_actividad.join(" · ")}
            </div>
          )}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: 12 }}>
        {Object.entries(data?.modulos || {}).map(([ej, m]) => (
          <div key={ej} data-testid={`gestion-modulo-${ej}`} style={{ ...glass, borderTop: `3px solid ${COLORES[ej]}` }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <b style={{ color: "#d4af37", fontSize: "0.86rem", letterSpacing: 1 }}>{m.nombre.toUpperCase()}</b>
              <button data-testid={`gestion-fuentes-btn-${ej}`} title="Configurar correos fuente del ejecutivo"
                onClick={() => setFuentesModal({ ejecutivo: ej, nombre: m.nombre, fuentes: m.fuentes })}
                style={{ marginLeft: "auto", cursor: "pointer", background: "transparent",
                  border: "1px solid rgba(212,175,55,0.4)", color: "#d4af37", borderRadius: 8,
                  padding: "0.2rem 0.5rem", fontSize: "0.7rem" }}>⚙️</button>
            </div>
            {m.alerta_incompleto && (
              <div data-testid={`gestion-incompleto-${ej}`} style={{ marginTop: 6, color: "#eab308", fontSize: "0.6rem",
                background: "rgba(234,179,8,0.1)", border: "1px solid rgba(234,179,8,0.4)", borderRadius: 8, padding: "0.35rem 0.6rem" }}>
                {m.mensaje_incompleto || "⚠️ Reporte posiblemente incompleto — configure los correos fuente en ⚙️"}
              </div>
            )}
            <div style={{ display: "flex", gap: 14, marginTop: 10 }}>
              {[["HOY", m.hoy], ["SEMANA", m.semana], ["MES", m.mes]].map(([k, v]) => (
                <div key={k}>
                  <div style={{ color: "#94a3b8", fontSize: "0.56rem", fontWeight: 800, letterSpacing: 1 }}>{k}</div>
                  <div style={{ color: "#f8fafc", fontWeight: 900, fontSize: "1.2rem" }}>{v}</div>
                </div>
              ))}
              <div style={{ marginLeft: "auto", textAlign: "right" }}>
                <div style={{ color: "#94a3b8", fontSize: "0.56rem", fontWeight: 800, letterSpacing: 1 }}>CUMPLIMIENTO vs PROMEDIO</div>
                <div style={{ color: m.cumplimiento_pct >= 100 ? "#4ade80" : "#f8fafc", fontWeight: 900, fontSize: "1.2rem" }}>
                  {m.cumplimiento_pct}%</div>
              </div>
            </div>
            <div style={{ marginTop: 10 }}>
              <div style={{ color: "#94a3b8", fontSize: "0.56rem", fontWeight: 800, letterSpacing: 1, marginBottom: 3 }}>
                ACTIVIDAD POR HORA (HOY)</div>
              <Barras datos={m.por_hora || []} color={COLORES[ej]} />
            </div>
            {(m.tipos || []).length > 0 && (
              <div style={{ marginTop: 10, display: "flex", flexWrap: "wrap", gap: 4 }}>
                {m.tipos.map(t => (
                  <span key={t.tipo} style={{ fontSize: "0.6rem", background: "rgba(148,163,184,0.12)",
                    borderRadius: 8, padding: "0.2rem 0.5rem", color: "#e2e8f0" }}>{t.tipo}: <b>{t.total}</b></span>
                ))}
              </div>
            )}
            {(m.clientes_hoy || []).length > 0 && (
              <div style={{ marginTop: 8 }}>
                <div style={{ color: "#94a3b8", fontSize: "0.56rem", fontWeight: 800, letterSpacing: 1 }}>CLIENTES GESTIONADOS HOY</div>
                <div style={{ color: "#e2e8f0", fontSize: "0.64rem" }}>{m.clientes_hoy.join(" · ")}</div>
              </div>
            )}
            {m.postventa && (
              <div data-testid="gestion-postventa-extras" style={{ marginTop: 10, display: "flex", gap: 14,
                borderTop: "1px solid rgba(148,163,184,0.15)", paddingTop: 8 }}>
                {[["CASOS ACTIVOS", m.postventa.casos_activos], ["RESUELTOS HOY", m.postventa.resueltos_hoy],
                  ["PROMEDIO RESOLUCIÓN", `${m.postventa.tiempo_promedio_dias} días`]].map(([k, v]) => (
                  <div key={k}>
                    <div style={{ color: "#94a3b8", fontSize: "0.54rem", fontWeight: 800 }}>{k}</div>
                    <div style={{ color: "#4ade80", fontWeight: 900, fontSize: "0.9rem" }}>{v}</div>
                  </div>
                ))}
              </div>
            )}
            {m.protegida && (
              <p style={{ marginTop: 8, marginBottom: 0, color: "#64748b", fontSize: "0.56rem", fontStyle: "italic" }}>
                Presentación en positivo garantizada: se destaca lo realizado, jamás se muestra como insuficiente.</p>
            )}
          </div>
        ))}
      </div>

      <p style={{ color: "#64748b", fontSize: "0.6rem", marginTop: 12 }}>
        🔒 {data?.privacidad || "Privacidad absoluta: nunca se muestra el contenido de un correo."} · Histórico persistido en la bóveda.</p>

      {fuentesModal && (
        <div data-testid="gestion-fuentes-modal" onClick={() => setFuentesModal(null)}
          style={{ position: "fixed", inset: 0, background: "rgba(2,6,23,0.75)", zIndex: 100,
            display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div onClick={e => e.stopPropagation()} style={{ ...glass, background: "#0f172a", width: 460, maxWidth: "92vw" }}>
            <h4 style={{ margin: 0, color: "#d4af37", fontSize: "0.86rem" }}>⚙️ Correos fuente — {fuentesModal.nombre}</h4>
            <p style={{ color: "#64748b", fontSize: "0.6rem" }}>Agregar/quitar es inmediato · sin límite de casillas · queda en bitácora</p>
            {(fuentesModal.fuentes || []).map(c => (
              <div key={c} style={{ display: "flex", alignItems: "center", gap: 8, padding: "0.3rem 0",
                borderBottom: "1px solid rgba(148,163,184,0.12)" }}>
                <span style={{ color: "#e2e8f0", fontSize: "0.7rem", flex: 1 }}>{c}</span>
                <button data-testid={`gestion-quitar-${c}`} onClick={() => opFuente(fuentesModal.ejecutivo, "quitar", c)}
                  style={{ cursor: "pointer", background: "#5C1A1A", color: "#fff", border: "none",
                    borderRadius: 6, padding: "0.2rem 0.6rem", fontSize: "0.6rem", fontWeight: 800 }}>QUITAR</button>
              </div>
            ))}
            {(fuentesModal.fuentes || []).length === 0 &&
              <p style={{ color: "#94a3b8", fontSize: "0.64rem" }}>
                🤖 Detección automática activa: el sistema identifica al ejecutivo por nombre en las casillas
                del administrador (Regla #36) y aprende sus direcciones solo. Agregar casillas es opcional.</p>}
            <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
              <input data-testid="gestion-nuevo-correo" value={nuevoCorreo} onChange={e => setNuevoCorreo(e.target.value)}
                placeholder="correo@ejecutivo.cl"
                style={{ flex: 1, background: "rgba(2,6,23,0.9)", border: "1px solid rgba(148,163,184,0.3)",
                  color: "#f8fafc", borderRadius: 8, padding: "0.4rem 0.6rem", fontSize: "0.7rem" }} />
              <button data-testid="gestion-agregar-fuente"
                onClick={() => nuevoCorreo.includes("@") && opFuente(fuentesModal.ejecutivo, "agregar", nuevoCorreo.trim())}
                className="maserati-btn" style={{ minHeight: 34 }}>AGREGAR FUENTE</button>
            </div>
            <button data-testid="gestion-fuentes-cerrar" onClick={() => setFuentesModal(null)}
              style={{ marginTop: 12, background: "transparent", border: "1px solid rgba(255,255,255,0.25)",
                color: "#e2e8f0", borderRadius: 8, padding: "0.3rem 0.8rem", cursor: "pointer", fontSize: "0.68rem" }}>Cerrar</button>
          </div>
        </div>
      )}
    </div>
  );
}
