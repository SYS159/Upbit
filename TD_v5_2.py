import pyupbit
import time
import os
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# --- [설정 로드] ---
access = os.getenv("UPBIT_ACCESS_KEY")
secret = os.getenv("UPBIT_SECRET_KEY")
webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

upbit = pyupbit.Upbit(access, secret)

# --- [V5.2 최종 세팅: 백테스트 수익 검증 완료된 8종목] ---
strategy_config = {
    "KRW-BTC": {"rsi_threshold": 30, "ts_activation": 1.0},
    "KRW-ETH": {"rsi_threshold": 25, "ts_activation": 1.5},
    "KRW-SOL": {"rsi_threshold": 25, "ts_activation": 2.0},
    "KRW-XRP": {"rsi_threshold": 25, "ts_activation": 2.0},
    "KRW-ADA": {"rsi_threshold": 25, "ts_activation": 1.0},
    "KRW-AVAX": {"rsi_threshold": 25, "ts_activation": 1.0},
    "KRW-DOT": {"rsi_threshold": 25, "ts_activation": 1.0},
    "KRW-TRX": {"rsi_threshold": 25, "ts_activation": 1.0}
}

target_tickers = list(strategy_config.keys())

# 공통 파라미터
ts_callback = 0.5      # 고점 대비 하락 시 매도
stop_loss = -2.0       # 고정 손절선
trend_exit_fee = -1.0  # 추세 꺾임 탈출 기준
vol_factor = 2.5       # 거래량 가중치
fixed_buy_amount = 200000  # 종목당 매수 금액

max_price_dict = {}    # 트레일링 스톱용 최고가 저장

def send_discord_msg(message):
    try:
        data = {"content": message}
        requests.post(webhook_url, json=data)
    except Exception as e:
        print(f"디스코드 전송 에러: {e}")

def get_rsi(ticker, interval="minute5", count=200):
    df = pyupbit.get_ohlcv(ticker, interval=interval, count=count)
    if df is None: return None
    delta = df['close'].diff()
    up, down = delta.copy(), delta.copy()
    up[up < 0], down[down > 0] = 0, 0
    _gain = up.ewm(com=13, min_periods=14).mean()
    _loss = down.abs().ewm(com=13, min_periods=14).mean()
    RS = _gain / _loss
    return 100 - (100 / (1 + RS))

print("--- TD_v5_2 실전 매매 봇 가동 ---")
send_discord_msg("🚀 **TD_v5_2** 가동 시작 (수익 검증 8종목 정예 모델)")

while True:
    try:
        for ticker in target_tickers:
            # 1. 지표 데이터 로드
            df = pyupbit.get_ohlcv(ticker, interval="minute5", count=20)
            if df is None or len(df) < 15: continue
            
            curr_price = pyupbit.get_current_price(ticker)
            ma3 = df['close'].rolling(window=3).mean()
            ma10 = df['close'].rolling(window=10).mean()
            vol_avg = df['volume'].rolling(window=10).mean()
            
            rsi_series = get_rsi(ticker)
            if rsi_series is None: continue
            curr_rsi = rsi_series.iloc[-1]
            
            # 2. 잔고 조회
            balance = upbit.get_balance(ticker)
            
            # --- [매수 로직] ---
            if balance == 0:
                config = strategy_config[ticker]
                rsi_limit = config['rsi_threshold']
                
                cond_gold = (ma3.iloc[-2] < ma10.iloc[-2] and ma3.iloc[-1] > ma10.iloc[-1] and df['volume'].iloc[-1] > vol_avg.iloc[-1] * vol_factor)
                cond_rsi = (curr_rsi < rsi_limit)

                if cond_gold or cond_rsi:
                    krw_balance = upbit.get_balance("KRW")
                    if krw_balance > fixed_buy_amount:
                        upbit.buy_market_order(ticker, fixed_buy_amount)
                        reason = "골든크로스" if cond_gold else f"RSI({rsi_limit}) 낙주"
                        send_discord_msg(f"✅ **[{ticker}] 매수**\n사유: {reason}")
                    else:
                        print(f"⚠️ {ticker} 잔고 부족")

            # --- [매도 로직] ---
            elif balance > 0:
                avg_buy_price = upbit.get_avg_buy_price(ticker)
                profit_rate = ((curr_price - avg_buy_price) / avg_buy_price) * 100
                ts_act = strategy_config[ticker]['ts_activation']
                
                # 최고가 관리
                if ticker not in max_price_dict: max_price_dict[ticker] = curr_price
                max_price_dict[ticker] = max(max_price_dict[ticker], curr_price)
                drop_from_max = ((max_price_dict[ticker] - curr_price) / max_price_dict[ticker]) * 100

                is_sell = False
                sell_reason = ""

                # 1. 커스텀 트레일링 스톱 (1.0%~2.0% 차등 적용)
                if profit_rate >= ts_act and drop_from_max >= ts_callback:
                    is_sell, sell_reason = True, f"TS 익절({ts_act}%)"
                # 2. 고정 손절 (-2.0%)
                elif profit_rate <= stop_loss:
                    is_sell, sell_reason = True, "손절(-2%)"
                # 3. 데드크로스 탈출 (익절 목표 도달 전 추세 꺾임)
                elif ma3.iloc[-1] < ma10.iloc[-1] and profit_rate < ts_act:
                    if profit_rate < trend_exit_fee:
                        is_sell, sell_reason = True, "추세 하락 탈출"

                if is_sell:
                    upbit.sell_market_order(ticker, balance)
                    send_discord_msg(f"💰 **[{ticker}] {sell_reason}**\n수익률: **{profit_rate:+.2f}%**")
                    if ticker in max_price_dict: del max_price_dict[ticker]

        time.sleep(10) # 10초마다 종목 순회

    except Exception as e:
        print(f"에러: {e}")
        time.sleep(1)