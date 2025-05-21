#lido_staking.py

import requests
import sqlite3
from datetime import datetime
import os
import json
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# API Keys
CMC_API_KEY = "60c68e38-60f8-4d1e-87b1-33d8f6b6e0f2"
ETHERSCAN_API_KEY = "RG5DUZDHP3DFBYAHM7HFJ1NZ78YS4GEHHJ"
CMC_BASE_URL = "https://pro-api.coinmarketcap.com"
ETHERSCAN_BASE_URL = "https://api.etherscan.io/api"

# IDs para CoinMarketCap
IDS = {
    "STETH": {"cmc": 8085},
    "WSTETH": {"cmc": 12409},
    "ETH": {"cmc": 1027}
}

# Lido Smart Contract
LIDO_CONTRACT_ADDRESS = "0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84"

# Fecha actual
current_date = datetime.now()
current_date_str = current_date.strftime('%Y-%m-%d')

# Base de datos SQLite
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "whalescope_electron", "whalescope.db")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Crear tablas
cursor.execute('''CREATE TABLE IF NOT EXISTS liquid_staking_pools
                  (pool_name TEXT, total_eth_deposited REAL, eth_staked REAL, eth_unstaked REAL,
                   staking_rewards REAL, timestamp TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS eth_staking_queues
                  (queue_type TEXT, eth_amount REAL, avg_wait_time REAL, timestamp TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS eth_staking_ratio
                  (date TEXT, staking_ratio REAL, avg_rewards REAL, timestamp TEXT)''')
conn.commit()

# Configurar reintentos para requests
session = requests.Session()
retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

# Función para obtener datos de Etherscan
def fetch_etherscan_data(action, symbol=None, retries=3):
    print(f"Iniciando fetch_etherscan_data para {action}, symbol: {symbol}")
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
            print(f"Etherscan {action} para {symbol or 'ETH'}: {result} ETH")
            return result
        except Exception as e:
            print(f"Intento {attempt+1}/{retries} fallido para Etherscan {action}: {e}")
            if attempt == retries - 1:
                print(f"Error al obtener datos de Etherscan para {action} tras {retries} intentos.")
                return None
            time.sleep(0.5 * (attempt + 1))

# Función para obtener datos de CoinMarketCap
def fetch_cmc_data(cmc_id, symbol):
    print(f"Iniciando fetch_cmc_data para {symbol} (ID: {cmc_id})")
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
        print(f"Respuesta de CoinMarketCap para {symbol} (ID: {cmc_id}): {json.dumps(data, indent=2)}")
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
            raise ValueError(f"Invalid CoinMarketCap circulating supply for {symbol}: {adapted_data['data'][str(cmc_id)]['circulating_supply']}")
        if adapted_data["data"][str(cmc_id)]["quote"]["USD"]["price"] <= 0:
            raise ValueError(f"Invalid CoinMarketCap price for {symbol}: {adapted_data['data'][str(cmc_id)]['quote']['USD']['price']}")
        return adapted_data
    except Exception as e:
        print(f"Error al obtener datos de CoinMarketCap para {symbol} (ID: {cmc_id}): {e}")
        return None

# Función principal para obtener datos
def fetch_token_data(symbol):
    print(f"Iniciando fetch_token_data para {symbol}")
    cmc_id = IDS[symbol]["cmc"]
    data = fetch_cmc_data(cmc_id, symbol)
    if data and symbol == "ETH":
        eth_supply = fetch_etherscan_data("ethsupply")
        if eth_supply and eth_supply > 0:
            data["data"][str(cmc_id)]["circulating_supply"] = eth_supply
            print(f"Usando suministro de Etherscan para ETH: {eth_supply}")
    return data

# Función para obtener datos de Lido
def fetch_lido_data():
    print("=== Buscando Datos de Lido ===")
    try:
        steth_data = fetch_token_data("STETH")
        print("STETH data fetched:", steth_data is not None)
        wsteth_data = fetch_token_data("WSTETH")
        print("WSTETH data fetched:", wsteth_data is not None)
        eth_data = fetch_token_data("ETH")
        print("ETH data fetched:", eth_data is not None)

        if not (steth_data and wsteth_data and eth_data):
            print("No se pudieron obtener datos para STETH, WSTETH o ETH.")
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
            print(f"Error: Precio de STETH inválido ({steth_price_usd}).")
            return None
        wsteth_to_eth_ratio = wsteth_price_usd / steth_price_usd
        eth_staked = steth_supply + (wsteth_supply * wsteth_to_eth_ratio)

        eth_unstaked = fetch_etherscan_data("ethbalance", "LIDO")
        if not eth_unstaked or eth_unstaked <= 10000:
            print(f"eth_unstaked inválido o muy bajo: {eth_unstaked}. Usando valor por defecto.")
            eth_unstaked = 87479

        total_eth_deposited = eth_staked + eth_unstaked

        lido_api_url = "https://eth-api.lido.fi/v1/protocol/steth/apr/last"
        try:
            response = session.get(lido_api_url)
            response.raise_for_status()
            lido_response = response.json()
            print(f"Respuesta cruda de Lido API (fetch_lido_data): {json.dumps(lido_response, indent=2)}")
            apr = lido_response.get("data", {}).get("apr", 3.5) / 100
            print(f"APR obtenido de Lido: {apr*100}%")
        except Exception as e:
            print(f"No se pudo obtener el APR desde la API de Lido: {e}. Usando valor por defecto.")
            apr = 3.5 / 100

        staking_rewards = eth_staked * apr

        data = {
            "pool_name": "Lido",
            "total_eth_deposited": float(total_eth_deposited),
            "eth_staked": float(eth_staked),
            "eth_unstaked": float(eth_unstaked),
            "staking_rewards": float(staking_rewards),
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        print(f"Datos de Lido obtenidos: {json.dumps(data, indent=2)}")
        return data
    except Exception as e:
        print(f"Error al obtener datos de Lido: {e}")
        return None

# Función para obtener datos de colas de stake/unstake
def fetch_staking_queues():
    print("=== Buscando Datos de Colas de Stake/Unstake ===")
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
        print(f"Colas de Stake/Unstake: {json.dumps(queues, indent=2)}")
        return queues
    except Exception as e:
        print(f"Error al obtener datos de colas: {e}")
        return []

# Función para obtener el staking ratio y recompensas
def fetch_staking_ratio():
    print("=== Buscando Staking Ratio ===")
    try:
        eth_data = fetch_token_data("ETH")
        if not eth_data:
            print("No se pudieron obtener datos de ETH.")
            return None

        eth_info = eth_data["data"][str(IDS["ETH"]["cmc"])]
        total_supply = eth_info["circulating_supply"]
        if total_supply <= 0:
            print(f"Error: Suministro circulante de ETH inválido ({total_supply}).")
            return None

        steth_data = fetch_token_data("STETH")
        wsteth_data = fetch_token_data("WSTETH")
        if not (steth_data and wsteth_data):
            print("No se pudieron obtener datos de stETH/wstETH.")
            return None

        steth_info = steth_data["data"][str(IDS["STETH"]["cmc"])]
        wsteth_info = wsteth_data["data"][str(IDS["WSTETH"]["cmc"])]
        steth_supply = steth_info["circulating_supply"]
        wsteth_supply = wsteth_info["circulating_supply"]
        steth_price_usd = steth_info["quote"]["USD"]["price"]
        wsteth_price_usd = wsteth_info["quote"]["USD"]["price"]

        if steth_price_usd <= 0:
            print(f"Error: Precio de STETH inválido ({steth_price_usd}).")
            return None
        wsteth_to_eth_ratio = wsteth_price_usd / steth_price_usd
        eth_staked_total = steth_supply + (wsteth_supply * wsteth_to_eth_ratio)

        staking_ratio = eth_staked_total / total_supply

        lido_api_url = "https://eth-api.lido.fi/v1/protocol/steth/apr/last"
        try:
            response = session.get(lido_api_url)
            response.raise_for_status()
            lido_response = response.json()
            print(f"Respuesta cruda de Lido API (fetch_staking_ratio): {json.dumps(lido_response, indent=2)}")
            avg_rewards = lido_response.get("data", {}).get("apr", 3.5) / 100
            print(f"APR para staking ratio: {avg_rewards*100}%")
        except Exception as e:
            print(f"No se pudo obtener el APR desde la API de Lido: {e}. Usando valor por defecto.")
            avg_rewards = 3.5 / 100

        data = {
            "date": current_date_str,
            "staking_ratio": float(staking_ratio),
            "avg_rewards": float(avg_rewards),
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        print(f"Staking Ratio: {json.dumps(data, indent=2)}")
        return data
    except Exception as e:
        print(f"Error al obtener staking ratio: {e}")
        return None

# Guardar datos en la base de datos y generar JSON
def save_data():
    print("Iniciando save_data")
    lido_data = fetch_lido_data()
    queues = fetch_staking_queues()
    ratio_data = fetch_staking_ratio()

    # Guardar en la base de datos
    if lido_data:
        print("Guardando liquid_staking_pools")
        cursor.execute("""
            INSERT OR REPLACE INTO liquid_staking_pools (pool_name, total_eth_deposited, eth_staked, eth_unstaked, staking_rewards, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (lido_data["pool_name"], lido_data["total_eth_deposited"], lido_data["eth_staked"],
              lido_data["eth_unstaked"], lido_data["staking_rewards"], lido_data["timestamp"]))
        conn.commit()

    if queues:
        print("Guardando eth_staking_queues")
        for queue in queues:
            cursor.execute("""
                INSERT OR REPLACE INTO eth_staking_queues (queue_type, eth_amount, avg_wait_time, timestamp)
                VALUES (?, ?, ?, ?)
            """, (queue["queue_type"], queue["eth_amount"], queue["avg_wait_time"],
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()

    if ratio_data:
        print("Guardando eth_staking_ratio")
        cursor.execute("""
            INSERT OR REPLACE INTO eth_staking_ratio (date, staking_ratio, avg_rewards, timestamp)
            VALUES (?, ?, ?, ?)
        """, (ratio_data["date"], ratio_data["staking_ratio"], ratio_data["avg_rewards"],
              ratio_data["timestamp"]))
        conn.commit()

    # Generar JSON output compatible con blackrock.py
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
            "avg_rewards": ratio_data["avg_rewards"] * 100 if ratio_data else 3.5  # Convert to percentage
        },
        "analytics": {
            "staking_ratio": ratio_data["staking_ratio"] if ratio_data else 0,
            "queues": queues if queues else []
        },
        "charts": [],  # Add historical data if needed
        "news": [],    # Add news if needed
    }

    with open(os.path.join(BASE_DIR, "lido_output.json"), "w") as f:
        json.dump(output_data, f, indent=4)
    print("Datos guardados en lido_output.json.")

# Ejecutar y cerrar
try:
    save_data()
except Exception as e:
    print(f"Error general en la ejecución: {e}")
finally:
    print("Cerrando conexión a la base de datos")
    conn.close()
print("Datos de staking almacenados en whalescope.db.")