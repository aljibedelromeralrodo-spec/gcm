import ConversorUF from "../../components/ConversorUF";
import UFAmountInput from "./UFAmountInput";
import { useClientes } from "./clientesCtx";

export default function ClientesAjustes() {
  const {
    agregarCodeudor,
    ajustes,
    cancelEdit,
    clearSelection,
    closeFinPanel,
    deleteClientFile,
    downloadFile,
    editDraft,
    editingId,
    finDraft,
    finOpenId,
    finSaving,
    isSelected,
    loadAjustes,
    mergeByProtocol,
    mergeSelected,
    merging,
    mergingProto,
    ocrRunning,
    openEmailModal,
    openFinPanel,
    openPreview,
    resetEdit,
    runOcrFin,
    saveEdit,
    saveFinPanel,
    savingEdit,
    selectionCount,
    setEditDraft,
    setFinDraft,
    setView,
    splitBundled,
    splittingRel,
    startEdit,
    toggleSelect,
    triggerUpload,
    ufValue,
    updateUf,
    uploadingFor,
    view
  } = useClientes();
  return (
        <div data-testid="clientes-ajustes">
          <div className="clientes-detail-header">
            <button className="docs-btn secondary" onClick={() => setView("list")}>
              <i className="fa fa-arrow-left"></i> Volver
            </button>
            <h3><i className="fa fa-sliders"></i> Ajustes — Clasificación de Solicitudes de Crédito</h3>
            <button className="docs-btn secondary" onClick={updateUf} data-testid="btn-uf-update" title="Valor actual de la UF"
              style={{ background: "rgba(250,204,21,0.15)", border: "1px solid rgba(250,204,21,0.5)", color: "#facc15" }}>
              <i className="fa fa-line-chart"></i> UF: ${ufValue.toLocaleString('es-CL')}
            </button>
            <button className="docs-btn secondary" onClick={loadAjustes}>
              <i className="fa fa-refresh"></i> Refrescar
            </button>
          </div>
          <div style={{ padding: "1rem", background: "rgba(212,175,55,0.08)", border: "1px solid #d4af37", borderRadius: 0, marginBottom: "1rem", fontSize: "0.88rem", lineHeight: 1.6 }}>
            <b>Reglas activas:</b><br/>
            Un correo se clasifica como <b>solicitud de crédito</b> si menciona «solicitud de crédito/financiamiento» O trae ≥3 documentos típicos (cédula, liquidaciones, AFP, CMF, impuesto renta, boletas honorarios).<br/>
            <b>Tipo cliente</b>: dependiente (liquidación+AFP) · independiente (impuesto renta+boletas).<br/>
            <b>Subsidio</b>: si no dice nada → sin subsidio, LTV 80% del valor propiedad.<br/>
            <b>Codeudor</b>: detectado por keyword "codeudor/aval" en asunto o cuerpo → subcarpeta con su nombre.<br/>
            <b>Estructura</b>: cada carpeta cliente tiene subcarpetas ordenadas (01_cedula, 02_liquidaciones o 02_impuesto_renta, 03_afp o 03_boletas..., 04_cmf, 99_otros).
          </div>
          {ajustes.length === 0 ? (
            <div className="clientes-empty">
              <i className="fa fa-inbox"></i>
              <p>Todavía no hay solicitudes clasificadas. Cuando el módulo <b>Procesamiento Correo</b> archive un correo con «Guardar en Carpeta Cliente», aparecerá acá.</p>
            </div>
          ) : (
            <div style={{ display: "grid", gap: "0.8rem" }}>
              {ajustes.map(f => {
                const cr = f.credit_request || {};
                const sub = cr.subsidy || {};
                const cod = cr.codeudor || {};
                const isEditing = editingId === f.id;
                return (
                  <div key={f.id} className="clientes-card" style={{ padding: "1rem", flexDirection: "column", alignItems: "stretch", borderLeft: cr.manual_override ? "3px solid #2e5ce6" : "" }} data-testid={`ajuste-${f.id}`}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem", gap: "0.5rem", flexWrap: "wrap" }}>
                      <h4 style={{ margin: 0 }}>
                        <i className="fa fa-user"></i> {f.nombre}
                        {f.rut && <small style={{ opacity: 0.6 }}> ({f.rut})</small>}
                        {cr.manual_override && (
                          <span data-testid={`manual-badge-${f.id}`} style={{ background: "#ede9fe", color: "#6d28d9", padding: "2px 8px", borderRadius: 0, fontSize: 11, fontWeight: 700, marginLeft: 8 }}>
                            <i className="fa fa-pencil" style={{ marginRight: 4 }} />editado manualmente
                          </span>
                        )}
                      </h4>
                      {!isEditing && (
                        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                          <span style={{ background: cr.is_request ? "#dcfce7" : "#fee2e2", color: cr.is_request ? "#166534" : "#991b1b", padding: "2px 8px", borderRadius: 0, fontSize: 12, fontWeight: 700 }}>
                            {cr.is_request ? "✓ Solicitud" : "✗ No"}
                          </span>
                          <span style={{ background: "#fef3c7", color: "#92400e", padding: "2px 8px", borderRadius: 0, fontSize: 12 }}>{cr.client_type || "?"}</span>
                          <span style={{ background: "#e0e7ff", color: "#3730a3", padding: "2px 8px", borderRadius: 0, fontSize: 12 }}>{sub.tipo || "?"}</span>
                          {cod.has_codeudor && <span style={{ background: "#fce7f3", color: "#9d174d", padding: "2px 8px", borderRadius: 0, fontSize: 12 }}>+ codeudor {cod.name || "s/n"}</span>}
                          <button className="docs-btn secondary" style={{ padding: "0.3rem 0.6rem", fontSize: 12 }} onClick={() => startEdit(f)} data-testid={`btn-edit-${f.id}`}>
                            <i className="fa fa-pencil" /> Editar
                          </button>
                          <button className="docs-btn secondary" style={{ padding: "0.3rem 0.6rem", fontSize: 12, background: "#d4af37", color: "#fff", border: "none" }} onClick={() => openFinPanel(f)} data-testid={`btn-fin-${f.id}`}>
                            <i className="fa fa-dollar" /> Datos financieros
                          </button>
                          {cr.manual_override && (
                            <button className="docs-btn secondary" style={{ padding: "0.3rem 0.6rem", fontSize: 12, color: "#e11d48" }} onClick={() => resetEdit(f.id)} data-testid={`btn-reset-${f.id}`}>
                              <i className="fa fa-undo" /> Volver a auto
                            </button>
                          )}
                        </div>
                      )}
                    </div>

                    {isEditing && (
                      <div data-testid={`edit-form-${f.id}`} style={{ background: "rgba(46,92,230,0.08)", border: "1px solid #2e5ce6", borderRadius: 0, padding: "0.9rem", marginBottom: "0.6rem", display: "grid", gap: "0.7rem", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
                        <label style={{ fontSize: 12 }}>
                          <b style={{ display: "block", marginBottom: 4 }}>¿Es solicitud?</b>
                          <select value={editDraft.is_request ? "si" : "no"} onChange={(e) => setEditDraft({ ...editDraft, is_request: e.target.value === "si" })} data-testid={`edit-is-request-${f.id}`} style={{ width: "100%", padding: "0.35rem", borderRadius: 0, border: "1px solid #d4d4d8" }}>
                            <option value="si">Sí, es solicitud</option>
                            <option value="no">No es solicitud</option>
                          </select>
                        </label>
                        <label style={{ fontSize: 12 }}>
                          <b style={{ display: "block", marginBottom: 4 }}>Tipo de cliente</b>
                          <select value={editDraft.client_type} onChange={(e) => setEditDraft({ ...editDraft, client_type: e.target.value })} data-testid={`edit-client-type-${f.id}`} style={{ width: "100%", padding: "0.35rem", borderRadius: 0, border: "1px solid #d4d4d8" }}>
                            <option value="dependiente">Dependiente (liquidación + AFP)</option>
                            <option value="independiente">Independiente (impuesto renta + boletas)</option>
                            <option value="desconocido">Desconocido / Por revisar</option>
                          </select>
                        </label>
                        <label style={{ fontSize: 12 }}>
                          <b style={{ display: "block", marginBottom: 4 }}>Subsidio</b>
                          <select value={editDraft.subsidy_tipo} onChange={(e) => setEditDraft({ ...editDraft, subsidy_tipo: e.target.value })} data-testid={`edit-subsidy-${f.id}`} style={{ width: "100%", padding: "0.35rem", borderRadius: 0, border: "1px solid #d4d4d8" }}>
                            <option value="con_subsidio">Con subsidio (DS1 / DS19)</option>
                            <option value="sin_subsidio">Sin subsidio</option>
                          </select>
                        </label>
                        <label style={{ fontSize: 12 }}>
                          <b style={{ display: "block", marginBottom: 4 }}>Codeudor</b>
                          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                            <input type="checkbox" checked={!!editDraft.codeudor_has} onChange={(e) => setEditDraft({ ...editDraft, codeudor_has: e.target.checked })} data-testid={`edit-codeudor-has-${f.id}`} />
                            <input type="text" placeholder="Nombre codeudor" value={editDraft.codeudor_name || ""} onChange={(e) => setEditDraft({ ...editDraft, codeudor_name: e.target.value, codeudor_has: true })} data-testid={`edit-codeudor-name-${f.id}`} style={{ flex: 1, padding: "0.35rem", borderRadius: 0, border: "1px solid #d4d4d8", fontSize: 12 }} />
                          </div>
                        </label>
                        <div style={{ gridColumn: "1 / -1", display: "flex", gap: 8, justifyContent: "flex-end" }}>
                          <button className="docs-btn secondary" onClick={cancelEdit} data-testid={`btn-cancel-${f.id}`} disabled={savingEdit}>
                            <i className="fa fa-times" /> Cancelar
                          </button>
                          <button className="docs-btn" style={{ background: "#2e5ce6", color: "#fff" }} onClick={() => saveEdit(f.id)} data-testid={`btn-save-${f.id}`} disabled={savingEdit}>
                            <i className="fa fa-check" /> {savingEdit ? "Guardando..." : "Guardar"}
                          </button>
                        </div>
                      </div>
                    )}

                    <div style={{ fontSize: 12, opacity: 0.75, marginBottom: "0.5rem" }}>
                      docs detectados: {(cr.doc_categories || []).join(", ") || "ninguno"} · matched: {cr.matched_keyword || "—"}
                    </div>

                    {/* ARCHIVOS TOOLBAR */}
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 6, padding: "0.4rem 0.6rem", background: "rgba(14,14,16,0.4)", borderRadius: 0, border: "1px solid rgba(148,163,184,0.15)" }}>
                      <span style={{ fontSize: 12, opacity: 0.85, marginRight: "auto", alignSelf: "center" }}>
                        <i className="fa fa-files-o" /> Archivos {selectionCount(f.id) > 0 && <span style={{ color: "#facc15" }}>· {selectionCount(f.id)} seleccionados</span>}
                      </span>
                      <button
                        onClick={() => triggerUpload(f.id, "")}
                        data-testid={`btn-upload-file-${f.id}`}
                        disabled={uploadingFor === f.id}
                        style={{ background: "rgba(16,217,142,0.15)", border: "1px solid rgba(16,217,142,0.5)", color: "#34eab9", borderRadius: 0, padding: "4px 10px", cursor: "pointer", fontSize: 12 }}
                        title="Subir archivo manualmente"
                      >
                        <i className={`fa ${uploadingFor === f.id ? "fa-spinner fa-spin" : "fa-plus"}`} /> Agregar archivo
                      </button>
                      <button
                        onClick={() => agregarCodeudor(f)}
                        data-testid={`btn-agregar-codeudor-${f.id}`}
                        style={{ background: "rgba(251,146,60,0.15)", border: "1px solid rgba(251,146,60,0.5)", color: "#fdba74", borderRadius: 0, padding: "4px 10px", cursor: "pointer", fontSize: 12 }}
                        title="Crear subcarpeta del codeudor y subir sus archivos"
                      >
                        <i className="fa fa-user-plus" /> Agregar Codeudor
                      </button>
                      <button
                        onClick={() => mergeByProtocol(f)}
                        data-testid={`btn-merge-proto-${f.id}`}
                        disabled={mergingProto === f.id}
                        style={{ background: "rgba(250,204,21,0.15)", border: "1px solid rgba(250,204,21,0.5)", color: "#facc15", borderRadius: 0, padding: "4px 10px", cursor: "pointer", fontSize: 12, fontWeight: 600 }}
                        title="Combinar TODOS los archivos siguiendo el orden del protocolo"
                      >
                        <i className={`fa ${mergingProto === f.id ? "fa-spinner fa-spin" : "fa-list-ol"}`} /> Combinar por Protocolo
                      </button>
                      <button
                        onClick={() => mergeSelected(f.id)}
                        data-testid={`btn-merge-${f.id}`}
                        disabled={merging || selectionCount(f.id) < 1}
                        style={{ background: "rgba(46,92,230,0.15)", border: "1px solid rgba(46,92,230,0.5)", color: "#c084fc", borderRadius: 0, padding: "4px 10px", cursor: selectionCount(f.id) < 1 ? "not-allowed" : "pointer", opacity: selectionCount(f.id) < 1 ? 0.5 : 1, fontSize: 12 }}
                        title="Combinar PDFs seleccionados en un único archivo"
                      >
                        <i className={`fa ${merging ? "fa-spinner fa-spin" : "fa-object-group"}`} /> Combinar PDFs
                      </button>
                      <button
                        onClick={() => openEmailModal(f)}
                        data-testid={`btn-send-email-${f.id}`}
                        style={{ background: "rgba(212,175,55,0.18)", border: "1px solid rgba(212,175,55,0.5)", color: "#d4af37", borderRadius: 0, padding: "4px 10px", cursor: "pointer", fontSize: 12 }}
                        title="Generar y enviar correo con antecedentes"
                      >
                        <i className="fa fa-paper-plane" /> Enviar correo
                      </button>
                      {selectionCount(f.id) > 0 && (
                        <button
                          onClick={() => clearSelection(f.id)}
                          style={{ background: "transparent", border: "1px solid rgba(148,163,184,0.3)", color: "#94a3b8", borderRadius: 0, padding: "4px 10px", cursor: "pointer", fontSize: 11 }}
                          title="Limpiar selección"
                        >
                          <i className="fa fa-times" /> Limpiar
                        </button>
                      )}
                    </div>

                    {finOpenId === f.id && (
                      <div data-testid={`fin-panel-${f.id}`} style={{ background: "rgba(212,175,55,0.08)", border: "1px solid #d4af37", borderRadius: 0, padding: "0.9rem", marginBottom: "0.6rem" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem" }}>
                          <h5 style={{ margin: 0, color: "#b8942e" }}><i className="fa fa-dollar" /> Datos financieros del cliente</h5>
                          <div style={{ display: "flex", gap: 6 }}>
                            <button className="docs-btn secondary" onClick={() => runOcrFin(f.id)} data-testid={`btn-ocr-${f.id}`} disabled={ocrRunning || finSaving} style={{ background: "#1e46c0", color: "#fff", border: "none", padding: "0.35rem 0.7rem", fontSize: 12 }}>
                              <i className="fa fa-magic" /> {ocrRunning ? "Leyendo PDFs..." : "Leer con OCR"}
                            </button>
                            <button className="docs-btn secondary" onClick={closeFinPanel} disabled={ocrRunning || finSaving} style={{ padding: "0.35rem 0.7rem", fontSize: 12 }}>Cerrar</button>
                          </div>
                        </div>
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "0.5rem" }}>
                          <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}>
                            <b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Cliente</b>
                            <input type="text" value={f.nombre} readOnly style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, background: "#f1f5f9", border: "1px solid #94a3b8", fontSize: 13, color: "#000", fontWeight: 600 }} />
                          </label>
                          <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}>
                            <b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>RUT</b>
                            <input type="text" value={f.rut || ""} readOnly style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, background: "#f1f5f9", border: "1px solid #94a3b8", fontSize: 13, color: "#000", fontWeight: 600 }} />
                          </label>
                          <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}>
                            <b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Proyecto</b>
                            <input type="text" value={finDraft.proyecto || ""} onChange={(e) => setFinDraft({ ...finDraft, proyecto: e.target.value })} data-testid={`fin-proyecto-${f.id}`} style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, border: "1px solid #94a3b8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }} />
                          </label>
                          <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}>
                            <b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Inmobiliaria</b>
                            <input type="text" value={finDraft.inmobiliaria || ""} onChange={(e) => setFinDraft({ ...finDraft, inmobiliaria: e.target.value })} data-testid={`fin-inmobiliaria-${f.id}`} style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, border: "1px solid #94a3b8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }} />
                          </label>
                          <label style={{ fontSize: 12, gridColumn: "1 / -1", color: "#be123c", fontWeight: 700 }}>
                            <b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Tipo de operación</b>
                            <select value={finDraft.con_subsidio ? "con" : "sin"} onChange={(e) => setFinDraft({ ...finDraft, con_subsidio: e.target.value === "con" })} data-testid={`fin-subsidy-${f.id}`} style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, border: "1px solid #94a3b8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }}>
                              <option value="con">CON subsidio (DS1 / DS19)</option>
                              <option value="sin">SIN subsidio</option>
                            </select>
                          </label>
                          <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}>
                            <b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Tipo propiedad</b>
                            <select value={finDraft.tipo_propiedad || ""} onChange={(e) => setFinDraft({ ...finDraft, tipo_propiedad: e.target.value })} data-testid={`fin-tipo-prop-${f.id}`} style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, border: "1px solid #94a3b8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }}>
                              <option value="">— seleccioná —</option>
                              <option value="Departamento">Departamento</option>
                              <option value="Casa">Casa</option>
                              <option value="Terreno">Terreno</option>
                              <option value="Oficina">Oficina</option>
                              <option value="Estacionamiento">Estacionamiento</option>
                              <option value="Bodega">Bodega</option>
                            </select>
                          </label>
                          <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}>
                            <b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Fecha de entrega</b>
                            <select value={finDraft.fecha_entrega || ""} onChange={(e) => setFinDraft({ ...finDraft, fecha_entrega: e.target.value })} data-testid={`fin-fecha-entrega-${f.id}`} style={{ width: "100%", padding: "0.4rem 0.5rem", borderRadius: 0, border: "1px solid #94a3b8", fontSize: 13, color: "#000", fontWeight: 600, background: "#fff" }}>
                              <option value="">— seleccioná —</option>
                              <option value="inmediata">Inmediata</option>
                              <option value="futura">Futura</option>
                            </select>
                          </label>
                          <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}>
                            <b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Valor propiedad (UF)</b>
                            <UFAmountInput value={finDraft.valor_propiedad} onChange={(v) => setFinDraft({ ...finDraft, valor_propiedad: v })} uf={ufValue} dataTestid={`fin-valor-${f.id}`} />
                          </label>
                          {finDraft.con_subsidio && (
                            <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}>
                              <b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Monto subsidio (UF)</b>
                              <UFAmountInput value={finDraft.monto_subsidio} onChange={(v) => setFinDraft({ ...finDraft, monto_subsidio: v })} uf={ufValue} dataTestid={`fin-subsidio-${f.id}`} />
                            </label>
                          )}
                          {finDraft.con_subsidio && (
                            <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}>
                              <b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Ahorro (UF)</b>
                              <UFAmountInput value={finDraft.ahorro} onChange={(v) => setFinDraft({ ...finDraft, ahorro: v })} uf={ufValue} dataTestid={`fin-ahorro-${f.id}`} />
                            </label>
                          )}
                          {!finDraft.con_subsidio && (
                            <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}>
                              <b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Pie (UF)</b>
                              <UFAmountInput value={finDraft.monto_pie} onChange={(v) => setFinDraft({ ...finDraft, monto_pie: v })} uf={ufValue} dataTestid={`fin-pie-${f.id}`} />
                            </label>
                          )}
                          <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}>
                            <b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Monto del crédito (UF)</b>
                            <UFAmountInput value={finDraft.monto_credito} onChange={(v) => setFinDraft({ ...finDraft, monto_credito: v })} uf={ufValue} dataTestid={`fin-credito-${f.id}`} />
                          </label>
                          <label style={{ fontSize: 12, color: "#be123c", fontWeight: 700 }}>
                            <b style={{ display: "block", color: "#be123c", fontWeight: 800 }}>Reserva (UF)</b>
                            <UFAmountInput value={finDraft.monto_reserva} onChange={(v) => setFinDraft({ ...finDraft, monto_reserva: v })} uf={ufValue} dataTestid={`fin-reserva-${f.id}`} />
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
                          const max80 = vp * 0.8;
                          const excedeMax = !finDraft.con_subsidio && mc > 0 && mc > max80 + 0.01;
                          const pctCredito = vp > 0 ? (mc / vp) * 100 : 0;
                          return (
                            <div style={{ marginTop: 8, display: "grid", gap: 6 }}>
                              <div data-testid={`fin-sum-${f.id}`} style={{ padding: "0.7rem 0.9rem", borderRadius: 0, background: ok ? "#dcfce7" : "#fee2e2", color: ok ? "#166534" : "#991b1b", fontSize: 14.5, fontWeight: 700, lineHeight: 1.45 }}>
                                {ok
                                  ? `✅ Suma cuadra: ${suma.toFixed(2)} UF = ${vp.toFixed(2)} UF`
                                  : `⚠️ Diferencia: ${diff.toFixed(2)} UF (suma actual: ${suma.toFixed(2)} vs valor propiedad: ${vp.toFixed(2)}). ${finDraft.con_subsidio ? 'Subsidio + Ahorro + Reserva + Crédito' : 'Pie + Reserva + Crédito'} debe = Valor propiedad.`}
                              </div>
                              {!finDraft.con_subsidio && mc > 0 && (
                                <div data-testid={`fin-80pct-${f.id}`} style={{ padding: "0.6rem 0.8rem", borderRadius: 0, background: excedeMax ? "#fee2e2" : "#e0f2fe", color: excedeMax ? "#991b1b" : "#075985", fontSize: 13.5, fontWeight: 600, lineHeight: 1.45 }}>
                                  {excedeMax
                                    ? `🚫 Crédito ${mc.toFixed(2)} UF supera el 80% máximo (${max80.toFixed(2)} UF) — SIN subsidio no permite más del 80% del valor propiedad. Actual: ${pctCredito.toFixed(1)}%.`
                                    : `📊 Crédito representa ${pctCredito.toFixed(1)}% del valor propiedad (máximo permitido SIN subsidio: 80% = ${max80.toFixed(2)} UF).`}
                                </div>
                              )}
                            </div>
                          );
                        })()}
                        <div style={{ marginTop: "0.6rem", textAlign: "right" }}>
                          <button className="docs-btn" style={{ background: "#d4af37", color: "#fff", border: "none" }} onClick={() => saveFinPanel(f.id)} data-testid={`btn-fin-save-${f.id}`} disabled={finSaving || ocrRunning}>
                            <i className="fa fa-check" /> {finSaving ? "Guardando..." : "Guardar datos"}
                          </button>
                        </div>
                      </div>
                    )}
                    {(f.subfolders || []).map(s => (
                      <details key={s.name} style={{ background: "rgba(255,255,255,0.03)", borderRadius: 0, padding: "0.4rem 0.7rem", marginTop: 4 }}>
                        <summary style={{ cursor: "pointer", fontWeight: 600, fontSize: 13, display: "flex", alignItems: "center", gap: 6 }}>
                          <span><i className="fa fa-folder"></i> {s.name} ({s.files.length})</span>
                          <button
                            onClick={(e) => { e.preventDefault(); e.stopPropagation(); triggerUpload(f.id, s.name); }}
                            data-testid={`btn-upload-sub-${f.id}-${s.name}`}
                            style={{ marginLeft: "auto", background: "rgba(16,217,142,0.12)", border: "1px solid rgba(16,217,142,0.35)", color: "#34eab9", borderRadius: 0, padding: "1px 8px", cursor: "pointer", fontSize: 11 }}
                            title={`Subir archivo a ${s.name}`}
                          >
                            <i className="fa fa-plus" /> Aquí
                          </button>
                        </summary>
                        <ul style={{ margin: "0.4rem 0 0", paddingLeft: 8, fontSize: 12, listStyle: "none" }}>
                          {s.files.map(ff => {
                            const rel = `${s.name}/${ff.name}`;
                            const sel = isSelected(f.id, rel);
                            return (
                              <li key={ff.name} style={{ opacity: 0.9, display: "flex", alignItems: "center", gap: 6, padding: "3px 4px", background: sel ? "rgba(250,204,21,0.08)" : "transparent", borderRadius: 0 }}>
                                <input
                                  type="checkbox"
                                  checked={sel}
                                  onChange={() => toggleSelect(f.id, rel)}
                                  data-testid={`sel-${f.id}-${ff.name}`}
                                  style={{ cursor: "pointer", accentColor: "#facc15" }}
                                  title="Seleccionar para combinar / adjuntar"
                                />
                                <i className={`fa ${ff.name.toLowerCase().endsWith('.pdf') ? 'fa-file-pdf-o' : ff.name.match(/\.(jpg|png|jpeg|gif|webp)$/i) ? 'fa-file-image-o' : 'fa-file-o'}`} style={{ opacity: 0.7 }}></i>
                                <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{ff.name}</span>
                                <span style={{ opacity: 0.5, fontSize: 11 }}>{Math.round(ff.size / 1024)} KB</span>
                                <button
                                  title="Ver / Preview"
                                  onClick={() => openPreview(f.id, rel, ff.name)}
                                  data-testid={`aj-preview-${f.id}-${ff.name}`}
                                  style={{ background: "rgba(212,175,55,0.15)", border: "1px solid rgba(212,175,55,0.4)", color: "#d4af37", borderRadius: 0, padding: "2px 8px", cursor: "pointer", fontSize: 11 }}
                                >
                                  <i className="fa fa-eye"></i>
                                </button>
                                {ff.name.toLowerCase().endsWith(".pdf") && ff.size > 100000 && (
                                  <button
                                    title="Dividir PDF empaquetado por categoría (IA)"
                                    onClick={() => splitBundled(f.id, rel, ff.name)}
                                    disabled={splittingRel === rel}
                                    data-testid={`aj-split-${f.id}-${ff.name}`}
                                    style={{ background: "rgba(46,92,230,0.15)", border: "1px solid rgba(46,92,230,0.4)", color: "#c084fc", borderRadius: 0, padding: "2px 8px", cursor: "pointer", fontSize: 11 }}
                                  >
                                    <i className={`fa ${splittingRel === rel ? "fa-spinner fa-spin" : "fa-cut"}`}></i>
                                  </button>
                                )}
                                <button
                                  title="Descargar"
                                  onClick={() => downloadFile(f.id, rel)}
                                  data-testid={`aj-download-${f.id}-${ff.name}`}
                                  style={{ background: "rgba(148,163,184,0.15)", border: "1px solid rgba(148,163,184,0.4)", color: "#94a3b8", borderRadius: 0, padding: "2px 8px", cursor: "pointer", fontSize: 11 }}
                                >
                                  <i className="fa fa-download"></i>
                                </button>
                                <button
                                  title="Eliminar"
                                  onClick={() => deleteClientFile(f.id, rel)}
                                  data-testid={`aj-delete-${f.id}-${ff.name}`}
                                  style={{ background: "rgba(225,29,72,0.15)", border: "1px solid rgba(225,29,72,0.4)", color: "#fb7185", borderRadius: 0, padding: "2px 8px", cursor: "pointer", fontSize: 11 }}
                                >
                                  <i className="fa fa-trash"></i>
                                </button>
                              </li>
                            );
                          })}
                        </ul>
                      </details>
                    ))}
                  </div>
                );
              })}
            </div>
          )}
        </div>
  );
}
