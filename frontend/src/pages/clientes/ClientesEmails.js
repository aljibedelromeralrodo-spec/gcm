
import { useClientes } from "./clientesCtx";

export default function ClientesEmails() {
  const {
    currentFolder,
    emailResults,
    emailSearch,
    emails,
    loading,
    saveAttachmentToFolder,
    savingAttachment,
    searchEmails,
    setEmailSearch,
    setView,
    view
  } = useClientes();
  return (
        <div data-testid="clientes-emails">
          <div className="clientes-detail-header">
            <button className="docs-btn secondary" onClick={() => setView("list")} data-testid="btn-back-emails">
              <i className="fa fa-arrow-left"></i> Volver
            </button>
            <h3><i className="fa fa-envelope"></i> Correos - aprobaciones@centralmutuos.cl</h3>
          </div>

          <div className="clientes-email-search">
            <input type="text" placeholder="Buscar en correos..." value={emailSearch}
              onChange={e => setEmailSearch(e.target.value)}
              onKeyDown={e => e.key === "Enter" && searchEmails()}
              data-testid="email-search-input" />
            <button className="docs-btn primary" onClick={searchEmails} disabled={loading} data-testid="btn-search-emails">
              <i className={`fa ${loading ? "fa-spinner fa-spin" : "fa-search"}`}></i> Buscar
            </button>
          </div>

          <div className="clientes-email-list">
            {(emailResults.length > 0 ? emailResults : emails).map((em, i) => (
              <div key={i} className="clientes-email-item" data-testid={`email-${i}`}>
                <div className="clientes-email-header">
                  <span className="clientes-email-from">{em.from}</span>
                  <span className="clientes-email-date">{em.date}</span>
                </div>
                <div className="clientes-email-subject">{em.subject || "(Sin asunto)"}</div>
                <div className="clientes-email-body">{(em.body || em.body_preview || "").slice(0, 200)}</div>
                {em.attachments?.length > 0 && (
                  <div className="clientes-email-attachments">
                    {em.attachments.map((att, j) => (
                      <span key={j} className="clientes-attachment-badge">
                        <i className="fa fa-paperclip"></i> {att.filename || att}
                        {currentFolder && att.filename && (
                          <button className="clientes-save-att" onClick={() => saveAttachmentToFolder(em.id, att.filename)}
                            disabled={savingAttachment === `${em.id}-${att.filename}`}>
                            <i className={`fa ${savingAttachment === `${em.id}-${att.filename}` ? "fa-spinner fa-spin" : "fa-save"}`}></i>
                          </button>
                        )}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {emails.length === 0 && emailResults.length === 0 && !loading && (
              <div className="clientes-empty"><i className="fa fa-envelope-o"></i><p>No se encontraron correos.</p></div>
            )}
          </div>
        </div>
  );
}
