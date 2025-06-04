import sys
import json
import logging
import sqlite3
import yfinance as yf
import requests
import time
from datetime import datetime, timedelta
import argparse
import warnings
import os
import configparser
from logging.handlers import RotatingFileHandler

# Leer config.ini
config = configparser.ConfigParser()
config.read('config.ini')

# Configuración inicial
sys.stderr = open('blackrock_errors.log', 'a')
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Configurar logging con rotación de archivos
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('blackrock.log', maxBytes=1024*1024, backupCount=5)  # 1 MB per file, keep 5 backups
    ]
)

# Constantes (leídas desde config.ini)
try:
    DB_PATH = config['DEFAULT']['DB_PATH']
    ARKHAM_API_KEY = config['API_KEYS']['ARKHAM_API_KEY']
except KeyError as e:
    logging.error(f"Missing key in config.ini: {e}")
    sys.exit(1)

def init_db():
    """Inicializa las tablas de la base de datos para almacenar datos de Arkham."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS arkham_wallets (
            entity_id TEXT, token TEXT, balance REAL, balance_usd REAL, timestamp TEXT,
            PRIMARY KEY (entity_id, token, timestamp)
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS arkham_transactions (
            entity_id TEXT, date TEXT, type TEXT, amount REAL, amount_usd REAL,
            PRIMARY KEY (entity_id, date, type)
        )''')
        conn.commit()
        logging.info("Database tables initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize database: {e}")
        raise
    finally:
        conn.close()

def fetch_market_stats(ticker='IBIT'):
    """Obtiene estadísticas de mercado para IBIT desde Yahoo Finance."""
    try:
        logging.info(f"Fetching market stats for {ticker}")
        stock = yf.Ticker(ticker)
        info = stock.info
        history = stock.history(period="30d")

        price = info.get('regularMarketPrice', info.get('previousClose', 0.0))
        volume_24h = info.get('volume', 0.0)
        market_cap = info.get('marketCap', 0.0)
        percent_change_24h = 0.0
        percent_change_7d = 0.0
        percent_change_30d = 0.0

        if not history.empty:
            if len(history) >= 2:
                percent_change_24h = ((history['Close'].iloc[-1] - history['Close'].iloc[-2]) / history['Close'].iloc[-2]) * 100
            if len(history) >= 7:
                percent_change_7d = ((history['Close'].iloc[-1] - history['Close'].iloc[-7]) / history['Close'].iloc[-7]) * 100
            if len(history) >= 30:
                percent_change_30d = ((history['Close'].iloc[-1] - history['Close'].iloc[-30]) / history['Close'].iloc[-30]) * 100

        analysis = {
            'recommendation': info.get('recommendationKey', 'N/A'),
            'target_price': info.get('targetMeanPrice', 0.0),
            'rating_summary': info.get('recommendationMean', 'N/A'),
            'earnings_estimate': info.get('earningsGrowth', 'N/A'),
        }

        markets = {
            'price': float(price),
            'volume_24h': float(volume_24h),
            'market_cap': float(market_cap),
            'percent_change_24h': float(percent_change_24h),
            'percent_change_7d': float(percent_change_7d),
            'percent_change_30d': float(percent_change_30d),
            'last_updated': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
            'analysis': analysis
        }
        logging.info(f"Market stats for {ticker}: Price ${price}, Volume ${volume_24h}")
        return markets
    except Exception as e:
        logging.error(f"Failed to fetch market stats: {e}")
        return {
            'price': 0.0,
            'volume_24h': 0.0,
            'market_cap': 0.0,
            'percent_change_24h': 0.0,
            'percent_change_7d': 0.0,
            'percent_change_30d': 0.0,
            'last_updated': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
            'analysis': {}
        }


def fetch_historical_prices(start_date, end_date):
    """Obtiene precios históricos de BTC y ETH desde CryptoCompare, con fallback a CoinGecko."""
    prices = {'BTC': {}, 'ETH': {}}
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        days = (end - start).days + 1

        for coin in ['BTC', 'ETH']:
            logging.info(f"Fetching historical prices for {coin} from CryptoCompare")
            end_timestamp = int(end.timestamp())
            url = f"https://min-api.cryptocompare.com/data/v2/histoday?fsym={coin}&tsym=USD&limit={days}&toTs={end_timestamp}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            logging.debug(f"CryptoCompare response for {coin}: {data}")
            price_data = data.get('Data', {}).get('Data', [])
            for entry in price_data:
                date = datetime.fromtimestamp(entry['time']).strftime('%Y-%m-%d')
                prices[coin][date] = entry['close']
            logging.info(f"Fetched {len(prices[coin])} prices for {coin} from CryptoCompare")
    except Exception as e:
        logging.error(f"Failed to fetch historical prices from CryptoCompare: {str(e)}")
        logging.info("Falling back to CoinGecko")
        try:
            coin_mapping = {'BTC': 'bitcoin', 'ETH': 'ethereum'}
            start_timestamp = int(start.timestamp())
            end_timestamp = int(end.timestamp())
            for coin in ['BTC', 'ETH']:
                coin_id = coin_mapping[coin]
                url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart/range?vs_currency=usd&from={start_timestamp}&to={end_timestamp}"
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                logging.debug(f"CoinGecko response for {coin}: {data}")
                price_data = data.get('prices', [])
                for entry in price_data:
                    timestamp_ms, price = entry
                    date = datetime.fromtimestamp(timestamp_ms / 1000).strftime('%Y-%m-%d')
                    prices[coin][date] = price
                logging.info(f"Fetched {len(prices[coin])} prices for {coin} from CoinGecko")
        except Exception as e:
            logging.error(f"Failed to fetch historical prices from CoinGecko: {str(e)}")
            prices = {'BTC': {}, 'ETH': {}}
    return prices






def check_api_key(api_key):
    """Verifica si la clave API de Arkham es válida usando el endpoint /health."""
    base_url = "https://api.arkm.com"
    endpoint = f"{base_url}/health"
    headers = {
        "API-Key": api_key,
        "Content-Type": "application/json",
        "User-Agent": "WhaleScope/1.0 (TestScript)"
    }
    try:
        logging.info(f"Checking API key validity at {endpoint}")
        logging.debug(f"Headers: {headers}")
        response = requests.get(endpoint, headers=headers, timeout=10)
        response.raise_for_status()
        logging.info(f"API key is valid. Response: {response.text}")
        return True
    except requests.RequestException as e:
        error_message = f"Failed to validate API key: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            error_message += f" | Status Code: {e.response.status_code} | Response: {e.response.text}"
        logging.error(error_message)
        return False

def fetch_blackrock_entity(api_key):
    """Obtiene información de la entidad BlackRock desde Arkham Intelligence."""
    base_url = "https://api.arkm.com"
    endpoint = f"{base_url}/intelligence/entity/blackrock"
    headers = {
        "API-Key": api_key,
        "Content-Type": "application/json",
        "User-Agent": "WhaleScope/1.0 (BlackRockScript)"
    }
    try:
        logging.info(f"Fetching BlackRock entity data from {endpoint}")
        time.sleep(0.1)  # Add delay to avoid rate limiting
        response = requests.get(endpoint, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        logging.debug(f"Raw API response: {data}")
        entity_id = data.get('id')
        if not entity_id:
            logging.error(f"No id found in BlackRock entity data: {data}")
            return None
        logging.info(f"Successfully fetched BlackRock entity data: {data}")
        return data
    except requests.RequestException as e:
        error_message = f"Failed to fetch BlackRock entity data: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            error_message += f" | Status Code: {e.response.status_code} | Response: {e.response.text}"
            if e.response.status_code == 401:
                error_message += " | Please verify your API key at https://info.arkm.com/api-platform"
        logging.error(error_message)
        return None



def fetch_arkham_transactions(api_key, entity_id, start_date, end_date):
    """Obtiene transacciones de BlackRock desde Arkham Intelligence."""
    base_url = "https://api.arkm.com"
    url = f"{base_url}/history/entity/{entity_id}"
    headers = {
        "API-Key": api_key,
        "Content-Type": "application/json"
    }
    params = {
        "startDate": start_date,
        "endDate": end_date,
        "limit": 100
    }
    try:
        logging.info(f"Fetching transactions for entity {entity_id} from {start_date} to {end_date}")
        time.sleep(0.05)
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        logging.debug(f"Raw transactions response: {data}")
        transactions = data.get('transfers', [])
        logging.info(f"Fetched {len(transactions)} transactions from Arkham")
        return transactions
    except requests.RequestException as e:
        error_message = f"Failed to fetch transactions from Arkham: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            error_message += f" | Status Code: {e.response.status_code} | Response: {e.response.text}"
        logging.error(error_message)
        return []






def fetch_arkham_balances(api_key, entity_id):
    """Obtiene balances de BlackRock desde Arkham Intelligence."""
    base_url = "https://api.arkm.com"
    url = f"{base_url}/balances/entity/{entity_id}"
    headers = {
        "API-Key": api_key,
        "Content-Type": "application/json"
    }
    try:
        logging.info(f"Fetching balances for entity {entity_id}")
        time.sleep(0.05)
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        balances = []
        # Extract balances from chain-specific arrays
        for chain in data.get('balances', {}):
            for balance in data['balances'].get(chain, []):
                balances.append(balance)
        logging.debug(f"Received balances: {balances}")
        logging.info(f"Fetched {len(balances)} balances from Arkham")
        return balances
    except requests.RequestException as e:
        error_message = f"Failed to fetch balances from Arkham: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            error_message += f" | Status Code: {e.response.status_code} | Response: {e.response.text}"
        logging.error(error_message)
        return []



def fetch_arkham_exchange_usage(api_key, entity_id, start_date, end_date):
    """Obtiene datos de uso de exchanges para BlackRock desde Arkham Intelligence."""
    transfers = fetch_arkham_transactions(api_key, entity_id, start_date, end_date)
    try:
        logging.info(f"Processing exchange usage for entity {entity_id} from {start_date} to {end_date}")
        deposits = {"total": 0, "summary": []}
        withdrawals = {"total": 0, "summary": []}
        for transfer in transfers:
            usd_value = transfer.get('usdValue', 0)
            from_address = transfer.get('fromAddress', '')
            to_address = transfer.get('toAddress', '')
            if isinstance(from_address, dict):
                from_address = from_address.get('address', '')
            if isinstance(to_address, dict):
                to_address = to_address.get('address', '')
            if 'exchange' in from_address.lower():
                withdrawals["total"] += usd_value
                withdrawals["summary"].append(transfer)
            elif 'exchange' in to_address.lower():
                deposits["total"] += usd_value
                deposits["summary"].append(transfer)

        exchange_usage = {"deposits": deposits, "withdrawals": withdrawals}
        logging.info(f"Fetched exchange usage: {exchange_usage}")
        return exchange_usage
    except Exception as e:
        logging.error(f"Failed to process exchange usage: {str(e)}")
        return {"deposits": {"total": 0, "summary": []}, "withdrawals": {"total": 0, "summary": []}}




def process_transactions(transactions, historical_prices):
    """Procesa transacciones para agrupar compras y ventas por fecha."""
    result = {'BTC': {}, 'ETH': {}}
    for tx in transactions:
        logging.debug(f"Processing transaction: {tx}")
        token = tx.get('tokenSymbol', '').upper()
        if token not in ['BTC', 'ETH']:
            continue
        date = tx.get('blockTimestamp', '').split('T')[0]
        if not date:
            continue
        to_address = tx.get('toAddress', '')
        if isinstance(to_address, dict):
            to_address = to_address.get('address', '')
        tx_type = 'buy' if 'blackrock' in to_address.lower() else 'sell'
        amount = float(tx.get('unitValue', 0))
        if amount < 0.1:
            continue

        if date not in result[token]:
            result[token][date] = {'buys': 0.0, 'sells': 0.0, 'buys_usd': 0.0, 'sells_usd': 0.0}
        if tx_type == 'buy':
            result[token][date]['buys'] += amount
            price = historical_prices[token].get(date, 0.0)
            result[token][date]['buys_usd'] += amount * price
        elif tx_type == 'sell':
            result[token][date]['sells'] += amount
            price = historical_prices[token].get(date, 0.0)
            result[token][date]['sells_usd'] += amount * price

    for token in result:
        result[token] = [
            {
                'date': date,
                'buys': data['buys'],
                'sells': data['sells'],
                'buys_usd': data['buys_usd'],
                'sells_usd': data['sells_usd']
            }
            for date, data in sorted(result[token].items())
        ]
    return result



def update_wallets(api_key, entity_id):
    """Actualiza los datos de las billeteras en la base de datos usando Arkham."""
    balances = fetch_arkham_balances(api_key, entity_id)
    wallet_data = []

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for balance in balances:
            token = balance.get('symbol', '').upper() or 'UNKNOWN'
            amount = float(balance.get('balance', 0))
            amount_usd = float(balance.get('usd', 0))
            wallet_data.append({
                'entity_id': entity_id,
                'token': token,
                'balance': amount,
                'balance_usd': amount_usd,
                'timestamp': timestamp
            })
            cursor.execute('''INSERT INTO arkham_wallets (entity_id, token, balance, balance_usd, timestamp)
                             VALUES (?, ?, ?, ?, ?)''',
                          (entity_id, token, amount, amount_usd, timestamp))
        conn.commit()
        logging.info(f"Inserted {len(wallet_data)} wallet entries")
    except Exception as e:
        logging.error(f"Failed to update wallets in database: {e}")
    finally:
        conn.close()

    return wallet_data




def main(start_date=None, end_date=None):
    """Función principal para obtener datos de BlackRock."""
    logger = logging.getLogger(__name__)
    try:
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        logger.info(f"Running blackrock.py from {start_date} to {end_date}")
        
        init_db()
        markets = fetch_market_stats()

        # Verificar la clave API
        logger.info("Checking API key validity")
        if not check_api_key(ARKHAM_API_KEY):
            raise Exception("Invalid API key. Please verify your API key at https://info.arkm.com/api-platform")

        # Obtener datos de la entidad BlackRock
        logger.info("Fetching BlackRock entity data")
        entity_data = fetch_blackrock_entity(ARKHAM_API_KEY)
        if not entity_data:
            raise Exception("Failed to fetch BlackRock entity data")
        
        entity_id = entity_data.get('id', 'blackrock')
        entity_name = entity_data.get('name', 'BlackRock')
        tags = entity_data.get('populatedTags', [{"id": "fund", "label": "Fund"}])
        logger.info(f"Entity ID: {entity_id}, Name: {entity_name}")

        # Obtener balances y transacciones
        logger.info("Updating wallets")
        wallet_data = update_wallets(ARKHAM_API_KEY, entity_id)
        
        logger.info("Fetching transactions")
        raw_transactions = fetch_arkham_transactions(ARKHAM_API_KEY, entity_id, start_date, end_date)
        
        logger.info("Fetching historical prices")
        historical_prices = fetch_historical_prices(start_date, end_date)
        
        logger.info("Processing transactions")
        transactions = process_transactions(raw_transactions, historical_prices)

        # Obtener uso de exchanges
        logger.info("Fetching exchange usage")
        exchange_usage = fetch_arkham_exchange_usage(ARKHAM_API_KEY, entity_id, start_date, end_date)

        # Calcular holdings por cadena
        logger.info("Calculating holdings by chain")
        holdings_by_chain = {
            'BTC': {'balance': 0.0, 'balance_usd': 0.0, 'price': historical_prices['BTC'].get(end_date, 0.0)},
            'ETH': {'balance': 0.0, 'balance_usd': 0.0, 'price': historical_prices['ETH'].get(end_date, 0.0)},
            'USDC': {'balance': 0.0, 'balance_usd': 0.0, 'price': 1.0}
        }
        total_balance_usd = 0.0
        for wallet in wallet_data:
            token = wallet['token']
            if token in holdings_by_chain:
                holdings_by_chain[token]['balance'] += wallet['balance']
                holdings_by_chain[token]['balance_usd'] += wallet['balance_usd']
            total_balance_usd += wallet['balance_usd']

        output_data = {
            "type": "result",
            "profile": {
                "name": entity_name,
                "total_balance_usd": total_balance_usd,
                "tags": [tag['label'] for tag in tags]
            },
            "markets": markets,
            "holdings_by_chain": holdings_by_chain,
            "transactions": transactions,
            "exchange_usage": exchange_usage,
            "timestamp": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        }

        json_output = json.dumps(output_data, allow_nan=False)
        print(json_output)
        sys.stdout.flush()
        logger.info("BlackRock data fetched successfully")

        try:
            with open('blackrock_output.json', 'w') as f:
                json.dump(output_data, f, indent=2)
            logger.info("Data saved to blackrock_output.json")
        except Exception as e:
            logger.error(f"Failed to save blackrock_output.json: {e}")

        return output_data
    except Exception as e:
        error = {"error": f"Failed to fetch BlackRock data: {str(e)}"}
        logger.error(f"Error in main: {error['error']}")
        print(json.dumps(error))
        sys.stdout.flush()
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BlackRock data fetcher")
    parser.add_argument('--start-date', type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument('--end-date', type=str, help="End date (YYYY-MM-DD)")
    args = parser.parse_args()
    
    main(args.start_date, args.end_date)