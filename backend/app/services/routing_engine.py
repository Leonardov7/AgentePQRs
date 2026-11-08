# ==============================================================================
# Motor de Enrutamiento Condicional - Agente PQR
# Descripción: Evalúa la confianza del LLM, procesa banderas de cortesía 
# y ejecuta el escalamiento algorítmico a asesores humanos.
# ==============================================================================

import os
import logging
import json
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from uuid import UUID

from app.models.models import Sesion, Mensaje

logger = logging.getLogger(__name__)

def obtener_umbral_dinamico() -> float:
    try:
        with open("assets/configuracion.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            if "umbral_rag" in data:
                return float(data["umbral_rag"])
    except:
        pass
    return float(os.getenv("SIMILARITY_THRESHOLD", "35.0"))

def traducir_distancia_a_confianza(similitud_cruda: float) -> float:
    """
    Convierte la distancia vectorial bruta (0.0 a 1.0) en un porcentaje humano (0% a 100%).
    """
    if similitud_cruda is None:
        return 0.0
    
    sim_float = float(similitud_cruda)
    confianza = sim_float * 100.0
    
    return round(confianza, 1)

def intencion_solicitar_humano(texto_usuario: str) -> bool:
    """
    Verifica si el usuario está pidiendo explícitamente comunicarse con un humano.
    """
    patrones = [
        r"hablar\s+con\s+humano",
        r"hablar\s+con\s+asesor",
        r"comunicar\s+con\s+alguien",
        r"pasar\s+con\s+asesor",
        r"necesito\s+un\s+humano",
        r"hablar\s+con\s+persona"
    ]
    texto_limpio = texto_usuario.lower()
    for patron in patrones:
        if re.search(patron, texto_limpio):
            return True
    return False

async def evaluar_y_enrutar_respuesta(db: AsyncSession, sesion_id: UUID, respuesta_dify: dict = None, peticion_usuario: str = None) -> dict:
    """
    Recibe el payload de Dify, evalúa el puntaje de similitud RAG, 
    interactúa con las etiquetas del LLM y altera el estado de la sesión.
    """
    
    # 0. BYPASS POR INTENCIÓN EXPLÍCITA DEL USUARIO
    if peticion_usuario and intencion_solicitar_humano(peticion_usuario):
        logger.warning(f">>> [INTENCIÓN DETECTADA] El usuario solicitó atención humana explícita.")
        return {
            "accion": "ofrecer_escalamiento",
            "estado_actual": "atencion_bot",
            "mensaje_publico": "¿Quieres que te comunique con un asesor institucional?",
            "opciones": [
                {"label": "👤 Sí, hablar con un asesor", "value": "/escalar_humano"},
                {"label": "🔄 No, continuar con el bot", "value": "/continuar"}
            ]
        }

    # Procesamiento normal de la respuesta de Dify
    logger.warning(">>> [DEBUG DIFY PAYLOAD] Paquete crudo recibido de la API:")
    logger.warning(json.dumps(respuesta_dify, indent=2, ensure_ascii=False))

    texto_respuesta = respuesta_dify.get("respuesta", "Ocurrió un error procesando la respuesta.")
    similitud = respuesta_dify.get("similitud_rag")
    url_fuente = respuesta_dify.get("url_fuente")
    estado_dify = respuesta_dify.get("estado")

    umbral_actual = obtener_umbral_dinamico()
    confianza_humana = traducir_distancia_a_confianza(similitud)
    str_similitud = f"{float(similitud):.3f}" if similitud is not None else "0.000"
    
    etiqueta_visual = f"*[DISTANCIA VECTORIAL: {str_similitud} | CONFIANZA: {confianza_humana}% | UMBRAL: {umbral_actual}%]*\n\n"

    # 1. Fallo catastrófico de red o API
    if estado_dify == "error":
        logger.error(f">>> [FALLO COGNITIVO] Error de conexión con Dify. Escalando sesión {sesion_id}.")
        await _escalar_a_humano(db, sesion_id)
        return {
            "accion": "escalado",
            "mensaje_publico": etiqueta_visual + "He tenido un problema técnico procesando tu solicitud. Te transferiré con un asesor humano para asistencia inmediata."
        }

    # 2. EVALUACIÓN DE BANDERA DETERMINISTA (BYPASS DE CORTESÍA)
    es_cortesia = False
    if "[CORTESÍA]" in texto_respuesta:
        es_cortesia = True
        texto_respuesta = texto_respuesta.replace("[CORTESÍA]", "").strip()
        logger.warning(f">>> [BYPASS] Etiqueta de cortesía detectada. Se ignora la baja similitud vectorial ({str_similitud}).")

    texto_limpio_bd = texto_respuesta

    # 3. EVALUACIÓN DE ALUCINACIÓN EXPRESA (EL LLM ADMITE IGNORANCIA)
    if "no poseo información institucional verificada" in texto_respuesta:
        logger.warning(">>> [PAUSA] El LLM no tiene la información. Ofreciendo opciones al usuario.")
        
        mensaje_auditoria = Mensaje(
            sesion_id=sesion_id,
            emisor="bot",
            contenido="Lo siento, no poseo información institucional verificada sobre esta consulta. ¿Deseas hablar con un asesor o prefieres reformular tu pregunta?",
            similitud_rag=similitud,
            url_fuente=url_fuente
        )
        db.add(mensaje_auditoria)
        await db.commit()
        
        return {
            "accion": "ofrecer_escalamiento",
            "estado_actual": "atencion_bot",
            "mensaje_publico": etiqueta_visual + "Lo siento, no poseo información institucional verificada sobre esta consulta en mi base actual.\n\n¿Qué deseas hacer?",
            "opciones": [
                {"label": "👤 Hablar con un asesor humano", "value": "/escalar_humano"},
                {"label": "🔄 Reformular mi pregunta", "value": "/continuar"}
            ]
        }
    
    # 4. EVALUACIÓN ALGORÍTMICA DE CONFIANZA (Solo aplica si NO es cortesía)
    if not es_cortesia and (similitud is None or confianza_humana < umbral_actual):
        logger.warning(f">>> [DESVÍO] Similitud ({similitud}) inferior al umbral ({umbral_actual}%). Ofreciendo opciones.")
        
        mensaje_rechazo = f"[BLOQUEADO POR BAJA CONFIANZA: {confianza_humana}%] {texto_limpio_bd}"
        mensaje_auditoria = Mensaje(
            sesion_id=sesion_id,
            emisor="sistema",
            contenido=mensaje_rechazo,
            similitud_rag=similitud,
            url_fuente=url_fuente
        )
        db.add(mensaje_auditoria)
        await db.commit()
        
        return {
            "accion": "ofrecer_escalamiento",
            "estado_actual": "atencion_bot",
            "mensaje_publico": etiqueta_visual + "Mi nivel de certeza sobre esta normativa no es lo suficientemente alto para darte una respuesta oficial.\n\n¿Quieres que te comunique con un asesor humano?",
            "opciones": [
                {"label": "👤 Sí, hablar con un asesor", "value": "/escalar_humano"},
                {"label": "🔄 No, reformular mi pregunta", "value": "/continuar"}
            ]
        }

    # 5. RESPUESTA APROBADA (Supera el umbral RAG o es una cortesía flaggeada)
    if es_cortesia:
        logger.warning(">>> [APROBADO] Entregando saludo de cortesía al usuario.")
    else:
        logger.warning(">>> [APROBADO] Similitud RAG suficiente. Entregando respuesta institucional.")

    mensaje_valido = Mensaje(
        sesion_id=sesion_id,
        emisor="bot",
        contenido=texto_limpio_bd,  
        similitud_rag=similitud,
        url_fuente=url_fuente
    )
    db.add(mensaje_valido)
    
    stmt = update(Sesion).where(Sesion.id == sesion_id).values(estado="atencion_bot")
    await db.execute(stmt)
    await db.commit()

    return {
        "accion": "respuesta_bot",
        "mensaje_publico": etiqueta_visual + texto_respuesta,
        "metadatos": {
            "similitud": similitud,
            "fuente": url_fuente
        }
    }

async def _escalar_a_humano(db: AsyncSession, sesion_id: UUID):
    """
    Actualiza el estado de la sesión en PostgreSQL para derivarla al dashboard WS.
    """
    stmt = update(Sesion).where(Sesion.id == sesion_id).values(estado="en_cola")
    await db.execute(stmt)
    
    mensaje_sistema = Mensaje(
        sesion_id=sesion_id,
        emisor="sistema",
        contenido="[ALERTA] Sesión escalada a atención humana."
    )
    db.add(mensaje_sistema)
    await db.commit()