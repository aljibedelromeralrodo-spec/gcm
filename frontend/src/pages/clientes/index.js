// Split incremental de ClientesModule (patrón aprobado 30/8/2026):
// se extraen componentes uno a uno; el resto sigue en el archivo viejo hasta que tenga test.
export { default as BrokersPanel } from "./BrokersPanel";
export { default as UFAmountInput } from "./UFAmountInput";
export { default as ClientesFilters } from "./ClientesFilters";
export { default as ClientesRowActions } from "./ClientesRowActions";
export { default as ClientesCardContent } from "./ClientesCardContent";
export { default as ReparosAbogado } from "./ReparosAbogado";
export { default as MoraCMF } from "./MoraCMF";
export { default as DocumentosContador } from "./DocumentosContador";
export { default as NotificarNoCalifico } from "./NotificarNoCalifico";
