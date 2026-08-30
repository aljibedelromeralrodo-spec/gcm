// BÚNKER DE SEGURIDAD: sesión terminal en cookie HttpOnly; Bearer solo legado / Predic.
import axios from "axios";
import { secureGet, secureRemove } from "./secureStore";

axios.defaults.withCredentials = true;

axios.interceptors.request.use((config) => {
  config.withCredentials = true;
  const predic = secureGet("predic_auth");
  const legado = secureGet("token", false); // sesiones anteriores a HttpOnly
  const token = (predic && predic.token) || legado;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
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
    if (status === 401 && !_redirigiendo && !err?.config?.skipAuthRedirect) {
      _redirigiendo = true;
      secureRemove("token");
      secureRemove("user");
      secureRemove("predic_auth");
      try { axios.post(`${process.env.REACT_APP_BACKEND_URL || ""}/api/auth/logout`, {}, { silent: true }); } catch { /* */ }
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
