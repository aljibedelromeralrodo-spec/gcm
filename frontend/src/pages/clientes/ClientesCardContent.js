// Corte 9: contenido informativo de la tarjeta (RUT, codeudor, archivos, chips de estado) — 0 lógica
const ClientesCardContent = ({ f, hasFin, rutValido, fmtAct }) => (
  <>
  {f.rut && <span className="clientes-rut">{f.rut}{rutValido(f.rut) &&
    <b title="RUT verificado al 100% (dígito verificador módulo 11)" style={{ color: "#22c55e", marginLeft: 4 }}>✓100%</b>}</span>}
  {f.codeudor_nombre && <span className="clientes-codeudor"><i className="fa fa-user-plus"></i> {f.codeudor_nombre}</span>}
  <span className="clientes-file-count">{f.total_archivos || 0} archivos</span>
  <div style={{ display: "flex", gap: 6, marginTop: 4, flexWrap: "wrap" }}>
    {f.is_ready_to_send && (
      <span style={{ fontSize: 10, background: "rgba(16,217,142,0.25)", color: "#0e9f6e", padding: "2px 6px", borderRadius: 0, fontWeight: 700 }}>🎯 Lista para enviar</span>
    )}
    {f.emails_sent_count > 0 && (
      <span title={`Último envío: ${(f.last_email_sent_at || "").slice(0,19).replace('T',' ')}`} style={{ fontSize: 10, background: "rgba(212,175,55,0.2)", color: "#0a3d91", padding: "2px 6px", borderRadius: 0, fontWeight: 700 }}>📧 Enviado a mesa × {f.emails_sent_count}{f.last_email_sent_at ? ` · ${fmtAct(f.last_email_sent_at)}` : ""}</span>
    )}
    {hasFin ? (
      <span style={{ fontSize: 10, background: "rgba(16,217,142,0.15)", color: "#10c98a", padding: "2px 6px", borderRadius: 0 }}>💰 Datos OK</span>
    ) : (
      <span style={{ fontSize: 10, background: "rgba(250,204,21,0.15)", color: "#a16207", padding: "2px 6px", borderRadius: 0 }}>💰 Sin datos financieros</span>
    )}
    {f.datos_financieros?.fecha_entrega && (
      <span data-testid={`badge-entrega-${f.id}`} style={{ fontSize: 10, background: "rgba(46,92,230,0.15)", color: "#1e46c0", padding: "2px 6px", borderRadius: 0, fontWeight: 700 }}>🏠 Entrega {f.datos_financieros.fecha_entrega}</span>
    )}
  </div>
  </>
);

export default ClientesCardContent;
