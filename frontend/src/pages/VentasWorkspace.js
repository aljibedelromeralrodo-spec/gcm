import { useState, useEffect } from "react";
import { Toaster } from "sonner";
import { S, GOLD_GRAD, PLAYFAIR } from "../victoria/theme";
import { CambiarClave } from "./VictoriaWorkspace";
import VentasPanel from "../victoria/VentasPanel";
import VentasFicha from "../victoria/VentasFicha";

const NAV_KEY = "ventas_nav_v1";
const EJECUTIVOS_VENTAS = { yerile: "Yerile Barrera", deysi: "Deisy Salazar", gerardo: "Gerardo Barrera" };

export default function VentasWorkspace({ user, onLogout, onUserUpdate }) {
  const [showClave, setShowClave] = useState(false);
  const [ejSel, setEjSel] = useState(() => sessionStorage.getItem("ventas_ej_sel") || "");
  const ejecutivo = user.ventas_ejecutivo || ejSel;
  const elegirEj = (v) => { setEjSel(v); sessionStorage.setItem("ventas_ej_sel", v); };
  const [nav, setNavRaw] = useState(() => {
    try {
      const s = JSON.parse(sessionStorage.getItem(NAV_KEY));
      if (s?.view) return s;
    } catch {}
    return { view: "panel", dashY: 0 };
  });
  const setNav = (n) => { setNavRaw(n); sessionStorage.setItem(NAV_KEY, JSON.stringify(n)); };

  useEffect(() => {
    if (nav.view === "panel" && nav.restaurar) {
      const t = setTimeout(() => {
        window.scrollTo(0, nav.dashY || 0);
        setNav({ ...nav, restaurar: false });
      }, 120);
      return () => clearTimeout(t);
    }
  }, [nav.view]); // eslint-disable-line react-hooks/exhaustive-deps

  const abrirCliente = (c) => {
    setNav({ ...nav, view: "ficha", cid: c.id, dashY: window.scrollY });
    window.scrollTo(0, 0);
  };
  const volver = () => setNav({ ...nav, view: "panel", restaurar: true });

  return (
    <div data-testid="ventas-workspace" style={S.page}>
      <Toaster position="top-right" richColors theme="dark" />
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12,
        padding: "1.1rem 3rem", background: "#0a0a0a", borderBottom: "1px solid rgba(212,175,55,0.35)",
        position: "sticky", top: 0, zIndex: 50 }}>
        <div>
          <div style={{ fontFamily: PLAYFAIR, fontWeight: 700, fontSize: "1.5rem", letterSpacing: 4,
            background: GOLD_GRAD, WebkitBackgroundClip: "text",
            backgroundClip: "text", WebkitTextFillColor: "transparent" }}>CENTRAL MUTUOS</div>
          <div style={{ color: "#a1a1aa", fontSize: "0.72rem", letterSpacing: 3, marginTop: 2 }}>MÓDULO VENTAS · ENTREGA INMEDIATA</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span data-testid="ventas-user-nombre" style={{ color: "#e4e4e7", fontSize: "0.95rem", fontWeight: 700 }}>
            <i className="fa fa-user-circle" style={{ marginRight: 7, color: "#BF953F" }}></i>{user.nombre}</span>
          <button onClick={() => setShowClave(true)} data-testid="ventas-btn-perfil"
            style={{ background: "rgba(212,175,55,0.1)", color: "#FCF6BA", border: "1px solid rgba(212,175,55,0.4)",
              borderRadius: 4, padding: "0.55rem 1rem", fontSize: "0.85rem", fontWeight: 700, cursor: "pointer" }}>
            <i className="fa fa-key" style={{ marginRight: 6 }}></i>Cambiar contraseña</button>
          <button onClick={onLogout} data-testid="ventas-btn-salir"
            style={{ background: "rgba(239,68,68,0.1)", color: "#f87171", border: "1px solid rgba(239,68,68,0.4)",
              borderRadius: 4, padding: "0.55rem 1rem", fontSize: "0.85rem", fontWeight: 700, cursor: "pointer" }}>
            <i className="fa fa-sign-out" style={{ marginRight: 6 }}></i>Cerrar sesión</button>
        </div>
      </header>

      {user.clave_temporal && (
        <div data-testid="ventas-banner-clave-temporal" style={{ margin: "16px 3rem 0", background: "rgba(245,158,11,0.08)",
          border: "1px solid rgba(245,158,11,0.5)", borderRadius: 4, padding: "0.8rem 1.2rem", color: "#fbbf24",
          fontSize: "0.9rem", fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
          <span>Está usando una contraseña temporal. Por seguridad, cámbiela ahora.</span>
          <button onClick={() => setShowClave(true)} data-testid="ventas-banner-btn-cambiar"
            style={{ background: "#f59e0b", color: "#0a0a0a", border: "none", borderRadius: 4,
              padding: "0.45rem 1.1rem", fontWeight: 800, fontSize: "0.85rem", cursor: "pointer" }}>
            Cambiar mi contraseña ahora</button>
        </div>
      )}

      {!user.ventas_ejecutivo && (
        <div data-testid="ventas-selector-bar" style={{ margin: "16px 3rem 0", background: "rgba(212,175,55,0.06)",
          border: "1px solid rgba(212,175,55,0.4)", borderRadius: 4, padding: "0.8rem 1.2rem",
          display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
          <span style={{ color: "#FCF6BA", fontSize: "0.9rem", fontWeight: 700 }}>
            <i className="fa fa-users" style={{ marginRight: 7 }}></i>Vista de administrador — Seleccione un ejecutivo de Ventas:</span>
          <select data-testid="ventas-selector-ejecutivo" value={ejSel} onChange={e => elegirEj(e.target.value)}
            style={{ background: "#0a0a0a", color: "#e4e4e7", border: "1px solid rgba(212,175,55,0.5)",
              borderRadius: 4, padding: "0.5rem 0.9rem", fontSize: "0.9rem", fontWeight: 700 }}>
            <option value="">— Elegir ejecutivo —</option>
            {Object.entries(EJECUTIVOS_VENTAS).map(([cod, nom]) => <option key={cod} value={cod}>{nom}</option>)}
          </select>
        </div>
      )}

      {nav.view === "panel" ? (
        <VentasPanel ejecutivo={ejecutivo} onAbrirCliente={abrirCliente} />
      ) : (
        <VentasFicha cid={nav.cid} onVolver={volver} />
      )}

      {showClave && <CambiarClave onClose={() => setShowClave(false)}
        onChanged={() => onUserUpdate({ ...user, clave_temporal: false })} />}
    </div>
  );
}
