import pyupbit
import time
import itertools

# =========================
# 🔥 후보 파라미터
# =========================
ts_candidates = [1.0, 1.5, 2.0, 3.0]
sl_candidates = [-0.8, -1.0, -1.5]
vol_candidates = [1.3, 1.5, 2.0]

best_params = {
    "ts": 1.5,
    "sl": -1.0,
    "vol": 1.5
}

# =========================
# 🔥 백테스트 (간이)
# =========================
def backtest(df, ts, sl, vol_mul):
    balance = 1000000
    position = 0
    buy_price = 0

    ma20 = df['close'].rolling(20).mean()
    vol_avg = df['volume'].rolling(20).mean()

    for i in range(20, len(df)):
        price = df['close'].iloc[i]

        # 매수
        if position == 0:
            cond = (
                price > ma20.iloc[i] and
                df['volume'].iloc[i] > vol_avg.iloc[i] * vol_mul
            )
            if cond:
                position = balance
                buy_price = price
                balance = 0

        # 매도
        else:
            profit = (price - buy_price) / buy_price * 100

            if profit >= ts or profit <= sl:
                balance = position * (price / buy_price)
                position = 0

    return balance

# =========================
# 🔥 자동 최적화
# =========================
def optimize_params(ticker):
    global best_params

    df = pyupbit.get_ohlcv(ticker, interval="minute15", count=200)
    if df is None:
        return

    best_score = 0

    for ts, sl, vol in itertools.product(ts_candidates, sl_candidates, vol_candidates):
        result = backtest(df, ts, sl, vol)

        if result > best_score:
            best_score = result
            best_params = {
                "ts": ts,
                "sl": sl,
                "vol": vol
            }

    print(f"🔥 최적 파라미터: {best_params}")