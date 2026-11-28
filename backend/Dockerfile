# ==============================================================================
# Dockerfile - Agente PQR (Backend FastAPI)
# ==============================================================================

# 1. Imagen fija en Debian 12 (bookworm), la versión que Playwright soporta de forma estable
FROM python:3.11-slim-bookworm

WORKDIR /app

# 2. Librería del sistema que necesita el programa interno de Playwright
RUN apt-get update \
    && apt-get install -y --no-install-recommends libatomic1 \
    && rm -rf /var/lib/apt/lists/*

# 3. Dependencias de Python (se cachea mientras requirements.txt no cambie)
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=1000 --retries=10 -r requirements.txt

# 4. Chromium y sus librerías del sistema en UN solo paso
RUN playwright install --with-deps chromium

# 5. Código de la aplicación
COPY ./app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]