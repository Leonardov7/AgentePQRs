# ==============================================================================
# Modelos ORM - Agente PQR
# Descripción: Mapeo estricto de las tablas PostgreSQL a clases de Python
# ==============================================================================

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Numeric, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.session import Base

class Asesor(Base):
    __tablename__ = 'asesores'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String(100), nullable=False)
    correo = Column(String(100), unique=True, nullable=False)
    rol = Column(String(50), default='asesor')
    estado = Column(String(20), default='offline')
    creado_en = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relación bidireccional
    sesiones = relationship("Sesion", back_populates="asesor_asignado")
    tickets_resueltos = relationship("TicketPendiente", back_populates="asesor_resolucion")


class Sesion(Base):
    __tablename__ = 'sesiones'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    estudiante_id = Column(String(100), nullable=True)
    estado = Column(String(50), default='atencion_bot')
    asesor_asignado_id = Column(UUID(as_uuid=True), ForeignKey('asesores.id', ondelete='SET NULL'), nullable=True)
    creado_en = Column(DateTime(timezone=True), default=datetime.utcnow)
    actualizado_en = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones bidireccionales
    asesor_asignado = relationship("Asesor", back_populates="sesiones")
    mensajes = relationship("Mensaje", back_populates="sesion", cascade="all, delete-orphan")
    ticket = relationship("TicketPendiente", back_populates="sesion", uselist=False, cascade="all, delete-orphan")


class Mensaje(Base):
    __tablename__ = 'mensajes'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sesion_id = Column(UUID(as_uuid=True), ForeignKey('sesiones.id', ondelete='CASCADE'), nullable=False)
    emisor = Column(String(20), nullable=False)
    contenido = Column(Text, nullable=False)
    similitud_rag = Column(Numeric(4, 3), nullable=True)
    url_fuente = Column(String(500), nullable=True)
    creado_en = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relación bidireccional
    sesion = relationship("Sesion", back_populates="mensajes")


class TicketPendiente(Base):
    __tablename__ = 'tickets_pendientes'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sesion_id = Column(UUID(as_uuid=True), ForeignKey('sesiones.id', ondelete='CASCADE'), unique=True, nullable=False)
    correo_contacto = Column(String(100), nullable=False)
    documento_identidad = Column(String(50), nullable=True)
    resumen_problema = Column(Text, nullable=False)
    estado = Column(String(20), default='abierto')
    asesor_resolucion_id = Column(UUID(as_uuid=True), ForeignKey('asesores.id', ondelete='SET NULL'), nullable=True)
    creado_en = Column(DateTime(timezone=True), default=datetime.utcnow)
    resuelto_en = Column(DateTime(timezone=True), nullable=True)

    # Relaciones bidireccionales
    sesion = relationship("Sesion", back_populates="ticket")
    asesor_resolucion = relationship("Asesor", back_populates="tickets_resueltos")