import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const inp = { background: "rgba(255,255,255,0.06)", border: "1px solid rgba(212,175,55,0.3)", color: "#fff", padding: "0.4rem 0.6rem", borderRadius: 8, fontSize: "0.72rem", boxSizing: "border-box" };
const goldBtn = { background: "linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C)", color: "#0a0a0a", border: "none", borderRadius: 8, padding: "0.4rem 0.9rem", fontWeight: 800, cursor: "pointer", fontSize: "0.7rem" };
const card = { background: "rgba(30,41,59,0.55)", border: "1px solid rgba(212,175,55,0.35)", borderRadius: 12, padding: "1rem", marginTop: 14 };
const sec = { background: "rgba(15,23,42,0.55)", border: "1px solid rgba(148,163,184,0.18)", borderRadius: 10, padding: "0.8rem", marginTop: 10 };

const Chip = ({ ok }) => <span style={{ fontWeight: 900, color: ok ? "#22c55e" : "#ef4444" }}>{ok ? "✅" : "❌"}</span>;

export const ManualConcreces = () => {
  const [carpetas, setCarpetas] = useState([]);
  const [fid, setFid] = useState("");
  const [d, setD] = useState(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(null);
  const [valido, setValido] = useState(false);
  const [reglas, setReglas] = useState(null);
  const [resDetalle, setResDetalle] = useState("");
  const [reparoTxt, setReparoTxt] = useState("");

  useEffect(() => {
    axios.get(`${API}/api/concreces/carpetas`).then(r => setCarpetas(r.data.carpetas || [])).catch(() => {});
  }, []);

  const cargar = useCallback((id) => {
    if (!id) return;
    axios.get(`${API}/api/concreces/flujo/${id}`).then(r => setD(r.data)).catch(e => setMsg("❌ " + (e.response?.data?.detail || "Error")));
  }, []);
  useEffect(() => { setD(null); setRevision(null); setValido(false); setMsg(""); cargar(fid); }, [fid, cargar]);

  const guardar = async (patch) => {
    try {
      const r = await axios.put(`${API}/api/concreces/flujo/${fid}`, patch);
      setD(r.data); setMsg("✅ Guardado");
    } catch (e) { setMsg("❌ " + (e.response?.data?.detail || "Error")); }
  };

  const fl = d?.flujo || {};
  const setCheck = (clave, v) => guardar({ checklist: { ...(fl.checklist || {}), [clave]: v } });
  const setCompra = (k, v) => setD(s => ({ ...s, flujo: { ...s.flujo, compra: { ...(s.flujo.compra || {}), [k]: v } } }));
  const setPol = (k, v) => setD(s => ({ ...s, flujo: { ...s.flujo, politica: { ...(s.flujo.politica || {}), [k]: v } } }));
  const setForm = (f, v) => guardar({ formularios: { ...(fl.formularios || {}), [f]: v } });

  const resolver = async (res) => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/concreces/flujo/${fid}/resolucion`, { resolucion: res, detalle: resDetalle });
      setMsg(`✅ ${r.data.carta_titulo} generada`); cargar(fid);
    } catch (e) { setMsg("❌ " + (e.response?.data?.detail || "Error")); }
    setBusy(false);
  };

  const genRevision = async () => {
    setBusy(true);
    try { const r = await axios.get(`${API}/api/concreces/flujo/${fid}/revision`); setRevision(r.data); setValido(false); }
    catch (e) { setMsg("❌ " + (e.response?.data?.detail || "Error")); }
    setBusy(false);
  };

  const enviar = async () => {
    setBusy(true);
    try {
      const r = await axios.post(`${API}/api/concreces/flujo/${fid}/enviar`, { confirmado: true });
      setMsg("✅ " + r.data.mensaje); setRevision(null); cargar(fid);
    } catch (e) { setMsg("❌ " + (e.response?.data?.detail || "Error")); }
    setBusy(false);
  };

  const agregarReparo = async () => {
    if (!reparoTxt.trim()) return;
    try { await axios.post(`${API}/api/concreces/flujo/${fid}/reparo`, { detalle: reparoTxt }); setReparoTxt(""); cargar(fid); }
    catch (e) { setMsg("❌ " + (e.response?.data?.detail || "Error")); }
  };
  const subsanar = async (rid) => {
    try { await axios.post(`${API}/api/concreces/flujo/${fid}/subsanar/${rid}`); cargar(fid); }
    catch (e) { setMsg("❌ " + (e.response?.data?.detail || "Error")); }
  };

  const verReglas = async () => {
    if (reglas) { setReglas(null); return; }
    const r = await axios.get(`${API}/api/concreces/reglas-oro`).catch(() => null);
    setReglas(r?.data?.reglas || []);
  };

  const sug = d?.compra_sugerencias || {};

  return (
    <div style={card} data-testid="modulo-victoria-concreces">
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <h4 style={{ margin: 0, color: "#d4af37", fontSize: "0.9rem" }}>📘 Módulo Victoria — Flujo ConCreces (según Manual de Procedimiento)</h4>
        <button data-testid="concreces-ver-reglas" onClick={verReglas} style={{ ...goldBtn, background: "rgba(212,175,55,0.15)", color: "#d4af37", border: "1px solid #d4af37" }}>
          {reglas ? "Ocultar" : "Ver"} Reglas de Oro ConCreces</button>
        <select data-testid="concreces-selector" value={fid} onChange={e => setFid(e.target.value)} style={{ ...inp, minWidth: 240, marginLeft: "auto" }}>
          <option value="">— Seleccionar carpeta de cliente —</option>
          {carpetas.map(c => <option key={c.id} value={c.id}>{`${c.nombre} · ${c.rut || "sin RUT"}`}</option>)}
        </select>
      </div>
      {reglas && (
        <div data-testid="concreces-reglas-oro" style={{ ...sec, borderColor: "rgba(212,175,55,0.5)" }}>
          {reglas.map(r => <p key={r.norma_clave} style={{ color: "#e2e8f0", fontSize: "0.66rem", margin: "4px 0" }}>🥇 {r.patron}</p>)}
          {reglas.length === 0 && <p style={{ color: "#94a3b8", fontSize: "0.68rem" }}>Sembrando reglas…</p>}
        </div>
      )}
      {msg && <p data-testid="concreces-msg" style={{ color: msg.startsWith("✅") ? "#22c55e" : "#ef4444", fontSize: "0.7rem", fontWeight: 700 }}>{msg}</p>}
      {!fid && <p style={{ color: "#94a3b8", fontSize: "0.72rem" }}>Selecciona una carpeta: el sistema te dirá paso a paso qué sigue, qué falta y qué está listo.</p>}

      {d && (<>
        {/* GUÍA: qué sigue */}
        <div data-testid="concreces-siguiente" style={{ marginTop: 10, background: d.siguiente ? "rgba(212,175,55,0.12)" : "rgba(34,197,94,0.12)", border: `1.5px solid ${d.siguiente ? "#d4af37" : "#22c55e"}`, borderRadius: 10, padding: "0.6rem 0.9rem", color: d.siguiente ? "#d4af37" : "#22c55e", fontWeight: 800, fontSize: "0.74rem" }}>
          {d.siguiente ? <>👉 SIGUIENTE PASO {d.siguiente.n}: {d.siguiente.titulo} — falta: {d.siguiente.faltan.slice(0, 3).join(" · ")}{d.siguiente.faltan.length > 3 ? "…" : ""}</>
            : "🏁 FLUJO COMPLETO — carpeta enviada a ConCreces"}
        </div>
        {/* STEPPER */}
        <div style={{ display: "flex", gap: 6, marginTop: 10, flexWrap: "wrap" }}>
          {d.pasos.map(p => (
            <span key={p.n} data-testid={`concreces-paso-${p.n}`} title={p.faltan.join(", ")} style={{ fontSize: "0.62rem", fontWeight: 800, padding: "0.3rem 0.6rem", borderRadius: 20, background: p.completo ? "rgba(34,197,94,0.15)" : "rgba(148,163,184,0.12)", color: p.completo ? "#22c55e" : "#94a3b8", border: `1px solid ${p.completo ? "#22c55e" : "rgba(148,163,184,0.3)"}` }}>
              {p.completo ? "✓" : p.n} {p.titulo}</span>
          ))}
        </div>

        {/* PASO 1 — CHECKLIST ANEXO I */}
        <div style={sec} data-testid="concreces-paso1">
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <b style={{ color: "#e2e8f0", fontSize: "0.76rem" }}>Paso 1 · Checklist ANEXO I</b>
            {["dependiente", "independiente"].map(t => (
              <button key={t} data-testid={`concreces-tipo-${t}`} onClick={() => guardar({ tipo_trabajador: t })}
                style={{ ...goldBtn, background: fl.tipo_trabajador === t ? undefined : "rgba(255,255,255,0.08)", color: fl.tipo_trabajador === t ? "#0a0a0a" : "#94a3b8" }}>
                {t === "dependiente" ? "Trabajador dependiente" : "Trabajador independiente"}</button>
            ))}
          </div>
          {(d.checklist_items || []).map(i => (
            <label key={i.clave} data-testid={`concreces-chk-${i.clave}`} style={{ display: "flex", gap: 8, alignItems: "center", padding: "0.3rem 0", color: i.ok ? "#22c55e" : "#e2e8f0", fontSize: "0.7rem", cursor: "pointer" }}>
              <input type="checkbox" checked={i.manual || i.auto} onChange={e => setCheck(i.clave, e.target.checked)} />
              {i.etiqueta}
              {i.auto && <span style={{ background: "rgba(56,189,248,0.15)", color: "#38bdf8", borderRadius: 6, padding: "0 6px", fontSize: "0.58rem", fontWeight: 800 }}>AUTO · detectado en carpeta</span>}
            </label>
          ))}
        </div>

        {/* PASO 2 — ANTECEDENTES DE LA COMPRA */}
        <div style={sec} data-testid="concreces-paso2">
          <b style={{ color: "#e2e8f0", fontSize: "0.76rem" }}>Paso 2 · Antecedentes de la compra</b>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(180px,1fr))", gap: 8, marginTop: 8 }}>
            {(d.compra_campos || []).map(([k, et]) => (
              <div key={k}>
                <div style={{ color: "#94a3b8", fontSize: "0.6rem" }}>{et}{sug[k] && !(fl.compra || {})[k] ? " · sugerido" : ""}</div>
                <input data-testid={`concreces-compra-${k}`} style={{ ...inp, width: "100%" }}
                  value={(fl.compra || {})[k] ?? ""} placeholder={sug[k] ? `Sugerencia: ${sug[k]}` : ""}
                  onChange={e => setCompra(k, e.target.value)} />
              </div>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button data-testid="concreces-compra-guardar" style={goldBtn} onClick={() => guardar({ compra: fl.compra || {} })}>Guardar paso 2</button>
            {Object.keys(sug).length > 0 && (
              <button data-testid="concreces-compra-autofill" style={{ ...goldBtn, background: "rgba(56,189,248,0.15)", color: "#38bdf8", border: "1px solid #38bdf8" }}
                onClick={() => guardar({ compra: { ...sug, ...(fl.compra || {}) } })}>Autocompletar con datos de la bóveda</button>
            )}
          </div>
        </div>

        {/* PASO 3 — POLÍTICA + RESOLUCIÓN */}
        <div style={sec} data-testid="concreces-paso3">
          <b style={{ color: "#e2e8f0", fontSize: "0.76rem" }}>Paso 3 · Política de crédito y resolución</b>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(150px,1fr))", gap: 8, marginTop: 8 }}>
            {[["renta_uf", "Renta mensual (UF)"], ["dividendo_uf", "Dividendo (UF)"], ["carga_financiera_pct", "Carga financiera (%)"],
              ["valor_venta_uf", "Valor venta (UF)"], ["tasacion_uf", "Tasación (UF)"], ["monto_credito_uf", "Monto crédito (UF)"],
              ["plazo_anios", "Plazo (años)"], ["edad", "Edad deudor"]].map(([k, et]) => (
              <div key={k}>
                <div style={{ color: "#94a3b8", fontSize: "0.6rem" }}>{et}</div>
                <input data-testid={`concreces-pol-${k}`} style={{ ...inp, width: "100%" }} value={(fl.politica || {})[k] ?? ""} onChange={e => setPol(k, e.target.value)} />
              </div>
            ))}
          </div>
          <div style={{ display: "flex", gap: 12, marginTop: 6, flexWrap: "wrap", color: "#94a3b8", fontSize: "0.66rem" }}>
            {[["extranjero", "Extranjero"], ["permanencia_definitiva", "Permanencia definitiva"], ["aval", "Aval / caución"], ["excepcion_40", "Excepción plazo 40 años"]].map(([k, et]) => (
              <label key={k} style={{ display: "flex", gap: 5, alignItems: "center", cursor: "pointer" }}>
                <input data-testid={`concreces-pol-${k}`} type="checkbox" checked={String((fl.politica || {})[k]) === "true"} onChange={e => setPol(k, String(e.target.checked))} />{et}
              </label>
            ))}
            <button data-testid="concreces-pol-evaluar" style={goldBtn} onClick={() => guardar({ politica: fl.politica || {} })}>Evaluar política</button>
          </div>
          <div style={{ marginTop: 8 }}>
            {(d.politica_checks || []).map((c, i) => (
              <p key={i} data-testid={`concreces-check-${i}`} style={{ margin: "3px 0", fontSize: "0.66rem", color: c.ok === true ? "#22c55e" : c.ok === false ? "#ef4444" : "#f59e0b" }}>
                {c.ok === true ? "✅" : c.ok === false ? "❌" : "⏳"} {c.regla} — {c.detalle}</p>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap", alignItems: "center" }}>
            <input data-testid="concreces-res-detalle" style={{ ...inp, flex: "1 1 220px" }} placeholder="Detalle / antecedentes solicitados (opcional)" value={resDetalle} onChange={e => setResDetalle(e.target.value)} />
            <button data-testid="concreces-res-aprobado" disabled={busy} style={{ ...goldBtn, background: "#22c55e", color: "#04120a" }} onClick={() => resolver("aprobado")}>APROBADO</button>
            <button data-testid="concreces-res-reparado" disabled={busy} style={{ ...goldBtn, background: "#f59e0b", color: "#1a1002" }} onClick={() => resolver("reparado")}>REPARADO</button>
            <button data-testid="concreces-res-rechazado" disabled={busy} style={{ ...goldBtn, background: "#ef4444", color: "#fff" }} onClick={() => resolver("rechazado")}>RECHAZADO</button>
            {fl.resolucion && <span data-testid="concreces-res-actual" style={{ color: "#d4af37", fontWeight: 800, fontSize: "0.7rem" }}>Resolución: {fl.resolucion.toUpperCase()} · {fl.carta_titulo}</span>}
          </div>
        </div>

        {/* PASO 4 — FORMULARIOS + PASO 5 — GOP */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(300px,1fr))", gap: 10 }}>
          <div style={sec} data-testid="concreces-paso4">
            <b style={{ color: "#e2e8f0", fontSize: "0.76rem" }}>Paso 4 · Formularios del cliente (ANEXO IV)</b>
            {(d.formularios || []).map(f => (
              <label key={f} style={{ display: "flex", gap: 8, alignItems: "center", padding: "0.25rem 0", color: (fl.formularios || {})[f] ? "#22c55e" : "#e2e8f0", fontSize: "0.68rem", cursor: "pointer" }}>
                <input data-testid={`concreces-form-${f.slice(0, 14).replace(/\s/g, "-")}`} type="checkbox" checked={!!(fl.formularios || {})[f]} onChange={e => setForm(f, e.target.checked)} />{f}
              </label>
            ))}
          </div>
          <div style={sec} data-testid="concreces-paso5">
            <b style={{ color: "#e2e8f0", fontSize: "0.76rem" }}>Paso 5 · Gastos Operacionales (GOP)</b>
            <label style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8, color: "#e2e8f0", fontSize: "0.7rem", cursor: "pointer" }}>
              <input data-testid="concreces-gop-pagado" type="checkbox" checked={!!(fl.gop || {}).pagado} onChange={e => guardar({ gop: { ...(fl.gop || {}), pagado: e.target.checked } })} />GOP pagados
            </label>
            <div style={{ marginTop: 6 }}>
              <div style={{ color: "#94a3b8", fontSize: "0.6rem" }}>Socio comercial (ANEXO III)</div>
              <select data-testid="concreces-gop-socio" style={{ ...inp, width: "100%" }} value={(fl.gop || {}).socio || ""} onChange={e => guardar({ gop: { ...(fl.gop || {}), socio: e.target.value } })}>
                <option value="">— Sin socio —</option>
                <option>Carlos Vildosola</option><option>Gerardo Barrera</option><option>Zona Propia</option>
              </select>
            </div>
            <p data-testid="concreces-gop-estado" style={{ marginTop: 8, fontWeight: 800, fontSize: "0.68rem", color: d.gop_ok ? "#22c55e" : "#ef4444" }}>
              {d.gop_ok ? "✅ Habilitado para escriturar" : "🔒 REGLA DE ORO 3: sin GOP pagados NO se envía a escriturar (excepción: Gerardo Barrera)"}</p>
          </div>
        </div>

        {/* PASO 6 — REVISIÓN Y ENVÍO */}
        <div style={{ ...sec, borderColor: "rgba(212,175,55,0.5)" }} data-testid="concreces-paso6">
          <b style={{ color: "#d4af37", fontSize: "0.76rem" }}>Paso 6 · Documento de revisión y envío a ConCreces</b>
          <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
            <button data-testid="concreces-gen-revision" disabled={busy} style={goldBtn} onClick={genRevision}>📄 Generar documento de revisión</button>
            {fl.enviado && <span data-testid="concreces-enviado-badge" style={{ color: "#22c55e", fontWeight: 800, fontSize: "0.7rem" }}>✅ ENVIADO a ConCreces el {String(fl.enviado_en || "").slice(0, 16).replace("T", " ")}</span>}
          </div>
          {fl.enviado && (
            <div style={{ marginTop: 10 }}>
              <div style={{ color: "#94a3b8", fontSize: "0.66rem", fontWeight: 700 }}>Reparos de la administradora (Regla de Oro 9 — deben subsanarse):</div>
              {(fl.reparos || []).map(r => (
                <div key={r.id} data-testid={`concreces-reparo-${r.id}`} style={{ display: "flex", gap: 8, alignItems: "center", padding: "0.3rem 0", fontSize: "0.68rem", color: r.estado === "subsanado" ? "#22c55e" : "#f59e0b" }}>
                  {r.estado === "subsanado" ? "✅" : "⚠️"} {r.detalle}
                  {r.estado === "pendiente" && <button data-testid={`concreces-subsanar-${r.id}`} style={{ ...goldBtn, padding: "0.2rem 0.6rem" }} onClick={() => subsanar(r.id)}>Subsanar</button>}
                </div>
              ))}
              <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
                <input data-testid="concreces-reparo-input" style={{ ...inp, flex: 1 }} placeholder="Registrar reparo recibido de la administradora…" value={reparoTxt} onChange={e => setReparoTxt(e.target.value)} />
                <button data-testid="concreces-reparo-agregar" style={goldBtn} onClick={agregarReparo}>+ Reparo</button>
              </div>
            </div>
          )}
        </div>
      </>)}

      {/* MODAL DOCUMENTO DE REVISIÓN */}
      {revision && (
        <div data-testid="concreces-modal-revision" onClick={() => setRevision(null)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.8)", zIndex: 700, display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
          <div onClick={e => e.stopPropagation()} style={{ background: "#0f172a", border: "1.5px solid #d4af37", borderRadius: 12, width: 860, maxWidth: "96vw", maxHeight: "92vh", display: "flex", flexDirection: "column" }}>
            <div style={{ padding: "0.7rem 1rem", borderBottom: "1px solid rgba(212,175,55,0.3)", color: "#d4af37", fontWeight: 800, fontSize: "0.8rem" }}>📄 Documento de Revisión — validar antes de enviar</div>
            <iframe title="revision" srcDoc={revision.html} style={{ flex: 1, minHeight: 380, border: "none", background: "#fff" }} data-testid="concreces-revision-iframe" />
            <div style={{ padding: "0.8rem 1rem", borderTop: "1px solid rgba(212,175,55,0.3)" }}>
              <label style={{ display: "flex", gap: 8, alignItems: "center", color: "#e2e8f0", fontSize: "0.72rem", cursor: "pointer" }}>
                <input data-testid="concreces-valido-check" type="checkbox" checked={valido} onChange={e => setValido(e.target.checked)} />
                Yo, Daniela Galindo, reviso y valido que toda la información está correcta para el envío a ConCreces.
              </label>
              <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                <button data-testid="concreces-enviar-btn" disabled={!valido || !revision.listo_para_enviar || busy} onClick={enviar}
                  style={{ ...goldBtn, flex: 1, opacity: (!valido || !revision.listo_para_enviar) ? 0.4 : 1, padding: "0.6rem" }}>
                  🚀 Confirmar y ENVIAR archivos a ConCreces</button>
                <button onClick={() => setRevision(null)} style={{ background: "transparent", color: "#94a3b8", border: "1px solid rgba(255,255,255,0.2)", borderRadius: 8, padding: "0.5rem 1rem", cursor: "pointer" }}>Cerrar</button>
              </div>
              {!revision.listo_para_enviar && <p data-testid="concreces-no-listo" style={{ color: "#ef4444", fontSize: "0.66rem", marginTop: 6, fontWeight: 700 }}>
                ⛔ Reglas de Oro incumplidas: {revision.validaciones.filter(v => !v.ok).map(v => v.regla).join(" · ")}</p>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ManualConcreces;
