from fastmcp import FastMCP
from datetime import datetime, timedelta
import sys
import os
import traceback
from dotenv import load_dotenv

# Load environment variables from project root's .env file FIRST
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# This MUST come before the `from rules import ...` line below,
# since Python resolves imports top-to-bottom.
sys.path.append(os.path.join(PROJECT_ROOT, "strategy_engine"))
sys.path.append(os.path.dirname(__file__))  # if risk_engine.py is in the same folder

# Initialize MCP server FIRST before any imports that might fail
mcp = FastMCP("liqwid-trading-agent")

# Now try to import dependencies
try:
    import pandas as pd
    import numpy as np
    from alpaca_client import client, data_client
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from alpaca.data.enums import DataFeed
    from rules import scan_signals as _scan_signals, score_conviction as _score_conviction
    from risk_engine import check_risk as _check_risk
    from alpaca.trading.requests import MarketOrderRequest, TakeProfitRequest, StopLossRequest
    from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
    from alpaca.trading.requests import LimitOrderRequest
except Exception as e:
    # Log the error and exit gracefully
    print(f"ERROR: Failed to initialize server dependencies: {e}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)

def _sanitize(obj):
    """Recursively convert NumPy types to native Python types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    else:
        return obj


def _get_account_data() -> dict:
    """Plain function - not an MCP tool."""
    account = client.get_account()
    return {
        "status": str(account.status),
        "buying_power": account.buying_power,
        "cash": account.cash,
        "portfolio_value": account.portfolio_value,
    }


def _get_positions_data() -> list[dict]:
    """Plain function - not an MCP tool."""
    positions = client.get_all_positions()
    return [{"symbol": p.symbol, "qty": p.qty, "side": p.side, "market_value": p.market_value} for p in positions]

def _place_order_data(symbol: str, side: str, qty: float, order_type: str = "market",
                       limit_price: float = None,
                       stop_loss: float = None, take_profit: float = None) -> dict:
    """
    Submits a market or limit order. If both stop_loss and take_profit are given,
    submits as a bracket order (entry + attached SL/TP legs in one call).
    """
    order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL

    order_class = OrderClass.SIMPLE
    take_profit_req = None
    stop_loss_req = None

    if stop_loss is not None and take_profit is not None:
        order_class = OrderClass.BRACKET
        take_profit_req = TakeProfitRequest(limit_price=round(take_profit, 2))
        stop_loss_req = StopLossRequest(stop_price=round(stop_loss, 2))

    common_args = dict(
        symbol=symbol,
        qty=qty,
        side=order_side,
        time_in_force=TimeInForce.DAY,
        order_class=order_class,
        take_profit=take_profit_req,
        stop_loss=stop_loss_req,
    )

    if order_type.lower() == "limit":
        if limit_price is None:
            raise ValueError("limit_price is required for limit orders")
        order_data = LimitOrderRequest(limit_price=round(limit_price, 2), **common_args)
    else:
        order_data = MarketOrderRequest(**common_args)

    order = client.submit_order(order_data)

    return {
        "id": str(order.id),
        "symbol": order.symbol,
        "qty": str(order.qty),
        "side": str(order.side),
        "status": str(order.status),
        "order_class": str(order.order_class),
        "submitted_at": str(order.submitted_at),
    }



def _cancel_order_data(order_id: str) -> dict:
    client.cancel_order_by_id(order_id)
    return {"order_id": order_id, "cancelled": True}


@mcp.tool
def get_account() -> dict:
    """Return current paper account state."""
    return _get_account_data()


@mcp.tool
def get_positions() -> list[dict]:
    """Return current open positions."""
    return _get_positions_data()

# @mcp.tool
# def get_market_data(symbol: str, timeframe: str = "1Min", lookback_minutes: int = 500) -> list[dict]:
#     """Fetch recent OHLCV bars for a symbol."""
#     tf_map = {"1Min": TimeFrame.Minute, "15Min": TimeFrame(15, "Min"), "1Hour": TimeFrame.Hour}
#     tf = tf_map.get(timeframe, TimeFrame.Minute)

#     end = datetime.now()
#     start = end - timedelta(minutes=lookback_minutes * 2)  # buffer for non-trading hours

#     request = StockBarsRequest(symbol_or_symbols=symbol, timeframe=tf, start=start, end=end, feed=DataFeed.IEX)
#     bars = data_client.get_stock_bars(request)
#     df = bars.df.reset_index()

#     return df.to_dict(orient="records")

def _fetch_bars(symbol: str, timeframe: str = "1Min", lookback_minutes: int = 500) -> list[dict]:
    """Plain function, not an MCP tool - does the actual data fetching."""
    tf_map = {"1Min": TimeFrame.Minute, "15Min": TimeFrame(15, "Min"), "1Hour": TimeFrame.Hour}
    tf = tf_map.get(timeframe, TimeFrame.Minute)

    end = datetime.now()
    start = end - timedelta(minutes=lookback_minutes * 2)

    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=tf,
        start=start,
        end=end,
        feed=DataFeed.IEX,
    )
    bars = data_client.get_stock_bars(request)
    df = bars.df.reset_index()
    return df.to_dict(orient="records")


@mcp.tool
def get_market_data(symbol: str, timeframe: str = "1Min", lookback_minutes: int = 500) -> list[dict]:
    """Fetch recent OHLCV bars for a symbol."""
    return _fetch_bars(symbol, timeframe, lookback_minutes)


@mcp.tool
def scan_signals(symbol: str = "SPY") -> list[dict]:
    """Scan for valid SH+BMS+RTO trading signals using live market data."""
    raw_bars = _fetch_bars(symbol, timeframe="1Min", lookback_minutes=500)
    df = pd.DataFrame(raw_bars)
    signals = _scan_signals(df, symbol=symbol)
    return _sanitize(signals)


@mcp.tool
def score_conviction(signal: dict) -> dict:
    """Score a signal's conviction level (0-100) with reasoning."""
    result = _score_conviction(signal)
    return _sanitize(result)

@mcp.tool
def check_risk(signal: dict) -> dict:
    """Risk gate - approves/rejects a signal and calculates position size."""
    account = _get_account_data()
    positions = _get_positions_data()
    result = _check_risk(signal, account, positions)
    return _sanitize(result)


@mcp.tool
def place_order(symbol: str, side: str, qty: float, order_type: str = "market",
                 limit_price: float = None,
                 stop_loss: float = None, take_profit: float = None) -> dict:
    """Submit a market or limit order (with optional bracket SL/TP) through Alpaca paper trading."""
    result = _place_order_data(symbol, side, qty, order_type, limit_price, stop_loss, take_profit)
    return _sanitize(result)


@mcp.tool
def cancel_order(order_id: str) -> dict:
    """Cancel an open order by its ID."""
    try:
        result = _cancel_order_data(order_id)
        return _sanitize(result)
    except Exception as e:
        return {"order_id": order_id, "cancelled": False, "error": str(e)}


if __name__ == "__main__":
    mcp.run()