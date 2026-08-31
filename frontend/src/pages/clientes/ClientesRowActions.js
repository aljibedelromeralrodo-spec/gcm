// Corte 8: acciones de la tarjeta de carpeta (Enviado, Enviar Ya, Abrir, eliminar) — 0 lógica
const ClientesRowActions = ({ f, enviadoManual, toggleEnvioManual, openFolder, deleteFolder }) => (
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
);

export default ClientesRowActions;
