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
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Configurar logging con rotación de archivos
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('blackrock.log', maxBytes=1024*1024, backupCount=5),
        logging.StreamHandler(sys.stderr)
    ]
)

# Constantes (leídas desde config.ini)
try:
    DB_PATH = config['DEFAULT']['DB_PATH']
    ARKHAM_API_KEY = config['API_KEYS']['ARKHAM_API_KEY']
except KeyError as e:
    logging.error(f"Error: Missing key in config.ini: {e}")
    sys.exit(1)

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS arkham_wallets (
            entity_id TEXT, token TEXT NOT NULL, balance REAL NOT NULL, balance_usd REAL NOT NULL, timestamp TEXT NOT NULL,
            PRIMARY KEY (entity_id, token, timestamp)
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS arkham_transactions (
            entity_id TEXT, date TEXT NOT NULL, type TEXT NOT NULL, amount REAL NOT NULL, amount_usd REAL NOT NULL,
            PRIMARY KEY (entity_id, date, type)
        )''')
        cursor.execute('''CREATE INDEX IF NOT EXISTS idx_wallets_timestamp 
                         ON arkham_wallets (entity_id, token, timestamp)''')
        conn.commit()
        logging.info("Database tables and indexes initialized successfully.")
    except Exception as e:
        logging.error(f"Error: Failed to initialize database: {e}")
        raise
    finally:
        conn.close()

def ensure_historical_wallet_data(api_key, entity_id, start_date, end_date, holdings_by_chain):
    try:
        logging.info(f"Processing historical wallet data for {entity_id} from {start_date} to {end_date}")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')

        # Limpiar entradas antiguas
        cursor.execute('''
            DELETE FROM arkham_wallets 
            WHERE entity_id = ? 
            AND timestamp BETWEEN ? AND ?
        ''', (entity_id, start.strftime('%Y-%m-%d 00:00:00'), end.strftime('%Y-%m-%d 23:59:59')))
        conn.commit()
        logging.info(f"Cleared existing wallet entries for {entity_id} from {start_date} to {end_date}")

        # Poblar con holdings_by_chain
        logging.info(f"Populating historical wallet data for {entity_id}")
        balances = [
            {'symbol': 'BTC', 'balance': holdings_by_chain['BTC']['balance'], 'usd': holdings_by_chain['BTC']['balance_usd']},
            {'symbol': 'ETH', 'balance': holdings_by_chain['ETH']['balance'], 'usd': holdings_by_chain['ETH']['balance_usd']},
            {'symbol': 'USDC', 'balance': holdings_by_chain['USDC']['balance'], 'usd': holdings_by_chain['USDC']['balance_usd']}
        ]
        # Validar API balances
        api_balances = fetch_arkham_balances(api_key, entity_id)
        if api_balances:
            for balance in api_balances:
                token = balance.get('symbol', '').upper()
                amount = float(balance.get('balance', 0))
                if token in ['BTC', 'ETH'] and amount > holdings_by_chain.get(token, {}).get('balance', 0) * 2:
                    logging.debug(f"Using API balance for {token}: {amount}")
                    for b in balances:
                        if b['symbol'].upper() == token:
                            b['balance'] = amount
                            b['usd'] = float(balance.get('usd', 0))

        delta = end - start
        inserted = 0
        for i in range(0, delta.days + 1, 7):  # Weekly
            timestamp = (start + timedelta(days=i)).strftime('%Y-%m-%d 12:00:00')
            for balance in balances:
                token = balance.get('symbol', '')
                amount = float(balance.get('balance', 0))
                amount_usd = float(balance.get('usd', 0))
                cursor.execute('''
                    INSERT OR REPLACE INTO arkham_wallets (entity_id, token, balance, balance_usd, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                ''', (entity_id, token, amount, amount_usd, timestamp))
                inserted += 1
        conn.commit()
        logging.info(f"Populated {inserted} historical wallet entries")
        
        conn.close()
    except Exception as e:
        logging.error(f"Error: Failed to ensure historical wallet data: {e}")
        if 'conn' in locals():
            conn.close()

def fetch_historical_balances(entity_id, start_date, end_date):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        logging.info(f"Fetching weekly historical balances for entity {entity_id} from {start_date} to {end_date}")
        
        start_datetime = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y-%m-%d 00:00:00')
        end_datetime = datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m-%d 23:59:59')
        
        cursor.execute('''
            SELECT token, balance, balance_usd, timestamp,
                   strftime('%Y-%W', timestamp) as week
            FROM (
                SELECT token, balance, balance_usd, timestamp,
                       ROW_NUMBER() OVER (PARTITION BY token, strftime('%Y-%W', timestamp) 
                                         ORDER BY timestamp DESC) as rn
                FROM arkham_wallets 
                WHERE entity_id = ? AND token IN ('BTC', 'ETH')
                AND timestamp BETWEEN ? AND ?
            )
            WHERE rn = 1
            ORDER BY timestamp
        ''', (entity_id, start_datetime, end_datetime))
        
        balances = {'BTC': [], 'ETH': []}
        for row in cursor.fetchall():
            token, balance, balance_usd, timestamp, week = row
            year, week_num = map(int, week.split('-'))
            week_end = datetime.strptime(f'{year}-W{week_num}-6', '%Y-W%W-%w').strftime('%Y-%m-%d')
            balances[token].append({
                'week_end': week_end,
                'balance': float(balance),
                'balance_usd': float(balance_usd)
            })
        
        logging.info(f"Fetched {len(balances['BTC'])} weekly BTC and {len(balances['ETH'])} weekly ETH balances")
        conn.close()
        return balances
    except Exception as e:
        logging.error(f"Error: Failed to fetch historical balances: {e}")
        if 'conn' in locals():
            conn.close()
        return {'BTC': [], 'ETH': []}

def fetch_historical_total_balance(entity_id, start_date, end_date):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        logging.info(f"Fetching weekly historical total balance for entity {entity_id} from {start_date} to {end_date}")
        
        start_datetime = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y-%m-%d 00:00:00')
        end_datetime = datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m-%d 23:59:59')
        
        cursor.execute('''
            SELECT strftime('%Y-%W', timestamp) as week,
                   SUM(balance_usd) as total_balance_usd
            FROM arkham_wallets
            WHERE entity_id = ?
            AND timestamp BETWEEN ? AND ?
            GROUP BY strftime('%Y-%W', timestamp)
            ORDER BY timestamp
        ''', (entity_id, start_datetime, end_datetime))
        
        total_balances = []
        for row in cursor.fetchall():
            week, total_balance_usd = row
            year, week_num = map(int, week.split('-'))
            week_end = datetime.strptime(f'{year}-W{week_num}-6', '%Y-W%W-%w').strftime('%Y-%m-%d')
            total_balances.append({
                'week_end': week_end,
                'total_balance_usd': float(total_balance_usd)
            })
        
        logging.info(f"Fetched {len(total_balances)} weekly total balances")
        conn.close()
        return total_balances
    except Exception as e:
        logging.error(f"Error: Failed to fetch historical total balance: {e}")
        if 'conn' in locals():
            conn.close()
        return {}

def fetch_market_stats(ticker='IBIT', end_date=None):
    try:
        logging.info(f"Fetching market stats for {ticker} with end_date {end_date}")
        stock = yf.Ticker(ticker)
        info = stock.info
        # Optional: Hardcode $418.18 for June 5, 2025
        # if end_date == '2025-06-05':
        #     price = 418.18
        #     logging.debug(f"Using hardcoded price for {end_date}: ${price}")
        # else:
        price = info.get('regularMarketPrice', info.get('previousClose', 0.0))
        logging.debug(f"Using yfinance price for {end_date}: ${price}")
        history = stock.history(period="30d")
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
        logging.error(f"Error: Failed to fetch market stats: {e}")
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
    prices = {'BTC': {}, 'ETH': {}}
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        days = (end - start).days + 1
        logging.info(f"Fetching historical prices for {days} days from {start_date} to {end_date}")
        for coin in ['BTC', 'ETH']:
            logging.info(f"Fetching historical prices for {coin} from CoinGecko")
            coin_id = 'bitcoin' if coin == 'BTC' else 'ethereum'
            start_timestamp = int(start.timestamp())
            end_timestamp = int(end.timestamp())
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart/range?vs_currency=usd&from={start_timestamp}&to={end_timestamp}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            logging.debug(f"CoinGecko response for {coin}: {data}")
            price_data = data.get('prices', [])
            for timestamp_ms, price in price_data:
                date = datetime.fromtimestamp(timestamp_ms / 1000).strftime('%Y-%m-%d')
                prices[coin][date] = price
            logging.info(f"Fetched {len(prices[coin])} prices for {coin} from CoinGecko")
    except Exception as e:
        logging.error(f"Error: Failed to fetch historical prices from CoinGecko: {str(e)}")
        logging.info("Falling back to hardcoded prices")
        prices = {
            'BTC': {end_date: 102323.0},
            'ETH': {end_date: 2445.21}
        }
        logging.warning(f"Using hardcoded prices for {end_date}: BTC=$102323, ETH=$2445.21")
    return prices

def check_api_key(api_key):
    base_url = "https://api.arkm.com"
    endpoint = f"{base_url}/health"
    headers = {
        "API-Key": api_key,
        "Content-Type": "application/json",
        "User-Agent": "WhaleScope/1.0 (TestScript)"
    }
    try:
        logging.info(f"Checking API key validity at {endpoint}")
        response = requests.get(endpoint, headers=headers, timeout=10)
        response.raise_for_status()
        logging.info(f"API key is valid. Response: {response.text}")
        return True
    except requests.RequestException as e:
        error_message = f"Error: Failed to validate API key: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            error_message += f" | Status Code: {e.response.status_code} | Response: {e.response.text}"
        logging.error(error_message)
        return False

def fetch_blackrock_entity(api_key):
    base_url = "https://api.arkm.com"
    endpoint = f"{base_url}/intelligence/entity/blackrock"
    headers = {
        "API-Key": api_key,
        "Content-Type": "application/json",
        "User-Agent": "WhaleScope/1.0 (BlackRockScript)"
    }
    try:
        logging.info(f"Fetching BlackRock entity data from {endpoint}")
        time.sleep(0.1)
        response = requests.get(endpoint, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        logging.debug(f"Raw API response: {json.dumps(data, indent=2)}")
        entity_id = data.get('id')
        if not entity_id:
            logging.error(f"Error: No id found in BlackRock entity data: {data}")
            return None
        logging.info(f"Successfully fetched BlackRock entity data: {data}")
        return data
    except requests.RequestException as e:
        error_message = f"Error: Failed to fetch BlackRock entity data: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            error_message += f" | Status Code: {e.response.status_code} | Response: {e.response.text}"
            if e.response.status_code == 401:
                error_message += " | Please verify your API key at https://info.arkm.com/api-platform"
        logging.error(error_message)
        return None

def fetch_arkham_balances(api_key, entity_id):
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
        logging.debug(f"Raw balances response: {json.dumps(data, indent=2)}")
        balances = []
        balances_dict = data.get('balances', {})
        for chain in balances_dict:
            chain_balances = balances_dict.get(chain, [])
            if isinstance(chain_balances, list):
                for balance in chain_balances:
                    if 'symbol' in balance and 'balance' in balance and 'usd' in balance:
                        logging.debug(f"Balance found: symbol={balance.get('symbol')}, balance={balance.get('balance')}, usd={balance.get('usd')}")
                        balances.append(balance)
                    else:
                        logging.warning(f"Incomplete balance data: {balance}")
        logging.info(f"Fetched {len(balances)} balances from Arkham")
        return balances
    except requests.RequestException as e:
        error_message = f"Error: Failed to fetch balances from Arkham: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            error_message += f" | Status Code: {e.response.status_code} | Response: {e.response.text}"
        logging.error(error_message)
        return []

def fetch_arkham_transactions(api_key, entity_id, start_date, end_date):
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
        logging.debug(f"Raw transactions response: {json.dumps(data, indent=2)}")
        transactions = data.get('transfers', [])
        logging.info(f"Fetched {len(transactions)} transactions from Arkham")
        return transactions
    except requests.RequestException as e:
        error_message = f"Error: Failed to fetch transactions from Arkham: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            error_message += f" | Status Code: {e.response.status_code} | Response: {e.response.text}"
        logging.error(error_message)
        return []

def fetch_arkham_exchange_usage(api_key, entity_id, start_date, end_date):
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
        logging.error(f"Error: Failed to process exchange usage: {str(e)}")
        return {"deposits": {"total": 0, "summary": []}, "withdrawals": {"total": 0, "summary": []}}

def process_transactions(transactions, historical_prices):
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
    balances = fetch_arkham_balances(api_key, entity_id)
    wallet_data = []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logging.debug(f"Processing {len(balances)} balances from Arkham API")
        for balance in balances:
            token = balance.get('symbol', balance.get('tokenSymbol', 'UNKNOWN')).upper()
            amount = float(balance.get('balance', 0))
            amount_usd = float(balance.get('usd', balance.get('usdValue', 0)))
            logging.debug(f"Inserting balance: token={token}, amount={amount}, usd={amount_usd}")
            wallet_data.append({
                'entity_id': entity_id,
                'token': token,
                'balance': amount,
                'balance_usd': amount_usd,
                'timestamp': timestamp
            })
            cursor.execute('''
                INSERT OR REPLACE INTO arkham_wallets (entity_id, token, balance, balance_usd, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (entity_id, token, amount, amount_usd, timestamp))
        conn.commit()
        logging.info(f"Inserted {len(wallet_data)} wallet entries")
        logging.debug(f"Wallet data: {wallet_data}")
    except Exception as e:
        logging.error(f"Error: Failed to update wallets in database: {e}")
    finally:
        conn.close()
    return wallet_data

def main(start_date=None, end_date=None):
    logger = logging.getLogger(__name__)
    logger.info("Starting blackrock.py")
    try:
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        logger.info(f"Running from {start_date} to {end_date}")
        init_db()
        logger.info("Database initialized")
        markets = fetch_market_stats(end_date=end_date)
        logger.info("Fetched market stats")
        logger.info("Checking API key")
        if not check_api_key(ARKHAM_API_KEY):
            raise Exception("Invalid API key")
        logger.info("Fetching BlackRock entity data")
        entity_data = fetch_blackrock_entity(ARKHAM_API_KEY)
        if not entity_data:
            raise Exception("Failed to fetch BlackRock entity data")
        entity_id = entity_data.get('id', 'blackrock')
        entity_name = entity_data.get('name', 'BlackRock')
        tags = entity_data.get('populatedTags', [{"id": "fund", "label": "Fund"}])
        logger.info(f"Entity ID: {entity_id}, Name: {entity_name}")
        logger.info("Updating wallets")
        wallet_data = update_wallets(ARKHAM_API_KEY, entity_id)
        logger.debug(f"Wallet data updated: {wallet_data}")
        holdings_by_chain = {
            'BTC': {'balance': 660594.7921210106, 'balance_usd': 67610980194.29366, 'price': 0.0},
            'ETH': {'balance': 1425463.6848275263, 'balance_usd': 3485472528.956026, 'price': 0.0},
            'USDC': {'balance': 2.229759, 'balance_usd': 2.229759, 'price': 1.0}
        }
        total_balance_usd = sum(holdings_by_chain[token]['balance_usd'] for token in holdings_by_chain)
        logger.info("Ensuring historical wallet data")
        ensure_historical_wallet_data(ARKHAM_API_KEY, entity_id, start_date, end_date, holdings_by_chain)
        logger.info("Fetching transactions")
        raw_transactions = fetch_arkham_transactions(ARKHAM_API_KEY, entity_id, start_date, end_date)
        logger.info("Fetching historical prices")
        historical_prices = fetch_historical_prices(start_date, end_date)
        logger.info("Processing transactions")
        transactions = process_transactions(raw_transactions, historical_prices)
        logger.info("Fetching exchange usage")
        exchange_usage = fetch_arkham_exchange_usage(ARKHAM_API_KEY, entity_id, start_date, end_date)
        logger.info("Fetching historical balances")
        historical_balances = fetch_historical_balances(entity_id, start_date, end_date)
        logger.info("Fetching historical total balance")
        historical_total_balance = fetch_historical_total_balance(entity_id, start_date, end_date)
        logger.info("Calculating holdings by chain")
        holdings_by_chain['BTC']['price'] = historical_prices['BTC'].get(end_date, 0.0)
        holdings_by_chain['ETH']['price'] = historical_prices['ETH'].get(end_date, 0.0)
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
            "historical_balances": historical_balances,
            "historical_total_balance": historical_total_balance,
            "timestamp": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        }
        logger.info("Outputting result")
        logger.debug(f"Final output data: {json.dumps(output_data, indent=2)}")
        json_output = json.dumps(output_data, allow_nan=False)
        print(json_output)
        sys.stdout.flush()
        try:
            with open('blackrock_output.json', 'w') as f:
                json.dump(output_data, f, indent=2)
            logger.info("Data saved to blackrock_output.json")
        except Exception as e:
            logger.error(f"Error: Failed to save blackrock_output.json: {e}")
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