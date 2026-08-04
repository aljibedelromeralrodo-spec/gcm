// Almacenamiento local ofuscado (XOR + base64). La defensa principal contra XSS
// es la sanitización con DOMPurify; esto evita credenciales legibles en texto plano.
const KEY = "CM-2026-terminal-oro";

const xor = (s) =>
  s.split("").map((c, i) => String.fromCharCode(c.charCodeAt(0) ^ KEY.charCodeAt(i % KEY.length))).join("");

export const secureSet = (k, value) => {
  try {
    const str = typeof value === "string" ? value : JSON.stringify(value);
    localStorage.setItem(k, "v1:" + btoa(unescape(encodeURIComponent(xor(str)))));
  } catch (e) { console.error("secureSet:", e); }
};

export const secureGet = (k, parseJson = true) => {
  const raw = localStorage.getItem(k);
  if (!raw) return null;
  try {
    let str;
    if (raw.startsWith("v1:")) {
      str = xor(decodeURIComponent(escape(atob(raw.slice(3)))));
    } else {
      str = raw; // valor legado sin cifrar: migrar
      secureSet(k, parseJson ? JSON.parse(raw) : raw);
    }
    return parseJson ? JSON.parse(str) : str;
  } catch (e) {
    console.error("secureGet:", e);
    localStorage.removeItem(k);
    return null;
  }
};

export const secureRemove = (k) => localStorage.removeItem(k);
