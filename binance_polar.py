import ccxt
import pandas as pd
import numpy as np
import os
from dotenv import load_dotenv
import json
import sys
import time
import logging

# Cargar variables de entorno
load_dotenv()

# Configuración de logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Use API_KEY and API_SECRET as per .env
api_key = os.getenv('API_KEY')
api_secret = os.getenv('API_SECRET')
logging.debug(f"API Key loaded: {bool(api_key)}, API Secret loaded: {bool(api_secret)}")

if not api_key or not api_secret:
    error_msg = {"error": "API_KEY or API_SECRET not set in .env"}
    print(json.dumps(error_msg))
    logging.error("API credentials missing: %s", error_msg)
    sys.exit(1)

exchange = ccxt.binance({
    'apiKey': api_key,
    'secret': api_secret,
    'enableRateLimit': True
})

# Configuración de usuario
tickers = {
    'BTC/USDT': 'yellow',
    'ETH/USDT': 'aqua',
    'XRP/USDT': 'blue',
    'BNB/USDT': 'magenta',
    'SOL/USDT': 'green',
    'DOGE/USDT': 'lime',
    'ADA/USDT': 'maroon',
    'TRX/USDT': 'silver',
    'LINK/USDT': 'olive',
    'AVAX/USDT': 'orange',
}

timeframe = '1d'
limit = 200  # Sufficient for recent data
show_percent = True
draw_mean = True
label_size = 10
interpolation_points = 300

def fetch_ohlcv(symbol):
    try:
        data = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if not data:
            logging.warning(f"No data fetched for {symbol}")
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['delta'] = np.abs(df['close'] - df['open']) / df['open']
        df['v_usdt'] = df['volume'] * df['close']
        logging.debug(f"Fetched {len(df)} records for {symbol}")
        return df
    except Exception as e:
        logging.error(f"Failed to fetch OHLCV for {symbol}: {e}")
        return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'delta', 'v_usdt'])

def normalize(series, scale):
    total = series.sum()
    return series / (total / scale) if total > 0 else series * 0  # Avoid division by zero

def polar_coordinates(angles, radii, center_angle_shift=0):
    angles = np.radians(angles + center_angle_shift)
    x = np.cos(angles) * radii
    y = np.sin(angles) * radii
    return x, y

def generate_polar_data():
    results = []
    for symbol, color in tickers.items():
        try:
            df = fetch_ohlcv(symbol)
            cum_vol = df['v_usdt'].sum()
            cum_delta = df['delta'].sum()
            logging.debug(f"{symbol}: cum_vol={cum_vol}, cum_delta={cum_delta}")
            results.append({'symbol': symbol, 'color': color, 'cum_vol': cum_vol, 'cum_delta': cum_delta})
            time.sleep(exchange.rateLimit / 1000)  # Respect rate limit
        except Exception as e:
            logging.error(f"[ERROR] {symbol}: {e}")
            results.append({'symbol': symbol, 'color': color, 'cum_vol': 0, 'cum_delta': 0})

    df_res = pd.DataFrame(results)
    df_res['norm_vol'] = normalize(df_res['cum_vol'], 360)
    df_res['norm_delta'] = normalize(df_res['cum_delta'], 100)
    df_res['area'] = df_res['cum_vol'] * df_res['cum_delta']
    total_area = df_res['area'].sum()
    df_res['percent'] = df_res['area'] / total_area * 100 if total_area > 0 else 0

    logging.debug(f"Generated polar data: {json.dumps(df_res.to_dict(orient='records')[:1])}...")  # Log first record
    return df_res.to_dict(orient='records')

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Section argument is required"}))
        logging.error("No section argument provided")
        sys.exit(1)

    section = sys.argv[1]
    if section != "binance_polar":
        print(json.dumps({"error": f"Unknown section: {section}"}))
        logging.error(f"Unknown section: {section}")
        sys.exit(1)

    # Ignore additional arguments (e.g., --start-date, --end-date) since this is real-time data
    logging.debug(f"Running with section={section}")
    try:
        data = generate_polar_data()
        print(json.dumps(data))
    except Exception as e:
        logging.error(f"Exception in generate_polar_data: {e}")
        print(json.dumps({"error": f"Failed to generate data: {e}"}))
        sys.exit(1)

if __name__ == "__main__":
    main()