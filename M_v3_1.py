import pyupbit
import time
import os
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

access = os.getenv("UPBIT_ACCESS_KEY")
secret = os.getenv("UPBIT_SECRET_KEY")
webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

upbit = pyupbit.Upbit(access, secret)
krw_markets = pyupbit.get_tickers(fiat="KRW")

# --- [기능 1: 주간 기준가 관리] ---
WEEKLY_BASE_FILE = "weekly_base_asset.txt"

def save_weekly_base(amount):
    with open(WEEKLY_BASE_FILE, "w", encoding="utf-8") as f:
        f.write(str(amount))

def load_weekly_base():
    if os.path.exists(WEEKLY_BASE_FILE):
        with open(WEEKLY_BASE_FILE, "r", encoding="utf-8") as f:
            return float(f.read())
    return None

def send_discord_msg(message):
    try:
        data = {"content": message}
        requests.post(webhook_url, json=data)
    except Exception as e:
        print(f"디스코드 전송 에러: {e}")

def save_daily_asset(total_eval, weekly_profit_rate):
    now_str = datetime.now().strftime('%Y-%m-%d')
    log_line = f"{now_str}, 자산: {int(total_eval):,}원, 주간수익률: {weekly_profit_rate:+.2f}%\n"
    with open("weekly_assets_log.txt", "a", encoding="utf-8") as f:
        f.write(log_line)
    print(f">> {now_str} 자산 기록 완료")

def get_and_clear_weekly_report():
    if not os.path.exists("weekly_assets_log.txt"):
        return "기록된 데이터가 없습니다."
    with open("weekly_assets_log.txt", "r", encoding="utf-8") as f:
        content = f.read()
    open("weekly_assets_log.txt", "w").close()
    return content

print("--- 업비트 주간 성적 추적 봇 V3.1 가동 ---")
send_discord_msg("🚀 **주간 성적 추적 봇 V3.1** 가동\n(매주 월요일 9시 리셋 / 정각 기준 30분 단위 알림)")

# 상태 관리 변수
last_report_min = -1  # 15분 알림 중복 방지용
daily_check_flag = False
weekly_base_asset = load_weekly_base()

while True:
    try:
        now = datetime.now()
        balances = upbit.get_balances()
        
        total_eval = 0      
        individual_details = "" 
        
        # 1. 현재 모든 잔고 및 개별 수익률 계산 (기존 기능 그대로)
        for b in balances:
            ticker = b['currency']
            balance = float(b['balance'])
            avg_buy_price = float(b['avg_buy_price'])
            
            if balance > 0:
                if ticker == 'KRW':
                    total_eval += balance
                else:
                    target_ticker = f"KRW-{ticker}"
                    if target_ticker in krw_markets:
                        current_price = pyupbit.get_current_price(target_ticker)
                        if current_price:
                            eval_val = balance * current_price
                            total_eval += eval_val
                            p_rate = ((current_price - avg_buy_price) / avg_buy_price) * 100 if avg_buy_price > 0 else 0
                            emoji = "📈" if p_rate >= 0 else "📉"
                            individual_details += f"> {emoji} **{ticker}**: {p_rate:+.2f}% (`{int(eval_val):,}`원)\n"

        # 2. 주간 기준가 설정 및 수익률 계산 (기존 기능 그대로)
        if weekly_base_asset is None:
            weekly_base_asset = total_eval
            save_weekly_base(weekly_base_asset)
        
        weekly_profit_rate = ((total_eval - weekly_base_asset) / weekly_base_asset) * 100
        weekly_diff = total_eval - weekly_base_asset

        # --- [로직 1: 정각 기준 15분마다 알림 전송] ---
        # 00분, 15분, 30분, 45분일 때만 실행
        if now.minute in [0, 30] and now.minute != last_report_min:
            status = (
                f"📊 **[주간 성적 리포트]**\n"
                f"{individual_details}\n"
                f"💰 **현재 총 자산**: `{int(total_eval):,}원`\n"
                f"📅 **이번 주 성적**: `{int(weekly_diff):+,}원` (**{weekly_profit_rate:+.2f}%**)\n"
                f"*(기준: 지난 월요일 09:00)*"
            )
            send_discord_msg(status)
            last_report_min = now.minute # 중복 전송 방지
            print(f"[{now.strftime('%H:%M:%S')}] 15분 정기 알림 전송 완료")

        # --- [로직 2: 매일 아침 9시 기록 및 월요일 리셋 (기존 기능 그대로)] ---
        if now.hour == 9 and now.minute == 0 and not daily_check_flag:
            # 월요일 9시: 주간 리포트 결산 및 기준가 갱신
            if now.weekday() == 0:
                weekly_data = get_and_clear_weekly_report()
                report_msg = f"📅 **[지난주 최종 통합 리포트]**\n```csv\n{weekly_data}```"
                send_discord_msg(report_msg)
                
                weekly_base_asset = total_eval
                save_weekly_base(weekly_base_asset)
                send_discord_msg(f"🚩 **이번 주 기준가가 갱신되었습니다.**\n시작 자산: `{int(weekly_base_asset):,}원`")
            
            # 매일 아침: 일일 자산 로그 저장
            save_daily_asset(total_eval, weekly_profit_rate)
            daily_check_flag = True
            
        if now.hour != 9:
            daily_check_flag = False

        time.sleep(20) # 20초 간격으로 체크
        
    except Exception as e:
        print(f"에러 발생: {e}")
        time.sleep(10)