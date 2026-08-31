// Corte 7: buscador, toolbar de acciones y tabs de ClientesModule (solo presentación)
const ClientesFilters = ({ searchQuery, setSearchQuery, syncing, cloudSync, syncMsg,
  loadEmails, loadAjustes, setShowCreate, setForzarModal, setCompromisoLibre,
  folderTab, setFolderTab, countClientes, countEscrituracion }) => (
  <>
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
  </>
);

export default ClientesFilters;
