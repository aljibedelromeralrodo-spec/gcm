import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { API_URL } from "../utils/formatters";
import { S, GOLD, PLAYFAIR } from "./theme";
import PreviewFlotante from "./PreviewFlotante";
import AuditoriaCampos from "./AuditoriaCampos";

const V_COLOR = { true: "#4ade80", false: "#f87171", null: "#f59e0b" };
const TRAZABLES = ["rut_titular", "rut_codeudor", "rol_avaluo", "direccion_propiedad", "nombre_cliente"];

export default function MutuosFicha({ oid, etapa, onSetEtapa, onVolver }) {
  const [det, setDet] = useState(null);
  const [datos, setDatos] = useState({});
  const [traz, setTraz] = useState(null);
  const [autorizando, setAutorizando] = useState(false);
  const [confirmo, setConfirmo] = useState(false);

  const cargar = useCallback(() => {
    axios.get(`${API_URL}/api/mutuos/operaciones/${oid}`)
      .then(r => setDet(r.data))
      .catch(e => toast.error(e.response?.data?.detail || "No se pudo cargar la operación"));
  }, [oid]);
  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => {
    if (det) setDatos((det.operacion.etapas[String(etapa)] || {}).datos || {});
    setConfirmo(false); setAutorizando(false);
  }, [det, etapa]);

  const guardar = async () => {
    try {
      const r = await axios.put(`${API_URL}/api/mutuos/operaciones/${oid}/etapa/${etapa}`, { datos });
      setDet(r.data.detalle);
      toast.success(`Etapa ${etapa} guardada y re-validada contra la bóveda`);
    } catch (e) { toast.error(e.response?.data?.detail || "No se pudo guardar la etapa"); }
  };

  const autorizar = async () => {
    try {
      const r = await axios.post(`${API_URL}/api/mutuos/operaciones/${oid}/autorizar/${etapa}`, { confirmado: true });
      setDet(r.data.detalle);
      toast.success(r.data.mensaje);
      setAutorizando(false);
      if (etapa < 6) onSetEtapa(etapa + 1);
    } catch (e) { toast.error(e.response?.data?.detail || "Autorización rechazada"); }
  };

  const copiarCarga = async () => {
    const sec = det?.carga_concreces?.secciones;
    if (!sec) { toast.error("Aún no hay expediente consolidado para copiar"); return; }
    try {
      await navigator.clipboard.writeText(JSON.stringify(sec, null, 2));
      toast.success("Datos copiados para pegar en Concreces. No se envió nada.");
    } catch (_e) { toast.error("No se pudo copiar al portapapeles"); }
  };

  const enviarRiesgo = async () => {
    try {
      const r = await axios.post(`${API_URL}/api/mutuos/operaciones/${oid}/enviar-riesgo`, { confirmado: true });
      toast.success(r.data.mensaje);
      cargar();
    } catch (e) { toast.error(e.response?.data?.detail || "El envío fue bloqueado"); }
  };

  const verOrigen = async (campo) => {
    try {
      const r = await axios.get(`${API_URL}/api/victoria/clientes/${det.cliente.id}/origen-dato/${campo}`);
      setTraz(r.data);
    } catch (e) { toast.error(e.response?.data?.detail || "No hay documento de origen para este dato"); }
  };

  if (!det) return <div style={{ padding: "4rem", color: "#a1a1aa", fontSize: "1.1rem" }}>Cargando operación…</div>;
  const op = det.operacion;
  const eg = det.etapas_guia[etapa - 1];
  const etapaData = op.etapas[String(etapa)] || {};
  const enviada = op.estado === "enviada_riesgo";

  return (
    <div data-testid="mutuos-ficha" style={{ padding: "2.5rem 3rem", maxWidth: 1500, margin: "0 auto" }}>
      <button data-testid="mutuos-btn-volver" onClick={onVolver} style={{ ...S.btnLine, ...S.btnSmall, marginBottom: 18 }}>
        ← Volver al panel de operaciones (conserva su posición)</button>

      <AuditoriaCampos clienteId={det.cliente?.id} />

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: 14 }}>
        <div>
          <div style={S.label}>Operación #{op.numero} · Guía de Usuario Mutuos</div>
          <h1 style={{ ...S.h1, marginTop: 6 }} data-testid="mutuos-ficha-cliente">{det.cliente?.nombre}</h1>
          <div style={{ color: "#a1a1aa", fontSize: "0.98rem", marginTop: 6 }}>
            RUT {det.cliente?.rut || "—"} · creada {String(op.creado || "").slice(0, 10)} · autocompletado desde bóveda y expediente único</div>
        </div>
        <span data-testid="mutuos-estado" style={{ ...S.pill(enviada ? "rgba(34,197,94,0.15)" : "rgba(212,175,55,0.18)",
          enviada ? "#4ade80" : "#FCF6BA"), fontSize: "0.95rem", padding: "0.5rem 1.2rem" }}>
          {enviada ? "ENVIADA A REVISIÓN DE RIESGO" : `EN PROCESO — ETAPA ${op.etapa_actual} DE 6`}</span>
      </div>

      {/* Validaciones irrenunciables con trazabilidad clic-origen */}
      <div data-testid="mutuos-validaciones" style={{ ...S.card, padding: "1.3rem 1.7rem", marginTop: 20 }}>
        <div style={S.label}>Validaciones irrenunciables (contra los documentos de la bóveda) — clic en un dato abre su documento de origen</div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 10 }}>
          {det.validaciones.map((v, i) => (
            <button key={i} data-testid={`mutuos-val-${v.campo}`}
              onClick={() => TRAZABLES.includes(v.campo) && verOrigen(v.campo)}
              title={TRAZABLES.includes(v.campo) ? "Clic: ver el documento físico de origen" : v.etiqueta}
              style={{ background: "rgba(255,255,255,0.04)", border: `1px solid ${V_COLOR[String(v.ok)]}55`,
                borderRadius: 4, padding: "0.6rem 0.9rem", textAlign: "left",
                cursor: TRAZABLES.includes(v.campo) ? "pointer" : "default" }}>
              <span style={{ color: V_COLOR[String(v.ok)], fontWeight: 800, fontSize: "0.9rem" }}>
                {v.ok === true ? "✓" : v.ok === false ? "✕" : "⏳"} {v.etiqueta}</span>
              <div style={{ color: "#a1a1aa", fontSize: "0.8rem", marginTop: 3,
                borderBottom: TRAZABLES.includes(v.campo) ? "1.5px dashed #b08d2a" : "none", display: "inline-block" }}>
                {v.ingresado || "—"} {v.documento && v.campo !== "deuda_garantia" ? `· doc: ${v.documento}` : v.campo === "deuda_garantia" ? `(${v.documento})` : ""} {TRAZABLES.includes(v.campo) ? "🔍" : ""}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Stepper 6 etapas de la guía */}
      <div data-testid="mutuos-stepper" style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 10, margin: "20px 0" }}>
        {det.etapas_guia.map(e => {
          const aut = (op.etapas[String(e.n)] || {}).autorizada;
          return (
            <button key={e.n} data-testid={`mutuos-etapa-${e.n}`} onClick={() => onSetEtapa(e.n)}
              style={{ textAlign: "left", cursor: "pointer", borderRadius: 4, padding: "0.8rem 1rem",
                background: etapa === e.n ? "rgba(212,175,55,0.12)" : "#141414",
                border: `1px solid ${etapa === e.n ? GOLD : aut ? "rgba(34,197,94,0.4)" : "rgba(255,255,255,0.1)"}` }}>
              <div style={{ fontFamily: PLAYFAIR, fontSize: "1.3rem", fontWeight: 700,
                color: aut ? "#4ade80" : etapa === e.n ? "#FCF6BA" : "#52525b" }}>{aut ? "✓" : e.n}</div>
              <div style={{ fontSize: "0.72rem", fontWeight: 700, color: etapa === e.n ? "#fff" : "#a1a1aa", marginTop: 3, lineHeight: 1.3 }}>
                {e.titulo.split("— ")[1]}</div>
            </button>
          );
        })}
      </div>

      <div style={{ ...S.card, padding: "1.8rem 2rem" }}>
        <h2 style={{ ...S.h2, fontSize: "1.5rem" }} data-testid="mutuos-titulo-etapa">{eg.titulo}</h2>
        <p style={{ ...S.body, fontSize: "0.98rem", color: "#a1a1aa", margin: "8px 0 18px" }}>{eg.descripcion}</p>

        {etapa < 6 ? (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 14 }}>
              {eg.campos.map(([k, et]) => (
                <div key={k}>
                  <label style={{ ...S.label, fontSize: "0.72rem", display: "flex", alignItems: "center", gap: 6 }}>
                    {et}{TRAZABLES.includes(k) && !enviada && (
                      <span onClick={() => verOrigen(k)} title="Ver el documento de origen de este dato"
                        style={{ cursor: "pointer", borderBottom: "1.5px dashed #b08d2a" }}>🔍</span>)}
                  </label>
                  <input data-testid={`mutuos-campo-${k}`} style={{ ...S.input, marginTop: 4 }} disabled={enviada}
                    value={datos[k] || ""} onChange={e => setDatos(s => ({ ...s, [k]: e.target.value }))} />
                </div>
              ))}
            </div>
            {!enviada && (
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 20 }}>
                <button data-testid="mutuos-guardar-etapa" onClick={guardar} style={S.btnLine}>
                  Guardar los datos de esta etapa y re-validar</button>
                {!etapaData.autorizada ? (
                  <button data-testid="mutuos-abrir-autorizacion" onClick={() => setAutorizando(true)} style={S.btnGold}>
                    Revisar y autorizar la {eg.titulo.split("— ")[1]} para continuar</button>
                ) : (
                  <span style={{ ...S.pill("rgba(34,197,94,0.15)", "#4ade80"), alignSelf: "center" }}>
                    ✓ ETAPA AUTORIZADA POR VICTORIA {String(etapaData.autorizada_en || "").slice(0, 10)}</span>
                )}
              </div>
            )}
          </>
        ) : (
          <div data-testid="mutuos-etapa6">
            {[1, 2, 3, 4, 5].map(n => {
              const aut = (op.etapas[String(n)] || {}).autorizada;
              return (
                <div key={n} style={{ display: "flex", gap: 12, alignItems: "center", padding: "0.6rem 0", borderTop: "1px solid rgba(255,255,255,0.08)" }}>
                  <span style={{ fontSize: "1.2rem", color: aut ? "#4ade80" : "#f87171" }}>{aut ? "✓" : "✕"}</span>
                  <span style={{ ...S.body }}>{det.etapas_guia[n - 1].titulo} {aut ? "— autorizada" : "— PENDIENTE de autorización"}</span>
                </div>
              );
            })}
            <div style={{ display: "flex", gap: 12, alignItems: "center", padding: "0.6rem 0", borderTop: "1px solid rgba(255,255,255,0.08)" }}>
              <span style={{ fontSize: "1.2rem", color: det.validaciones.every(v => v.ok !== false) ? "#4ade80" : "#f87171" }}>
                {det.validaciones.every(v => v.ok !== false) ? "✓" : "✕"}</span>
              <span style={S.body}>Validaciones irrenunciables sin conflictos</span>
            </div>
            {enviada ? (
              <>
                <div data-testid="mutuos-enviada" style={{ marginTop: 18, color: "#4ade80", fontWeight: 800, fontSize: "1.2rem" }}>
                  ✓ Operación #{op.numero} enviada a revisión de riesgo el {String(op.enviada_en || "").slice(0, 16).replace("T", " ")} UTC</div>
                <button data-testid="mutuos-copiar-carga" onClick={copiarCarga} style={{ ...S.btnLine, marginTop: 16, width: "100%" }}>
                  Copiar datos del expediente para pegar en Concreces (sin envío)</button>
              </>
            ) : (
              <>
                <label style={{ display: "flex", gap: 12, alignItems: "flex-start", marginTop: 18, cursor: "pointer" }}>
                  <input type="checkbox" data-testid="mutuos-check-final" checked={confirmo}
                    onChange={e => setConfirmo(e.target.checked)} style={{ width: 22, height: 22, accentColor: GOLD, marginTop: 2 }} />
                  <span style={{ ...S.body }}>Declaro que revisé todas las etapas, las validaciones están aprobadas
                    y autorizo el envío de esta operación a revisión de riesgo en ConCreces.</span>
                </label>
                <button data-testid="mutuos-copiar-carga" onClick={copiarCarga} style={{ ...S.btnLine, marginTop: 16, width: "100%" }}>
                  Copiar datos del expediente para pegar en Concreces (sin envío)</button>
                <button data-testid="mutuos-enviar-riesgo" onClick={enviarRiesgo} disabled={!confirmo || !det.lista_para_riesgo}
                  style={{ ...S.btnGold, marginTop: 12, width: "100%", padding: "1.1rem", fontSize: "1.05rem",
                    opacity: (!confirmo || !det.lista_para_riesgo) ? 0.35 : 1 }}>
                  Confirmar envío de la operación #{op.numero} a revisión de riesgo en ConCreces</button>
              </>
            )}
          </div>
        )}
      </div>

      {autorizando && (
        <div data-testid="mutuos-modal-autorizacion" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.82)", zIndex: 120, display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
          <div style={{ background: "#141414", border: "1px solid rgba(212,175,55,0.5)", borderRadius: 4, padding: "1.8rem", width: "100%", maxWidth: 560 }}>
            <h3 style={{ color: "#FCF6BA", margin: 0, fontFamily: PLAYFAIR, fontSize: "1.2rem" }}>Pantalla de autorización — {eg.titulo}</h3>
            <p style={{ ...S.body, fontSize: "0.95rem", marginTop: 10 }}>Revise los datos ingresados:</p>
            {eg.campos.map(([k, et]) => (
              <div key={k} style={{ display: "flex", justifyContent: "space-between", gap: 10, padding: "0.4rem 0", borderTop: "1px solid rgba(255,255,255,0.07)" }}>
                <span style={{ color: "#a1a1aa", fontSize: "0.85rem" }}>{et}</span>
                <b style={{ color: "#fff", fontSize: "0.9rem" }}>{datos[k] || "—"}</b>
              </div>
            ))}
            <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
              <button data-testid="mutuos-confirmar-autorizacion" onClick={autorizar} style={{ ...S.btnGold, flex: 1 }}>
                Autorizo esta etapa: los datos están revisados y correctos</button>
              <button data-testid="mutuos-cancelar-autorizacion" onClick={() => setAutorizando(false)} style={S.btnLine}>
                Aún no: seguir revisando</button>
            </div>
          </div>
        </div>
      )}

      {traz && <PreviewFlotante info={traz} onClose={() => setTraz(null)} />}
    </div>
  );
}
