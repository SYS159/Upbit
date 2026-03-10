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

def send_discord_msg(message):
    try:
        data = {"content": message}
        requests.post(webhook_url, json=data)
    except Exception as e:
        print(f"디스코드 전송 에러: {e}")

def save_daily_asset(total_eval, total_profit_rate):
    now_str = datetime.now().strftime('%Y-%m-%d')
    log_line = f"{now_str}, {int(total_eval)}, {total_profit_rate:+.2f}%\n"
    with open("weekly_assets.txt", "a", encoding="utf-8") as f:
        f.write(log_line)
    print(f">> {now_str} 자산 기록 완료")

def get_and_clear_weekly_report():
    if not os.path.exists("weekly_assets.txt"):
        return "기록된 데이터가 없습니다."
    with open("weekly_assets.txt", "r", encoding="utf-8") as f:
        content = f.read()
    open("weekly_assets.txt", "w").close()
    return content

print("--- 업비트 자산 관리 봇 가동 ---")
send_discord_msg("🚀 **업비트 자산 관리 봇**이 가동되었습니다.\n(10분마다 알림 / 매일 9시 기록 / 월요일 9시 통합 리포트)")

last_report_time = 0
daily_check_flag = False

while True:
    try:
        now = datetime.now()
        balances = upbit.get_balances()
        
        total_eval = 0      
        total_purchase = 0  
        individual_details = "" # 10분 알림에 상세 정보를 넣고 싶다면 사용
        
        for b in balances:
            ticker = b['currency']
            balance = float(b['balance'])
            avg_buy_price = float(b['avg_buy_price'])
            
            if balance > 0:
                if ticker == 'KRW':
                    total_eval += balance
                    total_purchase += balance
                else:
                    target_ticker = f"KRW-{ticker}"
                    if target_ticker in krw_markets:
                        current_price = pyupbit.get_current_price(target_ticker)
                        if current_price:
                            eval_val = balance * current_price
                            total_eval += eval_val
                            total_purchase += (balance * avg_buy_price)
                            
                            # (선택) 개별 코인 수익률 정보를 메시지에 포함
                            p_rate = ((current_price - avg_buy_price) / avg_buy_price) * 100 if avg_buy_price > 0 else 0
                            emoji = "📈" if p_rate >= 0 else "📉"
                            individual_details += f"> {emoji} **{ticker}**: {p_rate:+.2f}% (`{int(eval_val):,}`원)\n"

        total_profit_rate = ((total_eval - total_purchase) / total_purchase) * 100 if total_purchase > 0 else 0

        # --- [로직 1: 10분마다 실시간 알림] ---
        if time.time() - last_report_time > 600:
            discord_status = f"📊 **[실시간 자산 리포트]**\n{individual_details}\n💰 **총 평가금액**: `{int(total_eval):,}원`\n📊 **전체 수익률**: **{total_profit_rate:+.2f}%**"
            send_discord_msg(discord_status)
            print(f"[{now.strftime('%H:%M:%S')}] 디스코드 전송 완료 (수익률: {total_profit_rate:+.2f}%)")
            last_report_time = time.time()

        # --- [로직 2: 매일 아침 9시 기록 및 월요일 통합 리포트] ---
        if now.hour == 9 and now.minute == 0 and not daily_check_flag:
            save_daily_asset(total_eval, total_profit_rate)
            if now.weekday() == 0:
                weekly_data = get_and_clear_weekly_report()
                report_msg = f"📅 **[주간 자산 통합 리포트]**\n```csv\n{weekly_data}```\n엑셀에 붙여넣으세요!"
                send_discord_msg(report_msg)
            daily_check_flag = True
            
        if now.hour != 9:
            daily_check_flag = False

        time.sleep(30) # 30초마다 체크
        
    except Exception as e:
        print(f"에러 발생: {e}")
        time.sleep(10)