import { useState, useEffect, useRef, useMemo } from "react";
import { S, GOLD, GOLD_GRAD, PLAYFAIR } from "./theme";
import { hablarMartin } from "../utils/vozMartin";

const CLIENTE = {
  nombre: "Juan Pérez Soto", rut: "12.345.678-9",
  codeudor: "María González López", rutCodeudor: "9.876.543-2",
  direccion: "Av. Providencia 1234, Santiago", rol: "1234-56",
};

const ETAPA1 = [
  ["RUT del titular", "12.345.678-9"], ["Nombre completo", "Juan Pérez Soto"],
  ["Estado civil", "Casado"], ["RUT codeudor", "9.876.543-2"],
  ["Nombre codeudor", "María González López"], ["Correo", "juan.perez@ficticio.cl"],
];
const ETAPA2 = [
  ["Dirección de la propiedad", "Av. Providencia 1234, Santiago"],
  ["Comuna", "Providencia"], ["Región", "Metropolitana"], ["Situación habitacional", "Arrendatario"],
];
const ETAPA3 = [
  ["Rol de avalúo fiscal", "1234-56"], ["Avalúo fiscal", "2.100 UF"],
  ["Valor de tasación", "3.500 UF"], ["M² construidos", "82"], ["Año construcción", "2019"],
];
const ETAPA4 = [
  ["Precio vivienda", "3.500 UF"], ["Crédito solicitado", "2.800 UF"],
  ["Plazo", "25 años"], ["Tasa", "4,3%"], ["Subsidio", "Sin subsidio"], ["Pie / ahorro", "700 UF"],
];
const ETAPA5 = [
  ["Estudio de título — envío abogado", "05/06/2026"], ["Escrituración — envío", "12/06/2026"],
  ["Notaría", "Reveco"], ["Ingreso CBR", "19/06/2026"],
];
const VALIDACIONES = [
  { et: "RUT del cliente vs documentos", a: "12.345.678-9", b: "12.345.678-9" },
  { et: "RUT del codeudor vs documentos", a: "9.876.543-2", b: "9.876.543-2" },
  { et: "Rol de avalúo vs tasación y títulos", a: "1234-56", b: "1234-56" },
  { et: "Dirección vs tasación y títulos", a: "Av. Providencia 1234", b: "Av. Providencia 1234" },
  { et: "Deuda/Garantía (tope 80% de la tasación)", a: "80,0%", b: "tope 80% ✓" },
];

const ESCENAS = [
  ["intro", "Demo Módulo Mutuos — Victoria Vilches · caso completo con datos ficticios", 10],
  ["etapa1", "Etapa 1 — Evaluación del Cliente (autocompletado desde la bóveda)", 11],
  ["etapa2", "Etapa 2 — Registro de la Operación", 10],
  ["etapa3", "Etapa 3 — Tasación (sin tasación no se avanza)", 11],
  ["etapa4", "Etapa 4 — Datos del Crédito y Montos (regla del 80%)", 12],
  ["etapa5", "Etapa 5 — Seguimiento: títulos, escritura, notaría y CBR", 10],
  ["validaciones", "Validaciones irrenunciables — RUT · Rol · Dirección · 80%", 12],
  ["envio", "Etapa 6 — Autorización de Victoria y envío a Revisión de Riesgo", 9],
  ["final", "Proceso completo — resumen", 11],
];
const TOTAL = ESCENAS.reduce((a, e) => a + e[2], 0);

const NARRACION = [
  "Hola, soy Martín. Ahora te muestro el Módulo Mutuos de Victoria Vilches, construido etapa por etapa según su guía de usuario, con un cliente ficticio.",
  "Etapa uno: evaluación del cliente. Los datos del titular y del codeudor llegan autocompletados desde la bóveda. RUT siempre con puntos y guion.",
  "Etapa dos: registro de la operación. Se identifica la propiedad con su dirección, comuna y región.",
  "Etapa tres: la tasación. Rol de avalúo, valor y antecedentes. Sin tasación ingresada, el sistema no permite avanzar hacia operaciones.",
  "Etapa cuatro: datos del crédito. Precio, monto, plazo y tasa. La regla es clara: el crédito no puede superar el ochenta por ciento del valor de tasación.",
  "Etapa cinco: seguimiento de la operación. Estudio de títulos, escrituración, notaría y conservador de bienes raíces, cada hito con su fecha.",
  "Las validaciones irrenunciables: RUT del titular, RUT del codeudor, rol de avalúo, dirección, y la relación deuda garantía. Todo coincide, todo en verde.",
  "Etapa seis: Victoria autoriza cada etapa con su clave y la operación se envía a revisión de riesgo en ConCreces, con correo de aviso automático.",
  "Así opera el Módulo Mutuos de Victoria Vilches: seis etapas guiadas, validación total y cero errores. Listo para revisión de riesgo.",
];

const box = { background: "#141414", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 4, padding: "1.6rem 2rem" };
const fadeIn = (visible, delay = 0) => ({
  opacity: visible ? 1 : 0, transform: visible ? "translateY(0)" : "translateY(14px)",
  transition: `opacity 0.6s ease ${delay}s, transform 0.6s ease ${delay}s`,
});

function Formulario({ campos, prog, testPrefix }) {
  return (
    <div style={{ ...box, maxWidth: 820 }}>
      {campos.map(([et, val], i) => {
        const inicio = 0.08 + i * (0.75 / campos.length);
        const p = Math.min(1, Math.max(0, (prog - inicio) / 0.1));
        const texto = val.slice(0, Math.round(val.length * p));
        return (
          <div key={i} style={{ marginBottom: 13 }}>
            <label style={{ ...S.label, fontSize: "0.72rem" }}>{et}</label>
            <div data-testid={`${testPrefix}-${i}`} style={{ ...S.input, marginTop: 4, minHeight: "1.4em", borderColor: p >= 1 ? "rgba(34,197,94,0.5)" : "rgba(255,255,255,0.15)" }}>
              {texto}<span style={{ opacity: p > 0 && p < 1 ? 1 : 0, color: GOLD }}>▌</span>
              {p >= 1 && <span style={{ color: "#4ade80", float: "right" }}>✓</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function DemoMutuos({ autoPlay = false, onSalir }) {
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(autoPlay);

  useEffect(() => {
    if (!playing) return;
    const iv = setInterval(() => setT(x => Math.min(TOTAL, x + 0.1)), 100);
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

  const habloEscena = useRef(-1);
  useEffect(() => {
    if (!playing) { window.speechSynthesis?.cancel(); return; }
    if (habloEscena.current === idx) return;
    habloEscena.current = idx;
    hablarMartin(NARRACION[idx]);
  }, [idx, playing]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => window.speechSynthesis?.cancel(), []);

  const irA = (i) => { setT(ESCENAS.slice(0, i).reduce((a, e) => a + e[2], 0) + 0.01); };
  const reloj = `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
  const etapasHechas = Math.min(5, Math.max(0, idx - 0));

  return (
    <div data-testid="demo-mutuos" style={{ position: "fixed", inset: 0, zIndex: 200, background: "#0a0a0a", color: "#fff", fontFamily: "Inter, sans-serif", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.9rem 2.5rem", borderBottom: "1px solid rgba(212,175,55,0.35)", flexWrap: "wrap", gap: 10 }}>
        <div>
          <span style={{ fontFamily: PLAYFAIR, fontWeight: 700, fontSize: "1.2rem", letterSpacing: 3, background: GOLD_GRAD, WebkitBackgroundClip: "text", backgroundClip: "text", WebkitTextFillColor: "transparent" }}>CENTRAL MUTUOS</span>
          <span style={{ color: "#a1a1aa", fontSize: "0.75rem", letterSpacing: 2, marginLeft: 14 }}>DEMO MÓDULO MUTUOS · VICTORIA VILCHES · DATOS FICTICIOS</span>
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

      <div style={{ display: "flex", gap: 6, padding: "0.8rem 2.5rem" }}>
        {ESCENAS.map((e, i) => (
          <button key={e[0]} onClick={() => irA(i)} title={e[1]} data-testid={`demo-escena-${i}`}
            style={{ flex: 1, height: 6, borderRadius: 3, border: "none", cursor: "pointer",
              background: i < idx ? GOLD : i === idx ? `linear-gradient(90deg, ${GOLD} ${prog * 100}%, rgba(255,255,255,0.12) ${prog * 100}%)` : "rgba(255,255,255,0.12)" }} />
        ))}
      </div>

      <h1 data-testid="demo-titulo-escena" style={{ fontFamily: PLAYFAIR, fontSize: "1.85rem", fontWeight: 700, margin: "0.4rem 2.5rem 1rem", color: "#FCF6BA" }}>
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
                Crédito: 2.800 UF sobre tasación de 3.500 UF</p>
            </div>
            <div style={{ ...box, ...fadeIn(prog > 0.3, 0.2) }}>
              <div style={S.label}>Las 6 etapas de la Guía de Usuario</div>
              <p style={{ ...S.body, fontSize: "1.05rem", marginTop: 10, lineHeight: 1.9 }}>
                1 · Evaluación del Cliente<br />2 · Registro de la Operación<br />
                3 · Tasación<br />4 · Datos del Crédito y Montos<br />
                5 · Seguimiento de la Operación<br />6 · Validación final y envío a Revisión de Riesgo</p>
            </div>
          </div>
        )}

        {escena === "etapa1" && <Formulario campos={ETAPA1} prog={prog} testPrefix="demo-e1" />}
        {escena === "etapa2" && <Formulario campos={ETAPA2} prog={prog} testPrefix="demo-e2" />}
        {escena === "etapa3" && (
          <div style={{ maxWidth: 820 }}>
            <Formulario campos={ETAPA3} prog={prog} testPrefix="demo-e3" />
            {prog > 0.9 && <div style={{ color: "#facc15", fontWeight: 700, marginTop: 12 }} data-testid="demo-regla-tasacion">
              ⚠ Regla de la Guía: sin los datos de tasación, no se puede avanzar hacia operaciones</div>}
          </div>
        )}
        {escena === "etapa4" && (
          <div style={{ maxWidth: 820 }}>
            <Formulario campos={ETAPA4} prog={prog} testPrefix="demo-e4" />
            {prog > 0.85 && (
              <div style={{ ...box, marginTop: 14, borderColor: "rgba(34,197,94,0.6)" }} data-testid="demo-dg-ok">
                <b style={{ color: "#4ade80", fontSize: "1.1rem" }}>Deuda/Garantía: 2.800 ÷ 3.500 = 80,0% → dentro del tope permitido ✓</b>
              </div>
            )}
          </div>
        )}
        {escena === "etapa5" && <Formulario campos={ETAPA5} prog={prog} testPrefix="demo-e5" />}

        {escena === "validaciones" && (
          <div style={{ maxWidth: 950 }}>
            {VALIDACIONES.map((v, i) => {
              const ok = prog > 0.12 + i * 0.16;
              return (
                <div key={i} data-testid={`demo-val-${i}`} style={{ ...box, marginBottom: 12, display: "flex", gap: 18, alignItems: "center", borderColor: ok ? "rgba(34,197,94,0.6)" : "rgba(255,255,255,0.12)", transition: "border-color 0.5s ease" }}>
                  <span style={{ fontSize: "1.8rem", color: ok ? "#4ade80" : "#71717a" }}>{ok ? "✓" : "⏳"}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 700, fontSize: "1.02rem" }}>{v.et}</div>
                    <div style={{ color: "#a1a1aa", fontSize: "0.9rem", marginTop: 3 }}>
                      Ingresado: <b style={{ color: "#FCF6BA" }}>{v.a}</b> · Documento: <b style={{ color: ok ? "#4ade80" : "#FCF6BA" }}>{v.b}</b></div>
                  </div>
                  {ok && <span style={S.pill("rgba(34,197,94,0.15)", "#4ade80")}>COINCIDE</span>}
                </div>
              );
            })}
            {prog > 0.95 && <div style={{ color: "#4ade80", fontWeight: 800, fontSize: "1.1rem" }} data-testid="demo-val-ok">
              ✓ 5 de 5 validaciones aprobadas — la operación puede continuar</div>}
          </div>
        )}

        {escena === "envio" && (
          <div style={{ maxWidth: 760, textAlign: "center", margin: "2rem auto" }}>
            {prog < 0.45 ? (
              <div>
                <div style={{ ...box, marginBottom: 16, textAlign: "left" }}>
                  <div style={S.label}>Autorización etapa por etapa</div>
                  <p style={{ ...S.body, marginTop: 8 }}>Victoria autoriza las etapas 1 a 5 con su clave. Solo entonces se habilita el envío.</p>
                  <div style={{ marginTop: 10, color: "#4ade80", fontWeight: 700 }}>✓ Etapa 1 · ✓ Etapa 2 · ✓ Etapa 3 · ✓ Etapa 4 · ✓ Etapa 5</div>
                </div>
                <button style={{ ...S.btnGold, fontSize: "1.15rem", padding: "1.2rem 2.4rem", animation: "demoPulso 1s infinite" }}>
                  Enviar operación de Juan Pérez Soto a Revisión de Riesgo</button>
              </div>
            ) : (
              <div style={fadeIn(true)}>
                <div style={{ fontSize: "4.5rem", color: "#4ade80" }}>✓</div>
                <div data-testid="demo-envio-ok" style={{ fontFamily: PLAYFAIR, fontSize: "2.1rem", fontWeight: 700, color: "#4ade80" }}>
                  Enviada a Revisión de Riesgo</div>
                <p style={{ ...S.body, fontSize: "1.1rem", marginTop: 10 }}>
                  Correo de aviso despachado al equipo de riesgo con copia al ejecutivo<br />
                  Estado: <b style={{ color: "#FCF6BA" }}>ENVIADA A REVISIÓN</b></p>
              </div>
            )}
          </div>
        )}

        {escena === "final" && (
          <div style={{ maxWidth: 850, margin: "0 auto", textAlign: "center" }}>
            <div style={{ fontFamily: PLAYFAIR, fontSize: "1.5rem", color: "#a1a1aa" }}>Operación completa en</div>
            <div data-testid="demo-tiempo-total" style={{ fontFamily: PLAYFAIR, fontSize: "4.5rem", fontWeight: 700, background: GOLD_GRAD, WebkitBackgroundClip: "text", backgroundClip: "text", WebkitTextFillColor: "transparent" }}>
              6 etapas guiadas</div>
            <p style={{ ...S.body, fontSize: "1.1rem" }}>de la evaluación del cliente al envío a revisión de riesgo — según la Guía de Usuario Mutuos</p>
            <div style={{ ...box, marginTop: 20, textAlign: "left" }}>
              {[["Etapa 1 — Evaluación del Cliente", "autocompletada desde la bóveda"],
                ["Etapa 2 — Registro de la Operación", "propiedad identificada"],
                ["Etapa 3 — Tasación", "rol 1234-56 · 3.500 UF"],
                ["Etapa 4 — Crédito y Montos", "2.800 UF · D/G 80,0% ✓"],
                ["Etapa 5 — Seguimiento", "títulos · escritura · notaría · CBR"],
                ["Etapa 6 — Envío a Riesgo", "autorizada por Victoria ✓"]].map(([et, tt], i) => (
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
