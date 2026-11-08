import os

def empaquetar_proyecto(directorio_raiz, archivo_salida):
    # Detección estricta: Si la ruta CONTIENE alguna de estas carpetas, se ignora todo.
    carpetas_prohibidas = [
        'node_modules', 'venv', 'env', '__pycache__', '.git', 
        '.vscode', '.idea', 'build', 'dist', 'postgres_data', 
        'datos_listos_dify', 'public'
    ]
    
    # Extensiones de archivos que NO son código fuente
    excluir_exts = {'.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.zip', '.mp4', '.sqlite3', '.pyc', '.md', '.xlsx', '.exe', '.lock'}

    print(f"Empaquetando código desde: {os.path.abspath(directorio_raiz)}")
    
    with open(archivo_salida, 'w', encoding='utf-8') as f_out:
        for raiz, dirs, archivos in os.walk(directorio_raiz):
            # Filtro agresivo: Elimina las carpetas prohibidas antes de entrar
            dirs[:] = [d for d in dirs if d not in carpetas_prohibidas]
            
            # Filtro secundario: Si la ruta actual por alguna razón se coló (ej. subcarpetas)
            ruta_separada = os.path.normpath(raiz).split(os.sep)
            if any(prohibida in ruta_separada for prohibida in carpetas_prohibidas):
                continue
                
            for archivo in archivos:
                # Evitar extensiones no deseadas, locks, logs, o el archivo de salida
                if any(archivo.endswith(ext) for ext in excluir_exts):
                    continue
                if archivo.endswith('package-lock.json') or archivo == os.path.basename(archivo_salida):
                    continue
                
                ruta_completa = os.path.join(raiz, archivo)
                
                f_out.write(f"\n{'='*80}\n")
                f_out.write(f"ARCHIVO: {ruta_completa}\n")
                f_out.write(f"{'='*80}\n\n")
                
                try:
                    with open(ruta_completa, 'r', encoding='utf-8') as f_in:
                        f_out.write(f_in.read())
                except Exception as e:
                    f_out.write(f"[Error leyendo archivo: {e}]\n")

if __name__ == '__main__':
    empaquetar_proyecto('.', 'codigo_consolidado.txt')
    print("Proyecto empaquetado exitosamente en 'codigo_consolidado.txt'")