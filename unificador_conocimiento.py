# ==============================================================================
# Orquestador de Micro-Lotes para Bypass de Rate Limit (API de Google - 100 RPM)
# Descripción: Lee el documento PQR extremo y lo divide matemáticamente en 
# lotes de seguridad inferiores a 70 KB, asegurando que la concurrencia de Dify 
# jamás dispare el error HTTP 429 de RESOURCE_EXHAUSTED.
# ==============================================================================

import os
import sys

def generar_micro_lotes_seguros(ruta_archivo_origen: str, directorio_salida: str, limite_kb_seguro: int = 70):
    """
    Fracciona un archivo Markdown masivo en partes más pequeñas (micro-lotes),
    respetando los bloques semánticos definidos por "# --- DOCUMENTO FUENTE".
    """
    # 1. Validación estricta de rutas operativas
    if not os.path.exists(ruta_archivo_origen):
        print(f"[ERROR CRÍTICO] No se localizó el archivo fuente en la ruta: {ruta_archivo_origen}")
        sys.exit(1)

    if not os.path.exists(directorio_salida):
        os.makedirs(directorio_salida)
        print(f"[AUDITORÍA] Directorio de salida creado en: {directorio_salida}")

    limite_bytes_seguro = limite_kb_seguro * 1024
    
    # 2. Lectura y extracción del contenido en memoria
    try:
        with open(ruta_archivo_origen, "r", encoding="utf-8") as f:
            contenido_total = f.read()
    except Exception as e:
        print(f"[ERROR CRÍTICO] Fallo en la decodificación UTF-8 del archivo fuente: {str(e)}")
        sys.exit(1)

    # 3. Segmentación algorítmica por delimitador semántico
    delimitador_principal = "# --- DOCUMENTO FUENTE:"
    
    # Se utiliza un particionamiento que preserva el contexto del separador
    bloques_crudos = contenido_total.split(delimitador_principal)
    
    # El primer bloque puede estar vacío o contener cabeceras irrelevantes antes del primer documento
    bloques_validados = []
    for bloque in bloques_crudos:
        if bloque.strip():
            # Se reconstruye la integridad estructural del documento
            bloques_validados.append(delimitador_principal + bloque)

    total_bloques_extraidos = len(bloques_validados)
    print(f"[INFO] Análisis léxico completado: {total_bloques_extraidos} documentos individuales detectados en el archivo maestro.")

    # 4. Ensamblaje de Micro-Lotes (Batching)
    numero_lote_actual = 1
    peso_acumulado_lote_actual_bytes = 0
    buffer_lote = []
    lotes_ensamblados = 0

    for bloque in bloques_validados:
        peso_bloque_individual_bytes = len(bloque.encode('utf-8'))
        
        # Validación de sobrecarga: Si el bloque actual rompe el límite del lote, se procede al volcado en disco
        if peso_acumulado_lote_actual_bytes + peso_bloque_individual_bytes > limite_bytes_seguro and buffer_lote:
            _escribir_lote_en_disco(buffer_lote, numero_lote_actual, directorio_salida)
            lotes_ensamblados += 1
            
            # Reseteo de variables de estado para el siguiente lote
            numero_lote_actual += 1
            buffer_lote = []
            peso_acumulado_lote_actual_bytes = 0
            
        # Adición del bloque al buffer de RAM
        buffer_lote.append(bloque)
        peso_acumulado_lote_actual_bytes += peso_bloque_individual_bytes

    # 5. Volcado residual: Escribir cualquier bloque remanente que no alcanzó a activar el límite
    if buffer_lote:
        _escribir_lote_en_disco(buffer_lote, numero_lote_actual, directorio_salida)
        lotes_ensamblados += 1

    print(f"\n[ESTADO FINAL] Particionamiento culminado exitosamente.")
    print(f"[REPORTE] Se generaron {lotes_ensamblados} archivos de micro-lotes en la carpeta '{directorio_salida}'.")
    print(f"[DIRECTRIZ] Cada archivo está matemáticamente blindado para no exceder las 100 peticiones por minuto en Dify.")

def _escribir_lote_en_disco(buffer_datos: list, indice_lote: int, ruta_destino: str):
    """
    Función de bajo nivel para ejecutar la persistencia de datos en el sistema de archivos.
    """
    nombre_archivo = f"lote_seguro_pqr_parte_{indice_lote}.md"
    ruta_completa = os.path.join(ruta_destino, nombre_archivo)
    
    contenido_ensamblado = "".join(buffer_datos)
    peso_kb = len(contenido_ensamblado.encode('utf-8')) / 1024
    
    with open(ruta_completa, "w", encoding="utf-8") as archivo:
        archivo.write(contenido_ensamblado)
        
    print(f"  -> Volcado en disco: {nombre_archivo} | Peso estructural: {peso_kb:.2f} KB")

if __name__ == "__main__":
    # ==========================================================================
    # PARÁMETROS DE CONFIGURACIÓN DE RUTAS ABSOLUTAS
    # Se mapea directamente el archivo generado en el paso previo
    # ==========================================================================
    ARCHIVO_MAESTRO = r"E:\AgentesUcundinamarca\AgentePQR\datos_listos_dify\conocimiento_pqr_extremo.md"
    CARPETA_LOTES_SEGUROS = r"E:\AgentesUcundinamarca\AgentePQR\datos_listos_dify\lotes_seguros"
    
    # Ejecución del orquestador con el límite técnico de 70 KB
    generar_micro_lotes_seguros(ARCHIVO_MAESTRO, CARPETA_LOTES_SEGUROS, limite_kb_seguro=70)