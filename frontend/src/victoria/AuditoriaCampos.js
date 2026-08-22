import { useState, useEffect } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

const GOLD = "#d4af37";
const box = { background: "#0d0d0d", border: "1px solid rgba(212,175,55,0.3)", borderRadius: 6 };

export default function AuditoriaCampos({ clienteId }) {
  const [abierto, setAbierto] = useState(false);
  const [data, setData] = useState(null);
  const [frag, setFrag] = useState(null);

  useEffect(() => {
    if (abierto && clienteId) {
      setData(null);
      axios.get(`${API_URL}/api/victoria/clientes/${clienteId}/auditoria-campos`)
        .then(r => setData(r.data))
        .catch(() => setData({ campos: [], pendientes: [], regla: "" }));
    }
  }, [abierto, clienteId]);

  const verFragmento = async (c) => {
    setFrag({ etiqueta: c.etiqueta, cargando: true });
    try {
      const r = await axios.get(`${API_URL}/api/victoria/documentos/${c.doc_id}/fragmento`,
        { params: { q: c.valor, pagina: c.pagina }, responseType: "blob" });
      setFrag({ etiqueta: c.etiqueta, url: URL.createObjectURL(r.data), archivo: c.archivo, pagina: c.pagina, valor: c.valor });
    } catch { setFrag({ etiqueta: c.etiqueta, error: true }); }
  };

  if (!clienteId) return null;
  return (
    <div style={{ margin: "14px 0" }}>
      <button data-testid="auditoria-toggle" onClick={() => setAbierto(a => !a)}
        style={{ background: "transparent", border: `1px solid ${GOLD}`, color: GOLD, borderRadius: 6,
          padding: "0.6rem 1.2rem", cursor: "pointer", fontWeight: 700, fontSize: "0.85rem", letterSpacing: 1 }}>
        🔍 {abierto ? "Cerrar vista de auditoría" : "Vista de Auditoría — origen documental de cada dato"}
      </button>

      {abierto && (
        <div data-testid="auditoria-panel" style={{ ...box, marginTop: 12, padding: "1.3rem 1.6rem" }}>
          {!data && <div style={{ color: "#a1a1aa" }}>Rastreando el origen de cada campo…</div>}
          {data && (
            <>
              <p style={{ color: "#a1a1aa", fontSize: "0.82rem", margin: "0 0 12px", fontStyle: "italic" }}>{data.regla}</p>
              {data.campos.map(c => (
                <div key={c.campo} data-testid={`auditoria-campo-${c.campo}`}
                  style={{ display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap",
                    borderTop: "1px solid rgba(255,255,255,0.08)", padding: "0.7rem 0" }}>
                  <div style={{ flex: "1 1 240px" }}>
                    <div style={{ color: "#e4e4e7", fontWeight: 700, fontSize: "0.9rem" }}>{c.etiqueta}</div>
                    {c.pendiente
                      ? <span data-testid={`auditoria-pendiente-${c.campo}`} style={{ color: "#f59e0b", fontSize: "0.85rem", fontWeight: 700 }}>
                          ⏳ PENDIENTE — no hallado con certeza en los documentos (no se inventa)</span>
                      : <span style={{ color: "#FCF6BA", fontSize: "0.92rem" }}>{c.valor}</span>}
                  </div>
                  {!c.pendiente && c.doc_id && (
                    <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                      <span style={{ color: "#a1a1aa", fontSize: "0.78rem" }}>
                        📄 {c.tipo_etiqueta || "Documento"} · {c.archivo} · pág. {c.pagina}</span>
                      <button data-testid={`auditoria-fragmento-${c.campo}`} onClick={() => verFragmento(c)}
                        style={{ background: "rgba(212,175,55,0.12)", border: `1px solid ${GOLD}`, color: GOLD,
                          borderRadius: 5, padding: "0.35rem 0.8rem", cursor: "pointer", fontSize: "0.78rem", fontWeight: 700 }}>
                        Ver fragmento original</button>
                    </div>
                  )}
                  {!c.pendiente && !c.doc_id && <span style={{ color: "#71717a", fontSize: "0.78rem" }}>Dato de la ficha base (sin documento asociado)</span>}
                </div>
              ))}
              {data.pendientes.length > 0 && (
                <div style={{ marginTop: 10, color: "#f59e0b", fontSize: "0.82rem" }}>
                  Campos pendientes de respaldo documental: {data.pendientes.join(", ")}</div>
              )}
            </>
          )}
        </div>
      )}

      {frag && (
        <div data-testid="auditoria-frag-modal" onClick={() => setFrag(null)}
          style={{ position: "fixed", inset: 0, zIndex: 300, background: "rgba(0,0,0,0.85)",
            display: "flex", alignItems: "center", justifyContent: "center", padding: 30 }}>
          <div onClick={e => e.stopPropagation()} style={{ ...box, background: "#111", maxWidth: 900, maxHeight: "88vh", overflow: "auto", padding: "1.4rem 1.6rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 14, alignItems: "center", marginBottom: 12 }}>
              <div>
                <div style={{ color: GOLD, fontWeight: 800 }}>Fragmento original — {frag.etiqueta}</div>
                {frag.archivo && <div style={{ color: "#a1a1aa", fontSize: "0.8rem" }}>{frag.archivo} · página {frag.pagina} · valor: {frag.valor}</div>}
              </div>
              <button data-testid="auditoria-frag-cerrar" onClick={() => setFrag(null)}
                style={{ background: "transparent", border: "1px solid #555", color: "#d4d4d8", borderRadius: 5, padding: "0.4rem 0.9rem", cursor: "pointer" }}>✕ Cerrar</button>
            </div>
            {frag.cargando && <div style={{ color: "#a1a1aa", padding: "2rem" }}>Renderizando el fragmento del documento…</div>}
            {frag.error && <div style={{ color: "#f87171", padding: "1rem" }}>No se pudo renderizar el fragmento (documento físico no disponible).</div>}
            {frag.url && <img src={frag.url} alt="Fragmento original del documento" data-testid="auditoria-frag-img"
              style={{ maxWidth: "100%", border: `2px solid ${GOLD}`, borderRadius: 4, background: "#fff" }} />}
          </div>
        </div>
      )}
    </div>
  );
}
