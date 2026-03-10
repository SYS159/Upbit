
# 🔎 [V5 CUSTOM] 코인별 맞춤 RSI 백테스팅 시작...
# ✅ KRW-BTC 분석 완료 (RSI:30)
# ✅ KRW-ETH 분석 완료 (RSI:25)
# ✅ KRW-SOL 분석 완료 (RSI:25)
# ✅ KRW-XRP 분석 완료 (RSI:25)

# ============================================================
#           [ V5 CUSTOM: 종목별 맞춤 RSI 리포트 ]
# ============================================================
#      종목  설정RSI  수익률(%)  매매횟수
# KRW-SOL     25   12.39     8
# KRW-XRP     25    3.72     6
# KRW-ETH     25    1.42     7
# KRW-BTC     30   -0.21    12
# ============================================================

import pyupbit
import pandas as pd
import time

# 1. 대상 종목 (ETC 제외) 및 종목별 맞춤 RSI 설정
custom_rsi_settings = {
    "KRW-BTC": 30,  # 비트는 30이 안정적
    "KRW-ETH": 25,  # 이더는 25가 수익률 우세
    "KRW-SOL": 25,  # 솔라나는 변동성이 커서 25가 유리
    "KRW-XRP": 25   # 리플도 25에서 방어력 확인됨
}

target_tickers = list(custom_rsi_settings.keys())

# --- [전용 설정값] ---
ts_activation = 2.0
ts_callback = 0.5
stop_loss = -2.0
vol_factor = 2.5

def get_rsi(df, period=14):
    delta = df['close'].diff()
    up, down = delta.copy(), delta.copy()
    up[up < 0], down[down > 0] = 0, 0
    _gain = up.ewm(com=(period - 1), min_periods=period).mean()
    _loss = down.abs().ewm(com=(period - 1), min_periods=period).mean()
    return 100 - (100 / (1 + (_gain / _loss)))

results = []

print(f"🔎 [V5 CUSTOM] 코인별 맞춤 RSI 백테스팅 시작...")

for ticker in target_tickers:
    rsi_threshold = custom_rsi_settings[ticker]
    df = None
    
    for attempt in range(3):
        try:
            df = pyupbit.get_ohlcv(ticker, interval="minute5", count=2016)
            if df is not None: break
            time.sleep(1)
        except:
            time.sleep(1)

    if df is None:
        print(f"❌ {ticker} 데이터 로드 실패")
        continue
    
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
            # 해당 코인의 맞춤형 RSI 기준 사용
            cond_gold = (prev['ma3'] < prev['ma10'] and curr['ma3'] > curr['ma10'] and curr['volume'] > curr['vol_avg'] * vol_factor)
            cond_rsi = (curr['rsi'] < rsi_threshold)

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
                if profit_rate < -1.0: # 무한 매매 방지 문턱
                    is_sell = True

            if is_sell:
                hold = False
                yield_rate = (curr['close'] / buy_price) - (fee * 2)
                total_yield *= yield_rate

    final_profit = (total_yield - 1) * 100
    results.append({"종목": ticker, "설정RSI": rsi_threshold, "수익률(%)": round(final_profit, 2), "매매횟수": trade_count})
    print(f"✅ {ticker} 분석 완료 (RSI:{rsi_threshold})")

# 결과 출력
print("\n" + "="*60)
print("          [ V4 CUSTOM: 종목별 맞춤 RSI 리포트 ]")
print("="*60)
print(pd.DataFrame(results).sort_values(by="수익률(%)", ascending=False).to_string(index=False))
print("="*60)