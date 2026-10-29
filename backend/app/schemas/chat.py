# ==============================================================================
# Esquemas Pydantic - Agente PQR Universidad de Cundinamarca
# Descripción: Validación estricta de datos de entrada y salida para la API REST,
# serialización de historiales de sesión y metadatos del motor RAG.
# ==============================================================================

from pydantic import BaseModel, Field, UUID4
from typing import Optional, List, Dict, Any
from datetime import datetime

# ------------------------------------------------------------------------------
# Esquemas de Entrada (Requests)
# ------------------------------------------------------------------------------

class PeticionUsuario(BaseModel):
    """
    Esquema de validación para el payload entrante desde el Widget de React.
    Reemplaza al antiguo esquema PeticionEstudiante para universalizar el rol.
    """
    sesion_id: str = Field(..., description="UUID v4 que identifica la sesión única del chat.")
    texto_pregunta: str = Field(..., min_length=1, description="El mensaje crudo enviado por el usuario.")

class ComandoAsesor(BaseModel):
    """
    Esquema para acciones administrativas ejecutadas por los asesores humanos 
    desde el panel de control (ej. forzar cierre de sesión).
    """
    sesion_id: str = Field(..., description="UUID de la sesión a intervenir.")
    accion: str = Field(..., description="Comando a ejecutar: 'cerrar', 'transferir', 'suspender'.")
    motivo: Optional[str] = Field(None, description="Razón administrativa de la acción.")

# ------------------------------------------------------------------------------
# Esquemas de Salida (Responses)
# ------------------------------------------------------------------------------

class MetadatosRAG(BaseModel):
    """
    Estructura de datos para empaquetar la información de auditoría del motor de similitud vectorial.
    """
    similitud: Optional[float] = Field(None, description="Puntaje de similitud del 0.0 al 1.0 evaluado por Dify.")
    fuente: Optional[str] = Field(None, description="Nombre del documento o bloque Markdown recuperado.")
    tiempo_procesamiento: Optional[float] = Field(None, description="Milisegundos que tardó el LLM en responder.")

class RespuestaChat(BaseModel):
    """
    Esquema de respuesta estándar del endpoint POST /api/v1/chat/enviar.
    """
    sesion_id: str
    estado_actual: str = Field(..., description="Estado de la máquina: 'atencion_bot', 'en_cola', 'atencion_humana'.")
    respuesta_sistema: str = Field(..., description="El texto final sanitizado y aprobado para mostrar al usuario.")
    metadatos: Optional[MetadatosRAG] = None

class NotificacionSistema(BaseModel):
    """
    Esquema para respuestas de error, advertencias de enrutamiento o alertas operativas.
    """
    estado_sesion: str
    notificacion: str

class MensajeResponse(BaseModel):
    """
    Esquema de salida utilizado por el controlador de asesores para cargar el historial de chats.
    """
    id: Any
    sesion_id: Any
    emisor: str
    contenido: str
    similitud_rag: Optional[float] = None
    url_fuente: Optional[str] = None
    fecha_creacion: Optional[datetime] = None

    class Config:
        from_attributes = True

# ------------------------------------------------------------------------------
# Esquemas de Historial y Persistencia (Data Transfer Objects)
# ------------------------------------------------------------------------------

class MensajeDTO(BaseModel):
    """
    Objeto de transferencia para la serialización de mensajes individuales extraídos de PostgreSQL.
    """
    id: Any
    sesion_id: Any
    emisor: str = Field(..., description="Roles válidos: 'usuario', 'bot', 'sistema', 'asesor'.")
    contenido: str
    similitud_rag: Optional[float] = None
    url_fuente: Optional[str] = None
    fecha_creacion: Optional[datetime] = None

    class Config:
        from_attributes = True

class SesionDTO(BaseModel):
    """
    Objeto de transferencia para renderizar el estado de una sesión de PQR en el Dashboard administrativo.
    """
    id: Any
    estudiante_id: str
    estado: str
    fecha_creacion: Optional[datetime] = None
    fecha_actualizacion: Optional[datetime] = None
    mensajes: Optional[List[MensajeDTO]] = []

    class Config:
        from_attributes = True

class ListaSesionesPendientes(BaseModel):
    """
    Esquema para la consulta masiva de sesiones encoladas esperando atención humana.
    """
    total_pendientes: int
    sesiones: List[SesionDTO]