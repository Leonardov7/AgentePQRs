// ==============================================================================
// Dashboard Gerencial - Panel de Estadísticas y Métricas
// ==============================================================================
import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import '../Dashboard.css';

function AdminEstadisticas() {
  // Estados para simular los filtros
  const [fechaInicio, setFechaInicio] = useState("");
  const [fechaFin, setFechaFin] = useState("");

  return (
    <div className="dashboard-root">
      {/* Barra Superior Institucional */}
      <header className="top-navbar">
        <div className="navbar-brand">
          <span>🎓 Universidad de Cundinamarca | Consola PQR</span>
        </div>
        <ul className="navbar-menu">
          <li><Link to="/">Por Responder</Link></li>
          <li><Link to="/admin/estadisticas" className="active">Estadísticas</Link></li>
          <li><Link to="/admin/conocimiento">Gestión de Conocimiento</Link></li>
        </ul>
        <div className="navbar-user">
          Perfil: <strong>Superadministrador</strong>
        </div>
      </header>

      {/* Contenedor de Reportes */}
      <div className="estadisticas-container">
        {/* Barra de Filtros */}
        <div className="filtros-bar">
          <div className="filtro-grupo">
            <label>Rango de fechas:</label>
            <input type="date" value={fechaInicio} onChange={e => setFechaInicio(e.target.value)} />
            <span> a </span>
            <input type="date" value={fechaFin} onChange={e => setFechaFin(e.target.value)} />
            <button className="btn-filtrar">Filtrar</button>
          </div>
          <div className="filtro-grupo">
            <button className="btn-exportar">📊 Exportar Reporte PDF</button>
          </div>
        </div>

        {/* Tarjetas KPI (Basado en el diseño Dextra Reports) */}
        <div className="kpi-grid">
          <div className="kpi-card bg-azul">
            <div className="kpi-icono">👥</div>
            <div className="kpi-datos">
              <h4>SESIONES GLOBALES</h4>
              <h2>242</h2>
              <p>En lo que va del mes</p>
            </div>
          </div>
          
          <div className="kpi-card bg-verde">
            <div className="kpi-icono">❓</div>
            <div className="kpi-datos">
              <h4>TOTAL PREGUNTAS</h4>
              <h2>1,623</h2>
              <p>En lo que va del mes</p>
            </div>
          </div>

          <div className="kpi-card bg-naranja">
            <div className="kpi-icono">🤖</div>
            <div className="kpi-datos">
              <h4>RESUELTAS POR IA</h4>
              <h2>1,204</h2>
              <p>74.1% de contención</p>
            </div>
          </div>

          <div className="kpi-card bg-rojo">
            <div className="kpi-icono">⚠️</div>
            <div className="kpi-datos">
              <h4>ESCALADAS A HUMANO</h4>
              <h2>122</h2>
              <p>Requieren intervención</p>
            </div>
          </div>
        </div>

        {/* Área del Gráfico Principal */}
        <div className="grafico-panel">
          <div className="grafico-header">
            <h3>Volumen de PQRs por Tipología</h3>
          </div>
          <div className="grafico-placeholder">
            {/* Aquí integraremos Recharts o Chart.js más adelante */}
            <div className="barra-simulada" style={{ height: '80%' }}><span className="etiqueta">Peticiones</span></div>
            <div className="barra-simulada" style={{ height: '40%' }}><span className="etiqueta">Quejas</span></div>
            <div className="barra-simulada" style={{ height: '20%' }}><span className="etiqueta">Reclamos</span></div>
            <div className="barra-simulada" style={{ height: '60%' }}><span className="etiqueta">Sugerencias</span></div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AdminEstadisticas;