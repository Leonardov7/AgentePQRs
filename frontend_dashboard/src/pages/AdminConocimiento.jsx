import React, { useState, useEffect, useRef, useCallback } from 'react';
import '../Dashboard.css';
import '../GestionConocimiento.css';
import PanelDocumentos from '../components/PanelDocumentos';

const API = 'http://localhost:8000/api/v1/admin/conocimiento';

// Estado de la actualización -> texto para el usuario y color del indicador
const ESTADOS = {
  inactivo:   { texto: 'En espera',   color: '#cbd5e1' },
  procesando: { texto: 'En curso',    color: '#f59e0b' },
  completado: { texto: 'Completada',  color: '#2e7d32' },
  error:      { texto: 'Con errores', color: '#ef4444' },
  cancelado:  { texto: 'Cancelada',   color: '#94a3b8' },
};

// Convierte una línea del registro "[fecha hora] [ETIQUETA] mensaje" en partes para mostrarla ordenada
const parsearLinea = (linea) => {
  const m = linea.match(/^\[\d{4}-\d{2}-\d{2} (\d{2}:\d{2}:\d{2})\]\s*(?:\[([^\]]+)\])?\s*(.*)$/);
  if (!m) return { hora: '', etiqueta: '', texto: linea, clase: '' };
  const etiqueta = m[2] || '';
  let clase = '';
  if (/ERROR|FALL/i.test(etiqueta) || /^(error|fallo)/i.test(m[3])) clase = 'error';
  else if (/[ÉE]XITO/i.test(etiqueta)) clase = 'exito';
  else if (/AVISO|PAUSA/i.test(etiqueta)) clase = 'aviso';
  return { hora: m[1], etiqueta, texto: m[3], clase };
};

const AdminConocimiento = () => {
  // ---------------- Actualización manual ----------------
  const [urlObjetivo, setUrlObjetivo] = useState('https://www.ucundinamarca.edu.co/');
  const [limitePaginas, setLimitePaginas] = useState(15);
  const [modoInfinito, setModoInfinito] = useState(false);
  const [estadoTrabajo, setEstadoTrabajo] = useState('inactivo');
  const [jobId, setJobId] = useState(null);

  // ---------------- Registro de actividad ----------------
  const [logs, setLogs] = useState([]);
  const consolaRef = useRef(null);

  // ---------------- Actualización programada ----------------
  const [cronFrecuencia, setCronFrecuencia] = useState('diario');
  const [cronHora, setCronHora] = useState('02:00');
  const [cronDia, setCronDia] = useState('mon');
  const [cronFechaInicio, setCronFechaInicio] = useState('');
  const [cronFechaFin, setCronFechaFin] = useState('');
  const [programacionActiva, setProgramacionActiva] = useState(null);

  // ---------------- Historial (ventana) ----------------
  const [modalAbierto, setModalAbierto] = useState(false);
  const [historialArchivos, setHistorialArchivos] = useState([]);
  const [cargandoHistorial, setCargandoHistorial] = useState(false);

  // ---------------- Avisos ----------------
  const [aviso, setAviso] = useState(null);   // { tipo: 'ok' | 'error', texto }
  const mostrarAviso = useCallback((tipo, texto) => setAviso({ tipo, texto }), []);
  useEffect(() => {
    if (!aviso) return undefined;
    const t = setTimeout(() => setAviso(null), 9000);
    return () => clearTimeout(t);
  }, [aviso]);

  // Desplazamiento automático del registro
  useEffect(() => {
    if (consolaRef.current) consolaRef.current.scrollTop = consolaRef.current.scrollHeight;
  }, [logs]);

  // ---------------- Carga de datos ----------------
  const cargarProgramacionActual = async () => {
    try {
      const res = await fetch(`${API}/programacion_actual`);
      const data = await res.json();
      setProgramacionActiva(data.programado ? data : null);
    } catch (error) {
      console.error('Error al cargar programación:', error);
    }
  };

  const cargarHistorialArchivos = async () => {
    setCargandoHistorial(true);
    try {
      const res = await fetch(`${API}/historial-archivos`);
      const data = await res.json();
      setHistorialArchivos(data.archivos || []);
    } catch (error) {
      console.error('Error cargando archivos físicos:', error);
    } finally {
      setCargandoHistorial(false);
    }
  };

  useEffect(() => {
    cargarProgramacionActual();
    cargarHistorialArchivos();
    const buscarLogs = async () => {
      try {
        const res = await fetch(`${API}/logs`);
        if (res.ok) setLogs((await res.json()).logs);
      } catch (error) { /* se ignora para no saturar la consola */ }
    };
    buscarLogs();
    const intervalo = setInterval(buscarLogs, 3000);
    return () => clearInterval(intervalo);
    
  }, []);

  // Seguimiento del trabajo manual
  useEffect(() => {
    let intervalo;
    const verificar = async () => {
      try {
        const res = await fetch(`${API}/estado/${jobId}`);
        if (!res.ok) return;
        const datos = await res.json();
        if (datos.estado_trabajo === 'completed') { setEstadoTrabajo('completado'); cargarHistorialArchivos(); }
        else if (datos.estado_trabajo === 'failed' || datos.estado_trabajo === 'error') setEstadoTrabajo('error');
        else if (datos.estado_trabajo === 'cancelled') setEstadoTrabajo('cancelado');
      } catch (error) {
        setEstadoTrabajo('error');
      }
    };
    if (jobId && estadoTrabajo === 'procesando') intervalo = setInterval(verificar, 5000);
    return () => clearInterval(intervalo);
  }, [jobId, estadoTrabajo]);

  // ---------------- Acciones ----------------
  const iniciarScraping = async (e) => {
    e.preventDefault();
    setEstadoTrabajo('procesando');
    setJobId(null);
    setLogs([]);                       // cada actualización empieza con el registro limpio
    try {
      const res = await fetch(`${API}/iniciar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url_objetivo: urlObjetivo,
          limite_paginas: modoInfinito ? 999999 : parseInt(limitePaginas, 10),
        }),
      });
      const datos = await res.json();
      if (res.ok) setJobId(datos.job_id);
      else { setEstadoTrabajo('error'); mostrarAviso('error', 'No se pudo iniciar la actualización.'); }
    } catch (error) {
      setEstadoTrabajo('error');
      mostrarAviso('error', 'No hay conexión con el servidor.');
    }
  };

  const abortarScraping = async () => {
    if (!jobId) return;
    try {
      await fetch(`${API}/cancelar/${jobId}`, { method: 'DELETE' });
      setEstadoTrabajo('cancelado');
    } catch (error) {
      console.error(error);
    }
  };

  const handleFechaInicioChange = (e) => {
    const val = e.target.value;
    setCronFechaInicio(val);
    if (val && cronFrecuencia === 'semanal') {
      const p = val.split('-');
      const d = new Date(p[0], p[1] - 1, p[2]);
      setCronDia(['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'][d.getDay()]);
    }
  };

  const guardarProgramacion = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API}/programar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url_objetivo: urlObjetivo,
          limite_paginas: modoInfinito ? 999999 : parseInt(limitePaginas, 10),
          frecuencia: cronFrecuencia,
          hora: cronHora,
          dia_semana: cronDia,
          fecha_inicio: cronFechaInicio || null,
          fecha_fin: cronFechaFin || null,
        }),
      });
      if (res.ok) { mostrarAviso('ok', 'La actualización programada quedó activada.'); cargarProgramacionActual(); }
      else mostrarAviso('error', 'No se pudo guardar la programación.');
    } catch (error) {
      mostrarAviso('error', 'No hay conexión con el servidor.');
    }
  };

  const cancelarProgramacion = async () => {
    try {
      const res = await fetch(`${API}/programar`, { method: 'DELETE' });
      if (res.ok) { setProgramacionActiva(null); mostrarAviso('ok', 'La actualización programada se desactivó.'); }
    } catch (error) {
      mostrarAviso('error', 'No hay conexión con el servidor.');
    }
  };

  const abrirModalHistorial = () => { setModalAbierto(true); cargarHistorialArchivos(); };

  // ---------------- Datos para el resumen ----------------
  const enCurso = estadoTrabajo === 'procesando';
  const estadoVisible = ESTADOS[estadoTrabajo] || ESTADOS.inactivo;
  const ultima = historialArchivos.find((a) => (a.tipo || '').includes('Optimizado'));

  return (
    <div className="dashboard-root">
      <div className="estadisticas-container" style={{ padding: 0 }}>
        <div className="gc-page">

          {/* ================= ENCABEZADO ================= */}
          <div className="gc-header">
            <div>
              <h2>Gestión de Conocimiento</h2>
              <p>Mantén al día la información con la que el asistente responde a los usuarios: actualiza el contenido del sitio web y agrega tus propios documentos.</p>
            </div>
            <button className="gc-btn gc-btn--secundario" onClick={abrirModalHistorial}>Historial de bases</button>
          </div>

          {aviso && (
            <div className={`gc-aviso ${aviso.tipo === 'ok' ? 'gc-aviso--ok' : 'gc-aviso--error'}`}>
              <span>{aviso.texto}</span>
              <button onClick={() => setAviso(null)} aria-label="Cerrar">✕</button>
            </div>
          )}

          {/* ================= RESUMEN ================= */}
          <div className="gc-resumen">
            <div className="gc-resumen-item">
              <small>Estado de la actualización</small>
              <strong><span className="gc-punto" style={{ background: estadoVisible.color }} />{estadoVisible.texto}</strong>
            </div>
            <div className="gc-resumen-item">
              <small>Última actualización del sitio</small>
              <strong>{ultima ? ultima.fecha : 'Aún no se ha realizado'}</strong>
            </div>
            <div className="gc-resumen-item">
              <small>Próxima actualización automática</small>
              <strong>{programacionActiva ? programacionActiva.siguiente_ejecucion : 'Sin programar'}</strong>
            </div>
          </div>

          {/* ================= CUERPO ================= */}
          <div className="gc-grid">
            <div className="gc-col">

              {/* ---------- Actualización manual ---------- */}
              <div className="gc-card">
                <div className="gc-card-head">
                  <h3>Actualizar ahora</h3>
                  <p>Lee el sitio web y renueva la información del asistente.</p>
                </div>
                <form onSubmit={iniciarScraping}>
                  <div className="gc-campo">
                    <label htmlFor="gc-url">Dirección del sitio web</label>
                    <input id="gc-url" type="url" value={urlObjetivo} onChange={(e) => setUrlObjetivo(e.target.value)} required disabled={enCurso} />
                  </div>
                  <div className="gc-campo">
                    <label>Alcance</label>
                    <div className="gc-segmentos">
                      <button type="button" className={modoInfinito ? 'activo' : ''} onClick={() => setModoInfinito(true)} disabled={enCurso}>Todo el sitio</button>
                      <button type="button" className={!modoInfinito ? 'activo' : ''} onClick={() => setModoInfinito(false)} disabled={enCurso}>Limitar páginas</button>
                    </div>
                  </div>
                  {!modoInfinito && (
                    <div className="gc-campo">
                      <label htmlFor="gc-limite">Cantidad máxima de páginas</label>
                      <input id="gc-limite" type="number" min="1" max="5000" value={limitePaginas} onChange={(e) => setLimitePaginas(e.target.value)} required disabled={enCurso} />
                    </div>
                  )}
                  <button type="submit" className="gc-btn gc-btn--block" disabled={enCurso}>
                    {enCurso ? 'Actualizando…' : 'Iniciar actualización'}
                  </button>
                  {enCurso && (
                    <button type="button" className="gc-btn gc-btn--peligro gc-btn--block" style={{ marginTop: '0.6rem' }} onClick={abortarScraping}>
                      Detener actualización
                    </button>
                  )}
                </form>
                <p className="gc-nota">Los documentos adicionales no se modifican durante la actualización.</p>
              </div>

              {/* ---------- Actualización programada ---------- */}
              <div className="gc-card">
                <div className="gc-card-head">
                  <h3>Actualización programada</h3>
                  <p>Renueva la información automáticamente, sin intervención.</p>
                </div>
                {programacionActiva ? (
                  <div className="gc-programacion">
                    <strong>Programación activa</strong>
                    <p>{programacionActiva.detalles}</p>
                    <p>Próxima ejecución: {programacionActiva.siguiente_ejecucion}</p>
                    <button className="gc-btn gc-btn--peligro gc-btn--block" onClick={cancelarProgramacion}>Desactivar programación</button>
                  </div>
                ) : (
                  <form onSubmit={guardarProgramacion}>
                    <div className="gc-fila">
                      <div className="gc-campo">
                        <label htmlFor="gc-frec">Frecuencia</label>
                        <select id="gc-frec" value={cronFrecuencia} onChange={(e) => setCronFrecuencia(e.target.value)}>
                          <option value="diario">Diaria</option>
                          <option value="semanal">Semanal</option>
                        </select>
                      </div>
                      <div className="gc-campo">
                        <label htmlFor="gc-hora">Hora</label>
                        <input id="gc-hora" type="time" value={cronHora} onChange={(e) => setCronHora(e.target.value)} required />
                      </div>
                    </div>
                    {cronFrecuencia === 'semanal' && (
                      <div className="gc-campo">
                        <label htmlFor="gc-dia">Día de la semana (según la fecha de inicio)</label>
                        <select id="gc-dia" value={cronDia} onChange={(e) => setCronDia(e.target.value)} disabled>
                          <option value="mon">Lunes</option><option value="tue">Martes</option><option value="wed">Miércoles</option>
                          <option value="thu">Jueves</option><option value="fri">Viernes</option><option value="sat">Sábado</option>
                          <option value="sun">Domingo</option>
                        </select>
                      </div>
                    )}
                    <div className="gc-fila">
                      <div className="gc-campo">
                        <label htmlFor="gc-ini">Desde (opcional)</label>
                        <input id="gc-ini" type="date" value={cronFechaInicio} onChange={handleFechaInicioChange} />
                      </div>
                      <div className="gc-campo">
                        <label htmlFor="gc-fin">Hasta (opcional)</label>
                        <input id="gc-fin" type="date" value={cronFechaFin} onChange={(e) => setCronFechaFin(e.target.value)} />
                      </div>
                    </div>
                    <button type="submit" className="gc-btn gc-btn--block">Activar programación</button>
                    <p className="gc-nota">Usa la dirección y el alcance definidos en «Actualizar ahora».</p>
                  </form>
                )}
              </div>
            </div>

            {/* ---------- Registro de actividad ---------- */}
            <div className="gc-registro">
              <div className="gc-registro-head">
                <h3>Registro de actividad</h3>
                <p>Seguimiento en tiempo real de lo que hace el sistema durante la actualización.</p>
              </div>
              <div className="gc-registro-cuerpo" ref={consolaRef}>
                {logs.length === 0 ? (
                  <span className="gc-registro-vacio">Sin actividad por ahora. Cuando inicies una actualización verás aquí su avance.</span>
                ) : (
                  logs.map((linea, i) => {
                    const p = parsearLinea(linea);
                    return (
                      <div key={i} className={`gc-linea ${p.clase}`}>
                        {p.hora && <span className="gc-hora">{p.hora}</span>}
                        {p.etiqueta && <span className="gc-tag">{p.etiqueta}</span>}
                        <span className="gc-texto">{p.texto}</span>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>

          {/* ================= DOCUMENTOS ADICIONALES ================= */}
          <PanelDocumentos onAviso={mostrarAviso} />
        </div>

        {/* ================= HISTORIAL DE BASES (ventana) ================= */}
        {modalAbierto && (
          <div className="modal-overlay">
            <div className="modal-content">
              <div className="modal-header">
                <h3>Historial de Bases de Conocimiento</h3>
                <button className="modal-close-btn" onClick={() => setModalAbierto(false)}>✕</button>
              </div>
              <div className="modal-body">
                {cargandoHistorial ? (
                  <p style={{ textAlign: 'center', color: '#777', padding: '2rem' }}>Consultando almacenamiento del servidor...</p>
                ) : historialArchivos.length === 0 ? (
                  <p style={{ textAlign: 'center', color: '#777', padding: '2rem' }}>Aún no se han generado archivos de conocimiento.</p>
                ) : (
                  <table className="tabla-historial-archivos">
                    <thead>
                      <tr>
                        <th>Fecha de Generación</th>
                        <th>Nombre del Archivo</th>
                        <th>Clasificación</th>
                        <th>Tamaño</th>
                        <th style={{ textAlign: 'center' }}>Acción</th>
                      </tr>
                    </thead>
                    <tbody>
                      {historialArchivos.map((arch, index) => (
                        <tr key={index}>
                          <td>{arch.fecha}</td>
                          <td style={{ fontFamily: 'monospace', fontSize: '0.8rem', color: '#1b4d3e' }}>{arch.nombre}</td>
                          <td>
                            <span className={`etiqueta-tipo-archivo ${arch.tipo.includes('Optimizado') ? 'tipo-optimizado' : 'tipo-crudo'}`}>
                              {arch.tipo}
                            </span>
                          </td>
                          <td>{arch.peso_kb} KB</td>
                          <td style={{ textAlign: 'center' }}>
                            <a href={`${API}/descargar/${arch.nombre}`} download className="btn-descarga-mini">Descargar</a>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AdminConocimiento;