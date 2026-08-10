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

let _redirigiendo = false;
axios.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err && err.response && err.response.status === 401 && !_redirigiendo) {
      _redirigiendo = true;
      secureRemove("token");
      secureRemove("user");
      secureRemove("predic_auth");
      document.cookie = "cm_token=; path=/; Max-Age=0";
      window.location.reload();
    }
    return Promise.reject(err);
  }
);
