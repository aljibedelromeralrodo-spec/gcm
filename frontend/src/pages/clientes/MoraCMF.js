// Corte 11 (autopiloto): banner de mora CMF con link de pago, comprobante y formulario
const MoraCMF = ({ f, moraUp, moraMsg, enviarLinkPagoMora, subirComprobanteMora }) => (
  <>
  {(f.cmf_morosidad?.morosidad_clp > 0) && (
    <div data-testid={`mora-banner-${f.id}`} onClick={(ev) => ev.stopPropagation()}
      style={{ marginTop: 6, padding: "0.55rem 0.8rem", borderRadius: 0,
        background: f.cmf_morosidad.aclarada ? "rgba(16,217,142,0.12)" : "rgba(190,18,60,0.12)",
        border: `1px solid ${f.cmf_morosidad.aclarada ? "rgba(16,217,142,0.45)" : "rgba(190,18,60,0.45)"}` }}>
      {f.cmf_morosidad.aclarada ? (
        <span data-testid={`mora-aclarada-${f.id}`} style={{ fontSize: 11, fontWeight: 800, color: "#0e9f6e" }}>
          ✅ MORA ACLARADA {String(f.cmf_morosidad.aclarada_at || "").slice(0, 10)} — comprobante validado
          (${Number(f.cmf_morosidad.comprobante?.monto_detectado || 0).toLocaleString("es-CL")}) · alerta cerrada automáticamente
        </span>
      ) : (
        <>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <span style={{ fontSize: 11, fontWeight: 800, color: "#be123c" }}>
              🧾 MORA CMF: ${Number(f.cmf_morosidad.morosidad_clp).toLocaleString("es-CL")} — la Bóveda no permite morosidad
            </span>
            <button data-testid={`mora-link-pago-${f.id}`} disabled={moraUp === f.id}
              onClick={() => enviarLinkPagoMora(f)}
              title="Enviar al cliente el monto de la mora y los datos oficiales de transferencia"
              style={{ cursor: moraUp === f.id ? "wait" : "pointer", fontSize: 10, fontWeight: 800,
                padding: "3px 10px", background: "transparent", color: "#d4af37",
                border: "1px solid rgba(212,175,55,0.6)" }}>
              💳 Enviar link de pago al cliente{f.cmf_morosidad.link_pago_enviado_at ? ` ✓ ${String(f.cmf_morosidad.link_pago_enviado_at).slice(0, 10)}` : ""}
            </button>
            <label data-testid={`mora-subir-${f.id}`}
              style={{ cursor: moraUp === f.id ? "wait" : "pointer", fontSize: 10, fontWeight: 800,
                padding: "3px 10px", background: "#be123c", color: "#fff",
                opacity: moraUp === f.id ? 0.6 : 1 }}>
              {moraUp === f.id ? "⏳ Validando…" : "📤 Subir comprobante de pago"}
              <input type="file" accept=".pdf,image/*" style={{ display: "none" }} disabled={moraUp === f.id}
                onChange={(ev) => { subirComprobanteMora(f, ev.target.files?.[0], "comprobante"); ev.target.value = ""; }} />
            </label>
            <label data-testid={`mora-formulario-${f.id}`}
              title="Formulario manual de regularización (convenio / compromiso de pago)"
              style={{ cursor: moraUp === f.id ? "wait" : "pointer", fontSize: 10, fontWeight: 800,
                padding: "3px 10px", background: "transparent", color: "#be123c",
                border: "1px solid rgba(190,18,60,0.6)", opacity: moraUp === f.id ? 0.6 : 1 }}>
              📋 Subir formulario de regularización
              <input type="file" accept=".pdf,image/*" style={{ display: "none" }} disabled={moraUp === f.id}
                onChange={(ev) => { subirComprobanteMora(f, ev.target.files?.[0], "formulario"); ev.target.value = ""; }} />
            </label>
          </div>
          <div style={{ fontSize: 10, color: "#9f1239", marginTop: 3 }}>
            Al subir comprobante o formulario, el sistema valida y cierra la alerta automáticamente (sin pasar por el administrador).
          </div>
        </>
      )}
      {moraMsg[f.id] && (
        <div data-testid={`mora-msg-${f.id}`} style={{ marginTop: 5, fontSize: 11, fontWeight: 700,
          color: moraMsg[f.id].ok ? "#0e9f6e" : "#be123c" }}>
          {moraMsg[f.id].texto}
        </div>
      )}
    </div>
  )}
  </>
);

export default MoraCMF;
