# ==============================================================================
# Cliente Administrativo API Dify (Gestión de Conocimiento)  -  v2.4
# ------------------------------------------------------------------------------
# Un solo dataset de Dify con DOS tipos de documentos:
#   * Web:        "conocimiento_optimizado_<fecha>.txt"  -> lo crea y reemplaza el crawler
#   * Adicional:  "DOC__<nombre>.txt"                    -> los sube el administrador (PDF/Word)
# El crawler SOLO toca los documentos web; los adicionales nunca se borran por un crawl.
# ==============================================================================

import os
import json
import logging
import httpx

logger = logging.getLogger(__name__)

DIFY_URL = os.getenv("DIFY_API_BASE_URL", "https://api.dify.ai/v1")
DATASET_KEY = os.getenv("DIFY_DATASET_API_KEY", "")
DATASET_ID = os.getenv("DIFY_DATASET_ID", "")

# Debe ser IDÉNTICO a MARCA_FRAGMENTO de scraper_local.py
SEPARADOR_FRAGMENTO = "<<<FRAGMENTO>>>"

PREFIJO_WEB = "conocimiento_optimizado_"
PREFIJO_DOC = "DOC__"


class DifyError(Exception):
    """Error legible para mostrar al administrador."""


def _headers() -> dict:
    return {"Authorization": f"Bearer {DATASET_KEY}"}


def _verificar_credenciales():
    if not DATASET_KEY or not DATASET_ID:
        raise DifyError("Faltan DIFY_DATASET_API_KEY o DIFY_DATASET_ID en el archivo .env del backend.")


def _reglas_procesamiento() -> dict:
    return {
        "indexing_technique": "high_quality",
        "process_rule": {
            "mode": "custom",
            "rules": {
                "pre_processing_rules": [
                    # No colapsar saltos de línea: conservan la estructura del fragmento
                    {"id": "remove_extra_spaces", "enabled": False},
                    {"id": "remove_urls_emails", "enabled": False},
                ],
                "segmentation": {
                    "separator": SEPARADOR_FRAGMENTO,
                    # Dify mide este límite en CARACTERES al cortar; con 1000 partía los fragmentos
                    # largos y dejaba las colas sin cabecera. 2000 cubre el fragmento máximo (~1700).
                    "max_tokens": 2000,
                    "chunk_overlap": 0,
                },
            },
        },
    }


def _mensaje_http(e: httpx.HTTPStatusError) -> str:
    try:
        detalle = e.response.json().get("message") or e.response.text
    except Exception:
        detalle = e.response.text
    return f"Dify respondió {e.response.status_code}: {str(detalle)[:300]}"


# ------------------------------------------------------------------------------
# Operaciones sobre documentos (usadas por el panel de documentos adicionales)
# ------------------------------------------------------------------------------
async def listar_documentos(client: httpx.AsyncClient) -> list:
    """Devuelve TODOS los documentos del dataset (recorre las páginas)."""
    docs, pagina = [], 1
    while True:
        r = await client.get(
            f"{DIFY_URL}/datasets/{DATASET_ID}/documents",
            headers=_headers(), params={"page": pagina, "limit": 100},
        )
        r.raise_for_status()
        cuerpo = r.json()
        docs += cuerpo.get("data", [])
        if not cuerpo.get("has_more"):
            break
        pagina += 1
    return docs


async def listar_documentos_adicionales() -> list:
    _verificar_credenciales()
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            todos = await listar_documentos(client)
    except httpx.HTTPStatusError as e:
        raise DifyError(_mensaje_http(e))
    except httpx.HTTPError as e:
        raise DifyError(f"No se pudo conectar con Dify: {e}")
    salida = []
    for d in todos:
        nombre = d.get("name", "")
        if nombre.startswith(PREFIJO_DOC):
            salida.append({
                "id": d.get("id"),
                "nombre": nombre[len(PREFIJO_DOC):].rsplit(".", 1)[0],
                "estado": d.get("indexing_status"),
                "habilitado": d.get("enabled", True),
                "palabras": d.get("word_count"),
                "fragmentos": d.get("segment_count"),
                "creado": d.get("created_at"),
            })
    return salida


def nombre_archivo_documento(nombre: str) -> str:
    seguro = "".join(c if (c.isalnum() or c in " -_.()") else "_" for c in nombre).strip()
    return f"{PREFIJO_DOC}{seguro}.txt"


async def subir_documento_adicional(nombre: str, texto_fragmentado: str) -> dict:
    """Crea un documento nuevo. Falla si ya existe uno con ese nombre."""
    _verificar_credenciales()
    archivo = nombre_archivo_documento(nombre)
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            existentes = await listar_documentos(client)
            if any(d.get("name") == archivo for d in existentes):
                raise DifyError(f"Ya existe un documento llamado '{nombre}'. Usa 'Reemplazar'.")
            r = await client.post(
                f"{DIFY_URL}/datasets/{DATASET_ID}/document/create_by_file",
                headers=_headers(),
                data={"data": json.dumps(_reglas_procesamiento())},
                files={"file": (archivo, texto_fragmentado.encode("utf-8"), "text/plain")},
            )
            r.raise_for_status()
            return (r.json().get("document") or {})
    except httpx.HTTPStatusError as e:
        raise DifyError(_mensaje_http(e))
    except httpx.HTTPError as e:
        raise DifyError(f"No se pudo conectar con Dify: {e}")


async def reemplazar_documento_adicional(doc_id: str, nombre: str, texto_fragmentado: str) -> dict:
    """Sustituye el contenido de un documento existente (mismo id)."""
    _verificar_credenciales()
    archivo = nombre_archivo_documento(nombre)
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            r = await client.post(
                f"{DIFY_URL}/datasets/{DATASET_ID}/documents/{doc_id}/update_by_file",
                headers=_headers(),
                data={"data": json.dumps(_reglas_procesamiento())},
                files={"file": (archivo, texto_fragmentado.encode("utf-8"), "text/plain")},
            )
            r.raise_for_status()
            return (r.json().get("document") or {})
    except httpx.HTTPStatusError as e:
        raise DifyError(_mensaje_http(e))
    except httpx.HTTPError as e:
        raise DifyError(f"No se pudo conectar con Dify: {e}")


async def eliminar_documento_adicional(doc_id: str) -> None:
    _verificar_credenciales()
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Seguridad: solo se pueden borrar documentos adicionales desde el panel
            todos = await listar_documentos(client)
            objetivo = next((d for d in todos if d.get("id") == doc_id), None)
            if not objetivo or not objetivo.get("name", "").startswith(PREFIJO_DOC):
                raise DifyError("Ese documento no es un documento adicional o no existe.")
            r = await client.delete(f"{DIFY_URL}/datasets/{DATASET_ID}/documents/{doc_id}", headers=_headers())
            r.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise DifyError(_mensaje_http(e))
    except httpx.HTTPError as e:
        raise DifyError(f"No se pudo conectar con Dify: {e}")


# ------------------------------------------------------------------------------
# Sincronización del corpus web (crawler)
# ------------------------------------------------------------------------------
async def sincronizar_documento_dify(ruta_archivo: str, log_callback) -> bool:
    """
    1. Sube el corpus web nuevo.
    2. Solo si la subida funcionó, borra los corpus web ANTERIORES.
       Los documentos adicionales (prefijo DOC__) y cualquier otro documento se respetan.
    """
    if not DATASET_KEY or not DATASET_ID:
        log_callback("[DIFY API] IGNORADO: Faltan credenciales DIFY_DATASET_API_KEY o DIFY_DATASET_ID en el entorno.")
        return False

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            log_callback(f"[DIFY API] Consultando documentos en Dataset ID: {DATASET_ID}")
            existentes = await listar_documentos(client)
            ids_web_antiguos = [d["id"] for d in existentes
                                if d.get("name", "").startswith(PREFIJO_WEB) and d.get("id")]
            n_adicionales = sum(1 for d in existentes if d.get("name", "").startswith(PREFIJO_DOC))
            log_callback(f"[DIFY API] Corpus web anteriores: {len(ids_web_antiguos)} | "
                         f"documentos adicionales protegidos: {n_adicionales}")

            log_callback("[DIFY API] Subiendo nuevo corpus fragmentado...")
            # IMPORTANTE: se sube como .txt. Con .md Dify usa su lector de Markdown, que corta en
            # cada encabezado (#) y en cada línea "---" e ignora el separador personalizado.
            nombre_archivo = os.path.splitext(os.path.basename(ruta_archivo))[0] + ".txt"
            with open(ruta_archivo, "rb") as f:
                res = await client.post(
                    f"{DIFY_URL}/datasets/{DATASET_ID}/document/create_by_file",
                    headers=_headers(),
                    data={"data": json.dumps(_reglas_procesamiento())},
                    files={"file": (nombre_archivo, f, "text/plain")},
                )
            res.raise_for_status()
            nuevo_id = (res.json().get("document") or {}).get("id")

            for doc_id in ids_web_antiguos:
                if doc_id == nuevo_id:
                    continue
                log_callback(f"[DIFY API] Eliminando corpus web obsoleto: {doc_id}")
                r = await client.delete(f"{DIFY_URL}/datasets/{DATASET_ID}/documents/{doc_id}", headers=_headers())
                if r.status_code >= 400:
                    log_callback(f"[DIFY API] Aviso: no se pudo borrar {doc_id} (HTTP {r.status_code}).")

            log_callback("[DIFY API] ¡ÉXITO! Base de conocimiento sincronizada e indexando en Dify.")
            return True

    except Exception as e:
        log_callback(f"[DIFY API ERROR] Fallo durante la sincronización: {str(e)}")
        logger.error(f"Error Dify Admin: {str(e)}")
        return False