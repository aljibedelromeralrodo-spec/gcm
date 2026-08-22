import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { API_URL } from "../utils/formatters";
import { S, PLAYFAIR } from "./theme";

export default function MutuosPanel({ onAbrirOperacion }) {
  const [data, setData] = useState(null);
  const [cid, setCid] = useState("");
  const cargar = () => axios.get(`${API_URL}/api/mutuos/panel`).then(r => setData(r.data))
    .catch(e => toast.error(e.response?.data?.detail || "No se pudo cargar el panel"));
  useEffect(() => {
    cargar();
    const t = setInterval(cargar, 30000);
    return () => clearInterval(t);
  }, []);

  const crear = async () => {
    if (!cid) { toast.error("Elija primero el cliente de la bóveda"); return; }
    try {
      const r = await axios.post(`${API_URL}/api/mutuos/operaciones`, { cliente_id: cid });
      toast.success(r.data.mensaje);
      cargar();
      onAbrirOperacion({ id: r.data.operacion_id, etapa_actual: 1 });
    } catch (e) { toast.error(e.response?.data?.detail || "No se pudo crear la operación"); }
  };

  if (!data) return <div style={{ padding: "4rem", color: "#a1a1aa", fontSize: "1.1rem" }}>Cargando operaciones…</div>;
  const k = data.kpis;

  return (
    <div data-testid="mutuos-panel" style={{ padding: "2.5rem 3rem", maxWidth: 1500, margin: "0 auto" }}>
      <div style={S.label}>Gerencia de Operaciones · Guía de Usuario Mutuos</div>
      <h1 style={{ ...S.h1, margin: "6px 0 24px" }}>Operaciones hipotecarias</h1>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(230px, 1fr))", gap: 18 }}>
        <div style={{ ...S.card, padding: "1.4rem 1.6rem" }} data-testid="mutuos-kpi-proceso">
          <div style={S.label}>Operaciones en proceso</div>
          <div style={{ ...S.kpiValue, fontSize: "2.8rem" }}>{k.en_proceso}</div>
        </div>
        <div style={{ ...S.card, padding: "1.4rem 1.6rem" }} data-testid="mutuos-kpi-riesgo">
          <div style={S.label}>Enviadas a revisión de riesgo</div>
          <div style={{ ...S.kpiValue, fontSize: "2.8rem", color: "#4ade80" }}>{k.enviadas_riesgo}</div>
        </div>
        <div style={{ ...S.card, padding: "1.4rem 1.6rem" }} data-testid="mutuos-kpi-boveda">
          <div style={S.label}>Clientes en la bóveda (puente con Daniela)</div>
          <div style={{ ...S.kpiValue, fontSize: "2.8rem", color: "#FCF6BA" }}>{k.clientes_boveda}</div>
        </div>
      </div>

      <div style={{ ...S.card, padding: "1.6rem 2rem", marginTop: 22 }}>
        <h2 style={{ ...S.h2, marginBottom: 6 }}>Crear operación desde la bóveda</h2>
        <p style={{ ...S.body, fontSize: "0.9rem", color: "#a1a1aa", margin: "0 0 12px" }}>
          Puente de datos con el módulo de Daniela Galindo: nombre, RUT, codeudor, rol y dirección llegan autocompletados desde los documentos de la bóveda.</p>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <select data-testid="mutuos-select-cliente" value={cid} onChange={e => setCid(e.target.value)}
            style={{ ...S.input, flex: "1 1 320px" }}>
            <option value="">Elegir cliente de la bóveda…</option>
            {data.clientes_disponibles.map(c => <option key={c.id} value={c.id}>{c.nombre} — {c.rut || "sin RUT"}</option>)}
          </select>
          <button data-testid="mutuos-crear-operacion" onClick={crear} style={S.btnGold}>
            Crear operación con datos autocompletados</button>
        </div>
      </div>

      <div style={{ ...S.card, padding: "1.6rem 2rem", marginTop: 22 }}>
        <h2 style={{ ...S.h2, marginBottom: 10 }}>Mis operaciones ({data.operaciones.length})</h2>
        {data.operaciones.length === 0 && <p style={{ ...S.body, color: "#71717a" }}>Aún no hay operaciones: cree la primera desde un cliente de la bóveda.</p>}
        {data.operaciones.map(o => (
          <div key={o.id} data-testid={`mutuos-op-${o.id}`} style={{ borderTop: "1px solid rgba(255,255,255,0.08)", padding: "1rem 0", display: "flex", justifyContent: "space-between", gap: 14, flexWrap: "wrap", alignItems: "center" }}>
            <div>
              <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                <span style={{ fontFamily: PLAYFAIR, fontSize: "1.2rem", fontWeight: 700, color: "#fff" }}>
                  #{o.numero} · {o.cliente}</span>
                <span style={S.pill(o.estado === "enviada_riesgo" ? "rgba(34,197,94,0.15)" : "rgba(212,175,55,0.18)",
                  o.estado === "enviada_riesgo" ? "#4ade80" : "#FCF6BA")}>
                  {o.estado === "enviada_riesgo" ? "EN REVISIÓN DE RIESGO" : `ETAPA ${o.etapa_actual} DE 6`}</span>
              </div>
              <div style={{ color: "#a1a1aa", fontSize: "0.9rem", marginTop: 4 }}>
                RUT {o.rut || "—"} · {o.autorizadas} etapa(s) autorizadas · creada {String(o.creado || "").slice(0, 10)}</div>
            </div>
            <button data-testid={`mutuos-abrir-${o.id}`} onClick={() => onAbrirOperacion(o)}
              style={{ ...S.btnGold, ...S.btnSmall, padding: "0.7rem 1.3rem" }}>
              Abrir la operación y su flujo guiado →</button>
          </div>
        ))}
      </div>
    </div>
  );
}
