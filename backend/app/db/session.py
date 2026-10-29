# ==============================================================================
# Configuración de Base de Datos - Agente PQR
# Descripción: Motor asíncrono y gestor de sesiones de SQLAlchemy
# ==============================================================================

import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

# Obtener la URL de conexión desde las variables de entorno inyectadas por Docker
# Fallback local en caso de ejecutar fuera del contenedor
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+asyncpg://udec_admin:udec_password_secure_2026@localhost:5432/agente_pqr_db"
)

# Creación del motor asíncrono. 
# pool_size y max_overflow controlan la concurrencia de conexiones.
engine = create_async_engine(
    DATABASE_URL,
    echo=False, # Cambiar a True para ver las sentencias SQL puras en la consola durante depuración
    future=True,
    pool_size=20,
    max_overflow=10
)

# Fábrica de sesiones asíncronas
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Clase base de la cual heredarán todos los modelos ORM
Base = declarative_base()

# Dependencia para inyectar la sesión en los endpoints de FastAPI
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()