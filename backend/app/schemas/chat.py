# ==============================================================================
# Esquemas Pydantic - Agente PQR Universidad de Cundinamarca
# ==============================================================================

from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime

class InicioSesionRequest(BaseModel):
    nombre: str = Field(..., min_length=2)
    documento: str = Field(..., min_length=5)
    correo: str
    celular: str
    sede: str
    tipo_usuario: str
    politicas_aceptadas: bool

class PeticionUsuario(BaseModel):
    sesion_id: str = Field(...)
    texto_pregunta: str = Field(..., min_length=1)

class ComandoAsesor(BaseModel):
    sesion_id: str
    accion: str
    motivo: Optional[str] = None

class MetadatosRAG(BaseModel):
    similitud: Optional[float] = None
    fuente: Optional[str] = None
    tiempo_procesamiento: Optional[float] = None

class RespuestaChat(BaseModel):
    sesion_id: str
    estado_actual: str
    respuesta_sistema: str
    metadatos: Optional[MetadatosRAG] = None
    opciones: Optional[List[dict]] = None

class NotificacionSistema(BaseModel):
    estado_sesion: str
    notificacion: str

class MensajeResponse(BaseModel):
    id: Any
    sesion_id: Any
    emisor: str
    contenido: str
    similitud_rag: Optional[float] = None
    url_fuente: Optional[str] = None
    fecha_creacion: Optional[datetime] = None

    class Config:
        from_attributes = True

class MensajeDTO(BaseModel):
    id: Any
    sesion_id: Any
    emisor: str
    contenido: str
    similitud_rag: Optional[float] = None
    url_fuente: Optional[str] = None
    fecha_creacion: Optional[datetime] = None

    class Config:
        from_attributes = True

class SesionDTO(BaseModel):
    id: Any
    estudiante_id: str
    nombre_usuario: Optional[str] = None
    documento_identidad: Optional[str] = None
    correo: Optional[str] = None
    celular: Optional[str] = None
    sede: Optional[str] = None
    tipo_usuario: Optional[str] = None
    estado: str
    fecha_creacion: Optional[datetime] = None
    fecha_actualizacion: Optional[datetime] = None
    mensajes: Optional[List[MensajeDTO]] = []

    class Config:
        from_attributes = True

class ListaSesionesPendientes(BaseModel):
    total_pendientes: int
    sesiones: List[SesionDTO]