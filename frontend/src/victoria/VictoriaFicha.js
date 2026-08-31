import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { API_URL } from "../utils/formatters";
import { S, GOLD, PLAYFAIR, PASOS, ESTADO_PILL } from "./theme";
import DocViewer from "./DocViewer";
import PinModal from "./PinModal";
import PreviewFlotante from "./PreviewFlotante";
import AuditoriaCampos from "./AuditoriaCampos";

const COIN_COLOR = { true: "#4ade80", false: "#f87171", null: "#f59e0b" };
const CAMPOS_FORM = [
  ["nombre_cliente", "Nombre del cliente"],
  ["rut_titular", "RUT del cliente principal"],
  ["rut_codeudor", "RUT del codeudor (vacío si no hay)"],
  ["rol_avaluo", "Rol de avalúo fiscal de la propiedad"],
  ["direccion_propiedad", "Dirección exacta de la propiedad"],
];

function Contacto({ det, cargar }) {
  const c = det.cliente;
  const [f, setF] = useState({ email: c.email || "", telefono: c.telefono || "" });
  const [mail, setMail] = useState(null);
  const [enviando, setEnviando] = useState(false);

  const guardar = async () => {
    try {
      await axios.put(`${API_URL}/api/victoria/clientes/${c.id}/contacto`, f);
      toast.success("Datos de contacto del cliente guardados");
      cargar();
    } catch (e) { toast.error(e.response?.data?.detail || "No se pudo guardar el contacto"); }
  };

  const enviarCorreo = async (e) => {
    e.preventDefault();
    setEnviando(true);
    try {
      const r = await axios.post(`${API_URL}/api/victoria/clientes/${c.id}/enviar-correo`,
        { email: f.email, asunto: mail.asunto, mensaje: mail.mensaje });
      toast.success(r.data.mensaje);
      setMail(null);
    } catch (er) { toast.error(er.response?.data?.detail || "No se pudo enviar el correo"); }
    setEnviando(false);
  };

  const faltan = (det.requeridos && det.docs)
    ? Object.values(det.requeridos).filter(et => !det.docs.some(d => det.tipos[d.tipo] === et && (d.revision?.decision !== "rechazado")))
    : [];
  const msjWA = encodeURIComponent(
    `Estimado/a ${c.nombre}, le saluda Daniela Galindo de Central Mutuos. Le escribo por su operación hipotecaria.` +
    (faltan.length ? ` Para avanzar necesitamos los siguientes documentos: ${faltan.join(", ")}.` : " Su carpeta avanza según lo previsto.") +
    " Quedo atenta. Muchas gracias.");

  return (
    <div data-testid="ficha-contacto" style={{ ...S.card, padding: "1.5rem 2rem", marginTop: 20 }}>
      <div style={S.label}>Contactabilidad directa con el cliente</div>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 12, alignItems: "center" }}>
        <input data-testid="contacto-email" style={{ ...S.input, flex: "2 1 260px" }} placeholder="Correo del cliente"
          value={f.email} onChange={e => setF(s => ({ ...s, email: e.target.value }))} />
        <input data-testid="contacto-telefono" style={{ ...S.input, flex: "1 1 200px" }} placeholder="Teléfono (+569XXXXXXXX)"
          value={f.telefono} onChange={e => setF(s => ({ ...s, telefono: e.target.value }))} />
        <button data-testid="contacto-guardar" onClick={guardar} style={{ ...S.btnLine, ...S.btnSmall }}>
          Guardar datos de contacto del cliente</button>
        <button data-testid="contacto-abrir-correo" onClick={() => setMail({ asunto: "Su operación hipotecaria — Central Mutuos", mensaje: "" })}
          disabled={!f.email} style={{ ...S.btnGold, ...S.btnSmall, opacity: f.email ? 1 : 0.4 }}>
          <i className="fa fa-envelope" style={{ marginRight: 6 }}></i>Redactar y enviar correo al cliente</button>
        <a data-testid="contacto-whatsapp" href={f.telefono ? `https://wa.me/${f.telefono.replace("+", "")}?text=${msjWA}` : undefined}
          target="_blank" rel="noreferrer"
          style={{ ...S.btnLine, ...S.btnSmall, textDecoration: "none", color: "#4ade80", borderColor: "rgba(34,197,94,0.5)", opacity: f.telefono ? 1 : 0.4, pointerEvents: f.telefono ? "auto" : "none" }}>
          <i className="fa fa-whatsapp" style={{ marginRight: 6 }}></i>Abrir WhatsApp con mensaje pre-armado</a>
      </div>
      {mail && (
        <form onSubmit={enviarCorreo} data-testid="contacto-form-correo" style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 10, borderTop: "1px solid rgba(255,255,255,0.1)", paddingTop: 16 }}>
          <label style={S.label}>Correo directo a {f.email} (se envía desde la cuenta corporativa del sistema)</label>
          <input data-testid="correo-asunto" style={S.input} value={mail.asunto} required
            onChange={e => setMail(s => ({ ...s, asunto: e.target.value }))} placeholder="Asunto del correo" />
          <textarea data-testid="correo-mensaje" style={{ ...S.input, minHeight: 110, fontFamily: "inherit" }} value={mail.mensaje} required
            onChange={e => setMail(s => ({ ...s, mensaje: e.target.value }))} placeholder="Escriba aquí el mensaje para el cliente…" />
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <button type="submit" data-testid="correo-enviar" disabled={enviando} style={S.btnGold}>
              {enviando ? "Enviando…" : `Enviar este correo ahora a ${f.email}`}</button>
            <button type="button" data-testid="correo-cancelar" onClick={() => setMail(null)} style={S.btnLine}>
              Descartar el correo sin enviar</button>
          </div>
        </form>
      )}
    </div>
  );
}

function Paso1({ det, cargar, docSel, onSetDocSel }) {
  const [file, setFile] = useState(null);
  const [tipo, setTipo] = useState("");
  const [subiendo, setSubiendo] = useState(false);
  const [bloqueo, setBloqueo] = useState(null);
  const [pinAbierto, setPinAbierto] = useState(false);
  const docSelObj = det.docs.find(d => d.id === docSel) || null;

  const ejecutarSubida = async (pin = "") => {
    setSubiendo(true);
    const fd = new FormData();
    fd.append("file", file);
    fd.append("tipo", tipo);
    if (pin) fd.append("pin", pin);
    try {
      const r = await axios.post(`${API_URL}/api/victoria/clientes/${det.cliente.id}/subir`, fd);
      toast.success(r.data.forzado
        ? `«${r.data.doc.archivo}» cargado con PIN: quedó registrado como carga forzada`
        : `«${r.data.doc.archivo}» subido, clasificado como ${det.tipos[r.data.doc.tipo]} y auditado`);
      setFile(null); setBloqueo(null);
      cargar();
      onSetDocSel(r.data.doc.id);
    } catch (er) {
      const d = er.response?.data?.detail;
      if (er.response?.status === 409 && d?.codigo === "VALIDACION_BLOQUEADA") {
        setBloqueo(d);
        toast.error("Validación irrenunciable: hay datos que no coinciden con la ficha del cliente");
      } else if (pin) {
        toast.error(typeof d === "string" ? d : "PIN rechazado");
        throw er;
      } else toast.error(typeof d === "string" ? d : "No se pudo subir el documento");
    }
    setSubiendo(false);
  };

  const subir = (e) => {
    e.preventDefault();
    if (!file) { toast.error("Seleccione primero el archivo a subir"); return; }
    ejecutarSubida();
  };

  const cambiarTipo = async (did, t) => {
    try {
      await axios.put(`${API_URL}/api/victoria/documentos/${did}/tipo`, { tipo: t });
      toast.success(`Documento reclasificado como ${det.tipos[t]} y set re-auditado`);
      cargar();
    } catch (e) { toast.error(e.response?.data?.detail || "No se pudo reclasificar"); }
  };

  const presentes = new Set(det.docs.filter(d => d.revision?.decision !== "rechazado").map(d => d.tipo));
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1.4fr", gap: 24, alignItems: "start" }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        <div style={{ ...S.card, padding: "1.6rem 1.8rem" }}>
          <div style={S.label}>Set de crédito requerido</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 12 }}>
            {Object.entries(det.requeridos).map(([t, et]) => (
              <div key={t} data-testid={`requerido-${t}`} style={{
                border: `1px solid ${presentes.has(t) ? "rgba(34,197,94,0.5)" : "rgba(245,158,11,0.5)"}`,
                borderRadius: 4, padding: "0.8rem 1rem", fontSize: "0.95rem", fontWeight: 700,
                color: presentes.has(t) ? "#4ade80" : "#f59e0b" }}>
                {presentes.has(t) ? "✓ " : "⏳ "}{et}
              </div>
            ))}
          </div>
        </div>

        <div style={{ ...S.card, padding: "1.6rem 1.8rem" }}>
          <div style={S.label}>Historial de documentos del cliente ({det.docs.length})</div>
          {det.docs.length === 0 && <p style={{ ...S.body, color: "#71717a", marginTop: 10 }}>
            Aún no hay documentos: llegarán solos desde el correo monitoreado o puede subirlos aquí abajo.</p>}
          {det.docs.map(d => (
            <div key={d.id} data-testid={`doc-fila-${d.id}`} style={{
              borderTop: "1px solid rgba(255,255,255,0.08)", padding: "0.9rem 0",
              background: docSel === d.id ? "rgba(212,175,55,0.06)" : "transparent" }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
                <div style={{ flex: "1 1 220px" }}>
                  <div style={{ fontWeight: 700, color: "#fff", fontSize: "0.98rem", wordBreak: "break-all" }}>{d.archivo}</div>
                  <div style={{ color: "#a1a1aa", fontSize: "0.85rem", marginTop: 3 }}>
                    Recibido {String(d.recibido || "").slice(0, 16).replace("T", " ")} · origen {d.origen}
                    {d.revision && <b style={{ color: d.revision.decision === "aceptado" ? "#4ade80" : "#f87171" }}>
                      {" "}· {d.revision.decision === "aceptado" ? "ACEPTADO" : `RECHAZADO (${d.revision.motivo})`}</b>}
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <select data-testid={`doc-tipo-${d.id}`} value={d.tipo} style={{ ...S.input, width: 185, padding: "0.5rem 0.7rem", fontSize: "0.85rem" }}
                    onChange={e => cambiarTipo(d.id, e.target.value)}>
                    {Object.entries(det.tipos).map(([t, et]) => <option key={t} value={t}>{et}</option>)}
                  </select>
                  <button data-testid={`doc-ver-${d.id}`} onClick={() => onSetDocSel(d.id)}
                    style={{ ...S.btnGold, ...S.btnSmall }}>Ver documento en pantalla</button>
                </div>
              </div>
            </div>
          ))}
        </div>

        <form onSubmit={subir} style={{ ...S.card, padding: "1.6rem 1.8rem", display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={S.label}>Subir documento manualmente a la bóveda</div>
          <input type="file" data-testid="subir-archivo" onChange={e => setFile(e.target.files[0])}
            style={{ ...S.input, padding: "0.6rem" }} />
          <select data-testid="subir-tipo" value={tipo} onChange={e => setTipo(e.target.value)} style={S.input}>
            <option value="">Clasificación automática por contenido</option>
            {Object.entries(det.tipos).map(([t, et]) => <option key={t} value={t}>{et}</option>)}
          </select>
          <button type="submit" data-testid="subir-btn" disabled={subiendo} style={S.btnGold}>
            {subiendo ? "Subiendo y auditando…" : "Subir este documento a la bóveda del cliente"}</button>
          {bloqueo && (
            <div data-testid="subir-bloqueo" style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.5)", borderRadius: 4, padding: "1rem 1.2rem" }}>
              <div style={{ color: "#f87171", fontWeight: 700, fontSize: "0.95rem" }}>
                ⛔ {bloqueo.mensaje}</div>
              {(bloqueo.fallas || []).map((v, i) => (
                <div key={i} style={{ color: "#f87171", fontSize: "0.88rem", marginTop: 6 }}>
                  ✕ {v.etiqueta}: la ficha dice «{v.esperado}» pero el documento dice «{v.detectado}»</div>
              ))}
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 12 }}>
                <button type="button" data-testid="subir-forzar-pin" onClick={() => setPinAbierto(true)}
                  style={{ ...S.btnDanger, ...S.btnSmall }}>
                  Subir de todas formas con mi PIN de seguridad (queda registrado)</button>
                <button type="button" data-testid="subir-cancelar-bloqueo" onClick={() => setBloqueo(null)}
                  style={{ ...S.btnLine, ...S.btnSmall }}>Cancelar y corregir los datos primero</button>
              </div>
            </div>
          )}
        </form>
        {pinAbierto && <PinModal pinConfigurado={bloqueo?.pin_configurado} onClose={() => setPinAbierto(false)}
          titulo="Va a subir un documento cuyos datos no coinciden con la ficha del cliente."
          onConfirmar={(pin) => ejecutarSubida(pin)} />}
      </div>
      <DocViewer doc={docSelObj} onActualizado={cargar} />
    </div>
  );
}

function Paso2({ det, cargar }) {
  const [forms, setForms] = useState(det.formularios_auto || {});
  const [trabajando, setTrabajando] = useState(false);
  // Reinicia el formulario SOLO al cambiar de cliente (no en cada poll, evitaría perder ediciones)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { setForms(det.formularios_auto || {}); }, [det.cliente.id]);

  const guardar = async () => {
    setTrabajando(true);
    try {
      await axios.put(`${API_URL}/api/victoria/clientes/${det.cliente.id}/formularios`,
        { datos: forms, confirmado: det.cliente.formularios_confirmados || false });
      await axios.post(`${API_URL}/api/victoria/clientes/${det.cliente.id}/auditar`, {});
      toast.success("Datos guardados y auditoría de validaciones ejecutada nuevamente");
      cargar();
    } catch (e) { toast.error(e.response?.data?.detail || "No se pudo guardar"); }
    setTrabajando(false);
  };

  const auditar = async () => {
    setTrabajando(true);
    try {
      await axios.post(`${API_URL}/api/victoria/clientes/${det.cliente.id}/auditar`, {});
      toast.success("Auditoría de validaciones ejecutada: resultados actualizados");
      cargar();
    } catch (e) { toast.error(e.response?.data?.detail || "No se pudo auditar"); }
    setTrabajando(false);
  };

  const coin = det.auditoria?.coincidencias || [];
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr", gap: 24, alignItems: "start" }}>
      <div style={{ ...S.card, padding: "1.8rem 2rem" }}>
        <h2 style={{ ...S.h2, marginBottom: 6 }}>Validaciones cruzadas — Reglas de Oro ConCreces 11-14</h2>
        <p style={{ ...S.body, fontSize: "0.92rem", color: "#a1a1aa", margin: "0 0 14px" }}>
          Irrenunciables: no se puede enviar a ConCreces hasta que todo coincida.</p>
        {coin.length === 0 && <p style={{ ...S.body, color: "#f59e0b" }}>
          Aún no hay auditoría: ejecútela con el botón de abajo.</p>}
        {coin.map((x, i) => (
          <div key={i} data-testid={`coincidencia-${i}`} style={{ borderTop: "1px solid rgba(255,255,255,0.08)", padding: "1rem 0" }}>
            <div style={{ display: "flex", gap: 10, alignItems: "baseline" }}>
              <span style={{ fontSize: "1.3rem", color: COIN_COLOR[String(x.ok)] }}>
                {x.ok === true ? "✓" : x.ok === false ? "✕" : "⏳"}</span>
              <div>
                <div style={{ fontWeight: 700, color: "#fff", fontSize: "1rem" }}>{x.regla}</div>
                <div style={{ color: COIN_COLOR[String(x.ok)], fontSize: "0.93rem", marginTop: 4 }}>{x.detalle}</div>
                {(x.docs || []).length > 0 && <div style={{ color: "#71717a", fontSize: "0.83rem", marginTop: 3 }}>{x.docs.join(" · ")}</div>}
              </div>
            </div>
          </div>
        ))}
        <button data-testid="btn-auditar" onClick={auditar} disabled={trabajando} style={{ ...S.btnLine, marginTop: 14 }}>
          Ejecutar auditoría de validaciones nuevamente</button>
      </div>

      <div style={{ ...S.card, padding: "1.8rem 2rem" }}>
        <h2 style={{ ...S.h2, marginBottom: 6 }}>Datos de la operación (auto-rellenados desde los documentos)</h2>
        <p style={{ ...S.body, fontSize: "0.92rem", color: "#a1a1aa", margin: "0 0 14px" }}>
          Corrija aquí lo que la extracción automática haya leído mal.</p>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {CAMPOS_FORM.map(([k, et]) => (
            <div key={k}>
              <label style={{ ...S.label, fontSize: "0.72rem" }}>{et}</label>
              <input data-testid={`form-${k}`} style={{ ...S.input, marginTop: 4 }} value={forms[k] || ""}
                onChange={e => setForms(s => ({ ...s, [k]: e.target.value }))} />
            </div>
          ))}
          <button data-testid="btn-guardar-formularios" onClick={guardar} disabled={trabajando} style={S.btnGold}>
            {trabajando ? "Guardando…" : "Guardar datos corregidos y re-auditar validaciones"}</button>
        </div>
      </div>
    </div>
  );
}

function Paso3({ det, cargar }) {
  const [envio, setEnvio] = useState(null);
  const [trabajando, setTrabajando] = useState(false);
  const [traz, setTraz] = useState(null);

  useEffect(() => {
    const h = async (e) => {
      if (e.data?.tipo !== "dato-trazable") return;
      try {
        const r = await axios.get(`${API_URL}/api/victoria/clientes/${det.cliente.id}/origen-dato/${e.data.campo}`);
        setTraz(r.data);
      } catch (er) {
        toast.error(er.response?.data?.detail || "No hay documento de origen para este dato");
      }
    };
    window.addEventListener("message", h);
    return () => window.removeEventListener("message", h);
  }, [det.cliente.id]);

  const verDocEnvio = async () => {
    try {
      const r = await axios.get(`${API_URL}/api/victoria/clientes/${det.cliente.id}/documento-envio`);
      setEnvio(r.data);
    } catch (e) { toast.error(e.response?.data?.detail || "No se pudo generar el documento"); }
  };

  const confirmarForms = async () => {
    setTrabajando(true);
    try {
      await axios.put(`${API_URL}/api/victoria/clientes/${det.cliente.id}/formularios`,
        { datos: det.formularios_auto, confirmado: true });
      toast.success("Formularios confirmados como revisados y correctos");
      cargar();
    } catch (e) { toast.error(e.response?.data?.detail || "No se pudo confirmar"); }
    setTrabajando(false);
  };

  const aud = det.auditoria || {};
  const presentes = new Set(det.docs.filter(d => d.revision?.decision !== "rechazado").map(d => d.tipo));
  const faltan = Object.keys(det.requeridos).filter(t => !presentes.has(t));
  const criticas = (aud.alertas || []).filter(a => a.nivel === "critica");
  const advertencias = (aud.alertas || []).filter(a => a.nivel !== "critica");
  const coinMal = (aud.coincidencias || []).filter(c => c.ok !== true);
  const checks = [
    [faltan.length === 0, faltan.length === 0 ? "Set de crédito completo: los 4 documentos requeridos están en la bóveda"
      : `Faltan documentos requeridos: ${faltan.map(t => det.requeridos[t]).join(", ")}`],
    [criticas.length === 0, criticas.length === 0 ? "Sin alertas críticas de auditoría"
      : `${criticas.length} alerta(s) crítica(s): ${criticas[0]?.detalle || ""}`],
    [coinMal.length === 0 && (aud.coincidencias || []).length > 0,
      coinMal.length === 0 && (aud.coincidencias || []).length > 0
        ? "Reglas de Oro 11-14: todas las coincidencias validadas"
        : "Coincidencias pendientes o en conflicto — resuélvalas en el Paso 2"],
    [!!det.cliente.formularios_confirmados, det.cliente.formularios_confirmados
      ? "Formularios revisados y confirmados por Daniela"
      : "Formularios aún sin confirmar — confírmelos aquí abajo tras revisar el documento"],
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ ...S.card, padding: "1.8rem 2rem" }}>
        <h2 style={{ ...S.h2, marginBottom: 14 }}>Checklist completo de la operación</h2>
        {checks.map(([ok, txt], i) => (
          <div key={i} data-testid={`checklist-item-${i}`} style={{ display: "flex", gap: 12, alignItems: "baseline", padding: "0.7rem 0", borderTop: "1px solid rgba(255,255,255,0.08)" }}>
            <span style={{ fontSize: "1.25rem", color: ok ? "#4ade80" : "#f87171" }}>{ok ? "✓" : "✕"}</span>
            <span style={{ ...S.body, fontSize: "1rem", color: ok ? "#d4d4d8" : "#f87171" }}>{txt}</span>
          </div>
        ))}
        {advertencias.length > 0 && (
          <div style={{ marginTop: 12, color: "#f59e0b", fontSize: "0.92rem" }}>
            Advertencias no bloqueantes: {advertencias.map(a => a.detalle).join(" · ")}</div>
        )}
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 18 }}>
          <button data-testid="btn-ver-doc-envio" onClick={verDocEnvio} style={S.btnLine}>
            Generar y ver el documento de envío a ConCreces</button>
          {!det.cliente.formularios_confirmados && (
            <button data-testid="btn-confirmar-formularios" onClick={confirmarForms} disabled={trabajando} style={S.btnGold}>
              Confirmar que los formularios están revisados y correctos</button>
          )}
        </div>
      </div>
      {envio && (
        <div style={{ ...S.card, padding: "1.5rem" }} data-testid="doc-envio-preview">
          <div style={{ ...S.label, marginBottom: 6 }}>Documento de envío (revisión en pantalla, sin descarga)</div>
          <p style={{ ...S.body, fontSize: "0.85rem", color: "#a1a1aa", margin: "0 0 10px" }}>
            Los datos críticos (nombre, RUT, rol, dirección) están subrayados: al hacer clic se abre
            el documento físico de donde se extrajo cada dato, en la página exacta.</p>
          <iframe title="documento de envío" srcDoc={envio.html}
            style={{ width: "100%", height: 520, border: "1px solid rgba(255,255,255,0.1)", borderRadius: 4, background: "#fff" }} />
        </div>
      )}
      {traz && <PreviewFlotante info={traz} onClose={() => setTraz(null)} />}
    </div>
  );
}

function Paso4({ det, cargar }) {
  const [confirmo, setConfirmo] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState("");

  const despachar = async () => {
    setEnviando(true);
    try {
      const r = await axios.post(`${API_URL}/api/victoria/clientes/${det.cliente.id}/despachar`, { confirmado: true });
      setResultado(r.data.mensaje);
      toast.success(r.data.mensaje);
      cargar();
    } catch (e) { toast.error(e.response?.data?.detail || "El envío fue bloqueado"); }
    setEnviando(false);
  };

  const aud = det.auditoria || {};
  const listo = !aud.bloqueado && det.cliente.formularios_confirmados;
  const c = det.cliente;
  return (
    <div style={{ ...S.card, padding: "2.4rem", maxWidth: 860 }}>
      {c.despachado ? (
        <div data-testid="paso4-despachado">
          <div style={{ fontFamily: PLAYFAIR, fontSize: "2rem", color: "#4ade80", fontWeight: 700 }}>
            ✓ Set de crédito enviado a ConCreces</div>
          <p style={{ ...S.body, marginTop: 12 }}>
            Enviado el {String(c.despachado_en || "").slice(0, 16).replace("T", " ")} UTC por {c.despachado_por || "Victoria"}.
            {det.concreces && ` Estado en ConCreces: ${det.concreces.estado?.toUpperCase()} con ${det.concreces.n_documentos} documento(s).`}</p>
          {resultado && <p style={{ color: "#4ade80", fontWeight: 700, marginTop: 8 }}>{resultado}</p>}
        </div>
      ) : (
        <div data-testid="paso4-pendiente">
          <h2 style={{ ...S.h2, marginBottom: 10 }}>Confirmación final antes del envío</h2>
          <p style={{ ...S.body }}>
            Cliente: <b style={{ color: "#fff" }}>{c.nombre}</b> · RUT {c.rut || "—"} ·{" "}
            {det.docs.filter(d => d.revision?.decision !== "rechazado").length} documento(s) válidos en la bóveda.</p>
          {!listo && (
            <div data-testid="paso4-bloqueado" style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.4)", borderRadius: 4, padding: "1.1rem 1.3rem", marginTop: 14, color: "#f87171", fontSize: "0.98rem", fontWeight: 600 }}>
              ⛔ El envío está bloqueado por las Reglas de Oro: complete el checklist del Paso 3
              (coincidencias validadas, sin alertas críticas y formularios confirmados).</div>
          )}
          <label style={{ display: "flex", gap: 12, alignItems: "flex-start", marginTop: 20, cursor: "pointer" }}>
            <input type="checkbox" data-testid="paso4-check-revision" checked={confirmo}
              onChange={e => setConfirmo(e.target.checked)} style={{ width: 22, height: 22, accentColor: GOLD, marginTop: 2 }} />
            <span style={{ ...S.body, fontSize: "1rem" }}>
              Declaro que revisé el documento de envío, los formularios y las validaciones de coincidencia,
              y que este set de crédito está correcto para su presentación a ConCreces.</span>
          </label>
          <button data-testid="paso4-btn-despachar" onClick={despachar} disabled={!confirmo || !listo || enviando}
            style={{ ...S.btnGold, marginTop: 20, width: "100%", padding: "1.1rem", fontSize: "1.1rem",
              opacity: (!confirmo || !listo) ? 0.35 : 1 }}>
            {enviando ? "Despachando…" : `Confirmar envío del set de crédito de ${c.nombre} a ConCreces`}</button>
        </div>
      )}
    </div>
  );
}

export default function VictoriaFicha({ cid, paso, docSel, onSetPaso, onSetDocSel, onVolver }) {
  const [det, setDet] = useState(null);
  const cargar = useCallback(() => {
    axios.get(`${API_URL}/api/victoria/clientes/${cid}`)
      .then(r => setDet(r.data))
      .catch(e => toast.error(e.response?.data?.detail || "No se pudo cargar la ficha"));
  }, [cid]);
  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => {
    const t = setInterval(cargar, 45000);
    return () => clearInterval(t);
  }, [cargar]);

  if (!det) return <div style={{ padding: "4rem", color: "#a1a1aa", fontSize: "1.1rem" }}>Cargando ficha del cliente…</div>;

  const c = det.cliente;
  const est = c.despachado ? "despachado" : (det.auditoria && !det.auditoria.bloqueado && c.formularios_confirmados) ? "listo"
    : (det.auditoria?.bloqueado || !det.auditoria) ? "bloqueado" : "proceso";
  const [bg, fg, txt] = ESTADO_PILL[est];

  return (
    <div data-testid="victoria-ficha" style={{ padding: "2.5rem 3rem", maxWidth: 1600, margin: "0 auto" }}>
      <button data-testid="ficha-btn-volver" onClick={onVolver}
        style={{ ...S.btnLine, ...S.btnSmall, marginBottom: 20 }}>
        ← Volver al panel de Daniela (conserva su posición y filtros)</button>

      <AuditoriaCampos clienteId={cid} />

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: 14 }}>
        <div>
          <div style={S.label}>Ficha de operación · Bóveda independiente</div>
          <h1 style={{ ...S.h1, marginTop: 6 }} data-testid="ficha-nombre">{c.nombre}</h1>
          <div style={{ color: "#a1a1aa", fontSize: "1rem", marginTop: 6 }}>
            RUT {c.rut || "—"} · creado {String(c.creado || "").slice(0, 10)} · origen {c.origen}</div>
        </div>
        <span data-testid="ficha-estado" style={{ ...S.pill(bg, fg), fontSize: "0.95rem", padding: "0.5rem 1.2rem" }}>{txt}</span>
      </div>

      {det.siguiente && !c.despachado && (
        <div data-testid="ficha-siguiente-accion" style={{ marginTop: 16, background: "rgba(212,175,55,0.08)", border: `1px solid rgba(212,175,55,0.4)`, borderRadius: 4, padding: "0.9rem 1.2rem", color: "#FCF6BA", fontSize: "0.98rem", fontWeight: 600 }}>
          Siguiente acción sugerida: {det.siguiente.titulo} — {det.siguiente.detalle}</div>
      )}

      <Contacto det={det} cargar={cargar} />

      <div data-testid="ficha-stepper" style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, margin: "24px 0" }}>
        {PASOS.map(p => (
          <button key={p.n} data-testid={`stepper-paso-${p.n}`} onClick={() => onSetPaso(p.n)}
            style={{ textAlign: "left", cursor: "pointer", borderRadius: 4, padding: "1rem 1.2rem",
              background: paso === p.n ? "rgba(212,175,55,0.12)" : "#141414",
              border: `1px solid ${paso === p.n ? GOLD : "rgba(255,255,255,0.1)"}`, transition: "border-color 0.3s ease" }}>
            <div style={{ fontFamily: PLAYFAIR, fontSize: "1.7rem", fontWeight: 700, color: paso === p.n ? "#FCF6BA" : "#52525b" }}>{p.n}</div>
            <div style={{ fontSize: "0.85rem", fontWeight: 700, color: paso === p.n ? "#fff" : "#a1a1aa", marginTop: 4, lineHeight: 1.35 }}>
              {p.titulo.split("— ")[1]}</div>
          </button>
        ))}
      </div>

      <h2 style={{ ...S.h2, fontSize: "1.6rem", margin: "0 0 18px" }} data-testid="ficha-titulo-paso">
        {PASOS.find(p => p.n === paso)?.titulo}</h2>

      {paso === 1 && <Paso1 det={det} cargar={cargar} docSel={docSel} onSetDocSel={onSetDocSel} />}
      {paso === 2 && <Paso2 det={det} cargar={cargar} />}
      {paso === 3 && <Paso3 det={det} cargar={cargar} />}
      {paso === 4 && <Paso4 det={det} cargar={cargar} />}

      {paso < 4 && (
        <button data-testid="ficha-btn-siguiente-paso" onClick={() => onSetPaso(paso + 1)}
          style={{ ...S.btnLine, marginTop: 24 }}>
          Ir al {PASOS.find(p => p.n === paso + 1)?.titulo} →</button>
      )}
    </div>
  );
}
