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

# --- [V5.3 최종 전략 설정] ---
# 1. 깐깐한 그룹 (RSI 40): ADA, DOT, AVAX
# 2. 밸런스 그룹 (RSI 50): BTC, ETH, SOL, XRP, TRX
strategy_config = {
    "KRW-BTC":  {"rsi_threshold": 30, "rsi_max": 50, "ts_activation": 1.0},
    "KRW-ETH":  {"rsi_threshold": 25, "rsi_max": 50, "ts_activation": 1.5},
    "KRW-SOL":  {"rsi_threshold": 25, "rsi_max": 50, "ts_activation": 2.0},
    "KRW-XRP":  {"rsi_threshold": 25, "rsi_max": 50, "ts_activation": 2.0},
    "KRW-TRX":  {"rsi_threshold": 25, "rsi_max": 50, "ts_activation": 1.0},
    
    "KRW-ADA":  {"rsi_threshold": 25, "rsi_max": 40, "ts_activation": 1.0}, # RSI 40 상한
    "KRW-DOT":  {"rsi_threshold": 25, "rsi_max": 40, "ts_activation": 1.0}, # RSI 40 상한
    "KRW-AVAX": {"rsi_threshold": 25, "rsi_max": 40, "ts_activation": 1.0}  # RSI 40 상한
}

target_tickers = list(strategy_config.keys())

# 공통 파라미터
ts_callback = 0.5
stop_loss = -2.0
trend_exit_fee = -1.0
vol_factor = 2.5
fixed_buy_amount = 250000  # 종목당 25만 원 (최대 5개 동시 가동 가능)

max_price_dict = {}

def send_discord_msg(message):
    try:
        requests.post(webhook_url, json={"content": message})
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

print("🚀 TD_v5_3 실전 가동 시작 (RSI 40/50 필터 적용)")
send_discord_msg("🤖 **TD_v5_3** 가동 시작\n- 종목당 20만 원\n- RSI 상한 필터 적용")

while True:
    try:
        for ticker in target_tickers:
            config = strategy_config[ticker]
            
            # 데이터 수집
            df = pyupbit.get_ohlcv(ticker, interval="minute5", count=20)
            if df is None or len(df) < 15: continue
            
            curr_price = pyupbit.get_current_price(ticker)
            ma3 = df['close'].rolling(window=3).mean()
            ma10 = df['close'].rolling(window=10).mean()
            vol_avg = df['volume'].rolling(window=10).mean()
            
            rsi_series = get_rsi(ticker)
            if rsi_series is None: continue
            curr_rsi = rsi_series.iloc[-1]
            
            balance = upbit.get_balance(ticker)
            
            # --- [매수 로직] ---
            if balance == 0:
                # 필터 조건: 골든크로스 시 각 종목별 rsi_max 미만이어야 함
                cond_gold = (ma3.iloc[-2] < ma10.iloc[-2] and 
                             ma3.iloc[-1] > ma10.iloc[-1] and 
                             df['volume'].iloc[-1] > vol_avg.iloc[-1] * vol_factor and
                             curr_rsi < config['rsi_max'])
                
                # 낙주 조건: rsi_threshold는 이미 rsi_max보다 낮으므로 통과
                cond_rsi = (curr_rsi < config['rsi_threshold'])

                if cond_gold or cond_rsi:
                    krw_balance = upbit.get_balance("KRW")
                    if krw_balance > fixed_buy_amount:
                        upbit.buy_market_order(ticker, fixed_buy_amount)
                        reason = f"골든크로스(RSI < {config['rsi_max']})" if cond_gold else f"RSI({config['rsi_threshold']}) 낙주"
                        send_discord_msg(f"✅ **[{ticker}] 매수**\n사유: {reason}\n현재 RSI: {curr_rsi:.2f}")
            
            # --- [매도 로직] ---
            elif balance > 0:
                avg_buy_price = upbit.get_avg_buy_price(ticker)
                profit_rate = ((curr_price - avg_buy_price) / avg_buy_price) * 100
                ts_act = config['ts_activation']
                
                if ticker not in max_price_dict: max_price_dict[ticker] = curr_price
                max_price_dict[ticker] = max(max_price_dict[ticker], curr_price)
                drop_from_max = ((max_price_dict[ticker] - curr_price) / max_price_dict[ticker]) * 100

                is_sell, sell_reason = False, ""
                if profit_rate >= ts_act and drop_from_max >= ts_callback:
                    is_sell, sell_reason = True, f"TS 익절({ts_act}%)"
                elif profit_rate <= stop_loss:
                    is_sell, sell_reason = True, "손절(-2%)"
                elif ma3.iloc[-1] < ma10.iloc[-1] and profit_rate < ts_act:
                    if profit_rate < trend_exit_fee:
                        is_sell, sell_reason = True, "추세 하락 탈출"

                if is_sell:
                    upbit.sell_market_order(ticker, balance)
                    send_discord_msg(f"✅ **[{ticker}] {sell_reason}**\n수익률: **{profit_rate:+.2f}%**")
                    if ticker in max_price_dict: del max_price_dict[ticker]

        time.sleep(10)

    except Exception as e:
        print(f"Error: {e}")
        time.sleep(1)