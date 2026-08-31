// Corte 10: botón de reparos del abogado en la tarjeta (con lógica: abre el modal de reparos)
const ReparosAbogado = ({ f, openReparos }) => (
  <>
  {((f.reparos_alertas || []).length + ((f.estudio_reparos || {}).items || []).length) > 0 && (
    <button data-testid={`reparos-btn-${f.id}`}
      onClick={(ev) => { ev.stopPropagation(); openReparos(f); }}
      title="Reparos del abogado — pinche para leer el texto íntegro"
      style={{ cursor: "pointer", border: "none", borderRadius: 8, fontWeight: 800,
        fontSize: 10, padding: "2px 7px", background: "rgba(239,68,68,0.18)", color: "#ef4444" }}>
      ⚠️ {(f.reparos_alertas || []).length + ((f.estudio_reparos || {}).items || []).length} reparo(s)
    </button>
  )}
  </>
);

export default ReparosAbogado;
