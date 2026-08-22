import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { API_URL } from "../utils/formatters";
import { S, PLAYFAIR } from "./theme";
import DocViewer from "./DocViewer";
import PinModal from "./PinModal";

const CANALES = ["llamada", "whatsapp", "correo", "presencial"];

export default function VentasFicha({ cid, onVolver }) {
  const [det, setDet] = useState(null);
  const [docSel, setDocSel] = useState(null);
  const [file, setFile] = useState(null);
  const [tipo, setTipo] = useState("");
  const [subiendo, setSubiendo] = useState(false);
  const [bloqueo, setBloqueo] = useState(null);
  const [pinAbierto, setPinAbierto] = useState(false);
  const [contacto, setContacto] = useState({ canal: "llamada", nota: "" });

  const cargar = useCallback(() => {
    axios.get(`${API_URL}/api/victoria/clientes/${cid}`)
      .then(r => setDet(r.data))
      .catch(e => toast.error(e.response?.data?.detail || "No se pudo cargar la ficha"));
  }, [cid]);
  useEffect(() => { cargar(); }, [cargar]);

  const ejecutarSubida = async (pin = "") => {
    setSubiendo(true);
    const fd = new FormData();
    fd.append("file", file);
    fd.append("tipo", tipo);
    if (pin) fd.append("pin", pin);
    try {
      const r = await axios.post(`${API_URL}/api/victoria/clientes/${cid}/subir`, fd);
      toast.success(r.data.forzado
        ? `«${r.data.doc.archivo}» cargado con PIN: registrado como carga forzada`
        : `«${r.data.doc.archivo}» subido, clasificado y validado`);
      setFile(null); setBloqueo(null);
      cargar();
      setDocSel(r.data.doc.id);
    } catch (er) {
      const d = er.response?.data?.detail;
      if (er.response?.status === 409 && d?.codigo === "VALIDACION_BLOQUEADA") {
        setBloqueo(d);
        toast.error("Validación irrenunciable: los datos no coinciden con la ficha");
      } else if (pin) { toast.error(typeof d === "string" ? d : "PIN rechazado"); throw er; }
      else toast.error(typeof d === "string" ? d : "No se pudo subir el documento");
    }
    setSubiendo(false);
  };

  const registrarContacto = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${API_URL}/api/ventas/clientes/${cid}/contacto-registro`, contacto);
      toast.success("Contacto registrado en el historial del cliente");
      setContacto({ canal: "llamada", nota: "" });
      cargar();
    } catch (er) { toast.error(er.response?.data?.detail || "No se pudo registrar el contacto"); }
  };

  const cambiarEstado = async (estado) => {
    try {
      const r = await axios.put(`${API_URL}/api/ventas/clientes/${cid}/estado`, { estado });
      toast.success(`Estado del cliente actualizado a «${r.data.etiqueta}»`);
      cargar();
    } catch (er) { toast.error(er.response?.data?.detail || "No se pudo actualizar el estado"); }
  };

  if (!det) return <div style={{ padding: "4rem", color: "#a1a1aa", fontSize: "1.1rem" }}>Cargando ficha…</div>;
  const c = det.cliente;
  const v = c.ventas || {};
  const contactos = [...(v.contactos || [])].reverse();
  const presentes = new Set(det.docs.filter(d => d.revision?.decision !== "rechazado").map(d => d.tipo));
  const docSelObj = det.docs.find(d => d.id === docSel) || null;
  const ESTADOS = { en_gestion: "En gestión", contactado: "Contactado", esperando_documentos: "Esperando documentos", documentacion_completa: "Documentación completa", sin_respuesta: "Sin respuesta", enviado_mesa: "Enviado a mesa", aprobado: "Aprobado", rechazado: "Rechazado" };

  return (
    <div data-testid="ventas-ficha" style={{ padding: "2.5rem 3rem", maxWidth: 1500, margin: "0 auto" }}>
      <button data-testid="ventas-btn-volver" onClick={onVolver} style={{ ...S.btnLine, ...S.btnSmall, marginBottom: 18 }}>
        ← Volver a mi panel de Ventas (conserva su posición)</button>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: 14 }}>
        <div>
          <div style={S.label}>Ficha de gestión · Módulo Ventas</div>
          <h1 style={{ ...S.h1, marginTop: 6 }} data-testid="ventas-ficha-nombre">{c.nombre}</h1>
          <div style={{ color: "#a1a1aa", fontSize: "0.98rem", marginTop: 6 }}>
            RUT {c.rut || "—"} · asignado a {v.ejecutivo_nombre} el {String(v.asignado_en || "").slice(0, 10)} · entrega inmediata</div>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <label style={{ ...S.label, fontSize: "0.7rem" }}>Estado del cliente</label>
          <select data-testid="ventas-estado-select" value={v.estado || "en_gestion"}
            onChange={e => cambiarEstado(e.target.value)} style={{ ...S.input, width: 240, padding: "0.6rem 0.8rem" }}>
            {Object.entries(ESTADOS).map(([k, et]) => <option key={k} value={k}>{et}</option>)}
          </select>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1.3fr", gap: 22, marginTop: 22, alignItems: "start" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <div style={{ ...S.card, padding: "1.5rem 1.7rem" }}>
            <div style={S.label}>Estado de la documentación</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 10 }}>
              {Object.entries(det.requeridos).map(([t, et]) => (
                <div key={t} data-testid={`ventas-req-${t}`} style={{
                  border: `1px solid ${presentes.has(t) ? "rgba(34,197,94,0.5)" : "rgba(245,158,11,0.5)"}`,
                  borderRadius: 4, padding: "0.7rem 0.9rem", fontSize: "0.9rem", fontWeight: 700,
                  color: presentes.has(t) ? "#4ade80" : "#f59e0b" }}>
                  {presentes.has(t) ? "✓ " : "⏳ "}{et}</div>
              ))}
            </div>
            {det.docs.map(d => (
              <div key={d.id} style={{ borderTop: "1px solid rgba(255,255,255,0.08)", padding: "0.7rem 0", display: "flex", justifyContent: "space-between", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                <span style={{ fontSize: "0.9rem", color: "#e4e4e7", wordBreak: "break-all" }}>{d.archivo}
                  <span style={{ color: "#71717a" }}> · {det.tipos[d.tipo]}</span></span>
                <button data-testid={`ventas-doc-ver-${d.id}`} onClick={() => setDocSel(d.id)}
                  style={{ ...S.btnLine, ...S.btnSmall, padding: "0.4rem 0.8rem" }}>Ver documento</button>
              </div>
            ))}
            <form onSubmit={(e) => { e.preventDefault(); if (!file) { toast.error("Seleccione el archivo a subir"); return; } ejecutarSubida(); }}
              style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 12, borderTop: "1px solid rgba(255,255,255,0.1)", paddingTop: 12 }}>
              <input type="file" data-testid="ventas-subir-archivo" onChange={e => setFile(e.target.files[0])} style={{ ...S.input, padding: "0.5rem" }} />
              <select data-testid="ventas-subir-tipo" value={tipo} onChange={e => setTipo(e.target.value)} style={S.input}>
                <option value="">Clasificación automática por contenido</option>
                {Object.entries(det.tipos).map(([t, et]) => <option key={t} value={t}>{et}</option>)}
              </select>
              <button type="submit" data-testid="ventas-subir-btn" disabled={subiendo} style={S.btnGold}>
                {subiendo ? "Subiendo y validando…" : "Subir documento con validación irrenunciable"}</button>
              {bloqueo && (
                <div data-testid="ventas-subir-bloqueo" style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.5)", borderRadius: 4, padding: "0.9rem 1rem" }}>
                  <div style={{ color: "#f87171", fontWeight: 700, fontSize: "0.9rem" }}>⛔ {bloqueo.mensaje}</div>
                  {(bloqueo.fallas || []).map((x, i) => (
                    <div key={i} style={{ color: "#f87171", fontSize: "0.84rem", marginTop: 5 }}>
                      ✕ {x.etiqueta}: ficha «{x.esperado}» ≠ documento «{x.detectado}»</div>))}
                  <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
                    <button type="button" data-testid="ventas-subir-forzar" onClick={() => setPinAbierto(true)}
                      style={{ ...S.btnDanger, ...S.btnSmall }}>Subir de todas formas con mi PIN de seguridad</button>
                    <button type="button" onClick={() => setBloqueo(null)} style={{ ...S.btnLine, ...S.btnSmall }}>
                      Cancelar y corregir primero</button>
                  </div>
                </div>
              )}
            </form>
          </div>

          <div style={{ ...S.card, padding: "1.5rem 1.7rem" }}>
            <div style={S.label}>Contactos realizados ({contactos.length})</div>
            <form onSubmit={registrarContacto} style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
              <select data-testid="ventas-contacto-canal" value={contacto.canal}
                onChange={e => setContacto(s => ({ ...s, canal: e.target.value }))}
                style={{ ...S.input, width: 140, padding: "0.55rem 0.7rem" }}>
                {CANALES.map(cn => <option key={cn} value={cn}>{cn}</option>)}
              </select>
              <input data-testid="ventas-contacto-nota" style={{ ...S.input, flex: "1 1 200px" }} required
                placeholder="¿Qué se conversó / acordó con el cliente?"
                value={contacto.nota} onChange={e => setContacto(s => ({ ...s, nota: e.target.value }))} />
              <button type="submit" data-testid="ventas-contacto-registrar" style={{ ...S.btnGold, ...S.btnSmall }}>
                Registrar contacto realizado</button>
            </form>
            {contactos.map((r, i) => (
              <div key={i} style={{ borderTop: "1px solid rgba(255,255,255,0.08)", padding: "0.65rem 0" }}>
                <div style={{ fontSize: "0.9rem", color: "#fff" }}>
                  <b style={{ color: "#FCF6BA" }}>{r.canal}</b> · {String(r.fecha || "").slice(0, 16).replace("T", " ")}</div>
                <div style={{ color: "#a1a1aa", fontSize: "0.88rem", marginTop: 3 }}>{r.nota}</div>
              </div>
            ))}
          </div>
        </div>

        <DocViewer doc={docSelObj} onActualizado={cargar} />
      </div>

      {pinAbierto && <PinModal pinConfigurado={bloqueo?.pin_configurado} onClose={() => setPinAbierto(false)}
        titulo="Va a subir un documento cuyos datos no coinciden con la ficha del cliente."
        onConfirmar={(pin) => ejecutarSubida(pin)} />}
    </div>
  );
}
