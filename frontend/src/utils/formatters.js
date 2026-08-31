export const API_URL = process.env.REACT_APP_BACKEND_URL || "";

export const formatCurrency = (amount) => {
  if (!amount && amount !== 0) return "$0";
  return new Intl.NumberFormat("es-CL", { style: "currency", currency: "CLP", maximumFractionDigits: 0 }).format(amount);
};

export const formatUF = (amount) => {
  if (!amount && amount !== 0) return "0,00 UF";
  return new Intl.NumberFormat("es-CL", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(amount) + " UF";
};
