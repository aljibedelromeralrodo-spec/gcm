import { useState, useEffect, useRef } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

export const EmailAutocomplete = ({ value, onChange, style, placeholder, dataTestId }) => {
  const [sugs, setSugs] = useState([]);
  const [open, setOpen] = useState(false);
  const timer = useRef(null);

  useEffect(() => {
    if (!open || (value || "").length < 2) { setSugs([]); return; }
    clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      try {
        const r = await axios.get(`${API}/api/contactos/emails`, { params: { q: value } });
        setSugs(r.data.contactos || []);
      } catch { setSugs([]); }
    }, 350);
    return () => clearTimeout(timer.current);
  }, [value, open]);

  return (
    <div style={{ position: "relative" }}>
      <input style={style} value={value} placeholder={placeholder} data-testid={dataTestId}
        onChange={e => { onChange(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 200)} />
      {open && sugs.length > 0 && (
        <div style={{ position: "absolute", top: "110%", left: 0, right: 0, background: "#1a1f2e", border: "1px solid rgba(212,175,55,0.4)", borderRadius: 8, zIndex: 40, overflow: "hidden", maxHeight: 220, overflowY: "auto" }}>
          {sugs.map((s, i) => (
            <div key={i} data-testid={`${dataTestId}-sug-${i}`}
              onMouseDown={() => { onChange(s.email); setOpen(false); }}
              style={{ padding: "0.5rem 0.8rem", cursor: "pointer", fontSize: "0.83rem", borderBottom: "1px solid rgba(255,255,255,0.05)" }}
              onMouseEnter={e => e.currentTarget.style.background = "rgba(212,175,55,0.1)"}
              onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
              <b>{s.email}</b>
              {s.nombre && <span style={{ opacity: 0.6 }}> · {s.nombre}</span>}
              <span style={{ opacity: 0.4, fontSize: "0.7rem" }}> ({s.origen})</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
