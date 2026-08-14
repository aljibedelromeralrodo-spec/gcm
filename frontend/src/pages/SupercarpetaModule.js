import { useState, useEffect } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const INFORMES = [["tasacion", "Tasación"], ["estudio", "Estudio Títulos"], ["borrador", "Borrador Escritura"]];

export default function SupercarpetaModule() {
  const [data, setData] = useState(null);
  const [solo24, setSolo24] = useState(false);
  const [preview, setPreview] = useState(null);

  useEffect(() => {
    axios.get(`${API}/api/supercarpeta`).then(r => setData(r.data)).catch(() => setData({ clientes: [] }));
  }, []);

  const abrir = async (fid, cliente, inf) => {
    try {
      const r = await axios.get(`${API}/api/supercarpeta/archivo/${fid}`, {
        params: { ruta: inf.archivo }, responseType: "blob" });
      const url = URL.createObjectURL(new Blob([r.data], { type: "application/pdf" }));
      setPreview({ url, cliente, archivo: inf.archivo });
    } catch (e) { window.alert(e.response?.status === 404 ? "Informe no disponible" : "Error al abrir el informe"); }
  };

  const clientes = (data?.clientes || []).filter(c => !solo24 || c.recien_24h);

  return (
    <div className="module-content seamless-scope" data-testid="supercarpeta-module" style={{ minHeight: "100%", padding: "1.1rem", borderRadius: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 10 }}>
        <h3 style={{ margin: 0, color: "#f8fafc", fontSize: "1.02rem" }}>
          <i className="fa fa-folder folder-metal" style={{ marginRight: 8 }} />Supercarpeta de Management — {data?.mes || "…"}
        </h3>
        <span style={{ color: "#94a3b8", fontSize: "0.7rem" }}>
          {clientes.length}/{data?.total ?? 0} clientes · Regla #55: disponibilidad física de informes del mes corriente
        </span>
        <button data-testid="filtro-recien-24h" onClick={() => setSolo24(v => !v)}
          className={`maserati-btn ${solo24 ? "" : "neon"}`} style={{ marginLeft: "auto", minHeight: 38 }}>
          🟢 Recién llegados 24h ({data?.recien_llegados ?? 0}) {solo24 ? "· quitar filtro" : ""}
        </button>
      </div>
      <div style={{ background: "rgba(30,41,59,0.5)", border: "1px solid rgba(148,163,184,0.18)", borderRadius: 14, overflowX: "auto" }}>
        <table data-testid="supercarpeta-tabla" style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.72rem", color: "#e2e8f0" }}>
          <thead>
            <tr style={{ color: "#94a3b8", fontSize: "0.6rem", textTransform: "uppercase", letterSpacing: "0.1em" }}>
              {["Cliente", "RUT", "Broker", "Tasación (Value Property)", "Estudio de Títulos", "Borrador de Escritura"].map(h =>
                <th key={h} style={{ padding: "0.5rem 0.7rem", textAlign: "left", borderBottom: "1px solid rgba(148,163,184,0.15)" }}>{h}</th>)}
            </tr>
          </thead>
          <tbody>
            {clientes.map(c => (
              <tr key={c.id} data-testid={`super-fila-${c.id}`}
                className={c.recien_24h ? "neon-verde" : ""}
                style={{ borderBottom: "1px solid rgba(148,163,184,0.07)", height: 34 }}>
                <td style={{ padding: "0.3rem 0.7rem", fontWeight: 700, color: "#f8fafc", whiteSpace: "nowrap" }}>
                  <i className="fa fa-folder folder-metal" style={{ marginRight: 6, fontSize: "0.85rem" }} />{c.cliente}
                  {c.recien_24h && <span data-testid={`recien-${c.id}`} style={{ marginLeft: 6, color: "#22c55e", fontSize: "0.56rem", fontWeight: 800 }}>● NUEVO 24H</span>}
                </td>
                <td style={{ padding: "0.3rem 0.7rem", fontFamily: "monospace", fontSize: "0.66rem" }}>{c.rut || "—"}</td>
                <td style={{ padding: "0.3rem 0.7rem", color: "#38bdf8", fontSize: "0.62rem" }}>{c.broker_origen}</td>
                {INFORMES.map(([k]) => {
                  const inf = c.informes?.[k] || {};
                  return (
                    <td key={k} style={{ padding: "0.3rem 0.7rem" }}>
                      {inf.disponible
                        ? <button data-testid={`ver-${k}-${c.id}`} onClick={() => abrir(c.id, c.cliente, inf)}
                            title={`${inf.archivo} · ${(inf.fecha || "").slice(0, 16).replace("T", " ")}`}
                            style={{ cursor: "pointer", background: "rgba(34,197,94,0.12)", border: "1px solid rgba(34,197,94,0.5)",
                              color: "#22c55e", borderRadius: 8, padding: "0.2rem 0.6rem", fontSize: "0.62rem", fontWeight: 800 }}>
                            📄 Ver PDF
                          </button>
                        : <span style={{ color: "#64748b", fontSize: "0.58rem" }}>Pendiente de Información</span>}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        {data && clientes.length === 0 && <p style={{ color: "#94a3b8", textAlign: "center", padding: "1.5rem" }}>Sin clientes {solo24 ? "con informes en las últimas 24h" : "en el mes corriente"}.</p>}
      </div>
      {preview && (
        <div data-testid="super-preview-modal" onClick={() => { URL.revokeObjectURL(preview.url); setPreview(null); }}
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)", zIndex: 800, display: "flex", alignItems: "center", justifyContent: "center", padding: "2vh 2vw" }}>
          <div onClick={e => e.stopPropagation()} style={{ background: "#111214", border: "1.5px solid #d4af37", borderRadius: 12, width: "min(960px,96vw)", height: "92vh", display: "flex", flexDirection: "column" }}>
            <div style={{ display: "flex", alignItems: "center", padding: "0.6rem 1rem", gap: 10 }}>
              <b style={{ color: "#d4af37", fontSize: "0.8rem" }}>📄 {preview.cliente}</b>
              <span style={{ color: "#94a3b8", fontSize: "0.66rem" }}>{preview.archivo}</span>
              <button onClick={() => { URL.revokeObjectURL(preview.url); setPreview(null); }}
                style={{ marginLeft: "auto", background: "transparent", border: "1px solid rgba(255,255,255,0.25)", color: "#e2e8f0", borderRadius: 8, padding: "0.25rem 0.7rem", cursor: "pointer" }}>✕ Cerrar</button>
            </div>
            <iframe title="preview" src={preview.url} style={{ flex: 1, border: "none", borderRadius: "0 0 12px 12px", background: "#fff" }} />
          </div>
        </div>
      )}
    </div>
  );
}
