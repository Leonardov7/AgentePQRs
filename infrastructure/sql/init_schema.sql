-- ==============================================================================
-- Esquema de Base de Datos Relacional - Agente PQR Universidad de Cundinamarca
-- Motor Objetivo - PostgreSQL 16
-- Descripción - Tablas operacionales para el orquestador cognitivo, manejo de sesiones,
-- historial de chat y escalamiento a humanos.
-- ==============================================================================

-- Habilitar extensión para generación de UUIDs nativos
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Tabla de Asesores (Personal de la Universidad)
CREATE TABLE asesores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre VARCHAR(100) NOT NULL,
    correo VARCHAR(100) UNIQUE NOT NULL,
    rol VARCHAR(50) DEFAULT 'asesor', -- Valores permitidos 'asesor', 'coordinador', 'admin'
    estado VARCHAR(20) DEFAULT 'offline', -- Valores permitidos 'online', 'offline', 'ocupado'
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Tabla de Sesiones (Interacciones de Estudiantes)
CREATE TABLE sesiones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    estudiante_id VARCHAR(100), -- Identificador temporal anónimo o matrícula del estudiante logueado
    estado VARCHAR(50) DEFAULT 'atencion_bot', -- Valores permitidos 'atencion_bot', 'en_cola', 'atencion_humana', 'cerrada', 'ticket_asincrono'
    asesor_asignado_id UUID REFERENCES asesores(id) ON DELETE SET NULL,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Tabla de Mensajes (Historial detallado del chat)
CREATE TABLE mensajes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sesion_id UUID NOT NULL REFERENCES sesiones(id) ON DELETE CASCADE,
    emisor VARCHAR(20) NOT NULL, -- Valores permitidos 'estudiante', 'bot', 'asesor', 'sistema'
    contenido TEXT NOT NULL,
    similitud_rag NUMERIC(4, 3), -- Puntaje de similitud devuelto por Dify (ejemplo 0.852)
    url_fuente VARCHAR(500), -- Deep Link de donde Dify extrajo la información exacta
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Índices B-Tree para optimización de consultas de reportería y carga de historial en tiempo real
CREATE INDEX idx_mensajes_sesion ON mensajes(sesion_id);
CREATE INDEX idx_sesiones_estado ON sesiones(estado);

-- 4. Tabla de Tickets Diferidos (Gestión fuera de horario laboral)
CREATE TABLE tickets_pendientes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sesion_id UUID UNIQUE NOT NULL REFERENCES sesiones(id) ON DELETE CASCADE,
    correo_contacto VARCHAR(100) NOT NULL,
    documento_identidad VARCHAR(50),
    resumen_problema TEXT NOT NULL,
    estado VARCHAR(20) DEFAULT 'abierto', -- Valores permitidos 'abierto', 'en_proceso', 'resuelto'
    asesor_resolucion_id UUID REFERENCES asesores(id) ON DELETE SET NULL,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resuelto_en TIMESTAMP WITH TIME ZONE
);