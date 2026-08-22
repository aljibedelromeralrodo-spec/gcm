import { useEffect, useRef, useState } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

async function hablar(texto) {
  try {
    const r = await axios.post(`${API}/api/central/tts`, { text: texto });
    if (r.data?.audio) {
      const audio = new Audio(`data:audio/mp3;base64,${r.data.audio}`);
      await audio.play();
      return new Promise((res) => { audio.onended = res; audio.onerror = res; });
    }
  } catch (e) { console.error("martin proactivo tts", e); }
  return new Promise((res) => {
    if (!window.speechSynthesis) return res();
    const u = new SpeechSynthesisUtterance(texto);
    u.lang = "es-419"; u.onend = res; u.onerror = res;
    window.speechSynthesis.speak(u);
  });
}

export default function MartinProactivo({ user }) {
  const [aviso, setAviso] = useState(null);
  const busyRef = useRef(false);
  const esAdmin = ["admin", "maestro"].includes(user?.rol || "");

  useEffect(() => {
    if (!esAdmin) return;
    let vivo = true;
    const revisar = async () => {
      if (busyRef.current) return;
      try {
        const r = await axios.get(`${API}/api/central/proactivo`);
        const pendientes = r.data?.avisos || [];
        if (!vivo || !pendientes.length) return;
        busyRef.current = true;
        const a = pendientes[0];
        setAviso(a);
        await axios.post(`${API}/api/central/proactivo/${a.id}/hablado`).catch(() => {});
        await hablar(a.mensaje);
        if (vivo) setTimeout(() => setAviso(null), 12000);
        busyRef.current = false;
      } catch (e) { busyRef.current = false; }
    };
    revisar();
    const t = setInterval(revisar, 45000);
    return () => { vivo = false; clearInterval(t); };
  }, [esAdmin]);

  if (!aviso) return null;
  const aprobada = aviso.tipo === "mesa_aprobado";
  return (
    <div data-testid="martin-proactivo-banner" style={{
      position: "fixed", bottom: 96, right: 24, zIndex: 9998, maxWidth: 340,
      background: "#0a0a0a", border: `1px solid ${aprobada ? "#C9A227" : "#b91c1c"}`,
      borderRadius: 14, padding: "14px 16px", boxShadow: "0 8px 32px rgba(0,0,0,.5)",
      display: "flex", gap: 12, alignItems: "flex-start", animation: "fadeIn .3s ease" }}>
      <img src="/martin-avatar.jpeg" alt="Martín" style={{ width: 42, height: 42, borderRadius: "50%", objectFit: "cover", border: "2px solid #C9A227" }} />
      <div>
        <div style={{ color: "#C9A227", fontWeight: 700, fontSize: 13, marginBottom: 4 }}>
          <i className={`fa ${aprobada ? "fa-circle-check" : "fa-circle-exclamation"}`} style={{ marginRight: 6 }}></i>
          Martín — Veredicto de MESA
        </div>
        <div data-testid="martin-proactivo-mensaje" style={{ color: "#e5e7eb", fontSize: 13, lineHeight: 1.45 }}>{aviso.mensaje}</div>
        <button data-testid="martin-proactivo-cerrar" onClick={() => setAviso(null)} style={{
          marginTop: 8, background: "transparent", border: "1px solid #444", color: "#9ca3af",
          borderRadius: 8, padding: "3px 10px", fontSize: 12, cursor: "pointer" }}>Cerrar</button>
      </div>
    </div>
  );
}
