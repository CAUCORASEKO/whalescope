import sys
import subprocess
import json
import argparse
import os
import logging
from appdirs import user_log_dir

# === Logging ===
log_dir = user_log_dir("WhaleScope", "Cauco")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "whalescope.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=log_file,
    filemode='a'
)

# === Función para detectar qué Python usar ===
def get_python_command():
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # Si estamos en producción (dentro del .app)
    embed_python = os.path.join(base_dir, 'python_embed', 'bin', 'python3.11')
    if os.path.exists(embed_python):
        return embed_python

    # En desarrollo: usar venv si existe
    venv_python = os.path.join(base_dir, 'venv', 'bin', 'python3')
    if os.path.exists(venv_python):
        return venv_python

    # Fallback: usar python3 del sistema
    logging.warning("No se encontró python embebido ni venv, usando 'python3'")
    return 'python3'

# === Función principal que ejecuta los scripts por modo ===
def update_data(mode, start_date=None, end_date=None):
    logger = logging.getLogger(__name__)
    logger.info(f"Starting data update for mode '{mode}'")

    base_dir = os.path.dirname(os.path.abspath(__file__))

    scripts = {
        'bitcoin': os.path.join(base_dir, 'bitcoin.py'),
        'blackrock': os.path.join(base_dir, 'blackrock.py'),
        'lido': os.path.join(base_dir, 'lido_staking.py'),
        'binance-polar': os.path.join(base_dir, 'binance_polar.py')
    }

    output_files = {
        'bitcoin': os.path.join(base_dir, 'output.json'),
        'blackrock': os.path.join(base_dir, 'blackrock_output.json'),
        'lido': os.path.join(base_dir, 'lido_output.json'),
        'binance-polar': os.path.join(base_dir, 'binance_polar_output.json')
    }

    script = scripts.get(mode)
    output_file = output_files.get(mode)

    if not script or not os.path.exists(script):
        logger.error(f"Script '{script}' not found for mode '{mode}'")
        return {"error": f"Script '{script}' not found"}

    python_command = get_python_command()
    cmd = [python_command, script]
    if mode == 'binance-polar':
        cmd.append('binance_polar')
    elif start_date and end_date:
        cmd.extend(['--start-date', start_date, '--end-date', end_date])

    # Configurar PYTHONPATH para incluir site-packages de Python 3.11
    venv_site_packages = os.path.join(base_dir, 'venv', 'lib', 'python3.11', 'site-packages')
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    if os.path.exists(venv_site_packages):
        env["PYTHONPATH"] = f"{venv_site_packages}{os.pathsep}{os.environ.get('PYTHONPATH', '')}"
    else:
        logger.error(f"site-packages not found at {venv_site_packages}")
        return {"error": f"site-packages not found at {venv_site_packages}"}

    logger.info(f"Python command: {python_command}")
    logger.info(f"Executing: {' '.join(cmd)}")
    logger.info(f"PYTHONPATH: {env.get('PYTHONPATH', 'Not set')}")
    logger.info(f"Working directory: {base_dir}")

    # Depurar el Python usado
    python_version_cmd = [python_command, "--version"]
    try:
        version_result = subprocess.run(python_version_cmd, capture_output=True, text=True)
        logger.info(f"Python version: {version_result.stdout.strip()}")
    except Exception as e:
        logger.error(f"Error checking Python version: {str(e)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            env=env,
            cwd=base_dir  # Establecer directorio de trabajo
        )

        stdout_clean = result.stdout.strip()
        if not stdout_clean:
            logger.error("Empty stdout")
            return {"error": "Empty output from script"}

        data = json.loads(stdout_clean)

        # Validación mínima para 'lido'
        if mode == 'lido' and not all(k in data for k in ['markets', 'yields', 'analytics', 'charts']):
            logger.error("Missing keys in Lido data")
            return {"error": "Invalid JSON structure from lido"}

        # Validación mínima para 'binance-polar'
        if mode == 'binance-polar' and not isinstance(data, list):
            logger.error("Binance Polar data must be a list of objects")
            return {"error": "Invalid JSON structure from binance-polar"}

        with open(output_file, 'w') as f:
            json.dump(data, f, indent=4)

        logger.info(f"Data saved to {output_file}")
        return data

    except subprocess.CalledProcessError as e:
        logger.error(f"Script error: {e.stderr}")
        return {"error": f"Script execution error: {e.stderr}"}
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        logger.error(f"Output was: {result.stdout}")
        return {"error": f"Invalid JSON output: {e}"}
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {"error": str(e)}

# === Entry Point ===
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WhaleScope data updater")
    parser.add_argument('mode', choices=['bitcoin', 'blackrock', 'lido', 'binance-polar', 'all'], help="Mode to run")
    parser.add_argument('--start-date', type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument('--end-date', type=str, help="End date (YYYY-MM-DD)")
    args = parser.parse_args()

    modes = ['bitcoin', 'blackrock', 'lido', 'binance-polar'] if args.mode == 'all' else [args.mode]
    results = {}

    for mode in modes:
        results[mode] = update_data(mode, args.start_date, args.end_date)

    print(json.dumps(results[args.mode] if args.mode != 'all' else results, indent=4))
    sys.stdout.flush()