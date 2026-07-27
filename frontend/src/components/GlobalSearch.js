import { useState } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

export default function GlobalSearch({ onNavigate, onClose }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);

  const doSearch = async (q) => {
    setQuery(q);
    if (q.length < 2) { setResults([]); return; }
    try {
      const r = await axios.get(`${API_URL}/api/search`, { params: { q, limit: 15 } });
      setResults(r.data?.results || []);
    } catch { setResults([]); }
  };

  const handleSelect = (item) => {
    onNavigate(item.modulo || "dashboard");
  };

  return (
    <div className="gs-overlay" onClick={onClose}>
      <div className="gs-modal" onClick={e => e.stopPropagation()} data-testid="global-search-modal">
        <div className="gs-input-wrap">
          <i className="fa fa-search gs-icon"></i>
          <input type="text" className="gs-input" placeholder="Buscar clientes, simulaciones, correos..."
            value={query} onChange={e => doSearch(e.target.value)} autoFocus data-testid="global-search-input" />
          <span className="gs-esc">ESC</span>
        </div>
        {results.length > 0 && (
          <div className="gs-results" data-testid="global-search-results">
            {results.map((r, i) => (
              <button key={i} className="gs-result-item" onClick={() => handleSelect(r)} data-testid={`search-result-${i}`}>
                <i className={`fa ${r.tipo === 'simulacion' ? 'fa-bar-chart' : r.tipo === 'cliente' ? 'fa-folder' : r.tipo === 'seguimiento' ? 'fa-road' : 'fa-comment'} gs-result-icon`}></i>
                <div className="gs-result-content">
                  <span className="gs-result-name">{r.nombre}</span>
                  <span className="gs-result-detail">{r.detalle}</span>
                </div>
                <span className="gs-result-type">{r.tipo}</span>
              </button>
            ))}
          </div>
        )}
        {query.length >= 2 && results.length === 0 && (
          <div className="gs-empty">Sin resultados para "{query}"</div>
        )}
      </div>
    </div>
  );
}
