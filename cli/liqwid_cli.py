import asyncio
import sys
import json
from fastmcp import Client

SERVER_PATH = "mcp_server/server.py"

config = {
    "mcpServers": {
        "liqwid": {
            "transport": "stdio",
            "command": sys.executable,
            "args": [SERVER_PATH],
        }
    }
}


async def call_tool(client, name, args=None):
    result = await client.call_tool(name, args or {})
    return result.data if hasattr(result, "data") else result


def print_json(data):
    print(json.dumps(data, indent=2, default=str))


async def handle_trade(client, symbol):
    print(f"Scanning {symbol}...")
    signals = await call_tool(client, "scan_signals", {"symbol": symbol})

    if not signals:
        print("No valid signals right now.")
        return

    print(f"Found {len(signals)} signal(s). Scoring...\n")
    best = None
    best_score = -1
    for sig in signals:
        scored = await call_tool(client, "score_conviction", {"signal": sig})
        print(f"  {sig['direction']} @ {sig['timestamp']} | entry={sig['entry']} "
              f"sl={sig['sl']} tp={sig['tp']} | conviction={scored['score']}")
        if scored["score"] > best_score:
            best_score = scored["score"]
            best = sig

    print(f"\nBest signal: {best['direction']} entry={best['entry']} "
          f"sl={best['sl']} tp={best['tp']} (conviction {best_score})\n")

    risk = await call_tool(client, "check_risk", {"signal": best})
    print("Risk check result:")
    print_json(risk)

    if not risk["approved"]:
        print("\nTrade rejected by risk gate. Stopping.")
        return

    confirm = input(f"\nPlace order for {risk['position_size']} {symbol}? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return

    side = "buy" if best["direction"] == "BULLISH" else "sell"
    order = await call_tool(client, "place_order", {
        "symbol": symbol,
        "side": side,
        "qty": risk["position_size"],
        "stop_loss": best["sl"],
        "take_profit": best["tp"],
    })
    print("\nOrder placed:")
    print_json(order)


def print_help():
    print("""
LIQWID CLI - Commands:
  account                Show current paper account state
  positions               Show open positions
  market <symbol>          Fetch recent market data (prints bar count only)
  scan <symbol>            Scan for valid signals
  trade <symbol>            Full pipeline: scan -> score -> risk check -> confirm -> place order
  cancel <order_id>          Cancel an open order
  help                       Show this message
  exit / quit                 Exit the CLI
""")


async def repl():
    print("Connecting to LIQWID MCP server...")
    async with Client(config) as client:
        print("Connected. Type 'help' for commands.\n")

        while True:
            try:
                raw = input("liqwid> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                break

            if not raw:
                continue

            parts = raw.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else ""

            try:
                if cmd in ("exit", "quit"):
                    break
                elif cmd == "help":
                    print_help()
                elif cmd == "account":
                    result = await call_tool(client, "get_account")
                    print_json(result)
                elif cmd == "positions":
                    result = await call_tool(client, "get_positions")
                    print_json(result)
                elif cmd == "market":
                    symbol = arg or "SPY"
                    result = await call_tool(client, "get_market_data", {"symbol": symbol})
                    print(f"Fetched {len(result)} bars for {symbol}")
                elif cmd == "scan":
                    symbol = arg or "SPY"
                    result = await call_tool(client, "scan_signals", {"symbol": symbol})
                    print_json(result)
                elif cmd == "trade":
                    await handle_trade(client, arg or "SPY")
                elif cmd == "cancel":
                    if not arg:
                        print("Usage: cancel <order_id>")
                        continue
                    result = await call_tool(client, "cancel_order", {"order_id": arg})
                    print_json(result)
                else:
                    print(f"Unknown command: '{cmd}'. Type 'help' for options.")
            except Exception as e:
                print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(repl())