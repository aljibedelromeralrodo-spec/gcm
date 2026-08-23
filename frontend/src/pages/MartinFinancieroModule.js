import { useState, useEffect, useRef } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
// Paleta inspirada en Suma UC (educación financiera universitaria): azul confianza + amarillo energía
const AZUL = "#1e3a8a", CELESTE = "#38bdf8", AMARILLO = "#facc15", CREMA = "#fefce8";

export default function MartinFinancieroModule() {
  const [msgs, setMsgs] = useState([{ rol: "martin", texto: "¡Hola! Soy Martín, su asistente de educación financiera 💛 Puedo ayudarle con las finanzas de su hogar, subsidios habitacionales (DS49, DS1, DS19), beneficios del Estado, trámites financieros y también con el manejo del estrés económico. Estoy aquí para escucharle y orientarle, sin tecnicismos y sin juicios. ¿Sobre qué le gustaría conversar hoy?" }]);
  const [input, setInput] = useState("");
  const [temas, setTemas] = useState([]);
  const [cargando, setCargando] = useState(false);
  const [voz, setVoz] = useState(true);
  const [exps, setExps] = useState([]);
  const [expActiva, setExpActiva] = useState(null);
  const audioRef = useRef(null);
  const cancelRef = useRef(false);
  const [sessionId] = useState(() => `mf-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`);
  const endRef = useRef(null);

  useEffect(() => { axios.get(`${API}/api/martin-financiero/temas`).then(r => setTemas(r.data.temas || [])).catch(() => {}); }, []);
  useEffect(() => { axios.get(`${API}/api/martin-financiero/experiencias`).then(r => setExps(r.data.experiencias || [])).catch(() => {}); }, []);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, cargando]);

  const hablar = async (texto) => {
    if (!voz) return;
    try {
      const r = await axios.post(`${API}/api/central/tts`, { text: texto });
      if (r.data?.audio) new Audio(`data:audio/mp3;base64,${r.data.audio}`).play();
    } catch { /* voz opcional */ }
  };

  const hablarYEsperar = (texto) => new Promise((res) => {
    axios.post(`${API}/api/central/tts`, { text: texto }).then(r => {
      if (!r.data?.audio) return res();
      const a = new Audio(`data:audio/mp3;base64,${r.data.audio}`);
      audioRef.current = a; a.onended = res; a.onerror = res;
      a.play().catch(res);
    }).catch(res);
  });

  const detenerExp = () => {
    cancelRef.current = true;
    if (audioRef.current) audioRef.current.pause();
    setExpActiva(null);
    setMsgs(m => [...m, { rol: "martin", texto: "Experiencia detenida. Cuando quiera, retomamos con calma." }]);
  };

  const iniciarExp = async (id) => {
    if (expActiva) return;
    cancelRef.current = false;
    try {
      const r = await axios.get(`${API}/api/martin-financiero/experiencias/${id}`);
      const e = r.data;
      setExpActiva(e.id);
      setMsgs(m => [...m, { rol: "martin", texto: `🧘 Comenzamos "${e.titulo}" (${e.min} min aprox.). Busque un lugar tranquilo. Puede detener cuando quiera.` }]);
      for (const p of e.pasos) {
        if (cancelRef.current) break;
        setMsgs(m => [...m, { rol: "martin", texto: p.texto }]);
        await hablarYEsperar(p.texto);
        if (cancelRef.current) break;
        if (p.pausa) await new Promise(res => setTimeout(res, p.pausa * 1000));
      }
      if (!cancelRef.current) setMsgs(m => [...m, { rol: "martin", texto: "✨ Hemos terminado. Gracias por regalarse este momento; llévelo con usted al resto del día." }]);
    } catch { /* red */ }
    setExpActiva(null);
  };

  const enviar = async (texto) => {
    const t = (texto || input).trim();
    if (!t || cargando) return;
    setInput("");
    setMsgs(m => [...m, { rol: "usuario", texto: t }]);
    setCargando(true);
    try {
      const r = await axios.post(`${API}/api/martin-financiero/chat`, { message: t, session_id: sessionId });
      setMsgs(m => [...m, { rol: "martin", texto: r.data.response }]);
      hablar(r.data.response);
    } catch (e) {
      setMsgs(m => [...m, { rol: "martin", texto: "Disculpe, tuve un problema para responderle. ¿Puede intentarlo nuevamente?" }]);
    } finally { setCargando(false); }
  };

  return (
    <div data-testid="martin-financiero-module" style={{ minHeight: "100%", background: `linear-gradient(180deg, ${AZUL} 0%, #14275f 100%)`, padding: "0.8rem", display: "flex", flexDirection: "column", maxWidth: 860, margin: "0 auto", borderRadius: 18 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "0.6rem 0.4rem", flexWrap: "wrap" }}>
        <div style={{ width: 54, height: 54, borderRadius: "50%", background: AMARILLO, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 26, boxShadow: `0 0 0 3px ${CELESTE}` }}>🧑‍🏫</div>
        <div style={{ flex: 1, minWidth: 200 }}>
          <h2 style={{ color: "#fff", margin: 0, fontSize: "1.15rem" }}>Martín — Asistente Financiero</h2>
          <p style={{ color: CELESTE, fontSize: "0.68rem", margin: 0, fontWeight: 700, letterSpacing: 1 }}>EDUCACIÓN FINANCIERA PARA SU HOGAR · RESPONSABILIDAD SOCIAL CENTRAL MUTUOS</p>
        </div>
        <button data-testid="mf-voz-toggle" onClick={() => setVoz(!voz)}
          style={{ background: voz ? AMARILLO : "rgba(255,255,255,0.15)", color: voz ? AZUL : "#fff", border: 0, borderRadius: 999, padding: "0.5rem 1rem", fontWeight: 800, cursor: "pointer", fontSize: "0.72rem" }}>
          {voz ? "🔊 Voz activada" : "🔇 Voz apagada"}</button>
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", padding: "0.4rem" }} data-testid="mf-temas">
        {temas.map(t => (
          <button key={t.titulo} data-testid={`mf-tema-${t.titulo.toLowerCase()}`} onClick={() => enviar(t.pregunta)}
            style={{ background: "rgba(255,255,255,0.1)", border: `1.5px solid ${CELESTE}55`, color: "#fff", borderRadius: 999, padding: "0.45rem 0.95rem", cursor: "pointer", fontSize: "0.72rem", fontWeight: 700 }}>
            {t.icono} {t.titulo}</button>
        ))}
      </div>

      <div style={{ padding: "0.2rem 0.4rem 0.4rem" }} data-testid="mf-experiencias">
        <p style={{ color: AMARILLO, fontSize: "0.64rem", fontWeight: 800, letterSpacing: 1, margin: "4px 0 6px" }}>🧘 EXPERIENCIAS GUIADAS CON LA VOZ DE MARTÍN (3–7 MIN)</p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {exps.map(e => (
            <button key={e.id} data-testid={`mf-exp-${e.id}`} onClick={() => iniciarExp(e.id)} disabled={!!expActiva} title={e.proposito}
              style={{ background: expActiva === e.id ? AMARILLO : "rgba(250,204,21,0.12)", border: `1.5px solid ${AMARILLO}66`, color: expActiva === e.id ? AZUL : "#fde68a", borderRadius: 999, padding: "0.45rem 0.9rem", cursor: expActiva ? "default" : "pointer", fontSize: "0.7rem", fontWeight: 700, opacity: expActiva && expActiva !== e.id ? 0.4 : 1 }}>
              {e.icono} {e.titulo} · {e.min} min</button>
          ))}
          {expActiva && (
            <button data-testid="mf-exp-detener" onClick={detenerExp}
              style={{ background: "#dc2626", color: "#fff", border: 0, borderRadius: 999, padding: "0.45rem 1rem", cursor: "pointer", fontSize: "0.7rem", fontWeight: 800 }}>⏹ Detener</button>
          )}
        </div>
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "0.6rem 0.4rem", minHeight: 340, maxHeight: 480 }} data-testid="mf-chat">
        {msgs.map((m, i) => (
          <div key={i} style={{ display: "flex", justifyContent: m.rol === "usuario" ? "flex-end" : "flex-start", marginBottom: 10 }}>
            <div data-testid={`mf-msg-${i}`} style={{
              maxWidth: "82%", padding: "0.7rem 0.95rem", fontSize: "0.82rem", lineHeight: 1.6, whiteSpace: "pre-wrap",
              background: m.rol === "usuario" ? AMARILLO : CREMA, color: "#1f2937",
              borderRadius: m.rol === "usuario" ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
              boxShadow: "0 2px 8px rgba(0,0,0,0.25)" }}>
              {m.rol === "martin" && <b style={{ color: AZUL, display: "block", fontSize: "0.66rem", marginBottom: 3 }}>MARTÍN 💛</b>}
              {m.texto}
            </div>
          </div>
        ))}
        {cargando && <p style={{ color: CELESTE, fontSize: "0.72rem" }}>Martín está pensando…</p>}
        <div ref={endRef} />
      </div>

      <div style={{ display: "flex", gap: 8, padding: "0.5rem 0.4rem" }}>
        <input data-testid="mf-input" style={{ flex: 1, background: "#fff", border: 0, borderRadius: 999, padding: "0.75rem 1.1rem", fontSize: "0.82rem", color: "#111" }}
          placeholder="Escríbale su pregunta a Martín…" value={input}
          onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && enviar()} />
        <button data-testid="mf-enviar" onClick={() => enviar()} disabled={cargando}
          style={{ background: AMARILLO, color: AZUL, border: 0, borderRadius: 999, padding: "0.75rem 1.4rem", fontWeight: 900, cursor: "pointer", fontSize: "0.82rem" }}>Enviar ➤</button>
      </div>
      <p style={{ color: "rgba(255,255,255,0.55)", fontSize: "0.6rem", textAlign: "center", margin: "4px 0 2px" }}>
        Martín entrega educación financiera general, no asesoría personalizada ni oferta comercial · Diseñado para exportarse como app móvil independiente</p>
    </div>
  );
}
