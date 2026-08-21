// NORMATIVA DE NAVEGACIÓN: "Volver" regresa siempre al estado exacto anterior
export const guardarEstado = (clave, estado) => {
  try { sessionStorage.setItem(`cm_nav_${clave}`, JSON.stringify(estado)); } catch { /* lleno */ }
};
export const leerEstado = (clave) => {
  try { return JSON.parse(sessionStorage.getItem(`cm_nav_${clave}`)) || null; } catch { return null; }
};
export const marcarRegreso = (clave) => sessionStorage.setItem(`cm_nav_regreso_${clave}`, "1");
export const tomarRegreso = (clave) => {
  const v = sessionStorage.getItem(`cm_nav_regreso_${clave}`) === "1";
  sessionStorage.removeItem(`cm_nav_regreso_${clave}`);
  return v;
};
