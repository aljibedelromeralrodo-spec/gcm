import React from "react";
import { COLORS, formatCLP } from "./constants";
import { StatBox, EvalBadge, CentralScorePanel, ScoreHistory } from "./PredICWidgets";

const API_URL = process.env.REACT_APP_BACKEND_URL;

export function PredICResult({ result, onExportPDF, form }) {
  const viable = result.viable;

  // Determinar escenarios viables
  const esc1Viable = result.eval_escenario_1 === "VIABLE";
  const esc2Viable = result.eval_escenario_2 === "VIABLE";
  const anyViable = esc1Viable || esc2Viable;

  // ================================================================
  // NO VIABLE: Solo mostrar razones, sin opciones financieras
  // ================================================================
  if (!anyViable) {
    return (
      <div data-testid="predic-result" style={{ marginTop: "1.25rem", borderRadius: "18px", overflow: "hidden", border: "2px solid rgba(225,112,85,0.4)", background: "rgba(225,112,85,0.08)" }}>
        {/* Status */}
        <div data-testid="predic-result-status" style={{ padding: "1.5rem", textAlign: "center", background: "linear-gradient(135deg, rgba(225,112,85,0.15), rgba(225,112,85,0.05))" }}>
          <div style={{ fontSize: "3rem", marginBottom: "0.3rem" }}>
            <i className="fa fa-times-circle" style={{ color: COLORS.red }}></i>
          </div>
          <div style={{ fontSize: "1.6rem", fontWeight: 800, color: COLORS.red, letterSpacing: "2px" }}>
            SIN OPCIONES VIABLES
          </div>
          <div style={{ fontSize: "0.85rem", color: COLORS.textMuted, marginTop: "0.5rem" }}>
            No existen escenarios aprobables para estos parametros
          </div>
        </div>

        <div style={{ padding: "1.25rem" }}>
          {/* Razones principales */}
          {result.razones?.length > 0 && (
            <div data-testid="predic-result-reasons" style={{ padding: "1rem", borderRadius: "12px", background: "rgba(225,112,85,0.1)", border: "1px solid rgba(225,112,85,0.2)", marginBottom: "1rem" }}>
              <div style={{ fontSize: "0.85rem", fontWeight: 700, color: COLORS.red, marginBottom: "0.5rem" }}>
                <i className="fa fa-exclamation-triangle" style={{ marginRight: "0.3rem" }}></i> Por que no es viable
              </div>
              {result.razones.map((r, i) => (
                <div key={i} style={{ fontSize: "0.82rem", color: COLORS.text, paddingLeft: "0.75rem", marginTop: "0.35rem", borderLeft: `3px solid ${COLORS.red}` }}>
                  {r}
                </div>
              ))}
            </div>
          )}

          {/* Sugerencias de optimizacion */}
          {result.sugerencias_optimizacion?.length > 0 && (
            <div data-testid="predic-result-sugerencias" style={{ padding: "1rem", borderRadius: "12px", background: "rgba(108,92,231,0.08)", border: "1px solid rgba(108,92,231,0.2)", marginBottom: "1rem" }}>
              <div style={{ fontSize: "0.85rem", fontWeight: 700, color: COLORS.accent, marginBottom: "0.5rem" }}>
                <i className="fa fa-lightbulb-o" style={{ marginRight: "0.3rem" }}></i> Que se puede ajustar
              </div>
              {result.sugerencias_optimizacion.map((s, i) => (
                <div key={i} style={{ fontSize: "0.8rem", color: COLORS.text, paddingLeft: "0.75rem", marginTop: "0.3rem", borderLeft: `3px solid ${COLORS.accentLight}` }}>{s}</div>
              ))}
            </div>
          )}

          {/* Central Score */}
          {result.central_score && <CentralScorePanel score={result.central_score} />}
        </div>
      </div>
    );
  }

  // ================================================================
  // VIABLE: Mostrar solo las opciones aprobables
  // ================================================================
  const bg = "rgba(0,184,148,0.08)";
  const borderColor = "rgba(0,184,148,0.4)";

  return (
    <div data-testid="predic-result" style={{ marginTop: "1.25rem", borderRadius: "18px", overflow: "hidden", border: `2px solid ${borderColor}`, background: bg }}>
      {/* Status banner */}
      <div data-testid="predic-result-status" style={{ padding: "1.25rem", textAlign: "center", background: "linear-gradient(135deg, rgba(0,184,148,0.15), rgba(0,184,148,0.05))" }}>
        <div style={{ fontSize: "3rem", marginBottom: "0.3rem" }}>
          <i className="fa fa-check-circle" style={{ color: COLORS.green }}></i>
        </div>
        <div style={{ fontSize: "1.6rem", fontWeight: 800, color: COLORS.green, letterSpacing: "2px" }}>
          VIABLE
        </div>
      </div>

      {/* Details */}
      <div style={{ padding: "1.25rem" }}>
        {/* Valor Propiedad Solicitada */}
        {result.valor_propiedad_uf > 0 && (
          <div data-testid="predic-result-propiedad" style={{ textAlign: "center", marginBottom: "0.75rem", padding: "0.7rem", borderRadius: "12px", background: "rgba(212,175,55,0.08)", border: `2px solid ${COLORS.gold}` }}>
            <div style={{ fontSize: "0.78rem", color: COLORS.textMuted }}>Valor Propiedad Solicitada</div>
            <div style={{ fontSize: "1.5rem", fontWeight: 800, color: COLORS.gold }}>{result.valor_propiedad_uf} UF</div>
            <div style={{ fontSize: "0.85rem", color: COLORS.textMuted }}>{formatCLP(result.valor_propiedad_clp || (result.valor_propiedad_uf * (result.valor_uf_usado || 39000)))}</div>
          </div>
        )}

        {/* Credito solicitado */}
        {result.credito_solicitado_uf > 0 && (
          <div style={{ textAlign: "center", marginBottom: "0.75rem", padding: "0.7rem", borderRadius: "12px", background: "rgba(108,92,231,0.06)", border: `1px solid ${COLORS.border}` }}>
            <div style={{ fontSize: "0.78rem", color: COLORS.textMuted }}>Credito Solicitado</div>
            <div style={{ fontSize: "1.3rem", fontWeight: 700, color: COLORS.accentLight }}>{result.credito_solicitado_uf} UF</div>
            <div style={{ fontSize: "0.85rem", color: COLORS.textMuted }}>{formatCLP(result.credito_solicitado_clp)}</div>
          </div>
        )}

        {/* Monto credito aprobable */}
        <div data-testid="predic-result-max" style={{ textAlign: "center", marginBottom: "1rem", padding: "1rem", borderRadius: "12px", background: "rgba(108,92,231,0.1)", border: `1px solid ${COLORS.border}` }}>
          <div style={{ fontSize: "0.8rem", color: COLORS.textMuted }}>Monto Credito Probable</div>
          <div style={{ fontSize: "2rem", fontWeight: 800, color: COLORS.gold }}>{result.monto_aprobado_uf} UF</div>
          <div style={{ fontSize: "1.1rem", color: COLORS.accentLight, fontWeight: 600 }}>{formatCLP(result.monto_aprobado_clp)}</div>
        </div>

        {/* Dividendo: Opcion 1 + Opcion 2 */}
        <div style={{ display: "grid", gridTemplateColumns: result.dividendo_alternativo_clp > 0 ? "1fr 1fr" : "1fr", gap: "0.5rem", marginBottom: "1rem" }}>
          <div data-testid="predic-result-dividendo-principal" style={{ textAlign: "center", padding: "0.8rem", borderRadius: "12px", background: "rgba(108,92,231,0.08)", border: `2px solid ${COLORS.accent}` }}>
            <div style={{ fontSize: "0.65rem", color: COLORS.accent, fontWeight: 700, textTransform: "uppercase", letterSpacing: "1px" }}>Opcion 1 - {result.plazo_anos} anos</div>
            <div style={{ fontSize: "1.4rem", fontWeight: 700, color: COLORS.text }}>{result.dividendo_estimado_uf} UF</div>
            <div style={{ fontSize: "0.95rem", color: COLORS.gold, fontWeight: 600 }}>{formatCLP(result.dividendo_estimado_clp)}</div>
            <div style={{ fontSize: "0.65rem", color: COLORS.green, marginTop: "0.2rem" }}>Dividendo mensual</div>
          </div>
          {result.dividendo_alternativo_clp > 0 && (
            <div data-testid="predic-result-dividendo-alternativo" style={{ textAlign: "center", padding: "0.8rem", borderRadius: "12px", background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
              <div style={{ fontSize: "0.65rem", color: COLORS.textMuted, fontWeight: 700, textTransform: "uppercase", letterSpacing: "1px" }}>Opcion 2 - {result.plazo_alternativo} anos</div>
              <div style={{ fontSize: "1.4rem", fontWeight: 700, color: COLORS.text }}>{result.dividendo_alternativo_uf} UF</div>
              <div style={{ fontSize: "0.95rem", color: COLORS.gold, fontWeight: 600 }}>{formatCLP(result.dividendo_alternativo_clp)}</div>
              <div style={{ fontSize: "0.65rem", color: COLORS.orange, marginTop: "0.2rem" }}>Dividendo mensual</div>
            </div>
          )}
        </div>

        {/* Seguros y Dividendo Final */}
        {result.seguros && (
          <div data-testid="predic-seguros-section" style={{ marginBottom: "1rem" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem", marginBottom: "0.4rem" }}>
              <div data-testid="seguro-desgravamen-box" style={{ textAlign: "center", padding: "0.6rem", borderRadius: "10px", background: "rgba(108,92,231,0.06)", border: `1px solid ${COLORS.border}` }}>
                <div style={{ fontSize: "0.6rem", color: COLORS.textMuted, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.5px" }}>Seguro Desgravamen</div>
                <div style={{ fontSize: "1.1rem", fontWeight: 700, color: COLORS.text }}>{formatCLP(result.seguros.seguro_desgravamen)}</div>
                {result.seguros.tiene_codeudor && <div style={{ fontSize: "0.6rem", color: COLORS.orange, fontWeight: 600 }}>x2 por codeudor (base: {formatCLP(result.seguros.seguro_desgravamen_base)})</div>}
              </div>
              <div data-testid="seguro-incendio-box" style={{ textAlign: "center", padding: "0.6rem", borderRadius: "10px", background: "rgba(108,92,231,0.06)", border: `1px solid ${COLORS.border}` }}>
                <div style={{ fontSize: "0.6rem", color: COLORS.textMuted, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.5px" }}>Seguro de Incendio</div>
                <div style={{ fontSize: "1.1rem", fontWeight: 700, color: COLORS.text }}>{formatCLP(result.seguros.seguro_incendio)}</div>
              </div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: result.seguros.dividendo_final_alt > 0 ? "1fr 1fr" : "1fr", gap: "0.5rem" }}>
              <div data-testid="total-dividendo-final-box" style={{ textAlign: "center", padding: "0.7rem", borderRadius: "12px", background: "linear-gradient(135deg, rgba(108,92,231,0.15), rgba(162,155,254,0.1))", border: `2px solid ${COLORS.accent}` }}>
                <div style={{ fontSize: "0.6rem", color: COLORS.accent, fontWeight: 700, textTransform: "uppercase", letterSpacing: "1px" }}>Dividendo Final - {result.plazo_anos} anos</div>
                <div style={{ fontSize: "1.6rem", fontWeight: 800, color: COLORS.gold }}>{formatCLP(result.seguros.dividendo_final)}</div>
                <div style={{ fontSize: "0.6rem", color: COLORS.textMuted }}>{formatCLP(result.dividendo_estimado_clp)} + {formatCLP(result.seguros.total_seguros)} seguros</div>
              </div>
              {result.seguros.dividendo_final_alt > 0 && (
                <div data-testid="total-dividendo-final-alt-box" style={{ textAlign: "center", padding: "0.7rem", borderRadius: "12px", background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
                  <div style={{ fontSize: "0.6rem", color: COLORS.textMuted, fontWeight: 700, textTransform: "uppercase", letterSpacing: "1px" }}>Dividendo Final - {result.plazo_alternativo} anos</div>
                  <div style={{ fontSize: "1.6rem", fontWeight: 800, color: COLORS.gold }}>{formatCLP(result.seguros.dividendo_final_alt)}</div>
                  <div style={{ fontSize: "0.6rem", color: COLORS.textMuted }}>{formatCLP(result.dividendo_alternativo_clp)} + {formatCLP(result.seguros.total_seguros)} seguros</div>
                </div>
              )}
            </div>
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem", marginBottom: "0.75rem" }}>
          <StatBox label="Capacidad Max." value={`${result.capacidad_credito_uf} UF`} />
          <StatBox label="Carga Financiera" value={`${result.carga_financiera_pct}%`} warn={result.carga_financiera_pct > 40} />
          <StatBox label="Div/Renta" value={`${result.div_renta_pct}%`} warn={result.div_renta_pct > 35} />
          <StatBox label="LTV" value={`${result.ltv_pct}%`} warn={result.ltv_pct > 80} />
        </div>

        {/* Solo mostrar escenarios VIABLES */}
        <div style={{ display: "grid", gridTemplateColumns: esc1Viable && esc2Viable ? "1fr 1fr" : "1fr", gap: "0.5rem", marginBottom: "0.75rem" }}>
          {esc1Viable && <EvalBadge label="Escenario 1" result={result.eval_escenario_1} razones={result.eval_escenario_1_razones} />}
          {esc2Viable && <EvalBadge label="Escenario 2" result={result.eval_escenario_2} razones={result.eval_escenario_2_razones} />}
        </div>

        {result.tipo_deudor && (
          <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem", flexWrap: "wrap" }}>
            <span style={{ padding: "3px 8px", borderRadius: "6px", fontSize: "0.72rem", background: "rgba(108,92,231,0.12)", color: COLORS.accentLight }}>{result.tipo_deudor}</span>
            {result.edad_plazo > 0 && <span style={{ padding: "3px 8px", borderRadius: "6px", fontSize: "0.72rem", background: (result.edad_final_referencia || result.edad_plazo) > 80 ? "rgba(225,112,85,0.15)" : "rgba(0,184,148,0.12)", color: (result.edad_final_referencia || result.edad_plazo) > 80 ? COLORS.red : COLORS.green }}>Edad+Plazo: {result.edad_final_referencia || result.edad_plazo}{result.edad_plazo_codeudor > 0 ? ` (Titular: ${result.edad_plazo}, Codeudor: ${result.edad_plazo_codeudor})` : ""}</span>}
            {result.plazo_anos > 0 && <span data-testid="predic-result-plazo" style={{ padding: "3px 8px", borderRadius: "6px", fontSize: "0.72rem", background: result.plazo_en_rango_preferido ? "rgba(0,184,148,0.12)" : "rgba(243,156,18,0.12)", color: result.plazo_en_rango_preferido ? COLORS.green : COLORS.orange }}>
              Plazo: {result.plazo_anos} anos {result.plazo_en_rango_preferido ? "(optimo)" : `(max ${result.plazo_maximo})`}
            </span>}
            {result.plazo_recomendado > 0 && result.plazo_anos !== result.plazo_recomendado && (
              <span style={{ padding: "3px 8px", borderRadius: "6px", fontSize: "0.72rem", background: "rgba(108,92,231,0.12)", color: COLORS.accentLight }}>
                Recomendado: {result.plazo_recomendado} anos
              </span>
            )}
            {result.tasa_aplicada > 0 && <span style={{ padding: "3px 8px", borderRadius: "6px", fontSize: "0.72rem", background: "rgba(212,175,55,0.12)", color: COLORS.gold }}>Tasa: {result.tasa_aplicada}%</span>}
          </div>
        )}

        {/* Mesa Learning Insight */}
        {result.mesa_learning && result.mesa_learning.source === "mesa_learning" && (
          <div data-testid="predic-mesa-insight" style={{ padding: "0.75rem", borderRadius: "10px", background: "rgba(108,92,231,0.08)", border: `1px solid ${COLORS.border}`, marginBottom: "0.75rem" }}>
            <div style={{ fontSize: "0.78rem", fontWeight: 700, color: COLORS.accentLight, marginBottom: "0.3rem" }}>
              <i className="fa fa-graduation-cap" style={{ marginRight: "0.3rem" }}></i> Aprendizaje IA (Mesa)
            </div>
            <div style={{ fontSize: "0.72rem", color: COLORS.textMuted }}>{result.mesa_learning.detail}</div>
            <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.4rem", flexWrap: "wrap" }}>
              <span style={{ padding: "2px 6px", borderRadius: "4px", fontSize: "0.68rem", background: "rgba(0,184,148,0.12)", color: COLORS.green }}>
                Plazo promedio aprobado: {result.mesa_learning.plazo_promedio_aprobado} anos
              </span>
              <span style={{ padding: "2px 6px", borderRadius: "4px", fontSize: "0.68rem", background: "rgba(108,92,231,0.12)", color: COLORS.accentLight }}>
                {result.mesa_learning.casos_aprobados} aprobados / {result.mesa_learning.casos_rechazados} rechazados
              </span>
            </div>
          </div>
        )}

        {/* Castigos de renta */}
        {(result.castigo_renta_variable > 0 || result.castigo_renta_honorarios > 0) && (
          <div data-testid="predic-result-castigos" style={{ padding: "0.75rem", borderRadius: "10px", background: "rgba(243,156,18,0.08)", border: "1px solid rgba(243,156,18,0.2)", marginBottom: "0.75rem" }}>
            <div style={{ fontSize: "0.78rem", fontWeight: 700, color: COLORS.orange, marginBottom: "0.3rem" }}>
              <i className="fa fa-info-circle" style={{ marginRight: "0.3rem" }}></i>Castigos de Renta Aplicados
            </div>
            <div style={{ fontSize: "0.72rem", color: COLORS.textMuted }}>
              {result.castigo_renta_variable > 0 && <div>Renta variable: -{formatCLP(result.castigo_renta_variable)} (-15%)</div>}
              {result.castigo_renta_honorarios > 0 && <div>Honorarios: -{formatCLP(result.castigo_renta_honorarios)} (-20%)</div>}
              <div style={{ marginTop: "0.2rem", fontWeight: 600, color: COLORS.text }}>Renta efectiva: {formatCLP(result.renta_efectiva)}</div>
            </div>
          </div>
        )}

        {/* Export PDF button */}
        <button data-testid="predic-export-pdf" onClick={onExportPDF}
          style={{ marginTop: "1rem", width: "100%", padding: "0.75rem", borderRadius: "12px", border: `1px solid ${COLORS.gold}`, background: `linear-gradient(135deg, rgba(212,175,55,0.15), rgba(212,175,55,0.05))`, color: COLORS.gold, fontWeight: 700, fontSize: "0.9rem", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: "0.5rem" }}>
          <i className="fa fa-file-pdf-o"></i> Exportar Informe PDF
        </button>

        {/* Central Mutuos Score */}
        {result.central_score && <CentralScorePanel score={result.central_score} />}

        {/* Score History */}
        <ScoreHistory clientName={form?.nombre_cliente} apiUrl={API_URL} />
      </div>
    </div>
  );
}
