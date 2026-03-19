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
# 🛡️ [V7.1 절대 방어 파라미터 세팅] - 백테스트 1위 데이터 100% 반영
# =====================================================================
strategy_config = {
    # 📉 [눌림목 매수 그룹] - 돌파할 때 쫓아가지 않고, 지지선에서 안전하게 줍는다.
    "KRW-BTC":  {"ma_short": 3, "ma_long": 15, "vol_window": 10, "rsi_threshold": 30, "rsi_max": 50, "ts_activation": 1.0, "use_rsi_drop": True, "vol_factor": 1.0, "use_trend_exit": False, "use_pullback": True},
    "KRW-LINK": {"ma_short": 5, "ma_long": 20, "vol_window": 10, "rsi_threshold": 30, "rsi_max": 50, "ts_activation": 1.0, "use_rsi_drop": True, "vol_factor": 1.0, "use_trend_exit": True,  "use_pullback": True},
    "KRW-XRP":  {"ma_short": 5, "ma_long": 20, "vol_window": 10, "rsi_threshold": 30, "rsi_max": 50, "ts_activation": 1.5, "use_rsi_drop": True, "vol_factor": 1.0, "use_trend_exit": False, "use_pullback": True},

    # 🚀 [돌파 매수 그룹] - 힘이 붙을 때 시원하게 올라탄다 (눌림목 기다리면 기회 놓침)
    "KRW-TAO":  {"ma_short": 3, "ma_long": 15, "vol_window": 10, "rsi_threshold": 30, "rsi_max": 50, "ts_activation": 1.0, "use_rsi_drop": True, "vol_factor": 1.0, "use_trend_exit": True,  "use_pullback": False},
    "KRW-SOL":  {"ma_short": 3, "ma_long": 15, "vol_window": 10, "rsi_threshold": 30, "rsi_max": 50, "ts_activation": 1.5, "use_rsi_drop": True, "vol_factor": 1.0, "use_trend_exit": True,  "use_pullback": False},
    "KRW-NEAR": {"ma_short": 5, "ma_long": 20, "vol_window": 10, "rsi_threshold": 30, "rsi_max": 50, "ts_activation": 1.5, "use_rsi_drop": True, "vol_factor": 1.0, "use_trend_exit": False, "use_pullback": False},
    "KRW-ETH":  {"ma_short": 3, "ma_long": 15, "vol_window": 10, "rsi_threshold": 30, "rsi_max": 60, "ts_activation": 1.5, "use_rsi_drop": True, "vol_factor": 1.0, "use_trend_exit": False, "use_pullback": False}
}

target_tickers = list(strategy_config.keys())

# --- [공통 파라미터] ---
ts_callback = 0.75
stop_loss = -2.0
trend_exit_fee = -1.0
fixed_buy_amount = 250000  # 종목당 25만 원

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

print("🚀 UTH_v7_1 실전 가동 시작 (하이브리드 절대 방어 시스템)")
send_discord_msg("🤖 **UTH_v7_1** 가동 시작\n- 방어막 전개 완료: 코인별 눌림목/돌파 하이브리드 매수\n- 무거운 이평선 방어 및 추세탈출 최적화 완료")

while True:
    try:
        now = datetime.now()
            
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
            
            # --- [매수 로직: 하이브리드 타점 적용] ---
            if balance == 0:
                curr_low = df['low'].iloc[-1]
                curr_open = df['open'].iloc[-1]
                curr_close = df['close'].iloc[-1]

                if config['use_pullback']:
                    # 📉 [눌림목 매수] 정배열 상승 중, 가격이 단기선 근처로 눌렸다가 양봉 지지 확인 시
                    cond_gold = (ma_short.iloc[-1] > ma_long.iloc[-1] and 
                                 curr_low <= ma_short.iloc[-1] * 1.002 and  
                                 curr_close > curr_open and             
                                 curr_rsi < config['rsi_max'])
                else:
                    # 🚀 [돌파 매수] 거래량이 터지며 골든크로스가 일어나는 순간
                    cond_gold = (ma_short.iloc[-2] < ma_long.iloc[-2] and 
                                 ma_short.iloc[-1] > ma_long.iloc[-1] and 
                                 df['volume'].iloc[-1] > vol_avg.iloc[-1] * config['vol_factor'] and
                                 curr_rsi < config['rsi_max'] and
                                 curr_close > curr_open)

                # RSI 유턴 돌파 로직
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

            # --- [매도 로직: 추세 탈출(ON/OFF) 최적화] ---
            elif balance > 0:
                avg_buy_price = upbit.get_avg_buy_price(ticker)
                
                if avg_buy_price == 0: continue
                    
                curr_price = pyupbit.get_current_price(ticker)
                
                profit_rate = ((curr_price - avg_buy_price) / avg_buy_price) * 100
                ts_act = config['ts_activation']
                
                if ticker not in max_price_dict: max_price_dict[ticker] = curr_price
                max_price_dict[ticker] = max(max_price_dict[ticker], curr_price)
                
                drop_from_max = ((max_price_dict[ticker] - curr_price) / max_price_dict[ticker]) * 100
                max_profit_rate = ((max_price_dict[ticker] - avg_buy_price) / avg_buy_price) * 100

                is_sell, sell_reason = False, ""
                
                if max_profit_rate >= ts_act and drop_from_max >= ts_callback:
                    is_sell, sell_reason = True, f"TS 익절(최고 {max_profit_rate:.2f}% 도달 후 하락)🔺"
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