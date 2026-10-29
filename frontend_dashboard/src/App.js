// ==============================================================================
// Dashboard Administrativo React - Agente PQR
// Descripción: Panel de control para asesores (Consumo REST y WebSockets)
// ==============================================================================

import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import AdminConocimiento from './pages/AdminConocimiento'; // Asegúrate de que la ruta coincida donde guardes el archivo
import './Dashboard.css';

const API_BASE_URL = "http://localhost:8000/api/v1/admin";
const WS_BASE_URL = "ws://localhost:8000/api/v1/chat";

// ------------------------------------------------------------------------------
// COMPONENTE INTACTO: Tu dashboard original ahora encapsulado
// ------------------------------------------------------------------------------
function DashboardAsesor() {
  const [sesionesPendientes, setSesionesPendientes] = useState([]);
  const [sesionActiva, setSesionActiva] = useState(null);
  const [mensajes, setMensajes] = useState([]);
  const [textoInput, setTextoInput] = useState("");
  
  const wsRef = useRef(null);
  const mensajesEndRef = useRef(null);

  // Auto-scroll al último mensaje del chat activo
  useEffect(() => {
    mensajesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [mensajes]);

  // ------------------------------------------------------------------------------
  // 1. Monitoreo de Colas (Polling REST)
  // ------------------------------------------------------------------------------
  const cargarSesionesPendientes = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/sesiones/pendientes`);
      setSesionesPendientes(response.data);
    } catch (error) {
      console.error("Error obteniendo la cola de PQRs:", error);
    }
  };

  // Carga inicial y actualización cada 10 segundos
  useEffect(() => {
    cargarSesionesPendientes();
    const intervalo = setInterval(cargarSesionesPendientes, 10000);
    return () => clearInterval(intervalo);
  }, []);

  // ------------------------------------------------------------------------------
  // 2. Selección de Ticket y Carga de Contexto
  // ------------------------------------------------------------------------------
  const seleccionarSesion = async (sesionId) => {
    // Si ya había un WebSocket abierto para otro chat, lo cerramos
    if (wsRef.current) {
      wsRef.current.close();
    }

    setSesionActiva(sesionId);
    setMensajes([]); // Limpiar vista previa

    try {
      // Obtener el contexto previo entre el estudiante y Dify
      const response = await axios.get(`${API_BASE_URL}/sesiones/${sesionId}/historial`);
      setMensajes(response.data);
      
      // Abrir túnel TCP para el chat en vivo asumiendo el rol de 'asesor'
      conectarWebSocket(sesionId);
    } catch (error) {
      console.error("Error cargando historial:", error);
    }
  };

  // ------------------------------------------------------------------------------
  // 3. Gestión de Red en Tiempo Real (WebSockets)
  // ------------------------------------------------------------------------------
  const conectarWebSocket = (sesionId) => {
    const ws = new WebSocket(`${WS_BASE_URL}/ws/${sesionId}/asesor`);
    
    ws.onopen = () => console.log(`WebSocket conectado a sesión ${sesionId}`);
    
    ws.onmessage = (evento) => {
      const data = JSON.parse(evento.data);
      if (data.tipo === "nuevo_mensaje" || data.tipo === "alerta_sistema") {
        setMensajes(prev => [...prev, { emisor: data.emisor, contenido: data.contenido }]);
      }
    };
    
    ws.onclose = () => console.log("Conexión WebSocket cerrada.");
    wsRef.current = ws;
  };

  const enviarMensaje = () => {
    if (!textoInput.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    
    // Al inyectar el mensaje por WS, el backend automáticamente cambia el estado
    // de la base de datos de 'en_cola' a 'atencion_humana'.
    wsRef.current.send(JSON.stringify({ contenido: textoInput }));
    setMensajes(prev => [...prev, { emisor: 'asesor', contenido: textoInput }]);
    setTextoInput("");
  };

  // ------------------------------------------------------------------------------
  // 4. Cierre Administrativo de la PQR
  // ------------------------------------------------------------------------------
  const cerrarSesionPQR = async () => {
    if (!window.confirm("¿Estás seguro de que resolviste esta PQR y deseas clausurarla?")) return;

    try {
      await axios.put(`${API_BASE_URL}/sesiones/${sesionActiva}/cerrar`);
      
      // Limpiar interfaz
      if (wsRef.current) wsRef.current.close();
      setSesionActiva(null);
      setMensajes([]);
      cargarSesionesPendientes(); // Refrescar la barra lateral
      
      alert("PQR clausurada exitosamente.");
    } catch (error) {
      console.error("Error cerrando sesión:", error);
      alert("Hubo un problema al cerrar la sesión.");
    }
  };

  // ------------------------------------------------------------------------------
  // Renderizado de la Interfaz
  // ------------------------------------------------------------------------------
  return (
    <div className="dashboard-container">
      {/* Columna Izquierda: Lista de Espera */}
      <div className="sidebar">
        <div className="sidebar-header">
          Módulo PQRs - Ucundinamarca
        </div>
        
        {/* BOTÓN AÑADIDO PARA NAVEGAR AL SCRAPING SIN ROMPER EL CSS */}
        <div style={{ padding: '10px 15px', backgroundColor: '#eef2f5', borderBottom: '1px solid #ddd', textAlign: 'center' }}>
          <Link to="/admin/conocimiento" style={{ textDecoration: 'none', color: '#2980b9', fontWeight: 'bold', fontSize: '0.9em' }}>
            ⚙️ Panel de Extracción de Datos
          </Link>
        </div>

        <div style={{ overflowY: 'auto' }}>
          {sesionesPendientes.length === 0 ? (
            <div style={{ padding: '20px', textAlign: 'center', color: '#888' }}>
              No hay PQRs pendientes de intervención.
            </div>
          ) : (
            sesionesPendientes.map(sesion => (
              <div 
                key={sesion.sesion_id} 
                className={`sesion-item ${sesionActiva === sesion.sesion_id ? 'activa' : ''}`}
                onClick={() => seleccionarSesion(sesion.sesion_id)}
              >
                <div style={{ fontSize: '0.85em', color: '#555' }}>
                  ID: {sesion.sesion_id.substring(0,8)}...
                </div>
                <div className="badge-alerta">Requiere Humano</div>
                <div style={{ fontSize: '0.75em', marginTop: '5px', color: '#888' }}>
                  Actualizado: {new Date(sesion.actualizado_en).toLocaleTimeString()}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Columna Derecha: Consola de Chat */}
      {!sesionActiva ? (
        <div className="pantalla-vacia">
          Selecciona un ticket de la barra lateral para revisar el contexto.
        </div>
      ) : (
        <div className="chat-area">
          <div className="chat-header">
            <div>
              <strong>Asistiendo Sesión:</strong> {sesionActiva}
            </div>
            <button className="btn-cerrar-ticket" onClick={cerrarSesionPQR}>
              Resolver y Cerrar PQR
            </button>
          </div>

          <div className="mensajes-container">
            {mensajes.map((msg, idx) => (
              <div key={idx} className={`mensaje-burbuja mensaje-${msg.emisor}`}>
                <div style={{ fontSize: '0.75em', fontWeight: 'bold', marginBottom: '4px', opacity: 0.7 }}>
                  {msg.emisor.toUpperCase()}
                </div>
                {msg.contenido}
                
                {/* Renderizar metadatos RAG si existen (auditoría visual) */}
                {msg.similitud_rag && msg.emisor === "sistema" && (
                  <div className="similitud-tag">
                    [Umbral Caído] Similitud evaluada: {msg.similitud_rag}
                  </div>
                )}
              </div>
            ))}
            <div ref={mensajesEndRef} />
          </div>

          <div className="input-container">
            <input 
              type="text" 
              placeholder="Escribe tu respuesta institucional aquí..."
              value={textoInput}
              onChange={(e) => setTextoInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && enviarMensaje()}
            />
            <button onClick={enviarMensaje}>Enviar Mensaje</button>
          </div>
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------------------
// NUEVO COMPONENTE RAÍZ: Actúa como interruptor de pantallas
// ------------------------------------------------------------------------------
function App() {
  return (
    <Router>
      <Routes>
        {/* Ruta principal: Carga tu dashboard intacto */}
        <Route path="/" element={<DashboardAsesor />} />
        
        {/* Ruta secundaria: Carga la vista del administrador para el scraping */}
        <Route path="/admin/conocimiento" element={<AdminConocimiento />} />
      </Routes>
    </Router>
  );
}

export default App;