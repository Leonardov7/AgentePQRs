# ==============================================================================
# Cliente API Dify - Agente PQR
# Descripción: Maneja la comunicación HTTP asíncrona real con la nube de Dify.ai
# ==============================================================================

import os
import httpx
import logging
import re

logger = logging.getLogger(__name__)

DIFY_URL = os.getenv("DIFY_API_BASE_URL", "https://api.dify.ai/v1")
DIFY_KEY = os.getenv("DIFY_API_KEY", "")

# Diccionario global en memoria para persistencia de la conversación (Hilo conductor)
mapa_conversaciones_dify = {}

async def consultar_agente_dify(pregunta: str, identificador_usuario: str) -> dict:
    """
    Envía la pregunta del usuario a Dify, limpia las etiquetas de razonamiento 
    y extrae estrictamente la similitud reportada.
    """
    if not DIFY_KEY or "AQUI_PEGA" in DIFY_KEY:
        logger.error("DIFY_API_KEY no es válida o sigue siendo la de prueba.")
        return {"estado": "error"}

    headers = {
        "Authorization": f"Bearer {DIFY_KEY}",
        "Content-Type": "application/json"
    }
    
    # Recuperar el ID de conversación nativo de Dify si existe
    hilo_dify_actual = mapa_conversaciones_dify.get(identificador_usuario, "")
    
    payload = {
        "inputs": {},
        "query": pregunta,
        "response_mode": "blocking",
        "conversation_id": hilo_dify_actual,
        "user": identificador_usuario
    }

    logger.info(f">>> [AUDITORÍA DE RED] Destino HTTP: {DIFY_URL}/chat-messages")

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(f"{DIFY_URL}/chat-messages", json=payload, headers=headers)
            response.raise_for_status() 
            
            data = response.json()
            
            # Almacenar el identificador de memoria para el próximo turno
            if "conversation_id" in data and data["conversation_id"]:
                mapa_conversaciones_dify[identificador_usuario] = data["conversation_id"]

            texto_respuesta_cruda = data.get("answer", "Lo siento, no pude procesar el texto.")
            
            texto_limpio = re.sub(r'<think>.*?</think>', '', texto_respuesta_cruda, flags=re.DOTALL).strip()
            
            if not texto_limpio:
                texto_limpio = "Lo siento, hubo un error procesando la directriz cognitiva."

            retriever_resources = data.get("metadata", {}).get("retriever_resources", [])
            
            similitud_cruda = 0.0 
            url_fuente = "Sin Fuente Recuperada"
            
            if retriever_resources:
                mejor_fragmento = retriever_resources[0]
                similitud_cruda = mejor_fragmento.get("score", 0.0)
                url_fuente = mejor_fragmento.get("document_name", url_fuente)

            return {
                "estado": "exito",
                "respuesta": texto_limpio,
                "similitud_rag": similitud_cruda,
                "url_fuente": url_fuente
            }

    except httpx.HTTPStatusError as e:
        logger.error(f"Dify respondió con error HTTP: {e.response.status_code} - {e.response.text}")
        return {"estado": "error"}
    except Exception as e:
        logger.error(f"Fallo de conexión o timeout con la API de Dify: {str(e)}")
        return {"estado": "error"}