# ==============================================================================
# Servicio de Documentos Adicionales (PDF y Word) - Agente PQR
# ------------------------------------------------------------------------------
# Convierte un PDF o un .docx en fragmentos autocontenidos (con título y fuente)
# listos para el dataset de Dify. Reutiliza el mismo fragmentador que el crawler.
# Solo usa librerías que ya están instaladas en el contenedor (pypdf, python-docx).
# ==============================================================================

import io
import re
from collections import Counter
from typing import List, Tuple

from app.services.scraper_local import fragmentar_pagina, MARCA_FRAGMENTO

EXTENSIONES_VALIDAS = (".pdf", ".docx")
MAX_BYTES = 25 * 1024 * 1024

PATRON_TITULO_LEGAL = re.compile(
    r"^(ART[ÍI]CULO|CAP[ÍI]TULO|T[ÍI]TULO|SECCI[ÓO]N|PAR[ÁA]GRAFO)\s+[\dIVXLC\w\.\-ºo°]*", re.I)
PATRON_NUM_PAGINA = re.compile(r"^(p[áa]g(ina)?\.?\s*)?\d{1,4}(\s*(de|/)\s*\d{1,4})?$", re.I)


class DocumentoError(Exception):
    """Error legible para el administrador."""


# ------------------------------------------------------------------------------
# PDF
# ------------------------------------------------------------------------------
def _zona_borde(lineas: List[str]) -> List[str]:
    """Primeras y últimas 3 líneas no vacías de una página (donde viven encabezados y pies)."""
    utiles = [x.strip() for x in lineas if x.strip()]
    return utiles[:3] + utiles[-3:]


def _lineas_repetidas(paginas: List[List[str]]) -> set:
    """Encabezados/pies que se repiten en muchas páginas (logo, 'Página x de y', código del documento).
    Solo se miran los bordes de la página: el texto del cuerpo nunca se elimina."""
    if len(paginas) < 3:
        return set()
    cuenta = Counter()
    for lineas in paginas:
        for l in set(_zona_borde(lineas)):
            cuenta[l] += 1
    minimo = max(3, int(len(paginas) * 0.4))
    return {l for l, n in cuenta.items() if n >= minimo and len(l) < 140}


def _pdf_a_markdown(data: bytes) -> Tuple[str, int]:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise DocumentoError("Falta la librería pypdf en el servidor.")
    try:
        lector = PdfReader(io.BytesIO(data))
        if lector.is_encrypted:
            try:
                lector.decrypt("")
            except Exception:
                raise DocumentoError("El PDF está protegido con contraseña.")
        paginas = []
        for p in lector.pages:
            try:
                t = p.extract_text() or ""
            except Exception:
                t = ""
            paginas.append(t.replace("\x00", "").splitlines())
    except DocumentoError:
        raise
    except Exception as e:
        raise DocumentoError(f"No se pudo leer el PDF: {e}")

    total_chars = sum(len(l) for pag in paginas for l in pag)
    if total_chars < 80:
        raise DocumentoError("El PDF no tiene texto extraíble (parece un escaneo). "
                             "Pendiente para la versión con OCR; por ahora conviértelo a Word o PDF con texto.")

    repetidas = _lineas_repetidas(paginas)
    parrafos, actual = [], []

    def cerrar():
        nonlocal actual
        if actual:
            parrafos.append(" ".join(actual).strip())
            actual = []

    for lineas in paginas:
        borde = set(_zona_borde(lineas))
        for crudo in lineas:
            l = re.sub(r"\s+", " ", crudo).strip()
            if not l or (l in repetidas and crudo.strip() in borde) or PATRON_NUM_PAGINA.match(l):
                if not l:
                    # línea vacía: posible fin de párrafo si el anterior terminó con punto
                    if actual and re.search(r"[.:;]$", actual[-1]):
                        cerrar()
                continue
            if PATRON_TITULO_LEGAL.match(l):
                cerrar()
                if len(l) < 90 and not l.endswith((".", ":", ";", ",")):
                    parrafos.append("## " + l)      # línea que es solo el título del artículo
                else:
                    actual.append(l)                # el artículo trae su texto en la misma línea
                continue
            # un guion al final de línea une la palabra partida
            if actual and actual[-1].endswith("-") and l[:1].islower():
                actual[-1] = actual[-1][:-1] + l
                continue
            actual.append(l)
            # párrafo muy largo: cortar al terminar una oración
            if sum(len(x) for x in actual) > 700 and re.search(r"[.;:]$", l):
                cerrar()
    cerrar()
    # los títulos legales ("ARTÍCULO 5.") pasan a encabezado para abrir sección
    salida = []
    for p in parrafos:
        if p.startswith("## "):
            salida.append(p)
        elif PATRON_TITULO_LEGAL.match(p) and len(p) < 120:
            salida.append("## " + p)
        else:
            salida.append(p)
    return "\n\n".join(salida), len(paginas)


# ------------------------------------------------------------------------------
# Word (.docx)
# ------------------------------------------------------------------------------
def _docx_a_markdown(data: bytes) -> Tuple[str, int]:
    try:
        import docx
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ImportError:
        raise DocumentoError("Falta la librería python-docx en el servidor.")
    try:
        d = docx.Document(io.BytesIO(data))
    except Exception as e:
        raise DocumentoError(f"No se pudo leer el Word (¿es un .docx válido? Los .doc antiguos no sirven): {e}")

    bloques = []
    cuerpo = d.element.body
    for hijo in cuerpo.iterchildren():
        etiqueta = hijo.tag.rsplit("}", 1)[-1]
        if etiqueta == "p":
            p = Paragraph(hijo, d)
            texto = p.text.strip()
            if not texto:
                continue
            estilo = (p.style.name if p.style is not None else "") or ""
            m = re.match(r"(?:Heading|T[íi]tulo)\s*(\d)", estilo, re.I)
            if m:
                bloques.append("#" * min(int(m.group(1)) + 1, 4) + " " + texto)   # h1 del doc -> "##"
            elif estilo.lower().startswith(("title", "título")):
                bloques.append("## " + texto)
            elif "list" in estilo.lower() or "lista" in estilo.lower():
                bloques.append("- " + texto)
            elif PATRON_TITULO_LEGAL.match(texto) and len(texto) < 120:
                bloques.append("## " + texto)
            else:
                bloques.append(texto)
        elif etiqueta == "tbl":
            tabla = Table(hijo, d)
            filas = []
            for fila in tabla.rows:
                celdas, vistas = [], set()
                for c in fila.cells:
                    if id(c._tc) in vistas:       # celdas combinadas
                        continue
                    vistas.add(id(c._tc))
                    celdas.append(re.sub(r"\s+", " ", c.text).strip())
                filas.append(celdas)
            if not filas:
                continue
            encabezado = filas[0]
            if len(filas) > 1 and all(encabezado):
                for fila in filas[1:]:
                    pares = [f"{h}: {v}" for h, v in zip(encabezado, fila) if v]
                    if pares:
                        bloques.append("- " + "; ".join(pares))
            else:
                for fila in filas:
                    linea = " | ".join(x for x in fila if x)
                    if linea:
                        bloques.append("- " + linea)
    texto = "\n\n".join(bloques)
    if len(texto) < 40:
        raise DocumentoError("El documento Word no tiene texto.")
    return texto, 0


# ------------------------------------------------------------------------------
# API pública del servicio
# ------------------------------------------------------------------------------
def nombre_limpio(nombre_archivo: str) -> str:
    base = re.sub(r"\.(pdf|docx)$", "", nombre_archivo.strip(), flags=re.I)
    base = re.sub(r"[_]+", " ", base)
    return re.sub(r"\s+", " ", base).strip() or "Documento"


def convertir_documento(nombre_archivo: str, contenido: bytes, titulo: str = None) -> dict:
    """
    Devuelve:
      nombre, tipo, caracteres, paginas, fragmentos (int), texto_fragmentado (para Dify),
      muestra (primeros fragmentos, para la vista previa), advertencias (lista)
    """
    ext = "." + nombre_archivo.lower().rsplit(".", 1)[-1] if "." in nombre_archivo else ""
    if ext not in EXTENSIONES_VALIDAS:
        raise DocumentoError("Formato no soportado. Por ahora solo PDF y Word (.docx).")
    if len(contenido) == 0:
        raise DocumentoError("El archivo está vacío.")
    if len(contenido) > MAX_BYTES:
        raise DocumentoError("El archivo supera 25 MB.")

    if ext == ".pdf":
        markdown, paginas = _pdf_a_markdown(contenido)
    else:
        markdown, paginas = _docx_a_markdown(contenido)

    titulo = (titulo or nombre_limpio(nombre_archivo)).strip()
    fragmentos = fragmentar_pagina(titulo, "", markdown)
    if not fragmentos:
        raise DocumentoError("No se pudo generar contenido útil del documento.")

    advertencias = []
    if len(markdown) < 600:
        advertencias.append("El documento tiene muy poco texto; revisa la vista previa.")
    mayor = max(len(f) for f in fragmentos)
    if mayor > 1900:
        advertencias.append("Hay fragmentos muy largos; Dify podría partirlos.")

    return {
        "nombre": titulo,
        "tipo": ext.strip("."),
        "caracteres": len(markdown),
        "paginas": paginas,
        "fragmentos": len(fragmentos),
        "texto_fragmentado": f"\n\n{MARCA_FRAGMENTO}\n\n".join(fragmentos) + "\n",
        "muestra": fragmentos[:3],
        "advertencias": advertencias,
    }