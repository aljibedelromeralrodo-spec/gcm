import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const ORO = "#d4af37";
const panel = { background: "rgba(20,20,24,0.92)", border: "1px solid rgba(212,175,55,0.3)",
  borderRadius: 14, padding: "1.1rem 1.3rem", marginBottom: "1rem" };

const ScoreCircular = ({ score }) => {
  const color = score >= 80 ? "#4ade80" : score >= 60 ? "#fbbf24" : "#f87171";
  return (
    <div style={{ position: "relative", width: 130, height: 130 }} data-testid="score-circular">
      <svg width="130" height="130">
        <circle cx="65" cy="65" r="56" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="10" />
        <circle cx="65" cy="65" r="56" fill="none" stroke={color} strokeWidth="10" strokeLinecap="round"
          strokeDasharray={`${(score / 100) * 351.8} 351.8`} transform="rotate(-90 65 65)" />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center" }}>
        <div style={{ fontSize: "1.7rem", fontWeight: 900, color }}>{score}%</div>
        <div style={{ fontSize: "0.55rem", color: "#9ca3af", letterSpacing: "0.1em" }}>LÓGICO SIMPLE</div>
      </div>
    </div>
  );
};

export default function GuardianLogicoModule() {
  const [data, setData] = useState(null);
  const [vivo, setVivo] = useState(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState("");
  const [nodoSel, setNodoSel] = useState(null);

  const load = useCallback(async () => {
    try {
      const [r, v] = await Promise.all([
        axios.get(`${API}/api/guardian/estado`),
        axios.get(`${API}/api/tema-vivo/estado`),
      ]);
      setData(r.data); setVivo(v.data);
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 45000); return () => clearInterval(t); }, [load]);

  const revisarTodo = async () => {
    setBusy("todo");
    try {
      const r = await axios.post(`${API}/api/guardian/revisar-ahora`);
      setMsg(`🧠 ${r.data.reporte} (${r.data.ms} ms)`);
      load();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setBusy("");
  };
  const simplificar = async (nid) => {
    setBusy(nid);
    try {
      const r = await axios.post(`${API}/api/guardian/nudos/${nid}/simplificar`);
      setMsg(r.data.mensaje); load();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setBusy("");
  };

  const pasarMesa = async (nid) => {
    setBusy(nid);
    try {
      const r = await axios.post(`${API}/api/tema-vivo/mesa/${nid}/pasar`);
      setMsg(r.data.mensaje); load();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setBusy("");
  };
  const masTarde = async (nid) => {
    await axios.post(`${API}/api/tema-vivo/mesa/${nid}/mas-tarde`); load();
  };
  const hambreAhora = async () => {
    setBusy("hambre");
    try {
      const r = await axios.post(`${API}/api/tema-vivo/hambre-ahora`);
      setMsg(`🌙 Hambre nocturna: score ${r.data.score_antes}→${r.data.score_despues}. Aprendí: ${r.data.aprendi}`.slice(0, 220));
      load();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setBusy("");
  };

  const s = data?.score || {};
  return (
    <div data-testid="guardian-module" style={{ padding: "0.4rem 0" }}>
      <div style={{ ...panel, display: "flex", gap: 22, alignItems: "center", flexWrap: "wrap",
        background: "linear-gradient(135deg, rgba(20,20,24,0.95), rgba(30,35,60,0.4))" }}>
        <ScoreCircular score={s.total ?? 0} />
        <div style={{ flex: 1, minWidth: 260 }}>
          <h2 style={{ color: ORO, margin: 0, fontSize: "1.1rem" }}>🫀 Tema Vivo — Guardián Lógico</h2>
          <div style={{ color: "#cbd5e1", fontSize: "0.74rem", margin: "4px 0 6px" }}>
            Sistema simple, sencillo y fluido. Detecta lo que da vueltas, simplifica a una sola verdad
            y <b style={{ color: "#FCF6BA" }}>sabe cuándo retroceder</b>.</div>
          <div data-testid="banner-fase1" style={{ color: "#FCF6BA", fontSize: "0.64rem", fontWeight: 800,
            background: "rgba(212,175,55,0.12)", border: "1px solid rgba(212,175,55,0.3)",
            borderRadius: 8, padding: "0.3rem 0.6rem", marginBottom: 8, display: "inline-block" }}>
            {vivo?.restriccion || "FASE 1 — Masivo >10 BLOQUEADO"}</div>
          <div style={{ display: "flex", gap: 14, flexWrap: "wrap", fontSize: "0.7rem" }}>
            <span data-testid="kpi-simplicidad" style={{ color: "#4ade80" }}>Simplicidad {s.simplicidad}%</span>
            <span data-testid="kpi-logica" style={{ color: "#60a5fa" }}>Lógica {s.logica}%</span>
            <span data-testid="kpi-fluidez" style={{ color: "#c084fc" }}>Fluidez {s.fluidez}% ({s.fluidez_seg || 0}s entrada→mesa)</span>
            <span style={{ color: "#f87171" }}>Nudos activos: {s.nudos ?? 0}</span>
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <button data-testid="btn-revisar-todo" onClick={revisarTodo} disabled={busy === "todo"}
            style={{ background: "linear-gradient(135deg,#BF953F,#FCF6BA)", color: "#0a0a0a", border: "none",
              borderRadius: 12, padding: "0.7rem 1.3rem", cursor: "pointer", fontWeight: 900, fontSize: "0.74rem" }}>
            {busy === "todo" ? "🧠 Pensando…" : "🧹 Revisar y Simplificar Todo"}</button>
          <button data-testid="btn-hambre-ahora" onClick={hambreAhora} disabled={busy === "hambre"}
            style={{ background: "transparent", border: "1px solid rgba(192,132,252,0.5)", color: "#c084fc",
              borderRadius: 12, padding: "0.55rem 1.3rem", cursor: "pointer", fontWeight: 800, fontSize: "0.7rem" }}>
            {busy === "hambre" ? "🌙 Aprendiendo…" : "🌙 Hambre nocturna ahora"}</button>
        </div>
      </div>
      {msg && <div data-testid="guardian-msg" style={{ ...panel, color: "#FCF6BA", fontSize: "0.78rem", padding: "0.6rem 1rem" }}>{msg}</div>}

      <div style={{ ...panel, borderColor: "rgba(212,175,55,0.6)" }} data-testid="seccion-mesa-pendiente">
        <div style={{ color: ORO, fontSize: "0.72rem", fontWeight: 800, letterSpacing: "0.12em", marginBottom: 8 }}>
          💬 ¿LA PASO A MESA? — autorización chica, 1 click</div>
        {!(vivo?.notificaciones || []).length && (
          <div style={{ color: "#9ca3af", fontSize: "0.74rem" }} data-testid="sin-mesa-pendiente">
            Sin carpetas esperando tu click. Cuando una llegue a 6/6, Martín te preguntará aquí.</div>)}
        {(vivo?.notificaciones || []).map(n => (
          <div key={n.id} data-testid={`mesa-card-${n.id}`} style={{ background: "rgba(212,175,55,0.07)",
            border: "1.5px solid rgba(212,175,55,0.45)", borderRadius: 12, padding: "0.9rem 1rem", marginBottom: 10 }}>
            <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", marginBottom: 6 }}>
              <span style={{ fontSize: "1.2rem" }}>🔔</span>
              <b style={{ color: "#FCF6BA", fontSize: "0.8rem" }}>{n.cliente_nombre || n.cliente_rut}</b>
              <span style={{ background: "linear-gradient(135deg,#BF953F,#FCF6BA)", color: "#0a0a0a",
                padding: "0.1rem 0.55rem", borderRadius: 20, fontSize: "0.62rem", fontWeight: 900 }}>{n.barra}</span>
              {n.reparada_con_oro && <span style={{ color: ORO, fontSize: "0.62rem", fontWeight: 800 }}>✨ Reparada con oro</span>}
              <span style={{ marginLeft: "auto", color: "#6b7280", fontSize: "0.62rem" }}>
                {(n.created_at || "").slice(0, 16).replace("T", " ")}</span>
            </div>
            <div style={{ color: "#e2e8f0", fontSize: "0.78rem", fontStyle: "italic", marginBottom: 10 }}>
              “{n.mensaje_vivo}”</div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button data-testid={`btn-si-mesa-${n.id}`} disabled={busy === n.id} onClick={() => pasarMesa(n.id)}
                style={{ background: "linear-gradient(135deg,#166534,#22c55e)", color: "#fff", border: "none",
                  borderRadius: 8, padding: "0.5rem 1.2rem", cursor: "pointer", fontWeight: 900, fontSize: "0.72rem" }}>
                {busy === n.id ? "Pasando…" : "✅ Sí, pásala a mesa"}</button>
              <button data-testid={`btn-tarde-${n.id}`} onClick={() => masTarde(n.id)}
                style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.2)", color: "#cbd5e1",
                  borderRadius: 8, padding: "0.5rem 1rem", cursor: "pointer", fontSize: "0.72rem" }}>⏰ Más tarde</button>
            </div>
          </div>
        ))}
      </div>

      <div style={panel} data-testid="seccion-espejo">
        <div style={{ color: "#60a5fa", fontSize: "0.72rem", fontWeight: 800, letterSpacing: "0.12em", marginBottom: 8 }}>
          🪞 ESPEJO DE PENSAMIENTO — cómo piensa el sistema</div>
        <div style={{ maxHeight: 300, overflowY: "auto" }}>
          {(vivo?.pensamientos || []).map(p => (
            <div key={p.id} style={{ display: "flex", gap: 8, marginBottom: 8, alignItems: "flex-start" }}>
              <span style={{ fontSize: "0.9rem" }}>{p.origen === "backtracking" ? "↩️" : "💭"}</span>
              <div style={{ background: "rgba(96,165,250,0.08)", border: "1px solid rgba(96,165,250,0.2)",
                borderRadius: "2px 12px 12px 12px", padding: "0.45rem 0.7rem", fontSize: "0.7rem",
                color: "#dbeafe", flex: 1 }}>
                {p.pensamiento}
                <div style={{ color: "#6b7280", fontSize: "0.58rem", marginTop: 3 }}>
                  {(p.created_at || "").slice(0, 16).replace("T", " ")}
                  {p.retrocedio_a || p.retrocede_a ? " · retrocedió donde había que retroceder ✅" : ""}</div>
              </div>
            </div>
          ))}
          {!(vivo?.pensamientos || []).length && <div style={{ color: "#6b7280", fontSize: "0.72rem" }}>Aún sin pensamientos registrados.</div>}
        </div>
      </div>

      <div style={panel} data-testid="seccion-hambre">
        <div style={{ color: "#c084fc", fontSize: "0.72rem", fontWeight: 800, letterSpacing: "0.12em", marginBottom: 8 }}>
          🌙 HAMBRE NOCTURNA 3AM — lo que aprendió solo</div>
        {(vivo?.hambre || []).map(h => (
          <div key={h.id} style={{ padding: "0.45rem 0", borderBottom: "1px solid rgba(255,255,255,0.05)", fontSize: "0.7rem" }}>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <b style={{ color: "#e2e8f0" }}>{h.fecha}</b>
              <span style={{ color: "#c084fc" }}>{h.nudo_detectado}</span>
              <span style={{ marginLeft: "auto", fontWeight: 900,
                color: h.score_despues >= h.score_antes ? "#4ade80" : "#fbbf24" }}>
                {h.score_antes}% → {h.score_despues}% ✨</span>
            </div>
            <div style={{ color: "#9ca3af" }}>Aprendí: {h.que_aprendi}</div>
          </div>
        ))}
        {!(vivo?.hambre || []).length && <div style={{ color: "#6b7280", fontSize: "0.72rem" }}>Primera hambre esta madrugada a las 03:00 (o pruébala con el botón 🌙).</div>}
      </div>

      <div style={{ ...panel, borderColor: "rgba(212,175,55,0.5)" }} data-testid="seccion-orgullo">
        <div style={{ color: ORO, fontSize: "0.72rem", fontWeight: 800, letterSpacing: "0.12em", marginBottom: 8 }}>
          🏺 ORGULLO DE ORO — cicatrices doradas, quedó más fuerte</div>
        <div style={{ maxHeight: 260, overflowY: "auto" }}>
          {(vivo?.orgullo_oro || []).map(h => (
            <div key={h.id} style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap",
              fontSize: "0.66rem", padding: "0.35rem 0", borderBottom: "1px solid rgba(212,175,55,0.12)" }}>
              <span style={{ color: "#6b7280" }}>{(h.created_at || "").slice(0, 16).replace("T", " ")}</span>
              <span style={{ color: "#fca5a5" }}>{(h.tipo_falla || "").replace(/_/g, " ")}</span>
              {h.cliente_rut && <b style={{ color: "#e2e8f0" }}>{h.cliente_rut}</b>}
              <span style={{ color: "#fca5a5", background: "rgba(220,38,38,0.08)", padding: "0.1rem 0.45rem",
                borderRadius: 6 }}>{JSON.stringify(h.antes || {}).slice(0, 60)}</span>
              <span style={{ color: ORO, fontWeight: 900 }}>━✨━▶</span>
              <span style={{ color: "#a7f3d0", background: "rgba(74,222,128,0.08)", padding: "0.1rem 0.45rem",
                borderRadius: 6 }}>{JSON.stringify(h.despues || {}).slice(0, 60)}</span>
            </div>
          ))}
        </div>
      </div>

      <div style={panel} data-testid="flujo-unico">
        <div style={{ color: ORO, fontSize: "0.72rem", fontWeight: 800, letterSpacing: "0.12em", marginBottom: 10 }}>
          🗺️ FLUJO LÓGICO ÚNICO VERDAD</div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "stretch" }}>
          {(data?.flujo || []).map((f, i) => (
            <React.Fragment key={f.paso}>
              <div data-testid={`nodo-${f.paso}`} onClick={() => setNodoSel(nodoSel === f.paso ? null : f.paso)}
                style={{ flex: "1 1 120px", minWidth: 118, background: nodoSel === f.paso ? "rgba(212,175,55,0.15)" : "rgba(255,255,255,0.04)",
                  border: `1px solid ${nodoSel === f.paso ? ORO : "rgba(212,175,55,0.25)"}`, borderRadius: 10,
                  padding: "0.55rem", cursor: "pointer", textAlign: "center" }}>
                <div style={{ fontSize: "1.1rem" }}>{f.icono}</div>
                <div style={{ color: "#e2e8f0", fontSize: "0.62rem", fontWeight: 800 }}>{f.nombre}</div>
                {nodoSel === f.paso && <div style={{ color: "#9ca3af", fontSize: "0.58rem", marginTop: 4 }}>{f.detalle}</div>}
              </div>
              {i < (data?.flujo || []).length - 1 && (
                <div style={{ alignSelf: "center", color: ORO, fontWeight: 900 }}>→</div>)}
            </React.Fragment>
          ))}
        </div>
      </div>

      <div style={panel} data-testid="seccion-nudos">
        <div style={{ color: "#f87171", fontSize: "0.72rem", fontWeight: 800, letterSpacing: "0.12em", marginBottom: 8 }}>
          🪢 NUDOS DETECTADOS — lo que está dando vueltas</div>
        {!(data?.nudos || []).length && (
          <div style={{ color: "#4ade80", fontSize: "0.76rem" }} data-testid="sin-nudos">
            ✅ Sin nudos — el sistema fluye en una sola verdad.</div>)}
        {(data?.nudos || []).map(n => (
          <div key={n.id} style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap",
            padding: "0.5rem 0", borderBottom: "1px solid rgba(255,255,255,0.06)" }} data-testid={`nudo-${n.id}`}>
            <span>🪢</span>
            <div style={{ flex: 1, minWidth: 240 }}>
              <div style={{ color: "#fecaca", fontSize: "0.74rem", fontWeight: 700 }}>{n.nombre}</div>
              <div style={{ color: "#cbd5e1", fontSize: "0.68rem" }}>{n.hace}</div>
            </div>
            <span style={{ color: n.complejidad >= 7 ? "#f87171" : "#fbbf24", fontSize: "0.66rem", fontWeight: 800 }}>
              Complejidad {n.complejidad}/10</span>
            <button data-testid={`btn-simplificar-${n.id}`} disabled={!!busy} onClick={() => simplificar(n.id)}
              style={{ background: "linear-gradient(135deg,#BF953F,#FCF6BA)", color: "#0a0a0a", border: "none",
                borderRadius: 20, padding: "0.4rem 1rem", cursor: "pointer", fontWeight: 900, fontSize: "0.66rem" }}>
              ✨ Simplificar con oro — 1 click</button>
          </div>
        ))}
      </div>

      <div style={panel} data-testid="seccion-backtracking">
        <div style={{ color: "#c084fc", fontSize: "0.72rem", fontWeight: 800, letterSpacing: "0.12em", marginBottom: 8 }}>
          ↩️ BACKTRACKING — donde la mente humana supo retroceder</div>
        <div style={{ maxHeight: 340, overflowY: "auto" }}>
          {(data?.backtracking || []).map(b => (
            <div key={b.id} style={{ padding: "0.45rem 0", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap", fontSize: "0.68rem", alignItems: "center" }}>
                <span style={{ color: "#6b7280" }}>{(b.created_at || "").slice(0, 16).replace("T", " ")}</span>
                {b.cliente_rut && <b style={{ color: "#e2e8f0" }}>{b.cliente_rut}</b>}
                <span style={{ color: "#fbbf24" }}>paso: {b.paso_actual}</span>
                <span style={{ color: "#c084fc" }}>↩ retrocede a: {b.retrocede_a}</span>
                <span style={{ marginLeft: "auto", color: b.quedo_logico ? "#4ade80" : "#f87171", fontWeight: 800 }}>
                  {b.quedo_logico ? "Quedó lógico ✅" : "Pendiente ⚠️"}</span>
                <span style={{ color: "#6b7280" }}>{b.tiempo_ms} ms</span>
              </div>
              <div style={{ fontSize: "0.68rem", color: "#fca5a5" }}>💭 {b.incoherencia_detectada}</div>
              <div style={{ fontSize: "0.68rem", color: "#a7f3d0" }}>🔧 {b.correccion_aplicada}</div>
            </div>
          ))}
          {!(data?.backtracking || []).length && (
            <div style={{ color: "#6b7280", fontSize: "0.72rem" }}>Sin retrocesos aún — todo ha fluido lógico.</div>)}
        </div>
      </div>

      <div style={panel} data-testid="seccion-mapa">
        <div style={{ color: ORO, fontSize: "0.72rem", fontWeight: 800, letterSpacing: "0.12em", marginBottom: 8 }}>
          🧩 MAPA DE COMPONENTES (complejidad 1 = simple, 10 = enredado)</div>
        {(data?.mapa || []).map(m => (
          <div key={m.id} style={{ display: "flex", gap: 10, fontSize: "0.7rem", padding: "0.28rem 0",
            borderBottom: "1px solid rgba(255,255,255,0.04)", flexWrap: "wrap" }}>
            <span style={{ color: "#9ca3af", minWidth: 70 }}>{m.componente}</span>
            <b style={{ color: "#e2e8f0", minWidth: 190 }}>{m.nombre}</b>
            <span style={{ color: "#9ca3af", flex: 1 }}>{m.hace}</span>
            <span style={{ color: m.complejidad <= 3 ? "#4ade80" : "#fbbf24", fontWeight: 800 }}>{m.complejidad}/10</span>
          </div>
        ))}
      </div>
    </div>
  );
}
