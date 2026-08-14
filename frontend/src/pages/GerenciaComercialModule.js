import { useState, useEffect } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const HITO = {
  ok: { c: "#22c55e", i: "fa-check-circle", t: "Éxito" },
  proceso: { c: "#f59e0b", i: "fa-clock-o", t: "Proceso" },
  pendiente: { c: "#f59e0b", i: "fa-hourglass-half", t: "Pendiente" },
  bloqueo: { c: "#ef4444", i: "fa-ban", t: "Bloqueo" },
  alerta: { c: "#ef4444", i: "fa-exclamation-triangle", t: "ALERTA" },
};
const Icono = ({ estado }) => {
  const h = HITO[estado] || HITO.pendiente;
  return <i className={`fa ${h.i}`} title={h.t} style={{ color: h.c, fontSize: "1rem" }} />;
};

export default function GerenciaComercialModule() {
  const [data, setData] = useState(null);

  useEffect(() => {
    axios.get(`${API}/api/gerencia/cartera`).then(r => setData(r.data)).catch(() => setData({ cartera: [] }));
  }, []);

  const exportar = async () => {
    const r = await axios.get(`${API}/api/gerencia/export-xlsx`, { responseType: "blob" });
    const url = URL.createObjectURL(r.data);
    const a = document.createElement("a");
    a.href = url; a.download = `Reporte_Gerencia_${data?.mes || ""}.xlsx`; a.click();
    URL.revokeObjectURL(url);
  };

  const glass = { background: "rgba(30,41,59,0.55)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)",
    border: "1px solid rgba(148,163,184,0.18)", borderRadius: 14 };

  return (
    <div className="module-content" data-testid="gerencia-module" style={{ background: "#0f172a", minHeight: "100%", padding: "1.2rem", borderRadius: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap", marginBottom: 16 }}>
        <h3 style={{ margin: 0, color: "#f8fafc", fontSize: "1.05rem" }}>
          <i className="fa fa-line-chart" style={{ color: "#d4af37", marginRight: 8 }} />Gerencia Comercial — Torre de Control VIP
        </h3>
        <span style={{ color: "#94a3b8", fontSize: "0.72rem" }}>Mes {data?.mes || "…"} · {data?.total ?? 0} operaciones · Auditoría DashAI: {(data?.ultima_auditoria_dashai || "").slice(0, 16) || "pendiente"}</span>
        <button data-testid="btn-export-gerencia" onClick={exportar}
          style={{ marginLeft: "auto", background: "linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C)", color: "#0a0a0a", border: "none", borderRadius: 8, padding: "0.45rem 1rem", fontWeight: 800, cursor: "pointer", fontSize: "0.75rem" }}>
          <i className="fa fa-file-excel-o" /> Exportar Reporte Mensual
        </button>
      </div>
      {(data?.alertas_notaria || 0) > 0 && (
        <div data-testid="gerencia-alerta-notaria" style={{ ...glass, borderColor: "#ef4444", color: "#fecaca", padding: "0.6rem 1rem", marginBottom: 12, fontSize: "0.78rem", fontWeight: 700 }}>
          🚨 {data.alertas_notaria} aviso(s) de notaría sobre firmas faltantes detectados por DashAI
        </div>
      )}
      {(data?.excepciones_recientes || []).length > 0 && (
        <div data-testid="gerencia-excepciones" style={{ ...glass, borderColor: "#f59e0b", color: "#fde68a", padding: "0.6rem 1rem", marginBottom: 12, fontSize: "0.72rem" }}>
          ⚠️ Excepciones autorizadas recientes: {data.excepciones_recientes.map(e => `${e.usuario} (${e.cliente || e.hito})`).join(" · ")}
        </div>
      )}
      <div style={{ ...glass, overflowX: "auto" }}>
        <table data-testid="gerencia-tabla" style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.78rem", color: "#e2e8f0" }}>
          <thead>
            <tr style={{ color: "#94a3b8", fontSize: "0.66rem", textTransform: "uppercase", letterSpacing: "0.08em" }}>
              {["Cliente", "RUT", "Monto UF", "Subsidio", "Inmobiliaria", "Docs", "Firma Set", "Concreces", "Notaría", "Mesa"].map(h =>
                <th key={h} style={{ padding: "0.7rem 0.8rem", textAlign: "left", borderBottom: "1px solid rgba(148,163,184,0.15)" }}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {(data?.cartera || []).map(f => (
              <tr key={f.folder_id} data-testid={`gerencia-fila-${f.folder_id}`} style={{ borderBottom: "1px solid rgba(148,163,184,0.08)" }}>
                <td style={{ padding: "0.6rem 0.8rem", fontWeight: 700, color: "#f8fafc" }}>{f.cliente}
                  {f.alerta_notaria && <div style={{ color: "#fb7185", fontSize: "0.62rem", fontWeight: 600 }}>{f.alerta_notaria}</div>}
                </td>
                <td style={{ padding: "0.6rem 0.8rem", fontFamily: "monospace" }}>{f.rut || "—"}</td>
                <td style={{ padding: "0.6rem 0.8rem" }}>{f.monto_credito_uf ? Number(f.monto_credito_uf).toLocaleString("es-CL") : "—"}</td>
                <td style={{ padding: "0.6rem 0.8rem" }}>{f.subsidio ? "Sí" : "No"}</td>
                <td style={{ padding: "0.6rem 0.8rem" }}>{f.inmobiliaria || "—"}</td>
                <td style={{ padding: "0.6rem 0.8rem", textAlign: "center" }}><Icono estado={f.documentacion} /></td>
                <td style={{ padding: "0.6rem 0.8rem", textAlign: "center" }}><Icono estado={f.firma_set} /></td>
                <td style={{ padding: "0.6rem 0.8rem", textAlign: "center" }}><Icono estado={f.ingreso_concreces} /></td>
                <td style={{ padding: "0.6rem 0.8rem", textAlign: "center" }}><Icono estado={f.notaria} /></td>
                <td style={{ padding: "0.6rem 0.8rem", fontSize: "0.68rem", color: "#94a3b8" }}>{f.estado_mesa || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!data && <p style={{ color: "#94a3b8", textAlign: "center", padding: "2rem" }}>Cargando cartera…</p>}
      </div>
      <p data-testid="costo-desarrollo" style={{ color: "#64748b", fontSize: "0.68rem", marginTop: 12 }}>
        ⚡ Costo de Desarrollo del mes: <b style={{ color: "#d4af37" }}>{data?.costo_desarrollo_creditos ?? 0} créditos</b> (estimado por consumo real de IA — Ley de Eficiencia #23)
      </p>
    </div>
  );
}
