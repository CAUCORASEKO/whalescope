# bitcoin.py

import requests
import sqlite3
import json
import argparse
from datetime import datetime, timedelta
import logging
import time
import random
import os
import hashlib
import hmac
import urllib.parse
import pandas as pd
import sys
from appdirs import user_log_dir  # Import appdirs for platform-specific log directory

# Set up logging configuration to write to a platform-appropriate directory
# Use appdirs to determine a writable log directory (e.g., ~/Library/Logs/WhaleScope on macOS)
log_dir = user_log_dir("WhaleScope", "Cauco")  # App name: WhaleScope, author: Cauco
os.makedirs(log_dir, exist_ok=True)  # Create the log directory if it doesn't exist
log_file = os.path.join(log_dir, "bitcoin.log")  # Define log file path

try:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filename=log_file,  # Use platform-specific log file path
        filemode='a'  # Append mode to avoid overwriting logs
    )
    logger = logging.getLogger(__name__)
    logger.info("Script started successfully")
    logger.info("Logging setup completed")
except Exception as e:
    # Log to stderr if file logging setup fails
    print(f"Error setting up logging: {str(e)}", file=sys.stderr)
    sys.exit(1)

# Binance API configuration
API_KEY = 'API_KEY'
API_SECRET = 'API_SECRET'

# Cache configuration
CACHE_DIR = "cache"
CACHE_DURATION = 300  # 5 minutes in seconds

# Create cache directory if it doesn't exist
logger.info(f"Checking cache directory: {CACHE_DIR}")
if not os.path.exists(CACHE_DIR):
    try:
        os.makedirs(CACHE_DIR)
        logger.info(f"Created cache directory: {CACHE_DIR}")
    except OSError as e:
        logger.error(f"Error creating cache directory: {str(e)}")
        sys.exit(1)
else:
    logger.info("Cache directory already exists")

def get_cache_key(url):
    """Generate a cache key for the given URL."""
    return os.path.join(CACHE_DIR, hashlib.md5(url.encode()).hexdigest() + ".json")

def get_cached_response(url):
    """Retrieve cached response for the URL if available and not expired."""
    cache_file = get_cache_key(url)
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                cached = json.load(f)
            if time.time() - cached['timestamp'] < CACHE_DURATION:
                logger.info(f"Using cached data for {url}")
                return cached['data']
            else:
                logger.info(f"Cache expired for {url}, fetching new data")
                return None
        except json.JSONDecodeError as e:
            logger.error(f"Corrupted cache file {cache_file}: {str(e)}. Deleting file.")
            os.remove(cache_file)
            return None
        except Exception as e:
            logger.error(f"Error reading cache file {cache_file}: {str(e)}")
            return None
    return None

def cache_response(url, data):
    """Cache the response data for the given URL."""
    cache_file = get_cache_key(url)
    try:
        with open(cache_file, 'w') as f:
            json.dump({'timestamp': time.time(), 'data': data}, f, indent=2)
        logger.info(f"Cached response for {url} to {cache_file}")
    except Exception as e:
        logger.error(f"Failed to cache response for {url}: {str(e)}")

def make_request_with_retry(url, headers=None, params=None, max_retries=3):
    """Make an HTTP request with retries and caching."""
    cache_key = url + (json.dumps(params, sort_keys=True) if params else "")
    cached = get_cached_response(cache_key)
    if cached is not None:
        return cached

    for attempt in range(max_retries):
        logger.info(f"Requesting (attempt {attempt + 1}): {url}")
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json() if 'json' in response.headers.get('Content-Type', '').lower() else response.text
                cache_response(cache_key, data)
                return data
            elif response.status_code == 429:
                logger.warning(f"Rate limit reached (429). Retrying after {5 ** attempt} seconds...")
                time.sleep(5 ** attempt + random.uniform(0, 1))
            else:
                logger.error(f"Request error: {response.status_code} - {response.text}")
                return None
        except requests.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            if attempt == max_retries - 1:
                logger.error(f"Max retries reached for {url}")
                return None
            time.sleep(5 ** attempt + random.uniform(0, 1))
    return None

def sign_binance_request(params):
    """Sign a Binance API request with HMAC SHA256."""
    query_string = urllib.parse.urlencode(params)
    signature = hmac.new(
        API_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    params['signature'] = signature
    return params

def detect_whales(df, timeframe='1h', magnitude_60=1.2, length_60=24, magnitude_240=2.0, length_240=12, price_change_threshold=0.005, drift=False):
    """Detect whale activity in the given DataFrame based on volume and price changes."""
    df = df.copy()
    
    if timeframe == '1h':
        magnitude = magnitude_60
        length = length_60
    elif timeframe == '4h':
        magnitude = magnitude_240
        length = length_240
    else:
        raise ValueError("Only '1h' and '4h' timeframes are supported.")

    df['vma'] = df['volume'].rolling(window=length).mean()
    df['whale_volume'] = df['volume'] >= magnitude * df['vma']
    df['price_change'] = df['close'].pct_change().abs()
    df['whale_price'] = df['price_change'] >= price_change_threshold
    df['whale'] = df['whale_volume'] & df['whale_price']
    df['w1'] = df['whale'].shift(24)
    df['w2'] = df['whale'].shift(48)
    df['w3'] = df['whale'].shift(72)

    if drift:
        df['w1'] = df['w1'] | df['whale'].shift(23) | df['whale'].shift(25)
        df['w2'] = df['w2'] | df['whale'].shift(47) | df['whale'].shift(49)
        df['w3'] = df['w3'] | df['whale'].shift(71) | df['whale'].shift(73)

    df['is_whale'] = df['whale'] & (df['w1'] | df['w2'] | df['w3'])
    return df

def generate_market_analysis(price, change_24h, net_flow, whale_transaction, support_level):
    """Generate a simple market analysis."""
    analysis = ""

    # Rule 1: Evaluate price trend
    if change_24h < 0:
        analysis += f"Price declining ({change_24h}% in 24h)"
    else:
        analysis += f"Price rising ({change_24h}% in 24h)"

    # Rule 2: Interpret exchange flows
    if net_flow < 0:
        analysis += f", but negative net flow ({net_flow:.2f} BTC) suggests accumulation."
    else:
        analysis += f", and positive net flow ({net_flow:.2f} BTC) indicates potential selling."

    # Rule 3: Detect whale activity and its impact
    if whale_transaction > 200000000:  # Threshold for considering a "large whale"
        analysis += f" High whale activity (${whale_transaction/1000000:.1f}M): expect volatility."

    # Rule 4: Identify key price levels
    if price <= support_level * 1.02:  # If price is near support (within 2%)
        analysis += f" Price near support (${support_level}): potential buying opportunity."

    return analysis

def fetch_bitcoin_data(start_date=None, end_date=None):
    """Fetch Bitcoin market data and perform analysis."""
    logger.info(f"Starting fetch_bitcoin_data from {start_date} to {end_date}")

    # Clear cache to ensure fresh data
    if os.path.exists(CACHE_DIR):
        for cache_file in os.listdir(CACHE_DIR):
            try:
                os.remove(os.path.join(CACHE_DIR, cache_file))
                logger.info(f"Deleted cache file: {cache_file}")
            except Exception as e:
                logger.error(f"Failed to delete cache file {cache_file}: {str(e)}")
        logger.info("Cache cleared before fetching new data")

    # Connect to database with error handling
    try:
        logger.info("Connecting to database...")
        # Use a relative path to whalescope.db to work in the packaged app
        db_path = os.path.join(os.path.dirname(__file__), 'whalescope.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        logger.info("Database connected successfully")
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {str(e)}")
        sys.exit(1)

    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    if not start_date:
        start_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')

    logger.info(f"Fetching data from {start_date} to {end_date}")
    start_timestamp = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp())
    end_timestamp = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp())

    url_binance_klines = 'https://api.binance.com/api/v3/klines'
    params = {
        'symbol': 'BTCUSDT',
        'interval': '1d',
        'startTime': start_timestamp * 1000,
        'endTime': end_timestamp * 1000,
        'limit': 1000
    }
    historical_data = make_request_with_retry(url_binance_klines, params=params)
    if historical_data is None:
        logger.error("Failed to fetch historical data from Binance. Proceeding with empty data.")
        historical_data = []

    # Prepare price_history for the JSON response
    price_history = {
        "dates": [],
        "open": [],
        "high": [],
        "low": [],
        "close": []
    }
    cursor.execute("DELETE FROM btc_prices")
    conn.commit()

    dates = []
    price_dict = {}
    for entry in historical_data:
        timestamp_ms = entry[0]
        date = datetime.fromtimestamp(timestamp_ms / 1000).strftime('%Y-%m-%d')
        open_price = float(entry[1])  # Open price
        high_price = float(entry[2])  # High price
        low_price = float(entry[3])   # Low price
        close_price = float(entry[4]) # Close price
        cursor.execute("""
            INSERT INTO btc_prices (ticker, date, price_usd)
            VALUES (?, ?, ?)
        """, ('BTC-USD', date, close_price))
        dates.append(date)
        price_dict[date] = close_price
        price_history["dates"].append(date)
        price_history["open"].append(open_price)
        price_history["high"].append(high_price)
        price_history["low"].append(low_price)
        price_history["close"].append(close_price)
    conn.commit()
    logger.info(f"Historical data inserted: {len(historical_data)} rows")

    url_binance_spot = 'https://api.binance.com/api/v3/ticker/24hr'
    params = {'symbol': 'BTCUSDT'}
    binance_spot_data = make_request_with_retry(url_binance_spot, params=params)
    if binance_spot_data:
        price = float(binance_spot_data.get('lastPrice', 0))
        volume_24h = float(binance_spot_data.get('volume', 0)) * price
        percent_change_24h = float(binance_spot_data.get('priceChangePercent', 0))
    else:
        logger.warning("Failed to fetch spot data from Binance. Using default values.")
        price = 0
        volume_24h = 0
        percent_change_24h = 0

    url_current = 'https://api.coingecko.com/api/v3/coins/bitcoin?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false&sparkline=false'
    cmc_data = make_request_with_retry(url_current)
    if cmc_data:
        market_cap = cmc_data['market_data']['market_cap'].get('usd', 0)
        circulating_supply = cmc_data['market_data'].get('circulating_supply', 0)
        max_supply = cmc_data['market_data'].get('max_supply', 0)
        percent_change_7d = cmc_data['market_data'].get('price_change_percentage_7d', 0)
        percent_change_30d = cmc_data['market_data'].get('price_change_percentage_30d', 0)
        market_dominance = cmc_data['market_data'].get('market_cap_dominance', 0)
        last_updated = cmc_data['market_data'].get('last_updated', 'N/A')
    else:
        logger.warning("Failed to fetch current data from CoinGecko. Using default values.")
        market_cap = 0
        circulating_supply = 0
        max_supply = 0
        percent_change_7d = 0
        percent_change_30d = 0
        market_dominance = 0
        last_updated = 'N/A'

    if market_dominance == 0:
        url_total_market = 'https://api.coingecko.com/api/v3/global'
        total_market_data = make_request_with_retry(url_total_market)
        if total_market_data and 'data' in total_market_data:
            total_market_cap = total_market_data['data']['total_market_cap'].get('usd', 0)
            if total_market_cap > 0:
                market_dominance = (market_cap / total_market_cap) * 100
                logger.info(f"Market dominance calculated: {market_dominance}%")
        else:
            logger.warning("Unable to calculate market dominance. Keeping value at 0.")

    fees_dates = []
    fees_values = []
    url_fees_current = 'https://mempool.space/api/v1/fees/recommended'
    response_fees_current = make_request_with_retry(url_fees_current)
    if response_fees_current:
        avg_fee_sat_per_byte = (response_fees_current['fastestFee'] + response_fees_current['halfHourFee'] + response_fees_current['hourFee']) / 3
    else:
        logger.warning("Failed to fetch fees from Mempool.space. Using default value.")
        avg_fee_sat_per_byte = 0

    for date in dates:
        historical_price = price_dict.get(date, 0)
        avg_fee_sat = avg_fee_sat_per_byte * 250
        avg_fee_btc = avg_fee_sat / 1e8
        avg_fee_usd = avg_fee_btc * historical_price if historical_price else 0
        fees_dates.append(date)
        fees_values.append(avg_fee_usd)

    top_flows = []
    whale_start = int((datetime.now() - timedelta(days=5)).timestamp())
    whale_end = int(datetime.now().timestamp())
    url_whale_klines = 'https://api.binance.com/api/v3/klines'
    params = {
        'symbol': 'BTCUSDT',
        'interval': '1h',
        'startTime': whale_start * 1000,
        'endTime': whale_end * 1000,
        'limit': 1000
    }
    whale_data = make_request_with_retry(url_whale_klines, params=params)
    if whale_data:
        logger.info(f"Received candle data from Binance: {len(whale_data)} rows")
        df = pd.DataFrame(whale_data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_volume',
            'taker_buy_quote_volume', 'ignore'
        ])
        logger.info(f"DataFrame created with columns: {df.columns.tolist()}")
        logger.info(f"First rows of DataFrame:\n{df.head().to_string()}")
        
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['volume'] = df['volume'].astype(float)
        df['close'] = df['close'].astype(float)

        df = detect_whales(df, timeframe='1h', magnitude_60=1.2, length_60=24, price_change_threshold=0.005, drift=True)

        logger.info(f"Average volume (VMA): {df['vma'].mean()}")
        logger.info(f"Max volume: {df['volume'].max()}")
        logger.info(f"Max price change: {df['price_change'].max()}")
        logger.info(f"Rows with whale_volume=True: {len(df[df['whale_volume'] == True])}")
        logger.info(f"Rows with whale_price=True: {len(df[df['whale_price'] == True])}")
        logger.info(f"Rows with whale=True: {len(df[df['whale'] == True])}")

        whale_events = df[df['is_whale'] == True]
        logger.info(f"Whale events detected: {len(whale_events)}")
        for _, row in whale_events.iterrows():
            event = {
                "hash": "N/A",
                "time": row['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                "input_total_usd": row['volume'] * row['close'],
                "output_total_usd": row['volume'] * row['close'],
                "fee_usd": 0,
                "is_confirmed": True
            }
            top_flows.append(event)
            logger.info(f"Whale event added: {event}")
        top_flows = sorted(top_flows, key=lambda x: x['time'], reverse=True)[:5]
        logger.info(f"Detected {len(top_flows)} whale events from Binance.")
    else:
        logger.warning("Failed to fetch candles from Binance to detect whales. Trying Blockchair API v3...")
        url_blockchair_v3 = 'https://api.3xpl.com/bitcoin/transactions'
        params = {
            'order': 'input_total_usd:desc',
            'input_total_usd[gte]': 1000000,
            'limit': 5
        }
        blockchair_data = make_request_with_retry(url_blockchair_v3, params=params)
        if blockchair_data and 'data' in blockchair_data and blockchair_data['data']:
            for tx in blockchair_data['data']:
                top_flows.append({
                    "hash": tx.get('txid', 'N/A'),
                    "time": tx.get('time', 'N/A'),
                    "input_total_usd": float(tx.get('input_total_usd', 0)),
                    "output_total_usd": float(tx.get('output_total_usd', 0)),
                    "fee_usd": float(tx.get('fee_usd', 0)),
                    "is_confirmed": tx.get('confirmed', True)
                })
            logger.info(f"Fetched {len(top_flows)} large transactions from Blockchair API v3")
        else:
            logger.warning("Failed to fetch large transactions from Blockchair API v3. Trying Blockchair API v2...")
            url_blockchair_v2 = 'https://api.blockchair.com/bitcoin/transactions'
            params = {
                'sort': 'input_total_usd(desc)',
                'q': 'input_total_usd>=1000000',
                'limit': 5
            }
            blockchair_data = make_request_with_retry(url_blockchair_v2, params=params)
            if blockchair_data and 'data' in blockchair_data and blockchair_data['data']:
                for tx in blockchair_data['data']:
                    top_flows.append({
                        "hash": tx.get('hash', 'N/A'),
                        "time": tx.get('time', 'N/A'),
                        "input_total_usd": float(tx.get('input_total_usd', 0)),
                        "output_total_usd": float(tx.get('output_total_usd', 0)),
                        "fee_usd": float(tx.get('fee_usd', 0)),
                        "is_confirmed": tx.get('block_id', -1) != -1
                    })
                logger.info(f"Fetched {len(top_flows)} large transactions from Blockchair API v2")
            else:
                logger.warning("Failed to fetch large transactions from Blockchair API v2. Attempting additional fallback...")
                url_mempool = 'https://mempool.space/api/v1/transactions'
                mempool_data = make_request_with_retry(url_mempool)
                if mempool_data:
                    for tx in mempool_data[:5]:
                        input_total_btc = sum(vin.get('prevout', {}).get('value', 0) for vin in tx.get('vin', [])) / 1e8
                        input_total_usd = input_total_btc * price if price > 0 else 0
                        if input_total_usd >= 1000000:
                            top_flows.append({
                                "hash": tx.get('txid', 'N/A'),
                                "time": tx.get('status', {}).get('block_time', datetime.now().timestamp()),
                                "input_total_usd": input_total_usd,
                                "output_total_usd": sum(vout.get('value', 0) for vout in tx.get('vout', [])) / 1e8 * price if price > 0 else 0,
                                "fee_usd": tx.get('fee', 0) / 1e8 * price if price > 0 else 0,
                                "is_confirmed": tx.get('status', {}).get('confirmed', False)
                            })
                    if top_flows:
                        top_flows = sorted(top_flows, key=lambda x: x['input_total_usd'], reverse=True)[:5]
                        logger.info(f"Fetched {len(top_flows)} large transactions from Mempool.space")
                    else:
                        logger.warning("No large transactions found on Mempool.space. Proceeding with empty top_flows.")

    inflows = 0
    outflows = 0
    url_agg_trades = 'https://api.binance.com/api/v3/aggTrades'
    params = {
        'symbol': 'BTCUSDT',
        'limit': 1000
    }
    agg_trades = make_request_with_retry(url_agg_trades, params=params)
    if agg_trades:
        for trade in agg_trades:
            value_usd = float(trade['p']) * float(trade['q'])
            if trade['m']:
                outflows += value_usd
            else:
                inflows += value_usd
        logger.info(f"Inflows calculated: {inflows} USD, Outflows calculated: {outflows} USD")
        if price > 0:
            inflows = inflows / price
            outflows = outflows / price
        else:
            logger.warning("Price is 0, cannot convert inflows/outflows to BTC.")
    else:
        logger.warning("Failed to fetch aggTrades from Binance. Keeping inflows and outflows at 0.")

    # Calculate net flow
    net_flow = inflows - outflows

    # Determine support level (using a simple value based on the minimum price from historical data)
    prices = [float(entry[4]) for entry in historical_data if float(entry[4]) > 0]
    support_level = min(prices) if prices else 0

    # Get the latest whale transaction (if any)
    latest_whale_transaction = top_flows[0]["input_total_usd"] if top_flows else 0

    # Generate the market analysis
    analysis = generate_market_analysis(
        price=price,
        change_24h=percent_change_24h,
        net_flow=net_flow,
        whale_transaction=latest_whale_transaction,
        support_level=support_level
    )

    # Generate a simple conclusion
    conclusion = ""
    if percent_change_24h < 0 and net_flow < 0:
        conclusion = "Despite the short-term decline, whale accumulation suggests a potential rebound."
    elif percent_change_24h > 0 and net_flow < 0:
        conclusion = "Bullish trend supported by whale accumulation; market appears strong."
    else:
        conclusion = "Mixed market signals; monitor whale activity and flows for trend confirmation."

    data = {
        "type": "result",
        "markets": {
            "price": price,
            "volume_24h": volume_24h,
            "market_cap": market_cap,
            "fdv": price * max_supply if max_supply else market_cap,
            "current_supply": circulating_supply,
            "max_supply": max_supply,
            "percent_change_24h": percent_change_24h,
            "percent_change_7d": percent_change_7d,
            "percent_change_30d": percent_change_30d,
            "market_dominance": market_dominance,
            "last_updated": last_updated
        },
        "yields": {
            "percent_change_24h": percent_change_24h,
            "percent_change_7d": percent_change_7d,
            "percent_change_30d": percent_change_30d
        },
        "inflows": inflows,
        "outflows": outflows,
        "net_flow": net_flow,
        "top_flows": top_flows,
        "fees": {
            "dates": fees_dates,
            "values": fees_values
        },
        "price_history": price_history,  # New field for historical price data
        "analysis": analysis,
        "conclusion": conclusion,
        "timestamp": datetime.now().isoformat()
    }

    conn.close()
    logger.info("fetch_bitcoin_data completed")

    return data

if __name__ == "__main__":
    try:
        logger.info("Parsing arguments...")
        parser = argparse.ArgumentParser(description="Bitcoin data fetcher")
        parser.add_argument('--start-date', type=str, help="Start date (YYYY-MM-DD)")
        parser.add_argument('--end-date', type=str, help="End date (YYYY-MM-DD)")
        args = parser.parse_args()
        logger.info(f"Arguments received: start_date={args.start_date}, end_date={args.end_date}")

        # Fetch data and output JSON
        data = fetch_bitcoin_data(args.start_date, args.end_date)
        sys.stdout.write(json.dumps(data))
        sys.stdout.flush()
    except Exception as e:
        logger.error(f"Script failed: {str(e)}")
        sys.exit(1)