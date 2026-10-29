# ==============================================================================
# Controlador de Conocimiento (Endpoints Administrativos) - Agente PQR
# Descripción: Expone las rutas HTTP para la automatización del scraping 
# utilizando Playwright local, emulando la interfaz asíncrona de Firecrawl.
# ==============================================================================

from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from fastapi.responses import FileResponse
import logging
import os
import uuid
from datetime import datetime

from app.schemas.admin import PeticionScraping, RespuestaInicioScraping, RespuestaEstadoScraping
from app.services.scraper_local import rastrear_dominio

logger = logging.getLogger(__name__)
router = APIRouter()

DIRECTORIO_SALIDA = os.path.join(os.getcwd(), "datos_listos_dify")

# Diccionario en memoria para rastrear el progreso de los trabajos asíncronos sin usar base de datos
TRABAJOS_LOCALES = {}

async def tarea_scraping_segundo_plano(job_id: str, url: str, limite: int):
    """
    Se ejecuta en el background de FastAPI. Extrae las páginas, unifica el Markdown
    y actualiza el diccionario global para que el dashboard vea el progreso.
    """
    try:
        paginas_extraidas = await rastrear_dominio(url_base=url, limite_paginas=limite)
        
        if not paginas_extraidas:
            TRABAJOS_LOCALES[job_id]["status"] = "failed"
            TRABAJOS_LOCALES[job_id]["mensaje"] = "El crawler finalizó pero no extrajo ningún contenido válido."
            return

        if not os.path.exists(DIRECTORIO_SALIDA):
            os.makedirs(DIRECTORIO_SALIDA)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        nombre_archivo = f"conocimiento_local_{timestamp}.md"
        ruta_completa = os.path.join(DIRECTORIO_SALIDA, nombre_archivo)

        # Consolidación e Inyección de Índices Semánticos
        with open(ruta_completa, "w", encoding="utf-8") as archivo_salida:
            for indice, pagina in enumerate(paginas_extraidas, start=1):
                url_origen = pagina.get("url", "URL Desconocida")
                markdown_contenido = pagina.get("markdown", "")
                
                bloque_cabecera = (
                    f"\n\nINDICE_REGISTRO: {indice:04d}\n"
                    f"ORIGEN_URL: {url_origen}\n"
                    f"---\n\n"
                )
                archivo_salida.write(bloque_cabecera)
                archivo_salida.write(markdown_contenido)

        # Notificar al dashboard que finalizó con éxito
        TRABAJOS_LOCALES[job_id]["status"] = "completed"
        TRABAJOS_LOCALES[job_id]["total"] = len(paginas_extraidas)
        TRABAJOS_LOCALES[job_id]["archivo"] = nombre_archivo
        TRABAJOS_LOCALES[job_id]["mensaje"] = "Extracción y consolidación finalizada con éxito de forma local."

    except Exception as e:
        logger.error(f"Fallo crítico en tarea de scraping background: {str(e)}")
        TRABAJOS_LOCALES[job_id]["status"] = "error"
        TRABAJOS_LOCALES[job_id]["mensaje"] = str(e)


@router.post("/iniciar", response_model=RespuestaInicioScraping, status_code=status.HTTP_200_OK)
async def iniciar_extraccion_conocimiento(peticion: PeticionScraping, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    url_str = str(peticion.url_objetivo)
    
    # Inicializar el estado de la tarea
    TRABAJOS_LOCALES[job_id] = {
        "status": "scraping",
        "total": 0,
        "archivo": None,
        "mensaje": "Iniciando navegación con motor Chromium local..."
    }

    # Despachar la tarea pesada al pool asíncrono para liberar el hilo principal HTTP
    background_tasks.add_task(tarea_scraping_segundo_plano, job_id, url_str, peticion.limite_paginas)
    
    return RespuestaInicioScraping(
        estado="procesando",
        job_id=job_id,
        mensaje=f"Motor local inicializado para {url_str}."
    )

@router.get("/estado/{job_id}", response_model=RespuestaEstadoScraping, status_code=status.HTTP_200_OK)
async def verificar_estado_extraccion(job_id: str):
    trabajo = TRABAJOS_LOCALES.get(job_id)
    
    if not trabajo:
        raise HTTPException(status_code=404, detail="El ID de trabajo no existe o caducó en memoria.")

    estado_actual = trabajo.get("status")
    
    if estado_actual in ["error", "failed"]:
        raise HTTPException(status_code=500, detail=trabajo.get("mensaje", "Fallo desconocido."))

    return RespuestaEstadoScraping(
        estado_trabajo="completed" if estado_actual == "completed" else "scraping",
        total_paginas=trabajo.get("total", 0),
        mensaje=trabajo.get("mensaje", "Extrayendo..."),
        archivo_generado=trabajo.get("archivo") if estado_actual == "completed" else None
    )

@router.delete("/cancelar/{job_id}", status_code=status.HTTP_200_OK)
async def cancelar_extraccion(job_id: str):
    # En un hilo background simple es complejo matar el subproceso, pero podemos
    # marcarlo como cancelado para que el dashboard reaccione.
    if job_id in TRABAJOS_LOCALES:
        TRABAJOS_LOCALES[job_id]["status"] = "cancelled"
        TRABAJOS_LOCALES[job_id]["mensaje"] = "Operación abortada por el usuario."
        return {"estado": "cancelado", "mensaje": f"Trabajo {job_id} marcado para abortar."}
    
    raise HTTPException(status_code=404, detail="El ID de trabajo no existe.")

@router.get("/descargar/{nombre_archivo}", tags=["Administración de Conocimiento"])
async def descargar_archivo_conocimiento(nombre_archivo: str):
    ruta_completa = os.path.join(DIRECTORIO_SALIDA, nombre_archivo)
    if not os.path.exists(ruta_completa):
        raise HTTPException(status_code=404, detail="El archivo solicitado no existe en el servidor.")
        
    return FileResponse(path=ruta_completa, filename=nombre_archivo, media_type='text/markdown')