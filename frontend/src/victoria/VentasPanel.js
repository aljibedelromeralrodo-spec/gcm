import { useState, useEffect, useRef } from "react";
import axios from "axios";
import { toast } from "sonner";
import { API_URL } from "../utils/formatters";
import { S, PLAYFAIR } from "./theme";

const KPI = ({ testid, label, value, color }) => (
  <div data-testid={testid} style={{ ...S.card, padding: "1.4rem 1.6rem" }}>
    <div style={S.label}>{label}</div>
    <div style={{ ...S.kpiValue, fontSize: "2.6rem", color: color || "#fff" }}>{value}</div>
  </div>
);

export default function VentasPanel({ ejecutivo, onAbrirCliente }) {
  const [data, setData] = useState(null);
  const [f, setF] = useState({ nombre: "", rut: "", email: "", telefono: "", entrega_inmediata: true });
  const [creando, setCreando] = useState(false);
  const [emailsAviso, setEmailsAviso] = useState("");
  const poll = useRef(null);

  const guardarEmails = async () => {
    try {
      const emails = emailsAviso.split(",").map(x => x.trim()).filter(Boolean);
      const r = await axios.put(`${API_URL}/api/ventas/ejecutivos/${ejecutivo}/avisos-email`, { emails });
      toast.success(`Correos de aviso guardados (${r.data.emails.length})`);
    } catch (e) { toast.error(e.response?.data?.detail || "No se pudieron guardar los correos"); }
  };

  useEffect(() => {
    if (!ejecutivo) return;
    axios.get(`${API_URL}/api/ventas/avisos-email`)
      .then(r => setEmailsAviso((r.data[ejecutivo] || []).join(", ")))
      .catch(() => {});
  }, [ejecutivo]);

  const cargar = () => {
    if (!ejecutivo) return Promise.resolve();
    return axios.get(`${API_URL}/api/ventas/panel/${ejecutivo}`)
      .then(r => setData(r.data))
      .catch(e => toast.error(e.response?.data?.detail || "No se pudo cargar el panel de Ventas"));
  };

  useEffect(() => {
    setData(null);
    if (!ejecutivo) return;
    cargar();
    poll.current = setInterval(cargar, 30000);
    return () => clearInterval(poll.current);
  }, [ejecutivo]); // eslint-disable-line react-hooks/exhaustive-deps

  const hiloFrio = async (c) => {
    if (!window.confirm(`🧊 HILO FRÍO: ¿enviar correo de seguimiento institucional a ${c.nombre} (${c.semaforo?.dias_sin_movimiento} día(s) sin movimiento)?`)) return;
    const pin = window.prompt("🏛 REGLA ORO-75 — Ingrese el PIN maestro para autorizar el envío:") || "";
    if (!pin.trim()) return toast.warning("Envío cancelado: sin PIN maestro no se ejecuta ningún envío (ORO-75)");
    try {
      const r = await axios.post(`${API_URL}/api/ventas/clientes/${c.id}/hilo-frio`, { master_pin: pin });
      toast.success(r.data.mensaje);
      cargar();
    } catch (e) { toast.error(e.response?.data?.detail || "No se pudo enviar el seguimiento"); }
  };

  const crear = async (e) => {
    e.preventDefault();
    setCreando(true);
    try {
      const r = await axios.post(`${API_URL}/api/ventas/solicitudes`, f);
      r.data.asignado ? toast.success(r.data.mensaje) : toast.warning(r.data.mensaje);
      setF({ nombre: "", rut: "", email: "", telefono: "", entrega_inmediata: true });
      cargar();
    } catch (er) { toast.error(er.response?.data?.detail || "No se pudo ingresar la solicitud"); }
    setCreando(false);
  };

  if (!ejecutivo) return (
    <div data-testid="ventas-sin-ejecutivo" style={{ padding: "4rem", textAlign: "center" }}>
      <i className="fa fa-user-circle" style={{ fontSize: "2.4rem", color: "#BF953F" }}></i>
      <div style={{ color: "#e4e4e7", fontSize: "1.2rem", fontWeight: 700, marginTop: 14 }}>Seleccione un ejecutivo de Ventas</div>
      <div style={{ color: "#a1a1aa", fontSize: "0.9rem", marginTop: 8 }}>Use el selector superior para ver el panel de Yerile o Deisy.</div>
    </div>
  );
  if (!data) return <div style={{ padding: "4rem", color: "#a1a1aa", fontSize: "1.1rem" }}>Cargando panel de Ventas…</div>;
  const k = data.kpis;

  return (
    <div data-testid="ventas-panel" style={{ padding: "2.5rem 3rem", maxWidth: 1500, margin: "0 auto" }}>
      <div style={S.label}>Módulo Ventas · Gestión independiente</div>
      <h1 style={{ ...S.h1, margin: "6px 0 24px" }}>Clientes de {data.nombre}</h1>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 18 }}>
        <KPI testid="ventas-kpi-asignados" label="Clientes asignados" value={k.asignados} />
        <KPI testid="ventas-kpi-incompletos" label="Con documentación incompleta" value={k.incompletos} color={k.incompletos > 0 ? "#f59e0b" : "#4ade80"} />
        <KPI testid="ventas-kpi-completos" label="Documentación completa" value={k.completos} color="#4ade80" />
        <KPI testid="ventas-kpi-faltantes" label="Documentos faltantes en total" value={k.faltantes_total} color={k.faltantes_total > 0 ? "#f87171" : "#4ade80"} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 22, marginTop: 22, alignItems: "start" }}>
        <div style={{ ...S.card, padding: "1.8rem 2rem" }}>
          <h2 style={{ ...S.h2, marginBottom: 12 }}>Mis clientes asignados ({data.clientes.length})</h2>
          {data.clientes.length === 0 && <p style={{ ...S.body, color: "#71717a" }}>
            Aún no tiene clientes asignados: llegarán en turno alternado cuando entren solicitudes con documentación incompleta y entrega inmediata.</p>}
          {data.clientes.map(c => (
            <div key={c.id} data-testid={`ventas-cliente-${c.id}`} style={{ borderTop: "1px solid rgba(255,255,255,0.08)", padding: "1rem 0", display: "flex", justifyContent: "space-between", gap: 14, flexWrap: "wrap", alignItems: "center" }}>
              <div style={{ flex: "1 1 320px" }}>
                <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                  <span style={{ fontFamily: PLAYFAIR, fontSize: "1.2rem", fontWeight: 700, color: "#fff" }}>{c.nombre}</span>
                  <span style={S.pill(c.docs_completos ? "rgba(34,197,94,0.15)" : "rgba(245,158,11,0.15)",
                    c.docs_completos ? "#4ade80" : "#f59e0b")}>
                    {c.docs_completos ? "DOCUMENTACIÓN COMPLETA" : `FALTAN ${c.faltantes.length} DOCUMENTO(S)`}</span>
                  <span style={S.pill("rgba(255,255,255,0.08)", "#d4d4d8")}>{c.estado_etiqueta?.toUpperCase()}</span>
                </div>
                <div style={{ color: "#a1a1aa", fontSize: "0.9rem", marginTop: 5 }}>
                  RUT {c.rut || "—"} · asignado {String(c.asignado_en || "").slice(0, 10)} · {c.dias_gestion} día(s) en gestión
                  {c.ultimo_contacto
                    ? <> · último contacto: {c.ultimo_contacto.canal} {String(c.ultimo_contacto.fecha || "").slice(0, 10)}</>
                    : <b style={{ color: "#f87171" }}> · sin contactos registrados</b>}
                </div>
                {!c.docs_completos && <div style={{ color: "#f59e0b", fontSize: "0.9rem", marginTop: 4 }}>Faltan: {c.faltantes.join(", ")}</div>}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-end" }}>
                {c.hilo_frio && (
                  <button data-testid={`ventas-hilo-frio-${c.id}`} onClick={() => hiloFrio(c)}
                    style={{ background: "rgba(56,189,248,0.1)", color: "#7dd3fc", border: "1px solid rgba(56,189,248,0.45)", borderRadius: 8, padding: "0.55rem 1.1rem", fontWeight: 800, cursor: "pointer", fontSize: "0.8rem" }}>
                    🧊 Hilo Frío · {c.semaforo?.dias_sin_movimiento} días inactivo → enviar seguimiento</button>
                )}
                <button data-testid={`ventas-abrir-${c.id}`} onClick={() => onAbrirCliente(c)}
                  style={{ ...S.btnGold, ...S.btnSmall, padding: "0.7rem 1.3rem" }}>Abrir ficha y gestión del cliente →</button>
              </div>
            </div>
          ))}
        </div>

        <form onSubmit={crear} style={{ ...S.card, padding: "1.8rem 2rem", display: "flex", flexDirection: "column", gap: 12 }}>
          <h2 style={{ ...S.h2, margin: 0 }}>Ingresar solicitud de crédito</h2>
          <p style={{ ...S.body, fontSize: "0.88rem", color: "#a1a1aa", margin: 0 }}>
            Se asigna en turno alternado solo si cumple: documentación incompleta + entrega inmediata.</p>
          <input data-testid="ventas-sol-nombre" style={S.input} placeholder="Nombre completo del solicitante" required
            value={f.nombre} onChange={e => setF(s => ({ ...s, nombre: e.target.value }))} />
          <input data-testid="ventas-sol-rut" style={S.input} placeholder="RUT (ej: 12.345.678-9)" required
            value={f.rut} onChange={e => setF(s => ({ ...s, rut: e.target.value }))} />
          <input data-testid="ventas-sol-email" style={S.input} placeholder="Correo (opcional)"
            value={f.email} onChange={e => setF(s => ({ ...s, email: e.target.value }))} />
          <input data-testid="ventas-sol-telefono" style={S.input} placeholder="Teléfono (opcional)"
            value={f.telefono} onChange={e => setF(s => ({ ...s, telefono: e.target.value }))} />
          <label style={{ display: "flex", gap: 10, alignItems: "center", cursor: "pointer", color: "#FCF6BA", fontWeight: 700, fontSize: "0.95rem" }}>
            <input type="checkbox" data-testid="ventas-sol-inmediata" checked={f.entrega_inmediata}
              onChange={e => setF(s => ({ ...s, entrega_inmediata: e.target.checked }))}
              style={{ width: 20, height: 20, accentColor: "#BF953F" }} />
            La propiedad es de entrega inmediata</label>
          <button type="submit" data-testid="ventas-sol-crear" disabled={creando} style={S.btnGold}>
            {creando ? "Ingresando…" : "Ingresar solicitud y asignar automáticamente"}</button>

          <div style={{ borderTop: "1px solid rgba(255,255,255,0.1)", paddingTop: 14, marginTop: 6 }}>
            <div style={S.label}>Mis correos para avisos del sistema de gestión</div>
            <p style={{ ...S.body, fontSize: "0.82rem", color: "#a1a1aa", margin: "6px 0 8px" }}>
              Los avisos se asignan de forma aleatoria entre las ejecutivas y llegan a estos correos (separe con coma).</p>
            <input data-testid="ventas-emails-aviso" style={S.input} placeholder="correo1@dominio.cl, correo2@dominio.cl"
              value={emailsAviso} onChange={e => setEmailsAviso(e.target.value)} />
            <button type="button" data-testid="ventas-emails-guardar" onClick={guardarEmails}
              style={{ ...S.btnLine, ...S.btnSmall, marginTop: 8 }}>Guardar mis correos de aviso</button>
          </div>
        </form>
      </div>
    </div>
  );
}
