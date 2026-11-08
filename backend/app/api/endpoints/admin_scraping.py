# ==============================================================================
# Controlador de Extracción de Conocimiento (Scraping)
# Descripción: Expone las rutas HTTP para gestionar el scraping, consultar 
# estado, cancelar procesos y descargar bases de datos procesadas con ML.
# ==============================================================================

import os
import uuid
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import logging

from app.services.scraper_local import rastrear_dominio, generar_corpus_optimizado

router = APIRouter(prefix="/conocimiento", tags=["Gestión de Conocimiento"])
logger = logging.getLogger(__name__)

trabajos_activos = {}

DIR_DESCARGAS = "datos_listos_dify"
os.makedirs(DIR_DESCARGAS, exist_ok=True)

class ScrapingRequest(BaseModel):
    url_objetivo: str
    limite_paginas: int = 15

async def ejecutar_scraping_segundo_plano(job_id: str, url: str, limite: int):
    try:
        paginas_extraidas = await rastrear_dominio(
            url_base=url, 
            limite_paginas=limite, 
            job_id=job_id, 
            dict_estado=trabajos_activos
        )

        if trabajos_activos[job_id]["estado_trabajo"] == "cancelled":
            return

        if not paginas_extraidas:
            trabajos_activos[job_id]["estado_trabajo"] = "failed"
            trabajos_activos[job_id]["mensaje"] = "No se logró extraer contenido válido de la URL."
            return

        texto_crudo = ""
        for i, pag in enumerate(paginas_extraidas):
            texto_crudo += f"INDICE_REGISTRO: {str(i).zfill(4)}\nORIGEN_URL: {pag['url']}\n---\n\n{pag['markdown']}\n\n"

        trabajos_activos[job_id]["mensaje"] = "Aplicando optimización y deduplicación semántica (ML)..."
        texto_optimizado = generar_corpus_optimizado(texto_crudo)

        fecha_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        nombre_crudo = f"conocimiento_crudo_{fecha_str}.md"
        nombre_opt = f"conocimiento_optimizado_{fecha_str}.md"
        
        ruta_crudo = os.path.join(DIR_DESCARGAS, nombre_crudo)
        ruta_opt = os.path.join(DIR_DESCARGAS, nombre_opt)

        with open(ruta_crudo, "w", encoding="utf-8") as f:
            f.write(texto_crudo)
            
        with open(ruta_opt, "w", encoding="utf-8") as f:
            f.write(texto_optimizado)

        trabajos_activos[job_id].update({
            "estado_trabajo": "completed",
            "mensaje": "Extracción y optimización semántica finalizada con éxito.",
            "archivo_crudo": ruta_crudo,
            "archivo_optimizado": ruta_opt
        })

    except Exception as e:
        logger.error(f"Error en tarea de scraping {job_id}: {str(e)}")
        trabajos_activos[job_id]["estado_trabajo"] = "error"
        trabajos_activos[job_id]["mensaje"] = str(e)

@router.post("/iniciar")
async def iniciar_extraccion(request: ScrapingRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    
    trabajos_activos[job_id] = {
        "estado_trabajo": "procesando",
        "total_paginas": 0,
        "mensaje": "Iniciando rastreo de dominio...",
        "archivo_crudo": None,
        "archivo_optimizado": None
    }
    
    background_tasks.add_task(ejecutar_scraping_segundo_plano, job_id, request.url_objetivo, request.limite_paginas)
    
    return {
        "status": "success",
        "job_id": job_id,
        "mensaje": "Tarea de extracción iniciada en segundo plano."
    }

@router.get("/estado/{job_id}")
async def consultar_estado(job_id: str):
    if job_id not in trabajos_activos:
        raise HTTPException(status_code=404, detail="El ID de tarea no existe.")
        
    return trabajos_activos[job_id]

@router.delete("/cancelar/{job_id}")
async def cancelar_extraccion(job_id: str):
    if job_id not in trabajos_activos:
        raise HTTPException(status_code=404, detail="El ID de tarea no existe.")
        
    if trabajos_activos[job_id]["estado_trabajo"] in ["completed", "error", "failed"]:
        raise HTTPException(status_code=400, detail="La tarea ya finalizó.")
        
    trabajos_activos[job_id]["estado_trabajo"] = "cancelled"
    trabajos_activos[job_id]["mensaje"] = "Cancelación forzada por el usuario."
    
    return {"status": "success", "mensaje": "Señal de cancelación enviada al crawler."}

@router.get("/descargar/{nombre_archivo}")
async def descargar_archivo(nombre_archivo: str):
    ruta_archivo = os.path.join(DIR_DESCARGAS, nombre_archivo)
    
    if not os.path.exists(ruta_archivo):
        raise HTTPException(status_code=404, detail="El archivo solicitado no existe.")
        
    return FileResponse(
        path=ruta_archivo, 
        filename=nombre_archivo, 
        media_type='text/markdown'
    )

# ------------------------------------------------------------------------------
# Módulo de Programación Automática (CRON Nativo con Asyncio - Cero Dependencias)
# ------------------------------------------------------------------------------
import asyncio
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import Optional
import httpx
import logging

logger = logging.getLogger(__name__)

# Estado en memoria del planificador nativo
_cron_config = {
    "programado": False,
    "frecuencia": None,
    "hora": None,
    "dia_semana": None,
    "url_objetivo": None,
    "limite_paginas": None,
    "siguiente_ejecucion": None,
    "detalles": ""
}
_cron_task: Optional[asyncio.Task] = None

DIAS_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
DIAS_NOMBRE = {"mon": "Lunes", "tue": "Martes", "wed": "Miércoles", "thu": "Jueves", "fri": "Viernes", "sat": "Sábado", "sun": "Domingo"}

class ProgramacionRequest(BaseModel):
    url_objetivo: str
    limite_paginas: int
    frecuencia: str  # "diario", "semanal"
    hora: str        # Formato "HH:MM" (ej. "02:00")
    dia_semana: Optional[str] = "mon"

def _calcular_proxima_ejecucion(frecuencia: str, hora_str: str, dia_semana: str) -> datetime:
    ahora = datetime.now()
    hora, minuto = map(int, hora_str.split(":"))
    proxima = ahora.replace(hour=hora, minute=minuto, second=0, microsecond=0)

    if frecuencia == "diario":
        if proxima <= ahora:
            proxima += timedelta(days=1)
    elif frecuencia == "semanal":
        dia_objetivo = DIAS_MAP.get(dia_semana, 0)
        dias_faltantes = (dia_objetivo - ahora.weekday()) % 7
        proxima += timedelta(days=dias_faltantes)
        if proxima <= ahora:
            proxima += timedelta(days=7)
    return proxima

async def _bucle_cron_nativo():
    """Bucle asíncrono ligero que duerme hasta la hora exacta programada."""
    while _cron_config["programado"]:
        proxima = _calcular_proxima_ejecucion(
            _cron_config["frecuencia"],
            _cron_config["hora"],
            _cron_config["dia_semana"]
        )
        _cron_config["siguiente_ejecucion"] = proxima.strftime("%Y-%m-%d %H:%M:%S")
        segundos_espera = max(1.0, (proxima - datetime.now()).total_seconds())
        
        logger.info(f"[CRON NATIVO] Próxima extracción programada para {_cron_config['siguiente_ejecucion']} (en {int(segundos_espera)}s)")
        
        try:
            await asyncio.sleep(segundos_espera)
            if not _cron_config["programado"]:
                break
                
            logger.info(f"[CRON NATIVO] Disparando extracción automática para {_cron_config['url_objetivo']}")
            async with httpx.AsyncClient() as client:
                payload = {
                    "url_objetivo": _cron_config["url_objetivo"],
                    "limite_paginas": _cron_config["limite_paginas"]
                }
                await client.post("http://localhost:8000/api/v1/admin/conocimiento/iniciar", json=payload, timeout=10.0)
            
            # Esperar 65 segundos tras disparar para no repetir en el mismo minuto
            await asyncio.sleep(65)
        except asyncio.CancelledError:
            logger.info("[CRON NATIVO] Tarea programada cancelada por el administrador.")
            break
        except Exception as e:
            logger.error(f"[CRON NATIVO] Error al ejecutar extracción programada: {e}")
            await asyncio.sleep(60)

@router.post("/programar", status_code=200)
async def programar_extraccion(config: ProgramacionRequest):
    global _cron_task
    if _cron_task and not _cron_task.done():
        _cron_task.cancel()

    proxima = _calcular_proxima_ejecucion(config.frecuencia, config.hora, config.dia_semana or "mon")
    detalle_texto = f"Diario a las {config.hora}" if config.frecuencia == "diario" else f"Semanal ({DIAS_NOMBRE.get(config.dia_semana, config.dia_semana)}) a las {config.hora}"

    _cron_config.update({
        "programado": True,
        "frecuencia": config.frecuencia,
        "hora": config.hora,
        "dia_semana": config.dia_semana or "mon",
        "url_objetivo": config.url_objetivo,
        "limite_paginas": config.limite_paginas,
        "siguiente_ejecucion": proxima.strftime("%Y-%m-%d %H:%M:%S"),
        "detalles": detalle_texto
    })

    _cron_task = asyncio.create_task(_bucle_cron_nativo())
    return {"estado": "exito", "mensaje": f"Scraping programado ({detalle_texto})."}

@router.get("/programacion_actual")
async def obtener_programacion():
    if not _cron_config["programado"]:
        return {"programado": False}
    return {
        "programado": True,
        "siguiente_ejecucion": _cron_config["siguiente_ejecucion"],
        "detalles": _cron_config["detalles"]
    }

@router.delete("/programar")
async def eliminar_programacion():
    global _cron_task
    _cron_config["programado"] = False
    if _cron_task and not _cron_task.done():
        _cron_task.cancel()
    return {"estado": "exito", "mensaje": "Programación automática desactivada."}