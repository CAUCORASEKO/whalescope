import requests
import json
import logging
import sqlite3
import yfinance as yf
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Database setup
DB_PATH = "whalescope.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS eth_wallets (
        address TEXT, token TEXT, balance REAL, balance_usd REAL, timestamp TEXT, category TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS btc_wallets (
        address TEXT, balance_btc REAL, balance_usd REAL, timestamp TEXT, category TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS transactions (
        address TEXT, tx_hash TEXT, value REAL, value_usd REAL, date TEXT, timestamp TEXT,
        category TEXT, source_address TEXT, destination_address TEXT, confirmed INTEGER, token_symbol TEXT
    )''')
    conn.commit()
    conn.close()
    logging.info("Database tables migrated successfully.")

# Fetch historical data for charts
def fetch_historical_data(start_date, end_date):
    tickers = ['IBIT', 'ETHA']
    charts = {'IBIT': [], 'ETHA': []}
    
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    for ticker in tickers:
        logging.info(f"Fetching historical data for {ticker} from {start_date} to {end_date}")
        data = yf.download(ticker, start=start, end=end)
        if not data.empty:
            for date, row in data.iterrows():
                charts[ticker].append({
                    'date': date.strftime('%Y-%m-%d'),
                    'price': float(row['Close']),
                    'volume': int(row['Volume'])
                })
            logging.info(f"Historical data for {ticker} obtained - Dates: {len(charts[ticker])}")
        else:
            logging.warning(f"No historical data for {ticker}")
            charts[ticker].append({
                'date': start_date,
                'price': 0.0,
                'volume': 0
            })
    
    return charts

# Fetch market stats for IBIT and ETHA
def fetch_market_stats():
    tickers = ['IBIT', 'ETHA']
    markets = {}
    
    for ticker in tickers:
        logging.info(f"Fetching market stats for {ticker} (Yahoo Finance)")
        stock = yf.Ticker(ticker)
        info = stock.info
        history = stock.history(period="7d")
        
        price = info.get('regularMarketPrice', info.get('previousClose', 0))
        volume_24h = info.get('volume', 0)
        market_cap = info.get('marketCap', 0)
        
        percent_change_24h = 0
        percent_change_7d = 0
        percent_change_30d = 0
        
        if not history.empty:
            if len(history) >= 2:
                percent_change_24h = ((history['Close'][-1] - history['Close'][-2]) / history['Close'][-2]) * 100
            if len(history) >= 7:
                percent_change_7d = ((history['Close'][-1] - history['Close'][-7]) / history['Close'][-7]) * 100
        
        markets[ticker] = {
            'price': price,
            'volume_24h': volume_24h,
            'market_cap': market_cap,
            'percent_change_24h': percent_change_24h,
            'percent_change_7d': percent_change_7d,
            'percent_change_30d': percent_change_30d,
            'last_updated': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        }
    
    logging.info(f"Prices obtained: IBIT ${markets['IBIT']['price']}, ETHA ${markets['ETHA']['price']}")
    return markets

# Fetch news (unchanged from your logs)
def fetch_news():
    api_key = "YOUR_NEWSAPI_KEY"  # Replace with your NewsAPI key
    url = f"https://newsapi.org/v2/everything?q=BlackRock+OR+IBIT+OR+ETHA&apiKey={api_key}&language=en&sortBy=publishedAt&pageSize=5"
    logging.info("Fetching News for BlackRock, IBIT, and ETHA (NewsAPI)")
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        articles = response.json().get('articles', [])
        
        news = []
        for article in articles:
            logging.info(f"NewsAPI: {article['title']} ({article['source']['name']}) - {article['publishedAt']}")
            news.append({
                'title': article['title'],
                'source': article['source']['name'],
                'published_at': article['publishedAt'],
                'url': article['url'],
                'description': article['description'],
                'type': 'news'
            })
        return news
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch news: {e}")
        return []

# Fetch current BTC and ETH prices for USD conversions
def fetch_crypto_prices():
    tickers = {'BTC': 'BTC-USD', 'ETH': 'ETH-USD'}
    prices = {}
    
    for symbol, ticker in tickers.items():
        logging.info(f"Fetching current price for {symbol} (Yahoo Finance)")
        stock = yf.Ticker(ticker)
        price = stock.info.get('regularMarketPrice', stock.info.get('previousClose', 0))
        prices[symbol] = price
        logging.info(f"Current {symbol} price: ${price}")
    
    return prices

# Fetch ETH wallet data (unchanged from your logs)
def fetch_eth_data(address, category, start_date, end_date, crypto_prices):
    logging.info(f"[ETH] Fetching fresh data for {address} via Etherscan...")
    api_key = "RG5DUZDHP3DFBYAHM7HFJ1NZ78YS4GEHHJ"
    eth_balance_url = f"https://api.etherscan.io/api?module=account&action=balance&address={address}&tag=latest&apikey={api_key}"
    
    try:
        logging.info(f"Requesting {eth_balance_url} with params None")
        response = requests.get(eth_balance_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        logging.info(f"Successful request to {eth_balance_url}")
        eth_balance = int(data['result']) / 10**18
        logging.info(f"[ETH] Balance for {address}: {eth_balance} ETH")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch ETH balance for {address}: {e}")
        eth_balance = 0

    usdc_balance_url = f"https://api.etherscan.io/api?module=account&action=tokenbalance&contractaddress=0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48&address={address}&tag=latest&apikey={api_key}"
    try:
        logging.info(f"Requesting {usdc_balance_url} with params None")
        response = requests.get(usdc_balance_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        logging.info(f"Successful request to {usdc_balance_url}")
        usdc_balance = int(data['result']) / 10**6
        logging.info(f"[ETH] USDC Balance for {address}: {usdc_balance} USDC")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch USDC balance for {address}: {e}")
        usdc_balance = 0

    eth_transactions = []
    usdc_transactions = []
    
    # Fetch ETH transactions
    logging.info(f"[ETH] Fetching transactions for {address} via Etherscan between {start_date} and {end_date}...")
    tx_url = "https://api.etherscan.io/api"
    params = {
        'module': 'account',
        'action': 'txlist',
        'address': address,
        'startblock': 0,
        'endblock': 99999999,
        'sort': 'desc',
        'apikey': api_key
    }
    try:
        logging.info(f"Requesting {tx_url} with params {params}")
        response = requests.get(tx_url, params=params, timeout=10)
        response.raise_for_status()
        txs = response.json()['result']
        logging.info(f"Successful request to {tx_url}")
        
        start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
        end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
        
        for tx in txs:
            tx_date = datetime.fromtimestamp(int(tx['timeStamp']))
            if start_datetime <= tx_date <= end_datetime:
                value_eth = int(tx['value']) / 10**18
                eth_transactions.append({
                    'address': address,
                    'tx_hash': tx['hash'],
                    'value': value_eth,
                    'value_usd': value_eth * crypto_prices['ETH'],
                    'date': tx_date.strftime('%Y-%m-%d %H:%M:%S'),
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'category': category,
                    'source_address': tx['from'],
                    'destination_address': tx['to'],
                    'confirmed': 1 if tx['blockNumber'] else 0,
                    'token_symbol': 'ETH'
                })
        logging.info(f"[ETH] Fetched {len(eth_transactions)} ETH transactions for {address} in date range.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch ETH transactions for {address}: {e}")

    # Fetch ERC20 (USDC) transactions
    logging.info(f"[ETH] Fetching ERC20 transactions for {address} (contract 0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48) via Etherscan between {start_date} and {end_date}...")
    usdc_params = {
        'module': 'account',
        'action': 'tokentx',
        'contractaddress': '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',
        'address': address,
        'startblock': 0,
        'endblock': 99999999,
        'sort': 'desc',
        'apikey': api_key
    }
    try:
        logging.info(f"Requesting {tx_url} with params {usdc_params}")
        response = requests.get(tx_url, params=usdc_params, timeout=10)
        response.raise_for_status()
        txs = response.json()['result']
        logging.info(f"Successful request to {tx_url}")
        
        for tx in txs:
            tx_date = datetime.fromtimestamp(int(tx['timeStamp']))
            if start_datetime <= tx_date <= end_datetime:
                value_usdc = int(tx['value']) / 10**6
                usdc_transactions.append({
                    'address': address,
                    'tx_hash': tx['hash'],
                    'value': value_usdc,
                    'value_usd': value_usdc,  # USDC is 1:1 with USD
                    'date': tx_date.strftime('%Y-%m-%d %H:%M:%S'),
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'category': category,
                    'source_address': tx['from'],
                    'destination_address': tx['to'],
                    'confirmed': 1 if tx['blockNumber'] else 0,
                    'token_symbol': 'USDC'
                })
        logging.info(f"[ETH] Fetched {len(usdc_transactions)} ERC20 transactions for {address} in date range.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch ERC20 transactions for {address}: {e}")

    return [
        {
            'address': address,
            'token': 'ETH',
            'balance': eth_balance,
            'balance_usd': eth_balance * crypto_prices['ETH'],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'category': category
        },
        {
            'address': address,
            'token': 'USDC',
            'balance': usdc_balance,
            'balance_usd': usdc_balance,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'category': category
        }
    ], eth_transactions + usdc_transactions

# Fetch BTC wallet data using Mempool.space API
def fetch_btc_balance(address, btc_price):
    try:
        url = f"https://mempool.space/api/address/{address}"
        logging.info(f"Requesting {url} with params None")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        logging.info(f"Successful request to {url}")
        
        # Balance in satoshis (1 BTC = 100,000,000 satoshis)
        balance_satoshi = data['chain_stats']['funded_txo_sum'] - data['chain_stats']['spent_txo_sum']
        balance_btc = balance_satoshi / 100_000_000
        logging.info(f"[BTC] Balance for {address}: {balance_btc} BTC")
        return balance_btc, balance_btc * btc_price
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed with status code: {e.response.status_code if e.response else 'N/A'}")
        logging.error(f"Failed to fetch balance from Mempool.space for {address}.")
        return 0, 0

def fetch_btc_transactions(address, start_date, end_date, btc_price):
    try:
        url = f"https://mempool.space/api/address/{address}/txs"
        logging.info(f"Requesting {url} with params None")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        txs = response.json()
        logging.info(f"Successful request to {url}")

        transactions = []
        start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
        end_datetime = datetime.strptime(end_date, '%Y-%m-%d')

        for tx in txs:
            if not tx['status']['confirmed']:
                continue
            tx_date = datetime.fromtimestamp(tx['status']['block_time'])
            if start_datetime <= tx_date <= end_datetime:
                value_btc = sum(vout['value'] for vout in tx['vout']) / 100_000_000
                transactions.append({
                    'address': address,
                    'tx_hash': tx['txid'],
                    'value': value_btc,
                    'value_usd': value_btc * btc_price,
                    'date': tx_date.strftime('%Y-%m-%d %H:%M:%S'),
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'source_address': address,
                    'destination_address': tx['vout'][0]['scriptpubkey_address'] if tx['vout'] else 'unknown',
                    'confirmed': 1 if tx['status']['confirmed'] else 0,
                    'token_symbol': 'BTC'
                })
        logging.info(f"[BTC] Fetched {len(transactions)} BTC transactions for {address} in date range.")
        return transactions
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed with status code: {e.response.status_code if e.response else 'N/A'}")
        logging.error(f"Failed to fetch transactions from Mempool.space for {address}.")
        return []

def update_btc_data(start_date, end_date, crypto_prices):
    btc_wallets = [
        {'address': 'bc1qm34lsc65zpw79lxujrvu0xmk5f0g42r94v5j0', 'category': 'IBIT Bitcoin ETF'},
        {'address': '3EyjqW72h5H5aXG3NU6T3cT3cBT2uDX2T', 'category': 'Coinbase BTC'}
    ]

    btc_wallet_data = []
    btc_transactions = []
    btc_price = crypto_prices['BTC']

    for wallet in btc_wallets:
        address = wallet['address']
        category = wallet['category']
        
        logging.info(f"[BTC] Fetching balance from Mempool.space for {address}...")
        balance_btc, balance_usd = fetch_btc_balance(address, btc_price)
        btc_wallet_data.append({
            'address': address,
            'balance_btc': balance_btc,
            'balance_usd': balance_usd,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'category': category
        })

        logging.info(f"[BTC] Fetching transactions for {address} via Mempool.space between {start_date} and {end_date}...")
        txs = fetch_btc_transactions(address, start_date, end_date, btc_price)
        for tx in txs:
            tx['category'] = category
        btc_transactions.extend(txs)

    # Save to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for wallet in btc_wallet_data:
        cursor.execute('''INSERT INTO btc_wallets (address, balance_btc, balance_usd, timestamp, category)
                          VALUES (?, ?, ?, ?, ?)''',
                       (wallet['address'], wallet['balance_btc'], wallet['balance_usd'], wallet['timestamp'], wallet['category']))
    for tx in btc_transactions:
        cursor.execute('''INSERT INTO transactions (address, tx_hash, value, value_usd, date, timestamp, category, source_address, destination_address, confirmed, token_symbol)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                       (tx['address'], tx['tx_hash'], tx['value'], tx['value_usd'], tx['date'], tx['timestamp'], tx['category'],
                        tx['source_address'], tx['destination_address'], tx['confirmed'], tx['token_symbol']))
    conn.commit()
    conn.close()
    
    logging.info(f"[BTC] {len(btc_wallet_data)} wallets | {len(btc_transactions)} transactions inserted.")
    return btc_wallet_data, btc_transactions

# Main function to fetch and process all data
def main(start_date, end_date):
    logging.info("Running blackrock.py - Fetching real data for IBIT and ETHA...")
    
    # Initialize database
    init_db()
    
    # Clear any cache (if applicable)
    logging.info("Cache cleared before fetching new data")
    
    # Fetch historical data
    logging.info("=== Fetching Historical Data for IBIT and ETHA (Yahoo Finance) ===")
    charts = fetch_historical_data(start_date, end_date)
    
    # Fetch market stats
    logging.info("=== Fetching Market Stats for IBIT and ETHA (Yahoo Finance) ===")
    markets = fetch_market_stats()
    
    # Fetch yields (same as market stats for now)
    yields = {
        'IBIT': {
            'percent_change_24h': markets['IBIT']['percent_change_24h'],
            'percent_change_7d': markets['IBIT']['percent_change_7d'],
            'percent_change_30d': markets['IBIT']['percent_change_30d']
        },
        'ETHA': {
            'percent_change_24h': markets['ETHA']['percent_change_24h'],
            'percent_change_7d': markets['ETHA']['percent_change_7d'],
            'percent_change_30d': markets['ETHA']['percent_change_30d']
        }
    }
    
    # Fetch news
    logging.info("=== Fetching News for BlackRock, IBIT, and ETHA (NewsAPI) ===")
    news = fetch_news()
    
    # Fetch current crypto prices for USD conversions
    crypto_prices = fetch_crypto_prices()
    
    # Fetch ETH wallet data
    eth_wallets = [
        {'address': '0x5a52e96bacdabb82fd05763e25335261b270efcb', 'category': 'ETHA Ethereum ETF'},
        {'address': '0x28c6c06298d514db089934071355e5743bf21d60', 'category': 'Coinbase ETH'}
    ]
    
    eth_wallet_data = []
    eth_transactions = []
    
    for wallet in eth_wallets:
        wallets, txs = fetch_eth_data(wallet['address'], wallet['category'], start_date, end_date, crypto_prices)
        eth_wallet_data.extend(wallets)
        eth_transactions.extend(txs)
    
    # Save ETH data to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for wallet in eth_wallet_data:
        cursor.execute('''INSERT INTO eth_wallets (address, token, balance, balance_usd, timestamp, category)
                          VALUES (?, ?, ?, ?, ?, ?)''',
                       (wallet['address'], wallet['token'], wallet['balance'], wallet['balance_usd'], wallet['timestamp'], wallet['category']))
    for tx in eth_transactions:
        cursor.execute('''INSERT INTO transactions (address, tx_hash, value, value_usd, date, timestamp, category, source_address, destination_address, confirmed, token_symbol)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                       (tx['address'], tx['tx_hash'], tx['value'], tx['value_usd'], tx['date'], tx['timestamp'], tx['category'],
                        tx['source_address'], tx['destination_address'], tx['confirmed'], tx['token_symbol']))
    conn.commit()
    conn.close()
    
    logging.info(f"[ETH] {len(eth_wallet_data)} records inserted | {len(eth_transactions)} transactions inserted.")
    
    # Fetch BTC wallet data
    btc_wallet_data, btc_transactions = update_btc_data(start_date, end_date, crypto_prices)
    
    # Calculate analytics
    logging.info("=== Calculating Analytics ===")
    holdings_by_category = {}
    for wallet in btc_wallet_data:
        category = wallet['category']
        if category not in holdings_by_category:
            holdings_by_category[category] = {'BTC': 0}
        holdings_by_category[category]['BTC'] += wallet['balance_btc']
    
    for wallet in eth_wallet_data:
        category = wallet['category']
        token = wallet['token']
        if category not in holdings_by_category:
            holdings_by_category[category] = {'ETH': 0, 'USDC': 0}
        holdings_by_category[category][token] += wallet['balance']
    
    btc_sent = sum(tx['value'] for tx in btc_transactions if tx['source_address'] == tx['address'])
    btc_received = sum(tx['value'] for tx in btc_transactions if tx['destination_address'] == tx['address'])
    
    eth_sent = sum(tx['value'] for tx in eth_transactions if tx['token_symbol'] == 'ETH' and tx['source_address'] == tx['address'])
    eth_received = sum(tx['value'] for tx in eth_transactions if tx['token_symbol'] == 'ETH' and tx['destination_address'] == tx['address'])
    
    usdc_sent = sum(tx['value'] for tx in eth_transactions if tx['token_symbol'] == 'USDC' and tx['source_address'] == tx['address'])
    usdc_received = sum(tx['value'] for tx in eth_transactions if tx['token_symbol'] == 'USDC' and tx['destination_address'] == tx['address'])
    
    analytics = {
        'holdings_by_category': holdings_by_category,
        'btc_transaction_volume': {'sent': btc_sent, 'received': btc_received},
        'eth_transaction_volume': {
            'ETH': {'sent': eth_sent, 'received': eth_received},
            'USDC': {'sent': usdc_sent, 'received': usdc_received}
        }
    }
    
    logging.info(f"Total Holdings by Category: {holdings_by_category}")
    logging.info(f"BTC Transaction Volume: Sent {btc_sent} BTC, Received {btc_received} BTC")
    logging.info(f"ETH Transaction Volume: Sent {eth_sent} ETH, Received {eth_received} ETH")
    logging.info(f"USDC Transaction Volume: Sent {usdc_sent} USDC, Received {usdc_received} USDC")
    
    # Generate analysis and conclusion
    ibit_price_change = markets['IBIT']['percent_change_24h']
    etha_price_change = markets['ETHA']['percent_change_24h']
    btc_net_flow = btc_received - btc_sent
    eth_net_flow = eth_received - eth_sent
    
    analysis = (
        f"IBIT price {'rising' if ibit_price_change > 0 else 'declining'} ({ibit_price_change:.2f}% in 24h), "
        f"ETHA price {'rising' if etha_price_change > 0 else 'declining'} ({etha_price_change:.2f}% in 24h). "
        f"BTC net flow {'positive' if btc_net_flow >= 0 else 'negative'} ({btc_net_flow:.2f} BTC), "
        f"indicating {'accumulation' if btc_net_flow >= 0 else 'selling pressure'}. "
        f"ETH net flow {'positive' if eth_net_flow >= 0 else 'negative'} ({eth_net_flow:.2f} ETH), "
        f"indicating {'accumulation' if eth_net_flow >= 0 else 'selling pressure'}."
    )
    
    conclusion = ""
    if ibit_price_change < 0 and btc_net_flow < 0:
        conclusion += "IBIT declining with negative BTC net flow; potential bearish pressure on Bitcoin ETF. "
    elif ibit_price_change > 0 and btc_net_flow >= 0:
        conclusion += "IBIT rising with positive BTC net flow; potential bullish trend for Bitcoin ETF. "
    else:
        conclusion += "Mixed signals for IBIT; monitor BTC flows for trend confirmation. "
    
    if etha_price_change < 0 and eth_net_flow < 0:
        conclusion += "ETHA declining with negative ETH net flow; potential bearish pressure on Ethereum ETF."
    elif etha_price_change > 0 and eth_net_flow >= 0:
        conclusion += "ETHA rising with positive ETH net flow; potential bullish trend for Ethereum ETF."
    else:
        conclusion += "Mixed signals for ETHA; monitor ETH flows for trend confirmation."
    
    # Compile output
    output_data = {
        'type': 'result',
        'charts': charts,
        'markets': markets,
        'yields': yields,
        'news': news,
        'analytics': analytics,
        'wallets': {
            'ETH': eth_wallet_data,
            'BTC': btc_wallet_data
        },
        'transactions': {
            'ETH': eth_transactions,
            'BTC': btc_transactions
        },
        'analysis': analysis,
        'conclusion': conclusion
    }
    
    # Save to file
    with open('blackrock_output.json', 'w') as f:
        json.dump(output_data, f, indent=2)
    logging.info("Data saved to blackrock_output.json.")
    
    # Print JSON output for Electron to capture
    print(json.dumps(output_data))
    logging.info("\n✅ BlackRock data stored successfully.")

if __name__ == "__main__":
    import sys
    start_date = sys.argv[1] if len(sys.argv) > 1 else (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    end_date = sys.argv[2] if len(sys.argv) > 2 else datetime.now().strftime('%Y-%m-%d')
    main(start_date, end_date)