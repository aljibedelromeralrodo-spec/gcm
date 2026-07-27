import { useState } from "react";

export default function WelcomeTour({ onClose }) {
  const [tourStep, setTourStep] = useState(0);

  const nextTour = () => {
    if (tourStep < 4) setTourStep(tourStep + 1);
    else onClose();
  };

  const steps = [
    { icon: "fa-star", title: "Bienvenido a Central Mutuos", text: "Te mostrare las funciones principales del sistema en unos segundos." },
    { icon: "fa-th-large", title: "Dashboard", text: "Aqui ves tus metricas principales: simulaciones, clientes, estado del email y actividad reciente." },
    { icon: "fa-road", title: "Seguimiento", text: "Rastrea operaciones de credito automaticamente desde tus correos. Vista tabla o Kanban con linea de tiempo por cliente." },
    { icon: "fa-comment", title: "Central IA", text: "Tu asistente inteligente. Puede crear carpetas, buscar correos, enviar emails y calcular comisiones. Haz clic en el boton dorado abajo a la derecha." },
    { icon: "fa-search", title: "Busqueda Rapida", text: "Presiona Ctrl+K en cualquier momento para buscar clientes, simulaciones y correos al instante." },
  ];

  const step = steps[tourStep];

  return (
    <div className="tour-overlay">
      <div className="tour-modal" data-testid="tour-modal">
        <div className="tour-step">
          <div className="tour-icon"><i className={`fa ${step.icon}`}></i></div>
          <h3>{step.title}</h3>
          <p>{step.text}</p>
        </div>
        <div className="tour-actions">
          <button className="tour-skip" onClick={onClose}>Saltar</button>
          <div className="tour-dots">
            {[0,1,2,3,4].map(i => <span key={i} className={`tour-dot ${tourStep === i ? 'active' : ''}`}></span>)}
          </div>
          <button className="tour-next" onClick={nextTour} data-testid="tour-next">{tourStep === 4 ? "Comenzar" : "Siguiente"}</button>
        </div>
      </div>
    </div>
  );
}
