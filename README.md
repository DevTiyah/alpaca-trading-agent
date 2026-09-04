# Autonomous Trading Agent

## Engineering Sprint Report — Day 1 & Day 2

**Project:** LIQWID — Autonomous Trading Agent
**Sprint:** 3-Day Autonomous Trading Agent Sprint
**Team Size:** 2
**Trading Environment:** Alpaca Paper Trading
**Primary Interface:** MCP Server + CLI
**Current Status:** Day 2 completed / Day 3 handoff

---

# 1. Executive Summary

During Days 1 and 2, we progressed the LIQWID Autonomous Trading Agent from an initial project skeleton into a working paper-trading automation pipeline.

The system is designed around the following architecture:

**Market Data → Signal Detection → Conviction Scoring → Risk Validation → Trade Execution → Logging**

The agent is exposed through an **MCP server**, allowing the same underlying trading capabilities to be consumed by either a CLI or, later, an LLM-based agent.

By the end of Day 2, the major infrastructure required for autonomous paper trading had been implemented and tested. The scheduler successfully starts, checks the automation kill switch, and prevents trading when automation is disabled. The system is therefore capable of operating autonomously while maintaining an explicit safety mechanism.

An important distinction is that **the engineering pipeline is functional, but the trading strategy should not yet be presented as statistically proven**. Our recent backtesting has produced encouraging early results, including approximately **7 wins out of 10 tested setups**, but this is still too small a sample to establish a reliable statistical edge.

The immediate objective for Day 3 is therefore to make the existing system more robust, demonstrable, and agentic rather than claiming profitability.

---

# 2. Project Objective

The objective of the sprint is to build a working autonomous trading agent capable of:

1. Retrieving market data.
2. Identifying trading opportunities using our defined strategy.
3. Scoring the quality/conviction of identified signals.
4. Applying predefined risk rules.
5. Executing trades through Alpaca's Paper Trading API.
6. Running the entire process automatically on a schedule.
7. Recording decisions and activity for later analysis.
8. Exposing the trading capabilities through MCP so an LLM agent can interact with the system.

The target architecture is:

```text
              ┌─────────────────────┐
              │     CLI / LLM       │
              │       Agent         │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │    MCP Server       │
              │                     │
              │ Trading Tool Layer  │
              └──────────┬──────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
    Market Data      Strategy       Account/Risk
       Layer          Engine           Layer
          │              │              │
          └──────────────┼──────────────┘
                         ▼
              ┌─────────────────────┐
              │   Trading Pipeline  │
              │                     │
              │ Scan → Score → Risk │
              │ → Execute → Log     │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │ Alpaca Paper Trading│
              └─────────────────────┘
```

---

# 3. Day 1 — Foundation

## 3.1 Objective

The primary objective of Day 1 was to establish the technical foundation of the trading agent.

Rather than attempting to build a polished autonomous system immediately, the focus was on getting the individual components communicating correctly.

The Day 1 target was:

* Establish the project structure.
* Connect to Alpaca.
* Define the MCP interface.
* Implement the initial market-data functionality.
* Begin implementing the strategy engine.
* Establish the initial signal-scanning functionality.

This follows the sprint architecture where Person A handles the data/execution layer while Person B handles strategy/intelligence and automation.

---

## 3.2 Alpaca Paper Trading Integration

The trading system was designed around **Alpaca Paper Trading** rather than live capital.

This gives us a safe environment for testing:

* Market-data retrieval
* Account state
* Positions
* Orders
* Execution flow
* Automation

without exposing real funds.

The initial integration established the connection between the trading application and the Alpaca API.

The system is therefore being developed with a clear separation between:

**Trading logic**

and

**actual capital deployment.**

---

# 4. MCP Architecture

A central design decision was to expose trading capabilities as MCP tools rather than implementing the entire system as one monolithic script.

The intended MCP interface contains tools such as:

```text
get_market_data()
scan_signals()
score_conviction()
check_risk()
place_order()
get_positions()
get_account()
cancel_order()
```

This architecture is important because it allows the same trading infrastructure to eventually be controlled by:

* a human through the CLI
* an autonomous LLM agent
* automated scheduler logic

The sprint specification identifies this MCP tool layer as the core component that makes the project agentic rather than simply being a trading script.

---

# 5. Market Data and Account State

The initial trading infrastructure includes access to:

### Market data

The system can retrieve market information required by the strategy engine.

### Account state

The system can query the current paper-trading account.

### Positions

The system can inspect existing positions before making trading decisions.

These components are important because autonomous trading decisions cannot safely operate from signal information alone. The agent needs awareness of the current portfolio and account state.

---

# 6. Strategy Engine

While the infrastructure was being developed, the trading strategy was formalized into explicit rules.

The purpose of this was to move away from discretionary trading decisions and toward deterministic conditions that can be evaluated programmatically.

The strategy engine is responsible for identifying whether a particular market situation satisfies our predefined setup conditions.

Conceptually:

```text
Market Data
     │
     ▼
Strategy Rules
     │
     ├── Conditions satisfied?
     │
     ├── YES → Signal Candidate
     │
     └── NO  → No Signal
```

This makes the strategy reproducible and allows it to be backtested and eventually automated.

---

# 7. Initial Backtesting

Before treating the strategy as trustworthy, we began testing the strategy against historical price action.

The early results have been encouraging:

**Approximately 7 successful setups out of 10 tested setups.**

However, this result is being treated as an **early signal rather than proof of profitability**.

The sample size is currently too small to establish statistical confidence.

The next stage of validation should therefore include:

* substantially more trades
* different market conditions
* explicit recording of every qualifying setup
* reward/risk measurements
* expectancy
* out-of-sample testing

This distinction is important for the project: **we are building and validating an automated trading system, not claiming that we have already discovered a guaranteed profitable strategy.**

---

# 8. Day 1 Checkpoint

The Day 1 engineering objective was achieved:

* Project foundation established.
* Alpaca integration initiated.
* MCP architecture established.
* Market-data/account functionality established.
* Strategy engine initiated.
* Signal-scanning functionality established.

The sprint guide defines the Day 1 checkpoint as an MCP server exposing at least `get_market_data` and `scan_signals`, with both teammates able to interact with it independently.

---

# 9. Day 2 — Intelligence + Automation

## 9.1 Objective

Day 2 focused on transforming the foundation into an actual automated trading pipeline.

The target was:

```text
SCAN
  ↓
SCORE
  ↓
RISK CHECK
  ↓
EXECUTE
  ↓
LOG
```

running automatically against real paper-trading data.

This corresponds directly with the Day 2 sprint checkpoint.

---

# 10. Conviction Scoring

The signal engine was extended with a conviction-scoring layer.

Instead of simply producing:

```text
BUY
```

the system is intended to determine how strongly the available evidence supports the signal.

Conceptually:

```text
Signal
   │
   ▼
Signal Factors
   │
   ├── Strategy conditions
   ├── Market context
   ├── Confirmation factors
   └── Other defined criteria
          │
          ▼
   Conviction Score
      0 — 100
```

An important design principle is that the score should not be treated as a magic number.

The system should record **why** a particular score was produced.

For example:

```text
Signal detected

Trend condition:       PASS
Entry condition:       PASS
Confirmation:          PASS
Risk condition:        PASS

Conviction: 82/100
```

This makes the system easier to debug and much easier to demonstrate to judges.

---

# 11. Risk Management Layer

A major part of the automation system is the risk gate.

The purpose of the risk layer is to prevent the strategy engine from automatically executing every signal.

The conceptual flow is:

```text
Signal
  │
  ▼
Conviction Threshold
  │
  ▼
Risk Gate
  │
  ├── Position size
  ├── Maximum allocation
  ├── Diversification
  └── Existing positions
       │
       ▼
  APPROVE / REJECT
```

This creates a separation between:

**"The strategy found a setup."**

and

**"The system is allowed to trade the setup."**

That distinction is essential for autonomous execution.

---

# 12. Order Execution

The system was extended toward actual paper-order execution through Alpaca.

The intended order interface includes parameters such as:

```text
symbol
side
quantity
order type
stop loss
take profit
```

The trading agent therefore has a complete execution path:

```text
Signal
   ↓
Conviction
   ↓
Risk Gate
   ↓
Order
   ↓
Alpaca Paper Account
```

No real capital is being deployed during this sprint.

---

# 13. Automation Scheduler

One of the most important components completed during Day 2 was the automation scheduler.

The scheduler is responsible for repeatedly running the trading pipeline at a defined interval.

The current configuration scans:

```text
SPY
```

every:

```text
300 seconds
```

The scheduler startup output confirms that the automation process is running:

```text
LIQWID Scheduler starting.
Scanning ['SPY'] every 300s.
```

The scheduler also contains an automation kill switch.

---

# 14. Automation Kill Switch

A safety mechanism was implemented through:

```text
automation/AUTOMATION_ENABLED
```

The logic is intentionally simple:

### File exists

```text
AUTOMATION_ENABLED
        ↓
Automation ON
```

### File does not exist

```text
AUTOMATION_ENABLED absent
        ↓
Automation OFF
```

This provides a straightforward mechanism for preventing automated execution.

During testing, the scheduler was launched while the kill switch was disabled.

The system correctly produced:

```text
LIQWID Scheduler starting.
Scanning ['SPY'] every 300s.
Automation kill switch file: automation/AUTOMATION_ENABLED
-> Create this file to ENABLE automation, delete it to PAUSE.

[2026-09-04T13:04:06.339706] skipped:
Automation disabled (kill switch off)
```

This was an important successful test because it demonstrated that the scheduler does **not** automatically trade merely because the scheduler process is running.

---

# 15. Logging

The automation system also maintains a scheduler log.

The purpose of logging is to create a record of:

* scans
* signals
* skipped trades
* conviction decisions
* risk decisions
* executed orders
* automation state

This will be particularly important during the final demonstration because the team can show not only that the system is running, but also **what decisions it made and why.**

---

# 16. Current Architecture

At the end of Day 2, the system can be understood as the following pipeline:

```text
                 ┌───────────────┐
                 │   Scheduler   │
                 └───────┬───────┘
                         │
                         ▼
                 ┌───────────────┐
                 │ Market Data   │
                 └───────┬───────┘
                         │
                         ▼
                 ┌───────────────┐
                 │ Signal Scan   │
                 └───────┬───────┘
                         │
                         ▼
                 ┌───────────────┐
                 │  Conviction   │
                 │    Score      │
                 └───────┬───────┘
                         │
                         ▼
                 ┌───────────────┐
                 │   Risk Gate   │
                 └───────┬───────┘
                         │
                  ┌──────┴──────┐
                  │             │
                REJECT        APPROVE
                  │             │
                  ▼             ▼
                 LOG        PLACE ORDER
                                │
                                ▼
                       Alpaca Paper Trading
                                │
                                ▼
                              LOG
```

The MCP server sits around these capabilities and provides the interface through which the CLI and future LLM agent can interact with them.

---

# 17. What Has Been Successfully Demonstrated

The following engineering capabilities have been established during Days 1–2:

### Infrastructure

* Project structure
* Alpaca paper-trading integration
* MCP-based architecture
* Market-data access
* Account state access
* Position access

### Intelligence

* Formalized strategy rules
* Signal scanning
* Conviction scoring
* Reasoning behind signals

### Risk

* Risk-gating architecture
* Position/allocation controls
* Automation kill switch

### Automation

* Scheduled execution loop
* Automated scan cycle
* Automation ON/OFF mechanism
* Event logging

### Validation

* Historical strategy testing initiated
* Early result of approximately 7/10 successful setups
* Scheduler kill-switch behavior successfully tested

---

# 18. Current Limitations

The team should be explicit about what has **not** yet been proven.

## 18.1 Strategy Validation

The current backtest sample is still small.

A 7/10 result is encouraging but cannot yet establish a statistically reliable trading edge.

The strategy needs significantly more observations across different market conditions.

---

## 18.2 Paper Trading vs. Real Trading

The system currently operates against Alpaca Paper Trading.

Therefore, the project has demonstrated:

**technical execution**

but not:

**real-capital performance.**

---

## 18.3 LLM Agent Layer

The MCP architecture has been designed to support an LLM agent, but the final LLM-to-MCP layer remains a Day 3 task if time permits.

The sprint guide explicitly identifies this as a potential differentiator: an LLM can become a second consumer of the MCP tools and reason over their outputs.

---

# 19. Day 3 Handoff

The remaining work should focus on **robustness, agent integration, and demo readiness**, rather than rebuilding the foundation.

## Priority 1 — Error Handling

Add handling for:

* Alpaca API failures
* Network failures
* Empty market-data responses
* No signals
* Invalid signal responses
* Malformed tool responses
* Order failures
* Scheduler exceptions

The goal is to ensure that one failure does not crash the entire automation process.

The sprint guide specifically identifies API failures, missing signals, malformed responses, and demo crashes as issues that should be deliberately protected against.

---

## Priority 2 — Complete Kill Switch Demonstration

Verify both states:

```text
Automation OFF
     ↓
Scheduler runs
     ↓
No trade
```

and:

```text
Automation ON
     ↓
Scheduler runs
     ↓
Scan → Score → Risk → Execute
```

This should become part of the final demo.

---

## Priority 3 — CLI Polish

The CLI should expose simple commands such as:

```text
scan
score <symbol>
trade <symbol>
positions
account
```

The output should be readable rather than raw JSON.

This is important because the CLI is one of the primary interfaces judges will see.

---

## Priority 4 — LLM + MCP Agent

If time permits, connect an LLM to the MCP server.

The desired architecture becomes:

```text
              ┌───────────────┐
              │   LLM Agent   │
              └───────┬───────┘
                      │
                      ▼
              ┌───────────────┐
              │  MCP Server   │
              └───────┬───────┘
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
       Market      Strategy      Risk
        Data        Engine       Engine
                      │
                      ▼
                   Alpaca
```

The LLM should not directly control the broker.

Instead, it should reason through the controlled MCP tools.

---

# 20. Final Demo Story

The strongest demonstration should show a complete decision cycle rather than simply showing source code.

Recommended flow:

### Step 1 — Show account

```text
/account
```

Show current paper balance and positions.

### Step 2 — Run a scan

```text
/scan
```

Show whether a signal was found.

### Step 3 — Explain conviction

Show:

```text
Signal: ...
Conviction: XX/100

Factors:
✓ ...
✓ ...
✗ ...
```

### Step 4 — Show risk decision

```text
Risk Check:
APPROVED / REJECTED

Position Size:
...
```

### Step 5 — Execute through paper trading

Show the order being sent to Alpaca.

### Step 6 — Show resulting position

Retrieve the updated account/position state.

### Step 7 — Show automation

Run the scheduler and demonstrate that the system can repeat the entire process automatically.

### Step 8 — Show logs

Display the historical decision trail.

---

# 21. How We Should Position the Project

We should **not** present LIQWID as:

> "An AI that predicts the market and makes guaranteed money."

Instead, the stronger technical positioning is:

> **"An agentic trading infrastructure that combines a rule-based trading strategy, conviction scoring, risk controls, automated execution, and MCP-based tool access in a paper-trading environment."**

And when discussing the strategy:

> **"Our initial backtesting is encouraging, but we are continuing validation before making any claim of a statistically proven trading edge."**

This is more technically credible and aligns with the project's actual evidence.

The sprint guide itself recommends explicitly distinguishing a working paper-trading system from a statistically validated profitable strategy.

---

# 22. Day 2 Status

**Overall Status: ON TRACK**

| Component                | Status         |
| ------------------------ | -------------- |
| Project foundation       | ✅ Complete     |
| Alpaca Paper Trading     | ✅ Integrated   |
| MCP architecture         | ✅ Established  |
| Market data              | ✅ Working      |
| Account/positions        | ✅ Working      |
| Strategy rules           | ✅ Formalized   |
| Signal scanning          | ✅ Implemented  |
| Conviction scoring       | ✅ Implemented  |
| Risk layer               | ✅ Implemented  |
| Order execution          | ✅ Implemented  |
| Scheduler                | ✅ Running      |
| Kill switch              | ✅ Tested       |
| Logging                  | ✅ Implemented  |
| Historical backtesting   | 🟡 In progress |
| LLM → MCP agent          | 🟡 Day 3       |
| Error handling hardening | 🟡 Day 3       |
| CLI polish               | 🟡 Day 3       |
| Final demo               | 🟡 Day 3       |

---

# 23. Handoff Summary

**Day 1 built the foundation.**

**Day 2 connected the foundation into an automated trading pipeline.**

The system has now moved beyond being a collection of independent components and toward a functioning autonomous paper-trading system:

```text
Market
  ↓
Scan
  ↓
Signal
  ↓
Conviction
  ↓
Risk
  ↓
Execution
  ↓
Logging
```

The scheduler and kill switch have also been tested successfully, establishing the basic safety mechanism required for autonomous operation.

**Day 3 should focus on making this pipeline resilient, easy to demonstrate, and genuinely agentic through the MCP + LLM layer.**

The final goal is not simply to show that the bot can place a paper trade. The goal is to demonstrate a complete, explainable decision pipeline where a human or AI agent can inspect market state, reason about a signal, apply risk controls, execute through controlled tools, and leave behind an auditable record of what happened.
