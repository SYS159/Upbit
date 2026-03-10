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
krw_markets = pyupbit.get_tickers(fiat="KRW")

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
    try:
        requests.post(webhook_url, json={"content": message})
    except: pass

def save_daily_asset(total_eval, weekly_profit_rate):
    now_str = datetime.now().strftime('%Y-%m-%d')
    log_line = f"{now_str}, 자산: {int(total_eval):,}원, 수익률: {weekly_profit_rate:+.2f}%\n"
    with open("weekly_assets_log.txt", "a", encoding="utf-8") as f:
        f.write(log_line)

def get_and_clear_weekly_report():
    if not os.path.exists("weekly_assets_log.txt"): return "데이터 없음"
    with open("weekly_assets_log.txt", "r", encoding="utf-8") as f:
        content = f.read()
    open("weekly_assets_log.txt", "w").close()
    return content

# --- [핵심 기능: 주간 매매 로그 분석] ---
def get_weekly_trade_summary():
    """trade_log.csv를 읽어 종목별 확정 수익 합산"""
    if not os.path.exists(TRADE_LOG_FILE) or os.stat(TRADE_LOG_FILE).st_size == 0:
        return "이번 주 확정 수익(매도) 내역이 없습니다."
    
    summary = {}
    total_realized = 0
    
    with open(TRADE_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(',')
            if len(parts) < 3: continue
            ticker = parts[1]
            profit = int(parts[2])
            
            summary[ticker] = summary.get(ticker, 0) + profit
            total_realized += profit
            
    # 리포트 생성
    report = "🪙 **[주간 종목별 확정 수익 내역]**\n"
    # 수익이 높은 순서대로 정렬
    sorted_summary = sorted(summary.items(), key=lambda x: x[1], reverse=True)
    
    for ticker, amount in sorted_summary:
        emoji = "✅" if amount >= 0 else "❌"
        report += f"{emoji} **{ticker}**: `{amount:+,}원` 확정\n"
    
    report += f"\n💰 **주간 매도 수익 합계**: `{total_realized:+,}원`"
    
    # 분석 후 로그 파일 비우기 (새로운 주 시작)
    open(TRADE_LOG_FILE, "w").close()
    return report

print("--- 업비트 주간 성적 추적 봇 V4.0 가동 ---")
send_discord_msg("🚀 **성적 추적 봇 V4.0** 가동\n- 30분 단위 알림\n- 월요일 9시 매매 로그 기반 결산")

last_report_min = -1
daily_check_flag = False
weekly_base_asset = load_weekly_base()

while True:
    try:
        now = datetime.now()
        balances = upbit.get_balances()
        
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
                    target_ticker = f"KRW-{ticker}"
                    current_price = pyupbit.get_current_price(target_ticker)
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

        # --- [로직 1: 정각 기준 30분마다 실시간 알림] ---
        if now.minute in [0, 30] and now.minute != last_report_min:
            status = (
                f"📊 **[실시간 자산 리포트]**\n"
                f"{individual_details}\n"
                f"💰 **현재 총 자산**: `{int(total_eval):,}원`\n"
                f"📅 **주간 성적**: `{int(weekly_diff):+,}원` (**{weekly_profit_rate:+.2f}%**)\n"
                f"*(기준: 이번주 월요일 09:00)*"
            )
            send_discord_msg(status)
            last_report_min = now.minute

        # --- [로직 2: 매일 아침 9시 기록 및 월요일 최종 결산] ---
        if now.hour == 9 and now.minute == 0 and not daily_check_flag:
            # 월요일 아침 9시: 한 주간의 매매 로그 분석
            if now.weekday() == 0:
                trade_summary = get_weekly_trade_summary() # 로그 파일 읽고 비움
                daily_log = get_and_clear_weekly_report()
                
                final_msg = (
                    f"📅 **[지난주 투자 성적 최종 결산]**\n\n"
                    f"{trade_summary}\n\n"
                    f"📝 **일별 자산 흐름:**\n```csv\n{daily_log}```\n"
                    f"📈 **전체 자산 변동**: `{int(weekly_diff):+,}원` ({weekly_profit_rate:+.2f}%)\n"
                    f"💰 **최종 총 자산**: `{int(total_eval):,}원`"
                )
                send_discord_msg(final_msg)
                
                # 기준가 갱신 및 저장
                weekly_base_asset = total_eval
                save_weekly_base(weekly_base_asset)
                send_discord_msg(f"🚩 **이번 주 기준가가 갱신되었습니다.**\n시작 자산: `{int(weekly_base_asset):,}원`")

            # 매일 아침: 일일 자산 로그 저장
            save_daily_asset(total_eval, weekly_profit_rate)
            daily_check_flag = True
            
        if now.hour != 9:
            daily_check_flag = False

        time.sleep(20)
        
    except Exception as e:
        print(f"에러 발생: {e}")
        time.sleep(10)