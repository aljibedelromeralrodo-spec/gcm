import { useEffect } from "react";

const API = process.env.REACT_APP_BACKEND_URL;

export const DocumentoViewer = ({ doc, onClose }) => {
  useEffect(() => {
    const esc = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);
  if (!doc) return null;
  const url = `${API}/api/storage/ver/${doc.id || doc.bandeja_id}`;
  const esImagen = (doc.content_type || "").startsWith("image/");
  return (
    <div data-testid="documento-viewer-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      style={{ position: "fixed", inset: 0, zIndex: 1200, background: "rgba(2,6,23,0.85)",
        backdropFilter: "blur(4px)", display: "flex", flexDirection: "column", padding: "1.2rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10 }}>
        <b style={{ color: "#FCF6BA", fontSize: "0.9rem" }}>👁 {doc.nombre_archivo}</b>
        <span style={{ color: "#94a3b8", fontSize: "0.68rem" }}>
          {doc.cliente ? `${doc.cliente} · ` : ""}{doc.rut || ""} — visualización directa (sin descarga)</span>
        <button data-testid="documento-viewer-cerrar" onClick={onClose}
          style={{ marginLeft: "auto", background: "rgba(248,113,113,0.15)", color: "#f87171",
            border: "1px solid rgba(248,113,113,0.5)", borderRadius: 8, padding: "0.4rem 1rem",
            fontWeight: 800, cursor: "pointer", fontSize: "0.78rem" }}>✕ Cerrar</button>
      </div>
      <div style={{ flex: 1, background: "#0f172a", borderRadius: 12, overflow: "hidden",
        border: "1px solid rgba(212,175,55,0.35)", display: "flex", justifyContent: "center" }}>
        {esImagen
          ? <img src={url} alt={doc.nombre_archivo} data-testid="documento-viewer-img"
              style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }} />
          : <iframe src={url} title={doc.nombre_archivo} data-testid="documento-viewer-iframe"
              style={{ width: "100%", height: "100%", border: "none", background: "#fff" }} />}
      </div>
    </div>
  );
};

export default DocumentoViewer;
