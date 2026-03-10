import pyupbit
import time
import os
import requests
import json
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

load_dotenv()

access = os.getenv("UPBIT_ACCESS_KEY")
secret = os.getenv("UPBIT_SECRET_KEY")
webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

# API 연결 및 시간대 설정
upbit = pyupbit.Upbit(access, secret)
KST = timezone(timedelta(hours=9))

# --- [파일 및 기준가 설정] ---
WEEKLY_BASE_FILE = "weekly_base_asset.txt"
TRADE_LOG_FILE = "trade_log.csv"

def save_weekly_base(amount):
    with open(WEEKLY_BASE_FILE, "w", encoding="utf-8") as f:
        f.write(str(amount))

def load_weekly_base():
    if os.path.exists(WEEKLY_BASE_FILE):
        with open(WEEKLY_BASE_FILE, "r", encoding="utf-8") as f:
            return float(f.read())
    return None

def send_discord_msg(message):
    """디스코드 웹훅으로 메시지 전송"""
    try:
        requests.post(webhook_url, json={"content": message})
        print(f"[{datetime.now(KST).strftime('%H:%M:%S')}] 디스코드 전송 성공")
    except Exception as e:
        print(f"디스코드 전송 에러: {e}")

def save_daily_asset(total_eval, weekly_profit_rate):
    now_str = datetime.now(KST).strftime('%Y-%m-%d')
    log_line = f"{now_str}, 자산: {int(total_eval):,}원, 수익률: {weekly_profit_rate:+.2f}%\n"
    with open("weekly_assets_log.txt", "a", encoding="utf-8") as f:
        f.write(log_line)

def get_and_clear_weekly_report():
    if not os.path.exists("weekly_assets_log.txt"): return "데이터 없음"
    with open("weekly_assets_log.txt", "r", encoding="utf-8") as f:
        content = f.read()
    open("weekly_assets_log.txt", "w").close()
    return content

def get_weekly_trade_summary():
    """trade_log.csv를 읽어 종목별 확정 수익 합산"""
    if not os.path.exists(TRADE_LOG_FILE) or os.stat(TRADE_LOG_FILE).st_size == 0:
        return "이번 주 확정 수익(매도 완료) 내역이 없습니다."
    
    summary = {}
    total_realized = 0
    with open(TRADE_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(',')
            if len(parts) < 3: continue
            ticker, profit = parts[1], int(parts[2])
            summary[ticker] = summary.get(ticker, 0) + profit
            total_realized += profit
            
    report = "🪙 **[주간 종목별 확정 수익 내역]**\n"
    sorted_summary = sorted(summary.items(), key=lambda x: x[1], reverse=True)
    for ticker, amount in sorted_summary:
        emoji = "✅" if amount >= 0 else "❌"
        report += f"{emoji} **{ticker}**: `{amount:+,}원` 확정\n"
    report += f"\n💰 **주간 매도 수익 합계**: `{total_realized:+,}원`"
    
    # 분석 후 로그 비우기
    open(TRADE_LOG_FILE, "w").close()
    return report

print("--- 업비트 주간 성적 추적 봇 V4.0 가동 ---")
send_discord_msg("🚀 **성적 추적 봇 V4.0** 가동 시작 (KST/에러 수정 반영)")

last_sent_hm = "" 
daily_check_flag = False
weekly_base_asset = load_weekly_base()

while True:
    try:
        # 매 루프마다 한국 시간 및 마켓 리스트 갱신
        now = datetime.now(KST)
        current_hm = now.strftime("%H:%M")
        krw_markets = pyupbit.get_tickers(fiat="KRW")
        
        balances = upbit.get_balances()
        if balances is None:
            time.sleep(10)
            continue

        total_eval = 0      
        individual_details = "" 
        
        # 1. 현재 자산 및 개별 평가 수익률 계산
        for b in balances:
            ticker = b['currency']
            balance = float(b['balance'])
            avg_buy_price = float(b['avg_buy_price'])
            
            if balance > 0:
                if ticker == 'KRW':
                    total_eval += balance
                else:
                    target_market = f"KRW-{ticker}"
                    # 마켓에 존재하는 코인인 경우에만 조회 (에러 방지 핵심)
                    if target_market in krw_markets:
                        current_price = pyupbit.get_current_price(target_market)
                        if current_price:
                            eval_val = balance * current_price
                            total_eval += eval_val
                            p_rate = ((current_price - avg_buy_price) / avg_buy_price) * 100 if avg_buy_price > 0 else 0
                            emoji = "📈" if p_rate >= 0 else "📉"
                            individual_details += f"> {emoji} **{ticker}**: {p_rate:+.2f}% (`{int(eval_val):,}`원)\n"

        if weekly_base_asset is None:
            weekly_base_asset = total_eval
            save_weekly_base(weekly_base_asset)
        
        weekly_profit_rate = ((total_eval - weekly_base_asset) / weekly_base_asset) * 100
        weekly_diff = total_eval - weekly_base_asset

        # --- [로직 1: 정각/30분 정기 알림] ---
        # 테스트를 위해 분 조건을 [0, 30] 외에 추가할 수 있습니다.
        if now.minute in [0, 30] and current_hm != last_sent_hm:
            status = f"""📊 **[실시간 자산 리포트 - {current_hm}]**
{individual_details}
💰 **현재 총 자산**: `{int(total_eval):,}원`
📅 **주간 성적**: `{int(weekly_diff):+,}원` (**{weekly_profit_rate:+.2f}%**)
*(기준: 이번주 월요일 09:00)*"""
            send_discord_msg(status)
            last_sent_hm = current_hm

        # --- [로직 2: 매일 아침 9시 기록 및 월요일 최종 결산] ---
        if now.hour == 9 and now.minute == 0 and not daily_check_flag:
            if now.weekday() == 0:
                trade_summary = get_weekly_trade_summary()
                daily_log = get_and_clear_weekly_report()
                
                final_msg = f"""📅 **[지난주 투자 성적 최종 결산]**

{trade_summary}

📝 **일별 자산 흐름:**
```csv
{daily_log}```

📈 **전체 자산 변동**: `{int(weekly_diff):+,}원` ({weekly_profit_rate:+.2f}%)
💰 **최종 총 자산**: `{int(total_eval):,}원`"""
                send_discord_msg(final_msg)
                
                # 기준가 갱신 및 저장
                weekly_base_asset = total_eval
                save_weekly_base(weekly_base_asset)
                send_discord_msg(f"🚩 **이번 주 기준가가 갱신되었습니다.**\n시작 자산: `{int(weekly_base_asset):,}원` 시작")

            save_daily_asset(total_eval, weekly_profit_rate)
            daily_check_flag = True
            
        if now.hour != 9:
            daily_check_flag = False

        time.sleep(20) # 20초마다 체크
        
    except Exception as e:
        print(f"에러 발생: {e}")
        time.sleep(10)