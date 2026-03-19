import pyupbit
import pandas as pd
import time

def get_safe_ohlcv(ticker, days=7):
    count = days * 288 
    df_list = []
    to_date = None
    request_count = (count // 200) + 1 
    
    for _ in range(request_count):
        df = pyupbit.get_ohlcv(ticker, interval="minute5", count=200, to=to_date)
        if df is None or df.empty:
            time.sleep(1)
            df = pyupbit.get_ohlcv(ticker, interval="minute5", count=200, to=to_date)
            if df is None or df.empty: break
                
        df_list.append(df)
        to_date = df.index[0] 
        time.sleep(0.2) 
        
    if not df_list: return None
    final_df = pd.concat(df_list).sort_index()
    final_df = final_df[~final_df.index.duplicated(keep='last')] 
    return final_df.tail(count) 

# --- [시뮬레이션 로직] ---
def run_simulation(ticker, df, ma_short_len, ma_long_len, use_trend_exit, use_rsi_drop, vol_factor, vol_window, rsi_threshold=30, rsi_max=50, ts_act=1.0, ts_callback=0.75, stop_loss=-2.0, trend_exit_fee=-1.0):
    balance = 0
    avg_buy_price = 0
    max_price = 0
    total_profit_rate = 1.0  
    
    trade_count, win_count, gold_count, rsi_count = 0, 0, 0, 0
    current_buy_reason = ""

    for i in range(25, len(df)): 
        curr_close = df['close'].iloc[i]
        curr_rsi = df['rsi'].iloc[i]
        prev_rsi = df['rsi'].iloc[i-1] # 💡 RSI 유턴 로직용
        
        ma_short_prev = df['ma_short'].iloc[i-1]
        ma_long_prev = df['ma_long'].iloc[i-1]
        ma_short_curr = df['ma_short'].iloc[i]
        ma_long_curr = df['ma_long'].iloc[i]
        
        vol_curr = df['volume'].iloc[i]
        vol_avg_curr = df['vol_avg'].iloc[i]

        if balance == 0:
            # 💡 실전 봇과 동일한 양봉 필터 적용
            cond_gold = (ma_short_prev < ma_long_prev and 
                         ma_short_curr > ma_long_curr and 
                         vol_curr > vol_avg_curr * vol_factor and 
                         curr_rsi < rsi_max and
                         df['close'].iloc[i] > df['open'].iloc[i])
            
            # 💡 실전 봇과 동일한 RSI 유턴(Cross-up) 돌파 로직
            cond_rsi = (prev_rsi < rsi_threshold and curr_rsi >= rsi_threshold) if use_rsi_drop else False

            if cond_gold or cond_rsi:
                balance = 1
                avg_buy_price = curr_close
                max_price = curr_close
                current_buy_reason = "gold" if cond_gold else "rsi"
                
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
            # 💡 추세 탈출(데드크로스) ON/OFF 제어
            elif use_trend_exit and (ma_short_curr < ma_long_curr and profit_rate < ts_act):
                if profit_rate < trend_exit_fee:
                    is_sell = True

            if is_sell:
                net_profit = profit_rate - 0.1 
                total_profit_rate *= (1 + net_profit / 100)
                trade_count += 1
                
                if net_profit > 0: win_count += 1
                if current_buy_reason == "gold": gold_count += 1
                elif current_buy_reason == "rsi": rsi_count += 1
                balance = 0

    win_rate = (win_count / trade_count * 100) if trade_count > 0 else 0
    final_profit = (total_profit_rate - 1) * 100

    return {
        '종목': ticker,
        'MA선': f"{ma_short_len}/{ma_long_len}",
        '추세탈출': 'O' if use_trend_exit else 'X',
        'RSI유턴': 'O' if use_rsi_drop else 'X',
        '기준봉수': vol_window,  
        '거래량배수': vol_factor,
        '총매수': trade_count,
        '승률(%)': round(win_rate, 1),
        '총수익(%)': round(final_profit, 2)
    }

if __name__ == "__main__":
    pd.set_option('display.max_rows', None)
    pd.set_option('display.width', 1000) 
    
    # =====================================================================
    # ⚙️ [백테스트 중앙 통제실] - 여기서 모든 파라미터를 레고 조립하듯 조작하세요!
    # =====================================================================
    
    # 1. 테스트할 코인 목록
    target_tickers = ["KRW-BTC", "KRW-ETH", "KRW-SOL", "KRW-XRP", "KRW-NEAR", "KRW-LINK", "KRW-XRP", "KRW-TAO"]
    
    # 2. 이평선(MA) 조합 테스트 (단기, 장기)
    # 예: 빠른선(3,15)과 무거운선(5,20)을 동시에 비교 테스트!
    ma_options = [(3, 15), (5, 20)] 
    
    # 3. 추세 탈출(데드크로스 하락 손절) 기능 ON/OFF 테스트
    use_trend_exit_options = [True, False] 
    
    # 4. RSI 유턴 매수 로직 ON/OFF 테스트
    rsi_drop_options = [True] 
    
    # 5. 거래량 배수 및 기준봉 테스트
    vol_factor_options = [1.0, 1.5]
    vol_window_options = [5, 10]
    
    # 6. 종목별 트레일링 스탑 발동 기준점 (ts_callback은 함수 기본값 0.75로 세팅됨)
    ts_act_dict = {"KRW-TAO": 1.0, "KRW-BTC":1.0, "KRW-ETH":1.5, "KRW-SOL":1.5, "KRW-XRP":1.5, "KRW-NEAR":1.5, "KRW-LINK":1.0}
    
    # =====================================================================

    print("🚀 [UBT_v7_Master] 스마트 백테스트 시작...\n")
    all_results = []
    
    for ticker in target_tickers:
        print(f"[{ticker}] 안전하게 데이터 모으는 중...", end=" ")
        df = get_safe_ohlcv(ticker, days=7)
        if df is None or len(df) == 0:
            print("❌ 실패")
            continue
        print("✅ 완료")
            
        # RSI는 변하지 않으므로 한 번만 계산
        delta = df['close'].diff()
        up, down = delta.copy(), delta.copy()
        up[up < 0], down[down > 0] = 0, 0
        _gain = up.ewm(com=13, min_periods=14).mean()
        _loss = down.abs().ewm(com=13, min_periods=14).mean()
        df['rsi'] = 100 - (100 / (1 + (_gain / _loss)))

        # 💡 옵션 조합 시작
        for ma_short, ma_long in ma_options:
            df['ma_short'] = df['close'].rolling(window=ma_short).mean()
            df['ma_long'] = df['close'].rolling(window=ma_long).mean()
            
            for use_trend_exit in use_trend_exit_options:
                for vol_win in vol_window_options:
                    df['vol_avg'] = df['volume'].rolling(window=vol_win).mean()
                    
                    for use_rsi in rsi_drop_options:
                        for v_factor in vol_factor_options:
                            result = run_simulation(
                                ticker=ticker, 
                                df=df, 
                                ma_short_len=ma_short,
                                ma_long_len=ma_long,
                                use_trend_exit=use_trend_exit,
                                use_rsi_drop=use_rsi,
                                vol_factor=v_factor,
                                vol_window=vol_win, 
                                ts_act=ts_act_dict.get(ticker, 1.0)
                            )
                            if result: all_results.append(result)

    if all_results:
        df_summary = pd.DataFrame(all_results)
        df_sorted = df_summary.sort_values(by=['종목', '총수익(%)'], ascending=[True, False])
        
        # 💡 보기 편하게 컬럼 순서 재배치 (불필요한 세부 건수 생략하고 핵심만)
        columns_order = ['종목', 'MA선', '추세탈출', 'RSI유턴', '기준봉수', '거래량배수', '총매수', '승률(%)', '총수익(%)']
        df_sorted = df_sorted[columns_order]
        
        print("\n--- 📊 전략 조합별 상세 백테스트 결과 (최근 7일) ---")
        print(df_sorted.to_string(index=False))