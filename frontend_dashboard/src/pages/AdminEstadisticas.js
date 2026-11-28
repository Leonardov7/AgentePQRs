// ==============================================================================
// Dashboard Gerencial - Plataforma de Business Intelligence PQR
// ==============================================================================
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line
} from 'recharts';
import '../Dashboard.css';

const API_BASE_URL = "http://localhost:8000/api/v1/admin";

export default function AdminEstadisticas() {
  const [fechaInicio, setFechaInicio] = useState("");
  const [fechaFin, setFechaFin] = useState("");
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);
  
  // Vistas del menú lateral de BI
  const [vistaActiva, setVistaActiva] = useState("resumen"); 
  
  // Filtros dinámicos en frontend
  const [filtroDemRol, setFiltroDemRol] = useState("Todos");
  const [filtroDemSede, setFiltroDemSede] = useState("Todos");
  const [filtroRendEstado, setFiltroRendEstado] = useState("Todos");

  const cargarEstadisticas = async () => {
    setCargando(true);
    try {
      let url = `${API_BASE_URL}/estadisticas`;
      if (fechaInicio && fechaFin) {
        url += `?fecha_inicio=${fechaInicio}&fecha_fin=${fechaFin}`;
      }
      const response = await axios.get(url);
      setDatos(response.data);
    } catch (error) {
      console.error("Error al cargar métricas:", error);
    } finally {
      setCargando(false);
    }
  };

  useEffect(() => {
    cargarEstadisticas();
  }, []);

  // Función núcleo para agrupar dinámicamente cualquier columna
  const getDistribucion = (datosArray, campo) => {
    if (!datosArray) return [];
    const conteo = {};
    datosArray.forEach(item => {
      const val = item[campo] || "Sin Definir";
      conteo[val] = (conteo[val] || 0) + 1;
    });
    return Object.keys(conteo).map(k => ({ name: k, value: conteo[k] })).sort((a,b) => b.value - a.value);
  };

  const calcularTiempoPromedioResolucion = (datosArray) => {
    if (!datosArray) return 0;
    let totalMinutos = 0;
    let validos = 0;
    datosArray.forEach(item => {
      if(item.Fecha_Ingreso && item.Fecha_Actualizacion && item.Estado_Final === "Cerrada") {
         const inicio = new Date(item.Fecha_Ingreso);
         const fin = new Date(item.Fecha_Actualizacion);
         totalMinutos += (fin - inicio) / 60000;
         validos++;
      }
    });
    return validos > 0 ? (totalMinutos / validos).toFixed(1) : 0;
  };

  const descargarCSV = () => {
    if (!datos || datos.datos_crudos.length === 0) return alert("No hay datos para exportar.");
    const headers = Object.keys(datos.datos_crudos[0]).join(",");
    const filas = datos.datos_crudos.map(obj => 
      Object.values(obj).map(val => `"${val || ''}"`).join(",")
    ).join("\n");

    const csvContent = "data:text/csv;charset=utf-8," + headers + "\n" + filas;
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `Reporte_Analitico_PQR_${new Date().toISOString().split('T')[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const generarInterpretacion = () => {
    if (!datos || datos.datos_crudos.length === 0) return "No hay datos suficientes para generar un análisis.";
    const distSedes = getDistribucion(datos.datos_crudos, "Sede");
    const distRoles = getDistribucion(datos.datos_crudos, "Perfil");
    const sedeMayor = distSedes[0];
    const rolMayor = distRoles[0];
    const tiempoProm = calcularTiempoPromedioResolucion(datos.datos_crudos);
    
    return `Análisis Automatizado: En el periodo actual se registraron ${datos.sesiones_globales} interacciones totales. El agente automático institucional logró contener y resolver el ${datos.tasa_contencion}% de las solicitudes de manera autónoma, reduciendo drásticamente la carga operativa. Geográficamente, la sede con mayor demanda fue ${sedeMayor?.name || 'N/A'} concentrando ${sedeMayor?.value || 0} casos. El perfil predominante corresponde a ${rolMayor?.name || 'N/A'}. Los casos resueltos por asesores humanos tomaron un promedio de ${tiempoProm} minutos. Requieren especial atención y seguimiento continuo los ${datos.escaladas_humano} casos que debieron ser escalados a talento humano por complejidad.`;
  };

  // Colores Corporativos Universales
  const COLORES_PIE = ['#1b4d3e', '#2980b9', '#e67e22', '#8e44ad', '#27ae60', '#c0392b', '#f39c12'];
  const COLORES_PQRSD = {
      "Peticion": "#2980b9",
      "Queja": "#e67e22",
      "Reclamo": "#c0392b",
      "Sugerencia": "#27ae60",
      "Felicitacion": "#8e44ad"
  };

  // Lógica de filtrado en cliente
  let datosDemograficosFiltrados = [];
  let distSedesFiltrada = [];
  let distRolesFiltrada = [];
  let datosComportamientoFiltrados = [];
  let distEstadosFiltrada = [];
  let distPqrsdGlobal = [];

  if (datos && datos.datos_crudos) {
    // Para Demografía
    datosDemograficosFiltrados = datos.datos_crudos.filter(d => 
      (filtroDemRol === "Todos" || d.Perfil === filtroDemRol) &&
      (filtroDemSede === "Todos" || d.Sede === filtroDemSede)
    );
    distSedesFiltrada = getDistribucion(datosDemograficosFiltrados, "Sede");
    distRolesFiltrada = getDistribucion(datosDemograficosFiltrados, "Perfil");

    // Para Rendimiento
    datosComportamientoFiltrados = datos.datos_crudos.filter(d => 
      (filtroRendEstado === "Todos" || d.Estado_Final === filtroRendEstado)
    );
    distEstadosFiltrada = getDistribucion(datosComportamientoFiltrados, "Estado_Final");

    // Para Tipología Global (Módulo PQRSD)
    const soloCerrados = datos.datos_crudos.filter(d => d.Estado_Final === "Cerrada" && d.Tipologia_PQRSD !== "No Clasificada");
    distPqrsdGlobal = getDistribucion(soloCerrados, "Tipologia_PQRSD");
  }

  return (
    <div className="dashboard-container bi-container">
      {/* BANNER IZQUIERDO DE NAVEGACIÓN BI */}
      <div className="bi-sidebar no-print">
        <div className="bi-sidebar-title">Módulos Analíticos</div>
        <ul className="bi-nav">
          <li className={vistaActiva === "resumen" ? "active" : ""} onClick={() => setVistaActiva("resumen")}>
            <span className="bi-icon">📊</span> Resumen Ejecutivo
          </li>
          <li className={vistaActiva === "demografia" ? "active" : ""} onClick={() => setVistaActiva("demografia")}>
            <span className="bi-icon">👥</span> Análisis Demográfico
          </li>
          {/* NUEVO MÓDULO PQRSD */}
          <li className={vistaActiva === "pqrsd" ? "active" : ""} onClick={() => setVistaActiva("pqrsd")}>
            <span className="bi-icon">📋</span> Naturaleza del Servicio (PQRSD)
          </li>
          <li className={vistaActiva === "rendimiento" ? "active" : ""} onClick={() => setVistaActiva("rendimiento")}>
            <span className="bi-icon">⏱️</span> Rendimiento y Tiempos
          </li>
        </ul>
        <div className="bi-sidebar-footer">
          <p>Exportación de Datos</p>
          <button className="bi-btn-csv" onClick={descargarCSV}>⬇ Descargar Base (CSV)</button>
          <button className="bi-btn-print" onClick={() => window.print()}>🖨 Imprimir Informe</button>
        </div>
      </div>

      {/* ÁREA PRINCIPAL DE RESULTADOS */}
      <div className="bi-main-content">
        
        {/* Filtros Globales de Fecha */}
        <div className="filtros-bar no-print">
          <div className="filtro-grupo">
            <label style={{ fontSize: '0.85rem', fontWeight: 'bold', color: '#555' }}>Filtro de Fecha:</label>
            <input type="date" value={fechaInicio} onChange={e => setFechaInicio(e.target.value)} />
            <span style={{ color: '#888' }}> a </span>
            <input type="date" value={fechaFin} onChange={e => setFechaFin(e.target.value)} />
            <button className="btn-filtrar" onClick={cargarEstadisticas}>Aplicar</button>
            <button className="btn-exportar" style={{marginLeft: '10px', backgroundColor: '#e0e0e0', color: '#333'}} onClick={() => {setFechaInicio(""); setFechaFin(""); setTimeout(cargarEstadisticas, 100);}}>Limpiar</button>
          </div>
        </div>

        {cargando || !datos ? (
          <div style={{ textAlign: 'center', padding: '4rem', color: '#777', fontSize: '1.2rem' }}>Generando reportes analíticos...</div>
        ) : (
          <div className="bi-report-area">
            
            {/* 1. VISTA: RESUMEN EJECUTIVO */}
            {vistaActiva === "resumen" && (
              <div className="fade-in">
                <h2 className="bi-section-title">Resumen Ejecutivo General</h2>
                
                <div className="kpi-grid">
                  <div className="kpi-card bg-azul"><div className="kpi-icono">🌐</div><div className="kpi-datos"><h4>CASOS GLOBALES</h4><h2>{datos.sesiones_globales}</h2><p>Tickets totales</p></div></div>
                  <div className="kpi-card bg-verde"><div className="kpi-icono">🤖</div><div className="kpi-datos"><h4>TASA DE RESOLUCIÓN</h4><h2>{datos.tasa_contencion}%</h2><p>Contenidos por IA</p></div></div>
                  <div className="kpi-card bg-rojo"><div className="kpi-icono">⚠️</div><div className="kpi-datos"><h4>ESCALADOS A ASESOR</h4><h2>{datos.escaladas_humano}</h2><p>Intervención manual</p></div></div>
                  <div className="kpi-card bg-naranja"><div className="kpi-icono">💬</div><div className="kpi-datos"><h4>INTERACCIONES</h4><h2>{datos.total_preguntas}</h2><p>Mensajes procesados</p></div></div>
                </div>

                <div className="grafico-panel" style={{ height: 'auto', marginTop: '1.5rem', backgroundColor: '#e8f5e9', border: '1px solid #c8e6c9' }}>
                  <h3 style={{ color: '#2e7d32', marginBottom: '10px', fontSize: '1rem', borderBottom: 'none' }}>Análisis General de la Operación</h3>
                  <p style={{ color: '#333', fontSize: '0.95rem', lineHeight: '1.6' }}>{generarInterpretacion()}</p>
                </div>
              </div>
            )}

            {/* 2. VISTA: DEMOGRAFÍA CON FILTROS CRUZADOS (Recharts Integrado) */}
            {vistaActiva === "demografia" && (
              <div className="fade-in">
                <h2 className="bi-section-title">Análisis Demográfico Detallado</h2>
                
                <div className="bi-filtros-internos no-print">
                  <label style={{display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.85rem', fontWeight: 'bold'}}>
                    Filtrar por Perfil de Usuario:
                    <select value={filtroDemRol} onChange={e => setFiltroDemRol(e.target.value)}>
                      <option value="Todos">Mostrar Todos</option>
                      <option value="Estudiante">Estudiante</option>
                      <option value="Docente">Docente</option>
                      <option value="Administrativo">Administrativo</option>
                      <option value="Graduado">Graduado</option>
                      <option value="Ciudadano">Ciudadano</option>
                    </select>
                  </label>
                  
                  <label style={{display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.85rem', fontWeight: 'bold'}}>
                    Filtrar por Sede Institucional:
                    <select value={filtroDemSede} onChange={e => setFiltroDemSede(e.target.value)}>
                      <option value="Todos">Mostrar Todas</option>
                      <option value="Fusagasugá">Fusagasugá</option>
                      <option value="Girardot">Girardot</option>
                      <option value="Ubaté">Ubaté</option>
                      <option value="Chía">Chía</option>
                      <option value="Facatativá">Facatativá</option>
                      <option value="Soacha">Soacha</option>
                      <option value="Zipaquirá">Zipaquirá</option>
                    </select>
                  </label>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '2rem' }}>
                  <div className="grafico-panel" style={{ height: '350px' }}>
                    <div className="grafico-header"><h3>Distribución por Sede</h3></div>
                    {distSedesFiltrada.length === 0 ? (<p style={{color: '#999', margin: 'auto'}}>Sin datos</p>) : (
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie data={distSedesFiltrada} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={60} outerRadius={80} label>
                            {distSedesFiltrada.map((entry, index) => ( <Cell key={`cell-${index}`} fill={COLORES_PIE[index % COLORES_PIE.length]} /> ))}
                          </Pie>
                          <RechartsTooltip />
                          <Legend />
                        </PieChart>
                      </ResponsiveContainer>
                    )}
                  </div>
                  
                  <div className="grafico-panel" style={{ height: '350px' }}>
                    <div className="grafico-header"><h3>Distribución por Perfil</h3></div>
                    {distRolesFiltrada.length === 0 ? (<p style={{color: '#999', margin: 'auto'}}>Sin datos</p>) : (
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie data={distRolesFiltrada} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={60} outerRadius={80} label>
                            {distRolesFiltrada.map((entry, index) => ( <Cell key={`cell-${index}`} fill={COLORES_PIE[index % COLORES_PIE.length]} /> ))}
                          </Pie>
                          <RechartsTooltip />
                          <Legend />
                        </PieChart>
                      </ResponsiveContainer>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* 3. NUEVA VISTA: NATURALEZA DEL SERVICIO PQRSD */}
            {vistaActiva === "pqrsd" && (
              <div className="fade-in">
                <h2 className="bi-section-title">Naturaleza del Servicio (PQRSD)</h2>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '2rem' }}>
                  
                  {/* Dona Global de PQRSD */}
                  <div className="grafico-panel" style={{ height: '400px' }}>
                    <div className="grafico-header"><h3>Volumen Global de Casos Resueltos</h3></div>
                    {distPqrsdGlobal.length === 0 ? (<p style={{color: '#999', margin: 'auto'}}>No hay casos cerrados clasificados.</p>) : (
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie data={distPqrsdGlobal} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={70} outerRadius={90}>
                            {distPqrsdGlobal.map((entry, index) => ( <Cell key={`cell-${index}`} fill={COLORES_PQRSD[entry.name] || '#95a5a6'} /> ))}
                          </Pie>
                          <RechartsTooltip />
                          <Legend />
                        </PieChart>
                      </ResponsiveContainer>
                    )}
                  </div>

                  {/* Cruce PQRSD por Sede (Barras Apiladas) */}
                  <div className="grafico-panel" style={{ height: '400px' }}>
                    <div className="grafico-header"><h3>Correlación Tipología vs. Sede Institucional</h3></div>
                    {datos.distribucion_tipologia_sede.length === 0 ? (<p style={{color: '#999', margin: 'auto'}}>No hay datos cruzados suficientes.</p>) : (
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={datos.distribucion_tipologia_sede} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e0e0e0" />
                          <XAxis dataKey="name" tick={{fontSize: 12}} />
                          <YAxis />
                          <RechartsTooltip cursor={{fill: '#f4f6f8'}} />
                          <Legend />
                          <Bar dataKey="Peticion" stackId="a" fill="#2980b9" />
                          <Bar dataKey="Queja" stackId="a" fill="#e67e22" />
                          <Bar dataKey="Reclamo" stackId="a" fill="#c0392b" />
                          <Bar dataKey="Sugerencia" stackId="a" fill="#27ae60" />
                          <Bar dataKey="Felicitacion" stackId="a" fill="#8e44ad" />
                        </BarChart>
                      </ResponsiveContainer>
                    )}
                  </div>

                </div>
              </div>
            )}

            {/* 4. VISTA: RENDIMIENTO Y TIEMPOS */}
            {vistaActiva === "rendimiento" && (
              <div className="fade-in">
                <h2 className="bi-section-title">Rendimiento Operativo y Tiempos de Respuesta</h2>
                
                <div className="bi-filtros-internos no-print">
                  <label style={{display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.85rem', fontWeight: 'bold'}}>
                    Filtrar por Estado de Caso:
                    <select value={filtroRendEstado} onChange={e => setFiltroRendEstado(e.target.value)}>
                      <option value="Todos">Mostrar Todos</option>
                      <option value="Cerrada">Casos Cerrados (Resueltos)</option>
                      <option value="En Cola">Casos en Espera (En Cola)</option>
                      <option value="Atencion Bot">Atendidos por IA</option>
                    </select>
                  </label>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: '2rem' }}>
                  <div className="grafico-panel" style={{ height: 'auto', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', backgroundColor: '#f4f6f8' }}>
                    <h3 style={{ fontSize: '1.2rem', color: '#555', marginBottom: '10px' }}>Tiempo Promedio de Resolución</h3>
                    <h1 style={{ fontSize: '4rem', color: '#e67e22', margin: 0 }}>{calcularTiempoPromedioResolucion(datosComportamientoFiltrados)}</h1>
                    <span style={{ fontSize: '1rem', color: '#777' }}>Minutos / Ticket Cerrado</span>
                  </div>

                  <div className="grafico-panel" style={{ height: 'auto' }}>
                    <div className="grafico-header"><h3>Desglose de Estados Actuales</h3></div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                      {distEstadosFiltrada.map((est, idx) => {
                        const maximo = Math.max(...distEstadosFiltrada.map(e => e.value));
                        const porcentaje = ((est.value / maximo) * 100).toFixed(0);
                        return (
                          <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
                            <span style={{ width: '130px', fontWeight: 'bold', color: '#444', textAlign: 'right', fontSize: '0.85rem' }}>{est.name}</span>
                            <div style={{ flex: 1, backgroundColor: '#f0f0f0', borderRadius: '10px', height: '20px', overflow: 'hidden' }}>
                              <div style={{ width: `${porcentaje}%`, backgroundColor: '#2980b9', height: '100%', transition: 'width 0.5s' }}></div>
                            </div>
                            <span style={{ width: '40px', color: '#333', fontWeight: 'bold' }}>{est.value}</span>
                          </div>
                        )
                      })}
                      {distEstadosFiltrada.length === 0 && <p style={{color: '#999'}}>No hay casos con el filtro seleccionado.</p>}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}