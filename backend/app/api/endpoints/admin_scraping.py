# ==============================================================================
# Controlador de Extracción de Conocimiento (Scraping y Sincronización API)
# ==============================================================================

import os
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import logging

from app.services.scraper_local import rastrear_dominio, generar_corpus_optimizado
from app.services.dify_admin_client import sincronizar_documento_dify # INYECCIÓN DIFY

router = APIRouter(prefix="/conocimiento", tags=["Gestión de Conocimiento"])
logger = logging.getLogger(__name__)

trabajos_activos = {}

DIR_DESCARGAS = "datos_listos_dify"
os.makedirs(DIR_DESCARGAS, exist_ok=True)

# ------------------------------------------------------------------------------
# BUFFER DE AUDITORÍA GLOBAL (Mantiene los últimos 200 eventos en RAM)
# ------------------------------------------------------------------------------
_historial_logs = []

def agregar_log_global(mensaje: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_formateado = f"[{timestamp}] {mensaje}"
    _historial_logs.append(log_formateado)
    if len(_historial_logs) > 200:
        _historial_logs.pop(0)
    logger.info(f"AUDITORÍA SCRA: {mensaje}")

@router.get("/logs")
async def obtener_logs_sistema():
    return {"logs": _historial_logs}

# ------------------------------------------------------------------------------
# LÓGICA DE EXTRACCIÓN
# ------------------------------------------------------------------------------
class ScrapingRequest(BaseModel):
    url_objetivo: str
    limite_paginas: int = 15

async def ejecutar_scraping_segundo_plano(job_id: str, url: str, limite: int):
    try:
        agregar_log_global(f"[SISTEMA] Iniciando extracción en URL: {url} (Límite: {limite})")
        paginas_extraidas = await rastrear_dominio(
            url_base=url, 
            limite_paginas=limite, 
            job_id=job_id, 
            dict_estado=trabajos_activos
        )

        if trabajos_activos[job_id]["estado_trabajo"] == "cancelled":
            agregar_log_global("[SISTEMA] Rastreo cancelado por el administrador.")
            return

        if not paginas_extraidas:
            trabajos_activos[job_id]["estado_trabajo"] = "failed"
            agregar_log_global("[ERROR] No se logró extraer contenido válido de la URL.")
            return

        agregar_log_global(f"[SISTEMA] Extracción cruda finalizada. Páginas leídas: {len(paginas_extraidas)}")
        
        texto_crudo = ""
        for i, pag in enumerate(paginas_extraidas):
            texto_crudo += f"INDICE_REGISTRO: {str(i).zfill(4)}\nORIGEN_URL: {pag['url']}\n---\n\n{pag['markdown']}\n\n"

        agregar_log_global("[SISTEMA] Aplicando modelo ML de deduplicación semántica...")
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

        agregar_log_global("[ÉXITO] Bases de conocimiento renderizadas y guardadas en disco local.")

        # --- INTEGRACIÓN CON DIFY API ---
        agregar_log_global("[SISTEMA] Iniciando protocolo de sincronización con Dify...")
        await sincronizar_documento_dify(ruta_opt, agregar_log_global)

        trabajos_activos[job_id].update({
            "estado_trabajo": "completed",
            "mensaje": "Proceso integral completado.",
            "archivo_crudo": ruta_crudo,
            "archivo_optimizado": ruta_opt
        })

    except Exception as e:
        agregar_log_global(f"[ERROR CRÍTICO] Fallo general: {str(e)}")
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
    return {"status": "success", "job_id": job_id, "mensaje": "Tarea iniciada."}

@router.get("/estado/{job_id}")
async def consultar_estado(job_id: str):
    if job_id not in trabajos_activos:
        raise HTTPException(status_code=404, detail="El ID de tarea no existe.")
    return trabajos_activos[job_id]

@router.delete("/cancelar/{job_id}")
async def cancelar_extraccion(job_id: str):
    if job_id not in trabajos_activos:
        raise HTTPException(status_code=404, detail="El ID de tarea no existe.")
    trabajos_activos[job_id]["estado_trabajo"] = "cancelled"
    return {"status": "success", "mensaje": "Señal de cancelación enviada al crawler."}

@router.get("/descargar/{nombre_archivo}")
async def descargar_archivo(nombre_archivo: str):
    ruta_archivo = os.path.join(DIR_DESCARGAS, nombre_archivo)
    if not os.path.exists(ruta_archivo):
        raise HTTPException(status_code=404, detail="El archivo solicitado no existe.")
    return FileResponse(path=ruta_archivo, filename=nombre_archivo, media_type='text/markdown')

@router.get("/historial-archivos")
async def listar_archivos_conocimiento():
    if not os.path.exists(DIR_DESCARGAS):
        return {"archivos": []}
    lista_archivos = []
    for nombre_archivo in os.listdir(DIR_DESCARGAS):
        if nombre_archivo.endswith('.md'):
            ruta_completa = os.path.join(DIR_DESCARGAS, nombre_archivo)
            tamaño_kb = round(os.path.getsize(ruta_completa) / 1024, 1)
            fecha_mod_ts = os.path.getmtime(ruta_completa)
            fecha_str = datetime.fromtimestamp(fecha_mod_ts).strftime("%Y-%m-%d %H:%M:%S")
            tipo = "Optimizado (IA)" if "optimizado" in nombre_archivo.lower() else "Original (Crudo)"
            lista_archivos.append({
                "nombre": nombre_archivo,
                "tipo": tipo,
                "peso_kb": tamaño_kb,
                "fecha": fecha_str,
                "timestamp_raw": fecha_mod_ts
            })
    lista_archivos.sort(key=lambda x: x["timestamp_raw"], reverse=True)
    return {"archivos": lista_archivos}

# ------------------------------------------------------------------------------
# Módulo de Programación Automática (CRON)
# ------------------------------------------------------------------------------
import asyncio
from typing import Optional
import httpx

_cron_config = {
    "programado": False,
    "frecuencia": None, "hora": None, "dia_semana": None,
    "fecha_inicio": None, "fecha_fin": None,
    "url_objetivo": None, "limite_paginas": None,
    "siguiente_ejecucion": None, "detalles": ""
}
_cron_task: Optional[asyncio.Task] = None

DIAS_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
DIAS_NOMBRE = {"mon": "Lunes", "tue": "Martes", "wed": "Miércoles", "thu": "Jueves", "fri": "Viernes", "sat": "Sábado", "sun": "Domingo"}

class ProgramacionRequest(BaseModel):
    url_objetivo: str
    limite_paginas: int
    frecuencia: str 
    hora: str        
    dia_semana: Optional[str] = "mon"
    fecha_inicio: Optional[str] = None
    fecha_fin: Optional[str] = None

def _calcular_proxima_ejecucion(frecuencia: str, hora_str: str, dia_semana: str, fecha_inicio_str: str = None) -> datetime:
    ahora = datetime.now()
    base_dt = ahora
    if fecha_inicio_str:
        inicio_req = datetime.strptime(fecha_inicio_str, "%Y-%m-%d")
        if inicio_req > ahora: base_dt = inicio_req
    hora, minuto = map(int, hora_str.split(":"))
    proxima = base_dt.replace(hour=hora, minute=minuto, second=0, microsecond=0)
    if frecuencia == "diario":
        if proxima <= ahora: proxima += timedelta(days=1)
    elif frecuencia == "semanal":
        dia_objetivo = DIAS_MAP.get(dia_semana, 0)
        dias_faltantes = (dia_objetivo - proxima.weekday()) % 7
        proxima += timedelta(days=dias_faltantes)
        if proxima <= ahora: proxima += timedelta(days=7)
    return proxima

async def _bucle_cron_nativo():
    agregar_log_global("[CRON] Hilo de automatización activado en segundo plano.")
    while _cron_config["programado"]:
        ahora = datetime.now()
        if _cron_config["fecha_fin"]:
            limite_fin = datetime.strptime(_cron_config["fecha_fin"], "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            if ahora > limite_fin:
                agregar_log_global("[CRON] Fecha de finalización alcanzada. Tarea desactivada.")
                _cron_config["programado"] = False
                break
        proxima = _calcular_proxima_ejecucion(
            _cron_config["frecuencia"], _cron_config["hora"], _cron_config["dia_semana"], _cron_config["fecha_inicio"]
        )
        _cron_config["siguiente_ejecucion"] = proxima.strftime("%Y-%m-%d %H:%M:%S")
        segundos_espera = max(1.0, (proxima - datetime.now()).total_seconds())
        
        try:
            await asyncio.sleep(segundos_espera)
            if not _cron_config["programado"]: break
            
            agregar_log_global(f"[CRON] Disparando extracción programada en URL: {_cron_config['url_objetivo']}")
            
            # Lanzamos la tarea a nuestro propio endpoint interno
            async with httpx.AsyncClient() as client:
                payload = {
                    "url_objetivo": _cron_config["url_objetivo"],
                    "limite_paginas": _cron_config["limite_paginas"]
                }
                await client.post("http://localhost:8000/api/v1/admin/conocimiento/iniciar", json=payload, timeout=10.0)
            
            await asyncio.sleep(65)
        except asyncio.CancelledError:
            agregar_log_global("[CRON] Tarea cancelada manualmente.")
            break
        except Exception as e:
            logger.error(f"[CRON NATIVO] Error: {e}")
            await asyncio.sleep(60)

@router.post("/programar", status_code=200)
async def programar_extraccion(config: ProgramacionRequest):
    global _cron_task
    if _cron_task and not _cron_task.done():
        _cron_task.cancel()
    proxima = _calcular_proxima_ejecucion(config.frecuencia, config.hora, config.dia_semana or "mon", config.fecha_inicio)
    detalle_texto = f"Diario a las {config.hora}" if config.frecuencia == "diario" else f"Semanal ({DIAS_NOMBRE.get(config.dia_semana, config.dia_semana)}) a las {config.hora}"
    if config.fecha_inicio: detalle_texto += f", inicia {config.fecha_inicio}"
    if config.fecha_fin: detalle_texto += f", finaliza {config.fecha_fin}"

    _cron_config.update({
        "programado": True, "frecuencia": config.frecuencia, "hora": config.hora,
        "dia_semana": config.dia_semana or "mon", "fecha_inicio": config.fecha_inicio,
        "fecha_fin": config.fecha_fin, "url_objetivo": config.url_objetivo,
        "limite_paginas": config.limite_paginas,
        "siguiente_ejecucion": proxima.strftime("%Y-%m-%d %H:%M:%S"),
        "detalles": detalle_texto
    })
    _cron_task = asyncio.create_task(_bucle_cron_nativo())
    return {"estado": "exito", "mensaje": f"Automatización programada ({detalle_texto})."}

@router.get("/programacion_actual")
async def obtener_programacion():
    if not _cron_config["programado"]: return {"programado": False}
    return {
        "programado": True, "siguiente_ejecucion": _cron_config["siguiente_ejecucion"], "detalles": _cron_config["detalles"]
    }

@router.delete("/programar")
async def eliminar_programacion():
    global _cron_task
    _cron_config["programado"] = False
    if _cron_task and not _cron_task.done():
        _cron_task.cancel()
    return {"estado": "exito", "mensaje": "Automatización desactivada."}