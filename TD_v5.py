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

# --- [V5 핵심 설정: 코인별 맞춤 RSI] ---
# 백테스트 결과가 좋았던 종목과 수치로 구성 (ETC 제외)
strategy_config = {
    "KRW-BTC": {"rsi_threshold": 30},
    "KRW-ETH": {"rsi_threshold": 25},
    "KRW-SOL": {"rsi_threshold": 25},
    "KRW-XRP": {"rsi_threshold": 25}
}

target_tickers = list(strategy_config.keys())

# 공통 파라미터
ts_activation = 2.0    # 트레일링 스톱 활성화 (2%)
ts_callback = 0.5      # 고점 대비 하락 시 매도 (0.5%)
stop_loss = -2.0       # 강제 손절선 (-2%)
trend_exit_fee = -1.0  # 무한매매 방지 문턱 (-1%)
vol_factor = 2.5       # 거래량 필터

max_price_dict = {}    # 트레일링 스톱용 최고가 저장

def send_discord_msg(message):
    try:
        data = {"content": message}
        requests.post(webhook_url, json=data)
    except Exception as e:
        print(f"디스코드 전송 에러: {e}")

def get_rsi(ticker, interval="minute5", count=200):
    df = pyupbit.get_ohlcv(ticker, interval=interval, count=count)
    delta = df['close'].diff()
    up, down = delta.copy(), delta.copy()
    up[up < 0], down[down > 0] = 0, 0
    _gain = up.ewm(com=13, min_periods=14).mean()
    _loss = down.abs().ewm(com=13, min_periods=14).mean()
    RS = _gain / _loss
    return 100 - (100 / (1 + RS))

print("--- 업비트 자동매매 V5(Expert Custom) 가동 ---")
send_discord_msg("🚀 **Trading V5** 가동 시작\n대상: BTC, ETH, SOL, XRP (맞춤형 RSI 적용)")

while True:
    try:
        for ticker in target_tickers:
            # 1. 차트 데이터 및 지표 계산
            df = pyupbit.get_ohlcv(ticker, interval="minute5", count=20)
            if df is None: continue
            
            curr_price = pyupbit.get_current_price(ticker)
            ma3 = df['close'].rolling(window=3).mean()
            ma10 = df['close'].rolling(window=10).mean()
            vol_avg = df['volume'].rolling(window=10).mean()
            curr_rsi = get_rsi(ticker).iloc[-1]
            
            # 2. 잔고 확인
            balance = upbit.get_balance(ticker)
            
            # --- [매수 로직] ---
            if balance == 0:
                rsi_limit = strategy_config[ticker]['rsi_threshold']
                
                # 매수 조건 판단
                cond_gold = (ma3.iloc[-2] < ma10.iloc[-2] and ma3.iloc[-1] > ma10.iloc[-1] and df['volume'].iloc[-1] > vol_avg.iloc[-1] * vol_factor)
                cond_rsi = (curr_rsi < rsi_limit)

                if cond_gold or cond_rsi:
                    krw_balance = upbit.get_balance("KRW")
                    
                    # [수정 포인트] 여기에 원하는 고정 금액을 입력하세요 (예: 300,000)
                    fixed_buy_amount = 300,000 
                    
                    # 잔고가 고정 금액보다 많을 때만 실행
                    if krw_balance > fixed_buy_amount:
                        upbit.buy_market_order(ticker, fixed_buy_amount)
                        reason = "골든크로스" if cond_gold else f"RSI({rsi_limit}) 낙주"
                        send_discord_msg(f"✅ **[{ticker}] 매수 진입**\n이유: {reason}\n매수금액: {fixed_buy_amount:,}원")
                    else:
                        print(f"⚠️ 잔고 부족으로 {ticker} 매수 실패 (잔고: {krw_balance:,.0f}원)")
            
            # --- [매도 로직] ---
            elif balance > 0:
                avg_buy_price = upbit.get_avg_buy_price(ticker)
                profit_rate = ((curr_price - avg_buy_price) / avg_buy_price) * 100
                
                # 최고가 갱신 (TS용)
                if ticker not in max_price_dict: max_price_dict[ticker] = curr_price
                max_price_dict[ticker] = max(max_price_dict[ticker], curr_price)
                drop_from_max = ((max_price_dict[ticker] - curr_price) / max_price_dict[ticker]) * 100

                is_sell = False
                sell_reason = ""

                # 1. 트레일링 스톱 (수익 보존)
                if profit_rate >= ts_activation and drop_from_max >= ts_callback:
                    is_sell, sell_reason = True, "트레일링스톱 익절"
                # 2. 고정 손절 (-2%)
                elif profit_rate <= stop_loss:
                    is_sell, sell_reason = True, "고정 손절"
                # 3. 데드크로스 탈출 (무한매매 방지 문턱 -1%)
                elif ma3.iloc[-1] < ma10.iloc[-1] and profit_rate < ts_activation:
                    if profit_rate < trend_exit_fee:
                        is_sell, sell_reason = True, "추세 꺾임 탈출"

                if is_sell:
                    upbit.sell_market_order(ticker, balance)
                    send_discord_msg(f"💰 **[{ticker}] {sell_reason}**\n수익률: {profit_rate:.2f}%")
                    if ticker in max_price_dict: del max_price_dict[ticker]

        time.sleep(10) # 10초마다 반복

    except Exception as e:
        print(f"에러 발생: {e}")
        time.sleep(1)