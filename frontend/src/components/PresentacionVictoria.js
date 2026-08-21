import { useState, useEffect, useCallback } from "react";

const ORO = "#d4af37";
const PASOS = [
  {
    icono: "fa-envelope-open-o", titulo: "Detección automática desde el correo",
    sistema: "El sistema monitorea el correo de Victoria, detecta los sets de crédito, descarga los adjuntos y los clasifica solo: tasación, títulos, carpeta de crédito, simulación.",
    manual: "Revisar el correo, descargar archivo por archivo, renombrarlos y ordenarlos en carpetas.",
    minManual: 25,
  },
  {
    icono: "fa-search", titulo: "Auditoría automática del set",
    sistema: "Verifica que estén todos los documentos requeridos, que las fechas estén vigentes, que las firmas estén presentes y que el formato sea legible. Marca con alerta exacta lo que falta.",
    manual: "Abrir cada PDF y revisar a ojo fechas, firmas y completitud, uno por uno.",
    minManual: 30,
  },
  {
    icono: "fa-id-card-o", titulo: "Validación de RUT, Rol y Dirección",
    sistema: "Cruza el RUT del titular y del codeudor en todos los documentos, y el rol de avalúo y la dirección entre tasación y títulos. Si algo no coincide, BLOQUEA el envío y dice exactamente qué y en qué documentos.",
    manual: "Comparar dígito a dígito entre documentos; un error puede pasar inadvertido y devolver la operación completa.",
    minManual: 20,
  },
  {
    icono: "fa-file-text-o", titulo: "Autocompletado de formularios",
    sistema: "Rellena todos los formularios con los datos ya guardados en la bóveda. Victoria solo revisa, corrige lo alertado y confirma.",
    manual: "Transcribir a mano cada campo desde los PDF, con riesgo de errores de tipeo.",
    minManual: 15,
  },
  {
    icono: "fa-paper-plane-o", titulo: "Revisión final y envío con un clic",
    sistema: "Genera el documento de envío consolidado; Victoria lo revisa y despacha a ConCreces con un solo clic. Queda registro completo en la bóveda.",
    manual: "Armar el set final, redactar el correo, adjuntar todo y enviarlo esperando no haber omitido nada.",
    minManual: 10,
  },
];
const TOTAL_MANUAL = PASOS.reduce((a, p) => a + p.minManual, 0);

const css = `
@keyframes pv-fade { from { opacity: 0; transform: translateY(18px); } to { opacity: 1; transform: translateY(0); } }
@keyframes pv-line { from { width: 0; } to { width: 100%; } }
@keyframes pv-pulse { 0%,100% { box-shadow: 0 0 0 0 rgba(212,175,55,0.5); } 50% { box-shadow: 0 0 0 14px rgba(212,175,55,0); } }
.pv-in { animation: pv-fade 0.7s ease both; }
.pv-in-2 { animation: pv-fade 0.7s ease 0.35s both; }
.pv-in-3 { animation: pv-fade 0.7s ease 0.7s both; }
`;

export const PresentacionVictoria = ({ onClose }) => {
  const [paso, setPaso] = useState(0);
  const [auto, setAuto] = useState(true);
  const fin = paso >= PASOS.length;

  const avanzar = useCallback(() => setPaso(p => Math.min(p + 1, PASOS.length)), []);
  useEffect(() => {
    if (!auto || fin) return;
    const t = setTimeout(avanzar, 7000);
    return () => clearTimeout(t);
  }, [paso, auto, fin, avanzar]);

  const p = PASOS[paso];
  return (
    <div data-testid="presentacion-victoria" style={{ position: "fixed", inset: 0, zIndex: 800, background: "#050505", color: "#e8e8e8", display: "flex", flexDirection: "column", fontFamily: "'Georgia', serif" }}>
      <style>{css}</style>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", padding: "1.1rem 2rem", borderBottom: `1px solid rgba(212,175,55,0.35)` }}>
        <div>
          <div style={{ color: ORO, letterSpacing: 4, fontSize: "0.7rem", fontWeight: 700 }}>CENTRAL MUTUOS</div>
          <div style={{ fontSize: "1.15rem", fontWeight: 800, letterSpacing: 1 }}>Módulo Victoria — Flujo ConCreces</div>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", gap: 10, alignItems: "center" }}>
          <button data-testid="presentacion-auto" onClick={() => setAuto(a => !a)}
            style={{ background: "transparent", border: `1px solid ${ORO}`, color: ORO, borderRadius: 0, padding: "0.35rem 0.8rem", fontSize: "0.68rem", cursor: "pointer" }}>
            {auto ? "⏸ Pausar" : "▶ Auto"}</button>
          <button data-testid="presentacion-cerrar" onClick={onClose}
            style={{ background: "transparent", border: "1px solid #555", color: "#aaa", borderRadius: 0, padding: "0.35rem 0.8rem", fontSize: "0.68rem", cursor: "pointer" }}>✕ Cerrar</button>
        </div>
      </div>
      {/* Timeline */}
      <div style={{ display: "flex", gap: 0, padding: "1rem 2rem 0" }}>
        {PASOS.map((s, i) => (
          <div key={i} style={{ flex: 1, display: "flex", alignItems: "center" }}>
            <button data-testid={`presentacion-punto-${i}`} onClick={() => { setPaso(i); setAuto(false); }}
              style={{ width: 30, height: 30, borderRadius: "50%", flexShrink: 0, cursor: "pointer",
                background: i <= paso && !fin ? ORO : fin ? ORO : "rgba(255,255,255,0.08)",
                color: i <= paso || fin ? "#0a0a0a" : "#777", border: `1px solid ${i <= paso || fin ? ORO : "#444"}`,
                fontWeight: 800, fontSize: "0.72rem", animation: i === paso && !fin ? "pv-pulse 2s infinite" : "none" }}>
              {i + 1}</button>
            {i < PASOS.length - 1 && (
              <div style={{ flex: 1, height: 1, background: "rgba(255,255,255,0.12)", position: "relative", overflow: "hidden" }}>
                {i < paso && <div style={{ position: "absolute", inset: 0, background: ORO, animation: "pv-line 0.6s ease both" }} />}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Contenido */}
      {!fin && p && (
        <div key={paso} style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", padding: "0 2rem", maxWidth: 1050, margin: "0 auto", width: "100%", boxSizing: "border-box" }}>
          <div className="pv-in" style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <i className={`fa ${p.icono}`} style={{ color: ORO, fontSize: "2rem" }}></i>
            <div>
              <div style={{ color: ORO, fontSize: "0.66rem", letterSpacing: 3, fontWeight: 700 }}>PASO {paso + 1} DE {PASOS.length}</div>
              <h2 data-testid="presentacion-titulo" style={{ margin: "2px 0 0", fontSize: "1.6rem", fontWeight: 800, color: "#fff" }}>{p.titulo}</h2>
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18, marginTop: 26 }}>
            <div className="pv-in-2" style={{ border: `1px solid ${ORO}`, background: "rgba(212,175,55,0.06)", padding: "1.3rem 1.4rem" }}>
              <div style={{ color: ORO, fontWeight: 800, fontSize: "0.7rem", letterSpacing: 2, marginBottom: 10 }}>⚙ CON EL SISTEMA</div>
              <p style={{ margin: 0, lineHeight: 1.75, fontSize: "0.95rem" }}>{p.sistema}</p>
              <div style={{ marginTop: 14, color: "#22c55e", fontWeight: 800, fontSize: "0.78rem" }}>⏱ automático · segundos</div>
            </div>
            <div className="pv-in-3" style={{ border: "1px solid rgba(255,255,255,0.15)", background: "rgba(255,255,255,0.03)", padding: "1.3rem 1.4rem" }}>
              <div style={{ color: "#999", fontWeight: 800, fontSize: "0.7rem", letterSpacing: 2, marginBottom: 10 }}>✍ SIN EL SISTEMA (MANUAL)</div>
              <p style={{ margin: 0, lineHeight: 1.75, fontSize: "0.95rem", color: "#bbb" }}>{p.manual}</p>
              <div style={{ marginTop: 14, color: "#ef4444", fontWeight: 800, fontSize: "0.78rem" }}>⏱ ≈ {p.minManual} minutos · propenso a error humano</div>
            </div>
          </div>
        </div>
      )}

      {/* Resumen final */}
      {fin && (
        <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", padding: "0 2rem", textAlign: "center" }}>
          <div className="pv-in">
            <div style={{ color: ORO, fontSize: "0.7rem", letterSpacing: 4, fontWeight: 700 }}>RESUMEN</div>
            <h2 data-testid="presentacion-resumen" style={{ margin: "6px 0 0", fontSize: "1.8rem", color: "#fff" }}>Lo que el módulo le devuelve a Victoria</h2>
          </div>
          <div className="pv-in-2" style={{ display: "flex", gap: 18, marginTop: 30, flexWrap: "wrap", justifyContent: "center" }}>
            {[
              [`≈ ${TOTAL_MANUAL} min → 10 min`, "por operación: de trabajo manual a solo revisar y confirmar"],
              [`${Math.round((1 - 10 / TOTAL_MANUAL) * 100)}% menos tiempo`, `≈ ${TOTAL_MANUAL - 10} minutos ahorrados en cada set de crédito`],
              ["0 descuadres", "RUT, rol de avalúo y dirección validados al 100% antes de cada envío"],
              ["0 vencidos", "documentos fuera de plazo bloqueados automáticamente"],
            ].map(([n, t], i) => (
              <div key={i} style={{ border: `1px solid ${ORO}`, background: "rgba(212,175,55,0.06)", padding: "1.4rem 1.6rem", width: 215 }}>
                <div style={{ color: ORO, fontSize: "1.25rem", fontWeight: 900 }}>{n}</div>
                <div style={{ color: "#bbb", fontSize: "0.74rem", marginTop: 8, lineHeight: 1.6 }}>{t}</div>
              </div>
            ))}
          </div>
          <p className="pv-in-3" style={{ marginTop: 28, color: "#999", fontSize: "0.82rem", maxWidth: 620, lineHeight: 1.8 }}>
            Las validaciones de coincidencia son <b style={{ color: ORO }}>Reglas de Oro ConCreces</b>, guardadas en la Constitución del sistema: irrenunciables, y ninguna actualización puede omitirlas.
          </p>
        </div>
      )}

      {/* Footer navegación */}
      <div style={{ display: "flex", gap: 10, padding: "1rem 2rem 1.4rem", borderTop: "1px solid rgba(212,175,55,0.25)", alignItems: "center" }}>
        <button data-testid="presentacion-anterior" onClick={() => { setPaso(x => Math.max(0, x - 1)); setAuto(false); }} disabled={paso === 0}
          style={{ background: "transparent", border: "1px solid #555", color: paso === 0 ? "#444" : "#ccc", padding: "0.5rem 1.1rem", cursor: "pointer", borderRadius: 0, fontSize: "0.74rem" }}>← Anterior</button>
        <button data-testid="presentacion-siguiente" onClick={() => { avanzar(); setAuto(false); }} disabled={fin}
          style={{ background: fin ? "#333" : `linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C)`, border: "none", color: "#0a0a0a", padding: "0.5rem 1.4rem", cursor: "pointer", fontWeight: 800, borderRadius: 0, fontSize: "0.74rem" }}>
          {paso === PASOS.length - 1 ? "Ver resumen →" : "Siguiente →"}</button>
        <span style={{ marginLeft: "auto", color: "#666", fontSize: "0.66rem", letterSpacing: 1 }}>
          {fin ? "Fin de la presentación" : `${p?.titulo || ""}`}</span>
      </div>
    </div>
  );
};

export default PresentacionVictoria;
