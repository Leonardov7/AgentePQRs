import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import ConfigPanel from './ConfigPanel'; // <-- Importamos el Panel
import '../Dashboard.css';

const DashboardLayout = ({ children }) => {
  const location = useLocation();
  const [panelConfigAbierto, setPanelConfigAbierto] = useState(false); // Estado del drawer

  return (
    <div className="dashboard-root">
      <header className="top-navbar">
        <div className="navbar-brand">
          <span>🎓 Universidad de Cundinamarca | Consola PQR</span>
        </div>
        <ul className="navbar-menu">
          <li>
            <Link to="/admin/bandeja" className={location.pathname === '/admin/bandeja' ? 'active' : ''}>
              Centro de Atención
            </Link>
          </li>
          <li>
            <Link to="/admin/historial" className={location.pathname === '/admin/historial' ? 'active' : ''}>
              Auditoría
            </Link>
          </li>  
          
          <li>
            <Link to="/admin/estadisticas" className={location.pathname === '/admin/estadisticas' ? 'active' : ''}>
              Estadísticas
            </Link>
          </li>
          <li>
            <Link to="/admin/conocimiento" className={location.pathname === '/admin/conocimiento' ? 'active' : ''}>
              Gestión de Conocimiento
            </Link>
          </li>
        </ul>
        <div className="navbar-user" style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <span>Asesor: <strong>Soporte Académico</strong></span>
          
          {/* BOTÓN ESTÁTICO DEL ENGRANE PARA ABRIR EL PANEL */}
          <button 
            onClick={() => setPanelConfigAbierto(true)}
            style={{ 
              background: 'none', border: 'none', fontSize: '1.2rem', 
              cursor: 'pointer', padding: 0 
            }}
            title="Abrir Configuración Global"
          >
            ⚙️
          </button>
        </div>
      </header>

      {/* RENDERIZADO DEL COMPONENTE GLOBAL DE CONFIGURACIÓN */}
      <ConfigPanel 
        isOpen={panelConfigAbierto} 
        onClose={() => setPanelConfigAbierto(false)} 
      />

      {/* Contenido principal de la página actual */}
      {children}
    </div>
  );
};

export default DashboardLayout;