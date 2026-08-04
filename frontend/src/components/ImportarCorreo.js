import { useState, useEffect } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

const inpS = { background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 0, padding: "0.55rem 0.8rem", color: "#fff", fontSize: "0.9rem", width: "100%" };

export default function ImportarCorreo({ destino, destinoId, nombre, onDone, label, style }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [correos, setCorreos] = useState([]);
  const [sel, setSel] = useState({});
  const [buscando, setBuscando] = useState(false);
  const [importando, setImportando] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (!open || q.trim().length < 3) { setCorreos([]); return; }
    const t = setTimeout(async () => {
      setBuscando(true);
      try {
        const r = await axios.get(`${API}/api/correos/buscar`, { params: { q: q.trim() }, timeout: 90000 });
        setCorreos(r.data.correos || []);
      } catch (_e) { setCorreos([]); }
      setBuscando(false);
    }, 500);
    return () => clearTimeout(t);
  }, [q, open]);

  const abrir = () => { setQ(nombre || ""); setSel({}); setMsg(""); setCorreos([]); setOpen(true); };

  const importar = async () => {
    const mids = correos.filter((c, i) => sel[i] && c.message_id).map(c => c.message_id);
    if (!mids.length) { setMsg("Selecciona al menos un correo de la lista"); return; }
    setImportando(true); setMsg("⏳ Descargando adjuntos desde el correo… (puede tardar 1-2 minutos, no cierres esta ventana)");
    try {
      const r = await axios.post(`${API}/api/correos/importar`,
        { destino, destino_id: destinoId || "", nombre: q.trim(), message_ids: mids }, { timeout: 55000 });
      const jobId = r.data.job_id;
      let res = null;
      for (let i = 0; i < 120; i++) {
        await new Promise(s => setTimeout(s, 3000));
        const j = await axios.get(`${API}/api/jobs/${jobId}`, { timeout: 30000 });
        if (j.data.estado === "listo") { res = j.data.resultado; break; }
        if (j.data.estado === "error") throw new Error(j.data.error || "Error importando");
      }
      if (!res) throw new Error("La importación sigue en curso — revisá los archivos en unos minutos");
      const n = (res.guardados || []).length;
      setMsg(n ? `✅ ${n} archivo(s) importado(s): ${res.guardados.join(" · ")}`
               : "⚠️ Los correos elegidos no traían adjuntos nuevos (quizá ya estaban guardados)");
      if (n && onDone) onDone();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setImportando(false);
  };

  return (
    <>
      <button data-testid={`importar-correo-btn-${destino}`} onClick={abrir}
        style={{ background: "rgba(20,184,166,0.15)", border: "1px solid #14b8a6", color: "#2dd4bf", borderRadius: 0, padding: "0.45rem 0.9rem", fontWeight: 700, cursor: "pointer", fontSize: "0.82rem", ...style }}>
        <i className="fa fa-cloud-download" style={{ marginRight: "0.4rem" }} />{label || "Importar desde correo"}
      </button>
      {open && (
        <div onClick={() => setOpen(false)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.72)", zIndex: 9999, display: "flex", alignItems: "center", justifyContent: "center", padding: "3vh 3vw" }}>
          <div data-testid="importar-correo-modal" onClick={e => e.stopPropagation()}
            style={{ background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", border: "1px solid rgba(148,163,184,0.25)", borderRadius: 0, padding: "1.4rem", width: "min(820px, 96vw)", maxHeight: "90vh", overflow: "auto", display: "grid", gap: 10, color: "#e2e8f0" }}>
            <h4 style={{ margin: 0, color: "var(--gold, #d4af37)" }}>
              <i className="fa fa-cloud-download" style={{ marginRight: "0.5rem" }} />{label || "Importar desde correo"}
            </h4>
            <label style={{ fontSize: 12 }}>Buscar en el correo (nombre, RUT o asunto) <span style={{ opacity: 0.6 }}>— aparecen los correos coincidentes y eliges de cuál importar los adjuntos</span>
              <input data-testid="importar-correo-q" autoFocus style={inpS} value={q} onChange={e => setQ(e.target.value)} placeholder="Ej: Pedro González o 16.005.374-7" />
            </label>
            {buscando && <div style={{ fontSize: 12.5, opacity: 0.7 }}><i className="fa fa-spinner fa-spin" /> Buscando en el buzón…</div>}
            {!buscando && q.trim().length >= 3 && correos.length === 0 && (
              <div style={{ fontSize: 12, color: "#fb7185" }}>Sin coincidencias por ahora — probá con otro nombre, apellido o RUT.</div>
            )}
            {correos.length > 0 && (
              <div data-testid="importar-correo-lista" style={{ display: "grid", gap: 6 }}>
                {correos.map((c, i) => (
                  <label key={i} data-testid={`importar-correo-item-${i}`}
                    style={{ display: "flex", alignItems: "flex-start", gap: 12, padding: "0.8rem 1rem", background: sel[i] ? "rgba(20,184,166,0.12)" : "rgba(255,255,255,0.04)", border: `1px solid ${sel[i] ? "#14b8a6" : "rgba(255,255,255,0.1)"}`, borderRadius: 0, cursor: c.message_id ? "pointer" : "default", fontSize: "1rem" }}>
                    {c.message_id && <input type="checkbox" checked={!!sel[i]} onChange={() => setSel(s => ({ ...s, [i]: !s[i] }))} style={{ marginTop: 4, width: 18, height: 18, accentColor: "#14b8a6" }} />}
                    <span style={{ flex: 1 }}>
                      <b style={{ fontSize: "1.02rem", lineHeight: 1.35 }}>{c.subject || "(sin asunto)"}</b>
                      <span style={{ display: "block", opacity: 0.8, fontSize: "0.9rem", marginTop: 3 }}>{c.from}</span>
                      <span style={{ display: "block", opacity: 0.6, fontSize: "0.82rem", marginTop: 2 }}>{c.date} · casilla {c.cuenta}</span>
                    </span>
                  </label>
                ))}
              </div>
            )}
            {msg && <div data-testid="importar-correo-msg" style={{ fontSize: 12.5, fontWeight: 700, color: msg.startsWith("✅") ? "#34eab9" : (msg.startsWith("⚠️") ? "#facc15" : "#fb7185") }}>{msg}</div>}
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button data-testid="importar-correo-cerrar" onClick={() => setOpen(false)}
                style={{ background: "rgba(255,255,255,0.1)", border: "none", color: "#fff", borderRadius: 0, padding: "0.5rem 1rem", fontWeight: 700, cursor: "pointer" }}>Cerrar</button>
              <button data-testid="importar-correo-ejecutar" onClick={importar} disabled={importando}
                style={{ background: "#14b8a6", border: "none", color: "#04211d", borderRadius: 0, padding: "0.5rem 1.1rem", fontWeight: 800, cursor: "pointer" }}>
                <i className={`fa ${importando ? "fa-spinner fa-spin" : "fa-cloud-download"}`} style={{ marginRight: "0.4rem" }} />
                {importando ? "Importando adjuntos…" : "Importar seleccionados"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
