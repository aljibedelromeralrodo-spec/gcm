import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import PresentacionVictoria from "./PresentacionVictoria";

const API = process.env.REACT_APP_BACKEND_URL;
const inp = { background: "rgba(255,255,255,0.06)", border: "1px solid rgba(212,175,55,0.3)", color: "#fff", padding: "0.4rem 0.6rem", borderRadius: 8, fontSize: "0.72rem", boxSizing: "border-box" };
const goldBtn = { background: "linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C)", color: "#0a0a0a", border: "none", borderRadius: 8, padding: "0.4rem 0.9rem", fontWeight: 800, cursor: "pointer", fontSize: "0.7rem" };
const card = { background: "rgba(30,41,59,0.55)", border: "1px solid rgba(212,175,55,0.35)", borderRadius: 12, padding: "1rem", marginTop: 14 };
const sec = { background: "rgba(15,23,42,0.55)", border: "1px solid rgba(148,163,184,0.18)", borderRadius: 10, padding: "0.8rem", marginTop: 10 };

const FORM_CAMPOS = [["nombre_cliente", "Nombre cliente"], ["rut_titular", "RUT titular"], ["rut_codeudor", "RUT codeudor"], ["rol_avaluo", "Rol de avalúo fiscal"], ["direccion_propiedad", "Dirección de la propiedad"]];

export const VictoriaBoveda = () => {
  const [panel, setPanel] = useState(null);
  const [cid, setCid] = useState("");
  const [det, setDet] = useState(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState("");
  const [nuevo, setNuevo] = useState({ nombre: "", rut: "", rut_codeudor: "" });
  const [forms, setForms] = useState({});
  const [envio, setEnvio] = useState(null);
  const [showPres, setShowPres] = useState(false);
  const [tipoSubida, setTipoSubida] = useState("");

  const cargarPanel = useCallback(() => {
    axios.get(`${API}/api/victoria/panel`).then(r => setPanel(r.data)).catch(e => setMsg("❌ " + (e.response?.data?.detail || "Error")));
  }, []);
  const cargarDetalle = useCallback((id) => {
    if (!id) { setDet(null); return; }
    axios.get(`${API}/api/victoria/clientes/${id}`).then(r => { setDet(r.data); setForms(r.data.formularios_auto || {}); })
      .catch(e => setMsg("❌ " + (e.response?.data?.detail || "Error")));
  }, []);
  useEffect(() => { cargarPanel(); }, [cargarPanel]);
  useEffect(() => { setEnvio(null); cargarDetalle(cid); }, [cid, cargarDetalle]);

  const accion = async (fn, okMsg) => {
    setBusy("x");
    try { const r = await fn(); setMsg("✅ " + (okMsg || r?.data?.mensaje || "Listo")); cargarPanel(); cargarDetalle(cid); return r; }
    catch (e) { setMsg("❌ " + (e.response?.data?.detail || "Error")); }
    finally { setBusy(""); }
  };

  const crearCliente = () => accion(async () => {
    const r = await axios.post(`${API}/api/victoria/clientes`, nuevo);
    setNuevo({ nombre: "", rut: "", rut_codeudor: "" }); setCid(r.data.cliente.id);
    return r;
  }, "Cliente creado en la bóveda");

  const subir = (e) => {
    const f = e.target.files?.[0]; if (!f) return;
    const fd = new FormData(); fd.append("file", f); fd.append("tipo", tipoSubida);
    accion(() => axios.post(`${API}/api/victoria/clientes/${cid}/subir`, fd), "Documento subido, clasificado y auditado");
    e.target.value = "";
  };

  const guardarForms = (confirmado) => accion(() =>
    axios.put(`${API}/api/victoria/clientes/${cid}/formularios`, { datos: forms, confirmado }),
    confirmado ? "Formularios CONFIRMADOS por Victoria" : "Formularios guardados");

  const genEnvio = () => accion(async () => {
    const r = await axios.get(`${API}/api/victoria/clientes/${cid}/documento-envio`);
    setEnvio(r.data); return r;
  }, "Documento de envío generado");

  const despachar = () => accion(async () => {
    const r = await axios.post(`${API}/api/victoria/clientes/${cid}/despachar`, { confirmado: true });
    setEnvio(null); return r;
  });

  const aud = det?.auditoria;
  const cli = det?.cliente;

  return (
    <div style={card} data-testid="victoria-boveda">
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <h4 style={{ margin: 0, color: "#d4af37", fontSize: "0.9rem" }}>🗄️ Bóveda Independiente de Victoria — Sets de Crédito → ConCreces</h4>
        <button data-testid="victoria-presentacion-btn" onClick={() => setShowPres(true)}
          style={{ ...goldBtn, background: "rgba(212,175,55,0.15)", color: "#d4af37", border: "1px solid #d4af37" }}>▶ Ver presentación</button>
        <button data-testid="victoria-procesar-correo" disabled={!!busy} style={goldBtn}
          onClick={() => accion(async () => {
            const r = await axios.post(`${API}/api/victoria/procesar-correo`, {});
            setTimeout(() => { cargarPanel(); cargarDetalle(cid); }, 25000);
            return r;
          })}>{busy ? "…" : "📥 Revisar correo ahora"}</button>
        <span style={{ marginLeft: "auto", color: "#94a3b8", fontSize: "0.62rem" }}>
          Monitoreando: <b style={{ color: "#d4af37" }}>{panel?.correo_monitoreado || "sin configurar"}</b>
          {(panel?.aliados || []).map(a => ` · ${a.etiqueta}: ${a.email}`).join("")}</span>
      </div>
      {msg && <p data-testid="victoria-msg" style={{ color: msg.startsWith("✅") ? "#22c55e" : "#ef4444", fontSize: "0.7rem", fontWeight: 700 }}>{msg}</p>}

      {/* AVISOS */}
      {(panel?.avisos || []).length > 0 && (
        <div style={{ ...sec, borderColor: "rgba(245,158,11,0.5)" }} data-testid="victoria-avisos">
          <b style={{ color: "#f59e0b", fontSize: "0.72rem" }}>🔔 Avisos para Victoria</b>
          {panel.avisos.map(a => (
            <div key={a.id} style={{ display: "flex", gap: 8, alignItems: "center", padding: "0.25rem 0", color: "#e2e8f0", fontSize: "0.68rem" }}>
              ⚠️ {a.detalle}
              <button data-testid={`victoria-aviso-ok-${a.id}`} style={{ ...goldBtn, padding: "0.15rem 0.5rem", marginLeft: "auto" }}
                onClick={() => accion(() => axios.post(`${API}/api/victoria/avisos/${a.id}/leido`, {}), "Aviso archivado")}>OK</button>
            </div>
          ))}
        </div>
      )}

      {/* SIN CLASIFICAR */}
      {(panel?.sin_clasificar || []).length > 0 && (
        <div style={sec} data-testid="victoria-sin-clasificar">
          <b style={{ color: "#e2e8f0", fontSize: "0.72rem" }}>📎 Documentos sin clasificar (asignar a cliente)</b>
          {panel.sin_clasificar.map(d => (
            <div key={d.id} style={{ display: "flex", gap: 8, alignItems: "center", padding: "0.3rem 0", fontSize: "0.68rem", color: "#94a3b8", flexWrap: "wrap" }}>
              📄 {d.archivo} <span style={{ color: "#64748b" }}>({d.tipo})</span>
              <select data-testid={`victoria-asignar-sel-${d.id}`} style={{ ...inp, flex: "0 1 200px" }} defaultValue=""
                onChange={e => e.target.value && accion(() => axios.post(`${API}/api/victoria/sin-clasificar/${d.id}/asignar`, { cliente_id: e.target.value }), "Documento asignado y re-auditado")}>
                <option value="">— Asignar a… —</option>
                {(panel?.clientes || []).map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
              </select>
            </div>
          ))}
        </div>
      )}

      {/* CLIENTES DE LA BÓVEDA */}
      <div style={sec} data-testid="victoria-clientes">
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <b style={{ color: "#e2e8f0", fontSize: "0.72rem" }}>Clientes en la bóveda ({(panel?.clientes || []).length})</b>
          <input data-testid="victoria-nuevo-nombre" style={{ ...inp, flex: "0 1 170px" }} placeholder="Nombre cliente" value={nuevo.nombre} onChange={e => setNuevo({ ...nuevo, nombre: e.target.value })} />
          <input data-testid="victoria-nuevo-rut" style={{ ...inp, flex: "0 1 120px" }} placeholder="RUT" value={nuevo.rut} onChange={e => setNuevo({ ...nuevo, rut: e.target.value })} />
          <input data-testid="victoria-nuevo-rutcod" style={{ ...inp, flex: "0 1 130px" }} placeholder="RUT codeudor" value={nuevo.rut_codeudor} onChange={e => setNuevo({ ...nuevo, rut_codeudor: e.target.value })} />
          <button data-testid="victoria-crear-cliente" style={goldBtn} onClick={crearCliente}>+ Crear</button>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
          {(panel?.clientes || []).map(c => (
            <button key={c.id} data-testid={`victoria-cliente-${c.id}`} onClick={() => setCid(c.id === cid ? "" : c.id)}
              style={{ textAlign: "left", cursor: "pointer", borderRadius: 10, padding: "0.55rem 0.8rem", minWidth: 190,
                background: cid === c.id ? "rgba(212,175,55,0.18)" : "rgba(255,255,255,0.04)",
                border: `1.5px solid ${cid === c.id ? "#d4af37" : c.despachado ? "#22c55e" : c.bloqueado ? "rgba(239,68,68,0.5)" : "rgba(148,163,184,0.25)"}` }}>
              <div style={{ color: "#e2e8f0", fontWeight: 800, fontSize: "0.72rem" }}>{c.nombre}</div>
              <div style={{ color: "#94a3b8", fontSize: "0.6rem" }}>{c.rut || "sin RUT"} · {c.n_docs} doc(s)</div>
              <div style={{ fontSize: "0.58rem", fontWeight: 800, marginTop: 3, color: c.despachado ? "#22c55e" : c.siguiente ? "#d4af37" : "#22c55e" }}>
                {c.despachado ? "✅ DESPACHADO" : c.siguiente ? `👉 ${c.siguiente.titulo}` : "Listo"}</div>
            </button>
          ))}
          {(panel?.clientes || []).length === 0 && <p style={{ color: "#64748b", fontSize: "0.68rem" }}>La bóveda está vacía: los clientes se crean solos al llegar documentos por correo, o créalos aquí.</p>}
        </div>
      </div>

      {/* DETALLE CLIENTE */}
      {det && cli && (<>
        <div data-testid="victoria-siguiente" style={{ marginTop: 10, background: det.siguiente ? "rgba(212,175,55,0.12)" : "rgba(34,197,94,0.12)", border: `1.5px solid ${det.siguiente ? "#d4af37" : "#22c55e"}`, borderRadius: 10, padding: "0.6rem 0.9rem", color: det.siguiente ? "#d4af37" : "#22c55e", fontWeight: 800, fontSize: "0.74rem" }}>
          {det.siguiente ? <>👉 SIGUIENTE: {det.siguiente.titulo} — {det.siguiente.detalle}</> : "🏁 SET DESPACHADO A CONCRECES"}
        </div>

        {/* DOCUMENTOS */}
        <div style={sec} data-testid="victoria-docs">
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <b style={{ color: "#e2e8f0", fontSize: "0.72rem" }}>Documentos del set ({(det.docs || []).length})</b>
            <select data-testid="victoria-tipo-subida" style={{ ...inp }} value={tipoSubida} onChange={e => setTipoSubida(e.target.value)}>
              <option value="">Tipo: detectar automático</option>
              {Object.entries(det.tipos || {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <label style={{ ...goldBtn, display: "inline-block" }}>
              📤 Subir documento<input data-testid="victoria-subir" type="file" style={{ display: "none" }} onChange={subir} /></label>
            <button data-testid="victoria-auditar" disabled={!!busy} style={{ ...goldBtn, background: "rgba(56,189,248,0.15)", color: "#38bdf8", border: "1px solid #38bdf8" }}
              onClick={() => accion(() => axios.post(`${API}/api/victoria/clientes/${cid}/auditar`, {}), "Auditoría ejecutada")}>🔍 Re-auditar</button>
          </div>
          {Object.entries(det.requeridos || {}).map(([t, et]) => {
            const tiene = (det.docs || []).some(d => d.tipo === t);
            return <span key={t} style={{ display: "inline-block", margin: "6px 6px 0 0", fontSize: "0.6rem", fontWeight: 800, padding: "0.2rem 0.55rem", borderRadius: 20, background: tiene ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.12)", color: tiene ? "#22c55e" : "#ef4444", border: `1px solid ${tiene ? "#22c55e" : "#ef4444"}` }}>{tiene ? "✓" : "✗"} {et}</span>;
          })}
          {(det.docs || []).map(d => (
            <div key={d.id} data-testid={`victoria-doc-${d.id}`} style={{ padding: "0.45rem 0", borderBottom: "1px solid rgba(255,255,255,0.06)", fontSize: "0.68rem", color: "#e2e8f0" }}>
              📄 <b>{(det.tipos || {})[d.tipo] || d.tipo}</b> · {d.archivo}
              <span style={{ color: "#64748b" }}> · {d.origen === "correo" ? "📧 detectado en correo" : "subida manual"} · {String(d.recibido).slice(0, 16).replace("T", " ")}</span>
              <div style={{ color: "#94a3b8", fontSize: "0.6rem", marginTop: 2 }}>
                RUT: {(d.datos || {}).rut_titular || "—"} · Codeudor: {(d.datos || {}).rut_codeudor || "—"} · Rol: {(d.datos || {}).rol_avaluo || "—"} · Dir: {((d.datos || {}).direccion_propiedad || "—").slice(0, 45)} · Fecha: {(d.datos || {}).fecha_documento || "—"} · Firma: {(d.datos || {}).firmado ? "✅" : "—"}
              </div>
            </div>
          ))}
        </div>

        {/* AUDITORÍA */}
        {aud && (
          <div style={{ ...sec, borderColor: aud.bloqueado ? "rgba(239,68,68,0.5)" : "rgba(34,197,94,0.5)" }} data-testid="victoria-auditoria">
            <b style={{ color: aud.bloqueado ? "#ef4444" : "#22c55e", fontSize: "0.74rem" }}>
              {aud.bloqueado ? "🔒 AUDITORÍA: AVANCE BLOQUEADO" : "✅ AUDITORÍA: SIN BLOQUEOS"}</b>
            <div style={{ marginTop: 8 }}>
              <b style={{ color: "#d4af37", fontSize: "0.66rem" }}>Coincidencias obligatorias (Reglas de Oro 11-14 — irrenunciables):</b>
              {(aud.coincidencias || []).map((x, i) => (
                <p key={i} data-testid={`victoria-coincidencia-${i}`} style={{ margin: "4px 0", fontSize: "0.66rem", color: x.ok === true ? "#22c55e" : x.ok === false ? "#ef4444" : "#f59e0b" }}>
                  {x.ok === true ? "✅" : x.ok === false ? "🚨" : "⏳"} <b>{x.regla}</b> — {x.detalle}</p>
              ))}
            </div>
            {(aud.alertas || []).length > 0 && (
              <div style={{ marginTop: 8 }}>
                <b style={{ color: "#f59e0b", fontSize: "0.66rem" }}>Alertas ({aud.alertas.length}):</b>
                {aud.alertas.map((a, i) => (
                  <p key={i} data-testid={`victoria-alerta-${i}`} style={{ margin: "3px 0", fontSize: "0.64rem", color: a.nivel === "critica" ? "#ef4444" : "#f59e0b" }}>
                    {a.nivel === "critica" ? "🚨" : "⚠️"} [{a.doc}] {a.detalle}</p>
                ))}
              </div>
            )}
          </div>
        )}

        {/* FORMULARIOS AUTO-RELLENADOS */}
        <div style={sec} data-testid="victoria-formularios">
          <b style={{ color: "#e2e8f0", fontSize: "0.72rem" }}>Formularios — auto-rellenados con los datos de la bóveda {cli.formularios_confirmados && <span style={{ color: "#22c55e" }}>· ✅ CONFIRMADOS</span>}</b>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(200px,1fr))", gap: 8, marginTop: 8 }}>
            {FORM_CAMPOS.map(([k, et]) => (
              <div key={k}>
                <div style={{ color: "#94a3b8", fontSize: "0.6rem" }}>{et}</div>
                <input data-testid={`victoria-form-${k}`} style={{ ...inp, width: "100%" }} value={forms[k] ?? ""} onChange={e => setForms({ ...forms, [k]: e.target.value })} />
              </div>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button data-testid="victoria-forms-guardar" style={{ ...goldBtn, background: "rgba(255,255,255,0.1)", color: "#e2e8f0" }} onClick={() => guardarForms(false)}>Guardar</button>
            <button data-testid="victoria-forms-confirmar" style={goldBtn} onClick={() => guardarForms(true)}>✅ Revisado — Confirmar formularios</button>
          </div>
        </div>

        {/* ENVÍO */}
        <div style={{ ...sec, borderColor: "rgba(212,175,55,0.5)" }} data-testid="victoria-envio">
          <b style={{ color: "#d4af37", fontSize: "0.74rem" }}>Documento de envío y despacho a ConCreces</b>
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button data-testid="victoria-gen-envio" disabled={!!busy} style={goldBtn} onClick={genEnvio}>📄 Generar documento de envío</button>
            {cli.despachado && <span data-testid="victoria-despachado-badge" style={{ color: "#22c55e", fontWeight: 800, fontSize: "0.7rem" }}>✅ DESPACHADO el {String(cli.despachado_en || "").slice(0, 16).replace("T", " ")}</span>}
          </div>
        </div>
      </>)}

      {/* MODAL DOCUMENTO DE ENVÍO */}
      {envio && (
        <div data-testid="victoria-modal-envio" onClick={() => setEnvio(null)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.8)", zIndex: 700, display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
          <div onClick={e => e.stopPropagation()} style={{ background: "#0f172a", border: "1.5px solid #d4af37", borderRadius: 12, width: 880, maxWidth: "96vw", maxHeight: "92vh", display: "flex", flexDirection: "column" }}>
            <div style={{ padding: "0.7rem 1rem", borderBottom: "1px solid rgba(212,175,55,0.3)", color: "#d4af37", fontWeight: 800, fontSize: "0.8rem" }}>📄 Documento de Envío — revisión final de Victoria</div>
            <iframe title="envio" srcDoc={envio.html} style={{ flex: 1, minHeight: 400, border: "none", background: "#fff" }} data-testid="victoria-envio-iframe" />
            <div style={{ padding: "0.8rem 1rem", borderTop: "1px solid rgba(212,175,55,0.3)", display: "flex", gap: 8, alignItems: "center" }}>
              <button data-testid="victoria-despachar-btn" disabled={!envio.listo || !!busy} onClick={despachar}
                style={{ ...goldBtn, flex: 1, opacity: envio.listo ? 1 : 0.4, padding: "0.6rem" }}>
                🚀 DESPACHAR a ConCreces (1 clic)</button>
              <button onClick={() => setEnvio(null)} style={{ background: "transparent", color: "#94a3b8", border: "1px solid rgba(255,255,255,0.2)", borderRadius: 8, padding: "0.5rem 1rem", cursor: "pointer" }}>Cerrar</button>
            </div>
            {!envio.listo && <p data-testid="victoria-no-listo" style={{ color: "#ef4444", fontSize: "0.66rem", padding: "0 1rem 0.8rem", fontWeight: 700, margin: 0 }}>
              ⛔ {envio.bloqueado ? "Reglas de Oro 11-14: hay coincidencias sin validar o alertas críticas." : "Falta confirmar los formularios."} No se puede enviar a ConCreces hasta que todo coincida.</p>}
          </div>
        </div>
      )}

      {showPres && <PresentacionVictoria onClose={() => setShowPres(false)} />}
    </div>
  );
};

export default VictoriaBoveda;
