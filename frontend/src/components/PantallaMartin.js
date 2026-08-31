import { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

// Regex insensible a tildes para buscar carpetas ("perez" matchea "PÉREZ")
function rxAcentos(q) {
  const mapa = { a: "[aá]", e: "[eé]", i: "[ií]", o: "[oó]", u: "[uúü]", n: "[nñ]" };
  return (q || "").toLowerCase().split("").map(ch => {
    if (mapa[ch]) return mapa[ch];
    if (ch === " ") return ".*";
    return ch.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }).join("");
}

let narrAudio = null;
async function narrar(texto) {
  try { if (narrAudio) { narrAudio.pause(); narrAudio = null; } } catch (e) { console.error(e); }
  try {
    const r = await axios.post(`${API}/api/central/tts`, { text: texto });
    if (r.data?.audio) {
      narrAudio = new Audio(`data:audio/mp3;base64,${r.data.audio}`);
      narrAudio.play().catch(() => {});
      return;
    }
  } catch (e) { console.error(e); }
  try {
    window.speechSynthesis?.cancel();
    const u = new SpeechSynthesisUtterance(texto);
    u.lang = "es-CL";
    window.speechSynthesis?.speak(u);
  } catch (e) { console.error(e); }
}

export default function PantallaMartin() {
  const [modo, setModo] = useState(null);
  const [carpeta, setCarpeta] = useState(null);
  const [docActual, setDocActual] = useState(null);
  const [correos, setCorreos] = useState([]);
  const [correoIdx, setCorreoIdx] = useState(0);
  const [zoom, setZoom] = useState(100);
  const [aviso, setAviso] = useState("");
  const docUrlRef = useRef(null);
  const modoRef = useRef(null);
  const estadoRef = useRef({});
  useEffect(() => { modoRef.current = modo; }, [modo]);
  useEffect(() => { estadoRef.current = { carpeta, docActual, correos, correoIdx }; },
    [carpeta, docActual, correos, correoIdx]);

  const cerrar = useCallback(() => {
    if (docUrlRef.current) { URL.revokeObjectURL(docUrlRef.current); docUrlRef.current = null; }
    setModo(null); setCarpeta(null); setDocActual(null); setCorreos([]); setZoom(100); setAviso("");
    window.dispatchEvent(new CustomEvent("martin-pantalla-cerrada"));
    try { window.speechSynthesis?.cancel(); if (narrAudio) narrAudio.pause(); } catch (e) { console.error(e); }
  }, []);

  const abrirDocumento = useCallback(async (carp, archivo, idx) => {
    try {
      const r = await axios.get(
        `${API}/api/clientes/folders/${carp.id}/download/${encodeURIComponent(archivo.ruta)}?inline=true`,
        { responseType: "blob" });
      if (docUrlRef.current) URL.revokeObjectURL(docUrlRef.current);
      const url = URL.createObjectURL(r.data);
      docUrlRef.current = url;
      setDocActual({ nombre: archivo.nombre, ruta: archivo.ruta, url, idx });
      setModo("documento");
      setZoom(100);
      narrar(`Acá está ${archivo.nombre.replace(/[_.]/g, " ").replace(/pdf$/i, "")}. Puedes decir más grande, siguiente, o cierra.`);
    } catch (e) {
      setAviso("No pude abrir el documento");
      narrar("No pude abrir ese documento");
    }
  }, []);

  const abrirCarpeta = useCallback(async (query) => {
    try {
      const r = await axios.get(`${API}/api/clientes/folders`, { params: { q: rxAcentos(query) } });
      const f = (r.data?.folders || [])[0];
      if (!f) { narrar(`No encontré ninguna carpeta que se llame ${query}`); setAviso(`Sin resultados para «${query}»`); return; }
      const det = await axios.get(`${API}/api/clientes/folders/${f.id}`);
      const carp = { id: f.id, nombre: det.data?.nombre || f.nombre, archivos: det.data?.archivos || [] };
      setCarpeta(carp);
      setModo("carpeta");
      narrar(`Acá está la carpeta de ${carp.nombre}, tiene ${carp.archivos.length} documentos. Di "abre" y el nombre para verlo, o "cierra" para salir.`);
    } catch (e) {
      console.error("PantallaMartin abrirCarpeta:", e);
      setAviso("Error buscando la carpeta");
      narrar("Tuve un problema buscando esa carpeta");
    }
  }, []);

  const abrirSimulacion = useCallback(async (query) => {
    try {
      const r = await axios.get(`${API}/api/clientes/folders`, { params: { q: rxAcentos(query) } });
      const f = (r.data?.folders || [])[0];
      if (!f) { narrar(`No encontré la carpeta de ${query}`); return; }
      const det = await axios.get(`${API}/api/clientes/folders/${f.id}`);
      const archivos = det.data?.archivos || [];
      const sim = archivos.find(a => /simulad|simulaci/i.test(a.nombre));
      const carp = { id: f.id, nombre: det.data?.nombre || f.nombre, archivos };
      if (!sim) { setCarpeta(carp); setModo("carpeta"); narrar(`${carp.nombre} no tiene simulación guardada. Te muestro la carpeta completa.`); return; }
      setCarpeta(carp);
      abrirDocumento(carp, sim, archivos.indexOf(sim));
    } catch (e) { narrar("Tuve un problema buscando la simulación"); }
  }, [abrirDocumento]);

  const abrirCorreos = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/api/correos-preview`);
      const cs = r.data?.correos || [];
      if (!cs.length) { narrar("No hay correos esperando tu confirmación"); return; }
      setCorreos(cs); setCorreoIdx(0); setModo("correo");
      narrar(`Hay ${cs.length} correos esperando tu confirmación. El primero es ${cs[0].subject}. Di "envíalo" para mandarlo, "siguiente" para ver otro, o "cierra".`);
    } catch (e) { narrar("No pude cargar los correos"); }
  }, []);

  const enviarCorreoActual = useCallback(async () => {
    const { correos: cs, correoIdx: idx } = estadoRef.current;
    const c = cs[idx];
    if (!c) return;
    setAviso("Enviando...");
    try {
      const r = await axios.post(`${API}/api/correos-preview/${c.id}/confirmar`);
      setAviso(`✅ Enviado a ${r.data.to}`);
      narrar(`Listo, correo enviado a ${Array.isArray(r.data.to) ? r.data.to.join(", ") : r.data.to}`);
      const rest = cs.filter((_, i) => i !== idx);
      if (rest.length) { setCorreos(rest); setCorreoIdx(0); } else cerrar();
    } catch (e) {
      setAviso(`🚨 ${e.response?.data?.detail || "Error al enviar"}`);
      narrar("El envío falló, revisa el detalle en pantalla");
    }
  }, [cerrar]);

  // Apertura por evento (desde el chat / vigilia)
  useEffect(() => {
    const h = (e) => {
      const { tipo, query } = e.detail || {};
      setAviso("");
      if (tipo === "correo") abrirCorreos();
      else if (tipo === "simulacion") abrirSimulacion(query);
      else abrirCarpeta(query);
    };
    window.addEventListener("martin-pantalla", h);
    return () => window.removeEventListener("martin-pantalla", h);
  }, [abrirCarpeta, abrirCorreos, abrirSimulacion]);

  // Navegación siguiente/anterior
  const navegar = useCallback((delta) => {
    const { carpeta: carp, docActual: d, correos: cs, correoIdx: ci } = estadoRef.current;
    if (modoRef.current === "correo" && cs.length) {
      const n = (ci + delta + cs.length) % cs.length;
      setCorreoIdx(n);
      narrar(`Correo ${n + 1}: ${cs[n].subject}`);
    } else if (modoRef.current === "documento" && carp && d) {
      const n = (d.idx + delta + carp.archivos.length) % carp.archivos.length;
      abrirDocumento(carp, carp.archivos[n], n);
    }
  }, [abrirDocumento]);

  // ===== CONTROL POR VOZ dentro del modo pantalla =====
  useEffect(() => {
    if (!modo) return;
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    let activo = true;
    const rec = new SR();
    rec.lang = "es-CL";
    rec.continuous = true;
    rec.interimResults = false;
    rec.onresult = (e) => {
      const t = (e.results[e.results.length - 1][0].transcript || "").trim().toLowerCase();
      if (/\bcierra\b|\bsalir\b|\bci[eé]rralo\b/.test(t)) { cerrar(); return; }
      if (/m[aá]s grande|aum[eé]nta|zoom/.test(t)) { setZoom(z => Math.min(z + 25, 250)); return; }
      if (/m[aá]s chico|m[aá]s peque|ach[ií]ca/.test(t)) { setZoom(z => Math.max(z - 25, 50)); return; }
      if (/\bsiguiente\b|\bpr[oó]xim[oa]\b/.test(t)) { navegar(1); return; }
      if (/\banterior\b|\batr[aá]s\b/.test(t)) { navegar(-1); return; }
      if (/env[ií]alo|m[aá]ndalo|env[ií]a el correo/.test(t) && modoRef.current === "correo") { enviarCorreoActual(); return; }
      const mAbre = t.match(/\babre\b\s+(?:el\s+|la\s+)?(.+)$/);
      if (mAbre && modoRef.current === "carpeta") {
        const q = mAbre[1].trim();
        const { carpeta: carp } = estadoRef.current;
        const idx = (carp?.archivos || []).findIndex(a => a.nombre.toLowerCase().includes(q.split(" ")[0]));
        if (idx >= 0) abrirDocumento(carp, carp.archivos[idx], idx);
        else narrar(`No encontré un documento llamado ${q}`);
      }
    };
    rec.onend = () => { if (activo) setTimeout(() => { try { rec.start(); } catch (err) { console.error(err); } }, 350); };
    rec.onerror = () => {};
    const t = setTimeout(() => { try { rec.start(); } catch (err) { console.error(err); } }, 400);
    return () => { activo = false; clearTimeout(t); try { rec.abort(); } catch (err) { console.error(err); } };
  }, [modo, cerrar, navegar, enviarCorreoActual, abrirDocumento]);

  if (!modo) return null;
  const correo = correos[correoIdx];

  return (
    <div className="pantalla-martin" data-testid="pantalla-martin">
      <div className="pantalla-topbar">
        <span className="pantalla-titulo" data-testid="pantalla-titulo">
          <i className="fa fa-desktop" />{" "}
          {modo === "carpeta" && `CARPETA · ${carpeta?.nombre}`}
          {modo === "documento" && `${carpeta ? carpeta.nombre + " · " : ""}${docActual?.nombre}`}
          {modo === "correo" && `CORREO ${correoIdx + 1}/${correos.length} · esperando confirmación`}
        </span>
        <span className="pantalla-voz-hint">
          🎙 {modo === "correo" ? "«envíalo» · «siguiente» · «cierra»" : "«más grande» · «siguiente» · «cierra»"}
        </span>
        <div className="pantalla-botones">
          {modo !== "carpeta" && <>
            <button data-testid="pantalla-zoom-menos" onClick={() => setZoom(z => Math.max(z - 25, 50))}><i className="fa fa-search-minus" /></button>
            <span className="pantalla-zoom">{zoom}%</span>
            <button data-testid="pantalla-zoom-mas" onClick={() => setZoom(z => Math.min(z + 25, 250))}><i className="fa fa-search-plus" /></button>
            <button data-testid="pantalla-anterior" onClick={() => navegar(-1)}><i className="fa fa-chevron-left" /></button>
            <button data-testid="pantalla-siguiente" onClick={() => navegar(1)}><i className="fa fa-chevron-right" /></button>
          </>}
          {modo === "documento" && carpeta && (
            <button data-testid="pantalla-volver-carpeta" onClick={() => { setModo("carpeta"); narrar(`Volviendo a la carpeta de ${carpeta.nombre}`); }}>
              <i className="fa fa-folder-open" /> Carpeta
            </button>
          )}
          {modo === "correo" && (
            <button className="pantalla-enviar" data-testid="pantalla-enviar-correo" onClick={enviarCorreoActual}>
              <i className="fa fa-paper-plane" /> ENVÍALO
            </button>
          )}
          <button className="pantalla-cerrar" data-testid="pantalla-cerrar" onClick={cerrar}>
            <i className="fa fa-times" /> Cerrar
          </button>
        </div>
      </div>
      {aviso && <div className="pantalla-aviso" data-testid="pantalla-aviso">{aviso}</div>}

      <div className="pantalla-cuerpo">
        {modo === "carpeta" && carpeta && (
          <div className="pantalla-grilla" data-testid="pantalla-grilla">
            {carpeta.archivos.map((a, i) => (
              <button key={i} className="pantalla-doc-card" data-testid={`pantalla-doc-${i}`}
                onClick={() => abrirDocumento(carpeta, a, i)}>
                <i className={`fa ${/\.pdf$/i.test(a.nombre) ? "fa-file-pdf-o" : "fa-file-o"}`} />
                <span className="pantalla-doc-nombre">{a.nombre}</span>
                <span className="pantalla-doc-sub">{a.subfolder || "raíz"}</span>
              </button>
            ))}
            {!carpeta.archivos.length && <p style={{ color: "#888" }}>Carpeta vacía</p>}
          </div>
        )}
        {modo === "documento" && docActual && (
          <div className="pantalla-visor-wrap">
            <iframe title="doc" src={docActual.url} className="pantalla-visor"
              style={{ width: `${zoom}%`, height: zoom > 100 ? `${zoom}%` : "100%" }}
              data-testid="pantalla-visor-doc" />
          </div>
        )}
        {modo === "correo" && correo && (
          <div className="pantalla-correo" data-testid="pantalla-correo">
            <div className="pantalla-correo-meta">
              <div><b>Para:</b> {Array.isArray(correo.to) ? correo.to.join(", ") : correo.to}</div>
              <div><b>Asunto:</b> {correo.subject}</div>
              <div><b>Adjuntos:</b> {(correo.adjuntos || []).map(a => a.filename).join(", ") || "ninguno"}</div>
            </div>
            <iframe title="correo" srcDoc={correo.body_html} className="pantalla-correo-body"
              style={{ transform: `scale(${zoom / 100})`, transformOrigin: "top left", width: `${10000 / zoom}%` }} />
          </div>
        )}
      </div>
    </div>
  );
}
