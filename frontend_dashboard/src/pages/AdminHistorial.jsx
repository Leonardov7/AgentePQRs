import React, { useState, useEffect } from 'react';
import axios from 'axios';
import '../Dashboard.css';

const API_BASE_URL = "http://localhost:8000/api/v1/admin";

const AdminHistorial = () => {
  const [sesiones, setSesiones] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [busqueda, setBusqueda] = useState("");
  const [filtroFecha, setFiltroFecha] = useState("");
  
  const [sesionActiva, setSesionActiva] = useState(null);
  const [transcripcion, setTranscripcion] = useState([]);

  useEffect(() => {
    cargarHistorial();
  }, []);

  const cargarHistorial = async () => {
    setCargando(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/historial-completo`);
      setSesiones(response.data);
    } catch (error) {
      console.error("Error al cargar historial general:", error);
    } finally {
      setCargando(false);
    }
  };

  const abrirConversacion = async (sesion) => {
    setSesionActiva(sesion);
    try {
      const res = await axios.get(`${API_BASE_URL}/sesiones/${sesion.id}/historial`);
      setTranscripcion(res.data);
    } catch (error) {
      console.error("No se pudo cargar la transcripción:", error);
      setTranscripcion([]);
    }
  };

  const calcularDuracion = (inicio, fin) => {
    const diff = (new Date(fin) - new Date(inicio)) / 60000; 
    return Math.max(diff, 1).toFixed(0); 
  };

  const sesionesFiltradas = sesiones.filter(s => {
    const cumpleBusqueda = s.nombre.toLowerCase().includes(busqueda.toLowerCase()) || 
                           s.documento.includes(busqueda) || 
                           s.correo.toLowerCase().includes(busqueda.toLowerCase());
    const cumpleFecha = filtroFecha ? s.creado.startsWith(filtroFecha) : true;
    return cumpleBusqueda && cumpleFecha;
  });

  return (
    <div className="estadisticas-container">
      <div style={{ backgroundColor: '#fff', borderRadius: '8px', padding: '1.5rem', boxShadow: '0 1px 3px rgba(0,0,0,0.05)', height: '100%', display: 'flex', flexDirection: 'column' }}>
        
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
          <h2 style={{ color: '#1b4d3e', margin: 0 }}>Historial de Conversaciones</h2>
          <div style={{ display: 'flex', gap: '10px' }}>
            <input 
              type="date" 
              value={filtroFecha}
              onChange={(e) => setFiltroFecha(e.target.value)}
              style={{ padding: '8px 12px', border: '1px solid #ccc', borderRadius: '4px' }}
            />
            <input 
              type="text" 
              placeholder="Buscar por cédula, nombre o correo..." 
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              style={{ padding: '8px 12px', border: '1px solid #ccc', borderRadius: '4px', width: '300px' }}
            />
            <button onClick={cargarHistorial} style={{ padding: '8px 12px', backgroundColor: '#e9ecef', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>🔄 Recargar</button>
          </div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto' }}>
          {cargando ? (
            <p style={{ textAlign: 'center', marginTop: '2rem', color: '#666' }}>Cargando base de datos...</p>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ backgroundColor: '#f8f9fa', borderBottom: '2px solid #dee2e6', textAlign: 'left' }}>
                  <th style={{ padding: '12px' }}>Registro</th>
                  <th style={{ padding: '12px' }}>Usuario</th>
                  <th style={{ padding: '12px' }}>Identificación</th>
                  <th style={{ padding: '12px' }}>Contacto</th>
                  <th style={{ padding: '12px' }}>Estado y Duración</th>
                  <th style={{ padding: '12px', textAlign: 'center' }}>Auditoría</th>
                </tr>
              </thead>
              <tbody>
                {sesionesFiltradas.map((s) => (
                  <tr key={s.id} style={{ borderBottom: '1px solid #eee' }}>
                    <td style={{ padding: '12px' }}>{s.creado}</td>
                    <td style={{ padding: '12px', fontWeight: '500' }}>{s.nombre}</td>
                    <td style={{ padding: '12px' }}>{s.documento}<br/><span style={{fontSize: '0.7rem', color: '#666'}}>{s.rol} - {s.sede}</span></td>
                    <td style={{ padding: '12px' }}>{s.correo}<br/>{s.celular}</td>
                    <td style={{ padding: '12px' }}>
                      <span style={{ 
                        padding: '4px 8px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 'bold', display: 'inline-block', marginBottom: '4px',
                        backgroundColor: s.estado === 'cerrada' ? '#e8f5e9' : (s.estado === 'en_cola' ? '#fff3cd' : '#e3f2fd'),
                        color: s.estado === 'cerrada' ? '#2e7d32' : (s.estado === 'en_cola' ? '#856404' : '#1976d2')
                      }}>
                        {s.estado.toUpperCase().replace('_', ' ')}
                      </span>
                      <br/>
                      <span style={{fontSize: '0.75rem', color: '#555', fontWeight: 'bold'}}>
                        Total: {calcularDuracion(s.creado, s.actualizado)} min.
                      </span>
                    </td>
                    <td style={{ padding: '12px', textAlign: 'center' }}>
                      <button 
                        onClick={() => abrirConversacion(s)}
                        style={{ backgroundColor: '#1b4d3e', color: 'white', border: 'none', padding: '6px 12px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.75rem' }}
                      >
                        Leer Chat
                      </button>
                    </td>
                  </tr>
                ))}
                {sesionesFiltradas.length === 0 && (
                  <tr>
                    <td colSpan="6" style={{ padding: '20px', textAlign: 'center', color: '#888' }}>No se encontraron registros.</td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {sesionActiva && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000 }}>
          <div style={{ backgroundColor: 'white', width: '600px', height: '80vh', borderRadius: '8px', display: 'flex', flexDirection: 'column', boxShadow: '0 10px 30px rgba(0,0,0,0.3)' }}>
            <div style={{ padding: '1rem 1.5rem', backgroundColor: '#1b4d3e', color: 'white', borderTopLeftRadius: '8px', borderTopRightRadius: '8px', display: 'flex', justifyContent: 'space-between' }}>
              <h3 style={{ margin: 0, fontSize: '1rem' }}>Transcripción: {sesionActiva.nombre}</h3>
              <button onClick={() => setSesionActiva(null)} style={{ background: 'none', border: 'none', color: 'white', fontSize: '1.2rem', cursor: 'pointer' }}>✕</button>
            </div>
            
            <div style={{ padding: '1rem 1.5rem', backgroundColor: '#f8f9fa', borderBottom: '1px solid #eee', fontSize: '0.8rem', color: '#555', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div><strong>Documento:</strong> {sesionActiva.documento} | <strong>Correo:</strong> {sesionActiva.correo} | <strong>Celular:</strong> {sesionActiva.celular}</div>
              <div><strong>Sede/Rol:</strong> {sesionActiva.sede} ({sesionActiva.rol})</div>
              <div><strong>Duración Total de la Sesión:</strong> {calcularDuracion(sesionActiva.creado, sesionActiva.actualizado)} minutos</div>
            </div>

            <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {transcripcion.map((msg, i) => (
                <div key={i} style={{ 
                  alignSelf: msg.emisor === 'usuario' ? 'flex-end' : 'flex-start',
                  backgroundColor: msg.emisor === 'usuario' ? '#e9ecef' : (msg.emisor === 'bot' ? '#2980b9' : (msg.emisor === 'asesor' ? '#1b4d3e' : '#fff3cd')),
                  color: msg.emisor === 'usuario' ? '#333' : (msg.emisor === 'sistema' ? '#856404' : 'white'),
                  border: msg.emisor === 'sistema' ? '1px solid #ffeeba' : 'none',
                  padding: '10px 14px', borderRadius: '8px', maxWidth: '80%', fontSize: '0.85rem'
                }}>
                  <div style={{ fontSize: '0.65rem', opacity: 0.8, marginBottom: '4px', textTransform: 'uppercase' }}>
                    {msg.emisor === 'bot' ? 'Agente PQR' : (msg.emisor === 'asesor' ? 'Asesor' : (msg.emisor === 'sistema' ? 'Sistema' : 'Usuario'))}
                  </div>
                  <div>{msg.contenido}</div>
                </div>
              ))}
              {transcripcion.length === 0 && <p style={{ textAlign: 'center', color: '#888' }}>Cargando transcripción...</p>}
            </div>
          </div>
        </div>
      )}

    </div>
  );
};

export default AdminHistorial;