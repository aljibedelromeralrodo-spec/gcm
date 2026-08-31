export const API_URL = process.env.REACT_APP_BACKEND_URL || "";

const CSS_CONTRASTE_CORREO = `<style id="cm-contraste">
  tr[style*="#141416"], tr[style*="#0f0f11"] { background:#f3f4f6 !important; }
  td[style*="color:#FCF6BA"], td[style*="color:#fcf6ba"],
  td[style*="color:#e8e2cf"], td[style*="color:#E8E2CF"],
  td[style*="color:#F5E7B8"], td[style*="color:#8a7a5a"],
  td[style*="color:#b8860b"], td[style*="color:#d4af37"],
  th[style*="color:#FCF6BA"], h3[style*="color:#b8860b"] { color:#111827 !important; }
  td[style*="background:#0a0a0a"], td[style*="background:#0a0a0a"] *,
  div[style*="background:#0a0a0a"] { color:#C9A227 !important; }
  td[style*="background:#1a1f2e"], td[style*="background:#1a1f2e"] *,
  tr[style*="background:#1a1f2e"] td { color:#F5E7B8 !important; }
</style>`;

/** Correos operativos: tinta oscura sobre blanco. Encabezado negro y TOTAL GOP se respetan. */
export function htmlConContrasteCorreo(html) {
  if (!html) return "";
  if (html.includes('id="cm-contraste"') || html.includes("id='cm-contraste'")) return html;
  if (/<head/i.test(html)) return html.replace(/<head([^>]*)>/i, `<head$1>${CSS_CONTRASTE_CORREO}`);
  return `${CSS_CONTRASTE_CORREO}${html}`;
}

export const formatCurrency = (amount) => {
  if (!amount && amount !== 0) return "$0";
  return new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP", maximumFractionDigits: 0 }).format(amount);
};

export const formatUF = (amount) => {
  if (!amount && amount !== 0) return "0,00 UF";
  return new Intl.NumberFormat("es-CL", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(amount) + " UF";
};
