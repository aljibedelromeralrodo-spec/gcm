import { useState } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

// Estilo premium "Terminal de Inversión": gradiente slate + halo suave, sin colores planos
export const estiloConfianza = (confianza, campo) => {
  const c = (confianza || {})[campo];
  if (c === "alta") return {
    border: "1px solid rgba(52, 211, 153, 0.45)",
    background: "linear-gradient(180deg, rgba(16,185,129,0.08) 0%, rgba(15,23,42,0.55) 100%)",
    boxShadow: "0 0 0 1px rgba(52,211,153,0.14), 0 8px 24px -10px rgba(16,185,129,0.35), inset 0 1px 0 rgba(255,255,255,0.04)",
    borderRadius: "2px",
  };
  if (c === "dudosa") return {
    border: "1px solid rgba(251, 191, 36, 0.45)",
    background: "linear-gradient(180deg, rgba(245,158,11,0.08) 0%, rgba(15,23,42,0.55) 100%)",
    boxShadow: "0 0 0 1px rgba(251,191,36,0.14), 0 8px 24px -10px rgba(245,158,11,0.38), inset 0 1px 0 rgba(255,255,255,0.04)",
    borderRadius: "2px",
  };
  return {};
};

// Hook compartido: autocompletado enriquecido + Guardar y Aprender
export function useAprendizaje() {
  const [confianza, setConfianza] = useState({});
  const [extraido, setExtraido] = useState({});

  const autofill = async (nombre) => {
    const d = await axios.get(`${API}/api/aprendizaje/datos-cliente`, { params: { nombre }, timeout: 120000 });
    setConfianza(d.data.confianza || {});
    setExtraido({
      email: d.data.email || "", telefono: d.data.telefono || "", rut: d.data.rut || "",
      ejecutivo_nombre: d.data.ejecutivo_nombre || "", ejecutivo_email: d.data.ejecutivo_email || "",
      ejecutivo_interno: d.data.ejecutivo_interno || "", remitente: d.data.remitente || "",
    });
    return d.data;
  };

  const guardarAprender = async (nombre, pares) => {
    let n = 0;
    const nuevas = { ...confianza };
    const validado = { ...extraido };
    for (const [campo, val] of pares) {
      const orig = (extraido[campo] || "").trim();
      const v = (val || "").trim();
      if (v && v !== orig) {
        try {
          await axios.post(`${API}/api/aprendizaje/correccion`, {
            cliente: nombre, campo, valor_correcto: v, valor_extraido: orig, remitente: extraido.remitente || "",
          });
          nuevas[campo] = "alta"; validado[campo] = v; n++;
        } catch (_e) { /* siguiente campo */ }
      } else if (v && confianza[campo] === "dudosa") {
        nuevas[campo] = "alta"; validado[campo] = v;
      }
    }
    setConfianza(nuevas);
    setExtraido(validado);
    return n;
  };

  return { confianza, extraido, autofill, guardarAprender, setConfianza, setExtraido };
}

const dot = (grad, glow) => ({
  width: 9, height: 9, borderRadius: "50%", flexShrink: 0,
  background: grad, boxShadow: `0 0 8px ${glow}`,
});

export function PanelAprendizaje({ confianza, onGuardar, testId }) {
  if (!Object.values(confianza || {}).some(Boolean)) return null;
  return (
    <div data-testid={`${testId}-panel`} style={{
      display: "flex", alignItems: "center", gap: "1.1rem", flexWrap: "wrap",
      marginTop: "0.9rem", padding: "0.65rem 1rem",
      background: "linear-gradient(135deg, rgba(30,41,59,0.55) 0%, rgba(15,23,42,0.8) 100%)",
      border: "1px solid rgba(148,163,184,0.14)", borderRadius: "2px",
      backdropFilter: "blur(14px)", WebkitBackdropFilter: "blur(14px)",
      boxShadow: "0 10px 30px -14px rgba(2,6,23,0.7), inset 0 1px 0 rgba(255,255,255,0.04)",
    }}>
      <span style={{ fontSize: "0.66rem", letterSpacing: "0.16em", textTransform: "uppercase", color: "#94a3b8", fontWeight: 700 }}>
        Motor de Extracción · IA
      </span>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: "0.76rem", color: "#cbd5e1" }}>
        <span style={dot("radial-gradient(circle at 35% 35%, #6ee7b7, #059669)", "rgba(16,185,129,0.55)")} />
        Dato seguro (2+ fuentes)
      </span>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: "0.76rem", color: "#cbd5e1" }}>
        <span style={dot("radial-gradient(circle at 35% 35%, #fcd34d, #d97706)", "rgba(245,158,11,0.55)")} />
        Por validar antes de enviar
      </span>
      <button data-testid={testId} onClick={onGuardar} style={{
        marginLeft: "auto", background: "linear-gradient(135deg, rgba(51,65,85,0.9), rgba(15,23,42,0.95))",
        border: "1px solid rgba(212,175,55,0.45)", color: "#e7cf7a", borderRadius: "2px",
        padding: "0.45rem 1.1rem", cursor: "pointer", fontWeight: 700, fontSize: "0.74rem",
        letterSpacing: "0.1em", textTransform: "uppercase",
        boxShadow: "0 6px 18px -8px rgba(212,175,55,0.35), inset 0 1px 0 rgba(255,255,255,0.06)",
      }}>
        <i className="fa fa-graduation-cap" style={{ marginRight: 7 }} />Guardar y Aprender
      </button>
    </div>
  );
}
