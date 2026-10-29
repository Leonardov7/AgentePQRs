# ==============================================================================
# Motor de Extracción Semántica Local (Playwright + BS4)
# Descripción: Extrae contenido dinámico, limpia el DOM y aplica un aplanador
# semántico mediante Regex para destruir tablas Markdown y evitar la orfandad 
# de datos durante el chunking en el motor RAG.
# ==============================================================================

import asyncio
import logging
import re
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from playwright.async_api import async_playwright
from typing import List, Dict, Any
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

# Etiquetas HTML que introducen ruido al LLM y deben ser destruidas
ETIQUETAS_BASURA = [
    'nav', 'footer', 'header', 'aside', 'script', 'style', 
    'noscript', 'iframe', 'svg', 'button', 'form'
]

def aplanar_semantica_markdown(markdown_crudo: str) -> str:
    """
    Procesa el texto Markdown línea por línea para desenrollar tablas y propagar
    el contexto de los encabezados hacia las listas huérfanas.
    """
    lineas = markdown_crudo.split('\n')
    resultado = []
    encabezado_actual = ""
    en_tabla = False

    for linea in lineas:
        linea_limpia = linea.strip()

        # 1. Capturar el contexto del encabezado (Ej: "## Sede Fusagasugá")
        match_encabezado = re.match(r'^(#{1,6})\s+(.+)', linea_limpia)
        if match_encabezado:
            encabezado_actual = match_encabezado.group(2).strip()
            resultado.append(linea_limpia)
            continue

        # 2. Desenrollado de Tablas (Table Unrolling)
        match_tabla = re.match(r'^\|(.*)\|$', linea_limpia)
        if match_tabla:
            en_tabla = True
            contenido_filas = match_tabla.group(1)
            
            # Ignorar las filas de formato de tabla Markdown y los encabezados
            if "---" in contenido_filas or re.search(r'Sede.*Programa|Programa.*Sede', contenido_filas, re.IGNORECASE):
                continue
            
            # Dividir columnas y limpiar espacios en blanco
            columnas = [col.strip() for col in contenido_filas.split('|') if col.strip()]
            
            # Procesamiento de tablas de 2 columnas
            if len(columnas) == 2:
                col1, col2 = columnas[0], columnas[1]
                if re.search(r'Ingeniería|Licenciatura|Profesional|Administración|Zootecnia|Enfermería|Tecnología|Especialización|Maestría', col1, re.IGNORECASE):
                    oracion = f"El programa de {col1} se oferta en la sede de {col2}."
                else:
                    oracion = f"En la sede de {col1} se oferta el programa de {col2}."
                resultado.append(oracion)
            
            # Procesamiento de tablas de 3 columnas (ej. con fecha de radicación)
            elif len(columnas) == 3:
                programa, sede, fecha = columnas[0], columnas[1], columnas[2]
                resultado.append(f"El programa de {programa} se oferta en la sede de {sede} (Fecha de radicación registrada: {fecha}).")
            
            continue

        # Control de saltos de línea al salir de una tabla
        if en_tabla and not match_tabla:
            en_tabla = False
            resultado.append("")

        # 3. Propagación de Encabezados en Listas (Viñetas)
        match_lista = re.match(r'^[-*]\s+(.+)', linea_limpia)
        if match_lista:
            item_lista = match_lista.group(1).strip()
            if encabezado_actual:
                resultado.append(f"- [Contexto: {encabezado_actual}] {item_lista}")
            else:
                resultado.append(linea_limpia)
            continue

        # 4. Conservar texto normal
        resultado.append(linea_limpia)

    # Limpieza final de saltos de línea múltiples
    texto_final = '\n'.join(resultado)
    texto_final = re.sub(r'\n{3,}', '\n\n', texto_final)
    return texto_final

async def extraer_contenido_pagina(url: str, browser_context) -> Dict[str, Any]:
    """
    Navega a una URL específica, espera el renderizado completo y extrae el contenido principal.
    """
    page = await browser_context.new_page()
    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
        
        html_crudo = await page.content()
        titulo = await page.title()
        
        soup = BeautifulSoup(html_crudo, "html.parser")
        
        for elemento in soup.find_all(ETIQUETAS_BASURA):
            elemento.decompose()

        contenedor_principal = soup.find('main') or soup.find('article') or soup.find('div', id=lambda x: x and 'content' in x.lower())
        
        if contenedor_principal:
            html_limpio = str(contenedor_principal)
        else:
            html_limpio = str(soup.body) if soup.body else str(soup)

        # Conversión a Markdown semántico crudo
        markdown_crudo = md(
            html_limpio, 
            heading_style="ATX", 
            strip=['a', 'img'], 
            bullets="-"
        ).strip()
        
        # Inyección del algoritmo de aplanamiento para destruir tablas y anclar contextos
        markdown_procesado = aplanar_semantica_markdown(markdown_crudo)

        return {
            "url": url,
            "titulo": titulo,
            "markdown": markdown_procesado,
            "exito": True
        }

    except Exception as e:
        logger.error(f"Fallo al extraer {url}: {str(e)}")
        return {
            "url": url,
            "titulo": "Error",
            "markdown": "",
            "exito": False
        }
    finally:
        await page.close()

async def rastrear_dominio(url_base: str, limite_paginas: int = 50) -> List[Dict[str, Any]]:
    """
    Motor de Crawling BFS (Búsqueda en Anchura).
    Descubre enlaces internos recursivamente y extrae su contenido.
    """
    paginas_extraidas = []
    urls_visitadas = set()
    cola_urls = [url_base]
    dominio_base = urlparse(url_base).netloc

    logger.info(f">>> [SCRAPER LOCAL] Iniciando rastreo profundo en: {url_base}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) OrquestadorPQR/1.0"
        )

        while cola_urls and len(paginas_extraidas) < limite_paginas:
            url_actual = cola_urls.pop(0)
            url_actual = url_actual.rstrip('/')
            
            if url_actual in urls_visitadas:
                continue
                
            urls_visitadas.add(url_actual)
            logger.info(f"[{len(paginas_extraidas) + 1}/{limite_paginas}] Extrayendo: {url_actual}")

            datos_pagina = await extraer_contenido_pagina(url_actual, context)
            
            if not datos_pagina["exito"] or not datos_pagina["markdown"]:
                continue

            paginas_extraidas.append(datos_pagina)

            page = await context.new_page()
            try:
                await page.goto(url_actual, wait_until="domcontentloaded", timeout=15000)
                enlaces_elementos = await page.query_selector_all("a")
                
                for enlace in enlaces_elementos:
                    href = await enlace.get_attribute("href")
                    if href:
                        url_absoluta = urljoin(url_base, href)
                        url_absoluta = url_absoluta.split('#')[0]
                        
                        if urlparse(url_absoluta).netloc == dominio_base:
                            if not url_absoluta.lower().endswith(('.pdf', '.jpg', '.png', '.zip', '.rar', '.mp4')):
                                if url_absoluta not in urls_visitadas and url_absoluta not in cola_urls:
                                    cola_urls.append(url_absoluta)
            except Exception as e:
                logger.warning(f"No se pudieron extraer enlaces hijos de {url_actual}: {str(e)}")
            finally:
                await page.close()

        await browser.close()
        
    logger.info(f">>> [SCRAPER LOCAL] Rastreo finalizado. Páginas extraídas: {len(paginas_extraidas)}")
    return paginas_extraidas