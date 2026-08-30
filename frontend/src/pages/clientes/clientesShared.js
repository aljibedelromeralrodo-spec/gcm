export const API = process.env.REACT_APP_BACKEND_URL;
// Regla #65: validador de dígito verificador (módulo 11) — RUT verificado al 100%
export const rutValido = (rut) => {
  const r = String(rut || "").replace(/[^0-9kK]/g, "").toLowerCase();
  if (r.length < 8 || !/^\d+$/.test(r.slice(0, -1))) return false;
  const cuerpo = r.slice(0, -1), dv = r.slice(-1);
  let s = 0, m = 2;
  for (let i = cuerpo.length - 1; i >= 0; i--) { s += parseInt(cuerpo[i], 10) * m; m = m === 7 ? 2 : m + 1; }
  const res = 11 - (s % 11);
  const dvC = res === 11 ? "0" : res === 10 ? "k" : String(res);
  return dv === dvC;
};
export const CAT_LABELS = { cedula: "Cédula", liquidacion: "Liquidaciones", afp: "AFP", cmf: "CMF", imp_renta: "F22 / Carpeta tributaria", boletas: "Boletas / DAI", f29: "F29", contrato: "Contrato" };
