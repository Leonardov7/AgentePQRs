# ==============================================================================
# Controlador de Configuración - Agente PQR
# Descripción: Gestión de parámetros globales (Enlace de datos y Umbral IA)
# ==============================================================================

import os
import json
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

router = APIRouter()

ASSETS_DIR = "assets"
os.makedirs(ASSETS_DIR, exist_ok=True)
CONFIG_PATH = os.path.join(ASSETS_DIR, "configuracion.json")

class ConfiguracionGlobal(BaseModel):
    url_politicas: str = None
    umbral_rag: float = None

@router.post("/global", status_code=status.HTTP_200_OK)
async def actualizar_configuracion(datos: ConfiguracionGlobal):
    try:
        config_data = {}
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        
        if datos.url_politicas is not None:
            config_data["url_politicas"] = datos.url_politicas
        if datos.umbral_rag is not None:
            config_data["umbral_rag"] = datos.umbral_rag
        
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
            
        return {"estado": "exito", "mensaje": "Configuración guardada correctamente."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/global")
async def obtener_configuracion():
    config_data = {
        "url_politicas": "https://www.ucundinamarca.edu.co/proteccion-de-datos-personales/",
        "umbral_rag": 35.0
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                config_data.update(data)
        except:
            pass
    return config_data

@router.get("/politicas")
async def redirigir_politicas():
    url = "https://www.ucundinamarca.edu.co/proteccion-de-datos-personales/"
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                url = data.get("url_politicas", url)
        except:
            pass
    return RedirectResponse(url=url, status_code=307)