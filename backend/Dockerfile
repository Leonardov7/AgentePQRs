# ==============================================================================
# Dockerfile - Agente PQR (Backend FastAPI)
# Descripción: Empaquetado ligero para el orquestador en Python
# ==============================================================================

# 1. Usar imagen base optimizada para contenedores
FROM python:3.11-slim

# 2. Establecer el directorio de trabajo interno
WORKDIR /app

# 3. Copiar únicamente el archivo de requerimientos primero (optimiza caché de Docker)
COPY requirements.txt .

# 4. Instalar dependencias con tiempo de espera extendido para evitar fallos de red
RUN pip install --no-cache-dir --default-timeout=1000 --retries=10 -r requirements.txt

# Instalar los navegadores binarios de Playwright y sus dependencias de sistema operativo (Debian/Ubuntu)
RUN playwright install chromium
RUN playwright install-deps

# 5. Copiar el código fuente de la aplicación
COPY ./app ./app

# 6. Exponer el puerto de comunicación
EXPOSE 8000

# 7. Comando de arranque de ASGI Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]