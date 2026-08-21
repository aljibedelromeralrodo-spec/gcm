import { S } from "./theme";

const RES_PILL = {
  asociado: ["rgba(34,197,94,0.15)", "#4ade80", "ASOCIADO A LA BÓVEDA"],
  cuarentena: ["rgba(239,68,68,0.15)", "#f87171", "EN CUARENTENA"],
  sin_cliente: ["rgba(245,158,11,0.15)", "#f59e0b", "SIN CLIENTE IDENTIFICADO"],
  manual: ["rgba(255,255,255,0.1)", "#d4d4d8", "CARGA MANUAL"],
  manual_forzado: ["rgba(239,68,68,0.15)", "#f87171", "CARGA FORZADA CON PIN"],
  descartado: ["rgba(255,255,255,0.08)", "#71717a", "DESCARTADO"],
};
const CHIP_COLOR = { true: ["rgba(34,197,94,0.15)", "#4ade80", "✓"], false: ["rgba(239,68,68,0.15)", "#f87171", "✕"], null: ["rgba(255,255,255,0.07)", "#71717a", "—"] };
const CHIP_LABEL = { rut_titular: "RUT cliente", rut_codeudor: "RUT codeudor", rol_avaluo: "Rol avalúo", direccion_propiedad: "Dirección" };

export const ChipsValidacion = ({ validaciones, testid }) => (
  <div data-testid={testid} style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
    {(validaciones || []).map(v => {
      const [bg, fg, ic] = CHIP_COLOR[String(v.ok)];
      return (
        <span key={v.campo} title={v.ok === false ? `Ficha: «${v.esperado}» ≠ Documento: «${v.detectado}»` : v.ok === null ? "Sin dato para contrastar" : "Coincide exactamente"}
          style={{ background: bg, color: fg, borderRadius: 999, padding: "0.25rem 0.75rem", fontSize: "0.8rem", fontWeight: 700 }}>
          {ic} {CHIP_LABEL[v.campo] || v.etiqueta}</span>
      );
    })}
  </div>
);

export default function MonitorCorreo({ eventos }) {
  return (
    <div data-testid="dash-monitor-correo" style={{ ...S.card, marginTop: 24, padding: "1.8rem 2rem" }}>
      <h2 style={{ ...S.h2, marginBottom: 4 }}>Monitor en tiempo real — llegada y clasificación de documentos</h2>
      <p style={{ ...S.body, fontSize: "0.9rem", color: "#a1a1aa", margin: "0 0 10px" }}>
        Cada documento detectado se clasifica y se contrasta contra la ficha: RUT con RUT, rol con rol, dirección con dirección (Regla de Oro 15, irrenunciable).</p>
      {(eventos || []).length === 0 && <p style={{ ...S.body, color: "#71717a" }}>
        Aún no hay eventos: aparecerán aquí apenas llegue el próximo correo con documentos.</p>}
      {(eventos || []).map(ev => {
        const [bg, fg, txt] = RES_PILL[ev.resultado] || RES_PILL.manual;
        return (
          <div key={ev.id} data-testid={`evento-${ev.id}`} style={{ borderTop: "1px solid rgba(255,255,255,0.08)", padding: "0.9rem 0", display: "flex", justifyContent: "space-between", gap: 14, flexWrap: "wrap", alignItems: "center" }}>
            <div style={{ flex: "1 1 320px" }}>
              <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                <span style={{ fontWeight: 700, color: "#fff", fontSize: "0.97rem", wordBreak: "break-all" }}>{ev.archivo}</span>
                <span style={S.pill(bg, fg)}>{txt}</span>
              </div>
              <div style={{ color: "#a1a1aa", fontSize: "0.85rem", marginTop: 4 }}>
                {String(ev.fecha || "").slice(0, 16).replace("T", " ")} · {ev.tipo_etiqueta}
                {ev.cliente && <> · cliente <b style={{ color: "#FCF6BA" }}>{ev.cliente}</b></>} · vía {ev.origen}</div>
            </div>
            {(ev.validaciones || []).length > 0 && <ChipsValidacion validaciones={ev.validaciones} testid={`evento-chips-${ev.id}`} />}
          </div>
        );
      })}
    </div>
  );
}
