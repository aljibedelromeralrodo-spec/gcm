import axios from "axios";
import ImportarCorreo from "../../components/ImportarCorreo";
import ConversorUF from "../../components/ConversorUF";
import EnviarResultadoEjecutivo from "../../components/EnviarResultadoEjecutivo";
import PanelEstadoCarpeta from "../../components/PanelEstadoCarpeta";
import PrediccionEspejo from "../../components/PrediccionEspejo";
import CompromisoEditor from "../CompromisoEditor";
import { API } from "./clientesShared";
import { useClientes } from "./clientesCtx";

export default function ClientesFicha() {
  const {
    agregarCodeudor,
    calcularTecho,
    compromisoLibre,
    currentFolder,
    deleteClientFile,
    downloadAll,
    downloadFile,
    finDraft,
    finOpenId,
    finSaving,
    folders,
    formatSize,
    handleManualUpload,
    loading,
    mergingProto,
    ocrRunning,
    openEmailModal,
    openFinPanel,
    openMissingDocsModal,
    openPreview,
    regenerateCombined,
    runOcrFin,
    saveAllAttachments,
    saveFinPanel,
    setCompromisoLibre,
    setCurrentFolder,
    setFinDraft,
    setShowCompromiso,
    setTecho,
    setView,
    showCompromiso,
    techo,
    techoBusy,
    ufValue,
    uploadingManual,
    view
  } = useClientes();
  return (
        <div data-testid="clientes-detail">
          <div className="clientes-detail-header">
            <button className="docs-btn secondary" onClick={() => { setView("list"); setCurrentFolder(null); }} data-testid="btn-back-clientes">
              <i className="fa fa-arrow-left"></i> Volver
            </button>
            <h3><i className="fa fa-folder-open"></i> {currentFolder.nombre}</h3>
            {/* PRIMERA CATEGORÍA VISIBLE: resolución SERVIU (solo ventas con subsidio) */}
            {(() => {
              const df = currentFolder.datos_financieros || {};
              const conSub = df.con_subsidio ?? (currentFolder.credit_request?.subsidy?.tipo === "con_subsidio");
              const st = { display: "inline-block", padding: "0.35rem 0.9rem", borderRadius: 8, fontWeight: 900, fontSize: 13, letterSpacing: 0.5, whiteSpace: "nowrap" };
              if (!conSub) return (
                <span data-testid="badge-serviu" title="La resolución SERVIU aplica solo a ventas con subsidio"
                  style={{ ...st, background: "rgba(148,163,184,0.12)", color: "#94a3b8", border: "1px dashed #64748b" }}>
                  SIN SUBSIDIO · SERVIU NO APLICA</span>);
              return df.resolucion_serviu
                ? <span data-testid="badge-serviu" style={{ ...st, background: "rgba(34,197,94,0.18)", color: "#22c55e", border: "1px solid #22c55e" }}>✅ CON RESOLUCIÓN SERVIU</span>
                : <span data-testid="badge-serviu" style={{ ...st, background: "rgba(239,68,68,0.18)", color: "#f87171", border: "1px solid #ef4444" }}>⛔ SIN RESOLUCIÓN SERVIU</span>;
            })()}
            <div className="clientes-detail-actions">
              <button className="docs-btn secondary" onClick={saveAllAttachments} disabled={loading} data-testid="btn-fetch-attachments">
                <i className={`fa ${loading ? "fa-spinner fa-spin" : "fa-envelope"}`}></i> Buscar Adjuntos
              </button>
              <button className="docs-btn secondary" onClick={() => document.getElementById('manual-upload-input').click()} disabled={uploadingManual} data-testid="btn-upload-manual"
                style={{ background: "rgba(46,92,230,0.15)", border: "1px solid #2e5ce6", color: "#a78bfa" }}>
                <i className={`fa ${uploadingManual ? "fa-spinner fa-spin" : "fa-upload"}`}></i> {uploadingManual ? "Subiendo…" : "Subir Archivo"}
              </button>
              <input id="manual-upload-input" type="file" multiple style={{ display: "none" }} onChange={handleManualUpload}
                accept=".pdf,.jpg,.jpeg,.png,.heic,.heif,.docx,.doc,.xlsx" data-testid="manual-upload-input" />
              <ImportarCorreo destino="carpeta" destinoId={currentFolder.id} nombre={currentFolder.nombre}
                label="Importar desde correo"
                onDone={async () => { const r = await axios.get(`${API}/api/clientes/folders/${currentFolder.id}`); setCurrentFolder(r.data); }} />
              <ImportarCorreo destino="estudio_titulo" destinoId={currentFolder.id} nombre={currentFolder.nombre}
                label="Importar a Estudio de Título" style={{ background: "rgba(13,148,136,0.25)" }}
                onDone={async () => { const r = await axios.get(`${API}/api/clientes/folders/${currentFolder.id}`); setCurrentFolder(r.data); }} />
              <button className="docs-btn secondary" onClick={regenerateCombined} disabled={mergingProto === currentFolder.id} data-testid="btn-regen-combined"
                style={{ background: "rgba(234,88,12,0.15)", border: "1px solid #ea580c", color: "#fb923c" }}>
                <i className={`fa ${mergingProto === currentFolder.id ? "fa-spinner fa-spin" : "fa-file-pdf-o"}`}></i> {mergingProto === currentFolder.id ? "Combinando…" : "Regenerar Combinado"}
              </button>
              <button className="docs-btn secondary" onClick={() => openFinPanel(currentFolder)} data-testid="btn-fin-detail"
                style={{ background: "rgba(212,175,55,0.15)", border: "1px solid #d4af37", color: "#b8942e" }}>
                <i className="fa fa-dollar"></i> Datos Financieros
              </button>
              <button className="docs-btn secondary shimmer-oro" onClick={() => calcularTecho(currentFolder)} disabled={techoBusy} data-testid="btn-techo-hipotecario"
                style={{ backgroundImage: "linear-gradient(135deg, #BF953F, #FCF6BA 45%, #B38728, #FBF5B7 80%, #AA771C)", border: "none", color: "#0a0a0a", fontWeight: 800 }}>
                <i className={`fa ${techoBusy ? "fa-spinner fa-spin" : "fa-bar-chart"}`}></i> {techoBusy ? "Calculando…" : "Calcular Alcance Máximo"}
              </button>
              <button className="docs-btn secondary shimmer-oro" onClick={() => openEmailModal(currentFolder)} data-testid="btn-send-autocorreo-detail"
                style={{ background: "#10c98a", border: "1px solid #0e9f6e", color: "#fff", fontWeight: 600 }}>
                <i className="fa fa-paper-plane"></i> Enviar a Mesa
              </button>
              <button className="docs-btn secondary" data-testid="btn-reenviar-notificacion"
                onClick={async () => {
                  if (!window.confirm(`📧 ¿Re-enviar la notificación de aprobación a ${currentFolder.nombre}?\nSe saltará el bloqueo de duplicados (para cuando el cliente dice que no le llegó).`)) return;
                  try {
                    const r = await axios.post(`${API}/api/clientes/folders/${currentFolder.id}/reenviar-notificacion`);
                    window.alert(`✅ Notificación re-enviada a ${r.data.to}${(r.data.adjuntos || []).length ? ` con ${r.data.adjuntos.length} adjunto(s)` : r.data.con_links ? " con links de descarga segura" : ""} (BCC cuenta comercial)`);
                  } catch (e) { window.alert(`🚨 ${e.response?.data?.detail || "Error al re-enviar la notificación"}`); }
                }}
                style={{ background: "rgba(59,130,246,0.15)", border: "1px solid #3b82f6", color: "#93c5fd" }}>
                <i className="fa fa-bell"></i> Re-enviar Notificación
              </button>
              <button className="docs-btn secondary shimmer-oro" data-testid="btn-compromiso"
                onClick={() => setShowCompromiso(true)}
                style={{ background: "rgba(212,175,55,0.18)", border: "1px solid #d4af37", color: "#d4af37", fontWeight: 700 }}>
                <i className="fa fa-file-text-o"></i> Ver/Editar Compromiso de Compraventa
              </button>
              <button className="docs-btn secondary" onClick={() => openMissingDocsModal(currentFolder)} data-testid="btn-missing-docs-detail"
                title={(currentFolder.alertas_documentales || []).join("\n") || "Solicitar documentos faltantes"}
                style={{ background: "rgba(225,29,72,0.15)", border: "1px solid rgba(225,29,72,0.5)", color: "#fb7185" }}>
                <i className="fa fa-exclamation-triangle"></i> Documento Faltante
              </button>
              <button className="docs-btn secondary" onClick={() => agregarCodeudor(currentFolder)} data-testid={`btn-agregar-codeudor-${currentFolder.id}`}
                style={{ background: "rgba(251,146,60,0.15)", border: "1px solid rgba(251,146,60,0.5)", color: "#fdba74" }}>
                <i className="fa fa-user-plus"></i> Agregar Codeudor
              </button>
              <button className="docs-btn secondary" onClick={() => window.open(`${API}/api/informes/vip/${currentFolder.id}/pdf`, "_blank")} data-testid={`btn-informe-vip-${currentFolder.id}`}
                style={{ background: "rgba(212,175,55,0.12)", border: "1px solid rgba(212,175,55,0.5)", color: "#d4af37" }}>
                <i className="fa fa-file-pdf-o"></i> Informe VIP
              </button>
              <EnviarResultadoEjecutivo folder={currentFolder} />
              <button className="docs-btn primary" onClick={() => downloadAll(currentFolder.id)} data-testid="btn-download-all">
                <i className="fa fa-download"></i> Descargar Todo
              </button>
            </div>
          </div>

          <PanelEstadoCarpeta folder={currentFolder} />
          {currentFolder.prob_aprobacion?.discrepancia && (
            <div data-testid="discrepancia-viabilidad" style={{
              margin: "0 0 0.9rem", padding: "0.55rem 0.9rem", fontSize: 12, fontWeight: 700,
              border: `1px solid ${currentFolder.prob_aprobacion.discrepancia.hay ? "rgba(234,88,12,0.45)" : "rgba(16,217,142,0.35)"}`,
              background: currentFolder.prob_aprobacion.discrepancia.hay ? "rgba(234,88,12,0.08)" : "rgba(16,217,142,0.06)",
              color: currentFolder.prob_aprobacion.discrepancia.hay ? "#fb923c" : "#10d98e" }}>
              🪞 Mutuaria {currentFolder.prob_aprobacion.mutuaria?.porcentaje ?? currentFolder.prob_aprobacion.porcentaje}%
              {currentFolder.prob_aprobacion.concreces?.disponible
                ? ` · Concreces ${currentFolder.prob_aprobacion.concreces.porcentaje}%`
                : " · Concreces en calibración"}
              {" — "}{currentFolder.prob_aprobacion.discrepancia.mensaje}
            </div>
          )}
          <PrediccionEspejo folderId={currentFolder.id} />

          {showCompromiso && currentFolder && (
            <CompromisoEditor folder={currentFolder} onClose={() => setShowCompromiso(false)} />
          )}
          {compromisoLibre && (
            <CompromisoEditor folder={compromisoLibre} onClose={() => setCompromisoLibre(null)} />
          )}


          {techo && (
            <div data-testid="techo-modal" onClick={() => setTecho(null)}
              style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.82)", zIndex: 300, display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem" }}>
              <div onClick={e => e.stopPropagation()} style={{ background: "#0a0a0a", border: "1px solid rgba(212,175,55,0.4)", width: "min(680px, 96vw)", maxHeight: "90vh", overflow: "auto", padding: "1.6rem 1.8rem" }}>
                <div style={{ display: "flex", alignItems: "center", marginBottom: 6 }}>
                  <b style={{ color: "#d4af37", fontSize: "1.05rem", letterSpacing: "0.04em" }}>📊 Techo Hipotecario — {techo.cliente}</b>
                  <button data-testid="techo-cerrar" onClick={() => setTecho(null)} style={{ marginLeft: "auto", background: "transparent", border: "none", color: "#94a3b8", fontSize: "1.3rem", cursor: "pointer" }}>✕</button>
                </div>
                {!techo.datos_suficientes ? (
                  <div style={{ color: "#fb7185", fontSize: "0.85rem", padding: "1rem 0", lineHeight: 1.6 }}>
                    ⚠️ No hay renta líquida cargada en los Datos Financieros de esta carpeta. Ejecute la extracción OCR de las liquidaciones o ingrese la renta manualmente para calcular el alcance máximo.
                  </div>
                ) : (
                  <>
                    <div style={{ color: "#9a8c52", fontSize: "0.72rem", marginBottom: 14, lineHeight: 1.6 }}>
                      Renta líquida depurada: <b style={{ color: "#e7cf7a" }}>${techo.renta_liquida_depurada_clp.toLocaleString("es-CL")}</b> ·
                      castigos: variable −{techo.componentes_renta.castigo_variable_pct}%, honorarios −{techo.componentes_renta.castigo_honorarios_pct}% ·
                      tasa {techo.tasa_anual_pct}% · plazo {techo.plazo_anos} años
                    </div>
                    {techo.endeudamiento && (
                      <div style={{ border: "1px solid rgba(255,255,255,0.12)", padding: "0.7rem 0.9rem", marginBottom: 14, fontSize: "0.72rem", color: "#94a3b8", lineHeight: 1.7 }}>
                        <b style={{ color: "#cbd5e1" }}>Endeudamiento teórico (fórmula 2% mensual · 48 meses)</b><br />
                        Deuda CMF ${techo.endeudamiento.deuda_cmf_total_clp.toLocaleString("es-CL")} → cuota ${techo.endeudamiento.cuota_teorica_cmf_clp.toLocaleString("es-CL")}/mes ·
                        Crédito interno PAV ${techo.endeudamiento.pav_saldo_clp.toLocaleString("es-CL")} → cuota ${techo.endeudamiento.cuota_teorica_pav_clp.toLocaleString("es-CL")}/mes<br />
                        <b style={{ color: "#e7cf7a" }}>Endeudamiento mensual total: ${techo.endeudamiento.endeudamiento_mensual_clp.toLocaleString("es-CL")}</b> ({techo.carga_actual_pct}% de la renta)
                      </div>
                    )}
                    {techo.alerta_carga_excedida && (
                      <div data-testid="techo-alerta-carga" style={{ background: "rgba(225,29,72,0.12)", border: "1px solid rgba(225,29,72,0.5)", color: "#fb7185", padding: "0.6rem 0.9rem", marginBottom: 14, fontSize: "0.74rem", fontWeight: 700 }}>
                        🚨 Las deudas actuales ya superan el 40% de la renta líquida depurada — sin margen para un nuevo dividendo.
                      </div>
                    )}
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 14 }} data-testid="techo-doble-panel">
                      <div style={{ border: "1px solid rgba(255,255,255,0.15)", padding: "0.9rem 1rem" }}>
                        <div style={{ color: "#94a3b8", fontSize: "0.68rem", letterSpacing: "0.12em", textTransform: "uppercase" }}>Criterio Teórico (Bodega)</div>
                        <div style={{ color: "#e7cf7a", fontWeight: 900, fontSize: "1.2rem", marginTop: 6 }}>
                          {(techo.teorico_uf || 0).toLocaleString("es-CL")} UF
                        </div>
                        <div style={{ color: "#6b6b6b", fontSize: "0.68rem", marginTop: 4 }}>Reglas BTG/Ameris de la Constitución</div>
                      </div>
                      <div data-testid="techo-espejo-mesa" style={{ border: "1px solid rgba(14,165,233,0.45)", padding: "0.9rem 1rem", background: "rgba(14,165,233,0.05)" }}>
                        <div style={{ color: "#a5f3fc", fontSize: "0.68rem", letterSpacing: "0.12em", textTransform: "uppercase" }}>Veredicto Algoritmo Espejo MESA</div>
                        {techo.espejo_mesa?.disponible ? (
                          <>
                            <div style={{ color: "#a5f3fc", fontWeight: 900, fontSize: "1.2rem", marginTop: 6 }}>
                              {techo.espejo_mesa.monto_uf.toLocaleString("es-CL")} UF
                            </div>
                            <div style={{ color: "#6b6b6b", fontSize: "0.68rem", marginTop: 4 }}>
                              Precisión estimada: {techo.espejo_mesa.precision_pct}% · {techo.espejo_mesa.n} casos del segmento
                              {techo.espejo_mesa.segmento ? ` «${techo.espejo_mesa.segmento}»` : ""} · ventana 280 días
                            </div>
                          </>
                        ) : (
                          <div style={{ color: "#94a3b8", fontSize: "0.72rem", marginTop: 8, lineHeight: 1.5 }}>
                            🧠 {techo.espejo_mesa?.nota || "Espejo en calibración — se entrena cada 24h con las aprobaciones reales."}
                          </div>
                        )}
                        {techo.espejo_mesa?.sugerir_codeudor && (
                          <div data-testid="techo-sugerir-codeudor" style={{ color: "#e7cf7a", fontSize: "0.7rem", marginTop: 6, fontWeight: 700 }}>
                            💡 DashAI: para esta renta la MESA suele exigir <u>Incorporar Codeudor</u>
                          </div>
                        )}
                      </div>
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                      {techo.escenarios.map((e, i) => {
                        const esMejor = techo.mejor_escenario && e.banco === techo.mejor_escenario.banco && e.credito_maximo_uf === techo.mejor_escenario.credito_maximo_uf;
                        return (
                          <div key={i} data-testid={`techo-escenario-${e.banco.split(" ")[0].toLowerCase()}`}
                            style={{ border: `1px solid ${esMejor ? "rgba(212,175,55,0.6)" : "rgba(255,255,255,0.12)"}`, padding: "1rem 1.1rem", background: esMejor ? "rgba(212,175,55,0.05)" : "transparent" }}>
                            <div style={{ color: "#cbd5e1", fontSize: "0.72rem", letterSpacing: "0.1em", textTransform: "uppercase" }}>{e.banco}</div>
                            <div className={esMejor ? "shimmer-oro" : ""} style={{ marginTop: 8, padding: "0.5rem 0.7rem", display: "inline-block",
                              backgroundImage: "linear-gradient(135deg, #BF953F, #FCF6BA 45%, #B38728, #FBF5B7 80%, #AA771C)",
                              color: "#0a0a0a", fontWeight: 900, fontSize: "1.35rem", letterSpacing: "-0.01em" }}>
                              {e.credito_maximo_uf.toLocaleString("es-CL")} UF
                            </div>
                            <div style={{ color: "#94a3b8", fontSize: "0.72rem", marginTop: 8, lineHeight: 1.7 }}>
                              Dividendo máx: ${e.dividendo_maximo_clp.toLocaleString("es-CL")}<br />
                              Carga máx {e.carga_max_pct}% · Div/Renta {e.div_renta_max_pct}%<br />
                              <span style={{ color: "#e7cf7a" }}>Tope activo: {e.restriccion_activa}</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    <div style={{ color: "#6b6b6b", fontSize: "0.68rem", marginTop: 14, lineHeight: 1.6 }}>
                      Simulación inversa DashAI sobre los documentos reales, según los topes vigentes de la Constitución. Referencial: la MESA confirma el monto final.
                    </div>
                  </>
                )}
              </div>
            </div>
          )}
          {finOpenId === currentFolder.id && (
            <div data-testid={`fin-detail-panel`} style={{ background: "rgba(212,175,55,0.08)", border: "1px solid #d4af37", borderRadius: 0, padding: "0.9rem", marginBottom: "0.8rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
                <h5 style={{ margin: 0, color: "#b8942e" }}>
                  <i className="fa fa-dollar" /> Datos financieros del cliente
                  <span style={{ marginLeft: 10, fontSize: 11, fontWeight: 400, opacity: 0.7 }}>
                    UF: ${ufValue.toLocaleString('es-CL')}
                  </span>
                </h5>
                <div style={{ display: "flex", gap: 6 }}>
                  <button className="docs-btn secondary" onClick={() => runOcrFin(currentFolder.id)} disabled={ocrRunning || finSaving} style={{ background: "#1e46c0", color: "#fff", border: "none", padding: "0.35rem 0.7rem", fontSize: 12 }}>
                    <i className="fa fa-magic" /> {ocrRunning ? "Leyendo PDFs..." : "Autodetectar con IA"}
                  </button>
                  <button className="docs-btn primary" onClick={() => saveFinPanel(currentFolder.id)} disabled={finSaving} style={{ padding: "0.35rem 0.7rem", fontSize: 12 }}>
                    <i className={`fa ${finSaving ? "fa-spinner fa-spin" : "fa-save"}`} /> Guardar
                  </button>
                </div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "0.5rem" }}>
                {currentFolder.source_email && (() => {
                  const m = currentFolder.source_email.match(/^\s*(.*?)\s*<([^>]+)>\s*$/);
                  const nm = m ? m[1].replace(/"/g, "").trim() : "";
                  const ad = m ? m[2].trim() : (currentFolder.source_email.includes("@") ? currentFolder.source_email.trim() : "");
                  const disp = nm ? `${nm} <${ad}>` : ad;
                  return (
                    <div data-testid="fin-origen" style={{ gridColumn: "1 / -1", background: "#dbeafe", border: "1px solid #d4af37", borderRadius: 0, padding: "0.5rem 0.7rem", fontSize: 12 }}>
                      <b style={{ color: "#1e3a8a" }}>📧 Origen de la solicitud:</b> <span style={{ color: "#b8942e", fontFamily: "monospace" }}>{disp}</span>
                    </div>
                  );
                })()}
                <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}><b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Inmobiliaria</b>
                  <input type="text" value={finDraft.inmobiliaria || ""} onChange={(e) => setFinDraft({ ...finDraft, inmobiliaria: e.target.value })} style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, border: "1px solid #94a3b8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }} />
                </label>
                <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}><b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Proyecto</b>
                  <input type="text" value={finDraft.proyecto || ""} onChange={(e) => setFinDraft({ ...finDraft, proyecto: e.target.value })} style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, border: "1px solid #94a3b8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }} />
                </label>
                <label style={{ fontSize: 12, gridColumn: "1 / -1", color: "#be123c", fontWeight: 700 }}><b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Tipo de operación</b>
                  <select value={finDraft.con_subsidio ? "con" : "sin"} onChange={(e) => setFinDraft({ ...finDraft, con_subsidio: e.target.value === "con" })} style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, border: "1px solid #94a3b8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }}>
                    <option value="con">CON subsidio (DS1 / DS19)</option>
                    <option value="sin">SIN subsidio</option>
                  </select>
                </label>
                {finDraft.con_subsidio && (
                  <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}><b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Resolución SERVIU</b>
                    <select data-testid="fin-resolucion-serviu" value={finDraft.resolucion_serviu ? "con" : "sin"} onChange={(e) => setFinDraft({ ...finDraft, resolucion_serviu: e.target.value === "con" })} style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, border: "1px solid #94a3b8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }}>
                      <option value="con">CON resolución SERVIU</option>
                      <option value="sin">SIN resolución SERVIU</option>
                    </select>
                  </label>
                )}
                <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}><b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Vivienda</b>
                  <select data-testid="fin-tipo-vivienda" value={finDraft.tipo_vivienda || "nueva"} onChange={(e) => setFinDraft({ ...finDraft, tipo_vivienda: e.target.value })} style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, border: "1px solid #94a3b8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }}>
                    <option value="nueva">Vivienda nueva</option>
                    <option value="usada">Vivienda usada</option>
                  </select>
                </label>
                <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}><b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Tipo propiedad</b>
                  <select value={finDraft.tipo_propiedad || ""} onChange={(e) => setFinDraft({ ...finDraft, tipo_propiedad: e.target.value })} style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, border: "1px solid #94a3b8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }}>
                    <option value="">— seleccionar —</option>
                    <option value="Departamento">Departamento</option>
                    <option value="Casa">Casa</option>
                    <option value="Terreno">Terreno</option>
                    <option value="Oficina">Oficina</option>
                    <option value="Estacionamiento">Estacionamiento</option>
                    <option value="Bodega">Bodega</option>
                  </select>
                </label>
                <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}><b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Fecha de entrega</b>
                  <select value={finDraft.fecha_entrega || ""} onChange={(e) => setFinDraft({ ...finDraft, fecha_entrega: e.target.value })} data-testid="fin-fecha-entrega-detail" style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, border: "1px solid #94a3b8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }}>
                    <option value="">— seleccionar —</option>
                    <option value="inmediata">Inmediata</option>
                    <option value="futura">Futura</option>
                  </select>
                </label>
                <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}><b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Valor propiedad (UF)</b>
                  <input type="number" step="0.01" value={finDraft.valor_propiedad || ""} onChange={(e) => setFinDraft({ ...finDraft, valor_propiedad: e.target.value })} style={{ width: "100%", padding: "0.35rem", borderRadius: 0, border: "1px solid #d4d4d8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }} />
                </label>
                {finDraft.con_subsidio && (
                  <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}><b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Subsidio (UF)</b>
                    <input type="number" step="0.01" value={finDraft.monto_subsidio || ""} onChange={(e) => setFinDraft({ ...finDraft, monto_subsidio: e.target.value })} style={{ width: "100%", padding: "0.35rem", borderRadius: 0, border: "1px solid #d4d4d8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }} />
                  </label>
                )}
                {finDraft.con_subsidio && (
                  <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}><b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Ahorro (UF)</b>
                    <input type="number" step="0.01" value={finDraft.ahorro || ""} onChange={(e) => setFinDraft({ ...finDraft, ahorro: e.target.value })} style={{ width: "100%", padding: "0.35rem", borderRadius: 0, border: "1px solid #d4d4d8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }} />
                  </label>
                )}
                {!finDraft.con_subsidio && (
                  <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}><b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Pie (UF)</b>
                    <input type="number" step="0.01" value={finDraft.monto_pie || ""} onChange={(e) => setFinDraft({ ...finDraft, monto_pie: e.target.value })} style={{ width: "100%", padding: "0.35rem", borderRadius: 0, border: "1px solid #d4d4d8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }} />
                  </label>
                )}
                <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}><b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Monto crédito (UF)</b>
                  <input type="number" step="0.01" value={finDraft.monto_credito || ""} onChange={(e) => setFinDraft({ ...finDraft, monto_credito: e.target.value })} style={{ width: "100%", padding: "0.35rem", borderRadius: 0, border: "1px solid #d4d4d8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }} />
                </label>
                <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}><b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Reserva (UF)</b>
                  <input type="number" step="0.01" value={finDraft.monto_reserva || ""} onChange={(e) => setFinDraft({ ...finDraft, monto_reserva: e.target.value })} style={{ width: "100%", padding: "0.35rem", borderRadius: 0, border: "1px solid #d4d4d8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }} />
                </label>
              </div>
              <div style={{ marginTop: 10 }}>
                <ConversorUF style={{ background: "#fefce8", border: "1px solid #d4af37", color: "#1a1f2e" }} />
              </div>
              {(() => {
                const vp = Number(finDraft.valor_propiedad || 0);
                const ms = Number(finDraft.monto_subsidio || 0);
                const ah = Number(finDraft.ahorro || 0);
                const rs = Number(finDraft.monto_reserva || 0);
                const mp = Number(finDraft.monto_pie || 0);
                const mc = Number(finDraft.monto_credito || 0);
                const suma = finDraft.con_subsidio ? (ms + ah + rs + mc) : (mp + rs + mc);
                const diff = vp - suma;
                if (vp === 0 || suma === 0) return null;
                const ok = Math.abs(diff) < 1;
                // Regla 80% SIN subsidio: crédito no puede exceder 80% del valor propiedad
                const max80 = vp * 0.8;
                const excedeMax = !finDraft.con_subsidio && mc > 0 && mc > max80 + 0.01;
                const pctCredito = vp > 0 ? (mc / vp) * 100 : 0;
                return (
                  <div style={{ marginTop: 8, display: "grid", gap: 6 }}>
                    <div style={{ padding: "0.7rem 0.9rem", borderRadius: 0, background: ok ? "#dcfce7" : "#fee2e2", color: ok ? "#166534" : "#991b1b", fontSize: 14.5, fontWeight: 700, lineHeight: 1.45 }}>
                      {ok
                        ? `✅ Suma cuadra: ${suma.toFixed(2)} UF = ${vp.toFixed(2)} UF`
                        : `⚠️ Diferencia: ${diff.toFixed(2)} UF (suma actual: ${suma.toFixed(2)} vs valor propiedad: ${vp.toFixed(2)}). ${finDraft.con_subsidio ? 'Subsidio + Ahorro + Reserva + Crédito' : 'Pie + Reserva + Crédito'} debe = Valor propiedad.`}
                    </div>
                    {!finDraft.con_subsidio && mc > 0 && (
                      <div style={{ padding: "0.6rem 0.8rem", borderRadius: 0, background: excedeMax ? "#fee2e2" : "#e0f2fe", color: excedeMax ? "#991b1b" : "#075985", fontSize: 13.5, fontWeight: 600, lineHeight: 1.45 }}>
                        {excedeMax
                          ? `🚫 Crédito ${mc.toFixed(2)} UF supera el 80% máximo (${max80.toFixed(2)} UF) — SIN subsidio no permite más del 80% del valor propiedad. Actual: ${pctCredito.toFixed(1)}%.`
                          : `📊 Crédito representa ${pctCredito.toFixed(1)}% del valor propiedad (máximo permitido SIN subsidio: 80% = ${max80.toFixed(2)} UF).`}
                      </div>
                    )}
                  </div>
                );
              })()}
              <div style={{ marginTop: 8, fontSize: 11, opacity: 0.75 }}>
                💡 Si dejaste campos vacíos, hacé click en "Autodetectar con IA" para que Claude lea los PDFs adjuntos y complete lo que pueda.
              </div>
            </div>
          )}

          {currentFolder.codeudor_nombre && (
            <div className="clientes-codeudor-badge">
              <i className="fa fa-user-plus"></i> Codeudor: {currentFolder.codeudor_nombre} {currentFolder.codeudor_rut && `(${currentFolder.codeudor_rut})`}
            </div>
          )}

          <div className="clientes-files-list">
            {(!currentFolder.archivos || currentFolder.archivos.length === 0) && (
              <div className="clientes-empty">
                <i className="fa fa-file-o"></i>
                <p>Carpeta vacía. Use "Buscar Adjuntos" para traer archivos del correo.</p>
              </div>
            )}
            {(() => {
              const esCod = (a) => a.subfolder === "05_codeudor" || /^CODEUDOR_/i.test(a.nombre || "");
              const esEstudio = (a) => (a.subfolder || "").startsWith("07_estudio_titulo");
              const titularFiles = (currentFolder.archivos || []).filter(a => !esCod(a) && !esEstudio(a));
              const codFiles = (currentFolder.archivos || []).filter(esCod);
              const estudioFiles = (currentFolder.archivos || []).filter(a => esEstudio(a) && !esCod(a));
              const renderFile = (file, i) => (
              <div key={file.ruta || i} className="clientes-file-item" data-testid={`file-${i}`}>
                <i className={`fa ${file.nombre.endsWith('.pdf') ? 'fa-file-pdf-o' : file.nombre.match(/\.(jpg|png|jpeg)$/i) ? 'fa-file-image-o' : file.nombre.match(/\.(doc|docx)$/i) ? 'fa-file-word-o' : 'fa-file-o'}`}></i>
                <div className="clientes-file-info">
                  <span className="clientes-file-name">{file.nombre}</span>
                  {file.protegido && (
                    <span data-testid={`file-protegido-${i}`} title="Este documento tiene clave y no puede abrirse sin ella"
                      style={{ marginLeft: 6, fontSize: 10.5, fontWeight: 800, color: "#b45309",
                        border: "1px solid #f59e0b", background: "rgba(245,158,11,0.12)",
                        padding: "1px 7px", whiteSpace: "nowrap" }}>
                      🔒 Protegido — requiere clave
                    </span>
                  )}
                  {file.subfolder && <span className="clientes-file-subfolder">{file.subfolder}/</span>}
                  <span className="clientes-file-size">{formatSize(file.tamano)}</span>
                </div>
                <button
                  className="docs-btn secondary"
                  title="Ver / Preview"
                  onClick={() => openPreview(currentFolder.id, file.ruta, file.nombre)}
                  data-testid={`btn-preview-${i}`}
                  style={{ marginRight: 6 }}
                >
                  <i className="fa fa-eye"></i>
                </button>
                <button className="docs-btn secondary" title="Descargar" onClick={() => downloadFile(currentFolder.id, file.ruta)} data-testid={`btn-download-${i}`}>
                  <i className="fa fa-download"></i>
                </button>
                <button
                  className="docs-btn secondary"
                  title="Eliminar archivo"
                  data-testid={`btn-delete-file-${i}`}
                  onClick={async () => {
                    await deleteClientFile(currentFolder.id, file.ruta);
                    const r = await axios.get(`${API}/api/clientes/folders/${currentFolder.id}`);
                    setCurrentFolder(r.data);
                  }}
                  style={{ marginLeft: 6, color: "#be123c", borderColor: "#be123c" }}
                >
                  <i className="fa fa-trash"></i>
                </button>
              </div>
              );
              return (
                <>
                  {titularFiles.map(renderFile)}
                  {codFiles.length > 0 && (
                    <div data-testid="codeudor-subfolder" style={{ marginTop: 14, border: "1.5px dashed #2e5ce6", borderRadius: 0, padding: "10px 12px", background: "rgba(46,92,230,0.06)" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, color: "#1e46c0", fontWeight: 800, fontSize: 13 }}>
                        <i className="fa fa-folder"></i> Subcarpeta Codeudor{currentFolder.codeudor_nombre ? `: ${currentFolder.codeudor_nombre}` : ""}
                        <span style={{ fontWeight: 600, opacity: 0.7 }}>({codFiles.length} archivo{codFiles.length !== 1 ? "s" : ""})</span>
                      </div>
                      {codFiles.map((f2, j) => renderFile(f2, titularFiles.length + j))}
                    </div>
                  )}
                  {estudioFiles.length > 0 && (
                    <div data-testid="estudio-subfolder" style={{ marginTop: 14, border: "1.5px dashed #14b8a6", borderRadius: 0, padding: "10px 12px", background: "rgba(20,184,166,0.06)" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4, color: "#0d9488", fontWeight: 800, fontSize: 13 }}>
                        <i className="fa fa-balance-scale"></i> Carpeta Estudio de Título (separada)
                        <span style={{ fontWeight: 600, opacity: 0.7 }}>({estudioFiles.length} archivo{estudioFiles.length !== 1 ? "s" : ""})</span>
                      </div>
                      <div style={{ fontSize: 11, color: "#5eead4", marginBottom: 8 }}>
                        🔒 Regla inviolable: estos documentos pertenecen al Estudio de Título de la propiedad y NUNCA se combinan ni se envían con la solicitud de crédito.
                      </div>
                      {estudioFiles.map((f2, j) => renderFile(f2, titularFiles.length + codFiles.length + j))}
                    </div>
                  )}
                </>
              );
            })()}
          </div>
        </div>
  );
}
