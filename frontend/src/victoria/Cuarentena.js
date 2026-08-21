import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { API_URL } from "../utils/formatters";
import { S } from "./theme";
import { ChipsValidacion } from "./MonitorCorreo";
import PinModal from "./PinModal";

function ItemCuarentena({ d, clientes, pinConfigurado, onRefrescar }) {
  const [cid, setCid] = useState(d.candidato_cliente_id || "");
  const [pinAbierto, setPinAbierto] = useState(false);
  const [motivo, setMotivo] = useState("");
  const [descartando, setDescartando] = useState(false);
  const fallas = (d.validaciones_ingreso || []).filter(v => v.ok === false);

  const revalidar = async () => {
    try {
      const r = await axios.post(`${API_URL}/api/victoria/cuarentena/${d.id}/revalidar`, { cliente_id: cid });
      r.data.asociado ? toast.success(r.data.mensaje) : toast.warning(r.data.mensaje);
      onRefrescar();
    } catch (e) { toast.error(e.response?.data?.detail || "No se pudo revalidar"); }
  };

  const asociarConPin = async (pin) => {
    const r = await axios.post(`${API_URL}/api/victoria/cuarentena/${d.id}/asociar`, { cliente_id: cid, pin });
    toast.success(r.data.mensaje);
    onRefrescar();
  };

  const descartar = async () => {
    if (!motivo.trim()) { toast.error("Indique el motivo del descarte"); return; }
    try {
      const r = await axios.post(`${API_URL}/api/victoria/documentos/${d.id}/descartar`, { motivo });
      toast.success(r.data.mensaje);
      onRefrescar();
    } catch (e) { toast.error(e.response?.data?.detail || "No se pudo descartar"); }
  };

  return (
    <div data-testid={`cuarentena-item-${d.id}`} style={{ borderTop: "1px solid rgba(239,68,68,0.25)", padding: "1.1rem 0" }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <div>
          <div style={{ fontWeight: 700, color: "#fff", fontSize: "1rem", wordBreak: "break-all" }}>{d.archivo}</div>
          <div style={{ color: "#a1a1aa", fontSize: "0.87rem", marginTop: 3 }}>
            Candidato detectado: <b style={{ color: "#FCF6BA" }}>{d.candidato_nombre || "—"}</b> · recibido {String(d.recibido || "").slice(0, 16).replace("T", " ")}</div>
        </div>
        <ChipsValidacion validaciones={d.validaciones_ingreso} testid={`cuarentena-chips-${d.id}`} />
      </div>
      {fallas.map((v, i) => (
        <div key={i} style={{ color: "#f87171", fontSize: "0.9rem", marginTop: 6 }}>
          ✕ {v.etiqueta}: la ficha dice «{v.esperado}» pero el documento dice «{v.detectado}»</div>
      ))}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 12, alignItems: "center" }}>
        <select data-testid={`cuarentena-cliente-${d.id}`} value={cid} onChange={e => setCid(e.target.value)}
          style={{ ...S.input, width: 300, padding: "0.55rem 0.8rem" }}>
          <option value="">Elegir cliente de destino…</option>
          {clientes.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
        </select>
        <button data-testid={`cuarentena-revalidar-${d.id}`} onClick={revalidar} disabled={!cid}
          style={{ ...S.btnGold, ...S.btnSmall, opacity: cid ? 1 : 0.4 }}>
          Re-validar contra la ficha corregida y asociar si coincide</button>
        <button data-testid={`cuarentena-forzar-${d.id}`} onClick={() => setPinAbierto(true)} disabled={!cid}
          style={{ ...S.btnDanger, ...S.btnSmall, opacity: cid ? 1 : 0.4 }}>
          Asociar de todas formas (exige PIN de seguridad)</button>
        <button data-testid={`cuarentena-descartar-${d.id}`} onClick={() => setDescartando(s => !s)}
          style={{ ...S.btnLine, ...S.btnSmall }}>Descartar documento definitivamente</button>
      </div>
      {descartando && (
        <div style={{ display: "flex", gap: 10, marginTop: 10, flexWrap: "wrap" }}>
          <input data-testid={`cuarentena-motivo-${d.id}`} style={{ ...S.input, flex: "1 1 300px" }}
            placeholder="Motivo del descarte (obligatorio)" value={motivo} onChange={e => setMotivo(e.target.value)} />
          <button data-testid={`cuarentena-confirmar-descarte-${d.id}`} onClick={descartar}
            style={{ ...S.btnDanger, ...S.btnSmall }}>Confirmar descarte definitivo</button>
        </div>
      )}
      {pinAbierto && <PinModal pinConfigurado={pinConfigurado} onClose={() => setPinAbierto(false)}
        titulo={`Va a asociar «${d.archivo}» pese a que la validación irrenunciable no coincide.`}
        onConfirmar={asociarConPin} />}
    </div>
  );
}

export default function Cuarentena({ items, clientes, pinConfigurado, onRefrescar }) {
  if (!items || items.length === 0) return null;
  return (
    <div data-testid="dash-cuarentena" style={{ ...S.card, marginTop: 24, borderColor: "rgba(239,68,68,0.5)" }}>
      <h2 style={{ ...S.h2, color: "#f87171", marginBottom: 4 }}>
        Cuarentena — documentos bloqueados por la validación irrenunciable ({items.length})</h2>
      <p style={{ ...S.body, fontSize: "0.9rem", color: "#a1a1aa", margin: "0 0 10px" }}>
        Estos documentos NO se asociaron porque un dato no coincide exactamente con la ficha del cliente.
        Corrija la ficha (Paso 2) y re-valide, o autorice con su PIN dejando registro.</p>
      {items.map(d => <ItemCuarentena key={d.id} d={d} clientes={clientes}
        pinConfigurado={pinConfigurado} onRefrescar={onRefrescar} />)}
    </div>
  );
}
