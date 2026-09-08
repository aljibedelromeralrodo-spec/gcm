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
  if (!err?.response && (err?.message === "Network Error" || err?.code === "ERR_NETWORK" || err?.code === "ECONNABORTED")) {
    return "Sin conexión con el servidor.";
  }
  return "";
}

function _esCaidaTemporal(err) {
  const status = err?.response?.status;
  if (status === 502 || status === 503 || status === 504) return true;
  if (!err?.response && (err?.message === "Network Error" || err?.code === "ERR_NETWORK" || err?.code === "ECONNABORTED")) {
    return true;
  }
  return false;
}

let _redirigiendo = false;
let _ultimoAviso = { t: 0, msg: "" };
axios.interceptors.response.use(
  (r) => {
    try { window.dispatchEvent(new Event("cm-api-ok")); } catch { /* */ }
    return r;
  },
  async (err) => {
    const cfg = err?.config || {};
    const method = String(cfg.method || "get").toLowerCase();
    const retries = cfg.__cmRetries || 0;
    if (_esCaidaTemporal(err) && ["get", "head", "options"].includes(method) && retries < 3) {
      cfg.__cmRetries = retries + 1;
      await new Promise((ok) => setTimeout(ok, 800 * cfg.__cmRetries));
      return axios(cfg);
    }
    const status = err?.response?.status;
    const url = String(cfg.url || "");
    const esLogin = /\/auth\/login|\/auth\/crear-clave|\/auth\/logout/.test(url);
    if (status === 401 && !_redirigiendo && !cfg.skipAuthRedirect && !esLogin) {
      _redirigiendo = true;
      secureRemove("token");
      secureRemove("user");
      secureRemove("predic_auth");
      try { axios.post(`${process.env.REACT_APP_BACKEND_URL || ""}/api/auth/logout`, {}, { silent: true }); } catch { /* */ }
      window.location.reload();
      return Promise.reject(err);
    }
    // Sondeos del topbar marcan silent:true para no inundar. El resto avisa una vez cada 12 s.
    if (!cfg.silent && status !== 401) {
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
