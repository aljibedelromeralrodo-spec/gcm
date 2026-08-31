import React from "react";

// Input inteligente para montos en UF. Si el usuario ingresa un número
// grande (>= 20000) se asume que es CLP y se convierte automáticamente
// dividiendo por el valor de la UF del día (al hacer blur o pegar).
export default function UFAmountInput({ value, onChange, uf, testid, dataTestid }) {
  const [raw, setRaw] = React.useState(value == null || value === "" ? "" : String(value));
  React.useEffect(() => {
    setRaw(value == null || value === "" ? "" : String(value));
  }, [value]);

  const normalize = (str) => {
    if (str == null) return NaN;
    let s = String(str).trim().replace(/\$/g, "").replace(/\s+/g, "");
    if (s === "") return NaN;
    if (s.includes(",") && s.includes(".")) {
      s = s.replace(/\./g, "").replace(",", ".");
    } else if (s.includes(",") && !s.includes(".")) {
      s = s.replace(",", ".");
    } else if (s.includes(".")) {
      const parts = s.split(".");
      const lastLen = parts[parts.length - 1].length;
      if (parts.length > 2 || lastLen === 3) s = parts.join("");
    }
    return Number(s);
  };

  const commit = (str) => {
    const n = normalize(str);
    if (isNaN(n)) { onChange(""); return; }
    if (n >= 20000 && uf > 0) {
      const ufVal = +(n / uf).toFixed(2);
      onChange(ufVal);
      setRaw(String(ufVal));
    } else {
      const ufVal = +Number(n).toFixed(2);
      onChange(ufVal);
      setRaw(String(ufVal));
    }
  };

  const preview = (() => {
    const n = normalize(raw);
    if (isNaN(n) || n === 0) return null;
    if (n >= 20000 && uf > 0) {
      const ufEq = (n / uf);
      return `≈ UF ${ufEq.toLocaleString('es-CL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} (CLP detectado)`;
    }
    const clpEq = Math.round(n * uf);
    return `≈ $ ${clpEq.toLocaleString('es-CL')} CLP`;
  })();

  return (
    <div>
      <input
        type="text"
        inputMode="decimal"
        value={raw}
        onChange={(e) => setRaw(e.target.value)}
        onBlur={(e) => commit(e.target.value)}
        onPaste={(e) => {
          const pasted = (e.clipboardData || window.clipboardData).getData("text");
          if (pasted && pasted.length > 4) {
            e.preventDefault();
            commit(pasted);
          }
        }}
        placeholder="Ingresá UF o CLP…"
        data-testid={dataTestid || testid}
        style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, border: "1px solid #d4d4d8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }}
      />
      {preview && (
        <div style={{ fontSize: 10, color: "#b8942e", marginTop: 2, fontWeight: 500 }}>{preview}</div>
      )}
    </div>
  );
}
