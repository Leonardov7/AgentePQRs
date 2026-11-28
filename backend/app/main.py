# ==============================================================================
# Entrypoint FastAPI - Agente PQR
# Descripción: Inicialización del servidor, middleware y registro de rutas
# ==============================================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Importación de los Controladores (Routers)
from app.api.endpoints import chat, asesores, admin_scraping, configuracion, admin_documentos
# Inicialización de la aplicación con metadatos para la documentación automática (Swagger)
app = FastAPI(
    title="API Orquestador PQR UdeC",
    description="Núcleo de enrutamiento cognitivo y gestión de sesiones de chat para la Universidad de Cundinamarca",
    version="1.0.0"
)

# ------------------------------------------------------------------------------
# Configuración de CORS (Cross-Origin Resource Sharing)
# ------------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # En producción se debe restringir a los dominios de la universidad
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------------------
# Registro de Rutas REST
# ------------------------------------------------------------------------------
# Acoplamos el router de chat que creamos en el paso anterior.
# Todas las rutas dentro de chat.py ahora estarán prefijadas con /api/v1/chat

app.include_router(admin_documentos.router, prefix="/api/v1/admin", tags=["Documentos Adicionales"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Interacción Estudiantes"])

# Rutas del Panel Administrativo para Gestión de Asesores
app.include_router(asesores.router, prefix="/api/v1/admin", tags=["Dashboard Asesores"])

# Rutas del Panel Administrativo para Gestión de Conocimiento (Scraping)
# CORRECCIÓN APLICADA: Se ajusta el prefix a "/api/v1/admin" para que al unirse con 
# el prefix interno "/conocimiento" de admin_scraping.py resulte exactamente en "/api/v1/admin/conocimiento/iniciar"
app.include_router(admin_scraping.router, prefix="/api/v1/admin", tags=["Administración de Conocimiento"])



# Rutas del Panel Administrativo para Configuración Global (Políticas PDF)
app.include_router(configuracion.router, prefix="/api/v1/admin/configuracion", tags=["Configuración"])
# ------------------------------------------------------------------------------
# Endpoints Base de Monitoreo (Healthchecks)
# ------------------------------------------------------------------------------
@app.get("/", tags=["Health"])
async def root():
    return {
        "status": "online",
        "servicio": "Orquestador PQR Universidad de Cundinamarca",
        "motor_db": "PostgreSQL Async",
        "rutas_activas": ["/api/v1/chat/enviar", "/api/v1/admin/conocimiento/iniciar"]
    }