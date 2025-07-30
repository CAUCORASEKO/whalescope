import sys
import json
import logging
import os
import requests
import hashlib
import time
import random
from datetime import datetime, timedelta
import argparse
import urllib.parse
import hmac
from appdirs import user_log_dir  # For platform-specific log directory

# Set up logging configuration
log_dir = user_log_dir("WhaleScope", "Cauco")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "eth.log")

try:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filename=log_file,
        filemode='a'
    )
    logger = logging.getLogger(__name__)
    logger.info("Script started successfully")
    logger.info("Logging setup completed")
except Exception as e:
    print(f"Error setting up logging: {str(e)}", file=sys.stderr)
    sys.exit(1)

# Load environment variables
API_KEY = os.getenv('API_KEY', 'nGUWm71gEi81rTmdjRkcHq1xrhwnM8V5tuPVviIEtHNs1qCJcETbrvoSeMbTq4Ci')
API_SECRET = os.getenv('API_SECRET', 'U9OJIPGc42AU2gblGGK3gkl2vh9c176rzkHBa39B0wew6DpkDIcuRlNiZF2UyBk2')

# Binance API base URL
BINANCE_API_URL = "https://api.binance.com"

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

def get_cached_response(url, params=None):
    """Retrieve cached response for the URL if available and not expired."""
    cache_key = url + (json.dumps(params, sort_keys=True) if params else "")
    cache_file = get_cache_key(cache_key)
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                cached = json.load(f)
            if time.time() - cached['timestamp'] < CACHE_DURATION:
                logger.info(f"Using cached data for {cache_key}")
                return cached['data']
            else:
                logger.info(f"Cache expired for {cache_key}, fetching new data")
                os.remove(cache_file)
                return None
        except json.JSONDecodeError as e:
            logger.error(f"Corrupted cache file {cache_file}: {str(e)}. Deleting file.")
            os.remove(cache_file)
            return None
        except Exception as e:
            logger.error(f"Error reading cache file {cache_file}: {str(e)}")
            return None
    return None

def cache_response(url, params, data):
    """Cache the response data for the given URL and params."""
    cache_key = url + (json.dumps(params, sort_keys=True) if params else "")
    cache_file = get_cache_key(cache_key)
    try:
        with open(cache_file, 'w') as f:
            json.dump({'timestamp': time.time(), 'data': data}, f, indent=2)
        logger.info(f"Cached response for {cache_key} to {cache_file}")
    except Exception as e:
        logger.error(f"Failed to cache response for {cache_key}: {str(e)}")

def sign_request(params):
    """Sign a Binance API request with HMAC SHA256."""
    query_string = urllib.parse.urlencode(params)
    signature = hmac.new(
        API_SECRET.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    params['signature'] = signature
    return params

def make_request_with_retry(url, headers=None, params=None, max_retries=3, signed=False):
    """Make an HTTP request with retries and caching."""
    cache_key = url + (json.dumps(params, sort_keys=True) if params else "")
    cached = get_cached_response(url, params)
    if cached is not None:
        return cached

    if signed and params:
        params['timestamp'] = int(time.time() * 1000)
        params = sign_request(params)
        if headers is None:
            headers = {}
        headers['X-MBX-APIKEY'] = API_KEY

    for attempt in range(max_retries):
        logger.info(f"Requesting (attempt {attempt + 1}): {url} with params {params}")
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json() if 'json' in response.headers.get('Content-Type', '').lower() else response.text
                cache_response(url, params, data)
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

def generate_market_analysis(price, change_24h, net_flow, whale_transaction, support_level):
    """Generate a simple market analysis."""
    analysis = ""
    if change_24h < 0:
        analysis += f"Price declining ({change_24h}% in 24h)"
    else:
        analysis += f"Price rising ({change_24h}% in 24h)"
    if net_flow < 0:
        analysis += f", but negative net flow ({net_flow:.2f} ETH) suggests accumulation."
    else:
        analysis += f", and positive net flow ({net_flow:.2f} ETH) indicates potential selling."
    if whale_transaction > 200000000:
        analysis += f" High whale activity (${whale_transaction/1000000:.1f}M): expect volatility."
    if price <= support_level * 1.02:
        analysis += f" Price near support (${support_level}): potential buying opportunity."
    return analysis

def fetch_eth_data(start_date=None, end_date=None):
    """Fetch ETH market data and perform analysis using Binance API."""
    logger.info(f"Starting fetch_eth_data from {start_date} to {end_date}")

    # Clear cache to ensure fresh data
    if os.path.exists(CACHE_DIR):
        for cache_file in os.listdir(CACHE_DIR):
            if cache_file.endswith('.json'):
                try:
                    os.remove(os.path.join(CACHE_DIR, cache_file))
                    logger.info(f"Deleted cache file: {cache_file}")
                except Exception as e:
                    logger.error(f"Failed to delete cache file {cache_file}: {str(e)}")
        logger.info("Cache cleared before fetching new data")

    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    if not start_date:
        start_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')

    logger.info(f"Fetching data from {start_date} to {end_date}")
    start_timestamp = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)
    end_timestamp = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)

    # Fetch historical klines from Binance
    url_klines = f"{BINANCE_API_URL}/api/v3/klines"
    params = {
        'symbol': 'ETHUSDT',
        'interval': '1d',
        'startTime': start_timestamp,
        'endTime': end_timestamp,
        'limit': 1000
    }
    historical_data = make_request_with_retry(url_klines, params=params)
    if not historical_data:
        logger.error("Failed to fetch historical data from Binance. Proceeding with empty data.")
        historical_data = []

    # Prepare price_history
    price_history = {
        'dates': [],
        'open': [],
        'high': [],
        'low': [],
        'close': []
    }
    for entry in historical_data:
        timestamp_ms = entry[0]
        date = datetime.fromtimestamp(timestamp_ms / 1000).strftime('%Y-%m-%d')
        price_history['dates'].append(date)
        price_history['open'].append(float(entry[1]))
        price_history['high'].append(float(entry[2]))
        price_history['low'].append(float(entry[3]))
        price_history['close'].append(float(entry[4]))

    # Fetch 24hr ticker data
    url_ticker = f"{BINANCE_API_URL}/api/v3/ticker/24hr"
    params = {'symbol': 'ETHUSDT'}
    ticker_data = make_request_with_retry(url_ticker, params=params)
    if ticker_data:
        price = float(ticker_data.get('lastPrice', 0))
        volume_24h = float(ticker_data.get('volume', 0)) * price
        percent_change_24h = float(ticker_data.get('priceChangePercent', 0))
    else:
        logger.warning("Failed to fetch ticker data from Binance. Using default values.")
        price = 0
        volume_24h = 0
        percent_change_24h = 0

    # Placeholder market cap and other yields (Binance doesn't provide these directly via free API)
    markets = {
        'price': price,
        'percent_change_24h': percent_change_24h,
        'market_cap': 0,  # Placeholder; fetch from CoinGecko if needed
        'volume_24h': volume_24h,
        'last_updated': datetime.now().isoformat()
    }
    yields = {
        'percent_change_24h': percent_change_24h,
        'percent_change_7d': 0,  # Placeholder
        'percent_change_30d': 0   # Placeholder
    }

    # Fetch aggTrades for flows (approximation)
    url_agg_trades = f"{BINANCE_API_URL}/api/v3/aggTrades"
    params = {'symbol': 'ETHUSDT', 'limit': 1000}
    agg_trades = make_request_with_retry(url_agg_trades, params=params)
    inflows = 0
    outflows = 0
    if agg_trades:
        for trade in agg_trades:
            value_usd = float(trade['p']) * float(trade['q'])
            if trade['m']:  # 'm' is True if buyer is maker (sell)
                outflows += value_usd
            else:
                inflows += value_usd
        logger.info(f"Inflows calculated: {inflows} USD, Outflows calculated: {outflows} USD")
        if price > 0:
            inflows = inflows / price  # Convert to ETH
            outflows = outflows / price  # Convert to ETH
        else:
            logger.warning("Price is 0, cannot convert inflows/outflows to ETH.")
    else:
        logger.warning("Failed to fetch aggTrades from Binance. Keeping inflows and outflows at 0.")

    net_flow = inflows - outflows

    # Derive fees (placeholder based on volume)
    fees = {
        'dates': price_history['dates'],
        'values': [volume_24h * 0.0001 for _ in price_history['dates']]  # Placeholder fee (0.01% of volume)
    }

    # Top flows (approximate using aggTrades)
    top_flows = []
    if agg_trades:
        for trade in sorted(agg_trades, key=lambda x: float(x['q']) * float(x['p']), reverse=True)[:5]:
            top_flows.append({
                'hash': 'N/A',  # Binance aggTrades doesn't provide transaction hashes
                'time': datetime.fromtimestamp(int(trade['T']) / 1000).isoformat(),
                'input_total_usd': float(trade['q']) * float(trade['p']) if not trade['m'] else 0,
                'output_total_usd': float(trade['q']) * float(trade['p']) if trade['m'] else 0,
                'fee_usd': float(trade['q']) * float(trade['p']) * 0.0001,  # Placeholder fee
                'is_confirmed': True
            })
        logger.info(f"Detected {len(top_flows)} top flows from aggTrades.")
    else:
        logger.warning("No aggTrades data for top flows.")

    # Determine support level
    support_level = min(price_history['low']) if price_history['low'] else 0

    # Get the latest whale transaction
    latest_whale_transaction = top_flows[0]['input_total_usd'] if top_flows else 0

    # Generate market analysis
    analysis = generate_market_analysis(
        price=markets['price'],
        change_24h=markets['percent_change_24h'],
        net_flow=net_flow,
        whale_transaction=latest_whale_transaction,
        support_level=support_level
    )

    # Generate conclusion
    conclusion = ""
    if markets['percent_change_24h'] < 0 and net_flow < 0:
        conclusion = "Despite the short-term decline, whale accumulation suggests a potential rebound."
    elif markets['percent_change_24h'] > 0 and net_flow < 0:
        conclusion = "Bullish trend supported by whale accumulation; market appears strong."
    else:
        conclusion = "Mixed market signals; monitor whale activity and flows for trend confirmation."

    data = {
        'type': 'result',
        'markets': markets,
        'yields': yields,
        'inflows': inflows,
        'outflows': outflows,
        'net_flow': net_flow,
        'top_flows': top_flows,
        'fees': fees,
        'price_history': price_history,
        'analysis': analysis,
        'conclusion': conclusion,
        'timestamp': datetime.now().isoformat()
    }

    logger.info("fetch_eth_data completed")
    return data

if __name__ == "__main__":
    try:
        logger.info("Parsing arguments...")
        parser = argparse.ArgumentParser(description="ETH data fetcher")
        parser.add_argument('--start-date', type=str, help="Start date (YYYY-MM-DD)")
        parser.add_argument('--end-date', type=str, help="End date (YYYY-MM-DD)")
        args = parser.parse_args()
        logger.info(f"Arguments received: start_date={args.start_date}, end_date={args.end_date}")

        # Fetch data and output JSON
        data = fetch_eth_data(args.start_date, args.end_date)
        sys.stdout.write(json.dumps(data))
        sys.stdout.flush()
    except Exception as e:
        logger.error(f"Script failed: {str(e)}")
        sys.exit(1)