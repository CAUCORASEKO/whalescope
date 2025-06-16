import requests
import sqlite3
from datetime import datetime, timedelta
import os
import json
import time
import sys
import argparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# API Keys
CMC_API_KEY = "60c68e38-60f8-4d1e-87b1-33d8f6b6e0f2"
ETHERSCAN_API_KEY = "RG5DUZDHP3DFBYAHM7HFJ1NZ78YS4GEHHJ"
CMC_BASE_URL = "https://pro-api.coinmarketcap.com"
ETHERSCAN_BASE_URL = "https://api.etherscan.io/api"

# CoinMarketCap IDs
IDS = {
    "STETH": {"cmc": 8085},
    "WSTETH": {"cmc": 12409},
    "ETH": {"cmc": 1027}
}

# Lido Smart Contract
LIDO_CONTRACT_ADDRESS = "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84"

# Current date
current_date = datetime.now()
current_date_str = current_date.strftime('%Y-%m-%d')

# SQLite database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "whalescope.db")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Create tables
cursor.execute('''CREATE TABLE IF NOT EXISTS liquid_staking_pools
                  (pool_name TEXT, total_eth_deposited REAL, eth_staked REAL, eth_unstaked REAL,
                   staking_rewards REAL, timestamp TEXT, week_end TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS eth_staking_queues
                  (queue_type TEXT, eth_amount REAL, avg_wait_time REAL, timestamp TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS eth_staking_ratio
                  (date TEXT, staking_ratio REAL, avg_rewards REAL, timestamp TEXT)''')
conn.commit()

# Configure request retries
session = requests.Session()
retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

def fetch_etherscan_data(action, symbol=None, retries=3):
    print(f"Starting fetch_etherscan_data for {action}, symbol: {symbol}", file=sys.stderr)
    params = {
        "module": "stats" if action == "ethsupply" else "account",
        "action": "balance" if action == "ethbalance" else action,
        "apikey": ETHERSCAN_API_KEY
    }
    if action == "ethbalance" and symbol == "LIDO":
        params["address"] = LIDO_CONTRACT_ADDRESS
    for attempt in range(retries):
        try:
            time.sleep(0.2)
            response = session.get(ETHERSCAN_BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            if data["status"] != "1":
                raise ValueError(f"Etherscan error: {data.get('message', 'Unknown error')}")
            result = int(data["result"]) / 10**18
            print(f"Etherscan {action} for {symbol or 'ETH'}: {result} ETH", file=sys.stderr)
            return result
        except Exception as e:
            print(f"Attempt {attempt+1}/{retries} failed for Etherscan {action}: {e}", file=sys.stderr)
            if attempt == retries - 1:
                print(f"Failed to fetch Etherscan data for {action} after {retries} attempts.", file=sys.stderr)
                return None
            time.sleep(0.5 * (attempt + 1))

def fetch_cmc_data(cmc_id, symbol):
    print(f"Starting fetch_cmc_data for {symbol} (ID: {cmc_id})", file=sys.stderr)
    headers = {
        "X-CMC_PRO_API_KEY": CMC_API_KEY,
        "Accept": "application/json"
    }
    params = {
        "id": cmc_id,
        "convert": "USD"
    }
    url = f"{CMC_BASE_URL}/v1/cryptocurrency/quotes/latest"
    try:
        response = session.get(url, headers=headers, params=params)
        if response.status_code == 400:
            raise ValueError(f"HTTP 400: Invalid request for {symbol} (ID: {cmc_id})")
        response.raise_for_status()
        data = response.json()
        print(f"CoinMarketCap response for {symbol} (ID: {cmc_id}): {json.dumps(data, indent=2)}", file=sys.stderr)
        if "data" not in data or str(cmc_id) not in data["data"]:
            raise ValueError(f"Invalid CoinMarketCap response for {symbol}: missing data")
        adapted_data = {
            "data": {
                str(cmc_id): {
                    "circulating_supply": data["data"][str(cmc_id)].get("circulating_supply", 0),
                    "quote": {
                        "USD": {
                            "price": data["data"][str(cmc_id)]["quote"]["USD"].get("price", 0)
                        }
                    }
                }
            }
        }
        if adapted_data["data"][str(cmc_id)]["circulating_supply"] <= 0:
            raise ValueError(f"Invalid CoinMarketCap circulating supply for {symbol}")
        if adapted_data["data"][str(cmc_id)]["quote"]["USD"]["price"] <= 0:
            raise ValueError(f"Invalid CoinMarketCap price for {symbol}")
        return adapted_data
    except Exception as e:
        print(f"Error fetching CoinMarketCap data for {symbol} (ID: {cmc_id}): {e}", file=sys.stderr)
        return None

def fetch_token_data(symbol):
    print(f"Starting fetch_token_data for {symbol}", file=sys.stderr)
    cmc_id = IDS[symbol]["cmc"]
    data = fetch_cmc_data(cmc_id, symbol)
    if data and symbol == "ETH":
        eth_supply = fetch_etherscan_data("ethsupply")
        if eth_supply and eth_supply > 0:
            data["data"][str(cmc_id)]["circulating_supply"] = eth_supply
            print(f"Using Etherscan supply for ETH: {eth_supply}", file=sys.stderr)
    return data

def fetch_lido_data(week_end=None):
    print(f"=== Fetching Lido Data for week ending {week_end or 'current'} ===", file=sys.stderr)
    try:
        steth_data = fetch_token_data("STETH")
        print("STETH data fetched:", steth_data is not None, file=sys.stderr)
        wsteth_data = fetch_token_data("WSTETH")
        print("WSTETH data fetched:", wsteth_data is not None, file=sys.stderr)
        eth_data = fetch_token_data("ETH")
        print("ETH data fetched:", eth_data is not None, file=sys.stderr)

        if not (steth_data and wsteth_data and eth_data):
            print("Failed to fetch data for STETH, WSTETH, or ETH.", file=sys.stderr)
            return None

        steth_info = steth_data["data"][str(IDS["STETH"]["cmc"])]
        wsteth_info = wsteth_data["data"][str(IDS["WSTETH"]["cmc"])]
        eth_info = eth_data["data"][str(IDS["ETH"]["cmc"])]

        steth_supply = steth_info["circulating_supply"]
        wsteth_supply = wsteth_info["circulating_supply"]

        steth_price_usd = steth_info["quote"]["USD"]["price"]
        wsteth_price_usd = wsteth_info["quote"]["USD"]["price"]
        eth_price_usd = eth_info["quote"]["USD"]["price"]

        if steth_price_usd <= 0:
            print(f"Error: Invalid STETH price ({steth_price_usd}).", file=sys.stderr)
            return None
        wsteth_to_eth_ratio = wsteth_price_usd / steth_price_usd
        eth_staked = steth_supply + (wsteth_supply * wsteth_to_eth_ratio)

        eth_unstaked = fetch_etherscan_data("ethbalance", "LIDO")
        if not eth_unstaked or eth_unstaked <= 10000:
            print(f"Invalid or low eth_unstaked: {eth_unstaked}. Using default.", file=sys.stderr)
            eth_unstaked = 87479

        total_eth_deposited = eth_staked + eth_unstaked

        lido_api_url = "https://eth-api.lido.fi/v1/protocol/steth/apr/last"
        try:
            response = session.get(lido_api_url)
            response.raise_for_status()
            lido_response = response.json()
            print(f"Lido API raw response (fetch_lido_data): {json.dumps(lido_response, indent=2)}", file=sys.stderr)
            apr = lido_response.get("data", {}).get("apr", 3.5) / 100
            print(f"APR fetched from Lido: {apr*100}%", file=sys.stderr)
        except Exception as e:
            print(f"Failed to fetch APR from Lido API: {e}. Using default.", file=sys.stderr)
            apr = 3.5 / 100

        staking_rewards = eth_staked * apr

        data = {
            "pool_name": "Lido",
            "total_eth_deposited": float(total_eth_deposited),
            "eth_staked": float(eth_staked),
            "eth_unstaked": float(eth_unstaked),
            "staking_rewards": float(staking_rewards),
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "week_end": week_end or current_date_str
        }
        print(f"Lido data fetched: {json.dumps(data, indent=2)}", file=sys.stderr)
        return data
    except Exception as e:
        print(f"Error fetching Lido data: {e}", file=sys.stderr)
        return None

def fetch_staking_queues():
    print("=== Fetching Stake/Unstake Queue Data ===", file=sys.stderr)
    try:
        beaconchain_url = "https://beaconcha.in/api/v1/validators/queue"
        response = session.get(beaconchain_url)
        response.raise_for_status()
        queue_data = response.json()

        validators_to_enter = queue_data["data"]["beaconchain_entering"]
        validators_to_exit = queue_data["data"]["beaconchain_exiting"]
        eth_in_stake_queue = validators_to_enter * 32
        eth_in_unstake_queue = validators_to_exit * 32

        avg_wait_time_stake = 5.58 * 24 * 60 * 60
        avg_wait_time_unstake = 5.58 * 24 * 60 * 60

        queues = [
            {"queue_type": "stake", "eth_amount": float(eth_in_stake_queue), "avg_wait_time": float(avg_wait_time_stake)},
            {"queue_type": "unstake", "eth_amount": float(eth_in_unstake_queue), "avg_wait_time": float(avg_wait_time_unstake)}
        ]
        print(f"Stake/Unstake queues: {json.dumps(queues, indent=2)}", file=sys.stderr)
        return queues
    except Exception as e:
        print(f"Error fetching queue data: {e}", file=sys.stderr)
        return []

def fetch_staking_ratio():
    print("=== Fetching Staking Ratio ===", file=sys.stderr)
    try:
        eth_data = fetch_token_data("ETH")
        if not eth_data:
            print("Failed to fetch ETH data.", file=sys.stderr)
            return None

        eth_info = eth_data["data"][str(IDS["ETH"]["cmc"])]
        total_supply = eth_info["circulating_supply"]
        if total_supply <= 0:
            print(f"Error: Invalid ETH circulating supply ({total_supply}).", file=sys.stderr)
            return None

        steth_data = fetch_token_data("STETH")
        wsteth_data = fetch_token_data("WSTETH")
        if not (steth_data and wsteth_data):
            print("Failed to fetch stETH/wstETH data.", file=sys.stderr)
            return None

        steth_info = steth_data["data"][str(IDS["STETH"]["cmc"])]
        wsteth_info = wsteth_data["data"][str(IDS["WSTETH"]["cmc"])]
        steth_supply = steth_info["circulating_supply"]
        wsteth_supply = wsteth_info["circulating_supply"]
        steth_price_usd = steth_info["quote"]["USD"]["price"]
        wsteth_price_usd = wsteth_info["quote"]["USD"]["price"]

        if steth_price_usd <= 0:
            print(f"Error: Invalid STETH price ({steth_price_usd}).", file=sys.stderr)
            return None
        wsteth_to_eth_ratio = wsteth_price_usd / steth_price_usd
        eth_staked_total = steth_supply + (wsteth_supply * wsteth_to_eth_ratio)

        staking_ratio = eth_staked_total / total_supply

        lido_api_url = "https://eth-api.lido.fi/v1/protocol/steth/apr/last"
        try:
            response = session.get(lido_api_url)
            response.raise_for_status()
            lido_response = response.json()
            print(f"Lido API raw response (fetch_staking_ratio): {json.dumps(lido_response, indent=2)}", file=sys.stderr)
            avg_rewards = lido_response.get("data", {}).get("apr", 3.5) / 100
            print(f"APR for staking ratio: {avg_rewards*100}%", file=sys.stderr)
        except Exception as e:
            print(f"Failed to fetch APR from Lido API: {e}. Using default.", file=sys.stderr)
            avg_rewards = 3.5 / 100

        data = {
            "date": current_date_str,
            "staking_ratio": float(staking_ratio),
            "avg_rewards": float(avg_rewards),
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        print(f"Staking ratio: {json.dumps(data, indent=2)}", file=sys.stderr)
        return data
    except Exception as e:
        print(f"Error fetching staking ratio: {e}", file=sys.stderr)
        return None

def save_historical_data(start_date, end_date):
    print(f"Populating historical Lido data from {start_date} to {end_date}", file=sys.stderr)
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        if start > end:
            raise ValueError("Start date must be before or equal to end date")
        delta = end - start
        historical_data = []
        for i in range(0, delta.days + 1, 7):  # Weekly data
            week_end = (start + timedelta(days=i)).strftime('%Y-%m-%d')
            data = fetch_lido_data(week_end)
            if data:
                cursor.execute("""
                    INSERT OR REPLACE INTO liquid_staking_pools
                    (pool_name, total_eth_deposited, eth_staked, eth_unstaked, staking_rewards, timestamp, week_end)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (data["pool_name"], data["total_eth_deposited"], data["eth_staked"],
                      data["eth_unstaked"], data["staking_rewards"], data["timestamp"], week_end))
                historical_data.append({
                    "week_end": week_end,
                    "total_eth_deposited": data["total_eth_deposited"],
                    "eth_staked": data["eth_staked"],
                    "eth_unstaked": data["eth_unstaked"],
                    "staking_rewards": data["staking_rewards"]
                })
        conn.commit()
        return historical_data
    except Exception as e:
        print(f"Error in save_historical_data: {e}", file=sys.stderr)
        return []

def save_data(start_date=None, end_date=None):
    print("Starting save_data", file=sys.stderr)
    historical_data = []
    lido_data = None
    queues = []
    ratio_data = None

    try:
        if start_date and end_date:
            historical_data = save_historical_data(start_date, end_date)
        else:
            lido_data = fetch_lido_data()
            if lido_data:
                print("Saving liquid_staking_pools", file=sys.stderr)
                cursor.execute("""
                    INSERT OR REPLACE INTO liquid_staking_pools
                    (pool_name, total_eth_deposited, eth_staked, eth_unstaked, staking_rewards, timestamp, week_end)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (lido_data["pool_name"], lido_data["total_eth_deposited"], lido_data["eth_staked"],
                      lido_data["eth_unstaked"], lido_data["staking_rewards"], lido_data["timestamp"], current_date_str))
                conn.commit()

        queues = fetch_staking_queues()
        if queues:
            print("Saving eth_staking_queues", file=sys.stderr)
            for queue in queues:
                cursor.execute("""
                    INSERT OR REPLACE INTO eth_staking_queues
                    (queue_type, eth_amount, avg_wait_time, timestamp)
                    VALUES (?, ?, ?, ?)
                """, (queue["queue_type"], queue["eth_amount"], queue["avg_wait_time"],
                      datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()

        ratio_data = fetch_staking_ratio()
        if ratio_data:
            print("Saving eth_staking_ratio", file=sys.stderr)
            cursor.execute("""
                INSERT OR REPLACE INTO eth_staking_ratio
                (date, staking_ratio, avg_rewards, timestamp)
                VALUES (?, ?, ?, ?)
            """, (ratio_data["date"], ratio_data["staking_ratio"], ratio_data["avg_rewards"],
                  ratio_data["timestamp"]))
            conn.commit()

        output_data = {
            "markets": {
                "stETH": {
                    "total_eth_deposited": lido_data["total_eth_deposited"] if lido_data else 0,
                    "eth_staked": lido_data["eth_staked"] if lido_data else 0,
                    "eth_unstaked": lido_data["eth_unstaked"] if lido_data else 0,
                    "staking_rewards": lido_data["staking_rewards"] if lido_data else 0,
                    "last_updated": lido_data["timestamp"] if lido_data else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            },
            "yields": {
                "avg_rewards": ratio_data["avg_rewards"] * 100 if ratio_data else 3.5
            },
            "analytics": {
                "staking_ratio": ratio_data["staking_ratio"] if ratio_data else 0,
                "queues": queues if queues else []
            },
            "charts": historical_data
        }

        with open(os.path.join(BASE_DIR, "lido_output.json"), "w") as f:
            json.dump(output_data, f, indent=4)
        print("Data saved to lido_output.json", file=sys.stderr)
        return output_data

    except Exception as e:
        print(f"Error in save_data: {e}", file=sys.stderr)
        return {
            "markets": {"stETH": {"total_eth_deposited": 0, "eth_staked": 0, "eth_unstaked": 0, "staking_rewards": 0, "last_updated": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}},
            "yields": {"avg_rewards": 3.5},
            "analytics": {"staking_ratio": 0, "queues": []},
            "charts": [],
            "error": str(e)
        }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lido staking data fetcher")
    parser.add_argument('--start-date', type=str, help="Start date for historical data (YYYY-MM-DD)")
    parser.add_argument('--end-date', type=str, help="End date for historical data (YYYY-MM-DD)")
    args = parser.parse_args()

    try:
        output_data = save_data(start_date=args.start_date, end_date=args.end_date)
        print(json.dumps(output_data, indent=4))
    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=4), file=sys.stdout)
    finally:
        print("Closing database connection", file=sys.stderr)
        conn.close()
    sys.stdout.flush()