from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
import os
from dotenv import load_dotenv

load_dotenv()
client = StockHistoricalDataClient(os.getenv("ALPACA_KEY"), os.getenv("ALPACA_SECRET"))

request = StockBarsRequest(
    symbol_or_symbols="SPY",
    timeframe=TimeFrame.Minute,
    start="2026-08-01",
    end="2026-08-30",
)
bars = client.get_stock_bars(request)
df = bars.df
df.to_csv("strategy_engine/sample_data/SPY_1min_aug2026.csv")