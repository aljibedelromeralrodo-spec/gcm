import { useState, useEffect } from "react";
import { Toaster } from "sonner";
import { S, GOLD_GRAD, PLAYFAIR } from "../victoria/theme";
import { CambiarClave } from "./VictoriaWorkspace";
import MutuosPanel from "../victoria/MutuosPanel";
import MutuosFicha from "../victoria/MutuosFicha";

const NAV_KEY = "mutuos_nav_v1";

export default function MutuosWorkspace({ user, onLogout, onUserUpdate }) {
  const [showClave, setShowClave] = useState(false);
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

  const abrirOperacion = (o) => {
    setNav({ ...nav, view: "ficha", oid: o.id, etapa: o.etapa_actual || 1, dashY: window.scrollY });
    window.scrollTo(0, 0);
  };
  const volver = () => setNav({ ...nav, view: "panel", restaurar: true });

  return (
    <div data-testid="mutuos-workspace" style={S.page}>
      <Toaster position="top-right" richColors theme="dark" />
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12,
        padding: "1.1rem 3rem", background: "#0a0a0a", borderBottom: "1px solid rgba(212,175,55,0.35)",
        position: "sticky", top: 0, zIndex: 50 }}>
        <div>
          <div style={{ fontFamily: PLAYFAIR, fontWeight: 700, fontSize: "1.5rem", letterSpacing: 4,
            background: GOLD_GRAD, WebkitBackgroundClip: "text",
            backgroundClip: "text", WebkitTextFillColor: "transparent" }}>CENTRAL MUTUOS</div>
          <div style={{ color: "#a1a1aa", fontSize: "0.72rem", letterSpacing: 3, marginTop: 2 }}>
            MÓDULO VICTORIA VILCHES · GERENCIA DE OPERACIONES · MUTUOS</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span data-testid="mutuos-user-nombre" style={{ color: "#e4e4e7", fontSize: "0.95rem", fontWeight: 700 }}>
            <i className="fa fa-user-circle" style={{ marginRight: 7, color: "#BF953F" }}></i>{user.nombre}</span>
          <button onClick={() => setShowClave(true)} data-testid="mutuos-btn-perfil"
            style={{ background: "rgba(212,175,55,0.1)", color: "#FCF6BA", border: "1px solid rgba(212,175,55,0.4)",
              borderRadius: 4, padding: "0.55rem 1rem", fontSize: "0.85rem", fontWeight: 700, cursor: "pointer" }}>
            <i className="fa fa-key" style={{ marginRight: 6 }}></i>Cambiar contraseña</button>
          <button onClick={onLogout} data-testid="mutuos-btn-salir"
            style={{ background: "rgba(239,68,68,0.1)", color: "#f87171", border: "1px solid rgba(239,68,68,0.4)",
              borderRadius: 4, padding: "0.55rem 1rem", fontSize: "0.85rem", fontWeight: 700, cursor: "pointer" }}>
            <i className="fa fa-sign-out" style={{ marginRight: 6 }}></i>Cerrar sesión</button>
        </div>
      </header>

      {user.clave_temporal && (
        <div data-testid="mutuos-banner-clave-temporal" style={{ margin: "16px 3rem 0", background: "rgba(245,158,11,0.08)",
          border: "1px solid rgba(245,158,11,0.5)", borderRadius: 4, padding: "0.8rem 1.2rem", color: "#fbbf24",
          fontSize: "0.9rem", fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
          <span>Está usando una contraseña temporal. Por seguridad, cámbiela ahora.</span>
          <button onClick={() => setShowClave(true)} data-testid="mutuos-banner-btn-cambiar"
            style={{ background: "#f59e0b", color: "#0a0a0a", border: "none", borderRadius: 4,
              padding: "0.45rem 1.1rem", fontWeight: 800, fontSize: "0.85rem", cursor: "pointer" }}>
            Cambiar mi contraseña ahora</button>
        </div>
      )}

      {nav.view === "panel" ? (
        <MutuosPanel onAbrirOperacion={abrirOperacion} />
      ) : (
        <MutuosFicha oid={nav.oid} etapa={nav.etapa || 1}
          onSetEtapa={(e) => { setNav({ ...nav, etapa: e }); window.scrollTo({ top: 0, behavior: "smooth" }); }}
          onVolver={volver} />
      )}

      {showClave && <CambiarClave onClose={() => setShowClave(false)}
        onChanged={() => onUserUpdate({ ...user, clave_temporal: false })} />}
    </div>
  );
}
