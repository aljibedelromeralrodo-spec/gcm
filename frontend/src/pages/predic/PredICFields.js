import React from "react";
import { COLORS } from "./constants";

export function Field({ label, icon, value, onChange, style, testId, placeholder }) {
  return (
    <div>
      <label style={{ fontSize: "0.8rem", color: COLORS.textMuted, marginBottom: "0.2rem", display: "block" }}>
        <i className={`fa ${icon}`} style={{ marginRight: "0.4rem", color: COLORS.accentLight }}></i>{label}
      </label>
      <input data-testid={testId} placeholder={placeholder || "$0"} value={value}
        onChange={e => {
          const raw = e.target.value.replace(/[^0-9]/g, "");
          const formatted = raw ? parseInt(raw).toLocaleString("es-CL") : "";
          onChange(formatted);
        }}
        style={style} />
    </div>
  );
}

export function UFField({ label, icon, value, onChange, style, testId }) {
  return (
    <div>
      <label style={{ fontSize: "0.8rem", color: COLORS.textMuted, marginBottom: "0.2rem", display: "block" }}>
        <i className={`fa ${icon}`} style={{ marginRight: "0.4rem", color: COLORS.accentLight }}></i>{label}
      </label>
      <input data-testid={testId} placeholder="0 UF" value={value}
        onChange={e => {
          const raw = e.target.value.replace(/[^0-9.]/g, "");
          onChange(raw);
        }}
        style={style} />
    </div>
  );
}
