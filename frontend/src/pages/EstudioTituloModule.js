import { useState } from "react";
import axios from "axios";
import { vipCard, vipTitle, vipGoldBtn, useCarpetasVIP, VipHeader, VipVacio, FechaFmt, Semaforo } from "./TasacionModule";

const API = process.env.REACT_APP_BACKEND_URL;

export default function EstudioTituloModule() {
  const { carpetas, loading, error, reload } = useCarpetasVIP("estudio-titulo/carpetas");
  const [hilo, setHilo] = useState(null);
  const [cargandoHilo, setCargandoHilo] = useState(false);

  const verHilo = async (c) => {
    setCargandoHilo(true);
    try {
      const r = await axios.get(`${API}/api/estudio-titulo/reparos/${c.id}`);
      setHilo({ carpeta: c, ...r.data });
    } catch (e) { setHilo({ carpeta: c, reparos: { items: [] }, error: e.message }); }
    setCargandoHilo(false);
  };

  return (
    <div style={{ padding: "2rem", maxWidth: "1100px" }} data-testid="estudio-module">
      <VipHeader icon="fa-balance-scale" titulo="Estudio de Títulos" sub="Reparos del abogado en formato de hilo humano · datos directo desde MongoDB" total={carpetas.length} testId="estudio-header" />
      <button onClick={reload} data-testid="estudio-reload" style={{ ...vipGoldBtn, marginBottom: "1.5rem", padding: "0.5rem 1rem", fontSize: "0.82rem" }}>
        <i className="fa fa-refresh" style={{ marginRight: 6 }} />Actualizar
      </button>
      {error && <div style={{ color: "#ff6b8a", marginBottom: "1rem", fontWeight: 600 }}>⚠ {error}</div>}
      {loading ? <VipVacio texto="Cargando fichas…" testId="estudio-loading" /> :
        carpetas.length === 0 ? <VipVacio texto="No hay estudios de título solicitados todavía." testId="estudio-vacio" /> :
        carpetas.map((c, i) => (
          <div key={c.id} data-testid={`estudio-ficha-${i}`} style={{ ...vipCard, marginBottom: "1.4rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem" }}>
              <div>
                <h3 style={vipTitle}>{c.nombre}</h3>
                <div style={{ color: "#d4af37", fontWeight: 700, marginTop: 4, letterSpacing: "1px" }}>{c.rut || "RUT pendiente"} · {c.tipo_vivienda || "vivienda s/d"}</div>
                <div style={{ fontSize: "0.8rem", opacity: 0.55, color: "#fff", marginTop: 6 }}>Solicitado: {FechaFmt(c.solicitado_at)}{c.terminado_at ? ` · Terminado: ${FechaFmt(c.terminado_at)}` : ""}</div>
              </div>
              <div style={{ textAlign: "right" }}>
                <span style={{ display: "inline-block", fontSize: "0.72rem", fontWeight: 700, padding: "0.3rem 0.7rem", letterSpacing: "1px", marginBottom: 8, background: c.reparos_estado === "satisfecho" ? "rgba(16,217,142,0.15)" : c.reparos_estado === "pendiente" ? "rgba(245,158,11,0.15)" : "rgba(255,255,255,0.08)", color: c.reparos_estado === "satisfecho" ? "#10d98e" : c.reparos_estado === "pendiente" ? "#f59e0b" : "#9aa3b5" }}>
                  {c.reparos_estado === "satisfecho" ? "✓ REPAROS RESUELTOS" : c.reparos_estado === "pendiente" ? "⚠ REPAROS PENDIENTES" : "SIN REPAROS"}
                </span><br />
                <button onClick={() => verHilo(c)} data-testid={`estudio-ver-hilo-${i}`} style={{ ...vipGoldBtn, padding: "0.45rem 1rem", fontSize: "0.8rem" }}>
                  <i className="fa fa-comments" style={{ marginRight: 6 }} />{cargandoHilo ? "Cargando…" : "Ver hilo de reparos"}
                </button>
              </div>
            </div>
            <div style={{ marginTop: "0.9rem" }}>
              <Semaforo ok={!!c.pdf_disponible} label={c.pdf_disponible ? "Documentos físicos disponibles" : "PDF no disponible (solo alerta, la ficha carga igual)"} testId={`estudio-sem-pdf-${i}`} />
            </div>
          </div>
        ))}

      {hilo && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.8)", zIndex: 120, display: "flex", alignItems: "center", justifyContent: "center", padding: "2rem" }} onClick={() => setHilo(null)}>
          <div data-testid="estudio-hilo-modal" style={{ ...vipCard, maxWidth: "640px", width: "100%", maxHeight: "85vh", overflow: "auto" }} onClick={e => e.stopPropagation()}>
            <h3 style={{ ...vipTitle, color: "#d4af37", marginBottom: 4 }}>Hilo de reparos — {hilo.carpeta.nombre}</h3>
            <div style={{ fontSize: "0.8rem", opacity: 0.5, color: "#fff", marginBottom: "1.4rem" }}>{hilo.subject || hilo.carpeta.subject || "Estudio de títulos"}</div>
            {(hilo.reparos?.items || []).length === 0 ? (
              <div style={{ color: "#fff", opacity: 0.6, padding: "1rem 0" }}>Sin reparos registrados aún. El abogado todavía no responde con observaciones.</div>
            ) : (hilo.reparos.items).map((it, j) => (
              <div key={j} data-testid={`estudio-reparo-${j}`} style={{ display: "flex", gap: "0.8rem", marginBottom: "1rem", alignItems: "flex-start" }}>
                <div style={{ width: 36, height: 36, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800, fontSize: "0.85rem", background: it.satisfecho ? "rgba(16,217,142,0.2)" : "rgba(212,175,55,0.2)", color: it.satisfecho ? "#10d98e" : "#d4af37", border: `1px solid ${it.satisfecho ? "#10d98e" : "#d4af37"}` }}>
                  {it.satisfecho ? "✓" : it.n}
                </div>
                <div style={{ flex: 1, background: "rgba(255,255,255,0.05)", border: "1px solid rgba(212,175,55,0.2)", padding: "0.8rem 1rem", borderRadius: 0 }}>
                  <div style={{ color: "#fff", fontSize: "0.9rem", lineHeight: 1.55, fontFamily: "'Inter', sans-serif" }}>{it.texto}</div>
                  <div style={{ fontSize: "0.72rem", marginTop: 6, color: it.satisfecho ? "#10d98e" : "#f59e0b", fontWeight: 700 }}>
                    {it.satisfecho ? `Resuelto ${FechaFmt(it.satisfecho_en)}` : "Pendiente de resolución"}
                  </div>
                </div>
              </div>
            ))}
            <button onClick={() => setHilo(null)} style={{ ...vipGoldBtn, marginTop: "0.5rem", padding: "0.5rem 1.2rem", fontSize: "0.85rem" }} data-testid="estudio-hilo-cerrar">Cerrar</button>
          </div>
        </div>
      )}
    </div>
  );
}
