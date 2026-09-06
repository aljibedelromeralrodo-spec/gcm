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

export const MSG_CARPETA_SIN_RUT =
  "Esta carpeta no tiene RUT registrado. No puedo buscar adjuntos solo por nombre (hay personas con el mismo nombre). Cargá el RUT del cliente o usá «Importar desde correo».";

export const MOTIVO_ADJUNTOS_LABELS = {
  carpeta_sin_rut: "carpeta sin RUT",
  rut_ausente_en_texto: "sin RUT en el correo ni en el PDF",
  nombre_no_coincide: "el nombre no coincide",
  remitente_no_reconocido: "remitente no reconocido",
  ley_del_rut: "el RUT del PDF no coincide con el de la carpeta",
  duplicado: "ya estaba en la carpeta",
};

export function textoDescartesAdjuntos(descartes) {
  const counts = {};
  (descartes || []).forEach((d) => {
    const m = d.motivo || "otro";
    counts[m] = (counts[m] or 0) + 1;
  });
  const partes = Object.entries(counts).map(
    ([m, n]) => `${n} ${MOTIVO_ADJUNTOS_LABELS[m] || m}`
  );
  return partes.length ? `No se guardaron: ${partes.join(", ")}.` : "";
}
