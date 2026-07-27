import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { API_URL, formatUF, formatCurrency } from "../utils/formatters";

export default function AIPanel({ resultado, valorUF }) {
  const [aiData, setAiData] = useState(null);
  const [loading, setLoading] = useState(false);

  const analizar = useCallback(async () => {
    if (!resultado) return;
    setLoading(true);
    try {
      const res = await axios.post(`${API_URL}/api/ai/analizar`, { resultado, valor_uf: valorUF });
      setAiData(res.data);
    } catch (e) {
      console.error("AI error:", e);
    }
    setLoading(false);
  }, [resultado, valorUF]);

  useEffect(() => { if (resultado) analizar(); }, [resultado, analizar]);

  if (!resultado) return null;

  return (
    <div className="ai-panel" data-testid="ai-panel">
      <div className="ai-header">
        <h3 className="ai-title">Análisis Inteligente</h3>
        <span className="ai-badge">IA</span>
      </div>

      {loading ? (
        <div className="ai-loading" data-testid="ai-loading">
          <div className="ai-spinner"></div>
          <p>Analizando con IA...</p>
        </div>
      ) : aiData ? (
        <div className="space-y-4">
          <div data-testid="ai-escenarios">
            <h4 className="ai-section-title">Escenarios por Plazo</h4>
            <div className="ai-scenarios-grid">
              {aiData.escenarios?.map((esc) => (
                <div key={esc.plazo} className={`ai-scenario-card ${esc.viable ? 'viable' : 'no-viable'}`} data-testid={`escenario-${esc.plazo}`}>
                  <div className="ai-scenario-plazo">{esc.plazo} años</div>
                  <div className="ai-scenario-cap">{formatUF(esc.capacidad_uf)}</div>
                  {esc.dividendo_uf > 0 && <div className="ai-scenario-div">Div: {formatUF(esc.dividendo_uf)}</div>}
                  {esc.dividendo_clp > 0 && <div className="ai-scenario-div-clp">{formatCurrency(esc.dividendo_clp)}/mes</div>}
                  <div className="ai-scenario-edad">Edad+Plazo: {esc.edad_plazo}</div>
                  <div className={`ai-scenario-badge ${esc.viable ? 'badge-viable' : 'badge-no-viable'}`}>
                    {esc.viable ? 'VIABLE' : 'NO VIABLE'}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="ai-max-credit" data-testid="ai-monto-maximo">
            <h4 className="ai-section-title">Monto Máximo Viable</h4>
            <div className="ai-max-value">{formatUF(aiData.monto_maximo_viable_uf)}</div>
            <div className="ai-max-clp">{formatCurrency(aiData.monto_maximo_viable_clp)}</div>
            <div className="ai-max-plazo">Plazo óptimo: {aiData.mejor_plazo} años</div>
          </div>

          {aiData.recomendacion_ia && (
            <div className="ai-recommendation" data-testid="ai-recomendacion">
              <h4 className="ai-section-title">Recomendación IA</h4>
              <div className="ai-rec-text" dangerouslySetInnerHTML={{ __html: aiData.recomendacion_ia
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/^## (.*$)/gm, '<h5 style="color:var(--gold);margin:0.5rem 0 0.25rem;font-size:0.85rem;">$1</h5>')
                .replace(/^# (.*$)/gm, '<h4 style="color:var(--gold);margin:0.75rem 0 0.25rem;font-size:0.9rem;">$1</h4>')
                .replace(/\n/g, '<br/>')
              }} />
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
