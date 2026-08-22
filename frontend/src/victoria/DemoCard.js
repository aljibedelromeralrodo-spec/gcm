import { useState } from "react";
import axios from "axios";
import { Toaster, toast } from "sonner";
import { API_URL } from "../utils/formatters";
import DemoVictoria from "./DemoVictoria";

const btn = (color) => ({ background: "rgba(212,175,55,0.12)", color, border: `1.5px solid ${color}`,
  borderRadius: 10, padding: "0.6rem 1.1rem", fontSize: "0.78rem", fontWeight: 800, cursor: "pointer" });

export default function DemoCard() {
  const [ver, setVer] = useState(false);
  const [enviando, setEnviando] = useState(false);

  const descargar = async () => {
    try {
      const r = await axios.get(`${API_URL}/api/victoria/demo/video`, { responseType: "blob" });
      const u = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = u;
      a.download = "Demo_Modulo_Daniela_Central_Mutuos.mp4";
      a.click();
      URL.revokeObjectURL(u);
      toast.success("Descargando el video de la demo");
    } catch { toast.error("El video de la demo aún no está generado"); }
  };

  const enviar = async () => {
    setEnviando(true);
    try {
      const r = await axios.post(`${API_URL}/api/victoria/demo/enviar`, {});
      toast.success(r.data.mensaje);
    } catch (e) {
      const d = e.response?.data?.detail;
      toast.error(typeof d === "string" ? d : "No se pudo enviar el video");
    }
    setEnviando(false);
  };

  return (
    <div data-testid="demo-card" style={{ marginTop: 14, background: "rgba(30,41,59,0.55)", border: "1.5px solid rgba(212,175,55,0.4)", borderRadius: 12, padding: "1rem 1.3rem" }}>
      <Toaster position="top-right" richColors theme="dark" />
      <div style={{ color: "#d4af37", fontWeight: 800, fontSize: "0.9rem" }}>🎬 Demo módulo Daniela Galindo (datos ficticios)</div>
      <div style={{ color: "#94a3b8", fontSize: "0.72rem", marginTop: 3 }}>
        Caso completo Juan Pérez Soto (3.500 UF): detección de correo → clasificación → validación → preview → formularios → checklist → envío a ConCreces.</div>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 12 }}>
        <button data-testid="demo-ver-btn" onClick={() => setVer(true)} style={btn("#d4af37")}>
          ▶ Ver demo interactiva ahora</button>
        <button data-testid="demo-descargar-btn" onClick={descargar} style={btn("#93c5fd")}>
          ⬇ Descargar el video de la demo (MP4)</button>
        <button data-testid="demo-enviar-btn" onClick={enviar} disabled={enviando} style={btn("#4ade80")}>
          {enviando ? "Enviando…" : "✉ Enviar el video a gerardo.ext@centralmutuos.cl"}</button>
      </div>
      {ver && <DemoVictoria autoPlay onSalir={() => setVer(false)} />}
    </div>
  );
}
