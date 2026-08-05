import { vipCard, vipTitle, useCarpetasVIP, VipHeader, VipVacio, FechaFmt, Semaforo } from "./TasacionModule";

export default function EscrituraModule({ onNavigate }) {
  const { carpetas, loading, error, reload } = useCarpetasVIP("escrituracion/carpetas");

  const firmaVIP = (c) => {
    sessionStorage.setItem("cm_prefill_firma", JSON.stringify({ nombre: c.nombre, rut: c.rut, folder_id: c.id }));
    if (onNavigate) onNavigate("setcredito");
  };

  return (
    <div style={{ padding: "2rem", maxWidth: "1100px" }} data-testid="escritura-module">
      <VipHeader icon="fa-pencil-square-o" titulo="Escritura" sub="Carpetas en etapa de escrituración · datos directo desde MongoDB y GridFS" total={carpetas.length} testId="escritura-header" />
      <button onClick={reload} data-testid="escritura-reload" style={{ background: "transparent", border: "1px solid rgba(212,175,55,0.5)", color: "#d4af37", borderRadius: 0, padding: "0.5rem 1rem", fontWeight: 700, cursor: "pointer", marginBottom: "1.5rem", fontSize: "0.82rem", fontFamily: "'Inter', sans-serif" }}>
        <i className="fa fa-refresh" style={{ marginRight: 6 }} />Actualizar
      </button>
      {error && <div style={{ color: "#ff6b8a", marginBottom: "1rem", fontWeight: 600 }}>⚠ {error}</div>}
      {loading ? <VipVacio texto="Cargando fichas…" testId="escritura-loading" /> :
        carpetas.length === 0 ? <VipVacio texto="No hay carpetas en escrituración todavía." testId="escritura-vacio" /> :
        carpetas.map((c, i) => (
          <div key={c.id} data-testid={`escritura-ficha-${i}`} style={{ ...vipCard, marginBottom: "1.4rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1.2rem" }}>
              <div>
                <h3 style={vipTitle}>{c.nombre}</h3>
                <div style={{ color: "#d4af37", fontWeight: 700, marginTop: 4, letterSpacing: "1px" }}>{c.rut || "RUT pendiente"}</div>
                <div style={{ fontSize: "0.8rem", opacity: 0.55, color: "#fff", marginTop: 6 }}>
                  En escrituración desde: {FechaFmt(c.movida_at) === "—" ? "fecha no registrada" : FechaFmt(c.movida_at)}
                </div>
                <div style={{ marginTop: "0.7rem" }}>
                  <Semaforo ok={!!c.pdf_disponible} label={c.pdf_disponible ? "Documentos disponibles" : "PDF no disponible (solo alerta)"} testId={`escritura-sem-pdf-${i}`} />
                </div>
              </div>
              <button onClick={() => firmaVIP(c)} data-testid={`escritura-firma-vip-${i}`}
                style={{
                  background: "linear-gradient(120deg, #8a6d1a 0%, #BF953F 18%, #FCF6BA 38%, #d4af37 52%, #B38728 68%, #FBF5B7 85%, #AA771C 100%)",
                  color: "#0a0a0a", fontWeight: 900, border: "none", borderRadius: 0,
                  padding: "1rem 1.8rem", cursor: "pointer", fontSize: "1.02rem", letterSpacing: "1px",
                  fontFamily: "'Inter', sans-serif", textTransform: "uppercase",
                  boxShadow: "0 12px 32px -8px rgba(212,175,55,0.75), inset 0 1px 0 rgba(255,255,255,0.6)",
                }}>
                <i className="fa fa-pencil" style={{ marginRight: 8 }} />🖋 Generar Firma VIP
              </button>
            </div>
          </div>
        ))}
    </div>
  );
}
