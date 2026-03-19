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
def run_simulation(ticker, df, ma_short_len, ma_long_len, use_pullback, use_trend_exit, use_rsi_drop, vol_factor, vol_window, rsi_threshold=30, rsi_max=50, ts_act=1.0, ts_callback=0.75, stop_loss=-2.0, trend_exit_fee=-1.0):
    balance = 0
    avg_buy_price = 0
    max_price = 0
    total_profit_rate = 1.0  
    
    trade_count, win_count, gold_count, rsi_count = 0, 0, 0, 0
    current_buy_reason = ""

    for i in range(25, len(df)): 
        curr_close = df['close'].iloc[i]
        curr_low = df['low'].iloc[i]     # 💡 저가(꼬리) 확인용
        curr_open = df['open'].iloc[i]   # 💡 시가 확인용
        curr_rsi = df['rsi'].iloc[i]
        prev_rsi = df['rsi'].iloc[i-1] 
        
        ma_short_prev = df['ma_short'].iloc[i-1]
        ma_long_prev = df['ma_long'].iloc[i-1]
        ma_short_curr = df['ma_short'].iloc[i]
        ma_long_curr = df['ma_long'].iloc[i]
        
        vol_curr = df['volume'].iloc[i]
        vol_avg_curr = df['vol_avg'].iloc[i]

        if balance == 0:
            
            # 💡 매수 타점 스위치 (눌림목 vs 돌파)
            if use_pullback:
                # [눌림목 매수] 정배열 상승 중, 가격이 단기선까지 내려왔다가 양봉으로 지지받을 때
                cond_gold = (ma_short_curr > ma_long_curr and 
                             curr_low <= ma_short_curr * 1.002 and  # 저가가 단기선 근처(+0.2% 이내)까지 눌림
                             curr_close > curr_open and             # 양봉 마감 (지지의 증거)
                             curr_rsi < rsi_max)                    # 너무 고점이 아닐 것
            else:
                # [돌파 매수] 골든크로스가 터지는 순간 (기존 방식)
                cond_gold = (ma_short_prev < ma_long_prev and 
                             ma_short_curr > ma_long_curr and 
                             vol_curr > vol_avg_curr * vol_factor and 
                             curr_rsi < rsi_max and
                             curr_close > curr_open)
            
            # RSI 유턴 돌파 로직
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
        '매수타점': '눌림목' if use_pullback else '돌파', # 💡 표기 추가
        'MA선': f"{ma_short_len}/{ma_long_len}",
        '추세탈출': 'O' if use_trend_exit else 'X',
        '거래량배수': vol_factor if not use_pullback else '-', # 눌림목은 거래량 무시하므로 대시(-) 처리
        '총매수': trade_count,
        '승률(%)': round(win_rate, 1),
        '총수익(%)': round(final_profit, 2)
    }

if __name__ == "__main__":
    pd.set_option('display.max_rows', None)
    pd.set_option('display.width', 1000) 
    
    # =====================================================================
    # ⚙️ [백테스트 중앙 통제실]
    # =====================================================================
    target_tickers = ["KRW-BTC", "KRW-ETH", "KRW-SOL", "KRW-XRP", "KRW-NEAR", "KRW-LINK", "KRW-TAO"]
    
    # 🌟 [신규] 눌림목 매수 토글버튼 (True: 눌림목, False: 기존 돌파매수)
    pullback_options = [True, False]
    
    ma_options = [(3, 15)] 
    use_trend_exit_options = [True, False] 
    rsi_drop_options = [True] 
    vol_factor_options = [1.0] # 눌림목 비교를 위해 배수는 일단 1.0으로 고정
    vol_window_options = [10]
    
    ts_act_dict = {"KRW-TAO": 1.0, "KRW-BTC":1.0, "KRW-ETH":1.5, "KRW-SOL":1.5, "KRW-XRP":1.5, "KRW-NEAR":1.5, "KRW-LINK":1.0}
    # =====================================================================

    print("🚀 [UBT_v8_Master] 눌림목 vs 돌파 백테스트 시작...\n")
    all_results = []
    
    for ticker in target_tickers:
        print(f"[{ticker}] 데이터 수집 중...", end=" ")
        df = get_safe_ohlcv(ticker, days=7)
        if df is None or len(df) == 0:
            print("❌ 실패")
            continue
        print("✅ 완료")
            
        delta = df['close'].diff()
        up, down = delta.copy(), delta.copy()
        up[up < 0], down[down > 0] = 0, 0
        _gain = up.ewm(com=13, min_periods=14).mean()
        _loss = down.abs().ewm(com=13, min_periods=14).mean()
        df['rsi'] = 100 - (100 / (1 + (_gain / _loss)))

        for use_pullback in pullback_options:
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
                                    use_pullback=use_pullback, # 💡 인자 추가
                                    use_trend_exit=use_trend_exit,
                                    use_rsi_drop=use_rsi,
                                    vol_factor=v_factor,
                                    vol_window=vol_win, 
                                    ts_act=ts_act_dict.get(ticker, 1.0)
                                )
                                if result: all_results.append(result)

    if all_results:
        df_summary = pd.DataFrame(all_results)
        df_sorted = df_summary.sort_values(by=['종목', '매수타점', '총수익(%)'], ascending=[True, False, False])
        
        columns_order = ['종목', '매수타점', 'MA선', '추세탈출', '거래량배수', '총매수', '승률(%)', '총수익(%)']
        df_sorted = df_sorted[columns_order]
        
        print("\n--- 📊 매수 타점(눌림목 vs 돌파) 비교 백테스트 결과 ---")
        print(df_sorted.to_string(index=False))