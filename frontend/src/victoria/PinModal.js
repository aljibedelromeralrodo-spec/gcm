import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { API_URL } from "../utils/formatters";
import { S, PLAYFAIR } from "./theme";

export default function PinModal({ pinConfigurado, titulo, onConfirmar, onClose }) {
  const [pin, setPin] = useState("");
  const [conf, setConf] = useState("");
  const [trabajando, setTrabajando] = useState(false);

  const confirmar = async () => {
    if (!/^\d{4}$/.test(pin)) { toast.error("El PIN debe ser exactamente 4 dígitos"); return; }
    setTrabajando(true);
    try {
      if (!pinConfigurado) {
        if (pin !== conf) { toast.error("El PIN y su confirmación no coinciden"); setTrabajando(false); return; }
        await axios.post(`${API_URL}/api/victoria/pin`, { pin, confirmacion: conf });
        toast.success("PIN de seguridad creado");
      }
      await onConfirmar(pin);
      onClose();
    } catch (e) {
      const d = e.response?.data?.detail;
      toast.error(typeof d === "string" ? d : "Operación rechazada");
    }
    setTrabajando(false);
  };

  return (
    <div data-testid="pin-modal" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.8)", zIndex: 120, display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
      <div style={{ background: "#141414", border: "1px solid rgba(212,175,55,0.5)", borderRadius: 4, padding: "1.8rem", width: "100%", maxWidth: 430 }}>
        <h3 style={{ color: "#FCF6BA", margin: 0, fontSize: "1.15rem", fontFamily: PLAYFAIR }}>
          {pinConfigurado ? "PIN de seguridad requerido" : "Cree su PIN de seguridad (4 dígitos)"}</h3>
        <p style={{ color: "#a1a1aa", fontSize: "0.85rem", margin: "8px 0 14px" }}>
          {titulo} Esta acción quedará registrada como carga forzada con su nombre, fecha y hora.</p>
        <input data-testid="pin-input" type="password" inputMode="numeric" maxLength={4} autoFocus
          style={{ ...S.input, fontSize: "1.6rem", letterSpacing: "0.8em", textAlign: "center" }}
          placeholder="••••" value={pin} onChange={e => setPin(e.target.value.replace(/\D/g, ""))} />
        {!pinConfigurado && (
          <input data-testid="pin-confirmacion" type="password" inputMode="numeric" maxLength={4}
            style={{ ...S.input, fontSize: "1.6rem", letterSpacing: "0.8em", textAlign: "center", marginTop: 10 }}
            placeholder="Confirme su PIN" value={conf} onChange={e => setConf(e.target.value.replace(/\D/g, ""))} />
        )}
        <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
          <button data-testid="pin-confirmar" onClick={confirmar} disabled={trabajando}
            style={{ ...S.btnGold, flex: 1 }}>
            {trabajando ? "Verificando…" : pinConfigurado ? "Autorizar con mi PIN" : "Crear PIN y autorizar"}</button>
          <button data-testid="pin-cancelar" onClick={onClose} style={S.btnLine}>Cancelar la acción</button>
        </div>
      </div>
    </div>
  );
}
