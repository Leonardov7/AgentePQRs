# ==============================================================================
# Controlador de Chat (Endpoints REST y WebSockets) - Agente PQR
# Descripción: Expone las rutas HTTP para IA y las rutas WS para humanos
# ==============================================================================

from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
import json
import logging

from app.db.session import get_db, AsyncSessionLocal
from app.models.models import Sesion, Mensaje
from app.schemas.chat import PeticionUsuario
from app.services.dify_client import consultar_agente_dify
from app.services.routing_engine import evaluar_y_enrutar_respuesta, _escalar_a_humano
from app.websockets.manager import manager


logger = logging.getLogger(__name__)
router = APIRouter()

# ------------------------------------------------------------------------------
# 1. Endpoint REST Clásico (Usuario -> Dify / IA)
# ------------------------------------------------------------------------------
@router.post("/enviar", response_model=dict, status_code=status.HTTP_200_OK)
async def procesar_mensaje_usuario(peticion: PeticionUsuario, db: AsyncSession = Depends(get_db)):
    """
    Recibe un mensaje del usuario, lo guarda, consulta al LLM y evalúa el umbral RAG.
    """
    logger.info(f"Recibiendo petición REST para sesión: {peticion.sesion_id}")
    
    stmt = select(Sesion).where(Sesion.id == peticion.sesion_id)
    resultado = await db.execute(stmt)
    sesion = resultado.scalars().first()

    # Auto-crear la sesión en la primera interacción
    if not sesion:
        sesion = Sesion(
            id=peticion.sesion_id,
            estudiante_id="usuario_anonimo",
            estado="atencion_bot"
        )
        db.add(sesion)
        await db.commit()
        await db.refresh(sesion)

    if sesion.estado in ["cerrada", "ticket_asincrono"]:
        raise HTTPException(status_code=400, detail="La sesión ya ha sido clausurada o diferida.")

    mensaje_usuario = Mensaje(
        sesion_id=sesion.id,
        emisor="usuario",
        contenido=peticion.texto_pregunta
    )
    db.add(mensaje_usuario)
    await db.commit() 

    # Si la sesión ya fue escalada, el usuario debería usar WebSocket, no REST.
    if sesion.estado in ["en_cola", "atencion_humana"]:
        logger.info(f"Sesión {sesion.id} ignorada por IA. Ya está asignada a humano.")
        return {
            "estado_sesion": sesion.estado,
            "notificacion": "Tu sesión está asignada a un humano. Por favor, usa la conexión en tiempo real."
        }
    
    # ---------------------------------------------------------
    # INTERCEPTOR DE BOTONES DE ACCIÓN (Evita consultar a Dify)
    # ---------------------------------------------------------
    if peticion.texto_pregunta == "/escalar_humano":
        await _escalar_a_humano(db, sesion.id)
        return {
            "sesion_id": str(sesion.id),
            "estado_actual": "en_cola",
            "respuesta_sistema": "Te he puesto en la cola de atención. Un asesor humano se conectará contigo en breve."
        }
    
    if peticion.texto_pregunta == "/continuar":
        return {
            "sesion_id": str(sesion.id),
            "estado_actual": "atencion_bot",
            "respuesta_sistema": "¡Entendido! Puedes escribirme tu pregunta de otra forma e intentaré buscarla nuevamente."
        }
    # ---------------------------------------------------------

    logger.info(f"Enviando consulta a Dify Cloud para sesión: {sesion.id}")
    respuesta_bruta_dify = await consultar_agente_dify(
        pregunta=peticion.texto_pregunta,
        identificador_usuario=str(sesion.id)
    )

    resultado_enrutamiento = await evaluar_y_enrutar_respuesta(
        db=db, 
        sesion_id=sesion.id, 
        respuesta_dify=respuesta_bruta_dify
    )

    # Reestructuración de la respuesta final para admitir el paso de "opciones" (botones) al frontend
    respuesta_final = {
        "sesion_id": str(sesion.id),
        "estado_actual": "en_cola" if resultado_enrutamiento["accion"] == "escalado" else "atencion_bot",
        "respuesta_sistema": resultado_enrutamiento["mensaje_publico"],
        "metadatos": resultado_enrutamiento.get("metadatos", {})
    }

    # Inyección dinámica de los botones interactivos si el enrutador los generó
    if "opciones" in resultado_enrutamiento:
        respuesta_final["opciones"] = resultado_enrutamiento["opciones"]

    return respuesta_final

# ------------------------------------------------------------------------------
# 2. Endpoint WebSocket (Usuario <-> Asesor Humano)
# ------------------------------------------------------------------------------
@router.websocket("/ws/{sesion_id}/{rol}")
async def websocket_chat_humano(websocket: WebSocket, sesion_id: str, rol: str):
    """
    Establece un túnel bidireccional cuando la IA ya no puede responder.
    rol: 'usuario' o 'asesor'
    """
    await manager.connect(websocket, sesion_id, rol)
    
    try:
        while True:
            # Espera indefinidamente a que el cliente (React) envíe un texto
            datos_recibidos = await websocket.receive_text()
            payload = json.loads(datos_recibidos)
            
            # Extraemos el mensaje
            texto_mensaje = payload.get("contenido", "")
            
            # Validación básica de seguridad
            if not texto_mensaje.strip():
                continue

            # Persistencia en base de datos
            async with AsyncSessionLocal() as db:
                nuevo_mensaje = Mensaje(
                    sesion_id=sesion_id,
                    emisor=rol, 
                    contenido=texto_mensaje
                )
                db.add(nuevo_mensaje)
                
                if rol == "asesor":
                    stmt = update(Sesion).where(
                        Sesion.id == sesion_id, 
                        Sesion.estado == 'en_cola'
                    ).values(estado="atencion_humana")
                    await db.execute(stmt)
                
                await db.commit()

            # Transmisión en tiempo real al otro participante
            mensaje_a_emitir = {
                "tipo": "nuevo_mensaje",
                "emisor": rol,
                "contenido": texto_mensaje
            }
            # INYECCIÓN DEL FILTRO: Se pasa el parámetro sender_rol para suprimir el eco.
            await manager.broadcast_to_session(sesion_id, mensaje_a_emitir, sender_rol=rol)

    except WebSocketDisconnect:
        # El cliente cerró la pestaña o perdió conexión
        manager.disconnect(sesion_id, rol)
        
        # Notificar a la contraparte que el usuario se desconectó temporalmente
        mensaje_desconexion = {
            "tipo": "alerta_sistema",
            "emisor": "sistema",
            "contenido": f"El {rol} se ha desconectado del chat."
        }
        # Para alertas de sistema, sí se transmite a todos los que queden (no hay sender_rol)
        await manager.broadcast_to_session(sesion_id, mensaje_desconexion)