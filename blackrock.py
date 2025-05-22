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

# Redirigir stderr a un archivo
sys.stderr = open('blackrock_errors.log', 'a')

# Suprimir advertencias
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Configurar logging a archivo
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='blackrock.log',
    filemode='a'
)

# Database setup
DB_PATH = "whalescope.db"

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS eth_wallets (
            address TEXT, token TEXT, balance REAL, balance_usd REAL, timestamp TEXT, category TEXT
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS btc_wallets (
            address TEXT, balance_btc REAL, balance_usd REAL, timestamp TEXT, category TEXT
        )''')
        conn.commit()
        conn.close()
        logging.info("Database tables initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize database: {e}")
        raise

def fetch_market_stats():
    ticker = 'IBIT'
    try:
        logging.info(f"Fetching market stats for {ticker} (Yahoo Finance)")
        stock = yf.Ticker(ticker)
        info = stock.info
        history = stock.history(period="7d")
        
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
        
        markets = {
            'price': float(price),
            'volume_24h': float(volume_24h),
            'market_cap': float(market_cap),
            'percent_change_24h': float(percent_change_24h),
            'percent_change_7d': float(percent_change_7d),
            'percent_change_30d': float(percent_change_30d),
            'last_updated': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
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
            'last_updated': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        }

def fetch_crypto_prices():
    tickers = {'BTC': 'BTC-USD', 'ETH': 'ETH-USD'}
    prices = {}
    
    try:
        for symbol, ticker in tickers.items():
            logging.info(f"Fetching current price for {symbol} (Yahoo Finance)")
            stock = yf.Ticker(ticker)
            price = stock.info.get('regularMarketPrice', stock.info.get('previousClose', 0.0))
            prices[symbol] = float(price)
            logging.info(f"Current {symbol} price: ${price}")
        return prices
    except Exception as e:
        logging.error(f"Failed to fetch crypto prices: {e}")
        return {'BTC': 0.0, 'ETH': 0.0}

def fetch_eth_data(address, category, crypto_prices):
    api_key = "RG5DUZDHP3DFBYAHM7HFJ1NZ78YS4GEHHJ"
    eth_balance_url = f"https://api.etherscan.io/api?module=account&action=balance&address={address}&tag=latest&apikey={api_key}"
    
    try:
        logging.info(f"Requesting ETH balance for {address}")
        response = requests.get(eth_balance_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        eth_balance = int(data['result']) / 10**18
        logging.info(f"[ETH] Balance for {address}: {eth_balance} ETH")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch ETH balance for {address}: {e}")
        eth_balance = 0.0

    usdc_balance_url = f"https://api.etherscan.io/api?module=account&action=tokenbalance&contractaddress=0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48&address={address}&tag=latest&apikey={api_key}"
    try:
        logging.info(f"Requesting USDC balance for {address}")
        response = requests.get(usdc_balance_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        usdc_balance = int(data['result']) / 10**6
        logging.info(f"[ETH] USDC Balance for {address}: {usdc_balance} USDC")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch USDC balance for {address}: {e}")
        usdc_balance = 0.0

    return [
        {
            'address': address,
            'token': 'ETH',
            'balance': float(eth_balance),
            'balance_usd': float(eth_balance * crypto_prices['ETH']),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'category': category
        },
        {
            'address': address,
            'token': 'USDC',
            'balance': float(usdc_balance),
            'balance_usd': float(usdc_balance),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'category': category
        }
    ]

def fetch_btc_balance(address, btc_price):
    try:
        url = f"https://mempool.space/api/address/{address}"
        logging.info(f"Requesting {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        balance_satoshi = data['chain_stats']['funded_txo_sum'] - data['chain_stats']['spent_txo_sum']
        balance_btc = balance_satoshi / 100_000_000
        logging.info(f"[BTC] Balance for {address}: {balance_btc} BTC")
        return balance_btc, balance_btc * btc_price
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch BTC balance for {address}: {e}")
        return 0.0, 0.0

def update_btc_data(crypto_prices):
    btc_wallets = [
        {'address': 'bc1qm34lsc65zpw79lxujrvu0xmk5f0g42r94v5j0', 'category': 'IBIT Bitcoin ETF'},
        {'address': '3EyjqW72h5H5aXG3NU6T3cT3cBT2uDX2T', 'category': 'Coinbase BTC'}
    ]

    btc_wallet_data = []
    btc_price = crypto_prices.get('BTC', 0.0)

    try:
        for wallet in btc_wallets:
            address = wallet['address']
            category = wallet['category']
            
            logging.info(f"[BTC] Fetching balance for {address}")
            balance_btc, balance_usd = fetch_btc_balance(address, btc_price)
            btc_wallet_data.append({
                'address': address,
                'token': 'BTC',
                'balance': float(balance_btc),
                'balance_usd': float(balance_usd),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'category': category
            })

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        for wallet in btc_wallet_data:
            cursor.execute('''INSERT OR REPLACE INTO btc_wallets (address, balance_btc, balance_usd, timestamp, category)
                             VALUES (?, ?, ?, ?, ?)''',
                          (wallet['address'], wallet['balance'], wallet['balance_usd'], wallet['timestamp'], wallet['category']))
        conn.commit()
        conn.close()
        
        logging.info(f"[BTC] {len(btc_wallet_data)} wallets inserted")
        return btc_wallet_data
    except Exception as e:
        logging.error(f"Failed to update BTC data: {e}")
        return []

def main(start_date=None, end_date=None):
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
        
        eth_wallets = [
            {'address': '0x5a52e96bacdabb82fd05763e25335261b270efcb', 'category': 'ETHA Ethereum ETF'},
            {'address': '0x28c6c06298d514db089934071355e5743bf21d60', 'category': 'Coinbase ETH'}
        ]
        
        eth_wallet_data = []
        for wallet in eth_wallets:
            wallets = fetch_eth_data(wallet['address'], wallet['category'], crypto_prices)
            eth_wallet_data.extend(wallets)
        
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            for wallet in eth_wallet_data:
                cursor.execute('''INSERT OR REPLACE INTO eth_wallets (address, token, balance, balance_usd, timestamp, category)
                                VALUES (?, ?, ?, ?, ?, ?)''',
                              (wallet['address'], wallet['token'], wallet['balance'], wallet['balance_usd'], wallet['timestamp'], wallet['category']))
            conn.commit()
            conn.close()
            logger.info(f"[ETH] {len(eth_wallet_data)} wallets inserted")
        except Exception as e:
            logger.error(f"Failed to save ETH wallets to database: {e}")
        
        btc_wallet_data = update_btc_data(crypto_prices)
        
        output_data = {
            "type": "result",
            "markets": markets,
            "wallets": eth_wallet_data + btc_wallet_data,
            "timestamp": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        }
        
        json_output = json.dumps(output_data, allow_nan=False)
        print(json_output)  # Usar print en lugar de sys.stdout.write
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
    parser.add_argument('--start-date', type=str, help="Start date for data (YYYY-MM-DD)")
    parser.add_argument('--end-date', type=str, help="End date for data (YYYY-MM-DD)")
    args = parser.parse_args()
    
    main(args.start_date, args.end_date)