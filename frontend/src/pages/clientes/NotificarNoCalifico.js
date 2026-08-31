// Corte 12 (autopiloto): badge NO CALIFICÓ + notificación al ejecutivo
const NotificarNoCalifico = ({ f, evalNeg, notificandoNC, notificarNoCalifico }) => (
  <>
  {evalNeg[f.id] && (
    <>
      <span data-testid={`no-califico-${f.id}`}
        title={`Última evaluación del Motor (${evalNeg[f.id].fecha}): resultado negativo`}
        style={{ background: "#7f1d1d", color: "#fecaca", fontWeight: 900, fontSize: 10,
          letterSpacing: 1, padding: "2px 9px", border: "1px solid #ef4444" }}>
        ⛔ NO CALIFICÓ
      </span>
      <button data-testid={`btn-notificar-nc-${f.id}`}
        disabled={notificandoNC === f.id}
        onClick={(ev) => { ev.stopPropagation(); notificarNoCalifico(f); }}
        title={f.no_califico_notificado_at
          ? `Ya notificado el ${String(f.no_califico_notificado_at).slice(0, 16).replace("T", " ")}`
          : "Enviar correo al ejecutivo/solicitante informando el resultado negativo"}
        style={{ cursor: "pointer", border: "1px solid rgba(239,68,68,0.5)", borderRadius: 0,
          fontWeight: 800, fontSize: 10, padding: "2px 8px",
          background: "transparent", color: "#f87171" }}>
        {notificandoNC === f.id ? "Enviando…" : (f.no_califico_notificado_at ? "✓ Notificado" : "📧 Notificar al ejecutivo")}
      </button>
    </>
  )}
  </>
);

export default NotificarNoCalifico;
