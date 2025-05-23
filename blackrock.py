import sys
import json
import logging
import sqlite3
import yfinance as yf
import requests
from datetime import datetime, timedelta
import argparse
import warnings
import os

# Configuración inicial
sys.stderr = open('blackrock_errors.log', 'a')
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='blackrock.log',
    filemode='a'
)

# Constantes
DB_PATH = "whalescope.db"
ETHERSCAN_API_KEY = "RG5DUZDHP3DFBYAHM7HFJ1NZ78YS4GEHHJ"
USDC_CONTRACT = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
WALLETS = {
    'BTC': [
        {'address': '3MqUP6G1daVS5YTD8fz3QgwjZortWwxXFd', 'category': 'Coinbase BTC'},
        {'address': 'bc1q0rdpdg85zwqkltxjlfw9832x2wlzx7xll0gtru', 'category': 'BlackRock IBIT'},
    ],
    'ETH': [
        {'address': '0xceB69F6342eCE283b2F5c9088Ff249B5d0Ae66ea', 'category': 'Coinbase ETH'},
        {'address': '0x9645edD5BD30b6fB9447A17FAaA029056e6AD329', 'category': 'BlackRock ETHA'},
    ]
}

def init_db():
    """Inicializa las tablas de la base de datos para ETH y BTC."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS eth_wallets (
            address TEXT, token TEXT, balance REAL, balance_usd REAL, timestamp TEXT, category TEXT,
            PRIMARY KEY (address, token)
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS btc_wallets (
            address TEXT, balance_btc REAL, balance_usd REAL, timestamp TEXT, category TEXT,
            PRIMARY KEY (address)
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

        # Extraer análisis y recomendaciones
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
        
        

def fetch_crypto_prices():
    """Obtiene precios actuales de BTC y ETH desde Yahoo Finance."""
    tickers = {'BTC': 'BTC-USD', 'ETH': 'ETH-USD'}
    prices = {}
    try:
        for symbol, ticker in tickers.items():
            logging.info(f"Fetching price for {symbol}")
            stock = yf.Ticker(ticker)
            price = stock.info.get('regularMarketPrice', stock.info.get('previousClose', 0.0))
            prices[symbol] = float(price)
            logging.info(f"{symbol} price: ${price}")
        return prices
    except Exception as e:
        logging.error(f"Failed to fetch crypto prices: {e}")
        return {'BTC': 0.0, 'ETH': 0.0}

def fetch_eth_data(address, category, crypto_prices):
    """Obtiene balances de ETH y USDC para una dirección desde Etherscan."""
    eth_balance_url = f"https://api.etherscan.io/api?module=account&action=balance&address={address}&tag=latest&apikey={ETHERSCAN_API_KEY}"
    usdc_balance_url = f"https://api.etherscan.io/api?module=account&action=tokenbalance&contractaddress={USDC_CONTRACT}&address={address}&tag=latest&apikey={ETHERSCAN_API_KEY}"

    eth_balance = 0.0
    try:
        logging.info(f"Requesting ETH balance for {address}")
        response = requests.get(eth_balance_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        eth_balance = int(data['result']) / 10**18
        logging.info(f"ETH balance for {address}: {eth_balance} ETH")
    except requests.RequestException as e:
        logging.error(f"Failed to fetch ETH balance for {address}: {e}")

    usdc_balance = 0.0
    try:
        logging.info(f"Requesting USDC balance for {address}")
        response = requests.get(usdc_balance_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        usdc_balance = int(data['result']) / 10**6
        logging.info(f"USDC balance for {address}: {usdc_balance} USDC")
    except requests.RequestException as e:
        logging.error(f"Failed to fetch USDC balance for {address}: {e}")

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return [
        {
            'address': address,
            'token': 'ETH',
            'balance': float(eth_balance),
            'balance_usd': float(eth_balance * crypto_prices['ETH']),
            'timestamp': timestamp,
            'category': category
        },
        {
            'address': address,
            'token': 'USDC',
            'balance': float(usdc_balance),
            'balance_usd': float(usdc_balance),
            'timestamp': timestamp,
            'category': category
        }
    ]

def fetch_btc_balance(address, btc_price):
    """Obtiene el balance de BTC para una dirección desde Mempool."""
    try:
        url = f"https://mempool.space/api/address/{address}"
        logging.info(f"Requesting BTC balance for {address}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        balance_satoshi = data['chain_stats']['funded_txo_sum'] - data['chain_stats']['spent_txo_sum']
        balance_btc = balance_satoshi / 100_000_000
        logging.info(f"BTC balance for {address}: {balance_btc} BTC")
        return balance_btc, balance_btc * btc_price
    except requests.RequestException as e:
        logging.error(f"Failed to fetch BTC balance for {address}: {e}")
        return 0.0, 0.0

def update_wallets(crypto_prices):
    """Actualiza los datos de las billeteras ETH y BTC en la base de datos."""
    eth_wallet_data = []
    btc_wallet_data = []

    # Actualizar billeteras ETH
    try:
        for wallet in WALLETS['ETH']:
            wallets = fetch_eth_data(wallet['address'], wallet['category'], crypto_prices)
            eth_wallet_data.extend(wallets)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        for wallet in eth_wallet_data:
            cursor.execute('''INSERT OR REPLACE INTO eth_wallets (address, token, balance, balance_usd, timestamp, category)
                             VALUES (?, ?, ?, ?, ?, ?)''',
                          (wallet['address'], wallet['token'], wallet['balance'], wallet['balance_usd'], wallet['timestamp'], wallet['category']))
        conn.commit()
        logging.info(f"Inserted {len(eth_wallet_data)} ETH/USDC wallets")
    except Exception as e:
        logging.error(f"Failed to update ETH wallets: {e}")
    finally:
        conn.close()

    # Actualizar billeteras BTC
    try:
        btc_price = crypto_prices.get('BTC', 0.0)
        for wallet in WALLETS['BTC']:
            balance_btc, balance_usd = fetch_btc_balance(wallet['address'], btc_price)
            btc_wallet_data.append({
                'address': wallet['address'],
                'token': 'BTC',
                'balance': float(balance_btc),
                'balance_usd': float(balance_usd),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'category': wallet['category']
            })

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        for wallet in btc_wallet_data:
            cursor.execute('''INSERT OR REPLACE INTO btc_wallets (address, balance_btc, balance_usd, timestamp, category)
                             VALUES (?, ?, ?, ?, ?)''',
                          (wallet['address'], wallet['balance'], wallet['balance_usd'], wallet['timestamp'], wallet['category']))
        conn.commit()
        logging.info(f"Inserted {len(btc_wallet_data)} BTC wallets")
    except Exception as e:
        logging.error(f"Failed to update BTC wallets: {e}")
    finally:
        conn.close()

    return eth_wallet_data + btc_wallet_data

def main(start_date=None, end_date=None):
    """Función principal para obtener datos de BlackRock."""
    logger = logging.getLogger(__name__)
    try:
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        logger.info(f"Running blackrock.py from {start_date} to {end_date}")
        
        init_db()
        markets = fetch_market_stats()
        crypto_prices = fetch_crypto_prices()
        wallet_data = update_wallets(crypto_prices)

        output_data = {
            "type": "result",
            "markets": markets,
            "wallets": wallet_data,
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
        logger.error(error['error'])
        print(json.dumps(error))
        sys.stdout.flush()
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BlackRock data fetcher")
    parser.add_argument('--start-date', type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument('--end-date', type=str, help="End date (YYYY-MM-DD)")
    args = parser.parse_args()
    
    main(args.start_date, args.end_date)