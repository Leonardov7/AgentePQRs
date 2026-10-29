// ==============================================================================
// Componente Widget React - Agente PQR
// Descripción: Interfaz del estudiante con enrutamiento híbrido (REST / WS)
// ==============================================================================

import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';
import './Widget.css';

const API_BASE_URL = "http://localhost:8000/api/v1";
const WS_BASE_URL = "ws://localhost:8000/api/v1";

const WidgetPQR = () => {
    // Estados de memoria del componente
    const [sesionId] = useState(uuidv4()); // Generamos un UUID único para la sesión al montar el componente
    const [mensajes, setMensajes] = useState([{ emisor: 'bot', contenido: 'Hola. Soy el agente inteligente de Peticiones, Quejas y Reclamos de la Universidad de Cundinamarca. ¿En qué te puedo ayudar hoy?' }]);
    const [textoInput, setTextoInput] = useState("");
    const [cargando, setCargando] = useState(false);
    
    // Máquina de estados de red
    const [modoConexion, setModoConexion] = useState("REST"); // 'REST' (Bot) o 'WS' (Humano)
    const wsRef = useRef(null); // Mantiene viva la referencia al túnel TCP
    const mensajesEndRef = useRef(null);

    // Auto-scroll al último mensaje
    useEffect(() => {
        mensajesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [mensajes]);

    // Limpieza de WebSocket al desmontar el componente (evita memory leaks en el navegador)
    useEffect(() => {
        return () => {
            if (wsRef.current) wsRef.current.close();
        };
    }, []);

    // ------------------------------------------------------------------------------
    // Conexión y Gestión de WebSockets
    // ------------------------------------------------------------------------------
    const iniciarConexionWebSocket = () => {
        if (wsRef.current) return; // Evitar conexiones duplicadas
        
        const ws = new WebSocket(`${WS_BASE_URL}/chat/ws/${sesionId}/estudiante`);
        
        ws.onopen = () => {
            console.log("Túnel WebSocket establecido con el Orquestador.");
            setModoConexion("WS");
        };
        
        ws.onmessage = (evento) => {
            const data = JSON.parse(evento.data);
            if (data.tipo === "nuevo_mensaje" || data.tipo === "alerta_sistema") {
                setMensajes(prev => [...prev, { emisor: data.emisor, contenido: data.contenido }]);
            }
        };
        
        ws.onclose = () => {
            console.log("WebSocket desconectado.");
            setModoConexion("CERRADO");
        };

        wsRef.current = ws;
    };

    // Función atada al botón para transferir manualmente la sesión sincronizando la Base de Datos
    const conectarAsesorHumano = async () => {
        setMensajes(prev => [...prev, { 
            emisor: 'sistema', 
            contenido: 'Iniciando transferencia a entorno seguro en tiempo real. Un asesor se conectará en breve...' 
        }]);

        try {
            // Disparador silencioso al interceptor REST en chat.py para actualizar el estado a "en_cola"
            await axios.post(`${API_BASE_URL}/chat/enviar`, {
                sesion_id: sesionId,
                texto_pregunta: "/escalar_humano"
            });
            
            // Una vez que PostgreSQL registra el estado en_cola, se habilita el socket
            iniciarConexionWebSocket();
            
        } catch (error) {
            console.error("Fallo al sincronizar el estado de escalamiento con PostgreSQL:", error);
            setMensajes(prev => [...prev, { 
                emisor: 'sistema', 
                contenido: 'Error de red al notificar al sistema central. El asesor podría no recibir la alerta en su panel.' 
            }]);
        }
    };

    // ------------------------------------------------------------------------------
    // Envío de Mensajes (Híbrido)
    // ------------------------------------------------------------------------------
    const enviarMensaje = async () => {
        if (!textoInput.trim() || cargando) return;

        const mensajeUsuario = textoInput;
        setTextoInput("");
        setMensajes(prev => [...prev, { emisor: 'estudiante', contenido: mensajeUsuario }]);

        // Vía 1: Conexión WebSocket (El asesor humano está del otro lado)
        if (modoConexion === "WS") {
            if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                wsRef.current.send(JSON.stringify({ contenido: mensajeUsuario }));
            }
            return;
        }

        // Vía 2: Conexión HTTP REST Clásica (El bot de Dify está del otro lado)
        setCargando(true);
        try {
            const response = await axios.post(`${API_BASE_URL}/chat/enviar`, {
                sesion_id: sesionId,
                texto_pregunta: mensajeUsuario
            });

            const datos = response.data;
            
            // Renderizamos la respuesta y guardamos el estado_actual para habilitar el renderizado condicional de los botones
            setMensajes(prev => [...prev, { 
                emisor: 'bot', 
                contenido: datos.respuesta_sistema,
                estado_actual: datos.estado_actual
            }]);

        } catch (error) {
            setMensajes(prev => [...prev, { 
                emisor: 'sistema', 
                contenido: 'Error de red al contactar con el orquestador institucional.' 
            }]);
        } finally {
            setCargando(false);
        }
    };

    const manejarTeclaEnter = (e) => {
        if (e.key === 'Enter') enviarMensaje();
    };

    // ------------------------------------------------------------------------------
    // Renderizado de la Interfaz
    // ------------------------------------------------------------------------------
    return (
        <div className="pqr-widget-container">
            {/* Cabecera */}
            <div className="pqr-widget-header">
                <span>Centro de Ayuda PQR</span>
                <span className="pqr-status-indicator">
                    {modoConexion === "REST" ? "🤖 Bot IA" : modoConexion === "WS" ? "👤 Asesor Humano" : "❌ Desconectado"}
                </span>
            </div>

            {/* Historial de Chat */}
            <div className="pqr-messages-area">
                {mensajes.map((msg, idx) => (
                    <div key={idx}>
                        <div className={`message-bubble message-${msg.emisor}`}>
                            {msg.contenido}
                        </div>
                        
                        {/* Botón condicional evaluando explícitamente el contenido del mensaje */}
                        {msg.emisor === 'bot' && msg.contenido.includes('no poseo información institucional verificada') && idx === mensajes.length - 1 && (
                            <div style={{ display: 'flex', justifyContent: 'center', marginTop: '10px', marginBottom: '10px' }}>
                                <button 
                                    onClick={conectarAsesorHumano}
                                    style={{
                                        padding: '10px 15px',
                                        backgroundColor: '#2980b9',
                                        color: 'white',
                                        border: 'none',
                                        borderRadius: '5px',
                                        cursor: 'pointer',
                                        fontWeight: 'bold',
                                        boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
                                    }}
                                >
                                    🎧 Hablar con un asesor
                                </button>
                            </div>
                        )}
                    </div>
                ))}
                {cargando && (
                    <div className="message-bubble message-bot">
                        <span style={{ fontStyle: 'italic', color: '#888' }}>Analizando directrices...</span>
                    </div>
                )}
                <div ref={mensajesEndRef} />
            </div>

            {/* Cuadro de Texto */}
            <div className="pqr-input-area">
                <input 
                    type="text" 
                    value={textoInput}
                    onChange={(e) => setTextoInput(e.target.value)}
                    onKeyPress={manejarTeclaEnter}
                    placeholder="Escribe tu consulta aquí..."
                    disabled={modoConexion === "CERRADO"}
                />
                <button onClick={enviarMensaje} disabled={cargando || !textoInput.trim() || modoConexion === "CERRADO"}>
                    ➤
                </button>
            </div>
        </div>
    );
};

export default WidgetPQR;