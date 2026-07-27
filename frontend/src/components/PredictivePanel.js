import { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";

const API_URL = process.env.REACT_APP_BACKEND_URL;

function PredictivePanel({ formData, valorUF }) {
  const [prediction, setPrediction] = useState(null);
  const [insights, setInsights] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showInsights, setShowInsights] = useState(false);
  const debounceRef = useRef(null);

  // Load insights once
  useEffect(() => {
    axios.get(`${API_URL}/api/ia/insights`).then(r => {
      setInsights(r.data);
    }).catch(() => {});
  }, []);

  const fetchPrediction = useCallback(async (data) => {
    const renta = parseFloat(data.renta_titular) || 0;
    const plazo = parseInt(data.plazo_anos) || 0;
    const edad = parseInt(data.edad_cliente) || 0;
    if (!renta || !plazo || !edad) {
      setPrediction(null);
      return;
    }
    setLoading(true);
    try {
      const payload = {
        renta_titular: renta,
        renta_codeudor: parseFloat(data.renta_codeudor) || 0,
        plazo_anos: plazo,
        tasa_anual: (parseFloat(data.tasa_anual) || 6.35) / 100,
        credito_solicitado_uf: parseFloat(data.credito_solicitado_uf) || 0,
        valor_propiedad_uf: parseFloat(data.valor_propiedad_uf) || 0,
        edad_cliente: edad,
        carga_financiera: parseFloat(data.carga_financiera) || 0,
        subsidio_uf: parseFloat(data.subsidio_uf) || 0,
        ahorro_uf: parseFloat(data.ahorro_uf) || 0,
        valor_uf: valorUF,
        protestos_vigentes: data.protestos_vigentes || false,
        morosidad_dicom: data.morosidad_dicom || false,
        continuidad_laboral: data.continuidad_laboral !== false,
      };
      const res = await axios.post(`${API_URL}/api/ia/predict`, payload);
      setPrediction(res.data);
    } catch {
      setPrediction(null);
    }
    setLoading(false);
  }, [valorUF]);

  // Debounced prediction on form change
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchPrediction(formData), 600);
    return () => clearTimeout(debounceRef.current);
  }, [formData, fetchPrediction]);

  const getScoreColor = (score) => {
    if (score >= 80) return "#10b981";
    if (score >= 60) return "#22d3ee";
    if (score >= 40) return "#f59e0b";
    if (score >= 20) return "#f97316";
    return "#ef4444";
  };

  const getSeverityColor = (sev) => {
    if (sev === "alta") return "#ef4444";
    if (sev === "media") return "#f59e0b";
    return "#22d3ee";
  };

  const hasMinData = (parseFloat(formData.renta_titular) || 0) > 0 &&
    (parseInt(formData.plazo_anos) || 0) > 0 &&
    (parseInt(formData.edad_cliente) || 0) > 0;

  if (!hasMinData) {
    return (
      <div className="pred-panel" data-testid="predictive-panel-empty">
        <div className="pred-header">
          <i className="fa fa-line-chart pred-icon"></i>
          <span>IA Predictiva</span>
        </div>
        <div className="pred-waiting">
          <p>Ingrese renta, plazo y edad para ver la prediccion en tiempo real</p>
        </div>
      </div>
    );
  }

  return (
    <div className="pred-panel" data-testid="predictive-panel">
      <div className="pred-header">
        <i className="fa fa-line-chart pred-icon"></i>
        <span>IA Predictiva</span>
        {loading && <i className="fa fa-spinner fa-spin pred-loading-icon"></i>}
      </div>

      {prediction && (
        <>
          {/* Score Gauge */}
          <div className="pred-gauge-section" data-testid="pred-score-section">
            <div className="pred-gauge" style={{ "--score-color": getScoreColor(prediction.probabilidad) }}>
              <svg viewBox="0 0 120 70" className="pred-gauge-svg">
                <path d="M 10 65 A 50 50 0 0 1 110 65" fill="none" stroke="#1f2937" strokeWidth="10" strokeLinecap="round" />
                <path
                  d="M 10 65 A 50 50 0 0 1 110 65"
                  fill="none"
                  stroke={getScoreColor(prediction.probabilidad)}
                  strokeWidth="10"
                  strokeLinecap="round"
                  strokeDasharray={`${(prediction.probabilidad / 100) * 157} 157`}
                  style={{ filter: `drop-shadow(0 0 6px ${getScoreColor(prediction.probabilidad)})` }}
                />
              </svg>
              <div className="pred-gauge-value" style={{ color: getScoreColor(prediction.probabilidad) }} data-testid="pred-score-value">
                {Math.round(prediction.probabilidad)}%
              </div>
            </div>
            <div className="pred-nivel" data-testid="pred-nivel">
              <span className="pred-nivel-badge" style={{ background: getScoreColor(prediction.probabilidad) + "22", color: getScoreColor(prediction.probabilidad), borderColor: getScoreColor(prediction.probabilidad) }}>
                {prediction.nivel}
              </span>
            </div>
            <p className="pred-mensaje">{prediction.mensaje}</p>
          </div>

          {/* Bank Comparison */}
          <div className="pred-banks" data-testid="pred-banks">
            <div className="pred-bank">
              <span className="pred-bank-name">Inst. 1</span>
              <div className="pred-bank-bar-bg">
                <div className="pred-bank-bar" style={{ width: `${Math.max(prediction.score_btg, 0)}%`, background: getScoreColor(prediction.score_btg) }}></div>
              </div>
              <span className="pred-bank-score" style={{ color: getScoreColor(prediction.score_btg) }}>{Math.round(prediction.score_btg)}%</span>
            </div>
            <div className="pred-bank">
              <span className="pred-bank-name">Inst. 2</span>
              <div className="pred-bank-bar-bg">
                <div className="pred-bank-bar" style={{ width: `${Math.max(prediction.score_ameris, 0)}%`, background: getScoreColor(prediction.score_ameris) }}></div>
              </div>
              <span className="pred-bank-score" style={{ color: getScoreColor(prediction.score_ameris) }}>{Math.round(prediction.score_ameris)}%</span>
            </div>
            <div className="pred-bank-rec" data-testid="pred-mejor-banco">
              Mejor opcion: <strong>{prediction.mejor_banco}</strong>
            </div>
          </div>

          {/* Key Metrics */}
          <div className="pred-metrics" data-testid="pred-metrics">
            <div className="pred-metric">
              <span className="pred-metric-label">Div/Renta</span>
              <span className={`pred-metric-val ${prediction.metricas.div_renta_individual > 35 ? "danger" : prediction.metricas.div_renta_individual > 30 ? "warn" : "ok"}`}>
                {prediction.metricas.div_renta_individual}%
              </span>
            </div>
            <div className="pred-metric">
              <span className="pred-metric-label">LTV</span>
              <span className={`pred-metric-val ${prediction.metricas.ltv > 80 ? "danger" : prediction.metricas.ltv > 70 ? "warn" : "ok"}`}>
                {prediction.metricas.ltv}%
              </span>
            </div>
            <div className="pred-metric">
              <span className="pred-metric-label">Edad+Plazo</span>
              <span className={`pred-metric-val ${prediction.metricas.edad_plazo > 80 ? "danger" : prediction.metricas.edad_plazo > 75 ? "warn" : "ok"}`}>
                {prediction.metricas.edad_plazo}
              </span>
            </div>
            <div className="pred-metric">
              <span className="pred-metric-label">Carga Fin.</span>
              <span className={`pred-metric-val ${prediction.metricas.carga_financiera_total > 35 ? "danger" : prediction.metricas.carga_financiera_total > 30 ? "warn" : "ok"}`}>
                {prediction.metricas.carga_financiera_total}%
              </span>
            </div>
          </div>

          {/* Optimal Credit */}
          {prediction.optimo?.credito_maximo_seguro_uf > 0 && (
            <div className="pred-optimal" data-testid="pred-optimal">
              <div className="pred-optimal-label">Credito maximo seguro</div>
              <div className="pred-optimal-val">{prediction.optimo.credito_maximo_seguro_uf.toLocaleString("es-CL", { minimumFractionDigits: 1 })} UF</div>
            </div>
          )}

          {/* Risk Factors */}
          {prediction.factores_riesgo?.length > 0 && (
            <div className="pred-risks" data-testid="pred-risks">
              <div className="pred-section-label">Factores de riesgo</div>
              {prediction.factores_riesgo.map((f, i) => (
                <div key={i} className="pred-risk-item">
                  <span className="pred-risk-dot" style={{ background: getSeverityColor(f.severidad) }}></span>
                  <div className="pred-risk-info">
                    <span className="pred-risk-name">{f.factor}</span>
                    <span className="pred-risk-detail">{f.valor} (umbral: {f.umbral})</span>
                  </div>
                  <span className="pred-risk-sev" style={{ color: getSeverityColor(f.severidad) }}>{f.severidad}</span>
                </div>
              ))}
            </div>
          )}

          {/* Suggestions */}
          {prediction.sugerencias?.length > 0 && (
            <div className="pred-suggestions" data-testid="pred-suggestions">
              <div className="pred-section-label">Sugerencias</div>
              {prediction.sugerencias.map((s, i) => (
                <div key={i} className="pred-suggestion-item">
                  <i className="fa fa-lightbulb-o"></i>
                  <span>{s}</span>
                </div>
              ))}
            </div>
          )}

          {/* Historical Comparison */}
          <div className="pred-history" data-testid="pred-history-comparison">
            <span>vs Promedio historico ({prediction.comparacion_historica.tasa_aprobacion_global}%): </span>
            <span className={prediction.comparacion_historica.su_probabilidad_vs_promedio >= 0 ? "pred-above" : "pred-below"}>
              {prediction.comparacion_historica.su_probabilidad_vs_promedio > 0 ? "+" : ""}
              {prediction.comparacion_historica.su_probabilidad_vs_promedio}%
            </span>
          </div>

          {/* Insights Toggle */}
          {insights?.insights?.length > 0 && (
            <>
              <button className="pred-insights-toggle" onClick={() => setShowInsights(!showInsights)} data-testid="pred-insights-toggle">
                <i className={`fa fa-${showInsights ? "chevron-up" : "chevron-down"}`}></i>
                {showInsights ? "Ocultar" : "Ver"} Insights Historicos ({insights.insights.length})
              </button>
              {showInsights && (
                <div className="pred-insights" data-testid="pred-insights">
                  {insights.insights.map((ins, i) => (
                    <div key={i} className="pred-insight-item">
                      <div className="pred-insight-title">{ins.titulo}</div>
                      <div className="pred-insight-detail">{ins.detalle}</div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}

export default PredictivePanel;
