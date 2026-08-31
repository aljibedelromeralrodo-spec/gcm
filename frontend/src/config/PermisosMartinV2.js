// PermisosMartinV2.js - Permisos totales con 2 frenos
export const PermisosMartinV2 = {
  // TODO LIBRE
  puede: [
    "fs.mkdir", "fs.rename", "fs.move", "fs.copy",
    "bunker.clasificar", "bunker.separarRUT", "bunker.juntarRUT",
    "pdf.generar", "combinado.generar", "informe.generar"
  ],
  // SOLO 2 FRENOS CON PREGUNTA
  requiereConfirmacion: [
    "email.enviar",
    "mesa.enviar"
  ],
  // LOG OBLIGATORIO
  log: {
    destino: "mongo.logs_permisos",
    campos: ["usuario", "accion", "origen", "destino", "timestamp", "rollback_path"]
  },
  // SEGURIDAD
  prohibido: ["fs.deletePermanente", "bunker.purge"],
  papelera: "/papelera/",

  mensajeBloqueo: "¿Lo envío? / ¿Lo envío a mesa?"
};
