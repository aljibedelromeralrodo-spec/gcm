import { useState, useEffect } from "react";
import axios from "axios";
import { Toaster } from "sonner";
import { API_URL } from "../utils/formatters";
import { S, GOLD_GRAD, PLAYFAIR } from "../victoria/theme";
import VictoriaDashboard from "../victoria/VictoriaDashboard";
import VictoriaFicha from "../victoria/VictoriaFicha";

const inp = { width: "100%", background: "rgba(255,255,255,0.06)", border: "1px solid rgba(212,175,55,0.3)", color: "#fff", padding: "0.55rem 0.7rem", borderRadius: 4, fontSize: "0.9rem", boxSizing: "border-box" };
const lbl = { color: "#94a3b8", fontSize: "0.72rem", fontWeight: 700, display: "block", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.15em" };

export function CambiarClave({ onClose, onChanged }) {
  const [f, setF] = useState({ actual: "", nueva: "", conf: "" });
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [loading, setLoading] = useState(false);

  const enviar = async (e) => {
    e.preventDefault();
    setError(""); setOk("");
    setLoading(true);
    try {
      await axios.post(`${API_URL}/api/auth/cambiar-clave`,
        { clave_actual: f.actual, clave_nueva: f.nueva, confirmacion: f.conf });
      setOk("Contraseña actualizada correctamente");
      onChanged();
      setTimeout(onClose, 1500);
    } catch (er) {
      const d = er.response?.data?.detail;
      setError(typeof d === "string" ? d : "No se pudo cambiar la contraseña");
    }
    setLoading(false);
  };

  return (
    <div data-testid="victoria-cambiar-clave-modal" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.8)", zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
      <div style={{ background: "#141414", border: "1px solid rgba(212,175,55,0.4)", borderRadius: 4, padding: "1.8rem", width: "100%", maxWidth: 420 }}>
        <h3 style={{ color: "#FCF6BA", margin: "0 0 4px", fontSize: "1.15rem", fontFamily: PLAYFAIR }}>Cambiar mi contraseña</h3>
        <p style={{ color: "#94a3b8", fontSize: "0.8rem", margin: "0 0 14px" }}>
          Mínimo 8 caracteres, al menos una mayúscula y un número.</p>
        <form onSubmit={enviar} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div><label style={lbl}>Contraseña actual</label>
            <input type="password" style={inp} value={f.actual} required autoFocus data-testid="vw-clave-actual"
              onChange={e => setF(s => ({ ...s, actual: e.target.value }))} /></div>
          <div><label style={lbl}>Nueva contraseña</label>
            <input type="password" style={inp} value={f.nueva} required data-testid="vw-clave-nueva"
              onChange={e => setF(s => ({ ...s, nueva: e.target.value }))} /></div>
          <div><label style={lbl}>Confirmar nueva contraseña</label>
            <input type="password" style={inp} value={f.conf} required data-testid="vw-clave-conf"
              onChange={e => setF(s => ({ ...s, conf: e.target.value }))} /></div>
          {error && <p data-testid="vw-clave-error" style={{ color: "#ef4444", fontSize: "0.8rem", margin: 0 }}>{error}</p>}
          {ok && <p data-testid="vw-clave-ok" style={{ color: "#22c55e", fontSize: "0.8rem", margin: 0 }}>{ok}</p>}
          <div style={{ display: "flex", gap: 8 }}>
            <button type="submit" disabled={loading} data-testid="vw-clave-submit"
              style={{ flex: 1, background: GOLD_GRAD, color: "#0a0a0a", border: "none", borderRadius: 4, padding: "0.7rem", fontWeight: 800, cursor: "pointer" }}>
              {loading ? "Guardando…" : "Guardar mi nueva contraseña"}</button>
            <button type="button" onClick={onClose} data-testid="vw-clave-cancelar"
              style={{ background: "rgba(255,255,255,0.08)", color: "#e2e8f0", border: "1px solid rgba(148,163,184,0.3)", borderRadius: 4, padding: "0.7rem 1rem", cursor: "pointer" }}>
              Cerrar sin cambiar</button>
          </div>
        </form>
      </div>
    </div>
  );
}

const NAV_KEY = "vw_nav_v2";

export default function VictoriaWorkspace({ user, onLogout, onUserUpdate }) {
  const [showClave, setShowClave] = useState(false);
  const [nav, setNavRaw] = useState(() => {
    try {
      const s = JSON.parse(sessionStorage.getItem(NAV_KEY));
      if (s?.view) return s;
    } catch {}
    return { view: "dashboard", filtro: "todos", busqueda: "", dashY: 0 };
  });
  const setNav = (n) => { setNavRaw(n); sessionStorage.setItem(NAV_KEY, JSON.stringify(n)); };

  // Restaurar la posición exacta del panel al volver
  useEffect(() => {
    if (nav.view === "dashboard" && nav.restaurar) {
      const t = setTimeout(() => {
        window.scrollTo(0, nav.dashY || 0);
        setNav({ ...nav, restaurar: false });
      }, 120);
      return () => clearTimeout(t);
    }
  }, [nav.view]); // eslint-disable-line react-hooks/exhaustive-deps

  const abrirCliente = (c) => {
    const pasoSugerido = c.despachado ? 4 : Math.min(4, Math.max(1, { 1: 1, 2: 2, 3: 2, 4: 3, 5: 4 }[c.siguiente?.n] || 1));
    setNav({ ...nav, view: "ficha", cid: c.id, paso: pasoSugerido, docSel: null, dashY: window.scrollY });
    window.scrollTo(0, 0);
  };
  const volver = () => setNav({ ...nav, view: "dashboard", restaurar: true });

  return (
    <div data-testid="victoria-workspace" style={S.page}>
      <Toaster position="top-right" richColors theme="dark" />
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12,
        padding: "1.1rem 3rem", background: "#0a0a0a", borderBottom: "1px solid rgba(212,175,55,0.35)",
        position: "sticky", top: 0, zIndex: 50 }}>
        <div>
          <div style={{ fontFamily: PLAYFAIR, fontWeight: 700, fontSize: "1.5rem", letterSpacing: 4,
            background: GOLD_GRAD, WebkitBackgroundClip: "text",
            backgroundClip: "text", WebkitTextFillColor: "transparent" }}>CENTRAL MUTUOS</div>
          <div style={{ color: "#a1a1aa", fontSize: "0.72rem", letterSpacing: 3, marginTop: 2 }}>MÓDULO DANIELA GALINDO · CON CRECES</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span data-testid="victoria-user-nombre" style={{ color: "#e4e4e7", fontSize: "0.95rem", fontWeight: 700 }}>
            <i className="fa fa-user-circle" style={{ marginRight: 7, color: "#BF953F" }}></i>{user.nombre}</span>
          <button onClick={() => setShowClave(true)} data-testid="victoria-btn-perfil"
            style={{ background: "rgba(212,175,55,0.1)", color: "#FCF6BA", border: "1px solid rgba(212,175,55,0.4)",
              borderRadius: 4, padding: "0.55rem 1rem", fontSize: "0.85rem", fontWeight: 700, cursor: "pointer" }}>
            <i className="fa fa-key" style={{ marginRight: 6 }}></i>Cambiar contraseña</button>
          <button onClick={onLogout} data-testid="victoria-btn-salir"
            style={{ background: "rgba(239,68,68,0.1)", color: "#f87171", border: "1px solid rgba(239,68,68,0.4)",
              borderRadius: 4, padding: "0.55rem 1rem", fontSize: "0.85rem", fontWeight: 700, cursor: "pointer" }}>
            <i className="fa fa-sign-out" style={{ marginRight: 6 }}></i>Cerrar sesión</button>
        </div>
      </header>

      {user.clave_temporal && (
        <div data-testid="victoria-banner-clave-temporal" style={{ margin: "16px 3rem 0", background: "rgba(245,158,11,0.08)",
          border: "1px solid rgba(245,158,11,0.5)", borderRadius: 4, padding: "0.8rem 1.2rem", color: "#fbbf24",
          fontSize: "0.9rem", fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
          <span>Está usando una contraseña temporal. Por seguridad, cámbiela ahora.</span>
          <button onClick={() => setShowClave(true)} data-testid="victoria-banner-btn-cambiar"
            style={{ background: "#f59e0b", color: "#0a0a0a", border: "none", borderRadius: 4,
              padding: "0.45rem 1.1rem", fontWeight: 800, fontSize: "0.85rem", cursor: "pointer" }}>
            Cambiar mi contraseña ahora</button>
        </div>
      )}

      {nav.view === "dashboard" ? (
        <VictoriaDashboard onAbrirCliente={abrirCliente}
          filtro={nav.filtro} busqueda={nav.busqueda}
          onFiltro={(f) => setNav({ ...nav, filtro: f })}
          onBusqueda={(b) => setNav({ ...nav, busqueda: b })} />
      ) : (
        <VictoriaFicha cid={nav.cid} paso={nav.paso || 1} docSel={nav.docSel}
          onSetPaso={(p) => { setNav({ ...nav, paso: p }); window.scrollTo({ top: 0, behavior: "smooth" }); }}
          onSetDocSel={(d) => setNav({ ...nav, docSel: d })}
          onVolver={volver} />
      )}

      {showClave && <CambiarClave onClose={() => setShowClave(false)}
        onChanged={() => onUserUpdate({ ...user, clave_temporal: false })} />}
    </div>
  );
}
