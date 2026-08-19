import { useEffect, useState } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const ORO = "#d4af37";
const card = { background: "rgba(15,23,42,0.72)", border: "1px solid rgba(212,175,55,0.25)",
  borderRadius: 14, padding: "1rem 1.2rem", flex: "1 1 280px", minWidth: 260 };
const tit = { color: "#94a3b8", fontSize: "0.6rem", fontWeight: 900, letterSpacing: 1.6, textTransform: "uppercase" };
const KPI = ({ v, label, color = "#f8fafc" }) => (
  <div style={{ minWidth: 90 }}>
    <div style={{ color, fontSize: "1.7rem", fontWeight: 900, lineHeight: 1.1 }}>{v}</div>
    <div style={{ color: "#94a3b8", fontSize: "0.6rem", fontWeight: 700 }}>{label}</div>
  </div>
);
const fdd = (iso) => iso ? `${String(iso).slice(8, 10)}/${String(iso).slice(5, 7)}/${String(iso).slice(0, 4)}` : "—";

export default function FrentePrincipal({ rol }) {
  const [d, setD] = useState(null);
  const [idx, setIdx] = useState(null);
  const esAdmin = ["admin", "maestro"].includes(rol);
  useEffect(() => {
    axios.get(`${API}/api/gerencia-comercial/dashboard-principal`).then(r => setD(r.data)).catch(() => {});
    if (esAdmin) axios.get(`${API}/api/gerencia-comercial/indices-admin`).then(r => setIdx(r.data)).catch(() => {});
  }, [esAdmin]);
  if (!d) return null;
  const rt = d.financiero.ratio_mes;
  return (
    <div data-testid="frente-principal" style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 16 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
        <h2 style={{ color: ORO, fontSize: "0.95rem", fontWeight: 900, letterSpacing: 2, margin: 0 }}>
          ⬛ FRENTE PRINCIPAL — INFORMACIÓN EN VIVO</h2>
        <span style={{ color: "#475569", fontSize: "0.6rem" }}>período {d.mes}</span>
      </div>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <div style={card} data-testid="fp-operaciones">
          <div style={tit}>Operaciones</div>
          <div style={{ display: "flex", gap: 16, marginTop: 6, flexWrap: "wrap" }}>
            <KPI v={d.operaciones.activas} label="ACTIVAS" />
            <KPI v={`${d.operaciones.cerradas_mes}/${d.operaciones.meta_mes || "—"}`} label="CERRADAS VS META" color="#22c55e" />
            <KPI v={d.operaciones.atrasadas} label="ATRASADAS" color={d.operaciones.atrasadas ? "#ef4444" : "#22c55e"} />
            <KPI v={d.operaciones.sin_movimiento_5d} label="SIN MOV. +5D" color={d.operaciones.sin_movimiento_5d ? "#facc15" : "#22c55e"} />
            <KPI v={d.operaciones.con_docs_faltantes} label="DOCS FALTANTES" color={d.operaciones.con_docs_faltantes ? "#facc15" : "#22c55e"} />
          </div>
        </div>
        <div style={card} data-testid="fp-financiero">
          <div style={tit}>Financiero</div>
          <div style={{ display: "flex", gap: 16, marginTop: 6, flexWrap: "wrap" }}>
            <KPI v={d.financiero.cartera_activa} label="CARTERA ACTIVA" color={ORO} />
            <KPI v={d.financiero.cerradas_mes} label="CERRADAS MES" color="#22c55e" />
            <KPI v={rt === null ? "—" : `${rt}%`} label="CUMPLIMIENTO PROY."
              color={rt === null ? "#64748b" : rt >= 100 ? "#22c55e" : rt >= 60 ? "#facc15" : "#ef4444"} />
          </div>
        </div>
        <div style={card} data-testid="fp-espejo">
          <div style={tit}>Concreces · Algoritmo Espejo</div>
          <div style={{ display: "flex", gap: 16, marginTop: 6, flexWrap: "wrap" }}>
            <KPI v={d.espejo.ultima_sync ? fdd(d.espejo.ultima_sync) : "—"} label="ÚLTIMA SYNC" color="#93c5fd" />
            <KPI v={d.espejo.pendientes} label="RESPUESTA PENDIENTE" color={d.espejo.pendientes ? "#facc15" : "#22c55e"} />
            <KPI v={d.espejo.alertas_ia_24h} label="ALERTAS IA 24H" color={d.espejo.alertas_ia_24h ? "#ef4444" : "#22c55e"} />
          </div>
        </div>
        <div style={card} data-testid="fp-documentos">
          <div style={tit}>Documentos</div>
          <div style={{ display: "flex", gap: 16, marginTop: 6 }}>
            <KPI v={d.documentos.carpetas_incompletas} label="CARPETAS INCOMPLETAS" color={d.documentos.carpetas_incompletas ? "#facc15" : "#22c55e"} />
            <KPI v={d.documentos.sin_clasificar} label="SIN CLASIFICAR" color={d.documentos.sin_clasificar ? "#facc15" : "#22c55e"} />
          </div>
        </div>
      </div>
      {d.postventa.casos.length > 0 && (
        <div style={{ ...card, flex: "1 1 100%" }} data-testid="fp-postventa">
          <div style={tit}>Postventa — Escrituras en curso ({d.postventa.vencidos_total} pasos vencidos)</div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 6 }}>
            {d.postventa.casos.map(c => (
              <span key={c.id} style={{ fontSize: "0.68rem", fontWeight: 800, borderRadius: 999, padding: "3px 11px",
                color: c.vencidos ? "#ef4444" : "#e2e8f0", border: `1px solid ${c.vencidos ? "#ef444466" : "rgba(212,175,55,0.3)"}` }}>
                {c.cliente} → {c.paso_actual}{c.vencidos ? ` · 🚨${c.vencidos}` : ""}</span>
            ))}
          </div>
        </div>
      )}
      {esAdmin && idx && (
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }} data-testid="fp-algoritmo-hibrido">
          <div style={{ ...card, borderColor: "rgba(212,175,55,0.5)" }} data-testid="fp-indice-administrativo">
            <div style={{ ...tit, color: ORO }}>🔱 Algoritmo Híbrido — Índice Administrativo (solo Admin)</div>
            <div style={{ display: "flex", gap: 16, marginTop: 6, flexWrap: "wrap" }}>
              <KPI v={idx.administrativo.normativas_vigentes} label="NORMATIVAS VIGENTES" color={ORO} />
              <KPI v={idx.administrativo.brechas_abiertas} label="BRECHAS ABIERTAS" color={idx.administrativo.brechas_abiertas ? "#facc15" : "#22c55e"} />
              <KPI v={idx.administrativo.exportacion_pendiente ? "SÍ" : "NO"} label="EXPORT PENDIENTE"
                color={idx.administrativo.exportacion_pendiente ? "#facc15" : "#22c55e"} />
              <KPI v={idx.administrativo.trackers_administrativos} label="TRACKERS ADMIN." />
            </div>
            <div style={{ marginTop: 6 }}>
              {idx.administrativo.auditorias_recientes.map(a => (
                <div key={a.semana} style={{ color: "#94a3b8", fontSize: "0.64rem" }}>
                  {a.resultado === "aprobada" ? "✅" : "⚠️"} Auditoría {a.semana} · {fdd(a.fecha)} · {a.fallas} hallazgos</div>
              ))}
            </div>
          </div>
          <div style={{ ...card, borderColor: "rgba(212,175,55,0.5)" }} data-testid="fp-indice-formaciones">
            <div style={{ ...tit, color: ORO }}>🎓 Índice de Formaciones (solo Admin)</div>
            <div style={{ display: "flex", gap: 16, marginTop: 6 }}>
              <KPI v={idx.formaciones.activos} label="ACTIVOS OPERANDO" color="#22c55e" />
              <KPI v={idx.formaciones.pendientes_activacion.length} label="PEND. ACTIVACIÓN"
                color={idx.formaciones.pendientes_activacion.length ? "#facc15" : "#22c55e"} />
            </div>
            {idx.formaciones.pendientes_activacion.slice(0, 6).map((u, i) => (
              <div key={i} style={{ color: "#94a3b8", fontSize: "0.64rem" }}>
                ⏳ {u.nombre} ({u.rol}) — pendiente: {u.pendiente}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
