import { useState, useEffect, lazy, Suspense } from "react";
import VistaPreviaRol from "./components/VistaPreviaRol";
import HeliceADN from "./components/HeliceADN";
import ProtectorPantalla from "./components/ProtectorPantalla";
import axios from "axios";
import "./App.css";
import { API_URL, formatCurrency } from "./utils/formatters";
import { secureGet, secureSet, secureRemove } from "./utils/secureStore";
import LoginPage from "./pages/LoginPage";
import CentralPredic from "./pages/CentralPredic";
import PortalCliente from "./pages/PortalCliente";
import ShareTargetPage from "./pages/ShareTargetPage";
import PWAInstallPrompt from "./components/PWAInstallPrompt";
import BriefingMananero from "./components/BriefingMananero";

const DashboardModule = lazy(() => import("./pages/DashboardModule"));
const SimuladorModule = lazy(() => import("./pages/SimuladorModule"));
const HistorialModule = lazy(() => import("./pages/HistorialModule"));
const CalculadoraModule = lazy(() => import("./pages/CalculadoraModule"));
const FormatoModule = lazy(() => import("./pages/FormatoModule"));
const ClientesModule = lazy(() => import("./pages/ClientesModule"));
const CentralChat = lazy(() => import("./components/CentralChat"));
const SeguimientoModule = lazy(() => import("./pages/SeguimientoModule"));
const UsuariosModule = lazy(() => import("./pages/UsuariosModule"));
const GerenciaComercialModule = lazy(() => import("./pages/GerenciaComercialModule"));
const AdministracionModule = lazy(() => import("./pages/AdministracionModule"));
const BrokersModule = lazy(() => import("./pages/BrokersModule"));
const MiCorreoModule = lazy(() => import("./pages/MiCorreoModule"));
const BaseHistoricaModule = lazy(() => import("./pages/BaseHistoricaModule"));
const SupercarpetaModule = lazy(() => import("./pages/SupercarpetaModule"));
const CriteriosModule = lazy(() => import("./pages/CriteriosModule"));
const WhatsAppModule = lazy(() => import("./pages/WhatsAppModule"));
const AutocorreoModule = lazy(() => import("./pages/AutocorreoModule"));
const GastosOperacionalesModule = lazy(() => import("./pages/GastosOperacionalesModule"));
const AprobacionClienteModule = lazy(() => import("./pages/AprobacionClienteModule"));
const SetCreditoModule = lazy(() => import("./pages/SetCreditoModule"));
const EmailProcessingModule = lazy(() => import("./pages/EmailProcessingModule"));
const CierresModule = lazy(() => import("./pages/CierresModule"));
const AprendizajeModule = lazy(() => import("./pages/AprendizajeModule"));
const SaludModule = lazy(() => import("./pages/SaludModule"));
const BuzonRescateModule = lazy(() => import("./pages/BuzonRescateModule"));
const OportunidadesModule = lazy(() => import("./pages/OportunidadesModule"));
const TasacionModule = lazy(() => import("./pages/TasacionModule"));
const EstudioTituloModule = lazy(() => import("./pages/EstudioTituloModule"));
const EscrituraModule = lazy(() => import("./pages/EscrituraModule"));
const ContraloriaModule = lazy(() => import("./pages/ContraloriaModule"));
const CerebroDashAIModule = lazy(() => import("./pages/CerebroDashAIModule"));
const ContralorModule = lazy(() => import("./pages/ContralorModule"));
const PostventaModule = lazy(() => import("./pages/PostventaModule"));
const RoleDashboard = lazy(() => import("./pages/RoleDashboards"));
const FrentePrincipal = lazy(() => import("./components/FrentePrincipal"));
const AuditoriaForenseModule = lazy(() => import("./pages/AuditoriaForenseModule"));
const DespachoModule = lazy(() => import("./pages/DespachoModule"));
const GlobalSearch = lazy(() => import("./components/GlobalSearch"));
const WelcomeTour = lazy(() => import("./components/WelcomeTour"));

const MODULE_TITLES = {
  dashboard: 'Dashboard',
  tasacion: 'Tasación',
  estudio: 'Estudio de Títulos',
  escritura: 'Escritura',
  contraloria: 'Contraloría',
  dashai: '🧠 Cerebro DashAI',
  auditoria: '📋 Auditoría Forense',
  despacho: '🚀 Despacho Veloz',
  simulador: 'Simulador de Capacidad Crediticia',
  historial: 'Historial de Simulaciones',
  calculadora: 'Calculadora de Dividendo',
  formato: 'Formato',
  clientes: 'Carpeta Clientes',
  seguimiento: 'Seguimiento de Operaciones',
  usuarios: 'Gestion de Usuarios',
  criterios: 'Criterios de Evaluacion',
  'whatsapp': 'WhatsApp - Conexion y Aprobaciones',
  'autocorreo': 'Correo a Mesa - Envío revisado directo a mesa',
  'procesamiento': 'Procesamiento de Correo',
  basehistorica: '🏛 Base de Datos Histórica — Archivo Nacional',
  gastos: 'Gastos Operacionales',
  aprobacion: 'Envío Aprobación Cliente',
  cierres: 'Cierres — Seguimiento de Aprobaciones',
  aprendizaje: 'Aprendizaje IA — Flujo Comercial',
  oportunidades: 'Centro de Ventas VIP — José Martín',
  postventa: 'Postventa — Seguimiento de Escritura',
  contralor: 'Módulo Contralor — Algoritmo Espejo',
  gerencia: 'Gerencia Comercial',
  supercarpeta: 'Supercarpeta',
  administracion: 'Administración',
};

// ═══ SISTEMA DE ROLES: acceso por módulo ('total' | 'lectura' | 'bloqueado') ═══
const MODS_ADMINISTRATIVOS = ['administracion', 'usuarios', 'criterios', 'whatsapp', 'autocorreo',
  'procesamiento', 'basehistorica', 'gastos', 'setcredito', 'formato', 'clientes', 'simulador',
  'historial', 'calculadora', 'seguimiento', 'aprobacion', 'tasacion', 'estudio', 'escritura',
  'cierres', 'salud', 'rescate', 'aprendizaje', 'oportunidades', 'dashai', 'auditoria', 'despacho'];
const MODS_TODOS = ['dashboard', ...MODS_ADMINISTRATIVOS, 'gerencia',
  'supercarpeta', 'brokers', 'micorreo', 'postventa', 'contraloria', 'contralor'];
const ACCESOS_ROL = {
  gerencia: { total: ['dashboard', 'gerencia', 'supercarpeta', 'postventa', 'micorreo'], lectura: MODS_ADMINISTRATIVOS },
  administracion: { total: ['dashboard', ...MODS_ADMINISTRATIVOS, 'micorreo'], lectura: ['contralor'] },
  postventa: { total: ['dashboard', 'postventa', 'micorreo'], lectura: ['contralor'] },
  broker: { total: ['dashboard', 'brokers', 'micorreo'], lectura: [] },
  contralor: { total: ['contralor', 'dashboard'], lectura: MODS_TODOS },
};
const PERMISOS_LEGADO = {
  A: ['dashboard', 'clientes', 'simulador', 'historial', 'calculadora', 'formato', 'setcredito', 'micorreo'],
  B: ['dashboard', 'contraloria', 'criterios', 'seguimiento', 'gerencia', 'supercarpeta', 'administracion', 'salud', 'micorreo'],
  D: ['brokers', 'micorreo'],
};

function accesoModulo(user, key) {
  if (key === 'contraloria') return 'lectura'; // MÓDULO CONTROL: solo lectura SIN EXCEPCIÓN
  if (['admin', 'maestro'].includes(user.rol)) return 'total';
  const A = ACCESOS_ROL[user.rol];
  if (!A) {
    if (!user.perfil) return 'total';
    return (PERMISOS_LEGADO[user.perfil] || []).includes(key) ? 'total' : 'bloqueado';
  }
  if (A.total.includes(key)) return 'total';
  if (A.lectura.includes(key)) return 'lectura';
  return 'bloqueado';
}

function App() {
  const path = window.location.pathname;
  if (path === "/predic") return <CentralPredic />;
  if (path === "/portal") return <PortalCliente />;
  if (path === "/share-target") return <ShareTargetPage />;
  return <MainApp />;
}

function MainApp() {
  const [user, setUser] = useState(null);
  const [activeModule, setActiveModule] = useState("dashboard");
  // 👁 VISTA PREVIA POR ROL — exclusiva del Admin (sesión de fondo intacta)
  const [previewRol, setPreviewRol] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem("preview_rol") || "null"); } catch { return null; }
  });
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [valorUF, setValorUF] = useState(39842);
  const [ufMeta, setUfMeta] = useState(null);
  const [loadedSimulation, setLoadedSimulation] = useState(null);
  const [whatsappStatus, setWhatsappStatus] = useState(null);
  const [emailNotif, setEmailNotif] = useState(0);
  const [carpetaAlerts, setCarpetaAlerts] = useState(0);
  const [cierresAvisos, setCierresAvisos] = useState(0);
  const [showSearch, setShowSearch] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [fsMenuVisible, setFsMenuVisible] = useState(false);

  useEffect(() => {
    const fn = () => { setFullscreen(!!document.fullscreenElement); setFsMenuVisible(false); };
    document.addEventListener("fullscreenchange", fn);
    return () => document.removeEventListener("fullscreenchange", fn);
  }, []);

  // En pantalla completa: ocultar el menú al alejar el cursor del borde izquierdo
  useEffect(() => {
    if (!fullscreen || !fsMenuVisible) return;
    const fn = (e) => { if (e.clientX > 300) setFsMenuVisible(false); };
    window.addEventListener("mousemove", fn);
    return () => window.removeEventListener("mousemove", fn);
  }, [fullscreen, fsMenuVisible]);

  const toggleFullscreen = () => {
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => {});
    } else {
      document.documentElement.requestFullscreen().catch(() => {});
    }
  };
  const [showTour, setShowTour] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [energia, setEnergia] = useState(null);
  const [showCargarSaldo, setShowCargarSaldo] = useState(false);
  const [saldoInput, setSaldoInput] = useState("");

  useEffect(() => {
    const saved = secureGet("user");
    if (saved) {
      setUser(saved);
      // Hidratar el cargo oficial desde el backend (sesiones anteriores sin el campo)
      axios.get(`${API_URL}/api/auth/mi-perfil`).then(r => {
        if (r.data?.cargo && r.data.cargo !== saved.cargo) {
          const nu = { ...saved, cargo: r.data.cargo };
          setUser(nu);
          secureSet("user", nu);
        }
      }).catch(() => {});
    }
    if (!localStorage.getItem("tour_done")) setShowTour(true);
  }, []);

  const editarCargo = async () => {
    const nuevo = window.prompt("Cargo oficial del Administrador (fijo e inamovible por otros usuarios):", user?.cargo || "");
    if (!nuevo || !nuevo.trim()) return;
    try {
      const r = await axios.post(`${API_URL}/api/auth/mi-cargo`, { cargo: nuevo.trim() });
      const nu = { ...user, cargo: r.data.cargo };
      setUser(nu);
      secureSet("user", nu);
    } catch (e) { window.alert(e.response?.data?.detail || "No fue posible actualizar el cargo. Intente nuevamente."); }
  };

  // Close mobile sidebar on resize to desktop
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth > 1024) setSidebarOpen(false);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    const handler = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setShowSearch(p => !p);
      }
      if (e.key === 'Escape') setShowSearch(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  useEffect(() => {
    if (!user) return;
    const cargarUF = () => axios.get(`${API_URL}/api/valor-uf`)
      .then(r => { if (r.data?.valor_uf > 0) { setValorUF(r.data.valor_uf); setUfMeta(r.data); } })
      .catch((e) => console.error(e));
    cargarUF();
    const tUF = setInterval(cargarUF, 300000); // re-sincroniza la UF cada 5 min
    const cargarEnergia = () => axios.get(`${API_URL}/api/energia`).then(r => setEnergia(r.data)).catch(() => {});
    cargarEnergia();
    const tEne = setInterval(cargarEnergia, 120000);
    axios.get(`${API_URL}/api/whatsapp/status`).then(r => setWhatsappStatus(r.data)).catch((e) => console.error(e));
    axios.get(`${API_URL}/api/central/email-summary`).then(r => setEmailNotif(r.data?.total || 0)).catch((e) => console.error(e));
    const fetchAlerts = () => {
      axios.get(`${API_URL}/api/admin/alertas`)
        .then(r => setCarpetaAlerts((r.data?.alertas || []).filter(a => !a.leida).length))
        .catch((e) => console.error(e));
      axios.get(`${API_URL}/api/cierres/avisos`)
        .then(r => setCierresAvisos(r.data?.total || 0))
        .catch((e) => console.error(e));
    };
    fetchAlerts();
    const t = setInterval(fetchAlerts, 60000);
    return () => { clearInterval(t); clearInterval(tUF); clearInterval(tEne); };
  }, [user]);

  useEffect(() => {
    if (user?.perfil === 'D' || user?.rol === 'broker' || previewRol?.rol === 'broker') setActiveModule('brokers');
  }, [user, previewRol]);

  useEffect(() => {
    // Los cambios en simulación viajan con esta cabecera → log de auditoría backend
    if (previewRol) {
      axios.defaults.headers.common["X-Simula-Rol"] = previewRol.label;
      sessionStorage.setItem("preview_rol", JSON.stringify(previewRol));
    } else {
      delete axios.defaults.headers.common["X-Simula-Rol"];
      sessionStorage.removeItem("preview_rol");
    }
  }, [previewRol]);

  const cargarSaldoEnergia = () => {
    const s = parseFloat(saldoInput);
    if (!(s >= 0)) return;
    axios.post(`${API_URL}/api/energia/cargar`, { saldo: s })
      .then(r => { setEnergia(r.data); setShowCargarSaldo(false); setSaldoInput(""); })
      .catch((e) => console.error(e));
  };

  const handleLoadSimulation = (sim) => {
    setLoadedSimulation(sim);
    setActiveModule('simulador');
  };

  const logout = () => {
    secureRemove("token");
    secureRemove("user");
    setUser(null);
  };

  const esAdminReal = ["admin", "maestro"].includes(user?.rol || "");
  const uEff = (user && previewRol && esAdminReal)
    ? { ...user, rol: previewRol.rol, perfil: previewRol.perfil || "", _sim: previewRol.label }
    : user;

  if (!user) return <LoginPage onLogin={setUser} />;

  // REGLA UNIVERSAL: todos los roles ven TODOS los módulos en el menú.
  // El ingreso a un módulo no autorizado muestra el aviso, jamás un error técnico.
  const navItems = [
    { key: 'dashboard', icon: 'fa-th-large', label: 'Dashboard' },
    { key: 'clientes', icon: 'fa-folder-open', label: 'Carpeta Clientes' },
    { key: 'simulador', icon: 'fa-calculator', label: 'Simulador Inmobiliario' },
    { key: 'historial', icon: 'fa-history', label: 'Historial' },
    { key: 'calculadora', icon: 'fa-percent', label: 'Calculadora' },
    { key: 'seguimiento', icon: 'fa-road', label: 'Seguimiento' },
    { key: 'formato', icon: 'fa-file-pdf-o', label: 'Formato' },
    { key: 'gastos', icon: 'fa-money', label: 'Gastos Operacionales' },
    { key: 'aprobacion', icon: 'fa-trophy', label: 'Aprobación Cliente' },
    { key: 'tasacion', icon: 'fa-home', label: 'Tasación' },
    { key: 'estudio', icon: 'fa-balance-scale', label: 'Estudio de Títulos' },
    { key: 'escritura', icon: 'fa-pencil-square-o', label: 'Escritura' },
    { key: 'contraloria', icon: 'fa-search', label: 'Módulo Control 👁' },
    { key: 'contralor', icon: 'fa-eye', label: 'Módulo Contralor' },
    { key: 'postventa', icon: 'fa-heart', label: 'Postventa' },
    { key: 'dashai', icon: 'fa-lightbulb-o', label: '🧠 Cerebro DashAI' },
    { key: 'auditoria', icon: 'fa-balance-scale', label: '📋 Auditoría Forense' },
    { key: 'despacho', icon: 'fa-rocket', label: '🚀 Despacho Veloz' },
    { key: 'cierres', icon: 'fa-handshake-o', label: 'Cierres' },
    { key: 'oportunidades', icon: 'fa-diamond', label: 'Centro de Ventas VIP' },
    { key: 'salud', icon: 'fa-heartbeat', label: 'Panel de Salud' },
    { key: 'rescate', icon: 'fa-life-ring', label: 'Por Clasificar' },
    { key: 'aprendizaje', icon: 'fa-graduation-cap', label: 'Aprendizaje IA' },
    { key: 'setcredito', icon: 'fa-pencil-square-o', label: 'Set de Crédito' },
    { key: 'usuarios', icon: 'fa-user-plus', label: 'Usuarios' },
    { key: 'criterios', icon: 'fa-shield', label: 'Criterios' },
    { key: 'whatsapp', icon: 'fa-whatsapp', label: 'WhatsApp' },
    { key: 'autocorreo', icon: 'fa-envelope-o', label: 'Correo a Mesa' },
    { key: 'procesamiento', icon: 'fa-inbox', label: 'Procesamiento Correo' },
    { key: 'basehistorica', icon: 'fa-university', label: 'Base de Datos Histórica' },
    { key: 'gerencia', icon: 'fa-line-chart', label: 'Gerencia Comercial' },
    { key: 'supercarpeta', icon: 'fa-folder-open', label: 'Supercarpeta' },
    { key: 'administracion', icon: 'fa-database', label: 'Administración' },
    { key: 'brokers', icon: 'fa-briefcase', label: 'Panel Broker' },
    { key: 'micorreo', icon: 'fa-envelope', label: 'Mi Correo' },
  ];
  const acceso = accesoModulo(uEff, activeModule);

  return (
    <>
    {uEff?._sim && (
      <div data-testid="preview-bar" style={{ position: "fixed", top: 0, left: 0, right: 0, zIndex: 4000,
        background: "linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C)", color: "#0a0a0a",
        display: "flex", alignItems: "center", gap: 12, padding: "0.45rem 1rem",
        fontWeight: 900, fontSize: "0.76rem", letterSpacing: 0.5, boxShadow: "0 2px 14px rgba(0,0,0,0.45)" }}>
        <i className="fa fa-eye"></i>
        <span>MODO VISTA PREVIA — Simulando rol: {uEff._sim} · sesión Admin activa · sus cambios quedan auditados</span>
        <button data-testid="preview-volver-admin" onClick={() => setPreviewRol(null)}
          style={{ marginLeft: "auto", background: "#0a0a0a", color: "#FCF6BA", border: "none",
            borderRadius: 8, padding: "0.35rem 1rem", fontWeight: 900, cursor: "pointer",
            fontSize: "0.7rem", whiteSpace: "nowrap" }}>⬅ Volver a Admin</button>
      </div>
    )}
    <div className="dashboard-layout" data-testid="dashboard" style={uEff?._sim ? { paddingTop: 40 } : undefined}>
      <ProtectorPantalla user={user} />
      {fullscreen && (
        <div data-testid="fs-hover-zone" onMouseEnter={() => setFsMenuVisible(true)}
          style={{ position: "fixed", top: 0, bottom: 0, left: 0, width: 14, zIndex: 99 }} />
      )}
      {sidebarOpen && (
        <div
          className="mobile-backdrop"
          onClick={() => setSidebarOpen(false)}
          data-testid="mobile-backdrop"
        />
      )}
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''} ${fullscreen ? 'fs-auto' : ''} ${fullscreen && fsMenuVisible ? 'fs-visible' : ''}`}
        data-testid="sidebar" onMouseLeave={() => fullscreen && setFsMenuVisible(false)}>
        <div className="sidebar-brand" data-testid="sidebar-logo" style={{ background: "#0a0a0a",
          borderRadius: 10, padding: "0.95rem 0.5rem", textAlign: "center",
          border: "1px solid rgba(212,175,55,0.25)" }}>
          <div style={{ fontFamily: "'Playfair Display', serif", fontWeight: 700, fontSize: "1.06rem",
            letterSpacing: 2, whiteSpace: "nowrap",
            background: "linear-gradient(135deg,#BF953F,#FCF6BA,#B38728,#FBF5B7,#AA771C)",
            WebkitBackgroundClip: "text", backgroundClip: "text", WebkitTextFillColor: "transparent",
            filter: "drop-shadow(0 1px 12px rgba(191,149,63,0.55))" }}>CENTRAL MUTUOS</div>
          <div style={{ height: 1.5, margin: "7px auto 5px", width: "92%",
            background: "linear-gradient(90deg,transparent,#d4af37 20%,#d4af37 80%,transparent)" }} />
          <div style={{ fontFamily: "'Playfair Display', serif", color: "#d4af37",
            fontSize: "0.44rem", letterSpacing: 4.5, fontWeight: 400 }}>CON CRECES</div>
        </div>
        <nav className="sidebar-nav">
          {navItems.map(item => (
            <button key={item.key} className={`sidebar-item ${activeModule === item.key ? 'active' : ''}`} onClick={() => { setActiveModule(item.key); setSidebarOpen(false); }} data-testid={`nav-${item.key}`}>
              <span className="sidebar-icon"><i className={`fa ${item.icon}`}></i></span> {item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-user">
          <p className="sidebar-user-name">{user.nombre}</p>
          <p className="sidebar-user-role">{({ admin: 'Administrador', maestro: 'Administrador',
            gerencia: 'Gerencia Comercial', administracion: 'Administración', postventa: 'Postventa',
            contralor: 'Contralor', broker: 'Broker', ejecutivo: uEff.perfil === 'D' ? 'Broker' : 'Administración' }[uEff.rol]) || uEff.rol}
            {uEff._sim && <span style={{ display: "block", color: "#d4af37", fontSize: "0.56rem", fontWeight: 900 }}>👁 SIMULACIÓN</span>}</p>
          {user.cargo && (
            <p data-testid="sidebar-user-cargo" style={{ fontSize: "0.58rem", color: "#b8a04a",
              lineHeight: 1.5, margin: "4px 0 6px" }}>
              {user.cargo}
              {(user.rol === "admin" || user.rol === "maestro") && (
                <button data-testid="btn-editar-cargo" onClick={editarCargo}
                  title="Editar cargo oficial (solo el Administrador)"
                  style={{ background: "none", border: "none", color: "#d4af37",
                    cursor: "pointer", fontSize: "0.66rem", marginLeft: 4, padding: 0 }}>✎</button>
              )}
            </p>
          )}
          <button onClick={logout} className="sidebar-logout" data-testid="btn-logout">Cerrar Sesión</button>
        </div>
      </aside>

      <main className={`main-content ${fullscreen ? 'fs-full' : ''}`}>
        <header className="topbar">
          <button
            className="mobile-menu-btn"
            onClick={() => setSidebarOpen(p => !p)}
            data-testid="mobile-menu-btn"
            aria-label="Menu"
          >
            <i className={`fa ${sidebarOpen ? 'fa-times' : 'fa-bars'}`}></i>
          </button>
          <div>
            <h1 className="topbar-title">{MODULE_TITLES[activeModule] || 'Dashboard'}</h1>
            <p className="topbar-uf" data-testid="topbar-uf">UF: {formatCurrency(valorUF)}
              {ufMeta?.fuente === "sii.cl" && (
                <span style={{ display: "block", fontSize: "0.58rem", opacity: 0.65, letterSpacing: "0.04em" }}>
                  Fuente: SII.cl · Actualizado: {(ufMeta.actualizado || "").slice(11, 16) || "—"}
                </span>
              )}
            </p>
          </div>
          <div className="topbar-right">
            <button className="topbar-notif-btn" data-testid="btn-fullscreen" title={fullscreen ? "Salir de pantalla completa (Esc)" : "Pantalla completa"}
              onClick={toggleFullscreen} style={{ color: "var(--gold, #d4af37)" }}>
              <i className={`fa ${fullscreen ? "fa-compress" : "fa-expand"}`}></i>
            </button>
            <div className="global-search-wrap">
              <button className="global-search-trigger" onClick={() => setShowSearch(p => !p)} data-testid="global-search-btn" title="Buscar (Ctrl+K)">
                <i className="fa fa-search"></i>
                <span className="global-search-hint">Ctrl+K</span>
              </button>
            </div>
            {carpetaAlerts > 0 && (
              <button className="topbar-notif-btn" onClick={() => setActiveModule('clientes')} data-testid="topbar-carpeta-alert" title="Carpetas listas para enviar a mesa" style={{ color: "#22c55e" }}>
                <i className="fa fa-folder-open"></i>
                <span className="topbar-notif-badge" style={{ background: "#22c55e" }}>{carpetaAlerts}</span>
              </button>
            )}
            {cierresAvisos > 0 && (
              <button className="topbar-notif-btn" data-testid="topbar-cierres-aviso" title="Respuestas de ejecutivos en Cierres"
                onClick={() => { setActiveModule('cierres'); axios.post(`${API_URL}/api/cierres/avisos/marcar`).then(() => setCierresAvisos(0)).catch((e) => console.error(e)); }}
                style={{ color: "#0d9488" }}>
                <i className="fa fa-handshake-o"></i>
                <span className="topbar-notif-badge" style={{ background: "#0d9488" }}>{cierresAvisos}</span>
              </button>
            )}
            {emailNotif > 0 && (
              <button className="topbar-notif-btn" onClick={() => setActiveModule('dashboard')} data-testid="topbar-email-notif" title="Correos recientes">
                <i className="fa fa-bell"></i>
                <span className="topbar-notif-badge">{emailNotif}</span>
              </button>
            )}
            {whatsappStatus?.isReady && <span className="topbar-wa-badge" data-testid="wa-status">WhatsApp Conectado</span>}
            {esAdminReal && !previewRol && (
              <button data-testid="btn-vista-previa-rol" onClick={() => setShowPreviewModal(true)}
                title="Vista previa por rol — exclusivo del Administrador"
                style={{ background: "rgba(212,175,55,0.12)", border: "1px solid rgba(212,175,55,0.5)",
                  color: "#d4af37", borderRadius: 20, padding: "0.28rem 0.75rem", cursor: "pointer",
                  fontSize: "0.68rem", fontWeight: 800, whiteSpace: "nowrap" }}>
                <i className="fa fa-eye" style={{ marginRight: 5 }}></i>Vista previa por rol
              </button>
            )}
            <button data-testid="energia-indicador" onClick={() => setShowCargarSaldo(true)} title="Reserva de funcionamiento — clic para cargar saldo"
              style={{ background: energia?.nivel === "critico" ? "rgba(239,68,68,0.18)" : energia?.nivel === "bajo" ? "rgba(245,158,11,0.16)" : "rgba(16,201,138,0.12)",
                border: `1px solid ${energia?.nivel === "critico" ? "#ef4444" : energia?.nivel === "bajo" ? "#f59e0b" : "#10c98a"}`,
                color: energia?.nivel === "critico" ? "#fb7185" : energia?.nivel === "bajo" ? "#fbbf24" : "#10c98a",
                borderRadius: 20, padding: "0.28rem 0.75rem", cursor: "pointer", fontSize: "0.68rem", fontWeight: 800, whiteSpace: "nowrap" }}>
              <i className="fa fa-bolt" style={{ marginRight: 5 }}></i>
              {energia?.saldo_inicial > 0 ? `${Math.round(energia.saldo_actual)} cr · ${energia.dias_autonomia}d` : "Cargar saldo"}
            </button>
          </div>
        </header>
        {energia?.banner && (
          <div data-testid="energia-banner" style={{ background: energia.nivel === "critico" ? "#7f1d1d" : "#78350f",
            color: "#fff", padding: "0.6rem 1.2rem", fontSize: "0.8rem", fontWeight: 700, display: "flex",
            alignItems: "center", gap: 12, borderBottom: "1px solid rgba(255,255,255,0.15)" }}>
            <i className="fa fa-exclamation-triangle"></i>
            <span>{energia.banner}</span>
            <button data-testid="energia-banner-recargar" onClick={() => setShowCargarSaldo(true)}
              style={{ marginLeft: "auto", background: "#fff", color: "#111", border: "none", borderRadius: 6,
                padding: "0.3rem 0.9rem", fontWeight: 800, cursor: "pointer", fontSize: "0.72rem" }}>Actualizar saldo</button>
          </div>
        )}
        {showCargarSaldo && (
          <div data-testid="energia-modal" onClick={() => setShowCargarSaldo(false)}
            style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", zIndex: 500, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <div onClick={e => e.stopPropagation()} style={{ background: "#111214", border: "1px solid rgba(212,175,55,0.4)", borderRadius: 12, padding: "1.6rem 1.8rem", width: 380, maxWidth: "90vw" }}>
              <h3 style={{ color: "#d4af37", margin: "0 0 6px", fontSize: "1rem" }}>⚡ Reserva de Funcionamiento</h3>
              <p style={{ color: "#94a3b8", fontSize: "0.72rem", margin: "0 0 14px", lineHeight: 1.5 }}>
                Ingrese su saldo actual de créditos (Perfil → Manage Plan → Universal Key). El sistema descuenta el consumo real por cada llamada de IA y proyecta su autonomía a {energia?.consumo_dia || 9} créditos/día.
              </p>
              {energia?.saldo_inicial > 0 && (
                <div style={{ background: "rgba(255,255,255,0.04)", borderRadius: 8, padding: "0.7rem 0.9rem", marginBottom: 14, fontSize: "0.74rem", color: "#cbd5e1" }}>
                  Saldo estimado: <b style={{ color: "#fff" }}>{Math.round(energia.saldo_actual)} cr</b> · Gasto: {energia.gasto_estimado} cr · Autonomía: <b>{energia.dias_autonomia} día(s)</b> · Llamadas IA: {energia.llamadas_llm}
                </div>
              )}
              <input data-testid="energia-input-saldo" type="number" value={saldoInput} onChange={e => setSaldoInput(e.target.value)}
                placeholder="Ej: 150" autoFocus
                style={{ width: "100%", boxSizing: "border-box", background: "rgba(255,255,255,0.06)", border: "1px solid rgba(212,175,55,0.4)", color: "#fff", padding: "0.6rem 0.8rem", borderRadius: 8, fontSize: "0.9rem", marginBottom: 12 }} />
              <div style={{ display: "flex", gap: 8 }}>
                <button data-testid="energia-guardar-saldo" onClick={cargarSaldoEnergia}
                  style={{ flex: 1, background: "linear-gradient(135deg,#BF953F,#FCF6BA,#AA771C)", color: "#0a0a0a", border: "none", borderRadius: 8, padding: "0.6rem", fontWeight: 800, cursor: "pointer" }}>Guardar saldo</button>
                <button onClick={() => setShowCargarSaldo(false)}
                  style={{ background: "transparent", color: "#94a3b8", border: "1px solid rgba(255,255,255,0.2)", borderRadius: 8, padding: "0.6rem 1rem", cursor: "pointer" }}>Cerrar</button>
              </div>
            </div>
          </div>
        )}

        {showPreviewModal && esAdminReal && (
          <VistaPreviaRol onClose={() => setShowPreviewModal(false)}
            onActivar={(r) => { setPreviewRol(r); setShowPreviewModal(false); setActiveModule("dashboard"); }} />
        )}

        <BriefingMananero user={uEff} />
        <Suspense fallback={<div style={{ textAlign: "center", padding: "4rem" }}><i className="fa fa-spinner fa-spin" style={{ fontSize: "2rem", color: "var(--gold)" }}></i></div>}>
        {acceso === 'bloqueado' ? (
          <div data-testid="no-autorizado" style={{ display: "grid", placeItems: "center", minHeight: "50vh" }}>
            <div style={{ textAlign: "center", background: "rgba(30,41,59,0.6)", border: "1px solid rgba(248,113,113,0.4)",
              borderRadius: 16, padding: "2.5rem 3rem", maxWidth: 480 }}>
              <i className="fa fa-lock" style={{ fontSize: 40, color: "#f87171" }}></i>
              <h2 style={{ color: "#f8fafc", fontSize: "1.15rem", marginTop: 14 }}>No está autorizado el ingreso a este módulo</h2>
              <p style={{ color: "#94a3b8", fontSize: "0.85rem", marginTop: 8 }}>
                Su rol ({uEff.rol}) no tiene permisos sobre este módulo. Si necesita acceso, contacte al Administrador.</p>
            </div>
          </div>
        ) : (<>
        {acceso === 'lectura' && (
          <div data-testid="banner-lectura" style={{ background: "rgba(203,213,225,0.1)", border: "1px dashed #cbd5e1",
            borderRadius: 10, padding: "0.5rem 1rem", marginBottom: 12, color: "#e2e8f0", fontSize: "0.8rem", fontWeight: 700 }}>
            👁 MODO LECTURA — su rol puede visualizar este módulo pero no ejercer cambios.</div>
        )}
        {activeModule === 'dashboard' && ['admin', 'maestro', 'gerencia'].includes(uEff.rol) && <HeliceADN conTelepantalla={['admin', 'maestro'].includes(uEff.rol)} />}
        {activeModule === 'dashboard' && (
          ['gerencia', 'administracion', 'postventa', 'contralor', 'broker'].includes(uEff.rol)
            ? <>
                {uEff.rol === 'gerencia' && <FrentePrincipal rol={uEff.rol} />}
                <RoleDashboard rol={uEff.rol} nombre={user.nombre} onNavigate={setActiveModule} />
              </>
            : <>
                <FrentePrincipal rol={uEff.rol} />
                <DashboardModule valorUF={valorUF} userName={user?.nombre} onNavigate={setActiveModule} />
              </>)}
        {activeModule === 'simulador' && <SimuladorModule valorUF={valorUF} loadedSimulation={loadedSimulation} />}
        {activeModule === 'historial' && <HistorialModule valorUF={valorUF} onLoadSimulation={handleLoadSimulation} />}
        {activeModule === 'calculadora' && <CalculadoraModule valorUF={valorUF} />}
        {activeModule === 'formato' && <FormatoModule />}
        {activeModule === 'clientes' && <ClientesModule onNavigate={setActiveModule} />}
        {activeModule === 'seguimiento' && <SeguimientoModule />}
        {activeModule === 'usuarios' && <UsuariosModule />}
        {activeModule === 'gerencia' && <GerenciaComercialModule />}
        {activeModule === 'administracion' && <AdministracionModule user={uEff} />}
        {activeModule === 'brokers' && <BrokersModule user={uEff} />}
        {activeModule === 'micorreo' && <MiCorreoModule user={uEff} />}
        {activeModule === 'supercarpeta' && <SupercarpetaModule />}
        {activeModule === 'basehistorica' && <BaseHistoricaModule />}
        {activeModule === 'criterios' && <CriteriosModule />}
        {activeModule === 'whatsapp' && <WhatsAppModule />}
        {activeModule === 'autocorreo' && <AutocorreoModule />}
        {activeModule === 'procesamiento' && <EmailProcessingModule />}
        {activeModule === 'gastos' && <GastosOperacionalesModule onNavigate={setActiveModule} />}
        {activeModule === 'aprobacion' && <AprobacionClienteModule onNavigate={setActiveModule} />}
        {activeModule === 'setcredito' && <SetCreditoModule onNavigate={setActiveModule} />}
        {activeModule === 'cierres' && <CierresModule />}
        {activeModule === 'salud' && <SaludModule />}
        {activeModule === 'rescate' && <BuzonRescateModule />}
        {activeModule === 'aprendizaje' && <AprendizajeModule />}
        {activeModule === 'oportunidades' && <OportunidadesModule />}
        {activeModule === 'tasacion' && <TasacionModule />}
        {activeModule === 'estudio' && <EstudioTituloModule />}
        {activeModule === 'escritura' && <EscrituraModule onNavigate={setActiveModule} />}
        {activeModule === 'contraloria' && <ContraloriaModule />}
        {activeModule === 'contralor' && <ContralorModule user={uEff} />}
        {activeModule === 'postventa' && <PostventaModule user={uEff} />}
        {activeModule === 'dashai' && <CerebroDashAIModule />}
        {activeModule === 'auditoria' && <AuditoriaForenseModule />}
        {activeModule === 'despacho' && <DespachoModule />}
        </>)}
        </Suspense>
      </main>
    </div>

    <Suspense fallback={null}>
      <CentralChat userName={user?.nombre || ""} activeModule={activeModule} />
    </Suspense>

    {showSearch && (
      <Suspense fallback={null}>
        <GlobalSearch
          onNavigate={(mod) => { setActiveModule(mod); setShowSearch(false); }}
          onClose={() => setShowSearch(false)}
        />
      </Suspense>
    )}

    {showTour && user && (
      <Suspense fallback={null}>
        <WelcomeTour onClose={() => { setShowTour(false); localStorage.setItem("tour_done", "1"); }} />
      </Suspense>
    )}
    <PWAInstallPrompt />
    </>
  );
}

export default App;
