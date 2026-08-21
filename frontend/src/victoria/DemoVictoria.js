import { useState, useEffect, useRef, useMemo } from "react";
import { S, GOLD, GOLD_GRAD, PLAYFAIR } from "./theme";

const CLIENTE = {
  nombre: "Juan Pérez Soto", rut: "12.345.678-9",
  codeudor: "María González López", rutCodeudor: "9.876.543-2",
  direccion: "Av. Providencia 1234, Santiago", rol: "1234-56",
  valor: "3.500 UF", subsidio: "Sin subsidio",
};

const DOCS = [
  { icono: "fa-home", nombre: "tasacion_juan_perez.pdf", tipo: "Informe de Tasación", t: "1,2 s" },
  { icono: "fa-file-text", nombre: "estudio_titulos_providencia.pdf", tipo: "Estudio de Títulos", t: "1,4 s" },
  { icono: "fa-folder-open", nombre: "carpeta_credito_jperez.pdf", tipo: "Carpeta de Crédito", t: "0,9 s" },
  { icono: "fa-calculator", nombre: "simulacion_3500uf.pdf", tipo: "Simulación", t: "0,8 s" },
];

const VALIDACIONES = [
  { et: "RUT cliente principal", ficha: "12.345.678-9", doc: "12.345.678-9" },
  { et: "RUT codeudor", ficha: "9.876.543-2", doc: "9.876.543-2" },
  { et: "Rol de avalúo fiscal", ficha: "1234-56", doc: "1234-56 (tasación y títulos)" },
  { et: "Dirección propiedad", ficha: "Av. Providencia 1234, Santiago", doc: "Av. Providencia 1234, Santiago" },
];

const CAMPOS = [
  ["Nombre del cliente", "Juan Pérez Soto"],
  ["RUT titular", "12.345.678-9"],
  ["RUT codeudor", "9.876.543-2"],
  ["Rol de avalúo", "1234-56"],
  ["Dirección propiedad", "Av. Providencia 1234, Santiago"],
  ["Valor operación", "3.500 UF · Sin subsidio"],
];

const CHECKLIST = [
  "Set de crédito completo: 4 de 4 documentos requeridos en la bóveda",
  "Reglas de Oro 11-14: las 4 validaciones cruzadas coinciden",
  "Sin alertas críticas de auditoría ni documentos vencidos",
  "Formularios revisados y confirmados por Victoria",
];

// Escenas: [clave, título, duración en segundos]
const ESCENAS = [
  ["intro", "Demo Módulo Victoria — caso completo con datos ficticios", 10],
  ["deteccion", "Paso 1 — Detección automática del correo", 10],
  ["clasificacion", "Paso 2 — Clasificación de documentos por tipo", 10],
  ["validacion", "Paso 3 — Validación irrenunciable RUT · Rol · Dirección", 13],
  ["preview", "Paso 4 — Preview de documentos antes de aceptar", 11],
  ["formularios", "Paso 5 — Autocompletado de formularios", 12],
  ["revision", "Paso 6 — Revisión final con checklist completo", 9],
  ["envio", "Paso 7 — Envío a ConCreces con confirmación", 9],
  ["final", "Proceso completo — resumen de tiempos", 12],
];
const TOTAL = ESCENAS.reduce((a, e) => a + e[2], 0);

// Narración de Martín, sincronizada por escena
const NARRACION = [
  "Hola, soy Martín, el asistente de Central Mutuos ConCreces. Te voy a mostrar cómo funciona el módulo de Victoria paso a paso.",
  "Paso uno: llega un correo con el set de crédito. El sistema lo detecta y descarga los adjuntos automáticamente en segundos.",
  "Paso dos: cada documento se lee y se clasifica por tipo: tasación, estudio de títulos, carpeta de crédito y simulación.",
  "Paso tres: la validación irrenunciable. RUT con RUT, codeudor con codeudor, rol de avalúo y dirección. Todo debe coincidir exactamente.",
  "Paso cuatro: Victoria revisa cada documento en pantalla, sin descargarlo, y lo acepta o rechaza con un clic.",
  "Paso cinco: los formularios se completan solos con los datos extraídos. Cero digitación y cero errores.",
  "Paso seis: revisión final. El checklist completo queda aprobado en verde.",
  "Paso siete: Victoria confirma y el set viaja a ConCreces con un solo clic.",
  "Así de simple y rápido opera el módulo de Victoria. Todo validado, todo en orden, listo para ConCreces.",
];

const box = { background: "#141414", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 4, padding: "1.6rem 2rem" };
const fadeIn = (visible, delay = 0) => ({
  opacity: visible ? 1 : 0, transform: visible ? "translateY(0)" : "translateY(14px)",
  transition: `opacity 0.6s ease ${delay}s, transform 0.6s ease ${delay}s`,
});

export default function DemoVictoria({ autoPlay = false, onSalir }) {
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(autoPlay);
  const raf = useRef(null);

  useEffect(() => {
    if (!playing) return;
    const iv = setInterval(() => setT(x => Math.min(TOTAL, x + 0.1)), 100);
    raf.current = iv;
    return () => clearInterval(iv);
  }, [playing]);
  useEffect(() => { if (t >= TOTAL) setPlaying(false); }, [t]);

  const { escena, prog, idx } = useMemo(() => {
    let acc = 0;
    for (let i = 0; i < ESCENAS.length; i++) {
      const [k, , d] = ESCENAS[i];
      if (t < acc + d || i === ESCENAS.length - 1)
        return { escena: k, prog: Math.min(1, Math.max(0, (t - acc) / d)), idx: i };
      acc += d;
    }
    return { escena: "final", prog: 1, idx: ESCENAS.length - 1 };
  }, [t]);

  // Voz de Martín (Web Speech API): narra cada escena sincronizada
  const habloEscena = useRef(-1);
  useEffect(() => {
    if (!playing) { window.speechSynthesis?.cancel(); return; }
    if (habloEscena.current === idx) return;
    habloEscena.current = idx;
    try {
      const synth = window.speechSynthesis;
      if (!synth) return;
      synth.cancel();
      const u = new SpeechSynthesisUtterance(NARRACION[idx]);
      u.lang = "es-CL";
      const voces = synth.getVoices();
      const voz = voces.find(v => v.lang.startsWith("es") && /male|jorge|diego|carlos|raul|juan/i.test(v.name))
        || voces.find(v => v.lang.startsWith("es"));
      if (voz) u.voice = voz;
      u.rate = 1.02;
      u.pitch = 0.9;
      synth.speak(u);
    } catch {}
  }, [idx, playing]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => window.speechSynthesis?.cancel(), []);

  const irA = (i) => { setT(ESCENAS.slice(0, i).reduce((a, e) => a + e[2], 0) + 0.01); };
  const reloj = `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;

  return (
    <div data-testid="demo-victoria" style={{ position: "fixed", inset: 0, zIndex: 200, background: "#0a0a0a", color: "#fff", fontFamily: "Inter, sans-serif", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      {/* Barra superior */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.9rem 2.5rem", borderBottom: "1px solid rgba(212,175,55,0.35)", flexWrap: "wrap", gap: 10 }}>
        <div>
          <span style={{ fontFamily: PLAYFAIR, fontWeight: 700, fontSize: "1.2rem", letterSpacing: 3, background: GOLD_GRAD, WebkitBackgroundClip: "text", backgroundClip: "text", WebkitTextFillColor: "transparent" }}>CENTRAL MUTUOS</span>
          <span style={{ color: "#a1a1aa", fontSize: "0.75rem", letterSpacing: 2, marginLeft: 14 }}>DEMO MÓDULO VICTORIA · DATOS FICTICIOS</span>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <span data-testid="demo-reloj" style={{ fontFamily: "monospace", fontSize: "1.05rem", color: "#FCF6BA" }}>⏱ {reloj}</span>
          {!playing ? (
            <button data-testid="demo-btn-reproducir" onClick={() => { if (t >= TOTAL) setT(0); setPlaying(true); }}
              style={{ ...S.btnGold, ...S.btnSmall }}>▶ {t > 0 && t < TOTAL ? "Continuar la demo" : "Reproducir la demo completa"}</button>
          ) : (
            <button data-testid="demo-btn-pausar" onClick={() => setPlaying(false)} style={{ ...S.btnLine, ...S.btnSmall }}>⏸ Pausar la demo</button>
          )}
          <button data-testid="demo-btn-reiniciar" onClick={() => { setT(0); setPlaying(true); }} style={{ ...S.btnLine, ...S.btnSmall }}>⟲ Reiniciar desde el inicio</button>
          {onSalir && <button data-testid="demo-btn-salir" onClick={onSalir} style={{ ...S.btnDanger, ...S.btnSmall }}>✕ Cerrar la demo</button>}
        </div>
      </div>

      {/* Progreso de escenas */}
      <div style={{ display: "flex", gap: 6, padding: "0.8rem 2.5rem" }}>
        {ESCENAS.map((e, i) => (
          <button key={e[0]} onClick={() => irA(i)} title={e[1]} data-testid={`demo-escena-${i}`}
            style={{ flex: 1, height: 6, borderRadius: 3, border: "none", cursor: "pointer",
              background: i < idx ? GOLD : i === idx ? `linear-gradient(90deg, ${GOLD} ${prog * 100}%, rgba(255,255,255,0.12) ${prog * 100}%)` : "rgba(255,255,255,0.12)" }} />
        ))}
      </div>

      <h1 data-testid="demo-titulo-escena" style={{ fontFamily: PLAYFAIR, fontSize: "1.9rem", fontWeight: 700, margin: "0.4rem 2.5rem 1rem", color: "#FCF6BA" }}>
        {ESCENAS[idx][1]}</h1>

      <div style={{ flex: 1, overflow: "auto", padding: "0 2.5rem 2rem" }}>
        {escena === "intro" && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, maxWidth: 1100 }}>
            <div style={{ ...box, ...fadeIn(prog > 0.05) }}>
              <div style={S.label}>Cliente ficticio del caso</div>
              <div style={{ fontFamily: PLAYFAIR, fontSize: "2.1rem", fontWeight: 700, marginTop: 8 }}>{CLIENTE.nombre}</div>
              <p style={{ ...S.body, fontSize: "1.05rem", marginTop: 10 }}>
                RUT {CLIENTE.rut}<br />Codeudora: {CLIENTE.codeudor} · RUT {CLIENTE.rutCodeudor}<br />
                Propiedad: {CLIENTE.direccion}<br />Rol de avalúo: {CLIENTE.rol}<br />
                Valor: {CLIENTE.valor} · {CLIENTE.subsidio}</p>
            </div>
            <div style={{ ...box, ...fadeIn(prog > 0.3, 0.2) }}>
              <div style={S.label}>Lo que verá en esta demo</div>
              <p style={{ ...S.body, fontSize: "1.05rem", marginTop: 10, lineHeight: 1.9 }}>
                1 · Detección automática del correo<br />2 · Clasificación de documentos<br />
                3 · Validación irrenunciable (Regla de Oro 15)<br />4 · Preview antes de aceptar<br />
                5 · Formularios que se llenan solos<br />6 · Checklist final en verde<br />
                7 · Envío a ConCreces con un clic</p>
            </div>
          </div>
        )}

        {escena === "deteccion" && (
          <div style={{ maxWidth: 900 }}>
            <div style={{ ...box, ...fadeIn(prog > 0.05), display: "flex", gap: 20, alignItems: "center" }}>
              <i className="fa fa-envelope" style={{ fontSize: "3rem", color: GOLD, animation: prog < 0.35 ? "demoPulso 0.8s infinite" : "none" }}></i>
              <div>
                <div style={{ fontSize: "1.15rem", fontWeight: 700 }}>Correo entrante detectado en la casilla monitoreada</div>
                <div style={{ color: "#a1a1aa", marginTop: 4 }}>De: ejecutivo@brokerficticio.cl · Asunto: "Set de crédito Juan Pérez Soto — 3.500 UF"</div>
                {prog > 0.25 && <div data-testid="demo-tiempo-deteccion" style={{ color: "#4ade80", fontWeight: 700, marginTop: 6 }}>✓ Detectado automáticamente en 2,4 segundos</div>}
              </div>
            </div>
            <div style={{ ...box, marginTop: 20, ...fadeIn(prog > 0.35) }}>
              <div style={S.label}>Descargando adjuntos a la bóveda</div>
              {DOCS.map((d, i) => {
                const p = Math.min(1, Math.max(0, (prog - 0.4 - i * 0.12) / 0.15));
                return (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: 14, marginTop: 12 }}>
                    <i className={`fa ${d.icono}`} style={{ color: GOLD, width: 22 }}></i>
                    <span style={{ flex: "0 0 320px", fontSize: "0.98rem" }}>{d.nombre}</span>
                    <div style={{ flex: 1, height: 8, background: "rgba(255,255,255,0.1)", borderRadius: 4 }}>
                      <div style={{ width: `${p * 100}%`, height: "100%", background: GOLD_GRAD, borderRadius: 4, transition: "width 0.2s linear" }} />
                    </div>
                    <span style={{ color: p >= 1 ? "#4ade80" : "#71717a", fontWeight: 700, width: 90 }}>{p >= 1 ? `✓ ${d.t}` : "…"}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {escena === "clasificacion" && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 20, maxWidth: 1100 }}>
            {DOCS.map((d, i) => {
              const listo = prog > 0.15 + i * 0.18;
              return (
                <div key={i} style={{ ...box, ...fadeIn(prog > 0.03 + i * 0.05), display: "flex", justifyContent: "space-between", alignItems: "center", gap: 14 }}>
                  <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
                    <i className={`fa ${d.icono}`} style={{ fontSize: "1.8rem", color: GOLD }}></i>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: "1rem" }}>{d.nombre}</div>
                      <div style={{ color: "#a1a1aa", fontSize: "0.85rem" }}>Leyendo contenido con OCR e IA…</div>
                    </div>
                  </div>
                  <span style={{ ...S.pill(listo ? "rgba(34,197,94,0.15)" : "rgba(255,255,255,0.08)", listo ? "#4ade80" : "#71717a"), transition: "all 0.4s ease" }}>
                    {listo ? `✓ ${d.tipo}` : "clasificando…"}</span>
                </div>
              );
            })}
            {prog > 0.9 && <div style={{ gridColumn: "1 / -1", color: "#4ade80", fontWeight: 700, fontSize: "1.05rem" }} data-testid="demo-clasificacion-ok">
              ✓ 4 documentos clasificados y etiquetados automáticamente en 4,3 segundos</div>}
          </div>
        )}

        {escena === "validacion" && (
          <div style={{ maxWidth: 950 }}>
            <p style={{ ...S.body, marginBottom: 16 }}>Regla de Oro 15 — irrenunciable: ningún documento se asocia si un dato no coincide exactamente con la ficha.</p>
            {VALIDACIONES.map((v, i) => {
              const ok = prog > 0.15 + i * 0.2;
              return (
                <div key={i} data-testid={`demo-validacion-${i}`} style={{ ...box, marginBottom: 14, display: "flex", gap: 18, alignItems: "center", borderColor: ok ? "rgba(34,197,94,0.6)" : "rgba(255,255,255,0.12)", transition: "border-color 0.5s ease" }}>
                  <span style={{ fontSize: "1.9rem", color: ok ? "#4ade80" : "#71717a", transition: "color 0.4s ease" }}>{ok ? "✓" : "⏳"}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 700, fontSize: "1.05rem" }}>{v.et}</div>
                    <div style={{ color: "#a1a1aa", fontSize: "0.92rem", marginTop: 3 }}>
                      Ficha: <b style={{ color: "#FCF6BA" }}>{v.ficha}</b> · Documento: <b style={{ color: ok ? "#4ade80" : "#FCF6BA" }}>{v.doc}</b></div>
                  </div>
                  {ok && <span style={S.pill("rgba(34,197,94,0.15)", "#4ade80")}>COINCIDE EXACTAMENTE</span>}
                </div>
              );
            })}
            {prog > 0.95 && <div style={{ color: "#4ade80", fontWeight: 800, fontSize: "1.1rem" }} data-testid="demo-validacion-ok">
              ✓ Las 4 validaciones aprobadas: los documentos se asocian a la bóveda de Juan Pérez Soto</div>}
          </div>
        )}

        {escena === "preview" && (
          <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 24, maxWidth: 1150 }}>
            <div style={{ background: "#f5f2e9", borderRadius: 4, padding: "2rem", color: "#1a1a1a", fontFamily: "Georgia, serif", ...fadeIn(prog > 0.05) }}>
              <div style={{ borderBottom: "3px solid #8a6d1a", paddingBottom: 10, marginBottom: 14 }}>
                <b style={{ fontSize: "1.2rem" }}>INFORME DE TASACIÓN</b><br />
                <span style={{ color: "#555" }}>Tasaciones Ficticias SpA · Folio DEMO-001</span>
              </div>
              <p style={{ lineHeight: 2 }}>
                <b>Solicitante:</b> Juan Pérez Soto — RUT 12.345.678-9<br />
                <b>Codeudora:</b> María González López — RUT 9.876.543-2<br />
                <b>Propiedad:</b> Av. Providencia 1234, Santiago<br />
                <b>Rol de avalúo fiscal:</b> 1234-56<br />
                <b>Valor de tasación:</b> 3.500 UF</p>
              <p style={{ color: "#777", fontSize: "0.85rem", marginTop: 16 }}>Documento ficticio generado solo para esta demo.</p>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 14, ...fadeIn(prog > 0.3) }}>
              <div style={box}>
                <div style={S.label}>Victoria revisa sin descargar</div>
                <p style={{ ...S.body, marginTop: 8 }}>El documento se ve al instante en pantalla. Victoria decide con un clic:</p>
              </div>
              <button style={{ ...S.btnGold, transform: prog > 0.7 ? "scale(0.97)" : "scale(1)", transition: "transform 0.2s ease" }}>
                ✓ Aceptar documento como válido</button>
              <button style={S.btnDanger}>✕ Rechazar documento y solicitar reemplazo</button>
              {prog > 0.75 && <div data-testid="demo-preview-aceptado" style={{ color: "#4ade80", fontWeight: 800, fontSize: "1.05rem" }}>
                ✓ Los 4 documentos aceptados por Victoria (12,8 s de revisión)</div>}
            </div>
          </div>
        )}

        {escena === "formularios" && (
          <div style={{ maxWidth: 800 }}>
            <p style={{ ...S.body, marginBottom: 16 }}>El sistema rellena solo cada campo con lo extraído de los documentos: Victoria no digita nada.</p>
            <div style={box}>
              {CAMPOS.map(([et, val], i) => {
                const inicio = 0.08 + i * 0.14;
                const p = Math.min(1, Math.max(0, (prog - inicio) / 0.12));
                const texto = val.slice(0, Math.round(val.length * p));
                return (
                  <div key={i} style={{ marginBottom: 14 }}>
                    <label style={{ ...S.label, fontSize: "0.72rem" }}>{et}</label>
                    <div data-testid={`demo-campo-${i}`} style={{ ...S.input, marginTop: 4, minHeight: "1.4em", borderColor: p >= 1 ? "rgba(34,197,94,0.5)" : "rgba(255,255,255,0.15)" }}>
                      {texto}<span style={{ opacity: p > 0 && p < 1 ? 1 : 0, color: GOLD }}>▌</span>
                      {p >= 1 && <span style={{ color: "#4ade80", float: "right" }}>✓</span>}
                    </div>
                  </div>
                );
              })}
            </div>
            {prog > 0.95 && <div style={{ color: "#4ade80", fontWeight: 800, marginTop: 12, fontSize: "1.05rem" }} data-testid="demo-formularios-ok">
              ✓ 6 campos autocompletados en 3,1 segundos — 0 errores de digitación</div>}
          </div>
        )}

        {escena === "revision" && (
          <div style={{ maxWidth: 850 }}>
            {CHECKLIST.map((c, i) => {
              const ok = prog > 0.12 + i * 0.18;
              return (
                <div key={i} data-testid={`demo-check-${i}`} style={{ ...box, marginBottom: 12, display: "flex", gap: 16, alignItems: "center", borderColor: ok ? "rgba(34,197,94,0.6)" : "rgba(255,255,255,0.12)", transition: "border-color 0.5s ease" }}>
                  <span style={{ fontSize: "1.7rem", color: ok ? "#4ade80" : "#71717a" }}>{ok ? "✓" : "○"}</span>
                  <span style={{ ...S.body, fontSize: "1.05rem", color: ok ? "#fff" : "#71717a" }}>{c}</span>
                </div>
              );
            })}
            {prog > 0.9 && <div style={{ color: "#4ade80", fontWeight: 800, fontSize: "1.15rem" }} data-testid="demo-checklist-ok">
              ✓ Checklist completo: la operación de Juan Pérez Soto está LISTA PARA ENVÍO</div>}
          </div>
        )}

        {escena === "envio" && (
          <div style={{ maxWidth: 760, textAlign: "center", margin: "2rem auto" }}>
            {prog < 0.45 ? (
              <button style={{ ...S.btnGold, fontSize: "1.2rem", padding: "1.3rem 2.5rem", animation: "demoPulso 1s infinite" }}>
                Confirmar envío del set de crédito de Juan Pérez Soto a ConCreces</button>
            ) : (
              <div style={fadeIn(true)}>
                <div style={{ fontSize: "4.5rem", color: "#4ade80" }}>✓</div>
                <div data-testid="demo-envio-ok" style={{ fontFamily: PLAYFAIR, fontSize: "2.2rem", fontWeight: 700, color: "#4ade80" }}>
                  Set enviado a ConCreces</div>
                <p style={{ ...S.body, fontSize: "1.1rem", marginTop: 10 }}>
                  4 documentos validados · confirmación registrada con nombre, fecha y hora<br />
                  Estado en ConCreces: <b style={{ color: "#FCF6BA" }}>RECIBIDO</b></p>
              </div>
            )}
          </div>
        )}

        {escena === "final" && (
          <div style={{ maxWidth: 850, margin: "0 auto", textAlign: "center" }}>
            <div style={{ fontFamily: PLAYFAIR, fontSize: "1.5rem", color: "#a1a1aa" }}>Tiempo total del proceso completo</div>
            <div data-testid="demo-tiempo-total" style={{ fontFamily: PLAYFAIR, fontSize: "4.5rem", fontWeight: 700, background: GOLD_GRAD, WebkitBackgroundClip: "text", backgroundClip: "text", WebkitTextFillColor: "transparent" }}>
              58,3 segundos</div>
            <p style={{ ...S.body, fontSize: "1.1rem" }}>del correo entrante al envío confirmado en ConCreces — sin digitación manual</p>
            <div style={{ ...box, marginTop: 20, textAlign: "left" }}>
              {[["Detección y descarga automática", "2,4 s"], ["Clasificación de 4 documentos", "4,3 s"],
                ["Validación irrenunciable (4 contrastes)", "3,7 s"], ["Preview y aceptación por Victoria", "12,8 s"],
                ["Autocompletado de formularios", "3,1 s"], ["Revisión final con checklist", "18,0 s"],
                ["Confirmación y envío a ConCreces", "14,0 s"]].map(([et, tt], i) => (
                <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "0.55rem 0", borderTop: i ? "1px solid rgba(255,255,255,0.08)" : "none" }}>
                  <span style={S.body}>{et}</span><b style={{ color: "#FCF6BA" }}>{tt}</b>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
      <style>{`@keyframes demoPulso { 0%,100% { opacity: 1 } 50% { opacity: 0.55 } }`}</style>
    </div>
  );
}
