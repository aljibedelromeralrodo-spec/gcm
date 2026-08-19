import { useState } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

export const ROLES_PREVIEW = [
  { rol: "gerencia", label: "Gerencia Comercial", icono: "fa-line-chart" },
  { rol: "administracion", label: "Administrativo", icono: "fa-database" },
  { rol: "postventa", label: "Postventa", icono: "fa-heart" },
  { rol: "ejecutivo", perfil: "A", label: "Ejecutivo", icono: "fa-user" },
  { rol: "broker", perfil: "D", label: "Broker Interno", icono: "fa-briefcase" },
  { rol: "broker", perfil: "D", label: "Broker Externo", icono: "fa-globe" },
];

export default function VistaPreviaRol({ onActivar, onClose }) {
  const [pwd, setPwd] = useState("");
  const [verificado, setVerificado] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const verificar = async () => {
    if (!pwd) { setErr("Ingrese su contraseña de Administrador"); return; }
    setBusy(true); setErr("");
    try {
      await axios.post(`${API}/api/admin/verificar-password`, { password: pwd });
      setVerificado(true);
    } catch (e) {
      setErr(e.response?.data?.detail || "Contraseña de Administrador incorrecta");
    }
    setBusy(false);
  };

  return (
    <div data-testid="preview-modal" onClick={onClose}
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", zIndex: 5000,
        display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div onClick={e => e.stopPropagation()}
        style={{ background: "#111214", border: "1px solid rgba(212,175,55,0.45)", borderRadius: 14,
          padding: "1.6rem 1.8rem", width: 440, maxWidth: "92vw" }}>
        <h3 style={{ color: "#d4af37", margin: "0 0 6px", fontSize: "1rem" }}>
          👁 Vista previa por rol</h3>
        <p style={{ color: "#94a3b8", fontSize: "0.72rem", margin: "0 0 14px", lineHeight: 1.55 }}>
          Función exclusiva e intransferible del Administrador. Simula exactamente cómo ve el sistema
          cada rol sin cerrar su sesión. Los cambios que realice en simulación quedan registrados
          en el log de auditoría.</p>
        {!verificado ? (
          <>
            <input data-testid="preview-password" type="password" value={pwd} autoFocus
              onChange={e => setPwd(e.target.value)} onKeyDown={e => e.key === "Enter" && verificar()}
              placeholder="Confirme su contraseña de Administrador"
              style={{ width: "100%", boxSizing: "border-box", background: "rgba(255,255,255,0.06)",
                border: "1px solid rgba(212,175,55,0.4)", color: "#fff", padding: "0.6rem 0.8rem",
                borderRadius: 8, fontSize: "0.85rem", marginBottom: 10 }} />
            {err && <p data-testid="preview-error" style={{ color: "#f87171", fontSize: "0.7rem", margin: "0 0 10px", fontWeight: 700 }}>{err}</p>}
            <div style={{ display: "flex", gap: 8 }}>
              <button data-testid="preview-verificar" onClick={verificar} disabled={busy}
                style={{ flex: 1, background: "linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C)",
                  color: "#0a0a0a", border: "none", borderRadius: 8, padding: "0.6rem",
                  fontWeight: 800, cursor: "pointer" }}>
                {busy ? "Verificando…" : "Verificar identidad"}</button>
              <button onClick={onClose} style={{ background: "transparent", color: "#94a3b8",
                border: "1px solid rgba(255,255,255,0.2)", borderRadius: 8, padding: "0.6rem 1rem", cursor: "pointer" }}>
                Cancelar</button>
            </div>
          </>
        ) : (
          <>
            <p style={{ color: "#4ade80", fontSize: "0.7rem", fontWeight: 800, margin: "0 0 10px" }}>
              ✓ Identidad verificada. Seleccione el rol a simular:</p>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              {ROLES_PREVIEW.map(r => (
                <button key={r.label} data-testid={`preview-rol-${r.label.toLowerCase().replace(/ /g, "-")}`}
                  onClick={() => onActivar(r)}
                  style={{ background: "rgba(212,175,55,0.08)", border: "1px solid rgba(212,175,55,0.35)",
                    color: "#e2e8f0", borderRadius: 10, padding: "0.7rem 0.6rem", cursor: "pointer",
                    fontWeight: 800, fontSize: "0.74rem", textAlign: "left" }}>
                  <i className={`fa ${r.icono}`} style={{ color: "#d4af37", marginRight: 7 }}></i>
                  {r.label}</button>
              ))}
            </div>
            <button onClick={onClose} style={{ marginTop: 12, width: "100%", background: "transparent",
              color: "#94a3b8", border: "1px solid rgba(255,255,255,0.2)", borderRadius: 8,
              padding: "0.5rem", cursor: "pointer", fontSize: "0.72rem" }}>Cancelar</button>
          </>
        )}
      </div>
    </div>
  );
}
