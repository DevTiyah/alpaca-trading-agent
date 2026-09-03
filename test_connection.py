# test_connection.py
import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

load_dotenv()
client = TradingClient(os.getenv("ALPACA_KEY"), os.getenv("ALPACA_SECRET"), paper=True)
account = client.get_account()
print(account.status, account.buying_power)