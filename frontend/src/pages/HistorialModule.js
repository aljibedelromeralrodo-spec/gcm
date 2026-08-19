import { useState, useEffect } from "react";
import axios from "axios";
import { API_URL, formatUF } from "../utils/formatters";

export default function HistorialModule({ valorUF: _valorUF, onLoadSimulation }) {
  const [simulaciones, setSimulaciones] = useState([]);

  useEffect(() => {
    axios.get(`${API_URL}/api/simulaciones`, { params: { page: 1, limit: 50 } })
      .then(r => setSimulaciones(r.data.simulaciones || r.data))
      .catch((e) => console.error(e));
  }, []);

  const handleClick = (sim) => {
    const loaded = {
      ...sim,
      credito_maximo_uf: sim.credito_maximo_uf || 0,
      dividendo_credito_uf: sim.dividendo_credito_uf || 0,
      dividendo_credito_clp: sim.dividendo_credito_clp || 0,
      div_renta_individual: sim.div_renta_individual || 0,
      div_renta_codeudor: sim.div_renta_codeudor || 0,
      div_renta_conjunta: sim.div_renta_conjunta || 0,
      carga_fin_individual: sim.carga_fin_individual || 0,
      carga_fin_codeudor: sim.carga_fin_codeudor || 0,
      carga_fin_conjunta: sim.carga_fin_conjunta || 0,
      ltv: sim.ltv || 0,
      edad_plazo: sim.edad_plazo || 0,
      tipo_deudor_texto: sim.tipo_deudor_texto || '',
      tiene_codeudor: sim.tiene_codeudor || false,
      eval_btg: sim.eval_btg || 'SIN EVALUAR',
      eval_btg_razones: sim.eval_btg_razones || [],
      eval_ameris: sim.eval_ameris || 'SIN EVALUAR',
      eval_ameris_razones: sim.eval_ameris_razones || [],
    };
    onLoadSimulation(loaded);
  };

  return (
    <div className="module-content">
      <div className="history-table-wrapper" data-testid="historial-table">
        <table className="history-table">
          <thead>
            <tr><th>Fecha</th><th>Cliente</th><th>RUT</th><th>Crédito UF</th><th>Inst. 1</th><th>Inst. 2</th><th>Estado</th></tr>
          </thead>
          <tbody>
            {simulaciones.map((sim, idx) => (
              <tr key={idx} onClick={() => handleClick(sim)} className="history-row" data-testid={`historial-row-${idx}`}>
                <td>{new Date(sim.timestamp).toLocaleDateString('es-CL').replace(/-/g, '/')}</td>
                <td>{sim.nombre_completo || '-'}</td>
                <td>{sim.rut || '-'}</td>
                <td>{sim.credito_solicitado_uf ? formatUF(sim.credito_solicitado_uf) : formatUF(sim.capacidad_credito_uf)}</td>
                <td>{(sim.eval_btg === 'APROBADO/A' || sim.eval_btg === 'VIABLE') ? <span className="status-pill pill-approved">{sim.eval_btg}</span> : <span className="status-pill pill-rejected">-</span>}</td>
                <td>{(sim.eval_ameris === 'APROBADO/A' || sim.eval_ameris === 'VIABLE') ? <span className="status-pill pill-approved">{sim.eval_ameris}</span> : <span className="status-pill pill-rejected">-</span>}</td>
                <td><span className={`status-pill ${sim.precalificacion_aprobada ? 'pill-approved' : 'pill-rejected'}`}>{sim.precalificacion_aprobada ? 'Aprobado' : 'Rechazado'}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
        {simulaciones.length === 0 && <p className="empty-msg">No hay simulaciones registradas.</p>}
      </div>
    </div>
  );
}
