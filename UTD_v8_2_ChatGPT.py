import pyupbit
import asyncio
import time
import os
import requests
import itertools
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor

load_dotenv()

access = os.getenv("UPBIT_ACCESS_KEY")
secret = os.getenv("UPBIT_SECRET_KEY")
webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

upbit = pyupbit.Upbit(access, secret)

# =========================
# 🔥 설정
# =========================
MAX_HOLDINGS = 3
BUY_AMOUNT = 348000

CACHE_TTL = 15
OPTIMIZE_INTERVAL = 1800

ohlcv_cache = {}
max_price_dict = {}

executor = ThreadPoolExecutor(max_workers=5)

target_tickers = []
last_coin_update = 0
last_opt_time = 0

# 🔥 튜닝 후보
ts_candidates = [1.0, 1.5, 2.0]
sl_candidates = [-0.8, -1.0, -1.5]
vol_candidates = [1.3, 1.5, 2.0]

best_params = {"ts": 1.5, "sl": -1.0, "vol": 1.5}

# =========================
# 유틸
# =========================
def send_msg(msg):
    try:
        requests.post(webhook_url, json={"content": msg})
    except:
        pass

def get_rsi(df):
    delta = df['close'].diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    gain = up.ewm(com=13).mean()
    loss = down.ewm(com=13).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# =========================
# 🔥 캐싱
# =========================
def get_ohlcv_cached(ticker):
    now = time.time()

    if ticker in ohlcv_cache:
        ts, df = ohlcv_cache[ticker]
        if now - ts < CACHE_TTL:
            return df

    df = pyupbit.get_ohlcv(ticker, interval="minute15", count=100)
    time.sleep(0.12)

    ohlcv_cache[ticker] = (now, df)
    return df

# =========================
# 🔥 비동기
# =========================
async def fetch_all(tickers):
    loop = asyncio.get_event_loop()
    tasks = [
        loop.run_in_executor(executor, lambda t=t: (t, get_ohlcv_cached(t)))
        for t in tickers
    ]
    results = await asyncio.gather(*tasks)
    return {t: df for t, df in results if df is not None}

# =========================
# 🔥 코인 선별
# =========================
def select_coins():
    global target_tickers

    tickers = pyupbit.get_tickers(fiat="KRW")[:30]
    selected = []

    for t in tickers:
        df = get_ohlcv_cached(t)
        if df is None:
            continue

        ma20 = df['close'].rolling(20).mean()
        ma60 = df['close'].rolling(60).mean()
        vol_avg = df['volume'].rolling(20).mean()

        if (
            df['close'].iloc[-1] > ma20.iloc[-1] > ma60.iloc[-1]
            and df['volume'].iloc[-1] > vol_avg.iloc[-1] * 1.5
        ):
            selected.append(t)

    target_tickers = selected[:5]

# =========================
# 🔥 백테스트
# =========================
def backtest(df, ts, sl, vol):
    balance = 1.0
    position = 0
    buy_price = 0

    ma20 = df['close'].rolling(20).mean()
    vol_avg = df['volume'].rolling(20).mean()

    for i in range(20, len(df)):
        price = df['close'].iloc[i]

        if position == 0:
            if price > ma20.iloc[i] and df['volume'].iloc[i] > vol_avg.iloc[i] * vol:
                position = balance
                buy_price = price
                balance = 0
        else:
            profit = (price - buy_price) / buy_price * 100
            if profit >= ts or profit <= sl:
                balance = position * (price / buy_price)
                position = 0

    return balance

# =========================
# 🔥 자동 튜닝
# =========================
def optimize():
    global best_params

    df = pyupbit.get_ohlcv("KRW-BTC", interval="minute15", count=200)
    if df is None:
        return

    best_score = 0

    for ts, sl, vol in itertools.product(ts_candidates, sl_candidates, vol_candidates):
        score = backtest(df, ts, sl, vol)
        if score > best_score:
            best_score = score
            best_params = {"ts": ts, "sl": sl, "vol": vol}

    send_msg(f"🔥 최적화: {best_params}")

# =========================
# 🔥 매매
# =========================
def trade(ticker, df):
    curr_price = pyupbit.get_current_price(ticker)
    time.sleep(0.1)

    ma20 = df['close'].rolling(20).mean()
    vol_avg = df['volume'].rolling(20).mean()
    rsi = get_rsi(df)

    balance = upbit.get_balance(ticker)

    ts = best_params["ts"]
    sl = best_params["sl"]
    vol_mul = best_params["vol"]

    # 매수
    if balance == 0:
        if (
            curr_price > ma20.iloc[-1]
            and df['volume'].iloc[-1] > vol_avg.iloc[-1] * vol_mul
            and rsi.iloc[-1] > 50
        ):
            krw = upbit.get_balance("KRW")
            if krw > BUY_AMOUNT:
                upbit.buy_market_order(ticker, BUY_AMOUNT)
                send_msg(f"✅ {ticker} 매수")

    # 매도
    else:
        avg = upbit.get_avg_buy_price(ticker)
        profit = (curr_price - avg) / avg * 100

        if ticker not in max_price_dict:
            max_price_dict[ticker] = curr_price

        max_price_dict[ticker] = max(max_price_dict[ticker], curr_price)

        drop = (max_price_dict[ticker] - curr_price) / max_price_dict[ticker] * 100
        max_profit = (max_price_dict[ticker] - avg) / avg * 100

        if (max_profit >= ts and drop >= 0.5) or profit <= sl:
            upbit.sell_market_order(ticker, balance)
            send_msg(f"❌ {ticker} 매도 {profit:.2f}%")
            max_price_dict.pop(ticker, None)

# =========================
# 🔥 메인
# =========================
async def main():
    global last_coin_update, last_opt_time

    print("🔥 FINAL 자동매매 시작")

    while True:
        now = time.time()

        if now - last_coin_update > 90:
            select_coins()
            last_coin_update = now
            print("🎯", target_tickers)

        if now - last_opt_time > OPTIMIZE_INTERVAL:
            optimize()
            last_opt_time = now

        if not target_tickers:
            await asyncio.sleep(2)
            continue

        data = await fetch_all(target_tickers)

        balances = upbit.get_balances()
        holding_count = len([b for b in balances if b['currency'] != 'KRW'])

        for t, df in data.items():
            if df is None:
                continue
            trade(t, df)

        await asyncio.sleep(2)

asyncio.run(main())