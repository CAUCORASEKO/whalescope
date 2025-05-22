# whalescope.py 

import sys
import subprocess
import json
import argparse
import os
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='whalescope.log',
    filemode='a'
)

def update_data(mode, start_date=None, end_date=None):
    logger = logging.getLogger(__name__)
    logger.info(f"Iniciando actualización de datos para modo '{mode}'")
    
    # Usar rutas absolutas basadas en el directorio del script
    base_dir = os.path.dirname(os.path.abspath(__file__))
    scripts = {
        'bitcoin': os.path.join(base_dir, 'bitcoin.py'),
        'blackrock': os.path.join(base_dir, 'blackrock.py'),
        'lido': os.path.join(base_dir, 'lido_staking.py')
    }
    output_files = {
        'bitcoin': os.path.join(base_dir, 'output.json'),
        'blackrock': os.path.join(base_dir, 'blackrock_output.json'),
        'lido': os.path.join(base_dir, 'lido_output.json')
    }

    script = scripts.get(mode)
    output_file = output_files.get(mode)

    if not script:
        logger.error(f"Modo '{mode}' no reconocido")
        return {"error": f"Modo '{mode}' no reconocido"}

    if not os.path.exists(script):
        logger.error(f"Script '{script}' no encontrado")
        return {"error": f"Script '{script}' no encontrado"}

    logger.info(f"Ejecutando {script}")
    try:
        python_command = os.path.join(base_dir, 'venv', 'bin', 'python3')
        if not os.path.exists(python_command):
            python_command = 'python3'
            logger.warning(f"Python del entorno virtual no encontrado, usando {python_command}")
        
        # Construir comando
        cmd = [python_command, script]
        if start_date and end_date:
            cmd.extend(['--start-date', start_date, '--end-date', end_date])
        
        logger.info(f"Comando completo: {' '.join(cmd)}")
        
        # Ejecutar comando con entorno limpio
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1"}  # Forzar salida sin buffer
        )
        
        # Registrar salida completa
        logger.info(f"Stdout de {script}: {result.stdout}")
        if result.stderr:
            logger.error(f"Stderr de {script}: {result.stderr}")
        
        try:
            # Limpiar stdout y parsear
            stdout_clean = result.stdout.strip()
            if not stdout_clean:
                logger.error(f"Stdout está vacío para {script}")
                return {"error": "Stdout está vacío"}
            
            data = json.loads(stdout_clean)
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Datos guardados en {output_file}")
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Error al parsear la salida de {script}: {e}")
            logger.error(f"Contenido de stdout: '{result.stdout}'")
            return {"error": f"Invalid JSON output from {script}: {e}"}
    except subprocess.CalledProcessError as e:
        logger.error(f"Error al ejecutar {script}: {e}")
        logger.error(f"Salida de error: {e.stderr}")
        return {"error": f"Error executing {script}: {e.stderr}"}
    except Exception as e:
        logger.error(f"Error inesperado al ejecutar {script}: {e}")
        return {"error": f"Unexpected error: {str(e)}"}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WhaleScope data updater")
    parser.add_argument('mode', choices=['bitcoin', 'blackrock', 'lido', 'all'], help="Mode to run")
    parser.add_argument('--start-date', type=str, help="Start date for data (YYYY-MM-DD)")
    parser.add_argument('--end-date', type=str, help="End date for data (YYYY-MM-DD)")
    args = parser.parse_args()

    if args.mode == 'all':
        modes = ['bitcoin', 'blackrock', 'lido']
    else:
        modes = [args.mode]

    results = {}
    for mode in modes:
        result = update_data(mode, args.start_date, args.end_date)
        results[mode] = result

    # Imprimir solo JSON en stdout
    print(json.dumps(results[args.mode] if args.mode != 'all' else results))
    sys.stdout.flush()