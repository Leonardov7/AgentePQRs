// ==============================================================================
// Dashboard Administrativo - Centro de Atención (Asesores Humanos en Vivo)
// ==============================================================================
import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import '../Dashboard.css';

const API_BASE_URL = "http://localhost:8000/api/v1/admin";
const WS_BASE_URL = "ws://localhost:8000/api/v1/chat";

const AdminBandejaPQR = () => {
  const [sesionesPendientes, setSesionesPendientes] = useState([]);
  
  // Persistencia de la sesión activa al cambiar de pestaña
  const [sesionActiva, setSesionActiva] = useState(() => {
    return localStorage.getItem('sesionPQRActiva') || null;
  });
  
  const [mensajes, setMensajes] = useState([]);
  const [textoInput, setTextoInput] = useState("");
  
  const [tipologia, setTipologia] = useState("");
  const [notaInterna, setNotaInterna] = useState("");
  
  const wsRef = useRef(null);
  const mensajesEndRef = useRef(null);

  const cargarSesionesPendientes = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/sesiones/pendientes`);
      setSesionesPendientes(response.data);
    } catch (error) {
      console.error("Error obteniendo la cola de PQRs:", error);
    }
  };

  const conectarWebSocket = useCallback((sesionId) => {
    const ws = new WebSocket(`${WS_BASE_URL}/ws/${sesionId}/asesor`);
    ws.onmessage = (evento) => {
      const data = JSON.parse(evento.data);
      if (data.tipo === "nuevo_mensaje" || data.tipo === "alerta_sistema") {
        setMensajes(prev => [...prev, { emisor: data.emisor, contenido: data.contenido }]);
      }
    };
    wsRef.current = ws;
  }, []);

  const seleccionarSesion = useCallback(async (sesionId) => {
    if (wsRef.current) wsRef.current.close();
    setSesionActiva(sesionId);
    localStorage.setItem('sesionPQRActiva', sesionId);
    setMensajes([]);
    setTipologia(""); 
    setNotaInterna(""); 

    try {
      const response = await axios.get(`${API_BASE_URL}/sesiones/${sesionId}/historial`);
      setMensajes(response.data);
      conectarWebSocket(sesionId);
    } catch (error) {
      console.error("Error cargando historial:", error);
      if (error.response && error.response.status === 404) {
        setSesionActiva(null);
        localStorage.removeItem('sesionPQRActiva');
        setMensajes([]);
      }
    }
  }, [conectarWebSocket]);

  useEffect(() => {
    cargarSesionesPendientes();
    const intervalo = setInterval(cargarSesionesPendientes, 10000);
    return () => clearInterval(intervalo);
  }, []);

  useEffect(() => {
    if (sesionActiva) {
      seleccionarSesion(sesionActiva);
    }
  }, [sesionActiva, seleccionarSesion]);

  useEffect(() => {
    mensajesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [mensajes]);

  const enviarMensaje = () => {
    if (!textoInput.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ contenido: textoInput }));
    setMensajes(prev => [...prev, { emisor: 'asesor', contenido: textoInput }]);
    setTextoInput("");
  };

  const cerrarSesionPQR = async () => {
    if (!tipologia) {
      alert("Debes seleccionar una tipología antes de cerrar la PQR.");
      return;
    }
    if (!window.confirm("¿Deseas clausurar y resolver este ticket PQR?")) return;
    try {
      await axios.put(`${API_BASE_URL}/sesiones/${sesionActiva}/cerrar`, {
        tipologia: tipologia,
        nota_interna: notaInterna
      });
      if (wsRef.current) wsRef.current.close();
      setSesionActiva(null);
      localStorage.removeItem('sesionPQRActiva');
      setMensajes([]);
      setTipologia("");
      setNotaInterna("");
      cargarSesionesPendientes();
      alert("PQR cerrada con éxito.");
    } catch (error) {
      console.error("Error al cerrar sesión:", error);
    }
  };

  const sesionData = sesionesPendientes.find(s => s.sesion_id === sesionActiva);

  return (
    <div className="dashboard-container">
      {/* Columna Izquierda: Cola de Tickets */}
      <div className="sidebar-conversaciones">
        <div className="sidebar-header">
          Centro de Atención ({sesionesPendientes.length})
        </div>
        <div style={{ overflowY: 'auto', flex: 1 }}>
          {sesionesPendientes.length === 0 ? (
            <div style={{ padding: '20px', textAlign: 'center', color: '#888', fontSize: '0.85rem' }}>
              No hay PQRs en espera.
            </div>
          ) : (
            sesionesPendientes.map(sesion => (
              <div 
                key={sesion.sesion_id} 
                className={`sesion-item ${sesionActiva === sesion.sesion_id ? 'activa' : ''}`}
                onClick={() => seleccionarSesion(sesion.sesion_id)}
              >
                <div style={{ fontSize: '0.8rem', fontWeight: 'bold', color: '#333' }}>
                  {sesion.nombre_usuario || `Ticket #${sesion.sesion_id.substring(0, 8)}`}
                </div>
                <div style={{ fontSize: '0.75rem', color: '#666' }}>{sesion.sede} - {sesion.tipo_usuario}</div>
                <div style={{ fontSize: '0.75rem', color: '#d32f2f', marginTop: '2px', fontWeight: '500' }}>
                  Atención Humana
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Columna Central: Chat en Vivo */}
      {!sesionActiva ? (
        <div className="pantalla-vacia">
          Selecciona una PQR de la barra lateral izquierda para iniciar la atención en tiempo real.
        </div>
      ) : (
        <div className="chat-central">
          <div className="chat-header-info">
            <span style={{ fontSize: '0.9rem', fontWeight: 'bold' }}>Atendiendo Sesión Activa</span>
          </div>
          <div className="mensajes-container">
            {mensajes.map((msg, idx) => (
              <div key={idx} className={`mensaje-burbuja mensaje-${msg.emisor}`}>
                <div style={{ fontSize: '0.7rem', fontWeight: 'bold', marginBottom: '2px', opacity: 0.7 }}>
                  {msg.emisor.toUpperCase()}
                </div>
                {msg.contenido}
              </div>
            ))}
            <div ref={mensajesEndRef} />
          </div>
          <div className="input-container">
            <input 
              type="text" 
              placeholder="Escribe tu respuesta como asesor institucional..."
              value={textoInput}
              onChange={(e) => setTextoInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && enviarMensaje()}
            />
            <button onClick={enviarMensaje}>Enviar</button>
          </div>
        </div>
      )}

      {/* Columna Derecha: Detalles y Metadatos */}
      <div className="panel-derecho">
        <h3>Detalles del Ticket</h3>
        {!sesionActiva ? (
          <p style={{ fontSize: '0.85rem', color: '#777', marginTop: '1rem' }}>
            Sin ticket seleccionado.
          </p>
        ) : (
          <>
            {/* BLOQUE 1: TRAZABILIDAD */}
            <div className="meta-grupo">
              <label>ID de Sesión</label>
              <span style={{ fontSize: '0.75rem', wordBreak: 'break-all' }}>{sesionActiva}</span>
            </div>
            <div className="meta-grupo">
              <label>Estado Actual</label>
              <span style={{ color: '#2e7d32', fontWeight: 'bold' }}>En Cola de Intervención</span>
            </div>

            {/* BLOQUE 2: DETALLES DEL USUARIO CAPTURADOS */}
            <div style={{ margin: '1.5rem 0', borderTop: '1px solid #e0e0e0', paddingTop: '1rem' }}>
              <h4 style={{ fontSize: '0.9rem', marginBottom: '10px', color: '#444' }}>Perfil del Usuario</h4>
              <div className="meta-grupo">
                <label>Nombre Completo</label>
                <span>{sesionData?.nombre_usuario || 'N/A'}</span>
              </div>
              <div className="meta-grupo">
                <label>Identificación</label>
                <span>{sesionData?.documento_identidad || 'N/A'}</span>
              </div>
              <div className="meta-grupo">
                <label>Contacto</label>
                <span style={{ display: 'block' }}>{sesionData?.celular}</span>
                <span style={{ display: 'block' }}>{sesionData?.correo}</span>
              </div>
              <div className="meta-grupo">
                <label>Sede y Rol</label>
                <span>{sesionData?.sede} ({sesionData?.tipo_usuario})</span>
              </div>
            </div>

            {/* BLOQUE 3: GESTIÓN ADMINISTRATIVA */}
            <div style={{ margin: '1.5rem 0', borderTop: '1px solid #e0e0e0', paddingTop: '1rem' }}>
              <h4 style={{ fontSize: '0.9rem', marginBottom: '10px', color: '#444' }}>Resolución Operativa</h4>
              <div className="meta-grupo">
                <label>Tipología Institucional</label>
                <select 
                  value={tipologia} 
                  onChange={(e) => setTipologia(e.target.value)}
                  style={{ width: '100%', padding: '8px', marginTop: '4px', borderRadius: '4px', border: '1px solid #ccc', outline: 'none' }}
                >
                  <option value="">Clasificación del caso...</option>
                  <option value="peticion">Petición</option>
                  <option value="queja">Queja</option>
                  <option value="reclamo">Reclamo</option>
                  <option value="sugerencia">Sugerencia</option>
                  <option value="felicitacion">Felicitación</option>
                </select>
              </div>
              <div className="meta-grupo">
                <label>Notas Internas</label>
                <textarea 
                  value={notaInterna}
                  onChange={(e) => setNotaInterna(e.target.value)}
                  rows="4"
                  placeholder="Detalles de la solución o escalamiento..."
                  style={{ width: '100%', padding: '8px', marginTop: '4px', borderRadius: '4px', border: '1px solid #ccc', resize: 'vertical', outline: 'none' }}
                />
              </div>
            </div>

            {/* BLOQUE 4: ACCIONES DEL TICKET */}
            <div className="acciones-ticket">
              <button className="btn-accion btn-reasignar">Reasignar a otra Cola</button>
              <button className="btn-accion btn-resolver" onClick={cerrarSesionPQR}>
                Resolver y Cerrar PQR
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default AdminBandejaPQR;