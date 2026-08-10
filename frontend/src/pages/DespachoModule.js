import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

const ORO = "#D4AF37";
const mono = "'JetBrains Mono', 'Courier New', monospace";

export default function DespachoModule() {
  const [cola, setCola] = useState([]);
  const [despachados, setDespachados] = useState(0);
  const [sinTel, setSinTel] = useState(0);
  const [busy, setBusy] = useState(false);
  const [ultimo, setUltimo] = useState("");

  const cargar = useCallback(async () => {
    try {
      const r = await axios.get(`${API_URL}/api/despacho/cola`);
      setCola(r.data.pendientes || []);
      setDespachados(r.data.despachados || 0);
      setSinTel(r.data.sin_telefono || 0);
    } catch { /* silencioso */ }
  }, []);
  useEffect(() => { cargar(); }, [cargar]);

  const actual = cola[0];
  const siguiente = cola[1];

  const disparar = async () => {
    if (!actual || busy) return;
    setBusy(true);
    try {
      const r = await axios.post(`${API_URL}/api/despacho/${actual.id}/disparar`);
      window.open(r.data.whatsapp, "_blank", "noopener");
      setUltimo(r.data.cliente);
      setDespachados(r.data.despachados);
      setCola(prev => prev.slice(1));
    } catch (e) { alert("❌ " + (e?.response?.data?.detail || e.message)); }
    setBusy(false);
  };

  return (
    <div className="module-content" data-testid="despacho-module"
      style={{ fontFamily: mono, minHeight: "80vh", display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 14, marginBottom: "2rem", flexWrap: "wrap" }}>
        <h2 style={{ color: ORO, letterSpacing: "0.12em", margin: 0 }}>🚀 DESPACHO VELOZ</h2>
        <span style={{ fontSize: "0.7rem", opacity: 0.5, letterSpacing: "0.2em" }}>COLA DE CAMPAÑA · TERMINAL DE MANDO</span>
        <div data-testid="despacho-contador" style={{ marginLeft: "auto", fontSize: "0.95rem", letterSpacing: "0.06em" }}>
          <span style={{ color: "#34eab9", fontWeight: 800 }}>Despachados: {despachados}</span>
          <span style={{ color: "#4a4a4a", margin: "0 10px" }}>/</span>
          <span style={{ color: "#e7cf7a", fontWeight: 800 }}>Pendientes: {cola.length}</span>
        </div>
      </div>

      {actual ? (
        <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "2rem" }}>
          <div data-testid="despacho-actual" style={{ textAlign: "center", border: "1px solid rgba(212,175,55,0.45)",
            background: "linear-gradient(165deg, #0d0b06, #050505)", padding: "2rem 3.5rem",
            boxShadow: "0 0 50px -18px rgba(212,175,55,0.6)" }}>
            <div style={{ color: "#6b6b6b", fontSize: "0.62rem", letterSpacing: "0.3em", marginBottom: 10 }}>CLIENTE EN CURSOR</div>
            <div style={{ color: "#FCF6BA", fontSize: "1.7rem", fontWeight: 800, letterSpacing: "0.04em" }}>{actual.nombre}</div>
            <div style={{ color: "#9a8c52", fontSize: "0.85rem", marginTop: 8 }}>{actual.telefono} {actual.proyecto ? `· ${actual.proyecto}` : ""}</div>
          </div>

          <button data-testid="despacho-disparar-btn" onClick={disparar} disabled={busy}
            style={{ background: "linear-gradient(135deg, #BF953F, #FCF6BA 45%, #AA771C)", color: "#0a0a0a",
              border: "1px solid #FCF6BA", fontFamily: mono, fontWeight: 900, fontSize: "1.25rem",
              letterSpacing: "0.1em", padding: "1.6rem 3.5rem", cursor: "pointer", opacity: busy ? 0.5 : 1,
              boxShadow: "0 0 60px -12px rgba(212,175,55,0.9)" }}>
            🚀 DISPARAR SIGUIENTE INVITACIÓN
          </button>

          <div style={{ textAlign: "center", fontSize: "0.72rem", color: "#4a4a4a", letterSpacing: "0.08em" }}>
            {ultimo && <div data-testid="despacho-ultimo" style={{ color: "#34eab9", marginBottom: 6 }}>✓ {ultimo} → ENTREGADO</div>}
            {siguiente && <div>SIGUIENTE EN COLA: <span style={{ color: "#9a8c52" }}>{siguiente.nombre}</span></div>}
            <div style={{ marginTop: 10, maxWidth: 460, lineHeight: 1.7 }}>
              Al disparar: se abre WhatsApp con el mensaje Maserati + link VIP público (@CentralMutuos),
              el cliente queda ENTREGADO y el cursor avanza solo.
            </div>
          </div>
        </div>
      ) : (
        <div data-testid="despacho-vacio" style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center",
          justifyContent: "center", gap: 12, color: "#9a8c52" }}>
          <div style={{ fontSize: "2rem" }}>✓</div>
          <div style={{ letterSpacing: "0.14em", fontSize: "0.9rem" }}>COLA VACÍA — CAMPAÑA AL DÍA</div>
          <div style={{ fontSize: "0.7rem", color: "#4a4a4a" }}>Carga un Excel en el Centro de Ventas para llenar la fila de espera.</div>
        </div>
      )}
      {sinTel > 0 && (
        <div style={{ textAlign: "center", fontSize: "0.66rem", color: "#7a6a2f", letterSpacing: "0.06em" }}>
          ⚠ {sinTel} prospecto(s) sin teléfono quedaron fuera de la cola — complétalos en el Centro de Ventas.
        </div>
      )}
    </div>
  );
}
