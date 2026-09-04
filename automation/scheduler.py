import asyncio
import sys
import json
import os
from datetime import datetime
from fastmcp import Client

SERVER_PATH = "mcp_server/server.py"
SYMBOLS_TO_SCAN = ["SPY"]  # extend this list later
SCAN_INTERVAL_SECONDS = 300  # 5 minutes, per original sprint plan
MIN_CONVICTION_SCORE = 70   # provisional - signals below this are logged but not traded

LOG_PATH = "automation/scheduler_log.jsonl"
KILL_SWITCH_PATH = "automation/AUTOMATION_ENABLED"  # presence of this file = automation ON

config = {
    "mcpServers": {
        "liqwid": {
            "transport": "stdio",
            "command": sys.executable,
            "args": [SERVER_PATH],
        }
    }
}


def is_automation_enabled() -> bool:
    """Kill switch: automation only runs if this file exists. Delete it to pause instantly."""
    return os.path.exists(KILL_SWITCH_PATH)


def log_event(event: dict):
    event["logged_at"] = datetime.now().isoformat()
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(event, default=str) + "\n")
    print(f"[{event['logged_at']}] {event.get('action', 'event')}: {event.get('summary', '')}")


async def call_tool(client, name, args=None):
    result = await client.call_tool(name, args or {})
    return result.data if hasattr(result, "data") else result


async def run_cycle(client):
    if not is_automation_enabled():
        log_event({"action": "skipped", "summary": "Automation disabled (kill switch off)"})
        return

    for symbol in SYMBOLS_TO_SCAN:
        try:
            signals = await call_tool(client, "scan_signals", {"symbol": symbol})

            if not signals:
                log_event({"action": "no_signal", "symbol": symbol, "summary": "No valid setups found"})
                continue

            # score every signal, pick the best
            best = None
            best_score = -1
            for sig in signals:
                scored = await call_tool(client, "score_conviction", {"signal": sig})
                if scored["score"] > best_score:
                    best_score = scored["score"]
                    best = sig
                    best_reasoning = scored["reasoning"]

            log_event({
                "action": "signal_found",
                "symbol": symbol,
                "direction": best["direction"],
                "conviction": best_score,
                "reasoning": best_reasoning,
                "summary": f"{best['direction']} signal, conviction {best_score}",
            })

            if best_score < MIN_CONVICTION_SCORE:
                log_event({
                    "action": "skipped_low_conviction",
                    "symbol": symbol,
                    "conviction": best_score,
                    "summary": f"Conviction {best_score} below threshold {MIN_CONVICTION_SCORE}",
                })
                continue

            risk = await call_tool(client, "check_risk", {"signal": best})

            if not risk["approved"]:
                log_event({
                    "action": "rejected_by_risk_gate",
                    "symbol": symbol,
                    "reason": risk["reason"],
                    "summary": risk["reason"],
                })
                continue

            side = "buy" if best["direction"] == "BULLISH" else "sell"
            order = await call_tool(client, "place_order", {
                "symbol": symbol,
                "side": side,
                "qty": risk["position_size"],
                "stop_loss": best["sl"],
                "take_profit": best["tp"],
            })

            log_event({
                "action": "order_placed",
                "symbol": symbol,
                "order": order,
                "conviction": best_score,
                "position_size": risk["position_size"],
                "summary": f"Placed {side} order for {risk['position_size']} {symbol} (conviction {best_score})",
            })

        except Exception as e:
            # One bad cycle should never kill the scheduler
            log_event({"action": "error", "symbol": symbol, "error": str(e), "summary": f"Error scanning {symbol}: {e}"})


async def run_scheduler():
    print(f"LIQWID Scheduler starting. Scanning {SYMBOLS_TO_SCAN} every {SCAN_INTERVAL_SECONDS}s.")
    print(f"Automation kill switch file: {KILL_SWITCH_PATH}")
    print(f"  -> Create this file to ENABLE automation, delete it to PAUSE.\n")

    async with Client(config) as client:
        while True:
            await run_cycle(client)
            await asyncio.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(run_scheduler())