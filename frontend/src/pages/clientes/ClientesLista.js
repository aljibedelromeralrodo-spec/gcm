import CalendarioCarpetas from "../../components/CalendarioCarpetas";
import { CAT_LABELS, rutValido } from "./clientesShared";
import { useClientes } from "./clientesCtx";

export default function ClientesLista() {
  const {
    ajustes,
    cloudSync,
    countClientes,
    countEscrituracion,
    createFolder,
    deleteFolder,
    emails,
    enriching,
    enriquecerCarpeta,
    enviarLinkPagoMora,
    evalNeg,
    filtered,
    fmtAct,
    folderTab,
    loadAjustes,
    loadEmails,
    loading,
    marcarTerminado,
    moraMsg,
    moraUp,
    newFolder,
    notificandoNC,
    notificarNoCalifico,
    openEscritura,
    openEstudio,
    openFolder,
    openHistorial,
    openPedirFaltantes,
    openReparos,
    openTasacion,
    searchQuery,
    setCompromisoLibre,
    setFolderTab,
    setForzarModal,
    setNewFolder,
    setSearchQuery,
    setShowCreate,
    showCreate,
    subirComprobanteMora,
    syncMsg,
    syncing,
    techo,
    toggleEnvioManual,
    toggleEscrituracion,
    view,
    onNavigate
  } = useClientes();
  return (
        <div data-testid="clientes-list">
          <div className="clientes-toolbar">
            <div className="clientes-search">
              <i className="fa fa-search"></i>
              <input type="text" placeholder="Buscar cliente..." value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)} data-testid="clientes-search" />
            </div>
            <div className="clientes-toolbar-actions">
              <button className="docs-btn" data-testid="btn-cloud-sync" onClick={cloudSync} disabled={syncing}
                title="Para sincronizar cambios de diseño o nuevas funciones, use el botón Re-publish de la plataforma"
                style={{ background: "linear-gradient(135deg, #BF953F, #FCF6BA, #B38728)", color: "#0a0a0a", fontWeight: 800, border: "none", borderRadius: 0, opacity: syncing ? 0.6 : 1 }}>
                <i className={`fa ${syncing ? "fa-spinner fa-spin" : "fa-gem"}`}></i> {syncing ? "Sincronizando…" : "💎 Sincronizar Datos (Cloud Sync)"}
              </button>
              <span data-testid="cloud-sync-status"
                title="Para sincronizar cambios de diseño o nuevas funciones, use el botón Re-publish de la plataforma"
                style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: "0.72rem", fontWeight: 700, letterSpacing: "0.5px", color: "#10d98e", border: "1px solid rgba(16,217,142,0.35)", padding: "0.35rem 0.7rem", cursor: "help" }}>
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#10d98e", boxShadow: "0 0 6px #10d98e" }}></span>
                Sincronización: {window.location.hostname.includes("preview") ? "Preview" : "Live"} · Conexión Protegida
              </span>
              <button className="docs-btn secondary" onClick={loadEmails} data-testid="btn-view-emails">
                <i className="fa fa-envelope"></i> Ver Correos
              </button>
              <button className="docs-btn secondary" onClick={loadAjustes} data-testid="btn-ajustes">
                <i className="fa fa-sliders"></i> Ajustes
              </button>
              <button className="docs-btn primary" onClick={() => setShowCreate(true)} data-testid="btn-new-folder">
                <i className="fa fa-plus"></i> Nueva Carpeta
              </button>
              <button className="docs-btn secondary" data-testid="btn-forzar-folder"
                onClick={() => setForzarModal({ nombre: "", rut: "", sug: null, buscando: false, forzando: false, msg: "" })}
                style={{ borderColor: "#f59e0b", color: "#f59e0b" }}>
                <i className="fa fa-bolt"></i> Forzar Carpeta
              </button>
              <button className="docs-btn secondary" data-testid="btn-compromiso-independiente"
                onClick={() => setCompromisoLibre({ id: `libre-${Date.now()}`, nombre: "Compromiso Independiente" })}
                style={{ borderColor: "var(--gold, #d4af37)", color: "var(--gold, #d4af37)" }}>
                <i className="fa fa-file-text-o"></i> Compromiso Compraventa
              </button>
            </div>
          </div>

          {syncMsg && (
            <div data-testid="cloud-sync-msg" style={{ margin: "0.6rem 0 0", padding: "0.55rem 0.9rem", fontSize: "0.8rem", fontWeight: 600, background: syncMsg.startsWith("💎") ? "rgba(212,175,55,0.12)" : "rgba(225,29,72,0.12)", border: `1px solid ${syncMsg.startsWith("💎") ? "rgba(212,175,55,0.4)" : "rgba(225,29,72,0.4)"}`, color: syncMsg.startsWith("💎") ? "#d4af37" : "#ff6b8a" }}>
              {syncMsg}
            </div>
          )}

          <div data-testid="folder-tabs" style={{ display: "flex", gap: 8, margin: "0.9rem 0" }}>
            <button data-testid="tab-clientes" onClick={() => setFolderTab("clientes")}
              style={{ padding: "0.55rem 1.2rem", borderRadius: 0, fontWeight: 800, fontSize: 13, cursor: "pointer",
                background: folderTab === "clientes" ? "rgba(212,175,55,0.18)" : "rgba(148,163,184,0.08)",
                border: folderTab === "clientes" ? "2px solid var(--gold, #d4af37)" : "1.5px solid rgba(148,163,184,0.3)",
                color: folderTab === "clientes" ? "var(--gold, #d4af37)" : "#94a3b8" }}>
              <i className="fa fa-folder"></i> Solicitudes de Crédito ({countClientes})
            </button>
            <button data-testid="tab-escrituracion" onClick={() => setFolderTab("escrituracion")}
              style={{ padding: "0.55rem 1.2rem", borderRadius: 0, fontWeight: 800, fontSize: 13, cursor: "pointer",
                background: folderTab === "escrituracion" ? "rgba(46,92,230,0.18)" : "rgba(148,163,184,0.08)",
                border: folderTab === "escrituracion" ? "2px solid #2e5ce6" : "1.5px solid rgba(148,163,184,0.3)",
                color: folderTab === "escrituracion" ? "#2e5ce6" : "#94a3b8" }}>
              <i className="fa fa-pencil-square"></i> Escrituración ({countEscrituracion})
            </button>
            <button data-testid="tab-calendario" onClick={() => setFolderTab("calendario")}
              style={{ padding: "0.55rem 1.2rem", borderRadius: 0, fontWeight: 800, fontSize: 13, cursor: "pointer",
                background: folderTab === "calendario" ? "rgba(212,175,55,0.18)" : "rgba(148,163,184,0.08)",
                border: folderTab === "calendario" ? "2px solid var(--gold, #d4af37)" : "1.5px solid rgba(148,163,184,0.3)",
                color: folderTab === "calendario" ? "var(--gold, #d4af37)" : "#94a3b8" }}>
              <i className="fa fa-calendar"></i> Calendario
            </button>
          </div>

          {folderTab === "calendario" && <CalendarioCarpetas onOpenFolder={(id) => openFolder(id)} />}

          {showCreate && (
            <div className="clientes-create-form" data-testid="create-folder-form">
              <h4>Nueva Carpeta de Cliente</h4>
              <div className="clientes-form-grid">
                <div className="clientes-field">
                  <label>Nombre del Cliente *</label>
                  <input type="text" value={newFolder.nombre} onChange={e => setNewFolder({ ...newFolder, nombre: e.target.value })}
                    placeholder="Ej: Juan Pérez" data-testid="input-folder-nombre" />
                </div>
                <div className="clientes-field">
                  <label>RUT</label>
                  <input type="text" value={newFolder.rut} onChange={e => setNewFolder({ ...newFolder, rut: e.target.value })}
                    placeholder="12.345.678-9" data-testid="input-folder-rut" />
                </div>
                <div className="clientes-field">
                  <label>Codeudor (nombre)</label>
                  <input type="text" value={newFolder.codeudor_nombre} onChange={e => setNewFolder({ ...newFolder, codeudor_nombre: e.target.value })}
                    placeholder="Opcional" data-testid="input-folder-codeudor" />
                </div>
                <div className="clientes-field">
                  <label>RUT Codeudor</label>
                  <input type="text" value={newFolder.codeudor_rut} onChange={e => setNewFolder({ ...newFolder, codeudor_rut: e.target.value })}
                    placeholder="Opcional" />
                </div>
              </div>
              <div className="clientes-form-actions">
                <button className="docs-btn secondary" onClick={() => setShowCreate(false)}>Cancelar</button>
                <button className="docs-btn primary" onClick={createFolder} disabled={loading} data-testid="btn-confirm-create">
                  {loading ? "Creando..." : "Crear Carpeta"}
                </button>
              </div>
            </div>
          )}

          <div className="clientes-grid">
            {filtered.length === 0 && folderTab !== "calendario" && (
              <div className="clientes-empty">
                <i className="fa fa-folder-open-o"></i>
                <p>No hay carpetas de clientes{searchQuery ? " que coincidan" : ""}.</p>
              </div>
            )}
            {filtered.map(f => {
              // Faltantes: backend (perfil + vigencia por mes). Fallback local si el payload es viejo.
              const ct = f.credit_request?.client_type || "";
              const cats = f.credit_request?.doc_categories || [];
              const required = ct === "independiente"
                ? ["cedula", "imp_renta", "boletas", "cmf"]
                : ct === "mixto"
                ? ["cedula", "liquidacion", "afp", "imp_renta", "boletas", "cmf"]
                : (ct === "desconocido" ? ["cedula", "cmf"] : ["cedula", "liquidacion", "afp", "cmf"]);
              const missingCats = (f.validacion_documental?.cats_faltantes?.length)
                ? f.validacion_documental.cats_faltantes
                : required.filter(r => !cats.includes(r));
              const missing = (f.alertas_documentales && f.alertas_documentales.length)
                ? f.alertas_documentales
                : missingCats.map(m => CAT_LABELS[m] || m);
              const hasFin = f.datos_financieros && f.datos_financieros.valor_propiedad;
              const enviadoManual = f.envio_manual === true;
              const cardStyle = enviadoManual
                ? { position: "relative", background: "#be123c", borderLeft: "5px solid #7f1d1d", color: "#fff", flexWrap: "wrap" }
                : { position: "relative", flexWrap: "wrap", borderLeft: (f.emails_sent_count > 0) ? "5px solid #d4af37" : (f.is_ready_to_send ? "5px solid #10d98e" : (f.codeudor_nombre ? "5px solid #2e5ce6" : "")), background: (f.emails_sent_count > 0) ? "rgba(212,175,55,0.06)" : (f.is_ready_to_send ? "rgba(16,217,142,0.06)" : undefined) };
              const irAModulo = (mod) => {
                sessionStorage.setItem("cm_prefill_cliente", JSON.stringify({ nombre: f.nombre, rut: f.rut || "" }));
                onNavigate && onNavigate(mod);
              };
              const modBtn = (bg, border, color, big) => ({
                display: "flex", alignItems: "center", gap: 6, padding: big ? "0.55rem 1rem" : "0.45rem 0.8rem",
                borderRadius: 0, border: `1.5px solid ${border}`, background: bg, color,
                fontWeight: 800, fontSize: big ? 13 : 11.5, cursor: "pointer", whiteSpace: "nowrap",
              });
              return (
                <div key={f.id} className="clientes-card" data-testid={`folder-${f.id}`} style={cardStyle}>
                  {enviadoManual && (
                    <div style={{ position: "absolute", top: 8, left: 8, background: "#fff", color: "#be123c", borderRadius: 0, padding: "2px 8px", fontSize: 10, fontWeight: 800 }} data-testid={`badge-enviado-${f.id}`}>
                      ✅ ENVIADO (manual)
                    </div>
                  )}
                  {missing.length > 0 && (
                    <div title={`Faltan: ${missing.join(", ")}`} style={{ position: "absolute", top: 8, right: 8, background: "#be123c", color: "#fff", borderRadius: "50%", width: 22, height: 22, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, boxShadow: "0 2px 8px rgba(190,18,60,0.5)" }}>
                      {missing.length}
                    </div>
                  )}
                  <div className="clientes-card-icon"><i className="fa fa-folder"></i></div>
                  <div className="clientes-card-info">
                    <h4 style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>{f.nombre}
                      {(f.tasacion_informe_recibido_at || f.estudio_recibido_at) && (
                        <span data-testid={`informe-ok-${f.id}`}
                          title={`Informe recibido${f.tasacion_informe_recibido_at ? " · Tasación " + String(f.tasacion_informe_recibido_at).slice(0, 10) : ""}${f.estudio_recibido_at ? " · Títulos " + String(f.estudio_recibido_at).slice(0, 10) : ""}`}
                          style={{ fontSize: 13 }}>✅</span>
                      )}
                      {((f.reparos_alertas || []).length + ((f.estudio_reparos || {}).items || []).length) > 0 && (
                        <button data-testid={`reparos-btn-${f.id}`}
                          onClick={(ev) => { ev.stopPropagation(); openReparos(f); }}
                          title="Reparos del abogado — pinche para leer el texto íntegro"
                          style={{ cursor: "pointer", border: "none", borderRadius: 8, fontWeight: 800,
                            fontSize: 10, padding: "2px 7px", background: "rgba(239,68,68,0.18)", color: "#ef4444" }}>
                          ⚠️ {(f.reparos_alertas || []).length + ((f.estudio_reparos || {}).items || []).length} reparo(s)
                        </button>
                      )}
                      {evalNeg[f.id] && (
                        <>
                          <span data-testid={`no-califico-${f.id}`}
                            title={`Última evaluación del Motor (${evalNeg[f.id].fecha}): resultado negativo`}
                            style={{ background: "#7f1d1d", color: "#fecaca", fontWeight: 900, fontSize: 10,
                              letterSpacing: 1, padding: "2px 9px", border: "1px solid #ef4444" }}>
                            ⛔ NO CALIFICÓ
                          </span>
                          <button data-testid={`btn-notificar-nc-${f.id}`}
                            disabled={notificandoNC === f.id}
                            onClick={(ev) => { ev.stopPropagation(); notificarNoCalifico(f); }}
                            title={f.no_califico_notificado_at
                              ? `Ya notificado el ${String(f.no_califico_notificado_at).slice(0, 16).replace("T", " ")}`
                              : "Enviar correo al ejecutivo/solicitante informando el resultado negativo"}
                            style={{ cursor: "pointer", border: "1px solid rgba(239,68,68,0.5)", borderRadius: 0,
                              fontWeight: 800, fontSize: 10, padding: "2px 8px",
                              background: "transparent", color: "#f87171" }}>
                            {notificandoNC === f.id ? "Enviando…" : (f.no_califico_notificado_at ? "✓ Notificado" : "📧 Notificar al ejecutivo")}
                          </button>
                        </>
                      )}
                    </h4>
                    {f.rut && <span className="clientes-rut">{f.rut}{rutValido(f.rut) &&
                      <b title="RUT verificado al 100% (dígito verificador módulo 11)" style={{ color: "#22c55e", marginLeft: 4 }}>✓100%</b>}</span>}
                    {f.codeudor_nombre && <span className="clientes-codeudor"><i className="fa fa-user-plus"></i> {f.codeudor_nombre}</span>}
                    <span className="clientes-file-count">{f.total_archivos || 0} archivos</span>
                    <div style={{ display: "flex", gap: 6, marginTop: 4, flexWrap: "wrap" }}>
                      {f.is_ready_to_send && (
                        <span style={{ fontSize: 10, background: "rgba(16,217,142,0.25)", color: "#0e9f6e", padding: "2px 6px", borderRadius: 0, fontWeight: 700 }}>🎯 Lista para enviar</span>
                      )}
                      {f.emails_sent_count > 0 && (
                        <span title={`Último envío: ${(f.last_email_sent_at || "").slice(0,19).replace('T',' ')}`} style={{ fontSize: 10, background: "rgba(212,175,55,0.2)", color: "#0a3d91", padding: "2px 6px", borderRadius: 0, fontWeight: 700 }}>📧 Enviado a mesa × {f.emails_sent_count}{f.last_email_sent_at ? ` · ${fmtAct(f.last_email_sent_at)}` : ""}</span>
                      )}
                      {hasFin ? (
                        <span style={{ fontSize: 10, background: "rgba(16,217,142,0.15)", color: "#10c98a", padding: "2px 6px", borderRadius: 0 }}>💰 Datos OK</span>
                      ) : (
                        <span style={{ fontSize: 10, background: "rgba(250,204,21,0.15)", color: "#a16207", padding: "2px 6px", borderRadius: 0 }}>💰 Sin datos financieros</span>
                      )}
                      {f.datos_financieros?.fecha_entrega && (
                        <span data-testid={`badge-entrega-${f.id}`} style={{ fontSize: 10, background: "rgba(46,92,230,0.15)", color: "#1e46c0", padding: "2px 6px", borderRadius: 0, fontWeight: 700 }}>🏠 Entrega {f.datos_financieros.fecha_entrega}</span>
                      )}
                    </div>
                    {(f.cmf_morosidad?.morosidad_clp > 0) && (
                      <div data-testid={`mora-banner-${f.id}`} onClick={(ev) => ev.stopPropagation()}
                        style={{ marginTop: 6, padding: "0.55rem 0.8rem", borderRadius: 0,
                          background: f.cmf_morosidad.aclarada ? "rgba(16,217,142,0.12)" : "rgba(190,18,60,0.12)",
                          border: `1px solid ${f.cmf_morosidad.aclarada ? "rgba(16,217,142,0.45)" : "rgba(190,18,60,0.45)"}` }}>
                        {f.cmf_morosidad.aclarada ? (
                          <span data-testid={`mora-aclarada-${f.id}`} style={{ fontSize: 11, fontWeight: 800, color: "#0e9f6e" }}>
                            ✅ MORA ACLARADA {String(f.cmf_morosidad.aclarada_at || "").slice(0, 10)} — comprobante validado
                            (${Number(f.cmf_morosidad.comprobante?.monto_detectado || 0).toLocaleString("es-CL")}) · alerta cerrada automáticamente
                          </span>
                        ) : (
                          <>
                            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                              <span style={{ fontSize: 11, fontWeight: 800, color: "#be123c" }}>
                                🧾 MORA CMF: ${Number(f.cmf_morosidad.morosidad_clp).toLocaleString("es-CL")} — la Bóveda no permite morosidad
                              </span>
                              <button data-testid={`mora-link-pago-${f.id}`} disabled={moraUp === f.id}
                                onClick={() => enviarLinkPagoMora(f)}
                                title="Enviar al cliente el monto de la mora y los datos oficiales de transferencia"
                                style={{ cursor: moraUp === f.id ? "wait" : "pointer", fontSize: 10, fontWeight: 800,
                                  padding: "3px 10px", background: "transparent", color: "#d4af37",
                                  border: "1px solid rgba(212,175,55,0.6)" }}>
                                💳 Enviar link de pago al cliente{f.cmf_morosidad.link_pago_enviado_at ? ` ✓ ${String(f.cmf_morosidad.link_pago_enviado_at).slice(0, 10)}` : ""}
                              </button>
                              <label data-testid={`mora-subir-${f.id}`}
                                style={{ cursor: moraUp === f.id ? "wait" : "pointer", fontSize: 10, fontWeight: 800,
                                  padding: "3px 10px", background: "#be123c", color: "#fff",
                                  opacity: moraUp === f.id ? 0.6 : 1 }}>
                                {moraUp === f.id ? "⏳ Validando…" : "📤 Subir comprobante de pago"}
                                <input type="file" accept=".pdf,image/*" style={{ display: "none" }} disabled={moraUp === f.id}
                                  onChange={(ev) => { subirComprobanteMora(f, ev.target.files?.[0], "comprobante"); ev.target.value = ""; }} />
                              </label>
                              <label data-testid={`mora-formulario-${f.id}`}
                                title="Formulario manual de regularización (convenio / compromiso de pago)"
                                style={{ cursor: moraUp === f.id ? "wait" : "pointer", fontSize: 10, fontWeight: 800,
                                  padding: "3px 10px", background: "transparent", color: "#be123c",
                                  border: "1px solid rgba(190,18,60,0.6)", opacity: moraUp === f.id ? 0.6 : 1 }}>
                                📋 Subir formulario de regularización
                                <input type="file" accept=".pdf,image/*" style={{ display: "none" }} disabled={moraUp === f.id}
                                  onChange={(ev) => { subirComprobanteMora(f, ev.target.files?.[0], "formulario"); ev.target.value = ""; }} />
                              </label>
                            </div>
                            <div style={{ fontSize: 10, color: "#9f1239", marginTop: 3 }}>
                              Al subir comprobante o formulario, el sistema valida y cierra la alerta automáticamente (sin pasar por el administrador).
                            </div>
                          </>
                        )}
                        {moraMsg[f.id] && (
                          <div data-testid={`mora-msg-${f.id}`} style={{ marginTop: 5, fontSize: 11, fontWeight: 700,
                            color: moraMsg[f.id].ok ? "#0e9f6e" : "#be123c" }}>
                            {moraMsg[f.id].texto}
                          </div>
                        )}
                      </div>
                    )}
                    {missing.length > 0 && (
                      <div data-testid={`missing-docs-${f.id}`} style={{ display: "flex", gap: 4, marginTop: 5, flexWrap: "wrap", alignItems: "center" }}>
                        <span style={{ fontSize: 10, fontWeight: 800, color: enviadoManual ? "#fff" : "#be123c" }}>⚠️ FALTA:</span>
                        {missing.map((m, i) => (
                          <span key={`${m}-${i}`} style={{ fontSize: 10, fontWeight: 700, background: enviadoManual ? "rgba(255,255,255,0.25)" : "rgba(190,18,60,0.15)", color: enviadoManual ? "#fff" : "#be123c", padding: "2px 7px", borderRadius: 0, border: enviadoManual ? "1px solid rgba(255,255,255,0.4)" : "1px solid rgba(190,18,60,0.35)" }}>
                            {m}
                          </span>
                        ))}
                      </div>
                    )}
                    {(f.criterios || []).length > 0 && (
                      <div data-testid={`criterios-list-${f.id}`} style={{ display: "flex", gap: 4, marginTop: 5, flexWrap: "wrap", alignItems: "center" }}>
                        {f.criterios.map(c => (
                          <span key={c.nombre} title={c.nombre} style={{ fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 0,
                            background: enviadoManual ? "rgba(255,255,255,0.2)" : (c.ok ? "rgba(16,217,142,0.12)" : "rgba(148,163,184,0.12)"),
                            color: enviadoManual ? "#fff" : (c.ok ? "#10c98a" : "#94a3b8"),
                            border: `1px solid ${c.ok ? "rgba(16,217,142,0.4)" : "rgba(148,163,184,0.3)"}` }}>
                            {c.ok ? "✓" : "✗"} {c.nombre}
                          </span>
                        ))}
                      </div>
                    )}
                    <div style={{ display: "flex", gap: 8, marginTop: 5, alignItems: "center", flexWrap: "wrap" }}>
                      {f.source_email && (
                        <span data-testid={`recibido-de-${f.id}`} style={{ fontSize: 10.5, opacity: 0.75, color: enviadoManual ? "#fff" : undefined }}>
                          📥 Solicitud recibida de: <b>{f.source_email}</b>
                        </span>
                      )}
                      {missing.length > 0 && f.source_email && (
                        <button data-testid={`btn-pedir-faltantes-${f.id}`} onClick={() => openPedirFaltantes(f)}
                          style={{ fontSize: 10.5, fontWeight: 800, padding: "3px 10px", borderRadius: 0, cursor: "pointer",
                            background: "rgba(190,18,60,0.12)", color: enviadoManual ? "#fff" : "#be123c", border: "1.5px solid rgba(190,18,60,0.5)" }}>
                          📩 Pedir faltantes al remitente{f.faltantes_pedidos_at ? ` ✓ Solicitado ${fmtAct(f.faltantes_pedidos_at)}` : ""}
                        </button>
                      )}
                    </div>

                  </div>
                  {f.prob_aprobacion && f.prob_aprobacion.porcentaje != null && (
                    <div style={{ display: "flex", gap: 8, alignItems: "stretch", flexShrink: 0 }}>
                      <div data-testid={`prob-aprobacion-${f.id}`}
                        title={`Posibilidades de aprobación\n${(f.prob_aprobacion.factores || []).join("\n")}`}
                        style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minWidth: 88, padding: "6px 10px", borderRadius: 0,
                          background: enviadoManual ? "rgba(255,255,255,0.15)" : (f.prob_aprobacion.porcentaje >= 75 ? "rgba(16,217,142,0.12)" : f.prob_aprobacion.porcentaje >= 50 ? "rgba(250,204,21,0.18)" : "rgba(190,18,60,0.12)") }}>
                        <span style={{ fontSize: 36, fontWeight: 900, lineHeight: 1,
                          color: enviadoManual ? "#fff" : (f.prob_aprobacion.porcentaje >= 75 ? "#10c98a" : f.prob_aprobacion.porcentaje >= 50 ? "#a16207" : "#be123c") }}>
                          {f.prob_aprobacion.porcentaje}%
                        </span>
                        <span style={{ fontSize: 9, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.5, opacity: 0.85, color: enviadoManual ? "#fff" : undefined }}>aprobación</span>
                        {f.techo_uf != null && (
                          <span data-testid={`techo-max-${f.id}`}
                            title={`Techo Hipotecario (máximo crédito posible) — mejor escenario: ${f.techo_banco || ""}`}
                            style={{ fontSize: 10, fontWeight: 900, marginTop: 3, whiteSpace: "nowrap", color: enviadoManual ? "#fff" : "#d4af37" }}>
                            ▲ Techo {Math.round(f.techo_uf).toLocaleString("es-CL")} UF
                          </span>
                        )}
                        {f.prob_aprobacion?.concreces?.disponible && f.prob_aprobacion.concreces.porcentaje != null && (
                          <span data-testid={`espejo-concreces-${f.id}`}
                            title={f.prob_aprobacion.discrepancia?.mensaje || "Espejo Concreces"}
                            style={{ fontSize: 9, fontWeight: 800, marginTop: 2, whiteSpace: "nowrap",
                              color: enviadoManual ? "#fff" : (f.prob_aprobacion.discrepancia?.hay ? "#ea580c" : "#94a3b8") }}>
                            Concreces {f.prob_aprobacion.concreces.porcentaje}%
                          </span>
                        )}
                      </div>
                      <div data-testid={`mesa-criterios-${f.id}`}
                        style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minWidth: 92, padding: "6px 10px", borderRadius: 0,
                          background: f.mesa_respuesta === "aprobada" ? "rgba(16,217,142,0.15)" : (f.mesa_respuesta === "rechazada" ? "rgba(190,18,60,0.15)" : "rgba(148,163,184,0.1)"),
                          border: f.mesa_respuesta ? "1.5px solid " + (f.mesa_respuesta === "aprobada" ? "#10d98e" : "#be123c") : "1px dashed rgba(148,163,184,0.4)" }}>
                        <span style={{ fontSize: 9, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.5, opacity: 0.8, color: enviadoManual ? "#fff" : undefined }}>Mesa</span>
                        {f.mesa_respuesta === "aprobada" && <span style={{ fontSize: 13, fontWeight: 900, color: "#10c98a" }}>✅ APROBADA</span>}
                        {f.mesa_respuesta === "rechazada" && <span style={{ fontSize: 13, fontWeight: 900, color: "#be123c" }}>❌ RECHAZADA</span>}
                        {!f.mesa_respuesta && <span style={{ fontSize: 11, fontWeight: 700, opacity: 0.6, color: enviadoManual ? "#fff" : undefined }}>Sin respuesta</span>}
                        {(f.criterios || []).length > 0 && (
                          <span style={{ fontSize: 10, fontWeight: 700, marginTop: 2, color: enviadoManual ? "#fff" : ((f.criterios.filter(c => c.ok).length === f.criterios.length) ? "#10c98a" : "#a16207") }}>
                            criterios {f.criterios.filter(c => c.ok).length}/{f.criterios.length}
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                  <div className="clientes-card-actions">
                    <button
                      className="docs-btn"
                      data-testid={`btn-envio-manual-${f.id}`}
                      onClick={() => toggleEnvioManual(f)}
                      title={enviadoManual ? "Marcar como NO enviado" : "Marcar como ENVIADO (pinta la carpeta roja)"}
                      style={enviadoManual
                        ? { background: "#fff", color: "#be123c", border: "1px solid #fff", fontWeight: 800 }
                        : { background: "rgba(190,18,60,0.1)", color: "#be123c", border: "1px solid #be123c", fontWeight: 700 }}>
                      <i className={`fa ${enviadoManual ? "fa-check-square" : "fa-square-o"}`}></i> {enviadoManual ? "Enviado" : "No enviado"}
                    </button>
                    {f.is_ready_to_send && (
                      <button className="docs-btn" onClick={() => openFolder(f.id, "email")} data-testid={`btn-enviar-ya-${f.id}`}
                        title="Lista para enviar: abre la carpeta y prepara el autocorreo con preview automático"
                        style={{ background: "#10d98e", color: "#fff", border: "1px solid #0e9f6e", fontWeight: 700, boxShadow: "0 2px 8px rgba(16,217,142,0.4)" }}>
                        <i className="fa fa-paper-plane"></i> 🚀 Enviar Ya
                      </button>
                    )}
                    <button className="docs-btn primary" onClick={() => openFolder(f.id)} data-testid={`btn-open-${f.id}`}>
                      <i className="fa fa-folder-open"></i> Abrir
                    </button>
                    <button className="clientes-delete-btn" onClick={() => deleteFolder(f.id)}>
                      <i className="fa fa-trash"></i>
                    </button>
                  </div>
                  <div data-testid={`modulos-carpeta-${f.id}`} style={{ width: "100%", display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10, paddingTop: 10, borderTop: enviadoManual ? "1px solid rgba(255,255,255,0.3)" : "1px solid rgba(46,92,230,0.25)" }}>
                    <button data-testid={`btn-aprobacion-${f.id}`} onClick={() => irAModulo("aprobacion")}
                      title={`Enviar aprobación al cliente ${f.nombre}`}
                      style={modBtn("rgba(16,217,142,0.12)", "#10d98e", enviadoManual ? "#fff" : "#10c98a")}>
                      <i className="fa fa-trophy"></i> Enviar Aprobación Cliente
                    </button>
                    <button data-testid={`btn-gastos-${f.id}`} onClick={() => irAModulo("gastos")}
                      title={`Gasto operacional para ${f.nombre}`}
                      style={modBtn("var(--gold, #d4af37)", "var(--gold, #d4af37)", "#0a0e17", true)}>
                      <i className="fa fa-money"></i> GASTO OPERACIONAL
                    </button>
                    <button data-testid={`btn-setcredito-${f.id}`} onClick={() => irAModulo("setcredito")}
                      title={`Firma set de crédito de ${f.nombre}`}
                      style={modBtn("rgba(212,175,55,0.12)", "#d4af37", enviadoManual ? "#fff" : "#0f52ba")}>
                      <i className="fa fa-pencil-square-o"></i> Firma Set de Crédito
                    </button>
                    <button data-testid={`btn-tasacion-${f.id}`} onClick={() => openTasacion(f)}
                      title={`Solicitar tasación de la propiedad de ${f.nombre} (Value Property + Victoria Vilches)`}
                      style={modBtn("rgba(234,88,12,0.12)", "#ea580c", enviadoManual ? "#fff" : "#ea580c")}>
                      <i className="fa fa-home"></i> Solicitud de Tasación{f.tasacion_terminado_at ? ` ✅ Terminada ${fmtAct(f.tasacion_terminado_at)}` : (f.tasacion_solicitada_at ? ` ✓ Solicitada ${fmtAct(f.tasacion_solicitada_at)}` : "")}{f.tasacion_fecha ? ` · 📅 ${f.tasacion_fecha}` : ""}
                    </button>
                    {f.tasacion_solicitada_at && (
                      <button data-testid={`btn-tasacion-terminada-${f.id}`} onClick={() => marcarTerminado(f, "tasacion", !f.tasacion_terminado_at)}
                        title={f.tasacion_terminado_at ? "Desmarcar: la tasación vuelve a estado solicitada" : "Marcar la tasación como TERMINADA (queda registrado con fecha y hora)"}
                        style={modBtn(f.tasacion_terminado_at ? "rgba(16,217,142,0.15)" : "rgba(148,163,184,0.1)", f.tasacion_terminado_at ? "#10d98e" : "#94a3b8", f.tasacion_terminado_at ? "#34eab9" : (enviadoManual ? "#fff" : "#94a3b8"))}>
                        <i className="fa fa-check-circle"></i> {f.tasacion_terminado_at ? "Tasación terminada" : "¿Tasación terminada?"}
                      </button>
                    )}
                    <button data-testid={`btn-estudio-titulo-${f.id}`} onClick={() => openEstudio(f)}
                      title={`Solicitar estudio de títulos de ${f.nombre} (siempre con copia a Victoria Vilches)`}
                      style={modBtn("rgba(20,184,166,0.12)", "#14b8a6", enviadoManual ? "#fff" : "#0d9488")}>
                      <i className="fa fa-balance-scale"></i> Solicitud de Estudio de Título{f.estudio_titulo_terminado_at ? ` ✅ Terminado ${fmtAct(f.estudio_titulo_terminado_at)}` : (f.estudio_titulo_solicitado_at ? ` ✓ Solicitado ${fmtAct(f.estudio_titulo_solicitado_at)}` : "")}
                    </button>
                    {f.estudio_titulo_solicitado_at && (
                      <button data-testid={`btn-estudio-terminado-${f.id}`} onClick={() => marcarTerminado(f, "estudio_titulo", !f.estudio_titulo_terminado_at)}
                        title={f.estudio_titulo_terminado_at ? "Desmarcar: el estudio vuelve a estado solicitado" : "Marcar el estudio de título como TERMINADO (queda registrado con fecha y hora)"}
                        style={modBtn(f.estudio_titulo_terminado_at ? "rgba(16,217,142,0.15)" : "rgba(148,163,184,0.1)", f.estudio_titulo_terminado_at ? "#10d98e" : "#94a3b8", f.estudio_titulo_terminado_at ? "#34eab9" : (enviadoManual ? "#fff" : "#94a3b8"))}>
                        <i className="fa fa-check-circle"></i> {f.estudio_titulo_terminado_at ? "E. Título terminado" : "¿E. Título terminado?"}
                      </button>
                    )}
                    {f.estudio_titulo_solicitado_at && (() => {
                      const rep = f.estudio_reparos || {};
                      const items = rep.items || [];
                      const pendientes = items.filter(i => !i.satisfecho).length;
                      const satisfecho = rep.estado === "satisfecho";
                      return (
                        <button data-testid={`btn-reparos-${f.id}`} onClick={() => openReparos(f)}
                          title={`Reparos del estudio de título de ${f.nombre} (detección automática en el hilo del abogado)`}
                          style={modBtn(satisfecho ? "rgba(16,217,142,0.12)" : (pendientes ? "rgba(225,29,72,0.14)" : "rgba(148,163,184,0.1)"),
                            satisfecho ? "#10d98e" : (pendientes ? "#e11d48" : "#94a3b8"),
                            satisfecho ? "#34eab9" : (pendientes ? "#fb7185" : (enviadoManual ? "#fff" : "#94a3b8")))}>
                          <i className="fa fa-gavel"></i> Reparos E. Título{satisfecho ? " ✅ resueltos" : (items.length ? ` (${pendientes} pendiente${pendientes === 1 ? "" : "s"})` : "")}
                        </button>
                      );
                    })()}
                    <button data-testid={`btn-escritura-${f.id}`} onClick={() => openEscritura(f)}
                      title={`Avisar a ${f.nombre} la fecha de firma de su escritura (con confirmación de asistencia)`}
                      style={modBtn("rgba(236,72,153,0.12)", "#ec4899", enviadoManual ? "#fff" : "#db2777")}>
                      <i className="fa fa-pencil"></i> Firma de Escritura{f.escritura_confirmada_at ? ` ✅ Confirmada ${fmtAct(f.escritura_confirmada_at)}` : (f.escritura_solicitada_at ? ` ✓ Solicitada ${fmtAct(f.escritura_solicitada_at)}` : "")}
                    </button>
                    <button data-testid={`btn-enriquecer-${f.id}`} onClick={() => enriquecerCarpeta(f, "credito")}
                      disabled={enriching === f.id + "credito"}
                      title={`Buscar de nuevo en el correo (asunto, cuerpo y adjuntos) los documentos faltantes de ${f.nombre}`}
                      style={modBtn("rgba(212,175,55,0.12)", "#d4af37", enviadoManual ? "#fff" : "#b8942e")}>
                      <i className={`fa ${enriching === f.id + "credito" ? "fa-spinner fa-spin" : "fa-magic"}`}></i> Enriquecer archivos
                    </button>
                    <button data-testid={`btn-escrituracion-toggle-${f.id}`} onClick={() => toggleEscrituracion(f)}
                      title={f.is_escrituracion ? "Devolver esta carpeta a Solicitudes de Crédito" : "Enviar la ficha a Escrituración y activarla en Set de Crédito y Títulos"}
                      style={modBtn(f.is_escrituracion ? "rgba(148,163,184,0.12)" : "rgba(46,92,230,0.12)", f.is_escrituracion ? "#94a3b8" : "#2e5ce6", enviadoManual ? "#fff" : (f.is_escrituracion ? "#94a3b8" : "#9333ea"))}>
                      <i className="fa fa-exchange"></i> {f.is_escrituracion ? "Devolver a Clientes" : "⚖️ Enviar a Escrituración"}
                    </button>
                    <button data-testid={`btn-historial-${f.id}`} onClick={() => openHistorial(f)}
                      title={`Historial completo de actividades de ${f.nombre}`}
                      style={modBtn("rgba(212,175,55,0.10)", "#d4af37", enviadoManual ? "#fff" : "#b8912e")}>
                      <i className="fa fa-history"></i> Historial
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
  );
}
