import { useState, useEffect } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

const card = { background: "rgba(30,41,59,0.55)", border: "1.5px solid rgba(148,163,184,0.25)", borderRadius: 12, padding: "1rem 1.2rem" };

export default function VentasReporte() {
  const [data, setData] = useState(null);
  useEffect(() => {
    const cargar = () => axios.get(`${API_URL}/api/ventas/reporte`).then(r => setData(r.data)).catch(() => {});
    cargar();
    const t = setInterval(cargar, 30000);
    return () => clearInterval(t);
  }, []);

  if (!data) return <div style={{ color: "#94a3b8", padding: "1rem" }}>Cargando reporte de Ventas…</div>;

  return (
    <div data-testid="ventas-reporte" style={{ marginTop: 14 }}>
      <div style={{ color: "#d4af37", fontWeight: 800, fontSize: "0.95rem", marginBottom: 10 }}>
        🧲 Reporte en tiempo real — Módulo Ventas (asignación alternada: documentación incompleta + entrega inmediata)</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        {Object.entries(data.ejecutivos).map(([ej, e]) => (
          <div key={ej} data-testid={`reporte-ejecutivo-${ej}`} style={card}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
              <span style={{ color: "#e2e8f0", fontWeight: 800, fontSize: "1rem" }}>👤 {e.nombre}</span>
              <span style={{ color: "#94a3b8", fontSize: "0.75rem" }}>
                {e.total} cliente(s) · {e.incompletos} incompleto(s) · {e.faltantes_total} doc(s) faltantes ·
                promedio {e.dias_promedio_sin_completar} día(s) sin completar</span>
            </div>
            {e.clientes.length === 0 && <div style={{ color: "#64748b", fontSize: "0.8rem", marginTop: 8 }}>Sin clientes asignados aún.</div>}
            {e.clientes.map(c => (
              <div key={c.id} style={{ borderTop: "1px solid rgba(148,163,184,0.15)", padding: "0.55rem 0", display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
                <div>
                  <span style={{ color: "#fff", fontWeight: 700, fontSize: "0.85rem" }}>{c.nombre}</span>
                  <span style={{ color: "#94a3b8", fontSize: "0.75rem" }}> · {c.estado_etiqueta}</span>
                </div>
                <span style={{ fontSize: "0.75rem", fontWeight: 700,
                  color: c.docs_completos ? "#4ade80" : "#f59e0b" }}>
                  {c.docs_completos ? "✓ completa" : `faltan ${c.faltantes.length}`} · {c.dias_gestion} día(s)</span>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
