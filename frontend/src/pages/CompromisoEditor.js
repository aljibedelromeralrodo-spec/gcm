import { useState, useEffect, useRef } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

const ORO = "#d4af37";
const fmtCLP = (n) => "$" + Math.round(Number(n) || 0).toLocaleString("es-CL");
const MONO = "'JetBrains Mono', monospace";

const inp = {
  width: "100%", boxSizing: "border-box", background: "rgba(255,255,255,0.05)", color: ORO,
  border: "1px solid rgba(212,175,55,0.35)", padding: "0.35rem 0.55rem",
  fontFamily: MONO, fontSize: "0.74rem", fontWeight: 600, marginBottom: 6,
};
const lbl = { fontSize: "0.6rem", textTransform: "uppercase", letterSpacing: "0.08em", opacity: 0.6, display: "block", marginBottom: 2 };
const secTitle = { fontSize: "0.72rem", fontWeight: 800, color: ORO, letterSpacing: "0.1em", textTransform: "uppercase", margin: "14px 0 8px", borderBottom: "1px solid rgba(212,175,55,0.25)", paddingBottom: 4 };

function personaHTML(p, rol) {
  const F = "[COMPLETAR]";
  return `<b>${p.nombre || F}</b>, ${p.nacionalidad || "chilena"}, ${p.profesion || F}, ` +
    `${p.estado_civil || F}, cédula nacional de identidad N° <b>${p.rut || F}</b>, ` +
    `con domicilio en ${p.domicilio || F}, en adelante "${rol}"`;
}

export function buildCompromisoHTML(datos) {
  const d = datos;
  const saldo = Math.max(0, (Number(d.precio.valor_total_clp) || 0) - (Number(d.precio.pie_clp) || 0));
  const gastosTxt = { comprador: "serán de cargo exclusivo del Comprador", vendedor: "serán de cargo exclusivo del Vendedor", ambos: "serán solventados por ambas partes en proporciones iguales" }[d.resguardos.gastos] || "serán solventados por ambas partes en proporciones iguales";
  const pieRecibido = d.precio.pie_recibido
    ? ` El Vendedor declara haber recibido a su entera satisfacción el pago del pie, otorgando el más amplio y completo finiquito respecto de dicha suma.`
    : ` Dicha suma será pagada en la forma y oportunidad que las partes acuerden por escrito.`;
  const insc = (d.propiedad.fojas || d.propiedad.numero || d.propiedad.anio)
    ? `El dominio se encuentra inscrito a fojas <b>${d.propiedad.fojas || "[COMPLETAR]"}</b>, número <b>${d.propiedad.numero || "[COMPLETAR]"}</b>, del año <b>${d.propiedad.anio || "[COMPLETAR]"}</b>, en el Registro de Propiedad del Conservador de Bienes Raíces de <b>${d.propiedad.cbr || "[COMPLETAR]"}</b>.`
    : `La inscripción de dominio será acreditada con los certificados correspondientes del Conservador de Bienes Raíces.`;
  return `
<h1>COMPROMISO DE COMPRAVENTA</h1>
<p style="text-align:center;color:#555;font-size:10pt;margin-bottom:18px">Central Mutuos — Documento preparatorio de escritura pública</p>
<p>En <b>${d.propiedad.comuna || "[COMPLETAR]"}</b>, a ${new Date().toLocaleDateString("es-CL", { day: "numeric", month: "long", year: "numeric" })}, comparecen: por una parte, ${personaHTML(d.vendedor, "el Vendedor")}; y por la otra, ${personaHTML(d.comprador, "el Comprador")}; quienes acuerdan el siguiente compromiso de compraventa:</p>
<h2>PRIMERO — Objeto.</h2>
<p>El Vendedor se obliga a vender, ceder y transferir al Comprador, quien se obliga a comprar, aceptar y adquirir para sí, el inmueble ubicado en <b>${d.propiedad.direccion || "[COMPLETAR]"}</b>, comuna de <b>${d.propiedad.comuna || "[COMPLETAR]"}</b>, Rol de Avalúo N° <b>${d.propiedad.rol_avaluo || "[COMPLETAR]"}</b>. ${insc}</p>
<h2>SEGUNDO — Precio y forma de pago.</h2>
<p>El precio de la compraventa es la suma total de <b>${fmtCLP(d.precio.valor_total_clp)}</b>, que se pagará de la siguiente forma: a) <b>${fmtCLP(d.precio.pie_clp)}</b> por concepto de pie.${pieRecibido} b) El saldo de precio, ascendente a <b>${fmtCLP(saldo)}</b>, se pagará mediante crédito hipotecario por <b>${fmtCLP(d.precio.credito_clp || saldo)}</b> otorgado por la institución financiera que apruebe la operación, al momento de la firma de la escritura definitiva de compraventa.</p>
<p><b>Garantía del saldo:</b> ${d.precio.garantia || "El pago del saldo de precio quedará garantizado mediante instrucciones notariales irrevocables o vale vista bancario, a elección de las partes, entregadas en la notaría al momento de la firma de la escritura definitiva."}</p>
<h2>TERCERO — Condición suspensiva.</h2>
<p>La celebración de la compraventa definitiva queda expresamente supeditada a la aprobación del crédito hipotecario del Comprador. Las partes se obligan a suscribir la escritura pública de compraventa dentro del plazo de <b>${d.resguardos.plazo_escritura_dias || 60} días corridos</b> contados desde la comunicación formal de dicha aprobación. Si el crédito no fuere aprobado dentro del plazo señalado, este instrumento quedará sin efecto de pleno derecho, restituyéndose a las partes lo que hubieren entregado, sin ulterior responsabilidad.</p>
<h2>CUARTO — Cláusula penal.</h2>
<p>Si cualquiera de las partes se negare injustificadamente a suscribir la escritura definitiva o se arrepintiere de la presente convención, deberá pagar a la otra, a título de avaluación anticipada de perjuicios, una multa de <b>${fmtCLP(d.resguardos.clausula_penal_clp)}</b>, sin perjuicio del derecho de la parte diligente de exigir además el cumplimiento forzado del contrato.</p>
<h2>QUINTO — Gastos.</h2>
<p>Los gastos notariales, impuestos y derechos que irrogue la celebración de la compraventa definitiva ${gastosTxt}. Los gastos de inscripción en el Conservador de Bienes Raíces serán de cargo del Comprador.</p>
<h2>SEXTO — Domicilio y ejemplares.</h2>
<p>Para todos los efectos legales derivados del presente instrumento, las partes fijan su domicilio en la comuna de <b>${d.propiedad.comuna || "____________"}</b> y se someten a la competencia de sus Tribunales Ordinarios de Justicia. El presente compromiso se firma en dos ejemplares del mismo tenor, quedando uno en poder de cada parte.</p>
<br/><br/>
<table style="width:100%;margin-top:30px"><tr>
<td style="text-align:center;width:50%"><p>____________________________<br/><b>${d.vendedor.nombre || "[COMPLETAR]"}</b><br/>RUT ${d.vendedor.rut || "[COMPLETAR]"}<br/>VENDEDOR</p></td>
<td style="text-align:center;width:50%"><p>____________________________<br/><b>${d.comprador.nombre || "[COMPLETAR]"}</b><br/>RUT ${d.comprador.rut || "[COMPLETAR]"}<br/>COMPRADOR</p></td>
</tr></table>`;
}

function CampoPersona({ rol, datos, set }) {
  const campos = [["nombre", "Nombre Completo"], ["rut", "RUT"], ["nacionalidad", "Nacionalidad"],
    ["profesion", "Profesión"], ["estado_civil", "Estado Civil"], ["domicilio", "Domicilio"]];
  return (
    <>
      <div style={secTitle}>{rol === "comprador" ? "👤 Comprador" : "🏷 Vendedor"}</div>
      {campos.map(([k, l]) => (
        <div key={k}>
          <label style={lbl}>{l}</label>
          <input data-testid={`comp-${rol}-${k}`} style={inp} value={datos[rol][k] || ""}
            onChange={e => set(rol, k, e.target.value)} />
        </div>
      ))}
    </>
  );
}

export default function CompromisoEditor({ folder, onClose }) {
  const [datos, setDatos] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [manualDirty, setManualDirty] = useState(false);
  const [msg, setMsg] = useState("");
  const docRef = useRef(null);

  useEffect(() => {
    axios.get(`${API_URL}/api/compromiso/${folder.id}`).then(r => {
      setDatos(r.data.datos);
      setTimeout(() => {
        if (docRef.current) {
          docRef.current.innerHTML = r.data.clausulas_html || buildCompromisoHTML(r.data.datos);
          setManualDirty(!!r.data.clausulas_html);
        }
      }, 50);
      setLoading(false);
    }).catch(() => { setMsg("🚨 Error cargando el compromiso"); setLoading(false); });
  }, [folder.id]);

  const set = (sec, k, v) => {
    setDatos(prev => {
      const next = { ...prev, [sec]: { ...prev[sec], [k]: v } };
      if (!manualDirty && docRef.current) docRef.current.innerHTML = buildCompromisoHTML(next);
      return next;
    });
  };

  const regenerar = () => {
    if (manualDirty && !window.confirm("↻ Regenerar el documento desde el formulario reemplazará sus ediciones manuales. ¿Continuar?")) return;
    if (docRef.current) docRef.current.innerHTML = buildCompromisoHTML(datos);
    setManualDirty(false);
  };

  const guardar = async () => {
    setSaving(true);
    try {
      await axios.put(`${API_URL}/api/compromiso/${folder.id}`, {
        datos, clausulas_html: manualDirty ? docRef.current?.innerHTML || "" : "" });
      setMsg("✅ Borrador guardado");
    } catch { setMsg("🚨 Error al guardar"); }
    setSaving(false);
  };

  const descargarPDF = async () => {
    setPdfBusy(true);
    try {
      const r = await axios.post(`${API_URL}/api/compromiso/${folder.id}/pdf`,
        { html: docRef.current?.innerHTML || "" }, { responseType: "blob" });
      const url = URL.createObjectURL(new Blob([r.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `Compromiso_Compraventa_${(folder.nombre || "doc").replace(/\s+/g, "_")}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      setMsg("✅ PDF generado con la versión exacta del editor");
    } catch { setMsg("🚨 Error generando el PDF"); }
    setPdfBusy(false);
  };

  const cmd = (c) => { document.execCommand(c); setManualDirty(true); };
  const saldo = datos ? Math.max(0, (Number(datos.precio.valor_total_clp) || 0) - (Number(datos.precio.pie_clp) || 0)) : 0;

  return (
    <div data-testid="compromiso-editor" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.92)", zIndex: 400, display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "0.7rem 1.2rem", borderBottom: "1px solid rgba(212,175,55,0.35)", background: "#0a0a0a" }}>
        <b style={{ color: ORO, letterSpacing: "0.08em" }}>📜 EDITOR MAESTRO DE COMPROMISOS — {folder.nombre}</b>
        {msg && <span data-testid="compromiso-msg" style={{ fontSize: "0.72rem", color: msg.startsWith("✅") ? "#10c98a" : "#fb7185" }}>{msg}</span>}
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button data-testid="compromiso-regenerar" onClick={regenerar} style={{ background: "transparent", color: "#94a3b8", border: "1px solid rgba(255,255,255,0.2)", padding: "0.4rem 0.9rem", cursor: "pointer", fontSize: "0.72rem" }}>↻ Regenerar desde formulario</button>
          <button data-testid="compromiso-guardar" onClick={guardar} disabled={saving} style={{ background: "rgba(212,175,55,0.15)", color: ORO, border: `1px solid ${ORO}`, padding: "0.4rem 1rem", cursor: "pointer", fontSize: "0.72rem", fontWeight: 800 }}>{saving ? "Guardando…" : "💾 Guardar Borrador"}</button>
          <button data-testid="compromiso-pdf" onClick={descargarPDF} disabled={pdfBusy} className="shimmer-oro" style={{ border: "none", color: "#0a0a0a", fontWeight: 800, padding: "0.4rem 1.2rem", cursor: "pointer", fontSize: "0.72rem", backgroundImage: "linear-gradient(135deg, #BF953F, #FCF6BA 45%, #B38728, #FBF5B7 80%, #AA771C)" }}>{pdfBusy ? "Generando…" : "⬇ Generar y Descargar PDF"}</button>
          <button data-testid="compromiso-cerrar" onClick={onClose} style={{ background: "transparent", color: "#94a3b8", border: "none", fontSize: "1.3rem", cursor: "pointer" }}>✕</button>
        </div>
      </div>
      {loading || !datos ? (
        <div style={{ color: ORO, padding: "2rem", fontFamily: MONO }}>🧠 Pre-llenando con los datos de la carpeta (OCR + IA)…</div>
      ) : (
        <div style={{ flex: 1, display: "grid", gridTemplateColumns: "420px 1fr", overflow: "hidden" }}>
          {/* ══ FORMULARIO ══ */}
          <div style={{ overflowY: "auto", padding: "1rem 1.2rem", background: "linear-gradient(160deg, #121214, #060608)", borderRight: "1px solid rgba(212,175,55,0.25)" }}>
            <CampoPersona rol="comprador" datos={datos} set={set} />
            <CampoPersona rol="vendedor" datos={datos} set={set} />
            <div style={secTitle}>🏠 Datos del Inmueble</div>
            {[["direccion", "Dirección Exacta"], ["comuna", "Comuna"], ["rol_avaluo", "Rol de Avalúo"]].map(([k, l]) => (
              <div key={k}><label style={lbl}>{l}</label>
                <input data-testid={`comp-propiedad-${k}`} style={inp} value={datos.propiedad[k] || ""} onChange={e => set("propiedad", k, e.target.value)} /></div>
            ))}
            <label style={lbl}>Inscripción de Dominio (CBR)</label>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6 }}>
              {[["fojas", "Fojas"], ["numero", "Número"], ["anio", "Año"]].map(([k, l]) => (
                <input key={k} data-testid={`comp-propiedad-${k}`} style={inp} placeholder={l} value={datos.propiedad[k] || ""} onChange={e => set("propiedad", k, e.target.value)} />
              ))}
            </div>
            <label style={lbl}>Conservador de Bienes Raíces de</label>
            <input data-testid="comp-propiedad-cbr" style={inp} value={datos.propiedad.cbr || ""} onChange={e => set("propiedad", "cbr", e.target.value)} />
            <div style={secTitle}>💰 Módulo Financiero</div>
            <label style={lbl}>Valor Total de la Propiedad (CLP)</label>
            <input data-testid="comp-precio-valor" type="number" style={inp} value={datos.precio.valor_total_clp || ""} onChange={e => set("precio", "valor_total_clp", Number(e.target.value))} />
            <label style={lbl}>Monto del Pie (CLP)</label>
            <input data-testid="comp-precio-pie" type="number" placeholder="⟡ INGRESAR MONTO FINAL"
              className={!datos.precio.pie_clp ? "shimmer-oro" : ""}
              style={{ ...inp, ...(!datos.precio.pie_clp ? { border: `2px solid ${ORO}`, background: "rgba(212,175,55,0.16)", boxShadow: "0 0 18px -4px rgba(212,175,55,0.8)" } : {}) }}
              value={datos.precio.pie_clp || ""} onChange={e => set("precio", "pie_clp", Number(e.target.value))} />
            <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.68rem", opacity: 0.85, margin: "2px 0 8px", cursor: "pointer" }}>
              <input data-testid="comp-pie-recibido" type="checkbox" checked={!!datos.precio.pie_recibido} onChange={e => set("precio", "pie_recibido", e.target.checked)} />
              El vendedor declara haber recibido a su entera satisfacción el pago del pie
            </label>
            <div data-testid="comp-saldo-precio" style={{ ...inp, background: "rgba(212,175,55,0.1)", border: `1px solid ${ORO}`, fontWeight: 800 }}>
              ⚖ SALDO DE PRECIO (auto): {fmtCLP(saldo)}
            </div>
            <label style={lbl}>Monto Crédito Hipotecario (CLP)</label>
            <input data-testid="comp-precio-credito" type="number" placeholder="⟡ INGRESAR MONTO FINAL"
              className={!datos.precio.credito_clp ? "shimmer-oro" : ""}
              style={{ ...inp, ...(!datos.precio.credito_clp ? { border: `2px solid ${ORO}`, background: "rgba(212,175,55,0.16)", boxShadow: "0 0 18px -4px rgba(212,175,55,0.8)" } : {}) }}
              value={datos.precio.credito_clp || ""} onChange={e => set("precio", "credito_clp", Number(e.target.value))} />
            <label style={lbl}>Garantía (instrucciones notariales / Vale Vista)</label>
            <textarea data-testid="comp-precio-garantia" style={{ ...inp, minHeight: 54, resize: "vertical" }} value={datos.precio.garantia || ""} onChange={e => set("precio", "garantia", e.target.value)} placeholder="Ej: Vale vista bancario entregado en instrucciones notariales irrevocables…" />
            <div style={secTitle}>🛡 Cláusulas de Resguardo</div>
            <label style={lbl}>Condición Suspensiva — plazo firma escritura (días desde aprobación del crédito)</label>
            <input data-testid="comp-resg-plazo" type="number" style={inp} value={datos.resguardos.plazo_escritura_dias || ""} onChange={e => set("resguardos", "plazo_escritura_dias", Number(e.target.value))} />
            <label style={lbl}>Cláusula Penal — multa por incumplimiento (CLP)</label>
            <input data-testid="comp-resg-penal" type="number" style={inp} value={datos.resguardos.clausula_penal_clp || ""} onChange={e => set("resguardos", "clausula_penal_clp", Number(e.target.value))} />
            <label style={lbl}>Gastos notariales de cargo de</label>
            <select data-testid="comp-resg-gastos" style={inp} value={datos.resguardos.gastos} onChange={e => set("resguardos", "gastos", e.target.value)}>
              <option value="comprador">Comprador</option>
              <option value="vendedor">Vendedor</option>
              <option value="ambos">Ambos (50/50)</option>
            </select>
          </div>
          {/* ══ VISTA PREVIA EN VIVO (100% editable) ══ */}
          <div style={{ overflowY: "auto", padding: "1.2rem 2rem", background: "#1c1c1f" }}>
            <div style={{ display: "flex", gap: 6, marginBottom: 8, alignItems: "center" }}>
              <span style={{ fontSize: "0.62rem", color: ORO, letterSpacing: "0.12em", fontWeight: 800 }}>VISTA PREVIA EN VIVO — TEXTO 100% EDITABLE</span>
              {["bold", "italic", "underline"].map(c => (
                <button key={c} data-testid={`comp-rt-${c}`} onMouseDown={e => { e.preventDefault(); cmd(c); }}
                  style={{ background: "rgba(255,255,255,0.08)", color: "#e5e7eb", border: "1px solid rgba(255,255,255,0.15)", width: 28, height: 24, cursor: "pointer", fontWeight: 800, fontStyle: c === "italic" ? "italic" : "normal", textDecoration: c === "underline" ? "underline" : "none" }}>
                  {c === "bold" ? "B" : c === "italic" ? "I" : "U"}</button>
              ))}
              <button data-testid="comp-rt-parrafo" onMouseDown={e => { e.preventDefault(); document.execCommand("insertHTML", false, "<p>Nuevo párrafo — edite este texto…</p>"); setManualDirty(true); }}
                style={{ background: "rgba(255,255,255,0.08)", color: "#e5e7eb", border: "1px solid rgba(255,255,255,0.15)", height: 24, padding: "0 8px", cursor: "pointer", fontSize: "0.65rem" }}>+ Párrafo</button>
              {manualDirty && <span style={{ fontSize: "0.6rem", color: "#fdba74" }}>✎ con ediciones manuales</span>}
            </div>
            <div ref={docRef} data-testid="compromiso-preview" contentEditable suppressContentEditableWarning
              onInput={() => setManualDirty(true)}
              style={{ background: "#fdfdfb", color: "#111", minHeight: "90%", padding: "3rem 3.4rem",
                fontFamily: "Georgia, 'Times New Roman', serif", fontSize: "0.86rem", lineHeight: 1.65,
                boxShadow: "0 0 50px -12px rgba(212,175,55,0.35)", outline: "none", maxWidth: 820, margin: "0 auto" }} />
          </div>
        </div>
      )}
    </div>
  );
}
