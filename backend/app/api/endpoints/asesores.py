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
from pydantic import BaseModel
import re

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
class CierreSesionRequest(BaseModel):
    tipologia: str
    nota_interna: str

@router.put("/sesiones/{sesion_id}/cerrar", status_code=status.HTTP_200_OK)
async def cerrar_sesion_pqr(sesion_id: UUID, datos: CierreSesionRequest, db: AsyncSession = Depends(get_db)):
    """
    Permite a un asesor dar por finalizada la PQR, mutando el estado de la sesión a 'cerrada'.
    Guarda la tipología y nota interna en el historial de la sesión para fines analíticos.
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
    
    # Se añade la tipología directamente al mensaje de sistema con un separador robusto "||"
    mensaje_cierre = Mensaje(
        sesion_id=sesion.id,
        emisor="sistema",
        contenido=f"[RESOLUCIÓN] Caso cerrado por asesor. || TIPOLOGIA: {datos.tipologia.strip().lower()} || Notas adicionales: {datos.nota_interna}"
    )
    db.add(mensaje_cierre)
    await db.commit()

    return {"status": "exito", "detalle": f"Sesión {sesion_id} clausurada correctamente."}

# ------------------------------------------------------------------------------
# 4. Módulo de Estadísticas Directivas (Dashboard KPI y BI)
# ------------------------------------------------------------------------------
from sqlalchemy import func, and_
from typing import Optional

class EstadisticasResponse(BaseModel):
    sesiones_globales: int
    total_preguntas: int
    resueltas_ia: int
    escaladas_humano: int
    tasa_contencion: float
    datos_crudos: List[Dict[str, Any]]
    distribucion_tipologia_sede: List[Dict[str, Any]]

@router.get("/estadisticas", response_model=EstadisticasResponse, status_code=status.HTTP_200_OK)
async def obtener_estadisticas_directivas(
    fecha_inicio: Optional[str] = None, 
    fecha_fin: Optional[str] = None, 
    db: AsyncSession = Depends(get_db)
):
    """
    Retorna la sábana de datos crudos y cruces analíticos pre-procesados para el BI Frontend.
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

    # 1. KPIs Globales
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
    resueltas_ia = max(resueltas_ia, 0)
    tasa = round((resueltas_ia / total_sesiones) * 100, 1) if total_sesiones > 0 else 0.0

    # 2. Datos Crudos Básicos
    stmt_crudos = select(Sesion).where(and_(*filtros_sesion)).order_by(Sesion.creado_en.desc())
    sesiones_crudas = (await db.execute(stmt_crudos)).scalars().all()
    
    datos_crudos = []
    
    # 3. Extracción Analítica de Tipología
    for s in sesiones_crudas:
        tipologia_detectada = "No Clasificada"
        
        # Si la sesión está cerrada, buscamos su mensaje de resolución
        if s.estado == "cerrada":
             stmt_cierre = select(Mensaje.contenido).where(and_(Mensaje.sesion_id == s.id, Mensaje.emisor == "sistema", Mensaje.contenido.like("[RESOLUCIÓN]%")))
             res_cierre = await db.execute(stmt_cierre)
             mensaje_resolucion = res_cierre.scalar()
             
             if mensaje_resolucion:
                 # 1. Búsqueda por el nuevo formato estructurado "|| TIPOLOGIA: valor ||"
                 match_nuevo = re.search(r"\|\|\s*TIPOLOGIA:\s*([^|]+)", mensaje_resolucion)
                 if match_nuevo:
                     tipologia_detectada = match_nuevo.group(1).strip().capitalize()
                 else:
                     # 2. Búsqueda de respaldo (Fallback) para tickets antiguos usando la lógica original
                     # Extrae palabras clave directamente del texto
                     texto_min = mensaje_resolucion.lower()
                     if "peticion" in texto_min or "petición" in texto_min: tipologia_detectada = "Peticion"
                     elif "queja" in texto_min: tipologia_detectada = "Queja"
                     elif "reclamo" in texto_min: tipologia_detectada = "Reclamo"
                     elif "sugerencia" in texto_min: tipologia_detectada = "Sugerencia"
                     elif "felicitacion" in texto_min or "felicitación" in texto_min: tipologia_detectada = "Felicitacion"

        datos_crudos.append({
            "ID_Caso": str(s.id),
            "Fecha_Ingreso": s.creado_en.strftime("%Y-%m-%d %H:%M:%S") if s.creado_en else "",
            "Fecha_Actualizacion": s.actualizado_en.strftime("%Y-%m-%d %H:%M:%S") if s.actualizado_en else "",
            "Nombre_Usuario": s.nombre_usuario or "Anónimo",
            "Documento": s.documento_identidad or "N/A",
            "Contacto_Email": s.correo or "N/A",
            "Contacto_Telefono": s.celular or "N/A",
            "Sede": s.sede or "No Definida",
            "Perfil": s.tipo_usuario or "No Definido",
            "Estado_Final": s.estado.replace("_", " ").title(),
            "Tipologia_PQRSD": tipologia_detectada
        })

    # 4. Agrupación Preparada para Gráfico de Barras Apiladas (Recharts)
    mapa_sedes = {}
    for d in datos_crudos:
        if d["Estado_Final"] == "Cerrada" and d["Tipologia_PQRSD"] != "No Clasificada":
            sede = d["Sede"]
            tipo = d["Tipologia_PQRSD"]
            
            # Normalizamos los tipos para que coincidan exactamente con las llaves que espera Recharts
            if tipo == "Petición": tipo = "Peticion"
            if tipo == "Felicitación": tipo = "Felicitacion"
            
            if sede not in mapa_sedes:
                mapa_sedes[sede] = {"name": sede}
            
            mapa_sedes[sede][tipo] = mapa_sedes[sede].get(tipo, 0) + 1

    distribucion_tipologia_sede = list(mapa_sedes.values())

    return {
        "sesiones_globales": total_sesiones,
        "total_preguntas": total_preguntas,
        "resueltas_ia": resueltas_ia,
        "escaladas_humano": escaladas,
        "tasa_contencion": tasa,
        "datos_crudos": datos_crudos,
        "distribucion_tipologia_sede": distribucion_tipologia_sede
    }

# ------------------------------------------------------------------------------
# 5. Módulo de Auditoría (Historial General de Sesiones)
# ------------------------------------------------------------------------------
@router.get("/historial-completo", status_code=status.HTTP_200_OK)
async def obtener_historial_general(db: AsyncSession = Depends(get_db)):
    """
    Recupera TODAS las sesiones registradas en el sistema (sin importar su estado).
    """
    stmt = select(Sesion).order_by(Sesion.creado_en.desc())
    resultado = await db.execute(stmt)
    sesiones = resultado.scalars().all()

    lista_respuesta = []
    for sesion in sesiones:
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