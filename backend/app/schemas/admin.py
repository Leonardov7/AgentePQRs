# ==============================================================================
# Esquemas Pydantic - Panel de Administración y Scraping
# Descripción: Validación estricta de datos de entrada y salida para el
# orquestador de ingesta de conocimiento mediante Firecrawl.
# ==============================================================================

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime

class PeticionScraping(BaseModel):
    """
    Esquema para la solicitud de inicio de un trabajo de rastreo (crawl) a Firecrawl.
    """
    url_objetivo: HttpUrl = Field(..., description="La URL raíz desde donde iniciará el rastreo.")
    limite_paginas: int = Field(default=50, ge=1, le=500, description="Límite de subpáginas a procesar para evitar desbordamiento.")

class RespuestaInicioScraping(BaseModel):
    """
    Esquema de respuesta al iniciar el rastreo asíncrono.
    """
    estado: str = Field(..., description="Estado de la solicitud enviada a Firecrawl.")
    job_id: str = Field(..., description="Identificador único del trabajo de rastreo en Firecrawl.")
    mensaje: str = Field(..., description="Mensaje informativo para el dashboard del administrador.")

class MetadatosPaginaScrapeada(BaseModel):
    """
    Esquema para mapear los metadatos devueltos por Firecrawl por cada página.
    """
    sourceURL: str
    title: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = None

class DocumentoScrapeado(BaseModel):
    """
    Esquema de una página individual procesada.
    """
    markdown: str
    metadata: Optional[MetadatosPaginaScrapeada] = None

class RespuestaEstadoScraping(BaseModel):
    """
    Esquema de respuesta al consultar el estado de un trabajo en curso.
    """
    estado_trabajo: str = Field(..., description="Puede ser 'scraping', 'completed', o 'failed'.")
    total_paginas: int = Field(default=0, description="Cantidad de páginas procesadas hasta el momento.")
    mensaje: str
    archivo_generado: Optional[str] = Field(None, description="Ruta del archivo Markdown unificado si el trabajo finalizó.")