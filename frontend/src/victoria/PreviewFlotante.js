import { useState, useEffect } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";
import { S } from "./theme";

export default function PreviewFlotante({ info, onClose }) {
  const [url, setUrl] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let objUrl = null;
    axios.get(`${API_URL}/api/victoria/documentos/${info.doc_id}/contenido`, { responseType: "blob" })
      .then(r => { objUrl = URL.createObjectURL(r.data); setUrl(objUrl); })
      .catch(() => setErr("No fue posible cargar el documento de origen"));
    return () => { if (objUrl) URL.revokeObjectURL(objUrl); };
  }, [info.doc_id]);

  return (
    <div data-testid="preview-flotante" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.82)", zIndex: 130, display: "flex", alignItems: "center", justifyContent: "center", padding: "2rem" }}>
      <div style={{ background: "#141414", border: "1px solid rgba(212,175,55,0.5)", borderRadius: 4, width: "100%", maxWidth: 980, maxHeight: "92vh", display: "flex", flexDirection: "column", padding: "1.4rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
          <div>
            <div style={S.label}>Origen del dato · {info.etiqueta}</div>
            <div data-testid="preview-flotante-titulo" style={{ fontSize: "1.1rem", fontWeight: 700, color: "#fff", marginTop: 4 }}>
              «{info.valor}» — extraído de {info.tipo_etiqueta} ({info.archivo}), página {info.pagina}</div>
          </div>
          <button data-testid="preview-flotante-cerrar" onClick={onClose}
            style={{ ...S.btnLine, ...S.btnSmall }}>✕ Cerrar y volver a la revisión</button>
        </div>
        {err ? (
          <div style={{ color: "#f87171", padding: "2rem", fontSize: "1rem" }}>{err}</div>
        ) : !url ? (
          <div style={{ color: "#a1a1aa", padding: "2rem" }}>Cargando documento de origen…</div>
        ) : (
          <iframe title="documento de origen" data-testid="preview-flotante-iframe"
            src={`${url}#page=${info.pagina}`}
            style={{ width: "100%", flex: 1, minHeight: 480, border: "1px solid rgba(255,255,255,0.1)", borderRadius: 4, background: "#fff" }} />
        )}
      </div>
    </div>
  );
}
