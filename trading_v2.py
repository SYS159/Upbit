import pyupbit
import time
import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
upbit = pyupbit.Upbit(os.getenv("UPBIT_ACCESS_KEY"), os.getenv("UPBIT_SECRET_KEY"))
webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

# --- 설정 ---
target_tickers = ["KRW-BTC", "KRW-ETH", "KRW-SOL", "KRW-XRP", "KRW-DOGE", "KRW-ADA", "KRW-TRX", "KRW-ETC", "KRW-LINK", "KRW-SAND"]
buy_amount = 10000
stop_loss = -1.5          
ts_activation = 2.0       
ts_callback = 0.5         
max_price_dict = {}

def send_discord_msg(message):
    try: requests.post(webhook_url, json={"content": message})
    except: pass

def get_rsi(df, period=14):
    delta = df['close'].diff()
    up, down = delta.copy(), delta.copy()
    up[up < 0] = 0
    down[down > 0] = 0
    _gain = up.ewm(com=(period - 1), min_periods=period).mean()
    _loss = down.abs().ewm(com=(period - 1), min_periods=period).mean()
    RS = _gain / _loss
    return 100 - (100 / (1 + RS))

def is_market_good():
    """비트코인이 5일 이평선 위에 있는지 확인 (상승장 판별)"""
    try:
        btc_df = pyupbit.get_ohlcv("KRW-BTC", interval="day", count=5)
        btc_ma5 = btc_df['close'].mean()
        btc_curr = pyupbit.get_current_price("KRW-BTC")
        return btc_curr > btc_ma5
    except: return True

print(f"🚀 [PRO v2] 시장 필터 탑재 전략 가동")

while True:
    market_status = is_market_good()
    for ticker in target_tickers:
        try:
            df = pyupbit.get_ohlcv(ticker, interval="minute5", count=50)
            if df is None or len(df) < 30: continue

            ma5 = df['close'].rolling(window=5).mean()
            ma20 = df['close'].rolling(window=20).mean()
            rsi = get_rsi(df).iloc[-1]
            avg_volume = df['volume'].rolling(window=10).mean().iloc[-2]
            curr_volume = df['volume'].iloc[-1]

            balance = upbit.get_balance(ticker)
            current_price = pyupbit.get_current_price(ticker)

            if balance > 0:
                avg_buy_price = upbit.get_avg_buy_price(ticker)
                profit_rate = ((current_price - avg_buy_price) / avg_buy_price) * 100
                
                if ticker not in max_price_dict: max_price_dict[ticker] = current_price
                max_price_dict[ticker] = max(max_price_dict[ticker], current_price)
                drop_from_max = ((max_price_dict[ticker] - current_price) / max_price_dict[ticker]) * 100

                # 매도 로직 (TS 익절 / 손절 / 데드크로스)
                if profit_rate >= ts_activation and drop_from_max >= ts_callback:
                    upbit.sell_market_order(ticker, balance)
                    send_discord_msg(f"💰 [TS 익절] {ticker} | 수익: {profit_rate:.2f}%")
                    del max_price_dict[ticker]
                elif profit_rate <= stop_loss:
                    upbit.sell_market_order(ticker, balance)
                    send_discord_msg(f"🚨 [손절] {ticker} | 손실: {profit_rate:.2f}%")
                    if ticker in max_price_dict: del max_price_dict[ticker]
                elif ma5.iloc[-1] < ma20.iloc[-1]:
                    upbit.sell_market_order(ticker, balance)
                    send_discord_msg(f"📉 [데드크로스 탈출] {ticker} | 수익률: {profit_rate:.2f}%")
                    if ticker in max_price_dict: del max_price_dict[ticker]

            else:
                # 매수 로직 (비트코인 필터 추가)
                if market_status: 
                    if ma5.iloc[-2] < ma20.iloc[-2] and ma5.iloc[-1] > ma20.iloc[-1]:
                        if curr_volume > avg_volume * 1.5 and rsi < 70:
                            if upbit.get_balance("KRW") > buy_amount:
                                upbit.buy_market_order(ticker, buy_amount)
                                max_price_dict[ticker] = current_price
                                send_discord_msg(f"🔥 [PRO 매수] {ticker} (RSI: {rsi:.1f})")

            time.sleep(0.5)
        except Exception as e:
            print(f"Error: {e}"); time.sleep(1)
    time.sleep(1)