import pyupbit
import time
import os
import requests
import datetime
from dotenv import load_dotenv

load_dotenv()
upbit = pyupbit.Upbit(os.getenv("UPBIT_ACCESS_KEY"), os.getenv("UPBIT_SECRET_KEY"))
webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

# --- [V4 FULL 설정: 24시간 전방위 공략] ---
target_tickers = ["KRW-BTC", "KRW-ETH", "KRW-SOL", "KRW-ETC", "KRW-XRP"]
buy_amount = 240000       
ts_activation = 2.0      
ts_callback = 0.5        
stop_loss = -2.0         
vol_factor = 2.5         
rsi_oversold = 30        

max_price_dict = {}

def send_discord_msg(message):
    try: requests.post(webhook_url, json={"content": message})
    except: pass

def get_rsi(ticker):
    try:
        df = pyupbit.get_ohlcv(ticker, interval="minute5", count=30)
        delta = df['close'].diff()
        up, down = delta.copy(), delta.copy()
        up[up < 0], down[down > 0] = 0, 0
        _gain = up.ewm(com=13, min_periods=14).mean()
        _loss = down.abs().ewm(com=13, min_periods=14).mean()
        RS = _gain / _loss
        return 100 - (100 / (1 + RS.iloc[-1]))
    except: return 50 # 에러 시 중립값 반환

print(f"🚀 [V4 FULL] 24시간 무중단 공격 모드 가동 시작")

while True:
    for ticker in target_tickers:
        try:
            df = pyupbit.get_ohlcv(ticker, interval="minute5", count=30)
            if df is None or len(df) < 20: continue

            # 지표 계산
            ma3 = df['close'].rolling(window=3).mean()
            ma10 = df['close'].rolling(window=10).mean()
            vol_avg = df['volume'].rolling(window=10).mean().iloc[-2]
            curr_vol = df['volume'].iloc[-1]
            rsi = get_rsi(ticker)
            
            balance = upbit.get_balance(ticker)
            current_price = pyupbit.get_current_price(ticker)

            if balance > 0:
                # [보유 상태] 수익 극대화 및 리스크 관리
                avg_buy_price = upbit.get_avg_buy_price(ticker)
                current_price = pyupbit.get_current_price(ticker)
                profit_rate = ((current_price - avg_buy_price) / avg_buy_price) * 100
                
                # 최고가 갱신 및 트레일링 스톱 계산
                if ticker not in max_price_dict: max_price_dict[ticker] = current_price
                max_price_dict[ticker] = max(max_price_dict[ticker], current_price)
                drop_from_max = ((max_price_dict[ticker] - current_price) / max_price_dict[ticker]) * 100

                is_sell = False
                
                # 1. 트레일링 스톱 (익절)
                if profit_rate >= ts_activation and drop_from_max >= ts_callback:
                    reason = "트레일링스톱 익절"
                    is_sell = True
                
                # 2. 고정 손절 (-2.0%)
                elif profit_rate <= stop_loss:
                    reason = "고정 손절"
                    is_sell = True
                
                # 3. 데드크로스 탈출 (백테스트 로직 유지 + 무한매매 방어막)
                elif ma3.iloc[-1] < ma10.iloc[-1] and profit_rate < ts_activation:
                    # [방어막] 손실이 -0.5%보다 커졌을 때만 '데드크로스 탈출'을 허용합니다.
                    # 이렇게 하면 수수료만 떼이는 0.00% 매도를 방지할 수 있습니다.
                    if profit_rate < -0.5:
                        reason = "추세 꺾임 탈출(손절)"
                        is_sell = True

                if is_sell:
                    upbit.sell_market_order(ticker, balance)
                    send_discord_msg(f"💰 **[{ticker}] {reason}**\n수익률: {profit_rate:.2f}%")
                    if ticker in max_price_dict: del max_price_dict[ticker]

            else:
                # [미보유 상태] 24시간 상시 매수 감시
                # 1. 급등 포착 (3-10 골든크로스 + 거래량 2.5배)
                cond_gold = (ma3.iloc[-2] < ma10.iloc[-2] and ma3.iloc[-1] > ma10.iloc[-1] and curr_vol > vol_avg * vol_factor)
                # 2. 과매도 포착 (RSI 30 이하)
                cond_rsi = (rsi < rsi_oversold)

                if cond_gold or cond_rsi:
                    if upbit.get_balance("KRW") > buy_amount:
                        upbit.buy_market_order(ticker, buy_amount)
                        max_price_dict[ticker] = pyupbit.get_current_price(ticker)
                        msg = "🔥 골든크로스" if cond_gold else "💎 낙주 줍기"
                        send_discord_msg(f"🚀 **[{ticker}] 매수 진입**\n이유: {msg}\nRSI: {rsi:.1f}\n현재가: {current_price:,.0f}")

            time.sleep(0.5)
        except Exception as e:
            print(f"오류 발생: {e}")
            time.sleep(1)
    
    time.sleep(1)