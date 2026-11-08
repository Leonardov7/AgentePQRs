import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import '../Dashboard.css';

const AdminConocimiento = () => {
  // Estados originales
  const [urlObjetivo, setUrlObjetivo] = useState('https://www.ucundinamarca.edu.co/');
  const [limitePaginas, setLimitePaginas] = useState(15);
  const [modoInfinito, setModoInfinito] = useState(false);
  const [estadoTrabajo, setEstadoTrabajo] = useState('inactivo'); 
  const [jobId, setJobId] = useState(null);
  const [logs, setLogs] = useState([]);
  const [progresoPaginas, setProgresoPaginas] = useState(0);
  
  const [archivoCrudo, setArchivoCrudo] = useState(null);
  const [archivoOptimizado, setArchivoOptimizado] = useState(null);

  // NUEVOS Estados para Programación CRON
  const [cronFrecuencia, setCronFrecuencia] = useState('diario');
  const [cronHora, setCronHora] = useState('02:00');
  const [cronDia, setCronDia] = useState('mon');
  const [programacionActiva, setProgramacionActiva] = useState(null);

  const consolaRef = useRef(null);

  // Efecto original para autoscroll
  useEffect(() => {
    if (consolaRef.current) {
      consolaRef.current.scrollTop = consolaRef.current.scrollHeight;
    }
  }, [logs]);

  // NUEVO Efecto para cargar estado de programación al iniciar
  useEffect(() => {
    cargarProgramacionActual();
  }, []);

  const cargarProgramacionActual = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/v1/admin/conocimiento/programacion_actual');
      const data = await res.json();
      if (data.programado) {
        setProgramacionActiva(data);
      } else {
        setProgramacionActiva(null);
      }
    } catch (error) {
      console.error("Error al cargar programación:", error);
    }
  };

  // Efecto original para consultar estado del trabajo manual
  useEffect(() => {
    let intervaloConsulta;

    const verificarEstado = async () => {
      try {
        const respuesta = await fetch(`http://localhost:8000/api/v1/admin/conocimiento/estado/${jobId}`);
        
        if (!respuesta.ok) {
          throw new Error('Fallo en la comunicación con el servidor al verificar estado.');
        }

        const datos = await respuesta.json();
        
        setProgresoPaginas(datos.total_paginas);
        agregarLog(`[INFO] Estado actual: ${datos.estado_trabajo} | Páginas procesadas: ${datos.total_paginas}`);

        if (datos.estado_trabajo === 'completed') {
          setEstadoTrabajo('completado');
          agregarLog(`[ÉXITO] ${datos.mensaje}`);
          
          if (datos.archivo_crudo) {
            agregarLog(`[ARCHIVO] Base de conocimiento original (cruda) guardada.`);
            const nombreCrudo = datos.archivo_crudo.split('\\').pop().split('/').pop();
            setArchivoCrudo(nombreCrudo);
          }
          
          if (datos.archivo_optimizado) {
            agregarLog(`[ARCHIVO] Base de conocimiento optimizada por ML guardada.`);
            const nombreOptimizado = datos.archivo_optimizado.split('\\').pop().split('/').pop();
            setArchivoOptimizado(nombreOptimizado);
          }
        } else if (datos.estado_trabajo === 'failed' || datos.estado_trabajo === 'error') {
          setEstadoTrabajo('error');
          agregarLog(`[ERROR] El proceso de extracción falló: ${datos.mensaje}`);
        } else if (datos.estado_trabajo === 'cancelled') {
          setEstadoTrabajo('cancelado');
          agregarLog(`[CANCELADO] El proceso fue detenido por el administrador.`);
        }

      } catch (error) {
        setEstadoTrabajo('error');
        agregarLog(`[ERROR SISTEMA] ${error.message}`);
      }
    };

    if (jobId && estadoTrabajo === 'procesando') {
      intervaloConsulta = setInterval(verificarEstado, 5000);
    }

    return () => clearInterval(intervaloConsulta);
  }, [jobId, estadoTrabajo]);

  const agregarLog = (mensaje) => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs((prevLogs) => [...prevLogs, `[${timestamp}] ${mensaje}`]);
  };

  // Función original de inicio manual
  const iniciarScraping = async (e) => {
    e.preventDefault();
    setEstadoTrabajo('procesando');
    setJobId(null);
    setLogs([]);
    setProgresoPaginas(0);
    setArchivoCrudo(null);
    setArchivoOptimizado(null);
    
    agregarLog(`[SISTEMA] Iniciando secuencia de extracción para ${urlObjetivo}`);

    try {
      const respuesta = await fetch('http://localhost:8000/api/v1/admin/conocimiento/iniciar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url_objetivo: urlObjetivo,
          limite_paginas: modoInfinito ? 999999 : parseInt(limitePaginas, 10)
        }),
      });

      const datos = await respuesta.json();

      if (!respuesta.ok) {
        throw new Error(datos.detail || 'Error al iniciar el proceso en el servidor.');
      }

      setJobId(datos.job_id);
      agregarLog(`[CONEXIÓN] ${datos.mensaje}`);
      agregarLog(`[INFO] ID de Tarea Asignado: ${datos.job_id}`);
      
    } catch (error) {
      setEstadoTrabajo('error');
      agregarLog(`[ERROR CRÍTICO] ${error.message}`);
    }
  };

  // Función original de abortar
  const abortarScraping = async () => {
    if (!jobId) return;
    agregarLog(`[SISTEMA] Solicitando abortar la extracción en curso...`);
    try {
      const respuesta = await fetch(`http://localhost:8000/api/v1/admin/conocimiento/cancelar/${jobId}`, {
        method: 'DELETE'
      });
      const datos = await respuesta.json();
      if (!respuesta.ok) {
        throw new Error(datos.detail || 'Fallo al cancelar el trabajo.');
      }
      setEstadoTrabajo('cancelado');
      agregarLog(`[SISTEMA] ${datos.mensaje}`);
    } catch (error) {
      agregarLog(`[ERROR AL CANCELAR] ${error.message}`);
    }
  };

  // NUEVAS Funciones de Programación
  const guardarProgramacion = async (e) => {
    e.preventDefault();
    try {
      const respuesta = await fetch('http://localhost:8000/api/v1/admin/conocimiento/programar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url_objetivo: urlObjetivo,
          limite_paginas: modoInfinito ? 999999 : parseInt(limitePaginas, 10),
          frecuencia: cronFrecuencia,
          hora: cronHora,
          dia_semana: cronDia
        }),
      });
      if (respuesta.ok) {
        alert("Programación guardada exitosamente.");
        cargarProgramacionActual();
      } else {
        alert("Ocurrió un error al guardar la programación.");
      }
    } catch (error) {
      alert("Fallo de conexión al guardar la programación.");
    }
  };

  const cancelarProgramacion = async () => {
    try {
      const respuesta = await fetch('http://localhost:8000/api/v1/admin/conocimiento/programar', { 
        method: 'DELETE' 
      });
      if (respuesta.ok) {
        setProgramacionActiva(null);
        alert("Programación desactivada.");
      }
    } catch (error) {
      alert("Error de conexión al desactivar la programación.");
    }
  };

  return (
    <div className="dashboard-root">
      

      <div className="estadisticas-container" style={{ display: 'flex', justifyContent: 'center' }}>
        <div style={{ width: '100%', maxWidth: '1100px' }}>
          <div className="grafico-header" style={{ marginBottom: '2rem' }}>
            <h3>Gestión de Conocimiento Institucional</h3>
            <p style={{ color: '#666', fontSize: '0.9rem', marginTop: '0.5rem' }}>
              Módulo de extracción asíncrona local y optimización semántica RAG.
            </p>
          </div>

          {/* MANTENEMOS TU GRILLA ORIGINAL 1fr 2fr */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '2rem' }}>
            
            {/* Columna Izquierda (Paneles de Control) */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              
              {/* PANEL 1: Extracción Manual (TU CÓDIGO INTACTO) */}
              <div style={{ background: '#fff', padding: '1.5rem', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
                <h4 style={{ marginBottom: '1.5rem', color: '#1b4d3e', borderBottom: '1px solid #eee', paddingBottom: '0.5rem', fontSize: '1rem' }}>
                  Parámetros de Extracción
                </h4>
                <form onSubmit={iniciarScraping}>
                  <div style={{ marginBottom: '1rem' }}>
                    <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold', fontSize: '0.85rem', color: '#555' }}>URL Raíz</label>
                    <input
                      type="url"
                      value={urlObjetivo}
                      onChange={(e) => setUrlObjetivo(e.target.value)}
                      required
                      disabled={estadoTrabajo === 'procesando'}
                      style={{ width: '100%', padding: '0.65rem', borderRadius: '4px', border: '1px solid #ccc', boxSizing: 'border-box' }}
                    />
                  </div>

                  <div style={{ marginBottom: '1.5rem' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.85rem', color: '#555', marginBottom: '0.5rem' }}>
                      <input
                        type="checkbox"
                        checked={modoInfinito}
                        onChange={(e) => setModoInfinito(e.target.checked)}
                        disabled={estadoTrabajo === 'procesando'}
                      />
                      <strong>Extraer todo el sitio web (Hasta agotar enlaces)</strong>
                    </label>
                    
                    {!modoInfinito && (
                      <input
                        type="number"
                        min="1"
                        max="5000"
                        value={limitePaginas}
                        onChange={(e) => setLimitePaginas(e.target.value)}
                        required
                        disabled={estadoTrabajo === 'procesando'}
                        style={{ width: '100%', padding: '0.65rem', borderRadius: '4px', border: '1px solid #ccc', boxSizing: 'border-box' }}
                        placeholder="Límite de páginas"
                      />
                    )}
                  </div>

                  <button
                    type="submit"
                    disabled={estadoTrabajo === 'procesando'}
                    style={{
                      width: '100%',
                      padding: '0.75rem',
                      backgroundColor: estadoTrabajo === 'procesando' ? '#95a5a6' : '#1b4d3e',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      fontWeight: 'bold',
                      cursor: estadoTrabajo === 'procesando' ? 'not-allowed' : 'pointer'
                    }}
                  >
                    {estadoTrabajo === 'procesando' ? 'Procesando Extracción...' : 'Iniciar Extracción'}
                  </button>
                </form>

                {estadoTrabajo === 'procesando' && (
                  <button
                    onClick={abortarScraping}
                    style={{
                      width: '100%',
                      marginTop: '1rem',
                      padding: '0.75rem',
                      backgroundColor: '#e74c3c',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      fontWeight: 'bold',
                      cursor: 'pointer'
                    }}
                  >
                    Detener Emergencia
                  </button>
                )}

                <div style={{ marginTop: '2rem', padding: '1rem', background: '#f8f9fa', borderRadius: '4px', border: '1px solid #eee' }}>
                  <h3 style={{ fontSize: '0.85rem', margin: 0, color: '#7f8c8d' }}>Estado del Sistema</h3>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '0.75rem' }}>
                    <div style={{ 
                      width: '12px', 
                      height: '12px', 
                      borderRadius: '50%', 
                      backgroundColor: estadoTrabajo === 'procesando' ? '#f57c00' : estadoTrabajo === 'completado' ? '#2e7d32' : estadoTrabajo === 'error' ? '#c62828' : estadoTrabajo === 'cancelado' ? '#ed6c02' : '#bdc3c7'
                    }}></div>
                    <span style={{ fontWeight: 'bold', textTransform: 'uppercase', fontSize: '0.85rem', color: '#333' }}>
                      {estadoTrabajo}
                    </span>
                  </div>
                </div>

                {estadoTrabajo === 'completado' && (
                  <div style={{ marginTop: '1.5rem', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {archivoCrudo && (
                      <a 
                        href={`http://localhost:8000/api/v1/admin/conocimiento/descargar/${archivoCrudo}`}
                        download
                        style={{
                          display: 'block',
                          textAlign: 'center',
                          width: '100%',
                          padding: '0.75rem',
                          backgroundColor: '#6c757d',
                          color: 'white',
                          textDecoration: 'none',
                          borderRadius: '4px',
                          fontWeight: 'bold',
                          boxSizing: 'border-box',
                          fontSize: '0.85rem'
                        }}
                      >
                        ⬇ Descargar Base Original (.md)
                      </a>
                    )}
                    {archivoOptimizado && (
                      <a 
                        href={`http://localhost:8000/api/v1/admin/conocimiento/descargar/${archivoOptimizado}`}
                        download
                        style={{
                          display: 'block',
                          textAlign: 'center',
                          width: '100%',
                          padding: '0.75rem',
                          backgroundColor: '#2e7d32',
                          color: 'white',
                          textDecoration: 'none',
                          borderRadius: '4px',
                          fontWeight: 'bold',
                          boxSizing: 'border-box',
                          fontSize: '0.85rem'
                        }}
                      >
                        ⬇ Descargar Base Optimizada ML (.md)
                      </a>
                    )}
                  </div>
                )}
              </div>

              {/* NUEVO PANEL 2: Programación CRON (Añadido debajo del control manual) */}
              <div style={{ background: '#fff', padding: '1.5rem', borderRadius: '8px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
                <h4 style={{ marginBottom: '1.2rem', color: '#0984e3', borderBottom: '1px solid #eee', paddingBottom: '0.5rem', fontSize: '1rem' }}>
                  Automatización (CRON)
                </h4>
                
                {programacionActiva ? (
                  <div style={{ padding: '1rem', backgroundColor: '#e3f2fd', borderRadius: '6px', border: '1px solid #90caf9' }}>
                    <h5 style={{ margin: '0 0 0.5rem 0', color: '#1565c0', fontSize: '0.9rem' }}>⏱️ Rutina Activa</h5>
                    <p style={{ fontSize: '0.85rem', margin: '0 0 0.5rem 0' }}><strong>Próxima ejecución:</strong><br/>{programacionActiva.siguiente_ejecucion}</p>
                    <p style={{ fontSize: '0.85rem', margin: '0 0 1rem 0' }}><strong>Regla:</strong> {programacionActiva.detalles}</p>
                    <button 
                      onClick={cancelarProgramacion} 
                      style={{ width: '100%', padding: '0.6rem', backgroundColor: '#d32f2f', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.85rem', fontWeight: 'bold' }}
                    >
                      Desactivar Tarea
                    </button>
                  </div>
                ) : (
                  <form onSubmit={guardarProgramacion}>
                    <div style={{ marginBottom: '1rem' }}>
                      <label style={{ display: 'block', fontSize: '0.85rem', color: '#555', marginBottom: '0.3rem', fontWeight: 'bold' }}>Frecuencia</label>
                      <select value={cronFrecuencia} onChange={(e) => setCronFrecuencia(e.target.value)} style={{ width: '100%', padding: '0.65rem', borderRadius: '4px', border: '1px solid #ccc', boxSizing: 'border-box' }}>
                        <option value="diario">Diario</option>
                        <option value="semanal">Semanal</option>
                      </select>
                    </div>
                    {cronFrecuencia === 'semanal' && (
                      <div style={{ marginBottom: '1rem' }}>
                        <label style={{ display: 'block', fontSize: '0.85rem', color: '#555', marginBottom: '0.3rem', fontWeight: 'bold' }}>Día de la semana</label>
                        <select value={cronDia} onChange={(e) => setCronDia(e.target.value)} style={{ width: '100%', padding: '0.65rem', borderRadius: '4px', border: '1px solid #ccc', boxSizing: 'border-box' }}>
                          <option value="mon">Lunes</option>
                          <option value="tue">Martes</option>
                          <option value="wed">Miércoles</option>
                          <option value="thu">Jueves</option>
                          <option value="fri">Viernes</option>
                          <option value="sat">Sábado</option>
                          <option value="sun">Domingo</option>
                        </select>
                      </div>
                    )}
                    <div style={{ marginBottom: '1.5rem' }}>
                      <label style={{ display: 'block', fontSize: '0.85rem', color: '#555', marginBottom: '0.3rem', fontWeight: 'bold' }}>Hora de Ejecución</label>
                      <input type="time" value={cronHora} onChange={(e) => setCronHora(e.target.value)} required style={{ width: '100%', padding: '0.65rem', borderRadius: '4px', border: '1px solid #ccc', boxSizing: 'border-box' }} />
                    </div>
                    <button type="submit" style={{ width: '100%', padding: '0.75rem', backgroundColor: '#0984e3', color: 'white', border: 'none', borderRadius: '4px', fontWeight: 'bold', cursor: 'pointer' }}>
                      Guardar Programación
                    </button>
                  </form>
                )}
              </div>
            </div>

            {/* Columna Derecha (TU CONSOLA INTACTA) */}
            <div style={{ display: 'flex', flexDirection: 'column', background: '#1e1e1e', borderRadius: '8px', boxShadow: '0 4px 6px rgba(0,0,0,0.1)', overflow: 'hidden' }}>
              <div style={{ padding: '1rem 1.5rem', backgroundColor: '#2d2d2d', borderBottom: '1px solid #444' }}>
                <h4 style={{ margin: 0, color: '#fff', fontSize: '0.9rem', fontWeight: '500', letterSpacing: '0.5px' }}>Terminal de Auditoría Semántica</h4>
              </div>
              
              <div 
                ref={consolaRef}
                style={{ 
                  flexGrow: 1, 
                  color: '#4af626', 
                  padding: '1.5rem', 
                  fontFamily: '"Consolas", "Courier New", monospace', 
                  fontSize: '0.85rem',
                  overflowY: 'auto',
                  minHeight: '400px',
                  maxHeight: '750px' // Aumenté el max-height para que empate bien con la columna izquierda
                }}
              >
                {logs.length === 0 ? (
                  <span style={{ color: '#888' }}>Esperando inicio de operación...</span>
                ) : (
                  logs.map((log, index) => (
                    <div key={index} style={{ marginBottom: '0.5rem', lineHeight: '1.4' }}>
                      {log}
                    </div>
                  ))
                )}
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminConocimiento;