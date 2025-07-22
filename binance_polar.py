# binance_polar.py
import ccxt
import pandas as pd
import numpy as np
import os
from dotenv import load_dotenv
import json
import sys
import time

# Cargar variables de entorno
load_dotenv()

api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_API_SECRET')

if not api_key or not api_secret:
    print(json.dumps({"error": "BINANCE_API_KEY or BINANCE_API_SECRET not set in .env"}))
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
limit = 100
show_percent = True
draw_mean = True
label_size = 10
interpolation_points = 300

def fetch_ohlcv(symbol):
    data = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['delta'] = np.abs(df['close'] - df['open']) / df['open']
    df['v_usdt'] = df['volume'] * df['close']
    return df

def normalize(series, scale):
    return series / (series.sum() / scale)

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
            results.append({'symbol': symbol, 'color': color, 'cum_vol': cum_vol, 'cum_delta': cum_delta})
            time.sleep(exchange.rateLimit / 1000)
        except Exception as e:
            print(f"[ERROR] {symbol}: {e}")
            results.append({'symbol': symbol, 'color': color, 'cum_vol': 0, 'cum_delta': 0})

    df_res = pd.DataFrame(results)
    df_res['norm_vol'] = normalize(df_res['cum_vol'], 360)
    df_res['norm_delta'] = normalize(df_res['cum_delta'], 100)
    df_res['area'] = df_res['cum_vol'] * df_res['cum_delta']
    total_area = df_res['area'].sum()
    df_res['percent'] = df_res['area'] / total_area * 100

    return df_res.to_dict(orient='records')

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Section argument is required"}))
        sys.exit(1)

    section = sys.argv[1]
    if section == "binance_polar":
        data = generate_polar_data()
        print(json.dumps(data))
    else:
        print(json.dumps({"error": f"Unknown section: {section}"}))
        sys.exit(1)

if __name__ == "__main__":
    main()