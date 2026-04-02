import pyupbit
import pandas as pd
import time
from datetime import datetime  # 💡 바로 이 줄을 추가해 주세요!

def get_safe_ohlcv(ticker, interval="minute15", days=30):
    if interval == "minute15":
        candles_per_day = 96
    elif interval == "minute60":
        candles_per_day = 24
    else:
        candles_per_day = 288
        
    count = days * candles_per_day 
    df_list = []
    to_date = None
    request_count = (count // 200) + 1 
    
    for _ in range(request_count):
        df = pyupbit.get_ohlcv(ticker, interval=interval, count=200, to=to_date)
        if df is None or df.empty:
            time.sleep(1)
            df = pyupbit.get_ohlcv(ticker, interval=interval, count=200, to=to_date)
            if df is None or df.empty: break
                
        df_list.append(df)
        to_date = df.index[0] 
        time.sleep(0.2) 
        
    if not df_list: return None
    final_df = pd.concat(df_list).sort_index()
    final_df = final_df[~final_df.index.duplicated(keep='last')] 
    return final_df.tail(count) 

# --- [시뮬레이션 로직] ---
def run_simulation(ticker, interval, df, ma_short_len, ma_long_len, use_pullback, use_trend_exit, use_btc_filter, use_long_ma_filter, use_rsi_drop, vol_factor, vol_window, ts_callback, trend_exit_fee, rsi_threshold=30, rsi_max=50, ts_act=1.0, stop_loss=-2.0):
    balance = 0
    avg_buy_price = 0
    max_price = 0
    total_profit_rate = 1.0  
    
    trade_count, win_count, gold_count, rsi_count = 0, 0, 0, 0
    current_buy_reason = ""

    # 💡 120선 데이터를 확인해야 하므로 121번째 캔들부터 검사 시작 (에러 방지)
    for i in range(121, len(df)): 
        curr_close = df['close'].iloc[i]
        curr_low = df['low'].iloc[i]     
        curr_open = df['open'].iloc[i]   
        curr_rsi = df['rsi'].iloc[i]
        prev_rsi = df['rsi'].iloc[i-1] 
        
        curr_btc_is_positive = df['btc_is_positive'].iloc[i]
        
        ma_short_prev = df['ma_short'].iloc[i-1]
        ma_long_prev = df['ma_long'].iloc[i-1]
        ma_short_curr = df['ma_short'].iloc[i]
        ma_long_curr = df['ma_long'].iloc[i]
        
        # 💡 [핵심] 현재 120선(장기 이평선) 가격
        ma_120_curr = df['ma_120'].iloc[i]
        
        vol_curr = df['volume'].iloc[i]
        vol_avg_curr = df['vol_avg'].iloc[i]

        if balance == 0:
            # 🛡️ 1. 글로벌 BTC 필터
            if use_btc_filter and not curr_btc_is_positive:
                continue

            # 🛡️ 2. [장기 이평 필터] 현재가가 120선보다 아래에 있다면(장기 하락 추세) 매수 금지!
            if use_long_ma_filter and curr_close < ma_120_curr:
                continue

            if use_pullback:
                cond_gold = (ma_short_curr > ma_long_curr and 
                             curr_low <= ma_short_curr * 1.002 and  
                             curr_close > curr_open and             
                             curr_rsi < rsi_max)                    
            else:
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
        '타임프레임': '15분봉' if interval == 'minute15' else '1시간봉',
        'BTC필터': 'O' if use_btc_filter else 'X',
        '120선필터': 'O' if use_long_ma_filter else 'X', # 💡 출력 추가
        'TS콜백': ts_callback, 
        '추세인내': trend_exit_fee, 
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
    
    target_tickers = ["KRW-BTC", "KRW-ETH", "KRW-SOL", "KRW-XRP", "KRW-NEAR", "KRW-LINK", "KRW-TAO"]
    
    interval_options = ["minute15", "minute60"]
    
    # 💡 테스트 옵션들
    btc_filter_options = [True, False]
    long_ma_filter_options = [True, False] # 💡 장기 120선 필터 옵션
    ts_callback_options = [0.25, 0.5] 
    trend_exit_options = [-1.0, -1.5] 
    pullback_options = [True, False]
    ma_options = [(3, 15), (5, 20)] 
    use_trend_exit_options = [True, False] 
    
    rsi_drop_options = [True] 
    vol_factor_options = [1.0] 
    vol_window_options = [10]
    
    ts_act_dict = {"KRW-TAO": 1.0, "KRW-BTC":1.0, "KRW-ETH":1.5, "KRW-SOL":1.5, "KRW-XRP":1.5, "KRW-NEAR":1.5, "KRW-LINK":1.0}

    print("🚀 [UBT_v8_2] 멀티 타임프레임 + 장기 이평선(120선) 절대 방어막 백테스트 시작...\n")
    
    all_results = []
    
    for interval in interval_options:
        print(f"=======================================================")
        print(f"🕒 타임프레임: {interval} 데이터 수집 및 매크로 세팅 중...")
        print(f"=======================================================")
        
        btc_df = get_safe_ohlcv("KRW-BTC", interval=interval, days=30)
        btc_daily = pyupbit.get_ohlcv("KRW-BTC", interval="day", count=40)
        
        if btc_df is None or btc_daily is None:
            print(f"❌ {interval} 비트코인 데이터 로딩 실패! 건너뜁니다.")
            continue
            
        btc_daily_open_map = {d.date(): o for d, o in btc_daily['open'].items()}
        btc_df['trading_day'] = (btc_df.index - pd.Timedelta(hours=9)).date
        btc_df['btc_daily_open'] = btc_df['trading_day'].map(btc_daily_open_map)
        btc_df['btc_daily_open'] = btc_df['btc_daily_open'].ffill()
        
        btc_filter_series = btc_df['close'] >= btc_df['btc_daily_open']

        for ticker in target_tickers:
            print(f"[{ticker}] 30일치 {interval} 캔들 백테스트 중...", end=" ")
            df = get_safe_ohlcv(ticker, interval=interval, days=30)
            if df is None or len(df) == 0:
                print("❌ 실패")
                continue
            print("✅ 완료")
            
            df['btc_is_positive'] = btc_filter_series
            df['btc_is_positive'] = df['btc_is_positive'].ffill().fillna(False) 
                
            delta = df['close'].diff()
            up, down = delta.copy(), delta.copy()
            up[up < 0], down[down > 0] = 0, 0
            _gain = up.ewm(com=13, min_periods=14).mean()
            _loss = down.abs().ewm(com=13, min_periods=14).mean()
            df['rsi'] = 100 - (100 / (1 + (_gain / _loss)))
            
            # 💡 120선 장기 이평선 데이터 계산 추가
            df['ma_120'] = df['close'].rolling(window=120).mean()

            for use_long_ma in long_ma_filter_options: # 💡 120선 필터 루프 추가
                for use_btc in btc_filter_options: 
                    for ts_cb in ts_callback_options: 
                        for use_pullback in pullback_options:
                            for ma_short, ma_long in ma_options:
                                df['ma_short'] = df['close'].rolling(window=ma_short).mean()
                                df['ma_long'] = df['close'].rolling(window=ma_long).mean()
                                
                                for use_trend_exit in use_trend_exit_options:
                                    for t_exit in trend_exit_options:
                                        
                                        if not use_trend_exit and t_exit != -1.0:
                                            continue

                                        for vol_win in vol_window_options:
                                            df['vol_avg'] = df['volume'].rolling(window=vol_win).mean()
                                            
                                            for use_rsi in rsi_drop_options:
                                                for v_factor in vol_factor_options:
                                                    result = run_simulation(
                                                        ticker=ticker, 
                                                        interval=interval,
                                                        df=df, 
                                                        ma_short_len=ma_short,
                                                        ma_long_len=ma_long,
                                                        use_pullback=use_pullback, 
                                                        use_trend_exit=use_trend_exit,
                                                        use_btc_filter=use_btc, 
                                                        use_long_ma_filter=use_long_ma, # 💡 장기 필터 전달
                                                        use_rsi_drop=use_rsi,
                                                        vol_factor=v_factor,
                                                        vol_window=vol_win, 
                                                        ts_callback=ts_cb, 
                                                        trend_exit_fee=t_exit,
                                                        ts_act=ts_act_dict.get(ticker, 1.0)
                                                    )
                                                    if result: all_results.append(result)

if all_results:
        df_summary = pd.DataFrame(all_results)
        
        df_sorted = df_summary.sort_values(by=['종목', '총수익(%)'], ascending=[True, False])
        
        # 💡 컬럼 순서
        columns_order = ['종목', '타임프레임', 'BTC필터', '120선필터', 'TS콜백', '추세인내', '매수타점', 'MA선', '추세탈출', '총매수', '승률(%)', '총수익(%)']
        df_sorted = df_sorted[columns_order]
        
        # 💡 출력할 텍스트를 변수에 담기
        result_text = "--- 📊 멀티 타임프레임 & 120선 절대 방어막 종합 랭킹 (최근 30일) ---\n"
        result_text += df_sorted.to_string(index=False)
        
        # 1. 화면에 출력
        print("\n" + result_text)
        
        # 2. 텍스트 파일로 저장 (utf-8 인코딩으로 한글 깨짐 방지)
        file_name = f"backtest_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(result_text)
            
        print(f"\n💾 랭킹 결과가 [{file_name}] 파일로 안전하게 저장되었습니다!")