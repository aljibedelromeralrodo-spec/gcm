import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const ORO = "#d4af37";
const panel = { background: "rgba(20,20,24,0.92)", border: "1px solid rgba(212,175,55,0.3)",
  borderRadius: 14, padding: "1.1rem 1.3rem", marginBottom: "1rem" };

const HERR_LIBRES = [
  { id: "recontar_6_liquidaciones", icono: "📁", label: "Recontar 6 Liquidaciones", pide: "caso_id" },
  { id: "reparsear_correo_fallido", icono: "📧", label: "Reparsear Correo Fallido", pide: "message_id" },
  { id: "corregir_protocolo_mal_clasificado", icono: "🏷️", label: "Corregir Protocolo", pide: "caso_protocolo" },
  { id: "reparar_tasa_rota_con_oro", icono: "💰", label: "Reparar Tasa Rota con Oro" },
  { id: "reenriquecer_carpeta_manual", icono: "📂", label: "Reenriquecer Carpeta", pide: "caso_id" },
  { id: "reindexar_memoria_total", icono: "🧠", label: "Reindexar Memoria" },
  { id: "reiniciar_parser_cron", icono: "🔄", label: "Reiniciar Parser" },
  { id: "reintentar_envio_rebotado", icono: "↩️", label: "Reintentar Envío", pide: "cola_id" },
];
const HERR_PROTEGIDAS = [
  { id: "enviar_masivo", icono: "📢", label: "Enviar Masivo >10" },
  { id: "enviar_correo_sin_autorizacion", icono: "✉️", label: "Enviar sin Autorización" },
  { id: "cambiar_from_email", icono: "🔄", label: "Cambiar FROM" },
];
const PROTOS = ["dependiente_simple", "independiente", "mixto", "con_codeudor", "con_licencia_medica"];

const Kpi = ({ icono, valor, label, color }) => (
  <div style={{ ...panel, flex: "1 1 150px", marginBottom: 0, textAlign: "center", padding: "0.9rem" }}>
    <div style={{ fontSize: "1.4rem" }}>{icono}</div>
    <div style={{ fontSize: "1.5rem", fontWeight: 900, color: color || ORO }}>{valor}</div>
    <div style={{ fontSize: "0.6rem", color: "#9ca3af", letterSpacing: "0.08em", textTransform: "uppercase" }}>{label}</div>
  </div>
);

export default function MartinTallerModule() {
  const [data, setData] = useState(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState("");
  const [pedir, setPedir] = useState(null);
  const [inputVal, setInputVal] = useState("");
  const [protoSel, setProtoSel] = useState(PROTOS[0]);
  const [mejora, setMejora] = useState("");

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/martin/reparaciones`);
      setData(r.data);
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 45000); return () => clearInterval(t); }, [load]);

  const ejecutar = async (herramienta, params, fallaId) => {
    if (!window.confirm("¿Reparar con oro? ✨ (queda documentado, nada se borra)")) return;
    setBusy(herramienta + (fallaId || ""));
    try {
      const r = await axios.post(`${API}/api/martin/reparar`,
        { herramienta, params: params || {}, falla_id: fallaId });
      setMsg(r.data.mensaje || JSON.stringify(r.data).slice(0, 200));
      setPedir(null); setInputVal(""); load();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setBusy("");
  };

  const clickHerr = (h) => {
    if (!h.pide) return ejecutar(h.id, {});
    setPedir(h); setInputVal("");
  };
  const confirmarPedir = () => {
    const p = pedir.pide === "message_id" ? { message_id: inputVal }
      : pedir.pide === "cola_id" ? { cola_id: inputVal }
      : pedir.pide === "caso_protocolo" ? { caso_id: inputVal, protocolo: protoSel }
      : { caso_id: inputVal.includes("-") && inputVal.length < 15 ? "" : inputVal, rut: inputVal.length < 15 ? inputVal : "" };
    ejecutar(pedir.id, p);
  };

  const vigiaAhora = async () => {
    setBusy("vigia");
    try {
      const r = await axios.post(`${API}/api/martin/vigia-ahora`);
      setMsg(`👁️ Vigía ejecutado: ${r.data.fallas_nuevas} falla(s) nueva(s) detectada(s)`);
      load();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setBusy("");
  };
  const proponerMejora = async () => {
    if (!mejora.trim()) return;
    setBusy("mejora");
    try {
      const r = await axios.post(`${API}/api/martin/mejorar`, { texto: mejora });
      setMsg(r.data.mensaje); setMejora(""); load();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setBusy("");
  };

  const k = data?.kpis || {};
  return (
    <div data-testid="martin-taller" style={{ padding: "0.4rem 0" }}>
      <div style={{ ...panel, background: "linear-gradient(135deg, rgba(20,20,24,0.95), rgba(60,45,10,0.35))" }}>
        <h2 style={{ color: ORO, margin: 0, fontSize: "1.12rem" }}>🔧 Taller de Reparación — Filosofía Kintsugi</h2>
        <div style={{ color: "#cbd5e1", fontSize: "0.74rem", marginTop: 4 }}>
          Lo roto se une con oro y queda <b style={{ color: "#FCF6BA" }}>más fuerte</b>. Martín tiene libertad total
          para diagnosticar, reparar y mejorar — solo lo masivo pide autorización de Gerardo.
        </div>
      </div>
      {msg && <div data-testid="martin-msg" style={{ ...panel, color: "#FCF6BA", fontSize: "0.78rem", padding: "0.6rem 1rem" }}>{msg}</div>}

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: "1rem" }}>
        <Kpi icono="💔" valor={k.fallas_hoy ?? "—"} label="Fallas detectadas hoy" color="#f87171" />
        <Kpi icono="🔨" valor={k.reparadas_hoy ?? "—"} label="Reparadas con oro hoy" color="#4ade80" />
        <Kpi icono="⏱" valor={`${k.tiempo_promedio_ms ?? 0} ms`} label="Tiempo prom. reparación" />
        <Kpi icono="✨" valor={k.tasa_oro ?? "100%"} label="Tasa de oro" />
      </div>

      <div style={panel} data-testid="seccion-vigia">
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
          <div style={{ color: ORO, fontSize: "0.72rem", fontWeight: 800, letterSpacing: "0.12em" }}>👁️ VIGÍA AUTOMÁTICO (cada 10 min)</div>
          <button data-testid="btn-vigia-ahora" onClick={vigiaAhora} disabled={busy === "vigia"}
            style={{ marginLeft: "auto", background: "transparent", border: `1px solid ${ORO}55`, color: ORO,
              padding: "0.3rem 0.9rem", cursor: "pointer", borderRadius: 8, fontSize: "0.66rem", fontWeight: 800 }}>
            {busy === "vigia" ? "Vigilando…" : "👁️ Vigilar ahora"}</button>
          <button data-testid="btn-guardian" disabled={busy === "guardian"}
            onClick={async () => { setBusy("guardian"); try { const r = await axios.post(`${API}/api/guardian/revisar-ahora`); setMsg(`🧠 ${r.data.reporte}`); load(); } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); } setBusy(""); }}
            style={{ background: "transparent", border: "1px solid rgba(192,132,252,0.5)", color: "#c084fc",
              padding: "0.3rem 0.9rem", cursor: "pointer", borderRadius: 8, fontSize: "0.66rem", fontWeight: 800 }}>
            {busy === "guardian" ? "Pensando…" : "🧠 Llamar Guardián Lógico"}</button>
        </div>
        {!(data?.fallas || []).length && (
          <div style={{ color: "#4ade80", fontSize: "0.76rem" }} data-testid="sin-fallas">
            ✅ Sin fallas pendientes — el sistema está sano. El vigía sigue observando.</div>
        )}
        {(data?.fallas || []).map(f => (
          <div key={f.id} data-testid={`falla-${f.id}`} style={{ display: "flex", gap: 12, alignItems: "center",
            flexWrap: "wrap", padding: "0.55rem 0", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
            <span style={{ fontSize: "1.1rem" }}>💔</span>
            <div style={{ flex: 1, minWidth: 240 }}>
              <div style={{ color: "#fecaca", fontSize: "0.76rem", fontWeight: 700 }}>{f.tipo_falla.replace(/_/g, " ").toUpperCase()}</div>
              <div style={{ color: "#cbd5e1", fontSize: "0.72rem" }}>{f.descripcion}</div>
              <div style={{ color: "#6b7280", fontSize: "0.62rem" }}>{(f.created_at || "").slice(0, 16).replace("T", " ")}</div>
            </div>
            <button data-testid={`btn-reparar-falla-${f.id}`} disabled={!!busy}
              onClick={() => ejecutar(f.herramienta_recomendada, f.params, f.id)}
              style={{ background: "linear-gradient(135deg,#BF953F,#FCF6BA)", color: "#0a0a0a", border: "none",
                borderRadius: 20, padding: "0.45rem 1.1rem", cursor: "pointer", fontWeight: 900, fontSize: "0.7rem" }}>
              🔨 Reparar con oro — 1 click</button>
            <button onClick={async () => { await axios.post(`${API}/api/martin/fallas/${f.id}/descartar`); load(); }}
              style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.15)", color: "#9ca3af",
                borderRadius: 20, padding: "0.45rem 0.8rem", cursor: "pointer", fontSize: "0.64rem" }}>Descartar</button>
          </div>
        ))}
      </div>

      <div style={panel} data-testid="herramientas-libres">
        <div style={{ color: "#4ade80", fontSize: "0.72rem", fontWeight: 800, letterSpacing: "0.12em", marginBottom: 8 }}>
          🔓 HERRAMIENTAS LIBRES — sin pedir permiso</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(210px, 1fr))", gap: 8 }}>
          {HERR_LIBRES.map(h => (
            <button key={h.id} data-testid={`herr-${h.id}`} disabled={busy === h.id} onClick={() => clickHerr(h)}
              style={{ background: "rgba(74,222,128,0.06)", border: "1px solid rgba(74,222,128,0.3)",
                color: "#e2e8f0", borderRadius: 10, padding: "0.65rem 0.6rem", cursor: "pointer",
                fontSize: "0.7rem", fontWeight: 700, textAlign: "left" }}>
              {h.icono} {busy === h.id ? "Reparando…" : h.label}</button>
          ))}
        </div>
      </div>

      <div style={{ ...panel, borderColor: "rgba(220,38,38,0.45)" }} data-testid="herramientas-protegidas">
        <div style={{ color: "#f87171", fontSize: "0.72rem", fontWeight: 800, letterSpacing: "0.12em", marginBottom: 8 }}>
          🔒 PROTEGIDO — requiere autorización de Gerardo</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(210px, 1fr))", gap: 8 }}>
          {HERR_PROTEGIDAS.map(h => (
            <button key={h.id} data-testid={`herr-${h.id}`} disabled={busy === h.id}
              onClick={() => ejecutar(h.id, {})}
              style={{ background: "rgba(220,38,38,0.07)", border: "1px solid rgba(220,38,38,0.4)",
                color: "#fecaca", borderRadius: 10, padding: "0.65rem 0.6rem", cursor: "pointer",
                fontSize: "0.7rem", fontWeight: 700, textAlign: "left" }}>
              {h.icono} {h.label}</button>
          ))}
        </div>
        <div style={{ color: "#9ca3af", fontSize: "0.62rem", marginTop: 6 }}>
          Al pulsar NO se ejecuta nada: se crea una solicitud en la bandeja de Gerardo (/Blindaje Correos → Autorizar).</div>
      </div>

      <div style={panel} data-testid="mejorar-sistema">
        <div style={{ color: ORO, fontSize: "0.72rem", fontWeight: 800, letterSpacing: "0.12em", marginBottom: 8 }}>
          ➕ MEJORAR SISTEMA — libertad total</div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input data-testid="input-mejora" placeholder="¿Qué mejorar? (se agrega al cerebro del clasificador al instante)"
            value={mejora} onChange={e => setMejora(e.target.value)}
            style={{ flex: "1 1 320px", background: "rgba(255,255,255,0.06)", border: `1px solid ${ORO}44`,
              color: "#fff", padding: "0.55rem 0.7rem", borderRadius: 8, fontSize: "0.76rem" }} />
          <button data-testid="btn-mejora" onClick={proponerMejora} disabled={busy === "mejora"}
            style={{ background: "linear-gradient(135deg,#BF953F,#FCF6BA)", color: "#0a0a0a", border: "none",
              borderRadius: 8, padding: "0.55rem 1.2rem", cursor: "pointer", fontWeight: 900, fontSize: "0.72rem" }}>
            ✨ Incorporar mejora</button>
        </div>
      </div>

      <div style={panel} data-testid="galeria-kintsugi">
        <div style={{ color: ORO, fontSize: "0.72rem", fontWeight: 800, letterSpacing: "0.12em", marginBottom: 8 }}>
          🏺 GALERÍA KINTSUGI — historial de lo roto que quedó mejor</div>
        <div style={{ maxHeight: 380, overflowY: "auto" }}>
          {(data?.historial || []).map(h => (
            <div key={h.id} style={{ padding: "0.5rem 0", borderBottom: "1px solid rgba(212,175,55,0.14)" }}>
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center", fontSize: "0.7rem" }}>
                <span style={{ color: "#6b7280" }}>{(h.created_at || "").slice(0, 16).replace("T", " ")}</span>
                <b style={{ color: "#FCF6BA" }}>{h.reparador}</b>
                <span style={{ color: "#fca5a5" }}>{(h.tipo_falla || "").replace(/_/g, " ")}</span>
                <span style={{ color: "#9ca3af" }}>{(h.herramienta_usada || "").replace(/_/g, " ")}</span>
                {h.cliente_rut && <span style={{ color: "#cbd5e1" }}>{h.cliente_rut}</span>}
                <span style={{ color: "#6b7280" }}>{h.tiempo_reparacion_ms ? `${h.tiempo_reparacion_ms} ms` : ""}</span>
                {h.quedo_con_oro && <span style={{ marginLeft: "auto", background: "linear-gradient(135deg,#BF953F,#FCF6BA)",
                  color: "#0a0a0a", padding: "0.08rem 0.55rem", borderRadius: 20, fontSize: "0.6rem", fontWeight: 900 }}>
                  Quedó con oro ✨</span>}
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 4, fontSize: "0.66rem", flexWrap: "wrap" }}>
                <span style={{ color: "#fca5a5", background: "rgba(220,38,38,0.08)", padding: "0.15rem 0.5rem", borderRadius: 6 }}>
                  {JSON.stringify(h.antes || {}).slice(0, 90)}</span>
                <span style={{ color: ORO, fontWeight: 900 }}>━━✨━━▶</span>
                <span style={{ color: "#a7f3d0", background: "rgba(74,222,128,0.08)", padding: "0.15rem 0.5rem", borderRadius: 6 }}>
                  {JSON.stringify(h.despues || {}).slice(0, 90)}</span>
              </div>
            </div>
          ))}
          {!(data?.historial || []).length && <div style={{ color: "#6b7280", fontSize: "0.72rem" }}>Aún no hay reparaciones — todo sano.</div>}
        </div>
      </div>

      {pedir && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", zIndex: 3000,
          display: "flex", alignItems: "center", justifyContent: "center" }} data-testid="modal-params">
          <div style={{ ...panel, width: "min(480px, 92vw)" }}>
            <h3 style={{ color: ORO, marginTop: 0, fontSize: "0.95rem" }}>{pedir.icono} {pedir.label}</h3>
            <input data-testid="param-input" autoFocus value={inputVal} onChange={e => setInputVal(e.target.value)}
              placeholder={pedir.pide === "message_id" ? "ID del correo (ej: secundaria|1234)"
                : pedir.pide === "cola_id" ? "ID del registro en la cola" : "caso_id o RUT del cliente"}
              style={{ width: "100%", boxSizing: "border-box", background: "rgba(255,255,255,0.06)",
                border: `1px solid ${ORO}44`, color: "#fff", padding: "0.55rem", borderRadius: 8, marginBottom: 8 }} />
            {pedir.pide === "caso_protocolo" && (
              <select data-testid="param-protocolo" value={protoSel} onChange={e => setProtoSel(e.target.value)}
                style={{ width: "100%", background: "#1a1a1e", border: `1px solid ${ORO}44`, color: "#fff",
                  padding: "0.5rem", borderRadius: 8, marginBottom: 8 }}>
                {PROTOS.map(p => <option key={p} value={p}>{p.replace(/_/g, " ")}</option>)}
              </select>
            )}
            <div style={{ display: "flex", gap: 8 }}>
              <button data-testid="param-confirmar" onClick={confirmarPedir} disabled={!inputVal.trim()}
                style={{ background: "linear-gradient(135deg,#BF953F,#FCF6BA)", color: "#0a0a0a", border: "none",
                  borderRadius: 8, padding: "0.5rem 1.1rem", cursor: "pointer", fontWeight: 900 }}>🔨 Reparar con oro</button>
              <button onClick={() => setPedir(null)} style={{ background: "transparent",
                border: "1px solid rgba(255,255,255,0.2)", color: "#cbd5e1", borderRadius: 8,
                padding: "0.5rem 1rem", cursor: "pointer" }}>Cancelar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
