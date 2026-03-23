import pyupbit
import time
import os
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# --- [계정 및 보안 설정] ---
access = os.getenv("UPBIT_ACCESS_KEY")
secret = os.getenv("UPBIT_SECRET_KEY")
webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

upbit = pyupbit.Upbit(access, secret)

# =====================================================================
# 💎 [V7.4 최종 완성 파라미터] - BTC 매크로 필터 탑재
# =====================================================================
strategy_config = {
    # ⚡ [0.25 짧게 치고 빠지기 그룹]
    "KRW-TAO":  {"ma_short": 3, "ma_long": 15, "use_pullback": False, "use_trend_exit": True,  "ts_activation": 1.0, "ts_callback": 0.25, "vol_window": 10, "rsi_threshold": 30, "rsi_max": 50, "use_rsi_drop": True, "vol_factor": 1.0, "use_btc_filter": False}, # 💡 펌핑 코인: BTC 필터 OFF
    "KRW-SOL":  {"ma_short": 3, "ma_long": 15, "use_pullback": False, "use_trend_exit": True,  "ts_activation": 1.5, "ts_callback": 0.25, "vol_window": 10, "rsi_threshold": 30, "rsi_max": 50, "use_rsi_drop": True, "vol_factor": 1.0, "use_btc_filter": True},  # 🛡️ BTC 필터 ON
    "KRW-ETH":  {"ma_short": 3, "ma_long": 15, "use_pullback": False, "use_trend_exit": True,  "ts_activation": 1.5, "ts_callback": 0.25, "vol_window": 10, "rsi_threshold": 30, "rsi_max": 60, "use_rsi_drop": True, "vol_factor": 1.0, "use_btc_filter": True},  # 🛡️ BTC 필터 ON
    "KRW-XRP":  {"ma_short": 3, "ma_long": 15, "use_pullback": True,  "use_trend_exit": True,  "ts_activation": 1.5, "ts_callback": 0.25, "vol_window": 10, "rsi_threshold": 30, "rsi_max": 50, "use_rsi_drop": True, "vol_factor": 1.0, "use_btc_filter": False}, # 💡 독자 무빙: BTC 필터 OFF
    "KRW-BTC":  {"ma_short": 3, "ma_long": 15, "use_pullback": True,  "use_trend_exit": False, "ts_activation": 1.0, "ts_callback": 0.25, "vol_window": 10, "rsi_threshold": 30, "rsi_max": 50, "use_rsi_drop": True, "vol_factor": 1.0, "use_btc_filter": True},  # 🛡️ BTC 본인도 필터 ON

    # 🌊 [0.50 중간 여유 그룹]
    "KRW-NEAR": {"ma_short": 5, "ma_long": 20, "use_pullback": False, "use_trend_exit": False, "ts_activation": 1.5, "ts_callback": 0.50, "vol_window": 10, "rsi_threshold": 30, "rsi_max": 50, "use_rsi_drop": True, "vol_factor": 1.0, "use_btc_filter": True},  # 🛡️ BTC 필터 ON
    "KRW-LINK": {"ma_short": 5, "ma_long": 20, "use_pullback": True,  "use_trend_exit": True,  "ts_activation": 1.0, "ts_callback": 0.50, "vol_window": 10, "rsi_threshold": 30, "rsi_max": 50, "use_rsi_drop": True, "vol_factor": 1.0, "use_btc_filter": True}   # 🛡️ BTC 필터 ON
}

target_tickers = list(strategy_config.keys())

# --- [공통 파라미터] ---
stop_loss = -2.0
trend_exit_fee = -1.0
fixed_buy_amount = 230000  

max_price_dict = {}

# --- [로그 및 알림 함수] ---
def log_trade(ticker, profit_amount, profit_rate, reason):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"{now},{ticker},{int(profit_amount)},{profit_rate:.2f}%,{reason}\n"
    with open("trade_log.csv", "a", encoding="utf-8") as f:
        f.write(log_line)

def send_discord_msg(message):
    try: requests.post(webhook_url, json={"content": message})
    except: pass

def get_rsi(ticker):
    df = pyupbit.get_ohlcv(ticker, interval="minute5", count=200)
    if df is None: return None
    delta = df['close'].diff()
    up, down = delta.copy(), delta.copy()
    up[up < 0], down[down > 0] = 0, 0
    _gain = up.ewm(com=13, min_periods=14).mean()
    _loss = down.abs().ewm(com=13, min_periods=14).mean()
    return 100 - (100 / (1 + (_gain / _loss)))

print("🚀 UTD_v7_4 실전 가동 시작 (글로벌 BTC 매크로 필터 탑재)")
send_discord_msg("🤖 **UTD_v7_4** 가동 시작\n- 🛡️ 대장주(BTC) 시가 기준 매크로 필터 작동 중\n- TAO/XRP는 필터 예외(야수의 심장 모드)")

while True:
    try:
        now = datetime.now()
        
        # =====================================================================
        # 🌍 [글로벌 BTC 필터] 실시간 비트코인 일봉(9시 시가 대비) 양봉/음봉 판별
        # =====================================================================
        btc_daily = pyupbit.get_ohlcv("KRW-BTC", interval="day", count=1)
        if btc_daily is not None and not btc_daily.empty:
            btc_today_open = btc_daily['open'].iloc[-1]
            btc_curr_price = pyupbit.get_current_price("KRW-BTC")
            btc_is_positive = btc_curr_price >= btc_today_open
        else:
            btc_is_positive = True # 데이터 수신 에러 시 보수적으로 통과 처리
            
        for ticker in target_tickers:
            config = strategy_config[ticker]
            
            df = pyupbit.get_ohlcv(ticker, interval="minute5", count=40)
            if df is None or len(df) < 30: continue
            
            curr_price = pyupbit.get_current_price(ticker)
            
            ma_short = df['close'].rolling(window=config['ma_short']).mean()
            ma_long = df['close'].rolling(window=config['ma_long']).mean()
            vol_avg = df['volume'].rolling(window=config['vol_window']).mean()
            
            rsi_series = get_rsi(ticker)
            if rsi_series is None or len(rsi_series) < 2: continue
            
            prev_rsi = rsi_series.iloc[-2]
            curr_rsi = rsi_series.iloc[-1]
            
            balance = upbit.get_balance(ticker)
            
            # --- [매수 로직] ---
            if balance == 0:
                # 🛡️ [핵심 방어막] 비트코인 필터 적용 대상인데, BTC가 9시 시가보다 낮다면 즉시 패스!
                if config['use_btc_filter'] and not btc_is_positive:
                    continue

                curr_low = df['low'].iloc[-1]
                curr_open = df['open'].iloc[-1]
                curr_close = df['close'].iloc[-1]

                if config['use_pullback']:
                    cond_gold = (ma_short.iloc[-1] > ma_long.iloc[-1] and 
                                 curr_low <= ma_short.iloc[-1] * 1.002 and  
                                 curr_close > curr_open and             
                                 curr_rsi < config['rsi_max'])
                else:
                    cond_gold = (ma_short.iloc[-2] < ma_long.iloc[-2] and 
                                 ma_short.iloc[-1] > ma_long.iloc[-1] and 
                                 df['volume'].iloc[-1] > vol_avg.iloc[-1] * config['vol_factor'] and
                                 curr_rsi < config['rsi_max'] and
                                 curr_close > curr_open)

                cond_rsi = (prev_rsi < config['rsi_threshold'] and curr_rsi >= config['rsi_threshold']) if config['use_rsi_drop'] else False

                if cond_gold or cond_rsi:
                    krw_balance = upbit.get_balance("KRW")
                    if krw_balance > fixed_buy_amount:
                        upbit.buy_market_order(ticker, fixed_buy_amount)
                        
                        if cond_gold:
                            trade_type = "눌림목" if config['use_pullback'] else f"돌파(Vol x{config['vol_factor']})"
                            reason = f"{trade_type} 진입({config['ma_short']}/{config['ma_long']}선)"
                        else:
                            reason = f"RSI 유턴 돌파(현재 {curr_rsi:.1f}▲)"
                            
                        send_discord_msg(f"✅ **[{ticker}] 매수**\n사유: {reason}")

            # --- [매도 로직] ---
            elif balance > 0:
                avg_buy_price = upbit.get_avg_buy_price(ticker)
                if avg_buy_price == 0: continue
                    
                curr_price = pyupbit.get_current_price(ticker)
                
                profit_rate = ((curr_price - avg_buy_price) / avg_buy_price) * 100
                ts_act = config['ts_activation']
                ts_cb = config['ts_callback'] 
                
                if ticker not in max_price_dict: max_price_dict[ticker] = curr_price
                max_price_dict[ticker] = max(max_price_dict[ticker], curr_price)
                
                drop_from_max = ((max_price_dict[ticker] - curr_price) / max_price_dict[ticker]) * 100
                max_profit_rate = ((max_price_dict[ticker] - avg_buy_price) / avg_buy_price) * 100

                is_sell, sell_reason = False, ""
                
                if max_profit_rate >= ts_act and drop_from_max >= ts_cb:
                    is_sell, sell_reason = True, f"TS 익절(최고 {max_profit_rate:.2f}% 도달 후 {ts_cb}% 하락)🔺"
                elif profit_rate <= stop_loss:
                    is_sell, sell_reason = True, "손절(-2%)🔻"
                elif config['use_trend_exit'] and (ma_short.iloc[-1] < ma_long.iloc[-1]) and (profit_rate < ts_act):
                    if profit_rate < trend_exit_fee:
                        is_sell, sell_reason = True, f"추세 하락 탈출({config['ma_short']}/{config['ma_long']} 데드크로스)🔻"

                if is_sell:
                    profit_amount = (curr_price - avg_buy_price) * balance - (curr_price * balance * 0.001)
                    upbit.sell_market_order(ticker, balance)
                    log_trade(ticker, profit_amount, profit_rate, sell_reason)
                    send_discord_msg(f" **[{ticker}] {sell_reason}**\n수익: `{int(profit_amount):+,}원` ({profit_rate:+.2f}%)")
                    if ticker in max_price_dict: del max_price_dict[ticker]

        time.sleep(10)

    except Exception as e:
        print(f"Error: {e}")
        time.sleep(1)