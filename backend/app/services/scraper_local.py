# ==============================================================================
# Motor de Extracción Local v2 (Playwright + BeautifulSoup)
# ------------------------------------------------------------------------------
# Cambios respecto a v1 (ver comentarios "POR QUÉ" en cada bloque):
#   1. Cookies limpias en cada página  -> evita el error "Size of a request header
#      field exceeds server limit" que arruinaba el 94 % del corpus.
#   2. Una sola carga por página (v1 la cargaba dos veces).
#   3. Normalización y filtro de URLs (sin ?gaceta_download, sin /en/, sin paginación).
#   4. Detección de páginas de error / vacías: NUNCA se guardan como conocimiento.
#   5. Freno de seguridad: si hay 8 errores seguidos el rastreo se detiene y avisa.
#   6. Prioridad de rastreo: trámites, admisiones, derechos pecuniarios, etc. primero.
#   7. Sitemap.xml como fuente de URLs (descubre páginas que el menú no enlaza).
#   8. Extracción de texto de PDF y DOCX enlazados (normativa, reglamentos).
#   9. Aplanado genérico de tablas (v1 descartaba en silencio tablas de 4+ columnas).
#  10. (v2.1) Certificado TLS: el sitio sirve una cadena incompleta y las descargas de
#      PDF fallaban con "unable to verify the first certificate".
#  11. (v2.1) Documentos: se descartan listados de personas (admitidos, inscritos...) y
#      se priorizan circulares, calendario, reglamentos e instructivos.
#  12. (v2.1) Enlaces a documentos ya no se corrompen (markdownify escapaba "_" como "\\_").
#  13. (v2.1) Páginas con contenido idéntico bajo varias URLs se guardan una sola vez.
#  14. (v2.1) Se quita el ruido de noticias (comentarios, calificaciones, "relacionadas").
#  15. (v2.1) Título de página fiable y sin contextos de banner en las listas.
#  16. (v2.1) Índice sintético "Oferta académica por sede" construido desde las fichas.
#  17. (v2.2) Portal de noticias fuera del conocimiento, en 3 capas:
#      a) URL: /agencia-de-noticias, /noticias, /eventos, /agenda... ni se visitan;
#      b) sitemap: se omiten los sitemaps de "entradas" (posts) de WordPress;
#      c) contenido: una entrada de WordPress (noticia) se descarta SALVO que sea un aviso
#         de servicio vigente (matrícula, grados, descuentos, instructivos...). Todo lo
#         descartado/conservado queda listado en las estadísticas para auditarlo.
#  18. (v2.3) FRAGMENTACIÓN PROPIA: cada fragmento es una unidad completa (pregunta+respuesta,
#      sección con su título y URL). Dify partía el texto en CADA línea en blanco y dejaba
#      las preguntas separadas de sus respuestas y sin fuente. Ver generar_corpus_optimizado.
#  19. (v2.3) Deduplicación EXACTA entre páginas (reemplaza la semántica 0.88, que podía borrar
#      párrafos parecidos pero con datos distintos). La semántica queda como opción.
# La interfaz pública NO cambia: rastrear_dominio(...) y generar_corpus_optimizado(...)
# ==============================================================================

import asyncio
import html as html_lib
import io
import logging
import re
from collections import deque
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup, NavigableString
from markdownify import markdownify as md
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OrquestadorPQR/2.0"

# ------------------------------------------------------------------------------
# CONFIGURACIÓN AJUSTABLE
# ------------------------------------------------------------------------------
EXT_DOC_EXTRAIBLE = (".pdf", ".docx")
EXT_DOC_OTROS = (".doc", ".xls", ".xlsx", ".xlsm", ".ppt", ".pptx")
EXT_IGNORAR = (".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico", ".zip", ".rar",
               ".7z", ".mp4", ".mp3", ".avi", ".mov", ".css", ".js", ".woff", ".woff2", ".xml")

# Parámetros de URL que SÍ cambian el contenido de la página. Todo lo demás se descarta.
PARAMS_UTILES = {"sede", "p", "page_id"}

PATRON_RUTAS_EXCLUIDAS = re.compile(
    r"/(wp-admin|wp-json|wp-content|wp-includes|wp-login\.php|xmlrpc\.php|feed|comments|"
    r"author|tag|trackback)(/|$)", re.I)
PATRON_PAGINACION = re.compile(r"/page/\d+/?$", re.I)
PATRON_INGLES = re.compile(r"^/en(/|$)", re.I)

# Rutas que más importan a un asesor de PQR: se rastrean primero.
PATRON_PRIORITARIO = re.compile(
    r"(admision|inscrip|matricul|pecuniari|derechos|calendario|reglamento|estatuto|pqr|"
    r"peticion|queja|reclamo|atencion|ciudadan|tramite|servicio|sede|pregrado|posgrado|"
    r"programa|bienestar|apoyo|beca|financ|grado|homolog|reintegro|transfer|certific|"
    r"frecuente|contacto|registro|aspirante|estudiante|egresad|graduad|docente|biblioteca)", re.I)
# Contenido que cambia a diario y aporta poco a un asesor: se rastrea al final.
PATRON_BAJA_PRIORIDAD = re.compile(
    r"(noticia|agenda|evento|gaceta|convocatoria|boletin|galeria|video|podcast|categor)", re.I)

# Textos típicos de una página de error (se buscan SOLO en páginas cortas).
FIRMAS_ERROR = (
    "size of a request header field exceeds server limit",
    "your browser sent a request that this server could not understand",
    "request header or cookie too large", "request entity too large",
    "request-uri too large", "400 bad request", "403 forbidden", "404 not found",
    "página no encontrada", "pagina no encontrada", "service unavailable",
    "502 bad gateway", "504 gateway time-out", "access denied",
)
# Documentos que NUNCA deben entrar al conocimiento: listados de personas (datos personales).
PATRON_DOC_EXCLUIDO = re.compile(
    r"(admitid|listado|resultado|seleccionad|inscrit|matriculad|nomina|ganador|beneficiari)", re.I)
PATRON_DOC_ALTA = re.compile(
    r"(circular|calendario|reglamento|instructivo|derechos|pecuniari|matricula|guia|manual|"
    r"procedimiento|requisito|tramite|estatuto|cuota|descuento|apoyo)", re.I)
PATRON_DOC_BAJA = re.compile(r"(resoluciones-men|registro-calificado|/rc[-_]|snies)", re.I)

# Líneas de ruido de las noticias de WordPress
PATRON_CORTE_COMENTARIOS = re.compile(r"^#{1,6}\s*Deja un comentario.*$", re.I | re.M)
LINEAS_RUIDO = [
    r"^Cancelar respuesta$", r"^Califica esta noticia$", r"^\**\d(\.\d)?\**\s*/\s*5$", r"^·$",
    r"^\d+\s+calificaci[oó]n(es)?$", r"^Compartir( en .*)?$",
]
# --- Portal de noticias -------------------------------------------------------
# Secciones que son "portal" (información del día a día, no conocimiento permanente).
PATRON_PORTAL_NOTICIAS = re.compile(
    r"^/(index\.php/)?(agencia-de-noticias|noticias|noticia|eventos|evento|agenda|prensa|"
    r"galeria|multimedia|blog|category|categoria|boletin|boletines)(/|$)", re.I)
# Sitemaps de WordPress/Yoast que solo listan entradas, no páginas.
PATRON_SITEMAP_ENTRADAS = re.compile(
    r"(posts-post|post-sitemap|posts-noticia|news-sitemap|category|tag|author|attachment|"
    r"wp-sitemap-taxonomies|wp-sitemap-users)", re.I)
# Marcas del plantilla de "entrada" de WordPress (también la llevan algunas páginas de servicio,
# por eso por sí sola NO basta para descartar).
MARCAS_ENTRADA = ("califica esta noticia", "deja un comentario")
CLASES_BODY_ENTRADA = ("single-post", "single-noticia", "single-noticias", "type-post")
# Un aviso de entrada se conserva si trata de un servicio/trámite permanente y es reciente.
PATRON_AVISO_SERVICIO = re.compile(
    r"(matr[ií]cula|\bcuotas?\b|inscripci|\bgrados?\b|descuento|calendario|requisitos?|tr[aá]mites?|"
    r"\bpagos?\b|certificad|reintegro|cancelaci|homologa|apoyo financiero|\bbecas?\b|icetex|"
    r"pecuniari|reglamento|plataforma|instructivo|cartilla|gu[ií]a\b|derechos|macroproceso|proceso gesti)", re.I)
MAX_EDAD_AVISO_DIAS = 365
MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
         "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
MIN_CHARS_PAGINA = 60          # menos que esto = página vacía (se registra como "pobre")
MAX_ERRORES_SEGUIDOS = 8       # freno de seguridad
REINICIAR_CONTEXTO_CADA = 150  # recrea el navegador cada N páginas (libera memoria)

PATRON_RUIDO_DOM = re.compile(
    r"(^|[-_])(cookie|cookies|breadcrumb|breadcrumbs|sidebar|share|sharing|social|popup|"
    r"modal|newsletter|skip-link|screen-reader-text|comment|comments|respond|related|rating|"
    r"calific|post-navigation|nav-links|author-box)([-_]|$)", re.I)
SELECTORES_CONTENIDO = ["main", "[role=main]", "article", "#content", "#main-content",
                        "#main", ".entry-content", ".post-content", ".page-content"]


# ==============================================================================
# 1. URLs: normalización, filtro y prioridad
# ==============================================================================
def _dominio_canonico(netloc: str) -> str:
    netloc = netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def normalizar_url(url: str, dominio: str) -> Optional[str]:
    """Devuelve la URL en forma canónica o None si no pertenece al sitio.
    POR QUÉ: v1 trataba /p/3 y /p/3?gaceta_download=7 como páginas distintas; así
    nacieron las 4.667 URLs basura. Aquí se quitan los parámetros que no cambian
    el contenido, y las variantes colapsan en una sola."""
    try:
        p = urlparse(url.strip())
    except ValueError:
        return None
    if p.scheme not in ("http", "https") or _dominio_canonico(p.netloc) != dominio:
        return None
    ruta = re.sub(r"/{2,}", "/", p.path or "/")
    if len(ruta) > 300:
        return None
    query = urlencode(sorted((k, v) for k, v in parse_qsl(p.query) if k.lower() in PARAMS_UTILES))
    ruta = ruta.rstrip("/") or "/"
    return urlunparse((p.scheme, p.netloc.lower(), ruta, "", query, ""))


def clasificar_url(url: str, excluir_ingles: bool = True, excluir_noticias: bool = True) -> Optional[str]:
    """'pagina', 'documento' o None (descartar)."""
    ruta = urlparse(url).path.lower()
    if ruta.endswith(EXT_DOC_EXTRAIBLE):      # se evalúa ANTES de excluir /wp-content/
        return None if PATRON_DOC_EXCLUIDO.search(ruta) else "documento"
    if "%20" in ruta:                         # enlaces mal formados (texto pegado en el href)
        return None
    if ruta.endswith(EXT_DOC_OTROS + EXT_IGNORAR):
        return None
    if PATRON_RUTAS_EXCLUIDAS.search(ruta) or PATRON_PAGINACION.search(ruta):
        return None
    if excluir_noticias and PATRON_PORTAL_NOTICIAS.match(ruta):
        return None
    if excluir_ingles and PATRON_INGLES.match(ruta):
        return None
    return "pagina"


def _huella(markdown: str) -> str:
    import hashlib
    cuerpo = re.sub(r"^#.*\n+", "", markdown.strip(), count=1)   # ignora el título
    return hashlib.md5(re.sub(r"\s+", " ", cuerpo.lower()).encode("utf-8")).hexdigest()


def prioridad_url(url: str) -> int:
    """0 = alta, 1 = normal, 2 = baja."""
    ruta = urlparse(url).path
    if PATRON_BAJA_PRIORIDAD.search(ruta):
        return 2
    return 0 if PATRON_PRIORITARIO.search(ruta) else 1


def prioridad_documento(url: str) -> int:
    ruta = urlparse(url).path
    if PATRON_DOC_BAJA.search(ruta):
        return 3
    if PATRON_DOC_ALTA.search(ruta):
        return 0
    if re.search(r"acuerdo|resolucion|comunicado", ruta, re.I):
        return 1
    return 2


def _fecha_publicacion(texto: str):
    """Lee 'Fecha de publicación: 12 de noviembre de 2026'. Devuelve datetime.date o None."""
    import datetime as _dt
    m = re.search(r"Fecha de publicaci[oó]n:?\s*(\d{1,2})\s+de\s+([A-Za-zñáéíóú]+)\s+(?:de\s+|del\s+)?(\d{4})", texto, re.I)
    if not m or m.group(2).lower() not in MESES:
        return None
    try:
        return _dt.date(int(m.group(3)), MESES[m.group(2).lower()], int(m.group(1)))
    except ValueError:
        return None


def es_entrada_wordpress(html: str) -> List[str]:
    """Señales de que la página es una 'entrada' (noticia) y no una página institucional."""
    senales = []
    bajo = html.lower()
    m = re.search(r"<body[^>]*class=[\"']([^\"']*)", bajo)
    if m and any(c in m.group(1).split() or c in m.group(1) for c in CLASES_BODY_ENTRADA):
        senales.append("clase_body")
    senales += [f"texto:{x}" for x in MARCAS_ENTRADA if x in bajo]
    return senales


def decidir_entrada(url: str, titulo: str, texto_plano: str, hoy=None):
    """Para una entrada de WordPress devuelve (conservar: bool, motivo: str).
    Se conserva solo si es un aviso de servicio permanente y RECIENTE; el resto es noticia."""
    import datetime as _dt
    hoy = hoy or _dt.date.today()
    slug = urlparse(url).path.replace("-", " ").replace("/", " ")
    if not PATRON_AVISO_SERVICIO.search(f"{titulo} {slug}"):
        return False, "noticia"
    fecha = _fecha_publicacion(texto_plano[:800])
    if fecha and (hoy - fecha).days > MAX_EDAD_AVISO_DIAS:
        return False, f"aviso_vencido({fecha.isoformat()})"
    return True, "aviso_de_servicio"


def evaluar_calidad(status: int, texto_plano: str) -> Optional[str]:
    """Devuelve el motivo de rechazo o None si la página sirve como conocimiento."""
    if status >= 400:
        return f"http_{status}"
    texto = texto_plano.strip()
    if len(texto) < 1500 and any(f in texto.lower() for f in FIRMAS_ERROR):
        return "pagina_de_error"
    if len(texto) < MIN_CHARS_PAGINA:
        return "poco_contenido"
    return None


# ==============================================================================
# 2. HTML -> Markdown
# ==============================================================================
def _borrar(el) -> None:
    try:
        if not getattr(el, "decomposed", False):
            el.decompose()
    except Exception:
        pass


def _elegir_contenedor(soup: BeautifulSoup):
    for sel in SELECTORES_CONTENIDO:
        el = soup.select_one(sel)
        if el is not None and len(el.get_text(" ", strip=True)) >= 150:
            return el
    return soup.body or soup


def _limpiar_contenedor(c) -> None:
    """POR QUÉ: v1 borraba TODOS los <header> y <form>, perdiendo a veces el título (h1)
    o páginas enteras envueltas en un <form>. Aquí se borra solo lo que es ruido."""
    for t in c.find_all(["script", "style", "noscript", "iframe", "svg", "template", "nav",
                         "footer", "aside", "textarea"]):
        _borrar(t)
    # Botones, listas desplegables e inputs: se conserva su TEXTO. Muchas fichas muestran
    # sus datos dentro de esos controles (acordeones, selectores de sede) y borrarlos
    # dejaba los títulos de campo sin valor ("Créditos Académicos: <vacío>").
    for inp in c.find_all("input"):
        valor = (inp.get("value") or "").strip()
        if valor and len(valor) > 2 and (inp.get("type") or "text") in ("text", "readonly"):
            inp.replace_with(NavigableString(f" {valor} "))
        else:
            _borrar(inp)
    for o in c.find_all("option"):
        o.insert_after(NavigableString("\n"))
    for ctrl in c.find_all(["button", "select", "option", "label"]):
        ctrl.unwrap()
    for f in c.find_all("form"):
        if len(f.get_text(" ", strip=True)) < 400:
            _borrar(f)
    for h in c.find_all("header"):
        if not h.find(["h1", "h2", "h3"]):
            _borrar(h)
    for el in c.find_all(class_=PATRON_RUIDO_DOM):
        _borrar(el)
    for el in c.find_all(id=PATRON_RUIDO_DOM):
        _borrar(el)


def _titulo_limpio(titulo_h1: str, titulo_head: str) -> str:
    """El <title> de la página es más fiable que el primer <h1>, que a veces es el
    nombre del sitio o un banner. Se descartan las partes que solo nombran a la universidad."""
    def limpiar(t):
        return re.sub(r"\s+", " ", (t or "").strip())
    for fuente in (titulo_head, titulo_h1):
        partes = [limpiar(x) for x in re.split(r"\s[-|–—]\s", fuente or "") if limpiar(x)]
        utiles = [x for x in partes if not re.fullmatch(r"(universidad de cundinamarca|ucundinamarca)", x, re.I)]
        if utiles:
            return utiles[0]
    return ""


def _limpiar_ruido_texto(markdown: str) -> str:
    m = PATRON_CORTE_COMENTARIOS.search(markdown)
    if m:                                   # lo que sigue a "Deja un comentario" son noticias relacionadas
        markdown = markdown[:m.start()]
    for patron in LINEAS_RUIDO:
        markdown = re.sub(patron, "", markdown, flags=re.M | re.I)
    return re.sub(r"\n{3,}", "\n\n", markdown).strip()


def html_a_markdown(html: str, url_pagina: str, dominio: str, documentos: set):
    """Devuelve (titulo, markdown, texto_plano). Reescribe los enlaces a documentos
    como 'texto [documento: URL]' para que el asesor virtual pueda ofrecerlos."""
    soup = BeautifulSoup(html, "html.parser")
    titulo_head = soup.title.get_text(strip=True) if soup.title else ""
    contenedor = _elegir_contenedor(soup)
    _limpiar_contenedor(contenedor)

    h1 = contenedor.find("h1")
    titulo = _titulo_limpio(h1.get_text(" ", strip=True) if h1 else "", titulo_head)

    for a in contenedor.find_all("a", href=True):
        absoluta = urljoin(url_pagina, a["href"]).split("#")[0]
        ruta = urlparse(absoluta).path.lower()
        if ruta.endswith(EXT_DOC_EXTRAIBLE + EXT_DOC_OTROS):
            texto = a.get_text(" ", strip=True) or unquote(ruta.rsplit("/", 1)[-1])
            a.replace_with(NavigableString(f"{texto} [documento: {absoluta}] "))
            norm = normalizar_url(absoluta, dominio)
            if norm and clasificar_url(norm) == "documento":
                documentos.add(norm)
        else:
            if a.next_sibling is not None and not isinstance(a.next_sibling, NavigableString):
                a.insert_after(NavigableString(" "))   # enlaces pegados: evita "Gaceta 1Gaceta 2"
            a.unwrap()

    texto_plano = contenedor.get_text(" ", strip=True)
    markdown = md(str(contenedor), heading_style="ATX", strip=["a", "img"], bullets="-",
                  escape_underscores=False, escape_asterisks=False).strip()
    markdown = _limpiar_ruido_texto(markdown)
    markdown = aplanar_semantica_markdown(markdown)
    markdown = re.sub(r"^#\s*Universidad de Cundinamarca\s*\n+", "", markdown, flags=re.I)
    if titulo and not re.match(rf"^#\s*{re.escape(titulo)}\s*$", markdown.split("\n", 1)[0], re.I):
        markdown = f"# {titulo}\n\n{markdown}"
    return titulo, markdown, texto_plano


# ------------------------------------------------------------------------------
# Aplanado semántico de tablas y listas
# ------------------------------------------------------------------------------
def _es_separador_tabla(linea: str) -> bool:
    return bool(re.match(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?$", linea.strip()))


def _celdas(linea: str) -> List[str]:
    return [c.strip() for c in linea.strip().strip("|").split("|")]


def _aplanar_bloque_tabla(bloque: List[str], contexto: str) -> List[str]:
    """POR QUÉ: v1 solo entendía tablas de 2 o 3 columnas y descartaba las demás SIN
    avisar (p. ej. una tabla de valores de matrícula). Ahora cada fila se vuelve una
    oración 'Columna: valor; ...' que el buscador semántico puede recuperar."""
    header, filas = None, []
    if len(bloque) >= 2 and _es_separador_tabla(bloque[1]):
        header, filas = _celdas(bloque[0]), [_celdas(l) for l in bloque[2:]]
    else:
        filas = [_celdas(l) for l in bloque if not _es_separador_tabla(l)]

    salida = []
    prefijo = f"[Tabla: {contexto}] " if contexto else ""
    nombres = [h.lower() for h in header] if header else []
    es_sede_programa = bool(header) and len(header) == 2 and \
        any("sede" in n for n in nombres) and any("programa" in n for n in nombres)

    for fila in filas:
        if not any(fila):
            continue
        if es_sede_programa:
            sede = fila[nombres.index(next(n for n in nombres if "sede" in n))]
            prog = fila[nombres.index(next(n for n in nombres if "programa" in n))]
            if sede and prog:
                salida.append(f"El programa de {prog} se oferta en la sede de {sede}.")
            continue
        if header:
            pares = [f"{h}: {v}" for h, v in zip(header, fila) if v and h]
            extra = [v for v in fila[len(header):] if v]
            partes = pares + extra
        else:
            partes = [v for v in fila if v]
        if partes:
            salida.append(f"{prefijo}" + "; ".join(partes) + ".")
    return salida


def aplanar_semantica_markdown(markdown_crudo: str) -> str:
    lineas = markdown_crudo.split("\n")
    resultado: List[str] = []
    encabezado_actual = ""
    bloque_tabla: List[str] = []

    def vaciar_tabla():
        nonlocal bloque_tabla
        if bloque_tabla:
            resultado.extend(_aplanar_bloque_tabla(bloque_tabla, encabezado_actual))
            resultado.append("")
            bloque_tabla = []

    for linea in lineas:
        limpia = linea.strip()
        if re.match(r"^\|.*\|$", limpia):
            bloque_tabla.append(limpia)
            continue
        vaciar_tabla()

        m = re.match(r"^(#{1,6})\s+(.+)", limpia)
        if m:
            # Un h1 suele ser un banner ("Tu bienestar, nuestra prioridad"), no un contexto útil.
            encabezado_actual = m.group(2).strip() if len(m.group(1)) >= 2 else ""
            resultado.append(limpia)
            continue
        m = re.match(r"^[-*]\s+(.+)", limpia)
        if m:
            item = m.group(1).strip()
            resultado.append(f"- [Contexto: {encabezado_actual}] {item}" if encabezado_actual else limpia)
            continue
        resultado.append(limpia)
    vaciar_tabla()
    return re.sub(r"\n{3,}", "\n\n", "\n".join(resultado)).strip()


# ==============================================================================
# 3. Documentos (PDF / DOCX)
# ==============================================================================
def _reflujo_texto(t: str) -> str:
    """Une líneas partidas por el maquetado del PDF y quita números de página sueltos."""
    t = t.replace("\r", "")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"^\s*\d{1,3}\s*$", "", t, flags=re.M)
    t = re.sub(r"-\n(?=[a-záéíóúñ])", "", t)
    t = re.sub(r"(?<![.:;!?\n])\n(?=[a-záéíóúñ(])", " ", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def _texto_desde_pdf(datos: bytes) -> str:
    from pypdf import PdfReader
    lector = PdfReader(io.BytesIO(datos))
    if lector.is_encrypted:
        try:
            lector.decrypt("")
        except Exception:
            return ""
    paginas = []
    for pg in lector.pages:
        try:
            paginas.append(pg.extract_text() or "")
        except Exception:
            continue
    return _reflujo_texto("\n\n".join(paginas))


def _texto_desde_docx(datos: bytes) -> str:
    import docx
    doc = docx.Document(io.BytesIO(datos))
    partes = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    for tabla in doc.tables:
        for fila in tabla.rows:
            celdas = [c.text.strip() for c in fila.cells if c.text.strip()]
            if celdas:
                partes.append("; ".join(celdas) + ".")
    return _reflujo_texto("\n\n".join(partes))


async def _extraer_documento(context, url: str, max_bytes: int = 15 * 1024 * 1024):
    """Devuelve (texto, motivo_de_fallo)."""
    try:
        resp = await context.request.get(url, timeout=60000)
        if not resp.ok:
            return "", f"http_{resp.status}"
        datos = await resp.body()
        if len(datos) > max_bytes:
            return "", "demasiado_grande"
        texto = _texto_desde_pdf(datos) if urlparse(url).path.lower().endswith(".pdf") \
            else _texto_desde_docx(datos)
        if len(texto) < 200:
            return "", "sin_texto_extraible (posible escaneo: requiere OCR)"
        return texto, None
    except Exception as e:
        return "", f"excepcion: {e}"


# ==============================================================================
# 4. Navegador
# ==============================================================================
async def _bloquear_recursos_pesados(route):
    if route.request.resource_type in {"image", "media", "font"}:
        await route.abort()
    else:
        await route.continue_()


async def _nuevo_contexto(browser):
    # ignore_https_errors: el servidor de la universidad entrega la cadena de certificados
    # incompleta (el navegador la completa solo; el cliente HTTP de Playwright no).
    # Solo se visita el dominio configurado, así que el riesgo es bajo.
    contexto = await browser.new_context(user_agent=USER_AGENT, ignore_https_errors=True)
    await contexto.route("**/*", _bloquear_recursos_pesados)
    return contexto


# Enlaces de la página. Con excluir_noticias se omiten los que están dentro de widgets de
# noticias/eventos (carruseles de "últimas noticias" en portada y sedes). Salvaguarda: si el
# filtro eliminaría más del 80 % de los enlaces, se ignora (probablemente un contenedor demasiado amplio).
_JS_ENLACES = """(excluir) => {
  const todos = Array.from(document.querySelectorAll('a[href]'));
  if (!excluir) return todos.map(e => e.href);
  const SEL = '[class*="noticia"],[class*="news"],[id*="noticia"],[id*="news"],[class*="agencia"],[class*="evento"],[class*="agenda"]';
  const ok = todos.filter(a => { const c = a.closest(SEL); return !c || ['BODY','HTML','MAIN'].includes(c.tagName); });
  return (todos.length && ok.length < todos.length * 0.2) ? todos.map(e => e.href) : ok.map(e => e.href);
}"""


async def _cargar_pagina(context, url: str, excluir_noticias: bool = True) -> Dict[str, Any]:
    """UNA sola carga por página: de aquí salen el contenido Y los enlaces.
    (v1 cargaba cada página dos veces, duplicando el tráfico y las cookies.)"""
    page = await context.new_page()
    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        status = resp.status if resp else 0
        try:
            await page.wait_for_load_state("networkidle", timeout=6000)  # contenido dinámico
        except Exception:
            pass
        return {
            "status": status,
            "html": await page.content(),
            "titulo": await page.title(),
            "enlaces": await page.evaluate(_JS_ENLACES, excluir_noticias),
            "excepcion": None,
        }
    except Exception as e:
        return {"status": 0, "html": "", "titulo": "", "enlaces": [], "excepcion": str(e)}
    finally:
        await page.close()


async def _urls_desde_sitemap(context, url_base: str, excluir_noticias: bool = True) -> List[str]:
    p = urlparse(url_base)
    origen = f"{p.scheme}://{p.netloc}"
    pendientes = [f"{origen}/sitemap.xml", f"{origen}/wp-sitemap.xml", f"{origen}/sitemap_index.xml"]
    vistos, urls = set(), []
    while pendientes and len(vistos) < 40 and len(urls) < 8000:
        sm = pendientes.pop(0)
        if sm in vistos:
            continue
        vistos.add(sm)
        try:
            resp = await context.request.get(sm, timeout=20000)
            if not resp.ok:
                continue
            texto = await resp.text()
        except Exception:
            continue
        for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", texto, flags=re.S):
            loc = html_lib.unescape(loc)
            if loc.lower().endswith(".xml"):
                if excluir_noticias and PATRON_SITEMAP_ENTRADAS.search(loc):
                    continue            # sitemap de entradas/categorías: no es conocimiento
                pendientes.append(loc)
            else:
                urls.append(loc)
    return urls


# ==============================================================================
# 4b. Índice sintético: oferta académica por sede
# ==============================================================================
# Lugares de la universidad y su tipo. Ajustar aquí si se abre una nueva extensión.
LUGARES_UNIVERSIDAD = {
    "fusagasuga": ("Sede", "Fusagasugá"), "girardot": ("Seccional", "Girardot"),
    "ubate": ("Seccional", "Ubaté"), "facatativa": ("Extensión", "Facatativá"),
    "chia": ("Extensión", "Chía"), "soacha": ("Extensión", "Soacha"),
    "zipaquira": ("Extensión", "Zipaquirá"),
}


def _sin_tildes(t: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn").lower().strip()


def _lugares_en(texto: str) -> List[str]:
    plano = _sin_tildes(texto)
    return [k for k in LUGARES_UNIVERSIDAD if re.search(rf"\b{k}\b", plano)]


_PALABRAS_VACIAS = {"de", "del", "la", "el", "en", "y", "para", "profesional", "programa", "los", "las"}


def _clave_programa(nombre: str) -> str:
    """Clave para reconocer el mismo programa escrito de dos formas
    ('Profesional de Ciencias del Deporte' / 'Profesional en ciencias del deporte')."""
    tokens = [t for t in re.findall(r"[a-z0-9]+", _sin_tildes(nombre)) if t not in _PALABRAS_VACIAS]
    return " ".join(sorted(tokens))


def _nombre_programa(texto: str, pag: Dict[str, Any]) -> str:
    m = re.search(r"Denominaci[oó]n del Programa\s*\n+\s*([^\n#][^\n]*)", texto)
    if m and len(m.group(1).strip()) > 3:
        return m.group(1).strip().rstrip(".")
    if pag.get("titulo"):
        return pag["titulo"].strip()
    slug = pag["url"].rstrip("/").rsplit("/", 1)[-1].replace("-", " ")
    return slug[:1].upper() + slug[1:]


def generar_indice_oferta(paginas: List[Dict[str, Any]], url_base: str) -> Optional[Dict[str, Any]]:
    """Las páginas de sede cargan su lista de programas con JavaScript y quedan sin ella.
    La relación sede <-> programa se reconstruye con dos fuentes que SÍ se leen bien:
      1) la sección 'Lugar de desarrollo' de cada ficha de programa, y
      2) las páginas /pregrado?sede=... (títulos de programa por sede).
    No inventa nada: solo reordena datos presentes en el sitio."""
    por_sede = {k: {"pre": {}, "pos": {}} for k in LUGARES_UNIVERSIDAD}
    por_programa: Dict[tuple, Dict[str, Any]] = {}
    sin_lugar: List[str] = []

    def _mejor(a: str, b: str) -> str:   # prefiere la escritura con tildes/mayúsculas correctas
        return b if sum(ord(c) > 127 for c in b) + sum(c.isupper() for c in b) > \
            sum(ord(c) > 127 for c in a) + sum(c.isupper() for c in a) else a

    def registrar(nivel, nombre, lugar):
        clave = _clave_programa(nombre)
        prog = por_programa.setdefault((nivel, clave), {"nombre": nombre, "lugares": []})
        prog["nombre"] = _mejor(prog["nombre"], nombre)
        if lugar not in prog["lugares"]:
            prog["lugares"].append(lugar)

    for pag in paginas:
        if pag.get("tipo") != "pagina":
            continue
        texto = pag["markdown"].replace("**", "")
        m = re.search(r"/programas-(pregrado|posgrado)/", pag["url"])
        if m:
            nivel, nombre = m.group(1), _nombre_programa(texto, pag)
            sec = re.search(r"Lugar de desarrollo[^\n]*\n(.*?)(?=\n#{1,2}\s|\Z)", texto, re.S)
            lugares = _lugares_en(sec.group(1)) if sec else []
            if not lugares:   # respaldo: "158 créditos (Fusagasugá, Chía y Ubaté)"
                lugares = [k for par in re.findall(r"cr[eé]ditos\s*\(([^)]*)\)", texto, re.I) for k in _lugares_en(par)]
            if not lugares:
                sin_lugar.append(nombre)
            for lugar in lugares:
                registrar(nivel, nombre, lugar)
            continue
        m = re.search(r"/pregrado\?sede=sede_(\w+)", pag["url"])
        if m and _sin_tildes(m.group(1)) in LUGARES_UNIVERSIDAD:
            lugar = _sin_tildes(m.group(1))
            bloque = re.search(r"Nuestras facultades(.*?)(?=\n## |\Z)", texto, re.S)
            for h3 in re.findall(r"^###\s+(.+)$", bloque.group(1) if bloque else "", re.M):
                registrar("pregrado", h3.strip(), lugar)

    if not por_programa:
        return None

    for (nivel, clave), prog in por_programa.items():
        for lugar in prog["lugares"]:
            por_sede[lugar]["pre" if nivel == "pregrado" else "pos"][clave] = prog["nombre"]

    lineas = ["# Oferta académica por sede, extensión y seccional", "",
              "Resumen de en qué lugares se ofrece cada programa de la Universidad de Cundinamarca.", ""]
    for clave, (tipo, nombre_lugar) in sorted(LUGARES_UNIVERSIDAD.items(), key=lambda kv: kv[1][1]):
        d = por_sede[clave]
        if not (d["pre"] or d["pos"]):
            continue
        lineas.append(f"## {tipo} {nombre_lugar}")
        if d["pre"]:
            lineas.append(f"Programas de pregrado en {tipo} {nombre_lugar}: " + "; ".join(sorted(d["pre"].values())) + ".")
        if d["pos"]:
            lineas.append(f"Programas de posgrado en {tipo} {nombre_lugar}: " + "; ".join(sorted(d["pos"].values())) + ".")
        lineas.append("")
    lineas.append("## Dónde se ofrece cada programa")
    for (nivel, clave) in sorted(por_programa):
        prog = por_programa[(nivel, clave)]
        donde = ", ".join(f"{LUGARES_UNIVERSIDAD[k][0]} {LUGARES_UNIVERSIDAD[k][1]}" for k in prog["lugares"])
        lineas.append(f"El programa de {nivel} {prog['nombre']} se ofrece en: {donde}.")
        lineas.append("")
    if sin_lugar:
        logger.warning(f"[SCRAPER v2] Fichas sin 'Lugar de desarrollo' reconocible: {sin_lugar}")
    return {"url": url_base.rstrip("/") + "/pregrado", "titulo": "Oferta académica por sede",
            "markdown": "\n".join(lineas).strip(), "exito": True, "tipo": "indice"}


# ==============================================================================
# 5. Rastreo principal  (misma firma que v1 + parámetros opcionales)
# ==============================================================================
async def rastrear_dominio(url_base: str, limite_paginas: int = 50, job_id: str = None,
                           dict_estado: dict = None, incluir_documentos: bool = True,
                           max_documentos: int = 60, excluir_ingles: bool = True,
                           usar_sitemap: bool = True, pausa_s: float = 0.3,
                           generar_indice: bool = True, excluir_noticias: bool = True) -> List[Dict[str, Any]]:
    dominio = _dominio_canonico(urlparse(url_base).netloc)
    est = {"paginas_ok": 0, "duplicadas": 0, "noticias_descartadas": [], "avisos_conservados": [], "rechazadas": {}, "descartadas_por_filtro": 0, "documentos_ok": 0,
           "documentos_fallidos": {}, "contextos_reiniciados": 0, "abortado_por_errores": False,
           "muestras_pobres": []}
    paginas: List[Dict[str, Any]] = []
    visitadas, en_cola = set(), set()
    hashes_contenido: Dict[str, str] = {}
    colas = [deque(), deque(), deque()]
    documentos_pagina: set = set()      # enlaces a PDF/DOCX hallados dentro del HTML
    documentos_enlazados: List[str] = []
    docs_vistos: set = set()

    def encolar(crudo: str, forzar_prioridad: Optional[int] = None):
        norm = normalizar_url(crudo, dominio)
        if not norm:
            return
        tipo = clasificar_url(norm, excluir_ingles, excluir_noticias)
        if tipo is None:
            est["descartadas_por_filtro"] += 1
            return
        if tipo == "documento":
            if norm not in docs_vistos:
                docs_vistos.add(norm)
                documentos_enlazados.append(norm)
            return
        if norm in visitadas or norm in en_cola:
            return
        en_cola.add(norm)
        colas[prioridad_url(norm) if forzar_prioridad is None else forzar_prioridad].append(norm)

    def siguiente() -> Optional[str]:
        for q in colas:
            if q:
                return q.popleft()
        return None

    def reportar():
        if dict_estado is not None and job_id and job_id in dict_estado:
            dict_estado[job_id]["total_paginas"] = len(paginas)
            dict_estado[job_id]["estadisticas"] = est

    logger.info(f">>> [SCRAPER v2] Iniciando rastreo en: {url_base} (límite {limite_paginas})")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await _nuevo_contexto(browser)

        encolar(url_base, forzar_prioridad=0)
        if usar_sitemap:
            urls_sm = await _urls_desde_sitemap(context, url_base, excluir_noticias)
            logger.info(f"[SCRAPER v2] Sitemap: {len(urls_sm)} URLs descubiertas.")
            for u in urls_sm:
                encolar(u)

        intentos, errores_seguidos = 0, 0
        max_intentos = max(limite_paginas * 4, 50)

        while len(paginas) < limite_paginas and intentos < max_intentos:
            if dict_estado and job_id and dict_estado.get(job_id, {}).get("estado_trabajo") == "cancelled":
                logger.info("[SCRAPER v2] Rastreo abortado por solicitud del usuario.")
                break
            url = siguiente()
            if url is None:
                break
            visitadas.add(url)
            en_cola.discard(url)
            intentos += 1

            if intentos % REINICIAR_CONTEXTO_CADA == 0:
                await context.close()
                context = await _nuevo_contexto(browser)
                est["contextos_reiniciados"] += 1

            # --- Higiene de cookies (CAUSA RAÍZ del corpus roto) ---------------
            if intentos % 25 == 1:
                cookies = await context.cookies()
                peso = sum(len(c.get("name", "")) + len(c.get("value", "")) for c in cookies)
                logger.info(f"[diag] cookies acumuladas antes de limpiar: {len(cookies)} ({peso} bytes)")
            await context.clear_cookies()

            motivo, titulo, markdown, datos = None, "", "", {}
            for intento in (1, 2):
                datos = await _cargar_pagina(context, url, excluir_noticias)
                if datos["excepcion"]:
                    motivo = f"excepcion: {datos['excepcion'][:80]}"
                else:
                    docs_temp: set = set()
                    titulo, markdown, texto_plano = html_a_markdown(
                        datos["html"], url, dominio, docs_temp)
                    motivo = evaluar_calidad(datos["status"], texto_plano)
                    entrada_ok = None
                    if not motivo and excluir_noticias:
                        senales = es_entrada_wordpress(datos["html"])
                        if senales:
                            conservar, razon = decidir_entrada(url, titulo, texto_plano)
                            if not conservar:
                                motivo = f"noticia_excluida:{razon.split('(')[0]}"
                                est["noticias_descartadas"].append(f"{razon} | {url}")
                            else:
                                entrada_ok = url
                reintentable = motivo and (motivo.startswith("excepcion") or motivo == "pagina_de_error"
                                           or motivo.startswith("http_5"))
                if reintentable and intento == 1:
                    await context.clear_cookies()
                    await asyncio.sleep(1.5)
                    continue
                break

            # Los enlaces se aprovechan aunque la página sea "pobre" (p. ej. un índice),
            # pero NUNCA los de una página de error.
            # Tampoco se siguen los enlaces de una noticia descartada (suelen ser más noticias y adjuntos).
            if datos.get("status", 0) and datos["status"] < 400 and motivo != "pagina_de_error" \
                    and not (motivo or "").startswith("noticia_excluida"):
                for enlace in datos["enlaces"]:
                    encolar(enlace)

            if motivo and motivo.startswith("noticia_excluida"):
                est["rechazadas"][motivo] = est["rechazadas"].get(motivo, 0) + 1
                logger.info(f"[SCRAPER v2] Noticia excluida ({motivo}): {url}")
                reportar()
                await asyncio.sleep(pausa_s)
                continue                     # no cuenta como error ni suma enlaces de documentos
            if motivo:
                errores_seguidos += 1 if motivo != "poco_contenido" else 0
                est["rechazadas"][motivo] = est["rechazadas"].get(motivo, 0) + 1
                if motivo == "poco_contenido" and len(est["muestras_pobres"]) < 25:
                    est["muestras_pobres"].append(url)
                logger.warning(f"[SCRAPER v2] Rechazada ({motivo}): {url}")
                if errores_seguidos >= MAX_ERRORES_SEGUIDOS:
                    est["abortado_por_errores"] = True
                    logger.error(f"[SCRAPER v2] {errores_seguidos} errores seguidos: rastreo detenido "
                                 f"para no contaminar el corpus. Revisar bloqueo/cookies del sitio.")
                    break
            elif _huella(markdown) in hashes_contenido:
                errores_seguidos = 0
                est["duplicadas"] += 1
                logger.info(f"[SCRAPER v2] Duplicada de {hashes_contenido[_huella(markdown)]}: {url}")
            else:
                errores_seguidos = 0
                hashes_contenido[_huella(markdown)] = url
                documentos_pagina.update(docs_temp)   # los PDF de una noticia descartada no entran
                if entrada_ok:
                    est["avisos_conservados"].append(entrada_ok)
                est["paginas_ok"] += 1
                paginas.append({"url": url, "titulo": titulo, "markdown": markdown,
                                "exito": True, "tipo": "pagina"})
                logger.info(f"[{len(paginas)}/{limite_paginas}] OK: {url}")
            reportar()
            await asyncio.sleep(pausa_s)

        # --- Documentos (PDF/DOCX) ----------------------------------------------
        if incluir_documentos and not est["abortado_por_errores"]:
            for d in documentos_pagina:
                if d not in docs_vistos:
                    docs_vistos.add(d)
                    documentos_enlazados.append(d)
            documentos_enlazados.sort(key=prioridad_documento)
            for url_doc in documentos_enlazados[:max_documentos]:
                if dict_estado and job_id and dict_estado.get(job_id, {}).get("estado_trabajo") == "cancelled":
                    break
                await context.clear_cookies()
                texto, fallo = await _extraer_documento(context, url_doc)
                if fallo:
                    est["documentos_fallidos"][fallo] = est["documentos_fallidos"].get(fallo, 0) + 1
                    logger.warning(f"[SCRAPER v2] Documento omitido ({fallo}): {url_doc}")
                    continue
                nombre = re.sub(r"[-_]+", " ", unquote(urlparse(url_doc).path.rsplit("/", 1)[-1]).rsplit(".", 1)[0])
                paginas.append({"url": url_doc, "titulo": nombre, "exito": True, "tipo": "documento",
                                "markdown": f"# {nombre}\n\n{texto}"})
                est["documentos_ok"] += 1
                logger.info(f"[SCRAPER v2] Documento extraído ({len(texto)} chars): {url_doc}")
            reportar()

        await browser.close()

    if generar_indice:
        indice = generar_indice_oferta(paginas, url_base)
        if indice:
            paginas.append(indice)
            logger.info("[SCRAPER v2] Índice 'oferta académica por sede' generado.")

    logger.info(f">>> [SCRAPER v2] Fin. Páginas OK: {est['paginas_ok']} | documentos: {est['documentos_ok']} | "
                f"rechazadas: {est['rechazadas']} | filtradas: {est['descartadas_por_filtro']}")
    reportar()
    return paginas


# ==============================================================================
# FRAGMENTACIÓN Y DEDUPLICACIÓN DEL CORPUS  (v2.3)
# ------------------------------------------------------------------------------
# POR QUÉ: Dify, con separador "\n\n", convertía CADA párrafo en un fragmento. En la práctica
# el buscador recuperaba cosas como "Matrícula a cuotas" o "¿Cómo puedo solicitar el
# reingreso?" SIN su respuesta, y el modelo respondía inventando o diciendo "no sé".
# Ahora el corpus se entrega ya fragmentado: cada fragmento lleva título, URL y sección, y
# Dify solo corta en MARCA_FRAGMENTO (debe coincidir con SEPARADOR_FRAGMENTO de dify_admin_client).
# ==============================================================================
MARCA_FRAGMENTO = "<<<FRAGMENTO>>>"
MAX_CHARS_FRAGMENTO = 1400      # ~350 tokens: cabe de sobra en los 1000 de Dify
MIN_CHARS_FRAGMENTO = 450       # por debajo, se une con lo siguiente
UMBRAL_REPETIDO_CORTO = 3       # párrafo corto repetido en >= N páginas = relleno de plantilla
PATRON_ARTICULO = re.compile(r"^(ART[ÍI]CULO|Art[íi]culo|CAP[ÍI]TULO|Cap[íi]tulo|T[ÍI]TULO)\s+[\dIVXLC]+", re.U)


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", t.strip().lower())


def _es_encabezado(b: str):
    m = re.match(r"^(#{1,6})\s+(.*\S)", b)
    return (len(m.group(1)), m.group(2).strip()) if m else (0, "")


def _es_etiqueta(b: str) -> bool:
    """Bloque corto que NO se entiende solo y debe pegarse al siguiente: una pregunta
    ('¿Cómo solicito...?'), un rótulo ('Requisitos:') o un título de campo ('##### Créditos')."""
    if "\n" in b or len(b) > 220:
        return False
    nivel, _ = _es_encabezado(b)
    if nivel >= 4:
        return True
    if nivel:
        return False
    if b.startswith("¿") and b.rstrip().endswith("?"):
        return True
    return len(b) < 90 and b.rstrip().endswith(":")


def _partir_largo(texto: str, limite: int) -> List[str]:
    """Parte un bloque enorme por líneas y, si hace falta, por oraciones."""
    piezas, actual = [], ""
    unidades = []
    for linea in texto.split("\n"):
        if len(linea) > limite:
            unidades += re.split(r"(?<=[.;:!?])\s+", linea)
        else:
            unidades.append(linea)
    for u in unidades:
        if actual and len(actual) + len(u) + 1 > limite:
            piezas.append(actual.strip())
            actual = ""
        actual += (u if not actual else "\n" + u)
    if actual.strip():
        piezas.append(actual.strip())
    return piezas


PATRON_WIDGET_COMO = re.compile(r"^#{1,6}\s*¿(Para qué|Cuándo|Dónde|Qué|Cómo|Cuánto) como\?\s*$", re.I)
PATRON_SECCION_NOTICIAS = re.compile(r"^(últimas\s+)?(noticias|novedades|agenda|eventos|actualidad)\b", re.I)
PATRON_SOLO_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PATRON_TIP = re.compile(r"^Tip\s+\d+$", re.I)


def _quitar_ruido_bloques(bloques: List[str]) -> List[str]:
    """Quita lo que no sirve para responder PQR dentro de páginas útiles:
      - widget de la página ('¿Cómo como?', '¿Cuánto como?', ...);
      - secciones 'Noticias/Agenda/Eventos' (hasta el siguiente encabezado del mismo nivel o superior);
      - tarjetas de noticia (título + resumen + etiqueta + fecha AAAA-MM-DD);
      - tarjetas de 'Tip N' de bienestar."""
    # a) widget
    bloques = [b for b in bloques if not PATRON_WIDGET_COMO.match(b)]
    # b) secciones de noticias
    salida, saltar_nivel = [], 0
    for b in bloques:
        nivel, texto_h = _es_encabezado(b)
        if saltar_nivel:
            if nivel and nivel <= saltar_nivel:
                saltar_nivel = 0
            else:
                continue
        if nivel and PATRON_SECCION_NOTICIAS.match(texto_h):
            saltar_nivel = nivel
            continue
        salida.append(b)
    bloques = salida
    # c) tarjetas con fecha: borra hacia atrás hasta el encabezado de la tarjeta (máx. 4 bloques)
    quitar = set()
    for i, b in enumerate(bloques):
        es_fecha = PATRON_SOLO_FECHA.match(b.strip())
        es_tip = PATRON_TIP.match(b.strip())
        if not (es_fecha or es_tip):
            continue
        quitar.add(i)
        for j in range(i - 1, max(i - 5, -1), -1):
            nivel_j, _ = _es_encabezado(bloques[j])
            if 0 < nivel_j <= 2:            # encabezado de sección real: no es parte de la tarjeta
                break
            if len(bloques[j]) > 600:       # texto largo: no es una tarjeta
                break
            quitar.add(j)
            if nivel_j:                     # ### título de la tarjeta: llegamos al inicio
                break
    return [b for i, b in enumerate(bloques) if i not in quitar]


def fragmentar_pagina(titulo: str, url: str, markdown: str, max_chars: int = MAX_CHARS_FRAGMENTO,
                      min_chars: int = MIN_CHARS_FRAGMENTO) -> List[str]:
    """Devuelve fragmentos autocontenidos de una página."""
    cuerpo = re.sub(r"^#\s+.*\n+", "", markdown.strip(), count=1)      # el título va en la cabecera
    cuerpo = re.sub(r"^- \[Contexto: [^\]]*\]\s*", "- ", cuerpo, flags=re.M)  # la sección ya va en la cabecera
    bloques = [b.strip() for b in re.split(r"\n{2,}", cuerpo) if b.strip()]
    bloques = _quitar_ruido_bloques(bloques)

    # 1) Unidades: pega etiquetas/preguntas con el bloque siguiente. Los encabezados h1-h3 y los
    #    "Artículo N" abren sección.
    unidades, pendiente = [], ""
    for b in bloques:
        nivel, texto_h = _es_encabezado(b)
        if 0 < nivel <= 3 or PATRON_ARTICULO.match(b):
            if pendiente:
                unidades.append(("txt", pendiente.strip(), None)); pendiente = ""
            unidades.append(("sec", b if nivel else b, texto_h or b[:80]))
            continue
        if _es_etiqueta(b):
            pendiente += b + "\n"
            continue
        unidades.append(("txt", (pendiente + b).strip(), None)); pendiente = ""
    if pendiente:
        unidades.append(("txt", pendiente.strip(), None))

    # 2) Empaquetado en fragmentos de tamaño razonable, sin cortar una pregunta de su respuesta.
    fragmentos, actual, seccion_inicio, seccion_actual = [], [], "", ""

    def volcar():
        nonlocal actual, seccion_inicio
        texto = "\n\n".join(actual).strip()
        if texto:
            if url:
                cab = f"TÍTULO: {titulo}\nORIGEN_URL: {url}"
            else:
                cab = f"TÍTULO: {titulo}\nFUENTE: Documento institucional cargado por la universidad"
            if seccion_inicio and seccion_inicio != titulo:
                cab += f"\nSECCIÓN: {seccion_inicio}"
            fragmentos.append(f"{cab}\nCONTENIDO:\n{texto}")
        actual, seccion_inicio = [], seccion_actual

    expandidas = []
    for tipo, texto, nombre_sec in unidades:
        if tipo == "sec" and len(texto) > max_chars:
            piezas = _partir_largo(texto, max_chars)
            expandidas.append(("sec", piezas[0], nombre_sec))
            expandidas += [("txt", p, None) for p in piezas[1:]]
        else:
            expandidas.append((tipo, texto, nombre_sec))
    unidades = expandidas

    for tipo, texto, nombre_sec in unidades:
        if tipo == "sec":
            if actual and sum(map(len, actual)) >= min_chars:
                seccion_actual = nombre_sec; volcar(); seccion_actual = nombre_sec
                actual = [texto]; seccion_inicio = nombre_sec
                continue
            seccion_actual = nombre_sec
            if not actual:
                seccion_inicio = nombre_sec
            actual.append(texto)
            continue
        piezas = _partir_largo(texto, max_chars) if len(texto) > max_chars else [texto]
        for pieza in piezas:
            if actual and sum(map(len, actual)) + len(pieza) + 2 > max_chars:
                volcar()
                seccion_inicio = seccion_actual
            actual.append(pieza)
    volcar()
    # un título suelto sin contenido no es un fragmento
    return [f for f in fragmentos if len(f.split("CONTENIDO:\n", 1)[-1].strip()) >= 40]


def _titulo_de_registro(url: str, cuerpo: str) -> str:
    m = re.search(r"^#\s+(.+)$", cuerpo, re.M)
    if m and m.group(1).strip():
        return m.group(1).strip()
    return unquote(urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]).replace("-", " ").strip().capitalize() or url


def _leer_registros(texto_completo: str):
    partes = re.split(r"(INDICE_REGISTRO:\s+\d+\nORIGEN_URL:\s+.*?\n---)", texto_completo)
    registros = []
    for i in range(1, len(partes), 2):
        url = re.search(r"ORIGEN_URL:\s+(\S+)", partes[i]).group(1)
        cuerpo = (partes[i + 1] if i + 1 < len(partes) else "").strip()
        if cuerpo:
            registros.append((url, cuerpo))
    return registros


def _quitar_repetidos(registros):
    """Elimina relleno de plantilla y contenido idéntico entre páginas.
      - bloque CORTO (<160) repetido en >= UMBRAL_REPETIDO_CORTO páginas: se borra en todas;
      - bloque LARGO repetido en varias páginas: se conserva solo en la primera.
    Es deduplicación EXACTA (texto normalizado): nunca borra párrafos parecidos pero distintos."""
    from collections import defaultdict
    paginas_por_bloque = defaultdict(set)
    for url, cuerpo in registros:
        for b in re.split(r"\n{2,}", cuerpo):
            b = b.strip()
            if b and not _es_encabezado(b)[0]:
                paginas_por_bloque[_norm(b)].add(url)
    ya_vistos, salida = set(), []
    quitados = {"relleno": 0, "duplicado": 0}
    for url, cuerpo in registros:
        nuevos = []
        for b in re.split(r"\n{2,}", cuerpo):
            bs = b.strip()
            if not bs:
                continue
            if _es_encabezado(bs)[0]:
                nuevos.append(bs); continue
            clave, n = _norm(bs), len(paginas_por_bloque[_norm(bs)])
            if len(bs) < 160 and n >= UMBRAL_REPETIDO_CORTO:
                quitados["relleno"] += 1; continue
            if len(bs) >= 160 and n >= 2:
                if clave in ya_vistos:
                    quitados["duplicado"] += 1; continue
                ya_vistos.add(clave)
            nuevos.append(bs)
        salida.append((url, "\n\n".join(nuevos)))
    logger.info(f"[FRAGMENTADOR] Párrafos quitados: {quitados}")
    return salida


def _dedupe_semantico(registros, umbral: float):
    """OPCIONAL (usar_semantico=True). Es la deduplicación original; puede borrar párrafos
    parecidos con datos distintos (fechas, sedes), por eso ya no es el valor por defecto."""
    import numpy as np
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
    modelo = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    salida = []
    for url, cuerpo in registros:
        parrafos = [b.strip() for b in cuerpo.split("\n\n") if len(b.strip()) > 15]
        if len(parrafos) > 2:
            emb = modelo.encode(parrafos, convert_to_tensor=False)
            unicos, e_unicos = [], []
            for p, e in zip(parrafos, emb):
                if not e_unicos or np.max(cosine_similarity([e], e_unicos)[0]) < umbral:
                    unicos.append(p); e_unicos.append(e)
            parrafos = unicos
        salida.append((url, "\n\n".join(parrafos)))
    return salida


def generar_corpus_optimizado(texto_completo: str, umbral_similitud: float = 0.88,
                              usar_semantico: bool = False) -> str:
    """Convierte el corpus crudo (INDICE_REGISTRO/ORIGEN_URL) en fragmentos autocontenidos
    separados por MARCA_FRAGMENTO. Misma firma que antes; el archivo resultante se sube igual."""
    logger.info(">>> [FRAGMENTADOR] Limpiando, deduplicando y fragmentando el corpus...")
    registros = _leer_registros(texto_completo)
    if not registros:
        return texto_completo
    registros = [(u, _limpiar_heuristica_basica(c)) for u, c in registros]
    registros = _quitar_repetidos(registros)
    if usar_semantico:
        registros = _dedupe_semantico(registros, umbral_similitud)

    fragmentos, vistos = [], set()
    for url, cuerpo in registros:
        for f in fragmentar_pagina(_titulo_de_registro(url, cuerpo), url, cuerpo):
            huella = _norm(f.split("CONTENIDO:\n", 1)[-1])
            if huella in vistos:
                continue
            vistos.add(huella)
            fragmentos.append(f)
    tam = sorted(len(f) for f in fragmentos)
    logger.info(f">>> [FRAGMENTADOR] {len(registros)} páginas -> {len(fragmentos)} fragmentos "
                f"(mediana {tam[len(tam)//2] if tam else 0} caracteres, máx {tam[-1] if tam else 0}).")
    return f"\n\n{MARCA_FRAGMENTO}\n\n".join(fragmentos) + "\n"


def _limpiar_heuristica_basica(texto: str) -> str:
    texto = re.sub(r'-\s+\[Contexto:.*?\]\s+Inicio\n', '', texto, flags=re.IGNORECASE)
    patrones_cta = [
        r'^Ver más$', r'^Descargar$', r'^Inscríbete$', r'^Leer más$',
        r'^Ver perfil$', r'^Descargar plan rectoral$', r'^Ir a Autoevaluación$',
        r'^Ver más noticias relacionadas$', r'^Ver más información aquí$', r'^Descarga aquí.*$'
    ]
    for patron in patrones_cta:
        texto = re.sub(patron, '', texto, flags=re.MULTILINE | re.IGNORECASE)
    texto = re.sub(r'^(?P<linea>.{1,50})$\n+(?P=linea)', r'\g<linea>', texto, flags=re.MULTILINE)
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    return texto.strip()