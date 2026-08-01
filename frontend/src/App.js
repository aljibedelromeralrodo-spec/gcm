import { useState, useEffect, lazy, Suspense } from "react";
import axios from "axios";
import "./App.css";
import { API_URL, formatCurrency } from "./utils/formatters";
import LoginPage from "./pages/LoginPage";
import CentralPredic from "./pages/CentralPredic";
import PortalCliente from "./pages/PortalCliente";
import ShareTargetPage from "./pages/ShareTargetPage";
import PWAInstallPrompt from "./components/PWAInstallPrompt";

const DashboardModule = lazy(() => import("./pages/DashboardModule"));
const SimuladorModule = lazy(() => import("./pages/SimuladorModule"));
const HistorialModule = lazy(() => import("./pages/HistorialModule"));
const CalculadoraModule = lazy(() => import("./pages/CalculadoraModule"));
const FormatoModule = lazy(() => import("./pages/FormatoModule"));
const ClientesModule = lazy(() => import("./pages/ClientesModule"));
const CentralChat = lazy(() => import("./components/CentralChat"));
const SeguimientoModule = lazy(() => import("./pages/SeguimientoModule"));
const UsuariosModule = lazy(() => import("./pages/UsuariosModule"));
const CriteriosModule = lazy(() => import("./pages/CriteriosModule"));
const WhatsAppModule = lazy(() => import("./pages/WhatsAppModule"));
const AutocorreoModule = lazy(() => import("./pages/AutocorreoModule"));
const GastosOperacionalesModule = lazy(() => import("./pages/GastosOperacionalesModule"));
const AprobacionClienteModule = lazy(() => import("./pages/AprobacionClienteModule"));
const SetCreditoModule = lazy(() => import("./pages/SetCreditoModule"));
const EmailProcessingModule = lazy(() => import("./pages/EmailProcessingModule"));
const GlobalSearch = lazy(() => import("./components/GlobalSearch"));
const WelcomeTour = lazy(() => import("./components/WelcomeTour"));

const MODULE_TITLES = {
  dashboard: 'Dashboard',
  simulador: 'Simulador de Capacidad Crediticia',
  historial: 'Historial de Simulaciones',
  calculadora: 'Calculadora de Dividendo',
  formato: 'Formato',
  clientes: 'Carpeta Clientes',
  seguimiento: 'Seguimiento de Operaciones',
  usuarios: 'Gestion de Usuarios',
  criterios: 'Criterios de Evaluacion',
  'whatsapp': 'WhatsApp - Conexion y Aprobaciones',
  'autocorreo': 'Autocorreo - Reenvio Automatico de Aprobaciones',
  'procesamiento': 'Procesamiento de Correo',
  gastos: 'Gastos Operacionales',
  aprobacion: 'Envío Aprobación Cliente',
};

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
  const [valorUF, setValorUF] = useState(39842);
  const [loadedSimulation, setLoadedSimulation] = useState(null);
  const [whatsappStatus, setWhatsappStatus] = useState(null);
  const [emailNotif, setEmailNotif] = useState(0);
  const [carpetaAlerts, setCarpetaAlerts] = useState(0);
  const [showSearch, setShowSearch] = useState(false);
  const [showTour, setShowTour] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("user");
    if (saved) setUser(JSON.parse(saved));
    if (!localStorage.getItem("tour_done")) setShowTour(true);
  }, []);

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
    axios.get(`${API_URL}/api/valor-uf`).then(r => setValorUF(r.data.valor_uf)).catch(() => {});
    axios.get(`${API_URL}/api/whatsapp/status`).then(r => setWhatsappStatus(r.data)).catch(() => {});
    axios.get(`${API_URL}/api/central/email-summary`).then(r => setEmailNotif(r.data?.total || 0)).catch(() => {});
    const fetchAlerts = () =>
      axios.get(`${API_URL}/api/admin/alertas`)
        .then(r => setCarpetaAlerts((r.data?.alertas || []).filter(a => !a.leida).length))
        .catch(() => {});
    fetchAlerts();
    const t = setInterval(fetchAlerts, 60000);
    return () => clearInterval(t);
  }, [user]);

  const handleLoadSimulation = (sim) => {
    setLoadedSimulation(sim);
    setActiveModule('simulador');
  };

  const logout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setUser(null);
  };

  if (!user) return <LoginPage onLogin={setUser} />;

  const navItems = [
    { key: 'dashboard', icon: 'fa-th-large', label: 'Dashboard' },
    { key: 'clientes', icon: 'fa-folder-open', label: 'Carpeta Clientes' },
    { key: 'simulador', icon: 'fa-calculator', label: 'Simulador' },
    { key: 'historial', icon: 'fa-history', label: 'Historial' },
    { key: 'calculadora', icon: 'fa-percent', label: 'Calculadora' },
    { key: 'seguimiento', icon: 'fa-road', label: 'Seguimiento' },
    { key: 'formato', icon: 'fa-file-pdf-o', label: 'Formato' },
    { key: 'gastos', icon: 'fa-money', label: 'Gastos Operacionales' },
    { key: 'aprobacion', icon: 'fa-trophy', label: 'Aprobación Cliente' },
    { key: 'setcredito', icon: 'fa-pencil-square-o', label: 'Set de Crédito' },
    ...(user.rol === 'admin' ? [{ key: 'usuarios', icon: 'fa-user-plus', label: 'Usuarios' }] : []),
    ...(user.rol === 'admin' ? [{ key: 'criterios', icon: 'fa-shield', label: 'Criterios' }] : []),
    ...(user.rol === 'admin' ? [{ key: 'whatsapp', icon: 'fa-whatsapp', label: 'WhatsApp' }] : []),
    ...(user.rol === 'admin' ? [{ key: 'autocorreo', icon: 'fa-envelope-o', label: 'Autocorreo' }] : []),
    ...(user.rol === 'admin' ? [{ key: 'procesamiento', icon: 'fa-inbox', label: 'Procesamiento Correo' }] : []),
  ];

  return (
    <>
    <div className="dashboard-layout" data-testid="dashboard">
      {sidebarOpen && (
        <div
          className="mobile-backdrop"
          onClick={() => setSidebarOpen(false)}
          data-testid="mobile-backdrop"
        />
      )}
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`} data-testid="sidebar">
        <div className="sidebar-brand">
          <h2 className="sidebar-title">Central Mutuos</h2>
          <p className="sidebar-sub">Con Creces</p>
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
          <p className="sidebar-user-role">{user.rol}</p>
          <button onClick={logout} className="sidebar-logout" data-testid="btn-logout">Cerrar Sesión</button>
        </div>
      </aside>

      <main className="main-content">
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
            <p className="topbar-uf">UF: {formatCurrency(valorUF)}</p>
          </div>
          <div className="topbar-right">
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
            {emailNotif > 0 && (
              <button className="topbar-notif-btn" onClick={() => setActiveModule('dashboard')} data-testid="topbar-email-notif" title="Correos recientes">
                <i className="fa fa-bell"></i>
                <span className="topbar-notif-badge">{emailNotif}</span>
              </button>
            )}
            {whatsappStatus?.isReady && <span className="topbar-wa-badge" data-testid="wa-status">WhatsApp Conectado</span>}
          </div>
        </header>

        <Suspense fallback={<div style={{ textAlign: "center", padding: "4rem" }}><i className="fa fa-spinner fa-spin" style={{ fontSize: "2rem", color: "var(--gold)" }}></i></div>}>
        {activeModule === 'dashboard' && <DashboardModule valorUF={valorUF} userName={user?.nombre} onNavigate={setActiveModule} />}
        {activeModule === 'simulador' && <SimuladorModule valorUF={valorUF} loadedSimulation={loadedSimulation} />}
        {activeModule === 'historial' && <HistorialModule valorUF={valorUF} onLoadSimulation={handleLoadSimulation} />}
        {activeModule === 'calculadora' && <CalculadoraModule valorUF={valorUF} />}
        {activeModule === 'formato' && <FormatoModule />}
        {activeModule === 'clientes' && <ClientesModule onNavigate={setActiveModule} />}
        {activeModule === 'seguimiento' && <SeguimientoModule />}
        {activeModule === 'usuarios' && <UsuariosModule />}
        {activeModule === 'criterios' && <CriteriosModule />}
        {activeModule === 'whatsapp' && <WhatsAppModule />}
        {activeModule === 'autocorreo' && <AutocorreoModule />}
        {activeModule === 'procesamiento' && <EmailProcessingModule />}
        {activeModule === 'gastos' && <GastosOperacionalesModule onNavigate={setActiveModule} />}
        {activeModule === 'aprobacion' && <AprobacionClienteModule onNavigate={setActiveModule} />}
        {activeModule === 'setcredito' && <SetCreditoModule onNavigate={setActiveModule} />}
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
