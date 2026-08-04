import { useState, useEffect } from "react";
import axios from "axios";
import { API_URL } from "../utils/formatters";
import { COLORS, formatCLP } from "./predic/constants";
import { Field, UFField } from "./predic/PredICFields";
import { DashCard } from "./predic/PredICWidgets";
import { PredICResult } from "./predic/PredICResult";

export default function CentralPredic() {
  const [auth, setAuth] = useState(null);
  const [loginForm, setLoginForm] = useState({ usuario: "", password: "" });
  const [loginError, setLoginError] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);

  // Check stored session
  useEffect(() => {
    const saved = localStorage.getItem("predic_auth");
    if (saved) setAuth(JSON.parse(saved));
  }, []);

  const handleLogin = async () => {
    setLoginLoading(true);
    setLoginError("");
    try {
      const r = await axios.post(`${API_URL}/api/inmobiliaria/auth/login`, loginForm);
      if (r.data.ok) {
        setAuth(r.data);
        localStorage.setItem("predic_auth", JSON.stringify(r.data));
      } else {
        setLoginError(r.data.error || "Credenciales incorrectas");
      }
    } catch {
      setLoginError("Error de conexion");
    }
    setLoginLoading(false);
  };

  const logout = () => {
    setAuth(null);
    localStorage.removeItem("predic_auth");
  };

  if (!auth) return <PredICLogin form={loginForm} setForm={setLoginForm} onLogin={handleLogin} error={loginError} loading={loginLoading} />;
  return <PredICApp auth={auth} onLogout={logout} />;
}


function PredICLogin({ form, setForm, onLogin, error, loading }) {
  return (
    <div style={{ minHeight: "100vh", background: `linear-gradient(135deg, ${COLORS.bg} 0%, #1a1a4e 50%, #0a0e27 100%)`, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "'Segoe UI', sans-serif" }}>
      <div style={{ width: "380px", padding: "2.5rem", borderRadius: "2px", background: COLORS.card, border: `1px solid ${COLORS.border}`, boxShadow: "0 20px 60px rgba(0,0,0,0.5)" }}>
        <div style={{ textAlign: "center", marginBottom: "2rem" }}>
          <div style={{ fontSize: "2.5rem", fontWeight: 800, background: `linear-gradient(135deg, ${COLORS.accent}, ${COLORS.gold})`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            Central PREDIC
          </div>
          <div style={{ color: COLORS.textMuted, fontSize: "0.85rem", marginTop: "0.3rem" }}>Prediccion de Credito Inmobiliario</div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <input data-testid="predic-login-user" placeholder="Usuario" value={form.usuario}
            onChange={e => setForm({...form, usuario: e.target.value})}
            onKeyDown={e => e.key === "Enter" && onLogin()}
            style={{ padding: "0.85rem 1rem", borderRadius: "2px", border: `1px solid ${COLORS.border}`, background: "rgba(255,255,255,0.05)", color: COLORS.text, fontSize: "1rem", outline: "none" }}
          />
          <input data-testid="predic-login-pass" type="password" placeholder="Clave" value={form.password}
            onChange={e => setForm({...form, password: e.target.value})}
            onKeyDown={e => e.key === "Enter" && onLogin()}
            style={{ padding: "0.85rem 1rem", borderRadius: "2px", border: `1px solid ${COLORS.border}`, background: "rgba(255,255,255,0.05)", color: COLORS.text, fontSize: "1rem", outline: "none" }}
          />
          {error && <div data-testid="predic-login-error" style={{ color: COLORS.red, fontSize: "0.85rem", textAlign: "center" }}>{error}</div>}
          <button data-testid="predic-login-btn" onClick={onLogin} disabled={loading}
            style={{ padding: "0.9rem", borderRadius: "2px", border: "none", background: `linear-gradient(135deg, ${COLORS.accent}, #4834d4)`, color: "#fff", fontSize: "1rem", fontWeight: 700, cursor: loading ? "wait" : "pointer", letterSpacing: "1px" }}>
            {loading ? "Verificando..." : "INGRESAR"}
          </button>
        </div>
      </div>
    </div>
  );
}


function PredICApp({ auth, onLogout }) {
  const [modo, setModo] = useState("subsidio");
  const [form, setForm] = useState({ valor_propiedad: "", subsidio: "", pie: "", monto_credito: "", renta_fija: "", renta_variable: "", renta_honorarios: "", cuota_deudas: "", nombre_cliente: "" });
  const [advForm, setAdvForm] = useState({ edad_cliente: "35", tipo_deudor: "1", tipo_codeudor: "0", renta_codeudor: "", edad_codeudor: "", antiguedad_laboral_meses: "24", morosidad_dicom: false, protestos_vigentes: false, continuidad_laboral: true, plazo_anos: "0" });
  const [showAdv, setShowAdv] = useState(false);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showCalc, setShowCalc] = useState(false);
  const [calcForm, setCalcForm] = useState({ monto_deuda: "", tasa_anual: "2", plazo_anos: "4" });
  const [calcResult, setCalcResult] = useState(null);
  const [contactForm, setContactForm] = useState({ nombre: "", telefono: "", email: "", mensaje: "" });
  const [contactSent, setContactSent] = useState(false);
  const [comparacion, setComparacion] = useState(null);
  const [comparandoLoad, setComparandoLoad] = useState(false);
  const [showChat, setShowChat] = useState(false);
  const [chatEnabled, setChatEnabled] = useState(false);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatSessionId, setChatSessionId] = useState("");
  const [view, setView] = useState("predictor");
  const [dashData, setDashData] = useState(null);
  const [tasas, setTasas] = useState({ tasa_subsidio_mayor_2000: 6.35, tasa_subsidio_menor_2000: 6.50, tasa_sin_subsidio: 5.9 });
  const [seguros, setSeguros] = useState({ seguro_desgravamen: 10245, seguro_incendio: 23702 });
  const [tasasSaving, setTasasSaving] = useState(false);

  // Load configured rates, seguros, and check IA chat
  useEffect(() => {
    axios.get(`${API_URL}/api/inmobiliaria/config/tasas`)
      .then(r => setTasas({
        tasa_subsidio_mayor_2000: Math.round(r.data.tasa_subsidio_mayor_2000 * 10000) / 100,
        tasa_subsidio_menor_2000: Math.round(r.data.tasa_subsidio_menor_2000 * 10000) / 100,
        tasa_sin_subsidio: Math.round(r.data.tasa_sin_subsidio * 10000) / 100,
      }))
      .catch(() => {});
    axios.get(`${API_URL}/api/inmobiliaria/config/seguros`)
      .then(r => { if (r.data && r.data.seguro_desgravamen) setSeguros(r.data); })
      .catch(() => {});
    axios.get(`${API_URL}/api/inmobiliaria/ia-config`)
      .then(r => setChatEnabled(r.data.enabled || false))
      .catch(() => {});
  }, []);

  const saveTasas = async () => {
    setTasasSaving(true);
    try {
      await axios.put(`${API_URL}/api/inmobiliaria/config/tasas`, {
        tasa_subsidio_mayor_2000: tasas.tasa_subsidio_mayor_2000 / 100,
        tasa_subsidio_menor_2000: tasas.tasa_subsidio_menor_2000 / 100,
        tasa_sin_subsidio: tasas.tasa_sin_subsidio / 100,
      });
      alert("Tasas actualizadas correctamente");
    } catch { alert("Error al guardar tasas"); }
    setTasasSaving(false);
  };

  const parseCLP = (v) => parseFloat(String(v).replace(/\./g, "").replace(",", ".")) || 0;

  const exportPDF = async () => {
    if (!result || result.error) return;
    try {
      const resp = await axios.post(`${API_URL}/api/inmobiliaria/export-pdf`, {
        ...result,
        nombre_cliente: form.nombre_cliente || "",
        ejecutivo: auth?.usuario || "",
        inmobiliaria: auth?.inmobiliaria || "",
      }, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([resp.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = `PREDIC_${form.nombre_cliente || "cliente"}_${new Date().toISOString().slice(0,10)}.pdf`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch { alert("Error al generar PDF"); }
  };

  const loadDashboard = () => {
    axios.get(`${API_URL}/api/inmobiliaria/mi-dashboard?company=${encodeURIComponent(auth.inmobiliaria || "")}&usuario=${encodeURIComponent(auth.usuario || "")}`).then(r => setDashData(r.data)).catch(() => {});
  };

  const handlePredict = async () => {
    setLoading(true);
    setResult(null);
    try {
      const r = await axios.post(`${API_URL}/api/inmobiliaria/predict`, {
        modo,
        valor_propiedad_uf: parseCLP(form.valor_propiedad),
        subsidio_uf: modo === "subsidio" ? parseCLP(form.subsidio) : 0,
        pie_uf: parseCLP(form.pie),
        monto_credito_uf: parseCLP(form.monto_credito),
        renta_fija: parseCLP(form.renta_fija),
        renta_variable: parseCLP(form.renta_variable),
        renta_honorarios: parseCLP(form.renta_honorarios),
        renta_mensual: parseCLP(form.renta_fija) + parseCLP(form.renta_variable) + parseCLP(form.renta_honorarios),
        cuota_deudas: parseCLP(form.cuota_deudas),
        usuario: auth?.usuario || null,
        company_name: auth?.inmobiliaria || null,
        nombre_cliente: form.nombre_cliente || "",
        edad_cliente: parseInt(advForm.edad_cliente) || 35,
        tipo_deudor: parseInt(advForm.tipo_deudor) || 1,
        tipo_codeudor: parseInt(advForm.tipo_codeudor) || 0,
        renta_codeudor: parseCLP(advForm.renta_codeudor),
        edad_codeudor: parseInt(advForm.edad_codeudor) || 0,
        antiguedad_laboral_meses: parseInt(advForm.antiguedad_laboral_meses) || 24,
        morosidad_dicom: advForm.morosidad_dicom,
        protestos_vigentes: advForm.protestos_vigentes,
        continuidad_laboral: advForm.continuidad_laboral,
        plazo_anos: parseInt(advForm.plazo_anos) || 0,
      });
      setResult(r.data);
    } catch {
      setResult({ error: true });
    }
    setLoading(false);
  };

  const handleCalc = async () => {
    try {
      const r = await axios.post(`${API_URL}/api/inmobiliaria/calc-deuda`, {
        monto_deuda: parseCLP(calcForm.monto_deuda),
        tasa_anual: parseFloat(calcForm.tasa_anual) / 100,
        plazo_anos: parseInt(calcForm.plazo_anos),
      });
      setCalcResult(r.data);
    } catch {
      setCalcResult(null);
    }
  };

  const handleContact = async () => {
    if (!contactForm.nombre || !contactForm.telefono) return;
    try {
      await axios.post(`${API_URL}/api/inmobiliaria/leads`, {
        ...contactForm,
        resultado_viable: result?.viable,
        financiamiento_uf: result?.financiamiento_maximo_uf,
        inmobiliaria: auth.inmobiliaria || "",
      });
      setContactSent(true);
    } catch {}
  };

  const handleComparar = async () => {
    if (!result) return;
    setComparandoLoad(true);
    setComparacion(null);
    try {
      // Send credit amount and plazo from our result - backend derives property value with 20% pie
      const creditoUf = result.monto_aprobado_uf || parseFloat(form.monto_credito) || 0;

      const r = await axios.post(`${API_URL}/api/inmobiliaria/comparar-competidores`, {
        valor_propiedad_uf: parseFloat(form.valor_propiedad) || 1,
        monto_credito_uf: creditoUf,
        pie_pct: 20,
        plazo_anos: result.plazo_anos || 30,
        tasa_mutuaria: result.tasa_aplicada || 6.5,
        dividendo_mutuaria_uf: result.dividendo_estimado_uf || 0,
        dividendo_mutuaria_clp: result.dividendo_estimado_clp || 0,
      });
      setComparacion(r.data);
    } catch { setComparacion(null); }
    setComparandoLoad(false);
  };

  const sendChat = async () => {
    if (!chatInput.trim() || chatLoading) return;
    const msg = chatInput.trim();
    setChatInput("");
    setChatMessages(prev => [...prev, { role: "user", content: msg }]);
    setChatLoading(true);
    try {
      const r = await axios.post(`${API_URL}/api/inmobiliaria/ia-chat`, {
        message: msg,
        usuario: auth?.usuario || "",
        session_id: chatSessionId,
      });
      if (r.data.session_id) setChatSessionId(r.data.session_id);
      if (!r.data.enabled) setChatEnabled(false);
      setChatMessages(prev => [...prev, { role: "assistant", content: r.data.response }]);
    } catch {
      setChatMessages(prev => [...prev, { role: "assistant", content: "Error de conexion. Intente nuevamente." }]);
    }
    setChatLoading(false);
  };

  const S = { input: { width: "100%", padding: "0.75rem 1rem", borderRadius: "2px", border: `1px solid ${COLORS.border}`, background: "rgba(255,255,255,0.06)", color: COLORS.text, fontSize: "0.95rem", outline: "none", boxSizing: "border-box" } };

  return (
    <div style={{ minHeight: "100vh", background: `linear-gradient(135deg, ${COLORS.bg} 0%, #1a1a4e 50%, #0a0e27 100%)`, fontFamily: "'Segoe UI', sans-serif", color: COLORS.text }}>
      {/* Header */}
      <div style={{ padding: "1rem 1.5rem", display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: `1px solid ${COLORS.border}` }}>
        <div>
          <span style={{ fontSize: "1.3rem", fontWeight: 800, background: `linear-gradient(135deg, ${COLORS.accent}, ${COLORS.gold})`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            Central PREDIC
          </span>
          <span style={{ color: COLORS.textMuted, fontSize: "0.8rem", marginLeft: "0.75rem" }}>{auth.inmobiliaria} - {auth.nombre}</span>
        </div>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          {[["predictor", "fa-calculator", "Predictor"], ["dashboard", "fa-chart-bar", "Mi Dashboard"], ["config", "fa-cog", "Tasas"]].map(([v, icon, label]) => (
            <button key={v} data-testid={`predic-tab-${v}`} onClick={() => { setView(v); if (v === "dashboard") loadDashboard(); }}
              style={{ padding: "0.4rem 0.8rem", borderRadius: "2px", border: `1px solid ${view === v ? COLORS.accent : COLORS.border}`, background: view === v ? "rgba(108,92,231,0.15)" : "transparent", color: view === v ? COLORS.accentLight : COLORS.textMuted, fontSize: "0.78rem", fontWeight: 600, cursor: "pointer" }}>
              <i className={`fa ${icon}`} style={{ marginRight: "0.3rem" }}></i>{label}
            </button>
          ))}
          <button data-testid="predic-logout" onClick={onLogout} style={{ padding: "0.4rem 1rem", borderRadius: "2px", border: `1px solid ${COLORS.border}`, background: "transparent", color: COLORS.textMuted, cursor: "pointer", fontSize: "0.8rem" }}>
            Salir
          </button>
        </div>
      </div>

      {/* Dashboard View */}
      {view === "dashboard" && (
        <div style={{ maxWidth: "600px", margin: "0 auto", padding: "1.5rem 1rem" }}>
          {!dashData ? (
            <div style={{ textAlign: "center", padding: "3rem", color: COLORS.textMuted }}><i className="fa fa-spinner fa-spin" style={{ fontSize: "1.5rem" }}></i></div>
          ) : (
            <>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.75rem", marginBottom: "1.5rem" }}>
                <DashCard label="Predicciones" value={dashData.total} icon="fa-calculator" color={COLORS.accent} />
                <DashCard label="Viables" value={dashData.viables} icon="fa-check-circle" color={COLORS.green} />
                <DashCard label="Tasa" value={`${dashData.tasa_viabilidad}%`} icon="fa-chart-line" color={COLORS.gold} />
              </div>

              {dashData.recientes?.length > 0 && (
                <div style={{ padding: "1rem", borderRadius: "2px", background: COLORS.card, border: `1px solid ${COLORS.border}`, marginBottom: "1rem" }}>
                  <div style={{ fontWeight: 700, color: COLORS.text, fontSize: "0.9rem", marginBottom: "0.75rem" }}>
                    <i className="fa fa-history" style={{ color: COLORS.accent, marginRight: "0.4rem" }}></i>Mis Predicciones Recientes
                  </div>
                  {dashData.recientes.map((p, i) => (
                    <div key={i} style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.4rem 0", borderBottom: i < dashData.recientes.length - 1 ? `1px solid ${COLORS.border}` : "none" }}>
                      <span style={{ padding: "2px 6px", borderRadius: "2px", fontSize: "0.7rem", fontWeight: 700, background: p.viable ? "rgba(0,184,148,0.15)" : "rgba(225,112,85,0.15)", color: p.viable ? COLORS.green : COLORS.red }}>{p.viable ? "VIABLE" : "NO"}</span>
                      <span style={{ fontSize: "0.82rem", color: COLORS.text }}>{formatCLP(p.valor_propiedad_clp || 0)}</span>
                      <span style={{ fontSize: "0.75rem", color: COLORS.textMuted }}>Renta: {formatCLP(p.renta || 0)}</span>
                      <span style={{ marginLeft: "auto", fontSize: "0.7rem", color: COLORS.textMuted }}>{p.timestamp ? new Date(p.timestamp).toLocaleDateString("es-CL") : ""}</span>
                    </div>
                  ))}
                </div>
              )}

              {dashData.leads?.length > 0 && (
                <div style={{ padding: "1rem", borderRadius: "2px", background: COLORS.card, border: `1px solid ${COLORS.border}` }}>
                  <div style={{ fontWeight: 700, color: COLORS.text, fontSize: "0.9rem", marginBottom: "0.75rem" }}>
                    <i className="fa fa-users" style={{ color: COLORS.gold, marginRight: "0.4rem" }}></i>Mis Leads
                  </div>
                  {dashData.leads.map((l, i) => (
                    <div key={i} style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.4rem 0", borderBottom: i < dashData.leads.length - 1 ? `1px solid ${COLORS.border}` : "none" }}>
                      <i className="fa fa-user" style={{ color: COLORS.accent, fontSize: "0.8rem" }}></i>
                      <span style={{ fontSize: "0.82rem", color: COLORS.text, fontWeight: 500 }}>{l.nombre}</span>
                      <span style={{ fontSize: "0.75rem", color: COLORS.textMuted }}>{l.telefono}</span>
                      <span style={{ marginLeft: "auto", padding: "1px 6px", borderRadius: "2px", fontSize: "0.68rem", fontWeight: 600, background: l.estado === "nuevo" ? "rgba(243,156,18,0.15)" : "rgba(0,184,148,0.15)", color: l.estado === "nuevo" ? COLORS.orange : COLORS.green }}>{l.estado}</span>
                    </div>
                  ))}
                </div>
              )}

              {dashData.total === 0 && (
                <div style={{ textAlign: "center", padding: "2rem", color: COLORS.textMuted }}>
                  <i className="fa fa-chart-bar" style={{ fontSize: "2rem", marginBottom: "0.5rem", display: "block" }}></i>
                  Aun no tienes predicciones. Usa el Predictor para empezar.
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Predictor Content */}
      {/* Config View */}
      {view === "config" && (
        <div style={{ maxWidth: "520px", margin: "0 auto", padding: "1.5rem 1rem" }}>
          <div style={{ background: COLORS.card, borderRadius: "2px", padding: "1.5rem", border: `1px solid ${COLORS.border}` }}>
            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, color: COLORS.text, marginBottom: "1rem" }}>
              <i className="fa fa-cog" style={{ color: COLORS.gold, marginRight: "0.5rem" }}></i>Configuracion de Tasas de Interes
            </h3>
            <p style={{ fontSize: "0.8rem", color: COLORS.textMuted, marginBottom: "1.25rem" }}>
              Las tasas se aplican automaticamente segun el modo de evaluacion seleccionado.
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div style={{ padding: "0.75rem", borderRadius: "2px", background: "rgba(0,184,148,0.06)", border: "1px solid rgba(0,184,148,0.15)" }}>
                <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "#00b894", marginBottom: "0.6rem", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                  <i className="fa fa-ticket" style={{ marginRight: "0.3rem" }}></i>Tasas Con Subsidio
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
                  <div>
                    <label style={{ fontSize: "0.72rem", color: COLORS.textMuted, display: "block", marginBottom: "0.2rem" }}>
                      Credito &gt; 2000 UF (%)
                    </label>
                    <input data-testid="config-tasa-subsidio-mayor" type="number" step="0.01" min="0" max="20"
                      value={tasas.tasa_subsidio_mayor_2000}
                      onChange={e => setTasas({...tasas, tasa_subsidio_mayor_2000: parseFloat(e.target.value) || 0})}
                      style={{ ...S.input, fontSize: "1rem", fontWeight: 700, textAlign: "center" }} />
                  </div>
                  <div>
                    <label style={{ fontSize: "0.72rem", color: COLORS.textMuted, display: "block", marginBottom: "0.2rem" }}>
                      Credito &le; 2000 UF (%)
                    </label>
                    <input data-testid="config-tasa-subsidio-menor" type="number" step="0.01" min="0" max="20"
                      value={tasas.tasa_subsidio_menor_2000}
                      onChange={e => setTasas({...tasas, tasa_subsidio_menor_2000: parseFloat(e.target.value) || 0})}
                      style={{ ...S.input, fontSize: "1rem", fontWeight: 700, textAlign: "center" }} />
                  </div>
                </div>
              </div>

              <div>
                <label style={{ fontSize: "0.8rem", color: COLORS.textMuted, display: "block", marginBottom: "0.3rem" }}>
                  <i className="fa fa-bank" style={{ color: COLORS.accentLight, marginRight: "0.4rem" }}></i>Tasa Anual - Sin Subsidio (%)
                </label>
                <input data-testid="config-tasa-sin-subsidio" type="number" step="0.01" min="0" max="20"
                  value={tasas.tasa_sin_subsidio}
                  onChange={e => setTasas({...tasas, tasa_sin_subsidio: parseFloat(e.target.value) || 0})}
                  style={{ ...S.input, fontSize: "1.1rem", fontWeight: 700, textAlign: "center" }} />
              </div>
            </div>

            <button data-testid="config-save-tasas" onClick={saveTasas} disabled={tasasSaving}
              style={{ marginTop: "1.25rem", width: "100%", padding: "0.75rem", borderRadius: "2px", border: "none", background: `linear-gradient(135deg, ${COLORS.accent}, #4834d4)`, color: "#fff", fontWeight: 700, fontSize: "0.95rem", cursor: tasasSaving ? "wait" : "pointer" }}>
              <i className={`fa ${tasasSaving ? "fa-spinner fa-spin" : "fa-save"}`} style={{ marginRight: "0.5rem" }}></i>
              {tasasSaving ? "Guardando..." : "Guardar Tasas"}
            </button>

            <div style={{ marginTop: "1rem", padding: "0.75rem", borderRadius: "2px", background: "rgba(212,175,55,0.08)", border: `2px solid rgba(212,175,55,0.55)` }}>
              <div style={{ fontSize: "0.75rem", color: COLORS.gold }}>
                <i className="fa fa-info-circle" style={{ marginRight: "0.3rem" }}></i>
                Estas tasas se usaran en todas las evaluaciones nuevas. Los cambios se aplican inmediatamente.
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Predictor View */}
      {view === "predictor" && <div style={{ maxWidth: "520px", margin: "0 auto", padding: "1.5rem 1rem" }}>
        {/* Mode selector */}
        <div data-testid="predic-mode-selector" style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem" }}>
          {[["subsidio", "Con Subsidio"], ["sin_subsidio", "Sin Subsidio"]].map(([key, label]) => (
            <button key={key} data-testid={`predic-mode-${key}`} onClick={() => { setModo(key); setResult(null); }}
              style={{
                flex: 1, padding: "0.75rem", borderRadius: "2px", border: `2px solid ${modo === key ? COLORS.accent : COLORS.border}`,
                background: modo === key ? `linear-gradient(135deg, rgba(108,92,231,0.2), rgba(108,92,231,0.05))` : "transparent",
                color: modo === key ? COLORS.accentLight : COLORS.textMuted, fontWeight: 700, fontSize: "0.95rem", cursor: "pointer",
                transition: "all 0.2s",
              }}>
              {label}
            </button>
          ))}
        </div>

        {/* Form */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem", marginBottom: "1.25rem" }}>

          {/* Section: Cliente */}
          <div style={{ padding: "0.75rem", borderRadius: "2px", background: "rgba(108,92,231,0.04)", border: `1px solid ${COLORS.border}` }}>
            <div style={{ fontSize: "0.7rem", fontWeight: 700, color: COLORS.accentLight, marginBottom: "0.5rem", textTransform: "uppercase", letterSpacing: "1px" }}>
              <i className="fa fa-user" style={{ marginRight: "0.3rem" }}></i>Cliente
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "0.5rem" }}>
              <div>
                <label style={{ fontSize: "0.72rem", color: COLORS.textMuted, display: "block", marginBottom: "2px" }}>Nombre</label>
                <input data-testid="predic-nombre-cliente" placeholder="Nombre del cliente" value={form.nombre_cliente}
                  onChange={e => setForm({...form, nombre_cliente: e.target.value})}
                  style={S.input} />
              </div>
              <div>
                <label style={{ fontSize: "0.72rem", color: COLORS.textMuted, display: "block", marginBottom: "2px" }}>Edad</label>
                <input data-testid="predic-edad-main" type="number" placeholder="35" value={advForm.edad_cliente}
                  onChange={e => setAdvForm({...advForm, edad_cliente: e.target.value})}
                  style={S.input} />
                {parseInt(advForm.edad_cliente) > 0 && (
                  <div style={{ fontSize: "0.65rem", color: COLORS.accentLight, marginTop: "2px" }}>
                    Plazo auto: {Math.min(40, 80 - parseInt(advForm.edad_cliente))} anos
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Section: Propiedad */}
          <div style={{ padding: "0.75rem", borderRadius: "2px", background: "rgba(212,175,55,0.04)", border: `1px solid ${COLORS.border}` }}>
            <div style={{ fontSize: "0.7rem", fontWeight: 700, color: COLORS.gold, marginBottom: "0.5rem", textTransform: "uppercase", letterSpacing: "1px" }}>
              <i className="fa fa-home" style={{ marginRight: "0.3rem" }}></i>Propiedad y Credito
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
              <UFField label="Valor Propiedad (UF)" icon="fa-home" value={form.valor_propiedad} testId="predic-valor-propiedad"
                onChange={v => setForm({...form, valor_propiedad: v})} style={S.input} />
              <UFField label="Credito Requerido (UF)" icon="fa-bank" value={form.monto_credito} testId="predic-monto-credito"
                onChange={v => setForm({...form, monto_credito: v})} style={S.input} />
              {modo === "subsidio" && (
                <UFField label="Subsidio (UF)" icon="fa-ticket" value={form.subsidio} testId="predic-subsidio"
                  onChange={v => setForm({...form, subsidio: v})} style={S.input} />
              )}
              <UFField label="Pie / Ahorro (UF)" icon="fa-money" value={form.pie} testId="predic-pie"
                onChange={v => setForm({...form, pie: v})} style={S.input} />
            </div>
            {/* Plazo - primary field */}
            <div style={{ marginTop: "0.5rem", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
              <div>
                <label style={{ fontSize: "0.72rem", color: COLORS.textMuted, display: "block", marginBottom: "2px" }}>
                  <i className="fa fa-calendar" style={{ marginRight: "0.3rem" }}></i>Plazo (anos)
                </label>
                <input data-testid="predic-plazo" type="number" value={advForm.plazo_anos}
                  onChange={e => setAdvForm({...advForm, plazo_anos: e.target.value})}
                  style={S.input} placeholder="0 = automatico" min="0" max="40" />
                {(() => {
                  const edad = parseInt(advForm.edad_cliente) || 35;
                  const maxPlazo = Math.max(1, Math.min(40, 80 - edad));
                  const plazoIngresado = parseInt(advForm.plazo_anos) || 0;
                  return (
                    <div style={{ marginTop: "3px" }}>
                      {plazoIngresado === 0 && (
                        <div style={{ fontSize: "0.65rem", color: COLORS.accentLight }}>
                          Plazo sugerido: {Math.min(30, maxPlazo)} anos (max {maxPlazo} para edad {edad})
                        </div>
                      )}
                      {plazoIngresado > 0 && plazoIngresado <= maxPlazo && (
                        <div style={{ fontSize: "0.65rem", color: COLORS.green }}>
                          Edad + Plazo = {edad + plazoIngresado} (max 80)
                        </div>
                      )}
                      {plazoIngresado > maxPlazo && (
                        <div style={{ fontSize: "0.65rem", color: COLORS.red, fontWeight: 600 }}>
                          Excede limite: {edad} + {plazoIngresado} = {edad + plazoIngresado} (max 80). Se ajustara a {maxPlazo} anos.
                        </div>
                      )}
                    </div>
                  );
                })()}
              </div>
              <div>
                <label style={{ fontSize: "0.72rem", color: COLORS.textMuted, display: "block", marginBottom: "2px" }}>
                  <i className="fa fa-percent" style={{ marginRight: "0.3rem" }}></i>Tasa aplicada
                </label>
                {(() => {
                  if (modo !== "subsidio") {
                    return (
                      <div style={{ ...S.input, background: "rgba(108,92,231,0.08)", display: "flex", alignItems: "center", fontSize: "0.8rem", color: COLORS.accentLight, fontWeight: 600 }}>
                        Sin subsidio: {tasas.tasa_sin_subsidio}%
                      </div>
                    );
                  }
                  const credUf = parseFloat(form.monto_credito) || 0;
                  const tasaAplicada = credUf > 2000 ? tasas.tasa_subsidio_mayor_2000 : tasas.tasa_subsidio_menor_2000;
                  const tramo = credUf > 2000 ? "> 2000 UF" : "<= 2000 UF";
                  return (
                    <div style={{ ...S.input, background: "rgba(0,184,148,0.08)", display: "flex", alignItems: "center", fontSize: "0.8rem", color: COLORS.green, fontWeight: 600 }}>
                      {tasaAplicada}% ({tramo})
                    </div>
                  );
                })()}
              </div>
            </div>
            {/* Real-time LTV indicator */}
            {parseFloat(form.valor_propiedad) > 0 && parseFloat(form.monto_credito) > 0 && (
              <div style={{ marginTop: "0.4rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                <span style={{ padding: "2px 6px", borderRadius: "2px", fontSize: "0.65rem", fontWeight: 600,
                  background: (parseFloat(form.monto_credito) / parseFloat(form.valor_propiedad)) <= (modo === "subsidio" ? 0.8 : 0.9) ? "rgba(0,184,148,0.12)" : "rgba(225,112,85,0.12)",
                  color: (parseFloat(form.monto_credito) / parseFloat(form.valor_propiedad)) <= (modo === "subsidio" ? 0.8 : 0.9) ? COLORS.green : COLORS.red }}>
                  LTV: {((parseFloat(form.monto_credito) / parseFloat(form.valor_propiedad)) * 100).toFixed(0)}% (max {modo === "subsidio" ? "80" : "90"}%)
                </span>
                {parseFloat(form.pie) > 0 && (
                  <span style={{ padding: "2px 6px", borderRadius: "2px", fontSize: "0.65rem", fontWeight: 600, background: "rgba(108,92,231,0.1)", color: COLORS.accentLight }}>
                    Pie: {((parseFloat(form.pie) / parseFloat(form.valor_propiedad)) * 100).toFixed(0)}%
                  </span>
                )}
              </div>
            )}
          </div>

          {/* Section: Ingresos */}
          <div style={{ padding: "0.75rem", borderRadius: "2px", background: "rgba(0,184,148,0.04)", border: `1px solid ${COLORS.border}` }}>
            <div style={{ fontSize: "0.7rem", fontWeight: 700, color: COLORS.green, marginBottom: "0.5rem", textTransform: "uppercase", letterSpacing: "1px" }}>
              <i className="fa fa-briefcase" style={{ marginRight: "0.3rem" }}></i>Ingresos del Titular
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
              <Field label="Renta Fija (CLP)" icon="fa-money" value={form.renta_fija} testId="predic-renta-fija"
                onChange={v => setForm({...form, renta_fija: v})} style={S.input} placeholder="Sueldo base" />
              <Field label="Renta Variable (CLP)" icon="fa-line-chart" value={form.renta_variable} testId="predic-renta-variable"
                onChange={v => setForm({...form, renta_variable: v})} style={S.input} placeholder="Comisiones, bonos" />
              <Field label="Honorarios (CLP)" icon="fa-file-text-o" value={form.renta_honorarios} testId="predic-renta-honorarios"
                onChange={v => setForm({...form, renta_honorarios: v})} style={S.input} placeholder="Ingresos indep." />
              <Field label="Cuota Deudas (CLP)" icon="fa-credit-card" value={form.cuota_deudas} testId="predic-deudas"
                onChange={v => setForm({...form, cuota_deudas: v})} style={S.input} placeholder="$0" />
            </div>
            {/* Renta summary with castigos preview */}
            {(parseCLP(form.renta_fija) > 0 || parseCLP(form.renta_variable) > 0 || parseCLP(form.renta_honorarios) > 0) && (() => {
              const rf = parseCLP(form.renta_fija), rv = parseCLP(form.renta_variable), rh = parseCLP(form.renta_honorarios);
              const total = rf + rv + rh;
              const efectiva = rf + rv * 0.85 + rh * 0.80;
              const castigo = total - efectiva;
              return (
                <div style={{ marginTop: "0.4rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                  <span data-testid="predic-renta-total" style={{ padding: "2px 6px", borderRadius: "2px", fontSize: "0.65rem", fontWeight: 600, background: "rgba(0,184,148,0.12)", color: COLORS.green }}>
                    Total: ${total.toLocaleString("es-CL")}
                  </span>
                  {castigo > 0 && (
                    <span data-testid="predic-renta-castigo" style={{ padding: "2px 6px", borderRadius: "2px", fontSize: "0.65rem", fontWeight: 600, background: "rgba(243,156,18,0.12)", color: COLORS.orange }}>
                      Castigo Renta: -${castigo.toLocaleString("es-CL")} | Efectiva: ${efectiva.toLocaleString("es-CL")}
                    </span>
                  )}
                </div>
              );
            })()}
            {/* Debt ratio indicator */}
            {(() => {
              const totalR = parseCLP(form.renta_fija) + parseCLP(form.renta_variable) + parseCLP(form.renta_honorarios);
              const deuda = parseCLP(form.cuota_deudas);
              if (totalR > 0 && deuda > 0) {
                const ratio = deuda / totalR;
                return (
                  <div style={{ marginTop: "0.3rem" }}>
                    <span style={{ padding: "2px 6px", borderRadius: "2px", fontSize: "0.65rem", fontWeight: 600,
                      background: ratio <= 0.35 ? "rgba(0,184,148,0.12)" : "rgba(225,112,85,0.12)",
                      color: ratio <= 0.35 ? COLORS.green : COLORS.red }}>
                      Carga actual: {(ratio * 100).toFixed(0)}% {ratio > 0.35 ? "(>35%)" : ""}
                    </span>
                  </div>
                );
              }
              return null;
            })()}
          </div>
        </div>

        {/* Advanced evaluation toggle */}
        <button data-testid="predic-advanced-toggle" onClick={() => setShowAdv(!showAdv)}
          style={{ width: "100%", padding: "0.6rem", borderRadius: "2px", border: `1px solid ${COLORS.border}`, background: showAdv ? "rgba(108,92,231,0.1)" : "transparent", color: COLORS.textMuted, cursor: "pointer", fontSize: "0.82rem", fontWeight: 600, marginBottom: "0.75rem", display: "flex", alignItems: "center", justifyContent: "center", gap: "0.4rem" }}>
          <i className={`fa fa-${showAdv ? "chevron-up" : "chevron-down"}`}></i>
          Evaluacion Avanzada
        </button>

        {showAdv && (
          <div data-testid="predic-advanced-section" style={{ padding: "1rem", borderRadius: "2px", background: "rgba(108,92,231,0.06)", border: `1px solid ${COLORS.border}`, marginBottom: "0.75rem" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem", marginBottom: "0.75rem" }}>
              <div>
                <label style={{ fontSize: "0.72rem", color: COLORS.textMuted, display: "block", marginBottom: "2px" }}>Tipo Deudor</label>
                <select data-testid="predic-tipo-deudor" value={advForm.tipo_deudor} onChange={e => setAdvForm({...advForm, tipo_deudor: e.target.value})}
                  style={{ ...S.input, width: "100%" }}>
                  <option value="1">Dependiente Renta Fija</option>
                  <option value="2">Dep. Renta Variable</option>
                  <option value="3">Independiente/Honorarios</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: "0.72rem", color: COLORS.textMuted, display: "block", marginBottom: "2px" }}>Antiguedad Laboral (meses)</label>
                <input data-testid="predic-antiguedad" type="number" value={advForm.antiguedad_laboral_meses}
                  onChange={e => setAdvForm({...advForm, antiguedad_laboral_meses: e.target.value})}
                  style={S.input} placeholder="24" min="0" />
                {parseInt(advForm.antiguedad_laboral_meses) < 12 && parseInt(advForm.antiguedad_laboral_meses) >= 0 && (
                  <div style={{ fontSize: "0.65rem", color: COLORS.red, marginTop: "2px" }}>Min 12 meses requerido</div>
                )}
              </div>
              <div>
                <label style={{ fontSize: "0.72rem", color: COLORS.textMuted, display: "block", marginBottom: "2px" }}>Tipo Codeudor</label>
                <select data-testid="predic-tipo-codeudor" value={advForm.tipo_codeudor} onChange={e => setAdvForm({...advForm, tipo_codeudor: e.target.value})}
                  style={{ ...S.input, width: "100%" }}>
                  <option value="0">Sin Codeudor</option>
                  <option value="1">Conyuge</option>
                  <option value="2">Consanguineo/Union Civil</option>
                  <option value="3">Tercero</option>
                </select>
              </div>
              {parseInt(advForm.tipo_codeudor) > 0 && (
                <>
                  <div>
                    <label style={{ fontSize: "0.72rem", color: COLORS.textMuted, display: "block", marginBottom: "2px" }}>Renta Codeudor (CLP)</label>
                    <input data-testid="predic-renta-codeudor" type="text" value={advForm.renta_codeudor} onChange={e => setAdvForm({...advForm, renta_codeudor: e.target.value})} style={S.input} placeholder="$0" />
                  </div>
                  <div>
                    <label style={{ fontSize: "0.72rem", color: COLORS.textMuted, display: "block", marginBottom: "2px" }}>Edad Codeudor</label>
                    <input data-testid="predic-edad-codeudor" type="number" value={advForm.edad_codeudor} onChange={e => setAdvForm({...advForm, edad_codeudor: e.target.value})} style={S.input} placeholder="0" />
                  </div>
                </>
              )}
            </div>
            <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
              {[["morosidad_dicom", "DICOM Vigente"], ["protestos_vigentes", "Protestos Vigentes"]].map(([key, label]) => (
                <label key={key} style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.8rem", color: advForm[key] ? COLORS.red : COLORS.textMuted, cursor: "pointer" }}>
                  <input type="checkbox" checked={advForm[key]} onChange={e => setAdvForm({...advForm, [key]: e.target.checked})} style={{ accentColor: COLORS.red }} /> {label}
                </label>
              ))}
              <label style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.8rem", color: advForm.continuidad_laboral ? COLORS.green : COLORS.red, cursor: "pointer" }}>
                <input type="checkbox" checked={advForm.continuidad_laboral} onChange={e => setAdvForm({...advForm, continuidad_laboral: e.target.checked})} style={{ accentColor: COLORS.green }} /> Continuidad Laboral
              </label>
            </div>
          </div>
        )}

        {/* Predict button */}
        <button data-testid="predic-calculate-btn" onClick={handlePredict} disabled={loading}
          style={{
            width: "100%", padding: "1rem", borderRadius: "2px", border: "none", fontSize: "1.1rem", fontWeight: 800, cursor: loading ? "wait" : "pointer",
            background: `linear-gradient(135deg, ${COLORS.accent}, #4834d4, ${COLORS.accent})`, backgroundSize: "200%",
            color: "#fff", letterSpacing: "1px", boxShadow: `0 4px 20px rgba(108,92,231,0.4)`,
            animation: loading ? "none" : undefined,
          }}>
          {loading ? "Calculando..." : "EVALUAR CREDITO"}
        </button>

        {/* Result */}
        {result && !result.error && <PredICResult result={result} onExportPDF={exportPDF} form={form} />}
        {result?.error && <div style={{ textAlign: "center", padding: "1.5rem", color: COLORS.red }}>Error al calcular</div>}

        {/* Compare with Competitors Button */}
        {result && !result.error && (
          <button data-testid="predic-comparar-btn" onClick={handleComparar} disabled={comparandoLoad}
            style={{ width: "100%", marginTop: "1rem", padding: "0.85rem", borderRadius: "2px", border: "2px solid rgba(212,175,55,0.4)", background: "linear-gradient(135deg, rgba(212,175,55,0.15), rgba(212,175,55,0.05))", color: COLORS.gold, fontWeight: 700, fontSize: "0.95rem", cursor: "pointer", transition: "all 0.3s" }}>
            <i className={`fa ${comparandoLoad ? "fa-spinner fa-spin" : "fa-balance-scale"}`} style={{ marginRight: "0.4rem" }}></i>
            {comparandoLoad ? "Comparando..." : "COMPARA CON COMPETIDORES"}
          </button>
        )}

        {/* Comparison Results */}
        {comparacion && (
          <div data-testid="predic-comparacion" style={{ marginTop: "1rem", borderRadius: "2px", overflow: "hidden", border: `2px solid rgba(212,175,55,0.3)`, background: COLORS.card }}>
            {/* Header with commercial message */}
            <div style={{ padding: "1.25rem", background: "linear-gradient(135deg, rgba(212,175,55,0.15), rgba(108,92,231,0.1))", borderBottom: `1px solid ${COLORS.border}` }}>
              <div data-testid="comparar-titular" style={{ fontSize: "1.15rem", fontWeight: 800, color: COLORS.gold, marginBottom: "0.3rem" }}>
                {comparacion.mensaje_comercial?.titular}
              </div>
              <div style={{ fontSize: "0.85rem", color: COLORS.textMuted, lineHeight: 1.5 }}>
                {comparacion.mensaje_comercial?.subtitulo}
              </div>
            </div>

            {/* Summary badges */}
            <div style={{ padding: "0.75rem 1.25rem", display: "flex", gap: "0.5rem", flexWrap: "wrap", borderBottom: `1px solid ${COLORS.border}` }}>
              {comparacion.datos_comparacion && (
                <span style={{ padding: "4px 10px", borderRadius: "2px", fontSize: "0.75rem", fontWeight: 600, background: "rgba(212,175,55,0.2)", color: COLORS.text }}>
                  Credito: {comparacion.datos_comparacion.monto_credito_uf} UF | {comparacion.datos_comparacion.plazo_anos} anos | Pie {comparacion.datos_comparacion.pie_pct}%
                </span>
              )}
              <span style={{ padding: "4px 10px", borderRadius: "2px", fontSize: "0.75rem", fontWeight: 700, background: "rgba(212,175,55,0.15)", color: COLORS.gold }}>
                Tu tasa: {comparacion.resumen?.tasa_mutuaria}%
              </span>
              <span style={{ padding: "4px 10px", borderRadius: "2px", fontSize: "0.75rem", fontWeight: 600, background: "rgba(108,92,231,0.12)", color: COLORS.accentLight }}>
                Promedio bancos: {comparacion.resumen?.tasa_promedio_bancos}%
              </span>
              {comparacion.resumen?.diferencia_dividendo_mensual > 0 && (
                <span style={{ padding: "4px 10px", borderRadius: "2px", fontSize: "0.75rem", fontWeight: 600, background: "rgba(0,184,148,0.12)", color: COLORS.green }}>
                  Diferencia: ${Math.abs(comparacion.resumen.diferencia_dividendo_mensual).toLocaleString("es-CL")}/mes
                </span>
              )}
            </div>

            {/* Competitors table */}
            <div style={{ padding: "0.75rem 1rem", maxHeight: "320px", overflowY: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.78rem" }}>
                <thead>
                  <tr style={{ borderBottom: `1px solid ${COLORS.border}` }}>
                    <th style={{ padding: "0.4rem", textAlign: "left", color: COLORS.textMuted, fontWeight: 600 }}>Banco</th>
                    <th style={{ padding: "0.4rem", textAlign: "center", color: COLORS.textMuted, fontWeight: 600 }}>Tasa</th>
                    <th style={{ padding: "0.4rem", textAlign: "right", color: COLORS.textMuted, fontWeight: 600 }}>Dividendo</th>
                    <th style={{ padding: "0.4rem", textAlign: "right", color: COLORS.gold, fontWeight: 700 }}>Div. + Seguros</th>
                  </tr>
                </thead>
                <tbody>
                  {comparacion.competidores?.map((c, i) => {
                    const totalSeguros = (seguros.seguro_desgravamen || 0) + (seguros.seguro_incendio || 0);
                    const divFinal = (c.dividendo_clp || 0) + totalSeguros;
                    return (
                      <tr key={i} style={{ borderBottom: `1px solid ${COLORS.border}` }}>
                        <td style={{ padding: "0.4rem", color: COLORS.text }}>{c.banco}</td>
                        <td style={{ padding: "0.4rem", textAlign: "center", color: c.tasa <= (comparacion.resumen?.tasa_mutuaria || 99) ? COLORS.green : COLORS.text }}>{c.tasa}%</td>
                        <td style={{ padding: "0.4rem", textAlign: "right", color: COLORS.textMuted, fontSize: "0.72rem" }}>${c.dividendo_clp?.toLocaleString("es-CL")}</td>
                        <td style={{ padding: "0.4rem", textAlign: "right", fontWeight: 700, color: COLORS.gold }}>${divFinal.toLocaleString("es-CL")}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div style={{ fontSize: "0.68rem", color: COLORS.textMuted, fontStyle: "italic", marginTop: "0.4rem", padding: "0.2rem 0" }}>
                <i className="fa fa-info-circle" style={{ marginRight: "0.3rem" }}></i>
                Div. + Seguros incluye Desgravamen (${(seguros.seguro_desgravamen || 0).toLocaleString("es-CL")}) + Incendio (${(seguros.seguro_incendio || 0).toLocaleString("es-CL")})
              </div>
            </div>

            {/* Key points */}
            <div style={{ padding: "0.75rem 1.25rem", background: "rgba(0,184,148,0.04)", borderTop: `1px solid ${COLORS.border}` }}>
              {comparacion.mensaje_comercial?.puntos_clave?.map((p, i) => (
                <div key={i} style={{ fontSize: "0.75rem", color: COLORS.textMuted, padding: "0.2rem 0", display: "flex", gap: "0.3rem" }}>
                  <i className="fa fa-check" style={{ color: COLORS.green, marginTop: "2px", fontSize: "0.65rem" }}></i> {p}
                </div>
              ))}
              <div style={{ fontSize: "0.82rem", fontWeight: 700, color: COLORS.gold, marginTop: "0.6rem", textAlign: "center", fontStyle: "italic" }}>
                "{comparacion.mensaje_comercial?.conclusion}"
              </div>
              <button data-testid="predic-comparar-pdf" onClick={async () => {
                try {
                  const r = await axios.post(`${API_URL}/api/inmobiliaria/comparar-pdf`, {
                    valor_propiedad_uf: parseFloat(form.valor_propiedad) || 2000,
                    monto_credito_uf: parseFloat(form.monto_credito) || 0,
                    pie_pct: 20,
                    plazo_anos: result?.plazo_anos || 30,
                    tasa_mutuaria: result?.tasa_aplicada || 6.5,
                    dividendo_mutuaria_uf: result?.dividendo_estimado_uf || 0,
                    dividendo_mutuaria_clp: result?.dividendo_estimado_clp || 0,
                    nombre_cliente: form.nombre_cliente || "Cliente",
                  }, { responseType: "blob" });
                  const url = URL.createObjectURL(new Blob([r.data], { type: "application/pdf" }));
                  const a = document.createElement("a"); a.href = url; a.download = `Comparativa_${(form.nombre_cliente || "Cliente").replace(/ /g,"_")}.pdf`; a.click();
                } catch {}
              }}
                style={{ width: "100%", marginTop: "0.75rem", padding: "0.7rem", borderRadius: "2px", border: "none", background: "linear-gradient(135deg, rgba(212,175,55,0.9), rgba(180,140,40,0.9))", color: "#fff", fontWeight: 700, fontSize: "0.85rem", cursor: "pointer" }}>
                <i className="fa fa-file-pdf-o" style={{ marginRight: "0.3rem" }}></i> DESCARGAR PDF COMPARATIVO
              </button>
            </div>
          </div>
        )}

        {/* Contact form - appears after result */}
        {result && !result.error && (
          <div data-testid="predic-contact-section" style={{ marginTop: "1.25rem", borderRadius: "2px", padding: "1.25rem", border: `1px solid ${COLORS.border}`, background: COLORS.card }}>
            {contactSent ? (
              <div data-testid="predic-contact-success" style={{ textAlign: "center", padding: "1rem" }}>
                <i className="fa fa-check-circle" style={{ fontSize: "2.5rem", color: COLORS.green }}></i>
                <div style={{ fontSize: "1.1rem", fontWeight: 700, color: COLORS.green, marginTop: "0.5rem" }}>Datos Enviados</div>
                <div style={{ fontSize: "0.85rem", color: COLORS.textMuted, marginTop: "0.3rem" }}>Un ejecutivo te contactara a la brevedad</div>
              </div>
            ) : (
              <>
                <div style={{ fontSize: "1rem", fontWeight: 700, color: COLORS.gold, marginBottom: "0.75rem", textAlign: "center" }}>
                  <i className="fa fa-phone"></i> Quiero que me contacten
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                  <input data-testid="predic-contact-nombre" placeholder="Tu nombre completo" value={contactForm.nombre}
                    onChange={e => setContactForm({...contactForm, nombre: e.target.value})}
                    style={S.input} />
                  <input data-testid="predic-contact-telefono" placeholder="Telefono (ej: +56 9 1234 5678)" value={contactForm.telefono}
                    onChange={e => setContactForm({...contactForm, telefono: e.target.value})}
                    style={S.input} />
                  <input data-testid="predic-contact-email" placeholder="Email (opcional)" value={contactForm.email}
                    onChange={e => setContactForm({...contactForm, email: e.target.value})}
                    style={S.input} />
                  <textarea data-testid="predic-contact-mensaje" placeholder="Mensaje (opcional)" value={contactForm.mensaje}
                    onChange={e => setContactForm({...contactForm, mensaje: e.target.value})}
                    rows={2} style={{...S.input, resize: "none"}} />
                  <button data-testid="predic-contact-btn" onClick={handleContact}
                    style={{ padding: "0.8rem", borderRadius: "2px", border: "none", background: `linear-gradient(135deg, ${COLORS.green}, #00a884)`, color: "#fff", fontWeight: 700, fontSize: "0.95rem", cursor: "pointer", boxShadow: `0 4px 15px rgba(0,184,148,0.3)` }}>
                    <i className="fa fa-paper-plane"></i> ENVIAR MIS DATOS
                  </button>
                </div>
              </>
            )}
          </div>
        )}

        {/* Debt Calculator */}
        <div style={{ marginTop: "1.5rem" }}>
          <button data-testid="predic-calc-toggle" onClick={() => setShowCalc(!showCalc)}
            style={{ width: "100%", padding: "0.65rem", borderRadius: "2px", border: `1px solid ${COLORS.border}`, background: "transparent", color: COLORS.accentLight, cursor: "pointer", fontSize: "0.85rem", fontWeight: 600 }}>
            <i className={`fa fa-calculator`}></i> Calculadora de Endeudamiento {showCalc ? "▲" : "▼"}
          </button>
          {showCalc && (
            <div data-testid="predic-debt-calculator" style={{ marginTop: "0.75rem", padding: "1rem", borderRadius: "2px", border: `1px solid ${COLORS.border}`, background: COLORS.card }}>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                <Field label="Monto de la Deuda" icon="fa-money" value={calcForm.monto_deuda} testId="predic-calc-monto"
                  onChange={v => setCalcForm({...calcForm, monto_deuda: v})} style={S.input} />
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <div style={{ flex: 1 }}>
                    <label style={{ fontSize: "0.75rem", color: COLORS.textMuted }}>Tasa Anual %</label>
                    <input data-testid="predic-calc-tasa" value={calcForm.tasa_anual}
                      onChange={e => setCalcForm({...calcForm, tasa_anual: e.target.value})}
                      style={{...S.input, textAlign: "center"}} />
                  </div>
                  <div style={{ flex: 1 }}>
                    <label style={{ fontSize: "0.75rem", color: COLORS.textMuted }}>Plazo (anos)</label>
                    <input data-testid="predic-calc-plazo" value={calcForm.plazo_anos}
                      onChange={e => setCalcForm({...calcForm, plazo_anos: e.target.value})}
                      style={{...S.input, textAlign: "center"}} />
                  </div>
                </div>
                <button data-testid="predic-calc-btn" onClick={handleCalc}
                  style={{ padding: "0.6rem", borderRadius: "2px", border: "none", background: `linear-gradient(135deg, ${COLORS.orange}, #e67e22)`, color: "#fff", fontWeight: 700, cursor: "pointer" }}>
                  CALCULAR CUOTA
                </button>
                {calcResult && (
                  <div data-testid="predic-calc-result" style={{ padding: "0.75rem", borderRadius: "2px", background: "rgba(243,156,18,0.1)", border: `1px solid rgba(243,156,18,0.3)`, marginTop: "0.3rem" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.9rem" }}>
                      <span style={{ color: COLORS.textMuted }}>Cuota Mensual:</span>
                      <span style={{ fontWeight: 700, color: COLORS.orange }}>{formatCLP(calcResult.cuota_mensual)}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", marginTop: "0.3rem" }}>
                      <span style={{ color: COLORS.textMuted }}>Total a Pagar:</span>
                      <span style={{ color: COLORS.text }}>{formatCLP(calcResult.total_a_pagar)}</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem" }}>
                      <span style={{ color: COLORS.textMuted }}>Total Intereses:</span>
                      <span style={{ color: COLORS.text }}>{formatCLP(calcResult.total_intereses)}</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <div style={{ textAlign: "center", marginTop: "2rem", color: COLORS.textMuted, fontSize: "0.7rem" }}>
          Central PREDIC - Powered by Central Mutuos
        </div>
      </div>}

      {/* Floating Chat Button - only if enabled */}
      {chatEnabled && (
        <button data-testid="predic-chat-fab" onClick={() => setShowChat(!showChat)}
          style={{ position: "fixed", bottom: "1.5rem", right: "1.5rem", width: "56px", height: "56px", borderRadius: "50%", border: "none", background: `linear-gradient(135deg, ${COLORS.accent}, ${COLORS.gold})`, color: "#fff", fontSize: "1.3rem", cursor: "pointer", boxShadow: "0 4px 20px rgba(108,92,231,0.4)", zIndex: 1000, transition: "transform 0.3s", transform: showChat ? "rotate(45deg)" : "none" }}>
          <i className={showChat ? "fa fa-times" : "fa fa-comments"}></i>
        </button>
      )}

      {/* Chat Panel */}
      {showChat && chatEnabled && (
        <div data-testid="predic-chat-panel" style={{ position: "fixed", bottom: "5rem", right: "1.5rem", width: "360px", maxHeight: "500px", borderRadius: "2px", background: COLORS.card, border: `2px solid ${COLORS.accent}`, boxShadow: "0 8px 40px rgba(0,0,0,0.4)", zIndex: 1000, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {/* Chat Header */}
          <div style={{ padding: "0.75rem 1rem", background: `linear-gradient(135deg, ${COLORS.accent}, rgba(108,92,231,0.8))`, display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <i className="fa fa-robot" style={{ color: "#fff", fontSize: "1.1rem" }}></i>
            <div>
              <div style={{ fontWeight: 700, color: "#fff", fontSize: "0.85rem" }}>Central IA</div>
              <div style={{ fontSize: "0.65rem", color: "rgba(255,255,255,0.7)" }}>Asistente para inmobiliarias</div>
            </div>
          </div>
          {/* Chat Messages */}
          <div style={{ flex: 1, overflowY: "auto", padding: "0.75rem", display: "flex", flexDirection: "column", gap: "0.5rem", maxHeight: "340px", minHeight: "200px" }}>
            {chatMessages.length === 0 && (
              <div style={{ textAlign: "center", padding: "1.5rem 0.5rem", color: COLORS.textMuted, fontSize: "0.8rem" }}>
                <i className="fa fa-comments-o" style={{ fontSize: "2rem", display: "block", marginBottom: "0.5rem", opacity: 0.4 }}></i>
                Hola, soy Central IA. Puedo ayudarte con consultas sobre creditos hipotecarios, tasas, subsidios y mas.
              </div>
            )}
            {chatMessages.map((m, i) => (
              <div key={i} style={{ display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start" }}>
                <div style={{ maxWidth: "85%", padding: "0.5rem 0.75rem", borderRadius: m.role === "user" ? "12px 12px 2px 12px" : "12px 12px 12px 2px", background: m.role === "user" ? COLORS.accent : "rgba(255,255,255,0.05)", color: m.role === "user" ? "#fff" : COLORS.text, fontSize: "0.82rem", lineHeight: 1.5, border: m.role === "user" ? "none" : `1px solid ${COLORS.border}` }}>
                  {m.content}
                </div>
              </div>
            ))}
            {chatLoading && (
              <div style={{ display: "flex", justifyContent: "flex-start" }}>
                <div style={{ padding: "0.5rem 0.75rem", borderRadius: "2px", background: "rgba(255,255,255,0.05)", border: `1px solid ${COLORS.border}`, fontSize: "0.8rem", color: COLORS.textMuted }}>
                  <i className="fa fa-spinner fa-spin"></i> Pensando...
                </div>
              </div>
            )}
          </div>
          {/* Chat Input */}
          <div style={{ padding: "0.5rem", borderTop: `1px solid ${COLORS.border}`, display: "flex", gap: "0.4rem" }}>
            <input data-testid="predic-chat-input" value={chatInput} onChange={e => setChatInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && sendChat()}
              placeholder="Escribe tu consulta..."
              style={{ flex: 1, padding: "0.5rem 0.75rem", borderRadius: "2px", border: `1px solid ${COLORS.border}`, background: "rgba(255,255,255,0.05)", color: COLORS.text, fontSize: "0.82rem", outline: "none" }} />
            <button data-testid="predic-chat-send" onClick={sendChat} disabled={chatLoading || !chatInput.trim()}
              style={{ padding: "0.5rem 0.75rem", borderRadius: "2px", border: "none", background: COLORS.accent, color: "#fff", cursor: "pointer", fontSize: "0.85rem" }}>
              <i className="fa fa-paper-plane"></i>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}


