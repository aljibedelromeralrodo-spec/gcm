export const COLORS = {
  bg: "#0a0e27",
  card: "#111638",
  accent: "#6C5CE7",
  accentLight: "#a29bfe",
  gold: "#fdcb6e",
  green: "#00b894",
  red: "#e17055",
  orange: "#f39c12",
  text: "#dfe6e9",
  textMuted: "#636e72",
  border: "rgba(108,92,231,0.3)",
};

export function formatCLP(n) {
  return "$" + Math.round(n).toLocaleString("es-CL");
}
