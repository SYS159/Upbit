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

# --- [V6.4 정밀 백테스트 기반 최적화 설정 (TAO 추가 및 동적 파라미터)] ---
strategy_config = {
    # 🥇 MA5/20 (무거운 선) 최적화 코인
    "KRW-NEAR": {"ma_short": 5, "ma_long": 20, "vol_window": 10, "rsi_threshold": 30, "rsi_max": 50, "ts_activation": 1.5, "use_rsi_drop": True,  "vol_factor": 1.0},
    
    # 🥈 MA3/15 (빠른 선) 최적화 코인들
    "KRW-BTC":  {"ma_short": 3, "ma_long": 15, "vol_window": 5,  "rsi_threshold": 30, "rsi_max": 50, "ts_activation": 1.0, "use_rsi_drop": True,  "vol_factor": 1.0},
    "KRW-ETH":  {"ma_short": 3, "ma_long": 15, "vol_window": 5,  "rsi_threshold": 25, "rsi_max": 60, "ts_activation": 1.5, "use_rsi_drop": False, "vol_factor": 1.0},
    "KRW-LINK": {"ma_short": 3, "ma_long": 15, "vol_window": 5,  "rsi_threshold": 25, "rsi_max": 50, "ts_activation": 1.0, "use_rsi_drop": False, "vol_factor": 1.0},
    "KRW-SOL":  {"ma_short": 3, "ma_long": 15, "vol_window": 20, "rsi_threshold": 25, "rsi_max": 50, "ts_activation": 1.5, "use_rsi_drop": True,  "vol_factor": 1.0},
    "KRW-XRP":  {"ma_short": 3, "ma_long": 15, "vol_window": 10, "rsi_threshold": 25, "rsi_max": 50, "ts_activation": 1.5, "use_rsi_drop": True,  "vol_factor": 1.0},
    
    # 🌟 [신규 추가] 히든 에이스 TAO (트레일링 스탑 1.0% 짧게 끊어먹기)
    "KRW-TAO":  {"ma_short": 3, "ma_long": 15, "vol_window": 10, "rsi_threshold": 30, "rsi_max": 50, "ts_activation": 1.0, "use_rsi_drop": True,  "vol_factor": 1.0}
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

print("🚀 UTH_v6_4 실전 가동 시작 (RSI 유턴 돌파 & TAO 추가)")
send_discord_msg("🤖 **UTH_v6_4** 가동 시작\n- 폭락장 방어: RSI 유턴(Cross-up) 로직 적용\n- 신규 코인 TAO 추가 완료\n- 종목당 25만 원")

while True:
    try:
        now = datetime.now()
            
        for ticker in target_tickers:
            config = strategy_config[ticker]
            
            df = pyupbit.get_ohlcv(ticker, interval="minute5", count=40)
            if df is None or len(df) < 30: continue
            
            curr_price = pyupbit.get_current_price(ticker)
            
            # 동적 이평선 및 거래량 계산
            ma_short = df['close'].rolling(window=config['ma_short']).mean()
            ma_long = df['close'].rolling(window=config['ma_long']).mean()
            vol_avg = df['volume'].rolling(window=config['vol_window']).mean()
            
            rsi_series = get_rsi(ticker)
            if rsi_series is None or len(rsi_series) < 2: continue
            
            # 💡 [핵심] 직전 캔들과 현재 캔들의 RSI를 비교하기 위해 두 개를 가져옵니다.
            prev_rsi = rsi_series.iloc[-2]
            curr_rsi = rsi_series.iloc[-1]
            
            balance = upbit.get_balance(ticker)
            
            # --- [매수 로직] ---
            if balance == 0:
                # 1. 맞춤형 골든크로스 + 거래량 + RSI 제한 + [양봉 필터]
                cond_gold = (ma_short.iloc[-2] < ma_long.iloc[-2] and 
                             ma_short.iloc[-1] > ma_long.iloc[-1] and 
                             df['volume'].iloc[-1] > vol_avg.iloc[-1] * config['vol_factor'] and
                             curr_rsi < config['rsi_max'] and
                             df['close'].iloc[-1] > df['open'].iloc[-1])
                
                # 2. 💡 [핵심 업데이트] RSI 유턴(Cross-up) 돌파 로직
                # 직전 5분에는 기준선 아래 지하실에 있었으나, 현재 5분에는 기준선을 뚫고 올라왔을 때(찐반등) 매수
                cond_rsi = (prev_rsi < config['rsi_threshold'] and curr_rsi >= config['rsi_threshold']) if config['use_rsi_drop'] else False

                if cond_gold or cond_rsi:
                    krw_balance = upbit.get_balance("KRW")
                    if krw_balance > fixed_buy_amount:
                        upbit.buy_market_order(ticker, fixed_buy_amount)
                        
                        if cond_gold:
                            reason = f"골든크로스({config['ma_short']}/{config['ma_long']}선, Vol x{config['vol_factor']})"
                        else:
                            reason = f"RSI 유턴 돌파(현재 {curr_rsi:.1f}▲)"
                            
                        send_discord_msg(f"✅ **[{ticker}] 매수**\n사유: {reason}")

            # --- [매도 로직] ---
            elif balance > 0:
                avg_buy_price = upbit.get_avg_buy_price(ticker)
                
                # 💡 [안전 장치] 에어드랍이나 직접 입금 등으로 평단가가 0원인 코인은 계산식 오류(ZeroDivision) 방지를 위해 건너뜁니다.
                if avg_buy_price == 0:
                    continue
                    
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