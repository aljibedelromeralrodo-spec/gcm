import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

const COL_COLOR = {
  captacion: "#7c3aed",
  clasificar: "#d97706",
  autorizar: "#ea580c",
  listo_mesa: "#2563eb",
  gop: "#0f766e",
  en_mesa: "#4338ca",
  escrituracion: "#a16207",
  cerrado: "#15803d",
};

const CTA = {
  sincronizar: "Clasificar carpeta",
  autorizar_faltantes: "Autorizar mail de faltantes",
  enviar_gop: "Enviar gasto operacional",
  registrar_gop: "Registrar pago GOP",
  enviar_mesa: "Enviar a Mesa",
  enviar_tasacion: "Solicitar tasación",
  enviar_estudio: "Solicitar estudio de títulos",
  mover_escrituracion: "Pasar a escrituración",
  abrir_escritura: "Abrir Escritura",
  abrir_postventa: "Abrir Postventa",
  abrir_publicidad: "Abrir Publicidad",
  abrir_supercarpeta: "Abrir Supercarpeta",
};

export default function ProFlujoModule({ onNavigate }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [q, setQ] = useState("");
  const [colFiltro, setColFiltro] = useState("");
  const [ficha, setFicha] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [pin, setPin] = useState("");
  const [direccion, setDireccion] = useState("");

  const load = () => {
    axios.get(`${API_URL}/api/pro-flujo`).then((r) => { setData(r.data); setErr(""); })
      .catch((e) => setErr(e.response?.data?.detail || "No se pudo cargar el Pro Flujo"));
  };
  useEffect(() => { load(); }, []);

  const abrir = async (it) => {
    if (it.prospecto) {
      ir("publicidad", it);
      return;
    }
    setMsg("");
    setPin("");
    try {
      const r = await axios.get(`${API_URL}/api/pro-flujo/ficha/${it.id}`);
      setFicha(r.data);
      setDireccion(r.data.preview?.direccion || "");
    } catch (e) {
      setFicha({ ...it, preview: { tipo: "error", hint: e.response?.data?.detail || e.message } });
    }
  };

  const ir = (mod, it) => {
    if (it?.id && !it.prospecto) sessionStorage.setItem("cm_abrir_folder_id", it.id);
    if (it?.nombre) sessionStorage.setItem("cm_prefill_cliente", JSON.stringify({ nombre: it.nombre, rut: it.rut || "", folder_id: it.id }));
    if (it?.auth_id) sessionStorage.setItem("cm_abrir_auth_id", it.auth_id);
    if (onNavigate) onNavigate(mod);
  };

  const actuar = async (confirm) => {
    if (!ficha) return;
    const accion = ficha.accion;
    if (accion?.startsWith("abrir_")) {
      ir(ficha.modulo, ficha);
      return;
    }
    if (accion === "registrar_gop") {
      ir("gastos", ficha);
      return;
    }
    setBusy(true);
    setMsg("");
    try {
      const r = await axios.post(`${API_URL}/api/pro-flujo/actuar`, {
        fid: ficha.id,
        accion,
        confirm,
        auth_id: ficha.auth_id,
        master_pin: pin,
        direccion,
        email: ficha.email,
      });
      setMsg(r.data.mensaje || "Listo");
      if (confirm || accion === "sincronizar") {
        load();
        if (ficha.id) {
          const nf = await axios.get(`${API_URL}/api/pro-flujo/ficha/${ficha.id}`);
          setFicha(nf.data);
        }
      }
    } catch (e) {
      setMsg(e.response?.data?.detail || e.message);
    } finally { setBusy(false); }
  };

  const cols = useMemo(() => {
    const list = data?.columnas || [];
    const ql = q.trim().toLowerCase();
    return list
      .filter((c) => !colFiltro || c.id === colFiltro)
      .map((c) => ({
        ...c,
        items: (c.items || []).filter((it) => {
          if (!ql) return true;
          return `${it.nombre} ${it.rut} ${it.protocolo}`.toLowerCase().includes(ql);
        }),
      }));
  }, [data, q, colFiltro]);

  const pv = ficha?.preview || {};

  return (
    <div style={{ padding: "1.1rem 1.2rem 2rem" }} data-testid="pro-flujo">
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h2 style={{ margin: 0, color: "#d4af37", fontFamily: "'Playfair Display', serif" }}>Pro Flujo operativo</h2>
          <p style={{ margin: "4px 0 0", color: "#94a3b8", fontSize: 13 }}>
            Tocá una tarjeta, revisá el preview y ejecutá el siguiente paso. Los correos siguen pasando por autorización / preview.
          </p>
        </div>
        <button onClick={load} style={btn}>↻ Actualizar</button>
      </div>

      {err && <p style={{ color: "#f87171", fontWeight: 700 }}>{err}</p>}

      {data && (
        <>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", margin: "12px 0" }}>
            <Chip>Carpetas {data.total_carpetas}</Chip>
            <Chip>Prospectos {data.total_prospectos}</Chip>
            <Chip>Mails por autorizar {data.autorizaciones_pendientes}</Chip>
            <Chip ok={data.listo_para_operar}>
              {data.listo_para_operar ? "Correo de salida listo" : "Falta MAIL2 para operar al 100%"}
            </Chip>
          </div>

          {(data.bloqueos_100 || []).length > 0 && (
            <div data-testid="pro-flujo-bloqueos" style={{ border: "1px solid rgba(251,191,36,0.4)",
              background: "rgba(120,53,15,0.25)", padding: "10px 12px", marginBottom: 14 }}>
              <b style={{ color: "#fbbf24", fontSize: 12 }}>Para el 100% falta</b>
              <ul style={{ margin: "6px 0 0", paddingLeft: 18, color: "#e2e8f0", fontSize: 13 }}>
                {data.bloqueos_100.map((b) => (
                  <li key={b.id}>
                    <button onClick={() => onNavigate?.(b.modulo)} style={linkBtn}>{b.modulo}</button>
                    {" — "}{b.falta}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar cliente o RUT…"
              style={{ flex: "1 1 180px", minWidth: 160, background: "rgba(0,0,0,0.35)", color: "#e2e8f0",
                border: "1px solid rgba(212,175,55,0.3)", padding: "6px 10px" }} />
            <button onClick={() => setColFiltro("")} style={chipBtn(!colFiltro)}>Todas</button>
            {(data.columnas || []).map((c) => (
              <button key={c.id} onClick={() => setColFiltro(c.id)} style={chipBtn(colFiltro === c.id)}>
                {c.titulo} {c.n}
              </button>
            ))}
          </div>

          <div style={{ display: "flex", gap: 10, overflowX: "auto", paddingBottom: 12 }}>
            {cols.map((c) => (
              <div key={c.id} data-testid={`col-${c.id}`} style={{
                minWidth: 230, maxWidth: 270, flex: "0 0 230px",
                background: "rgba(15,23,42,0.7)", border: "1px solid rgba(212,175,55,0.2)", padding: 8,
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                  <b style={{ color: COL_COLOR[c.id] || "#d4af37", fontSize: 12 }}>{c.titulo}</b>
                  <span style={{ color: "#94a3b8", fontSize: 11 }}>{c.items.length}</span>
                </div>
                <div style={{ color: "#64748b", fontSize: 11, margin: "2px 0 8px" }}>{c.hint}</div>
                {c.items.map((it) => (
                  <button key={it.id || it.nombre} onClick={() => abrir(it)}
                    data-testid={`card-${it.id || it.nombre}`}
                    style={{
                      display: "block", width: "100%", textAlign: "left", cursor: "pointer",
                      background: ficha?.id === it.id ? "rgba(212,175,55,0.12)" : "rgba(0,0,0,0.35)",
                      border: `1px solid ${ficha?.id === it.id ? "#d4af37" : "rgba(148,163,184,0.15)"}`,
                      color: "#e2e8f0", padding: "8px 8px 7px", marginBottom: 6, fontSize: 12,
                    }}>
                    <div style={{ fontWeight: 800 }}>{it.nombre}</div>
                    {it.protocolo ? <div style={{ color: "#94a3b8", fontSize: 11 }}>{it.protocolo}</div> : null}
                    <div style={{ color: "#fde68a", fontSize: 11, marginTop: 3 }}>{it.siguiente}</div>
                    {it.hitos?.length ? (
                      <div style={{ color: "#86efac", fontSize: 10, marginTop: 2 }}>{it.hitos.join(" · ")}</div>
                    ) : null}
                  </button>
                ))}
              </div>
            ))}
          </div>
        </>
      )}

      {ficha && (
        <div data-testid="pro-flujo-ficha" style={{
          marginTop: 8, border: "1px solid rgba(212,175,55,0.35)",
          background: "rgba(2,6,23,0.92)", padding: 14,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
            <div>
              <b style={{ color: "#d4af37", fontSize: 16 }}>{ficha.nombre}</b>
              <div style={{ color: "#94a3b8", fontSize: 12 }}>{ficha.rut || "sin RUT"} · {ficha.email || "sin correo"}</div>
            </div>
            <button onClick={() => setFicha(null)} style={ghost}>Cerrar</button>
          </div>
          <p style={{ color: "#fde68a", fontSize: 13, margin: "8px 0" }}>{ficha.siguiente}</p>
          {(ficha.faltan || []).length > 0 && (
            <p style={{ color: "#fdba74", fontSize: 12 }}>Faltan: {ficha.faltan.join(", ")}</p>
          )}
          {pv.hint && <p style={{ color: "#cbd5e1", fontSize: 12 }}>{pv.hint}</p>}
          {pv.subject && <p style={{ color: "#e2e8f0", fontSize: 12 }}><b>Asunto:</b> {pv.subject}</p>}
          {pv.to && <p style={{ color: "#e2e8f0", fontSize: 12 }}><b>Para:</b> {Array.isArray(pv.to) ? pv.to.join(", ") : pv.to}</p>}
          {pv.body && (
            <div style={{ maxHeight: 180, overflow: "auto", background: "#fff", color: "#111",
              padding: 8, fontSize: 12, margin: "6px 0 10px" }}
              dangerouslySetInnerHTML={{ __html: pv.body }} />
          )}
          {ficha.accion === "enviar_tasacion" && (
            <label style={{ display: "block", color: "#94a3b8", fontSize: 11, fontWeight: 700 }}>
              Dirección de la propiedad
              <input value={direccion} onChange={(e) => setDireccion(e.target.value)}
                style={{ display: "block", width: "100%", marginTop: 4, padding: 6 }} />
            </label>
          )}
          {pv.pide_pin && (
            <label style={{ display: "block", color: "#94a3b8", fontSize: 11, fontWeight: 700, marginTop: 8 }}>
              MASTER_PIN (GOP)
              <input type="password" value={pin} onChange={(e) => setPin(e.target.value)}
                style={{ display: "block", width: 220, marginTop: 4, padding: 6 }} />
            </label>
          )}
          {msg && <p style={{ color: msg.toLowerCase().includes("error") || msg.toLowerCase().includes("falta") ? "#f87171" : "#86efac", fontWeight: 700, fontSize: 13 }}>{msg}</p>}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
            {["abrir_publicidad", "abrir_postventa", "abrir_supercarpeta", "abrir_escritura", "registrar_gop"].includes(ficha.accion) ? (
              <button disabled={busy} onClick={() => actuar(false)} style={btn}>
                {CTA[ficha.accion] || "Abrir módulo"}
              </button>
            ) : (
              <>
                <button disabled={busy} onClick={() => actuar(false)} style={ghost}>
                  {ficha.accion === "sincronizar" ? CTA.sincronizar : "Ver preview"}
                </button>
                {ficha.accion !== "sincronizar" && (
                  <button disabled={busy} onClick={() => actuar(true)} style={btn} data-testid="pro-flujo-ejecutar">
                    {busy ? "…" : (CTA[ficha.accion] || "Ejecutar")}
                  </button>
                )}
              </>
            )}
            <button onClick={() => ir(ficha.modulo, ficha)} style={ghost}>Abrir {ficha.modulo}</button>
          </div>
        </div>
      )}
    </div>
  );
}

function Chip({ children, ok }) {
  return (
    <span style={{
      fontSize: 12, fontWeight: 700, padding: "4px 10px",
      background: ok === false ? "rgba(127,29,29,0.4)" : "rgba(212,175,55,0.12)",
      color: ok === false ? "#fecaca" : "#fde68a",
      border: "1px solid rgba(212,175,55,0.25)",
    }}>{children}</span>
  );
}

const btn = {
  background: "linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C)", color: "#0a0a0a",
  border: "none", fontWeight: 800, padding: "8px 14px", cursor: "pointer",
};
const ghost = {
  background: "transparent", color: "#d4af37", border: "1px solid rgba(212,175,55,0.5)",
  fontWeight: 800, padding: "8px 14px", cursor: "pointer",
};
const linkBtn = {
  background: "none", border: "none", color: "#d4af37", fontWeight: 800,
  cursor: "pointer", padding: 0, textDecoration: "underline",
};
const chipBtn = (on) => ({
  background: on ? "#d4af37" : "rgba(0,0,0,0.3)",
  color: on ? "#0a0a0a" : "#e2e8f0",
  border: "1px solid rgba(212,175,55,0.35)",
  fontWeight: 700, fontSize: 11, padding: "4px 8px", cursor: "pointer",
});
