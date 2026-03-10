
# RSI30
# ==================================================
#      종목  최종수익(%)  매매횟수
# KRW-XRP     6.80     9
# KRW-BTC     3.02    10
# KRW-SOL     1.99    10
# KRW-ETH     0.84    14
# KRW-ETC    -3.32    14
# ==================================================
# RSI25
# ==================================================
#      종목  최종수익(%)  매매횟수
# KRW-SOL    13.65     8
# KRW-XRP     6.69     5
# KRW-ETH     5.80     7
# KRW-ETC    -1.00     8
# KRW-BTC    -1.75    11
# ==================================================
# RSI20
# ==================================================
#      종목  최종수익(%)  매매횟수
# KRW-SOL     6.52     5
# KRW-XRP     5.90     5
# KRW-ETH     4.30     6
# KRW-BTC     3.11     6
# KRW-ETC    -2.68     6
# ==================================================

import pyupbit
import pandas as pd
import time

# 대상 종목 5개 확실히 지정
target_tickers = ["KRW-BTC", "KRW-ETH", "KRW-SOL", "KRW-ETC", "KRW-XRP"]

# 전략 설정값
ts_activation = 2.0
ts_callback = 0.5
stop_loss = -2.0
rsi_oversold = 20
vol_factor = 2.5

def get_rsi(df, period=14):
    delta = df['close'].diff()
    up, down = delta.copy(), delta.copy()
    up[up < 0], down[down > 0] = 0, 0
    _gain = up.ewm(com=(period - 1), min_periods=period).mean()
    _loss = down.abs().ewm(com=(period - 1), min_periods=period).mean()
    return 100 - (100 / (1 + (_gain / _loss)))

results = []

print("🔎 [V4 FINAL CHECK] 5개 종목 전수 조사 시작...")

for ticker in target_tickers:
    df = None
    # --- 데이터 로드 재시도 로직 (최대 3번) ---
    for attempt in range(3):
        try:
            df = pyupbit.get_ohlcv(ticker, interval="minute5", count=2016)
            if df is not None:
                break
            print(f"⚠️ {ticker} 데이터 로드 재시도 중... ({attempt + 1}/3)")
            time.sleep(2) # 재시도 전 대기
        except Exception:
            time.sleep(2)

    if df is None:
        print(f"❌ {ticker} 데이터를 끝내 가져오지 못했습니다. 넘어갑니다.")
        continue
    
    # 지표 계산
    df['ma3'] = df['close'].rolling(window=3).mean()
    df['ma10'] = df['close'].rolling(window=10).mean()
    df['vol_avg'] = df['volume'].rolling(window=10).mean()
    df['rsi'] = get_rsi(df)
    
    hold = False
    buy_price = 0
    max_price = 0
    total_yield = 1.0
    fee = 0.0005 
    trade_count = 0

    for i in range(15, len(df)):
        curr = df.iloc[i]
        prev = df.iloc[i-1]

        if not hold:
            cond_gold = (prev['ma3'] < prev['ma10'] and curr['ma3'] > curr['ma10'] and curr['volume'] > curr['vol_avg'] * vol_factor)
            cond_rsi = (curr['rsi'] < rsi_oversold)
            if cond_gold or cond_rsi:
                hold = True
                buy_price = curr['close']
                max_price = buy_price
                trade_count += 1
        else:
            max_price = max(max_price, curr['high'])
            profit_rate = (curr['close'] - buy_price) / buy_price * 100
            drop_from_max = (max_price - curr['close']) / max_price * 100

            is_sell = False
            if profit_rate >= ts_activation and drop_from_max >= ts_callback: is_sell = True
            elif profit_rate <= stop_loss: is_sell = True
            elif curr['ma3'] < curr['ma10'] and profit_rate < ts_activation:
                # 무한 매매 방지 문턱 (-1.0%)
                if profit_rate < -1:
                    is_sell = True

            if is_sell:
                hold = False
                yield_rate = (curr['close'] / buy_price) - (fee * 2)
                total_yield *= yield_rate

    final_profit = (total_yield - 1) * 100
    results.append({"종목": ticker, "최종수익(%)": round(final_profit, 2), "매매횟수": trade_count})
    print(f"✅ {ticker} 분석 완료")
    time.sleep(0.5) # 종목 간 API 호출 간격 확보

# 결과 출력
print("\n" + "="*50)
print(pd.DataFrame(results).sort_values(by="최종수익(%)", ascending=False).to_string(index=False))
print("="*50)