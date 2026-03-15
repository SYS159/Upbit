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

# --- [V6.1 백테스트 기반 맞춤형 전략 설정] ---
# 각 코인별로 낙주(use_rsi_drop)와 거래량 배수(vol_factor)를 다르게 적용
strategy_config = {
"KRW-BTC": {"rsi_threshold": 30, "rsi_max": 50, "ts_activation": 1.0, "use_rsi_drop": True, "vol_factor": 1.0},
"KRW-ETH": {"rsi_threshold": 25, "rsi_max": 50, "ts_activation": 1.5, "use_rsi_drop": True, "vol_factor": 1.0},
"KRW-SOL": {"rsi_threshold": 25, "rsi_max": 50, "ts_activation": 1.5, "use_rsi_drop": True, "vol_factor": 1.5},
"KRW-XRP": {"rsi_threshold": 25, "rsi_max": 50, "ts_activation": 1.5, "use_rsi_drop": True, "vol_factor": 1.5},
"KRW-ADA": {"rsi_threshold": 25, "rsi_max": 40, "ts_activation": 1.0, "use_rsi_drop": False, "vol_factor": 2.0},
"KRW-DOT": {"rsi_threshold": 25, "rsi_max": 40, "ts_activation": 1.0, "use_rsi_drop": False, "vol_factor": 1.0},
"KRW-AVAX": {"rsi_threshold": 25, "rsi_max": 40, "ts_activation": 1.0, "use_rsi_drop": True, "vol_factor": 1.5},
"KRW-DOGE": {"rsi_threshold": 25, "rsi_max": 50, "ts_activation": 1.5, "use_rsi_drop": False, "vol_factor": 2.0},
"KRW-LINK": {"rsi_threshold": 25, "rsi_max": 40, "ts_activation": 1.0, "use_rsi_drop": False, "vol_factor": 2.0},
"KRW-NEAR": {"rsi_threshold": 25, "rsi_max": 50, "ts_activation": 1.5, "use_rsi_drop": False, "vol_factor": 1.5}
# "KRW-SHIB": {"rsi_threshold": 25, "rsi_max": 50, "ts_activation": 1.5, "use_rsi_drop": False, "vol_factor": 1.0}
}

target_tickers = list(strategy_config.keys())

# 공통 파라미터 (vol_factor는 개별 설정으로 이동됨)
ts_callback = 0.5
stop_loss = -2.0
trend_exit_fee = -1.0
fixed_buy_amount = 250000  # 종목당 25만 원

max_price_dict = {}

# --- [추가 기능: 로그 기록 함수] ---
def log_trade(ticker, profit_amount, profit_rate, reason):
    """매도 시 수익 현황을 파일에 기록"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"{now},{ticker},{int(profit_amount)},{profit_rate:.2f}%,{reason}\n"
    with open("trade_log.csv", "a", encoding="utf-8") as f:
        f.write(log_line)

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


print("🚀 UTD_v6_1 실전 가동 시작 (백테스트 맞춤형 전략)")
send_discord_msg("🤖 **UTD_v6_1** 가동 시작\n- 코인별 개별 파라미터(낙주/거래량) 적용 완료\n- 종목당 25만 원\n- 로그 기록 활성화 (trade_log.csv)")

while True:
    try:
        now = datetime.now()
        # print(f"[{now.strftime('%H:%M:%S')}] 차트 스캔 중...", end='\r') # 필요시 주석 해제하여 스캔 상태 확인
            
        for ticker in target_tickers:
            config = strategy_config[ticker]
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
                # 1. 골든크로스 조건 (코인별 vol_factor 적용)
                cond_gold = (ma3.iloc[-2] < ma10.iloc[-2] and 
                             ma3.iloc[-1] > ma10.iloc[-1] and 
                             df['volume'].iloc[-1] > vol_avg.iloc[-1] * config['vol_factor'] and
                             curr_rsi < config['rsi_max'])
                
                # 2. RSI 낙주 조건 (코인별 use_rsi_drop 적용)
                cond_rsi = (curr_rsi < config['rsi_threshold']) if config['use_rsi_drop'] else False

                if cond_gold or cond_rsi:
                    krw_balance = upbit.get_balance("KRW")
                    if krw_balance > fixed_buy_amount:
                        upbit.buy_market_order(ticker, fixed_buy_amount)
                        reason = f"골든크로스(Vol x{config['vol_factor']})" if cond_gold else f"RSI({config['rsi_threshold']}) 낙주"
                        send_discord_msg(f"✅ **[{ticker}] 매수**\n사유: {reason}\n현재 RSI: {curr_rsi:.2f}")

            # --- [매도 로직] ---
            elif balance > 0:
                avg_buy_price = upbit.get_avg_buy_price(ticker)
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
                elif ma3.iloc[-1] < ma10.iloc[-1] and profit_rate < ts_act:
                    if profit_rate < trend_exit_fee:
                        is_sell, sell_reason = True, "추세 하락 탈출🔻"

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