# ==============================================================================
# Cliente API Dify - Agente PQR
# Descripción: Maneja la comunicación HTTP asíncrona real con la nube de Dify.ai
# ==============================================================================

import os
import httpx
import logging
import re
import json

logger = logging.getLogger(__name__)

DIFY_URL = os.getenv("DIFY_API_BASE_URL", "https://api.dify.ai/v1")
DIFY_KEY = os.getenv("DIFY_API_KEY", "")

# Memoria en tiempo de ejecución para preservar el hilo conversacional (sesion_id -> dify_conversation_id)
_mapa_conversaciones_dify = {}

async def consultar_agente_dify(pregunta: str, identificador_usuario: str) -> dict:
    """
    Envía la pregunta del usuario a Dify manteniendo el conversation_id activo,
    limpia las etiquetas de razonamiento y extrae estrictamente la similitud reportada.
    """
    if not DIFY_KEY or "AQUI_PEGA" in DIFY_KEY:
        logger.error("DIFY_API_KEY no es válida o sigue siendo la de prueba.")
        return {"estado": "error", "respuesta": "Error interno de configuración (API Key)."}

    headers = {
        "Authorization": f"Bearer {DIFY_KEY}",
        "Content-Type": "application/json"
    }
    
    # Recuperar el ID de conversación de Dify si esta sesión ya había hablado antes
    conversacion_dify_actual = _mapa_conversaciones_dify.get(identificador_usuario, "")

    payload = {
        "inputs": {},
        "query": pregunta,
        "response_mode": "blocking",
        "conversation_id": conversacion_dify_actual,
        "user": identificador_usuario
    }

    logger.info(f">>> [AUDITORÍA DE RED] Destino HTTP: {DIFY_URL}/chat-messages | Hilo Dify: '{conversacion_dify_actual or 'NUEVO'}'")

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(f"{DIFY_URL}/chat-messages", json=payload, headers=headers)
            
            # Si el conversation_id expiró o cambió de App en Dify, reintentar como hilo nuevo
            if response.status_code == 404 and conversacion_dify_actual:
                logger.warning(">>> [HILO DIFY] Conversación previa no encontrada en Dify. Reiniciando hilo...")
                _mapa_conversaciones_dify.pop(identificador_usuario, None)
                payload["conversation_id"] = ""
                response = await client.post(f"{DIFY_URL}/chat-messages", json=payload, headers=headers)

            response.raise_for_status() 
            
            data = response.json()
            
            # Guardar el conversation_id devuelto por Dify para mantener el hilo en las siguientes preguntas
            nuevo_conv_id = data.get("conversation_id")
            if nuevo_conv_id:
                _mapa_conversaciones_dify[identificador_usuario] = nuevo_conv_id

            texto_respuesta_cruda = data.get("answer", "Lo siento, no pude procesar el texto.")
            
            texto_limpio = re.sub(r'<think>.*?</think>', '', texto_respuesta_cruda, flags=re.DOTALL).strip()
            
            if not texto_limpio:
                texto_limpio = "Lo siento, hubo un error procesando la directriz cognitiva."

            metadata = data.get("metadata", {})
            retriever_resources = metadata.get("retriever_resources", [])
            
            logger.warning(f">>> [AUDITORÍA METADATA DIFY] Recursos recuperados ({len(retriever_resources)}): {json.dumps(retriever_resources, ensure_ascii=False)}")
            
            # Si Dify no envía documentos, la similitud es estrictamente cero.
            similitud_cruda = 0.0 
            url_fuente = "Sin Fuente Recuperada"
            
            if retriever_resources and len(retriever_resources) > 0:
                recursos_ordenados = sorted(
                    retriever_resources, 
                    key=lambda x: float(x.get("score") or 0.0), 
                    reverse=True
                )
                mejor_fragmento = recursos_ordenados[0]
                similitud_cruda = float(mejor_fragmento.get("score") or 0.0)
                url_fuente = mejor_fragmento.get("document_name") or mejor_fragmento.get("dataset_name") or url_fuente

            return {
                "estado": "exito",
                "respuesta": texto_limpio,
                "similitud_rag": similitud_cruda,
                "url_fuente": url_fuente
            }

    except httpx.HTTPStatusError as e:
        logger.error(f"Dify respondió con error HTTP: {e.response.status_code} - {e.response.text}")
        return {"estado": "error", "respuesta": "El servidor de inteligencia artificial está temporalmente fuera de servicio."}
    except Exception as e:
        logger.error(f"Fallo de conexión o timeout con la API de Dify: {str(e)}")
        return {"estado": "error", "respuesta": "Tiempo de espera agotado al conectar con el motor cognitivo."}