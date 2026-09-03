RISK_PCT_PER_TRADE = 0.01       # risk 1% of equity per trade
MAX_CONCURRENT_POSITIONS = 5     # cap total open positions
MAX_ALLOCATION_PCT_PER_SYMBOL = 0.20  # no single symbol > 20% of equity

def get_asset_class(symbol: str) -> str:
    """
    MVP heuristic: Alpaca crypto pairs contain '/', e.g. 'BTC/USD'.
    Equities are plain tickers, e.g. 'SPY'.
    """
    return "crypto" if "/" in symbol else "equity"


def get_available_buying_power(account: dict, asset_class: str) -> float:
    """
    Selects the appropriate buying power field.
    Crypto uses cash only (Alpaca doesn't extend margin on crypto).
    Equity uses regular buying power (may include margin).
    """
    if asset_class == "crypto":
        return float(account["cash"])
    else:
        return float(account["buying_power"])


def check_risk(signal: dict, account: dict, open_positions: list[dict],
                risk_pct=RISK_PCT_PER_TRADE,
                max_concurrent=MAX_CONCURRENT_POSITIONS,
                max_allocation_pct=MAX_ALLOCATION_PCT_PER_SYMBOL) -> dict:
    """
    Hard gate. Returns {"approved": bool, "position_size": float, "reason": str}.
    """
    symbol = signal["symbol"]
    entry = signal["entry"]
    sl = signal["sl"]
    asset_class = get_asset_class(symbol)

    equity = float(account["portfolio_value"])
    buying_power = get_available_buying_power(account, asset_class)

    # --- Gate 1: max concurrent positions ---
    if len(open_positions) >= max_concurrent:
        return {"approved": False, "position_size": 0, "reason": f"Max concurrent positions ({max_concurrent}) reached"}

    # --- Gate 2: existing exposure to this symbol ---
    existing_exposure = sum(
        float(p.get("market_value", 0)) for p in open_positions if p.get("symbol") == symbol
    )
    max_symbol_allocation = equity * max_allocation_pct
    if existing_exposure >= max_symbol_allocation:
        return {"approved": False, "position_size": 0, "reason": f"Max allocation for {symbol} already reached"}

    # --- Gate 3: calculate position size from risk % ---
    risk_per_unit = abs(entry - sl)
    if risk_per_unit == 0:
        return {"approved": False, "position_size": 0, "reason": "Zero risk distance (invalid SL)"}

    max_risk_dollars = equity * risk_pct
    qty = max_risk_dollars / risk_per_unit

    # --- Gate 4: does this fit within buying power? ---
    position_cost = qty * entry
    if position_cost > buying_power:
        # scale down to what buying power actually allows
        qty = buying_power / entry
        position_cost = qty * entry

    # --- Gate 5: respect remaining room under the symbol allocation cap ---
    remaining_symbol_room = max_symbol_allocation - existing_exposure
    if position_cost > remaining_symbol_room:
        qty = remaining_symbol_room / entry
        position_cost = qty * entry

    if qty <= 0:
        return {"approved": False, "position_size": 0, "reason": "Calculated position size is zero or negative"}

    return {
        "approved": True,
        "position_size": round(qty, 6),  # 6 decimals covers crypto fractional sizing
        "reason": f"Approved: risking {risk_pct*100:.1f}% of equity (${max_risk_dollars:.2f}), "
                  f"size={qty:.6f} {symbol} (${position_cost:.2f})",
    }


if __name__ == "__main__":
    mock_account = {
        "portfolio_value": "100000",
        "buying_power": "400000",
        "cash": "100000",
    }
    mock_signal = {
        "symbol": "SPY",
        "entry": 768.87,
        "sl": 768.36,
    }
    mock_positions = []  # no open positions yet

    result = check_risk(mock_signal, mock_account, mock_positions)
    print(result)

    # Test the crypto path too
    mock_crypto_signal = {
        "symbol": "BTC/USD",
        "entry": 60000,
        "sl": 59500,
    }
    result_crypto = check_risk(mock_crypto_signal, mock_account, mock_positions)
    print(result_crypto)

