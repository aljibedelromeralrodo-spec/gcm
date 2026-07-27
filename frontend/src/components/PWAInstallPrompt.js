import { useState, useEffect } from "react";

export default function PWAInstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] = useState(null);
  const [showPrompt, setShowPrompt] = useState(false);
  const [isInstalled, setIsInstalled] = useState(false);

  useEffect(() => {
    // Check if already installed
    if (window.matchMedia("(display-mode: standalone)").matches) {
      setIsInstalled(true);
      return;
    }

    const handler = (e) => {
      e.preventDefault();
      setDeferredPrompt(e);
      setShowPrompt(true);
    };

    window.addEventListener("beforeinstallprompt", handler);
    window.addEventListener("appinstalled", () => {
      setIsInstalled(true);
      setShowPrompt(false);
    });

    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  const handleInstall = async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === "accepted") {
      setShowPrompt(false);
    }
    setDeferredPrompt(null);
  };

  const handleDismiss = () => setShowPrompt(false);

  if (isInstalled || !showPrompt) return null;

  return (
    <div data-testid="pwa-install-banner" style={{
      position: "fixed", bottom: "70px", left: "50%", transform: "translateX(-50%)",
      zIndex: 10000, background: "linear-gradient(135deg, #1a2332 0%, #0f1923 100%)",
      border: "1px solid rgba(212,175,55,0.3)", borderRadius: "12px",
      padding: "12px 16px", display: "flex", alignItems: "center", gap: "12px",
      boxShadow: "0 8px 32px rgba(0,0,0,0.4)", maxWidth: "90vw", width: "360px",
    }}>
      <img src="/icon-192x192.png" alt="Predictor" style={{ width: "40px", height: "40px", borderRadius: "8px" }} />
      <div style={{ flex: 1 }}>
        <div style={{ color: "#fff", fontSize: "0.85rem", fontWeight: 600 }}>Instalar Predictor</div>
        <div style={{ color: "#aaa", fontSize: "0.7rem" }}>Accede rapido desde tu celular</div>
      </div>
      <button data-testid="pwa-install-btn" onClick={handleInstall} style={{
        background: "linear-gradient(135deg, #d4af37, #c49b2f)", color: "#000",
        border: "none", borderRadius: "8px", padding: "8px 14px",
        fontSize: "0.75rem", fontWeight: 700, cursor: "pointer",
      }}>INSTALAR</button>
      <button onClick={handleDismiss} style={{
        background: "none", border: "none", color: "#666",
        fontSize: "1.1rem", cursor: "pointer", padding: "0 4px",
      }}>&times;</button>
    </div>
  );
}
