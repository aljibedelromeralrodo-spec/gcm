import { useState, useEffect, useMemo, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const HITO = {
  ok: { c: "#22c55e", i: "fa-check-circle", t: "Éxito" },
  proceso: { c: "#f59e0b", i: "fa-clock-o", t: "Proceso" },
  pendiente: { c: "#f59e0b", i: "fa-hourglass-half", t: "Pendiente" },
  bloqueo: { c: "#ef4444", i: "fa-ban", t: "Bloqueo" },
  alerta: { c: "#ef4444", i: "fa-exclamation-triangle", t: "ALERTA" },
};
const Icono = ({ estado }) => {
  const h = HITO[estado] || HITO.pendiente;
  return <i className={`fa ${h.i}`} title={h.t} style={{ color: h.c, fontSize: "1rem" }} />;
};

// SISTEMA DE ICONOGRAFÍA: ✅ verde · ⏳ amarillo · ⚠️ rojo
const EstadoRadar = ({ estado, title }) => {
  if (estado === "ok") return <span title={title || "Completo"} style={{ fontSize: "0.85rem" }}>✅</span>;
  if (estado === "alerta") return <span title={title || "Alerta"} style={{ fontSize: "0.85rem" }}>⚠️</span>;
  if (estado === "pendiente_informacion") return <span title={title} style={{ color: "#94a3b8", fontSize: "0.58rem" }}>Pendiente de Información</span>;
  return <span title={title || "En proceso"} style={{ fontSize: "0.85rem" }}>⏳</span>;
};

const selEstilo = { background: "rgba(255,255,255,0.06)", border: "1px solid rgba(148,163,184,0.3)",
  color: "#e2e8f0", padding: "0.45rem 0.6rem", borderRadius: 10, fontSize: "0.7rem" };

const RECLAMOS_UI = [
  ["tasacion", "📩 Reclamar Tasación", f => f.tasacion_estado !== "ok"],
  ["serviu", "📩 Reclamar SERVIU", f => !!f.subsidio],
  ["actualizacion", "📩 Reclamar Actualización", f => f.doc20?.estado !== "ok"],
  ["firmas", "📩 Reclamar Firmas", f => f.hito_firmas !== "ok"],
  ["movimiento", "📩 Reclamar Movimiento", f => !!f.inactivo_96h],
];

export default function GerenciaComercialModule() {
  const [data, setData] = useState(null);
  const [feed, setFeed] = useState(null);
  const [busyRec, setBusyRec] = useState("");
  const [filtro, setFiltro] = useState({ broker: "", desde: "", hasta: "", docs: "", tipo: "" });

  const recargar = useCallback(() => {
    axios.get(`${API}/api/gerencia/cartera`).then(r => setData(r.data)).catch(() => setData({ cartera: [] }));
  }, []);
  useEffect(() => { recargar(); }, [recargar]);

  // FEED DE GERENCIA: hitos externos de la Malla de Inteligencia, actualizado al segundo
  useEffect(() => {
    const load = () => axios.get(`${API}/api/hitos/feed`).then(r => setFeed(r.data)).catch(() => {});
    load();
    const iv = setInterval(load, 1000);
    return () => clearInterval(iv);
  }, []);

  const exportar = async () => {
    const r = await axios.get(`${API}/api/gerencia/export-xlsx`, { responseType: "blob" });
    const url = URL.createObjectURL(r.data);
    const a = document.createElement("a");
    a.href = url; a.download = `Reporte_Gerencia_${data?.mes || ""}.xlsx`; a.click();
    URL.revokeObjectURL(url);
  };

  const marcarFirma = async (fid, rol, estado) => {
    try { await axios.post(`${API}/api/flujos/firmas/${fid}`, { rol, estado }); recargar(); }
    catch (e) { console.error(e); }
  };
  const fecharFirma = async (fid, fecha) => {
    try { await axios.post(`${API}/api/flujos/fecha-firma/${fid}`, { fecha }); recargar(); }
    catch (e) { console.error(e); }
  };

  // ACCIÓN ÚNICA (Regla #49): el reclamo SOLO sale cuando Rodrigo pincha
  const reclamar = async (fid, tipo, destinatario) => {
    setBusyRec(`${fid}-${tipo}`);
    try {
      await axios.post(`${API}/api/gerencia/reclamo/${fid}`, { tipo, destinatario });
      recargar();
    } catch (e) {
      const det = e.response?.data?.detail || "Error de envío";
      if (e.response?.status === 400 && det.includes("correo configurado")) {
        const manual = window.prompt("El Broker no tiene correo configurado.\nIngrese el correo del destinatario:");
        if (manual) { await reclamar(fid, tipo, manual); return; }
      } else {
        window.alert(det);
      }
    }
    setBusyRec("");
  };

  // CENTRO DE FILTRADO MULTI-VARIABLE (instantáneo, en memoria — Regla #54)
  const cartera = useMemo(() => {
    let fs = data?.cartera || [];
    if (filtro.broker) fs = fs.filter(f => (f.broker_origen || "DIRECTO") === filtro.broker);
    if (filtro.desde) fs = fs.filter(f => (f.actualizado || "") >= filtro.desde);
    if (filtro.hasta) fs = fs.filter(f => (f.actualizado || "") <= filtro.hasta);
    if (filtro.docs === "completo") fs = fs.filter(f => f.documentacion === "ok" && f.doc20?.estado === "ok");
    if (filtro.docs === "incompleto") fs = fs.filter(f => !(f.documentacion === "ok" && f.doc20?.estado === "ok"));
    if (filtro.tipo === "subsidio") fs = fs.filter(f => f.subsidio);
    if (filtro.tipo === "sin_subsidio") fs = fs.filter(f => !f.subsidio);
    if (filtro.tipo === "inmobiliaria") fs = fs.filter(f => f.tipo_operacion === "INMOBILIARIA");
    return fs;
  }, [data, filtro]);

  const glass = { background: "rgba(30,41,59,0.55)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)",
    border: "1px solid rgba(148,163,184,0.18)", borderRadius: 14 };
  const res = data?.resumen || {};

  const Tarjeta = ({ k, titulo, val, activo }) => (
    <button data-testid={`gerencia-card-${k}`} onClick={() => setFiltro({ ...filtro, tipo: activo ? "" : k })}
      className="maserati-btn" style={{ flexDirection: "column", alignItems: "flex-start", gap: 2, minWidth: 160,
        borderColor: activo ? "#d4af37" : undefined, background: activo ? "rgba(212,175,55,0.12)" : undefined }}>
      <span style={{ fontSize: "0.58rem", color: "#94a3b8", letterSpacing: "0.12em" }}>{titulo}</span>
      <span style={{ fontSize: "0.9rem", color: "#FCF6BA" }}>{val?.n ?? 0} ops · {Number(val?.uf ?? 0).toLocaleString("es-CL")} UF</span>
    </button>
  );

  return (
    <div className="module-content" data-testid="gerencia-module" style={{ background: "#0f172a", minHeight: "100%", padding: "1.2rem", borderRadius: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap", marginBottom: 14 }}>
        <h3 style={{ margin: 0, color: "#f8fafc", fontSize: "1.05rem" }}>
          <i className="fa fa-line-chart" style={{ color: "#d4af37", marginRight: 8 }} />Gerencia Comercial — Centro de Mando Estratégico
        </h3>
        <span style={{ color: "#94a3b8", fontSize: "0.72rem" }}>Mes {data?.mes || "…"} · {cartera.length}/{data?.total ?? 0} operaciones · Auditoría DashAI: {(data?.ultima_auditoria_dashai || "").slice(0, 16) || "pendiente"}</span>
        <button data-testid="btn-export-gerencia" onClick={exportar} className="maserati-btn" style={{ marginLeft: "auto" }}>
          <i className="fa fa-file-excel-o" /> Exportar Reporte Mensual
        </button>
      </div>

      {/* CABECERA SEGMENTADA: sumatorias con filtrado dinámico */}
      <div className="gerencia-filtros" data-testid="gerencia-cards" style={{ marginBottom: 12 }}>
        <Tarjeta k="subsidio" titulo="CON SUBSIDIO" val={res.subsidio} activo={filtro.tipo === "subsidio"} />
        <Tarjeta k="sin_subsidio" titulo="SIN SUBSIDIO" val={res.sin_subsidio} activo={filtro.tipo === "sin_subsidio"} />
        <Tarjeta k="inmobiliaria" titulo="INMOBILIARIA" val={{ n: (data?.cartera || []).filter(f => f.tipo_operacion === "INMOBILIARIA").length, uf: 0 }} activo={filtro.tipo === "inmobiliaria"} />
        <button data-testid="gerencia-card-total" onClick={() => setFiltro({ broker: "", desde: "", hasta: "", docs: "", tipo: "" })}
          className="maserati-btn neon" style={{ flexDirection: "column", alignItems: "flex-start", gap: 2, minWidth: 160 }}>
          <span style={{ fontSize: "0.58rem", color: "#94a3b8", letterSpacing: "0.12em" }}>TOTAL (limpiar filtros)</span>
          <span style={{ fontSize: "0.9rem" }}>{res.total?.n ?? 0} ops · {Number(res.total?.uf ?? 0).toLocaleString("es-CL")} UF</span>
        </button>
      </div>

      {/* CENTRO DE FILTRADO MULTI-VARIABLE */}
      <div className="gerencia-filtros" data-testid="gerencia-filtros" style={{ ...glass, padding: "0.7rem 0.9rem", marginBottom: 12 }}>
        <label style={{ color: "#94a3b8", fontSize: "0.62rem" }}>Broker<br />
          <select data-testid="filtro-broker" style={selEstilo} value={filtro.broker} onChange={e => setFiltro({ ...filtro, broker: e.target.value })}>
            <option value="">Todos</option>
            {(data?.brokers || []).map(b => <option key={b} value={b}>{b}</option>)}
          </select>
        </label>
        <label style={{ color: "#94a3b8", fontSize: "0.62rem" }}>Desde<br />
          <input data-testid="filtro-desde" type="date" style={selEstilo} value={filtro.desde} onChange={e => setFiltro({ ...filtro, desde: e.target.value })} />
        </label>
        <label style={{ color: "#94a3b8", fontSize: "0.62rem" }}>Hasta<br />
          <input data-testid="filtro-hasta" type="date" style={selEstilo} value={filtro.hasta} onChange={e => setFiltro({ ...filtro, hasta: e.target.value })} />
        </label>
        <label style={{ color: "#94a3b8", fontSize: "0.62rem" }}>Estado documental<br />
          <select data-testid="filtro-docs" style={selEstilo} value={filtro.docs} onChange={e => setFiltro({ ...filtro, docs: e.target.value })}>
            <option value="">Todos</option>
            <option value="completo">Completo</option>
            <option value="incompleto">Incompleto</option>
          </select>
        </label>
        <label style={{ color: "#94a3b8", fontSize: "0.62rem" }}>Tipo operación<br />
          <select data-testid="filtro-tipo" style={selEstilo} value={filtro.tipo} onChange={e => setFiltro({ ...filtro, tipo: e.target.value })}>
            <option value="">Todas</option>
            <option value="subsidio">Subsidio</option>
            <option value="sin_subsidio">Sin Subsidio</option>
            <option value="inmobiliaria">Inmobiliaria</option>
          </select>
        </label>
      </div>

      {feed && (
        <div data-testid="gerencia-feed-hitos" style={{ ...glass, borderColor: "rgba(212,175,55,0.4)", padding: "0.8rem 1rem", marginBottom: 12 }}>
          <div style={{ display: "flex", gap: 10, alignItems: "baseline", flexWrap: "wrap", marginBottom: 6 }}>
            <b style={{ color: "#d4af37", fontSize: "0.78rem" }}>🕸️ Malla de Inteligencia — Hitos Externos en vivo</b>
            <span style={{ color: "#64748b", fontSize: "0.62rem" }}>
              actualiza al segundo · Regla #34: sin RUT no hay hito · {feed.descartados || 0} descartado(s) por Regla de Hierro
            </span>
          </div>
          {(feed.hitos || []).length === 0 && <span style={{ color: "#94a3b8", fontSize: "0.7rem" }}>Sin hitos externos todavía. DashAI escucha las fuentes activas del Gestor.</span>}
          {(feed.hitos || []).slice(0, 6).map(h => (
            <div key={h.id} data-testid={`feed-hito-${h.id}`} style={{ display: "flex", gap: 8, flexWrap: "wrap", fontSize: "0.7rem", padding: "0.25rem 0", borderBottom: "1px solid rgba(148,163,184,0.08)" }}>
              <b style={{ color: h.hito?.includes("Reparo") ? "#ef4444" : "#22c55e" }}>{h.hito}</b>
              <span style={{ color: "#f8fafc" }}>{h.cliente}</span>
              <span style={{ color: "#94a3b8", fontFamily: "monospace" }}>{h.rut}</span>
              <span style={{ color: "#64748b" }}>{h.direccion === "enviado" ? "→" : "←"} {h.fuente}</span>
              <span style={{ color: "#64748b", marginLeft: "auto" }}>{(h.creado || "").slice(0, 16).replace("T", " ")}</span>
            </div>
          ))}
        </div>
      )}
      {(data?.alertas_notaria || 0) > 0 && (
        <div data-testid="gerencia-alerta-notaria" style={{ ...glass, borderColor: "#ef4444", color: "#fecaca", padding: "0.6rem 1rem", marginBottom: 12, fontSize: "0.78rem", fontWeight: 700 }}>
          🚨 {data.alertas_notaria} aviso(s) de notaría sobre firmas faltantes detectados por DashAI
        </div>
      )}
      {(data?.excepciones_recientes || []).length > 0 && (
        <div data-testid="gerencia-excepciones" style={{ ...glass, borderColor: "#f59e0b", color: "#fde68a", padding: "0.6rem 1rem", marginBottom: 12, fontSize: "0.72rem" }}>
          ⚠️ Excepciones autorizadas recientes: {data.excepciones_recientes.map(e => `${e.usuario} (${e.cliente || e.hito})`).join(" · ")}
        </div>
      )}

      <div style={{ ...glass, overflowX: "auto" }}>
        <table data-testid="gerencia-tabla" style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.78rem", color: "#e2e8f0" }}>
          <thead>
            <tr style={{ color: "#94a3b8", fontSize: "0.66rem", textTransform: "uppercase", letterSpacing: "0.08em" }}>
              {["Cliente", "Broker", "RUT", "Tipo", "Monto UF", "Subsidio", "Inmobiliaria", "Divergencia", "Docs", "Doc 2.0", "Firmas", "Fecha Firma", "Tasación", "Estudio", "Firma Set", "Concreces", "Notaría", "Mesa", "Acciones de Mando"].map(h =>
                <th key={h} style={{ padding: "0.7rem 0.8rem", textAlign: "left", borderBottom: "1px solid rgba(148,163,184,0.15)" }}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {cartera.map(f => (
              <tr key={f.folder_id} data-testid={`gerencia-fila-${f.folder_id}`}
                style={{ borderBottom: "1px solid rgba(148,163,184,0.08)",
                  background: f.datos_incompletos ? "rgba(239,68,68,0.12)" : (f.inactivo_96h ? "rgba(148,163,184,0.10)" : "transparent") }}>
                <td style={{ padding: "0.6rem 0.8rem", fontWeight: 700, color: "#f8fafc" }}>{f.cliente}
                  {f.datos_incompletos && <div data-testid={`broker-no-actualizado-${f.folder_id}`} style={{ color: "#ef4444", fontSize: "0.6rem", fontWeight: 800 }}>🔴 Broker no actualizado</div>}
                  {f.inactivo_96h && !f.datos_incompletos && <div style={{ color: "#94a3b8", fontSize: "0.58rem" }}>⏸ Sin actividad 96h</div>}
                  {f.alerta_notaria && <div style={{ color: "#fb7185", fontSize: "0.62rem", fontWeight: 600 }}>{f.alerta_notaria}</div>}
                </td>
                <td style={{ padding: "0.6rem 0.8rem", color: "#38bdf8", fontSize: "0.68rem" }}>{f.broker_origen || "DIRECTO"}</td>
                <td style={{ padding: "0.6rem 0.8rem", fontFamily: "monospace" }}>{f.rut || "—"}</td>
                <td style={{ padding: "0.6rem 0.8rem" }}>
                  {f.tipo_operacion
                    ? <span data-testid={`gerencia-tipo-${f.folder_id}`} style={{ fontSize: "0.6rem", fontWeight: 800, padding: "0.15rem 0.5rem", borderRadius: 6,
                        background: f.tipo_operacion === "USADA" ? "rgba(34,197,94,0.15)" : "rgba(56,189,248,0.15)",
                        color: f.tipo_operacion === "USADA" ? "#22c55e" : "#38bdf8" }}>{f.tipo_operacion}</span>
                    : "—"}
                </td>
                <td style={{ padding: "0.6rem 0.8rem" }}>{f.monto_credito_uf ? Number(f.monto_credito_uf).toLocaleString("es-CL") : "—"}</td>
                <td style={{ padding: "0.6rem 0.8rem" }}>{f.subsidio ? "Sí" : "No"}</td>
                <td style={{ padding: "0.6rem 0.8rem" }}>{f.inmobiliaria || "—"}</td>
                <td data-testid={`gerencia-divergencia-${f.folder_id}`} style={{ padding: "0.6rem 0.8rem", textAlign: "center" }}>
                  {f.divergencia_control
                    ? <span title="DashAI detectó diferencia entre Bodega e Ingreso Concreces (Regla #35)" style={{ color: "#f59e0b", fontSize: "0.6rem", fontWeight: 800 }}>⚠️ Inconsistencia con Control</span>
                    : <span style={{ color: "#22c55e", fontSize: "0.8rem" }}>✅</span>}
                </td>
                <td style={{ padding: "0.6rem 0.8rem", textAlign: "center" }}><Icono estado={f.documentacion} /></td>
                <td data-testid={`gerencia-doc20-${f.folder_id}`} style={{ padding: "0.6rem 0.8rem", textAlign: "center" }}>
                  <EstadoRadar estado={f.doc20?.estado} title={(f.doc20?.faltantes || []).length ? `Falta: ${f.doc20.faltantes.join(", ")}` : "AFP + Liquidación + CMF al día"} />
                </td>
                <td data-testid={`gerencia-firmas-${f.folder_id}`} style={{ padding: "0.6rem 0.8rem", textAlign: "center" }}>
                  <EstadoRadar estado={f.hito_firmas === "ok" ? "ok" : (f.hito_firmas === "proceso" ? "proceso" : "alerta")}
                    title={(f.firmas || []).map(x => `${x.label}: ${x.estado}`).join(" · ") || "Sin firmantes"} />
                  <div style={{ display: "flex", gap: 3, justifyContent: "center", marginTop: 3 }}>
                    {(f.firmas || []).map(x => (
                      <span key={x.rol} data-testid={`firma-${x.rol}-${f.folder_id}`}
                        title={`${x.label}: ${x.estado} (clic para cambiar)`}
                        onClick={() => marcarFirma(f.folder_id, x.rol, x.estado === "firmado" ? "pendiente" : "firmado")}
                        style={{ cursor: "pointer", fontSize: "0.56rem", fontWeight: 800, padding: "0.05rem 0.3rem", borderRadius: 4,
                          background: x.estado === "firmado" ? "rgba(34,197,94,0.2)" : "rgba(148,163,184,0.15)",
                          color: x.estado === "firmado" ? "#22c55e" : "#94a3b8" }}>
                        {x.label[0]}
                      </span>
                    ))}
                  </div>
                </td>
                <td data-testid={`gerencia-fecha-firma-${f.folder_id}`} style={{ padding: "0.6rem 0.4rem" }}>
                  <input type="date" defaultValue={f.fecha_firma || ""} onBlur={e => fecharFirma(f.folder_id, e.target.value)}
                    style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(148,163,184,0.25)", color: "#e2e8f0", borderRadius: 6, padding: "0.15rem 0.3rem", fontSize: "0.62rem", width: 110 }} />
                </td>
                <td data-testid={`gerencia-tasacion-${f.folder_id}`} style={{ padding: "0.6rem 0.8rem", textAlign: "center", fontSize: "0.6rem" }}>
                  {f.tasacion_estado === "pendiente_informacion"
                    ? <span style={{ color: "#94a3b8" }}>Pendiente de Información</span>
                    : <Icono estado={f.tasacion_estado} />}
                </td>
                <td data-testid={`gerencia-estudio-${f.folder_id}`} style={{ padding: "0.6rem 0.8rem", textAlign: "center", fontSize: "0.6rem" }}>
                  {f.estudio_estado === "pendiente_informacion"
                    ? <span style={{ color: "#94a3b8" }}>Pendiente de Información</span>
                    : <>
                        <Icono estado={f.estudio_estado} />
                        {f.reparos_pendientes > 0 && <div style={{ color: "#ef4444", fontWeight: 800 }}>{f.reparos_pendientes} reparo(s)</div>}
                      </>}
                </td>
                <td style={{ padding: "0.6rem 0.8rem", textAlign: "center" }}><Icono estado={f.firma_set} /></td>
                <td style={{ padding: "0.6rem 0.8rem", textAlign: "center" }}><Icono estado={f.ingreso_concreces} /></td>
                <td style={{ padding: "0.6rem 0.8rem", textAlign: "center" }}><Icono estado={f.notaria} /></td>
                <td style={{ padding: "0.6rem 0.8rem", fontSize: "0.68rem", color: "#94a3b8" }}>{f.estado_mesa || "—"}</td>
                <td style={{ padding: "0.6rem 0.6rem" }}>
                  <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                    {RECLAMOS_UI.filter(([, , cond]) => cond(f)).map(([tipo, label]) => {
                      const hecho = f.reclamos?.[tipo];
                      return (
                        <button key={tipo} data-testid={`reclamo-${tipo}-${f.folder_id}`}
                          className={`maserati-btn ${hecho ? "hecho" : (tipo === "movimiento" ? "neon" : "")}`}
                          disabled={busyRec === `${f.folder_id}-${tipo}`}
                          title={hecho ? `Ya solicitado por ${hecho.por} a ${hecho.destinatario}` : "El envío depende 100% de Gerencia (Regla #49)"}
                          onClick={() => reclamar(f.folder_id, tipo)}>
                          {busyRec === `${f.folder_id}-${tipo}` ? "Enviando…"
                            : hecho ? `✓ Solicitado el ${(hecho.fecha || "").slice(0, 10)}` : label}
                        </button>
                      );
                    })}
                    {RECLAMOS_UI.every(([, , cond]) => !cond(f)) && <span style={{ color: "#22c55e", fontSize: "0.62rem" }}>Sin gestiones pendientes</span>}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!data && <p style={{ color: "#94a3b8", textAlign: "center", padding: "2rem" }}>Cargando cartera…</p>}
        {data && cartera.length === 0 && <p style={{ color: "#94a3b8", textAlign: "center", padding: "2rem" }}>Sin operaciones con los filtros aplicados.</p>}
      </div>
      <p data-testid="costo-desarrollo" style={{ color: "#64748b", fontSize: "0.68rem", marginTop: 12 }}>
        ⚡ Costo de Desarrollo del mes: <b style={{ color: "#d4af37" }}>{data?.costo_desarrollo_creditos ?? 0} créditos</b> (estimado por consumo real de IA — Ley de Eficiencia #23)
        · Cada clic queda en el Log de Gestión Gerencial (Regla #52)
      </p>
    </div>
  );
}
