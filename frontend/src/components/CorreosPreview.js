import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { htmlConContrasteCorreo } from "../utils/formatters";

const API = process.env.REACT_APP_BACKEND_URL;
const ORO = "#d4af37";
const LS_ABIERTO = "cm_correos_preview_dock";
const FILTROS_NEGOCIO = [
  { id: "todos", label: "Todos" },
  { id: "en_curso", label: "En curso" },
  { id: "faltantes", label: "Documentos faltantes" },
  { id: "preaprobacion", label: "Pre aprobación" },
  { id: "aprobado", label: "Aprobados" },
  { id: "rechazado", label: "Rechazados" },
];
const btn = (c) => ({ background: "transparent", color: c, border: `1px solid ${c}`, cursor: "pointer",
  padding: "0.28rem 0.7rem", fontWeight: 700, fontSize: "0.7rem" });

function estadoNegocio(c) {
  if (c?.estado_negocio) return c.estado_negocio;
  const nombres = (c?.adjuntos || []).map((a) => a.filename || a.name || "").join(" ");
  const t = `${c?.subject || ""} ${nombres}`.toLowerCase();
  if (/rechaz|no califica|no cumple par[aá]metros|reprobado|denegad/.test(t)) return "rechazado";
  if (/pre[-\s]?aprob|preaprobaci[oó]n|precalific/.test(t)) return "preaprobacion";
  if (/aprobaci[oó]n\s+mesa|agrado de informar|ha sido aprobad|califica para un mutuo|carta[_\s-]?aprobaci[oó]n|hipotecario endosable/.test(t)) return "aprobado";
  if (/documentos?\s+faltantes|faltantes\s+[—\-]|necesitamos (?:que nos hagan llegar )?los siguientes documentos/.test(t)) return "faltantes";
  if (/\bds19\b|simulador|solicitud|evaluar|evaluaci[oó]n|entrega inmediata|antecedentes|\(\s*(sin|con)\s+subsidio/.test(t)) return "en_curso";
  return "otro";
}

function leerDock() {
  try { return localStorage.getItem(LS_ABIERTO) !== "0"; } catch { return true; }
}

export default function CorreosPreview() {
  const [data, setData] = useState(null);
  const [abierto, setAbierto] = useState(null);
  const [oculto, setOculto] = useState(false);
  const [dockAbierto, setDockAbierto] = useState(leerDock);
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  const [filtro, setFiltro] = useState("todos");

  const cargar = useCallback(() => {
    axios.get(`${API}/api/correos-preview`)
      .then(r => setData(r.data))
      .catch(e => { if ([401, 403].includes(e.response?.status)) setOculto(true); });
  }, []);

  useEffect(() => { cargar(); const t = setInterval(cargar, 20000); return () => clearInterval(t); }, [cargar]);

  useEffect(() => {
    if (!abierto) return undefined;
    const onKey = (e) => { if (e.key === "Escape") setAbierto(null); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [abierto]);

  useEffect(() => {
    if (!abierto || filtro === "todos" || !data) return;
    const sigue = (data.correos || []).some((c) => c.id === abierto && estadoNegocio(c) === filtro);
    if (!sigue) setAbierto(null);
  }, [filtro, abierto, data]);

  const setDock = (v) => {
    setDockAbierto(v);
    try { localStorage.setItem(LS_ABIERTO, v ? "1" : "0"); } catch { /* ignore */ }
  };

  if (oculto || !data || !data.total) return null;

  const accion = async (pid, tipo, confirmar) => {
    if (!window.confirm(confirmar)) return;
    setBusy(pid + tipo); setMsg("");
    try {
      const r = await axios.post(`${API}/api/correos-preview/${pid}/${tipo}`);
      setMsg(r.data.enviado ? `✅ Correo enviado a ${r.data.to}` : "🗑 Correo descartado");
      setAbierto(null);
      cargar();
    } catch (e) { setMsg(`🚨 ${e.response?.data?.detail || "Error"}`); }
    setBusy("");
  };

  const verCorreo = (id) => {
    setAbierto((prev) => (prev === id ? null : id));
    if (!dockAbierto) setDock(true);
  };

  const diasRestantes = (iso) => {
    const t = Date.parse(iso || "");
    if (!Number.isFinite(t)) return null;
    return Math.max(0, Math.ceil((t - Date.now()) / 86400000));
  };

  const todos = data.correos || [];
  const visibles = filtro === "todos" ? todos : todos.filter((c) => estadoNegocio(c) === filtro);
  const nNegocio = (id) => (id === "todos" ? todos.length : todos.filter((c) => estadoNegocio(c) === id).length);
  const preAll = todos.filter((c) => c.categoria === "preaprobacion");
  const rechAll = todos.filter((c) => estadoNegocio(c) === "rechazado");
  const otrosAll = todos.filter((c) => c.categoria !== "preaprobacion" && estadoNegocio(c) !== "rechazado");
  const pre = visibles.filter((c) => c.categoria === "preaprobacion");
  const rechazados = visibles.filter((c) => estadoNegocio(c) === "rechazado");
  const otros = visibles.filter((c) => c.categoria !== "preaprobacion" && estadoNegocio(c) !== "rechazado");

  const renderCard = (c, i) => {
    const dias = diasRestantes(c.caduca_el);
    return (
      <div key={c.id} data-testid={`preview-correo-${i}`}
        className={`correos-dock-card ${abierto === c.id ? "is-sel" : ""}`}>
        <div style={{ fontSize: "0.8rem", color: "#F5E7B8", fontWeight: 700, lineHeight: 1.35 }}>
          {c.subject || "(sin asunto)"}
        </div>
        <div data-testid={`preview-destinatario-${i}`} style={{ fontSize: "0.7rem", opacity: 0.75, marginTop: 3 }}>
          <i className="fa fa-envelope" style={{ color: ORO, marginRight: 5 }} />
          Para: {Array.isArray(c.to) ? c.to.join(", ") : c.to}{c.cc ? ` · CC: ${c.cc}` : ""}
        </div>
        <div style={{ fontSize: "0.66rem", opacity: 0.55, marginTop: 2 }}>
          {(c.creado || "").slice(0, 16).replace("T", " ")} · {(c.adjuntos || []).length} adjunto(s)
          {(c.adjuntos || []).length > 0 && `: ${(c.adjuntos || []).map(a => a.filename).join(", ").slice(0, 90)}`}
          {dias != null && ` · caduca en ${dias} día${dias === 1 ? "" : "s"}`}
        </div>
        <div className="correos-dock-actions">
          <button data-testid={`preview-ver-${i}`} style={btn(ORO)}
            onClick={() => verCorreo(c.id)}>
            <i className="fa fa-eye" /> {abierto === c.id ? "Ocultar" : "Ver correo"}
          </button>
          <button data-testid={`preview-descartar-${i}`} disabled={!!busy} style={btn("#e11d48")}
            onClick={() => accion(c.id, "descartar", "¿Descartar este correo?")}>
            <i className="fa fa-times" /> Descartar
          </button>
        </div>
      </div>
    );
  };

  return (
    <>
      <button
        type="button"
        data-testid="correos-preview-tab"
        className={`correos-dock-tab ${dockAbierto ? "is-open" : ""}`}
        aria-expanded={dockAbierto}
        aria-controls="correos-preview-panel"
        title={dockAbierto ? "Ocultar correos" : "Mostrar correos pendientes"}
        onClick={() => setDock(!dockAbierto)}
      >
        <i className={`fa ${dockAbierto ? "fa-chevron-right" : "fa-envelope"}`} />
        <span>Correos ({data.total})</span>
      </button>

      {dockAbierto && (
        <aside id="correos-preview-panel" data-testid="correos-preview-panel" className="correos-dock" role="complementary" aria-label="Buzón de correos">
          <div className="correos-dock-head">
            <i className="fa fa-eye" style={{ color: "#f59e0b" }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <b>Buzón de correos ({data.total})</b>
              <div className="correos-dock-sub">
                Preaprobaciones {preAll.length} · 2 meses · Rechazados {rechAll.length} · 3 días · Otros {otrosAll.length} · 1 semana
              </div>
            </div>
            <button type="button" data-testid="correos-preview-ocultar" className="correos-dock-hide"
              onClick={() => setDock(false)} title="Ocultar panel">
              <i className="fa fa-times" /> Ocultar
            </button>
          </div>
          {msg && <div data-testid="preview-msg" className="correos-dock-msg">{msg}</div>}
          <div className="correos-dock-filtros" data-testid="preview-filtros-negocio" role="tablist" aria-label="Filtrar por etapa del negocio">
            {FILTROS_NEGOCIO.map((f) => (
              <button
                key={f.id}
                type="button"
                role="tab"
                aria-selected={filtro === f.id}
                data-testid={`preview-filtro-${f.id}`}
                className={`correos-dock-filtro ${filtro === f.id ? "is-on" : ""}`}
                onClick={() => setFiltro(f.id)}
              >
                {f.label}
                <span className="correos-dock-filtro-n">{nNegocio(f.id)}</span>
              </button>
            ))}
          </div>
          <div className="correos-dock-list">
            {filtro === "todos" && pre.length > 0 && (
              <div data-testid="preview-grupo-preaprobacion" className="correos-dock-grupo">Preaprobaciones · caducan a los 2 meses</div>
            )}
            {pre.map((c) => renderCard(c, (data.correos || []).indexOf(c)))}
            {(filtro === "todos" || filtro === "rechazado") && rechazados.length > 0 && (
              <div data-testid="preview-grupo-rechazados" className="correos-dock-grupo">Rechazados · se eliminan a los 3 días</div>
            )}
            {rechazados.map((c) => renderCard(c, (data.correos || []).indexOf(c)))}
            {filtro === "todos" && otros.length > 0 && (
              <div data-testid="preview-grupo-otros" className="correos-dock-grupo">Otros · se eliminan a la semana</div>
            )}
            {otros.map((c) => renderCard(c, (data.correos || []).indexOf(c)))}
            {visibles.length === 0 && (
              <div data-testid="preview-filtro-vacio" className="correos-dock-vacio">
                No hay correos en esta etapa.
              </div>
            )}
          </div>
          {abierto && (() => {
            const i = data.correos.findIndex((c) => c.id === abierto);
            const c = i >= 0 ? data.correos[i] : null;
            if (!c) return null;
            return (
              <div className="correos-dock-vista">
                <div className="correos-dock-vista-bar">
                  <div className="correos-dock-vista-label">Vista del correo · tal como lo recibe el destinatario</div>
                  <button
                    type="button"
                    data-testid="preview-cerrar-vista"
                    className="correos-dock-vista-cerrar"
                    aria-label="Cerrar vista del correo"
                    title="Cerrar vista del correo (Esc)"
                    onClick={() => setAbierto(null)}
                  >
                    <i className="fa fa-times" /> Cerrar
                  </button>
                </div>
                <iframe data-testid={`preview-cuerpo-${i}`} title={`preview-${i}`} srcDoc={htmlConContrasteCorreo(c.body_html)}
                  className="correos-dock-iframe" />
              </div>
            );
          })()}
        </aside>
      )}
    </>
  );
}
