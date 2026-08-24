import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const ORO = "#d4af37";

const btn = (color) => ({
  background: "transparent", color, border: `1px solid ${color}`, cursor: "pointer",
  padding: "0.3rem 0.8rem", fontWeight: 700, fontSize: "0.72rem", letterSpacing: "0.05em",
});

export default function RetenidosModoPrueba() {
  const [data, setData] = useState(null);
  const [oculto, setOculto] = useState(false);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");

  const cargar = useCallback(() => {
    axios.get(`${API}/api/modo-prueba/retenidos`)
      .then(r => setData(r.data))
      .catch(e => { if (e.response?.status === 403) setOculto(true); });
  }, []);

  useEffect(() => {
    cargar();
    const t = setInterval(cargar, 30000);
    return () => clearInterval(t);
  }, [cargar]);

  if (oculto || !data || !data.total) return null;

  const accion = async (url, confirmar, id) => {
    if (confirmar && !window.confirm(confirmar)) return;
    setBusy(id); setMsg("");
    try {
      const r = await axios.post(`${API}/api/modo-prueba/retenidos/${url}`);
      if (r.data.procesados !== undefined) setMsg(`✅ ${r.data.enviados}/${r.data.procesados} correo(s) enviados`);
      else if (r.data.enviado) setMsg(`✅ Correo enviado a ${r.data.cliente || "cliente"}`);
      else if (r.data.descartados !== undefined) setMsg(`🗑 ${r.data.descartados} correo(s) descartados`);
      else setMsg("🗑 Correo descartado sin enviar");
      cargar();
    } catch (e) { setMsg(`🚨 ${e.response?.data?.detail || "Error"}`); }
    setBusy("");
  };

  return (
    <div data-testid="retenidos-modo-prueba" style={{ background: "rgba(14,14,16,0.9)",
      border: "1px solid rgba(212,175,55,0.35)", borderRadius: 0, padding: "1rem 1.3rem", marginBottom: "1rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: "0.7rem" }}>
        <i className="fa fa-pause-circle" style={{ color: ORO }} />
        <b style={{ color: ORO, fontSize: "0.9rem", letterSpacing: "0.06em" }}>
          🧪 Correos retenidos por Modo Prueba ({data.total})
        </b>
        <span style={{ fontSize: "0.7rem", opacity: 0.55 }}>Notificaciones a clientes en pausa — decida su destino</span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button data-testid="retenidos-aprobar-todos" disabled={!!busy}
            onClick={() => accion("aprobar-todos", `¿Enviar ahora los ${data.total} correos retenidos a sus clientes?`, "todos-ap")}
            style={btn("#10d98e")}>
            {busy === "todos-ap" ? <i className="fa fa-spinner fa-spin" /> : <i className="fa fa-paper-plane" />} Aprobar todos
          </button>
          <button data-testid="retenidos-descartar-todos" disabled={!!busy}
            onClick={() => accion("descartar-todos", `¿Descartar los ${data.total} correos retenidos SIN enviarlos?`, "todos-de")}
            style={btn("#e11d48")}>
            {busy === "todos-de" ? <i className="fa fa-spinner fa-spin" /> : <i className="fa fa-trash" />} Descartar todos
          </button>
        </div>
      </div>
      {msg && <div data-testid="retenidos-msg" style={{ fontSize: "0.78rem", color: "#F5E7B8", marginBottom: "0.6rem" }}>{msg}</div>}
      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        {data.retenidos.map((r, i) => (
          <div key={r.seg_id || i} data-testid={`retenido-fila-${i}`} style={{ display: "flex", alignItems: "center",
            gap: 12, flexWrap: "wrap", background: "rgba(255,255,255,0.03)",
            border: "1px solid rgba(212,175,55,0.15)", padding: "0.6rem 0.9rem" }}>
            <span style={{ fontSize: "0.72rem", fontWeight: 800, letterSpacing: "0.06em",
              color: (r.estado || "").startsWith("aprob") ? "#10d98e" : "#fb7185" }}>
              {(r.estado || "").startsWith("aprob") ? "APROBADO" : "RECHAZO"}
            </span>
            <div style={{ flex: 1, minWidth: 220 }}>
              <div style={{ fontSize: "0.82rem", color: "#F5E7B8", fontWeight: 700 }}>{r.cliente || "Cliente"}</div>
              <div data-testid={`retenido-destinatario-${i}`} style={{ fontSize: "0.72rem", opacity: 0.75 }}>
                <i className="fa fa-envelope" style={{ marginRight: 5, color: ORO }} />
                {r.email_cliente || "⚠️ sin correo en la ficha"}
              </div>
              <div data-testid={`retenido-asunto-${i}`} style={{ fontSize: "0.7rem", opacity: 0.55 }}>
                {r.asunto || "(sin asunto de origen)"}
              </div>
            </div>
            <div style={{ fontSize: "0.68rem", opacity: 0.6, textAlign: "right", minWidth: 150 }}>
              <div data-testid={`retenido-fecha-${i}`}>
                <i className="fa fa-clock-o" style={{ marginRight: 4 }} />
                {(r.retenido_en || r.encolado_en || "").slice(0, 16).replace("T", " ")}
              </div>
              <div data-testid={`retenido-motivo-${i}`} style={{ color: "#e7cf7a" }}>{r.motivo || "Retenido por Modo Prueba"}</div>
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <button data-testid={`retenido-aprobar-${i}`} disabled={!!busy}
                onClick={() => accion(`${r.seg_id}/aprobar`, `¿Enviar ahora la notificación a ${r.cliente}?`, r.seg_id + "ap")}
                style={btn("#10d98e")}>
                {busy === r.seg_id + "ap" ? <i className="fa fa-spinner fa-spin" /> : <i className="fa fa-check" />} Aprobar
              </button>
              <button data-testid={`retenido-descartar-${i}`} disabled={!!busy}
                onClick={() => accion(`${r.seg_id}/descartar`, `¿Descartar el correo de ${r.cliente} SIN enviarlo?`, r.seg_id + "de")}
                style={btn("#e11d48")}>
                {busy === r.seg_id + "de" ? <i className="fa fa-spinner fa-spin" /> : <i className="fa fa-times" />} Descartar
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
