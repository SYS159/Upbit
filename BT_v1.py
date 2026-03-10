
# =================================================================
#       [ V4 EXPERT: 지정가+RSI+TS 통합 리포트 ]
# =================================================================
#      종목  수익률(%)  매매횟수  승률(%)
# KRW-SOL   12.01    47   72.3
# KRW-BTC    9.84    61   77.0
# KRW-ETH    9.16    46   63.0
# KRW-XRP    8.09    38   78.9
# KRW-ETC    7.97    36   80.6
# =================================================================


import pyupbit
import pandas as pd
import time

# 대상 종목: 수익률 검증된 5개
target_tickers = ["KRW-BTC", "KRW-ETH", "KRW-SOL", "KRW-ETC", "KRW-XRP"]

# --- [전략 설정값] ---
ts_activation = 2.0  # 트레일링 스톱 활성화 (2%)
ts_callback = 0.5    # 고점 대비 하락 시 매도 (0.5%)
stop_loss = -2.0     # 손절선 (약간 넓게 조정)
vol_factor = 2.5     # 거래량 필터
rsi_oversold = 30    # RSI 과매도 기준 (낙주 매수용)
limit_order_dist = 0.001 # 지정가 매수 보정 (현재가보다 0.1% 아래에서 체결 가정)

def get_rsi(df, period=14):
    delta = df['close'].diff()
    up, down = delta.copy(), delta.copy()
    up[up < 0], down[down > 0] = 0, 0
    _gain = up.ewm(com=(period - 1), min_periods=period).mean()
    _loss = down.abs().ewm(com=(period - 1), min_periods=period).mean()
    RS = _gain / _loss
    return 100 - (100 / (1 + RS))

results = []

print("🚀 [V4 EXPERT] 지정가 + RSI + 트레일링 스톱 백테스팅 시작...")

for ticker in target_tickers:
    try:
        # 5분봉 7일치 데이터
        df = pyupbit.get_ohlcv(ticker, interval="minute5", count=2016)
        if df is None: continue
        
        # 지표 계산
        df['ma3'] = df['close'].rolling(window=3).mean()
        df['ma10'] = df['close'].rolling(window=10).mean()
        df['vol_avg'] = df['volume'].rolling(window=10).mean()
        df['rsi'] = get_rsi(df)
        
        # 비트코인 필터용 (일봉 5일선) - 백테스트 편의상 해당 시점 5분봉의 ma 계산으로 대체 가능하나 
        # 여기서는 단순화를 위해 매수 조건에 집중
        
        hold = False
        buy_price = 0
        max_price = 0
        total_yield = 1.0
        fee = 0.0005 # 지정가 매수 시 수수료는 동일하나 슬리피지 감소 효과 반영
        trade_count = 0
        win_count = 0

        for i in range(15, len(df)):
            curr = df.iloc[i]
            prev = df.iloc[i-1]

            if not hold:
                # [매수 조건 1] 3-10 골든크로스 + 거래량 폭발
                cond_gold = (prev['ma3'] < prev['ma10'] and curr['ma3'] > curr['ma10'] and curr['volume'] > curr['vol_avg'] * vol_factor)
                
                # [매수 조건 2] RSI 과매도 구간 (낙주 줍기)
                cond_rsi = (curr['rsi'] < rsi_oversold)

                if cond_gold or cond_rsi:
                    hold = True
                    # 지정가 매수 적용: 현재가보다 살짝 유리한 가격에 체결되었다고 가정 (슬리피지 방지)
                    buy_price = curr['close'] * (1 - limit_order_dist) 
                    max_price = buy_price
                    trade_count += 1
            else:
                max_price = max(max_price, curr['high'])
                profit_rate = (curr['close'] - buy_price) / buy_price * 100
                drop_from_max = (max_price - curr['close']) / max_price * 100

                is_sell = False
                # 1. 트레일링 스톱
                if (max_price - buy_price) / buy_price * 100 >= ts_activation:
                    if drop_from_max >= ts_callback:
                        is_sell = True
                
                # 2. 고정 손절
                if profit_rate <= stop_loss:
                    is_sell = True
                
                # 3. 데드크로스 (익절권 아닐 때만)
                if curr['ma3'] < curr['ma10'] and profit_rate < ts_activation:
                    is_sell = True

                if is_sell:
                    hold = False
                    # 지정가 매도 역시 현재가보다 0.1% 유리하게 체결 가정
                    sell_price = curr['close'] * (1 + limit_order_dist)
                    yield_rate = (sell_price / buy_price) - (fee * 2)
                    total_yield *= yield_rate
                    if yield_rate > 1.0: win_count += 1

        final_profit = (total_yield - 1) * 100
        win_rate = (win_count / trade_count * 100) if trade_count > 0 else 0
        results.append({"종목": ticker, "수익률(%)": round(final_profit, 2), "매매횟수": trade_count, "승률(%)": round(win_rate, 1)})
        print(f"✅ {ticker} 분석 완료")
        time.sleep(0.1)

    except Exception as e:
        print(f"❌ {ticker} 에러: {e}")

# 결과 출력
df_results = pd.DataFrame(results)
print("\n" + "="*65)
print("      [ V4 EXPERT: 지정가+RSI+TS 통합 리포트 ]")
print("="*65)
print(df_results.sort_values(by="수익률(%)", ascending=False).to_string(index=False))
print("="*65)