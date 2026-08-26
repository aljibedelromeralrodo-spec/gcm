import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const ORO = "#d4af37";

export default function CarpetasFaltantes() {
  const [data, setData] = useState(null);
  const [abierto, setAbierto] = useState(false);
  const [oculto, setOculto] = useState(false);

  const cargar = useCallback(() => {
    axios.get(`${API}/api/carpetas/faltantes`)
      .then(r => setData(r.data))
      .catch(e => { if ([401, 403].includes(e.response?.status)) setOculto(true); });
  }, []);

  useEffect(() => { cargar(); }, [cargar]);

  if (oculto || !data || !data.total) return null;

  return (
    <div data-testid="carpetas-faltantes" style={{ background: "rgba(14,14,16,0.9)",
      border: "1px solid rgba(212,175,55,0.35)", padding: "1rem 1.3rem", marginBottom: "1rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}
        data-testid="carpetas-faltantes-toggle" onClick={() => setAbierto(a => !a)}>
        <i className="fa fa-folder-open" style={{ color: ORO }} />
        <b style={{ color: ORO, fontSize: "0.9rem", letterSpacing: "0.06em" }}>
          📂 Carpetas con documentos faltantes ({data.total})
        </b>
        <span style={{ fontSize: "0.7rem", opacity: 0.55 }}>gestión manual — sin envíos automáticos</span>
        <button data-testid="carpetas-faltantes-refrescar"
          onClick={(e) => { e.stopPropagation(); cargar(); }}
          style={{ marginLeft: "auto", background: "transparent", color: ORO, cursor: "pointer",
            border: `1px solid ${ORO}`, padding: "0.25rem 0.7rem", fontSize: "0.7rem", fontWeight: 700 }}>
          <i className="fa fa-refresh" /> Actualizar
        </button>
        <i className={`fa fa-chevron-${abierto ? "up" : "down"}`} style={{ color: ORO, fontSize: "0.75rem" }} />
      </div>
      {abierto && (
        <div style={{ marginTop: "0.8rem", display: "flex", flexDirection: "column", gap: "0.5rem",
          maxHeight: 420, overflowY: "auto" }}>
          {data.carpetas.map((c, i) => (
            <div key={i} data-testid={`carpeta-faltante-${i}`} style={{ display: "flex", gap: 12,
              alignItems: "flex-start", flexWrap: "wrap", background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(212,175,55,0.15)", padding: "0.55rem 0.9rem" }}>
              <div style={{ minWidth: 230, flex: 1 }}>
                <div style={{ fontSize: "0.82rem", color: "#F5E7B8", fontWeight: 700 }}>
                  {c.nombre}
                  {c.resultado_mesa && (
                    <span style={{ marginLeft: 8, fontSize: "0.62rem", letterSpacing: "0.05em",
                      color: c.resultado_mesa === "aprobado" ? "#10d98e" : "#fb7185" }}>
                      {c.resultado_mesa.toUpperCase()}
                    </span>
                  )}
                </div>
                <div style={{ fontSize: "0.68rem", opacity: 0.65 }}>
                  RUT {c.rut || "—"} · {c.docs} doc(s) · {c.tipo_cliente} · creada {c.creada.replace("T", " ")}
                </div>
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", maxWidth: 520 }}>
                {c.faltantes.map((ft, j) => (
                  <span key={j} data-testid={`faltante-chip-${i}-${j}`} style={{ fontSize: "0.66rem",
                    color: "#e7cf7a", border: "1px solid rgba(212,175,55,0.4)",
                    padding: "0.15rem 0.5rem", whiteSpace: "nowrap" }}>
                    {ft.etiqueta} (faltan {ft.faltan})
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
