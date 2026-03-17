import pyupbit
import pandas as pd
import time

# 💡 [추가됨] 업비트 차단 방지용 안전한 데이터 수집 함수
def get_safe_ohlcv(ticker, days=7):
    count = days * 288 # 5분봉 하루 288개
    df_list = []
    to_date = None
    request_count = (count // 200) + 1 # 200개씩 몇 번 요청할지 계산
    
    for _ in range(request_count):
        df = pyupbit.get_ohlcv(ticker, interval="minute5", count=200, to=to_date)
        
        # 서버 지연 시 1초 쉬고 재시도
        if df is None or df.empty:
            time.sleep(1)
            df = pyupbit.get_ohlcv(ticker, interval="minute5", count=200, to=to_date)
            if df is None or df.empty: 
                break
                
        df_list.append(df)
        to_date = df.index[0] # 받은 데이터 중 가장 옛날 시간을 다음 요청 기준으로 설정
        time.sleep(0.2) # 🔥 핵심: 쪼개서 받을 때마다 0.2초 휴식!
        
    if not df_list: return None
    
    # 조각난 데이터 합치고 시간순 정렬
    final_df = pd.concat(df_list).sort_index()
    final_df = final_df[~final_df.index.duplicated(keep='last')] # 중복 제거
    return final_df.tail(count) # 딱 원하는 갯수만 잘라서 반환

# --- [시뮬레이션 로직 (이전과 동일)] ---
def run_simulation(ticker, df, use_rsi_drop, vol_factor, rsi_threshold=30, rsi_max=50, ts_act=1.0, ts_callback=0.5, stop_loss=-2.0, trend_exit_fee=-1.0):
    balance = 0
    avg_buy_price = 0
    max_price = 0
    total_profit_rate = 1.0  
    
    trade_count = 0
    win_count = 0
    gold_count = 0
    rsi_count = 0
    current_buy_reason = ""

    for i in range(25, len(df)): # MA20 계산을 위해 시작 인덱스를 조금 넉넉하게 변경
        curr_close = df['close'].iloc[i]
        curr_rsi = df['rsi'].iloc[i]
        
        # 💡 [핵심 수정] 3, 10 -> 5, 20으로 변수명 및 데이터 변경
        ma5_prev = df['ma5'].iloc[i-1]
        ma20_prev = df['ma20'].iloc[i-1]
        ma5_curr = df['ma5'].iloc[i]
        ma20_curr = df['ma20'].iloc[i]
        
        vol_curr = df['volume'].iloc[i]
        vol_avg_curr = df['vol_avg'].iloc[i]

        if balance == 0:
            # 💡 [핵심 수정] 골든크로스 로직 5선, 20선 교차 확인
            cond_gold = (ma5_prev < ma20_prev and 
                         ma5_curr > ma20_curr and 
                         vol_curr > vol_avg_curr * vol_factor and 
                         curr_rsi < rsi_max)
            # 👇 수정된 부분: "이전 캔들에서는 RSI가 바닥이었고, 이번 캔들에서 위로 뚫고 올라왔는가?"
            # prev_rsi = df['rsi'].iloc[i-1]
            # cond_rsi = (prev_rsi < rsi_threshold and curr_rsi >= rsi_threshold) if use_rsi_drop else False
            # 결과가 예전께 더 좋아서 현재는 예전꺼 그대로 반영.
            cond_rsi = (curr_rsi < rsi_threshold) if use_rsi_drop else False

            if cond_gold or cond_rsi:
                balance = 1
                avg_buy_price = curr_close
                max_price = curr_close
                
                if cond_gold:
                    current_buy_reason = "gold"
                else:
                    current_buy_reason = "rsi"
                
        elif balance > 0:
            profit_rate = ((curr_close - avg_buy_price) / avg_buy_price) * 100
            max_price = max(max_price, curr_close)
            drop_from_max = ((max_price - curr_close) / max_price) * 100
            max_profit_rate = ((max_price - avg_buy_price) / avg_buy_price) * 100

            is_sell = False

            if max_profit_rate >= ts_act and drop_from_max >= ts_callback:
                is_sell = True
            elif profit_rate <= stop_loss:
                is_sell = True
            # 💡 [핵심 수정] 추세 하락 탈출도 5선, 20선 데드크로스 확인
            elif ma5_curr < ma20_curr and profit_rate < ts_act:
                if profit_rate < trend_exit_fee:
                    is_sell = True

            if is_sell:
                net_profit = profit_rate - 0.1 
                total_profit_rate *= (1 + net_profit / 100)
                trade_count += 1
                
                if net_profit > 0: 
                    win_count += 1
                    
                if current_buy_reason == "gold":
                    gold_count += 1
                elif current_buy_reason == "rsi":
                    rsi_count += 1
                    
                balance = 0

    win_rate = (win_count / trade_count * 100) if trade_count > 0 else 0
    final_profit = (total_profit_rate - 1) * 100

    return {
        '종목': ticker,
        'RSI낙주': 'O' if use_rsi_drop else 'X',
        '거래량': vol_factor,
        '총매수': trade_count,
        '골든': gold_count,
        'RSI': rsi_count,
        '승률(%)': round(win_rate, 1),
        '총수익(%)': round(final_profit, 2)
    }

if __name__ == "__main__":
    pd.set_option('display.max_rows', None)
    # 한 줄에 다 나오게 너비 설정 조정
    pd.set_option('display.width', 1000) 
    
    target_tickers = [
        "KRW-BTC", "KRW-ETH", "KRW-SOL", "KRW-XRP", 
        "KRW-AVAX",
        "KRW-NEAR","KRW-LINK"
    ]
    
    rsi_drop_options = [True, False]
    vol_factor_options = [1.0, 1.5, 2.0, 2.5]
    
    ts_act_dict = {
        "KRW-BTC": 1.0, "KRW-ETH": 1.5, "KRW-SOL": 1.5, "KRW-XRP": 1.5, "KRW-AVAX": 1.0,
        "KRW-NEAR":1.5,"KRW-LINK":1.0
        # 아무것도 적지않으면 자동으로 1%로 테스트
    }
    
    print("🚀 [세부 분석 버전] 7일치 차트 다운로드 시작 (시간이 조금 걸립니다)...\n")
    
    all_results = []
    
    for ticker in target_tickers:
        print(f"[{ticker}] 안전하게 데이터 모으는 중...", end=" ")
        
        df = get_safe_ohlcv(ticker, days=7)
        
        if df is None or len(df) == 0:
            print("❌ 실패")
            continue
        print("✅ 완료")
            
        # 💡 [핵심 수정] MA5, MA20 계산으로 변경
        df['ma5'] = df['close'].rolling(window=5).mean()
        df['ma20'] = df['close'].rolling(window=20).mean()
        # 몇개봉의 거래량을 기준으로 할것인가
        df['vol_avg'] = df['volume'].rolling(window=10).mean()
        
        delta = df['close'].diff()
        up, down = delta.copy(), delta.copy()
        up[up < 0], down[down > 0] = 0, 0
        _gain = up.ewm(com=13, min_periods=14).mean()
        _loss = down.abs().ewm(com=13, min_periods=14).mean()
        df['rsi'] = 100 - (100 / (1 + (_gain / _loss)))

        for use_rsi in rsi_drop_options:
            for v_factor in vol_factor_options:
                result = run_simulation(
                    ticker=ticker, 
                    df=df, 
                    use_rsi_drop=use_rsi,
                    vol_factor=v_factor,
                    ts_act=ts_act_dict.get(ticker, 1.0)
                )
                
                if result:
                    all_results.append(result)

    if all_results:
        df_summary = pd.DataFrame(all_results)
        
        # 💡 [에러 수정] '총수익률(%)' -> '총수익(%)' 으로 변경 완료
        df_sorted = df_summary.sort_values(by=['종목', '총수익(%)'], ascending=[True, False])
        
        # 보기 편하게 컬럼 순서 재배치 (선택 사항)
        columns_order = ['종목', 'RSI낙주', '거래량', '총매수', '골든', 'RSI', '승률(%)', '총수익(%)']
        df_sorted = df_sorted[columns_order]
        
        print("\n--- 📊 전략 조합별 상세 백테스트 결과 (MA5/MA20 적용, 최근 7일) ---")
        print(df_sorted.to_string(index=False))