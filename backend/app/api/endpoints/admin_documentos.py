# ==============================================================================
# Controlador de Documentos Adicionales (PDF / Word) - Agente PQR
# Rutas finales:  /api/v1/admin/conocimiento/documentos/...
# ==============================================================================

import logging
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.services import dify_admin_client as dify
from app.services.documentos_servicio import convertir_documento, DocumentoError, MAX_BYTES

router = APIRouter(prefix="/conocimiento/documentos", tags=["Documentos Adicionales"])
logger = logging.getLogger(__name__)


async def _leer_archivo(archivo: UploadFile) -> bytes:
    contenido = await archivo.read(MAX_BYTES + 1)
    return contenido


async def _convertir(archivo: UploadFile, titulo: Optional[str]) -> dict:
    contenido = await _leer_archivo(archivo)
    try:
        # pypdf / python-docx son bloqueantes: se ejecutan fuera del bucle asíncrono
        return await run_in_threadpool(convertir_documento, archivo.filename or "", contenido, titulo)
    except DocumentoError as e:
        raise HTTPException(status_code=422, detail=str(e))


def _resumen(r: dict) -> dict:
    return {k: r[k] for k in ("nombre", "tipo", "caracteres", "paginas", "fragmentos", "advertencias")}


@router.get("")
async def listar():
    try:
        return {"documentos": await dify.listar_documentos_adicionales()}
    except dify.DifyError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/previsualizar")
async def previsualizar(archivo: UploadFile = File(...), titulo: Optional[str] = Form(None)):
    """Convierte el archivo y muestra qué se enviaría, SIN subir nada a Dify."""
    r = await _convertir(archivo, titulo)
    return {**_resumen(r), "muestra": r["muestra"]}


@router.post("")
async def subir(archivo: UploadFile = File(...), titulo: Optional[str] = Form(None)):
    r = await _convertir(archivo, titulo)
    try:
        doc = await dify.subir_documento_adicional(r["nombre"], r["texto_fragmentado"])
    except dify.DifyError as e:
        raise HTTPException(status_code=409 if "Ya existe" in str(e) else 502, detail=str(e))
    return {"mensaje": "Documento enviado a Dify. La indexación tarda unos segundos.",
            "id": doc.get("id"), **_resumen(r)}


@router.put("/{doc_id}")
async def reemplazar(doc_id: str, archivo: UploadFile = File(...), titulo: Optional[str] = Form(None)):
    """Reemplaza el contenido de UN documento. `titulo` debe ser el nombre actual para conservarlo."""
    r = await _convertir(archivo, titulo)
    try:
        doc = await dify.reemplazar_documento_adicional(doc_id, r["nombre"], r["texto_fragmentado"])
    except dify.DifyError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"mensaje": "Documento reemplazado. La indexación tarda unos segundos.",
            "id": doc.get("id") or doc_id, **_resumen(r)}


@router.delete("/{doc_id}")
async def eliminar(doc_id: str):
    try:
        await dify.eliminar_documento_adicional(doc_id)
    except dify.DifyError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"mensaje": "Documento eliminado."}