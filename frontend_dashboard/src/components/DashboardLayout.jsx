import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import axios from 'axios';
import ConfigPanel from './ConfigPanel';
import '../Dashboard.css';

const DashboardLayout = ({ children }) => {
  const location = useLocation();
  const [panelConfigAbierto, setPanelConfigAbierto] = useState(false);
  const [ticketsPendientes, setTicketsPendientes] = useState(0);

  const cargarCampana = async () => {
    try {
      const response = await axios.get("http://localhost:8000/api/v1/admin/sesiones/pendientes");
      setTicketsPendientes(response.data.length);
    } catch (error) {
      console.error("Fallo al cargar notificaciones:", error);
    }
  };

  useEffect(() => {
    cargarCampana();
    const intervalo = setInterval(cargarCampana, 10000); // Actualiza la campana
    return () => clearInterval(intervalo);
  }, []);

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
        <div className="navbar-user" style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <span>Asesor: <strong>Soporte Académico</strong></span>
          
          {/* CAMPANA MONOCROMÁTICA */}
          <div className="notification-bell-container" title="Tickets Pendientes">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="#555">
              <path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.89 2 2 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"/>
            </svg>
            {ticketsPendientes > 0 && (
              <span className="notification-badge">{ticketsPendientes}</span>
            )}
          </div>

          {/* ENGRANE MONOCROMÁTICO */}
          <button 
            onClick={() => setPanelConfigAbierto(true)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex' }}
            title="Abrir Configuración Global"
          >
            <svg viewBox="0 0 24 24" width="22" height="22" fill="#555">
              <path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.06-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.56-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.73 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.04.3-.06.62-.06.94s.02.64.06.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .43-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.49-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/>
            </svg>
          </button>
        </div>
      </header>

      <ConfigPanel 
        isOpen={panelConfigAbierto} 
        onClose={() => setPanelConfigAbierto(false)} 
      />

      {children}
    </div>
  );
};

export default DashboardLayout;