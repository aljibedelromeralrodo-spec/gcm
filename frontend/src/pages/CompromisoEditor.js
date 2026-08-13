import { useState, useEffect, useRef } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

const ORO = "#d4af37";
const MONO = "'JetBrains Mono', monospace";
const fmtCLP = (n) => "$" + Math.round(Number(n) || 0).toLocaleString("es-CL");
const fmtUF = (n) => (Number(n) || 0).toLocaleString("es-CL", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " UF";

// ── Números a palabras (estilo notarial, español de Chile) ──
const U = ["", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve", "veinte", "veintiuno", "veintidós", "veintitrés", "veinticuatro", "veinticinco", "veintiséis", "veintisiete", "veintiocho", "veintinueve"];
const D = ["", "", "", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta", "noventa"];
const C = ["", "ciento", "doscientos", "trescientos", "cuatrocientos", "quinientos", "seiscientos", "setecientos", "ochocientos", "novecientos"];
function _tres(n) {
  if (n === 0) return "";
  if (n === 100) return "cien";
  const c = Math.floor(n / 100), r = n % 100;
  let s = C[c];
  if (r > 0) {
    if (r < 30) s += (s ? " " : "") + U[r];
    else {
      const d = Math.floor(r / 10), u = r % 10;
      s += (s ? " " : "") + D[d] + (u ? " y " + U[u] : "");
    }
  }
  return s;
}
export function numeroAPalabras(num) {
  num = Math.round((Number(num) || 0) * 100) / 100;
  const entero = Math.floor(num);
  const dec = Math.round((num - entero) * 100);
  let s;
  if (entero === 0) s = "cero";
  else {
    const millones = Math.floor(entero / 1000000), miles = Math.floor((entero % 1000000) / 1000), resto = entero % 1000;
    const partes = [];
    if (millones) partes.push(millones === 1 ? "un millón" : _tres(millones).replace(/uno$/, "un") + " millones");
    if (miles) partes.push(miles === 1 ? "mil" : _tres(miles).replace(/uno$/, "un") + " mil");
    if (resto) partes.push(_tres(resto));
    s = partes.join(" ");
  }
  if (dec > 0) s += ` coma ${_tres(dec) || "cero"}`;
  return s;
}
const ufPalabras = (n) => `${numeroAPalabras(n)} unidades de fomento`;
const clpPalabras = (n) => `${numeroAPalabras(Math.round(Number(n) || 0))} pesos chilenos`;

const inp = {
  width: "100%", boxSizing: "border-box", background: "rgba(255,255,255,0.05)", color: ORO,
  border: "1px solid rgba(212,175,55,0.35)", padding: "0.35rem 0.55rem",
  fontFamily: MONO, fontSize: "0.74rem", fontWeight: 600, marginBottom: 6,
};
const oroVacio = { border: `2px solid ${ORO}`, background: "rgba(212,175,55,0.16)", boxShadow: "0 0 18px -4px rgba(212,175,55,0.8)" };
const lbl = { fontSize: "0.6rem", textTransform: "uppercase", letterSpacing: "0.08em", opacity: 0.6, display: "block", marginBottom: 2 };
const secTitle = { fontSize: "0.72rem", fontWeight: 800, color: ORO, letterSpacing: "0.1em", textTransform: "uppercase", margin: "14px 0 8px", borderBottom: "1px solid rgba(212,175,55,0.25)", paddingBottom: 4 };

function personaHTML(p, rol) {
  const F = "[COMPLETAR]";
  return `<b>${p.nombre || F}</b>, ${p.nacionalidad || "chilena"}, ${p.profesion || F}, ` +
    `${p.estado_civil || F}, cédula nacional de identidad N° <b>${p.rut || F}</b>, ` +
    `con domicilio en ${p.domicilio || F}, en adelante "${rol}"`;
}

const ufTxt = (n) => n > 0 ? `<b>${fmtUF(n)}</b> (${ufPalabras(n)})` : "<b>[POR DEFINIR]</b>";
const clpTxt = (n, uf) => (n > 0 && uf > 0) ? `<b>${fmtCLP(n * uf)}</b> (${clpPalabras(n * uf)})` : "<b>[POR DEFINIR]</b>";

export function buildFinanzasHTML(d, ufHoy) {
  const uf = Number(ufHoy) || 0;
  const totalUF = Number(d.precio.valor_total_uf) || 0;
  const pieUF = Number(d.precio.pie_uf) || 0;
  const saldoUF = Math.max(0, Math.round((totalUF - pieUF) * 100) / 100);
  const clausulaPie = d.precio.pie_recibido ? `
<div data-testid="clausula-pie-blindada" style="border:1.5pt solid #000000;background:#ffffff;padding:12px 16px;margin:8px 0 12px">
<p style="margin:0;color:#000000"><b>DÉCIMO: PRECIO Y FORMA DE PAGO.</b> El precio de la venta es la suma de ${ufTxt(totalUF)}. De este monto, el comprador paga en este acto la suma de ${ufTxt(pieUF)}, equivalentes a ${clpTxt(pieUF, uf)} al valor UF del día de hoy (${uf > 0 ? fmtCLP(uf) : "[POR DEFINIR]"} al ${new Date().toLocaleDateString("es-CL")}), dinero que el vendedor declara recibir a su entera y total satisfacción, otorgando por este instrumento el más amplio y completo finiquito respecto de dicha suma.</p>
</div>` : `
<p><b>SEGUNDO — Precio y forma de pago.</b> El precio de la venta es la suma de ${ufTxt(totalUF)}. De este monto, el comprador pagará por concepto de pie la suma de ${ufTxt(pieUF)}, equivalentes a ${clpTxt(pieUF, uf)} al valor UF del día de hoy, en la forma y oportunidad que las partes acuerden por escrito.</p>`;
  return `<div id="cm-finanzas" contenteditable="false">${clausulaPie}
<p><b>Saldo de precio (bloqueo de cálculo):</b> el saldo restante, ascendente a ${saldoUF > 0 ? ufTxt(saldoUF) : "<b>[POR DEFINIR]</b>"}, equivalente a ${clpTxt(saldoUF, uf)} al valor UF del día, corresponde a la diferencia exacta entre el Precio Total y el Pie ya pagado, y se pagará mediante <b>crédito hipotecario</b> otorgado por la institución financiera que apruebe la operación, al momento de la firma de la escritura definitiva de compraventa.</p>
<p><b>Garantía del saldo:</b> ${d.precio.garantia || "El pago del saldo de precio quedará garantizado mediante instrucciones notariales irrevocables o vale vista bancario, a elección de las partes, entregadas en la notaría al momento de la firma de la escritura definitiva."}</p></div>`;
}

export function buildCompromisoHTML(datos, ufHoy) {
  const d = datos;
  const uf = Number(ufHoy) || 0;
  const totalUF = Number(d.precio.valor_total_uf) || 0;
  const pieUF = Number(d.precio.pie_uf) || 0;
  const saldoUF = Math.max(0, Math.round((totalUF - pieUF) * 100) / 100);
  const pieCLP = pieUF * uf;
  const multaUF = Number(d.resguardos.clausula_penal_uf) || 0;
  const gastosTxt = { comprador: "serán de cargo exclusivo del Comprador", vendedor: "serán de cargo exclusivo del Vendedor", ambos: "serán solventados por ambas partes en proporciones iguales" }[d.resguardos.gastos] || "serán solventados por ambas partes en proporciones iguales";
  const insc = (d.propiedad.fojas || d.propiedad.numero || d.propiedad.anio)
    ? `El dominio se encuentra inscrito a fojas <b>${d.propiedad.fojas || "[COMPLETAR]"}</b>, número <b>${d.propiedad.numero || "[COMPLETAR]"}</b>, del año <b>${d.propiedad.anio || "[COMPLETAR]"}</b>, en el Registro de Propiedad del Conservador de Bienes Raíces de <b>${d.propiedad.cbr || "[COMPLETAR]"}</b>.`
    : `La inscripción de dominio será acreditada con los certificados correspondientes del Conservador de Bienes Raíces.`;
  // REGLA DE HIERRO: cláusulas financieras SIEMPRE reconstruidas desde datos.precio en vivo
  const clausulaPie = `
<h2 style="color:#000000;font-weight:700">SEGUNDO — Precio y forma de pago.</h2>
<p>El precio de la venta es la suma de ${ufTxt(totalUF)}, equivalente a ${clpTxt(totalUF, uf)} al valor UF del día. De este monto, el Comprador ${d.precio.pie_recibido ? "ha pagado por concepto de pie" : "pagará por concepto de pie"} la suma de ${ufTxt(pieUF)}, equivalentes a ${clpTxt(pieUF, uf)}${d.precio.pie_recibido ? ", según se declara en la cláusula SÉPTIMA del presente instrumento" : ", en la forma y oportunidad que las partes acuerden por escrito"}.</p>`;
  const clausulaFiniquito = d.precio.pie_recibido ? `
<h2 style="color:#000000;font-weight:700">SÉPTIMA — Declaración de pago y finiquito del pie.</h2>
<p>El Vendedor declara bajo juramento haber recibido del Comprador, de manera íntegra, total y oportuna, la suma de ${ufTxt(pieUF)}, equivalente a ${clpTxt(pieUF, uf)} al valor UF del día de hoy (${uf > 0 ? fmtCLP(uf) : "[POR DEFINIR]"} al ${new Date().toLocaleDateString("es-CL")}), por concepto de pie del precio de la compraventa. En consecuencia, el Vendedor otorga al Comprador el más amplio, completo y total finiquito respecto de dicha suma, declarándola íntegramente pagada y renunciando expresamente a toda acción, cobro o reclamación posterior derivada de su pago.</p>` : "";
  return `
<h1 style="color:#000000;-webkit-text-fill-color:#000000;background:none;font-weight:900;font-size:18pt;text-align:center;letter-spacing:1px;text-decoration:none;font-family:'Times New Roman',Times,serif;margin:0 0 6px">COMPROMISO DE COMPRAVENTA</h1>
<p style="text-align:center;color:#000000;font-size:10pt;margin-bottom:18px">Central Mutuos — Documento preparatorio de escritura pública · Valor UF del día: ${fmtCLP(uf)}</p>
<p>En <b>${d.propiedad.comuna || "[COMPLETAR]"}</b>, a ${new Date().toLocaleDateString("es-CL", { day: "numeric", month: "long", year: "numeric" })}, comparecen: por una parte, ${personaHTML(d.vendedor, "el Vendedor")}; y por la otra, ${personaHTML(d.comprador, "el Comprador")}; quienes acuerdan el siguiente compromiso de compraventa:</p>
<h2 style="color:#000000;font-weight:700">PRIMERO — Objeto.</h2>
<p>El Vendedor se obliga a vender, ceder y transferir al Comprador, quien se obliga a comprar, aceptar y adquirir para sí, el inmueble ubicado en <b>${d.propiedad.direccion || "[COMPLETAR]"}</b>, comuna de <b>${d.propiedad.comuna || "[COMPLETAR]"}</b>, Rol de Avalúo N° <b>${d.propiedad.rol_avaluo || "[COMPLETAR]"}</b>. ${insc}</p>
${clausulaPie}
<p><b>Saldo de precio (bloqueo de cálculo):</b> el saldo restante, ascendente a ${saldoUF > 0 ? ufTxt(saldoUF) : "<b>[POR DEFINIR]</b>"}, equivalente a ${clpTxt(saldoUF, uf)} al valor UF del día, corresponde a la diferencia exacta entre el Precio Total y el Pie ya pagado, y se pagará mediante <b>crédito hipotecario</b> otorgado por la institución financiera que apruebe la operación, al momento de la firma de la escritura definitiva de compraventa.</p>
<p><b>Garantía del saldo:</b> ${d.precio.garantia || "El pago del saldo de precio quedará garantizado mediante instrucciones notariales irrevocables o vale vista bancario, a elección de las partes, entregadas en la notaría al momento de la firma de la escritura definitiva."}</p>
<h2 style="color:#000000;font-weight:700">TERCERO — Condición suspensiva.</h2>
<p>La celebración de la compraventa definitiva queda expresamente supeditada a la aprobación del crédito hipotecario del Comprador. Las partes se obligan a suscribir la escritura pública de compraventa dentro del plazo de <b>${d.resguardos.plazo_escritura_dias || 60} días corridos</b> contados desde la comunicación formal de dicha aprobación. Si el crédito no fuere aprobado dentro del plazo señalado, este instrumento quedará sin efecto de pleno derecho, restituyéndose a las partes lo que hubieren entregado, sin ulterior responsabilidad.</p>
<h2 style="color:#000000;font-weight:700">CUARTO — Cláusula penal.</h2>
<p>Si cualquiera de las partes se negare injustificadamente a suscribir la escritura definitiva o se arrepintiere de la presente convención, deberá pagar a la otra, a título de avaluación anticipada de perjuicios, una multa de <b>${fmtUF(multaUF)}</b> (${ufPalabras(multaUF)}), equivalente a <b>${fmtCLP(multaUF * uf)}</b> (${clpPalabras(multaUF * uf)}) al valor UF del día, sin perjuicio del derecho de la parte diligente de exigir además el cumplimiento forzado del contrato.</p>
<h2 style="color:#000000;font-weight:700">QUINTO — Gastos.</h2>
<p>Los gastos notariales, impuestos y derechos que irrogue la celebración de la compraventa definitiva ${gastosTxt}. Los gastos de inscripción en el Conservador de Bienes Raíces serán de cargo del Comprador.</p>
<h2 style="color:#000000;font-weight:700">SEXTO — Domicilio y ejemplares.</h2>
<p>Para todos los efectos legales derivados del presente instrumento, las partes fijan su domicilio en la comuna de <b>${d.propiedad.comuna || "[COMPLETAR]"}</b> y se someten a la competencia de sus Tribunales Ordinarios de Justicia. El presente compromiso se firma en dos ejemplares del mismo tenor, quedando uno en poder de cada parte.</p>
${clausulaFiniquito}
<br/><br/>
<table style="width:100%;margin-top:30px"><tr>
<td style="text-align:center;width:50%"><p>____________________________<br/><b>${d.vendedor.nombre || "[COMPLETAR]"}</b><br/>RUT ${d.vendedor.rut || "[COMPLETAR]"}<br/>VENDEDOR</p></td>
<td style="text-align:center;width:50%"><p>____________________________<br/><b>${d.comprador.nombre || "[COMPLETAR]"}</b><br/>RUT ${d.comprador.rut || "[COMPLETAR]"}<br/>COMPRADOR</p></td>
</tr></table>`;
}

const H1_LEGAL = `<h1 style="color:#000000;-webkit-text-fill-color:#000000;background:none;font-weight:900;font-size:18pt;text-align:center;letter-spacing:1px;text-decoration:none;font-family:'Times New Roman',Times,serif;margin:0 0 6px">`;

// EXTINCIÓN DE DORADOS: sanea documentos guardados con el estilo antiguo
const sobrio = (html) => (html || "")
  .replace(/<h1[^>]*>/i, H1_LEGAL)
  .split("#b8942e").join("#000000")
  .split("#faf6e8").join("#ffffff")
  .split("#d4af37").join("#000000")
  .split("2px solid #000000").join("1.5pt solid #000000")
  .split("color:#555").join("color:#000000");

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

function migrarUF(datos, ufHoy) {
  const p = datos.precio || {};
  const uf = Number(ufHoy) || 1;
  if (p.valor_total_uf === undefined) {
    datos.precio = {
      valor_total_uf: p.valor_total_clp ? Math.round((p.valor_total_clp / uf) * 100) / 100 : 0,
      pie_uf: p.pie_clp ? Math.round((p.pie_clp / uf) * 100) / 100 : 0,
      pie_recibido: !!p.pie_recibido, garantia: p.garantia || "",
    };
  }
  const r = datos.resguardos || {};
  if (r.clausula_penal_uf === undefined) {
    datos.resguardos = { ...r, clausula_penal_uf: r.clausula_penal_clp ? Math.round((r.clausula_penal_clp / uf) * 100) / 100 : 0 };
  }
  return datos;
}

export default function CompromisoEditor({ folder, onClose }) {
  const [datos, setDatos] = useState(null);
  const [ufHoy, setUfHoy] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [manualDirty, setManualDirty] = useState(false);
  const [msg, setMsg] = useState("");
  const docRef = useRef(null);

  useEffect(() => {
    Promise.all([
      axios.get(`${API_URL}/api/compromiso/${folder.id}`),
      axios.get(`${API_URL}/api/valor-uf`),
    ]).then(([r, u]) => {
      const uf = Number(u.data.valor || u.data.uf || u.data.valor_uf) || 0;
      setUfHoy(uf);
      const d = migrarUF(r.data.datos, uf);
      setDatos(d);
      setTimeout(() => {
        // ELIMINACIÓN DE CACHÉ: el documento SIEMPRE nace del formulario, nunca de clausulas_html guardado
        if (docRef.current) {
          docRef.current.innerHTML = buildCompromisoHTML(d, uf);
          setManualDirty(false);
        }
      }, 50);
      setLoading(false);
    }).catch(() => { setMsg("🚨 Error cargando el compromiso"); setLoading(false); });
  }, [folder.id]);

  const set = (sec, k, v) => {
    setDatos(prev => {
      const next = { ...prev, [sec]: { ...prev[sec], [k]: v } };
      if (!manualDirty && docRef.current) docRef.current.innerHTML = buildCompromisoHTML(next, ufHoy);
      return next;
    });
  };

  const regenerar = () => {
    if (manualDirty && !window.confirm("↻ Regenerar el documento desde el formulario reemplazará sus ediciones manuales. ¿Continuar?")) return;
    if (docRef.current) docRef.current.innerHTML = buildCompromisoHTML(datos, ufHoy);
    setManualDirty(false);
  };

  const guardar = async () => {
    setSaving(true);
    try {
      await axios.put(`${API_URL}/api/compromiso/${folder.id}`, { datos, clausulas_html: "" });
      setMsg("✅ Borrador guardado");
    } catch { setMsg("🚨 Error al guardar"); }
    setSaving(false);
  };

  const descargarPDF = async () => {
    setPdfBusy(true);
    try {
      // VERIFICACIÓN SII: UF oficial capturada EN VIVO en el segundo de la generación, sin fallback antiguo
      let ufFinal = 0;
      try {
        const u = await axios.get(`${API_URL}/api/valor-uf`);
        if (u.data.en_vivo !== false) ufFinal = Number(u.data.valor_uf) || 0;
      } catch { /* sin conexión al SII */ }
      if (!(ufFinal > 0)) {
        setMsg("🚨 UF SII no disponible en vivo. Reintente en unos segundos.");
        setPdfBusy(false);
        return;
      }
      setUfHoy(ufFinal);
      // SINCRONIZACIÓN ATÓMICA: reconstrucción total desde el formulario, ignora manualDirty
      const htmlFinal = sobrio(buildCompromisoHTML(datos, ufFinal));
      if (docRef.current) docRef.current.innerHTML = htmlFinal;
      setManualDirty(false);
      const r = await axios.post(`${API_URL}/api/compromiso/${folder.id}/pdf`,
        { html: htmlFinal }, { responseType: "blob" });
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
  const saldoUF = datos ? Math.max(0, Math.round(((Number(datos.precio.valor_total_uf) || 0) - (Number(datos.precio.pie_uf) || 0)) * 100) / 100) : 0;
  const precioUF = datos ? Number(datos.precio.valor_total_uf) || 0 : 0;
  // REGLA DE PRECISIÓN: LTV truncado a 2 decimales — jamás redondea hacia arriba
  const ltvPct = precioUF > 0 ? Math.floor((saldoUF / precioUF) * 10000 + 1e-6) / 100 : 0;
  const topeNormativoUF = Math.round(precioUF * 0.80 * 100) / 100;
  const excesoLTV = precioUF > 0 && saldoUF > topeNormativoUF + 0.005;

  return (
    <div data-testid="compromiso-editor" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.92)", zIndex: 400, display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "0.7rem 1.2rem", borderBottom: "1px solid rgba(212,175,55,0.35)", background: "#0a0a0a" }}>
        <b style={{ color: ORO, letterSpacing: "0.08em" }}>📜 EDITOR MAESTRO DE COMPROMISOS — {folder.nombre}</b>
        <span style={{ fontSize: "0.68rem", color: "#94a3b8", fontFamily: MONO }} data-testid="comp-uf-hoy">UF hoy: {fmtCLP(ufHoy)}</span>
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
            <div style={secTitle}>💰 Módulo Financiero — Moneda Maestra UF</div>
            <label style={lbl}>Precio de Venta (UF)</label>
            <input data-testid="comp-precio-valor-uf" type="number" step="0.01" placeholder="⟡ INGRESAR UF"
              style={{ ...inp, ...(!datos.precio.valor_total_uf ? oroVacio : {}) }}
              value={datos.precio.valor_total_uf || ""} onChange={e => set("precio", "valor_total_uf", Number(e.target.value))} />
            {datos.precio.valor_total_uf > 0 && <div style={{ fontSize: "0.62rem", opacity: 0.6, marginTop: -4, marginBottom: 6, fontFamily: MONO }}>≈ {fmtCLP(datos.precio.valor_total_uf * ufHoy)} hoy</div>}
            <label style={lbl}>Monto del Pie (UF)</label>
            <input data-testid="comp-precio-pie-uf" type="number" step="0.01" placeholder="⟡ INGRESAR UF"
              className={!datos.precio.pie_uf ? "shimmer-oro" : ""}
              style={{ ...inp, ...(!datos.precio.pie_uf ? oroVacio : {}) }}
              value={datos.precio.pie_uf || ""} onChange={e => set("precio", "pie_uf", Number(e.target.value))} />
            {datos.precio.pie_uf > 0 && <div style={{ fontSize: "0.62rem", opacity: 0.6, marginTop: -4, marginBottom: 6, fontFamily: MONO }}>≈ {fmtCLP(datos.precio.pie_uf * ufHoy)} al valor UF de hoy</div>}
            <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.68rem", opacity: 0.9, margin: "2px 0 8px", cursor: "pointer" }}>
              <input data-testid="comp-pie-recibido" type="checkbox" checked={!!datos.precio.pie_recibido} onChange={e => set("precio", "pie_recibido", e.target.checked)} />
              El vendedor declara haber recibido a su entera satisfacción el pago del pie (activa la cláusula SÉPTIMA blindada)
            </label>
            <div data-testid="comp-saldo-precio" style={{ ...inp, background: "rgba(212,175,55,0.1)", border: `1px solid ${ORO}`, fontWeight: 800 }}>
              ⚖ SALDO DE PRECIO (auto): {fmtUF(saldoUF)} ≈ {fmtCLP(saldoUF * ufHoy)}
            </div>
            <label style={lbl}>Monto Crédito Hipotecario (bloqueado = saldo exacto)</label>
            <div data-testid="comp-credito-bloqueado" style={{ ...inp, opacity: 0.85, background: "rgba(255,255,255,0.03)", ...(excesoLTV ? { border: "1.5px solid #ef4444", boxShadow: "0 0 14px -4px rgba(239,68,68,0.8)" } : {}) }}>
              🔒 {fmtUF(saldoUF)} — diferencia exacta Precio Total − Pie
            </div>
            {precioUF > 0 && (
              <div data-testid="comp-ltv" style={{ ...inp, fontWeight: 800, background: excesoLTV ? "rgba(239,68,68,0.12)" : "rgba(16,201,138,0.08)",
                border: `1px solid ${excesoLTV ? "#ef4444" : "#10c98a"}`, color: excesoLTV ? "#fb7185" : "#10c98a" }}>
                📐 FINANCIAMIENTO (LTV): {ltvPct.toFixed(2).replace(".", ",")}% {excesoLTV ? "" : "· dentro de norma"}
              </div>
            )}
            {excesoLTV && (
              <div data-testid="comp-alerta-ltv" style={{ background: "rgba(127,29,29,0.4)", border: "1.5px solid #ef4444", color: "#fecaca",
                padding: "0.55rem 0.75rem", fontSize: "0.7rem", fontWeight: 800, marginBottom: 8, letterSpacing: "0.04em" }}>
                🚨 EXCESO DE LÍMITE NORMATIVO 80% — el crédito ({fmtUF(saldoUF)}) supera el máximo permitido de {fmtUF(topeNormativoUF)}. Aumente el pie o baje el precio.
              </div>
            )}
            <label style={lbl}>Garantía (instrucciones notariales / Vale Vista)</label>
            <textarea data-testid="comp-precio-garantia" style={{ ...inp, minHeight: 54, resize: "vertical" }} value={datos.precio.garantia || ""} onChange={e => set("precio", "garantia", e.target.value)} placeholder="Ej: Vale vista bancario entregado en instrucciones notariales irrevocables…" />
            <div style={secTitle}>🛡 Cláusulas de Resguardo</div>
            <label style={lbl}>Condición Suspensiva — plazo firma escritura (días desde aprobación del crédito)</label>
            <input data-testid="comp-resg-plazo" type="number" style={inp} value={datos.resguardos.plazo_escritura_dias || ""} onChange={e => set("resguardos", "plazo_escritura_dias", Number(e.target.value))} />
            <label style={lbl}>Cláusula Penal — multa por incumplimiento (UF)</label>
            <input data-testid="comp-resg-penal-uf" type="number" step="0.01" style={inp} value={datos.resguardos.clausula_penal_uf || ""} onChange={e => set("resguardos", "clausula_penal_uf", Number(e.target.value))} />
            <label style={lbl}>Gastos notariales de cargo de</label>
            <select data-testid="comp-resg-gastos" style={inp} value={datos.resguardos.gastos} onChange={e => set("resguardos", "gastos", e.target.value)}>
              <option value="comprador">Comprador</option>
              <option value="vendedor">Vendedor</option>
              <option value="ambos">Ambos (50/50)</option>
            </select>
          </div>
          {/* ══ VISTA PREVIA EN VIVO (100% editable, salvo cláusula de pie blindada) ══ */}
          <div style={{ overflowY: "auto", padding: "1.2rem 2rem", background: "#1c1c1f" }}>
            <div style={{ display: "flex", gap: 6, marginBottom: 8, alignItems: "center" }}>
              <span style={{ fontSize: "0.62rem", color: ORO, letterSpacing: "0.12em", fontWeight: 800 }}>VISTA PREVIA EN VIVO — TEXTO EDITABLE (CLÁUSULA DE PIE BLINDADA 🔒)</span>
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
              style={{ background: "#ffffff", color: "#000000", minHeight: "90%", padding: "3rem 3.4rem",
                fontFamily: "'Times New Roman', Times, serif", fontSize: "0.9rem", lineHeight: 1.5,
                border: "none", boxShadow: "none", outline: "none", maxWidth: 820, margin: "0 auto" }} />
          </div>
        </div>
      )}
    </div>
  );
}
