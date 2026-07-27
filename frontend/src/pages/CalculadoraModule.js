import { useState, useEffect } from "react";
import axios from "axios";
import { formatCurrency, API_URL } from "../utils/formatters";

export default function CalculadoraModule({ valorUF }) {
  const [filasDividendo, setFilasDividendo] = useState([
    { tasa: "6.50", plazo: "25", monto: "", codeudor: false, dividendoUF: null, dividendoCLP: null }
  ]);
  const [seguros, setSeguros] = useState({ seguro_desgravamen: 10245, seguro_incendio: 23702 });

  useEffect(() => {
    axios.get(`${API_URL}/api/inmobiliaria/config/seguros`).then(r => {
      if (r.data && r.data.seguro_desgravamen) setSeguros(r.data);
    }).catch(() => {});
  }, []);

  const calcularDividendo = (tasa, plazo, monto) => {
    const tasaAnual = parseFloat(tasa) / 100;
    const plazoAnos = parseInt(plazo);
    const montoUF = parseFloat(monto);
    if (!tasaAnual || !plazoAnos || !montoUF || tasaAnual <= 0 || plazoAnos <= 0 || montoUF <= 0) return null;
    const tasaMensual = Math.pow(1 + tasaAnual, 1 / 12) - 1;
    const n = plazoAnos * 12;
    const factor = Math.pow(1 + tasaMensual, n);
    return { uf: montoUF * (tasaMensual * factor) / (factor - 1), clp: Math.round(montoUF * (tasaMensual * factor) / (factor - 1) * valorUF) };
  };

  const handleChange = (idx, field, value) => {
    setFilasDividendo(prev => {
      const nuevas = [...prev];
      nuevas[idx] = { ...nuevas[idx], [field]: field === "codeudor" ? value : value };
      const r = calcularDividendo(nuevas[idx].tasa, nuevas[idx].plazo, nuevas[idx].monto);
      nuevas[idx].dividendoUF = r ? r.uf : null;
      nuevas[idx].dividendoCLP = r ? r.clp : null;
      return nuevas;
    });
  };

  const getDesgravamen = (codeudor) => codeudor ? seguros.seguro_desgravamen * 2 : seguros.seguro_desgravamen;

  return (
    <div className="module-content">
      <div className="calc-card" data-testid="calculadora-dividendo-card">
        <h3>Calculadora Predictiva de Dividendo</h3>
        <p className="calc-desc">Estime el dividendo mensual con seguros incluidos</p>
        <table className="calc-table" data-testid="tabla-dividendo">
          <thead>
            <tr>
              <th>TASA (%)</th><th>PLAZO</th><th>MONTO (UF)</th><th>CODEUDOR</th>
              <th>DIVIDENDO</th><th>SEG. DESGRAVAMEN</th><th>SEG. INCENDIO</th>
              <th>TOTAL DIVIDENDO</th><th>DIVIDENDO FINAL</th><th></th>
            </tr>
          </thead>
          <tbody>
            {filasDividendo.map((f, i) => {
              const desgravamen = getDesgravamen(f.codeudor);
              const totalSeguros = desgravamen + seguros.seguro_incendio;
              const totalDividendo = f.dividendoCLP ? f.dividendoCLP + totalSeguros : null;
              return (
                <tr key={i} data-testid={`fila-dividendo-${i}`}>
                  <td><input type="number" step="0.01" value={f.tasa} onChange={e => handleChange(i,'tasa',e.target.value)} data-testid={`input-tasa-div-${i}`} style={{width:"70px"}} /></td>
                  <td><input type="number" value={f.plazo} onChange={e => handleChange(i,'plazo',e.target.value)} data-testid={`input-plazo-div-${i}`} style={{width:"55px"}} /></td>
                  <td><input type="number" step="0.01" value={f.monto} onChange={e => handleChange(i,'monto',e.target.value)} data-testid={`input-monto-div-${i}`} style={{width:"80px"}} /></td>
                  <td>
                    <label style={{display:"flex",alignItems:"center",gap:"4px",fontSize:"0.75rem",cursor:"pointer"}}>
                      <input type="checkbox" checked={f.codeudor} onChange={e => handleChange(i,'codeudor',e.target.checked)} data-testid={`input-codeudor-${i}`} />
                      Si
                    </label>
                  </td>
                  <td data-testid={`resultado-clp-div-${i}`} className="calc-highlight">{f.dividendoCLP ? formatCurrency(f.dividendoCLP) : '-'}</td>
                  <td data-testid={`seguro-desgravamen-${i}`} style={{color: f.codeudor ? "#e17055" : "inherit"}}>
                    {formatCurrency(desgravamen)}
                    {f.codeudor && <span style={{fontSize:"0.6rem",display:"block",color:"#e17055"}}>x2 codeudor</span>}
                  </td>
                  <td data-testid={`seguro-incendio-${i}`}>{formatCurrency(seguros.seguro_incendio)}</td>
                  <td data-testid={`total-dividendo-${i}`} style={{fontWeight:600}}>{totalDividendo ? formatCurrency(totalDividendo) : '-'}</td>
                  <td data-testid={`dividendo-final-${i}`} style={{fontWeight:700, color: "var(--accent-primary)", fontSize:"0.95rem"}}>
                    {totalDividendo ? formatCurrency(totalDividendo) : '-'}
                  </td>
                  <td>{filasDividendo.length > 1 && <button className="calc-del" onClick={() => setFilasDividendo(p => p.filter((_,j)=>j!==i))} data-testid={`btn-eliminar-fila-${i}`}>&#10005;</button>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div className="calc-footer">
          <button onClick={() => setFilasDividendo(p => [...p, {tasa:"6.50",plazo:"25",monto:"",codeudor:false,dividendoUF:null,dividendoCLP:null}])} className="calc-add-btn" data-testid="btn-agregar-fila">+ Agregar Escenario</button>
          <span className="calc-uf-note" data-testid="nota-uf-calculadora">UF: {formatCurrency(valorUF)}</span>
        </div>
        <div style={{marginTop:"0.8rem",padding:"0.6rem",borderRadius:"8px",background:"rgba(99,110,114,0.06)",border:"1px solid var(--border)",fontSize:"0.75rem",color:"var(--text-secondary)"}}>
          <i className="fa fa-info-circle" style={{marginRight:"0.3rem",color:"var(--accent-primary)"}}></i>
          Seg. Desgravamen: {formatCurrency(seguros.seguro_desgravamen)} (x2 con codeudor) | Seg. Incendio: {formatCurrency(seguros.seguro_incendio)}
        </div>
      </div>
    </div>
  );
}
