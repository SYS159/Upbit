import pyupbit
import pandas as pd
import time

# # 1. 대상 종목 및 맞춤 설정 (익절 수치 ts_activation 추가)
# strategy_config = {
#     "KRW-BTC": {"rsi": 30, "ts_act": 1.0},  # 비트는 1%부터 익절 감시
#     "KRW-ETH": {"rsi": 25, "ts_act": 1.5},  # 이더는 1.5%
#     "KRW-SOL": {"rsi": 25, "ts_act": 2.0},  # 솔라나는 2%
#     "KRW-XRP": {"rsi": 25, "ts_act": 2.0}   # 리플도 2%
# }


# 테스트용 임
strategy_config = {
    "KRW-BTC": {"rsi": 30, "ts_act": 1.0},
    "KRW-ETH": {"rsi": 25, "ts_act": 1.5},
    "KRW-SOL": {"rsi": 25, "ts_act": 2.0},
    "KRW-XRP": {"rsi": 25, "ts_act": 2.0},

    "KRW-ADA": {"rsi": 25, "ts_act": 1.0},
    "KRW-AVAX": {"rsi": 25, "ts_act": 1.0},
    "KRW-DOT": {"rsi": 25, "ts_act": 1.0},
    "KRW-TRX": {"rsi": 25, "ts_act": 1.0},
}


target_tickers = list(strategy_config.keys())

# --- [공통 파라미터] ---
ts_callback = 0.5
stop_loss = -2.0
trend_exit_fee = -1.0
vol_factor = 2.5

def get_rsi(df, period=14):
    delta = df['close'].diff()
    up, down = delta.copy(), delta.copy()
    up[up < 0], down[down > 0] = 0, 0
    _gain = up.ewm(com=(period - 1), min_periods=period).mean()
    _loss = down.abs().ewm(com=(period - 1), min_periods=period).mean()
    return 100 - (100 / (1 + (_gain / _loss)))

results = []

print("🔎 [V5.2 TEST] 종목별 차등 익절 백테스팅 시작...")

for ticker in target_tickers:
    config = strategy_config[ticker]
    rsi_limit = config['rsi']
    ts_act = config['ts_act']
    
    df = None
    for _ in range(3):
        try:
            df = pyupbit.get_ohlcv(ticker, interval="minute5", count=2016)
            if df is not None: break
            time.sleep(1)
        except: time.sleep(1)

    if df is None: continue
    
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
            cond_rsi = (curr['rsi'] < rsi_limit)

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
            # 1. 종목별 맞춤 트레일링 스톱 (비트는 1.0%부터 작동)
            if profit_rate >= ts_act and drop_from_max >= ts_callback: is_sell = True
            # 2. 고정 손절
            elif profit_rate <= stop_loss: is_sell = True
            # 3. 데드크로스 탈출 (수정된 로직)
            elif curr['ma3'] < curr['ma10'] and profit_rate < ts_act:
                if profit_rate < trend_exit_fee: is_sell = True

            if is_sell:
                hold = False
                total_yield *= (curr['close'] / buy_price) - (fee * 2)

    final_profit = (total_yield - 1) * 100
    results.append({"종목": ticker, "목표익절(%)": ts_act, "최종수익(%)": round(final_profit, 2), "매매횟수": trade_count})
    print(f"✅ {ticker} 분석 완료")

    time.sleep(0.5) # 업비트 서버 보호를 위한 휴식

print("\n" + "="*60)
print("        [ V5.2 리포트 ]")
print("="*60)
if results:
    df_res = pd.DataFrame(results).sort_values(by="최종수익(%)", ascending=False)
    print(df_res.to_string(index=False))
else:
    print("분석 결과가 없습니다.")
print("="*60)