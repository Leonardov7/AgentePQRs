# ==============================================================================
# Gestor de WebSockets - Agente PQR
# Descripción: Maneja las conexiones TCP persistentes entre estudiantes y asesores
# ==============================================================================

from fastapi import WebSocket
from typing import Dict, List
import json
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Diccionario en memoria para rastrear las conexiones activas por cada sesión de chat.
        # Estructura esperada: { "sesion_id_uuid": {"estudiante": WebSocket, "asesor": WebSocket} }
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, websocket: WebSocket, sesion_id: str, rol: str):
        """
        Acepta una nueva conexión WebSocket y la registra en el diccionario en memoria.
        rol debe ser 'estudiante' o 'asesor'.
        """
        await websocket.accept()
        
        if sesion_id not in self.active_connections:
            self.active_connections[sesion_id] = {}
            
        self.active_connections[sesion_id][rol] = websocket
        logger.info(f"Nueva conexión WebSocket: Sesión {sesion_id} - Rol: {rol}")

    def disconnect(self, sesion_id: str, rol: str):
        """
        Elimina la conexión del registro en memoria cuando el usuario cierra la pestaña o pierde red.
        """
        if sesion_id in self.active_connections:
            if rol in self.active_connections[sesion_id]:
                del self.active_connections[sesion_id][rol]
            # Si ambos se desconectan, limpiamos la clave de la sesión para liberar memoria RAM
            if not self.active_connections[sesion_id]:
                del self.active_connections[sesion_id]
        logger.info(f"Desconexión WebSocket: Sesión {sesion_id} - Rol: {rol}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """
        Envía un mensaje JSON de vuelta únicamente al cliente que originó la acción (ej. confirmación de lectura).
        """
        await websocket.send_text(json.dumps(message))

    async def broadcast_to_session(self, sesion_id: str, message: dict, sender_rol: str = None):
        """
        Transmite un mensaje JSON a los participantes conectados en una sesión de chat específica.
        [MODIFICACIÓN ARQUITECTÓNICA]: Si se especifica sender_rol, el orquestador aborta la 
        transmisión hacia ese nodo específico, anulando el eco de red y previniendo la duplicación 
        de burbujas en interfaces de usuario optimistas (React).
        """
        if sesion_id in self.active_connections:
            for rol, connection in self.active_connections[sesion_id].items():
                if rol == sender_rol:
                    continue # Omisión algorítmica: El servidor ignora al emisor
                try:
                    await connection.send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"Fallo al enviar mensaje WebSocket a {rol} en sesión {sesion_id}: {str(e)}")

# Instancia global del gestor (Singleton). 
# Esta única variable manejará toda la carga de red en tiempo real de FastAPI.
manager = ConnectionManager()