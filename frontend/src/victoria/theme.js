export const GOLD = "#BF953F";
export const GOLD_GRAD = "linear-gradient(90deg,#BF953F,#FCF6BA,#B38728)";
export const PLAYFAIR = "'Playfair Display', serif";

export const S = {
  page: { minHeight: "100vh", background: "#0a0a0a", color: "#fff", fontFamily: "Inter, sans-serif" },
  card: { background: "#141414", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 4, padding: "2rem", boxShadow: "0 8px 32px rgba(0,0,0,0.5)" },
  label: { fontSize: "0.8rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.2em", color: GOLD },
  kpiValue: { fontFamily: PLAYFAIR, fontSize: "3.2rem", fontWeight: 700, lineHeight: 1.1, color: "#fff" },
  h1: { fontFamily: PLAYFAIR, fontSize: "2.2rem", fontWeight: 700, color: "#fff", margin: 0, letterSpacing: 0.5 },
  h2: { fontFamily: PLAYFAIR, fontSize: "1.45rem", fontWeight: 600, color: "#FCF6BA", margin: 0 },
  body: { fontSize: "1rem", color: "#d4d4d8", lineHeight: 1.6 },
  btnGold: { background: GOLD_GRAD, color: "#0a0a0a", border: "none", borderRadius: 4, padding: "0.9rem 1.8rem", fontWeight: 700, fontSize: "1rem", cursor: "pointer", transition: "opacity 0.3s ease" },
  btnLine: { background: "transparent", color: "#FCF6BA", border: `1px solid ${GOLD}`, borderRadius: 4, padding: "0.9rem 1.8rem", fontWeight: 600, fontSize: "1rem", cursor: "pointer", transition: "background-color 0.3s ease" },
  btnDanger: { background: "transparent", color: "#f87171", border: "1px solid rgba(239,68,68,0.6)", borderRadius: 4, padding: "0.9rem 1.8rem", fontWeight: 600, fontSize: "1rem", cursor: "pointer" },
  btnSmall: { padding: "0.55rem 1.1rem", fontSize: "0.88rem" },
  input: { width: "100%", background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.15)", color: "#fff", padding: "0.85rem 1rem", borderRadius: 4, fontSize: "1rem", boxSizing: "border-box" },
  pill: (bg, fg) => ({ display: "inline-block", background: bg, color: fg, borderRadius: 999, padding: "0.3rem 0.9rem", fontSize: "0.82rem", fontWeight: 700, whiteSpace: "nowrap" }),
};

export const ESTADO_PILL = {
  despachado: ["rgba(34,197,94,0.15)", "#4ade80", "ENVIADO A CONCRECES"],
  listo: ["rgba(212,175,55,0.18)", "#FCF6BA", "LISTO PARA ENVÍO"],
  bloqueado: ["rgba(239,68,68,0.15)", "#f87171", "BLOQUEADO"],
  proceso: ["rgba(255,255,255,0.08)", "#d4d4d8", "EN PROCESO"],
};

export const estadoCliente = (c) => {
  if (c.despachado) return "despachado";
  if (c.listo_envio) return "listo";
  if (c.alertas_criticas > 0 || (c.faltantes || []).length > 0) return "bloqueado";
  return "proceso";
};

export const PASOS = [
  { n: 1, titulo: "Paso 1 — Recepción y clasificación de documentos" },
  { n: 2, titulo: "Paso 2 — Validación de RUT cliente, RUT codeudor, Rol de avalúo y dirección" },
  { n: 3, titulo: "Paso 3 — Revisión final con checklist completo" },
  { n: 4, titulo: "Paso 4 — Envío a ConCreces con confirmación" },
];
