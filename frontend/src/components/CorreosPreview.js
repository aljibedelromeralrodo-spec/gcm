import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const ORO = "#d4af37";
const btn = (c) => ({ background: "transparent", color: c, border: `1px solid ${c}`, cursor: "pointer",
  padding: "0.3rem 0.8rem", fontWeight: 700, fontSize: "0.72rem" });

export default function CorreosPreview() {
  const [data, setData] = useState(null);
  const [abierto, setAbierto] = useState(null);
  const [adjunto, setAdjunto] = useState(null);
  const [oculto, setOculto] = useState(false);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");

  const verAdjunto = async (pid, idx, filename) => {
    if (adjunto && adjunto.pid === pid && adjunto.idx === idx) {
      URL.revokeObjectURL(adjunto.url); setAdjunto(null); return;
    }
    setBusy(`adj${pid}${idx}`);
    try {
      const r = await axios.get(`${API}/api/correos-preview/${pid}/adjunto/${idx}`, { responseType: "blob" });
      if (adjunto) URL.revokeObjectURL(adjunto.url);
      setAdjunto({ pid, idx, filename, url: URL.createObjectURL(r.data), tipo: r.data.type });
    } catch (e) { setMsg("🚨 No se pudo cargar el adjunto"); }
    setBusy("");
  };

  const quitarAdjunto = async (pid, idx, filename) => {
    if (!window.confirm(`¿Quitar «${filename}» de este correo? El correo se enviará SIN este adjunto.`)) return;
    setBusy(`quitar${pid}${idx}`);
    try {
      const r = await axios.post(`${API}/api/correos-preview/${pid}/adjunto/${idx}/quitar`);
      setMsg(`🗑 Adjunto quitado: ${r.data.quitado}`);
      if (adjunto && adjunto.pid === pid) { URL.revokeObjectURL(adjunto.url); setAdjunto(null); }
      cargar();
    } catch (e) { setMsg(`🚨 ${e.response?.data?.detail || "No se pudo quitar el adjunto"}`); }
    setBusy("");
  };

  const cargar = useCallback(() => {
    axios.get(`${API}/api/correos-preview`)
      .then(r => setData(r.data))
      .catch(e => { if ([401, 403].includes(e.response?.status)) setOculto(true); });
  }, []);

  useEffect(() => { cargar(); const t = setInterval(cargar, 20000); return () => clearInterval(t); }, [cargar]);

  if (oculto || !data || !data.total) return null;

  const accion = async (pid, tipo, confirmar) => {
    if (!window.confirm(confirmar)) return;
    setBusy(pid + tipo); setMsg("");
    try {
      const r = await axios.post(`${API}/api/correos-preview/${pid}/${tipo}`);
      setMsg(r.data.enviado ? `✅ Correo enviado a ${r.data.to}` : "🗑 Correo descartado sin enviar");
      setAbierto(null);
      cargar();
    } catch (e) { setMsg(`🚨 ${e.response?.data?.detail || "Error"}`); }
    setBusy("");
  };

  return (
    <div data-testid="correos-preview-panel" style={{ background: "rgba(20,12,2,0.95)",
      border: "1.5px solid rgba(245,158,11,0.6)", padding: "1rem 1.3rem", marginBottom: "1rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <i className="fa fa-eye" style={{ color: "#f59e0b" }} />
        <b style={{ color: "#f5b942", fontSize: "0.9rem", letterSpacing: "0.06em" }}>
          👁 Correos esperando SU confirmación ({data.total})
        </b>
        <span style={{ fontSize: "0.7rem", opacity: 0.6 }}>Normativa: ningún correo sale sin su aprobación explícita</span>
      </div>
      {msg && <div data-testid="preview-msg" style={{ fontSize: "0.78rem", color: "#F5E7B8", margin: "0.5rem 0" }}>{msg}</div>}
      <div style={{ marginTop: "0.7rem", display: "flex", flexDirection: "column", gap: "0.5rem", maxHeight: 460, overflowY: "auto" }}>
        {data.correos.map((c, i) => (
          <div key={c.id} data-testid={`preview-correo-${i}`} style={{ background: "rgba(255,255,255,0.03)",
            border: "1px solid rgba(245,158,11,0.25)", padding: "0.6rem 0.9rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <div style={{ flex: 1, minWidth: 240 }}>
                <div style={{ fontSize: "0.82rem", color: "#F5E7B8", fontWeight: 700 }}>{c.subject || "(sin asunto)"}</div>
                <div data-testid={`preview-destinatario-${i}`} style={{ fontSize: "0.72rem", opacity: 0.75 }}>
                  <i className="fa fa-envelope" style={{ color: ORO, marginRight: 5 }} />
                  Para: {Array.isArray(c.to) ? c.to.join(", ") : c.to}{c.cc ? ` · CC: ${c.cc}` : ""}
                </div>
                <div style={{ fontSize: "0.68rem", opacity: 0.55 }}>
                  {(c.creado || "").slice(0, 16).replace("T", " ")} · {(c.adjuntos || []).length} adjunto(s)
                  {(c.adjuntos || []).length > 0 && `: ${(c.adjuntos || []).map(a => a.filename).join(", ").slice(0, 90)}`}
                </div>
              </div>
              <button data-testid={`preview-ver-${i}`} style={btn(ORO)}
                onClick={() => setAbierto(abierto === c.id ? null : c.id)}>
                <i className="fa fa-eye" /> {abierto === c.id ? "Ocultar" : "Ver correo"}
              </button>
              <button data-testid={`preview-confirmar-${i}`} disabled={!!busy} style={btn("#10d98e")}
                onClick={() => accion(c.id, "confirmar", `¿CONFIRMA el envío de «${c.subject}» a ${Array.isArray(c.to) ? c.to.join(", ") : c.to}?`)}>
                {busy === c.id + "confirmar" ? <i className="fa fa-spinner fa-spin" /> : <i className="fa fa-paper-plane" />} Confirmar y enviar
              </button>
              <button data-testid={`preview-descartar-${i}`} disabled={!!busy} style={btn("#e11d48")}
                onClick={() => accion(c.id, "descartar", "¿Descartar este correo SIN enviarlo?")}>
                <i className="fa fa-times" /> Descartar
              </button>
            </div>
            {(c.adjuntos || []).length > 0 && (
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                {(c.adjuntos || []).map((a, j) => (
                  <span key={j} style={{ display: "inline-flex", alignItems: "stretch" }}>
                    <button data-testid={`preview-adjunto-${i}-${j}`} disabled={!!busy}
                      style={{ ...btn(adjunto && adjunto.pid === c.id && adjunto.idx === j ? "#10d98e" : "#8ab4f8"), borderRight: "none" }}
                      onClick={() => verAdjunto(c.id, j, a.filename)}>
                      {busy === `adj${c.id}${j}` ? <i className="fa fa-spinner fa-spin" /> : <i className="fa fa-paperclip" />} {a.filename}
                    </button>
                    <button data-testid={`preview-adjunto-quitar-${i}-${j}`} disabled={!!busy}
                      title={`Quitar ${a.filename} del correo`}
                      style={{ ...btn("#e11d48"), padding: "0.3rem 0.5rem" }}
                      onClick={() => quitarAdjunto(c.id, j, a.filename)}>
                      <i className="fa fa-times" />
                    </button>
                  </span>
                ))}
              </div>
            )}
            {adjunto && adjunto.pid === c.id && (
              <div data-testid={`preview-adjunto-visor-${i}`} style={{ marginTop: 8 }}>
                <div style={{ fontSize: "0.72rem", color: "#8ab4f8", marginBottom: 4 }}>
                  <i className="fa fa-paperclip" /> Adjunto: {adjunto.filename}
                </div>
                {adjunto.tipo.startsWith("image/")
                  ? <img src={adjunto.url} alt={adjunto.filename} style={{ maxWidth: "100%", maxHeight: 420, border: "1px solid rgba(138,180,248,0.4)" }} />
                  : <iframe title={`adj-${i}`} src={adjunto.url}
                      style={{ width: "100%", height: 420, background: "#fff", border: "1px solid rgba(138,180,248,0.4)" }} />}
              </div>
            )}
            {abierto === c.id && (
              <iframe data-testid={`preview-cuerpo-${i}`} title={`preview-${i}`} srcDoc={c.body_html}
                style={{ width: "100%", height: 380, background: "#fff", border: "1px solid rgba(245,158,11,0.3)", marginTop: 8 }} />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
