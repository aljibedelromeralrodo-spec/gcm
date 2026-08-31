// Corte 13 (autopiloto): contador rojo de documentos faltantes en la tarjeta
const DocumentosContador = ({ missing }) => (
  <>
  {missing.length > 0 && (
    <div title={`Faltan: ${missing.join(", ")}`} style={{ position: "absolute", top: 8, right: 8, background: "#be123c", color: "#fff", borderRadius: "50%", width: 22, height: 22, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, boxShadow: "0 2px 8px rgba(190,18,60,0.5)" }}>
      {missing.length}
    </div>
  )}
  </>
);

export default DocumentosContador;
