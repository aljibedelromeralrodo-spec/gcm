import { useState, useEffect, useRef, useMemo } from "react";
import { S, GOLD, GOLD_GRAD, PLAYFAIR } from "./theme";
import { hablarMartin } from "../utils/vozMartin";

const EJECUTIVAS = [
  { nombre: "Yerile Barrera", ini: "YB" },
  { nombre: "Deysi Salazar", ini: "DS" },
];
const SOLICITUDES = [
  { nombre: "Carolina Rojas Fuentes", rut: "15.678.234-5", faltan: "tasación y simulación", a: 0 },
  { nombre: "Andrés Muñoz Leiva", rut: "17.234.567-8", faltan: "estudio de títulos", a: 1 },
  { nombre: "Paula Castro Vidal", rut: "14.890.123-4", faltan: "carpeta de crédito y tasación", a: 0 },
];

const ESCENAS = [
  ["intro", "Demo Módulo Ventas — datos ficticios", 9],
  ["condiciones", "Condición de entrada: documentación incompleta + entrega inmediata", 11],
  ["asignacion", "Asignación automática alternada — Yerile · Deysi · Yerile", 12],
  ["panel", "Panel de la ejecutiva — clientes, faltantes y días en gestión", 12],
  ["gestion", "Ficha del cliente — contactos, estados y carga con validación", 13],
  ["reporte", "Reporte en tiempo real para el Administrador", 11],
  ["final", "Módulo Ventas — cierre", 10],
];
const TOTAL = ESCENAS.reduce((a, e) => a + e[2], 0);

const NARRACION = [
  "Hola, soy Martín. Te presento el Módulo Ventas de Central Mutuos, con las ejecutivas Yerile Barrera y Deysi Salazar.",
  "Cuando llega una solicitud con documentación incompleta y entrega inmediata, califica automáticamente para Ventas.",
  "La asignación es alternada: una solicitud para Yerile, la siguiente para Deysi, y así sucesivamente. Siempre equilibrado.",
  "Cada ejecutiva ve solo sus clientes: qué documentos faltan, cuándo se asignó y el último contacto registrado.",
  "Desde la ficha registra contactos, actualiza el estado y sube documentos, con las mismas validaciones irrenunciables del módulo de Daniela Galindo.",
  "El administrador ve el reporte completo en tiempo real: clientes por ejecutiva, estados, faltantes y días en gestión.",
  "Documentación completa y cliente listo para avanzar. Así trabaja el Módulo Ventas de Central Mutuos.",
];

const box = { background: "#141414", border: "1px solid rgba(255,255,255,0.12)", borderRadius: 4, padding: "1.6rem 2rem" };
const fadeIn = (visible, delay = 0) => ({
  opacity: visible ? 1 : 0, transform: visible ? "translateY(0)" : "translateY(14px)",
  transition: `opacity 0.6s ease ${delay}s, transform 0.6s ease ${delay}s`,
});

export default function DemoVentas({ autoPlay = false, onSalir }) {
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

  const irA = (i) => setT(ESCENAS.slice(0, i).reduce((a, e) => a + e[2], 0) + 0.01);
  const reloj = `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;

  return (
    <div data-testid="demo-ventas" style={{ position: "fixed", inset: 0, zIndex: 200, background: "#0a0a0a", color: "#fff", fontFamily: "Inter, sans-serif", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.9rem 2.5rem", borderBottom: "1px solid rgba(212,175,55,0.35)", flexWrap: "wrap", gap: 10 }}>
        <div>
          <span style={{ fontFamily: PLAYFAIR, fontWeight: 700, fontSize: "1.2rem", letterSpacing: 3, background: GOLD_GRAD, WebkitBackgroundClip: "text", backgroundClip: "text", WebkitTextFillColor: "transparent" }}>CENTRAL MUTUOS</span>
          <span style={{ color: "#a1a1aa", fontSize: "0.75rem", letterSpacing: 2, marginLeft: 14 }}>DEMO MÓDULO VENTAS · DATOS FICTICIOS</span>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <span data-testid="demo-ventas-reloj" style={{ fontFamily: "monospace", fontSize: "1.05rem", color: "#FCF6BA" }}>⏱ {reloj}</span>
          {!playing ? (
            <button data-testid="demo-ventas-reproducir" onClick={() => { if (t >= TOTAL) setT(0); setPlaying(true); }}
              style={{ ...S.btnGold, ...S.btnSmall }}>▶ {t > 0 && t < TOTAL ? "Continuar la demo" : "Reproducir la demo completa"}</button>
          ) : (
            <button data-testid="demo-ventas-pausar" onClick={() => setPlaying(false)} style={{ ...S.btnLine, ...S.btnSmall }}>⏸ Pausar la demo</button>
          )}
          <button data-testid="demo-ventas-reiniciar" onClick={() => { setT(0); setPlaying(true); }} style={{ ...S.btnLine, ...S.btnSmall }}>⟲ Reiniciar</button>
          {onSalir && <button data-testid="demo-ventas-salir" onClick={onSalir} style={{ ...S.btnDanger, ...S.btnSmall }}>✕ Cerrar la demo</button>}
        </div>
      </div>

      <div style={{ display: "flex", gap: 6, padding: "0.8rem 2.5rem" }}>
        {ESCENAS.map((e, i) => (
          <button key={e[0]} onClick={() => irA(i)} title={e[1]}
            style={{ flex: 1, height: 6, borderRadius: 3, border: "none", cursor: "pointer",
              background: i < idx ? GOLD : i === idx ? `linear-gradient(90deg, ${GOLD} ${prog * 100}%, rgba(255,255,255,0.12) ${prog * 100}%)` : "rgba(255,255,255,0.12)" }} />
        ))}
      </div>

      <h1 data-testid="demo-ventas-titulo" style={{ fontFamily: PLAYFAIR, fontSize: "1.9rem", fontWeight: 700, margin: "0.4rem 2.5rem 1rem", color: "#FCF6BA" }}>
        {ESCENAS[idx][1]}</h1>

      <div style={{ flex: 1, overflow: "auto", padding: "0 2.5rem 2rem" }}>
        {escena === "intro" && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, maxWidth: 1000 }}>
            {EJECUTIVAS.map((e, i) => (
              <div key={i} style={{ ...box, textAlign: "center", ...fadeIn(prog > 0.1 + i * 0.2) }}>
                <div style={{ width: 90, height: 90, borderRadius: "50%", margin: "0 auto", background: GOLD_GRAD, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: PLAYFAIR, fontSize: "2rem", fontWeight: 700, color: "#0a0a0a" }}>{e.ini}</div>
                <div style={{ fontFamily: PLAYFAIR, fontSize: "1.6rem", fontWeight: 700, marginTop: 14 }}>{e.nombre}</div>
                <div style={{ color: "#a1a1aa", marginTop: 6 }}>Ejecutiva de Ventas · panel independiente</div>
              </div>
            ))}
          </div>
        )}

        {escena === "condiciones" && (
          <div style={{ maxWidth: 900 }}>
            <div style={{ ...box, ...fadeIn(prog > 0.05) }}>
              <div style={{ fontSize: "1.15rem", fontWeight: 700 }}>Solicitud entrante: {SOLICITUDES[0].nombre} — RUT {SOLICITUDES[0].rut}</div>
              <div style={{ display: "flex", gap: 14, marginTop: 16, flexWrap: "wrap" }}>
                <span style={{ ...S.pill(prog > 0.3 ? "rgba(245,158,11,0.15)" : "rgba(255,255,255,0.08)", prog > 0.3 ? "#f59e0b" : "#71717a"), fontSize: "1rem", padding: "0.5rem 1.2rem" }}>
                  {prog > 0.3 ? "✓" : "…"} Documentación incompleta (faltan {SOLICITUDES[0].faltan})</span>
                <span style={{ ...S.pill(prog > 0.55 ? "rgba(212,175,55,0.18)" : "rgba(255,255,255,0.08)", prog > 0.55 ? "#FCF6BA" : "#71717a"), fontSize: "1rem", padding: "0.5rem 1.2rem" }}>
                  {prog > 0.55 ? "✓" : "…"} Entrega inmediata</span>
              </div>
              {prog > 0.8 && <div data-testid="demo-ventas-califica" style={{ color: "#4ade80", fontWeight: 800, fontSize: "1.2rem", marginTop: 18 }}>
                → CALIFICA PARA EL MÓDULO VENTAS. Si el set estuviera completo o no fuera entrega inmediata, seguiría el flujo normal.</div>}
            </div>
          </div>
        )}

        {escena === "asignacion" && (
          <div style={{ maxWidth: 1000 }}>
            {SOLICITUDES.map((s, i) => {
              const ok = prog > 0.2 + i * 0.25;
              return (
                <div key={i} style={{ ...box, marginBottom: 14, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 14, ...fadeIn(prog > 0.05 + i * 0.15) }}>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: "1.05rem" }}>Solicitud {i + 1}: {s.nombre}</div>
                    <div style={{ color: "#a1a1aa", fontSize: "0.9rem" }}>Incompleta (faltan {s.faltan}) + entrega inmediata</div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <span style={{ fontSize: "1.6rem", color: ok ? GOLD : "#3f3f46", transition: "color 0.4s" }}>→</span>
                    <span style={{ ...S.pill(ok ? "rgba(212,175,55,0.18)" : "rgba(255,255,255,0.06)", ok ? "#FCF6BA" : "#52525b"), fontSize: "1rem", padding: "0.5rem 1.2rem" }}>
                      {EJECUTIVAS[s.a].nombre}</span>
                  </div>
                </div>
              );
            })}
            {prog > 0.92 && <div style={{ color: "#4ade80", fontWeight: 800, fontSize: "1.05rem" }}>✓ Turno alternado automático: nadie queda sobrecargado</div>}
          </div>
        )}

        {escena === "panel" && (
          <div style={{ ...box, maxWidth: 1000, ...fadeIn(prog > 0.05) }}>
            <div style={S.label}>Panel de Yerile Barrera — solo sus clientes</div>
            {[SOLICITUDES[0], SOLICITUDES[2]].map((s, i) => {
              const ok = prog > 0.25 + i * 0.3;
              return (
                <div key={i} style={{ borderTop: "1px solid rgba(255,255,255,0.08)", padding: "1rem 0", ...fadeIn(ok) }}>
                  <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                    <span style={{ fontFamily: PLAYFAIR, fontSize: "1.2rem", fontWeight: 700 }}>{s.nombre}</span>
                    <span style={S.pill("rgba(245,158,11,0.15)", "#f59e0b")}>FALTAN: {s.faltan.toUpperCase()}</span>
                  </div>
                  <div style={{ color: "#a1a1aa", fontSize: "0.92rem", marginTop: 5 }}>
                    Asignado hoy · 0 días en gestión · último contacto: llamada hace 2 horas</div>
                </div>
              );
            })}
          </div>
        )}

        {escena === "gestion" && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 22, maxWidth: 1100 }}>
            <div style={{ ...box, ...fadeIn(prog > 0.05) }}>
              <div style={S.label}>Registro de contacto</div>
              <div style={{ ...S.input, marginTop: 10 }}>llamada · "Cliente enviará la tasación mañana"</div>
              {prog > 0.3 && <div style={{ color: "#4ade80", fontWeight: 700, marginTop: 10 }}>✓ Contacto registrado en el historial</div>}
              <div style={{ ...S.label, marginTop: 18 }}>Actualización de estado</div>
              <div style={{ ...S.input, marginTop: 10, color: "#FCF6BA" }}>Esperando documentos</div>
            </div>
            <div style={{ ...box, ...fadeIn(prog > 0.4) }}>
              <div style={S.label}>Carga de documento con validación irrenunciable</div>
              <div style={{ fontSize: "0.95rem", marginTop: 10 }}>tasacion_carolina_rojas.pdf</div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
                {["RUT cliente", "RUT codeudor", "Rol avalúo", "Dirección"].map((et, i) => {
                  const ok = prog > 0.55 + i * 0.09;
                  return <span key={i} style={S.pill(ok ? "rgba(34,197,94,0.15)" : "rgba(255,255,255,0.07)", ok ? "#4ade80" : "#71717a")}>{ok ? "✓" : "…"} {et}</span>;
                })}
              </div>
              {prog > 0.93 && <div style={{ color: "#4ade80", fontWeight: 800, marginTop: 14 }}>✓ Documento validado y guardado en la bóveda del cliente</div>}
            </div>
          </div>
        )}

        {escena === "reporte" && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 22, maxWidth: 1100 }}>
            {EJECUTIVAS.map((e, i) => (
              <div key={i} style={{ ...box, ...fadeIn(prog > 0.1 + i * 0.25) }}>
                <div style={{ fontFamily: PLAYFAIR, fontSize: "1.3rem", fontWeight: 700 }}>{e.nombre}</div>
                <div style={{ display: "flex", gap: 18, marginTop: 12, flexWrap: "wrap" }}>
                  <div><div style={{ ...S.kpiValue, fontSize: "2.2rem" }}>{i === 0 ? 2 : 1}</div><div style={S.label}>clientes</div></div>
                  <div><div style={{ ...S.kpiValue, fontSize: "2.2rem", color: "#f59e0b" }}>{i === 0 ? 3 : 1}</div><div style={S.label}>docs faltantes</div></div>
                  <div><div style={{ ...S.kpiValue, fontSize: "2.2rem", color: "#FCF6BA" }}>{i === 0 ? 2 : 4}</div><div style={S.label}>días en gestión</div></div>
                </div>
              </div>
            ))}
            {prog > 0.7 && <div style={{ gridColumn: "1 / -1", color: "#FCF6BA", fontWeight: 700, fontSize: "1.05rem" }}>
              El administrador es el único con visión transversal: los módulos no mezclan información entre sí (Regla de Oro de arquitectura).</div>}
          </div>
        )}

        {escena === "final" && (
          <div style={{ maxWidth: 800, margin: "2rem auto", textAlign: "center" }}>
            <div style={{ fontSize: "4rem", color: "#4ade80" }}>✓</div>
            <div data-testid="demo-ventas-total" style={{ fontFamily: PLAYFAIR, fontSize: "2.4rem", fontWeight: 700, background: GOLD_GRAD, WebkitBackgroundClip: "text", backgroundClip: "text", WebkitTextFillColor: "transparent" }}>
              Módulo Ventas operativo</div>
            <p style={{ ...S.body, fontSize: "1.15rem", marginTop: 12 }}>
              Asignación alternada automática · gestión independiente por ejecutiva ·<br />
              validaciones irrenunciables · reporte transversal solo para el administrador</p>
          </div>
        )}
      </div>
    </div>
  );
}
