import { useState, useEffect, useCallback } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

const card = { background: "rgba(14,14,16,0.9)", padding: "1.2rem", borderRadius: "0px", border: "1px solid transparent", backgroundImage: "linear-gradient(115deg, rgba(255,255,255,0.09) 0%, rgba(255,255,255,0.02) 18%, transparent 32%), linear-gradient(160deg, rgba(30,30,30,0.95), rgba(10,10,10,0.98)), linear-gradient(135deg, #BF953F, #FCF6BA, #B38728, #FBF5B7, #AA771C)", boxShadow: "0 35px 70px -20px rgba(0,0,0,0.95), 0 0 38px -16px rgba(191,149,63,0.45)", backgroundOrigin: "border-box", backgroundClip: "padding-box, padding-box, border-box", marginBottom: "0.8rem" };
const inp = { width: "100%", padding: "0.55rem 0.8rem", borderRadius: 0, border: "1px solid rgba(148,163,184,0.3)", background: "#232326", color: "#e2e8f0", fontSize: "0.9rem" };

export default function BuzonRescateModule() {
  const [pendientes, setPendientes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");
  const [asignando, setAsignando] = useState(null);
  const [clienteInput, setClienteInput] = useState("");
  const [tipoDoc, setTipoDoc] = useState("");
  const [folders, setFolders] = useState([]);
  const [procesando, setProcesando] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [r, rf] = await Promise.all([
        axios.get(`${API}/api/rescate/pendientes`),
        axios.get(`${API}/api/clientes/folders-light`),
      ]);
      setPendientes(r.data.pendientes || []);
      setFolders(rf.data.folders || []);
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const abrirAsignar = (p) => {
    setAsignando(p);
    setClienteInput(p.cliente_sugerido && p.cliente_sugerido.split(" ").length >= 2 ? p.cliente_sugerido : "");
    setTipoDoc("");
    setMsg("");
  };

  const confirmar = async () => {
    if (!clienteInput || clienteInput.trim().split(/\s+/).length < 2) {
      setMsg("Ingresa el nombre completo del cliente (nombre y apellido).");
      return;
    }
    setProcesando(true);
    try {
      const r = await axios.post(`${API}/api/rescate/${asignando.id}/asignar`, {
        cliente: clienteInput.trim(), tipo_documento: tipoDoc,
      }, { timeout: 120000 });
      setMsg(`✅ Correo asignado a "${r.data.cliente}": archivos movidos a su carpeta y procesados.`);
      setAsignando(null);
      load();
    } catch (e) { setMsg("Error: " + (e.response?.data?.detail || e.message)); }
    setProcesando(false);
  };

  return (
    <div style={{ padding: "1.5rem", color: "var(--white)", maxWidth: 1000 }} data-testid="rescate-module">
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: "0.5rem" }}>
        <h2 style={{ margin: 0, color: "var(--gold)", fontSize: "1.3rem" }}><i className="fa fa-life-ring" style={{ marginRight: 8 }} />Buzón de Rescate — Por Clasificar</h2>
        <button onClick={load} data-testid="rescate-refresh" style={{ marginLeft: "auto", background: "rgba(255,255,255,0.1)", border: "none", color: "#fff", borderRadius: 0, padding: "0.4rem 0.9rem", cursor: "pointer", fontWeight: 700 }}>
          <i className="fa fa-refresh" style={{ marginRight: 6 }} />Actualizar
        </button>
      </div>
      <p style={{ fontSize: "0.85rem", opacity: 0.7, marginTop: 0 }}>Correos que el sistema no logró clasificar automáticamente. Asígnalos manualmente y se procesarán como si hubieran sido automáticos.</p>
      {msg && <div data-testid="rescate-msg" style={{ padding: "0.6rem 1rem", borderRadius: 0, background: msg.startsWith("✅") ? "rgba(16,217,142,0.12)" : "rgba(225,29,72,0.12)", border: `1px solid ${msg.startsWith("✅") ? "#10d98e" : "#e11d48"}`, marginBottom: "0.8rem", fontSize: "0.85rem" }}>{msg}</div>}

      {loading && <div style={{ textAlign: "center", padding: "2rem" }}><i className="fa fa-spinner fa-spin" style={{ fontSize: "1.6rem", color: "var(--gold)" }} /></div>}
      {!loading && pendientes.length === 0 && (
        <div style={{ ...card, textAlign: "center", color: "#10d98e" }} data-testid="rescate-vacio">
          <i className="fa fa-check-circle" style={{ fontSize: "1.6rem" }} /><br />No hay correos pendientes por clasificar. Todo procesado automáticamente.
        </div>
      )}

      {pendientes.map((p, i) => (
        <div key={p.id} style={card} data-testid={`rescate-item-${i}`}>
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <div style={{ flex: 1, minWidth: 250 }}>
              <div style={{ fontWeight: 700, fontSize: "0.95rem" }}>{p.subject || "(sin asunto)"}</div>
              <div style={{ fontSize: "0.78rem", opacity: 0.65, marginTop: 3 }}>
                De: {p.sender} · {(p.fecha || "").slice(0, 16).replace("T", " ")}
              </div>
              <div style={{ fontSize: "0.78rem", color: "#f59e0b", marginTop: 3 }}>⚠ {p.motivo}</div>
              {(p.adjuntos || []).length > 0 && (
                <div style={{ fontSize: "0.75rem", opacity: 0.7, marginTop: 3 }}>
                  📎 {p.adjuntos.slice(0, 5).join(" · ")}{p.adjuntos.length > 5 ? ` (+${p.adjuntos.length - 5})` : ""}
                </div>
              )}
            </div>
            <button onClick={() => abrirAsignar(p)} data-testid={`rescate-asignar-${i}`}
              style={{ background: "var(--gold)", border: "none", color: "#1a1f2e", borderRadius: 0, padding: "0.55rem 1.1rem", cursor: "pointer", fontWeight: 800, fontSize: "0.85rem" }}>
              <i className="fa fa-hand-pointer-o" style={{ marginRight: 6 }} />Asignar Manualmente
            </button>
          </div>
        </div>
      ))}

      {asignando && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }} data-testid="rescate-modal">
          <div style={{ background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", border: "1px solid rgba(212,175,55,0.4)", borderRadius: 0, padding: "1.5rem", width: 480, maxWidth: "92vw" }}>
            <h3 style={{ margin: "0 0 0.4rem", color: "var(--gold)" }}>Asignar correo a un cliente</h3>
            <div style={{ fontSize: "0.8rem", opacity: 0.7, marginBottom: "1rem" }}>{asignando.subject}</div>
            <label style={{ fontSize: "0.8rem", display: "block", marginBottom: 4 }}>Nombre del cliente</label>
            <input list="rescate-clientes" style={inp} value={clienteInput} onChange={e => setClienteInput(e.target.value)}
              placeholder="Ej: Melisa Rivera" data-testid="rescate-cliente-input" />
            <datalist id="rescate-clientes">
              {folders.map(f => <option key={f.id} value={f.nombre} />)}
            </datalist>
            <label style={{ fontSize: "0.8rem", display: "block", margin: "0.9rem 0 4px" }}>Tipo de documento (opcional)</label>
            <select style={inp} value={tipoDoc} onChange={e => setTipoDoc(e.target.value)} data-testid="rescate-tipo-select">
              <option value="">Automático (según cada archivo)</option>
              <option value="simulacion">Simulación</option>
              <option value="carta">Carta de aprobación</option>
            </select>
            <div style={{ display: "flex", gap: 10, marginTop: "1.2rem", justifyContent: "flex-end" }}>
              <button onClick={() => setAsignando(null)} data-testid="rescate-cancelar" style={{ background: "rgba(255,255,255,0.1)", border: "none", color: "#fff", borderRadius: 0, padding: "0.55rem 1rem", cursor: "pointer" }}>Cancelar</button>
              <button onClick={confirmar} disabled={procesando} data-testid="rescate-confirmar"
                style={{ background: "#10d98e", border: "none", color: "#052e16", borderRadius: 0, padding: "0.55rem 1.2rem", cursor: "pointer", fontWeight: 800 }}>
                {procesando ? <><i className="fa fa-spinner fa-spin" /> Procesando…</> : "Confirmar y procesar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
