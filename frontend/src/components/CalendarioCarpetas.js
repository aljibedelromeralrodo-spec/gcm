import { useState, useEffect, useCallback } from "react";
import { guardarEstado, leerEstado } from "../utils/navegacion";
import axios from "axios";

const API = process.env.REACT_APP_BACKEND_URL;
const ORO = "#d4af37";
const ROJO_OSCURO = "#7f1d1d";
const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
  "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
const DIAS_SEM = ["LUN", "MAR", "MIÉ", "JUE", "VIE", "SÁB", "DOM"];
const fmt = (n) => Number(n || 0).toLocaleString("es-CL");

const Item = ({ c, rojo, onOpen, onAccion }) => (
  <div data-testid={`cal-carpeta-${c.folder_id}`}
    onClick={() => onOpen && onOpen(c.folder_id)}
    title="Abrir detalle completo de la carpeta"
    onMouseEnter={e => { e.currentTarget.style.background = rojo ? "rgba(127,29,29,0.55)" : "rgba(212,175,55,0.16)"; }}
    onMouseLeave={e => { e.currentTarget.style.background = rojo ? "rgba(127,29,29,0.35)" : "rgba(212,175,55,0.06)"; }}
    style={{
    display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap",
    padding: "0.55rem 0.8rem", marginTop: 6, borderRadius: 0,
    cursor: onOpen ? "pointer" : "default", transition: "background-color 0.15s ease",
    background: rojo ? "rgba(127,29,29,0.35)" : "rgba(212,175,55,0.06)",
    border: rojo ? `1.5px solid ${ROJO_OSCURO}` : "1px solid rgba(212,175,55,0.25)",
    borderLeft: rojo ? `5px solid ${ROJO_OSCURO}` : `5px solid ${ORO}` }}>
    <i className="fa fa-folder" style={{ color: rojo ? "#fca5a5" : ORO }} />
    <b style={{ color: rojo ? "#fecaca" : "var(--white, #fff)", fontSize: 13, textDecoration: onOpen ? "underline" : "none", textDecorationColor: rojo ? "#fca5a5" : `${ORO}88`, textUnderlineOffset: 3 }}>{c.nombre}</b>
    <span style={{ fontFamily: "monospace", fontSize: 11.5, color: rojo ? "#fca5a5" : "#94a3b8" }}>{c.rut || "—"}</span>
    {c.monto_uf && <span style={{ fontSize: 11.5, fontWeight: 800, color: rojo ? "#fecaca" : ORO }}>{fmt(c.monto_uf)} UF</span>}
    {onAccion && (
      <span style={{ display: "inline-flex", gap: 5 }} onClick={e => e.stopPropagation()}>
        {c.descartada ? (
          <>
            <span data-testid={`badge-descartada-${c.folder_id}`} style={{ fontSize: 9.5, fontWeight: 900, letterSpacing: 1,
              padding: "2px 7px", background: "rgba(100,100,100,0.2)", border: "1px solid #64748b", color: "#94a3b8" }}>DESCARTADA</span>
            <button data-testid={`cal-considerar-${c.folder_id}`} onClick={() => onAccion(c.folder_id, "considerar")}
              title="Reactivar la solicitud en el flujo"
              style={{ fontSize: 10, fontWeight: 800, padding: "2px 8px", cursor: "pointer",
                background: "rgba(16,217,142,0.12)", border: "1px solid rgba(16,217,142,0.5)", color: "#10d98e" }}>✓ Considerar</button>
          </>
        ) : (
          <>
            <button data-testid={`cal-considerar-${c.folder_id}`} onClick={() => onAccion(c.folder_id, "considerar")}
              title="Mantener la solicitud activa en el flujo"
              style={{ fontSize: 10, fontWeight: 800, padding: "2px 8px", cursor: "pointer",
                background: "rgba(16,217,142,0.12)", border: "1px solid rgba(16,217,142,0.5)", color: "#10d98e" }}>✓ Considerar</button>
            <button data-testid={`cal-descartar-${c.folder_id}`} onClick={() => onAccion(c.folder_id, "descartar")}
              title="Marcar como no válida: sale del flujo sin eliminarse"
              style={{ fontSize: 10, fontWeight: 800, padding: "2px 8px", cursor: "pointer",
                background: "rgba(225,29,72,0.1)", border: "1px solid rgba(225,29,72,0.5)", color: "#fb7185" }}>✕ Descartar</button>
          </>
        )}
      </span>
    )}
    <span style={{ marginLeft: "auto", fontSize: 10.5, color: rojo ? "#fca5a5" : "#94a3b8" }}>
      Recibida {c.fecha_recepcion}{rojo && c.dias_sin_avance != null ? ` · ${c.dias_sin_avance} día(s) sin avance` : ""}</span>
    {onOpen && <i className="fa fa-external-link" style={{ fontSize: 11, color: rojo ? "#fca5a5" : ORO }} />}
  </div>
);

export default function CalendarioCarpetas({ onOpenFolder }) {
  const hoy = new Date();
  // NORMATIVA DE NAVEGACIÓN: al volver, conservar mes/año/día exactos
  const nav0 = leerEstado("calendario") || {};
  const [anio, setAnio] = useState(nav0.anio ?? hoy.getFullYear());
  const [mesN, setMesN] = useState(nav0.mesN ?? hoy.getMonth());
  const [datos, setDatos] = useState(null);
  const [dia, setDia] = useState(nav0.dia ?? null);
  useEffect(() => { guardarEstado("calendario", { anio, mesN, dia }); }, [anio, mesN, dia]);

  const mesStr = `${anio}-${String(mesN + 1).padStart(2, "0")}`;

  const cargar = useCallback(() => {
    axios.get(`${API}/api/clientes/calendario`, { params: { mes: mesStr } })
      .then(r => setDatos(r.data)).catch(() => setDatos({ dias: {}, total_mes: 0 }));
  }, [mesStr]);
  useEffect(() => { cargar(); setDia(null); }, [cargar]);

  const abrirDia = (fecha) => {
    setDia({ fecha, loading: true });
    axios.get(`${API}/api/clientes/calendario/dia`, { params: { fecha } })
      .then(r => setDia({ ...r.data, loading: false }))
      .catch(() => setDia({ fecha, loading: false, del_dia: [], pendientes_anteriores: [], error: true }));
  };

  const accionCarpeta = async (fid, accion) => {
    if (accion === "descartar" && !window.confirm("¿Descartar esta solicitud?\nSaldrá del flujo y de los contadores, pero NO se elimina y seguirá visible en el histórico.")) return;
    try {
      await axios.post(`${API}/api/clientes/folders/${fid}/${accion}`);
      cargar();
      if (dia?.fecha) abrirDia(dia.fecha);
    } catch (e) { alert(e.response?.data?.detail || "Error al ejecutar la acción"); }
  };

  const mover = (delta) => {
    let m = mesN + delta, a = anio;
    if (m < 0) { m = 11; a -= 1; }
    if (m > 11) { m = 0; a += 1; }
    setMesN(m); setAnio(a);
  };

  const primerDia = new Date(anio, mesN, 1);
  const offset = (primerDia.getDay() + 6) % 7; // lunes = 0
  const diasMes = new Date(anio, mesN + 1, 0).getDate();
  const celdas = [...Array(offset).fill(null), ...Array.from({ length: diasMes }, (_, i) => i + 1)];
  const hoyStr = hoy.toISOString().slice(0, 10);

  return (
    <div data-testid="calendario-carpetas" style={{ background: "#0c0c0c", border: "1px solid rgba(212,175,55,0.25)", padding: "1.2rem 1.4rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
        <button data-testid="cal-mes-prev" onClick={() => mover(-1)} style={{ background: "transparent", border: `1px solid ${ORO}55`, color: ORO, padding: "0.3rem 0.8rem", cursor: "pointer", fontWeight: 800 }}>←</button>
        <h4 style={{ margin: 0, color: ORO, letterSpacing: 2, fontFamily: "Georgia, serif" }}>
          {MESES[mesN].toUpperCase()} {anio}</h4>
        <button data-testid="cal-mes-next" onClick={() => mover(1)} style={{ background: "transparent", border: `1px solid ${ORO}55`, color: ORO, padding: "0.3rem 0.8rem", cursor: "pointer", fontWeight: 800 }}>→</button>
        <span style={{ color: "#8a8a8a", fontSize: "0.72rem", marginLeft: "auto" }}>
          {datos ? `${datos.total_mes} carpeta(s) recibidas en el mes` : "Cargando…"}</span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 4 }}>
        {DIAS_SEM.map(d => (
          <div key={d} style={{ textAlign: "center", color: "#8a8a8a", fontSize: "0.6rem", fontWeight: 800, letterSpacing: 2, padding: "4px 0" }}>{d}</div>
        ))}
        {celdas.map((n, i) => {
          if (!n) return <div key={`v${i}`} />;
          const fecha = `${mesStr}-${String(n).padStart(2, "0")}`;
          const count = datos?.dias?.[fecha] || 0;
          const sel = dia?.fecha === fecha;
          return (
            <button key={fecha} data-testid={`cal-dia-${fecha}`} onClick={() => abrirDia(fecha)}
              style={{ minHeight: 62, cursor: "pointer", padding: "6px 8px", textAlign: "left",
                background: sel ? "rgba(212,175,55,0.16)" : "#0f0f0f",
                border: sel ? `2px solid ${ORO}` : (fecha === hoyStr ? "1.5px dashed rgba(212,175,55,0.6)" : "1px solid rgba(255,255,255,0.07)") }}>
              <div style={{ color: fecha === hoyStr ? ORO : "#c9c4b4", fontWeight: 800, fontSize: 13 }}>{n}</div>
              {count > 0 && (
                <div style={{ marginTop: 4, display: "inline-block", background: "rgba(212,175,55,0.18)",
                  color: ORO, fontWeight: 900, fontSize: 11.5, padding: "1px 8px", border: "1px solid rgba(212,175,55,0.4)" }}>
                  {count}</div>
              )}
            </button>
          );
        })}
      </div>

      {dia && (
        <div data-testid="cal-detalle-dia" style={{ marginTop: 16, borderTop: "1px solid rgba(212,175,55,0.25)", paddingTop: 12 }}>
          <h5 style={{ margin: 0, color: "#e8e3d3", fontSize: "0.85rem" }}>
            📅 {dia.fecha} {dia.loading ? "— cargando…" : `— ${dia.resumen?.del_dia ?? 0} del día · ${dia.resumen?.pendientes ?? 0} pendientes anteriores`}</h5>
          {!dia.loading && (
            <>
              <div style={{ color: ORO, fontSize: "0.62rem", fontWeight: 800, letterSpacing: 2, marginTop: 10 }}>
                CARPETAS DEL DÍA ({(dia.del_dia || []).length})</div>
              {(dia.del_dia || []).map(c => <Item key={c.folder_id} c={c} rojo={false} onOpen={onOpenFolder} onAccion={accionCarpeta} />)}
              {(dia.del_dia || []).length === 0 && <p style={{ color: "#7a7a7a", fontSize: "0.7rem", margin: "4px 0" }}>Sin carpetas recibidas este día.</p>}
              <div style={{ color: "#f87171", fontSize: "0.62rem", fontWeight: 800, letterSpacing: 2, marginTop: 14 }}>
                ⏳ PENDIENTES DE DÍAS ANTERIORES SIN PROCESAR ({(dia.pendientes_anteriores || []).length})</div>
              {(dia.pendientes_anteriores || []).map(c => <Item key={c.folder_id} c={c} rojo={true} onOpen={onOpenFolder} onAccion={accionCarpeta} />)}
              {(dia.pendientes_anteriores || []).length === 0 && <p style={{ color: "#4ade80", fontSize: "0.7rem", margin: "4px 0" }}>Sin carpetas pendientes acumuladas. ✅</p>}
            </>
          )}
        </div>
      )}
      <p style={{ color: "#6a6a6a", fontSize: "0.6rem", marginTop: 12, marginBottom: 0 }}>
        Una carpeta se considera pendiente si no registró avance (mesa, estudio, tasación, faltantes o escrituración) dentro de su día hábil de recepción.
      </p>
    </div>
  );
}
