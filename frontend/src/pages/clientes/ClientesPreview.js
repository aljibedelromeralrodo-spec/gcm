import { useClientes } from "./clientesCtx";

/** Visor global: se monta siempre (ficha, lista, ajustes y modales). */
export default function ClientesPreview() {
  const { previewFile, closePreview } = useClientes();
  if (!previewFile) return null;
  return (
        <div
          data-testid="preview-modal"
          onClick={closePreview}
          style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)",
            display: "flex", alignItems: "center", justifyContent: "center",
            zIndex: 9999, padding: "2vh 2vw",
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", color: "#e2e8f0",
              borderRadius: 0, boxShadow: "0 20px 60px rgba(0,0,0,0.6)",
              width: "min(1200px, 96vw)", height: "min(900px, 92vh)",
              display: "flex", flexDirection: "column", overflow: "hidden",
              border: "1px solid rgba(148,163,184,0.25)",
            }}
          >
            <div style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "0.6rem 0.9rem", borderBottom: "1px solid rgba(148,163,184,0.2)",
              background: "rgba(14,14,16,0.9)",
            }}>
              <i className={`fa ${previewFile.mime === "pdf" ? "fa-file-pdf-o" : previewFile.mime === "image" ? "fa-file-image-o" : "fa-file-o"}`} style={{ color: "#facc15" }} />
              <span style={{ flex: 1, fontWeight: 600, fontSize: 14, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{previewFile.name}</span>
              <a
                href={previewFile.url.replace("?inline=true", "")}
                target="_blank" rel="noreferrer"
                data-testid="preview-download-link"
                style={{ background: "rgba(148,163,184,0.15)", color: "#e2e8f0", padding: "5px 12px", borderRadius: 0, textDecoration: "none", fontSize: 12 }}
              >
                <i className="fa fa-download" /> Descargar
              </a>
              <button
                onClick={closePreview}
                data-testid="btn-preview-close"
                style={{ background: "rgba(225,29,72,0.2)", color: "#fda4af", border: "1px solid rgba(225,29,72,0.4)", borderRadius: 0, padding: "5px 12px", cursor: "pointer", fontSize: 12 }}
              >
                <i className="fa fa-times" /> Cerrar
              </button>
            </div>
            <div style={{ flex: 1, background: "#232326", overflow: "hidden" }}>
              {previewFile.mime === "pdf" && (
                <iframe title={previewFile.name} src={previewFile.url} style={{ width: "100%", height: "100%", border: "none", background: "#fff" }} />
              )}
              {previewFile.mime === "image" && (
                <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", overflow: "auto", background: "#0b1220" }}>
                  <img src={previewFile.url} alt={previewFile.name} style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }} />
                </div>
              )}
              {previewFile.mime === "text" && (
                <iframe title={previewFile.name} src={previewFile.url} style={{ width: "100%", height: "100%", border: "none", background: "#fff" }} />
              )}
              {previewFile.mime === "other" && (
                <div style={{ padding: "2rem", textAlign: "center", color: "#94a3b8" }}>
                  <i className="fa fa-file-o" style={{ fontSize: 48, opacity: 0.5, display: "block", marginBottom: 12 }} />
                  <p>Vista previa no disponible para este formato.</p>
                  <a href={previewFile.url.replace("?inline=true", "")} target="_blank" rel="noreferrer" style={{ color: "#d4af37", textDecoration: "underline" }}>
                    Descargar archivo
                  </a>
                </div>
              )}
            </div>
          </div>
        </div>
  );
}
