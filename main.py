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

# 자산 정보를 파일에 저장하는 함수
def save_daily_asset(total_eval, total_profit_rate):
    now_str = datetime.now().strftime('%Y-%m-%d')
    # 날짜, 총평가금액, 수익률 순서로 저장 (엑셀 복붙용)
    log_line = f"{now_str}, {int(total_eval)}, {total_profit_rate:+.2f}%\n"
    with open("weekly_assets.txt", "a", encoding="utf-8") as f:
        f.write(log_line)
    print(f">> {now_str} 자산 기록 완료")

# 일주일 기록을 가져오고 파일을 비우는 함수
def get_and_clear_weekly_report():
    if not os.path.exists("weekly_assets.txt"):
        return "기록된 데이터가 없습니다."
    
    with open("weekly_assets.txt", "r", encoding="utf-8") as f:
        content = f.read()
    
    # 파일 초기화 (새로운 주를 위해)
    open("weekly_assets.txt", "w").close()
    return content

print("--- 업비트 자산 관리 봇 가동 ---")
send_discord_msg("🚀 **업비트 자산 관리 봇**이 가동되었습니다. (매일 9시 기록 / 월요일 9시 통합 리포트)")

last_report_time = 0
daily_check_flag = False # 하루에 한 번만 기록하기 위한 플래그

while True:
    try:
        now = datetime.now()
        balances = upbit.get_balances()
        
        total_eval = 0      
        total_purchase = 0  
        
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
                            total_eval += (balance * current_price)
                            total_purchase += (balance * avg_buy_price)

        total_profit_rate = ((total_eval - total_purchase) / total_purchase) * 100 if total_purchase > 0 else 0

        # --- [핵심 로직: 매일 아침 9시 기록] ---
        if now.hour == 9 and now.minute == 0 and not daily_check_flag:
            # 1. 일단 오늘치 기록
            save_daily_asset(total_eval, total_profit_rate)
            
            # 2. 만약 오늘이 월요일(0)이라면 일주일치 디스코드 전송
            if now.weekday() == 0:
                weekly_data = get_and_clear_weekly_report()
                report_msg = f"📅 **[주간 자산 통합 리포트]**\n(날짜, 자산액, 수익률)\n```csv\n{weekly_data}```\n위 내용을 복사해서 엑셀에 붙여넣으세요!"
                send_discord_msg(report_msg)
            
            daily_check_flag = True # 기록 완료 표시
            
        # 9시가 지나면 플래그 초기화
        if now.hour != 9:
            daily_check_flag = False

        # --- 수정 후 (10분마다 디스코드 알림 추가) ---
        if time.time() - last_report_time > 600:
            # 터미널에도 출력
            status_msg = f"[{now.strftime('%H:%M:%S')}] 현재 자산: {int(total_eval):,}원 ({total_profit_rate:+.2f}%)"
            print(status_msg)
            
            # 디스코드 전송 추가
            discord_status = f"📊 **[실시간 알림]**\n현재 자산: `{int(total_eval):,}원`\n수익률: **{total_profit_rate:+.2f}%**"
            send_discord_msg(discord_status)
            
            last_report_time = time.time()

        time.sleep(30) # 30초마다 체크
        
    except Exception as e:
        print(f"에러 발생: {e}")
        time.sleep(10)