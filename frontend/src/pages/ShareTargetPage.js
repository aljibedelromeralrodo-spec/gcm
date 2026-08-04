import { useEffect, useState } from "react";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;

// Lee el payload guardado por el service worker en IndexedDB.
// Ojo: NO borramos automáticamente — solo cuando el usuario confirme el upload
// o toque "Descartar". Así puede acumular archivos compartidos de a uno desde
// WhatsApp Business que no permite multi-share externo.
function readSharedPayload(consume) {
  return new Promise((resolve) => {
    try {
      const req = indexedDB.open("cm-share", 1);
      req.onupgradeneeded = () => req.result.createObjectStore("kv");
      req.onerror = () => resolve(null);
      req.onsuccess = () => {
        const tx = req.result.transaction("kv", "readwrite");
        const store = tx.objectStore("kv");
        const g = store.get("lastShare");
        g.onsuccess = () => {
          const val = g.result || null;
          if (consume && val) {
            try { store.delete("lastShare"); } catch (_e) { /* ignore */ }
          }
          resolve(val);
        };
        g.onerror = () => resolve(null);
      };
    } catch (e) {
      resolve(null);
    }
  });
}

function clearSharedPayload() {
  return new Promise((resolve) => {
    try {
      const req = indexedDB.open("cm-share", 1);
      req.onupgradeneeded = () => req.result.createObjectStore("kv");
      req.onsuccess = () => {
        const tx = req.result.transaction("kv", "readwrite");
        tx.objectStore("kv").delete("lastShare");
        tx.oncomplete = () => resolve();
      };
      req.onerror = () => resolve();
    } catch (e) { resolve(); }
  });
}

const MAX_ACCUMULATED_FILES = 20;

export default function ShareTargetPage() {
  const [payload, setPayload] = useState(null);
  const [folders, setFolders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [selectedFolder, setSelectedFolder] = useState("");
  const [folderSearch, setFolderSearch] = useState("");
  const [newName, setNewName] = useState("");
  const [newRut, setNewRut] = useState("");
  const [mode, setMode] = useState("existing"); // existing | new
  const [status, setStatus] = useState("");
  const [routeToCodeudor, setRouteToCodeudor] = useState(false);
  const [destino, setDestino] = useState("credito"); // credito | voucher_tasacion | voucher_gasto_operacional

  const DESTINOS = [
    { key: "credito", label: "Documentos crédito", icon: "fa-folder-open", color: "#d4af37", desc: "Carpeta del cliente (gestión de crédito)" },
    { key: "voucher_tasacion", label: "Voucher Tasación", icon: "fa-home", color: "#d4af37", desc: "Voucher de pago de la tasación" },
    { key: "voucher_gasto_operacional", label: "Voucher Gasto Op.", icon: "fa-money", color: "#10d98e", desc: "Vouchers de pago del gasto operacional" },
  ];

  useEffect(() => {
    (async () => {
      // NO consumir — el usuario puede seguir compartiendo más archivos
      const p = await readSharedPayload(false);
      setPayload(p);
      // Mostrar la página al tiro; las carpetas se cargan en segundo plano
      setLoading(false);
      const cargarCarpetas = (timeout) => axios.get(`${API}/api/clientes/folders-light`, { timeout })
        .then(r => setFolders(r.data.folders || []));
      cargarCarpetas(20000).catch(() => { cargarCarpetas(40000).catch((e) => console.error(e)); });
      // Auto-detect: si el primer archivo es PDF/imagen, OCR para extraer RUT
      if (p && p.files && p.files.length > 0) {
        const first = p.files[0];
        const isDetectable = /pdf|jpeg|jpg|png|heic|webp/i.test(first.type) ||
                             /\.(pdf|jpg|jpeg|png|heic|webp)$/i.test(first.name || "");
        if (isDetectable && !selectedFolder) {
          try {
            const fd = new FormData();
            const blob = first.blob instanceof Blob ? first.blob : new Blob([first.blob], { type: first.type });
            fd.append("file", blob, first.name);
            const dr = await axios.post(`${API}/api/clientes/detect-client`, fd, {
              headers: { "Content-Type": "multipart/form-data" },
              timeout: 30000,
            });
            const match = dr.data?.matched_folder;
            if (match) {
              setSelectedFolder(match.id);
              setMode("existing");
              setStatus(`🎯 Detecté RUT ${dr.data.rut} → carpeta de ${match.nombre}. Confirmá abajo.`);
            } else if (dr.data?.rut) {
              setNewRut(dr.data.rut);
              setStatus(`💡 Detecté RUT ${dr.data.rut} pero no encontré carpeta. Escribí el nombre para crear una nueva.`);
              setMode("new");
            }
          } catch (e) { /* noop, usuario elige manualmente */ }
        }
      }
      setLoading(false);
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps -- intencional: procesar archivo compartido solo al montar

  const handleDiscard = async () => {
    if (!window.confirm(`¿Descartar los ${payload?.files?.length || 0} archivo(s) acumulados?`)) return;
    await clearSharedPayload();
    window.location.href = "/";
  };

  const doUpload = async (folderId, folderNameForToast) => {
    if (!payload || !payload.files || payload.files.length === 0) {
      alert("No hay archivos para subir.");
      return;
    }
    setUploading(true);
    let ok = 0;
    const errors = [];
    for (const f of payload.files) {
      try {
        const fd = new FormData();
        const blob = f.blob instanceof Blob ? f.blob : new Blob([f.blob], { type: f.type });
        fd.append("file", blob, f.name || "archivo");
        if (destino !== "credito") fd.append("categoria", destino);
        else if (routeToCodeudor) fd.append("route_to_codeudor", "true");
        await axios.post(`${API}/api/clientes/folders/${folderId}/upload-file`, fd, {
          headers: { "Content-Type": "multipart/form-data" },
          timeout: 180000,
        });
        ok += 1;
      } catch (err) {
        errors.push(`${f.name}: ${err.response?.data?.detail || err.message}`);
      }
    }
    // Consumir sesión: limpiar IDB para no repetir en próximo share
    await clearSharedPayload();
    setUploading(false);
    const okMsg = destino === "voucher_tasacion"
      ? `✅ ${ok} voucher(s) de Tasación guardado(s) en la carpeta de ${folderNameForToast}.`
      : destino === "voucher_gasto_operacional"
        ? `✅ ${ok} voucher(s) de Gasto Operacional guardado(s) en la carpeta de ${folderNameForToast}.`
        : `✅ ${ok} archivo(s) subido(s) a ${folderNameForToast}. El COMBINADO_PROTOCOLO se está regenerando.`;
    setStatus(errors.length
      ? `✅ ${ok}/${payload.files.length} subidos. Errores:\n${errors.join("\n")}`
      : okMsg);
    setTimeout(() => {
      window.location.href = `/?open_folder=${folderId}`;
    }, 2000);
  };

  const handleUploadExisting = () => {
    const folder = folders.find((f) => f.id === selectedFolder);
    if (!folder) { alert("Elegí una carpeta"); return; }
    doUpload(folder.id, folder.nombre);
  };

  const handleCreateAndUpload = async () => {
    const nombre = newName.trim();
    if (!nombre) { alert("Escribí un nombre de cliente"); return; }
    setUploading(true);
    try {
      const r = await axios.post(`${API}/api/clientes/folders`, { nombre, rut: newRut.trim() });
      const newId = r.data.id;
      setUploading(false);
      await doUpload(newId, nombre);
    } catch (err) {
      setUploading(false);
      alert("Error creando carpeta: " + (err.response?.data?.detail || err.message));
    }
  };

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", background: "#0a0f1c", color: "#e2e8f0", display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem" }}>
        <div><i className="fa fa-spinner fa-spin" /> Cargando archivos compartidos…</div>
      </div>
    );
  }

  if (!payload || !payload.files || payload.files.length === 0) {
    return (
      <div style={{ minHeight: "100vh", background: "#0a0f1c", color: "#e2e8f0", padding: "1.5rem" }}>
        <div style={{ maxWidth: 560, margin: "0 auto" }}>
          <h2 style={{ marginTop: 0 }}>📲 Central Mutuos — Compartir archivos</h2>
          <p style={{ fontSize: 14, color: "#94a3b8" }}>Subí documentos de clientes directo al sistema, sin contraseña.</p>

          <label data-testid="share-pick-files" style={{ display: "block", textAlign: "center", background: "#d4af37", color: "#070708", borderRadius: 0, padding: "0.9rem", fontWeight: 700, fontSize: 15, cursor: "pointer", marginBottom: "1rem" }}>
            <i className="fa fa-folder-open" /> Elegir archivos del teléfono
            <input type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.heic,.webp,.doc,.docx,application/pdf,image/*"
              style={{ display: "none" }}
              onChange={(e) => {
                const fs = Array.from(e.target.files || []);
                if (fs.length === 0) return;
                setPayload({ files: fs.map(f => ({ name: f.name, type: f.type, size: f.size, blob: f })) });
              }} />
          </label>

          <div style={{ background: "rgba(212,175,55,0.1)", border: "1px solid rgba(212,175,55,0.4)", borderRadius: 0, padding: "0.8rem", fontSize: 13, marginBottom: "0.8rem" }}>
            <b>📥 O compartí desde WhatsApp:</b>
            <div style={{ marginTop: 4, color: "#cbd5e1" }}>Mantené presionado un archivo → <b>Compartir</b> → elegí <b>Central Mutuos</b>.</div>
          </div>

          <div style={{ background: "rgba(212,175,55,0.1)", border: "1px solid rgba(212,175,55,0.4)", borderRadius: 0, padding: "0.8rem", fontSize: 13 }}>
            <b style={{ color: "#facc15" }}>⬇️ Instalá el mini programa (una sola vez):</b>
            <ol style={{ margin: "0.4rem 0 0 1.1rem", padding: 0, color: "#cbd5e1" }}>
              <li>Abrí este link en <b>Chrome</b> del teléfono</li>
              <li>Menú (⋮) → <b>"Agregar a pantalla de inicio"</b> o <b>"Instalar aplicación"</b></li>
              <li>Queda el ícono <b>Central Mutuos</b> como una app</li>
            </ol>
          </div>

          <a href="/" style={{ color: "#facc15", display: "inline-block", marginTop: "1rem" }}>← Volver a la app</a>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", background: "#0a0f1c", color: "#e2e8f0", padding: "1rem", paddingBottom: "3rem" }}>
      <div style={{ maxWidth: 560, margin: "0 auto" }}>
        <h2 style={{ marginTop: 0 }}>📥 Archivos recibidos</h2>
        <div style={{ background: "rgba(212,175,55,0.1)", border: "1px solid rgba(212,175,55,0.5)", borderRadius: 0, padding: "0.75rem", marginBottom: "0.6rem" }}>
          <b>{payload.files.length} / {MAX_ACCUMULATED_FILES} archivo(s) acumulado(s):</b>
          {payload.files.length >= MAX_ACCUMULATED_FILES && (
            <div style={{ fontSize: 11, color: "#facc15", marginTop: 4 }}>⚠️ Límite alcanzado. Confirmá esta tanda antes de sumar más.</div>
          )}
          <ul style={{ margin: "0.4rem 0 0 1rem", padding: 0, fontSize: 13 }}>
            {payload.files.slice(0, MAX_ACCUMULATED_FILES).map((f, i) => (
              <li key={i}>{f.name} <span style={{ color: "#94a3b8" }}>({Math.round((f.size || 0) / 1024)} KB)</span></li>
            ))}
          </ul>
        </div>
        <div style={{ background: "rgba(250,204,21,0.12)", border: "1px solid rgba(250,204,21,0.4)", borderRadius: 0, padding: "0.6rem 0.8rem", marginBottom: "1rem", fontSize: 12, color: "#facc15" }}>
          💡 <b>WhatsApp Business no permite multi-share externo.</b> Podés volver a WhatsApp y compartir MÁS archivos de a uno — se van a ir acumulando acá (hasta 15 min). Cuando termines, confirmá abajo.
          <div style={{ marginTop: 6 }}>
            <button onClick={handleDiscard} data-testid="btn-discard"
              style={{ background: "transparent", border: "1px solid rgba(248,113,113,0.5)", color: "#fb7185", padding: "3px 10px", borderRadius: 0, fontSize: 11, cursor: "pointer" }}>
              🗑️ Descartar todos y empezar de cero
            </button>
          </div>
        </div>

        <div style={{ marginBottom: "0.9rem" }}>
          <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 6, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1 }}>¿Qué estás enviando?</div>
          <div style={{ display: "flex", gap: 6 }}>
            {DESTINOS.map((d) => (
              <button key={d.key} onClick={() => { setDestino(d.key); if (d.key !== "credito") setMode("existing"); }}
                data-testid={`destino-${d.key}`}
                style={{ flex: 1, padding: "0.55rem 0.3rem", background: destino === d.key ? d.color : "rgba(255,255,255,0.06)",
                  color: destino === d.key ? "#0a0f1c" : "#cbd5e1", border: `1px solid ${destino === d.key ? d.color : "rgba(148,163,184,0.25)"}`,
                  borderRadius: 0, fontWeight: 700, fontSize: 11.5, cursor: "pointer", lineHeight: 1.25 }}>
                <i className={`fa ${d.icon}`} style={{ display: "block", fontSize: 15, marginBottom: 3 }} />
                {d.label}
              </button>
            ))}
          </div>
          <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 5 }}>
            {DESTINOS.find((d) => d.key === destino)?.desc}
            {destino !== "credito" && " — se guarda en la carpeta del cliente como VOUCHER (no entra al COMBINADO)."}
          </div>
        </div>

        {destino === "credito" && (
          <div style={{ display: "flex", gap: 6, marginBottom: "1rem" }}>
            <button onClick={() => setMode("existing")} data-testid="mode-existing" style={{ flex: 1, padding: "0.6rem", background: mode === "existing" ? "#d4af37" : "rgba(212,175,55,0.2)", color: "#fff", border: "none", borderRadius: 0, fontWeight: 700, cursor: "pointer" }}>
              📁 Cliente existente
            </button>
            <button onClick={() => setMode("new")} data-testid="mode-new" style={{ flex: 1, padding: "0.6rem", background: mode === "new" ? "#10d98e" : "rgba(212,175,55,0.2)", color: "#fff", border: "none", borderRadius: 0, fontWeight: 700, cursor: "pointer" }}>
              ➕ Cliente nuevo
            </button>
          </div>
        )}

        {(mode === "existing" || destino !== "credito") ? (
          <div>
            <label style={{ display: "block", fontSize: 12, marginBottom: 4, color: "#94a3b8" }}>🔍 Buscar carpeta cliente</label>
            <input
              type="text"
              value={folderSearch}
              onChange={(e) => setFolderSearch(e.target.value)}
              placeholder="Escribí nombre o RUT (ej: Bryan, 20398906)"
              data-testid="folder-search"
              style={{ width: "100%", padding: "0.55rem 0.7rem", borderRadius: 0, background: "#232326", color: "#e2e8f0", border: "1px solid rgba(148,163,184,0.3)", fontSize: 14, marginBottom: "0.4rem" }}
            />
            <div style={{ maxHeight: 260, overflowY: "auto", background: "rgba(14,14,16,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)", border: "1px solid rgba(148,163,184,0.15)", borderRadius: 0, marginBottom: "0.8rem" }}>
              {(() => {
                const q = folderSearch.trim().toLowerCase();
                const norm = (s) => (s || "").toLowerCase().replace(/[.\-\s]/g, "");
                const list = folders.filter((f) => {
                  if (!q) return true;
                  return (f.nombre || "").toLowerCase().includes(q) ||
                         norm(f.rut).includes(norm(q));
                });
                if (list.length === 0) {
                  return <div style={{ padding: "0.8rem", fontSize: 12, color: "#94a3b8", textAlign: "center" }}>Sin resultados. Probá con &quot;Cliente nuevo&quot;.</div>;
                }
                return list.slice(0, 100).map((f) => (
                  <div key={f.id} onClick={() => setSelectedFolder(f.id)} data-testid={`folder-opt-${f.id}`}
                    style={{ padding: "0.55rem 0.7rem", cursor: "pointer", borderBottom: "1px solid rgba(148,163,184,0.08)", background: selectedFolder === f.id ? "rgba(212,175,55,0.25)" : "transparent", color: "#e2e8f0", fontSize: 13 }}>
                    <div style={{ fontWeight: selectedFolder === f.id ? 700 : 500 }}>
                      {selectedFolder === f.id && <span style={{ color: "#d4af37" }}>✓ </span>}
                      {f.nombre}
                    </div>
                    {f.rut && <div style={{ fontSize: 11, color: "#94a3b8" }}>RUT: {f.rut}</div>}
                  </div>
                ));
              })()}
            </div>
            <button onClick={handleUploadExisting} disabled={!selectedFolder || uploading} data-testid="btn-upload-existing"
              style={{ width: "100%", padding: "0.75rem", background: (!selectedFolder || uploading) ? "#475569" : "#d4af37", color: "#fff", border: "none", borderRadius: 0, fontWeight: 700, fontSize: 14, cursor: uploading ? "wait" : "pointer" }}>
              <i className={`fa ${uploading ? "fa-spinner fa-spin" : "fa-upload"}`} /> {uploading ? "Subiendo…"
                : destino === "voucher_tasacion" ? `Guardar ${payload.files.length} voucher(s) de Tasación`
                : destino === "voucher_gasto_operacional" ? `Guardar ${payload.files.length} voucher(s) de Gasto Op.`
                : `Subir ${payload.files.length} archivo(s)${routeToCodeudor ? ' (Codeudor)' : ' (Titular)'}`}
            </button>
            {destino === "credito" && selectedFolder && (() => {
              const folder = folders.find((x) => x.id === selectedFolder);
              const hasCodeudor = folder && (folder.codeudor_nombre || "").trim().length > 0;
              if (!hasCodeudor) return null;
              return (
                <div style={{ marginTop: 10, padding: "0.6rem 0.8rem", background: "rgba(46,92,230,0.12)", border: "1px solid rgba(46,92,230,0.5)", borderRadius: 0, fontSize: 12, color: "#c4b5fd" }}>
                  <div style={{ marginBottom: 6, fontWeight: 700 }}>⚠️ Esta carpeta tiene CODEUDOR ({folder.codeudor_nombre})</div>
                  <div style={{ marginBottom: 8 }}>Elegí a quién pertenecen estos {payload.files.length} archivo(s):</div>
                  <div style={{ display: "flex", gap: 6 }}>
                    <button onClick={() => setRouteToCodeudor(false)} data-testid="btn-route-titular"
                      style={{ flex: 1, padding: "6px", background: !routeToCodeudor ? "#d4af37" : "transparent", border: `1px solid ${!routeToCodeudor ? "#d4af37" : "rgba(46,92,230,0.5)"}`, color: "#fff", borderRadius: 0, fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
                      👤 Titular ({folder.nombre.slice(0, 20)})
                    </button>
                    <button onClick={() => setRouteToCodeudor(true)} data-testid="btn-route-codeudor"
                      style={{ flex: 1, padding: "6px", background: routeToCodeudor ? "#2e5ce6" : "transparent", border: `1px solid ${routeToCodeudor ? "#2e5ce6" : "rgba(46,92,230,0.5)"}`, color: "#fff", borderRadius: 0, fontSize: 12, fontWeight: 600, cursor: "pointer" }}>
                      👥 Codeudor ({folder.codeudor_nombre.slice(0, 20)})
                    </button>
                  </div>
                  <div style={{ marginTop: 6, fontSize: 10, color: "#a78bfa" }}>
                    Titular → COMBINADO_PROTOCOLO principal. Codeudor → COMBINADO_CODEUDOR separado.
                  </div>
                </div>
              );
            })()}
          </div>
        ) : (
          <div>
            <label style={{ display: "block", fontSize: 12, marginBottom: 4, color: "#94a3b8" }}>Nombre del cliente *</label>
            <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Ej: Bryan Contreras" data-testid="new-name-input"
              style={{ width: "100%", padding: "0.6rem", borderRadius: 0, background: "#232326", color: "#e2e8f0", border: "1px solid rgba(148,163,184,0.3)", fontSize: 14, marginBottom: "0.6rem" }} />
            <label style={{ display: "block", fontSize: 12, marginBottom: 4, color: "#94a3b8" }}>RUT (opcional)</label>
            <input value={newRut} onChange={(e) => setNewRut(e.target.value)} placeholder="15234567-8" data-testid="new-rut-input"
              style={{ width: "100%", padding: "0.6rem", borderRadius: 0, background: "#232326", color: "#e2e8f0", border: "1px solid rgba(148,163,184,0.3)", fontSize: 14, marginBottom: "0.8rem" }} />
            <button onClick={handleCreateAndUpload} disabled={!newName.trim() || uploading} data-testid="btn-create-and-upload"
              style={{ width: "100%", padding: "0.75rem", background: (!newName.trim() || uploading) ? "#475569" : "#10d98e", color: "#fff", border: "none", borderRadius: 0, fontWeight: 700, fontSize: 14, cursor: uploading ? "wait" : "pointer" }}>
              <i className={`fa ${uploading ? "fa-spinner fa-spin" : "fa-plus"}`} /> {uploading ? "Creando y subiendo…" : `Crear carpeta y subir ${payload.files.length} archivo(s)`}
            </button>
          </div>
        )}

        {status && (
          <div style={{ marginTop: "1rem", padding: "0.75rem", background: "rgba(16,217,142,0.12)", border: "1px solid rgba(16,217,142,0.5)", borderRadius: 0, whiteSpace: "pre-wrap", fontSize: 13 }} data-testid="share-status">
            {status}
          </div>
        )}

        <div style={{ marginTop: "1.5rem", textAlign: "center" }}>
          <a href="/" style={{ color: "#94a3b8", fontSize: 13 }}>← Cancelar y volver</a>
        </div>
      </div>
    </div>
  );
}
