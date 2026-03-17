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

# --- [V6.3 정밀 백테스트 기반 최적화 설정 (동적 MA & 거래량 기준봉 적용)] ---
strategy_config = {
    # 🥇 MA5/20 (무거운 선) 최적화 코인
    "KRW-NEAR": {"ma_short": 5, "ma_long": 20, "vol_window": 10, "rsi_threshold": 30, "rsi_max": 50, "ts_activation": 1.5, "use_rsi_drop": True,  "vol_factor": 1.0},
    
    # 🥈 MA3/15 (빠른 선) 최적화 코인들
    "KRW-BTC":  {"ma_short": 3, "ma_long": 15, "vol_window": 5,  "rsi_threshold": 30, "rsi_max": 50, "ts_activation": 1.0, "use_rsi_drop": True,  "vol_factor": 1.0},
    "KRW-ETH":  {"ma_short": 3, "ma_long": 15, "vol_window": 5,  "rsi_threshold": 25, "rsi_max": 60, "ts_activation": 1.5, "use_rsi_drop": False, "vol_factor": 1.0},
    "KRW-LINK": {"ma_short": 3, "ma_long": 15, "vol_window": 5,  "rsi_threshold": 25, "rsi_max": 50, "ts_activation": 1.0, "use_rsi_drop": False, "vol_factor": 1.0},
    "KRW-SOL":  {"ma_short": 3, "ma_long": 15, "vol_window": 20, "rsi_threshold": 25, "rsi_max": 50, "ts_activation": 1.5, "use_rsi_drop": True,  "vol_factor": 1.0},
    "KRW-XRP":  {"ma_short": 3, "ma_long": 15, "vol_window": 10, "rsi_threshold": 25, "rsi_max": 50, "ts_activation": 1.5, "use_rsi_drop": True,  "vol_factor": 1.0}
}

target_tickers = list(strategy_config.keys())

# --- [공통 파라미터] ---
ts_callback = 0.5
stop_loss = -2.0
trend_exit_fee = -1.0
fixed_buy_amount = 250000  # 종목당 25만 원

max_price_dict = {}

# --- [로그 및 알림 함수] ---
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

print("🚀 UTD_v6_3 실전 가동 시작 (동적 다중지능 & 양봉 필터 장착)")
send_discord_msg("🤖 **UTD_v6_3** 가동 시작\n- 코인별 맞춤형 이평선(MA) 및 거래량 기준봉 적용 완료\n- 음봉 휩쏘 방지(양봉 필터) 활성화\n- 종목당 25만 원")

while True:
    try:
        now = datetime.now()
            
        for ticker in target_tickers:
            config = strategy_config[ticker]
            
            # 💡 코인마다 요구하는 최대 캔들 수가 다르므로 넉넉하게 40개 호출
            df = pyupbit.get_ohlcv(ticker, interval="minute5", count=40)
            if df is None or len(df) < 30: continue
            
            curr_price = pyupbit.get_current_price(ticker)
            
            # 💡 [핵심] 봇이 코인에 맞춰 스스로 선을 바꿉니다! (동적 MA 및 거래량 계산)
            ma_short = df['close'].rolling(window=config['ma_short']).mean()
            ma_long = df['close'].rolling(window=config['ma_long']).mean()
            vol_avg = df['volume'].rolling(window=config['vol_window']).mean()
            
            rsi_series = get_rsi(ticker)
            if rsi_series is None: continue
            curr_rsi = rsi_series.iloc[-1]
            
            balance = upbit.get_balance(ticker)
            
            # --- [매수 로직] ---
            if balance == 0:
                # 1. 맞춤형 골든크로스 + 거래량 + RSI 제한 + [양봉 필터]
                cond_gold = (ma_short.iloc[-2] < ma_long.iloc[-2] and 
                             ma_short.iloc[-1] > ma_long.iloc[-1] and 
                             df['volume'].iloc[-1] > vol_avg.iloc[-1] * config['vol_factor'] and
                             curr_rsi < config['rsi_max'] and
                             df['close'].iloc[-1] > df['open'].iloc[-1])  # 💡 양봉(종가>시가)일 때만 매수 허락!
                
                # 2. 맞춤형 단순 낙주 로직
                cond_rsi = (curr_rsi < config['rsi_threshold']) if config['use_rsi_drop'] else False

                if cond_gold or cond_rsi:
                    krw_balance = upbit.get_balance("KRW")
                    if krw_balance > fixed_buy_amount:
                        upbit.buy_market_order(ticker, fixed_buy_amount)
                        
                        # 알림 메시지 구성
                        if cond_gold:
                            reason = f"골든크로스({config['ma_short']}/{config['ma_long']}선, Vol x{config['vol_factor']})"
                        else:
                            reason = f"RSI({config['rsi_threshold']}) 낙주"
                            
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
                # 💡 맞춤형 단기선이 장기선을 깨고 내려갈 때 추세 탈출!
                elif ma_short.iloc[-1] < ma_long.iloc[-1] and profit_rate < ts_act:
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