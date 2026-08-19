import { useEffect, useMemo, useState } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const oro = "#d4af37";
const card = { background: "rgba(15,23,42,0.72)", border: "1px solid rgba(212,175,55,0.22)",
  borderRadius: 14, padding: "1.1rem 1.3rem", boxShadow: "0 6px 22px rgba(0,0,0,0.35)" };
const h2 = { color: "#e2e8f0", fontSize: "0.82rem", fontWeight: 900, letterSpacing: 1.6,
  textTransform: "uppercase", margin: "0 0 10px" };
const clp = (n) => "$" + Math.round(n || 0).toLocaleString("es-CL");
const Tend = ({ v, sufijo = "" }) => (v === null || v === undefined) ? null : (
  <span style={{ fontSize: "0.7rem", fontWeight: 900, color: v > 0 ? "#4ade80" : v < 0 ? "#f87171" : "#94a3b8" }}>
    {v > 0 ? "▲" : v < 0 ? "▼" : "◆"} {Math.abs(v)}{sufijo} vs mes anterior
  </span>
);

const Metrica = ({ id, titulo, valor, sub, tend, tendSuf, color = "#f8fafc" }) => (
  <div data-testid={`cc-metrica-${id}`} style={{ ...card, flex: "1 1 220px", minWidth: 210 }}>
    <div style={{ color: "#94a3b8", fontSize: "0.62rem", fontWeight: 800, letterSpacing: 1.4 }}>{titulo}</div>
    <div style={{ color, fontSize: "1.9rem", fontWeight: 900, lineHeight: 1.15, margin: "4px 0 2px" }}>{valor}</div>
    {sub && <div style={{ color: "#94a3b8", fontSize: "0.68rem" }}>{sub}</div>}
    <Tend v={tend} sufijo={tendSuf} />
  </div>
);

const SEMAF = { verde: "#22c55e", amarillo: "#facc15", rojo: "#ef4444" };

export default function GerenciaCommandCenter({ onNavigate }) {
  const [d, setD] = useState(null);
  const [ccOpts, setCcOpts] = useState([]);
  const [ccSel, setCcSel] = useState([]);
  const [orden, setOrden] = useState({ col: "cerradas_mes", asc: false });
  const [busy, setBusy] = useState("");

  const cargar = () => {
    axios.get(`${API}/api/gerencia-panel/command-center`).then(r => setD(r.data)).catch(() => setD({ error: true }));
  };
  useEffect(() => {
    cargar();
    axios.get(`${API}/api/gerencia-panel/cc-opciones`).then(r => setCcOpts(r.data.opciones || [])).catch(() => {});
  }, []);

  const brokersOrd = useMemo(() => {
    const arr = [...(d?.brokers || [])];
    arr.sort((a, b) => {
      const va = a[orden.col] ?? -1, vb = b[orden.col] ?? -1;
      const cmp = typeof va === "string" ? String(va).localeCompare(String(vb)) : va - vb;
      return orden.asc ? cmp : -cmp;
    });
    return arr;
  }, [d, orden]);

  const setCol = (col) => setOrden(o => ({ col, asc: o.col === col ? !o.asc : false }));
  const toggleCc = (em) => setCcSel(s => (s.includes(em) ? s.filter(x => x !== em) : [...s, em]));

  const enviarCorreo = async (op) => {
    const ccTxt = ccSel.length ? `\nCon copia (CC) a: ${ccSel.join(", ")}` : "\nSin copias (CC) seleccionadas";
    if (!window.confirm(`Enviar solicitud de estado y seguimiento para ${op.cliente}.${ccTxt}\n¿Confirmar el envío?`)) return;
    setBusy(op.fid);
    try {
      const r = await axios.post(`${API}/api/gerencia-panel/accion`, { fid: op.fid, tipo: "seguimiento", cc: ccSel });
      window.alert(`Solicitud enviada a ${r.data.para}. ${r.data.nota}`);
    } catch (e) { window.alert(e.response?.data?.detail || "No fue posible enviar la solicitud. Intente nuevamente."); }
    setBusy("");
  };

  const marcarUrgente = async (op) => {
    try {
      await axios.post(`${API}/api/gerencia-panel/urgente`, { fid: op.fid });
      cargar();
    } catch (e) { window.alert(e.response?.data?.detail || "No fue posible actualizar la marca de urgencia."); }
  };

  const registrarCumple = async (op) => {
    const f = window.prompt(`Fecha de nacimiento de ${op.cliente} (DD/MM/AAAA):`, "");
    if (!f || !f.trim()) return;
    try {
      const r = await axios.post(`${API}/api/gerencia-panel/fecha-nacimiento`, { fid: op.fid, fecha: f.trim() });
      window.alert(`Fecha de nacimiento registrada: ${r.data.fecha_nacimiento}`);
      cargar();
    } catch (e) { window.alert(e.response?.data?.detail || "No fue posible registrar la fecha."); }
  };

  if (!d) return <p style={{ color: "#94a3b8", padding: "2rem" }}>Cargando panel de control…</p>;
  if (d.error) return <p style={{ color: "#f87171", padding: "2rem" }}>No fue posible cargar el panel. Actualice la página o verifique su sesión.</p>;

  const z = d.zona1 || {};
  const maxSerie = Math.max(...(d.serie_mensual || []).map(x => x[1]), 1);
  const COLS = [["broker", "Broker"], ["clientes", "Clientes activos"], ["tramitacion", "En tramitación"],
    ["cerradas_mes", "Cerradas este mes"], ["monto_uf", "Monto UF"], ["tasa_cierre", "Tasa cierre"],
    ["dias_respuesta", "Días de respuesta"], ["semaforo", "Estado"]];

  return (
    <div data-testid="gerencia-command-center" style={{ display: "grid", gap: 18 }}>
      {/* ══ ZONA 1 — COMMAND CENTER ══ */}
      <div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 10 }}>
          <h3 style={{ ...h2, margin: 0, color: oro }}>Command Center — {d.mes}</h3>
          <span style={{ color: "#64748b", fontSize: "0.64rem" }}>Datos reales del sistema · UF del día {clp(z.monto_tramitacion?.valor_uf_dia)}</span>
        </div>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <Metrica id="activas" titulo="OPERACIONES ACTIVAS" valor={z.operaciones_activas?.valor ?? 0}
            sub={`${z.operaciones_activas?.nuevas_mes ?? 0} ingresadas este mes`}
            tend={z.operaciones_activas?.tendencia} tendSuf=" op." />
          <Metrica id="monto" titulo="MONTO EN TRAMITACIÓN" color={oro}
            valor={`UF ${(z.monto_tramitacion?.uf ?? 0).toLocaleString("es-CL")}`}
            sub={`${clp(z.monto_tramitacion?.clp)} CLP`} />
          <Metrica id="tasa" titulo="TASA DE CIERRE DEL MES"
            valor={`${z.tasa_cierre?.mes_actual ?? 0}%`}
            sub={`${z.tasa_cierre?.cierres_mes ?? 0} cierre(s) · mes anterior ${z.tasa_cierre?.mes_anterior ?? 0}%`}
            tend={z.tasa_cierre?.tendencia} tendSuf=" pts" />
          <Metrica id="cierre-dias" titulo="TIEMPO PROMEDIO DE CIERRE"
            valor={z.tiempo_promedio_cierre_dias !== null && z.tiempo_promedio_cierre_dias !== undefined
              ? `${z.tiempo_promedio_cierre_dias} días` : "No disponible"}
            sub="desde el ingreso hasta escritura confirmada" />
          <Metrica id="bloqueadas" titulo="BLOQUEADAS POR NORMATIVA" color="#f87171"
            valor={z.bloqueadas_normativa?.n ?? 0}
            sub={`${z.bloqueadas_normativa?.pct ?? 0}% del total activo · documentación incompleta`} />
          <Metrica id="sin-clasificar" titulo="DOCS SIN CLASIFICAR" color="#facc15"
            valor={z.docs_sin_clasificar ?? 0} sub="pendientes de asignación en bandeja" />
        </div>
        {/* Mini gráfico de tendencia mensual */}
        <div style={{ ...card, marginTop: 12, display: "flex", alignItems: "flex-end", gap: 14 }}>
          <div style={{ color: "#94a3b8", fontSize: "0.62rem", fontWeight: 800, letterSpacing: 1.2, alignSelf: "flex-start" }}>
            OPERACIONES INGRESADAS<br />POR MES (6 MESES)</div>
          <div data-testid="cc-grafico-mensual" style={{ display: "flex", gap: 18, alignItems: "flex-end", height: 74, flex: 1 }}>
            {(d.serie_mensual || []).map(([m, n]) => (
              <div key={m} style={{ textAlign: "center" }}>
                <div style={{ color: "#e2e8f0", fontSize: "0.66rem", fontWeight: 800 }}>{n}</div>
                <div style={{ width: 34, height: Math.max(6, (n / maxSerie) * 48), margin: "2px auto",
                  background: `linear-gradient(180deg, ${oro}, #8a6d1f)`, borderRadius: 4 }} />
                <div style={{ color: "#64748b", fontSize: "0.58rem", fontFamily: "monospace" }}>{m.slice(5)}/{m.slice(2, 4)}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ══ CUMPLEAÑOS DE LA SEMANA ══ */}
      {(d.cumpleanos_semana || []).length > 0 && (
        <div data-testid="cc-cumpleanos" style={{ ...card, borderColor: "rgba(212,175,55,0.5)" }}>
          <h3 style={{ ...h2, color: oro, margin: "0 0 8px" }}>🎂 Cumpleaños de Clientes — Próximos 7 días</h3>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {d.cumpleanos_semana.map(c => (
              <div key={c.fid} data-testid={`cc-cumple-${c.fid}`} style={{ background: "rgba(2,6,23,0.5)",
                border: "1px solid rgba(212,175,55,0.35)", borderRadius: 10, padding: "0.6rem 1rem" }}>
                <b style={{ color: "#f8fafc", fontSize: "0.82rem" }}>{c.cliente}</b>
                <div style={{ color: oro, fontSize: "0.7rem", fontWeight: 800 }}>
                  {c.dias === 0 ? "¡HOY!" : `en ${c.dias} día(s)`} · {c.fecha}</div>
                {c.broker && <div style={{ color: "#64748b", fontSize: "0.62rem" }}>{c.broker}</div>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ══ ZONA 2 — RENDIMIENTO POR BROKER ══ */}
      <div style={card} data-testid="cc-zona-brokers">
        <h3 style={h2}>Rendimiento por Broker</h3>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
            <thead>
              <tr>
                {COLS.map(([k, lb]) => (
                  <th key={k} onClick={() => setCol(k)} data-testid={`cc-orden-${k}`}
                    style={{ color: orden.col === k ? oro : "#94a3b8", textAlign: "left", cursor: "pointer",
                      padding: "8px 10px", fontSize: "0.66rem", letterSpacing: 0.8, userSelect: "none", whiteSpace: "nowrap" }}>
                    {lb} {orden.col === k ? (orden.asc ? "↑" : "↓") : "↕"}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {brokersOrd.map(b => (
                <tr key={b.broker} data-testid={`cc-broker-${b.broker}`}
                  style={{ borderTop: "1px solid rgba(148,163,184,0.14)",
                    background: b.mejor_mes ? "rgba(212,175,55,0.10)" : "transparent" }}>
                  <td style={{ padding: "11px 10px", color: b.mejor_mes ? oro : "#f8fafc", fontWeight: 800 }}>
                    {b.mejor_mes && <span title="Mejor rendimiento del mes" style={{ marginRight: 6 }}>🏆</span>}{b.broker}</td>
                  <td style={{ color: "#e2e8f0" }}>{b.clientes}</td>
                  <td style={{ color: "#e2e8f0" }}>{b.tramitacion}</td>
                  <td style={{ color: b.cerradas_mes > 0 ? "#4ade80" : "#94a3b8", fontWeight: 800 }}>{b.cerradas_mes}</td>
                  <td style={{ color: oro, fontWeight: 700 }}>{b.monto_uf ? `UF ${b.monto_uf.toLocaleString("es-CL")}` : "No disponible"}</td>
                  <td style={{ color: "#e2e8f0" }}>{b.tasa_cierre}%</td>
                  <td style={{ color: "#e2e8f0" }}>{b.dias_respuesta ?? "No disponible"}</td>
                  <td><span style={{ display: "inline-block", width: 12, height: 12, borderRadius: "50%",
                    background: SEMAF[b.semaforo] || "#64748b", boxShadow: `0 0 8px ${SEMAF[b.semaforo] || "#64748b"}` }}
                    title={`Estado: ${b.semaforo}`} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ══ ZONA 3 — CARGA ADMINISTRATIVA ══ */}
      <div style={{ ...card, borderColor: "rgba(96,165,250,0.4)", background: "linear-gradient(135deg, rgba(12,26,48,0.9), rgba(15,23,42,0.85))" }}
        data-testid="cc-zona-carga">
        <h3 style={{ ...h2, color: "#93c5fd" }}>Carga Administrativa del Mes — Daniela y Victoria</h3>
        <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
          {Object.entries(d.carga_administrativa || {}).map(([nombre, c]) => (
            <div key={nombre} data-testid={`cc-carga-${nombre.split(" ")[0].toLowerCase()}`}
              style={{ flex: "1 1 340px", background: "rgba(2,6,23,0.55)", borderRadius: 12,
                border: "1px solid rgba(96,165,250,0.28)", padding: "1rem 1.2rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <b style={{ color: "#f8fafc", fontSize: "1rem" }}>{nombre}</b>
                <span style={{ marginLeft: "auto", fontSize: "0.66rem", fontWeight: 900, padding: "3px 12px", borderRadius: 999,
                  background: c.indicador_carga === "Alta" ? "rgba(239,68,68,0.18)" : c.indicador_carga === "Media" ? "rgba(250,204,21,0.15)" : "rgba(34,197,94,0.15)",
                  color: c.indicador_carga === "Alta" ? "#f87171" : c.indicador_carga === "Media" ? "#facc15" : "#4ade80",
                  border: `1px solid ${c.indicador_carga === "Alta" ? "#ef4444" : c.indicador_carga === "Media" ? "#facc15" : "#22c55e"}` }}>
                  CARGA {c.indicador_carga.toUpperCase()}</span>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 12 }}>
                {[["Documentos procesados", c.documentos_procesados], ["Correos gestionados", c.correos_gestionados],
                  ["Operaciones tramitadas", c.operaciones_tramitadas],
                  ["Horas prom. resolución", c.horas_promedio_resolucion ?? "No disponible"]].map(([lb, v]) => (
                  <div key={lb}>
                    <div style={{ color: "#93c5fd", fontSize: "1.35rem", fontWeight: 900 }}>{v}</div>
                    <div style={{ color: "#94a3b8", fontSize: "0.62rem", letterSpacing: 0.6 }}>{lb.toUpperCase()}</div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ══ ZONA 4 — BANDEJA DE GESTIÓN ══ */}
      <div style={card} data-testid="cc-zona-bandeja">
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <h3 style={{ ...h2, margin: 0 }}>Bandeja de Gestión — Operaciones Activas ({(d.bandeja || []).length})</h3>
          <span style={{ color: "#64748b", fontSize: "0.62rem" }}>Alerta automática sobre 5 días hábiles sin movimiento</span>
        </div>
        {/* Selector CC para los correos de acción */}
        <div data-testid="gerencia-cc-selector" style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center",
          margin: "10px 0", background: "rgba(2,6,23,0.5)", border: "1px dashed rgba(96,165,250,0.35)",
          borderRadius: 8, padding: "0.5rem 0.7rem" }}>
          <span style={{ color: "#93c5fd", fontSize: "0.68rem", fontWeight: 800 }}>Con copia (CC) en los correos:</span>
          {ccOpts.map(o => (
            <button key={o.email} data-testid={`cc-chip-${o.email}`} onClick={() => toggleCc(o.email)} title={o.email}
              style={{ fontSize: "0.64rem", fontWeight: 800, borderRadius: 999, padding: "3px 10px", cursor: "pointer",
                background: ccSel.includes(o.email) ? "rgba(96,165,250,0.25)" : "transparent",
                color: ccSel.includes(o.email) ? "#dbeafe" : "#94a3b8",
                border: `1px solid ${ccSel.includes(o.email) ? "#60a5fa" : "rgba(148,163,184,0.35)"}` }}>
              {ccSel.includes(o.email) ? "✓ " : ""}{o.nombre}</button>
          ))}
        </div>
        <div style={{ display: "grid", gap: 8, maxHeight: 520, overflowY: "auto" }}>
          {(d.bandeja || []).map(op => (
            <div key={op.fid} data-testid={`cc-op-${op.fid}`}
              style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap",
                background: op.urgente ? "rgba(239,68,68,0.10)" : "rgba(2,6,23,0.5)",
                border: `1px solid ${op.urgente ? "rgba(239,68,68,0.55)" : op.alerta ? "rgba(250,204,21,0.4)" : "rgba(148,163,184,0.18)"}`,
                borderRadius: 10, padding: "0.65rem 0.9rem" }}>
              <div style={{ minWidth: 220 }}>
                <b style={{ color: "#f8fafc", fontSize: "0.85rem" }}>
                  {op.urgente && <span title="Marcada urgente" style={{ color: "#f87171", marginRight: 5 }}>⚑</span>}{op.cliente}</b>
                <div style={{ color: "#64748b", fontSize: "0.66rem", fontFamily: "monospace" }}>{op.rut || "RUT no disponible"}</div>
              </div>
              <div style={{ color: "#94a3b8", fontSize: "0.7rem", minWidth: 120 }}>
                <div style={{ color: "#cbd5e1", fontWeight: 700 }}>{op.broker}</div>BROKER</div>
              <div style={{ color: "#94a3b8", fontSize: "0.7rem", minWidth: 110 }}>
                <div style={{ color: oro, fontWeight: 700 }}>{op.tipo}</div>TIPO</div>
              <div style={{ color: "#94a3b8", fontSize: "0.7rem", minWidth: 170 }}>
                <div style={{ color: op.estado.startsWith("Bloqueada") ? "#f87171" : "#cbd5e1", fontWeight: 700 }}>{op.estado}</div>ESTADO</div>
              <div style={{ color: "#94a3b8", fontSize: "0.7rem", minWidth: 130 }}>
                <div style={{ color: "#cbd5e1", fontWeight: 700 }}>
                  {op.ultimo_movimiento !== "No disponible"
                    ? `${op.ultimo_movimiento.slice(8, 10)}/${op.ultimo_movimiento.slice(5, 7)}/${op.ultimo_movimiento.slice(0, 4)}`
                    : "No disponible"}</div>ÚLTIMO MOVIMIENTO</div>
              {op.alerta && (
                <span data-testid={`cc-alerta-${op.fid}`} style={{ color: "#facc15", fontSize: "0.66rem", fontWeight: 900 }}>
                  ⚠ {op.dias_sin_movimiento} días hábiles sin movimiento</span>
              )}
              <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
                <button data-testid={`cc-correo-${op.fid}`} onClick={() => enviarCorreo(op)} disabled={busy === op.fid}
                  style={{ background: "rgba(96,165,250,0.15)", color: "#93c5fd", border: "1px solid rgba(96,165,250,0.45)",
                    borderRadius: 7, padding: "0.32rem 0.7rem", fontWeight: 800, cursor: "pointer", fontSize: "0.66rem" }}>
                  ✉ Enviar correo</button>
                <button data-testid={`cc-carpeta-${op.fid}`} onClick={() => onNavigate && onNavigate("supercarpeta")}
                  style={{ background: "rgba(212,175,55,0.12)", color: oro, border: "1px solid rgba(212,175,55,0.45)",
                    borderRadius: 7, padding: "0.32rem 0.7rem", fontWeight: 800, cursor: "pointer", fontSize: "0.66rem" }}>
                  📁 Ver carpeta</button>
                <button data-testid={`cc-urgente-${op.fid}`} onClick={() => marcarUrgente(op)}
                  style={{ background: op.urgente ? "rgba(239,68,68,0.2)" : "rgba(239,68,68,0.08)", color: "#f87171",
                    border: "1px solid rgba(239,68,68,0.5)", borderRadius: 7, padding: "0.32rem 0.7rem",
                    fontWeight: 800, cursor: "pointer", fontSize: "0.66rem" }}>
                  ⚑ {op.urgente ? "Quitar urgencia" : "Marcar urgente"}</button>
                <button data-testid={`cc-cumple-btn-${op.fid}`} onClick={() => registrarCumple(op)}
                  title="Registrar fecha de nacimiento para alertas de cumpleaños"
                  style={{ background: "rgba(212,175,55,0.08)", color: oro, border: "1px solid rgba(212,175,55,0.35)",
                    borderRadius: 7, padding: "0.32rem 0.55rem", fontWeight: 800, cursor: "pointer", fontSize: "0.66rem" }}>
                  🎂</button>
              </div>
            </div>
          ))}
          {(d.bandeja || []).length === 0 && (
            <p style={{ color: "#64748b", fontSize: "0.76rem", fontStyle: "italic" }}>No hay operaciones activas en la bandeja.</p>
          )}
        </div>
      </div>
      <PanelComercial />
    </div>
  );
}

// ═══ VISIÓN GERENCIAL: BROKERS INTERNOS · RANKING · PROYECCIÓN VS REAL · EJECUTIVOS ═══
const Ratio = ({ v }) => v === null || v === undefined
  ? <span style={{ color: "#64748b", fontSize: "0.7rem" }}>sin proyección</span>
  : <span style={{ fontWeight: 900, fontSize: "1.05rem",
      color: v >= 100 ? "#22c55e" : v >= 60 ? "#facc15" : "#ef4444" }}>{v}%</span>;

const BrokerCard = ({ b, interno }) => (
  <div data-testid={`gc-broker-${b.codigo}`} style={{ ...card, flex: "1 1 300px", minWidth: 280,
    borderColor: interno ? "rgba(212,175,55,0.5)" : "rgba(148,163,184,0.25)" }}>
    <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
      <b style={{ color: "#f8fafc", fontSize: "0.9rem" }}>{b.nombre}</b>
      <span style={{ fontSize: "0.56rem", fontWeight: 900, letterSpacing: 1, borderRadius: 5,
        padding: "0.1rem 0.45rem", color: interno ? "#0a0a0a" : "#94a3b8",
        background: interno ? oro : "rgba(148,163,184,0.15)" }}>{interno ? "INTERNO" : "EXTERNO"}</span>
    </div>
    <div style={{ display: "flex", gap: 16, marginTop: 8, flexWrap: "wrap" }}>
      <div><div style={{ color: "#94a3b8", fontSize: "0.58rem", fontWeight: 800 }}>ACTIVAS</div>
        <div style={{ color: "#f8fafc", fontSize: "1.5rem", fontWeight: 900 }}>{b.activas}</div></div>
      <div><div style={{ color: "#94a3b8", fontSize: "0.58rem", fontWeight: 800 }}>CERRADAS</div>
        <div style={{ color: "#22c55e", fontSize: "1.5rem", fontWeight: 900 }}>{b.cerradas}</div></div>
      <div><div style={{ color: "#94a3b8", fontSize: "0.58rem", fontWeight: 800 }}>MONTO UF</div>
        <div style={{ color: oro, fontSize: "1.5rem", fontWeight: 900 }}>{Math.round(b.monto_uf).toLocaleString("es-CL")}</div></div>
      <div><div style={{ color: "#94a3b8", fontSize: "0.58rem", fontWeight: 800 }}>CUMPLIMIENTO</div>
        <div><Ratio v={b.ratio_cumplimiento} /></div>
        <div style={{ color: "#64748b", fontSize: "0.56rem" }}>{b.operaciones_nuevas_mes} real / {b.proyecciones_mes} proy.</div></div>
    </div>
    <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
      {[["Ingreso", b.etapas.ingreso, "#94a3b8"], ["Evaluación", b.etapas.evaluacion, "#facc15"],
        ["Escrituración", b.etapas.escrituracion, "#22c55e"]].map(([lb, n, col]) => (
        <span key={lb} style={{ fontSize: "0.62rem", fontWeight: 800, color: col,
          border: `1px solid ${col}44`, borderRadius: 999, padding: "2px 9px" }}>{lb}: {n}</span>))}
      {b.en_riesgo > 0 && <span style={{ fontSize: "0.62rem", fontWeight: 900, color: "#facc15",
        border: "1px solid #facc1566", borderRadius: 999, padding: "2px 9px" }}>⚠ {b.en_riesgo} en riesgo</span>}
      {b.atrasadas > 0 && <span style={{ fontSize: "0.62rem", fontWeight: 900, color: "#ef4444",
        border: "1px solid #ef444466", borderRadius: 999, padding: "2px 9px" }}>🚨 {b.atrasadas} atrasadas</span>}
    </div>
  </div>
);

export function PanelComercial() {
  const [p, setP] = useState(null);
  const [vista, setVista] = useState("general");
  useEffect(() => {
    axios.get(`${API}/api/gerencia-comercial/panel`).then(r => setP(r.data)).catch(() => {});
  }, []);
  if (!p) return null;
  const todos = [...p.brokers_internos, ...p.brokers_externos];
  const sel = vista === "general" ? null : todos.find(b => b.codigo === vista);
  return (
    <div data-testid="gc-panel-comercial" style={{ display: "flex", flexDirection: "column", gap: 14, marginTop: 4 }}>
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <h2 style={{ ...h2, margin: 0 }}>👑 Visión Comercial</h2>
        <select data-testid="gc-vista-selector" value={vista} onChange={e => setVista(e.target.value)}
          style={{ background: "#0f172a", color: "#f8fafc", border: "1px solid rgba(212,175,55,0.4)",
            borderRadius: 8, padding: "0.35rem 0.7rem", fontSize: "0.74rem", fontWeight: 700 }}>
          <option value="general">Vista general — todas las operaciones</option>
          <optgroup label="Brokers Internos">
            {p.brokers_internos.map(b => <option key={b.codigo} value={b.codigo}>{b.nombre}</option>)}
          </optgroup>
          <optgroup label="Brokers Externos">
            {p.brokers_externos.map(b => <option key={b.codigo} value={b.codigo}>{b.nombre}</option>)}
          </optgroup>
        </select>
      </div>
      {sel ? (
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }} data-testid="gc-vista-particular">
          <BrokerCard b={sel} interno={p.brokers_internos.some(b => b.codigo === sel.codigo)} />
          <div style={{ ...card, flex: "1 1 240px" }}>
            <h2 style={h2}>Posición en ranking</h2>
            <div style={{ color: oro, fontSize: "2.4rem", fontWeight: 900 }}>
              #{p.ranking.findIndex(r => r.codigo === sel.codigo) + 1 || "—"}</div>
            <div style={{ color: "#94a3b8", fontSize: "0.68rem" }}>
              de {p.ranking.length} brokers del período · {sel.proyecciones_total} proyecciones históricas</div>
          </div>
        </div>
      ) : (
      <>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <Metrica id="gc-riesgo" titulo="OPERACIONES EN RIESGO" valor={p.kpis.en_riesgo} color="#facc15"
          sub="7-14 días sin movimiento" />
        <Metrica id="gc-atrasadas" titulo="OPERACIONES ATRASADAS" valor={p.kpis.atrasadas} color="#ef4444"
          sub="+14 días sin movimiento" />
        <Metrica id="gc-cerradas" titulo="CERRADAS EXITOSAMENTE" valor={p.kpis.cerradas_exitosas} color="#22c55e"
          sub="en escrituración" />
        <Metrica id="gc-monto" titulo="MONTO GESTIONADO (UF)" valor={Math.round(p.kpis.monto_total_uf).toLocaleString("es-CL")}
          color={oro} sub={`período ${p.mes}`} />
      </div>
      <div style={card} data-testid="gc-brokers-internos">
        <h2 style={h2}>👑 Brokers Internos</h2>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          {p.brokers_internos.map(b => <BrokerCard key={b.codigo} b={b} interno />)}
        </div>
      </div>
      <div style={card} data-testid="gc-brokers-externos">
        <h2 style={h2}>🌐 Brokers Externos</h2>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          {p.brokers_externos.length === 0 && <p style={{ color: "#64748b", fontSize: "0.74rem" }}>Sin brokers externos registrados.</p>}
          {p.brokers_externos.map(b => <BrokerCard key={b.codigo} b={b} />)}
        </div>
      </div>
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
        <div style={{ ...card, flex: "2 1 420px" }} data-testid="gc-ranking">
          <h2 style={h2}>🏆 Ranking de Brokers — volumen y monto</h2>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.76rem" }}>
            <thead><tr style={{ color: "#94a3b8", textAlign: "left" }}>
              <th style={{ padding: "4px 6px" }}>#</th><th>Broker</th><th>Operaciones</th><th>Monto UF</th><th>Cumplimiento</th></tr></thead>
            <tbody>{p.ranking.map((b, i) => (
              <tr key={b.codigo} style={{ borderTop: "1px solid rgba(148,163,184,0.12)", color: "#e2e8f0" }}>
                <td style={{ padding: "5px 6px", color: i < 3 ? oro : "#64748b", fontWeight: 900 }}>{i + 1}</td>
                <td style={{ fontWeight: 800 }}>{b.nombre}</td>
                <td>{b.operaciones}</td>
                <td style={{ color: oro, fontWeight: 800 }}>{Math.round(b.monto_uf).toLocaleString("es-CL")}</td>
                <td><Ratio v={b.ratio_cumplimiento} /></td>
              </tr>))}
            </tbody>
          </table>
        </div>
        <div style={{ ...card, flex: "1 1 300px" }} data-testid="gc-ejecutivos">
          <h2 style={h2}>🧭 Panel Ejecutivo</h2>
          {p.ejecutivos.map(e => (
            <div key={e.nombre} style={{ borderTop: "1px solid rgba(148,163,184,0.1)", padding: "6px 0" }}>
              <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
                <b style={{ color: "#f8fafc", fontSize: "0.8rem" }}>{e.nombre}</b>
                <span style={{ color: "#94a3b8", fontSize: "0.6rem", textTransform: "uppercase" }}>{e.rol}</span>
                <span style={{ marginLeft: "auto", color: oro, fontWeight: 900 }}>{e.ratio_avance}%</span>
              </div>
              <div style={{ color: "#94a3b8", fontSize: "0.64rem" }}>
                {e.ops_activas} activas · {e.completadas} completadas · aporte {e.aporte_pct}% del objetivo</div>
              <div style={{ height: 5, background: "rgba(148,163,184,0.15)", borderRadius: 4, marginTop: 3 }}>
                <div style={{ width: `${e.ratio_avance}%`, height: "100%", borderRadius: 4,
                  background: `linear-gradient(90deg,#8a6d1a,${oro})` }} /></div>
            </div>
          ))}
        </div>
      </div>
      </>
      )}
    </div>
  );
}
