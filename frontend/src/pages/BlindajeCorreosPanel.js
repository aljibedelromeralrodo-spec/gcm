import { useEffect, useState } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

const TONO = {
  pendiente: { bg: "#fef3c7", fg: "#92400e", label: "Pendiente" },
  autorizado: { bg: "#dcfce7", fg: "#166534", label: "Autorizado" },
  editado: { bg: "#dbeafe", fg: "#1e40af", label: "Editado" },
  rechazado: { bg: "#fee2e2", fg: "#991b1b", label: "Rechazado" },
  enviado: { bg: "#dcfce7", fg: "#14532d", label: "Enviado" },
  error: { bg: "#fee2e2", fg: "#7f1d1d", label: "Error" },
};

function Badge({ estado }) {
  const t = TONO[estado] || { bg: "#e2e8f0", fg: "#334155", label: estado || "—" };
  return (
    <span style={{ background: t.bg, color: t.fg, fontSize: 11, fontWeight: 800,
      padding: "2px 8px", letterSpacing: 0.04 }}>{t.label}</span>
  );
}

export default function BlindajeCorreosPanel() {
  const [tab, setTab] = useState("bandeja");
  const [estado, setEstado] = useState(null);
  const [protos, setProtos] = useState([]);
  const [autos, setAutos] = useState([]);
  const [filtro, setFiltro] = useState("pendiente");
  const [sel, setSel] = useState(null);
  const [draft, setDraft] = useState({ asunto: "", destinatario: "", body_html: "", motivo: "" });
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");

  const load = async () => {
    const [e, p, a] = await Promise.all([
      axios.get(`${API}/api/blindaje-correos/estado`),
      axios.get(`${API}/api/blindaje-correos/protocolos`),
      axios.get(`${API}/api/blindaje-correos/autorizaciones?estado=${filtro}`),
    ]);
    setEstado(e.data);
    setProtos(p.data.protocolos || []);
    setAutos(a.data.autorizaciones || []);
  };

  useEffect(() => { load().catch((err) => setMsg(err.response?.data?.detail || err.message)); }, [filtro]);

  useEffect(() => {
    const aid = sessionStorage.getItem("cm_abrir_auth_id");
    if (!aid || !autos.length) return;
    const hit = autos.find((a) => a.id === aid);
    if (hit) {
      sessionStorage.removeItem("cm_abrir_auth_id");
      abrir(hit);
    }
  }, [autos]);

  const abrir = (a) => {
    setSel(a);
    setDraft({
      asunto: a.asunto_propuesto || "",
      destinatario: a.destinatario || "",
      body_html: a.mensaje_propuesto || "",
      motivo: "",
    });
  };

  const decidir = async (accion) => {
    if (!sel) return;
    setBusy(accion);
    setMsg("");
    try {
      const r = await axios.post(`${API}/api/blindaje-correos/autorizaciones/${sel.id}/decidir`, {
        accion,
        asunto: draft.asunto,
        destinatario: draft.destinatario,
        body_html: draft.body_html,
        motivo: draft.motivo,
      });
      setMsg(accion === "rechazar" ? "Rechazado." : `Listo: ${r.data.estado}`);
      setSel(null);
      await load();
    } catch (e) {
      setMsg(e.response?.data?.detail || e.message);
    } finally { setBusy(""); }
  };

  return (
    <div data-testid="blindaje-panel">
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 14 }}>
        {[
          ["bandeja", "Bandeja autorización"],
          ["protocolos", "Protocolos"],
        ].map(([k, lab]) => (
          <button key={k} onClick={() => setTab(k)} data-testid={`blindaje-tab-${k}`}
            style={{ border: "1px solid #d4af37", background: tab === k ? "#d4af37" : "#fff",
              color: tab === k ? "#0a0a0a" : "#92400e", fontWeight: 800, padding: "6px 12px", cursor: "pointer" }}>
            {lab}
          </button>
        ))}
      </div>

      {estado && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))", gap: 8, marginBottom: 16 }}>
          {[
            ["Versión", estado.version],
            ["Pendientes", estado.autorizaciones_pendientes],
            ["Cola activa", estado.cola_activa],
            ["Enviados", estado.enviados],
            ["Envío", "SMTP gerardo.ext · sin Emergent"],
          ].map(([k, v]) => (
            <div key={k} style={{ border: "1px solid #e2e8f0", padding: "8px 10px", background: "#f8fafc" }}>
              <div style={{ fontSize: 11, color: "#64748b", fontWeight: 700 }}>{k}</div>
              <div style={{ fontSize: 15, fontWeight: 800, color: "#1a1f2e" }}>{v}</div>
            </div>
          ))}
        </div>
      )}
      {msg && <p style={{ color: "#92400e", fontWeight: 700, fontSize: 13 }}>{msg}</p>}

      {tab === "protocolos" && (
        <div style={{ display: "grid", gap: 10 }}>
          {protos.map((p) => (
            <div key={p.id} data-testid={`proto-${p.id}`}
              style={{ border: "1px solid #e2e8f0", padding: 12, background: "#fff" }}>
              <div style={{ fontWeight: 800 }}>{p.nombre} <span style={{ color: "#64748b", fontWeight: 600 }}>· {p.id}</span></div>
              <div style={{ fontSize: 12, color: "#475569", marginTop: 4 }}>
                Valida con {p.valida_con || "—"}
                {p.requiere_codeudor ? " · exige codeudor" : ""}
                {p.dias_licencia_max ? ` · licencia máx ${p.dias_licencia_max} días` : ""}
              </div>
              <div style={{ fontSize: 12, marginTop: 6 }}>
                <b>Obligatorios:</b> {(p.documentos_requeridos || []).join(" · ")}
              </div>
              {(p.documentos_opcionales || []).length > 0 && (
                <div style={{ fontSize: 12, color: "#64748b" }}>
                  <b>Opcionales:</b> {p.documentos_opcionales.join(" · ")}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {tab === "bandeja" && (
        <div style={{ display: "grid", gridTemplateColumns: sel ? "1fr 1.1fr" : "1fr", gap: 14 }}>
          <div>
            <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
              {["pendiente", "autorizado", "rechazado", "todas"].map((f) => (
                <button key={f} onClick={() => setFiltro(f)}
                  style={{ fontSize: 11, fontWeight: 800, padding: "4px 8px", cursor: "pointer",
                    border: "1px solid #cbd5e1", background: filtro === f ? "#1a1f2e" : "#fff",
                    color: filtro === f ? "#fff" : "#334155" }}>{f}</button>
              ))}
            </div>
            {autos.length === 0 && <p style={{ color: "#64748b", fontSize: 13 }}>Sin solicitudes {filtro === "todas" ? "" : filtro}.</p>}
            {autos.map((a) => (
              <button key={a.id} onClick={() => abrir(a)} data-testid={`auth-${a.id}`}
                style={{ display: "block", width: "100%", textAlign: "left", cursor: "pointer",
                  border: `1px solid ${sel?.id === a.id ? "#d4af37" : "#e2e8f0"}`,
                  background: sel?.id === a.id ? "rgba(212,175,55,0.08)" : "#fff",
                  padding: "10px 12px", marginBottom: 6 }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                  <b>{a.cliente_nombre || "Sin nombre"}</b>
                  <Badge estado={a.estado} />
                </div>
                <div style={{ fontSize: 12, color: "#64748b" }}>
                  {a.protocolo_detectado} · faltan {(a.documentos_faltan || []).length}
                </div>
              </button>
            ))}
          </div>

          {sel && (
            <div data-testid="blindaje-detalle" style={{ border: "1px solid #d4af37", padding: 14, background: "#fff" }}>
              <h3 style={{ margin: "0 0 8px", fontSize: 16 }}>{sel.cliente_nombre}</h3>
              <p style={{ margin: "0 0 10px", fontSize: 12, color: "#64748b" }}>
                Protocolo {sel.protocolo_detectado} · RUT {sel.cliente_rut || "—"}
              </p>
              <div style={{ fontSize: 12, marginBottom: 8 }}>
                <b>Tiene:</b> {(sel.documentos_tiene || []).join(", ") || "—"}<br />
                <b>Faltan:</b> {(sel.documentos_faltan || []).join(", ") || "—"}
              </div>
              <label style={lab}>Destinatario</label>
              <input value={draft.destinatario} onChange={(e) => setDraft({ ...draft, destinatario: e.target.value })}
                style={inp} />
              <label style={lab}>Asunto</label>
              <input value={draft.asunto} onChange={(e) => setDraft({ ...draft, asunto: e.target.value })}
                style={inp} />
              <label style={lab}>Cuerpo (HTML)</label>
              <textarea value={draft.body_html} rows={8}
                onChange={(e) => setDraft({ ...draft, body_html: e.target.value })}
                style={{ ...inp, fontFamily: "ui-monospace, monospace", fontSize: 12 }} />
              {sel.estado === "pendiente" && (
                <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
                  <button disabled={!!busy} onClick={() => decidir("autorizar")}
                    data-testid="blindaje-autorizar"
                    style={{ ...btn, background: "#166534", color: "#fff" }}>
                    {busy === "autorizar" ? "Enviando…" : "Autorizar y enviar"}
                  </button>
                  <button disabled={!!busy} onClick={() => decidir("editar")}
                    style={{ ...btn, background: "#1e40af", color: "#fff" }}>Guardar edición</button>
                  <button disabled={!!busy} onClick={() => decidir("rechazar")}
                    style={{ ...btn, background: "#991b1b", color: "#fff" }}>Rechazar</button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const lab = { display: "block", fontSize: 11, fontWeight: 800, color: "#64748b", marginTop: 8 };
const inp = { width: "100%", boxSizing: "border-box", padding: "6px 8px", border: "1px solid #cbd5e1" };
const btn = { border: "none", padding: "8px 12px", fontWeight: 800, cursor: "pointer" };
