import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

const card = { background: "rgba(15,23,42,0.6)", padding: "1.3rem", borderRadius: "14px", border: "1px solid rgba(255,255,255,0.08)" };

function hora(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString("es-CL", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }); } catch { return iso; }
}

const Estado = ({ ok, textoOk, textoMal }) => (
  <span style={{ color: ok ? "#22c55e" : "#ef4444", fontWeight: 800, fontSize: "0.8rem", border: `1px solid ${ok ? "#22c55e" : "#ef4444"}`, borderRadius: 20, padding: "0.15rem 0.7rem" }}>
    {ok ? `● ${textoOk}` : `● ${textoMal}`}
  </span>
);

export default function SaludModule() {
  const [data, setData] = useState(null);
  const [calib, setCalib] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/salud/estado`);
      setData(r.data); setError("");
      axios.get(`${API}/api/calibracion/estado`).then(rc => setCalib(rc.data)).catch(() => {});
    } catch (e) { setError(e.response?.data?.detail || e.message); }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [load]);

  if (error) return <div style={{ padding: "2rem", color: "#ef4444" }} data-testid="salud-error">Error cargando el panel: {error}</div>;
  if (!data) return <div style={{ padding: "3rem", textAlign: "center" }}><i className="fa fa-spinner fa-spin" style={{ fontSize: "2rem", color: "var(--gold)" }} /></div>;

  const m = data.monitoreo_buzon || {};
  const a = data.autocorreo_mesa || {};
  const c = data.cola_correos || {};
  const f = data.carpetas || {};

  return (
    <div style={{ padding: "1.5rem", color: "var(--white)", maxWidth: 1100 }} data-testid="salud-module">
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: "1.2rem" }}>
        <h2 style={{ margin: 0, color: "var(--gold)", fontSize: "1.3rem" }}><i className="fa fa-heartbeat" style={{ marginRight: 8 }} />Panel de Salud — Flujo 24/7</h2>
        <button onClick={load} data-testid="salud-refresh" style={{ marginLeft: "auto", background: "rgba(255,255,255,0.1)", border: "none", color: "#fff", borderRadius: 8, padding: "0.4rem 0.9rem", cursor: "pointer", fontWeight: 700 }}>
          <i className="fa fa-refresh" style={{ marginRight: 6 }} />Actualizar
        </button>
        <span style={{ fontSize: "0.72rem", opacity: 0.5 }}>Se actualiza solo cada 30 s</span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "1rem" }}>
        {/* 1. MONITOREO DEL BUZÓN */}
        <div style={card} data-testid="salud-monitoreo">
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
            <h3 style={{ margin: 0, fontSize: "1rem", color: "var(--gold)" }}><i className="fa fa-inbox" style={{ marginRight: 6 }} />1. Monitoreo del buzón</h3>
            <Estado ok={!m.alerta} textoOk="FUNCIONANDO" textoMal="ATRASADO" />
          </div>
          <div style={{ fontSize: "0.86rem", lineHeight: 1.9 }}>
            <div>Revisión cada <b style={{ color: "var(--gold)" }}>{m.intervalo_min} min</b>{m.corriendo_ahora ? " · 🔄 revisando ahora…" : ""}</div>
            <div>Última revisión: <b data-testid="salud-ultima-revision">{hora(m.ultima_revision)}</b> {m.hace_min != null && <span style={{ opacity: 0.6 }}>(hace {m.hace_min} min)</span>}</div>
            <div style={{ opacity: 0.75 }}>Último ciclo: {m.ultimo_resultado?.enqueued ?? 0} nuevos · {m.ultimo_resultado?.processed ?? 0} procesados · {m.ultimo_resultado?.carpetas ?? 0} carpetas</div>
            {(m.ultimo_resultado?.errors || []).slice(0, 2).map((e, i) => <div key={i} style={{ color: "#f87171", fontSize: "0.75rem" }}>⚠ {e}</div>)}
          </div>
        </div>

        {/* 2. CARPETAS */}
        <div style={card} data-testid="salud-carpetas">
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
            <h3 style={{ margin: 0, fontSize: "1rem", color: "var(--gold)" }}><i className="fa fa-folder-open" style={{ marginRight: 6 }} />2. Creación de carpetas</h3>
            <Estado ok={true} textoOk="MODO FORZADO" textoMal="" />
          </div>
          <div style={{ fontSize: "0.86rem", lineHeight: 1.9 }}>
            <div>Creadas últimas 24 h: <b style={{ color: "#22c55e" }} data-testid="salud-carpetas-24h">{f.creadas_24h}</b> · Descartados: <b style={{ color: "#f59e0b" }}>{f.descartados_24h}</b></div>
            {(f.ultimas || []).map((x, i) => (
              <div key={i} style={{ fontSize: "0.78rem", opacity: 0.85 }}>📁 {x.nombre} <span style={{ opacity: 0.55 }}>· {hora(x.fecha)} · {x.origen}</span></div>
            ))}
          </div>
        </div>

        {/* 3. COLA DE CORREOS */}
        <div style={{ ...card, gridColumn: "1 / -1" }} data-testid="salud-cola">
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10, flexWrap: "wrap" }}>
            <h3 style={{ margin: 0, fontSize: "1rem", color: "var(--gold)" }}><i className="fa fa-paper-plane" style={{ marginRight: 6 }} />3. Cola de correos (goteo anti-bloqueo)</h3>
            <Estado ok={(c.fallidos_24h || 0) === 0} textoOk="SIN ERRORES 24H" textoMal={`${c.fallidos_24h} ERROR(ES) 24H`} />
            <span style={{ fontSize: "0.75rem", opacity: 0.7 }}>Goteo: 1 correo cada <b>{c.goteo_seg}s</b> · Reintento automático a los <b>{c.reintento_seg}s</b></span>
            <span style={{ marginLeft: "auto", fontSize: "0.85rem" }}>Enviados 24 h: <b style={{ color: "#22c55e" }} data-testid="salud-enviados-24h">{c.enviados_24h}</b></span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <div>
              <div style={{ fontSize: "0.72rem", textTransform: "uppercase", opacity: 0.6, marginBottom: 4 }}>Últimos envíos (código SMTP)</div>
              {(c.ultimos_envios || []).length === 0 && <div style={{ fontSize: "0.8rem", opacity: 0.5 }}>Sin envíos registrados aún</div>}
              {(c.ultimos_envios || []).map((e, i) => (
                <div key={i} style={{ fontSize: "0.78rem", padding: "0.2rem 0", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                  <span style={{ color: e.ok ? "#22c55e" : "#ef4444", fontWeight: 700 }}>{e.smtp_code || "—"}</span>
                  <span style={{ opacity: 0.8 }}> → {e.to}</span>
                  <span style={{ opacity: 0.5 }}> · {(e.subject || "").slice(0, 40)} · {hora(e.fecha)}</span>
                </div>
              ))}
            </div>
            <div>
              <div style={{ fontSize: "0.72rem", textTransform: "uppercase", opacity: 0.6, marginBottom: 4 }}>Errores de envío (log_errores_correo)</div>
              {(c.ultimos_errores || []).length === 0 && <div style={{ fontSize: "0.8rem", color: "#22c55e" }}>✓ Sin errores registrados</div>}
              {(c.ultimos_errores || []).map((e, i) => (
                <div key={i} style={{ fontSize: "0.78rem", padding: "0.2rem 0", borderBottom: "1px solid rgba(255,255,255,0.05)", color: "#fca5a5" }}>
                  <b>{e.smtp_code || "—"}</b> → {e.destinatario} <span style={{ opacity: 0.7 }}>· intento {e.intento} · {(e.error || "").slice(0, 60)} · {hora(e.fecha)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* PANEL DE AUDITORÍA — CALIBRACIÓN DE RIESGO */}
        {calib && (
          <div style={{ ...card, gridColumn: "1 / -1", border: "1px solid rgba(212,175,55,0.35)" }} data-testid="salud-auditoria">
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8, flexWrap: "wrap" }}>
              <h3 style={{ margin: 0, fontSize: "1rem", color: "var(--gold)" }}><i className="fa fa-balance-scale" style={{ marginRight: 6 }} />Panel de Auditoría — Calibración de Riesgo</h3>
              {calib.asertividad != null && (
                <span style={{ marginLeft: "auto", fontSize: "1.15rem", fontWeight: 900, color: calib.asertividad >= 80 ? "#22c55e" : calib.asertividad >= 60 ? "#f59e0b" : "#ef4444" }} data-testid="salud-asertividad">
                  {calib.asertividad}% asertividad
                </span>
              )}
            </div>
            <div style={{ fontSize: "0.9rem", fontStyle: "italic", opacity: 0.9, marginBottom: 8 }} data-testid="salud-calibracion-msg">“{calib.mensaje}”</div>
            <div style={{ display: "flex", gap: "1.4rem", fontSize: "0.83rem", flexWrap: "wrap" }}>
              <span>Respuestas de mesa: <b>{calib.respuestas_mesa}</b></span>
              <span style={{ color: "#22c55e" }}>Aprobadas: <b>{calib.aprobadas}</b></span>
              <span style={{ color: "#ef4444" }}>Rechazadas: <b>{calib.rechazadas}</b></span>
              <span>Con predicción del sistema: <b>{calib.muestras_con_prediccion}</b> ({calib.aciertos} aciertos)</span>
            </div>
            {calib.tendencia && <div style={{ marginTop: 8, fontSize: "0.85rem", color: "#f59e0b", fontWeight: 700 }} data-testid="salud-tendencia">{calib.tendencia}</div>}
            <div style={{ marginTop: 8, fontSize: "0.75rem", opacity: 0.65 }}>
              Reglas duras activas: {(calib.hard_rules || []).join(" · ")}
            </div>
          </div>
        )}

        {/* AUTOCORREO MESA */}
        <div style={{ ...card, gridColumn: "1 / -1" }} data-testid="salud-autocorreo">
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <h3 style={{ margin: 0, fontSize: "1rem", color: "var(--gold)" }}><i className="fa fa-envelope-o" style={{ marginRight: 6 }} />Autocorreo de Mesa (aprobaciones/rechazos)</h3>
            <Estado ok={a.activo && !a.alerta} textoOk="ACTIVO" textoMal={a.activo ? "ATRASADO" : "APAGADO"} />
            <span style={{ fontSize: "0.85rem", opacity: 0.8 }}>Última corrida: <b>{hora(a.ultima_corrida)}</b>{a.hace_min != null ? ` (hace ${a.hace_min} min)` : ""} · Procesados: {a.ultimo_resultado?.processed ?? 0} · Enviados: {a.ultimo_resultado?.sent ?? 0}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
