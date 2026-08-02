import { useState, useEffect } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

export default function AutocorreoModule() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [runResult, setRunResult] = useState(null);
  const [msg, setMsg] = useState("");
  const [archive, setArchive] = useState([]);
  const [mailboxes, setMailboxes] = useState([]);
  const [reporte, setReporte] = useState(null);

  const formatDate = (iso) => {
    if (!iso) return "—";
    try {
      const d = new Date(iso);
      return d.toLocaleString("es-CL", { dateStyle: "short", timeStyle: "short" });
    } catch {
      return iso;
    }
  };

  const load = async () => {
    try {
      const [r, a, m, rd] = await Promise.all([
        axios.get(`${API_URL}/api/autocorreo/status`),
        axios.get(`${API_URL}/api/autocorreo/archive`).catch(() => ({ data: { folders: [] } })),
        axios.get(`${API_URL}/api/autocorreo/mailboxes?probe=true`).catch(() => ({ data: { accounts: [] } })),
        axios.get(`${API_URL}/api/reportes/diario/status`).catch(() => ({ data: null })),
      ]);
      setData(r.data);
      setArchive(a.data?.folders || []);
      setMailboxes(m.data?.accounts || []);
      setReporte(rd.data);
    } catch (e) {
      setMsg("Error cargando estado: " + (e.response?.data?.detail || e.message));
    }
  };

  const resetBackoff = async (email) => {
    try {
      const url = email
        ? `${API_URL}/api/autocorreo/imap/reset-backoff?account=${encodeURIComponent(email)}`
        : `${API_URL}/api/autocorreo/imap/reset-backoff`;
      await axios.post(url);
      setMsg(email ? `Backoff limpiado para ${email}` : "Backoff limpiado (todas las cuentas)");
      await load();
    } catch (e) {
      setMsg("Error: " + (e.response?.data?.detail || e.message));
    }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 15000); // refresh every 15s
    return () => clearInterval(t);
  }, []);

  const togglePeriodic = async () => {
    setLoading(true);
    try {
      await axios.post(`${API_URL}/api/autocorreo/periodic`, { enabled: !data.periodic_enabled });
      await load();
      setMsg(!data.periodic_enabled ? "Automatico ACTIVADO" : "Automatico DESACTIVADO");
    } catch (e) {
      setMsg("Error: " + (e.response?.data?.detail || e.message));
    }
    setLoading(false);
  };

  const toggleEnabled = async () => {
    setLoading(true);
    try {
      await axios.post(`${API_URL}/api/autocorreo/toggle`, { enabled: !data.enabled });
      await load();
    } catch (e) {
      setMsg("Error: " + (e.response?.data?.detail || e.message));
    }
    setLoading(false);
  };

  const setCutoffNow = async () => {
    if (!window.confirm("Marcar la linea AHORA? Los correos anteriores quedaran ignorados permanentemente.")) return;
    setLoading(true);
    try {
      const r = await axios.post(`${API_URL}/api/autocorreo/cutoff/now`);
      setMsg(`Linea de corte fijada en: ${formatDate(r.data.cutoff_iso)}`);
      await load();
    } catch (e) {
      setMsg("Error: " + (e.response?.data?.detail || e.message));
    }
    setLoading(false);
  };

  const clearCutoff = async () => {
    if (!window.confirm("Quitar la linea de corte? El sistema podria procesar correos antiguos.")) return;
    setLoading(true);
    try {
      await axios.post(`${API_URL}/api/autocorreo/cutoff/clear`);
      setMsg("Linea de corte removida");
      await load();
    } catch (e) {
      setMsg("Error: " + (e.response?.data?.detail || e.message));
    }
    setLoading(false);
  };

  const runNow = async () => {
    setLoading(true);
    setRunResult(null);
    try {
      const r = await axios.post(`${API_URL}/api/autocorreo/run`, {}, { timeout: 60000 });
      if (r.data.started || r.data.running) {
        setRunResult({ message: r.data.message || "Procesamiento iniciado en segundo plano..." });
        let tries = 0;
        const poll = setInterval(async () => {
          tries++;
          try {
            const s = await axios.get(`${API_URL}/api/autocorreo/status`);
            if (!s.data.running || tries >= 18) {
              clearInterval(poll);
              if (s.data.last_run_result) setRunResult(s.data.last_run_result);
              await load();
            }
          } catch { clearInterval(poll); }
        }, 10000);
      } else {
        setRunResult(r.data);
      }
      await load();
    } catch (e) {
      setMsg("Error ejecutando: " + (e.response?.data?.detail || e.message));
    }
    setLoading(false);
  };

  const toggleReporte = async () => {
    setLoading(true);
    try {
      const r = await axios.post(`${API_URL}/api/reportes/diario/toggle`, { enabled: !(reporte?.enabled) });
      setReporte(r.data);
      setMsg(r.data.enabled ? "Reporte diario ACTIVADO" : "Reporte diario desactivado");
    } catch (e) {
      setMsg("Error: " + (e.response?.data?.detail || e.message));
    }
    setLoading(false);
  };

  const cambiarHoraReporte = async () => {
    const v = prompt("¿A qué hora enviar el reporte diario? (0 a 23, hora Chile)", String(reporte?.hora ?? 10));
    if (v === null) return;
    const n = parseInt(v, 10);
    if (isNaN(n) || n < 0 || n > 23) return setMsg("Hora inválida (0 a 23)");
    const r = await axios.post(`${API_URL}/api/reportes/diario/toggle`, { hora: n });
    setReporte(r.data);
    setMsg(`Reporte diario programado a las ${n}:00 (hora Chile)`);
  };

  const enviarReporteAhora = async () => {
    if (!window.confirm("¿Enviar el reporte diario AHORA al correo destino?")) return;
    setLoading(true);
    try {
      const r = await axios.post(`${API_URL}/api/reportes/diario/enviar-ahora`, {}, { timeout: 60000 });
      setMsg(`✅ Reporte enviado a ${r.data.destino}: ${r.data.recibidas} recibidas, ${r.data.enviadas} enviadas a mesa`);
      await load();
    } catch (e) {
      setMsg("Error enviando reporte: " + (e.response?.data?.detail || e.message));
    }
    setLoading(false);
  };

  if (!data) {
    return <div style={{ padding: "2rem", color: "var(--white)" }}>Cargando...</div>;
  }

  return (
    <div style={{ padding: "1.5rem", color: "var(--white)", maxWidth: "1100px" }} data-testid="autocorreo-module">
      {msg && (
        <div style={{ padding: "0.75rem 1rem", borderRadius: "10px", background: "rgba(59,130,246,0.15)", border: "1px solid #3b82f6", marginBottom: "1rem", fontSize: "0.9rem" }} data-testid="autocorreo-msg">
          <i className="fa fa-info-circle" style={{ marginRight: "0.5rem" }} />{msg}
          <button onClick={() => setMsg("")} style={{ float: "right", background: "none", border: "none", color: "var(--white)", cursor: "pointer", opacity: 0.6 }}>
            <i className="fa fa-times" />
          </button>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: "1rem", marginBottom: "1.5rem" }}>
        <StatCard label="Total Enviados" value={data.sent} icon="fa-paper-plane" color="#22c55e" />
        <StatCard label="Total Fallidos" value={data.failed} icon="fa-exclamation-triangle" color={data.failed > 0 ? "#ef4444" : "#888"} />
        <StatCard label="Total Procesados" value={data.total} icon="fa-list" color="#3b82f6" />
        <StatCard label="Latencia" value="30 seg" icon="fa-bolt" color="#f59e0b" sub="Polling automatico" />
      </div>

      <div className="card" style={{ background: "rgba(15,23,42,0.6)", padding: "1.5rem", borderRadius: "14px", border: "1px solid rgba(255,255,255,0.08)", marginBottom: "1.5rem" }}>
        <h3 style={{ margin: "0 0 1rem", color: "var(--gold)", fontSize: "1.1rem" }}>
          <i className="fa fa-cogs" style={{ marginRight: "0.5rem" }} />Controles
        </h3>

        <Row label="Sistema Correo a Mesa" right={<StatusPill active={data.enabled} />}>
          <button onClick={toggleEnabled} disabled={loading} className="autocorreo-btn"
            data-testid="btn-toggle-enabled"
            style={{ background: data.enabled ? "#ef4444" : "#22c55e", color: "#fff" }}>
            {data.enabled ? "Desactivar" : "Activar"}
          </button>
        </Row>

        <Row label="Procesamiento Automatico (cada 30s)" right={<StatusPill active={data.periodic_enabled} />}>
          <button onClick={togglePeriodic} disabled={loading} className="autocorreo-btn"
            data-testid="btn-toggle-periodic"
            style={{ background: data.periodic_enabled ? "#ef4444" : "#22c55e", color: "#fff" }}>
            {data.periodic_enabled ? "Pausar" : "Activar 24/7"}
          </button>
        </Row>

        <Row label="Linea de corte" right={<span style={{ fontSize: "0.85rem", opacity: 0.85 }} data-testid="cutoff-display">{data.cutoff_iso ? formatDate(data.cutoff_iso) : "Sin corte (procesa todo)"}</span>}>
          <button onClick={setCutoffNow} disabled={loading} className="autocorreo-btn"
            data-testid="btn-cutoff-now"
            style={{ background: "#f59e0b", color: "#0a0e17" }}>
            <i className="fa fa-clock-o" style={{ marginRight: "0.4rem" }} />Marcar AHORA
          </button>
          {data.cutoff_iso && (
            <button onClick={clearCutoff} disabled={loading} className="autocorreo-btn"
              data-testid="btn-cutoff-clear"
              style={{ background: "transparent", border: "1px solid #888", color: "#bbb", marginLeft: "0.5rem" }}>
              Quitar
            </button>
          )}
        </Row>

        <Row label="Destino" right={<span style={{ fontSize: "0.85rem", opacity: 0.85 }} data-testid="destino-display">{data.destination}</span>}>
          <button onClick={runNow} disabled={loading} className="autocorreo-btn"
            data-testid="btn-run-now"
            style={{ background: "var(--gold)", color: "#0a0e17" }}>
            <i className="fa fa-play" style={{ marginRight: "0.4rem" }} />Ejecutar AHORA
          </button>
        </Row>

        {runResult && (
          <div style={{ marginTop: "1rem", padding: "0.75rem 1rem", background: "rgba(34,197,94,0.1)", border: "1px solid #22c55e", borderRadius: "10px", fontSize: "0.9rem" }} data-testid="run-result">
            {runResult.message ? (
              <span><strong style={{ color: "#eab308" }}>⏳ En proceso:</strong> {runResult.message}</span>
            ) : runResult.error ? (
              <span style={{ color: "#ef4444" }}>Error: {runResult.error}</span>
            ) : (
              <span><strong style={{ color: "#22c55e" }}>Ejecucion completa:</strong> {runResult.sent || 0} enviados, {runResult.processed || 0} procesados</span>
            )}
            {runResult.errors && runResult.errors.length > 0 && (
              <div style={{ marginTop: "0.5rem", color: "#ef4444" }}>Errores: {runResult.errors.slice(0,3).join(" | ")}</div>
            )}
          </div>
        )}
      </div>

      {/* REPORTE DIARIO 10:00 AM */}
      <div className="card" data-testid="reporte-diario-card" style={{ background: "rgba(15,23,42,0.6)", padding: "1.5rem", borderRadius: "14px", border: "1px solid rgba(255,255,255,0.08)", marginBottom: "1.5rem" }}>
        <h3 style={{ margin: "0 0 1rem", color: "var(--gold)", fontSize: "1.1rem" }}>
          <i className="fa fa-calendar-check-o" style={{ marginRight: "0.5rem" }} />Reporte Diario {reporte ? `(${reporte.hora ?? 10}:00 hrs Chile)` : ""}
        </h3>
        <p style={{ fontSize: "0.85rem", opacity: 0.75, margin: "0 0 0.8rem" }}>
          Todos los días a las {reporte?.hora ?? 10}:00 se envía al correo destino el listado de las últimas 24 hrs
          ({reporte?.hora ?? 10}:00 del día anterior → {reporte?.hora ?? 10}:00): <b>solicitudes de crédito recibidas</b> y
          las <b>enviadas efectivamente a mesa</b>, con nombre, RUT, inmobiliaria y ejecutivo.
        </p>
        <Row label="Envío automático diario" right={<StatusPill active={!!reporte?.enabled} />}>
          <button onClick={toggleReporte} disabled={loading} className="autocorreo-btn"
            data-testid="btn-toggle-reporte"
            style={{ background: reporte?.enabled ? "#ef4444" : "#22c55e", color: "#fff" }}>
            {reporte?.enabled ? "Desactivar" : "Activar"}
          </button>
          <button onClick={cambiarHoraReporte} disabled={loading} className="autocorreo-btn"
            data-testid="btn-hora-reporte"
            style={{ background: "#3b82f6", color: "#fff", marginLeft: "0.5rem" }}>
            <i className="fa fa-clock-o" style={{ marginRight: "0.4rem" }} />{reporte?.hora ?? 10}:00
          </button>
          <button onClick={enviarReporteAhora} disabled={loading} className="autocorreo-btn"
            data-testid="btn-reporte-ahora"
            style={{ background: "var(--gold)", color: "#0a0e17", marginLeft: "0.5rem" }}>
            <i className="fa fa-paper-plane" style={{ marginRight: "0.4rem" }} />Enviar AHORA
          </button>
        </Row>
        {reporte?.last_result?.enviado_en && (
          <div style={{ fontSize: "0.82rem", opacity: 0.8, marginTop: "0.4rem" }} data-testid="reporte-last-result">
            Último envío: {formatDate(reporte.last_result.enviado_en)} → {reporte.last_result.destino} ·{" "}
            {reporte.last_result.recibidas} recibidas · {reporte.last_result.enviadas} enviadas a mesa
            {reporte.last_result.error && <span style={{ color: "#ef4444" }}> · Error: {reporte.last_result.error}</span>}
          </div>
        )}
      </div>

      <div className="card" style={{ background: "rgba(15,23,42,0.6)", padding: "1.5rem", borderRadius: "14px", border: "1px solid rgba(255,255,255,0.08)", marginBottom: "1.5rem" }} data-testid="autocorreo-mailboxes">
        {mailboxes.some(m => m.auth_live === false) && (
          <div data-testid="auth-broken-banner" style={{
            background: "linear-gradient(90deg, #dc2626, #b91c1c)", color: "#fff",
            padding: "1rem 1.2rem", borderRadius: 12, marginBottom: "1.1rem",
            display: "flex", alignItems: "center", gap: "0.9rem", flexWrap: "wrap",
            boxShadow: "0 4px 20px rgba(220,38,38,0.35)",
          }}>
            <i className="fa fa-exclamation-triangle" style={{ fontSize: "1.6rem" }} />
            <div style={{ flex: 1, minWidth: 240 }}>
              <div style={{ fontWeight: 800, fontSize: "1rem", marginBottom: 3 }}>
                Gmail se desconectó — los correos NO se están procesando
              </div>
              <div style={{ fontSize: "0.82rem", opacity: 0.95 }}>
                {mailboxes.filter(m => m.auth_live === false).map(m => m.email).join(", ")} rechazó las credenciales. Reconectá con OAuth (30 seg) y el sistema arranca solo.
              </div>
            </div>
            {mailboxes.filter(m => m.auth_live === false).map(m => (
              <a key={m.email} href={`${API_URL}${m.connect_url}`} target="_blank" rel="noreferrer"
                data-testid={`btn-reconnect-${m.slot}`}
                style={{
                  background: "#fff", color: "#b91c1c", padding: "0.6rem 1.1rem",
                  borderRadius: 8, fontWeight: 800, textDecoration: "none",
                  display: "inline-flex", alignItems: "center", gap: 6,
                }}>
                <i className="fa fa-google" /> Reconectar {m.role}
              </a>
            ))}
          </div>
        )}
        <h3 style={{ margin: "0 0 0.6rem", color: "var(--gold)", fontSize: "1.1rem" }}>
          <i className="fa fa-envelope-o" style={{ marginRight: "0.5rem" }} />
          Cuentas de correo
          <span style={{ fontSize: "0.72rem", opacity: 0.6, fontWeight: 400, marginLeft: "0.7rem" }}>
            {mailboxes.length} activa{mailboxes.length === 1 ? "" : "s"}
          </span>
        </h3>
        <p style={{ fontSize: "0.82rem", opacity: 0.7, marginBottom: "1rem" }}>
          Cuando la cuenta <b>principal</b> queda bloqueada por Gmail (OVERQUOTA), Correo a Mesa lee y envía desde la de <b>respaldo</b>.
          Ambas envían al mismo destino: <code>{data.destination}</code>.
        </p>
        <div style={{ display: "grid", gap: "0.6rem" }}>
          {mailboxes.map((m) => (
            <div key={m.email} data-testid={`mailbox-${m.slot}`}
              style={{
                background: "rgba(255,255,255,0.03)",
                border: `1px solid ${m.backoff_remaining_s > 0 ? "#ef4444" : "rgba(255,255,255,0.08)"}`,
                borderRadius: "10px", padding: "0.9rem 1.1rem",
                display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.6rem",
              }}>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
                  <span style={{
                    fontSize: "0.7rem", fontWeight: 700, letterSpacing: 1,
                    padding: "0.15rem 0.5rem", borderRadius: 999,
                    background: m.role === "principal" ? "rgba(245,158,11,0.18)" : "rgba(139,92,246,0.18)",
                    color: m.role === "principal" ? "#f59e0b" : "#a78bfa",
                    textTransform: "uppercase",
                  }}>{m.role}</span>
                  <b style={{ fontSize: "0.95rem" }}>{m.email}</b>
                </div>
                <div style={{ fontSize: "0.8rem", opacity: 0.75, marginTop: "0.3rem" }}>
                  {m.auth_method === "oauth" && (
                    <span style={{ color: "#22c55e" }}><i className="fa fa-check-circle" /> OAuth conectado</span>
                  )}
                  {m.auth_method === "app_password" && (
                    <span style={{ color: "#22c55e" }}><i className="fa fa-key" /> App Password conectado</span>
                  )}
                  {m.auth_method === "none" && (
                    <span style={{ color: "#f59e0b" }}><i className="fa fa-exclamation-triangle" /> Sin credenciales</span>
                  )}
                  {m.backoff_remaining_s > 0 && (
                    <span style={{ color: "#ef4444", marginLeft: "0.7rem" }}>
                      <i className="fa fa-hourglass-half" /> OVERQUOTA — reintenta en {Math.floor(m.backoff_remaining_s / 60)}min {m.backoff_remaining_s % 60}s
                    </span>
                  )}
                </div>
              </div>
              <div style={{ display: "flex", gap: "0.4rem" }}>
                {m.auth_method !== "app_password" && (
                  <a href={`${API_URL}${m.connect_url}`} target="_blank" rel="noreferrer"
                    data-testid={`connect-oauth-${m.slot}`}
                    className="autocorreo-btn"
                    style={{
                      background: m.oauth_configured ? "transparent" : "#3b82f6",
                      color: m.oauth_configured ? "#93c5fd" : "#fff",
                      border: m.oauth_configured ? "1px solid #3b82f6" : "none",
                      textDecoration: "none", display: "inline-flex", alignItems: "center", justifyContent: "center",
                    }}>
                    <i className="fa fa-google" style={{ marginRight: "0.4rem" }} />
                    {m.oauth_configured ? "Reconectar" : "Conectar Gmail"}
                  </a>
                )}
                {m.backoff_remaining_s > 0 && (
                  <button onClick={() => resetBackoff(m.email)} className="autocorreo-btn"
                    data-testid={`reset-backoff-${m.slot}`}
                    style={{ background: "#f59e0b", color: "#0a0e17" }}>
                    <i className="fa fa-refresh" style={{ marginRight: "0.3rem" }} />Reset
                  </button>
                )}
              </div>
            </div>
          ))}
          {mailboxes.length <= 1 && (
            <div style={{
              padding: "0.8rem 1rem", borderRadius: 10,
              background: "rgba(139,92,246,0.08)", border: "1px dashed #a78bfa",
              fontSize: "0.85rem",
            }} data-testid="add-backup-hint">
              <b><i className="fa fa-lightbulb-o" /> Sumá una cuenta de respaldo</b><br/>
              Pedile al admin que agregue <code>EMAIL_USER_2=tucorreo@gmail.com</code> en <code>backend/.env</code> y reinicie el backend. Después volvé acá y hacé click en <b>Conectar Gmail</b> para autorizarla.
            </div>
          )}
        </div>
      </div>

      <div className="card" style={{ background: "rgba(15,23,42,0.6)", padding: "1.5rem", borderRadius: "14px", border: "1px solid rgba(255,255,255,0.08)" }} data-testid="autocorreo-manual-upload">
        <h3 style={{ margin: "0 0 0.8rem", color: "var(--gold)", fontSize: "1.1rem" }}>
          <i className="fa fa-cloud-upload" style={{ marginRight: "0.5rem" }} />
          Subida manual (bypass Gmail)
        </h3>
        <p style={{ fontSize: "0.85rem", opacity: 0.7, marginBottom: "1rem" }}>
          Cuando Gmail está bloqueado por cuota, podés subir directo los PDFs desde tu compu/celular.
          El sistema detecta simulación vs carta, ajusta las simulaciones y las archiva.
        </p>
        <ManualUploadForm apiUrl={API_URL} onDone={load} />
      </div>

      <div className="card" style={{ background: "rgba(15,23,42,0.6)", padding: "1.5rem", borderRadius: "14px", border: "1px solid rgba(255,255,255,0.08)" }} data-testid="autocorreo-archive">
        <h3 style={{ margin: "0 0 1rem", color: "var(--gold)", fontSize: "1.1rem" }}>
          <i className="fa fa-folder-open" style={{ marginRight: "0.5rem" }} />PDFs ajustados archivados por cliente
          <span style={{ fontSize: "0.75rem", opacity: 0.6, fontWeight: 400, marginLeft: "0.7rem" }}>
            {archive.length} carpeta{archive.length === 1 ? "" : "s"}
          </span>
        </h3>
        {archive.length === 0 ? (
          <div style={{ padding: "1rem", opacity: 0.6, fontSize: "0.9rem" }}>
            Todavia no hay archivos. Cada vez que Correo a Mesa procese un correo, guardara los PDFs ajustados aca en la carpeta del cliente.
          </div>
        ) : (
          <div style={{ display: "grid", gap: "0.6rem" }}>
            {archive.map((f) => {
              const adjusted = f.files.find((x) => /ajustad/i.test(x.name));
              const primary = adjusted || f.files[0];
              const primaryUrl = primary ? `${API_URL}/api/autocorreo/archive/${encodeURIComponent(f.cliente)}/${encodeURIComponent(primary.name)}` : null;
              return (
                <details key={f.cliente} style={{
                  background: "rgba(255,255,255,0.03)",
                  border: "1px solid rgba(255,255,255,0.08)",
                  borderRadius: "10px",
                  padding: "0.6rem 0.9rem",
                }} data-testid={`archive-folder-${f.cliente}`}>
                  <summary style={{ cursor: "pointer", fontWeight: 700, listStyle: "none", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    {primaryUrl ? (
                      <a href={primaryUrl} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}
                         data-testid={`open-adjusted-${f.cliente}`}
                         style={{ color: "var(--gold)", textDecoration: "none", display: "flex", alignItems: "center", gap: 6 }}>
                        <i className="fa fa-file-pdf-o" />
                        {f.cliente}
                        <span style={{ opacity: 0.55, fontSize: "0.75rem", marginLeft: 6, fontWeight: 400 }}>
                          {adjusted ? "(abre PDF ajustado)" : "(abre PDF)"}
                        </span>
                      </a>
                    ) : (
                      <span><i className="fa fa-folder" style={{ marginRight: "0.5rem", color: "var(--gold)" }} />{f.cliente}</span>
                    )}
                    <span style={{ opacity: 0.6, fontSize: "0.85rem" }}>{f.count} archivo{f.count === 1 ? "" : "s"}</span>
                  </summary>
                  <div style={{ marginTop: "0.6rem", paddingLeft: "1.5rem", display: "grid", gap: "0.3rem" }}>
                    {f.files.map((file) => (
                      <a key={file.name}
                        href={`${API_URL}/api/autocorreo/archive/${encodeURIComponent(f.cliente)}/${encodeURIComponent(file.name)}`}
                        target="_blank" rel="noreferrer"
                        style={{ color: "#93c5fd", textDecoration: "none", fontSize: "0.85rem",
                                display: "flex", justifyContent: "space-between", padding: "0.25rem 0" }}
                        data-testid={`archive-file-${file.name}`}>
                        <span><i className="fa fa-file-pdf-o" style={{ marginRight: "0.4rem", opacity: 0.75 }} />{file.name}</span>
                        <span style={{ opacity: 0.5, fontSize: "0.75rem" }}>{Math.round(file.size / 1024)} KB</span>
                      </a>
                    ))}
                  </div>
                </details>
              );
            })}
          </div>
        )}
      </div>

      <div className="card" style={{ background: "rgba(15,23,42,0.6)", padding: "1.5rem", borderRadius: "14px", border: "1px solid rgba(255,255,255,0.08)" }}>
        <h3 style={{ margin: "0 0 1rem", color: "var(--gold)", fontSize: "1.1rem" }}>
          <i className="fa fa-list" style={{ marginRight: "0.5rem" }} />Ultimos procesados
        </h3>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.88rem" }} data-testid="autocorreo-table">
            <thead>
              <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.1)", color: "var(--gold)" }}>
                <th style={{ textAlign: "left", padding: "0.6rem" }}>Fecha</th>
                <th style={{ textAlign: "left", padding: "0.6rem" }}>Cliente / Asunto</th>
                <th style={{ textAlign: "left", padding: "0.6rem" }}>Estado</th>
                <th style={{ textAlign: "left", padding: "0.6rem" }}>Reenviado a</th>
                <th style={{ textAlign: "left", padding: "0.6rem" }}>Detalle</th>
              </tr>
            </thead>
            <tbody>
              {(!data.recent || data.recent.length === 0) ? (
                <tr><td colSpan={5} style={{ padding: "1.5rem", textAlign: "center", opacity: 0.6 }}>Sin envios todavia</td></tr>
              ) : data.recent.map((r, i) => (
                <tr key={i} style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }} data-testid={`row-${i}`}>
                  <td style={{ padding: "0.6rem", whiteSpace: "nowrap", opacity: 0.8 }}>{formatDate(r.processed_at)}</td>
                  <td style={{ padding: "0.6rem", maxWidth: "300px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.subject || "—"}</td>
                  <td style={{ padding: "0.6rem" }}>
                    <span style={{
                      padding: "0.15rem 0.55rem", borderRadius: "999px", fontSize: "0.78rem", fontWeight: 700,
                      background: r.status === "sent" ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)",
                      color: r.status === "sent" ? "#22c55e" : "#ef4444",
                    }}>{r.status === "sent" ? "Enviado" : "Fallido"}</span>
                  </td>
                  <td style={{ padding: "0.6rem", maxWidth: "220px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} data-testid={`reenviado-${i}`}
                      title={r.reenviado ? `Reenviado a ${r.reenviado_a}${r.reenviado_fecha ? " el " + formatDate(r.reenviado_fecha) : ""}` : "Sin reenvío detectado en Enviados"}>
                    {r.reenviado
                      ? <span style={{ color: "#22c55e", fontWeight: 600 }}><i className="fa fa-share" style={{ marginRight: "0.35rem" }} />{r.reenviado_a || "Sí"}</span>
                      : <span style={{ opacity: 0.35 }}>—</span>}
                  </td>
                  <td style={{ padding: "0.6rem", opacity: 0.7, fontSize: "0.8rem", maxWidth: "240px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {r.error ? <span style={{ color: "#ef4444" }}>{r.error}</span> : (r.attachments_info || "—")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <style>{`
        .autocorreo-btn {
          padding: 0.5rem 1rem; border-radius: 8px; border: none;
          cursor: pointer; font-weight: 700; font-size: 0.85rem;
          transition: opacity 0.2s; min-width: 130px;
        }
        .autocorreo-btn:disabled { opacity: 0.5; cursor: wait; }
        .autocorreo-btn:hover:not(:disabled) { opacity: 0.85; }
      `}</style>
    </div>
  );
}


function ManualUploadForm({ apiUrl, onDone }) {
  const [cliente, setCliente] = useState("");
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  const submit = async () => {
    if (!cliente.trim() || files.length === 0) {
      alert("Ingresá el nombre del cliente y al menos un PDF.");
      return;
    }
    setBusy(true);
    setResult(null);
    try {
      const fd = new FormData();
      fd.append("cliente", cliente.trim());
      for (const f of files) fd.append("files", f);
      const r = await axios.post(`${apiUrl}/api/autocorreo/manual-archive`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResult(r.data);
      onDone && onDone();
    } catch (e) {
      alert("Error: " + (e.response?.data?.detail || e.message));
    } finally { setBusy(false); }
  };

  return (
    <div style={{ display: "grid", gap: "0.8rem" }}>
      <div>
        <label style={{ display: "block", fontSize: "0.85rem", marginBottom: 4, opacity: 0.8 }}>
          Nombre del cliente
        </label>
        <input type="text" value={cliente} onChange={(e) => setCliente(e.target.value)}
          placeholder="Ej: Jose Cambimbo"
          data-testid="manual-cliente"
          style={{
            width: "100%", padding: "0.5rem", borderRadius: 8,
            border: "1px solid rgba(255,255,255,0.15)",
            background: "rgba(0,0,0,0.3)", color: "#fff", fontSize: "0.9rem",
          }} />
      </div>
      <div>
        <label style={{ display: "block", fontSize: "0.85rem", marginBottom: 4, opacity: 0.8 }}>
          PDFs (simulación + carta)
        </label>
        <input type="file" accept="application/pdf" multiple
          onChange={(e) => setFiles(Array.from(e.target.files))}
          data-testid="manual-files"
          style={{ width: "100%", color: "#fff", fontSize: "0.85rem" }} />
        {files.length > 0 && (
          <div style={{ fontSize: "0.8rem", opacity: 0.7, marginTop: 4 }}>
            {files.length} archivo{files.length === 1 ? "" : "s"} seleccionado{files.length === 1 ? "" : "s"}
          </div>
        )}
      </div>
      <button className="docs-btn primary" onClick={submit} disabled={busy}
        data-testid="btn-manual-upload"
        style={{ alignSelf: "flex-start" }}>
        {busy ? (<><i className="fa fa-spinner fa-spin" /> Procesando...</>) :
                (<><i className="fa fa-cloud-upload" /> Subir y archivar</>)}
      </button>
      {result && (
        <div style={{
          background: "rgba(34,197,94,0.1)", border: "1px solid #22c55e",
          padding: "0.7rem", borderRadius: 8, fontSize: "0.85rem",
        }}>
          <b>✅ Archivado en {result.folder}</b>
          {(() => {
            const adj = result.saved.find((s) => s.type === "simulacion_ajustada");
            if (!adj) return null;
            const url = `${apiUrl}/api/autocorreo/archive/${encodeURIComponent(result.cliente)}/${encodeURIComponent(adj.name)}`;
            return (
              <div style={{ marginTop: 6 }}>
                <a href={url} target="_blank" rel="noreferrer"
                   data-testid="link-open-adjusted"
                   style={{ color: "#22c55e", fontWeight: 700, textDecoration: "underline" }}>
                  <i className="fa fa-external-link" /> Abrir PDF ajustado ahora
                </a>
              </div>
            );
          })()}
          <ul style={{ margin: "0.4rem 0 0", paddingLeft: 20 }}>
            {result.saved.map((s, i) => {
              const url = `${apiUrl}/api/autocorreo/archive/${encodeURIComponent(result.cliente)}/${encodeURIComponent(s.name)}`;
              return (
                <li key={i}>
                  <a href={url} target="_blank" rel="noreferrer" style={{ color: "#93c5fd" }}>{s.name}</a>
                  <span style={{ opacity: 0.7 }}> ({s.type}{s.pages_removed !== undefined ? `, removidas ${s.pages_removed}/${s.pages_original} pág` : ""})</span>
                </li>
              );
            })}
          </ul>
          {result.errors && result.errors.length > 0 && (
            <div style={{ marginTop: 6, color: "#fca5a5" }}>
              Errores: {result.errors.map((e, i) => <div key={i}>• {e.file}: {e.error}</div>)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StatusPill({ active }) {
  return (
    <span style={{
      padding: "0.25rem 0.75rem", borderRadius: "999px", fontSize: "0.8rem", fontWeight: 700,
      background: active ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)",
      color: active ? "#22c55e" : "#ef4444",
      border: `1px solid ${active ? "#22c55e" : "#ef4444"}`,
    }}>
      <i className={`fa ${active ? "fa-check-circle" : "fa-times-circle"}`} style={{ marginRight: "0.4rem" }} />
      {active ? "Activo" : "Inactivo"}
    </span>
  );
}

function StatCard({ label, value, icon, color, sub }) {
  return (
    <div style={{
      background: "rgba(15,23,42,0.6)", padding: "1.2rem 1.4rem",
      borderRadius: "14px", border: "1px solid rgba(255,255,255,0.08)",
    }} data-testid={`stat-${label.toLowerCase().replace(/\s/g,'-')}`}>
      <div style={{ display: "flex", alignItems: "center", gap: "0.7rem", marginBottom: "0.4rem" }}>
        <i className={`fa ${icon}`} style={{ color, fontSize: "1.2rem" }} />
        <span style={{ fontSize: "0.85rem", opacity: 0.75 }}>{label}</span>
      </div>
      <div style={{ fontSize: "1.8rem", fontWeight: 800, color }}>{value}</div>
      {sub && <div style={{ fontSize: "0.75rem", opacity: 0.55, marginTop: "0.2rem" }}>{sub}</div>}
    </div>
  );
}

function Row({ label, right, children }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "0.85rem 0", borderBottom: "1px solid rgba(255,255,255,0.05)",
      gap: "1rem", flexWrap: "wrap",
    }}>
      <div style={{ flex: 1, minWidth: "200px" }}>
        <div style={{ fontWeight: 600 }}>{label}</div>
        {right && <div style={{ marginTop: "0.3rem" }}>{right}</div>}
      </div>
      <div>{children}</div>
    </div>
  );
}
