# whalescope.py
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

    # Producción: Python embebido
    embed_python = os.path.join(base_dir, 'python_embed', 'bin', 'python3.11')
    if os.path.exists(embed_python):
        return embed_python

    # Desarrollo: venv local
    venv_python = os.path.join(base_dir, 'venv', 'bin', 'python3')
    if os.path.exists(venv_python):
        return venv_python

    # Fallback: sistema
    logging.warning("No se encontró python embebido ni venv, usando 'python3'")
    return 'python3'

# === Detectar site-packages embebido o venv ===
def get_site_packages_dir(base_dir):
    embed_site_packages = os.path.join(base_dir, 'python_embed', 'lib', 'python3.11', 'site-packages')
    venv_site_packages = os.path.join(base_dir, 'venv', 'lib', 'python3.11', 'site-packages')

    if os.path.exists(embed_site_packages):
        return embed_site_packages
    elif os.path.exists(venv_site_packages):
        return venv_site_packages
    else:
        return None

# === Función principal ===
def update_data(mode, start_date=None, end_date=None):
    logger = logging.getLogger(__name__)
    logger.info(f"Starting data update for mode '{mode}'")

    base_dir = os.path.dirname(os.path.abspath(__file__))

    scripts = {
        'bitcoin': os.path.join(base_dir, 'bitcoin.py'),
        'blackrock': os.path.join(base_dir, 'blackrock.py'),
        'lido': os.path.join(base_dir, 'lido_staking.py'),
        'binance-polar': os.path.join(base_dir, 'binance_polar.py'),
        'eth': os.path.join(base_dir, 'eth.py')
    }

    output_files = {
        'bitcoin': os.path.join(base_dir, 'output.json'),
        'blackrock': os.path.join(base_dir, 'blackrock_output.json'),
        'lido': os.path.join(base_dir, 'lido_output.json'),
        'binance-polar': os.path.join(base_dir, 'binance_polar_output.json'),
        'eth': os.path.join(base_dir, 'eth_output.json')
    }

    script = scripts.get(mode)
    output_file = output_files.get(mode)

    if not script or not os.path.exists(script):
        logger.error(f"Script '{script}' not found for mode '{mode}'")
        return {"error": f"Script '{script}' not found"}

    python_command = get_python_command()
    cmd = [python_command, script]

    # Fechas solo para algunos modos
    if start_date and end_date and mode != 'binance-polar':
        cmd.extend(['--start-date', start_date, '--end-date', end_date])
    if mode == 'binance-polar':
        cmd.append('binance_polar')

    # Configurar entorno
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    site_packages_dir = get_site_packages_dir(base_dir)
    if site_packages_dir:
        env["PYTHONPATH"] = f"{site_packages_dir}{os.pathsep}{os.environ.get('PYTHONPATH', '')}"
    else:
        logger.error("site-packages not found in either python_embed or venv")
        return {"error": "site-packages not found in either python_embed or venv"}

    logger.info(f"Python command: {python_command}")
    logger.info(f"Executing: {' '.join(cmd)}")
    logger.info(f"PYTHONPATH: {env.get('PYTHONPATH', 'Not set')}")
    logger.info(f"Working directory: {base_dir}")

    # Versión de Python
    try:
        version_result = subprocess.run([python_command, "--version"], capture_output=True, text=True)
        logger.info(f"Python version: {version_result.stdout.strip()}")
    except Exception as e:
        logger.error(f"Error checking Python version: {str(e)}")

    # Ejecutar script
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            cwd=base_dir
        )
        stdout_clean = result.stdout.strip()
        if result.returncode != 0:
            logger.error("Script failed with return code %d, stderr: %s, stdout: %s", result.returncode, result.stderr, stdout_clean)
            return {"error": f"Script execution failed with code {result.returncode}: {result.stderr}"}
        if not stdout_clean:
            logger.error("Empty stdout, stderr: %s", result.stderr)
            return {"error": "Empty output from script, stderr: " + result.stderr}
        data = json.loads(stdout_clean)

        # Validaciones mínimas
        if mode == 'lido' and not all(k in data for k in ['markets', 'yields', 'analytics', 'charts']):
            logger.error("Missing keys in Lido data")
            return {"error": "Invalid JSON structure from lido"}

        if mode == 'binance-polar' and not isinstance(data, list):
            logger.error("Binance Polar data must be a list of objects")
            return {"error": "Invalid JSON structure from binance-polar"}

        with open(output_file, 'w') as f:
            json.dump(data, f, indent=4)

        logger.info(f"Data saved to {output_file}")
        return data

    except json.JSONDecodeError as e:
        logger.error("JSON decode error: %s, Output was: %s", e, result.stdout)
        return {"error": f"Invalid JSON output: {e}"}
    except Exception as e:
        logger.error("Unexpected error: %s, stderr: %s", str(e), result.stderr if 'result' in locals() else "N/A")
        return {"error": str(e)}

# === Entry Point ===
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WhaleScope data updater")
    parser.add_argument('mode', choices=['bitcoin', 'blackrock', 'lido', 'binance-polar', 'eth', 'all'], help="Mode to run")
    parser.add_argument('--start-date', type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument('--end-date', type=str, help="End date (YYYY-MM-DD)")
    args = parser.parse_args()

    modes = ['bitcoin', 'blackrock', 'lido', 'binance-polar', 'eth'] if args.mode == 'all' else [args.mode]
    results = {}

    for mode in modes:
        results[mode] = update_data(mode, args.start_date, args.end_date)

    print(json.dumps(results[args.mode] if args.mode != 'all' else results, indent=4))
    sys.stdout.flush()
