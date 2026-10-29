# ==============================================================================
# Cliente API Firecrawl - Módulo de Administración
# Descripción: Maneja la comunicación HTTP asíncrona con Firecrawl para el
# rastreo y extracción de contenido web optimizado para LLMs.
# ==============================================================================

import os
import httpx
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

FIRECRAWL_API_URL = "https://api.firecrawl.dev/v1"
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")

async def iniciar_trabajo_crawl(url: str, limite: int) -> Dict[str, Any]:
    """
    Envía una petición POST a Firecrawl para iniciar un trabajo de rastreo profundo.
    Retorna el Job ID para realizar el seguimiento asíncrono.
    """
    if not FIRECRAWL_API_KEY:
        logger.error("FIRECRAWL_API_KEY no está configurada en las variables de entorno.")
        return {"success": False, "error": "API Key no configurada."}

    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "url": url,
        "limit": limite,
        "scrapeOptions": {
            "formats": ["markdown"],
            "onlyMainContent": True
        }
    }

    logger.info(f">>> [FIRECRAWL] Iniciando rastreo en URL: {url} con límite de {limite} páginas.")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{FIRECRAWL_API_URL}/crawl", json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"Firecrawl respondió con error HTTP: {e.response.status_code} - {e.response.text}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Fallo de conexión con la API de Firecrawl: {str(e)}")
        return {"success": False, "error": str(e)}

async def consultar_estado_crawl(job_id: str) -> Dict[str, Any]:
    """
    Consulta el estado de un trabajo de rastreo previamente iniciado.
    Si el estado es 'completed', el JSON de respuesta contendrá el arreglo 'data' con los markdowns.
    """
    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(f"{FIRECRAWL_API_URL}/crawl/{job_id}", headers=headers)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Fallo al consultar el estado del trabajo {job_id} en Firecrawl: {str(e)}")
        return {"status": "error", "error": str(e)}

async def cancelar_trabajo_crawl(job_id: str) -> Dict[str, Any]:
    """
    Envía una petición DELETE para abortar un trabajo de rastreo en curso en los servidores de Firecrawl.
    """
    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(f"{FIRECRAWL_API_URL}/crawl/{job_id}", headers=headers)
            response.raise_for_status()
            return {"success": True, "data": response.json()}
    except Exception as e:
        logger.error(f"Fallo al intentar cancelar el trabajo {job_id} en Firecrawl: {str(e)}")
        return {"success": False, "error": str(e)}