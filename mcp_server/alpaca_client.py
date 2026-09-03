import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

load_dotenv()

client = TradingClient(os.getenv("ALPACA_KEY"), os.getenv("ALPACA_SECRET"), paper=True)
data_client = StockHistoricalDataClient(os.getenv("ALPACA_KEY"), os.getenv("ALPACA_SECRET"))

