import { useState, useEffect } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

const COLORS = { bg: "#0a0e17", card: "#111827", border: "#1e293b", text: "#e2e8f0", textMuted: "#94a3b8", accent: "#6c5ce7", green: "#00b894", red: "#e17055", orange: "#f39c12" };

const S = {
  page: { padding: "1.5rem", color: COLORS.text, maxWidth: "1200px", margin: "0 auto" },
  card: { background: COLORS.card, borderRadius: "2px", border: `1px solid ${COLORS.border}`, padding: "1.25rem", marginBottom: "1rem" },
  badge: (color) => ({ display: "inline-block", padding: "2px 8px", borderRadius: "2px", fontSize: "0.72rem", fontWeight: 600, background: `${color}20`, color }),
  header: { fontSize: "1.1rem", fontWeight: 700, color: COLORS.accent, marginBottom: "0.75rem" },
  subheader: { fontSize: "0.85rem", fontWeight: 700, color: COLORS.text, marginBottom: "0.5rem" },
  row: { display: "flex", justifyContent: "space-between", padding: "0.3rem 0", borderBottom: `1px solid ${COLORS.border}22`, fontSize: "0.78rem" },
  label: { color: COLORS.textMuted },
  value: { fontWeight: 600, color: COLORS.text },
};

function CriteriaRow({ label, value, unit = "", highlight }) {
  return (
    <div style={S.row}>
      <span style={S.label}>{label}</span>
      <span style={{ ...S.value, color: highlight ? COLORS.green : COLORS.text }}>{value}{unit && ` ${unit}`}</span>
    </div>
  );
}

export default function CriteriosModule() {
  const [criteria, setCriteria] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get(`${API_URL}/api/admin/criterios`).then(r => {
      setCriteria(r.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div style={S.page}>Cargando criterios...</div>;
  if (!criteria) return <div style={S.page}>No hay criterios configurados</div>;

  const btg = criteria.btg_pactual || {};
  const ameris = criteria.ameris || {};
  const general = criteria.parametros_generales || {};

  return (
    <div style={S.page} data-testid="criterios-module">
      <div style={{ marginBottom: "1rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.3rem" }}>
          <i className="fa fa-shield" style={{ fontSize: "1.2rem", color: COLORS.accent }}></i>
          <h2 style={{ fontSize: "1.2rem", fontWeight: 700, color: COLORS.text, margin: 0 }}>Regla de Oro - Criterios de Evaluacion</h2>
        </div>
        <p style={{ fontSize: "0.75rem", color: COLORS.textMuted, margin: 0 }}>
          Version: {criteria.version} | Estos criterios son la fuente de verdad del evaluador crediticio
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
        {/* BTG CON SUBSIDIO */}
        <div style={S.card}>
          <div style={S.header}><i className="fa fa-bank" style={{ marginRight: "0.4rem" }}></i>BTG Pactual - Con Subsidio</div>
          {btg.con_subsidio && <>
            <CriteriaRow label="Monto credito" value={`${btg.con_subsidio.monto_credito_min_uf} - ${btg.con_subsidio.monto_credito_max_uf}`} unit="UF" />
            <CriteriaRow label="LTV maximo" value={`${(btg.con_subsidio.ltv_max * 100).toFixed(0)}%`} />
            <CriteriaRow label="DIV/Renta maximo" value={`${(btg.con_subsidio.div_renta_max * 100).toFixed(0)}%`} />
            <CriteriaRow label="Carga Financiera sin codeudor" value={`${(btg.con_subsidio.carga_financiera_max_sin_codeudor * 100).toFixed(0)}%`} />
            <CriteriaRow label="Carga Financiera con codeudor" value={`${(btg.con_subsidio.carga_financiera_max_con_codeudor * 100).toFixed(0)}%`} />
            <CriteriaRow label="Edad termino maximo" value={btg.con_subsidio.edad_termino_max} unit="anos" />
            <CriteriaRow label="Antiguedad laboral minima" value={btg.con_subsidio.antiguedad_laboral_min_meses} unit="meses" />
            <CriteriaRow label="Morosidad permitida" value={btg.con_subsidio.morosidad_permitida} />
          </>}
        </div>

        {/* BTG SIN SUBSIDIO */}
        <div style={S.card}>
          <div style={S.header}><i className="fa fa-bank" style={{ marginRight: "0.4rem" }}></i>BTG Pactual - Sin Subsidio</div>
          {btg.sin_subsidio && <>
            <CriteriaRow label="Renta minima" value={btg.sin_subsidio.renta_min_uf} unit="UF" />
            <CriteriaRow label="Monto credito" value={`${btg.sin_subsidio.monto_credito_min_uf} - ${btg.sin_subsidio.monto_credito_max_uf}`} unit="UF" />
            <CriteriaRow label="Valor propiedad" value={`${btg.sin_subsidio.valor_propiedad_min_uf} - ${btg.sin_subsidio.valor_propiedad_max_uf}`} unit="UF" />
            <CriteriaRow label="Plazo" value={`${btg.sin_subsidio.plazo_min_anos} - ${btg.sin_subsidio.plazo_max_anos}`} unit="anos" />
            <CriteriaRow label="Edad titular" value={`${btg.sin_subsidio.edad_min} - ${btg.sin_subsidio.edad_max}`} unit="anos" />
            <CriteriaRow label="Edad + Plazo maximo" value={btg.sin_subsidio.edad_plazo_max} />
            <CriteriaRow label="LTV maximo" value={`${(btg.sin_subsidio.ltv_max * 100).toFixed(0)}%`} />
            <CriteriaRow label="DIV/Renta sin codeudor" value={`${(btg.sin_subsidio.div_renta_max_sin_codeudor * 100).toFixed(0)}%`} />
            <CriteriaRow label="DIV/Renta con codeudor (conjunto)" value={`${(btg.sin_subsidio.div_renta_max_con_codeudor_conjunto * 100).toFixed(0)}%`} />
            <CriteriaRow label="DIV/Renta titular con codeudor" value={`${(btg.sin_subsidio.div_renta_max_titular_con_codeudor * 100).toFixed(0)}%`} />
            <CriteriaRow label="Carga financiera maxima" value={`${(btg.sin_subsidio.carga_financiera_max * 100).toFixed(0)}%`} />
            <CriteriaRow label="Antiguedad laboral minima" value={btg.sin_subsidio.antiguedad_laboral_min_meses} unit="meses" />
          </>}
        </div>

        {/* BTG CASTIGOS */}
        <div style={S.card}>
          <div style={{ ...S.header, color: COLORS.orange }}><i className="fa fa-exclamation-triangle" style={{ marginRight: "0.4rem" }}></i>BTG - Castigos de Renta</div>
          {btg.castigos_renta && <>
            <CriteriaRow label="Renta variable (comisiones, bonos)" value={`-${(btg.castigos_renta.renta_variable_castigo * 100).toFixed(0)}%`} highlight />
            <CriteriaRow label="Honorarios independientes" value={`-${(btg.castigos_renta.honorarios_castigo * 100).toFixed(0)}%`} highlight />
            <div style={{ marginTop: "0.5rem" }}>
              <span style={{ fontSize: "0.72rem", color: COLORS.red, fontWeight: 600 }}>No se consideran:</span>
              <div style={{ fontSize: "0.7rem", color: COLORS.textMuted, marginTop: "0.2rem" }}>
                {btg.castigos_renta.no_considera?.join(", ")}
              </div>
            </div>
          </>}
        </div>

        {/* AMERIS CON SUBSIDIO */}
        <div style={S.card}>
          <div style={S.header}><i className="fa fa-institution" style={{ marginRight: "0.4rem" }}></i>AMERIS - Con Subsidio (unico perfil)</div>
          {ameris.con_subsidio && <>
            <CriteriaRow label="Monto credito minimo" value={ameris.con_subsidio.monto_credito_min_uf} unit="UF" />
            <CriteriaRow label="LTV maximo base" value={`${(ameris.con_subsidio.ltv_max_base * 100).toFixed(0)}%`} />
            <CriteriaRow label="Antiguedad laboral minima" value={ameris.con_subsidio.antiguedad_laboral_min_meses} unit="meses" />
            <div style={{ ...S.subheader, marginTop: "0.75rem" }}>Politicas por Edad Final (Edad + Plazo)</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: "0.3rem", marginBottom: "0.5rem" }}>
              <span style={{ fontSize: "0.65rem", color: COLORS.textMuted, fontWeight: 700 }}>Edad Final</span>
              <span style={{ fontSize: "0.65rem", color: COLORS.textMuted, fontWeight: 700 }}>LTV Max</span>
              <span style={{ fontSize: "0.65rem", color: COLORS.textMuted, fontWeight: 700 }}>DIV/Renta</span>
              <span style={{ fontSize: "0.65rem", color: COLORS.textMuted, fontWeight: 700 }}>Carga Fin</span>
            </div>
            {ameris.con_subsidio.politicas_edad_final?.map((p, i) => (
              <div key={i} style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: "0.3rem", padding: "0.2rem 0", borderBottom: `1px solid ${COLORS.border}22`, fontSize: "0.72rem" }}>
                <span style={{ color: COLORS.text, fontWeight: 600 }}>Hasta {p.edad_final_max}</span>
                <span style={{ color: COLORS.green }}>{(p.ltv_max * 100).toFixed(0)}%</span>
                <span style={{ color: COLORS.accent }}>{(p.div_renta_max * 100).toFixed(0)}%</span>
                <span style={{ color: COLORS.orange }}>{(p.carga_fin_max * 100).toFixed(0)}%</span>
              </div>
            ))}
            <div style={{ marginTop: "0.5rem" }}>
              <div style={S.subheader}>DIV/Renta - Sin Codeudor</div>
              <CriteriaRow label="Titular hasta 40 anos" value={`${(ameris.con_subsidio.div_renta_sin_codeudor?.edad_max_40 * 100).toFixed(0)}%`} />
              <CriteriaRow label="Titular mayor 40 anos" value={`${(ameris.con_subsidio.div_renta_sin_codeudor?.edad_mayor_40 * 100).toFixed(0)}%`} />
            </div>
            <div style={{ marginTop: "0.5rem" }}>
              <div style={S.subheader}>DIV/Renta - Con Codeudor Tipo 1/2</div>
              <CriteriaRow label="LTV hasta 75%" value={`${(ameris.con_subsidio.div_renta_con_codeudor_tipo_1_2?.ltv_max_75 * 100).toFixed(0)}%`} />
              <CriteriaRow label="LTV mayor 75%" value={`${(ameris.con_subsidio.div_renta_con_codeudor_tipo_1_2?.ltv_mayor_75 * 100).toFixed(0)}%`} />
            </div>
            <div style={{ marginTop: "0.5rem" }}>
              <div style={S.subheader}>Carga Financiera</div>
              <CriteriaRow label="Sin codeudor" value={`${(ameris.con_subsidio.carga_sin_codeudor_max * 100).toFixed(0)}%`} />
              <CriteriaRow label="Con codeudor Tipo 1/2 (conjunto)" value={`${(ameris.con_subsidio.carga_con_codeudor_tipo_1_2_max * 100).toFixed(0)}%`} />
              <CriteriaRow label="Con codeudor Tipo 3 (conjunto)" value={`${(ameris.con_subsidio.carga_con_codeudor_tipo_3_max_conjunto * 100).toFixed(0)}%`} />
              <CriteriaRow label="Con codeudor Tipo 3 (titular individual)" value={`${(ameris.con_subsidio.carga_con_codeudor_tipo_3_max_titular * 100).toFixed(0)}%`} />
            </div>
          </>}
        </div>
      </div>

      {/* PARAMETROS GENERALES */}
      <div style={S.card}>
        <div style={{ ...S.header, color: COLORS.green }}><i className="fa fa-check-circle" style={{ marginRight: "0.4rem" }}></i>Parametros Generales Compartidos</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
          <div>
            <div style={S.subheader}>Con Subsidio</div>
            {general.con_subsidio && <>
              <CriteriaRow label="Carga financiera maxima" value={`${(general.con_subsidio.carga_fin_max * 100).toFixed(0)}%`} />
              <CriteriaRow label="Antiguedad minima" value={general.con_subsidio.antiguedad_min_meses} unit="meses" />
              <CriteriaRow label="Edad maxima termino" value={general.con_subsidio.edad_max_termino} unit="anos" />
              <CriteriaRow label="LTV maximo" value={`${(general.con_subsidio.ltv_max * 100).toFixed(0)}%`} />
              <CriteriaRow label="Morosidad permitida" value={general.con_subsidio.morosidad} />
            </>}
          </div>
          <div>
            <div style={S.subheader}>Sin Subsidio</div>
            {general.sin_subsidio && <>
              <CriteriaRow label="Carga financiera maxima" value={`${(general.sin_subsidio.carga_fin_max * 100).toFixed(0)}%`} />
              <CriteriaRow label="Antiguedad minima" value={general.sin_subsidio.antiguedad_min_meses} unit="meses" />
              <CriteriaRow label="Edad maxima termino" value={general.sin_subsidio.edad_max_termino} unit="anos" />
              <CriteriaRow label="LTV maximo" value={`${(general.sin_subsidio.ltv_max * 100).toFixed(0)}%`} />
              <CriteriaRow label="Morosidad permitida" value={general.sin_subsidio.morosidad} />
            </>}
          </div>
        </div>
      </div>

      {criteria.updated_at && (
        <div style={{ textAlign: "right", fontSize: "0.7rem", color: COLORS.textMuted }}>
          Ultima actualizacion: {new Date(criteria.updated_at).toLocaleString("es-CL")}
        </div>
      )}
    </div>
  );
}
