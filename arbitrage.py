# Algorithmic Arbitrage ETF Trading (Rotman Trading Simulator)
# Builds upon the Liability Trading case to manage liquidity risks while while exploiting arbitrage strategies
# Written by: Karan Manoj Shah
# Written on: 20 September 2025

import requests
from time import sleep

API = "http://localhost:9999/v1"
API_KEY = {"X-API-Key": "KEY_HERE"}

# Tickers
CAD  = "CAD"    # currency instrument quoted in CAD
USD  = "USD"    # price of 1 USD in CAD (i.e., USD/CAD)
BULL = "BULL"   # stock in CAD
BEAR = "BEAR"   # stock in CAD
RITC = "RITC"   # ETF quoted in USD

FEE_MKT = 0.02          # $/share (market)
REBATE_LMT = 0.01       # $/share (passive) - not used in this baseline
MAX_SIZE_EQUITY = 10000 # per order for BULL/BEAR/RITC
MAX_SIZE_FX = 2500000   # per order for CAD/USD
MAX_STOCK_TRADE_SIZE = 10000
MAX_LONG_NET  = 200000
MAX_SHORT_NET = -200000
MAX_GROSS     = 300000

# Cushion to beat fees & slippage.
# 3 legs with market orders => ~0.06 CAD/sh cost; add a bit more for safety.
ARB_THRESHOLD = 0.07

# Gets simulation status (active or stopped) for the tick
def get_tick(session):
    r = session.get(f"{API}/case")
    r.raise_for_status()
    j = r.json()
    return j["tick"], j["status"]

# get best bid and ask prices for given ticker
def get_bid_ask(session, ticker):
    r = session.get(f"{API}/securities/book", params={"ticker": ticker})
    r.raise_for_status()
    book = r.json()
    bid = float(book["bids"][0]["price"] if book["bids"] else 0.0)
    ask = float(book["asks"][0]["price"] if book["asks"] else 0.0)
    return bid, ask

# get current position on each security
def pos_map(session):
    r = session.get(f"{API}/securities")
    r.raise_for_status()
    out = {p["ticker"]: int(p.get("position", 0)) for p in r.json()}
    for k in (BULL, BEAR, RITC, USD, CAD):
        out.setdefault(k, 0)
    return out

# check that current position doesn't exceed trading limits
def within_limits(pos):
    gross = abs(pos[BULL]) + abs(pos[BEAR]) + abs(pos[RITC])
    net = pos[BULL] + pos[BEAR] + pos[RITC]
    return (gross < MAX_GROSS) and (MAX_SHORT_NET < net < MAX_LONG_NET)

# place a limit buy order at given price
def buy(session, ticker, quantity, price):
    print("buy", ticker, quantity)
    while quantity > MAX_STOCK_TRADE_SIZE:
        session.post(f"{API}/orders?ticker={ticker}&type=LIMIT&quantity={MAX_STOCK_TRADE_SIZE}&action=BUY&price={price}")
        quantity -= MAX_STOCK_TRADE_SIZE
    if quantity > 0:
        session.post(f"{API}/orders?ticker={ticker}&type=LIMIT&quantity={quantity}&action=BUY&price={price}")

# place a limit sell order at given price
def sell(session, ticker, quantity, price):
    print("sell", ticker, quantity)
    while quantity > MAX_STOCK_TRADE_SIZE:
        session.post(f"{API}/orders?ticker={ticker}&type=LIMIT&quantity={MAX_STOCK_TRADE_SIZE}&action=SELL&price={price}")
        quantity -= MAX_STOCK_TRADE_SIZE
    if quantity > 0:
        session.post(f"{API}/orders?ticker={ticker}&type=LIMIT&quantity={quantity}&action=SELL&price={price}")

# get cost of buying a security at market price
def get_cost(qty):
    cost = 0
    while qty > MAX_STOCK_TRADE_SIZE:
        cost += 0.2
        qty -= MAX_STOCK_TRADE_SIZE
    if qty > 0:
        cost += 0.2
    return cost * 2

# evaluate a tender offer and execute if profitable
def evaluate_tender(session, tender, positions, prices):
    tender_id = tender["tender_id"]
    price = tender["price"]
    ticker = tender["ticker"]
    action = tender["action"]
    qty = tender["quantity"]

    if positions[ticker] == 0: # no current position on security for which tender offer has been made
        if action == "SELL": # offer made to sell security
            cost_to_buy = prices[ticker][1] * qty
            cost_to_buy += get_cost(qty)
            if price * qty > cost_to_buy + FEE_MKT * 3: # offer is profitable
                buy(session, ticker, qty, prices[ticker][1])
                session.post(f"{API}/tenders/{tender_id}", params={"price": price})
        else: # offer made to buy security
            income_at_sell = prices[ticker][0] * qty
            income_at_sell -= get_cost(qty)
            if price * qty + FEE_MKT * 3 < income_at_sell: # offer is profitable
                session.post(f"{API}/tenders/{tender_id}", params={"price": price})
                sell(session, ticker, qty, prices[ticker][0])
    else: # existing position on security for which tender offer has been made
        if action == "BUY": # offer made to buy security
            positions[ticker] += qty
            if (within_limits(positions)):
                income_at_sell = prices[ticker][0] * qty
                income_at_sell -= get_cost(qty)
                if price * qty + FEE_MKT * 3 < income_at_sell: # offer is profitable
                    session.post(f"{API}/tenders/{tender_id}", params={"price": price})
                    sell(session, ticker, qty, prices[ticker][0])
            positions[ticker] -= qty
        else: # offer made to sell security
            positions[ticker] -= qty
            if within_limits(positions):
                cost_to_buy = prices[ticker][1] * qty
                cost_to_buy += get_cost(qty)
                if price * qty > cost_to_buy + 0.6: # offer is profitable
                    buy(session, ticker, qty, prices[ticker][1])
                    session.post(f"{API}/tenders/{tender_id}", params={"price": price})
            positions[ticker] += qty

# check if tenders are offered and evaluate them
def check_tenders(session, positions, prices):
    res = session.get(f"{API}/tenders")
    res.raise_for_status()
    offers = res.json()

    if len(offers) > 0:
        evaluate_tender(session, offers[0], positions, prices)

def settle_limit_orders(session, prices):
    res = session.get(f"{API}/orders")
    for order in res.json():
        if order["status"] == "OPEN" and abs(prices[order["ticker"]][0] - order["price"]) > 1.5:
            session.delete(f"{API}/orders/{order['order_id']}")
            session.post(f"{API}/orders?ticker={order['ticker']}&type=MARKET&quantity={order['quantity']}&action={order['action']}&price={order['price']}")

if __name__ == "__main__":
    with requests.Session() as session:
        session.headers.update(API_KEY)

        tick, status = get_tick(session)

        # wait for market to open
        while status != "ACTIVE":
            sleep(0.5)
            tick, status = get_tick(session)

        # main loop
        while status == "ACTIVE":
            # get market prices for securities
            bull_bid, bull_ask = get_bid_ask(session, BULL)
            bear_bid, bear_ask = get_bid_ask(session, BEAR)
            ritc_bid_usd, ritc_ask_usd = get_bid_ask(session, RITC)
            usd_bid, usd_ask = get_bid_ask(session, USD)

            # convert ETF prices from USD to CAD
            ritc_bid = ritc_bid_usd * usd_bid
            ritc_ask = ritc_ask_usd * usd_ask

            prices = {
                "RITC": (ritc_bid, ritc_ask),
                "BEAR": (bear_bid, bear_ask),
                "BULL": (bull_bid, bull_ask)
            }

            # get current position on each security
            positions = pos_map(session)

            # find arbitrage opportunities on BULL
            if bull_ask - bull_bid > ARB_THRESHOLD:
                buy(session, BULL, 100, bull_bid)
                sell(session, BULL, 100, bull_ask)

            # find arbitrage opportunities on BEAR
            if bear_ask - bear_bid > ARB_THRESHOLD:
                buy(session, BEAR, 100, bear_bid)
                sell(session, BEAR, 100, bear_ask)

            # find arbitrage opportunities on RITC
            if ritc_ask - ritc_bid > 0.14:
                buy(session, RITC, 100, ritc_bid)
                sell(session, RITC, 100, ritc_ask)

            # check if tender offers are made
            check_tenders(session, positions, prices)

            # settle open limit orders that haven't been executed for too long
            settle_limit_orders(session, prices)

            sleep(0.4)
            tick, status = get_tick(session)
