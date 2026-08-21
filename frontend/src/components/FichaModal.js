import { formatUF, formatCurrency } from "../utils/formatters";

export default function FichaModal({ resultado, valorUF: _valorUF, onClose, previewRef, onDownloadPDF }) {
  return (
    <div className="ficha-overlay" onClick={onClose} data-testid="ficha-modal">
      <div className="ficha-modal" onClick={(e) => e.stopPropagation()}>
        <div className="ficha-modal-header">
          <h2>Ficha - Evaluación de Crédito</h2>
          <button onClick={onClose} className="ficha-close">&times;</button>
        </div>

        <div className="ficha-content" ref={previewRef}>
          <div className="ficha-logos">
            <div className="ficha-brand-left">
              <h3>Central Mutuos</h3>
              <p>Asesoría Crediticia</p>
            </div>
            <div className="ficha-brand-right">
              <h3>Con Creces</h3>
              <p>Asesorías</p>
            </div>
          </div>

          <div className="ficha-section">
            <h3 className="ficha-section-title">DATOS DEL CLIENTE</h3>
            <div className="ficha-grid-2">
              <div><strong>Nombre:</strong> {resultado.nombre_completo || 'No proporcionado'}</div>
              <div><strong>RUT:</strong> {resultado.rut || 'No proporcionado'}</div>
              <div><strong>Teléfono:</strong> {resultado.telefono || 'No proporcionado'}</div>
              <div><strong>Email:</strong> {resultado.correo || 'No proporcionado'}</div>
            </div>
          </div>

          <div className={`ficha-result-banner ${resultado.precalificacion_aprobada ? 'approved' : 'rejected'}`}>
            <h3>CAPACIDAD CREDITICIA CALCULADA</h3>
          </div>

          <div className="ficha-section">
            <h3 className="ficha-section-title">CAPACIDAD DE CRÉDITO</h3>
            <div className="ficha-grid-2">
              <div><strong>Capacidad:</strong> {formatUF(resultado.capacidad_credito_uf)}</div>
              <div><strong>En Pesos:</strong> {formatCurrency(resultado.capacidad_credito_clp)}</div>
              <div><strong>Valor Máx. Compra:</strong> {formatUF(resultado.valor_maximo_compra_uf)}</div>
              <div><strong>Dividendo Mensual:</strong> {formatCurrency(resultado.dividendo_credito_clp || resultado.dividendo_tope)}</div>
              <div><strong>Tasa Anual:</strong> {resultado.tasa_anual ? (resultado.tasa_anual * 100).toFixed(2) : '6.35'}%</div>
              <div><strong>Plazo:</strong> {resultado.plazo_anos} años</div>
              {resultado.credito_solicitado_uf > 0 && <>
                <div><strong>Crédito Solicitado:</strong> {formatUF(resultado.credito_solicitado_uf)}</div>
                <div><strong>Crédito Máximo:</strong> {formatUF(resultado.credito_maximo_uf)}</div>
              </>}
            </div>
          </div>

          <div className="ficha-section">
            <h3 className="ficha-checklist-title">CHECK LIST - EVALUACION DE CASOS</h3>
            <table className="ficha-checklist-table">
              <thead>
                <tr>
                  <th style={{width:'30%'}}>ITEM</th>
                  <th>DETALLE CON SUBSIDIO</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="ficha-item-label">ANTECEDENTES PERSONALES</td>
                  <td>
                    <ul>
                      <li>C.I (Ambos lados). <em>(Extranjeros deben contar con permanencia definitiva)</em></li>
                      <li>Idem anterior, para el caso de los codeudores.</li>
                      <li>DPS y formularios firmados. <em>(Contra cierre de la operación)</em></li>
                    </ul>
                  </td>
                </tr>
                <tr>
                  <td className="ficha-item-label">ANTECEDENTES LABORALES</td>
                  <td>
                    <ul>
                      <li>Liquidaciones últimos 3 meses <em>(renta fija)</em></li>
                      <li>Liquidaciones últimos 6 meses <em>(renta variable)</em></li>
                      <li>Certificado de antigüedad. <em>(Si se indica en la liquidación, se toma en cuenta ese dato)</em></li>
                      <li>Certificado de AFP últimos 24 meses.</li>
                      <li>Trabajadores Independientes <em>(Boletas del año en curso + última declaración de renta)</em></li>
                    </ul>
                  </td>
                </tr>
                <tr>
                  <td className="ficha-item-label">ANTECEDENTES FINANCIEROS</td>
                  <td>
                    <ul>
                      <li>Acreditación de deudas <em>(Certificado de deudas en instituciones bancarias, comerciales, etc.)</em></li>
                    </ul>
                  </td>
                </tr>
                <tr>
                  <td className="ficha-item-label">INFORMACION DE LO QUE COMPRA</td>
                  <td>
                    <ul>
                      <li>Fecha de entrega (Recepción del proyecto)</li>
                      <li>Monto Vivienda</li>
                      <li>Monto Crédito</li>
                      <li>Monto Subsidio</li>
                      <li>Monto Pie</li>
                      <li>Inmobiliaria</li>
                      <li>Proyecto</li>
                      <li>Comuna</li>
                    </ul>
                  </td>
                </tr>
              </tbody>
            </table>
            <div className="ficha-checklist-note">
              *Esta información es estrictamente necesaria para la evaluación del crédito Hipotecario.
            </div>
          </div>

          <div className="ficha-legal">
            <div className="ficha-legal-inner">
              <h3>AVISO LEGAL IMPORTANTE</h3>
              <div className="ficha-legal-divider"></div>
              <p>El presente documento <strong className="ficha-legal-red">NO CONSTITUYE</strong> ni una preaprobación ni aprobación crediticia del cliente.</p>
              <p>Debe pasar por proceso en comité de riesgo para una aprobación final.</p>
            </div>
          </div>

          <div className="ficha-contact">
            <h4>PARA CONTINUAR CON EL PROCESO</h4>
            <div className="ficha-contact-inner">
              <p className="ficha-contact-label">Comuníquese a:</p>
              <a href="mailto:gerardo.ext@centralmutuos.cl" className="ficha-contact-email">gerardo.ext@centralmutuos.cl</a>
              <p className="ficha-contact-brand">Central Mutuos - con creces</p>
            </div>
          </div>
        </div>

        <div className="ficha-actions">
          <button onClick={() => window.print()} className="ficha-action-btn print-btn">Imprimir</button>
          <button onClick={onDownloadPDF} className="ficha-action-btn pdf-btn">Generar PDF</button>
          <button onClick={() => {
            const subject = encodeURIComponent(`Simulación Crediticia - ${resultado.nombre_completo}`);
            const body = encodeURIComponent(`Estimado/a,\n\nAdjunto resultados de simulación crediticia.\n\nCliente: ${resultado.nombre_completo}\nCapacidad: ${formatUF(resultado.capacidad_credito_uf)}\nDividendo: ${formatCurrency(resultado.dividendo_credito_clp || resultado.dividendo_tope)}\n\nSaludos,\nCentral Mutuos - Con Creces`);
            window.open(`mailto:?subject=${subject}&body=${body}`);
          }} className="ficha-action-btn email-btn">Enviar Email</button>
          <button onClick={() => {
            const text = encodeURIComponent(`Central Mutuos - con creces.\nEstimado cliente, envío simulación de capacidad de crédito.\n\nCliente: ${resultado.nombre_completo}\nCapacidad: ${formatUF(resultado.capacidad_credito_uf)}\nDividendo: ${formatCurrency(resultado.dividendo_credito_clp || resultado.dividendo_tope)}\n\nCentral Mutuos - con creces`);
            window.open(`https://wa.me/${resultado.telefono ? resultado.telefono.replace(/\s+/g,'') : ''}?text=${text}`, '_blank');
          }} className="ficha-action-btn wa-btn">Enviar WhatsApp</button>
          <button onClick={onClose} className="ficha-action-btn close-btn">Cerrar</button>
        </div>
      </div>
    </div>
  );
}
