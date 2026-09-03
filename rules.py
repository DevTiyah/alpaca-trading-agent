from zoneinfo import ZoneInfo

SWING_LOOKBACK = 2  # configurable per spec

def detect_swings(df, lookback=SWING_LOOKBACK):
    """Returns list of dicts: {index, type: 'high'|'low', price}"""
    swings = []
    for i in range(lookback, len(df) - lookback):
        window_highs = df['high'].iloc[i-lookback:i+lookback+1]
        window_lows = df['low'].iloc[i-lookback:i+lookback+1]

        if df['high'].iloc[i] == window_highs.max() and \
           (window_highs == window_highs.max()).sum() == 1:
            swings.append({"index": i, "type": "high", "price": df['high'].iloc[i]})

        if df['low'].iloc[i] == window_lows.min() and \
           (window_lows == window_lows.min()).sum() == 1:
            swings.append({"index": i, "type": "low", "price": df['low'].iloc[i]})

    return swings

def get_relevant_swing(swings, current_index, direction):
    """
    Find the most recent swing high (bullish) or swing low (bearish)
    that formed before current_index.
    Returns the swing dict, or None if no prior swing of that type exists.
    """
    target_type = "high" if direction == "bullish" else "low"
    candidates = [s for s in swings if s["index"] < current_index and s["type"] == target_type]
    if not candidates:
        return None
    return max(candidates, key=lambda s: s["index"])  # most recent by index


def detect_bms(df, i, direction, swings):
    """
    Returns True if candle i's close breaks the relevant prior swing point,
    confirming a break of market structure in the given direction.
    direction: "bullish" or "bearish"
    """
    relevant_swing = get_relevant_swing(swings, i, direction)
    if relevant_swing is None:
        return False

    close_price = df["close"].iloc[i]

    if direction == "bullish":
        return close_price > relevant_swing["price"]
    else:  # bearish
        return close_price < relevant_swing["price"]

def find_first_bms_breaks(df, swings, direction, start=0, end=None):
    """
    Scans forward and returns only the FIRST candle index of each BMS
    break event, collapsing consecutive True's into a single entry.
    """
    if end is None:
        end = len(df)

    breaks = []
    was_broken = False

    for i in range(start, end):
        is_broken = detect_bms(df, i, direction, swings)
        if is_broken and not was_broken:
            breaks.append(i)
        was_broken = is_broken

    return breaks

def find_order_block(df, bms_index, direction, as_of_index, displacement_multiplier=1.5, lookback_window=20):
    """
    as_of_index: the current candle being evaluated (e.g., during retracement scan).
    Mitigation is only checked from bms_index+1 up to as_of_index — never beyond,
    since the strategy can't see future candles when making a real decision.
    """
    opposing_is_bearish_candle = direction == "bullish"
    search_start = max(0, bms_index - lookback_window)

    ob_candidate = None
    for i in range(bms_index, search_start - 1, -1):
        candle_open = df["open"].iloc[i]
        candle_close = df["close"].iloc[i]
        is_bearish = candle_close < candle_open
        is_bullish = candle_close > candle_open

        if opposing_is_bearish_candle and is_bearish:
            ob_candidate = i
            break
        elif not opposing_is_bearish_candle and is_bullish:
            ob_candidate = i
            break

    if ob_candidate is None:
        return None

    ob_high = df["high"].iloc[ob_candidate]
    ob_low = df["low"].iloc[ob_candidate]
    ob_range = ob_high - ob_low

    displacement_high = df["high"].iloc[ob_candidate:bms_index + 1].max()
    displacement_low = df["low"].iloc[ob_candidate:bms_index + 1].min()
    displacement_range = displacement_high - displacement_low

    if ob_range == 0 or displacement_range < displacement_multiplier * ob_range:
        return None

    # Mitigation check: ONLY up to as_of_index, never beyond (no lookahead)
    mitigated = False
    for j in range(bms_index + 1, as_of_index + 1):
        if direction == "bullish" and df["close"].iloc[j] < ob_low:
            mitigated = True
            break
        elif direction == "bearish" and df["close"].iloc[j] > ob_high:
            mitigated = True
            break

    return {
        "index": ob_candidate,
        "high": ob_high,
        "low": ob_low,
        "mitigated": mitigated,
    }

def calculate_ote_zone(displacement_low, displacement_high, direction, zone=(0.62, 0.79)):
    """
    Returns (lower_price, upper_price) bounds of the OTE zone in real price terms.
    For a bullish move, retracement is measured pulling back DOWN from the high.
    For a bearish move, retracement is measured pulling back UP from the low.
    """
    rng = displacement_high - displacement_low
    if direction == "bullish":
        upper = displacement_high - zone[0] * rng   # 0.62 retracement (shallower)
        lower = displacement_high - zone[1] * rng   # 0.79 retracement (deeper)
    else:  # bearish
        lower = displacement_low + zone[0] * rng
        upper = displacement_low + zone[1] * rng
    return (lower, upper)


def detect_ote(df, i, ob_index, bms_index, direction, zone=(0.62, 0.79)):
    """
    Checks whether candle i's price has entered the OTE zone of the
    displacement leg running from ob_index to bms_index.
    Uses wick (high/low) touch, not just close, since a retracement
    can tag the zone without closing inside it.
    """
    displacement_high = df["high"].iloc[ob_index:bms_index + 1].max()
    displacement_low = df["low"].iloc[ob_index:bms_index + 1].min()

    lower, upper = calculate_ote_zone(displacement_low, displacement_high, direction, zone)

    candle_high = df["high"].iloc[i]
    candle_low = df["low"].iloc[i]

    # Did this candle's wick touch into the zone at all?
    return candle_low <= upper and candle_high >= lower

def find_ssl_levels(swings):
    """Sell-side liquidity pools = swing lows."""
    return [s for s in swings if s["type"] == "low"]

def find_bsl_levels(swings):
    """Buy-side liquidity pools = swing highs."""
    return [s for s in swings if s["type"] == "high"]

def get_relevant_liquidity_level(levels, current_index):
    """Most recent liquidity level (swing) before current_index."""
    candidates = [lvl for lvl in levels if lvl["index"] < current_index]
    if not candidates:
        return None
    return max(candidates, key=lambda lvl: lvl["index"])


def detect_liquidity_sweep(df, i, levels, sweep_type):
    """
    sweep_type: "ssl" (sweep sell-side low, bullish signal)
                "bsl" (sweep buy-side high, bearish signal)
    Returns the swept level dict if a sweep occurred at candle i, else None.
    """
    relevant_level = get_relevant_liquidity_level(levels, i)
    if relevant_level is None:
        return None

    candle_low = df["low"].iloc[i]
    candle_high = df["high"].iloc[i]
    candle_close = df["close"].iloc[i]

    if sweep_type == "ssl":
        swept = candle_low < relevant_level["price"]
        rejected = candle_close > relevant_level["price"]
        if swept and rejected:
            return relevant_level
    elif sweep_type == "bsl":
        swept = candle_high > relevant_level["price"]
        rejected = candle_close < relevant_level["price"]
        if swept and rejected:
            return relevant_level

    return None

def get_htf_bias(df, resample_rule="15min", ma_window=10):
    """
    MVP approximation: resamples 1-min data to a higher timeframe,
    then compares the latest close to a moving average and its recent slope.
    Returns "bullish", "bearish", or "consolidating".
    """
    df_indexed = df.set_index("timestamp")
    resampled = df_indexed["close"].resample(resample_rule).last().dropna()

    if len(resampled) < ma_window + 2:
        return "consolidating"  # not enough data yet

    ma = resampled.rolling(ma_window).mean()
    latest_close = resampled.iloc[-1]
    latest_ma = ma.iloc[-1]
    prior_ma = ma.iloc[-2]

    ma_slope_up = latest_ma > prior_ma
    ma_slope_down = latest_ma < prior_ma

    if latest_close > latest_ma and ma_slope_up:
        return "bullish"
    elif latest_close < latest_ma and ma_slope_down:
        return "bearish"
    else:
        return "consolidating"

def get_current_session(timestamp):
    """
    timestamp: pandas Timestamp (UTC-aware)
    Returns "london", "ny", or "other" based on locked session windows (ET).
    """
    et_time = timestamp.astimezone(ZoneInfo("America/New_York"))
    hour = et_time.hour
    minute = et_time.minute
    time_decimal = hour + minute / 60

    if 3.0 <= time_decimal < 6.0:
        return "london"
    elif 9.5 <= time_decimal < 11.5:
        return "ny"
    else:
        return "other"

def select_tp_pool(entry, sl, pools, direction, min_r=1.5, max_r=5.0):
    """
    pools: list of liquidity level dicts (opposing direction), e.g. BSL levels for a long.
    Returns {"tp_level": price, "r_multiple": float} for furthest qualifying pool,
    or None if no pool falls within [min_r, max_r].
    """
    risk = abs(entry - sl)
    if risk == 0:
        return None

    candidates = []
    for pool in pools:
        level = pool["price"]
        reward = abs(level - entry)
        r_multiple = reward / risk
        if min_r <= r_multiple <= max_r:
            candidates.append((level, r_multiple))

    if not candidates:
        return None

    best = max(candidates, key=lambda c: c[1])
    return {"tp_level": best[0], "r_multiple": best[1]}

def select_tp_pool(entry, sl, pools, direction, min_r=1.5, max_r=5.0):
    """
    pools: list of liquidity level dicts (opposing direction), e.g. BSL levels for a long.
    Returns {"tp_level": price, "r_multiple": float} for furthest qualifying pool,
    or None if no pool falls within [min_r, max_r].
    """
    risk = abs(entry - sl)
    if risk == 0:
        return None

    candidates = []
    for pool in pools:
        level = pool["price"]
        reward = abs(level - entry)
        r_multiple = reward / risk
        if min_r <= r_multiple <= max_r:
            candidates.append((level, r_multiple))

    if not candidates:
        return None

    best = max(candidates, key=lambda c: c[1])
    return {"tp_level": best[0], "r_multiple": best[1]}

def detect_sh_bms_rto(df, i, swings, ssl_levels, bsl_levels, direction, htf_bias):
    """
    Checks candle i as a potential entry point for the SH+BMS+RTO setup.
    Returns a Signal dict if all hard gates + confluence pass, else None.
    """
    # --- HARD GATE 1: HTF bias alignment ---
    bias_aligned = (direction == "bullish" and htf_bias == "bullish") or \
                   (direction == "bearish" and htf_bias == "bearish")
    if not bias_aligned:
        return None

    # --- HARD GATE 2: Liquidity sweep occurred recently ---
    sweep_type = "ssl" if direction == "bullish" else "bsl"
    levels = ssl_levels if direction == "bullish" else bsl_levels

    # look back a window for a recent sweep (not necessarily at candle i itself)
    recent_sweep = None
    sweep_index = None
    for j in range(max(0, i - 30), i + 1):
        sweep = detect_liquidity_sweep(df, j, levels, sweep_type)
        if sweep:
            recent_sweep = sweep
            sweep_index = j

    if recent_sweep is None:
        return None

    # --- HARD GATE 3: BMS confirmed after the sweep ---
    first_breaks = find_first_bms_breaks(df, swings, direction, start=sweep_index, end=i + 1)
    if not first_breaks:
        return None
    bms_index = first_breaks[-1]  # most recent break after the sweep

    # --- Order Block (supporting condition 1) ---
    ob = find_order_block(df, bms_index, direction, as_of_index=i)
    ob_valid = ob is not None and not ob["mitigated"]

    # --- OTE retracement (supporting condition 2) ---
    ote_valid = False
    if ob_valid:
        ote_valid = detect_ote(df, i, ob["index"], bms_index, direction)

    # --- Session timing (supporting condition 3) ---
    session = get_current_session(df["timestamp"].iloc[i])
    session_valid = session in ("london", "ny")

    # --- Confluence: need >=2 of 3 supporting conditions ---
    supporting_count = sum([ob_valid, ote_valid, session_valid])
    if supporting_count < 2:
        return None

    # Entry requires price to actually be in the OTE zone right now
    if not ote_valid:
        return None  # per spec: no entry without retracement confirmation

    entry = df["close"].iloc[i]

    # --- SL: OB boundary ---
    if direction == "bullish":
        sl = ob["low"]
    else:
        sl = ob["high"]

    # --- TP: furthest opposing pool within R-multiple band ---
    opposing_pools = bsl_levels if direction == "bullish" else ssl_levels
    tp_result = select_tp_pool(entry, sl, opposing_pools, direction)
    if tp_result is None:
        return None  # per locked spec: no qualifying TP pool = NO TRADE

    return {
        "setup": "SH_BMS_RTO",
        "direction": direction.upper(),
        "htf_bias": htf_bias.upper(),
        "liquidity_type": sweep_type.upper(),
        "liquidity_swept": True,
        "bms": True,
        "order_block": {"high": ob["high"], "low": ob["low"], "index": ob["index"]},
        "ote_retracement": True,
        "confluence_count": supporting_count,
        "entry": entry,
        "sl": sl,
        "tp": tp_result["tp_level"],
        "r_multiple": tp_result["r_multiple"],
        "timestamp": str(df["timestamp"].iloc[i]),
    }


# if __name__ == "__main__":
#     from data_loader import load_bars

#     df = load_bars("sample_data/SPY_1min_aug2026.csv")
#     swings = detect_swings(df)

#     bms_hits = []
#     for i in range(50, 200):
#         if detect_bms(df, i, "bullish", swings):
#             bms_hits.append(i)

#     print(f"Bullish BMS hits in range 50-200: {len(bms_hits)}")
#     print(bms_hits[:10])

# if __name__ == "__main__":
#     from data_loader import load_bars

#     df = load_bars("sample_data/SPY_1min_aug2026.csv")
#     swings = detect_swings(df)

#     first_breaks = find_first_bms_breaks(df, swings, "bullish", start=50, end=200)
#     print(f"First-break BMS events in range 50-200: {len(first_breaks)}")
#     print(first_breaks)

# if __name__ == "__main__":
#     from data_loader import load_bars

#     df = load_bars("sample_data/SPY_1min_aug2026.csv")
#     swings = detect_swings(df)

#     first_breaks = find_first_bms_breaks(df, swings, "bullish", start=50, end=200)
#     print(f"First-break BMS events: {len(first_breaks)}")

#     for bms_i in first_breaks:
#         ob = find_order_block(df, bms_i, "bullish", as_of_index=bms_i)
#         print(f"BMS at {bms_i} -> OB: {ob}")

# if __name__ == "__main__":
#     from data_loader import load_bars

#     df = load_bars("sample_data/SPY_1min_aug2026.csv")
#     swings = detect_swings(df)

#     first_breaks = find_first_bms_breaks(df, swings, "bullish", start=50, end=200)
#     print(f"First-break BMS events: {len(first_breaks)}")

#     for bms_i in first_breaks:
#         ob = find_order_block(df, bms_i, "bullish", as_of_index=bms_i)
#         if ob is None:
#             print(f"BMS at {bms_i} -> no OB, skipping OTE check")
#             continue

#         # scan forward up to 20 candles after the break looking for retracement into OTE
#         ote_hit = None
#         for j in range(bms_i + 1, min(bms_i + 21, len(df))):
#             if detect_ote(df, j, ob["index"], bms_i, "bullish"):
#                 ote_hit = j
#                 break

#         print(f"BMS at {bms_i} -> OB at {ob['index']} -> OTE hit at {ote_hit}")

# if __name__ == "__main__":
#     from data_loader import load_bars

#     df = load_bars("sample_data/SPY_1min_aug2026.csv")
#     swings = detect_swings(df)
#     ssl_levels = find_ssl_levels(swings)
#     bias = get_htf_bias(df)
    
#     sweep_hits = []
#     for i in range(50, 200):
#         sweep = detect_liquidity_sweep(df, i, ssl_levels, "ssl")
#         if sweep:
#             sweep_hits.append((i, sweep["price"]))
#     print(f"HTF bias (full dataset, as of last candle): {bias}")

#     print(f"SSL sweeps in range 50-200: {len(sweep_hits)}")
#     print(sweep_hits[:10])
    

if __name__ == "__main__":
    from data_loader import load_bars

    df = load_bars("sample_data/SPY_1min_aug2026.csv")
    swings = detect_swings(df)
    ssl_levels = find_ssl_levels(swings)
    bsl_levels = find_bsl_levels(swings)
    htf_bias = get_htf_bias(df)

    print(f"HTF bias: {htf_bias}")

    signals = []
    for i in range(50, 500):  # wider range now that we're testing the full pipeline
        signal = detect_sh_bms_rto(df, i, swings, ssl_levels, bsl_levels, "bullish", htf_bias)
        if signal:
            signals.append(signal)

    print(f"\nFound {len(signals)} valid signals in range 50-500")
    for s in signals:
        print(s)