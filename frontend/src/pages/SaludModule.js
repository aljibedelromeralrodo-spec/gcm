import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

const card = { background: "rgba(14,14,16,0.9)", padding: "1.3rem", borderRadius: "0px", border: "1px solid transparent", backgroundImage: "linear-gradient(115deg, rgba(255,255,255,0.09) 0%, rgba(255,255,255,0.02) 18%, transparent 32%), linear-gradient(160deg, rgba(30,30,30,0.95), rgba(10,10,10,0.98)), linear-gradient(135deg, #BF953F, #FCF6BA, #B38728, #FBF5B7, #AA771C)", boxShadow: "0 35px 70px -20px rgba(0,0,0,0.95), 0 0 38px -16px rgba(191,149,63,0.45)", backgroundOrigin: "border-box", backgroundClip: "padding-box, padding-box, border-box" };

function hora(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString("es-CL", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }); } catch { return iso; }
}

const Estado = ({ ok, textoOk, textoMal }) => (
  <span style={{ color: ok ? "#10d98e" : "#e11d48", fontWeight: 800, fontSize: "0.8rem", border: `1px solid ${ok ? "#10d98e" : "#e11d48"}`, borderRadius: 20, padding: "0.15rem 0.7rem" }}>
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
      axios.get(`${API}/api/calibracion/estado`).then(rc => setCalib(rc.data)).catch((e) => console.error(e));
    } catch (e) { setError(e.response?.data?.detail || e.message); }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [load]);

  if (error) return <div style={{ padding: "2rem", color: "#e11d48" }} data-testid="salud-error">Error cargando el panel: {error}</div>;
  if (!data) return <div style={{ padding: "3rem", textAlign: "center" }}><i className="fa fa-spinner fa-spin" style={{ fontSize: "2rem", color: "var(--gold)" }} /></div>;

  const m = data.monitoreo_buzon || {};
  const a = data.autocorreo_mesa || {};
  const c = data.cola_correos || {};
  const f = data.carpetas || {};

  return (
    <div style={{ padding: "1.5rem", color: "var(--white)", maxWidth: 1100 }} data-testid="salud-module">
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: "1.2rem" }}>
        <h2 style={{ margin: 0, color: "var(--gold)", fontSize: "1.3rem" }}><i className="fa fa-heartbeat" style={{ marginRight: 8 }} />Panel de Salud — Flujo 24/7</h2>
        <span data-testid="salud-motor-whatsapp" style={{ fontSize: "0.7rem", fontWeight: 800, letterSpacing: "0.08em", color: "#34eab9",
          border: "1px solid rgba(16,217,142,0.4)", padding: "0.3rem 0.8rem", whiteSpace: "nowrap" }}>
          🚀 Motor WhatsApp: {data.motor_whatsapp || "VÍA RÁPIDA ACTIVA (Sin API Meta)"}
        </span>
        <button onClick={load} data-testid="salud-refresh" style={{ marginLeft: "auto", background: "rgba(255,255,255,0.1)", border: "none", color: "#fff", borderRadius: 0, padding: "0.4rem 0.9rem", cursor: "pointer", fontWeight: 700 }}>
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
            {(m.ultimo_resultado?.errors || []).slice(0, 2).map((e, i) => <div key={i} style={{ color: "#fb7185", fontSize: "0.75rem" }}>⚠ {e}</div>)}
          </div>
        </div>

        {/* 2. CARPETAS */}
        <div style={card} data-testid="salud-carpetas">
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
            <h3 style={{ margin: 0, fontSize: "1rem", color: "var(--gold)" }}><i className="fa fa-folder-open" style={{ marginRight: 6 }} />2. Creación de carpetas</h3>
            <Estado ok={true} textoOk="MODO FORZADO" textoMal="" />
          </div>
          <div style={{ fontSize: "0.86rem", lineHeight: 1.9 }}>
            <div>Creadas últimas 24 h: <b style={{ color: "#10d98e" }} data-testid="salud-carpetas-24h">{f.creadas_24h}</b> · Descartados: <b style={{ color: "#f59e0b" }}>{f.descartados_24h}</b></div>
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
            <span style={{ marginLeft: "auto", fontSize: "0.85rem" }}>Enviados 24 h: <b style={{ color: "#10d98e" }} data-testid="salud-enviados-24h">{c.enviados_24h}</b></span>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <div>
              <div style={{ fontSize: "0.72rem", textTransform: "uppercase", opacity: 0.6, marginBottom: 4 }}>Últimos envíos (código SMTP)</div>
              {(c.ultimos_envios || []).length === 0 && <div style={{ fontSize: "0.8rem", opacity: 0.5 }}>Sin envíos registrados aún</div>}
              {(c.ultimos_envios || []).map((e, i) => (
                <div key={i} style={{ fontSize: "0.78rem", padding: "0.2rem 0", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                  <span style={{ color: e.ok ? "#10d98e" : "#e11d48", fontWeight: 700 }}>{e.smtp_code || "—"}</span>
                  <span style={{ opacity: 0.8 }}> → {e.to}</span>
                  <span style={{ opacity: 0.5 }}> · {(e.subject || "").slice(0, 40)} · {hora(e.fecha)}</span>
                </div>
              ))}
            </div>
            <div>
              <div style={{ fontSize: "0.72rem", textTransform: "uppercase", opacity: 0.6, marginBottom: 4 }}>Errores de envío (log_errores_correo)</div>
              {(c.ultimos_errores || []).length === 0 && <div style={{ fontSize: "0.8rem", color: "#10d98e" }}>✓ Sin errores registrados</div>}
              {(c.ultimos_errores || []).map((e, i) => (
                <div key={i} style={{ fontSize: "0.78rem", padding: "0.2rem 0", borderBottom: "1px solid rgba(255,255,255,0.05)", color: "#fda4af" }}>
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
                <span style={{ marginLeft: "auto", fontSize: "1.15rem", fontWeight: 900, color: calib.asertividad >= 80 ? "#10d98e" : calib.asertividad >= 60 ? "#f59e0b" : "#e11d48" }} data-testid="salud-asertividad">
                  {calib.asertividad}% asertividad
                </span>
              )}
            </div>
            <div style={{ fontSize: "0.9rem", fontStyle: "italic", opacity: 0.9, marginBottom: 8 }} data-testid="salud-calibracion-msg">“{calib.mensaje}”</div>
            <div style={{ display: "flex", gap: "1.4rem", fontSize: "0.83rem", flexWrap: "wrap" }}>
              <span>Respuestas de mesa: <b>{calib.respuestas_mesa}</b></span>
              <span style={{ color: "#10d98e" }}>Aprobadas: <b>{calib.aprobadas}</b></span>
              <span style={{ color: "#e11d48" }}>Rechazadas: <b>{calib.rechazadas}</b></span>
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

      <LoopsGuardCard />
    </div>
  );
}

function LoopsGuardCard() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState("");
  const [soloImap, setSoloImap] = useState(false);

  const load = useCallback(() => {
    axios.get(`${API}/api/loops/estado`).then(r => { setData(r.data); setErr(""); }).catch(e => {
      setErr(e.response?.data?.detail || e.message);
    });
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, [load]);

  const pausar = async (nombre, pausado) => {
    setBusy(nombre);
    try {
      await axios.post(`${API}/api/loops/${nombre}/pausa`, { pausado });
      load();
    } catch (e) {
      setErr(e.response?.data?.detail || e.message);
    } finally { setBusy(""); }
  };

  if (!data && !err) return null;
  const loops = (data?.loops || []).filter(l => !soloImap || l.imap);
  const candidatos = loops.filter(l => l.pausable);
  const protegidos = loops.filter(l => !l.pausable);

  return (
    <div style={{ ...card, marginTop: 16 }} data-testid="salud-loops">
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 10 }}>
        <h3 style={{ margin: 0, fontSize: "1rem", color: "var(--gold)" }}>
          <i className="fa fa-cogs" style={{ marginRight: 6 }} />Loops 24/7 — inventario y freno
        </h3>
        <Estado ok={!(data?.atrasados || []).length} textoOk="SIN ATRASOS" textoMal={`${(data?.atrasados || []).length} ATRASADO(S)`} />
        <span style={{ fontSize: "0.78rem", opacity: 0.75 }}>
          IMAP corriendo: <b>{data?.imap_corriendo ?? "—"}</b> · Pausados: <b>{data?.pausados ?? 0}</b>
        </span>
        <label style={{ marginLeft: "auto", fontSize: "0.75rem", cursor: "pointer" }}>
          <input type="checkbox" checked={soloImap} onChange={e => setSoloImap(e.target.checked)} data-testid="salud-loops-solo-imap" style={{ marginRight: 6 }} />
          Solo IMAP
        </label>
        <button onClick={load} data-testid="salud-loops-refresh" style={{ background: "rgba(255,255,255,0.1)", border: "none", color: "#fff", padding: "0.35rem 0.8rem", cursor: "pointer", fontWeight: 700 }}>
          Actualizar
        </button>
      </div>
      <p style={{ fontSize: "0.78rem", opacity: 0.8, margin: "0 0 10px" }}>
        {data?.nota || "Todo sigue encendido. Mesa, ingesta y cuenta única no se pausan."}
      </p>
      {err && <div data-testid="salud-loops-error" style={{ color: "#e11d48", fontSize: "0.8rem", marginBottom: 8 }}>{err}</div>}

      <div style={{ fontSize: "0.72rem", textTransform: "uppercase", opacity: 0.6, marginBottom: 4 }}>Candidatos a pausa (siguen encendidos)</div>
      {(candidatos.length === 0) && <div style={{ fontSize: "0.8rem", opacity: 0.5, marginBottom: 10 }}>Ninguno en esta vista</div>}
      {candidatos.map(l => (
        <div key={l.nombre} data-testid={`salud-loop-${l.nombre}`} style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", padding: "0.35rem 0", borderBottom: "1px solid rgba(255,255,255,0.05)", fontSize: "0.8rem" }}>
          <span style={{ color: l.pausado ? "#f59e0b" : (l.atrasado ? "#e11d48" : "#10d98e"), fontWeight: 800, minWidth: 72 }}>
            {l.pausado ? "PAUSADO" : l.atrasado ? "ATRASADO" : (l.estado || "—").toUpperCase()}
          </span>
          <b style={{ color: l.recomendado ? "var(--gold)" : "#fff" }}>{l.titulo}</b>
          {l.imap && <span style={{ opacity: 0.55 }}>IMAP</span>}
          {l.recomendado && <span style={{ color: "var(--gold)", fontSize: "0.68rem", fontWeight: 800 }}>recomendado</span>}
          <span style={{ opacity: 0.65, flex: 1, minWidth: 180 }}>{l.motivo}</span>
          <span style={{ opacity: 0.5, fontSize: "0.72rem" }}>♥ {hora(l.heartbeat)} · reinicios {l.reinicios}</span>
          {data?.editable && (
            <button data-testid={`salud-loop-pausa-${l.nombre}`} disabled={busy === l.nombre}
              onClick={() => pausar(l.nombre, !l.pausado)}
              style={{ background: l.pausado ? "linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C)" : "transparent",
                color: l.pausado ? "#0a0a0a" : "#f59e0b", border: "1px solid rgba(212,175,55,0.5)",
                fontWeight: 800, fontSize: "0.68rem", padding: "0.25rem 0.7rem", cursor: "pointer" }}>
              {l.pausado ? "Reanudar" : "Pausar"}
            </button>
          )}
        </div>
      ))}

      <details style={{ marginTop: 12 }} data-testid="salud-loops-protegidos">
        <summary style={{ cursor: "pointer", color: "var(--gold)", fontSize: "0.8rem", fontWeight: 700 }}>
          Loops protegidos ({protegidos.length}) — no se pausan
        </summary>
        {protegidos.map(l => (
          <div key={l.nombre} data-testid={`salud-loop-${l.nombre}`} style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", padding: "0.28rem 0", borderBottom: "1px solid rgba(255,255,255,0.04)", fontSize: "0.76rem" }}>
            <span style={{ color: l.atrasado ? "#e11d48" : "#94a3b8", fontWeight: 700, minWidth: 72 }}>
              {l.atrasado ? "ATRASADO" : (l.estado || "—")}
            </span>
            <b>{l.titulo}</b>
            {l.imap && <span style={{ opacity: 0.5 }}>IMAP</span>}
            {l.solapa?.length > 0 && <span style={{ opacity: 0.45 }}>solapa: {l.solapa.join(", ")}</span>}
            <span style={{ opacity: 0.6, flex: 1 }}>{l.motivo}</span>
            <span style={{ opacity: 0.45, fontSize: "0.7rem" }}>{hora(l.heartbeat)}</span>
          </div>
        ))}
      </details>
    </div>
  );
}
