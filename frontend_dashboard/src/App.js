import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import DashboardLayout from './components/DashboardLayout';
import AdminConocimiento from './pages/AdminConocimiento';
import AdminEstadisticas from './pages/AdminEstadisticas';
import AdminBandejaPQR from './pages/AdminBandejaPQR';
import AdminHistorial from './pages/AdminHistorial';

function App() {
  return (
    <Router>
      <DashboardLayout>
        <Routes>
          <Route path="/" element={<Navigate to="/admin/bandeja" replace />} />
          <Route path="/admin/bandeja" element={<AdminBandejaPQR />} />
          <Route path="/admin/conocimiento" element={<AdminConocimiento />} />
          <Route path="/admin/historial" element={<AdminHistorial />} />         
         <Route path="/admin/estadisticas" element={<AdminEstadisticas />} />
        </Routes>
      </DashboardLayout>
    </Router>
  );
}

export default App;