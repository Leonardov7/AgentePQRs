import React, { useState, useEffect } from 'react';
import './ConfigPanel.css';

const ConfigPanel = ({ isOpen, onClose }) => {
  const [vistaActiva, setVistaActiva] = useState('menu');
  const [urlPoliticas, setUrlPoliticas] = useState("");
  const [umbralRag, setUmbralRag] = useState(35.0);
  const [cargando, setCargando] = useState(false);
  const [mensaje, setMensaje] = useState({ tipo: '', texto: '' });

  useEffect(() => {
    if (isOpen) {
      fetch('http://localhost:8000/api/v1/admin/configuracion/global')
        .then(res => res.json())
        .then(data => {
          setUrlPoliticas(data.url_politicas);
          setUmbralRag(data.umbral_rag);
        })
        .catch(() => console.error("Error cargando configuración"));
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const guardarConfiguracion = async (e) => {
    e.preventDefault();
    setCargando(true);
    setMensaje({ tipo: '', texto: '' });

    try {
      const response = await fetch('http://localhost:8000/api/v1/admin/configuracion/global', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url_politicas: urlPoliticas, umbral_rag: parseFloat(umbralRag) }),
      });

      if (response.ok) {
        setMensaje({ tipo: 'exito', texto: 'Configuración actualizada.' });
      } else {
        setMensaje({ tipo: 'error', texto: 'Error al guardar la configuración.' });
      }
    } catch (error) {
      setMensaje({ tipo: 'error', texto: 'Fallo de conexión al servidor.' });
    } finally {
      setCargando(false);
    }
  };

  const renderMenu = () => (
    <div className="config-menu-lista">
      <div 
        className="config-menu-item" 
        onClick={() => { setVistaActiva('politicas'); setMensaje({ tipo: '', texto: '' }); }}
      >
        <div className="config-item-icon">🔗</div>
        <div className="config-item-text">
          <h5>Tratamiento de Datos</h5>
          <p>Configurar el enlace oficial de la universidad</p>
        </div>
        <div className="config-item-arrow">›</div>
      </div>
      
      <div 
        className="config-menu-item" 
        onClick={() => { setVistaActiva('similitud'); setMensaje({ tipo: '', texto: '' }); }}
      >
        <div className="config-item-icon">🎯</div>
        <div className="config-item-text">
          <h5>Precisión del Asistente</h5>
          <p>Nivel de similitud para respuestas automáticas</p>
        </div>
        <div className="config-item-arrow">›</div>
      </div>

      <div className="config-menu-item futuro">
        <div className="config-item-icon">🤖</div>
        <div className="config-item-text">
          <h5>Personalización del Agente</h5>
          <p>Ajustes de avatar, nombre y tono (Próximamente)</p>
        </div>
      </div>
    </div>
  );

  const renderPoliticas = () => (
    <div className="config-submodulo">
      <p className="config-descripcion">
        Define la URL oficial de Protección de Datos de la Universidad. El Widget redirigirá a los usuarios a este enlace automáticamente.
      </p>

      {mensaje.texto && (
        <div className={`config-alerta ${mensaje.tipo}`}>
          {mensaje.texto}
        </div>
      )}

      <form onSubmit={guardarConfiguracion} className="config-form">
        <label className="config-file-label">
          Enlace Institucional (URL)
          <input 
            type="url" 
            value={urlPoliticas}
            onChange={(e) => setUrlPoliticas(e.target.value)}
            placeholder="https://www.ucundinamarca.edu.co/..."
            required
            style={{ fontWeight: 'normal', cursor: 'text', borderStyle: 'solid' }}
          />
        </label>
        
        <button 
          type="submit" 
          className="config-btn-submit"
          disabled={!urlPoliticas || cargando}
        >
          {cargando ? 'Guardando...' : 'Actualizar Enlace'}
        </button>
      </form>
    </div>
  );

  const renderSimilitud = () => (
    <div className="config-submodulo">
      <p className="config-descripcion">
        Define el nivel de similitud mínimo requerido para que el asistente responda automáticamente. Si la certeza de la Inteligencia Artificial es menor a este porcentaje, se le ofrecerá al usuario la opción de hablar con un humano.
      </p>

      {mensaje.texto && (
        <div className={`config-alerta ${mensaje.tipo}`}>
          {mensaje.texto}
        </div>
      )}

      <form onSubmit={guardarConfiguracion} className="config-form">
        <label className="config-file-label">
          Similitud mínima requerida: {umbralRag}%
          <input 
            type="range" 
            min="10" 
            max="90" 
            step="1" 
            value={umbralRag} 
            onChange={(e) => setUmbralRag(e.target.value)} 
            style={{ marginTop: '10px' }} 
          />
        </label>
        
        <button 
          type="submit" 
          className="config-btn-submit"
          disabled={cargando}
        >
          {cargando ? 'Guardando...' : 'Aplicar Similitud'}
        </button>
      </form>
    </div>
  );

  return (
    <>
      <div className="config-overlay" onClick={onClose}></div>
      <div className="config-drawer">
        <div className="config-drawer-header">
          {vistaActiva !== 'menu' ? (
            <button className="config-back-btn" onClick={() => setVistaActiva('menu')}>
              ‹ Volver
            </button>
          ) : (
            <h3 className="config-title">Ajustes Globales</h3>
          )}
          <button className="config-close-btn" onClick={onClose}>✕</button>
        </div>

        <div className="config-drawer-body">
          {vistaActiva === 'menu' && renderMenu()}
          {vistaActiva === 'politicas' && renderPoliticas()}
          {vistaActiva === 'similitud' && renderSimilitud()}
        </div>
      </div>
    </>
  );
};

export default ConfigPanel;