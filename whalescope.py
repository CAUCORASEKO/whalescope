import sys
import subprocess
import json
import argparse
import os
import logging
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='whalescope.log',
    filemode='a'
)

def update_data(mode, start_date=None, end_date=None):
    logger = logging.getLogger(__name__)
    logger.info(f"Starting data update for mode '{mode}'")
    
    # Use absolute paths based on script directory
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
        logger.error(f"Mode '{mode}' not recognized")
        return {"error": f"Mode '{mode}' not recognized"}

    if not os.path.exists(script):
        logger.error(f"Script '{script}' not found")
        return {"error": f"Script '{script}' not found"}

    logger.info(f"Executing {script}")
    try:
        python_command = os.path.join(base_dir, 'venv', 'bin', 'python3')
        if not os.path.exists(python_command):
            python_command = 'python3'
            logger.warning(f"Virtual environment Python not found, using {python_command}")
        
        # Build command
        cmd = [python_command, script]
        if start_date and end_date:
            cmd.extend(['--start-date', start_date, '--end-date', end_date])
        
        logger.info(f"Full command: {' '.join(cmd)}")
        
        # Execute command with clean environment
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1"}  # Force unbuffered output
        )
        
        # Log output
        logger.info(f"Stdout from {script}: {result.stdout}")
        if result.stderr:
            logger.error(f"Stderr from {script}: {result.stderr}")
        
        try:
            # Parse JSON from stdout
            stdout_clean = result.stdout.strip()
            if not stdout_clean:
                logger.error(f"Stdout is empty for {script}")
                return {"error": f"Empty stdout from {script}"}
            
            data = json.loads(stdout_clean)
            # Validate expected keys for Lido
            if mode == 'lido' and not all(key in data for key in ['markets', 'yields', 'analytics', 'charts']):
                logger.error(f"Invalid JSON structure from {script}: missing required keys")
                return {"error": f"Invalid JSON structure from {script}"}
            
            # Save to output file
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=4)
            logger.info(f"Data saved to {output_file}")
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON output from {script}: {e}")
            logger.error(f"Stdout content: '{result.stdout}'")
            return {"error": f"Invalid JSON output from {script}: {e}"}
    except subprocess.CalledProcessError as e:
        logger.error(f"Error executing {script}: {e}")
        logger.error(f"Error output: {e.stderr}")
        return {"error": f"Error executing {script}: {e.stderr}"}
    except Exception as e:
        logger.error(f"Unexpected error executing {script}: {e}")
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

    # Output JSON to stdout
    print(json.dumps(results[args.mode] if args.mode != 'all' else results, indent=4))
    sys.stdout.flush()