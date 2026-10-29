# ==============================================================================
# Controlador de Asesores (Endpoints Administrativos) - Agente PQR
# Descripción: Expone las rutas HTTP para el panel de administración (Dashboard)
# ==============================================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, update
from typing import List, Dict, Any
from uuid import UUID

from app.db.session import get_db
from app.models.models import Sesion, Mensaje, Asesor
from app.schemas.chat import MensajeResponse

router = APIRouter()

# ------------------------------------------------------------------------------
# 1. Obtener la Cola de Atención en Tiempo Real
# ------------------------------------------------------------------------------
@router.get("/sesiones/pendientes", response_model=List[Dict[str, Any]], status_code=status.HTTP_200_OK)
async def obtener_sesiones_en_cola(db: AsyncSession = Depends(get_db)):
    """
    Retorna todas las sesiones cuyo estado es 'en_cola'.
    Esta ruta será consultada por el frontend del Dashboard cada pocos segundos
    o alimentada por eventos SSE/WebSockets para pintar la bandeja de entrada del asesor.
    """
    # Consulta a base de datos ordenando por la fecha de actualización más antigua primero (FIFO)
    stmt = select(Sesion).where(Sesion.estado == "en_cola").order_by(Sesion.actualizado_en.asc())
    resultado = await db.execute(stmt)
    sesiones_pendientes = resultado.scalars().all()

    # Mapeo manual para devolver un esquema plano que sea fácil de renderizar en React
    lista_respuesta = []
    for sesion in sesiones_pendientes:
        lista_respuesta.append({
            "sesion_id": str(sesion.id),
            "estudiante_id": sesion.estudiante_id,
            "estado": sesion.estado,
            "creado_en": sesion.creado_en.isoformat(),
            "actualizado_en": sesion.actualizado_en.isoformat()
        })

    return lista_respuesta

# ------------------------------------------------------------------------------
# 2. Recuperar el Contexto (Historial de Conversación)
# ------------------------------------------------------------------------------
@router.get("/sesiones/{sesion_id}/historial", response_model=List[MensajeResponse], status_code=status.HTTP_200_OK)
async def obtener_historial_sesion(sesion_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Extrae todos los mensajes de una sesión específica.
    Permite al asesor humano leer la conversación previa entre el estudiante y el bot
    antes de intervenir, para no pedir al usuario que repita la información.
    """
    # Validación de existencia
    stmt_sesion = select(Sesion).where(Sesion.id == sesion_id)
    resultado_sesion = await db.execute(stmt_sesion)
    if not resultado_sesion.scalars().first():
        raise HTTPException(status_code=404, detail="La sesión solicitada no existe.")

    # Consulta del historial ordenado cronológicamente (los más antiguos primero)
    stmt_mensajes = select(Mensaje).where(Mensaje.sesion_id == sesion_id).order_by(Mensaje.creado_en.asc())
    resultado_mensajes = await db.execute(stmt_mensajes)
    mensajes_historial = resultado_mensajes.scalars().all()

    return mensajes_historial

# ------------------------------------------------------------------------------
# 3. Mutación de Estado de la Sesión (Cierre Administrativo)
# ------------------------------------------------------------------------------
@router.put("/sesiones/{sesion_id}/cerrar", status_code=status.HTTP_200_OK)
async def cerrar_sesion_pqr(sesion_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Permite a un asesor dar por finalizada la PQR, mutando el estado de la sesión a 'cerrada'.
    Esto la remueve de las colas de atención activa.
    """
    stmt = select(Sesion).where(Sesion.id == sesion_id)
    resultado = await db.execute(stmt)
    sesion = resultado.scalars().first()

    if not sesion:
        raise HTTPException(status_code=404, detail="La sesión no existe.")

    if sesion.estado == "cerrada":
        raise HTTPException(status_code=400, detail="La sesión ya se encuentra cerrada.")

    # Ejecutar la mutación de estado a nivel relacional
    stmt_update = update(Sesion).where(Sesion.id == sesion_id).values(estado="cerrada")
    await db.execute(stmt_update)
    
    # Inyectar un mensaje de sistema para trazabilidad
    mensaje_cierre = Mensaje(
        sesion_id=sesion.id,
        emisor="sistema",
        contenido="[RESOLUCIÓN] Esta petición ha sido marcada como resuelta y cerrada por un asesor humano."
    )
    db.add(mensaje_cierre)
    await db.commit()

    return {"status": "exito", "detalle": f"Sesión {sesion_id} clausurada correctamente."}