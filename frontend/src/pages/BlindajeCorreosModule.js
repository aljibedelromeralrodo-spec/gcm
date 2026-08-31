import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const ORO = "#d4af37";

const PROTO_COLOR = {
  dependiente_simple: "#60a5fa", mixto: "#c084fc", con_codeudor: "#fb923c",
  con_licencia_medica: "#f87171", independiente: "#4ade80",
};
const ESTADO_COLOR = {
  enviado: "#4ade80", autorizado: "#fbbf24", error: "#f87171",
  rebotado: "#dc2626", pendiente_autorizacion: "#9ca3af", rechazado: "#6b7280",
};

const panel = { background: "rgba(20,20,24,0.92)", border: "1px solid rgba(212,175,55,0.25)",
  borderRadius: 14, padding: "1.1rem 1.3rem", marginBottom: "1rem" };

const Kpi = ({ icono, valor, label, color }) => (
  <div style={{ ...panel, flex: "1 1 150px", marginBottom: 0, textAlign: "center", padding: "0.9rem" }}>
    <div style={{ fontSize: "1.5rem" }}>{icono}</div>
    <div style={{ fontSize: "1.6rem", fontWeight: 900, color: color || ORO }}>{valor}</div>
    <div style={{ fontSize: "0.62rem", color: "#9ca3af", letterSpacing: "0.08em", textTransform: "uppercase" }}>{label}</div>
  </div>
);

const BarraLiq = ({ tiene, total = 6 }) => {
  const color = tiene >= total ? "#4ade80" : tiene >= 3 ? "#fbbf24" : "#f87171";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ display: "flex", gap: 2 }}>
        {Array.from({ length: total }).map((_, i) => (
          <div key={i} style={{ width: 16, height: 9, borderRadius: 2,
            background: i < tiene ? color : "rgba(255,255,255,0.12)" }} />
        ))}
      </div>
      <span style={{ fontSize: "0.72rem", fontWeight: 800, color }}>{tiene}/{total} liquidaciones</span>
    </div>
  );
};

export default function BlindajeCorreosModule() {
  const [tab, setTab] = useState("autorizar");
  const [data, setData] = useState(null);
  const [dash, setDash] = useState(null);
  const [msg, setMsg] = useState("");
  const [exp, setExp] = useState(null);
  const [edit, setEdit] = useState(null);
  const [original, setOriginal] = useState(null);
  const [carpeta, setCarpeta] = useState(null);
  const [busy, setBusy] = useState("");
  const [procesando, setProcesando] = useState(false);

  const load = useCallback(async () => {
    try {
      const [a, d] = await Promise.all([
        axios.get(`${API}/api/blindaje/autorizaciones`),
        axios.get(`${API}/api/blindaje/dashboard`),
      ]);
      setData(a.data); setDash(d.data);
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, [load]);

  const accion = async (aid, tipo, payload) => {
    setBusy(aid);
    try {
      await axios.post(`${API}/api/blindaje/autorizaciones/${aid}/${tipo}`, payload || {});
      setMsg(tipo === "autorizar" ? "✅ Correo autorizado y enviado desde gerardo.ext@centralmutuos.cl" : "Correo rechazado");
      setEdit(null); load();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setBusy("");
  };

  const verOriginal = async (aid) => {
    const r = await axios.get(`${API}/api/blindaje/autorizaciones/${aid}/correo-original`);
    setOriginal(r.data.correo);
  };
  const verCarpeta = async (casoId) => {
    const r = await axios.get(`${API}/api/blindaje/casos/${casoId}/carpeta`);
    setCarpeta(r.data.documentos || []);
  };
  const procesarAhora = async () => {
    setProcesando(true);
    try {
      const r = await axios.post(`${API}/api/blindaje/procesar-ahora`);
      setMsg(`Revisados ${r.data.total_revisados} correos · ${r.data.procesados.length} procesados`);
      load();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setProcesando(false);
  };

  const k = data?.kpis || {};
  const dk = dash?.kpis || {};

  return (
    <div data-testid="blindaje-module" style={{ padding: "0.4rem 0" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: "1rem", flexWrap: "wrap" }}>
        <h2 style={{ color: ORO, margin: 0, fontSize: "1.15rem" }}>🛡️ Blindaje de Correos V16</h2>
        <button data-testid="tab-autorizar" onClick={() => setTab("autorizar")}
          style={{ background: tab === "autorizar" ? "rgba(212,175,55,0.2)" : "transparent",
            border: `1px solid ${ORO}55`, color: ORO, padding: "0.35rem 1rem", cursor: "pointer",
            borderRadius: 8, fontSize: "0.72rem", fontWeight: 800 }}>
          ✅ Autorizar Correos {k.pendientes_total > 0 && `(${k.pendientes_total})`}
        </button>
        <button data-testid="tab-dashboard" onClick={() => setTab("dashboard")}
          style={{ background: tab === "dashboard" ? "rgba(212,175,55,0.2)" : "transparent",
            border: `1px solid ${ORO}55`, color: ORO, padding: "0.35rem 1rem", cursor: "pointer",
            borderRadius: 8, fontSize: "0.72rem", fontWeight: 800 }}>📊 Dashboard Blindaje</button>
        <button data-testid="btn-procesar-ahora" onClick={procesarAhora} disabled={procesando}
          style={{ marginLeft: "auto", background: "transparent", border: "1px solid rgba(255,255,255,0.2)",
            color: "#e2e8f0", padding: "0.35rem 1rem", cursor: "pointer", borderRadius: 8, fontSize: "0.68rem" }}>
          {procesando ? "Procesando…" : "🔄 Procesar inbox ahora"}
        </button>
      </div>
      {msg && <div data-testid="blindaje-msg" style={{ ...panel, color: "#FCF6BA", fontSize: "0.78rem", padding: "0.6rem 1rem" }}>{msg}</div>}

      {tab === "autorizar" && (
        <>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: "1rem" }}>
            <Kpi icono="⏳" valor={k.pendientes_total ?? "—"} label="Pendientes" color="#fbbf24" />
            <Kpi icono="✅" valor={k.autorizados_hoy ?? "—"} label="Autorizados hoy" color="#4ade80" />
            <Kpi icono="⏱" valor={`${k.tiempo_promedio_min ?? 0} min`} label="Tiempo prom. autorización" />
          </div>
          {(data?.pendientes || []).length === 0 && (
            <div style={{ ...panel, color: "#9ca3af", fontSize: "0.8rem" }} data-testid="sin-pendientes">
              Sin correos esperando autorización. Cuando el clasificador detecte documentos faltantes,
              el correo propuesto aparecerá aquí — nada se envía sin tu autorización.
            </div>
          )}
          {(data?.pendientes || []).map(p => (
            <div key={p.id} style={{ ...panel, borderColor: `${PROTO_COLOR[p.protocolo_detectado] || ORO}66` }}
              data-testid={`autorizacion-card-${p.id}`}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", cursor: "pointer" }}
                onClick={() => setExp(exp === p.id ? null : p.id)}>
                <span style={{ color: "#6b7280", fontSize: "0.66rem" }}>{(p.created_at || "").slice(0, 16).replace("T", " ")}</span>
                <b style={{ color: "#fff", fontSize: "0.85rem" }}>{p.cliente_nombre || "(sin nombre)"}</b>
                <span style={{ color: "#9ca3af", fontSize: "0.72rem" }}>{p.cliente_rut}</span>
                <span style={{ background: `${PROTO_COLOR[p.protocolo_detectado] || "#888"}22`,
                  color: PROTO_COLOR[p.protocolo_detectado] || "#888", padding: "0.12rem 0.6rem",
                  borderRadius: 20, fontSize: "0.62rem", fontWeight: 800 }}>
                  {(p.protocolo_detectado || "").replace(/_/g, " ").toUpperCase()}</span>
                <span style={{ fontSize: "0.64rem", color: "#9ca3af" }}>IA {Math.round(p.confianza_ia || 0)}%</span>
                <span style={{ fontSize: "0.66rem", color: "#4ade80" }}>✔ {(p.documentos_tiene || []).length} tiene</span>
                <span style={{ fontSize: "0.66rem", color: "#f87171" }}>✘ {(p.documentos_faltan || []).length} faltan</span>
                <span style={{ marginLeft: "auto" }}><BarraLiq tiene={p.liquidaciones_tiene || 0} /></span>
              </div>
              {exp === p.id && (
                <div style={{ marginTop: 12 }}>
                  <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                    <div style={{ flex: "1 1 220px" }}>
                      <div style={{ color: "#4ade80", fontSize: "0.66rem", fontWeight: 800, marginBottom: 6 }}>TIENE</div>
                      {(p.documentos_tiene || []).map(d => (
                        <div key={d} style={{ fontSize: "0.72rem", color: "#a7f3d0" }}>✅ {d.replace(/_/g, " ")}</div>))}
                      {!(p.documentos_tiene || []).length && <div style={{ fontSize: "0.7rem", color: "#6b7280" }}>Nada aún</div>}
                    </div>
                    <div style={{ flex: "1 1 220px" }}>
                      <div style={{ color: "#f87171", fontSize: "0.66rem", fontWeight: 800, marginBottom: 6 }}>FALTA</div>
                      {(p.documentos_faltan || []).map(d => (
                        <div key={d} style={{ fontSize: "0.72rem", color: "#fecaca" }}>❌ {d.replace(/_/g, " ")}</div>))}
                    </div>
                    <div style={{ flex: "2 1 340px", background: "#fff", borderRadius: 10, padding: "0.8rem", maxHeight: 260, overflowY: "auto" }}>
                      <div style={{ fontSize: "0.68rem", color: "#666", marginBottom: 4 }}>Vista previa del correo propuesto:</div>
                      <div style={{ color: "#111", fontSize: "0.78rem" }}
                        dangerouslySetInnerHTML={{ __html: p.mensaje_propuesto || "" }} />
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
                    <button data-testid={`btn-autorizar-${p.id}`} disabled={busy === p.id}
                      onClick={() => accion(p.id, "autorizar")}
                      style={{ background: "linear-gradient(135deg,#166534,#22c55e)", color: "#fff", border: "none",
                        borderRadius: 8, padding: "0.5rem 1.1rem", cursor: "pointer", fontWeight: 800, fontSize: "0.72rem" }}>
                      {busy === p.id ? "Enviando…" : "✅ Autorizar y Enviar desde gerardo.ext"}</button>
                    <button data-testid={`btn-editar-${p.id}`}
                      onClick={() => setEdit({ id: p.id, asunto: "", body_html: p.mensaje_propuesto || "" })}
                      style={{ background: "transparent", border: `1px solid ${ORO}66`, color: ORO,
                        borderRadius: 8, padding: "0.5rem 1rem", cursor: "pointer", fontSize: "0.72rem", fontWeight: 700 }}>
                      ✏️ Editar y Autorizar</button>
                    <button data-testid={`btn-rechazar-${p.id}`} onClick={() => accion(p.id, "rechazar")}
                      style={{ background: "transparent", border: "1px solid #dc262666", color: "#f87171",
                        borderRadius: 8, padding: "0.5rem 1rem", cursor: "pointer", fontSize: "0.72rem" }}>❌ Rechazar</button>
                    <button data-testid={`btn-original-${p.id}`} onClick={() => verOriginal(p.id)}
                      style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.2)", color: "#cbd5e1",
                        borderRadius: 8, padding: "0.5rem 1rem", cursor: "pointer", fontSize: "0.72rem" }}>👁️ Correo original</button>
                    <button data-testid={`btn-carpeta-${p.id}`} onClick={() => verCarpeta(p.caso_id)}
                      style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.2)", color: "#cbd5e1",
                        borderRadius: 8, padding: "0.5rem 1rem", cursor: "pointer", fontSize: "0.72rem" }}>📁 Ver carpeta</button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </>
      )}

      {tab === "dashboard" && dash && (
        <>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: "1rem" }}>
            <Kpi icono="📥" valor={dk.entrantes_hoy} label="Entrada hoy (Claude)" />
            <Kpi icono="📁" valor={dk.enriquecidas_hoy} label="Enriquecidas auto" color="#4ade80" />
            <Kpi icono="⏳" valor={dk.pendiente_autorizacion} label="Pendiente autorización" color="#fbbf24" />
            <Kpi icono="✅" valor={dk.enviados_hoy} label="Enviados blindados hoy" color="#4ade80" />
            <Kpi icono="⛔" valor={dk.rebotados} label="Rebotados" color={dk.rebotados ? "#f87171" : "#4ade80"} />
            <Kpi icono="⚖️" valor={dk.listas_mesa} label="Carpetas listas para mesa" />
          </div>
          <div style={panel} data-testid="checklist-antispam">
            <div style={{ color: ORO, fontSize: "0.7rem", fontWeight: 800, letterSpacing: "0.12em", marginBottom: 8 }}>
              🔐 CHECKLIST ANTI-SPAM (SPF · DKIM · DMARC)</div>
            {(dash.checklist || []).map(c => (
              <div key={c.item} style={{ display: "flex", gap: 10, fontSize: "0.74rem", padding: "0.28rem 0",
                borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                <span>{c.ok ? "✅" : "⚠️"}</span>
                <b style={{ color: "#e2e8f0", minWidth: 190 }}>{c.item}</b>
                <span style={{ color: "#9ca3af" }}>{c.detalle}</span>
              </div>
            ))}
          </div>
          <div style={panel}>
            <div style={{ color: ORO, fontSize: "0.7rem", fontWeight: 800, letterSpacing: "0.12em", marginBottom: 8 }}>
              📤 COLA DE SALIDA BLINDADA (últimos 50)</div>
            <div style={{ maxHeight: 300, overflowY: "auto" }}>
              {(dash.cola || []).map(c => (
                <div key={c.id} style={{ display: "flex", gap: 10, fontSize: "0.7rem", padding: "0.3rem 0",
                  borderBottom: "1px solid rgba(255,255,255,0.05)", alignItems: "center", flexWrap: "wrap" }}>
                  <span style={{ width: 9, height: 9, borderRadius: "50%", background: ESTADO_COLOR[c.estado] || "#888" }} />
                  <span style={{ color: ESTADO_COLOR[c.estado] || "#888", fontWeight: 800, minWidth: 150 }}>
                    {(c.estado || "").replace(/_/g, " ").toUpperCase()}</span>
                  <span style={{ color: "#e2e8f0", flex: 1 }}>{c.asunto}</span>
                  <span style={{ color: "#6b7280" }}>{c.destinatario}</span>
                  <span style={{ color: "#6b7280" }}>{(c.created_at || "").slice(0, 16).replace("T", " ")}</span>
                  <span style={{ color: "#9ca3af" }}>{c.proveedor_envio}</span>
                </div>
              ))}
              {!(dash.cola || []).length && <div style={{ color: "#6b7280", fontSize: "0.72rem" }}>Cola vacía.</div>}
            </div>
          </div>
          <div style={panel}>
            <div style={{ color: ORO, fontSize: "0.7rem", fontWeight: 800, letterSpacing: "0.12em", marginBottom: 8 }}>
              📜 LOG DE BLINDAJE EN TIEMPO REAL</div>
            <div style={{ maxHeight: 320, overflowY: "auto" }}>
              {(dash.log || []).map(l => (
                <div key={l.id} style={{ display: "flex", gap: 10, fontSize: "0.68rem", padding: "0.26rem 0",
                  borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                  <span style={{ color: "#6b7280", minWidth: 118 }}>{(l.created_at || "").slice(0, 16).replace("T", " ")}</span>
                  <b style={{ color: "#FCF6BA", minWidth: 220 }}>{l.evento}</b>
                  <span style={{ color: "#9ca3af", wordBreak: "break-all" }}>{JSON.stringify(l.detalle || {}).slice(0, 160)}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {edit && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", zIndex: 3000,
          display: "flex", alignItems: "center", justifyContent: "center" }} data-testid="modal-editar">
          <div style={{ ...panel, width: "min(760px, 94vw)", maxHeight: "88vh", overflowY: "auto" }}>
            <h3 style={{ color: ORO, marginTop: 0 }}>✏️ Editar correo antes de autorizar</h3>
            <input data-testid="edit-asunto" placeholder="Asunto (vacío = mantener el propuesto)" value={edit.asunto}
              onChange={e => setEdit({ ...edit, asunto: e.target.value })}
              style={{ width: "100%", boxSizing: "border-box", background: "rgba(255,255,255,0.06)",
                border: `1px solid ${ORO}44`, color: "#fff", padding: "0.55rem", borderRadius: 8, marginBottom: 8 }} />
            <textarea data-testid="edit-body" rows={12} value={edit.body_html}
              onChange={e => setEdit({ ...edit, body_html: e.target.value })}
              style={{ width: "100%", boxSizing: "border-box", background: "rgba(255,255,255,0.06)",
                border: `1px solid ${ORO}44`, color: "#fff", padding: "0.55rem", borderRadius: 8, fontFamily: "monospace", fontSize: "0.72rem" }} />
            <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
              <button data-testid="edit-confirmar" disabled={busy === edit.id}
                onClick={() => accion(edit.id, "autorizar", { asunto: edit.asunto || undefined, body_html: edit.body_html })}
                style={{ background: "linear-gradient(135deg,#166534,#22c55e)", color: "#fff", border: "none",
                  borderRadius: 8, padding: "0.55rem 1.2rem", cursor: "pointer", fontWeight: 800 }}>
                ✅ Autorizar y Enviar editado</button>
              <button onClick={() => setEdit(null)} style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.2)",
                color: "#cbd5e1", borderRadius: 8, padding: "0.55rem 1rem", cursor: "pointer" }}>Cancelar</button>
            </div>
          </div>
        </div>
      )}

      {original && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", zIndex: 3000,
          display: "flex", alignItems: "center", justifyContent: "center" }} onClick={() => setOriginal(null)}>
          <div style={{ ...panel, width: "min(680px, 94vw)", maxHeight: "84vh", overflowY: "auto" }} onClick={e => e.stopPropagation()}>
            <h3 style={{ color: ORO, marginTop: 0 }}>👁️ Correo original</h3>
            <div style={{ fontSize: "0.76rem", color: "#e2e8f0" }}>
              <p><b>De:</b> {original.remitente}</p>
              <p><b>Asunto:</b> {original.asunto}</p>
              <p><b>Clasificación:</b> {original.clasificacion} · <b>Protocolo:</b> {original.protocolo_detectado} · <b>Confianza:</b> {Math.round(original.confianza || 0)}%</p>
              <pre style={{ whiteSpace: "pre-wrap", background: "rgba(255,255,255,0.05)", padding: "0.7rem",
                borderRadius: 8, fontSize: "0.7rem" }}>{original.body_text}</pre>
            </div>
            <button onClick={() => setOriginal(null)} style={{ background: "transparent", border: `1px solid ${ORO}66`,
              color: ORO, borderRadius: 8, padding: "0.4rem 1rem", cursor: "pointer" }}>Cerrar</button>
          </div>
        </div>
      )}

      {carpeta && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", zIndex: 3000,
          display: "flex", alignItems: "center", justifyContent: "center" }} onClick={() => setCarpeta(null)}>
          <div style={{ ...panel, width: "min(560px, 94vw)", maxHeight: "84vh", overflowY: "auto" }} onClick={e => e.stopPropagation()}>
            <h3 style={{ color: ORO, marginTop: 0 }}>📁 Estado de la carpeta</h3>
            {carpeta.map(d => (
              <div key={d.documento_tipo} style={{ display: "flex", gap: 10, fontSize: "0.74rem", padding: "0.3rem 0",
                borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                <span>{["recibido", "recibido_por_correo_auto", "validado"].includes(d.estado) ? "✅" : "❌"}</span>
                <span style={{ color: "#e2e8f0", flex: 1 }}>{d.label}</span>
                <span style={{ color: "#9ca3af" }}>{d.estado.replace(/_/g, " ")}{d.mes_detectado ? ` · ${d.mes_detectado}` : ""}</span>
              </div>
            ))}
            <button onClick={() => setCarpeta(null)} style={{ marginTop: 10, background: "transparent",
              border: `1px solid ${ORO}66`, color: ORO, borderRadius: 8, padding: "0.4rem 1rem", cursor: "pointer" }}>Cerrar</button>
          </div>
        </div>
      )}
    </div>
  );
}
