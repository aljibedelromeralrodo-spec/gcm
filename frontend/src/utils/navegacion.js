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

const MOD_RX = /^[a-z][a-z0-9_]{1,40}$/;

/** Módulo activo desde ?mod= (prioridad) o sessionStorage. No toca el hash. */
export function leerModuloUrl(validos) {
  try {
    const q = new URLSearchParams(window.location.search).get("mod") || "";
    if (MOD_RX.test(q) && (!validos || validos.has(q))) return q;
  } catch { /* */ }
  try {
    const s = sessionStorage.getItem("cm_mod") || "";
    if (MOD_RX.test(s) && (!validos || validos.has(s))) return s;
  } catch { /* */ }
  return "";
}

/** Persiste el módulo en ?mod= con replaceState (F5 y deep-link, sin ensuciar el historial). */
export function escribirModuloUrl(mod) {
  if (!mod || !MOD_RX.test(mod)) return;
  try { sessionStorage.setItem("cm_mod", mod); } catch { /* */ }
  try {
    const u = new URL(window.location.href);
    if (u.searchParams.get("mod") === mod) return;
    u.searchParams.set("mod", mod);
    window.history.replaceState(null, "", u.pathname + u.search + u.hash);
  } catch { /* */ }
}
