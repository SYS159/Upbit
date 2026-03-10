import pyupbit
import time
import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
upbit = pyupbit.Upbit(os.getenv("UPBIT_ACCESS_KEY"), os.getenv("UPBIT_SECRET_KEY"))
webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

# --- [V3 설정: 백테스트 최적화 값] ---
# 백테스트 수익률이 좋았던 종목 위주로 구성 (DOGE, ADA 등 마이너스 종목 제외 추천)
target_tickers = ["KRW-BTC", "KRW-ETH", "KRW-SOL"] 
buy_amount = 10000       # 소액 테스트 권장
take_profit = 2.0        # 백테스트에서 사용한 2% 익절
stop_loss = -1.5         # 고정 손절선
vol_factor = 2.5         # 거래량 2.5배 필터 (가짜 신호 차단 핵심)

def send_discord_msg(message):
    try: requests.post(webhook_url, json={"content": message})
    except: pass

def is_market_good():
    """비트코인 5일 이평선 필터 (하락장 매수 금지)"""
    try:
        btc_df = pyupbit.get_ohlcv("KRW-BTC", interval="day", count=5)
        return pyupbit.get_current_price("KRW-BTC") > btc_df['close'].mean()
    except: return True

print(f"🕵️ [V3 가동] BTC/ETH/SOL 집중 공략 모드")

while True:
    market_status = is_market_good()
    for ticker in target_tickers:
        try:
            # 5분봉 데이터 30개 로드
            df = pyupbit.get_ohlcv(ticker, interval="minute5", count=30)
            if df is None or len(df) < 20: continue

            # 백테스트와 동일한 3분/10분 이평선 계산
            ma3 = df['close'].rolling(window=3).mean()
            ma10 = df['close'].rolling(window=10).mean()
            vol_avg = df['volume'].rolling(window=10).mean().iloc[-2]
            curr_vol = df['volume'].iloc[-1]

            balance = upbit.get_balance(ticker)
            current_price = pyupbit.get_current_price(ticker)

            if balance > 0:
                # [보유 중] 익절/손절/데드크로스 감시
                avg_buy_price = upbit.get_avg_buy_price(ticker)
                profit_rate = ((current_price - avg_buy_price) / avg_buy_price) * 100
                
                # 매도 조건 (익절 2% / 손절 -1.5% / 3-10 데드크로스)
                if profit_rate >= take_profit or profit_rate <= stop_loss or ma3.iloc[-1] < ma10.iloc[-1]:
                    upbit.sell_market_order(ticker, balance)
                    type_str = "익절" if profit_rate >= take_profit else ("손절" if profit_rate <= stop_loss else "데드")
                    send_discord_msg(f"✅ **[{ticker}] {type_str} 매도**\n수익률: {profit_rate:.2f}%")
            
            else:
                # [미보유] 매수 조건 (비트필터 + 3-10 골든크로스 + 거래량 2.5배)
                if market_status:
                    if ma3.iloc[-2] < ma10.iloc[-2] and ma3.iloc[-1] > ma10.iloc[-1]:
                        if curr_vol > vol_avg * vol_factor:
                            if upbit.get_balance("KRW") > buy_amount:
                                upbit.buy_market_order(ticker, buy_amount)
                                send_discord_msg(f"🔥 **[{ticker}] V3 매수 포착!**\n이유: 3-10 골든크로스 + 거래량 폭발")

            time.sleep(0.5) # API 호출 안정화
        except Exception as e:
            print(f"에러: {e}"); time.sleep(1)
    
    time.sleep(1)