# Algorithmic Arbitrage ETF Trading Bot (compatible with Rotman Trading Simulator)

Python REST trading bot for the RIT x CMU trading contest that performs market-making/spread capture on equities and cross-currency ETF arbitrage, with risk controls, cost modeling, tender-offer handling, and automated order management.

## Features
- Connects to the RIT simulator via REST (requests), pulls top-of-book quotes, positions, tenders, and manages orders (place/cancel/market-sweep).
- Market-making/spread-capture on BULL/BEAR and on RITC (ETF quoted in USD, converted to CAD via USD/CAD quotes).
- Transaction-cost modeling (fees/slippage) with profitability thresholds and order slicing to comply with per-order caps.
- Portfolio risk controls: gross/net exposure limits and per-instrument caps.
- Liquidity management: cancels stale limits and sweeps to market when prices move away.
- Automated tender-offer evaluation and execution with live-book pricing and risk checks.
- Event loop synchronized to market status; runs at ~2–3 Hz.

## Instruments
- CAD (cash), USD (USD/CAD FX), BULL (equity), BEAR (equity), RITC (USD-quoted ETF).
- RITC prices are converted to CAD using USD/CAD top-of-book (bid/ask) for bid/ask respectively.

## How it works (high-level)
- Fetches market status and waits for OPEN.
- Each cycle:
  - Pulls bid/ask for BULL, BEAR, RITC (USD) and USD/CAD; converts RITC to CAD.
  - Updates current positions and checks exposure limits.
  - Spread capture: if spread exceeds threshold, simultaneously post limit buy at bid and sell at ask (sliced).
  - Evaluates tender offers vs live book, net of costs/fees; accepts and hedges when profitable and within limits.
  - Cancels/market-sweeps stale open orders if price drifts away.
- Costs/thresholds are parameterized (e.g., ARB_THRESHOLD, FEE_MKT, size caps).

## Requirements
- Python 3.9+
- requests

`pip install requests`

## Configuration
Edit the constants at the top of the script:
- API endpoint: API = "http://localhost:9999/v1"
- API key header: API_KEY = {"X-API-Key": "YOUR_KEY"}
- Symbols: CAD, USD, BULL, BEAR, RITC
- Trading params: FEE_MKT, REBATE_LMT, ARB_THRESHOLD, MAX_SIZE_EQUITY, MAX_STOCK_TRADE_SIZE, exposure limits, etc.

Example:
```
API = "http://localhost:9999/v1"
API_KEY = {"X-API-Key": "REPLACE_ME"}
ARB_THRESHOLD = 0.07
MAX_STOCK_TRADE_SIZE = 10000
MAX_GROSS = 300000
```

## Run
1) Start the RIT simulator and case on localhost:9999.
2) Set your API key in the script.
3) Run:
   python arbitrage.py
4) The bot will wait for market ACTIVE, then trade until case closure.

## Strategy details
- Spread capture (BULL/BEAR/RITC):
  - If ask - bid > threshold, place paired limit orders: buy at bid, sell at ask, sliced to size caps.
  - For RITC, converts USD quotes to CAD using USD/CAD bid/ask to ensure CAD-consistent spread.
- Tender offers:
  - Compares tender price vs live bid/ask, subtracting modeled costs/fees.
  - Ensures within gross/net limits; accepts offer and hedges using limit/market orders when profitable.
- Risk & liquidity:
  - within_limits() guards net and gross exposure.
  - settle_limit_orders() cancels open limits that drift away and replaces with market orders to reduce inventory risk.

## Notes and assumptions
- Designed for the RIT contest API; endpoints may differ in other venues.
- Fee/slippage model is simplified; tune ARB_THRESHOLD and get_cost() for your venue.
- Example logic uses top-of-book only; depth and queue position are not modeled.
- Uses limit orders for spread capture and market sweeps for stale inventory.

## Extending
- Add queue-aware pricing and inventory skew.
- Incorporate depth-of-book analytics and volatility-sensitive thresholds.
- Replace static params with config/env vars or CLI flags.
- Add logging/metrics and backtest harness.

## Disclaimer
For educational/simulation use only. Not investment advice. Use at your own risk.
