import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

function formatDate(d) {
  if (!d) return "";
  try { return new Date(d).toLocaleDateString("es-CL").replace(/-/g, "/"); } catch { return d; }
}

export default function SeguimientoModule() {
  const [clientes, setClientes] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [selected, setSelected] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const [filterExec, setFilterExec] = useState("");
  const [viewMode, setViewMode] = useState("table");
  const [fichaData, setFichaData] = useState(null);
  const [fichaLoading, setFichaLoading] = useState(false);

  const fetchClientes = useCallback(async (q = "") => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/api/seguimiento/clientes`, { params: { q } });
      setClientes(r.data?.clientes || []);
    } catch { setClientes([]); }
    setLoading(false);
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/seguimiento/stats`);
      setStats(r.data);
    } catch (e) { console.error(e); }
  }, []);

  useEffect(() => { fetchClientes(); fetchStats(); }, [fetchClientes, fetchStats]);

  const handleSearch = () => fetchClientes(search);
  const handleSearchKey = (e) => { if (e.key === "Enter") handleSearch(); };

  // Get unique ejecutivos for filter
  const ejecutivosCM = [...new Set(clientes.map(c => c.ejecutivo_cm).filter(Boolean))].sort();
  const ejecutivosExt = [...new Set(clientes.map(c => c.ejecutivo_externo).filter(Boolean))].sort();

  // Apply filter
  const filteredClientes = filterExec
    ? clientes.filter(c => (c.ejecutivo_cm || "").toLowerCase() === filterExec.toLowerCase() || (c.ejecutivo_externo || "").toLowerCase() === filterExec.toLowerCase())
    : clientes;

  const processEmails = async () => {
    setProcessing(true);
    try {
      await axios.post(`${API}/api/seguimiento/process-emails?max_emails=30`);
      await fetchClientes(search);
      await fetchStats();
    } catch (e) { console.error(e); }
    setProcessing(false);
  };

  const openTimeline = async (clientName) => {
    setSelected(clientName);
    setTimelineLoading(true);
    try {
      const r = await axios.get(`${API}/api/seguimiento/clientes/${encodeURIComponent(clientName)}/timeline`);
      setTimeline(r.data?.timeline || []);
    } catch { setTimeline([]); }
    setTimelineLoading(false);
  };

  const closeTimeline = () => { setSelected(null); setTimeline([]); };

  const openFicha = async (clientName) => {
    setFichaLoading(true);
    try {
      const r = await axios.get(`${API}/api/reportes/ficha-cliente/${encodeURIComponent(clientName)}`);
      setFichaData(r.data);
    } catch { setFichaData(null); }
    setFichaLoading(false);
  };

  const closeFicha = () => setFichaData(null);

  const estadoColor = (estado) => {
    if (!estado) return "#888";
    const s = estado.toLowerCase();
    if (s.includes("aprob")) return "#10d98e";
    if (s.includes("rechaz")) return "#e11d48";
    if (s.includes("cierre") || s.includes("pago")) return "#d4af37";
    if (s.includes("pendiente")) return "#f59e0b";
    return "#d4af37";
  };

  return (
    <div className="module-content" data-testid="seguimiento-module">
      {/* Stats Bar */}
      {stats && (
        <div className="seg-stats-bar" data-testid="seg-stats">
          <div className="seg-stat">
            <span className="seg-stat-val">{stats.total_clientes}</span>
            <span className="seg-stat-label">Clientes</span>
          </div>
          <div className="seg-stat">
            <span className="seg-stat-val">{stats.total_operaciones}</span>
            <span className="seg-stat-label">Operaciones</span>
          </div>
          <div className="seg-stat">
            <span className="seg-stat-val">{stats.operaciones_semana}</span>
            <span className="seg-stat-label">Esta semana</span>
          </div>
        </div>
      )}

      {/* Search & Actions */}
      <div className="seg-toolbar" data-testid="seg-toolbar">
        <div className="seg-search-group">
          <input type="text" className="seg-search-input"
            placeholder="Buscar por nombre de cliente..."
            value={search} onChange={e => setSearch(e.target.value)}
            onKeyDown={handleSearchKey}
            data-testid="seg-search-input" />
          <button className="seg-search-btn" onClick={handleSearch} data-testid="seg-search-btn">
            <i className="fa fa-search"></i>
          </button>
        </div>
        <select className="seg-filter-select" value={filterExec} onChange={e => setFilterExec(e.target.value)} data-testid="seg-filter-exec">
          <option value="">Todos los ejecutivos</option>
          {ejecutivosCM.length > 0 && <optgroup label="Ejecutivos CM">
            {ejecutivosCM.map(e => <option key={`cm-${e}`} value={e}>{e}</option>)}
          </optgroup>}
          {ejecutivosExt.length > 0 && <optgroup label="Ejecutivos Externos">
            {ejecutivosExt.map(e => <option key={`ext-${e}`} value={e}>{e}</option>)}
          </optgroup>}
        </select>
        <button className="seg-process-btn" onClick={processEmails} disabled={processing} data-testid="seg-process-btn">
          {processing ? <><i className="fa fa-spinner fa-spin"></i> Procesando...</> : <><i className="fa fa-refresh"></i> Procesar correos</>}
        </button>
        <a className="seg-process-btn" href={`${API}/api/reportes/seguimiento/excel`} download data-testid="seg-excel-btn">
          <i className="fa fa-file-excel-o"></i> Excel
        </a>
        <div className="seg-view-toggle">
          <button className={viewMode === "table" ? "active" : ""} onClick={() => setViewMode("table")} data-testid="seg-view-table"><i className="fa fa-th-list"></i></button>
          <button className={viewMode === "kanban" ? "active" : ""} onClick={() => setViewMode("kanban")} data-testid="seg-view-kanban"><i className="fa fa-columns"></i></button>
        </div>
      </div>

      {/* Timeline Modal */}
      {selected && (
        <div className="seg-timeline-overlay" onClick={closeTimeline}>
          <div className="seg-timeline-modal" onClick={e => e.stopPropagation()} data-testid="seg-timeline-modal">
            <div className="seg-timeline-header">
              <h3>{selected}</h3>
              <button className="seg-timeline-close" onClick={closeTimeline} data-testid="seg-timeline-close">
                <i className="fa fa-times"></i>
              </button>
            </div>
            {timelineLoading ? (
              <div style={{ textAlign: "center", padding: "2rem" }}>
                <i className="fa fa-spinner fa-spin" style={{ fontSize: "1.5rem", color: "var(--gold)" }}></i>
              </div>
            ) : timeline.length === 0 ? (
              <p style={{ color: "var(--text-muted)", padding: "1.5rem", textAlign: "center" }}>Sin registros</p>
            ) : (
              <div className="seg-timeline" data-testid="seg-timeline-list">
                {timeline.map((t, i) => (
                  <div key={i} className="seg-timeline-entry" data-testid={`timeline-entry-${i}`}>
                    <div className="seg-tl-dot" style={{ background: estadoColor(t.estado) }}></div>
                    <div className="seg-tl-content">
                      <div className="seg-tl-date">{t.fecha_correo || formatDate(t.created_at)}</div>
                      <div className="seg-tl-subject">{t.asunto}</div>
                      <div className="seg-tl-summary">{t.resumen}</div>
                      <div className="seg-tl-meta">
                        <span className="seg-tl-estado" style={{ color: estadoColor(t.estado) }}>{t.estado}</span>
                        {t.correo_remitente && <span className="seg-tl-from"><i className="fa fa-envelope-o"></i> {t.correo_remitente.split("<")[0].trim()}</span>}
                        {t.ejecutivo_cm && <span className="seg-tl-exec"><i className="fa fa-user"></i> CM: {t.ejecutivo_cm}</span>}
                        {t.ejecutivo_externo && <span className="seg-tl-exec-ext"><i className="fa fa-user-o"></i> Ext: {t.ejecutivo_externo}</span>}
                        {t.monto_credito && <span className="seg-tl-monto"><i className="fa fa-money"></i> {t.monto_credito}</span>}
                        {t.tiene_adjuntos && <span className="seg-tl-att"><i className="fa fa-paperclip"></i></span>}
                      </div>
                      {t.cuerpo_preview && (
                        <div className="seg-tl-preview">{t.cuerpo_preview.slice(0, 200)}</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Client Table / Kanban */}
      {loading ? (
        <div style={{ textAlign: "center", padding: "3rem" }}>
          <i className="fa fa-spinner fa-spin" style={{ fontSize: "2rem", color: "var(--gold)" }}></i>
          <p style={{ color: "var(--text-secondary)", marginTop: "1rem" }}>Cargando seguimiento...</p>
        </div>
      ) : clientes.length === 0 ? (
        <div className="seg-empty" data-testid="seg-empty">
          <i className="fa fa-inbox" style={{ fontSize: "3rem", color: "var(--gold)", opacity: 0.3 }}></i>
          <p>Sin operaciones registradas</p>
          <p style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
            Presiona "Procesar correos" para extraer operaciones de los emails
          </p>
        </div>
      ) : viewMode === "kanban" ? (
        /* KANBAN VIEW */
        <div className="seg-kanban" data-testid="seg-kanban">
          {filterExec && <div className="seg-filter-badge">Filtrando: <strong>{filterExec}</strong> ({filteredClientes.length}) <button onClick={() => setFilterExec("")}><i className="fa fa-times"></i></button></div>}
          {["pendiente", "en proceso", "aprobado", "cierre", "firma", "pago", "rechazado"].map(col => {
            const items = filteredClientes.filter(c => (c.estado || "").toLowerCase().includes(col));
            if (items.length === 0 && !["pendiente","en proceso","aprobado"].includes(col)) return null;
            return (
              <div key={col} className="seg-kanban-col" data-testid={`kanban-col-${col.replace(/\s/g,'-')}`}>
                <div className="seg-kanban-header" style={{ borderColor: estadoColor(col) }}>
                  <span style={{ color: estadoColor(col) }}>{col.toUpperCase()}</span>
                  <span className="seg-kanban-count">{items.length}</span>
                </div>
                <div className="seg-kanban-cards">
                  {items.map((c, i) => (
                    <div key={i} className="seg-kanban-card" onClick={() => openFicha(c.id)} data-testid={`kanban-card-${col.replace(/\s/g,'-')}-${i}`}>
                      <div className="seg-kanban-name">{c.cliente_display || c.id}</div>
                      {c.proyecto && <div className="seg-kanban-project">{c.proyecto}</div>}
                      <div className="seg-kanban-meta">
                        {c.ejecutivo_cm && <span><i className="fa fa-user"></i> {c.ejecutivo_cm}</span>}
                        {c.monto_credito && <span><i className="fa fa-money"></i> {c.monto_credito}</span>}
                        <span><i className="fa fa-envelope"></i> {c.total_correos}</span>
                      </div>
                    </div>
                  ))}
                  {items.length === 0 && <div className="seg-kanban-empty">Sin operaciones</div>}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* TABLE VIEW */
        <div className="seg-table-wrap" data-testid="seg-table">
          {filterExec && <div className="seg-filter-badge">Filtrando: <strong>{filterExec}</strong> ({filteredClientes.length} clientes) <button onClick={() => setFilterExec("")}><i className="fa fa-times"></i></button></div>}
          <table className="seg-table">
            <thead>
              <tr>
                <th>Cliente</th>
                <th>RUT</th>
                <th>Proyecto</th>
                <th>Ejecutivo CM</th>
                <th>Ejecutivo Externo</th>
                <th>Remitente</th>
                <th>Monto</th>
                <th>Estado</th>
                <th>Correos</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filteredClientes.map((c, i) => (
                <tr key={i} className="seg-table-row" data-testid={`seg-row-${i}`}>
                  <td className="seg-name" onClick={() => openTimeline(c.id)} style={{ cursor: "pointer" }}>{c.cliente_display || c.id}</td>
                  <td>{c.rut || "-"}</td>
                  <td>{c.proyecto || "-"}</td>
                  <td className="seg-exec-cm">{c.ejecutivo_cm || "-"}</td>
                  <td className="seg-exec-ext">{c.ejecutivo_externo || "-"}</td>
                  <td className="seg-email">{c.correo_remitente ? c.correo_remitente.split("<")[0].trim() : "-"}</td>
                  <td className="seg-monto">{c.monto_credito || "-"}</td>
                  <td>
                    <select
                      data-testid={`seg-estado-select-${i}`}
                      value={(c.estado || "").toLowerCase().includes("aprob") ? "aprobacion" : (c.estado || "").toLowerCase().includes("rech") ? "rechazo" : "observacion"}
                      onChange={async (e) => {
                        try {
                          await axios.patch(`${API}/api/seguimiento/estado`, { cliente: c.cliente || c.cliente_display || c.id, estado: e.target.value });
                          fetchClientes();
                        } catch (err) { alert("Error: " + (err.response?.data?.detail || err.message)); }
                      }}
                      style={{ background: "transparent", color: estadoColor(c.estado), border: `1px solid ${estadoColor(c.estado)}`, borderRadius: 0, padding: "0.15rem 0.4rem", fontSize: "0.75rem", fontWeight: 700, cursor: "pointer" }}
                      title="Corregir estado manualmente"
                    >
                      <option value="aprobacion" style={{ color: "#10d98e", background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)" }}>aprobación</option>
                      <option value="rechazo" style={{ color: "#e11d48", background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)" }}>rechazo</option>
                      <option value="observacion" style={{ color: "#f59e0b", background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)" }}>observación</option>
                    </select>
                  </td>
                  <td style={{ textAlign: "center" }}>{c.total_correos}</td>
                  <td>
                    <button className="seg-ficha-btn" onClick={() => openFicha(c.id)} title="Ver ficha completa" data-testid={`ficha-btn-${i}`}>
                      <i className="fa fa-id-card-o"></i>
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Ficha Cliente Modal */}
      {(fichaData || fichaLoading) && (
        <div className="seg-timeline-overlay" onClick={closeFicha}>
          <div className="seg-timeline-modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 800 }} data-testid="ficha-modal">
            <div className="seg-timeline-header">
              <h3><i className="fa fa-id-card"></i> {fichaData?.cliente || "Cargando..."}</h3>
              <button className="seg-timeline-close" onClick={closeFicha}><i className="fa fa-times"></i></button>
            </div>
            {fichaLoading ? (
              <div style={{ textAlign: "center", padding: "2rem" }}>
                <i className="fa fa-spinner fa-spin" style={{ fontSize: "1.5rem", color: "var(--gold)" }}></i>
              </div>
            ) : fichaData ? (
              <div className="ficha-content">
                {/* Resumen */}
                <div className="ficha-summary">
                  <div className="ficha-sum-item"><span className="ficha-sum-label">Estado</span><span className="ficha-sum-val" style={{ color: estadoColor(fichaData.resumen?.ultimo_estado) }}>{fichaData.resumen?.ultimo_estado || "-"}</span></div>
                  <div className="ficha-sum-item"><span className="ficha-sum-label">Proyecto</span><span className="ficha-sum-val">{fichaData.resumen?.proyecto || "-"}</span></div>
                  <div className="ficha-sum-item"><span className="ficha-sum-label">Ejecutivo CM</span><span className="ficha-sum-val">{fichaData.resumen?.ejecutivo_cm || "-"}</span></div>
                  <div className="ficha-sum-item"><span className="ficha-sum-label">Correos</span><span className="ficha-sum-val">{fichaData.resumen?.total_correos || 0}</span></div>
                  <div className="ficha-sum-item"><span className="ficha-sum-label">Simulaciones</span><span className="ficha-sum-val">{fichaData.resumen?.total_simulaciones || 0}</span></div>
                  <div className="ficha-sum-item"><span className="ficha-sum-label">Carpeta</span><span className="ficha-sum-val">{fichaData.resumen?.tiene_carpeta ? `Si (${fichaData.resumen?.total_archivos} archivos)` : "No"}</span></div>
                  <div className="ficha-sum-item"><span className="ficha-sum-label">Comunicaciones</span><span className="ficha-sum-val">{fichaData.resumen?.total_comunicaciones || 0}</span></div>
                </div>

                {/* Seguimiento */}
                {fichaData.seguimiento?.length > 0 && (
                  <div className="ficha-section">
                    <h5><i className="fa fa-road"></i> Seguimiento ({fichaData.seguimiento.length})</h5>
                    {fichaData.seguimiento.slice(0, 8).map((s, i) => (
                      <div key={i} className="ficha-entry">
                        <span className="ficha-entry-date">{s.fecha_correo}</span>
                        <span className="ficha-entry-estado" style={{ color: estadoColor(s.estado) }}>{s.estado}</span>
                        <span className="ficha-entry-text">{s.resumen || s.asunto}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Simulaciones */}
                {fichaData.simulaciones?.length > 0 && (
                  <div className="ficha-section">
                    <h5><i className="fa fa-bar-chart"></i> Simulaciones ({fichaData.simulaciones.length})</h5>
                    {fichaData.simulaciones.map((s, i) => (
                      <div key={i} className="ficha-entry">
                        <span className="ficha-entry-date">{s.timestamp ? new Date(s.timestamp).toLocaleDateString("es-CL").replace(/-/g, "/") : ""}</span>
                        <span className={`ficha-entry-estado ${s.precalificacion_aprobada ? '' : 'fail'}`} style={{ color: s.precalificacion_aprobada ? "#10d98e" : "#e11d48" }}>
                          {s.precalificacion_aprobada ? "Aprobado" : "Rechazado"}
                        </span>
                        <span className="ficha-entry-text">{s.capacidad_credito_uf ? `${s.capacidad_credito_uf} UF` : ""}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Conversaciones */}
                {fichaData.conversaciones?.length > 0 && (
                  <div className="ficha-section">
                    <h5><i className="fa fa-comments"></i> Conversaciones con Central ({fichaData.conversaciones.length})</h5>
                    {fichaData.conversaciones.slice(0, 5).map((c, i) => (
                      <div key={i} className="ficha-entry">
                        <span className="ficha-entry-date">{c.timestamp ? new Date(c.timestamp).toLocaleDateString("es-CL").replace(/-/g, "/") : ""}</span>
                        <span className="ficha-entry-text">{(c.user_msg || "").slice(0, 80)}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Comunicaciones Enviadas */}
                {fichaData.comunicaciones?.length > 0 && (
                  <div className="ficha-section" data-testid="ficha-comunicaciones">
                    <h5><i className="fa fa-paper-plane"></i> Comunicaciones Enviadas ({fichaData.comunicaciones.length})</h5>
                    {fichaData.comunicaciones.map((c, i) => (
                      <div key={i} className="ficha-entry ficha-comm-entry">
                        <span className="ficha-entry-date">{c.sent_at ? new Date(c.sent_at).toLocaleDateString("es-CL").replace(/-/g, "/") : ""}</span>
                        <div className="ficha-comm-detail">
                          <span className="ficha-comm-to"><i className="fa fa-envelope-o"></i> {c.to}</span>
                          <span className="ficha-comm-subject">{c.subject}</span>
                          <span className="ficha-comm-by">Enviado por: {c.sent_by || "Central"}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
