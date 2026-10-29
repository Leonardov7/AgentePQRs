import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';

const AdminConocimiento = () => {
  const [urlObjetivo, setUrlObjetivo] = useState('https://www.ucundinamarca.edu.co/');
  const [limitePaginas, setLimitePaginas] = useState(15);
  const [estadoTrabajo, setEstadoTrabajo] = useState('inactivo'); 
  const [jobId, setJobId] = useState(null);
  const [logs, setLogs] = useState([]);
  const [progresoPaginas, setProgresoPaginas] = useState(0);
  const [archivoDescarga, setArchivoDescarga] = useState(null);

  const consolaRef = useRef(null);

  useEffect(() => {
    if (consolaRef.current) {
      consolaRef.current.scrollTop = consolaRef.current.scrollHeight;
    }
  }, [logs]);

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
          if (datos.archivo_generado) {
            agregarLog(`[ARCHIVO] Base de conocimiento guardada en el servidor.`);
            const nombreArchivo = datos.archivo_generado.split('\\').pop().split('/').pop();
            setArchivoDescarga(nombreArchivo);
          }
        } else if (datos.estado_trabajo === 'failed' || datos.estado_trabajo === 'error') {
          setEstadoTrabajo('error');
          agregarLog(`[ERROR] El proceso de extracción falló en Firecrawl: ${datos.mensaje}`);
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

  const iniciarScraping = async (e) => {
    e.preventDefault();
    setEstadoTrabajo('procesando');
    setJobId(null);
    setLogs([]);
    setProgresoPaginas(0);
    setArchivoDescarga(null);
    
    agregarLog(`[SISTEMA] Iniciando secuencia de extracción para ${urlObjetivo}`);

    try {
      const respuesta = await fetch('http://localhost:8000/api/v1/admin/conocimiento/iniciar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url_objetivo: urlObjetivo,
          limite_paginas: parseInt(limitePaginas, 10)
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

  return (
    <div style={{ padding: '2rem', maxWidth: '900px', margin: '0 auto', fontFamily: 'sans-serif' }}>
      <header style={{ borderBottom: '2px solid #eee', marginBottom: '2rem', paddingBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ color: '#2c3e50', margin: 0 }}>Gestión de Conocimiento Institucional</h1>
          <p style={{ color: '#7f8c8d', marginTop: '0.5rem' }}>
            Módulo de extracción asíncrona mediante Firecrawl para la actualización del motor RAG.
          </p>
        </div>
        <Link to="/" style={{ textDecoration: 'none', backgroundColor: '#ecf0f1', color: '#2c3e50', padding: '0.5rem 1rem', borderRadius: '4px', fontWeight: 'bold' }}>
          Volver al Chat
        </Link>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '2rem' }}>
        
        {/* Panel de Configuración */}
        <div style={{ background: '#f8f9fa', padding: '1.5rem', borderRadius: '8px', border: '1px solid #dee2e6' }}>
          <h2 style={{ fontSize: '1.2rem', marginTop: 0, color: '#343a40' }}>Parámetros de Extracción</h2>
          <form onSubmit={iniciarScraping}>
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold', fontSize: '0.9rem' }}>URL Raíz</label>
              <input
                type="url"
                value={urlObjetivo}
                onChange={(e) => setUrlObjetivo(e.target.value)}
                required
                disabled={estadoTrabajo === 'procesando'}
                style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #ccc', boxSizing: 'border-box' }}
              />
            </div>

            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold', fontSize: '0.9rem' }}>Límite de Páginas</label>
              <input
                type="number"
                min="1"
                max="500"
                value={limitePaginas}
                onChange={(e) => setLimitePaginas(e.target.value)}
                required
                disabled={estadoTrabajo === 'procesando'}
                style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #ccc', boxSizing: 'border-box' }}
              />
            </div>

            <button
              type="submit"
              disabled={estadoTrabajo === 'procesando'}
              style={{
                width: '100%',
                padding: '0.75rem',
                backgroundColor: estadoTrabajo === 'procesando' ? '#95a5a6' : '#2980b9',
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

          {/* Botón de Emergencia para Cancelar */}
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

          {/* Indicador de Estado Visual */}
          <div style={{ marginTop: '2rem', padding: '1rem', background: '#fff', borderRadius: '4px', border: '1px solid #eee' }}>
            <h3 style={{ fontSize: '1rem', marginTop: 0, color: '#7f8c8d' }}>Estado del Sistema</h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginTop: '0.5rem' }}>
              <div style={{ 
                width: '15px', 
                height: '15px', 
                borderRadius: '50%', 
                backgroundColor: estadoTrabajo === 'procesando' ? '#f1c40f' : estadoTrabajo === 'completado' ? '#2ecc71' : estadoTrabajo === 'error' ? '#e74c3c' : estadoTrabajo === 'cancelado' ? '#e67e22' : '#bdc3c7'
              }}></div>
              <span style={{ fontWeight: 'bold', textTransform: 'uppercase', fontSize: '0.9rem' }}>
                {estadoTrabajo}
              </span>
            </div>
          </div>

          {/* Botón de Descarga */}
          {estadoTrabajo === 'completado' && archivoDescarga && (
            <div style={{ marginTop: '1.5rem' }}>
              <a 
                href={`http://localhost:8000/api/v1/admin/conocimiento/descargar/${archivoDescarga}`}
                download
                style={{
                  display: 'block',
                  textAlign: 'center',
                  width: '100%',
                  padding: '0.75rem',
                  backgroundColor: '#27ae60',
                  color: 'white',
                  textDecoration: 'none',
                  borderRadius: '4px',
                  fontWeight: 'bold',
                  boxSizing: 'border-box'
                }}
              >
                 Descargar Archivo (.md)
              </a>
            </div>
          )}
        </div>

        {/* Consola de Monitoreo */}
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <h2 style={{ fontSize: '1.2rem', marginTop: 0, color: '#343a40' }}>Terminal de Auditoría</h2>
          <div 
            ref={consolaRef}
            style={{ 
              flexGrow: 1, 
              backgroundColor: '#1e1e1e', 
              color: '#00ff00', 
              padding: '1rem', 
              borderRadius: '8px', 
              fontFamily: 'monospace', 
              fontSize: '0.85rem',
              overflowY: 'auto',
              minHeight: '400px',
              maxHeight: '500px',
              border: '1px solid #000'
            }}
          >
            {logs.length === 0 ? (
              <span style={{ color: '#888' }}>Esperando inicio de operación...</span>
            ) : (
              logs.map((log, index) => (
                <div key={index} style={{ marginBottom: '0.4rem', lineHeight: '1.4' }}>
                  {log}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminConocimiento;