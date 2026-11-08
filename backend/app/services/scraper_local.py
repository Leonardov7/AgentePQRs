# ==============================================================================
# Motor de Extracción Semántica Local (Playwright + BS4 + ML)
# Descripción: Extrae contenido dinámico, limpia el DOM y aplica un aplanador
# semántico mediante Regex para destruir tablas Markdown. Incluye deduplicación
# vectorial para optimización de contexto RAG.
# ==============================================================================

import asyncio
import logging
import re
import numpy as np
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from playwright.async_api import async_playwright
from typing import List, Dict, Any
from urllib.parse import urljoin, urlparse
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

ETIQUETAS_BASURA = [
    'nav', 'footer', 'header', 'aside', 'script', 'style', 
    'noscript', 'iframe', 'svg', 'button', 'form'
]

def aplanar_semantica_markdown(markdown_crudo: str) -> str:
    lineas = markdown_crudo.split('\n')
    resultado = []
    encabezado_actual = ""
    en_tabla = False

    for linea in lineas:
        linea_limpia = linea.strip()

        match_encabezado = re.match(r'^(#{1,6})\s+(.+)', linea_limpia)
        if match_encabezado:
            encabezado_actual = match_encabezado.group(2).strip()
            resultado.append(linea_limpia)
            continue

        match_tabla = re.match(r'^\|(.*)\|$', linea_limpia)
        if match_tabla:
            en_tabla = True
            contenido_filas = match_tabla.group(1)
            
            if "---" in contenido_filas or re.search(r'Sede.*Programa|Programa.*Sede', contenido_filas, re.IGNORECASE):
                continue
            
            columnas = [col.strip() for col in contenido_filas.split('|') if col.strip()]
            
            if len(columnas) == 2:
                col1, col2 = columnas[0], columnas[1]
                if re.search(r'Ingeniería|Licenciatura|Profesional|Administración|Zootecnia|Enfermería|Tecnología|Especialización|Maestría', col1, re.IGNORECASE):
                    oracion = f"El programa de {col1} se oferta en la sede de {col2}."
                else:
                    oracion = f"En la sede de {col1} se oferta el programa de {col2}."
                resultado.append(oracion)
            
            elif len(columnas) == 3:
                programa, sede, fecha = columnas[0], columnas[1], columnas[2]
                resultado.append(f"El programa de {programa} se oferta en la sede de {sede} (Fecha de radicación registrada: {fecha}).")
            
            continue

        if en_tabla and not match_tabla:
            en_tabla = False
            resultado.append("")

        match_lista = re.match(r'^[-*]\s+(.+)', linea_limpia)
        if match_lista:
            item_lista = match_lista.group(1).strip()
            if encabezado_actual:
                resultado.append(f"- [Contexto: {encabezado_actual}] {item_lista}")
            else:
                resultado.append(linea_limpia)
            continue

        resultado.append(linea_limpia)

    texto_final = '\n'.join(resultado)
    texto_final = re.sub(r'\n{3,}', '\n\n', texto_final)
    return texto_final

async def extraer_contenido_pagina(url: str, browser_context) -> Dict[str, Any]:
    page = await browser_context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
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

        markdown_crudo = md(
            html_limpio, 
            heading_style="ATX", 
            strip=['a', 'img'], 
            bullets="-"
        ).strip()
        
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

async def rastrear_dominio(url_base: str, limite_paginas: int = 50, job_id: str = None, dict_estado: dict = None) -> List[Dict[str, Any]]:
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
            if dict_estado and job_id:
                if dict_estado.get(job_id, {}).get("estado_trabajo") == "cancelled":
                    logger.info("Rastreo abortado por solicitud del usuario.")
                    break

            url_actual = cola_urls.pop(0)
            url_actual = url_actual.rstrip('/')
            
            if url_actual in urls_visitadas:
                continue
                
            urls_visitadas.add(url_actual)
            logger.info(f"[{len(paginas_extraidas) + 1}/{limite_paginas}] Extrayendo: {url_actual}")
            
            if dict_estado and job_id:
                dict_estado[job_id]["total_paginas"] = len(paginas_extraidas)

            datos_pagina = await extraer_contenido_pagina(url_actual, context)
            
            if not datos_pagina["exito"] or not datos_pagina["markdown"]:
                continue

            paginas_extraidas.append(datos_pagina)

            page = await context.new_page()
            try:
                await page.goto(url_actual, wait_until="domcontentloaded", timeout=30000)
                enlaces_elementos = await page.query_selector_all("a")
                
                for enlace in enlaces_elementos:
                    href = await enlace.get_attribute("href")
                    if href:
                        url_absoluta = urljoin(url_base, href)
                        url_absoluta = url_absoluta.split('#')[0]
                        
                        if urlparse(url_absoluta).netloc == dominio_base:
                            if not url_absoluta.lower().endswith(('.pdf', '.jpg', '.png', '.zip', '.rar', '.mp4', '.xlsx', '.xls', '.docx', '.doc', '.xlsm')):
                                if url_absoluta not in urls_visitadas and url_absoluta not in cola_urls:
                                    cola_urls.append(url_absoluta)
            except Exception as e:
                logger.warning(f"No se pudieron extraer enlaces hijos de {url_actual}: {str(e)}")
            finally:
                await page.close()

        await browser.close()
        
    logger.info(f">>> [SCRAPER LOCAL] Rastreo finalizado. Páginas extraídas: {len(paginas_extraidas)}")
    return paginas_extraidas

# ==============================================================================
# PIPELINE DE ML: LIMPIEZA SEMÁNTICA Y DEDUPLICACIÓN
# ==============================================================================

def _limpiar_heuristica_basica(texto: str) -> str:
    texto = re.sub(r'-\s+\[Contexto:.*?\]\s+Inicio\n', '', texto, flags=re.IGNORECASE)
    patrones_cta = [
        r'^Ver más$', r'^Descargar$', r'^Inscríbete$', r'^Leer más$',
        r'^Ver perfil$', r'^Descargar plan rectoral$', r'^Ir a Autoevaluación$',
        r'^Ver más noticias relacionadas$', r'^Ver más información aquí$', r'^Descarga aquí.*$'
    ]
    for patron in patrones_cta:
        texto = re.sub(patron, '', texto, flags=re.MULTILINE | re.IGNORECASE)
    
    texto = re.sub(r'^(?P<linea>.{1,50})$\n+(?P=linea)', r'\g<linea>', texto, flags=re.MULTILINE)
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    return texto.strip()

def generar_corpus_optimizado(texto_completo: str, umbral_similitud: float = 0.88) -> str:
    logger.info(">>> [FILTRO SEMÁNTICO] Iniciando limpieza de ruido RAG...")
    registros = re.split(r'(INDICE_REGISTRO:\s+\d+\nORIGEN_URL:\s+.*?\n---)', texto_completo)
    
    if len(registros) < 3:
        return texto_completo 
        
    logger.info("Cargando modelo Sentence-Transformer en memoria...")
    modelo = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    
    documento_optimizado = ""
    total_parrafos_originales = 0
    total_parrafos_retenidos = 0
    
    for i in range(1, len(registros), 2):
        cabecera = registros[i]
        cuerpo = registros[i+1] if i+1 < len(registros) else ""
        
        cuerpo_limpio = _limpiar_heuristica_basica(cuerpo)
        
        bloques_crudos = cuerpo_limpio.split('\n\n')
        parrafos = [bloque.strip() for bloque in bloques_crudos if len(bloque.strip()) > 15]
        total_parrafos_originales += len(parrafos)
        
        if len(parrafos) > 2:
            embeddings = modelo.encode(parrafos, convert_to_tensor=False)
            parrafos_unicos = []
            embeddings_unicos = []
            
            for parrafo, embedding in zip(parrafos, embeddings):
                if not embeddings_unicos:
                    parrafos_unicos.append(parrafo)
                    embeddings_unicos.append(embedding)
                    continue
                
                similitudes = cosine_similarity([embedding], embeddings_unicos)[0]
                if np.max(similitudes) < umbral_similitud:
                    parrafos_unicos.append(parrafo)
                    embeddings_unicos.append(embedding)
            parrafos_optimizados = parrafos_unicos
        else:
            parrafos_optimizados = parrafos
            
        total_parrafos_retenidos += len(parrafos_optimizados)
        cuerpo_final = "\n\n".join(parrafos_optimizados)
        documento_optimizado += f"{cabecera}\n\n{cuerpo_final}\n\n"
        
    logger.info(f">>> [FILTRO SEMÁNTICO] Optimización completada. Párrafos retenidos: {total_parrafos_retenidos} de {total_parrafos_originales}.")
    return documento_optimizado