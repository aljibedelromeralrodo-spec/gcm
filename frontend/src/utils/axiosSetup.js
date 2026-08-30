// BÚNKER DE SEGURIDAD: adjunta el token JWT a cada llamada y gestiona el 401.
import axios from "axios";
import { secureGet, secureRemove } from "./secureStore";

axios.interceptors.request.use((config) => {
  const terminal = secureGet("token", false);
  const predic = secureGet("predic_auth");
  const token = terminal || (predic && predic.token);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
    // Cookie de sesión: permite abrir archivos con window.open / <a href> (el
    // navegador no envía headers en esos casos, pero sí la cookie).
    document.cookie = `cm_token=${token}; path=/; SameSite=Lax; Secure`;
  }
  return config;
});

function _detalleError(err) {
  const d = err?.response?.data?.detail;
  if (typeof d === "string" && d.trim()) return d.slice(0, 180);
  if (Array.isArray(d) && d.length) return (d.map(x => x.msg || x).join("; ")).slice(0, 180);
  if (!err?.response && (err?.message === "Network Error" || err?.code === "ERR_NETWORK")) {
    return "Sin conexión con el servidor.";
  }
  return "";
}

let _redirigiendo = false;
let _ultimoAviso = { t: 0, msg: "" };
axios.interceptors.response.use(
  (r) => r,
  (err) => {
    const status = err?.response?.status;
    if (status === 401 && !_redirigiendo) {
      _redirigiendo = true;
      secureRemove("token");
      secureRemove("user");
      secureRemove("predic_auth");
      document.cookie = "cm_token=; path=/; Max-Age=0";
      window.location.reload();
      return Promise.reject(err);
    }
    // Sondeos del topbar marcan silent:true para no inundar. El resto avisa una vez cada 12 s.
    if (!err?.config?.silent && status !== 401) {
      const msg = _detalleError(err) || (status >= 500 ? "El servidor no respondió correctamente." : "");
      const ahora = Date.now();
      if (msg && (msg !== _ultimoAviso.msg || ahora - _ultimoAviso.t > 12000)) {
        _ultimoAviso = { t: ahora, msg };
        try { window.dispatchEvent(new CustomEvent("cm-api-error", { detail: { status, msg } })); } catch { /* */ }
      }
    }
    return Promise.reject(err);
  }
);
