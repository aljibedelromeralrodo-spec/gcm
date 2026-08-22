import { useState, useEffect } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";

const GOLD = "#d4af37";
const PLAYFAIR = "'Playfair Display', Georgia, serif";
const card = { background: "#0d0d0d", border: "1px solid rgba(212,175,55,0.35)", borderRadius: 8, padding: "1.4rem 1.6rem" };
const label = { color: "#8a8a8a", fontSize: "0.68rem", letterSpacing: 2, textTransform: "uppercase", fontWeight: 700 };
const SEM = { verde: "#4ade80", amarillo: "#facc15", rojo: "#f87171", cerrado: "#71717a" };
const SEM_TXT = { verde: "Activo", amarillo: "Sin movimiento 3+ días", rojo: "Paralizado 5+ días", cerrado: "Cerrado" };

const Dot = ({ color }) => <span style={{ display: "inline-block", width: 12, height: 12, borderRadius: "50%",
  background: SEM[color] || "#71717a", boxShadow: `0 0 8px ${SEM[color] || "#333"}` }} />;

function Timeline({ cid, nombre, onCerrar }) {
  const [ev, setEv] = useState(null);
  useEffect(() => {
    axios.get(`${API_URL}/api/ventas/clientes/${cid}/timeline`).then(r => setEv(r.data.eventos)).catch(() => setEv([]));
  }, [cid]);
  return (
    <div data-testid="ventas-timeline-modal" onClick={onCerrar} style={{ position: "fixed", inset: 0, zIndex: 300,
      background: "rgba(0,0,0,0.85)", display: "flex", alignItems: "center", justifyContent: "center", padding: 30 }}>
      <div onClick={e => e.stopPropagation()} style={{ ...card, background: "#111", maxWidth: 680, width: "100%", maxHeight: "85vh", overflow: "auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <div style={{ color: GOLD, fontWeight: 800, fontFamily: PLAYFAIR, fontSize: "1.15rem" }}>Línea de tiempo — {nombre}</div>
          <button data-testid="ventas-timeline-cerrar" onClick={onCerrar} style={{ background: "transparent", border: "1px solid #555", color: "#d4d4d8", borderRadius: 5, padding: "0.35rem 0.8rem", cursor: "pointer" }}>✕</button>
        </div>
        {!ev && <div style={{ color: "#a1a1aa" }}>Cargando trazabilidad…</div>}
        {ev && ev.length === 0 && <div style={{ color: "#71717a" }}>Sin acciones registradas.</div>}
        {ev && ev.map((e, i) => (
          <div key={i} style={{ display: "flex", gap: 14, borderLeft: `2px solid ${GOLD}`, marginLeft: 6, paddingLeft: 16, paddingBottom: 16, position: "relative" }}>
            <span style={{ position: "absolute", left: -6, top: 2, width: 10, height: 10, borderRadius: "50%", background: GOLD }} />
            <div>
              <div style={{ color: "#a1a1aa", fontSize: "0.72rem", fontFamily: "monospace" }}>
                {String(e.fecha || "").slice(0, 16).replace("T", " · ")} — {e.por || "sistema"}</div>
              <div style={{ color: "#e4e4e7", fontSize: "0.9rem", marginTop: 2 }}>{e.accion}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function VentasReporte() {
  const [rep, setRep] = useState(null);
  const [rend, setRend] = useState(null);
  const [emb, setEmb] = useState(null);
  const [tl, setTl] = useState(null);
  const [filtros, setFiltros] = useState({ ejecutivo: "", desde: "", hasta: "", estado: "", resultado: "" });

  useEffect(() => {
    const cargar = () => {
      axios.get(`${API_URL}/api/ventas/reporte`).then(r => setRep(r.data)).catch(() => {});
      axios.get(`${API_URL}/api/ventas/rendimiento`).then(r => setRend(r.data)).catch(() => {});
      axios.get(`${API_URL}/api/ventas/embudo`).then(r => setEmb(r.data)).catch(() => {});
    };
    cargar();
    const t = setInterval(cargar, 30000);
    return () => clearInterval(t);
  }, []);

  const exportar = async () => {
    const params = Object.fromEntries(Object.entries(filtros).filter(([, v]) => v));
    const r = await axios.get(`${API_URL}/api/ventas/export`, { params, responseType: "blob" });
    const url = URL.createObjectURL(r.data);
    const a = document.createElement("a");
    a.href = url; a.download = `Ventas_CentralMutuos_${new Date().toISOString().slice(0, 10)}.xlsx`;
    a.click(); URL.revokeObjectURL(url);
  };

  if (!rep) return <div style={{ color: "#a1a1aa", padding: "1rem" }}>Cargando el Módulo Ventas…</div>;
  const maxEmb = emb ? Math.max(1, ...emb.embudo.map(e => e.total)) : 1;

  return (
    <div data-testid="ventas-reporte" style={{ marginTop: 14, background: "#0a0a0a", borderRadius: 10, padding: "1.6rem 1.8rem", border: "1px solid rgba(212,175,55,0.25)" }}>
      <div style={{ fontFamily: PLAYFAIR, color: GOLD, fontWeight: 800, fontSize: "1.25rem", letterSpacing: 1, marginBottom: 4 }}>
        MÓDULO VENTAS — Dirección Comercial</div>
      <div style={{ color: "#8a8a8a", fontSize: "0.78rem", marginBottom: 18 }}>
        Balance de carga inteligente · semáforo de urgencia · trazabilidad completa</div>

      {rend && (
        <div data-testid="ventas-rendimiento" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
          {Object.entries(rend.ejecutivos).map(([ej, e]) => (
            <div key={ej} data-testid={`rendimiento-${ej}`} style={card}>
              <div style={{ fontFamily: PLAYFAIR, color: "#fff", fontWeight: 800, fontSize: "1.1rem", marginBottom: 12 }}>{e.nombre}</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                {[["Clientes activos", e.activos, "#fff"], ["Cerrados este mes", e.cerrados_mes, "#FCF6BA"],
                  ["Tasa de conversión", `${e.tasa_conversion}%`, e.tasa_conversion >= 50 ? "#4ade80" : "#facc15"],
                  ["Días promedio a cierre", e.dias_promedio_cierre, "#fff"]].map(([et, v, c]) => (
                  <div key={et}>
                    <div style={label}>{et}</div>
                    <div style={{ fontFamily: PLAYFAIR, fontSize: "1.9rem", fontWeight: 700, color: c }}>{v}</div>
                  </div>
                ))}
              </div>
              <div style={{ display: "flex", gap: 14, marginTop: 10, alignItems: "center" }}>
                <span style={{ ...label, margin: 0 }}>Urgencias:</span>
                <span style={{ color: SEM.verde, fontSize: "0.8rem", fontWeight: 700 }}>● {e.semaforos.verde}</span>
                <span style={{ color: SEM.amarillo, fontSize: "0.8rem", fontWeight: 700 }}>● {e.semaforos.amarillo}</span>
                <span style={{ color: SEM.rojo, fontSize: "0.8rem", fontWeight: 700 }}>● {e.semaforos.rojo}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {emb && (
        <div data-testid="ventas-embudo" style={{ ...card, marginBottom: 20 }}>
          <div style={{ ...label, marginBottom: 12 }}>Embudo de ventas · {emb.total} cliente(s)</div>
          {emb.embudo.map(e => (
            <div key={e.etapa} data-testid={`embudo-${e.etapa}`} style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
              <span style={{ flex: "0 0 210px", color: "#e4e4e7", fontSize: "0.85rem", fontWeight: 700 }}>{e.etiqueta}</span>
              <div style={{ flex: 1, height: 22, background: "rgba(255,255,255,0.06)", borderRadius: 4, overflow: "hidden" }}>
                <div style={{ width: `${(e.total / maxEmb) * 100}%`, height: "100%", minWidth: e.total ? 24 : 0,
                  background: e.etapa === "aprobado" ? "linear-gradient(90deg,#166534,#4ade80)"
                    : e.etapa === "rechazado" ? "linear-gradient(90deg,#7f1d1d,#f87171)"
                    : "linear-gradient(90deg,#8a6d1a,#d4af37)",
                  display: "flex", alignItems: "center", justifyContent: "flex-end", paddingRight: 8,
                  color: "#0a0a0a", fontWeight: 800, fontSize: "0.78rem", transition: "width 0.6s ease" }}>
                  {e.total || ""}</div>
              </div>
              <span style={{ color: "#71717a", fontSize: "0.72rem", flex: "0 0 120px" }}>
                {Object.entries(e.por_ejecutivo).map(([k, n]) => `${emb.ejecutivos[k].split(" ")[0]}: ${n}`).join(" · ")}</span>
            </div>
          ))}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
        {Object.entries(rep.ejecutivos).map(([ej, e]) => (
          <div key={ej} data-testid={`reporte-ejecutivo-${ej}`} style={card}>
            <div style={{ color: "#fff", fontWeight: 800, marginBottom: 8 }}>{e.nombre} — cartera con semáforo de urgencia</div>
            {e.clientes.length === 0 && <div style={{ color: "#71717a", fontSize: "0.8rem" }}>Sin clientes asignados.</div>}
            {e.clientes.map(c => (
              <div key={c.id} data-testid={`semaforo-cliente-${c.id}`} style={{ borderTop: "1px solid rgba(255,255,255,0.08)", padding: "0.6rem 0", display: "flex", justifyContent: "space-between", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                  <Dot color={c.semaforo?.color} />
                  <div>
                    <span style={{ color: "#fff", fontWeight: 700, fontSize: "0.85rem" }}>{c.nombre}</span>
                    <div style={{ color: "#8a8a8a", fontSize: "0.72rem" }}>
                      {SEM_TXT[c.semaforo?.color]} {c.semaforo?.color !== "verde" && c.semaforo?.color !== "cerrado" ? `(${c.semaforo?.dias_sin_movimiento} días)` : ""} · {c.estado_etiqueta}</div>
                  </div>
                </div>
                <button data-testid={`ver-timeline-${c.id}`} onClick={() => setTl({ cid: c.id, nombre: c.nombre })}
                  style={{ background: "transparent", border: `1px solid ${GOLD}`, color: GOLD, borderRadius: 5,
                    padding: "0.35rem 0.8rem", cursor: "pointer", fontSize: "0.72rem", fontWeight: 700 }}>Línea de tiempo</button>
              </div>
            ))}
          </div>
        ))}
      </div>

      <div data-testid="ventas-export" style={card}>
        <div style={{ ...label, marginBottom: 10 }}>Exportación a Excel — filtros</div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
          <select data-testid="export-ejecutivo" value={filtros.ejecutivo} onChange={e => setFiltros(f => ({ ...f, ejecutivo: e.target.value }))}
            style={{ background: "#141414", color: "#e4e4e7", border: "1px solid rgba(212,175,55,0.4)", borderRadius: 5, padding: "0.5rem 0.7rem" }}>
            <option value="">Todas las ejecutivas</option>
            <option value="yerile">Yerile Barrera</option>
            <option value="deysi">Deisy Salazar</option>
          </select>
          <input type="date" data-testid="export-desde" value={filtros.desde} onChange={e => setFiltros(f => ({ ...f, desde: e.target.value }))}
            style={{ background: "#141414", color: "#e4e4e7", border: "1px solid rgba(212,175,55,0.4)", borderRadius: 5, padding: "0.45rem 0.7rem" }} />
          <input type="date" data-testid="export-hasta" value={filtros.hasta} onChange={e => setFiltros(f => ({ ...f, hasta: e.target.value }))}
            style={{ background: "#141414", color: "#e4e4e7", border: "1px solid rgba(212,175,55,0.4)", borderRadius: 5, padding: "0.45rem 0.7rem" }} />
          <select data-testid="export-resultado" value={filtros.resultado} onChange={e => setFiltros(f => ({ ...f, resultado: e.target.value }))}
            style={{ background: "#141414", color: "#e4e4e7", border: "1px solid rgba(212,175,55,0.4)", borderRadius: 5, padding: "0.5rem 0.7rem" }}>
            <option value="">Todos los resultados</option>
            <option value="abierto">En gestión (abiertos)</option>
            <option value="aprobado">Aprobados</option>
            <option value="rechazado">Rechazados</option>
          </select>
          <button data-testid="export-descargar" onClick={exportar}
            style={{ background: "linear-gradient(90deg,#8a6d1a,#d4af37)", color: "#0a0a0a", fontWeight: 800,
              border: "none", borderRadius: 5, padding: "0.55rem 1.3rem", cursor: "pointer", letterSpacing: 1 }}>
            ⬇ Descargar Excel</button>
        </div>
      </div>

      {tl && <Timeline cid={tl.cid} nombre={tl.nombre} onCerrar={() => setTl(null)} />}
    </div>
  );
}
