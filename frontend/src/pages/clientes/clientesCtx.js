import { createContext, useContext } from "react";

export const ClientesCtx = createContext(null);
export const useClientes = () => useContext(ClientesCtx);
