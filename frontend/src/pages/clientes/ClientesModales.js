import DOMPurify from "dompurify";
import BrokersPanel from "./BrokersPanel";
import { useClientes } from "./clientesCtx";

export default function ClientesModales() {
  const {
    aplicarPlantillaEstudio,
    brokers,
    closeEmailModal,
    closeMissingDocsModal,
    codeudorForm,
    codeudorModal,
    confirmSendClientEmail,
    confirmSendMissingDocs,
    declararReparos,
    detectarFechaTasacion,
    ejecutarForzar,
    eliminarPlantillaEstudio,
    emailModal,
    emails,
    enriching,
    enriquecerCarpeta,
    enviarEtapa2,
    escrituraAddNotaria,
    escrituraEnviar,
    escrituraModal,
    escrituraPreview,
    escrituraSaveNotariaEmail,
    estudioEnviar,
    estudioModal,
    estudioPlantillas,
    estudioPreview,
    fmtActFull,
    forzarModal,
    guardarCodeudor,
    guardarFechaTasacion,
    guardarPlantillaEstudio,
    historialModal,
    loading,
    missingDocsModal,
    notarias,
    openPreview,
    pedirEnviar,
    pedirModal,
    pedirPreview,
    pickInmoPlantilla,
    previewClientEmail,
    refreshMissingDocsPreview,
    reloadBrokers,
    reparosModal,
    scanReparos,
    selectionCount,
    setCodeudorForm,
    setCodeudorModal,
    setEmailModal,
    setEscrituraModal,
    setEstudioModal,
    setForzarModal,
    setHistorialModal,
    setMissingDocsModal,
    setPedirModal,
    setReparosModal,
    setTasacionModal,
    subirVoucher,
    tasacionContactos,
    tasacionEnviar,
    tasacionModal,
    tasacionPreview,
    toggleEnvioManual,
    toggleReparo,
    ufValue
  } = useClientes();
  return (
    <>
      {/* EMAIL MODAL */}
      {tasacionModal && (() => {
        const m = tasacionModal;
        const set = (k, v) => setTasacionModal(prev => ({ ...prev, [k]: v, preview: null }));
        const inpS = { width: "100%", padding: "0.5rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.3)", background: "#232326", color: "#e2e8f0", fontSize: 13 };
        const lblS = { fontSize: 12 };
        return (
          <div data-testid="tasacion-modal" onClick={() => setTasacionModal(null)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9998, padding: "3vh 3vw" }}>
            <div onClick={(e) => e.stopPropagation()} style={{ background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", color: "#e2e8f0", borderRadius: 0, width: "min(760px, 96vw)", maxHeight: "94vh", overflow: "auto", border: "1px solid rgba(148,163,184,0.25)", boxShadow: "0 20px 60px rgba(0,0,0,0.6)" }}>
              <div style={{ padding: "0.9rem 1.1rem", borderBottom: "1px solid rgba(148,163,184,0.2)", display: "flex", alignItems: "center", gap: 10 }}>
                <i className="fa fa-home" style={{ color: "#fb923c" }} />
                <h4 style={{ margin: 0, flex: 1 }}>Solicitud de Tasación — {m.folder.nombre}</h4>
                <button onClick={() => setTasacionModal(null)} data-testid="btn-tasacion-close" style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: 18 }}><i className="fa fa-times" /></button>
              </div>
              <div style={{ padding: "1rem 1.1rem", display: "grid", gap: "0.75rem" }}>
                {m.prefillLoading && (
                  <div data-testid="tasacion-prefill-loading" style={{ padding: "0.5rem 0.9rem", background: "rgba(212,175,55,0.1)", border: "1px solid rgba(212,175,55,0.3)", color: "#d4af37", fontSize: 12, fontWeight: 600 }}>
                    <i className="fa fa-spinner fa-spin" style={{ marginRight: 6 }} />Completando datos automáticamente (OCR + IA)… puedes editar y enviar sin esperar.
                  </div>
                )}
                {m.msg && (
                  <div data-testid="tasacion-msg" style={{ padding: "0.6rem 0.9rem", borderRadius: 0, background: m.msg.startsWith("✅") ? "rgba(16,217,142,0.15)" : "rgba(225,29,72,0.15)", color: m.msg.startsWith("✅") ? "#34eab9" : "#fb7185", fontWeight: 600, fontSize: 13 }}>{m.msg}</div>
                )}
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Destinatarios <span style={{ color: "#34eab9" }}>· la tasación SIEMPRE va a Value Property y Victoria Vilches</span></b>
                  <input value={m.destinatarios} onChange={e => set("destinatarios", e.target.value)} data-testid="tasacion-destinatarios" style={inpS} />
                </label>
                <div style={{ background: "rgba(28,28,30,0.7)", borderRadius: 0, padding: "0.5rem 0.9rem", fontSize: 12, opacity: 0.85 }}>
                  Asunto: SOLICITUD TASACION // {m.folder.nombre}{m.folder.rut ? ` Rut: ${m.folder.rut}` : ""}
                </div>
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Texto inicial del correo (editable)</b>
                  <textarea value={m.intro} onChange={e => set("intro", e.target.value)} rows={2} placeholder={`Estimados, se envía solicitud de tasación para ${m.folder.nombre}...`} data-testid="tasacion-intro" style={{ ...inpS, resize: "vertical" }} />
                </label>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Canal / Tipo</b>
                    <select value={m.modalidad} onChange={e => set("modalidad", e.target.value)} data-testid="tasacion-modalidad" style={inpS}>
                      <option value="inmobiliaria">Vivienda nueva (inmobiliaria)</option>
                      <option value="broker">Broker</option>
                      <option value="usada">Vivienda usada (vendedor libre)</option>
                    </select>
                  </label>
                  <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Tipo de tasación</b>
                    <select value={m.tipo} onChange={e => set("tipo", e.target.value)} data-testid="tasacion-tipo" style={inpS}>
                      <option>Individual</option>
                      <option>Propiedad usada</option>
                      <option>Individual (proyecto con tasaciones previas)</option>
                    </select>
                  </label>
                </div>
                {m.modalidad === "inmobiliaria" && (
                  <div style={{ background: "rgba(46,92,230,0.08)", border: "1px solid rgba(46,92,230,0.3)", borderRadius: 0, padding: "0.7rem 0.9rem", display: "grid", gap: "0.6rem" }}>
                    <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Inmobiliaria <span style={{ opacity: 0.6 }}>(si ya tiene plantilla guardada, autocompleta el contacto)</span></b>
                      <input value={m.inmobiliaria} onChange={e => pickInmoPlantilla(e.target.value)} list="inmo-plantillas" placeholder="Ej: Ecomac" data-testid="tasacion-inmobiliaria" style={inpS} />
                      <datalist id="inmo-plantillas">
                        {tasacionContactos.map(c => <option key={c.inmobiliaria_key} value={c.inmobiliaria} />)}
                      </datalist>
                    </label>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.6rem" }}>
                      <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Contacto inmobiliaria (nombre)</b>
                        <input value={m.inmo_contacto_nombre} onChange={e => set("inmo_contacto_nombre", e.target.value)} placeholder="A quién se le solicita" data-testid="tasacion-inmo-nombre" style={inpS} />
                      </label>
                      <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Mail contacto inmobiliaria <span style={{ opacity: 0.6 }}>(se agrega al envío)</span></b>
                        <input value={m.inmo_contacto_email} onChange={e => set("inmo_contacto_email", e.target.value)} placeholder="contacto@inmobiliaria.cl" data-testid="tasacion-inmo-email" style={inpS} />
                      </label>
                    </div>
                    <div style={{ fontSize: 11, opacity: 0.7 }}>💾 Al enviar, el contacto queda guardado como plantilla para esta inmobiliaria (no se agrega a los destinatarios, va como contacto en el correo).</div>
                  </div>
                )}
                {m.modalidad === "broker" && (
                  <div style={{ background: "rgba(212,175,55,0.06)", border: "1px solid rgba(212,175,55,0.3)", borderRadius: 0, padding: "0.7rem 0.9rem", display: "grid", gap: "0.6rem" }}>
                    <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Broker <span style={{ opacity: 0.6 }}>(su contacto va en el correo, se puede editar abajo)</span></b>
                      <select value={m.broker_id} data-testid="tasacion-broker" style={inpS}
                        onChange={e => {
                          const b = brokers.find(x => x.id === e.target.value);
                          setTasacionModal(prev => ({ ...prev, preview: null, broker_id: e.target.value,
                            contacto_nombre: b ? (b.contactos || b.nombre) : prev.contacto_nombre,
                            contacto_email: b ? (b.emails || [])[0] || "" : prev.contacto_email }));
                        }}>
                        <option value="">— Seleccionar broker —</option>
                        {brokers.map(b => <option key={b.id} value={b.id}>{b.nombre}{b.contactos ? ` — ${b.contactos}` : ""}</option>)}
                      </select>
                    </label>
                    <BrokersPanel brokers={brokers} dest={""} setDest={() => {}} reloadBrokers={reloadBrokers} soloAdmin />
                  </div>
                )}
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Dirección de la propiedad <span style={{ color: "#fb7185" }}>*</span></b>
                  <input value={m.direccion} onChange={e => set("direccion", e.target.value)} placeholder="Ej: ELISA CORREA 527, LOS SAUCES, LA FLORIDA" data-testid="tasacion-direccion" style={inpS} />
                </label>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.75rem" }}>
                  <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>N° unidad / depto</b>
                    <input value={m.unidad} onChange={e => set("unidad", e.target.value)} placeholder="Ej: Depto 1204" data-testid="tasacion-unidad" style={inpS} />
                  </label>
                  <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Comuna</b>
                    <input value={m.comuna} onChange={e => set("comuna", e.target.value)} placeholder="Ej: La Florida" data-testid="tasacion-comuna" style={inpS} />
                  </label>
                  <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Ciudad</b>
                    <input value={m.ciudad} onChange={e => set("ciudad", e.target.value)} placeholder="Ej: Santiago" data-testid="tasacion-ciudad" style={inpS} />
                  </label>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.75rem" }}>
                  <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Rol de Avalúo Fiscal</b>
                    <input value={m.rol_avaluo} onChange={e => set("rol_avaluo", e.target.value)} placeholder="Ej: 12324-00005" data-testid="tasacion-rol" style={inpS} />
                  </label>
                  <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Valor aproximado (UF)</b>
                    <input value={m.valor_uf} onChange={e => set("valor_uf", e.target.value)} placeholder="Ej: 3.200" data-testid="tasacion-valor" style={inpS} />
                  </label>
                  <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Valor esperado tasación (UF)</b>
                    <input value={m.valor_esperado_uf} onChange={e => set("valor_esperado_uf", e.target.value)} placeholder="Ej: 3.200" data-testid="tasacion-valor-esperado" style={inpS} />
                  </label>
                </div>
                {!m.archivos.some(a => a.sel && /carta|oferta|aprobaci/i.test(a.nombre)) && (
                  <div data-testid="tasacion-sin-carta" style={{ fontSize: 12, color: "#facc15", background: "rgba(250,204,21,0.08)", border: "1px solid rgba(250,204,21,0.35)", borderRadius: 0, padding: "6px 10px" }}>
                    ⚠️ No hay <b>carta de aprobación</b> seleccionada en los adjuntos — la solicitud debe incluirla.
                  </div>
                )}
                <div style={{ background: "rgba(28,28,30,0.7)", borderRadius: 0, padding: "0.7rem 0.9rem", display: "grid", gap: "0.6rem" }}>
                  <div style={{ opacity: 0.8, fontSize: 11, textTransform: "uppercase", fontWeight: 700 }}>
                    {m.modalidad === "usada" ? "Contacto del vendedor (para que el tasador coordine)" : "Contacto para coordinar la visita del tasador"}
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.6rem" }}>
                    <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Nombre</b>
                      <input value={m.contacto_nombre} onChange={e => set("contacto_nombre", e.target.value)} placeholder={m.modalidad === "usada" ? "Nombre del vendedor" : "Quién recibe al tasador"} data-testid="tasacion-contacto-nombre" style={inpS} />
                    </label>
                    <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Teléfono</b>
                      <input value={m.contacto_telefono} onChange={e => set("contacto_telefono", e.target.value)} placeholder="+56 9 …" data-testid="tasacion-contacto-fono" style={inpS} />
                    </label>
                    <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Mail <span style={{ opacity: 0.6 }}>(opcional)</span></b>
                      <input value={m.contacto_email} onChange={e => set("contacto_email", e.target.value)} placeholder="contacto@correo.cl" data-testid="tasacion-contacto-email" style={inpS} />
                    </label>
                  </div>
                </div>
                <div style={{ background: "rgba(212,175,55,0.08)", border: "1px solid rgba(212,175,55,0.35)", borderRadius: 0, padding: "0.7rem 0.9rem", display: "grid", gap: "0.4rem" }}>
                  <div style={{ opacity: 0.85, fontSize: 11, textTransform: "uppercase", fontWeight: 700, color: "#d4af37" }}>Voucher de pago de la tasación</div>
                  <input type="file" accept=".pdf,.jpg,.jpeg,.png" data-testid="tasacion-voucher-input"
                    onChange={e => subirVoucher(e.target.files[0])} style={{ fontSize: 12 }} />
                  {m.voucher_nombre && <div style={{ fontSize: 12, color: "#34eab9" }}>✅ {m.voucher_nombre} — se adjunta y el correo dirá "Adjunto voucher de pago tasación"</div>}
                </div>
                <div style={{ background: "rgba(234,88,12,0.08)", border: "1px solid rgba(234,88,12,0.3)", borderRadius: 0, padding: "0.7rem 0.9rem", display: "flex", gap: 8, alignItems: "end", flexWrap: "wrap" }}>
                  <label style={{ ...lblS, flex: 1, minWidth: 200 }}><b style={{ display: "block", marginBottom: 4 }}>📅 Fecha de tasación informada por Value Property</b>
                    <input value={m.fecha_tasacion} onChange={e => setTasacionModal(prev => ({ ...prev, fecha_tasacion: e.target.value }))} placeholder="Aún sin fecha" data-testid="tasacion-fecha-vp" style={inpS} />
                  </label>
                  <button onClick={detectarFechaTasacion} disabled={m.loading} data-testid="btn-detectar-fecha" style={{ ...inpS, width: "auto", background: "#ea580c", border: "none", fontWeight: 700, cursor: "pointer" }}>
                    <i className="fa fa-magic" /> Detectar del correo
                  </button>
                  <button onClick={guardarFechaTasacion} disabled={m.loading} data-testid="btn-guardar-fecha" style={{ ...inpS, width: "auto", background: "#334155", border: "none", fontWeight: 700, cursor: "pointer" }}>
                    Guardar
                  </button>
                </div>
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Observaciones / antecedentes adicionales</b>
                  <textarea value={m.observaciones} onChange={e => set("observaciones", e.target.value)} rows={2} placeholder="Ej: Se adjunta carta oferta. Ya contamos con tasaciones de este proyecto." data-testid="tasacion-observaciones" style={{ ...inpS, resize: "vertical" }} />
                </label>
                {m.archivos.length > 0 && (
                  <div style={{ background: "rgba(28,28,30,0.7)", borderRadius: 0, padding: "0.7rem 0.9rem" }}>
                    <div style={{ opacity: 0.7, fontSize: 11, textTransform: "uppercase", marginBottom: 6 }}>Adjuntos — SOLO la carta de aprobación y el voucher pueden enviarse; el resto está bloqueado</div>
                    <div style={{ display: "grid", gap: 4, maxHeight: 140, overflow: "auto" }}>
                      {m.archivos.map((a, i) => {
                        const permitido = /carta|oferta|aprobaci|voucher/i.test(a.nombre) || a.ruta === m.voucher_ruta;
                        return (
                        <label key={a.ruta} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5, cursor: permitido ? "pointer" : "not-allowed", opacity: permitido ? 1 : 0.45 }}>
                          <input type="checkbox" checked={!!a.sel} disabled={!permitido} data-testid={`tasacion-adj-${i}`}
                            onChange={() => permitido && setTasacionModal(prev => ({ ...prev, preview: null, archivos: prev.archivos.map(x => x.ruta === a.ruta ? { ...x, sel: !x.sel } : x) }))} />
                          <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{a.nombre} <span style={{ opacity: 0.5 }}>{a.subfolder ? `(${a.subfolder})` : ""}</span>{!permitido && <span style={{ fontSize: 10, color: "#94a3b8" }}> 🔒</span>}</span>
                          <button type="button" data-testid={`tasacion-adj-ver-${i}`}
                            title={`Ver ${a.nombre}`}
                            onClick={(e) => { e.preventDefault(); e.stopPropagation(); openPreview(m.folder.id, a.ruta, a.nombre); }}
                            style={{ background: "rgba(212,175,55,0.15)", border: "1px solid #d4af37", color: "#d4af37", borderRadius: 0, padding: "2px 10px", fontSize: 11, fontWeight: 700, cursor: "pointer", flexShrink: 0, opacity: 1 }}>
                            <i className="fa fa-eye" /> Ver
                          </button>
                        </label>
                        );
                      })}
                    </div>
                  </div>
                )}
                {m.preview && (
                  <div style={{ background: "#fff", borderRadius: 0, padding: "0.9rem", maxHeight: 260, overflow: "auto" }}>
                    <div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(m.preview.body) }} />
                    {m.preview.attachments.length > 0 && (
                      <div style={{ marginTop: 8, fontSize: 12, color: "#334155" }}>📎 Adjuntos: {m.preview.attachments.join(", ")}</div>
                    )}
                  </div>
                )}
                <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
                  <button onClick={tasacionPreview} disabled={m.loading} data-testid="btn-tasacion-preview"
                    style={{ padding: "0.55rem 1.1rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.4)", background: "transparent", color: "#e2e8f0", fontWeight: 700, cursor: "pointer" }}>
                    <i className={`fa ${m.loading ? "fa-spinner fa-spin" : "fa-eye"}`} /> Ver preview
                  </button>
                  <button onClick={tasacionEnviar} disabled={m.loading || !m.direccion.trim()} data-testid="btn-tasacion-enviar"
                    title={!m.direccion.trim() ? "Falta la dirección de la propiedad" : ""}
                    style={{ padding: "0.55rem 1.1rem", borderRadius: 0, border: "none", background: "#ea580c", color: "#fff", fontWeight: 800, cursor: "pointer", opacity: (m.loading || !m.direccion.trim()) ? 0.6 : 1 }}>
                    <i className={`fa ${m.loading ? "fa-spinner fa-spin" : "fa-paper-plane"}`} /> Enviar solicitud
                  </button>
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {estudioModal && (() => {
        const m = estudioModal;
        const set = (k, v) => setEstudioModal(prev => ({ ...prev, [k]: v, preview: null }));
        const inpS = { width: "100%", padding: "0.5rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.3)", background: "#232326", color: "#e2e8f0", fontSize: 13 };
        const lblS = { fontSize: 12 };
        return (
          <div data-testid="estudio-modal" onClick={() => setEstudioModal(null)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9998, padding: "3vh 3vw" }}>
            <div onClick={(e) => e.stopPropagation()} style={{ background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", color: "#e2e8f0", borderRadius: 0, width: "min(760px, 96vw)", maxHeight: "94vh", overflow: "auto", border: "1px solid rgba(148,163,184,0.25)", boxShadow: "0 20px 60px rgba(0,0,0,0.6)" }}>
              <div style={{ padding: "0.9rem 1.1rem", borderBottom: "1px solid rgba(148,163,184,0.2)", display: "flex", alignItems: "center", gap: 10 }}>
                <i className="fa fa-balance-scale" style={{ color: "#2dd4bf" }} />
                <h4 style={{ margin: 0, flex: 1 }}>Solicitud de Estudio de Título — {m.folder.nombre}</h4>
                <button onClick={() => setEstudioModal(null)} data-testid="btn-estudio-close" style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: 18 }}><i className="fa fa-times" /></button>
              </div>
              <div style={{ padding: "1rem 1.1rem", display: "grid", gap: "0.75rem" }}>
                {m.prefillLoading && (
                  <div data-testid="estudio-prefill-loading" style={{ padding: "0.5rem 0.9rem", background: "rgba(45,212,191,0.08)", border: "1px solid rgba(45,212,191,0.3)", color: "#2dd4bf", fontSize: 12, fontWeight: 600 }}>
                    <i className="fa fa-spinner fa-spin" style={{ marginRight: 6 }} />Completando datos automáticamente (OCR + IA)… puedes editar y enviar sin esperar.
                  </div>
                )}
                {m.msg && (
                  <div data-testid="estudio-msg" style={{ padding: "0.6rem 0.9rem", borderRadius: 0, background: m.msg.startsWith("✅") ? "rgba(16,217,142,0.15)" : "rgba(225,29,72,0.15)", color: m.msg.startsWith("✅") ? "#34eab9" : "#fb7185", fontWeight: 600, fontSize: 13 }}>{m.msg}</div>
                )}
                <div style={{ display: "flex", gap: 8, alignItems: "center", background: "rgba(212,175,55,0.06)", border: "1px solid rgba(212,175,55,0.25)", borderRadius: 0, padding: "0.5rem 0.9rem", flexWrap: "wrap" }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: "var(--gold, #d4af37)" }}>📋 Plantillas</span>
                  <select data-testid="estudio-plantilla-select" onChange={e => { if (e.target.value) aplicarPlantillaEstudio(e.target.value); e.target.value = ""; }}
                    style={{ ...inpS, width: "auto", flex: 1, minWidth: 180, padding: "5px 8px", fontSize: 12 }} defaultValue="">
                    <option value="">Aplicar plantilla guardada…</option>
                    {estudioPlantillas.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                  </select>
                  <button data-testid="estudio-plantilla-guardar" onClick={guardarPlantillaEstudio}
                    style={{ background: "rgba(212,175,55,0.15)", border: "1px solid rgba(212,175,55,0.5)", color: "#d4af37", borderRadius: 0, padding: "5px 12px", fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
                    💾 Guardar plantilla
                  </button>
                  {estudioPlantillas.length > 0 && (
                    <select data-testid="estudio-plantilla-eliminar" onChange={e => { if (e.target.value) eliminarPlantillaEstudio(e.target.value); e.target.value = ""; }}
                      style={{ ...inpS, width: "auto", padding: "5px 8px", fontSize: 12 }} defaultValue="">
                      <option value="">🗑 Eliminar…</option>
                      {estudioPlantillas.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                    </select>
                  )}
                </div>
                <button data-testid="estudio-enriquecer" onClick={() => enriquecerCarpeta(m.folder, "estudio")}
                  disabled={enriching === m.folder.id + "estudio"}
                  title="Busca en el correo (asunto, cuerpo y adjuntos) documentos del estudio de título y los guarda en 07_estudio_titulo. NUNCA se mezclan con los documentos de la solicitud de crédito."
                  style={{ background: "rgba(212,175,55,0.12)", border: "1.5px solid #d4af37", color: "#d4af37", borderRadius: 0, padding: "0.55rem 1rem", fontSize: 12.5, fontWeight: 800, cursor: "pointer", textAlign: "left" }}>
                  <i className={`fa ${enriching === m.folder.id + "estudio" ? "fa-spinner fa-spin" : "fa-magic"}`}></i> 🔎 Enriquecer archivos del Estudio de Título (busca en el correo · se guardan separados de la solicitud de crédito)
                </button>
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Destinatarios <span style={{ color: "#34eab9" }}>· broker seleccionado + Victoria Vilches siempre en copia</span></b>
                  <input value={m.destinatarios} onChange={e => set("destinatarios", e.target.value)} data-testid="estudio-destinatarios" style={inpS} />
                </label>
                <BrokersPanel brokers={brokers} dest={m.destinatarios} setDest={(v) => set("destinatarios", v)} reloadBrokers={reloadBrokers} />
                <div style={{ background: "rgba(28,28,30,0.5)", border: "1px solid rgba(148,163,184,0.2)", borderRadius: 0, padding: "0.6rem 0.9rem" }}>
                  <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Con copia (CC) <span style={{ color: "#d4af37" }}>· opcional — se mantienen informados en TODO el hilo del estudio (reparos, recordatorios y resolución)</span></b>
                    <input value={m.cc || ""} onChange={e => set("cc", e.target.value)} data-testid="estudio-cc" placeholder="correo1@ejemplo.cl, correo2@ejemplo.cl" style={inpS} />
                  </label>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                    {m.folder.source_email && !String(m.cc || "").toLowerCase().includes(String(m.folder.source_email).toLowerCase()) && (
                      <button data-testid="cc-add-cliente" onClick={() => set("cc", [m.cc, m.folder.source_email].filter(Boolean).join(", "))}
                        style={{ background: "rgba(16,217,142,0.12)", border: "1px solid rgba(16,217,142,0.4)", color: "#34eab9", borderRadius: 0, padding: "3px 10px", fontSize: 11.5, cursor: "pointer" }}>
                        + Cliente/Solicitante ({m.folder.source_email})
                      </button>
                    )}
                    {brokers.flatMap(b => (b.emails || []).map(em => ({ nombre: b.nombre, em })))
                      .filter(x => !String(m.cc || "").toLowerCase().includes(x.em.toLowerCase()))
                      .map((x, i) => (
                        <button key={i} data-testid={`cc-add-broker-${i}`} onClick={() => set("cc", [m.cc, x.em].filter(Boolean).join(", "))}
                          style={{ background: "rgba(212,175,55,0.12)", border: "1px solid rgba(212,175,55,0.4)", color: "#d4af37", borderRadius: 0, padding: "3px 10px", fontSize: 11.5, cursor: "pointer" }}>
                          + {x.nombre} ({x.em})
                        </button>
                      ))}
                  </div>
                </div>
                <div style={{ background: "rgba(28,28,30,0.7)", borderRadius: 0, padding: "0.5rem 0.9rem", fontSize: 12, opacity: 0.85 }}>
                  Asunto: SOLICITUD ESTUDIO DE TITULOS // {m.folder.nombre}{m.folder.rut ? ` ${m.folder.rut}` : ""}
                </div>
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Texto inicial del correo (editable)</b>
                  <textarea value={m.intro} onChange={e => set("intro", e.target.value)} rows={2} placeholder="Solicitamos dar inicio al estudio de títulos del cliente en referencia..." data-testid="estudio-intro" style={{ ...inpS, resize: "vertical" }} />
                </label>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Tipo de vivienda</b>
                    <select value={m.tipo_vivienda} data-testid="estudio-tipo" style={inpS}
                      onChange={e => {
                        const t = e.target.value;
                        setEstudioModal(prev => ({ ...prev, preview: null, tipo_vivienda: t,
                          docs_texto: ((t === "usada" ? prev.docs_usada : prev.docs_nueva) || []).join("\n") }));
                      }}>
                      <option value="nueva">Vivienda nueva (inmobiliaria)</option>
                      <option value="usada">Vivienda usada</option>
                    </select>
                  </label>
                  {m.tipo_vivienda === "nueva" ? (
                    <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Inmobiliaria / Proyecto <span style={{ opacity: 0.6 }}>(plantilla)</span></b>
                      <input value={m.inmobiliaria} list="inmo-plantillas-estudio" placeholder="Ej: Ecomac" data-testid="estudio-inmobiliaria" style={inpS}
                        onChange={e => {
                          const v = e.target.value;
                          const p = tasacionContactos.find(c => (c.inmobiliaria || "").toLowerCase() === v.toLowerCase());
                          setEstudioModal(prev => ({ ...prev, preview: null, inmobiliaria: v,
                            inmo_contacto_nombre: p ? (p.contacto_nombre || prev.inmo_contacto_nombre) : prev.inmo_contacto_nombre,
                            inmo_contacto_email: p ? (p.contacto_email || prev.inmo_contacto_email) : prev.inmo_contacto_email }));
                        }} />
                      <datalist id="inmo-plantillas-estudio">
                        {tasacionContactos.map(c => <option key={c.inmobiliaria_key} value={c.inmobiliaria} />)}
                      </datalist>
                    </label>
                  ) : <div />}
                </div>
                {m.tipo_vivienda === "nueva" && (
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.6rem" }}>
                    <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Contacto inmobiliaria (nombre)</b>
                      <input value={m.inmo_contacto_nombre} onChange={e => set("inmo_contacto_nombre", e.target.value)} placeholder="A quién se le solicita" data-testid="estudio-inmo-nombre" style={inpS} />
                    </label>
                    <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Mail contacto inmobiliaria <span style={{ opacity: 0.6 }}>(💾 se guarda como plantilla al enviar)</span></b>
                      <input value={m.inmo_contacto_email} onChange={e => set("inmo_contacto_email", e.target.value)} placeholder="contacto@inmobiliaria.cl" data-testid="estudio-inmo-email" style={inpS} />
                    </label>
                  </div>
                )}
                {m.tipo_vivienda === "usada" && (
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.6rem" }}>
                    <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Vendedor (nombre)</b>
                      <input value={m.vendedor_nombre} onChange={e => set("vendedor_nombre", e.target.value)} placeholder="Vendedor libre" data-testid="estudio-vendedor-nombre" style={inpS} />
                    </label>
                    <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Mail del vendedor</b>
                      <input value={m.vendedor_email} onChange={e => set("vendedor_email", e.target.value)} placeholder="vendedor@correo.cl" data-testid="estudio-vendedor-email" style={inpS} />
                    </label>
                    <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Teléfono <span style={{ opacity: 0.6 }}>(opcional)</span></b>
                      <input value={m.vendedor_telefono} onChange={e => set("vendedor_telefono", e.target.value)} placeholder="+56 9 …" data-testid="estudio-vendedor-fono" style={inpS} />
                    </label>
                  </div>
                )}
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Dirección de la propiedad</b>
                  <input value={m.direccion} onChange={e => set("direccion", e.target.value)} placeholder="Dirección completa" data-testid="estudio-direccion" style={inpS} />
                </label>
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>{m.tipo_vivienda === "usada" ? "Documentos solicitados para vivienda usada" : "Documentos obligatorios solicitados a la inmobiliaria (vivienda nueva)"} <span style={{ opacity: 0.6 }}>(uno por línea — se listan en el correo junto a la frase de reserva de antecedentes)</span></b>
                  <textarea value={m.docs_texto} onChange={e => set("docs_texto", e.target.value)} rows={8} data-testid="estudio-docs" style={{ ...inpS, resize: "vertical", fontSize: 12 }} />
                </label>
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Observaciones</b>
                  <textarea value={m.observaciones} onChange={e => set("observaciones", e.target.value)} rows={2} data-testid="estudio-observaciones" style={{ ...inpS, resize: "vertical" }} />
                </label>
                {m.archivos.length > 0 && (() => {
                  const esEst = (a) => (a.subfolder || "").startsWith("07_estudio_titulo");
                  const adjCredito = m.archivos.filter(a => !esEst(a));
                  const docsEstudio = m.archivos.filter(esEst);
                  return (
                  <>
                  {docsEstudio.length > 0 && (
                    <div data-testid="estudio-docs-recibidos" style={{ background: "rgba(20,184,166,0.08)", border: "1.5px dashed #14b8a6", borderRadius: 0, padding: "0.7rem 0.9rem" }}>
                      <div style={{ color: "#2dd4bf", fontSize: 11, textTransform: "uppercase", fontWeight: 800, marginBottom: 4 }}>
                        ⚖ Documentos del Estudio de Título recibidos ({docsEstudio.length})
                      </div>
                      <div style={{ fontSize: 11, color: "#5eead4", marginBottom: 6 }}>
                        Carpeta separada de la propiedad — NUNCA se mezclan con la solicitud de crédito. Usá "Enriquecer archivos" para seguir sumando los que lleguen por correo.
                      </div>
                      <button data-testid="btn-estudio-etapa2" onClick={() => enviarEtapa2(m)} disabled={m.loading}
                        title="Etapa 2: enviar al abogado los documentos del estudio recibidos, con copia a Victoria Vilches, en el mismo hilo del correo"
                        style={{ background: "#0d9488", border: "none", color: "#fff", borderRadius: 0, padding: "0.5rem 1rem", fontSize: 12.5, fontWeight: 800, cursor: "pointer", marginBottom: 8 }}>
                        <i className={`fa ${m.loading ? "fa-spinner fa-spin" : "fa-paper-plane"}`} /> 📤 Etapa 2: Enviar documentos recibidos a Guillermo Marluf (CC Victoria Vilches)
                      </button>
                      {m.folder.estudio_docs_enviados_abogado_at && (
                        <div data-testid="estudio-etapa2-badge" style={{ fontSize: 11, color: "#34eab9", fontWeight: 700, marginBottom: 6 }}>
                          ✅ Etapa 2 realizada: {(m.folder.estudio_docs_enviados_abogado || []).length} documento(s) enviados el {new Date(m.folder.estudio_docs_enviados_abogado_at).toLocaleString("es-CL")}
                        </div>
                      )}
                      <div style={{ display: "grid", gap: 4, maxHeight: 130, overflow: "auto" }}>
                        {docsEstudio.map((a, i) => (
                          <div key={a.ruta} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5 }}>
                            <i className="fa fa-file-pdf-o" style={{ color: "#2dd4bf" }} />
                            <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{a.nombre}</span>
                            <button type="button" data-testid={`estudio-doc-ver-${i}`}
                              onClick={() => openPreview(m.folder.id, a.ruta, a.nombre)}
                              style={{ background: "rgba(212,175,55,0.15)", border: "1px solid #d4af37", color: "#d4af37", borderRadius: 0, padding: "2px 10px", fontSize: 11, fontWeight: 700, cursor: "pointer", flexShrink: 0 }}>
                              <i className="fa fa-eye" /> Ver
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  <div style={{ background: "rgba(28,28,30,0.7)", borderRadius: 0, padding: "0.7rem 0.9rem" }}>
                    <div style={{ opacity: 0.7, fontSize: 11, textTransform: "uppercase", marginBottom: 6 }}>Adjuntos de la solicitud — la carta de aprobación va preseleccionada</div>
                    <div style={{ display: "grid", gap: 4, maxHeight: 140, overflow: "auto" }}>
                      {adjCredito.map((a, i) => (
                        <label key={a.ruta} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5, cursor: "pointer" }}>
                          <input type="checkbox" checked={!!a.sel} data-testid={`estudio-adj-${i}`}
                            onChange={() => setEstudioModal(prev => ({ ...prev, preview: null, archivos: prev.archivos.map(x => x.ruta === a.ruta ? { ...x, sel: !x.sel } : x) }))} />
                          <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{a.nombre} <span style={{ opacity: 0.5 }}>{a.subfolder ? `(${a.subfolder})` : ""}</span></span>
                          <button type="button" data-testid={`estudio-adj-ver-${i}`}
                            title={`Ver ${a.nombre} antes de enviarlo`}
                            onClick={(e) => { e.preventDefault(); e.stopPropagation(); openPreview(m.folder.id, a.ruta, a.nombre); }}
                            style={{ background: "rgba(212,175,55,0.15)", border: "1px solid #d4af37", color: "#d4af37", borderRadius: 0, padding: "2px 10px", fontSize: 11, fontWeight: 700, cursor: "pointer", flexShrink: 0 }}>
                            <i className="fa fa-eye" /> Ver
                          </button>
                        </label>
                      ))}
                    </div>
                  </div>
                  </>
                  );
                })()}
                {m.preview && (
                  <div style={{ background: "#fff", borderRadius: 0, padding: "0.9rem", maxHeight: 260, overflow: "auto" }}>
                    <div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(m.preview.body) }} />
                    {m.preview.attachments.length > 0 && (
                      <div style={{ marginTop: 8, fontSize: 12, color: "#334155" }}>📎 Adjuntos: {m.preview.attachments.join(", ")}</div>
                    )}
                  </div>
                )}
                <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
                  <button onClick={estudioPreview} disabled={m.loading} data-testid="btn-estudio-preview"
                    style={{ padding: "0.55rem 1.1rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.4)", background: "transparent", color: "#e2e8f0", fontWeight: 700, cursor: "pointer" }}>
                    <i className={`fa ${m.loading ? "fa-spinner fa-spin" : "fa-eye"}`} /> Ver preview
                  </button>
                  <button onClick={estudioEnviar} disabled={m.loading} data-testid="btn-estudio-enviar"
                    style={{ padding: "0.55rem 1.1rem", borderRadius: 0, border: "none", background: "#0d9488", color: "#fff", fontWeight: 800, cursor: "pointer", opacity: m.loading ? 0.6 : 1 }}>
                    <i className={`fa ${m.loading ? "fa-spinner fa-spin" : "fa-paper-plane"}`} /> Enviar solicitud
                  </button>
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {pedirModal && (() => {
        const m = pedirModal;
        const set = (k, v) => setPedirModal(prev => ({ ...prev, [k]: v, preview: null }));
        const inpS = { width: "100%", padding: "0.5rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.3)", background: "#232326", color: "#e2e8f0", fontSize: 13 };
        const lblS = { fontSize: 12 };
        return (
          <div data-testid="pedir-modal" onClick={() => setPedirModal(null)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9998, padding: "3vh 3vw" }}>
            <div onClick={(e) => e.stopPropagation()} style={{ background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", color: "#e2e8f0", borderRadius: 0, width: "min(680px, 96vw)", maxHeight: "94vh", overflow: "auto", border: "1px solid rgba(148,163,184,0.25)", boxShadow: "0 20px 60px rgba(0,0,0,0.6)" }}>
              <div style={{ padding: "0.9rem 1.1rem", borderBottom: "1px solid rgba(148,163,184,0.2)", display: "flex", alignItems: "center", gap: 10 }}>
                <i className="fa fa-envelope" style={{ color: "#fb7185" }} />
                <h4 style={{ margin: 0, flex: 1 }}>Pedir documentos faltantes — {m.folder.nombre}</h4>
                <button onClick={() => setPedirModal(null)} data-testid="btn-pedir-close" style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: 18 }}><i className="fa fa-times" /></button>
              </div>
              <div style={{ padding: "1rem 1.1rem", display: "grid", gap: "0.75rem" }}>
                {m.msg && (
                  <div data-testid="pedir-msg" style={{ padding: "0.6rem 0.9rem", borderRadius: 0, background: m.msg.startsWith("✅") ? "rgba(16,217,142,0.15)" : "rgba(225,29,72,0.15)", color: m.msg.startsWith("✅") ? "#34eab9" : "#fb7185", fontWeight: 600, fontSize: 13 }}>{m.msg}</div>
                )}
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Destinatario (quien nos envió la solicitud de crédito)</b>
                  <input value={m.destinatario} onChange={e => set("destinatario", e.target.value)} data-testid="pedir-destinatario" style={inpS} />
                </label>
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Documentos faltantes (uno por línea)</b>
                  <textarea value={m.faltantes} onChange={e => set("faltantes", e.target.value)} rows={4} data-testid="pedir-faltantes-lista" style={{ ...inpS, resize: "vertical" }} />
                </label>
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Mensaje adicional (opcional)</b>
                  <textarea value={m.mensaje} onChange={e => set("mensaje", e.target.value)} rows={2} data-testid="pedir-mensaje" style={{ ...inpS, resize: "vertical" }} />
                </label>
                {m.preview && (
                  <div style={{ background: "#fff", borderRadius: 0, padding: "0.9rem", maxHeight: 240, overflow: "auto" }}>
                    <div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(m.preview.body) }} />
                  </div>
                )}
                <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
                  <button onClick={pedirPreview} disabled={m.loading} data-testid="btn-pedir-preview"
                    style={{ padding: "0.55rem 1.1rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.4)", background: "transparent", color: "#e2e8f0", fontWeight: 700, cursor: "pointer" }}>
                    <i className={`fa ${m.loading ? "fa-spinner fa-spin" : "fa-eye"}`} /> Ver preview
                  </button>
                  <button onClick={pedirEnviar} disabled={m.loading || !m.destinatario.includes("@")} data-testid="btn-pedir-enviar"
                    style={{ padding: "0.55rem 1.1rem", borderRadius: 0, border: "none", background: "#be123c", color: "#fff", fontWeight: 800, cursor: "pointer", opacity: (m.loading || !m.destinatario.includes("@")) ? 0.6 : 1 }}>
                    <i className={`fa ${m.loading ? "fa-spinner fa-spin" : "fa-paper-plane"}`} /> Enviar solicitud de faltantes
                  </button>
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {escrituraModal && (() => {
        const m = escrituraModal;
        const set = (k, v) => setEscrituraModal(prev => ({ ...prev, [k]: v, preview: null }));
        const inpS = { width: "100%", padding: "0.5rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.3)", background: "#232326", color: "#e2e8f0", fontSize: 13 };
        const lblS = { fontSize: 12 };
        const notariaSel = notarias.find(n => n.id === m.notaria_id);
        return (
          <div data-testid="escritura-modal" onClick={() => setEscrituraModal(null)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9998, padding: "3vh 3vw" }}>
            <div onClick={(e) => e.stopPropagation()} style={{ background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", color: "#e2e8f0", borderRadius: 0, width: "min(760px, 96vw)", maxHeight: "94vh", overflow: "auto", border: "1px solid rgba(148,163,184,0.25)", boxShadow: "0 20px 60px rgba(0,0,0,0.6)" }}>
              <div style={{ padding: "0.9rem 1.1rem", borderBottom: "1px solid rgba(148,163,184,0.2)", display: "flex", alignItems: "center", gap: 10 }}>
                <i className="fa fa-pencil" style={{ color: "#f472b6" }} />
                <h4 style={{ margin: 0, flex: 1 }}>Firma de Escritura — {m.folder.nombre}</h4>
                <button onClick={() => setEscrituraModal(null)} data-testid="btn-escritura-close" style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: 18 }}><i className="fa fa-times" /></button>
              </div>
              <div style={{ padding: "1rem 1.1rem", display: "grid", gap: "0.75rem" }}>
                {m.msg && (
                  <div data-testid="escritura-msg" style={{ padding: "0.6rem 0.9rem", borderRadius: 0, background: m.msg.startsWith("✅") ? "rgba(16,217,142,0.15)" : "rgba(225,29,72,0.15)", color: m.msg.startsWith("✅") ? "#34eab9" : "#fb7185", fontWeight: 600, fontSize: 13 }}>{m.msg}</div>
                )}
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Correo del cliente <span style={{ color: "#fb7185" }}>*</span></b>
                  <input value={m.email_cliente} onChange={e => set("email_cliente", e.target.value)} placeholder="cliente@correo.cl" data-testid="escritura-email" style={inpS} />
                </label>
                <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Notaría (por ciudad) <span style={{ color: "#fb7185" }}>*</span></b>
                  <select value={m.notaria_id} onChange={e => set("notaria_id", e.target.value)} data-testid="escritura-notaria" style={inpS}>
                    <option value="">— Seleccionar notaría —</option>
                    {notarias.map(n => <option key={n.id} value={n.id}>{n.ciudad} — {n.nombre} · {n.direccion}</option>)}
                  </select>
                </label>
                {notariaSel && !notariaSel.email && (
                  <div style={{ display: "flex", gap: 6, alignItems: "center", background: "rgba(250,204,21,0.08)", border: "1px solid rgba(250,204,21,0.3)", borderRadius: 0, padding: "0.5rem 0.8rem", fontSize: 12 }}>
                    <span style={{ color: "#facc15" }}>⚠️ Esta notaría no tiene correo: no recibirá el aviso de confirmación.</span>
                    <input value={m.notaria_email_edit} onChange={e => setEscrituraModal(prev => ({ ...prev, notaria_email_edit: e.target.value }))} placeholder="correo@notaria.cl" data-testid="escritura-notaria-email" style={{ ...inpS, flex: 1, width: "auto" }} />
                    <button onClick={escrituraSaveNotariaEmail} data-testid="escritura-notaria-email-save" style={{ ...inpS, width: "auto", background: "#a16207", border: "none", fontWeight: 700, cursor: "pointer" }}>Guardar</button>
                  </div>
                )}
                {m.addNotaria ? (
                  <div style={{ background: "rgba(236,72,153,0.06)", border: "1px dashed rgba(236,72,153,0.4)", borderRadius: 0, padding: "0.7rem 0.9rem", display: "grid", gap: "0.5rem" }}>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1.5fr", gap: "0.5rem" }}>
                      <input value={m.nn.ciudad} onChange={e => setEscrituraModal(prev => ({ ...prev, nn: { ...prev.nn, ciudad: e.target.value } }))} placeholder="Ciudad *" data-testid="notaria-new-ciudad" style={inpS} />
                      <input value={m.nn.nombre} onChange={e => setEscrituraModal(prev => ({ ...prev, nn: { ...prev.nn, nombre: e.target.value } }))} placeholder="Nombre notaría" data-testid="notaria-new-nombre" style={inpS} />
                    </div>
                    <input value={m.nn.direccion} onChange={e => setEscrituraModal(prev => ({ ...prev, nn: { ...prev.nn, direccion: e.target.value } }))} placeholder="Dirección completa *" data-testid="notaria-new-direccion" style={inpS} />
                    <div style={{ display: "flex", gap: 6 }}>
                      <input value={m.nn.email} onChange={e => setEscrituraModal(prev => ({ ...prev, nn: { ...prev.nn, email: e.target.value } }))} placeholder="Correo notaría (para avisarle la confirmación)" data-testid="notaria-new-email" style={{ ...inpS, flex: 1 }} />
                      <button onClick={escrituraAddNotaria} data-testid="notaria-new-save" style={{ ...inpS, width: "auto", background: "#db2777", border: "none", fontWeight: 700, cursor: "pointer" }}>Guardar notaría</button>
                    </div>
                  </div>
                ) : (
                  <button onClick={() => setEscrituraModal(prev => ({ ...prev, addNotaria: true }))} data-testid="btn-add-notaria" style={{ justifySelf: "start", background: "transparent", border: "1px dashed rgba(236,72,153,0.5)", color: "#f9a8d4", borderRadius: 0, padding: "0.3rem 0.7rem", fontSize: 11.5, cursor: "pointer" }}>
                    <i className="fa fa-plus" /> Agregar notaría nueva
                  </button>
                )}
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Día de la firma <span style={{ color: "#fb7185" }}>*</span></b>
                    <input type="date" value={m.fecha} onChange={e => set("fecha", e.target.value)} data-testid="escritura-fecha" style={inpS} />
                  </label>
                  <label style={lblS}><b style={{ display: "block", marginBottom: 4 }}>Horario <span style={{ opacity: 0.6 }}>(10:00 por defecto — horario a sugerir si es distinto)</span></b>
                    <input type="time" value={m.hora} onChange={e => set("hora", e.target.value)} data-testid="escritura-hora" style={inpS} />
                  </label>
                </div>
                <div style={{ fontSize: 11.5, opacity: 0.75, background: "rgba(16,217,142,0.06)", border: "1px solid rgba(16,217,142,0.25)", borderRadius: 0, padding: "0.5rem 0.8rem", lineHeight: 1.6 }}>
                  El cliente recibe el correo con el botón <b>"CONFIRMO QUE ASISTIRÉ"</b>. Al confirmar, indica si va solo, con mandatario y/o codeudor,
                  y se avisa automáticamente a la <b>notaría</b> (si tiene correo) y a <b>Victoria Vilches, Daniela Galindo y Rodrigo Ibáñez</b> con el día, horario y acompañantes.
                </div>
                {m.preview && (
                  <div style={{ background: "#fff", borderRadius: 0, padding: "0.9rem", maxHeight: 280, overflow: "auto" }}>
                    <div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(m.preview.body) }} />
                  </div>
                )}
                <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
                  <button onClick={escrituraPreview} disabled={m.loading} data-testid="btn-escritura-preview"
                    style={{ padding: "0.55rem 1.1rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.4)", background: "transparent", color: "#e2e8f0", fontWeight: 700, cursor: "pointer" }}>
                    <i className={`fa ${m.loading ? "fa-spinner fa-spin" : "fa-eye"}`} /> Ver preview
                  </button>
                  <button onClick={escrituraEnviar} disabled={m.loading || !m.email_cliente.includes("@") || !m.fecha || !m.notaria_id} data-testid="btn-escritura-enviar"
                    title={!m.email_cliente.includes("@") ? "Falta el correo del cliente" : (!m.fecha ? "Falta la fecha" : (!m.notaria_id ? "Falta la notaría" : ""))}
                    style={{ padding: "0.55rem 1.1rem", borderRadius: 0, border: "none", background: "#db2777", color: "#fff", fontWeight: 800, cursor: "pointer", opacity: (m.loading || !m.email_cliente.includes("@") || !m.fecha || !m.notaria_id) ? 0.6 : 1 }}>
                    <i className={`fa ${m.loading ? "fa-spinner fa-spin" : "fa-paper-plane"}`} /> Enviar aviso al cliente
                  </button>
                </div>
              </div>
            </div>
          </div>
        );
      })()}

      {emailModal && (() => {
        const f = emailModal.folder;
        const df = f.datos_financieros || {};
        const cr = f.credit_request || {};
        const conSub = df.con_subsidio ?? (cr.subsidy?.tipo === "con_subsidio");
        // Formato UF con prefijo "UF" antes del número. Ej: "UF 3.200,00"
        // Valores < 20000 se consideran UF nativos, >= 20000 se convierten desde CLP.
        const fmt = (n) => {
          if (n == null || n === "") return "—";
          const v = Number(n);
          if (Number.isNaN(v)) return String(n);
          const uf = v < 20000 ? v : v / (Number(ufValue) || 40842);
          return `UF ${uf.toLocaleString('es-CL', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        };
        const prefijoAsunto = `Antecedentes crédito hipotecario — ${f.nombre}${f.rut ? ` (${f.rut})` : ""}${df.fecha_entrega ? ` — Entrega: ${df.fecha_entrega.charAt(0).toUpperCase() + df.fecha_entrega.slice(1)}` : ""}`;
        const previewSubject = prefijoAsunto
          + (emailModal.subject_extra ? ` — ${emailModal.subject_extra}` : "")
          + (emailModal.ejecutivo_externo ? ` — Ejecutivo: ${emailModal.ejecutivo_externo}` : "");
        return (
          <div data-testid="email-modal" onClick={closeEmailModal} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9998, padding: "3vh 3vw" }}>
            <div onClick={(e) => e.stopPropagation()} style={{ background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", color: "#e2e8f0", borderRadius: 0, width: "min(760px, 96vw)", maxHeight: "94vh", overflow: "auto", border: "1px solid rgba(148,163,184,0.25)", boxShadow: "0 20px 60px rgba(0,0,0,0.6)" }}>
              <div style={{ padding: "0.9rem 1.1rem", borderBottom: "1px solid rgba(148,163,184,0.2)", display: "flex", alignItems: "center", gap: 10 }}>
                <i className="fa fa-paper-plane" style={{ color: "#d4af37" }} />
                <h4 style={{ margin: 0, flex: 1 }}>Enviar correo con antecedentes</h4>
                <button onClick={closeEmailModal} data-testid="btn-email-close" style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: 18 }}><i className="fa fa-times" /></button>
              </div>
              <div style={{ padding: "1rem 1.1rem", display: "grid", gap: "0.75rem" }}>
                <div style={{ background: "rgba(28,28,30,0.7)", borderRadius: 0, padding: "0.7rem 0.9rem", fontSize: 13, lineHeight: 1.5 }}>
                  <div style={{ opacity: 0.7, fontSize: 11, textTransform: "uppercase", marginBottom: 4 }}>Datos que se incluirán en el correo</div>
                  <div><b>Cliente:</b> {f.nombre}</div>
                  <div><b>RUT:</b> {f.rut || <span style={{ color: "#fb7185" }}>— falta</span>}</div>
                  <div><b>Tipo:</b> {conSub ? "CON subsidio (DS1 / DS19)" : "SIN subsidio"}</div>
                  <div><b>Inmobiliaria:</b> {df.inmobiliaria || <span style={{ color: "#facc15" }}>— falta (completar en Ver datos financieros)</span>}</div>
                  {df.proyecto && <div><b>Proyecto:</b> {df.proyecto}</div>}
                  <div><b>Valor propiedad:</b> {fmt(df.valor_propiedad)}</div>
                  {conSub && <div><b>Monto subsidio:</b> {fmt(df.monto_subsidio)}</div>}
                  {conSub && <div><b>Ahorro:</b> {fmt(df.ahorro)}</div>}
                  {!conSub && <div><b>Pie:</b> {fmt(df.monto_pie)}</div>}
                  <div><b>Reserva:</b> {fmt(df.monto_reserva)}</div>
                  <div><b>Monto crédito:</b> {fmt(df.monto_credito)}</div>
                </div>

                <label style={{ fontSize: 12 }}>
                  <b style={{ display: "block", marginBottom: 4 }}>Destinatario <span style={{ color: "#fb7185" }}>🔒 fijo</span></b>
                  <input
                    type="email"
                    value={emailModal.to}
                    readOnly
                    data-testid="email-to-input"
                    style={{ width: "100%", padding: "0.5rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.3)", background: "#232326", color: "#e2e8f0", fontSize: 13, cursor: "not-allowed", opacity: 0.85 }}
                  />
                  <div style={{ marginTop: 6, padding: "6px 10px", borderRadius: 0, background: "rgba(225,29,72,0.12)", border: "1px solid rgba(225,29,72,0.4)", color: "#fda4af", fontSize: 11, fontWeight: 500 }}>
                    🔒 <b>Regla inviolable</b>: todos los correos a mesa se envían solo a la cuenta Central Mutuos. No se puede modificar el destinatario.
                  </div>
                </label>

                <label style={{ fontSize: 12 }}>
                  <b style={{ display: "block", marginBottom: 4 }}>Ejecutivo interno * <span style={{ color: "#facc15" }}>se incluye en el correo a mesa junto al correo de origen</span></b>
                  <select
                    value={emailModal.ejecutivo || ""}
                    onChange={(e) => setEmailModal({ ...emailModal, ejecutivo: e.target.value })}
                    data-testid="email-ejecutivo-select"
                    style={{ width: "100%", padding: "0.5rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.3)", background: "#232326", color: "#e2e8f0", fontSize: 13 }}>
                    <option value="">— Seleccionar ejecutivo —</option>
                    <option value="Deisy Salazar">Deisy Salazar</option>
                    <option value="Yerile Barrera">Yerile Barrera</option>
                    <option value="Gerardo Barrera">Gerardo Barrera</option>
                  </select>
                </label>

                <label style={{ fontSize: 12 }}>
                  <b style={{ display: "block", marginBottom: 4 }}>Ejecutivo externo (de dónde viene la solicitud) <span style={{ color: "#facc15" }}>se agrega al asunto y al correo</span></b>
                  <input
                    type="text"
                    value={emailModal.ejecutivo_externo || ""}
                    onChange={(e) => setEmailModal({ ...emailModal, ejecutivo_externo: e.target.value })}
                    placeholder="Ej: Javiera Garrido — World Consultores"
                    data-testid="email-ejecutivo-externo-input"
                    style={{ width: "100%", padding: "0.5rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.3)", background: "#232326", color: "#e2e8f0", fontSize: 13 }}
                  />
                </label>

                <label style={{ fontSize: 12 }}>
                  <b style={{ display: "block", marginBottom: 4 }}>Asunto <span style={{ color: "#fb7185" }}>🔒 prefijo fijo</span> + texto adicional (opcional)</b>
                  <div style={{ padding: "0.45rem 0.6rem", borderRadius: 0, background: "rgba(225,29,72,0.08)", border: "1px dashed rgba(225,29,72,0.4)", fontSize: 12, color: "#fda4af", marginBottom: 6 }} data-testid="email-subject-prefijo">
                    🔒 {prefijoAsunto}
                  </div>
                  <input
                    type="text"
                    value={emailModal.subject_extra || ""}
                    onChange={(e) => setEmailModal({ ...emailModal, subject_extra: e.target.value })}
                    placeholder="Agregar al asunto (ej: URGENTE, con codeudor…) — el prefijo nunca se borra"
                    data-testid="email-subject-input"
                    style={{ width: "100%", padding: "0.5rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.3)", background: "#232326", color: "#e2e8f0", fontSize: 13 }}
                  />
                  <div style={{ marginTop: 5, fontSize: 11, opacity: 0.75 }} data-testid="email-subject-final">
                    Asunto final: <span style={{ color: "#facc15" }}>{previewSubject}</span>
                  </div>
                </label>

                <label style={{ fontSize: 12 }}>
                  <b style={{ display: "block", marginBottom: 4 }}>Mensaje adicional (opcional)</b>
                  <textarea
                    value={emailModal.extra}
                    onChange={(e) => setEmailModal({ ...emailModal, extra: e.target.value })}
                    rows={3}
                    placeholder="Comentarios extra para el destinatario…"
                    data-testid="email-extra-input"
                    style={{ width: "100%", padding: "0.5rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.3)", background: "#232326", color: "#e2e8f0", fontSize: 13, resize: "vertical" }}
                  />
                </label>

                <div style={{ background: "rgba(28,28,30,0.5)", borderRadius: 0, padding: "0.6rem 0.9rem", fontSize: 12, display: "grid", gap: 6 }}>
                  <div style={{ opacity: 0.7, fontSize: 11, textTransform: "uppercase" }}>Adjuntos</div>
                  <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={!!emailModal.include_merged}
                      onChange={(e) => setEmailModal({ ...emailModal, include_merged: e.target.checked })}
                      data-testid="email-include-merged"
                      style={{ accentColor: "#facc15" }}
                    />
                    Adjuntar combinado del <b>titular</b> (COMBINADO_PROTOCOLO_*.pdf)
                  </label>
                  {(f.codeudor_nombre || f.credit_request?.codeudor?.has_codeudor) && (
                    <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                      <input
                        type="checkbox"
                        checked={!!emailModal.include_codeudor_merged}
                        onChange={(e) => setEmailModal({ ...emailModal, include_codeudor_merged: e.target.checked })}
                        data-testid="email-include-codeudor"
                        style={{ accentColor: "#facc15" }}
                      />
                      Adjuntar combinado del <b>codeudor</b> {f.codeudor_nombre ? `(${f.codeudor_nombre})` : ""} — se genera automáticamente si no existe
                    </label>
                  )}
                  <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: selectionCount(f.id) > 0 ? "pointer" : "not-allowed", opacity: selectionCount(f.id) > 0 ? 1 : 0.5 }}>
                    <input
                      type="checkbox"
                      checked={!!emailModal.attach_selected}
                      onChange={(e) => setEmailModal({ ...emailModal, attach_selected: e.target.checked })}
                      disabled={selectionCount(f.id) < 1}
                      data-testid="email-attach-selected"
                      style={{ accentColor: "#facc15" }}
                    />
                    Adjuntar archivos seleccionados ({selectionCount(f.id)})
                  </label>
                </div>
              </div>
              {emailModal.preview && (
                <div style={{ padding: "0.8rem 1.1rem", borderTop: "1px solid rgba(148,163,184,0.2)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                    <i className="fa fa-eye" style={{ color: "#facc15" }} />
                    <b style={{ fontSize: 13 }}>Preview del correo (autorizá con "Enviar a Mesa")</b>
                    <span style={{ marginLeft: "auto", fontSize: 11, opacity: 0.7 }}>
                      UF día: <b>{Number(emailModal.preview.uf_valor || ufValue).toLocaleString('es-CL')}</b>
                    </span>
                  </div>
                  {(emailModal.preview.missing_docs || []).length > 0 && (
                    <div data-testid="email-missing-docs-warning" style={{ marginBottom: 8, padding: "8px 12px", borderRadius: 0, background: "rgba(225,29,72,0.12)", border: "1px solid rgba(225,29,72,0.5)", color: "#fda4af", fontSize: 12 }}>
                      <b>🚫 Documentación incompleta — faltan:</b> {emailModal.preview.missing_docs.join(" · ")}
                      <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8, cursor: "pointer", color: "#fecaca", fontWeight: 600 }}>
                        <input type="checkbox" checked={!!emailModal.force_incompleto}
                          onChange={(e) => setEmailModal({ ...emailModal, force_incompleto: e.target.checked })}
                          data-testid="email-force-incompleto" style={{ accentColor: "#e11d48" }} />
                        Asumo el envío manual con documentación incompleta
                      </label>
                    </div>
                  )}
                  {emailModal.editBody != null ? (
                    <div>
                      <textarea value={emailModal.editBody} data-testid="email-body-editor"
                        onChange={(e) => setEmailModal({ ...emailModal, editBody: e.target.value })}
                        rows={12}
                        style={{ width: "100%", padding: "0.6rem 0.8rem", borderRadius: 0, border: "1px solid rgba(250,204,21,0.5)", background: "#232326", color: "#e2e8f0", fontSize: 12, fontFamily: "monospace", resize: "vertical" }} />
                      <div style={{ marginTop: 6, background: "#fff", color: "#111", borderRadius: 0, padding: "0.6rem 0.8rem", maxHeight: 200, overflow: "auto", border: "1px solid rgba(148,163,184,0.3)" }}
                           dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(emailModal.editBody) }} />
                      <button onClick={() => setEmailModal({ ...emailModal, editBody: null })} data-testid="email-body-reset"
                        style={{ marginTop: 6, background: "transparent", border: "1px solid rgba(148,163,184,0.3)", color: "#94a3b8", borderRadius: 0, padding: "4px 10px", cursor: "pointer", fontSize: 12 }}>
                        <i className="fa fa-undo" /> Volver al cuerpo automático
                      </button>
                    </div>
                  ) : (
                    <div>
                      <div style={{ background: "#fff", color: "#111", borderRadius: 0, padding: "0.6rem 0.8rem", maxHeight: 320, overflow: "auto", border: "1px solid rgba(148,163,184,0.3)" }}
                           dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(emailModal.preview.body_html || emailModal.preview.body) }} />
                      <button onClick={() => setEmailModal({ ...emailModal, editBody: emailModal.preview.body_html || emailModal.preview.body || "" })} data-testid="email-body-edit-btn"
                        style={{ marginTop: 6, background: "rgba(250,204,21,0.15)", border: "1px solid rgba(250,204,21,0.5)", color: "#facc15", borderRadius: 0, padding: "4px 10px", cursor: "pointer", fontSize: 12, fontWeight: 600 }}>
                        <i className="fa fa-pencil" /> Editar cuerpo manualmente
                      </button>
                    </div>
                  )}
                  {emailModal.preview.attachments?.length > 0 && (
                    <div style={{ marginTop: 8, fontSize: 12, color: "#d4af37" }}>
                      <b>Adjuntos:</b> {emailModal.preview.attachments.map(a => `📎 ${a}`).join("  ·  ")}
                    </div>
                  )}
                </div>
              )}
              <div style={{ padding: "0.8rem 1.1rem", borderTop: "1px solid rgba(148,163,184,0.2)", display: "flex", gap: 8, justifyContent: "flex-end" }}>
                <button onClick={closeEmailModal} disabled={emailModal.sending} style={{ background: "transparent", border: "1px solid rgba(148,163,184,0.3)", color: "#94a3b8", borderRadius: 0, padding: "6px 14px", cursor: "pointer", fontSize: 13 }}>Cancelar</button>
                {!emailModal.preview ? (
                  <button onClick={previewClientEmail} disabled={emailModal.sending || !emailModal.to} data-testid="btn-email-preview"
                    style={{ background: !emailModal.to ? "rgba(148,163,184,0.15)" : "rgba(250,204,21,0.2)", border: `1px solid ${!emailModal.to ? "rgba(148,163,184,0.3)" : "rgba(250,204,21,0.6)"}`, color: !emailModal.to ? "#94a3b8" : "#facc15", borderRadius: 0, padding: "6px 14px", cursor: (emailModal.sending || !emailModal.to) ? "not-allowed" : "pointer", fontSize: 13, fontWeight: 600 }}
                    title={!emailModal.to ? "Completá el destinatario primero" : "Generar preview"}>
                    <i className={`fa ${emailModal.sending ? "fa-spinner fa-spin" : "fa-eye"}`} /> {emailModal.sending ? "Generando…" : (!emailModal.to ? "Completá destinatario" : "Ver Preview")}
                  </button>
                ) : (
                  <>
                    <button onClick={() => setEmailModal({ ...emailModal, preview: null })} disabled={emailModal.sending}
                      style={{ background: "transparent", border: "1px solid rgba(148,163,184,0.3)", color: "#94a3b8", borderRadius: 0, padding: "6px 14px", cursor: "pointer", fontSize: 13 }}>
                      <i className="fa fa-pencil" /> Editar
                    </button>
                    <button onClick={async () => {
                        await toggleEnvioManual({ ...emailModal.folder, envio_manual: false });
                        closeEmailModal();
                      }} disabled={emailModal.sending} data-testid="btn-marcar-enviado"
                      title="Marca la carpeta como ENVIADA manualmente (la pinta roja) sin enviar el correo"
                      style={{ background: "#ec4899", border: "1px solid #be185d", color: "#fff", borderRadius: 0, padding: "6px 14px", cursor: "pointer", fontSize: 13, fontWeight: 700 }}>
                      <i className="fa fa-check" /> Marcar como enviado
                    </button>
                    {(() => {
                      const df = emailModal.folder.datos_financieros || {};
                      const conSub = df.con_subsidio ?? (emailModal.folder.credit_request?.subsidy?.tipo === "con_subsidio");
                      const vp = Number(df.valor_propiedad || 0);
                      const mc = Number(df.monto_credito || 0);
                      const bloq80 = !conSub && vp > 0 && mc > 0 && mc > vp * 0.8 + 0.01;
                      const md = emailModal.preview?.missing_docs || [];
                      const bloqDocs = md.length > 0 && !emailModal.force_incompleto;
                      const bloqueado = bloq80 || bloqDocs;
                      const label = emailModal.sending ? "Enviando…"
                        : bloq80 ? "🚫 Bloqueado por regla 80%"
                        : bloqDocs ? "🚫 Faltan documentos"
                        : "Enviar a Mesa";
                      const title = bloq80
                        ? `🚫 BLOQUEADO: crédito ${mc.toFixed(2)} UF supera el 80% (${(vp * 0.8).toFixed(2)} UF) — SIN subsidio no permite más del 80%`
                        : bloqDocs
                        ? `🚫 BLOQUEADO: faltan ${md.join(", ")}. Marcá "Asumo el envío manual" para enviar igual.`
                        : "Enviar correo revisado directo a mesa";
                      return (
                        <button onClick={confirmSendClientEmail} disabled={emailModal.sending || bloqueado} data-testid="btn-email-send" title={title}
                          style={{
                            background: bloqueado ? "#7f1d1d" : "#10c98a",
                            border: `1px solid ${bloqueado ? "#450a0a" : "#0e9f6e"}`,
                            color: "#fff", borderRadius: 0, padding: "6px 18px",
                            cursor: (emailModal.sending || bloqueado) ? "not-allowed" : "pointer",
                            fontSize: 13, fontWeight: 700,
                            boxShadow: bloqueado ? "none" : "0 2px 8px rgba(22,163,74,0.4)",
                            opacity: bloqueado ? 0.6 : 1,
                          }}>
                          <i className={`fa ${emailModal.sending ? "fa-spinner fa-spin" : "fa-paper-plane"}`} /> {label}
                        </button>
                      );
                    })()}
                  </>
                )}
              </div>
            </div>
          </div>
        );
      })()}
      {/* HISTORIAL MODAL */}
      {historialModal && (
        <div data-testid="historial-modal" onClick={() => setHistorialModal(null)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9998, padding: "3vh 3vw" }}>
          <div onClick={(e) => e.stopPropagation()} style={{ background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", color: "#e2e8f0", borderRadius: 0, width: "min(640px, 96vw)", maxHeight: "90vh", overflow: "auto", border: "1px solid rgba(212,175,55,0.4)", boxShadow: "0 20px 60px rgba(0,0,0,0.6)" }}>
            <div style={{ padding: "0.9rem 1.1rem", borderBottom: "1px solid rgba(148,163,184,0.2)", display: "flex", alignItems: "center", gap: 10, position: "sticky", top: 0, background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)" }}>
              <i className="fa fa-history" style={{ color: "#d4af37" }} />
              <h4 style={{ margin: 0, flex: 1 }}>Historial — {historialModal.folder.nombre}</h4>
              <button onClick={() => setHistorialModal(null)} data-testid="btn-historial-close" style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: 18 }}><i className="fa fa-times" /></button>
            </div>
            <div style={{ padding: "1rem 1.1rem" }}>
              {historialModal.loading ? (
                <div style={{ opacity: 0.7 }}><i className="fa fa-spinner fa-spin" /> Cargando historial…</div>
              ) : historialModal.eventos.length === 0 ? (
                <div style={{ opacity: 0.7 }} data-testid="historial-vacio">Sin actividades registradas todavía.</div>
              ) : (
                <div>
                  {historialModal.eventos.map((ev, i) => (
                    <div key={i} data-testid={`historial-evento-${i}`} style={{ display: "flex", gap: 12, padding: "0.55rem 0", borderBottom: i < historialModal.eventos.length - 1 ? "1px solid rgba(148,163,184,0.12)" : "none" }}>
                      <div style={{ fontSize: 17, width: 26, textAlign: "center" }}>{ev.icono}</div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 700, fontSize: 13 }}>{ev.titulo}</div>
                        {ev.detalle && <div style={{ fontSize: 11.5, opacity: 0.7 }}>{ev.detalle}</div>}
                      </div>
                      <div style={{ fontSize: 11.5, color: "#d4af37", fontWeight: 700, whiteSpace: "nowrap" }}>{fmtActFull(ev.fecha)}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
      {/* MISSING DOCS MODAL */}
      {missingDocsModal && (() => {
        const p = missingDocsModal.preview;
        return (
          <div data-testid="missing-docs-modal" onClick={closeMissingDocsModal} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9998, padding: "3vh 3vw" }}>
            <div onClick={(e) => e.stopPropagation()} style={{ background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", color: "#e2e8f0", borderRadius: 0, width: "min(760px, 96vw)", maxHeight: "94vh", overflow: "auto", border: "1px solid rgba(225,29,72,0.5)", boxShadow: "0 20px 60px rgba(0,0,0,0.6)" }}>
              <div style={{ padding: "0.9rem 1.1rem", borderBottom: "1px solid rgba(148,163,184,0.2)", display: "flex", alignItems: "center", gap: 10 }}>
                <i className="fa fa-exclamation-triangle" style={{ color: "#fb7185" }} />
                <h4 style={{ margin: 0, flex: 1 }}>Correo de documento faltante — {missingDocsModal.folder.nombre}</h4>
                <button onClick={closeMissingDocsModal} style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: 18 }}><i className="fa fa-times" /></button>
              </div>
              <div style={{ padding: "1rem 1.1rem", display: "grid", gap: "0.75rem" }}>
                {p && (
                  <>
                    <div style={{ background: "rgba(225,29,72,0.1)", borderRadius: 0, padding: "0.7rem 0.9rem", fontSize: 13 }}>
                      <div style={{ opacity: 0.7, fontSize: 11, textTransform: "uppercase", marginBottom: 4 }}>Detección automática</div>
                      <div><b>Cliente tipo:</b> {p.client_type}</div>
                      <div><b>Documentos presentes:</b> {p.present.join(", ") || "ninguno"}</div>
                      <div style={{ color: "#fb7185" }}><b>Documentos faltantes:</b> {p.missing.length > 0 ? p.missing.join(", ") : "ninguno detectado"}</div>
                      {p.source_email && <div style={{ opacity: 0.75, fontSize: 12, marginTop: 4 }}><b>Origen:</b> {p.source_email}</div>}
                    </div>
                    <label style={{ fontSize: 12 }}><b style={{ display: "block", marginBottom: 4 }}>Destinatario *</b>
                      <input type="email" value={missingDocsModal.to} onChange={(e) => setMissingDocsModal({ ...missingDocsModal, to: e.target.value })} onBlur={refreshMissingDocsPreview} data-testid="missing-to" style={{ width: "100%", padding: "0.5rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.3)", background: "#232326", color: "#e2e8f0", fontSize: 13 }} />
                    </label>
                    <label style={{ fontSize: 12 }}><b style={{ display: "block", marginBottom: 4 }}>Mensaje adicional (opcional)</b>
                      <textarea value={missingDocsModal.extra} onChange={(e) => setMissingDocsModal({ ...missingDocsModal, extra: e.target.value })} onBlur={refreshMissingDocsPreview} rows={2} data-testid="missing-extra" style={{ width: "100%", padding: "0.5rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.3)", background: "#232326", color: "#e2e8f0", fontSize: 13 }} />
                    </label>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                        <i className="fa fa-eye" style={{ color: "#facc15" }} />
                        <b style={{ fontSize: 12 }}>Preview (Asunto: <span style={{ color: "#facc15" }}>{p.subject}</span>)</b>
                      </div>
                      <div style={{ background: "#fff", color: "#111", borderRadius: 0, padding: "0.6rem 0.8rem", maxHeight: 280, overflow: "auto", border: "1px solid rgba(148,163,184,0.3)" }}
                           dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(p.body_html) }} />
                    </div>
                  </>
                )}
              </div>
              <div style={{ padding: "0.8rem 1.1rem", borderTop: "1px solid rgba(148,163,184,0.2)", display: "flex", gap: 8, justifyContent: "flex-end" }}>
                <button onClick={closeMissingDocsModal} disabled={missingDocsModal.sending} style={{ background: "transparent", border: "1px solid rgba(148,163,184,0.3)", color: "#94a3b8", borderRadius: 0, padding: "6px 14px", cursor: "pointer", fontSize: 13 }}>Cancelar</button>
                <button onClick={confirmSendMissingDocs} disabled={missingDocsModal.sending || !p} data-testid="btn-missing-send"
                  style={{ background: "#10c98a", border: "1px solid #0e9f6e", color: "#fff", borderRadius: 0, padding: "6px 18px", cursor: "pointer", fontSize: 13, fontWeight: 700, boxShadow: "0 2px 8px rgba(22,163,74,0.4)" }}>
                  <i className={`fa ${missingDocsModal.sending ? "fa-spinner fa-spin" : "fa-paper-plane"}`} /> {missingDocsModal.sending ? "Procesando…" : "Enviar correo"}
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {forzarModal && (() => {
        const m = forzarModal;
        const inpF = { width: "100%", padding: "0.55rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.3)", background: "#232326", color: "#e2e8f0", fontSize: 13 };
        return (
          <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.65)", zIndex: 9998, display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }} onClick={() => !m.forzando && setForzarModal(null)}>
            <div data-testid="forzar-modal" onClick={e => e.stopPropagation()} style={{ background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", border: "1px solid rgba(148,163,184,0.25)", borderRadius: 0, padding: "1.4rem", width: "min(640px, 96vw)", maxHeight: "90vh", overflow: "auto", display: "grid", gap: 10 }}>
              <h3 style={{ margin: 0, fontSize: 15, color: "#f59e0b" }}><i className="fa fa-bolt" /> Forzar Carpeta — buscá por nombre y/o RUT</h3>
              <label style={{ fontSize: 12 }}>Nombre del cliente <span style={{ opacity: 0.6 }}>(al escribir aparecen sugerencias de correos, archivos y carpetas)</span>
                <input data-testid="forzar-nombre" autoFocus style={inpF} value={m.nombre}
                  onChange={e => setForzarModal({ ...m, nombre: e.target.value, msg: "" })} placeholder="Ej: Pedro González" />
              </label>
              <label style={{ fontSize: 12 }}>RUT <span style={{ opacity: 0.6 }}>(opcional — con o sin puntos)</span>
                <input data-testid="forzar-rut" style={inpF} value={m.rut}
                  onChange={e => setForzarModal({ ...m, rut: e.target.value })} placeholder="Ej: 12.345.678-9" />
              </label>
              {m.buscando && <div style={{ fontSize: 12, color: "#94a3b8" }}><i className="fa fa-spinner fa-spin" /> Buscando coincidencias en carpetas, cola y buzón…</div>}
              {m.sug && !m.buscando && (
                <div data-testid="forzar-sugerencias" style={{ display: "grid", gap: 8 }}>
                  {(m.sug.carpetas || []).length > 0 && (
                    <div style={{ background: "rgba(212,175,55,0.06)", border: "1px dashed rgba(212,175,55,0.4)", borderRadius: 0, padding: "0.6rem 0.8rem" }}>
                      <div style={{ fontSize: 11, fontWeight: 800, color: "#d4af37", marginBottom: 4 }}>📁 CARPETAS EXISTENTES ({m.sug.carpetas.length})</div>
                      {m.sug.carpetas.map(c => <div key={c.id} style={{ fontSize: 12.5 }}>• {c.nombre} {c.rut && <span style={{ opacity: 0.6 }}>· {c.rut}</span>} — {c.archivos} archivo(s)</div>)}
                    </div>
                  )}
                  {(m.sug.correos || []).length > 0 && (
                    <div style={{ background: "rgba(212,175,55,0.06)", border: "1px dashed rgba(212,175,55,0.4)", borderRadius: 0, padding: "0.6rem 0.8rem" }}>
                      <div style={{ fontSize: 11, fontWeight: 800, color: "#d4af37", marginBottom: 4 }}>📧 CORREOS EN EL BUZÓN ({m.sug.correos.length}) — marcá uno o varios para descargar exactamente esos</div>
                      {m.sug.correos.map((c, i) => (
                        <label key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: 12, marginBottom: 4, cursor: c.message_id ? "pointer" : "default" }}>
                          {c.message_id && <input type="checkbox" data-testid={`forzar-correo-sel-${i}`} checked={!!c.sel}
                            onChange={() => setForzarModal(prev => ({ ...prev, sug: { ...prev.sug, correos: prev.sug.correos.map((x, j) => j === i ? { ...x, sel: !x.sel } : x) } }))} />}
                          <span>• <b>{(c.subject || "").slice(0, 60)}</b><br /><span style={{ opacity: 0.6, fontSize: 11 }}>{(c.from || "").slice(0, 50)} · {(c.date || "").slice(0, 22)}</span></span>
                        </label>
                      ))}
                    </div>
                  )}
                  {(m.sug.cola || []).length > 0 && (
                    <div style={{ background: "rgba(46,92,230,0.06)", border: "1px dashed rgba(46,92,230,0.4)", borderRadius: 0, padding: "0.6rem 0.8rem" }}>
                      <div style={{ fontSize: 11, fontWeight: 800, color: "#a78bfa", marginBottom: 4 }}>📥 EN LA COLA DE PROCESAMIENTO ({m.sug.cola.length})</div>
                      {m.sug.cola.map((c, i) => <div key={i} style={{ fontSize: 12 }}>• {(c.subject || "").slice(0, 55)} — {c.adjuntos} adjunto(s)</div>)}
                    </div>
                  )}
                  {!(m.sug.carpetas || []).length && !(m.sug.correos || []).length && !(m.sug.cola || []).length && (
                    <div style={{ fontSize: 12, color: "#fb7185" }}>Sin coincidencias por ahora — podés forzar igual y el sistema hará la búsqueda profunda (cuerpo de correos incluido).</div>
                  )}
                </div>
              )}
              {m.msg && <div data-testid="forzar-msg" style={{ fontSize: 12.5, fontWeight: 700, color: m.msg.startsWith("✅") ? "#34eab9" : "#fb7185" }}>{m.msg}</div>}
              <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                <button onClick={() => setForzarModal(null)} disabled={m.forzando} style={{ background: "transparent", border: "1px solid rgba(148,163,184,0.3)", color: "#94a3b8", borderRadius: 0, padding: "0.55rem 1rem", fontSize: 12.5, cursor: "pointer" }}>Cerrar</button>
                <button data-testid="forzar-ejecutar" onClick={ejecutarForzar} disabled={m.forzando || (!m.nombre.trim() && !m.rut.trim())}
                  style={{ background: "#f59e0b", border: "none", color: "#101012", borderRadius: 0, padding: "0.55rem 1.3rem", fontSize: 12.5, fontWeight: 800, cursor: "pointer" }}>
                  <i className={`fa ${m.forzando ? "fa-spinner fa-spin" : "fa-bolt"}`} /> {m.forzando ? "Forzando (busca y descarga adjuntos)…" : "Forzar Carpeta"}
                </button>
              </div>
            </div>
          </div>
        );
      })()}

      {reparosModal && (() => {
        const m = reparosModal;
        const rep = m.data?.reparos || {};
        const items = rep.items || [];
        const vendedor = m.data?.vendedor || {};
        const satisfecho = rep.estado === "satisfecho";
        const pendientes = items.filter(i => !i.satisfecho).length;
        const fmtF = (iso) => iso ? new Date(iso).toLocaleString("es-CL", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "";
        return (
          <div data-testid="reparos-modal" onClick={() => setReparosModal(null)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9998, padding: "3vh 3vw" }}>
            <div onClick={(e) => e.stopPropagation()} style={{ background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", color: "#e2e8f0", borderRadius: 0, width: "min(720px, 96vw)", maxHeight: "94vh", overflow: "auto", border: "1px solid rgba(148,163,184,0.25)", boxShadow: "0 20px 60px rgba(0,0,0,0.6)" }}>
              <div style={{ padding: "0.9rem 1.1rem", borderBottom: "1px solid rgba(148,163,184,0.2)", display: "flex", alignItems: "center", gap: 10 }}>
                <i className="fa fa-gavel" style={{ color: satisfecho ? "#34eab9" : "#fb7185" }} />
                <h4 style={{ margin: 0, flex: 1 }}>Reparos Estudio de Título — {m.folder.nombre}</h4>
                <button onClick={() => setReparosModal(null)} data-testid="btn-reparos-close" style={{ background: "transparent", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: 18 }}><i className="fa fa-times" /></button>
              </div>
              <div style={{ padding: "1rem 1.1rem", display: "grid", gap: "0.75rem" }}>
                {m.msg && (
                  <div data-testid="reparos-msg" style={{ padding: "0.6rem 0.9rem", borderRadius: 0, background: m.msg.startsWith("Error") ? "rgba(225,29,72,0.15)" : "rgba(16,217,142,0.15)", color: m.msg.startsWith("Error") ? "#fb7185" : "#34eab9", fontWeight: 600, fontSize: 13 }}>{m.msg}</div>
                )}
                {m.loading ? (
                  <div style={{ textAlign: "center", padding: "1.5rem" }}><i className="fa fa-spinner fa-spin" /> Cargando reparos…</div>
                ) : (
                  <>
                    <div style={{ fontSize: 12, color: "#94a3b8", background: "rgba(148,163,184,0.07)", border: "1px solid rgba(148,163,184,0.15)", borderRadius: 0, padding: "0.6rem 0.9rem", display: "grid", gap: 3 }}>
                      <div>🤖 El sistema revisa automáticamente el <b>hilo del correo</b> del estudio de título. Cuando el abogado envía reparos, se reenvían de inmediato al vendedor (CC Victoria Vilches).</div>
                      {rep.abogado_email && <div>⚖ Abogado detectado en el hilo: <b style={{ color: "#e2e8f0" }}>{rep.abogado_email}</b></div>}
                      {vendedor.email && <div>🏠 Vendedor: <b style={{ color: "#e2e8f0" }}>{vendedor.nombre || "—"}</b> · {vendedor.email}{vendedor.telefono ? ` · ${vendedor.telefono}` : ""}</div>}
                      {!vendedor.email && <div style={{ color: "#facc15" }}>⚠️ No hay correo del vendedor registrado — el reenvío automático de reparos no podrá enviarse.</div>}
                      {rep.detectado_en && <div>📥 Primeros reparos detectados: {fmtF(rep.detectado_en)}</div>}
                      {rep.reenviado_vendedor_at && <div>📤 Reparos reenviados al vendedor: {fmtF(rep.reenviado_vendedor_at)}</div>}
                      {rep.reenvio_vendedor_error && <div style={{ color: "#fb7185" }}>⚠️ Reenvío al vendedor: {rep.reenvio_vendedor_error}</div>}
                      {rep.recordatorio_enviado_at && <div>⏰ Recordatorio de estado enviado al abogado: {fmtF(rep.recordatorio_enviado_at)}</div>}
                      {m.data?.tipo_vivienda === "usada" && !rep.recordatorio_enviado_at && !satisfecho && items.length > 0 && (
                        <div>⏰ Vivienda usada: si a los 5 días no hay avance, se consultará el estado en el mismo hilo (una vez).</div>
                      )}
                    </div>

                    {items.length === 0 ? (
                      <div style={{ textAlign: "center", padding: "1rem", color: "#94a3b8", fontSize: 13 }} data-testid="reparos-vacio">
                        Aún no se han detectado reparos del abogado en el hilo de este estudio de título.
                      </div>
                    ) : (
                      <div style={{ display: "grid", gap: 6 }}>
                        {items.map((it) => (
                          <label key={it.n} data-testid={`reparo-item-${it.n}`} style={{ display: "flex", alignItems: "flex-start", gap: 10, background: it.satisfecho ? "rgba(16,217,142,0.08)" : "rgba(225,29,72,0.06)", border: `1px solid ${it.satisfecho ? "rgba(16,217,142,0.35)" : "rgba(225,29,72,0.25)"}`, borderRadius: 0, padding: "0.6rem 0.9rem", cursor: "pointer" }}>
                            <input type="checkbox" checked={!!it.satisfecho} onChange={(e) => toggleReparo(it.n, e.target.checked)} data-testid={`reparo-check-${it.n}`} style={{ marginTop: 3, width: 16, height: 16, accentColor: "#10d98e", cursor: "pointer" }} />
                            <div style={{ flex: 1 }}>
                              <div style={{ fontSize: 13, color: it.satisfecho ? "#6ee7c7" : "#e2e8f0", textDecoration: it.satisfecho ? "line-through" : "none" }}>{it.n}. {it.texto}</div>
                              <div style={{ fontSize: 11, color: it.satisfecho ? "#34eab9" : "#fb7185", fontWeight: 700, marginTop: 2 }}>
                                {it.satisfecho ? `✅ Reparo aceptado${it.satisfecho_en ? ` · ${fmtF(it.satisfecho_en)}` : ""}` : "Pendiente — marcar la casilla \"Reparo aceptado\" cuando quede resuelto"}
                              </div>
                            </div>
                          </label>
                        ))}
                      </div>
                    )}

                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "flex-end", borderTop: "1px solid rgba(148,163,184,0.15)", paddingTop: "0.8rem" }}>
                      <button onClick={scanReparos} disabled={m.scanning} data-testid="btn-reparos-scan"
                        style={{ background: "rgba(212,175,55,0.15)", border: "1px solid #d4af37", color: "#d4af37", borderRadius: 0, padding: "8px 14px", cursor: "pointer", fontSize: 13, fontWeight: 700 }}>
                        <i className={`fa ${m.scanning ? "fa-spinner fa-spin" : "fa-refresh"}`} /> {m.scanning ? "Revisando hilo…" : "Buscar reparos ahora"}
                      </button>
                      {satisfecho ? (
                        <div data-testid="reparos-satisfecho-badge" style={{ background: "rgba(16,217,142,0.15)", border: "1px solid #10d98e", color: "#34eab9", borderRadius: 0, padding: "8px 14px", fontSize: 13, fontWeight: 700 }}>
                          ✅ Todos los reparos satisfechos {rep.declarado_satisfecho_at ? `· ${fmtF(rep.declarado_satisfecho_at)}` : ""} {rep.declarado_por === "abogado" ? "(confirmado por el abogado)" : ""}
                        </div>
                      ) : (
                        <button onClick={declararReparos} disabled={m.declarando || items.length === 0 || pendientes > 0} data-testid="btn-reparos-declarar"
                          title={pendientes > 0 ? `Faltan ${pendientes} reparo(s) por marcar como satisfechos` : ""}
                          style={{ background: (m.declarando || items.length === 0 || pendientes > 0) ? "#475569" : "#10c98a", border: "none", color: "#fff", borderRadius: 0, padding: "8px 16px", cursor: (items.length === 0 || pendientes > 0) ? "not-allowed" : "pointer", fontSize: 13, fontWeight: 700 }}>
                          <i className={`fa ${m.declarando ? "fa-spinner fa-spin" : "fa-check-circle"}`} /> {m.declarando ? "Enviando aviso…" : "Declaro que todos los reparos han sido recibidos satisfactoriamente y podemos continuar con el estudio de título"}
                        </button>
                      )}
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        );
      })()}
      {codeudorModal && (
        <div data-testid="codeudor-modal" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.82)", zIndex: 3000, display: "flex", alignItems: "center", justifyContent: "center", backdropFilter: "blur(6px)" }}
          onClick={() => setCodeudorModal(null)}>
          <div onClick={e => e.stopPropagation()} style={{ width: 420, maxWidth: "92vw", background: "linear-gradient(160deg, rgba(22,22,24,0.98), rgba(8,8,9,0.99))", border: "1px solid rgba(212,175,55,0.45)", borderRadius: 0, padding: "1.6rem 1.7rem", boxShadow: "0 40px 90px -20px rgba(0,0,0,0.95), 0 0 44px -14px rgba(191,149,63,0.4)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: "1.1rem" }}>
              <i className="fa fa-user-plus" style={{ color: "var(--gold)" }} />
              <span style={{ fontSize: "0.95rem", fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "#fff" }}>Agregar Codeudor</span>
            </div>
            <div style={{ fontSize: "0.75rem", opacity: 0.65, marginBottom: "1rem" }}>Carpeta titular: <b style={{ color: "var(--gold)" }}>{codeudorModal.nombre}</b></div>
            <label style={{ fontSize: "0.7rem", letterSpacing: "0.1em", textTransform: "uppercase", opacity: 0.7 }}>Nombre del codeudor</label>
            <input data-testid="codeudor-nombre-input" value={codeudorForm.nombre} onChange={e => setCodeudorForm(p => ({ ...p, nombre: e.target.value }))}
              placeholder="Ej: Ángel Mayorga Soto" style={{ width: "100%", margin: "6px 0 14px", background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 0, color: "#fff", padding: "10px 12px", fontSize: "0.9rem" }} />
            <label style={{ fontSize: "0.7rem", letterSpacing: "0.1em", textTransform: "uppercase", color: "#e8cf7f", fontWeight: 700 }}>RUT del codeudor (obligatorio)</label>
            <input data-testid="codeudor-rut-input" value={codeudorForm.rut} onChange={e => setCodeudorForm(p => ({ ...p, rut: e.target.value }))}
              placeholder="12.345.678-9" style={{ width: "100%", margin: "6px 0 6px", background: "rgba(212,175,55,0.08)", border: "1px solid rgba(212,175,55,0.55)", borderRadius: 0, color: "#f4dc82", fontWeight: 700, letterSpacing: "0.06em", padding: "10px 12px", fontSize: "0.95rem", fontFamily: "'JetBrains Mono', monospace" }} />
            <div style={{ fontSize: "0.68rem", color: "rgba(232,207,127,0.75)", marginBottom: "1.2rem" }}>
              <i className="fa fa-link" style={{ marginRight: 5 }} />Todo documento entrante con este RUT irá directo a la subcarpeta 05_Codeudor del titular — sin crear carpetas nuevas.
            </div>
            <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
              <button data-testid="codeudor-cancelar-btn" onClick={() => setCodeudorModal(null)} style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.25)", color: "#cbd5e1", borderRadius: 0, padding: "9px 16px", cursor: "pointer", fontSize: "0.8rem" }}>Cancelar</button>
              <button data-testid="codeudor-guardar-btn" onClick={guardarCodeudor} style={{ background: "linear-gradient(135deg, #BF953F, #FCF6BA 45%, #B38728)", border: "none", color: "#141414", fontWeight: 800, borderRadius: 0, padding: "9px 20px", cursor: "pointer", fontSize: "0.8rem", letterSpacing: "0.05em" }}>
                <i className="fa fa-check" style={{ marginRight: 6 }} />Vincular Codeudor
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
