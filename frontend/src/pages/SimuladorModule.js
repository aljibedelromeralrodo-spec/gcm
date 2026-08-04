import { useState, useEffect, useRef } from "react";
import axios from "axios";
import { API_URL, formatUF, formatCurrency } from "../utils/formatters";
import PredictivePanel from "../components/PredictivePanel";
import AIPanel from "../components/AIPanel";
import FichaModal from "../components/FichaModal";

export default function SimuladorModule({ valorUF, loadedSimulation }) {
  const [resultado, setResultado] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [mostrarPreview, setMostrarPreview] = useState(false);
  const [mostrarConfig, setMostrarConfig] = useState(false);
  const [montoDeudaTotal, setMontoDeudaTotal] = useState("");
  const previewRef = useRef(null);

  const [umbrales, setUmbrales] = useState({
    btg_div_renta: 35, btg_carga_fin: 40, btg_ltv: 80, btg_edad_plazo: 80,
    ameris_div_renta: 30, ameris_carga_fin: 35, ameris_ltv: 80, ameris_edad_plazo: 75
  });

  const [formData, setFormData] = useState({
    nombre_completo: "", rut: "", telefono: "", correo: "",
    renta_titular: "", renta_codeudor: "", plazo_anos: "", tasa_anual: "6.35",
    carga_financiera: "", ahorro_uf: "", subsidio_uf: "", edad_cliente: "", edad_codeudor: "",
    valor_propiedad_uf: "", credito_solicitado_uf: "",
    continuidad_laboral: true, protestos_vigentes: false, morosidad_dicom: false, tipo_deudor: 1
  });

  useEffect(() => {
    if (loadedSimulation) setResultado(loadedSimulation);
  }, [loadedSimulation]);

  const valorCuotaDeuda = (() => {
    const deuda = parseFloat(montoDeudaTotal);
    if (!deuda || deuda <= 0) return null;
    const r = Math.pow(1.02, 1 / 12) - 1;
    const n = 48;
    const factor = Math.pow(1 + r, n);
    return Math.round(deuda * (r * factor) / (factor - 1));
  })();

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setCargando(true);
    try {
      const data = {
        nombre_completo: formData.nombre_completo, rut: formData.rut, telefono: formData.telefono, correo: formData.correo,
        valor_uf: valorUF,
        renta_titular: parseFloat(formData.renta_titular) || 0,
        renta_codeudor: parseFloat(formData.renta_codeudor) || 0,
        plazo_anos: parseInt(formData.plazo_anos) || 0,
        tasa_anual: parseFloat(formData.tasa_anual) / 100 || 0,
        carga_financiera: parseFloat(formData.carga_financiera) || 0,
        ahorro_uf: parseFloat(formData.ahorro_uf) || 0,
        subsidio_uf: parseFloat(formData.subsidio_uf) || 0,
        edad_cliente: parseInt(formData.edad_cliente) || 0,
        edad_codeudor: parseInt(formData.edad_codeudor) || 0,
        valor_propiedad_uf: parseFloat(formData.valor_propiedad_uf) || 0,
        credito_solicitado_uf: parseFloat(formData.credito_solicitado_uf) || 0,
        continuidad_laboral: formData.continuidad_laboral,
        protestos_vigentes: formData.protestos_vigentes,
        morosidad_dicom: formData.morosidad_dicom,
        tipo_deudor: parseInt(formData.tipo_deudor) || 1,
        umbral_btg_div_renta: umbrales.btg_div_renta / 100,
        umbral_btg_carga_fin: umbrales.btg_carga_fin / 100,
        umbral_btg_ltv: umbrales.btg_ltv / 100,
        umbral_btg_edad_plazo: umbrales.btg_edad_plazo,
        umbral_ameris_div_renta: umbrales.ameris_div_renta / 100,
        umbral_ameris_carga_fin: umbrales.ameris_carga_fin / 100,
        umbral_ameris_ltv: umbrales.ameris_ltv / 100,
        umbral_ameris_edad_plazo: umbrales.ameris_edad_plazo
      };
      const response = await axios.post(`${API_URL}/api/simular-credito`, data);
      setResultado(response.data);
    } catch (err) {
      alert("Error al simular: " + (err.response?.data?.detail || err.message));
    }
    setCargando(false);
  };

  const handleDownloadPDF = async () => {
    if (!resultado) return;
    try {
      const response = await axios.post(`${API_URL}/api/simulacion/pdf`, resultado, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `Central_Mutuos_${resultado.nombre_completo || 'simulacion'}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert('Error generando PDF: ' + err.message);
    }
  };

  return (
    <div className="module-content">
      <div className="sim-grid sim-grid-3col">
        {/* FORM */}
        <div className="sim-form-col">
          <form onSubmit={handleSubmit} className="sim-form" data-testid="simulation-form">
            <div className="flex justify-end mb-2">
              <button type="button" onClick={() => setMostrarConfig(!mostrarConfig)} className="config-btn" data-testid="btn-config">
                {mostrarConfig ? 'Cerrar Config' : 'Configuración'}
              </button>
            </div>

            {mostrarConfig && (
              <div className="config-panel" data-testid="panel-config">
                <h4 className="config-title">Umbrales de Aprobación</h4>
                <div className="config-grid">
                  <div className="config-institution">
                    <h5 className="config-inst-name">Institucion 1</h5>
                    <div className="config-fields">
                      <div><label>DIV/Renta %</label><input type="number" value={umbrales.btg_div_renta} onChange={e => setUmbrales(p=>({...p,btg_div_renta:+e.target.value||0}))} data-testid="config-btg-div-renta" /></div>
                      <div><label>Carga Fin %</label><input type="number" value={umbrales.btg_carga_fin} onChange={e => setUmbrales(p=>({...p,btg_carga_fin:+e.target.value||0}))} data-testid="config-btg-carga-fin" /></div>
                      <div><label>LTV %</label><input type="number" value={umbrales.btg_ltv} onChange={e => setUmbrales(p=>({...p,btg_ltv:+e.target.value||0}))} data-testid="config-btg-ltv" /></div>
                      <div><label>Edad+Plazo</label><input type="number" value={umbrales.btg_edad_plazo} onChange={e => setUmbrales(p=>({...p,btg_edad_plazo:+e.target.value||0}))} data-testid="config-btg-edad-plazo" /></div>
                    </div>
                  </div>
                  <div className="config-institution">
                    <h5 className="config-inst-name">Institucion 2</h5>
                    <div className="config-fields">
                      <div><label>DIV/Renta %</label><input type="number" value={umbrales.ameris_div_renta} onChange={e => setUmbrales(p=>({...p,ameris_div_renta:+e.target.value||0}))} data-testid="config-ameris-div-renta" /></div>
                      <div><label>Carga Fin %</label><input type="number" value={umbrales.ameris_carga_fin} onChange={e => setUmbrales(p=>({...p,ameris_carga_fin:+e.target.value||0}))} data-testid="config-ameris-carga-fin" /></div>
                      <div><label>LTV %</label><input type="number" value={umbrales.ameris_ltv} onChange={e => setUmbrales(p=>({...p,ameris_ltv:+e.target.value||0}))} data-testid="config-ameris-ltv" /></div>
                      <div><label>Edad+Plazo</label><input type="number" value={umbrales.ameris_edad_plazo} onChange={e => setUmbrales(p=>({...p,ameris_edad_plazo:+e.target.value||0}))} data-testid="config-ameris-edad-plazo" /></div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            <fieldset className="form-fieldset">
              <legend>Datos Personales</legend>
              <div className="field-grid-2">
                <div><label>Nombre Completo</label><input name="nombre_completo" value={formData.nombre_completo} onChange={handleInputChange} placeholder="Nombre del cliente" data-testid="input-nombre-completo" /></div>
                <div><label>RUT</label><input name="rut" value={formData.rut} onChange={handleInputChange} placeholder="12.345.678-9" data-testid="input-rut" /></div>
                <div><label>Teléfono</label><input name="telefono" value={formData.telefono} onChange={handleInputChange} placeholder="+56 9..." data-testid="input-telefono" /></div>
                <div><label>Correo</label><input name="correo" value={formData.correo} onChange={handleInputChange} placeholder="email@ejemplo.cl" data-testid="input-correo" /></div>
              </div>
            </fieldset>

            <fieldset className="form-fieldset">
              <legend>Datos del Crédito</legend>
              <div className="field-grid-2">
                <div><label>Renta Titular (CLP)</label><input type="number" name="renta_titular" value={formData.renta_titular} onChange={handleInputChange} placeholder="1.000.000" data-testid="input-renta-titular" /></div>
                <div><label>Renta Codeudor (CLP)</label><input type="number" name="renta_codeudor" value={formData.renta_codeudor} onChange={handleInputChange} placeholder="0" data-testid="input-renta-codeudor" /></div>
                <div><label>Plazo (Años)</label><input type="number" name="plazo_anos" value={formData.plazo_anos} onChange={handleInputChange} placeholder="25" data-testid="input-plazo" /></div>
                <div><label>Tasa Anual (%)</label><input type="number" step="0.01" name="tasa_anual" value={formData.tasa_anual} onChange={handleInputChange} placeholder="6.35" data-testid="input-tasa" /></div>
                <div><label>Edad Cliente</label><input type="number" name="edad_cliente" value={formData.edad_cliente} onChange={handleInputChange} placeholder="35" data-testid="input-edad" /></div>
                <div><label>Edad Codeudor</label><input type="number" name="edad_codeudor" value={formData.edad_codeudor} onChange={handleInputChange} placeholder="30" data-testid="input-edad-codeudor" /></div>
              </div>
            </fieldset>

            <fieldset className="form-fieldset">
              <legend>Deudas y Ahorros</legend>
              <div className="field-grid-2">
                <div><label>Carga Financiera (CLP)</label><input type="number" name="carga_financiera" value={formData.carga_financiera} onChange={handleInputChange} placeholder="200.000" data-testid="input-carga-financiera" /></div>
                <div><label>Ahorro (UF)</label><input type="number" step="0.01" name="ahorro_uf" value={formData.ahorro_uf} onChange={handleInputChange} placeholder="300" data-testid="input-ahorro" /></div>
                <div><label>Subsidio (UF)</label><input type="number" step="0.01" name="subsidio_uf" value={formData.subsidio_uf} onChange={handleInputChange} placeholder="0" data-testid="input-subsidio" /></div>
              </div>
            </fieldset>

            <fieldset className="form-fieldset fieldset-highlight">
              <legend>Valor Cuota Estimado de Deuda</legend>
              <div className="field-grid-2">
                <div><label>Monto Deuda Total (CLP)</label><input type="number" value={montoDeudaTotal} onChange={e => setMontoDeudaTotal(e.target.value)} placeholder="5.000.000" data-testid="input-monto-deuda" /></div>
                <div>
                  <label>Cuota (48m, 2% anual)</label>
                  <div className={`cuota-result ${valorCuotaDeuda ? 'active' : ''}`} data-testid="valor-cuota-deuda">
                    {valorCuotaDeuda ? formatCurrency(valorCuotaDeuda) + ' /mes' : 'Ingrese monto'}
                  </div>
                </div>
              </div>
            </fieldset>

            <fieldset className="form-fieldset fieldset-gold">
              <legend>Crédito Solicitado</legend>
              <div className="field-grid-2">
                <div><label>Valor Propiedad (UF)</label><input type="number" step="0.01" name="valor_propiedad_uf" value={formData.valor_propiedad_uf} onChange={handleInputChange} placeholder="3.000" data-testid="input-valor-propiedad" /></div>
                <div><label>Crédito Solicitado (UF)</label><input type="number" step="0.01" name="credito_solicitado_uf" value={formData.credito_solicitado_uf} onChange={handleInputChange} placeholder="2.400" data-testid="input-credito-solicitado" /></div>
              </div>
              <p className="field-hint">Sin subsidio: máx 80%. Con subsidio: crédito + ahorro + subsidio = propiedad.</p>
            </fieldset>

            <fieldset className="form-fieldset">
              <legend>Antecedentes Comerciales</legend>
              <div className="field-grid-2">
                <div>
                  <label>Tipo de Deudor</label>
                  <select name="tipo_deudor" value={formData.tipo_deudor} onChange={handleInputChange} data-testid="select-tipo-deudor">
                    <option value={1}>Tipo 1 - Renta Fija</option>
                    <option value={2}>Tipo 2 - Renta Variable</option>
                    <option value={3}>Tipo 3 - Independiente</option>
                  </select>
                </div>
                <div className="checkbox-field">
                  <input type="checkbox" checked={formData.continuidad_laboral} onChange={e => setFormData(p=>({...p,continuidad_laboral:e.target.checked}))} data-testid="check-continuidad" />
                  <label>Continuidad Laboral</label>
                </div>
                <div className="checkbox-field">
                  <input type="checkbox" checked={formData.protestos_vigentes} onChange={e => setFormData(p=>({...p,protestos_vigentes:e.target.checked}))} data-testid="check-protestos" />
                  <label className={formData.protestos_vigentes ? 'text-danger' : ''}>Protestos Vigentes</label>
                </div>
                <div className="checkbox-field">
                  <input type="checkbox" checked={formData.morosidad_dicom} onChange={e => setFormData(p=>({...p,morosidad_dicom:e.target.checked}))} data-testid="check-morosidad" />
                  <label className={formData.morosidad_dicom ? 'text-danger' : ''}>Morosidad DICOM</label>
                </div>
              </div>
            </fieldset>

            <button type="submit" className="submit-btn" disabled={cargando} data-testid="btn-simular">
              {cargando ? "Procesando..." : "Verificar Capacidad Crediticia"}
            </button>
          </form>
        </div>

        {/* PREDICTIVE AI PANEL */}
        <div className="sim-predict-col">
          <PredictivePanel formData={formData} valorUF={valorUF} />
        </div>

        {/* RESULTS COLUMN */}
        <div className="sim-results-col">
          {resultado ? (
            <>
              <div className="result-card" data-testid="resultado-card">
                <div className={`result-header ${resultado.precalificacion_aprobada ? 'approved' : 'rejected'}`}>
                  <h3>{resultado.precalificacion_aprobada ? 'CUMPLE CRITERIOS' : 'NO CUMPLE CRITERIOS'}</h3>
                  <p>{resultado.nombre_completo}</p>
                </div>
                <div className="result-body">
                  <div className="result-row"><span>Capacidad de Credito</span><span className="result-val gold" data-testid="capacidad-credito">{formatUF(resultado.capacidad_credito_uf)}</span></div>
                  <div className="result-row"><span>En Pesos</span><span className="result-val" data-testid="capacidad-credito-clp">{formatCurrency(resultado.capacidad_credito_clp)}</span></div>
                  <div className="result-row"><span>Dividendo Mensual</span><span className="result-val" data-testid="dividendo">{formatCurrency(resultado.dividendo_credito_clp || resultado.dividendo_tope)} ({formatUF(resultado.dividendo_credito_uf || 0)})</span></div>

                  <div className="result-sections-grid">
                    <div>
                      <div className="result-section" data-testid="credito-maximo-section">
                        <h4>Monto Maximo de Credito</h4>
                        <div className="max-credit-box">
                          <span className="max-credit-uf" data-testid="credito-maximo-uf">{formatUF(resultado.credito_maximo_uf)}</span>
                          <span className="max-credit-clp" data-testid="credito-maximo-clp">{formatCurrency(resultado.credito_maximo_uf * resultado.valor_uf)}</span>
                        </div>
                      </div>

                      <div className="result-section" data-testid="evaluacion-instituciones">
                        <h4>Evaluacion Instituciones</h4>
                        <div className="eval-grid">
                          {(resultado.eval_btg === 'APROBADO/A' || resultado.eval_btg === 'VIABLE') && (
                            <div className="eval-badge approved" data-testid="eval-btg-badge">
                              <span className="eval-name">Institucion 1</span><span className="eval-status">{resultado.eval_btg}</span>
                            </div>
                          )}
                          {(resultado.eval_ameris === 'APROBADO/A' || resultado.eval_ameris === 'VIABLE') && (
                            <div className="eval-badge approved" data-testid="eval-ameris-badge">
                              <span className="eval-name">Institucion 2</span><span className="eval-status">{resultado.eval_ameris}</span>
                            </div>
                          )}
                          {resultado.eval_btg !== 'APROBADO/A' && resultado.eval_btg !== 'VIABLE' &&
                           resultado.eval_ameris !== 'APROBADO/A' && resultado.eval_ameris !== 'VIABLE' && (
                            <div className="eval-reasons">
                              <p style={{fontWeight: 700, color: '#e11d48'}}>Sin opciones viables</p>
                              {resultado.eval_btg_razones?.map((r, i) => <p key={'b'+i}>{r}</p>)}
                              {resultado.eval_ameris_razones?.map((r, i) => <p key={'a'+i}>{r}</p>)}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>

                    <div>
                      <div className="result-section" data-testid="ratios-section">
                        <h4>Ratios Ficha PreAprobacion</h4>
                        <table className="ratios-table" data-testid="tabla-ratios">
                          <thead><tr><th>Ratio</th><th>Individual</th>{resultado.tiene_codeudor && <th>Codeudor</th>}<th>Conjunta</th></tr></thead>
                          <tbody>
                            <tr><td>DIV/Renta</td><td className={resultado.div_renta_individual > 0.35 ? 'danger' : 'success'} data-testid="div-renta-ind">{(resultado.div_renta_individual*100).toFixed(1)}%</td>{resultado.tiene_codeudor && <td className={resultado.div_renta_codeudor > 0.35 ? 'danger' : 'success'}>{(resultado.div_renta_codeudor*100).toFixed(1)}%</td>}<td className={resultado.div_renta_conjunta > 0.30 ? 'danger' : 'success'} data-testid="div-renta-conj">{(resultado.div_renta_conjunta*100).toFixed(1)}%</td></tr>
                            <tr><td>Carga Fin.</td><td className={resultado.carga_fin_individual > 0.40 ? 'danger' : 'success'} data-testid="carga-fin-ind">{(resultado.carga_fin_individual*100).toFixed(1)}%</td>{resultado.tiene_codeudor && <td className={resultado.carga_fin_codeudor > 0.40 ? 'danger' : 'success'}>{(resultado.carga_fin_codeudor*100).toFixed(1)}%</td>}<td className={resultado.carga_fin_conjunta > 0.35 ? 'danger' : 'success'} data-testid="carga-fin-conj">{(resultado.carga_fin_conjunta*100).toFixed(1)}%</td></tr>
                          </tbody>
                        </table>
                        <div className="ratios-extra">
                          <span>LTV: <b className={resultado.ltv > 0.80 ? 'danger' : 'success'} data-testid="ltv-valor">{(resultado.ltv*100).toFixed(1)}%</b></span>
                          <span>Edad+Plazo: <b className={resultado.edad_plazo > 80 ? 'danger' : 'success'} data-testid="edad-plazo-valor">{resultado.edad_plazo}</b></span>
                        </div>
                        <p className="tipo-deudor-text" data-testid="tipo-deudor-texto">{resultado.tipo_deudor_texto}</p>
                      </div>

                      {resultado.credito_solicitado_uf > 0 && (
                        <div className="result-section" data-testid="verificacion-credito">
                          <h4>Verificacion Credito Solicitado</h4>
                          <div className="result-row"><span>Credito Solicitado</span><span className="result-val gold" data-testid="credito-solicitado-result">{formatUF(resultado.credito_solicitado_uf)}</span></div>
                          {resultado.pie_requerido_uf > 0 && <div className="result-row"><span>Pie Requerido</span><span className="result-val" data-testid="pie-requerido-result">{formatUF(resultado.pie_requerido_uf)}</span></div>}
                          <div className={`viable-badge ${resultado.credito_viable ? 'viable' : 'no-viable'}`} data-testid="credito-viable-badge">
                            {resultado.credito_viable ? 'CREDITO VIABLE' : 'CREDITO NO VIABLE'}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {resultado.razones_rechazo?.length > 0 && (
                    <div className="rejection-reasons" data-testid="razones-rechazo">
                      <h4>Razones de Rechazo</h4>
                      {resultado.razones_rechazo.map((r, i) => <p key={i}>- {r}</p>)}
                    </div>
                  )}
                </div>
              </div>

              <AIPanel resultado={resultado} valorUF={valorUF} />

              <div className="action-buttons" data-testid="action-buttons">
                <button className="action-btn ficha" onClick={() => setMostrarPreview(true)} data-testid="btn-ficha">
                  <i className="fa fa-file-text-o"></i> Ver Ficha
                </button>
                <button className="action-btn print" onClick={() => { setMostrarPreview(true); setTimeout(() => window.print(), 500); }} data-testid="btn-print">
                  <i className="fa fa-print"></i> Imprimir
                </button>
                <button className="action-btn pdf" onClick={handleDownloadPDF} data-testid="btn-pdf">
                  <i className="fa fa-file-pdf-o"></i> PDF
                </button>
                <button className="action-btn email" onClick={() => {
                  const subject = encodeURIComponent(`Simulación Crediticia - ${resultado.nombre_completo}`);
                  const body = encodeURIComponent(`Estimado/a,\n\nAdjunto resultados de simulación crediticia:\n\nCliente: ${resultado.nombre_completo}\nCapacidad: ${formatUF(resultado.capacidad_credito_uf)}\nDividendo: ${formatCurrency(resultado.dividendo_credito_clp || resultado.dividendo_tope)}\nCrédito Máximo: ${formatUF(resultado.credito_maximo_uf)}\n\nSaludos,\nCentral Mutual - Con Creces`);
                  window.open(`mailto:?subject=${subject}&body=${body}`);
                }} data-testid="btn-email">
                  <i className="fa fa-envelope"></i> Email
                </button>
                <button className="action-btn whatsapp" onClick={() => {
                  const text = encodeURIComponent(`*Simulación Crediticia*\nCliente: ${resultado.nombre_completo}\nCapacidad: ${formatUF(resultado.capacidad_credito_uf)}\nDividendo: ${formatCurrency(resultado.dividendo_credito_clp || resultado.dividendo_tope)}\nCrédito Máximo: ${formatUF(resultado.credito_maximo_uf)}\n\n_Central Mutual - Con Creces_`);
                  window.open(`https://wa.me/?text=${text}`, '_blank');
                }} data-testid="btn-whatsapp">
                  <i className="fa fa-whatsapp"></i> WhatsApp
                </button>
              </div>
            </>
          ) : (
            <div className="empty-results" data-testid="empty-results">
              <div className="empty-icon">&#9888;</div>
              <h3>Sin Resultados</h3>
              <p>Complete el formulario y presione "Verificar Capacidad Crediticia" para ver el análisis.</p>
            </div>
          )}
        </div>
      </div>

      {mostrarPreview && resultado && (
        <FichaModal
          resultado={resultado}
          valorUF={valorUF}
          onClose={() => setMostrarPreview(false)}
          previewRef={previewRef}
          onDownloadPDF={handleDownloadPDF}
        />
      )}
    </div>
  );
}
