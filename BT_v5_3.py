import pyupbit
import pandas as pd
import time

# --- [설정: 정예 8종목 및 차등 익절] ---
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

# 공통 파라미터
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
print("🔎 [V5.3 TEST] V5.2 + RSI 55 상한 필터 백테스팅 시작...")

for ticker in target_tickers:
    config = strategy_config[ticker]
    
    # --- [수정된 데이터 수집 로직: 재시도 추가] ---
    df = None
    for attempt in range(3):  # 최대 3번 재시도
        df = pyupbit.get_ohlcv(ticker, interval="minute5", count=2016)
        if df is not None:
            break
        print(f"⚠️ {ticker} 데이터 수집 실패... {attempt+1}차 재시도 중")
        time.sleep(2) # 실패 시 2초 대기
    
    if df is None:
        print(f"❌ {ticker} 데이터를 끝내 가져오지 못했습니다.")
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
            # 1. 골든크로스 조건 (RSI 55 미만일 때만!)
            cond_gold = (prev['ma3'] < prev['ma10'] and 
                         curr['ma3'] > curr['ma10'] and 
                         curr['volume'] > curr['vol_avg'] * vol_factor and
                         curr['rsi'] < 40) # <--- V5.3 핵심 필터
            
            # 2. RSI 낙주 조건 (이미 rsi_limit이 낮으므로 55 조건 자동 충족)
            cond_rsi = (curr['rsi'] < config['rsi'])

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
            # 트레일링 스톱 익절
            if profit_rate >= config['ts_act'] and drop_from_max >= ts_callback: is_sell = True
            # 고정 손절
            elif profit_rate <= stop_loss: is_sell = True
            # 데드크로스 탈출
            elif curr['ma3'] < curr['ma10'] and profit_rate < config['ts_act']:
                if profit_rate < trend_exit_fee: is_sell = True

            if is_sell:
                hold = False
                total_yield *= (curr['close'] / buy_price) - (fee * 2)

    final_profit = (total_yield - 1) * 100
    results.append({"종목": ticker, "최종수익(%)": round(final_profit, 2), "매매횟수": trade_count})
    print(f"✅ {ticker} 분석 완료")
    time.sleep(1)

print("\n" + "="*60)
print("          [ V5.3 리포트: RSI 55 필터 적용 ]")
print("="*60)
if results:
    df_res = pd.DataFrame(results).sort_values(by="최종수익(%)", ascending=False)
    print(df_res.to_string(index=False))
print("="*60)