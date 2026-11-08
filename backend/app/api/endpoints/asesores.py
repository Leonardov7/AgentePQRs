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
from datetime import datetime

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
    stmt = select(Sesion).where(Sesion.estado == "en_cola").order_by(Sesion.actualizado_en.asc())
    resultado = await db.execute(stmt)
    sesiones_pendientes = resultado.scalars().all()

    lista_respuesta = []
    for sesion in sesiones_pendientes:
        lista_respuesta.append({
            "sesion_id": str(sesion.id),
            "estudiante_id": sesion.estudiante_id,
            "nombre_usuario": sesion.nombre_usuario,
            "documento_identidad": sesion.documento_identidad,
            "correo": sesion.correo,
            "celular": sesion.celular,
            "sede": sesion.sede,
            "tipo_usuario": sesion.tipo_usuario,
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
    stmt_sesion = select(Sesion).where(Sesion.id == sesion_id)
    resultado_sesion = await db.execute(stmt_sesion)
    if not resultado_sesion.scalars().first():
        raise HTTPException(status_code=404, detail="La sesión solicitada no existe.")

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

    stmt_update = update(Sesion).where(Sesion.id == sesion_id).values(estado="cerrada")
    await db.execute(stmt_update)
    
    mensaje_cierre = Mensaje(
        sesion_id=sesion.id,
        emisor="sistema",
        contenido="[RESOLUCIÓN] Esta petición ha sido marcada como resuelta y cerrada por un asesor humano."
    )
    db.add(mensaje_cierre)
    await db.commit()

    return {"status": "exito", "detalle": f"Sesión {sesion_id} clausurada correctamente."}

# ------------------------------------------------------------------------------
# 4. Módulo de Estadísticas Directivas (Dashboard KPI)
# ------------------------------------------------------------------------------
from sqlalchemy import func, and_
from pydantic import BaseModel
from typing import Optional

class EstadisticasResponse(BaseModel):
    sesiones_globales: int
    total_preguntas: int
    resueltas_ia: int
    escaladas_humano: int
    tasa_contencion: float

@router.get("/estadisticas", response_model=EstadisticasResponse, status_code=status.HTTP_200_OK)
async def obtener_estadisticas_directivas(
    fecha_inicio: Optional[str] = None, 
    fecha_fin: Optional[str] = None, 
    db: AsyncSession = Depends(get_db)
):
    """
    Calcula los KPI en tiempo real desde la base de datos PostgreSQL para el panel directivo.
    Soporta filtrado opcional por rango de fechas ISO (YYYY-MM-DD).
    """
    filtros_sesion = []
    filtros_mensaje = [Mensaje.emisor == "usuario"]

    if fecha_inicio and fecha_fin:
        try:
            inicio_dt = datetime.strptime(f"{fecha_inicio} 00:00:00", "%Y-%m-%d %H:%M:%S")
            fin_dt = datetime.strptime(f"{fecha_fin} 23:59:59", "%Y-%m-%d %H:%M:%S")
            filtros_sesion.append(Sesion.creado_en.between(inicio_dt, fin_dt))
            filtros_mensaje.append(Mensaje.creado_en.between(inicio_dt, fin_dt))
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD.")

    stmt_sesiones = select(func.count(Sesion.id)).where(and_(*filtros_sesion))
    res_sesiones = await db.execute(stmt_sesiones)
    total_sesiones = res_sesiones.scalar() or 0

    stmt_preguntas = select(func.count(Mensaje.id)).where(and_(*filtros_mensaje))
    res_preguntas = await db.execute(stmt_preguntas)
    total_preguntas = res_preguntas.scalar() or 0

    filtros_escaladas = filtros_sesion.copy()
    filtros_escaladas.append(Sesion.estado.in_(["en_cola", "atencion_humana"]))
    stmt_escaladas = select(func.count(Sesion.id)).where(and_(*filtros_escaladas))
    res_escaladas = await db.execute(stmt_escaladas)
    escaladas = res_escaladas.scalar() or 0

    resueltas_ia = total_sesiones - escaladas
    if resueltas_ia < 0: 
        resueltas_ia = 0

    tasa = 0.0
    if total_sesiones > 0:
        tasa = round((resueltas_ia / total_sesiones) * 100, 1)

    return {
        "sesiones_globales": total_sesiones,
        "total_preguntas": total_preguntas,
        "resueltas_ia": resueltas_ia,
        "escaladas_humano": escaladas,
        "tasa_contencion": tasa
    }

# ------------------------------------------------------------------------------
# 5. Módulo de Auditoría (Historial General de Sesiones)
# ------------------------------------------------------------------------------
@router.get("/historial-completo", status_code=status.HTTP_200_OK)
async def obtener_historial_general(db: AsyncSession = Depends(get_db)):
    """
    Recupera TODAS las sesiones registradas en el sistema (sin importar su estado).
    Incluye datos de perfil, tipología de cierre y tiempos para la tabla del Dashboard.
    """
    stmt = select(Sesion).order_by(Sesion.creado_en.desc())
    resultado = await db.execute(stmt)
    sesiones = resultado.scalars().all()

    lista_respuesta = []
    for sesion in sesiones:
        # Contar cuántos mensajes humanos hubo para métricas rápidas
        lista_respuesta.append({
            "id": str(sesion.id),
            "nombre": sesion.nombre_usuario or "Anónimo",
            "documento": sesion.documento_identidad or "N/A",
            "correo": sesion.correo or "N/A",
            "sede": sesion.sede or "N/A",
            "rol": sesion.tipo_usuario or "N/A",
            "estado": sesion.estado,
            "creado": sesion.creado_en.strftime("%Y-%m-%d %H:%M"),
            "actualizado": sesion.actualizado_en.strftime("%Y-%m-%d %H:%M")
        })

    return lista_respuesta