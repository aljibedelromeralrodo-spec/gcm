/* Service Worker Central Mutuos: recibe archivos compartidos (Web Share Target)
   y los acumula en IndexedDB para que /share-target los procese. */
const MAX_FILES = 20;
const EXPIRY_MS = 15 * 60 * 1000;

self.addEventListener("install", (e) => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

function idbOpen() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open("cm-share", 1);
    req.onupgradeneeded = () => req.result.createObjectStore("kv");
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function idbGet(db, key) {
  return new Promise((resolve) => {
    const g = db.transaction("kv", "readonly").objectStore("kv").get(key);
    g.onsuccess = () => resolve(g.result || null);
    g.onerror = () => resolve(null);
  });
}

function idbSet(db, key, val) {
  return new Promise((resolve) => {
    const tx = db.transaction("kv", "readwrite");
    tx.objectStore("kv").put(val, key);
    tx.oncomplete = () => resolve();
    tx.onerror = () => resolve();
  });
}

async function handleShare(request) {
  const formData = await request.formData();
  const files = formData.getAll("files").filter((f) => f && f.size);
  const nuevos = [];
  for (const f of files) {
    nuevos.push({ name: f.name || "archivo", type: f.type || "", size: f.size, blob: f });
  }
  const db = await idbOpen();
  let payload = await idbGet(db, "lastShare");
  // Acumular con lo anterior si no expiró
  if (payload && payload.ts && Date.now() - payload.ts < EXPIRY_MS && Array.isArray(payload.files)) {
    const existentes = payload.files;
    const nombres = new Set(existentes.map((x) => `${x.name}|${x.size}`));
    for (const n of nuevos) {
      if (!nombres.has(`${n.name}|${n.size}`) && existentes.length < MAX_FILES) {
        existentes.push(n);
      }
    }
    payload = { files: existentes, ts: Date.now() };
  } else {
    payload = { files: nuevos.slice(0, MAX_FILES), ts: Date.now() };
  }
  await idbSet(db, "lastShare", payload);
  return Response.redirect("/share-target", 303);
}

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method === "POST" && url.pathname === "/share-receive") {
    e.respondWith(handleShare(e.request));
  }
});
