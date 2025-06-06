import sys
import sqlite3
import json
import logging
import pandas as pd
import argparse
from datetime import datetime

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('fetch_balance_data.log')]
)

# Ruta a la base de datos
DB_PATH = '/Users/mestizo/Desktop/whalescope/WhaleScope/whalescope.db'

def query_balances(start_date, end_date):
    """Query historical BTC and ETH balances from whalescope.db."""
    try:
        conn = sqlite3.connect(DB_PATH)
        query = """
        SELECT token, balance, balance_usd, timestamp
        FROM arkham_wallets
        WHERE entity_id = ? AND token IN ('BTC', 'ETH')
        AND timestamp >= ? AND timestamp <= ?
        ORDER BY timestamp
        """
        df = pd.read_sql_query(query, conn, params=('blackrock', start_date, end_date))
        conn.close()
        logging.info(f"Queried {len(df)} balance entries from database for {start_date} to {end_date}")
        return df
    except Exception as e:
        logging.error(f"Failed to query balances: {e}")
        return pd.DataFrame()

def format_data(df):
    """Format balance data as JSON."""
    if df.empty:
        return {'BTC': [], 'ETH': []}
    
    data = {'BTC': [], 'ETH': []}
    for token in ['BTC', 'ETH']:
        token_df = df[df['token'] == token]
        data[token] = [
            {'timestamp': row['timestamp'], 'balance': row['balance'], 'balance_usd': row['balance_usd']}
            for _, row in token_df.iterrows()
        ]
    logging.info(f"Formatted data: {len(data['BTC'])} BTC entries, {len(data['ETH'])} ETH entries")
    return data

def main():
    logging.info("Starting fetch_balance_data.py")
    parser = argparse.ArgumentParser(description="Fetch BlackRock balance data")
    parser.add_argument('--start-date', type=str, default='2025-05-01', help="Start date (YYYY-MM-DD)")
    parser.add_argument('--end-date', type=str, default='2025-06-05', help="End date (YYYY-MM-DD)")
    args = parser.parse_args()

    try:
        # Convert dates to timestamp format for SQLite
        start_timestamp = f"{args.start_date} 00:00:00"
        end_timestamp = f"{args.end_date} 23:59:59"
        df = query_balances(start_timestamp, end_timestamp)
        data = format_data(df)
        with open('blackrock_balances.json', 'w') as f:
            json.dump(data, f, indent=4)
        logging.info("Saved balance data to blackrock_balances.json")
        print(json.dumps(data))  # Output for IPC
    except Exception as e:
        logging.error(f"Error in main: {e}")
        print(json.dumps({'error': str(e)}))

if __name__ == "__main__":
    main()