import React, { useState, useEffect, useRef } from 'react';
import './Widget.css'; 

const Widget = () => {
  // ---------------------------------------------------------
  // Estados de Interfaz
  // ---------------------------------------------------------
  const [abierto, setAbierto] = useState(false);
  const [mostrarTooltip, setMostrarTooltip] = useState(false);
  
  // ---------------------------------------------------------
  // Estados Operativos
  // ---------------------------------------------------------
  const [sesionIniciada, setSesionIniciada] = useState(false);
  const [cargando, setCargando] = useState(false);
  const [sesionId, setSesionId] = useState("");
  
  const [mensajes, setMensajes] = useState([]);
  const [textoPregunta, setTextoPregunta] = useState("");
  const [escribiendo, setEscribiendo] = useState(false);
  const mensajesEndRef = useRef(null);
  const wsRef = useRef(null);

  // ---------------------------------------------------------
  // Datos Quemados para Pruebas Rápidas (Bypass de Tipeo)
  // ---------------------------------------------------------
  const [formData, setFormData] = useState({
    nombre: "Usuario de Prueba",
    documento: "100200300",
    correo: "estudiante.prueba@ucundinamarca.edu.co",
    celular: "3001234567",
    sede: "Fusagasugá",
    tipo_usuario: "Estudiante",
    politicas_aceptadas: true
  });

  // Animación suave del tooltip
  useEffect(() => {
    if (!abierto) {
      const timer = setTimeout(() => setMostrarTooltip(true), 3000);
      return () => clearTimeout(timer);
    } else {
      setMostrarTooltip(false);
    }
  }, [abierto]);

  useEffect(() => {
    mensajesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [mensajes, sesionIniciada]);

  // RESTAURACIÓN DE BIDIRECCIONALIDAD Y ENRUTAMIENTO DIFY VÍA WEBSOCKET
  useEffect(() => {
    if (sesionIniciada && sesionId) {
      const ws = new WebSocket(`ws://localhost:8000/api/v1/chat/ws/${sesionId}/usuario`);
      ws.onmessage = (evento) => {
        const data = JSON.parse(evento.data);
        
        // Apagamos el indicador de escritura apenas recibimos cualquier respuesta
        setEscribiendo(false);

        if (data.tipo === "nuevo_mensaje" || data.tipo === "alerta_sistema") {
          setMensajes(prev => [...prev, { 
            emisor: data.emisor, 
            contenido: data.contenido,
            opciones: data.opciones 
          }]);
        }
      };
      wsRef.current = ws;
      return () => ws.close();
    }
  }, [sesionIniciada, sesionId]);

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData({
      ...formData,
      [name]: type === 'checkbox' ? checked : value
    });
  };

  // ---------------------------------------------------------
  // Inicialización (Endpoint POST de la Fase 1)
  // ---------------------------------------------------------
  const iniciarChat = async (e) => {
    e.preventDefault();
    setCargando(true);
    
    try {
      const respuesta = await fetch("http://localhost:8000/api/v1/chat/iniciar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData)
      });
      
      const datos = await respuesta.json();
      
      if (respuesta.ok) {
        setSesionId(datos.sesion_id);
        setSesionIniciada(true);
        setMensajes([{
          emisor: "bot", 
          contenido: `¡Hola ${formData.nombre.split(' ')[0]}! Soy tu agente PQR de la Universidad de Cundinamarca. ¿En qué te puedo asesorar hoy?`
        }]);
      } else {
        alert("No pudimos iniciar la sesión: " + (datos.detail || "Verifica los campos."));
      }
    } catch (error) {
      console.error("Fallo de red:", error);
      alert("Error conectando con el servidor institucional.");
    } finally {
      setCargando(false);
    }
  };

  // ---------------------------------------------------------
  // Ciclo de Mensajería Unificado (Solo WebSocket)
  // ---------------------------------------------------------
  const enviarMensajeREST = async (e) => {
    e.preventDefault();
    if (!textoPregunta.trim()) return;

    const textoEnviado = textoPregunta;
    setTextoPregunta("");
    
    // Mostramos el mensaje en la pantalla del usuario inmediatamente
    setMensajes((prev) => [...prev, { emisor: "usuario", contenido: textoEnviado }]);

    // El backend se encarga ahora de rutear si va a Dify o al Humano
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      setEscribiendo(true); // Encendemos el indicador de "Procesando tu solicitud..."
      wsRef.current.send(JSON.stringify({ contenido: textoEnviado }));
    } else {
      console.error("El WebSocket no está conectado.");
      setMensajes((prev) => [...prev, { emisor: "sistema", contenido: "Error de conexión en tiempo real. Intenta recargar la página." }]);
    }
  };

  const enviarOpcionWebSocket = (opcionValue) => {
    setTextoPregunta(opcionValue);
    setTimeout(() => document.querySelector('.udec-chat-input-form button').click(), 50);
  };

  return (
    <div className="udec-widget-root">
      
      {/* =========================================================
          BOTÓN FLOTANTE Y TOOLTIP
          ========================================================= */}
      {!abierto && (
        <div className="udec-launcher-container">
          {mostrarTooltip && (
            <div className="udec-tooltip">
              ¿Necesitas ayuda? Habla con nuestro agente
            </div>
          )}
          <button className="udec-launcher-btn" onClick={() => setAbierto(true)}>
            <svg viewBox="0 0 24 24" width="28" height="28" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5 0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29 1.94-3.5 3.22-6 3.22z"/>
            </svg>
          </button>
        </div>
      )}

      {/* =========================================================
          PANEL DEL CHAT ENCAPSULADO
          ========================================================= */}
      {abierto && (
        <div className="udec-chat-panel">
          
          <div className="udec-chat-header">
            <div className="udec-header-info">
              <span className="udec-header-avatar">🤖</span>
              <div>
                <h4 style={{margin: 0, fontSize: '0.95rem'}}>Agente PQR</h4>
                <p style={{margin: 0, fontSize: '0.7rem', opacity: 0.8}}>Universidad de Cundinamarca</p>
              </div>
            </div>
            <button className="udec-close-btn" onClick={() => setAbierto(false)}>✕</button>
          </div>

          <div className="udec-chat-body">
            
            {/* --- FASE PRE-CHAT: FORMULARIO INYECTADO EN LA BURBUJA --- */}
            {!sesionIniciada ? (
              <div className="udec-prechat-wrapper">
                <div className="udec-prechat-message">
                  <p>Para brindarte una orientación personalizada, por favor confírmanos tus datos institucionales.</p>
                </div>
                
                <form className="udec-form" onSubmit={iniciarChat}>
                  
                  {/* Ícono de Usuario */}
                  <div className="udec-input-group">
                    <span className="udec-input-icon">
                      <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>
                    </span>
                    <input type="text" name="nombre" value={formData.nombre} onChange={handleInputChange} placeholder="Nombre Completo" required />
                  </div>
                  
                  {/* Ícono de Identificación */}
                  <div className="udec-input-group">
                    <span className="udec-input-icon">
                      <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M21 3H3c-1.11 0-2 .89-2 2v14c0 1.11.89 2 2 2h18c1.11 0 2-.89 2-2V5c0-1.11-.89-2-2-2zm-9 15H4v-2h8v2zm0-4H4v-2h8v2zm6-4h-2V8h2v2zm2 4h-6V8h6v2z"/></svg>
                    </span>
                    <input type="text" name="documento" value={formData.documento} onChange={handleInputChange} placeholder="Cédula o NIT" required />
                  </div>

                  {/* Ícono de Correo */}
                  <div className="udec-input-group">
                    <span className="udec-input-icon">
                      <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/></svg>
                    </span>
                    <input type="email" name="correo" value={formData.correo} onChange={handleInputChange} placeholder="Correo Electrónico" required />
                  </div>

                  {/* Ícono de Celular */}
                  <div className="udec-input-group">
                    <span className="udec-input-icon">
                      <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M17 1.01L7 1c-1.1 0-2 .9-2 2v18c0 1.1.9 2 2 2h10c1.1 0 2-.9 2-2V3c0-1.1-.9-1.99-2-1.99zM17 19H7V5h10v14z"/></svg>
                    </span>
                    <input type="tel" name="celular" value={formData.celular} onChange={handleInputChange} placeholder="Teléfono / Celular" required />
                  </div>
                  
                  {/* Ícono de Sede / Edificio */}
                  <div className="udec-input-group">
                    <span className="udec-input-icon">
                      <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M15 11V5l-3-3-3 3v2H3v14h18V11h-6zm-8 8H5v-2h2v2zm0-4H5v-2h2v2zm0-4H5V9h2v2zm6 8h-2v-2h2v2zm0-4h-2v-2h2v2zm0-4h-2V7h2v2zm0-4h-2V5h2v2zm6 12h-2v-2h2v2zm0-4h-2v-2h2v2z"/></svg>
                    </span>
                    <select name="sede" value={formData.sede} onChange={handleInputChange} required>
                      <option value="">Selecciona tu Sede...</option>
                      <option value="Fusagasugá">Fusagasugá</option>
                      <option value="Girardot">Girardot</option>
                      <option value="Ubaté">Ubaté</option>
                      <option value="Chía">Chía</option>
                      <option value="Facatativá">Facatativá</option>
                      <option value="Soacha">Soacha</option>
                      <option value="Zipaquirá">Zipaquirá</option>
                    </select>
                  </div>

                  {/* Ícono de Tipo de Usuario / Birrete */}
                  <div className="udec-input-group">
                    <span className="udec-input-icon">
                      <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M12 3L1 9l4 2.18v6L12 21l7-3.82v-6l2-1.09V17h2V9L12 3zm6.82 6L12 12.72 5.18 9 12 5.28 18.82 9zM17 15.99l-5 2.73-5-2.73v-3.72l5 2.73 5-2.73v3.72z"/></svg>
                    </span>
                    <select name="tipo_usuario" value={formData.tipo_usuario} onChange={handleInputChange} required>
                      <option value="">Soy...</option>
                      <option value="Estudiante">Estudiante</option>
                      <option value="Docente">Docente</option>
                      <option value="Administrativo">Administrativo</option>
                      <option value="Graduado">Graduado</option>
                      <option value="Ciudadano">Ciudadano</option>
                    </select>
                  </div>

                  <label className="udec-checkbox">
                    <input type="checkbox" name="politicas_aceptadas" checked={formData.politicas_aceptadas} onChange={handleInputChange} required />
                    <span>Acepto la <a href="http://localhost:8000/api/v1/admin/configuracion/politicas" target="_blank" rel="noopener noreferrer">política de tratamiento de datos</a>.</span>
                  </label>

                  <button type="submit" disabled={cargando} className="udec-submit-btn">
                    {cargando ? "Iniciando..." : "Comenzar Chat"}
                  </button>
                </form>
              </div>

            ) : (
              
              /* --- FASE IN-CHAT: MENSAJES Y CONVERSACIÓN --- */
              <div className="udec-chat-messages-container">
                <div className="udec-messages-scroll">
                  {mensajes.map((msg, idx) => (
                    <div key={idx} className={`udec-bubble-wrapper ${msg?.emisor?.includes('usuario') ? 'derecha' : 'izquierda'} ${msg.emisor === 'sistema' ? 'sistema' : ''}`}>
                      
                      {/* IDENTIDAD: Diferenciar Bot, Asesor y Usuario (Estilo WhatsApp) */}
                      {msg.emisor === 'asesor' && <div className="udec-asesor-tag">👤 Asesor Institucional</div>}
                      {msg.emisor === 'bot' && <div className="udec-asesor-tag" style={{color: '#2980b9'}}>🤖 Agente PQR</div>}
                      {msg.emisor === 'usuario' && <div className="udec-asesor-tag" style={{textAlign: 'right', color: '#555'}}>{formData.nombre.split(' ')[0]}</div>}

                      <div className="udec-bubble">
                        {msg.contenido}
                      </div>

                      {/* RENDERIZADO DE BOTONES DE OPCIÓN (Escalamiento interactivo) */}
                      {msg.opciones && (
                        <div className="widget-opciones-container">
                          {msg.opciones.map((opcion, i) => (
                            <button 
                              key={i} 
                              className="widget-opcion-btn"
                              onClick={() => enviarOpcionWebSocket(opcion.value)}
                            >
                              {opcion.label}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                  
                  {/* INDICADOR DE ESCRITURA RESTAURADO (Sombreado Analizando) */}
                  {escribiendo && (
                    <div className="udec-bubble-wrapper izquierda">
                       <div className="udec-asesor-tag" style={{color: '#2980b9'}}>🤖 Agente PQR</div>
                       <div className="udec-bubble escribiendo-indicador">
                          Procesando tu solicitud...
                       </div>
                    </div>
                  )}

                  <div ref={mensajesEndRef} />
                </div>
                
                <form className="udec-chat-input-form" onSubmit={enviarMensajeREST}>
                  <input 
                    type="text" 
                    value={textoPregunta} 
                    onChange={(e) => setTextoPregunta(e.target.value)} 
                    placeholder="Escribe tu mensaje..." 
                  />
                  <button type="submit" disabled={!textoPregunta.trim()}>
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
                      <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                    </svg>
                  </button>
                </form>
              </div>
            )}

          </div>
        </div>
      )}
    </div>
  );
};

export default Widget;