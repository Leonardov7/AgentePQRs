// ==============================================================================
// Punto de Entrada React - Agente PQR (Widget)
// ==============================================================================

import React from 'react';
import WidgetPQR from './Widget';

function App() {
  return (
    <div className="App">
      {/* 
        El componente principal la página web iría aquí.
        El WidgetPQR se renderiza al final para que flote sobre todo el contenido
        gracias a su posición 'fixed' en el CSS.
      */}
      <div style={{ padding: '20px', fontFamily: 'sans-serif' }}>
        <h1>Universidad de Cundinamarca</h1>
        <p>Simulador de la página web institucional.</p>
      </div>

      {/* Inyección del Agente  */}
      <WidgetPQR />
    </div>
  );
}

export default App;