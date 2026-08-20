import { useState, useRef } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const ORO = "#d4af37";
const CHUNK = 4 * 1024 * 1024;
const fmtGB = (b) => (b >= 1e9 ? `${(b / 1e9).toFixed(2)} GB` : b >= 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.round(b / 1024)} KB`);

export default function MboxImport() {
  const [file, setFile] = useState(null);
  const [st, setSt] = useState(null); // {pct, correos, bytes, estado, msg}
  const cancelRef = useRef(false);

  const subir = async () => {
    if (!file) return;
    cancelRef.current = false;
    setSt({ pct: 0, correos: 0, bytes: 0, estado: "subiendo" });
    let sid = "";
    try {
      const ini = await axios.post(`${API}/api/mbox/iniciar`, { filename: file.name, total_bytes: file.size });
      sid = ini.data.sid;
      for (let off = 0; off < file.size; off += CHUNK) {
        if (cancelRef.current) {
          await axios.post(`${API}/api/mbox/cancelar/${sid}`);
          setSt(s => ({ ...s, estado: "cancelado", msg: "Carga cancelada" }));
          return;
        }
        const blob = file.slice(off, off + CHUNK);
        const buf = await blob.arrayBuffer();
        let r = null;
        for (let intento = 0; intento < 4; intento++) {
          try {
            r = await axios.post(`${API}/api/mbox/chunk/${sid}`, buf,
              { headers: { "Content-Type": "application/octet-stream" }, timeout: 180000 });
            break;
          } catch (e) {
            if (intento === 3) throw e;
            await new Promise(res => setTimeout(res, 2500 * (intento + 1)));
          }
        }
        setSt({ pct: r.data.pct, correos: r.data.correos_importados, bytes: r.data.bytes_recibidos, estado: "subiendo" });
      }
      const fin = await axios.post(`${API}/api/mbox/finalizar/${sid}`);
      setSt({ pct: 100, correos: fin.data.correos_importados, bytes: file.size, estado: "completado",
        msg: `✅ Procesamiento completo: ${fin.data.correos_importados.toLocaleString("es-CL")} correos importados a la base de datos${fin.data.omitidos ? ` (${fin.data.omitidos} omitidos)` : ""}` });
    } catch (e) {
      setSt(s => ({ ...(s || {}), estado: "error", msg: e.response?.data?.detail || "Error durante la carga — puedes reintentar" }));
    }
  };

  const ocupado = st?.estado === "subiendo";
  return (
    <div data-testid="mbox-import" style={{ marginTop: 14, padding: "0.9rem 1rem", background: "#0c0c0c",
      border: "1px solid rgba(212,175,55,0.25)" }}>
      <div style={{ color: ORO, fontSize: "0.72rem", fontWeight: 800, letterSpacing: 2 }}>
        📦 IMPORTAR ARCHIVO .MBOX (hasta 100 GB)</div>
      <p style={{ color: "#8a8a8a", fontSize: "0.64rem", margin: "4px 0 8px" }}>
        Sube el archivo completo desde tu computador: la app lo divide en fragmentos automáticamente,
        procesa cada correo y lo une en una sola base de datos. No cierres esta pestaña durante la carga.</p>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <input data-testid="mbox-file" type="file" accept=".mbox,application/mbox,*/*" disabled={ocupado}
          onChange={e => { setFile(e.target.files?.[0] || null); setSt(null); }}
          style={{ color: "#e8e3d3", fontSize: "0.7rem" }} />
        {file && <span style={{ color: "#94a3b8", fontSize: "0.66rem" }}>{fmtGB(file.size)}</span>}
        {!ocupado && (
          <button data-testid="mbox-subir" onClick={subir} disabled={!file}
            style={{ background: file ? ORO : "#333", border: "none", color: "#0a0a0a", padding: "0.4rem 1rem",
              fontWeight: 900, fontSize: "0.66rem", letterSpacing: 1, cursor: file ? "pointer" : "not-allowed" }}>
            PROCESAR ARCHIVO</button>
        )}
        {ocupado && (
          <button data-testid="mbox-cancelar" onClick={() => { cancelRef.current = true; }}
            style={{ background: "transparent", border: "1px solid rgba(239,68,68,0.5)", color: "#f87171",
              padding: "0.4rem 1rem", fontWeight: 800, fontSize: "0.66rem", cursor: "pointer" }}>CANCELAR</button>
        )}
      </div>
      {st && (
        <div style={{ marginTop: 10 }}>
          <div style={{ height: 14, background: "#1a1a1a", border: "1px solid rgba(212,175,55,0.3)", position: "relative" }}>
            <div data-testid="mbox-barra" style={{ height: "100%", width: `${st.pct || 0}%`,
              background: st.estado === "error" ? "#7f1d1d" : "linear-gradient(90deg, #8a6d1a, #d4af37)",
              transition: "width 0.4s ease" }} />
            <span style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
              color: "#fff", fontSize: 10, fontWeight: 900 }}>{st.pct || 0}%</span>
          </div>
          <div data-testid="mbox-progreso" style={{ display: "flex", gap: 14, marginTop: 5, color: "#e8e3d3", fontSize: "0.66rem", flexWrap: "wrap" }}>
            <span>📧 Correos importados: <b style={{ color: ORO }}>{Number(st.correos || 0).toLocaleString("es-CL")}</b></span>
            <span>💾 Procesado: {fmtGB(st.bytes || 0)}{file ? ` de ${fmtGB(file.size)}` : ""}</span>
            <span style={{ textTransform: "capitalize" }}>Estado: {st.estado}</span>
          </div>
          {st.msg && <div data-testid="mbox-msg" style={{ marginTop: 6, fontSize: "0.68rem", fontWeight: 700,
            color: st.estado === "error" ? "#f87171" : "#4ade80" }}>{st.msg}</div>}
        </div>
      )}
    </div>
  );
}
