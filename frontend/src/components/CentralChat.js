import { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import { elegirVozEspanol } from "../utils/vozMartin";

const API = process.env.REACT_APP_BACKEND_URL;
const CENTRAL_AVATAR = "/martin-avatar.jpeg";

let currentAudio = null;
let lastSpeakArgs = null;
let speakSession = 0;

// Divide el texto en trozos por FRASES COMPLETAS (nunca corta a mitad de frase).
// El primer trozo es más corto para que el audio comience casi de inmediato.
function splitSpeechChunks(texto, primerMax = 150, restoMax = 320) {
  const frases = texto.match(/[^.!?…]+[.!?…]+[\s]*|[^.!?…]+$/g) || [texto];
  const chunks = [];
  let cur = "";
  for (const f of frases) {
    const max = chunks.length === 0 ? primerMax : restoMax;
    if (cur && (cur + f).length > max) { chunks.push(cur.trim()); cur = f; }
    else cur += f;
  }
  if (cur.trim()) chunks.push(cur.trim());
  return chunks;
}

function pauseSpeaking() {
  if (currentAudio) { try { currentAudio.pause(); } catch (e) { console.error(e); } }
  else if (window.speechSynthesis?.speaking) window.speechSynthesis.pause();
}

function resumeSpeaking() {
  if (currentAudio) { try { currentAudio.play(); } catch (e) { console.error(e); } }
  else if (window.speechSynthesis?.paused) window.speechSynthesis.resume();
}

function restartSpeaking() {
  if (lastSpeakArgs) {
    speakText(lastSpeakArgs.text, lastSpeakArgs.onEnd);
  } else if (currentAudio) {
    try { currentAudio.currentTime = 0; currentAudio.play(); } catch (e) { console.error(e); }
  }
}

function renderTextWithLinks(text) {
  if (!text) return text;
  // Detect http(s) URLs AND absolute API paths like /api/...; transform both
  // into clickable anchors. Relative /api/... paths get the REACT_APP_BACKEND_URL
  // prefix so the link opens in a new tab pointing at the live backend.
  const linkRe = /(https?:\/\/[^\s)]+|\/api\/[^\s)]+)/g;
  const parts = String(text).split(linkRe);
  return parts.map((part, idx) => {
    if (part && /^(https?:\/\/|\/api\/)/.test(part)) {
      const href = part.startsWith("/api/") ? `${API}${part}` : part;
      return (
        <a key={idx} href={href} target="_blank" rel="noreferrer"
           className="central-msg-link" data-testid="central-msg-link"
           style={{ color: "#d4af37", textDecoration: "underline", wordBreak: "break-all" }}>
          {part}
        </a>
      );
    }
    return <span key={idx}>{part}</span>;
  });
}


async function speakText(text, onEnd) {
  let clean = text.replace(/[*#_>`]/g, "").replace(/\n+/g, ". ");
  if (clean.length > 4000) {
    const corte = Math.max(clean.lastIndexOf(". ", 4000), clean.lastIndexOf("! ", 4000), clean.lastIndexOf("? ", 4000));
    clean = corte > 0 ? clean.slice(0, corte + 1) : clean.slice(0, 4000);
  }
  lastSpeakArgs = { text, onEnd };
  stopSpeaking();
  const session = speakSession;

  // Pipeline por trozos: el primer trozo es corto (audio casi inmediato) y los
  // siguientes se sintetizan EN PARALELO mientras se reproduce el anterior.
  const chunks = splitSpeechChunks(clean);
  const fetches = chunks.map(c =>
    axios.post(`${API}/api/central/tts`, { text: c }).then(r => r.data?.audio || null).catch(() => null));

  for (let i = 0; i < chunks.length; i++) {
    if (session !== speakSession) return;
    const b64 = await fetches[i];
    if (session !== speakSession) return;
    if (!b64) {
      // Fallback navegador para lo que falta, en frases completas
      speakWithBrowser(chunks.slice(i).join(" "), session, onEnd);
      return;
    }
    const ok = await playB64(b64, session);
    if (!ok) return;
  }
  if (session === speakSession) onEnd?.();
}

function playB64(b64, session) {
  return new Promise(resolve => {
    if (session !== speakSession) return resolve(false);
    const audio = new Audio(`data:audio/mp3;base64,${b64}`);
    currentAudio = audio;
    audio.onended = () => { if (currentAudio === audio) currentAudio = null; resolve(session === speakSession); };
    audio.onerror = () => { if (currentAudio === audio) currentAudio = null; resolve(session === speakSession); };
    audio.play().catch(() => resolve(false));
  });
}

function speakWithBrowser(texto, session, onEnd) {
  if (!window.speechSynthesis) { onEnd?.(); return; }
  window.speechSynthesis.cancel();
  // Chrome corta utterances largas (~15s): encolar por frases completas
  const frases = splitSpeechChunks(texto, 200, 200);
  const vSel = elegirVozEspanol();
  frases.forEach((f, idx) => {
    const u = new SpeechSynthesisUtterance(f);
    if (vSel) { u.voice = vSel; u.lang = vSel.lang; } else u.lang = "es-419";
    u.rate = 1.0; u.pitch = 1.0;
    if (idx === frases.length - 1) {
      u.onend = () => { if (session === speakSession) onEnd?.(); };
      u.onerror = () => { if (session === speakSession) onEnd?.(); };
    }
    window.speechSynthesis.speak(u);
  });
}

function stopSpeaking() {
  speakSession += 1;
  if (currentAudio) { currentAudio.pause(); currentAudio = null; }
  window.speechSynthesis?.cancel();
}

function formatTime(date) {
  return date.toLocaleTimeString("es-CL", { hour: "2-digit", minute: "2-digit" });
}

// ===== "MUÉSTRAME EN PANTALLA": detección local del comando (voz o texto) =====
function detectarComandoPantalla(texto) {
  const t = (texto || "").toLowerCase().trim();
  if (!/mu[eé]strame|ens[eé][ñn]ame|[aá]brelo en pantalla|abre en pantalla|en pantalla/.test(t)) return null;
  let m;
  if (/correo|correos|mail/.test(t)) return { tipo: "correo", query: "" };
  if ((m = t.match(/simulaci[oó]n\s+(?:de\s+|del?\s+)?(.+)$/))) return { tipo: "simulacion", query: m[1].trim() };
  if ((m = t.match(/carpeta\s+(?:de\s+|del?\s+)?(.+)$/))) return { tipo: "carpeta", query: m[1].trim() };
  if ((m = t.match(/documento\s+(?:de\s+|del?\s+)?(.+)$/))) return { tipo: "carpeta", query: m[1].trim() };
  const resto = t.replace(/.*?(?:mu[eé]strame|ens[eé][ñn]ame|abre)\s*(?:en pantalla)?\s*(?:a\s+|la\s+|el\s+)?/, "").trim();
  return resto.length > 2 ? { tipo: "carpeta", query: resto } : null;
}

export default function CentralChat({ userName, activeModule }) {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [paused, setPaused] = useState(false);
  const [recording, setRecording] = useState(false);
  const [liveText, setLiveText] = useState("");
  const [connected, setConnected] = useState(null);
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState([]);
  const [copied, setCopied] = useState(null);
  const [attachedFiles, setAttachedFiles] = useState([]);
  const [autoVoice, setAutoVoice] = useState(true);
  const [conversationMode, setConversationMode] = useState(false);
  const [sessionId] = useState(() => `c-${Date.now()}-${Math.random().toString(36).slice(2,8)}`);
  const [vigilia, setVigilia] = useState(false);
  const [pantallaAbierta, setPantallaAbierta] = useState(false);
  const wakeSinComandoRef = useRef(0);
  const endRef = useRef(null);
  const recRef = useRef(null);
  const silenceRef = useRef(null);
  const fullTextRef = useRef("");
  const recordingRef = useRef(false);
  const conversationModeRef = useRef(false);
  const startRecordingRef = useRef(null);
  const fileInputRef = useRef(null);

  // Keep refs in sync
  useEffect(() => { conversationModeRef.current = conversationMode; }, [conversationMode]);
  useEffect(() => { recordingRef.current = recording; }, [recording]);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, loading]);

  // Proactive greeting when chat opens for first time
  const [greeted, setGreeted] = useState(false);
  useEffect(() => {
    if (open && !greeted && msgs.length === 0) {
      setGreeted(true);
      const hoy = new Date().toISOString().slice(0, 10);
      const yaResumen = localStorage.getItem("martin_resumen_dia") === hoy;
      const url = yaResumen ? `${API}/api/central/proactive` : `${API}/api/central/resumen-diario`;
      axios.get(url).then(r => {
        const texto = r.data?.resumen || r.data?.message;
        if (texto) {
          if (!yaResumen) localStorage.setItem("martin_resumen_dia", hoy);
          const greetMsg = { role: "assistant", text: texto, time: new Date() };
          setMsgs([greetMsg]);
          if (autoVoice) {
            setSpeaking(true);
            speakText(texto, () => setSpeaking(false));
          }
        }
      }).catch((e) => console.error(e));
    }
  }, [open, greeted, msgs.length, autoVoice]);

  // Health check with auto-reconnect
  const checkHealth = useCallback(() => {
    let attempts = 0;
    const check = () => {
      axios.get(`${API}/api/central/health`, { timeout: 10000 })
        .then(() => setConnected(true))
        .catch(() => {
          attempts++;
          if (attempts < 5) setTimeout(check, 3000);
          else setConnected(false);
        });
    };
    check();
  }, []);

  useEffect(() => {
    checkHealth();
    // Auto-reconnect every 30s if disconnected
    const interval = setInterval(() => {
      setConnected(prev => {
        if (prev === false) {
          axios.get(`${API}/api/central/health`, { timeout: 10000 })
            .then(() => setConnected(true))
            .catch((e) => console.error(e));
        }
        return prev;
      });
    }, 30000);
    return () => clearInterval(interval);
  }, [checkHealth]);

  useEffect(() => {
    return () => {
      if (recRef.current) try { recRef.current.abort(); } catch (e) { console.error(e); }
      if (silenceRef.current) clearTimeout(silenceRef.current);
      stopSpeaking();
    };
  }, []);

  // Keep recordingRef in sync
  useEffect(() => { recordingRef.current = recording; }, [recording]);

  // ===== COMANDOS DE VOZ DURANTE EL HABLA =====
  // «para» detiene al instante · «continúa» retoma · «desde el principio»/«desde cero» reinicia
  useEffect(() => {
    if (!speaking) { setPaused(false); return; }
    if (recording) return;
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    let activo = true;
    const cmd = new SR();
    cmd.lang = "es-CL";
    cmd.continuous = true;
    cmd.interimResults = true;
    cmd.onresult = (e) => {
      const last = (e.results[e.results.length - 1][0].transcript || "").toLowerCase();
      if (/desde\s+(el\s+principio|cero)/.test(last)) {
        restartSpeaking(); setPaused(false);
      } else if (/\bcontin[uú]a\b|\bsigue\b|\bretoma\b/.test(last)) {
        resumeSpeaking(); setPaused(false);
      } else if (/\bpara\b|\bpausa\b|\bdet[eé]nte\b|\bstop\b/.test(last)) {
        pauseSpeaking(); setPaused(true);
      }
    };
    cmd.onend = () => { if (activo) { try { cmd.start(); } catch (e2) { console.error(e2); } } };
    cmd.onerror = () => {};
    try { cmd.start(); } catch (e3) { console.error(e3); }
    return () => { activo = false; try { cmd.abort(); } catch (e4) { console.error(e4); } };
  }, [speaking, recording]);

  // ===== SEND MESSAGE =====
  const sendMsg = useCallback(async (text, withVoice = false) => {
    const t = (text || "").trim();
    if (!t && attachedFiles.length === 0) return;

    // "Muéstrame en pantalla...": toma el control visual sin pasar por el LLM
    const pantalla = detectarComandoPantalla(t);
    if (pantalla && attachedFiles.length === 0) {
      stopSpeaking();
      setSpeaking(false);
      setMsgs(prev => [...prev, { role: "user", text: t, time: new Date() },
        { role: "assistant", text: `🖥 Abriendo en pantalla: ${pantalla.query || "correos en espera"}...`, time: new Date() }]);
      setInput("");
      window.dispatchEvent(new CustomEvent("martin-pantalla", { detail: pantalla }));
      return;
    }

    const timestamp = new Date();
    const msgObj = { role: "user", text: t, time: timestamp };
    if (attachedFiles.length > 0) {
      msgObj.files = attachedFiles.map(f => f.name);
    }
    setMsgs(prev => [...prev, msgObj]);
    setInput("");
    setLoading(true);
    setLiveText("");

    try {
      let r;
      const hasFiles = attachedFiles.length > 0;

      for (let attempt = 0; attempt < 2; attempt++) {
        try {
          if (hasFiles) {
            const fd = new FormData();
            fd.append("message", t || "Analiza estos archivos");
            fd.append("session_id", sessionId);
            fd.append("user_name", userName || "");
            fd.append("context_module", activeModule || "");
            attachedFiles.forEach(f => fd.append("files", f));
            r = await axios.post(`${API}/api/central/chat-files`, fd, { timeout: 120000 });
          } else {
            r = await axios.post(`${API}/api/central/chat`, {
              message: t, session_id: sessionId,
              user_name: userName || "", context_module: activeModule || "",
              conversation_mode: conversationModeRef.current,
            }, { timeout: 60000 });
          }
          break;
        } catch (retryErr) {
          if (attempt === 0) {
            await new Promise(res => setTimeout(res, 1500));
          } else {
            throw retryErr;
          }
        }
      }

      const resp = r.data?.response || "Sin respuesta";
      const assistantMsg = { role: "assistant", text: resp, time: new Date() };

      // Check for generated file
      if (r.data?.generated_file?.ready) {
        assistantMsg.generatedFile = r.data.generated_file;
      }
      // File info
      if (r.data?.files_info?.length > 0) {
        assistantMsg.filesInfo = r.data.files_info;
      }

      setMsgs(prev => [...prev, assistantMsg]);
      setConnected(true);
      setAttachedFiles([]);

      if (withVoice || autoVoice) {
        setSpeaking(true);
        speakText(resp, () => {
          setSpeaking(false);
          // In conversation mode, restart mic automatically after Martin finishes
          if (conversationModeRef.current) {
            setTimeout(() => {
              if (conversationModeRef.current && !recordingRef.current) {
                try { startRecordingRef.current?.(); } catch (e) { console.error(e); }
              }
            }, 400);
          }
        });
      }
    } catch (err) {
      console.error("Central chat error:", err);
      const isNetworkError = !err.response;
      const statusCode = err.response?.status;
      const serverMsg = err.response?.data?.detail;
      
      let errorText;
      if (isNetworkError) {
        setConnected(false);
        errorText = "No se pudo conectar con el servidor. Verificando conexion...";
        // Auto-retry health check
        setTimeout(() => checkHealth(), 2000);
      } else if (statusCode === 500 && serverMsg?.includes("LLM")) {
        errorText = "El servicio de IA no esta disponible temporalmente. Intenta de nuevo en unos segundos.";
      } else if (statusCode === 500) {
        errorText = "Error interno del servidor. Intenta de nuevo.";
      } else {
        errorText = serverMsg || "Error al procesar tu mensaje. Intenta de nuevo.";
      }
      
      setMsgs(prev => [...prev, {
        role: "assistant",
        text: errorText,
        isError: true, time: new Date()
      }]);
    }
    setLoading(false);
  }, [sessionId, userName, activeModule, attachedFiles, checkHealth, autoVoice]);

  // ===== PUSH-TO-TALK =====
  const startRecording = useCallback(async () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      setMsgs(prev => [...prev, {
        role: "assistant",
        text: "Tu navegador no soporta reconocimiento de voz. Usa Chrome para esta funcion.",
        isError: true, time: new Date()
      }]);
      return;
    }

    // Request microphone permission explicitly first
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      // Stop the stream immediately - we just needed the permission
      stream.getTracks().forEach(t => t.stop());
    } catch (permErr) {
      console.error("Microphone permission denied:", permErr);
      setMsgs(prev => [...prev, {
        role: "assistant",
        text: "Necesito acceso al microfono. Cuando tu navegador te lo pida, haz clic en 'Permitir'.",
        isError: true, time: new Date()
      }]);
      return;
    }

    if (speaking) { stopSpeaking(); setSpeaking(false); }
    if (recRef.current) try { recRef.current.abort(); } catch (e) { console.error(e); }

    const rec = new SR();
    rec.lang = "es-CL";
    rec.continuous = true;
    rec.interimResults = true;
    recRef.current = rec;
    fullTextRef.current = "";
    setLiveText("");
    setRecording(true);

    rec.onresult = (e) => {
      let final = "";
      let interim = "";
      for (let i = 0; i < e.results.length; i++) {
        if (e.results[i].isFinal) final += e.results[i][0].transcript;
        else interim += e.results[i][0].transcript;
      }
      fullTextRef.current = final;
      setLiveText(final + interim);

      if (silenceRef.current) clearTimeout(silenceRef.current);
      if ((final + interim).trim().length > 0) {
        // In conversation mode, wait longer before cutting off (6s vs 2s)
        const silenceDelay = conversationModeRef.current ? 6000 : 2500;
        silenceRef.current = setTimeout(() => {
          const text = fullTextRef.current.trim() || (final + interim).trim();
          if (text.length > 1) {
            try { rec.stop(); } catch (e) { console.error(e); }
            setRecording(false);
            setLiveText("");
            sendMsg(text, true);
          }
        }, silenceDelay);
      }
    };

    rec.onend = () => {
      if (silenceRef.current) clearTimeout(silenceRef.current);
      const text = fullTextRef.current.trim();
      if (text.length > 1 && recordingRef.current) {
        setRecording(false);
        setLiveText("");
        sendMsg(text, true);
      } else {
        setRecording(false);
        setLiveText("");
      }
    };

    rec.onerror = (e) => {
      console.error("SpeechRecognition error:", e.error);
      setRecording(false);
      setLiveText("");
      if (e.error === "no-speech") {
        // Silence - do nothing
      }
    };

    try { rec.start(); } catch (err) {
      console.error("Failed to start recognition:", err);
      setRecording(false);
    }
  }, [speaking, sendMsg]);

  const stopRecording = useCallback(() => {
    if (silenceRef.current) clearTimeout(silenceRef.current);
    if (recRef.current) try { recRef.current.stop(); } catch (e) { console.error(e); }
  }, []);

  // Expose startRecording via ref for conversation mode auto-restart
  useEffect(() => { startRecordingRef.current = startRecording; }, [startRecording]);

  const toggleRecording = useCallback(() => {
    if (recording) stopRecording();
    else startRecording();
  }, [recording, stopRecording, startRecording]);

  // ===== VIGILIA: manos libres con palabra de activación «Martín» =====
  // La pantalla Martín (overlay) tiene su propio control por voz: la vigilia se pausa.
  useEffect(() => {
    const abre = () => setPantallaAbierta(true);
    const cierra = () => setPantallaAbierta(false);
    window.addEventListener("martin-pantalla", abre);
    window.addEventListener("martin-pantalla-cerrada", cierra);
    return () => { window.removeEventListener("martin-pantalla", abre); window.removeEventListener("martin-pantalla-cerrada", cierra); };
  }, []);

  useEffect(() => {
    if (!vigilia || recording || speaking || loading || pantallaAbierta) return;
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    let activo = true;
    const rec = new SR();
    rec.lang = "es-CL";
    rec.continuous = true;
    rec.interimResults = false;
    rec.onresult = (e) => {
      const last = (e.results[e.results.length - 1][0].transcript || "").trim().toLowerCase();
      const m = last.match(/mart[ií]n[,.\s]*(.*)$/);
      if (!m) return;
      const comando = (m[1] || "").trim();
      axios.post(`${API}/api/central/vigilia-log`, { texto: last, comando, user_name: userName || "" }).catch(() => {});
      activo = false;
      try { rec.abort(); } catch (err) { console.error(err); }
      setOpen(true);
      if (comando.length > 2) {
        wakeSinComandoRef.current = 0;
        sendMsg(comando, true);
      } else {
        wakeSinComandoRef.current += 1;
        if (wakeSinComandoRef.current >= 3) {
          wakeSinComandoRef.current = 0;
          setSpeaking(true);
          speakText("¿Sí? Te escucho", () => { setSpeaking(false); setTimeout(() => startRecordingRef.current?.(), 300); });
        } else {
          setTimeout(() => startRecordingRef.current?.(), 200);
        }
      }
    };
    rec.onend = () => { if (activo) setTimeout(() => { try { rec.start(); } catch (err) { console.error(err); } }, 400); };
    rec.onerror = () => {};
    const t = setTimeout(() => { try { rec.start(); } catch (err) { console.error(err); } }, 350);
    return () => { activo = false; clearTimeout(t); try { rec.abort(); } catch (err) { console.error(err); } };
  }, [vigilia, recording, speaking, loading, pantallaAbierta, sendMsg, userName]);

  const toggleVigilia = useCallback(async () => {
    if (vigilia) { setVigilia(false); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach(tr => tr.stop());
    } catch (e) {
      console.error("Vigilia: microfono denegado", e);
      return;
    }
    setAutoVoice(true);
    wakeSinComandoRef.current = 0;
    setVigilia(true);
  }, [vigilia]);

  // ===== TEXT HANDLERS =====
  const handleSend = () => { const v = input.trim(); if (v) sendMsg(v, false); };
  const handleKey = (e) => { if (e.key === "Enter" && !loading) handleSend(); };
  const stopSpeak = () => { stopSpeaking(); setSpeaking(false); setPaused(false); };

  // ===== COPY MESSAGE =====
  const copyMsg = (text, idx) => {
    navigator.clipboard?.writeText(text);
    setCopied(idx);
    setTimeout(() => setCopied(null), 2000);
  };

  // ===== HISTORY =====
  const loadHistory = async () => {
    setShowHistory(!showHistory);
    if (!showHistory) {
      try {
        const r = await axios.get(`${API}/api/central/conversations`, { params: { user_name: userName, limit: 30 } });
        setHistory(r.data?.conversations || []);
      } catch { setHistory([]); }
    }
  };

  // ===== EXPORT =====
  const exportChat = () => {
    const lines = msgs.map(m =>
      `[${m.time ? formatTime(m.time) : ""}] ${m.role === "user" ? (userName || "Tu") : "Martin"}: ${m.text}`
    ).join("\n\n");
    const blob = new Blob([lines], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `martin_chat_${new Date().toISOString().slice(0,10)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <>
      {/* BOTÓN VIGILIA — manos libres, al lado de la cara de Martín */}
      <div className={`vigilia-wrap ${vigilia ? "activa" : ""}`}>
        {vigilia && (
          <span className="vigilia-label" data-testid="vigilia-label">
            {recording ? "TE ESCUCHO..." : speaking ? "MARTÍN HABLANDO..." : "VIGILIA ACTIVA · di «Martín»"}
          </span>
        )}
        <button className={`vigilia-btn ${vigilia ? "activa" : ""}`} onClick={toggleVigilia}
          data-testid="vigilia-btn"
          title={vigilia ? "Silenciar vigilia (un toque)" : "Activar VIGILIA manos libres"}>
          <i className={`fa ${vigilia ? "fa-microphone" : "fa-microphone-slash"}`}></i>
          <span className="vigilia-txt">{vigilia ? "VIGILIA" : "OFF"}</span>
          {vigilia && <><span className="vigilia-onda o1" /><span className="vigilia-onda o2" /></>}
        </button>
      </div>

      {/* FAB */}
      <button className={`central-fab ${open ? "active" : ""}`}
        onClick={() => setOpen(o => !o)} data-testid="central-fab">
        {open ? <i className="fa fa-times"></i> : <img src={CENTRAL_AVATAR} alt="Central" className="central-fab-avatar" />}
      </button>

      {/* Chat panel */}
      {open && (
        <div className="central-panel" data-testid="central-panel">
          {/* Header */}
          <div className="central-header">
            <div className="central-header-info">
              <span className="central-logo">Martin</span>
              <span className="central-status" data-testid="central-status" style={
                recording ? { color: "#d4af37" } :
                paused ? { color: "#ff9800" } :
                speaking ? { color: "#d4af37" } :
                loading ? { color: "#ff9800" } :
                connected === false ? { color: "#e11d48" } : {}
              }>
                {recording ? "Escuchando..." : paused ? "En pausa · di «continúa» o «desde el principio»" : speaking ? "Hablando... · di «para» para detener" : loading ? "Pensando..." : connected === false ? "Sin conexion" : "Tu guia"}
              </span>
              {connected === false && (
                <button data-testid="central-reconnect-btn"
                  onClick={() => { setConnected(null); checkHealth(); }}
                  style={{ background: "rgba(212,175,55,0.2)", border: "1px solid #d4af37", color: "#d4af37", borderRadius: 0, padding: "2px 8px", fontSize: "0.7rem", cursor: "pointer", marginLeft: 6 }}>
                  <i className="fa fa-refresh"></i> Reconectar
                </button>
              )}
            </div>
            <div className="central-header-btns">
              {connected !== null && (
                <span className="central-conn-dot" data-testid="central-conn-indicator"
                  style={{ width: 8, height: 8, borderRadius: "50%", display: "inline-block",
                    background: connected ? "#10d98e" : "#e11d48",
                    boxShadow: connected ? "0 0 6px #10d98e" : "0 0 6px #e11d48" }}
                  title={connected ? "Conectado" : "Sin conexion"} />
              )}
              <button className="central-header-action" onClick={() => setAutoVoice(v => !v)}
                title={autoVoice ? "Desactivar voz" : "Activar voz"} data-testid="central-voice-toggle"
                style={{ background: autoVoice ? "rgba(212,175,55,0.2)" : "none", borderRadius: 0 }}>
                <i className={`fa ${autoVoice ? "fa-volume-up" : "fa-volume-off"}`}
                  style={{ fontSize: "0.75rem", color: autoVoice ? "#d4af37" : "#555" }}></i>
              </button>
              <button className="central-header-action" onClick={() => {
                  const newMode = !conversationMode;
                  setConversationMode(newMode);
                  if (newMode && !autoVoice) setAutoVoice(true);
                  if (newMode && !recordingRef.current) {
                    setTimeout(() => { try { startRecordingRef.current?.(); } catch (e) { console.error(e); } }, 300);
                  } else if (!newMode && recordingRef.current) {
                    stopRecording();
                  }
                }}
                title={conversationMode ? "Modo conversacion ACTIVO - click para salir" : "Activar modo conversacion"}
                data-testid="central-convo-toggle"
                style={{
                  background: conversationMode ? "rgba(16,217,142,0.3)" : "none",
                  borderRadius: 0,
                  animation: conversationMode ? "pulse 1.8s infinite" : "none",
                }}>
                <i className={`fa ${conversationMode ? "fa-comments" : "fa-comments-o"}`}
                  style={{ fontSize: "0.75rem", color: conversationMode ? "#10d98e" : "#888" }}></i>
              </button>
              {msgs.length > 0 && (
                <button className="central-header-action" onClick={exportChat} title="Exportar chat" data-testid="central-export-btn">
                  <i className="fa fa-download" style={{ fontSize: "0.75rem", color: "#888" }}></i>
                </button>
              )}
              <button className="central-header-action" onClick={loadHistory} title="Historial" data-testid="central-history-btn"
                style={{ background: showHistory ? "rgba(212,175,55,0.15)" : "none" }}>
                <i className="fa fa-clock-o" style={{ fontSize: "0.75rem", color: showHistory ? "#d4af37" : "#888" }}></i>
              </button>
              {speaking && <button className="central-stop-speak" onClick={stopSpeak} data-testid="central-stop-speak"><i className="fa fa-stop"></i></button>}
              <button className="central-close" onClick={() => setOpen(false)} data-testid="central-close"><i className="fa fa-chevron-down"></i></button>
            </div>
          </div>

          {/* History Panel */}
          {showHistory && (
            <div className="central-history-panel" data-testid="central-history-panel">
              <div className="central-history-title">Conversaciones anteriores</div>
              {history.length === 0 ? (
                <p style={{ color: "#666", fontSize: "0.78rem", padding: "8px" }}>Sin historial</p>
              ) : (
                <div className="central-history-list">
                  {history.slice(0, 20).map((h, i) => (
                    <div key={i} className="central-history-item" data-testid={`history-item-${i}`}>
                      <span className="central-history-user">{h.user_name || "Usuario"}</span>
                      <span className="central-history-msg">{(h.user_msg || "").slice(0, 60)}</span>
                      <span className="central-history-time">{h.timestamp ? new Date(h.timestamp).toLocaleDateString("es-CL").replace(/-/g, "/") : ""}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Messages */}
          <div className="central-messages">
            {msgs.length === 0 && !showHistory && (
              <div className="central-welcome">
                <img src={CENTRAL_AVATAR} alt="Martin" className="central-welcome-avatar" />
                <p className="central-welcome-title">Hola{userName ? `, ${userName}` : ""}. Soy Martin, tu guia.</p>
                <p className="central-welcome-sub">Preguntame lo que quieras o presiona el microfono para hablar</p>
                <div className="central-quick-actions">
                  <button onClick={() => sendMsg("Que documentos necesito para un credito hipotecario?", false)} className="central-quick" data-testid="quick-docs">Documentos credito</button>
                  <button onClick={() => sendMsg("Como mejorar mi capacidad crediticia?", false)} className="central-quick" data-testid="quick-capacity">Capacidad crediticia</button>
                  <button onClick={() => sendMsg("Explicame que es la UF", false)} className="central-quick" data-testid="quick-uf">Que es la UF</button>
                  <button onClick={() => sendMsg("Busca mis correos recientes de aprobaciones", false)} className="central-quick" data-testid="quick-emails">Correos aprobaciones</button>
                </div>
              </div>
            )}
            {msgs.map((m, i) => (
              <div key={i} className={`central-msg ${m.role}`} data-testid={`central-msg-${i}`}>
                {m.role === "assistant" && <img src={CENTRAL_AVATAR} alt="M" className="central-msg-avatar" />}
                <div className={`central-msg-bubble ${m.isError ? "error-msg" : ""}`}>
                  {m.files && (
                    <div className="central-msg-files">
                      {m.files.map((f, fi) => (
                        <span key={fi} className="central-file-tag"><i className="fa fa-paperclip"></i> {f}</span>
                      ))}
                    </div>
                  )}
                  <div className="central-msg-text">{renderTextWithLinks(m.text)}</div>
                  {m.generatedFile && (
                    <div className="central-generated-file" data-testid="central-generated-file">
                      <div className="central-gen-header">
                        <i className="fa fa-file-text"></i>
                        <span>{m.generatedFile.title} ({m.generatedFile.total} registros)</span>
                      </div>
                      <div className="central-gen-actions">
                        <a href={`${API}/api/central/download-generated/${m.generatedFile.file_id}?formato=excel`}
                          className="central-gen-btn excel" target="_blank" rel="noreferrer" data-testid="download-gen-excel">
                          <i className="fa fa-file-excel-o"></i> Excel
                        </a>
                        <a href={`${API}/api/central/download-generated/${m.generatedFile.file_id}?formato=pdf`}
                          className="central-gen-btn pdf" target="_blank" rel="noreferrer" data-testid="download-gen-pdf">
                          <i className="fa fa-file-pdf-o"></i> PDF
                        </a>
                      </div>
                    </div>
                  )}
                  <div className="central-msg-meta">
                    {m.time && <span className="central-msg-time">{formatTime(m.time)}</span>}
                    {m.role === "assistant" && !m.isError && (
                      <>
                        <button className="central-meta-btn" onClick={() => copyMsg(m.text, i)}
                          title="Copiar" data-testid={`copy-msg-${i}`}>
                          <i className={`fa ${copied === i ? "fa-check" : "fa-copy"}`}></i>
                        </button>
                        <button className="central-meta-btn" onClick={() => {
                          setSpeaking(true);
                          speakText(m.text, () => setSpeaking(false));
                        }} title="Escuchar" data-testid={`replay-msg-${i}`}>
                          <i className="fa fa-volume-up"></i>
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            ))}
            {loading && (
              <div className="central-msg assistant">
                <img src={CENTRAL_AVATAR} alt="M" className="central-msg-avatar" />
                <div className="central-msg-bubble central-typing"><span/><span/><span/></div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          {/* Live transcript while recording */}
          {recording && liveText && (
            <div className="central-live-bar" data-testid="central-live-bar">
              <i className="fa fa-microphone live-mic-icon"></i>
              <span>{liveText}</span>
            </div>
          )}

          {/* Attached files preview */}
          {attachedFiles.length > 0 && (
            <div className="central-attached-bar" data-testid="central-attached-files">
              {attachedFiles.map((f, i) => (
                <div key={i} className="central-attached-file">
                  <i className={`fa fa-file-${f.name.endsWith('.pdf') ? 'pdf-o' : f.name.endsWith('.csv') ? 'text-o' : 'excel-o'}`}></i>
                  <span>{f.name}</span>
                  <button onClick={() => setAttachedFiles(prev => prev.filter((_, idx) => idx !== i))} className="central-attached-remove">
                    <i className="fa fa-times"></i>
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Input bar */}
          <div className="central-input-bar">
            <input type="file" ref={fileInputRef} multiple accept=".xlsx,.xls,.csv,.pdf"
              style={{ display: "none" }}
              onChange={e => {
                const newFiles = Array.from(e.target.files);
                setAttachedFiles(prev => [...prev, ...newFiles]);
                e.target.value = "";
              }}
              data-testid="central-file-upload" />
            <button className="central-attach-btn" onClick={() => fileInputRef.current?.click()}
              disabled={loading} data-testid="central-attach-btn" title="Adjuntar archivos">
              <i className="fa fa-paperclip"></i>
            </button>
            <button
              className={`central-mic-btn ${recording ? "active" : ""}`}
              onClick={toggleRecording}
              disabled={loading}
              data-testid="central-mic-btn"
              title={recording ? "Dejar de grabar" : "Hablar"}
            >
              <i className={`fa ${recording ? "fa-stop" : "fa-microphone"}`}></i>
              {recording && <span className="mic-recording-pulse"></span>}
            </button>
            <input type="text" className="central-text-input"
              placeholder={attachedFiles.length > 0 ? "Que quieres hacer con estos archivos?" : "Escribe aqui..."}
              value={input} onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              disabled={recording || loading}
              data-testid="central-input" />
            <button className="central-send-btn" onClick={handleSend}
              disabled={loading || (!input.trim() && attachedFiles.length === 0) || recording}
              data-testid="central-send-btn">
              {loading ? <i className="fa fa-spinner fa-spin"></i> : <i className="fa fa-paper-plane"></i>}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
