import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { API_URL } from "../utils/formatters";
import { S } from "./theme";

export default function DocViewer({ doc, onActualizado }) {
  const [url, setUrl] = useState(null);
  const [mime, setMime] = useState("");
  const [err, setErr] = useState("");
  const [motivo, setMotivo] = useState("");
  const [rechazando, setRechazando] = useState(false);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (!doc?.id) return;
    let objUrl = null;
    setUrl(null); setErr(""); setRechazando(false); setMotivo("");
    axios.get(`${API_URL}/api/victoria/documentos/${doc.id}/contenido`, { responseType: "blob" })
      .then(r => {
        objUrl = URL.createObjectURL(r.data);
        setMime(r.data.type || "application/pdf");
        setUrl(objUrl);
      })
      .catch(async (e) => {
        let d = "No fue posible cargar el documento";
        try { d = JSON.parse(await e.response.data.text()).detail || d; } catch {}
        setErr(d);
      });
    return () => { if (objUrl) URL.revokeObjectURL(objUrl); };
  }, [doc?.id]);

  const decidir = async (decision) => {
    if (decision === "rechazado" && !motivo.trim()) { toast.error("Indique el motivo del rechazo"); return; }
    setEnviando(true);
    try {
      await axios.post(`${API_URL}/api/victoria/documentos/${doc.id}/revision`,
        { decision, motivo: motivo.trim() });
      toast.success(decision === "aceptado"
        ? `«${doc.archivo}» aceptado como válido`
        : `«${doc.archivo}» rechazado — quedó fuera del set y se registró el aviso`);
      onActualizado();
    } catch (e) { toast.error(e.response?.data?.detail || "No se pudo registrar la decisión"); }
    setEnviando(false);
  };

  if (!doc) return (
    <div data-testid="doc-viewer-vacio" style={{ ...S.card, display: "flex", alignItems: "center", justifyContent: "center", minHeight: 480 }}>
      <p style={{ ...S.body, color: "#71717a", fontSize: "1.1rem" }}>
        Seleccione un documento de la lista para verlo aquí al instante, sin descargarlo.</p>
    </div>
  );

  const rev = doc.revision;
  const esImg = mime.startsWith("image/");
  return (
    <div data-testid="doc-viewer" style={{ ...S.card, padding: "1.5rem" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10, marginBottom: 14 }}>
        <div>
          <div style={S.label}>Previsualización del documento</div>
          <div style={{ fontSize: "1.15rem", fontWeight: 700, color: "#fff", marginTop: 4 }} data-testid="doc-viewer-nombre">{doc.archivo}</div>
        </div>
        {rev && <span data-testid="doc-viewer-estado-revision" style={S.pill(
          rev.decision === "aceptado" ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)",
          rev.decision === "aceptado" ? "#4ade80" : "#f87171")}>
          {rev.decision === "aceptado" ? "✓ ACEPTADO POR VICTORIA" : "✕ RECHAZADO"}</span>}
      </div>
      {err ? (
        <div data-testid="doc-viewer-error" style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.4)", borderRadius: 4, padding: "1.4rem", color: "#f87171", fontSize: "1rem" }}>{err}</div>
      ) : !url ? (
        <div style={{ minHeight: 420, display: "flex", alignItems: "center", justifyContent: "center", color: "#a1a1aa" }}>Cargando documento…</div>
      ) : esImg ? (
        <img src={url} alt={doc.archivo} data-testid="doc-viewer-imagen"
          style={{ width: "100%", maxHeight: 560, objectFit: "contain", background: "#000", borderRadius: 4, border: "1px solid rgba(255,255,255,0.1)" }} />
      ) : (
        <iframe src={url} title={doc.archivo} data-testid="doc-viewer-iframe"
          style={{ width: "100%", height: 560, border: "1px solid rgba(255,255,255,0.1)", borderRadius: 4, background: "#fff" }} />
      )}
      {!err && url && (
        <div style={{ marginTop: 16 }}>
          {!rechazando ? (
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              <button data-testid="doc-btn-aceptar" disabled={enviando} onClick={() => decidir("aceptado")}
                style={{ ...S.btnGold, flex: "1 1 240px" }}>
                ✓ Aceptar documento como válido</button>
              <button data-testid="doc-btn-rechazar" disabled={enviando} onClick={() => setRechazando(true)}
                style={{ ...S.btnDanger, flex: "1 1 240px" }}>
                ✕ Rechazar documento y solicitar reemplazo</button>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <label style={S.label}>Motivo exacto del rechazo (se registrará en los avisos)</label>
              <input data-testid="doc-input-motivo-rechazo" style={S.input} value={motivo} autoFocus
                placeholder="Ej: documento ilegible / falta la firma / corresponde a otro cliente"
                onChange={e => setMotivo(e.target.value)} />
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                <button data-testid="doc-btn-confirmar-rechazo" disabled={enviando} onClick={() => decidir("rechazado")}
                  style={{ ...S.btnDanger, flex: 1 }}>Confirmar rechazo de este documento</button>
                <button data-testid="doc-btn-cancelar-rechazo" onClick={() => setRechazando(false)}
                  style={{ ...S.btnLine, flex: 1 }}>No rechazar — volver a la previsualización</button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
