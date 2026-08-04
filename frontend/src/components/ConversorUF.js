import { useState, useEffect } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

const fmtCLP = (n) => "$" + Math.round(n).toLocaleString("es-CL");

export default function ConversorUF({ style }) {
  const [uf, setUf] = useState(null);
  const [ufVal, setUfVal] = useState("");
  const [clpVal, setClpVal] = useState("");

  useEffect(() => {
    axios.get(`${API}/api/valor-uf`).then(r => setUf(Number(r.data.valor_uf || 0))).catch(() => {});
  }, []);

  const onUf = (v) => {
    setUfVal(v);
    const n = parseFloat(String(v).replace(/\./g, "").replace(",", "."));
    setClpVal(uf && !isNaN(n) ? fmtCLP(n * uf) : "");
  };
  const onClp = (v) => {
    const limpio = String(v).replace(/[^\d]/g, "");
    setClpVal(limpio ? fmtCLP(Number(limpio)) : "");
    setUfVal(uf && limpio ? (Number(limpio) / uf).toFixed(2) : "");
  };

  const inpS = { width: "100%", padding: "0.5rem 0.7rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.4)", fontSize: "1.05rem", fontWeight: 700, background: "rgba(255,255,255,0.06)", color: "inherit" };

  return (
    <div data-testid="conversor-uf" style={{ padding: "0.8rem 1rem", borderRadius: 0, border: "1px solid rgba(212,175,55,0.35)", background: "rgba(212,175,55,0.06)", ...style }}>
      <div style={{ fontWeight: 800, fontSize: "0.85rem", marginBottom: 6, color: "var(--gold, #d4af37)" }}>
        <i className="fa fa-exchange" style={{ marginRight: "0.4rem" }} />
        Conversor UF ⇄ Pesos {uf ? `(UF hoy: ${fmtCLP(uf)})` : "(cargando UF…)"}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", gap: 8, alignItems: "center" }}>
        <label style={{ fontSize: 11, fontWeight: 700 }}>UF
          <input data-testid="conversor-uf-input" style={inpS} value={ufVal} onChange={e => onUf(e.target.value)} placeholder="Ej: 3.500" />
        </label>
        <i className="fa fa-arrows-h" style={{ marginTop: 14, opacity: 0.6 }} />
        <label style={{ fontSize: 11, fontWeight: 700 }}>Pesos (CLP)
          <input data-testid="conversor-clp-input" style={inpS} value={clpVal} onChange={e => onClp(e.target.value)} placeholder="Ej: $143.000.000" />
        </label>
      </div>
    </div>
  );
}
