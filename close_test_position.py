# close_test_position.py
import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

load_dotenv()
client = TradingClient(os.getenv("ALPACA_KEY"), os.getenv("ALPACA_SECRET"), paper=True)

result = client.close_position("SPY")
print(result)