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
import uuid

from app.db.session import get_db, AsyncSessionLocal
from app.models.models import Sesion, Mensaje
from app.schemas.chat import PeticionUsuario, InicioSesionRequest
from app.services.dify_client import consultar_agente_dify
from app.services.routing_engine import evaluar_y_enrutar_respuesta, _escalar_a_humano
from app.websockets.manager import manager

logger = logging.getLogger(__name__)
router = APIRouter()

# ------------------------------------------------------------------------------
# 1. Endpoints REST (Usuario -> Dify / IA)
# ------------------------------------------------------------------------------

@router.post("/iniciar", response_model=dict, status_code=status.HTTP_201_CREATED)
async def iniciar_sesion_pqr(datos: InicioSesionRequest, db: AsyncSession = Depends(get_db)):
    """
    Inicializa una nueva sesión de chat PQR capturando los datos formales del usuario.
    Retorna el sesion_id (UUID) que el widget usará para enviar los mensajes.
    """
    nuevo_id = uuid.uuid4()
    
    # Registramos el perfil completo del usuario en la base de datos desde el inicio
    nueva_sesion = Sesion(
        id=nuevo_id,
        estudiante_id=datos.documento,
        nombre_usuario=datos.nombre,
        documento_identidad=datos.documento,
        correo=datos.correo,
        celular=datos.celular,
        sede=datos.sede,
        tipo_usuario=datos.tipo_usuario,
        politicas_aceptadas=datos.politicas_aceptadas,
        estado="atencion_bot"
    )
    
    db.add(nueva_sesion)
    await db.commit()
    
    logger.info(f"Nueva sesión PQR inicializada: {nuevo_id} para {datos.nombre} ({datos.tipo_usuario})")
    
    return {
        "estado": "exito",
        "sesion_id": str(nuevo_id),
        "mensaje": "Sesión iniciada correctamente."
    }

@router.post("/enviar", response_model=dict, status_code=status.HTTP_200_OK)
async def procesar_mensaje_usuario(peticion: PeticionUsuario, db: AsyncSession = Depends(get_db)):
    """
    Recibe un mensaje del usuario, lo guarda, consulta al LLM y evalúa el umbral RAG.
    """
    logger.info(f"Recibiendo petición REST para sesión: {peticion.sesion_id}")
    
    stmt = select(Sesion).where(Sesion.id == peticion.sesion_id)
    resultado = await db.execute(stmt)
    sesion = resultado.scalars().first()

    # Como el chat ahora requiere formulario, si la sesión no existe, rechazamos la petición
    if not sesion:
        raise HTTPException(status_code=403, detail="Sesión no válida o caducada. Por favor, reinicia el chat.")

    if sesion.estado in ["cerrada", "ticket_asincrono"]:
        raise HTTPException(status_code=400, detail="El caso ya ha sido gestionado o cerrado.")

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
            "notificacion": "Un asesor institucional ya está atendiendo tu caso. Por favor, usa la ventana de chat en vivo."
        }
    
    # ---------------------------------------------------------
    # INTERCEPTOR DE BOTONES DE ACCIÓN (Evita consultar a Dify)
    # ---------------------------------------------------------
    if peticion.texto_pregunta == "/escalar_humano":
        await _escalar_a_humano(db, sesion.id)
        return {
            "sesion_id": str(sesion.id),
            "estado_actual": "en_cola",
            "respuesta_sistema": "Te he transferido con nuestro equipo de atención institucional. Un asesor se conectará contigo en un momento."
        }
    
    if peticion.texto_pregunta == "/continuar":
        return {
            "sesion_id": str(sesion.id),
            "estado_actual": "atencion_bot",
            "respuesta_sistema": "¡Entendido! Cuéntame, ¿cómo más te puedo ayudar hoy?"
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
# 2. Endpoint WebSocket Unificado (Usuario <-> IA / Humano)
# ------------------------------------------------------------------------------
@router.websocket("/ws/{sesion_id}/{rol}")
async def websocket_chat_humano(websocket: WebSocket, sesion_id: str, rol: str):
    await manager.connect(websocket, sesion_id, rol)
    
    try:
        while True:
            datos_recibidos = await websocket.receive_text()
            payload = json.loads(datos_recibidos)
            texto_mensaje = payload.get("contenido", "")
            
            if not texto_mensaje.strip():
                continue

            async with AsyncSessionLocal() as db:
                nuevo_mensaje = Mensaje(
                    sesion_id=sesion_id,
                    emisor=rol, 
                    contenido=texto_mensaje
                )
                db.add(nuevo_mensaje)
                await db.commit()

                stmt = select(Sesion).where(Sesion.id == sesion_id)
                resultado = await db.execute(stmt)
                sesion = resultado.scalars().first()

                if not sesion:
                     continue

                if rol == "asesor":
                    if sesion.estado == 'en_cola':
                         stmt_update = update(Sesion).where(Sesion.id == sesion_id).values(estado="atencion_humana")
                         await db.execute(stmt_update)
                         await db.commit()
                    
                    mensaje_a_emitir = {
                        "tipo": "nuevo_mensaje",
                        "emisor": "asesor",
                        "contenido": texto_mensaje
                    }
                    await manager.broadcast_to_session(sesion_id, mensaje_a_emitir, sender_rol=rol)
                
                elif rol == "usuario":
                    if sesion.estado == "atencion_bot":
                         if texto_mensaje == "/escalar_humano":
                              await _escalar_a_humano(db, sesion.id)
                              respuesta_final = {
                                  "tipo": "nuevo_mensaje",
                                  "emisor": "sistema",
                                  "contenido": "Te he puesto en la cola de atención. Un asesor humano se conectará contigo en breve."
                              }
                              await manager.send_personal_message(respuesta_final, websocket)
                              continue
                         
                         if texto_mensaje == "/continuar":
                              respuesta_final = {
                                  "tipo": "nuevo_mensaje",
                                  "emisor": "bot",
                                  "contenido": "¡Entendido! Puedes escribirme tu pregunta de otra forma e intentaré buscarla nuevamente."
                              }
                              await manager.send_personal_message(respuesta_final, websocket)
                              continue

                         # 1. Intentamos bypass de intención manual
                         resultado_enrutamiento = await evaluar_y_enrutar_respuesta(
                             db=db, 
                             sesion_id=sesion.id, 
                             peticion_usuario=texto_mensaje
                         )
                         
                         # 2. Si no hay Bypass manual, se dispara Dify
                         if not resultado_enrutamiento or "accion" not in resultado_enrutamiento:
                             logger.info(f"Enviando consulta a Dify Cloud para sesión: {sesion.id}")
                             respuesta_bruta_dify = await consultar_agente_dify(
                                 pregunta=texto_mensaje,
                                 identificador_usuario=str(sesion.id)
                             )

                             # Y volvemos a enrutar con el resultado crudo de Dify
                             resultado_enrutamiento = await evaluar_y_enrutar_respuesta(
                                 db=db, 
                                 sesion_id=sesion.id, 
                                 respuesta_dify=respuesta_bruta_dify
                             )

                         # PROTECCIÓN EXTRA: Si el motor devuelve None, forzamos un fallback seguro
                         if not resultado_enrutamiento:
                             resultado_enrutamiento = {
                                 "accion": "escalado",
                                 "mensaje_publico": "Error interno al procesar. Te he transferido con un asesor humano."
                             }

                         # 3. Empaquetar y enviar por socket
                         respuesta_final = {
                             "tipo": "nuevo_mensaje",
                             "emisor": "bot" if resultado_enrutamiento.get("accion") != "escalado" else "sistema",
                             "contenido": resultado_enrutamiento.get("mensaje_publico", "Error procesando tu petición."),
                         }
                         
                         if "opciones" in resultado_enrutamiento:
                             respuesta_final["opciones"] = resultado_enrutamiento["opciones"]

                         await manager.send_personal_message(respuesta_final, websocket)

                    elif sesion.estado in ["en_cola", "atencion_humana"]:
                         mensaje_a_emitir = {
                             "tipo": "nuevo_mensaje",
                             "emisor": "usuario",
                             "contenido": texto_mensaje
                         }
                         await manager.broadcast_to_session(sesion_id, mensaje_a_emitir, sender_rol=rol)
                    else:
                         mensaje_rechazo = {
                             "tipo": "nuevo_mensaje",
                             "emisor": "sistema",
                             "contenido": "Esta sesión ya no se encuentra activa."
                         }
                         await manager.send_personal_message(mensaje_rechazo, websocket)

    except WebSocketDisconnect:
        manager.disconnect(sesion_id, rol)
        mensaje_desconexion = {
            "tipo": "alerta_sistema",
            "emisor": "sistema",
            "contenido": "La contraparte se ha desconectado momentáneamente del chat." if rol == 'asesor' else "El usuario ha cerrado la ventana de chat."
        }
        await manager.broadcast_to_session(sesion_id, mensaje_desconexion)