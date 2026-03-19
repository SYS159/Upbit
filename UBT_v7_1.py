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
        curr_low = df['low'].iloc[i]     
        curr_open = df['open'].iloc[i]   
        curr_rsi = df['rsi'].iloc[i]
        prev_rsi = df['rsi'].iloc[i-1] 
        
        ma_short_prev = df['ma_short'].iloc[i-1]
        ma_long_prev = df['ma_long'].iloc[i-1]
        ma_short_curr = df['ma_short'].iloc[i]
        ma_long_curr = df['ma_long'].iloc[i]
        
        vol_curr = df['volume'].iloc[i]
        vol_avg_curr = df['vol_avg'].iloc[i]

        if balance == 0:
            if use_pullback:
                # [눌림목 매수]
                cond_gold = (ma_short_curr > ma_long_curr and 
                             curr_low <= ma_short_curr * 1.002 and  
                             curr_close > curr_open and             
                             curr_rsi < rsi_max)                    
            else:
                # [돌파 매수]
                cond_gold = (ma_short_prev < ma_long_prev and 
                             ma_short_curr > ma_long_curr and 
                             vol_curr > vol_avg_curr * vol_factor and 
                             curr_rsi < rsi_max and
                             curr_close > curr_open)
            
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
        '매수타점': '눌림목' if use_pullback else '돌파',
        'MA선': f"{ma_short_len}/{ma_long_len}",
        '추세탈출': 'O' if use_trend_exit else 'X',
        '총매수': trade_count,
        '승률(%)': round(win_rate, 1),
        '총수익(%)': round(final_profit, 2)
    }

if __name__ == "__main__":
    pd.set_option('display.max_rows', None)
    pd.set_option('display.width', 1000) 
    
    # =====================================================================
    # ⚙️ [백테스트 중앙 통제실] - 3대장 변수 총동원
    # =====================================================================
    target_tickers = ["KRW-BTC", "KRW-ETH", "KRW-SOL", "KRW-XRP", "KRW-NEAR", "KRW-LINK", "KRW-TAO"]
    
    # 1. 매수 타점 2가지 (눌림목 vs 돌파)
    pullback_options = [True, False]
    
    # 2. 이평선 2가지 (빠른선 3/15 vs 무거운선 5/20)
    ma_options = [(3, 15), (5, 20)] 
    
    # 3. 추세 탈출(손절) 2가지 (ON vs OFF)
    use_trend_exit_options = [True, False] 
    
    # 고정 변수 (결과를 직관적으로 비교하기 위해 거래량 등은 1가지로 고정)
    rsi_drop_options = [True] 
    vol_factor_options = [1.0] 
    vol_window_options = [10]
    
    ts_act_dict = {"KRW-TAO": 1.0, "KRW-BTC":1.0, "KRW-ETH":1.5, "KRW-SOL":1.5, "KRW-XRP":1.5, "KRW-NEAR":1.5, "KRW-LINK":1.0}
    # =====================================================================

    print("🚀 [UBT_v7_Ultimate] 모든 전략의 교차 검증을 시작합니다...\n")
    all_results = []
    
    for ticker in target_tickers:
        print(f"[{ticker}] 7일치 캔들 다운로드 중...", end=" ")
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
                                    use_pullback=use_pullback, 
                                    use_trend_exit=use_trend_exit,
                                    use_rsi_drop=use_rsi,
                                    vol_factor=v_factor,
                                    vol_window=vol_win, 
                                    ts_act=ts_act_dict.get(ticker, 1.0)
                                )
                                if result: all_results.append(result)

    if all_results:
        df_summary = pd.DataFrame(all_results)
        
        # 💡 [정렬 마법] 1차: 종목별(가나다순) -> 2차: 수익률 높은 순으로 줄세우기
        df_sorted = df_summary.sort_values(by=['종목', '총수익(%)'], ascending=[True, False])
        
        columns_order = ['종목', '매수타점', 'MA선', '추세탈출', '총매수', '승률(%)', '총수익(%)']
        df_sorted = df_sorted[columns_order]
        
        print("\n--- 📊 전략 조합별 랭킹 결과 (종목별 수익률 1등~8등) ---")
        print(df_sorted.to_string(index=False))